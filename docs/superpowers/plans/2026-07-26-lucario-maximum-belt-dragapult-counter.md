# ルカリオex Maximum Belt導入（Dragapult ex対策）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mega Lucario exのメガブレイブ(270)にACE SPEC「Maximum Belt」(+50、相手のアクティブ`ex`限定)を組み合わせ、Dragapult ex(HP320・弱点抵抗力ともにn/a)を270+50=320でちょうど1発でワンパンできるようにする。

**Architecture:** (1) デッキ構築側でACE SPEC枠をHero's Cape(1159)からMaximum Belt(1158)へ差し替え、(2) `_score_attach_option`にMaximum Beltの装着優先度（Mega Lucario ex最優先）を追加、(3) `_calc_attack_damage`にMaximum Beltのダメージボーナスを組み込み、`calc_attack_plan`が実際にKO判定できるようにする。3レイヤーとも既存のHero_Cape/ex無効化パターンを踏襲する。

**Tech Stack:** Python 3.12, pytest, 既存の`lucario_agent`パッケージ構造（`constants.py`/`main.py`/`combat.py`）。

## Global Constraints

- ACE SPECはデッキ内1枚制限（既存の`feedback_ace_spec_deck_rule`方針、`tests/test_lucario_deck.py::test_ace_spec_does_not_exceed_1_copy`で機械チェック済み）
- `Hero_Cape`定数自体は`src/lucario_agent/constants.py`から削除しない（`decks/cinderace_starmie_20260630.py`が引き続き使用するため）。削除するのは`lucario_agent`モジュール内での参照のみ
- Maximum Beltのダメージボーナス(+50)は「相手のアクティブ`ex`ポケモン」限定・「弱点・抵抗力の適用より前」に加算する（カード効果文の順序を忠実に再現）
- Premium Power Proとの連携ロジックは追加しない（Maximum Belt単体で270+50=320のちょうどKOが成立するため）
- コードコメントは日本語で書く（プロジェクト規約）

---

### Task 1: デッキ構築変更（ACE SPEC枠のMaximum Beltへの差し替え）

**Files:**
- Modify: `src/lucario_agent/constants.py`
- Modify: `decks/lucario_20260621.py:18`
- Test: `tests/test_lucario_deck.py`

**Interfaces:**
- Produces: `lucario_agent.constants.Maximum_Belt`（int定数、値`1158`）。Task 2/3がこの定数をimportして使う

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_deck.py`の`ACE_SPEC_IDS = {1159}  # Hero's Cape`を以下に置き換える：

```python
ACE_SPEC_IDS = {1158}  # Maximum Belt
```

さらに、ファイル末尾（`test_switch_and_air_balloon_newly_adopted`の後）に以下のテストを追加する：

```python
def test_maximum_belt_replaces_hero_cape():
    """2026-07-26: Dragapult ex(HP320)へのワンパン対策として、ACE SPEC枠を
    Hero's CapeからMaximum Beltへ差し替えた"""
    ids = {card_id for card_id, _ in DECK}
    assert 1159 not in ids, "Hero's Cape は今回の改修で削除されたはず"
    counts = dict(DECK)
    assert counts.get(1158) == 1, "Maximum Belt(ACE SPEC)が1枚採用されているはず"
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_lucario_deck.py -v`
Expected: `test_maximum_belt_replaces_hero_cape`がFAIL（`1159 not in ids`のassertで失敗、まだHero's Capeがデッキに残っているため）。`test_ace_spec_does_not_exceed_1_copy`はPASSのまま（ACE_SPEC_IDS={1158}だがデッキにまだ1158が無いためチェック対象0件でスルーする）

- [ ] **Step 3: `src/lucario_agent/constants.py`にMaximum_Belt定数を追加する**

9行目`Hero_Cape             = 1159`の直後に以下を追加する：

```python
Maximum_Belt          = 1158  # ACE SPEC：相手のアクティブexへの技ダメージ+50（弱点・抵抗力適用前）
```

