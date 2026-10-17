"""
読むためのレポートを書き出す（`priorwork export`）。

`reports/*.md` は作業用で、管理ブロックのコメントや未記入の記入欄、テンプレートの説明文を含む。
ここでは、それらを除いた「読むための版」を Markdown / HTML / Word で作る。
未記入・未確認・検査エラーが残っていれば、冒頭に「下書き」の表示を付けて、完成品と取り違えないようにする。

原稿から始めるサーベイ（`new --manuscript`）では、`--draft` で原稿の 1〜3 章の下書きだけを書き出す。
レポートの `<!-- priorwork:draft -->` の直後の節を取り出し、本文で引用した採用論文の参照文献を付ける。
原稿に貼るためのものなので、「下書き」の表示は付けない（問題はコマンドの出力で伝える）。
"""

import html
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import i18n
from .check import ERROR, check_survey, find_citations
from .i18n import t, tl
from .survey import BIBLIO_LABEL, CARD_FIELDS, INCLUDED, Survey, first_surname, render_references, year_labels

FORMATS = {"html": ".html", "md": ".clean.md", "docx": ".docx"}
DRAFT_FORMATS = {"html": ".draft.html", "md": ".draft.md", "docx": ".draft.docx"}
DRAFT_ANCHOR = "<!-- priorwork:draft -->"

# テンプレート（assets/<lang>/templates/*.md）にある、執筆者向けの説明文。両方の言語
_HINTS = [
    re.compile(r"^\d+章のカードの記入内容から自動で作られます。\s*$"),
    re.compile(r"^引用キーは Zotero で管理する（ここではキーを作らない）。\s*$"),
    re.compile(r"^Built automatically from the paper cards in section \d+\.\s*$"),
    re.compile(r"^Citation keys are managed in Zotero \(none are made here\)\.\s*$"),
]
_RULES_HEADING = re.compile(r"^(?:記入のルール|How to fill in a card):\s*$")
_NOTE_START = re.compile(r"^>\s*\[!NOTE\]")
# 範囲の未設定の表示（survey.render_scope）。読むための版ではコマンドの案内を外す
_UNSET = "(not set — set it with `priorwork scope`)"

# 「- **X**:」「- **識別戦略の発展**（OLS 等 → DID）:」のように、コロンで終わって中身のない箇条書き
_LABEL_ONLY = re.compile(r"^(\s*)(?:[-*]|\d+\.)\s+\S.*[:：]\s*$")
_FIELD = re.compile(r"^- \*\*([^*]+)\*\*")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _strip_front_matter(md: str) -> Tuple[str, Optional[str]]:
    m = re.match(r"\A---\n(.*?)\n---\n", md, re.DOTALL)
    if not m:
        return md, None
    title = re.search(r'^title:\s*"?(.*?)"?\s*$', m.group(1), re.MULTILINE)
    return md[m.end():], title.group(1) if title else None


def _drop_note_and_rules(lines: List[str]) -> List[str]:
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if _NOTE_START.match(line):
            while i < len(lines) and lines[i].startswith(">"):
                i += 1
            continue
        if _RULES_HEADING.match(line):
            i += 1
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                i += 1
            continue
        if any(rx.match(line) for rx in _HINTS):
            i += 1
            continue
        out.append(line)
        i += 1
    return out


def _drop_empty_items(lines: List[str]) -> List[str]:
    """中身のない箇条書き（と、その下の中身のない子項目）を消す。"""
    out = list(lines)
    i = 0
    while i < len(out):
        m = _LABEL_ONLY.match(out[i])
        if not m:
            i += 1
            continue
        indent, j, end = len(m.group(1)), i + 1, i + 1
        while j < len(out) and (not out[j].strip() or _indent(out[j]) > indent):
            if out[j].strip():
                if not _LABEL_ONLY.match(out[j]):  # 中身のある子がある
                    break
                end = j + 1
            j += 1
        else:
            del out[i:end]  # 直後の空行は残す
            continue
        i += 1
    return out


