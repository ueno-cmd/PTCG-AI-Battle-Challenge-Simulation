import os
import random
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass

from cg.api import AreaType, CardType, Log, LogType, Observation, SelectContext, OptionType, Card, Pokemon, State, all_card_data, to_observation_class
from dragapult_agent.constants import (
    Dreepy, Drakloak, Dragapult_ex, Fezandipiti_ex, Budew,
    Meowth_ex, Rare_Candy, Unfair_Stamp, Buddy_Buddy_Poffin, Night_Stretcher,
    Ultra_Ball, Poke_Pad, Boss_Orders, Crispin,
    Lillie_Determination,
    Basic_Fire_Energy, Basic_Psychic_Energy,
    Munkidori, Duskull, Dusclops, Dusknoir, Moltres, Yveltal,
)

"""
Dragapult ex Deck
Advanced Level
This deck focuses on setting up multiple knockouts to take at least three Prize cards in a single turn with its Phantom Dive attack.
"""

my_deck: list[int] = []


def _load_deck() -> list[int]:
    """deck.csvを初回のみ読み込む（importタイミングでのファイルI/Oを避けるための遅延初期化）"""
    global my_deck
    if my_deck:
        return my_deck
    file_path = "deck.csv"
    if not os.path.exists(file_path):
        file_path = "/kaggle_simulations/agent/" + file_path
    with open(file_path, "r") as file:
        csv = file.read().split("\n")
    my_deck = [int(csv[i]) for i in range(60)]
    return my_deck
    
