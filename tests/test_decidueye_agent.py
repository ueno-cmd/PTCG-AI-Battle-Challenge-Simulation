import pytest
from dataclasses import dataclass
from cg.api import CardType, EnergyType, Card
import decidueye_agent.main as dm
from unittest.mock import patch
from tests.conftest import make_pokemon, make_player_state


@dataclass
class MockCardData:
    cardId:     int
    name:       str               = ""
    ex:         bool              = False
    stage2:     bool              = False
    stage1:     bool              = False
    cardType:   CardType          = CardType.POKEMON
    weakness:   EnergyType | None = None
    resistance: EnergyType | None = None


def _card(card_id: int, **kwargs) -> MockCardData:
    return MockCardData(cardId=card_id, **kwargs)


@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        dm.Rowlet:               _card(dm.Rowlet),
        dm.Dartrix:              _card(dm.Dartrix, stage1=True),
        dm.Decidueye_ex:         _card(dm.Decidueye_ex, ex=True, stage2=True),
        dm.Teal_Mask_Ogerpon_ex: _card(dm.Teal_Mask_Ogerpon_ex, ex=True),
        dm.Budew:                _card(dm.Budew),
        dm.Iron_Leaves:          _card(dm.Iron_Leaves),
        dm.Judge:                _card(dm.Judge,     cardType=CardType.SUPPORTER),
        dm.Xerosic:              _card(dm.Xerosic,   cardType=CardType.SUPPORTER),
        dm.Rare_Candy:           _card(dm.Rare_Candy,         cardType=CardType.ITEM),
        dm.Ultra_Ball:           _card(dm.Ultra_Ball,         cardType=CardType.ITEM),
        dm.Buddy_Buddy_Poffin:   _card(dm.Buddy_Buddy_Poffin, cardType=CardType.ITEM),
        dm.Bug_Catching_Set:     _card(dm.Bug_Catching_Set,   cardType=CardType.ITEM),
        dm.Dusk_Ball:            _card(dm.Dusk_Ball,          cardType=CardType.ITEM),
        dm.Crushing_Hammer:      _card(dm.Crushing_Hammer,    cardType=CardType.ITEM),
        dm.Boss_Orders:          _card(dm.Boss_Orders,        cardType=CardType.SUPPORTER),
        dm.Carmine:              _card(dm.Carmine,            cardType=CardType.SUPPORTER),
        dm.Explorer_Guidance:    _card(dm.Explorer_Guidance,  cardType=CardType.SUPPORTER),
        dm.Night_Stretcher:      _card(dm.Night_Stretcher,    cardType=CardType.ITEM),
        dm.Hand_Trimmer:         _card(dm.Hand_Trimmer,       cardType=CardType.ITEM),
        dm.Prime_Catcher:        _card(dm.Prime_Catcher,      cardType=CardType.ITEM),
        dm.Pokegear:             _card(dm.Pokegear,           cardType=CardType.ITEM),
        dm.Basic_G_Energy:       _card(dm.Basic_G_Energy,     cardType=CardType.BASIC_ENERGY),
        12: _card(12, cardType=CardType.SPECIAL_ENERGY),
    }
    monkeypatch.setattr(dm, "card_table", table)
    return table


class TestPrizeCount:
    def test_regular_pokemon_yields_1(self):
        p = make_pokemon(id=dm.Rowlet)
        assert dm.prize_count(p) == 1

    def test_ex_pokemon_yields_2(self):
        p = make_pokemon(id=dm.Decidueye_ex)
        assert dm.prize_count(p) == 2

    def test_legacy_energy_reduces_count(self):
        p = make_pokemon(id=dm.Decidueye_ex)
        legacy = Card(id=12, serial=12, playerIndex=0)
        object.__setattr__(p, "energyCards", [legacy])
        assert dm.prize_count(p) == 1


