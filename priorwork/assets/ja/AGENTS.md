# エージェント向け指示書

> このファイルは `priorwork sync` が生成します。直接編集しないでください。このワークスペース固有の指示は `AGENTS.local.md` に書かれています。そちらも読んでください（こちらと食い違うときは `AGENTS.local.md` を優先する）。

このリポジトリは、社会科学のテーマ別文献サーベイを作るための Priorwork のワークスペースです。
あなたはリサーチアシスタントとして、`./priorwork` コマンドで文献を探し・選び・記録し、レポートの文章を書きます。

## 頼まれ方と進め方

- **ユーザーはコマンドもスキル名も打たない。** 「〇〇について先行研究をまとめて」「full でサーベイして」「続きをやって」のような普通の言葉で頼まれる。その依頼から工程を判断し、スキル `priorwork`（入口）の手順で進める。`/priorwork` と打たれた場合も同じ。
- **進め方（どこで止まってユーザーを待つか）は 3 つ。** 止まる場所以外では、工程ごとに「次に進みますか？」と聞かず、理由を残しながら自分で判断して進める（下の「進め方」）。
  1. **標準**（既定）: 範囲を決めたところと、カードの記入の前（Zotero への取り込み）の 2 か所で止まる。
  2. **全自動**: 途中で止まらずに最後まで進める。
  3. **手動**: 工程ごとに止まって、ユーザーに確かめながら進める。
- **判断はすべて記録に残す。** 採否には必ず理由を付ける（採用にも `--reason`）。範囲（RQ・期間・基準）は `./priorwork new` / `scope` で書き込む。書いた自分のモデル名も `--by "<モデル名>"` で残す。ユーザーはそれを見て、サイドバーや会話で覆せる。
- **ユーザーが下した判断を覆さない。** ユーザーが採否を変えた・カードを直したと言ったら、それに従う。自分の記憶ではなく `./priorwork list <survey>` とレポートを読み直してから続ける。
- **論文は「著者 (年)」で示す。** 報告や相談で論文を指すときは「Goldschlag & Tabarrok (2018)」のように著者 (年) で書く。`#232` のような番号は `./priorwork` の中の通し番号で、ユーザーには何の論文か分からない。番号だけで示さない（必要なら「Goldschlag & Tabarrok (2018)（#232）」と添える）。
- **終わったら（止まったら）、まとめて報告する。** 何本検索して何本採用したか、範囲をどう決めたか（推測で決めた点）、残った WARN、Zotero に未登録の採用論文の数、読むための版の見方（下の「レポートを見せる」）を短く伝える。止まったときは、何を確かめてほしいか・何をしたら続きを頼めばよいかを書く。

## 進め方（標準・全自動・手動）

どの進め方にするかは、次の順に決める。

1. その依頼の言葉: 「全自動で」「最後まで止まらずに」→ 全自動。「相談しながら」「1件ずつ見せて」「工程ごとに確認して」→ 手動。
2. `AGENTS.local.md` に書かれた進め方。
3. サーベイに記録した進め方（`./priorwork status <survey>` の「進め方」）。
4. どれも無ければ標準。

新しいサーベイは `./priorwork new ... --mode standard|auto|manual` で進め方を記録する。途中でユーザーが変えたら `./priorwork scope <survey> --mode ...` で記録し直す（次の会話でも同じ進め方で続けられる）。

**標準**で止まる 2 か所:

- **範囲を決めたところ**: `./priorwork new` で作ったら、RQ・期間・分野・採用基準・除外基準・深さと、推測で決めた点を示して止まる。ユーザーが直したら `./priorwork scope` で直してから、検索に進む。
- **カードの記入の前**: 選別と引用の追跡が終わったら止まり、採用論文と PDF を Zotero に集めてもらう（PDF から本文で確かめたカードが増え、結果として手間が減る）。
  - Priorwork が Zotero に書き込めるとき（次にやることが `./priorwork zotero <survey> --add --dry-run`。下の「Zotero」）: その出力（コレクションに入れるものの一覧）をそのまま示し、「Zotero のコレクション『…』に入れてよいですか」と聞く。了解を得たら `./priorwork zotero <survey> --add` で入れ、「Zotero で PDF をそろえたら『続きをやって』と言ってください」と伝える。
  - そうでないとき: `./priorwork zotero <survey> --dois` の DOI の一覧をそのまま示し、「Zotero で集めたいコレクションを選び、魔法の杖に貼って、PDF もそろったら『続きをやって』と言ってください」と伝える。

  ユーザーが続きを頼んだら `./priorwork scope <survey> --go-on` で記録し、カードの記入から再開する（`./priorwork status` の次にやることに「ここで止まってユーザーを待つ」が出ている間は、この止まる場所の前にいる）。