card_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築する（importタイミングでのcg.api呼び出しを避けるための遅延初期化）"""
    global card_table
    if not card_table:
        card_table = {c.cardId: c for c in all_card_data()}
    return card_table


def _attach_score(
    attach_id: int,
    pokemon: Pokemon,
    active: bool,
    *,
    card_table: dict,
    can_switch: bool,
    bench_attacker: bool,
    no_more_dex: bool,
    field_counts: dict,
    my_asleep: bool,
    my_paralyzed: bool,
) -> int:
    energy_count = len(pokemon.energies)
    if card_table[attach_id].cardType == CardType.TOOL:
        # Attach tool
        score = 60000
        if active:
            score += 1000
        return score

    # Attach energy
    if pokemon.id == Budew:
        return -1
    elif pokemon.id == Meowth_ex or pokemon.id == Fezandipiti_ex:
        if active and not can_switch and not my_asleep and not my_paralyzed:
            if bench_attacker or field_counts[Budew] >= 1:
                return 22000
            else:
                return 18000
        else:
            return -1
    if active and can_main_attack:
        return -1
    score = 20000
    if energy_count >= 2:
        if active and not can_switch and not my_asleep and not my_paralyzed:
            score += 200
        else:
            return -1
    elif energy_count == 1:
        if attach_id == pokemon.energyCards[0].id:
            return -1
        if pokemon.id == Dragapult_ex:
            score += 250
        elif pokemon.id == Dreepy:
            score -= 150
        else:
            # energy_count==0の同種族への新規着手(+50)より不利にしない。
            # 元々ここが-200だったため、1エネルギー投資済みの控え(例: Drakloak)への
            # 追加装着が常に新規着手より低評価となり、2エネルギー(攻撃可能)への到達を
            # 遅らせる非対称バグがあった（2026-07-22、実ログ20戦・77件中4件の矛盾で発覚。
            # 詳細: docs/analyses/20260722-dragapult-attach-scoring-verified.md）
            score += 50
        if active:
            score += 200
    else:  # energy_count == 0
        if active:
            if bench_attacker:
                score += 400
        else:
            if pokemon.id == Dragapult_ex:
                score += 150
            elif pokemon.id == Dreepy:
                score += 100
            else:
                score += 50
            if bench_attacker:
                score -= 200
    if no_more_dex and (pokemon.id == Dreepy or pokemon.id == Drakloak):
        score -= 500
    return score

UNNECESSARY = -10000000
BOSS_ORDERS_EXPLORE_EPSILON = 0.28  # ルカリオexのEPSILON（src/lucario_agent/combat.py:13）と同値を初期値として踏襲
_dragapult_rng = random.Random()  # 本番用の実乱数。テストでは_boss_orders_scoreを直接呼び乱数を注入する


def _boss_orders_score(has_pull_target: bool, explore_roll: float, epsilon: float) -> int:
    """ボスの指令のスコアを返す。
    has_pull_target: 現在のベスト攻撃プランがベンチの相手を狙っているか（plan_a.attack > 0）
    explore_roll: 探索的先出し判定用の乱数値（0.0以上1.0未満）
    epsilon: 探索的先出しを行う確率の閾値
    """
    if has_pull_target:
        return 60000  # ベストプランがベンチ狙いを示している：即使用
    if explore_roll < epsilon:
        return 30000  # 確定的な引き剥がし先がなくても、一定確率で探索的に先出しする
    return 0  # 温存


def _own_switch_target_score(card_id: int, energy_count: int, bench_attacker: bool) -> int:
    """SelectContext.SWITCH/TO_ACTIVE/SETUP_ACTIVE_POKEMON共通で、
    自分のポケモンをアクティブへ送る候補への優先度スコアを返す
    （hp・energy_count*1000の共通加点は呼び出し側で加算する）。
    強制入場時のみスボミーを特別優先していた分岐は、実戦で効果が
    機能している確証がなく、本命アタッカーを出し損ねるリスクの方が
    明確なため削除した（2026-07-23、docs/analyses/20260723-dragapult-post-attach-fix-20-games.md参照）。"""
    if card_id == Dreepy:
        return 10000
    elif card_id == Drakloak:
        return 20000 if energy_count >= 1 else -10000
    elif card_id == Dragapult_ex:
        return 50000
    elif card_id == Budew:
        return 30000 if not bench_attacker else 0
    elif card_id == Fezandipiti_ex:
        return -1000
    elif card_id == Meowth_ex:
        return -2000
    return 0


def _evolve_score(
    pre_evolution_id: int, energy_count: int, dragapult_ex_field_count: int,
    opponent_prize_count: int,
) -> int:
    """OptionType.EVOLVEのスコアを返す（進化元ポケモンのエネルギー数は
    呼び出し側で加算済みの前提ではなく、この関数内で加算する）。
    既存のDreepy→Drakloak・Drakloak→Dragapult_exの優先度は維持しつつ、
    新規のDuskull(ヨマワル)→Dusclops(サマヨール)・
    Dusclops(サマヨール)→Dusknoir(ヨノワール)の優先度を追加する。
    ドラパルトライン優先の設計方針（設計書参照）に基づき、ヨマワル系統の
    加点はドラパルトライン（Dreepy=30000、フォールバックのDrakloak=70000）
    よりやや低く設定している"""
    score = energy_count
    if pre_evolution_id == Dreepy:
        return score + 30000
    elif pre_evolution_id == Duskull:
        return score + 25000
    elif pre_evolution_id == Dusclops:
        return score + 60000
    elif (dragapult_ex_field_count >= 2
          or (dragapult_ex_field_count == 1 and opponent_prize_count <= 2)):
        return -1
    else:
        return score + 70000


def _fetch_from_discard_score(discard_count: int, bench_space: int) -> int:
    """ヨマワルの特性「むかえにいく」（トラッシュから最大3枚のヨマワルをベンチに戻す）
    のスコアを返す。デッキ内はヨマワル2・サマヨール1・ヨノワール1の計4枚のみのため、
    主目的はハイパーボール等で手札から直接トラッシュされたヨマワルの回収。
    トラッシュに回収対象がなければ、または自分のベンチに空きがなければ
    使う意味がない（docs/superpowers/specs/2026-07-23-dragapult-crustle-counter-deck-design.md）"""
    if discard_count <= 0 or bench_space <= 0:
        return -1
    return 42000


def _cursed_bomb_score(opponent_active_id: int | None) -> int:
    """ヨノワール／サマヨールの特性「カースドボム」
    （自分を気絶させ、相手ポケモン1匹にダメカンを直接配置）のスコアを返す。
    「ダメカンの直接配置」は「攻撃ダメージ」ではないため、イワパレスのような
    no_damage_dex()該当の特性ブロックを迂回できる。自爆前提のため、
    相手アクティブが直接攻撃を完全ブロックする相手の時のみ発動する
    （docs/superpowers/specs/2026-07-23-dragapult-crustle-counter-deck-design.md）"""
    if opponent_active_id is not None and no_damage_dex(opponent_active_id):
        return 90000
    return -1


def _adrena_brain_score(opponent_active_id: int | None) -> int:
    """マシマシラの特性「アドレナブレイン」
    （悪エネルギー装着時、自分の場のポケモン1匹のダメカン最大3個を
    相手のポケモン1匹に移し替え。自爆なし・毎ターン使用可）のスコアを返す。
    カースドボムと同じ理由（ダメカンの直接配置は攻撃ダメージではないため）で
    イワパレスの特性を迂回できる。発動条件のみを実装し、対象選択（どのポケモンの
    ダメカンを何個移すか）は既存の汎用ロジックに委ねる（次回以降のログ検証待ち）"""
    if opponent_active_id is not None and no_damage_dex(opponent_active_id):
        return 85000
    return -1


def _crispin_score(
    *,
    deck_counts: dict,
    can_main_attack: bool,
    bench_attacker: bool,
    field_counts: dict,
) -> int:
    """アカマツ(Crispin)のスコアを返す。
    「自分の山札から、それぞれちがうタイプの基本エネルギーを2枚まで選び、
    1枚を手札に、残りを自分のポケモンに付ける」効果のため、炎・超いずれかの
    基本エネルギーが山札に0枚だと2種を探せず効果が弱まる。修正前はこの
    低評価分岐がelifではなく独立したifだったため、直後のif/elseで無条件に
    上書きされ常に死んでいた（2026-07-23発見、docs/analyses/20260723-dragapult-main-if-else-audit.md参照）。
    """
    if deck_counts[Basic_Fire_Energy] == 0 or deck_counts[Basic_Psychic_Energy] == 0:
        return 10
    if not can_main_attack and not bench_attacker and field_counts[Dragapult_ex] >= 1:
        return 55000
    return 25000


# ==================== PLAYスコアリングのポリシー登録制（トレーナーズカードのみ） ====================
@dataclass
class PlayTrainerCardContext:
    """OptionType.PLAY のトレーナーズカードのスコアリングに必要な情報をまとめる。
    ポケモンカード分岐(Dreepy/Fezandipiti_ex/Budew/Meowth_ex)はagent()側に
    残すため含まない"""
    card_id: int
    card_score: int          # hand_scores[o.index]
    state: State
    stadium_id: int
    deck_counts: defaultdict
    negative_hand_count: int
    no_draw: bool
    use_support: int
    no_more_dex: bool


class TrainerCardPolicy(ABC):
    """1枚のトレーナーズカード（サポート/グッズ/スタジアム）のPLAY判断を表す"""
    @abstractmethod
    def play_score(self, ctx: PlayTrainerCardContext) -> int: ...


class FixedScorePolicy(TrainerCardPolicy):
    """固定スコアのみを返すカード用"""
    def __init__(self, score: int):
        self._score = score

    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        return self._score


class SupporterSelectedPolicy(TrainerCardPolicy):
    """このターンの最強サポート(use_support)と一致すれば固定スコア、そうでなければ-1。
    no_draw_gate=Trueの場合、山札残り僅少(no_draw)ならuse_supportとの一致に関わらず-1にする
    （現行のelif no_draw連鎖で、この分岐より後ろに書かれているカードだけが受ける
    暗黙の副作用を明示化したもの。Boss_Orders/Lillie_Determinationはno_drawの影響を
    受けないため no_draw_gate=False のまま使う）"""
    def __init__(self, score: int, *, no_draw_gate: bool = False):
        self._score = score
        self._no_draw_gate = no_draw_gate

    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        if self._no_draw_gate and ctx.no_draw:
            return -1
        return self._score if ctx.card_id == ctx.use_support else -1


class RareCandyPolicy(TrainerCardPolicy):
    """no_more_dex(プライズ枚数から見てドラパルトexの数が既に十分)ならもう不要"""
    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        return -1 if ctx.no_more_dex else 75000


class NightStretcherPolicy(TrainerCardPolicy):
    """手札評価(card_score)が閾値以上(=有用なカードを回収できる)場合のみ使用"""
    CARD_SCORE_THRESHOLD = 18000

    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        return 42000 if ctx.card_score >= self.CARD_SCORE_THRESHOLD else -1


class BuddyBuddyPoffinPolicy(TrainerCardPolicy):
    """山札にドロディー(Dreepy)が残っている場合のみ使用。山札残り僅少(no_draw)なら使わない"""
    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        if ctx.no_draw:
            return -1
        return 46000 if ctx.deck_counts[Dreepy] > 0 else -1


class UltraBallPolicy(TrainerCardPolicy):
    """手札に低評価カードが2枚以上ある(=捨てても惜しくない)場合のみ使用。
    山札残り僅少(no_draw)なら使わない"""
    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        if ctx.no_draw:
            return -1
        return 44000 if ctx.negative_hand_count >= 2 else -1


class PokePadPolicy(TrainerCardPolicy):
    """山札にドロディー(Dreepy)かイダテヌキ(Drakloak)が残っている場合のみ使用。
    山札残り僅少(no_draw)なら使わない"""
    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        if ctx.no_draw:
            return -1
        return 45000 if ctx.deck_counts[Dreepy] + ctx.deck_counts[Drakloak] > 0 else -1


TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Unfair_Stamp: FixedScorePolicy(15000),
    Boss_Orders: SupporterSelectedPolicy(35000),
    Lillie_Determination: SupporterSelectedPolicy(14000),
    Rare_Candy: RareCandyPolicy(),
    Night_Stretcher: NightStretcherPolicy(),
    Buddy_Buddy_Poffin: BuddyBuddyPoffinPolicy(),
    Ultra_Ball: UltraBallPolicy(),
    Poke_Pad: PokePadPolicy(),
    Crispin: SupporterSelectedPolicy(35000, no_draw_gate=True),
}


def _score_play_trainer_card(card_id: int, ctx: PlayTrainerCardContext) -> int:
    """OptionType.PLAY のトレーナーズカード分岐のスコアを返す。
    未登録カードは現行のif/elif連鎖がどれにも一致しない場合と同じく0を返す。
    注意：旧if/elif連鎖では`no_draw`時に未一致カードは-1になっていたが
    （カードID指定の無い`elif no_draw:`が連鎖の途中にあったため）、この
    フォールバックはno_drawの値に関わらず常に0を返す。現行デッキの
    トレーナーズカードは全て登録済みのためこの経路には到達しないが、
    今後カードを追加する際はno_drawとの組み合わせを見落とさないこと"""
    policy = TRAINER_CARD_POLICIES.get(card_id)
    return policy.play_score(ctx) if policy is not None else 0


class AttackPlan:
    attack: int = 0
    counter: list[int] = []

can_switch = False
can_attack = False
can_main_attack = False
can_energy_attach = False
use_support = 0  # The Supporter card planned for use.
bench_attacker = False  # Whether there is a Benched Pokémon that is ready to attack
pre_turn_log: list[Log] = []
current_turn_log: list[Log] = []

prize: list[int] = []
card_counts: defaultdict[int, int] = defaultdict(int)
serial_set: set[int] = set()
plan_a = AttackPlan()
plan_b = AttackPlan()


def no_damage_dex(id: int) -> bool:
    """Checks if the defending Pokémon possesses innate immunities preventing Dragapult ex from hitting it."""
    # Drednaw, Milotic ex, Sylveon, Crustle
    return id == 158 or id == 207 or id == 330 or id == 345


def no_damage_counter(pokemon: Pokemon) -> bool:
    """Checks if a target prevents placement of Phantom Dive's 6 bench damage counters (via abilities/Energy)."""
    # Poltchageist, Empoleon ex, Skeledirge, Milotic ex, Misty's Magikarp, Antique Cover Fossil
    if pokemon.id == 28 or pokemon.id == 199 or pokemon.id == 203 or pokemon.id == 207 or pokemon.id == 362 or pokemon.id == 1136:
        return True
    for card in pokemon.energyCards:
        # Mist Energy, Rock Fighting Energy
        if card.id == 11 or card.id == 20:
            return True
    return False


