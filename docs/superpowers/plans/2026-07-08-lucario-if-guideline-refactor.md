# ルカリオexエージェント ロジック不整合修正 + if文ガイドライン準拠リファクタ 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/lucario_agent/main.py` に対し、(1) Ogerpon_ex（Crustle対策の要）がサーチ優先度ロジックから漏れている不整合、(2) `calc_attack_plan`内のダメージ計算重複によるCrustle無効化の非同期、(3) `docs/steering/coding-gideline.md`のif文設計ガイドライン違反（ネスト超過・無名複合条件）を修正する。

**Architecture:** 既存の`_score_card_option`/`_score_play_option`関数内に不足していた分岐を追加し、`calc_attack_plan`のダメージ計算部分を新規ヘルパー関数`_calc_attack_damage`に切り出して重複を解消する。`Premium_Power_Pro`分岐はガード節（早期return）で平坦化する。すべてTDD（Red-Green-Refactor）で実施し、既存253件のテストを一切壊さないことを各タスクで確認する。

**Tech Stack:** Python 3.12 / pytest / uv

## Global Constraints

- 全コミットメッセージ・コードコメント・ドキュメントは日本語で書く（`CLAUDE.md`）
- 既存の253件のテストは常にPASSを維持すること（回帰禁止）
- 各タスク完了時に `uv run pytest -q` を実行し、全件PASSを確認してからコミットする
- 定数・カードIDは既存の名前付き定数（`Ogerpon_ex`, `Crustle`, `Mega_Lucario_ex`等）を使うこと。新しいマジックナンバーを増やさない

---

### Task 1: Ogerpon_exをSelectContext.TO_HANDスコアリングに追加

**背景:** `decks/lucario_20260621.py:9`で「Crustle対策の要」と明記され2枚採用されているOgerpon_exが、山札サーチ（Ultra_Ball等でカードを手札に加える際の候補選択）の優先度ロジックに一切登場しない。Lunatone/Solrock/Riolu/Mega_Lucario_exには個別の優先ボーナスがあるのに、Ogerpon_exだけ基礎点200のまま埋もれてしまう。

**Files:**
- Modify: `src/lucario_agent/main.py:393-406`（`_score_card_option`の`SelectContext.TO_HAND`分岐）
- Test: `tests/test_lucario_agent.py`（末尾に新規クラス`TestToHandContext`を追加）

**Interfaces:**
- Consumes: 既存の`_score_card_option(obs, o, context, my_index, state, my_state, field_counts, hand_counts, discard_counts, attacker1, current_plan, ability_used_flag)`のシグネチャは変更しない
- Produces: `SelectContext.TO_HAND`でcard.id==Ogerpon_exのときのスコア計算ロジック（後続タスクからは参照されない）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`TestBossOrdersEpsilonGreedy`クラスの直後（790行目付近、ファイル末尾）に追記する：

```python
# ==================== ロジック不整合修正: Ogerpon_exのサーチ優先度 ====================
class TestToHandContext:
    """SelectContext.TO_HAND（山札サーチ時の候補選択）でのOgerpon_ex優先度テスト"""

    def _score(self, card_id, field_counts=None, hand_counts=None):
        card = Card(id=card_id, serial=1, playerIndex=0)
        obs = MagicMock()
        obs.select.deck = [card]
        return lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.DECK, index=0, playerIndex=0),
            context=lm.SelectContext.TO_HAND, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=field_counts or defaultdict(int),
            hand_counts=hand_counts or defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )

    def test_prioritized_when_not_yet_secured(self):
        """場に1枚もいなければ、リオル等と同様にサーチ優先度を上げる"""
        assert self._score(lm.Ogerpon_ex) == 200 + 40

    def test_slightly_deprioritized_with_1_in_play(self):
        fc = defaultdict(int, {lm.Ogerpon_ex: 1})
        assert self._score(lm.Ogerpon_ex, field_counts=fc) == 200 - 3

    def test_deprioritized_when_both_copies_in_play(self):
        """デッキの採用枚数(2枚)を場で使い切っていれば探す必要はない"""
        fc = defaultdict(int, {lm.Ogerpon_ex: 2})
        assert self._score(lm.Ogerpon_ex, field_counts=fc) == 200 - 150
```

