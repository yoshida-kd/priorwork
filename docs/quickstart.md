# Quick guide

> This is the source of the quick guide. Read it at **<https://yoshida-kd.github.io/priorwork/quickstart/>**. <!-- pages:skip -->

From installing Priorwork to your first literature review, in six short steps, all in VS Code.
Every step has a longer version in the [guide](https://yoshida-kd.github.io/priorwork/guide/).

## 1. Install

1. Install [VS Code](https://code.visualstudio.com/) and an AI agent that works in it (Claude Code,
   Antigravity, …).
2. Install the **Priorwork** extension from the
   [Marketplace](https://marketplace.visualstudio.com/items?itemName=yoshida-kd.priorwork).

On Windows, open a folder inside WSL first; on a server, connect with Remote - SSH first.

## 2. Make a workspace

Open an empty folder and press **Create a Workspace** in the Priorwork sidebar. Choose the
language of the reports. Python is set up for you (uv is installed if you have no Python).

Then open the gear (**Settings**), enter a free
[Semantic Scholar API key](https://www.semanticscholar.org/product/api#api-key-form) and press
**Save and Check the Connections**. Publish the workspace to GitHub as a **private** repository
from the sidebar: the reports contain abstracts.

## 3. Ask the agent

In your agent's chat, say what you want in your own words:

> Do a full review of how government organisations staff up when demand for their services changes.

Or **New Survey → Ask your agent to do it** in the sidebar, which copies the request. The agent sets
the scope, searches, screens, chases citations, fills in a card for each paper and writes the
review. It stops twice for you to check: once the scope is set, and before writing the cards.

## 4. Collect the papers in Zotero

At the second stop, the agent shows the DOIs of the included papers. Paste them into Zotero's
**Add Item by Identifier** (the magic wand), attach the PDFs, and say "carry on". The cards are then
written from the full texts. (Without Zotero, just say "carry on".)

## 5. Read the report

When the agent is done, right-click the survey in the sidebar → **Export and View the Report**. It
opens inside VS Code, on a server too.

## 6. Check and correct

Under the survey in the sidebar are the included, maybe and excluded papers. Click one to read its
abstract and the agent's reason: **I**, **M** or **X** overturns the decision, and a card is corrected
on its page (**Ctrl+S** saves). The agent follows your corrections when you say "carry on".

## 7. Where next

- [The guide](https://yoshida-kd.github.io/priorwork/guide/): everything in detail — starting from
- [Starting from a manuscript](https://yoshida-kd.github.io/priorwork/manuscripts/): from your own manuscript, and with Octavo.
- [Installing Priorwork](https://yoshida-kd.github.io/priorwork/install/): on Windows or a server.
  your manuscript, Zotero, Octavo, the checks.
- [The reference](https://yoshida-kd.github.io/priorwork/reference/): every command, for the agent.
