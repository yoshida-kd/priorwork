---
name: priorwork-snowball
description: >-
  Finds papers missed by keyword search by following the references and citations of the papers already
  included in a survey (`./priorwork snowball`), then screens the new candidates.
  Use after some papers have been included, always for a full survey.
---

# 引用をたどって見落としを補う

ルールは [AGENTS.md](../../../AGENTS.md) に従う。

深さ（`./priorwork status <survey>` に表示）が `full` なら必ず行う。`quick` なら、採用論文が少ないときや見落としが気になるときに行う。

## 手順

1. 実行する。採用論文のうち何本と引用関係にあるか（リンク数）の多い順に、未登録の論文が候補として登録される。

   ```bash
   ./priorwork snowball <survey>
   ```

   - 定番の先行研究だけ欲しい: `--direction references`
   - 最近の後続研究だけ欲しい: `--direction citations`
   - 候補が多すぎる / 少なすぎる: `--min-links` を上げる / 1 にする

2. 新しい候補を `priorwork-screen` の手順で選別する。特に次の論文に注意する。
   - リンク数が多い（採用論文の多くが参照している）論文 → 分野の定番の可能性が高い。範囲に合えば採用する。
   - コメント・リプライ論文（タイトルに "Comment" "Reply" など）→ 採用はしないが、論争点の整理の手がかりにする。

3. 採用が大きく増えたら（目安: 前回から 5 本以上）、もう一度実行する。リンク数の精度が上がる。新しい候補がほとんど出なくなったら終える。
