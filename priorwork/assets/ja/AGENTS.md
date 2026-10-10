# エージェント向け指示書

> このファイルは `priorwork sync` が生成します。直接編集しないでください。このワークスペース固有の指示は `AGENTS.local.md` に書かれています。そちらも読んでください（こちらと食い違うときは `AGENTS.local.md` を優先する）。

このリポジトリは、社会科学のテーマ別文献サーベイを作るための Priorwork のワークスペースです。
あなたはリサーチアシスタントとして、`./priorwork` コマンドで文献を探し・選び・記録し、レポートの文章を書きます。

## 頼まれ方と進め方

- **ユーザーはコマンドもスキル名も打たない。** 「〇〇について先行研究をまとめて」「full でサーベイして」「続きをやって」のような普通の言葉で頼まれる。その依頼から工程を判断し、スキル `priorwork`（入口）の手順で進める。`/priorwork` と打たれた場合も同じ。
- **既定は「任せて進める」。** 範囲の設定から、検索・選別・引用の追跡・カードの記入・文章・検査・書き出しまで、途中でユーザーの判断を待たずに最後まで進める。工程ごとに止まって「次に進みますか？」と聞かない。
  - 止まって聞くのは、テーマが曖昧で検索語を決められないとき、API キーなどの設定が無くて進めないとき、⚠️ の論文で掲載版が見つからず採否が結果を大きく左右するときだけ。
  - ユーザーが「相談しながら」「1件ずつ見せて」と言ったとき、または `AGENTS.local.md` にそう書かれているときは、**相談モード**にする: 範囲と採否は推薦を示してユーザーの答えを待つ（スキル `priorwork-screen` の「相談モード」）。
- **判断はすべて記録に残す。** 採否には必ず理由を付ける（採用にも `--reason`）。範囲（RQ・期間・基準）は `./priorwork new` / `scope` で書き込む。ユーザーはそれを見て、サイドバーや会話で覆せる。
- **ユーザーが下した判断を覆さない。** ユーザーが採否を変えた・カードを直したと言ったら、それに従う。自分の記憶ではなく `./priorwork list <survey>` とレポートを読み直してから続ける。
- **終わったら、まとめて報告する。** 何本検索して何本採用したか、範囲をどう決めたか（推測で決めた点）、残った WARN、読むための版の見方（下の「レポートを見せる」）を短く伝える。

## ディレクトリ

- `reports/YYYYMMDD_<slug>.md` … 作業用のレポート（管理ブロックや記入欄を含む）。エージェントが書く。
- `reports/YYYYMMDD_<slug>.draft.md` … 原稿から作ったサーベイで `./priorwork export --draft` が作る、原稿の 1〜3 章の下書き（参考文献つき）。
- `reports/YYYYMMDD_<slug>.html` … `./priorwork export` が作る**読むための版。人が読むのはこれ**。
  未記入・未確認・`check` の ERROR が残っていると、冒頭に「下書き」と表示される。
- `.priorwork/surveys/YYYYMMDD_<slug>.json` … 論文の候補・採否・検索履歴（状態）。`./priorwork` だけが書き換える。
- `.priorwork/config.json` … ワークスペースの設定（言語）。`./priorwork` だけが書き換える。
- `.priorwork/cache/`, `.priorwork/data/`, `.priorwork/sync.json` … 本文テキスト・SSCI リスト・同期の記録。触らない。ユーザーに開かせない。
- `.venv/` … Priorwork 本体（エンジン）。**中のファイルを読まない・開かない・直さない。** コマンドの使い方は `./priorwork <コマンド> --help` で調べる。出力がおかしいと思ったら、エンジンのコードを調べずにユーザーに伝える。

ユーザーへの報告では、内部のファイルではなく、レポートのどこが変わったかを伝える。

## 基本の考え方

