"""改善点メモ 6 章: 派生文書、ハイフン入りの姓、add の途中保存、Zotero の反映の遅れ、
文字の無い PDF、オンライン先行公開の年。"""
import pytest

from priorwork import api, cli, derived
from priorwork.api import ApiError
from priorwork.check import ERROR, INFO, WARN, check_survey, find_citations
from priorwork.fulltext import content_chars
from priorwork.survey import INCLUDED, Survey, surname

TEXT = ("=== page 1 ===\n\nWe use 1,234 municipalities from 2001 to 2010.\n\n"
        "=== page 2 ===\n\nThe estimate is .35 (s.e. 0.08) using difference-in-differences.\n")
CARD = {"evidence": "fulltext", "rq": "外部委託は人員を減らすか", "x": "外部委託", "y": "職員数",
        "data": "1,234 自治体、2001–2010 年（p. 1）", "method": "差の差（p. 2）",
        "findings": "係数は 0.35（標準誤差 0.08）（p. 2）", "limits": "記載なし"}


@pytest.fixture
def s(s2_record, tmp_path):
    s = Survey.create("外部委託", "mob", {"question": "q"}, depth="full")
    s.upsert(s2_record(doi="10.1/a", title="Outsourcing and staff", authors=("Melissa Dell",), year=2010),
             "search", status=INCLUDED)
    s.get(1)["record"]["pages"] = "101-102"
    (tmp_path / "ft.txt").write_text(TEXT, encoding="utf-8")
    s.get(1)["fulltext"] = {"path": "ft.txt", "source": "oa:x", "pages": 2, "chars": 900, "page_markers": True}
    s.save()
    s.render()
    s.set_card(1, CARD)
    return s


# ---- 6.1 派生文書 ----

def test_derive_makes_a_file_beside_the_report_with_its_references(s):
    out = derived.create(s, "lecture", "行政学の講義資料", length=2000, structure="背景; 知見; 問い")
    assert out.name == f"{s.name}.lecture.md"
    text = out.read_text(encoding="utf-8")
    assert "## 背景" in text and "## 問い" in text
    assert "2,000" in text and "含めない" in text
    # 書いた引用に合わせて参考文献が付く
    out.write_text(text.replace("## 背景", "## 背景\n\nDell (2010) は 1,234 の自治体を調べた。"), encoding="utf-8")
    derived.render_all(s)
    refs = out.read_text(encoding="utf-8").split("priorwork:derived_references")[1]
    assert "Outsourcing and staff" in refs
    # 状態ファイルに記録が残る（一覧に出る）
    assert Survey.load(s.name).data["derived"]["lecture"]["length"] == 2000


def test_derive_rejects_names_that_clash_with_other_outputs(s):
    from priorwork.survey import SurveyError
    with pytest.raises(SurveyError):
        derived.create(s, "draft", "x")
    with pytest.raises(SurveyError):
        derived.create(s, "講義", "x")


def test_check_looks_at_the_derived_text(s):
    out = derived.create(s, "memo", "読書メモ", length=40)
    text = out.read_text(encoding="utf-8")
    out.write_text(text.replace("<!-- 文章をここに書く -->",
                                "Dell (2010) は 2,500 の自治体を調べた。Fake (2019) も同じ。"), encoding="utf-8")
    found = check_survey(s)
    errors = [m for lv, m in found if lv == ERROR]
    warns = [m for lv, m in found if lv == WARN]
    assert any("Fake (2019)" in m and "memo" in m for m in errors), errors
    assert any("2500" in m and "カード" in m for m in warns), warns        # カードに無い数値
    assert not any("1234" in m for m in warns)


def test_a_card_not_read_in_full_is_reported(s):
    s.set_card(1, {**CARD, "evidence": "abstract"})
    out = derived.create(s, "memo", "読書メモ")
    out.write_text(out.read_text(encoding="utf-8").replace("<!-- 文章をここに書く -->", "Dell (2010) の結果。"),
                   encoding="utf-8")
    assert any("本文確認済" in m and "memo" in m for lv, m in check_survey(s) if lv == WARN)


def test_length_counts_text_without_citation_parentheses():
    md = "# 題\n\n- 本文です（Dell 2010）。\n- Dell (2010) は言う。\n"
    assert derived.measure(md, "ja", False) == len("本文です。") + len("Dellは言う。")
    assert derived.measure(md, "ja", True) > derived.measure(md, "ja", False)
    assert derived.measure("Smith (2010) argues this (Dell 2010).", "en", False) == 3


# ---- 6.2 ハイフン入りの姓 ----

def test_hyphenated_surnames_match_whatever_the_hyphen():
    assert surname("Xavier Fernández‐i‐Marín") == "fernandez-i-marin"          # U+2010
    for text in ("Fernández‐i‐Marín et al. (2024a)", "Fernandez-i-Marin et al. (2024a)"):
        assert [c.name for c in find_citations(text)] == ["fernandez-i-marin"]
    # 文の中のダッシュは姓に入れない
    assert [c.name for c in find_citations("Japan—Smith (2001)")] == ["smith"]