その間（検索・選別・引用の追跡、カード・文章・検査・書き出し）は止まらずに進める。

**手動**では、範囲・検索・選別・引用の追跡・Zotero への取り込み・カード（数本ごと）・文章・検査のそれぞれの後で止まり、結果と次にすることを示して答えを待つ。採否は推薦を示して答えを待つ（スキル `priorwork-screen` の「手動のとき」）。

どの進め方でも、テーマが曖昧で検索語を決められないとき、API キーなどの設定が無くて進めないとき、⚠️ の論文で掲載版が見つからず採否が結果を大きく左右するときは止まって聞く。

## ディレクトリ

- `reports/YYYYMMDD_<slug>.md` … 作業用のレポート（管理ブロックや記入欄を含む）。エージェントが書く。やり直した版は `YYYYMMDD_v2_<slug>.md`。
- `manuscripts/<論文名>/` … ユーザーの原稿（形式は問わない: Markdown・Quarto・HTML・Word・PDF など）と結果の表・図（`priorwork-manuscript` で使う）。**読むだけで、書き換えない。** Octavo のプロジェクト（別のリポジトリ。`octavo.config.py` がある）の原稿は、写さずにその場所のまま使う（`../<プロジェクト>/papers/<名前>`。これも読むだけ）。
- `reports/YYYYMMDD_<slug>.draft.md` … 原稿の 1〜3 章を書く（または欠けを補う）サーベイで `./priorwork export --draft` が作る下書き（補完なら、どこに何を足すかの一覧。参考文献つき）。原稿が Octavo のプロジェクトにあれば、`--octavo` で Octavo のプロジェクトの受け取り場所 `literature/priorwork/<サーベイ>.md`（添え状の `.json` つき） に置く（引用が `[@key]`。原稿への取り込みは Octavo の側でする）。
- `reports/YYYYMMDD_<slug>.<名前>.md` … サーベイから派生する短い文章（講義資料・読書メモ・要点の整理など）。`./priorwork derive` が作り、用途・字数の目安と参考文献を管理ブロックに書く。エージェントは間の文章を書く（スキル `priorwork-derive`）。ほかの名前（`<名前>.lecture.md` など）で独自に作らない。
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
- **Git は作業ブランチの中だけで使う。** サーベイ名のブランチでコミット・push し、PR を作るところまでをする。マージはユーザーがする（下の「Git」）。
- **やり直しを頼まれたら、元と同じ slug で新しいサーベイを作る**（`./priorwork new ... --slug <元の slug>`）。版はエンジンが日付の直後に振る（`20261012_v2_<slug>`）ので、slug に `_v2` を付けない。同じ slug に版が複数あると slug だけでは引けないので、以後は `./priorwork new` が出した名前（`20261012_v2_<slug>` か `v2_<slug>`）で指定する。古いほうはユーザーが要らないと言ったら `./priorwork archive <古いサーベイ>` でアーカイブする（一覧から隠れるだけで、何も消えない。`--undo` で戻る）。アーカイブしたサーベイは、頼まれない限り続けない。
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
| 別のモデルとして監査する（頼まれたときだけ） | `priorwork-audit` | `check`, `card`, `audit` |
| 原稿から始める（1〜3 章の下書き・原稿への助言） | `priorwork-manuscript` | `read`, `new --manuscript --purpose …`, `card --set role=…`, `export --draft` |
| サーベイから短い文章を作る（講義資料・読書メモ・要点の整理） | `priorwork-derive` | `derive`, `check`, `export --derived` |

ユーザーが自分の原稿（書きかけでもよい）を示して、欠けているところの補完や、イントロ・先行研究・理論と仮説の下書きや、それを支える文献、足りない先行研究・引用の向き・論の組み立てへの助言を求めたら、`priorwork-manuscript` の手順で進める。原稿の形式は問わない（`./priorwork read` でテキストにする）。原稿は読むだけで、書き換えない。

サーベイを元にした講義資料・読書メモ・要点の整理など、短い文章を頼まれたら、`priorwork-derive` の手順で進める（用途・字数・構成を `./priorwork derive` で記録し、本文確認済のカードから引く）。

## 深さ（quick / full）

