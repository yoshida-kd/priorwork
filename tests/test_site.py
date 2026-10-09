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


def test_the_two_guides_have_the_same_sections():
    assert headings(REPO / "docs" / "guide.md") == headings(REPO / "docs" / "guide.ja.md")


def test_the_pages_name_only_prior_work():
    for path in [*(REPO / "site").rglob("*.html"), REPO / "site" / "style.css"]:   # 借りた見た目に名前が残っていないか
        assert "octavo" not in path.read_text(encoding="utf-8").lower(), path


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc is not installed")
def test_the_site_builds_and_its_links_resolve(tmp_path):
    shutil.copytree(REPO / "site", tmp_path, dirs_exist_ok=True)
    subprocess.run(["sh", str(REPO / "site" / "build.sh"), str(tmp_path)], check=True)
    for idx, guide in (("index.html", "guide/index.html"), ("ja/index.html", "ja/guide/index.html")):
        page = (tmp_path / guide).read_text(encoding="utf-8")
        assert "pages:skip" not in page and "<nav class=\"toc" in page
        ids = set(re.findall(r'id="([^"]+)"', page)) | {"install"}
        for html in (tmp_path / idx, tmp_path / guide):
            for anchor in re.findall(r'href="(?:guide/)?#([^"]+)"', html.read_text(encoding="utf-8")):
                assert anchor in ids, (html.name, anchor)
