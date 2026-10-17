"""原稿をテキストにする（`priorwork read`）。

原稿の形式を問わずにエージェントが読めるようにする: Markdown・Quarto（.qmd）・LaTeX・テキストはそのまま、
HTML（Quarto が書き出したものなど）はタグとスクリプトを除き、Word（.docx）は段落と表のテキストを、
PDF はページごとのテキストを取り出す。フォルダなら、中のファイルを順に（表・図のファイル名も）並べる。

原稿が Octavo のプロジェクトの中にあれば、原稿のほかに、プロジェクトの分析の結果（results/*.json）・
表（tables/）・分析（analysis/*.qmd）・図の名前と、原稿が引いている文献（.bib の [@key]）も並べる。
組んだ出力（build/）や元データ（data/）は読まない。
"""
from __future__ import annotations

import html
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import octavo
from .i18n import t

TEXT_SUFFIXES = {".md", ".qmd", ".rmd", ".markdown", ".txt", ".tex", ".bib", ".csv", ".tsv", ".typ", ".rst", ".org"}
HTML_SUFFIXES = {".html", ".htm", ".xhtml"}
SKIP_DIRS = {".git", ".quarto", "_freeze", "node_modules", "__pycache__", ".venv", "renv", "site_libs"}
# Octavo のプロジェクトの根から読むときに飛ばすフォルダ（組んだ出力・元データ・外から来た資料）
OCTAVO_SKIP_DIRS = {"build", "data", "refs", "out", "cache"}
MAX_BYTES = 2_000_000   # これより大きいファイルは読まない（データの CSV など）
# HTML の中で、文章でない要素（Quarto の HTML は数 MB のスクリプト・埋め込み画像を持つことがある）
_SKIP_TAGS = {"script", "style", "svg", "noscript", "template", "head"}
_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table",
               "blockquote", "pre", "figcaption", "caption", "dt", "dd", "header", "footer", "aside"}
_TAG_HEADING = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "h5": "##### ", "h6": "###### "}


class ManuscriptError(Exception):
    pass


class _HtmlText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: List[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self.skip += 1
        elif not self.skip:
            if tag in _BLOCK_TAGS:
                self.out.append("\n")
            if tag in _TAG_HEADING:
                self.out.append(_TAG_HEADING[tag])
            elif tag == "li":
                self.out.append("- ")
            elif tag in ("td", "th"):
                self.out.append(" | ")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif not self.skip and tag in _BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_text(source: str) -> str:
    parser = _HtmlText()
    parser.feed(source)
    parser.close()
    return _tidy("".join(parser.out))


def docx_text(path: Path) -> str:
    """Word の本文（段落と表）。見出しのスタイルは # にする。脚注・コメントは読まない。"""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8")
    except (zipfile.BadZipFile, KeyError) as e:
        raise ManuscriptError(t("Not a Word (.docx) file: {path} ({error})", path=path, error=e)) from e
    lines = []
    for para in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        text = "".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", para))
        text = html.unescape(text)
        heading = re.search(r'<w:pStyle w:val="(?:Heading|heading|見出し)\s*(\d)"', para)
        if heading and text.strip():
            text = "#" * int(heading.group(1)) + " " + text
        lines.append(text)
    return _tidy("\n".join(lines))


def pdf_text(path: Path) -> str:
    from .fulltext import extract_text
    text, _ = extract_text(path.read_bytes())
    return text


def file_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if path.stat().st_size > MAX_BYTES and suffix != ".pdf":
        return t("(too large to read: {size} MB)", size=round(path.stat().st_size / 1e6, 1)) + "\n"
    if suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix in HTML_SUFFIXES:
        return html_text(path.read_text(encoding="utf-8", errors="replace"))
    if suffix == ".docx":
        return docx_text(path)
    if suffix == ".pdf":
        return pdf_text(path)
    raise ManuscriptError(t("Cannot read this kind of file as text: {path}", path=path))


def readable(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES | HTML_SUFFIXES | {".docx", ".pdf"}


def _walk(path: Path, skip: frozenset = frozenset()) -> List[Path]:
    if path.is_file():
        return [path]
    out = []
    for f in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = f.relative_to(path)
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts) or (rel.parts[0] in skip):
            continue
        out.append(f)
    return out


def read(path: Path) -> List[Tuple[Path, str]]:
    """原稿（ファイルかフォルダ）を、(ファイル, テキスト) の並びにする。読めないファイル（画像など）は
    テキストを空にして並べる（表・図があることはエージェントに伝える）。"""
    if not path.exists():
        raise ManuscriptError(t("The manuscript is not found: {path}", path=path))
    root = octavo.find_project(path)
    if root is None:
        return [(f, file_text(f) if readable(f) else "") for f in _walk(path) if f.suffix.lower() != ".bib"]
    skip = frozenset(OCTAVO_SKIP_DIRS)
    files = _walk(path, skip if path.resolve() == root else frozenset())
    if path.resolve() != root:
        # 原稿の外にある、分析の結果・表・分析・図（Octavo の決まった置き場）
        for sub, pattern in (("results", "*.json"), ("tables", "*.md"), ("analysis", "*.qmd"), ("figures", "*.png")):
            files += sorted((root / sub).glob(pattern)) if (root / sub).is_dir() else []
    seen, got = set(), []
    for f in files:
        if f.resolve() in seen or f.suffix.lower() == ".bib":
            continue
        seen.add(f.resolve())
        figure = f.resolve().is_relative_to((root / "figures").resolve())   # 図は名前だけ
        got.append((f, file_text(f) if readable(f) and not figure else ""))
    return got


def cited_entries(path: Path) -> Tuple[Optional[Path], List[Dict[str, Any]]]:
    """原稿が引いている文献（.bib のエントリー）。Octavo のプロジェクトなら設定の bib_file、
    そうでなければ原稿のフォルダの .bib。原稿が Markdown でなく [@key] が読めなければ、.bib のすべて。"""
    root = octavo.find_project(path)
    if root is not None:
        bib = Path(octavo.project_info(root)["bib"])
    else:
        folder = path if path.is_dir() else path.parent
        bibs = sorted(folder.rglob("*.bib"))
        bib = bibs[0] if bibs else None
    if bib is None or not bib.is_file():
        return None, []
    entries = octavo.read_bib(bib)
    by_key = {e["key"]: e for e in entries}
    text = "\n".join(file_text(f) for f in _walk(path) if f.suffix.lower() in {".md", ".qmd", ".rmd", ".markdown", ".tex"})
    keys = octavo.cited_keys(text, set(by_key)) if text else []
    return bib, [by_key[k] for k in keys] if text else entries


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
