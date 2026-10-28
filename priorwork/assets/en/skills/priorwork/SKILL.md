---
name: priorwork
description: >-
  The entry point of Priorwork. Makes or continues a social-science literature survey end to end with
  `./priorwork` (scope, searches, screening, citation chasing, paper cards, text, check, export), stopping
  for the user where its mode says (standard: after the scope and before the cards). Use whenever the user asks, in any words or language, for a literature survey,
  literature review or prior work on a topic, for the literature behind their own manuscript, or to
  continue, finish or improve an existing survey.
---

# Make or continue a survey (entry point)

Follow the rules in [AGENTS.md](../../../AGENTS.md). The user asks without naming a skill, so tell from their words which of these it is:

- A new topic ("review the literature on X") → from 1
- From their own manuscript ("the analysis is done; write the introduction, literature review and hypotheses", "shore up the literature of this paper", "what literature is this manuscript missing?", "check how it cites the literature") → the skill `priorwork-manuscript`. The same when continuing a survey made from a manuscript (`./priorwork status <survey>` shows "Manuscript:")
- More of an existing survey ("carry on", "finish it") → from 2. If you had stopped at a stop of the mode, this is the user's signal that they are done (before the cards, record `./priorwork scope <survey> --go-on` first)
- One part only ("search more", "fill in the cards", "check it") → just the skill of that step
- An audit ("audit this survey", "check it as another model") → the skill `priorwork-audit`. Only when asked. If you wrote the survey yourself, suggest asking another model

Choose the mode (standard, full auto, manual) as in AGENTS.md, "Modes". If nothing says otherwise, standard: stop once the scope is set, and before filling in the cards.

## 1. A new survey

Check with `./priorwork status` that there is no survey on the same topic yet. If there is none, set the scope and create it as in `priorwork-new` (record the mode with `--mode`). In standard and manual, show the scope and stop here; in full auto, go on to the searches.

## 2. Look at the state, then take the next step

```bash
./priorwork status <survey>
```

Work through the next steps from the top. The usual order:

1. **Search** (`priorwork-new`, part 2): while it says "Search more", add searches on other subtopics.
2. **Screen** (`priorwork-screen`): sort every candidate into included, excluded or maybe.
3. **Chase citations** (`priorwork-snowball`): always for full. If new candidates appear, go back to 2.
4. **Zotero** (standard and manual stop here): when Priorwork may write to Zotero (the next step is `zotero <survey> --add`), show the list from `--add --dry-run` and add with `--add` once the user agrees; otherwise show the DOIs from `./priorwork zotero <survey> --dois` as they are. Then wait for the user to collect the papers and their PDFs in Zotero and ask you to go on (AGENTS.md, "Modes" and "Zotero"). When asked to go on, record `./priorwork scope <survey> --go-on`. Full auto does not stop: add with `--add` if Priorwork may write, and give the number not in Zotero in the final report.
5. **Fill in the cards** (`priorwork-extract`): every included paper.
6. **Write the text**: 3 below.
7. **Check and export** (`priorwork-check`): fix until there are no ERRORs, then write the HTML.

Look at `./priorwork status <survey>` again after each step ("Stop here and wait for the user" marks the stop of standard). In manual, show the results and stop after each step. This is long work, so at the end of a step you may tell the user where you are in one line (except at the stops, do not wait for an answer).

## 3. Write the text

For a survey made from a manuscript, write as in `priorwork-manuscript`. Otherwise, write these sections of the report from the cards (take the numbers from the report's headings; older reports number and order them differently).

| Section | What to write |
| :--- | :--- |
| Background and central questions | why the topic matters and which questions the review addresses |
| Theoretical traditions | the theories in the literature, their claims and mechanisms |
| Methods and causal identification over time | how identification, data and external validity changed |
| Consensus and open debates | what is agreed and where results diverge |
| Gaps in the literature | questions the literature has not answered yet |
| Hypotheses and implications for this study | only here, the framework and working hypotheses of this study (the user's) |

- Follow the `<!-- What to write: … -->` under each heading. Do not delete the template's headings or sections.
- The four sections on traditions, methods, debates and gaps hold **only what the literature found**, citing included papers as Author (year) for each claim (the sections with `<!-- priorwork:synthesis -->`; `check` gives a WARN when one cites nothing).
- Write the user's typology, hypotheses or own analytical axes only in "Hypotheses and implications for this study", never as "the literature holds that …". When drawing on the literature there, cite which finding it rests on as Author (year).
- Cite only papers included in the survey. Write author (year) as in the references section.
- Do not add anything that is not on the cards (estimates, periods, …). Each time you cite, check that **the direction of the finding** matches the card's main findings.
- Do not write the number of included papers or other counts by hand (the appendix has them).
- For quick, the sections from traditions to gaps can be a short overview. For full, cover the debates and the gaps in the research.

## 4. When it is done, report

After `priorwork-check` and the export, say briefly (refer to papers as Author (year), never by number alone):

- the number of queries, candidates and included papers, and the main reasons for exclusion
- what in the scope (question, period, criteria, depth) you decided yourself because the request did not say
- the WARNs left and why it is a "Draft" (if it is)
- how many included papers are not in Zotero yet (show the DOIs from `./priorwork zotero <survey> --dois` as they are; do not drop papers whose full text you could get yourself). If you added them with `--add`: which items were made new and which were already in the library, and that the user should get the PDFs in Zotero
- how to view the report (AGENTS.md, "Showing the report")
- that decisions and cards corrected in the sidebar will be followed in the next round

Use Git as in AGENTS.md, "Git": commit and push on the branch named after the survey at each step, and once the report is exported, open a pull request (or update the open one by pushing). Give its URL in your report. The user merges.
