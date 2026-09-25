import pytest

from priorwork.survey import (
    CANDIDATE, EXCLUDED, INCLUDED, MAYBE, Survey, SurveyError, author_short, extract_blocks, parse_card_fields,
    status_trail, surname,
)


@pytest.fixture
def s(tmp_path):
    return Survey.create("最低賃金", "minimum wage", {"question": "雇用は減るか"})


def test_create_and_load(s):
    assert s.md_path.name.endswith("_minimum_wage.md") and s.json_path.exists()
    loaded = Survey.load("minimum_wage")
    assert loaded.data["scope"]["question"] == "雇用は減るか"
    assert "雇用は減るか" in extract_blocks(s.md_path.read_text())["scope"]


def test_numbers_are_stable_and_duplicates_merge(s, s2_record, oa_record):
    e1, new1 = s.upsert(s2_record(doi="10.1/a", title="A study of minimum wages in Germany"), "search")
    e2, new2 = s.upsert(s2_record(doi="10.1/b", title="Another paper on labor markets"), "search")
    e3, new3 = s.upsert(oa_record(doi="10.1/A", title="A study of minimum wages in Germany"), "snowball")
    assert (e1["number"], e2["number"]) == (1, 2)
    assert new1 and new2 and not new3 and e3 is e1
    assert e1["found_by"] == ["search", "snowball"]


def test_published_version_replaces_wp_and_keeps_card(s, s2_record):
    wp = s2_record(doi="10.2139/ssrn.1", journal="SSRN Electronic Journal", title="The persistent effects of mining")
    e, _ = s.upsert(wp, "search", status=INCLUDED)
    s.render()
    md = s.md_path.read_text().replace("- **RQ**:", "- **RQ**: 鉱山労働の長期効果", 1)
    s.md_path.write_text(md)

    published = s2_record(doi="10.3982/ECTA8121", journal="Econometrica", title="The persistent effects of mining")
    e2, is_new = s.upsert(published, "search")
    assert not is_new and e2["key"] == "doi:10.3982/ecta8121"
    s.render()
    md = s.md_path.read_text()
    assert "<!-- paper: doi:10.3982/ecta8121 -->" in md and "ssrn" not in extract_blocks(md)["papers"]
    assert "鉱山労働の長期効果" in extract_blocks(md)["matrix"]


def test_render_preserves_card_edits_and_builds_matrix(s, s2_record):
    e, _ = s.upsert(s2_record(), "search")
    s.set_status([e["number"]], INCLUDED)
    s.render()
    md = s.md_path.read_text()
    md = md.replace("- **RQ**:", "- **RQ**: 雇用は減るか\n  - 詳細メモ", 1).replace("- **確認レベル**: 未確認", "- **確認レベル**: 要旨のみ", 1)
    md = md.replace("## 1. 研究の背景と中心的な論点\n", "## 1. 研究の背景と中心的な論点\n手で書いた文章\n")
    s.md_path.write_text(md)

    assert s.render()
    md = s.md_path.read_text()
    assert "手で書いた文章" in md and "  - 詳細メモ" in md
    matrix = extract_blocks(md)["matrix"]
    assert "雇用は減るか" in matrix and "要旨のみ" in matrix
    assert not s.render()  # 冪等


def test_excluded_card_is_archived_and_restored(s, s2_record):
    e, _ = s.upsert(s2_record(), "search", status=INCLUDED)
    s.render()
    s.md_path.write_text(s.md_path.read_text().replace("- **限界**:", "- **限界**: ARCHIVE_TEST_MEMO", 1))
    s.set_status([e["number"]], EXCLUDED, "対象外")
    s.render()
    assert "ARCHIVE_TEST_MEMO" not in s.md_path.read_text()
    assert "ARCHIVE_TEST_MEMO" in Survey.load(s.name).data["papers"][e["key"]]["card_archive"]

    s.set_status([e["number"]], INCLUDED)
    s.render()
    assert "ARCHIVE_TEST_MEMO" in s.md_path.read_text()


def test_unregistered_card_is_kept(s):
    md = s.md_path.read_text().replace(
        "<!-- BEGIN priorwork:papers -->\n", "<!-- BEGIN priorwork:papers -->\n<!-- paper: doi:10.9/x -->\n- **RQ**: 手書き\n")
    s.md_path.write_text(md)
    s.render()
    papers = extract_blocks(s.md_path.read_text())["papers"]
    assert "未登録の論文" in papers and "- **RQ**: 手書き" in papers


def test_missing_block_is_an_error(s):
    s.md_path.write_text(s.md_path.read_text().replace("<!-- END priorwork:matrix -->", ""))
    with pytest.raises(SurveyError, match="matrix"):
        s.render()


def test_parse_card_fields_uses_sub_bullets_when_inline_empty():
    body = "- **確認レベル**: 本文確認済\n- **識別戦略**:\n  - DID\n  - 州境の郡ペア\n- **限界**: 短期のみ"
    f = parse_card_fields(body)
    assert f == {"evidence": "本文確認済", "method": "DID / 州境の郡ペア", "limits": "短期のみ"}


def test_ambiguous_or_missing_survey_reference(s):
    with pytest.raises(SurveyError):
        Survey.load("nope")