def _mark_unfilled_cards(lines: List[str], lang: str) -> List[str]:
    # 自動で書かれる欄（書誌・確認レベル）しか無いカードは「未記入」
    fixed = {tl(la, label) for la in i18n.LANGS for label in (BIBLIO_LABEL, dict(CARD_FIELDS)["evidence"])}
    out, i = [], 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i].startswith("### #"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("#"):
                j += 1
            body = lines[i + 1:j]
            fields = [m.group(1) for m in (_FIELD.match(ln) for ln in body) if m]
            out.extend(body)
            if not [f for f in fields if f not in fixed]:
                while out and not out[-1].strip():
                    out.pop()
                out.extend(["- " + tl(lang, "(card not filled in)"), ""])
            i = j
            continue
        i += 1
    return out


def _mark_empty_sections(lines: List[str], lang: str) -> Tuple[List[str], List[str]]:
    out, empty, i = [], [], 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i].startswith("## "):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("## "):
                j += 1
            body = lines[i + 1:j]
            out.extend(body)
            if not any(ln.strip() for ln in body):
                out.extend(["*" + tl(lang, "(not written)") + "*", ""])
                empty.append(lines[i][3:].strip())
            i = j
            continue
        i += 1
    return out, empty


def clean_markdown(md: str, with_abstracts: bool = False, lang: str = "ja") -> Tuple[str, Optional[str], List[str]]:
    """作業用の Markdown を読むための版にする。戻り値: (本文, タイトル, 未記入の節)"""
    md, title = _strip_front_matter(md)
    lines = _drop_note_and_rules(md.splitlines())
    text = re.sub(r"<!--.*?-->[ \t]*\n?", "", "\n".join(lines), flags=re.DOTALL)
    for la in i18n.LANGS:
        text = text.replace(tl(la, _UNSET), tl(la, "(not set)"))
    if not with_abstracts:
        text = re.sub(r"<details>.*?</details>[ \t]*\n?", "", text, flags=re.DOTALL)
    lines = _drop_empty_items(text.splitlines())
    lines = _mark_unfilled_cards(lines, lang)
    lines, empty_sections = _mark_empty_sections(lines, lang)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n", title, empty_sections


def draft_issues(survey: Survey, empty_sections: List[str], langs=None) -> Dict[str, List[str]]:
    """完成品として読まれると困る点。言語ごとに返す（レポートの表示はサーベイの言語、CLI の表示は表示の言語）。"""
    unchecked = survey.unfilled()
    errors = [m for level, m in check_survey(survey, None) if level == ERROR]
    out: Dict[str, List[str]] = {}
    for lang in langs or (survey.lang, i18n.language()):
        issues = []
        if unchecked:
            numbers = tl(lang, ", ").join(f"#{e['number']}" for e in unchecked[:8]) + (tl(lang, " and more") if len(unchecked) > 8 else "")
            issues.append(tl(lang, "{n|# paper card is|# paper cards are} still \"{unchecked}\" ({numbers})",
                             n=len(unchecked), unchecked=tl(lang, "unchecked"), numbers=numbers))
        if empty_sections:
            issues.append(tl(lang, "empty sections: {names}", names=tl(lang, ", ").join(empty_sections)))
        if errors:
            issues.append(tl(lang, "`priorwork check` reports {n|# ERROR|# ERRORs}", n=len(errors)))
        out[lang] = issues
    return out


def _with_banner(text: str, issues: List[str], lang: str) -> str:
    if not issues:
        return text
    banner = "> ⚠️ **" + tl(lang, "Draft") + "**: " + tl(lang, ". ").join(issues) + tl(lang, ".") + "\n"
    lines = text.splitlines(True)
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            return "".join(lines[:i + 1]) + "\n" + banner + "".join(lines[i + 1:])
    return banner + "\n" + text


