---
name: priorwork-audit
description: >-
  Audits a literature survey written by another AI model: checks each paper card against the full text,
  the direction of every citation in the text, the separation of the literature from the user's own
  hypotheses, mechanical exclusions in screening and the SSCI status; fixes what is wrong and records the
  audit with `./priorwork audit`. Use when asked to audit, review or double-check a survey that a different
  model wrote. Never use it on a survey you wrote yourself.
---

# 別のモデルが書いたサーベイを監査する

ルールは [AGENTS.md](../../../AGENTS.md) に従う。サーベイは、書いたモデルと別のモデルが監査して初めて 1 回分になる（AGENTS.md「監査」）。

## 0. 監査してよいか確かめる

```bash
./priorwork audit <survey>        # 書いたモデルと、これまでの監査
```

「書いたモデル」に自分（自分のモデル名）があれば、監査しない。ユーザーに「このサーベイは私が書いたので、別のモデルに監査を頼んでください」と伝えて終える。記録が無ければ、ユーザーに書いたモデルを確かめる。

## 1. 機械的な検査

```bash
./priorwork check <survey>
```

ERROR と、カード・まとめの節・採用数・Zotero の WARN を控える。直すのは 2〜5 で、本文と突き合わせてから。

## 2. カードを本文と突き合わせる（いちばん大事）

採用論文すべてについて、1 本ずつ行う。

```bash
./priorwork card <survey> <番号>
./priorwork fulltext <survey> <番号>    # 本文を取得し、テキストの場所を出す
```

- 「本文確認済」のカードは、本文を開いて次を確かめる: データ・サンプル数・期間、識別戦略（実際に使った手法か）、主な結果の数値と**向き**、添えたページ。
- 本文に無い数値・手法・ページは直すか消す。本文を取得できない論文で「本文確認済」なら「要旨のみ」に下げる。
- カードがレポートの言語で書かれていなければ書き直す。
- 直すときは `./priorwork card <survey> <番号> --set …` か、カードの記入欄を書き換える。

数が多いときも抜き取りにせず、全件を見る。時間がかかりすぎるときは、どこまで見たかを報告で伝え、続きは次の監査で行う（その場合 `--note` に範囲を書く）。

## 3. 文章を確かめる

レポートの背景から「本研究の仮説と示唆」までの各節で:

- **引用の向き**: 「X (年) は〜を示した」が、その論文のカードの主な結果と同じ向きか。逆なら直す。
- **先行研究と本研究の仮説の混同**: ユーザーの分類・仮説・分析軸が、先行研究の合意や確立した事実のように書かれていないか。そうなら「本研究の仮説と示唆」に移し、先行研究のどの知見に基づくかを著者 (年) で示す。
- **手で書いた件数**: 採用数などが付録の記録と食い違っていないか（食い違えば消す）。
- 採用していない論文・登録の無い論文を引いていないか（`check` の ERROR）。

## 4. 選別を確かめる

```bash
./priorwork list <survey> --status excluded --abstract
```

- 同じ文の理由で大量に除外されていないか（付録の「除外の理由」でも分かる）。
- RQ に直結する論文が「テーマ外」で落ちていないか。落ちていれば、理由を付けて採用か保留に戻す（`./priorwork include <survey> N --reason "監査: …"`）。採用に戻した論文は、カードを書く（`priorwork-extract`）。
- ユーザーが下した採否は変えない（`./priorwork list` の履歴で分かる）。

## 5. SSCI の判定を確かめる

`✅ SSCI` の採用論文は、誌名だけでなく ISSN と出版社が収録誌と合っているか（同じ誌名の別誌がある）。`./priorwork journal "<ISSN>"` で確かめる。

## 6. 記録して報告する

```bash
./priorwork check <survey>
./priorwork export <survey>
./priorwork audit <survey> --by "<自分のモデル名>" --note "<確かめた範囲と直したこと（1 行）>"
```

報告では、見つけた問題を種類ごとに（カードの誤り・引用の向き・仮説の混同・選別・SSCI）件数と代表例で伝え、直したもの・直せなかったものを分ける。
