# ルカリオexデッキ Judge増量・ポケモンいれかえ/ふうせん採用 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ルカリオexデッキにJudgeを2→3枚増量し、ポケモンいれかえ（Switch）とふうせん（Air Balloon）を新規採用して、既知の2つのギャップ（Judgeの資源枯渇・自発的な交代手段の欠如）に対応する。

**Architecture:** `decks/lucario_20260621.py`のカード構成を60枚のまま入れ替え、`src/lucario_agent/main.py`に新規`SwitchPolicy`（既存の`TrainerCardPolicy`パターンに準拠、`_score_retreat_option`のロジックを流用）と`_score_attach_option`への新規分岐（既存のHero_Capeパターンに準拠）を追加する。合わせて`_analyze_main_options`のcan_switch判定にSwitch保持時の条件を追加する。

**Tech Stack:** Python, pytest, uv（パッケージ・実行管理）

## Global Constraints

- テストは`uv run pytest`で実行する（このプロジェクトの標準コマンド）
- コードコメントは日本語で書く（変数名・関数名は英語）。WHYが非自明な箇所のみコメントを書き、自明な内容は書かない
- 既存の`TrainerCardPolicy`（ABC＋登録辞書）パターンに従う。生のif/elif連鎖を新設しない
- 設計書: `docs/superpowers/specs/2026-07-25-lucario-judge-switch-airballoon-design.md`（本プランはこれに準拠）
- スコープ外（今回は触らない）: ゲノセクトのエースカンセラー、マクノシタ/ハリテヤマ系統、ロケット団の監視塔、マキシマムベルト、`OPPONENT_HAND_THRESHOLD`の閾値見直し。Hilda/Wally's Compassion/Ciphermaniac's Codebreakingの削除に伴い`TRAINER_CARD_POLICIES`内の対応する登録（`WallyCompassionPolicy`含む）が到達不能なデッドコードになるが、今回は削除しない（デッキ変更のみに範囲を絞るため。将来的なクリーンアップ候補として別途扱う）

---

### Task 1: デッキ構成の入れ替え・カードID定数の追加

**Files:**
- Modify: `decks/lucario_20260621.py`
- Modify: `src/lucario_agent/constants.py`
- Modify: `tests/test_lucario_deck.py`

**Interfaces:**
- Produces: `lucario_agent.constants.Switch`（int, 値1123）、`lucario_agent.constants.Air_Balloon`（int, 値1174）。Task 2〜4がこれらを`import`して使う

- [ ] **Step 1: 失敗するテストを書く（デッキ内容の変更を先に定義）**

`tests/test_lucario_deck.py`を以下のように書き換える（既存の`test_dusk_ball_and_carmine_and_switch_removed`は「Switch削除」の期待が今回の変更と矛盾するため、Switchの行だけ取り除いて`test_dusk_ball_and_carmine_removed`に改名する。`test_new_cards_present_with_expected_counts`はHilda/Wally's Compassion/Ciphermaniac's Codebreakingの期待値を削除しJudgeを3に変更する。新規に採用カードの存在確認テストを追加する）：

