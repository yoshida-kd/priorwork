---
name: survey-extract
description: >-
  Fills in the per-paper cards (RQ, X, Y, data, identification strategy, findings, limitations) of a
  survey from abstracts or full texts retrieved with `./priorwork fulltext`, then regenerates the comparison
  matrix with `./priorwork render`. Use when included papers have unfilled cards.
---

# 各論文のカードを記入する

ルールは [AGENTS.md](../../../AGENTS.md) に従う。

## 深さによる違い

- `full`: 中核論文は本文を取得し、確認レベルを「本文確認済」にする。
- `quick`: 要旨だけで記入してよい（確認レベルは「要旨のみ」）。本文がほしい論文だけユーザーと相談して取得する。

どちらでも、要旨・本文に書かれていることだけを書き、確認レベルを必ず更新する。

## 手順（1 本ずつ）

1. 未記入の論文を確認する。

   ```bash
   ./priorwork status <survey>
   ```

2. 本文を取得する。Zotero に PDF が添付されていればそれを使い（Zotero 連携の設定時）、無ければオープンアクセス版を探す。

   ```bash
   ./priorwork fulltext <survey> <番号>
   ./priorwork fulltext <survey> <番号> --pdf "<PDF のパス>"   # ユーザーから PDF の場所を聞いた場合
   ```

   取得できなければ、ユーザーに「Zotero に PDF を添付するか、PDF の場所を教えてほしい」と伝える（`./priorwork zotero <survey>` で Zotero の登録状況と PDF の有無が分かる）。要旨だけで進めるかどうかもユーザーに確認する。

   取得元が「Zotero の索引テキスト（ページ区切りなし）」の場合、ページ番号は書かず「（ページ未確認）」とする。

3. サーベイ Markdown の 3 章で、その論文のカード（`<!-- paper: ... -->` の下）の記入欄だけを書き換える。
   - 見出し行・`書誌` 行・`⚠️` 行は自動生成されるので触らない。
   - `**RQ**: ` などの行内には、マトリクスに載る短い要約（1 文）を書く。詳細は直下に `  - ` の箇条書きで足す。
   - 本文に書かれていることだけを書く。$N$・推定値・期間は本文の表記どおりに書き、該当ページを `（p.12）` のように添える。
   - 見つからなければ「記載なし」と書く。推測で埋めない。
   - `**確認レベル**` を「本文確認済」または「要旨のみ」に更新する。

4. マトリクスを更新する。

   ```bash
   ./priorwork render <survey>
   ```

5. 2〜3 本ごとにユーザーへ要点（識別戦略・主な結果）を報告し、続けるか確認する。
