# レビュー結果：グリムスナールex 立ち往生解消＋山札セーフティ

- 日付: 2026-07-12
- 対象範囲: `e0e1666..c87c1f9`（6コミット、feature/grimmsnarl-promotion-deck-safety）
- レビュー方式: サブエージェント駆動開発（タスク別レビュー6回＋最終ブランチ全体レビュー1回・Opusモデル）
- 設計書: `docs/superpowers/specs/2026-07-12-grimmsnarl-promotion-deck-safety-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-12-grimmsnarl-promotion-deck-safety.md`
- 実装サマリー: `docs/implementations/20260712-grimmsnarl-promotion-deck-safety.md`

## 最終判定

**Ready to merge = Yes**（Critical/Important無し、Minorのみ）

- 4修正は全て`FEATURE_FLAGS`で正しくゲートされ、全OFF時は現行挙動と完全一致（コード・テスト両面で保証）
- リポジトリ全体テスト341件PASS（開始時303件＋新規38件）
- ワザコスト（`ATTACK_COSTS`）はEN_Card_Data.csv実測値と一致することをタスクレビュアーが独立検証
- A/B実験ノートブック（9セル）はセル間依存・自己完結性（新規import無し）を実ファイルで検証済み

## タスク別レビューの経過

| Task | 範囲 | 判定 | 特記事項 |
|---|---|---|---|
| 1 基盤 | e0e1666..3bef7a0 | 承認 | コスト値をCSV原本と突合確認 |
| 2 昇格 | 3bef7a0..db120b2 | 承認 | 全9テストの期待値を手計算検証 |
| 3 ボスゲート | db120b2..e06e947 | 承認 | 既存6テスト更新が前提条件追加のみ（アサーション不変）を確認 |
| 4 山札セーフティ | e06e947..6202d1e | 承認 | 全10テストの算術検算＋カード効果テキスト突合 |
| 5 A/Bビルダー | 6202d1e..7e4df4d | 承認 | **計画側の誤記`grimmsnarl_agent()`→`agent()`を実装者が発見・修正**（controller裏取り済み） |
| 6 回帰・サマリー | 7e4df4d..c87c1f9 | controller直接検証 | 341件PASS・両ノートブック再生成確認 |

## 最終レビューのMinor指摘（マージブロックなし）

1. **ready Yveltal（1エネ・20ダメ）が未準備オーロンゲより交代先で優先される境界挙動が未テスト**
   （12000+20=12020 > 10000+）。stall回避としては設計意図通りだが、次サイクルでテスト追加＋意図確定を推奨
2. **Secret Boxのゲート通過後スコアが汎用1000のまま**（専用スコア枝なし）。ACE SPECサーチとしては
   優先度が低すぎる可能性。次サイクルでの対応を推奨（今回スコープ外として記録）
3. `_expected_damage`のif連鎖と`ATTACK_COSTS`の二重管理 → Morpekoがエネ依存計算を要するため現状維持が妥当

## 持ち越しMinor事項のトリアージ（9件全てブロック不要）

タスクレビューからの持ち越し9件は最終レビューで全件トリアージ済み。マージ前修正が必要なものは無し。
詳細は`.superpowers/sdd/progress.md`の本計画セクションを参照。

## 実務上の注意（Kaggle投入前）

- A/Bノートブックは.gitignore対象のため、投入時は`uv run python scripts/build_grimmsnarl_feature_ab_notebook.py`で
  再生成した最新の`.ipynb`を使うこと（main.py改修が自動追従する）
- 実機では1セル目から順に流し、`FEATURE_FLAGS`/`agent`が埋め込みmain.pyと一致することを確認してから
  1000試合を回すこと

## 次サイクル持ち越し事項

1. ready Yveltalの交代先優先の意図確定＋テスト追加（Minor#1）
2. Secret Boxの`_score_play`専用スコア枝（Minor#2）