- [ ] **Step 4: `decks/lucario_20260621.py`のACE SPEC枠を差し替える**

18行目を置き換える：

```python
    (1158, 1),   # Maximum Belt（ACE SPEC。Dragapult ex(HP320)対策、Hero's Capeから差し替え。2026-07-26）
```

（元の`(1159, 1),   # Hero's Cape (ACE SPEC)`の行を削除する）

- [ ] **Step 5: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_lucario_deck.py -v`
Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/constants.py decks/lucario_20260621.py tests/test_lucario_deck.py
git commit -m "feat(lucario): ACE SPEC枠をHero's CapeからMaximum Beltへ差し替え"
```

---

### Task 2: ATTACHスコアリングへのMaximum Belt優先度追加

**Files:**
- Modify: `src/lucario_agent/main.py:14` (import), `src/lucario_agent/main.py:467-478` (`_score_attach_option`)
- Test: `tests/test_lucario_agent.py`

**Interfaces:**
- Consumes: `lucario_agent.constants.Maximum_Belt`（Task 1で追加済み）
- Produces: `lm.Maximum_Belt`（`main.py`経由でテストからアクセス可能になる）。Task 3のテストがこれを使う

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の50行目付近、`mock_card_table`フィクスチャ内の以下の行：

```python
        lm.Hero_Cape:            _card(lm.Hero_Cape,            cardType=CardType.TOOL),
```

を以下に置き換える：

```python
        lm.Maximum_Belt:         _card(lm.Maximum_Belt,         cardType=CardType.TOOL),
```

次に、1537-1568行目の`TestScoreAttachOptionHeroCapeVsAirBalloon`クラス全体を、以下の内容で置き換える：

```python
class TestScoreAttachOptionMaximumBeltVsAirBalloon:
    """2026-07-26: Dragapult ex対策としてACE SPECをHero's CapeからMaximum Beltへ
    差し替えた。Maximum Belt(ACE SPEC・相手のアクティブexへの技ダメージ+50の恒久バフ)は
    Air Balloon(にげるコスト-2)より長期的価値が高いため、同一ポケモンを対象とした場合
    Maximum Beltのスコアが常にAir Balloonを上回ることを確認する回帰テスト"""

    def _score(self, card_id, pokemon):
        obs = MagicMock()
        card = Card(id=card_id, serial=1, playerIndex=0)
        my_state = make_player_state(active_pokemon=pokemon, hand=[card])
        obs.current.players = [my_state, make_player_state()]
        option = Option(
            type=OptionType.ATTACH, area=lm.AreaType.HAND, index=0,
            inPlayArea=lm.AreaType.ACTIVE, inPlayIndex=0,
        )
        return lm._score_attach_option(
            obs, option, my_index=0, current_plan=lm.AttackPlan(), attacker1=False,
        )

    def test_maximum_belt_beats_air_balloon_for_mega_lucario_ex(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex)
        maximum_belt_score = self._score(lm.Maximum_Belt, lucario)
        air_balloon_score  = self._score(lm.Air_Balloon, lucario)
        assert maximum_belt_score > air_balloon_score

    def test_maximum_belt_beats_air_balloon_for_riolu(self):
        riolu = make_pokemon(id=lm.Riolu)
        maximum_belt_score = self._score(lm.Maximum_Belt, riolu)
        air_balloon_score  = self._score(lm.Air_Balloon, riolu)
        assert maximum_belt_score > air_balloon_score
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py -v -k "MaximumBelt or maximum_belt"`
Expected: FAIL（`AttributeError: module 'lucario_agent.main' has no attribute 'Maximum_Belt'`。main.pyがまだMaximum_Beltをimportしていないため）

- [ ] **Step 3: `src/lucario_agent/main.py`のimportを更新する**

14行目：

```python
    Poke_Pad, Hero_Cape, Boss_Orders, Lillie_Determination, Gravity_Mountain,
```

