import pytest

from priorwork import ssci


@pytest.mark.parametrize("journal,issns,types,source_type,expected", [
    ("Social Science Research Network", [], [], "", ssci.PREPRINT),
    ("SSRN Electronic Journal", ["1556-5068"], ["preprint"], "repository", ssci.PREPRINT),
    ("National Bureau of Economic Research", [], ["report"], "repository", ssci.PREPRINT),
    ("Thesis Eleven", ["0725-5136"], ["article"], "journal", ssci.JOURNAL),  # "thesis" を WP と誤認しない
    ("IZA Journal of Labor Economics", ["2193-8997"], ["article"], "journal", ssci.JOURNAL),
    ("The American Economic Review", ["0002-8282"], ["JournalArticle"], "journal", ssci.SSCI_LIKELY),
    ("PLOS ONE", ["1932-6203"], ["article"], "journal", ssci.JOURNAL),
    ("Cambridge University Press eBooks", [], ["book"], "ebook platform", ssci.BOOK),
    ("", [], [], "", ssci.UNKNOWN),
])
def test_classify_without_list(journal, issns, types, source_type, expected):
    assert ssci.classify(journal, issns, types, source_type)[0] == expected


def test_classify_with_journal_list(tmp_path, monkeypatch):
    csv = tmp_path / "Social Sciences Citation Index (SSCI).csv"
    csv.write_text('﻿"Journal title","ISSN","eISSN"\n'
                   '"AMERICAN ECONOMIC JOURNAL-APPLIED ECONOMICS","1945-7782","1945-7790"\n'
                   '"SERIES-JOURNAL OF THE SPANISH ECONOMIC ASSOCIATION","1869-4187","1869-4195"\n', encoding="utf-8")
    monkeypatch.setattr(ssci, "_list_cache", ssci.SSCIJournalList(csv))

    # 誌名の表記揺れ（コロン / ハイフン）は正規化で吸収
    assert ssci.classify("American Economic Journal: Applied Economics", [])[0] == ssci.SSCI
    # 誌名が違っても ISSN で一致
    assert ssci.classify("SERIEs", ["1869-4195"], source_type="journal")[0] == ssci.SSCI
    assert ssci.classify("PLOS ONE", ["1932-6203"], source_type="journal")[0] == ssci.NOT_SSCI


def test_list_autodetects_downloaded_filename(tmp_path, monkeypatch):
    (tmp_path / "Social Sciences Citation Index (SSCI).csv").write_text('"Journal title","ISSN"\n"ECONOMETRICA","0012-9682"\n')
    monkeypatch.setattr(ssci, "DEFAULT_SSCI_LIST", tmp_path / "ssci_journals.csv")
    monkeypatch.setattr(ssci, "_list_cache", None)
    monkeypatch.delenv("SSCI_JOURNAL_LIST", raising=False)
    assert ssci.get_ssci_list().loaded
    assert ssci.classify("Econometrica", [])[0] == ssci.SSCI


def test_same_title_with_another_issn_is_not_ssci(tmp_path, monkeypatch):
    """同名の別誌（ISSN が違う）を誌名だけで SSCI と判定しない。"""
    csv = tmp_path / "ssci.csv"
    csv.write_text('"Journal title","ISSN","eISSN"\n"PUBLIC POLICY AND ADMINISTRATION","0952-0767","1749-4192"\n',
                   encoding="utf-8")
    monkeypatch.setattr(ssci, "_list_cache", ssci.SSCIJournalList(csv))
    assert ssci.classify("Public Policy and Administration", ["0952-0767"], source_type="journal")[0] == ssci.SSCI
    # リトアニアの同名誌（ISSN が違う）
    assert ssci.classify("Public Policy and Administration", ["1648-2603", "2029-2872"],
                         source_type="journal")[0] == ssci.NOT_SSCI
    # ISSN が分からないときだけ誌名で照合する
    assert ssci.classify("Public Policy and Administration", [], source_type="journal")[0] == ssci.SSCI


def test_render_reclassifies_with_the_list(tmp_path, monkeypatch, oa_record):
    from priorwork.survey import INCLUDED, Survey
    s = Survey.create("t", "t", {})
    rec = oa_record(journal="Public Policy and Administration", issns=("1648-2603",))
    rec["ssci"] = {"status": ssci.SSCI, "badge": ssci.BADGE[ssci.SSCI], "tier": ssci.TIER[ssci.SSCI]}  # 古い誤判定
    s.upsert(rec, "test", INCLUDED)
    s.save()
    s.render()
    assert Survey.load(s.name).papers[0]["record"]["ssci"]["status"] == ssci.SSCI  # リストが無ければ触らない

    csv = tmp_path / "ssci.csv"
    csv.write_text('"Journal title","ISSN"\n"PUBLIC POLICY AND ADMINISTRATION","0952-0767"\n', encoding="utf-8")
    monkeypatch.setattr(ssci, "_list_cache", ssci.SSCIJournalList(csv))
    s = Survey.load(s.name)
    s.render()
    assert Survey.load(s.name).papers[0]["record"]["ssci"]["status"] == ssci.NOT_SSCI
    assert ssci.badge(ssci.NOT_SSCI) in s.md_path.read_text(encoding="utf-8")
