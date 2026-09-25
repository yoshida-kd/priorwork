# Prior Work

**AI エージェントと対話しながら作る、社会科学の先行研究サーベイ**

[English](README.md)

社会科学（経済学・社会学・政治学・経営学・心理学など）のテーマ別文献サーベイを、AI エージェント（Claude Code・Antigravity など）と対話しながら作るためのツールです。VS Code の拡張機能を使うと、候補の選別や検索・検査をサイドバーから操作できます。

- **チャットが画面、リポジトリが記憶。** 論文の候補・採否・検索履歴は `.priorwork/surveys/` の JSON に残るので、会話をまたいで続きから作業できます
- **採否はユーザーが決める。** エージェントは候補を番号つきで示して推薦し、「2, 5, 7 を採用」のような指示を記録します。VS Code では論文ごとのページでキー 1 つで決められます
- **でっち上げを機械的に検出する。** 本文中の「著者 (年)」が登録済みの論文に対応しているか、DOI が別の論文を指していないかを `priorwork check` で検査します
- **人が読むのは `reports/` のレポートだけ。** `priorwork export` が読むための版（HTML）を作ります。状態ファイルやキャッシュは `.priorwork/` に隠れています

```
① 範囲を決める → ② 検索 → ③ 選別 → ④ 引用をたどる → ⑤ 本文から記入 → ⑥ 検査
   /survey-new               /survey-screen  /survey-snowball  /survey-extract   /survey-check
```

## 構成

| | エンジン（`priorwork` コマンド・VS Code 拡張機能） | ワークスペース |
| :--- | :--- | :--- |
| 持つもの | コード、AGENTS.md・スキルの原本 | サーベイのレポート、状態、`.env` |
| 入手 | PyPI（`pip install priorwork`）・VS Code Marketplace（Prior Work） | 自分で作る（GitHub の非公開リポジトリ） |
| 更新 | 版を切ってリリース | `./priorwork upgrade` |

ワークスペースは `requirements.txt` でエンジンの版を固定しているので、意図しない更新は起きません。新しい版に上げるときは `./priorwork upgrade` の1コマンドです（コードのコピーを持たないので、マージの衝突は起きません）。

---

## セットアップ

### VS Code から始める

1. VS Code の拡張機能で **Prior Work** を入れます（**Python 3.10 以上**と **git** が必要）
2. アクティビティバーの Prior Work から **ワークスペースを作る** を選び、空のフォルダとレポートの言語（日本語・英語）を選びます。拡張機能がそのフォルダに `.venv` を作り、PyPI から `priorwork` を入れて `priorwork init` します
3. **.env を開く** で API キーを設定します（下の「API キー」）
4. **新しいサーベイ** → **検索** → **候補を選別する**。その先の記入や文章はエージェントに頼みます

拡張機能でできること:

- サイドバーに、サーベイごとの「次にやること」と、未選別・保留・採用・除外の論文。論文の上で採用・保留・除外（複数選択も可）
- 論文ごとのページ: 要旨・SSCI の判定・警告・調査範囲の採否基準を見ながら、**I** 採用・**M** 保留・**X** 除外（理由つき）。決めると次の未選別の論文に進みます
- 検索（関連度順・bulk 検索・SSCI 収録誌のみ）、引用をたどる、DOI で追加、本文の取得、検査（問題パネル）、読むための版の表示、設定の診断、`sync`・`upgrade`、lit からの移行
- エージェントがターミナルで状態を変えると、サイドバーが追随します

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

ワークスペースは GitHub の**非公開**リポジトリで管理する前提です（レポートと状態 JSON には論文の要旨などが入るため）。別のマシンで続けるときは、clone して `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` し、`.env` を作り直します。

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

### lit（旧名）のワークスペースを移行する

Prior Work は `lit` という名前で開発していました。lit で作ったワークスペース（`.lit/`、`./lit`）は、次の手順で移行します。VS Code の拡張機能で開くと、サイドバーに **Prior Work に移行する** が出ます（`.venv` に priorwork が無ければ入れるところから案内します）。

```bash
.venv/bin/pip install priorwork
.venv/bin/priorwork migrate
git status                                      # 移動の内容を確認してコミット
```