を以下に置き換える：

```python
    Poke_Pad, Maximum_Belt, Boss_Orders, Lillie_Determination, Gravity_Mountain,
```

- [ ] **Step 4: `_score_attach_option`のHero_Cape分岐をMaximum_Belt分岐に置き換える**

470-477行目：

```python
    if card.id == Hero_Cape:
        pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
        score = 7000
        if pokemon.id == Riolu:
            score += 100
        elif pokemon.id == Mega_Lucario_ex:
            score += 200
        return score
```

を以下に置き換える：

```python
    if card.id == Maximum_Belt:
        pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
        score = 7000
        if pokemon.id == Riolu:
            score += 100  # 進化後もツールは維持されるため次点で許容
        elif pokemon.id == Mega_Lucario_ex:
            score += 200  # メガブレイブでのワンパンを狙う主目的のため最優先
        return score
```

- [ ] **Step 5: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: 全件PASS（`Hero_Cape`関連の他テストは無くなっているため影響なし）

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat(lucario): Maximum BeltのATTACHスコアリング分岐を追加"
```

---

### Task 3: ダメージ計算へのMaximum Belt反映と統合テスト

**Files:**
- Modify: `src/lucario_agent/combat.py:7-11` (import), `src/lucario_agent/combat.py:98-117` (`_calc_attack_damage`), `src/lucario_agent/combat.py:211`, `src/lucario_agent/combat.py:223`
- Test: `tests/test_lucario_agent.py`

**Interfaces:**
- Consumes: `lm.Maximum_Belt`（Task 2で`main.py`にimport済み。`combat.py`内では`lucario_agent.constants.Maximum_Belt`を直接import）
- Produces: `_calc_attack_damage(attacker_id, base_damage, defender_id, defender_data, card_table, attacker_tools=())`（`attacker_tools`が新規キーワード引数。既存呼び出しは省略可、デフォルト`()`で従来通りの挙動）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`TestCalcAttackDamage`クラス（353行目、`test_generalizes_to_any_ex_attacker_not_just_mega_lucario`の後）に以下を追加する：

```python
    def test_maximum_belt_adds_50_against_ex_defender(self):
        """Maximum Belt装着で相手exへの技ダメージが+50される"""
        defender = MockCardData(cardId=999, ex=True)
        belt = Card(id=lm.Maximum_Belt, serial=1, playerIndex=0)
        assert lm._calc_attack_damage(
            lm.Mega_Lucario_ex, 270, 999, defender, card_table=lm.card_table,
            attacker_tools=[belt],
        ) == 320

    def test_maximum_belt_no_bonus_against_non_ex_defender(self):
        """相手が非exならMaximum Beltの+50は適用されない"""
        defender = MockCardData(cardId=999, ex=False)
        belt = Card(id=lm.Maximum_Belt, serial=1, playerIndex=0)
        assert lm._calc_attack_damage(
            lm.Mega_Lucario_ex, 270, 999, defender, card_table=lm.card_table,
            attacker_tools=[belt],
        ) == 270

    def test_maximum_belt_applied_before_weakness_doubling(self):
        """カード効果文「before applying Weakness and Resistance」の順序確認：
        (130+50)*2=360になる（130*2+50=310ではない）"""
        defender = MockCardData(cardId=999, ex=True, weakness=EnergyType.FIGHTING)
        belt = Card(id=lm.Maximum_Belt, serial=1, playerIndex=0)
        assert lm._calc_attack_damage(
            lm.Mega_Lucario_ex, 130, 999, defender, card_table=lm.card_table,
            attacker_tools=[belt],
        ) == 360

    def test_without_maximum_belt_no_bonus(self):
        """attacker_tools省略時（既存呼び出し）は従来通りボーナス無し"""
        defender = MockCardData(cardId=999, ex=True)
        assert lm._calc_attack_damage(
            lm.Mega_Lucario_ex, 270, 999, defender, card_table=lm.card_table,
        ) == 270
