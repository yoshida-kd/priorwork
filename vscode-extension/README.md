# Priorwork

**Hand your literature review to an AI agent, then check it — no terminal needed.**

[日本語](README.ja.md)

Priorwork keeps a topic-based literature review in a Git workspace. Tell your AI agent (Claude
Code, Antigravity or any agent that reads `AGENTS.md`) the topic, in plain words: it sets the scope,
searches Semantic Scholar and OpenAlex, screens with a reason for every decision, chases citations,
fills in a card for each paper, writes the review, checks and exports it — without stopping. This
extension is where you check and correct its work, without a terminal. The extension never calls an
AI service itself.

- **Ask your agent.** *New Survey → Ask your agent to do it* copies a request for a whole survey;
  *Ask Your Agent…* on a survey copies one to carry on, search more, screen, chase citations, fill in
  the cards, write or check. A button opens the chat of Claude Code, Antigravity or Copilot when it is
  installed. You can also just ask in the chat — no skill names needed.
- **Surveys in the sidebar.** Each survey with what is left to screen, its next steps, and its
  papers grouped as *to screen*, *maybe*, *included* and *excluded*.
- **A page per paper.** Title, authors, journal and its SSCI status, citations, warnings (a DOI
  that points to another paper, a working-paper version, a possible book review) and the abstract,
  with the survey's inclusion and exclusion criteria at the top and the reason the agent gave. Overturn
  a decision with a click or a key — **I** include, **M** maybe, **X** exclude (with a reason).
  For included papers, the page also holds the **paper card** (research question, X, Y, data,
  identification, findings, limitations and how it was checked): check and correct what your
  agent wrote, and save with **Ctrl+S**.
- **Search and snowball.** Search in English (by relevance, boolean *bulk* search, or SSCI journals
  only), then chase the references and citations of the included papers to find what keyword
  search missed.
- **Checks you can trust.** *Check the Survey* lists author–year citations in the text that match
  no registered paper, DOIs that point to other titles and unfilled cards in the Problems panel.
- **Reports inside VS Code.** *Export and View the Report*, or right-click `reports/*.html` → *View
  the Report in Priorwork*, shows the report as it will be read (marked *Draft* until it is done) —
  on a server over SSH too. When the agent exports it, a notification offers to show it.
- **Zotero, read only.** Link a Zotero collection to a survey: included papers missing from it are
  one *Copy the DOIs* away from Zotero's magic wand, papers you put in it can be registered as
  candidates, and full texts come from its PDFs first.
- **Settings without files.** API keys, Zotero and the SSCI list on one page, with a connection
  check; keys are never shown. A row in the sidebar publishes the workspace to a private GitHub
  repository.

## Getting started

1. Install the extension. Nothing else is needed to start: it uses Python 3.10 or later if you
   have it, and otherwise installs [uv](https://docs.astral.sh/uv/), which downloads Python (into
   your home folder, without administrator rights). You will also want an AI agent that works in
   VS Code (Claude Code, Antigravity, …), and **git** to keep the workspace on GitHub.
2. Run **Priorwork: Create a Workspace…** (or use the button in the Priorwork sidebar). Pick an
   empty folder and the language of the reports (English or Japanese). The extension creates a
   `.venv` there and installs the `priorwork` command from PyPI.
3. Open the **Settings** (the gear in the sidebar) and add a free [Semantic Scholar API key](https://www.semanticscholar.org/product/api#api-key-form)
   (searches without one are often rate-limited). Zotero and the SSCI list are optional and set
   there too; **Save and Check the Connections** tells you whether they work.
4. **New Survey…** → **Ask your agent to do it**: give the topic and the depth, and paste the
   copied request into your agent's chat (or just ask in the chat).
5. Read the report when the agent has exported it, then check the decisions and cards on each
   paper's page and correct what you disagree with. The agent follows your changes.
6. Ask for more with **Ask Your Agent…** on the survey. To search and screen yourself instead,
   choose **Set it up myself** in step 4 and use **Search…** and **Screen Candidates**.

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
| Ask Your Agent… | Copy a request (carry on, search more, fill in the cards, …) to paste into your agent's chat |
| Export and View the Report / View the Report in Priorwork | The version for reading (HTML), inside VS Code |
| Link a Zotero Collection… | Tie a Zotero collection to the survey (Priorwork never writes to Zotero) |
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
