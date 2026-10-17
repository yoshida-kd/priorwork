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

Either way, write only what the abstract or full text says, and always update the evidence level. **Set "full text checked" only when you filled in the card from the full text you fetched with `./priorwork fulltext` and read.** A card written from the abstract is "abstract only", even if the full text is in the cache.

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

   - If it says "The PDF has only N pages", the full text is incomplete (perhaps the publisher's preview). Do not fill the card from it; set it to abstract only, and ask in your report for the whole PDF in Zotero.
   - Give pages as the journal prints them on each page of the PDF. For a text without journal pages (an author's accepted manuscript or a working-paper version), give the PDF page (the N of `=== page N ===`) and write in the memo "pages are those of the accepted-manuscript PDF".

3. In the section "The papers" of the survey Markdown, rewrite only the fields of that paper's card (under `<!-- paper: ... -->`), or use `./priorwork card <survey> <number> --set rq=... evidence=fulltext`.
   - **Write in the language of the report.** Summarise in your own words rather than copying the abstract; keep terms in the original in brackets.
   - The heading, the `Source` line and the `⚠️` lines are generated; do not touch them.
   - On the line itself (`**RQ**: ` and so on), write a short summary (one sentence) for the matrix. Add details as `  - ` bullet points right below it.
   - Write only what the text says. Give $N$, estimates and periods as written, with the page, like `(p. 12)`. On a card checked against the full text, the data, identification and main findings always carry a page (or "(page not checked)" when the full text has no page breaks).
   - For the identification, write the method the paper actually uses (never DID for a paper that does not use it). If unclear, "not reported".
   - For the main findings, keep the direction of the result (rises / falls, does / does not) exactly as the paper states it.
   - If something is not there, write "not reported". Never fill it in by guessing.
   - Do not name another paper or a data source on a card in the form Author (year) (`check` takes it for an unregistered citation and gives an ERROR). Write "Franchino's 2004 data" instead.
   - Update `**Evidence**` to "full text checked" or "abstract only".
   - If the full text shows that a paper is out of scope, do not fill in its card; exclude it with `./priorwork exclude` and a reason.

4. Every few papers, update the matrix and check. `check` gives a WARN for numbers not in the full text, pages not in the paper, cards without pages and cards not in the report's language. Fix them against the full text.

   ```bash
   ./priorwork render <survey>
   ./priorwork check <survey> --offline
   ```

Only in manual mode, report the key points (identification strategy, main findings) every 2–3 papers, naming the papers as Author (year), and check whether to go on.
