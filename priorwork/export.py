"""
読むためのレポートを書き出す（`priorwork export`）。

`reports/*.md` は作業用で、管理ブロックのコメントや未記入の記入欄、テンプレートの説明文を含む。
ここでは、それらを除いた「読むための版」を Markdown / HTML / Word で作る。
未記入・未確認・検査エラーが残っていれば、冒頭に「下書き」の表示を付けて、完成品と取り違えないようにする。
"""

import html
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import i18n
from .check import ERROR, check_survey
from .i18n import t, tl
from .survey import BIBLIO_LABEL, CARD_FIELDS, Survey

FORMATS = {"html": ".html", "md": ".clean.md", "docx": ".docx"}

# テンプレート（assets/<lang>/templates/literature_review.md）にある、執筆者向けの説明文。両方の言語
_HINTS = [
    re.compile(r"^3章のカードの記入内容から自動で作られます。\s*$"),
    re.compile(r"^引用キーは Zotero で管理する（ここではキーを作らない）。\s*$"),
    re.compile(r"^Built automatically from the paper cards in section 3\.\s*$"),
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
@media print { main { max-width:none; padding:0; } body { font-size:10.5pt; } h2 { break-after:avoid; } h3, tr { break-inside:avoid; } }
"""


def to_html(md: str, title: str, lang: str = "ja") -> str:
    from markdown_it import MarkdownIt
    body = MarkdownIt("commonmark", {"html": True}).enable("table").render(md)
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    return (f"<!DOCTYPE html>\n<html lang=\"{lang}\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{html.escape(title)}</title>\n<style>{_CSS}</style>\n</head>\n<body>\n<main>\n{body}</main>\n</body>\n</html>\n")


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
    return out, issues[i18n.language()]