- [ ] **Step 2: テストを実行し失敗を確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestToHandContext -v`
Expected: 3件とも `assert 200 == 240` のようなFAIL（Ogerpon_exの分岐が存在せず基礎点200のまま）

- [ ] **Step 3: 最小実装**

`src/lucario_agent/main.py`の`_score_card_option`内、`SelectContext.TO_HAND`ケース（393〜406行目）を以下に置き換える：

```python
        case SelectContext.TO_HAND:
            score = 200 - hand_counts[card.id] * 100
            if card.id == Lunatone:
                score += -250 if field_counts[card.id] >= 1 else 60
            elif card.id == Solrock:
                score += -250 if field_counts[card.id] >= 1 else 50
            elif card.id == Riolu:
                total = field_counts[Riolu] + field_counts[Mega_Lucario_ex]
                score += -150 if total >= 2 else (-3 if total >= 1 else 40)
            elif card.id == Mega_Lucario_ex:
                score += 40 if field_counts[Riolu] >= 1 else -15
            elif card.id == Ogerpon_ex:
                # デッキ採用枚数(2枚)に対する充足度で優先度を調整（Riolu方式を踏襲）
                score += -150 if field_counts[Ogerpon_ex] >= 2 else (-3 if field_counts[Ogerpon_ex] >= 1 else 40)
            elif card.id == Basic_Fighting_Energy:
                score += 30 if not ability_used_flag or not state.energyAttached else -1
            return score
```

- [ ] **Step 4: テストを実行しPASSを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestToHandContext -v`
Expected: 3件ともPASS

- [ ] **Step 5: 既存テストに回帰がないことを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: 全件PASS（253+3件）

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix: TO_HANDサーチ優先度にOgerpon_exを追加"
```

---

### Task 2: Ultra_Ballのalready_found判定にOgerpon_exを追加

**背景:** `_score_play_option`のUltra_Ball使用判定（「主力アタッカーをまだ確保していないか」）がRiolu/Mega_Lucario_exしか見ておらず、Ogerpon_exが既に場・手札にあってもUltra_Ballの優先度が下がらない。Task 1と同じ根本原因（Ogerpon_ex追加時の更新漏れ）。

**Files:**
- Modify: `src/lucario_agent/main.py:459-461`（`_score_play_option`のUltra_Ball分岐）
- Test: `tests/test_lucario_agent.py`（Task 1で追加した`TestToHandContext`の直後に新規クラス`TestUltraBallAlreadyFoundIncludesOgerponEx`を追加）

**Interfaces:**
- Consumes: 既存の`_score_play_option(...)`シグネチャは変更しない
- Produces: なし（後続タスクから参照されない）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`TestToHandContext`クラスの直後に追記する：

```python
class TestUltraBallAlreadyFoundIncludesOgerponEx:
    """Ultra_Ballの使用判定(already_found)にOgerpon_exも含まれることの確認"""

    def _score(self, field_counts=None, hand_counts=None):
        obs = MagicMock()
        my_ps = make_player_state(hand=[Card(id=lm.Ultra_Ball, serial=1, playerIndex=0)])
        obs.current.players = [my_ps, make_player_state()]
        return lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=my_ps,
            hand_counts=hand_counts or defaultdict(int),
            field_counts=field_counts or defaultdict(int), stadium_id=0,
        )

    def test_lower_priority_when_ogerpon_ex_already_on_field(self):
        """リオル/メガルカリオexが未確保でも、オーガポンexが場にいれば優先度を下げる"""
        fc = defaultdict(int, {lm.Ogerpon_ex: 1})
        assert self._score(field_counts=fc) == 5500

    def test_lower_priority_when_ogerpon_ex_already_in_hand(self):
        hc = defaultdict(int, {lm.Ogerpon_ex: 1})
        assert self._score(hand_counts=hc) == 5500
```

- [ ] **Step 2: テストを実行し失敗を確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestUltraBallAlreadyFoundIncludesOgerponEx -v`
Expected: 2件とも `assert 6000 == 5500` でFAIL（Ogerpon_exが`already_found`集計に含まれず0のまま扱われるため）

- [ ] **Step 3: 最小実装**

`src/lucario_agent/main.py`の`_score_play_option`内、Ultra_Ball分岐（459〜461行目）を以下に置き換える：

