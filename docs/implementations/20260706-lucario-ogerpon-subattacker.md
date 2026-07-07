# 実装サマリー：ルカリオexデッキ サブアタッカー「オーガポン いしずえのめんex」導入

**実装日：** 2026-07-06〜07-07
**関連設計書：** `docs/superpowers/specs/2026-07-06-lucario-ogerpon-subattacker-design.md`
**関連計画書：** `docs/superpowers/plans/2026-07-06-lucario-ogerpon-subattacker.md`

## 背景

イワパレス（特性「しんぴのいしやど」：相手の「ポケモン【ex】」からの技ダメージを
受けない）のような、特性で耐性を持つポケモンへの対策が現行のルカリオexデッキ
（Mega Lucario ex / Solrock・Lunatoneのみ）に存在しないことが課題だった。
「オーガポン いしずえのめんex」（Card ID 117）は技「ぶちやぶる」（3エネルギー・
140ダメージ・弱点/抵抗力を計算しない仕様）を持ち、サブアタッカーとして採用する
ことで打点の多様化を図る。

なお、特性の「相手の効果を無視する」部分自体はシミュレータ本体側が処理する
ため、エージェント側の実装対象外とした。

## 変更内容

### デッキ（`decks/lucario_20260621.py`）— commit `5dd2171`

- Solrock (676) を4枚→3枚に削減
- Cornerstone Mask Ogerpon ex (117) を1枚新規採用
- デッキ合計60枚・ACE SPEC（Hero's Cape, 1枚）は変更なし

### エージェントロジック（`src/lucario_agent/main.py`）

- **`calc_attack_plan`（commit `db8c1d4`）**：
  既存のMega Lucario ex / Solrockのif/elif連鎖に、Ogerpon_exの3つ目の分岐を追加
  （3エネルギー必要・base_damage=140固定）。技「ぶちやぶる」は弱点・抵抗力を
  計算しない仕様のため、既存の弱点2倍/抵抗力-30処理を`my_pokemon.id != Ogerpon_ex`
  の条件でオーガポンexのときだけスキップするようにした。

- **`energy_score`（commit `15e17ba`）**：
  オーガポンexのエネルギー充填優先度を追加。3エネ未満（充填中）なら+80、
  さらにルカリオ系統（attacker1）が準備済みなら追加で+40のボーナスを付与し、
  余剰エネルギーをオーガポンexへ回すよう誘導する。グリムスナールexデッキの
  マシマシラ導入時と同じパターンを踏襲。

- **DISCARD保護（commit `cd34765`）**：
  `_score_card_option`の保護対象カードタプル（Riolu, Mega_Lucario_ex, Solrock,
  Lunatone）にOgerpon_exを追加。1枚しか採用していないため、誤ってトラッシュ
  されないようスコア-100で保護する。

## テスト結果

- 今回のTask1〜4で追加したオーガポンex関連テストは計8件：
  - `tests/test_lucario_deck.py`（Task1・2件）：`test_ogerpon_ex_present_with_1_copy`、
    `test_solrock_reduced_to_3`
  - `tests/test_lucario_agent.py` `TestCalcAttackPlan`（Task2・3件）：
    `test_ogerpon_ex_selected_as_attacker_with_3_energy`、
    `test_ogerpon_ex_ignores_weakness`、`test_ogerpon_ex_not_selected_with_insufficient_energy`
  - `tests/test_lucario_agent.py` `TestEnergyScoreOgerponEx`（Task3・2件）：
    `test_charging_gets_bonus_below_3_energy`、`test_attacker1_ready_gives_extra_bonus`
  - `tests/test_lucario_agent.py` `TestDiscardContext`（Task4・1件）：
    `test_protects_ogerpon_ex`
- リポジトリ全体：`uv run pytest -q` を実行し、**248 passed**（全件PASS、
  回帰なし）を確認。

```
$ uv run pytest -q
........................................................................ [ 29%]
........................................................................ [ 58%]
........................................................................ [ 87%]
................................                                         [100%]
248 passed in 0.08s
```

## 未対応事項

- **アタッカー定義のテーブル化（案2）**：`calc_attack_plan`のif/elif連鎖を
  `{id, energy_required, base_damage, ignore_weakness_resistance}`のような
  辞書テーブルに置き換える案は、設計書に将来の検討事項として記載済みだが
  今回は着手しない。現状アタッカーは3種のみでありYAGNIの観点、および
  グリムスナールデッキのモルペコ追加時と同じ手法との一貫性を優先した。
  4種目以降のサブアタッカー追加や、攻撃ごとに異なる特殊効果が増えてきた
  場合に再検討する。
- モルペコ専用RETREAT判断ロジックのような、オーガポンex専用の撤退判断は
  今回のスコープ外（既存のRETREATロジックのまま）。
- 超高速デッキ（Mega Lucario ex先行完成型）との相性検証は今回未実施。

## 次のステップ

- `output/`用デッキCSVの生成、およびKaggleへの再アップロードは本改修の
  スコープ外。実施可否はユーザー判断待ち。
- Kaggle再提出後のLBスコア変化確認はユーザーが手動で実施する。