サーベイには深さがある（既定・未設定は full）。`./priorwork status <survey>` に表示される。依頼に「quick」「さっと」「概観」などとあれば quick、「full」「本格的に」「網羅的に」とあれば full にする。どちらとも言われなければ、テーマの広さから決め、報告でそう伝える。

| | quick（簡易） | full（本格） |
| :--- | :--- | :--- |
| 検索 | 2〜3 クエリ | サブテーマを 3〜6 に分け、それぞれ 2〜4 クエリ（通常の検索と `--bulk` を併用） |
| 件数の目安 | 候補 30 本前後、採用 15〜20 本 | 候補 **100 本以上**、採用 30 本以上。`./priorwork status` が「検索を足す」と出す間は検索を足す |
| `--limit` | 既定（10）のまま | 既定（25）のまま。減らさない |
| スナウボール | 任意 | 行う（採用が増えたら再実行） |
| カード | 要旨のみでよい | **採用論文すべて**本文を取得して本文確認済まで（要旨のみは本文が取れなかった論文だけ） |
| 文章 | 概観と比較表 | 背景・学説・論争点・研究の空白まで |

件数は目安で、固定の上限ではない。0 件だった検索は、語を減らすか言い換えて検索し直す。ルールと `./priorwork check` は深さによらず同じ。ただし full では、`./priorwork check` がスナウボール未実施と、本文を試さずに「要旨のみ」にしたカードを WARN、本文が見つからなかったカードを INFO で伝える。深さは後から `./priorwork scope SURVEY --depth full` で変えられる。

## レポートを見せる

`./priorwork export <survey>` で HTML を書き出したら、ユーザーには次の見方を伝える（SSH でつないだサーバーでもこれで見られる。Live Preview や Live Server を勧めない）。

- VS Code の Priorwork のサイドバーで、サーベイを右クリック →「レポートを書き出して見る」。
- またはエクスプローラーで `reports/<名前>.html` を右クリック →「Priorwork でレポートを見る」。

## 監査（任意。頼まれたときだけ）

監査は、ユーザーが頼んだときだけ行う。サーベイの完成の条件ではない。報告で監査を勧めたり、「監査がまだ」と書いたりしない。

- 書くときは、自分のモデル名を記録する: `./priorwork new ... --by "<モデル名>"`。別のモデルが続きを書くときは `./priorwork scope <survey> --by "<モデル名>"`。監査を頼まれたとき、誰が書いたかが分かる。
- 監査を頼まれたら、スキル `priorwork-audit` の手順で行い、最後に `./priorwork audit <survey> --by "<自分のモデル名>" --note "<確かめたこと>"` で記録する。
- 自分が書いた（`--by` に自分がある）サーベイの監査を頼まれたら、同じモデルは自分の誤読に気付きにくいので、別のモデル（例: 書いたのが Gemini なら Claude）に頼むよう伝える。

## Git（作業ブランチと PR）

ワークスペースは GitHub の非公開リポジトリに置く。エージェントは、ユーザーに聞かずに PR を作るところまで Git を操作してよい（`AGENTS.local.md` で別に決めていれば、そちらに従う）。**マージはユーザーがする。**

- **ブランチ名はサーベイ名そのもの**（`./priorwork new` が出した名前。例: `20261015_statutory_text_analysis`、やり直しなら `20261015_v2_<slug>`）。ブランチ名を自分で考えない。サーベイに結び付かない作業（`AGENTS.local.md` の直しなど）は、ブランチ名をユーザーに聞く。
- **始めるとき**: `git status` を見る。このサーベイのものでない未コミットの変更があれば、ブランチを切り替えずに報告で聞く。
  - 新しいサーベイ: main を最新にし（`git switch main` → リモートがあれば `git pull --ff-only`）、`./priorwork new` のあとに `git switch -c <サーベイ名>`。
  - 続き・監査: `git switch <サーベイ名>`（無ければ main から作る）。リモートにあれば `git pull --ff-only`。
