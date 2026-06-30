# src/cinderace_starmie_agent/main.py
import os
from collections import defaultdict
from dataclasses import dataclass, field

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, to_observation_class,
)

# ==================== カードID定数 ====================
Scorbunny            = 664
Raboot               = 665
Cinderace            = 666
Staryu               = 1030
Mega_Starmie_ex      = 1031

Buddy_Buddy_Poffin   = 1086
Ultra_Ball           = 1121
Mega_Signal          = 1145
Night_Stretcher      = 1097
Heros_Cape           = 1159
Pokegear_30          = 1122
Crushing_Hammer      = 1120
Salvatore            = 1189
Hilda                = 1225
Lillie_Determination = 1227
Wallys_Compassion    = 1229

Basic_Water_Energy   = 3
Ignition_Energy      = 17

# ==================== アタックID（_build_card_table で設定）====================
Turbo_Flare_ID:  int = 0
Jetting_Blow_ID: int = 0
Nebula_Beam_ID:  int = 0

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築し、攻撃IDも設定する"""
    global card_table, Turbo_Flare_ID, Jetting_Blow_ID, Nebula_Beam_ID
    if not card_table:
        card_table      = {c.cardId: c for c in all_card_data()}
        cinderace_data  = card_table[Cinderace]
        starmie_data    = card_table[Mega_Starmie_ex]
        Turbo_Flare_ID  = cinderace_data.attacks[0]   # Turbo Flare
        Jetting_Blow_ID = starmie_data.attacks[0]     # Jetting Blow
        Nebula_Beam_ID  = starmie_data.attacks[1]     # Nebula Beam
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
    field_counts:          defaultdict
    hand_counts:           defaultdict
    discard_counts:        defaultdict
    cinderace_active:      bool
    starmie_bench_idx:     int
    starmie_bench_energy:  int
    starmie_active_damage: int
    op_active_hp:          int
    wally_in_hand:         bool
    switch_to_starmie:     bool


def _collect_field_state(my_state, op_state) -> FieldState:
    """バトル場・ベンチ・手札・トラッシュから行動判断に必要な状態を収集する"""
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)

    cinderace_active     = False
    starmie_bench_idx    = -1
    starmie_bench_energy = 0
    starmie_active_dmg   = 0

    for card in my_state.active:
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id == Cinderace and len(card.energies) >= 1:
            cinderace_active = True
        elif card.id == Mega_Starmie_ex:
            starmie_active_dmg = card.maxHp - card.hp

    for i, card in enumerate(my_state.bench):
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id == Mega_Starmie_ex and starmie_bench_idx == -1:
            starmie_bench_idx    = i
            starmie_bench_energy = len(card.energies)

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    op_active_hp = 0
    for card in op_state.active:
        if card is not None:
            op_active_hp = card.hp

    wally_in_hand     = hand_counts[Wallys_Compassion] >= 1
    switch_to_starmie = (
        starmie_bench_idx >= 0
        and starmie_bench_energy >= 1
        and not cinderace_active
    )

    return FieldState(
        field_counts=field_counts,
        hand_counts=hand_counts,
        discard_counts=discard_counts,
        cinderace_active=cinderace_active,
        starmie_bench_idx=starmie_bench_idx,
        starmie_bench_energy=starmie_bench_energy,
        starmie_active_damage=starmie_active_dmg,
        op_active_hp=op_active_hp,
        wally_in_hand=wally_in_hand,
        switch_to_starmie=switch_to_starmie,
    )


def agent(obs_dict: dict) -> list[int]:
    """暫定実装（Task 4 で完成させる）"""
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        _load_deck()
        return my_deck
    return [0]
