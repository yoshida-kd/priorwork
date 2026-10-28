---
name: priorwork-derive
description: >-
  Writes a short text made from a finished survey — a lecture handout, reading notes, a summary of the
  main points — in `reports/<survey>.<name>.md`, with its purpose, length and structure recorded by
  `./priorwork derive`. Cites only included papers from cards checked against the full text, and checks
  each number and the direction of each finding against the card. Use when asked for lecture material,
  notes, a summary or any other short text based on a survey.
---

# サーベイから派生する短い文章を書く

ルールは [AGENTS.md](../../../AGENTS.md) に従う。講義資料・読書メモ・要点の整理など、サーベイを元にした短い文章を頼まれたときの手順。サーベイのレポート（`reports/<survey>.md`）や原稿の下書き（`--draft`）とは別のファイルに書く。

## 1. 何を作るかを決める

依頼の言葉から次を決める。書かれていなければ、推測で決めて報告で伝える（手動の進め方なら聞く）。

- **名前**: 英小文字・数字・`-`・`_`（例: `lecture`、`reading-notes`）。ファイルは `reports/<survey>.<名前>.md`。
- **用途**: 誰が何に使うか（例: 「行政学の講義資料（学部 2 年向け、90 分）」）。
- **字数**: 目安（日本語は文字数、英語は語数）。引用の括弧（「（Dell 2010）」）を字数に含めるかも決める。言われなければ含めない。
- **構成**: 節の見出し（例: 「背景; 先行研究の知見; 残る問い」）。

```bash
./priorwork derive <survey> <名前> --purpose "<用途>" --length 2000 --structure "背景; 先行研究の知見; 残る問い" [--count-citations]
./priorwork derive <survey>       # このサーベイの派生文書の一覧
```

既にある名前なら、用途・字数などの記録だけが直り、書いた文章はそのまま残る。

## 2. 書く

- ファイルの冒頭（用途・字数の目安）と末尾（参考文献）は `./priorwork` が書き直す管理ブロック。その間に書く。
- **引く論文は、採用論文の本文確認済のカードから選ぶ。** 要旨のみのカードの論文は引かないか、本文を取得してカードを本文確認済にしてから引く（`priorwork-extract`）。
- **数値と結論の向きを、カードの「主な結果」と照合する。** 数値はカードにあるとおりに書く（四捨五入や単位の言い換えをしない）。「促す／促さない」「増える／減る」がカードと合っているか確かめる。
- 論文は「著者 (年)」で引く（レポートと同じ形。a/b の区別もレポートの参考文献に合わせる）。
- **先行研究の知見と、ユーザーの枠組み・仮説を混ぜない**（AGENTS.md のルール 2）。
- 採用論文の本数などを手で書かない。
- 字数の目安を大きく外れない（15% を超えると `check` が知らせる）。

## 3. 確かめて、読む版を書き出す

```bash
./priorwork check <survey>                       # 派生文書の引用・本文確認・数値・字数も見る
./priorwork export <survey> --derived <名前>     # reports/<survey>.<名前>.html（Word なら --format docx）
```

`check` が派生文書について出すもの:

- ERROR: サーベイの採用論文に無い引用
- WARN: 本文確認済でないカードからの引用、引用した文にあってカードに無い数値
- INFO: 字数が目安から外れている、まだ文章が無い

ERROR を直してから書き出す。WARN の数値は、カードを本文と突き合わせてどちらが正しいかを確かめ、文章かカードを直す。

## 4. 報告

どのファイルに何を書いたか（用途・字数・構成）、推測で決めた点、引いた論文の数、残った WARN、読む版の見方（AGENTS.md「レポートを見せる」。HTML は `reports/<survey>.<名前>.html`）を短く伝える。Git を使うなら、このファイルも `git add reports/<サーベイ名>.*` に入る。
