"""
Literature API client.

役割分担:
- Semantic Scholar: 検索・論文取得・引用関係（主）
- OpenAlex: S2 の結果を DOI で照合して書誌情報（誌名・ISSN・巻号）を補正、
  S2 に無い DOI の取得、被引用数順の引用関係
- PubMed（医学のサーベイ）: 検索と、PMID・PMC ID・出版の種類・MeSH・MEDLINE 索引の有無・撤回。
  Europe PMC: PMC の本文（XML）

S2 は定番論文ほど DOI の誤り（別論文や SSRN 版の DOI）や ISSN の欠落があるため、
Zotero に取り込む DOI と SSCI 照合に使う ISSN は OpenAlex 側の値を優先する。
どちらのソースから取得しても、同じ形の正規化済み dict（`_record` 参照）を返す。
"""

import hashlib
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import quote, urlencode

import requests

from . import ssci
from .i18n import t
from .ssci import classify_paper
from .workspace import ROOT


def _load_dotenv():
    """Load <workspace>/.env regardless of the current working directory."""
    path = ROOT / ".env"
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(path)
        return
    except ImportError:
        pass
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("'\"")
        if k and v and k not in os.environ:
            os.environ[k] = v


_load_dotenv()

S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"
OPENALEX_BASE_URL = "https://api.openalex.org"

S2_PAPER_FIELDS = (
    "paperId,title,abstract,authors,year,venue,publicationVenue,journal,citationCount,referenceCount,"
    "openAccessPdf,tldr,externalIds,url,fieldsOfStudy,s2FieldsOfStudy,publicationTypes"
)
# bulk 検索は tldr を返せない
S2_BULK_FIELDS = S2_PAPER_FIELDS.replace(",tldr", "")
S2_LINKED_FIELDS = "paperId,title,authors,year,venue,publicationVenue,journal,citationCount,externalIds,publicationTypes"
CROSSREF_BASE_URL = "https://api.crossref.org"
NCBI_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPEPMC_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
PUBMED_BATCH = 100
# 研究の論文でない PubMed の出版の種類。検索では落とす（--include-preprints で残す）
PUBMED_NOT_RESEARCH = {"Editorial", "Letter", "Comment", "News", "Newspaper Article", "Published Erratum",
                       "Retraction of Publication", "Expression of Concern", "Biography", "Autobiography", "Portrait",
                       "Interview", "Lecture", "Personal Narrative", "Patient Education Handout", "Congress"}
CROSSREF_BATCH = 20
OPENALEX_SELECT = (
    "id,doi,title,display_name,publication_year,type,authorships,primary_location,biblio,"
    "cited_by_count,referenced_works_count,abstract_inverted_index,open_access,topics,is_retracted"
)

OPENALEX_BATCH = 50
# 雑誌版を題名で探す問い合わせは 1 件ずつなので、1 回の検索・照合で引く件数に上限を設ける
MAX_VERSION_LOOKUPS = 10
RETRY_STATUSES = {429, 500, 502, 503, 504}
BACKOFF_DELAYS = [5, 10, 20, 40, 60]

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "priorwork"
CACHE_TTL_SEC = float(os.environ.get("PRIORWORK_CACHE_TTL_DAYS") or 7) * 86400


def _error_detail(resp: requests.Response) -> str:
    """エラー本文を 1 行に要約する（HTML のエラーページをそのまま出さない）。"""
    text = resp.text or ""
    if "html" in resp.headers.get("Content-Type", "") or text.lstrip().startswith("<"):
        title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
        return re.sub(r"\s+", " ", title.group(1)).strip() if title else t("an HTML error page")
    return re.sub(r"\s+", " ", text)[:200].strip()


_BOOL_WORDS = {"AND": "+", "OR": "|", "NOT": "-"}


def journal_key(name: str) -> str:
    """誌名を比べるための形: 小文字、先頭の The、& と and、記号と空白の違いを無視する。"""
    s = html.unescape(name or "").lower().replace("&", " and ")
    s = re.sub(r"[^\w]+", " ", s).strip()
    return re.sub(r"^the ", "", s)


# 誌の OpenAlex source ID（/sources/issn:… で確かめたもの）。よく使う誌は名前から引く問い合わせを省く
KNOWN_SOURCES = {journal_key(name): sid for name, sid in (
    ("Journal of Public Administration Research and Theory", "S169433491"),
    ("American Political Science Review", "S176007004"),
    ("American Journal of Political Science", "S90314269"),
    ("British Journal of Political Science", "S95691132"),
    ("Public Administration Review", "S76877748"),
    ("Public Administration", "S201221823"),
)}

ISSN_RE = re.compile(r"^\d{4}-?\d{3}[\dX]$", re.IGNORECASE)

# プレプリント・WP の DOI（OSF 系・SSRN・arXiv・NBER・Research Square・Preprints.org）
# bioRxiv・medRxiv は 10.1101/ の後ろが数字（Genome Research など同じ出版社の雑誌は 10.1101/gr.… と文字が続く）
PREPRINT_DOI_RE = re.compile(
    r"^10\.(?:3121\d|3122\d|3123\d|31124)/|^10\.2139/ssrn|^10\.48550/arxiv|^10\.3386/w\d|"
    r"^10\.21203/rs\.|^10\.20944/preprints|^10\.1101/\d", re.IGNORECASE)


def preprint_doi(doi: str) -> bool:
    return bool(PREPRINT_DOI_RE.search(doi or ""))


def openalex_years(year: Optional[str]) -> str:
    """S2 の年の指定（2019 / 2013-2022 / 2013- / -2022）を OpenAlex の filter にする。"""
    m = re.fullmatch(r"\s*(\d{4})?\s*(-)?\s*(\d{4})?\s*", year or "")
    if not m or not (m.group(1) or m.group(3)):
        return ""
    start, dash, end = m.groups()
    if not dash:
        return f"publication_year:{start or end}"
    if start and end:
        return f"publication_year:{start}-{end}"
    return f"publication_year:>{int(start) - 1}" if start else f"publication_year:<{int(end) + 1}"


def openalex_query(query: str) -> str:
    """検索語を OpenAlex の .search の形にする: + / | / -（bulk の書き方）を AND / OR / NOT に、
    カンマ（filter の区切り）は空白に。引用符の中は変えない。"""
    parts = re.split(r'("[^"]*")', bulk_query(query))
    for i in range(0, len(parts), 2):
        p = parts[i].replace(",", " ")
        p = re.sub(r"\s*\|\s*", " OR ", p)
        p = re.sub(r"\s*\+\s*", " AND ", p)
        parts[i] = re.sub(r"(^|\s)-(?=[\w(\"])", r"\1NOT ", p)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def pubmed_dates(year: Optional[str]) -> Dict[str, str]:
    """S2 の年の指定を esearch の mindate / maxdate にする（片方だけは指定できない）。"""
    m = re.fullmatch(r"\s*(\d{4})?\s*(-)?\s*(\d{4})?\s*", year or "")
    if not m or not (m.group(1) or m.group(3)):
        return {}
    start, dash, end = m.groups()
    low, high = (start or "1000", end or "3000") if dash else (start or end, start or end)
    return {"datetype": "pdat", "mindate": low, "maxdate": high}


def pubmed_term(query: str, journals: Sequence[str] = ()) -> str:
    """検索語を PubMed の形にする: bulk の + / | / - を AND / OR / NOT に。[tiab] などのタグや MeSH はそのまま通る。"""
    term = openalex_query(query)
    if journals:
        names = [f"{j.strip()}[is]" if ISSN_RE.match(j.strip()) else f'"{j.strip()}"[ta]' for j in journals]
        term = f"({term}) AND ({' OR '.join(names)})"
    return term


