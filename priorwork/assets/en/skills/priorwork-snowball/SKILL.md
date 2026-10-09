---
name: priorwork-snowball
description: >-
  Finds papers missed by keyword search by following the references and citations of the papers already
  included in a survey (`./priorwork snowball`), then screens the new candidates.
  Use after some papers have been included, always for a full survey.
---

# Chase citations to find what was missed

Follow the rules in [AGENTS.md](../../../AGENTS.md).

If the depth (shown by `./priorwork status <survey>`) is `full`, always do this. For `quick`, do it when few papers are included or missed papers are a worry.

## Steps

1. Run it. Unregistered papers are added as candidates, those linked by citations to the most included papers (the most links) first.

   ```bash
   ./priorwork snowball <survey>
   ```

   - Only the classic earlier work: `--direction references`
   - Only recent follow-up work: `--direction citations`
   - Too many / too few candidates: raise `--min-links` / set it to 1

2. Screen the new candidates as in `priorwork-screen`. Watch for these papers in particular:
   - Many links (cited by many of the included papers) → likely a classic of the field. Include it if it fits the scope.
   - Comments and replies ("Comment", "Reply", … in the title) → not included, but useful for the debates.

3. When the included papers have grown a lot (about 5 more since the last run), run it again: the link counts get better. Stop when hardly any new candidates appear.
