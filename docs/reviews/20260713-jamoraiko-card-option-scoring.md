# ジャモライコ OptionType.CARD スコアリング追加 レビュー結果

- 日付: 2026-07-13
- 対象ブランチ: `feature/jamoraiko-card-option-scoring`（mainへFFマージ済み、`75e0a7a..8c40868`）
- 設計書: `docs/superpowers/specs/2026-07-13-jamoraiko-card-option-scoring-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-13-jamoraiko-card-option-scoring.md`
- 実装サマリー: `docs/implementations/20260713-jamoraiko-card-option-scoring.md`

## タスク別レビュー（サブエージェント駆動開発）

全6タスクをサブエージェント駆動開発で実装。各タスクは個別にSpec Compliance（仕様準拠）とTask quality（品質）の2軸でレビューし、承認後に次タスクへ進んだ。

| Task | 内容 | 結果 |
|---|---|---|
| 1 | `PokemonLine`/`POKEMON_LINES`テーブル + `_score_setup_active` | 1回で承認 |
| 2 | `_is_attack_ready`/`_score_switch_target` | 1回で承認（実装中に計画のテスト期待値の計算ミスを発見・修正） |
| 3 | `_score_search_candidate`（TO_HAND/TO_BENCH） | 1回で承認 |
| 4 | `_score_discard_candidate`（DISCARD） | 1回で承認（コミットメッセージの軽微なtypoのみ） |
| 5 | `_score_card_option`ディスパッチャ + `_score_option`統合 | Important1件（DISCARDディスパッチの直接テスト欠落）→修正・再承認 |
| 6 | 校正ノートブック再ビルド・実装サマリー作成 | Important1件（テスト件数の誤記「28件」→正しくは「29件」）→修正・再承認 |

## 最終ブランチ全体レビュー（Opusモデル）

1回目（`75e0a7a..212f032`）：Ready to merge = With fixes。Critical無し。

- **Important1件**：`agent()`エントリポイント経由で`OptionType.CARD`が機能することを検証する統合テストが存在しない。0.015事故（校正実験でイオナサンプル相手に勝率0.015）の本質は「配線が黙って無反応になる」という失敗モードだったため、これを直接ガードするテストが必要と判断
- **Minor（マージ前推奨と明記された1件）**：`_score_switch_target`に非Pokemon防御（`isinstance`ガード）がない。実績エージェント`grimmsnarl_agent`が同種のガードを持っており、想定外カード型でのクラッシュを防ぐため追加を推奨
- 残りのMinor2件（カード→コンテキスト対応の実バトルログ未検証、破棄保護リストの網羅性）は次サイクル送りと判断

### 修正1と再レビューでの追加発見

修正1（`d2ef894`）でImportant1件・Minor1件を反映。あわせて`tests/conftest.py`の`make_main_obs`が`hand`を常に空リストで無視していたバグを発見・修正（`context`/`select_type`引数を追加し他コンテキストのobs_dict生成にも対応）。

再レビューで**新たなImportant1件**を発見：追加した`agent()`統合テストのアサーションが、`sorted(..., reverse=True)`の安定ソートによるタイブレークで、スコアリングの配線が丸ごと壊れて全オプションが同点0点になった場合でも`index 0`が返るためテストが偽陽性でPASSしてしまう構造だった（＝防ごうとした0.015事故クラスの回帰を実際には検出できない）。

### 修正2と最終確認

修正2（`8c40868`）で、勝者カードをindex 0以外（index 1）に配置しアサーションを`[1]`に変更。配線を意図的に一時破壊して実際にテストがREDになることを検証済み。

最終確認レビュー（`d2ef894..8c40868`）：**Ready to merge = Yes**。Critical/Important/Minorとも指摘なし。

## テスト件数の推移

419（着手前）→ 422 → 430 → 436 → 442 → 448（Task1〜5） → 450（最終レビュー対応の統合テスト2件追加）

## 未検証・次サイクル持ち越し

- カード→コンテキストの対応関係（特につりざおMAXがTO_HANDを発行するかTO_DECKか等）は実バトルログでの裏取りが未実施
- 破棄保護リスト（`_score_discard_candidate`）はBoss/Lillie/Max_Rodのみ保護しており、ハッコウシティ・カナリィ等は汎用スコアのまま。チューニング余地あり
- ユーザーがKaggleで校正ノートブック（`jamoraiko_vs_iono_experiment.ipynb`）を再実行し、勝率が0.015からどこまで改善したかを確認する必要がある（本レビューのスコープ外）
