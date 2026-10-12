---
name: priorwork-audit
description: >-
  Audits a literature survey written by another AI model: checks each paper card against the full text,
  the direction of every citation in the text, the separation of the literature from the user's own
  hypotheses, mechanical exclusions in screening and the SSCI status; fixes what is wrong and records the
  audit with `./priorwork audit`. Use when asked to audit, review or double-check a survey that a different
  model wrote. Never use it on a survey you wrote yourself.
---

# Audit a survey written by another model

Follow the rules in [AGENTS.md](../../../AGENTS.md). A survey counts as done only once a model other than the one that wrote it has audited it (AGENTS.md, "Audit").

## 0. Make sure you may audit it

```bash
./priorwork audit <survey>        # who wrote it, and the audits so far
```

If "Written by" names you (your model), do not audit it. Tell the user "I wrote this survey, so please ask another model to audit it" and stop. If nothing is recorded, ask the user which model wrote it.

## 1. Mechanical checks

```bash
./priorwork check <survey>
```

Note the ERRORs and the WARNs about cards, synthesis sections, counts and Zotero. Fix them in 2–5, after comparing with the full text.

## 2. Compare the cards with the full text (the most important part)

Do this for every included paper, one at a time.

```bash
./priorwork card <survey> <number>
./priorwork fulltext <survey> <number>    # fetches the full text and prints where its text is
```

- For a card marked "full text checked", open the full text and check: the data, sample size and period; the identification (is it the method the paper actually uses?); the numbers **and direction** of the main findings; the pages given.
- Fix or remove numbers, methods and pages that are not in the full text. If the full text cannot be fetched and the card says "full text checked", lower it to "abstract only".
- Rewrite a card that is not in the language of the report.
- Fix with `./priorwork card <survey> <number> --set …` or by editing the card's fields.

Even when there are many, check them all rather than a sample. If it takes too long, say in your report how far you got and leave the rest to the next audit (then give the range in `--note`).

## 3. Check the text

In each section from the background to "Hypotheses and implications for this study":

- **Direction of citations**: does "X (year) showed …" point the same way as the main findings on that paper's card? If not, fix it.
- **Literature mixed with this study's hypotheses**: is the user's typology, hypothesis or analytical axis written as if it were a consensus of the literature or an established fact? If so, move it to "Hypotheses and implications for this study" and cite which finding of the literature it rests on as Author (year).
- **Counts written by hand**: does a number of included papers disagree with the appendix? If so, delete it.
- Are papers cited that are not included or not registered (`check` ERRORs)?

## 4. Check the screening

```bash
./priorwork list <survey> --status excluded --abstract
```

- Were many papers excluded with the same sentence as the reason (the appendix's "Reasons for exclusion" shows it too)?
- Were papers that bear directly on the question dropped as "off topic"? If so, bring them back as included or maybe with a reason (`./priorwork include <survey> N --reason "Audit: …"`), and fill in the cards of those you include (`priorwork-extract`).
- Never change a decision the user made (the history in `./priorwork list` shows it).

## 5. Check the SSCI status

For included papers marked `✅ SSCI`, check that the ISSN and publisher, not just the title, match the listed journal (different journals can share a title). Use `./priorwork journal "<ISSN>"`.

## 6. Record and report

```bash
./priorwork check <survey>
./priorwork export <survey>
./priorwork audit <survey> --by "<your model name>" --note "<what you checked and fixed, in one line>"
```

In your report, give the problems found by kind (card errors, direction of citations, mixed-in hypotheses, screening, SSCI) with counts and typical examples, and separate what you fixed from what you could not.
