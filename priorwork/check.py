"""
サーベイの検査（`priorwork check`）。エージェントが書いた内容の取り違え・でっち上げを機械的に拾う。
"""

import re
import unicodedata
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

from . import ssci
from .i18n import t
from .survey import (
    CANDIDATE, EVIDENCE_ABSTRACT, EVIDENCE_FULLTEXT, EVIDENCE_KEYS, EVIDENCE_UNCHECKED, INCLUDED, MAYBE, Survey,
    SurveyError,
    evidence_key, evidence_label, extract_blocks, first_surname, parse_card_fields, parse_cards, strip_blocks, surname,
    year_labels,
)

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"

# 本文中の著者年引用:
#   叙述型   "Acemoglu et al. (2001)", "Acemoglu, Johnson and Robinson (2001, 2005)", "Dell (2010a, p. 3)"
#   括弧型   "(Dell, 2010)", "(e.g., Dell 2010; Acemoglu et al., 2001a, 2005)"
_NAME = r"(?:(?:van|von|de|der|den|du|da|di|le|la|del|dos)\s+){0,2}[A-Z][A-Za-z'\-]+"
_AUTHORS = rf"{_NAME}(?:\s+et\s+al\.?|(?:\s*,\s*{_NAME})*,?\s*(?:and|&)\s*{_NAME})?"
_YEAR = r"\d{4}[a-z]?"
_GAP = r"[\s\x00]"   # _fold が日本語などを \x00 にする。「Acemoglu ら (2001)」の「ら」を読み飛ばす
_NARRATIVE_RE = re.compile(rf"\b({_AUTHORS}){_GAP}*\(\s*({_YEAR}(?:\s*[,;]\s*{_YEAR})*)(?:\s*[,:][^()]*)?\s*\)")
_PAREN_RE = re.compile(r"\(([^()]*)\)")
_PAREN_ITEM_RE = re.compile(rf"\b({_AUTHORS}){_GAP}*,?{_GAP}+({_YEAR}(?:\s*,\s*{_YEAR})*)\b")
_YEAR_ITEM_RE = re.compile(r"(\d{4})([a-z]?)")
_DOI_RE = re.compile(r"(?:doi\.org/|doi:\s*)(10\.\d{4,9}/[^\s)\]>|]+)", re.IGNORECASE)
# 著者年引用と同じ形になるが論文ではないもの（組織の報告書・図表番号など）。未登録でも ERROR にせず INFO で伝える
_NON_AUTHOR_WORDS = {
    "bank", "fund", "organization", "organisation", "office", "ministry", "commission", "council", "bureau",
    "agency", "institute", "department", "government", "union", "nations", "census", "survey", "table", "figure",
    "fig", "section", "appendix", "chapter", "wave", "round", "model", "column", "panel", "equation", "act",
}  # May・Law など姓にもなる語は入れない（架空の引用を見逃すため）
_IGNORE_RE = re.compile(r"<!--\s*priorwork:ignore-citation\s+(.+?)\s*\(?\s*(\d{4})[a-z]?\s*\)?\s*-->")


class Citation(NamedTuple):
    name: str     # 筆頭著者の姓（照合用: 小文字・アクセントなし）
    year: int
    suffix: str   # 2001a の "a"
    text: str     # 表示用（例: "Acemoglu et al. (2001a)"）

    @property
    def is_non_author(self) -> bool:
        return self.name in _NON_AUTHOR_WORDS or bool(re.fullmatch(r"[A-Z]{2,}", self.text.split(" (")[0].split()[-1]))


Finding = Tuple[str, str]