def plain_query(query: str) -> str:
    """PubMed のタグ（[tiab] など）を外した検索語（S2 はタグを読めない）。"""
    return re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", " ", query)).strip()


def title_query(title: str) -> str:
    """題名を OpenAlex の title.search に渡せる形にする（カンマを除き、AND / OR / NOT を演算子にしない）。"""
    s = re.sub(r"[,\"]", " ", title or "")
    s = re.sub(r"\b(AND|OR|NOT)\b", lambda m: m.group(1).lower(), s)
    return re.sub(r"\s+", " ", s).strip()


def _close_years(a: Optional[int], b: Optional[int], within: int = 2) -> bool:
    return not a or not b or abs(a - b) <= within


def in_journals(record: Dict[str, Any], journals: Sequence[str]) -> bool:
    """論文の誌が、指定した誌（誌名か ISSN）のどれかと同じか。"""
    issns = {j.strip().upper().replace("-", "") for j in journals if ISSN_RE.match(j.strip())}
    keys = {journal_key(j) for j in journals if not ISSN_RE.match(j.strip())}
    return journal_key(record.get("journal_name") or "") in keys or \
        any(i.upper().replace("-", "") in issns for i in record.get("issns") or [])


def bulk_query(query: str) -> str:
    """bulk 検索のクエリの AND / OR / NOT（大文字の語）を + / | / - に直す。

    S2 の bulk 検索はこれらの語を演算子と見ず、ただの語として探すので、0 件になる（エージェントがよく書く）。
    引用符の中は変えない。
    """
    parts = re.split(r'("[^"]*")', query)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"\bAND\s+NOT\s+", "NOT ", parts[i])
        parts[i] = re.sub(r"\b(AND|OR)\b", lambda m: f" {_BOOL_WORDS[m.group(1)]} ", parts[i])
        parts[i] = re.sub(r"\bNOT\s+", "-", parts[i])
    return re.sub(r"\s+", " ", "".join(parts)).strip()


class ApiError(RuntimeError):
    def __init__(self, service: str, message: str, status: Optional[int] = None):
        super().__init__(f"[{service}] {message}")
        self.service = service
        self.status = status


# ---------------- Cache ----------------

def _cache_path(key: str) -> Path:
    return CACHE_DIR / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json")


def _cache_get(key: str) -> Optional[Any]:
    path = _cache_path(key)
    try:
        if time.time() - path.stat().st_mtime > CACHE_TTL_SEC:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _cache_set(key: str, data: Any):
    path = _cache_path(key)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


# ---------------- Identifier parsing ----------------

def parse_identifier(identifier: str) -> Dict[str, str]:
    """
    DOI / URL / S2 paperId / arXiv ID / OpenAlex ID を判別する。
    Returns {"type": "doi|pmid|s2|arxiv|openalex|raw", "value": ..., "s2_id": ...}
    """
    raw = identifier.strip()

    m = re.search(r"doi\.org/(10\.\d{4,9}/\S+)", raw, re.IGNORECASE)
    if m or re.match(r"^(doi:)?10\.\d{4,9}/\S+$", raw, re.IGNORECASE):
        doi = m.group(1) if m else re.sub(r"^doi:", "", raw, flags=re.IGNORECASE)
        return {"type": "doi", "value": doi, "s2_id": f"DOI:{doi}"}

    m = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", raw, re.IGNORECASE) or re.match(r"^pmid:\s*(\d+)$", raw, re.IGNORECASE)
    if m:
        return {"type": "pmid", "value": m.group(1), "s2_id": f"PMID:{m.group(1)}"}

    m = re.search(r"openalex\.org/(W\d+)", raw, re.IGNORECASE) or re.match(r"^(W\d+)$", raw, re.IGNORECASE)
    if m:
        wid = m.group(1).upper()
        return {"type": "openalex", "value": wid, "s2_id": ""}

    m = re.search(r"semanticscholar\.org/paper/(?:[^/]+/)?([a-f0-9]{40})", raw, re.IGNORECASE) or re.match(
        r"^([a-f0-9]{40})$", raw, re.IGNORECASE
    )
    if m:
        return {"type": "s2", "value": m.group(1), "s2_id": m.group(1)}

    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", raw, re.IGNORECASE) or re.match(
        r"^(?:arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?$", raw, re.IGNORECASE
    )
    if m:
        return {"type": "arxiv", "value": m.group(1), "s2_id": f"ARXIV:{m.group(1)}"}

    return {"type": "raw", "value": raw, "s2_id": raw}


# ---------------- Normalization ----------------

def _bare_doi(doi: Optional[str]) -> str:
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", doi or "", flags=re.IGNORECASE)


def author_name(name: str) -> str:
    """すべて大文字の著者名（OpenAlex の "TODD L. ALLEE" など）を、参照文献で使える形（"Todd L. Allee"）にする。"""
    name = re.sub(r"\s+", " ", name or "").strip()
    if re.search(r"[A-Z]{2}", name) and name == name.upper():
        return " ".join(w if w.rstrip(".") in ("II", "III", "IV") else w.title() for w in name.split())
    return name


