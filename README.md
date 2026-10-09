# Priorwork

**Hand your literature review to an AI agent, then check it — no terminal needed**

[日本語](README.ja.md) · **[Guide](https://yoshida-kd.github.io/priorwork/guide/)** · [Website](https://yoshida-kd.github.io/priorwork/)

Priorwork (as in *prior work*) is a toolkit for handing topic-based literature reviews in economics,
sociology, political science, public administration, management, psychology and neighbouring fields
to an AI agent (Claude Code, Antigravity and others).

**Ask in plain words; check in the sidebar.** Tell your agent "do a full review of …" (or use **New
Survey → Ask your agent to do it** in VS Code). It sets the scope, searches, screens, chases
citations, fills in the paper cards, writes the review, checks it and exports it, without stopping.
You read the report and overturn or correct anything from the Priorwork sidebar. No terminal, no
commands or skill names to learn. The extension never calls an AI service itself, so there is
nothing to pay for beyond the agent you already use.

- **Every decision has a reason.** The agent records a reason for each paper it includes or
  excludes, and writes the scope it chose into the report. Overturn a decision with one key on the
  paper's page; the agent follows your changes and never overturns them. Prefer to decide each
  paper yourself? Ask it to go through it together with you.
- **The repository remembers.** Candidates, decisions and the search log live in JSON under
  `.priorwork/surveys/`, so a survey picks up where it left off in the next conversation.
- **Cards you can check.** Each included paper gets a card (research question, X, Y, data,
  identification, findings, limitations) written only from the abstract or the full text, with the
  evidence it was checked against.
- **Fabrication is caught mechanically.** `priorwork check` finds author–year citations in the
  text that match no registered paper, and DOIs that point to other papers.
- **People read only the reports.** `priorwork export` writes the version for reading (HTML);
  the state and caches stay out of the way in `.priorwork/`.

```
① scope → ② search → ③ screen → ④ chase citations → ⑤ fill in the cards → ⑥ write → ⑦ check and export
```

## How it fits together

| | The engine (the `priorwork` command and the VS Code extension) | A workspace |
| :--- | :--- | :--- |
| Holds | the code and the originals of `AGENTS.md` and the skills | the reports, their state, `.env` |
| Comes from | PyPI (`pip install priorwork`) and the VS Code Marketplace (Priorwork) | you (a private GitHub repository) |
| Updated by | releases | `./priorwork upgrade` |

A workspace pins the engine's version in `requirements.txt`, so nothing changes behind your back;
`./priorwork upgrade` moves it to a new release in one command. Workspaces hold no copy of the
code, so updates never conflict.

---

## Setup

### From VS Code

1. Install **Priorwork** from the Extensions view. Nothing else is needed to start: the
   extension uses Python 3.10 or later if you have it, and otherwise installs
   [uv](https://docs.astral.sh/uv/), which downloads Python (into your home folder, without
   administrator rights). You will also want an AI agent that works in VS Code (Claude Code,
   Antigravity, …), and **git** to keep the workspace on GitHub.
2. In the Priorwork activity bar, choose **Create a Workspace**, then an empty folder and the
   language of the reports (English or Japanese). The extension creates a `.venv` in that folder,
   installs `priorwork` from PyPI and sets the workspace up.
3. Open the **Settings** (the gear in the sidebar): add a free Semantic Scholar API key
   (recommended), and Zotero and the SSCI list if you have them. **Save and Check the Connections**
   tells you whether they work.
4. **Publish it to GitHub** from the row in the sidebar, as a **private** repository. The agent
   commits at each natural break; it pushes only when you agree.
5. **New Survey** → **Ask your agent to do it**: give the topic and paste the copied request into
   the agent's chat (or just ask in the chat). The agent works through to the exported report.
6. Read the report (**Export and View the Report**, or right-click `reports/*.html` → **View the
   Report in Priorwork**; this works over SSH too), then check decisions and cards on each paper's
   page and correct what you disagree with.
7. Ask for more with **Ask Your Agent…** on the survey, or in the chat ("search more", "carry on").

What the extension does:

- The sidebar: each survey's next steps, and its papers as *to screen*, *maybe*, *included* and
  *excluded*, with include / maybe / exclude on each (several at once, too).
- A page per paper: the abstract, the SSCI status, warnings and the scope's criteria, with **I**
  include, **M** maybe and **X** exclude (with a reason). It then moves on to the next unscreened
  paper. For included papers, the page also holds the paper card, to check and correct what the
  agent wrote (**Ctrl+S** saves it).
- Search (by relevance, boolean bulk search, SSCI journals only), citation chasing, adding by DOI,
  full texts, Zotero, checks (in the Problems panel), the report for reading, settings, diagnosis
  and updates of the engine.
- Requests for the agent, copied to paste into its chat. When the agent changes the state or the
  report, the sidebar and the paper page follow.

To continue on another machine, clone the repository in VS Code, run **Set Up the Python
Environment** from the sidebar's menu and enter your keys in the **Settings** again (`.env` is not
in Git).

