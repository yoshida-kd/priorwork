---
name: priorwork-derive
description: >-
  Writes a short text made from a finished survey — a lecture handout, reading notes, a summary of the
  main points — in `reports/<survey>.<name>.md`, with its purpose, length and structure recorded by
  `./priorwork derive`. Cites only included papers from cards checked against the full text, and checks
  each number and the direction of each finding against the card. Use when asked for lecture material,
  notes, a summary or any other short text based on a survey.
---

# Write a short text from a survey

Follow the rules in [AGENTS.md](../../../AGENTS.md). Use this when asked for lecture material, reading notes, a summary of the main points or any other short text based on a survey. It goes in a file of its own, apart from the survey's report (`reports/<survey>.md`) and the manuscript draft (`--draft`).

## 1. Decide what to make

Take these from the request. When it does not say, decide and say so in your report (in the manual mode, ask).

- **Name**: lower-case letters, digits, `-` and `_` (e.g. `lecture`, `reading-notes`). The file is `reports/<survey>.<name>.md`.
- **Purpose**: who uses it for what (e.g. "a handout for an undergraduate public administration class, 90 minutes").
- **Length**: about how long (characters in Japanese, words in English), and whether citations in parentheses ("(Dell 2010)") count. Unless told, they don't.
- **Structure**: the section headings (e.g. "background; findings; open questions").

```bash
./priorwork derive <survey> <name> --purpose "<purpose>" --length 2000 --structure "background; findings; open questions" [--count-citations]
./priorwork derive <survey>       # the survey's derived documents
```

For a name that already exists, only the record (purpose, length, …) changes; the text you wrote stays.

## 2. Write it

- The top of the file (purpose, length) and the end (references) are managed blocks that `./priorwork` rewrites. Write between them.
- **Cite from the included papers whose cards were checked against the full text.** Don't cite a paper whose card is abstract only, or fetch its full text and fill in the card first (`priorwork-extract`).
- **Check every number and the direction of every finding against the card's findings.** Write numbers as the card has them (don't round or change units). Check that "raises / does not raise", "more / fewer" agrees with the card.
- Cite papers as author (year), as the report does (with the same a/b as its references).
- **Don't mix the literature with the user's own framework and hypotheses** (rule 2 in AGENTS.md).
- Don't write counts of included papers by hand.
- Stay near the target length (`check` says so beyond 15%).

## 3. Check it and write the version for reading

```bash
./priorwork check <survey>                       # also checks citations, cards, numbers and length of derived documents
./priorwork export <survey> --derived <name>     # reports/<survey>.<name>.html (--format docx for Word)
```

What `check` reports for derived documents:

- ERROR: a citation that is not an included paper of the survey
- WARN: a citation from a card not checked against the full text; a number in a citing sentence that is not in the card
- INFO: the length is off the target; no text yet

Fix the ERRORs before exporting. For a WARN about a number, check the card against the full text to see which is right, and fix the text or the card.

## 4. Report

Say which file you wrote and what it is (purpose, length, structure), what you decided yourself, how many papers it cites, the WARNs left, and how to read it (AGENTS.md, "Showing the report"; the HTML is `reports/<survey>.<name>.html`). With Git, the file goes in with `git add reports/<survey>.*`.
