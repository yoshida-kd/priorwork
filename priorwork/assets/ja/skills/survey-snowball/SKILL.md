---
name: survey-snowball
description: >-
  Finds papers missed by keyword search by following the references and citations of the papers
  already included in a survey (`./priorwork snowball`), then hands the new candidates to screening.
  Use after some papers have been included, or when the user suspects key papers are missing.
---

# 引用をたどって見落としを補う

ルールは [AGENTS.md](../../../AGENTS.md) に従う。

深さ（`./priorwork status <survey>` に表示）が `full` なら必ず行う。`quick` なら任意で、ユーザーが見落としを気にするときか、採用論文が少ないときに勧める。

## 手順

1. 実行する。採用論文のうち何本と引用関係にあるか（リンク数）の多い順に、未登録の論文が候補として登録される。

   ```bash
   ./priorwork snowball <survey> --limit 15
   ```

   - 定番の先行研究だけ欲しい: `--direction references`
   - 最近の後続研究だけ欲しい: `--direction citations`
   - 候補が多すぎる / 少なすぎる: `--min-links` を上げる / 1 にする

2. 結果をユーザーに要約する。特に次の論文は目立たせる。
   - リンク数が多い（採用論文の多くが参照している）のに、まだ採用していない論文 → 分野の定番の可能性
   - コメント・リプライ論文（タイトルに "Comment" "Reply" など）→ 論争点の整理に重要

3. 新しい候補の選別は `/survey-screen` の手順で行う。

採用が 3 本以上に増えるたびに再実行すると、リンク数の精度が上がる。