- **状態は `./priorwork` が管理する。** JSON（`.priorwork/surveys/`）を直接編集しない。
- **Markdown は部分的に自動生成される。** `<!-- BEGIN priorwork:… -->` 〜 `<!-- END priorwork:… -->` の範囲は `./priorwork` が再生成する。手で書くのは、各論文カードの記入欄と、ブロック外の文章（背景・学説・論争点など）だけ。
- **`./priorwork status` が「スキルが古い」と警告したら、`./priorwork sync` を実行してから続ける。**
- **ワークスペースは Git で管理し、GitHub（非公開リポジトリ）に push する。** 一区切りついたら `reports/*.md` と `.priorwork/surveys/` などの変更をコミットしてよい。push はユーザーの了承を得てから行う。`.env`（API キー）はコミットしない。
- **会話を再開したら、まず状態を見る。** `./priorwork status`（一覧）→ `./priorwork status <survey>`（進捗と次にやること）。
- **ユーザーは VS Code の Priorwork のサイドバーからも操作する**（採否の記録・論文カードの直し・書き出しなど）。

## 工程とスキル

入口はスキル `priorwork`。状態を見て、次の工程のスキルの手順に従う。

| 工程 | スキル | 主なコマンド |
| :--- | :--- | :--- |
| 全体の進行（入口） | `priorwork` | `status` |
| 範囲を決めて作成・検索 | `priorwork-new` | `new`, `search --into` |
| 候補の選別 | `priorwork-screen` | `list`, `include`, `exclude`, `maybe` |
| 引用をたどって見落としを補う | `priorwork-snowball` | `snowball` |
| 各論文カードの記入 | `priorwork-extract` | `fulltext`, `card`, `render` |
| 検査と修正・書き出し | `priorwork-check` | `check`, `export` |
| 分析まで済んだ原稿の 1〜3 章を書く | `priorwork-manuscript` | `new --manuscript`, `card --set role=…`, `export --draft` |

ユーザーが自分の原稿（分析まで書いたもの）を示して、イントロ・先行研究・理論と仮説や、それを支える文献を求めたら、`priorwork-manuscript` の手順で進める。原稿は読むだけで、書き換えない。

## 深さ（quick / full）

サーベイには深さがある（既定・未設定は full）。`./priorwork status <survey>` に表示される。依頼に「quick」「さっと」「概観」などとあれば quick、「full」「本格的に」「網羅的に」とあれば full にする。どちらとも言われなければ、テーマの広さから決め、報告でそう伝える。

| | quick（簡易） | full（本格） |
| :--- | :--- | :--- |
| 検索 | 2〜3 クエリ | サブテーマを 3〜6 に分け、それぞれ 2〜4 クエリ（通常の検索と `--bulk` を併用） |
| 件数の目安 | 候補 30 本前後、採用 15〜20 本 | 候補 **100 本以上**、採用 30 本以上。`./priorwork status` が「検索を足す」と出す間は検索を足す |
| `--limit` | 既定（10）のまま | 既定（25）のまま。減らさない |
| スナウボール | 任意 | 行う（採用が増えたら再実行） |
| カード | 要旨のみでよい | 中核論文は本文確認済まで |
| 文章 | 概観と比較表 | 背景・学説・論争点・研究の空白まで |

件数は目安で、固定の上限ではない。0 件だった検索は、語を減らすか言い換えて検索し直す。ルールと `./priorwork check` は深さによらず同じ。ただし full では、`./priorwork check` がスナウボール未実施を WARN、「要旨のみ」のカードを INFO で伝える。深さは後から `./priorwork scope SURVEY --depth full` で変えられる。

## レポートを見せる

`./priorwork export <survey>` で HTML を書き出したら、ユーザーには次の見方を伝える（SSH でつないだサーバーでもこれで見られる。Live Preview や Live Server を勧めない）。

- VS Code の Priorwork のサイドバーで、サーベイを右クリック →「レポートを書き出して見る」。
- またはエクスプローラーで `reports/<名前>.html` を右クリック →「Priorwork でレポートを見る」。

## Zotero

Zotero への書き込みはユーザーが手作業で行う。エージェントは Zotero に書き込まない。

- **採用論文を Zotero に集めたい**と言われたら、`./priorwork zotero <survey> --dois` の DOI の一覧を示し、「Zotero で集めたいコレクションを選び、魔法の杖（識別子でアイテムを追加）に貼る」と伝える。サイドバーの次にやることの「Zotero に追加」でも DOI をまとめてコピーできる。
- **ユーザーが Zotero のコレクションを教えてくれたら**、`./priorwork zotero <survey> --collection "<名前>"` で結び付ける（名前が分からなければ `./priorwork zotero --collections` で一覧）。以後、
  - 「Zotero にあるか」はそのコレクションに入っているかで判定される。
  - `./priorwork zotero <survey> --import` で、コレクションの論文を候補に登録できる。これはユーザーが自分で選んで入れた論文なので、範囲から明らかに外れない限り採用する。
  - 本文（`./priorwork fulltext`）はそのコレクションの PDF を優先して読む。カードの記入も、コレクションに PDF がある論文から始める。

