# tests/test_jamoraiko_agent.py
from collections import defaultdict
from dataclasses import dataclass as _dc
from unittest.mock import MagicMock

import pytest

from cg.api import AreaType, CardType, OptionType

import jamoraiko_agent.main as jm

from tests.conftest import make_pokemon, make_player_state, make_main_obs


class TestAgentDeckSelection:
    def test_agent_returns_deck_when_select_is_none(self):
        obs_dict = {"select": None, "logs": [], "current": None, "search_begin_input": None}
        result = jm.agent(obs_dict)
        assert len(result) == 60
        assert result[0] == 63  # タケルライコex が先頭


class TestCollectFieldState:
    def test_iono_lightning_on_board_counts_only_iono_pokemon(self):
        voltorb = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])       # 雷2
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4])  # 雷3
        non_iono = make_pokemon(id=999, energies=[4, 4, 4, 4])            # 対象外のはずが混入しないことを確認
        my_state = make_player_state(active_pokemon=voltorb, bench=[bellibolt, non_iono])
        fs = jm._collect_field_state(my_state)
        assert fs.iono_lightning_on_board == 5

    def test_own_board_basic_energy_total_counts_lightning_and_fighting(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 6])  # 雷1闘1
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[])
        fs = jm._collect_field_state(my_state)
        assert fs.own_board_basic_energy_total == 2

    def test_active_energy_count_reflects_active_pokemon_only(self):
        active = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        bench_mon = make_pokemon(id=jm.Iono_Tadbulb, energies=[4, 4, 4])
        my_state = make_player_state(active_pokemon=active, bench=[bench_mon])
        fs = jm._collect_field_state(my_state)
        assert fs.active_energy_count == 2

    def test_field_counts_and_hand_counts_are_tracked(self):
        active = make_pokemon(id=jm.Iono_Voltorb)
        hand_card = make_pokemon(id=jm.Canari)
        my_state = make_player_state(active_pokemon=active, bench=[], hand=[hand_card])
        fs = jm._collect_field_state(my_state)
        assert fs.field_counts[jm.Iono_Voltorb] == 1
        assert fs.hand_counts[jm.Canari] == 1


@_dc
class MockAttack:
    """テスト用 Attack 代替クラス（cg.api.Attack と同一フィールドのみ定義）"""
    attackId: int
    name: str
    text: str = ""
    damage: int = 0
    energies: list = None


@pytest.fixture(autouse=True)
def mock_attack_table(monkeypatch):
    table = {
        1001: MockAttack(attackId=1001, name="Voltaic Chain"),
        1002: MockAttack(attackId=1002, name="Thunderous Bolt"),
        1003: MockAttack(attackId=1003, name="Mach Bolt"),
        1004: MockAttack(attackId=1004, name="Bellowing Thunder"),
        1005: MockAttack(attackId=1005, name="Burst Roar"),
    }
    monkeypatch.setattr(jm, "attack_table", table)
    return table


@_dc
class MockCardData:
    """テスト用CardData代替クラス（cg.api.CardDataと同一フィールドのみ定義）"""
    cardId:   int
    name:     str      = ""
    cardType: CardType = CardType.POKEMON


@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        jm.Raging_Bolt_ex:          MockCardData(cardId=jm.Raging_Bolt_ex),
        jm.Iono_Voltorb:            MockCardData(cardId=jm.Iono_Voltorb),
        jm.Iono_Tadbulb:            MockCardData(cardId=jm.Iono_Tadbulb),
        jm.Iono_Bellibolt_ex:       MockCardData(cardId=jm.Iono_Bellibolt_ex),
        jm.Iono_Wattrel:            MockCardData(cardId=jm.Iono_Wattrel),
        jm.Iono_Kilowattrel:        MockCardData(cardId=jm.Iono_Kilowattrel),
        jm.Buddy_Buddy_Poffin:      MockCardData(cardId=jm.Buddy_Buddy_Poffin, cardType=CardType.ITEM),
        jm.Night_Stretcher:         MockCardData(cardId=jm.Night_Stretcher, cardType=CardType.ITEM),
        jm.Max_Rod:                 MockCardData(cardId=jm.Max_Rod, cardType=CardType.ITEM),
        jm.Energy_Retrieval:        MockCardData(cardId=jm.Energy_Retrieval, cardType=CardType.ITEM),
        jm.Energy_Search:           MockCardData(cardId=jm.Energy_Search, cardType=CardType.ITEM),
        jm.Ultra_Ball:               MockCardData(cardId=jm.Ultra_Ball, cardType=CardType.ITEM),
        jm.Switch:                   MockCardData(cardId=jm.Switch, cardType=CardType.ITEM),
        jm.Boss_Orders:               MockCardData(cardId=jm.Boss_Orders, cardType=CardType.SUPPORTER),
        jm.Lillie_Determination:       MockCardData(cardId=jm.Lillie_Determination, cardType=CardType.SUPPORTER),
        jm.Canari:                     MockCardData(cardId=jm.Canari, cardType=CardType.SUPPORTER),
        jm.Levincia:                   MockCardData(cardId=jm.Levincia, cardType=CardType.STADIUM),
        jm.Basic_Lightning_Energy:      MockCardData(cardId=jm.Basic_Lightning_Energy, cardType=CardType.BASIC_ENERGY),
        jm.Basic_Fighting_Energy:       MockCardData(cardId=jm.Basic_Fighting_Energy, cardType=CardType.BASIC_ENERGY),
    }
    monkeypatch.setattr(jm, "card_table", table)
    return table


