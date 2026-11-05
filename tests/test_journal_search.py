"""誌を指定した検索（--journal）: S2 が誌名を持たない論文を OpenAlex で補うこと、
プレプリントの DOI を雑誌版に替えること。ネットには出ない（S2・OpenAlex の応答は下の固定データ）。"""

import pytest

from priorwork import cli
from priorwork.api import ApiError, LiteratureClient, from_s2, in_journals

from .conftest import openalex_work, s2_paper
from .test_search_zotero import ws  # noqa: F401

JPART = "Journal of Public Administration Research and Theory"
AJPS = "American Journal of Political Science"

# S2 で JPART を venue で絞ると出てくる論文（誌名が付いているもの）
S2_JPART = [
    s2_paper(title="Bureaucratic Discretion and Administrative Burden in Street-Level Work", doi="10.1093/jopart/muz001",
             journal=JPART, year=2019, citations=150, paperId="b" * 40),
    s2_paper(title="Racialized Burdens: Applying Racialized Organization Theory to the Administrative State",
             doi="10.31235/osf.io/q3xb8", journal=JPART, year=2022, citations=120, paperId="c" * 40,
             authors=("Victor Ray", "Pamela Herd", "Donald Moynihan")),
]
# S2 の Moynihan, Herd & Harvey (2014) は venue が ""・publicationVenue が null。venue での絞り込みから落ちる
S2_MOYNIHAN = s2_paper(title="Administrative Burden: Learning, Psychological, and Compliance Costs in Citizen-State "
                             "Interactions", doi="10.1093/jopart/muu009", journal="", year=2014, citations=900,
                       venue="", publicationVenue=None)
S2_MOYNIHAN["journal"] = None

# OpenAlex を JPART の source ID で絞った検索の結果
OA_JPART = [
    openalex_work(title="Administrative Burden: Learning, Psychological, and Compliance Costs in Citizen-State "
                        "Interactions", doi="10.1093/jopart/muu009", journal=JPART, issns=("1053-1858",), year=2014,
                  wid="W2014", citations=1085, authors=("Donald Moynihan", "Pamela Herd", "Hope Harvey")),
    openalex_work(title="The Bite of Administrative Burden: A Theoretical and Empirical Investigation",
                  doi="10.1093/jopart/muv034", journal=JPART, issns=("1053-1858",), year=2015, wid="W2015",
                  citations=307, authors=("Carolyn J. Heinrich",)),
    openalex_work(title="Bureaucratic Discretion and Administrative Burden in Street-Level Work",
                  doi="10.1093/jopart/muz001", journal=JPART, issns=("1053-1858",), year=2019, wid="W2019",
                  citations=160),
]
# DOI の照合で OpenAlex が知っている work（プレプリントの DOI は SocArXiv のリポジトリ）
OA_BY_DOI = OA_JPART + [
    openalex_work(title="Racialized Burdens: Applying Racialized Organization Theory to the Administrative State",
                  doi="10.31235/osf.io/q3xb8", journal="SocArXiv", issns=(), source_type="repository",
                  work_type="preprint", year=2021, wid="WPRE"),
]
# 題名で引いたときの雑誌版
RAY_JOURNAL = openalex_work(title="Racialized Burdens: Applying Racialized Organization Theory to the Administrative State",
                            doi="10.1093/jopart/muac001", journal=JPART, issns=("1053-1858",), year=2023, wid="WRAY",
                            citations=130, authors=("Victor Ray", "Pamela Herd", "Donald Moynihan"))


