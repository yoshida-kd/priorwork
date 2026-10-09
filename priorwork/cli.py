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

from . import __version__, i18n, scaffold, settings, ssci
from .api import ApiError, LiteratureClient
from .check import ERROR, INFO, WARN, check_survey
from .doctor import NG, OK, run_checks
from .export import FORMATS, export
from .fulltext import FulltextError, fetch_fulltext
from .i18n import t, tl
from .snowball import snowball
from .survey import (
    CANDIDATE, CARD_FIELDS, DEFAULT_DEPTH, DEPTHS, EVIDENCE_KEYS, EXCLUDED, INCLUDED, MAYBE, STATUSES, Survey,
    SurveyError, author_short, evidence_key, evidence_label, status_label, status_trail,
)
from .workspace import ROOT, meta_dir, workspace_lang
from .zotero import ZoteroClient, ZoteroError

SORTS = ("citations", "relevance", "recent", "cpy")
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
    "  scope SURVEY ...           set the scope (research question, period, criteria)",
    "  list SURVEY                list the papers (numbers, decisions, SSCI)",
    "  include / exclude / maybe  record decisions (e.g. priorwork include SURVEY 2 5 7)",
    "  add SURVEY DOI...          register papers by DOI (included by default)",
    "  card SURVEY N [--set ...]  show or fill in the card of an included paper",
    "  render SURVEY              regenerate the managed blocks of the Markdown",
    "  export SURVEY              write the report for reading (HTML / Word / Markdown)",
    "  check SURVEY               find empty fields, unregistered citations and DOI mismatches",
    "  fulltext SURVEY N          get the full text (Zotero / open-access PDF)",
    "  zotero [SURVEY]            check the Zotero link / which included papers are in Zotero",
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


def added_json(added: List[tuple]) -> List[Dict[str, Any]]:
    return [{"number": e["number"], "new": is_new, "status": e["status"], "title": e["record"]["title"]}
            for e, is_new in added]


def survey_summary(s: Survey) -> Dict[str, Any]:
    return {"name": s.name, "topic": s.data["topic"], "created": s.data.get("created", ""), "depth": s.depth,
            "lang": s.lang, "report": str(s.md_path), "counts": s.counts(), "searches": len(s.data["searches"])}


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

