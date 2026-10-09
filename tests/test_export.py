from priorwork.export import clean_markdown, draft_issues, export, to_html
from priorwork.survey import INCLUDED, Survey


def test_clean_removes_scaffolding_and_empty_items():
    md = """---
title: "T"
---

# T

> [!NOTE]
> `<!-- BEGIN priorwork:… -->` は再生成されます。

## 1. 背景
- **学術的背景**:
  - 実際の内容
- **本サーベイで扱う論点**:

## 3. 各論文
記入のルール:
- 書かれていることだけを書く

<!-- BEGIN priorwork:papers -->
<!-- paper: doi:10.1/a -->
### #1 A (2000): T
- **書誌**: x
- **確認レベル**: 未確認
- **RQ**:
- **メモ**:

<details><summary>要旨</summary>

**Abstract**: text

</details>

### #2 B (2001): U
- **書誌**: y
- **確認レベル**: 要旨のみ
- **RQ**: 何か

<!-- END priorwork:papers -->
"""
    text, title, empty = clean_markdown(md)
    assert title == "T"
    for junk in ("<!--", "[!NOTE]", "記入のルール", "書かれていることだけ", "<details>", "**RQ**:\n", "本サーベイで扱う論点"):
        assert junk not in text, junk
    assert "実際の内容" in text and "**RQ**: 何か" in text
    assert text.count("（カード未記入）") == 1
    assert "- **確認レベル**: 未確認\n- （カード未記入）\n\n### #2" in text
    assert "要旨" in clean_markdown(md, with_abstracts=True)[0]
    assert empty == []


def test_empty_sections_are_marked():
    text, _, empty = clean_markdown("# T\n\n## 4. 学説\n- **潮流 A**:\n  - 主な主張:\n\n## 5. 手法\n本文\n")
    assert empty == ["4. 学説"] and "*（未記入）*" in text and "本文" in text


def test_fresh_survey_exports_as_draft_and_html_is_self_contained(tmp_path):
    s = Survey.create("最低賃金", "mw", {"question": "雇用は減るか"})
    out, issues = export(s, "html")
    page = out.read_text(encoding="utf-8")
    assert out.suffix == ".html" and "<style>" in page and "<!-- BEGIN" not in page
    assert "下書き" in page and any("未記入の節" in i for i in issues)
    assert "雇用は減るか" in page and "<table" not in page or "table-wrap" in page


def test_unchecked_cards_are_reported_until_the_level_is_updated(s2_record):
    s = Survey.create("最低賃金", "mw", {"question": "q"})
    s.upsert(s2_record(doi="10.1/a", title="Minimum wages study"), "search", status=INCLUDED)
    s.save()
    s.render()
    assert any("未確認" in i for i in draft_issues(s, [])["ja"])

    md = s.md_path.read_text(encoding="utf-8").replace("**確認レベル**: 未確認", "**確認レベル**: 要旨のみ")
    s.md_path.write_text(md, encoding="utf-8")
    assert not any("未確認" in i for i in draft_issues(s, [])["ja"])


def test_to_html_escapes_title():
    assert "&lt;b&gt;" in to_html("# x\n", "<b>")


def test_label_with_a_parenthetical_note_is_still_an_empty_item():
    text, _, empty = clean_markdown("## 5. 手法\n- **識別戦略の発展**（OLS 等 → DID / IV）:\n- **外的妥当性**:\n  - 中身\n")
    assert "識別戦略の発展" not in text and "外的妥当性" in text and "中身" in text and empty == []