def prize_count(pokemon: Pokemon, is_attack_damage: bool) -> int:
    """Calculates how many Prize cards a Pokémon yields upon being Knocked Out, factoring in modifiers."""
    data = card_table[pokemon.id]
    count = 3 if data.megaEx else 2 if data.ex else 1
    if is_attack_damage:
        for card in pokemon.energyCards:
            if card.id == 12:  # Legacy Energy
                count -= 1
        for card in pokemon.tools:
            if card.id == 1172 and "Lillie" in data.name:  # Lillie’s Pearl
                count -= 1
    return max(0, count)


def pokemon_score(pokemon: Pokemon, is_attack_damage: bool) -> int:
    """Heuristically evaluates the tactical worth of targeting a specific Pokémon on the opponent's field."""
    data = card_table[pokemon.id]
    score = prize_count(pokemon, is_attack_damage) * 1000
    score += len(pokemon.energies) * 150
    score += len(pokemon.tools) * 100
    if data.stage2:
        score += 250
    elif data.stage1:
        score += 130
    
    id = pokemon.id
    # Squawkabilly ex, Noctowl, Fan Rotom, Archaludon ex
    if id == 144 or id == 322 or id == 323 or id == 337:
        score -= 200
    if id == 112 and len(pokemon.energies) >= 1:  # Munkidori
        score += 300
    score += pokemon.hp
    return score