```

続けて、`TestCalcAttackPlan`クラス内（`from cg.api import Option, OptionType`の少し後、既存の`calc_attack_plan`系テストが並ぶセクションの末尾）に以下を追加する：

```python
    def test_without_maximum_belt_mega_brave_does_not_ko_320hp_ex(self):
        """前提確認：Maximum Belt未装着だとメガブレイブ(270)のみではHP320・exを倒しきれない"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=337, hp=320), prize_count=6)  # Archaludon ex(ex=True)相当
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.remain_hp > 0

    def test_maximum_belt_enables_one_shot_ko_on_320hp_ex_active(self):
        """Maximum Belt装着でメガブレイブ(270)+50=320により、
        HP320・exの相手をちょうど1発でKOできることを確認する統合テスト"""
        belt = Card(id=lm.Maximum_Belt, serial=1, playerIndex=0)
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6], tools=[belt])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=337, hp=320), prize_count=6)  # Archaludon ex(ex=True)相当
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.attacker     == 0
        assert result.attack_index == 1
        assert result.remain_hp    == 0
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py -v -k "maximum_belt"`
Expected: `TestCalcAttackDamage`側のMaximum Belt関連4件がFAIL（`_calc_attack_damage() got an unexpected keyword argument 'attacker_tools'`）。`TestCalcAttackPlan`側の2件は`_calc_attack_damage`が`calc_attack_plan`内部から呼ばれるだけで`attacker_tools`は未使用のため、`test_without_maximum_belt_mega_brave_does_not_ko_320hp_ex`はこの時点でも通ってしまう可能性があるが、`test_maximum_belt_enables_one_shot_ko_on_320hp_ex_active`はFAIL（remain_hpが0にならず270ダメージ分の50が残るため）

- [ ] **Step 3: `src/lucario_agent/combat.py`のimportを更新する**

7-11行目：

```python
from lucario_agent.constants import (
    Lunatone, Solrock, Riolu, Mega_Lucario_ex, Ogerpon_ex,
    Basic_Fighting_Energy, Rock_Fighting_Energy, Nighttime_Mine,
    EX_DAMAGE_NULLIFIER_IDS,
)
```

を以下に置き換える：

```python
from lucario_agent.constants import (
    Lunatone, Solrock, Riolu, Mega_Lucario_ex, Ogerpon_ex,
    Basic_Fighting_Energy, Rock_Fighting_Energy, Nighttime_Mine,
    EX_DAMAGE_NULLIFIER_IDS, Maximum_Belt,
)
```

- [ ] **Step 4: `_calc_attack_damage`にMaximum Beltのボーナスを追加する**

98-117行目：

```python
def _calc_attack_damage(attacker_id: int, base_damage: int, defender_id: int, defender_data, card_table: dict) -> int:
    """弱点・抵抗力・ex技無効化ポケモンの特性を考慮した実ダメージを1箇所で計算する"""
    damage = base_damage
    attack_ignores_defender_effects = attacker_id == Ogerpon_ex  # ぶちやぶる：相手にかかっている効果を計算しない
    if not attack_ignores_defender_effects:
        if defender_data.weakness == EnergyType.FIGHTING:
            damage *= 2
        elif defender_data.resistance == EnergyType.FIGHTING:
            damage -= 30

    attacker_is_ex = card_table[attacker_id].ex or card_table[attacker_id].megaEx
    defender_nullifies_ex_damage = (
        not attack_ignores_defender_effects  # ぶちやぶるは無効化を貫通するため対象外
        and defender_id in EX_DAMAGE_NULLIFIER_IDS
        and attacker_is_ex
    )
    if defender_nullifies_ex_damage:
        damage = 0  # Crustle/Sylveonの特性：相手のポケモンexの技ダメージを無効化する

    return damage
```

を以下に置き換える：

```python
def _calc_attack_damage(
    attacker_id: int, base_damage: int, defender_id: int, defender_data, card_table: dict,
    attacker_tools: tuple = (),
) -> int:
    """弱点・抵抗力・ex技無効化ポケモンの特性を考慮した実ダメージを1箇所で計算する"""
    damage = base_damage
    defender_is_ex = defender_data.ex or defender_data.megaEx
    if defender_is_ex and any(t.id == Maximum_Belt for t in attacker_tools):
        damage += 50  # Maximum Belt：相手のアクティブexへの技ダメージ+50（弱点・抵抗力の適用より前）

    attack_ignores_defender_effects = attacker_id == Ogerpon_ex  # ぶちやぶる：相手にかかっている効果を計算しない
    if not attack_ignores_defender_effects:
        if defender_data.weakness == EnergyType.FIGHTING:
            damage *= 2
        elif defender_data.resistance == EnergyType.FIGHTING:
            damage -= 30

    attacker_is_ex = card_table[attacker_id].ex or card_table[attacker_id].megaEx
    defender_nullifies_ex_damage = (
        not attack_ignores_defender_effects  # ぶちやぶるは無効化を貫通するため対象外
        and defender_id in EX_DAMAGE_NULLIFIER_IDS
        and attacker_is_ex
    )
    if defender_nullifies_ex_damage:
        damage = 0  # Crustle/Sylveonの特性：相手のポケモンexの技ダメージを無効化する

    return damage
```

- [ ] **Step 5: `calc_attack_plan`内の2箇所の呼び出しに`attacker_tools`を渡す**

211行目：

```python
                damage = _calc_attack_damage(my_pokemon.id, base_damage, op_pokemon.id, data, card_table)
```

を以下に置き換える：

```python
                damage = _calc_attack_damage(
                    my_pokemon.id, base_damage, op_pokemon.id, data, card_table,
                    attacker_tools=my_pokemon.tools,
                )
```

223行目：

```python
                    base_dmg_normal = _calc_attack_damage(my_pokemon.id, 130, op_pokemon.id, data, card_table)
```

を以下に置き換える：

```python
                    base_dmg_normal = _calc_attack_damage(
                        my_pokemon.id, 130, op_pokemon.id, data, card_table,
                        attacker_tools=my_pokemon.tools,
                    )
```

- [ ] **Step 6: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: 全件PASS

- [ ] **Step 7: リポジトリ全体のテストを実行する**

Run: `uv run pytest`
Expected: 全件PASS（既存の無関係な失敗・エラーがあれば、着手前の`main`ブランチと同数であることを確認する）

- [ ] **Step 8: 提出用notebookを再生成する**

Run: `uv run python scripts/build_lucario_submission_notebook.py`
Expected: `notebooks/submissions/lucario_agent_submission.ipynb`が正常に再生成される（Kaggleアップロードはユーザー実施）

- [ ] **Step 9: コミット**

```bash
git add src/lucario_agent/combat.py tests/test_lucario_agent.py
git commit -m "feat(lucario): _calc_attack_damageにMaximum Beltのダメージボーナスを反映"
```

---

## 完了条件

- `decks/lucario_20260621.py`のACE SPEC枠がMaximum Belt(1158)になっている
- `_score_attach_option`がMaximum BeltをMega Lucario ex最優先で装着する
- `_calc_attack_damage`がMaximum Belt装着時、相手のアクティブexへの技ダメージに弱点・抵抗力適用前の+50を加算する
- `calc_attack_plan`が「メガブレイブ(270)+Maximum Belt(50)=320でHP320・exの相手をちょうどKOできる」と正しく判定する
- リポジトリ全体のテストがPASSする（既存の無関係な失敗・エラー件数に変化がないことを確認）
- 実装完了後、`docs/implementations/20260726-lucario-maximum-belt-dragapult-counter.md`に実装サマリーを保存する（CLAUDE.mdフェーズ4の規約）
