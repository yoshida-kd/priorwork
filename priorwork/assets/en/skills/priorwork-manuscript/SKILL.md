---
name: priorwork-manuscript
description: >-
  Works from the user's own manuscript in any format (Markdown, Quarto, HTML, Word, PDF): reads it with
  `./priorwork read`, agrees with the user what to make (a draft of its introduction, literature review and
  theory and hypotheses; advice on missing literature, the direction of its citations and the argument; or
  both as separate reports) and which parts to cover, then searches, screens, fills in the cards and writes
  each report (`./priorwork new --manuscript … --purpose draft|advice`). Use when the user points to their
  manuscript, finished or not, and asks for its sections 1–3, the literature behind it, or advice on it.
---

# Start from a manuscript (a draft of sections 1–3, advice on it)

Follow the rules in [AGENTS.md](../../../AGENTS.md). The user has a manuscript of their own and wants the literature behind it. There are two kinds of report, and one manuscript may get both as separate reports.

| Purpose (`--purpose`) | Suits | The report |
| :--- | :--- | :--- |
| `draft` (a draft of sections 1–3) | a manuscript with the data, methods and results written, but not yet its introduction, literature review or theory and hypotheses | claims to back with literature, cards, a draft to paste into the manuscript (`export --draft`), a check that hypotheses were not fitted after the results |
| `advice` (advice on the manuscript) | a finished or unfinished paper | a summary of the advice, a check of its citations (direction, overstatement), missing literature, comments on the argument, cards |

**Only read the manuscript; never rewrite it.** Put what should change in the report and in your report to the user.

## 1. Read the manuscript

The manuscript goes in `manuscripts/<paper name>/` in the workspace (see `manuscripts/README.md`). Besides the manuscript, the folder may hold tables, figures and logs of results that are not in it. **Read every file in the folder.**

