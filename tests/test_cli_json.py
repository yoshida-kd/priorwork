"""`--json` の出力。VS Code の拡張機能（vscode-extension/src/cli.ts）が読む形なので、キーを変えるときは両方を直す。"""

import json
import re
from pathlib import Path

import pytest

from priorwork import cli, scaffold, survey
from priorwork.api import from_openalex

from .conftest import openalex_work

EXT_TYPES = Path(__file__).resolve().parent.parent / "vscode-extension" / "src" / "cli.ts"


class FakeClient:
    def __init__(self, use_cache=True):
        pass

    def complete_abstracts(self, records):
        return records

    def search(self, query, limit=20, year=None, bulk=False):
        return [from_openalex(openalex_work(title=f"Paper number {i} on minimum wages", doi=f"10.1/{i}",
                                            wid=f"W{i}", citations=100 - i)) for i in range(3)]


@pytest.fixture
def ws(tmp_path, monkeypatch, capsys):
    scaffold.init(tmp_path)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "LiteratureClient", FakeClient)
    monkeypatch.setattr(survey, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(survey, "STATE_DIR", tmp_path / ".priorwork" / "surveys")

    def run(*argv, code=0):
        capsys.readouterr()
        try:
            cli.main(list(argv))
        except SystemExit as e:
            assert (e.code or 0) == code or (code and e.code), e.code
        return json.loads(capsys.readouterr().out)
    return run


def test_status_list_and_decisions(ws):
    top = ws("status", "--json")
    assert top["workspace"] and top["git"] == {"repo": True, "remote": False, "branch": top["git"]["branch"], "other_surveys": []} and top["surveys"] == [] and top["lang"] == "ja"

    made = ws("new", "最低賃金", "--slug", "mw", "--json")
    assert made["name"].endswith("_mw") and made["report"].endswith(".md") and made["lang"] == "ja"
    found = ws("search", "minimum wage", "--into", "mw", "--limit", "3", "--json")
    assert found["new"] == 3 and [a["number"] for a in found["added"]] == [1, 2, 3]

    changed = ws("include", "mw", "1", "2", "--json")
    assert [c["number"] for c in changed["changed"]] == [1, 2] and changed["changed"][0]["status"] == "included"
    ws("exclude", "mw", "3", "--reason", "off topic", "--json")

    top = ws("status", "--json")
    assert top["surveys"][0]["counts"] == {"candidate": 0, "included": 2, "excluded": 1, "maybe": 0}
    detail = ws("status", "mw", "--json")
    assert detail["unfilled"] == [1, 2] and detail["scope"]["question"] == ""
    assert [s["id"] for s in detail["next"]][:1] == ["scope"] and "check" in [s["id"] for s in detail["next"]]
    entries = ws("list", "mw", "--json")
    assert {e["number"]: e["status"] for e in entries} == {1: "included", 2: "included", 3: "excluded"}
    assert entries[2]["reason"] == "off topic" and entries[0]["record"]["abstract"]


def test_check_export_and_doctor(ws):
    ws("new", "t", "--slug", "mw", "--json")
    checked = ws("check", "mw", "--offline", "--json")
    assert checked["errors"] == 0 and all({"level", "message"} <= set(f) for f in checked["findings"])
    exported = ws("export", "mw", "--json")
    assert Path(exported["path"]).is_file() and exported["issues"]
    doctor = ws("doctor", "--json", code=None)
    assert doctor["version"] and {"level", "name", "message"} <= set(doctor["checks"][0])


def test_card_reads_and_writes(ws):
    ws("new", "t", "--slug", "mw", "--json")
    ws("search", "minimum wage", "--into", "mw", "--limit", "1", "--json")
    ws("include", "mw", "1", "--json")
    card = ws("card", "mw", "1", "--json")
    assert card["number"] == 1 and card["evidence"] == "unchecked"
    assert [o["key"] for o in card["evidence_options"]] == ["unchecked", "abstract", "fulltext"]
    assert {"key", "label", "value"} <= set(card["fields"][0]) and "evidence" not in [f["key"] for f in card["fields"]]
    card = ws("card", "mw", "1", "--set", "rq=Does employment fall?\nIn the short run", "evidence=fulltext", "--json")
    assert card["evidence"] == "fulltext"
    assert next(f["value"] for f in card["fields"] if f["key"] == "rq") == "Does employment fall?\nIn the short run"


def test_settings_reads_and_writes_through_stdin(ws, tmp_path, monkeypatch):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO('{"SEMANTIC_SCHOLAR_API_KEY": "abc", "ZOTERO_USER_ID": "42"}'))
    st = ws("settings", "--stdin", "--json")
    items = {i["key"]: i for i in st["items"]}
    assert items["SEMANTIC_SCHOLAR_API_KEY"]["set"] and items["SEMANTIC_SCHOLAR_API_KEY"]["value"] == ""
    assert items["ZOTERO_USER_ID"]["value"] == "42" and st["exists"] and st["ssci"]["file"] is None
    assert "abc" not in json.dumps(st)


