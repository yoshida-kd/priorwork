# Starting from a manuscript

> This is the source of this page. Read it at **<https://yoshida-kd.github.io/priorwork/manuscripts/>**. <!-- pages:skip -->

Instead of a topic, you can start from a manuscript of your own, finished or not. **One manuscript gets one survey and one report**, and the agent puts the work where the manuscript needs it:

| The manuscript | The report mainly gives you |
| :--- | :--- |
| Half written | what each section lacks, and what to add where |
| Analysis done, no introduction, literature review or theory | those parts, written out in the language of the manuscript |
| Finished | a check of its citations, the literature it does not mention, comments on the argument |

## 1. Where to put it

In `manuscripts/`, one folder per paper (`manuscripts/README.md` says the same).

```text
manuscripts/
  make_or_buy/          ← one folder per paper (an English name)
    paper.md            ← the manuscript; only what is written so far is fine
    tables/             ← results tables, figures and logs not in the manuscript
```

Any format will do: Markdown, Quarto (.qmd and its HTML), LaTeX, Word (.docx), PDF.

## 2. How to ask

**New Survey → Start from my manuscript** in the sidebar lets you choose the manuscript (or its folder) and copies the request. If you choose one outside the workspace, it offers to copy it into `manuscripts/` (the original stays where it is). You can also ask in the chat:

> The manuscript in manuscripts/make_or_buy is half written. Fill in what it lacks from the literature.

> The manuscript in manuscripts/make_or_buy is written up to the analysis. Write the introduction, literature review and theory and hypotheses.

> What literature is the manuscript in manuscripts/make_or_buy missing, and where does it cite the literature badly?

## 3. Leave marks where you want help

While writing, put `[cite]` where a citation is needed, `[@?]` where a paper should be cited, or `TODO(priorwork): <what you need>` on a line of its own. The agent takes them first and says which it could not fill, and why.

## 4. Agreeing what to make

The agent reads the manuscript, then proposes what to focus on, which parts to cover and the scope of the searches, and waits for your answer. If your request already settles these, it goes ahead.

## 5. What is in the report


| Section | What it holds |
| :--- | :--- |
| What to do first | the most important points, in order |
| What the manuscript lacks | each section's state, and your marks |
| Claims that need literature | with the papers in support and **the papers that conflict** |
| What to add | item by item in the manuscript's order: **Where** (the sentence it goes before or after, quoted), **Why**, and the text. Only what the literature backs, never your methods or results |
| Checking the citations | place by place: fits / wrong direction / overstated / weak evidence, with a suggested fix |
| Literature the manuscript does not mention | where and why to cite it |
| The hypotheses and their literature | the literature behind each hypothesis and the literature against it |
| The argument | how the question, gap, hypotheses, methods, results and contribution hang together |

Each paper card also gets a **Role in the manuscript**, which the comparison matrix shows too. Sections nobody asked for say "Not covered".

The manuscript itself is never rewritten. Read the report and change the manuscript yourself. The agent exports what to add to `reports/<name>.draft.md`, with its references; for an Octavo manuscript it goes into the project's inbox (see below).

A survey made by an earlier version as a draft or as advice keeps its report and can be carried on as it is.

## 6. Working with an Octavo manuscript

A manuscript you write in [Octavo](https://github.com/yoshida-kd/octavo) (a tool for writing papers in
Markdown and Quarto) can stay in its Octavo project (another repository). One Priorwork workspace can
serve the papers of many Octavo projects.

Octavo's collection picker, lists of collections and **Ask Priorwork for the Literature** come with Octavo
releases after 0.6.4.

### The link between them is a Zotero collection

Octavo pulls its `.bib` of references from the
collection named in its settings (`zotero_collection`). Link the Priorwork survey
to the same collection, and the included papers you put there become the Octavo manuscript's references
too.

1. In the Octavo project, choose the paper's collection (**Choose the Zotero Collection** in Octavo's
   sidebar).
2. Right-click the paper in Octavo's sidebar → **Ask Priorwork for the Literature** (or choose the
   paper in the Octavo project with Priorwork's **New Survey → Start from my manuscript**) to copy a
   request, and paste it into the agent's chat in the window of your Priorwork workspace. The two are
   separate windows, so the request carries it across.
3. The agent reads the manuscript, the project's results and tables, and the literature it cites (the
   `.bib`), and registers the papers it cites. The survey is linked to
   the same Zotero collection as Octavo.
4. The draft is exported in Octavo's form into the Octavo project's inbox
   (`literature/priorwork/<survey>.md`, with a `.json`
   manifest and `<survey>.cards.json`, the cards of the included papers for Octavo to show over each
   `[@key]`): citations become `[@key]` from the `.bib`, and Octavo makes the references section.
   Priorwork never changes the manuscript: ask the agent in the Octavo project to "work the draft from
   Priorwork into the manuscript" (or move it yourself).
5. Papers not in the `.bib` yet are written as `[@PRIORWORK:<DOI>]`, with a list of their DOIs. Put them
   in the Zotero collection ([the guide, 3.7](https://yoshida-kd.github.io/priorwork/guide/#37-collect-the-papers-in-zotero); Priorwork can do it for you), pull
   them into Octavo and press **Replace the Marks with the .bib Keys** in Octavo's sidebar (until then,
   Octavo's checks report them as missing keys).

### Requests without the clipboard

An Octavo that knows where your Priorwork workspace is puts its
requests in the workspace's `.priorwork/requests/` instead of copying them. They show under **Requests
from Octavo** at the top of the sidebar: click one to ask your agent to carry it out (a short request
that points to it) or to decline it with a reason Octavo can read. The agent records the outcome, and
Octavo shows it.

### One survey for several papers

A survey on a topic (say, the literature on outsourcing) can serve
several papers. Right-click the survey → **Link to an Octavo Project…** and choose the project's folder
(as many as you like); **Export for an Octavo Project…** writes the sections on theories, methods,
debates and gaps with that project's `.bib` keys to its inbox, `literature/priorwork/<survey>.md`. In Octavo,
add the survey's collection to the project's (**Choose the Zotero Collection** there lets you mark any
number).

### Several surveys for one Octavo project

One paper may get several surveys, by angle (theory,
methods, …), even from different workspaces. Then make a collection for each survey in Zotero under the
Octavo project's collection (e.g. "Make or buy / Theory" and "Make or buy / Methods" under "Make or
buy"), and link each survey to its own. Octavo's pull takes the collections under its collection
too, so every survey's included papers end up in one `.bib`. The sidebar's list of collections shows
Octavo's collection and the ones under it first, and the survey's status lists the other surveys for
the same Octavo project.

Priorwork never changes the files of the Octavo project. The check tells you when the survey and Octavo
use different collections. The manuscript's place is recorded relative to the workspace (e.g.
`../make_or_buy/papers/main`), so it works on another machine too if the repositories are cloned side by
side in the same way.
