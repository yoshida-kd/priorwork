"""実際のサーベイ（公務員の給与）で見つかった不具合: render の冪等性、check の数値とページ、WP 版と掲載版をまとめた
OpenAlex の work、fix の誌名とページ、姓の前置詞。"""
import pytest

from priorwork import check, derived, fulltext, ssci
from priorwork.api import LiteratureClient, from_openalex, from_s2
from priorwork.survey import INCLUDED, Survey, author_short, display_surname

from .conftest import openalex_work, s2_paper


@pytest.fixture
def survey(tmp_path):
    return Survey.create("t", "t", {}, reports_dir=tmp_path / "r", state_dir=tmp_path / "s", lang="en")


def included(s, **kw):
    e, _ = s.upsert(from_openalex(openalex_work(**kw)), "search")
    s.set_status([e["number"]], INCLUDED)
    return e


def test_render_does_not_repeat_the_notes_under_a_card(survey):
    e = included(survey)
    e["record"]["notes"].append("Replaced the preprint / working-paper DOI 10.3386/w1 with the journal version 10.1/abc")
    survey.render()
    survey.set_card(e["number"], {"rq": "Why?"})
    survey.render()
    md = survey.md_path.read_text(encoding="utf-8")
    assert md.count("ℹ️ Replaced") == 1 and "Why?" in md
    assert not survey.render()   # 冪等


def test_render_repairs_notes_that_were_repeated_before(survey):
    e = included(survey)
    e["record"]["notes"].append("A note")
    survey.render()
    md = survey.md_path.read_text(encoding="utf-8")
    survey.md_path.write_text(md.replace("- ℹ️ A note\n", "- ℹ️ A note\n" * 50), encoding="utf-8")
    survey.render()
    assert survey.md_path.read_text(encoding="utf-8").count("ℹ️ A note") == 1


def test_a_decimal_point_does_not_end_a_sentence():
    sentences = derived._SENTENCE.findall("Scores rose by 0.27 standard deviations (Dee & Wyckoff (2015)). Next one.")
    assert sentences[0].startswith("Scores rose by 0.27 standard deviations")


@pytest.mark.parametrize("text", ["(p. F117)", "(pp. S117-S120)", "(p. E244)", "(p. 12)"])
def test_pages_with_a_letter_are_pages(text):
    assert check._PAGE_RE.search(text)
    assert not check._card_numbers(f"the effect was 117 percent {text}") - {"117"}


def test_journal_pages_with_a_letter():
    assert fulltext.journal_pages({"pages": "F107-F130"}) == (107, 130)


@pytest.mark.parametrize("text, number", [
    ("a sample of 10 943 workers", "10943"),
    ("a sample of 10,943 workers", "10943"),
    ("cut by35,000federal jobs", "35000"),
])
def test_thousands_separators_in_the_full_text(text, number):
    assert number in check._text_numbers(text)


def test_separate_numbers_are_kept_when_spaced_like_thousands():
    found = check._text_numbers("in 2015 100 firms")
    assert {"2015", "100"} <= found


def merged_work(**kw):
    """OpenAlex が WP 版と掲載版を 1 つにまとめた work（DOI は WP 版、所在の先頭は掲載誌）。"""
    w = openalex_work(doi="10.2139/ssrn.2480321", journal="Labour Economics", issns=("0927-5371",), **kw)
    w["primary_location"]["landing_page_url"] = "https://doi.org/10.1016/j.labeco.2016.08.001"
    return w


def test_a_merged_work_takes_the_journal_doi():
    rec = from_openalex(merged_work())
    assert rec["doi"] == "10.1016/j.labeco.2016.08.001" and rec["preprint_doi"] == "10.2139/ssrn.2480321"
    assert rec["journal_name"] == "Labour Economics"


def test_a_work_whose_own_doi_is_the_journal_keeps_it():
    w = openalex_work(doi="10.1/abc")
    w["primary_location"]["landing_page_url"] = "https://doi.org/10.2139/ssrn.1"
    assert from_openalex(w)["doi"] == "10.1/abc"


class FakeOpenAlex(LiteratureClient):
    def __init__(self, works):
        super().__init__(use_cache=False)
        self.works = works

    def _openalex(self, path, params):
        return {"results": self.works}


def test_s2_journal_doi_is_found_through_the_merged_work():
    # S2 は掲載版の DOI に SSRN の誌名を付けて返した（Hospido & Moral-Benito 2016）
    rec = from_s2(s2_paper(doi="10.1016/J.LABECO.2016.08.001", journal="SSRN Electronic Journal"))
    [out] = FakeOpenAlex([merged_work()])._verify_with_openalex([rec])
    assert out["journal_name"] == "Labour Economics" and out["verified"]
    assert not any("OpenAlex" in w for w in out["warnings"])


def test_s2_working_paper_doi_becomes_the_journal_version():
    rec = from_s2(s2_paper(doi="10.2139/ssrn.2480321", journal="Labour Economics"))
    [out] = FakeOpenAlex([merged_work()])._verify_with_openalex([rec])
    assert out["doi"] == "10.1016/j.labeco.2016.08.001" and out["preprint_doi"] == "10.2139/ssrn.2480321"
    assert any("10.2139/ssrn.2480321" in n for n in out["notes"])


def test_fix_corrects_the_journal_and_the_pages(survey):
    e = included(survey, journal="SSRN Electronic Journal", issns=("1556-5068",), source_type="repository")
    survey.fix_record(e["number"], journal_name="Labour Economics", pages="145 – 159")
    r = e["record"]
    assert r["journal_name"] == "Labour Economics" and r["pages"] == "145-159" and r["issns"] == []
    assert r["ssci"]["status"] != ssci.PREPRINT
    # 書誌を差し替えても、手で直した誌名とページは残る
    survey.replace_record(e, from_openalex(openalex_work(journal="SSRN Electronic Journal")))
    assert e["record"]["journal_name"] == "Labour Economics" and e["record"]["pages"] == "145-159"


@pytest.mark.parametrize("name, shown", [
    ("Ernesto Dal Bó", "Dal Bó"),
    ("Rafael Di Tella", "Di Tella"),
    ("Jacques van der Gaag", "van der Gaag"),
    ("Caroline Van Rijckeghem", "Van Rijckeghem"),
    ("Joppe de Ree", "de Ree"),
    ("J. Ignacio García-Pérez", "García-Pérez"),
])
def test_particles_from_the_survey(name, shown):
    assert display_surname(name) == shown


def test_author_short_keeps_the_particle():
    assert author_short(["Ernesto Dal Bó", "F. Finan", "M. Rossi"]) == "Dal Bó et al."
