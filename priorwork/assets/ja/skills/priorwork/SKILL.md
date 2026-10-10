---
name: priorwork
description: >-
  The entry point of Priorwork. Makes or continues a social-science literature survey end to end with
  `./priorwork` (scope, searches, screening, citation chasing, paper cards, text, check, export) without
  waiting between steps. Use whenever the user asks, in any words or language, for a literature survey,
  literature review or prior work on a topic, for the literature behind their own manuscript, or to
  continue, finish or improve an existing survey.
---

# サーベイを作る・続ける（入口）

ルールは [AGENTS.md](../../../AGENTS.md) に従う。ユーザーはスキル名を打たずに頼むので、依頼の言葉から次のどれかを判断する。

- 新しいテーマ（「〇〇について先行研究をまとめて」）→ 1 から
- 自分の原稿の補強（「分析はできているので、イントロ・先行研究・仮説を書いて」「この論文の先行研究を固めて」）→ スキル `priorwork-manuscript`。原稿から作ったサーベイ（`./priorwork status <survey>` に「原稿:」と出る）を続けるときも同じ
- 既存のサーベイの続き（「続けて」「仕上げて」）→ 2 から
- 一部だけ（「もっと検索して」「カードを埋めて」「検査して」）→ 該当する工程のスキルだけ

既定では途中で止まらずに最後まで進める（AGENTS.md「頼まれ方と進め方」）。ユーザーが相談しながら進めたいと言ったときだけ、範囲と採否で答えを待つ。

## 1. 新しいサーベイ

`./priorwork status` で同じテーマのサーベイが無いか確かめ、無ければ `priorwork-new` の手順で範囲を決めて作成し、検索する。

## 2. 状態を見て、次の工程へ

```bash
./priorwork status <survey>
```

「次にやること」を上から片付ける。目安の順序:

1. **検索**（`priorwork-new` の 2）: 「検索を足す」と出ている間は、サブテーマを変えて検索を足す。
2. **選別**（`priorwork-screen`）: 候補をすべて採用・除外・保留に分ける。
3. **引用をたどる**（`priorwork-snowball`）: full なら必ず。新しい候補が出たら 2 に戻る。
4. **カードの記入**（`priorwork-extract`）: 採用論文すべて。
5. **文章**: 下の 3。
6. **検査と書き出し**（`priorwork-check`）: ERROR が 0 になるまで直し、HTML を書き出す。

工程が終わるたびに `./priorwork status <survey>` を見直す。長い作業になるので、工程の区切りで「いまどこまで進んだか」を一行だけ伝えてよい（答えは待たない）。

## 3. 文章を書く

原稿から作ったサーベイは、`priorwork-manuscript` の 5 で書く。それ以外は、レポートの 1 章（背景）と 4〜7 章（理論の潮流・実証手法の変遷・合意と論争・まとめ）を、カードをもとに書く。

- 引用するのは、サーベイに採用した論文だけ。著者 (年) の表記は 8 章の参照文献に合わせる。
- カードに書かれていないこと（推定値・期間など）を文章に足さない。
- quick なら 4〜7 章は短い概観でよい。full なら論争点・研究の空白まで書く。

## 4. 終わったら報告する

`priorwork-check` を通して書き出したら、次を短く伝える。

- 検索のクエリ数・候補数・採用数・除外の主な理由
- 範囲（RQ・期間・基準・深さ）のうち、依頼に無く自分で決めたもの
- 残った WARN と「下書き」の理由（あれば）
- レポートの見方（AGENTS.md「レポートを見せる」）
- 採否やカードは、サイドバーで直せば次の作業でそれに従うこと

Git は操作しない（AGENTS.md「基本の考え方」）。コミットや push を頼まれていなければ、報告の最後に「変更をコミットしてよいか」と聞くだけにする。