_CSS = """
:root { --bg:#fff; --fg:#1d2733; --muted:#5b6673; --line:#d9dee5; --accent:#1f5fae; --soft:#f4f6f9; --warn:#fff6dd; --warn-line:#e3c766; }
@media (prefers-color-scheme: dark) { :root { --bg:#14181d; --fg:#e3e8ee; --muted:#9aa5b1; --line:#2c343d; --accent:#7db3f0; --soft:#1b2027; --warn:#2b2614; --warn-line:#7a6a2a; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.75 "Hiragino Sans","Noto Sans JP","Yu Gothic",system-ui,sans-serif; }
main { max-width: 52rem; margin: 0 auto; padding: 2rem 1rem 4rem; }
h1 { font-size:1.7rem; line-height:1.35; margin:0 0 1.2rem; }
h2 { font-size:1.3rem; margin:2.6rem 0 .8rem; padding-bottom:.3rem; border-bottom:1px solid var(--line); }
h3 { font-size:1.05rem; margin:1.8rem 0 .4rem; }
a { color:var(--accent); overflow-wrap:anywhere; }
ul, ol { padding-left: 1.4rem; }
blockquote { margin:1rem 0; padding:.6rem 1rem; background:var(--warn); border-left:4px solid var(--warn-line); }
blockquote p { margin:.2rem 0; }
.table-wrap { overflow-x:auto; margin:1rem 0; }
table { border-collapse:collapse; font-size:.85rem; line-height:1.5; }
th, td { border:1px solid var(--line); padding:.4rem .6rem; vertical-align:top; min-width:7rem; }
th { background:var(--soft); text-align:left; }
details { margin:.5rem 0; color:var(--muted); }
code { background:var(--soft); padding:.1em .3em; border-radius:3px; }
pre.mermaid { background:#fff; color:#1d2733; padding:1rem; border:1px solid var(--line); border-radius:6px; overflow-x:auto; text-align:center; }
@media print { main { max-width:none; padding:0; } body { font-size:10.5pt; } h2 { break-after:avoid; } h3, tr { break-inside:avoid; } }
"""


# Mermaid の図（```mermaid）はブラウザで描く。図があるときだけ読み込む（読めなければコードのまま見える）。
# VS Code の拡張機能のビューワーは、このスクリプトだけを許可する（vscode-extension/src/extension.ts）
MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
_MERMAID_RE = re.compile(r'<pre><code class="language-mermaid">(.*?)</code></pre>', re.S)


def to_html(md: str, title: str, lang: str = "ja") -> str:
    from markdown_it import MarkdownIt
    body = MarkdownIt("commonmark", {"html": True}).enable("table").render(md)
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    body, diagrams = _MERMAID_RE.subn(r'<pre class="mermaid">\1</pre>', body)
    script = f'<script src="{MERMAID_JS}"></script>\n' if diagrams else ""
    return (f"<!DOCTYPE html>\n<html lang=\"{lang}\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{html.escape(title)}</title>\n<style>{_CSS}</style>\n</head>\n<body>\n<main>\n{body}</main>\n"
            f"{script}</body>\n</html>\n")


def draft_section(md: str) -> str:
    """`<!-- priorwork:draft -->` の直後の節（見出しの下から次の `## ` まで）。小見出し（###）は ## に上げる。"""
    i = md.find(DRAFT_ANCHOR)
    if i < 0:
        raise RuntimeError(t("The report has no draft of the manuscript ({anchor} before its heading). "
                             "Only a survey made with `priorwork new --manuscript` has one", anchor=DRAFT_ANCHOR))
    lines = md[i + len(DRAFT_ANCHOR):].lstrip("\n").splitlines()
    body = []
    for line in lines[1:] if lines and lines[0].startswith("## ") else lines:
        if line.startswith("## "):
            break
        body.append(line[1:] if line.startswith("### ") else line)
    text = re.sub(r"<!--.*?-->[ \t]*\n?", "", "\n".join(body), flags=re.DOTALL)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(_drop_empty_items(text.splitlines()))).strip() + "\n"


def cited_papers(survey: Survey, text: str) -> List[dict]:
    """本文で引用した採用論文（筆頭著者・年・a/b で照合。a/b の無い引用は、その著者・年の採用論文すべて）。"""
    included = survey.by_status(INCLUDED)
    labels = year_labels(included)
    cites = find_citations(text)
    return [e for e in included
            if any(c.name == first_surname(e["record"]) and str(c.year) == labels[e["key"]][:4]
                   and (not c.suffix or labels[e["key"]][4:] == c.suffix) for c in cites)]


def _draft_lang(text: str) -> str:
    """下書きの言語（原稿の言語）。仮名があれば日本語。"""
    return "ja" if re.search(r"[\u3040-\u30ff]", text) else "en"


def export_draft(survey: Survey, fmt: str = "md", out: Optional[Path] = None) -> Tuple[Path, List[str]]:
    """原稿の 1〜3 章の下書きを書き出す。戻り値: (出力先, 問題（表示の言語）)"""
    if fmt not in DRAFT_FORMATS:
        raise ValueError(t("The format is one of {choices}: {fmt}", choices=" / ".join(DRAFT_FORMATS), fmt=fmt))
    text = draft_section(survey.md_path.read_text(encoding="utf-8"))
    if not re.search(r"^(?!#)\S", text, re.MULTILINE):
        raise RuntimeError(t("The draft of the manuscript is not written yet"))
    lang = _draft_lang(text)
    cited = cited_papers(survey, text)
    labels = year_labels(survey.by_status(INCLUDED))
    text += "\n## " + tl(lang, "References") + "\n\n" + render_references(cited, labels, lang) + "\n"
    errors = [m for level, m in check_survey(survey, None) if level == ERROR]
    issues = [t("`priorwork check` reports {n|# ERROR|# ERRORs}", n=len(errors))] if errors else []
    out = out or survey.md_path.with_name(survey.md_path.stem + DRAFT_FORMATS[fmt])
    _write(out, text, survey.data["topic"], fmt, lang)
    return out, issues