class TestCalcAttackPlan:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
            active_fighting_energy_count=0,
        )
        base.update(overrides)
        return jm.FieldState(**base)

    def test_voltaic_chain_damage_scales_with_iono_lightning_on_board(self):
        voltorb = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        fs = self._fs(active_energy_count=2, iono_lightning_on_board=5)
        my_state = make_player_state(active_pokemon=voltorb, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(voltorb, op_active_hp=999, fs=fs, my_state=my_state)
        assert plan.damage == 20 + 20 * 5

    def test_lethal_attack_is_preferred_over_non_lethal(self):
        voltorb = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        fs = self._fs(active_energy_count=2, iono_lightning_on_board=10)  # 20+200=220ダメ
        my_state = make_player_state(active_pokemon=voltorb, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(voltorb, op_active_hp=200, fs=fs, my_state=my_state)
        assert plan.is_lethal is True

    def test_bellowing_thunder_chosen_when_lethal_and_only_damaging_option(self):
        """タケルライコexの技はきょくらいごう(ダメージ技)とはじけるほうこう(ダメージ0)の2つのみのため、
        同一ポケモンが同時に2つの確定KO可能技を持つことは構造上ありえない。
        きょくらいごうが確定KO可能なら、それがそのまま選ばれることを確認する"""
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 6])
        # fs は my_active から自動導出されないため、雷1闘1の想定を active_fighting_energy_count=1 で明示する
        fs = self._fs(active_energy_count=2, active_fighting_energy_count=1,
                       own_board_basic_energy_total=10)  # きょくらいごうは700ダメ
        my_state = make_player_state(active_pokemon=raging_bolt, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(raging_bolt, op_active_hp=50, fs=fs, my_state=my_state)
        assert plan.is_lethal is True
        assert plan.attacker_id == jm.Raging_Bolt_ex

    def test_thunderous_bolt_penalised_when_not_lethal(self):
        """確定KOでない場合、次ターン技封じのサンダーボルトより他技を優先する"""
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])
        fs = self._fs(active_energy_count=4, iono_lightning_on_board=4)
        my_state = make_player_state(active_pokemon=bellibolt, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(bellibolt, op_active_hp=9999, fs=fs, my_state=my_state)
        # サンダーボルト(230)一択のはずだが、ペナルティが付いていても他に選択肢がないので選ばれる
        assert plan.attacker_id == jm.Iono_Bellibolt_ex

    def test_burst_roar_only_chosen_when_no_other_attack_available(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4])  # 闘エネなし＝きょくらいごう不可
        fs = self._fs(active_energy_count=1, own_board_basic_energy_total=1)
        my_state = make_player_state(active_pokemon=raging_bolt, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(raging_bolt, op_active_hp=200, fs=fs, my_state=my_state)
        assert plan.attack_id == 1005  # Burst Roar

    def test_no_active_pokemon_returns_empty_plan(self):
        fs = self._fs()
        my_state = make_player_state(active_pokemon=None, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(None, op_active_hp=100, fs=fs, my_state=my_state)
        assert plan.attacker_id == -1

    def test_bellowing_thunder_excluded_when_no_fighting_energy_even_if_lethal(self):
        """タケルライコexに雷2枚・闘0枚がついている場合、きょくらいごうのダメージが
        確定KO相当の量でも、闘エネルギーが0本のため候補から除外されるべき
        （本数だけを見て属性を見ないと、雷2枚だけでも「使用可能」と誤判定してしまう）"""
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 4])  # 雷2、闘0
        fs = self._fs(
            active_energy_count=2, active_fighting_energy_count=0,
            own_board_basic_energy_total=10,  # きょくらいごうなら700ダメ（確定KO相当）
        )
        my_state = make_player_state(active_pokemon=raging_bolt, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(raging_bolt, op_active_hp=50, fs=fs, my_state=my_state)
        # きょくらいごう(1004)は選ばれない。闘エネがないので残る技ははじけるほうこう(1005)のみ、
        # ダメージ0のためis_lethalにはならない
        assert plan.attack_id != 1004
        assert plan.is_lethal is False


class TestEnergyScore:
    def test_active_slot_gets_bonus(self):
        p = make_pokemon(id=jm.Iono_Voltorb, energies=[])
        assert jm.energy_score(p, True) > jm.energy_score(p, False)

    def test_voltorb_prioritised_below_2_energy(self):
        no_e  = make_pokemon(id=jm.Iono_Voltorb, energies=[])
        two_e = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        assert jm.energy_score(no_e, False) > jm.energy_score(two_e, False)

    def test_bellibolt_ex_prioritised_below_4_energy(self):
        low  = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4])
        full = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])
        assert jm.energy_score(low, False) > jm.energy_score(full, False)

    def test_kilowattrel_prioritised_below_3_energy(self):
        low  = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4])
        full = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4, 4, 4])
        assert jm.energy_score(low, False) > jm.energy_score(full, False)


