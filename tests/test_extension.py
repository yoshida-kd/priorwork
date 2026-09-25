"""VS Code の拡張機能（vscode-extension/）の見張り。JS のテストは無いので、壊れやすい約束はここで確かめる。

- package.json の `%key%` が英語・日本語の package.nls*.json で引けること（過不足なし）
- `vscode.l10n.t('…')` の文言に日本語訳（l10n/bundle.l10n.ja.json）があること（過不足・{0} の食い違いなし）
- package.json に書いたコマンドと、extension.ts が登録するコマンドが一致すること
- Marketplace に出せる形であること（版が CLI と同じ、CHANGELOG にその版の節、アイコンが PNG など）
"""

import json
import re
from pathlib import Path

import pytest

from priorwork import __version__

EXT = Path(__file__).resolve().parent.parent / "vscode-extension"
pytestmark = pytest.mark.skipif(not EXT.exists(), reason="no extension in this tree")

_LIT = r"'(?:[^'\\]|\\.)*'"
_CALL = re.compile(r"(?:vscode\.l10n|\bL)\.t\(\s*(" + _LIT + r"(?:\s*\+\s*" + _LIT + r")*)")


def _unquote(s: str) -> str:
    return json.loads('"' + s[1:-1].replace('"', '\\"').replace("\\'", "'") + '"')


def l10n_strings():
    found = set()
    for f in sorted((EXT / "src").glob("*.ts")):
        for m in _CALL.finditer(f.read_text(encoding="utf-8")):
            found.add("".join(_unquote(x) for x in re.findall(_LIT, m.group(1))))
    return found


def manifest():
    return json.loads((EXT / "package.json").read_text(encoding="utf-8"))


def nls(name):
    return json.loads((EXT / name).read_text(encoding="utf-8"))


def test_every_manifest_key_is_translated():
    used = set(re.findall(r'"%([\w.]+)%"', (EXT / "package.json").read_text(encoding="utf-8")))
    en, ja = nls("package.nls.json"), nls("package.nls.ja.json")
    assert used == set(en), (used - set(en), set(en) - used)
    assert set(en) == set(ja), set(en) ^ set(ja)


def test_every_runtime_string_is_translated():
    used = l10n_strings()
    bundle = nls("l10n/bundle.l10n.ja.json")
    assert not used - set(bundle), sorted(used - set(bundle))
    assert not set(bundle) - used, sorted(set(bundle) - used)
    for en, ja in bundle.items():
        assert sorted(re.findall(r"\{\d+\}", en)) == sorted(re.findall(r"\{\d+\}", ja)), en


def test_contributed_commands_are_registered():
    contributed = {c["command"] for c in manifest()["contributes"]["commands"]}
    source = (EXT / "src" / "extension.ts").read_text(encoding="utf-8")
    registered = set(re.findall(r"^\s+'(priorwork\.\w+)': ", source, re.M))
    assert contributed == registered, (contributed - registered, registered - contributed)
    used_in_menus = {m["command"] for menu in manifest()["contributes"]["menus"].values() for m in menu}
    assert used_in_menus <= contributed


def test_marketplace_listing_is_complete():
    m = manifest()
    assert m["name"] == "priorwork" and m["publisher"] == "yoshida-kd" and not m.get("private")
    assert m["version"] == __version__, "vscode-extension/package.json と priorwork/__init__.py の版を揃える"
    toml = (EXT.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^version = "([^"]+)"', toml, re.M).group(1) == __version__, "pyproject.toml の版も揃える"
    assert f"## {__version__}" in (EXT / "CHANGELOG.md").read_text(encoding="utf-8")
    icon = EXT / m["icon"]
    assert icon.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert m["repository"]["url"].endswith("yoshida-kd/priorwork.git")
    assert (EXT / "LICENSE").exists() and (EXT / "README.md").exists()
    ignored = (EXT / ".vscodeignore").read_text(encoding="utf-8").split()
    assert "src/**" in ignored and "node_modules/**" in ignored


def test_webview_script_only_sends_messages_the_panel_handles():
    js = (EXT / "media" / "paper.js").read_text(encoding="utf-8")
    ts = (EXT / "src" / "paper.ts").read_text(encoding="utf-8")
    sent = set(re.findall(r"type: '(\w+)'", js))
    handled = set(re.findall(r"case '(\w+)':", ts))
    assert sent and sent <= handled, sent - handled