def test_the_extension_reads_only_keys_the_cli_writes():
    """cli.ts の interface に書いたキーが、上のテストで確かめた JSON にあること（名前を変えたら両方直す）。"""
    if not EXT_TYPES.exists():
        pytest.skip("no extension in this tree")
    text = EXT_TYPES.read_text(encoding="utf-8")
    declared = {}
    for name, body in re.findall(r"export interface (\w+)(?: extends [\w, ]+)? \{(.*?)\n\}", text, re.S):
        declared[name] = set(re.findall(r"^\s+(\w+)\??:", body, re.M))
    expected = {
        "WorkspaceStatus": {"version", "root", "workspace", "lang", "git", "sync", "zotero", "zotero_write", "requests", "surveys", "archived"},
        "GitInfo": {"repo", "remote", "branch", "other_surveys"},
        "SurveySummary": {"name", "topic", "created", "version", "depth", "mode", "lang", "report", "manuscript", "purpose",
                          "zotero_collection", "archived", "counts", "searches"},
        "SurveyDetail": {"scope", "unfilled", "zotero_missing", "zotero_write", "zotero_written", "written_by", "audits", "octavo", "octavo_projects",
                         "sync", "next"},
        "OctavoProject": {"root", "name", "bib", "bib_exists", "zotero_collections", "manuscript", "missing"},
        "Audit": {"at", "by", "note", "included"},
        "ZoteroCollectionLink": {"key", "name"},
        "ZoteroCollections": {"collections"},
        "ZoteroCollection": {"key", "name", "path", "parent", "depth", "items", "total"},
        "ZoteroReport": {"survey", "collection", "papers", "missing_dois", "to_import", "imported", "no_doi",
                         "can_write", "dry_run", "written"},
        "ZoteroWrite": {"number", "title", "doi", "action", "key", "done", "error", "undo"},
        "NextStep": {"id", "text", "args"},
        "OctavoRequest": {"id", "from", "kind", "project", "manuscript", "text", "created_at", "status", "survey",
                          "done_at", "note"},
        "Entry": {"number", "key", "status", "reason", "found_by", "history", "record", "fulltext"},
        "PaperRecord": {"title", "authors", "year", "journal_name", "doi", "abstract", "tldr", "citation_count",
                        "ssci", "warnings", "url", "oa_pdf"},
        "CheckReport": {"findings", "errors", "warnings"},
        "DoctorReport": {"version", "root", "lang", "checks", "ng", "warn"},
        "ExportReport": {"path", "issues"},
        "SearchReport": {"query", "hits", "new", "added"},
        "Counts": {"candidate", "included", "excluded", "maybe"},
        "Scope": {"question", "years", "fields", "inclusion", "exclusion"},
        "Ssci": {"status", "badge", "tier"},
        "HistoryItem": {"at", "status", "reason", "migrated"},
        "FulltextInfo": {"path", "source", "pages", "chars", "page_markers", "version"},
        "Finding": {"level", "message"},
        "DoctorCheck": {"level", "name", "message"},
        "AddedPaper": {"number", "new", "status", "title"},
        "CardReport": {"number", "evidence", "evidence_options", "fields"},
        "CardField": {"key", "label", "value"},
        "EvidenceOption": {"key", "label"},
        "SettingsReport": {"env", "exists", "items", "ssci"},
        "SettingItem": {"key", "secret", "set", "value"},
        "SsciListInfo": {"file", "journals"},
    }
    for name, keys in expected.items():
        assert name in declared, name
        assert declared[name] <= keys, (name, declared[name] - keys)


