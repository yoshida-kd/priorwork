# Prior Work

**Literature reviews for the social sciences, built with an AI agent — and screened in VS Code.**

[日本語](README.ja.md)

Prior Work keeps a topic-based literature review in a Git workspace. An AI agent (Claude Code or
any agent that reads `AGENTS.md`) searches Semantic Scholar and OpenAlex, fills in a card for each
paper and writes the review; you make the decisions. This extension puts those decisions in the
sidebar: see every survey, screen the candidates, chase citations and check the report without
typing commands.

- **Surveys in the sidebar.** Each survey with what is left to screen, its next steps, and its
  papers grouped as *to screen*, *maybe*, *included* and *excluded*.
- **A page per paper.** Title, authors, journal and its SSCI status, citations, warnings (a DOI
  that points to another paper, a working-paper version, a possible book review) and the abstract,
  with the survey's inclusion and exclusion criteria at the top. Decide with a click or a key —
  **I** include, **M** maybe, **X** exclude (with a reason) — and it moves on to the next one.
- **Search and snowball.** Search in English (by relevance, boolean *bulk* search, or SSCI journals
  only), then chase the references and citations of the included papers to find what keyword
  search missed.
- **Checks you can trust.** *Check the Survey* lists author–year citations in the text that match
  no registered paper, DOIs that point to other titles and unfilled cards in the Problems panel.
  *Export and View* shows the report as it will be read, marked *Draft* until it is done.
- **Follows your agent.** When the agent records a decision or runs a search in the terminal, the
  sidebar updates.

## Getting started

1. Install the extension. You need **Python 3.10 or later** and **git**.
2. Run **Prior Work: Create a Workspace…** (or use the button in the Prior Work sidebar). Pick an
   empty folder and the language of the reports (English or Japanese). The extension creates a
   `.venv` there and installs the `priorwork` command from PyPI.
3. **Open .env** and add a free [Semantic Scholar API key](https://www.semanticscholar.org/product/api#api-key-form)
   (searches without one are often rate-limited). Zotero is optional.
4. **New Survey…**: the topic, an English slug, the depth (*quick* or *full*) and, if you like,
   the research question.
5. **Search…**, then **Screen Candidates**.
6. Ask your agent to take it from there: the workspace carries `AGENTS.md` and skills
   (`/survey-new`, `/survey-screen`, `/survey-snowball`, `/survey-extract`, `/survey-check`).

Keep the workspace in a **private** GitHub repository: the reports and state files contain
abstracts, and `.env` holds your keys (it is kept out of Git).

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
| Export and View the Report | The version for reading (HTML) |
| Diagnose the Setup | API keys, the SSCI list, Git, connections |
| Update AGENTS.md and Skills / Update the Engine | Keep the workspace in step with the engine |
| Move a lit Workspace to Prior Work | For workspaces made with lit, Prior Work's former name |

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

The command-line tool, the workspace layout and the rules the agent follows are described in the
[project's README](https://github.com/yoshida-kd/priorwork#readme). The extension and the
`priorwork` command are released together, under one version number
([changelog](CHANGELOG.md)).
