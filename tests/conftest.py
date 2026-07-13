# tests/conftest.py
import sys
import os
from unittest.mock import MagicMock, patch

# libcg.so のロードを防ぐため cg.sim を先にモック（必須）
sys.modules['cg.sim'] = MagicMock()
sys.modules['cg.game'] = MagicMock()

# cg.api のデータクラスをインポート（pure Pythonなのでモック不要）
from cg.api import (
    AreaType, CardType, EnergyType,
    SelectContext, OptionType, SelectType,
    Card, Pokemon, PlayerState, State,
    SelectData, Option, Observation,
)

import pytest


def make_pokemon(
    id: int = 1,
    hp: int = 100,
    max_hp: int = None,
    appear_this_turn: bool = False,
    energies: list = None,
) -> Pokemon:
    """テスト用Pokemonオブジェクトを生成する"""
    return Pokemon(
        id=id,
        serial=id,
        hp=hp,
        maxHp=max_hp if max_hp is not None else hp,
        appearThisTurn=appear_this_turn,
        energies=energies or [],
        energyCards=[],
        tools=[],
        preEvolution=[],
    )


def make_player_state(
    active_pokemon: Pokemon = None,
    bench: list = None,
    hand: list = None,
    discard: list = None,
    hand_count: int = 5,
    deck_count: int = 50,
    prize_count: int = 6,
) -> PlayerState:
    """テスト用PlayerStateオブジェクトを生成する"""
    return PlayerState(
        active=[active_pokemon] if active_pokemon else [],
        bench=bench or [],
        benchMax=5,
        deckCount=deck_count,
        discard=discard or [],
        prize=[None] * prize_count,
        handCount=hand_count,
        hand=hand or [],
        poisoned=False,
        burned=False,
        asleep=False,
        paralyzed=False,
        confused=False,
    )


def make_main_obs(
    your_index: int = 0,
    my_state: PlayerState = None,
    op_state: PlayerState = None,
    options: list = None,
    turn: int = 3,
    context: SelectContext = SelectContext.MAIN,
    select_type: SelectType = SelectType.MAIN,
) -> dict:
    """obs_dictを生成する（agent()に渡すdict形式）。

    デフォルトはMAINコンテキストだが、context/select_typeを指定すれば
    SETUP_ACTIVE_POKEMONなど他のコンテキストのobs_dictも生成できる。
    """
    my = my_state or make_player_state(active_pokemon=make_pokemon(id=1, hp=300))
    op = op_state or make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
    players = [my, op] if your_index == 0 else [op, my]

    def player_to_dict(ps: PlayerState) -> dict:
        def card_to_dict(p) -> dict:
            if p is None:
                return None
            if isinstance(p, Pokemon):
                return {
                    "id": p.id, "serial": p.serial,
                    "hp": p.hp, "maxHp": p.maxHp,
                    "appearThisTurn": p.appearThisTurn,
                    "energies": [int(e) for e in p.energies],
                    "energyCards": [], "tools": [], "preEvolution": [],
                }
            # Card（手札など、場に出ていないためHP/エネルギーを持たない実体）
            return {
                "id": p.id,
                "serial": getattr(p, "serial", p.id),
                "playerIndex": getattr(p, "playerIndex", 0),
            }
        return {
            "active": [card_to_dict(p) for p in ps.active],
            "bench": [card_to_dict(p) for p in ps.bench],
            "benchMax": ps.benchMax,
            "deckCount": ps.deckCount,
            "discard": [],
            "prize": [None] * len(ps.prize),
            "handCount": ps.handCount,
            "hand": [card_to_dict(p) for p in ps.hand],
            "poisoned": False, "burned": False,
            "asleep": False, "paralyzed": False, "confused": False,
        }

    def option_to_dict(o: Option) -> dict:
        return {k: v for k, v in {
            "type": int(o.type),
            "number": o.number,
            "area": int(o.area) if o.area is not None else None,
            "index": o.index,
            "playerIndex": o.playerIndex,
            "inPlayArea": int(o.inPlayArea) if o.inPlayArea is not None else None,
            "inPlayIndex": o.inPlayIndex,
            "attackId": o.attackId,
        }.items() if v is not None}

    return {
        "select": {
            "type": int(select_type),
            "context": int(context),
            "minCount": 1,
            "maxCount": 1,
            "remainDamageCounter": 0,
            "remainEnergyCost": 0,
            "option": [option_to_dict(o) for o in (options or [])],
            "deck": None,
            "contextCard": None,
            "effect": None,
        },
        "logs": [],
        "current": {
            "turn": turn,
            "turnActionCount": 0,
            "yourIndex": your_index,
            "firstPlayer": 0,
            "supporterPlayed": False,
            "stadiumPlayed": False,
            "energyAttached": False,
            "retreated": False,
            "result": -1,
            "stadium": [],
            "looking": None,
            "players": [player_to_dict(p) for p in players],
        },
        "search_begin_input": None,
    }
