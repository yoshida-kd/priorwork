# Installing Priorwork

> This is the source of the install guide. Read it at **<https://yoshida-kd.github.io/priorwork/install/>**. <!-- pages:skip -->

You need VS Code, the Priorwork extension and an AI agent that runs in VS Code and reads `AGENTS.md` (Claude Code, Antigravity and others). The extension prepares Python when you create a workspace.

| What you use | Where to read |
| :--- | :--- |
| Linux or a Mac | [On your own computer](#1-on-your-own-computer) |
| Windows | [Windows](#2-windows) (in WSL) |
| A server over SSH | [A server over SSH](#3-a-server-over-ssh) |

## 1. On your own computer

1. Install [VS Code](https://code.visualstudio.com/).
2. In the Extensions view, find **Priorwork** and install it ([Marketplace](https://marketplace.visualstudio.com/items?itemName=yoshida-kd.priorwork)).
3. The Priorwork icon appears in the activity bar. Open an empty folder and press **Create a Workspace** ([next steps](https://yoshida-kd.github.io/priorwork/guide/#2-create-a-workspace)).

The extension looks for Python 3.10 or newer. If there is none, it asks whether to install uv, and uv fetches Python.

## 2. Windows

Install WSL (Ubuntu), open a folder inside WSL with VS Code's **WSL** extension, then follow [the steps above](#1-on-your-own-computer). Using Priorwork on Windows directly has not been checked.

## 3. A server over SSH

Connect with VS Code's **Remote - SSH** extension, then follow [the steps above](#1-on-your-own-computer) on the server. The extension, Python and the workspace all live on the server.

## 4. Keys and lists

All optional, in **Settings** (the gear in the sidebar). See [the guide](https://yoshida-kd.github.io/priorwork/guide/#7-settings).

| What | Why |
| :--- | :--- |
| A free [Semantic Scholar API key](https://www.semanticscholar.org/product/api#api-key-form) | recommended: without one, searches often fail on the rate limit |
| Zotero | collect the included papers, and read full texts from your PDFs |
| The SSCI list from Clarivate's [Master Journal List](https://mjl.clarivate.com/) | settles which journals are in the SSCI |
| For medical surveys: a free NCBI key, the SCIE list | a faster PubMed, and ✅ SCIE |

## 5. Updating

The extension updates from the Marketplace. A workspace keeps its version of the engine until you update it ([how](https://yoshida-kd.github.io/priorwork/guide/#10-updating-the-engine)).
