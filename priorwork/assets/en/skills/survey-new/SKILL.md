---
name: survey-new
description: >-
  Starts a new social-science literature survey: agrees on the scope with the user, creates
  reports/YYYYMMDD_<slug>.md and .priorwork/surveys/YYYYMMDD_<slug>.json with `./priorwork new`, and runs the first searches.
  Use when the user wants to begin a survey or literature review on a new topic.
---

# Start a new survey

Follow the rules in [AGENTS.md](../../../AGENTS.md).

## 1. Agree on the scope with the user (stop here once)

Propose the following, as far as the user's request allows, and ask the user to confirm.

- The research question (one sentence)
- The period (e.g. 1990-2025)
- The fields (e.g. labour economics, sociology)
- Inclusion criteria (e.g. empirical studies with causal identification, international peer-reviewed journals)
- Exclusion criteria (e.g. theory only, simulations only, working papers)
- An English slug (e.g. `minimum_wage_employment`)
- The depth (`quick` / `full`). Recommend one from how broad the topic is and let the user decide.

  | | quick | full |
  | :--- | :--- | :--- |
  | Suits | a narrow topic, or just an overview | a broad topic with several subtopics, or when coverage matters |
  | Searches | one or two queries, `--ssci-only` | several queries per subtopic |
  | Included papers | about 20 (not a limit) | no limit |
  | Citation chasing | optional | yes |
  | Cards | abstracts are fine | core papers checked in the full text |
  | Text | an overview and the matrix | background, theories, debates and research gaps |

  The depth only changes how far to go; the rules in AGENTS.md and `./priorwork check` apply the same way.
  When in doubt, start with quick. It can be switched later with `./priorwork scope <survey> --depth full`.

Once agreed, create the survey.

```bash
./priorwork new "<topic>" --slug <slug> --depth quick|full --question "..." --years "..." --fields "..." --inclusion "..." --exclusion "..."
```

## 2. The first searches

- Queries are always in English. Try synonyms and rephrasings (quick: one or two queries; full: two to four or more per subtopic).
- Combine the normal search (by relevance) with `--bulk` (boolean operators, sorted by citations; good at finding the classics).

```bash
./priorwork search "<English query>" --into <survey> --limit 10
./priorwork search '"minimum wage" + (employment | "job loss")' --bulk --into <survey> --limit 10
```

Query ideas: the English terms for the concept, typical identification strategies (`"difference-in-differences"` and so on), the countries or regions studied.

## 3. Report to the user and stop

- Give the number of candidates registered and point out notable papers (highly cited ones, ones with ⚠️).
- Ask whether to move on to screening (`/survey-screen`) or to search more. Mention that the user can also screen in the Priorwork sidebar in VS Code.
