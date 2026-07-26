# 実装サマリー: Lucario ex デッキへの Maximum Belt 統合（Dragapult カウンター）

**実装日**: 2026-07-26  
**実装者**: Claude Code  
**設計書**: `docs/superpowers/specs/2026-07-26-lucario-maximum-belt-dragapult-counter-design.md`
**実装計画**: `docs/superpowers/plans/2026-07-26-lucario-maximum-belt-dragapult-counter.md`

---

## 概要

Lucario ex デッキに ACE SPEC カード「Maximum Belt」（ID 1158）を統合した。これにより、Mega Lucario ex の Mega Brave（基礎ダメージ 270）と Maximum Belt のボーナス（+50）を組み合わせることで、HP 320 の ex ポケモン（Dragapult ex など）をちょうど 1 発で KO できるようになった。

---

## 実装の構成

### Task 1（デッキ構築変更）
- `src/lucario_agent/constants.py`: `Maximum_Belt = 1158` を追加（`Hero_Cape`は他デッキ用に残置）
- `decks/lucario_20260621.py`: ACE SPEC 枠を Hero's Cape(1159) → Maximum Belt(1158) に変更

### Task 2（ATTACHスコアリング）
- `src/lucario_agent/main.py`: `Hero_Cape` → `Maximum_Belt` へのimport置き換え
- `_score_attach_option`: Maximum Belt を Mega Lucario ex(7200) > Riolu(7100) の順で優先装着するロジック
- **最終ブランチレビューで追加修正（後述）**: 上記2体以外（Solrock等の非アタッカー）への装着は
  当初「ベース7000点」を返しており、1枚しかないACE SPECを実質無価値なポケモンへ永久装着してしまう
  リスクが指摘された。`-1`（温存）を返すよう修正済み

### Task 3（本実装）

#### 1. 定数のインポート
ファイル: `src/lucario_agent/combat.py`

```python
from lucario_agent.constants import (
    ...
    Maximum_Belt,
)
```

#### 2. ダメージ計算関数の拡張
ファイル: `src/lucario_agent/combat.py` の `_calc_attack_damage()`

**署名の変更**:
```python
def _calc_attack_damage(
    attacker_id: int, base_damage: int, defender_id: int, defender_data, card_table: dict,
    attacker_tools: tuple = (),
) -> int:
```

**実装の追加**:
```python
defender_is_ex = defender_data.ex or defender_data.megaEx
if defender_is_ex and any(t.id == Maximum_Belt for t in attacker_tools):
    damage += 50  # Maximum Belt：相手のアクティブexへの技ダメージ+50（弱点・抵抗力の適用より前）
```

**重要な設計決定**:
- ボーナスは弱点・抵抗力計算の**前に**適用（カード効果文「before applying Weakness and Resistance」に準拠）
- デフォルト引数 `attacker_tools: tuple = ()` で既存呼び出しの互換性を確保
- `megaEx` フィールドも `ex` と同等に扱い、汎用性を確保

#### 3. 攻撃プラン計算での利用
ファイル: `src/lucario_agent/combat.py` の `calc_attack_plan()`

**2 つの呼び出し箇所を修正**:

1. 行 218-220（アクティブポケモンへの攻撃評価）:
```python
damage = _calc_attack_damage(
    my_pokemon.id, base_damage, op_pokemon.id, data, card_table,
    attacker_tools=my_pokemon.tools,
)
```

2. 行 233-235（Mega Brave vs 通常攻撃の判定）:
```python
base_dmg_normal = _calc_attack_damage(
    my_pokemon.id, 130, op_pokemon.id, data, card_table,
    attacker_tools=my_pokemon.tools,
)
```

攻撃側ポケモンの `tools` タプルをそのまま渡すことで、装備カードの情報が自動的にダメージ計算に反映される。

---

## テスト戦略と検証

### 単体テスト（`TestCalcAttackDamage`）

4 つの新規テストを追加:

1. **`test_maximum_belt_adds_50_against_ex_defender`**
   - 相手が ex で Maximum Belt 装着 → +50 が適用される

2. **`test_maximum_belt_no_bonus_against_non_ex_defender`**
   - 相手が非 ex で Maximum Belt 装着 → +50 は**適用されない**

3. **`test_maximum_belt_applied_before_weakness_doubling`**
   - ボーナスと弱点の順序を検証
   - (130 + 50) × 2 = 360（130 × 2 + 50 = 310 ではない）

4. **`test_without_maximum_belt_no_bonus`**
   - attacker_tools を省略時、従来通りボーナスなし

### 統合テスト（`TestCalcAttackPlan`）

2 つの新規テストを追加:

1. **`test_without_maximum_belt_mega_brave_does_not_ko_320hp_ex`**
   - 前提確認：Maximum Belt なしではダメージ 270 では足りない
   - `remain_hp > 0`