def add_card_count(card: Card | Pokemon | None, my_index: int):
    if card == None:
        return
    if isinstance(card, Pokemon) or card.playerIndex == my_index:
        if card.serial not in serial_set:
            card_counts[card.id] -= 1
            serial_set.add(card.serial)
    if isinstance(card, Pokemon):
        for c in card.energyCards:
            add_card_count(c, my_index)
        for c in card.tools:
            add_card_count(c, my_index)
        for c in card.preEvolution:
            add_card_count(c, my_index)

def set_card_counts(obs: Observation, my_index: int):
    _load_deck()
    _build_card_table()
    card_counts.clear()
    serial_set.clear()
    for id in my_deck:
        card_counts[id] += 1
    
    state = obs.current
    my_state = state.players[my_index]
    for card in my_state.hand:
        add_card_count(card, my_index)
    for card in my_state.discard:
        add_card_count(card, my_index)
    for card in my_state.bench:
        add_card_count(card, my_index)
    for card in my_state.active:
        add_card_count(card, my_index)
    for card in state.stadium:
        add_card_count(card, my_index)
    if state.looking != None:
        for card in state.looking:
            add_card_count(card, my_index)
    add_card_count(obs.select.effect, my_index)

    
def get_card(obs: Observation, area: AreaType, index: int, player_index: int) -> Pokemon | Card | None:
    """Helper function to safely extract a Card or Pokemon object from specific zones."""
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

