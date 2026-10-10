# Priorwork

**先行研究サーベイを AI エージェントに任せて、確かめる — ターミナルは不要**

[English](README.md) · **[手引き](https://yoshida-kd.github.io/priorwork/ja/guide/)** · [ウェブページ](https://yoshida-kd.github.io/priorwork/ja/)

Priorwork（prior work ＝ 先行研究）は、社会科学（経済学・社会学・政治学・行政学・経営学・心理学など）のテーマ別文献サーベイを、AI エージェント（Claude Code・Antigravity など）に任せて作るためのツールです。

**頼むのは普通の言葉で、確かめるのはサイドバーで。** エージェントに「〇〇について先行研究を full でまとめて」と頼むと（VS Code の **新しいサーベイ → エージェントに任せる** でも）、範囲の設定・検索・選別・引用の追跡・論文カードの記入・文章・検査・書き出しまで、止まらずに進めます。あなたはレポートを読み、Priorwork のサイドバーで覆したり直したりします。ターミナルも、覚えるコマンドやスキル名もありません。拡張機能が自分で AI のサービスを呼ぶことはないので、いま使っているエージェントのほかに費用はかかりません。

- **判断には必ず理由が残る。** エージェントは採否ごとに理由を記録し、決めた範囲をレポートに書き込みます。論文ごとのページでキー 1 つで覆せ、エージェントはあなたの判断に従い、覆しません。一つずつ自分で決めたいときは「相談しながら進めて」と頼みます
- **覚えるのはリポジトリ。** 論文の候補・採否・検索履歴は `.priorwork/surveys/` の JSON に残るので、会話をまたいで続きから作業できます
- **確かめられるカード。** 採用論文ごとの論文カード（RQ・X・Y・データ・識別戦略・結果・限界）は、要旨・本文に書かれていることだけで書かれ、何で確かめたか（確認レベル）が残ります
- **でっち上げを機械的に検出する。** 本文中の「著者 (年)」が登録済みの論文に対応しているか、DOI が別の論文を指していないかを `priorwork check` で検査します
- **人が読むのは `reports/` のレポートだけ。** `priorwork export` が読むための版（HTML）を作ります。状態ファイルやキャッシュは `.priorwork/` に隠れています

```
① 範囲を決める → ② 検索 → ③ 選別 → ④ 引用をたどる → ⑤ カードを記入 → ⑥ 文章 → ⑦ 検査と書き出し
```

## 構成

| | エンジン（`priorwork` コマンド・VS Code 拡張機能） | ワークスペース |
| :--- | :--- | :--- |
| 持つもの | コード、AGENTS.md・スキルの原本 | サーベイのレポート、状態、`.env` |
| 入手 | PyPI（`pip install priorwork`）・VS Code Marketplace（Priorwork） | 自分で作る（GitHub の非公開リポジトリ） |
| 更新 | 版を切ってリリース | `./priorwork upgrade` |

ワークスペースは `requirements.txt` でエンジンの版を固定しているので、意図しない更新は起きません。新しい版に上げるときは `./priorwork upgrade` の1コマンドです（コードのコピーを持たないので、マージの衝突は起きません）。

---

## セットアップ

### VS Code から始める

1. VS Code の拡張機能で **Priorwork** を入れます。始めるのにほかに入れるものはありません。Python 3.10 以上があればそれを使い、無ければ [uv](https://docs.astral.sh/uv/) を入れて Python を取ってきます（ホームフォルダーに入り、管理者権限は要りません）。VS Code で動く AI エージェント（Claude Code・Antigravity など）と、ワークスペースを GitHub に置くための **git** を用意してください
2. アクティビティバーの Priorwork から **ワークスペースを作る** を選び、空のフォルダとレポートの言語（日本語・英語）を選びます。拡張機能がそのフォルダに `.venv` を作り、PyPI から `priorwork` を入れてワークスペースを用意します
3. サイドバーの歯車の **設定** を開き、Semantic Scholar の無料 API キー（推奨）と、あれば Zotero・SSCI リストを設定します。**保存して接続を確かめる** で動くかを確かめられます
4. サイドバーに出る行から、**GitHub の非公開リポジトリ**として公開します。エージェントは、頼まれない限り Git を操作しません（コミットや push は頼んだときだけ）
5. **新しいサーベイ** → **エージェントに任せる** でテーマを入れ、コピーされた依頼文をエージェントのチャットに貼ります（チャットで直接頼んでも同じです）。エージェントが書き出しまで進めます
6. レポートを読みます（**レポートを書き出して見る**、または `reports/*.html` を右クリック → **Priorwork でレポートを見る**。SSH でつないだサーバーでも見られます）。論文ごとのページで採否とカードを確かめ、違うところを直します
7. 続きは、サーベイの **エージェントに頼む…** か、チャットで（「もっと検索して」「続けて」）

拡張機能でできること:

- サイドバーに、サーベイごとの「次にやること」と、未選別・保留・採用・除外の論文。論文の上で採用・保留・除外（複数選択も可）
- 論文ごとのページ: 要旨・SSCI の判定・警告・調査範囲の採否基準を見ながら、**I** 採用・**M** 保留・**X** 除外（理由つき）。決めると次の未選別の論文に進みます。採用論文のページでは論文カードも表示・編集でき、エージェントが書いた内容を確かめて直せます（**Ctrl+S** で保存）
- 検索（関連度順・bulk 検索・SSCI 収録誌のみ）、引用をたどる、DOI で追加、本文の取得、Zotero、検査（問題パネル）、読むための版の表示、設定、診断、エンジンの更新
- エージェントへの依頼文のコピー。エージェントが状態やレポートを変えると、サイドバーと論文のページが追随します

別のマシンで続けるときは、VS Code でリポジトリを clone し、サイドバーのメニューの **Python の環境（.venv）を用意する** を実行して、**設定** でキーを入れ直します（`.env` は Git に載らないため）。

### コマンドラインで始める

```bash
mkdir my-surveys && cd my-surveys
python3 -m venv .venv
.venv/bin/pip install priorwork
.venv/bin/priorwork init --lang ja     # git init し、reports/ .priorwork/ AGENTS.md スキル ./priorwork .env.example などを作る
cp .env.example .env                   # API キーなどを記入（.env は Git 管理外）
./priorwork doctor                     # 設定を診断（--online で接続も確認）
git add -A && git commit -m "Initialize priorwork workspace"
gh repo create my-surveys --private --source=. --push   # GitHub に作って push（Web で作って git remote add しても可）
```

ワークスペースは GitHub の**非公開**リポジトリで管理する前提です（レポートと状態 JSON には論文の要旨などが入るため）。別のマシンで続けるときは、clone して `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` し、`.env` を作り直します（`priorwork settings` で設定済みの項目が分かります）。

`--lang` はワークスペースの言語です（レポートの見出し・AGENTS.md・スキル。後から変えられません）。CLI の表示の言語はこれとは別で、`PRIORWORK_LANG=ja` かロケールで決まります（VS Code の拡張機能は VS Code の表示言語に合わせます）。

Git に載るもの・載らないもの（`.gitignore` は `priorwork sync` が管理します）:

| Git に載る | Git に載らない |
| :--- | :--- |
| `reports/*.md`、`.priorwork/surveys/`（状態）、`.priorwork/config.json`、`.priorwork/sync.json`、AGENTS.md・スキル、`./priorwork`、`requirements.txt`、`.env.example` | `.env`（API キー）、`.venv/`、`.priorwork/cache/`（本文テキスト）、`.priorwork/data/`（SSCI リスト。ライセンス上共有しない）、`priorwork export` の出力 |

`./priorwork doctor` は、Git のリポジトリか、GitHub のリモートがあるか、`.env` が誤って Git に載っていないかも確認します。

`priorwork init` が作るもの:

```text
my-surveys/
├── reports/                 # レポート（作業用の .md と、priorwork export の出力 .html など）
├── AGENTS.md, CLAUDE.md     # エージェント向けの指示（priorwork sync が生成。直接編集しない）
├── AGENTS.local.md          # このワークスペース固有の指示（自由に編集）
├── .claude/skills/          # 工程ごとのスキル（.agent/skills への symlink）
├── .agent/skills/           # priorwork sync が生成
├── priorwork                # 実行用ラッパー（./priorwork。.venv があればそれを使う）
├── requirements.txt         # エンジンの版（priorwork==X.Y.Z）
├── .env / .env.example
└── .priorwork/
    ├── config.json          # ワークスペースの言語
    ├── surveys/             # 状態 JSON（Git 管理）
    ├── cache/               # 抽出した本文・Zotero の一覧（Git 管理外）
    └── data/                # SSCI 収録リストの CSV（Git 管理外）
```

### エンジンを更新する

```bash
./priorwork upgrade                  # PyPI の最新の版に上げる（--to 0.4.0 で指定）
```

`requirements.txt` を書き換え、`pip install` して、AGENTS.md・スキルを同期します。`pip install` に失敗したときは `requirements.txt` を元に戻します。

`./priorwork status` は、AGENTS.md・スキルがエンジンの版と合っていないと警告します。`priorwork sync` が上書きするのは、`priorwork sync` 自身が書き出したファイルだけです。由来の分からないファイルは、`--force` を付けない限り上書きしません。

### API キー

ワークスペースの `.env`（Git 管理外）に保存します。VS Code では **設定** のページで入れます。コマンドラインでは `.env` を直接書くか、`priorwork settings --stdin` に JSON を渡します。

| 変数 | 用途 |
| :--- | :--- |
| `SEMANTIC_SCHOLAR_API_KEY` | [Semantic Scholar API キー](https://www.semanticscholar.org/product/api#api-key-form)（推奨）。無いとレート制限で検索が失敗しやすい |
| `OPENALEX_API_KEY` / `OPENALEX_MAILTO` | 任意。OpenAlex はキー無しでも使えるが、1 日の利用量に上限がある |
| `ZOTERO_API_KEY` / `ZOTERO_USER_ID` | 任意。Zotero 連携（読み取り専用）。下の「Zotero 連携」を参照 |
| `ZOTERO_WEBDAV_URL` / `ZOTERO_WEBDAV_USER` / `ZOTERO_WEBDAV_PASSWORD` | 任意。Zotero のファイル同期に WebDAV（Nextcloud など）を使っている場合 |
| `ZOTERO_DATA_DIR` | 任意。このマシンで Zotero を動かしている場合のデータフォルダ（既定: `~/Zotero`） |

### Zotero 連携（任意）

設定すると、採用論文の Zotero 登録状況の確認（`priorwork zotero`、`status`、`check`）と、Zotero に添付した PDF からの本文取得（`priorwork fulltext`）ができます。Zotero・WebDAV のどちらにも書き込みはしません。

1. https://www.zotero.org/settings/keys で API キーを作成する。権限は **「Allow library access」だけ**（notes・write は外す）。同じページの「Your user ID for use in API calls」がユーザー ID
2. WebDAV 同期の場合は、PDF の zip が置かれているフォルダ（Zotero に設定した URL ＋ `zotero/`）の URL と認証情報を設定する。Nextcloud なら、専用ユーザーに `zotero` フォルダを**閲覧のみ**で共有し、そのユーザーのアプリパスワードを使うと安全
3. `./priorwork zotero` で接続を確認する（ライブラリの件数と WebDAV の接続結果が出る）

WebDAV が「フォルダが見つかりません」になる場合は URL を見直してください。Nextcloud をサブパス（例: `https://example.com/nextcloud/`）に置いている場合は、そのパスも含める必要があります。

```
https://example.com/nextcloud/remote.php/dav/files/<ユーザー名>/zotero/
```

### SSCI 収録リスト（推奨）

SSCI に収録されているかは、Clarivate の [Master Journal List](https://mjl.clarivate.com/) でしか確定できません。SSCI の収録誌リストを CSV でダウンロードし、VS Code の **設定** のページか `./priorwork settings --import-ssci <CSV>` で取り込んでください（`.priorwork/data/` にコピーされます。Git 管理外）。

リストが無い場合は、主要誌約 100 誌の内蔵リストによる**推定**になります。

| 表示 | 意味 |
| :--- | :--- |
| ✅ SSCI収録（リスト照合済） | 収録リストと ISSN または誌名が一致 |
| 🟡 SSCI収録の可能性大（誌名推定・要確認） | リスト未設定で、内蔵リストと一致 |
| 🔍 学術誌（SSCI未確認） / ⚪ SSCI非収録誌 | 学術誌だが SSCI 不明 / 収録リストに無い |
| 📕 書籍 / ❌ WP・プレプリント / ❓ 掲載誌不明 | 既定では検索結果から除外 |

---

## 使い方

### エージェントと進める

エージェントでワークスペースを開き、普通の言葉で頼みます（例:「最低賃金の雇用効果について先行研究を full でまとめて」）。エージェントは AGENTS.md とスキル（`.agent/skills/`。`.claude/skills/` からも見える）に従い、入口の `priorwork` スキルが状態を見て次の工程に進み、書き出しまで続けます。スキル名を打つ必要はありません（`/priorwork` と打っても構いません）。VS Code では、**新しいサーベイ → エージェントに任せる** と、サーベイの **エージェントに頼む…** が依頼文をコピーします。

| スキル | やること |
| :--- | :--- |
| `priorwork` | 入口。状態を見て、サーベイ全体を工程ごとに進める |
| `priorwork-new` | 範囲を決めてサーベイを作成し、深さに見合う検索をする |
| `priorwork-screen` | 候補を採否の基準に照らして、理由つきで判断する（相談モードでは推薦して答えを待つ） |
| `priorwork-snowball` | 採用論文の参考文献・被引用から見落としを探す |
| `priorwork-extract` | 本文を取得し、論文カード（RQ・識別戦略など）を記入する |
| `priorwork-check` | 検査して問題を直し、レポートを書き出す |
| `priorwork-manuscript` | 分析まで済んだ原稿を読み、それを支える・食い違う文献を集めて、原稿の 1〜3 章（イントロ・先行研究・理論と仮説）を下書きする |

### 分析まで済んだ原稿から

「データと方法」「分析」まで書いた原稿があれば、ワークスペースの `manuscripts/<論文名>/` に原稿と結果の表を入れ、「manuscripts/<論文名> の原稿のイントロ・先行研究・仮説を書いて」と頼みます（サイドバーの **新しいサーベイ → 原稿から始める** でも依頼文を作れます）。エージェントは原稿から文献で支える主張（重要性・研究の流れ・メカニズム・方法の先例）を洗い出し、結果と食い違う知見も含めて主張ごとに探し、各論文カードに「原稿での役割」を記入して、1〜3 章を原稿の言語で下書きします（`./priorwork new … --manuscript manuscripts/<論文名>`）。下書きは `./priorwork export SURVEY --draft` で `reports/<名前>.draft.md`（引用した論文の参考文献つき）に書き出されます。結果を見てから仮説を立てることにならないよう、仮説ごとの根拠と、探索的に扱う結果の案を、レポートに別に記録します。原稿そのものは書き換えません。

既定では、エージェントが自分で判断して進めます。範囲と採否を自分で決めたいときは「相談しながら進めて」と頼むか、`AGENTS.local.md` にそう書きます。会話を再開したときは「続きをやろう」と言えば、エージェントが `./priorwork status` で進捗と次の作業を確認します。

### 深さ（quick / full）

サーベイには深さがあります。依頼の言葉から（無ければエージェントが）決め、あとから `./priorwork scope SURVEY --depth full` で変えられます。

| | quick（簡易） | full（本格） |
| :--- | :--- | :--- |
| 向くテーマ | 狭い・概観だけ欲しい | 広い・サブテーマが複数ある・網羅性が要る |
| 検索 | 2〜3 クエリ（1 回 10 件） | サブテーマごとに 2〜4 クエリ（1 回 25 件）、候補 100 本以上 |
| スナウボール | 任意 | 行う |
| カード | 要旨のみでよい | 採用論文すべてを本文で確かめる（本文が見つからないものだけ要旨のみ） |

件数などは目安で、固定の上限はありません。ルールと `priorwork check` は深さによらず同じです。

### サーベイのファイル

| ファイル | 中身 | 編集 |
| :--- | :--- | :--- |
| `reports/YYYYMMDD_<slug>.md` | 作業用のレポート本体 | 文章と論文カードの記入欄は手で書く。`<!-- BEGIN priorwork:… -->` 〜 `<!-- END priorwork:… -->` の範囲は `priorwork` が再生成 |
| `.priorwork/surveys/YYYYMMDD_<slug>.json` | 論文候補・採否と理由（変更の履歴つき）・検索履歴・調査範囲・深さ・レポートの言語 | `priorwork` コマンド（と VS Code の拡張機能）だけで変更する |

- **読むための版**は `./priorwork export <survey>` で作ります（`reports/YYYYMMDD_<slug>.html`。ブラウザで開くか、印刷して PDF にできます）。管理ブロックのコメント、未記入の記入欄、テンプレートの説明文を除き、要旨も省きます（`--with-abstracts` で載せる）。`--format docx`（pandoc が必要）、`--format md` も選べます。未記入・未確認の論文カード・`check` の ERROR が残っていると、冒頭に「下書き」と表示されます。出力は Git 管理外です
- **比較マトリクス**（2 章）は、各論文カード（3 章）の記入欄から自動で作られます。カードを書き換えたら `./priorwork render`
- **参照文献**（8 章）は採用論文から DOI つきで自動生成されます（引用キーは作りません。Zotero へは手作業で登録）。本文で同じ「著者 (年)」になる採用論文が複数あると、タイトル順に 2001a / 2001b と区別します（カード・比較マトリクスも同じ表記）
- **文献探索の記録**（付録）には、実行した検索・件数・除外理由と、採否を見直した論文の件数が自動で残ります。採否の経緯（例: 保留 → 除外（理論のみ） → 採用）は `./priorwork list` に表示されます
- 採用を取り消した論文のカードは、記入内容ごと JSON に退避され、再び採用すると復元されます

### コマンド一覧

```bash
# ワークスペースの管理
./priorwork init [DIR] [--lang ja|en]                          # ワークスペースを初期化
./priorwork sync [--force|--diff]                              # AGENTS.md・スキル・./priorwork をエンジンの版に更新
./priorwork upgrade [--to X.Y.Z]                               # エンジンを更新して sync
./priorwork doctor [--online]                                  # 設定（API キー・SSCI リスト・エンジンの版）を診断
./priorwork settings [--stdin] [--import-ssci CSV]             # API キー・Zotero・SSCI リストの設定

# サーベイの管理
./priorwork status [SURVEY]                                    # 一覧 / 進捗と次にやること
./priorwork new "<テーマ>" --slug <slug> [--depth quick|full] [--question ... --years ... --fields ... --inclusion ... --exclusion ...]
./priorwork scope SURVEY --question "..." [--depth quick|full]  # 範囲の変更
./priorwork archive SURVEY [--undo]                          # 一覧から隠す（ファイルは残る）
./priorwork list SURVEY [--status candidate maybe] [--abstract]
./priorwork include SURVEY 2 5 7
./priorwork exclude SURVEY 3 --reason "理論モデルのみ"          # 除外には理由が必須
./priorwork maybe SURVEY 9          ./priorwork reset SURVEY 9 # 保留 / 候補に戻す
./priorwork add SURVEY <DOI>... [--candidate]                  # DOI を指定して登録（既定で採用）
./priorwork card SURVEY 3 [--set rq="..." evidence=abstract]   # 論文カードを表示・記入
./priorwork render SURVEY
./priorwork check SURVEY [--offline]
./priorwork export SURVEY [--format html|docx|md] [-o PATH] [--with-abstracts]   # 読むための版を書き出す
./priorwork fulltext SURVEY <番号> [--pdf <パス>]
./priorwork zotero [SURVEY] [--refresh]                         # Zotero 接続確認 / 採用論文の登録状況
./priorwork zotero --collections | SURVEY --collection 名前 | SURVEY --import | SURVEY --dois  # コレクション

# 文献の探索
./priorwork search "<English query>" [--into SURVEY] [--bulk] [--sort citations|relevance|recent|cpy] [--year 2010-2024] [--ssci-only] [--limit N]
./priorwork snowball SURVEY [--direction both|references|citations] [--limit N] [--min-links N]
./priorwork get <DOI>
./priorwork citations <DOI> [--sort cited]      ./priorwork references <DOI> [--sort cited]
./priorwork journal "<誌名 or ISSN>"
```

`SURVEY` はファイル名（拡張子なし）か slug で指定します。多くのコマンドは `--json` で JSON を出力します（VS Code の拡張機能・スクリプト向け）。

---

## しくみ

### 検索

- **通常の検索**は Semantic Scholar の関連度検索です
- **`--bulk`** は Semantic Scholar の bulk 検索で、`+`（AND）、`|`（OR）、`-`（除外）、`"フレーズ"` が使え、被引用数の多い順に取得します。キーワード検索では埋もれやすい定番論文を拾えます
- 並び順（`--sort`）: `citations` 被引用数 / `relevance` 関連度 / `recent` 新しい順 / `cpy` 年あたり被引用数。いずれも SSCI 判定の高いものが先です
- 同じ論文の WP 版と掲載版が両方あれば、掲載版だけを残します

### データソースの役割分担

| 処理 | Semantic Scholar | OpenAlex |
| :--- | :--- | :--- |
| 検索 | ✔ | 使わない（関連度が低いため） |
| 書誌情報の照合 | — | ✔ S2 の結果を DOI でまとめて照合し、誌名・ISSN・巻号を置き換える |
| 論文取得（`get` / `add`） | ✔ まず S2 | S2 に無い DOI のとき |
| 引用関係（`citations` / `references`） | ✔ `--sort recent` | `--sort cited`、S2 に無い・出版社が非公開のとき |
| `snowball` / `check` の DOI 再確認 | — | ✔ |

Semantic Scholar は検索の質が高い一方、定番論文ほどレコードが壊れていることがあります（別論文や SSRN 版の DOI、ISSN の欠落、未登録）。そのため DOI と ISSN は OpenAlex で実体を確認した値を使い、問題があれば ⚠️ を表示します。

| 警告 | 意味 |
| :--- | :--- |
| DOI が別タイトルを指している | S2 の DOI が別の論文（リプライ論文など）のもの |
| DOI は WP / プレプリント版 | S2 は掲載誌を示しているが、DOI は SSRN などの WP 版 |
| OpenAlex に DOI が見つからない / DOI なし / DOI 未照合 | DOI の誤り、欠落、または照合できなかった |
| 書評・コメントの可能性 | タイトルが「…, by 著者名」の形、または 1 ページだけ |

### 引用をたどる（snowball）

採用論文の参考文献と被引用論文を OpenAlex から集め、「採用論文のうち何本と引用関係にあるか（リンク数）」の多い順に候補を登録します。採用論文が 3 本以上なら、既定ではリンク数 2 以上だけを候補にします。

### 本文の取得（fulltext）

PDF はワークスペースに置きません。次の順で PDF を探し、抽出したテキストだけを Git 管理外の `.priorwork/cache/fulltext/` に保存します。

1. `--pdf` で指定したファイル
2. このマシンの Zotero の添付 PDF（`zotero.sqlite` を読み取り専用で開き、DOI で照合）
3. Zotero Web API で見つけた添付 PDF（WebDAV の `<キー>.zip`、または Zotero File Storage から取得）
4. Zotero が索引化した本文テキスト（ページ区切りが無いため、PDF が取れないときの予備）
5. オープンアクセス版の PDF

出版社のサイトは自動ダウンロードを拒否することが多いため、非 OA の論文は Zotero に PDF を添付してから実行してください。

Zotero の論文一覧は `.priorwork/cache/zotero/index.json` に保存し、次回からは変更分だけを取得します。論文と照合するときは DOI（「その他」欄の `DOI: ...` も含む）を使い、DOI の無い論文だけタイトルで照合します。

### 検査（check）

| 検査 | レベル |
| :--- | :--- |
| 本文・カード中の「著者 (年)」「(著者, 年; 著者, 年)」が登録済みの論文に対応しているか | ERROR（未登録）/ WARN（未採用） |
| 2001a / 2001b の区別が参照文献と合っているか | WARN |
| 本文中の DOI が登録済みか | ERROR |
| 採用論文の ⚠️、OpenAlex での DOI とタイトルの一致 | ERROR |
| カードの確認レベル（未確認 / 要旨のみ / 本文確認済）と未記入の欄 | WARN |
| Markdown が状態ファイルと一致しているか（`render` 忘れ） | WARN |
| 未選別の候補、SSCI 以外の採用論文、Zotero 未登録の採用論文（連携設定時）、組織名・図表番号とみなして照合しなかった引用 | INFO |

著者年引用の検出は正規表現によるもので、すべての書き方を拾えるわけではありません。叙述型（`Acemoglu et al. (2001, 2005)`、`Dell (2010, p. 5)`）と、括弧にまとめた型（`(e.g., Dell 2010; Acemoglu et al., 2001a)`）を検出します。

「World Bank (2010)」「OECD (2019)」のような組織名・略語は、未登録でも ERROR にせず INFO で伝えます。論文ではないのに引用と誤認されたものは、レポートに次のコメントを書くと検査から外せます。

```markdown
<!-- priorwork:ignore-citation Smith (2015) -->
```

### 扱えない文献

国内学会誌（J-STAGE など）の論文は Semantic Scholar・OpenAlex のどちらにも登録されていないことが多く、`priorwork get` / `priorwork add` で登録できません（`... は Semantic Scholar にも OpenAlex にも見つかりません` と表示されます）。国際査読誌を対象とする方針のため、現状は対象外です。

### その他

- **リトライ**: HTTP 429 / 5xx / 通信エラーは、5→10→20→40→60 秒と待ち時間を延ばして最大 5 回再試行（`PRIORWORK_MAX_RETRIES`）
- **キャッシュ**: API レスポンスを `~/.cache/priorwork/` に 7 日間保存（`PRIORWORK_CACHE_TTL_DAYS`、`PRIORWORK_NO_CACHE=1`、`--no-cache`）
- **表示の言語**: `PRIORWORK_LANG=ja|en`、無ければロケール

---

## 開発

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest          # ネットワーク不要
bin/priorwork --help                # このチェックアウトのコードで動かす
```

```text
.
├── priorwork/
│   ├── cli.py                  # コマンド（--json の出力を含む）
│   ├── i18n.py / lang_ja.py    # 表示の言語（英語が原文、日本語は対訳表）
│   ├── workspace.py            # ワークスペースのパスと言語
│   ├── scaffold.py             # init / sync / upgrade
│   ├── survey.py               # 状態ファイルと Markdown 生成
│   ├── api.py                  # Semantic Scholar / OpenAlex
│   ├── ssci.py                 # SSCI 判定
│   ├── snowball.py             # 引用をたどる
│   ├── fulltext.py             # 本文取得（Zotero / OA）
│   ├── zotero.py               # Zotero Web API / WebDAV（読み取り専用）
│   ├── check.py                # 検査
│   ├── export.py               # 読むための版の書き出し
│   ├── doctor.py               # 設定の診断
│   └── assets/                 # ワークスペースに配る原本（en/・ja/ ごとの AGENTS.md・skills・レポートのテンプレート、env.example）
├── vscode-extension/           # VS Code の拡張機能（TypeScript）
├── tests/
└── bin/priorwork               # 開発用ラッパー
```

AGENTS.md・スキルを直すときは、`priorwork/assets/en/` と `priorwork/assets/ja/` の両方を編集します。ワークスペースには `priorwork sync` で配られます。

不具合の報告や要望は [Issues](https://github.com/yoshida-kd/priorwork/issues) へどうぞ。
