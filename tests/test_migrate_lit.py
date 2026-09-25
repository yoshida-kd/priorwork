"""旧名 lit のワークスペースを priorwork に移す（`priorwork migrate`）。"""

import json

from priorwork import scaffold
from priorwork.survey import Survey, extract_blocks

LIT_REPORT = """---
title: "最低賃金 に関する文献サーベイ"
---

# 最低賃金 に関する文献サーベイ

## 0. 調査の範囲
<!-- BEGIN lit:scope -->
<!-- END lit:scope -->

## 2. 文献比較マトリクス
<!-- BEGIN lit:matrix -->
<!-- END lit:matrix -->

## 3. 各論文の詳細
<!-- BEGIN lit:papers -->
<!-- END lit:papers -->

## 背景
手で書いた文章 <!-- lit:ignore-citation World Bank (2010) -->

## 8. 参照文献
<!-- BEGIN lit:references -->
<!-- END lit:references -->

## 付録. 文献探索の記録
<!-- BEGIN lit:log -->
<!-- END lit:log -->
"""


def lit_workspace(root):
    """lit 0.1 系が作ったワークスペースの形（.lit/、./lit、git の requirements、lit の .gitignore ブロック）。"""
    (root / ".lit" / "surveys").mkdir(parents=True)
    (root / ".lit" / "cache" / "fulltext").mkdir(parents=True)
    (root / ".lit" / "cache" / "fulltext" / "001.txt").write_text("text")
    (root / "reports").mkdir()
    (root / "reports" / "20260101_mw.md").write_text(LIT_REPORT, encoding="utf-8")
    state = {"version": 2, "topic": "最低賃金", "created": "2026-01-01", "depth": "quick",
             "scope": {"question": "雇用は減るか", "years": "", "fields": "", "inclusion": "", "exclusion": ""},
             "next_number": 1, "papers": {}, "searches": []}
    (root / ".lit" / "surveys" / "20260101_mw.json").write_text(json.dumps(state, ensure_ascii=False))
    (root / "lit").write_text("#!/bin/sh\nexec python3 -m litsurvey \"$@\"\n")
    (root / "AGENTS.md").write_text("lit の AGENTS.md")
    manifest = {"engine_version": "0.1.0", "hash": "x", "files": ["AGENTS.md", "lit"],
                "hashes": {"AGENTS.md": scaffold._sha(b"lit \xe3\x81\xae AGENTS.md"), "lit": "y"}}
    (root / ".lit" / "sync.json").write_text(json.dumps(manifest))
    (root / "requirements.txt").write_text("litsurvey @ git+https://github.com/yoshida-kd/lit.git@v0.1.0\n")
    (root / ".gitignore").write_text("notes/\n\n# BEGIN lit (managed by `lit sync`)\n.env\n.lit/cache/\n.lit/data/\n# END lit\n")


def test_a_lit_workspace_is_recognised(tmp_path):
    lit_workspace(tmp_path)
    assert scaffold.is_lit_workspace(tmp_path) and scaffold.is_legacy(tmp_path)
    assert not scaffold.is_old_layout(tmp_path)


def test_migrate_moves_a_lit_workspace(tmp_path):
    lit_workspace(tmp_path)
    out = scaffold.migrate(tmp_path)

    assert not (tmp_path / ".lit").exists() and not scaffold.is_legacy(tmp_path)
    assert (tmp_path / ".priorwork" / "cache" / "fulltext" / "001.txt").read_text() == "text"
    assert json.loads((tmp_path / ".priorwork" / "config.json").read_text()) == {"lang": "ja"}
    # ./lit は sync の記録にあるので消え、./priorwork ができる
    assert not (tmp_path / "lit").exists() and (tmp_path / "priorwork").exists()
    assert "lit" in out["removed"]
    assert (tmp_path / "requirements.txt").read_text().startswith("priorwork==")
    gitignore = (tmp_path / ".gitignore").read_text()
    assert "# BEGIN lit" not in gitignore and ".lit/cache/" not in gitignore
    assert "notes/" in gitignore and ".priorwork/cache/" in gitignore
    # 手で変えていない lit の AGENTS.md は日本語の新しいものに置き換わる
    assert "priorwork" in (tmp_path / "AGENTS.md").read_text() and "エージェント" in (tmp_path / "AGENTS.md").read_text()

    # レポートの印は priorwork: に書き換わり、手で書いた文章は残る
    md = (tmp_path / "reports" / "20260101_mw.md").read_text(encoding="utf-8")
    assert "BEGIN lit:" not in md and "<!-- BEGIN priorwork:scope -->" in md
    assert "手で書いた文章" in md and "雇用は減るか" in extract_blocks(md)["scope"]
    assert out["rendered"] == ["reports/20260101_mw.md"]
    s = Survey.load("mw", tmp_path / "reports", tmp_path / ".priorwork" / "surveys")
    assert s.data["version"] == 3 and s.lang == "ja" and s.depth == "quick"
    assert scaffold.sync_status(tmp_path) is None


def test_migrate_refuses_when_both_directories_exist(tmp_path):
    lit_workspace(tmp_path)
    (tmp_path / ".priorwork").mkdir()
    try:
        scaffold.migrate(tmp_path)
    except scaffold.ScaffoldError as e:
        assert ".lit/" in str(e)
    else:
        raise AssertionError("expected ScaffoldError")
    assert (tmp_path / ".lit" / "surveys" / "20260101_mw.json").exists()


def test_the_old_ignore_marker_still_works_after_migration(tmp_path):
    from priorwork.check import ignored_citations
    assert ignored_citations("<!-- lit:ignore-citation World Bank (2010) -->") == {("bank", 2010)}
    assert ignored_citations("<!-- priorwork:ignore-citation World Bank (2010) -->") == {("bank", 2010)}