```python
from decks.lucario_20260621 import DECK

ENERGY_IDS = {6}  # Basic {F} Energy
ACE_SPEC_IDS = {1159}  # Hero's Cape


def test_deck_has_60_cards():
    assert sum(count for _, count in DECK) == 60


def test_no_non_energy_card_exceeds_4_copies():
    for card_id, count in DECK:
        if card_id not in ENERGY_IDS:
            assert count <= 4, f"Card {card_id} が {count} 枚（上限4枚）"


def test_key_pokemon_present():
    ids = {card_id for card_id, _ in DECK}
    assert 677 in ids, "Riolu が不在"
    assert 678 in ids, "Mega Lucario ex が不在"
    assert 676 in ids, "Solrock が不在"
    assert 675 in ids, "Lunatone が不在"


def test_makuhita_hariyama_line_removed():
    ids = {card_id for card_id, _ in DECK}
    assert 673 not in ids, "Makuhita は今回の改修で削除されたはず"
    assert 674 not in ids, "Hariyama は今回の改修で削除されたはず"


def test_dusk_ball_and_carmine_removed():
    ids = {card_id for card_id, _ in DECK}
    assert 1102 not in ids, "Dusk Ball は今回の改修で削除されたはず"
    assert 1192 not in ids, "Carmine は今回の改修で削除されたはず"


def test_energy_count():
    basic = sum(c for i, c in DECK if i == 6)
    rock = sum(c for i, c in DECK if i == 20)
    assert basic == 7
    assert rock == 4
    assert basic + rock == 11


def test_ace_spec_does_not_exceed_1_copy():
    for card_id, count in DECK:
        if card_id in ACE_SPEC_IDS:
            assert count <= 1, f"ACE SPECカード {card_id} が {count} 枚（上限1枚）"


def test_no_duplicate_card_id_entries():
    ids = [card_id for card_id, _ in DECK]
    assert len(ids) == len(set(ids)), "同じcard_idが複数タプルに分かれている"


def test_new_cards_present_with_expected_counts():
    counts = dict(DECK)
    assert counts[1121] == 4  # Ultra Ball
    assert counts[1122] == 4  # Pokégear 3.0
    assert counts[1097] == 2  # Night Stretcher
    assert counts[1213] == 3  # Judge（2026-07-25: 2→3、Alakazam対面のJudge資源枯渇対策）


def test_ogerpon_ex_present_with_2_copies():
    counts = dict(DECK)
    assert counts[117] == 2  # Cornerstone Mask Ogerpon ex（1→2に増量）


def test_solrock_reduced_to_2():
    counts = dict(DECK)
    assert counts[676] == 2  # Solrock 3→2（オーガポンex増量のため1枚減）


def test_hilda_wally_ciphermaniac_removed():
    """2026-07-25: 資源制約に効果の薄い単発サポート3種を削り、
    Judge増量・Switch・Air Balloonの採用枠に充てた"""
    ids = {card_id for card_id, _ in DECK}
    assert 1225 not in ids, "Hilda（トウコ）は今回の改修で削除されたはず"
    assert 1229 not in ids, "Wally's Compassion（ミツルの思いやり）は今回の改修で削除されたはず"
    assert 1188 not in ids, "Ciphermaniac's Codebreaking（暗号マニアの解読）は今回の改修で削除されたはず"


def test_switch_and_air_balloon_newly_adopted():
    """2026-07-25: 自発的な交代手段が無い構造的ギャップへの対応として新規採用"""
    counts = dict(DECK)
    assert counts[1123] == 1  # ポケモンいれかえ（Switch）
    assert counts[1174] == 2  # ふうせん（Air Balloon）
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_lucario_deck.py -v`
Expected: `test_dusk_ball_and_carmine_removed`は存在しない関数名エラー（旧名のまま）、`test_new_cards_present_with_expected_counts`はJudge=2でFAIL、`test_hilda_wally_ciphermaniac_removed`と`test_switch_and_air_balloon_newly_adopted`はKeyErrorまたはFAIL

- [ ] **Step 3: デッキ定義・定数を変更する**

`decks/lucario_20260621.py`を以下に書き換える：

```python
# ルカリオデッキ定義（20260725 Judge増量・Switch/Air Balloon採用）
# 2026-07-03軽量版リビルドをベースに、資源制約(Judge枯渇)と交代手段の
# 欠如という2つの既知ギャップに対応。単発サポート3種(Hilda/Wally's
# Compassion/Ciphermaniac's Codebreaking)を削り採用枠に充てた

DECK = [
    (677, 4),    # Riolu
    (678, 3),    # Mega Lucario ex
    (676, 2),    # Solrock（3→2。オーガポンex増量のため1枚減）
    (675, 2),    # Lunatone
    (117, 2),    # Cornerstone Mask Ogerpon ex（1→2に増量。Crustle対策の要）
    (1142, 4),   # Fighting Gong
    (1121, 4),   # Ultra Ball
    (1152, 2),   # Poké Pad
    (1141, 4),   # Premium Power Pro
    (1097, 2),   # Night Stretcher
    (1122, 4),   # Pokégear 3.0
    (1159, 1),   # Hero's Cape (ACE SPEC)
    (1227, 4),   # Lillie's Determination
    (1182, 4),   # Boss's Orders
    (1213, 3),   # Judge（2→3。Alakazam対面のJudge資源枯渇対策）
    (1123, 1),   # Switch（ポケモンいれかえ。自発的な交代手段の欠如への対応、新規採用）
    (1174, 2),   # Air Balloon（ふうせん。にげるコスト-2、新規採用）
    (1252, 1),   # Gravity Mountain
    (6, 7),      # Basic {F} Energy
    (20, 4),     # Rock {F} Energy（Alakazam「ハンドパワー」対策。闘エネルギー1個分＋相手の技の効果を無効化）
]
```

