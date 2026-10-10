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
    assert top["workspace"] and top["git"] == {"repo": True, "remote": False} and top["surveys"] == [] and top["lang"] == "ja"

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
        "WorkspaceStatus": {"version", "root", "workspace", "lang", "git", "sync", "zotero", "surveys", "archived"},
        "GitInfo": {"repo", "remote"},
        "SurveySummary": {"name", "topic", "created", "depth", "lang", "report", "manuscript", "zotero_collection",
                          "archived", "counts", "searches"},
        "SurveyDetail": {"scope", "unfilled", "zotero_missing", "sync", "next"},
        "ZoteroCollectionLink": {"key", "name"},
        "ZoteroCollections": {"collections"},
        "ZoteroCollection": {"key", "name", "path", "items"},
        "ZoteroReport": {"survey", "collection", "papers", "missing_dois", "to_import", "imported", "no_doi"},
        "NextStep": {"id", "text", "args"},
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
        "FulltextInfo": {"path", "source", "pages", "chars", "page_markers"},
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
    made = ws("new", "t", "--slug", "mp", "--manuscript", str(tmp_path / "paper.md"), "--json")
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
    ws("new", "行政需要", "--slug", "mob", "--json")
    capsys.readouterr()
    cli.main(["new", "行政需要", "--slug", "mob_v2", "--json"])
    assert "mob" in capsys.readouterr().err             # 同じテーマがあると知らせる
    top = ws("status", "--json")
    assert [s["name"].split("_", 1)[1] for s in top["surveys"]] == ["mob", "mob_v2"] and top["archived"] == []
    assert top["zotero"] is False and top["surveys"][0]["zotero_collection"] is None
    assert ws("archive", "mob", "--json")["archived"]
    top = ws("status", "--json")
    assert [s["name"].split("_", 1)[1] for s in top["surveys"]] == ["mob_v2"]
    assert top["archived"][0]["archived"] and ws("status", "mob", "--json")["archived"]
    assert ws("archive", "mob", "--undo", "--json")["archived"] is None
    assert len(ws("status", "--json")["surveys"]) == 2
