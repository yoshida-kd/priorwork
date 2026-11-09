# Priorwork のインストール

> これはインストールの手引きの原稿。読むなら **<https://yoshida-kd.github.io/priorwork/ja/install/>** で。 <!-- pages:skip -->

VS Code、Priorwork の拡張機能、VS Code で動いて `AGENTS.md` を読む AI エージェント（Claude Code・Antigravity など）を使う。Python は、ワークスペースを作るときに拡張機能が用意する。

| 使っているもの | 読むところ |
| :--- | :--- |
| Linux か Mac | [手元のコンピューター](#1-手元のコンピューター) |
| Windows | [Windows](#2-windows)（WSL の中で） |
| SSH でつなぐサーバー | [SSH でつなぐサーバー](#3-ssh-でつなぐサーバー) |

## 1. 手元のコンピューター

1. [VS Code](https://code.visualstudio.com/) を入れる。
2. 拡張機能のビューで **Priorwork** を探して入れる（[Marketplace](https://marketplace.visualstudio.com/items?itemName=yoshida-kd.priorwork)）。
3. アクティビティバーに Priorwork のアイコンが出る。空のフォルダを開いて **ワークスペースを作る** を押す（[この先](https://yoshida-kd.github.io/priorwork/ja/guide/#2-ワークスペースを作る)）。

拡張機能は Python 3.10 以上を探す。無ければ uv を入れるかを聞き、uv が Python を取ってくる。

## 2. Windows

WSL（Ubuntu）を入れ、VS Code の **WSL** 拡張機能で WSL の中のフォルダを開いてから、[上の手順](#1-手元のコンピューター)を行う。Windows で直接使うことは確かめていない。

## 3. SSH でつなぐサーバー

VS Code の **Remote - SSH** 拡張機能でつなぎ、サーバーの上で[上の手順](#1-手元のコンピューター)を行う。拡張機能・Python・ワークスペースはサーバー側に置かれる。

## 4. キーとリスト

どれも任意で、**設定**（サイドバーの歯車）から入れる。[手引き](https://yoshida-kd.github.io/priorwork/ja/guide/#7-設定)を参照。

| もの | 何のため |
| :--- | :--- |
| 無料の [Semantic Scholar の API キー](https://www.semanticscholar.org/product/api#api-key-form) | 推奨。無いと検索がレート制限で失敗しやすい |
| Zotero | 採用論文を集める、手元の PDF から本文を読む |
| Clarivate の [Master Journal List](https://mjl.clarivate.com/) の SSCI リスト | SSCI 収録誌を確定する |
| 医学のサーベイなら、無料の NCBI キーと SCIE リスト | PubMed を速くする、✅ SCIE を足す |

## 5. 更新

拡張機能は Marketplace から更新される。エンジンの版は、更新するまでワークスペースごとに固定される（[手順](https://yoshida-kd.github.io/priorwork/ja/guide/#10-エンジンを更新する)）。
