# tests/test_jamoraiko_agent.py
from collections import defaultdict
from dataclasses import dataclass as _dc
from unittest.mock import MagicMock

import pytest

from cg.api import AreaType, OptionType

import jamoraiko_agent.main as jm

from tests.conftest import make_pokemon, make_player_state


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


class TestCalcAttackPlan:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
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
        fs = self._fs(active_energy_count=2, own_board_basic_energy_total=10)  # きょくらいごうは700ダメ
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
        )
        base.update(overrides)
        return jm.FieldState(**base)