```python
    if card.id == Ultra_Ball:
        already_found = (
            field_counts[Riolu] + field_counts[Mega_Lucario_ex] + field_counts[Ogerpon_ex]
            + hand_counts[Riolu] + hand_counts[Mega_Lucario_ex] + hand_counts[Ogerpon_ex]
        )
        return 6000 if already_found == 0 else 5500
```

- [ ] **Step 4: テストを実行しPASSを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestUltraBallAlreadyFoundIncludesOgerponEx -v`
Expected: 2件ともPASS

- [ ] **Step 5: 既存テストに回帰がないことを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix: Ultra_Ball使用判定のalready_foundにOgerpon_exを追加"
```

---

### Task 3: calc_attack_planのダメージ計算を`_calc_attack_damage`ヘルパーに切り出す

**背景:** `calc_attack_plan`内で「弱点/抵抗力/Crustle無効化」を考慮したダメージ計算が2箇所（メインのダメージ計算307〜315行目、メガブレイブ温存判定用の`base_dmg_normal`再計算325〜330行目）に重複実装されており、後者にはCrustle無効化(`damage=0`)が反映されていない。現状は実害がない（Crustle相手はどちらの攻撃も実ダメージ0のため選択結果は変わらない）が、今後同種の耐性ポケモンが増えた際に誤判定を招く構造的リスクがある。またこの関数はネストが6階層に達しており、`docs/steering/coding-gideline.md`のネスト2階層ルールに違反している。ダメージ計算を1箇所に集約することで重複を解消しつつネストも浅くする。

**Files:**
- Modify: `src/lucario_agent/main.py`（`calc_attack_plan`関数の直前に新規関数`_calc_attack_damage`を追加し、234行目付近の`# ==================== 攻撃プラン計算 ====================`セクションに配置。関数本体307〜336行目を書き換え）
- Test: `tests/test_lucario_agent.py`（`TestCalcAttackPlan`クラスの直前に新規クラス`TestCalcAttackDamage`を追加）

**Interfaces:**
- Produces: `_calc_attack_damage(attacker_id: int, base_damage: int, defender_id: int, defender_data) -> int`
  - `attacker_id`: 攻撃側ポケモンのカードID（`my_pokemon.id`）
  - `base_damage`: 弱点等を考慮する前の基礎ダメージ
  - `defender_id`: 防御側ポケモンのカードID（`op_pokemon.id`）
  - `defender_data`: `card_table[defender_id]`（`weakness`/`resistance`属性を持つ）
  - 戻り値: 弱点2倍・抵抗力-30・Ogerpon_exの弱点無視仕様・Crustleの特性無効化をすべて適用した実ダメージ

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`TestCalcAttackPlan`クラス定義（229行目）の直前に追記する：

```python
class TestCalcAttackDamage:
    """弱点/抵抗力/Crustle無効化を1箇所に集約した_calc_attack_damageのテスト"""

    def test_no_modifier_returns_base_damage(self):
        defender = MockCardData(cardId=999)
        assert lm._calc_attack_damage(lm.Mega_Lucario_ex, 130, 999, defender) == 130

    def test_weakness_doubles_damage(self):
        defender = MockCardData(cardId=999, weakness=EnergyType.FIGHTING)
        assert lm._calc_attack_damage(lm.Mega_Lucario_ex, 130, 999, defender) == 260

    def test_resistance_reduces_damage_by_30(self):
        defender = MockCardData(cardId=999, resistance=EnergyType.FIGHTING)
        assert lm._calc_attack_damage(lm.Mega_Lucario_ex, 130, 999, defender) == 100

    def test_ogerpon_ex_ignores_weakness(self):
        """ぶちやぶるは弱点を計算しない"""
        defender = MockCardData(cardId=999, weakness=EnergyType.FIGHTING)
        assert lm._calc_attack_damage(lm.Ogerpon_ex, 140, 999, defender) == 140

    def test_crustle_nullifies_mega_lucario_ex_damage(self):
        defender = MockCardData(cardId=lm.Crustle)
        assert lm._calc_attack_damage(lm.Mega_Lucario_ex, 270, lm.Crustle, defender) == 0

    def test_crustle_does_not_nullify_ogerpon_ex_damage(self):
        """ぶちやぶるは相手にかかっている効果を計算しないためCrustleの特性を貫通する"""
        defender = MockCardData(cardId=lm.Crustle)
        assert lm._calc_attack_damage(lm.Ogerpon_ex, 140, lm.Crustle, defender) == 140

    def test_crustle_does_not_nullify_non_ex_attacker_damage(self):
        """Crustleの特性はexポケモンの技のみを無効化する（Solrock等の非exは通常通り）"""
        defender = MockCardData(cardId=lm.Crustle)
        assert lm._calc_attack_damage(lm.Solrock, 70, lm.Crustle, defender) == 70
```

