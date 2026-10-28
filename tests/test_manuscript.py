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
    s = Survey.create("最低賃金と雇用", "mw_paper", {"question": "雇用は減るか"}, manuscript=str(manuscript), purpose="draft")
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


def test_a_folder_can_be_the_manuscript(tmp_path):
    folder = tmp_path / "manuscripts" / "mob"
    (folder / "tables").mkdir(parents=True)
    (folder / "paper.md").write_text("# 5. Results\n")
    s = Survey.create("t", "folder", {}, manuscript=str(folder))
    assert s.manuscript == "manuscripts/mob" and "role" in dict(s.card_spec)


def test_the_draft_must_cite_papers_read_in_full(ms):
    write_draft(ms, "Card and Krueger (1994) found no fall in employment.")
    shallow = [m for level, m in check_survey(ms) if level == WARN and "本文で確かめていない" in m]
    assert shallow and "#1" in shallow[0]
    ms.set_card(1, {"evidence": "fulltext"})
    assert not [m for level, m in check_survey(ms) if "本文で確かめていない" in m]


# ---------------- 書きかけの原稿の補完（--purpose complete） ----------------

def test_the_authors_marks_are_found(tmp_path):
    from priorwork import manuscript
    paper = tmp_path / "paper.md"
    paper.write_text("# 1. Introduction\nWages rose [cite].\n\n## 2.1 Theory\nMonopsony [@?] explains it.\n"
                     "TODO(priorwork): add the literature on institutions\n")
    marks = manuscript.find_marks(manuscript.read(paper))
    assert [(m["line"], m["heading"], m["mark"], m["note"]) for m in marks] == [
        (2, "1. Introduction", "[cite]", ""), (5, "2.1 Theory", "[@?]", ""),
        (6, "2.1 Theory", "TODO(priorwork)", "add the literature on institutions")]


def test_a_survey_that_fills_in_a_manuscript(manuscript, s2_record):
    s = Survey.create("最低賃金と雇用", "mw_fill", {"question": "雇用は減るか"}, manuscript=str(manuscript))
    assert s.purpose == "complete"
    e, _ = s.upsert(s2_record(doi="10.1/a", title="Minimum wages and employment in New Jersey",
                              authors=("David Card", "Alan B. Krueger"), year=1994), "search")
    s.set_status([e["number"]], INCLUDED)
    s.render()
    from priorwork import cli
    assert "complete" in {step["id"] for step in cli.next_steps(s, [])}
    with pytest.raises(RuntimeError, match="補完の一覧"):              # まだ何も書いていない
        export_draft(s, "md")

    md = s.md_path.read_text()
    md = md.replace("### K1 差し込む — \n\n- **場所**: \n- **理由**: \n",
                    "### K1 差し込む — 1. Introduction\n\n- **理由**: [cite] の印\n\n"
                    "Card and Krueger (1994) は雇用の減少を見いだしていない。\n")
    s.md_path.write_text(md)
    found = [m for lvl, m in check_survey(s, None) if lvl == WARN]
    assert any("場所" in m and "K1" in m for m in found), found       # どこに足すかが無い

    s.md_path.write_text(md.replace("- **理由**:", "- **場所**: 1. Introduction の「Wages rose」の後\n- **理由**:"))
    assert not any("場所" in m and "K1" in m for lvl, m in check_survey(s, None))
    out, _ = export_draft(s, "md")
    text = out.read_text()
    assert "## K1 差し込む — 1. Introduction" in text and "場所" in text
    assert "Krueger" in text.rsplit("\n## ", 1)[1]                     # 最後の節（参照文献）に引いた論文


def test_a_changed_manuscript_is_noticed(ms, manuscript, capsys):
    from priorwork import cli
    assert ms.manuscript_read["sha256"] and not ms.manuscript_changed()
    assert "manuscript_changed" not in {step["id"] for step in cli.next_steps(ms, [])}
    manuscript.write_text(manuscript.read_text() + "\n# 6. Discussion\nTODO(priorwork): the literature on X\n")
    s = Survey.load("mw_paper")
    assert s.manuscript_changed()
    step = next(st for st in cli.next_steps(s, []) if st["id"] == "manuscript_changed")
    assert step["args"] == ["read", s.manuscript, "--for", s.name]
    assert any("読み直し" in m for lvl, m in check_survey(s, None) if lvl == WARN)
    cli.main(["read", str(manuscript), "--for", s.name])                 # 読み直したと記録する
    assert "TODO(priorwork)" in capsys.readouterr().out
    assert not Survey.load("mw_paper").manuscript_changed()
