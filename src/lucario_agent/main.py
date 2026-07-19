import os
import random
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, Option, PlayerState, all_card_data, to_observation_class,
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
Rock_Fighting_Energy  = 20  # ロック闘エネルギー：装着ポケモンは相手の技の"効果"を受けない（Alakazam「ハンドパワー」対策）
Ultra_Ball                 = 1121
Pokegear                   = 1122
Night_Stretcher            = 1097
Judge                      = 1213
Hilda                      = 1225
Wally_Compassion           = 1229
Ciphermaniac_Codebreaking  = 1188
Ogerpon_ex                 = 117
Crustle                     = 345  # 特性「ふしぎな岩の宿」：相手の「ポケモン【ex】」の技ダメージを無効化する壁ポケモン

EPSILON = 0.28  # 温存判断時に探索的先出しをする確率
_rng    = random.Random()  # 本番用の実乱数。テストではスタブを注入する

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
    elif pokemon.id == Ogerpon_ex:
        if energy_count < 3:
            score += 80
        if attacker1:
            score += 40  # ルカリオ確保済みなら余剰エネルギーをオーガポンexへ
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
def _calc_attack_damage(attacker_id: int, base_damage: int, defender_id: int, defender_data) -> int:
    """弱点・抵抗力・Crustleの特性無効化を考慮した実ダメージを1箇所で計算する"""
    damage = base_damage
    attack_ignores_defender_effects = attacker_id == Ogerpon_ex  # ぶちやぶる：相手にかかっている効果を計算しない
    if not attack_ignores_defender_effects:
        if defender_data.weakness == EnergyType.FIGHTING:
            damage *= 2
        elif defender_data.resistance == EnergyType.FIGHTING:
            damage -= 30

    defender_nullifies_ex_damage = defender_id == Crustle and attacker_id == Mega_Lucario_ex
    if defender_nullifies_ex_damage:
        damage = 0  # Crustleの特性「ふしぎな岩の宿」：相手のexポケモンの技ダメージを無効化する

    return damage


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
    rng: "random.Random | None" = None,
) -> AttackPlan:
    """最適な攻撃プランを計算して返す。

    【メモ・2026-07-17】Mega_Lucario_ex/Solrock/Ogerpon_exのアタッカー候補は
    if/elif連鎖で判定している。2026-07-07にテーブル化リファクタリング
    （アタッカー定義をdataclassのリストに切り出す案）が検討されたが、
    ブレスト中にスコープ確定直後で中断されたまま未着手。今回のTrainerCardPolicy化とは
    別スコープのため対象外とする
    """
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
            elif a == 1:
                break
            elif my_pokemon.id == Solrock:
                if field_counts[Lunatone] >= 1:
                    energy_required = 1
                    base_damage     = 70
            elif my_pokemon.id == Ogerpon_ex:
                energy_required = 3
                base_damage     = 140

            if base_damage <= 0:
                continue

            energy_count = len(my_pokemon.energies)
            more_energy  = False
            mega_brave_unavailable_for_current_active = (
                a == 1 and i == 0 and energy_count >= 2 and not can_use_mega_brave
            )
            if mega_brave_unavailable_for_current_active:
                break
            if energy_count < energy_required:
                can_attach_energy_this_turn = (
                    hand_counts[Basic_Fighting_Energy] + hand_counts[Rock_Fighting_Energy] >= 1
                    and not state.energyAttached
                )
                if can_attach_energy_this_turn:
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
                data   = card_table[op_pokemon.id]
                damage = _calc_attack_damage(my_pokemon.id, base_damage, op_pokemon.id, data)

                prize = 0
                score = pokemon_score(op_pokemon)
                if op_pokemon.hp <= damage:
                    prize = prize_count(op_pokemon)
                else:
                    score *= damage / op_pokemon.hp
                score += base_score

                is_mega_brave_choice = my_pokemon.id == Mega_Lucario_ex and a == 1
                if is_mega_brave_choice:
                    base_dmg_normal = _calc_attack_damage(my_pokemon.id, 130, op_pokemon.id, data)
                    if op_pokemon.hp <= base_dmg_normal:
                        score -= 1000  # 通常攻撃で足りるならメガブレイブは温存
                    elif op_pokemon.hp > damage:
                        active_rng = rng if rng is not None else _rng
                        if active_rng.random() >= EPSILON:
                            score -= 300  # 探索に外れたら温存寄り

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
            # 【メモ・2026-07-17】current_plan(グローバルplan)はSelectContext.MAIN かつ
            # turn>=2 のタイミングでのみ再計算される。それ以外のタイミング（相手の
            # ボスの指令等で強制的にこのコンテキストへ入った場合）は直前のMAIN計算
            # 時点の古いattacker/targetを参照し続けるため、盤面が変わった後もスコアが
            # ズレる可能性がある。2026-07-17時点ではこれが直接の敗因になったケースは
            # 未確認（実ログ86197001の敗因はSETUP_ACTIVE_POKEMON側だった）が、
            # 潜在リスクとして次回検討の余地がある
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
                elif card.id == Ogerpon_ex:
                    score += 20 if energy_count >= 3 else 6
            else:
                score = 100 if o.index == current_plan.target - 1 else 0
            return score

        case SelectContext.SETUP_ACTIVE_POKEMON:
            if card.id == Solrock:
                return 4 if state.firstPlayer != my_index else 2
            if card.id == Riolu:
                return 3
            if card.id == Ogerpon_ex:
                return 1  # ルナトーン(0点)より優先。Riolu/Solrockには劣後させたまま
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
            elif card.id == Ogerpon_ex:
                # デッキ採用枚数(2枚)に対する充足度で優先度を調整（Riolu方式を踏襲）
                score += -150 if field_counts[Ogerpon_ex] >= 2 else (-3 if field_counts[Ogerpon_ex] >= 1 else 40)
            elif card.id == Basic_Fighting_Energy:
                score += 30 if not ability_used_flag or not state.energyAttached else -1
            return score

        case SelectContext.DISCARD:
            if o.playerIndex != my_index:
                return 0
            if card.id == Basic_Fighting_Energy:
                return 50 if hand_counts[Basic_Fighting_Energy] >= 2 else -20
            if card.id in (Riolu, Mega_Lucario_ex, Solrock, Lunatone, Ogerpon_ex, Judge):
                return -100
            if card.id in (Boss_Orders, Lillie_Determination):
                return -50
            return 10

        case SelectContext.ATTACH_FROM:
            return energy_score(card, o.area == AreaType.ACTIVE, attacker1)

        case _:
            return 0


