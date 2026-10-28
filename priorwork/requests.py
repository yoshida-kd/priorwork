"""ほかの道具（Octavo）からの依頼（`priorwork requests`）。

Octavo は、依頼文をクリップボードで渡す代わりに、Priorwork のワークスペースの受け取り場所
（`.priorwork/requests/<id>.json`）に置く。Priorwork のサイドバーがそれを出し、エージェントが
`./priorwork requests <id>` で中身を読んで進め、終わったら `--done` で記録する（Octavo はその記録を読める）。

依頼の形（`priorwork-request` 版 1。見本は tests/fixtures/request.json。Octavo との約束）:
  書くのは Octavo: format, version, id, from, project（Octavo のプロジェクトの根）, manuscript（原稿。無ければ null）,
                   kind（start: 原稿からサーベイを作る / use-surveys: あるサーベイを使う / other）, text（依頼の文）, created_at
  書くのは Priorwork: status（open / done / declined）, survey（進めたサーベイ）, done_at, note
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .i18n import t
from .workspace import meta_dir

REQUEST_FORMAT = "priorwork-request"
REQUEST_VERSION = 1
STATUSES = ("open", "done", "declined")


class RequestError(Exception):
    pass


def requests_dir(root: Path) -> Path:
    return meta_dir(root) / "requests"


def _load(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("format") != REQUEST_FORMAT:
        return None
    data.setdefault("id", path.stem)
    data.setdefault("status", "open")
    data["path"] = str(path)
    return data


def all_requests(root: Path) -> List[Dict[str, Any]]:
    """受け取った依頼（古い順）。読めないファイルや、ほかの形のファイルは飛ばす。"""
    d = requests_dir(root)
    found = [r for r in (_load(p) for p in sorted(d.glob("*.json"))) if r] if d.is_dir() else []
    return sorted(found, key=lambda r: (r.get("created_at") or "", r["id"]))


def open_requests(root: Path) -> List[Dict[str, Any]]:
    return [r for r in all_requests(root) if r["status"] == "open"]


def get(root: Path, request_id: str) -> Dict[str, Any]:
    hits = [r for r in all_requests(root) if r["id"] == request_id or r["id"].startswith(request_id)]
    if len(hits) != 1:
        raise RequestError(t("No request {id}. The open ones: {ids}", id=request_id,
                             ids=", ".join(r["id"] for r in open_requests(root)) or t("(none)"))
                           if not hits else t("More than one request starts with {id}", id=request_id))
    return hits[0]


def close(root: Path, request_id: str, status: str, survey: str = "", note: str = "", now: str = "") -> Dict[str, Any]:
    """依頼に結果を書き込む（Octavo が書いた欄はそのまま）。"""
    if status not in STATUSES:
        raise RequestError(t("The status is one of {choices}: {status}", choices=" / ".join(STATUSES), status=status))
    r = get(root, request_id)
    path = Path(r.pop("path"))
    r.update(status=status, survey=survey or r.get("survey") or None, note=note or r.get("note") or "",
             done_at=now if status != "open" else None)
    fd, tmp = tempfile.mkstemp(prefix=path.stem + ".", suffix=".tmp", dir=path.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    r["path"] = str(path)
    return r


def summary(r: Dict[str, Any], width: int = 80) -> str:
    text = re.sub(r"\s+", " ", r.get("text") or "").strip()
    return text if len(text) <= width else text[:width - 1] + "…"