- [ ] **Step 2: テストを実行し失敗を確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestCalcAttackDamage -v`
Expected: `AttributeError: module 'lucario_agent.main' has no attribute '_calc_attack_damage'` で7件ともFAIL

- [ ] **Step 3: 最小実装**

`src/lucario_agent/main.py`の`# ==================== 攻撃プラン計算 ====================`（234行目）の直後、`def calc_attack_plan(`の直前に新規関数を追加する：

```python
def _calc_attack_damage(attacker_id: int, base_damage: int, defender_id: int, defender_data) -> int:
    """弱点・抵抗力・Crustleの特性無効化を考慮した実ダメージを1箇所で計算する"""
    damage = base_damage
    attack_ignores_defender_effects = attacker_id == Ogerpon_ex  # ぶちやぶる：相手にかかっている効果を計算しない
    if not attack_ignores_defender_effects:
        if defender_data.weakness == EnergyType.FIGHTING:
            damage *= 2
        elif defender_data.resistance == EnergyType.FIGHTING:
            damage -= 30

    defender_nullifies_ex_damage = defender_id == Crustle and attacker_id == Mega_Lucario_ex
    if defender_nullifies_ex_damage:
        damage = 0  # Crustleの特性「ふしぎな岩の宿」：相手のexポケモンの技ダメージを無効化する

    return damage
```

- [ ] **Step 4: テストを実行しPASSを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestCalcAttackDamage -v`
Expected: 7件ともPASS

- [ ] **Step 5: calc_attack_plan内の重複箇所を_calc_attack_damageに置き換える**

`src/lucario_agent/main.py`の`calc_attack_plan`関数内、以下の2箇所を書き換える。

まず307〜315行目（メインのダメージ計算）:

```python
                damage = base_damage
                data   = card_table[op_pokemon.id]
                if my_pokemon.id != Ogerpon_ex:
                    if data.weakness == EnergyType.FIGHTING:
                        damage *= 2
                    elif data.resistance == EnergyType.FIGHTING:
                        damage -= 30
                if op_pokemon.id == Crustle and my_pokemon.id == Mega_Lucario_ex:
                    damage = 0  # Crustleの特性により、ex ポケモンの技ダメージは通らない
```

を以下に置き換える：

```python
                data   = card_table[op_pokemon.id]
                damage = _calc_attack_damage(my_pokemon.id, base_damage, op_pokemon.id, data)
```

次に325〜336行目（メガブレイブ温存判定）:

```python
                if my_pokemon.id == Mega_Lucario_ex and a == 1:
                    base_dmg_normal = 130
                    if data.weakness == EnergyType.FIGHTING:
                        base_dmg_normal *= 2
                    elif data.resistance == EnergyType.FIGHTING:
                        base_dmg_normal -= 30
                    if op_pokemon.hp <= base_dmg_normal:
                        score -= 1000  # 通常攻撃で足りるならメガブレイブは温存
                    elif op_pokemon.hp > damage:
                        active_rng = rng if rng is not None else _rng
                        if active_rng.random() >= EPSILON:
                            score -= 300  # 探索に外れたら温存寄り
```

を以下に置き換える（`base_dmg_normal`も同じヘルパーで計算することで、Crustle無効化の非同期を解消する）：

```python
                is_mega_brave_choice = my_pokemon.id == Mega_Lucario_ex and a == 1
                if is_mega_brave_choice:
                    base_dmg_normal = _calc_attack_damage(my_pokemon.id, 130, op_pokemon.id, data)
                    if op_pokemon.hp <= base_dmg_normal:
                        score -= 1000  # 通常攻撃で足りるならメガブレイブは温存
                    elif op_pokemon.hp > damage:
                        active_rng = rng if rng is not None else _rng
                        if active_rng.random() >= EPSILON:
                            score -= 300  # 探索に外れたら温存寄り
