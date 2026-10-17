"""Octavo のプロジェクトとのつなぎ: 設定と .bib を読む、原稿の引用を登録する、下書きを [@key] で書き出す。"""
from pathlib import Path

import pytest

from priorwork import cli, octavo
from priorwork.api import from_openalex
from priorwork.survey import INCLUDED, Survey

from .conftest import openalex_work
from .test_cli_json import FakeClient, ws  # noqa: F401  （ws はフィクスチャ）

BIB = """% Zotero から
@article{card1994,
  title = {Minimum {Wages} and Employment: A Case Study},
  author = {Card, David and Krueger, Alan B.},
  year = {1994},
  doi = {10.1/card},
}
@article{dube2010,
  title = "Minimum Wage Effects Across State Borders",
  author = {Dube, Arindrajit and Lester, T. William and Reich, Michael},
  date = {2010-11},
  doi = {https://doi.org/10.1/DUBE},
}
@book{nodoi2001, title={A Book}, author={Smith, John}, year=2001}
"""

CONFIG = """\"\"\"設定\"\"\"
import os
CONFIG = {
    'documents': {'papers': {'src': 'papers/*/paper.md'}},
    'bib_file': 'refs.bib',
    'zotero_collection': 'Minimum wages',
    'meta': {'author': os.environ.get('ME', 'me')},
}
"""


