import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, all_attack, to_observation_class,
)

# ==================== カードID定数 ====================
Raging_Bolt_ex          = 63    # タケルライコex
Iono_Voltorb            = 265   # ナンジャモのビリリダマ
Iono_Tadbulb            = 268   # ナンジャモのズピカ
Iono_Bellibolt_ex       = 269   # ナンジャモのハラバリーex
Iono_Wattrel            = 270   # ナンジャモのカイデン
Iono_Kilowattrel        = 271   # ナンジャモのタイカイデン
Buddy_Buddy_Poffin      = 1086  # なかよしポフィン
Night_Stretcher         = 1097  # 夜のタンカ
Max_Rod                 = 1110  # つりざおMAX (ACE SPEC)
Energy_Retrieval        = 1118  # エネルギー回収
Energy_Search           = 1119  # エネルギー転送（山札から基本エネルギー1枚サーチ）
Ultra_Ball               = 1121  # ハイパーボール
Switch                   = 1123  # ポケモンいれかえ
Boss_Orders               = 1182  # ボスの指令
Lillie_Determination       = 1227  # リーリエの決心
Canari                     = 1233  # カナリィ
Levincia                   = 1254  # ハッコウシティ
Basic_Lightning_Energy      = 4
Basic_Fighting_Energy       = 6

IONO_POKEMON_IDS = {Iono_Voltorb, Iono_Tadbulb, Iono_Bellibolt_ex, Iono_Wattrel, Iono_Kilowattrel}

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}
attack_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築する"""
    global card_table
    if not card_table:
        card_table = {c.cardId: c for c in all_card_data()}
    return card_table


def _build_attack_table() -> dict:
    """attack_table（attackId -> Attack）を初回のみ構築する"""
    global attack_table
    if not attack_table:
        attack_table = {a.attackId: a for a in all_attack()}
    return attack_table


def _attack_id_by_name(name: str) -> "int | None":
    """技名からattackIdを逆引きする（cg.apiはKaggle環境でしか実行できないため、
    マジックナンバーを決め打ちせずattack_tableから解決する）"""
    for attack_id, attack in attack_table.items():
        if attack.name == name:
            return attack_id
    return None


# ==================== デッキ（遅延初期化）====================
my_deck: list[int] = []


def _load_deck() -> list[int]:
    """deck.csv を初回のみ読み込む"""
    global my_deck
    if my_deck:
        return my_deck
    file_path = "deck.csv"
    if not os.path.exists(file_path):
        file_path = "/kaggle_simulations/agent/" + file_path
    try:
        with open(file_path, "r") as f:
            rows = f.read().split("\n")
        my_deck = [int(rows[i]) for i in range(60)]
    except FileNotFoundError:
        from decks.jamoraiko_20260713 import DECK
        my_deck = [card_id for card_id, count in DECK for _ in range(count)]
    return my_deck


# ==================== ユーティリティ ====================
def get_card(obs: Observation, area: AreaType, index: int, player_index: int) -> "Pokemon | Card | None":
    """指定ゾーンからカードを安全に取得する"""
    ps = obs.current.players[player_index]
    match area:
        case AreaType.DECK:
            return obs.select.deck[index]
        case AreaType.HAND:
            return ps.hand[index]
        case AreaType.DISCARD:
            return ps.discard[index]
        case AreaType.ACTIVE:
            return ps.active[index]
        case AreaType.BENCH:
            return ps.bench[index]
        case AreaType.PRIZE:
            return ps.prize[index]
        case AreaType.STADIUM:
            return obs.current.stadium[index]
        case AreaType.LOOKING:
            return obs.current.looking[index]
        case _:
            return None


# ==================== メインエージェント ====================
def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG エージェント（ジャモライコ）。

    Returns:
        list[int]: 選択するオプションのインデックスリスト
    """
    # 初回のデッキ選択時は select が None で、current/logs 等の必須フィールドが
    # obs_dict に含まれない場合がある（to_observation_class は dataclass の必須
    # フィールド欠落で例外を送出するため、変換前に select の有無を判定する）。
    if obs_dict.get("select") is None:
        return _load_deck()

    obs = to_observation_class(obs_dict)

    _build_card_table()
    _build_attack_table()

    state    = obs.current
    select   = obs.select
    my_index = state.yourIndex

    # Task 3以降でスコアリングを追加するまでは先頭を返す暫定実装
    return list(range(select.minCount))
