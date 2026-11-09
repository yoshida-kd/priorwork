"""実際のサーベイの改善メモ（6 章）から: 姓の前置詞、ハイフン、題名の改行、複数の PDF、Zotero の重複。"""
import pytest

from priorwork import check, fulltext
from priorwork.api import from_openalex
from priorwork.export import octavo_citations, unconverted_citations
from priorwork.survey import INCLUDED, Survey, author_short, display_surname, split_name, surname
from priorwork.zotero import ZoteroClient

from .conftest import openalex_work


@pytest.mark.parametrize("name, shown, key", [
    ("Andrew H. Van de Ven", "Van de Ven", "ven"),
    ("Arjen van Witteloostuijn", "van Witteloostuijn", "witteloostuijn"),
    ("Van de Ven, Andrew H.", "Van de Ven", "ven"),
    ("Robert E. Lucas Jr.", "Lucas", "lucas"),
    ("Robert E. Lucas, Jr.", "Lucas", "lucas"),
    ("Van Morrison", "Morrison", "morrison"),              # 最初の語は名
    ("Rafael La Porta", "La Porta", "porta"),
    ("Xavier Fernández‐i‐Marín", "Fernández‐i‐Marín", "fernandez-i-marin"),
    ("RECOVERY Collaborative Group", "RECOVERY Collaborative Group", "group"),
])
def test_surnames(name, shown, key):
    assert display_surname(name) == shown and surname(name) == key


def test_a_capitalised_name_in_the_middle_is_not_a_particle():
    assert display_surname("Thi Le Nguyen") == "Nguyen"
    assert split_name("Drazin, Robert") == ("Robert", "Drazin")


@pytest.fixture
def survey(tmp_path):
    return Survey.create("t", "t", {}, reports_dir=tmp_path / "r", state_dir=tmp_path / "s", lang="en")


def add(s, title, authors, year, doi):
    e, _ = s.upsert(from_openalex(openalex_work(title=title, authors=authors, year=year, doi=doi, wid="W" + doi[-1])), "search")
    s.set_status([e["number"]], INCLUDED)
    return e


def test_particles_and_hyphens_become_keys(survey):
    add(survey, "Strategy and structure in firms today", ("Robert Drazin", "Andrew H. Van de Ven"), 1985, "10.1/a")
    add(survey, "Organizational ecology in a long view", ("Arjen van Witteloostuijn", "B", "C"), 2018, "10.1/b")
    add(survey, "Policy growth in the European countries", ("Xavier Fernández‐i‐Marín", "B", "C"), 2024, "10.1/c")
    assert author_short(survey.by_status(INCLUDED)[0]["record"]["authors"]) == "Drazin & Van de Ven"
    bib = [{"key": "drazin1985", "doi": "10.1/a", "title": "", "year": "1985"},
           {"key": "vw2018", "doi": "10.1/b", "title": "", "year": "2018"},
           {"key": "fim2024", "doi": "10.1/c", "title": "", "year": "2024"}]
    text, missing, _ = octavo_citations(
        "Drazin & Van de Ven (1985) and van Witteloostuijn et al. (2018) and Fernández‐i‐Marín et al. (2024) "
        "and (Fernandez-i-Marin et al., 2024) and Nobody (1999).", survey, bib)
    assert "@drazin1985" in text and "@vw2018" in text and text.count("fim2024") == 2 and not missing
    assert unconverted_citations(text) == ["Nobody (1999)"]


def test_two_group_authors_ending_in_the_same_word_are_told_apart(survey):
    add(survey, "A first randomised trial of one drug", ("RECOVERY Collaborative Group",), 2021, "10.1/a")
    add(survey, "A second randomised trial of another", ("PARADIGM Study Group",), 2021, "10.1/b")
    bib = [{"key": "rec", "doi": "10.1/a", "title": "", "year": "2021"}, {"key": "par", "doi": "10.1/b", "title": "", "year": "2021"}]
    text, _, _ = octavo_citations("RECOVERY Collaborative Group (2021) and PARADIGM Study Group (2021).", survey, bib)
    assert text == "@rec and @par."
    # どちらか分からないなら変換しない
    text, _, _ = octavo_citations("Group (2021) said so.", survey, bib)
    assert text == "Group (2021) said so." and unconverted_citations(text) == ["Group (2021)"]


