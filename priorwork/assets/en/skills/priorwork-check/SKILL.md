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
   | A citation matches several included papers / no paper matches 2001a | Make the citation in the text match the 2001a / 2001b labels in the references section |
   | A citation taken for an organisation or a figure number and not checked (INFO) | If it is a paper, register it as above. Reports, statistics and the like can stay |
   | Text that is not a citation is taken for one | Write `<!-- priorwork:ignore-citation Author (year) -->` near it. Never use this to hide a citation of a real paper |
   | ⚠️ The DOI points to another title / is a working paper / is not found | Replace it as in "Papers with a ⚠️ about the DOI" in `priorwork-screen` (`fix --id`). If you have checked that the DOI is right, `fix --confirm "<reason>"` |
   | Text in a card is taken for an unregistered Author (year) citation | Do not write sources that are not papers of the survey (a data source, say) as Author (year) ("Franchino's 2004 data" instead). Register it if it is a paper for the survey |
   | The full text has far fewer pages than the journal pages | The full text is incomplete (perhaps the publisher's preview). Do not fill the card from it; ask in your report for the whole PDF in Zotero (set the level to abstract only) |
   | Evidence level unchecked / empty fields | Fill them in as in `priorwork-extract` |
   | Citations not chased (full) | Do it as in `priorwork-snowball` |
   | A number on a card is not in the full text / a cited page is not in the paper | Compare with the full text (the text from `./priorwork fulltext`) and fix it; remove it if the paper does not say it. If only the form differs (units, rounding), write it as the paper does |
   | "Full text checked" but no page / no full text fetched | Read the full text and add the pages. If you did not read it, lower the evidence level to "abstract only" |
   | A card is not in the report's language | Rewrite it in that language (keep terms in the original in brackets) |
   | A synthesis section cites no paper | Rewrite it from the included papers, citing them as Author (year). If it is this study's own view, move it to "Hypotheses and implications for this study" |
   | The text gives a wrong number of included papers | Delete the sentence with the count (the appendix gives it) |
   | Included papers not in Zotero | Show the DOIs from `./priorwork zotero <survey> --dois` as they are in your report (also those whose full text you got) |
   | The survey and the Octavo project use different Zotero collections | Ask the user which one to use. The survey's is set with `./priorwork zotero <survey> --collection "<name>"`; the user sets Octavo's with `octavo config set zotero_collection "<name>"` |
   | The draft cites papers not in the Octavo project's .bib | Give their DOIs in your report; the user puts them in the Zotero collection and runs `octavo bib pull`, then export again with `export --draft --octavo` |
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