def main_option_proc(obs: Observation, damage: int):
    state = obs.current
    select = obs.select
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]

    global can_switch
    global can_attack
    global can_main_attack
    global can_energy_attach

    can_switch = False
    can_attack = False
    can_main_attack = False
    can_energy_attach = False
    for o in select.option:
        if o.type == OptionType.RETREAT:
            can_switch = True
        elif o.type == OptionType.ATTACK:
            can_attack = True
            if o.attackId == 154:  # Phantom Dive
                can_main_attack = True
    
    plan_a.attack = -1
    plan_b.attack = -1
    if not can_main_attack and not (bench_attacker and can_switch):
        return
    
    cards = [op_state.active[0]]
    for pokemon in op_state.bench:
        cards.append(pokemon)
    counter_indices = []
    ci = []
    ci.append(0)
    remain_damage = 60
    while ci:
        index = ci[-1]
        hp = cards[index].hp
        if remain_damage >= hp:
            counter_indices.append(ci.copy())
            if index < len(cards) - 1:
                remain_damage -= hp
                ci.append(index + 1)
                continue
        if index == len(cards) - 1:
            ci.pop()
            if ci:
                remain_damage += cards[ci[-1]].hp
        if ci:
            ci[-1] += 1
    counter_indices.append([])

    remain_prize = len(my_state.prize)
    plan_score = 0
    for i, pokemon in enumerate(cards):
        base_prize_count = 0
        base_score = pokemon_score(pokemon, True)
        active_damage = 0 if no_damage_dex(pokemon.id) else damage
        if pokemon.hp <= active_damage:
            base_prize_count += prize_count(pokemon, True)
        else:
            base_score *= active_damage / pokemon.hp
        ci = []
        max_score = base_score
        if remain_prize <= base_prize_count:
            max_score = 50000
        else:
            for indices in counter_indices:
                if i in indices:
                    continue
                prize = base_prize_count
                score = base_score
                for index in indices:
                    prize += prize_count(cards[index], False)
                    score += pokemon_score(cards[index], False)
                if remain_prize <= prize:
                    score = 50000
                else:
                    if prize >= 2:
                        if remain_prize <= 4:
                            score -= 1200
                    elif prize == 1:
                        score -= 300
                    else:
                        score += 1200
                if max_score < score:
                    max_score = score
                    ci = indices
        if plan_score < max_score:
            plan_score = max_score
            plan_a.attack = i
            plan_a.counter = ci
        if i == 0:
            plan_b.attack = plan_a.attack
            plan_b.counter = plan_a.counter

