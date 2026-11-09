"""医学のサーベイ（--discipline medical）: PubMed の検索、MEDLINE・SCIE の判定、PICO のカード、撤回、PMC の本文。"""
import json

import pytest

from priorwork import api, check, cli, fulltext, settings, ssci
from priorwork.api import ApiError, LiteratureClient, expand_pages, from_openalex, parse_identifier, pubmed_articles
from priorwork.survey import Survey, off_field

from .conftest import openalex_work, s2_paper

ARTICLE = """<PubmedArticle><MedlineCitation Status="{status}"><PMID Version="1">{pmid}</PMID>
<Article><Journal><ISSN IssnType="Electronic">1533-4406</ISSN>
<JournalIssue><Volume>383</Volume><Issue>27</Issue><PubDate><Year>2020</Year><Month>Dec</Month></PubDate></JournalIssue>
<Title>The New England journal of medicine</Title></Journal>
<ArticleTitle>{title}.</ArticleTitle><Pagination><MedlinePgn>{pages}</MedlinePgn></Pagination>
<ELocationID EIdType="doi" ValidYN="Y">{doi}</ELocationID>
<Abstract><AbstractText Label="METHODS">We randomised <i>adults</i>.</AbstractText>
<AbstractText Label="RESULTS">HR 0.72 (95% CI, 0.60 to 0.86).</AbstractText></Abstract>
<AuthorList><Author><LastName>Polack</LastName><ForeName>Fernando P</ForeName></Author>
<Author><CollectiveName>C4591001 Clinical Trial Group</CollectiveName></Author></AuthorList>
<PublicationTypeList>{types}</PublicationTypeList></Article>
<MeshHeadingList><MeshHeading><DescriptorName>Humans</DescriptorName></MeshHeading></MeshHeadingList>
</MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="pubmed">{pmid}</ArticleId>
<ArticleId IdType="doi">{doi}</ArticleId><ArticleId IdType="pmc">PMC7745181</ArticleId></ArticleIdList>
<ReferenceList><Reference><ArticleIdList><ArticleId IdType="doi">10.9/reference</ArticleId></ArticleIdList></Reference></ReferenceList>
</PubmedData></PubmedArticle>"""


def article(pmid="33301246", title="Safety and Efficacy of a Vaccine", doi="10.1056/NEJMoa2034577", status="MEDLINE",
            pages="2603-15", types=("Journal Article", "Randomized Controlled Trial")):
    return ARTICLE.format(pmid=pmid, title=title, doi=doi, status=status, pages=pages,
                          types="".join(f"<PublicationType>{t}</PublicationType>" for t in types))


def xml(*articles):
    return "<PubmedArticleSet>" + "".join(articles) + "</PubmedArticleSet>"


@pytest.fixture
def fake_pubmed(monkeypatch):
    """_pubmed を、PMID ごとの記事を返すものにする。"""
    def install(*articles, idlist=None, doi_ids=None):
        def fake(self, path, params, raw=False):
            if path.startswith("esearch"):
                ids = idlist if idlist is not None else []
                if '[doi]' in params["term"] and doi_ids is not None:
                    ids = doi_ids
                return {"esearchresult": {"count": str(len(ids)), "idlist": ids, "querytranslation": params["term"]}}
            return xml(*[a for a in articles if any(f'>{i}</PMID>' in a for i in params["id"].split(","))])
        monkeypatch.setattr(LiteratureClient, "_pubmed", fake)
    return install


# ---------------- 記録の読み取り ----------------

