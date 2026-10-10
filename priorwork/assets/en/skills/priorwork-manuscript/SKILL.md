---
name: priorwork-manuscript
description: >-
  Backs up a manuscript whose analysis is done: reads its data, methods and results, works out which claims
  need literature, searches and screens for them (including conflicting findings), and drafts the
  manuscript's introduction, literature review and theory and hypotheses, then exports the draft with
  `./priorwork export --draft`. Use when the user has a paper or draft with the analysis written and asks for
  its introduction, literature review, hypotheses or the literature behind it.
---

# Write sections 1–3 of a manuscript whose analysis is done

Follow the rules in [AGENTS.md](../../../AGENTS.md). The user has a manuscript with the data and methods and the analysis written, and wants the literature behind it and the manuscript's sections 1–3 (introduction, literature review, theory and hypotheses). By default, carry on to the end without stopping.

## 1. Read the manuscript and create the survey

If you do not know where the manuscript is, ask (have it put inside the workspace, e.g. `manuscript/paper.md`; .docx, .tex and .pdf are fine too; if you cannot read the format, ask for a text version). Read it and decide:

- the topic (the title or the research question), an English slug and the depth (full by default)
- the scope: the research question is the manuscript's; set the period, fields and criteria to suit its field

```bash
./priorwork new "<topic>" --slug <slug> --manuscript <path of the manuscript> --depth full --question "..." --fields "..." --inclusion "..." --exclusion "..."
```

Fill in section 1 of the report, "The manuscript in brief", with only what the manuscript says (research question, Y, X, data, identification, main results, unexpected results). Copy estimates exactly as they are in the manuscript's tables.

## 2. List the claims to back with the literature

In the table in section 2 of the report, list the claims that need literature, with IDs (C1, C2, …). Consider at least these kinds:

| Kind | Where in the manuscript | Example |
| :--- | :--- | :--- |
| Why it matters, the puzzle | Introduction | "The employment effect of minimum wages is a policy controversy" |
| Lines of research it contributes to (2–4) | Literature review | "Estimates from cross-border comparisons" |
| Mechanisms and theory | Theory and hypotheses | "Under monopsony, employment need not fall" |
| Rival theories and findings | Theory and hypotheses, discussion | "In a competitive labour market, employment falls" |
| Precedents for the methods and data | Data and methods (backing) | "Studies with the same identification or data" |

**For each main result, also make a claim for the findings that conflict with it** (e.g. "C3: some studies report that X does not raise Y"). Do not gather only supporting literature.

## 3. Search and screen claim by claim

Proceed as in `priorwork-new` part 2 (search), `priorwork-screen` (screening) and `priorwork-snowball` (citation chasing), with the claims in section 2 as the subtopics.

- Write 2–4 English queries per claim. For claims about conflicting findings, also use words for the opposite result (`"no effect"`, `null`, `negative`, `heterogeneous`, …).
- Put the claim's ID in the reason (e.g. `--reason "C2 supports: positive effect with the same identification"`, `--reason "C3 conflicts: reports a fall in employment"`). Do not exclude a paper because it conflicts.
- Register the papers the manuscript already cites with `./priorwork add <survey> <DOI>` (check the details with `get` first).

## 4. Fill in the cards

Fill them in as in `priorwork-extract`. Also write the **Role in the manuscript** (`role`): the IDs of the claims in section 2 and how the paper bears on them (supports / conflicts / source of theory / method precedent / background).

```bash
./priorwork card <survey> N --set "role=C2 supports; method precedent"
```

Then fill the "Supporting literature" and "Conflicting or qualifying literature" columns of the table in section 2 with author (year), as the cards say. If a claim is left with no literature, search more for it. If there is still none, propose in section 6 to weaken or drop the claim.

## 5. Write the draft

In section 5 of the report (after `<!-- priorwork:draft -->`), write text that can go straight into the manuscript, **in the language of the manuscript** (the headings too, if you like; `###` subheadings become `##` when exported).

- **Introduction**: why it matters and the puzzle → what the literature does not know → this study's question, methods, main results and contribution. Keep the results within the summary in section 1.
- **Literature review**: for each line of research in section 2, give the claims and the evidence. Do not list papers one by one; say what each line has found and what is left, and end with where this study stands.
- **Theory and hypotheses**: derive the hypotheses from the mechanisms. Give the literature behind each hypothesis. If there is a rival theory, say what it predicts too.

Keep to these:

- Cite only papers included in the survey. Write author (year) as in the references. Do not add anything that is not on the cards.
- **Do not write hypotheses after the fact.** Make hypotheses only of what follows naturally from the literature. Do not write unexpected or fragile results as if the literature had predicted them. Propose treating such results as exploratory findings in section 6, and leave the decision to the user.
- **Do not hide conflicting literature.** Mention papers that conflict with the manuscript's results in the literature review or the hypotheses, with the reasons the results may differ (units, period, identification), as far as the cards say.
- Do not rewrite sections 4 and 5 of the manuscript. If you notice something to fix there, say so in the report.

In section 6 (where the hypotheses come from), write the literature behind each hypothesis, what was added or changed after seeing the results, the results treated as exploratory, and how the conflicting literature is handled. This is a record for the user to judge; it is not part of the exported draft.

## 6. Check and export

Fix the ERRORs as in `priorwork-check`, then export the draft and the version for reading.

```bash
./priorwork export <survey> --draft          # reports/<name>.draft.md (the draft and the references it cites)
./priorwork export <survey>                  # reports/<name>.html (everything, with the claims and the cards)
```

`--draft --format docx` writes Word (needs pandoc).

## 7. Report

Besides "4. When it is done, report" in the entry skill `priorwork`, say:

- the claims in section 2 and how the literature lines up (claims with only supporting literature, claims with conflicting literature, claims with none found)
- what the user should decide from section 6 (results proposed as exploratory, how the conflicting literature is handled)
- the draft file (`reports/<name>.draft.md`): the user reads and edits it before moving it into the manuscript
