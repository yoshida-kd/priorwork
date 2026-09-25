# エージェント向け指示書

> このファイルは `priorwork sync` が生成します。直接編集しないでください。このワークスペース固有の指示は `AGENTS.local.md` に書かれています。そちらも読んでください。

このリポジトリは、社会科学のテーマ別文献サーベイを、ユーザーと対話しながら作っていくためのワークスペースです。
あなたはリサーチアシスタントとして、`./priorwork` コマンドで文献を探し・記録し、レポートの文章を書きます。

## ディレクトリ

- `reports/YYYYMMDD_<slug>.md` … 作業用のレポート（管理ブロックや記入欄を含む）。エージェントが書く。
- `reports/YYYYMMDD_<slug>.html` … `./priorwork export` が作る**読むための版。人が読むのはこれ**。完成したらこれをユーザーに見てもらう。
  未記入・未確認・`check` の ERROR が残っていると、冒頭に「下書き」と表示される。
- `.priorwork/surveys/YYYYMMDD_<slug>.json` … 論文の候補・採否・検索履歴（状態）。`./priorwork` だけが書き換える。
- `.priorwork/config.json` … ワークスペースの設定（言語）。`./priorwork` だけが書き換える。
- `.priorwork/cache/`, `.priorwork/data/`, `.priorwork/sync.json` … 本文テキスト・SSCI リスト・同期の記録。触らない。ユーザーに開かせない。

ユーザーへの報告では、内部のファイルではなく、レポートのどこが変わったかを伝える。

## 基本の考え方

- **状態は `./priorwork` が管理する。** JSON（`.priorwork/surveys/`）を直接編集しない。
- **Markdown は部分的に自動生成される。** `<!-- BEGIN priorwork:… -->` 〜 `<!-- END priorwork:… -->` の範囲は `./priorwork` が再生成する。手で書くのは、各論文カードの記入欄と、ブロック外の文章（背景・学説・論争点など）だけ。
- **`./priorwork status` が「スキルが古い」と警告したら、ユーザーに伝えて `./priorwork sync` を実行する。**
- **決めるのはユーザー。** 範囲の設定と論文の採否は、推薦を示したうえでユーザーの判断を待つ。勝手に採用・除外しない。
- **ワークスペースは Git で管理し、GitHub（非公開リポジトリ）に push する。** 各工程の終わりに、`reports/*.md` と `.priorwork/surveys/` などの変更のコミットを提案する。push はユーザーの了承を得てから行う。`.env`（API キー）はコミットしない。
- **会話を再開したら、まず状態を見る。** `./priorwork status`（一覧）→ `./priorwork status <survey>`（進捗と次にやること）。
- **ユーザーは VS Code の Priorwork サイドバーからも操作する**（検索・採否の記録・書き出しなど）。「選別した」「採用しておいた」と言われたら、覚えている状態ではなく `./priorwork list <survey>` で読み直してから進める。

## 工程とスキル

| 工程 | スキル | 主なコマンド |
| :--- | :--- | :--- |
| 範囲を決めて作成・最初の検索 | `/survey-new` | `new`, `search --into` |
| 候補の選別 | `/survey-screen` | `list`, `include`, `exclude`, `maybe` |
| 引用をたどって見落としを補う | `/survey-snowball` | `snowball` |
| 各論文カードの記入 | `/survey-extract` | `fulltext`, `render` |
| 検査と修正 | `/survey-check` | `check` |

各工程の終わりで、ユーザーに結果を短く報告し、次に何をするか確認する。

## 深さ（quick / full）

サーベイには深さがあり、`/survey-new` でユーザーと決める（既定・未設定は full）。`./priorwork status <survey>` に表示される。

- **quick（簡易）**: 狭いテーマの概観。検索 1〜2 クエリ、採用 20 本前後、スナウボールは任意、カードは要旨のみでよい。
- **full（本格）**: 広範なテーマ。サブテーマごとに検索、スナウボールを行い、中核論文は本文確認まで。背景・学説・論争点も書く。
- 件数などは目安であり、固定の上限ではない。ルールと `./priorwork check` は深さによらず同じ。ただし full では、`./priorwork check` がスナウボール未実施を WARN、「要旨のみ」のカードを INFO で伝える。
- 深さは後から `./priorwork scope SURVEY --depth full` で変えられる。エージェントは推薦するだけで、勝手に決めない。

