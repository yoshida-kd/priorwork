import pytest

from priorwork import api, fulltext, ssci, survey, workspace, zotero
from priorwork.api import from_openalex, from_s2


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """ユーザーの SSCI リスト・reports/・状態ファイル・キャッシュ・.env に依存しないようにする。"""
    monkeypatch.setattr(ssci, "_list_cache", ssci.SSCIJournalList(None))
    monkeypatch.setattr(survey, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(survey, "ROOT", tmp_path)
    workspace.save_config(tmp_path, {"lang": "ja"})        # 既存のテストは日本語のワークスペースを見ている
    monkeypatch.setattr(survey, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(api, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(fulltext, "FULLTEXT_DIR", tmp_path / "fulltext")
    monkeypatch.setattr(zotero, "INDEX_PATH", tmp_path / "zotero" / "index.json")
    monkeypatch.setenv("PRIORWORK_NO_CACHE", "1")
    # 既存のテストは日本語の表示を見ている。英語は test_english.py などで言語を指定して確かめる
    monkeypatch.setenv("PRIORWORK_LANG", "ja")
    for var in ("ZOTERO_API_KEY", "ZOTERO_USER_ID", "ZOTERO_WEBDAV_URL"):  # 本物の Zotero に接続しない
        monkeypatch.delenv(var, raising=False)
    yield


def s2_paper(title="Minimum Wages and Low-Wage Jobs", doi="10.1/abc", journal="Journal of Politics", year=2019,
             authors=("Doruk Cengiz", "Arindrajit Dube"), citations=100, **extra):
    raw = {
        "paperId": "a" * 40,
        "title": title,
        "authors": [{"name": a} for a in authors],
        "year": year,
        "venue": journal,
        "journal": {"name": journal, "volume": "10", "pages": "1-20"},
        "publicationVenue": {"name": journal, "type": "journal"},
        "externalIds": {"DOI": doi} if doi else {},
        "citationCount": citations,
        "publicationTypes": ["JournalArticle"],
        "abstract": "We study minimum wages.",
    }
    raw.update(extra)
    return raw


def openalex_work(title="Minimum Wages and Low-Wage Jobs", doi="10.1/abc", journal="Journal of Politics",
                  issns=("0022-3816",), source_type="journal", work_type="article", year=2019, wid="W1",
                  authors=("Doruk Cengiz", "Arindrajit Dube"), citations=100, referenced=()):
    return {
        "id": f"https://openalex.org/{wid}",
        "doi": f"https://doi.org/{doi}" if doi else None,
        "title": title,
        "publication_year": year,
        "type": work_type,
        "authorships": [{"author": {"display_name": a}} for a in authors],
        "primary_location": {"source": {"display_name": journal, "issn": list(issns), "type": source_type}},
        "biblio": {"volume": "134", "issue": "3", "first_page": "1405", "last_page": "1454"},
        "cited_by_count": citations,
        "referenced_works": [f"https://openalex.org/{r}" for r in referenced],
        "abstract_inverted_index": {"Hello": [0], "world": [1]},
    }


@pytest.fixture
def s2_record():
    def make(**kw):
        return from_s2(s2_paper(**kw))
    return make


@pytest.fixture
def oa_record():
    def make(**kw):
        return from_openalex(openalex_work(**kw))
    return make
