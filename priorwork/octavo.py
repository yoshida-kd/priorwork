"""Octavo（Markdown・Quarto で論文を書く道具）のプロジェクトとのつなぎ。

Priorwork の原稿（`new --manuscript`）が Octavo のプロジェクトの中にあれば、
  * プロジェクトの設定（`octavo.config.py`）から、参考文献の `.bib` と Zotero のコレクションを読む
  * `.bib` から、原稿が引いている論文（`[@key]`）の DOI を読む（`add --cited`）
  * 下書きの「著者 (年)」を、`.bib` のキーで `[@key]` に書き換える（`export --draft --octavo`）

**Octavo のファイルは読むだけで、書き換えない。** 書くのは、プロジェクトの受け取り場所
（`literature/priorwork/`。Octavo は原稿として拾わない）に、書き出した文章と添え状（JSON）を置くことだけ。
原稿に取り込むのは Octavo の側（エージェント）。書誌の正本は Zotero で、`.bib` は Zotero から
書き出したもの（Better BibTeX など）。Priorwork はキーを作らず、`.bib` にあるキーを使う。
設定は Python のファイルなので、実行せずに（ast で）書かれた値だけを読む。
"""
from __future__ import annotations

import ast
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_NAME = "octavo.config.py"
DEFAULT_BIB = "literature.bib"
# 下書きで、.bib にまだ無い論文の印。DOI があれば `PRIORWORK:<DOI>` にして、Octavo が `octavo bib pull` の後に
# .bib の DOI から本物のキーに置き換えられるようにする。置き換えるまでは、Octavo の検査が「無いキー」として拾う
MISSING_PREFIX = "PRIORWORK:"
# Priorwork が書き出す受け取り場所（プロジェクトの根から）と、添え状の形式の版。
# 添え状の形は Octavo との約束で、tests/fixtures/handoff.json が見本（Octavo のテストも同じ見本を見る）
INBOX = Path("literature") / "priorwork"
HANDOFF_FORMAT = "priorwork-handoff"
HANDOFF_VERSION = 1
# Pandoc の引用キーにそのまま書ける文字（それ以外を含む DOI は @{…} で囲む）
_KEY_SAFE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_:.#$%&\-+?<>~/]*[A-Za-z0-9_]$")


def placeholder(doi: str, fallback: str) -> str:
    """.bib に無い論文の印（`@` の後ろに書くもの）。DOI があれば DOI で、無ければ fallback（著者と年）で。"""
    if not doi:
        return MISSING_PREFIX + fallback
    key = MISSING_PREFIX + doi.lower()
    return key if _KEY_SAFE.match(key) and "}" not in key else "{" + key.replace("}", "") + "}"


def inbox(root: Path) -> Path:
    return Path(root) / INBOX


def find_project(path: Path) -> Optional[Path]:
    """path（ファイルかフォルダ）を含む Octavo のプロジェクトの根。無ければ None。"""
    p = path.resolve()
    for d in [p, *p.parents] if p.is_dir() else list(p.parents):
        if (d / CONFIG_NAME).is_file():
            return d
    return None


def read_config(root: Path) -> Dict[str, Any]:
    """`CONFIG = {...}` のうち、値がリテラルで書かれた鍵だけを返す（実行はしない）。"""
    try:
        tree = ast.parse((root / CONFIG_NAME).read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(tg, ast.Name) and tg.id == "CONFIG" for tg in node.targets) \
                and isinstance(node.value, ast.Dict):
            out = {}
            for k, v in zip(node.value.keys, node.value.values):
                try:
                    out[ast.literal_eval(k)] = ast.literal_eval(v)
                except (ValueError, TypeError, SyntaxError):
                    continue
            return out
    return {}


def collections_of(value: Any) -> List[str]:
    """設定の zotero_collection（None・名前・名前の並び）を、名前（パス）の並びにする。"""
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [v for v in value if isinstance(v, str) and v.strip()]
    return []


def project_info(root: Path) -> Dict[str, Any]:
    cfg = read_config(root)
    bib = root / (cfg.get("bib_file") or DEFAULT_BIB)
    return {"root": str(root), "name": root.name, "bib": str(bib), "bib_exists": bib.is_file(),
            "zotero_collections": collections_of(cfg.get("zotero_collection"))}