`src/lucario_agent/constants.py`に以下を追加する（`Ciphermaniac_Codebreaking = 1188`の行の直後）：

```python
Switch                      = 1123
Air_Balloon                 = 1174
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_lucario_deck.py -v`
Expected: PASS（全件）

- [ ] **Step 5: コミット**

```bash
git add decks/lucario_20260621.py src/lucario_agent/constants.py tests/test_lucario_deck.py
git commit -m "feat(lucario): Judge3枚化・ポケモンいれかえ/ふうせん新規採用でデッキを更新

トウコ・ミツルの思いやり・暗号マニアの解読を削り、Judgeの資源枯渇問題と
自発的な交代手段の欠如という既知のギャップに対応する採用枠を確保した。"
```

---

### Task 2: `_analyze_main_options`にSwitch保持時のcan_switch判定を追加

**Files:**
- Modify: `src/lucario_agent/main.py:143-162`（`_analyze_main_options`関数）
- Test: `tests/test_lucario_agent.py`

**Interfaces:**
- Consumes: `lucario_agent.constants.Switch`（Task 1で追加済み。`main.py`冒頭のconstants importに`Switch`を追加する必要がある）
- Produces: `_analyze_main_options(obs, select, my_index)`の`can_switch`が、RETREATが選択肢に無くてもSwitchがPLAY選択肢にあればTrueになる（Task 3が前提とする挙動）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`TestScoreAttackOptionChoice`クラスの直後（798行目付近、`TestAgent`クラスの前）に以下を追加する：

```python
class TestAnalyzeMainOptionsSwitch:
    """_analyze_main_options: ポケモンいれかえ(Switch)がPLAY選択肢にあれば、
    RETREATが選択肢に無くてもcan_switchがTrueになることを確認する
    （2026-07-03に削除された旧ロジックの復活。エネルギー不足でRETREATが
    出せない局面でも、Switchがあればベンチ交代を検討できるようにする）"""

    def _analyze(self, hand_cards):
        obs = MagicMock()
        my_state = make_player_state(hand=hand_cards)
        obs.current.players = [my_state, make_player_state()]
        select = MagicMock()
        select.option = [Option(type=OptionType.PLAY, index=0)]
        return lm._analyze_main_options(obs, select, my_index=0)

    def test_can_switch_true_when_switch_in_play_options(self):
        switch_card = Card(id=lm.Switch, serial=1, playerIndex=0)
        can_switch, _, _, _ = self._analyze([switch_card])
        assert can_switch is True

    def test_can_switch_false_when_only_unrelated_card_playable(self):
        other_card = Card(id=lm.Boss_Orders, serial=1, playerIndex=0)
        can_switch, _, _, _ = self._analyze([other_card])
        assert can_switch is False

    def test_can_switch_still_true_when_retreat_option_present(self):
        """既存挙動の回帰確認：RETREATが選択肢にあれば従来通りTrue"""
        obs = MagicMock()
        obs.current.players = [make_player_state(), make_player_state()]
        select = MagicMock()
        select.option = [Option(type=OptionType.RETREAT)]
        can_switch, _, _, _ = lm._analyze_main_options(obs, select, my_index=0)
        assert can_switch is True
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestAnalyzeMainOptionsSwitch -v`
Expected: `test_can_switch_true_when_switch_in_play_options`がFAIL（`can_switch`が`False`のまま）。他2件はPASS（既存ロジックで通る）

- [ ] **Step 3: `_analyze_main_options`を修正する**

`src/lucario_agent/main.py`12-18行目の`from lucario_agent.constants import (...)`を以下のように書き換え、`Switch`をimportに追加する：

