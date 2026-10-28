"""
Zotero 連携。既定は読み取り専用で、設定で許可したときだけ採用論文をコレクションに入れる。

- Zotero Web API: ライブラリの論文一覧（DOI・添付ファイル）を手元に同期し、登録状況の照合と本文取得に使う
- WebDAV（Nextcloud など）: Zotero が `<添付キー>.zip` の形で保存している PDF を取得する
- WebDAV を使っていない場合は、Zotero File Storage の `/items/<key>/file` から取得する

サーベイに Zotero のコレクションを結び付けると（`priorwork zotero SURVEY --collection 名前`）、
「Zotero にあるか」はそのコレクションに入っているかで見る。コレクションに入れた論文は候補として取り込め（`--import`）、
本文もそのコレクションの PDF を優先する。コレクションを作るのはユーザー。

書き込み（`priorwork zotero SURVEY --add`）は、ZOTERO_WRITE=1 で、キーに書き込みの権限があり、サーベイに
コレクションを結び付けたときだけ行う。することは「採用論文をそのコレクションに入れる」だけ:
ライブラリに同じ DOI（無ければタイトル）のアイテムがあれば、そのコレクションに足す。無ければ書誌から作る。
ほかのアイテムの中身・ほかのコレクション・WebDAV には触らない。書いたものは状態ファイルに記録し、
`--undo` で Priorwork が書いたものだけを戻す（作ったアイテムはごみ箱へ。ユーザーが手を入れたものは残す）。

設定（.env）:
  ZOTERO_API_KEY, ZOTERO_USER_ID               … 必須（書き込まないなら「Allow library access」のみのキーを推奨）
  ZOTERO_WRITE=1                               … 採用論文をコレクションに入れてよい（キーに「Allow write access」も要る）
  ZOTERO_WEBDAV_URL, ZOTERO_WEBDAV_USER, ZOTERO_WEBDAV_PASSWORD … WebDAV 同期のとき
"""

import io
import json
import os
import re
import secrets
import sys
import tempfile
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
WRITE_BATCH = 50   # Zotero の API が一度に受け付けるアイテムの数

_DOI_IN_EXTRA = re.compile(r"^\s*DOI:\s*(10\.\S+)\s*$", re.IGNORECASE | re.MULTILINE)


class ZoteroError(RuntimeError):
    pass


def normalize_doi(doi: str) -> str:
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", (doi or "").strip(), flags=re.IGNORECASE).lower()


