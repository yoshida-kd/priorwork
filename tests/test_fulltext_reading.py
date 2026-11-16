"""本文を読む量を減らす: 参照文献の節を分ける・目次とページと語で読む・ほかのサーベイの本文を使う・PDF の道具。"""
import json

import pytest

from priorwork import cli, fulltext, scaffold, survey
from priorwork.api import from_openalex
from priorwork.survey import INCLUDED, Survey

from .conftest import openalex_work

REFS = "\n".join(f"Author{i}, A. ({1990 + i}). A study of things number {i}. Journal of Studies, {i}(2), 1-20."
                 for i in range(20))
TEXT = ("=== page 1 ===\n\nThe Journal of Studies 12\nAbstract\nWe study things.\n1. Introduction\n"
        + "Intro text. " * 200
        + "\n\n=== page 2 ===\n\nThe Journal of Studies 13\n2. Data and Methods\nWe use 1,234 municipalities.\n"
        + "Table 1 Summary statistics\nN = 1,234\n" + "Method text. " * 200
        + "\n\n=== page 3 ===\n\nThe Journal of Studies 14\n3. Results\nThe effect is 0.27 (p < 0.05).\n"
        + "Results text. " * 200 + "\nReferences\n" + REFS[:1200]
        + "\n\n=== page 4 ===\n\nThe Journal of Studies 15\n" + REFS[1200:]
        + "\nAppendix A. Additional tables\nTable A1 Robustness\nN = 999\n")


def test_the_references_are_kept_apart_and_the_pages_stay():
    body, refs = fulltext.split_references(TEXT)
    assert "Author3, A. (1993)" in refs and "Author3" not in body
    assert "Appendix A. Additional tables" in body and "N = 999" in body          # 後ろの付録は残す
    assert [p for p, _ in fulltext.pages_of(body)] == [1, 2, 3, 4]
    assert "=== page" not in refs and fulltext.REFS_NOTE in body


def test_a_text_without_a_references_section_is_left_alone():
    text = "=== page 1 ===\n\nReferences\nnot really\n" + "x " * 400
    assert fulltext.split_references(text) == (text, "")


def test_outline_lists_headings_and_captions_without_running_heads():
    items = fulltext.outline(TEXT)
    texts = [(i["page"], i["text"]) for i in items]
    assert (1, "1. Introduction") in texts and (2, "2. Data and Methods") in texts and (3, "3. Results") in texts
    assert (2, "Table 1 Summary statistics") in texts
    assert not any("Journal of Studies" in x for _, x in texts)


def test_pages_and_grep():
    assert "1,234 municipalities" in fulltext.read_pages(TEXT, "2") and "Intro text" not in fulltext.read_pages(TEXT, "2")
    hits = fulltext.grep(TEXT, r"N = \d")
    assert [h["page"] for h in hits][:1] == [2]
    with pytest.raises(fulltext.FulltextError):
        fulltext.parse_page_range("five")


def test_the_engine_falls_back_to_pypdf(monkeypatch):
    monkeypatch.setattr(fulltext, "docling_available", lambda: False)
    monkeypatch.delenv("PRIORWORK_PDF_ENGINE", raising=False)
    assert fulltext.pdf_engine() == "pypdf"
    monkeypatch.setenv("PRIORWORK_PDF_ENGINE", "docling")
    with pytest.raises(fulltext.FulltextError):
        fulltext.pdf_engine()
    monkeypatch.setattr(fulltext, "docling_available", lambda: True)
    assert fulltext.pdf_engine() == "docling"
    monkeypatch.setenv("PRIORWORK_PDF_ENGINE", "pypdf")
    assert fulltext.pdf_engine() == "pypdf"


def test_a_docling_failure_reads_it_with_pypdf(monkeypatch):
    def broken(pdf):
        raise RuntimeError("no model")
    monkeypatch.setattr(fulltext, "_extract_docling", broken)
    monkeypatch.setattr(fulltext, "_extract_pypdf", lambda pdf: ("=== page 1 ===\n\ntext", 1))
    assert fulltext.extract_text(b"%PDF", "docling") == ("=== page 1 ===\n\ntext", 1)
    assert fulltext.last_engine == "pypdf"


