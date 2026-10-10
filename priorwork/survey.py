"""
サーベイの状態管理と Markdown 生成。

reports/YYYYMMDD_<slug>.md              … 人（とエージェント）が読み書きするレポート本体
.priorwork/surveys/YYYYMMDD_<slug>.json … 論文候補・採否・検索履歴などの状態（CLI が管理）

Markdown のうち `<!-- BEGIN priorwork:NAME -->` 〜 `<!-- END priorwork:NAME -->` の範囲は CLI が再生成する。
ただし「各論文の詳細」カード（papers）は、見出しと書誌行だけを再生成し、
RQ・識別戦略などの記入内容はそのまま残す。比較マトリクスはカードの記入内容から作る。

レポートに書く文言（見出し・記入欄の名前・確認レベル）は、サーベイの言語（状態ファイルの `lang`）で決まる。
表示の言語（i18n.language()）とは別。読むときは、どちらの言語の記入欄名・確認レベルも受け付ける。
"""

import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from . import i18n, ssci
from .i18n import t, tl
from .workspace import REPORTS_DIR, ROOT, STATE_DIR, template_path, workspace_lang

CANDIDATE, INCLUDED, EXCLUDED, MAYBE = "candidate", "included", "excluded", "maybe"
STATUSES = (CANDIDATE, INCLUDED, EXCLUDED, MAYBE)
# 表示名（英語が原文。表示は status_label()、レポートは status_label(s, lang)）
STATUS_NAMES = {CANDIDATE: "Candidate", INCLUDED: "Included", EXCLUDED: "Excluded", MAYBE: "Maybe"}

# 状態 JSON の形式の版。形式を変えるときは版を上げ、MIGRATIONS[旧版] に旧版 → 次の版への変換を登録する
SCHEMA_VERSION = 3

DEPTHS = {"quick": "Quick (a narrow topic; get an overview fast)",
          "full": "Full (a broad topic; aim for coverage)"}
DEFAULT_DEPTH = "full"
BLOCKS = ("scope", "matrix", "papers", "references", "log")
MARKER = "priorwork"

# カードの記入欄: (キー, ラベル)。ラベルは英語が原文で、レポートにはサーベイの言語で書く。
# 読むときはどちらの言語のラベルも受け付ける（括弧の前までの先頭一致）
CARD_FIELDS = [
    ("evidence", "Evidence"),
    ("rq", "RQ"),
    ("x", "X (explanatory variable / treatment)"),
    ("y", "Y (outcome)"),
    ("data", "Data / sample"),
    ("method", "Identification"),
    ("findings", "Main findings"),
    ("limits", "Limitations"),
    ("memo", "Notes"),
]
BIBLIO_LABEL = "Source"
MATRIX_FIELDS = ["rq", "x", "y", "data", "method", "findings", "limits"]
# 原稿から始めるサーベイ（`new --manuscript`）だけのカードの記入欄: 論文が原稿のどの主張を支える・食い違うか
ROLE_FIELD = ("role", "Role in the manuscript")
MANUSCRIPT_CARD_FIELDS = [CARD_FIELDS[0], ROLE_FIELD, *CARD_FIELDS[1:]]

# 確認レベル。キーは状態の判定に使い、表記はサーベイの言語で書く（読むときは両方の言語を受け付ける）
EVIDENCE_UNCHECKED, EVIDENCE_ABSTRACT, EVIDENCE_FULLTEXT = "unchecked", "abstract", "fulltext"
EVIDENCE_NAMES = {EVIDENCE_UNCHECKED: "unchecked", EVIDENCE_ABSTRACT: "abstract only",
                  EVIDENCE_FULLTEXT: "full text checked"}
EVIDENCE_KEYS = tuple(EVIDENCE_NAMES)

# レポートの表の見出し（英語が原文。サーベイの言語で書く）
SCOPE_ROWS = [("question", "Research question"), ("years", "Period"), ("fields", "Fields"),
              ("inclusion", "Inclusion criteria"), ("exclusion", "Exclusion criteria")]
MATRIX_HEADS = ["Paper", "Journal", "RQ", "X", "Y", "Data / sample", "Identification", "Main findings", "Limitations",
                "Checked"]
LOG_HEADS = ["Time", "Kind", "Query / target", "Conditions", "Hits", "New candidates"]

_CARD_MARKER = re.compile(r"^<!-- paper: (\S+) -->\s*$")


def status_label(status: str, lang: Optional[str] = None) -> str:
    """採否の名前。lang を省くと表示の言語。"""
    return tl(lang or i18n.language(), STATUS_NAMES[status])


def evidence_label(key: str, lang: str) -> str:
    return tl(lang, EVIDENCE_NAMES[key])


def evidence_key(value: str) -> Optional[str]:
    """カードに書かれた確認レベル（どちらの言語でも）→ キー。空なら unchecked、読めなければ None。"""
    v = (value or "").strip()
    if not v:
        return EVIDENCE_UNCHECKED
    for key in EVIDENCE_KEYS:
        if any(v.lower() == evidence_label(key, lang).lower() for lang in i18n.LANGS):
            return key
    return None