- **コミット**: 工程の区切り（検索・選別・カード・検査・書き出し・監査）と、止まる前に。足すのはこのサーベイのファイルだけ（`git add reports/<サーベイ名>.* .priorwork/surveys/<サーベイ名>.json`）。`git add -A` は使わない。メッセージはレポートの言語で 1 行（例: 「候補の選別（採用 42 本）」）。
- **push**: 作業ブランチだけ（`git push -u origin <サーベイ名>`）。リモートが無ければ push せず、報告で伝える。
- **PR**: 書き出しまで済んだら `gh pr create --base main --head <サーベイ名> --title "<テーマ>" --body "<報告の要約>"`。PR が既にあれば作らない（push で更新される）。`gh` が無い・ログインしていなければ PR は作らず、報告で伝える。報告に PR の URL を書く。
- **しないこと**: マージ（`git merge`・`gh pr merge`）、main へのコミット・push、force push、`git reset --hard`・`git rebase`・`git clean`、ブランチの削除。`.env`（API キー）はコミットしない。

## Zotero

Zotero に書き込むのは、ユーザーが設定で許したとき（`.env` の `ZOTERO_WRITE=1`）に `./priorwork zotero <survey> --add` を使うときだけ。それ以外は、Zotero への追加はユーザーが手作業で行う。Zotero の API を直接呼んだり、Zotero のデータのファイルを書き換えたりしない。書き込みを許す設定（`.env`）は、ユーザーが自分で変える。

- **採用論文は、例外なくすべて Zotero に入れる前提**で扱う。Zotero はユーザーが論文を書くときの参考文献の管理の基盤なので、本文をオープンアクセスなどで自分で取得できた論文も、Zotero に入れる一覧から外さない。
- Zotero に入れる一覧は、**必ず `./priorwork` の出力をそのまま使う**（`./priorwork zotero <survey> --dois`、または `--add --dry-run`）。自分で選び直したり、絞ったりしない。報告では未登録の本数を伝える（`./priorwork check` も WARN で出す）。

**Priorwork が Zotero に入れるとき**（`./priorwork status <survey>` の次にやることに `zotero <survey> --add` が出ていれば、書き込みが許されていて、コレクションも結び付いている）:

- `--add` がするのは、**採用論文を結び付けたコレクションに入れることだけ**。ライブラリに同じ DOI（無ければタイトル）のアイテムがあれば、それをコレクションに足す。無ければ書誌から作る。ほかのアイテムの中身やほかのコレクションには触らず、コレクションも作らない（無ければユーザーに Zotero で作ってもらう）。
- **いつ入れるかは進め方による。** 全自動では止まらずに `--add` で入れる。標準では、カードの記入の前に止まるところで `--add --dry-run` の一覧を示して聞き、了解を得てから入れる（上の「進め方」）。手動では、そのつど `--dry-run` を示して聞く。
- 入れたら、どれを新しく作り、どれをライブラリから足したかを報告する。PDF は付かないので、Zotero で PDF を探してもらう（選んで右クリック →「Find Full Text」）よう伝える。
- **取り消しを頼まれたら**、`./priorwork zotero <survey> --undo [番号 …]` で戻す（先に `--dry-run` で示す）。戻すのは Priorwork が書いたものだけ。作ったアイテムはごみ箱に入れ、その後ユーザーが手を入れたものは残す。
- 書き込みが許されていないのに Zotero に入れたいと言われたら、下の手作業の方法を示し、設定のページ（「Priorwork が採用論文をサーベイのコレクションに入れてよい」）で許せることも伝える。

**手作業で入れるとき**:

- **採用論文を Zotero に集めたい**と言われたら、`./priorwork zotero <survey> --dois` の DOI の一覧を示し、「Zotero で集めたいコレクションを選び、魔法の杖（識別子でアイテムを追加）に貼る」と伝える。サイドバーの次にやることの「Zotero に追加」でも DOI をまとめてコピーできる。
- **Zotero のアプリでの操作は、アプリが zotero.org と同期してから届く。** ユーザーが「入れた」「PDF がある」と言ったのに `./priorwork zotero` や `fulltext` に出ないときは、Zotero の同期（緑の矢印）を待ってもらってから実行し直す（`./priorwork` がそう表示する）。PDF はファイルの同期も要る。待てないときは、ユーザーに PDF を `manuscripts/` などに置いてもらい `fulltext --pdf` で読む。
- **ユーザーが Zotero のコレクションを教えてくれたら**、`./priorwork zotero <survey> --collection "<名前>"` で結び付ける（名前が分からなければ `./priorwork zotero --collections` で一覧）。Zotero のコレクションは入れ子にできる。同じ名前が別の親の下にあれば、パスで指定する（`"親 / 子"`）。以後、
  - 「Zotero にあるか」はそのコレクションに入っているかで判定される（その下のコレクションに入っていてもよい）。
  - `./priorwork zotero <survey> --import` で、コレクションの論文を候補に登録できる。これはユーザーが自分で選んで入れた論文なので、範囲から明らかに外れない限り採用する。
  - 本文（`./priorwork fulltext`）はそのコレクションの PDF を優先して読む。カードの記入も、コレクションに PDF がある論文から始める。
