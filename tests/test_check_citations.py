import pytest

from priorwork.check import ERROR, INFO, WARN, check_survey, find_citations
from priorwork.survey import EXCLUDED, INCLUDED, Survey


def pairs(text):
    return {(c.name, c.year, c.suffix) for c in find_citations(text)}


@pytest.mark.parametrize("text, expected", [
    ("(Dell, 2010; Fake et al., 2019)", {("dell", 2010, ""), ("fake", 2019, "")}),
    ("(Dell 2010; Fake 2019)", {("dell", 2010, ""), ("fake", 2019, "")}),
    ("(e.g., Dell 2010, p. 3; Acemoglu et al., 2001a, 2005)",
     {("dell", 2010, ""), ("acemoglu", 2001, "a"), ("acemoglu", 2005, "")}),
    ("Acemoglu et al. (2001, 2005)", {("acemoglu", 2001, ""), ("acemoglu", 2005, "")}),
    ("Acemoglu, Johnson and Robinson (2001a)", {("acemoglu", 2001, "a")}),
    ("Dell (2010, p. 5)", {("dell", 2010, "")}),
    ("Dell (2010) は（Fake, 2019；Card, 1994）と異なり", {("dell", 2010, ""), ("fake", 2019, ""), ("card", 1994, "")}),
    ("Acemoglu ら (2001)", {("acemoglu", 2001, "")}),
    ("IV (2SLS) で推定。In 2010 (Table 3)", set()),
])
def test_citation_forms(text, expected):
    assert pairs(text) == expected


def test_organizations_and_acronyms_are_marked():
    marked = {c.text: c.is_non_author for c in find_citations("World Bank (2010) と OECD (2019)、Dell (2010)")}
    assert marked == {"Bank (2010)": True, "OECD (2019)": True, "Dell (2010)": False}


def write_prose(s, prose):
    md = s.md_path.read_text().replace("## 1. 研究の背景と中心的な論点\n", f"## 1. 研究の背景と中心的な論点\n{prose}\n")
    s.md_path.write_text(md)


@pytest.fixture
def s(s2_record):
    s = Survey.create("t", "cite", {})
    s.upsert(s2_record(doi="10.1/dell", title="The persistent effects of mining", authors=("Melissa Dell",), year=2010),
             "search", status=INCLUDED)
    s.save()
    s.render()
    return s


def messages(s, level):
    return [m for lvl, m in check_survey(s) if lvl == level]


def test_fabricated_citation_in_a_group_is_an_error(s):
    write_prose(s, "先行研究（Dell, 2010; Fake et al., 2019）")
    errors = messages(s, ERROR)
    assert any("Fake et al. (2019)" in m for m in errors)
    assert not any("Dell" in m for m in errors)


def test_organizations_are_info_and_ignore_comment_silences(s):
    write_prose(s, "World Bank (2010) と Smith (2015)\n<!-- lit:ignore-citation Smith (2015) -->")
    assert not any("Smith" in m or "Bank" in m for m in messages(s, ERROR))
    assert any("Bank (2010)" in m for m in messages(s, INFO))


def test_any_included_paper_satisfies_a_shared_author_year(s, s2_record):
    s.upsert(s2_record(doi="10.1/dell2", title="Another Dell paper from 2010", authors=("Melissa Dell",), year=2010),
             "search", status=EXCLUDED, reason="x")
    s.save()
    s.render()
    write_prose(s, "Dell (2010)")
    assert not any("Dell" in m for m in messages(s, WARN) + messages(s, ERROR))


def test_letter_suffixes_are_checked(s, s2_record):
    s.upsert(s2_record(doi="10.1/dell2", title="Another Dell paper from 2010", authors=("Melissa Dell",), year=2010),
             "search", status=INCLUDED)
    s.save()
    s.render()
    write_prose(s, "Dell (2010) と Dell (2010b)、Dell (2010c)")
    warns = messages(s, WARN)
    assert any("「Dell (2010)」は採用論文の複数に当たります" in m for m in warns)
    assert any("「Dell (2010c)」" in m for m in warns)
    assert not any("「Dell (2010b)」" in m for m in warns)


def test_suffix_without_ambiguity_is_warned(s):
    write_prose(s, "Dell (2010a)")
    assert any("a/b は不要" in m for m in messages(s, WARN))
