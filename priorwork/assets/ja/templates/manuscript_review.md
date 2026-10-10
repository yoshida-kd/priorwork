---
title: "{topic_yaml} — 原稿のための先行研究"
topic: "{topic_yaml}"
date: "{date}"
tags:
  - social-science
  - survey
  - literature-review
  - manuscript
status: draft # draft | in-progress | completed
---

# {topic} — 原稿のための先行研究

> [!NOTE]
> 分析（データと方法・分析）まで済んだ原稿を補強する文献を集め、原稿の 1〜3 章（イントロ・先行研究・理論と仮説）を下書きするレポートです。
> `<!-- BEGIN priorwork:… -->` 〜 `<!-- END priorwork:… -->` の範囲は `priorwork` コマンドが再生成します。
> 手で書き換えてよいのは、4章の各論文カードの記入欄（確認レベル〜メモ）と、ブロック外の文章だけです。

## 0. 調査の範囲
<!-- BEGIN priorwork:scope -->
<!-- END priorwork:scope -->

## 1. 原稿の要約
- **リサーチクエスチョン**:
- **Y（結果変数）**:
- **X（説明変数・処置）**:
- **データ・対象・期間**:
- **識別戦略・方法**:
- **主な結果**:
- **予想と違った・頑健でない結果**:

## 2. 文献で支える主張
| ID | 主張 | 原稿で使う場所 | 支える文献 | 食い違う・限定する文献 |
| :--- | :--- | :--- | :--- | :--- |
| C1 | | | | |

## 3. 文献比較マトリクス
4章のカードの記入内容から自動で作られます。

<!-- BEGIN priorwork:matrix -->
<!-- END priorwork:matrix -->

## 4. 各論文の詳細
記入のルール:
- 要旨・本文に書かれていることだけを書く。書かれていなければ「記載なし」と書く
- **確認レベル** は「未確認 / 要旨のみ / 本文確認済」のいずれか
- **原稿での役割** は、2章の主張の ID と関係（支持 / 食い違い / 理論の出どころ / 方法の先例 / 背景）。例: 「C2 支持; 方法の先例」
- 1 行目（`**RQ**: ...` の行内）はマトリクスに載るので短く。詳細は直下の箇条書きに書く

<!-- BEGIN priorwork:papers -->
<!-- END priorwork:papers -->

<!-- priorwork:draft -->
## 5. 原稿の下書き
<!-- 原稿の言語で書く（見出しも原稿の言語にしてよい）。`priorwork export <survey> --draft` で、この節だけを参考文献つきで書き出す。 -->

### Introduction

### Literature review

### Theory and hypotheses

## 6. 仮説の根拠と後付けの点検
- **先行研究から導いた仮説と、その根拠の文献**:
- **結果を見てから加えた・変えた点**:
- **探索的な発見として扱う結果**:
- **原稿の結果と食い違う先行研究と、その扱い**:

## 7. 参照文献
引用キーは Zotero で管理する（ここではキーを作らない）。

<!-- BEGIN priorwork:references -->
<!-- END priorwork:references -->

## 付録. 文献探索の記録
<!-- BEGIN priorwork:log -->
<!-- END priorwork:log -->