class FakeClient(LiteratureClient):
    """S2 と OpenAlex の応答を固定データで返す。fail=True なら OpenAlex はすべて失敗する。"""

    def __init__(self, s2=(), search=(), by_doi=(), titles=None, fail=False):
        super().__init__(use_cache=False)
        self.s2_data, self.search_works, self.by_doi = list(s2), list(search), list(by_doi)
        self.titles = titles or {}
        self.fail = fail
        self.s2_params, self.oa_calls = {}, []

    def _s2(self, path, params):
        self.s2_params = params
        return {"data": self.s2_data}

    def _openalex(self, path, params):
        self.oa_calls.append((path, params))
        if self.fail:
            raise ApiError("OpenAlex", "HTTP 503: unavailable", 503)
        f = params.get("filter", "")
        if f.startswith("doi:"):
            wanted = set(f[4:].split("|"))
            return {"results": [w for w in self.by_doi if w["doi"].replace("https://doi.org/", "").lower() in wanted]}
        if f.startswith("title.search:"):
            title = f.split(",")[0][len("title.search:"):]
            return {"results": [w for key, works in self.titles.items() if key in title for w in works]}
        if "title_and_abstract.search:" in f:
            return {"results": self.search_works}
        return {"results": []}


def searched(client):
    return [p for path, p in client.oa_calls if "title_and_abstract.search:" in p.get("filter", "")]


def test_s2_drops_a_paper_whose_venue_is_empty():
    # S2 は誌名の空のレコードを venue での絞り込みに入れない。入っても、誌名で確かめると落ちる
    rec = from_s2(S2_MOYNIHAN)
    assert rec["journal_name"] == "" and not in_journals(rec, [JPART])
    c = FakeClient(s2=S2_JPART, by_doi=OA_BY_DOI, fail=True)
    titles = [r["title"] for r in c.search("administrative burden", limit=5, bulk=True, journals=[JPART])]
    assert not any(t.startswith("Administrative Burden: Learning") for t in titles)


def test_openalex_fills_in_what_s2_missed(capsys):
    c = FakeClient(s2=S2_JPART, search=OA_JPART, by_doi=OA_BY_DOI, titles={"Racialized Burdens": [RAY_JOURNAL]})
    out = c.search("administrative burden", limit=5, year="2013-2022", bulk=True, journals=[JPART])
    [call] = searched(c)
    # 誌は名前でなく source ID で、年と語も filter に入れる。bulk なら被引用数順
    assert call["filter"] == ("primary_location.source.id:S169433491,publication_year:2013-2022,"
                              "title_and_abstract.search:administrative burden")
    assert call["sort"] == "cited_by_count:desc"
    dois = [r["doi"] for r in out]
    assert dois[:2] == ["10.1093/jopart/muu009", "10.1093/jopart/muv034"]      # 被引用数で並べ直した
    assert len(dois) == len(set(dois)) == 4                                     # DOI で重複を除いた
    found = {r["doi"]: r["found_in"] for r in out}
    assert found["10.1093/jopart/muu009"] == ["OpenAlex"]
    assert found["10.1093/jopart/muz001"] == ["SemanticScholar", "OpenAlex"]    # 両方で見つかった
    assert c.last_search["openalex"] == "used" and c.last_search["sources"] == {JPART: "S169433491"}


def test_relevance_order_keeps_s2_and_puts_the_rest_at_their_openalex_rank():
    c = FakeClient(s2=S2_JPART, search=OA_JPART, by_doi=OA_BY_DOI)
    out = c.search("administrative burden", limit=5, journals=[JPART])
    assert "sort" not in searched(c)[0]
    # S2: Discretion, Racialized。OpenAlex: Moynihan（1位）, Bite（2位）, Discretion（3位、S2 と同じ）
    assert [r["title"].split()[0] for r in out] == ["Bureaucratic", "Administrative", "Racialized", "The"]
    assert [r["found_in"] for r in out] == [["SemanticScholar", "OpenAlex"], ["OpenAlex"], ["SemanticScholar"],
                                            ["OpenAlex"]]


