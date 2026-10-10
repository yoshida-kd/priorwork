"""原稿から始めるサーベイ（`new --manuscript`）: 原稿での役割の欄・マトリクスの列・下書きの書き出し。"""

import pytest

from priorwork.check import ERROR, WARN, check_survey
from priorwork.export import DRAFT_ANCHOR, export, export_draft
from priorwork.survey import INCLUDED, Survey, SurveyError, extract_blocks


@pytest.fixture
def manuscript(tmp_path):
    path = tmp_path / "manuscript" / "paper.md"
    path.parent.mkdir()
    path.write_text("# 4. Data and methods\n...\n# 5. Results\n...\n")
    return path


@pytest.fixture
def ms(manuscript, s2_record):
    s = Survey.create("最低賃金と雇用", "mw_paper", {"question": "雇用は減るか"}, manuscript=str(manuscript))
    for i, (doi, title, authors, year) in enumerate([
        ("10.1/a", "Minimum wages and employment in New Jersey", ("David Card", "Alan B. Krueger"), 1994),
        ("10.1/b", "The effect of minimum wages on low-wage jobs", ("Doruk Cengiz", "Arindrajit Dube"), 2019),
    ]):
        e, _ = s.upsert(s2_record(doi=doi, title=title, authors=authors, year=year), "search")
        s.set_status([e["number"]], INCLUDED)
    s.render()
    return s


def write_draft(s: Survey, text: str):
    md = s.md_path.read_text()
    md = md.replace("### Literature review\n", "### Literature review\n" + text + "\n", 1)
    s.md_path.write_text(md)


def test_the_manuscript_is_recorded_relative_to_the_workspace(ms, tmp_path):
    assert ms.manuscript == "manuscript/paper.md"
    assert Survey.load("mw_paper").manuscript == "manuscript/paper.md"
    md = ms.md_path.read_text()
    assert "`manuscript/paper.md`" in extract_blocks(md)["scope"] and DRAFT_ANCHOR in md
    with pytest.raises(SurveyError):
        Survey.create("t", "missing", {}, manuscript=str(tmp_path / "nope.md"))


def test_cards_and_matrix_have_the_role(ms):
    card = ms.card(1)
    assert "role" in card
    assert ms.set_card(1, {"role": "C1 支持"})
    assert ms.card(1)["role"] == "C1 支持"
    matrix = extract_blocks(ms.md_path.read_text())["matrix"]
    assert matrix.splitlines()[0].split(" | ")[2] == "役割" and "C1 支持" in matrix
    empty = [m for level, m in check_survey(ms) if level == WARN and "#2" in m and "role" in m]
    assert empty


def test_a_survey_without_a_manuscript_has_no_role(s2_record):
    s = Survey.create("t", "plain", {})
    e, _ = s.upsert(s2_record(), "search", status=INCLUDED)
    s.render()
    assert "role" not in s.card(e["number"]) and "役割" not in extract_blocks(s.md_path.read_text())["matrix"]
    with pytest.raises(SurveyError):
        s.set_card(e["number"], {"role": "C1"})
    with pytest.raises(RuntimeError):
        export_draft(s)


def test_the_draft_is_exported_with_the_papers_it_cites(ms):
    with pytest.raises(RuntimeError):
        export_draft(ms)  # まだ書かれていない
    write_draft(ms, "Card and Krueger (1994) found no fall in employment.")
    out, issues = export_draft(ms)
    text = out.read_text()
    assert out.name.endswith(".draft.md") and not issues
    assert text.startswith("## Introduction") and "## Literature review\nCard and Krueger (1994)" in text
    assert "## References" in text and "Card, Alan B. Krueger (1994)" in text and "Cengiz" not in text
    assert "<!--" not in text and "原稿の言語" not in text


def test_the_draft_reports_unregistered_citations(ms):
    write_draft(ms, "不明な研究として Nobody (2001) がある。")
    out, issues = export_draft(ms)
    assert issues and "## 参考文献" in out.read_text()
    assert any(level == ERROR and "Nobody" in m for level, m in check_survey(ms))


def test_the_full_report_still_exports(ms):
    write_draft(ms, "Card and Krueger (1994) found no fall in employment.")
    out, _ = export(ms, "md")
    text = out.read_text()
    assert "Card and Krueger (1994) found" in text and "原稿の言語" not in text


def test_check_warns_when_the_manuscript_moved(ms, manuscript):
    manuscript.unlink()
    assert any(level == WARN and "paper.md" in m for level, m in check_survey(ms))
