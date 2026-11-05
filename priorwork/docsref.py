# -*- coding: utf-8 -*-
"""AI 向けのリファレンス（priorwork/docs/reference.md・reference.ja.md）を、節ごとに読み出す。

同じ文章がウェブ（Pages の /reference/）にも出るが、エージェントがウェブを読めるとは限らず、
入っている Priorwork の版とウェブの版が違うこともある。だからパッケージの中に置き
（package-data の *.md）、`priorwork docs` で手元の版のものを読ませる。site/build.sh もここから組む。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from pathlib import Path

HEADING = re.compile(r'^(#{2,3}) (.+?)\s*$')


DOCS = Path(__file__).resolve().parent / "docs"


def source(lang: str) -> Optional[Path]:
    p = DOCS / ("reference.ja.md" if lang == "ja" else "reference.md")
    return p if p.exists() else None


def read(lang: str) -> str:
    p = source(lang) or source('en')
    if p is None:
        return ''
    # GitHub で読む人への案内（「ページで読んで」）は落とす
    return '\n'.join(ln for ln in p.read_text(encoding='utf-8').split('\n')
                     if '<!-- pages:skip -->' not in ln)


def sections(text: str) -> list:
    """[(level, title, first line, end line)]。コードブロックの中の # は見出しではない。"""
    lines = text.split('\n')
    heads, fence = [], None
    for i, ln in enumerate(lines):
        m = re.match(r'^(`{3,}|~{3,})', ln)
        if m:
            if fence is None:
                fence = m.group(1)
            elif ln.startswith(fence) and not ln[len(fence):].strip():
                fence = None
            continue
        if fence is None:
            h = HEADING.match(ln)
            if h:
                heads.append((len(h.group(1)), h.group(2), i))
    out = []
    for k, (level, title, start) in enumerate(heads):
        end = next((s for lv, _, s in heads[k + 1:] if lv <= level), len(lines))
        out.append((level, title, start, end))
    return out


def number(title: str) -> str:
    m = re.match(r'^(\d+(?:\.\d+)*)\.? ', title)
    return m.group(1) if m else ''


def find(text: str, query: str) -> list:
    """番号（`3` / `3.2`）か、見出しの言葉（大文字・小文字は問わない）で節を探す。"""
    secs = sections(text)
    q = query.strip().rstrip('.')
    if re.fullmatch(r'\d+(?:\.\d+)*', q):
        return [s for s in secs if number(s[1]) == q]
    low = q.lower()
    return [s for s in secs if low in s[1].lower()]


def search(text: str, word: str) -> list:
    """その言葉を含む、いちばん小さい節（### か、### のない ##）。"""
    lines = text.split('\n')
    secs = sections(text)
    low = word.lower()
    out = []
    for level, title, start, end in secs:
        inner = [s for s in secs if s[0] > level and start < s[2] < end]
        stop = inner[0][2] if inner else end
        if any(low in ln.lower() for ln in lines[start:stop]):
            out.append((level, title, start, stop))
    return out


def body(text: str, sec) -> str:
    return '\n'.join(text.split('\n')[sec[2]:sec[3]]).strip() + '\n'
