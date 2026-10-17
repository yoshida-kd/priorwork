"""原稿をテキストにする（`priorwork read`）: 形式を問わずに読める。"""
import zipfile

from priorwork import cli, manuscript


def _docx(path):
    xml = ('<?xml version="1.0"?><w:document xmlns:w="w"><w:body>'
           '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Introduction</w:t></w:r></w:p>'
           '<w:p><w:r><w:t xml:space="preserve">Wages </w:t></w:r><w:r><w:t>&amp; jobs</w:t></w:r></w:p>'
           '</w:body></w:document>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)


def test_reads_each_format(tmp_path):
    (tmp_path / "paper.qmd").write_text("# Results\n\nSee Card (1994).\n", encoding="utf-8")
    (tmp_path / "paper.html").write_text(
        "<html><head><title>T</title><style>p{}</style></head><body><h2>Data</h2>"
        "<script>var big = 1;</script><p>Panel of <em>counties</em></p></body></html>", encoding="utf-8")
    _docx(tmp_path / "paper.docx")
    (tmp_path / "fig.png").write_bytes(b"\x89PNG")
    (tmp_path / ".quarto").mkdir()
    (tmp_path / ".quarto" / "x.md").write_text("hidden")
    got = {f.name: text for f, text in manuscript.read(tmp_path)}
    assert set(got) == {"paper.qmd", "paper.html", "paper.docx", "fig.png"}
    assert "Card (1994)" in got["paper.qmd"]
    assert "## Data" in got["paper.html"] and "Panel of counties" in got["paper.html"] and "big" not in got["paper.html"]
    assert got["paper.docx"].splitlines()[:2] == ["# Introduction", "Wages & jobs"]
    assert got["fig.png"] == ""


def test_the_read_command(tmp_path, capsys):
    (tmp_path / "paper.md").write_text("Hello\n", encoding="utf-8")
    cli.main(["read", str(tmp_path)])
    assert capsys.readouterr().out == "=== paper.md ===\nHello\n"
    cli.main(["read", str(tmp_path / "paper.md"), "--out", str(tmp_path / "out.txt")])
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "=== paper.md ===\nHello\n"
