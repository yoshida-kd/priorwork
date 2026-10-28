"""検索の件数（深さで変わる既定）・bulk のクエリの直し・Zotero のコレクション。"""

import pytest

from priorwork import cli, zotero
from priorwork.api import bulk_query, from_openalex, from_s2
from priorwork.zotero import ZoteroClient, ZoteroError

from .conftest import openalex_work, s2_paper
from .test_cli_json import ws  # noqa: F401  （フィクスチャ）


def test_bulk_query_turns_boolean_words_into_operators():
    assert bulk_query('(local government OR "public sector") AND contracting') == \
        '(local government | "public sector") + contracting'
    assert bulk_query("outsourcing AND NOT simulation") == "outsourcing -simulation"
    assert bulk_query('"make OR buy" | insourcing') == '"make OR buy" | insourcing'   # 引用符の中は変えない
    assert bulk_query("Oregon and Portland") == "Oregon and Portland"                  # 小文字は語のまま


class ManyClient:
    """何件でも返す検索。"""
    calls = []

    def __init__(self, use_cache=True):
        pass

    def complete_abstracts(self, records):
        return records

    def search(self, query, limit=20, year=None, bulk=False):
        ManyClient.calls.append(limit)
        return [from_openalex(openalex_work(title=f"Paper {query} {i} on outsourcing", doi=f"10.1/{query}{i}",
                                            wid=f"W{query}{i}", citations=200 - i)) for i in range(limit)]


def test_a_full_survey_searches_more_by_default(ws, monkeypatch):  # noqa: F811
    monkeypatch.setattr(cli, "LiteratureClient", ManyClient)
    ws("new", "t", "--slug", "deep", "--depth", "full", "--json")
    ws("new", "t", "--slug", "quick", "--depth", "quick", "--json")
    assert ws("search", "a", "--into", "deep", "--json")["hits"] == 25
    assert ws("search", "b", "--into", "quick", "--json")["hits"] == 10
    assert ws("search", "c", "--into", "deep", "--limit", "5", "--json")["hits"] == 5

    steps = {s["id"]: s for s in ws("status", "deep", "--json")["next"]}
    assert "search_more" in steps and "2" in steps["search_more"]["text"]   # 2 クエリ
    assert "search_more" not in {s["id"] for s in ws("status", "quick", "--json")["next"]}


# ---------------- Zotero ----------------

def fake_zotero(tmp_path):
    z = ZoteroClient("key", "1", index_path=tmp_path / "zindex.json")
    item = {"parentItem": "", "contentType": "", "linkMode": "", "filename": "", "year": "2020"}
    z._index = {"version": 3, "collections": {
        "C1": {"key": "C1", "name": "make-or-buy", "parent": ""},
        "C2": {"key": "C2", "name": "reading", "parent": "C1"},
    }, "items": {
        "A": {**item, "key": "A", "itemType": "journalArticle", "title": "Paper number 0 on minimum wages",
              "doi": "10.1/0", "collections": ["C1"]},
        "B": {**item, "key": "B", "itemType": "journalArticle", "title": "Paper number 1 on minimum wages",
              "doi": "10.1/1", "collections": []},
        "N": {**item, "key": "N", "itemType": "journalArticle", "title": "A paper the user put in the folder",
              "doi": "10.9/new", "collections": ["C1"]},
        "X": {**item, "key": "X", "itemType": "book", "title": "A book without a DOI in the folder",
              "doi": "", "collections": ["C1"]},
    }}
    z.sync = lambda force=False: z._index
    return z


def test_collections_and_lookup(tmp_path):
    z = fake_zotero(tmp_path)
    assert [(c["path"], c["items"]) for c in z.collections()] == [("make-or-buy", 3), ("make-or-buy / reading", 0)]
    assert z.find_collection("reading")["key"] == "C2"
    assert z.find_collection("make-or-buy / reading")["key"] == "C2"
    with pytest.raises(ZoteroError):
        z.find_collection("nothing")


