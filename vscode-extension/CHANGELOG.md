# Changelog

Priorwork's command-line tool (`priorwork` on PyPI) and this extension are
released together, under one version number.

## 0.1.5

- **The sidebar no longer sticks at "priorwork status failed".** The cause
  was two `status` runs (one per survey) writing the Zotero cache through the
  same temporary file at once. The cache now uses a file per process, a
  Zotero problem no longer stops `status`, and the next steps retry by
  themselves once, then offer *Reload*.
- **Archive a survey** (right-click → *Archive the Survey…*, or
  `priorwork archive SURVEY`). It moves to an *Archived* group at the bottom
  of the sidebar; nothing is deleted, and it can be brought back (`--undo`).
  `priorwork status` lists the archived ones with `--archived`.
- **Surveys with the same topic are told apart** in the sidebar by name and
  date (e.g. `make_or_buy_v2`). `priorwork new` says when the topic already
  exists. Asked to redo a survey, the agent makes a new one and archives the
  old one once you say so.
- **Zotero collection in the sidebar.** Each survey has a row *Link a Zotero
  collection…*, which reads *Zotero: <collection>* once linked.
- **The agent leaves Git alone** unless you ask (it used to commit at each
  break); at the end it asks whether to commit.
- The title bar of an HTML file no longer shows Priorwork's viewer icon next
  to Live Preview's (right-click the file in the explorer instead).
- **Claude Code runs `./priorwork` without asking.** Making a workspace, and
  `priorwork sync`, add `Bash(./priorwork:*)` to `.claude/settings.json`
  (other settings are kept; other commands are still checked). Antigravity
  has no workspace settings file, so the guide explains adding `./priorwork`
  to its allow list once. The permission is only for the agent: the sidebar
  never needs it.
- **Full surveys read every included paper in the full text.** "Core papers
  only" proved too vague. A card may stay "abstract only" only when no full
  text could be found: `fulltext` now records a failed attempt, and `check`
  warns about abstract-only cards whose full text was never tried (or was
  fetched but not used) and lists the ones with no full text, so you can
  attach their PDFs in Zotero. In a survey made from a manuscript, the papers
  the draft cites must be checked in the full text.
- **A place for manuscripts.** Put a manuscript whose analysis is done, with
  its tables, in `manuscripts/<paper name>/` (the workspace gets the folder
  and a README). `--manuscript` takes the folder, and the agent reads all of
  it. **New Survey → Start from my manuscript** picks it (offering to copy one
  from outside the workspace) and copies the request for your agent.

## 0.1.4

- **Start from your manuscript.** If the data, methods and analysis of a paper
  are written, ask your agent to write its introduction, literature review and
  theory and hypotheses. It reads the manuscript, lists the claims that need
  literature (including findings that conflict with your results), searches
  and screens claim by claim, records each paper's *Role in the manuscript* on
  its card (a Role column in the matrix too), and drafts sections 1–3 in the
  language of the manuscript. A separate section records the literature
  behind each hypothesis and which results to treat as exploratory, so that
  the hypotheses are not written after the fact. The manuscript itself is
  never rewritten. New skill `priorwork-manuscript`;
  `priorwork new … --manuscript PATH`; `priorwork export SURVEY --draft`
  writes the draft with the references it cites (`reports/<name>.draft.md`).
- *Ask Your Agent…* and the next step *Write the draft* ask for the draft of
  the manuscript on a survey made from one.

## 0.1.3

- **Hand the survey to your agent.** The agent now carries a survey through to
  the exported report without stopping: it sets the scope, searches, screens
  (recording a reason for every decision, includes too), chases citations,
  fills in the cards, writes, checks and exports, then reports what it decided.
  You overturn decisions and correct cards in the sidebar; the agent follows
  them. To decide each paper yourself, ask it to go through it together with
  you (or say so in `AGENTS.local.md`).
- **No skill names to type.** Ask in plain words. The skills are renamed
  `priorwork` (the entry point) and `priorwork-new`, `priorwork-screen`,
  `priorwork-snowball`, `priorwork-extract`, `priorwork-check`; `priorwork
  sync` replaces the old `survey-*` skills.
- **New Survey → Ask your agent to do it** copies a request for a whole survey;
  *Ask Your Agent…* gains *Carry on to the end* and *Search more*. After
  copying, a button opens the chat of Claude Code, Antigravity or Copilot.
- **Full surveys search more.** `search` and `snowball` take 25 papers by
  default for a full survey (10 otherwise), and the next steps say *Search
  more* until a full survey has 6+ queries and 80+ papers. Bulk search turns
  `AND` / `OR` / `NOT` into `+` / `|` / `-` (written the other way, it found
  nothing), and a search that finds nothing says how to rephrase it.
- **View the report anywhere.** Right-click `reports/*.html` → *View the Report
  in Priorwork*, also on a server over SSH where Live Preview cannot open it.
  When the agent exports a report, a notification offers to show it.
