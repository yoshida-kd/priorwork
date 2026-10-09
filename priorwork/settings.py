"""ワークスペースの設定（`priorwork settings`）: `.env` の API キーなどと、SSCI 収録リストの取り込み。

VS Code の拡張機能の設定ページがこれを通して読み書きする（拡張機能は `.env` を直接触らない）。
キーの値は表示しない（「設定済みか」だけを返す）。書き換えはキーを引数に載せないよう、標準入力の JSON で受け取る。
`.env` のコメントや、ここで扱わない行はそのまま残す。
"""

import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import ssci
from .i18n import t
from .workspace import ASSETS_DIR, data_dir

# (変数名, 秘密か)。並びは設定ページの並び
ITEMS = [
    ("SEMANTIC_SCHOLAR_API_KEY", True),
    ("OPENALEX_API_KEY", True),
    ("OPENALEX_MAILTO", False),
    ("ZOTERO_API_KEY", True),
    ("ZOTERO_USER_ID", False),
    ("ZOTERO_DATA_DIR", False),
    ("ZOTERO_WEBDAV_URL", False),
    ("ZOTERO_WEBDAV_USER", False),
    ("ZOTERO_WEBDAV_PASSWORD", True),
]
SECRETS = {k for k, secret in ITEMS if secret}
SSCI_FILE = "ssci_journals.csv"   # 取り込んだリストの置き場所（ssci.DEFAULT_SSCI_LIST と同じ名前）

_LINE = re.compile(r"^\s*(#\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


class SettingsError(Exception):
    pass


def env_path(root: Path) -> Path:
    return root / ".env"


def _unquote(raw: str) -> str:
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    return re.split(r"\s+#", v, 1)[0].strip()   # 引用符の無い値の後ろのコメント


def _quote(value: str) -> str:
    if not re.search(r"[\s#'\"]", value):
        return value
    if "'" not in value:
        return f"'{value}'"   # 一重引用符の中は、python-dotenv もそのまま読む（\ を解釈しない）
    raise SettingsError(t("A value cannot contain both a quote (') and spaces or #: {value}", value=value))


def read_env(root: Path) -> Dict[str, str]:
    """`.env` の値（コメントアウトされた行は読まない）。"""
    try:
        lines = env_path(root).read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    values = {}
    for line in lines:
        m = _LINE.match(line)
        if m and not m.group(1):
            values[m.group(2)] = _unquote(m.group(3))
    return values


def status(root: Path) -> Dict[str, Any]:
    env = read_env(root)
    items = [{"key": k, "secret": secret, "set": bool(env.get(k)), "value": "" if secret else env.get(k, "")}
             for k, secret in ITEMS]
    lst = ssci.get_ssci_list()
    return {"env": str(env_path(root)), "exists": env_path(root).is_file(), "items": items,
            "ssci": {"file": lst.path.name if lst.loaded and lst.path else None, "journals": len(lst.titles)}}


def update(root: Path, values: Dict[str, Optional[str]]) -> List[str]:
    """値を書き換える。None はそのまま、空文字は消す。変えた変数名を返す。"""
    known = {k for k, _ in ITEMS}
    unknown = sorted(set(values) - known)
    if unknown:
        raise SettingsError(t("Unknown settings: {names}", names=", ".join(unknown)))
    path = env_path(root)
    if not path.exists():
        example = ASSETS_DIR / "env.example"
        path.write_text(example.read_text(encoding="utf-8") if example.exists() else "", encoding="utf-8")
    lines = path.read_text(encoding="utf-8").splitlines()
    current = read_env(root)
    changed = []
    for key, value in values.items():
        if value is None:
            continue
        value = value.strip()
        if "\n" in value or "\r" in value:
            raise SettingsError(t("A value must be on one line: {key}", key=key))
        if current.get(key, "") == value:
            continue
        new = f"{key}={_quote(value)}"
        matches = [(i, m) for i, m in ((i, _LINE.match(ln)) for i, ln in enumerate(lines)) if m and m.group(2) == key]
        active = [i for i, m in matches if not m.group(1)]
        commented = [i for i, m in matches if m.group(1)]
        if active:
            lines[active[0]] = new
            for i in reversed(active[1:]):   # 同じ変数が何度も書かれていたら、最初の1つにまとめる
                del lines[i]
        elif commented:
            lines[commented[0]] = new
        else:
            lines.append(new)
        changed.append(key)
    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if os.name == "posix":
            path.chmod(0o600)
    return changed


def import_ssci(root: Path, src: Path) -> Dict[str, Any]:
    """Master Journal List からダウンロードした SSCI の CSV を、ワークスペースに取り込む。"""
    src = src.expanduser()
    if not src.is_file():
        raise SettingsError(t("File not found: {path}", path=src))
    try:
        lst = ssci.SSCIJournalList(src)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise SettingsError(t("Could not read {file}: {error}", file=src.name, error=e)) from e
    if not lst.loaded:
        raise SettingsError(t("{file} has no journal title or ISSN column. Download the SSCI list as CSV from "
                              "the Master Journal List", file=src.name))
    dest = data_dir(root) / SSCI_FILE
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    ssci._list_cache = None   # このプロセスでも新しいリストを使う
    return {"file": dest.name, "journals": len(lst.titles)}