```python
from lucario_agent.constants import (
    Lunatone, Solrock, Riolu, Mega_Lucario_ex, Premium_Power_Pro, Fighting_Gong,
    Poke_Pad, Hero_Cape, Boss_Orders, Lillie_Determination, Gravity_Mountain,
    Nighttime_Mine, Basic_Fighting_Energy, Rock_Fighting_Energy, Ultra_Ball,
    Pokegear, Night_Stretcher, Judge, Hilda, Wally_Compassion,
    Ciphermaniac_Codebreaking, Ogerpon_ex, Crustle, Sylveon, EX_DAMAGE_NULLIFIER_IDS,
    Switch,
)
```

`_analyze_main_options`（143-162行目）の`for o in select.option:`ループを以下に書き換える：

```python
    for o in select.option:
        if o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            if card.id == Boss_Orders:
                can_op_switch = True
            elif card.id == Switch:
                can_switch = True
        elif o.type == OptionType.RETREAT:
            can_switch = True
        elif o.type == OptionType.ATTACK:
            can_attack = True
            if o.attackId == 983:  # Mega Brave
                can_use_mega_brave = True
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestAnalyzeMainOptionsSwitch -v`
Expected: PASS（全件）

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: 既存テストに回帰なし（全件PASS）

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat(lucario): SwitchがPLAY選択肢にあればcan_switchをTrueにする

RETREATがエネルギー不足で選択肢に出せない局面でも、ポケモンいれかえが
あればベンチアタッカーへの交代をcalc_attack_planが検討できるようにする。"
```

---

### Task 3: `SwitchPolicy`新設・`TRAINER_CARD_POLICIES`登録

**Files:**
- Modify: `src/lucario_agent/main.py`（`TrainerCardPolicy`のサブクラス群、`TRAINER_CARD_POLICIES`辞書）
- Test: `tests/test_lucario_agent.py`

**Interfaces:**
- Consumes: `_score_retreat_option(current_plan, my_active, card_table)`（`combat.py`、既存）、`PlayScoringContext`（既存、`current_plan`・`my_state`フィールドを使う）
- Produces: `lucario_agent.main.SwitchPolicy`クラス、`TRAINER_CARD_POLICIES[Switch]`エントリ

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`冒頭の`mock_card_table`フィクスチャ（27-60行目付近）に、`lm.Ciphermaniac_Codebreaking`の行の直後、以下を追加する：

```python
        lm.Switch:                _card(lm.Switch,                cardType=CardType.ITEM),
        lm.Air_Balloon:           _card(lm.Air_Balloon,           cardType=CardType.TOOL),
```

`TestAnalyzeMainOptionsSwitch`クラスの直後に以下を追加する：

