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


# ==================== スコアリング ====================
def _score_play(card_id: int, fs: FieldState, prize_count: int) -> int:
    """PLAY コンテキスト：手札からカードを使う際のスコア"""
    if card_id == Rare_Candy:
        has_impidimp     = fs.field_counts[Impidimp] >= 1
        grimmsnarl_ready = fs.hand_counts[Grimmsnarl_ex] >= 1
        return 9000 if (has_impidimp and grimmsnarl_ready) else -1
    if card_id == Buddy_Buddy_Poffin:
        needs_bench = fs.impidimp_bench_idx == -1 or fs.munkidori_bench_idx == -1
        return 8000 if needs_bench else 2000
    if card_id == Dawn:
        line_in_hand = (
            fs.hand_counts[Impidimp] >= 1
            and fs.hand_counts[Morgrem] >= 1
            and fs.hand_counts[Grimmsnarl_ex] >= 1
        )
        return 2500 if line_in_hand else 7000
    if card_id == Lillie_Determination:
        return 5000 if prize_count == 6 else 3500
    if card_id == Xerosics_Machinations:
        return 3000
    if card_id == Poke_Pad:
        return 4000
    if card_id == Night_Stretcher:
        return 2000
    return 1000


def _score_attach(pokemon: "Pokemon", area: AreaType, card_id: int, fs: FieldState) -> int:
    """ATTACH コンテキスト：エネルギー/ツールの付与先スコア"""
    energy_count = len(pokemon.energies)
    if card_id == Heros_Cape:
        return 8500 if pokemon.id == Grimmsnarl_ex else -1
    if card_id == Basic_D_Energy:
        if pokemon.id == Grimmsnarl_ex:
            return 9000 - energy_count * 1000
        if pokemon.id == Morpeko:
            return 4000
        return -1
    return 3000


def _score_attack(attack_id: int, fs: FieldState) -> int:
    """ATTACK コンテキスト：ワザ選択スコア"""
    if attack_id == Shadow_Bullet_ID:
        return 2000
    if attack_id == Spiky_Wheel_ID:
        return 1500
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
            if card.id == Impidimp:
                return 100
            if card.id == Morpeko:
                return 50
            return 10

        case SelectContext.SWITCH | SelectContext.TO_ACTIVE:
            if o.playerIndex != my_index or not isinstance(card, Pokemon):
                return 0
            score = len(card.energies) * 2
            if card.id == Grimmsnarl_ex:
                score += 100
            elif card.id == Morpeko:
                score += 30
            return score

        case SelectContext.TO_BENCH | SelectContext.TO_HAND:
            if not isinstance(card, Pokemon):
                return 10
            if card.id == Grimmsnarl_ex:
                return 100 if fs.field_counts[Grimmsnarl_ex] == 0 else 10
            if card.id == Impidimp:
                return 60 if fs.field_counts[Impidimp] < 2 else 20
            if card.id == Munkidori:
                return 40 if fs.munkidori_bench_idx == -1 else 10
            return 10

        case SelectContext.DAMAGE_COUNTER:
            # Shadow Bulletのベンチ30ダメ対象：最もKOに近い（HPが低い）相手ベンチを狙う
            if not isinstance(card, Pokemon):
                return 0
            return 100000 - card.hp

        case SelectContext.DISCARD:
            card_id = card.id
            score = 5
            if card_id in (Grimmsnarl_ex, Impidimp, Morgrem):
                score = -50
            elif card_id == Basic_D_Energy:
                score = 30
            if discard_hand_counts[card_id] >= 2:
                score += 100
            discard_hand_counts[card_id] -= 1
            return score

        case _:
            return 0


def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG エージェント（マリィのグリムスナールex）

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
            case OptionType.ABILITY:
                card = get_card(obs, o.area, o.index, my_index)
                score = 500 if card.id == Munkidori else 300
            case OptionType.RETREAT:
                # Grimmsnarl exが瀕死（想定される大技の一撃=180ダメ以下しか耐えられない）なら逃げる
                if fs.grimmsnarl_active and fs.my_active_hp <= 180:
                    score = 3000
                else:
                    score = -1
            case OptionType.ATTACK:
                score = _score_attack(o.attackId, fs)
            case _:
                score = 0
        scores.append(score)

    desc_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return desc_indices[:select.maxCount]