- `.lit/` を `.priorwork/` に移します（状態・キャッシュ・同期の記録）。ワークスペースの言語は日本語になります
- `./lit` を消して `./priorwork` を書き出し、`requirements.txt` の `litsurvey @ git+…` を `priorwork==X.Y.Z` に、`.gitignore` の lit のブロックを priorwork のものに置き換えます
- レポートの管理ブロックの印（`<!-- BEGIN lit:… -->`）を `<!-- BEGIN priorwork:… -->` に書き換えます（手で書いた文章・カードはそのまま）。`<!-- lit:ignore-citation … -->` はそのまま使えます
- `.env` の `LIT_MAX_RETRIES` などは `PRIORWORK_…` に名前を変えてください（`doctor` が知らせます）

さらに古いテンプレート（`surveys/` に md と json が同居し、`litsurvey/` のコードごとコピーされている構成）も `priorwork migrate [--clean]` で移せます。`--clean` はコピーされていたエンジンのコードを削除します。上書きした旧 AGENTS.md などは `.priorwork/cache/migrate-backup/` に退避します。

### API キー

ワークスペースの `.env` に書きます。

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

SSCI に収録されているかは、Clarivate の [Master Journal List](https://mjl.clarivate.com/) でしか確定できません。SSCI の収録誌リストを CSV でダウンロードし、`.priorwork/data/` に置いてください（ダウンロードしたときのファイル名のままで構いません。Git 管理外）。

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

Claude Code（または Antigravity など）でワークスペースを開き、たとえば「最低賃金の雇用効果についてサーベイを始めたい」と話しかけます。
エージェントは AGENTS.md のルールに従い、工程ごとのスキル（`.agent/skills/`）を使って進めます。スキルは `/survey-new` のように直接呼び出すこともできます。

| スキル | やること | ユーザーが決めること |
| :--- | :--- | :--- |
| `/survey-new` | サーベイを作成し、最初の検索をする | RQ・期間・採用 / 除外基準・深さ |
| `/survey-screen` | 候補を 5〜10 件ずつ推薦つきで示す（VS Code のサイドバーで自分で選別してもよい） | 採用 / 除外（理由つき）/ 保留 |
| `/survey-snowball` | 採用論文の参考文献・被引用から見落としを探す | 候補の採否 |
| `/survey-extract` | 本文を取得し、論文カード（RQ・識別戦略など）を記入する | PDF の場所、要旨だけで進めるか |
| `/survey-check` | 検査して問題を直す | 解決できなかった指摘の扱い |

会話を再開したときは「続きをやろう」と言えば、エージェントが `./priorwork status` で進捗と次の作業を確認します。

### 深さ（quick / full）

サーベイには深さがあります。`/survey-new` でユーザーと決め、あとから `./priorwork scope SURVEY --depth full` で変えられます。

| | quick（簡易） | full（本格） |
| :--- | :--- | :--- |
| 向くテーマ | 狭い・概観だけ欲しい | 広い・サブテーマが複数ある・網羅性が要る |
| 検索 | 1〜2 クエリ | サブテーマごとに複数クエリ |
| スナウボール | 任意 | 行う |
| カード | 要旨のみでよい | 中核論文は本文確認済まで |

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
./priorwork migrate [--clean]                                  # lit のワークスペースや旧構成から移行

# サーベイの管理
./priorwork status [SURVEY]                                    # 一覧 / 進捗と次にやること
./priorwork new "<テーマ>" --slug <slug> [--depth quick|full] [--question ... --years ... --fields ... --inclusion ... --exclusion ...]
./priorwork scope SURVEY --question "..." [--depth quick|full]  # 範囲の変更
./priorwork list SURVEY [--status candidate maybe] [--abstract]
./priorwork include SURVEY 2 5 7
./priorwork exclude SURVEY 3 --reason "理論モデルのみ"          # 除外には理由が必須
./priorwork maybe SURVEY 9          ./priorwork reset SURVEY 9 # 保留 / 候補に戻す
./priorwork add SURVEY <DOI>... [--candidate]                  # DOI を指定して登録（既定で採用）
./priorwork render SURVEY
./priorwork check SURVEY [--offline]
./priorwork export SURVEY [--format html|docx|md] [-o PATH] [--with-abstracts]   # 読むための版を書き出す
./priorwork fulltext SURVEY <番号> [--pdf <パス>]
./priorwork zotero [SURVEY] [--refresh]                         # Zotero 接続確認 / 採用論文の登録状況

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
│   ├── scaffold.py             # init / sync / upgrade / migrate
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
