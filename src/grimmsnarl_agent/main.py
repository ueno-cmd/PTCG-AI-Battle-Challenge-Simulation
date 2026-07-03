import os
import random
from collections import defaultdict
from dataclasses import dataclass

from cg.api import (
    AreaType, CardType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, to_observation_class,
)

# ==================== カードID定数 ====================
# 20260702改修：Morpeko/Dudunsparce/Dunsparce/Dawn/Xerosic's Machinations/
# Energy Recycler/Hero's Capeはデッキから削除済みのため定数ごと削除。
# 代わりにTeam Rocket's Petrelを追加（docs/superpowers/specs/2026-07-02-grimmsnarl-deck-revision-design.md）
# フェーズB改修（2026-07-03）：Budew/Tatsugiri/Psyduckはデッキから削除済みのため定数ごと削除。
# 代わりにFezandipiti_exを追加（docs/superpowers/specs/2026-07-03-grimmsnarl-deck-revision-phase-b-design.md）
Impidimp       = 646
Morgrem        = 647
Grimmsnarl_ex  = 648
Munkidori      = 112
Froslass       = 104
Shaymin        = 343
Yveltal        = 689
Fezandipiti_ex = 140

# 特性が「場にいれば無条件で発動」する専用要員。バトル場に出す前提のカードではないため、
# SWITCH/TO_ACTIVEでは他に選択肢がある限り選ばれないよう明確に減点する。
# Munkidoriは特性発動にエネルギー要求があり攻撃も可能なため対象外。
# Fezandipiti_exは210HPの実戦アタッカーであり特性もバトル場条件なしのため対象外。
SUPPORT_ONLY_IDS = {Froslass, Shaymin}

Rare_Candy             = 1079
Buddy_Buddy_Poffin     = 1086
Lillie_Determination   = 1227
Poke_Pad               = 1152
Night_Stretcher        = 1097
Spikemuth_Gym          = 1259
Boss_Orders            = 1182
Team_Rocket_Petrel     = 1219

Basic_D_Energy = 7

# ==================== ボスの指令：即使用/温存の判断用定数 ====================
SHADOW_BULLET_DAMAGE = 180  # Shadow Bulletの与ダメージ（_score_attackと共通の閾値）
EPSILON              = 0.28  # 温存判断時に探索的先出しをする確率
_rng                  = random.Random()  # 本番用の実乱数。テストではスタブを注入する

