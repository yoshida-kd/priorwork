# Contributing

Issues and pull requests are welcome. The public repository is written by a release script, so a contribution is carried over to the development repository and comes out in the next release.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest          # no network needed
bin/priorwork --help                # run the code of this checkout
```

```text
.
├── priorwork/
│   ├── cli.py                  # the commands (including --json output)
│   ├── i18n.py / lang_ja.py    # messages: English source, Japanese catalogue
│   ├── workspace.py            # a workspace's paths and language
│   ├── scaffold.py             # init / sync / upgrade
│   ├── survey.py               # the state and the generated Markdown
│   ├── api.py                  # Semantic Scholar / OpenAlex / PubMed
│   ├── ssci.py                 # SSCI status
│   ├── snowball.py             # citation chasing
│   ├── fulltext.py             # full texts (Zotero / open access)
│   ├── zotero.py               # Zotero Web API / WebDAV (read only)
│   ├── check.py                # checks
│   ├── export.py               # the version for reading
│   ├── doctor.py               # diagnosis
│   └── assets/                 # what workspaces receive: AGENTS.md, skills and the report template per language (en/, ja/), env.example
├── vscode-extension/           # the VS Code extension (TypeScript)
├── tests/
└── bin/priorwork               # the development wrapper
```

When you change `AGENTS.md` or a skill, edit both `priorwork/assets/en/` and
`priorwork/assets/ja/`; workspaces receive them through `priorwork sync`.

Every command and option in the guides and the reference must exist (`tests/test_docs_commands.py`), and the English and Japanese pages must have the same sections (`tests/test_site.py`).
