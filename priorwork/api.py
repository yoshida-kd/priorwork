"""
Literature API client.

役割分担:
- Semantic Scholar: 検索・論文取得・引用関係（主）
- OpenAlex: S2 の結果を DOI で照合して書誌情報（誌名・ISSN・巻号）を補正、
  S2 に無い DOI の取得、被引用数順の引用関係

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
from pathlib import Path
from typing import Any, Dict, List, Optional
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
    "openAccessPdf,tldr,externalIds,url,fieldsOfStudy,publicationTypes"
)
# bulk 検索は tldr を返せない
S2_BULK_FIELDS = S2_PAPER_FIELDS.replace(",tldr", "")
S2_LINKED_FIELDS = "paperId,title,authors,year,venue,publicationVenue,journal,citationCount,externalIds,publicationTypes"
OPENALEX_SELECT = (
    "id,doi,title,display_name,publication_year,type,authorships,primary_location,biblio,"
    "cited_by_count,referenced_works_count,abstract_inverted_index,open_access,topics"
)

OPENALEX_BATCH = 50
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
    Returns {"type": "doi|s2|arxiv|openalex|raw", "value": ..., "s2_id": ...}
    """
    raw = identifier.strip()

    m = re.search(r"doi\.org/(10\.\d{4,9}/\S+)", raw, re.IGNORECASE)
    if m or re.match(r"^(doi:)?10\.\d{4,9}/\S+$", raw, re.IGNORECASE):
        doi = m.group(1) if m else re.sub(r"^doi:", "", raw, flags=re.IGNORECASE)
        return {"type": "doi", "value": doi, "s2_id": f"DOI:{doi}"}

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
        "verified": False,   # OpenAlex で DOI 照合済みか
        "warnings": [],
    }
    rec.update({k: v for k, v in kw.items() if v is not None})
    # 雑誌側の脚注記号（"...Jobs*" など）が Markdown の強調を壊すので落とす
    rec["title"] = re.sub(r"\s*[*†‡]+$", "", rec["title"])
    rec["warnings"] = list(rec["warnings"])
    if re.search(r",\s*(?:edited\s+)?by\s+[A-Z]", rec["title"]) or re.fullmatch(r"(\d+)\s*-+\s*\1", rec["pages"]):
        rec["warnings"].append(t("May be a book review or comment (guessed from the title or the page range)"))
    rec["ssci"] = classify_paper(rec)
    return rec


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
        fields=p.get("fieldsOfStudy") or [],
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
    work_id = (w.get("id") or "").replace("https://openalex.org/", "")
    return _record(
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
    )


# ---------------- Client ----------------

class LiteratureClient:
    def __init__(self, use_cache: bool = True):
        self.s2_api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or os.environ.get("S2_API_KEY")
        self.openalex_api_key = os.environ.get("OPENALEX_API_KEY")
        self.openalex_mailto = os.environ.get("OPENALEX_MAILTO")
        self.use_cache = use_cache and os.environ.get("PRIORWORK_NO_CACHE") != "1"
        self.max_retries = int(os.environ.get("PRIORWORK_MAX_RETRIES") or 5)
        self._last_request: Dict[str, float] = {}

    # ---- HTTP ----

    def _throttle(self, service: str):
        interval = {"SemanticScholar": 1.1 if self.s2_api_key else 1.5}.get(service, 0.2)
        elapsed = time.time() - self._last_request.get(service, 0.0)
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_request[service] = time.time()

    def _get_json(self, service: str, url: str, params: Dict[str, Any], headers: Dict[str, str],
                  secret_params: Optional[Dict[str, Any]] = None) -> Any:
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
                    data = resp.json()
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

    # ---- Semantic Scholar ----

    def _search_s2(self, query: str, limit: int, year: Optional[str], bulk: bool) -> List[Dict[str, Any]]:
        if bulk:
            # bulk 検索: AND(+) / OR(|) / 除外(-) / "フレーズ" が使え、被引用数順に最大 1000 件返る
            data = self._s2("/paper/search/bulk", {"query": query, "fields": S2_BULK_FIELDS, "year": year,
                                                    "sort": "citationCount:desc"})
        else:
            data = self._s2("/paper/search", {"query": query, "limit": min(limit, 100), "fields": S2_PAPER_FIELDS,
                                               "year": year})
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
        except ApiError as e:
            print("[Notice] " + t("{error} → the DOIs are not checked with OpenAlex (the details from S2 are kept)",
                                  error=e), file=sys.stderr)
            for r in with_doi:
                r["warnings"].append(t("DOI not verified"))
            return records

        for r in with_doi:
            w = works.get(r["doi"].lower())
            if not w:
                r["warnings"].append(t("OpenAlex does not know the DOI (verify the DOI)"))
                continue
            oa = from_openalex(w)
            if ssci.normalize_title(oa["title"]) != ssci.normalize_title(r["title"]):
                r["warnings"].append(t("The DOI points to another title: \"{title}\" (verify the DOI)", title=oa["title"]))
            s2_journal, s2_status = r["journal_name"], r["ssci"]["status"]
            # Zotero 取り込み・SSCI 照合に使う書誌情報は、DOI の実体（OpenAlex）側で丸ごと置き換える
            for field in ("journal_name", "issns", "source_type", "publication_types", "volume", "issue", "pages"):
                r[field] = oa[field]
            if not r["abstract"]:
                r["abstract"] = oa["abstract"]
            r["verified"] = True
            r["openalex_id"] = oa["openalex_id"]
            r["ssci"] = ssci.classify_paper(r)
            if r["ssci"]["status"] == ssci.PREPRINT and s2_status != ssci.PREPRINT and s2_journal:
                r["warnings"].append(t("S2 gives the journal as \"{journal}\", but the DOI is a working paper / preprint version "
                                         "(find the DOI of the published version)", journal=s2_journal))
        return records

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

    # ---- Public interface ----

    def search(self, query: str, limit: int = 20, year: Optional[str] = None, bulk: bool = False) -> List[Dict[str, Any]]:
        """S2 で検索し、結果を OpenAlex で DOI 照合する。S2 が失敗したらエラー（OpenAlex 検索は精度が低いため使わない）。"""
        return self._verify_with_openalex(self._search_s2(query, limit, year, bulk))

    def get_paper(self, identifier: str) -> Dict[str, Any]:
        """S2 で取得して DOI 照合する。S2 に無い（404）DOI / OpenAlex ID は OpenAlex から取得する。"""
        ident = parse_identifier(identifier)
        if ident["s2_id"]:
            try:
                return self._verify_with_openalex([self._get_paper_s2(ident["s2_id"])])[0]
            except ApiError as e:
                if e.status != 404:
                    raise
                print("[Notice] " + t("Not in Semantic Scholar; fetching it from OpenAlex: {id}", id=ident["value"]),
                      file=sys.stderr)
        try:
            return self._get_paper_openalex(ident)
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
