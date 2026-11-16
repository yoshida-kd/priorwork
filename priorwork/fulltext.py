"""
本文テキストの取得（`priorwork fulltext`）。

PDF はリポジトリに置かない。次の順で PDF を探し、抽出したテキストだけを
Git 管理外の `.priorwork/cache/fulltext/` に保存する。

1. `--pdf` で指定したファイル
2. このマシンの Zotero データフォルダ（`ZOTERO_DATA_DIR`、既定は ~/Zotero）の添付 PDF
3. Zotero Web API で見つけた添付 PDF（WebDAV / Zotero File Storage から取得）
4. Zotero が索引化した本文テキスト（ページ区切りなし）
5. オープンアクセス版の PDF（Semantic Scholar / OpenAlex が示す全所在。ランディングページなら、その中の PDF のリンク）

PDF から抽出したテキストは `=== page N ===` でページが区切られる。4 だけはページ番号が付かない。
"""

import io
import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .api import ApiError
from .i18n import t

from .workspace import CACHE_DIR, ROOT

FULLTEXT_DIR = CACHE_DIR / "fulltext"
MAX_PDF_BYTES = 50 * 1024 * 1024


class FulltextError(RuntimeError):
    pass


MAX_ATTACHMENTS = 4   # 1 本の論文で調べる Zotero の添付 PDF の数