def within_collection(ours: str, theirs: str) -> bool:
    """コレクション ours が theirs そのものか、その下にあるか（Octavo は theirs の下のコレクションの文献も取る）。
    パス（"親 / 子" / "親/子"）は大文字小文字と区切りの空白を無視する。theirs が名前だけなら、ours のパスの
    どこかにその名前があればよい。"""
    po = [x.strip().lower() for x in ours.split("/")]
    pt = [x.strip().lower() for x in theirs.split("/")]
    if len(pt) == 1:
        return pt[0] in po
    return po[:len(pt)] == pt


# ---------------- .bib ----------------

def _split_fields(body: str) -> Dict[str, str]:
    """`name = {…}` / `name = "…"` / `name = 2020` の並びを読む（入れ子の {} も）。"""
    fields: Dict[str, str] = {}
    i, n = 0, len(body)
    while i < n:
        m = re.compile(r"\s*,?\s*([A-Za-z][\w\-:]*)\s*=\s*").match(body, i)
        if not m:
            break
        name, i = m.group(1).lower(), m.end()
        if i < n and body[i] in "{\"":
            close = "}" if body[i] == "{" else "\""
            depth, j = 0, i
            while j < n:
                ch = body[j]
                if ch == "\\":
                    j += 2
                    continue
                if close == "}" and ch == "{":
                    depth += 1
                elif ch == "}" and close == "}":
                    depth -= 1
                    if depth == 0:
                        break
                elif close == "\"" and ch == "\"" and j > i:
                    break
                j += 1
            value, i = body[i + 1:j], j + 1
        else:
            m2 = re.compile(r"[^,]*").match(body, i)
            value, i = m2.group(0), m2.end()
        fields[name] = re.sub(r"\s+", " ", value.replace("{", "").replace("}", "")).strip()
    return fields


def parse_bib(text: str) -> List[Dict[str, Any]]:
    """エントリーの並び: key, type, doi, title, year, authors（姓）。"""
    entries = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        kind = m.group(1).lower()
        if kind in ("comment", "string", "preamble"):
            continue
        depth, j = 1, m.end()
        while j < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        f = _split_fields(text[m.end():j - 1])
        year = f.get("year") or (f.get("date") or "")[:4]
        doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", f.get("doi", ""), flags=re.I).strip().lower()
        surnames = [a.split(",")[0].strip() if "," in a else a.strip().split(" ")[-1]
                    for a in re.split(r"\s+and\s+", f.get("author", "")) if a.strip()]
        entries.append({"key": m.group(2), "type": kind, "doi": doi, "title": f.get("title", ""),
                        "year": year if re.fullmatch(r"\d{4}", year or "") else "", "authors": surnames})
    return entries


def read_bib(path: Path) -> List[Dict[str, Any]]:
    try:
        return parse_bib(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return []


def _norm_title(title: str) -> str:
    title = unicodedata.normalize("NFKD", title.lower())
    return re.sub(r"[^a-z0-9]+", "", "".join(ch for ch in title if not unicodedata.combining(ch)))


def match_entry(record: Dict[str, Any], entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Priorwork の論文の書誌に当たる .bib のエントリー（DOI、無ければタイトルと年）。"""
    doi = (record.get("doi") or "").lower()
    if doi:
        for e in entries:
            if e["doi"] == doi:
                return e
    title = _norm_title(record.get("title") or "")
    if title:
        for e in entries:
            if _norm_title(e["title"]) == title and (not e["year"] or not record.get("year")
                                                     or e["year"] == str(record["year"])):
                return e
    return None


# Pandoc の引用キー（[@key] / @key）。メールアドレス（a@b）は前が語なので拾わない
_CITE_RE = re.compile(r"(?<![\w@])@\{?([A-Za-z0-9_][\w:.#$%&\-+?<>~/]*?)\}?(?=[\s;,\].)!?]|$)", re.M)


def cited_keys(text: str, known: Optional[set] = None) -> List[str]:
    """本文が引いているキー（出てきた順・重複なし）。known を渡せば .bib にあるものだけ。"""
    seen: Dict[str, None] = {}
    for m in _CITE_RE.finditer(text):
        key = m.group(1).rstrip(".:")
        if known is None or key in known:
            seen.setdefault(key, None)
    return list(seen)