# ==================== アタックID（_build_card_table で設定）====================
Shadow_Bullet_ID: int = 0

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築し、攻撃IDも設定する"""
    global card_table, Shadow_Bullet_ID
    if not card_table:
        card_table       = {c.cardId: c for c in all_card_data()}
        grimmsnarl_data  = card_table[Grimmsnarl_ex]
        Shadow_Bullet_ID = grimmsnarl_data.attacks[0]  # Shadow Bullet
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
def _score_play(
    card_id: int,
    fs: FieldState,
    prize_count: int,
    rng: "random.Random | None" = None,
) -> int:
    """PLAY コンテキスト：手札からカードを使う際のスコア"""
    if card_id == Rare_Candy:
        has_impidimp     = fs.field_counts[Impidimp] >= 1
        grimmsnarl_ready = fs.hand_counts[Grimmsnarl_ex] >= 1
        return 9000 if (has_impidimp and grimmsnarl_ready) else -1
    if card_id == Buddy_Buddy_Poffin:
        needs_bench = fs.impidimp_bench_idx == -1 or fs.munkidori_bench_idx == -1
        return 8000 if needs_bench else 2000
    if card_id == Team_Rocket_Petrel:
        # Dawnの後継：進化ライン（特にRare Candy）を狙ってサーチする役割
        return 7000
    if card_id == Lillie_Determination:
        return 5000 if prize_count == 6 else 3500
    if card_id == Poke_Pad:
        return 4000
    if card_id == Night_Stretcher:
        return 2000
    if card_id == Boss_Orders:
        if not fs.op_bench_hp:
            return -1  # 対象不在なら温存
        has_ko_target = any(hp <= SHADOW_BULLET_DAMAGE for hp in fs.op_bench_hp)
        if has_ko_target:
            return 8800  # 即使用（KO確定）
        active_rng = rng if rng is not None else _rng
        if active_rng.random() < EPSILON:
            return 6000  # 探索的先出し（KO確定ではないがキーポケモンを引きずり出す）
        return -1  # 温存
    return 1000


def _score_attach(pokemon: "Pokemon", area: AreaType, card_id: int, fs: FieldState) -> int:
    """ATTACH コンテキスト：エネルギー/ツールの付与先スコア"""
    energy_count = len(pokemon.energies)
    if card_id == Basic_D_Energy:
        if pokemon.id == Grimmsnarl_ex:
            return 9000 - energy_count * 1000
        if pokemon.id == Fezandipiti_ex and energy_count < 3 and fs.grimmsnarl_energy_count >= 2:
            # クルーエルアローは悪悪+無色1=3エネで発動。グリムスナールexが
            # シャドーバレット分（2エネ）を確保済みの場合のみ余剰分を分配する
            return 5000 - energy_count * 500
        if pokemon.id == Munkidori and energy_count == 0 and fs.grimmsnarl_energy_count >= 2:
            # アドレナブレインはエネルギー1枚で発動するため、グリムスナールexが
            # シャドーバレット分（2エネ）を確保済みの場合のみ余剰分を分配する
            return 4000
        return -1
    return 3000


def _score_attack(attack_id: int, fs: FieldState) -> int:
    """ATTACK コンテキスト：ワザ選択スコア"""
    if attack_id == Shadow_Bullet_ID:
        # 相手バトルポケモンのHPがSHADOW_BULLET_DAMAGE以下ならShadow Bulletで確実にKOできる
        # （きぜつ確定）ので、RETREATの3000点より高くして撤退より攻撃を優先する
        return 5000 if fs.op_active_hp <= SHADOW_BULLET_DAMAGE else 2000
    return 1000


def _score_own_switch_target(card: "Pokemon") -> int:
    """自分のポケモンをバトル場に出す際の優先スコア（SWITCH/TO_ACTIVE共通）

    特性専用ポケモン（SUPPORT_ONLY_IDS）は場にいるだけで効果を発揮し攻撃力も乏しいため、
    他に選択肢がある限り選ばれないよう常に負のスコア域に収める。
    それ以外は残りHP（生存力）とエネルギー装着数を基準に評価する。
    """
    if card.id == Grimmsnarl_ex:
        return 10000 + len(card.energies) * 2
    if card.id in SUPPORT_ONLY_IDS:
        return -1000 + card.hp
    return card.hp + len(card.energies) * 2


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
            return 10

        case SelectContext.SWITCH:
            if o.playerIndex != my_index or not isinstance(card, Pokemon):
                return 0
            return _score_own_switch_target(card)

        case SelectContext.TO_ACTIVE:
            if not isinstance(card, Pokemon):
                return 0
            if o.playerIndex != my_index:
                # ボスの指令等で相手ベンチを強制的にバトル場に出す場合：
                # 最もHPが低い（KOに近い）ポケモンを狙う
                return 100000 - card.hp
            return _score_own_switch_target(card)

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
                if card is None:
                    score = 0
                else:
                    score = _score_play(card.id, fs, prize_count, _rng)
            case OptionType.ATTACH:
                card    = get_card(obs, AreaType.HAND, o.index, my_index)
                pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
                if card is None or pokemon is None:
                    score = 0
                else:
                    score = _score_attach(pokemon, o.inPlayArea, card.id, fs)
            case OptionType.EVOLVE:
                pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
                score   = 10000 + len(pokemon.energies)
            case OptionType.ABILITY:
                card = get_card(obs, o.area, o.index, my_index)
                if card is None:
                    score = 0
                else:
                    # アビリティは無償（ターンを消費しない）ため、非確定KOの攻撃（2000点）より
                    # 優先して毎ターン使用する。ただしEVOLVE（10000+）や確定KO攻撃（5000）は上回らない
                    score = 2500 if card.id == Munkidori else 1200
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
