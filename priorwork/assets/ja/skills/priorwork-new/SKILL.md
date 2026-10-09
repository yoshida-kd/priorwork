---
name: priorwork-new
description: >-
  Starts a new social-science literature survey: settles the scope (research question, period, criteria,
  depth), creates reports/YYYYMMDD_<slug>.md with `./priorwork new`, and runs enough searches for the depth.
  Use when a survey on a new topic is needed, or when an existing survey needs more searches.
---

# 新しいサーベイを始める・検索する

ルールは [AGENTS.md](../../../AGENTS.md) に従う。

## 1. 範囲を決める

依頼から次の項目を決める。依頼に無いものは、テーマから妥当な案を自分で決めて進め、最後の報告で「こう決めた」と伝える。ユーザーに聞くのは、テーマが曖昧で検索語を決められないときだけ（相談モードでは、案を示して答えを待つ）。

- リサーチクエスチョン（1 文）
- 対象期間（例: 1990-2025。指定が無ければ空でよい）
- 分野（例: 行政学、労働経済学）
- 採用基準（例: 実証研究、国際査読誌）
- 除外基準（例: 理論のみ、WP）
- 英語の slug（例: `minimum_wage_employment`）
- 深さ（`quick` / `full`）: AGENTS.md「深さ」の表で決める。

```bash
./priorwork new "<テーマ（日本語可）>" --slug <slug> --depth quick|full --question "..." --years "..." --fields "..." --inclusion "..." --exclusion "..."
```

## 2. 検索する

まず、テーマをサブテーマ（概念・対象・手法の切り口）に分ける。full なら 3〜6、quick なら 1〜2。

サブテーマごとに、英語のクエリを 2〜4 本作り、通常の検索と `--bulk` を併用する。`--limit` は付けない（既定が深さに合わせてある）。

```bash
./priorwork search "local government outsourcing staff capacity" --into <survey>
./priorwork search '("contracting out" | outsourcing) + ("local government" | municipal) + (capacity | workforce)' --bulk --into <survey>
```

- `--bulk` の演算子は `+`（AND）・`|`（OR）・`-`（NOT）・`"フレーズ"`。`AND`/`OR` と書いても直されるが、語を詰め込みすぎると 0 件になる。
- 0 件・数件だったクエリは、語を減らす・同義語に変える・`--bulk` を外すなどして検索し直す。
- 検索語の例: 概念の英語表現と同義語、代表的な理論の名前（`"transaction cost"` など）、識別戦略（`"difference-in-differences"`）、対象国・地域。
- 有名な論文が分かっていれば `./priorwork add <survey> <DOI>` で直接登録してよい（`get` で書誌を確かめてから）。

`./priorwork status <survey>` が「検索を足す」と出す間は、まだ試していない切り口で検索を足す。

## 3. 次へ

選別（`priorwork-screen`）に進む。相談モードのときだけ、候補の件数と目立つ論文を伝えて答えを待つ。