### From the command line

```bash
mkdir my-surveys && cd my-surveys
python3 -m venv .venv
.venv/bin/pip install priorwork
.venv/bin/priorwork init --lang en     # runs git init and writes reports/ .priorwork/ AGENTS.md skills ./priorwork .env.example …
cp .env.example .env                   # add your API keys (.env is kept out of Git)
./priorwork doctor                     # diagnose the setup (--online also checks the connections)
git add -A && git commit -m "Initialize priorwork workspace"
gh repo create my-surveys --private --source=. --push   # or create it on the web and git remote add
```

Keep the workspace in a **private** GitHub repository: the reports and state files contain
abstracts. To continue on another machine, clone it, run
`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` and recreate `.env`
(`priorwork settings` shows what is set).

`--lang` is the workspace's language: the headings of the reports, `AGENTS.md` and the skills. It
is fixed when the workspace is created. The language of the command's messages is separate: it is
`PRIORWORK_LANG` (`en` or `ja`), or else the locale (the VS Code extension follows VS Code's
display language).

What goes into Git (`priorwork sync` manages `.gitignore`):

| In Git | Not in Git |
| :--- | :--- |
| `reports/*.md`, `.priorwork/surveys/` (the state), `.priorwork/config.json`, `.priorwork/sync.json`, `AGENTS.md` and the skills, `./priorwork`, `requirements.txt`, `.env.example` | `.env` (API keys), `.venv/`, `.priorwork/cache/` (full texts), `.priorwork/data/` (the SSCI list, which may not be shared under its licence), the output of `priorwork export` |

`./priorwork doctor` also checks that the workspace is a Git repository with a GitHub remote and
that `.env` has not been committed by mistake.

What `priorwork init` creates:

```text
my-surveys/
├── reports/                 # the reports (the working .md, and .html etc. from priorwork export)
├── AGENTS.md, CLAUDE.md     # instructions for agents (written by priorwork sync; do not edit)
├── AGENTS.local.md          # instructions for this workspace only (edit freely)
├── .claude/skills/          # the skills for each step (a symlink to .agent/skills)
├── .agent/skills/           # written by priorwork sync
├── priorwork                # the wrapper (./priorwork; uses .venv when there is one)
├── requirements.txt         # the engine's version (priorwork==X.Y.Z)
├── .env / .env.example
└── .priorwork/
    ├── config.json          # the workspace's language
    ├── surveys/             # the state (in Git)
    ├── cache/               # extracted full texts, the Zotero index (not in Git)
    └── data/                # the SSCI journal list CSV (not in Git)
```

### Updating the engine

```bash
./priorwork upgrade                  # to the latest version on PyPI (--to 0.4.0 for a given one)
```

It rewrites `requirements.txt`, runs `pip install` and syncs `AGENTS.md` and the skills. If
`pip install` fails, `requirements.txt` is restored.

`./priorwork status` warns when `AGENTS.md` and the skills do not match the engine's version.
`priorwork sync` overwrites only files it wrote itself; anything else is left alone unless you
pass `--force`.

### API keys

They go into the workspace's `.env` (kept out of Git). In VS Code, set them on the **Settings** page;
on the command line, edit `.env` or pipe JSON into `priorwork settings --stdin`.

