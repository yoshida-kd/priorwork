"""Zotero の一覧の同期（差分で添付を取りこぼさない）と、同じ論文が複数あるときの選び方。ネットには出ない。"""

from priorwork import zotero
from priorwork.zotero import ZoteroClient


class FakeResponse:
    def __init__(self, status, body, version):
        self.status_code, self.ok, self._body, self.text = status, status < 400, body, ""
        self.headers = {"Last-Modified-Version": str(version)}

    def json(self):
        return self._body


class FakeLibrary:
    """Zotero の Web API の読み取りの部分。items は key -> (version, data)。on_page はページを返すたびに呼ぶ。"""

    def __init__(self):
        self.version, self.items, self.on_page, self.calls = 0, {}, None, []

    def add(self, key, **data):
        self.version += 1
        self.items[key] = (self.version, {"key": key, **data})

    def paper(self, key, title, doi="", collections=()):
        self.add(key, itemType="journalArticle", title=title, DOI=doi, collections=list(collections))

    def pdf(self, key, parent):
        self.add(key, itemType="attachment", parentItem=parent, contentType="application/pdf", filename=f"{key}.pdf",
                 linkMode="imported_file")

    def __call__(self, method, url, params=None, headers=None, **kw):
        path = url.replace(zotero.API_BASE + "/users/1", "")
        params = params or {}
        self.calls.append((path, dict(params)))
        if path == "/collections":
            return FakeResponse(200, [], self.version)
        if path == "/deleted":
            return FakeResponse(200, {"items": []}, self.version)
        if path.endswith("/children"):
            parent = path.split("/")[2]
            return FakeResponse(200, [{"key": k, "data": d} for k, (v, d) in self.items.items()
                                      if d.get("parentItem") == parent], self.version)
        assert path == "/items"
        since = int(params.get("since") or 0)
        if params.get("format") == "versions":
            if since and since >= self.version:
                return FakeResponse(304, None, self.version)
            return FakeResponse(200, {k: v for k, (v, d) in self.items.items() if v > since}, self.version)
        if "itemKey" in params:
            keys = params["itemKey"].split(",")
            return FakeResponse(200, [{"key": k, "data": self.items[k][1]} for k in keys], self.version)
        start, limit = params["start"], params["limit"]
        rows = [kv for kv in self.items.items() if kv[1][0] > since]
        if params.get("sort") != "dateAdded":
            rows.sort(key=lambda kv: -kv[1][0])    # 本物の既定（dateModified の新しい順）に近い
        page = [{"key": k, "data": d} for k, (v, d) in rows[start:start + limit]]
        resp = FakeResponse(200, page, self.version)
        resp.headers["Total-Results"] = str(len(rows))
        if self.on_page:
            self.on_page(start)
        return resp


def client(tmp_path, monkeypatch, lib):
    monkeypatch.setattr(zotero.requests, "request", lib)
    return ZoteroClient("key", "1", index_path=tmp_path / "index.json")


def test_attachments_added_later_are_found_by_the_incremental_sync(tmp_path, monkeypatch):
    lib = FakeLibrary()
    for n in range(3):
        lib.paper(f"P{n}", f"A long enough title of paper number {n}", doi=f"10.1/{n}")
    z = client(tmp_path, monkeypatch, lib)
    z.sync()
    assert all(not z.pdf_attachments(f"P{n}") for n in range(3))
    for n in range(3):           # 子を足しても親の版は変わらない
        lib.pdf(f"F{n}", f"P{n}")
    z.sync()
    assert all(z.pdf_attachments(f"P{n}") for n in range(3))
    assert any(p.get("format") == "versions" for _, p in lib.calls)
    assert z.sync()["version"] == lib.version       # 変わっていなければ 304 で済む


def test_attachments_added_while_reading_are_not_lost(tmp_path, monkeypatch):
    """Zotero のアプリが同期している最中に全体を読んでも、そのあいだに増えた添付を取りこぼさない。"""
    lib = FakeLibrary()
    for n in range(250):
        lib.paper(f"P{n}", f"A long enough title of paper number {n}", doi=f"10.1/{n}")
    z = client(tmp_path, monkeypatch, lib)

    def upload(start):
        if start == 0:
            for n in range(40):
                lib.pdf(f"F{n}", f"P{n}")
    lib.on_page = upload
    z.sync(force=True)
    lib.on_page = None
    z.sync()
    assert sum(1 for n in range(250) if z.pdf_attachments(f"P{n}")) == 40


def test_pdf_attachments_can_reread_one_paper(tmp_path, monkeypatch):
    lib = FakeLibrary()
    lib.paper("P", "A long enough title of the paper", doi="10.1/p")
    z = client(tmp_path, monkeypatch, lib)
    z.sync()
    lib.pdf("F", "P")
    assert z.pdf_attachments("P") == []
    assert [a["key"] for a in z.pdf_attachments("P", refresh=True)] == ["F"]
    assert [a["key"] for a in z.pdf_attachments("P")] == ["F"]        # 一覧にも残る


def test_a_duplicate_with_a_pdf_is_preferred(tmp_path, monkeypatch, capsys):
    lib = FakeLibrary()
    title = "Administrative Burden: Learning, Psychological, and Compliance Costs"
    lib.paper("XJEK6YT7", title, doi="10.1093/jopart/muu009")
    lib.paper("BZW9AHYD", title, doi="10.1093/jopart/muu009")
    lib.pdf("F", "BZW9AHYD")
    lib.paper("NODOI", title)                                          # DOI の無い同じ題名も重複
    lib.paper("OTHER", title, doi="10.31235/osf.io/other")             # DOI の違う同じ題名は別の版
    z = client(tmp_path, monkeypatch, lib)
    record = {"doi": "10.1093/jopart/muu009", "title": title}
    assert [i["key"] for i in z.find_items(record)] == ["BZW9AHYD", "XJEK6YT7", "NODOI"]
    assert z.find_item(record)["key"] == "BZW9AHYD"
    err = capsys.readouterr().err
    assert "3 件" in err and "XJEK6YT7" in err and "重複アイテム" in err
    assert z.status(record)["pdfs"] == 1 and not capsys.readouterr().err   # 一覧の照合では知らせない