def _fold(text: str) -> str:
    """アクセントを落とし（Acemoğlu → Acemoglu）、全角の括弧・句読点は半角にし（NFKD）、
    それ以外の非 ASCII 文字（日本語など）は \x00 にする。日本語を単に削除すると「IV、Dell (2010)」が
    「IVDell (2010)」に、空白にすると「IV（2000年代）」が「IV (2000 )」になり、引用と誤認するため。"""
    chars = []
    text = text.translate(str.maketrans({"’": "'", "、": ","}))
    for ch in unicodedata.normalize("NFKD", text):
        if unicodedata.combining(ch):
            continue
        chars.append(ch if ord(ch) < 128 else "\x00")
    return "".join(chars)


def _citations(authors: str, years: str) -> List[Citation]:
    first = re.split(r"\s+et\s+al|\s*,\s*|\s*(?:\band\b|&)\s*", authors)[0]
    shown = re.sub(r"\s+", " ", authors).strip()
    return [Citation(first.split()[-1].lower(), int(y), suf, f"{shown} ({y}{suf})")
            for y, suf in _YEAR_ITEM_RE.findall(years)]


def find_citations(text: str) -> List[Citation]:
    """本文中の著者年引用を取り出す（筆頭著者の姓・年・a/b の区別）。"""
    text = _fold(text)
    found: List[Citation] = []
    for m in _NARRATIVE_RE.finditer(text):
        found += _citations(m.group(1), m.group(2))
    for m in _PAREN_RE.finditer(text):
        for item in m.group(1).split(";"):
            for im in _PAREN_ITEM_RE.finditer(item):
                found += _citations(im.group(1), im.group(2))
    unique: Dict[Tuple[str, int, str], Citation] = {}
    for c in found:
        unique.setdefault((c.name, c.year, c.suffix), c)
    return sorted(unique.values())


def ignored_citations(md: str) -> Set[Tuple[str, int]]:
    """`<!-- priorwork:ignore-citation World Bank (2010) -->` で検査から外した引用。"""
    return {(surname(m.group(1)), int(m.group(2))) for m in _IGNORE_RE.finditer(_fold(md))}


