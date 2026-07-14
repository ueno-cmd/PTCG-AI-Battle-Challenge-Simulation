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

    def test_hand_has_basic_lightning_energy_true_when_present(self):
        energy_card = make_pokemon(id=jm.Basic_Lightning_Energy)
        my_state = make_player_state(hand=[energy_card])
        fs = jm._collect_field_state(my_state)
        assert fs.hand_has_basic_lightning_energy is True

    def test_hand_has_basic_lightning_energy_false_when_absent(self):
        canari = make_pokemon(id=jm.Canari)
        my_state = make_player_state(hand=[canari])
        fs = jm._collect_field_state(my_state)
        assert fs.hand_has_basic_lightning_energy is False


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
        jm.Energy_Switch:            MockCardData(cardId=jm.Energy_Switch, cardType=CardType.ITEM),
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

    def test_raging_bolt_ex_prioritised_below_1_energy(self):
        no_e  = make_pokemon(id=jm.Raging_Bolt_ex, energies=[])
        one_e = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4])
        assert jm.energy_score(no_e, False) > jm.energy_score(one_e, False)

    def test_raging_bolt_ex_no_bonus_once_at_1_energy(self):
        one_e = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4])
        two_e = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 4])
        assert jm.energy_score(one_e, False) == jm.energy_score(two_e, False)


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

    def test_energy_switch_scores_high_when_raging_bolt_ex_needs_lightning_and_source_exists(self, mock_card_table):
        mock_card_table[jm.Energy_Switch] = MockCardData(cardId=jm.Energy_Switch, cardType=CardType.ITEM)
        energy_switch = make_pokemon(id=jm.Energy_Switch)
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])  # 雷0闘1
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 雷4=供給可能
        my_state = make_player_state(
            active_pokemon=raging_bolt, bench=[bellibolt],
            hand=[energy_switch], deck_count=40, prize_count=6,
        )
        obs, o = self._make_obs_with_hand_card(jm.Energy_Switch, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score >= 7000

    def test_energy_switch_scores_low_when_no_source_available(self, mock_card_table):
        mock_card_table[jm.Energy_Switch] = MockCardData(cardId=jm.Energy_Switch, cardType=CardType.ITEM)
        energy_switch = make_pokemon(id=jm.Energy_Switch)
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])  # 雷0闘1
        my_state = make_player_state(
            active_pokemon=raging_bolt, bench=[],
            hand=[energy_switch], deck_count=40, prize_count=6,
        )
        obs, o = self._make_obs_with_hand_card(jm.Energy_Switch, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score < 7000


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

    def test_agent_selects_card_option_for_setup_active_pokemon(self):
        """SETUP_ACTIVE_POKEMONコンテキストでOptionType.CARDがagent()まで正しく配線されていることを検証する。

        0.015事故は_score_optionのOptionType.CARD分岐そのものが未実装で
        「配線が黙って無反応」になっていたことが原因だったため、
        _score_option直呼びだけでなくagent(obs_dict)の入口から出口まで通す
        スモークテストを1本用意し、この事故クラスの再発を防ぐ。

        識別力：低スコアカード(index 0)と高スコアカード(index 1)を配置し、
        [1]を期待することで、配線崩壊時に両オプションが同点(0点)になり
        安定ソート[0]が返されるため確実にREDになる。
        """
        from cg.api import Card, Option, SelectContext, SelectType

        hand = [
            Card(id=jm.Raging_Bolt_ex, serial=1, playerIndex=0),  # タケルライコex：200点（低スコア）
            Card(id=jm.Iono_Voltorb, serial=2, playerIndex=0),    # ビリリダマ：300点（高スコア、期待される選択肢）
        ]
        my_state = make_player_state(hand=hand, hand_count=len(hand), deck_count=50, prize_count=6)
        op_state = make_player_state(deck_count=50, prize_count=6)

        options = [
            Option(type=OptionType.CARD, area=AreaType.HAND, index=0, playerIndex=0),
            Option(type=OptionType.CARD, area=AreaType.HAND, index=1, playerIndex=0),
        ]
        obs_dict = make_main_obs(
            your_index=0, my_state=my_state, op_state=op_state, options=options,
            context=SelectContext.SETUP_ACTIVE_POKEMON, select_type=SelectType.CARD,
        )
        result = jm.agent(obs_dict)
        assert result == [1]


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

    def test_non_pokemon_card_returns_zero_without_crashing(self):
        """SWITCH/TO_ACTIVEコンテキストで想定外の非PokemonカードCard型が渡された場合、
        card.hp/card.energiesへの無条件アクセスでAttributeErrorが起きないことを検証する。
        grimmsnarl_agentのisinstance(card, Pokemon)ガードと同じ堅牢化。
        """
        from cg.api import Card, Option

        non_pokemon = Card(id=999, serial=1, playerIndex=0)
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        plan = jm.AttackPlan()
        score = jm._score_switch_target(non_pokemon, o, my_index=0, plan=plan)
        assert score == 0


class TestScoreSearchCandidate:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
            active_fighting_energy_count=0,
        )
        base.update(overrides)
        return jm.FieldState(**base)

    def test_pokemon_below_cap_scores_positive(self):
        fs = self._fs()
        assert jm._score_search_candidate(jm.Iono_Voltorb, fs) > 0

    def test_pokemon_at_cap_is_deprioritised(self):
        fs = self._fs(field_counts=defaultdict(int, {jm.Iono_Voltorb: 2}))
        assert jm._score_search_candidate(jm.Iono_Voltorb, fs) < 0

    def test_evolution_deprioritised_when_pre_evo_absent(self):
        fs_no_pre_evo = self._fs()
        fs_with_pre_evo = self._fs(field_counts=defaultdict(int, {jm.Iono_Tadbulb: 1}))
        score_absent = jm._score_search_candidate(jm.Iono_Bellibolt_ex, fs_no_pre_evo)
        score_present = jm._score_search_candidate(jm.Iono_Bellibolt_ex, fs_with_pre_evo)
        assert score_present > score_absent

    def test_lightning_energy_has_base_priority(self):
        fs = self._fs()
        assert jm._score_search_candidate(jm.Basic_Lightning_Energy, fs) == 150

    def test_fighting_energy_prioritised_when_raging_bolt_ex_needs_it(self):
        fs_needs = self._fs(
            field_counts=defaultdict(int, {jm.Raging_Bolt_ex: 1}),
            active_fighting_energy_count=0,
        )
        fs_not_needed = self._fs()
        score_needs = jm._score_search_candidate(jm.Basic_Fighting_Energy, fs_needs)
        score_not_needed = jm._score_search_candidate(jm.Basic_Fighting_Energy, fs_not_needed)
        assert score_needs > score_not_needed

    def test_unknown_card_defaults_to_zero(self):
        fs = self._fs()
        assert jm._score_search_candidate(999999, fs) == 0


