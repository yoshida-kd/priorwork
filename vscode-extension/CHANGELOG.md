# Changelog

Prior Work's command-line tool (`priorwork` on PyPI) and this extension are
released together, under one version number.

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