def check_survey(survey: Survey, client: Optional[Any] = None) -> List[Finding]:
    findings: List[Finding] = []
    md = survey.md_path.read_text(encoding="utf-8")

    try:
        rendered = survey.rendered_markdown(md)
    except SurveyError as e:
        return [(ERROR, str(e))]
    if rendered != md:
        findings.append((WARN, t("The Markdown does not match the state file. Run `priorwork render`")))

    blocks = extract_blocks(md)
    cards = parse_cards(blocks.get("papers", ""))
    included = survey.by_status(INCLUDED)

    # 1. 採用論文ごとの記入状況と警告
    abstract_only = []
    for e in included:
        r, label = e["record"], f"#{e['number']} {e['record']['title'][:50]}"
        for w in r.get("warnings", []):
            findings.append((ERROR, f"{label}: ⚠️ {w}"))
        fields = parse_card_fields(cards.get(e["key"], ""))
        evidence = fields.get("evidence", "")
        level = evidence_key(evidence) if "evidence" in fields else None
        if level is None:
            findings.append((WARN, t("{label}: the evidence level must be one of {levels}: {value}", label=label,
                                     levels=" / ".join(evidence_label(k, survey.lang) for k in EVIDENCE_KEYS),
                                     value=repr(evidence))))
        elif level == EVIDENCE_UNCHECKED:
            findings.append((WARN, t("{label}: the evidence level is still \"{unchecked}\"", label=label,
                                     unchecked=evidence_label(EVIDENCE_UNCHECKED, survey.lang))))
        elif level == EVIDENCE_ABSTRACT:
            abstract_only.append(e)
        empty = [k for k in survey.matrix_fields if not fields.get(k)]
        if empty:
            findings.append((WARN, t("{label}: some fields are empty ({fields})", label=label, fields=", ".join(empty))))
        if r["ssci"]["status"] not in (ssci.SSCI, ssci.SSCI_LIKELY):
            findings.append((INFO, t("{label}: not an SSCI journal ({badge})", label=label,
                                     badge=ssci.badge(r["ssci"]["status"]))))

    # 2. 本文中の著者年引用が、登録済みの論文に対応しているか
    registered: Dict[Tuple[str, Any], List[dict]] = {}
    for e in survey.papers:
        r = e["record"]
        for a in r.get("authors", []):
            entries = registered.setdefault((surname(a), r.get("year")), [])
            if e not in entries:
                entries.append(e)
    labels = year_labels(included)
    # カードの記入欄も対象にする（要旨の <details> は論文側の文章なので除く）
    card_text = "\n".join(re.sub(r"<details>.*?</details>", "", body, flags=re.S) for body in cards.values())
    prose = re_blocks_removed(md) + "\n" + card_text
    ignored = ignored_citations(md)
    non_authors = []
    for c in find_citations(prose):
        if (c.name, c.year) in ignored:
            continue
        entries = registered.get((c.name, c.year), [])
        if not entries:
            if c.is_non_author:
                non_authors.append(c.text)
            else:
                findings.append((ERROR, t("The citation \"{cite}\" in the text has no registered paper "
                                          "(check that it exists with `priorwork get`, then register it with `priorwork add`)",
                                          cite=c.text)))
            continue
        adopted = [e for e in entries if e["status"] == INCLUDED]
        if not adopted:
            findings.append((WARN, t("The citation \"{cite}\" in the text is {numbers}, which is not included ({statuses})",
                                     cite=c.text, numbers=", ".join("#" + str(e["number"]) for e in entries),
                                     statuses=", ".join(sorted({e["status"] for e in entries})))))
            continue
        # 筆頭著者と年が同じ採用論文が複数あると、参照文献では 2001a / 2001b で区別している
        same = [e for e in adopted if first_surname(e["record"]) == c.name]
        suffixed = {labels[e["key"]][-1]: e for e in same if labels[e["key"]][-1:].isalpha()}
        assigned = ", ".join(f"#{e['number']} = {labels[e['key']]}" for e in suffixed.values())
        if c.suffix and c.suffix not in suffixed:
            findings.append((WARN, t("No included paper is \"{year}\" in the citation \"{cite}\"", cite=c.text,
                                     year=f"{c.year}{c.suffix}")
                                   + (f" ({assigned})" if suffixed
                                      else t(" (only one included paper has this author and year, so it needs no a/b)"))))
        elif not c.suffix and len(suffixed) > 1:
            findings.append((WARN, t("The citation \"{cite}\" in the text matches several included papers ({assigned}). "
                                     "Tell them apart as {year}a / {year}b, as the references do",
                                     cite=c.text, assigned=assigned, year=c.year)))
    if non_authors:
        findings.append((INFO, t("Not checked, taken for an organisation or a table/figure number: {cites} "
                                 "(if one is a paper, register it with `priorwork add`)", cites=", ".join(non_authors))))

    # 3. 本文中の DOI が登録済みか
    keys = {e["key"] for e in survey.papers}
    for doi in sorted({d.rstrip(".,;").lower() for d in _DOI_RE.findall(prose)}):
        if f"doi:{doi}" not in keys:
            findings.append((ERROR, t("The DOI {doi} in the text is not registered", doi=doi)))

    # 4. DOI の実在とタイトルの一致を OpenAlex で再確認
    if client is not None:
        with_doi = [e for e in included if e["record"].get("doi")]
        works = {}
        for w in client.openalex_works(dois=[e["record"]["doi"] for e in with_doi], select="doi,title"):
            works[(w.get("doi") or "").lower().replace("https://doi.org/", "")] = w
        for e in with_doi:
            if e["record"].get("warnings"):
                continue  # 検索時の照合で既に警告済み（上で ERROR として報告している）
            w = works.get(e["record"]["doi"].lower())
            label = f"#{e['number']} {e['record']['title'][:50]}"
            if not w:
                findings.append((ERROR, t("{label}: OpenAlex does not know the DOI {doi}", label=label,
                                          doi=e["record"]["doi"])))
            elif ssci.normalize_title(w.get("title") or "") != ssci.normalize_title(e["record"]["title"]):
                findings.append((ERROR, t("{label}: the DOI points to another title: \"{title}\"", label=label,
                                          title=w.get("title"))))

    # 5. 原稿から始めるサーベイ: 原稿が動いていないか（エージェントは原稿を読み直して下書きを書く）
    if survey.manuscript and not (survey.root / survey.manuscript).exists():
        findings.append((WARN, t("The manuscript {path} is not found. If it moved, set it again with "
                                 "`priorwork scope {name} --manuscript <path>`", path=survey.manuscript, name=survey.name)))

    # 6. 進捗
    pending = survey.by_status(CANDIDATE, MAYBE)
    if pending:
        findings.append((INFO, t("{n|# candidate is|# candidates are} not screened yet "
                                 "(`priorwork list {name} --status candidate maybe`)", n=len(pending), name=survey.name)))
    if not included:
        findings.append((INFO, t("No paper is included yet")))

    # 7. 深さ（full は網羅性を求める。quick は要旨のみ・スナウボール省略でよいので何も言わない）
    if survey.depth == "full" and included:
        if not any(q["kind"] == "snowball" for q in survey.data["searches"]):
            findings.append((WARN, t("The depth is full, but the citations have not been chased (`priorwork snowball {name}`). "
                                     "If quick is enough, change it with `priorwork scope {name} --depth quick`",
                                     name=survey.name)))
        # full では採用論文すべての本文を読む。要旨のみでよいのは、本文が取れなかった論文だけ
        abstract = evidence_label(EVIDENCE_ABSTRACT, survey.lang)
        fetched = [e for e in abstract_only if e.get("fulltext")]
        failed = [e for e in abstract_only if not e.get("fulltext") and e.get("fulltext_failed")]
        untried = [e for e in abstract_only if not e.get("fulltext") and not e.get("fulltext_failed")]
        if untried:
            findings.append((WARN, t("The depth is full, but {n|# card is|# cards are} \"{abstract}\" without trying the "
                                     "full text (`priorwork fulltext {name} N`): {numbers}", n=len(untried),
                                     abstract=abstract, name=survey.name, numbers=_numbers(untried))))
        if fetched:
            findings.append((WARN, t("The full text was fetched, but {n|# card is|# cards are} still \"{abstract}\" "
                                     "(fill them in from the full text): {numbers}", n=len(fetched), abstract=abstract,
                                     numbers=_numbers(fetched))))
        if failed:
            findings.append((INFO, t("No full text could be found for {numbers}, so {n|its card is|their cards are} "
                                     "\"{abstract}\". Attach the PDF in Zotero (or give it with `--pdf`) to read it",
                                     n=len(failed), abstract=abstract, numbers=_numbers(failed))))

    # 8. 原稿の下書きで引用する論文は、深さによらず本文で確かめる
    if survey.manuscript:
        from .export import cited_papers, draft_section   # export が check を読むので、ここで読む
        try:
            cited = cited_papers(survey, draft_section(md))
        except RuntimeError:
            cited = []
        shallow = [e for e in cited if evidence_key(parse_card_fields(cards.get(e["key"], "")).get("evidence", ""))
                   != EVIDENCE_FULLTEXT]
        if shallow:
            findings.append((WARN, t("The draft of the manuscript cites {n|# paper|# papers} not checked against the "
                                     "full text: {numbers}", n=len(shallow), numbers=_numbers(shallow))))
    return findings


def _numbers(entries: List[dict], limit: int = 10) -> str:
    return ", ".join(f"#{e['number']}" for e in entries[:limit]) + (" …" if len(entries) > limit else "")


def re_blocks_removed(md: str) -> str:
    """管理ブロック・front matter・HTML コメントを除いた、人が書いた文章だけを返す。"""
    text = strip_blocks(md)
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)
