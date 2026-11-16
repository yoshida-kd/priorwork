"""実際のサーベイ（政策の波及、採用201本）から報告された点: 小文字の前置詞でつながる姓、検索から入った論文の
掲載号の年（include で直す・`fix --issue-years` でまとめて直す）。"""
import json

import pytest

from priorwork import check, cli, scaffold, survey
from priorwork.api import from_openalex
from priorwork.survey import CANDIDATE, Survey

from .conftest import openalex_work

ISSUE_YEARS = {"10.1/early": 2019, "10.1/same": 2018}


class Client:
    issue_years_failed = False

    def __init__(self, use_cache=True):
        pass

    def openalex_works(self, dois, select=""):
        return [{"doi": "https://doi.org/" + d, "title": f"Paper {d}"} for d in dois]

    def issue_years(self, dois):
        return {d: ISSUE_YEARS[d] for d in dois if d in ISSUE_YEARS}


@pytest.fixture
def ws(tmp_path, monkeypatch, capsys):
    scaffold.init(tmp_path)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "LiteratureClient", Client)
    monkeypatch.setattr(survey, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(survey, "STATE_DIR", tmp_path / ".priorwork" / "surveys")
    s = Survey.create("t", "fugu", {})
    for doi, year in (("10.1/early", 2018), ("10.1/same", 2018), ("10.1/novol", 2018)):
        rec = from_openalex(openalex_work(doi=doi, wid="W" + doi[-3:], title=f"Paper {doi}", year=year))
        rec["volume"] = "" if doi == "10.1/novol" else "12"
        s.upsert(rec, "search", status=CANDIDATE)
    s.save()
    s.render()

    def run(*argv, code=0):
        capsys.readouterr()
        try:
            cli.main(list(argv))
        except SystemExit as e:
            assert bool(e.code) == bool(code), e.code
        return capsys.readouterr().out
    run.name = s.name
    return run


def years(name):
    return {e["record"]["doi"]: (e["record"]["year"], e["record"].get("online_year"), "year" in (e.get("fixed") or {}))
            for e in Survey.load(name).papers}


def test_include_sets_the_year_of_the_journal_issue(ws):
    out = ws("include", ws.name, "1", "2", "3")
    assert "2019" in out
    assert years(ws.name) == {"10.1/early": (2019, 2018, False), "10.1/same": (2018, None, False),
                              "10.1/novol": (2018, None, False)}


def test_fix_issue_years_applies_what_check_suggests(ws):
    s = Survey.load(ws.name)
    s.set_status([1, 2, 3], survey.INCLUDED)
    s.save()
    s.render()
    assert any("--issue-years" not in m and "--year 2019" in m for _, m in check.check_survey(Survey.load(ws.name), Client()))

    dry = json.loads(ws("fix", ws.name, "--issue-years", "--dry-run", "--json"))
    assert dry["years"] == [{"number": 1, "title": "Paper 10.1/early", "from": 2018, "to": 2019}] and dry["dry_run"]
    assert years(ws.name)["10.1/early"] == (2018, None, False)

    ws("fix", ws.name, "--issue-years")
    assert years(ws.name)["10.1/early"] == (2019, 2018, True)
    assert not [m for _, m in check.check_survey(Survey.load(ws.name), Client()) if "2019" in m]
    assert "掲載号の年です" in ws("fix", ws.name, "--issue-years")


def test_fix_needs_a_number_or_issue_years(ws):
    ws("fix", ws.name, "--year", "2020", code=1)


def test_check_suggests_the_bulk_fix_when_several_years_differ(ws, monkeypatch):
    monkeypatch.setitem(ISSUE_YEARS, "10.1/same", 2019)
    s = Survey.load(ws.name)
    s.set_status([1, 2], survey.INCLUDED)
    s.save()
    s.render()
    infos = [m for lv, m in check.check_survey(Survey.load(ws.name), Client()) if lv == check.INFO]
    assert any(f"fix {ws.name} --issue-years" in m and "2 本" in m for m in infos), infos


@pytest.mark.parametrize("a, b, same", [
    ("Policy diffusion: Seven lessons for scholars and practitioners", "Policy Diffusion", False),   # 主題が短い
    ("Learning from neighbours: Policy diffusion among cities", "Learning from Neighbours", True),
    ("Learning from neighbours: Policy diffusion among cities", "Learning from neighbours: A reply", False),
    ("Learning from neighbours", "Learning from strangers: Policy diffusion", False),
    ("Why do cities copy each other? Evidence from Japan", "Why do cities copy each other", True),
])
def test_same_main_title(a, b, same):
    from priorwork import ssci
    assert ssci.same_main_title(a, b) is same


def doi_findings(ws, title, works=True, warning=None):
    s = Survey.load(ws.name)
    s.set_status([2], survey.INCLUDED)
    if warning:
        s.get(2)["record"]["warnings"] = [warning]
    s.save()
    s.render()

    class C(Client):
        def openalex_works(self, dois, select=""):
            return [{"doi": "https://doi.org/" + d, "title": title} for d in dois] if works else []
    return [(lv, m) for lv, m in check.check_survey(Survey.load(ws.name), C()) if "#2" in m and "DOI" in m]


def test_a_subtitle_only_difference_is_info(ws):
    found = doi_findings(ws, "Paper 10.1/same: The subtitle the database adds")
    assert [lv for lv, _ in found] == [check.INFO] and "副題だけ" in found[0][1]


def test_another_title_is_still_an_error(ws):
    assert [lv for lv, _ in doi_findings(ws, "Something else entirely on taxes")] == [check.ERROR]


def test_a_doi_unknown_to_openalex_is_a_warning_with_the_way_to_check(ws):
    found = doi_findings(ws, "", works=False)
    assert [lv for lv, _ in found] == [check.WARN] and "priorwork get 10.1/same" in found[0][1]


def test_a_recorded_subtitle_warning_is_read_back_as_info(ws):
    found = doi_findings(ws, "Paper 10.1/same", warning='DOI が別タイトルを指している: "Paper 10.1/same: A subtitle"（DOI 要確認）')
    assert check.ERROR not in [lv for lv, _ in found] and any("副題だけ" in m for _, m in found)


# ---- 2. 確かめた WARN の記録 ----

def test_a_checked_warning_is_recorded_and_hidden(ws):
    s = Survey.load(ws.name)
    s.set_status([2], survey.INCLUDED)
    s.save()
    s.render()
    findings = [("WARN", "#2: 345 in the card is not in the full text"), ("WARN", "#2: something else"),
                ("WARN", "#20: 345 too"), ("ERROR", "#2: 345 error")]
    ws("fix", ws.name, "2", "--confirm-warning", "345", "--reason", "Table 3 gives 345 as 3.45e2")
    entry = Survey.load(ws.name).get(2)
    assert entry["checked_warnings"][0]["match"] == "345" and "Table 3" in entry["checked_warnings"][0]["reason"]
    kept = check._without_checked_warnings(Survey.load(ws.name), findings)
    assert ("WARN", "#2: something else") in kept and ("WARN", "#20: 345 too") in kept and ("ERROR", "#2: 345 error") in kept
    assert not any(m.startswith("#2: 345 in") for _, m in kept) and any(lv == "INFO" and "#2" in m for lv, m in kept)
    ws("fix", ws.name, "2", "--confirm-warning", "345", code=1)            # 理由が要る
    ws("fix", ws.name, "2", "--confirm-warning", "345", "--reason", "")    # 空の理由で消す
    assert "checked_warnings" not in Survey.load(ws.name).get(2)


# ---- 8. 文献の言語 ----

def test_languages_in_the_scope_reach_the_report(ws):
    md = Survey.load(ws.name).md_path
    assert "文献の言語" not in md.read_text(encoding="utf-8")
    ws("scope", ws.name, "--languages", "英語のみ。日本語の文献は対象外")
    assert "- **文献の言語**: 英語のみ。日本語の文献は対象外" in md.read_text(encoding="utf-8")


# ---- 6. サーベイの無いワークスペース ----

def test_status_and_doctor_notice_an_octavo_only_workspace(tmp_path, monkeypatch, capsys):
    from priorwork import doctor
    scaffold.init(tmp_path)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(survey, "STATE_DIR", tmp_path / ".priorwork" / "surveys")
    (tmp_path / "projects" / "jpo").mkdir(parents=True)
    (tmp_path / "projects" / "jpo" / "octavo.config.py").write_text("CONFIG = {}\n")
    cli.main(["status"])
    assert "projects/jpo" in capsys.readouterr().out
    notes = [m for lv, name, m in doctor.run_checks(tmp_path) if "projects/jpo" in m]
    assert notes and "AGENTS.md" in notes[0]


# ---- 7. 分かれた Octavo のプロジェクト ----

def test_a_split_octavo_project_is_relinked(ws, tmp_path):
    for name in ("two_shocks", "reorg", "hiring"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "octavo.config.py").write_text("CONFIG = {}\n")
    ws("scope", ws.name, "--octavo", str(tmp_path / "two_shocks"))
    (tmp_path / "two_shocks" / "octavo.config.py").unlink()
    (tmp_path / "two_shocks").rmdir()
    warns = [m for lv, m in check.check_survey(Survey.load(ws.name)) if "--unlink-octavo" in m]
    assert warns and str(tmp_path / "two_shocks") in warns[0]
    ws("scope", ws.name, "--octavo", str(tmp_path / "reorg"), "--octavo", str(tmp_path / "hiring"),
       "--unlink-octavo", str(tmp_path / "two_shocks"))
    assert sorted(p["name"] for p in Survey.load(ws.name).octavo_projects) == ["hiring", "reorg"]


# ---- D. 別のサーベイの直しを引き継ぐ ----

def test_corrections_in_another_survey_are_carried_over(tmp_path):
    from priorwork.api import from_openalex as oa
    kw = dict(reports_dir=tmp_path / "r", state_dir=tmp_path / "s")
    first = Survey.create("t", "first", {}, **kw)
    e, _ = first.upsert(oa(openalex_work(doi="10.1/x", title="A paper on cities", year=2018)), "search")
    e["record"]["warnings"] = ["DOI not verified"]
    first.fix_record(e["number"], year=2019, authors=["Van de Ven, Andrew H."], confirm="checked the publisher's page")
    w, _ = first.upsert(oa(openalex_work(doi="10.1/wp", wid="W9", title="A working paper", year=2017)), "search")
    first.replace_record(w, oa(openalex_work(doi="10.1/pub", wid="W10", title="A working paper", year=2018)))
    first.save()

    second = Survey.create("t", "second", {}, **kw)
    rec = oa(openalex_work(doi="10.1/x", title="A paper on cities", year=2018))
    rec["warnings"] = ["DOI not verified", "Another warning"]
    got, _ = second.upsert(rec, "search")
    r = got["record"]
    assert (r["year"], r["authors"]) == (2019, ["Andrew H. Van de Ven"]) and got["fixed"]["year"] == 2019
    assert r["warnings"] == ["Another warning"] and "checked the publisher's page" in got["confirmed"]["reason"]
    assert got["inherited_from"] == first.name and any("引き継ぎ" in n for n in r["notes"])
    wp, _ = second.upsert(oa(openalex_work(doi="10.1/wp", wid="W9", title="A working paper", year=2017)), "search")
    assert any("10.1/pub" in n and "--id 10.1/pub" in n for n in wp["record"]["notes"])
    plain, _ = second.upsert(oa(openalex_work(doi="10.1/other", wid="W11", title="Untouched")), "search")
    assert "inherited_from" not in plain and not plain["record"]["notes"]