def test_pubmed_record_is_normalized():
    r = pubmed_articles(xml(article()))[0]
    assert r["source"] == "PubMed" and r["pmid"] == "33301246" and r["pmcid"] == "PMC7745181"
    assert r["doi"] == "10.1056/NEJMoa2034577"      # 参考文献の DOI を拾わない
    assert r["title"] == "Safety and Efficacy of a Vaccine"     # PubMed の題名の最後のピリオドを落とす
    assert r["authors"] == ["Fernando P Polack", "C4591001 Clinical Trial Group"]
    assert r["year"] == 2020 and r["pages"] == "2603-2615" and r["volume"] == "383"
    assert r["abstract"] == "METHODS: We randomised adults. RESULTS: HR 0.72 (95% CI, 0.60 to 0.86)."
    assert r["mesh"] == ["Humans"] and r["medline"] is True
    assert r["ssci"]["status"] == ssci.MEDLINE


@pytest.mark.parametrize("given, expected", [("1405-14", "1405-1414"), ("2603-2615", "2603-2615"), ("e1234", "e1234"),
                                             ("S12-8", "S12-S18"), ("", "")])
def test_medline_page_ranges_are_written_out(given, expected):
    assert expand_pages(given) == expected


def test_a_paper_not_indexed_for_medline_is_not_called_medline():
    r = pubmed_articles(xml(article(status="PubMed-not-MEDLINE")))[0]
    assert r["ssci"]["status"] == ssci.PUBMED


def test_retracted_papers_are_flagged_from_both_sources():
    r = pubmed_articles(xml(article(types=("Journal Article", "Retracted Publication"))))[0]
    assert r["retracted"] and any("Retracted" in w or "撤回" in w for w in r["warnings"])
    w = dict(openalex_work(), is_retracted=True)
    assert from_openalex(w)["retracted"]


@pytest.mark.parametrize("given, kind", [("PMID:123", "pmid"), ("https://pubmed.ncbi.nlm.nih.gov/123/", "pmid"),
                                         ("10.1056/x", "doi")])
def test_pubmed_identifiers(given, kind):
    assert parse_identifier(given)["type"] == kind


def test_biorxiv_dois_are_preprints_but_cold_spring_harbor_journals_are_not():
    assert api.preprint_doi("10.1101/2020.03.01.123456")
    assert not api.preprint_doi("10.1101/gr.123456.111")


def test_query_is_translated_for_pubmed():
    assert api.pubmed_term('(sglt2 | empagliflozin) + "heart failure" -mice') == \
        '(sglt2 OR empagliflozin) AND "heart failure" NOT mice'
    assert api.pubmed_term("aspirin[tiab]", ["N Engl J Med", "1533-4406"]) == \
        '(aspirin[tiab]) AND ("N Engl J Med"[ta] OR 1533-4406[is])'
    assert api.plain_query("aspirin[tiab] AND Randomized Controlled Trial[pt]") == \
        "aspirin AND Randomized Controlled Trial"
    assert api.pubmed_dates("2015-2024") == {"datetype": "pdat", "mindate": "2015", "maxdate": "2024"}
    assert api.pubmed_dates("2015-")["maxdate"] == "3000"
    assert api.pubmed_dates("2020")["mindate"] == api.pubmed_dates("2020")["maxdate"] == "2020"


# ---------------- 検索 ----------------

def test_search_merges_pubmed_and_s2(monkeypatch, fake_pubmed):
    fake_pubmed(article(), idlist=["33301246"], doi_ids=[])
    same = dict(api.from_s2(s2_paper(title="Safety and Efficacy of a Vaccine", doi="10.1056/nejmoa2034577", citations=9)),
                found_in=["SemanticScholar"], tldr="short summary")
    only_s2 = dict(api.from_s2(s2_paper(title="An observational cohort elsewhere", doi="10.1/other", journal="Some Cardiology Journal")),
                   found_in=["SemanticScholar"])
    monkeypatch.setattr(LiteratureClient, "search", lambda self, q, **kw: [same, only_s2])
    out = LiteratureClient(use_cache=False).search_medical("vaccine", limit=5)
    assert [r["source"] for r in out] == ["PubMed", "SemanticScholar"]
    assert out[0]["found_in"] == ["PubMed", "SemanticScholar"] and out[0]["tldr"] == "short summary"
    assert out[1]["medline"] is False and out[1]["ssci"]["status"] == ssci.NOT_PUBMED


