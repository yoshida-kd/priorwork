"""検索の件数（深さで変わる既定）・bulk のクエリの直し・Zotero のコレクション。"""

import pytest

from priorwork import cli, zotero
from priorwork.api import bulk_query, from_openalex
from priorwork.zotero import ZoteroClient, ZoteroError

from .conftest import openalex_work
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


def test_link_a_collection_import_and_list_dois(ws, tmp_path, monkeypatch, capsys):  # noqa: F811
    z = fake_zotero(tmp_path)
    monkeypatch.setattr(zotero.ZoteroClient, "from_env", classmethod(lambda cls: z))
    monkeypatch.setattr(cli.ZoteroClient, "from_env", classmethod(lambda cls: z))

    class Client(ManyClient):
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
