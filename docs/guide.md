# Prior Work guide

> This is the source of the guide. Read it at **<https://yoshida-kd.github.io/priorwork/guide/>**. <!-- pages:skip -->

**Literature reviews for the social sciences, built with an AI agent — no terminal needed**

Prior Work is a toolkit for writing topic-based literature reviews in economics, sociology, political
science, management, psychology and neighbouring fields together with an AI agent (Claude Code, for
example). With the VS Code extension, everything you do yourself — searching, screening, checking the
paper cards, settings, checks, exporting — happens in the sidebar, and everything you ask of the agent
— filling in the cards from the full texts, writing the review — happens in its chat.

This guide covers everything. The short introduction is the
[README](https://github.com/yoshida-kd/priorwork#readme).
[日本語の手引き](https://yoshida-kd.github.io/priorwork/ja/guide/)

---

## 1. Introduction

### 1.1 What it does

- **Finds literature.** English keyword searches on Semantic Scholar (by relevance, boolean *bulk*
  search, or SSCI journals only), with DOIs, journals and ISSNs verified against OpenAlex. It also
  chases the references and citations of the included papers to find what keyword search missed.
- **Screens.** A page per candidate, with the abstract and the criteria, and one key to include,
  keep as maybe, or exclude (with a reason). The agent can recommend decisions too.
- **Builds paper cards.** Each included paper gets a card: research question, explanatory
  variable, outcome, data, identification, findings and limitations. The agent fills it in from the
  abstract or the full text; you check and correct it. A comparison matrix is built from the cards.
- **Catches fabrication.** It checks mechanically that every author–year citation in the text
  matches a registered paper, and that no DOI points to another paper.
- **Exports a version to read.** HTML (also Word or Markdown) without the markers and empty fields.

### 1.2 You decide

Prior Work is built so that the AI is not left to its own devices. You set the scope (the research
question, the period, the inclusion and exclusion criteria) and decide on each paper; the agent only
recommends. Cards hold only what the abstract or the full text says, with a record of how it was
checked. The extension never calls an AI service itself: AI help comes only through the agent you
already use.

### 1.3 What you need

| | Needed? | |
| :--- | :--- | :--- |
| VS Code and the Prior Work extension | yes | Linux and macOS. On Windows, use it inside WSL ([2.2](#22-windows-and-servers-over-ssh)) |
| Python 3.10 or later | automatic | if it is missing, the extension installs uv, which downloads Python |
| An AI agent | recommended | one that works in VS Code and reads `AGENTS.md` (Claude Code, for example), for the cards and the text |
| git and a GitHub account | recommended | to keep the workspace in a private GitHub repository |
| A Semantic Scholar API key | recommended | free; without one, searches often fail on the rate limit |
| Zotero | optional | which included papers are in Zotero, and full texts from the PDFs attached there |
| The SSCI journal list | optional | the CSV from Clarivate's Master Journal List; otherwise the status is guessed |

---

## 2. Install

### 2.1 With VS Code

1. Install [VS Code](https://code.visualstudio.com/).
2. Find **Prior Work** in the Extensions view and install it
   ([Marketplace](https://marketplace.visualstudio.com/items?itemName=yoshida-kd.priorwork)).
3. The Prior Work icon appears in the activity bar. Go on to
   [Create a workspace](#3-create-a-workspace).

The extension sets Python up when you create a workspace. It uses Python 3.10 or later if it finds
one; otherwise it asks whether to install uv. uv (a small tool from Astral) goes into your home
folder, without administrator rights, and downloads Python for the workspace.

### 2.2 Windows and servers over SSH

- **Windows**: install WSL (Ubuntu), open a folder inside WSL with VS Code's **WSL** extension, and
  follow the steps above. Using Prior Work on Windows directly has not been tested.
- **A server**: connect with VS Code's **Remote - SSH** extension and follow the steps above on the
  server. The extension, Python and the workspace live on the server.

### 2.3 On the command line

Without the extension, or to work with the agent alone, install the `priorwork` command from PyPI.

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
2. If you use Zotero, fill in the **Zotero** fields ([7.2](#72-zotero)).
3. If you have the SSCI journal list, import it with **Import the SSCI List (CSV)…**
   ([7.3](#73-the-ssci-journal-list)).
4. **Save and Check the Connections** shows the diagnosis at the bottom of the page.

The settings are saved in the workspace's `.env`, which is kept out of Git. The page never shows the
values of the keys.

### 3.3 Put it on GitHub

The reports and state files contain abstracts, so keep the workspace in a **private** repository.

1. Press **Not on GitHub yet — publish it as a private repository** in the sidebar.
2. When VS Code asks, choose **Publish to GitHub private repository** and include all the files it
   suggests (`.env` is left out by `.gitignore`).

Later changes are committed and pushed from VS Code's **Source Control** view. The agent also offers
to commit at the end of each step.

### 3.4 Continue on another machine

1. Clone the repository in VS Code and open it.
2. Run **Set Up the Python Environment (.venv)** from the sidebar's menu (…).
3. Enter your keys in the **Settings** again (`.env` is not in Git), and import the SSCI list again.

---

## 4. A survey, step by step

```
① scope → ② search → ③ screen → ④ chase citations → ⑤ fill in the cards → ⑥ write → ⑦ check and export
```

**Next steps**, under each survey in the sidebar, says what to do now; click an item to start it.

### 4.1 Set the scope

**New Survey** asks for the topic, an English slug (the file name, e.g. `minimum_wage_employment`),
the depth and the research question. Add the period, the fields and the inclusion and exclusion
criteria later with **Edit the Scope** (right-click the survey). The criteria are shown at the top of
each paper's page.

The **depth** is a guide to the size of the survey.

| | quick | full |
| :--- | :--- | :--- |
| Suits | a narrow topic, or just an overview | a broad topic with subtopics, or when coverage matters |
| Searches | one or two queries | several queries per subtopic |
| Citation chasing | optional | yes |
| Cards | abstracts are fine | core papers checked in the full text |

To discuss the scope with the agent, say in its chat, for example, "I want to start a review on the
employment effects of minimum wages" (skill `/survey-new`).

### 4.2 Search

**Search** asks for an English query and how to search:

- **Search**: Semantic Scholar's relevance search (20 results).
- **Bulk search**: `+` (and), `|` (or), `-` (not) and `"phrases"`, most cited first (25 results). It
  finds the classics that keyword search buries.
- **SSCI journals only**: the relevance search, keeping SSCI journals only.

The results are registered as candidates. When both a working paper and its published version are
found, only the published one is kept; books, working papers, preprints and papers with no known
venue are left out by default. A paper whose DOI you already know is added with **Add Papers by DOI**.

### 4.3 Screen

**Screen Candidates** opens the page of the first unscreened paper.

- At the top, the survey's inclusion and exclusion criteria; below, the title, the authors, the
  journal and its SSCI status, citations, warnings and the abstract.
- **I** include, **M** maybe, **X** exclude (type the reason first), **U** back to candidate. After a
  decision it moves on to the next unscreened paper (setting `priorwork.autoAdvance`).
- **N** next unscreened, **J / K** next / previous, **O** open the DOI in the browser.
- Reasons you used before are offered as buttons.

Right-click papers in the sidebar to include, keep or exclude several at once.

Check papers with a warning (⚠️) before including them.

| Warning | Meaning |
| :--- | :--- |
| The DOI points to another title | Semantic Scholar's DOI belongs to another paper (a reply, say) |
| The DOI is a working paper / preprint version | a journal is named, but the DOI is an SSRN-style version |
| OpenAlex does not know the DOI / No DOI / DOI not verified | a wrong or missing DOI, or it could not be checked |
| May be a book review or comment | a title like "…, by Author", or a single page |

To have the agent recommend decisions, use **Ask Your Agent… → Recommend decisions on the candidates**
on the survey and paste the request into its chat. The agent recommends with reasons and records
nothing until you answer.

### 4.4 Chase citations

**Chase Citations** collects the references and citing papers of the included papers from OpenAlex
and registers them as candidates, ordered by how many included papers each is linked to. With three
or more included papers, only those linked to at least two are taken by default. Screen them as in 4.3.

### 4.5 Fill in the paper cards

Each included paper gets a card in section 3 of the report. Asking the agent is the quickest way.

1. Click **Fill in … cards** in the next steps, or **Ask Your Agent… → Fill in the paper cards** on the
   survey. A request naming the unfilled papers is copied.
2. Paste it into the agent's chat. The agent gets the full texts ([5.3](#53-full-texts)), writes only
   what they say, and updates the evidence level.
3. On each paper's page, check the card against the abstract, correct it if needed, and press
   **Ctrl+S** to save.

Section [5](#5-paper-cards) describes the cards.

### 4.6 Write the text

Section 1 (the background) and sections 4 to 7 (theoretical traditions, empirical methods, consensus
and debates, conclusions) are text written from the cards. Ask for it with **Ask Your Agent… → Write
the text of the report**; the agent cites only papers registered in the survey and runs the checks at
the end. To write it yourself, open it with **Open the Working Report (Markdown)** on the survey.

### 4.7 Check and export

1. **Check the Survey** lists the problems in VS Code's **Problems** panel ([6](#6-checks)). To have
   them fixed, use **Ask Your Agent… → Check and fix**.
2. **Export and View the Report** opens the version for reading (HTML). While cards are unchecked or
   empty, or the check reports ERRORs, it is marked *Draft* at the top. Open it in the browser to print
   it to PDF.

### 4.8 Add papers to Zotero

With Zotero set up, the next steps show **Add … to Zotero** when included papers are missing from
Zotero. Click it to copy their DOIs, paste them into Zotero's **Add Item by Identifier** (the magic
wand), press Enter, then click **Reload from Zotero**. Prior Work never writes to Zotero.

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

- The heading and the source line are generated. You (or the agent) write from the evidence level to
  the notes.
- The **first line** of each field goes into the comparison matrix (section 2), so keep it short;
  details go on the lines below it, which become bullet points.
- Write only what the abstract or the full text says. If it says nothing, write "not reported".

### 5.2 The evidence level

| Evidence | Meaning |
| :--- | :--- |
| unchecked | not checked yet (before filling in, or partly guessed) |
| abstract only | checked against the abstract |
| full text checked | checked against the full text |

Unchecked cards are flagged by the checks, and the export is marked *Draft*. In a full survey, check
the core papers in the full text.

### 5.3 Full texts

Get one with **Get the Full Text** on an included paper's page or from the paper's context menu in the
sidebar. PDFs are never stored in the workspace; only the extracted text is kept, in
`.priorwork/cache/fulltext/` (outside Git). Prior Work looks in this order:

1. a PDF attached in the local Zotero (matched by DOI)
2. a PDF attached in Zotero found through the Web API (WebDAV or Zotero's own file sync)
3. the text Zotero indexed (no page breaks; a fallback)
4. an open-access PDF

Publishers usually refuse automated downloads, so for papers that are not open access, attach the PDF
in Zotero first.

### 5.4 When a paper is no longer included

Its card is kept, with what was written, in the state file, and comes back if the paper is included
again.

---

## 6. Checks

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

## 7. Settings

### 7.1 API keys

| Setting | Purpose |
| :--- | :--- |
| Semantic Scholar API key | recommended; without one, searches often fail on the rate limit (HTTP 429) |
| OpenAlex API key, email address | optional; OpenAlex works without a key, with a daily usage cap |

### 7.2 Zotero

With Zotero set up, Prior Work shows which included papers are in Zotero and gets full texts from the
PDFs attached there. It never writes to Zotero or WebDAV.

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

### 7.3 The SSCI journal list

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

### 7.4 VS Code settings

| Setting | Default | |
| :--- | :--- | :--- |
| `priorwork.command` | *(empty)* | The `priorwork` command. Empty: the workspace's `.venv`, then `priorwork` on `PATH` |
| `priorwork.python` | *(empty)* | The Python used to create `.venv`. Empty: look for 3.10 or later, else use uv |
| `priorwork.autoAdvance` | `true` | Move on to the next unscreened paper after a decision |

---

## 8. Working with the agent

### 8.1 Asking

The workspace carries instructions for agents (`AGENTS.md`) and a skill for each step. Open the
workspace in Claude Code (or another agent) and talk to it; it follows them.

**Ask Your Agent…** on a survey copies a request for the common jobs.

| Job | Skill | What you decide |
| :--- | :--- | :--- |
| Fill in the paper cards | `/survey-extract` | where the PDFs are; whether abstracts are enough |
| Recommend decisions on the candidates | `/survey-screen` | include / exclude (with a reason) / maybe |
| Chase citations | `/survey-snowball` | decisions on the new candidates |
| Write the text of the report | — | the content |
| Check and fix | `/survey-check` | findings that cannot be resolved |

When you come back, say "let's continue"; the agent checks the progress and the next steps.

### 8.2 What the agent keeps to

- It only recommends decisions, and waits for your answer.
- Every paper mentioned in the text is registered; it never writes authors, years or DOIs from memory.
- Cards hold only what the abstract or the full text says, with the evidence level updated.
- It tells you about papers with ⚠️, and never calls a 🟡 (guessed) journal "in the SSCI".
- It runs the checks before calling anything finished.

Instructions for one workspace only (fields to prefer, writing style, journals to leave out, …) go in
`AGENTS.local.md`. `AGENTS.md` and the skills are rewritten to match the engine's version; do not edit
them.

---

## 9. Inside a workspace

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
| `.priorwork/surveys/YYYYMMDD_<slug>.json` | candidates, decisions and reasons (with their history), the search log, the scope, the depth | changed only by Prior Work |

The references (section 8) are generated from the included papers, with DOIs, and the appendix records
the searches, the counts, the reasons for exclusion and the decisions that were revised.

---

## 10. Updating the engine

A workspace pins the engine's version (the `priorwork` command) in `requirements.txt`, so nothing
changes behind your back. After the extension is updated, it offers **Update the Engine** when the
workspace's version is older; that also brings `AGENTS.md` and the skills up to date. When only
`AGENTS.md` and the skills are out of date, the sidebar shows a row to update them.

---

## 11. On the command line

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
./priorwork include SURVEY 2 5 7
./priorwork exclude SURVEY 3 --reason "theory only"
./priorwork maybe SURVEY 9 / ./priorwork reset SURVEY 9
./priorwork add SURVEY <DOI>... [--candidate]
./priorwork card SURVEY 3 [--set rq="..." evidence=abstract]
./priorwork render SURVEY
./priorwork check SURVEY [--offline]
./priorwork export SURVEY [--format html|docx|md] [--with-abstracts]
./priorwork fulltext SURVEY <number> [--pdf <path>]
./priorwork zotero [SURVEY] [--refresh]

# Finding literature
./priorwork search "<English query>" [--into SURVEY] [--bulk] [--sort citations|relevance|recent|cpy] [--year 2010-2024] [--ssci-only]
./priorwork snowball SURVEY [--direction both|references|citations] [--min-links N]
./priorwork get <DOI>
./priorwork citations <DOI> / ./priorwork references <DOI>
./priorwork journal "<journal or ISSN>"
```

`SURVEY` is the file name without the extension, or the slug. Most commands print JSON with `--json`.

---

## 12. Troubleshooting

**Searches stop with "rate limited (HTTP 429)".** Without a Semantic Scholar API key, requests share a
public pool. Enter a key in the settings. If it still happens, wait a while and try again; Prior Work
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
