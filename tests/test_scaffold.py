import json

import pytest

from priorwork import scaffold


def test_init_creates_workspace_and_sync_is_idempotent(tmp_path):
    root = tmp_path / "ws"
    scaffold.init(root)
    for rel in ("AGENTS.md", "CLAUDE.md", ".env.example", "priorwork", "AGENTS.local.md", "requirements.txt",
                ".agent/skills/survey-new/SKILL.md", ".priorwork/sync.json", ".priorwork/config.json"):
        assert (root / rel).exists(), rel
    assert (root / ".claude" / "skills").is_symlink()
    assert (root / "reports").is_dir() and (root / ".priorwork" / "surveys").is_dir()
    assert (root / "priorwork").stat().st_mode & 0o111
    assert scaffold.sync_status(root) is None
    assert (root / ".git").is_dir()

    again = scaffold.sync(root)
    assert not again.written and not again.skipped


def test_sync_updates_managed_files_but_not_unmanaged_edits(tmp_path):
    root = tmp_path / "ws"
    scaffold.init(root)

    # エンジンの更新: 前回の sync が書き出した内容のまま（手元で未変更）なら、新しい版に置き換える
    (root / "AGENTS.md").write_text("old engine version")
    m = json.loads(scaffold._manifest_path(root).read_text())
    m["hashes"]["AGENTS.md"] = scaffold._sha(b"old engine version")
    scaffold._manifest_path(root).write_text(json.dumps(m))
    assert "AGENTS.md" in scaffold.sync(root).written

    scaffold._manifest_path(root).unlink()                   # 記録がない = 由来不明のファイル
    (root / "AGENTS.md").write_text("my own rules")
    res = scaffold.sync(root)
    assert "AGENTS.md" in res.skipped and (root / "AGENTS.md").read_text() == "my own rules"
    assert scaffold.sync_status(root) is not None
    assert "AGENTS.md" in scaffold.sync(root, force=True).written


def test_sync_removes_skills_that_the_engine_dropped(tmp_path):
    root = tmp_path / "ws"
    scaffold.init(root)
    m = json.loads(scaffold._manifest_path(root).read_text())
    m["files"].append(".agent/skills/survey-old/SKILL.md")
    scaffold._manifest_path(root).write_text(json.dumps(m))
    (root / ".agent/skills/survey-old").mkdir()
    (root / ".agent/skills/survey-old/SKILL.md").write_text("x")
    assert ".agent/skills/survey-old/SKILL.md" in scaffold.sync(root).removed
    assert not (root / ".agent/skills/survey-old").exists()


def test_gitignore_tracks_state_but_ignores_cache(tmp_path):
    (tmp_path / ".gitignore").write_text("notes/\n")
    scaffold.ensure_gitignore(tmp_path)
    lines = (tmp_path / ".gitignore").read_text().splitlines()
    assert lines[0] == "notes/" and ".priorwork/" not in lines
    assert ".priorwork/cache/" in lines and ".priorwork/data/" in lines
    assert scaffold.ensure_gitignore(tmp_path) is False


def test_engine_repo_itself_is_never_rewritten():
    from priorwork.workspace import ENGINE_DIR
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.sync(ENGINE_DIR.parent)


def test_init_pins_engine_to_the_current_release(tmp_path):
    from priorwork import __version__
    scaffold.init(tmp_path / "ws")
    assert (tmp_path / "ws" / "requirements.txt").read_text().strip() == f"priorwork=={__version__}"


def test_pin_requirements_replaces_only_the_engine_line(tmp_path):
    (tmp_path / "requirements.txt").write_text("pandas\npriorwork==0.3.0\n")
    line = scaffold.pin_requirements(tmp_path, "v0.10.0")
    assert (tmp_path / "requirements.txt").read_text() == f"pandas\n{line}\n" and line == "priorwork==0.10.0"


def test_latest_version_comes_from_pypi(monkeypatch):
    import requests

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"info": {"version": "0.10.0"}}
    monkeypatch.setattr(requests, "get", lambda url, timeout: Resp())
    assert scaffold.latest_version() == "0.10.0"


def test_upgrade_restores_requirements_when_pip_fails(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("priorwork==0.3.0\n")

    def fail(*a, **k):
        raise scaffold.subprocess.CalledProcessError(1, "pip")
    monkeypatch.setattr(scaffold.subprocess, "run", fail)
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.upgrade(tmp_path, "v0.4.0")
    assert (tmp_path / "requirements.txt").read_text().strip() == "priorwork==0.3.0"


def test_sync_does_not_overwrite_local_edits_of_managed_files(tmp_path):
    root = tmp_path / "ws"
    scaffold.init(root)
    (root / ".agent/skills/survey-new/SKILL.md").write_text("my tweak")

    assert "survey-new/SKILL.md" in scaffold.sync_status(root)
    res = scaffold.sync(root)
    assert ".agent/skills/survey-new/SKILL.md" in res.modified
    assert (root / ".agent/skills/survey-new/SKILL.md").read_text() == "my tweak"
    assert scaffold.sync_status(root) is not None            # 警告し続ける

    assert "my tweak" in scaffold.diff(root)                  # --diff は書き換えずに差分を示す
    assert (root / ".agent/skills/survey-new/SKILL.md").read_text() == "my tweak"

    assert ".agent/skills/survey-new/SKILL.md" in scaffold.sync(root, force=True).written
    assert scaffold.sync_status(root) is None and scaffold.diff(root) == ""


def test_sync_adds_export_outputs_to_an_existing_gitignore(tmp_path):
    scaffold.init(tmp_path)
    (tmp_path / ".gitignore").write_text(".env\n")          # export に対応する前のワークスペース
    assert ".gitignore" in scaffold.sync(tmp_path).written
    assert "reports/*.html" in (tmp_path / ".gitignore").read_text().splitlines()


def test_init_keeps_an_existing_repo_and_env_example_is_tracked(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    root = tmp_path / "ws"                                   # 既存リポジトリの中のサブディレクトリ
    res = scaffold.init(root)
    assert not (root / ".git").exists() and not any(w.startswith(".git/") for w in res.written)
    (root / ".env").write_text("X=1")
    ignored = lambda rel: subprocess.run(["git", "check-ignore", "-q", rel], cwd=root).returncode == 0
    assert ignored(".env") and not ignored(".env.example")