def test_search_survives_when_one_source_is_down(monkeypatch, fake_pubmed, capsys):
    def boom(self, q, **kw):
        raise ApiError("SemanticScholar", "rate limited", 429)
    monkeypatch.setattr(LiteratureClient, "search", boom)
    fake_pubmed(article(), idlist=["33301246"])
    assert len(LiteratureClient(use_cache=False).search_medical("vaccine")) == 1
    # PubMed も落ちていれば、エラーにする（conftest の隔離に戻す）
    def down(self, path, params, raw=False):
        raise ApiError("PubMed", "down", 503)
    monkeypatch.setattr(LiteratureClient, "_pubmed", down)
    with pytest.raises(ApiError):
        LiteratureClient(use_cache=False).search_medical("vaccine")


def test_annotate_gives_pubmed_details_to_a_paper_found_elsewhere(fake_pubmed):
    fake_pubmed(article(), doi_ids=["33301246"])
    r = api.from_s2(s2_paper(title="Safety and Efficacy of a Vaccine", doi="10.1056/NEJMoa2034577"))
    assert r["ssci"]["status"] not in (ssci.MEDLINE,)
    LiteratureClient(use_cache=False).annotate_pubmed([r])
    assert r["pmid"] == "33301246" and r["pmcid"] and r["ssci"]["status"] == ssci.MEDLINE
    assert "Randomized Controlled Trial" in r["publication_types"]


def test_annotate_leaves_a_paper_unchecked_when_pubmed_is_down():
    r = api.from_s2(s2_paper())
    LiteratureClient(use_cache=False).annotate_pubmed([r])
    assert r.get("medline") is None


def test_field_filter_keeps_medicine_in_a_medical_survey(s2_record):
    clinical = dict(s2_record(), fields=["Medicine"])
    cs = dict(s2_record(), fields=["Computer Science"])
    assert off_field(clinical, "social") and not off_field(clinical, "medical")
    assert off_field(cs, "medical")
    assert not off_field(dict(pubmed_articles(xml(article()))[0], fields=["Computer Science"]), "medical")


def test_only_the_medical_filter_counts_medline(s2_record):
    medline = pubmed_articles(xml(article()))[0]
    assert [p["pmid"] for p in cli.rank_and_filter([medline], ssci_only=True, medical=True)] == [medline["pmid"]]
    assert cli.rank_and_filter([medline], ssci_only=True) == []


# ---------------- 雑誌のリスト ----------------

def test_scie_list_is_imported_and_recognized(tmp_path, monkeypatch):
    csv = tmp_path / "Science Citation Index Expanded (SCIE).csv"
    csv.write_text("Journal title,ISSN,eISSN\nThe Lancet,0140-6736,1474-547X\n", encoding="utf-8")
    monkeypatch.setattr(ssci, "DEFAULT_SCIE_LIST", tmp_path / "data" / "scie_journals.csv")
    ssci._scie_cache = None
    monkeypatch.setattr(settings, "data_dir", lambda root: tmp_path / "data")
    try:
        assert settings.import_scie(tmp_path, csv)["journals"] == 1
        status, _ = ssci.classify("The Lancet", ["0140-6736"], source_type="journal", medline=True, pmid="1")
        assert status == ssci.SCIE
        assert settings.status(tmp_path)["scie"]["file"] == "scie_journals.csv"
    finally:
        ssci._scie_cache = None


def test_the_ssci_csv_is_not_taken_for_the_scie_list(tmp_path, monkeypatch):
    (tmp_path / "Social Sciences Citation Index (SSCI).csv").write_text("Journal title,ISSN\nA,0000-0001\n", encoding="utf-8")
    monkeypatch.setattr(ssci, "DEFAULT_SCIE_LIST", tmp_path / "scie_journals.csv")
    ssci._scie_cache = None
    try:
        assert not ssci.get_scie_list().loaded
    finally:
        ssci._scie_cache = None


