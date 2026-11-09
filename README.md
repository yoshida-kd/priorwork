# Priorwork

**Hand your literature review to an AI agent, then check it — no terminal needed**

[![tests](https://github.com/yoshida-kd/priorwork/actions/workflows/tests.yml/badge.svg)](https://github.com/yoshida-kd/priorwork/actions/workflows/tests.yml)

[日本語 README](https://github.com/yoshida-kd/priorwork/blob/main/README.ja.md)

Priorwork (as in *prior work*) hands topic-based literature reviews in the social sciences and clinical research to an AI agent (Claude Code, Antigravity and others). Ask in plain words: the agent sets the scope, searches, screens, chases citations, fills in a card for each paper, writes the review, checks it and exports a version for reading. You read it, then check and correct it in the VS Code sidebar.

```
scope → search → screen → chase citations → paper cards → text → check and export
```

## What it does

- **A reason for every decision.** The agent records why it included or excluded each paper, and writes the scope into the report. One key on a paper's page overturns a decision, and the agent never overturns yours.
- **It remembers in the repository.** Candidates, decisions and the search history live in JSON files, so work carries on across conversations.
- **Cards you can check.** Each included paper gets a card written only from its abstract or full text, which says which of the two it was checked against, and with pages.
- **Made-up citations are caught.** Every "Author (year)" in the text must be a registered paper, and each DOI must point to that paper. A paper that has been retracted gives an error.
- **Literature from several sources.** Semantic Scholar and OpenAlex; in a medical survey, PubMed too, with MEDLINE status, cards for the clinical question and effect sizes, and open full texts from PMC.
- **From your own manuscript.** Give it a manuscript, finished or not, and get one report: what to add and where, a check of its citations, the literature it does not mention, comments on the argument. It never rewrites the manuscript.
- **Zotero and Octavo.** Link a Zotero collection to a survey to collect the papers and read your PDFs. Priorwork sends writing to [Octavo](https://github.com/yoshida-kd/octavo) projects with their `.bib` keys.
- **No API keys for AI.** The extension never calls an AI service itself. AI comes only through the agent you already use.

## Install

Install the [VS Code extension](https://marketplace.visualstudio.com/items?itemName=yoshida-kd.priorwork), open an empty folder and press **Create a Workspace** in the Priorwork sidebar. It prepares Python. On Windows and servers, see [Installing Priorwork](https://yoshida-kd.github.io/priorwork/install/).

## Getting started

Tell your agent, in the workspace:

> Do a full review of the literature on how minimum wages affect employment.

Or use **New Survey → Ask your agent to do it** in the sidebar. The agent stops so you can check the scope and collect papers in Zotero; ask it not to stop if you prefer. Then read the report and correct it in the sidebar.

## Guides

- [Quick guide](https://yoshida-kd.github.io/priorwork/quickstart/) — from installing to your first review, in six steps
- [Installing Priorwork](https://yoshida-kd.github.io/priorwork/install/) — on your computer, Windows and servers
- [Guide](https://yoshida-kd.github.io/priorwork/guide/) — using it in VS Code
- [Starting from a manuscript](https://yoshida-kd.github.io/priorwork/manuscripts/) — your own manuscript, and Octavo
- [Reference](https://yoshida-kd.github.io/priorwork/reference/) — every command, for AI agents (also `./priorwork docs`)

## Contributing and license

Issues and pull requests are welcome. See [CONTRIBUTING.md](https://github.com/yoshida-kd/priorwork/blob/main/CONTRIBUTING.md). MIT License.