- **Zotero collections.** Link a Zotero collection to a survey (*Link a Zotero
  Collection…*, or `priorwork zotero SURVEY --collection NAME`). "In Zotero"
  then means in that collection; papers you put in it can be registered as
  candidates (`--import`); full texts come from its PDFs first. `--dois`
  prints the DOIs to paste into Zotero's magic wand. Priorwork still never
  writes to Zotero.
- The agent no longer opens Priorwork's own files in `.venv`.
- Renamed from Prior Work to Priorwork (the display name only; the commands,
  the package and the extension ID are unchanged).

## 0.1.2

- Creating a workspace no longer stops at "the priorwork command was not
  found": the extension mistook its own error for priorwork's version, so it
  skipped setting up the workspace's `.venv`. The message, when it does
  appear, now says what to do.

## 0.1.1

- A guide and a web page: <https://yoshida-kd.github.io/priorwork/>.
- Nothing but the extension is needed to start: when Python 3.10 or later is
  not found, it offers to install uv, which downloads Python for the
  workspace's `.venv`.
- The paper page shows the card of an included paper and lets you fill it in:
  the evidence level and each field, saved with **Ctrl+S**. Changes not yet
  saved are kept while you move between papers. The comparison matrix is
  regenerated on save.
- **Settings** page (the gear in the sidebar): the API keys, Zotero and WebDAV,
  importing the SSCI list, and a connection check, without opening `.env`.
  Keys are never shown. `priorwork settings` does the same from the command
  line (`--stdin` takes the values as JSON, `--import-ssci CSV`).
- The next step *Add papers to Zotero* no longer opens a terminal: it copies
  the DOIs of the included papers missing from Zotero (to paste into Zotero's
  *Add Item by Identifier*) and reloads the library. No step opens a terminal
  any more.
- When the workspace is not on GitHub yet, the sidebar offers to publish it as
  a private repository (through VS Code's *Publish to GitHub*).
  `priorwork status --json` has a new `git` key (`repo`, `remote`).
- **Ask Your Agent…** (on a survey, on the paper page and in the next steps)
  copies a request — fill in the cards, recommend decisions, chase citations,
  write the text, check and fix — to paste into your agent's chat. Nothing is
  sent anywhere by the extension.
- `priorwork card SURVEY N [--set KEY=VALUE ...]` shows or fills in a card
  (`--json` for the extension).
- Removed `priorwork migrate` and **Move a lit Workspace to Prior Work**, with
  everything that recognised workspaces of lit (Prior Work's unpublished former
  name). No published version ever wrote that layout.
- A workspace with no `.priorwork/config.json` is now taken to be in English
  (it was Japanese). `priorwork init` always writes the setting, so only a
  workspace that lost the file is affected.
- `priorwork status --json` no longer has the `legacy` key.

## 0.1.0

First release of **Prior Work**. (It was developed as `lit` and never
published under that name; a lit workspace is recognised and
`priorwork migrate` — or **Move a lit Workspace to Prior Work** in the
extension — moves it.)

**The `priorwork` command**

- Workspaces in Git: the working report (`reports/*.md`), the state of each
  survey (`.priorwork/surveys/*.json`), and `AGENTS.md` plus skills for the
  agent, kept in step with the engine by `priorwork sync`.
- Search Semantic Scholar (by relevance, or boolean *bulk* search) with DOIs,
  journals and ISSNs verified against OpenAlex; SSCI status from Clarivate's
  list, or guessed from a built-in list of major journals.
- Numbered candidates and decisions (include / maybe / exclude with a reason)
  with their history; citation chasing (snowballing) from the included papers.
- Full texts from Zotero (local, WebDAV or Zotero storage) or open-access PDFs.
- `priorwork check`: author–year citations with no registered paper, DOIs that
  point to other titles, unfilled cards, a report out of step with its state.
- `priorwork export`: the report for reading (HTML, Word or Markdown), marked
  *Draft* until it is complete.
- English and Japanese: messages follow the display language
  (`PRIORWORK_LANG`), and each workspace has its own language for the reports,
  `AGENTS.md` and the skills.
- `--json` output for scripts and the extension.

**The VS Code extension**

- The Prior Work sidebar: surveys, next steps, and papers by decision, with
  include / maybe / exclude on each paper (several at once, too).
- A page per paper for screening, with the scope's criteria at the top, keys
  (I, M, X, U, N, J/K, O) and a move to the next unscreened paper.
- Create a workspace (with its `.venv` and the `priorwork` command), new
  survey, scope, search, snowball, add by DOI, full text, check (in the
  Problems panel), export and view, diagnose, sync, upgrade, and move a lit
  workspace.
- The sidebar follows changes made by the agent in the terminal.
- English and Japanese, following VS Code's display language.