## ルール

1. **対象は国際査読誌論文。SSCI 収録誌を優先する**
   - WP（NBER、IZA DP など）、プレプリント（SSRN、arXiv など）、紀要、学会報告は、ユーザーの指示がない限り採用しない。
   - 古典的な書籍は、背景の説明で触れてよいが採用論文には入れない。
2. **でっち上げない**
   - 文章中で論文に言及するときは、その論文が `./priorwork` に登録されていること。記憶だけで著者・年・DOI を書かない。
   - カードには要旨・本文に書かれていることだけを書き、確認レベル（未確認 / 要旨のみ / 本文確認済）を必ず更新する。
3. **⚠️ を無視しない**
   - 「DOI が別タイトルを指している」「DOI は WP / プレプリント版」「書評・コメントの可能性」などの警告がある論文は、`priorwork-screen` の手順で掲載版に置き換えるか、置き換えられなければ保留にして報告で伝える。
4. **SSCI 判定を偽らない**
   - 🟡（誌名推定）を「SSCI 収録」と断定しない。雑誌単体の判定は `./priorwork journal "<誌名 or ISSN>"`。
5. **BibTeX の引用キーを作らない**（ユーザーが Zotero で管理する）。参照文献は `./priorwork` が DOI つきで生成する。
6. **完成と言う前に `./priorwork check` を通す**。ERROR が残っていれば、完成とは言わずに残りを伝える。
7. **検索クエリは英語**。日本語のテーマは、同義語を含む英語のクエリに言い換えてから検索する。`--bulk` の演算子は `+`（AND）・`|`（OR）・`-`（NOT）。
8. **API の待ち時間は正常**。レート制限の再試行中は止めずに待つ。エラーで終わったら少し時間をおいて再実行する。
9. **登録できない文献がある**。国内学会誌（J-STAGE など）は Semantic Scholar・OpenAlex に無いことが多く、`add` できない。その場合は無理に登録せず、報告で伝える。

## コマンド早見表

```bash
./priorwork status [SURVEY]          # 一覧 / 進捗と次にやること
./priorwork new "<テーマ>" --slug <slug> [--depth quick|full] [--manuscript PATH] [--question ... --years ... --fields ... --inclusion ... --exclusion ...]
./priorwork scope SURVEY [--question ...] [--depth quick|full] [--manuscript PATH]
./priorwork search "<English query>" [--into SURVEY] [--bulk] [--sort citations|relevance|recent|cpy] [--year 2010-2024] [--ssci-only] [--limit N]
./priorwork list SURVEY [--status candidate maybe included excluded] [--abstract]
./priorwork include SURVEY N... --reason "..."   ./priorwork exclude SURVEY N... --reason "..."   ./priorwork maybe SURVEY N... --reason "..."   ./priorwork reset SURVEY N...
./priorwork add SURVEY <DOI>... [--candidate]
./priorwork snowball SURVEY [--direction both|references|citations] [--limit N] [--min-links N]
./priorwork fulltext SURVEY N [--pdf PATH]
./priorwork card SURVEY N [--set KEY=VALUE ...]
./priorwork render SURVEY
./priorwork check SURVEY [--offline]
./priorwork export SURVEY [--format html|docx|md] [--with-abstracts]   # 読むための版を書き出す
./priorwork export SURVEY --draft [--format md|docx|html]             # 原稿の 1〜3 章の下書き（原稿から作ったサーベイ）
./priorwork zotero [SURVEY] [--collections] [--collection NAME] [--import] [--dois]
./priorwork get <DOI>      ./priorwork citations <DOI> [--sort cited]      ./priorwork references <DOI> [--sort cited]      ./priorwork journal "<誌名>"
./priorwork doctor [--online]        # 設定の診断（動作がおかしいとき）
./priorwork sync                     # AGENTS.md・スキルをエンジンの版に更新
```

`SURVEY` は `20260917_minimum_wage_employment` のようなファイル名（拡張子なし）か、slug（`minimum_wage_employment`）で指定する。
