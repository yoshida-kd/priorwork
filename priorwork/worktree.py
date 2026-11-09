"""同じワークスペースで、いくつものサーベイを同時に進める: サーベイごとの git worktree（`new --worktree`）。

サーベイはそれぞれのブランチで進むので、同じフォルダで切り替えると、別のセッションの作業を巻き込む。worktree は
ワークスペースの `worktrees/<slug>/` に置き、Git に入らないもの（`.env`・`.venv`・リストの CSV・本文のキャッシュ）は
本体へのリンクで共有する。リンクは `.gitignore` の `.venv/` のような「/ で終わる行」に当たらないので、Git の除外は
リポジトリの `info/exclude`（どの worktree にも効き、コミットされない）に書く。
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .i18n import t

DIR = "worktrees"
SHARED = (".env", ".venv", ".priorwork/data", ".priorwork/cache")
EXCLUDES = (f"/{DIR}/", "/.env", "/.venv", "/.priorwork/data", "/.priorwork/cache")


class WorktreeError(Exception):
    pass


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    except OSError as e:
        raise WorktreeError(t("git is not available: {error}", error=e)) from e


def _out(cwd: Path, *args: str) -> str:
    done = _git(cwd, *args)
    return done.stdout.strip() if done.returncode == 0 else ""


def common_dir(root: Path) -> Optional[Path]:
    """リポジトリの本体の .git（worktree の中からでも同じもの）。Git の外なら None。"""
    found = _out(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(found) if found else None


def main_root(root: Path) -> Path:
    """本体のチェックアウトの場所（worktree の中から呼ばれても）。"""
    common = common_dir(root)
    if common is None:
        raise WorktreeError(t("This workspace is not a Git repository, so it cannot have worktrees"))
    return common.parent


def base_branch(root: Path) -> str:
    """新しいサーベイの元にするブランチ（リモートの既定、無ければ main か master）。"""
    head = _out(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head:
        return head.split("/", 1)[1]
    for name in ("main", "master"):
        if _git(root, "rev-parse", "--verify", "--quiet", name).returncode == 0:
            return name
    raise WorktreeError(t("There is no main branch to start the survey from"))


def _exclude(common: Path):
    path = common / "info" / "exclude"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines()
    new = [e for e in EXCLUDES if e not in lines]
    if new:
        path.write_text(text + ("" if not text or text.endswith("\n") else "\n") + "\n".join(new) + "\n", encoding="utf-8")


def link_shared(main: Path, tree: Path) -> List[str]:
    """Git に入らないものを、本体へのリンクにする。本体に無いもの（`.env` など）の名前を返す。"""
    absent = []
    for name in SHARED:
        source, link = main / name, tree / name
        if name in (".priorwork/data", ".priorwork/cache"):
            source.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            absent.append(name)
            continue
        if link.exists() or link.is_symlink():
            continue
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(os.path.relpath(source, link.parent))
    return absent


def create(root: Path, slug: str) -> Path:
    """`worktrees/<slug>/` を、既定のブランチの先頭で作る（ブランチはサーベイの名前が決まってから `name_branch` で作る）。"""
    main = main_root(root)
    tree = main / DIR / slug
    if tree.exists():
        raise WorktreeError(t("{path} already exists. Continue there, or choose another slug", path=tree))
    _exclude(common_dir(root))
    base = base_branch(main)
    done = _git(main, "worktree", "add", "--detach", str(tree), base)
    if done.returncode != 0:
        raise WorktreeError(t("Could not create the worktree: {error}", error=done.stderr.strip()))
    return tree


def name_branch(tree: Path, name: str):
    done = _git(tree, "switch", "-c", name)
    if done.returncode != 0:
        raise WorktreeError(t("Could not create the branch {name}: {error}", name=name, error=done.stderr.strip()))


def discard(tree: Path):
    """作ったばかりの worktree を取り消す（中にまだ何も無いとき）。"""
    main = main_root(tree)
    _git(main, "worktree", "remove", "--force", str(tree))


def _unsaved(tree: Path, main: Path) -> Dict[str, Any]:
    """消すと失われるもの: 未コミットの変更と、どこにも push していないコミット。"""
    changes = _out(tree, "status", "--porcelain")
    upstream = _out(tree, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    ahead = _out(tree, "rev-list", "--count", f"{upstream or base_branch(main)}..HEAD")
    return {"changes": len(changes.splitlines()), "unpushed": int(ahead or 0)}


def listing(root: Path) -> List[Dict[str, Any]]:
    """`worktrees/` の下の worktree（サーベイの名前と、ブランチ）。Git の外なら空。"""
    if common_dir(root) is None:
        return []
    main = main_root(root)
    found, path = [], None
    for line in _out(main, "worktree", "list", "--porcelain").splitlines() + [""]:
        if line.startswith("worktree "):
            path, branch = Path(line[len("worktree "):]), ""
        elif line.startswith("branch "):
            branch = line[len("branch refs/heads/"):]
        elif not line and path is not None:
            if path.parent == main / DIR and path.is_dir():
                surveys = sorted(p.stem for p in (path / ".priorwork" / "surveys").glob("*.json"))
                found.append({"name": path.name, "path": str(path), "branch": branch, "surveys": surveys,
                              **_unsaved(path, main)})
            path = None
    return found


def remove(root: Path, name: str, force: bool = False) -> Dict[str, Any]:
    """worktree を消す。ブランチは残す（PR のため）。未コミット・未 push のものがあれば、force でなければ断る。"""
    main = main_root(root)
    entry = next((w for w in listing(main) if name in (w["name"], w["branch"], w["path"])), None)
    if entry is None:
        raise WorktreeError(t("No worktree named {name}. See `priorwork worktree`", name=name))
    if Path(entry["path"]).resolve() == Path(root).resolve():
        raise WorktreeError(t("You are inside this worktree. Run this from the workspace's main folder ({path})", path=main))
    if not force and (entry["changes"] or entry["unpushed"]):
        raise WorktreeError(t("{name} has {changes|# uncommitted change|# uncommitted changes} and {unpushed|# commit|# commits} "
                              "not pushed. Commit and push first (--force throws them away)", name=entry["name"],
                              changes=entry["changes"], unpushed=entry["unpushed"]))
    done = _git(main, "worktree", "remove", *(["--force"] if force else []), entry["path"])
    if done.returncode != 0:
        raise WorktreeError(t("Could not remove the worktree: {error}", error=done.stderr.strip()))
    return entry
