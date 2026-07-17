# ルカリオexエージェント TrainerCardPolicy化＋3件のロジック修正 実装サマリー

## 背景

`src/lucario_agent/main.py`の`_score_play_option`（トレーナーズカードのif/elif連鎖）を、ジャモライコと同じ`TrainerCardPolicy`レジストリパターンでクラス化した。その過程で、実バトルログ（86363073, 86197001, 86241854, 86295193, 86295949等）で確認済みの2つのロジックミス（リーリエの決意が手札の質を無視して固定スコア／ハイパーボールが主要ポケモン確保後も歯止めなく撃ち続ける）と、`SETUP_ACTIVE_POKEMON`でのオーガポンex優先度欠如（86197001戦で実際の敗因と特定済み）を修正した。

- 設計書: `docs/superpowers/specs/2026-07-17-lucario-trainer-card-policy-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-17-lucario-trainer-card-policy.md`
- ブランチ: `feature/lucario-trainer-card-policy`（通常のfeatureブランチ、worktreeは不使用）

## 実装内容

`superpowers:subagent-driven-development`で6タスクを実施（各タスクごとに実装→タスクレビュー→最終ブランチ全体レビューの流れ）：

1. **スキャフォールディング**：`PlayScoringContext`データクラス（`_score_play_option`の既存引数を集約）、`TrainerCardPolicy`（ABC、`play_score(ctx) -> int`）、`FixedScorePolicy`を新設。まだ未配線
2. **レジストリ移行（振る舞い変更なし）**：11枚のトレーナーズカードを`TRAINER_CARD_POLICIES`辞書＋個別ポリシークラスに移行し、`_score_play_option`本体をレジストリ経由の薄いディスパッチャに置き換え
3. **リーリエの決意の手札質ガード**：手札にRiolu/Mega_Lucario_ex/Ogerpon_ex/Solrock/Lunatoneのいずれかがあれば`-1`（温存）を返すよう修正
4. **ハイパーボールの確保済み抑制**：`already_found`（Riolu+Mega_Lucario_ex+Ogerpon_exの場+手札合計）が3以上ならスコアを`100`（大幅抑制、-1ではなく他に選択肢が無ければ撃てる余地は残す）に修正
5. **SETUP_ACTIVE_POKEMONのオーガポンex優先度**：Ogerpon_exに`1`点を付与し、Lunatone（0点）との同点を解消。Riolu(3点)/Solrock(2or4点)には引き続き劣後
6. **対象外箇所へのコメント追記**：SWITCH/TO_ACTIVEでの`current_plan`陳腐化リスク、`calc_attack_plan`のアタッカーテーブル化リファクタ検討事項（2026-07-07にブレスト中断のまま）をdocstring/コメントで明記。機能変更なし

## テスト結果

- 新規テスト16件追加（Task1:2件、Task3:6件、Task4:3件、Task5:5件）
- 既存テストは全てそのままPASS（Task2は完全な振る舞い保存リファクタリングとして確認済み）
- リポジトリ全体 `uv run pytest -q`：495件→511件、全PASS

## コミット範囲

`001f2bf..928dbb1`（feature/lucario-trainer-card-policyブランチ、6コミット、main未マージ）
- `5505d53` feat(lucario): add TrainerCardPolicy scaffolding (PlayScoringContext/ABC/FixedScorePolicy)
- `151e2fe` refactor(lucario): migrate _score_play_option to TrainerCardPolicy registry (behavior-preserving)
- `983a400` fix(lucario): suppress Lillie's Determination when hand already has a key Pokemon
- `164a81e` fix(lucario): suppress Ultra Ball once key Pokemon are already secured
- `33ccdb1` fix(lucario): prioritize Ogerpon ex over Lunatone in SETUP_ACTIVE_POKEMON
- `928dbb1` docs(lucario): annotate SWITCH/TO_ACTIVE staleness risk and calc_attack_plan table-ization backlog

## レビュー結果

タスク単位レビュー6件・最終ブランチ全体レビューともに Ready to merge = Yes（Critical/Important無し）。詳細は`docs/reviews/20260717-lucario-trainer-card-policy.md`参照。

## 未対応（次回以降の課題）

- Minor（次回持ち越し）：`PremiumPowerProPolicy`が「手札にリーリエの決意があれば温存」判定を続けているが、Task3のリーリエ抑制ロジックにより両者が同時にサプレスされ、支援者を1枚も出せないターンが発生しうる（低頻度・保守的な結果=キーポケモンは守られるだけなので緊急度は低いと判断）
- Minor（次回持ち越し）：Task2で固定スコアに移行したカード（Pokegear/Night_Stretcher/Hilda/Ciphermaniac_Codebreaking）専用の回帰テストは無く、既存テストによる暗黙カバーのみ
- デッキCSV再生成・Kaggle再提出でスコア変化を確認する（ユーザー側で別途実施、要明示確認）
- ジャモライコ側`LillieDeterminationPolicy`の同種バグ修正（次回持ち越し、ユーザー判断で今回スコープ外）
- Alakazam系対策・RETREAT未実装への対応（次回セッション）