class TestScoreAttachOption:
    def test_fighting_energy_prioritises_raging_bolt_ex_without_fighting(self):
        from cg.api import Option

        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4])
        energy_card = make_pokemon(id=jm.Basic_Fighting_Energy)
        my_state = make_player_state(
            active_pokemon=raging_bolt, hand=[energy_card],
        )
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ATTACH, index=0, inPlayArea=AreaType.ACTIVE, inPlayIndex=0)
        score = jm._score_attach_option(obs, o, my_index=0)
        assert score > 1000  # タケルライコexへの初回闘エネは高優先


class TestDeckSafety:
    def test_safe_draws_reserves_one_draw_per_remaining_prize(self):
        my_state = make_player_state(deck_count=20, prize_count=6)
        assert jm._safe_draws(my_state) == 20 - 6 - 1

    def test_lillie_determination_consumption_scales_with_prize(self):
        hand_counts = defaultdict(int, {jm.Lillie_Determination: 1})
        my_state_full_prize = make_player_state(deck_count=40, prize_count=6)
        my_state_low_prize  = make_player_state(deck_count=40, prize_count=2)
        assert jm._deck_consumption(jm.Lillie_Determination, my_state_full_prize, hand_counts) == 8 - 0
        assert jm._deck_consumption(jm.Lillie_Determination, my_state_low_prize, hand_counts) == 6 - 0

    def test_deck_consumption_returns_none_for_unrelated_card(self):
        hand_counts = defaultdict(int, {jm.Canari: 1})
        my_state = make_player_state(deck_count=40, prize_count=6)
        assert jm._deck_consumption(jm.Canari, my_state, hand_counts) is None

    def test_flashing_draw_consumption_fills_hand_to_6(self):
        hand_counts = defaultdict(int, {jm.Canari: 2})  # 手札2枚
        my_state = make_player_state(deck_count=40, prize_count=6)
        assert jm._flashing_draw_consumption(my_state, hand_counts) == 4

    def test_burst_roar_blocked_when_deck_thin(self):
        """山札が薄い時、はじけるほうこう(6枚ドロー固定)は選ばれない"""
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4])
        fs = self._fs(active_energy_count=1, own_board_basic_energy_total=1)
        my_state = make_player_state(active_pokemon=raging_bolt, deck_count=5, prize_count=6)  # safe_draws = -2
        plan = jm.calc_attack_plan(raging_bolt, op_active_hp=200, fs=fs, my_state=my_state)
        assert plan.attacker_id == -1  # 使える技がない

    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
            active_fighting_energy_count=0,
        )
        base.update(overrides)
        return jm.FieldState(**base)