- **原稿が Octavo のプロジェクトにあるとき**、Octavo はその設定（`zotero_collection`）の Zotero のコレクションから参考文献の `.bib` を取る。サーベイも同じコレクションに結び付ける（`./priorwork new --manuscript` が自動で結び付ける。違っていれば `./priorwork check` が知らせる）。採用論文をそのコレクションに入れれば、Octavo の参考文献にもなる。Octavo はその下のコレクションの文献も取るので、**1 つの Octavo のプロジェクトに複数のサーベイがあるときは、サーベイごとに Octavo のコレクションの下のコレクション**（`"<Octavo のコレクション> / <サーベイ>"`）を使う（同じコレクションに混ぜると、`--import` で互いの論文が候補に入る）。コレクションはユーザーが Zotero で作る。**Octavo のプロジェクトに書くのは `./priorwork export --octavo` が受け取り場所（`literature/priorwork/`）に置くものだけ。** 設定・`.bib`・原稿は書き換えない。原稿への取り込みは、Octavo のプロジェクトのエージェントに頼むようユーザーに伝える。
- **Octavo からの依頼。** Octavo は依頼を `.priorwork/requests/` に置くことがある（`./priorwork status` に件数が出る）。「Octavo からの依頼を進めて」と頼まれたら、`./priorwork requests` で一覧を見て、`./priorwork requests <id>` で中身を読み、依頼の文に従って進める（原稿からなら `priorwork-manuscript`）。済んだら `./priorwork requests <id> --done --survey <survey>` で記録する。進められない（範囲の外・原稿が見つからないなど）なら、`--decline --note "<理由>"` で記録してユーザーに伝える。依頼のファイルは自分で書き換えない。
- **サーベイと Octavo のプロジェクトは多対多。** テーマのサーベイを論文（Octavo のプロジェクト）で使うと頼まれたら、`./priorwork scope <survey> --octavo <プロジェクトのパス>` で結び付け（いくつでも）、`./priorwork export <survey> --octavo <プロジェクト>` でそのプロジェクトの `.bib` のキーを使って書き出す（そのプロジェクトの `literature/priorwork/<サーベイ>.md`。原稿の下書きのサーベイなら下書き、それ以外は学説・手法・論争・空白の節）。Octavo のプロジェクトの Zotero のコレクション（並びでもよい）にサーベイのコレクションが入っていなければ `./priorwork check` が知らせるので、Octavo 側に足すようユーザーに伝える。

## ルール

1. **対象は国際査読誌論文。SSCI 収録誌を優先する**
   - WP（NBER、IZA DP など）、プレプリント（SSRN、arXiv など）、紀要、学会報告は、ユーザーの指示がない限り採用しない。
   - 古典的な書籍は、背景の説明で触れてよいが採用論文には入れない。
2. **でっち上げない・取り違えない**
   - 文章中で論文に言及するときは、その論文が `./priorwork` に登録されていること。記憶だけで著者・年・DOI を書かない。
   - カードには要旨・本文に書かれていることだけを書き、確認レベル（未確認 / 要旨のみ / 本文確認済）を必ず更新する。**「本文確認済」は、その論文の本文を `./priorwork fulltext` で取得して読んだときだけ**にする。要旨から書いたものは「要旨のみ」。
   - 本文確認済のカードでは、数値・手法・主な結果にページ（`（p. 12）`）を添える。ページの分からない本文なら「（ページ未確認）」と書く。`./priorwork check` は、本文に無い数値・論文に無いページを WARN にする。
   - 年は掲載号の年で引く（オンラインで先に公開された年ではない）。`./priorwork add` は巻のある論文の年を掲載号の年に直し、`./priorwork check` は食い違う採用論文を `fix --year` の形で知らせる。
   - カードは**レポートの言語**で書く（日本語のレポートなら日本語。用語の原語は括弧内に残す）。要旨の英文をそのまま写さない。
   - 文章で先行研究を引くときは、カードの「主な結果」と**結論の向き**（促す／促さない、増える／減る）が合っているか確かめる。
   - **先行研究の知見と、本研究（ユーザー）の枠組み・仮説を混ぜない。** ユーザーが示した分類や仮説は「本研究の仮説と示唆」の節にだけ書き、先行研究の合意のように書かない。
   - 採用論文の本数などの件数を、文章に手で書かない（付録の記録に自動で出る。食い違うと `check` が WARN にする）。