def test_collections_form_a_tree_and_count_subcollections(tmp_path):
    z = fake_zotero(tmp_path)
    cols = z._index["collections"]
    cols["C3"] = {"key": "C3", "name": "Another paper", "parent": ""}
    cols["C4"] = {"key": "C4", "name": "reading", "parent": "C3"}           # 同じ名前が別の親の下に
    cols["C5"] = {"key": "C5", "name": "Theory", "parent": "C2"}
    z._index["items"]["B"]["collections"] = ["C5"]                          # 孫のコレクションに入れた論文
    got = z.collections()
    assert [(c["path"], c["depth"], c["items"], c["total"]) for c in got] == [
        ("Another paper", 0, 0, 0), ("Another paper / reading", 1, 0, 0),
        ("make-or-buy", 0, 3, 4), ("make-or-buy / reading", 1, 0, 1), ("make-or-buy / reading / Theory", 2, 1, 1)]
    assert got[1]["parent"] == "C3"
    with pytest.raises(ZoteroError, match="make-or-buy / reading"):           # 名前だけでは決まらない
        z.find_collection("reading")
    assert z.find_collection("make-or-buy/reading")["key"] == "C2"          # 区切りの空白は問わない
    assert z.find_collection("Make-or-buy / Reading / theory")["key"] == "C5"
    record = {"doi": "10.1/1", "title": "Paper number 1 on minimum wages"}
    assert z.status(record, "C1")["in_collection"] and not z.status(record, "C3")["in_collection"]


def test_link_a_collection_import_and_list_dois(ws, tmp_path, monkeypatch, capsys):  # noqa: F811
    z = fake_zotero(tmp_path)
    monkeypatch.setattr(zotero.ZoteroClient, "from_env", classmethod(lambda cls: z))
    monkeypatch.setattr(cli.ZoteroClient, "from_env", classmethod(lambda cls: z))

    class Client(ManyClient):
        def complete_abstracts(self, records):
            return records

        def search(self, query, limit=20, year=None, bulk=False):
            return [from_openalex(openalex_work(title=f"Paper number {i} on minimum wages", doi=f"10.1/{i}",
                                                wid=f"W{i}", citations=100 - i)) for i in range(3)]

        def get_paper(self, doi):
            return from_openalex(openalex_work(title="A paper the user put in the folder", doi=doi, wid="W99"))

    monkeypatch.setattr(cli, "LiteratureClient", Client)
    ws("new", "t", "--slug", "mw", "--json")
    ws("search", "x", "--into", "mw", "--json")
    ws("include", "mw", "1", "2", "3", "--json")

    assert ws("zotero", "--collections", "--json")["collections"][0]["name"] == "make-or-buy"
    linked = ws("zotero", "mw", "--collection", "make-or-buy", "--json")
    assert linked["collection"] == {"key": "C1", "name": "make-or-buy"}
    # #1 はコレクションにある / #2 は Zotero にあるがコレクションに無い / #3 は Zotero に無い
    assert linked["missing_dois"] == ["10.1/1", "10.1/2"] and linked["to_import"] == 2

    detail = ws("status", "mw", "--json")
    assert detail["zotero_collection"]["name"] == "make-or-buy" and detail["zotero_missing"] == [2, 3]
    assert "zotero_import" in {s["id"] for s in detail["next"]}

    imported = ws("zotero", "mw", "--import", "--json")
    assert [a["title"] for a in imported["imported"]] == ["A paper the user put in the folder"]
    assert imported["no_doi"] == ["A book without a DOI in the folder"] and imported["to_import"] == 1
    entries = ws("list", "mw", "--json")
    assert entries[-1]["found_by"] == ["zotero"] and entries[-1]["status"] == "candidate"

    capsys.readouterr()
    cli.main(["zotero", "mw", "--dois"])
    assert capsys.readouterr().out.split() == ["10.1/1", "10.1/2"]

    assert ws("zotero", "mw", "--collection", "", "--json")["collection"] is None