# ==================== 山札セーフティ（battlecore B方式） ====================
def _safe_draws(my_state) -> int:
    """安全に消費できる山札枚数。残りプライズ数を残りターン数の見積もりとして使い、
    毎ターンの必須ドロー分を温存する（デッキアウト防止。実ログ85626724が直接の動機）"""
    return my_state.deckCount - len(my_state.prize) - 1


def _deck_consumption(card_id: int, my_state, hand_counts: defaultdict) -> "int | None":
    """このカードを使った場合の山札の正味消費枚数。山札を消費しない札はNone"""
    hand_count = sum(hand_counts.values())
    if card_id == Lillie_Determination:
        draws = 8 if len(my_state.prize) == 6 else 6
        return max(0, draws - (hand_count - 1))
    if card_id == Judge:
        return max(0, 4 - (hand_count - 1))
    if card_id == Hilda:
        return 2
    if card_id in (Pokegear, Ultra_Ball, Poke_Pad):
        return 1
    return None


# ==================== PLAYスコアリングのポリシー登録制 ====================
@dataclass
class PlayScoringContext:
    """OptionType.PLAY のスコアリングに必要な情報をまとめる（_score_play_optionの既存引数を集約）"""
    obs: Observation
    o: Option
    my_index: int
    current_plan: AttackPlan
    can_attack: bool
    state: PlayerState
    my_state: PlayerState
    hand_counts: defaultdict
    field_counts: defaultdict
    stadium_id: int
    attacker1: bool = False
    rng: "random.Random | None" = None
    op_hand_count: int = 0