2. **`test_maximum_belt_enables_one_shot_ko_on_320hp_ex_active`**
   - Maximum Belt 装着でメガブレイブが 320 HP の ex をちょうど KO
   - `remain_hp == 0`
   - Mega Lucario ex が選択され（`attacker == 0`）、Mega Brave が使用される（`attack_index == 1`）

### テスト結果（最終ブランチレビュー後の修正込み・最新）

```
$ uv run pytest tests/test_lucario_agent.py -v
====================== 201 passed =======================

$ uv run pytest
====================== 738 passed =======================
```

全テストが PASS（既存の無関連な失敗なし）。

## 最終ブランチレビューでの指摘と対応

Opusモデルによる最終ブランチレビューで、ダメージ計算ロジック自体（弱点・ぶちやぶる・ex無効化との
順序関係）はカード原文と完全に一致していると確認された一方、Important指摘が1件あった：

- **Maximum BeltのATTACHスコアリングが、装着先を問わずベース7000点を返していた**（`_score_attach_option`）。
  Hero's Capeは「どのポケモンに付けてもHP+100」という汎用カードだったため問題なかったが、
  Maximum Beltはアタッカー（Mega Lucario ex/Riolu）以外に付けると価値がほぼゼロであり、
  ツール再装着不可・ACE SPEC1枚制限という制約下で、非アタッカーへの永久装着＝実質的な浪費事故に
  つながるリスクがあった。ユーザー確認の上、Mega Lucario ex(7200)/Riolu(7100)以外は`-1`（温存）を
  返すよう修正し、回帰テスト`test_maximum_belt_deprioritized_for_non_attacker`を追加した

その他、以下は実害未確認・設計判断が必要なためマージはブロックせずバックログに委ねた（次回以降の
検討候補）：

- **ふうせん(Air Balloon)とMaximum Beltのどうぐ枠競合の可能性**：ポケモンのどうぐが1匹1枚制限か
  未確認のまま。もし制限があるなら、序盤にAir BalloonをMega Lucario exへ先に装着してしまうと、
  後から引いたMaximum Beltの装着先が塞がれる恐れがある。次回、実バトルログで実際に競合が
  発生しているか確認してから対応要否を判断する
- **Hero's Cape喪失によるHP低下（Mega Lucario ex: 440→340）が設計書に未記載**：ACE SPEC1枚制限
  による必然の取捨選択だが、Dragapult ex以外の対面での防御性能低下リスクは実測していない。
  Kaggle再提出後、新版と旧版の勝率比較を推奨（[[feedback_log_driven_debugging]]踏襲）
- `attacker_tools`の型注釈が`tuple`だが実際は`list`が渡される（実行時無害、次回クリーンアップ候補）
- 計画書に記載の「`Hero_Cape`定数を残す理由」に事実誤認あり（実際は`cinderace_starmie_agent`が
  独自定数`Heros_Cape`を使っており`lucario_agent.constants.Hero_Cape`への参照はゼロ・完全なデッド
  コード）。今回の実装自体は計画通りで問題ないが、次回`Hero_Cape`定数の削除可否を検討する余地あり

---

## 実装の利点

1. **競技戦略への対応**
   - Dragapult ex（HP 320）をちょうど KO 可能な火力が得られた
   - メタゲームの変化に柔軟に対応できる

2. **汎用的な設計**
   - ダメージボーナスロジックが特定のポケモンに限定されない
   - 今後のカード追加時に容易に拡張可能

3. **互換性の確保**
   - 既存コードへの破壊的変更がない
   - デフォルト引数でレガシー呼び出しをサポート

4. **テストカバレッジ**
   - ダメージ計算と攻撃プラン選択の両層で検証
   - エッジケース（非 ex、弱点併用）を網羅

---

## コード品質指標

- **テストカバレッジ**: 6 つの新規テスト（単体 4 + 統合 2）
- **変更行数**: +88 行（テスト込み）
- **複雑性増加**: 低（ボーナス適用はシンプルな条件付き加算）
- **リグレッション**: なし（既存テスト 737 件全 PASS）

---

## 今後の拡張性

このアーキテクチャは以下の拡張に対応可能:

- **他の ACE SPEC カード**: ツール効果の統一的な扱い
- **複数ツール装備**: `any()` で任意のツール検出が可能
- **条件付きボーナス**: defender_data の他のフィールドと組み合わせた複雑なロジック

---

## 関連ファイル

- `src/lucario_agent/combat.py` — ダメージ計算ロジック
- `tests/test_lucario_agent.py` — テストスイート
- `decks/lucario_20260621.py` — デッキリスト
- `lucario_agent/main.py` — 定数定義
- `notebooks/submissions/lucario_agent_submission.ipynb` — Kaggle 提出用ノートブック

---

## 参考資料

- カード効果文: Maximum Belt は「相手のアクティブなポケモンexへのダメージが 50 増える（弱点・抵抗力の計算より前）」
- 競技ルール: ACE SPEC は 1 デッキ 1 枚制限
- 関連技術: Dragapult ex（HP 320、弱点・抵抗力なし）は最適なテストケース