def test_the_zotero_cache_survives_concurrent_writers(tmp_path):
    """サイドバーは status を同時に走らせる。一時ファイルを共有すると、片方の rename が失敗していた。"""
    import threading
    from priorwork.zotero import ZoteroClient
    z = ZoteroClient("1", "k", index_path=tmp_path / "zotero" / "index.json")
    errors = []

    def write(n):
        try:
            for _ in range(100):
                z._save_index({"version": n, "items": {}})
        except Exception as e:   # noqa: BLE001
            errors.append(e)
    threads = [threading.Thread(target=write, args=(n,)) for n in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert not errors and z._load_index()["version"] in range(4)
    assert not list((tmp_path / "zotero").glob("*.tmp"))


class FieldClient(ManyClient):
    """S2 の分野付きで返す検索（医学だけ・分野なし・政治学）。"""

    def search(self, query, limit=20, year=None, bulk=False):
        out = []
        for i, fields in enumerate([["Medicine"], [], ["Political Science", "Computer Science"]]):
            rec = from_s2(s2_paper(title=f"Statutory text paper number {i}", doi=f"10.1/f{i}"))
            rec["fields"] = fields
            out.append(rec)
        return out


def test_a_new_survey_leaves_out_papers_outside_the_social_sciences(ws, monkeypatch, capsys):  # noqa: F811
    monkeypatch.setattr(cli, "LiteratureClient", FieldClient)
    ws("new", "t", "--slug", "soc", "--json")
    capsys.readouterr()
    cli.main(["search", "statutes", "--into", "soc", "--json"])
    out = capsys.readouterr()
    assert "Medicine" in out.err
    assert sorted(e["record"]["title"][-1] for e in ws("list", "soc", "--json")) == ["1", "2"]
    ws("scope", "soc", "--search-field", "all", "--json")
    assert len(ws("search", "statutes", "--into", "soc", "--json")["added"]) == 3


# ---------------- Zotero への書き込み（ZOTERO_WRITE=1 のときだけ） ----------------

class FakeZoteroServer:
    """Zotero の Web API の書き込みの部分。書いたものは z の一覧（_index）にも映す。"""

    def __init__(self, z, can_write=True):
        self.z, self.can_write, self.calls = z, can_write, []
        self.version = 10
        self.items = {k: {"key": k, "version": 3, "data": {"key": k, "collections": list(i["collections"])}}
                      for k, i in z._index["items"].items()}

    def __call__(self, method, url, params=None, headers=None, auth=None, timeout=None, stream=False, json=None):
        self.calls.append((method, url.replace(zotero.API_BASE, ""), json))
        path = url.replace(zotero.API_BASE, "")
        if path == "/keys/current":
            return FakeResponse(200, {"access": {"user": {"library": True, "write": self.can_write}}})
        key = path.rsplit("/", 1)[-1]
        if method == "GET":
            return FakeResponse(200, self.items[key]) if key in self.items else FakeResponse(404, {})
        self.version += 1
        if method == "POST":
            done = {}
            for n, data in enumerate(json):
                k = f"NEW{self.version}{n}"
                self.items[k] = {"key": k, "version": self.version, "data": {**data, "key": k}}
                self.z._index["items"][k] = {"key": k, "itemType": data["itemType"], "title": data["title"],
                                             "doi": data.get("DOI", ""), "parentItem": "", "contentType": "",
                                             "linkMode": "", "filename": "", "year": data.get("date", ""),
                                             "collections": data["collections"]}
                done[str(n)] = {"key": k, "version": self.version}
            return FakeResponse(200, {"successful": done, "failed": {}})
        item = self.items[key]
        assert headers["If-Unmodified-Since-Version"] == str(item["version"])
        item["data"].update(json)
        item["version"] = self.version
        if json.get("deleted"):
            self.z._index["items"].pop(key)
        else:
            self.z._index["items"][key]["collections"] = item["data"]["collections"]
        return FakeResponse(204, None, {"Last-Modified-Version": str(self.version)})

    def writes(self):
        return [(m, p, b) for m, p, b in self.calls if m != "GET"]


class FakeResponse:
    def __init__(self, status, body, headers=None):
        self.status_code, self.ok, self._body, self.headers, self.text = status, status < 400, body, headers or {}, ""

    def json(self):
        return self._body


def test_adding_the_included_papers_to_the_collection_and_undoing_it(ws, tmp_path, monkeypatch, capsys):  # noqa: F811
    z = fake_zotero(tmp_path)
    monkeypatch.setattr(cli.ZoteroClient, "from_env", classmethod(lambda cls: z))
    server = FakeZoteroServer(z)
    monkeypatch.setattr(zotero.requests, "request", server)

    class Client(ManyClient):
        def search(self, query, limit=20, year=None, bulk=False):
            return [from_openalex(openalex_work(title=f"Paper number {i} on minimum wages", doi=f"10.1/{i}",
                                                wid=f"W{i}", citations=100 - i)) for i in range(3)]

    monkeypatch.setattr(cli, "LiteratureClient", Client)
    ws("new", "t", "--slug", "mw", "--json")
    ws("search", "x", "--into", "mw", "--json")
    ws("include", "mw", "1", "2", "3", "--json")
    ws("zotero", "mw", "--collection", "make-or-buy", "--json")

    # 設定で許していなければ書かない（何をするかを見るだけならできる）
    with pytest.raises(SystemExit, match="ZOTERO_WRITE=1"):
        cli.main(["zotero", "mw", "--add"])
    plan = ws("zotero", "mw", "--add", "--dry-run", "--json")
    assert [(w["number"], w["action"]) for w in plan["written"]] == [(2, "collect"), (3, "create")]
    assert plan["dry_run"] and not plan["can_write"] and not server.writes()
    capsys.readouterr()
    cli.main(["zotero", "mw", "--add", "--dry-run"])
    out = capsys.readouterr().out
    assert "まだ何も書いていません" in out and "#3 新規（書誌から作成）" in out and "#2 ライブラリにあるアイテム" in out
    steps = {s["id"]: s for s in ws("status", "mw", "--json")["next"]}
    assert steps["zotero"]["args"][2:] == [] and steps["wait_zotero"]["args"][-1] == "--dois"

    # 許していても、キーに書き込みの権限が無ければ書かない
    monkeypatch.setenv("ZOTERO_WRITE", "1")
    z.write = True
    server.can_write = False
    with pytest.raises(SystemExit, match="Allow write access"):
        cli.main(["zotero", "mw", "--add"])
    assert not server.writes()
    server.can_write = True

    detail = ws("status", "mw", "--json")
    steps = {s["id"]: s for s in detail["next"]}
    assert detail["zotero_write"] and steps["zotero"]["args"][2:] == ["--add"]
    assert steps["wait_zotero"]["args"][2:] == ["--add", "--dry-run"]   # 標準: 見せて了解を得てから

    added = ws("zotero", "mw", "--add", "--json")
    assert [(w["number"], w["action"], w["done"]) for w in added["written"]] == [(2, "collect", True), (3, "create", True)]
    assert added["missing_dois"] == []
    (post,) = [b for m, p, b in server.writes() if m == "POST"]
    assert post[0]["itemType"] == "journalArticle" and post[0]["DOI"] == "10.1/2" and post[0]["collections"] == ["C1"]
    assert post[0]["creators"][0] == {"creatorType": "author", "firstName": "Doruk", "lastName": "Cengiz"}
    patches = [(p, b) for m, p, b in server.writes() if m == "PATCH"]
    assert patches == [("/users/1/items/B", {"collections": ["C1"]})]        # ほかのアイテムの中身は書き換えない
    assert ws("status", "mw", "--json")["zotero_written"] == 2

    server.calls.clear()   # もう一度実行しても、二重には入れない
    assert ws("zotero", "mw", "--add", "--json")["written"] == [] and not server.writes()

    # 作ったアイテムは、手が入っていなければごみ箱へ
    created = added["written"][1]["key"]
    undone = ws("zotero", "mw", "--undo", "3", "--json")
    assert [(w["number"], w["undo"]) for w in undone["written"]] == [(3, "trash")]
    assert server.items[created]["data"]["deleted"] == 1 and ws("status", "mw", "--json")["zotero_written"] == 1

    # 作り直したアイテムにユーザーが手を入れたら残し、足しただけのアイテムはコレクションから外す
    again = ws("zotero", "mw", "--add", "--json")["written"]
    server.items[again[0]["key"]]["version"] += 5
    undone = ws("zotero", "mw", "--undo", "--json")
    assert sorted((w["number"], w["undo"]) for w in undone["written"]) == [(2, "uncollect"), (3, "keep")]
    assert server.items["B"]["data"]["collections"] == [] and "deleted" not in server.items[again[0]["key"]]["data"]
    assert ws("status", "mw", "--json")["zotero_written"] == 0
    assert ws("zotero", "mw", "--undo", "--json")["written"] == []


def test_reading_never_writes_without_the_setting(tmp_path, monkeypatch):
    z = fake_zotero(tmp_path)
    monkeypatch.setattr(zotero.requests, "request", FakeZoteroServer(z))
    with pytest.raises(ZoteroError):
        z._patch("B", 3, {"collections": []})
    assert zotero.item_from_record({"title": "A chapter", "authors": ["Plato"], "year": 2001, "doi": "10.1/c",
                                    "publication_types": ["book-chapter"], "journal_name": "A Book"}, ["C1"]) == {
        "itemType": "bookSection", "title": "A chapter", "creators": [{"creatorType": "author", "name": "Plato"}],
        "date": "2001", "bookTitle": "A Book", "extra": "DOI: 10.1/c", "collections": ["C1"]}
