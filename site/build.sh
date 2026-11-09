#!/bin/sh
# 手引き（docs/guide*.md）・原稿から始める（docs/manuscripts*.md）・インストール（docs/install*.md）・クイックガイド（docs/quickstart*.md）・リファレンス（priorwork/docs/reference*.md。
# パッケージに同梱するので priorwork/ の中にある）を、Pages に出す HTML にする（Octavo の site/build.sh と同じ形）。
#   sh site/build.sh <出力先>   ->  <出力先>/guide/index.html・<出力先>/ja/guide/index.html
# .github/workflows/pages.yml とテストが使う。原稿は Markdown のまま docs/ に置く。
#
# 見出しの id は GitHub と同じ作り方（gfm_auto_identifiers）にする。手引きの中の
# `#3-settings` のようなリンクが、GitHub で読んでも Pages で読んでも同じ所へ飛ぶように。
# 日本語の行の途中の改行は空白にしない（east_asian_line_breaks）。
set -eu
out=${1:?usage: sh site/build.sh <output dir>}
here=$(cd "$(dirname "$0")" && pwd)
repo=$(dirname "$here")

# 色分けはしない（ページの色はダークモードに合わせて切り替わるので、pandoc の固定の色が合わない）
if pandoc --help | grep -q -- '--syntax-highlighting'; then
  nohl=--syntax-highlighting=none
else
  nohl=--no-highlight
fi

page() {  # page <原稿> <出力> <言語> <題> <説明> <目次の見出し> <根> <トップ> <フォルダー名>
  mkdir -p "$(dirname "$2")"
  # `<!-- pages:skip -->` の付いた行（GitHub で読む人への「ページで読んで」）は落とす
  grep -v -- '<!-- pages:skip -->' "$1" | pandoc -f markdown+gfm_auto_identifiers+east_asian_line_breaks -t html5 \
    --template "$here/guide.html" --toc --toc-depth=3 --wrap=none "$nohl" \
    -V lang="$3" -V "$3=1" -M pagetitle="$4" -V description="$5" -V toclabel="$6" \
    -V root="$7" -V home="$8" -V slug="$9" -V "nav_$9=1" -o "$2"
}

page "$repo/docs/guide.md" "$out/guide/index.html" en "Priorwork guide" \
  "How to use Priorwork in VS Code: hand literature reviews for the social sciences and clinical research to your AI agent, then check them from the sidebar." \
  "Contents" "../" "../" guide
page "$repo/docs/guide.ja.md" "$out/ja/guide/index.html" ja "Priorwork 手引き" \
  "Priorwork の手引き。社会科学と臨床研究の先行研究サーベイを AI エージェントに任せ、VS Code のサイドバーで確かめる。" \
  "目次" "../../" "../" guide
page "$repo/docs/manuscripts.md" "$out/manuscripts/index.html" en "Starting from a manuscript" \
  "Hand your manuscript to your AI agent with Priorwork: one report with what to add and where, a check of its citations and comments, and working with Octavo." \
  "Contents" "../" "../" manuscripts
page "$repo/docs/manuscripts.ja.md" "$out/ja/manuscripts/index.html" ja "原稿から始める" \
  "Priorwork で原稿を AI エージェントに渡す。どこに何を足すか、引用の点検、コメントを 1 本のレポートに。Octavo との連携も。" \
  "目次" "../../" "../" manuscripts
page "$repo/docs/install.md" "$out/install/index.html" en "Installing Priorwork" \
  "Installing Priorwork on Linux, macOS, Windows (WSL) and servers over SSH: the VS Code extension prepares Python." \
  "Contents" "../" "../" install
page "$repo/docs/install.ja.md" "$out/ja/install/index.html" ja "Priorwork のインストール" \
  "Linux・macOS・Windows（WSL）・SSH でつなぐサーバーへの Priorwork のインストール。VS Code 拡張機能が Python を用意する。" \
  "目次" "../../" "../" install
page "$repo/docs/quickstart.md" "$out/quickstart/index.html" en "Priorwork quick guide" \
  "From installing Priorwork to your first literature review in six short steps, all in VS Code." \
  "Contents" "../" "../" quickstart
page "$repo/docs/quickstart.ja.md" "$out/ja/quickstart/index.html" ja "Priorwork クイックガイド" \
  "Priorwork を入れてから最初の先行研究サーベイまでの6つの手順。すべて VS Code で。" \
  "目次" "../../" "../" quickstart
page "$repo/priorwork/docs/reference.md" "$out/reference/index.html" en "Priorwork reference" \
  "Every Priorwork command, written for AI agents. The same text comes with Priorwork: ./priorwork docs." \
  "Contents" "../" "../" reference
page "$repo/priorwork/docs/reference.ja.md" "$out/ja/reference/index.html" ja "Priorwork リファレンス" \
  "Priorwork のすべてのコマンド。AI エージェント向け。同じ文章が Priorwork に同梱されている（./priorwork docs）。" \
  "目次" "../../" "../" reference
