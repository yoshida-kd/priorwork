# Priorwork guide

> This is the source of the guide. Read it at **<https://yoshida-kd.github.io/priorwork/guide/>**. <!-- pages:skip -->

**Literature reviews for the social sciences, handed to your AI agent — no terminal needed**

Priorwork is a toolkit for having an AI agent (Claude Code, Antigravity, …) write topic-based reviews of
the prior work in economics, sociology, political science, public administration, management, psychology
and neighbouring fields. Give it the topic: the agent sets the scope, finds and selects the literature,
fills in a card for each paper, writes the review, checks it and exports a version for reading. You read
the result, then check and correct it in the VS Code sidebar.

This guide covers everything. For a short introduction, see the
[README](https://github.com/yoshida-kd/priorwork/blob/main/README.md).
[日本語の手引き](https://yoshida-kd.github.io/priorwork/ja/guide/)

---

## 1. Introduction

### 1.1 What it does

- **Hand it over.** Ask "review the literature on X" and the agent carries on from the scope to the
  export without stopping. There are no commands or skill names to learn.
- **Find the literature.** English keyword search in Semantic Scholar (by relevance, or a boolean bulk
  search), with DOIs, journals and ISSNs checked against OpenAlex. The references and citing papers of
  the included papers are followed to catch what keyword search misses.
- **Make paper cards.** For each included paper, a card with the research question, the explanatory
  variable, the outcome, the data, the identification strategy, the findings and the limitations. A
  comparison matrix is built from the cards.
- **Catch fabrications.** Every "Author (year)" in the text must match a registered paper, and every
  DOI the right paper; this is checked mechanically.
- **Export for reading.** HTML (or Word or Markdown) without the markers and empty fields, viewable
  inside VS Code — on a server over SSH too.
- **Check and correct.** Every decision and its reason, every card and every search is recorded. On
  each paper's page in the sidebar you can overturn decisions and correct cards.

### 1.2 Hand it over, then check

The agent decides the scope and each paper on its own, but always leaves the reason, and writes the
scope into the report. Cards hold only what the abstract or the full text says, with the evidence it
was checked against. You read them and correct whatever you disagree with; the agent follows your
corrections in the next round.

If you would rather decide each paper yourself, tell the agent to go through it together with you
([4.6](#46-ask-for-more-or-go-through-it-together)). You can also search and screen from the sidebar
yourself ([5](#5-doing-it-yourself)).

The extension never calls an AI service itself. AI help comes only through the agent you already use.

### 1.3 What you need

| What | Needed | |
| :--- | :--- | :--- |
| VS Code and the Priorwork extension | yes | Linux, macOS; on Windows, inside WSL ([2.2](#22-windows-and-servers-over-ssh)) |
| An AI agent | yes | Claude Code, Antigravity or another agent that runs in VS Code and reads `AGENTS.md` |
| Python 3.10 or later | automatic | if missing, the extension installs uv, which downloads Python |
| git and a GitHub account | recommended | to keep the workspace in a private GitHub repository |
| A Semantic Scholar API key | recommended | free; without one, searches often hit the rate limit |
| Zotero | optional | to collect the included papers in Zotero and read full texts from its PDFs |
| The SSCI journal list | optional | the CSV from Clarivate's Master Journal List; otherwise guessed from major journals |

---

## 2. Install

### 2.1 With VS Code

1. Install [VS Code](https://code.visualstudio.com/).
2. Find **Priorwork** in the Extensions view and install it
   ([Marketplace](https://marketplace.visualstudio.com/items?itemName=yoshida-kd.priorwork)).
3. The Priorwork icon appears in the activity bar. Go on to
   [Create a workspace](#3-create-a-workspace).

The extension sets Python up when you create a workspace. It uses Python 3.10 or later if it finds
one; otherwise it asks whether to install uv. uv (a small tool from Astral) goes into your home
folder, without administrator rights, and downloads Python for the workspace.

### 2.2 Windows and servers over SSH

- **Windows**: install WSL (Ubuntu), open a folder inside WSL with VS Code's **WSL** extension, and
  follow the steps above. Using Priorwork on Windows directly has not been tested.
- **A server**: connect with VS Code's **Remote - SSH** extension and follow the steps above on the
  server. The extension, Python and the workspace live on the server. Exported reports can be viewed
  inside Priorwork ([4.4](#44-view-the-report)).

### 2.3 On the command line

Without the extension, install the `priorwork` command from PyPI.

```bash
mkdir my-surveys && cd my-surveys
python3 -m venv .venv
.venv/bin/pip install priorwork
.venv/bin/priorwork init --lang en
./priorwork settings          # the settings (key values are never shown)
./priorwork doctor --online   # diagnose the settings and the connections
```

---

## 3. Create a workspace

A **workspace** is the folder that holds the reports of your surveys and their state. One workspace
holds any number of surveys. It is kept in a private GitHub repository.

### 3.1 Create it

1. Open an empty folder (or nothing at all) and press **Create a Workspace** in the sidebar.
2. Choose where, and the language of the reports (English or Japanese). The language cannot be
   changed later: it is the language of the report headings and of the instructions for the agent
   (`AGENTS.md` and the skills).
3. The extension creates a `.venv`, installs `priorwork` from PyPI and sets the workspace up
   (including `git init`).

### 3.2 Set it up

Open the gear in the sidebar (**Settings**).

1. Enter a **Semantic Scholar** API key. [Request one for free](https://www.semanticscholar.org/product/api#api-key-form).
2. If you use Zotero, fill in the **Zotero** fields ([8.2](#82-zotero)).
3. If you have the SSCI journal list, import it with **Import the SSCI List (CSV)…**
   ([8.3](#83-the-ssci-journal-list)).
4. **Save and Check the Connections** shows the diagnosis at the bottom of the page.

The settings are saved in the workspace's `.env`, which is kept out of Git. The page never shows the
values of the keys.

### 3.3 Put it on GitHub

The reports and state files contain abstracts, so keep the workspace in a **private** repository.

1. Press **Not on GitHub yet — publish it as a private repository** in the sidebar.
2. When VS Code asks, choose **Publish to GitHub private repository** and include all the files it
   suggests (`.env` is left out by `.gitignore`).

The agent commits the changes at each natural break, and pushes only when you agree.

### 3.4 Continue on another machine

1. Clone the repository in VS Code and open it.
2. Run **Set Up the Python Environment (.venv)** from the sidebar's menu (…).
3. Enter your keys in the **Settings** again (`.env` is not in Git), and import the SSCI list again.

---

## 4. Hand it to the agent

### 4.1 Ask

With the workspace folder open, ask in your agent's chat, in either of two ways:

- **Ask in your own words in the chat.** For example: "Do a full review of how government
  organisations staff up when demand for their services changes, from a make-or-buy angle." There is no
  need to type commands or skill names (typing `/priorwork` works too).
- **Ask from the sidebar.** **New Survey** → **Ask your agent to do it**, give the topic in your own
  words and choose the depth; a request is copied. Open the chat with **Open Claude Code** (or similar)
  in the notification and paste it.

If you already have a research question, a period or criteria, add them to the request. Otherwise the
agent decides them from the topic and says what it decided in its final report.

### 4.2 What the agent does

The agent follows the workspace's `AGENTS.md` and skills, in this order, without stopping:

```
① scope → ② search → ③ screen → ④ chase citations → ⑤ fill in the cards → ⑥ write → ⑦ check and export
```

1. **Scope**: decides the research question, period, fields, inclusion and exclusion criteria and
   depth, and creates the survey.
2. **Search**: splits the topic into subtopics and searches with English queries, rephrasing those that
   find nothing.
3. **Screen**: sorts the candidates into included, maybe and excluded against the criteria, with a
   reason for each.
4. **Chase citations**: picks up papers missed by keyword search from the references and citing papers
   of the included ones, and screens them.
5. **Cards**: fills in the cards of the included papers from the full text (a PDF in Zotero or an
   open-access version) or the abstract.
6. **Text**: writes the background, theoretical traditions, empirical methods, consensus and debates,
   and conclusions from the cards.
7. **Check and export**: checks citations, DOIs and empty fields, fixes them, and exports the version
   for reading (HTML).

At the end it reports the numbers searched and included, the parts of the scope it decided itself, what
is left to look at, and how to view the report. Since this takes a while, it may tell you where it is in
one line along the way (without waiting for an answer).

### 4.3 Depth

The **depth** is a guide to the size of the survey. If the request says "quick", "an overview", "full"
or "thorough", the agent follows it; otherwise it decides from how broad the topic is.

| | quick | full |
| :--- | :--- | :--- |
| Suits | a narrow topic, or just an overview | a broad topic with subtopics, or when coverage matters |
| Searches | 2–3 queries (10 results each) | 2–4 queries per subtopic (25 results each), aiming at 100+ candidates |
| Citation chasing | optional | yes |
| Cards | abstracts are fine | core papers checked in the full text |
| Text | an overview and the comparison table | background, theories, debates and gaps |

When a full survey has too few searches, **Search more** appears in the **Next steps** in the sidebar.
The agent sees it too and adds searches.

### 4.4 View the report

Open the version for reading (HTML) inside VS Code. It works the same on a server reached over SSH.

- Right-click the survey in the sidebar → **Export and View the Report**.
- Right-click `reports/<name>.html` in the Explorer → **View the Report in Priorwork**.
- When the agent exports it, click **View** in the notification.

While cards are unchecked or empty, or the check reports ERRORs, it is marked *Draft* at the top. On a
local machine you can also open it in the browser and print it to PDF.

### 4.5 Check and correct

Under each survey in the sidebar are its included, maybe, excluded and unscreened papers. Click a paper
to open its page.

- **Decisions**: read the abstract and the reason the agent left. To overturn it, press **I** include,
  **M** maybe or **X** exclude (with a reason). Select several papers in the sidebar and right-click to
  change them at once.
- **Cards**: on an included paper's page, compare the card with the abstract, correct it and press
  **Ctrl+S** to save.
- **Scope**: change the research question, the criteria or the depth with **Edit the Scope** (right-click
  the survey).

The agent never overturns your decisions or corrections. After correcting, ask it to "carry on" and it
works from there.

### 4.6 Ask for more, or go through it together

- **More**: ask in the chat — "carry on", "search more", "fill in the cards". **Ask Your Agent…**
  (right-click the survey) also copies requests for the common jobs: carry on to the end, search more,
  screen, chase citations, fill in the cards, write the text, check and fix.
- **Together**: ask it to "go through it with me" or "show me the candidates one by one", and the agent
  only recommends the scope and decisions and waits for your answers. To make this the rule, write
  "Ask the user before deciding the scope and each paper" in the workspace's `AGENTS.local.md`.

When you come back to a conversation, "let's continue" is enough: the agent checks the state and takes
the next step.

### 4.7 Collect the papers in Zotero

Priorwork never writes to Zotero; you add the papers. Two things make it easier (for setting up Zotero,
see [8.2](#82-zotero)).

**Add the included papers' DOIs to Zotero at once.**

1. In Zotero, select the collection (folder) the papers should go into.
2. Click **Add … to Zotero** in the next steps of the sidebar and **Copy the DOIs** (or ask the agent
   for "the list of DOIs to add to Zotero").
3. Paste them into Zotero's **Add Item by Identifier** (the magic wand) and press Enter. They go into the
   selected collection.
4. Click **Reload from Zotero** to update the status.

**Link a Zotero collection to the survey.** Right-click the survey → **Link a Zotero Collection…** and
choose a collection you made in Zotero (or tell the agent "use my Zotero collection X"). Once linked:

- "In Zotero" means in that collection.
- Papers you put into the collection yourself can be registered as candidates (**Register … papers from
  the Zotero collection** in the next steps). The agent includes them unless they are clearly out of
  scope.
- Full texts come from the PDFs in that collection first.

---

## 5. Doing it yourself

You can also work from the sidebar yourself instead of handing it to the agent. **Next steps**, under
each survey in the sidebar, says what to do now; click an item to start it.

### 5.1 Set the scope

**New Survey** → **Set it up myself** asks for the topic, an English slug (the file name, e.g.
`minimum_wage_employment`), the depth and the research question. Add the period, the fields and the
inclusion and exclusion criteria later with **Edit the Scope** (right-click the survey). The criteria
are shown at the top of each paper's page.

### 5.2 Search

**Search** asks for an English query and how to search:

- **Search**: Semantic Scholar's relevance search (20 results).
- **Bulk search**: `+` (and), `|` (or), `-` (not) and `"phrases"`, most cited first (25 results). It
  finds the classics that keyword search buries. `AND`, `OR` and `NOT` are turned into `+`, `|` and `-`.
- **SSCI journals only**: the relevance search, keeping SSCI journals only.

The results are registered as candidates. When both a working paper and its published version are
found, only the published one is kept; books, working papers, preprints and papers with no known
venue are left out by default. A paper whose DOI you already know is added with **Add Papers by DOI**.

### 5.3 Screen

**Screen Candidates** opens the page of the first unscreened paper.

- At the top, the survey's inclusion and exclusion criteria; below, the title, the authors, the
  journal and its SSCI status, citations, warnings and the abstract.
- **I** include, **M** maybe, **X** exclude (type the reason first), **U** back to candidate. After a
  decision it moves on to the next unscreened paper (setting `priorwork.autoAdvance`).
- **N** next unscreened, **J / K** next / previous, **O** open the DOI in the browser.
- Reasons you used before are offered as buttons.

Check papers with a warning (⚠️) before including them.

| Warning | Meaning |
| :--- | :--- |
| The DOI points to another title | Semantic Scholar's DOI belongs to another paper (a reply, say) |
| The DOI is a working paper / preprint version | a journal is named, but the DOI is an SSRN-style version |
| OpenAlex does not know the DOI / No DOI / DOI not verified | a wrong or missing DOI, or it could not be checked |
| May be a book review or comment | a title like "…, by Author", or a single page |

### 5.4 Chase citations

**Chase Citations** collects the references and citing papers of the included papers from OpenAlex
and registers them as candidates, ordered by how many included papers each is linked to. With three
or more included papers, only those linked to at least two are taken by default. Screen them as in 5.3.

### 5.5 Fill in the paper cards

Each included paper gets a card in section 3 of the report. Write it on the paper's page and press
**Ctrl+S** to save. **Get the Full Text** brings in the full text ([6.3](#63-full-texts)). To hand only
the cards to the agent, use **Ask Your Agent… → Fill in the paper cards**. Section
[6](#6-paper-cards) describes the cards.

### 5.6 Write the text

Section 1 (the background) and sections 4 to 7 (theoretical traditions, empirical methods, consensus
and debates, conclusions) are text written from the cards. Open the report with **Open the Working
Report (Markdown)** on the survey and write it, or ask the agent with **Ask Your Agent… → Write the
text of the report**.

### 5.7 Check and export

1. **Check the Survey** lists the problems in VS Code's **Problems** panel ([7](#7-checks)).
2. **Export and View the Report** opens the version for reading (HTML) ([4.4](#44-view-the-report)).

---

## 6. Paper cards

### 6.1 The fields

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

- The heading and the source line are generated. You (or the agent) write from the evidence level to
  the notes.
- The **first line** of each field goes into the comparison matrix (section 2), so keep it short;
  details go on the lines below it, which become bullet points.
- Write only what the abstract or the full text says. If it says nothing, write "not reported".

### 6.2 The evidence level

| Evidence | Meaning |
| :--- | :--- |
| unchecked | not checked yet (before filling in, or partly guessed) |
| abstract only | checked against the abstract |
| full text checked | checked against the full text |

Unchecked cards are flagged by the checks, and the export is marked *Draft*. In a full survey, check
the core papers in the full text.

### 6.3 Full texts

Get one with **Get the Full Text** on an included paper's page or from the paper's context menu in the
sidebar (the agent gets them the same way). PDFs are never stored in the workspace; only the extracted text is kept, in
`.priorwork/cache/fulltext/` (outside Git). Priorwork looks in this order:

1. a PDF attached in the local Zotero (matched by DOI)
2. a PDF attached in Zotero found through the Web API (WebDAV or Zotero's own file sync), preferring
   the collection linked to the survey
3. the text Zotero indexed (no page breaks; a fallback)
4. an open-access PDF

Publishers usually refuse automated downloads, so for papers that are not open access, attach the PDF
in Zotero first.

### 6.4 When a paper is no longer included

Its card is kept, with what was written, in the state file, and comes back if the paper is included
again.

---

## 7. Checks

**Check the Survey** looks at:

| Check | Level |
| :--- | :--- |
| Author–year citations in the text and the cards ("Author (year)", "(Author, year; …)") match registered papers | ERROR (unregistered) / WARN (not included) |
| 2001a / 2001b match the references | WARN |
| DOIs in the text are registered | ERROR |
| ⚠️ on included papers; the DOI and title agree in OpenAlex | ERROR |
| The evidence level of each card, and empty fields | WARN |
| The report matches the state file | WARN |
| Unscreened candidates, non-SSCI included papers, included papers missing from Zotero, citations taken for organisations or table numbers | INFO |

Citations are found with regular expressions, so not every style is caught. `Acemoglu et al. (2001,
2005)`, `Dell (2010, p. 5)` and `(e.g., Dell 2010; Acemoglu et al., 2001a)` are. Organisations such as
"World Bank (2010)" or "OECD (2019)" are reported as INFO. Something that is not a citation can be
excluded with a comment in the report:

```markdown
<!-- priorwork:ignore-citation Smith (2015) -->
```

---

## 8. Settings

### 8.1 API keys

| Setting | Purpose |
| :--- | :--- |
| Semantic Scholar API key | recommended; without one, searches often fail on the rate limit (HTTP 429) |
| OpenAlex API key, email address | optional; OpenAlex works without a key, with a daily usage cap |

### 8.2 Zotero

With Zotero set up, Priorwork shows which included papers are in Zotero, links a collection to a
survey ([4.7](#47-collect-the-papers-in-zotero)) and gets full texts from the PDFs attached there. It never writes to Zotero or WebDAV.

1. Create an API key at <https://www.zotero.org/settings/keys> with **only "Allow library access"**
   (no notes, no write access). "Your user ID for use in API calls" on the same page is the user ID.
2. Enter the key and the user ID under **Zotero** in the settings. If Zotero runs on this machine,
   enter its data folder too (default `~/Zotero`).
3. If Zotero syncs its files through WebDAV (Nextcloud and the like), enter under **Zotero file sync
   through WebDAV** the URL of the folder that holds the PDF zips (the URL set in Zotero plus
   `zotero/`), the user name and the password. With Nextcloud, share the `zotero` folder read only
   with a dedicated user and use that user's app password.
4. Check with **Save and Check the Connections**.

If WebDAV reports "folder not found", check the URL. With Nextcloud under a sub-path, include that path
(e.g. `https://example.com/nextcloud/remote.php/dav/files/<user>/zotero/`).

### 8.3 The SSCI journal list

Only Clarivate's [Master Journal List](https://mjl.clarivate.com/) settles whether a journal is in the
SSCI. Download the SSCI list there as CSV (a free account is needed) and import it with **Import the
SSCI List (CSV)…** in the settings. The list is copied to the workspace's `.priorwork/data/` and stays
out of Git under its licence. Without it, the status is guessed from a built-in list of about 100
major journals.

| Shown | Meaning |
| :--- | :--- |
| ✅ SSCI (checked against the list) | the ISSN or the name matches the list |
| 🟡 Probably SSCI (guessed from the journal name; verify) | no list; matches the built-in list |
| 🔍 Journal (SSCI not verified) / ⚪ Not in SSCI | unknown status / not in the list |
| 📕 Book / ❌ Working paper / preprint / ❓ Unknown venue | left out of search results by default |

### 8.4 VS Code settings

| Setting | Default | |
| :--- | :--- | :--- |
| `priorwork.command` | *(empty)* | The `priorwork` command. Empty: the workspace's `.venv`, then `priorwork` on `PATH` |
| `priorwork.python` | *(empty)* | The Python used to create `.venv`. Empty: look for 3.10 or later, else use uv |
| `priorwork.autoAdvance` | `true` | Move on to the next unscreened paper after a decision |

---

## 9. Instructions for the agent

### 9.1 AGENTS.md and the skills

The workspace carries instructions for agents (`AGENTS.md`) and a skill for each step (`.agent/skills/`,
also seen through `.claude/skills/`). The entry point is the `priorwork` skill: it looks at the state and
goes on to the skill of the next step (`priorwork-new`, `priorwork-screen`, `priorwork-snowball`,
`priorwork-extract`, `priorwork-check`). The agent picks them from the words of your request, so there
are no names to remember.

Instructions for one workspace only (fields to prefer, writing style, journals to leave out, "ask me
before deciding each paper", …) go in `AGENTS.local.md`. `AGENTS.md` and the skills are rewritten to
match the engine's version; do not edit them.

### 9.2 What the agent keeps to

- It leaves a reason for every decision and for the scope, and never overturns your decisions.
- Every paper mentioned in the text is registered; it never writes authors, years or DOIs from memory.
- Cards hold only what the abstract or the full text says, with the evidence level updated.
- It replaces papers with ⚠️ by their published versions, or sets them to maybe and tells you. It never
  calls a 🟡 (guessed) journal "in the SSCI".
- It runs the checks before calling anything finished.
- It never opens the files of Priorwork itself (inside `.venv`).
- It never writes to Zotero, and pushes only when you agree.

---

## 10. Inside a workspace

```text
my-surveys/
├── reports/                 # the reports (the working .md, and the exported .html etc.)
├── AGENTS.md, CLAUDE.md     # instructions for agents (updated automatically; do not edit)
├── AGENTS.local.md          # instructions for this workspace only (edit freely)
├── .agent/skills/           # the skills for each step (also seen through .claude/skills)
├── priorwork                # ./priorwork (what the agent runs)
├── requirements.txt         # the engine's version (priorwork==X.Y.Z)
├── .env                     # the settings (not in Git)
└── .priorwork/
    ├── config.json          # the workspace's language
    ├── surveys/             # the state of each survey (in Git)
    ├── cache/               # full texts, the Zotero index (not in Git)
    └── data/                # the SSCI list (not in Git)
```

| File | Contents | Editing |
| :--- | :--- | :--- |
| `reports/YYYYMMDD_<slug>.md` | the working report | the text and the card fields are written by hand (or by the agent); everything between `<!-- BEGIN priorwork:… -->` and `<!-- END priorwork:… -->` is regenerated |
| `.priorwork/surveys/YYYYMMDD_<slug>.json` | candidates, decisions and reasons (with their history), the search log, the scope, the depth, the Zotero collection | changed only by Priorwork |

The references (section 8) are generated from the included papers, with DOIs, and the appendix records
the searches, the counts, the reasons for exclusion and the decisions that were revised.

---

## 11. Updating the engine

A workspace pins the engine's version (the `priorwork` command) in `requirements.txt`, so nothing
changes behind your back. After the extension is updated, it offers **Update the Engine** when the
workspace's version is older; that also brings `AGENTS.md` and the skills up to date. When only
`AGENTS.md` and the skills are out of date, the sidebar shows a row to update them.

---

## 12. On the command line

Everything the extension does is also a `./priorwork` command (the agent uses them).

```bash
# Workspace
./priorwork init [DIR] [--lang en|ja]              # create a workspace
./priorwork settings [--stdin] [--import-ssci CSV] # API keys, Zotero, the SSCI list
./priorwork doctor [--online]                      # diagnose the settings and connections
./priorwork sync [--force|--diff]                  # AGENTS.md and the skills to the engine's version
./priorwork upgrade [--to X.Y.Z]                   # update the engine

# Surveys
./priorwork status [SURVEY]                        # the list / progress and next steps
./priorwork new "<topic>" --slug <slug> [--depth quick|full] [--question ...]
./priorwork scope SURVEY --question "..." [--years ... --fields ... --inclusion ... --exclusion ... --depth ...]
./priorwork list SURVEY [--status candidate maybe] [--abstract]
./priorwork include SURVEY 2 5 7 [--reason "..."]
./priorwork exclude SURVEY 3 --reason "theory only"
./priorwork maybe SURVEY 9 / ./priorwork reset SURVEY 9
./priorwork add SURVEY <DOI>... [--candidate]
./priorwork card SURVEY 3 [--set rq="..." evidence=abstract]
./priorwork render SURVEY
./priorwork check SURVEY [--offline]
./priorwork export SURVEY [--format html|docx|md] [--with-abstracts]
./priorwork fulltext SURVEY <number> [--pdf <path>]

# Zotero (read only)
./priorwork zotero [SURVEY] [--refresh]            # the link / which included papers are in Zotero
./priorwork zotero --collections                   # list the collections
./priorwork zotero SURVEY --collection "<name>"    # link a collection ("" unlinks it)
./priorwork zotero SURVEY --import                 # register the papers of the collection as candidates
./priorwork zotero SURVEY --dois                   # DOIs of included papers not in Zotero (for the magic wand)

# Finding literature
./priorwork search "<English query>" [--into SURVEY] [--bulk] [--sort citations|relevance|recent|cpy] [--year 2010-2024] [--ssci-only] [--limit N]
./priorwork snowball SURVEY [--direction both|references|citations] [--min-links N]
./priorwork get <DOI>
./priorwork citations <DOI> / ./priorwork references <DOI>
./priorwork journal "<journal or ISSN>"
```

`SURVEY` is the file name without the extension, or the slug. `--limit` defaults to 25 when registering
into a full survey, else 10. Most commands print JSON with `--json`.

---

## 13. Troubleshooting

**The agent asks you to type commands or skill names.** Check whether `./priorwork status` says the
skills are out of date; if so, update AGENTS.md and the skills from the row in the sidebar (or
`./priorwork sync`). If it still asks, name Priorwork in the request: "carry on with the survey in
Priorwork".

**The agent opens files inside `.venv` (such as `i18n.py`).** They are part of Priorwork itself and
have nothing to do with your survey. Close them, and do not edit them (updates overwrite them). The
current AGENTS.md tells the agent not to open them.

**Too few papers were found.** Check that the depth is full (right-click the survey → **Edit the
Scope**) and ask the agent to "search more". **Search more** in the next steps of the sidebar copies a
request too.

**The HTML report does not open in Live Preview or similar.** On a server reached over SSH, browser
extensions often cannot open files on the server. View it inside Priorwork as in
[4.4](#44-view-the-report).

**Searches stop with "rate limited (HTTP 429)".** Without a Semantic Scholar API key, requests share a
public pool. Enter a key in the settings. If it still happens, wait a while and try again; Priorwork
retries up to five times, waiting longer each time.

**A paper cannot be registered.** Papers in domestic journals (J-STAGE and the like) are often in
neither Semantic Scholar nor OpenAlex. Since the target is international peer-reviewed journals, they
are out of scope for now.

**The Python environment cannot be set up.** The output panel (**Show Output** in the sidebar's
menu) says why. If uv cannot be installed, install Python 3.10 or later (from
[python.org](https://www.python.org/), for example) and run **Set Up the Python Environment (.venv)**
again.

**The sidebar says the priorwork command was not found.** The workspace has no `.venv` yet. Run **Set
Up the Python Environment (.venv)**.

**Not sure what is wrong.** **Diagnose the Setup** checks the settings, Git and the connections at
once.

Bug reports and suggestions are welcome in [Issues](https://github.com/yoshida-kd/priorwork/issues).
