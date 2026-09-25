"""ワークスペースの診断（`priorwork doctor`）。新しいワークスペースを作った直後や、動作がおかしいときに使う。

VS Code の拡張機能も `priorwork doctor --json` でこの結果を読む（項目のキーは CHECK_KEYS）。
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, List, Optional, Tuple

from . import __version__, i18n, scaffold, ssci
from .i18n import t
from .workspace import data_dir, meta_dir, reports_dir, state_dir, workspace_lang
from .zotero import ZoteroClient, ZoteroError

OK, WARN, NG = "ok", "warn", "ng"
Check = Tuple[str, str, str]  # (レベル, 項目, 説明)

# 旧名 lit のときの環境変数（.env に残っていたら新しい名前を案内する）
LEGACY_ENV = ("LIT_MAX_RETRIES", "LIT_CACHE_TTL_DAYS", "LIT_NO_CACHE", "LIT_WORKSPACE")


def _pinned_version(root: Path) -> Optional[str]:
    try:
        text = (root / "requirements.txt").read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(rf"^\s*{scaffold.DIST}\s*==\s*v?(\d+(?:\.\d+)*)\s*$", text, re.MULTILINE)
    return m.group(1) if m else None


def _git(root: Path, *args: str) -> Optional[subprocess.CompletedProcess]:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    except OSError:
        return None


def git_checks(root: Path) -> List[Check]:
    """ワークスペースは GitHub で管理する前提。リポジトリ・リモート・.env の扱いを確認する。"""
    name = "Git"
    if not scaffold.in_git_repo(root):
        return [(WARN, name, t("Not a Git repository. Run `git init`, then create a private repository on GitHub and push"))]
    out: List[Check] = []
    env_name = t(".env in Git")
    tracked = _git(root, "ls-files", "--error-unmatch", ".env")
    if tracked and tracked.returncode == 0:
        out.append((NG, env_name, t(".env is committed to Git. Remove it with `git rm --cached .env` and issue new API keys")))
    elif (root / ".env").is_file() and (ignored := _git(root, "check-ignore", "-q", ".env")) and ignored.returncode != 0:
        out.append((NG, env_name, t(".env is not in .gitignore. Fix .gitignore with `./priorwork sync`")))
    remotes = (_git(root, "remote", "-v") or subprocess.CompletedProcess([], 0, "")).stdout.split()
    urls = sorted({u for u in remotes[1::3]})
    if not urls:
        out.append((WARN, name, t("No remote. Create a private repository on GitHub and push "
                                  "(e.g. `gh repo create <name> --private --source=. --push`)")))
    elif not any("github.com" in u for u in urls):
        out.append((WARN, name, t("The remote is not GitHub: {urls}", urls=", ".join(urls))))
    else:
        out.append((OK, name, t("Remote: {urls}", urls=", ".join(urls))))
    return out


def run_checks(root: Path, client: Optional[Any] = None) -> List[Check]:
    """client を渡すと、Semantic Scholar・OpenAlex・Zotero にも接続して確認する。"""
    out: List[Check] = []

    # ワークスペース
    layout = t("Layout")
    missing = [d.relative_to(root) for d in (reports_dir(root), state_dir(root), meta_dir(root)) if not d.is_dir()]
    if scaffold.is_lit_workspace(root):
        out.append((NG, layout, t("This is a workspace of lit, priorwork's former name. Move it with `priorwork migrate`")))
    elif scaffold.is_old_layout(root):
        out.append((NG, layout, t("Old layout (surveys/ holds both md and json). Move it with `priorwork migrate`")))
    elif missing:
        out.append((WARN, layout, t("Missing directories: {dirs} (create them with `priorwork init`)",
                                    dirs=", ".join(map(str, missing)))))
    else:
        out.append((OK, layout, t("reports/ and .priorwork/ are there ({root})", root=root)))
    lang = workspace_lang(root)
    out.append((OK, t("Workspace language"), t("{lang} (reports, AGENTS.md and the skills)", lang=lang)))
    out.append((OK, t("Display language"), t("{lang} (PRIORWORK_LANG, or the locale)", lang=i18n.language())))
    agents = t("AGENTS.md and skills")
    note = scaffold.sync_status(root)
    out.append((WARN, agents, note) if note else (OK, agents, t("They match the engine's version")))
    engine = t("Engine version")
    pinned = _pinned_version(root)
    if pinned and pinned != __version__:
        out.append((WARN, engine, t("requirements.txt says {pinned}, but {installed} is installed "
                                    "(`./priorwork upgrade` or `pip install -r requirements.txt`)",
                                    pinned=pinned, installed=__version__)))
    else:
        out.append((OK, engine, __version__ + (t(" (requirements.txt: {pinned})", pinned=pinned) if pinned else "")))

    out.extend(git_checks(root))

    # 設定
    if not (root / ".env").is_file():
        out.append((WARN, ".env", t("There is no .env. Copy `.env.example` to `.env` and set your API keys")))
    legacy = [v for v in LEGACY_ENV if os.environ.get(v)]
    if legacy:
        out.append((WARN, ".env", t("Settings under lit's old names: {names}. Rename them to PRIORWORK_…",
                                    names=", ".join(legacy))))
    if os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or os.environ.get("S2_API_KEY"):
        out.append((OK, "Semantic Scholar", t("An API key is set")))
    else:
        out.append((WARN, "Semantic Scholar", t("No API key. Requests share a public pool, so searches often fail with HTTP 429")))
    if os.environ.get("OPENALEX_API_KEY") or os.environ.get("OPENALEX_MAILTO"):
        out.append((OK, "OpenAlex", t("Set")))
    else:
        out.append((OK, "OpenAlex", t("No key or e-mail (it works, with a daily usage cap)")))

    ssci_name = t("SSCI journal list")
    ssci_list = ssci.get_ssci_list()
    if ssci_list.loaded:
        out.append((OK, ssci_name, t("{file} ({n|# ISSN|# ISSNs})", file=ssci_list.path.name, n=len(ssci_list.issns))))
    else:
        out.append((WARN, ssci_name, t("Not set, so the SSCI status is guessed from the journal name (🟡). "
                                       "Put Clarivate's CSV in {dir}", dir=data_dir(root))))

    zotero = ZoteroClient.from_env()
    out.append((OK, "Zotero", t("Set")) if zotero
               else (OK, "Zotero", t("Not set (optional; with it, priorwork can see what is in Zotero and fetch full texts)")))

    if shutil.which("pandoc"):
        out.append((OK, "pandoc", t("Found (`priorwork export --format docx` works)")))
    else:
        out.append((OK, "pandoc", t("Not found (optional; needed only for Word output, not for HTML)")))

    if client is not None:
        out.extend(_online_checks(client, zotero))
    return out


def _online_checks(client: Any, zotero: Optional[ZoteroClient]) -> List[Check]:
    out: List[Check] = []
    for name, probe in ((t("Semantic Scholar connection"), lambda: client.search("minimum wage employment", limit=1)),
                        (t("OpenAlex connection"), lambda: client.openalex_works(dois=["10.1257/aer.91.5.1369"]))):
        try:
            out.append((OK, name, t("Responded")) if probe() else (WARN, name, t("Responded, but with no results")))
        except Exception as e:  # 接続・認証・レート制限など、原因を問わず診断結果として見せる
            out.append((NG, name, str(e)))
    if zotero:
        try:
            out.append((OK, t("Zotero connection"), t("WebDAV: {status}", status=zotero.check_webdav())))
        except ZoteroError as e:
            out.append((NG, t("Zotero connection"), str(e)))
    return out
