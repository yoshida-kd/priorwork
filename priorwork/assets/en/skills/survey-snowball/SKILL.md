---
name: survey-snowball
description: >-
  Finds papers missed by keyword search by following the references and citations of the papers
  already included in a survey (`./priorwork snowball`), then hands the new candidates to screening.
  Use after some papers have been included, or when the user suspects key papers are missing.
---

# Chase citations to find what was missed

Follow the rules in [AGENTS.md](../../../AGENTS.md).

If the depth (shown by `./priorwork status <survey>`) is `full`, always do this. For `quick` it is optional; suggest it when the user worries about missing papers or when few papers are included.

## Steps

1. Run it. Unregistered papers are added as candidates, ordered by how many included papers they are linked to by citations (the number of links).

   ```bash
   ./priorwork snowball <survey> --limit 15
   ```

   - Only the classic earlier work: `--direction references`
   - Only recent follow-up work: `--direction citations`
   - Too many / too few candidates: raise `--min-links` / set it to 1

2. Summarise the result for the user. Point out in particular:
   - papers with many links (cited by many included papers) that are not included yet → possibly the field's classics
   - comments and replies ("Comment", "Reply" in the title) → important for mapping the debates

3. Screen the new candidates as in `/survey-screen`.

Running it again each time three or more papers have been added to the included ones makes the link counts more accurate.
