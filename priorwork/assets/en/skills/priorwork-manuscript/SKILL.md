---
name: priorwork-manuscript
description: >-
  Works from the user's own manuscript in any format (Markdown, Quarto, HTML, Word, PDF): reads it with
  `./priorwork read`, agrees with the user which parts to cover and what to focus on, then searches, screens,
  fills in the cards and writes one report (`./priorwork new --manuscript …`): what the manuscript lacks, what to
  add and where (the author's marks first, whole sections if needed), a check of its citations, literature it does
  not mention, comments on the argument. Use when the user points to their manuscript, finished or not, and asks to
  fill it in, for its sections 1–3, the literature behind it, or advice on it.
---

# Start from a manuscript

Follow the rules in [AGENTS.md](../../../AGENTS.md). The user has a manuscript of their own and wants the literature to support it. **One manuscript gets one survey and one report.** What to write in it depends on the state of the manuscript:

| The manuscript | Put the work in |
| :--- | :--- |
| In progress (missing sections, headings only, thin parts, no citations, the author's marks `[cite]`, `[@?]`, `TODO(priorwork): …`) | what it lacks (section 3), what to add (section 5) |
| The analysis is done, but no introduction, literature review or theory and hypotheses | what to add (section 5): those parts as "write the section" items |
| Finished | the check of its citations (section 6), missing literature (section 7), the argument (section 9) |

Write "Not covered" in a section nobody asked for. **Only read the manuscript; never rewrite it.** Tell the user what should change in the report and in your report to them.

A survey made by an earlier version has a report of another shape (`purpose` in `./priorwork status <survey> --json` is `draft` or `advice`). Carry on with it as its headings and `<!-- What to write: … -->` notes say. To add the rest, make a new survey and register its included papers with `add`.

## 1. Read the manuscript

The manuscript goes in `manuscripts/<paper name>/` in the workspace (see `manuscripts/README.md`). Besides the manuscript, the folder may hold tables, figures and logs of results that are not in it. **Read every file in the folder.**

- If you do not know which manuscript, look in `manuscripts/`: take it if there is one, ask if there are several.
- If it is not in `manuscripts/`, ask the user to put it there (do not copy files from outside on your own).
- Any format will do. Read it as text with `./priorwork read` (Markdown, Quarto (.qmd), LaTeX, HTML (such as Quarto's output), Word (.docx), PDF; for a folder it prints every file in turn, figures by name only).

  ```bash
  ./priorwork read manuscripts/<paper name>
  ./priorwork read manuscripts/<paper name> --out /tmp/<paper name>.txt   # when it is long, write it out and read it in parts
  ```

- When you read it again after the survey is made, add `--for <survey>` (`./priorwork read manuscripts/<paper name> --for <survey>`). That records that you read the manuscript as it is now; when the user later changes it, the next steps of `./priorwork status` say "the manuscript has changed". Then read it again, tell the user what changed, and update what it made stale (the map and the additions, the draft, the advice; and search more if new claims need literature).
- A manuscript in an **Octavo project** (another repository, with `octavo.config.py`) is not copied into `manuscripts/`; point to it where it is (e.g. `../make_or_buy/papers/main`). Besides the manuscript, `./priorwork read` prints the project's results (`results/*.json`), tables, analyses (`.qmd`), the names of its figures, and the literature the manuscript cites (`[@key]` in the `.bib`). Follow "A manuscript in an Octavo project" below too.

## 2. Agree with the user what to make

Once you have read the manuscript, propose the following and **wait for the answer** (whatever the mode; only when the request settles all of it may you go on without waiting, saying in your report how you decided).

- **What to focus on**: from the table above, with your reasons from the state of the manuscript.
- **What to cover**: which parts of the manuscript (e.g. "the literature review in section 2 and the hypotheses in section 3", "the whole paper").
- **The search**: the research question (the manuscript's), fields, period, inclusion and exclusion criteria, depth (default full).

Then make the survey. **Do not make a second survey for the same manuscript**; add to the one you have.

```bash
./priorwork new "<topic>" --slug <slug> --by "<your model name>" --manuscript manuscripts/<paper name> --mode standard|auto|manual --depth full --question "..." --fields "..." --inclusion "..." --exclusion "..."
```

If the manuscript is in an Octavo project, `new` links the project's Zotero collection to the survey (`./priorwork status <survey>` shows "Octavo project").

This agreement is the first stop of the standard mode (the scope). From here follow AGENTS.md, "Modes" (in standard, the next stop is before the cards).

## 3. Summarise the manuscript

Fill in section 1 of the report only from what the manuscript says. Copy estimates exactly from its tables. Give the parts this report covers.

## 4. Work out where literature is needed

- **Section 3**: for each section of the manuscript, its state (written / thin / heading only / missing), the author's marks (at the end of `./priorwork read`) and the plan. The marks are where the author wants literature, so list all of them.
- **Section 4**: the claims to support, with IDs (C1, C2, …). Think of at least these kinds:

| Kind | Where it is used | Example |
| :--- | :--- | :--- |
| Why the problem matters, the puzzle | introduction | "The employment effect of the minimum wage is contested" |
| Streams of research it contributes to (2–4) | literature review | "Estimates from comparing regions" |
| Mechanism, theory | theory and hypotheses | "Under monopsony, employment need not fall" |
| Competing theories and findings | theory and hypotheses, discussion | "In a competitive labour market, employment falls" |
| Precedents for the method or data | data and methods (support) | "Studies with the same identification or data" |

  **For each main result, also state the conflicting finding as a claim** ("C3: X is reported not to raise Y"). Do not collect only literature in support.
- **Section 6**: the main places where the manuscript cites the literature, with IDs (R1, R2, …): where, what it says, the paper cited.
- **Section 7**: for the question, theory, method and results, research streams it does not mention.

## 5. Search and screen

Follow part 2 of `priorwork-new` (searching), `priorwork-screen` (screening) and `priorwork-snowball` (citation chasing). Instead of subtopics, use the claims (C) or the citations (R) from 4.

- Write 2–4 English queries per claim or citation. When looking for conflicting findings, use words for the opposite result too (`"no effect"`, `null`, `negative`, `heterogeneous`, …).
- Put the ID in the reason for each decision (e.g. `--reason "C2 supports: positive effect with the same identification"`, `--reason "R3 cited by the manuscript"`, `--reason "to add: reports a fall in employment"`). Never exclude a paper because it conflicts.
- **Register the papers the manuscript already cites** (check the record with `./priorwork get`, then `./priorwork add <survey> <DOI>`). If the manuscript has a `.bib` (an Octavo project, say), `./priorwork add <survey> --cited` registers every paper it cites as `[@key]` at once (those without a DOI are listed; search for them by title). For `advice`, register them all so that you can check the direction of each citation. Mark those that cannot be registered (domestic journals, say) as "not registered" in the table of section 3.

Standard and manual stop before filling in the cards and show the DOIs to add to Zotero (AGENTS.md, "Modes").

## 6. Fill in the cards

Fill them in as in `priorwork-extract`. Also write the **Role in the manuscript** (`role`).

```bash
./priorwork card <survey> N --set "role=K2, C1 supports"
./priorwork card <survey> N --set "role=R2 cited by the manuscript; wrong direction"
```

- `role`: the IDs of the item in section 5, the claim in section 4 or the citation in section 6, and the relation (supports / conflicts / source of the theory / precedent for the method / background, cited by the manuscript or a candidate to add).
- Fill in the literature columns of section 4 from the cards, as Author (year). If a claim still has no paper, search on that claim. If none turns up, propose weakening or cutting it in section 8 or 9.
- Papers that bear on the manuscript's claims (those cited in section 5, those whose direction you judge in section 6) are checked in the full text whatever the depth.

## 7. Write the report

Follow the `<!-- What to write: … -->` notes. Cite only papers included in the survey, as in the references. Add nothing that is not on the cards.

**Section 5, what to add.** In the manuscript's order, in the **language of the manuscript**:

- The heading is `### K1 kind — section`. The kinds are "write the section" (a missing or heading-only section), "insert" (a paragraph in a thin section), "add a citation" (a claim without one, `[cite]`, `[@?]`: the paper to cite and the sentence with the citation in it).
- Each item has **Where** (the section's heading and the sentence it goes before or after, quoted exactly) and **Why** (the gap, the author's mark, the claim ID), then the text. `./priorwork check` gives a WARN for an item without a place.
- **Fill in the author's marks first.** Each mark gets an item, or a reason in section 3 why not (no literature supports it, out of scope).
- Add only what the literature supports. Do not write the content of the methods or results (data, estimates, interpretation); literature supporting the choice of method is fine. If what you add conflicts with what the manuscript says, give that as the reason.
- When writing whole sections:
  - **Introduction**: why the problem matters and the puzzle → what the literature does not know → this study's question, method, main results and contribution. Keep the results to the summary in section 1.
  - **Literature review**: by research stream, the claims and their evidence; not a list of papers, but what each stream has found and left open, ending with where this study stands.
  - **Theory and hypotheses**: the mechanism and the hypotheses, with the literature behind each. If there are competing theories, what they would predict.

**Do not hide conflicting literature.** Where it conflicts with the manuscript's results, mention it in the text, with the reasons the difference may arise (sample, period, identification) as far as the cards go. **Do not attribute to the literature what it does not say.**

**Section 6, citations.** For each R, compare the card of the cited paper (the **direction** of its main findings, sample, method) with what the manuscript says: fits / wrong direction / overstated / weak evidence. For those that do not fit, say what to change (soften it, use another paper, show the conflicting finding too).

**Section 7, missing literature.** By research stream, where in the manuscript and why, citing included papers. Do not hide findings that conflict with its results.

**Section 8, hypotheses.** For each hypothesis, the literature behind it, the literature that conflicts with it, and how the manuscript deals with that.

**Section 9, the argument.** Comments on how the question, the gap, the hypotheses, the method, the results and the contribution connect. Do not mix what the literature says with the manuscript's claims.

**Section 2, what to do first.** Write it last: the 3–7 most important points, each with where, the problem, what to do and the literature behind it. To suggest a rewritten sentence, show it briefly in the language of the manuscript.

## 8. Check and export

Fix until there are no ERRORs, as in `priorwork-check`, then export.

```bash
./priorwork export <survey> --draft          # reports/<name>.draft.md: section 5 and the references of the papers it cites
./priorwork export <survey>                  # reports/<name>.html: everything
```

`--draft --format docx` makes a Word file (it needs pandoc). If the manuscript is in an Octavo project, use the form under "A manuscript in an Octavo project".

## A manuscript in an Octavo project

- Write the draft with "Author (year)" as for any manuscript. The engine turns it into Octavo's form:

  ```bash
  ./priorwork export <survey> --octavo    # <project>/literature/priorwork/<survey>.md and .json (citations as [@key], no references section)
  ```

  The keys come from the Octavo project's `.bib` (exported from Zotero), matched by DOI. Never make up keys.
- Included papers not in the `.bib` are written as `[@PRIORWORK:<DOI>]`, and their DOIs are listed. Give those DOIs as they are in your report, and tell the user to put them in the Zotero collection (the name under "Octavo project" in `./priorwork status`) and run `octavo bib pull` and then `octavo priorwork resolve` in the Octavo project, which replaces the marks by the `.bib` keys (until then Octavo reports them as missing keys; with Octavo 0.6.6 or older, export again after `octavo bib pull`). If Priorwork may write to Zotero, `./priorwork zotero <survey> --add` puts them in (AGENTS.md, "Zotero").
- `./priorwork check` warns when the survey and the Octavo project use different Zotero collections, and when the draft cites papers not in the `.bib`. If the collections differ, ask the user which one to use.
- What you export goes into the Octavo project's inbox (`literature/priorwork/`). Working it into the manuscript happens on Octavo's side: tell the user to ask the agent in the Octavo project to "work the draft from Priorwork into the manuscript". Never change the Octavo project's other files (settings, `.bib`, manuscript).

- `export --octavo` puts section 5 in the inbox, followed by a part for the author with what you wrote in sections 2 and 6–9 (not text for the manuscript).

## 9. Report

In addition to "4. Report when you are done" in the entry skill `priorwork`, tell the user, naming papers as Author (year):

- the main points of section 2
- what the manuscript lacks, how many items to add and of what kinds, the author's marks you filled in and those you did not, and why
- how many citations are "wrong direction" or "overstated"
- which claims have only supporting literature, which have conflicting literature, and which found none
- the files you exported (the user reads them before moving anything into the manuscript)
- for a manuscript in an Octavo project, the files placed in the inbox and the DOIs missing from the `.bib` (to add to Zotero, then `octavo bib pull`)
