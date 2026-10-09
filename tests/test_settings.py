"""ワークスペースの設定（`priorwork settings`）。.env の書き換えと SSCI リストの取り込み。"""

import pytest

from priorwork import settings, ssci


def test_update_keeps_comments_and_hides_secrets(tmp_path):
    (tmp_path / ".env").write_text("# my notes\nSEMANTIC_SCHOLAR_API_KEY=old\nOTHER=1\n# ZOTERO_DATA_DIR=\n")
    changed = settings.update(tmp_path, {"SEMANTIC_SCHOLAR_API_KEY": "new key", "ZOTERO_DATA_DIR": r"C:\Zotero",
                                         "ZOTERO_API_KEY": None, "OPENALEX_MAILTO": "me@example.com"})
    assert changed == ["SEMANTIC_SCHOLAR_API_KEY", "ZOTERO_DATA_DIR", "OPENALEX_MAILTO"]
    text = (tmp_path / ".env").read_text()
    assert text == ("# my notes\nSEMANTIC_SCHOLAR_API_KEY='new key'\nOTHER=1\nZOTERO_DATA_DIR=C:\\Zotero\n"
                    "OPENALEX_MAILTO=me@example.com\n")
    assert settings.read_env(tmp_path)["SEMANTIC_SCHOLAR_API_KEY"] == "new key"
    items = {i["key"]: i for i in settings.status(tmp_path)["items"]}
    assert items["SEMANTIC_SCHOLAR_API_KEY"] == {"key": "SEMANTIC_SCHOLAR_API_KEY", "secret": True, "set": True, "value": ""}
    assert items["OPENALEX_MAILTO"]["value"] == "me@example.com" and not items["ZOTERO_API_KEY"]["set"]

    settings.update(tmp_path, {"SEMANTIC_SCHOLAR_API_KEY": ""})        # 空文字で消す
    assert "SEMANTIC_SCHOLAR_API_KEY=\n" in (tmp_path / ".env").read_text()
    assert settings.update(tmp_path, {"OPENALEX_MAILTO": "me@example.com"}) == []


def test_update_creates_env_from_the_example_and_rejects_bad_input(tmp_path):
    settings.update(tmp_path, {"ZOTERO_USER_ID": "123"})
    text = (tmp_path / ".env").read_text()
    assert "ZOTERO_USER_ID=123\n" in text and "SEMANTIC_SCHOLAR_API_KEY=" in text and text.count("ZOTERO_USER_ID") == 1
    with pytest.raises(settings.SettingsError):
        settings.update(tmp_path, {"PATH": "x"})
    with pytest.raises(settings.SettingsError):
        settings.update(tmp_path, {"ZOTERO_USER_ID": "1\n2"})


def test_import_ssci(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", lambda root: root / ".priorwork" / "data")
    good = tmp_path / "Social Sciences Citation Index (SSCI).csv"
    good.write_text("Journal title,ISSN,eISSN\nJOURNAL OF POLITICS,0022-3816,1468-2508\n")
    got = settings.import_ssci(tmp_path, good)
    assert got == {"file": "ssci_journals.csv", "journals": 1}
    assert (tmp_path / ".priorwork" / "data" / "ssci_journals.csv").read_text() == good.read_text()
    assert ssci._list_cache is None
    bad = tmp_path / "other.csv"
    bad.write_text("name,value\na,1\n")
    with pytest.raises(settings.SettingsError):
        settings.import_ssci(tmp_path, bad)
