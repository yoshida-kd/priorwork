"""同時に進めるサーベイの worktree。本物の git で確かめる（外部には接続しない）。"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from priorwork import scaffold, worktree

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git is not installed")
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@example.com"}
ENV.pop("PRIORWORK_WORKSPACE", None)


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, capture_output=True, text=True, check=True).stdout.strip()


def pw(cwd, *args, ok=True):
    done = subprocess.run([sys.executable, "-m", "priorwork", *args], cwd=cwd, env={**ENV, "PRIORWORK_LANG": "en"},
                          capture_output=True, text=True)
    if ok:
        assert done.returncode == 0, done.stderr
    return done


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    scaffold.init(root)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    (root / ".env").write_text("SEMANTIC_SCHOLAR_API_KEY=x\n")
    return root


def made(root, slug="second"):
    return json.loads(pw(root, "new", "A second topic", "--slug", slug, "--worktree", "--json").stdout)


def test_a_survey_in_its_own_worktree_leaves_the_other_alone(ws):
    pw(ws, "new", "A first topic", "--slug", "first")
    git(ws, "switch", "-qc", "first_branch")
    (ws / "note.txt").write_text("in progress")
    out = made(ws)
    tree = Path(out["worktree"])
    assert tree == ws / "worktrees" / "second"
    # 開いている作業はそのまま
    assert git(ws, "branch", "--show-current") == "first_branch" and (ws / "note.txt").exists()
    assert git(tree, "branch", "--show-current") == out["name"] == out["branch"]
    assert (tree / "reports" / f"{out['name']}.md").exists() and not (ws / "reports" / f"{out['name']}.md").exists()
    assert not list((tree / "reports").glob("*first*"))              # main の先頭から
    # 共有
    assert (tree / ".env").read_text().startswith("SEMANTIC") and (tree / ".env").is_symlink()
    assert (tree / ".priorwork" / "cache").is_symlink() and (tree / ".priorwork" / "data").is_symlink()
    # Git には、サーベイのファイルだけが見える
    changed = git(tree, "status", "--porcelain")
    assert "reports/" in changed and ".env" not in changed and "cache" not in changed and "worktrees" not in changed
    assert "worktrees" not in git(ws, "status", "--porcelain")
    # 本体の status に出て、ほかのブランチには出ない
    status = json.loads(pw(ws, "status", "--json").stdout)["git"]
    assert [w["branch"] for w in status["worktrees"]] == [out["name"]] and out["name"] not in status["other_surveys"]
    assert "worktree" in pw(ws, "status").stdout
    # worktree の中でも動く
    assert json.loads(pw(tree, "status", "--json").stdout)["root"] == str(tree.resolve())
    assert worktree.main_root(tree).resolve() == ws.resolve()


def test_it_is_refused_when_the_folder_exists(ws):
    made(ws)
    done = pw(ws, "new", "Again", "--slug", "second", "--worktree", ok=False)
    assert done.returncode != 0 and "already exists" in done.stderr


def test_a_failed_new_leaves_no_worktree(ws):
    done = pw(ws, "new", "T", "--slug", "bad", "--worktree", "--manuscript", "manuscripts/none", ok=False)
    assert done.returncode != 0 and not (ws / "worktrees" / "bad").exists()
    assert "bad" not in git(ws, "worktree", "list")


def test_a_manuscript_not_committed_yet_is_found(ws):
    (ws / "manuscripts" / "p").mkdir(parents=True)
    (ws / "manuscripts" / "p" / "paper.md").write_text("# Paper\n")
    out = json.loads(pw(ws, "new", "T", "--slug", "ms", "--worktree", "--manuscript", "manuscripts/p", "--json").stdout)
    assert out["manuscript"].endswith("manuscripts/p")


def test_removal_refuses_to_lose_work(ws):
    out = made(ws)
    tree = Path(out["worktree"])
    done = pw(ws, "worktree", "--remove", "second", ok=False)
    assert done.returncode != 0 and "uncommitted" in done.stderr and tree.exists()
    git(tree, "add", "reports", ".priorwork/surveys")
    git(tree, "commit", "-qm", "survey")
    done = pw(ws, "worktree", "--remove", "second", ok=False)
    assert done.returncode != 0 and "not pushed" in done.stderr and tree.exists()
    bare = ws.parent / "origin.git"
    git(ws.parent, "init", "-q", "--bare", str(bare))
    git(ws, "remote", "add", "origin", str(bare))
    git(tree, "push", "-q", "-u", "origin", out["branch"])
    pw(ws, "worktree", "--remove", "second")
    assert not tree.exists() and out["branch"] in git(ws, "branch", "--list", out["branch"])     # ブランチは残る
    assert json.loads(pw(ws, "worktree", "--json").stdout)["worktrees"] == []


def test_force_removes_and_inside_is_refused(ws):
    tree = Path(made(ws)["worktree"])
    done = pw(tree, "worktree", "--remove", "second", "--force", ok=False)
    assert done.returncode != 0 and "inside" in done.stderr
    pw(ws, "worktree", "--remove", "second", "--force")
    assert not tree.exists()


def test_a_workspace_outside_git_says_so(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    scaffold.init(root)
    if (root / ".git").exists():
        shutil.rmtree(root / ".git")
    done = pw(root, "new", "T", "--slug", "x", "--worktree", ok=False)
    assert done.returncode != 0 and "Git" in done.stderr