class TestScoreDiscardCandidate:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
            active_fighting_energy_count=0,
        )
        base.update(overrides)
        return jm.FieldState(**base)

    def test_surplus_pokemon_is_safe_to_discard(self):
        fs = self._fs(hand_counts=defaultdict(int, {jm.Iono_Voltorb: 3}))  # 上限2を超過
        assert jm._score_discard_candidate(jm.Iono_Voltorb, fs) > 0

    def test_needed_pokemon_is_protected(self):
        fs = self._fs()
        assert jm._score_discard_candidate(jm.Iono_Voltorb, fs) < 0

    def test_key_supporter_is_protected(self):
        fs = self._fs()
        assert jm._score_discard_candidate(jm.Boss_Orders, fs) < 0

    def test_fighting_energy_is_protected(self):
        fs = self._fs()
        assert jm._score_discard_candidate(jm.Basic_Fighting_Energy, fs) < 0

    def test_surplus_lightning_energy_is_safe_to_discard(self):
        fs = self._fs(hand_counts=defaultdict(int, {jm.Basic_Lightning_Energy: 3}))
        assert jm._score_discard_candidate(jm.Basic_Lightning_Energy, fs) > 0

    def test_generic_card_gets_small_positive_score(self):
        fs = self._fs()
        assert jm._score_discard_candidate(999999, fs) == 10