def _write(out: Path, text: str, title: str, fmt: str, lang: str):
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "html":
        out.write_text(to_html(text, title, lang), encoding="utf-8")
    elif fmt == "md":
        out.write_text(text, encoding="utf-8")
    else:
        if not shutil.which("pandoc"):
            raise RuntimeError(t("Word output needs pandoc (https://pandoc.org/). You can also export HTML and print it to PDF from a browser"))
        subprocess.run(["pandoc", "-f", "commonmark+pipe_tables", "-o", str(out), "--metadata", f"title={title}"],
                       input=text, text=True, check=True)


def export(survey: Survey, fmt: str = "html", out: Optional[Path] = None, with_abstracts: bool = False) -> Tuple[Path, List[str]]:
    """レポートを書き出す。戻り値: (出力先, 下書きの理由（表示の言語）)"""
    if fmt not in FORMATS:
        raise ValueError(t("The format is one of {choices}: {fmt}", choices=" / ".join(FORMATS), fmt=fmt))
    lang = survey.lang
    text, title, empty_sections = clean_markdown(survey.md_path.read_text(encoding="utf-8"), with_abstracts, lang)
    issues = draft_issues(survey, empty_sections)
    text = _with_banner(text, issues[lang], lang)
    title = title or survey.data["topic"]
    out = out or survey.md_path.with_name(survey.md_path.stem + FORMATS[fmt])
    _write(out, text, title, fmt, lang)
    return out, issues[i18n.language()]


# ---------------- Octavo の原稿の書き方（[@key]）----------------

_O_NAME = r"(?:(?:van|von|de|der|den|du|da|di|le|la|del|dos)\s+){0,2}[A-ZÀ-Þ][\w'\-]+"
_O_AUTHORS = rf"{_O_NAME}(?:\s+et\s+al\.?|(?:\s*,\s*{_O_NAME})*,?\s*(?:and|&)\s*{_O_NAME})?"
_O_YEARS = r"\d{4}[a-z]?(?:\s*[,;]\s*\d{4}[a-z]?)*"
# 叙述型: Smith (2010) / Smith ら（2010, p. 5）
_O_NARRATIVE = re.compile(rf"\b({_O_AUTHORS})(\s*(?:ら|ほか|他)?\s*)[(（]\s*({_O_YEARS})\s*(?:[,，:]\s*([^()（）]*?))?\s*[)）]")
# 括弧型の中身の 1 件: e.g., Smith 2010, p. 3 / Smith and Jones, 2010a
_O_ITEM = re.compile(rf"^(.*?)\b({_O_AUTHORS})\s*,?\s+({_O_YEARS})\s*(?:,\s*(.+))?$", re.S)
_O_PAREN = re.compile(r"[(（]([^()（）]*\d{4}[^()（）]*)[)）]")


def _o_key(name_part: str, year: str, labels_index: Dict[Tuple[str, str], dict], bib_keys: Dict[str, str],
           missing: Dict[str, dict]) -> Optional[str]:
    first = re.split(r"\s+et\s+al|\s*,\s*|\s*(?:\band\b|&)\s*", name_part.strip())[0].split()[-1]
    from .survey import surname
    entry = labels_index.get((surname(first), year))
    if entry is None:
        return None
    key = bib_keys.get(entry["key"])
    if key:
        return key
    missing[entry["key"]] = entry
    from .octavo import MISSING_PREFIX
    return f"{MISSING_PREFIX}{re.sub(r'[^A-Za-z0-9]', '', first)}{year}"