| Variable | Purpose |
| :--- | :--- |
| `SEMANTIC_SCHOLAR_API_KEY` | A [Semantic Scholar API key](https://www.semanticscholar.org/product/api#api-key-form) (recommended). Without one, searches often fail on the rate limit |
| `OPENALEX_API_KEY` / `OPENALEX_MAILTO` | Optional. OpenAlex works without a key, with a daily usage cap |
| `ZOTERO_API_KEY` / `ZOTERO_USER_ID` | Optional. The Zotero link (read only); see below |
| `ZOTERO_WEBDAV_URL` / `ZOTERO_WEBDAV_USER` / `ZOTERO_WEBDAV_PASSWORD` | Optional. If Zotero syncs files through WebDAV (Nextcloud and the like) |
| `ZOTERO_DATA_DIR` | Optional. Zotero's data folder when Zotero runs on this machine (default `~/Zotero`) |

### The Zotero link (optional)

With it, priorwork shows which included papers are in Zotero (`priorwork zotero`, `status`,
`check`) and gets full texts from the PDFs attached there (`priorwork fulltext`). It never writes
to Zotero or WebDAV.

1. Create an API key at https://www.zotero.org/settings/keys with **only "Allow library access"**
   (no notes, no write access). "Your user ID for use in API calls" on the same page is the user ID.
2. For WebDAV sync, set the URL of the folder that holds the PDF zips (the URL set in Zotero plus
   `zotero/`) and the credentials. With Nextcloud, share the `zotero` folder **read only** with a
   dedicated user and use that user's app password.
3. Check the connection with `./priorwork zotero` (it shows the size of the library and the WebDAV result).

If WebDAV reports "folder not found", check the URL. With Nextcloud under a sub-path (such as
`https://example.com/nextcloud/`), include that path:

```
https://example.com/nextcloud/remote.php/dav/files/<user>/zotero/
```

### The SSCI journal list (recommended)

Only Clarivate's [Master Journal List](https://mjl.clarivate.com/) settles whether a journal is in
the SSCI. Download the SSCI list as CSV and import it on the **Settings** page in VS Code, or with
`./priorwork settings --import-ssci <CSV>` (it is copied to `.priorwork/data/`, which stays out of Git). Without it, the status is **guessed** from a built-in list of about 100
major journals.

| Shown | Meaning |
| :--- | :--- |
| ✅ SSCI (checked against the list) | the ISSN or the name matches the list |
| 🟡 Probably SSCI (guessed from the journal name; verify) | no list set; matches the built-in list |
| 🔍 Journal (SSCI not verified) / ⚪ Not in SSCI | a journal of unknown status / not in the list |
| 📕 Book / ❌ Working paper / preprint / ❓ Unknown venue | left out of search results by default |

---

## Usage

### With your agent

Open the workspace with your agent and ask in plain words, for example "do a full review of the
employment effects of minimum wages". The agent follows `AGENTS.md` and the skills
(`.agent/skills/`, also under `.claude/skills/`): the entry point `priorwork` looks at the state and
takes the next step, through to the exported report. You never need to type a skill name (typing
`/priorwork` works too). In VS Code, **New Survey → Ask your agent to do it** and **Ask Your Agent…**
on a survey copy ready-made requests.

| Skill | What it does |
| :--- | :--- |
| `priorwork` | the entry point: looks at the state and runs the whole survey, step by step |
| `priorwork-new` | sets the scope, creates the survey and runs enough searches for the depth |
| `priorwork-screen` | decides each candidate against the criteria, with a reason (in consultation mode, recommends and waits) |
| `priorwork-snowball` | chases the references and citations of the included papers |
| `priorwork-extract` | gets the full texts and fills in the paper cards (RQ, identification, …) |
| `priorwork-check` | checks the survey, fixes what it finds and exports the report |

The agent decides on its own by default. To decide the scope and each paper yourself, ask it to go
through it together with you, or write that in `AGENTS.local.md`. When you come back, say "let's
continue"; the agent looks at `./priorwork status` for progress and the next steps.

### Depth (quick / full)

A survey has a depth, taken from the request (or chosen by the agent) and changeable later with
`./priorwork scope SURVEY --depth full`.

| | quick | full |
| :--- | :--- | :--- |
| Suits | a narrow topic, or just an overview | a broad topic with subtopics, or when coverage matters |
| Searches | 2–3 queries (10 results each) | 2–4 queries per subtopic (25 results each), 100+ candidates |
| Citation chasing | optional | yes |
| Cards | abstracts are fine | core papers checked in the full text |

The numbers are guides, not limits. The rules and `priorwork check` are the same at both depths.

### The files of a survey

| File | Contents | Editing |
| :--- | :--- | :--- |
| `reports/YYYYMMDD_<slug>.md` | the working report | write the text and the card fields by hand; `priorwork` regenerates everything between `<!-- BEGIN priorwork:… -->` and `<!-- END priorwork:… -->` |
| `.priorwork/surveys/YYYYMMDD_<slug>.json` | candidates, decisions and reasons (with their history), the search log, the scope, the depth, the report's language | changed only by `priorwork` (and the VS Code extension) |

- **The version for reading** comes from `./priorwork export <survey>` (`reports/YYYYMMDD_<slug>.html`,
  to open in a browser or print to PDF). It leaves out the markers, empty fields, the template's
  hints and the abstracts (`--with-abstracts` keeps them). `--format docx` (needs pandoc) and
  `--format md` are also available. While cards are unchecked or empty, or `check` reports
  ERRORs, it is marked *Draft* at the top. The output stays out of Git.
- **The comparison matrix** (section 2) is built from the paper cards (section 3). After editing
  cards, run `./priorwork render`.
- **The references** (section 8) are generated from the included papers, with DOIs (no citation
  keys; add papers to Zotero by hand). Included papers that would be cited the same way in the
  text are told apart as 2001a / 2001b, by title (the cards and the matrix use the same labels).
- **The search log** (appendix) records the searches, the counts, the reasons for exclusion and how
  many decisions were revised. A paper's history (e.g. Maybe → Excluded (theory only) → Included)
  shows in `./priorwork list`.
- The card of a paper that is no longer included is kept, with what was written, in the JSON, and
  comes back when the paper is included again.

### Commands

```bash
# Workspace
./priorwork init [DIR] [--lang en|ja]                          # set up a workspace
./priorwork sync [--force|--diff]                              # update AGENTS.md, the skills and ./priorwork
./priorwork upgrade [--to X.Y.Z]                               # update the engine, then sync
./priorwork doctor [--online]                                  # diagnose the setup
./priorwork settings [--stdin] [--import-ssci CSV]             # API keys, Zotero, the SSCI list

# Surveys
./priorwork status [SURVEY]                                    # the list / progress and next steps
./priorwork new "<topic>" --slug <slug> [--depth quick|full] [--question ... --years ... --fields ... --inclusion ... --exclusion ...]
./priorwork scope SURVEY --question "..." [--depth quick|full]  # change the scope
./priorwork list SURVEY [--status candidate maybe] [--abstract]
./priorwork include SURVEY 2 5 7
./priorwork exclude SURVEY 3 --reason "theory only"            # an exclusion needs a reason
./priorwork maybe SURVEY 9          ./priorwork reset SURVEY 9 # maybe / back to candidate
./priorwork add SURVEY <DOI>... [--candidate]                  # register by DOI (included by default)
./priorwork card SURVEY 3 [--set rq="..." evidence=abstract]   # show or fill in a card
./priorwork render SURVEY
./priorwork check SURVEY [--offline]
./priorwork export SURVEY [--format html|docx|md] [-o PATH] [--with-abstracts]
./priorwork fulltext SURVEY <number> [--pdf <path>]
./priorwork zotero [SURVEY] [--refresh]
./priorwork zotero --collections | SURVEY --collection NAME | SURVEY --import | SURVEY --dois

# Finding literature
./priorwork search "<English query>" [--into SURVEY] [--bulk] [--sort citations|relevance|recent|cpy] [--year 2010-2024] [--ssci-only] [--limit N]
./priorwork snowball SURVEY [--direction both|references|citations] [--limit N] [--min-links N]
./priorwork get <DOI>
./priorwork citations <DOI> [--sort cited]      ./priorwork references <DOI> [--sort cited]
./priorwork journal "<journal or ISSN>"
```

`SURVEY` is the file name without the extension, or the slug. Most commands print JSON with
`--json` (for the VS Code extension and scripts).

---

## How it works

### Searching

- **A normal search** is Semantic Scholar's relevance search.
- **`--bulk`** is Semantic Scholar's bulk search: `+` (and), `|` (or), `-` (not) and `"phrases"`,
  most cited first. It finds the classics that keyword search buries.
- The order (`--sort`): `citations`, `relevance`, `recent` or `cpy` (citations per year), always
  with the better SSCI status first.
- When both a working paper and its published version are found, only the published one is kept.

### Which source does what

| Task | Semantic Scholar | OpenAlex |
| :--- | :--- | :--- |
| Search | ✔ | not used (poorer relevance) |
| Verifying details | — | ✔ S2's results are matched by DOI in batches; journal, ISSN, volume and issue come from OpenAlex |
| Getting a paper (`get` / `add`) | ✔ first | for DOIs S2 does not have |
| Citation links (`citations` / `references`) | ✔ `--sort recent` | `--sort cited`, or when S2 lacks them |
| Re-checking DOIs in `snowball` / `check` | — | ✔ |

Semantic Scholar searches well, but its records of classic papers are sometimes broken (the DOI of
another paper or of an SSRN version, missing ISSNs, missing papers). DOIs and ISSNs are therefore
taken from what OpenAlex confirms, and problems are flagged with ⚠️.

| Warning | Meaning |
| :--- | :--- |
| The DOI points to another title | S2's DOI belongs to another paper (a reply, say) |
| The DOI is a working paper / preprint version | S2 names a journal, but the DOI is an SSRN-style version |
| OpenAlex does not know the DOI / No DOI / DOI not verified | a wrong or missing DOI, or it could not be checked |
| May be a book review or comment | a title like "…, by Author", or a single page |

### Chasing citations (snowball)

The references and citing papers of the included papers are collected from OpenAlex and
registered as candidates, ordered by how many included papers each is linked to. With three or
more included papers, only those with at least two links are taken by default.

### Full texts

PDFs are never stored in the workspace. priorwork looks for one in this order and keeps only the
extracted text, in `.priorwork/cache/fulltext/` (outside Git):

1. the file given with `--pdf`
2. a PDF attached in the local Zotero (`zotero.sqlite`, opened read only, matched by DOI)
3. a PDF attached in Zotero found through the Web API (from WebDAV's `<key>.zip` or Zotero File Storage)
4. the text Zotero indexed (no page breaks; a fallback)
5. an open-access PDF

Publishers usually refuse automated downloads, so for papers that are not open access, attach the
PDF in Zotero first.

The list of Zotero items is kept in `.priorwork/cache/zotero/index.json`, and later runs fetch only
what changed. Papers are matched by DOI (including `DOI: ...` in the Extra field), and by title only
when there is no DOI.

### Checks

| Check | Level |
| :--- | :--- |
| Author–year citations in the text and the cards ("Author (year)", "(Author, year; …)") match registered papers | ERROR (unregistered) / WARN (not included) |
| 2001a / 2001b match the references | WARN |
| DOIs in the text are registered | ERROR |
| ⚠️ on included papers; the DOI and title agree in OpenAlex | ERROR |
| The evidence level of each card (unchecked / abstract only / full text checked) and empty fields | WARN |
| The Markdown matches the state file (a forgotten `render`) | WARN |
| Unscreened candidates, non-SSCI included papers, included papers missing from Zotero, citations taken for organisations or table numbers | INFO |

Citations are found with regular expressions, so not every style is caught. Narrative
(`Acemoglu et al. (2001, 2005)`, `Dell (2010, p. 5)`) and parenthetical
(`(e.g., Dell 2010; Acemoglu et al., 2001a)`) citations are.

Organisations and acronyms such as "World Bank (2010)" or "OECD (2019)" are reported as INFO, not
ERROR. Something that is not a citation can be excluded with a comment in the report:

```markdown
<!-- priorwork:ignore-citation Smith (2015) -->
```

### What cannot be registered

Papers in domestic journals (J-STAGE and the like) are often in neither Semantic Scholar nor
OpenAlex, so `priorwork get` / `add` cannot register them. Since the target is international
peer-reviewed journals, they are out of scope for now.

### Other

- **Retries**: HTTP 429 / 5xx / network errors are retried up to five times, waiting 5→10→20→40→60 s (`PRIORWORK_MAX_RETRIES`).
- **Cache**: API responses are kept in `~/.cache/priorwork/` for seven days (`PRIORWORK_CACHE_TTL_DAYS`, `PRIORWORK_NO_CACHE=1`, `--no-cache`).
- **Messages**: `PRIORWORK_LANG=en|ja`, or else the locale.

---

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest          # no network needed
bin/priorwork --help                # run the code of this checkout
```

```text
.
├── priorwork/
│   ├── cli.py                  # the commands (including --json output)
│   ├── i18n.py / lang_ja.py    # messages: English source, Japanese catalogue
│   ├── workspace.py            # a workspace's paths and language
│   ├── scaffold.py             # init / sync / upgrade
│   ├── survey.py               # the state and the generated Markdown
│   ├── api.py                  # Semantic Scholar / OpenAlex
│   ├── ssci.py                 # SSCI status
│   ├── snowball.py             # citation chasing
│   ├── fulltext.py             # full texts (Zotero / open access)
│   ├── zotero.py               # Zotero Web API / WebDAV (read only)
│   ├── check.py                # checks
│   ├── export.py               # the version for reading
│   ├── doctor.py               # diagnosis
│   └── assets/                 # what workspaces receive: AGENTS.md, skills and the report template per language (en/, ja/), env.example
├── vscode-extension/           # the VS Code extension (TypeScript)
├── tests/
└── bin/priorwork               # the development wrapper
```

When you change `AGENTS.md` or a skill, edit both `priorwork/assets/en/` and
`priorwork/assets/ja/`; workspaces receive them through `priorwork sync`.

Bug reports and suggestions are welcome in [Issues](https://github.com/yoshida-kd/priorwork/issues).

## License

MIT
