---
name: survey-check
description: >-
  Validates a literature survey with `./priorwork check` (unregistered author-year citations, DOIs that
  point to other papers, unfilled cards, stale matrix) and fixes the reported problems.
  Use after editing a survey and before telling the user that a section or the survey is done.
---

# サーベイを検査して直す

ルールは [AGENTS.md](../../../AGENTS.md) に従う。

## 手順

1. 検査する。

   ```bash
   ./priorwork check <survey>
   ```

2. 指摘ごとに対応する。

   | 指摘 | 対応 |
   | :--- | :--- |
   | 本文中の引用「X (年)」が未登録 | `./priorwork search` / `./priorwork get` で実在と書誌を確認し、`./priorwork add <survey> <DOI>` で登録。見つからなければ、その記述を削除するか「要出典」と明記してユーザーに伝える |
   | 本文中の DOI が未登録 | 上と同じ |
   | 引用が採用論文の複数に当たる / 2001a に当たる論文がない | 参照文献（8 章）の 2001a / 2001b の表記に合わせて本文の引用を直す |
   | 組織名・図表番号とみなして照合しなかった引用（INFO） | 論文なら上と同じく登録する。報告書・統計などはそのままでよい |
   | 論文ではない記述が引用と誤認される | その記述の近くに `<!-- priorwork:ignore-citation 著者 (年) -->` を書く。実在する論文の引用を隠すためには使わない |
   | ⚠️ DOI が別タイトルを指している / WP 版 | `/survey-screen` の「⚠️ DOI 要確認の論文を採用するとき」の手順で置き換える |
   | 確認レベルが未確認 / 未記入の欄 | `/survey-extract` の手順で記入 |
   | Markdown が状態ファイルと一致しない | `./priorwork render <survey>` |
   | 管理ブロックが見つからない | 消えた `<!-- BEGIN priorwork:… -->` / `<!-- END priorwork:… -->` を git の履歴などから復元 |

3. ERROR が 0 になるまで 1〜2 を繰り返す。WARN と INFO は、残っているものをユーザーに伝える。

**ERROR が残っている間は、ユーザーに「完成した」と言わない。**

## 4. ERROR が 0 になったら

読むための版を書き出し、ユーザーに見てもらう。

```bash
./priorwork export <survey>
```

出力の冒頭に「下書き」の表示が出た場合は、その理由（未確認のカード、未記入の節など）をユーザーに伝え、完成とは言わない。