def test_a_survey_from_a_manuscript(ws, tmp_path):
    (tmp_path / "paper.md").write_text("# 5. Results\n")
    made = ws("new", "t", "--slug", "mp", "--manuscript", str(tmp_path / "paper.md"), "--purpose", "draft", "--json")
    assert made["manuscript"] == "paper.md"
    ws("search", "minimum wage", "--into", "mp", "--limit", "1", "--json")
    ws("include", "mp", "1", "--json")
    detail = ws("status", "mp", "--json")
    assert detail["manuscript"] == "paper.md" and "draft" in [s["id"] for s in detail["next"]]
    card = ws("card", "mp", "1", "--set", "role=C1 supports", "--json")
    assert next(f["value"] for f in card["fields"] if f["key"] == "role") == "C1 supports"
    with pytest.raises(SystemExit) as e:   # まだ下書きが無い
        cli.main(["export", "mp", "--draft", "--json"])
    assert "not written yet" in str(e.value) or "まだ" in str(e.value)
    assert ws("status", "--json")["surveys"][0]["manuscript"] == "paper.md"


def test_archive_hides_a_survey_and_brings_it_back(ws, capsys):
    first = ws("new", "行政需要", "--slug", "mob", "--json")["name"]
    capsys.readouterr()
    cli.main(["new", "行政需要", "--slug", "mob", "--json"])   # やり直し: 同じ slug で作ると版が付く
    assert "mob" in capsys.readouterr().err             # 同じテーマがあると知らせる
    top = ws("status", "--json")
    assert [s["name"].split("_", 1)[1] for s in top["surveys"]] == ["mob", "v2_mob"] and top["archived"] == []
    assert [s["version"] for s in top["surveys"]] == [1, 2]
    assert top["zotero"] is False and top["surveys"][0]["zotero_collection"] is None
    assert ws("archive", first, "--json")["archived"]
    top = ws("status", "--json")
    assert [s["name"].split("_", 1)[1] for s in top["surveys"]] == ["v2_mob"]
    assert top["archived"][0]["archived"] and ws("status", first, "--json")["archived"]
    assert ws("archive", first, "--undo", "--json")["archived"] is None
    assert len(ws("status", "--json")["surveys"]) == 2


def test_audit_must_be_by_another_model(ws):
    name = ws("new", "t", "--slug", "au", "--by", "Gemini 3.8 Flash", "--json")["name"]
    with pytest.raises(SystemExit, match="Gemini 3.8 Flash"):        # 書いたモデルは監査できない
        cli.main(["audit", name, "--by", "gemini-3.8-flash"])
    assert ws("status", name, "--json")["audits"] == []
    audit = ws("audit", name, "--by", "Claude Opus 5.5", "--note", "カードを本文と突き合わせた", "--json")
    assert audit["by"] == "Claude Opus 5.5" and audit["included"] == 0
    detail = ws("status", name, "--json")
    assert detail["written_by"] == ["Gemini 3.8 Flash"] and detail["audits"][0]["note"] == "カードを本文と突き合わせた"
    assert ws("audit", name, "--json")["audits"][0]["by"] == "Claude Opus 5.5"


def test_list_with_abstracts_and_fix(ws, capsys):
    ws("new", "t", "--slug", "fx", "--json")
    ws("search", "minimum wage", "--into", "fx", "--limit", "1", "--json")
    capsys.readouterr()
    cli.main(["list", "fx", "--abstract"])               # 差し込み口 {text} が t() の引数とぶつからない
    assert "Paper number 0" in capsys.readouterr().out
    fixed = ws("fix", "fx", "1", "--authors", "Yuen Yuen Ang", "--year", "2023", "--confirm", "出版社のページで確認", "--json")
    assert fixed["record"]["authors"] == ["Yuen Yuen Ang"] and fixed["record"]["year"] == 2023
    assert fixed["fixed"] == {"authors": ["Yuen Yuen Ang"], "year": 2023} and fixed["confirmed"]["reason"]
    assert ws("list", "fx", "--json")[0]["record"]["authors"] == ["Yuen Yuen Ang"]


def test_surveys_on_other_branches_are_shown(ws, tmp_path, capsys):
    import subprocess

    def git(*a):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *a], cwd=tmp_path, check=True,
                       capture_output=True)
    git("commit", "--allow-empty", "-q", "-m", "init")
    git("branch", "20261001_statutes")                   # 別のブランチで進んでいるサーベイ
    top = ws("status", "--json")
    assert top["git"]["other_surveys"] == ["20261001_statutes"] and top["git"]["branch"]
    with pytest.raises(SystemExit, match="git switch 20261001_statutes"):
        cli.main(["status", "statutes"])