class TrainerCardPolicy(ABC):
    """1枚のトレーナーズカード（サポート/グッズ/スタジアム）のPLAY判断を表す"""
    @abstractmethod
    def play_score(self, ctx: PlayScoringContext) -> int: ...


class FixedScorePolicy(TrainerCardPolicy):
    """固定スコアのみを返すカード用"""
    def __init__(self, score: int):
        self._score = score

    def play_score(self, ctx: PlayScoringContext) -> int:
        return self._score


class PremiumPowerProPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        confirmed_ko_already_secured = ctx.state.supporterPlayed and ctx.current_plan.remain_hp <= 0
        if confirmed_ko_already_secured:
            return -1
        if ctx.can_attack:
            return 5000
        other_supporter_in_hand = ctx.hand_counts[Boss_Orders] >= 1 or ctx.hand_counts[Lillie_Determination] >= 1
        if not ctx.state.supporterPlayed and not other_supporter_in_hand:
            return 3050
        return -1


class BossOrdersPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        if ctx.current_plan.target < 1:
            return -1  # 対象不在なら温存
        if ctx.current_plan.remain_hp <= 0:
            return 8800  # 即使用（確定KO）
        active_rng = ctx.rng if ctx.rng is not None else _rng
        if active_rng.random() < EPSILON:
            return 6000  # 探索的先出し
        return -1  # 温存


class LillieDeterminationPolicy(TrainerCardPolicy):
    """手札に「今すぐ場へ展開できる」主要ポケモンがあれば温存する。
    Mega Lucario exは進化元のRioluが場にいなければ死に札のため、温存条件から除外する
    （86363073, 86197001, 86241854, 86295193, 86295949, 86486986等の実ログで、
    有用な手札を持ちながら、あるいは死に札を有用と誤認して山札に戻していた
    ロジックミスの修正）"""
    DIRECTLY_PLAYABLE_IDS = (Riolu, Ogerpon_ex, Solrock, Lunatone)

    def play_score(self, ctx: PlayScoringContext) -> int:
        deployable = any(ctx.hand_counts[pid] >= 1 for pid in self.DIRECTLY_PLAYABLE_IDS)
        deployable = deployable or (
            ctx.hand_counts[Mega_Lucario_ex] >= 1 and ctx.field_counts[Riolu] >= 1
        )
        return -1 if deployable else 3100


class UltraBallPolicy(TrainerCardPolicy):
    """主要ポケモンを十分確保済み（already_found>=3）ならスコアを大幅に下げる
    （86197001の実ログで、手札がボスの指令とメガルカリオexの2枚しかない状況でも
    ハイパーボールを撃ち両方とも巻き込んで捨てていたロジックミスの修正）"""
    ALREADY_FOUND_SUPPRESS_THRESHOLD = 3

    def play_score(self, ctx: PlayScoringContext) -> int:
        already_found = (
            ctx.field_counts[Riolu] + ctx.field_counts[Mega_Lucario_ex] + ctx.field_counts[Ogerpon_ex]
            + ctx.hand_counts[Riolu] + ctx.hand_counts[Mega_Lucario_ex] + ctx.hand_counts[Ogerpon_ex]
        )
        if already_found >= self.ALREADY_FOUND_SUPPRESS_THRESHOLD:
            return 100
        return 6000 if already_found == 0 else 5500