def journal_pages(record: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    """掲載誌のページ範囲（"330-345" → (330, 345)。"F107-F130" も）。最後のページが無い・最初より前なら (最初, None)。"""
    m = re.match(r"^\s*[A-Za-z]?(\d+)\s*(?:[-–]+\s*[A-Za-z]?(\d+))?", record.get("pages") or "")
    if not m:
        return None, None
    first, last = int(m.group(1)), int(m.group(2)) if m.group(2) else None
    return first, last if last is not None and last > first else None


def incomplete_fulltext(entry: Dict[str, Any]) -> Optional[int]:
    """取得した本文の PDF のページ数が掲載誌のページ数の半分に満たない（出版社のプレビューなど）とき、
    掲載誌のページ数を返す。"""
    info = entry.get("fulltext") or {}
    first, last = journal_pages(entry["record"])
    if not info.get("page_markers") or not info.get("pages") or last is None:
        return None
    expected = last - first + 1
    return expected if info["pages"] * 2 < expected else None


def zotero_data_dir() -> Path:
    return Path(os.environ.get("ZOTERO_DATA_DIR") or Path.home() / "Zotero").expanduser()


def find_zotero_pdf(doi: str, data_dir: Optional[Path] = None) -> Optional[Path]:
    """Zotero の zotero.sqlite を読み取り専用で開き、DOI が一致する論文の添付 PDF を返す。"""
    data_dir = data_dir or zotero_data_dir()
    db = data_dir / "zotero.sqlite"
    if not doi or not db.exists():
        return None
    # immutable=1: Zotero 起動中（DB ロック中）でも読める。書き込みは一切しない
    conn = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT att.key, ia.path
            FROM itemData d
            JOIN fields f ON f.fieldID = d.fieldID AND f.fieldName = 'DOI'
            JOIN itemDataValues v ON v.valueID = d.valueID
            JOIN itemAttachments ia ON ia.parentItemID = d.itemID AND ia.contentType = 'application/pdf'
            JOIN items att ON att.itemID = ia.itemID
            WHERE lower(trim(v.value)) = lower(?)
            """,
            (doi.strip(),),
        ).fetchall()
    finally:
        conn.close()
    found = []
    for key, path in rows:
        if not path:
            continue
        if path.startswith("storage:"):
            candidate = data_dir / "storage" / key / path[len("storage:"):]
        else:
            candidate = Path(path)  # リンクされたファイル（絶対パス）
        if candidate.exists():
            found.append(candidate)
    if len(found) < 2:
        return found[0] if found else None
    # 同じ論文に PDF がいくつもあれば、ワーキングペーパー版でないものを選ぶ
    return found[best_pdf([p.read_bytes() for p in found])]


# 表紙の上のほうだけを見る（掲載版の 1 ページ目の脚注にも "NBER" や "working paper" は出てくる）
_WP_RE = re.compile(r"\b(?:working\s+paper|discussion\s+paper|preprint|mimeo|author\s+manuscript|"
                    r"accepted\s+manuscript|draft\s+version|this\s+draft)\b", re.IGNORECASE)


def working_paper_text(text: str) -> bool:
    """本文の 1 ページ目（表紙）が、ワーキングペーパー・原稿の版らしいか。"""
    first = re.split(r"(?m)^=== page 2 ===", text or "", maxsplit=1)[0]
    return bool(_WP_RE.search(first[:800]))


def best_pdf(pdfs: List[bytes]) -> int:
    """同じ論文の PDF のうち、読むものの番号: ワーキングペーパー版でなく、読める文字の多いもの。"""
    def score(pdf: bytes) -> Tuple[bool, int]:
        try:
            text, _ = extract_text(pdf, "pypdf")   # 版を見分けるだけ（Docling は重い）
        except Exception:   # 壊れた PDF は選ばない
            return (False, -1)
        return (not working_paper_text(text), len(text))
    scores = [score(p) for p in pdfs]
    return scores.index(max(scores))


_PDF_META_RE = re.compile(r"<meta[^>]+name=[\"']citation_pdf_url[\"'][^>]*>", re.IGNORECASE)
_CONTENT_RE = re.compile(r"content=[\"']([^\"']+)[\"']", re.IGNORECASE)


def download_pdf(url: str, follow_landing: bool = True) -> bytes:
    """PDF を取得する。ランディングページ（HTML）が返ったら、その `citation_pdf_url`（機関リポジトリ・出版社の
    多くが載せる PDF のリンク）を一度だけたどる。"""
    resp = requests.get(url, headers={"User-Agent": "priorwork/0.1"}, timeout=60, stream=True,
                        allow_redirects=True)
    if not resp.ok:
        raise FulltextError(t("Could not download the PDF (HTTP {status}): {url}", status=resp.status_code, url=url))
    chunks, size = [], 0
    for chunk in resp.iter_content(1 << 16):
        size += len(chunk)
        if size > MAX_PDF_BYTES:
            raise FulltextError(t("The PDF is too large (>{mb} MB): {url}", mb=MAX_PDF_BYTES // 1024 // 1024, url=url))
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data.startswith(b"%PDF"):
        pdf_url = landing_pdf_url(data.decode("utf-8", "replace"), resp.url or url) if follow_landing else None
        if pdf_url and pdf_url != url:
            return download_pdf(pdf_url, follow_landing=False)
        raise FulltextError(t("Not a PDF (probably the publisher's landing page): {url}", url=url))
    return data


def landing_pdf_url(html: str, base: str) -> Optional[str]:
    """ランディングページの `<meta name="citation_pdf_url" content="…">`。"""
    from urllib.parse import urljoin
    for tag in _PDF_META_RE.findall(html):
        m = _CONTENT_RE.search(tag)
        if m:
            return urljoin(base, m.group(1).replace("&amp;", "&"))
    return None


# PDF から文字を取り出す道具。auto: Docling（任意の依存。手元で動くレイアウト・表の認識モデル）が入っていれば
# それで表と見出しのある Markdown に、無ければ pypdf で文字だけに。PRIORWORK_PDF_ENGINE=pypdf / docling で固定できる
PDF_ENGINES = ("auto", "docling", "pypdf")
_docling_converter: Any = None
last_engine = ""   # 直前の extract_text が実際に使った道具（Docling が失敗すれば pypdf）


def docling_available() -> bool:
    try:
        import docling.document_converter  # noqa: F401
    except Exception:   # 入っていない・壊れている（torch が読めないなど）
        return False
    return True


def pdf_engine() -> str:
    """これから使う道具（docling / pypdf）。"""
    chosen = (os.environ.get("PRIORWORK_PDF_ENGINE") or "auto").strip().lower()
    if chosen not in PDF_ENGINES:
        chosen = "auto"
    if chosen == "pypdf":
        return "pypdf"
    if docling_available():
        return "docling"
    if chosen == "docling":
        raise FulltextError(t("PRIORWORK_PDF_ENGINE=docling, but Docling is not installed "
                              "(`pip install \"priorwork[docling]\"`)"))
    return "pypdf"


def extract_text(pdf: bytes, engine: Optional[str] = None) -> Tuple[str, int]:
    """(ページを `=== page N ===` で区切ったテキスト, ページ数)。"""
    global last_engine
    engine = engine or pdf_engine()
    if engine == "docling":
        try:
            last_engine = "docling"
            return _extract_docling(pdf)
        except Exception as e:   # モデルの読み込み・変換の失敗。pypdf で続ける
            logging.getLogger(__name__).debug("docling failed", exc_info=True)
            print("[Notice] " + t("Docling could not read the PDF ({error}); using pypdf", error=str(e)[:200]),
                  file=__import__("sys").stderr)
    last_engine = "pypdf"
    return _extract_pypdf(pdf)


def _extract_pypdf(pdf: bytes) -> Tuple[str, int]:
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)  # フォント関連の冗長な警告を抑える
    reader = PdfReader(io.BytesIO(pdf))
    pages = []
    for i, page in enumerate(reader.pages, 1):
        pages.append(f"\n\n=== page {i} ===\n\n" + (page.extract_text() or ""))
    return "".join(pages).strip(), len(reader.pages)


def _extract_docling(pdf: bytes) -> Tuple[str, int]:
    """Docling で、ページごとの Markdown（見出し・表。ページのヘッダー・フッターは除かれる）にする。
    ページの印は pypdf と同じ形にする（カードのページと check の照合が使う）。"""
    global _docling_converter
    from docling.datamodel.base_models import DocumentStream
    from docling.document_converter import DocumentConverter

    if _docling_converter is None:      # モデルの読み込みは重いので、1 回だけ
        _docling_converter = DocumentConverter()
    doc = _docling_converter.convert(DocumentStream(name="paper.pdf", stream=io.BytesIO(pdf))).document
    n = doc.num_pages()
    pages = [f"\n\n=== page {i} ===\n\n" + compact_markdown(doc.export_to_markdown(page_no=i)) for i in range(1, n + 1)]
    return "".join(pages).strip(), n


def compact_markdown(md: str) -> str:
    """Docling の Markdown を短くする: 表の列をそろえる空白と罫線を詰め、画像の印を除く（読む量を pypdf と同じくらいに）。"""
    out = []
    for ln in md.splitlines():
        if ln.strip() == "<!-- image -->":
            continue
        if ln.lstrip().startswith("|"):
            ln = re.sub(r"-{3,}", "---", re.sub(r" {2,}", " ", ln))
        out.append(ln)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


# ---- 参照文献の節を分ける（エージェントが読む量を減らす。参照文献は別のファイルに残す）----

_REFS_HEAD = re.compile(r"^[ \t]*(?:#{1,6}[ \t]*)?(?:[0-9IVX]+\.?[ \t]+)?\**(?:References|REFERENCES|Reference List|"
                        r"Bibliography|BIBLIOGRAPHY|Literature Cited|LITERATURE CITED|Works Cited|WORKS CITED|"
                        r"参考文献|引用文献)\**[ \t]*:?[ \t]*$", re.M)
# 参照文献の後ろの付録（表を含むことがある）は残す
_AFTER_REFS = re.compile(r"^[ \t]*(?:#{1,6}[ \t]*)?\**(?:Online[ \t]+)?(?:Appendix|APPENDIX|Appendices|APPENDICES|"
                         r"Supplementary|SUPPLEMENTARY|Supporting Information|付録)\b.{0,100}$", re.M)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}[a-z]?\b")
_MARKER_RE = re.compile(r"\n*=== page \d+ ===\n*")


def split_references(text: str) -> Tuple[str, str]:
    """(本文, 参照文献の節)。本文の後半にある参照文献の見出しから、付録の見出し（無ければ終わり）まで。
    ページの印は本文に残す（ページの数え方を変えない）。見つからなければ (text, "")。"""
    heads = [m for m in _REFS_HEAD.finditer(text) if m.start() >= len(text) * 0.4]
    if not heads:
        return text, ""
    start = heads[0].start()
    after = _AFTER_REFS.search(text, heads[0].end())
    end = after.start() if after else len(text)
    refs = text[start:end]
    if len(refs) < 500 or len(_YEAR_RE.findall(refs)) < 5:
        return text, ""
    markers = "".join(m.group(0) for m in _MARKER_RE.finditer(refs))
    return text[:start] + REFS_NOTE + markers + text[end:], _MARKER_RE.sub("\n", refs).strip() + "\n"


REFS_NOTE = "[References: moved to a separate file (`priorwork fulltext SURVEY N --references`)]\n"


def save_text(text: str, out: Path) -> Dict[str, Any]:
    """本文を保存する。参照文献の節は `<名前>.refs.txt` に分ける。保存したものの情報を返す。"""
    body, refs = split_references(text)
    out.write_text(body, encoding="utf-8")
    refs_path = out.with_name(out.stem + ".refs.txt")
    if refs:
        refs_path.write_text(refs, encoding="utf-8")
    elif refs_path.exists():
        refs_path.unlink()
    return {"chars": len(body), "references_chars": len(refs)}


def references_path(text_path: Path) -> Path:
    return text_path.with_name(text_path.stem + ".refs.txt")


# ---- 保存した本文を部分ごとに読む（全文を読まずに済ませる）----

_HEADING_WORDS = ("Introduction", "Background", "Literature", "Theory", "Theoretical", "Hypothes", "Data", "Method",
                  "Methodology", "Research Design", "Empirical", "Identification", "Estimation", "Model", "Results",
                  "Findings", "Analysis", "Robustness", "Discussion", "Conclusion", "Concluding", "Limitations",
                  "Appendix", "Abstract", "Policy", "Implications")
_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s+\S.{0,120}"                                         # Markdown（Docling）
    r"|(?:\d+(?:\.\d+){0,3}\.?|[IVX]{1,5}\.)\s+[A-Z][^.!?]{2,90}"        # 1. / 2.1 / III. の付いた見出し
    r"|(?:" + "|".join(_HEADING_WORDS) + r")[A-Za-z]*(?:\s+[A-Za-z&,:-]+){0,6}"
    r"|[A-Z][A-Z0-9 ,:&\-]{4,70})$")
_CAPTION_RE = re.compile(r"^(?:\*\*)?(?:Table|TABLE|Figure|FIGURE|Fig\.)\s+[A-Z]?\d+[A-Za-z]?\b(?![,;])")


def pages_of(text: str) -> List[Tuple[int, str]]:
    """[(ページ, そのページの文字)]。ページの印が無ければ [(0, 全体)]。"""
    parts = re.split(r"=== page (\d+) ===", text)
    if len(parts) == 1:
        return [(0, text)]
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def outline(text: str) -> List[Dict[str, Any]]:
    """見出しと表・図の見出し（どのページか）。どのページにもある行（柱）は除く。"""
    pages = pages_of(text)
    folded = lambda x: re.sub(r"\d+", "#", re.sub(r"\s+", "", x))   # noqa: E731  柱のページ番号は毎ページ違う
    counts: Dict[str, int] = {}
    for _, body in pages:
        for ln in {folded(x) for x in body.splitlines() if x.strip()}:
            counts[ln] = counts.get(ln, 0) + 1
    out: List[Dict[str, Any]] = []
    seen_captions = set()
    for page, body in pages:
        for raw in body.splitlines():
            ln = raw.strip()
            if not ln or len(ln) > 130 or (len(pages) >= 4 and counts.get(folded(ln), 0) >= max(2, len(pages) // 4)):
                continue
            cap = _CAPTION_RE.match(ln)
            if cap:
                label = re.sub(r"[*\s]+", " ", cap.group(0)).strip().lower()
                if label not in seen_captions:
                    seen_captions.add(label)
                    out.append({"page": page, "kind": "caption", "text": ln.strip("*# ")[:110]})
            elif (_HEADING_RE.match(ln) and (ln.startswith("#") or len(ln) <= 60)
                  and not re.search(r"\d{3,}|\(\d{4}\)|https?:|@|[,;]$", ln)):   # 脚注・住所・文の途中を除く
                out.append({"page": page, "kind": "heading", "text": ln.strip("*# ")[:110]})
    return out


def parse_page_range(spec: str) -> List[int]:
    pages: List[int] = []
    for part in spec.replace(" ", "").split(","):
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            raise FulltextError(t("Give pages like 5, 5-9 or 3,7-8: {spec}", spec=spec))
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        pages += range(min(a, b), max(a, b) + 1)
    return pages


def read_pages(text: str, spec: str) -> str:
    wanted = set(parse_page_range(spec))
    return "".join(f"=== page {p} ===\n{body.strip()}\n\n" for p, body in pages_of(text) if p in wanted)


def grep(text: str, pattern: str, context: int = 1, limit: int = 40) -> List[Dict[str, Any]]:
    """語（正規表現。大文字小文字を区別しない）の出てくる行と、その前後の行（どのページか）。"""
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error:
        rx = re.compile(re.escape(pattern), re.IGNORECASE)
    hits: List[Dict[str, Any]] = []
    for page, body in pages_of(text):
        lines = body.splitlines()
        for i, ln in enumerate(lines):
            if rx.search(ln):
                lo, hi = max(0, i - context), min(len(lines), i + context + 1)
                hits.append({"page": page, "text": "\n".join(x for x in lines[lo:hi] if x.strip())})
                if len(hits) >= limit:
                    return hits
    return hits


# 本文のある1ページの文字数はふつう 2,000 字を超える。繰り返しの行を除いてこれに満たないなら、
# 文字を持たない（スキャンした画像の）PDF とみなす
MIN_CHARS_PER_PAGE = 300


def content_chars(text: str) -> Tuple[int, int]:
    """(ページ数, 本文の文字数)。どのページにも出る行（「Downloaded from …」などの透かし・
    ヘッダー）は数えない。スキャンした PDF は、その1行しか文字を持たないことがある。"""
    pages = [p for p in re.split(r"\n*=== page \d+ ===\n*", text) if p is not None]
    pages = [p for p in pages if p.strip()] or [text]
    lines = [{ln.strip() for ln in p.split("\n") if ln.strip()} for p in pages]
    counts: Dict[str, int] = {}
    for ls in lines:
        for ln in ls:
            counts[ln] = counts.get(ln, 0) + 1
    repeated = {ln for ln, n in counts.items() if len(pages) >= 2 and n * 2 >= len(pages) and len(ln) <= 150}
    chars = sum(len(re.sub(r"\s+", "", ln)) for ls in lines for ln in ls
                if ln not in repeated and not re.match(r"(?i)downloaded from\b", ln))
    return len(pages), chars


def oa_pdf_urls(record: Dict[str, Any], client: Any) -> List[Tuple[str, str]]:
    """試す (URL, 版) の順: 記録した OA の PDF → OpenAlex の全所在の PDF（OA のものから）→ OA の所在のランディングページ
    （機関リポジトリなど。`download_pdf` がページ内の PDF のリンクをたどる）。版は OpenAlex の version
    （publishedVersion / acceptedVersion / submittedVersion。分からなければ空）。"""
    urls: List[Tuple[str, str]] = [(record["oa_pdf"], "")] if record.get("oa_pdf") else []
    landing: List[Tuple[str, str]] = []
    if record.get("doi"):
        for w in client.openalex_works(dois=[record["doi"]],
                                       select="doi,open_access,best_oa_location,primary_location,locations"):
            locations = [w.get("best_oa_location") or {}, w.get("primary_location") or {}, *(w.get("locations") or [])]
            locations.sort(key=lambda loc: not loc.get("is_oa"))      # OA の所在を先に（sort は安定）
            for loc in locations:
                if loc.get("pdf_url"):
                    urls.append((loc["pdf_url"], loc.get("version") or ""))
            if (w.get("open_access") or {}).get("oa_url"):
                urls.append((w["open_access"]["oa_url"], ""))
            landing += [(loc["landing_page_url"], loc.get("version") or "") for loc in locations
                        if loc.get("is_oa") and loc.get("landing_page_url")]
    # 同じ URL は、版の分かっているものを残して 1 つにする
    best: Dict[str, str] = {}
    for url, version in urls + landing:
        best[url] = best.get(url) or version
    return list(best.items())


def fetch_fulltext(entry: Dict[str, Any], client: Any, pdf_path: Optional[str] = None,
                   out_dir: Optional[Path] = None, zotero: Any = None) -> Dict[str, Any]:
    from .zotero import ZoteroError

    out_dir = out_dir or FULLTEXT_DIR
    record = entry["record"]
    attempts = []
    pdf, source, text, n_pages, version = None, "", None, None, ""

    if pdf_path:
        path = Path(pdf_path).expanduser()
        if not path.exists():
            raise FulltextError(t("No such file: {path}", path=path))
        pdf, source = path.read_bytes(), f"file:{path}"
    if pdf is None:
        zpath = find_zotero_pdf(record.get("doi", ""))
        if zpath:
            pdf, source = zpath.read_bytes(), f"zotero:{zpath}"
        elif (zotero_data_dir() / "zotero.sqlite").exists():
            attempts.append(t("No PDF in the local Zotero ({path})", path=zotero_data_dir()))

    if pdf is None and zotero is not None:
        try:
            item = zotero.find_item(record)
            attachments = zotero.pdf_attachments(item["key"], refresh=True) if item else []
            if not item:
                attempts.append(t("Not in the Zotero library (matched by DOI and title)"))
            elif not attachments:
                attempts.append(t("In Zotero, but no PDF is attached"))
            if not item or not attachments:
                attempts.append(zotero.sync_note())
            got = []
            for att in attachments[:MAX_ATTACHMENTS]:
                try:
                    got.append((zotero.download_pdf(att), f"zotero:{att['key']} ({att['filename']})"))
                except ZoteroError as e:
                    attempts.append(str(e))
            if got:   # いくつもあれば、ワーキングペーパー版でないものを読む
                pdf, source = got[best_pdf([g[0] for g in got]) if len(got) > 1 else 0]
            if pdf is None:
                for att in attachments:
                    ft = zotero.indexed_fulltext(att["key"])
                    if ft and len(ft.get("content") or "") >= 500:
                        text, source = ft["content"], f"zotero-index:{att['key']} (no page breaks)"
                        n_pages = ft.get("totalPages")
                        break
                else:
                    if attachments:
                        attempts.append(t("Zotero has no indexed full text"))
        except ZoteroError as e:
            attempts.append(str(e))

    if pdf is None and text is None:
        urls = oa_pdf_urls(record, client)
        if not urls:
            attempts.append(t("No open-access PDF"))
        for url, url_version in urls:
            try:
                pdf, source, version = download_pdf(url), f"oa:{url}", url_version
                break
            except (FulltextError, requests.RequestException) as e:
                attempts.append(str(e))
    if pdf is None and text is None and record.get("pmcid"):
        # PDF が取れなければ PMC の本文（XML）。ページ区切りは無いが、OA の臨床研究の多くはここで読める
        try:
            body = client.pmc_fulltext(record["pmcid"])
        except ApiError as e:
            attempts.append(str(e))
        else:
            if len(body) >= 500:
                text, source = body, f"europepmc:{record['pmcid']} (no page breaks)"
            else:
                attempts.append(t("PMC has no open full text ({id})", id=record["pmcid"]))
    if pdf is None and text is None:
        raise FulltextError(t("No full-text PDF was found:") + "\n  - " + "\n  - ".join(attempts) +
                            "\n  → " + t("Attach the PDF in Zotero, or give it with `--pdf <path>`"))

    engine = pdf_engine() if pdf is not None else ""
    if pdf is not None:
        text, n_pages = extract_text(pdf, engine)
    if len(text) < 500:
        raise FulltextError(t("Could not extract text from the PDF (probably a scanned image): {source}", source=source))
    if pdf is not None:
        pages, chars = content_chars(text)
        if pages >= 2 and chars < MIN_CHARS_PER_PAGE * pages:
            raise FulltextError(t("Could not extract text from the PDF (probably a scanned image): {source}",
                                  source=source) + "\n  " + t(
                "Apart from a line repeated on every page, there are only {chars} characters in {pages} pages. "
                "Get a PDF with text (or run OCR on it) and give it with `--pdf <path>`", chars=chars, pages=pages))
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_key = re.sub(r"[^\w.-]+", "_", entry["key"])[:80]
    out = out_dir / f"{entry['number']:03d}_{safe_key}.txt"
    saved = save_text(text, out)
    return {"path": str(out.relative_to(ROOT) if out.is_relative_to(ROOT) else out),
            "source": source, "pages": n_pages, "chars": saved["chars"], "page_markers": pdf is not None,
            "version": version, "working_paper": pdf is not None and working_paper_text(text),
            "references_chars": saved["references_chars"], "extractor": last_engine if pdf is not None else "text"}
