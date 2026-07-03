import os
from collections import defaultdict
from dataclasses import dataclass

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, to_observation_class,
)

# ==================== カードID定数 ====================
Lunatone              = 675
Solrock               = 676
Riolu                 = 677
Mega_Lucario_ex       = 678
Premium_Power_Pro     = 1141
Fighting_Gong         = 1142
Poke_Pad              = 1152
Hero_Cape             = 1159
Boss_Orders           = 1182
Lillie_Determination  = 1227
Gravity_Mountain      = 1252
Basic_Fighting_Energy = 6

# ==================== デッキ安全性定数 ====================
DECK_SAFETY_THRESHOLD = 15  # 山札残数がこれ未満なら大量ドロー系を抑制

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築する"""
    global card_table
    if not card_table:
        card_table = {c.cardId: c for c in all_card_data()}
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


# ==================== ターン状態管理 ====================
@dataclass
class AttackPlan:
    attacker:     int  = -1
    target:       int  = -1
    attack_index: int  = -1
    remain_hp:    int  = -1
    energy:       bool = False


plan:         AttackPlan = AttackPlan()
pre_turn:     int        = 0
ability_used: bool       = False


def _reset_turn_state() -> None:
    """ターン開始時にグローバル攻撃プランとアビリティフラグをリセットする"""
    global plan, ability_used
    plan = AttackPlan()
    ability_used = False


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


def prize_count(pokemon: Pokemon) -> int:
    """KO 時に相手が取るプライズ枚数を返す（修飾カードを考慮）"""
    data = card_table[pokemon.id]
    count = 3 if data.megaEx else 2 if data.ex else 1
    for card in pokemon.energyCards:
        if card.id == 12:  # Legacy Energy
            count -= 1
    for card in pokemon.tools:
        if card.id == 1172 and "Lillie" in data.name:  # Lillie's Pearl
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
    id_ = pokemon.id
    if id_ in (144, 322, 323, 337):  # Squawkabilly ex, Noctowl, Fan Rotom, Archaludon ex
        score -= 200
    if id_ == 112 and len(pokemon.energies) >= 1:  # Munkidori
        score += 300
    score += pokemon.hp
    return score


def energy_score(pokemon: Pokemon, active: bool, attacker1: bool) -> int:
    """エネルギー付与先ポケモンの優先度スコアを返す"""
    energy_count = len(pokemon.energies)
    score = 8000
    if active:
        score += 10
    if pokemon.id == Lunatone:
        score -= 100
    elif pokemon.id == Solrock:
        if energy_count < 1:
            score += 20
        else:
            score -= 100
    elif pokemon.id in (Riolu, Mega_Lucario_ex):
        if pokemon.id == Mega_Lucario_ex:
            score += 1
        if energy_count < 2:
            score += 100
        if attacker1:
            score -= 50
    return score


# ==================== フィールド状態 ====================
def _collect_field_state(my_state):
    """バトル場・ベンチ・手札・捨て山のカード枚数とアタッカー準備状況を返す"""
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)
    attacker1 = False

    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id in (Riolu, Mega_Lucario_ex):
            if len(card.energies) >= 2:
                attacker1 = True

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    return field_counts, hand_counts, discard_counts, attacker1


def _get_stadium_id(state) -> int:
    """現在のスタジアムカード ID を返す（なければ 0）"""
    for card in state.stadium:
        return card.id
    return 0


def _analyze_main_options(obs: Observation, select, my_index: int) -> tuple[bool, bool, bool, bool]:
    """MAIN コンテキストのオプション一覧から行動フラグを抽出する"""
    can_switch         = False
    can_op_switch      = False
    can_use_mega_brave = False
    can_attack         = False

    for o in select.option:
        if o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            if card.id == Boss_Orders:
                can_op_switch = True
        elif o.type == OptionType.RETREAT:
            can_switch = True
        elif o.type == OptionType.ATTACK:
            can_attack = True
            if o.attackId == 983:  # Mega Brave
                can_use_mega_brave = True

    return can_switch, can_op_switch, can_use_mega_brave, can_attack


# ==================== 攻撃プラン計算 ====================
def calc_attack_plan(
    obs: Observation,
    my_state,
    op_state,
    state,
    field_counts:   defaultdict,
    hand_counts:    defaultdict,
    discard_counts: defaultdict,
    can_switch:         bool,
    can_op_switch:      bool,
    can_use_mega_brave: bool,
    can_attack:         bool,
    my_prize:           int,
) -> AttackPlan:
    """最適な攻撃プランを計算して返す"""
    new_plan   = AttackPlan()
    best_score = -1

    my_cards = [my_state.active[0]] + list(my_state.bench)
    op_cards = [op_state.active[0]] + list(op_state.bench)

    for i, my_pokemon in enumerate(my_cards):
        if my_pokemon is None:
            continue
        if i != 0 and not can_switch:
            break
        for a in range(2):
            energy_required = 0
            base_damage     = 0
            base_score      = 0

            if my_pokemon.id == Mega_Lucario_ex:
                if a == 0:
                    energy_required = 1
                    base_damage     = 130
                    base_score     += 60 * min(3, discard_counts[Basic_Fighting_Energy])
                else:
                    energy_required = 2
                    base_damage     = 270
                if a == 1 and my_prize in (2, 3):
                    base_score -= 500
            elif a == 1:
                break
            elif my_pokemon.id == Solrock:
                if field_counts[Lunatone] >= 1:
                    energy_required = 1
                    base_damage     = 70

            if base_damage <= 0:
                continue

            energy_count = len(my_pokemon.energies)
            more_energy  = False
            if a == 1 and i == 0 and energy_count >= 2 and not can_use_mega_brave:
                break
            if energy_count < energy_required:
                if hand_counts[Basic_Fighting_Energy] >= 1 and not state.energyAttached:
                    energy_count += 1
                    if energy_count < energy_required:
                        continue
                    else:
                        more_energy = True
                else:
                    continue

            for j, op_pokemon in enumerate(op_cards):
                if op_pokemon is None:
                    continue
                if j != 0 and not can_op_switch:
                    break
                damage = base_damage
                data   = card_table[op_pokemon.id]
                if data.weakness == EnergyType.FIGHTING:
                    damage *= 2
                elif data.resistance == EnergyType.FIGHTING:
                    damage -= 30

                prize = 0
                score = pokemon_score(op_pokemon)
                if op_pokemon.hp <= damage:
                    prize = prize_count(op_pokemon)
                else:
                    score *= damage / op_pokemon.hp
                score += base_score

                if len(op_state.prize) <= prize:
                    score = 50000

                if i == 0:
                    score += 220
                if j == 0:
                    score += 300
                score += energy_count

                if best_score < score:
                    best_score            = score
                    new_plan.attacker     = i
                    new_plan.target       = j
                    new_plan.attack_index = a
                    new_plan.remain_hp    = op_pokemon.hp - damage
                    new_plan.energy       = more_energy

    return new_plan


# ==================== スコアリング ====================
def _score_card_option(obs, o, context, my_index, state, my_state,
                       field_counts, hand_counts, discard_counts,
                       attacker1, current_plan, ability_used_flag) -> int:
    """OptionType.CARD のスコアをコンテキスト別に返す"""
    card = get_card(obs, o.area, o.index, o.playerIndex)
    if card is None:
        return 0
    energy_count = len(card.energies) if isinstance(card, Pokemon) else 0

    match context:
        case SelectContext.SWITCH | SelectContext.TO_ACTIVE:
            if o.playerIndex == my_index:
                score = energy_count * 2
                if o.index == current_plan.attacker - 1:
                    score += 100
                if card.id == Mega_Lucario_ex:
                    score += 8 if len(my_state.prize) in (2, 3) else 20
                elif card.id == Solrock:
                    score += 5
                elif card.id == Riolu:
                    score += 4
            else:
                score = 100 if o.index == current_plan.target - 1 else 0
            return score

        case SelectContext.SETUP_ACTIVE_POKEMON:
            if card.id == Solrock:
                return 4 if state.firstPlayer != my_index else 2
            if card.id == Riolu:
                return 3
            return 0

        case SelectContext.TO_HAND:
            score = 200 - hand_counts[card.id] * 100
            if card.id == Lunatone:
                score += -250 if field_counts[card.id] >= 1 else 60
            elif card.id == Solrock:
                score += -250 if field_counts[card.id] >= 1 else 50
            elif card.id == Riolu:
                total = field_counts[Riolu] + field_counts[Mega_Lucario_ex]
                score += -150 if total >= 2 else (-3 if total >= 1 else 40)
            elif card.id == Mega_Lucario_ex:
                score += 40 if field_counts[Riolu] >= 1 else -15
            elif card.id == Basic_Fighting_Energy:
                score += 30 if not ability_used_flag or not state.energyAttached else -1
            return score

        case SelectContext.ATTACH_FROM:
            return energy_score(card, o.area == AreaType.ACTIVE, attacker1)

        case _:
            return 0


def _score_play_option(obs, o, my_index, current_plan, can_attack,
                       state, my_state, hand_counts, field_counts, stadium_id) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]
    if data.cardType == CardType.POKEMON:
        if card.id in (Lunatone, Solrock):
            return -1 if field_counts[card.id] >= 1 else 20000
        if card.id == Riolu:
            return -1 if field_counts[Riolu] + field_counts[Mega_Lucario_ex] >= 2 else 20000
        return 20000
    # トレーナーズ
    if card.id == Premium_Power_Pro:
        if state.supporterPlayed and current_plan.remain_hp <= 0:
            return -1
        if not can_attack:
            if not state.supporterPlayed and hand_counts[Boss_Orders] == 0 and hand_counts[Lillie_Determination] == 0:
                return 3050
            return -1
        return 5000
    if card.id == Boss_Orders:
        return 3200 if current_plan.target >= 1 else -1
    if card.id == Lillie_Determination:
        return 3100 if my_state.deckCount >= DECK_SAFETY_THRESHOLD else -1
    if card.id == Gravity_Mountain:
        return -1 if stadium_id == 0 else 10000
    return 10000


def _score_attach_option(obs, o, my_index, current_plan, attacker1) -> int:
    """OptionType.ATTACH のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    if card.id == Hero_Cape:
        pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
        score = 7000
        if pokemon.id == Riolu:
            score += 100
        elif pokemon.id == Mega_Lucario_ex:
            score += 200
        return score
    pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
    score = energy_score(pokemon, o.inPlayArea == AreaType.ACTIVE, attacker1)
    if o.inPlayArea == AreaType.ACTIVE:
        if current_plan.attacker == 0 and current_plan.energy:
            score += 200
    else:
        if current_plan.attacker == 1 + o.inPlayIndex and current_plan.energy:
            score += 200
    return score


