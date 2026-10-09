---
name: priorwork-extract
description: >-
  Fills in the per-paper cards (RQ, X, Y, data, identification strategy, findings, limitations) of a
  survey from abstracts or full texts retrieved with `./priorwork fulltext`, then regenerates the comparison
  matrix with `./priorwork render`. Use when included papers have unfilled cards.
---

# 各論文のカードを記入する

ルールは [AGENTS.md](../../../AGENTS.md) に従う。

## 深さによる違い

- `full`: 中核論文（被引用数が多い・RQ に直結する・リンク数が多い）は本文を取得し、確認レベルを「本文確認済」にする。それ以外は要旨のみでよい。
- `quick`: 要旨だけで記入してよい（確認レベルは「要旨のみ」）。

どちらでも、要旨・本文に書かれていることだけを書き、確認レベルを必ず更新する。

## 手順（1 本ずつ、採用論文がなくなるまで）

1. 未記入の論文を確認する。Zotero のコレクションを結び付けていれば、そこに PDF がある論文から始める。

   ```bash
   ./priorwork status <survey>
   ./priorwork zotero <survey>     # Zotero 連携があれば、PDF の有無が分かる
   ```

2. 本文を取得する（Zotero の PDF → オープンアクセス版の順に探す）。

   ```bash
   ./priorwork fulltext <survey> <番号>
   ```

   取得できなければ要旨だけで記入し、確認レベルを「要旨のみ」にする。本文が取れなかった論文は、最後の報告で「Zotero に PDF を添付すれば本文で確かめられる」と伝える。

   取得元が「Zotero の索引テキスト（ページ区切りなし）」の場合、ページ番号は書かず「（ページ未確認）」とする。

3. サーベイ Markdown の 3 章で、その論文のカード（`<!-- paper: ... -->` の下）の記入欄だけを書き換える（`./priorwork card <survey> <番号> --set rq=... evidence=fulltext` でもよい）。
   - 見出し行・`書誌` 行・`⚠️` 行は自動生成されるので触らない。
   - `**RQ**: ` などの行内には、マトリクスに載る短い要約（1 文）を書く。詳細は直下に `  - ` の箇条書きで足す。
   - 本文に書かれていることだけを書く。$N$・推定値・期間は本文の表記どおりに書き、該当ページを `（p.12）` のように添える。
   - 見つからなければ「記載なし」と書く。推測で埋めない。
   - `**確認レベル**` を「本文確認済」または「要旨のみ」に更新する。
   - 本文を読んで範囲から外れると分かった論文は、カードを書かずに `./priorwork exclude` で理由を付けて除外する。

4. 数本ごとにマトリクスを更新する。

   ```bash
   ./priorwork render <survey>
   ```

相談モードのときだけ、2〜3 本ごとに要点（識別戦略・主な結果）を伝えて、続けるか確かめる。