# ---- CLI ----

@pytest.fixture
def ws(tmp_path, monkeypatch, capsys):
    scaffold.init(tmp_path)
    monkeypatch.setattr(survey, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(survey, "STATE_DIR", tmp_path / ".priorwork" / "surveys")
    monkeypatch.setattr(fulltext, "FULLTEXT_DIR", tmp_path / "ft")

    def make(name):
        s = Survey.create("t", name, {})
        rec = from_openalex(openalex_work(doi="10.1/same", title="A study of things"))
        rec["pages"] = ""
        s.upsert(rec, "search", status=INCLUDED)
        s.save()
        s.render()
        return s

    def run(*argv, code=0):
        capsys.readouterr()
        try:
            cli.main(list(argv))
        except SystemExit as e:
            assert bool(e.code) == bool(code), e.code
        return capsys.readouterr()
    run.make = make
    return run


def fetched(monkeypatch, calls):
    def fake(entry, client, pdf_path=None, out_dir=None, zotero=None):
        calls.append(entry["key"])
        out = fulltext.FULLTEXT_DIR / f"{entry['number']:03d}.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        saved = fulltext.save_text(TEXT, out)
        return {"path": str(out), "source": "file:x", "pages": 4, "chars": saved["chars"], "page_markers": True,
                "version": "", "working_paper": False, "references_chars": saved["references_chars"],
                "extractor": "pypdf"}
    monkeypatch.setattr(cli, "fetch_fulltext", fake)


def test_reading_the_saved_full_text_by_parts(ws, monkeypatch):
    calls = []
    fetched(monkeypatch, calls)
    s = ws.make("one")
    out = ws("fulltext", s.name, "1").out
    assert "--outline" in out and "参照文献" in out
    assert "2. Data and Methods" in ws("fulltext", s.name, "1", "--outline").out
    assert "0.27" in ws("fulltext", s.name, "1", "--pages", "3").out
    hits = json.loads(ws("fulltext", s.name, "1", "--grep", "municipalities", "--json").out)["hits"]
    assert hits[0]["page"] == 2
    assert "Author3, A. (1993)" in ws("fulltext", s.name, "1", "--references").out
    assert calls == [s.get(1)["key"]]                     # 読むだけなら取り直さない


def test_reading_before_fetching_says_how(ws):
    s = ws.make("none")
    with pytest.raises(SystemExit) as e:
        cli.main(["fulltext", s.name, "1", "--outline"])
    assert "priorwork fulltext" in str(e.value.code)


def test_a_text_saved_before_the_split_is_split_when_read(ws, tmp_path):
    s = ws.make("old")
    path = tmp_path / "old.txt"
    path.write_text(TEXT, encoding="utf-8")
    s.get(1)["fulltext"] = {"path": str(path), "source": "file:x", "pages": 4, "chars": len(TEXT), "page_markers": True}
    s.save()
    assert "Author3" in ws("fulltext", s.name, "1", "--references").out
    assert "Author3" not in path.read_text(encoding="utf-8")


def test_another_surveys_full_text_is_used(ws, monkeypatch):
    calls = []
    fetched(monkeypatch, calls)
    first, second = ws.make("first"), ws.make("second")
    ws("fulltext", first.name, "1")
    done = ws("fulltext", second.name, "1")
    assert "first" in done.err and len(calls) == 1
    assert Survey.load(second.name).get(1)["fulltext"]["path"] == Survey.load(first.name).get(1)["fulltext"]["path"]
    ws("fulltext", second.name, "1", "--refresh")
    assert len(calls) == 2


def test_docling_markdown_is_compacted():
    md = "| A     | B    |\n|-------|------|\n| 1     | 2    |\n\n<!-- image -->\n\n\n\nText"
    assert fulltext.compact_markdown(md) == "| A | B |\n|---|---|\n| 1 | 2 |\n\nText"