- If you do not know which manuscript, look in `manuscripts/`: take it if there is one, ask if there are several.
- If it is not in `manuscripts/`, ask the user to put it there (do not copy files from outside on your own).
- Any format will do. Read it as text with `./priorwork read` (Markdown, Quarto (.qmd), LaTeX, HTML (such as Quarto's output), Word (.docx), PDF; for a folder it prints every file in turn, figures by name only).

  ```bash
  ./priorwork read manuscripts/<paper name>
  ./priorwork read manuscripts/<paper name> --out /tmp/<paper name>.txt   # when it is long, write it out and read it in parts
  ```

- A manuscript in an **Octavo project** (another repository, with `octavo.config.py`) is not copied into `manuscripts/`; point to it where it is (e.g. `../make_or_buy/papers/main`). Besides the manuscript, `./priorwork read` prints the project's results (`results/*.json`), tables, analyses (`.qmd`), the names of its figures, and the literature the manuscript cites (`[@key]` in the `.bib`). Follow "A manuscript in an Octavo project" below too.

## 2. Agree with the user what to make

Once you have read it, propose the following and **wait for the user's answer** (whatever the mode; only when the request already settles the purpose, the parts and the number of reports may you go on without waiting, saying in your report how you decided).

- **Purpose**: `draft`, `advice`, or both (as separate reports). Recommend one from the state of the manuscript, with your reasons.
- **Parts**: which parts of the manuscript to cover (e.g. "the literature review in section 2 and the hypotheses in section 3", "the whole paper").
- **Scope of the searches**: the research question (the manuscript's), fields, period, inclusion and exclusion criteria, depth (full by default).
- **How many reports, in which order**: if both, which first (the papers included in the first survey can be carried into the later one with `add`).

With the answer, make one survey per report, each with its own slug (e.g. `make_or_buy_draft`, `make_or_buy_advice`).

```bash
./priorwork new "<topic>" --slug <slug> --by "<your model name>" --manuscript manuscripts/<paper name> --purpose draft|advice --mode standard|auto|manual --depth full --question "..." --fields "..." --inclusion "..." --exclusion "..."
```

When the manuscript is in an Octavo project, `new` links the survey to the project's Zotero collection (`./priorwork status <survey>` shows "Octavo project").

For the second survey, first register the relevant included papers of the first with `./priorwork add <second> <DOI>...`, then search for what is missing.

This conversation is the first stop of the standard mode (the scope). From here on, follow AGENTS.md, "Modes" (in standard, the next stop is before the cards).

## 3. Summarise the manuscript

Fill in section 1, "The manuscript in brief", with only what the manuscript says. Copy estimates exactly as in its tables. For `advice`, put the parts agreed in 2 under "What the advice covers".

## 4. Work out where literature is needed

**`draft`**: in the table of section 2, list the claims that need literature, each with an ID (C1, C2, …). Consider at least these kinds:

| Kind | Where in the manuscript | Example |
| :--- | :--- | :--- |
| Why the problem matters, the puzzle | Introduction | "The employment effect of minimum wages is contested in policy" |
| Strands of research it contributes to (2–4) | Literature review | "The line of estimates from cross-border comparisons" |
| Mechanism, theory | Theory and hypotheses | "Under monopsony, employment need not fall" |
| Competing theories and findings | Theory and hypotheses, discussion | "In a competitive labour market, employment falls" |
| Precedents for the method or data | Data and methods (support) | "Studies with the same identification or the same data" |

**For each main result, also set up the conflicting findings as a claim** ("C3: some report that X does not raise Y"). Do not gather only supporting literature.

**`advice`**: in the table of section 3, list the main places where the manuscript cites the literature, each with an ID (R1, R2, …): where, what the manuscript says, and the papers cited. Also ask, for its question, theory, methods and results, whether a strand of research is missing; these are candidates for section 4.

## 5. Search and screen

Follow part 2 of `priorwork-new` (searching), `priorwork-screen` (screening) and `priorwork-snowball` (citation chasing). Instead of subtopics, use the claims (C) or the citations (R) from 4.

- Write 2–4 English queries per claim or citation. When looking for conflicting findings, use words for the opposite result too (`"no effect"`, `null`, `negative`, `heterogeneous`, …).
- Put the ID in the reason for each decision (e.g. `--reason "C2 supports: positive effect with the same identification"`, `--reason "R3 cited by the manuscript"`, `--reason "to add: reports a fall in employment"`). Never exclude a paper because it conflicts.
- **Register the papers the manuscript already cites** (check the record with `./priorwork get`, then `./priorwork add <survey> <DOI>`). If the manuscript has a `.bib` (an Octavo project, say), `./priorwork add <survey> --cited` registers every paper it cites as `[@key]` at once (those without a DOI are listed; search for them by title). For `advice`, register them all so that you can check the direction of each citation. Mark those that cannot be registered (domestic journals, say) as "not registered" in the table of section 3.

Standard and manual stop before filling in the cards and show the DOIs to add to Zotero (AGENTS.md, "Modes").

## 6. Fill in the cards

Fill them in as in `priorwork-extract`. Also fill in **Role in the manuscript** (`role`):

```bash
./priorwork card <survey> N --set "role=C2 supports; method precedent"       # draft
./priorwork card <survey> N --set "role=R2 cited; opposite direction"        # advice
```

- `draft`: the IDs of the claims in section 2 and how the paper bears on them (supports / conflicts / source of theory / method precedent / background). Then fill in the "Supporting" and "Conflicting or qualifying" columns of the table in section 2 from the cards, as Author (year). If a claim is left with no literature, search more for it. If nothing turns up, propose in section 6 to soften or drop the claim.
- `advice`: the ID in section 3, whether the manuscript cites the paper or it is one to add, and what it means for the manuscript (supports / conflicts / source of theory / method precedent / background).
- Check the papers that carry the manuscript's claims (those cited in the `draft`, and those whose citation you judge in `advice`) against the full text, whatever the depth ("full text checked").

## 7a. Write the draft (`draft`)

In section 5 of the report (after `<!-- priorwork:draft -->`), write text that can go straight into the manuscript, **in the language of the manuscript** (the headings too, if you like; `###` subheadings become `##` when exported).

- **Introduction**: why the problem matters and the puzzle → what the literature has not settled → this study's question, methods, main results and contribution. Keep the results within the summary in section 1.
- **Literature review**: for each strand in section 2, sum up the claims and the evidence. Do not list papers; say what each strand has established and what is left, and end with where this study stands.
- **Theory and hypotheses**: derive the hypotheses from the mechanisms. Give the literature behind each hypothesis. If there is a competing theory, say what it predicts too.

Keep to these:

- Cite only papers included in the survey, written as in the references. Add nothing that is not on the cards.
- **Do not fit hypotheses after the fact.** Only hypotheses that follow naturally from the literature are hypotheses. Do not write unexpected or fragile results as if the literature had predicted them. Propose in section 6 to treat such results as exploratory findings, and leave it to the user.
- **Do not hide conflicting literature.** Discuss literature that conflicts with the manuscript's results in the literature review or the hypotheses, with the reasons the results may differ (setting, period, identification) as far as the cards say.

In section 6 (where the hypotheses come from), write the papers behind each hypothesis, what was added or changed after seeing the results, which results to treat as exploratory, and how conflicting literature is handled. This is a record for the user to decide on; it is not exported with the draft.

## 7b. Write the advice (`advice`)

Write in the language of the report, following the `<!-- What to write: … -->` under each heading.

- **Section 3, the citations**: for each R, compare the card of the cited paper (the **direction** of its main finding, its setting and method) with what the manuscript says, and give a verdict (fits / opposite direction / overstated / weak support). For those that do not fit, say where and how to change the manuscript (soften the wording, cite another paper, show the conflicting findings too).
- **Section 4, missing literature**: for each strand, where in the manuscript and why to cite it, citing included papers as Author (year). Do not hide findings that conflict with the manuscript's results.
- **Section 5, the argument**: comments on how the question, the gap in the literature, the hypotheses, the methods, the results and the contribution hang together. Keep what the literature shows apart from the manuscript's own claims (the authors' hypotheses and interpretations).
- **Section 2, the summary**: write it last. From sections 3–5, the 3–7 most important things to fix, most important first (where, the problem, the suggested fix, the papers behind it).

Cite only papers included in the survey. When you suggest new wording for the manuscript, give it briefly, in the language of the manuscript.

## 8. Check and export

Fix until there are no ERRORs as in `priorwork-check`, then export.

```bash
./priorwork export <survey> --draft          # draft: reports/<name>.draft.md (the draft and the references it cites)
./priorwork export <survey>                  # reports/<name>.html (the whole report)
```

`--draft --format docx` makes a Word file (needs pandoc). For a manuscript in an Octavo project, export it as in "A manuscript in an Octavo project" below.

## A manuscript in an Octavo project

- Write the draft with "Author (year)" as for any manuscript. The engine turns it into Octavo's form:

  ```bash
  ./priorwork export <survey> --octavo    # reports/<name>.<project>.octavo.md (citations as [@key], no references section)
  ```

  The keys come from the Octavo project's `.bib` (exported from Zotero), matched by DOI. Never make up keys.
- Included papers not in the `.bib` are written as `[@PRIORWORK:…]`, and their DOIs are listed. Give those DOIs as they are in your report, and tell the user to put them in the Zotero collection (the name under "Octavo project" in `./priorwork status`), run `octavo bib pull` in the Octavo project, and export again (Octavo reports `[@PRIORWORK:…]` as missing keys).
- `./priorwork check` warns when the survey and the Octavo project use different Zotero collections, and when the draft cites papers not in the `.bib`. If the collections differ, ask the user which one to use.
- The user reads the `.octavo.md` and moves it into the Octavo manuscript (`paper.md`). Never change the Octavo project's files.

## 9. Report

Besides "4. When it is done, report" in the entry skill `priorwork`, say the following, naming papers as Author (year):

- for a manuscript in an Octavo project, the `.octavo.md` file and the DOIs of the papers not in the `.bib` (to add to Zotero before exporting again)
- `draft`: the claims in section 2 and their literature (claims with only supporting literature, claims with conflicting literature, claims with none found), what the user should decide from the check in section 6, and the draft file (`reports/<name>.draft.md`; the user reads and edits it before moving it into the manuscript)
- `advice`: the main points of the summary (section 2), and how many citations were judged "opposite direction" or "overstated"
- when one manuscript got several reports, the name of each, and what is not made yet
