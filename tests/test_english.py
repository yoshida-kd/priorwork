"""英語のワークスペース（レポート・AGENTS.md・スキル）と、英語の表示。"""

import pytest

from priorwork import scaffold, survey
from priorwork.check import WARN, check_survey
from priorwork.export import export
from priorwork.survey import INCLUDED, Survey, extract_blocks


@pytest.fixture
def english(tmp_path, monkeypatch):
    monkeypatch.setenv("PRIORWORK_LANG", "en")
    scaffold.init(tmp_path / "ws", lang="en")
    monkeypatch.setattr(survey, "ROOT", tmp_path / "ws")
    return tmp_path / "ws"


def test_init_writes_english_assets(english):
    assert (english / "AGENTS.md").read_text().startswith("# Instructions for agents")
    assert "Start a new survey" in (english / ".agent/skills/priorwork-new/SKILL.md").read_text()
    assert "Instructions for agents specific" in (english / "AGENTS.local.md").read_text()
    assert scaffold.sync_status(english) is None


def test_the_language_is_fixed_at_init(english):
    scaffold.init(english, lang="ja")                       # 既存のワークスペースの言語は変えない
    assert (english / "AGENTS.md").read_text().startswith("# Instructions for agents")


def test_english_report_renders_and_reads_back(english, s2_record):
    s = Survey.create("Minimum wages", "mw", {"question": "Do they cost jobs?"})
    assert s.lang == "en"
    md = s.md_path.read_text()
    assert "# Literature review: Minimum wages" in md and "**Research question**: Do they cost jobs?" in md
    s.upsert(s2_record(), "search", status=INCLUDED)
    s.save()
    s.render()
    md = s.md_path.read_text()
    papers = extract_blocks(md)["papers"]
    assert "- **Evidence**: unchecked" in papers and "- **Source**:" in papers
    assert "| Paper | Journal |" in extract_blocks(md)["matrix"]
    assert "Included 1" in extract_blocks(md)["log"]

    assert any('still "unchecked"' in m for lvl, m in check_survey(s) if lvl == WARN)
    md = md.replace("- **Evidence**: unchecked", "- **Evidence**: abstract only").replace(
        "- **RQ**:", "- **RQ**: Employment effects of the minimum wage", 1)
    s.md_path.write_text(md)
    s.render()
    assert "abstract only" in extract_blocks(s.md_path.read_text())["matrix"]
    assert not any("unchecked" in m for _, m in check_survey(s))


def test_english_export_is_marked_as_a_draft_in_english(english):
    s = Survey.create("Minimum wages", "mw", {})
    out, issues = export(s, "html")
    page = out.read_text()
    assert '<html lang="en">' in page and "Draft" in page and "empty sections" in page
    assert "(not set)" in page and "priorwork scope" not in page


def test_a_japanese_survey_in_an_english_workspace_keeps_japanese_labels(english, s2_record):
    s = Survey.create("最低賃金", "mw", {}, lang="ja")
    s.upsert(s2_record(), "search", status=INCLUDED)
    s.save()
    s.render()
    assert "- **確認レベル**: 未確認" in s.md_path.read_text()
    # 表示の言語（英語）は検査のメッセージに、レポートの言語（日本語）は確認レベルの表記に
    assert any('still "未確認"' in m for _, m in check_survey(s))
