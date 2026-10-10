"""表示の言語（i18n.t / tl）と対訳表（lang_ja.py）の見張り。

コードの中の `t('…')` / `tl(lang, '…')` を AST で拾い、動的に引く表（USAGE_LINES など）を足して、
lang_ja.MESSAGES との過不足と、差し込み口の名前の食い違いを調べる（Octavo の Messages と同じやり方）。
"""

import ast
import re
from pathlib import Path

import pytest

from priorwork import cli, i18n, ssci, survey
from priorwork.i18n import t, tl
from priorwork.lang_ja import MESSAGES

PKG = Path(survey.__file__).resolve().parent
_SLOT = re.compile(r"(?<!\{)\{(\w+)(?:\|[^{}|]*\|[^{}|]*)?\}(?!\})")


def used_messages():
    found = set()
    for f in sorted(PKG.glob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("t", "tl"):
                arg = node.args[0] if node.func.id == "t" else node.args[1]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    found.add(arg.value)
    # 変数を通して引く表
    found |= {ln for ln in cli.USAGE_LINES if ln}
    found |= {h for _, h in cli.STATUS_COMMANDS + cli.LINK_COMMANDS}
    found |= set(survey.STATUS_NAMES.values()) | set(survey.DEPTHS.values()) | set(survey.EVIDENCE_NAMES.values())
    found |= {label for _, label in survey.MANUSCRIPT_CARD_FIELDS + survey.SCOPE_ROWS}
    found |= set(survey.MATRIX_HEADS) | set(survey.LOG_HEADS) | {survey.BIBLIO_LABEL}
    found |= set(ssci.BADGE.values())
    return found


def test_every_message_has_a_japanese_translation():
    missing = sorted(used_messages() - set(MESSAGES))
    assert not missing, "lang_ja.py に訳がない:\n" + "\n".join(missing)


def test_no_translation_is_unused():
    unused = sorted(set(MESSAGES) - used_messages())
    assert not unused, "どこからも使われていない訳:\n" + "\n".join(unused)


def test_slots_match_between_the_languages():
    for en, ja in MESSAGES.items():
        assert set(_SLOT.findall(en)) == set(_SLOT.findall(ja)), en


def test_every_plural_form_is_in_english_only():
    for en, ja in MESSAGES.items():
        assert not re.search(r"\{\w+\|", ja), en


def test_language_follows_env_then_locale(monkeypatch):
    monkeypatch.delenv("PRIORWORK_LANG", raising=False)
    monkeypatch.setenv("LANG", "ja_JP.UTF-8")
    for var in ("LC_ALL", "LC_MESSAGES"):
        monkeypatch.delenv(var, raising=False)
    assert i18n.language() == "ja"
    monkeypatch.setenv("PRIORWORK_LANG", "en")
    assert i18n.language() == "en"


def test_plurals_and_slots(monkeypatch):
    monkeypatch.setenv("PRIORWORK_LANG", "en")
    assert t("{n|# search|# searches}", n=1) == "1 search"
    assert t("{n|# search|# searches}", n="1,523") == "1,523 searches"
    assert tl("ja", "{n|# search|# searches}", n=3) == "検索 3 回"
    assert t("no such message {x}", x=1) == "no such message 1"


@pytest.mark.parametrize("lang", i18n.LANGS)
def test_card_labels_round_trip_in_both_languages(lang):
    record = {"title": "T", "tldr": "", "abstract": "A"}
    body = survey.new_card_body(record, lang)
    fields = survey.parse_card_fields(body)
    assert survey.evidence_key(fields["evidence"]) == survey.EVIDENCE_UNCHECKED
    assert set(fields) >= {"evidence"}