class TestScorePlayOption:
    def _make_obs_with_hand_card(self, card_id, my_state):
        from cg.api import Option
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.PLAY, index=0)
        return obs, o

    def test_buddy_buddy_poffin_scores_positively(self, mock_card_table):
        mock_card_table[jm.Buddy_Buddy_Poffin] = MockCardData(cardId=jm.Buddy_Buddy_Poffin, cardType=CardType.ITEM)
        poffin = make_pokemon(id=jm.Buddy_Buddy_Poffin)
        my_state = make_player_state(hand=[poffin], deck_count=40, prize_count=6)
        obs, o = self._make_obs_with_hand_card(jm.Buddy_Buddy_Poffin, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score > 0

    def test_lillie_determination_blocked_when_deck_thin(self, mock_card_table):
        mock_card_table[jm.Lillie_Determination] = MockCardData(cardId=jm.Lillie_Determination, cardType=CardType.SUPPORTER)
        lillie = make_pokemon(id=jm.Lillie_Determination)
        my_state = make_player_state(hand=[lillie], deck_count=5, prize_count=6)  # safe_draws = -2
        obs, o = self._make_obs_with_hand_card(jm.Lillie_Determination, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score == -1

    def test_boss_orders_scores_high_when_lethal(self, mock_card_table):
        mock_card_table[jm.Boss_Orders] = MockCardData(cardId=jm.Boss_Orders, cardType=CardType.SUPPORTER)
        boss = make_pokemon(id=jm.Boss_Orders)
        my_state = make_player_state(hand=[boss], deck_count=40, prize_count=6)
        obs, o = self._make_obs_with_hand_card(jm.Boss_Orders, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan(attacker_id=jm.Iono_Voltorb, attack_id=1001, damage=300, is_lethal=True)
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score >= 8000


class TestAgentEndToEnd:
    def test_agent_picks_lethal_attack_when_available(self):
        from cg.api import Option

        my_active = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        my_bench  = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4, 4, 4, 4, 4])
        my_state  = make_player_state(active_pokemon=my_active, bench=[my_bench], deck_count=40, prize_count=6)
        op_active = make_pokemon(id=999, hp=50)
        op_state  = make_player_state(active_pokemon=op_active, deck_count=40, prize_count=6)

        options = [
            Option(type=OptionType.RETREAT),
            Option(type=OptionType.ATTACK, attackId=jm._attack_id_by_name("Voltaic Chain") or 1001),
        ]
        obs_dict = make_main_obs(your_index=0, my_state=my_state, op_state=op_state, options=options)
        result = jm.agent(obs_dict)
        chosen = options[result[0]]
        assert chosen.type == OptionType.ATTACK


class TestScoreSetupActive:
    def test_voltorb_outranks_raging_bolt_ex(self):
        assert jm._score_setup_active(jm.Iono_Voltorb) > jm._score_setup_active(jm.Raging_Bolt_ex)

    def test_raging_bolt_ex_outranks_tadbulb(self):
        assert jm._score_setup_active(jm.Raging_Bolt_ex) > jm._score_setup_active(jm.Iono_Tadbulb)

    def test_unknown_card_defaults_to_zero(self):
        assert jm._score_setup_active(999999) == 0


class TestIsAttackReady:
    def test_voltorb_ready_with_2_energy(self):
        assert jm._is_attack_ready(jm.Iono_Voltorb, energy_count=2, fighting_count=0) is True

    def test_voltorb_not_ready_with_1_energy(self):
        assert jm._is_attack_ready(jm.Iono_Voltorb, energy_count=1, fighting_count=0) is False

    def test_raging_bolt_ex_not_ready_without_fighting_energy(self):
        # きょくらいごうは闘エネ必須。はじけるほうこうはis_utilityのため候補から除外される
        assert jm._is_attack_ready(jm.Raging_Bolt_ex, energy_count=2, fighting_count=0) is False

    def test_raging_bolt_ex_ready_with_fighting_energy(self):
        assert jm._is_attack_ready(jm.Raging_Bolt_ex, energy_count=2, fighting_count=1) is True

    def test_unknown_card_is_never_ready(self):
        assert jm._is_attack_ready(999999, energy_count=10, fighting_count=10) is False


class TestScoreSwitchTarget:
    def test_opponent_bench_lethal_gets_large_bonus(self):
        from cg.api import Option

        target = make_pokemon(id=999, hp=50)
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=1)
        plan = jm.AttackPlan(attacker_id=jm.Iono_Voltorb, attack_id=1001, damage=60, is_lethal=False)
        score = jm._score_switch_target(target, o, my_index=0, plan=plan)
        # スコアは -hp + 100000（このケースでは99950）。HPは最大でも数百程度なので
        # 90000以上であれば確実に確定KOボーナス分岐が適用されたことを検証できる
        assert score >= 90000

    def test_opponent_bench_prefers_lower_hp_when_not_lethal(self):
        from cg.api import Option

        low_hp = make_pokemon(id=999, hp=50)
        high_hp = make_pokemon(id=999, hp=200)
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=1)
        plan = jm.AttackPlan(attacker_id=jm.Iono_Voltorb, attack_id=1001, damage=10, is_lethal=False)
        score_low = jm._score_switch_target(low_hp, o, my_index=0, plan=plan)
        score_high = jm._score_switch_target(high_hp, o, my_index=0, plan=plan)
        assert score_low > score_high

    def test_own_pokemon_ready_to_attack_outranks_not_ready(self):
        from cg.api import Option

        ready = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])       # 2エネ=攻撃可能
        not_ready = make_pokemon(id=jm.Iono_Voltorb, energies=[4])      # 1エネ=攻撃不可
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        plan = jm.AttackPlan()
        score_ready = jm._score_switch_target(ready, o, my_index=0, plan=plan)
        score_not_ready = jm._score_switch_target(not_ready, o, my_index=0, plan=plan)
        assert score_ready > score_not_ready