def _score_option(obs, o, context, my_index, state, my_state, op_state,
                  field_counts, hand_counts, discard_counts,
                  attacker1, current_plan, can_attack,
                  stadium_id, ability_used_flag) -> int:
    """1 つのオプションにヒューリスティックスコアを付ける"""
    match o.type:
        case OptionType.NUMBER:
            return o.number
        case OptionType.YES:
            return 1
        case OptionType.CARD:
            return _score_card_option(
                obs, o, context, my_index, state, my_state,
                field_counts, hand_counts, discard_counts,
                attacker1, current_plan, ability_used_flag,
            )
        case OptionType.PLAY:
            return _score_play_option(
                obs, o, my_index, current_plan, can_attack,
                state, my_state, hand_counts, field_counts, stadium_id,
            )
        case OptionType.ATTACH:
            return _score_attach_option(obs, o, my_index, current_plan, attacker1)
        case OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            return 9000 + len(pokemon.energies)
        case OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            return 1 if card.id == 1267 else 30000  # Lumiose City は低優先
        case OptionType.RETREAT:
            return 2000 if current_plan.attacker >= 1 else -1
        case OptionType.ATTACK:
            score = 1000
            if current_plan.attack_index == 1:
                score += 100 if o.attackId == 983 else 0  # Mega Brave 優先
            else:
                score += 0 if o.attackId == 983 else 100
            return score
        case _:
            return 0


