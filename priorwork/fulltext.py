"""
本文テキストの取得（`priorwork fulltext`）。

PDF はリポジトリに置かない。次の順で PDF を探し、抽出したテキストだけを
Git 管理外の `.priorwork/cache/fulltext/` に保存する。

1. `--pdf` で指定したファイル
2. このマシンの Zotero データフォルダ（`ZOTERO_DATA_DIR`、既定は ~/Zotero）の添付 PDF
3. Zotero Web API で見つけた添付 PDF（WebDAV / Zotero File Storage から取得）
4. Zotero が索引化した本文テキスト（ページ区切りなし）
5. オープンアクセス版の PDF（Semantic Scholar / OpenAlex が示す URL）

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


def download_pdf(url: str) -> bytes:
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
        raise FulltextError(t("Not a PDF (probably the publisher's landing page): {url}", url=url))
    return data


def extract_text(pdf: bytes) -> Tuple[str, int]:
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)  # フォント関連の冗長な警告を抑える
    reader = PdfReader(io.BytesIO(pdf))
    pages = []
    for i, page in enumerate(reader.pages, 1):
        pages.append(f"\n\n=== page {i} ===\n\n" + (page.extract_text() or ""))
    return "".join(pages).strip(), len(reader.pages)


def oa_pdf_urls(record: Dict[str, Any], client: Any) -> List[str]:
    urls = [record["oa_pdf"]] if record.get("oa_pdf") else []
    if record.get("doi"):
        for w in client.openalex_works(dois=[record["doi"]], select="doi,open_access,best_oa_location,primary_location"):
            for loc in (w.get("best_oa_location") or {}, w.get("primary_location") or {}):
                if loc.get("pdf_url"):
                    urls.append(loc["pdf_url"])
            if (w.get("open_access") or {}).get("oa_url"):
                urls.append(w["open_access"]["oa_url"])
    return list(dict.fromkeys(urls))


def fetch_fulltext(entry: Dict[str, Any], client: Any, pdf_path: Optional[str] = None,
                   out_dir: Optional[Path] = None, zotero: Any = None) -> Dict[str, Any]:
    from .zotero import ZoteroError

    out_dir = out_dir or FULLTEXT_DIR
    record = entry["record"]
    attempts = []
    pdf, source, text, n_pages = None, "", None, None

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
        for url in urls:
            try:
                pdf, source = download_pdf(url), f"oa:{url}"
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
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_key = re.sub(r"[^\w.-]+", "_", entry["key"])[:80]
    out = out_dir / f"{entry['number']:03d}_{safe_key}.txt"
    out.write_text(text, encoding="utf-8")
    return {"path": str(out.relative_to(ROOT) if out.is_relative_to(ROOT) else out),
            "source": source, "pages": n_pages, "chars": len(text), "page_markers": pdf is not None}