3. **⚠️ を無視しない**
   - 「DOI が別タイトルを指している」「DOI は WP / プレプリント版」「書評・コメントの可能性」などの警告がある論文は、`priorwork-screen` の手順で掲載版に置き換える（`fix --id`）か、置き換えられなければ保留にして報告で伝える。警告を `fix --confirm` で解除するのは、書誌が正しいことを確かめたときだけ。
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
./priorwork new "<テーマ>" --slug <slug> --by "<モデル名>" [--mode standard|auto|manual] [--depth quick|full] [--manuscript PATH [--purpose draft|advice]] [--question ... --years ... --fields ... --inclusion ... --exclusion ...]
./priorwork scope SURVEY [--question ...] [--mode standard|auto|manual] [--go-on] [--depth quick|full] [--search-field social|all] [--manuscript PATH] [--by "<モデル名>"]
./priorwork archive SURVEY [--undo]  # 一覧から隠す（ファイルは残る）。アーカイブの一覧は status --archived
./priorwork search "<English query>" [--into SURVEY] [--bulk] [--sort citations|relevance|recent|cpy] [--year 2010-2024] [--ssci-only] [--field social|all] [--limit N]
./priorwork list SURVEY [--status candidate maybe included excluded] [--abstract]
./priorwork include SURVEY N... --reason "..."   ./priorwork exclude SURVEY N... --reason "..."   ./priorwork maybe SURVEY N... --reason "..."   ./priorwork reset SURVEY N...
./priorwork add SURVEY <DOI>... [--candidate]      ./priorwork add SURVEY --cited   # 原稿が引いている論文（.bib の DOI）を登録
./priorwork fix SURVEY N [--id <掲載版の DOI>] [--authors "A; B"] [--year Y] [--confirm "<確かめたこと>"]
./priorwork snowball SURVEY [--direction both|references|citations] [--limit N] [--min-links N]
./priorwork fulltext SURVEY N [--pdf PATH]
./priorwork card SURVEY N [--set KEY=VALUE ...]
./priorwork render SURVEY
./priorwork check SURVEY [--offline]
./priorwork audit SURVEY [--by "<モデル名>" --note "..."]   # 頼まれた監査を記録（--by なしで記録を見る）
./priorwork export SURVEY [--format html|docx|md] [--with-abstracts]   # 読むための版を書き出す
./priorwork export SURVEY --draft [--format md|docx|html]             # 原稿の 1〜3 章の下書き（--purpose draft のサーベイ）
./priorwork derive SURVEY [NAME --purpose "..." --length N --structure "a; b; c" [--count-citations]]   # 派生文書を作る（NAME を省くと一覧）
./priorwork export SURVEY --derived NAME [--format html|docx|md]      # 派生文書を読むための版に
./priorwork export SURVEY --octavo [PROJECT] [--bib PATH]             # Octavo のプロジェクト用に（引用を [@key] に。下書きか、まとめの節）
./priorwork scope SURVEY --octavo PATH [--octavo PATH ...]           # このサーベイを使う Octavo のプロジェクトを結び付ける（--unlink-octavo で外す）
./priorwork requests [ID] [--done --survey SURVEY | --decline --note "..."]   # Octavo からの依頼
./priorwork read PATH [--out FILE]   # 原稿（.md・.qmd・.html・.docx・.pdf など、フォルダも可）をテキストにする
./priorwork zotero [SURVEY] [--collections] [--collection NAME] [--import] [--dois]   # --dois は Zotero の連携が無くても使える
./priorwork zotero SURVEY --add [--dry-run]      # 採用論文を結び付けたコレクションに入れる（ZOTERO_WRITE=1 のときだけ。--undo [番号 …] で戻す）
./priorwork get <DOI>      ./priorwork citations <DOI> [--sort cited]      ./priorwork references <DOI> [--sort cited]      ./priorwork journal "<誌名>"
./priorwork doctor [--online]        # 設定の診断（動作がおかしいとき）
./priorwork sync                     # AGENTS.md・スキルをエンジンの版に更新
```

`SURVEY` は `20260917_minimum_wage_employment` のようなファイル名（拡張子なし）か、slug（`minimum_wage_employment`）で指定する。やり直した版があるときは `v2_minimum_wage_employment` のように版を付けるか、ファイル名で指定する。