def test_with_journals_the_ssci_status_does_not_reorder(ws, monkeypatch, capsys):  # noqa: F811
    """OpenAlex で補った論文は ISSN が揃い SSCI 判定が上がりやすい。誌を指定したら判定では並べない。"""
    papers = [dict(from_s2(p), found_in=["SemanticScholar"]) for p in S2_JPART[:1]]
    papers[0]["ssci"] = dict(papers[0]["ssci"], tier=3)
    oa = dict(from_s2(S2_JPART[0]), title="Another paper on administrative burden in JPART", doi="10.1093/x",
              found_in=["OpenAlex"])
    oa["ssci"] = dict(oa["ssci"], tier=5)
    assert [p["doi"] for p in cli.rank_and_filter(papers + [oa], sort="relevance")][0] == "10.1093/x"
    assert [p["doi"] for p in cli.rank_and_filter(papers + [oa], sort="relevance", by_tier=False)][0] == \
        papers[0]["doi"]
    assert cli.found_in_label(oa) == " | 見つけた所: OpenAlex"
    assert cli.found_in_label(dict(oa, found_in=["SemanticScholar", "OpenAlex"])) == " | 見つけた所: S2 + OpenAlex"


def test_a_preprint_doi_is_replaced_with_the_journal_version():
    c = FakeClient(s2=S2_JPART, by_doi=OA_BY_DOI, titles={"Racialized Burdens": [RAY_JOURNAL]})
    [_, ray] = c._verify_with_openalex([from_s2(p) for p in S2_JPART])
    assert ray["doi"] == "10.1093/jopart/muac001" and ray["preprint_doi"] == "10.31235/osf.io/q3xb8"
    assert ray["journal_name"] == JPART and ray["year"] == 2023 and ray["verified"]
    assert not ray["warnings"]
    assert ray["notes"] == ["プレプリント・WP の DOI 10.31235/osf.io/q3xb8 を雑誌版 10.1093/jopart/muac001 に替えました"]
    # 題名の照会には誌の source ID も添える
    [title_call] = [p for _, p in c.oa_calls if p["filter"].startswith("title.search:")]
    assert "primary_location.source.id:S169433491" in title_call["filter"]


def test_an_unknown_doi_is_replaced_when_the_journal_version_matches():
    broockman = s2_paper(title="Does Affective Polarization Undermine Democratic Norms or Accountability? Maybe Not",
                         doi="10.31219/osf.io/9btsq", journal=AJPS, year=2022)
    journal = openalex_work(title="Does Affective Polarization Undermine Democratic Norms or Accountability? Maybe Not",
                            doi="10.1111/ajps.12719", journal=AJPS, issns=("0092-5853",), year=2023, wid="WBKW")
    c = FakeClient(titles={"Does Affective Polarization": [journal]})          # OpenAlex は OSF の DOI を知らない
    [out] = c._verify_with_openalex([from_s2(broockman)])
    assert out["doi"] == "10.1111/ajps.12719" and out["preprint_doi"] == "10.31219/osf.io/9btsq"
    assert not out["warnings"]


def test_no_match_keeps_the_doi_and_the_warning():
    broockman = s2_paper(title="Does Affective Polarization Undermine Democratic Norms or Accountability? Maybe Not",
                         doi="10.31219/osf.io/9btsq", journal=AJPS, year=2022)
    other = [openalex_work(title="Does Affective Polarization Undermine Democratic Norms or Accountability? A Reply",
                           doi="10.1111/ajps.99999", journal=AJPS, year=2023),
             openalex_work(title="Does Affective Polarization Undermine Democratic Norms or Accountability? Maybe Not",
                           doi="10.1111/ajps.88888", journal=AJPS, year=2010)]          # 年が離れすぎ
    c = FakeClient(titles={"Does Affective Polarization": other})
    [out] = c._verify_with_openalex([from_s2(broockman)])
    assert out["doi"] == "10.31219/osf.io/9btsq" and "preprint_doi" not in out and not out["notes"]
    assert out["warnings"] == ["OpenAlex に DOI が見つからない（DOI 要確認）"]