def test_depth_defaults_to_full_and_can_change(s):
    assert s.depth == "full"
    s.set_depth("quick")
    s.save()
    s.render()
    assert Survey.load("minimum_wage").depth == "quick"
    assert "quick" in extract_blocks(s.md_path.read_text())["scope"]
    with pytest.raises(SurveyError):
        s.set_depth("huge")


def test_legacy_survey_without_depth_is_full(s):
    del s.data["depth"]
    assert s.depth == "full"
    assert "full" in s.rendered_markdown(s.md_path.read_text())


def test_state_file_from_a_newer_engine_is_refused(s):
    s.data["version"] = 999
    s.save()
    with pytest.raises(SurveyError, match="priorwork upgrade"):
        Survey.load("minimum_wage")


def test_old_state_files_are_migrated_on_load(s, monkeypatch):
    from priorwork import survey
    monkeypatch.setattr(survey, "SCHEMA_VERSION", 4)
    monkeypatch.setitem(survey.MIGRATIONS, 3, lambda d: {**d, "renamed": d["topic"]})
    loaded = Survey.load("minimum_wage")
    assert loaded.data["version"] == 4 and loaded.data["renamed"] == "最低賃金"


def test_v1_state_files_get_a_status_history(s, s2_record):
    e, _ = s.upsert(s2_record(), "search")
    s.set_status([e["number"]], EXCLUDED, "理論のみ")
    s.data["version"] = 1
    del s.data["lang"]
    for entry in s.data["papers"].values():
        del entry["history"]
    s.save()
    loaded = Survey.load("minimum_wage")
    assert loaded.data["version"] == 3 and loaded.lang == "ja"
    assert loaded.get(e["number"])["history"] == [
        {"at": e["updated"], "status": EXCLUDED, "reason": "理論のみ", "migrated": True}]


def test_status_changes_are_kept_in_history(s, s2_record):
    e, _ = s.upsert(s2_record(), "search")
    s.set_status([e["number"]], MAYBE)
    s.set_status([e["number"]], EXCLUDED, "理論のみ")
    s.set_status([e["number"]], EXCLUDED, "理論のみ")   # 変化が無ければ記録しない
    s.set_status([e["number"]], INCLUDED)
    assert [h["status"] for h in e["history"]] == [CANDIDATE, MAYBE, EXCLUDED, INCLUDED]
    assert status_trail(e) == "候補 → 保留 → 除外（理論のみ） → 採用"
    assert e["reason"] == ""
    s.save()
    s.render()
    assert f"採否の見直し**: 1 件（#{e['number']}" in extract_blocks(s.md_path.read_text())["log"]


def test_first_decision_is_not_a_revision(s, s2_record):
    e, _ = s.upsert(s2_record(), "search")
    s.set_status([e["number"]], INCLUDED)
    s.save()
    s.render()
    assert "見直し" not in extract_blocks(s.md_path.read_text())["log"]


def test_same_author_and_year_get_letter_suffixes(s, s2_record):
    for doi, title in (("10.1/b", "Reversal of fortune"), ("10.1/a", "Colonial origins of development")):
        s.upsert(s2_record(doi=doi, title=title, authors=("Daron Acemoglu", "Simon Johnson", "James Robinson"),
                           year=2001), "search", status=INCLUDED)
    s.upsert(s2_record(doi="10.1/c", title="Unrelated paper", authors=("Daron Acemoglu", "James Robinson"), year=2001),
             "search", status=INCLUDED)
    s.save()
    s.render()
    blocks = extract_blocks(s.md_path.read_text())
    refs = blocks["references"]
    assert "(2001a). Colonial origins" in refs and "(2001b). Reversal" in refs
    assert "Acemoglu, James Robinson (2001). Unrelated" in refs   # 本文での書き方が違えば区別しない
    assert "Acemoglu et al. (2001a): Colonial origins" in blocks["papers"]
    assert "Acemoglu et al. (2001b)" in blocks["matrix"]


def test_name_suffixes_are_not_surnames():
    assert surname("Robert E. Lucas Jr.") == "lucas" and surname("Daron Acemoğlu") == "acemoglu"
    assert author_short(["Robert E. Lucas Jr.", "Thomas J. Sargent"]) == "Lucas & Sargent"


def test_log_block_shows_the_screening_flow(s, s2_record):
    s.upsert(s2_record(doi="10.1/a", title="First paper on wages"), "search")
    s.upsert(s2_record(doi="10.1/b", title="Second paper on jobs"), "snowball", status=INCLUDED)
    s.upsert(s2_record(doi="10.1/a", title="First paper on wages"), "snowball")   # 重複は 1 件のまま
    s.log_search("search", "wages", {}, hits=10, new=1)
    s.log_search("snowball", "seeds", {}, hits=5, new=1)
    s.save()
    s.render()
    log = extract_blocks(s.md_path.read_text())["log"]
    assert "検索 1 回・引用をたどる 1 回（延べ 15 件ヒット）" in log
    assert "重複を除いて 2 件（検索で見つけた 1 / 引用から 1 / 手動登録 0）" in log
    assert "採用 1・保留 0・除外 0・未選別 1" in log
