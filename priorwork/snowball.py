"""
採用論文の参考文献・被引用をたどって候補を集める（`priorwork snowball`）。

採用論文のうち何本と引用関係にあるか（リンク数）で並べるので、
キーワード検索では拾えない定番論文や、分野の議論の中心にある後続研究が上に来る。
"""

from collections import Counter
from typing import Any, Dict, List, Tuple

from .api import from_openalex
from .survey import INCLUDED, Survey


def snowball(survey: Survey, client: Any, direction: str = "both", per_paper: int = 50,
             limit: int = 15, min_links: int = 0) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns (候補レコードのリスト（リンク数の多い順、`_links` 付き）, 集計情報)。
    min_links=0 のときは採用論文の数に応じて自動で決める（3 本以上なら 2）。
    """
    included = survey.by_status(INCLUDED)
    if not included:
        return [], {"seeds": 0}

    seeds = client.openalex_works(
        dois=[e["record"]["doi"] for e in included if e["record"].get("doi")],
        openalex_ids=[e["record"]["openalex_id"] for e in included
                      if not e["record"].get("doi") and e["record"].get("openalex_id")],
        select="id,doi,referenced_works",
    )
    seed_ids = {w["id"].replace("https://openalex.org/", "") for w in seeds}

    refs: Counter = Counter()
    cites: Counter = Counter()
    for w in seeds:
        if direction in ("both", "references"):
            refs.update({r.replace("https://openalex.org/", "") for r in w.get("referenced_works") or []})
        if direction in ("both", "citations"):
            cites.update(set(client.citing_work_ids(w["id"].replace("https://openalex.org/", ""), per_paper)))

    known = {e["record"].get("openalex_id") for e in survey.papers} | seed_ids
    links = Counter()
    for c in (refs, cites):
        for wid, n in c.items():
            if wid not in known:
                links[wid] += n

    threshold = min_links or (2 if len(seeds) >= 3 else 1)
    # 取得件数を抑えるため、リンク数の多い順に上限つきで詳細を取る
    top_ids = [wid for wid, n in links.most_common() if n >= threshold][: max(limit * 4, 50)]
    records = []
    for w in client.openalex_works(openalex_ids=top_ids):
        rec = dict(from_openalex(w), verified=True)
        wid = rec["openalex_id"]
        rec["_links"] = {"total": links[wid], "references": refs.get(wid, 0), "citations": cites.get(wid, 0)}
        if survey.find(rec) is None:
            records.append(rec)
    records.sort(key=lambda r: (r["_links"]["total"], r["citation_count"]), reverse=True)
    stats = {"seeds": len(seeds), "skipped": len(included) - len(seeds), "linked": len(links), "threshold": threshold}
    return records, stats
