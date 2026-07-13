# tests/test_jamoraiko_agent.py
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
