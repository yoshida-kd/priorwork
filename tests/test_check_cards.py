"""カードの書き方（言語・本文の根拠）、まとめの節の引用、手で書いた採用数、監査の検査。"""
from priorwork.check import SYNTHESIS_MARK, WARN, check_survey
from priorwork.survey import INCLUDED, Survey

TEXT = ("=== page 1 ===\n\nWe use 1,234 municipalities from 2001 to 2010.\n\n"
        "=== page 2 ===\n\nThe estimate is .35 (s.e. 0.08) using difference-in-differences.\n")


def survey_with_card(s2_record, tmp_path, card, depth="full", lang="ja"):
    s = Survey.create("外部委託", "mob", {"question": "q"}, depth=depth, lang=lang)
    s.upsert(s2_record(doi="10.1/a", title="Outsourcing study"), "search", status=INCLUDED)
    s.get(1)["record"]["pages"] = "101-102"
    (tmp_path / "ft.txt").write_text(TEXT, encoding="utf-8")
    s.get(1)["fulltext"] = {"path": "ft.txt", "source": "oa:x", "pages": 2, "chars": 900, "page_markers": True}
    s.save()
    s.render()
    s.set_card(1, card)
    return s


def messages(s):
    return [m for level, m in check_survey(s) if level == WARN]


GOOD = {"evidence": "fulltext", "rq": "外部委託は人員を減らすか", "x": "外部委託", "y": "職員数",
        "data": "1,234 自治体、2001–2010 年（p. 1）", "method": "差の差（difference-in-differences）（p. 2）",
        "findings": "係数は 0.35（標準誤差 0.08）（p. 2）", "limits": "記載なし"}


def test_a_well_grounded_card_passes(s2_record, tmp_path):
    s = survey_with_card(s2_record, tmp_path, GOOD)
    assert not [m for m in messages(s) if "#1" in m or "カード" in m], messages(s)


def test_numbers_and_pages_not_in_the_full_text(s2_record, tmp_path):
    s = survey_with_card(s2_record, tmp_path, {**GOOD, "data": "2,500 自治体（p. 70）", "findings": "係数は 0.42（p. 2）"})
    found = messages(s)
    assert any("2,500" in m and "0.42" in m and "本文に見つかりません" in m for m in found), found
    assert any("p. 70" in m and "論文にありません" in m for m in found), found


def test_fulltext_level_without_full_text_or_pages(s2_record, tmp_path):
    card = {**GOOD, "data": "自治体のパネル", "method": "差の差", "findings": "人員が減る"}
    s = survey_with_card(s2_record, tmp_path, card)
    assert any("ページがありません" in m for m in messages(s))
    s.set_card(1, {**card, "findings": "人員が減る（ページ未確認）"})
    s.save()
    s.render()
    assert not any("ページがありません" in m for m in messages(s))
    del s.get(1)["fulltext"]
    s.save()
    assert any("本文を取得した記録がありません" in m for m in messages(s))


def test_card_in_another_language(s2_record, tmp_path):
    card = {**GOOD, "rq": "Does outsourcing cut staff?", "x": "Outsourcing", "y": "Staff numbers",
            "data": "1,234 municipalities (p. 1)", "method": "Difference-in-differences (p. 2)",
            "findings": "Coefficient 0.35 (p. 2)", "limits": "Not stated"}
    assert any("レポートの言語（日本語）" in m for m in messages(survey_with_card(s2_record, tmp_path, card)))


def test_synthesis_sections_must_cite_and_counts_must_match(s2_record, tmp_path):
    s = survey_with_card(s2_record, tmp_path, GOOD)
    md = s.md_path.read_text(encoding="utf-8")
    assert SYNTHESIS_MARK in md
    md = md.replace(SYNTHESIS_MARK, SYNTHESIS_MARK + "\n外部委託は人員を減らすという見方が多い。\n本サーベイでは採用した 57 本を整理する。", 1)
    s.md_path.write_text(md, encoding="utf-8")
    found = messages(s)
    assert any("論文を 1 本も引いていません" in m for m in found), found
    assert any("採用が 57 本" in m and "実際は 1 本" in m for m in found), found


def test_audit_is_asked_for_once_the_cards_are_filled(s2_record, tmp_path):
    s = survey_with_card(s2_record, tmp_path, GOOD)
    assert any("監査" in m for m in messages(s))
    s.add_audit("Claude Opus 5.5")
    s.save()
    s.render()
    assert not any("監査" in m for m in messages(s))
    assert "**監査**: " in s.md_path.read_text(encoding="utf-8")


def test_a_list_of_pages_is_not_taken_for_numbers(s2_record, tmp_path):
    s = survey_with_card(s2_record, tmp_path, {**GOOD, "findings": "係数は 0.35（p. 1, 2-3）"})
    assert not any("本文に見つかりません" in m for m in messages(s)), messages(s)
    s.set_card(1, {**GOOD, "findings": "係数は 0.35（p. 2, 70-72）"})
    assert any("p. 70" in m and "論文にありません" in m for m in messages(s)), messages(s)


def test_numbers_after_japanese_text_and_wrong_journal_pages(s2_record, tmp_path):
    s = survey_with_card(s2_record, tmp_path, {**GOOD, "data": "約1,234 自治体、2001–2010 年（p. 101）"})
    assert not any("本文に見つかりません" in m or "論文にありません" in m for m in messages(s)), messages(s)
    s.get(1)["record"]["pages"] = "101-101"   # データベースの誤った範囲（"330-330"）
    s.save()
    assert not any("論文にありません" in m for m in messages(s)), messages(s)


def test_a_preview_pdf_is_flagged_as_incomplete(s2_record, tmp_path):
    s = survey_with_card(s2_record, tmp_path, GOOD)
    s.get(1)["record"]["pages"] = "605-623"
    s.save()
    assert any("#1 (2/19 pp.)" in m for m in messages(s)), messages(s)