def test_a_hyphenated_author_is_not_reported_as_unregistered(s2_record):
    s = Survey.create("t", "hy", {})
    s.upsert(s2_record(doi="10.1/f", title="Policy accumulation", authors=("Xavier Fernández‐i‐Marín", "Christoph Knill"),
                       year=2024), "search", status=INCLUDED)
    s.save()
    s.render()
    md = s.md_path.read_text().replace("## 1. 研究の背景と中心的な論点\n",
                                       "## 1. 研究の背景と中心的な論点\nFernández-i-Marín and Knill (2024) は言う。\n")
    s.md_path.write_text(md)
    assert not any("Marin" in m for lv, m in check_survey(s) if lv == ERROR)


# ---- 6.3 add はレート制限で止まっても、それまでの登録を残す ----

def test_add_keeps_what_it_registered_before_the_rate_limit(s2_record, monkeypatch, capsys):
    Survey.create("t", "add", {}).save()
    calls = []

    def get_paper(self, pid):
        calls.append(pid)
        if pid == "10.1/c":
            raise ApiError("SemanticScholar", "gave up after 5 retries (429)", 429)
        return s2_record_from(pid)

    def s2_record_from(pid):
        return s2_record(doi=pid, title=f"Paper {pid}", authors=("Ann Lee",), year=2020)

    monkeypatch.setattr(api.LiteratureClient, "get_paper", get_paper)
    with pytest.raises(SystemExit):
        cli.main(["add", "add", "10.1/a", "10.1/b", "10.1/c", "10.1/d", "--candidate"])
    s = Survey.load("add")
    assert {e["record"]["doi"] for e in s.papers} == {"10.1/a", "10.1/b"}
    assert calls == ["10.1/a", "10.1/b", "10.1/c"]               # 429 の後は試さない
    out = capsys.readouterr().out
    assert "./priorwork add" in out and "10.1/c 10.1/d" in out and "--candidate" in out


# ---- 6.4 Zotero の反映の遅れ ----

def test_the_zotero_note_says_where_it_reads_from():
    from priorwork.zotero import ZoteroClient
    z = ZoteroClient("k", "1")
    z._index = {"synced_at": "2026-10-27T10:00:00", "items": {}}
    note = z.sync_note()
    assert "zotero.org" in note and "2026-10-27T10:00:00" in note and "--pdf" in note


# ---- 6.5 文字の無い PDF ----

def test_a_scanned_pdf_with_a_watermark_line_has_no_content():
    scan = "".join(f"\n\n=== page {i} ===\n\nDownloaded from informs.org by [1.2.3.4] on 01 May 2026\n"
                   for i in range(1, 25))
    assert content_chars(scan) == (24, 0)
    real = "".join(f"\n\n=== page {i} ===\n\nOrganization Science\n" + f"word{i} " * 300 for i in range(1, 25))
    assert content_chars(real)[1] > 300 * 24


def test_check_does_not_ask_to_fill_in_from_a_scanned_text(s, tmp_path):
    scan = "".join(f"=== page {i} ===\n\nDownloaded from informs.org\n\n" for i in range(1, 30))
    (tmp_path / "ft.txt").write_text(scan, encoding="utf-8")
    s.get(1)["fulltext"]["pages"] = 29
    s.save()
    s.set_card(1, {**CARD, "evidence": "abstract"})
    msgs = check_survey(s)
    assert not any("要旨のみ" in m and "本文を取得" in m for lv, m in msgs if lv == WARN), msgs


# ---- 6.6 オンライン先行公開の年 ----

def test_issue_year_replaces_the_online_year(monkeypatch, s2_record):
    monkeypatch.setattr(api.LiteratureClient, "_crossref", lambda self, path, params: {"message": {"items": [
        {"DOI": "10.1/x", "journal-issue": {"published-print": {"date-parts": [[2024, 6]]}}}]}})
    client = api.LiteratureClient(use_cache=False)
    rec = s2_record(doi="10.1/x", year=2023)
    rec["volume"] = "31"
    client.use_issue_year(rec)
    assert (rec["year"], rec["online_year"]) == (2024, 2023)


def test_check_warns_about_an_online_year(s, monkeypatch):
    class Client:
        def openalex_works(self, **kw):
            return [{"doi": "https://doi.org/10.1/a", "title": "Outsourcing and staff"}]

        def issue_years(self, dois):
            return {"10.1/a": 2011}

    s.get(1)["record"]["volume"] = "12"
    s.save()
    warns = [m for lv, m in check_survey(s, Client()) if lv == WARN]
    assert any("2011" in m and "--year 2011" in m for m in warns), warns


def test_a_derived_document_exports_to_html_without_its_header(s):
    out = derived.create(s, "lecture", "講義資料", length=100)
    out.write_text(out.read_text(encoding="utf-8").replace("<!-- 文章をここに書く -->", "Dell (2010) は 1,234 の自治体を調べた。"),
                   encoding="utf-8")
    html, issues = derived.export_one(s, "lecture")
    assert html.name == f"{s.name}.lecture.html" and issues == []
    text = html.read_text(encoding="utf-8")
    assert "1,234" in text and "Outsourcing and staff" in text
    assert "字数の目安" not in text and "priorwork:" not in text
