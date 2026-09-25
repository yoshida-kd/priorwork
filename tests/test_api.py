import pytest

from priorwork import ssci
from priorwork.api import ApiError, LiteratureClient, from_s2, parse_identifier

from .conftest import openalex_work, s2_paper


@pytest.mark.parametrize("raw,type_,value", [
    ("10.1257/aer.91.5.1369", "doi", "10.1257/aer.91.5.1369"),
    ("https://doi.org/10.1162/003355300554881", "doi", "10.1162/003355300554881"),
    ("doi:10.3982/ECTA8121", "doi", "10.3982/ECTA8121"),
    ("W3124166904", "openalex", "W3124166904"),
    ("https://arxiv.org/abs/2101.00001v2", "arxiv", "2101.00001"),
    ("649def34f8be52c8b66281af98ae884c09aef38b", "s2", "649def34f8be52c8b66281af98ae884c09aef38b"),
])
def test_parse_identifier(raw, type_, value):
    ident = parse_identifier(raw)
    assert (ident["type"], ident["value"]) == (type_, value)


def test_from_s2_cleans_title_and_venue():
    rec = from_s2(s2_paper(title="The Effect of Minimum Wages*", journal="Jurnal Ekonomi &amp; Studi"))
    assert rec["title"] == "The Effect of Minimum Wages"
    assert rec["journal_name"] == "Jurnal Ekonomi & Studi"


def test_book_review_warning():
    rec = from_s2(s2_paper(title="Economic Change in Modern Indonesia, by Anne Booth"))
    assert any("書評" in w for w in rec["warnings"])
    rec = from_s2(s2_paper(journal="Southern Economic Journal"))
    assert not rec["warnings"]


class FakeOpenAlexClient(LiteratureClient):
    def __init__(self, works):
        super().__init__(use_cache=False)
        self.works = works
        self.calls = []

    def _openalex(self, path, params):
        self.calls.append((path, params))
        return {"results": self.works}


def test_verify_replaces_biblio_with_openalex():
    client = FakeOpenAlexClient([openalex_work(doi="10.1/ABC", issns=("0022-3816",))])
    rec = from_s2(s2_paper(doi="10.1/abc"))
    rec["issns"] = []
    [out] = client._verify_with_openalex([rec])
    assert out["verified"] and out["openalex_id"] == "W1"
    assert out["issns"] == ["0022-3816"] and out["issue"] == "3" and out["pages"] == "1405-1454"
    assert not out["warnings"]
    assert len(client.calls) == 1  # まとめて 1 回で照会


def test_verify_flags_doi_pointing_to_other_paper():
    client = FakeOpenAlexClient([openalex_work(title="Minimum Wages and Low-Wage Jobs: Reply")])
    [out] = client._verify_with_openalex([from_s2(s2_paper())])
    assert any("別タイトル" in w for w in out["warnings"])


def test_verify_flags_wp_doi_for_published_paper():
    client = FakeOpenAlexClient([openalex_work(journal="SSRN Electronic Journal", source_type="repository",
                                               work_type="preprint", issns=("1556-5068",))])
    [out] = client._verify_with_openalex([from_s2(s2_paper(journal="Econometrica"))])
    assert out["ssci"]["status"] == ssci.PREPRINT
    assert any("WP / プレプリント版" in w for w in out["warnings"])


def test_verify_survives_openalex_failure():
    class Failing(FakeOpenAlexClient):
        def _openalex(self, path, params):
            raise ApiError("OpenAlex", "down", 503)
    [out] = Failing([])._verify_with_openalex([from_s2(s2_paper())])
    assert not out["verified"] and "DOI 未照合" in out["warnings"]


def test_linked_falls_back_when_s2_references_are_elided():
    class Client(LiteratureClient):
        def _s2(self, path, params):
            return {"data": None}  # 出版社が引用データを非公開にしている

        def _linked_openalex(self, ident, kind, limit):
            return ["from-openalex"]

    assert Client(use_cache=False).get_linked("10.1/abc", "references") == ["from-openalex"]


def test_get_paper_does_not_fall_back_on_rate_limit():
    class Client(LiteratureClient):
        def _s2(self, path, params):
            raise ApiError("SemanticScholar", "gave up", 429)

        def _get_paper_openalex(self, ident):
            raise AssertionError("OpenAlex should not be used")

    with pytest.raises(ApiError):
        Client(use_cache=False).get_paper("10.1/abc")