class JudgePolicy(TrainerCardPolicy):
    """相手の手札が閾値以上に膨れている場合は最優先で発動する
    （Alakazam系のPsychic Draw×Rare Candyドローエンジン対策。実ログ86139105ほかで、
    相手手札が最大25枚まで膨張しても8敗中5敗でJudgeが一度も使われていなかった問題の修正。
    閾値は暫定値）"""
    OPPONENT_HAND_THRESHOLD = 10

    def play_score(self, ctx: PlayScoringContext) -> int:
        if ctx.op_hand_count >= self.OPPONENT_HAND_THRESHOLD:
            return 9000
        no_fighting_energy_in_hand = (
            ctx.hand_counts[Basic_Fighting_Energy] + ctx.hand_counts[Rock_Fighting_Energy] == 0
        )
        return 7000 if no_fighting_energy_in_hand and not ctx.attacker1 else -1


class WallyCompassionPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        my_lucario = next(
            (p for p in ([ctx.my_state.active[0]] if ctx.my_state.active else []) + list(ctx.my_state.bench)
             if p is not None and p.id == Mega_Lucario_ex),
            None,
        )
        if my_lucario is not None and my_lucario.hp < my_lucario.maxHp:
            return 6800
        return -1


class GravityMountainPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        return -1 if ctx.stadium_id == 0 else 10000


TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Premium_Power_Pro: PremiumPowerProPolicy(),
    Boss_Orders: BossOrdersPolicy(),
    Lillie_Determination: LillieDeterminationPolicy(),
    Ultra_Ball: UltraBallPolicy(),
    Pokegear: FixedScorePolicy(5200),
    Night_Stretcher: FixedScorePolicy(4800),
    Judge: JudgePolicy(),
    Hilda: FixedScorePolicy(5300),
    Ciphermaniac_Codebreaking: FixedScorePolicy(5100),
    Wally_Compassion: WallyCompassionPolicy(),
    Gravity_Mountain: GravityMountainPolicy(),
}


def _score_play_option(obs, o, my_index, current_plan, can_attack,
                       state, my_state, hand_counts, field_counts, stadium_id,
                       attacker1: bool = False,
                       rng: "random.Random | None" = None,
                       op_hand_count: int = 0) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]
    consumption = _deck_consumption(card.id, my_state, hand_counts)
    if consumption is not None and consumption > _safe_draws(my_state):
        return -1  # 山札温存
    if data.cardType == CardType.POKEMON:
        if card.id in (Lunatone, Solrock):
            return -1 if field_counts[card.id] >= 1 else 20000
        if card.id == Riolu:
            return -1 if field_counts[Riolu] + field_counts[Mega_Lucario_ex] >= 2 else 20000
        return 20000

    policy = TRAINER_CARD_POLICIES.get(card.id)
    if policy is None:
        return 10000

    ctx = PlayScoringContext(
        obs=obs, o=o, my_index=my_index, current_plan=current_plan, can_attack=can_attack,
        state=state, my_state=my_state, hand_counts=hand_counts, field_counts=field_counts,
        stadium_id=stadium_id, attacker1=attacker1, rng=rng, op_hand_count=op_hand_count,
    )
    return policy.play_score(ctx)


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
    if card.id == Rock_Fighting_Energy and o.inPlayArea == AreaType.ACTIVE:
        # Alakazam「ハンドパワー」はアクティブのポケモンのみを狙うため、
        # そのときアクティブの子を優先的に守る
        score += 500
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
                attacker1, op_hand_count=op_state.handCount,
            )
        case OptionType.ATTACH:
            return _score_attach_option(obs, o, my_index, current_plan, attacker1)
        case OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            return 9000 + len(pokemon.energies)
        case OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if card.id == 1267:
                return 1  # Lumiose City は低優先
            if card.id == Lunatone:
                # ルナサイクルの発動条件（カードテキスト）：場にソルロックがいる／手札の
                # 基本闘エネルギーをトラッシュできる。予備(2枚以上)が無い時は手札の最後の
                # 1枚を失うため温存する（実ログ86456814ほかで多発していた症状の修正）
                lunar_cycle_ready = (
                    field_counts[Solrock] >= 1 and hand_counts[Basic_Fighting_Energy] >= 2
                )
                return 8500 if _safe_draws(my_state) >= 3 and lunar_cycle_ready else -1
            return 30000
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
