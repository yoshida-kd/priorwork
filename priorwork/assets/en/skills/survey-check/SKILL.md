---
name: survey-check
description: >-
  Validates a literature survey with `./priorwork check` (unregistered author-year citations, DOIs that
  point to other papers, unfilled cards, stale matrix) and fixes the reported problems.
  Use after editing a survey and before telling the user that a section or the survey is done.
---

# Check the survey and fix it

Follow the rules in [AGENTS.md](../../../AGENTS.md).

## Steps

1. Check it.

   ```bash
   ./priorwork check <survey>
   ```

2. Deal with each finding.

   | Finding | What to do |
   | :--- | :--- |
   | A citation "X (year)" in the text has no registered paper | Confirm it exists and get its details with `./priorwork search` / `./priorwork get`, then register it with `./priorwork add <survey> <DOI>`. If it cannot be found, delete the statement or mark it "citation needed" and tell the user |
   | A DOI in the text is not registered | As above |
   | A citation matches several included papers / no paper is 2001a | Change the citation in the text to match 2001a / 2001b as written in the references (section 8) |
   | Citations not checked as organisations or table numbers (INFO) | If one is a paper, register it as above. Reports and statistics can stay |
   | Something that is not a citation is taken for one | Put `<!-- priorwork:ignore-citation Author (year) -->` next to it. Never use this to hide a citation of a real paper |
   | ⚠️ The DOI points to another title / a working paper version | Replace it as in "Including a paper whose DOI needs checking" in `/survey-screen` |
   | The evidence is unchecked / fields are empty | Fill them in as in `/survey-extract` |
   | The Markdown does not match the state file | `./priorwork render <survey>` |
   | Managed blocks are missing | Restore the lost `<!-- BEGIN priorwork:… -->` / `<!-- END priorwork:… -->` from the git history or elsewhere |

3. Repeat 1 and 2 until there are no ERRORs. Tell the user about the WARNs and INFOs that remain.

**Never tell the user it is done while ERRORs remain.**

## 4. When there are no ERRORs

Write the version for reading and ask the user to look at it.

```bash
./priorwork export <survey>
```

If it is marked "Draft" at the top, tell the user why (unchecked cards, empty sections, …) and do not call it done.