# ==================== メインエージェント ====================
def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG エージェント。

    Returns:
        list[int]: 選択するオプションのインデックスリスト
    """
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        _load_deck()
        return my_deck

    _build_card_table()

    global plan, pre_turn, ability_used

    state    = obs.current
    select   = obs.select
    context  = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]
    my_prize = len(my_state.prize)

    if pre_turn != state.turn:
        pre_turn = state.turn
        _reset_turn_state()

    field_counts, hand_counts, discard_counts, attacker1 = _collect_field_state(my_state)
    stadium_id = _get_stadium_id(state)

    can_switch = can_op_switch = can_use_mega_brave = can_attack = False
    if context == SelectContext.MAIN and state.turn >= 2:
        can_switch, can_op_switch, can_use_mega_brave, can_attack = _analyze_main_options(obs, select, my_index)
        plan = calc_attack_plan(
            obs, my_state, op_state, state,
            field_counts, hand_counts, discard_counts,
            can_switch, can_op_switch, can_use_mega_brave, can_attack,
            my_prize,
        )

    scores = [
        _score_option(
            obs, o, context, my_index, state, my_state, op_state,
            field_counts, hand_counts, discard_counts,
            attacker1, plan, can_attack,
            stadium_id, ability_used,
        )
        for o in select.option
    ]

    desc_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    if context == SelectContext.MAIN:
        o = select.option[desc_indices[0]]
        if o.type == OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if card.id == Lunatone:
                ability_used = True

    return desc_indices[:select.maxCount]
