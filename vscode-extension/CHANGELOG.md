# Changelog

Priorwork's command-line tool (`priorwork` on PyPI) and this extension are
released together, under one version number.

## 0.1.9

- **Modes: where the agent stops for you.** *Standard* (the new default)
  stops twice: once the scope is set, and before the paper cards, showing the
  DOIs to collect in Zotero, so that more cards are read from the PDFs. *Full
  auto* carries on to the end (the old behaviour), and *manual* stops after
  every step. Choose it in your request, in `AGENTS.local.md`, or with
  `priorwork new/scope --mode standard|auto|manual`; it is recorded in the
  survey. `priorwork status` shows the stop before the cards until
  `priorwork scope SURVEY --go-on` records that you said to go on, and the
  sidebar's step copies the DOIs and the request to carry on. **New Survey →
  Ask your agent to do it** asks for the mode too.
- **The audit by another model is optional.** `priorwork check` no longer
  warns that a survey is not audited, the next steps no longer ask for it,
  and the agent no longer asks you for one in its reports. Ask for an audit
  when you want one (`priorwork audit` still records it).
- **Start from a manuscript in any format, for a draft or for advice.**
  `priorwork read PATH` turns a manuscript (Markdown, Quarto, LaTeX, HTML such
  as Quarto's output, Word, PDF, or a folder of them) into text for the agent.
  `priorwork new --manuscript PATH --purpose advice` makes a report of advice
  on a finished manuscript: how it cites the literature (the direction of each
  cited finding, overstatements), the literature it is missing, and the
  argument, with a summary first. `--purpose draft` (the default) drafts
  sections 1–3 as before. The agent proposes what to make, which parts to
  cover and how many reports, and agrees it with you; one manuscript can have
  both reports.
- The agent names papers as "Author (year)" in its reports, not by numbers
  such as `#232`.
- The report viewer lets you select and copy text, and search the page with
  Ctrl+F.
- `priorwork zotero SURVEY --dois` works without the Zotero link (it lists
  the DOIs of all included papers).
- **Octavo.** Surveys and [Octavo](https://github.com/yoshida-kd/octavo)
  projects are many-to-many, joined through Zotero collections:
  - A manuscript in an Octavo project (another repository) is used where it
    is, recorded relative to the workspace. `priorwork read` also reads the
    project's results, tables and analyses and lists the literature the
    manuscript cites; `priorwork add SURVEY --cited` registers it from the
    `.bib`. **New Survey → Start from my manuscript** takes a paper in an
    Octavo project without copying it.
  - `priorwork scope SURVEY --octavo PATH` (repeatable; **Link to an Octavo
    Project…**) links other projects that use a survey, so a survey on a
    topic can serve several papers.
  - `priorwork export SURVEY --octavo [PROJECT]` (**Export for an Octavo
    Project…**) writes the draft of the manuscript, or the sections on the
    literature, with `[@key]` citations from that project's `.bib`
    (`reports/<name>.<project>.octavo.md`). Papers not in the `.bib` yet
    become `[@PRIORWORK:…]`, with their DOIs listed.
  - The survey is linked to the Zotero collection the Octavo project pulls its
    `.bib` from (`zotero_collection` in its settings: a name or a list). Each
    survey can use a collection under it, and `priorwork check` says, project
    by project, when the survey's collection is not among them or when its
    text cites papers missing from the `.bib`. `priorwork status` lists the
    other surveys for the same projects. (Lists of collections, and choosing
    them in Octavo's sidebar, come with the next Octavo release.)
- **Zotero collections as Zotero shows them.** Choosing the collection goes
  folder by folder: only the top folders are listed, and choosing one opens
  it ("Use this folder", "Up", and a search over all folders). A collection
  can be given by its path (`"parent / child"`, needed when a name is used
  twice), and papers in a collection under the linked one count as in it.
  The row is always under each survey (it opens the settings when Zotero is
  not set up), the list can be reloaded after you make a collection in
  Zotero, and it explains how to make one.

## 0.1.8

- **The agent works on a branch and opens a pull request.** It commits on a
  branch named after the survey at each step, pushes it, and opens a pull
  request once the report is exported; you merge it. It never merges, pushes
  to main or rewrites history, and `priorwork sync` also denies those in
  `.claude/settings.json` for Claude Code (along with allowing the Git
  commands it needs).
- Surveys on other branches, still waiting to be merged, are listed by
  `priorwork status` and in the sidebar, which also shows the branch you are
  on. A survey that is only on another branch tells you to `git switch` to it.
- `priorwork fulltext` records whether an open-access PDF is the published
  version or the author's manuscript, and says to give PDF pages for a
  manuscript.
- **`priorwork fix`** corrects a registered paper: `--id` replaces a
  working-paper DOI with the published version (the number, status and card
  stay), `--authors` / `--year` / `--title` fix details the databases got
  wrong, and `--confirm "<reason>"` clears a warning you have checked,
  keeping the reason. `priorwork add` of the published version now replaces
  an unverified working-paper DOI by itself.
- Titles that differ only by a subtitle Semantic Scholar repeated are no
  longer "a DOI pointing to another title"; all-capital author names are
  tidied ("TODD L. ALLEE" → "Todd L. Allee"); the year follows the published
  version of the DOI.
- `priorwork check` warns when the full text has far fewer pages than the
  paper (the publisher's preview), no longer takes "約30,715" for 715, and
  accepts journal pages when the database gives a wrong page range.
- `priorwork list --abstract` no longer fails.
- **Fewer off-topic candidates.** Searches into a new survey leave out papers
  whose Semantic Scholar fields lie outside the social sciences (medicine or
  computer science only, say; papers with no field are kept). Change it with
  `priorwork scope SURVEY --search-field all`, or per search with `--field`.
- **More full texts.** `priorwork fulltext` tries every location OpenAlex
  knows, open ones first, and follows the PDF link on a landing page (an
  institutional repository's, say).
- **More abstracts.** Papers with no abstract in Semantic Scholar or OpenAlex
  get the one the publisher registered with Crossref.

## 0.1.7

- `priorwork check` no longer takes the later pages of a page list on a card
  (`(p. 177, 184-190)`) for numbers missing from the full text.

## 0.1.6

- **An audit by another model.** A survey now counts as done only once a
  model other than the one that wrote it has audited it: the writer records
  itself (`priorwork new … --by "<model>"`), and the auditor records its
  audit (`priorwork audit SURVEY --by "<model>"`, refused for the model that
  wrote it). The new skill `priorwork-audit` checks every card against the
  full text, the direction of each citation, hypotheses passed off as the
  literature, and mechanical exclusions. *Ask your agent… → Audit as another
  model* copies the request, and the next steps offer it once the cards are
  filled in.
- **`priorwork check` looks harder at the cards and the text.** It warns
  about numbers on a card that are not in the full text, pages that are not
  in the paper, "full text checked" cards with no page or no full text
  fetched, cards not written in the report's language, synthesis sections
  that cite no paper, and a number of included papers written by hand that
  disagrees with the survey. Included papers not in Zotero are now a WARN.
- **A new report layout** for new surveys: the synthesis comes first
  (background, theories, methods, debates, gaps), then a separate section for
  the hypotheses of this study, then the matrix, the paper cards and the
  references. Each section says what to write. Existing reports keep their
  layout and still work.
- **Mermaid diagrams** (```` ```mermaid ````) are drawn in the exported HTML
  and in the report viewer, instead of showing as code.
- **The SSCI check no longer trusts a title alone.** When a journal's ISSN
  is known and differs from the listed one, a journal with the same title is
  "not in SSCI" (e.g. the two journals called *Public Policy and
  Administration*). Existing surveys are re-checked when rendered.
- **Redone surveys get a version right after the date**:
  `priorwork new … --slug make_or_buy` for an existing `make_or_buy` makes
  `20261012_v2_make_or_buy`, and the sidebar shows "v2". Surveys named the
  old way (`…_make_or_buy_v2`) count as versions too.
- The agent instructions now say that every included paper goes into Zotero
  (also those whose full text the agent found itself), that the list to add
  is the output of `priorwork zotero --dois` as it is, that cards are written
  in the report's language with pages, and that screening never excludes
  many papers with one recycled reason.

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
