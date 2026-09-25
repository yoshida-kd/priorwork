import sqlite3

import pytest

from priorwork import cli
from priorwork.api import from_openalex
from priorwork.check import ERROR, WARN, check_survey, find_citations
from priorwork.fulltext import find_zotero_pdf
from priorwork.survey import INCLUDED, Survey

from .conftest import openalex_work


def test_find_citations():
    text = ("Acemoglu et al. (2001) と Card and Krueger (1994)、（Dell, 2010）、"
            "van Dijk (2015) を参照。Acemoğlu, Johnson & Robinson (2001)")
    assert {(c.name, c.year) for c in find_citations(text)} == {("acemoglu", 2001), ("card", 1994), ("dell", 2010),
                                                                ("dijk", 2015)}
    # 日本語に挟まれた略語・年代を引用と誤認しない
    assert [(c.name, c.year) for c in find_citations("歴史的IVの台頭（2000年代）。死亡率IV、Dell (2010) など")] == [("dell", 2010)]


@pytest.fixture
def included_survey(s2_record):
    s = Survey.create("t", "check", {})
    e, _ = s.upsert(s2_record(authors=("Daron Acemoğlu", "Simon Johnson"), year=2001, doi="10.1/ajr"), "search",
                    status=INCLUDED)
    s.save()
    s.render()
    return s, e


def test_check_flags_unregistered_citations_and_unfilled_cards(included_survey):
    s, e = included_survey
    md = s.md_path.read_text().replace(
        "## 1. 研究の背景と中心的な論点\n",
        "## 1. 研究の背景と中心的な論点\nAcemoglu et al. (2001) に対し Glaeser et al. (2004) が反論 https://doi.org/10.9999/fake\n")
    s.md_path.write_text(md)
    findings = check_survey(s)
    errors = [m for lvl, m in findings if lvl == ERROR]
    assert any("Glaeser et al. (2004)" in m for m in errors)
    assert not any("Acemoglu et al. (2001)" in m for m in errors)  # アクセント付きの著者名でも照合できる
    assert any("10.9999/fake" in m for m in errors)
    assert any("未確認" in m for lvl, m in findings if lvl == WARN)


def test_check_detects_drift(included_survey):
    s, e = included_survey
    s.set_status([e["number"]], "excluded", "x")
    s.save()  # render していない
    assert any("priorwork render" in m for _, m in check_survey(s))


def test_check_verifies_doi_titles_online(included_survey):
    s, _ = included_survey

    class Client:
        def openalex_works(self, dois=(), openalex_ids=(), select=""):
            return [{"doi": "https://doi.org/10.1/ajr", "title": "Something else entirely"}]

    assert any("別タイトル" in m for lvl, m in check_survey(s, Client()) if lvl == ERROR)


def test_find_zotero_pdf(tmp_path):
    db = sqlite3.connect(tmp_path / "zotero.sqlite")
    db.executescript("""
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT);
        CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE itemData (itemID INT, fieldID INT, valueID INT);
        CREATE TABLE itemAttachments (itemID INT, parentItemID INT, contentType TEXT, path TEXT);
        INSERT INTO items VALUES (1, 'PARENT01'), (2, 'ATTACH01');
        INSERT INTO fields VALUES (26, 'DOI');
        INSERT INTO itemDataValues VALUES (7, '10.1257/AER.91.5.1369');
        INSERT INTO itemData VALUES (1, 26, 7);
        INSERT INTO itemAttachments VALUES (2, 1, 'application/pdf', 'storage:ajr.pdf');
    """)
    db.commit()
    db.close()
    pdf = tmp_path / "storage" / "ATTACH01" / "ajr.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4")
    assert find_zotero_pdf("10.1257/aer.91.5.1369", tmp_path) == pdf
    assert find_zotero_pdf("10.1/other", tmp_path) is None


def test_rank_and_filter(s2_record, oa_record):
    wp = oa_record(title="Same paper title for ranking", doi="10.2139/ssrn.9", journal="SSRN Electronic Journal",
                   source_type="repository", work_type="preprint", citations=999)
    pub = s2_record(title="Same paper title for ranking", doi="10.1/pub", journal="American Economic Review", citations=10)
    other = s2_record(title="An unrelated but highly cited paper", doi="10.1/x", journal="Some Journal", citations=500)
    out = cli.rank_and_filter([wp, other, pub])
    assert [p["doi"] for p in out] == ["10.1/pub", "10.1/x"]  # WP は統合・除外、SSCI 推定誌が先
    assert [p["doi"] for p in cli.rank_and_filter([wp, other, pub], ssci_only=True)] == ["10.1/pub"]


def test_cli_interactive_flow(monkeypatch, capsys):
    class FakeClient:
        def __init__(self, use_cache=True):
            pass

        def search(self, query, limit=20, year=None, bulk=False):
            return [from_openalex(openalex_work(title=f"Paper number {i} on minimum wages", doi=f"10.1/{i}",
                                                wid=f"W{i}", citations=100 - i)) for i in range(3)]

        def openalex_works(self, dois=(), openalex_ids=(), select=""):
            if "referenced_works" in select:
                return [openalex_work(doi=d, wid=f"W{d[-1]}", referenced=["W90", "W91"]) for d in dois]
            return [openalex_work(title=f"Cited classic {w}", doi=f"10.9/{w}", wid=w) for w in openalex_ids]

        def citing_work_ids(self, work_id, limit):
            return ["W90"]

    monkeypatch.setattr(cli, "LiteratureClient", FakeClient)
    cli.main(["new", "最低賃金", "--slug", "mw"])
    cli.main(["search", "minimum wage", "--into", "mw", "--limit", "3"])
    cli.main(["include", "mw", "1", "2"])
    with pytest.raises(SystemExit):
        cli.main(["exclude", "mw", "3"])  # 理由なしの除外は拒否
    cli.main(["exclude", "mw", "3", "--reason", "対象外"])
    cli.main(["snowball", "mw", "--min-links", "1"])
    out = capsys.readouterr().out
    assert "#4 [新規候補] Cited classic W90" in out and "リンク数 4" in out

    s = Survey.load("mw")
    assert [e["status"] for e in s.papers] == ["included", "included", "excluded", "candidate", "candidate"]
    assert [q["kind"] for q in s.data["searches"]] == ["search", "snowball"]
    cli.main(["status", "mw"])
    assert "次にやること" in capsys.readouterr().out