def test_a_title_with_a_line_break_does_not_pile_up(survey):
    e = add(survey, "The politics of reorganization in\n Western Europe", ("A Author",), 2023, "10.1/a")
    assert e["record"]["title"] == "The politics of reorganization in Western Europe"
    e["record"]["title"] = "An older record with\n a line break in it"     # 前の版で登録された題名
    for _ in range(3):
        survey.save(), survey.render()
    md = survey.md_path.read_text(encoding="utf-8")
    assert md.count("a line break in it") <= 3 and "with\n a line" not in md
    assert not [m for _, m in check.check_survey(survey) if "does not match" in m]


def test_check_says_when_the_years_were_not_compared(survey):
    e = add(survey, "A paper with a volume and a year", ("A Author",), 2020, "10.1/a")

    class Client:
        issue_years_failed = True

        def openalex_works(self, dois=(), select=""):
            return [{"doi": "https://doi.org/10.1/a", "title": e["record"]["title"]}]

        def issue_years(self, dois):
            return {}
    survey.save(), survey.render()
    assert any("Crossref" in m for _, m in check.check_survey(survey, Client()))


@pytest.mark.parametrize("cover, expected", [
    ("NBER WORKING PAPER SERIES\nThe title", True),
    ("Accepted manuscript\nThe title", True),
    ("The Review of Economics\nThe title\n" + "x" * 900 + "Research Associate, NBER working paper 123", False),
    ("=== page 1 ===\nJournal\n=== page 2 ===\nworking paper", False),
])
def test_a_working_paper_is_told_from_its_cover(cover, expected):
    assert fulltext.working_paper_text(cover) is expected


def test_the_published_pdf_is_chosen(monkeypatch):
    texts = {b"wp": "DISCUSSION PAPER SERIES\n" + "x" * 900, b"pub": "The Journal\n" + "x" * 800, b"bad": None}

    def fake(pdf):
        if texts[pdf] is None:
            raise ValueError("broken")
        return texts[pdf], 10
    monkeypatch.setattr(fulltext, "extract_text", fake)
    assert fulltext.best_pdf([b"wp", b"pub"]) == 1
    assert fulltext.best_pdf([b"bad", b"wp"]) == 1


def test_a_duplicate_item_in_the_collection_counts(monkeypatch):
    z = ZoteroClient.__new__(ZoteroClient)
    a = {"key": "A", "doi": "10.1/x", "title": "T", "parentItem": "", "collections": [], "contentType": ""}
    b = dict(a, key="B", collections=["C"])
    monkeypatch.setattr(ZoteroClient, "index", {"items": {"A": a, "B": b}})
    z.prefer_collection = ""
    z._parents = lambda: [a, b]
    z.subtree = lambda key: {key}
    st = z.status({"doi": "10.1/x", "title": "T"}, "C")
    assert st["in_collection"] and st["key"] == "B"
    assert not z.status({"doi": "10.1/x", "title": "T"}, "D")["in_collection"]


class FakeZotero:
    write = True

    def __init__(self):
        self.inside = {}

    def find_collection(self, name):
        return {"key": name.upper(), "name": name}

    def plan_add(self, papers, collection):
        return [{"number": e["number"], "title": e["record"]["title"], "doi": e["record"]["doi"], "action": "collect",
                 "key": "ITEM"} for e in papers if e["number"] not in self.inside.get(collection, set())]

    def check_write_access(self):
        pass

    def add(self, plan, records, collection):
        for p in plan:
            self.inside.setdefault(collection, set()).add(p["number"])
            p.update(done=True, version=1)
        return plan

    def sync(self):
        pass

    def status(self, record, collection):
        return {"in_collection": bool(self.inside.get(collection))}


def test_add_goes_to_the_other_collection_too_and_is_recorded_once(survey):
    from priorwork.cli import zotero_add
    add(survey, "A paper with a volume and a year", ("A Author",), 2020, "10.1/a")
    survey.data["zotero_collection"] = {"key": "OURS", "name": "ours"}
    z = FakeZotero()
    assert {p["collection_name"] for p in zotero_add(survey, z, [INCLUDED], True, ["theirs"])} == {"ours", "theirs"}
    assert not z.inside                                               # --dry-run は書かない
    zotero_add(survey, z, [INCLUDED], False, ["theirs"])
    assert z.inside == {"OURS": {1}, "THEIRS": {1}}
    assert {w["collection"] for w in survey.zotero_written} == {"OURS", "THEIRS"}
    assert zotero_add(survey, z, [INCLUDED], False, ["theirs"]) == []  # 2 回目は何もしない
    assert len(survey.zotero_written) == 2