```

さらに同関数内の無名複合条件2箇所に名前をつける。290行目:

```python
            if a == 1 and i == 0 and energy_count >= 2 and not can_use_mega_brave:
                break
```

を以下に置き換える：

```python
            mega_brave_unavailable_for_current_active = (
                a == 1 and i == 0 and energy_count >= 2 and not can_use_mega_brave
            )
            if mega_brave_unavailable_for_current_active:
                break
```

293行目:

```python
                if hand_counts[Basic_Fighting_Energy] >= 1 and not state.energyAttached:
```

を以下に置き換える：

```python
                can_attach_energy_this_turn = (
                    hand_counts[Basic_Fighting_Energy] >= 1 and not state.energyAttached
                )
                if can_attach_energy_this_turn:
```

- [ ] **Step 6: 既存テストで回帰がないことを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: 全件PASS（`TestCalcAttackPlan`・`TestCrustleAbilityInteraction`を含む既存分が壊れていないこと）

- [ ] **Step 7: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "refactor: calc_attack_planのダメージ計算を_calc_attack_damageに集約しネストを解消"
```

---

### Task 4: Premium_Power_Pro分岐をガード節で平坦化

**背景:** `_score_play_option`のPremium_Power_Pro分岐は3階層ネスト＋無名の三重and条件（`not state.supporterPlayed and hand_counts[Boss_Orders] == 0 and hand_counts[Lillie_Determination] == 0`）を含み、`docs/steering/coding-gideline.md`のガード節ルール（2階層まで）と複合条件命名ルールに違反している。この分岐には既存テストが1件も存在しないため、先に現状の挙動を確定させるテストを書く。

**Files:**
- Modify: `src/lucario_agent/main.py:440-447`（`_score_play_option`のPremium_Power_Pro分岐）
- Test: `tests/test_lucario_agent.py`（`TestNewCardScoring`クラスの直後、774行目付近に新規クラス`TestPremiumPowerProScoring`を追加）

**Interfaces:**
- Consumes: 既存の`_score_play_option(...)`シグネチャは変更しない
- Produces: なし

- [ ] **Step 1: 現状の挙動を確定させるテストを書く**

`tests/test_lucario_agent.py`の`TestNewCardScoring`クラス（688〜772行目）の直後に追記する。真理値表は現行コードから導出したもので、リファクタ前後でスコアが変わらないことをこのテストで保証する：

```python
class TestPremiumPowerProScoring:
    """パワープロテインのスコアリング（既存挙動の固定化テスト）"""

    def _score(self, remain_hp, can_attack, supporter_played,
               boss_in_hand=0, lillie_in_hand=0):
        my_ps = make_player_state(hand=[Card(id=lm.Premium_Power_Pro, serial=1, playerIndex=0)])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        state = _make_state()
        state.supporterPlayed = supporter_played
        plan = lm.AttackPlan(remain_hp=remain_hp)
        hand_counts = defaultdict(int, {
            lm.Boss_Orders: boss_in_hand,
            lm.Lillie_Determination: lillie_in_hand,
        })
        return lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=plan, can_attack=can_attack,
            state=state, my_state=my_ps,
            hand_counts=hand_counts, field_counts=defaultdict(int), stadium_id=0,
        )

    def test_holds_when_supporter_played_and_ko_already_confirmed(self):
        score = self._score(remain_hp=0, can_attack=True, supporter_played=True)
        assert score == -1

    def test_used_freely_when_can_attack(self):
        """攻撃可能な場面では確定KO済みでない限り優先的に使う"""
        score = self._score(remain_hp=50, can_attack=True, supporter_played=False)
        assert score == 5000

    def test_used_as_backup_supporter_when_no_other_option(self):
        """攻撃不可・サポーター未使用・他の有力サポーターも手札にない場合は温存せず使う"""
        score = self._score(remain_hp=50, can_attack=False, supporter_played=False)
        assert score == 3050

    def test_held_when_attack_impossible_but_supporter_already_played(self):
        score = self._score(remain_hp=50, can_attack=False, supporter_played=True)
        assert score == -1

    def test_held_when_better_supporter_available_in_hand(self):
        """ボスの指令が手札にあるならパワープロテインは温存"""
        score = self._score(
            remain_hp=50, can_attack=False, supporter_played=False, boss_in_hand=1,
        )
        assert score == -1
```