def octavo_citations(text: str, survey: Survey, bib_entries: List[dict]) -> Tuple[str, List[dict]]:
    """下書きの「著者 (年)」を Pandoc の引用（[@key]）にする。戻り値: (本文, .bib に無い採用論文)。
    採用論文に当たらない引用は、そのまま残す（check が ERROR にする）。"""
    from .octavo import match_entry
    included = survey.by_status(INCLUDED)
    labels = year_labels(included)
    index = {(first_surname(e["record"]), labels[e["key"]]): e for e in included}
    bib_keys = {e["key"]: (match_entry(e["record"], bib_entries) or {}).get("key", "") for e in included}
    missing: Dict[str, dict] = {}

    def years(s: str) -> List[str]:
        return re.findall(r"\d{4}[a-z]?", s)

    def paren(m: "re.Match") -> str:
        items, out = m.group(1).split(";"), []
        for item in items:
            im = _O_ITEM.match(item.strip())
            if not im:
                return m.group(0)
            prefix, names, ys, loc = im.group(1).strip(), im.group(2), years(im.group(3)), (im.group(4) or "").strip()
            keys = [_o_key(names, y, index, bib_keys, missing) for y in ys]
            if None in keys:
                return m.group(0)
            for i, k in enumerate(keys):
                out.append(" ".join(x for x in (prefix if i == 0 else "", f"@{k}", loc if i == len(keys) - 1 else "")
                                    if x))
        return "[" + "; ".join(out) + "]"

    def narrative(m: "re.Match") -> str:
        names, ys, loc = m.group(1), years(m.group(3)), (m.group(4) or "").strip()
        keys = [_o_key(names, y, index, bib_keys, missing) for y in ys]
        if None in keys:
            return m.group(0)
        if len(keys) == 1:
            return f"@{keys[0]}" + (f" [{loc}]" if loc else "")
        return f"{names} [" + "; ".join(f"-@{k}" for k in keys) + (f", {loc}" if loc else "") + "]"

    text = _O_PAREN.sub(paren, text)
    text = _O_NARRATIVE.sub(narrative, text)
    return text, list(missing.values())


def synthesis_sections(md: str) -> str:
    """先行研究のまとめの節（テンプレートで `<!-- priorwork:synthesis -->` を付けた節: 学説・手法・論争・空白など）を
    ひと続きにする。見出しの番号（「2. 」）と、書き方の注・空の記入欄は除く。"""
    from .check import SYNTHESIS_MARK
    parts = []
    for m in re.finditer(re.escape(SYNTHESIS_MARK), md):
        head = md.rfind("\n## ", 0, m.start())
        if head < 0:
            continue
        title = re.sub(r"^\d+\.\s*", "", md[head + 4:md.find("\n", head + 1)].strip())
        end = md.find("\n## ", m.end())
        body = re.sub(r"<!--.*?-->[ \t]*\n?", "", md[m.end():end if end >= 0 else len(md)], flags=re.S)
        body = "\n".join(_drop_empty_items(body.strip().splitlines())).strip()
        if body:
            parts.append(f"## {title}\n\n{body}\n")
    return "\n".join(parts)


def octavo_text(survey: Survey, md: str) -> str:
    """Octavo の原稿に持っていく文章: 原稿の 1〜3 章を書くサーベイなら下書き、それ以外は先行研究のまとめの節。"""
    return draft_section(md) if survey.purpose == "draft" else synthesis_sections(md)


def export_octavo(survey: Survey, bib: Path, out: Optional[Path] = None, project: str = "") -> Tuple[Path, List[dict]]:
    """Octavo の原稿に貼れる形（[@key] の引用。参考文献は Octavo が .bib から作る）で書き出す。
    キーはそのプロジェクトの .bib から取るので、プロジェクトごとに書き出す（reports/<名前>.<プロジェクト>.octavo.md）。"""
    from .octavo import read_bib
    text = octavo_text(survey, survey.md_path.read_text(encoding="utf-8"))
    if not re.search(r"^(?!#)\S", text, re.MULTILINE):
        raise RuntimeError(t("The draft of the manuscript is not written yet") if survey.purpose == "draft"
                           else t("The sections on the literature (theories, methods, debates, gaps) are not written yet"))
    entries = read_bib(bib)
    if not entries:
        raise RuntimeError(t("No entries in {path}. Pull it from Zotero first (`octavo bib pull`)", path=bib))
    text, missing = octavo_citations(text, survey, entries)
    stem = survey.md_path.stem + (f".{re.sub(r'[^A-Za-z0-9_-]+', '_', project)}" if project else "")
    out = out or survey.md_path.with_name(stem + ".octavo.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out, missing
