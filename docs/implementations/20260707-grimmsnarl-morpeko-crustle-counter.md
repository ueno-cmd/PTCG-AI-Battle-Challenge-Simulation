# 実装サマリー：グリムスナールexデッキ Crustle対策（モルペコ優先切り替え）

**実装日：** 2026-07-07
**進め方：** ユーザー指定により軽量直接実装（設計書・計画書ファイル作成は省略、フルレビューも省略）
**参照：** ルカリオexデッキで実装済みのCrustle対策（`docs/implementations/20260707-crustle-counter-ogerpon-priority.md`）と同じ発想を、グリムスナールexデッキの構造に合わせて移植

## 背景

グリムスナールexデッキはex技持ちのGrimmsnarl_ex（Shadow Bullet）・Fezandipiti_ex（Cruel Arrow）と、非exのMarnie_Morpeko（Spiky Wheel）を採用している。相手がCrustle（イワパレス、Card ID 345、特性「ふしぎな岩の宿／しんぴのいしやど」＝相手の「ポケモン【ex】」の技ダメージを無効化）の場合、ex技持ち2体の攻撃は実質無意味になる一方、非exのモルペコは通常通りダメージを与えられる。ルカリオexデッキでMega_Lucario_exのダメージを0として評価しオーガポンexへ切り替える対策を実装済みだったため、同じ考え方をグリムスナールexデッキにも適用した。

なお、グリムスナールexデッキの`main.py`はルカリオex側の`calc_attack_plan`（アタッカー候補をループしてスコア最大の組み合わせを選ぶ構造）とは異なり、アクティブなポケモンの技を`_score_attack`で単純にスコアリングする構造のため、関数をそのまま移植するのではなく、既存構造に合わせて等価な効果を実装した。

## 変更内容（`src/grimmsnarl_agent/main.py`）

- **定数追加**：`Crustle = 345`、`EX_ATTACKER_IDS = {Grimmsnarl_ex, Fezandipiti_ex}`
- **`FieldState`**：`op_active_id`（相手アクティブのカードID）・`my_active_id`（自分アクティブのカードID）を追加し、`_collect_field_state`で収集
- **`_score_attack`**：`attack_id`がShadow Bullet／Cruel Arrow（ex技）かつ`fs.op_active_id == Crustle`なら`-1`を返す（ダメージ0として評価し、無意味な攻撃として扱う）。Spiky Wheel（非ex）はこの対象外で従来通り評価される
- **`agent()`のRETREATスコアリング**：既存の「Grimmsnarl ex瀕死なら撤退」条件に加え、「アクティブがex攻撃者（`EX_ATTACKER_IDS`）でCrustle対面、かつベンチにモルペコがいる」場合も撤退を優先（スコア3000）する条件を追加
- **`_score_own_switch_target`**：`fs`引数を追加。Crustle対面時はモルペコのSWITCH/TO_ACTIVEスコアを最優先（20000+エネルギー数×2、Grimmsnarl_exの基本スコア10000超を上回る）に引き上げ。Crustle以外の対面では従来のスコアリング（Grimmsnarl_ex優先）を維持。呼び出し側（`_score_card_option`のSWITCH／TO_ACTIVE own分岐）も`fs`を渡すよう修正

## テスト結果

- 追加テスト計6件（`tests/test_grimmsnarl_agent.py`）：
  - `_score_attack`：`test_shadow_bullet_nullified_when_opponent_is_crustle`、`test_cruel_arrow_nullified_when_opponent_is_crustle`、`test_spiky_wheel_not_nullified_when_opponent_is_crustle`
  - `_score_card_option`（SWITCH）：`test_switch_morpeko_outranks_grimmsnarl_when_opponent_is_crustle`、`test_switch_grimmsnarl_still_preferred_when_opponent_is_not_crustle`（Crustle以外では副作用がないことの確認）
  - `agent()`統合テスト：`test_retreats_to_morpeko_when_opponent_is_crustle`
  - 既存の`FieldState`直接構築テスト（6箇所）は新規必須フィールド追加に伴い`my_active_id`/`op_active_id`を明示的に追加して更新
- リポジトリ全体：`uv run pytest -q` で**259 passed**（全件PASS、回帰なし）を確認

```
$ uv run pytest -q
........................................................................ [ 27%]
........................................................................ [ 55%]
........................................................................ [ 83%]
...........................................                              [100%]
259 passed in 0.11s
```

## 未対応事項

- モルペコが実際にCrustleの特性を貫通してダメージを与えられたかは実バトルログで未確認（次にCrustle系デッキと対戦した際に要検証）
- 今回はユーザー指定により軽量実装のためフルのサブエージェントレビューは実施していない
- デッキCSV生成・Kaggle再提出はユーザー判断待ち
