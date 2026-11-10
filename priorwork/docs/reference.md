# Priorwork reference

> This is the source of the reference. Read it at **<https://yoshida-kd.github.io/priorwork/reference/>**. <!-- pages:skip -->

This page is written for **AI agents** working in a Priorwork workspace, and for anyone who
wants every detail. People who use Priorwork from VS Code should read the
[guide](https://yoshida-kd.github.io/priorwork/guide/) instead.

The same text comes with Priorwork, matching the installed version:

```bash
./priorwork docs                     # the list of sections
./priorwork docs 5.2                 # one section, by number
./priorwork docs zotero              # or by words from its heading
./priorwork docs --search snowball   # every section that mentions a word
./priorwork docs --all               # everything
```

`--lang ja` gives the Japanese text. The workspace's `AGENTS.md` and skills say **how to run a
survey**; this page is what each command does.

---

## 1. Rules and where things are

### 1.1 The rules

- Leave a reason for every decision and for the scope; never overturn the user's decisions or
  corrections.
- Stop where the survey's mode says (standard, auto, manual); decide on your own in between.
- Every paper mentioned in the text is registered; never write authors, years or DOIs from memory.
- Cards hold only what the abstract or the full text says, with the evidence level updated.
- Name papers as "Author (year)" when talking to the user, not by number.
- Run `./priorwork check` before calling anything finished.
- Write to Zotero only through `./priorwork zotero --add`, and only when it is allowed
  (`ZOTERO_WRITE=1`).
- In Git, work on a branch named after the survey, commit and push, open a pull request; never merge.
- Never open or edit Priorwork's own files (inside `.venv`), `AGENTS.md` or the skills; instructions
  for one workspace go in `AGENTS.local.md`.

### 1.2 Inside a workspace

```text
my-surveys/
├── reports/                 # the reports (the working .md, the exported .html, the manuscript drafts .draft.md, …)
├── manuscripts/             # manuscripts to start from, with their tables (one folder per paper; only read)
├── AGENTS.md, CLAUDE.md     # instructions for agents (updated automatically; do not edit)
├── AGENTS.local.md          # instructions for this workspace only (edit freely)
├── .agent/skills/           # the skills for each step (also seen through .claude/skills)
├── priorwork                # ./priorwork (what the agent runs)
├── requirements.txt         # the engine's version (priorwork==X.Y.Z)
├── .env                     # the settings (not in Git)
└── .priorwork/
    ├── config.json          # the workspace's language
    ├── surveys/             # the state of each survey (in Git)
    ├── requests/            # requests from Octavo
    ├── cache/               # full texts, the Zotero index (not in Git)
    └── data/                # the SSCI list (not in Git)
```

| File | Contents | Editing |
| :--- | :--- | :--- |
| `reports/YYYYMMDD_<slug>.md` | the working report (a redone survey is `YYYYMMDD_v2_<slug>.md`) | the text and the card fields by hand or by the agent; everything between `<!-- BEGIN priorwork:… -->` and `<!-- END priorwork:… -->` is regenerated |
| `.priorwork/surveys/YYYYMMDD_<slug>.json` | candidates, decisions and reasons (with their history), the search log, the scope, the depth, the mode, the Zotero collection | only through `./priorwork` |

`SURVEY` in the commands below is the file name without the extension, or the slug (with the
version for a redone survey: `v2_<slug>`).

### 1.3 Finding out the state

```bash
./priorwork status                   # every survey, and surveys on other branches
./priorwork status SURVEY            # its progress and next steps
./priorwork list SURVEY --status candidate maybe
./priorwork doctor --online          # the settings and the connections
```

Most commands print JSON with `--json`.

---

## 2. Surveys

### 2.1 Creating and scoping

```bash
./priorwork new "<topic>" --slug <slug> --by "<model>" --mode standard --depth full --question "..."
./priorwork scope SURVEY --question "..." --years 2000-2025 --fields "..." --inclusion "..." --exclusion "..."
./priorwork scope SURVEY --go-on     # the user has checked the scope: carry on
```

- `--slug` is an English file name (`minimum_wage_employment`); the report is
  `reports/YYYYMMDD_<slug>.md`. A second survey with the same slug is numbered `YYYYMMDD_v2_<slug>`.
- `--by` records the model that wrote it (the audit refuses the same model).
- `--search-field social|medical|all`: drop results outside that field (default `social`; `medical` in a medical survey).
- `--discipline medical` (only on `new`): a clinical survey. See [2.4](#24-medical-surveys).

### 2.2 Modes and depth

| Mode | Where it stops |
| :--- | :--- |
| `standard` (default) | once the scope is set, and before writing the cards (for the user to collect the papers in Zotero) |
| `auto` | never |
| `manual` | after every step; decisions are recommendations it waits on |

| | `quick` | `full` |
| :--- | :--- | :--- |
| Searches | 2–3 queries, 10 results each | 2–4 queries per subtopic, 25 results each, aiming at 100+ candidates |
| Citation chasing | optional | yes |
| Cards | abstracts are fine | every included paper in the full text (abstract only when none can be found) |
| Text | an overview and the comparison table | background, theories, debates and gaps |

The mode is recorded in the survey. A mode in `AGENTS.local.md` ("Mode: full auto") applies to new
surveys.

### 2.3 Redoing and archiving

```bash
./priorwork archive SURVEY           # hide it from the list; the files stay
./priorwork archive SURVEY --undo
./priorwork status --archived
```

### 2.4 Medical surveys

`./priorwork new "<topic>" --slug <slug> --discipline medical` makes a survey for clinical research. It cannot be changed later. Other surveys in the workspace stay as they are.

| | Social (default) | Medical |
| :--- | :--- | :--- |
| Search | Semantic Scholar, OpenAlex | PubMed and Semantic Scholar (`--source`); if one fails, the other's results |
| Query | `+ \| -`, `"phrases"` | the same, plus PubMed's tags (`[tiab]`, `[MeSH Terms]`, `[pt]`) |
| Journals | ✅ SSCI, 🟡, ⚪ | ✅ MEDLINE (PubMed's record of the paper), ✅ SCIE (`settings --import-scie`), 🔍 In PubMed, 🔍 not found in PubMed |
| Left out of searches | working papers, preprints, books | the same, plus letters, editorials and comments (`--include-preprints` keeps them) |
| Card fields | RQ, X, Y, data, identification | clinical question, population, intervention or exposure, outcomes, study design, effect sizes |
| Report | theories, methods | evidence by study design, effects, safety and harms |
| Full text | as in 5.2 | the same, then PMC's text through Europe PMC (no page breaks) |

- The keys for `card --set` are the same: `rq`, `data`, `x`, `y`, `method`, `findings`, `limits`, `memo`.
- `add` and `fix --id` also take `PMID:<number>` or a PubMed URL. A DOI is looked up in PubMed first.
- ✅ MEDLINE is PubMed's status of that paper; a very recent paper in an indexed journal may show 🔍 In PubMed. `./priorwork journal "<name or ISSN>" --medline` asks the NLM Catalog about the journal.
- Retractions (PubMed, OpenAlex) give a ⚠️ and an ERROR in `check`, which `fix --confirm` does not clear. `check` without `--offline` also finds later retractions.
- The search log keeps PubMed's reading of each query and its total count.
- The report says it is a narrative review, neither a systematic review nor clinical guidance.

### 2.5 Several surveys at once

```bash
./priorwork new "<topic>" --slug <slug> --by "<model>" --worktree
./priorwork worktree                       # the worktrees, with what is not committed or pushed
./priorwork worktree --remove <slug>       # the branch stays
```

- `--worktree` makes `worktrees/<slug>/` from the top of main, on a new branch named after the survey, without touching the current folder or branch. Run that survey's commands from that folder.
- `.env`, `.venv`, `.priorwork/data` and `.priorwork/cache` there are links to the workspace's, so keys, journal lists, the engine and fetched full texts are shared. An upgrade reaches all of them. `git`'s `info/exclude` keeps the links and `worktrees/` out of Git, with no commit.
- `status` lists them, and leaves their branches out of "On other branches".
- `--remove` refuses while there are uncommitted changes or commits not pushed. `--force` throws them away.

---

## 3. Finding the literature

### 3.1 Search

```bash
./priorwork search "<English query>" --into SURVEY
./priorwork search "minimum wage + employment -teen" --into SURVEY --bulk --sort citations
./priorwork search "<query>" --into SURVEY --year 2010-2024 --journal "American Economic Review" --ssci-only
```

- Default: Semantic Scholar's relevance search. `--bulk`: `+` (and), `|` (or), `-` (not),
  `"phrases"`, most cited first (`AND`, `OR`, `NOT` are turned into these).
- `--sort citations|relevance|recent|cpy`, `--year`, `--journal` (full name or ISSN, repeatable),
  `--ssci-only` (or `--indexed-only`; in a medical survey, MEDLINE and SCIE), `--field social|medical|all`, `--source auto|pubmed|s2`, `--limit N` (default 25 into a full survey, else 10),
  `--include-preprints` (books, working papers, preprints and unknown venues are left out by
  default).
- DOIs, journals and ISSNs are checked against OpenAlex; when a working paper and its published
  version are both found, only the published one is kept.
- `--journal` searches Semantic Scholar (by `venue`) **and** OpenAlex (by the journal's source ID,
  from its name or ISSN). Semantic Scholar often has no venue for a paper, and the venue filter
  drops it silently; OpenAlex's results that Semantic Scholar did not have are added (merged by DOI;
  with `--bulk` re-sorted by citations; otherwise Semantic Scholar's order is kept and each added
  paper goes in at its OpenAlex rank), and a notice says how many. With `--journal` the results are
  not grouped by SSCI status (same journals). Each record's `found_in` says where it was found (the
  list shows it as "found in: S2 / OpenAlex / S2 + OpenAlex"), and the search log records
  `openalex` (`used` / `failed`) and `openalex_added`. When OpenAlex fails, the Semantic Scholar
  results are returned alone, with a notice. Without `--journal`, OpenAlex is not searched (its
  keyword search is less precise).
- A journal paper whose DOI is a preprint / working paper (OSF, SocArXiv, SSRN, arXiv, NBER, …) or
  unknown to OpenAlex is looked up by title in OpenAlex (with the journal's source ID or ISSN). When
  the journal version matches (`same_title`, the year within ±2), its DOI and details replace them:
  the old DOI is kept as `preprint_doi` and a note (ℹ️, `notes`) says so. Otherwise the warning
  stays. At most 10 such lookups per search.

### 3.2 Chasing citations

```bash
./priorwork snowball SURVEY --direction both --min-links 2
```

Collects the references and citing papers of the included papers from OpenAlex, ordered by how
many included papers each is linked to. With three or more included papers, only those linked to
at least two are taken by default.

### 3.3 One paper

```bash
./priorwork add SURVEY 10.1257/aer.91.5.1369             # register and include
./priorwork add SURVEY 10.1257/aer.91.5.1369 --candidate # register as a candidate
./priorwork get 10.1257/aer.91.5.1369
./priorwork citations 10.1257/aer.91.5.1369 --sort cited
./priorwork references 10.1257/aer.91.5.1369
./priorwork journal "Journal of Public Administration Research and Theory"
./priorwork fix SURVEY 12 --id 10.1093/jopart/xyz --authors "A; B" --year 2019
./priorwork fix SURVEY 12 --journal "Labour Economics" --pages 101-122
./priorwork fix SURVEY 12 --confirm "checked the publisher's page"
```

`fix` replaces a working-paper DOI with the published one, corrects authors, year, title, journal
or pages, or clears a warning you have checked (with what you checked). Correct the journal when the
databases give a working-paper series (SSRN) for a published paper, and the pages when they give a
single page (`145-145`). If `--id` comes back with another DOI, the databases hold the two versions as
one paper; `fix` says so.

---

## 4. Screening

```bash
./priorwork include SURVEY 2 5 7 --reason "..."
./priorwork exclude SURVEY 3 --reason "theory only"
./priorwork maybe SURVEY 9 --reason "..."
./priorwork reset SURVEY 9
```

Check a paper with a warning before including it:

| Warning | Meaning | What to do |
| :--- | :--- | :--- |
| The DOI points to another title | Semantic Scholar's DOI belongs to another paper | find the right DOI, `fix --id` |
| The DOI is a working paper / preprint version | a journal is named, but the DOI is an SSRN-style version | `fix --id` the published DOI |
| OpenAlex does not know the DOI / No DOI / not verified | wrong, missing or unchecked | check it; `fix` |
| May be a book review or comment | a title like "…, by Author", or a single page | usually exclude |

Never call a 🟡 (guessed) journal "in the SSCI": only ✅ is checked against the list.

---

## 5. Paper cards

### 5.1 The fields

```
### #1 Acemoglu et al. (2001): The Colonial Origins of Comparative Development
- Source: American Economic Review 91(5) | ✅ SSCI | cited by 8534 | DOI   ← automatic
- Evidence: unchecked / abstract only / full text checked
- RQ: Do institutions cause the differences in income between countries?
- X (explanatory variable / treatment): the quality of today's institutions
- Y (outcome): GDP per capita in 1995
- Data / sample: 64 former colonies
- Identification: 2SLS, with settler mortality as the instrument
- Main findings: better institutions raise income substantially
- Limitations: measurement error in the mortality data
- Notes:
```

```bash
./priorwork card SURVEY 3
./priorwork card SURVEY 3 --set evidence=fulltext rq="..." findings="..."
```

- Keys: `evidence` (`unchecked`, `abstract`, `fulltext`), `rq`, `x`, `y`, `data`, `method`,
  `findings`, `limits`, `memo`, and `role` (the role in the manuscript) for a survey started from a
  manuscript. A new line in a value starts the bullet points below the field.
- The **first line** of a field goes into the comparison matrix: one short sentence.
- Only what the abstract or full text says; otherwise "not reported". In the report's language,
  terms in the original in brackets.
- With `fulltext`, give the page (`(p. 12)`) for the data, the identification and the main
  findings, or "(page not checked)" when the text has no page breaks.
- A card of a paper no longer included is kept in the state file and comes back with it.

### 5.2 Full texts

```bash
./priorwork fulltext SURVEY 3
./priorwork fulltext SURVEY 3 --pdf path/to/paper.pdf
```

Looked for in this order: a PDF in the local Zotero (by DOI); a PDF found through the Zotero web
API (WebDAV or Zotero's file sync, the survey's collection first); the text Zotero indexed (no
pages); an open-access PDF (every location OpenAlex knows, and `citation_pdf_url` on landing
pages). Only the extracted text is kept, in `.priorwork/cache/fulltext/`. A failure is recorded.

---

## 6. Writing, checking and exporting

### 6.1 The report

The synthesis comes first: background (1); theoretical traditions, methods, consensus and
debates, gaps (2–5, each claim citing included papers); hypotheses and implications for the
user's study (6, kept apart from the literature); then the comparison matrix, the cards and the
references (generated). Mermaid diagrams (```` ```mermaid ````) are drawn in the HTML.

```bash
./priorwork render SURVEY     # regenerate the managed blocks
```

### 6.2 Checks

```bash
./priorwork check SURVEY
./priorwork check SURVEY --offline
```

| Check | Level |
| :--- | :--- |
| Author–year citations in the text and cards match registered papers | ERROR (unregistered) / WARN (not included) |
| 2001a / 2001b match the references | WARN |
| DOIs in the text are registered | ERROR |
| ⚠️ on included papers; DOI and title agree in OpenAlex | ERROR |
| Evidence level of each card, empty fields | WARN |
| `fulltext` cards: numbers not in the full text, pages not in the paper, no page, no full text | WARN |
| Cards not in the report's language | WARN |
| Synthesis sections citing no paper; a count of included papers that disagrees | WARN |
| Included papers missing from Zotero | WARN |
| The report matches the state file | WARN |
| Unscreened candidates, non-SSCI included papers, organisations or table numbers taken for citations | INFO |

Something that is not a citation can be excluded in the report:

```markdown
<!-- priorwork:ignore-citation Smith (2015) -->
```

### 6.3 Audit by another model

```bash
./priorwork audit SURVEY --by "<model>" --note "..."
./priorwork audit SURVEY
```

Only when the user asks. The auditor compares every card with the full text, checks the
direction of each citation, hypotheses passed off as the literature and the excluded papers, fixes
them and records the audit. Refused for the model that wrote the survey.

### 6.4 Export

```bash
./priorwork export SURVEY                       # reports/<name>.html
./priorwork export SURVEY --format docx         # or md
./priorwork export SURVEY --with-abstracts
./priorwork derive SURVEY handout --purpose "lecture handout" --length 2000 --structure "a; b; c"
./priorwork export SURVEY --derived handout
```

Marked *Draft* while cards are unchecked or empty, or the check has ERRORs. `derive` records a
short text made from the survey (`reports/<name>.<text name>.md`): it cites only included papers
checked in the full text, and the length leaves out citations in parentheses unless
`--count-citations`.

---

## 7. Starting from a manuscript

```bash
./priorwork read manuscripts/make_or_buy
./priorwork new "<topic>" --slug <slug> --manuscript manuscripts/make_or_buy
./priorwork add SURVEY --cited
./priorwork export SURVEY --draft
```

- `read` turns Markdown, Quarto (.qmd and its HTML), LaTeX, Word and PDF into text, and lists the
  user's marks: `[cite]`, `[@?]`, `TODO(priorwork): …`.
- One manuscript gets one survey and one report: what it lacks, the claims that need literature (with conflicting findings), what to add (**Where** quotes the sentence it goes before or after, with **Why**; whole sections if needed), a check of each cited paper's direction, missing literature, the hypotheses and their literature, the argument, and what to do first. Sections nobody asked for say "Not covered".
- `export --draft` writes what to add, with its references. `export --octavo` adds a part for the author with the rest.
- Surveys made by earlier versions with `--purpose draft` or `advice` keep their own report and carry on as they are.
- Cards get a **Role in the manuscript** (`role`). The manuscript is never rewritten.
- `add --cited` registers the papers the manuscript cites (the DOIs in its `.bib`).

---

## 8. Zotero

```bash
./priorwork zotero                          # the link
./priorwork zotero --collections            # the collections, as a tree
./priorwork zotero SURVEY --collection "Parent / Child"   # link ("" unlinks)
./priorwork zotero SURVEY --import          # register the collection's papers as candidates
./priorwork zotero SURVEY --dois            # DOIs of included papers not in Zotero (for the magic wand)
./priorwork zotero SURVEY --add --dry-run   # what --add would put into the collection
./priorwork zotero SURVEY --add
./priorwork zotero SURVEY --add --also "Paper / References"   # and into another collection, such as an Octavo project's
./priorwork zotero SURVEY --undo
```

- Settings in `.env`: `ZOTERO_API_KEY`, `ZOTERO_USER_ID`, `ZOTERO_DATA_DIR` (a local Zotero),
  `ZOTERO_WEBDAV_URL` / `_USER` / `_PASSWORD` (file sync through WebDAV), `ZOTERO_WRITE`.
- Reading only by default. `--add` needs `ZOTERO_WRITE=1` and a key with write access: an item
  already in the library (same DOI or title) is added to the collection, otherwise a new item is
  made; it never changes or deletes items, never touches other collections, never makes one.
  `--undo` takes back only what Priorwork wrote. In the standard mode show the list at the stop
  before the cards and add once the user agrees; in auto add without stopping; in manual ask.
- Once linked, "in Zotero" means in that collection (and those under it); full texts come from
  its PDFs first.
- The library is read from zotero.org and kept in `.priorwork/cache/zotero/` (only the changes are
  read; `--refresh` reads all). When a paper has no PDF there, `fulltext` asks Zotero for that
  paper's attachments again. When the library has the same paper twice, the one with a PDF is used
  and a notice names both: ask the user to merge them in Zotero (Duplicate Items).

---

## 9. Octavo

```bash
./priorwork scope SURVEY --octavo ../make_or_buy
./priorwork export SURVEY --octavo
./priorwork export SURVEY --octavo ../make_or_buy --bib literature/literature.bib
./priorwork requests
./priorwork requests <id> --done --survey SURVEY
./priorwork requests <id> --decline --note "..."
```

- An Octavo manuscript stays in its project; read it in place. One survey can serve several
  projects, and one project several surveys.
- `export --octavo` writes into the project's `literature/priorwork/`: `<survey>.md` (citations as
  `[@key]` from the project's `.bib`), `<survey>.json` (a manifest: `draft`, `synthesis` or
  `complete`) and `<survey>.cards.json` (the cards). It writes nowhere else in the project.
- A paper not in the `.bib` is written `[@PRIORWORK:<DOI>]`; the user adds it to Zotero, then runs
  `octavo bib pull` and `octavo priorwork resolve` in the Octavo project.
- Link the survey to a Zotero collection under the Octavo project's (`zotero_collection`), so that
  `octavo bib pull` gathers every survey's included papers.
- Requests from Octavo arrive in `.priorwork/requests/<id>.json`; record the outcome.

---

## 10. Settings and the engine

```bash
./priorwork settings                         # the settings (key values are never shown)
./priorwork settings --stdin                 # set them from KEY=VALUE lines on stdin
./priorwork settings --import-ssci SSCI.csv  # the SSCI list from Clarivate's Master Journal List
./priorwork doctor --online
./priorwork sync                             # AGENTS.md and the skills to the engine's version (--diff, --force)
./priorwork upgrade                          # the newest engine, then sync (--to X.Y.Z)
```

| Setting | Purpose |
| :--- | :--- |
| `SEMANTIC_SCHOLAR_API_KEY` | recommended; without it, searches often hit HTTP 429 |
| `OPENALEX_API_KEY`, `OPENALEX_MAILTO` | optional |
| `NCBI_API_KEY` | optional; PubMed allows 10 requests a second with it, 3 without |
| `ZOTERO_*` | [8](#8-zotero) |

The SSCI status: ✅ checked against the list, 🟡 guessed from a built-in list of about 100 journals
(verify), 🔍 unknown, ⚪ not in the list; 📕 books, ❌ working papers and preprints, ❓ unknown venues
are left out of searches by default.

### 10.1 Retries, cache and language

- Retries: HTTP 429, 5xx and network errors wait 5, 10, 20, 40 and 60 s, up to 5 times (`PRIORWORK_MAX_RETRIES`).
- Cache: API responses stay in `~/.cache/priorwork/` for 7 days (`PRIORWORK_CACHE_TTL_DAYS`; `PRIORWORK_NO_CACHE=1` or `--no-cache` turns it off).
- Messages: `PRIORWORK_LANG=ja|en`, otherwise the locale.

---

## 11. Commands

```bash
./priorwork init [DIR] [--lang en|ja]
./priorwork settings [--stdin] [--import-ssci CSV]
./priorwork doctor [--online]
./priorwork sync [--force|--diff]
./priorwork upgrade [--to X.Y.Z]
./priorwork worktree [--remove NAME [--force]]
./priorwork status [SURVEY] [--archived]
./priorwork new "<topic>" --slug <slug> --by "<model>" [--mode standard|auto|manual] [--depth quick|full] [--manuscript PATH] [--question ... --years ... --fields ... --inclusion ... --exclusion ...]
./priorwork scope SURVEY [--question ...] [--mode ...] [--go-on] [--depth ...] [--search-field social|medical|all] [--manuscript PATH] [--octavo PATH] [--by "<model>"]
./priorwork archive SURVEY [--undo]
./priorwork read PATH [--out FILE]
./priorwork requests [ID] [--done --survey SURVEY | --decline --note "..."]
./priorwork search "<query>" [--into SURVEY] [--bulk] [--sort citations|relevance|recent|cpy] [--year 2010-2024] [--journal "<name>" ...] [--ssci-only] [--field social|medical|all] [--limit N]
./priorwork snowball SURVEY [--direction both|references|citations] [--limit N] [--min-links N]
./priorwork list SURVEY [--status candidate maybe included excluded] [--abstract]
./priorwork include|exclude|maybe SURVEY N... --reason "..."
./priorwork reset SURVEY N...
./priorwork add SURVEY <DOI>... [--candidate] | --cited
./priorwork fix SURVEY N [--id <DOI>] [--authors "A; B"] [--year Y] [--title T] [--journal J] [--pages P] [--confirm "..."]
./priorwork card SURVEY N [--set KEY=VALUE ...]
./priorwork fulltext SURVEY N [--pdf PATH]
./priorwork render SURVEY
./priorwork check SURVEY [--offline]
./priorwork audit SURVEY [--by "<model>" --note "..."]
./priorwork export SURVEY [--format html|docx|md] [--with-abstracts] [--draft] [--derived NAME] [--octavo [PROJECT] [--bib PATH]]
./priorwork derive SURVEY [NAME --purpose "..." --length N --structure "a; b; c" [--count-citations]]
./priorwork zotero [SURVEY] [--collections] [--collection NAME] [--import] [--dois] [--add [--also COLLECTION] [--dry-run]] [--undo]
./priorwork get <DOI>
./priorwork citations <DOI> [--sort cited]
./priorwork references <DOI> [--sort cited]
./priorwork journal "<journal or ISSN>"
./priorwork docs [SECTION] [--search WORD] [--all] [--lang en|ja]
```

---

## 12. When something goes wrong

- **HTTP 429 (rate limited)**: set `SEMANTIC_SCHOLAR_API_KEY`; Priorwork retries up to five times.
- **A paper cannot be found**: papers in domestic journals (J-STAGE and the like) are often in neither
  Semantic Scholar nor OpenAlex; they are out of scope.
- **The full text cannot be fetched**: publishers refuse automated downloads; ask the user to
  attach the PDF in Zotero, or use `fulltext --pdf`.
- **The skills look out of date**: `./priorwork status` says so; `./priorwork sync`.
- **"It is on the branch …"**: the survey is on another branch; `git switch` to it.
- **Not sure what is wrong**: `./priorwork doctor --online`.
