---
name: priorwork-screen
description: >-
  Screens the candidate papers of a literature survey against its inclusion and exclusion criteria and
  records include/exclude/maybe with a reason for each (`./priorwork include|exclude|maybe`). Decides on its
  own by default; in consultation mode, presents recommendations and waits. Use when a survey has unscreened candidates.
---

# 候補を選別する

ルールは [AGENTS.md](../../../AGENTS.md) に従う。

## 手順（既定: 任せて進める）

1. 候補を要旨つきで表示する。

   ```bash
   ./priorwork status <survey>                 # 範囲（RQ・採用基準・除外基準）を確かめる
   ./priorwork list <survey> --status candidate --abstract
   ```

2. 1 本ずつ、範囲の採用・除外基準に照らして判断し、理由を付けて記録する。まとめて記録してよい。

   ```bash
   ./priorwork include <survey> 2 5 7 --reason "自治体の外部委託と人員の関係を実証"
   ./priorwork exclude <survey> 3 --reason "理論モデルのみ"
   ./priorwork maybe <survey> 9 --reason "要旨では識別戦略が不明。本文で確認"
   ```

   - 理由は 1 行で、どの基準に当たったかが分かるように書く。同じ理由で除外するものはまとめて 1 回で記録する。
   - 要旨だけでは判断できないものは「保留」にし、何が分からないかを理由に書く。保留は、カードの記入の前に本文や `./priorwork get` で確かめて、採用か除外に決める。
   - 迷ったら、full では採用寄り（後で除外できる）、quick では除外寄りにする。
   - WP・プレプリント・書評・コメントは除外（AGENTS.md ルール 1）。⚠️ 付きは下の手順。
   - **ユーザーが下した採否は変えない。** 候補（candidate）だけを判断する。

3. 候補がなくなるまで繰り返す。終わったら採用・保留・除外の件数を控え、次の工程（`priorwork-snowball` または `priorwork-extract`）に進む。

## 相談モード

ユーザーが相談しながら進めたいと言ったとき（または `AGENTS.local.md` にそうあるとき）は、記録する前に答えを待つ。

1. 5〜10 件ずつ、次の形で示す（番号は `#` の番号をそのまま使う）。

   | # | 著者 (年) | 掲載誌 | 推薦 | 理由（採用・除外基準に照らして 1 行） |
   | :--- | :--- | :--- | :--- | :--- |

2. ユーザーの返答（例:「2,5,7 採用、3 は除外」）をそのまま記録する。除外には理由が必須。
3. ユーザーがサイドバーで選別したと言ったら、続ける前に一覧を取り直す。

## ⚠️ DOI 要確認の論文

「DOI が別タイトルを指している」「DOI は WP / プレプリント版」の論文は、掲載版を探して登録し直す。

```bash
./priorwork search "<論文タイトル>" --limit 5
./priorwork get "<掲載版の DOI>"        # タイトル・誌名・年が一致することを確認
./priorwork add <survey> "<掲載版の DOI>"
./priorwork exclude <survey> <元の番号> --reason "DOI 誤りのため #<新しい番号> に置き換え"
```

掲載版が確認できなければ採用せず「保留」にし、報告で伝える。
