"""priorwork — 社会科学の先行研究サーベイを対話的に作るための CLI。

表示する文字列は英語が原文で、日本語は lang_ja.py（i18n.t）。VS Code の拡張機能は `--json` の出力を読む。
その形は tests/test_cli_json.py と拡張機能側の型（vscode-extension/src/cli.ts）の両方で押さえている。
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__, derived, i18n, scaffold, settings, ssci
import requests

from .api import RETRY_STATUSES, ApiError, LiteratureClient
from .check import ERROR, INFO, WARN, check_survey
from .doctor import NG, OK, run_checks
from .export import FORMATS, export, export_draft
from .fulltext import FulltextError, fetch_fulltext, incomplete_fulltext
from .i18n import t, tl
from .snowball import snowball
from .survey import (
    CANDIDATE, DEFAULT_DEPTH, DEPTHS, EVIDENCE_KEYS, EXCLUDED, INCLUDED, MAYBE, MODES, PURPOSES, SEARCH_FIELDS,
    STATUSES, Survey,
    SurveyError, author_short, off_field, evidence_key, evidence_label, now_iso, status_label, status_trail,
)
from . import octavo
from .manuscript import ManuscriptError
from .workspace import ROOT, meta_dir, workspace_lang
from .zotero import ZoteroClient, ZoteroError, write_allowed
from . import requests as requestsmod

SORTS = ("citations", "relevance", "recent", "cpy")
# --limit の既定。full のサーベイでは多めに取る（少ない件数から選別すると、ほとんど残らない）
DEFAULT_LIMIT = {"quick": 10, "full": 25}
# full のサーベイで「検索が足りない」とみなす目安（次にやることに出す）
FULL_MIN_QUERIES = 6
FULL_MIN_FOUND = 80
# サブコマンドの説明（英語が原文。t() で訳す）
STATUS_COMMANDS = [("include", "include"), ("exclude", "exclude (--reason is required)"), ("maybe", "maybe"),
                   ("reset", "back to candidate")]
LINK_COMMANDS = [("citations", "papers citing this paper"), ("references", "the references of this paper")]

# `priorwork --help` の説明（英語が原文。行ごとに訳す）
USAGE_LINES = [
    "priorwork — build literature reviews for the social sciences, in conversation with an AI agent",
    "",
    "Workspace",
    "  init [DIR]                 set up a workspace (reports/, .priorwork/, AGENTS.md, skills, …)",
    "  sync [--force|--diff]      update AGENTS.md, the skills and ./priorwork to the engine's version",
    "  doctor [--online]          diagnose the setup (API keys, SSCI list, engine version, …)",
    "  upgrade [--to X.Y.Z]       update the engine to the latest (or given) version, then sync",
    "  settings                   show or change the API keys, Zotero and the SSCI list",
    "",
    "Surveys",
    "  status [SURVEY]            list the surveys / progress and next steps",
    "  new TOPIC --slug SLUG      create a survey (reports/YYYYMMDD_<slug>.md and .priorwork/surveys/*.json)",
    "  new ... --manuscript PATH  start from your manuscript (--purpose complete: fill in what it lacks; draft: its sections 1–3; advice: advice on it)",
    "  read PATH                  print the text of a manuscript (.md, .qmd, .html, .docx, .pdf, … or a folder)",
    "  requests [ID]              requests from Octavo (--done / --decline records the outcome)",
    "  scope SURVEY ...           set the scope (research question, period, criteria)",
    "  archive SURVEY [--undo]    hide a survey from the list, keeping its files (e.g. one that was redone)",
    "  list SURVEY                list the papers (numbers, decisions, SSCI)",
    "  include / exclude / maybe  record decisions (e.g. priorwork include SURVEY 2 5 7)",
    "  add SURVEY DOI...          register papers by DOI (included by default)",
    "  card SURVEY N [--set ...]  show or fill in the card of an included paper",
    "  render SURVEY              regenerate the managed blocks of the Markdown",
    "  export SURVEY              write the report for reading (HTML / Word / Markdown)",
    "  export SURVEY --draft      write the draft of the manuscript's sections 1–3 with its references",
    "  check SURVEY               find empty fields, unregistered citations and DOI mismatches",
    "  audit SURVEY --by MODEL    record an audit by another AI model (optional; when you ask for one)",
    "  fulltext SURVEY N          get the full text (Zotero / open-access PDF)",
    "  zotero [SURVEY]            check the Zotero link / which included papers are in Zotero",
    "  zotero SURVEY --collection NAME   link a Zotero collection (--import registers its papers, --dois lists the DOIs to add)",
    "  zotero SURVEY --add [--dry-run]   add the included papers to the linked collection (only with ZOTERO_WRITE=1; --undo takes it back)",
    "",
    "Finding literature",
    "  search QUERY [--into SURVEY]   search (--into registers the results as candidates)",
    "  snowball SURVEY                register candidates from the citations of the included papers",
    "  get / citations / references   paper details and citation links",
    "  journal NAME_OR_ISSN           the SSCI status of a journal",
]


# ---------------- Helpers ----------------

def rank_and_filter(papers: List[Dict[str, Any]], include_preprints: bool = False, ssci_only: bool = False,
                    sort: str = "citations") -> List[Dict[str, Any]]:
    """同一論文を統合し、除外ルールを適用して「SSCI 判定 → 指定した順」に並べる。"""
    this_year = date.today().year

    def secondary(p):
        if sort == "citations":
            return p["citation_count"]
        if sort == "recent":
            return p.get("year") or 0
        if sort == "cpy":  # 年あたり被引用数
            return p["citation_count"] / max(1, this_year - (p.get("year") or this_year) + 1)
        return 0  # relevance: 検索 API の返却順を保つ（安定ソート）

    best: Dict[str, Dict[str, Any]] = {}
    for p in papers:
        k = ssci.normalize_title(p["title"]) or p["doi"].lower() or p["id"]
        if k not in best or (p["ssci"]["tier"], p["citation_count"]) > (best[k]["ssci"]["tier"], best[k]["citation_count"]):
            best[k] = p

    kept = []
    for p in best.values():
        status = p["ssci"]["status"]
        if not include_preprints and status in (ssci.PREPRINT, ssci.BOOK, ssci.UNKNOWN):
            continue
        if ssci_only and status not in (ssci.SSCI, ssci.SSCI_LIKELY):
            continue
        kept.append(p)
    return sorted(kept, key=lambda p: (p["ssci"]["tier"], secondary(p)), reverse=True)


def print_paper(p: Dict[str, Any], prefix: str, abstract: bool = False, extra: str = ""):
    authors = ", ".join(p["authors"][:3]) + (" et al." if len(p["authors"]) > 3 else "")
    print(f"{prefix} {p['title']}")
    print(f"    {p['journal_name'] or 'N/A'} ({p['year'] or 'N/A'}) | {ssci.badge(p['ssci']['status'])}")
    print(f"    {authors or 'Unknown'} | " + t("cited by {n}", n=p["citation_count"]) + " | "
          f"{('DOI: ' + p['doi']) if p['doi'] else ('ID: ' + p['id'])}{extra}")
    for w in p.get("warnings", []):
        print(f"    ⚠️ {w}")
    if p.get("tldr"):
        print(f"    TL;DR: {p['tldr']}")
    elif abstract and p.get("abstract"):
        text = re.sub(r"\s+", " ", p["abstract"])
        print("    " + t("Abstract: {text}", text=text[:600] + ("…" if len(text) > 600 else "")))
    print()


def dump_json(data: Any):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def warn_if_no_ssci_list():
    if not ssci.get_ssci_list().loaded:
        print("[Notice] " + t("No SSCI journal list is set, so the SSCI status is guessed from the journal name."),
              file=sys.stderr)


def add_records(survey: Survey, records: List[Dict[str, Any]], found_by: str) -> List[tuple]:
    """候補として登録し、(entry, is_new) のリストを返す。"""
    return [survey.upsert(r, found_by) for r in records]


def entry_prefix(entry: Dict[str, Any], is_new: bool) -> str:
    state = t("new candidate") if is_new else t("already registered: {status}", status=status_label(entry["status"]))
    return f"#{entry['number']} [{state}]"


def render_and_report(survey: Survey):
    survey.save()
    survey.render()
    derived.render_all(survey)


def added_json(added: List[tuple]) -> List[Dict[str, Any]]:
    return [{"number": e["number"], "new": is_new, "status": e["status"], "title": e["record"]["title"]}
            for e, is_new in added]


# Zotero を見る処理の失敗は、status などを止めない（ネットワーク・キャッシュの読み書き・壊れた応答）
ZOTERO_SOFT_ERRORS = (ZoteroError, OSError, ValueError, requests.RequestException)


def survey_summary(s: Survey) -> Dict[str, Any]:
    return {"name": s.name, "topic": s.data["topic"], "created": s.data.get("created", ""), "version": s.version,
            "depth": s.depth, "mode": s.mode, "lang": s.lang, "report": str(s.md_path),
            "manuscript": s.manuscript or None, "purpose": s.purpose or None,
            "zotero_collection": s.zotero_collection or None, "archived": s.archived or None,
            "counts": s.counts(), "searches": len(s.data["searches"])}


def same_topic(s: Survey, surveys: List[Survey]) -> List[Survey]:
    """同じテーマ（大文字小文字・空白を無視）のほかのサーベイ（アーカイブしたものは除く）。"""
    key = re.sub(r"\s+", " ", s.data["topic"]).strip().lower()
    return [o for o in surveys if o.name != s.name and not o.archived
            and re.sub(r"\s+", " ", o.data["topic"]).strip().lower() == key]


# ---------------- Workspace commands ----------------

def _print_sync(result: "scaffold.SyncResult"):
    for rel in result.written:
        print("  " + t("updated: {path}", path=rel))
    for rel in result.removed:
        print("  " + t("removed: {path}", path=rel))
    for rel in result.skipped:
        print("  " + t("skipped (not written by priorwork): {path}  → to overwrite it, `priorwork sync --force`", path=rel))
    for rel in result.modified:
        print("  " + t("skipped (changed by hand): {path}  → see the diff with `priorwork sync --diff`, "
                       "overwrite with `--force`", path=rel))
    if not (result.written or result.removed or result.skipped or result.modified):
        print("  " + t("no changes"))


def cmd_init(args, client):
    root = Path(args.dir).resolve() if args.dir else ROOT
    result = scaffold.init(root, lang=args.lang)
    print(t("Workspace: {root} (priorwork {version}, {lang})", root=root, version=__version__,
            lang=workspace_lang(root)))
    _print_sync(result)
    print("\n" + t("Next: copy `.env.example` to `.env`, set your API keys and check with `./priorwork doctor`.\n"
                   "    Make the first commit and push it to a private GitHub repository "
                   "(e.g. `gh repo create <name> --private --source=. --push`).\n"
                   "    Then start a survey with `./priorwork new \"<topic>\" --slug <slug>`"))


def cmd_sync(args, client):
    if args.diff:
        return print(scaffold.diff(ROOT) or t("No differences"))
    print(t("Workspace: {root} (priorwork {version}, {lang})", root=ROOT, version=__version__, lang=workspace_lang(ROOT)))
    _print_sync(scaffold.sync(ROOT, force=args.force))


def cmd_doctor(args, client):
    checks = run_checks(ROOT, client if args.online else None)
    ng = sum(1 for c in checks if c[0] == NG)
    warn = sum(1 for c in checks if c[0] == "warn")
    if args.json:
        dump_json({"version": __version__, "root": str(ROOT), "lang": workspace_lang(ROOT),
                   "checks": [{"level": lv, "name": n, "message": m} for lv, n, m in checks], "ng": ng, "warn": warn})
    else:
        icons = {OK: "✅", "warn": "⚠️ ", NG: "❌"}
        for level, name, msg in checks:
            print(f"{icons[level]} {name}: {msg}")
        print("\n" + t("{ng|# problem|# problems} / {warn|# warning|# warnings}", ng=ng, warn=warn)
              + ("" if args.online else t(" (check the connections with `priorwork doctor --online`)")))
    if ng:
        sys.exit(1)


def cmd_settings(args, client):
    if args.import_ssci:
        got = settings.import_ssci(ROOT, Path(args.import_ssci))
        if not args.json:
            print(t("Imported the SSCI list: {file} ({n|# journal|# journals})", file=got["file"], n=got["journals"]))
    if args.stdin:
        try:
            values = json.loads(sys.stdin.read() or "{}")
        except ValueError as e:
            raise settings.SettingsError(t("Give the settings as a JSON object on stdin: {error}", error=e)) from e
        if not isinstance(values, dict) or not all(v is None or isinstance(v, str) for v in values.values()):
            raise settings.SettingsError(t("Give the settings as a JSON object on stdin: {error}",
                                           error='{"KEY": "value"}'))
        changed = settings.update(ROOT, values)
        if not args.json:
            print(t("Updated: {names}", names=", ".join(changed)) if changed else t("no changes"))
    if args.json:
        return dump_json(settings.status(ROOT))
    if not (args.stdin or args.import_ssci):
        st = settings.status(ROOT)
        print(st["env"] + ("" if st["exists"] else " " + t("(not created yet)")))
        for item in st["items"]:
            shown = t("set") if item["set"] else t("not set")
            if item["value"]:
                shown += f" ({item['value']})"
            print(f"  {item['key']}: {shown}")
        print(t("SSCI journal list") + ": " + (f"{st['ssci']['file']} ({st['ssci']['journals']})" if st["ssci"]["file"]
                                               else t("not set")))


def cmd_upgrade(args, client):
    version = scaffold.upgrade(ROOT, args.to)
    print(t("Updated the engine to {version}. Review the changes with `git diff requirements.txt AGENTS.md .agent` "
            "and commit them.", version=version))


# ---------------- Survey commands ----------------

def next_steps(s: Survey, zotero_missing: List[Dict[str, Any]], zotero_pending: int = 0) -> List[Dict[str, Any]]:
    """次にやること。id は VS Code の拡張機能がボタンに結びつける。"""
    c = s.counts()
    sc = s.data["scope"]
    unfilled = s.unfilled()
    steps: List[Dict[str, Any]] = []

    def step(sid: str, text: str, args: List[str]):
        steps.append({"id": sid, "text": text, "args": args})

    if not sc.get("question"):
        step("scope", t("Set the scope"), ["scope", s.name, "--question", "..."])
    if s.manuscript_changed():
        # 読んだ後に原稿が変わった: 読み直して、補完・下書き・助言のうち古くなったところを直す
        step("manuscript_changed", t("The manuscript has changed since it was read ({date}): read it again with "
                                     "`priorwork read {path} --for {name}` and update what it made stale",
                                     date=s.manuscript_read.get("at", "")[:10], path=s.manuscript, name=s.name),
             ["read", s.manuscript, "--for", s.name])
    if not s.data["searches"]:
        step("search", t("Search"), ["search", "<English query>", "--into", s.name])
    elif s.depth == "full":
        queries = sum(1 for q in s.data["searches"] if q["kind"] in ("search", "bulk") and q.get("hits"))
        found = len(s.papers)
        if queries < FULL_MIN_QUERIES or found < FULL_MIN_FOUND:
            step("search_more", t("Search more: a full survey usually needs {min_q}+ queries and {min_n}+ papers "
                                  "(now {queries|# query|# queries}, {n|# paper|# papers})",
                                  min_q=FULL_MIN_QUERIES, min_n=FULL_MIN_FOUND, queries=queries, n=found),
                 ["search", "<English query>", "--into", s.name])
    if c[CANDIDATE] or c[MAYBE]:
        step("screen", t("Screen {n|# candidate|# candidates}", n=c[CANDIDATE] + c[MAYBE]),
             ["list", s.name, "--status", "candidate", "maybe", "--abstract"])
    if c[INCLUDED] and not any(q["kind"] == "snowball" for q in s.data["searches"]):
        if s.depth == "full":
            step("snowball", t("Chase citations to find what was missed"), ["snowball", s.name])
        else:
            step("snowball", t("(Optional) chase citations if you worry about missed papers"), ["snowball", s.name])
    if zotero_pending:
        step("zotero_import", t("Register {n|# paper|# papers} from the Zotero collection \"{name}\" as candidates",
                                n=zotero_pending, name=s.zotero_collection.get("name", "")),
             ["zotero", s.name, "--import"])
    # 設定で許されていて、コレクションを結び付けていれば、Priorwork が採用論文をコレクションに入れられる
    can_add = write_allowed() and bool(s.zotero_collection)
    if zotero_missing:
        numbers = ", ".join(f"#{e['number']}" for e in zotero_missing[:10])
        if can_add:
            step("zotero", t("Add {n|# included paper|# included papers} to the Zotero collection \"{name}\" ({numbers})",
                             n=len(zotero_missing), name=s.zotero_collection["name"], numbers=numbers),
                 ["zotero", s.name, "--add"])
        else:
            step("zotero", t("Add {n|# included paper|# included papers} to Zotero ({numbers})", n=len(zotero_missing),
                             numbers=numbers), ["zotero", s.name])
    if unfilled and len(unfilled) == c[INCLUDED] and s.mode == "standard" and not s.data.get("cards_go"):
        # 標準の進め方: カードの記入の前に止まり、ユーザーが Zotero に論文と PDF を集めるのを待つ
        # （本文で確かめられるカードが増える）。ユーザーが続きを頼んだら `scope --go-on` で記録して進む
        if can_add:
            step("wait_zotero", t("Stop here and wait for the user (standard mode): show what goes into the Zotero "
                                  "collection (`priorwork zotero {name} --add --dry-run`) and ask whether to add it; "
                                  "add it with `priorwork zotero {name} --add` once the user agrees, and ask the user "
                                  "to get the PDFs in Zotero. When the user says to go on, record it with "
                                  "`priorwork scope {name} --go-on` and fill in the cards", name=s.name),
                 ["zotero", s.name, "--add", "--dry-run"])
        else:
            step("wait_zotero", t("Stop here and wait for the user (standard mode): show the DOIs to add to Zotero "
                                  "(`priorwork zotero {name} --dois`), and when the user says to go on, record it with "
                                  "`priorwork scope {name} --go-on` and fill in the cards", name=s.name),
                 ["zotero", s.name, "--dois"])
    if unfilled:
        numbers = ", ".join(f"#{e['number']}" for e in unfilled[:10])
        text = (t("Fill in {n|# card|# cards} from the abstracts ({numbers}); \"abstract only\" is fine",
                  n=len(unfilled), numbers=numbers) if s.depth == "quick"
                else t("Fill in {n|# card|# cards} from the full texts ({numbers})", n=len(unfilled), numbers=numbers))
        step("fill", text, ["fulltext", s.name, str(unfilled[0]["number"])])
    if s.purpose == "advice" and c[INCLUDED]:
        step("advice", t("Write the advice on the manuscript (missing literature, the direction of its citations, "
                         "the argument)"), ["check", s.name])
    if s.purpose == "draft" and c[INCLUDED]:
        step("draft", t("Write the draft of the manuscript's introduction, literature review and hypotheses, "
                        "then export it"), ["export", s.name, "--draft"] + (["--octavo"] if s.octavo else []))
    if s.purpose == "complete" and c[INCLUDED]:
        step("complete", t("Map what the manuscript lacks and write what to add, where (the author's marks first), "
                           "then export it"), ["export", s.name, "--draft"] + (["--octavo"] if s.octavo else []))
    linked = [p for p in s.octavo_projects if not p.get("manuscript") and not p.get("missing")]
    if linked and c[INCLUDED] and s.purpose not in ("draft", "complete"):
        step("octavo", t("Write the sections on the literature for the Octavo {n|project|projects} {names}",
                         n=len(linked), names=", ".join(p["name"] for p in linked)),
             ["export", s.name, "--octavo", linked[0]["name"]])
    step("check", t("Check"), ["check", s.name])
    if c[INCLUDED]:
        step("export", t("Write the version for reading (HTML)"), ["export", s.name])
    return steps


def git_info(surveys: List[Survey]) -> Dict[str, Any]:
    """Git の状態。サーベイはそれぞれのブランチで進む（AGENTS.md「Git」）ので、今のブランチに無いサーベイの
    ブランチも返す（main を見ていると、PR を待つサーベイが一覧に出ないため）。"""
    if not scaffold.in_git_repo(ROOT):
        return {"repo": False, "remote": False, "branch": "", "other_surveys": []}
    here = {s.name for s in surveys}
    branch = scaffold.git_branch(ROOT)
    return {"repo": True, "remote": scaffold.has_remote(ROOT), "branch": branch,
            "other_surveys": [b for b in scaffold.survey_branches(ROOT) if b not in here and b != branch]}


def cmd_status(args, client):
    if not args.survey:
        everything = Survey.list_all()
        surveys = [s for s in everything if not s.archived]
        archived = [s for s in everything if s.archived]
        git = git_info(everything)
        if args.json:
            return dump_json({"version": __version__, "root": str(ROOT), "workspace": meta_dir(ROOT).is_dir(),
                              "lang": workspace_lang(ROOT), "git": git, "sync": scaffold.sync_status(ROOT),
                              "zotero": ZoteroClient.from_env() is not None, "zotero_write": write_allowed(),
                              "requests": [request_json(r) for r in requestsmod.open_requests(ROOT)],
                              "surveys": [survey_summary(s) for s in surveys],
                              "archived": [survey_summary(s) for s in archived]})
        shown = archived if args.archived else surveys
        if not shown:
            print(t("No archived surveys.") if args.archived
                  else t("No surveys yet. Create one with `priorwork new \"<topic>\" --slug <english_slug>`."))
        for s in shown:
            c = s.counts()
            print(f"{s.name}: {s.data['topic']} | " + t("included {included} / maybe {maybe} / candidates {candidate} / "
                                                       "excluded {excluded}", **c))
        if archived and not args.archived:
            print(t("({n|# archived survey|# archived surveys} not shown: `priorwork status --archived`)", n=len(archived)))
        waiting = requestsmod.open_requests(ROOT)
        if waiting:
            print(t("{n|# request|# requests} from Octavo waiting: `priorwork requests`", n=len(waiting)))
        if git["other_surveys"]:
            print(t("On other branches (not merged into this one yet): {names}. To continue one, "
                    "`git switch <name>`", names=", ".join(git["other_surveys"])))
        return

    s = Survey.load(args.survey)
    zotero_missing = zotero_unregistered(s)
    pending = zotero_pending(s)
    steps = next_steps(s, zotero_missing, pending)
    if args.json:
        return dump_json({**survey_summary(s), "scope": s.data["scope"],
                          "unfilled": [e["number"] for e in s.unfilled()],
                          "zotero_missing": [e["number"] for e in zotero_missing],
                          "zotero_write": write_allowed(), "zotero_written": len(s.zotero_written),
                          "written_by": s.written_by, "audits": s.audits, "octavo": s.octavo,
                          "octavo_projects": s.octavo_projects,
                          "sync": scaffold.sync_status(ROOT), "next": steps})
    print(f"# {s.name}: {s.data['topic']}")
    if s.archived:
        print("⚠️ " + t("Archived on {date}. Bring it back with `priorwork archive {name} --undo`",
                        date=s.archived[:10], name=s.name))
    print(t("Report: {path}", path=s.md_path))
    if s.manuscript:
        print(t("Manuscript: {path}", path=s.manuscript) + " | "
              + {"advice": t("purpose: advice on the manuscript"),
                 "complete": t("purpose: filling in what the manuscript lacks")}.get(s.purpose,
                                                                                    t("purpose: a draft of its sections 1–3")))
    for p in s.octavo_projects:
        print(t("Octavo project: {root} | .bib: {bib} | Zotero collections: {collections}", root=p["root"],
                bib=(Path(p["bib"]).name if p["bib"] else "-") + ("" if p["bib_exists"] else " " + t("(not there yet)")),
                collections=", ".join(p["zotero_collections"]) or t("(not set)")))
    roots = {p["root"] for p in s.octavo_projects}
    if roots:
        others = [o for o in Survey.list_all() if o.name != s.name and roots & {p["root"] for p in o.octavo_projects}]
        if others:
            print(t("Other surveys for these Octavo projects: {names}", names=", ".join(
                o.name + (f" ({o.zotero_collection['name']})" if o.zotero_collection else "") for o in others)))
    notice = scaffold.sync_status(ROOT)
    if notice:
        print(f"⚠️ {notice}")
    sc = s.data["scope"]
    unset = t("(not set)")
    print(t("RQ: {question} | period: {years} | depth: {depth}", question=sc.get("question") or unset,
            years=sc.get("years") or unset, depth=s.depth)
          + " | " + t("mode: {mode}", mode=mode_label(s.mode) + ("" if s.data.get("mode") else " " + t("(default)"))))
    print(t("included {included} / maybe {maybe} / candidates {candidate} / excluded {excluded}", **s.counts())
          + " | " + t("{n|# search|# searches}", n=len(s.data["searches"])))
    if s.written_by or s.audits:
        print(t("Written by: {writers}", writers=", ".join(s.written_by) or t("(not recorded)")) + " | "
              + (t("audited by {models}", models=", ".join(a["by"] for a in s.audits)) if s.audits
                 else t("no audit (optional)")))
    print("\n" + t("Next:"))
    for i, st in enumerate(steps, 1):
        print(f"  {i}. {st['text']}: priorwork {' '.join(_shell(a) for a in st['args'])}")


def mode_label(mode: str) -> str:
    return {"standard": t("standard (stops after the scope and before the cards)"), "auto": t("full auto"),
            "manual": t("manual (stops after every step)")}.get(mode, mode)


def _shell(arg: str) -> str:
    return f'"{arg}"' if re.search(r"[\s<>]", arg) else arg


def zotero_unregistered(s: Survey) -> List[Dict[str, Any]]:
    """Zotero 連携が設定されていれば、Zotero 未登録の採用論文を返す（失敗しても status 等は止めない）。

    サーベイに Zotero のコレクションを結び付けていれば、そのコレクションに無いものを返す。
    """
    z = ZoteroClient.from_env()
    if z is None:
        return []
    coll = s.zotero_collection.get("key", "")
    try:
        return [e for e in s.by_status(INCLUDED)
                if not (st := z.status(e["record"], coll))["registered"] or (coll and not st["in_collection"])]
    except ZOTERO_SOFT_ERRORS as e:
        print(f"[Notice] {e}", file=sys.stderr)
        return []


def cmd_new(args, client):
    scope = {k: getattr(args, k) or "" for k in ("question", "years", "fields", "inclusion", "exclusion")}
    s = Survey.create(args.topic, args.slug, scope, depth=args.depth or DEFAULT_DEPTH, lang=args.lang,
                      manuscript=args.manuscript, purpose=args.purpose)
    if args.by or args.search_field or args.mode:
        if args.by:
            s.add_writer(args.by)
        if args.search_field:
            s.set_search_field(args.search_field)
        if args.mode:
            s.set_mode(args.mode)
        s.save()
        s.render()
    link_octavo_collection(s)
    others = same_topic(s, Survey.list_all())
    if others:
        print("[Notice] " + t("Other surveys have the same topic: {names}. If this one redoes them, archive the old "
                              "ones with `priorwork archive <survey>` (nothing is deleted)",
                              names=", ".join(o.name for o in others)), file=sys.stderr)
    if args.json:
        return dump_json({**survey_summary(s), "state": str(s.json_path)})
    print(t("Created: {path}", path=s.md_path))
    print("         " + str(s.json_path))
    print(t("Next: priorwork search \"<English query>\" --into {name}", name=s.name))


def link_octavo_collection(s: Survey):
    """原稿が Octavo のプロジェクトにあり、その .bib を引くコレクションが 1 つに決まっていれば、サーベイにも
    結び付ける（同じコレクションに論文を集めれば、Octavo の参考文献にもなる）。"""
    info = s.octavo
    names = (info or {}).get("zotero_collections", [])
    if not names or s.zotero_collection:
        return
    others = [o for o in Survey.list_all() if o.name != s.name and not o.archived
              and info["root"] in {p["root"] for p in o.octavo_projects}]
    if others or len(names) > 1:
        # ほかのサーベイと同じコレクションに混ぜない（--import で互いの論文が候補に入ってしまう）。
        # サーベイごとに、Octavo のコレクションのどれかの下のコレクションを使ってもらう
        print("[Notice] " + t("The Octavo project pulls its .bib from {names}{others}. Make a collection for this "
                              "survey under one of them in Zotero, and link it: `priorwork zotero {survey} "
                              "--collection \"<path>\"` (Octavo pulls the collections under them too)",
                              names=", ".join(f'"{n}"' for n in names), survey=s.name,
                              others=t(", and other surveys use it too ({names})",
                                       names=", ".join(o.name for o in others)) if others else ""), file=sys.stderr)
        return
    name = names[0]
    z = ZoteroClient.from_env()
    if z is None:
        print("[Notice] " + t("The Octavo project pulls its .bib from the Zotero collection \"{name}\". Set up Zotero "
                              "and link the survey to it too", name=name), file=sys.stderr)
        return
    try:
        z.sync()
        found = z.find_collection(name)
    except ZOTERO_SOFT_ERRORS as e:
        print(f"[Notice] {e}", file=sys.stderr)
        return
    s.set_zotero_collection(found["key"], found["path"])
    s.save()
    print("[Notice] " + t("Linked the Zotero collection \"{name}\" that the Octavo project uses", name=found["path"]),
          file=sys.stderr)


def cmd_scope(args, client):
    s = Survey.load(args.survey)
    s.update_scope(**{k: getattr(args, k) for k in ("question", "years", "fields", "inclusion", "exclusion")})
    if args.depth:
        s.set_depth(args.depth)
    if args.search_field:
        s.set_search_field(args.search_field)
    if args.manuscript:
        s.set_manuscript(args.manuscript)
        s.save()
        link_octavo_collection(s)
    if args.by:
        s.add_writer(args.by)
    if args.mode:
        s.set_mode(args.mode)
    if args.go_on:
        s.data["cards_go"] = now_iso()
    for path in args.octavo or []:
        s.link_octavo(path)
    for path in args.unlink_octavo or []:
        s.link_octavo(path, unlink=True)
    render_and_report(s)
    if args.json:
        return dump_json({"scope": s.data["scope"], "depth": s.depth, "mode": s.mode,
                          "manuscript": s.manuscript or None, "purpose": s.purpose or None,
                          "octavo_projects": s.octavo_projects})
    for k, v in s.data["scope"].items():
        print(f"{k}: {v}")
    print(f"depth: {s.depth}")
    print(f"mode: {s.mode}")
    print(f"search field: {s.search_field}")
    if s.manuscript:
        print(f"manuscript: {s.manuscript} ({s.purpose})")
    for p in s.octavo_projects:
        print(f"octavo: {p['root']}")


def cmd_read(args, client):
    from . import manuscript
    path = Path(args.path).expanduser()
    files = manuscript.read(path)
    bib, cited = manuscript.cited_entries(path)
    marks = manuscript.find_marks(files)
    if args.for_survey:
        s = Survey.load(args.for_survey)
        if not s.manuscript:
            raise SurveyError(t("{name} is not a survey made from a manuscript", name=s.name))
        s.note_manuscript_read()
        s.save()
    if args.json:
        return dump_json({"files": [{"path": str(f), "text": text} for f, text in files],
                          "bib": str(bib) if bib else None, "cited": cited, "marks": marks})
    base = octavo.find_project(path) or (path if path.is_dir() else path.parent)
    parts = []
    for f, text in files:
        try:
            name = f.resolve().relative_to(base.resolve()).as_posix()
        except ValueError:
            name = f.name
        parts.append(f"=== {name} ===\n" + (text.rstrip() if text else t("(not text: a figure or another kind of file)"))
                     + "\n")
    if bib:
        lines = [f"- [@{e['key']}] {', '.join(e['authors'][:3])}{' et al.' if len(e['authors']) > 3 else ''} "
                 f"({e['year'] or 'n.d.'}) {e['title']}" + (f" doi:{e['doi']}" if e["doi"] else "") for e in cited]
        parts.append(f"=== {t('Literature the manuscript cites ({bib}): {n}', bib=bib.name, n=len(cited))} ===\n"
                     + "\n".join(lines) + "\n")
    if marks:
        # 作者の頼みごと（補完で優先して埋める）。場所は見出しと行で
        lines = [f"- {Path(m['file']).name}:{m['line']}" + (f" [{m['heading']}]" if m["heading"] else "")
                 + f" {m['mark']}" + (f" {m['note']}" if m["note"] else "") + f"\n    {m['context']}" for m in marks]
        title = t("Author's marks for Priorwork: {n}", n=len(marks))
        parts.append(f"=== {title} ===\n" + "\n".join(lines) + "\n")
    out = "\n".join(parts)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(t("Wrote the text of {n|# file|# files} to {path}", n=len(files), path=args.out))
    else:
        print(out, end="")


def request_json(r: Dict[str, Any]) -> Dict[str, Any]:
    return {k: r.get(k) for k in ("id", "from", "kind", "project", "manuscript", "text", "created_at", "status",
                                  "survey", "done_at", "note")}


def cmd_requests(args, client):
    """ほかの道具（Octavo）からの依頼の一覧・中身・結果の記録。"""
    if args.done or args.decline:
        if not args.id:
            raise requestsmod.RequestError(t("Give the request: `priorwork requests <id> --done`"))
        if args.survey:
            Survey.load(args.survey)   # 名前を確かめる
        r = requestsmod.close(ROOT, args.id, "done" if args.done else "declined", args.survey or "", args.note or "",
                              now_iso())
        if args.json:
            return dump_json(request_json(r))
        print(t("Recorded the request {id} as {status}", id=r["id"], status=r["status"]))
        return
    if args.id:
        r = requestsmod.get(ROOT, args.id)
        if args.json:
            return dump_json(request_json(r))
        print(f"# {r['id']} ({r.get('from') or '?'}, {r.get('kind') or 'other'}, {r['status']})")
        for label, key in ((t("Octavo project"), "project"), (t("Manuscript"), "manuscript"),
                           (t("Received"), "created_at"), (t("Survey"), "survey"), (t("Note"), "note")):
            if r.get(key):
                print(f"{label}: {r[key]}")
        print("\n" + (r.get("text") or "").strip())
        if r["status"] == "open":
            print("\n" + t("When it is done: `priorwork requests {id} --done --survey <survey>` "
                           "(or --decline --note \"<why>\")", id=r["id"]))
        return
    shown = requestsmod.all_requests(ROOT) if args.all else requestsmod.open_requests(ROOT)
    if args.json:
        return dump_json({"requests": [request_json(r) for r in shown]})
    if not shown:
        print(t("No requests from Octavo") if args.all else t("No open requests from Octavo"))
    for r in shown:
        print(f"{r['id']} [{r['status']}] {r.get('kind') or 'other'} | {requestsmod.summary(r)}")


def cmd_archive(args, client):
    s = Survey.load(args.survey)
    s.set_archived(not args.undo)
    s.save()
    if args.json:
        return dump_json({"name": s.name, "archived": s.archived or None})
    print(t("Archived {name} (hidden from the list; the report and state stay). Undo with "
            "`priorwork archive {name} --undo`", name=s.name) if s.archived
          else t("Brought back {name}", name=s.name))


def cmd_list(args, client):
    s = Survey.load(args.survey)
    statuses = args.status or list(STATUSES)
    entries = [e for e in s.papers if e["status"] in statuses]
    if args.json:
        return dump_json(entries)
    print(t("{name}: {n|# paper|# papers} ({statuses})", name=s.name, n=len(entries),
            statuses=" / ".join(status_label(x) for x in statuses)) + "\n")
    for e in entries:
        reason = f" — {e['reason']}" if e.get("reason") else ""
        extra = " | " + t("found by: {how}", how=", ".join(e["found_by"]))
        if e.get("fulltext"):
            extra += " | " + t("full text fetched")
        if len({h["status"] for h in e.get("history", [])}) > 1:
            extra += " | " + t("history: {trail}", trail=status_trail(e))
        print_paper(e["record"], f"#{e['number']} [{status_label(e['status'])}{reason}]", abstract=args.abstract,
                    extra=extra)


def cmd_set_status(args, client):
    status = {"include": INCLUDED, "exclude": EXCLUDED, "maybe": MAYBE, "reset": CANDIDATE}[args.command]
    if status == EXCLUDED and not args.reason:
        sys.exit(t("Error: {message}", message=t("An exclusion needs a reason (--reason \"...\")")))
    s = Survey.load(args.survey)
    entries = s.set_status(args.numbers, status, args.reason or "")
    render_and_report(s)
    if args.json:
        return dump_json({"changed": [{"number": e["number"], "status": status, "title": e["record"]["title"]}
                                      for e in entries]})
    for e in entries:
        print(f"#{e['number']} → {status_label(status)}: {e['record']['title']}")
        for w in e["record"].get("warnings", []):
            print(f"    ⚠️ {w}")


def cmd_add(args, client):
    s = Survey.load(args.survey)
    status = CANDIDATE if args.candidate else INCLUDED
    ids = list(args.paper_ids)
    no_doi: List[Dict[str, Any]] = []
    if args.cited:
        from . import manuscript
        if not s.manuscript:
            raise SurveyError(t("{name} has no manuscript (`priorwork scope {name} --manuscript <path>`)", name=s.name))
        bib, cited = manuscript.cited_entries(s.root / s.manuscript)
        if bib is None:
            raise SurveyError(t("No .bib was found for the manuscript {path}", path=s.manuscript))
        ids += [e["doi"] for e in cited if e["doi"]]
        no_doi = [e for e in cited if not e["doi"]]
        if not args.json:
            print(t("The manuscript cites {n|# work|# works} in {bib} ({doi} with a DOI)", n=len(cited), bib=bib.name,
                    doi=len(cited) - len(no_doi)))
    if not ids and not no_doi:
        raise SurveyError(t("Give the DOIs to register, or --cited"))
    added = []
    failed: List[str] = []        # データベースに無い・引けなかった
    untried: List[str] = []       # レート制限で止めたので、まだ試していない
    for i, pid in enumerate(ids):
        try:
            rec = client.get_paper(pid)
        except ApiError as e:
            print(f"[Notice] {pid}: {e}", file=sys.stderr)
            if e.status is None or e.status in RETRY_STATUSES:
                # 再試行を使い切った（429 など）。残りも同じなので止める。登録できた分は保存してある
                failed.append(pid)
                untried = ids[i + 1:]
                break
            failed.append(pid)
            continue
        old = s.find(rec)
        old_key = old and old["key"]
        entry, is_new = s.upsert(rec, "manual", status=status)
        if not is_new and status == INCLUDED:
            s.set_status([entry["number"]], INCLUDED)
        added.append((entry, is_new))
        s.save()                  # 1本ごとに保存する（途中で止まっても、それまでの登録は残る）
        if not args.json:
            if is_new:
                state = t("new")
            elif entry["key"] != old_key:
                state = t("already registered; replaced {key} with this one", key=old_key)
            else:
                state = t("already registered")
            print_paper(rec, f"#{entry['number']} [{state} → {status_label(entry['status'])}]")
    s.log_search("manual", t("cited by the manuscript") if args.cited else ", ".join(ids), {"status": status},
                 len(ids), sum(1 for _, n in added if n))
    render_and_report(s)
    rest = failed + untried
    resume = f"./priorwork add {s.name} {' '.join(rest)}" + (" --candidate" if args.candidate else "")
    if args.json:
        dump_json({"added": added_json(added), "failed": failed, "untried": untried,
                   "no_doi": [f"{e['key']}: {e['title']}" for e in no_doi]})
        if rest and not args.cited:
            sys.exit(t("Error: {message}", message=t(
                "Registered {done} of {total}; they are saved. To carry on with the rest, wait a little and run:",
                done=len(added), total=len(ids)) + " " + resume))
        return
    for e in no_doi:
        print("  " + t("no DOI in the .bib (search it by title): [@{key}] {title}", key=e["key"], title=e["title"]))
    for pid in failed:
        print("  " + t("not registered: {doi}", doi=pid))
    if untried:
        print("  " + t("stopped at the rate limit; {n|# more was|# more were} not tried yet", n=len(untried)))
    if rest:
        print(t("Registered {done} of {total}; they are saved. To carry on with the rest, wait a little and run:",
                done=len(added), total=len(ids)))
        print(f"  {resume}")
        if not args.cited:
            sys.exit(1)


def cmd_fix(args, client):
    s = Survey.load(args.survey)
    e = s.get(args.number)
    if args.id:
        rec = client.get_paper(args.id)
        old_key = e["key"]
        s.replace_record(e, rec)
        if not args.json:
            print(t("#{number}: replaced {old} with {new}", number=e["number"], old=old_key, new=e["key"]))
    authors = [a.strip() for a in args.authors.split(";")] if args.authors else None
    s.fix_record(args.number, confirm=args.confirm or "", authors=authors, year=args.year, title=args.title)
    render_and_report(s)
    if args.json:
        return dump_json({"number": e["number"], "key": e["key"], "record": e["record"],
                          "fixed": e.get("fixed", {}), "confirmed": e.get("confirmed")})
    print_paper(e["record"], f"#{e['number']}")
    if e.get("confirmed"):
        print(t("Checked by hand: {reason}", reason=e["confirmed"]["reason"]))


def card_json(s: Survey, number: int) -> Dict[str, Any]:
    values = s.card(number)
    lang = s.lang
    return {"number": number, "evidence": evidence_key(values.get("evidence", "")),
            "evidence_options": [{"key": k, "label": evidence_label(k, lang)} for k in EVIDENCE_KEYS],
            "fields": [{"key": k, "label": tl(lang, label), "value": values.get(k, "")}
                       for k, label in s.card_spec if k != "evidence"]}


def cmd_card(args, client):
    s = Survey.load(args.survey)
    if args.set:
        values = {}
        for item in args.set:
            key, sep, value = item.partition("=")
            if not sep:
                sys.exit(t("Error: {message}", message=t("Give each field as KEY=VALUE: {item}", item=item)))
            values[key.strip()] = value
        changed = s.set_card(args.number, values)
        if not args.json:
            print(f"{s.md_path}: " + (t("updated") if changed else t("no changes")))
    if args.json:
        return dump_json(card_json(s, args.number))
    if not args.set:
        card = card_json(s, args.number)
        names = {o["key"]: o["label"] for o in card["evidence_options"]}
        print(f"#{args.number} " + t("Evidence") + f": {names.get(card['evidence'], '?')}")
        for f in card["fields"]:
            lines = f["value"].split("\n") if f["value"] else [""]
            print(f"  {f['key']} ({f['label']}): {lines[0]}")
            for line in lines[1:]:
                print(f"      - {line}")


def cmd_render(args, client):
    s = Survey.load(args.survey)
    changed = s.render()
    derived.render_all(s)
    print(f"{s.md_path}: " + (t("updated") if changed else t("no changes")))


def cmd_derive(args, client):
    s = Survey.load(args.survey)
    if args.name is None:
        known = derived.entries(s)
        if args.json:
            return dump_json({"survey": s.name, "derived": [
                {"name": n, "path": str(derived.path_of(s, n).relative_to(ROOT)), **spec} for n, spec in known.items()]})
        if not known:
            print(t("{name} has no derived documents yet (`priorwork derive {name} NAME --purpose \"...\"`)",
                    name=s.name))
        for n, spec in known.items():
            print(f"{n}: {derived.path_of(s, n).relative_to(ROOT)} | {spec.get('purpose') or ''}"
                  + (" | " + t("about {n}", n=f"{spec['length']:,}") if spec.get("length") else ""))
        return
    if not args.purpose and args.name not in derived.entries(s):
        raise SurveyError(t("Say what it is for: --purpose \"...\" (e.g. \"a lecture handout in three parts\")"))
    out = derived.create(s, args.name, args.purpose or "", args.length, args.count_citations, args.structure or "")
    if args.json:
        return dump_json({"survey": s.name, "name": args.name, "path": str(out.relative_to(ROOT))})
    print(t("{path}: write the text between the managed blocks (the references at the end follow what you cite)",
            path=out.relative_to(ROOT)))


def cmd_audit(args, client):
    s = Survey.load(args.survey)
    if not args.by:
        if args.json:
            return dump_json({"written_by": s.written_by, "audits": s.audits})
        print(t("Written by: {writers}", writers=", ".join(s.written_by) or t("(not recorded)")))
        for a in s.audits:
            print(f"  {a['at'][:16].replace('T', ' ')} {a['by']}" + (f" — {a['note']}" if a.get("note") else ""))
        if not s.audits:
            print(t("No audit recorded. An audit is optional: when you want one, ask another AI model to audit "
                    "it, and it records it with `priorwork audit {name} --by \"<model>\"`", name=s.name))
        return
    audit = s.add_audit(args.by, args.note)
    s.save()
    s.render()
    if args.json:
        return dump_json(audit)
    print(t("Recorded the audit by {model}", model=audit["by"]))


def cmd_check(args, client):
    s = Survey.load(args.survey)
    findings = check_survey(s, None if args.offline else client)
    if not args.offline:
        missing = zotero_unregistered(s)
        if missing:
            # 採用論文は、本文を別に取得できたかによらず、すべて Zotero に入れる（参考文献の管理はそちらで行う）
            findings.append((WARN, t("{n|# included paper is|# included papers are} not in Zotero: {numbers} "
                                     "(`priorwork zotero {name}`)", n=len(missing),
                                     numbers=", ".join(f"#{e['number']}" for e in missing), name=s.name)))
    order = {ERROR: 0, WARN: 1, INFO: 2}
    findings = sorted(findings, key=lambda f: order[f[0]])
    errors = sum(1 for f in findings if f[0] == ERROR)
    warns = sum(1 for f in findings if f[0] == WARN)
    if args.json:
        dump_json({"findings": [{"level": lv, "message": m} for lv, m in findings], "errors": errors, "warnings": warns})
    else:
        for level, msg in findings:
            print(f"[{level}] {msg}")
        print(f"\nERROR {errors} / WARN {warns}" + ("" if findings else t(" — no problems")))
    if errors:
        sys.exit(1)


def cmd_export(args, client):
    s = Survey.load(args.survey)
    output = Path(args.output) if args.output else None
    if args.octavo is not None or args.bib:
        if args.octavo is None:
            args.octavo = ""
        return export_for_octavo(s, args, output)
    try:
        if args.derived:
            out, issues = derived.export_one(s, args.derived, args.format or "html", output)
        elif args.draft:
            out, issues = export_draft(s, args.format or "md", output)
        else:
            out, issues = export(s, args.format or "html", output, args.with_abstracts)
    except (RuntimeError, OSError) as e:
        sys.exit(t("Error: {message}", message=e))
    if args.json:
        return dump_json({"path": str(out.resolve()), "issues": issues})
    print(t("Written: {path}", path=out))
    if issues:
        print("⚠️ " + t("Written as a draft (marked at the top):"))
        for issue in issues:
            print(f"  - {issue}")


def pick_octavo_project(s: Survey, which: str) -> Dict[str, Any]:
    """`--octavo [PROJECT]` のプロジェクト。PROJECT はパスかフォルダの名前。省けるのは 1 つだけのとき。"""
    projects = [p for p in s.octavo_projects if not p.get("missing")]
    if not projects:
        raise SurveyError(t("{name} is not linked to an Octavo project. Link one with "
                            "`priorwork scope {name} --octavo <path>`", name=s.name))
    if not which:
        if len(projects) == 1:
            return projects[0]
        raise SurveyError(t("{name} is linked to several Octavo projects; name one: {projects}", name=s.name,
                            projects=", ".join(p["name"] for p in projects)))
    target = Path(which).expanduser()
    target = (target if target.is_absolute() else Path.cwd() / target).resolve()
    for p in projects:
        if p["name"] == which or Path(p["root"]).resolve() == target:
            return p
    raise SurveyError(t("{name} is not linked to the Octavo project {project}. The linked ones: {projects}",
                        name=s.name, project=which, projects=", ".join(p["name"] for p in projects)))


def export_for_octavo(s: Survey, args, output: Optional[Path]):
    from .export import export_octavo
    if args.bib:
        bib, project = Path(args.bib), {"name": "", "zotero_collections": []}
    else:
        project = pick_octavo_project(s, args.octavo)
        bib = Path(project["bib"])
    try:
        out, missing = export_octavo(s, bib, output, project["name"], Path(project["root"]) if project.get("root") else None)
    except (RuntimeError, OSError) as e:
        sys.exit(t("Error: {message}", message=e))
    coll = s.zotero_collection.get("name", "") or ", ".join(project["zotero_collections"])
    if args.json:
        return dump_json({"path": str(out.resolve()), "bib": str(bib),
                          "manifest": str(out.with_suffix(".json").resolve()) if project.get("root") else None,
                          "missing": [{"number": e["number"], "doi": e["record"].get("doi") or "",
                                       "title": e["record"]["title"]} for e in missing]})
    print(t("Written: {path}", path=out))
    if project.get("root"):
        print(t("It is in the Octavo project's inbox for Priorwork (with {manifest}). Priorwork does not change the "
                "manuscript: ask the agent in the Octavo project to work it into the manuscript",
                manifest=out.with_suffix(".json").name))
    if missing:
        print("⚠️ " + t("{n|# paper cited in the text is|# papers cited in the text are} not in {bib}, so "
                        "{n|it is|they are} written as [@{prefix}<DOI>] (Octavo shows ?? until it is there). Add "
                        "{n|it|them} to Zotero{where}, then run `octavo bib pull` and `octavo priorwork resolve` in the "
                        "Octavo project to replace the marks by the keys (with Octavo 0.6.6 or older, export again "
                        "after `octavo bib pull` instead):",
                        n=len(missing), bib=bib.name, prefix=octavo.MISSING_PREFIX,
                        where=t(" (the collection \"{name}\")", name=coll) if coll else ""))
        for e in missing:
            r = e["record"]
            print(f"  {author_short(r['authors'])} ({r.get('year') or 'n.d.'}) "
                  + (f"https://doi.org/{r['doi']}" if r.get("doi") else r["title"]))


def cmd_fulltext(args, client):
    s = Survey.load(args.survey)
    entry = s.get(args.number)
    try:
        info = fetch_fulltext(entry, client, pdf_path=args.pdf, zotero=ZoteroClient.from_env())
    except FulltextError as e:
        # 「試して取れなかった」を残す（check が「試していない」と区別する）
        entry["fulltext_failed"] = {"at": now_iso(), "reason": str(e).splitlines()[0]}
        s.save()
        raise
    entry["fulltext"] = info
    entry.pop("fulltext_failed", None)
    s.save()
    if args.json:
        return dump_json({"number": entry["number"], **info})
    print(f"#{entry['number']} {entry['record']['title']}")
    print(t("Full text: {path} ({pages} pages, {chars} characters)", path=info["path"], pages=info["pages"] or "?",
            chars=f"{info['chars']:,}"))
    print(t("Source: {source}", source=info["source"]))
    if info.get("version") in ("acceptedVersion", "submittedVersion"):
        print(t("* This is the author's manuscript ({version}), not the published version. Its pages are not the "
                "journal's: give the PDF page (the N of `=== page N ===`) and say so in the memo",
                version=info["version"]))
    expected = incomplete_fulltext(entry)
    if expected:
        print(t("* The PDF has only {pages} pages, but the paper has {expected} journal pages. It may be only the "
                "publisher's preview: get the whole PDF (attach it in Zotero, or give it with `--pdf`)",
                pages=info["pages"], expected=expected))
    if not info["page_markers"]:
        print(t("* This is Zotero's index text, which has no page breaks. Check the PDF before giving page numbers."))
    print(t("* Extracted text can garble columns, tables and formulas. Check numbers against the page in the PDF too."))


def zotero_pending(s: Survey) -> int:
    """結び付けたコレクションにあって、サーベイにまだ無い論文の数（失敗しても status は止めない）。"""
    z = ZoteroClient.from_env()
    if z is None or not s.zotero_collection:
        return 0
    try:
        return len(zotero_to_import(s, z))
    except ZOTERO_SOFT_ERRORS as e:
        print(f"[Notice] {e}", file=sys.stderr)
        return 0


def zotero_to_import(s: Survey, z: ZoteroClient) -> List[Dict[str, Any]]:
    """結び付けたコレクションにあって、サーベイにまだ無い論文（Zotero のアイテム）。"""
    coll = s.zotero_collection.get("key")
    if not coll:
        return []
    known_dois = {(e["record"].get("doi") or "").lower() for e in s.papers} - {""}
    known_titles = {ssci.normalize_title(e["record"]["title"]) for e in s.papers}
    return [i for i in z.collection_items(coll)
            if i["doi"] not in known_dois and ssci.normalize_title(i["title"]) not in known_titles]


def zotero_add(s: Survey, z: ZoteroClient, statuses: List[str], dry_run: bool) -> List[Dict[str, Any]]:
    """採用論文（statuses の論文）を、結び付けたコレクションに入れる。書いたものは状態ファイルに記録する。"""
    coll = s.zotero_collection
    if not coll:
        raise ZoteroError(t("No Zotero collection is linked to {survey}. Link one with "
                            "`priorwork zotero {survey} --collection \"<name>\"`", survey=s.name))
    if not z.write and not dry_run:
        raise ZoteroError(t("Priorwork may not write to Zotero. To let it add the included papers to the collection, "
                            "set ZOTERO_WRITE=1 in .env (on the settings page) and give the API key write access"))
    papers = s.by_status(*statuses)
    plan = z.plan_add(papers, coll["key"])
    if dry_run or not plan:
        return plan
    z.check_write_access()
    result = z.add(plan, {e["number"]: e["record"] for e in papers}, coll["key"])
    at = now_iso()
    s.set_zotero_written(s.zotero_written + [
        {"number": p["number"], "key": p["key"], "action": p["action"], "collection": coll["key"],
         "version": p["version"], "at": at} for p in result if p["done"]])
    s.save()
    z.sync()
    return result


def zotero_undo(s: Survey, z: ZoteroClient, numbers: List[int], dry_run: bool) -> List[Dict[str, Any]]:
    """`zotero_add` で書いたもの（numbers があればその論文の分）を戻す。"""
    entries = {e["number"]: e for e in s.papers}
    todo = [{**w, "title": entries[w["number"]]["record"]["title"] if w["number"] in entries else ""}
            for w in s.zotero_written if not numbers or w["number"] in numbers]
    if dry_run or not todo:
        return todo
    if not z.write:
        raise ZoteroError(t("Priorwork may not write to Zotero. To let it add the included papers to the collection, "
                            "set ZOTERO_WRITE=1 in .env (on the settings page) and give the API key write access"))
    z.check_write_access()
    result = z.undo(todo)
    undone = {(r["key"], r["action"]) for r in result if r["done"]}
    s.set_zotero_written([w for w in s.zotero_written if (w["key"], w["action"]) not in undone])
    s.save()
    z.sync()
    return result


def print_written(written: List[Dict[str, Any]], coll: Dict[str, str], add: bool, dry_run: bool):
    if not written:
        print((t("Nothing to add: the papers are all in the collection \"{name}\"", name=coll.get("name", "")) if add
               else t("Nothing to undo: Priorwork has not written to Zotero for this survey")) + "\n")
        return
    if add:
        print((t("Would add to the Zotero collection \"{name}\" (nothing written yet):", name=coll["name"]) if dry_run
               else t("Added to the Zotero collection \"{name}\":", name=coll["name"])))
    else:
        print(t("Would undo (nothing written yet):") if dry_run else t("Undid what Priorwork wrote to Zotero:"))
    labels = {"create": t("new item from the bibliographic data"), "collect": t("item already in the library"),
              "trash": t("to the Zotero trash"), "keep": t("kept (changed in Zotero since)"),
              "uncollect": t("out of the collection"), "gone": t("no longer in Zotero")}
    if not add and dry_run:   # 作ったアイテムに手が入ったかは、書くときに確かめる
        labels.update(create=t("to the Zotero trash, unless changed in Zotero since"), collect=labels["uncollect"])
    for w in written:
        if not dry_run and not w.get("done"):
            what = t("failed: {error}", error=w.get("error", ""))
        else:
            what = labels[w.get("undo") or w["action"]]
        print(f"  #{w['number']} {what} | {w.get('title', '')}")
    print()


def cmd_zotero(args, client):
    z = ZoteroClient.from_env()
    if z is None and args.survey and args.dois and not (args.collection or args.import_collection or args.json):
        # Zotero の連携が無くても、Zotero に入れる DOI の一覧（採用論文すべて）は出せる
        print("[Notice] " + t("Zotero is not set up, so these are the DOIs of all the papers, whether in Zotero or not"),
              file=sys.stderr)
        for e in Survey.load(args.survey).by_status(*(args.status or [INCLUDED])):
            if e["record"].get("doi"):
                print(e["record"]["doi"])
        return
    if z is None:
        sys.exit(t("Error: {message}", message=t("Zotero is not set up. Set ZOTERO_API_KEY and ZOTERO_USER_ID in .env")))
    index = z.sync(force=args.refresh)

    if args.collections:
        cols = z.collections()
        if args.json:
            return dump_json({"collections": cols})
        for c in cols:   # Zotero と同じ木の形で（下のコレクションの論文も数に含める）
            print(f"{'  ' * c['depth']}{c['name']}  ({t('{n|# item|# items}', n=c['total'])}, key {c['key']})")
        if not cols:
            print(t("No collections in the Zotero library"))
        return

    if not args.survey:
        items = index["items"].values()
        parents = [i for i in items if not i["parentItem"] and i["itemType"] != "attachment"]
        pdfs = [i for i in items if i["contentType"] == "application/pdf"]
        print(t("Zotero library: {n|# item|# items} ({doi} with a DOI) / {pdfs|# PDF attached|# PDFs attached} | "
                "library version {version} | synced {synced}", n=len(parents),
                doi=sum(1 for i in parents if i["doi"]), pdfs=len(pdfs), version=index["version"],
                synced=index.get("synced_at", "")))
        print(t("WebDAV: {status}", status=z.check_webdav()))
        return

    s = Survey.load(args.survey)
    if args.collection is not None:
        found = z.find_collection(args.collection) if args.collection.strip() else {"key": "", "path": ""}
        s.set_zotero_collection(found["key"], found["path"])
        s.save()
        if not args.json:
            print(t("Linked the Zotero collection \"{name}\" to {survey}", name=found["path"], survey=s.name)
                  if found["key"] else t("Unlinked the Zotero collection from {survey}", survey=s.name))
    coll = s.zotero_collection
    z.prefer_collection = coll.get("key", "")
    statuses = args.status or [INCLUDED]

    written: List[Dict[str, Any]] = []
    if args.add:
        written = zotero_add(s, z, statuses, args.dry_run)
    elif args.undo is not None:
        written = zotero_undo(s, z, args.undo, args.dry_run)

    imported: List[tuple] = []
    no_doi: List[Dict[str, Any]] = []
    if args.import_collection:
        if not coll:
            raise ZoteroError(t("No Zotero collection is linked to {survey}. Link one with "
                                "`priorwork zotero {survey} --collection \"<name>\"`", survey=s.name))
        for item in zotero_to_import(s, z):
            if not item["doi"]:
                no_doi.append(item)
                continue
            try:
                rec = client.get_paper(item["doi"])
            except ApiError as e:
                print(f"[Notice] {item['doi']}: {e}", file=sys.stderr)
                no_doi.append(item)
                continue
            imported.append(s.upsert(rec, "zotero"))
        if imported:
            s.log_search("zotero", coll["name"], {}, len(imported), sum(1 for _, n in imported if n))
        render_and_report(s)

    entries = [e for e in s.papers if e["status"] in statuses]
    rows = []
    for e in entries:
        st = z.status(e["record"], coll.get("key", ""))
        r = e["record"]
        rows.append({"number": e["number"], "title": r["title"], "doi": r.get("doi") or "",
                     "link": f"https://doi.org/{r['doi']}" if r.get("doi") else (r.get("url") or ""),
                     "registered": st["registered"], "in_collection": st["in_collection"], "pdfs": st["pdfs"],
                     "missing": not st["registered"] or bool(coll and not st["in_collection"]), "entry": e})
    missing = [r for r in rows if r["missing"]]
    pending = zotero_to_import(s, z)

    if args.json:
        return dump_json({"survey": s.name, "collection": coll or None,
                          "papers": [{k: v for k, v in r.items() if k != "entry"} for r in rows],
                          "missing_dois": [r["doi"] for r in missing if r["doi"]],
                          "to_import": len(pending),
                          "imported": added_json(imported), "no_doi": [i["title"] for i in no_doi],
                          "can_write": z.write, "dry_run": bool(args.dry_run), "written": written})
    if args.dois:
        for r in missing:
            if r["doi"]:
                print(r["doi"])
        return

    if args.add or args.undo is not None:
        print_written(written, coll, bool(args.add), args.dry_run)
    if imported or no_doi:
        print(t("Imported from the Zotero collection: {n|# paper|# papers} ({new} new)", n=len(imported),
                new=sum(1 for _, n in imported if n)))
        for item in no_doi:
            print("  " + t("not imported (no DOI, or not found): {title}", title=item["title"]))
        print()
    print(t("{name}: Zotero status of {n|# paper|# papers} ({statuses})", name=s.name, n=len(entries),
            statuses=" / ".join(status_label(x) for x in statuses))
          + (" | " + t("collection: {name}", name=coll["name"]) if coll else "") + "\n")
    for r in rows:
        e = r["entry"]
        if not r["registered"]:
            mark = "❌ " + t("not in Zotero")
        elif coll and not r["in_collection"]:
            mark = "🟡 " + t("in Zotero, not in the collection")
        else:
            mark = ("✅ " + t("in Zotero ({n|# PDF|# PDFs})", n=r["pdfs"])) if r["pdfs"] else "🟡 " + t("in Zotero (no PDF)")
        print(f"#{r['number']} {mark} | {author_short(e['record']['authors'])} ({e['record'].get('year') or 'n.d.'}) "
              f"{r['title']}")
        if r["missing"] and r["link"]:
            print(f"    {r['link']}")
    can_add = z.write and bool(coll)
    print("\n" + t("{n|# paper is|# papers are} not in Zotero", n=len(missing))
          + (t(" (add them to Zotero by hand; this command picks them up the next time it runs)")
             if missing and not can_add else ""))
    if missing or any(r["registered"] and not r["pdfs"] for r in rows):
        print("  " + z.sync_note())
    if missing and can_add:
        print(t("To add them to the collection \"{collection}\": `priorwork zotero {name} --add` (see what it does "
                "first with --dry-run; --undo takes it back)", collection=coll["name"], name=s.name))
    elif any(r["doi"] for r in missing):
        print(t("To add them at once: copy the DOIs from `priorwork zotero {name} --dois` and paste them into Zotero's "
                "\"Add Item by Identifier\" (the magic wand){where}", name=s.name,
                where=t(" with the collection \"{name}\" selected", name=coll["name"]) if coll else ""))
    if pending:
        print(t("{n|# paper is|# papers are} in the collection but not in the survey yet: "
                "`priorwork zotero {name} --import` registers them as candidates", n=len(pending), name=s.name))


# ---------------- Discovery commands ----------------

def cmd_search(args, client):
    warn_if_no_ssci_list()
    s = Survey.load(args.into) if args.into else None
    limit = args.limit or DEFAULT_LIMIT["full" if s and s.depth == "full" else "quick"]
    # 除外・重複統合で件数が減るので多めに取得する
    fetch_limit = min(max(limit * 4, 20), 100)
    try:
        papers = client.search(args.query, limit=fetch_limit, year=args.year, bulk=args.bulk)
    except ApiError as e:
        if s is not None and (e.status is None or e.status in RETRY_STATUSES):
            # 検索は1回の問い合わせなので、途中までの結果は無い。サーベイは前のまま（前の検索の結果も残る）
            print("[Notice] " + t("This query gave nothing, and {name} is as it was (earlier searches are kept). "
                                  "Wait a little and run the same command again", name=s.name), file=sys.stderr)
        raise
    field = args.field or (s.search_field if s else "all")
    if field == "social":
        dropped = [p for p in papers if off_field(p)]
        papers = [p for p in papers if not off_field(p)]
        if dropped:
            print("[Notice] " + t("Left out {n|# paper|# papers} outside the social sciences (e.g. {example}). "
                                  "To keep them, add --field all", n=len(dropped),
                                  example=", ".join(sorted({f for p in dropped for f in p["fields"]})[:3])),
                  file=sys.stderr)
    results = rank_and_filter(papers, args.include_preprints, args.ssci_only, args.sort)[:limit]
    client.complete_abstracts(results)
    if not results:
        print("[Notice] " + (t("No hits. Bulk search takes + (AND), | (OR), - (NOT) and \"phrases\"; "
                                "try fewer terms or synonyms") if args.bulk
                              else t("No hits. Try fewer terms, synonyms or --bulk")), file=sys.stderr)

    if not args.into:
        if args.json:
            return dump_json(results)
        print(t("Results for '{query}': {n|# paper|# papers}", query=args.query, n=len(results)) + "\n")
        for i, p in enumerate(results, 1):
            print_paper(p, f"[{i}]")
        return

    added = add_records(s, results, "search")
    new = sum(1 for _, is_new in added if is_new)
    s.log_search("bulk" if args.bulk else "search", args.query,
                 {"year": args.year, "sort": args.sort, "ssci_only": args.ssci_only, "limit": limit, "field": field},
                 len(results), new)
    render_and_report(s)
    if args.json:
        return dump_json({"query": args.query, "hits": len(results), "new": new, "added": added_json(added)})
    print(t("'{query}' → {n|# paper|# papers} ({new} new {new|candidate|candidates} added to {name})",
            query=args.query, n=len(results), new=new, name=s.name) + "\n")
    for entry, is_new in added:
        print_paper(entry["record"], entry_prefix(entry, is_new), abstract=args.abstract)


def cmd_snowball(args, client):
    s = Survey.load(args.survey)
    records, stats = snowball(s, client, direction=args.direction, per_paper=args.per_paper,
                              min_links=args.min_links)
    if not stats["seeds"]:
        sys.exit(t("Error: {message}", message=t("No paper is included yet. Include some with `priorwork include` first")))
    limit = args.limit or DEFAULT_LIMIT["full" if s.depth == "full" else "quick"]
    records = rank_and_filter(records, args.include_preprints, args.ssci_only, "relevance")[:limit]
    client.complete_abstracts(records)
    added = add_records(s, records, "snowball")
    new = sum(1 for _, is_new in added if is_new)
    s.log_search("snowball", t("citations of {n|# included paper|# included papers} ({direction})", n=stats["seeds"],
                               direction=args.direction),
                 {"min_links": stats["threshold"], "per_paper": args.per_paper}, len(records), new)
    render_and_report(s)
    if args.json:
        return dump_json({"seeds": stats["seeds"], "skipped": stats["skipped"], "linked": stats["linked"],
                          "threshold": stats["threshold"], "hits": len(records), "new": new,
                          "added": added_json(added)})
    print(t("Unregistered papers linked by citations to {seeds|# included paper|# included papers}: {linked} → "
            "registered the top {n} with at least {threshold|# link|# links} as candidates",
            seeds=stats["seeds"], linked=stats["linked"], n=len(records), threshold=stats["threshold"]))
    if stats["skipped"]:
        print(t("({n|# included paper was|# included papers were} skipped: no DOI or OpenAlex ID, "
                "or not found in OpenAlex)", n=stats["skipped"]))
    print()
    for (entry, is_new), rec in zip(added, records):
        links = rec["_links"]
        print_paper(entry["record"], entry_prefix(entry, is_new), abstract=args.abstract,
                    extra=" | " + t("{total|# link|# links} (cited by the included papers {references} / "
                                    "citing them {citations})", **links))


def cmd_get(args, client):
    p = client.get_paper(args.paper_id)
    if args.json:
        return dump_json(p)
    print(f"Title:     {p['title']}")
    print(f"Authors:   {', '.join(p['authors']) or 'Unknown'}")
    vol = f" {p['volume']}" + (f"({p['issue']})" if p["issue"] else "") + (f", {p['pages']}" if p["pages"] else "")
    print(f"Journal:   {p['journal_name'] or 'N/A'} ({p['year'] or 'N/A'}){vol if p['volume'] else ''}")
    print(f"SSCI:      {ssci.badge(p['ssci']['status'])}")
    print(f"Type:      {', '.join(p['publication_types']) or 'N/A'} | ISSN: {', '.join(p['issns']) or 'N/A'}")
    print(f"DOI:       {p['doi'] or 'N/A'}")
    print(f"Citations: {p['citation_count']} | References: {p['reference_count']} | "
          f"Source: {p['source']}"
          + (t(" (DOI verified with OpenAlex)") if p["verified"] and p["source"] != "OpenAlex" else ""))
    for w in p["warnings"]:
        print(f"⚠️  {w}")
    print(f"OA PDF:    {p['oa_pdf'] or 'N/A'}")
    if p["tldr"]:
        print(f"TL;DR:     {p['tldr']}")
    print("\n--- Abstract ---")
    print(p["abstract"] or t("(no abstract)"))


def cmd_linked(args, client):
    kind = args.command
    results = client.get_linked(args.paper_id, kind, limit=args.limit, sort=args.sort)
    if args.json:
        return dump_json(results)
    order = (t("by citations") if results and results[0]["source"] == "OpenAlex"
             else t("in S2's order (roughly newest first)"))
    head = (t("Papers citing {id}: {n} ({order})", id=args.paper_id, n=len(results), order=order) if kind == "citations"
            else t("References of {id}: {n} ({order})", id=args.paper_id, n=len(results), order=order))
    print(head + "\n")
    for i, p in enumerate(results, 1):
        print_paper(dict(p, tldr=""), f"[{i}]")


def cmd_journal(args, client):
    q = args.name_or_issn.strip()
    issn = ssci.normalize_issn(q) if re.fullmatch(r"\d{4}-?\d{3}[\dXx]", q) else ""
    status, _ = ssci.classify(journal_name="" if issn else q, issns=[issn] if issn else [], source_type="journal")
    lst = ssci.get_ssci_list()
    if args.json:
        return dump_json({"query": q, "status": status, "badge": ssci.badge(status), "list": lst.loaded})
    print(f"{q}: {ssci.badge(status)}")
    print(t("Basis: {basis}", basis=t("checked against the Clarivate list ({file})", file=lst.path.name) if lst.loaded
            else t("guessed from the journal name with the built-in list of major journals (verify)")))


# ---------------- Entry point ----------------

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--no-cache", action="store_true", help=t("do not use the cache of API responses"))

    as_json = argparse.ArgumentParser(add_help=False)
    as_json.add_argument("--json", action="store_true", help=t("print JSON (for the VS Code extension and scripts)"))

    filters = argparse.ArgumentParser(add_help=False)
    filters.add_argument("--limit", type=int, help=t("number of papers (default: 25 for a full survey, else 10)"))
    filters.add_argument("--ssci-only", action="store_true", help=t("only papers in SSCI journals (including guessed ones)"))
    filters.add_argument("--include-preprints", action="store_true",
                         help=t("also include working papers, preprints, books and unknown venues"))
    filters.add_argument("--abstract", action="store_true", help=t("show the start of the abstract when there is no TL;DR"))

    parser = argparse.ArgumentParser(prog="priorwork", description="\n".join(t(ln) if ln else "" for ln in USAGE_LINES),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"priorwork {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("init", parents=[common], help=t("set up a workspace"))
    p.add_argument("dir", nargs="?", help=t("the directory (default: the current workspace)"))
    p.add_argument("--lang", choices=i18n.LANGS,
                   help=t("the language of the reports, AGENTS.md and the skills (default: the display language)"))

    p = sub.add_parser("sync", parents=[common], help=t("update AGENTS.md, the skills and ./priorwork to the engine's version"))
    p.add_argument("--force", action="store_true", help=t("also overwrite files changed by hand"))
    p.add_argument("--diff", action="store_true", help=t("show the differences from the engine's version without writing"))

    p = sub.add_parser("doctor", parents=[common, as_json], help=t("diagnose the setup"))
    p.add_argument("--online", action="store_true", help=t("also check the connections to Semantic Scholar, OpenAlex and Zotero"))

    p = sub.add_parser("settings", parents=[common, as_json],
                       help=t("show or change the settings in .env (API keys, Zotero) and the SSCI list"))
    p.add_argument("--stdin", action="store_true",
                   help=t("read the values to write as a JSON object from stdin (an empty string removes one)"))
    p.add_argument("--import-ssci", metavar="CSV", help=t("import the SSCI list downloaded from the Master Journal List"))

    p = sub.add_parser("upgrade", parents=[common], help=t("update the engine, then sync"))
    p.add_argument("--to", metavar="X.Y.Z", help=t("the version to update to (default: the latest)"))

    p = sub.add_parser("status", parents=[common, as_json], help=t("list the surveys / progress and next steps"))
    p.add_argument("survey", nargs="?")
    p.add_argument("--archived", action="store_true", help=t("list the archived surveys instead"))

    p = sub.add_parser("read", parents=[common, as_json],
                       help=t("print the text of a manuscript (.md, .qmd, .tex, .html, .docx, .pdf, … or a folder)"))
    p.add_argument("path", help=t("the manuscript file, or its folder"))
    p.add_argument("--out", metavar="FILE", help=t("write the text to a file instead"))
    p.add_argument("--for", dest="for_survey", metavar="SURVEY",
                   help=t("record that the survey's agent read the manuscript as it is now (a later change is then "
                          "shown in the next steps)"))

    p = sub.add_parser("requests", parents=[common, as_json], help=t("requests from Octavo"))
    p.add_argument("id", nargs="?", help=t("a request (the start of its id is enough); leave out to list them"))
    p.add_argument("--all", action="store_true", help=t("list the closed ones too"))
    p.add_argument("--done", action="store_true", help=t("record that the request is done"))
    p.add_argument("--decline", action="store_true", help=t("record that the request is declined (say why with --note)"))
    p.add_argument("--survey", help=t("with --done: the survey that carried it out"))
    p.add_argument("--note", help=t("a note for the one who asked"))

    p = sub.add_parser("archive", parents=[common, as_json],
                       help=t("archive a survey: hide it from the list, keeping its files"))
    p.add_argument("survey")
    p.add_argument("--undo", action="store_true", help=t("bring it back"))

    scope_args = argparse.ArgumentParser(add_help=False)
    scope_args.add_argument("--question", help=t("the research question"))
    scope_args.add_argument("--years", help=t("the period (e.g. 2000-2024)"))
    scope_args.add_argument("--fields", help=t("the fields (e.g. labour economics, sociology)"))
    scope_args.add_argument("--inclusion", help=t("inclusion criteria"))
    scope_args.add_argument("--exclusion", help=t("exclusion criteria"))
    scope_args.add_argument("--depth", choices=list(DEPTHS),
                            help=t("the depth of the survey (quick or full; default full)"))
    scope_args.add_argument("--search-field", choices=list(SEARCH_FIELDS),
                            help=t("the fields that searches into the survey keep (social: leave out papers outside "
                                   "the social sciences, the default for new surveys; all: keep everything)"))
    scope_args.add_argument("--by", metavar="MODEL",
                            help=t("the AI model writing the survey (e.g. \"Gemini 3.1 Pro\"); "
                                   "an audit, if you ask for one, is then by another model"))
    scope_args.add_argument("--mode", choices=list(MODES),
                            help=t("where the agent stops for you (standard: after the scope and before the cards, "
                                   "so you can collect the papers in Zotero, the default; auto: never; "
                                   "manual: after every step)"))
    scope_args.add_argument("--manuscript", metavar="PATH",
                            help=t("your manuscript (a file in any format, or a folder under manuscripts/ with the "
                                   "manuscript and its tables): the survey then fills in what it lacks, drafts its sections 1–3 "
                                   "or advises on it (--purpose)"))

    p = sub.add_parser("new", parents=[common, scope_args, as_json], help=t("create a survey"))
    p.add_argument("topic", help=t("the topic (any language)"))
    p.add_argument("--slug", required=True, help=t("an English slug for the file name (e.g. minimum_wage_employment)"))
    p.add_argument("--lang", choices=i18n.LANGS, help=t("the language of the report (default: the workspace's)"))
    p.add_argument("--purpose", choices=list(PURPOSES),
                   help=t("with --manuscript, what the report is for (complete: fill in what a manuscript in progress "
                          "lacks, from the literature, the default; draft: a draft of the sections 1–3 of a manuscript "
                          "whose analysis is done; advice: advice on a finished manuscript — missing literature, the "
                          "direction of its citations, the argument)"))

    p = sub.add_parser("scope", parents=[common, scope_args, as_json], help=t("set the scope"))
    p.add_argument("survey")
    p.add_argument("--octavo", action="append", metavar="PATH",
                   help=t("link an Octavo project that uses this survey (repeatable; a survey can serve several papers)"))
    p.add_argument("--unlink-octavo", action="append", metavar="PATH", help=t("unlink an Octavo project"))
    p.add_argument("--go-on", action="store_true",
                   help=t("record that the user said to go on to the cards (standard mode stops before them)"))

    p = sub.add_parser("list", parents=[common, as_json], help=t("list the papers"))
    p.add_argument("survey")
    p.add_argument("--status", nargs="+", choices=list(STATUSES), help=t("filter (one or more)"))
    p.add_argument("--abstract", action="store_true", help=t("also show the start of the abstract"))

    for name, help_text in STATUS_COMMANDS:
        p = sub.add_parser(name, parents=[common, as_json], help=t(help_text))
        p.add_argument("survey")
        p.add_argument("numbers", nargs="+", type=int, help=t("paper numbers (without #)"))
        p.add_argument("--reason", help=t("the reason"))

    p = sub.add_parser("add", parents=[common, as_json], help=t("register papers by DOI or ID (included by default)"))
    p.add_argument("survey")
    p.add_argument("paper_ids", nargs="*", help="DOI / DOI URL / Semantic Scholar ID / OpenAlex ID")
    p.add_argument("--candidate", action="store_true", help=t("register as a candidate, not as included"))
    p.add_argument("--cited", action="store_true",
                   help=t("register the papers the survey's manuscript cites (the DOIs in its .bib)"))

    p = sub.add_parser("fix", parents=[common, as_json],
                       help=t("correct the details of a registered paper (published-version DOI, authors, year, title) "
                              "or clear a warning you have checked"))
    p.add_argument("survey")
    p.add_argument("number", type=int, help=t("the paper number"))
    p.add_argument("--id", metavar="DOI",
                   help=t("replace the details with those of this DOI / ID (e.g. the published version of a working paper)"))
    p.add_argument("--authors", help=t("the authors, separated by \";\" (e.g. \"Yuen Yuen Ang\")"))
    p.add_argument("--year", type=int, help=t("the year"))
    p.add_argument("--title", help=t("the title"))
    p.add_argument("--confirm", metavar="REASON",
                   help=t("clear the warnings after checking that the details are right, recording why"))

    p = sub.add_parser("card", parents=[common, as_json], help=t("show or fill in the card of an included paper"))
    p.add_argument("survey")
    p.add_argument("number", type=int, help=t("the paper number"))
    p.add_argument("--set", nargs="+", metavar="KEY=VALUE",
                   help=t("fields to write (evidence=unchecked|abstract|fulltext, rq, x, y, data, method, findings, "
                          "limits, memo, and role for a survey with a manuscript); a new line starts the bullet points below"))

    p = sub.add_parser("render", parents=[common], help=t("regenerate the managed blocks of the Markdown"))
    p.add_argument("survey")

    p = sub.add_parser("check", parents=[common, as_json], help=t("check the survey"))
    p.add_argument("survey")
    p.add_argument("--offline", action="store_true", help=t("do not re-check the DOIs with OpenAlex"))

    p = sub.add_parser("derive", parents=[common, as_json],
                       help=t("a short text made from the survey (a lecture handout, reading notes, a summary)"))
    p.add_argument("survey")
    p.add_argument("name", nargs="?", help=t("its name (reports/<survey>.<name>.md); leave out to list them"))
    p.add_argument("--purpose", help=t("what it is for, e.g. \"lecture handout for public administration\""))
    p.add_argument("--length", type=int, help=t("about how long (characters in Japanese, words in English)"))
    p.add_argument("--count-citations", action="store_true",
                   help=t("count the citations in parentheses in the length (default: not counted)"))
    p.add_argument("--structure", help=t("its sections, separated by ; (e.g. \"background; findings; open questions\")"))

    p = sub.add_parser("audit", parents=[common, as_json],
                       help=t("record an audit by an AI model other than the one that wrote the survey"))
    p.add_argument("survey")
    p.add_argument("--by", metavar="MODEL", help=t("the model that audited it (e.g. \"Claude Opus 5.5\")"))
    p.add_argument("--note", default="", help=t("what was checked and fixed, in one line"))

    p = sub.add_parser("export", parents=[common, as_json], help=t("write the report for reading"))
    p.add_argument("survey")
    p.add_argument("--format", choices=list(FORMATS), help=t("the format (default: html; md with --draft)"))
    p.add_argument("-o", "--output", help=t("where to write it (default: next to the report in reports/)"))
    p.add_argument("--with-abstracts", action="store_true", help=t("also include each paper's abstract"))
    p.add_argument("--derived", metavar="NAME",
                   help=t("write a derived document (priorwork derive) for reading: reports/<name>.<NAME>.html"))
    p.add_argument("--draft", action="store_true",
                   help=t("write only the draft of the manuscript's sections 1–3, with its references "
                          "(a survey made with --manuscript)"))
    p.add_argument("--octavo", nargs="?", const="", default=None, metavar="PROJECT",
                   help=t("write for an Octavo project, with citations as [@key] from its .bib: the draft of the "
                          "manuscript, or the sections on the literature, into the project's inbox "
                          "(literature/priorwork/<survey>.md, with a .json manifest). Name the project (path or "
                          "folder name) when the survey is linked to several"))
    p.add_argument("--bib", metavar="PATH", help=t("the .bib to take the keys from (default: the Octavo project's)"))

    p = sub.add_parser("fulltext", parents=[common, as_json], help=t("get the full text"))
    p.add_argument("survey")
    p.add_argument("number", type=int, help=t("the paper number"))
    p.add_argument("--pdf", help=t("the path of the PDF"))

    p = sub.add_parser("zotero", parents=[common, as_json],
                       help=t("check the Zotero link / which included papers are in Zotero"))
    p.add_argument("survey", nargs="?")
    p.add_argument("--collections", action="store_true", help=t("list the collections of the Zotero library"))
    p.add_argument("--collection", metavar="NAME",
                   help=t("link a Zotero collection (name, path or key) to the survey; \"\" unlinks it"))
    p.add_argument("--import", dest="import_collection", action="store_true",
                   help=t("register the papers of the linked collection as candidates"))
    p.add_argument("--dois", action="store_true",
                   help=t("print only the DOIs of the papers not in Zotero (for the magic wand)"))
    p.add_argument("--add", action="store_true",
                   help=t("add the included papers to the linked collection (only with ZOTERO_WRITE=1)"))
    p.add_argument("--undo", nargs="*", type=int, metavar="NUMBER",
                   help=t("take back what --add wrote (all, or the papers with these numbers)"))
    p.add_argument("--dry-run", action="store_true", help=t("with --add or --undo: show what would be done, and do nothing"))
    p.add_argument("--status", nargs="+", choices=list(STATUSES), help=t("which papers (default: included only)"))
    p.add_argument("--refresh", action="store_true", help=t("reload the whole library instead of the changes"))

    p = sub.add_parser("search", parents=[common, filters, as_json], help=t("search"))
    p.add_argument("query", help=t("an English query (--bulk accepts + | - \"...\")"))
    p.add_argument("--into", metavar="SURVEY", help=t("register the results as candidates of the survey"))
    p.add_argument("--year", help=t("a year or a range (e.g. 2015-2024)"))
    p.add_argument("--bulk", action="store_true", help=t("bulk search (boolean operators, most cited first)"))
    p.add_argument("--sort", choices=SORTS, default="citations",
                   help=t("citations / relevance / recent (newest first) / cpy (citations per year)"))
    p.add_argument("--field", choices=list(SEARCH_FIELDS),
                   help=t("social: leave out papers outside the social sciences / all (default: the survey's setting; "
                          "all without --into)"))

    p = sub.add_parser("snowball", parents=[common, filters, as_json],
                       help=t("register candidates from the citations of the included papers"))
    p.add_argument("survey")
    p.add_argument("--direction", choices=["both", "references", "citations"], default="both")
    p.add_argument("--per-paper", type=int, default=50,
                   help=t("citing papers to look at per included paper (default: 50)"))
    p.add_argument("--min-links", type=int, default=0,
                   help=t("minimum number of links (default: 2 with three or more included papers, else 1)"))

    p = sub.add_parser("get", parents=[common, as_json], help=t("paper details"))
    p.add_argument("paper_id", help="DOI / DOI URL / Semantic Scholar ID / OpenAlex ID")

    for name, help_text in LINK_COMMANDS:
        p = sub.add_parser(name, parents=[common, as_json], help=t(help_text))
        p.add_argument("paper_id", help="DOI / DOI URL / Semantic Scholar ID / OpenAlex ID")
        p.add_argument("--limit", type=int, default=10, help=t("number of papers (default: 10)"))
        p.add_argument("--sort", choices=["recent", "cited"], default="recent",
                       help=t("recent: S2's order (roughly newest first) / cited: by citations (OpenAlex)"))

    p = sub.add_parser("journal", parents=[common, as_json], help=t("the SSCI status of a journal name or ISSN"))
    p.add_argument("name_or_issn")
    return parser


HANDLERS = {
    "init": cmd_init, "sync": cmd_sync, "upgrade": cmd_upgrade, "doctor": cmd_doctor, "settings": cmd_settings,
    "status": cmd_status, "archive": cmd_archive, "new": cmd_new, "scope": cmd_scope, "list": cmd_list,
    "include": cmd_set_status, "exclude": cmd_set_status, "maybe": cmd_set_status, "reset": cmd_set_status,
    "add": cmd_add, "fix": cmd_fix, "card": cmd_card, "render": cmd_render, "check": cmd_check, "derive": cmd_derive, "audit": cmd_audit, "read": cmd_read, "requests": cmd_requests, "export": cmd_export, "fulltext": cmd_fulltext, "zotero": cmd_zotero,
    "search": cmd_search, "snowball": cmd_snowball, "get": cmd_get,
    "citations": cmd_linked, "references": cmd_linked, "journal": cmd_journal,
}


def main(argv: Optional[List[str]] = None):
    args = build_parser().parse_args(argv)
    client = LiteratureClient(use_cache=not args.no_cache)
    try:
        HANDLERS[args.command](args, client)
    except SurveyError as e:
        ref = getattr(args, "survey", None) or getattr(args, "into", None)
        branches = [b for b in scaffold.survey_branches(ROOT) if ref and ref in b] if ref else []
        hint = ("\n" + t("It is on the branch {branch}: switch to it with `git switch {branch}`", branch=branches[0])
                if len(branches) == 1 and scaffold.git_branch(ROOT) != branches[0] else "")
        sys.exit(t("Error: {message}", message=e) + hint)
    except (ApiError, FulltextError, ManuscriptError, ZoteroError, scaffold.ScaffoldError,
            settings.SettingsError, requestsmod.RequestError) as e:
        sys.exit(t("Error: {message}", message=e))
    except KeyboardInterrupt:
        sys.exit(130)
