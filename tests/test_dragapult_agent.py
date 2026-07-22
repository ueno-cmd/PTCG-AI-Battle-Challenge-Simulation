# tests/test_dragapult_agent.py
from collections import defaultdict
from dataclasses import dataclass, field as dc_field

from cg.api import CardType

import dragapult_agent.main as dm


@dataclass
class _MockCardData:
    cardId: int
    cardType: CardType = CardType.BASIC_ENERGY


@dataclass
class _MockPokemon:
    id: int
    energies: list = dc_field(default_factory=list)
    energyCards: list = dc_field(default_factory=list)


def test_attach_score_active_gets_priority_when_bench_attacker_ready_and_zero_energy():
    """energy_count=0・active=True・bench_attackerありなら+400点される既存挙動を維持"""
    card_table = {dm.Basic_Fire_Energy: _MockCardData(cardId=dm.Basic_Fire_Energy)}
    pokemon = _MockPokemon(id=dm.Dragapult_ex)
    score = dm._attach_score(
        dm.Basic_Fire_Energy, pokemon, True,
        card_table=card_table, can_switch=False, bench_attacker=True,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert score == 20000 + 400


def test_attach_score_returns_minus_one_for_bench_pokemon_with_full_energy():
    """energy_count>=2かつactive=Falseの控えポケモンには、これ以上エネルギーを
    貼る意味がないため-1（非採用）を返す既存挙動を維持"""
    card_table = {dm.Basic_Fire_Energy: _MockCardData(cardId=dm.Basic_Fire_Energy)}
    pokemon = _MockPokemon(id=dm.Dragapult_ex, energies=[1, 1], energyCards=[
        _MockCardData(cardId=dm.Basic_Fire_Energy)])
    score = dm._attach_score(
        dm.Basic_Fire_Energy, pokemon, False,
        card_table=card_table, can_switch=False, bench_attacker=False,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert score == -1


def test_boss_orders_score_confirmed_pull_target():
    """確定的な引き剥がし先がある場合は最優先スコア"""
    assert dm._boss_orders_score(has_pull_target=True, explore_roll=0.99, epsilon=0.28) == 60000


def test_boss_orders_score_exploratory_use_within_epsilon():
    """確定的な引き剥がし先が無くても、乱数がepsilon未満なら探索的に先出しする"""
    assert dm._boss_orders_score(has_pull_target=False, explore_roll=0.1, epsilon=0.28) == 30000


def test_boss_orders_score_conserve_outside_epsilon():
    """確定的な引き剥がし先が無く、乱数もepsilon以上なら温存（0点）"""
    assert dm._boss_orders_score(has_pull_target=False, explore_roll=0.5, epsilon=0.28) == 0


def test_boss_orders_score_boundary_is_exclusive():
    """explore_roll == epsilon ちょうどは温存側（lucario_agentのrng.random() < EPSILONと同じ境界）"""
    assert dm._boss_orders_score(has_pull_target=False, explore_roll=0.28, epsilon=0.28) == 0