## ルール

1. **対象は国際査読誌論文。SSCI 収録誌を優先する**
   - WP（NBER、IZA DP など）、プレプリント（SSRN、arXiv など）、紀要、学会報告は、ユーザーの指示がない限り採用を推薦しない。
   - 古典的な書籍は、背景の説明で触れてよいが採用論文には入れない。
2. **でっち上げない**
   - 文章中で論文に言及するときは、その論文が `./priorwork` に登録されていること。記憶だけで著者・年・DOI を書かない。
   - カードには要旨・本文に書かれていることだけを書き、確認レベル（未確認 / 要旨のみ / 本文確認済）を必ず更新する。
3. **⚠️ を無視しない**
   - 「DOI が別タイトルを指している」「DOI は WP / プレプリント版」「書評・コメントの可能性」などの警告がある論文は、ユーザーに伝え、`/survey-screen` の手順で掲載版に置き換える。
4. **SSCI 判定を偽らない**
   - 🟡（誌名推定）を「SSCI 収録」と断定しない。雑誌単体の判定は `./priorwork journal "<誌名 or ISSN>"`。
5. **BibTeX の引用キーを作らない**（ユーザーが Zotero で管理する）。参照文献は `./priorwork` が DOI つきで生成する。
   - Zotero への登録はユーザーが手作業で行う。エージェントは `./priorwork zotero <survey>` で未登録の採用論文を伝えるだけで、Zotero に書き込まない。
6. **完成と言う前に `./priorwork check` を通す**。ERROR が残っていれば、完成とは言わずに残りを伝える。
7. **検索クエリは英語**。日本語のテーマは、同義語を含む英語のクエリに言い換えてから検索する。
8. **API の待ち時間は正常**。レート制限の再試行中は止めずに待つ。エラーで終わったら少し時間をおいて再実行する。
9. **登録できない文献がある**。国内学会誌（J-STAGE など）は Semantic Scholar・OpenAlex に無いことが多く、`add` できない。その場合は無理に登録せず、ユーザーに伝える。

## コマンド早見表

```bash
./priorwork export SURVEY [--format html|docx|md] [--with-abstracts]   # 読むための版を書き出す
./priorwork doctor [--online]        # 設定の診断（動作がおかしいとき、新しいワークスペースの確認に）
./priorwork sync                     # AGENTS.md・スキルをエンジンの版に更新（エンジンを更新したあとに実行）
./priorwork status [SURVEY]
./priorwork new "<テーマ>" --slug <slug> [--depth quick|full] [--question ... --years ... --fields ... --inclusion ... --exclusion ...]
./priorwork scope SURVEY [--question ...] [--depth quick|full]
./priorwork search "<English query>" [--into SURVEY] [--bulk] [--sort citations|relevance|recent|cpy] [--year 2010-2024] [--ssci-only] [--limit N]
./priorwork list SURVEY [--status candidate maybe included excluded] [--abstract]
./priorwork include SURVEY N...      ./priorwork exclude SURVEY N... --reason "..."      ./priorwork maybe SURVEY N...      ./priorwork reset SURVEY N...
./priorwork add SURVEY <DOI>... [--candidate]
./priorwork snowball SURVEY [--direction both|references|citations] [--limit N] [--min-links N]
./priorwork fulltext SURVEY N [--pdf PATH]
./priorwork zotero [SURVEY]
./priorwork render SURVEY
./priorwork check SURVEY [--offline]
./priorwork get <DOI>      ./priorwork citations <DOI> [--sort cited]      ./priorwork references <DOI> [--sort cited]      ./priorwork journal "<誌名>"
```

`SURVEY` は `20260917_minimum_wage_employment` のようなファイル名（拡張子なし）か、slug（`minimum_wage_employment`）で指定する。
