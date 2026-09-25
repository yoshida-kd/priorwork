"""表示する文字列の言語（Octavo の i18n.py と同じ仕組み）。

**コードに直接書く文字列は英語**で、日本語は `lang_ja.py` の対訳表に置く。
表示するときは `t()` を通す:

    from .i18n import t
    print(t("Registered {n|paper|papers}", n=len(added)))

言語の決め方は上から順に、最初に見つかったもの:

    PRIORWORK_LANG=ja / en       明示（`ja` で始まれば日本語、それ以外は英語）
    LC_ALL / LC_MESSAGES / LANG  ロケール（`ja` で始まれば日本語）
    どれも無ければ英語

**訳が無ければ英語のまま出る**（落ちない）。VS Code の拡張機能は、VS Code の
表示言語に合わせて PRIORWORK_LANG を渡す。

埋め込みは `{name}` の名前つきだけを見る（`str.format` は使わない。文言に
`{topic}` のような本物の波括弧が混じることがあるため）。

ここで訳すのは **CLI が画面に出すものだけ**。レポートの見出し・記入欄の名前、
ワークスペースに書き出す AGENTS.md・スキルは「ワークスペースの言語」
（`.priorwork/config.json` の `lang`、サーベイごとには状態ファイルの `lang`）で決まり、
こことは別（`survey.py` の REPORT_TEXT、`assets/<lang>/`）。
"""

import os
import re
from typing import Dict, Optional

# `{name}` だけを差し込み口として見る。二重の波括弧は文字どおり
_SLOT = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")
# 英語の単数・複数: `{n|paper|papers}` は n が 1 なら paper、それ以外は papers。
# 形の中の `#` はその数になる（`{n|the one is|all # are}`）。日本語の訳は `{n}` だけを使う
_PLURAL = re.compile(r"(?<!\{)\{(\w+)\|([^{}|]*)\|([^{}|]*)\}(?!\})")

LANGS = ("en", "ja")


def _count(v) -> Optional[int]:
    if isinstance(v, int):
        return v
    if isinstance(v, (list, tuple, set)):
        return len(v)
    try:
        return int(str(v).replace(",", ""))
    except ValueError:
        return None


def _plural(m: "re.Match", kw: dict) -> str:
    name, one, other = m.groups()
    if name not in kw:
        return m.group(0)
    form = one if _count(kw[name]) == 1 else other
    return form.replace("#", str(kw[name]))


def normalize(lang: Optional[str]) -> str:
    """'ja_JP.UTF-8' → 'ja'。日本語以外はすべて 'en'。"""
    return "ja" if (lang or "").lower().startswith("ja") else "en"


def language() -> str:
    """いま使う表示の言語。**毎回環境を見る**（テストが差し替えられるように）。"""
    explicit = os.environ.get("PRIORWORK_LANG")
    if explicit:
        return normalize(explicit)
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var)
        if v:
            return normalize(v)
    return "en"


def catalog(lang: Optional[str] = None) -> Dict[str, str]:
    if (lang or language()) != "ja":
        return {}
    from .lang_ja import MESSAGES
    return MESSAGES


def fill(text: str, **kw) -> str:
    """訳さずに差し込みだけ行う（レポートの文言など、言語を呼び出し側が決めるもの）。"""
    if not kw:
        return text
    text = _PLURAL.sub(lambda m: _plural(m, kw), text)
    return _SLOT.sub(lambda m: str(kw[m.group(1)]) if m.group(1) in kw else m.group(0), text)


def t(s: str, **kw) -> str:
    """表示用の文字列。訳が無ければ英語のまま返す。"""
    return fill(catalog().get(s, s), **kw)


def tl(lang: str, s: str, **kw) -> str:
    """言語を指定して訳す（レポートに書く文言。言語はサーベイが決める）。対訳表は t() と共通。"""
    return fill(catalog(normalize(lang)).get(s, s), **kw)