```python
class TestSwitchPolicy:
    """SwitchPolicy: ポケモンいれかえのPLAYスコアリング。
    _score_retreat_optionと同条件で発火するが、にげるコスト(エネルギー破棄)を
    伴わないぶんRETREATより優先されるよう+100して返す"""

    def _ctx(self, current_plan, my_state):
        return lm.PlayScoringContext(
            obs=MagicMock(), o=Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=current_plan, can_attack=False,
            state=_make_state(), my_state=my_state,
            hand_counts=defaultdict(int), field_counts=defaultdict(int), stadium_id=0,
        )

    def test_negative_when_plan_keeps_current_attacker_and_active_is_effective(self):
        plan = lm.AttackPlan(attacker=0, damage=130)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Mega_Lucario_ex, hp=50))
        assert lm.SwitchPolicy().play_score(self._ctx(plan, my_state)) == -1

    def test_high_score_when_plan_switches_attacker(self):
        plan = lm.AttackPlan(attacker=1)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Mega_Lucario_ex, hp=50))
        assert lm.SwitchPolicy().play_score(self._ctx(plan, my_state)) == 2100

    def test_positive_when_ineffective_attack_and_high_value_active(self):
        plan = lm.AttackPlan(attacker=0, damage=0)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Mega_Lucario_ex, hp=50))
        assert lm.SwitchPolicy().play_score(self._ctx(plan, my_state)) == 2100

    def test_negative_when_ineffective_attack_but_regular_pokemon(self):
        plan = lm.AttackPlan(attacker=0, damage=0)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=50))
        assert lm.SwitchPolicy().play_score(self._ctx(plan, my_state)) == -1

    def test_scores_higher_than_retreat_when_same_condition_fires(self):
        """RETREATと同条件が成立するとき、エネルギーを失わないSwitchが+100分だけ優先される"""
        plan = lm.AttackPlan(attacker=1)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Mega_Lucario_ex, hp=50))
        retreat_score = lm._score_retreat_option(plan, my_state.active[0], lm.card_table)
        assert lm.SwitchPolicy().play_score(self._ctx(plan, my_state)) == retreat_score + 100


class TestScoreOptionPlaySwitchWiring:
    """main.py側でPLAYのSwitchケースがTRAINER_CARD_POLICIES経由で
    SwitchPolicyへ正しく配線されていることの統合テスト"""

    def test_score_option_play_switch_uses_switch_policy(self):
        switch_card = Card(id=lm.Switch, serial=1, playerIndex=0)
        my_state = make_player_state(
            active_pokemon=make_pokemon(id=lm.Mega_Lucario_ex, hp=50), hand=[switch_card],
        )
        op_state = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100))
        plan = lm.AttackPlan(attacker=1)
        obs = MagicMock()
        obs.current.players = [my_state, op_state]
        option = Option(type=OptionType.PLAY, index=0)
        score = lm._score_option(
            obs=obs, o=option, context=lm.SelectContext.MAIN, my_index=0,
            state=_make_state(), my_state=my_state, op_state=op_state,
            field_counts=defaultdict(int), hand_counts=defaultdict(int), discard_counts=defaultdict(int),
            attacker1=False, current_plan=plan, can_attack=True,
            stadium_id=0, ability_used_flag=False,
        )
        assert score == 2100
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestSwitchPolicy tests/test_lucario_agent.py::TestScoreOptionPlaySwitchWiring -v`
Expected: FAIL（`lm.SwitchPolicy`が存在しない、`AttributeError`）

- [ ] **Step 3: `SwitchPolicy`を実装する**

`src/lucario_agent/main.py`の`JudgePolicy`クラス定義の直後（`class WallyCompassionPolicy`の直前）に以下を追加する：

```python
class SwitchPolicy(TrainerCardPolicy):
    """ポケモンいれかえ：_score_retreat_optionと同条件で発火するが、
    にげるコスト(エネルギー破棄)を伴わないぶんRETREATより+100して優先する。
    条件不成立時(-1)はそのまま-1を返す（負のスコアに加算してはいけない）"""
    def play_score(self, ctx: PlayScoringContext) -> int:
        my_active = ctx.my_state.active[0] if ctx.my_state.active else None
        base = _score_retreat_option(ctx.current_plan, my_active, card_table)
        return base + 100 if base > 0 else -1
```

`TRAINER_CARD_POLICIES`辞書（400-412行目）の`Judge: JudgePolicy(),`の行の直後に以下を追加する：

```python
    Switch: SwitchPolicy(),
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestSwitchPolicy tests/test_lucario_agent.py::TestScoreOptionPlaySwitchWiring -v`
Expected: PASS（全件）

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: 既存テストに回帰なし（全件PASS）

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat(lucario): ポケモンいれかえのSwitchPolicyを新設