class ZoteroClient:
    def __init__(self, api_key: str, user_id: str, webdav_url: str = "", webdav_user: str = "",
                 webdav_password: str = "", index_path: Optional[Path] = None, write: bool = False):
        self.api_key = api_key
        self.write = write   # ZOTERO_WRITE で、採用論文をコレクションに入れることを許されているか
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
                   webdav_password=os.environ.get("ZOTERO_WEBDAV_PASSWORD", ""),
                   write=write_allowed())

    # ---- HTTP ----

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None,
             auth=None, api: bool = True, stream: bool = False) -> requests.Response:
        return self._request("GET", url, params=params, headers=headers, auth=auth, api=api, stream=stream)

    def _request(self, method: str, url: str, params: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None, auth=None, api: bool = True, stream: bool = False,
                 body: Any = None) -> requests.Response:
        if method != "GET" and not (api and self.write):
            raise ZoteroError(t("Writing to Zotero is not allowed (set ZOTERO_WRITE=1 in .env)"))
        h = {"User-Agent": "priorwork/0.1"}
        if api:
            h.update({"Zotero-API-Key": self.api_key, "Zotero-API-Version": "3"})
        h.update(headers or {})
        service = "Zotero" if api else "WebDAV"
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.request(method, url, params=params, headers=h, auth=auth, timeout=60, stream=stream,
                                        json=body)
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
        """コレクションの一覧。Zotero と同じ木の順（親の直後に子、同じ親の中は名前順）で、
        パス（"親 / 子"）・深さ（一番上が 0）・中の論文の数（items: そのコレクションだけ、
        total: 下のコレクションも含めて）を付ける。"""
        cols = self.index.get("collections") or {}
        children: Dict[str, List[str]] = {}
        for k, c in cols.items():
            parent = c["parent"] if c["parent"] in cols else ""
            children.setdefault(parent, []).append(k)
        direct: Dict[str, int] = {}
        for i in self._parents():
            for k in i["collections"]:
                direct[k] = direct.get(k, 0) + 1
        out: List[Dict[str, Any]] = []

        def walk(parent: str, prefix: str, depth: int, seen: frozenset):
            for k in sorted(children.get(parent, []), key=lambda k: cols[k]["name"].lower()):
                if k in seen:      # 壊れた親子関係でも止まる
                    continue
                path = f"{prefix} / {cols[k]['name']}" if prefix else cols[k]["name"]
                out.append({"key": k, "name": cols[k]["name"], "path": path, "parent": parent, "depth": depth,
                            "items": direct.get(k, 0), "total": 0})
                walk(k, path, depth + 1, seen | {k})
        walk("", "", 0, frozenset())
        for c in out:
            c["total"] = len(self.collection_items(c["key"]))
        return out

    def subtree(self, key: str) -> set:
        """そのコレクションと、その下のコレクションすべてのキー。"""
        cols = self.index.get("collections") or {}
        keys, todo = set(), [key]
        while todo:
            k = todo.pop()
            if k in keys:
                continue
            keys.add(k)
            todo += [c for c, v in cols.items() if v["parent"] == k]
        return keys

    def find_collection(self, name_or_key: str) -> Dict[str, Any]:
        """パス（"親 / 子" または "親/子"）・名前・キーでコレクションを探す。見つからない / 複数あればエラー。
        同じ名前のコレクションが別の親の下にあれば、パスで指定してもらう。"""
        q = name_or_key.strip()
        norm = lambda p: "/".join(part.strip().lower() for part in p.split("/"))   # noqa: E731
        cols = self.collections()
        hits = ([c for c in cols if c["key"] == q] or [c for c in cols if c["path"] == q]
                or [c for c in cols if norm(c["path"]) == norm(q)]
                or [c for c in cols if c["name"].lower() == q.lower()])
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise ZoteroError(t("No Zotero collection named \"{name}\". The collections: {names}", name=q,
                                names=", ".join(c["path"] for c in cols) or t("(none)")))
        raise ZoteroError(t("More than one Zotero collection is named \"{name}\"; give the path or the key: {names}",
                            name=q, names=", ".join(f"{c['path']} ({c['key']})" for c in hits)))

    def collection_items(self, key: str) -> List[Dict[str, Any]]:
        """そのコレクションの論文。下のコレクションに入れた論文も含める（論文ごとのコレクションを
        「理論」「方法」のように分けて使っていても、まとめて一つのコレクションとして扱う）。"""
        keys = self.subtree(key)
        return [i for i in self._parents() if keys & set(i["collections"])]

    def _parents(self) -> List[Dict[str, Any]]:
        return [i for i in self.index["items"].values() if not i["parentItem"] and i["itemType"] != "attachment"]

    def _load_index(self) -> Dict[str, Any]:
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"version": 0, "items": {}}

    def _save_index(self, index: Dict[str, Any]):
        """一覧のキャッシュを書く。VS Code のサイドバーは複数の `status` を同時に走らせるので、
        一時ファイルはプロセスごとに分ける。書けなくても（キャッシュなので）止めない。"""
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix="index.", suffix=".tmp", dir=self.index_path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False)
            os.replace(tmp, self.index_path)
        except OSError as e:
            print("[Notice] " + t("Could not save the Zotero cache: {error}", error=e), file=sys.stderr)

    @property
    def index(self) -> Dict[str, Any]:
        if self._index is None:
            self.sync()
        return self._index

    def sync_note(self) -> str:
        """Zotero のアプリでの変更が見えないときの説明。Priorwork が読むのは zotero.org のライブラリで、
        アプリの変更はアプリが同期してから届く（PDF はファイルの同期も要る）。"""
        when = (self._index or {}).get("synced_at") or "?"
        return t("Priorwork reads your library on zotero.org (read at {when}). What you change in the Zotero app "
                 "shows here once the app has synced it: press the sync button (the green arrows) in Zotero, wait "
                 "until it stops, and run this again. A PDF also needs Zotero's file syncing (Settings > Sync > "
                 "File Syncing, or WebDAV); until then, `priorwork fulltext SURVEY N --pdf <path>` reads it.",
                 when=when)

    # ---- Lookup ----

    def find_item(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """DOI（無ければタイトル）で、論文に対応する Zotero の親アイテムを探す。"""
        preferred = self.subtree(self.prefer_collection) if self.prefer_collection else set()
        items = sorted(self._parents(), key=lambda i: not (preferred & set(i.get("collections", []))))
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
                "in_collection": bool(collection) and bool(self.subtree(collection) & set(item.get("collections", [])))}

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

    # ---- Writing (ZOTERO_WRITE=1 のときだけ。採用論文をコレクションに入れることだけをする) ----

    def check_write_access(self):
        """キーに書き込みの権限があるか確かめる。無ければ ZoteroError。"""
        resp = self._get(f"{API_BASE}/keys/current")
        if not resp.ok:
            raise ZoteroError("[Zotero] " + t("Cannot read the key's permissions (HTTP {status})", status=resp.status_code))
        if not ((resp.json().get("access") or {}).get("user") or {}).get("write"):
            raise ZoteroError("[Zotero] " + t("The API key cannot write to the library. At https://www.zotero.org/settings/keys, "
                                              "edit the key and check \"Allow write access\""))

    def item(self, key: str) -> Optional[Dict[str, Any]]:
        """アイテムの今の中身（version と data）。消えていれば None。"""
        resp = self._get(f"{self.prefix}/items/{key}")
        if resp.status_code == 404:
            return None
        if not resp.ok:
            raise ZoteroError("[Zotero] " + t("Cannot read the item {key} (HTTP {status})", key=key, status=resp.status_code))
        return resp.json()

    def _patch(self, key: str, version: int, data: Dict[str, Any]) -> int:
        """アイテムの一部を書き換え、新しい版を返す。ほかで書き換えられていれば（版が違えば）書かない。"""
        resp = self._request("PATCH", f"{self.prefix}/items/{key}", headers={"If-Unmodified-Since-Version": str(version)},
                             body=data)
        if resp.status_code == 412:
            raise ZoteroError("[Zotero] " + t("The item {key} was changed in Zotero meanwhile; run it again", key=key))
        if not resp.ok:
            raise ZoteroError("[Zotero] " + t("Cannot change the item {key} (HTTP {status}): {detail}", key=key,
                                              status=resp.status_code, detail=resp.text[:200]))
        return int(resp.headers.get("Last-Modified-Version") or version + 1)

    def _create(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """アイテムを作る。作れたものは {key, version}、断られたものは {error}（並びは渡したものと同じ）。
        途中で失敗しても、それまでに作ったものを返す（記録して --undo で戻せるように）。"""
        out: List[Dict[str, Any]] = []
        for i in range(0, len(items), WRITE_BATCH):
            chunk = items[i:i + WRITE_BATCH]
            try:
                # 書き込みの合言葉があれば、やり直しで同じアイテムが二重にできない
                resp = self._request("POST", f"{self.prefix}/items",
                                     headers={"Zotero-Write-Token": secrets.token_hex(16)}, body=chunk)
                if not resp.ok:
                    raise ZoteroError("[Zotero] " + t("Cannot add the items (HTTP {status}): {detail}",
                                                      status=resp.status_code, detail=resp.text[:200]))
            except ZoteroError as e:
                out += [{"error": str(e)} for _ in chunk]
                continue
            result = resp.json()
            for n in range(len(chunk)):
                done = (result.get("successful") or {}).get(str(n))
                failed = (result.get("failed") or {}).get(str(n)) or {}
                out.append({"key": done["key"], "version": int(done.get("version") or 0)} if done
                           else {"error": failed.get("message") or t("rejected by Zotero")})
        return out

    def plan_add(self, papers: List[Dict[str, Any]], collection: str) -> List[Dict[str, Any]]:
        """コレクションに入れる論文と、そのやり方（collect: ライブラリにあるアイテムを足す / create: 書誌から作る）。
        papers はサーベイの論文（number と record）。コレクションに（その下も含めて）既にあるものは入れない。"""
        plan = []
        for e in papers:
            st = self.status(e["record"], collection)
            if st["in_collection"]:
                continue
            plan.append({"number": e["number"], "title": e["record"]["title"], "doi": e["record"].get("doi") or "",
                         "action": "collect" if st["registered"] else "create", "key": st["key"]})
        return plan

    def add(self, plan: List[Dict[str, Any]], records: Dict[int, Dict[str, Any]], collection: str) -> List[Dict[str, Any]]:
        """plan_add の計画どおりに書き、それぞれに done（と key・version、または error）を付けて返す。"""
        creates = [p for p in plan if p["action"] == "create"]
        for p, r in zip(creates, self._create([item_from_record(records[p["number"]], [collection]) for p in creates])):
            p.update(r, done="key" in r)
        for p in plan:
            if p["action"] != "collect":
                continue
            try:
                cur = self.item(p["key"])
                if cur is None:
                    raise ZoteroError("[Zotero] " + t("The item {key} is no longer in the library", key=p["key"]))
                cols = cur["data"].get("collections") or []
                version = cur["version"] if collection in cols else self._patch(p["key"], cur["version"],
                                                                               {"collections": cols + [collection]})
                p.update(done=True, version=version)
            except ZoteroError as e:
                p.update(done=False, error=str(e))
        return plan

    def undo(self, written: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """add で書いたものを戻す。作ったアイテムは、その後に手が入っていなければ（版が同じで、PDF などの子が
        無ければ）ごみ箱に入れ、入っていれば残す（keep）。足したアイテムは、そのコレクションから外すだけ。"""
        out = []
        for w in written:
            r = {**w, "done": True}
            try:
                cur = self.item(w["key"])
                if cur is None or cur["data"].get("deleted"):
                    r["undo"] = "gone"
                elif w["action"] == "create":
                    children = any(i["parentItem"] == w["key"] for i in self.index["items"].values())
                    if cur["version"] == w.get("version") and not children:
                        self._patch(w["key"], cur["version"], {"deleted": 1})
                        r["undo"] = "trash"
                    else:
                        r["undo"] = "keep"
                else:
                    cols = cur["data"].get("collections") or []
                    if w["collection"] in cols:
                        self._patch(w["key"], cur["version"], {"collections": [c for c in cols if c != w["collection"]]})
                    r["undo"] = "uncollect"
            except ZoteroError as e:
                r.update(done=False, error=str(e))
            out.append(r)
        return out


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


def write_allowed() -> bool:
    """.env の ZOTERO_WRITE で、採用論文を Zotero のコレクションに入れることが許されているか。"""
    return os.environ.get("ZOTERO_WRITE", "").strip().lower() in ("1", "true", "yes", "on")


def _creator(name: str) -> Dict[str, str]:
    first, _, last = name.rpartition(" ")
    return ({"creatorType": "author", "firstName": first, "lastName": last} if first
            else {"creatorType": "author", "name": name})


def item_from_record(rec: Dict[str, Any], collections: List[str]) -> Dict[str, Any]:
    """サーベイの論文の書誌から、Zotero のアイテムを作る（雑誌論文・本の章・本）。"""
    types = {x.lower() for x in rec.get("publication_types") or []}
    doi = rec.get("doi") or ""
    common = {"title": rec.get("title", ""), "creators": [_creator(a) for a in rec.get("authors") or []],
              "abstractNote": rec.get("abstract", ""), "date": str(rec.get("year") or ""), "url": rec.get("url", ""),
              "collections": collections}
    if types & {"book-chapter", "booksection"}:
        item = {"itemType": "bookSection", **common, "bookTitle": rec.get("journal_name", ""),
                "pages": rec.get("pages", ""), "extra": f"DOI: {doi}" if doi else ""}
    elif "book" in types and not rec.get("journal_name"):
        item = {"itemType": "book", **common, "extra": f"DOI: {doi}" if doi else ""}
    else:
        item = {"itemType": "journalArticle", **common, "publicationTitle": rec.get("journal_name", ""),
                "volume": rec.get("volume", ""), "issue": rec.get("issue", ""), "pages": rec.get("pages", ""),
                "DOI": doi, "ISSN": ", ".join(rec.get("issns") or [])}
    return {k: v for k, v in item.items() if v or k == "collections"}
