import os
from collections import defaultdict
from dataclasses import dataclass

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, to_observation_class,
)

# ==================== カードID定数 ====================
Rowlet               = 1020
Dartrix              = 1021
Decidueye_ex         = 1022
Teal_Mask_Ogerpon_ex = 96
Budew                = 235
Iron_Leaves          = 27
Basic_G_Energy       = 1
Judge                = 1213
Xerosic              = 1197
Crushing_Hammer      = 1120
Rare_Candy           = 1079
Ultra_Ball           = 1121
Buddy_Buddy_Poffin   = 1086
Bug_Catching_Set     = 1094
Dusk_Ball            = 1102
Boss_Orders          = 1182
Carmine              = 1192
Explorer_Guidance    = 1185
Night_Stretcher      = 1097
Hand_Trimmer         = 1087
Prime_Catcher        = 1088
Pokegear             = 1122

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    # card_table を初回のみ構築する
    global card_table
    if not card_table:
        card_table = {c.cardId: c for c in all_card_data()}
    return card_table


# ==================== デッキ（遅延初期化）====================
my_deck: list[int] = []


def _load_deck() -> list[int]:
    # deck.csv を初回のみ読み込む
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
        my_deck = []
    return my_deck


# ==================== ターン状態管理 ====================
@dataclass
class DecidPlan:
    attacker:      int  = -1
    target:        int  = -1
    attack_index:  int  = -1
    sniper_active: bool = False


plan:     DecidPlan = DecidPlan()
pre_turn: int       = 0


def _reset_turn_state() -> None:
    # ターンごとに計画状態をリセット
    global plan
    plan = DecidPlan()


# ==================== メインエージェント（スタブ）====================
def agent(obs_dict: dict) -> list[int]:
    # ジュナイパーexコントロールエージェントのメインエントリーポイント
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        _load_deck()
        return my_deck

    _build_card_table()

    global plan, pre_turn

    state    = obs.current
    select   = obs.select
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]

    if pre_turn != state.turn:
        pre_turn = state.turn
        _reset_turn_state()

    scores = [0] * len(select.option)
    return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