class TestScoreCardOptionDispatch:
    def test_dispatches_setup_active_pokemon(self):
        from cg.api import Option, SelectContext

        voltorb = make_pokemon(id=jm.Iono_Voltorb)
        my_state = make_player_state(hand=[voltorb], deck_count=40, prize_count=6)
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.CARD, area=AreaType.HAND, index=0, playerIndex=0)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_card_option(obs, o, SelectContext.SETUP_ACTIVE_POKEMON, my_index=0, fs=fs, plan=plan)
        assert score == jm._score_setup_active(jm.Iono_Voltorb)

    def test_dispatches_switch_context(self):
        from cg.api import Option, SelectContext

        target = make_pokemon(id=999, hp=50)
        op_state = make_player_state(active_pokemon=None, bench=[target])
        obs = MagicMock()
        obs.current.players = [make_player_state(), op_state]
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=1)
        fs = jm._collect_field_state(make_player_state())
        plan = jm.AttackPlan(attacker_id=jm.Iono_Voltorb, attack_id=1001, damage=60, is_lethal=False)
        score = jm._score_card_option(obs, o, SelectContext.SWITCH, my_index=0, fs=fs, plan=plan)
        assert score == jm._score_switch_target(target, o, my_index=0, plan=plan)

    def test_dispatches_to_hand_and_to_bench_identically(self):
        from cg.api import Option, SelectContext

        voltorb = make_pokemon(id=jm.Iono_Voltorb)
        my_state = make_player_state(deck_count=40, prize_count=6)
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.CARD, area=AreaType.DECK, index=0, playerIndex=0)
        obs.select.deck = [voltorb]
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score_hand = jm._score_card_option(obs, o, SelectContext.TO_HAND, my_index=0, fs=fs, plan=plan)
        score_bench = jm._score_card_option(obs, o, SelectContext.TO_BENCH, my_index=0, fs=fs, plan=plan)
        assert score_hand == score_bench == jm._score_search_candidate(jm.Iono_Voltorb, fs)

    def test_returns_zero_when_card_is_none(self):
        from cg.api import Option, SelectContext

        my_state = make_player_state()
        my_state.active = [None]
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.CARD, area=AreaType.ACTIVE, index=0, playerIndex=0)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_card_option(obs, o, SelectContext.SWITCH, my_index=0, fs=fs, plan=plan)
        assert score == 0

    def test_dispatches_discard(self):
        from cg.api import Option, SelectContext

        voltorb = make_pokemon(id=jm.Iono_Voltorb)
        my_state = make_player_state(hand=[voltorb], deck_count=40, prize_count=6)
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.CARD, area=AreaType.HAND, index=0, playerIndex=0)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_card_option(obs, o, SelectContext.DISCARD, my_index=0, fs=fs, plan=plan)
        assert score == jm._score_discard_candidate(jm.Iono_Voltorb, fs)

    def test_score_option_routes_card_type_through_dispatcher(self, mock_card_table):
        from cg.api import Option, SelectContext

        voltorb = make_pokemon(id=jm.Iono_Voltorb)
        my_state = make_player_state(hand=[voltorb], deck_count=40, prize_count=6)
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.CARD, area=AreaType.HAND, index=0, playerIndex=0)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_option(
            obs, o, SelectContext.SETUP_ACTIVE_POKEMON, my_index=0,
            state=None, my_state=my_state, fs=fs, plan=plan,
        )
        assert score == jm._score_setup_active(jm.Iono_Voltorb)

    def test_dispatches_detach_from_prefers_surplus_source_over_raging_bolt_ex(self):
        from cg.api import Option, SelectContext

        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 雷4=余剰あり
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 6])
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[bellibolt])
        obs = MagicMock()
        obs.current.players = [my_state]
        o_bellibolt = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        o_raging = Option(type=OptionType.CARD, area=AreaType.ACTIVE, index=0, playerIndex=0)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score_bellibolt = jm._score_card_option(obs, o_bellibolt, SelectContext.DETACH_FROM, my_index=0, fs=fs, plan=plan)
        score_raging = jm._score_card_option(obs, o_raging, SelectContext.DETACH_FROM, my_index=0, fs=fs, plan=plan)
        assert score_bellibolt > score_raging

    def test_dispatches_attach_from_prefers_raging_bolt_ex_needing_lightning(self):
        from cg.api import Option, SelectContext

        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])  # 雷0闘1
        other = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4, 4, 4])
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[other])
        obs = MagicMock()
        obs.current.players = [my_state]
        o_raging = Option(type=OptionType.CARD, area=AreaType.ACTIVE, index=0, playerIndex=0)
        o_other = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score_raging = jm._score_card_option(obs, o_raging, SelectContext.ATTACH_FROM, my_index=0, fs=fs, plan=plan)
        score_other = jm._score_card_option(obs, o_other, SelectContext.ATTACH_FROM, my_index=0, fs=fs, plan=plan)
        assert score_raging > score_other


