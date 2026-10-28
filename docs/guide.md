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
  export. You choose where it stops for you to check (standard, full auto, manual). There are no
  commands or skill names to learn.
- **Start from your manuscript.** Give it a manuscript (Markdown, Quarto, Word, PDF, …) and it drafts
  its sections 1–3, or advises on the literature it is missing, the direction of its citations and the
  argument.
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

You choose where it stops for you to check. In the standard mode it stops twice: once the scope is set,
and before writing the cards (so that you can collect the papers in Zotero). Full auto never stops, and
manual stops after every step ([4.6](#46-choose-the-mode-ask-for-more)). You can also search and screen from the sidebar
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
5. So that your agent does not ask before every `./priorwork` command, allow `./priorwork` in the agent:
   - **When it is needed**: when you hand work to the agent (ask in the chat). The agent runs
     `./priorwork …` in the terminal for every search, decision and card, tens to hundreds of times per
     survey; without the permission it asks each time. The sidebar's buttons and the `./priorwork` you
     type yourself do not need it (they do not go through the agent).
   - **What it allows**: only commands starting with `./priorwork`. Priorwork touches only the workspace
     (`reports/`, `.priorwork/`) and the literature APIs; it never runs Git, and it writes to Zotero only
     if you allow it ([8.2](#82-zotero)).
     Other commands are still checked.
   - **Claude Code**: automatic. Making the workspace (and every `priorwork sync`) adds
     `Bash(./priorwork:*)` to the allowed rules in `.claude/settings.json`, keeping your other settings.
     To stop it, move the rule from `allow` to `deny` (just removing it, the next sync adds it back;
     it is not added while it is under `deny`).
   - **Antigravity**: it has no settings file in the workspace, so this cannot be automatic. Add
     `./priorwork` once to the terminal commands allowed to run without review in its settings (the
     allow list; the menu names differ between versions). Other commands are still checked.

The settings are saved in the workspace's `.env`, which is kept out of Git. The page never shows the
values of the keys.

### 3.3 Put it on GitHub

The reports and state files contain abstracts, so keep the workspace in a **private** repository.

1. Press **Not on GitHub yet — publish it as a private repository** in the sidebar.
2. When VS Code asks, choose **Publish to GitHub private repository** and include all the files it
   suggests (`.env` is left out by `.gitignore`).

The agent makes a branch named after the survey (e.g. `20261015_statutory_text_analysis`), commits and pushes at each step, and opens a pull request once the report is exported. **It never merges**: review the pull request and merge it on GitHub. In Claude Code, pushing to main, force-pushing and merging are also denied in `.claude/settings.json`. To keep the agent away from Git, say so in `AGENTS.local.md`.

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
  words and choose the depth and the mode; a request is copied. Open the chat with **Open Claude Code** (or similar)
  in the notification and paste it.

If you already have a research question, a period or criteria, add them to the request. Otherwise the
agent decides them from the topic; in the standard mode it shows you the scope it decided and waits (in
full auto it says what it decided in its final report).

### 4.2 What the agent does

The agent follows the workspace's `AGENTS.md` and skills, in this order. ⏸ marks where the standard mode
stops for you to check ([4.6](#46-choose-the-mode-ask-for-more)):

```
① scope ⏸ → ② search → ③ screen → ④ chase citations → ⏸ collect in Zotero
  → ⑤ fill in the cards → ⑥ write → ⑦ check and export
```

1. **Scope**: decides the research question, period, fields, inclusion and exclusion criteria and
   depth, and creates the survey.
2. **Search**: splits the topic into subtopics and searches with English queries, rephrasing those that
   find nothing.
3. **Screen**: sorts the candidates into included, maybe and excluded against the criteria, with a
   reason for each.
4. **Chase citations**: picks up papers missed by keyword search from the references and citing papers
   of the included ones, and screens them. In the standard mode it then stops and shows the DOIs to add
   to Zotero ([4.7](#47-collect-the-papers-in-zotero)). Collect the papers and their PDFs in Zotero and
   say "carry on": the cards can then be written from the full texts.
5. **Cards**: fills in the cards of the included papers from the full text (a PDF in Zotero or an
   open-access version) or the abstract.
6. **Text**: writes the background, the literature's theories, methods, debates and gaps (citing the
   included papers for each claim), and, kept apart from them, the hypotheses and implications for your
   study, from the cards.
7. **Check and export**: checks citations, DOIs, empty fields and whether the cards match the full
   texts, fixes them, and exports the version for reading (HTML).
At the end it reports the numbers searched and included, the parts of the scope it decided itself, what
is left to look at, how many included papers are not in Zotero yet, and how to view the report. It names
papers as "Goldschlag & Tabarrok (2018)", not by numbers such as `#232`. Since this takes a while, it may
tell you where it is in one line along the way (except at the stops, without waiting for an answer).

**Audit (optional).** To have another model check the survey too, ask that model (e.g. Claude if Gemini
wrote it) in its chat to "audit the survey <name>" (**Ask Your Agent… → Audit as another model** copies
the request), since a model rarely catches its own misreadings. The auditor compares every card with the
full text, checks the direction of each citation, hypotheses passed off as the literature and the
excluded papers, fixes them and records the audit (`./priorwork audit SURVEY --by "<model>"`, refused for
the model that wrote it). Without an audit, a survey is not left unfinished.

### 4.3 Depth

The **depth** is a guide to the size of the survey. If the request says "quick", "an overview", "full"
or "thorough", the agent follows it; otherwise it decides from how broad the topic is.

| | quick | full |
| :--- | :--- | :--- |
| Suits | a narrow topic, or just an overview | a broad topic with subtopics, or when coverage matters |
| Searches | 2–3 queries (10 results each) | 2–4 queries per subtopic (25 results each), aiming at 100+ candidates |
| Citation chasing | optional | yes |
| Cards | abstracts are fine | every included paper checked in the full text (abstract only when none can be found) |
| Text | an overview and the comparison table | background, theories, debates and gaps |

When a full survey has too few searches, **Search more** appears in the **Next steps** in the sidebar.
The agent sees it too and adds searches.

### 4.4 View the report

Open the version for reading (HTML) inside VS Code. It works the same on a server reached over SSH.

- Right-click the survey in the sidebar → **Export and View the Report**.
- Right-click `reports/<name>.html` in the Explorer → **View the Report in Priorwork**.
- When the agent exports it, click **View** in the notification.

You can select and copy the text, and search the page with **Ctrl+F** (**Cmd+F** on a Mac).

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

### 4.6 Choose the mode, ask for more

The **mode** decides where the agent stops and waits for you to check.

| Mode | Where it stops | How to ask |
| :--- | :--- | :--- |
| **Standard** (default) | Twice: once the scope is set, and before writing the cards (for you to collect the papers in Zotero) | say nothing |
| **Full auto** | Never: it carries on to the end | "full auto", "to the end without stopping" |
| **Manual** | After every step (scope, searches, screening, citations, Zotero, cards, text, check); decisions too, as recommendations it waits on | "go through it with me", "show me one by one" |

Standard is the default because when the included papers and their PDFs are in Zotero before the cards
are written, more cards are checked against the full texts, which saves work in the end. Between the
stops, the agent decides on its own and records its reasons.

The mode is recorded in the survey, so the next conversation carries on in the same mode. To always use
one mode, write it in the workspace's `AGENTS.local.md` (e.g. "Mode: full auto"). **New Survey → Ask
your agent to do it** in the sidebar lets you choose it too.

- **More**: ask in the chat — "carry on", "search more", "fill in the cards". Saying "carry on" where it
  stopped tells it you are done checking. **Ask Your Agent…** (right-click the survey) also copies
  requests for the common jobs: carry on, carry on to the end, search more, screen, chase citations, fill
  in the cards, write the text, check and fix, and audit as another model.

- **Redo**: ask "redo this survey" and the agent makes a new one with the same slug; Priorwork numbers
  it right after the date (`20261012_v2_<slug>`) and the sidebar shows **v2**. When surveys share a
  topic, the sidebar also shows their names and dates side by side. Once you no longer need the old one,
  right-click it → **Archive the Survey…** (or ask the agent). It leaves the list for the **Archived**
  group at the bottom; nothing is deleted, and the button on it brings it back
  (`./priorwork archive SURVEY [--undo]`).

When you come back to a conversation, "let's continue" is enough: the agent checks the state and takes
the next step.

### 4.7 Collect the papers in Zotero

You add the papers, unless you let Priorwork do it (below). Two things make it easier (for setting up
Zotero, see [8.2](#82-zotero)).

**Add the included papers' DOIs to Zotero at once.**

1. In Zotero, select the collection (folder) the papers should go into.
2. Click **Add … to Zotero** in the next steps of the sidebar and **Copy the DOIs** (or ask the agent
   for "the list of DOIs to add to Zotero").
3. Paste them into Zotero's **Add Item by Identifier** (the magic wand) and press Enter. They go into the
   selected collection.
4. Click **Reload from Zotero** to update the status.

In the standard mode, the agent stops before writing the cards and shows you this list of DOIs. The next
steps in the sidebar show **Stop here and wait for the user** too; click it to copy the DOIs, and the
request asking the agent to carry on. The list of DOIs works without the Zotero link too (it then lists
every included paper).

**Or let Priorwork add them.** If you allow it in the settings ([8.2](#82-zotero)) and link a collection
to the survey (below), Priorwork puts the included papers into that collection itself:

- An item already in your library (same DOI, or the same title) is added to the collection; otherwise a
  new item is made from the bibliographic data. Priorwork never changes or deletes your items, never
  touches other collections and does not make collections.
- **Add … to the Zotero collection** in the next steps shows the list first and adds it once you confirm.
  The agent does the same: in the standard mode it shows you the list at the stop before the cards and
  adds it when you agree; in full auto it adds without stopping; in manual it asks each time.
- No PDFs come with the items: select them in Zotero, right-click → **Find Full Text**.
- **Undo What Priorwork Added…** (or asking the agent to undo it, `./priorwork zotero <survey> --undo`)
  takes back only what Priorwork wrote. Items it made go to the Zotero trash, except those you changed
  or attached a file to since; items that were already in your library only leave the collection.

**Link a Zotero collection to the survey.** Under each survey in the sidebar, click **Link a Zotero
collection…** and choose a collection you made in Zotero (without the Zotero link it reads **Zotero:
not set up** and opens the settings page). Priorwork does not make collections, so make a new one in
Zotero (right-click "My Library" → New Collection…) and bring it in with **Reload the list**. The list is
the same tree as in Zotero, and papers in a collection under it count as in it (when the same name is
under two parents, the path `parent / child` tells them apart). Then choose it (or tell the agent
"use my Zotero collection X"). The row then reads **Zotero: <collection>**; click it to change or unlink
it. Once linked:

- "In Zotero" means in that collection.
- Papers you put into the collection yourself can be registered as candidates (**Register … papers from
  the Zotero collection** in the next steps). The agent includes them unless they are clearly out of
  scope.
- Full texts come from the PDFs in that collection first.

### 4.8 Start from a manuscript (filling it in, a draft or advice)

You can also start from your own manuscript, finished or not, instead of a topic. There are three
kinds of report, and one manuscript can have several as separate reports.

| Purpose | Suits | What the report holds |
| :--- | :--- | :--- |
| **Filling it in** (the default) | a manuscript in progress: sections missing, thin or without citations | a map of what each section lacks, and a list of what to add where (each item quotes the sentence it goes before or after), cards, a check of its citations |
| **A draft of sections 1–3** | a manuscript with the analysis (data, methods, results) written | claims to back with literature, paper cards, a draft introduction, literature review and theory and hypotheses, a check against fitting hypotheses after the results |
| **Advice on the manuscript** | a finished or unfinished paper | a summary of the advice, a check of its citations (the direction of each cited finding, overstatements), missing literature, comments on the argument |

**Where to put the manuscript.** In the workspace's `manuscripts/`, one folder per paper (the same
explanation is in `manuscripts/README.md`):

```text
manuscripts/
  make_or_buy/          ← one folder per paper (an English name)
    paper.md            ← the manuscript; only the parts that are written
    tables/             ← tables, figures and logs of the results (any not in the manuscript)
```

Any format will do. Priorwork turns Markdown, Quarto (.qmd, and the HTML it renders), LaTeX, Word
(.docx) and PDF into text for the agent (`./priorwork read`). If the results are in separate files
(regression tables in .tex, …), put them in the same folder. The agent reads everything in it.

**How to ask.** **New Survey → Start from my manuscript** in the sidebar lets you choose the manuscript
(or its folder) and copies the request. If you choose one outside the workspace, it offers to copy it
into `manuscripts/` (the original stays where it is). You can also ask in the chat:

> The manuscript in manuscripts/make_or_buy is written up to the analysis. Gather the literature to back
> it up and write the introduction, literature review and theory and hypotheses.

> What literature is the manuscript in manuscripts/make_or_buy missing, and where does it cite the
> literature badly?

> The manuscript in manuscripts/make_or_buy is half written. Fill in what it lacks from the literature.

**Leave marks where you want help.** While writing, put `[cite]` where a citation is needed, `[@?]`
where a paper should be cited, or `TODO(priorwork): <what you need>` on a line of its own (say,
`TODO(priorwork): the literature on institutions`). `./priorwork read` lists them, and when filling the
manuscript in, the agent takes them first and says which it could not fill (and why).

**Agreeing what to make.** The agent reads the manuscript, then proposes the purpose (filling it in, a
draft, advice, or several), which parts of the manuscript to cover, the scope of the searches and how many reports, and waits
for your answer. If your request already settles these, it goes ahead. If you want both, the papers
included in the first report carry over into the second.

For **a draft of sections 1–3**, the agent then:

1. Writes "The manuscript in brief" in the report (research question, variables, data, identification,
   main results, unexpected results).
2. Lists, with IDs, the claims that need literature (why it matters, the lines of research it
   contributes to, mechanisms, rival theories, precedents for the methods). For each main result it also
   makes a claim for **the findings that conflict with it**.
3. Searches and screens claim by claim, and fills in each card's **Role in the manuscript** (e.g. "C2
   supports; method precedent"). The comparison matrix gets a Role column too.
4. Drafts the introduction, literature review and theory and hypotheses in the language of the
   manuscript, citing only included papers.
5. Checks the survey and writes the draft to `reports/<name>.draft.md`, with the references it cites
   (`--format docx` for Word).

Writing hypotheses after seeing the results easily turns into hypothesizing after the results are known
(HARKing). So the report records, in a section apart from the draft, the literature behind each
hypothesis, what was added or changed after seeing the results, which results to treat as exploratory,
and how conflicting literature is handled. That section is for you to judge; it is not part of the
exported draft.

For **advice on the manuscript**, the agent registers the papers the manuscript cites, fills in their
cards, and judges place by place whether the direction, setting and method of each cited paper match
what the manuscript says (fits / opposite direction / overstated / weak support). It then writes about
the literature the manuscript is missing (where and why to cite it) and about the argument (how the
question, the gap in the literature, the hypotheses, the methods, the results and the contribution hang
together), and sums up what to fix, most important first.

For **filling it in**, the agent maps each section's state (written, thin, heading only, missing) and
your marks, lists the claims that need literature (with the findings that conflict with your results),
searches and screens claim by claim, and writes what to add in the manuscript's order: "Write the
section", "Insert" or "Add citations", each with **Where** (the heading and the sentence it goes before
or after, quoted) and **Why**, and the text in the language of the manuscript. It fills in only what the
literature backs, never the content of your methods or results. `./priorwork export SURVEY --draft`
writes the list with its references; for an Octavo manuscript it goes into the project's inbox
([4.9](#49-working-with-an-octavo-manuscript)).

Either way, the manuscript itself is never rewritten. Read the draft, the additions or the advice and
edit your manuscript yourself.

On the command line: `./priorwork new "<topic>" --slug <slug> --manuscript manuscripts/make_or_buy
--purpose complete` (`draft` for a draft, `advice` for advice; without `--purpose`, `complete`), and for
filling in or a draft, `./priorwork export SURVEY --draft`.

### 4.9 Working with an Octavo manuscript

A manuscript you write in [Octavo](https://github.com/yoshida-kd/octavo) (a tool for writing papers in
Markdown and Quarto) can stay in its Octavo project (another repository). One Priorwork workspace can
serve the papers of many Octavo projects.

Octavo's collection picker, lists of collections and **Ask Priorwork for the Literature** come with Octavo
releases after 0.6.4.

**The link between them is a Zotero collection.** Octavo pulls its `.bib` of references from the
collection named in its settings (`zotero_collection`, with `octavo bib pull`). Link the Priorwork survey
to the same collection, and the included papers you put there become the Octavo manuscript's references
too.

1. In the Octavo project, choose the paper's collection (**Choose the Zotero Collection** in Octavo's
   sidebar, or `octavo config set zotero_collection "<name>"`).
2. Right-click the paper in Octavo's sidebar → **Ask Priorwork for the Literature** (or choose the
   paper in the Octavo project with Priorwork's **New Survey → Start from my manuscript**) to copy a
   request, and paste it into the agent's chat in the window of your Priorwork workspace. The two are
   separate windows, so the request carries it across.
3. The agent reads the manuscript, the project's results and tables, and the literature it cites (the
   `.bib`), and registers the papers it cites (`./priorwork add SURVEY --cited`). The survey is linked to
   the same Zotero collection as Octavo.
4. The draft is exported in Octavo's form into the Octavo project's inbox
   (`./priorwork export SURVEY --draft --octavo` → `literature/priorwork/<survey>.md`, with a `.json`
   manifest and `<survey>.cards.json`, the cards of the included papers for Octavo to show over each
   `[@key]`): citations become `[@key]` from the `.bib`, and Octavo makes the references section.
   Priorwork never changes the manuscript: ask the agent in the Octavo project to "work the draft from
   Priorwork into the manuscript" (or move it yourself).
5. Papers not in the `.bib` yet are written as `[@PRIORWORK:<DOI>]`, with a list of their DOIs. Put them
   in the Zotero collection ([4.7](#47-collect-the-papers-in-zotero); Priorwork can do it for you) and run
   `octavo bib pull` and then `octavo priorwork resolve` in Octavo, which replaces them by `[@key]` from
   the DOIs (until then, Octavo's checks report them as missing keys). Octavo 0.6.6 and older have no
   inbox: export again after `octavo bib pull` instead.

**Requests without the clipboard.** An Octavo that knows where your Priorwork workspace is puts its
requests in the workspace's `.priorwork/requests/` instead of copying them. They show under **Requests
from Octavo** at the top of the sidebar: click one to ask your agent to carry it out (a short request
that points to it) or to decline it with a reason Octavo can read. The agent records the outcome with
`./priorwork requests <id> --done --survey <survey>`, and Octavo shows it.

**One survey for several papers.** A survey on a topic (say, the literature on outsourcing) can serve
several papers. Right-click the survey → **Link to an Octavo Project…** and choose the project's folder
(as many as you like); **Export for an Octavo Project…** writes the sections on theories, methods,
debates and gaps with that project's `.bib` keys to its inbox, `literature/priorwork/<survey>.md`
(`./priorwork scope SURVEY --octavo <path>`, `./priorwork export SURVEY --octavo <project>`). In Octavo,
add the survey's collection to the project's (**Choose the Zotero Collection** there lets you mark any
number).

**Several surveys for one Octavo project.** One paper may get several surveys, by angle (theory,
methods, …), even from different workspaces. Then make a collection for each survey in Zotero under the
Octavo project's collection (e.g. "Make or buy / Theory" and "Make or buy / Methods" under "Make or
buy"), and link each survey to its own. `octavo bib pull` takes the collections under its collection
too, so every survey's included papers end up in one `.bib`. The sidebar's list of collections shows
Octavo's collection and the ones under it first, and `./priorwork status` lists the other surveys for
the same Octavo project.

Priorwork never changes the files of the Octavo project. The check tells you when the survey and Octavo
use different collections. The manuscript's place is recorded relative to the workspace (e.g.
`../make_or_buy/papers/main`), so it works on another machine too if the repositories are cloned side by
side in the same way.

### 4.10 Short texts from a survey

You can also ask for a short text based on a survey: a lecture handout, reading notes, a summary of
the main points ("a lecture handout from this survey, in three parts, about 2,000 characters", say).
The agent records its purpose, length and structure (`./priorwork derive`) and writes it in
`reports/<name>.<text name>.md`. It sits beside the survey's files, so it goes into Git with them.

- It cites included papers whose cards were checked against the full text, and checks numbers and the
  direction of findings against the cards.
- The length leaves out citations in parentheses ("(Dell 2010)") unless you say otherwise
  (`--count-citations`).
- The references at the end are made from the papers it cites.
- `./priorwork check` reports citations that are not included papers (ERROR), citations from cards not
  checked against the full text and numbers that are not in the card (WARN), and a length off the
  target (INFO).
- The version for reading is `./priorwork export SURVEY --derived <text name>`
  (`reports/<name>.<text name>.html`; `--format docx` for Word).

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

Each included paper gets a card in the section "The papers" of the report. Write it on the paper's page and press
**Ctrl+S** to save. **Get the Full Text** brings in the full text ([6.3](#63-full-texts)). To hand only
the cards to the agent, use **Ask Your Agent… → Fill in the paper cards**. Section
[6](#6-paper-cards) describes the cards.

### 5.6 Write the text

The report puts the synthesis first: the background (section 1); the literature's theoretical
traditions, methods, consensus and debates, and gaps (sections 2–5, each claim citing included papers);
and the hypotheses and implications for your study (section 6, kept apart from the literature). The
comparison matrix, the paper cards and the references follow. These sections are text written from the
cards, and each says under its heading what to write (reports made up to 0.1.5 keep their older order).
Mermaid diagrams (```` ```mermaid ````) are drawn in the HTML. Open the report with **Open the Working
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
- The **first line** of each field goes into the comparison matrix, so keep it to one short sentence;
  details go on the lines below it, which become bullet points.
- Write only what the abstract or the full text says. If it says nothing, write "not reported".
- Write the cards in the language of the report, keeping terms in the original in brackets.
- On a card checked against the full text, give the page (`(p. 12)`) for the data, the identification
  and the main findings, or "(page not checked)" when the full text has no page breaks.

### 6.2 The evidence level

| Evidence | Meaning |
| :--- | :--- |
| unchecked | not checked yet (before filling in, or partly guessed) |
| abstract only | checked against the abstract |
| full text checked | checked against the full text fetched with **Get the Full Text** (`fulltext`) |

Unchecked cards are flagged by the checks, and the export is marked *Draft*. In a full survey, every
included paper is checked in the full text; a card may stay "abstract only" only when no full text
could be found, and the checks list those papers so that you can attach their PDFs in Zotero.

### 6.3 Full texts

Get one with **Get the Full Text** on an included paper's page or from the paper's context menu in the
sidebar (the agent gets them the same way). PDFs are never stored in the workspace; only the extracted text is kept, in
`.priorwork/cache/fulltext/` (outside Git). Priorwork looks in this order:

1. a PDF attached in the local Zotero (matched by DOI)
2. a PDF attached in Zotero found through the Web API (WebDAV or Zotero's own file sync), preferring
   the collection linked to the survey
3. the text Zotero indexed (no page breaks; a fallback)
4. an open-access PDF (every location OpenAlex knows; on a landing page, such as an institutional repository's, the PDF link it gives)

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
| Cards marked "full text checked": numbers not in the full text, pages not in the paper, no page given, no full text fetched | WARN |
| Cards not written in the language of the report | WARN |
| Synthesis sections (theories, methods, debates, gaps) that cite no paper; a number of included papers in the text that disagrees with the survey | WARN |
| Included papers missing from Zotero | WARN |
| The report matches the state file | WARN |
| Unscreened candidates, non-SSCI included papers, citations taken for organisations or table numbers | INFO |

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
survey ([4.7](#47-collect-the-papers-in-zotero)) and gets full texts from the PDFs attached there. By
default it only reads: it never writes to Zotero or WebDAV.

1. Create an API key at <https://www.zotero.org/settings/keys> with **only "Allow library access"**
   (no notes, no write access). "Your user ID for use in API calls" on the same page is the user ID.
2. Enter the key and the user ID under **Zotero** in the settings. If Zotero runs on this machine,
   enter its data folder too (default `~/Zotero`).
   - **To let Priorwork add the included papers to the survey's collection** ([4.7](#47-collect-the-papers-in-zotero)),
     check **Let Priorwork add the included papers to the survey's collection** (`ZOTERO_WRITE=1` in
     `.env`) and also check **Allow write access** for the key on the Zotero page. Both are needed;
     **Save and Check the Connections** tells you whether the key can write.
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
`priorwork-extract`, `priorwork-check`). To start from a manuscript, it uses
`priorwork-manuscript` ([4.8](#48-start-from-a-manuscript-filling-it-in-a-draft-or-advice)). The agent
picks them from the words of your request, so there are no names to remember.

Instructions for one workspace only (fields to prefer, writing style, journals to leave out, "Mode:
full auto", …) go in `AGENTS.local.md`. `AGENTS.md` and the skills are rewritten to
match the engine's version; do not edit them.

### 9.2 What the agent keeps to

- It leaves a reason for every decision and for the scope, and never overturns your decisions.
- It stops where the mode says, and decides on its own in between.
- In its reports it names papers as "Author (year)", not by number.
- Every paper mentioned in the text is registered; it never writes authors, years or DOIs from memory.
- Cards hold only what the abstract or the full text says, with the evidence level updated.
- It replaces papers with ⚠️ by their published versions, or sets them to maybe and tells you. It never
  calls a 🟡 (guessed) journal "in the SSCI".
- It runs the checks before calling anything finished.
- It never opens the files of Priorwork itself (inside `.venv`).
- It writes to Zotero only through `./priorwork zotero --add`, when you allow it (it adds the included
  papers to the survey's collection). In Git, it commits and pushes on a branch named after the survey and opens
  a pull request; you merge.

---

## 10. Inside a workspace

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
    ├── cache/               # full texts, the Zotero index (not in Git)
    └── data/                # the SSCI list (not in Git)
```

| File | Contents | Editing |
| :--- | :--- | :--- |
| `reports/YYYYMMDD_<slug>.md` | the working report (a redone survey is `YYYYMMDD_v2_<slug>.md`) | the text and the card fields are written by hand (or by the agent); everything between `<!-- BEGIN priorwork:… -->` and `<!-- END priorwork:… -->` is regenerated |
| `.priorwork/surveys/YYYYMMDD_<slug>.json` | candidates, decisions and reasons (with their history), the search log, the scope, the depth, the Zotero collection | changed only by Priorwork |

The references are generated from the included papers, with DOIs, and the appendix records
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
./priorwork new "<topic>" --slug <slug> [--mode standard|auto|manual] [--depth quick|full] [--question ...]
./priorwork new "<topic>" --slug <slug> --manuscript manuscripts/<paper> [--purpose draft|advice]   # from a manuscript
./priorwork scope SURVEY --question "..." [--years ... --fields ... --inclusion ... --exclusion ... --depth ... --mode ...]
./priorwork read PATH                     # the text of a manuscript (.md, .qmd, .html, .docx, .pdf, …)
./priorwork add SURVEY --cited            # register the papers the manuscript cites (the DOIs in its .bib)
./priorwork export SURVEY --draft --octavo   # the draft in Octavo's form ([@key])
./priorwork archive SURVEY [--undo]       # hide it from the list (the files stay); status --archived lists them
./priorwork list SURVEY [--status candidate maybe] [--abstract]
./priorwork include SURVEY 2 5 7 [--reason "..."]
./priorwork exclude SURVEY 3 --reason "theory only"
./priorwork maybe SURVEY 9 / ./priorwork reset SURVEY 9
./priorwork add SURVEY <DOI>... [--candidate]
./priorwork fix SURVEY N [--id <published DOI>] [--authors "A; B"] [--year Y] [--confirm "<what you checked>"]
./priorwork card SURVEY 3 [--set rq="..." evidence=abstract]
./priorwork render SURVEY
./priorwork check SURVEY [--offline]
./priorwork export SURVEY [--format html|docx|md] [--with-abstracts]
./priorwork derive SURVEY [NAME --purpose "..." --length N --structure "a; b"]   # a short text from the survey (no NAME: list them)
./priorwork export SURVEY --derived NAME [--format html|docx|md]
./priorwork fulltext SURVEY <number> [--pdf <path>]

# Zotero (read only)
./priorwork zotero [SURVEY] [--refresh]            # the link / which included papers are in Zotero
./priorwork zotero --collections                   # list the collections
./priorwork zotero SURVEY --collection "<name>"    # link a collection ("" unlinks it)
./priorwork zotero SURVEY --import                 # register the papers of the collection as candidates
./priorwork zotero SURVEY --dois                   # DOIs of included papers not in Zotero (for the magic wand)

# Finding literature
./priorwork search "<English query>" [--into SURVEY] [--bulk] [--sort citations|relevance|recent|cpy] [--year 2010-2024] [--ssci-only] [--field social|all] [--limit N]
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