def test_medline_journal_needs_the_exact_title(monkeypatch):
    summary = {"result": {"uids": ["1"], "1": {"medlineta": "Lancet Oncol", "titlemainlist": [{"title": "The Lancet. Oncology."}]}}}
    monkeypatch.setattr(LiteratureClient, "_pubmed", lambda self, path, params, raw=False:
                        {"esearchresult": {"idlist": ["1"]}} if path.startswith("esearch") else summary)
    client = LiteratureClient(use_cache=False)
    assert client.medline_journal("Lancet Oncol") is True
    assert client.medline_journal("Lancet") is False


# ---------------- サーベイとレポート ----------------

@pytest.fixture
def medical_survey(tmp_path):
    def make(lang="en", **kw):
        return Survey.create("SGLT2 inhibitors in heart failure", "sglt2", {}, reports_dir=tmp_path / "reports",
                             state_dir=tmp_path / "state", lang=lang, discipline="medical", **kw)
    return make


@pytest.mark.parametrize("lang, label, head, section", [
    ("en", "Clinical question", "Study design", "Safety and harms"),
    ("ja", "臨床上の問い", "研究デザイン", "安全性と有害事象"),
])
def test_a_medical_survey_has_its_own_cards_and_report(medical_survey, lang, label, head, section):
    s = medical_survey(lang=lang)
    assert s.medical and s.search_field == "medical"
    e, _ = s.upsert(pubmed_articles(xml(article()))[0], "search")
    s.set_status([e["number"]], "included")
    s.save(), s.render()
    md = s.md_path.read_text(encoding="utf-8")
    assert f"**{label}**" in md and head in md and section in md
    assert "PMID 33301246" in md and "Randomized Controlled Trial" in md
    assert "social-science" not in md and "SSCI" not in md
    # 書いた欄を読み返せる
    s.set_card(e["number"], {"rq": "Does it work?", "method": "RCT", "findings": "HR 0.72"})
    s.save(), s.render()
    assert s.card_fields()[e["key"]]["method"] == "RCT"
    assert "| Does it work? |" in s.md_path.read_text(encoding="utf-8")


def test_card_fields_round_trip_in_a_medical_survey(medical_survey):
    from priorwork.survey import card_values, new_card_body, parse_card_fields, set_card_fields, MEDICAL_CARD_FIELDS
    body = new_card_body(pubmed_articles(xml(article()))[0], "ja", MEDICAL_CARD_FIELDS)
    body = set_card_fields(body, {"rq": "効くか", "findings": "HR 0.72\n95% CI 0.60-0.86"}, "ja", MEDICAL_CARD_FIELDS)
    assert "主な結果（効果量と95%信頼区間）" in body
    assert parse_card_fields(body)["rq"] == "効くか"
    assert card_values(body)["findings"] == "HR 0.72\n95% CI 0.60-0.86"


def test_a_social_survey_stays_as_it_was(tmp_path):
    s = Survey.create("Minimum wage", "mw", {}, reports_dir=tmp_path / "r", state_dir=tmp_path / "s", lang="en")
    assert not s.medical and s.search_field == "social" and "discipline" not in s.data
    md = s.md_path.read_text(encoding="utf-8")
    assert "Identification" in md and "social-science" in md


def test_medical_template_matches_in_both_languages():
    from priorwork.workspace import assets_dir
    en, ja = [(assets_dir(lang) / "templates" / "medical_review.md").read_text(encoding="utf-8") for lang in ("en", "ja")]
    for mark in ("<!-- priorwork:synthesis -->", "<!-- BEGIN priorwork:", "\n## "):
        assert en.count(mark) == ja.count(mark), mark


