"""手引き・クイックガイド・リファレンスに書いた priorwork のコマンドとオプションが、実際にあること。

エージェントはリファレンスのとおりに実行するので、無いオプションを書くと誤ったコマンドを打たせる。
"""

import argparse
import re
from pathlib import Path

from priorwork import cli

REPO = Path(__file__).resolve().parent.parent
DOCS = [*sorted((REPO / "docs").glob("*.md")), *sorted((REPO / "priorwork" / "docs").glob("*.md")),
        REPO / "priorwork" / "assets" / "en" / "AGENTS.md", REPO / "priorwork" / "assets" / "ja" / "AGENTS.md"]


def options(parser) -> set:
    out = set()
    for a in parser._actions:
        out |= set(a.option_strings)
        if isinstance(a, argparse._SubParsersAction):
            for q in a.choices.values():
                out |= options(q)
    return out


def mentions(text: str) -> list:
    """コードブロックの行と、インラインのコードのうち (./)priorwork … で始まるもの。"""
    lines = []
    for body in re.findall(r"^```\w*\n(.*?)^```", text, re.S | re.M):
        lines += body.split("\n")
    lines += re.findall(r"`((?:\./)?priorwork [^`]+)`", text)
    out = []
    for ln in lines:
        ln = re.sub(r"\s+#\s.*$", "", ln).strip()
        # 1行に2つ書いた所（`./priorwork a …   ./priorwork b …`）は分ける
        for part in re.split(r"\s{2,}(?=(?:\./)?priorwork )|\s/\s(?=(?:\./)?priorwork )", ln):
            if re.match(r"(?:\./)?priorwork [a-z]", part):
                out.append(part)
    return out


def test_every_command_and_option_exists():
    sub = next(a for a in cli.build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    bad = []
    for doc in DOCS:
        for ln in mentions(doc.read_text(encoding="utf-8")):
            words = ln.split()
            for cmd in words[1].split("|"):
                if cmd not in sub.choices:
                    bad.append((doc.name, ln))
                    continue
                known = options(sub.choices[cmd])
                bad += [(doc.name, f) for f in re.findall(r"(?<![\w-])--[a-z][a-z-]*", ln) if f not in known]
    assert bad == []
