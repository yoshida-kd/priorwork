#!/usr/bin/env python3
"""
SSCI (Web of Science Social Sciences Citation Index) status classification.

SSCI 収録の可否は Clarivate の Master Journal List でしか確定できない。
そのため判定は次の優先順で行う:

1. 収録リスト CSV（.priorwork/data/ssci_journals.csv など）があれば ISSN / 誌名で照合 → 確定判定
2. リストが無ければ、内蔵の主要誌リストと誌名の完全一致 → 「推定」
3. それ以外は「学術誌（SSCI未確認）」「プレプリント／WP」「掲載誌不明」に分類
"""

import csv
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .i18n import language, tl
from .workspace import DATA_DIR, ROOT

DEFAULT_SSCI_LIST = DATA_DIR / "ssci_journals.csv"

# Status tiers (higher = preferred in ranking)
SSCI = "ssci"                    # 収録リストで照合済み
SSCI_LIKELY = "ssci_likely"      # リスト未設定、内蔵リストの誌名と一致
JOURNAL = "journal"              # 学術誌だが SSCI 未確認
NOT_SSCI = "not_ssci"            # 収録リストに無い学術誌
BOOK = "book"                    # 書籍・書籍の章
UNKNOWN = "unknown"              # 掲載誌不明
PREPRINT = "preprint"            # WP / プレプリント / 学位論文など

TIER = {SSCI: 5, SSCI_LIKELY: 4, JOURNAL: 3, NOT_SSCI: 2, BOOK: 1, UNKNOWN: 1, PREPRINT: 0}

# 英語が原文。表示・レポートでは badge() で言語を選ぶ（状態ファイルには英語のまま入る）
BADGE = {
    SSCI: "✅ SSCI (checked against the list)",
    SSCI_LIKELY: "🟡 Probably SSCI (guessed from the journal name; verify)",
    JOURNAL: "🔍 Journal (SSCI not verified)",
    NOT_SSCI: "⚪ Not in SSCI (checked against the list)",
    BOOK: "📕 Book (outside SSCI)",
    UNKNOWN: "❓ Unknown venue",
    PREPRINT: "❌ Working paper / preprint",
}


def badge(status: str, lang: Optional[str] = None) -> str:
    """判定の表示。lang を省くと表示の言語（i18n.language()）。"""
    return tl(lang or language(), BADGE.get(status, BADGE[UNKNOWN]))

# 内蔵リスト: SSCI 収録が広く知られる主要誌（完全一致で照合。網羅的ではない）
KNOWN_SSCI_JOURNALS = [
    # Economics
    "American Economic Review", "Quarterly Journal of Economics", "Journal of Political Economy",
    "Review of Economic Studies", "Econometrica", "Journal of Economic Literature",
    "Journal of Economic Perspectives", "American Economic Review: Insights",
    "American Economic Journal: Applied Economics", "American Economic Journal: Economic Policy",
    "American Economic Journal: Macroeconomics", "American Economic Journal: Microeconomics",
    "Economic Journal", "Journal of the European Economic Association", "Review of Economics and Statistics",
    "Journal of Monetary Economics", "Journal of Econometrics", "Journal of Labor Economics",
    "Journal of Public Economics", "Journal of Development Economics", "Journal of International Economics",
    "Journal of Economic Growth", "Journal of Human Resources", "ILR Review",
    "Industrial and Labor Relations Review", "Labour Economics", "Journal of Health Economics",
    "Journal of Urban Economics", "Journal of Economic History", "Explorations in Economic History",
    "World Development", "Economic Policy", "Journal of Finance", "Journal of Financial Economics",
    "Review of Financial Studies", "Annual Review of Economics", "Southern Economic Journal",
    "Journal of Law and Economics", "Journal of Legal Studies", "Journal of Law, Economics, and Organization",
    # Sociology / Demography
    "American Sociological Review", "American Journal of Sociology", "Social Forces",
    "Sociological Methods & Research", "British Journal of Sociology", "European Sociological Review",
    "Social Science Research", "Social Networks", "Sociology", "Work and Occupations",
    "Gender & Society", "Journal of Marriage and Family", "Demography", "Annual Review of Sociology",
    "Population and Development Review", "Social Science & Medicine",
    # Political Science / IR
    "American Political Science Review", "American Journal of Political Science", "Journal of Politics",
    "British Journal of Political Science", "Comparative Political Studies", "International Organization",
    "World Politics", "Comparative Politics", "Journal of Conflict Resolution", "Political Analysis",
    "Political Behavior", "International Studies Quarterly", "Security Studies",
    "Annual Review of Political Science", "European Journal of Political Research",
    "Journal of Peace Research", "Public Opinion Quarterly",
    # Management / Business
    "Academy of Management Journal", "Academy of Management Review", "Administrative Science Quarterly",
    "Strategic Management Journal", "Organization Science", "Journal of Management",
    "Journal of Marketing", "Journal of Marketing Research", "Journal of Consumer Research",
    "Management Science", "Research Policy", "Journal of Business Ethics", "Human Relations",
    "Organization Studies", "Journal of International Business Studies", "Journal of Management Studies",
    # Psychology
    "Psychological Review", "Psychological Bulletin", "Psychological Science",
    "Journal of Personality and Social Psychology", "Journal of Applied Psychology",
    "Annual Review of Psychology", "Journal of Experimental Psychology: General",
    # Public administration / Law
    "Journal of Public Administration Research and Theory", "Public Administration Review",
    "Governance", "Journal of Policy Analysis and Management", "Harvard Law Review", "Yale Law Journal",
    # Multidisciplinary social science
    "Nature Human Behaviour",
]

