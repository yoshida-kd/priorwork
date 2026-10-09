---
name: priorwork-new
description: >-
  Starts a new social-science literature survey: settles the scope (research question, period, criteria,
  depth), creates reports/YYYYMMDD_<slug>.md with `./priorwork new`, and runs enough searches for the depth.
  Use when a survey on a new topic is needed, or when an existing survey needs more searches.
---

# Start a new survey and search

Follow the rules in [AGENTS.md](../../../AGENTS.md).

## 1. Set the scope

Settle these from the request. For anything the request does not say, decide something sensible from the topic yourself, go on, and say what you decided in your final report. Ask the user only when the topic is too vague to choose search terms (in consultation mode, propose the scope and wait).

- The research question (one sentence)
- The period (e.g. 1990-2025; may be left empty)
- The fields (e.g. public administration, labour economics)
- Inclusion criteria (e.g. empirical studies, international peer-reviewed journals)
- Exclusion criteria (e.g. theory only, working papers)
- An English slug (e.g. `minimum_wage_employment`)
- The depth (`quick` / `full`): decide with the table in AGENTS.md, "Depth".

```bash
./priorwork new "<topic (any language)>" --slug <slug> --depth quick|full --question "..." --years "..." --fields "..." --inclusion "..." --exclusion "..."
```

## 2. Search

First split the topic into subtopics (concepts, populations, methods): 3–6 for full, 1–2 for quick.

For each subtopic, write 2–4 English queries and use both plain and `--bulk` searches. Do not pass `--limit` (the default fits the depth).

```bash
./priorwork search "local government outsourcing staff capacity" --into <survey>
./priorwork search '("contracting out" | outsourcing) + ("local government" | municipal) + (capacity | workforce)' --bulk --into <survey>
```

- The `--bulk` operators are `+` (AND), `|` (OR), `-` (NOT) and `"phrases"`. `AND`/`OR` are turned into them, but too many terms find nothing.
- Rerun a query that found nothing or almost nothing with fewer terms, synonyms, or without `--bulk`.
- Ideas for terms: the concept in English and its synonyms, the names of the main theories (`"transaction cost"`, …), identification strategies (`"difference-in-differences"`), countries and regions.
- If you know a well-known paper, you may register it directly with `./priorwork add <survey> <DOI>` (after checking it with `get`).

While `./priorwork status <survey>` says "Search more", add searches from angles you have not tried yet.

## 3. Next

Go on to screening (`priorwork-screen`). Only in consultation mode, tell the user the number of candidates and the notable papers and wait.