def test_lookups_for_journal_versions_are_capped(monkeypatch, capsys):
    from priorwork import api
    monkeypatch.setattr(api, "MAX_VERSION_LOOKUPS", 2)
    papers = [s2_paper(title=f"A Paper Number {i} About Administrative Burden", doi=f"10.31235/osf.io/x{i}",
                       journal=JPART, paperId=str(i) * 40) for i in range(5)]
    c = FakeClient()
    c._verify_with_openalex([from_s2(p) for p in papers])
    assert sum(1 for _, p in c.oa_calls if p["filter"].startswith("title.search:")) == 2
    assert "残り 3 件" in capsys.readouterr().err


def test_when_openalex_fails_only_the_s2_results_are_returned(capsys):
    c = FakeClient(s2=S2_JPART, fail=True)
    out = c.search("administrative burden", limit=5, bulk=True, journals=[JPART])
    assert [r["doi"] for r in out] == [p["externalIds"]["DOI"] for p in S2_JPART]
    assert c.last_search == {"openalex": "failed"}
    assert "S2 の結果だけを返します" in capsys.readouterr().err


def test_without_journals_openalex_is_not_searched():
    c = FakeClient(s2=S2_JPART, search=OA_JPART, by_doi=OA_BY_DOI)
    c.search("administrative burden", limit=5, bulk=True)
    assert not searched(c) and c.last_search == {}


def test_a_journal_not_in_the_table_is_looked_up_by_name_or_issn():
    class Sources(FakeClient):
        def _openalex(self, path, params):
            if path == "/sources":
                return {"results": [{"id": "https://openalex.org/S1", "display_name": "Governance"},
                                    {"id": "https://openalex.org/S2", "display_name": "Governance: An International Journal",
                                     "alternate_titles": ["Governance, An International Journal"]}]}
            if path == "/sources/issn:0952-1895":
                return {"id": "https://openalex.org/S3"}
            return super()._openalex(path, params)
    c = Sources()
    assert c.journal_source_ids(["Governance, An International Journal", "0952-1895", "Nowhere Review"]) == {
        "Governance, An International Journal": "S2", "0952-1895": "S3"}


def test_search_into_a_survey_logs_the_openalex_part(ws, monkeypatch, capsys):  # noqa: F811
    client = FakeClient(s2=S2_JPART, search=OA_JPART, by_doi=OA_BY_DOI, titles={"Racialized Burdens": [RAY_JOURNAL]})
    monkeypatch.setattr(cli, "LiteratureClient", lambda *a, **kw: client)
    ws("new", "t", "--slug", "burden", "--json")
    capsys.readouterr()
    cli.main(["search", "administrative burden", "--into", "burden", "--journal", JPART, "--year", "2013-2022",
              "--limit", "5", "--bulk", "--json"])
    err = capsys.readouterr().err
    assert "S2 の検索に出なかった 2 件を OpenAlex から足しました" in err
    entries = {e["record"]["doi"]: e["record"] for e in ws("list", "burden", "--json")}
    assert {"10.1093/jopart/muu009", "10.1093/jopart/muv034", "10.1093/jopart/muac001"} <= set(entries)
    assert entries["10.1093/jopart/muu009"]["found_in"] == ["OpenAlex"]
    assert entries["10.1093/jopart/muac001"]["preprint_doi"] == "10.31235/osf.io/q3xb8"
    from priorwork.survey import Survey
    log = Survey.load("burden").data["searches"][-1]["params"]
    assert log["journals"] == JPART and log["openalex"] == "used" and log["openalex_added"] == 2


@pytest.mark.parametrize("year,expected", [("2019", "publication_year:2019"), ("2013-2022", "publication_year:2013-2022"),
                                           ("2013-", "publication_year:>2012"), ("-2022", "publication_year:<2023"),
                                           (None, "")])
def test_years_for_openalex(year, expected):
    from priorwork.api import openalex_years
    assert openalex_years(year) == expected
