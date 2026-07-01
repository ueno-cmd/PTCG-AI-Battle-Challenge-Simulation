import os
from collections import defaultdict
from dataclasses import dataclass

from cg.api import (
    AreaType, CardType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, to_observation_class,
)

# ==================== カードID定数 ====================
Impidimp      = 646
Morgrem       = 647
Grimmsnarl_ex = 648
Morpeko       = 649
Munkidori     = 112
Dudunsparce   = 66
Dunsparce     = 305

Dawn                   = 1231
Rare_Candy             = 1079
Buddy_Buddy_Poffin     = 1086
Lillie_Determination   = 1227
Poke_Pad               = 1152
Night_Stretcher        = 1097
Xerosics_Machinations  = 1197
Energy_Recycler        = 1139
Spikemuth_Gym          = 1259
Heros_Cape             = 1159

Basic_D_Energy = 7

# ==================== アタックID（_build_card_table で設定）====================
Shadow_Bullet_ID: int = 0
Spiky_Wheel_ID:   int = 0

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築し、攻撃IDも設定する"""
    global card_table, Shadow_Bullet_ID, Spiky_Wheel_ID
    if not card_table:
        card_table       = {c.cardId: c for c in all_card_data()}
        grimmsnarl_data  = card_table[Grimmsnarl_ex]
        morpeko_data     = card_table[Morpeko]
        Shadow_Bullet_ID = grimmsnarl_data.attacks[0]  # Shadow Bullet
        Spiky_Wheel_ID   = morpeko_data.attacks[0]     # Spiky Wheel
    return card_table


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
        my_deck = []
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


# ==================== フィールド状態 ====================
@dataclass
class FieldState:
    """毎ターン計算されるフィールド状態"""
    field_counts:            defaultdict
    hand_counts:             defaultdict
    discard_counts:          defaultdict
    grimmsnarl_active:       bool
    grimmsnarl_energy_count: int
    impidimp_bench_idx:      int
    munkidori_bench_idx:     int
    rare_candy_in_hand:      bool
    my_active_hp:            int
    op_active_hp:            int
    op_bench_hp:             list


def _collect_field_state(my_state, op_state) -> FieldState:
    """バトル場・ベンチ・手札・トラッシュから行動判断に必要な状態を収集する"""
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)

    grimmsnarl_active       = False
    grimmsnarl_energy_count = 0
    impidimp_bench_idx      = -1
    munkidori_bench_idx     = -1
    my_active_hp            = 0

    for card in my_state.active:
        if card is None:
            continue
        field_counts[card.id] += 1
        my_active_hp = card.hp
        if card.id == Grimmsnarl_ex:
            grimmsnarl_active       = True
            grimmsnarl_energy_count = len(card.energies)

    for i, card in enumerate(my_state.bench):
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id == Impidimp and impidimp_bench_idx == -1:
            impidimp_bench_idx = i
        elif card.id == Munkidori and munkidori_bench_idx == -1:
            munkidori_bench_idx = i

    for card in my_state.hand:
        if card is None:
            continue
        hand_counts[card.id] += 1

    for card in my_state.discard:
        if card is None:
            continue
        discard_counts[card.id] += 1

    op_active_hp = 0
    for card in op_state.active:
        if card is not None:
            op_active_hp = card.hp

    op_bench_hp = [card.hp for card in op_state.bench if card is not None]

    rare_candy_in_hand = hand_counts[Rare_Candy] >= 1

    return FieldState(
        field_counts=field_counts,
        hand_counts=hand_counts,
        discard_counts=discard_counts,
        grimmsnarl_active=grimmsnarl_active,
        grimmsnarl_energy_count=grimmsnarl_energy_count,
        impidimp_bench_idx=impidimp_bench_idx,
        munkidori_bench_idx=munkidori_bench_idx,
        rare_candy_in_hand=rare_candy_in_hand,
        my_active_hp=my_active_hp,
        op_active_hp=op_active_hp,
        op_bench_hp=op_bench_hp,
    )


def agent(obs_dict: dict) -> list[int]:
    """暫定実装（Task 4 で完成させる）"""
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        _load_deck()
        return my_deck
    return [0]
