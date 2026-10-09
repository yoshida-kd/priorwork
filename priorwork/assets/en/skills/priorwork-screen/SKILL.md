---
name: priorwork-screen
description: >-
  Screens the candidate papers of a literature survey against its inclusion and exclusion criteria and
  records include/exclude/maybe with a reason for each (`./priorwork include|exclude|maybe`). Decides on its
  own by default; in consultation mode, presents recommendations and waits. Use when a survey has unscreened candidates.
---

# Screen the candidates

Follow the rules in [AGENTS.md](../../../AGENTS.md).

## Steps (default: you are trusted to proceed)

1. Show the candidates with their abstracts.

   ```bash
   ./priorwork status <survey>                 # check the scope (question, inclusion and exclusion criteria)
   ./priorwork list <survey> --status candidate --abstract
   ```

2. Judge each paper against the inclusion and exclusion criteria and record the decision with a reason. You may record several at once.

   ```bash
   ./priorwork include <survey> 2 5 7 --reason "Empirical study of contracting out and municipal staffing"
   ./priorwork exclude <survey> 3 --reason "Theoretical model only"
   ./priorwork maybe <survey> 9 --reason "Identification unclear from the abstract; check the full text"
   ```

   - Write the reason in one line so that it shows which criterion applied. Record papers excluded for the same reason in one command.
   - When the abstract is not enough, use maybe and say in the reason what is unclear. Before filling in the cards, settle each maybe as included or excluded from the full text or `./priorwork get`.
   - When in doubt, lean towards including for full (you can still exclude later) and towards excluding for quick.
   - Working papers, preprints, book reviews and comments are excluded (AGENTS.md, rule 1). For ⚠️ papers, see below.
   - **Never change a decision the user made.** Decide only candidates.

3. Repeat until no candidates are left. Note the numbers included, maybe and excluded, then go on to the next step (`priorwork-snowball` or `priorwork-extract`).

## Consultation mode

When the user wants to go through it together (or `AGENTS.local.md` says so), wait for their answer before recording anything.

1. Present 5–10 papers at a time like this (use the `#` numbers as they are):

   | # | Author (year) | Journal | Recommendation | Reason (one line, against the criteria) |
   | :--- | :--- | :--- | :--- | :--- |

2. Record the user's answer (e.g. "include 2, 5, 7; exclude 3") as given. An exclusion needs a reason.
3. If the user says they screened in the sidebar, reload the list before going on.

## Papers with a ⚠️ about the DOI

For papers where "the DOI points to another title" or "the DOI is a working paper / preprint version", find the published version and register that instead.

```bash
./priorwork search "<title of the paper>" --limit 5
./priorwork get "<DOI of the published version>"   # check that the title, journal and year match
./priorwork add <survey> "<DOI of the published version>"
./priorwork exclude <survey> <old number> --reason "Wrong DOI; replaced by #<new number>"
```

If you cannot confirm the published version, do not include the paper: set it to maybe and mention it in your report.