class TestFindEnergySwitchSource:
    def test_returns_bellibolt_ex_when_surplus_lightning(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 雷4=閾値到達
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        assert jm._find_energy_switch_source(my_state) is bellibolt

    def test_returns_none_when_below_threshold(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4])  # 雷3=閾値未満
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        assert jm._find_energy_switch_source(my_state) is None

    def test_ignores_raging_bolt_ex_itself(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 4, 4, 4, 4])
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[])
        assert jm._find_energy_switch_source(my_state) is None


class TestRagingBoltExNeedsLightning:
    def test_true_when_no_lightning_attached(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])  # 闘1のみ
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[])
        assert jm._raging_bolt_ex_needs_lightning(my_state) is True

    def test_false_when_lightning_already_attached(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 6])
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[])
        assert jm._raging_bolt_ex_needs_lightning(my_state) is False

    def test_false_when_raging_bolt_ex_not_on_board(self):
        my_state = make_player_state(active_pokemon=None, bench=[])
        assert jm._raging_bolt_ex_needs_lightning(my_state) is False


class TestScoreOptionKilowattrelAbility:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
            active_fighting_energy_count=0, hand_has_basic_lightning_energy=False,
        )
        base.update(overrides)
        return jm.FieldState(**base)

    def test_kilowattrel_ability_suppressed_when_hand_has_lightning_energy(self, mock_card_table):
        from cg.api import Option, SelectContext

        kilowattrel = make_pokemon(id=jm.Iono_Kilowattrel)
        my_state = make_player_state(active_pokemon=kilowattrel, deck_count=40, prize_count=6)
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ABILITY, area=AreaType.ACTIVE, index=0)
        fs = self._fs(hand_has_basic_lightning_energy=True)
        plan = jm.AttackPlan()
        score = jm._score_option(
            obs, o, SelectContext.MAIN, my_index=0,
            state=None, my_state=my_state, fs=fs, plan=plan,
        )
        assert score == -1

    def test_kilowattrel_ability_allowed_when_hand_has_no_lightning_energy_and_deck_safe(self, mock_card_table):
        from cg.api import Option, SelectContext

        kilowattrel = make_pokemon(id=jm.Iono_Kilowattrel)
        my_state = make_player_state(active_pokemon=kilowattrel, deck_count=40, prize_count=6)
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ABILITY, area=AreaType.ACTIVE, index=0)
        fs = self._fs(
            hand_has_basic_lightning_energy=False,
            hand_counts=defaultdict(int, {jm.Canari: 6}),
        )
        plan = jm.AttackPlan()
        score = jm._score_option(
            obs, o, SelectContext.MAIN, my_index=0,
            state=None, my_state=my_state, fs=fs, plan=plan,
        )
        assert score == 8000


class TestScoreOptionEnergyType:
    def test_energy_option_always_scores_high(self):
        from cg.api import Option, SelectContext

        o = Option(type=OptionType.ENERGY, area=AreaType.ACTIVE, index=0, energyIndex=0, count=1)
        fs = jm.FieldState(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
            active_fighting_energy_count=0,
        )
        plan = jm.AttackPlan()
        score = jm._score_option(
            obs=MagicMock(), o=o, context=SelectContext.DISCARD_ENERGY, my_index=0,
            state=None, my_state=make_player_state(), fs=fs, plan=plan,
        )
        assert score == 9000