def test_check_reports_a_retracted_included_paper_even_after_confirming(medical_survey):
    s = medical_survey()
    e, _ = s.upsert(pubmed_articles(xml(article(types=("Journal Article", "Retracted Publication"))))[0], "search")
    s.set_status([e["number"]], "included")
    s.fix_record(e["number"], confirm="looks fine")
    s.save(), s.render()
    errors = [m for level, m in check.check_survey(s) if level == check.ERROR]
    assert any("retracted" in m or "撤回" in m for m in errors)


def test_check_finds_a_later_retraction_online(medical_survey):
    class Client:
        def openalex_works(self, dois=(), select=""):
            return [{"doi": "https://doi.org/10.1056/nejmoa2034577", "title": "Safety and Efficacy of a Vaccine",
                     "is_retracted": True}]
        def issue_years(self, dois):
            return {}
    s = medical_survey()
    e, _ = s.upsert(pubmed_articles(xml(article()))[0], "search")
    s.set_status([e["number"]], "included")
    s.save(), s.render()
    assert any("retracted" in m or "撤回" in m for level, m in check.check_survey(s, Client()) if level == check.ERROR)


def test_a_group_author_is_recognized_in_the_text(medical_survey):
    s = medical_survey()
    e, _ = s.upsert(dict(pubmed_articles(xml(article()))[0], authors=["RECOVERY Collaborative Group"], year=2021), "search")
    s.set_status([e["number"]], "included")
    s.save(), s.render()
    md = s.md_path.read_text(encoding="utf-8")
    s.md_path.write_text(md.replace("- **Randomized trials**:", "- **Randomized trials**: RECOVERY Collaborative Group (2021) found it."),
                         encoding="utf-8")
    assert not [m for level, m in check.check_survey(s) if level == check.ERROR and "RECOVERY" in m]


def test_effect_sizes_on_a_card_match_the_full_text():
    """小数の効果量と信頼区間を、本文の数値と突き合わせられる。"""
    text = "=== page 2 ===\nThe hazard ratio was 0.72 (95% CI, 0.60 to 0.86) among 7,020 patients."
    written = "HR 0.72 (95% CI 0.60-0.86), n=7,020 (p. 2)"
    in_text = check._text_numbers(text)
    assert all(check._plain_number(n) in in_text for n in check._card_numbers(written))


# ---------------- PMC の本文 ----------------

JATS = """<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta><abstract><p>Short summary.</p></abstract></article-meta></front>
<body><sec><title>Methods</title><p>We enrolled <italic>adults</italic>. {long}</p></sec>
<table-wrap><caption><p>Table 1</p></caption><table><tr><th>Arm</th><th>HR</th></tr><tr><td>Vaccine</td><td>0.72</td></tr></table></table-wrap></body>
<back><ref-list><ref><mixed-citation>Someone 1999</mixed-citation></ref></ref-list></back></article>"""


def test_jats_full_text_keeps_tables_and_drops_references():
    text = api.jats_fulltext(JATS.format(long="x"))
    assert "We enrolled adults." in text and "Vaccine | 0.72" in text and "Table 1" in text
    assert "Short summary." in text and "Someone 1999" not in text


def test_fulltext_falls_back_on_pmc(tmp_path, monkeypatch):
    class Client:
        def openalex_works(self, dois=(), select=""):
            return []
        def pmc_fulltext(self, pmcid):
            return api.jats_fulltext(JATS.format(long="word " * 200))
    monkeypatch.setattr(fulltext, "find_zotero_pdf", lambda doi: None)
    record = dict(pubmed_articles(xml(article()))[0], oa_pdf="")
    got = fulltext.fetch_fulltext({"record": record, "key": "k", "number": 1}, Client(), out_dir=tmp_path)
    assert got["source"].startswith("europepmc:PMC7745181") and got["page_markers"] is False
    assert "Vaccine | 0.72" in (tmp_path / "001_k.txt").read_text(encoding="utf-8")
