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

from .i18n import t

from .workspace import CACHE_DIR, ROOT

FULLTEXT_DIR = CACHE_DIR / "fulltext"
MAX_PDF_BYTES = 50 * 1024 * 1024


class FulltextError(RuntimeError):
    pass


def journal_pages(record: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    """掲載誌のページ範囲（"330-345" → (330, 345)）。最後のページが無い・最初より前なら (最初, None)。"""
    m = re.match(r"^\s*(\d+)\s*(?:[-–]+\s*(\d+))?", record.get("pages") or "")
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
    for key, path in rows:
        if not path:
            continue
        if path.startswith("storage:"):
            candidate = data_dir / "storage" / key / path[len("storage:"):]
        else:
            candidate = Path(path)  # リンクされたファイル（絶対パス）
        if candidate.exists():
            return candidate
    return None


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


def extract_text(pdf: bytes) -> Tuple[str, int]:
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)  # フォント関連の冗長な警告を抑える
    reader = PdfReader(io.BytesIO(pdf))
    pages = []
    for i, page in enumerate(reader.pages, 1):
        pages.append(f"\n\n=== page {i} ===\n\n" + (page.extract_text() or ""))
    return "".join(pages).strip(), len(reader.pages)


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
            attachments = zotero.pdf_attachments(item["key"]) if item else []
            if not item:
                attempts.append(t("Not in the Zotero library (matched by DOI and title)"))
            elif not attachments:
                attempts.append(t("In Zotero, but no PDF is attached"))
            if not item or not attachments:
                attempts.append(zotero.sync_note())
            for att in attachments:
                try:
                    pdf, source = zotero.download_pdf(att), f"zotero:{att['key']} ({att['filename']})"
                    break
                except ZoteroError as e:
                    attempts.append(str(e))
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
    if pdf is None and text is None:
        raise FulltextError(t("No full-text PDF was found:") + "\n  - " + "\n  - ".join(attempts) +
                            "\n  → " + t("Attach the PDF in Zotero, or give it with `--pdf <path>`"))

    if pdf is not None:
        text, n_pages = extract_text(pdf)
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
    out.write_text(text, encoding="utf-8")
    return {"path": str(out.relative_to(ROOT) if out.is_relative_to(ROOT) else out),
            "source": source, "pages": n_pages, "chars": len(text), "page_markers": pdf is not None,
            "version": version}