def make_project(root: Path) -> Path:
    (root / "papers" / "mw").mkdir(parents=True)
    (root / "octavo.config.py").write_text(CONFIG, encoding="utf-8")
    (root / "refs.bib").write_text(BIB, encoding="utf-8")
    (root / "results").mkdir()
    (root / "results" / "analysis.json").write_text('{"n_obs": 1523}', encoding="utf-8")
    (root / "data").mkdir()
    (root / "data" / "raw.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    paper = root / "papers" / "mw" / "paper.md"
    paper.write_text("# Intro\n\nAs shown by @card1994 and [see @dube2010, p. 3]. Mail me@example.com.\n",
                     encoding="utf-8")
    return paper


def test_config_bib_and_cited_keys(tmp_path):
    paper = make_project(tmp_path / "proj")
    root = octavo.find_project(paper)
    assert root == (tmp_path / "proj").resolve()
    info = octavo.project_info(root)
    assert info["zotero_collections"] == ["Minimum wages"] and info["bib"].endswith("refs.bib") and info["bib_exists"]
    entries = octavo.read_bib(Path(info["bib"]))
    assert [(e["key"], e["doi"], e["year"]) for e in entries] == [
        ("card1994", "10.1/card", "1994"), ("dube2010", "10.1/dube", "2010"), ("nodoi2001", "", "2001")]
    assert entries[0]["title"] == "Minimum Wages and Employment: A Case Study"
    assert entries[1]["authors"] == ["Dube", "Lester", "Reich"]
    assert octavo.cited_keys(paper.read_text(), {e["key"] for e in entries}) == ["card1994", "dube2010"]


def test_read_an_octavo_paper(tmp_path, capsys):
    paper = make_project(tmp_path / "proj")
    cli.main(["read", str(paper.parent)])
    out = capsys.readouterr().out
    assert "=== papers/mw/paper.md ===" in out and "=== results/analysis.json ===" in out
    assert "raw.csv" not in out and "@article" not in out
    assert "[@dube2010] Dube, Lester, Reich (2010)" in out and "doi:10.1/dube" in out


@pytest.fixture
def fake_get(monkeypatch):
    titles = {"10.1/card": ("Minimum Wages and Employment: A Case Study", ("David Card", "Alan B. Krueger"), 1994),
              "10.1/dube": ("Minimum Wage Effects Across State Borders", ("Arindrajit Dube", "T. William Lester"), 2010),
              "10.1/neum": ("Minimum Wages and Employment", ("David Neumark", "William Wascher"), 2007)}

    def get_paper(self, pid):
        title, authors, year = titles[pid]
        return from_openalex(openalex_work(title=title, doi=pid, authors=authors, year=year, wid=pid[-4:]))
    monkeypatch.setattr(FakeClient, "get_paper", get_paper, raising=False)


def test_add_cited_and_export_for_octavo(ws, tmp_path, fake_get, capsys):  # noqa: F811
    paper = make_project(tmp_path / "proj")
    made = ws("new", "mw", "--slug", "mw", "--manuscript", str(paper.parent), "--json")
    added = ws("add", "mw", "--cited", "--json")
    assert len(added["added"]) == 2 and added["no_doi"] == []
    ws("add", "mw", "10.1/neum", "--json")                       # .bib にまだ無い論文
    detail = ws("status", "mw", "--json")
    assert detail["octavo"]["zotero_collections"] == ["Minimum wages"]
    assert "--octavo" in next(s for s in detail["next"] if s["id"] == "draft")["args"]

    s = Survey.load("mw")
    md = s.md_path.read_text(encoding="utf-8").replace(
        "### Introduction",
        "### Introduction\n\nCard and Krueger (1994) found no fall, unlike Neumark and Wascher (2007, p. 5) "
        "(e.g., Dube et al., 2010; Card and Krueger 1994). See also Smith (2001) and (2010年代).")
    s.md_path.write_text(md, encoding="utf-8")
    capsys.readouterr()
    cli.main(["export", "mw", "--draft", "--octavo"])
    out = capsys.readouterr().out
    assert "10.1/neum" in out and "Minimum wages" in out
    text = Path(made["report"]).with_name(Path(made["report"]).stem + ".proj.octavo.md").read_text(encoding="utf-8")
    assert "@card1994 found no fall, unlike @PRIORWORK:Neumark2007 [p. 5]" in text
    assert "[e.g., @dube2010; @card1994]" in text
    assert "Smith (2001)" in text and "(2010年代)" in text           # 採用論文でない・引用でないものは残す
    found = [m for lvl, m in cli.check_survey(Survey.load("mw"), None)]
    assert any("Neumark" in m or "#3" in m for m in found), found


def test_check_compares_the_zotero_collections(ws, tmp_path):  # noqa: F811
    paper = make_project(tmp_path / "proj")
    ws("new", "mw", "--slug", "mw", "--manuscript", str(paper), "--json")
    s = Survey.load("mw")
    assert s.manuscript.startswith("proj/") or s.manuscript.startswith("../")
    s.set_zotero_collection("K1", "Other")
    s.save()
    found = [m for lvl, m in cli.check_survey(Survey.load("mw"), None)]
    assert any("Minimum wages" in m and "Other" in m for m in found), found


def test_a_manuscript_outside_the_workspace_is_kept_relative(tmp_path):
    from priorwork.survey import manuscript_ref
    (tmp_path / "ws").mkdir()
    paper = make_project(tmp_path / "proj")
    assert manuscript_ref(str(paper), tmp_path / "ws") == "../proj/papers/mw/paper.md"


def test_several_surveys_for_one_octavo_project(ws, tmp_path, capsys):  # noqa: F811
    from priorwork.octavo import within_collection
    assert within_collection("Minimum wages / Theory", "Minimum wages")
    assert within_collection("Research / Minimum wages / Theory", "minimum wages")      # 名前だけの指定
    assert within_collection("Minimum wages/Theory", "Minimum wages / Theory")
    assert not within_collection("Other / Theory", "Minimum wages")
    assert not within_collection("Research / Theory", "Research / Minimum wages")

    paper = make_project(tmp_path / "proj")
    ws("new", "mw theory", "--slug", "theory", "--manuscript", str(paper.parent), "--json")
    capsys.readouterr()
    cli.main(["new", "mw methods", "--slug", "methods", "--manuscript", str(paper.parent)])
    err = capsys.readouterr().err
    assert "theory" in err and "Minimum wages" in err and "--collection" in err  # サーベイごとに下のコレクションを
    s = Survey.load("methods")
    s.set_zotero_collection("K2", "Minimum wages / Methods")
    s.save()
    found = [m for lvl, m in cli.check_survey(Survey.load("methods"), None)]
    assert not any("Minimum wages / Methods" in m for m in found), found       # 下のコレクションなら食い違いではない
    capsys.readouterr()
    cli.main(["status", "methods"])
    assert "theory" in capsys.readouterr().out


def test_one_survey_for_several_octavo_projects(ws, tmp_path, fake_get, capsys):  # noqa: F811
    """1 つのテーマのサーベイを、いくつもの論文（Octavo のプロジェクト）で使う。"""
    a = make_project(tmp_path / "proj_a")
    b = make_project(tmp_path / "proj_b")
    (tmp_path / "proj_b" / "refs.bib").write_text(BIB.split("@article{dube2010")[0], encoding="utf-8")  # card だけ
    cfg = (tmp_path / "proj_b" / "octavo.config.py")
    cfg.write_text(cfg.read_text().replace("'zotero_collection': 'Minimum wages'",
                                           "'zotero_collection': ['Paper B', 'Surveys / Minimum wages']"))
    made = ws("new", "minimum wages", "--slug", "mw", "--json")
    linked = ws("scope", "mw", "--octavo", str(a.parent), "--octavo", str(tmp_path / "proj_b"), "--json")
    assert [p["name"] for p in linked["octavo_projects"]] == ["proj_a", "proj_b"]
    assert linked["octavo_projects"][1]["zotero_collections"] == ["Paper B", "Surveys / Minimum wages"]
    ws("add", "mw", "10.1/card", "10.1/dube", "--json")

    s = Survey.load("mw")
    md = s.md_path.read_text(encoding="utf-8")
    from priorwork.check import SYNTHESIS_MARK
    md = md.replace(SYNTHESIS_MARK, SYNTHESIS_MARK + "\nCard and Krueger (1994) found no fall (Dube et al., 2010).", 1)
    s.md_path.write_text(md, encoding="utf-8")
    with pytest.raises(SystemExit, match="proj_a"):                     # どのプロジェクトか決まらない
        cli.main(["export", "mw", "--octavo"])
    ws("export", "mw", "--octavo", "proj_a", "--json")
    got = ws("export", "mw", "--octavo", str(tmp_path / "proj_b"), "--json")
    assert [m["doi"] for m in got["missing"]] == ["10.1/dube"]          # proj_b の .bib には無い
    stem = Path(made["report"]).stem
    text_a = Path(made["report"]).with_name(f"{stem}.proj_a.octavo.md").read_text(encoding="utf-8")
    text_b = Path(made["report"]).with_name(f"{stem}.proj_b.octavo.md").read_text(encoding="utf-8")
    assert text_a.startswith("## ") and "@card1994 found no fall [@dube2010]." in text_a
    assert "[@PRIORWORK:Dube2010]" in text_b

    s = Survey.load("mw")
    s.set_zotero_collection("K", "Paper B / Theory")
    s.save()
    found = [m for lvl, m in cli.check_survey(Survey.load("mw"), None)]
    assert any("proj_a" in m and "Paper B / Theory" in m for m in found), found   # proj_a のコレクションとは違う
    assert not any("proj_b" in m and "Paper B / Theory" in m for m in found), found  # proj_b の並びの下にはある
    assert any("proj_b" in m and "#2" in m for m in found), found                 # 文章が引く論文が .bib に無い
    left = ws("scope", "mw", "--unlink-octavo", str(tmp_path / "proj_b"), "--json")["octavo_projects"]
    assert [p["name"] for p in left] == ["proj_a"]
