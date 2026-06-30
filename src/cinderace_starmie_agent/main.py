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


# ==================== スコアリング ====================
def _score_play(card_id: int, fs: FieldState, prize_count: int) -> int:
    """PLAY コンテキスト：手札からカードを使う際のスコア"""
    if card_id == Lillie_Determination:
        return 10000 if prize_count == 6 else 3000
    if card_id == Buddy_Buddy_Poffin:
        needs_scorbunny = fs.field_counts[Scorbunny] + fs.hand_counts[Scorbunny] == 0
        needs_staryu    = fs.field_counts[Staryu]    + fs.hand_counts[Staryu]    == 0
        return 8000 if (needs_scorbunny or needs_staryu) else 2000
    if card_id == Salvatore:
        has_staryu    = fs.field_counts[Staryu] >= 1
        needs_starmie = (
            fs.field_counts[Mega_Starmie_ex] + fs.hand_counts[Mega_Starmie_ex] == 0
        )
        return 7000 if (has_staryu and needs_starmie) else 2000
    if card_id == Wallys_Compassion:
        return 6500 if fs.starmie_active_damage > 0 else -1
    if card_id == Hilda:
        needs_cinderace = fs.field_counts[Cinderace] + fs.hand_counts[Cinderace] == 0
        needs_starmie   = (
            fs.field_counts[Mega_Starmie_ex] + fs.hand_counts[Mega_Starmie_ex] == 0
        )
        return 5000 if (needs_cinderace or needs_starmie) else 2000
    if card_id == Mega_Signal:
        return 4500 if fs.field_counts[Mega_Starmie_ex] == 0 else 1000
    if card_id == Pokegear_30:
        has_supporter = any(
            fs.hand_counts[c] >= 1
            for c in (Salvatore, Hilda, Lillie_Determination, Wallys_Compassion)
        )
        return 4000 if not has_supporter else 1500
    if card_id == Ultra_Ball:
        needs_any = (
            fs.field_counts[Cinderace]       + fs.hand_counts[Cinderace]       == 0
            or fs.field_counts[Mega_Starmie_ex] + fs.hand_counts[Mega_Starmie_ex] == 0
        )
        return 3000 if needs_any else -1
    if card_id == Night_Stretcher:
        useful = (
            fs.discard_counts[Staryu] >= 1
            or fs.discard_counts[Basic_Water_Energy] >= 1
            or fs.discard_counts[Cinderace] >= 1
        )
        return 2000 if useful else 500
    if card_id == Crushing_Hammer:
        return 1000
    return 2000


def _score_attach(pokemon: Pokemon, area: AreaType, card_id: int, fs: FieldState) -> int:
    """ATTACH コンテキスト：エネルギー/ツールの付与先スコア"""
    energy_count = len(pokemon.energies)
    if card_id == Ignition_Energy:
        # Cinderaceへのみ・0エネのときだけ（Turbo Flare 起動用）
        if pokemon.id == Cinderace and energy_count == 0:
            return 9000
        return -1
    if card_id == Heros_Cape:
        # Mega Starmie ex への Hero's Cape 装着を最優先
        return 8500 if pokemon.id == Mega_Starmie_ex else -1
    if card_id == Basic_Water_Energy:
        if pokemon.id == Mega_Starmie_ex:
            if area == AreaType.BENCH and energy_count <= 2:
                return 8000 + (3 - energy_count) * 100
            if area == AreaType.ACTIVE and energy_count == 0:
                return 7500
        if pokemon.id == Cinderace and energy_count == 0:
            return 7000
        return -1
    return 5000


def _score_attack(attack_id: int, fs: FieldState) -> int:
    """ATTACK コンテキスト：ワザ選択スコア"""
    if attack_id == Turbo_Flare_ID:
        return 1000
    if attack_id == Jetting_Blow_ID:
        # 相手HP ≤ 170 なら Jetting Blow + ベンチ50 でちょうど倒せる圏内
        return 1200 if fs.op_active_hp <= 170 else 800
    if attack_id == Nebula_Beam_ID:
        return 1200 if fs.op_active_hp > 170 else 800
    return 1000


