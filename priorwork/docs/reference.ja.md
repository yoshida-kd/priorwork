# Priorwork リファレンス

> これはリファレンスの原稿。読むなら **<https://yoshida-kd.github.io/priorwork/ja/reference/>** で。 <!-- pages:skip -->

このページは、Priorwork のワークスペースで作業する **AI エージェント**と、細かいところまで知りたい人のためのものだ。VS Code から Priorwork を使う人は、[手引き](https://yoshida-kd.github.io/priorwork/ja/guide/)を読めば足りる。

同じ文章が Priorwork に同梱されていて、入っている版に合ったものが読める:

```bash
./priorwork docs                     # 節の一覧
./priorwork docs 5.2                 # 番号で1つの節
./priorwork docs zotero              # 見出しの言葉で
./priorwork docs --search snowball   # その言葉が出てくる節すべて
./priorwork docs --all               # 全部
```

`--lang en` で英語になる（既定は表示の言語）。**サーベイの進め方**はワークスペースの `AGENTS.md` とスキルにあり、このページは各コマンドが何をするかを書いたものだ。

---

## 1. 決まりと置き場所

### 1.1 決まり

- 採否と範囲には必ず理由を残す。利用者の採否や修正は覆さない。
- サーベイの進め方（標準・全自動・手動）が止まると決めた所で止まり、その間は自分で決める。
- 文章で触れる論文はすべて登録する。著者・年・DOI を記憶から書かない。
- カードには要旨か本文に書かれていることだけを書き、確認レベルを更新する。
- 利用者に論文を示すときは「著者 (年)」で、番号では示さない。
- 終わったと言う前に `./priorwork check` を実行する。
- Zotero への書き込みは `./priorwork zotero --add` だけで、許されているとき（`ZOTERO_WRITE=1`）だけだ。
- Git では、サーベイ名のブランチで作業し、コミット・push して PR を作る。マージはしない。
- Priorwork 自体のファイル（`.venv` の中）、`AGENTS.md`、スキルは開かず、直さない。そのワークスペースだけの指示は `AGENTS.local.md` にある。

### 1.2 ワークスペースの中身

```text
my-surveys/
├── reports/                 # レポート（作業用の .md、書き出した .html、原稿の下書き .draft.md など）
├── manuscripts/             # 起点にする原稿とその図表（論文ごとのフォルダ。読むだけ）
├── AGENTS.md, CLAUDE.md     # エージェント向けの指示（自動で更新。直さない）
├── AGENTS.local.md          # このワークスペースだけの指示（自由に書く）
├── .agent/skills/           # 工程ごとのスキル（.claude/skills からも見える）
├── priorwork                # ./priorwork（エージェントが実行するもの）
├── requirements.txt         # エンジンの版（priorwork==X.Y.Z）
├── .env                     # 設定（Git に載せない）
└── .priorwork/
    ├── config.json          # ワークスペースの言語
    ├── surveys/             # サーベイごとの状態（Git に載せる）
    ├── requests/            # Octavo からの依頼
    ├── cache/               # 本文、Zotero の索引（Git に載せない）
    └── data/                # SSCI リスト（Git に載せない）
```

| ファイル | 中身 | 書き換え |
| :--- | :--- | :--- |
| `reports/YYYYMMDD_<slug>.md` | 作業用のレポート（やり直したサーベイは `YYYYMMDD_v2_<slug>.md`） | 文章とカードの欄は手かエージェントで書く。`<!-- BEGIN priorwork:… -->` から `<!-- END priorwork:… -->` までは作り直される |
| `.priorwork/surveys/YYYYMMDD_<slug>.json` | 候補、採否と理由（履歴付き）、検索の記録、範囲、深さ、進め方、Zotero のコレクション | `./priorwork` を通してだけ |

以下のコマンドの `SURVEY` は、拡張子を除いたファイル名か slug（やり直したサーベイは版付きで `v2_<slug>`）。

### 1.3 状態を調べる

```bash
./priorwork status                   # すべてのサーベイと、ほかのブランチのサーベイ
./priorwork status SURVEY            # 進み具合と次の工程
./priorwork list SURVEY --status candidate maybe
./priorwork doctor --online          # 設定と接続
```

たいていのコマンドは `--json` で JSON を出す。

---

## 2. サーベイ

### 2.1 作る・範囲を決める

```bash
./priorwork new "<topic>" --slug <slug> --by "<model>" --mode standard --depth full --question "..."
./priorwork scope SURVEY --question "..." --years 2000-2025 --fields "..." --inclusion "..." --exclusion "..."
./priorwork scope SURVEY --go-on     # 利用者が範囲を確かめた: 先へ進む
```

- `--slug` は英語のファイル名（`minimum_wage_employment`）。レポートは `reports/YYYYMMDD_<slug>.md` になる。同じ slug の2つ目は `YYYYMMDD_v2_<slug>` と番号が付く。
- `--by` は書いたモデルを記録する（監査は同じモデルを断る）。
- `--search-field social|all`: 社会科学の外の検索結果を除くか（既定は `social`）。

### 2.2 進め方と深さ

| 進め方 | 止まる所 |
| :--- | :--- |
| `standard`（既定） | 範囲を決めたところと、カードを書く前（利用者が Zotero に論文を集めるため） |
| `auto` | 止まらない |
| `manual` | 工程ごと。採否も、待つ前提の提案になる |

| | `quick` | `full` |
| :--- | :--- | :--- |
| 検索 | 2〜3 本、各 10 件 | 下位テーマごとに 2〜4 本、各 25 件。候補 100 件以上が目安 |
| 引用をたどる | 任意 | 行う |
| カード | 要旨でよい | 採用論文はすべて本文で確かめる（本文が見つからないときだけ要旨） |
| 文章 | 概観と比較表 | 背景、理論、論争、空白 |

進め方はサーベイに記録される。`AGENTS.local.md` の進め方（「進め方: 全自動」）は新しいサーベイに効く。

### 2.3 やり直しとアーカイブ

```bash
./priorwork archive SURVEY           # 一覧から隠す。ファイルは残る
./priorwork archive SURVEY --undo
./priorwork status --archived
```

---

## 3. 文献を探す

### 3.1 検索

```bash
./priorwork search "<English query>" --into SURVEY
./priorwork search "minimum wage + employment -teen" --into SURVEY --bulk --sort citations
./priorwork search "<query>" --into SURVEY --year 2010-2024 --journal "American Economic Review" --ssci-only
```

- 既定は Semantic Scholar の関連度検索。`--bulk`: `+`（かつ）、`|`（または）、`-`（除く）、`"句"`、被引用の多い順（`AND`・`OR`・`NOT` はこれに直す）。
- `--sort citations|relevance|recent|cpy`、`--year`、`--journal`（正式名か ISSN。繰り返せる）、`--ssci-only`、`--field social|all`、`--limit N`（full のサーベイに入れるときは既定 25、ほかは 10）、`--include-preprints`（本・ワーキングペーパー・プレプリント・掲載先不明は既定で除く）。
- DOI・掲載誌・ISSN は OpenAlex で照合する。ワーキングペーパーと掲載版が両方見つかれば、掲載版だけを残す。
- `--journal` を付けると、Semantic Scholar（`venue` で絞る）**と** OpenAlex（誌名か ISSN から引いた誌の source ID で絞る）の両方で探す。Semantic Scholar は誌名（venue）を持たない論文が多く、venue での絞り込みから黙って落ちる。OpenAlex の結果のうち Semantic Scholar に無かったものを足し（DOI で重複を除く。`--bulk` なら被引用数で並べ直し、それ以外は Semantic Scholar の結果の後ろに足す）、足した件数をお知らせに出す。どちらで見つかったかは各レコードの `found_in` に、検索ログには `openalex`（`used` / `failed`）と `openalex_added` が残る。OpenAlex が失敗したら、お知らせを出して Semantic Scholar の結果だけを返す。`--journal` が無ければ OpenAlex では検索しない（キーワード検索の精度が低い）。
- 雑誌の論文なのに DOI がプレプリント・WP のもの（OSF・SocArXiv・SSRN・arXiv・NBER など）か OpenAlex の知らないものは、題名で OpenAlex を引く（誌の source ID か ISSN も添える）。雑誌版が一致すれば（`same_title`、年の差 ±2 以内）その DOI と書誌情報に替え、元の DOI を `preprint_doi` に残し、注記（ℹ️、`notes`）を付ける。一致しなければ警告のまま。1 回の検索で 10 件まで引く。

### 3.2 引用をたどる

```bash
./priorwork snowball SURVEY --direction both --min-links 2
```

採用論文の参考文献と被引用を OpenAlex から集め、つながる採用論文の多い順に並べる。採用論文が3本以上なら、既定では2本以上とつながるものだけを取る。

### 3.3 1本の論文

```bash
./priorwork add SURVEY 10.1257/aer.91.5.1369             # 登録して採用
./priorwork add SURVEY 10.1257/aer.91.5.1369 --candidate # 候補として登録
./priorwork get 10.1257/aer.91.5.1369
./priorwork citations 10.1257/aer.91.5.1369 --sort cited
./priorwork references 10.1257/aer.91.5.1369
./priorwork journal "Journal of Public Administration Research and Theory"
./priorwork fix SURVEY 12 --id 10.1093/jopart/xyz --authors "A; B" --year 2019
./priorwork fix SURVEY 12 --confirm "checked the publisher's page"
```

`fix` は、ワーキングペーパーの DOI を掲載版のものに替え、著者・年・題を直し、確かめた警告を（何を確かめたかとともに）解除する。

---

## 4. 選別

```bash
./priorwork include SURVEY 2 5 7 --reason "..."
./priorwork exclude SURVEY 3 --reason "theory only"
./priorwork maybe SURVEY 9 --reason "..."
./priorwork reset SURVEY 9
```

警告のある論文は、採用する前に確かめる:

| 警告 | 意味 | すること |
| :--- | :--- | :--- |
| DOI が別のタイトルを指している | Semantic Scholar の DOI が別の論文のもの | 正しい DOI を探し `fix --id` |
| DOI がワーキングペーパー・プレプリント版 | 掲載誌があるのに DOI が SSRN などの版 | 掲載版の DOI に `fix --id` |
| OpenAlex が DOI を知らない／DOI 無し／未確認 | 誤り・欠け・確かめられない | 確かめて `fix` |
| 書評・コメントかもしれない | 「…, by 著者」のような題、1ページだけ | たいてい除外 |

🟡（推定）の雑誌を「SSCI 収録」と言わない。リストで確かめたのは ✅ だけだ。

---

## 5. 論文カード

### 5.1 欄

```
### #1 Acemoglu et al. (2001): The Colonial Origins of Comparative Development
- Source: American Economic Review 91(5) | ✅ SSCI | cited by 8534 | DOI   ← automatic
- Evidence: unchecked / abstract only / full text checked
- RQ: Do institutions cause the differences in income between countries?
- X (explanatory variable / treatment): the quality of today's institutions
- Y (outcome): GDP per capita in 1995
- Data / sample: 64 former colonies
- Identification: 2SLS, with settler mortality as the instrument
- Main findings: better institutions raise income substantially
- Limitations: measurement error in the mortality data
- Notes:
```

```bash
./priorwork card SURVEY 3
./priorwork card SURVEY 3 --set evidence=fulltext rq="..." findings="..."
```

- キー: `evidence`（`unchecked`・`abstract`・`fulltext`）、`rq`、`x`、`y`、`data`、`method`、`findings`、`limits`、`memo`、原稿から始めたサーベイでは `role`（原稿での役割）。値の中の改行は、欄の下の箇条書きになる。
- 欄の**1行目**は比較マトリクスに入るので、短い1文にする。
- 要旨か本文に書かれていることだけ。無ければ「記載なし」。レポートの言語で書き、用語は原語を括弧で添える。
- `fulltext` では、データ・識別・主な結果にページ（`(p. 12)`）を付ける。本文に改ページが無いときは「(ページ未確認)」。
- 採用を取り消した論文のカードは状態ファイルに残り、採用し直すと戻る。

### 5.2 本文

```bash
./priorwork fulltext SURVEY 3
./priorwork fulltext SURVEY 3 --pdf path/to/paper.pdf
```

探す順: ローカルの Zotero の PDF（DOI で照合）、Zotero のウェブ API で見つかる PDF（WebDAV か Zotero のファイル同期。サーベイのコレクションが先）、Zotero が索引した本文（ページ無し）、オープンアクセスの PDF（OpenAlex の知るすべての所在と、ランディングページの `citation_pdf_url`）。残すのは取り出した文章だけで、`.priorwork/cache/fulltext/` に置く。取れなかったことも記録する。

---

## 6. 書く・検査する・書き出す

### 6.1 レポート

まとめが先に来る: 背景（1）、理論の系譜・手法・合意と論争・空白（2〜5。主張ごとに採用論文を引く）、利用者の研究への仮説と含意（6。先行研究とは分ける）。そのあとに比較マトリクス・カード・参考文献（自動）。Mermaid の図（```` ```mermaid ````）は HTML で描かれる。

```bash
./priorwork render SURVEY     # 管理ブロックを作り直す
```

### 6.2 検査

```bash
./priorwork check SURVEY
./priorwork check SURVEY --offline
```

| 検査 | レベル |
| :--- | :--- |
| 文章とカードの「著者 (年)」が登録済みの論文に対応しているか | ERROR（未登録）/ WARN（未採用） |
| 2001a / 2001b が参考文献と合っているか | WARN |
| 文章中の DOI が登録済みか | ERROR |
| 採用論文の ⚠️、OpenAlex での DOI とタイトルの一致 | ERROR |
| カードの確認レベル、未記入の欄 | WARN |
| `fulltext` のカード: 本文に無い数値、論文に無いページ、ページ無し、本文未取得 | WARN |
| レポートの言語で書かれていないカード | WARN |
| 論文を引いていないまとめの節、食い違う採用数 | WARN |
| Zotero に無い採用論文 | WARN |
| レポートが状態ファイルと一致しているか | WARN |
| 未選別の候補、SSCI 以外の採用論文、組織名・図表番号とみなした引用 | INFO |

引用でないものは、レポートに書いて外せる:

```markdown
<!-- priorwork:ignore-citation Smith (2015) -->
```

### 6.3 別のモデルによる監査

```bash
./priorwork audit SURVEY --by "<model>" --note "..."
./priorwork audit SURVEY
```

利用者に頼まれたときだけ行う。すべてのカードを本文と比べ、引用の向き、先行研究と称した仮説、除外した論文を確かめ、直して、監査を記録する。サーベイを書いたモデルは断られる。

### 6.4 書き出し

```bash
./priorwork export SURVEY                       # reports/<name>.html
./priorwork export SURVEY --format docx         # または md
./priorwork export SURVEY --with-abstracts
./priorwork derive SURVEY handout --purpose "lecture handout" --length 2000 --structure "a; b; c"
./priorwork export SURVEY --derived handout
```

カードが未確認か未記入、または検査に ERROR があるあいだは「下書き」と付く。`derive` はサーベイから作る短い文章（`reports/<name>.<文章名>.md`）を記録する。引くのは本文で確かめた採用論文だけで、分量には括弧の中の引用を数えない（`--count-citations` で数える）。

---

## 7. 原稿から始める

```bash
./priorwork read manuscripts/make_or_buy
./priorwork new "<topic>" --slug <slug> --manuscript manuscripts/make_or_buy --purpose complete
./priorwork add SURVEY --cited
./priorwork export SURVEY --draft
```

- `read` は Markdown・Quarto（.qmd とその HTML）・LaTeX・Word・PDF を文章にし、利用者の印（`[cite]`・`[@?]`・`TODO(priorwork): …`）を並べる。
- `--purpose complete`（既定）: 節ごとに足りないものを、前後の文を引いた「**場所**」と「**理由**」付きの補いとして。`draft`: 序論・先行研究・理論と仮説の下書きと、先行研究の要る主張（ID 付き、食い違う知見も）、下書きに入れない HARKing の節。`advice`: 引用ごとの向きの確認、足りない先行研究、論の組み立て。
- カードには「**原稿での役割**」（`role`）が付く。原稿そのものは書き換えない。
- `add --cited` は、原稿が引いている論文（その `.bib` の DOI）を登録する。

---

## 8. Zotero

```bash
./priorwork zotero                          # 結び付きの確認
./priorwork zotero --collections            # コレクションの木
./priorwork zotero SURVEY --collection "Parent / Child"   # 結び付ける（"" で外す）
./priorwork zotero SURVEY --import          # コレクションの論文を候補に登録
./priorwork zotero SURVEY --dois            # Zotero に無い採用論文の DOI（魔法の杖用）
./priorwork zotero SURVEY --add --dry-run   # --add が入れるもの
./priorwork zotero SURVEY --add
./priorwork zotero SURVEY --undo
```

- `.env` の設定: `ZOTERO_API_KEY`、`ZOTERO_USER_ID`、`ZOTERO_DATA_DIR`（ローカルの Zotero）、`ZOTERO_WEBDAV_URL` / `_USER` / `_PASSWORD`（WebDAV のファイル同期）、`ZOTERO_WRITE`。
- 既定では読むだけだ。`--add` には `ZOTERO_WRITE=1` と書き込める鍵が要る。ライブラリにある項目（同じ DOI か題）はコレクションに加え、無ければ新しく作る。項目を変えたり消したりせず、ほかのコレクションに触れず、コレクションも作らない。`--undo` は Priorwork が書いたものだけを戻す。標準の進め方ではカードの前の停止で一覧を示し、利用者が同意してから入れる。全自動では止まらずに入れ、手動では毎回尋ねる。
- 結び付けると、「Zotero にある」はそのコレクション（とその下）にあることで、本文もまずその PDF から取る。

---

## 9. Octavo

```bash
./priorwork scope SURVEY --octavo ../make_or_buy
./priorwork export SURVEY --octavo
./priorwork export SURVEY --octavo ../make_or_buy --bib literature/literature.bib
./priorwork requests
./priorwork requests <id> --done --survey SURVEY
./priorwork requests <id> --decline --note "..."
```

- Octavo の原稿はそのプロジェクトに置いたまま、その場で読む。1つのサーベイが複数のプロジェクトに、1つのプロジェクトが複数のサーベイに使える。
- `export --octavo` はプロジェクトの `literature/priorwork/` に書く: `<survey>.md`（プロジェクトの `.bib` のキーで `[@key]`）、`<survey>.json`（目録。`draft`・`synthesis`・`complete`）、`<survey>.cards.json`（カード）。プロジェクトのほかの所には書かない。
- `.bib` に無い論文は `[@PRIORWORK:<DOI>]` と書く。利用者が Zotero に入れ、Octavo のプロジェクトで `octavo bib pull` と `octavo priorwork resolve` を実行する。
- サーベイを Octavo のプロジェクトのコレクション（`zotero_collection`）の下のコレクションに結び付ければ、`octavo bib pull` がすべてのサーベイの採用論文を集める。
- Octavo からの依頼は `.priorwork/requests/<id>.json` に届く。結果を記録する。

---

## 10. 設定とエンジン

```bash
./priorwork settings                         # 設定（キーの値は出さない）
./priorwork settings --stdin                 # 標準入力の KEY=VALUE の行で設定する
./priorwork settings --import-ssci SSCI.csv  # Clarivate の Master Journal List の SSCI リスト
./priorwork doctor --online
./priorwork sync                             # AGENTS.md とスキルをエンジンの版に（--diff、--force）
./priorwork upgrade                          # 最新のエンジンにして sync（--to X.Y.Z）
```

| 設定 | 用途 |
| :--- | :--- |
| `SEMANTIC_SCHOLAR_API_KEY` | 推奨。無いと検索が HTTP 429 になりやすい |
| `OPENALEX_API_KEY`、`OPENALEX_MAILTO` | 任意 |
| `ZOTERO_*` | [8](#8-zotero) |

SSCI の表示: ✅ リストで確認、🟡 約 100 誌の組み込みのリストから推定（要確認）、🔍 不明、⚪ リストに無い。📕 本・❌ ワーキングペーパーとプレプリント・❓ 掲載先不明は、既定で検索結果から除く。

---

## 11. コマンド

```bash
./priorwork init [DIR] [--lang en|ja]
./priorwork settings [--stdin] [--import-ssci CSV]
./priorwork doctor [--online]
./priorwork sync [--force|--diff]
./priorwork upgrade [--to X.Y.Z]
./priorwork status [SURVEY] [--archived]
./priorwork new "<topic>" --slug <slug> --by "<model>" [--mode standard|auto|manual] [--depth quick|full] [--manuscript PATH [--purpose complete|draft|advice]] [--question ... --years ... --fields ... --inclusion ... --exclusion ...]
./priorwork scope SURVEY [--question ...] [--mode ...] [--go-on] [--depth ...] [--search-field social|all] [--manuscript PATH] [--octavo PATH] [--by "<model>"]
./priorwork archive SURVEY [--undo]
./priorwork read PATH [--out FILE]
./priorwork requests [ID] [--done --survey SURVEY | --decline --note "..."]
./priorwork search "<query>" [--into SURVEY] [--bulk] [--sort citations|relevance|recent|cpy] [--year 2010-2024] [--journal "<name>" ...] [--ssci-only] [--field social|all] [--limit N]
./priorwork snowball SURVEY [--direction both|references|citations] [--limit N] [--min-links N]
./priorwork list SURVEY [--status candidate maybe included excluded] [--abstract]
./priorwork include|exclude|maybe SURVEY N... --reason "..."
./priorwork reset SURVEY N...
./priorwork add SURVEY <DOI>... [--candidate] | --cited
./priorwork fix SURVEY N [--id <DOI>] [--authors "A; B"] [--year Y] [--confirm "..."]
./priorwork card SURVEY N [--set KEY=VALUE ...]
./priorwork fulltext SURVEY N [--pdf PATH]
./priorwork render SURVEY
./priorwork check SURVEY [--offline]
./priorwork audit SURVEY [--by "<model>" --note "..."]
./priorwork export SURVEY [--format html|docx|md] [--with-abstracts] [--draft] [--derived NAME] [--octavo [PROJECT] [--bib PATH]]
./priorwork derive SURVEY [NAME --purpose "..." --length N --structure "a; b; c" [--count-citations]]
./priorwork zotero [SURVEY] [--collections] [--collection NAME] [--import] [--dois] [--add [--dry-run]] [--undo]
./priorwork get <DOI>
./priorwork citations <DOI> [--sort cited]
./priorwork references <DOI> [--sort cited]
./priorwork journal "<journal or ISSN>"
./priorwork docs [SECTION] [--search WORD] [--all] [--lang en|ja]
```

---

## 12. うまくいかないとき

- **HTTP 429（レート制限）**: `SEMANTIC_SCHOLAR_API_KEY` を設定する。Priorwork は5回まで待って試し直す。
- **論文が見つからない**: 国内の学術誌（J-STAGE など）の論文は、Semantic Scholar にも OpenAlex にも無いことが多く、対象外だ。
- **本文が取れない**: 出版社は自動のダウンロードを断る。Zotero に PDF を添付するよう利用者に頼むか、`fulltext --pdf` を使う。
- **スキルが古いようだ**: `./priorwork status` がそう言う。`./priorwork sync`。
- **「ブランチ … にあります」**: サーベイは別のブランチにある。`git switch` で移る。
- **何がおかしいかわからない**: `./priorwork doctor --online`。
