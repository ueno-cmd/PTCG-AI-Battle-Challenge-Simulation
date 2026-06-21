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


# ==================== ユーティリティ ====================
def get_card(obs: Observation, area: AreaType, index: int, player_index: int):
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


def prize_count(pokemon: Pokemon) -> int:
    """KO 時に相手が取るプライズ枚数を返す"""
    data = card_table[pokemon.id]
    count = 2 if data.ex else 1
    for card in pokemon.energyCards:
        if card.id == 12:  # Legacy Energy
            count -= 1
    return max(0, count)


def pokemon_score(pokemon: Pokemon) -> int:
    """対象ポケモンの戦術的価値をヒューリスティックに評価する"""
    data  = card_table[pokemon.id]
    score = prize_count(pokemon) * 1000
    score += len(pokemon.energies) * 150
    score += len(pokemon.tools) * 100
    if data.stage2:
        score += 250
    elif data.stage1:
        score += 130
    score += pokemon.hp
    return score


def energy_score(pokemon: Pokemon) -> int:
    """エネルギー付与先ポケモンの優先度スコアを返す"""
    score        = 8000
    energy_count = len(pokemon.energies)
    if pokemon.id == Decidueye_ex:
        score += 500
        if energy_count < 2:
            score += 200
        else:
            score -= 300
    elif pokemon.id in (Rowlet, Dartrix):
        score += 50
    elif pokemon.id == Teal_Mask_Ogerpon_ex:
        score -= 200
    return score


# ==================== フィールド状態 ====================
def _collect_field_state(my_state) -> tuple:
    """バトル場・ベンチ・手札・捨て山のカウントと Decidueye ex 準備状況を返す"""
    field_counts    = defaultdict(int)
    hand_counts     = defaultdict(int)
    discard_counts  = defaultdict(int)
    decidueye_ready = False

    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id == Decidueye_ex and len(card.energies) >= 1:
            decidueye_ready = True

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    return field_counts, hand_counts, discard_counts, decidueye_ready


# ==================== 攻撃プラン計算 ====================
def calc_attack_plan(my_state, sniper_active: bool, can_switch: bool) -> DecidPlan:
    """Sniper's Eye が発動しているときのみ Crushing Arrow プランを立てる"""
    new_plan = DecidPlan()

    if not sniper_active:
        return new_plan

    # バトル場 → ベンチの順に Decidueye ex を探す
    my_cards = list(my_state.active) + list(my_state.bench)
    for i, pokemon in enumerate(my_cards):
        if pokemon is None:
            continue
        if i != 0 and not can_switch:
            break
        if pokemon.id == Decidueye_ex and len(pokemon.energies) >= 1:
            new_plan.attacker     = i
            new_plan.attack_index = 0   # Crushing Arrow（唯一の技）
            new_plan.target       = 0   # 相手アクティブを狙う
            new_plan.sniper_active = True
            break

    return new_plan


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
