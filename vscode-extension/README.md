# Prior Work

**Literature reviews for the social sciences, built with an AI agent — no terminal needed.**

[日本語](README.ja.md)

Prior Work keeps a topic-based literature review in a Git workspace. An AI agent (Claude Code or
any agent that reads `AGENTS.md`) searches Semantic Scholar and OpenAlex, fills in a card for each
paper and writes the review; you make the decisions and check its work. This extension gives you
everything else without a terminal: what you do yourself happens in the sidebar, and what you ask
of the agent goes through its chat. The extension never calls an AI service itself.

- **Surveys in the sidebar.** Each survey with what is left to screen, its next steps, and its
  papers grouped as *to screen*, *maybe*, *included* and *excluded*.
- **A page per paper.** Title, authors, journal and its SSCI status, citations, warnings (a DOI
  that points to another paper, a working-paper version, a possible book review) and the abstract,
  with the survey's inclusion and exclusion criteria at the top. Decide with a click or a key —
  **I** include, **M** maybe, **X** exclude (with a reason) — and it moves on to the next one.
  For included papers, the page also holds the **paper card** (research question, X, Y, data,
  identification, findings, limitations and how it was checked): check and correct what your
  agent wrote, and save with **Ctrl+S**.
- **Search and snowball.** Search in English (by relevance, boolean *bulk* search, or SSCI journals
  only), then chase the references and citations of the included papers to find what keyword
  search missed.
- **Checks you can trust.** *Check the Survey* lists author–year citations in the text that match
  no registered paper, DOIs that point to other titles and unfilled cards in the Problems panel.
  *Export and View* shows the report as it will be read, marked *Draft* until it is done.
- **Ask your agent.** *Ask Your Agent…* copies a ready-made request — fill in the cards, recommend
  decisions, chase citations, write the text, check and fix — to paste into the agent's chat. When
  the agent records a decision or edits the report, the sidebar and the paper page update.
- **Settings without files.** API keys, Zotero and the SSCI list on one page, with a connection
  check; keys are never shown. A row in the sidebar publishes the workspace to a private GitHub
  repository.

## Getting started

1. Install the extension. Nothing else is needed to start: it uses Python 3.10 or later if you
   have it, and otherwise installs [uv](https://docs.astral.sh/uv/), which downloads Python (into
   your home folder, without administrator rights). For the writing you will want an AI agent that
   works in VS Code (Claude Code, for example), and **git** to keep the workspace on GitHub.
2. Run **Prior Work: Create a Workspace…** (or use the button in the Prior Work sidebar). Pick an
   empty folder and the language of the reports (English or Japanese). The extension creates a
   `.venv` there and installs the `priorwork` command from PyPI.
3. Open the **Settings** (the gear in the sidebar) and add a free [Semantic Scholar API key](https://www.semanticscholar.org/product/api#api-key-form)
   (searches without one are often rate-limited). Zotero and the SSCI list are optional and set
   there too; **Save and Check the Connections** tells you whether they work.
4. **New Survey…**: the topic, an English slug, the depth (*quick* or *full*) and, if you like,
   the research question.
5. **Search…**, then **Screen Candidates**.
6. **Ask Your Agent…** to fill in the cards and write the text, and check its cards on each
   paper's page. The workspace carries `AGENTS.md` and skills (`/survey-new`, `/survey-screen`,
   `/survey-snowball`, `/survey-extract`, `/survey-check`) for the agent.
7. **Check the Survey**, then **Export and View the Report**.

Keep the workspace in a **private** GitHub repository (the row *Not on GitHub yet* in the sidebar
sets it up): the reports and state files contain abstracts. `.env`, which holds your keys, is kept
out of Git.

## Commands

| Command | What it does |
| :--- | :--- |
| Create a Workspace… | Set up a workspace (and its `.venv`) in a folder |
| New Survey… / Edit the Scope… | Create a survey; change its research question, period, criteria, depth |
| Search… / Chase Citations / Add Papers by DOI… | Find candidates |
| Screen Candidates | Open the paper page at the first unscreened paper |
| Include / Maybe / Exclude… / Back to Candidate | Also from the sidebar, for several papers at once |
| Get the Full Text | From Zotero or an open-access PDF (for included papers) |
| Check the Survey | Findings in the Problems panel |
| Ask Your Agent… | Copy a request (fill in the cards, write the text, …) to paste into your agent's chat |
| Export and View the Report | The version for reading (HTML) |
| Settings (API Keys, Zotero, SSCI List)… | Set the keys and Zotero, import the SSCI list, check the connections |
| Diagnose the Setup | API keys, the SSCI list, Git, connections |
| Publish the Workspace to GitHub (Private)… | VS Code's *Publish to GitHub*, with a reminder to keep it private |
| Update AGENTS.md and Skills / Update the Engine | Keep the workspace in step with the engine |

## Settings

| Setting | Default | |
| :--- | :--- | :--- |
| `priorwork.command` | *(empty)* | The `priorwork` command. Empty: the workspace's `.venv`, then `priorwork` on `PATH` |
| `priorwork.python` | *(empty)* | The Python used to create `.venv`. Empty: `python3` (`py -3` on Windows) |
| `priorwork.autoAdvance` | `true` | Move on to the next unscreened paper after a decision |

## What leaves your machine

Search queries and DOIs go to Semantic Scholar and OpenAlex; with Zotero set up, the extension
reads your Zotero library (read only). Nothing else is sent anywhere.

## More

Everything — the steps of a survey, the paper cards, the settings, the agent, the command-line
tool — is in the [guide](https://yoshida-kd.github.io/priorwork/guide/); a shorter overview is the
[project's README](https://github.com/yoshida-kd/priorwork#readme). The extension and the
`priorwork` command are released together, under one version number
([changelog](CHANGELOG.md)).