_score_retreat_optionと同条件で発火し、エネルギーを失わない分RETREATより
+100優先する。TRAINER_CARD_POLICIESへ登録し配線した。"
```

---

### Task 4: ふうせん（Air Balloon）のATTACHスコアリング分岐を追加

**Files:**
- Modify: `src/lucario_agent/main.py:445-471`（`_score_attach_option`関数）
- Test: `tests/test_lucario_agent.py`

**Interfaces:**
- Consumes: `lucario_agent.constants.Air_Balloon`（Task 1で追加済み）
- Produces: `_score_attach_option`がAir Balloon装着時、メガルカリオex > リオル > その他の優先度でスコアを返す

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`TestScoreAttachOptionRockFightingEnergy`クラスの直前に以下を追加する：

```python
class TestScoreAttachOptionAirBalloon:
    """_score_attach_optionのふうせん(Air Balloon)分岐：メガルカリオex最優先、
    次いでリオル（両者ともにげるコスト2で、-2の効果を最大限活かせるため）"""

    def _score(self, pokemon):
        obs = MagicMock()
        air_balloon_card = Card(id=lm.Air_Balloon, serial=1, playerIndex=0)
        my_state = make_player_state(active_pokemon=pokemon, hand=[air_balloon_card])
        obs.current.players = [my_state, make_player_state()]
        option = Option(
            type=OptionType.ATTACH, area=lm.AreaType.HAND, index=0,
            inPlayArea=lm.AreaType.ACTIVE, inPlayIndex=0,
        )
        return lm._score_attach_option(
            obs, option, my_index=0, current_plan=lm.AttackPlan(), attacker1=False,
        )

    def test_mega_lucario_ex_highest_priority(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex)
        assert self._score(lucario) == 7200

    def test_riolu_second_priority(self):
        riolu = make_pokemon(id=lm.Riolu)
        assert self._score(riolu) == 7100

    def test_other_pokemon_base_score(self):
        solrock = make_pokemon(id=lm.Solrock)
        assert self._score(solrock) == 7000

    def test_mega_lucario_ex_scores_higher_than_riolu(self):
        assert self._score(make_pokemon(id=lm.Mega_Lucario_ex)) > self._score(make_pokemon(id=lm.Riolu))
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreAttachOptionAirBalloon -v`
Expected: FAIL（Air Balloon分岐が無いため、全ケースで`energy_score`経由の別の値が返り期待値と不一致）

- [ ] **Step 3: `_score_attach_option`にAir Balloon分岐を追加する**

`src/lucario_agent/main.py`の`from lucario_agent.constants import (...)`（Task 2で`Switch,`を追加済み）に`Air_Balloon,`も追加し、末尾を以下のようにする：

```python
    Ciphermaniac_Codebreaking, Ogerpon_ex, Crustle, Sylveon, EX_DAMAGE_NULLIFIER_IDS,
    Switch, Air_Balloon,
)
```

`_score_attach_option`関数（445行目〜）で、Hero_Capeブロックの直後（455行目の`return score`の後、456行目の`pokemon = get_card(...)`の前）に以下を追加する：

```python
    if card.id == Air_Balloon:
        pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
        score = 7000
        if pokemon.id == Mega_Lucario_ex:
            score += 200
        elif pokemon.id == Riolu:
            score += 100
        return score
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreAttachOptionAirBalloon -v`
Expected: PASS（全件）

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: 既存テストに回帰なし（全件PASS）

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat(lucario): ふうせん(Air Balloon)のATTACHスコアリング分岐を追加

にげるコストが最大(2)のメガルカリオex・リオルを優先して装着先に選ぶ。"
```

---

### Task 5: 全体テスト実行・提出用notebook再生成

**Files:**
- Modify: なし（ビルド成果物`notebooks/submissions/lucario_agent_submission.ipynb`は`.gitignore`対象のため未コミット）

**Interfaces:**
- Consumes: Task 1〜4で完成した`src/lucario_agent/{constants,combat,main}.py`と`decks/lucario_20260621.py`
- Produces: 最新ロジックを含む提出用notebook（Kaggleアップロードはユーザーが別途実施）

- [ ] **Step 1: リポジトリ全体のテストを実行する**

Run: `uv run pytest -q`
Expected: 既存の無関係な失敗・エラー件数から増加なし（PASS件数がTask 1〜4で追加したテスト分だけ増えていること）

- [ ] **Step 2: 提出用notebookを再生成する**

Run: `uv run python scripts/build_lucario_submission_notebook.py`
Expected: `notebooks/submissions/lucario_agent_submission.ipynb`が正常に生成される（構文エラー時は非ゼロ終了・notebook書き出しなしになるはずなので、正常終了を確認する）

- [ ] **Step 3: 生成されたnotebookに新規ロジックが含まれることを確認する**

Run: `grep -c "SwitchPolicy\|Air_Balloon" notebooks/submissions/lucario_agent_submission.ipynb`
Expected: 0より大きい件数（新規クラス・定数がnotebookに埋め込まれている）

- [ ] **Step 4: 最終確認（コミットなし）**

`git status`で、`decks/`・`src/lucario_agent/`・`tests/`配下の変更が全てTask 1〜4で既にコミット済みであることを確認する。`notebooks/submissions/*.ipynb`は`.gitignore`対象のためコミット不要（Kaggleアップロードはユーザーが別途実施）。