def test_standard_mode_stops_before_the_cards_until_the_user_says_go_on(ws):
    ws("new", "t", "--slug", "md", "--json")
    ws("search", "minimum wage", "--into", "md", "--limit", "2", "--json")
    ws("include", "md", "1", "2", "--json")
    detail = ws("status", "md", "--json")
    ids = [s["id"] for s in detail["next"]]
    assert detail["mode"] == "standard" and ids.index("wait_zotero") < ids.index("fill")
    assert ws("scope", "md", "--go-on", "--json")["mode"] == "standard"
    assert "wait_zotero" not in [s["id"] for s in ws("status", "md", "--json")["next"]]

    ws("new", "t2", "--slug", "au", "--mode", "auto", "--json")
    ws("search", "minimum wage", "--into", "au", "--limit", "1", "--json")
    ws("include", "au", "1", "--json")
    detail = ws("status", "au", "--json")
    assert detail["mode"] == "auto" and "wait_zotero" not in [s["id"] for s in detail["next"]]
    assert "audit" not in [s["id"] for s in detail["next"]]          # 監査は任意（次にやることに出さない）
    assert ws("scope", "au", "--mode", "manual", "--json")["mode"] == "manual"


def test_a_survey_that_advises_on_a_manuscript(ws, tmp_path):
    (tmp_path / "paper.md").write_text("# Paper\n")
    made = ws("new", "t", "--slug", "adv", "--manuscript", str(tmp_path / "paper.md"), "--purpose", "advice", "--json")
    assert made["purpose"] == "advice"
    report = Path(made["report"]).read_text(encoding="utf-8")
    assert "原稿への助言" in report and "priorwork:draft" not in report
    ws("search", "minimum wage", "--into", "adv", "--limit", "1", "--json")
    ws("include", "adv", "1", "--json")
    ids = [s["id"] for s in ws("status", "adv", "--json")["next"]]
    assert "advice" in ids and "draft" not in ids
    # 同じ原稿から、補完のサーベイ（目的を省いたときの既定）も別に作れる
    filled = ws("new", "t", "--slug", "fill", "--manuscript", str(tmp_path / "paper.md"), "--json")
    assert filled["purpose"] == "complete" and filled["manuscript"] == made["manuscript"]
    report = Path(filled["report"]).read_text(encoding="utf-8")
    assert "原稿の補完" in report and "priorwork:draft" in report and "原稿の欠けの地図" in report
    with pytest.raises(SystemExit):
        cli.main(["new", "t", "--slug", "x", "--purpose", "advice"])          # 原稿が無い


def test_zotero_dois_without_zotero_lists_every_included_paper(ws, capsys):
    ws("new", "t", "--slug", "zd", "--json")
    ws("search", "minimum wage", "--into", "zd", "--limit", "2", "--json")
    ws("include", "zd", "1", "--json")
    capsys.readouterr()
    cli.main(["zotero", "zd", "--dois"])
    out = capsys.readouterr().out.split()
    assert len(out) == 1 and out[0].startswith("10.")


def test_requests_from_octavo(ws, tmp_path):
    """Octavo が .priorwork/requests/ に置いた依頼を一覧にし、結果を書き込む（Octavo が書いた欄はそのまま）。"""
    sample = json.loads((Path(__file__).parent / "fixtures" / "request.json").read_text(encoding="utf-8"))
    d = tmp_path / ".priorwork" / "requests"
    d.mkdir(parents=True)
    (d / f"{sample['id']}.json").write_text(json.dumps(sample), encoding="utf-8")
    (d / "broken.json").write_text("{", encoding="utf-8")                     # 読めないものは飛ばす
    (d / "other.json").write_text('{"format": "something-else"}', encoding="utf-8")
    st = ws("status", "--json")
    assert [r["id"] for r in st["requests"]] == [sample["id"]] and st["requests"][0]["kind"] == "start"
    assert set(st["requests"][0]) == set(sample) - {"format", "version"}
    assert ws("requests", "2026", "--json")["text"] == sample["text"]      # id の先頭だけでよい
    ws("new", "t", "--slug", "mob", "--json")
    done = ws("requests", sample["id"], "--done", "--survey", "mob", "--note", "made a survey", "--json")
    assert done["status"] == "done" and done["survey"] == "mob" and done["done_at"]
    on_disk = json.loads((d / f"{sample['id']}.json").read_text(encoding="utf-8"))
    assert {k: on_disk[k] for k in ("format", "project", "text", "created_at")} == \
        {k: sample[k] for k in ("format", "project", "text", "created_at")}
    assert ws("status", "--json")["requests"] == [] and len(ws("requests", "--all", "--json")["requests"]) == 1
