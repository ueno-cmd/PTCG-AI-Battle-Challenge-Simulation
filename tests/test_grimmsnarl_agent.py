import pytest
from dataclasses import dataclass, field
from collections import defaultdict
from cg.api import CardType, Card

import grimmsnarl_agent.main as gm
from tests.conftest import make_pokemon, make_player_state


@dataclass
class MockCardData:
    cardId:   int
    name:     str      = ""
    ex:       bool     = False
    stage1:   bool     = False
    stage2:   bool     = False
    cardType: CardType = CardType.POKEMON
    attacks:  list     = field(default_factory=list)


@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        gm.Impidimp:        MockCardData(cardId=gm.Impidimp, attacks=[9101]),
        gm.Morgrem:         MockCardData(cardId=gm.Morgrem, stage1=True, attacks=[9101]),
        gm.Grimmsnarl_ex:   MockCardData(cardId=gm.Grimmsnarl_ex, stage2=True, ex=True, attacks=[9102]),
        gm.Morpeko:         MockCardData(cardId=gm.Morpeko, attacks=[9103]),
        gm.Munkidori:       MockCardData(cardId=gm.Munkidori, attacks=[9104]),
        gm.Dudunsparce:     MockCardData(cardId=gm.Dudunsparce, stage1=True, attacks=[9105]),
        gm.Dunsparce:       MockCardData(cardId=gm.Dunsparce, attacks=[9106]),
        gm.Rare_Candy:      MockCardData(cardId=gm.Rare_Candy, cardType=CardType.ITEM),
        gm.Buddy_Buddy_Poffin: MockCardData(cardId=gm.Buddy_Buddy_Poffin, cardType=CardType.ITEM),
        gm.Dawn:            MockCardData(cardId=gm.Dawn, cardType=CardType.SUPPORTER),
        gm.Lillie_Determination: MockCardData(cardId=gm.Lillie_Determination, cardType=CardType.SUPPORTER),
        gm.Basic_D_Energy:  MockCardData(cardId=gm.Basic_D_Energy, cardType=CardType.BASIC_ENERGY),
    }
    monkeypatch.setattr(gm, "card_table", table)
    monkeypatch.setattr(gm, "Shadow_Bullet_ID", 9102)
    monkeypatch.setattr(gm, "Spiky_Wheel_ID", 9103)
    return table


# ==================== _collect_field_state ====================
class TestCollectFieldState:
    def test_grimmsnarl_active_detected(self):
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, energies=[7, 7])
        my_ps = make_player_state(active_pokemon=grimmsnarl)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.grimmsnarl_active is True
        assert fs.grimmsnarl_energy_count == 2

    def test_grimmsnarl_not_active_when_absent(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Impidimp))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.grimmsnarl_active is False
        assert fs.grimmsnarl_energy_count == 0

    def test_impidimp_bench_detected(self):
        impidimp = make_pokemon(id=gm.Impidimp)
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Morpeko),
            bench=[impidimp],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.impidimp_bench_idx == 0

    def test_impidimp_bench_absent_returns_minus1(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Morpeko))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.impidimp_bench_idx == -1

    def test_munkidori_bench_detected(self):
        munkidori = make_pokemon(id=gm.Munkidori, energies=[7])
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex),
            bench=[munkidori],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.munkidori_bench_idx == 0

    def test_rare_candy_in_hand_detected(self):
        candy = Card(id=gm.Rare_Candy, serial=1, playerIndex=0)
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Impidimp),
            hand=[candy],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.rare_candy_in_hand is True

    def test_op_active_hp(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=180))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.op_active_hp == 180

    def test_op_bench_hp_list(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex))
        op_bench = [make_pokemon(id=2, hp=30), make_pokemon(id=3, hp=90)]
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200), bench=op_bench)
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.op_bench_hp == [30, 90]
