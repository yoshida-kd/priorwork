"""ウェブページ（site/）と手引き（docs/guide*.md）。Pages に出す前に、組めるか・リンクが切れていないかを見る。"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def headings(path: Path):
    text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
    return [len(m.group(1)) for m in re.finditer(r"^(#{2,3}) ", text, re.M)]


PAIRS = [
    (REPO / "docs" / "guide.md", REPO / "docs" / "guide.ja.md"),
    (REPO / "docs" / "quickstart.md", REPO / "docs" / "quickstart.ja.md"),
    (REPO / "docs" / "install.md", REPO / "docs" / "install.ja.md"),
    (REPO / "docs" / "manuscripts.md", REPO / "docs" / "manuscripts.ja.md"),
    (REPO / "priorwork" / "docs" / "reference.md", REPO / "priorwork" / "docs" / "reference.ja.md"),
]


def test_the_two_guides_have_the_same_sections():
    for en, ja in PAIRS:
        assert headings(en) == headings(ja), en.name


def test_the_guide_is_for_people_in_vs_code():
    """手引きにはコマンドを書かない（エージェント向けのリファレンスにある）。"""
    for path in [REPO / "docs" / f"{n}{s}.md" for n in ("guide", "install", "manuscripts") for s in ("", ".ja")]:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"^```bash", text, re.M), path.name
        assert not re.search(r"\./priorwork [a-z]", text), path.name


def test_the_reference_ships_and_docs_reads_it(capsys):
    from priorwork import cli
    cli.main(["docs", "8", "--lang", "en"])
    out = capsys.readouterr().out
    assert out.startswith("## 8. Zotero") and "## 9." not in out
    cli.main(["docs", "--search", "snowball", "--lang", "ja"])
    assert "snowball" in capsys.readouterr().out
    for lang in ("en", "ja"):
        assert "./priorwork docs" in (REPO / "priorwork" / "assets" / lang / "AGENTS.md").read_text(encoding="utf-8")


def test_the_pages_name_only_prior_work():
    for path in [*(REPO / "site").rglob("*.html"), REPO / "site" / "style.css"]:   # 借りた見た目に名前が残っていないか
        assert "octavo" not in path.read_text(encoding="utf-8").lower(), path


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc is not installed")
def test_the_site_builds_and_its_links_resolve(tmp_path):
    shutil.copytree(REPO / "site", tmp_path, dirs_exist_ok=True)
    subprocess.run(["sh", str(REPO / "site" / "build.sh"), str(tmp_path)], check=True)
    for idx, guide in (("index.html", "guide/index.html"), ("ja/index.html", "ja/guide/index.html"),
                       ("index.html", "quickstart/index.html"), ("ja/index.html", "ja/quickstart/index.html"),
                       ("index.html", "reference/index.html"), ("ja/index.html", "ja/reference/index.html"),
                       ("index.html", "install/index.html"), ("ja/index.html", "ja/install/index.html"),
                       ("index.html", "manuscripts/index.html"), ("ja/index.html", "ja/manuscripts/index.html")):
        page = (tmp_path / guide).read_text(encoding="utf-8")
        assert "pages:skip" not in page and "<nav class=\"toc" in page
        ids = set(re.findall(r'id="([^"]+)"', page)) | {"install"}
        for html in (tmp_path / idx, tmp_path / guide):
            for anchor in re.findall(r'href="(?:guide/)?#([^"]+)"', html.read_text(encoding="utf-8")):
                assert anchor in ids, (html.name, anchor)


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc is not installed")
def test_every_link_between_the_pages_resolves(tmp_path):
    """ページどうしのリンク（パスと #見出し）が、組んだサイトの中にある。"""
    shutil.copytree(REPO / "site", tmp_path, dirs_exist_ok=True)
    subprocess.run(["sh", str(REPO / "site" / "build.sh"), str(tmp_path)], check=True)
    base = "https://yoshida-kd.github.io/priorwork/"
    for page in tmp_path.rglob("index.html"):
        for href in re.findall(r'href="([^"]+)"', page.read_text(encoding="utf-8")):
            if href.startswith(base):
                target, anchor = (tmp_path / href[len(base):].split("#")[0]), href.partition("#")[2]
            elif href.startswith(("http", "mailto:")) or href.startswith("#"):
                continue
            else:
                target, anchor = (page.parent / href.split("#")[0]), href.partition("#")[2]
            if target.is_dir():
                target = target / "index.html"
            if target.suffix not in (".html",):
                assert target.exists(), (page, href)
                continue
            assert target.exists(), (page, href)
            if anchor:
                from urllib.parse import unquote
                assert f'id="{unquote(anchor)}"' in target.read_text(encoding="utf-8"), (page, href)
