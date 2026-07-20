# ルカリオexデッキ 居座りボーナス修正＋RETREAT HP温存観点追加 実装サマリー

**関連設計書：** `docs/superpowers/specs/2026-07-20-lucario-stay-bonus-retreat-hp-preservation-design.md`
**関連計画書：** `docs/superpowers/plans/2026-07-20-lucario-stay-bonus-retreat-hp-preservation.md`

## 背景

`docs/analyses/20260720-lucario-submission-notebook-first-run-20-games-analysis.md`（notebook自動生成スクリプト初の実地提出、新規20戦分析）で、居座りボーナスバグ（`combat.py`の`calc_attack_plan`にある`i==0`+220・`j==0`+300の固定加点）が敗戦の一因（9敗中1敗で明確に関与）として再確認された。同日の別セッションで一度「YAGNIで撤回」と判断されていたが、実ログでの再現（`87053177`・`86898758`）を受けて修正を実施した。併せて、関連課題として持ち越されていた「RETREATスコア式へのHP温存観点の追加」（瀕死の高価値ポケモンを温存退却させる判断が一切無い問題）も一体で対応した。

## 実装内容

`superpowers:subagent-driven-development`で4タスクをTDD形式で実装した（featureブランチ`feature/lucario-stay-bonus-retreat-hp-preservation`、コミット範囲`1056801..9c0c712`、4コミット）。

### Task 1（コミット`64a2b9b`）：`AttackPlan.damage`フィールド追加

`AttackPlan`データクラスに`damage: int = -1`フィールドを追加し、`calc_attack_plan`が最良プランを更新する際に選択したプランの実ダメージ量を保存するようにした。後続タスクがこの値を参照する。

### Task 2（コミット`839befe`）：居座りボーナスバグ本体の修正

`calc_attack_plan`の位置ボーナス（現在のアクティブ`i==0`+220・現在の対象`j==0`+300）を、`damage > 0`のときのみ加算するよう修正。実ダメージ0のプランが位置ボーナスだけでベンチ交代プランを上回ることがなくなった。KO確定プラン（`score = 50000`上書き）は必ず`damage > 0`が前提のため、KO確定プラン同士のタイブレークとしての位置ボーナスの役割は変わらない。

### Task 3（コミット`d514e95`）：`_score_retreat_option`にHP温存退却の分岐を追加

既存の`current_plan.attacker >= 1`分岐（より良いアタッカーへの切替）はそのまま維持し、新たに「今ターンの最善プランが実質ノーダメージ（`damage <= 0`）かつ現在のアクティブがex/megaEx（プライズ価値2〜3）」の場合に退却スコア2000を返す分岐を追加。新引数`my_active`・`card_table`はデフォルト`None`とし、既存の単一引数呼び出しは非破壊のまま動作する。

### Task 4（コミット`9c0c712`）：`main.py`の呼び出し配線

`_score_option`のRETREATケースが、Task 3で拡張された新シグネチャへ現在のアクティブポケモン（`my_state.active[0] if my_state.active else None`）と`card_table`を渡すよう更新した。

## 新規・変更ファイル

- `src/lucario_agent/combat.py`（`AttackPlan`フィールド追加、位置ボーナスのダメージ条件付け、`_score_retreat_option`の分岐追加）
- `src/lucario_agent/main.py`（RETREATケースの呼び出し配線）
- `tests/test_lucario_agent.py`（新規テスト7件：`TestAttackPlanDamageField`1件、`TestStayBonusDamageGating`1件、`TestScoreRetreatOption`への追加4件、`TestScoreOptionRetreatWiring`1件）

## テスト結果

- 新規追加テスト7件、全てPASS
- リポジトリ全体回帰：`uv run pytest -q`で574件PASS（既存567件＋新規7件、失敗0件）
- mainへのマージ後も574件PASSを再確認済み

## レビュー結果

各タスクの個別レビュー（4件）・最終ブランチ全体レビュー（1件、Opusモデル）ともにCritical/Important指摘無し、Ready to merge = Yes。詳細は`docs/reviews/20260720-lucario-stay-bonus-retreat-hp-preservation.md`参照。

## マージ

`feature/lucario-stay-bonus-retreat-hp-preservation`ブランチを`main`へfast-forwardマージし、featureブランチは削除済み（コミット範囲`1056801..9c0c712`）。**push未実施**（origin/mainより先行、pushタイミングはユーザー判断）。

## スコープ外（次回以降の検討候補）

- 相手の技火力を推定した精密な脅威判定（アプローチB。今回のアプローチA＝閾値ベースの効果を実測してから検討）
- Dragapult ex系トゥールボックス対策（同日の20戦分析で新たに浮上した別課題）
- ソルロックの「弱点・抵抗力を無視する」効果の`_calc_attack_damage`未実装（既知だが本修正とは無関係）

## 次回セッションへの申し送り

Kaggle提出用notebookを再生成・再提出後、新規のバトルログが溜まったら以下を実測検証する：
1. 居座りボーナスバグの再発有無
2. ミラー対面（Mega Lucario ex同士）の戦績変化（今回の修正の狙い）
3. `_score_retreat_option`の新分岐（`damage<=0`かつex/megaEx）が想定通りに発火し、プライズ献上を減らせているか
