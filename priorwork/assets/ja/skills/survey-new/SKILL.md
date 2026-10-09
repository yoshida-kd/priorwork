---
name: survey-new
description: >-
  Starts a new social-science literature survey: agrees on the scope with the user, creates
  reports/YYYYMMDD_<slug>.md and .priorwork/surveys/YYYYMMDD_<slug>.json with `./priorwork new`, and runs the first searches.
  Use when the user wants to begin a survey or literature review on a new topic.
---

# 新しいサーベイを始める

ルールは [AGENTS.md](../../../AGENTS.md) に従う。

## 1. 範囲をユーザーと決める（ここで一度止まる）

次の項目を、ユーザーの依頼から読み取れる範囲で案として示し、確認をとる。

- リサーチクエスチョン（1 文）
- 対象期間（例: 1990-2025）
- 分野（例: 労働経済学、社会学）
- 採用基準（例: 因果識別のある実証研究、国際査読誌）
- 除外基準（例: 理論のみ、シミュレーションのみ、WP）
- 英語の slug（例: `minimum_wage_employment`）
- 深さ（`quick` / `full`）。テーマの広さから推薦を示し、ユーザーに決めてもらう。

  | | quick（簡易） | full（本格） |
  | :--- | :--- | :--- |
  | 向くテーマ | 狭い・概観だけ欲しい | 広い・サブテーマが複数ある・網羅性が要る |
  | 検索 | 1〜2 クエリ、`--ssci-only` | サブテーマごとに複数クエリ |
  | 採用の目安 | 20 本前後（固定ではない） | 制限なし |
  | スナウボール | 任意 | 行う |
  | カード | 要旨のみでよい | 中核論文は本文確認済まで |
  | 文章 | 概観と比較表 | 背景・学説・論争点・研究の空白まで |

  深さで変わるのは進め方の目安だけで、AGENTS.md のルールと `./priorwork check` は同じように適用する。
  迷ったら quick で始めてよい。後から `./priorwork scope <survey> --depth full` で切り替えられる。

合意できたら作成する。

```bash
./priorwork new "<テーマ（日本語可）>" --slug <slug> --depth quick|full --question "..." --years "..." --fields "..." --inclusion "..." --exclusion "..."
```

## 2. 最初の検索

- クエリは必ず英語にする。同義語・言い換えで試す（quick: 1〜2 本、full: サブテーマごとに 2〜4 本以上）。
- 通常の検索（関連度が高い）と `--bulk`（ブール演算・被引用数の多い順。定番論文を拾いやすい）を併用する。

```bash
./priorwork search "<English query>" --into <survey> --limit 10
./priorwork search '"minimum wage" + (employment | "job loss")' --bulk --into <survey> --limit 10
```

検索語の例: 概念の英語表現、代表的な識別戦略（`"difference-in-differences"` など）、対象国・地域。

## 3. ユーザーに報告して止まる

- 登録された候補の件数と、目立つ論文（被引用数の多いもの、⚠️ 付き）を短く示す。
- 次は候補の選別（`/survey-screen`）に進むか、検索を追加するかを聞く。VS Code の Prior Work のサイドバーでユーザー自身が選別することもできる、と伝える。