def _score_card_option(
    obs: Observation,
    o,
    context,
    my_index: int,
    fs: FieldState,
    discard_hand_counts: defaultdict,
) -> int:
    """OptionType.CARD のコンテキスト別スコア"""
    card = get_card(obs, o.area, o.index, o.playerIndex)
    if card is None:
        return 0

    match context:
        case SelectContext.SETUP_ACTIVE_POKEMON:
            if card.id == Cinderace:
                return 100   # Explosiveness 特性でバトル場スタート最優先
            if card.id == Scorbunny:
                return 50
            if card.id == Staryu:
                return 30
            return 10

        case SelectContext.SWITCH | SelectContext.TO_ACTIVE:
            if o.playerIndex != my_index:
                return 0
            if not isinstance(card, Pokemon):
                return 0
            energy_count = len(card.energies)
            score = energy_count * 2
            if card.id == Mega_Starmie_ex:
                score += 50
                if fs.switch_to_starmie and o.index == fs.starmie_bench_idx:
                    score += 100
            elif card.id == Cinderace:
                score += 20
            elif card.id == Scorbunny:
                score += 5
            return score

        case SelectContext.TO_BENCH | SelectContext.TO_HAND:
            if not isinstance(card, Pokemon):
                return 10
            if card.id == Mega_Starmie_ex:
                return 100 if fs.field_counts[Mega_Starmie_ex] == 0 else 10
            if card.id == Cinderace:
                return 80
            if card.id == Staryu:
                return 60 if (
                    fs.field_counts[Staryu] + fs.field_counts[Mega_Starmie_ex] < 2
                ) else 20
            if card.id == Scorbunny:
                return 40 if (
                    fs.field_counts[Scorbunny] + fs.field_counts[Cinderace] < 2
                ) else 10
            return 10

        case SelectContext.DISCARD:
            card_id = card.id
            score = 5
            if card_id in (Mega_Starmie_ex, Cinderace):
                score = -50
            elif card_id == Ignition_Energy:
                score = 80   # ターン終了で消えるため惜しくない
            elif card_id == Wallys_Compassion:
                score = -100
            elif card_id in (Salvatore, Hilda):
                score = 20 if discard_hand_counts[card_id] >= 2 else -20
            elif card_id == Basic_Water_Energy:
                score = 30
            elif card_id in (Staryu, Scorbunny):
                score = 10
            if discard_hand_counts[card_id] >= 2:
                score += 100  # 重複カードは積極トラッシュ
            discard_hand_counts[card_id] -= 1
            return score

        case _:
            return 0


def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG エージェント（Cinderace + Mega Starmie ex）

    Returns:
        list[int]: 選択するオプションのインデックスリスト
    """
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        _load_deck()
        return my_deck

    _build_card_table()

    state    = obs.current
    select   = obs.select
    context  = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]
    prize_count = len(my_state.prize)

    fs = _collect_field_state(my_state, op_state)

    # DISCARD コンテキスト用に手札カウントのコピーを保持（段階的な選択を追跡）
    discard_hand_counts = defaultdict(int, fs.hand_counts)

    scores = []
    for o in select.option:
        match o.type:
            case OptionType.NUMBER:
                score = o.number
            case OptionType.YES:
                score = 1
            case OptionType.CARD:
                score = _score_card_option(
                    obs, o, context, my_index, fs, discard_hand_counts
                )
            case OptionType.PLAY:
                card  = get_card(obs, AreaType.HAND, o.index, my_index)
                score = _score_play(card.id, fs, prize_count)
            case OptionType.ATTACH:
                card    = get_card(obs, AreaType.HAND, o.index, my_index)
                pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
                score   = _score_attach(pokemon, o.inPlayArea, card.id, fs)
            case OptionType.EVOLVE:
                pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
                score   = 10000 + len(pokemon.energies)
            case OptionType.RETREAT:
                if fs.wally_in_hand and fs.starmie_active_damage > 0:
                    score = 3000  # Wally's Compassion ループ準備
                elif fs.switch_to_starmie:
                    score = 2000
                else:
                    score = -1
            case OptionType.ATTACK:
                score = _score_attack(o.attackId, fs)
            case _:
                score = 0
        scores.append(score)

    desc_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return desc_indices[:select.maxCount]
