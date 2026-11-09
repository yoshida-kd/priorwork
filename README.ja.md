# Priorwork

**先行研究サーベイを AI エージェントに任せて、確かめる — ターミナルは不要**

[![tests](https://github.com/yoshida-kd/priorwork/actions/workflows/tests.yml/badge.svg)](https://github.com/yoshida-kd/priorwork/actions/workflows/tests.yml)

[English README](https://github.com/yoshida-kd/priorwork/blob/main/README.md)

Priorwork（prior work ＝ 先行研究）は、社会科学と臨床研究のテーマ別の先行研究サーベイを、AI エージェント（Claude Code・Antigravity など）に任せて作るための道具。普通の言葉で頼むと、エージェントが範囲の設定・検索・選別・引用の追跡・論文カードの記入・文章・検査・書き出しまで進める。あなたはレポートを読み、VS Code のサイドバーで確かめて直す。

```
範囲 → 検索 → 選別 → 引用をたどる → 論文カード → 文章 → 検査と書き出し
```

## できること

- **判断には必ず理由が残る。** エージェントは採否ごとに理由を記録し、範囲をレポートに書き込む。論文ごとのページでキー 1 つで覆せ、エージェントはあなたの判断を覆さない。
- **覚えるのはリポジトリ。** 候補・採否・検索履歴は JSON に残るので、会話をまたいで続けられる。
- **確かめられるカード。** 採用論文ごとのカードは要旨か本文に書かれていることだけで書かれ、どちらで確かめたかとページが残る。
- **でっち上げを検出する。** 文章中の「著者 (年)」は登録済みの論文に、DOI はその論文に対応していなければならない。撤回された論文はエラーになる。
- **いくつもの文献の出どころ。** Semantic Scholar と OpenAlex。医学のサーベイでは PubMed も使い、MEDLINE の判定、臨床上の問いと効果量のカード、PMC の公開された本文が加わる。
- **自分の原稿から。** 書きかけでも出来上がりでも、原稿を渡すと 1 本のレポートになる。どこに何を足すか、引用の点検、足りない先行研究、論の組み立てへのコメント。原稿は書き換えない。
- **Zotero と Octavo。** Zotero のコレクションをサーベイに結び付けて、論文を集め、PDF を読む。[Octavo](https://github.com/yoshida-kd/octavo) のプロジェクトへ、その `.bib` のキーで文章を渡す。
- **AI の API キーは要らない。** 拡張機能が自分で AI のサービスを呼ぶことはない。AI の手助けは、ふだん使っているエージェントを通してだけ入る。

## インストール

[VS Code の拡張機能](https://marketplace.visualstudio.com/items?itemName=yoshida-kd.priorwork)を入れ、空のフォルダを開いて、Priorwork のサイドバーの **ワークスペースを作る** を押す。Python は拡張機能が用意する。Windows とサーバーは [Priorwork のインストール](https://yoshida-kd.github.io/priorwork/ja/install/)を参照。

## 始め方

ワークスペースで、エージェントに頼む。

> 最低賃金が雇用に与える影響の先行研究を full でまとめて

サイドバーの **新しいサーベイ → エージェントに任せる** でもよい。エージェントは、範囲の確認と Zotero への論文の収集のために止まる（止まらないようにも頼める）。あとはレポートを読み、サイドバーで直す。

## 手引き

- [クイックガイド](https://yoshida-kd.github.io/priorwork/ja/quickstart/) — インストールから最初のサーベイまで、6つの手順で
- [Priorwork のインストール](https://yoshida-kd.github.io/priorwork/ja/install/) — 手元のコンピューター、Windows、サーバー
- [手引き](https://yoshida-kd.github.io/priorwork/ja/guide/) — VS Code での使い方
- [原稿から始める](https://yoshida-kd.github.io/priorwork/ja/manuscripts/) — 自分の原稿から、Octavo と一緒に
- [リファレンス](https://yoshida-kd.github.io/priorwork/ja/reference/) — すべてのコマンド。AI エージェント向け（`./priorwork docs` でも読める）

## 貢献とライセンス

Issue や Pull Request を歓迎する。詳しくは [CONTRIBUTING.md](https://github.com/yoshida-kd/priorwork/blob/main/CONTRIBUTING.md) を参照。MIT ライセンス。