def agent(obs_dict: dict) -> list[int]:
    """Main Agent Function.

    Each element in the returned list must be >= 0 and < len(obs.select.option).
    The list length must be between obs.select.minCount and obs.select.maxCount (inclusive), with no duplicate elements.
    
    Returns:
        list[int]: A list of option index.
    """
    obs = to_observation_class(obs_dict)
    if obs.select == None:
        # In the initial selection, the obs.select is None, and it is necessary to return the deck.
        # The deck is a list of 60 card IDs.
        # The deck must comply with the Pokémon Trading Card Game rules.
        _load_deck()
        return my_deck

    global pre_turn_log
    global current_turn_log

    state = obs.current
    select = obs.select
    context = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]
            
    if state.turn == 0:
        prize.clear()
        pre_turn_log.clear()
        current_turn_log.clear()
    else:
        for log in obs.logs:
            current_turn_log.append(log)
            if log.type == LogType.TURN_END:
                pre_turn_log = current_turn_log
                current_turn_log = []

    pre_ko = False
    no_item = False
    for log in pre_turn_log:
        if log.type == LogType.ATTACK:
            if log.attackId == 323:  # Itchy Pollen
                no_item = True
        elif log.type == LogType.MOVE_CARD:
            if (log.playerIndex == my_index
                and (log.fromArea == AreaType.BENCH or log.fromArea == AreaType.ACTIVE)
                and log.toArea == AreaType.DISCARD):
                pre_ko = True

    if select.deck != None:
        set_card_counts(obs, my_index)
        for card in select.deck:
            card_counts[card.id] -= 1
        prize.clear()
        for id in card_counts:
            for _ in range(card_counts[id]):
                prize.append(id)
                
    set_card_counts(obs, my_index)
    for id in prize:
        card_counts[id] -= 1
    deck_counts = card_counts

    prize_diff = len(my_state.prize) - len(op_state.prize)
    
    global bench_attacker

    # Number of cards per card ID on the Bench and in the Active Spot
    field_counts = defaultdict(int)
    # Number of cards per card ID in hand
    hand_counts = defaultdict(int)
    # Number of cards per card ID in discard pile
    discard_counts = defaultdict(int)
    
    active_id = 0
    bench_attacker = False
    can_evolve_dreepy = False
    evolve_dreepy_count = 0
    can_evolve_drakloak = False
    can_evolve_yomawaru = False
    can_evolve_samayouru = False
    damage = 200
    for card in my_state.active:
        if card == None:
            continue
        active_id = card.id
        field_counts[card.id] += 1
        if not card.appearThisTurn:
            if card.id == Dreepy:
                can_evolve_dreepy = True
                evolve_dreepy_count += 1
            elif card.id == Drakloak:
                can_evolve_drakloak = True
            elif card.id == Duskull:
                can_evolve_yomawaru = True
            elif card.id == Dusclops:
                can_evolve_samayouru = True
    for card in my_state.bench:
        field_counts[card.id] += 1
        if not card.appearThisTurn:
            if card.id == Dreepy:
                can_evolve_dreepy = True
                evolve_dreepy_count += 1
            elif card.id == Drakloak:
                can_evolve_drakloak = True
            elif card.id == Duskull:
                can_evolve_yomawaru = True
            elif card.id == Dusclops:
                can_evolve_samayouru = True
        if card.id == Dragapult_ex and len(card.energies) >= 2:
            bench_attacker = True
    main_pokemon_count = field_counts[Dreepy] + field_counts[Drakloak] + field_counts[Dragapult_ex]
    no_more_dex = (field_counts[Dragapult_ex] * 2 >= len(op_state.prize))

    stadium_id = 0
    for card in state.stadium:
        stadium_id = card.id

    support_count = 0

    for card in my_state.discard:
        discard_counts[card.id] += 1

    def hand_score(id: int, ignore_count: bool):
        score = 0
        if id == Dreepy:
            if main_pokemon_count >= 3:
                score = 1000
            else:
                score = 18000
        elif id == Drakloak:
            if can_evolve_dreepy:
                score = 20000
            else:
                score = 3000
        elif id == Dragapult_ex:
            if no_more_dex:
                score = UNNECESSARY
            elif can_evolve_dreepy and hand_counts[Rare_Candy] >= 1 and not no_item:
                score = 40000
            elif can_evolve_drakloak:
                if field_counts[id] == 0:
                    score = 30000
                elif field_counts[id] == 1:
                    score = 10000
                else:
                    score = 50
            else:
                if field_counts[id] >= 2:
                    score = 50
                else:
                    score = 2000
        elif id == Fezandipiti_ex:
            if pre_ko:
                score = 50000
            elif prize_diff <= -2:
                score = 5
            elif len(op_state.prize) == 1:
                score = UNNECESSARY
        elif id == Budew:
            if field_counts[id] + field_counts[Drakloak] + field_counts[Dragapult_ex] >= 1:
                score = UNNECESSARY
            elif state.turn >= 2:
                score = 30000
        elif id == Duskull:
            if field_counts[id] + field_counts[Dusclops] + field_counts[Dusknoir] >= 1:
                score = 1000
            else:
                score = 15000
        elif id == Dusclops:
            if can_evolve_yomawaru and field_counts[Dusclops] + field_counts[Dusknoir] == 0:
                score = 16000
            else:
                score = 1000
        elif id == Dusknoir:
            if can_evolve_samayouru and field_counts[Dusknoir] == 0:
                score = 17000
            else:
                score = 1000
        elif id == Munkidori:
            if field_counts[id] == 0:
                score = 12000
            else:
                score = 500
        elif id == Moltres:
            if field_counts[id] == 0:
                score = 12000
            else:
                score = 500
        elif id == Yveltal:
            if field_counts[id] == 0:
                score = 13000
            else:
                score = 500
        elif id == Meowth_ex:
            if support_count > hand_counts[Boss_Orders]:
                score = 5
            elif state.supporterPlayed:
                score = 40
            else:
                score = 35000
        elif id == Rare_Candy:
            if no_more_dex:
                score = UNNECESSARY
            elif can_evolve_dreepy and hand_counts[Dragapult_ex] >= 1:
                score = 40000
        elif id == Unfair_Stamp:
            if pre_ko:
                score = 80000
            elif len(op_state.prize) == 1:
                score = UNNECESSARY
            else:
                score = 80
        elif id == Buddy_Buddy_Poffin:
            count = deck_counts[Dreepy]
            if count == 0:
                score = UNNECESSARY
            else:
                if state.turn <= 2 and field_counts[Budew] == 0 and deck_counts[Budew] >= 1:
                    count += 1
                if count >= 2:
                    score = 35000
        elif id == Night_Stretcher:
            for i in discard_counts:
                if discard_counts[i] >= 1:
                    card_type = card_table[i].cardType
                    if card_type == CardType.POKEMON or card_type == CardType.BASIC_ENERGY:
                        score = max(score, hand_score(i, ignore_count))
        elif id == Ultra_Ball:
            if main_pokemon_count <= 2 or field_counts[Dreepy] >= 1:
                score = 70
            else:
                score = 5
        elif id == Poke_Pad:
            score = max(hand_score(Dreepy, ignore_count), hand_score(Drakloak, ignore_count))
        elif id == Boss_Orders:
            score = _boss_orders_score(plan_a.attack > 0, _dragapult_rng.random(), BOSS_ORDERS_EXPLORE_EPSILON)
        elif id == Crispin:
            if not ignore_count or support_count == 0:
                score = _crispin_score(
                    deck_counts=deck_counts, can_main_attack=can_main_attack,
                    bench_attacker=bench_attacker, field_counts=field_counts,
                )
        elif id == Lillie_Determination:
            if not ignore_count or support_count == 0:
                score = 45000
        elif id == Basic_Fire_Energy or id == Basic_Psychic_Energy:
            if can_main_attack and (len(op_state.prize) <= 2
                or (bench_attacker and len(op_state.prize) <= 4)):
                score = UNNECESSARY
            else:
                max_score = -10000
                for pokemon in my_state.active:
                    if pokemon == None:
                        continue
                    max_score = max(max_score, _attach_score(
                        id, pokemon, True,
                        card_table=card_table, can_switch=can_switch, bench_attacker=bench_attacker,
                        no_more_dex=no_more_dex, field_counts=field_counts,
                        my_asleep=my_state.asleep, my_paralyzed=my_state.paralyzed,
                    ))
                for pokemon in my_state.bench:
                    max_score = max(max_score, _attach_score(
                        id, pokemon, False,
                        card_table=card_table, can_switch=can_switch, bench_attacker=bench_attacker,
                        no_more_dex=no_more_dex, field_counts=field_counts,
                        my_asleep=my_state.asleep, my_paralyzed=my_state.paralyzed,
                    ))
                score = max_score - 5000
                if can_main_attack or bench_attacker:
                    score /= 10
        
        if not ignore_count and hand_counts[id] > 0:
            if id == Drakloak and hand_counts[id] < evolve_dreepy_count:
                score -= 10
            elif id == Dreepy:
                score -= 100
            else:
                score -= 100000
        return score

    global use_support
    if context == SelectContext.MAIN:
        main_option_proc(obs, damage)
                    
        use_support = 0
        if not state.supporterPlayed:
            support_score = 0
            for o in select.option:
                if o.type == OptionType.PLAY:
                    card = get_card(obs, AreaType.HAND, o.index, state.yourIndex)
                    if card_table[card.id].cardType == CardType.SUPPORTER:
                        score = hand_score(card.id, True)
                        if support_score < score:
                            support_score = score
                            use_support = card.id

    hand_scores = []
    negative_hand_count = 0
    for card in my_state.hand:
        score = hand_score(card.id, False)
        hand_scores.append(score)
        if score < 0:
            negative_hand_count += 1
        hand_counts[card.id] += 1
        if card_table[card.id].cardType == CardType.SUPPORTER and card.id != Boss_Orders:
            support_count += 1

    no_draw = (my_state.deckCount <= 8)  # Whether to restrict actions that reduce the deck
    do_switch = (not can_main_attack and (bench_attacker or (active_id != Budew and field_counts[Budew] >= 1 and state.turn >= 2)))
    effect_card_id = 0 if select.effect == None else select.effect.id
    context_card_id = 0 if select.contextCard == None else select.contextCard.id
    
    scores = []  # Score for each action
    for o in select.option:
        score = 0  # The default and baseline score is 0.
        if o.type == OptionType.NUMBER:
            score = o.number
        elif o.type == OptionType.YES:
            if context == SelectContext.IS_FIRST:
                score = -1
            else:
                score = 1
        elif o.type == OptionType.CARD:
            card = get_card(obs, o.area, o.index, o.playerIndex)
            if card != None:
                energy_count = 0
                hp = 0
                if isinstance(card, Pokemon):
                    energy_count = len(card.energies)
                    hp = card.hp
                if (context == SelectContext.SWITCH
                    or context == SelectContext.TO_ACTIVE
                    or context == SelectContext.SETUP_ACTIVE_POKEMON):
                    # Selection of the Pokémon to send to the Active Spot
                    if o.playerIndex == my_index:
                        score += _own_switch_target_score(card.id, energy_count, bench_attacker)
                    else:
                        if plan_a.attack == o.index + 1:
                            score += 100000
                    score += energy_count * 1000
                    score += hp
                elif context == SelectContext.SETUP_BENCH_POKEMON:
                    if my_index == state.firstPlayer or card.id != Dreepy:
                        score = -1
                elif context == SelectContext.TO_BENCH or context == SelectContext.TO_HAND:
                    score = hand_score(card.id, False)
                    hand_counts[card.id] += 1
                    if effect_card_id == Crispin:
                        # Reverse scoring
                        score = 100000 - hand_score(card.id, True)
                elif context == SelectContext.DISCARD:
                    hand_counts[card.id] -= 1
                    if card_table[card.id].cardType == CardType.SUPPORTER:
                        support_count -= 1
                    score = -hand_score(card.id, False)
                elif context == SelectContext.DAMAGE_COUNTER or context == SelectContext.DAMAGE_COUNTER_ANY:
                    if hp > 0:
                        score = 100000 - 10 * hp + pokemon_score(card, False)
                        if context == SelectContext.DAMAGE_COUNTER:
                            if 210 <= hp <= 230:
                                score += 20000 + hp * 20
                                if o.area == AreaType.ACTIVE:
                                    score += 10000
                            elif 40 <= hp <= 90:
                                score += 10000 + hp * 20
                            elif hp <= 30:
                                score += -10000 + hp * 20
                            if card.id == 133 or card.id == 351:
                                score += 30000
                        else:
                            index = o.index + 1
                            if index in plan_b.counter:
                                score += 100000
                            else:
                                remain_damage = select.remainDamageCounter * 10
                                if 210 <= hp <= 200 + remain_damage:
                                    score += 30000
                                elif 20 <= hp <= 60 + remain_damage:
                                    score += 10000
                                elif hp == 10:
                                    score -= 100000
                            if no_damage_counter(card):
                                score = -1
                elif context == SelectContext.ATTACH_FROM:
                    score = _attach_score(
                        context_card_id, card, o.area == AreaType.ACTIVE,
                        card_table=card_table, can_switch=can_switch, bench_attacker=bench_attacker,
                        no_more_dex=no_more_dex, field_counts=field_counts,
                        my_asleep=my_state.asleep, my_paralyzed=my_state.paralyzed,
                    )
                    if card.id == Dragapult_ex:
                        score += 200
        elif o.type == OptionType.ENERGY_CARD or o.type == OptionType.ENERGY:
            # Discarding energy (Retreat or Crushing Hammer)
            if o.playerIndex != state.yourIndex:
                if o.area == AreaType.BENCH:
                    score = 20
                else:
                    score = 10
                card = get_card(obs, o.area, o.index, o.playerIndex)
                if card_table[card.id].cardType == CardType.SPECIAL_ENERGY:
                    score += 1
        elif o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            card_score = hand_scores[o.index]
            if card.id == Dreepy:
                score = 51000
            elif card.id == Fezandipiti_ex:
                if card_score > 0:
                    score = 53000
                else:
                    score = -1
            elif card.id == Budew:
                if field_counts[Budew] == 0 and field_counts[Dragapult_ex] == 0:
                    score = 52000
                else:
                    score = -1
            elif card.id == Duskull:
                if field_counts[Duskull] + field_counts[Dusclops] + field_counts[Dusknoir] == 0:
                    score = 51000
                else:
                    score = -1
            elif card.id == Munkidori:
                if field_counts[Munkidori] == 0:
                    score = 51000
                else:
                    score = -1
            elif card.id == Moltres:
                if field_counts[Moltres] == 0:
                    score = 51000
                else:
                    score = -1
            elif card.id == Yveltal:
                if field_counts[Yveltal] == 0:
                    score = 51000
                else:
                    score = -1
            elif card.id == Meowth_ex:
                if state.supporterPlayed:
                    score = -1
                elif support_count == 0:
                    score = 50000
                elif support_count == hand_counts[Boss_Orders] and not plan_a.attack <= 0:
                    score = 50000
                else:
                    score = -1
            else:
                # トレーナーズカード(グッズ/サポート/スタジアム)はTrainerCardPolicyへ委譲
                # (docs/superpowers/plans/2026-07-23-dragapult-trainer-card-policy-migration.md)
                ctx = PlayTrainerCardContext(
                    card_id=card.id, card_score=card_score, state=state, stadium_id=stadium_id,
                    deck_counts=deck_counts, negative_hand_count=negative_hand_count,
                    no_draw=no_draw, use_support=use_support, no_more_dex=no_more_dex,
                )
                score = _score_play_trainer_card(card.id, ctx)
        elif o.type == OptionType.ATTACH:
            card = get_card(obs, o.area, o.index, my_index)
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            score = _attach_score(
                card.id, pokemon, o.inPlayArea == AreaType.ACTIVE,
                card_table=card_table, can_switch=can_switch, bench_attacker=bench_attacker,
                no_more_dex=no_more_dex, field_counts=field_counts,
                my_asleep=my_state.asleep, my_paralyzed=my_state.paralyzed,
            )
        elif o.type == OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            score = _evolve_score(
                pokemon.id, len(pokemon.energies), field_counts[Dragapult_ex], len(op_state.prize),
            )
        elif o.type == OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if no_draw:
                score = -1
            elif card.id == 1267:  # Lumiose City
                score = 1
            elif card.id == Duskull:
                bench_space = my_state.benchMax - len(my_state.bench)
                score = _fetch_from_discard_score(discard_counts[Duskull], bench_space)
            elif card.id == Dusknoir or card.id == Dusclops:
                opponent_active_id = op_state.active[0].id if op_state.active else None
                score = _cursed_bomb_score(opponent_active_id)
            elif card.id == Munkidori:
                opponent_active_id = op_state.active[0].id if op_state.active else None
                score = _adrena_brain_score(opponent_active_id)
            else:
                score = 40000
        elif o.type == OptionType.RETREAT:
            if do_switch:
                score = 10000
            else:
                score = -1
        elif o.type == OptionType.ATTACK:
            score = o.attackId

        scores.append(score)

    output = []
    if len(scores) >= 1:
        # Select in descending order of score
        sorted_scores = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        for i in range(select.maxCount):
            # If the score is negative, do not select it if skipping is possible
            if (sorted_scores[i][1] >= 0
                or select.minCount > i
                or (context != SelectContext.TO_BENCH and context != SelectContext.SETUP_BENCH_POKEMON)):
                output.append(sorted_scores[i][0])
                
    return output

