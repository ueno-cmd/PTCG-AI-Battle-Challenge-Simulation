# ジャモライコエージェント TrainerCardPolicyレジストリ導入 実装サマリー

## 背景

`src/jamoraiko_agent/main.py`の`_score_play_option`関数は、トレーナーズカードごとのif/elif分岐が11個並ぶ形で肥大化していた。今後ドラパルドex等の新デッキでも同じ設計パターンを踏襲できるよう、`TrainerCardPolicy`レジストリパターン（`{card_id: policy_instance}`の辞書ディスパッチ）へリファクタリングした。**振る舞いは一切変更しない**純粋なリファクタリングとして実施。

- 設計書: `docs/superpowers/specs/2026-07-14-jamoraiko-trainer-card-policy-registry-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-14-jamoraiko-trainer-card-policy-registry.md`
- ブランチ: `feature/jamoraiko-trainer-card-policy-registry`（通常のfeatureブランチ、worktreeは不使用）

## 実装内容

`superpowers:subagent-driven-development`で1タスクを実施：

1. `PlayScoringContext`データクラス（`obs`/`o`/`my_index`/`fs`/`my_state`/`plan`をまとめる）を新設
2. `TrainerCardPolicy`（ABC、`play_score(ctx) -> int`）と4つの具象クラスを実装
   - `FixedScorePolicy`：固定スコアを返すだけのカード用（ハイパーボール等）
   - `LillieDeterminationPolicy`：山札セーフティを判定（山札が薄いと-1）
   - `BossOrdersPolicy`：確定KO時に高スコア（8800）
   - `EnergySwitchPolicy`：既存`ENERGY_POLICY`へ委譲
3. `TRAINER_CARD_POLICIES`辞書に11枚のトレーナーズカードを登録
4. `_score_play_option`をレジストリ参照の薄いディスパッチャに縮小
   （`data.cardType == CardType.POKEMON`のケースはレジストリ対象外のまま現状維持）

## 実装中に発覚した問題と対処

初回実装（コミット`19fce1c`）で、`PlayScoringContext`のフィールド`o: "Option"`/`my_state: "PlayerState"`がクォート付き型注釈になっていた。これは校正ノートブック（`scripts/build_jamoraiko_vs_iono_notebook.py`が`exec()`で`sys.modules`未登録の動的モジュール名前空間に`main.py`を読み込む方式）で過去に発生した`AttributeError: 'NoneType' object has no attribute '__dict__'`クラッシュ（[[feedback_dataclass_string_annotation_exec]]参照）と同じパターンを再現することが、コントローラーの事前精査で判明した。

実装者（サブエージェント）は当初、計画の対象外だった`scripts/build_jamoraiko_vs_iono_notebook.py`に`sys.modules`登録＋`PlayerState`用のプレースホルダー（`type(None)`）を追加する場当たり的な対処をしていた。これはコントローラーが差分レビューで検出し、ユーザーに2案を提示：

1. **（採用）** `main.py`の既存`from cg.api import (...)`に`Option`/`PlayerState`を追加しクォートを外すだけ
2. 実装者の場当たり対処（ビルドスクリプト側）をそのまま採用

ユーザーは案1を選択。修正コミット（`bc79250`）でビルドスクリプトへの変更を完全に撤回し、`main.py`のみで根本解決した（過去の`PokemonLine.pre_evo_id: int | None`と同じ「dataclassフィールドはクォート付き注釈を使わない」規約に合わせる形）。

## テスト結果

- 新規テスト8件追加（`TestTrainerCardPolicies`7件＋`test_unregistered_card_defaults_to_1000`1件）
- 既存の`TestScorePlayOption`5件は無変更のままPASS（レジストリ経由でも同じ結果を返すことの回帰確認）
- リポジトリ全体 `uv run pytest -q`：499件→507件、全PASS

## コミット範囲

`081ddd4..bc79250`（feature/jamoraiko-trainer-card-policy-registryブランチ、2コミット、main未マージ）
- `19fce1c` refactor: _score_play_optionのif分岐をTrainerCardPolicyレジストリに置き換え（振る舞い変更なし）
- `bc79250` fix: PlayScoringContextのクォート付き型注釈を解消しビルドスクリプトへの場当たり対処を撤回

## レビュー結果

タスク単位レビュー・最終ブランチ全体レビューともに Ready to merge = Yes（Critical/Important無し）。詳細は`docs/reviews/20260714-jamoraiko-trainer-card-policy-registry.md`参照。

## 未対応（次回以降の課題）

- Minor（対応不要と判断）：`data.cardType == CardType.POKEMON`判定がレジストリlookupより前に来る実装になった点は、レジストリ登録カードが非POKEMONである前提に暗黙的に依存している（現状のcard_tableでは問題なし。将来カード追加時のコメント補足は任意）
- Minor（対応不要と判断）：`PlayScoringContext`の`obs`/`o`/`my_index`は現行ポリシーでは未使用（将来の拡張性のための設計、YAGNI違反ではないと判断）
- マージ後、ユーザーがKaggle上でノートブックを再実行し、振る舞いが変わっていないこと（勝率が今回の変更前後で大きく変動しないこと）を確認する必要あり
- 次回セッションで、フラッシュドロー依存の調整・`OptionType.ABILITY`分岐へのパターン展開・resilience調査（ドラパルドex・イワパレス・フーディン対策）のいずれに進むかをユーザーと判断