def _label_stem(label: str) -> str:
    return re.split(r"\s*[（(]", label, 1)[0]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def paper_key(record: Dict[str, Any]) -> str:
    if record.get("doi"):
        return "doi:" + record["doi"].lower()
    if record.get("openalex_id"):
        return "openalex:" + record["openalex_id"]
    return "s2:" + record.get("id", "")


def ascii_fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def display_surname(name: str) -> str:
    """姓（表示用）。"Robert E. Lucas Jr." → "Lucas" のように Jr. などの接尾辞を除く。"""
    parts = name.replace(",", " ").split()
    while len(parts) > 1 and parts[-1].rstrip(".").lower() in _NAME_SUFFIXES:
        parts.pop()
    return parts[-1].rstrip(".") if parts else ""


def surname(name: str) -> str:
    """照合用の姓（アクセントを落とした小文字）。"""
    return ascii_fold(display_surname(name)).lower()


def author_short(authors: List[str]) -> str:
    names = [display_surname(a) for a in authors if a.split()]
    if not names:
        return "Unknown"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return f"{names[0]} et al."


def md_cell(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text)).replace("|", "\\|").strip()


def sanitize_slug(name: str) -> str:
    name = re.sub(r"[^\w\s-]", "", ascii_fold(name))
    name = re.sub(r"[\s_-]+", "_", name)
    return name.strip("_").lower()[:60]


# ---------------- State ----------------

class SurveyError(RuntimeError):
    pass


def migrate_data(data: Dict[str, Any], name: str = "") -> Dict[str, Any]:
    """状態ファイルを現在の形式にそろえる。新しいエンジンで作られたファイルは、古いエンジンでは触らない。"""
    version = data.get("version", 1)
    if version > SCHEMA_VERSION:
        raise SurveyError(t("{name} was written by a newer priorwork (format v{version}; this one reads v{supported}). "
                            "Update it with `priorwork upgrade`",
                            name=name or t("The state file"), version=version, supported=SCHEMA_VERSION))
    while version < SCHEMA_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
        data["version"] = version
    return data


def _migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """v2: 採否の履歴（history）を持つ。v1 には履歴が無いので、移行時点の状態を最初の記録にする。"""
    for e in data["papers"].values():
        e.setdefault("history", [{"at": e.get("updated") or e.get("added") or "", "status": e["status"],
                                  "reason": e.get("reason", ""), "migrated": True}])
    return data


def _migrate_v2_to_v3(data: Dict[str, Any]) -> Dict[str, Any]:
    """v3: レポートの言語（lang）を持つ。v2 までは日本語のレポートしか無かった。"""
    data.setdefault("lang", "ja")
    return data


MIGRATIONS: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]] = {1: _migrate_v1_to_v2, 2: _migrate_v2_to_v3}


def status_trail(entry: Dict[str, Any], lang: Optional[str] = None) -> str:
    """採否の経緯（例: Maybe → Excluded (theory only) → Included）。同じ状態が続く記録はまとめる。"""
    lang = lang or i18n.language()
    steps: List[str] = []
    for h in entry.get("history", []):
        step = status_label(h["status"], lang) + (tl(lang, " ({reason})", reason=h["reason"]) if h.get("reason") else "")
        if not steps or steps[-1] != step:
            steps.append(step)
    return " → ".join(steps)


def revised(entry: Dict[str, Any]) -> bool:
    """一度下した採否（採用・除外・保留）を、別の採否に変えたことがあるか。"""
    decisions = [h["status"] for h in entry.get("history", []) if h["status"] != CANDIDATE]
    return any(a != b for a, b in zip(decisions, decisions[1:]))


