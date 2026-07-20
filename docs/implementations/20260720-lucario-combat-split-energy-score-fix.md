# ルカリオexデッキ combat.py切り出し・energy_score無効化考慮修正 実装サマリー

- 日付: 2026-07-20
- 設計書: `docs/superpowers/specs/2026-07-20-lucario-combat-split-stay-bonus-fix-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-20-lucario-combat-split-energy-score-fix.md`
- 監査結果: `docs/reviews/20260720-lucario-combat-decision-logic-audit.md`
- ブランチ: `feature/lucario-combat-split`（コミット範囲 `e7525e0..f118ced`、mainへのマージ・push未実施）

## 背景

`docs/analyses/20260720-lucario-ex-nullifier-fix-verification-20-games.md`のフォローアップ。当初「居座りボーナス」（`calc_attack_plan`の位置ボーナス）が主因と仮説を立てたが、設計・実装計画の作成過程で自己検証と4本の監査Agentによる再検証を行った結果、この仮説は撤回し、実ログで裏付けられた`energy_score`関連の実バグ3件を修正することにスコープを変更した（詳細は監査結果ドキュメント参照）。

併せて、ユーザーから「`main.py`（826行）を修正しやすくするため意思決定チェーンを別ファイルに切り出せないか」との要望があり、`constants.py`・`combat.py`への切り出しを同時に実施した。

## 変更内容

### ファイル分割（Task1〜3）

- `src/lucario_agent/constants.py`（新規）：カードID定数群
- `src/lucario_agent/combat.py`（新規）：`AttackPlan`・`prize_count`・`pokemon_score`・`energy_score`・`_calc_attack_damage`・`_tera_stadium_cost_bonus`・`calc_attack_plan`・`_score_retreat_option`・`_score_attack_option_choice`
  - `card_table`（カードメタデータ辞書）をモジュール間の暗黙グローバル共有ではなく、明示的な引数として各関数へ渡す形に変更
- `src/lucario_agent/main.py`：上記2ファイルからimportして再export。既存テスト（`tests/test_lucario_agent.py`）は`lm.X`形式のアクセスパターンのまま変更不要

### 実バグ修正（Task4）

1. `energy_score`のMega_Lucario_ex/Riolu分岐に、相手がex無効化持ち（Crustle/Sylveon）のときの`-150`減点を追加（Ogerpon_exの`+150`ボーナスと対称化）
2. `_score_card_option`のATTACH_FROMケース（メガルカリオexの通常技「アクセルジャブ」自身の効果に対応する選択コンテキスト）が`op_active_nullifies_ex`を`energy_score`へ渡し忘れていた転送漏れを修正
3. `_score_attach_option`のRock_Fighting_Energyへの「アクティブ優先+500」ボーナスが、相手がex無効化持ち・対象がexのときは抑制されるよう修正

### その他（Task5・6）

- `tests/test_lucario_attacker_energy_consistency.py`（新規）：`calc_attack_plan`の手打ちエネルギー要求・ダメージ値を`data/competition/EN_Card_Data.csv`のカード原文と突き合わせるテスト
- `scripts/build_lucario_submission_main.py`（新規）：`constants.py`+`combat.py`+`main.py`を結合しKaggle提出用の単一ファイルを生成するビルドスクリプト

## テスト結果

`uv run pytest -q`でリポジトリ全体561件全PASS（既存541件＋新規20件）。各タスクは独立したサブエージェントが実装し、タスクごとにレビューを実施（全6タスク承認）。

## 最終ブランチ全体レビュー

- 1回目（`e7525e0..dc89074`）: Ready to merge = With fixes。Critical/Important無し。Minor4件のうち2件（`main.py`の未使用`EnergyType`import・ビルドスクリプトの`cg.api`生存陽性テスト欠如）を`f118ced`で修正。残り2件（`EPSILON`/`_rng`の`combat.py`/`main.py`間の重複は正当な設計判断、Task4-1の`attacker1=True`複合ケース未テストは算術的に安全）は対応不要と判定
- レビュー結果: `docs/reviews/20260720-lucario-combat-split-energy-score-fix-final-review.md`

## 未対応・次回持ち越し

- `docs/reviews/20260720-lucario-combat-decision-logic-audit.md`で発見されたが今回スコープ外とした項目：
  - RETREATスコア式へのHP温存観点の追加（新しい設計判断が必要、別途ブレスト）
  - ソルロックの「弱点・抵抗力を無視する」効果が`_calc_attack_damage`に未実装（Crustleとは無関係の軽微な潜在バグ）
- `all_attack()`/CSVベースの本格的なアタッカーテーブル化（2026-07-07に中断した案。Task5のテストが将来の足がかりになる）
- Kaggleへのアップロード・再提出・スコア推移確認はユーザー側で実施
