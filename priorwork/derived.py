"""
サーベイから派生する短い文章（講義資料・読書メモ・要点の整理など。`priorwork derive`）。

置き場所は `reports/<サーベイ名>.<名前>.md`（サーベイのほかのファイルと並ぶので、
`git add reports/<サーベイ名>.*` で一緒に入る）。冒頭の管理ブロック（用途・字数の目安・数え方）と
末尾の参考文献は `./priorwork` が書き直し、その間の文章をエージェントが書く。

`priorwork check` が見ること:
- 本文の著者年引用が、採用論文に対応しているか（未登録は ERROR、採用でなければ WARN）
- 引用した論文のカードが本文確認済か（そうでなければ WARN。派生文書は本文確認済のカードから引く）
- 引用した文に書いた数値が、その論文のカードにあるか（無ければ WARN。数値は写し間違えやすい）
- 字数が目安から大きく外れていないか（INFO）
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .i18n import t, tl
from .survey import (
    EVIDENCE_FULLTEXT, INCLUDED, Survey, SurveyError, evidence_key, extract_blocks, first_surname, now_iso,
    parse_card_fields, parse_cards, render_references, replace_blocks, strip_blocks, year_labels,
)

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
# サーベイのほかの書き出しと同じ名前は使わない（reports/<サーベイ>.<名前>.md が重なる）
RESERVED = {"draft", "octavo", "html", "docx", "md", "bak"}
HEAD, REFS = "derived", "derived_references"
TOLERANCE = 0.15          # 字数の目安からのずれ（15% を超えたら知らせる）


def path_of(survey: Survey, name: str) -> Path:
    return survey.md_path.with_name(f"{survey.name}.{name}.md")


def entries(survey: Survey) -> Dict[str, Dict[str, Any]]:
    """このサーベイの派生文書（名前 → 用途・字数など）。前からの状態ファイルには無い。"""
    return survey.data.get("derived") or {}


def _head(survey: Survey, spec: Dict[str, Any]) -> str:
    lang = survey.lang
    lines = [f"> **{tl(lang, 'Purpose')}**: {spec.get('purpose') or '—'}"]
    if spec.get("length"):
        rule = tl(lang, "citations in parentheses counted") if spec.get("count_citations") else \
            tl(lang, "citations in parentheses not counted")
        unit = tl(lang, "characters") if lang == "ja" else tl(lang, "words")
        paren = "（{}）" if lang == "ja" else "({})"
        lines.append(f"> **{tl(lang, 'Length')}**: {tl(lang, 'about')} {spec['length']:,} {unit} " + paren.format(rule))
    if spec.get("structure"):
        lines.append(f"> **{tl(lang, 'Structure')}**: {spec['structure']}")
    lines.append(f"> **{tl(lang, 'From the survey')}**: {survey.name} — "
                 + tl(lang, "cite only included papers, from cards checked against the full text; check each "
                           "number and the direction of each finding against the card"))
    return "\n>\n".join(lines)          # 1 行ずつ（続けて書くと Markdown では 1 段落になる）


def _references(survey: Survey, body: str) -> str:
    from .export import cited_papers
    included = survey.by_status(INCLUDED)
    cited = cited_papers(survey, body)
    lang = survey.lang
    return f"## {tl(lang, 'References')}\n\n" + render_references(cited, year_labels(included), lang)


def create(survey: Survey, name: str, purpose: str, length: Optional[int] = None,
           count_citations: bool = False, structure: str = "") -> Path:
    if not NAME_RE.match(name) or name in RESERVED:
        raise SurveyError(t("The name of a derived document is lower-case letters, digits, - and _ "
                            "(not {reserved}): {name}", reserved=", ".join(sorted(RESERVED)), name=name))
    out = path_of(survey, name)
    spec = {"purpose": purpose, "length": length, "count_citations": count_citations, "structure": structure,
            "created": now_iso()}
    known = survey.data.setdefault("derived", {})
    if out.exists() or name in known:
        # 既にあれば、用途などの記録だけを直す（書いた文章はそのまま）
        known[name] = {**known.get(name, {}), **{k: v for k, v in spec.items() if v not in (None, "")},
                       "count_citations": count_citations}
        survey.save()
        render_one(survey, name)
        return out
    known[name] = spec
    survey.save()
    lang = survey.lang
    sections = [s.strip() for s in re.split(r"\s*[;/／；]\s*", structure) if s.strip()] if structure else []
    body = "\n\n".join(f"## {s}" for s in sections) or f"<!-- {tl(lang, 'Write the text here')} -->"
    text = (f"# {survey.data['topic']} — {purpose}\n\n"
            f"<!-- BEGIN priorwork:{HEAD} -->\n{_head(survey, known[name])}\n<!-- END priorwork:{HEAD} -->\n\n"
            f"{body}\n\n"
            f"<!-- BEGIN priorwork:{REFS} -->\n{_references(survey, '')}\n<!-- END priorwork:{REFS} -->\n")
    out.write_text(text, encoding="utf-8")
    return out


def render_one(survey: Survey, name: str) -> bool:
    """管理ブロック（冒頭の用途と、末尾の参考文献）を書き直す。変わったら True。"""
    p = path_of(survey, name)
    spec = entries(survey).get(name)
    if spec is None or not p.exists():
        return False
    md = p.read_text(encoding="utf-8")
    body = strip_blocks(md)
    new = replace_blocks(md, {HEAD: _head(survey, spec), REFS: _references(survey, body)})
    if new != md:
        p.write_text(new, encoding="utf-8")
        return True
    return False


def render_all(survey: Survey) -> None:
    for name in entries(survey):
        render_one(survey, name)


# ---------------- 字数 ----------------

_FULL_PAREN = re.compile(r"[（(]([^（）()]*)[）)]")


def measure(md: str, lang: str, count_citations: bool) -> int:
    """書いた文章の分量。日本語は空白を除いた文字数、英語は語数。見出しの印・箇条書きの印・強調の * は数えない。
    count_citations が False なら、引用の括弧（「(Smith 2020)」「（山田 2020）」、叙述の「(2020)」）を除いて数える。"""
    from .check import find_citations
    text = re.sub(r"<!--.*?-->", "", strip_blocks(md), flags=re.S)
    lines = []
    for line in text.splitlines():
        if line.startswith("#"):
            continue                     # 見出しは数えない（題も節の名前も）
        lines.append(re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", line))
    text = re.sub(r"[*_`>]", "", "\n".join(lines))
    if not count_citations:
        def drop(m: "re.Match") -> str:
            inner = m.group(1)
            return "" if (find_citations("X " + m.group(0)) or re.fullmatch(r"\s*\d{4}[a-z]?(\s*[,;]\s*\d{4}[a-z]?)*\s*", inner)) else m.group(0)
        text = _FULL_PAREN.sub(drop, text)
    if lang == "ja":
        return len(re.sub(r"\s+", "", text))
    return len(re.findall(r"\S*\w\S*", text))


# ---------------- 検査 ----------------

_SENTENCE = re.compile(r"[^。！？.!?\n]+[。！？.!?]?")


def check(survey: Survey) -> List[Tuple[str, str]]:
    from .check import ERROR, INFO, WARN, _card_numbers, _numbers, _plain_number, find_citations, ignored_citations
    from .export import cited_papers
    findings: List[Tuple[str, str]] = []
    md_survey = survey.md_path.read_text(encoding="utf-8")
    cards = parse_cards(extract_blocks(md_survey).get("papers", ""))
    included = survey.by_status(INCLUDED)
    labels = year_labels(included)
    for name, spec in entries(survey).items():
        p = path_of(survey, name)
        if not p.exists():
            findings.append((WARN, t("The derived document {file} is gone (make it again with `priorwork derive`)",
                                     file=p.name)))
            continue
        md = p.read_text(encoding="utf-8")
        body = strip_blocks(md)
        cited = cited_papers(survey, body)
        ignored = ignored_citations(md)
        # 引用が採用論文に対応しているか
        for c in find_citations(body):
            if (c.name, c.year) in ignored or c.is_non_author:
                continue
            if not any(c.name == first_surname(e["record"]) and str(c.year) == labels[e["key"]][:4] for e in included):
                findings.append((ERROR, t("{file}: the citation \"{cite}\" is not an included paper of the survey",
                                          file=p.name, cite=c.text)))
        # 引用したカードは本文確認済か
        shallow = [e for e in cited if evidence_key(parse_card_fields(cards.get(e["key"], "")).get("evidence", ""))
                   != EVIDENCE_FULLTEXT]
        if shallow:
            findings.append((WARN, t("{file}: {n|# cited paper is|# cited papers are} not checked against the full "
                                     "text (cite from cards that are): {numbers}",
                                     file=p.name, n=len(shallow), numbers=_numbers(shallow))))
        # 引用した文の数値が、そのカードにあるか
        for sentence in _SENTENCE.findall(body):
            hits = cited_papers(survey, sentence)
            if not hits:
                continue
            nums = {_plain_number(n) for n in _card_numbers(sentence)}
            known = {_plain_number(n) for e in hits for n in _card_numbers(cards.get(e["key"], ""))}
            missing = sorted(n for n in nums if n not in known)
            if missing:
                findings.append((WARN, t("{file}: {numbers} in \"{sentence}\" {n|is|are} not in the card of the "
                                         "paper it cites (check it against the card's findings)", file=p.name,
                                         numbers=", ".join(missing), n=len(missing),
                                         sentence=sentence.strip()[:60])))
        # 字数
        if spec.get("length"):
            got = measure(md, survey.lang, bool(spec.get("count_citations")))
            if abs(got - spec["length"]) > spec["length"] * TOLERANCE:
                findings.append((INFO, t("{file}: {got} {unit}, against about {want} (citations in parentheses "
                                         "{rule})", file=p.name, got=f"{got:,}", want=f"{spec['length']:,}",
                                         unit=t("characters") if survey.lang == "ja" else t("words"),
                                         rule=t("counted") if spec.get("count_citations") else t("not counted"))))
        if not re.search(r"^(?!#)(?!<!--)\S", body, re.M):
            findings.append((INFO, t("{file} has no text yet", file=p.name)))
    return findings


def export_one(survey: Survey, name: str, fmt: str = "html", out: Optional[Path] = None) -> Tuple[Path, List[str]]:
    """読むための版（HTML・Word・Markdown）。冒頭の用途の欄は外し、参考文献は付けたまま。"""
    from .export import _write
    from .check import ERROR
    if name not in entries(survey):
        raise SurveyError(t("{name} has no derived document called {derived} (`priorwork derive {name}` lists them)",
                            name=survey.name, derived=name))
    render_one(survey, name)
    md = path_of(survey, name).read_text(encoding="utf-8")
    text = re.sub(rf"<!-- BEGIN priorwork:{HEAD} -->.*?<!-- END priorwork:{HEAD} -->\n*", "", md, flags=re.S)
    text = re.sub(r"<!-- (?:BEGIN|END) priorwork:\w+ -->\n?", "", text)
    issues = [msg for level, msg in check(survey) if level == ERROR and path_of(survey, name).name in msg]
    suffix = {"html": ".html", "docx": ".docx", "md": ".clean.md"}[fmt]
    out = out or path_of(survey, name).with_suffix(suffix)
    title = (re.search(r"^# (.+)$", md, re.M) or [None, survey.data["topic"]])[1]
    _write(out, text, title, fmt, survey.lang)
    return out, issues