# 単語境界つきで照合するプレプリント / WP / 非査読ソースのパターン
PREPRINT_PATTERNS = [
    r"arxiv", r"ssrn", r"social science research network", r"biorxiv", r"medrxiv",
    r"socarxiv", r"psyarxiv", r"edarxiv", r"osf preprints?", r"research square", r"preprints\.org",
    r"national bureau of economic research", r"nber", r"cepr", r"centre for economic policy research",
    r"repec", r"mpra", r"econstor", r"zenodo", r"figshare", r"hal",
    r"working papers?", r"discussion papers?", r"policy research working paper", r"policy papers?",
    r"occasional papers?", r"white papers?", r"staff reports?", r"mimeo", r"conference draft",
    r"dissertations?", r"repository",
]
_PREPRINT_RE = re.compile(r"\b(?:" + "|".join(PREPRINT_PATTERNS) + r")\b", re.IGNORECASE)

# OpenAlex work.type / source.type、S2 publicationTypes のうち非査読扱いにするもの
NON_PEER_REVIEWED_TYPES = {"preprint", "report", "dissertation", "posted-content", "repository", "other"}
BOOK_TYPES = {"book", "book-chapter", "booksection", "monograph", "ebook platform"}


def normalize_title(name: str) -> str:
    s = (name or "").lower().replace("&", " and ")
    s = re.sub(r"^the\s+", "", s.strip())
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def normalize_issn(issn: str) -> str:
    s = re.sub(r"[^0-9Xx]", "", issn or "").upper()
    return f"{s[:4]}-{s[4:]}" if len(s) == 8 else ""


class SSCIJournalList:
    """Clarivate Master Journal List の CSV を ISSN / 誌名で引ける形にしたもの。"""

    def __init__(self, path: Optional[Path]):
        self.path = path
        self.issns: Set[str] = set()
        self.titles: Set[str] = set()
        if path and path.exists():
            self._load(path)

    @property
    def loaded(self) -> bool:
        return bool(self.issns or self.titles)

    def _load(self, path: Path):
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            title_cols = [c for c in fields if "title" in c.lower()]
            issn_cols = [c for c in fields if "issn" in c.lower()]
            for row in reader:
                for c in title_cols:
                    t = normalize_title(row.get(c, ""))
                    if t:
                        self.titles.add(t)
                for c in issn_cols:
                    i = normalize_issn(row.get(c, ""))
                    if i:
                        self.issns.add(i)

    def contains(self, journal_name: str, issns: Iterable[str]) -> bool:
        if any(normalize_issn(i) in self.issns for i in issns):
            return True
        return normalize_title(journal_name) in self.titles


_KNOWN_TITLES = {normalize_title(t) for t in KNOWN_SSCI_JOURNALS}
_list_cache: Optional[SSCIJournalList] = None


def get_ssci_list() -> SSCIJournalList:
    global _list_cache
    if _list_cache is None:
        env_path = os.environ.get("SSCI_JOURNAL_LIST")
        path = Path(env_path).expanduser() if env_path else DEFAULT_SSCI_LIST
        if not env_path and not path.exists():
            # Master Journal List からダウンロードしたままのファイル名（"Social Sciences Citation Index (SSCI).csv" など）も拾う
            candidates = sorted(p for p in DEFAULT_SSCI_LIST.parent.glob("*.csv") if "ssci" in p.name.lower())
            path = candidates[0] if candidates else path
        if not path.is_absolute():
            path = ROOT / path
        _list_cache = SSCIJournalList(path)
    return _list_cache


def classify(
    journal_name: str,
    issns: List[str],
    work_types: Iterable[str] = (),
    source_type: str = "",
) -> Tuple[str, str]:
    """Returns (status, badge)."""
    types = {t.lower() for t in work_types if t}
    source_type = (source_type or "").lower()

    if (
        (journal_name and _PREPRINT_RE.search(journal_name))
        or types & NON_PEER_REVIEWED_TYPES
        or source_type in NON_PEER_REVIEWED_TYPES
    ):
        return PREPRINT, BADGE[PREPRINT]

    if types & BOOK_TYPES or source_type in BOOK_TYPES:
        return BOOK, BADGE[BOOK]

    if not journal_name and not issns:
        return UNKNOWN, BADGE[UNKNOWN]

    ssci_list = get_ssci_list()
    if ssci_list.loaded:
        if ssci_list.contains(journal_name, issns):
            return SSCI, BADGE[SSCI]
    elif normalize_title(journal_name) in _KNOWN_TITLES:
        return SSCI_LIKELY, BADGE[SSCI_LIKELY]

    is_journal = (
        bool(issns)
        or source_type in {"journal", "book series"}
        or bool(types & {"journalarticle", "review", "article"})
    )
    if not is_journal:
        return UNKNOWN, BADGE[UNKNOWN]
    if ssci_list.loaded:
        return NOT_SSCI, BADGE[NOT_SSCI]
    return JOURNAL, BADGE[JOURNAL]


def classify_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    status, badge = classify(
        journal_name=paper.get("journal_name", ""),
        issns=paper.get("issns", []),
        work_types=paper.get("publication_types", []),
        source_type=paper.get("source_type", ""),
    )
    return {"status": status, "badge": badge, "tier": TIER[status]}
