---
name: survey-extract
description: >-
  Fills in the per-paper cards (RQ, X, Y, data, identification strategy, findings, limitations) of a
  survey from abstracts or full texts retrieved with `./priorwork fulltext`, then regenerates the comparison
  matrix with `./priorwork render`. Use when included papers have unfilled cards.
---

# Fill in the paper cards

Follow the rules in [AGENTS.md](../../../AGENTS.md).

## Depth

- `full`: get the full text of the core papers and set their evidence to "full text checked".
- `quick`: the abstract is enough (evidence "abstract only"). Get the full text only for papers the user wants to look at more closely.

Either way, write only what the abstract or the full text says, and always update the evidence level.

## Steps (one paper at a time)

1. See which papers are unfilled.

   ```bash
   ./priorwork status <survey>
   ```

2. Get the full text. A PDF attached in Zotero is used when Zotero is set up; otherwise an open-access version is looked for.

   ```bash
   ./priorwork fulltext <survey> <number>
   ./priorwork fulltext <survey> <number> --pdf "<path to the PDF>"   # when the user tells you where the PDF is
   ```

   If it cannot be found, ask the user to attach the PDF in Zotero or to tell you where it is (`./priorwork zotero <survey>` shows which papers are in Zotero and whether they have a PDF). Also ask whether to go on with the abstract only.

   If the source is "Zotero's index text (no page breaks)", do not give page numbers; write "(page not checked)".

3. In section 3 of the survey Markdown, change only the fields of that paper's card (below `<!-- paper: ... -->`).
   - The heading, the `Source` line and the `⚠️` lines are generated; leave them alone.
   - After `**RQ**: ` and the other labels, write a short summary (one sentence) that goes into the matrix. Add details as `  - ` sub-bullets below it.
   - Write only what the text says. Give $N$, estimates and periods exactly as the paper does, with the page, like `(p. 12)`.
   - If something is not there, write "not reported". Never fill a field by guessing.
   - Update `**Evidence**` to "full text checked" or "abstract only".

4. Update the matrix.

   ```bash
   ./priorwork render <survey>
   ```

5. Every two or three papers, report the key points (identification, main findings) to the user and ask whether to continue.