class TestPokemonScore:
    def test_ex_scores_higher_than_regular(self):
        ex  = make_pokemon(id=dm.Decidueye_ex, hp=320)
        reg = make_pokemon(id=dm.Rowlet, hp=60)
        assert dm.pokemon_score(ex) > dm.pokemon_score(reg)

    def test_more_energies_yields_higher_score(self):
        no_e  = make_pokemon(id=dm.Decidueye_ex, energies=[])
        two_e = make_pokemon(id=dm.Decidueye_ex, energies=[1, 1])
        assert dm.pokemon_score(two_e) > dm.pokemon_score(no_e)


class TestEnergyScore:
    def test_decidueye_ex_prioritised(self):
        """Decidueye ex はその他ポケモンより高いエネルギー付与優先度"""
        decidueye = make_pokemon(id=dm.Decidueye_ex, energies=[])
        rowlet    = make_pokemon(id=dm.Rowlet, energies=[])
        assert dm.energy_score(decidueye) > dm.energy_score(rowlet)

    def test_decidueye_deprioritised_when_full(self):
        """Decidueye ex に 2 枚以上エネルギーがある場合は優先度を下げる"""
        low_e  = make_pokemon(id=dm.Decidueye_ex, energies=[1])
        full_e = make_pokemon(id=dm.Decidueye_ex, energies=[1, 1, 1])
        assert dm.energy_score(low_e) > dm.energy_score(full_e)


class TestCollectFieldState:
    def test_counts_decidueye_ex_in_field(self):
        dec = make_pokemon(id=dm.Decidueye_ex)
        ps  = make_player_state(active_pokemon=dec)
        fc, _, _, ready = dm._collect_field_state(ps)
        assert fc[dm.Decidueye_ex] == 1
        assert ready is False  # エネルギーなし

    def test_decidueye_ready_when_has_energy(self):
        dec = make_pokemon(id=dm.Decidueye_ex, energies=[1])
        ps  = make_player_state(active_pokemon=dec)
        _, _, _, ready = dm._collect_field_state(ps)
        assert ready is True


class TestCalcAttackPlan:
    def test_attacks_when_sniper_active_and_energy_ready(self):
        """Sniper's Eye 発動中 + Decidueye ex にエネルギー 1 枚 → 攻撃プランを立てる"""
        dec = make_pokemon(id=dm.Decidueye_ex, energies=[1])
        ps  = make_player_state(active_pokemon=dec)
        result = dm.calc_attack_plan(ps, sniper_active=True, can_switch=False)
        assert result.attacker     == 0
        assert result.attack_index == 0
        assert result.sniper_active is True

    def test_no_attack_without_sniper(self):
        """op_hand != 4（Sniper's Eye 未発動）→ 攻撃しない"""
        dec = make_pokemon(id=dm.Decidueye_ex, energies=[1])
        ps  = make_player_state(active_pokemon=dec)
        result = dm.calc_attack_plan(ps, sniper_active=False, can_switch=False)
        assert result.attacker == -1

    def test_no_attack_without_energy(self):
        """Sniper's Eye 発動中でもエネルギー 0 枚 → 攻撃しない"""
        dec = make_pokemon(id=dm.Decidueye_ex, energies=[])
        ps  = make_player_state(active_pokemon=dec)
        result = dm.calc_attack_plan(ps, sniper_active=True, can_switch=False)
        assert result.attacker == -1

    def test_attacks_from_bench_when_can_switch(self):
        """ベンチの Decidueye ex + can_switch=True → 攻撃プランを立てる"""
        rowlet = make_pokemon(id=dm.Rowlet)
        dec    = make_pokemon(id=dm.Decidueye_ex, energies=[1])
        ps     = make_player_state(active_pokemon=rowlet, bench=[dec])
        result = dm.calc_attack_plan(ps, sniper_active=True, can_switch=True)
        assert result.attacker == 1  # ベンチ index 0 → 全体 index 1


class TestAgentInit:
    def test_returns_deck_when_select_is_none(self):
        """select が None のとき my_deck を返す"""
        obs_dict = {"select": None, "logs": [], "current": None, "search_begin_input": None}
        with patch.object(dm, "my_deck", [1] * 60):
            result = dm.agent(obs_dict)
        assert result == [1] * 60
