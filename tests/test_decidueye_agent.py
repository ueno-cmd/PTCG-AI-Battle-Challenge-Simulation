import pytest
from dataclasses import dataclass
from cg.api import CardType, EnergyType
import decidueye_agent.main as dm
from unittest.mock import patch


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


class TestAgentInit:
    def test_returns_deck_when_select_is_none(self):
        """select が None のとき my_deck を返す"""
        obs_dict = {"select": None, "logs": [], "current": None, "search_begin_input": None}
        with patch.object(dm, "my_deck", [1] * 60):
            result = dm.agent(obs_dict)
        assert result == [1] * 60
