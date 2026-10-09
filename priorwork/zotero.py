"""
Zotero 連携（読み取り専用）。

- Zotero Web API: ライブラリの論文一覧（DOI・添付ファイル）を手元に同期し、登録状況の照合と本文取得に使う
- WebDAV（Nextcloud など）: Zotero が `<添付キー>.zip` の形で保存している PDF を取得する
- WebDAV を使っていない場合は、Zotero File Storage の `/items/<key>/file` から取得する

Zotero にも WebDAV にも書き込みは一切しない（GET のみ）。

サーベイに Zotero のコレクションを結び付けると（`priorwork zotero SURVEY --collection 名前`）、
「Zotero にあるか」はそのコレクションに入っているかで見る。コレクションに入れた論文は候補として取り込め（`--import`）、
本文もそのコレクションの PDF を優先する。コレクションを作る・論文を入れるのはユーザー（Zotero に書き込まない）。

設定（.env）:
  ZOTERO_API_KEY, ZOTERO_USER_ID               … 必須（キーは「Allow library access」のみの読み取り専用を推奨）
  ZOTERO_WEBDAV_URL, ZOTERO_WEBDAV_USER, ZOTERO_WEBDAV_PASSWORD … WebDAV 同期のとき
"""

import io
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from . import ssci
from .i18n import t
from .workspace import CACHE_DIR

API_BASE = "https://api.zotero.org"
INDEX_PATH = CACHE_DIR / "zotero" / "index.json"
MAX_RETRIES = 5
MAX_PDF_BYTES = 100 * 1024 * 1024

_DOI_IN_EXTRA = re.compile(r"^\s*DOI:\s*(10\.\S+)\s*$", re.IGNORECASE | re.MULTILINE)


class ZoteroError(RuntimeError):
    pass


def normalize_doi(doi: str) -> str:
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", (doi or "").strip(), flags=re.IGNORECASE).lower()


