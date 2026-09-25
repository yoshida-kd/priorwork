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
    levels = {level for level, _ in depth_findings(s)}
    assert levels == {WARN, INFO}

    s.log_search("snowball", "x", {}, hits=1, new=0)
    assert [level for level, _ in depth_findings(s)] == [INFO]


def test_quick_survey_is_not_nagged(s2_record):
    assert depth_findings(survey_with_abstract_only_card("quick", s2_record)) == []
