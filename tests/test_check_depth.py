from priorwork.check import INFO, WARN, check_survey
from priorwork.survey import INCLUDED, Survey


def survey_with_abstract_only_card(depth, s2_record):
    s = Survey.create("最低賃金", "mw", {"question": "q"}, depth=depth)
    s.upsert(s2_record(doi="10.1/a", title="Minimum wages study"), "search", status=INCLUDED)
    s.save()
    s.render()
    md = s.md_path.read_text(encoding="utf-8").replace("**確認レベル**: 未確認", "**確認レベル**: 要旨のみ")
    s.md_path.write_text(md, encoding="utf-8")
    return s


def depth_findings(s):
    return [f for f in check_survey(s) if "深さ" in f[1]]


def test_full_survey_is_told_to_snowball_and_verify_full_texts(s2_record):
    s = survey_with_abstract_only_card("full", s2_record)
    found = depth_findings(s)
    assert [level for level, _ in found] == [WARN, WARN] and "本文を試さずに" in found[1][1]

    s.log_search("snowball", "x", {}, hits=1, new=0)
    assert [level for level, _ in depth_findings(s)] == [WARN]


def full_text_findings(s):
    return [f for f in check_survey(s) if "#1" in f[1] and "本文" in f[1]]


def test_full_survey_tells_untried_fetched_and_unavailable_full_texts_apart(s2_record):
    s = survey_with_abstract_only_card("full", s2_record)
    e = s.get(1)
    e["fulltext_failed"] = {"at": "2026-10-10T00:00:00", "reason": "No full-text PDF was found:"}
    s.save()
    assert [level for level, m in full_text_findings(s)] == [INFO]     # 取れなかった → Zotero に PDF を
    del e["fulltext_failed"]
    e["fulltext"] = {"path": "x.txt", "source": "oa:x", "pages": 3, "chars": 900, "page_markers": True}
    s.save()
    found = full_text_findings(s)
    assert [level for level, _ in found] == [WARN] and "取得したのに" in found[0][1]


def test_quick_survey_is_not_nagged(s2_record):
    assert depth_findings(survey_with_abstract_only_card("quick", s2_record)) == []
