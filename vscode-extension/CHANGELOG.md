# Changelog

Prior Work's command-line tool (`priorwork` on PyPI) and this extension are
released together, under one version number.

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
