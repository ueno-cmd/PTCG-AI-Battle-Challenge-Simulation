# ジャモライコ OptionType.CARD スコアリング追加 実装サマリー

- 日付: 2026-07-13
- 設計書: `docs/superpowers/specs/2026-07-13-jamoraiko-card-option-scoring-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-13-jamoraiko-card-option-scoring.md`

## 背景

校正実験（`jamoraiko_vs_iono_experiment.ipynb`、200試合）でジャモライコの勝率が0.015という
壊滅的な結果になった。原因は`src/jamoraiko_agent/main.py`の`_score_option`に
`OptionType.CARD`のケースが一つも実装されておらず、`SETUP_ACTIVE_POKEMON`/`SWITCH`/
`TO_ACTIVE`/`TO_HAND`/`TO_BENCH`/`DISCARD`という多くの重要な意思決定が全て
「エンジンが提示した順番の先頭を機械的に選ぶだけ」になっていたこと。

## 実装内容

データ駆動型（`POKEMON_LINES`テーブル）で6コンテキスト分のスコアリングを新規実装：

- `PokemonLine`/`POKEMON_LINES`：ポケモンごとの優先度データ（進化前ID・場に置きたい上限・
  初期アクティブ優先度）
- `_score_setup_active`：初期アクティブ選択（ビリリダマ＞タケルライコex＞ズピカ/カイデン）
- `_is_attack_ready`/`_score_switch_target`：交代先選択（自分側は攻撃可能なポケモンを優先、
  相手側＝ボスの指令は現在の攻撃プランで確定KOできるベンチを最優先）
- `_score_search_candidate`：TO_HAND/TO_BENCH共通のサーチ優先度（上限超過は減点、
  進化ポケモンは進化前不在なら減点）
- `_score_discard_candidate`：DISCARD（ハイパーボール・カナリィのコスト）。余剰札は気軽に
  切り、キーカード・ACE SPECは温存
- `_score_card_option`：上記をコンテキストで振り分けるディスパッチャ。`_score_option`の
  `match`文に`case OptionType.CARD:`を追加して接続

## テスト

`tests/test_jamoraiko_agent.py`に28件のテストクラス（`TestScoreSetupActive`/
`TestIsAttackReady`/`TestScoreSwitchTarget`/`TestScoreSearchCandidate`/
`TestScoreDiscardCandidate`/`TestScoreCardOptionDispatch`）を追加。
リポジトリ全体`uv run pytest -q`で全件PASS。

## 未検証（次回以降）

- `POKEMON_LINES`の優先度の具体的な数値（300/200/150/180等）は初期値であり、微調整の余地がある
- 校正ノートブックの再実行はユーザーがKaggle上で実施し、勝率が0.015からどこまで改善したかを確認する
