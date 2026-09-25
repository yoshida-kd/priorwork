---
name: survey-screen
description: >-
  Screens candidate papers of a literature survey together with the user: presents candidates in
  small numbered batches with a recommendation, then records include/exclude/maybe decisions with
  `./priorwork include|exclude|maybe`. Use when a survey has unscreened candidates.
---

# Screen the candidates

Follow the rules in [AGENTS.md](../../../AGENTS.md). **The user decides.** The agent only gives a recommendation and its reason.

## Steps

1. List the candidates with their abstracts.

   ```bash
   ./priorwork list <survey> --status candidate maybe --abstract
   ```

2. Present them in batches of 5 to 10 (about 10 at a time for `quick`, around 5 for `full`) in this form, using the `#` numbers as they are.

   | # | Author (year) | Journal | Recommendation | Reason (one line, against the inclusion and exclusion criteria) |
   | :--- | :--- | :--- | :--- | :--- |

   - Recommend "include / exclude / maybe". When the abstract does not settle it, say "maybe" and write what is unclear.
   - Always mention a ⚠️ (DOI to verify, possibly a book review, …).

3. Record the user's answer (e.g. "include 2, 5, 7; exclude 3") as given. An exclusion needs a reason.

   ```bash
   ./priorwork include <survey> 2 5 7
   ./priorwork exclude <survey> 3 --reason "theory only"
   ./priorwork maybe <survey> 9 --reason "check the identification in the full text"
   ```

4. Repeat 2 and 3 until no candidates are left or the user stops.

The user may also screen in the Priorwork sidebar in VS Code. When the user says so, reload the list with step 1 before continuing.

## Including a paper whose DOI needs checking (⚠️)

For papers where "the DOI points to another title" or "the DOI is a working paper / preprint version", find the published version and register that instead.

```bash
./priorwork search "<paper title>" --limit 5
./priorwork get "<DOI of the published version>"    # check that the title, journal and year match
./priorwork add <survey> "<DOI of the published version>"
./priorwork exclude <survey> <old number> --reason "wrong DOI; replaced by #<new number>"
```

If it cannot be confirmed, do not include it: mark it "maybe" and tell the user.

## When done

Give the number of included papers and ask whether to chase citations for missed papers (`/survey-snowball`) or to fill in the cards (`/survey-extract`).
