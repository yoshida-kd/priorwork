# クイックガイド

> これはクイックガイドの原稿です。読むなら **<https://yoshida-kd.github.io/priorwork/ja/quickstart/>** で。 <!-- pages:skip -->

Priorwork を入れてから最初の先行研究サーベイができるまでを、VS Code での6つの短い手順で説明します。それぞれの詳しい説明は[手引き](https://yoshida-kd.github.io/priorwork/ja/guide/)にあります。

## 1. インストール

1. [VS Code](https://code.visualstudio.com/) と、そこで動く AI エージェント（Claude Code・Antigravity など）を入れます。
2. [Marketplace](https://marketplace.visualstudio.com/items?itemName=yoshida-kd.priorwork) から **Priorwork** 拡張機能を入れます。

Windows では先に WSL の中のフォルダを開き、サーバーでは先に Remote - SSH でつなぎます。

## 2. ワークスペースを作る

空のフォルダを開き、Priorwork のサイドバーの **ワークスペースを作る** を押します。レポートの言語を選びます。Python は自動で用意されます（Python が無ければ uv が入ります）。

続けて歯車（**設定**）を開き、無料の [Semantic Scholar の API キー](https://www.semanticscholar.org/product/api#api-key-form) を入れて **保存して接続を確かめる** を押します。レポートには要旨が入るので、ワークスペースはサイドバーから GitHub の**非公開**リポジトリとして公開します。

## 3. エージェントに頼む

エージェントのチャットで、ふつうの言葉で頼みます:

> 行政需要の変化に対して行政組織がどう人材を確保するか、先行研究を full でまとめて。

サイドバーの **新しいサーベイ → エージェントに任せる** でも依頼文がコピーされます。エージェントは範囲を決め、検索し、選別し、引用をたどり、論文ごとのカードを書き、サーベイの文章を書きます。確かめてもらうために2回止まります。範囲を決めたところと、カードを書く前です。

## 4. Zotero に論文を集める

2回目に止まったとき、エージェントが採用論文の DOI を示します。Zotero の **識別子でアイテムを追加**（魔法の杖）に貼り、PDF を添付してから「続けて」と言います。カードが本文から書かれます（Zotero を使わないなら、そのまま「続けて」）。

## 5. レポートを読む

終わったら、サイドバーのサーベイを右クリック → **レポートを書き出して見る**。VS Code の中で開きます（サーバーでも）。

## 6. 確かめて直す

サイドバーのサーベイの下に、採用・保留・除外の論文が並びます。押すと要旨とエージェントの理由が出ます。**I**・**M**・**X** で採否を覆し、カードはそのページで直します（**Ctrl+S** で保存）。「続けて」と言えば、エージェントはあなたの直しに従います。

## 7. このあとは

- [手引き](https://yoshida-kd.github.io/priorwork/ja/guide/): すべての詳しい説明。Zotero、検査。
- [原稿から始める](https://yoshida-kd.github.io/priorwork/ja/manuscripts/): 自分の原稿から、Octavo と一緒に。
- [インストール](https://yoshida-kd.github.io/priorwork/ja/install/): Windows やサーバーで使うとき。
- [リファレンス](https://yoshida-kd.github.io/priorwork/ja/reference/): エージェント向けの、すべてのコマンド。
