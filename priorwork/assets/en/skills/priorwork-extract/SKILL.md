---
name: priorwork-extract
description: >-
  Fills in the per-paper cards (RQ, X, Y, data, identification strategy, findings, limitations) of a
  survey from abstracts or full texts retrieved with `./priorwork fulltext`, then regenerates the comparison
  matrix with `./priorwork render`. Use when included papers have unfilled cards.
---

# Fill in the paper cards

Follow the rules in [AGENTS.md](../../../AGENTS.md).

## By depth

- `full`: for **every included paper**, get the full text (`./priorwork fulltext`), fill in the card from it and set the evidence level to "full text checked". Do not pick papers to read by whether they are "core". "Abstract only" is allowed only for papers whose full text `fulltext` tried and could not find (the failure is recorded, and `check` tells it apart from not trying).
  - You need not read the full text from start to end. Focus on the data and sample, the identification, the main results (tables) and the limitations, and fill in the card's fields.
- `quick`: filling in from the abstracts is fine (evidence level "abstract only").

Either way, write only what the abstract or full text says, and always update the evidence level.

In a survey made from a manuscript (`priorwork-manuscript`), the papers the draft cites must be "full text checked" at any depth (`check` gives a WARN otherwise).

## Steps (one paper at a time, until every included paper is done)

1. See which papers are unfilled. If a Zotero collection is linked, start with the papers that have a PDF there.

   ```bash
   ./priorwork status <survey>
   ./priorwork zotero <survey>     # with Zotero set up, shows which papers have a PDF
   ```

2. Get the full text (the PDF in Zotero first, then an open-access version).

   ```bash
   ./priorwork fulltext <survey> <number>
   ```

   If there is none, fill in from the abstract and set the evidence level to "abstract only". In your final report, list the papers without a full text and say that attaching a PDF in Zotero would let you check them in the full text.

   If the source is "Zotero's index text (no page breaks)", do not give page numbers; write "(page not checked)".

3. In section 3 of the survey Markdown, rewrite only the fields of that paper's card (under `<!-- paper: ... -->`), or use `./priorwork card <survey> <number> --set rq=... evidence=fulltext`.
   - The heading, the `Source` line and the `⚠️` lines are generated; do not touch them.
   - On the line itself (`**RQ**: ` and so on), write a short summary (one sentence) for the matrix. Add details as `  - ` bullet points right below it.
   - Write only what the text says. Give $N$, estimates and periods as written, with the page, like `(p. 12)`.
   - If something is not there, write "not reported". Never fill it in by guessing.
   - Update `**Evidence**` to "full text checked" or "abstract only".
   - If the full text shows that a paper is out of scope, do not fill in its card; exclude it with `./priorwork exclude` and a reason.

4. Every few papers, update the matrix.

   ```bash
   ./priorwork render <survey>
   ```

Only in consultation mode, report the key points (identification strategy, main findings) every 2–3 papers and check whether to go on.