- [ ] **Step 2: テストを実行しリファクタ前の実装で全件PASSすることを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestPremiumPowerProScoring -v`
Expected: 5件ともPASS（これは既存コードの現状挙動を記録する特性化テストであり、リファクタ前時点でGREENになるのが正しい）

- [ ] **Step 3: ガード節にリファクタ**

`src/lucario_agent/main.py`の`_score_play_option`内、Premium_Power_Pro分岐（440〜447行目）を以下に置き換える：

```python
    if card.id == Premium_Power_Pro:
        confirmed_ko_already_secured = state.supporterPlayed and current_plan.remain_hp <= 0
        if confirmed_ko_already_secured:
            return -1
        if can_attack:
            return 5000
        other_supporter_in_hand = hand_counts[Boss_Orders] >= 1 or hand_counts[Lillie_Determination] >= 1
        if not state.supporterPlayed and not other_supporter_in_hand:
            return 3050
        return -1
```

- [ ] **Step 4: テストを再実行しリファクタ後も同じ結果になることを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestPremiumPowerProScoring -v`
Expected: 5件ともPASS（スコアが変化していないこと＝挙動保存の確認）

- [ ] **Step 5: 既存テスト全体で回帰がないことを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "refactor: Premium_Power_Pro分岐をガード節で平坦化しif文ガイドラインに準拠"
```

---

### Task 5: 全体テスト実行・実装サマリー・レビューサマリーの作成

**Files:**
- Create: `docs/implementations/20260708-lucario-if-guideline-refactor.md`
- Create: `docs/reviews/20260708-lucario-if-guideline-refactor.md`

**Interfaces:**
- Consumes: Task 1〜4で追加・変更した全コード・テスト

- [ ] **Step 1: リポジトリ全体のテストを実行**

Run: `uv run pytest -q`
Expected: 全件PASS（253＋新規テスト分。0 failed）

- [ ] **Step 2: superpowers:requesting-code-reviewスキルでコードレビューを依頼する**

Task 1〜4の差分（`git diff`）に対してレビューを実施し、指摘があれば反映する。

- [ ] **Step 3: 実装サマリーを作成**

`docs/implementations/20260708-lucario-if-guideline-refactor.md`に、背景・変更内容（コミットハッシュ付き）・テスト結果・未対応事項を記載する（既存の`docs/implementations/20260707-crustle-counter-ogerpon-priority.md`と同じ形式に揃える）。

- [ ] **Step 4: レビューサマリーを作成**

`docs/reviews/20260708-lucario-if-guideline-refactor.md`に、Step 2のレビュー結果（指摘事項・対応状況）を記載する（既存の`docs/reviews/20260707-crustle-counter-ogerpon-priority.md`と同じ形式に揃える）。

- [ ] **Step 5: コミット**

```bash
git add docs/implementations/20260708-lucario-if-guideline-refactor.md docs/reviews/20260708-lucario-if-guideline-refactor.md
git commit -m "docs: if文ガイドライン準拠リファクタの実装・レビューサマリーを追加"
```

---

## Self-Review

- **仕様網羅性:** ユーザー承認済みの3方針（Finding 1のTO_HAND/Ultra_Ball修正、Finding 2のcalc_attack_plan分割、Premium_Power_Proのガード節化）はTask 1〜4でそれぞれ対応済み。「docsのsteeringに移動して参照できるようにする」は前タスクで完了済みのため本計画には含めない。「レビューサマリを忘れずに」はTask 5でカバー。
- **プレースホルダー確認:** 全ステップに具体的なコード・コマンド・期待値を記載済み。「後で実装」等の曖昧な記述なし。
- **型・シグネチャ整合性:** `_calc_attack_damage(attacker_id: int, base_damage: int, defender_id: int, defender_data) -> int`はTask 3のStep 1（テスト）・Step 3（実装）・Step 5（calc_attack_plan内での呼び出し）で一貫して同じシグネチャを使用。