def next_steps(s: Survey, zotero_missing: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """次にやること。id は VS Code の拡張機能がボタンに結びつける。"""
    c = s.counts()
    sc = s.data["scope"]
    unfilled = s.unfilled()
    steps: List[Dict[str, Any]] = []

    def step(sid: str, text: str, args: List[str]):
        steps.append({"id": sid, "text": text, "args": args})

    if not sc.get("question"):
        step("scope", t("Set the scope"), ["scope", s.name, "--question", "..."])
    if not s.data["searches"]:
        step("search", t("Search"), ["search", "<English query>", "--into", s.name])
    if c[CANDIDATE] or c[MAYBE]:
        step("screen", t("Screen {n|# candidate|# candidates}", n=c[CANDIDATE] + c[MAYBE]),
             ["list", s.name, "--status", "candidate", "maybe", "--abstract"])
    if c[INCLUDED] and not any(q["kind"] == "snowball" for q in s.data["searches"]):
        if s.depth == "full":
            step("snowball", t("Chase citations to find what was missed"), ["snowball", s.name])
        else:
            step("snowball", t("(Optional) chase citations if you worry about missed papers"), ["snowball", s.name])
    if zotero_missing:
        step("zotero", t("Add {n|# included paper|# included papers} to Zotero ({numbers})", n=len(zotero_missing),
                         numbers=", ".join(f"#{e['number']}" for e in zotero_missing[:10])), ["zotero", s.name])
    if unfilled:
        numbers = ", ".join(f"#{e['number']}" for e in unfilled[:10])
        text = (t("Fill in {n|# card|# cards} from the abstracts ({numbers}); \"abstract only\" is fine",
                  n=len(unfilled), numbers=numbers) if s.depth == "quick"
                else t("Fill in {n|# card|# cards} from the full texts ({numbers})", n=len(unfilled), numbers=numbers))
        step("fill", text, ["fulltext", s.name, str(unfilled[0]["number"])])
    step("check", t("Check"), ["check", s.name])
    if c[INCLUDED]:
        step("export", t("Write the version for reading (HTML)"), ["export", s.name])
    return steps


def cmd_status(args, client):
    if not args.survey:
        surveys = Survey.list_all()
        if args.json:
            return dump_json({"version": __version__, "root": str(ROOT), "workspace": meta_dir(ROOT).is_dir(),
                              "lang": workspace_lang(ROOT),
                              "git": {"repo": (repo := scaffold.in_git_repo(ROOT)),
                                      "remote": repo and scaffold.has_remote(ROOT)}, "sync": scaffold.sync_status(ROOT),
                              "surveys": [survey_summary(s) for s in surveys]})
        if not surveys:
            print(t("No surveys yet. Create one with `priorwork new \"<topic>\" --slug <english_slug>`."))
            return
        for s in surveys:
            c = s.counts()
            print(f"{s.name}: {s.data['topic']} | " + t("included {included} / maybe {maybe} / candidates {candidate} / "
                                                       "excluded {excluded}", **c))
        return

    s = Survey.load(args.survey)
    zotero_missing = zotero_unregistered(s)
    steps = next_steps(s, zotero_missing)
    if args.json:
        return dump_json({**survey_summary(s), "scope": s.data["scope"],
                          "unfilled": [e["number"] for e in s.unfilled()],
                          "zotero_missing": [e["number"] for e in zotero_missing],
                          "sync": scaffold.sync_status(ROOT), "next": steps})
    print(f"# {s.name}: {s.data['topic']}")
    print(t("Report: {path}", path=s.md_path))
    notice = scaffold.sync_status(ROOT)
    if notice:
        print(f"⚠️ {notice}")
    sc = s.data["scope"]
    unset = t("(not set)")
    print(t("RQ: {question} | period: {years} | depth: {depth}", question=sc.get("question") or unset,
            years=sc.get("years") or unset, depth=s.depth))
    print(t("included {included} / maybe {maybe} / candidates {candidate} / excluded {excluded}", **s.counts())
          + " | " + t("{n|# search|# searches}", n=len(s.data["searches"])))
    print("\n" + t("Next:"))
    for i, st in enumerate(steps, 1):
        print(f"  {i}. {st['text']}: priorwork {' '.join(_shell(a) for a in st['args'])}")


def _shell(arg: str) -> str:
    return f'"{arg}"' if re.search(r"[\s<>]", arg) else arg


def zotero_unregistered(s: Survey) -> List[Dict[str, Any]]:
    """Zotero 連携が設定されていれば、Zotero 未登録の採用論文を返す（失敗しても status 等は止めない）。"""
    z = ZoteroClient.from_env()
    if z is None:
        return []
    try:
        return [e for e in s.by_status(INCLUDED) if not z.status(e["record"])["registered"]]
    except ZoteroError as e:
        print(f"[Notice] {e}", file=sys.stderr)
        return []


def cmd_new(args, client):
    scope = {k: getattr(args, k) or "" for k in ("question", "years", "fields", "inclusion", "exclusion")}
    s = Survey.create(args.topic, args.slug, scope, depth=args.depth or DEFAULT_DEPTH, lang=args.lang)
    if args.json:
        return dump_json({**survey_summary(s), "state": str(s.json_path)})
    print(t("Created: {path}", path=s.md_path))
    print("         " + str(s.json_path))
    print(t("Next: priorwork search \"<English query>\" --into {name}", name=s.name))


def cmd_scope(args, client):
    s = Survey.load(args.survey)
    s.update_scope(**{k: getattr(args, k) for k in ("question", "years", "fields", "inclusion", "exclusion")})
    if args.depth:
        s.set_depth(args.depth)
    render_and_report(s)
    if args.json:
        return dump_json({"scope": s.data["scope"], "depth": s.depth})
    for k, v in s.data["scope"].items():
        print(f"{k}: {v}")
    print(f"depth: {s.depth}")


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
    added = []
    for pid in args.paper_ids:
        rec = client.get_paper(pid)
        entry, is_new = s.upsert(rec, "manual", status=status)
        if not is_new and status == INCLUDED:
            s.set_status([entry["number"]], INCLUDED)
        added.append((entry, is_new))
        if not args.json:
            state = t("new") if is_new else t("already registered")
            print_paper(rec, f"#{entry['number']} [{state} → {status_label(entry['status'])}]")
    s.log_search("manual", ", ".join(args.paper_ids), {"status": status}, len(args.paper_ids),
                 sum(1 for _, n in added if n))
    render_and_report(s)
    if args.json:
        dump_json({"added": added_json(added)})


def card_json(s: Survey, number: int) -> Dict[str, Any]:
    values = s.card(number)
    lang = s.lang
    return {"number": number, "evidence": evidence_key(values.get("evidence", "")),
            "evidence_options": [{"key": k, "label": evidence_label(k, lang)} for k in EVIDENCE_KEYS],
            "fields": [{"key": k, "label": tl(lang, label), "value": values.get(k, "")}
                       for k, label in CARD_FIELDS if k != "evidence"]}


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
    print(f"{s.md_path}: " + (t("updated") if changed else t("no changes")))


def cmd_check(args, client):
    s = Survey.load(args.survey)
    findings = check_survey(s, None if args.offline else client)
    if not args.offline:
        missing = zotero_unregistered(s)
        if missing:
            findings.append((INFO, t("{n|# included paper is|# included papers are} not in Zotero: {numbers} "
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
    try:
        out, issues = export(s, args.format, Path(args.output) if args.output else None, args.with_abstracts)
    except (RuntimeError, OSError) as e:
        sys.exit(t("Error: {message}", message=e))
    if args.json:
        return dump_json({"path": str(out.resolve()), "issues": issues})
    print(t("Written: {path}", path=out))
    if issues:
        print("⚠️ " + t("Written as a draft (marked at the top):"))
        for issue in issues:
            print(f"  - {issue}")


def cmd_fulltext(args, client):
    s = Survey.load(args.survey)
    entry = s.get(args.number)
    info = fetch_fulltext(entry, client, pdf_path=args.pdf, zotero=ZoteroClient.from_env())
    entry["fulltext"] = info
    s.save()
    if args.json:
        return dump_json({"number": entry["number"], **info})
    print(f"#{entry['number']} {entry['record']['title']}")
    print(t("Full text: {path} ({pages} pages, {chars} characters)", path=info["path"], pages=info["pages"] or "?",
            chars=f"{info['chars']:,}"))
    print(t("Source: {source}", source=info["source"]))
    if not info["page_markers"]:
        print(t("* This is Zotero's index text, which has no page breaks. Check the PDF before giving page numbers."))
    print(t("* Extracted text can garble columns, tables and formulas. Check numbers against the page in the PDF too."))


def cmd_zotero(args, client):
    z = ZoteroClient.from_env()
    if z is None:
        sys.exit(t("Error: {message}", message=t("Zotero is not set up. Set ZOTERO_API_KEY and ZOTERO_USER_ID in .env")))
    index = z.sync(force=args.refresh)
    items = index["items"].values()
    parents = [i for i in items if not i["parentItem"] and i["itemType"] != "attachment"]
    pdfs = [i for i in items if i["contentType"] == "application/pdf"]

    if not args.survey:
        print(t("Zotero library: {n|# item|# items} ({doi} with a DOI) / {pdfs|# PDF attached|# PDFs attached} | "
                "library version {version} | synced {synced}", n=len(parents),
                doi=sum(1 for i in parents if i["doi"]), pdfs=len(pdfs), version=index["version"],
                synced=index.get("synced_at", "")))
        print(t("WebDAV: {status}", status=z.check_webdav()))
        return

    s = Survey.load(args.survey)
    statuses = args.status or [INCLUDED]
    entries = [e for e in s.papers if e["status"] in statuses]
    missing = 0
    print(t("{name}: Zotero status of {n|# paper|# papers} ({statuses})", name=s.name, n=len(entries),
            statuses=" / ".join(status_label(x) for x in statuses)) + "\n")
    for e in entries:
        st = z.status(e["record"])
        r = e["record"]
        mark = ((("✅ " + t("in Zotero ({n|# PDF|# PDFs})", n=st["pdfs"])) if st["pdfs"]
                 else "🟡 " + t("in Zotero (no PDF)")) if st["registered"] else "❌ " + t("not in Zotero"))
        missing += not st["registered"]
        link = f"https://doi.org/{r['doi']}" if r.get("doi") else (r.get("url") or "")
        print(f"#{e['number']} {mark} | {author_short(r['authors'])} ({r.get('year') or 'n.d.'}) {r['title']}")
        if not st["registered"]:
            print(f"    {link}")
    print("\n" + t("{n|# paper is|# papers are} not in Zotero", n=missing)
          + (t(" (add them to Zotero by hand; this command picks them up the next time it runs)") if missing else ""))


# ---------------- Discovery commands ----------------

def cmd_search(args, client):
    warn_if_no_ssci_list()
    # 除外・重複統合で件数が減るので多めに取得する
    fetch_limit = min(max(args.limit * 4, 20), 100)
    papers = client.search(args.query, limit=fetch_limit, year=args.year, bulk=args.bulk)
    results = rank_and_filter(papers, args.include_preprints, args.ssci_only, args.sort)[: args.limit]

    if not args.into:
        if args.json:
            return dump_json(results)
        print(t("Results for '{query}': {n|# paper|# papers}", query=args.query, n=len(results)) + "\n")
        for i, p in enumerate(results, 1):
            print_paper(p, f"[{i}]")
        return

    s = Survey.load(args.into)
    added = add_records(s, results, "search")
    new = sum(1 for _, is_new in added if is_new)
    s.log_search("bulk" if args.bulk else "search", args.query,
                 {"year": args.year, "sort": args.sort, "ssci_only": args.ssci_only, "limit": args.limit},
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
    records = rank_and_filter(records, args.include_preprints, args.ssci_only, "relevance")[: args.limit]
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
    filters.add_argument("--limit", type=int, default=10, help=t("number of papers (default: 10)"))
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

    scope_args = argparse.ArgumentParser(add_help=False)
    scope_args.add_argument("--question", help=t("the research question"))
    scope_args.add_argument("--years", help=t("the period (e.g. 2000-2024)"))
    scope_args.add_argument("--fields", help=t("the fields (e.g. labour economics, sociology)"))
    scope_args.add_argument("--inclusion", help=t("inclusion criteria"))
    scope_args.add_argument("--exclusion", help=t("exclusion criteria"))
    scope_args.add_argument("--depth", choices=list(DEPTHS),
                            help=t("the depth of the survey (quick or full; default full)"))

    p = sub.add_parser("new", parents=[common, scope_args, as_json], help=t("create a survey"))
    p.add_argument("topic", help=t("the topic (any language)"))
    p.add_argument("--slug", required=True, help=t("an English slug for the file name (e.g. minimum_wage_employment)"))
    p.add_argument("--lang", choices=i18n.LANGS, help=t("the language of the report (default: the workspace's)"))

    p = sub.add_parser("scope", parents=[common, scope_args, as_json], help=t("set the scope"))
    p.add_argument("survey")

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
    p.add_argument("paper_ids", nargs="+", help="DOI / DOI URL / Semantic Scholar ID / OpenAlex ID")
    p.add_argument("--candidate", action="store_true", help=t("register as a candidate, not as included"))

    p = sub.add_parser("card", parents=[common, as_json], help=t("show or fill in the card of an included paper"))
    p.add_argument("survey")
    p.add_argument("number", type=int, help=t("the paper number"))
    p.add_argument("--set", nargs="+", metavar="KEY=VALUE",
                   help=t("fields to write (evidence=unchecked|abstract|fulltext, rq, x, y, data, method, findings, "
                          "limits, memo); a new line starts the bullet points below"))

    p = sub.add_parser("render", parents=[common], help=t("regenerate the managed blocks of the Markdown"))
    p.add_argument("survey")

    p = sub.add_parser("check", parents=[common, as_json], help=t("check the survey"))
    p.add_argument("survey")
    p.add_argument("--offline", action="store_true", help=t("do not re-check the DOIs with OpenAlex"))

    p = sub.add_parser("export", parents=[common, as_json], help=t("write the report for reading"))
    p.add_argument("survey")
    p.add_argument("--format", choices=list(FORMATS), default="html", help=t("the format (default: html)"))
    p.add_argument("-o", "--output", help=t("where to write it (default: next to the report in reports/)"))
    p.add_argument("--with-abstracts", action="store_true", help=t("also include each paper's abstract"))

    p = sub.add_parser("fulltext", parents=[common, as_json], help=t("get the full text"))
    p.add_argument("survey")
    p.add_argument("number", type=int, help=t("the paper number"))
    p.add_argument("--pdf", help=t("the path of the PDF"))

    p = sub.add_parser("zotero", parents=[common], help=t("check the Zotero link / which included papers are in Zotero"))
    p.add_argument("survey", nargs="?")
    p.add_argument("--status", nargs="+", choices=list(STATUSES), help=t("which papers (default: included only)"))
    p.add_argument("--refresh", action="store_true", help=t("reload the whole library instead of the changes"))

    p = sub.add_parser("search", parents=[common, filters, as_json], help=t("search"))
    p.add_argument("query", help=t("an English query (--bulk accepts + | - \"...\")"))
    p.add_argument("--into", metavar="SURVEY", help=t("register the results as candidates of the survey"))
    p.add_argument("--year", help=t("a year or a range (e.g. 2015-2024)"))
    p.add_argument("--bulk", action="store_true", help=t("bulk search (boolean operators, most cited first)"))
    p.add_argument("--sort", choices=SORTS, default="citations",
                   help=t("citations / relevance / recent (newest first) / cpy (citations per year)"))

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
    "status": cmd_status, "new": cmd_new, "scope": cmd_scope, "list": cmd_list,
    "include": cmd_set_status, "exclude": cmd_set_status, "maybe": cmd_set_status, "reset": cmd_set_status,
    "add": cmd_add, "card": cmd_card, "render": cmd_render, "check": cmd_check, "export": cmd_export, "fulltext": cmd_fulltext, "zotero": cmd_zotero,
    "search": cmd_search, "snowball": cmd_snowball, "get": cmd_get,
    "citations": cmd_linked, "references": cmd_linked, "journal": cmd_journal,
}


def main(argv: Optional[List[str]] = None):
    args = build_parser().parse_args(argv)
    client = LiteratureClient(use_cache=not args.no_cache)
    try:
        HANDLERS[args.command](args, client)
    except (ApiError, SurveyError, FulltextError, ZoteroError, scaffold.ScaffoldError, settings.SettingsError) as e:
        sys.exit(t("Error: {message}", message=e))
    except KeyboardInterrupt:
        sys.exit(130)
