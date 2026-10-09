---
name: survey-screen
description: >-
  Screens candidate papers of a literature survey together with the user: presents candidates in
  small numbered batches with a recommendation, then records include/exclude/maybe decisions with
  `./priorwork include|exclude|maybe`. Use when a survey has unscreened candidates.
---

# 候補を選別する

ルールは [AGENTS.md](../../../AGENTS.md) に従う。**採否を決めるのはユーザー。** エージェントは推薦と理由を示すだけ。

## 手順

1. 候補を要旨つきで表示する。

   ```bash
   ./priorwork list <survey> --status candidate maybe --abstract
   ```

2. 5〜10 件ずつ（`quick` なら 10 件程度まとめて、`full` なら 5 件前後に絞って）、次の形でユーザーに示す（番号は `#` の番号をそのまま使う）。

   | # | 著者 (年) | 掲載誌 | 推薦 | 理由（範囲の採用・除外基準に照らして 1 行） |
   | :--- | :--- | :--- | :--- | :--- |

   - 推薦は「採用 / 除外 / 保留」。判断材料が要旨にない場合は「保留」とし、何が分からないかを書く。
   - ⚠️ 付き（DOI 要確認、書評の可能性など）はその旨を必ず書く。

3. ユーザーの返答（例:「2,5,7 採用、3 は除外」）をそのまま記録する。除外には理由が必須。

   ```bash
   ./priorwork include <survey> 2 5 7
   ./priorwork exclude <survey> 3 --reason "理論モデルのみ"
   ./priorwork maybe <survey> 9 --reason "本文で識別戦略を確認"
   ```

4. 候補がなくなるか、ユーザーが止めるまで 2〜3 を繰り返す。

ユーザーは VS Code の Prior Work のサイドバーで選別することもある。そう言われたら、続ける前に 1 の一覧を取り直す。

## ⚠️ DOI 要確認の論文を採用するとき

「DOI が別タイトルを指している」「DOI は WP / プレプリント版」の論文は、掲載版を探して登録し直す。

```bash
./priorwork search "<論文タイトル>" --limit 5
./priorwork get "<掲載版の DOI>"        # タイトル・誌名・年が一致することを確認
./priorwork add <survey> "<掲載版の DOI>"
./priorwork exclude <survey> <元の番号> --reason "DOI 誤りのため #<新しい番号> に置き換え"
```

確認できない場合は採用せず「保留」にし、ユーザーに伝える。

## 終わったら

採用件数を伝え、次に引用をたどって見落としを補う（`/survey-snowball`）か、カードの記入（`/survey-extract`）に進むかを聞く。