def jats_text(abstract: str) -> str:
    """Crossref の要旨（JATS の XML）を平文にする。先頭の「Abstract」の見出しは落とす。"""
    text = re.sub(r"<(jats:)?title>.*?</(jats:)?title>", " ", abstract or "", flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def _record(**kw) -> Dict[str, Any]:
    rec = {
        "id": "",
        "source": "",
        "title": "",
        "authors": [],
        "year": None,
        "journal_name": "",
        "volume": "",
        "issue": "",
        "pages": "",
        "issns": [],
        "source_type": "",
        "publication_types": [],
        "doi": "",
        "url": "",
        "citation_count": 0,
        "reference_count": 0,
        "abstract": "",
        "tldr": "",
        "oa_pdf": "",
        "fields": [],
        "openalex_id": "",
        "pmid": "",
        "pmcid": "",
        "mesh": [],
        "retracted": False,
        "verified": False,   # OpenAlex で DOI 照合済みか
        "warnings": [],
        "notes": [],         # 知らせるだけのこと（DOI を雑誌版に替えた、など）。確かめる必要のあるものは warnings
    }
    rec.update({k: v for k, v in kw.items() if v is not None})
    # 雑誌側の脚注記号（"...Jobs*" など）が Markdown の強調を壊すので落とす
    rec["title"] = re.sub(r"\s*[*†‡]+$", "", re.sub(r"\s+", " ", rec["title"]).strip())
    rec["authors"] = [author_name(a) for a in rec["authors"] if author_name(a)]
    rec["warnings"] = list(rec["warnings"])
    rec["notes"] = list(rec["notes"])
    if re.search(r",\s*(?:edited\s+)?by\s+[A-Z]", rec["title"]) or re.fullmatch(r"(\d+)\s*-+\s*\1", rec["pages"]):
        rec["warnings"].append(t("May be a book review or comment (guessed from the title or the page range)"))
    if rec["retracted"]:
        mark_retracted(rec)
    rec["ssci"] = classify_paper(rec)
    return rec


def mark_retracted(rec: Dict[str, Any]):
    """撤回された論文の印。警告は `fix --confirm` で消せるので、`check` は retracted も別に見る。"""
    rec["retracted"] = True
    warning = t("Retracted: do not rely on this paper (the retraction is recorded in PubMed or OpenAlex)")
    if warning not in rec["warnings"]:
        rec["warnings"].append(warning)


def not_research(record: Dict[str, Any]) -> bool:
    return bool(set(record.get("publication_types") or []) & PUBMED_NOT_RESEARCH)


def expand_pages(pages: str) -> str:
    """MEDLINE の略したページ（"1405-14"）を全部書く（"1405-1414"）。"""
    m = re.fullmatch(r"\s*([A-Za-z]*)(\d+)\s*-\s*([A-Za-z]*)(\d+)\s*", pages or "")
    if not m:
        return (pages or "").strip()
    prefix, first, _, last = m.groups()
    if len(last) < len(first):
        last = first[:len(first) - len(last)] + last
    return f"{prefix}{first}-{prefix}{last}"


def _xml_text(element: Optional[ET.Element]) -> str:
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip() if element is not None else ""


def from_pubmed(article: ET.Element) -> Dict[str, Any]:
    """efetch の <PubmedArticle> 1 件を正規化する。"""
    citation = article.find("MedlineCitation")
    art = citation.find("Article")
    journal = art.find("Journal")
    issue = journal.find("JournalIssue") if journal is not None else None

    date = issue.find("PubDate") if issue is not None else None
    year_text = (date.findtext("Year") or date.findtext("MedlineDate") or "") if date is not None else ""
    m = re.search(r"\d{4}", year_text)

    authors = []
    for a in art.findall("AuthorList/Author"):
        name = a.findtext("CollectiveName") or " ".join(x for x in (a.findtext("ForeName"), a.findtext("LastName")) if x)
        if name:
            authors.append(name)

    ids = {i.get("IdType"): (i.text or "").strip() for i in article.findall("PubmedData/ArticleIdList/ArticleId")}
    doi = ids.get("doi") or next((e.text or "" for e in art.findall("ELocationID") if e.get("EIdType") == "doi"), "")
    doi = _bare_doi(doi.strip())
    pmid = (citation.findtext("PMID") or "").strip()

    parts = []
    for text in art.findall("Abstract/AbstractText"):
        body = _xml_text(text)
        if body:
            parts.append(f"{text.get('Label')}: {body}" if text.get("Label") else body)

    types = [(p.text or "").strip() for p in art.findall("PublicationTypeList/PublicationType") if p.text]
    issns = [i.text.strip() for i in (journal.findall("ISSN") if journal is not None else []) if i.text]
    linking = citation.findtext("MedlineJournalInfo/ISSNLinking")
    if linking and linking.strip() not in issns:
        issns.append(linking.strip())
    return _record(
        id=f"PMID:{pmid}",
        source="PubMed",
        pmid=pmid,
        pmcid=ids.get("pmc", ""),
        title=re.sub(r"\.$", "", _xml_text(art.find("ArticleTitle"))),
        authors=authors,
        year=int(m.group()) if m else None,
        journal_name=journal.findtext("Title") if journal is not None else "",
        volume=(issue.findtext("Volume") or "") if issue is not None else "",
        issue=(issue.findtext("Issue") or "") if issue is not None else "",
        pages=expand_pages(art.findtext("Pagination/MedlinePgn") or ""),
        issns=issns,
        source_type="journal",
        publication_types=types,
        doi=doi,
        url=f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        abstract=" ".join(parts),
        mesh=[_xml_text(h.find("DescriptorName")) for h in citation.findall("MeshHeadingList/MeshHeading")],
        medline=citation.get("Status") == "MEDLINE",
        retracted="Retracted Publication" in types,
        found_in=["PubMed"],
    )


def pubmed_articles(xml: str) -> List[Dict[str, Any]]:
    """efetch の XML を正規化する。壊れた記録は飛ばす。"""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise ApiError("PubMed", t("could not read the response: {error}", error=e)) from e
    records = []
    for article in root.findall("PubmedArticle"):
        try:
            records.append(from_pubmed(article))
        except AttributeError:   # MedlineCitation や Article の無い記録
            continue
    return records


_JATS_BLOCKS = {"title", "p", "tr", "caption"}


def jats_fulltext(xml: str) -> str:
    """Europe PMC の全文 XML（JATS）の本文を平文にする（表は行ごとに | で区切る。参考文献は入れない）。"""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return ""
    lines: List[str] = []

    def walk(el: ET.Element):
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "tr":
            lines.append(" | ".join(_xml_text(c) for c in el))
        elif tag in _JATS_BLOCKS and not any(d.tag in _JATS_BLOCKS for d in el.iter() if d is not el):
            text = _xml_text(el)
            if text:
                lines.append(text)
        else:
            for child in el:
                walk(child)

    for part in [root.find(".//abstract"), root.find(".//body")]:
        if part is not None:
            walk(part)
    return "\n".join(lines)


def from_s2(p: Dict[str, Any]) -> Dict[str, Any]:
    venue = p.get("publicationVenue") or {}
    journal = p.get("journal") or {}
    issns = [i for i in [venue.get("issn"), *(venue.get("alternate_issns") or [])] if i]
    doi = (p.get("externalIds") or {}).get("DOI") or ""
    return _record(
        id=p.get("paperId") or "",
        source="SemanticScholar",
        title=(p.get("title") or "").strip(),
        authors=[a.get("name", "") for a in (p.get("authors") or []) if a.get("name")],
        year=p.get("year"),
        journal_name=html.unescape(journal.get("name") or venue.get("name") or p.get("venue") or ""),
        volume=(journal.get("volume") or "").strip(),
        pages=(journal.get("pages") or "").strip(),
        issns=issns,
        source_type=venue.get("type") or "",
        publication_types=p.get("publicationTypes") or [],
        doi=doi,
        url=f"https://doi.org/{doi}" if doi else (p.get("url") or ""),
        citation_count=p.get("citationCount") or 0,
        reference_count=p.get("referenceCount") or 0,
        abstract=(p.get("abstract") or "").strip(),
        tldr=((p.get("tldr") or {}).get("text") or "").strip(),
        oa_pdf=(p.get("openAccessPdf") or {}).get("url") or "",
        # fieldsOfStudy（外部の分類）は空のことが多いので、S2 の分類器による s2FieldsOfStudy も合わせる
        fields=list(dict.fromkeys([*(p.get("fieldsOfStudy") or []),
                                   *(f.get("category") for f in (p.get("s2FieldsOfStudy") or []) if f.get("category"))])),
    )


def from_openalex(w: Dict[str, Any]) -> Dict[str, Any]:
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    biblio = w.get("biblio") or {}
    pages = biblio.get("first_page") or ""
    if pages and biblio.get("last_page"):
        pages += f"-{biblio['last_page']}"

    abstract = ""
    inv = w.get("abstract_inverted_index")
    if isinstance(inv, dict):
        positions = sorted((pos, word) for word, poss in inv.items() for pos in poss)
        abstract = " ".join(word for _, word in positions)

    doi = _bare_doi(w.get("doi"))
    # OpenAlex は WP 版と掲載版を 1 つの work にまとめ、DOI に WP 版を、所在の先頭に掲載誌を置くことがある
    # （Hospido & Moral-Benito 2016: 10.2139/ssrn.2480321 と Labour Economics）。誌名に合わせて掲載版の DOI を使う
    published, preprint = location_doi(loc), ""
    if published and published.lower() != doi.lower() and preprint_doi(doi) and not preprint_doi(published):
        doi, preprint = published, doi
    work_id = (w.get("id") or "").replace("https://openalex.org/", "")
    rec = _record(
        id=work_id,
        openalex_id=work_id,
        source="OpenAlex",
        title=(w.get("title") or w.get("display_name") or "").strip(),
        authors=[(a.get("author") or {}).get("display_name", "") for a in (w.get("authorships") or [])],
        year=w.get("publication_year"),
        journal_name=src.get("display_name") or "",
        volume=biblio.get("volume") or "",
        issue=biblio.get("issue") or "",
        pages=pages,
        issns=src.get("issn") or ([src["issn_l"]] if src.get("issn_l") else []),
        source_type=src.get("type") or "",
        publication_types=[w["type"]] if w.get("type") else [],
        doi=doi,
        url=f"https://doi.org/{doi}" if doi else (w.get("id") or ""),
        citation_count=w.get("cited_by_count") or 0,
        reference_count=w.get("referenced_works_count") or 0,
        abstract=abstract,
        oa_pdf=loc.get("pdf_url") or (w.get("open_access") or {}).get("oa_url") or "",
        fields=[t.get("display_name") for t in (w.get("topics") or [])[:3]],
        retracted=bool(w.get("is_retracted")),
    )
    if preprint:
        rec["preprint_doi"] = preprint
    return rec


def location_doi(loc: Dict[str, Any]) -> str:
    """OpenAlex の所在の DOI（landing_page_url が doi.org のとき）。"""
    url = (loc or {}).get("landing_page_url") or ""
    return _bare_doi(url) if re.match(r"^https?://(dx\.)?doi\.org/10\.", url, re.IGNORECASE) else ""


def _date_year(part: Any) -> Optional[int]:
    """Crossref の日付（{"date-parts": [[2024, 5]]}）の年。"""
    try:
        y = int(((part or {}).get("date-parts") or [[None]])[0][0])
    except (TypeError, ValueError, IndexError):
        return None
    return y if 1800 < y < 2200 else None


def merge_found(s2: List[Dict[str, Any]], oa: List[Dict[str, Any]], bulk: bool) -> List[Dict[str, Any]]:
    """S2 の結果に、OpenAlex の結果のうち S2 に無かったものを足す（DOI・OpenAlex ID・題名と年で同じ論文を見る）。

    bulk（被引用順）なら被引用数で並べ直す。関連度順なら S2 の順を保ち、OpenAlex にだけあった論文は
    OpenAlex での順位の位置に差し込む（OpenAlex の 3 位なら S2 の 3 位の後ろ）。どちらで見つかったかは
    found_in に残す。同じ論文で S2 の側がプレプリント版なら、OpenAlex の雑誌版に替える。"""
    out = list(s2)
    rank = {id(p): n for n, p in enumerate(s2)}
    for n, r in enumerate(oa):
        same = next((p for p in out if (r["doi"] and r["doi"].lower() in {p["doi"].lower(), (p.get("preprint_doi") or "").lower()})
                     or (r.get("preprint_doi") and p["doi"] and r["preprint_doi"].lower() == p["doi"].lower())
                     or (r["openalex_id"] and r["openalex_id"] == p.get("openalex_id"))
                     or (ssci.same_title(p["title"], r["title"]) and _close_years(p.get("year"), r.get("year")))), None)
        if same is None:
            out.append(r)
            rank[id(r)] = n + 0.5
            continue
        found = list(dict.fromkeys([*same.get("found_in", []), "OpenAlex"]))
        if r["ssci"]["tier"] > same["ssci"]["tier"] and r["doi"] and same["doi"] and r["doi"].lower() != same["doi"].lower():
            LiteratureClient._take_journal_version(same, r, list(same["warnings"]))
        same["found_in"] = found
    if bulk:
        out.sort(key=lambda p: p.get("citation_count") or 0, reverse=True)
    else:
        out.sort(key=lambda p: rank[id(p)])
    return out


# ---------------- Client ----------------

class LiteratureClient:
    def __init__(self, use_cache: bool = True):
        self.s2_api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or os.environ.get("S2_API_KEY")
        self.openalex_api_key = os.environ.get("OPENALEX_API_KEY")
        self.openalex_mailto = os.environ.get("OPENALEX_MAILTO")
        self.ncbi_api_key = os.environ.get("NCBI_API_KEY")
        self.use_cache = use_cache and os.environ.get("PRIORWORK_NO_CACHE") != "1"
        self.max_retries = int(os.environ.get("PRIORWORK_MAX_RETRIES") or 5)
        self._last_request: Dict[str, float] = {}
        self._source_ids: Dict[str, str] = {}     # journal_key -> OpenAlex source ID（この実行で分かったもの）
        self.issue_years_failed = False           # 直前の issue_years が Crossref の失敗で打ち切られたか
        self.last_search: Dict[str, Any] = {}     # 直前の search() で OpenAlex をどう使ったか（検索ログ用）

    # ---- HTTP ----

    def _throttle(self, service: str):
        interval = {"SemanticScholar": 1.1 if self.s2_api_key else 1.5,
                    "PubMed": 0.12 if self.ncbi_api_key else 0.35}.get(service, 0.2)
        elapsed = time.time() - self._last_request.get(service, 0.0)
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_request[service] = time.time()

    def _get_json(self, service: str, url: str, params: Dict[str, Any], headers: Dict[str, str],
                  secret_params: Optional[Dict[str, Any]] = None, raw: bool = False) -> Any:
        """raw なら本文をそのまま返す（XML を返す API のため）。"""
        params = {k: v for k, v in params.items() if v is not None}
        cache_key = f"{url}?{urlencode(sorted(params.items()))}"
        if self.use_cache:
            cached = _cache_get(cache_key)
            if cached is not None:
                return cached

        all_params = {**params, **{k: v for k, v in (secret_params or {}).items() if v}}
        for attempt in range(self.max_retries + 1):
            self._throttle(service)
            try:
                resp = requests.get(url, params=all_params, headers=headers, timeout=30)
            except (requests.ConnectionError, requests.Timeout) as e:
                status, detail, retry_after = None, t("network error: {error}", error=e.__class__.__name__), None
            else:
                if resp.ok:
                    data = resp.text if raw else resp.json()
                    if self.use_cache:
                        _cache_set(cache_key, data)
                    return data
                status, detail = resp.status_code, _error_detail(resp)
                retry_after = resp.headers.get("Retry-After")
                if status not in RETRY_STATUSES:
                    raise ApiError(service, f"HTTP {status}: {detail}", status)

            if attempt >= self.max_retries:
                raise ApiError(service, t("gave up after {n|# retry|# retries} ({detail})", n=self.max_retries, detail=status or detail), status)
            try:
                wait = max(float(retry_after), 1.0)
            except (TypeError, ValueError):
                wait = BACKOFF_DELAYS[min(attempt, len(BACKOFF_DELAYS) - 1)]
            reason = t("rate limited (HTTP 429)") if status == 429 else (f"HTTP {status}" if status else detail)
            print(f"[{service}] " + t("{reason}. Retrying in {seconds} s ({attempt}/{max})", reason=reason,
                                      seconds=f"{wait:.0f}", attempt=attempt + 1, max=self.max_retries),
                  file=sys.stderr)
            time.sleep(wait)
        raise AssertionError("unreachable")

    def _s2(self, path: str, params: Dict[str, Any]) -> Any:
        headers = {"User-Agent": "priorwork/0.1", "Accept": "application/json"}
        if self.s2_api_key:
            headers["x-api-key"] = self.s2_api_key
        return self._get_json("SemanticScholar", f"{S2_BASE_URL}{path}", params, headers)

    def _openalex(self, path: str, params: Dict[str, Any]) -> Any:
        ua = "priorwork/0.1" + (f" (mailto:{self.openalex_mailto})" if self.openalex_mailto else "")
        return self._get_json(
            "OpenAlex", f"{OPENALEX_BASE_URL}{path}", params, {"User-Agent": ua},
            secret_params={"api_key": self.openalex_api_key, "mailto": self.openalex_mailto},
        )

    def _crossref(self, path: str, params: Dict[str, Any]) -> Any:
        ua = "priorwork/0.1" + (f" (mailto:{self.openalex_mailto})" if self.openalex_mailto else "")
        return self._get_json("Crossref", f"{CROSSREF_BASE_URL}{path}", params, {"User-Agent": ua},
                              secret_params={"mailto": self.openalex_mailto})

    def _pubmed(self, path: str, params: Dict[str, Any], raw: bool = False) -> Any:
        return self._get_json("PubMed", f"{NCBI_BASE_URL}/{path}", {**params, "tool": "priorwork"},
                              {"User-Agent": "priorwork/0.1"}, secret_params={"api_key": self.ncbi_api_key}, raw=raw)

    def _europepmc(self, path: str) -> str:
        return self._get_json("EuropePMC", f"{EUROPEPMC_BASE_URL}{path}", {}, {"User-Agent": "priorwork/0.1"}, raw=True)

    def complete_abstracts(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """S2 にも OpenAlex にも要旨が無い論文を、Crossref（出版社が登録した要旨）で補う。失敗しても止めない。"""
        missing = [r for r in records if not r.get("abstract") and r.get("doi")]
        try:
            for i in range(0, len(missing), CROSSREF_BATCH):
                chunk = missing[i:i + CROSSREF_BATCH]
                data = self._crossref("/works", {"filter": ",".join(f"doi:{r['doi'].lower()}" for r in chunk),
                                                 "rows": CROSSREF_BATCH, "select": "DOI,abstract"})
                found = {(item.get("DOI") or "").lower(): item.get("abstract")
                         for item in (data.get("message") or {}).get("items") or []}
                for r in chunk:
                    text = jats_text(found.get(r["doi"].lower()) or "")
                    if text:
                        r["abstract"] = text
        except ApiError as e:
            print("[Notice] " + t("{error} → abstracts are not filled in from Crossref", error=e), file=sys.stderr)
        return records

    def issue_years(self, dois: List[str]) -> Dict[str, int]:
        """DOI ごとの、掲載号の年（Crossref の journal-issue / published-print）。分からない DOI は入らない。

        S2・OpenAlex の年はオンラインで先に公開された年のことが多く（巻・号に載るのは翌年など）、
        参照文献の年と食い違う。失敗しても止めない（空のまま返す）。"""
        years: Dict[str, int] = {}
        self.issue_years_failed = False
        dois = [d.lower() for d in dois if d]
        try:
            for i in range(0, len(dois), CROSSREF_BATCH):
                chunk = dois[i:i + CROSSREF_BATCH]
                data = self._crossref("/works", {"filter": ",".join(f"doi:{d}" for d in chunk),
                                                 "rows": CROSSREF_BATCH,
                                                 "select": "DOI,published-print"})   # journal-issue はこの経路で選べない（HTTP 400）
                for item in (data.get("message") or {}).get("items") or []:
                    year = _date_year((item.get("journal-issue") or {}).get("published-print")) \
                        or _date_year(item.get("published-print"))
                    if year:
                        years[(item.get("DOI") or "").lower()] = year
        except ApiError as e:
            self.issue_years_failed = True
            print("[Notice] " + t("{error} → the years of the journal issues are not checked", error=e), file=sys.stderr)
        return years

    def use_issue_year(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """巻のある論文の年を、オンライン先行公開の年から掲載号の年に直す（元の年は online_year に残す）。"""
        if record.get("doi") and record.get("volume"):
            year = self.issue_years([record["doi"]]).get(record["doi"].lower())
            if year and record.get("year") and year > record["year"]:
                record["online_year"], record["year"] = record["year"], year
        return record

    # ---- Semantic Scholar ----

    def _search_s2(self, query: str, limit: int, year: Optional[str], bulk: bool,
                   journals: Sequence[str] = ()) -> List[Dict[str, Any]]:
        # 誌で絞るときは S2 の venue（誌名をカンマで並べる）。誌名にカンマがあると切れるので除く
        venue = ",".join(j.replace(",", " ") for j in journals) or None
        if bulk:
            # bulk 検索: AND(+) / OR(|) / 除外(-) / "フレーズ" が使え、被引用数順に最大 1000 件返る
            data = self._s2("/paper/search/bulk", {"query": bulk_query(query), "fields": S2_BULK_FIELDS, "year": year,
                                                    "sort": "citationCount:desc", "venue": venue})
        else:
            data = self._s2("/paper/search", {"query": query, "limit": min(limit, 100), "fields": S2_PAPER_FIELDS,
                                               "year": year, "venue": venue})
        return [from_s2(p) for p in (data.get("data") or [])[:limit]]

    def _get_paper_s2(self, s2_id: str) -> Dict[str, Any]:
        return from_s2(self._s2(f"/paper/{quote(s2_id, safe=':')}", {"fields": S2_PAPER_FIELDS}))

    def _linked_s2(self, s2_id: str, kind: str, limit: int) -> List[Dict[str, Any]]:
        key = "citingPaper" if kind == "citations" else "citedPaper"
        data = self._s2(f"/paper/{quote(s2_id, safe=':')}/{kind}",
                        {"limit": min(limit, 1000), "fields": S2_LINKED_FIELDS})
        if data.get("data") is None:
            # 出版社の意向で引用データが非公開（elided）の論文は data: null になる
            raise ApiError("SemanticScholar", t("the publisher does not make the {kind} public", kind=kind), 404)
        return [from_s2(item[key]) for item in data.get("data") or [] if (item.get(key) or {}).get("paperId")]

    # ---- OpenAlex ----

    def _get_paper_openalex(self, ident: Dict[str, str]) -> Dict[str, Any]:
        if ident["type"] not in ("doi", "openalex"):
            raise ApiError("OpenAlex", t("OpenAlex can only look up a DOI or an OpenAlex ID: {id}", id=ident["value"]), 404)
        path = f"/works/doi:{ident['value']}" if ident["type"] == "doi" else f"/works/{ident['value']}"
        rec = from_openalex(self._openalex(path, {"select": OPENALEX_SELECT}))
        rec["verified"] = True
        return rec

    def _verify_with_openalex(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """S2 のレコードを DOI で OpenAlex と照合し、書誌情報を補正する（まとめて照会するので API 呼び出しは少ない）。"""
        targets = [r for r in records if r["source"] == "SemanticScholar"]
        for r in targets:
            if not r["doi"]:
                r["warnings"].append(t("No DOI"))

        with_doi = [r for r in targets if r["doi"]]
        works: Dict[str, Dict[str, Any]] = {}
        try:
            for i in range(0, len(with_doi), OPENALEX_BATCH):
                chunk = with_doi[i:i + OPENALEX_BATCH]
                data = self._openalex("/works", {
                    "filter": "doi:" + "|".join(r["doi"].lower() for r in chunk),
                    "per_page": OPENALEX_BATCH,
                    "select": OPENALEX_SELECT,
                })
                for w in data.get("results") or []:
                    works[_bare_doi(w.get("doi")).lower()] = w
                    # 掲載版の DOI でも引ける（work の DOI が WP 版のとき）
                    works.setdefault(location_doi(w.get("primary_location") or {}).lower() or "-", w)
        except ApiError as e:
            print("[Notice] " + t("{error} → the DOIs are not checked with OpenAlex (the details from S2 are kept)",
                                  error=e), file=sys.stderr)
            for r in with_doi:
                r["warnings"].append(t("DOI not verified"))
            return records

        # 雑誌版を探す候補: S2 の誌名は雑誌なのに、DOI がプレプリント・WP のもの、または OpenAlex が知らないもの
        versions: List[tuple] = []
        for r in with_doi:
            w = works.get(r["doi"].lower())
            s2_journal, s2_status, s2_issns = r["journal_name"], r["ssci"]["status"], list(r["issns"])
            journal_like = bool(s2_journal) and s2_status != ssci.PREPRINT
            if not w:
                warning = t("OpenAlex does not know the DOI (verify the DOI)")
                r["warnings"].append(warning)
                if journal_like:
                    versions.append((r, s2_journal, s2_issns, [warning]))
                continue
            oa = from_openalex(w)
            if oa.get("preprint_doi", "").lower() == r["doi"].lower() and ssci.same_title(oa["title"], r["title"]):
                # S2 の DOI は WP 版で、OpenAlex の同じ work に掲載版がある
                self._take_journal_version(r, oa)
                if oa["retracted"]:
                    mark_retracted(r)
                continue
            added = []
            if not ssci.same_title(oa["title"], r["title"]):
                added.append(t("The DOI points to another title: \"{title}\" (verify the DOI)", title=oa["title"]))
                r["warnings"].append(added[-1])
            # Zotero 取り込み・SSCI 照合に使う書誌情報は、DOI の実体（OpenAlex）側で丸ごと置き換える
            for field in ("journal_name", "issns", "source_type", "publication_types", "volume", "issue", "pages"):
                r[field] = oa[field]
            # S2 は WP 版と掲載版を一つにまとめ、WP 版の年を返すことがある。年も DOI の実体（掲載版）に合わせる
            if oa["year"]:
                r["year"] = oa["year"]
            if not r["abstract"]:
                r["abstract"] = oa["abstract"]
            r["verified"] = True
            r["openalex_id"] = oa["openalex_id"]
            if oa["retracted"]:
                mark_retracted(r)
            r["ssci"] = ssci.classify_paper(r)
            if r["ssci"]["status"] == ssci.PREPRINT and s2_status != ssci.PREPRINT and s2_journal:
                added.append(t("S2 gives the journal as \"{journal}\", but the DOI is a working paper / preprint version "
                               "(find the DOI of the published version)", journal=s2_journal))
                r["warnings"].append(added[-1])
            if journal_like and (preprint_doi(r["doi"]) or r["ssci"]["status"] == ssci.PREPRINT):
                versions.append((r, s2_journal, s2_issns, added))
        self._use_journal_versions(versions)
        return records

    def _journal_version(self, r: Dict[str, Any], journal: str, issns: Sequence[str]) -> Optional[Dict[str, Any]]:
        """題名（と、分かれば誌）で OpenAlex を引き、同じ論文の雑誌版を返す。無ければ None。"""
        filters = [f"title.search:{title_query(r['title'])}"]
        sid = self._source_ids.get(journal_key(journal)) or KNOWN_SOURCES.get(journal_key(journal))
        if sid:
            filters.append(f"primary_location.source.id:{sid}")
        elif issns:
            filters.append(f"primary_location.source.issn:{issns[0]}")
        data = self._openalex("/works", {"filter": ",".join(filters), "per_page": 5, "select": OPENALEX_SELECT})
        for w in data.get("results") or []:
            oa = from_openalex(w)
            if (oa["doi"] and oa["doi"].lower() != r["doi"].lower() and not preprint_doi(oa["doi"])
                    and oa["ssci"]["status"] != ssci.PREPRINT and ssci.same_title(oa["title"], r["title"])
                    and _close_years(oa["year"], r["year"])):
                return oa
        return None

    def _use_journal_versions(self, versions: List[tuple]):
        """プレプリント・WP の DOI が付いた雑誌論文の DOI と書誌情報を、OpenAlex で見つけた雑誌版に替える。
        見つからなければ警告のまま。問い合わせは MAX_VERSION_LOOKUPS 件まで。"""
        for n, (r, journal, issns, added) in enumerate(versions):
            if n >= MAX_VERSION_LOOKUPS:
                print("[Notice] " + t("Did not look for the journal version of {n|# more paper|# more papers} "
                                      "(at most {max} per search; the warnings stay)",
                                      n=len(versions) - n, max=MAX_VERSION_LOOKUPS), file=sys.stderr)
                return
            try:
                oa = self._journal_version(r, journal, issns)
            except ApiError as e:
                print("[Notice] " + t("{error} → the journal versions of preprint DOIs are not looked for", error=e),
                      file=sys.stderr)
                return
            if oa:
                self._take_journal_version(r, oa, added)

    @staticmethod
    def _take_journal_version(r: Dict[str, Any], oa: Dict[str, Any], dropped_warnings: Sequence[str] = ()):
        old = r["doi"]
        for field in ("journal_name", "issns", "source_type", "publication_types", "volume", "issue", "pages",
                      "doi", "url", "openalex_id"):
            r[field] = oa[field]
        if oa["year"]:
            r["year"] = oa["year"]
        if not r["abstract"]:
            r["abstract"] = oa["abstract"]
        r["preprint_doi"] = old
        r["verified"] = True
        r["warnings"] = [w for w in r["warnings"] if w not in dropped_warnings
                         and w != t("OpenAlex does not know the DOI (verify the DOI)")]
        r["notes"].append(t("Replaced the preprint / working-paper DOI {old} with the journal version {doi}",
                            old=old, doi=oa["doi"]))
        r["ssci"] = ssci.classify_paper(r)

    def journal_source_ids(self, journals: Sequence[str]) -> Dict[str, str]:
        """誌名か ISSN ごとの OpenAlex source ID。OpenAlex に見つからない誌は入らない。"""
        ids: Dict[str, str] = {}
        for j in journals:
            key = journal_key(j)
            sid = self._source_ids.get(key) or KNOWN_SOURCES.get(key)
            if not sid and ISSN_RE.match(j.strip()):
                try:
                    sid = self._openalex(f"/sources/issn:{j.strip().upper()}", {"select": "id,display_name"}).get("id")
                except ApiError as e:
                    if e.status != 404:
                        raise
            elif not sid:
                data = self._openalex("/sources", {"search": j, "per_page": 10,
                                                   "select": "id,display_name,alternate_titles"})
                for src in data.get("results") or []:
                    names = [src.get("display_name") or "", *(src.get("alternate_titles") or [])]
                    if key in {journal_key(n) for n in names}:
                        sid = src.get("id")
                        break
            if sid:
                sid = sid.replace("https://openalex.org/", "")
                self._source_ids[key] = sid
                ids[j] = sid
        return ids

    def _search_openalex(self, query: str, limit: int, year: Optional[str], bulk: bool,
                         source_ids: Sequence[str]) -> List[Dict[str, Any]]:
        """誌（source ID）で絞って OpenAlex を検索する。誌の絞り込みが ID で確かに効くときだけ使う。"""
        filters = ["primary_location.source.id:" + "|".join(source_ids)]
        years = openalex_years(year)
        if years:
            filters.append(years)
        q = openalex_query(query)
        if q:
            filters.append(f"title_and_abstract.search:{q}")
        params = {"filter": ",".join(filters), "per_page": min(max(limit, 1), 200), "select": OPENALEX_SELECT}
        if bulk:
            params["sort"] = "cited_by_count:desc"
        data = self._openalex("/works", params)
        return [dict(from_openalex(w), verified=True, found_in=["OpenAlex"]) for w in data.get("results") or []]

    def _linked_openalex(self, ident: Dict[str, str], kind: str, limit: int) -> List[Dict[str, Any]]:
        if ident["type"] in ("s2", "arxiv"):
            # OpenAlex は S2 ID / arXiv ID を直接引けないので、S2 で DOI を得てから引き直す
            doi = self._get_paper_s2(ident["s2_id"])["doi"]
            if not doi:
                raise ApiError("OpenAlex", t("There is no DOI, so OpenAlex cannot look it up: {id}", id=ident["value"]))
            ident = {"type": "doi", "value": doi}
        work_id = ident["value"] if ident["type"] == "openalex" else self._get_paper_openalex(ident)["id"]
        data = self._openalex("/works", {
            "filter": f"{'cites' if kind == 'citations' else 'cited_by'}:{work_id}",
            "per_page": min(limit, 200),
            "select": OPENALEX_SELECT,
            "sort": "cited_by_count:desc",
        })
        return [dict(from_openalex(w), verified=True) for w in data.get("results") or []]

    # ---- PubMed ----

    def _esearch(self, term: str, retmax: int, year: Optional[str] = None, db: str = "pubmed") -> Dict[str, Any]:
        data = self._pubmed("esearch.fcgi", {"db": db, "term": term, "retmax": retmax, "retmode": "json",
                                             "sort": "relevance" if db == "pubmed" else None, **pubmed_dates(year)})
        result = data.get("esearchresult") or {}
        if result.get("ERROR"):
            raise ApiError("PubMed", str(result["ERROR"]))
        return result

    def _pubmed_fetch(self, pmids: Sequence[str]) -> List[Dict[str, Any]]:
        """PMID の順に、PubMed の記録を返す。"""
        found: Dict[str, Dict[str, Any]] = {}
        for i in range(0, len(pmids), PUBMED_BATCH):
            xml = self._pubmed("efetch.fcgi", {"db": "pubmed", "id": ",".join(pmids[i:i + PUBMED_BATCH]),
                                               "retmode": "xml"}, raw=True)
            found.update((r["pmid"], r) for r in pubmed_articles(xml))
        return [found[p] for p in pmids if p in found]

    def _search_pubmed(self, query: str, limit: int, year: Optional[str],
                       journals: Sequence[str]) -> List[Dict[str, Any]]:
        term = pubmed_term(query, journals)
        result = self._esearch(term, limit, year)
        self.last_pubmed = {"pubmed_count": int(result.get("count") or 0),
                            "pubmed_query": result.get("querytranslation") or term}
        return self._pubmed_fetch(result.get("idlist") or [])

    def _enrich_pubmed(self, records: List[Dict[str, Any]]):
        """PubMed の記録に OpenAlex の情報（被引用数・OpenAlex ID・OA の PDF・撤回・誌名）を足す。
        書誌と DOI は PubMed のまま（出版社が登録した値）。失敗しても止めない。"""
        with_doi = [r for r in records if r["source"] == "PubMed" and r["doi"]]
        try:
            for i in range(0, len(with_doi), OPENALEX_BATCH):
                chunk = with_doi[i:i + OPENALEX_BATCH]
                data = self._openalex("/works", {"filter": "doi:" + "|".join(r["doi"].lower() for r in chunk),
                                                 "per_page": OPENALEX_BATCH, "select": OPENALEX_SELECT})
                works = {_bare_doi(w.get("doi")).lower(): w for w in data.get("results") or []}
                for r in chunk:
                    w = works.get(r["doi"].lower())
                    if not w:
                        continue
                    oa = from_openalex(w)
                    r.update(citation_count=oa["citation_count"], reference_count=oa["reference_count"],
                             openalex_id=oa["openalex_id"], verified=True, oa_pdf=r["oa_pdf"] or oa["oa_pdf"])
                    r["fields"] = oa["fields"]
                    if oa["journal_name"] and oa["source_type"] == "journal":   # PubMed の誌名は "The Lancet. Oncology" の形
                        r["journal_name"] = oa["journal_name"]
                    r["issns"] = list(dict.fromkeys([*r["issns"], *oa["issns"]]))
                    if oa["retracted"]:
                        mark_retracted(r)
                    r["ssci"] = ssci.classify_paper(r)
        except ApiError as e:
            print("[Notice] " + t("{error} → the citation counts of the PubMed results are not filled in", error=e),
                  file=sys.stderr)

    def annotate_pubmed(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """PubMed を通らなかった論文を DOI で PubMed と照合する（PMID・PMC ID・種類・MeSH・MEDLINE・撤回）。
        見つからなければ medline=False。PubMed が失敗したら未確認（None）のまま。"""
        pending = [r for r in records if r.get("medline") is None]
        with_doi = [r for r in pending if r.get("doi")]
        found: Dict[str, Dict[str, Any]] = {}
        try:
            for i in range(0, len(with_doi), PUBMED_BATCH):
                chunk = with_doi[i:i + PUBMED_BATCH]
                term = " OR ".join(f'"{r["doi"]}"[doi]' for r in chunk)
                ids = self._esearch(term, PUBMED_BATCH).get("idlist") or []
                found.update((p["doi"].lower(), p) for p in self._pubmed_fetch(ids) if p["doi"])
        except ApiError as e:
            print("[Notice] " + t("{error} → PubMed's details are not added", error=e), file=sys.stderr)
            return records
        for r in pending:
            p = found.get((r.get("doi") or "").lower())
            r["medline"] = bool(p and p["medline"])
            if p:
                for key in ("pmid", "pmcid", "mesh"):
                    r[key] = p[key]
                r["publication_types"] = list(dict.fromkeys([*r["publication_types"], *p["publication_types"]]))
                r["abstract"] = r.get("abstract") or p["abstract"]
                if p["retracted"]:
                    mark_retracted(r)
            r["ssci"] = ssci.classify_paper(r)
        return records

    def search_medical(self, query: str, limit: int = 20, year: Optional[str] = None, bulk: bool = False,
                       journals: Sequence[str] = ()) -> List[Dict[str, Any]]:
        """医学のサーベイの検索: PubMed（主）に、S2 にだけあった論文を足す。片方が失敗してももう片方を返す。"""
        pubmed: List[Dict[str, Any]] = []
        self.last_pubmed = {}
        failed: Optional[ApiError] = None
        try:
            pubmed = self._search_pubmed(query, limit, year, journals)
            self._enrich_pubmed(pubmed)
        except ApiError as e:
            failed = e
            print("[Notice] " + t("{error} → only the S2 results (PubMed was not searched)", error=e), file=sys.stderr)
        try:
            s2 = self.search(plain_query(query), limit=limit, year=year, bulk=bulk, journals=journals)
        except ApiError as e:
            if failed:
                raise
            print("[Notice] " + t("{error} → only the PubMed results", error=e), file=sys.stderr)
            s2 = []
        info = self.last_search
        self.last_search = {**info, **self.last_pubmed, "pubmed": "failed" if failed else "used"}
        return self.annotate_pubmed(self._merge_pubmed(pubmed, s2, bulk))

    @staticmethod
    def _merge_pubmed(pubmed: List[Dict[str, Any]], others: List[Dict[str, Any]], bulk: bool) -> List[Dict[str, Any]]:
        """PubMed の結果の後ろに、PubMed に無かった論文を足す。同じ論文は PubMed の記録に S2 の要約などを足す。"""
        out = list(pubmed)
        for r in others:
            same = next((p for p in pubmed if (r["doi"] and r["doi"].lower() == p["doi"].lower())
                         or (ssci.same_title(p["title"], r["title"]) and _close_years(p.get("year"), r.get("year")))),
                        None)
            if same is None:
                out.append(r)
                continue
            same["found_in"] = list(dict.fromkeys([*same.get("found_in", []), *r.get("found_in", [])]))
            same["tldr"] = same["tldr"] or r["tldr"]
            same["abstract"] = same["abstract"] or r["abstract"]
            same["citation_count"] = max(same["citation_count"], r["citation_count"])
            same["oa_pdf"] = same["oa_pdf"] or r["oa_pdf"]
        if bulk:
            out.sort(key=lambda p: p.get("citation_count") or 0, reverse=True)
        return out

    def medline_journal(self, name_or_issn: str) -> Optional[bool]:
        """誌（名前か ISSN）が今も MEDLINE に索引されているか（NLM Catalog）。"""
        q = name_or_issn.strip()
        if ISSN_RE.match(q):
            return bool(self._esearch(f"{q}[issn] AND currentlyindexed[All]", 1, db="nlmcatalog").get("idlist"))
        # [Title] は語句を含む誌も拾う（"Lancet" に 18 誌）ので、正式な誌名か略称が同じものだけを見る
        # NLM の誌名に "The" は付かないことがある（"The Lancet" は "Lancet (London, England)"）
        name = re.sub(r"^the\s+", "", q, flags=re.IGNORECASE)
        ids = self._esearch(f'"{name}"[Title] AND currentlyindexed[All]', 50, db="nlmcatalog").get("idlist") or []
        if not ids:
            return False
        result = (self._pubmed("esummary.fcgi", {"db": "nlmcatalog", "id": ",".join(ids), "retmode": "json"})
                  .get("result") or {})
        key = journal_key(q)
        for uid in result.get("uids") or []:
            item = result.get(uid) or {}
            names = [item.get("medlineta") or "", *(t.get("title", "") for t in item.get("titlemainlist") or [])]
            if key in {journal_key(re.sub(r"\.$", "", n)) for n in names}:
                return True
        return False

    def get_paper_medical(self, identifier: str) -> Dict[str, Any]:
        """医学のサーベイの 1 本: DOI ならまず PubMed で引く（書誌が確かで、S2 のレート制限を待たない）。
        PubMed に無い・PubMed が失敗したら、ふつうの取得（S2 → OpenAlex）にする。"""
        ident = parse_identifier(identifier)
        if ident["type"] == "doi":
            try:
                ids = self._esearch(f'"{ident["value"]}"[doi]', 1).get("idlist") or []
                records = self._pubmed_fetch(ids)
            except ApiError as e:
                print("[Notice] " + t("{error} → PubMed's details are not added", error=e), file=sys.stderr)
                records = []
            if records:
                self._enrich_pubmed(records)
                return records[0]
        return self.get_paper(identifier)

    def pmc_fulltext(self, pmcid: str) -> str:
        """Europe PMC の全文（OA の論文だけ。ページ区切りは無い）。無ければ空。"""
        try:
            return jats_fulltext(self._europepmc(f"/{pmcid}/fullTextXML"))
        except ApiError as e:
            if e.status != 404:
                raise
            return ""

    # ---- Public interface ----

    def search(self, query: str, limit: int = 20, year: Optional[str] = None, bulk: bool = False,
               journals: Sequence[str] = ()) -> List[Dict[str, Any]]:
        """S2 で検索し、結果を OpenAlex で DOI 照合する。S2 が失敗したらエラー。

        誌を指定しない検索では OpenAlex の検索は使わない（題名・要旨の検索の精度が低い）。
        journals を渡すと、その誌（正式な誌名か ISSN）に載った論文だけ。このときは OpenAlex でも、誌を
        source ID で絞って検索し、S2 に無かったものを足す: S2 は誌名（venue）が空の論文が多く、venue での
        絞り込みからは黙って落ちる。誌の絞り込みは ID で確かに効くので、取りこぼしを拾う補助に使える。
        OpenAlex が失敗したら S2 の結果だけを返す。どう使ったかは self.last_search に残す。"""
        s2 = [dict(r, found_in=["SemanticScholar"]) for r in self._search_s2(query, limit, year, bulk, journals)]
        self.last_search = {}
        failed: Optional[ApiError] = None
        ids: Dict[str, str] = {}
        if journals:
            try:
                ids = self.journal_source_ids(journals)
            except ApiError as e:
                failed = e
        records = self._verify_with_openalex(s2)
        if not journals:
            return records
        missing = [j for j in journals if j not in ids]
        if not failed and missing:
            print("[Notice] " + t("OpenAlex does not know the journal {names}, so it was searched in S2 only",
                                  names=" / ".join(missing)), file=sys.stderr)
        if not failed and ids:
            try:
                extra = self._search_openalex(query, limit, year, bulk, list(ids.values()))
            except ApiError as e:
                failed = e
            else:
                records = merge_found(records, extra, bulk)
                self.last_search = {"openalex": "used", "sources": ids}
        if failed:
            print("[Notice] " + t("{error} → only the S2 results (OpenAlex was not searched for the journals)",
                                  error=failed), file=sys.stderr)
            self.last_search = {"openalex": "failed"}
        return records

    def get_paper(self, identifier: str) -> Dict[str, Any]:
        """S2 で取得して DOI 照合する。S2 に無い（404）DOI / OpenAlex ID は OpenAlex から取得する。"""
        ident = parse_identifier(identifier)
        if ident["type"] == "pmid":
            records = self._pubmed_fetch([ident["value"]])
            if not records:
                raise ApiError("PubMed", t("PubMed does not know the PMID {id}", id=ident["value"]), 404)
            self._enrich_pubmed(records)
            return records[0]
        if ident["s2_id"]:
            try:
                return self.use_issue_year(
                    self.complete_abstracts(self._verify_with_openalex([self._get_paper_s2(ident["s2_id"])]))[0])
            except ApiError as e:
                if e.status != 404:
                    raise
                print("[Notice] " + t("Not in Semantic Scholar; fetching it from OpenAlex: {id}", id=ident["value"]),
                      file=sys.stderr)
        try:
            return self.use_issue_year(self.complete_abstracts([self._get_paper_openalex(ident)])[0])
        except ApiError as e:
            if e.status != 404:
                raise
            raise ApiError("OpenAlex", t("{id} is in neither Semantic Scholar nor OpenAlex (perhaps a domestic "
                                         "journal, a very recent paper or a wrong DOI)", id=ident["value"]), 404)

    def get_linked(self, identifier: str, kind: str, limit: int = 10, sort: str = "recent") -> List[Dict[str, Any]]:
        """
        kind: "citations"（この論文を引用している論文）| "references"（この論文の参考文献）
        sort: "recent" は S2（S2 に無い論文なら OpenAlex）、"cited" は被引用数順にソートできる OpenAlex
        """
        ident = parse_identifier(identifier)
        if sort == "recent" and ident["s2_id"]:
            try:
                return self._verify_with_openalex(self._linked_s2(ident["s2_id"], kind, limit))
            except ApiError as e:
                if e.status != 404:
                    raise
                print("[Notice] " + t("{error}: {id} → fetching it from OpenAlex (by citations)", error=e, id=ident["value"]),
                      file=sys.stderr)
        return self._linked_openalex(ident, kind, limit)

    # ---- Snowballing (OpenAlex) ----

    def openalex_works(self, dois: List[str] = (), openalex_ids: List[str] = (),
                       select: str = OPENALEX_SELECT) -> List[Dict[str, Any]]:
        """DOI / OpenAlex ID で OpenAlex の work を（生の JSON のまま）まとめて取得する。"""
        works = []
        for name, values in (("doi", [d.lower() for d in dois]), ("openalex", list(openalex_ids))):
            for i in range(0, len(values), OPENALEX_BATCH):
                data = self._openalex("/works", {"filter": f"{name}:" + "|".join(values[i:i + OPENALEX_BATCH]),
                                                 "per_page": OPENALEX_BATCH, "select": select})
                works.extend(data.get("results") or [])
        return works

    def citing_work_ids(self, work_id: str, limit: int) -> List[str]:
        """work_id を引用している論文の OpenAlex ID（被引用数の多い順）。"""
        data = self._openalex("/works", {"filter": f"cites:{work_id}", "sort": "cited_by_count:desc",
                                         "per_page": min(limit, 200), "select": "id"})
        return [w["id"].replace("https://openalex.org/", "") for w in data.get("results") or []]
