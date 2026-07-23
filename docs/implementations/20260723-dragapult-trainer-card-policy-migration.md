# ドラパルトex PLAY分岐 TrainerCardPolicy移植 実装サマリー

## 概要

`src/dragapult_agent/main.py`の`agent()`内`OptionType.PLAY`分岐にあった12枚のトレーナーズカード（グッズ/サポート/スタジアム）のif/elif連鎖を、`src/lucario_agent/main.py`で実運用中の`TrainerCardPolicy`パターン（ABC＋登録辞書）へ、振る舞いを一切変えずに移植した。

- 設計書：`docs/superpowers/specs/2026-07-23-dragapult-trainer-card-policy-migration-design.md`
- 実装計画：`docs/superpowers/plans/2026-07-23-dragapult-trainer-card-policy-migration.md`
- レビュー結果：`docs/reviews/20260723-dragapult-trainer-card-policy-migration.md`

## 実装内容

`superpowers:subagent-driven-development`で8タスクに分解し、タスクごとに新規サブエージェントを割り当てて実装・タスクレビューを実施した。

1. スキャフォールディング：`PlayTrainerCardContext`（dataclass）・`TrainerCardPolicy`（ABC）・`FixedScorePolicy`・空の`TRAINER_CARD_POLICIES`辞書・`_score_play_trainer_card`ディスパッチャを追加
2. 固定スコア2枚（Unfair_Stamp・Crushing_Hammer）を`FixedScorePolicy`で登録
3. `SupporterSelectedPolicy`（`no_draw_gate`パラメータ付き）を追加し、Boss_Orders・Lillie_Determinationを登録
4. `RareCandyPolicy`・`TeamRocketWatchtowerPolicy`を追加・登録
5. `NightStretcherPolicy`を追加・登録
6. `no_draw`ゲート付き5枚（Buddy_Buddy_Poffin・Ultra_Ball・Poke_Pad・Crispin・Brock_Scouting）を、専用クラス3つ＋`SupporterSelectedPolicy(no_draw_gate=True)`の使い回しで移植
7. カバレッジ回帰テスト（`TRAINER_CARD_POLICIES`の登録カードIDが過不足なく12枚と一致することを保証）を追加
8. `agent()`のPLAY分岐にディスパッチャを配線し、旧if/elif連鎖（トレーナーズカード部分のみ）を削除

**対象外（今回のスコープ外）**：ポケモンカード分岐（Dreepy/Fezandipiti_ex/Latias_ex/Budew/Meowth_ex）と`hand_score()`関数は構造がより複雑なため据え置き。RL/オフラインログ観察トラックも今回は着手せず。

## 発見事項：暗黙のno_drawゲート

現行のif/elif連鎖には、カードID指定の無い`elif no_draw: score = -1`という分岐が中盤に存在し、これより後ろに書かれているカード（Buddy_Buddy_Poffin・Ultra_Ball・Poke_Pad・Crispin・Brock_Scouting）だけが暗黙に山札残り僅少時に使用不可となっていた。これより前のカードは影響を受けない。移植にあたり、この5枚だけに`if ctx.no_draw: return -1`を明示的に追加し、暗黙の副作用をコード上で可視化した。挙動そのものは変更していない。この設計が実際のゲーム戦略として妥当かどうかは未検証のままバックログに残した。

## テスト

- `uv run pytest tests/test_dragapult_agent.py -v`：43件全PASS（既存14件＋新規29件）
- `uv run pytest -q`（リポジトリ全体）：644件PASS、失敗10件・エラー12件（いずれも本タスクと無関係な、1.3GBのバトルログ・unity-catalogデータを必要とするETL系テストで、着手前から存在）
- 移行前後で対象12カード全ての判定が一致することを確認する回帰テストを新設し、[[feedback_agent_dispatch_coverage]]の教訓（ジャモライコの`OptionType.CARD`未実装事故）に対応

## レビュー結果

各タスクの個別レビュー（8件）全てCritical/Important無しでApproved。最終ブランチレビュー（Opusモデル）もReady to merge = Yes（Critical/Important無し、Minor2件）。

Minor指摘への対応：
1. `_score_play_trainer_card`の未登録カードフォールバックが、旧コードの`no_draw`時-1挙動と異なる点（現行デッキでは到達しないが将来カード追加時の見落とし防止）→ docstringに明記済み（対応済み）
2. デッキ内の全トレーナーズカードが登録済みかを横断チェックするテストの提案 → バックログ項目として次回以降に持ち越し

## 運用

- `superpowers:subagent-driven-development`のブランチ`worktree-majestic-pondering-teapot`をmainへローカルマージ済み（コミット`8391fa4`）
- push・Kaggle再提出はユーザー判断で別途実施（本タスクでは未実施）
- 提出用notebook`notebooks/submissions/dragapult_agent_submission.ipynb`は再生成済み（`.ipynb`は`.gitignore`対象のため未コミット）
