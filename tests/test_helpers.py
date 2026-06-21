# tests/test_helpers.py
# conftest.pyが先にロードされることで cg.sim はモック済み

from mascarnage_agent.main import no_damage_counter, prize_count
from tests.conftest import make_pokemon


def test_no_damage_counter_returns_true_for_milotic_ex():
    """ミロカロスex（207）はダメカンを置けない"""
    p = make_pokemon(id=207)
    assert no_damage_counter(p) is True


def test_no_damage_counter_returns_false_for_normal_pokemon():
    """通常ポケモンはダメカンを置ける"""
    p = make_pokemon(id=999)
    assert no_damage_counter(p) is False


def test_prize_count_normal_pokemon():
    """非exポケモンはサイド1枚"""
    from cg.api import CardData, CardType, EnergyType
    card_table = {
        1: CardData(
            cardId=1, name="Normal", cardType=CardType.POKEMON,
            retreatCost=1, hp=100, weakness=None, resistance=None,
            energyType=EnergyType.COLORLESS,
            basic=True, stage1=False, stage2=False,
            ex=False, megaEx=False, tera=False, aceSpec=False,
            evolvesFrom=None, skills=[], attacks=[],
        )
    }
    p = make_pokemon(id=1)
    assert prize_count(p, card_table) == 1


def test_prize_count_ex_pokemon():
    """exポケモンはサイド2枚"""
    from cg.api import CardData, CardType, EnergyType
    card_table = {
        2: CardData(
            cardId=2, name="Test ex", cardType=CardType.POKEMON,
            retreatCost=2, hp=300, weakness=None, resistance=None,
            energyType=EnergyType.COLORLESS,
            basic=False, stage1=False, stage2=False,
            ex=True, megaEx=False, tera=False, aceSpec=False,
            evolvesFrom=None, skills=[], attacks=[],
        )
    }
    p = make_pokemon(id=2)
    assert prize_count(p, card_table) == 2


def test_prize_count_mega_ex_pokemon():
    """メガexポケモンはサイド3枚"""
    from cg.api import CardData, CardType, EnergyType
    card_table = {
        3: CardData(
            cardId=3, name="Test Mega ex", cardType=CardType.POKEMON,
            retreatCost=3, hp=400, weakness=None, resistance=None,
            energyType=EnergyType.COLORLESS,
            basic=False, stage1=False, stage2=False,
            ex=True, megaEx=True, tera=False, aceSpec=False,
            evolvesFrom=None, skills=[], attacks=[],
        )
    }
    p = make_pokemon(id=3)
    assert prize_count(p, card_table) == 3