class Survey:
    def __init__(self, md_path: Path, data: Dict[str, Any], json_path: Optional[Path] = None):
        self.md_path = md_path
        self.json_path = json_path or STATE_DIR / f"{md_path.stem}.json"
        self.data = data

    # ---- lifecycle ----

    @classmethod
    def create(cls, topic: str, slug: str, scope: Dict[str, str], today: Optional[date] = None,
               reports_dir: Optional[Path] = None, state_dir: Optional[Path] = None,
               template: Optional[Path] = None, depth: str = DEFAULT_DEPTH, lang: Optional[str] = None,
               manuscript: Optional[str] = None) -> "Survey":
        if depth not in DEPTHS:
            raise SurveyError(t("depth is one of {choices}: {depth}", choices=" / ".join(DEPTHS), depth=depth))
        lang = i18n.normalize(lang or workspace_lang(ROOT))
        today = today or date.today()
        reports_dir = reports_dir or REPORTS_DIR
        state_dir = state_dir or STATE_DIR
        template = template or template_path(lang, manuscript=bool(manuscript))
        slug = sanitize_slug(slug) or "survey"
        md_path = reports_dir / f"{today.strftime('%Y%m%d')}_{slug}.md"
        json_path = state_dir / f"{md_path.stem}.json"
        if md_path.exists() or json_path.exists():
            raise SurveyError(t("{name} already exists", name=md_path.name))
        data = {
            "version": SCHEMA_VERSION,
            "topic": topic,
            "created": today.isoformat(),
            "lang": lang,
            "depth": depth,
            "scope": {k: scope.get(k, "") for k in ("question", "years", "fields", "inclusion", "exclusion")},
            "next_number": 1,
            "papers": {},
            "searches": [],
        }
        if manuscript:
            data["manuscript"] = manuscript_ref(manuscript, reports_dir.parent)
        survey = cls(md_path, data, json_path)
        values = {"topic": topic, "topic_yaml": topic.replace("\\", "\\\\").replace('"', '\\"'),
                  "date": today.isoformat()}
        text = template.read_text(encoding="utf-8")
        reports_dir.mkdir(parents=True, exist_ok=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        md_path.write_text(re.sub(r"\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), text),
                           encoding="utf-8")
        survey.save()
        survey.render()
        return survey

    @classmethod
    def load(cls, ref: str, reports_dir: Optional[Path] = None, state_dir: Optional[Path] = None) -> "Survey":
        """ref: .md / .json のパス、ファイル名（拡張子なし可）、または slug。"""
        reports_dir = reports_dir or REPORTS_DIR
        state_dir = state_dir or STATE_DIR
        path = Path(ref)
        name = path.name.removesuffix(".md").removesuffix(".json")
        if path.suffix in (".md", ".json"):
            stems = [name]
        else:
            stems = sorted(p.stem for p in state_dir.glob("*.json")
                           if p.stem == name or p.stem.split("_", 1)[-1] == name)
        if not stems:
            raise SurveyError(t("No survey matches {ref} (see the list with `priorwork status`)", ref=ref))
        if len(stems) > 1:
            raise SurveyError(t("More than one survey matches: {names}", names=", ".join(stems)))
        md_path, json_path = reports_dir / f"{stems[0]}.md", state_dir / f"{stems[0]}.json"
        if not json_path.exists():
            raise SurveyError(t("The state file is missing: {path}", path=json_path))
        if not md_path.exists():
            raise SurveyError(t("The report is missing: {path}", path=md_path))
        return cls(md_path, migrate_data(json.loads(json_path.read_text(encoding="utf-8")), json_path.name), json_path)

    @staticmethod
    def list_all(reports_dir: Optional[Path] = None, state_dir: Optional[Path] = None) -> List["Survey"]:
        return [Survey.load(p.name, reports_dir, state_dir) for p in sorted((state_dir or STATE_DIR).glob("*.json"))]

    def save(self):
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.json_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.json_path)

    @property
    def name(self) -> str:
        return self.md_path.stem

    @property
    def lang(self) -> str:
        """レポートの言語。lang を持たない（v2 までの）状態は日本語。"""
        return i18n.normalize(self.data.get("lang") or "ja")

    # ---- papers ----

    @property
    def papers(self) -> List[Dict[str, Any]]:
        return sorted(self.data["papers"].values(), key=lambda e: e["number"])

    def by_status(self, *statuses: str) -> List[Dict[str, Any]]:
        return [e for e in self.papers if e["status"] in statuses]

    def counts(self) -> Dict[str, int]:
        return {s: len(self.by_status(s)) for s in STATUSES}

    def get(self, number: int) -> Dict[str, Any]:
        for e in self.data["papers"].values():
            if e["number"] == number:
                return e
        raise SurveyError(t("#{number} is not in this survey", number=number))

    def find(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = paper_key(record)
        if key in self.data["papers"]:
            return self.data["papers"][key]
        title = ssci.normalize_title(record.get("title", ""))
        for e in self.data["papers"].values():
            # "Comment" のような短い汎用タイトル同士を同一視しないよう、ある程度の長さを要求する
            if len(title) > 20 and ssci.normalize_title(e["record"]["title"]) == title:
                return e
            if record.get("openalex_id") and e["record"].get("openalex_id") == record["openalex_id"]:
                return e
        return None

    def upsert(self, record: Dict[str, Any], found_by: str, status: str = CANDIDATE,
               reason: str = "") -> Tuple[Dict[str, Any], bool]:
        """候補として登録する。既にあれば（同じ DOI / タイトル）状態は変えず、発見経路だけ追記する。"""
        existing = self.find(record)
        if existing:
            if found_by not in existing["found_by"]:
                existing["found_by"].append(found_by)
            # WP 版で登録済みのところに掲載版が見つかったら、書誌情報を掲載版に差し替える
            if record["ssci"]["tier"] > existing["record"]["ssci"]["tier"]:
                old_key = existing["key"]
                existing["record"] = record
                existing["key"] = paper_key(record)
                if existing["key"] != old_key:
                    existing.setdefault("previous_keys", []).append(old_key)
                self.data["papers"].pop(old_key)
                self.data["papers"][existing["key"]] = existing
            return existing, False
        entry = {
            "number": self.data["next_number"],
            "key": paper_key(record),
            "status": status,
            "reason": reason,
            "found_by": [found_by],
            "added": now_iso(),
            "updated": now_iso(),
            "history": [{"at": now_iso(), "status": status, "reason": reason}],
            "record": record,
        }
        self.data["next_number"] += 1
        self.data["papers"][entry["key"]] = entry
        return entry, True

    def set_status(self, numbers: Iterable[int], status: str, reason: str = "") -> List[Dict[str, Any]]:
        entries = [self.get(n) for n in numbers]
        for e in entries:
            if (e["status"], e.get("reason", "")) != (status, reason):
                e.setdefault("history", []).append({"at": now_iso(), "status": status, "reason": reason})
            e["status"] = status
            e["reason"] = reason
            e["updated"] = now_iso()
        return entries

    def log_search(self, kind: str, query: str, params: Dict[str, Any], hits: int, new: int):
        self.data["searches"].append({"at": now_iso(), "kind": kind, "query": query,
                                      "params": {k: v for k, v in params.items() if v not in (None, False, "")},
                                      "hits": hits, "new": new})

    @property
    def depth(self) -> str:
        """quick / full。depth を持たない既存サーベイは full として扱う。"""
        return self.data.get("depth", DEFAULT_DEPTH)

    def set_depth(self, depth: str):
        if depth not in DEPTHS:
            raise SurveyError(t("depth is one of {choices}: {depth}", choices=" / ".join(DEPTHS), depth=depth))
        self.data["depth"] = depth

    @property
    def zotero_collection(self) -> Dict[str, str]:
        """結び付けた Zotero のコレクション（{key, name}）。無ければ空の dict（キーは任意。無い状態ファイルもそのまま読める）。"""
        return self.data.get("zotero_collection") or {}

    def set_zotero_collection(self, key: str, name: str):
        if key:
            self.data["zotero_collection"] = {"key": key, "name": name}
        else:
            self.data.pop("zotero_collection", None)

    @property
    def root(self) -> Path:
        """ワークスペースの根（reports/ の親）。"""
        return self.md_path.parent.parent

    @property
    def manuscript(self) -> str:
        """原稿のパス（ワークスペースからの相対。外ならそのまま）。原稿から始めるサーベイでなければ空。"""
        return self.data.get("manuscript") or ""

    def set_manuscript(self, path: str):
        """原稿を結び付ける（キーは任意。無い状態ファイルもそのまま読める）。"""
        self.data["manuscript"] = manuscript_ref(path, self.root)

    @property
    def card_spec(self) -> List[Tuple[str, str]]:
        """このサーベイのカードの記入欄。原稿から始めるサーベイには「原稿での役割」がある。"""
        return MANUSCRIPT_CARD_FIELDS if self.manuscript else CARD_FIELDS

    @property
    def matrix_fields(self) -> List[str]:
        return (["role"] if self.manuscript else []) + MATRIX_FIELDS

    @property
    def archived(self) -> str:
        """アーカイブした日（ISO）。していなければ空。アーカイブしたサーベイは一覧に出さない（ファイルは残る）。"""
        return self.data.get("archived") or ""

    def set_archived(self, archived: bool):
        if archived:
            self.data["archived"] = now_iso()
        else:
            self.data.pop("archived", None)

    def update_scope(self, **scope: Optional[str]):
        for k, v in scope.items():
            if v is not None:
                self.data["scope"][k] = v

    # ---- cards ----

    def card_fields(self) -> Dict[str, Dict[str, str]]:
        """採用論文ごとの記入欄（レポートから読む）。"""
        cards = parse_cards(extract_blocks(self.md_path.read_text(encoding="utf-8")).get("papers", ""))
        return {key: parse_card_fields(body) for key, body in cards.items()}

    def unfilled(self) -> List[Dict[str, Any]]:
        """確認レベルが「未確認」のままの採用論文。"""
        fields = self.card_fields()
        return [e for e in self.by_status(INCLUDED)
                if evidence_key(fields.get(e["key"], {}).get("evidence", "")) == EVIDENCE_UNCHECKED]

    def card(self, number: int) -> Dict[str, str]:
        """採用論文のカードの記入欄（フォーム用。1行目が行内の値、2行目以降が直下の箇条書き）。"""
        key = self._card_key(number)
        self.render()   # 採用したばかりでカードがまだ無ければ作る
        cards = parse_cards(extract_blocks(self.md_path.read_text(encoding="utf-8"))["papers"])
        return card_values(cards.get(key, ""))

    def set_card(self, number: int, values: Dict[str, str]) -> bool:
        """カードの記入欄を書き換え、マトリクスなどを再生成する。確認レベルはキー（unchecked など）で渡す。変更があれば True。"""
        key = self._card_key(number)
        unknown = sorted(set(values) - {k for k, _ in self.card_spec})
        if unknown:
            raise SurveyError(t("Unknown card fields: {names} (use {known})", names=", ".join(unknown),
                                known=", ".join(k for k, _ in self.card_spec)))
        values = dict(values)
        if "evidence" in values:
            if values["evidence"] not in EVIDENCE_KEYS:
                raise SurveyError(t("The evidence level is one of: {keys}", keys=", ".join(EVIDENCE_KEYS)))
            values["evidence"] = evidence_label(values["evidence"], self.lang)
        self.render()
        md = self.md_path.read_text(encoding="utf-8")
        cards = parse_cards(extract_blocks(md)["papers"])
        cards[key] = set_card_fields(cards.get(key, ""), values, self.lang)
        papers = "\n\n".join(f"<!-- paper: {k} -->\n{body}" for k, body in cards.items())
        new_md = self.rendered_markdown(replace_blocks(md, {"papers": papers}))
        if new_md == md:
            return False
        self.md_path.write_text(new_md, encoding="utf-8")
        self.save()
        return True

    def _card_key(self, number: int) -> str:
        e = self.get(number)
        if e["status"] != INCLUDED:
            raise SurveyError(t("#{number} is not included, so it has no card", number=number))
        return e["key"]

    # ---- rendering ----

    def render(self) -> bool:
        """管理ブロックを再生成して Markdown を書き戻す。変更があれば True。"""
        md = self.md_path.read_text(encoding="utf-8")
        new_md = self.rendered_markdown(md)
        if new_md != md:
            self.md_path.write_text(new_md, encoding="utf-8")
            self.save()  # カードのアーカイブが更新されている可能性がある
            return True
        return False

    def rendered_markdown(self, md: str) -> str:
        lang = self.lang
        blocks = extract_blocks(md)
        missing = [b for b in BLOCKS if b not in blocks]
        if missing:
            raise SurveyError(t("Managed blocks are missing: {names} (restore `<!-- BEGIN priorwork:{first} -->` … "
                                "`<!-- END priorwork:{first} -->`)", names=", ".join(missing), first=missing[0]))
        cards = parse_cards(blocks["papers"])
        included = sorted(self.by_status(INCLUDED), key=_chronological)
        labels = year_labels(included)

        card_texts = []
        bodies: Dict[str, str] = {}
        previous = {k: e["key"] for e in self.papers for k in e.get("previous_keys", [])}
        for old, new in previous.items():
            if old in cards and new not in cards:
                cards[new] = cards.pop(old)
            cards.pop(old, None)
        for e in included:
            body = cards.get(e["key"]) or e.pop("card_archive", None) or new_card_body(e["record"], lang, self.card_spec)
            bodies[e["key"]] = body
            card_texts.append(card_block(e, body, labels[e["key"]], lang))
        # 採用から外れた論文のカードは、記入内容を失わないよう状態ファイルに退避する
        for key, body in cards.items():
            if key in bodies:
                continue
            if key in self.data["papers"]:
                self.data["papers"][key]["card_archive"] = body
            else:
                card_texts.append(f"<!-- paper: {key} -->\n### ⚠️ "
                                  + tl(lang, "Unregistered paper (register it with `priorwork add`)") + f"\n{body}")

        fields = {key: parse_card_fields(body) for key, body in bodies.items()}
        none_yet = "*" + tl(lang, "(No included papers yet)") + "*"
        rendered = {
            "scope": render_scope(self.data, lang),
            "matrix": render_matrix(included, fields, labels, lang, role=bool(self.manuscript)),
            "papers": "\n\n".join(card_texts) if card_texts else none_yet,
            "references": render_references(included, labels, lang),
            "log": render_log(self.data, self.papers, lang),
        }
        return replace_blocks(md, rendered)


def manuscript_ref(path: str, root: Path) -> str:
    """原稿（ファイル、または原稿と結果の表・図を入れたフォルダ）のパスを確かめ、
    ワークスペースからの相対パス（外なら絶対パス）にする。"""
    p = Path(path).expanduser()
    p = (p if p.is_absolute() else Path.cwd() / p).resolve()
    if not p.exists():
        raise SurveyError(t("The manuscript is not found: {path}", path=path))
    try:
        return p.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(p)


def _chronological(e: Dict[str, Any]):
    r = e["record"]
    return (r.get("year") or 9999, first_surname(r), e["number"])


def first_surname(record: Dict[str, Any]) -> str:
    return surname(record["authors"][0]) if record.get("authors") else ""


def year_labels(included: List[Dict[str, Any]]) -> Dict[str, str]:
    """採用論文ごとの年の表記。本文で同じ書き方（「著者 (年)」）になる論文が複数あれば、
    タイトル順に 2001a, 2001b のように区別する。"""
    groups: Dict[Tuple[str, Any], List[Dict[str, Any]]] = {}
    for e in included:
        r = e["record"]
        groups.setdefault((ascii_fold(author_short(r["authors"])).lower(), r.get("year")), []).append(e)
    labels = {}
    for (_, year), entries in groups.items():
        base = str(year) if year else "n.d."
        if len(entries) == 1:
            labels[entries[0]["key"]] = base
            continue
        entries.sort(key=lambda e: (ssci.normalize_title(e["record"]["title"]), e["number"]))
        for i, e in enumerate(entries):
            labels[e["key"]] = f"{base}{'-' if not year else ''}{chr(ord('a') + i)}"
    return labels


# ---------------- Markdown blocks ----------------

_BLOCK_RE = re.compile(rf"<!-- BEGIN {MARKER}:(\w+) -->\n?(.*?)\n?<!-- END {MARKER}:\1 -->", re.S)


def extract_blocks(md: str) -> Dict[str, str]:
    return {m.group(1): m.group(2) for m in _BLOCK_RE.finditer(md)}


def replace_blocks(md: str, rendered: Dict[str, str]) -> str:
    def sub(m):
        name = m.group(1)
        if name not in rendered:
            return m.group(0)
        return f"<!-- BEGIN {MARKER}:{name} -->\n{rendered[name]}\n<!-- END {MARKER}:{name} -->"
    return _BLOCK_RE.sub(sub, md)


def strip_blocks(md: str) -> str:
    """管理ブロックを取り除いた文章（検査で人が書いた部分だけを見るとき）。"""
    return _BLOCK_RE.sub("", md)


def _biblio_prefixes() -> Tuple[str, ...]:
    return tuple(f"- **{tl(lang, BIBLIO_LABEL)}**" for lang in i18n.LANGS)


def parse_cards(papers_block: str) -> Dict[str, str]:
    """カードごとに、再生成する行（見出し・書誌・⚠️）を除いた本文を返す。"""
    cards: Dict[str, List[str]] = {}
    current = None
    regenerated = ("### ", "- ⚠️", *_biblio_prefixes())
    for line in papers_block.splitlines():
        m = _CARD_MARKER.match(line)
        if m:
            current = m.group(1)
            cards[current] = []
            continue
        if current is None:
            continue
        if line.startswith(regenerated):
            if not cards[current] or all(not l.strip() for l in cards[current]):
                continue
        cards[current].append(line)
    return {k: "\n".join(v).strip("\n") for k, v in cards.items()}


def _field_stems() -> List[Tuple[str, str]]:
    """(ラベルの括弧前の部分, キー)。両方の言語。長いものから照合する（"RQ" と "Data" などの前方一致の取り違え防止）。"""
    stems = {(_label_stem(tl(lang, label)), key) for key, label in MANUSCRIPT_CARD_FIELDS for lang in i18n.LANGS}
    return sorted(stems, key=lambda s: -len(s[0]))


def parse_card_fields(body: str) -> Dict[str, str]:
    """カード本文から記入欄の値を取り出す（行内の値。空なら直下の箇条書きを連結）。"""
    values: Dict[str, str] = {}
    current = None
    stems = _field_stems()
    for line in body.splitlines():
        m = re.match(r"^- \*\*(.+?)\*\*[:：]\s*(.*)$", line)
        if m:
            current = None
            for stem, key in stems:
                if m.group(1).startswith(stem):
                    current = key
                    values[key] = m.group(2).strip()
                    break
            continue
        sub = re.match(r"^\s{2,}[-*]\s+(.*)$", line)
        if current and sub and sub.group(1).strip():
            values[current] = " / ".join(v for v in (values.get(current, ""), sub.group(1).strip()) if v)
        elif not line.startswith(" "):
            current = None
    return values


_FIELD_LINE = re.compile(r"^- \*\*(.+?)\*\*[:：]\s*(.*)$")


def _field_spans(lines: List[str]) -> Dict[str, Tuple[int, int, str]]:
    """記入欄ごとの (先頭の行, 直下の箇条書きの終わりの次の行, 書かれているラベル)。parse_card_fields と同じ読み方。"""
    spans: Dict[str, Tuple[int, int, str]] = {}
    stems = _field_stems()
    for i, line in enumerate(lines):
        m = _FIELD_LINE.match(line)
        key = m and next((k for stem, k in stems if m.group(1).startswith(stem)), None)
        if key and key not in spans:
            j = i + 1
            while j < len(lines) and lines[j].startswith((" ", "\t")) and lines[j].strip():
                j += 1
            spans[key] = (i, j, m.group(1))
    return spans


def card_values(body: str) -> Dict[str, str]:
    """記入欄ごとの値（フォーム用）。1行目が行内の値、2行目以降が直下の箇条書き（印を外したもの）。"""
    lines = body.splitlines()
    values = {}
    for key, (i, j, _) in _field_spans(lines).items():
        inline = _FIELD_LINE.match(lines[i]).group(2).strip()
        subs = [re.sub(r"^[-*]\s+", "", ln.strip()) for ln in lines[i + 1:j]]
        values[key] = "\n".join([inline, *subs]).rstrip()
    return values


def set_card_fields(body: str, values: Dict[str, str], lang: str) -> str:
    """記入欄を書き換えたカード本文（card_values の逆）。ほかの行はそのまま。消されていた欄は最後の欄の後ろに足す。"""
    lines = body.splitlines()
    labels = dict(MANUSCRIPT_CARD_FIELDS)
    for key, value in values.items():
        spans = _field_spans(lines)
        parts = value.replace("\r\n", "\n").split("\n")
        inline = parts[0].strip()
        subs = [re.sub(r"^[-*]\s+", "", p.strip()) for p in parts[1:] if p.strip()]
        if key in spans:
            i, j, label = spans[key]
        else:
            i = j = max((s[1] for s in spans.values()), default=0)
            label = tl(lang, labels[key])
        lines[i:j] = [f"- **{label}**: {inline}".rstrip(), *(f"  - {s}" for s in subs)]
    return "\n".join(lines)


def new_card_body(record: Dict[str, Any], lang: str, fields: Optional[List[Tuple[str, str]]] = None) -> str:
    lines = []
    for key, label in fields or CARD_FIELDS:
        value = evidence_label(EVIDENCE_UNCHECKED, lang) if key == "evidence" else ""
        lines.append(f"- **{tl(lang, label)}**: {value}".rstrip())
    summary = []
    if record.get("tldr"):
        summary.append(f"**{tl(lang, 'TL;DR (generated by Semantic Scholar)')}**: {record['tldr']}")
    if record.get("abstract"):
        summary.append("**Abstract**: " + re.sub(r"\s+", " ", record["abstract"]))
    lines.append("")
    lines.append(f"<details><summary>{tl(lang, 'Abstract')}</summary>\n\n"
                 + ("\n\n".join(summary) or tl(lang, "(no abstract)")) + "\n\n</details>")
    return "\n".join(lines)


def biblio(record: Dict[str, Any]) -> str:
    s = f"*{record.get('journal_name') or 'N/A'}*"
    if record.get("volume"):
        s += f" {record['volume']}" + (f"({record['issue']})" if record.get("issue") else "")
    if record.get("pages"):
        s += f", {record['pages']}"
    return s


def doi_link(record: Dict[str, Any], lang: str) -> str:
    if record.get("doi"):
        return f"[{record['doi']}](https://doi.org/{record['doi']})"
    return f"[Link]({record['url']})" if record.get("url") else tl(lang, "no DOI")


def card_block(entry: Dict[str, Any], body: str, label: str, lang: str) -> str:
    r = entry["record"]
    lines = [
        f"<!-- paper: {entry['key']} -->",
        f"### #{entry['number']} {author_short(r['authors'])} ({label or r.get('year') or 'n.d.'}): {r['title']}",
        f"- **{tl(lang, BIBLIO_LABEL)}**: {biblio(r)} | {ssci.badge(r['ssci']['status'], lang)} | "
        + tl(lang, "cited by {n}", n=r.get("citation_count", 0)) + f" | {doi_link(r, lang)}",
    ]
    lines += [f"- ⚠️ {w}" for w in r.get("warnings", [])]
    return "\n".join(lines) + "\n" + body


def render_scope(data: Dict[str, Any], lang: str) -> str:
    sc = data["scope"]
    rows = [(label, sc.get(key)) for key, label in SCOPE_ROWS]
    basis = ssci.get_ssci_list()
    ssci_text = (tl(lang, "checked against the Clarivate list ({file})", file=basis.path.name) if basis.loaded
                 else tl(lang, "guessed from the journal name with the built-in list of major journals (verify)"))
    unset = tl(lang, "(not set — set it with `priorwork scope`)")
    lines = [f"- **{tl(lang, k)}**: {v or unset}" for k, v in rows]
    if data.get("manuscript"):
        lines.append(f"- **{tl(lang, 'Manuscript')}**: `{data['manuscript']}`")
    depth = data.get("depth", DEFAULT_DEPTH)
    lines.append(f"- **{tl(lang, 'Depth')}**: {depth} — {tl(lang, DEPTHS[depth])}")
    lines.append(f"- **{tl(lang, 'Basis of the SSCI status')}**: {ssci_text}")
    return "\n".join(lines)


def render_matrix(included: List[Dict[str, Any]], fields: Dict[str, Dict[str, str]],
                  labels: Optional[Dict[str, str]], lang: str, role: bool = False) -> str:
    """比較マトリクス。role（原稿から始めるサーベイ）なら、雑誌の次に「役割」の列を置く。"""
    labels = labels or {}
    heads = [tl(lang, h) for h in MATRIX_HEADS]
    keys = MATRIX_FIELDS
    if role:
        heads.insert(2, tl(lang, "Role"))
        keys = ["role", *MATRIX_FIELDS]
    header = "| " + " | ".join(heads) + " |\n|" + " :--- |" * len(heads)
    if not included:
        return header + "\n| " + tl(lang, "(No included papers yet)") + " |" + " |" * (len(heads) - 1)
    rows = []
    for e in included:
        r, f = e["record"], fields.get(e["key"], {})
        year = labels.get(e["key"]) or r.get("year") or "n.d."
        paper = f"**#{e['number']} {md_cell(author_short(r['authors']))} ({year})**<br>{md_cell(r['title'])}"
        journal = f"{md_cell(r.get('journal_name') or 'N/A')}<br>{ssci.badge(r['ssci']['status'], lang)}"
        if r.get("warnings"):
            journal += "<br>⚠️ " + tl(lang, "needs checking")
        cells = [md_cell(f.get(k, "")) for k in keys]
        evidence = f.get("evidence") or evidence_label(EVIDENCE_UNCHECKED, lang)
        rows.append(f"| {paper} | {journal} | " + " | ".join(cells) + f" | {md_cell(evidence)} |")
    return header + "\n" + "\n".join(rows)


def render_references(included: List[Dict[str, Any]], labels: Optional[Dict[str, str]], lang: str) -> str:
    if not included:
        return "*" + tl(lang, "(No included papers yet)") + "*"
    labels = labels or {}
    lines = []
    for e in sorted(included, key=lambda e: (first_surname(e["record"]), e["record"].get("year") or 0,
                                             labels.get(e["key"], ""))):
        r = e["record"]
        vol = ""
        if r.get("volume"):
            vol = f", {r['volume']}" + (f"({r['issue']})" if r.get("issue") else "")
        if r.get("pages"):
            vol += f", {r['pages']}"
        link = f"https://doi.org/{r['doi']}" if r.get("doi") else (r.get("url") or "")
        year = labels.get(e["key"]) or r.get("year") or "n.d."
        lines.append(f"- {', '.join(r['authors']) or 'Unknown'} ({year}). {r['title']}. "
                     f"*{r.get('journal_name') or 'N/A'}*{vol}. {link}")
    return "\n".join(lines)


def _flow_line(data: Dict[str, Any], papers: List[Dict[str, Any]], counts: Dict[str, int], lang: str) -> str:
    """検索 → 重複を除いた候補 → 採否 の流れ（PRISMA 風の件数）。"""
    runs = {k: [s for s in data["searches"] if s["kind"] in kinds]
            for k, kinds in (("search", ("search", "bulk")), ("snowball", ("snowball",)),
                             ("manual", ("manual", "zotero")))}
    # Zotero のコレクションから取り込んだものは「手で追加」に数える（ユーザーが選んで入れたもの）
    first = {k: sum(1 for e in papers if e["found_by"][:1] in ([k], ["zotero"] if k == "manual" else [k]))
             for k in runs}
    hits = sum(s["hits"] for s in runs["search"] + runs["snowball"])
    return (f"- **{tl(lang, 'Flow')}**: "
            + tl(lang, "{searches|# search|# searches} and {snowballs|# citation chase|# citation chases} "
                       "({hits|# hit|# hits} in all)", searches=len(runs["search"]), snowballs=len(runs["snowball"]),
                 hits=hits)
            + " → "
            + tl(lang, "{n|# paper|# papers} after removing duplicates (search {search} / citations {snowball} / "
                       "added by hand {manual})", n=len(papers), search=first["search"], snowball=first["snowball"],
                 manual=first["manual"])
            + " → "
            + tl(lang, "included {included}, maybe {maybe}, excluded {excluded}, not screened {candidate}",
                 included=counts[INCLUDED], maybe=counts[MAYBE], excluded=counts[EXCLUDED],
                 candidate=counts[CANDIDATE]))


def render_log(data: Dict[str, Any], papers: List[Dict[str, Any]], lang: str) -> str:
    counts = {s: sum(1 for e in papers if e["status"] == s) for s in STATUSES}
    lines = [f"- **{tl(lang, 'Counts')}**: "
             + " / ".join(f"{status_label(s, lang)} {counts[s]}" for s in (INCLUDED, MAYBE, CANDIDATE, EXCLUDED))]
    lines.append(_flow_line(data, papers, counts, lang))
    reasons: Dict[str, int] = {}
    no_reason = tl(lang, "no reason given")
    for e in papers:
        if e["status"] == EXCLUDED:
            reasons[e.get("reason") or no_reason] = reasons.get(e.get("reason") or no_reason, 0) + 1
    changed = [e for e in papers if revised(e)]
    sep = tl(lang, ", ")
    if changed:
        numbers = sep.join(f"#{e['number']}" for e in changed[:10]) + (tl(lang, " and more") if len(changed) > 10 else "")
        lines.append(f"- **{tl(lang, 'Decisions revised')}**: "
                     + tl(lang, "{n} ({numbers}; see the history with `priorwork list`)", n=len(changed), numbers=numbers))
    if reasons:
        lines.append(f"- **{tl(lang, 'Reasons for exclusion')}**: "
                     + sep.join(tl(lang, "{reason} ({n})", reason=k, n=v)
                                for k, v in sorted(reasons.items(), key=lambda x: -x[1])))
    if data["searches"]:
        lines += ["", "| " + " | ".join(tl(lang, h) for h in LOG_HEADS) + " |",
                  "| :--- | :--- | :--- | :--- | ---: | ---: |"]
        for s in data["searches"]:
            params = ", ".join(f"{k}={v}" for k, v in s["params"].items())
            lines.append(f"| {s['at'][:16].replace('T', ' ')} | {s['kind']} | {md_cell(s['query'])} | {md_cell(params)} "
                         f"| {s['hits']} | {s['new']} |")
    return "\n".join(lines)
