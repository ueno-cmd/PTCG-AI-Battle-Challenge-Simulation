# 実装サマリー：ルカリオexエージェント ロジック不整合修正 + if文ガイドライン準拠リファクタ

**実装日：** 2026-07-08
**関連計画書：** `docs/superpowers/plans/2026-07-08-lucario-if-guideline-refactor.md`
**関連ガイドライン：** `docs/steering/coding-gideline.md`（元`coding-gideline.md`をリポジトリ直下からdocs/steeringへ移動し、`docs/steering/dev-guidelines.md`から参照するようにした）
**作業ブランチ：** `fix/lucario-if-guideline-refactor`（`main`直での実装を避けるためユーザー承認の上で作成）

## 背景

10連勝の実績があるルカリオexエージェント（`src/lucario_agent/main.py`）は、オーガポンex導入・Crustle対策・メガブレイブのε-greedy化など段階的な機能追加を経ており、ロジックの不整合と、`docs/steering/coding-gideline.md`（if文設計ガイドライン：ネスト2階層まで・複合条件の命名・判断と処理の分離）への違反が蓄積していないかをレビューした。

コミット履歴・過去の実装ドキュメント（`docs/implementations/20260706-lucario-ogerpon-subattacker.md`、`docs/implementations/20260707-crustle-counter-ogerpon-priority.md`）・カードの実効果（`data/EN_Card_Data.csv`等）を照合した結果、以下2件の実害あるロジック不整合と、ガイドライン違反箇所を特定した。

1. **Ogerpon_ex（デッキで2枚採用、Crustle対策の要）が山札サーチ優先度ロジックから漏れている**：`DISCARD`保護には追加済みだったが、`SelectContext.TO_HAND`のスコアリングとUltra_Ballの`already_found`使用判定には追加されていなかった。
2. **`calc_attack_plan`内でダメージ計算（弱点/抵抗力/Crustle無効化）が2箇所に重複実装されており、片方（`base_dmg_normal`）にCrustle無効化が反映されていない**：現状は実害なし（Crustle戦はどちらの攻撃を選んでも実ダメージ0のため）だが、構造的リスクとして残っていた。
3. **`calc_attack_plan`がネスト6階層に達し、無名の複合if条件が4箇所存在**：機能追加が最も集中した関数であり、ガイドライン違反も集中していた。
4. **`_score_play_option`のPremium_Power_Pro分岐が3階層ネスト＋無名三重and条件**：既存テストが1件もなかった。

## 変更内容

サブエージェント駆動開発（TDD、タスクごとのspec+quality二段階レビュー、最終ブランチ全体レビュー）で全4タスクを実施した。

| コミット | 内容 |
|---|---|
| `393e66d` | Ogerpon_exをTO_HANDサーチ優先度に追加 |
| `ce36773` | Ultra_Ball使用判定の`already_found`にOgerpon_exを追加 |
| `c563aae` | `calc_attack_plan`のダメージ計算を`_calc_attack_damage`ヘルパーに集約しネストを解消 |
| `1c522cf` | `Premium_Power_Pro`分岐をガード節で平坦化 |

### 1. Ogerpon_exのTO_HANDサーチ優先度（`393e66d`）

`_score_card_option`の`SelectContext.TO_HAND`に、Riolu方式（デッキ採用枚数に対する充足度）を踏襲した分岐を追加：場に0枚なら+40、1枚なら-3、2枚（採用上限）なら-150。

### 2. Ultra_Ballのalready_found判定（`ce36773`）

`_score_play_option`のUltra_Ball使用判定`already_found`の集計に、`field_counts[Ogerpon_ex]`・`hand_counts[Ogerpon_ex]`を追加。

### 3. `_calc_attack_damage`ヘルパーへの集約（`c563aae`）

新規関数`_calc_attack_damage(attacker_id, base_damage, defender_id, defender_data) -> int`を追加し、弱点2倍・抵抗力-30・Ogerpon_exの弱点無視仕様・Crustleの特性無効化（Mega_Lucario_exのみ対象）を1箇所に集約。`calc_attack_plan`内の2つの重複呼び出し箇所（メインダメージ計算・メガブレイブ温存判定用の`base_dmg_normal`）を置き換えた。これにより**`base_dmg_normal`もCrustle無効化を正しく反映するようになった**（正確性の修正）。あわせて無名の複合条件2箇所に`mega_brave_unavailable_for_current_active`・`can_attach_energy_this_turn`と命名した。

### 4. Premium_Power_Proのガード節化（`1c522cf`）

既存テストが無かったため、まず現状挙動を固定する特性化テスト5件を追加（リファクタ前のコードでPASSすることを確認）。その後、3階層ネスト＋無名三重and条件を、`confirmed_ko_already_secured`・`other_supporter_in_hand`の2つの名前付きガード節に書き換え、同じテストが変わらずPASSすることを確認した（真理値表による挙動保存の検証はレビューでも独立に実施済み）。

## テスト結果

- 新規テスト計17件（TO_HAND3、Ultra_Ball2、`_calc_attack_damage`単体7、Premium_Power_Pro特性化5）
- リポジトリ全体：`uv run pytest -q`で**273 passed**（lucario_agent関連は既存256件＋新規17件が全PASS）
- `tests/test_grimmsnarl_agent.py`の既存3件失敗（コミット`c80e057`由来、本タスク開始前から存在）はスコープ外としてユーザー承認済み。今回の変更との因果関係なし（差分はlucario_agent関連の2ファイルのみ）

```
$ uv run pytest -q
...
3 failed, 273 passed in 0.13s
```

## 各タスクのレビュー結果

- Task 1（TO_HAND）：Approved。Issues無し。
- Task 2（Ultra_Ball）：Approved。Issues無し。
- Task 3（`_calc_attack_damage`集約）：Approved。Minor1件（Crustle低HP時のcalc_attack_plan経由統合テスト欠落）→最終レビューで実害ほぼゼロと再評価、対応不要。
- Task 4（Premium_Power_Proガード節化）：Approved。Minor2件（Lillie単独ケース未検証／変数名がsupporterPlayed条件を含意しない点、いずれもbrief起因）→対応不要。

## 未対応事項（最終ブランチ全体レビューより）

- `base_dmg_normal`のCrustle無効化修正について、`calc_attack_plan`経由の統合テスト（低HP Crustle vs Mega_Lucario_ex）は追加していない。`_calc_attack_damage`の単体テストはあるが、旧バグを実際に踏む経路の統合テストはない。ただし影響評価の結果、Crustle戦では通常攻撃・メガブレイブいずれもダメージ0でスコアが元々0近傍に沈むため、エージェントの最終選択には影響しない（実害ほぼゼロ）。将来Crustle類似の耐性ポケモンが増えた際の回帰検知用に、余力があれば追加を検討。
- `Lillie_Determination`単独が手札にあるケースの`Premium_Power_Pro`テストは未追加（`Boss_Orders`側とコード上完全対称のため実リスクは低い）。
- `calc_attack_plan`の三重forループ由来のインデント（自分ポケモン×技×相手ポケモンの総当たり）は今回のスコープでは解消していない。これはアルゴリズムの本質であり、if文ネストの問題とは性質が異なるため計画時点で対象外とした。

## 次のステップ

- ブランチ`fix/lucario-if-guideline-refactor`のmainへの統合（マージ方法）はユーザー判断待ち。
- Kaggle再提出・LBスコア確認は本改修のスコープ外。
