---
name: priorwork-check
description: >-
  Validates a literature survey with `./priorwork check` (unregistered author-year citations, DOIs that
  point to other papers, unfilled cards, stale matrix), fixes the reported problems and exports the HTML
  for reading. Use after editing a survey and before telling the user that a section or the survey is done.
---

# Check, fix and export the survey

Follow the rules in [AGENTS.md](../../../AGENTS.md).

## Steps

1. Check it.

   ```bash
   ./priorwork check <survey>
   ```

2. Deal with each finding.

   | Finding | What to do |
   | :--- | :--- |
   | A citation "X (year)" in the text is not registered | Confirm that it exists and get its details with `./priorwork search` / `./priorwork get`, then register it with `./priorwork add <survey> <DOI>`. If you cannot find it, delete the statement or mark it "citation needed" and mention it in your report |
   | A DOI in the text is not registered | Same as above |
   | A citation matches several included papers / no paper matches 2001a | Make the citation in the text match the 2001a / 2001b labels in the references (section 8) |
   | A citation taken for an organisation or a figure number and not checked (INFO) | If it is a paper, register it as above. Reports, statistics and the like can stay |
   | Text that is not a citation is taken for one | Write `<!-- priorwork:ignore-citation Author (year) -->` near it. Never use this to hide a citation of a real paper |
   | ⚠️ The DOI points to another title / is a working paper | Replace it as in "Papers with a ⚠️ about the DOI" in `priorwork-screen` |
   | Evidence level unchecked / empty fields | Fill them in as in `priorwork-extract` |
   | Citations not chased (full) | Do it as in `priorwork-snowball` |
   | The Markdown does not match the state | `./priorwork render <survey>` |
   | A managed block is missing | Restore the lost `<!-- BEGIN priorwork:… -->` / `<!-- END priorwork:… -->` from the git history or similar |

3. Repeat 1–2 until there are no ERRORs. Mention the WARNs and INFOs you could not fix in your report.

**Never tell the user it is finished while ERRORs remain.**

## 4. Export

```bash
./priorwork export <survey>
```

If the output is marked "Draft" at the top, give the reasons (unchecked cards, empty sections, …) in your report and do not call it finished.

Tell the user how to view it, as in AGENTS.md, "Showing the report" (right-click the survey in the sidebar → "Export and View the Report", or right-click `reports/<name>.html` → "View the Report in Priorwork").
