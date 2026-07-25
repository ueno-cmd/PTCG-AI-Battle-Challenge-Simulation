# ルカリオexデッキ Judge増量・ポケモンいれかえ/ふうせん採用 実装サマリー

**関連設計書：** `docs/superpowers/specs/2026-07-25-lucario-judge-switch-airballoon-design.md`
**関連計画書：** `docs/superpowers/plans/2026-07-25-lucario-judge-switch-airballoon.md`
**ブランチ：** `feature/lucario-judge-switch-airballoon`（コミット範囲 `fae92fb..ab44807`、5コミット）

## 背景

ドラパルトexのスコア低迷を受け、堅実な戦績のルカリオexへ再びフォーカスする方針転換の一環。以下2つの既知ギャップに対応する低リスク改修（ゲノセクトのエースカンセラー・マクノシタ/ハリテヤマ系統・ロケット団の監視塔は新規ロジックが必要でリスクが高いため意図的にスコープ外）：

1. **Judgeの資源枯渇問題**（2026-07-19実測検証で判明）：デッキ内2枚のみのため、序盤の自己都合トリガーが終盤の防御用途を食い潰す
2. **自発的な交代手段の欠如**（2026-07-20/25実測検証で判明）：ボスの指令は相手専用で、自分から交代する手段が一切ない

ユーザーが発見した実在のジムバトル優勝デッキを参考に、既存の判断パターンを流用できる低リスク枠（Judge増量・ポケモンいれかえ・ふうせん）のみを今回のスコープとした。

## 実装内容

`superpowers:subagent-driven-development`で4タスクをTDD形式で実装し、最終ブランチレビュー（Opusモデル）の指摘を1回の修正waveで反映した。

### Task 1（コミット`7a082e2`）：デッキ構成の入れ替え・カードID定数の追加

`decks/lucario_20260621.py`から単発サポート3種（Hilda/Wally's Compassion/Ciphermaniac's Codebreaking）を削除し、Judgeを2→3枚に増量、ポケモンいれかえ(Switch, ID1123)・ふうせん(Air Balloon, ID1174)を新規採用（60枚のまま収支ゼロ）。`src/lucario_agent/constants.py`に`Switch`・`Air_Balloon`定数を追加。

### Task 2（コミット`d9933f4`）：`_analyze_main_options`にSwitch保持時のcan_switch判定を追加

RETREATがエネルギー不足で選択肢に出せない局面でも、ポケモンいれかえがあれば`calc_attack_plan`がベンチアタッカーへの交代を検討できるよう、`_analyze_main_options`のPLAY分岐に`elif card.id == Switch: can_switch = True`を追加。2026-07-03の軽量化リビルドで削除された旧ロジックの復活にあたる（ブランチ作業中に計画レビューで発覚し追加承認を得た）。

### Task 3（コミット`0a91c20`）：`SwitchPolicy`新設・`TRAINER_CARD_POLICIES`登録

既存の`_score_retreat_option`と同条件で発火するが、にげるコスト(エネルギー破棄)を伴わない分RETREATより+100優先する`SwitchPolicy`を新設。条件不成立時(-1)に誤って+100してしまわないよう`base > 0`のガードを実装。

### Task 4（コミット`a9a6e7a`）：ふうせん(Air Balloon)のATTACHスコアリング分岐を追加

`_score_attach_option`にHero's Capeと同型の分岐を追加。にげるコストが最大(2)のメガルカリオex・リオルを優先して装着先に選ぶ。

### 最終レビュー指摘の修正（コミット`ab44807`）

最終ブランチレビュー（Opusモデル）で、4タスクを組み合わせて初めて見える2件のImportant指摘が見つかり、1回の修正waveで反映した：

1. **Hero's CapeとAir Balloonのスコアが同点だった問題**：両方とも同一ポケモンに対して同じスコア（メガルカリオex=7200、リオル=7100）を返しており、どちらが1つしかない「どうぐ」枠を取るかが実質ランダムだった。Air Balloonのベーススコアを7000→6900に下げ、恒久バフのHero's Capeが常に優先されるよう修正
2. **Air Balloon装着後、SwitchPolicyの「+100優先」の前提が崩れる問題**：Air Balloonでにげるコストが実質0になったポケモンでは、RETREATもエネルギーを失わなくなるのに、SwitchPolicyは常に+100優先し続けていた。アクティブの実効にげるコスト（`card_table[my_active.id].retreatCost`からAir Balloon装着分×2を引いた値）を計算し、0以下ならRETREATを優先(`base - 100`)するよう修正

## テスト結果

- リポジトリ全体：`uv run pytest -q`で**730件PASS**（既存726件＋今回追加分、失敗0件）
- 各タスク・最終レビューともにCritical/Important指摘は全て解消済み

## 提出用notebook・deck.csv

- `uv run python scripts/build_lucario_submission_notebook.py`実行済み、最終修正（Air Balloon同点解消・SwitchPolicy修正）を含む最新版を確認済み
- `uv run python scripts/build_deck.py decks/lucario_20260621.py`実行済み（`output/deck_20260725_152334.csv`、Judge3枚・Switch1枚・Air Balloon2枚を含む60枚を確認済み）
- Kaggleアップロード・再提出はユーザーが別途実施

## スコープ外（意図的に対象としないもの）

- ゲノセクトのエースカンセラー・マクノシタ/ハリテヤマ系統・ロケット団の監視塔・マキシマムベルト（設計時点で高リスク枠として除外）
- `TRAINER_CARD_POLICIES`内のHilda/Ciphermaniac_Codebreaking/Wally_Compassion登録、`WallyCompassionPolicy`クラス、`_deck_consumption`のHilda分岐は、カードがデッキから削除されたことで到達不能なデッドコードになっているが、デッキ変更のみに範囲を絞るため今回は削除しなかった（最終レビューで「テストが通り続けるのに実行されない状態は誤った安心感を生む」との指摘あり。対応要否はユーザー判断待ち）
- Air Balloon分岐がACTIVE/BENCHを区別していない点、Hero's Cape分岐とAir Balloon分岐のif/elif順序不一致、`constants.py`の`=`位置ずれは、いずれもMinor（実害小・対応不要）として記録