class ZoteroClient:
    def __init__(self, api_key: str, user_id: str, webdav_url: str = "", webdav_user: str = "",
                 webdav_password: str = "", index_path: Optional[Path] = None):
        self.api_key = api_key
        self.prefix = f"{API_BASE}/users/{user_id}"
        self.webdav_url = webdav_url.rstrip("/") + "/" if webdav_url else ""
        self.webdav_auth = (webdav_user, webdav_password) if webdav_user else None
        self.index_path = index_path or INDEX_PATH
        self._index: Optional[Dict[str, Any]] = None
        # サーベイに結び付けたコレクション（キー）。同じ論文が複数あれば、こちらの中のものを優先する
        self.prefer_collection = ""

    @classmethod
    def from_env(cls) -> Optional["ZoteroClient"]:
        """.env に ZOTERO_API_KEY と ZOTERO_USER_ID が無ければ None（Zotero 連携なしで動く）。"""
        from . import api  # noqa: F401  .env を読み込ませる

        key, user = os.environ.get("ZOTERO_API_KEY"), os.environ.get("ZOTERO_USER_ID")
        if not key or not user:
            return None
        return cls(key, user,
                   webdav_url=os.environ.get("ZOTERO_WEBDAV_URL", ""),
                   webdav_user=os.environ.get("ZOTERO_WEBDAV_USER", ""),
                   webdav_password=os.environ.get("ZOTERO_WEBDAV_PASSWORD", ""))

    # ---- HTTP ----

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None,
             auth=None, api: bool = True, stream: bool = False) -> requests.Response:
        h = {"User-Agent": "priorwork/0.1"}
        if api:
            h.update({"Zotero-API-Key": self.api_key, "Zotero-API-Version": "3"})
        h.update(headers or {})
        service = "Zotero" if api else "WebDAV"
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.get(url, params=params, headers=h, auth=auth, timeout=60, stream=stream)
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt >= MAX_RETRIES:
                    raise ZoteroError(f"[{service}] " + t("Cannot connect: {error}", error=e.__class__.__name__))
                time.sleep(5 * (attempt + 1))
                continue
            if resp.status_code in (429, 503) and attempt < MAX_RETRIES:
                wait = float(resp.headers.get("Retry-After") or 5 * (attempt + 1))
                print(f"[{service}] " + t("HTTP {status}. Retrying in {seconds} s", status=resp.status_code, seconds=f"{wait:.0f}"), file=sys.stderr)
                time.sleep(wait)
                continue
            if resp.status_code in (401, 403):
                raise ZoteroError(f"[{service}] " + t("Authentication failed (HTTP {status}). Check the key, user ID and "
                                                      "password in .env, and the key's permissions (library access)",
                                                      status=resp.status_code))
            # サーバー過負荷時の Backoff 指示に従う（次のリクエストまで待つ）
            if api and resp.headers.get("Backoff"):
                time.sleep(min(float(resp.headers["Backoff"]), 60))
            return resp
        raise ZoteroError(f"[{service}] " + t("Gave up after too many retries"))

    # ---- Library index ----

    def sync(self, force: bool = False) -> Dict[str, Any]:
        """ライブラリの論文・添付ファイルの一覧を差分同期して .priorwork/cache/zotero/index.json に保存する。"""
        index = self._load_index()
        if force:
            index = {"version": 0, "items": {}}
        since = index["version"]

        headers = {"If-Modified-Since-Version": str(since)} if since else {}
        start, new_version = 0, since
        while True:
            resp = self._get(f"{self.prefix}/items", {"format": "json", "limit": 100, "start": start, "since": since},
                             headers=headers)
            if resp.status_code == 304:
                break
            if not resp.ok:
                raise ZoteroError("[Zotero] " + t("Cannot read the library (HTTP {status}): {detail}", status=resp.status_code, detail=resp.text[:200]))
            new_version = int(resp.headers.get("Last-Modified-Version", new_version))
            batch = resp.json()
            for item in batch:
                data = item.get("data") or {}
                if data.get("deleted") or data.get("itemType") in ("note", "annotation"):
                    index["items"].pop(item["key"], None)
                    continue
                index["items"][item["key"]] = {
                    "key": item["key"],
                    "itemType": data.get("itemType", ""),
                    "title": data.get("title", ""),
                    "doi": normalize_doi(data.get("DOI") or "") or
                           normalize_doi((_DOI_IN_EXTRA.search(data.get("extra") or "") or [None, ""])[1]),
                    "year": (re.search(r"\d{4}", data.get("date") or "") or [""])[0],
                    "parentItem": data.get("parentItem", ""),
                    "contentType": data.get("contentType", ""),
                    "linkMode": data.get("linkMode", ""),
                    "filename": data.get("filename", ""),
                    "collections": data.get("collections") or [],
                }
            total = int(resp.headers.get("Total-Results", len(batch)))
            start += len(batch)
            if not batch or start >= total:
                break

        if new_version != since or "collections" not in index:
            index["collections"] = self._fetch_collections()
        if since and new_version != since:
            resp = self._get(f"{self.prefix}/deleted", {"since": since})
            if resp.ok:
                for key in (resp.json().get("items") or []):
                    index["items"].pop(key, None)
        index["version"] = new_version
        index["synced_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._save_index(index)
        self._index = index
        return index

    def _fetch_collections(self) -> Dict[str, Dict[str, str]]:
        collections: Dict[str, Dict[str, str]] = {}
        start = 0
        while True:
            resp = self._get(f"{self.prefix}/collections", {"format": "json", "limit": 100, "start": start})
            if not resp.ok:
                raise ZoteroError("[Zotero] " + t("Cannot read the collections (HTTP {status})", status=resp.status_code))
            batch = resp.json()
            for c in batch:
                data = c.get("data") or {}
                collections[c["key"]] = {"key": c["key"], "name": data.get("name", ""),
                                         "parent": data.get("parentCollection") or ""}
            start += len(batch)
            if not batch or start >= int(resp.headers.get("Total-Results", len(batch))):
                return collections

    def collections(self) -> List[Dict[str, Any]]:
        """コレクションの一覧（親の名前つきのパス "親 / 子" と、中の論文の数）。"""
        cols = self.index.get("collections") or {}

        def path(key: str, depth: int = 0) -> str:
            c = cols.get(key)
            if not c or depth > 20:
                return ""
            parent = path(c["parent"], depth + 1) if c["parent"] else ""
            return f"{parent} / {c['name']}" if parent else c["name"]

        counts: Dict[str, int] = {}
        for i in self._parents():
            for k in i["collections"]:
                counts[k] = counts.get(k, 0) + 1
        return sorted(({"key": k, "name": c["name"], "path": path(k), "items": counts.get(k, 0)}
                       for k, c in cols.items()), key=lambda c: c["path"].lower())

    def find_collection(self, name_or_key: str) -> Dict[str, Any]:
        """名前・パス・キーでコレクションを探す。見つからない / 複数あればエラー。"""
        q = name_or_key.strip()
        cols = self.collections()
        hits = ([c for c in cols if c["key"] == q] or [c for c in cols if c["path"] == q]
                or [c for c in cols if c["name"].lower() == q.lower()])
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise ZoteroError(t("No Zotero collection named \"{name}\". The collections: {names}", name=q,
                                names=", ".join(c["path"] for c in cols) or t("(none)")))
        raise ZoteroError(t("More than one Zotero collection is named \"{name}\"; give the path or the key: {names}",
                            name=q, names=", ".join(f"{c['path']} ({c['key']})" for c in hits)))

    def collection_items(self, key: str) -> List[Dict[str, Any]]:
        return [i for i in self._parents() if key in i["collections"]]

    def _parents(self) -> List[Dict[str, Any]]:
        return [i for i in self.index["items"].values() if not i["parentItem"] and i["itemType"] != "attachment"]

    def _load_index(self) -> Dict[str, Any]:
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"version": 0, "items": {}}

    def _save_index(self, index: Dict[str, Any]):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.index_path)

    @property
    def index(self) -> Dict[str, Any]:
        if self._index is None:
            self.sync()
        return self._index

    # ---- Lookup ----

    def find_item(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """DOI（無ければタイトル）で、論文に対応する Zotero の親アイテムを探す。"""
        items = sorted(self._parents(), key=lambda i: self.prefer_collection not in i.get("collections", []))
        doi = normalize_doi(record.get("doi", ""))
        if doi:
            for i in items:
                if i["doi"] == doi:
                    return i
        title = ssci.normalize_title(record.get("title", ""))
        if len(title) > 20:
            for i in items:
                if ssci.normalize_title(i["title"]) == title:
                    return i
        return None

    def pdf_attachments(self, parent_key: str) -> List[Dict[str, Any]]:
        return [i for i in self.index["items"].values()
                if i["parentItem"] == parent_key and i["contentType"] == "application/pdf"]

    def status(self, record: Dict[str, Any], collection: str = "") -> Dict[str, Any]:
        """Zotero にあるか。collection を渡すと、そのコレクションに入っているか（in_collection）も見る。"""
        item = self.find_item(record)
        if not item:
            return {"registered": False, "key": "", "pdfs": 0, "in_collection": False}
        return {"registered": True, "key": item["key"], "pdfs": len(self.pdf_attachments(item["key"])),
                "in_collection": bool(collection) and collection in item.get("collections", [])}

    # ---- Content ----

    def download_pdf(self, attachment: Dict[str, Any]) -> bytes:
        """添付 PDF を WebDAV（<key>.zip）または Zotero File Storage から取得する。"""
        if attachment["linkMode"] == "linked_file":
            raise ZoteroError(t("A linked file ({name}) is not synced to the server, so it cannot be fetched", name=attachment["filename"]))

        if self.webdav_url:
            url = f"{self.webdav_url}{attachment['key']}.zip"
            resp = self._get(url, auth=self.webdav_auth, api=False)
            if resp.status_code == 404:
                raise ZoteroError(t("{file} is not on the WebDAV server (Zotero may not have synced the file yet)", file=f"{attachment['key']}.zip"))
            if not resp.ok:
                raise ZoteroError(t("Cannot fetch from WebDAV (HTTP {status}): {url}", status=resp.status_code, url=url))
            return _pdf_from_zip(resp.content, attachment.get("filename", ""))

        resp = self._get(f"{self.prefix}/items/{attachment['key']}/file")
        if resp.status_code == 404:
            raise ZoteroError(t("The file is not in Zotero File Storage (if you sync with WebDAV, set ZOTERO_WEBDAV_URL)"))
        if not resp.ok:
            raise ZoteroError(t("Cannot fetch from Zotero File Storage (HTTP {status})", status=resp.status_code))
        if len(resp.content) > MAX_PDF_BYTES or not resp.content.startswith(b"%PDF"):
            raise ZoteroError(t("The file fetched is not a PDF"))
        return resp.content

    def indexed_fulltext(self, attachment_key: str) -> Optional[Dict[str, Any]]:
        """Zotero デスクトップが索引化・同期した本文テキスト（ページ区切りなし）。無ければ None。"""
        resp = self._get(f"{self.prefix}/items/{attachment_key}/fulltext")
        if resp.status_code == 404:
            return None
        if not resp.ok:
            raise ZoteroError("[Zotero] " + t("Cannot fetch the full text (HTTP {status})", status=resp.status_code))
        return resp.json()

    def check_webdav(self) -> str:
        """WebDAV の設定確認用。PROPFIND（読み取り）でフォルダが見えるかだけを確かめる。"""
        if not self.webdav_url:
            return t("not set (Zotero File Storage is used)")
        try:
            resp = requests.request("PROPFIND", self.webdav_url, auth=self.webdav_auth, headers={"Depth": "0"},
                                    timeout=30)
        except requests.RequestException as e:
            return t("Cannot connect: {error}", error=e.__class__.__name__)
        if resp.status_code == 207:
            return t("connected")
        if resp.status_code in (401, 403):
            return t("authentication failed (HTTP {status})", status=resp.status_code)
        if resp.status_code == 404:
            return t("folder not found (check that ZOTERO_WEBDAV_URL ends in .../zotero/)")
        return t("unexpected response (HTTP {status})", status=resp.status_code)


def _pdf_from_zip(data: bytes, filename: str) -> bytes:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ZoteroError(t("The file on the WebDAV server is not a readable ZIP"))
    members = [m for m in zf.infolist() if m.filename.lower().endswith(".pdf")]
    if not members:
        raise ZoteroError(t("There is no PDF in the ZIP"))
    member = next((m for m in members if m.filename == filename), members[0])
    if member.file_size > MAX_PDF_BYTES:
        raise ZoteroError(t("The PDF is too large ({mb} MB)", mb=member.file_size // 1024 // 1024))
    pdf = zf.read(member)
    if not pdf.startswith(b"%PDF"):
        raise ZoteroError(t("The file in the ZIP is not a PDF"))
    return pdf
