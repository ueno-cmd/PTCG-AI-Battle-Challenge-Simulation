import os
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, all_attack, to_observation_class,
    Option, PlayerState,
)

# ==================== カードID定数 ====================
Raging_Bolt_ex          = 63    # タケルライコex
Iono_Voltorb            = 265   # ナンジャモのビリリダマ
Iono_Tadbulb            = 268   # ナンジャモのズピカ
Iono_Bellibolt_ex       = 269   # ナンジャモのハラバリーex
Iono_Wattrel            = 270   # ナンジャモのカイデン
Iono_Kilowattrel        = 271   # ナンジャモのタイカイデン
Buddy_Buddy_Poffin      = 1086  # なかよしポフィン
Night_Stretcher         = 1097  # 夜のタンカ
Max_Rod                 = 1110  # つりざおMAX (ACE SPEC)
Energy_Retrieval        = 1118  # エネルギー回収
Energy_Switch            = 1116  # エネルギーつけかえ（自分の場のポケモン間で基本エネルギー1個を付け替え）
Ultra_Ball               = 1121  # ハイパーボール
Switch                   = 1123  # ポケモンいれかえ
Boss_Orders               = 1182  # ボスの指令
Lillie_Determination       = 1227  # リーリエの決心
Canari                     = 1233  # カナリィ
Levincia                   = 1254  # ハッコウシティ
Basic_Lightning_Energy      = 4
Basic_Fighting_Energy       = 6

IONO_POKEMON_IDS = {Iono_Voltorb, Iono_Tadbulb, Iono_Bellibolt_ex, Iono_Wattrel, Iono_Kilowattrel}

def _safe_draws(my_state) -> int:
    """安全に消費できる山札枚数。残りプライズ数を残りターン数の見積もりとして使い、
    毎ターンの必須ドロー分を温存する（デッキアウト防止）"""
    return my_state.deckCount - len(my_state.prize) - 1


def _deck_consumption(card_id: int, my_state, hand_counts: defaultdict) -> "int | None":
    """このカードを使った場合の山札の正味消費枚数。山札を消費しない札はNone"""
    hand_count = sum(hand_counts.values())
    if card_id == Lillie_Determination:
        draws = 8 if len(my_state.prize) == 6 else 6
        return max(0, draws - (hand_count - 1))
    return None


def _flashing_draw_consumption(my_state, hand_counts: defaultdict) -> int:
    """タイカイデンの特性「フラッシュドロー」による山札消費枚数
    （自身の雷エネ1個をコストにトラッシュし、手札が6枚になるまでドロー）"""
    hand_count = sum(hand_counts.values())
    return max(0, 6 - hand_count)


# ==================== フィールド状態 ====================
@dataclass
class FieldState:
    field_counts: defaultdict
    hand_counts: defaultdict
    discard_counts: defaultdict
    iono_lightning_on_board: int
    active_energy_count: int
    hand_has_basic_lightning_energy: bool = False


def _collect_field_state(my_state) -> FieldState:
    """バトル場・ベンチ・手札・捨て山のカード枚数と、
    チェインボルトのダメージ計算に必要な雷エネルギー集計を返す。"""
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)
    iono_lightning_on_board = 0
    active_energy_count = 0

    active = my_state.active[0] if my_state.active else None

    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        field_counts[card.id] += 1
        lightning = card.energies.count(EnergyType.LIGHTNING)
        if card.id in IONO_POKEMON_IDS:
            iono_lightning_on_board += lightning

    if active is not None:
        active_energy_count = len(active.energies)

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    return FieldState(
        field_counts=field_counts,
        hand_counts=hand_counts,
        discard_counts=discard_counts,
        iono_lightning_on_board=iono_lightning_on_board,
        active_energy_count=active_energy_count,
        hand_has_basic_lightning_energy=hand_counts[Basic_Lightning_Energy] > 0,
    )


# ==================== アタッカーテーブル ====================
@dataclass(frozen=True)
class Attacker:
    id: int
    attack_name: str
    energy_required: int
    damage_fn: Callable[[FieldState], int]
    locks_next_turn: bool = False


ATTACKERS: list[Attacker] = [
    Attacker(id=Iono_Voltorb, attack_name="Voltaic Chain", energy_required=2,
             damage_fn=lambda fs: 20 + 20 * fs.iono_lightning_on_board),
    Attacker(id=Iono_Bellibolt_ex, attack_name="Thunderous Bolt", energy_required=4,
             damage_fn=lambda fs: 230, locks_next_turn=True),
    Attacker(id=Iono_Kilowattrel, attack_name="Mach Bolt", energy_required=3,
             damage_fn=lambda fs: 70),
]


# ==================== ポケモンライン優先度テーブル ====================
@dataclass(frozen=True)
class PokemonLine:
    id: int
    pre_evo_id: int | None = None     # 進化前のID（自身が進化ポケモンの場合）
    max_field_copies: int = 1         # 場+手札に置きたい上限（これ以上のサーチ優先度は下げる）
    setup_active_priority: int = 0    # 初期アクティブ選択時の基礎優先度


POKEMON_LINES: dict[int, PokemonLine] = {
    Iono_Voltorb:      PokemonLine(id=Iono_Voltorb, max_field_copies=3, setup_active_priority=300),
    Iono_Tadbulb:      PokemonLine(id=Iono_Tadbulb, max_field_copies=1, setup_active_priority=50),
    Iono_Bellibolt_ex: PokemonLine(id=Iono_Bellibolt_ex, pre_evo_id=Iono_Tadbulb, max_field_copies=1),
    Iono_Wattrel:      PokemonLine(id=Iono_Wattrel, max_field_copies=1, setup_active_priority=50),
    Iono_Kilowattrel:  PokemonLine(id=Iono_Kilowattrel, pre_evo_id=Iono_Wattrel, max_field_copies=1),
}


# ==================== 攻撃プラン計算 ====================
@dataclass
class AttackPlan:
    attacker_id: int = -1
    attack_id:   int = -1
    damage:      int = 0
    is_lethal:   bool = False


def calc_attack_plan(my_active: "Pokemon | None", op_active_hp: int,
                      fs: FieldState, my_state) -> AttackPlan:
    """アクティブなポケモンについて、テーブル上の候補技から最適な1つを選ぶ。

    優先順位：
    1. 確定KOできる技があれば最優先
    2. 確定KOがなければ最大ダメージを選ぶが、次ターン技封じの技は減点評価
    """
    if my_active is None:
        return AttackPlan()

    candidates = []
    for atk in ATTACKERS:
        if atk.id != my_active.id:
            continue
        if fs.active_energy_count < atk.energy_required:
            continue
        damage = atk.damage_fn(fs)
        is_lethal = damage >= op_active_hp
        candidates.append((atk, damage, is_lethal))

    if not candidates:
        return AttackPlan()

    lethal = [c for c in candidates if c[2]]
    if lethal:
        # 現在のATTACKERSテーブルでは同一ポケモンが複数の技エントリを持つことはないため、
        # 複数のlethal候補から選別するロジックは不要。先頭を採用すれば十分
        chosen = lethal[0]
    else:
        def effective_damage(c):
            atk, damage, _ = c
            return damage - (150 if atk.locks_next_turn else 0)
        chosen = max(candidates, key=effective_damage)

    atk, damage, is_lethal = chosen
    attack_id = _attack_id_by_name(atk.attack_name)
    return AttackPlan(
        attacker_id=atk.id,
        attack_id=attack_id if attack_id is not None else -1,
        damage=damage,
        is_lethal=is_lethal,
    )


# ==================== エネルギー運用ポリシー ====================
class EnergyPolicy:
    """雷/闘エネルギーの手張り優先度、エネルギーつけかえの運用、
    きょくらいごうの追加ダメージ用エネルギー破棄を1箇所に集約する。
    OptionType.ATTACH / PLAY / ENERGY_CARD という複数のSelectContextに
    またがるロジックをここに閉じ込め、散逸を防ぐ。
    """

    SURPLUS_THRESHOLD = {
        Iono_Bellibolt_ex: 4,  # Thunderous Boltのenergy_required（ATTACKERSテーブルより）
        Iono_Kilowattrel: 3,   # Mach Boltのenergy_required（ATTACKERSテーブルより）
    }

    def attach_priority(self, pokemon: Pokemon, active: bool) -> int:
        """雷エネルギー装填先の優先度スコアを返す（攻撃射程に近いほど高スコア）"""
        lightning_count = pokemon.energies.count(EnergyType.LIGHTNING)
        score = 8000
        if active:
            score += 10
        if pokemon.id == Iono_Voltorb:
            if lightning_count < 2:
                score += 100
        elif pokemon.id == Iono_Bellibolt_ex:
            if lightning_count < 4:
                score += 60
        elif pokemon.id == Iono_Kilowattrel:
            if lightning_count < 3:
                score += 40
        elif pokemon.id == Raging_Bolt_ex:
            if lightning_count < 1:
                score += 90
        return score

    def find_surplus_source(self, my_state) -> "Pokemon | None":
        """エネルギーつけかえの供給元にできる、自分自身の攻撃条件を満たし
        雷エネルギーに余剰があるナンジャモポケモンを1体返す（無ければNone）。
        タケルライコex自身は候補に含まない（供給元は常に他のポケモン）。"""
        for card in my_state.active + my_state.bench:
            if card is None:
                continue
            threshold = self.SURPLUS_THRESHOLD.get(card.id)
            if threshold is None:
                continue
            lightning_count = card.energies.count(EnergyType.LIGHTNING)
            if lightning_count >= threshold:
                return card
        return None

    def needs_lightning(self, my_state) -> bool:
        """場のタケルライコexが雷エネルギーを1枚も持っていないか（きょくらいごうのコスト未達）"""
        for card in my_state.active + my_state.bench:
            if card is not None and card.id == Raging_Bolt_ex:
                if card.energies.count(EnergyType.LIGHTNING) < 1:
                    return True
        return False

    def has_growth_path(self, fs: FieldState, my_state) -> bool:
        """タケルライコexがまだきょくらいごう着地に伸びる見込みがあるか
        （手札に闘/雷の基本エネルギーがある、またはエネルギーつけかえの供給元がある）"""
        if fs.hand_counts[Basic_Fighting_Energy] > 0 or fs.hand_counts[Basic_Lightning_Energy] > 0:
            return True
        if fs.hand_counts[Energy_Switch] > 0 and self.find_surplus_source(my_state) is not None:
            return True
        return False

    def play_score(self, my_state) -> int:
        """OptionType.PLAY（エネルギーつけかえを使うか）のスコアを返す"""
        if self.needs_lightning(my_state) and self.find_surplus_source(my_state) is not None:
            return 7500  # タケルライコexが雷0枚で、ベンチに余剰供給元がある時のみ高優先
        return 200

    def switch_destination_score(self, card) -> int:
        """SelectContext.ATTACH_FROM（エネルギーつけかえで付け直す先のポケモン）のスコアを返す"""
        if not isinstance(card, Pokemon):
            return 0
        if card.id == Raging_Bolt_ex:
            return 500 if card.energies.count(EnergyType.LIGHTNING) < 1 else -500
        return 0

    def switch_source_score(self, obs, o, my_index: int) -> int:
        """SelectContext.SWITCH_ENERGY_CARD（エネルギーつけかえで動かす元の
        エネルギーカードを選ぶ）のスコアを返す"""
        card = get_card(obs, o.area, o.index, o.playerIndex)
        if not isinstance(card, Pokemon):
            return 0
        if card.id == Raging_Bolt_ex:
            return -1000  # タケルライコex自身のエネルギーは動かさない
        threshold = self.SURPLUS_THRESHOLD.get(card.id)
        if threshold is None:
            return 0
        lightning_count = card.energies.count(EnergyType.LIGHTNING)
        return 500 if lightning_count >= threshold else -500

    def discard_for_damage_score(self) -> int:
        """SelectContext.DISCARD_ENERGY_CARD（きょくらいごうの追加ダメージ用エネルギー破棄）
        のスコアを返す。貪欲方針：提示されたエネルギーは常に破棄する"""
        return 9000


ENERGY_POLICY = EnergyPolicy()


def _score_attach_option(obs, o, my_index: int) -> int:
    """OptionType.ATTACH のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
    if pokemon is None or card is None:
        return 0
    if card.id == Basic_Fighting_Energy:
        if pokemon.id == Raging_Bolt_ex:
            fighting_count = pokemon.energies.count(EnergyType.FIGHTING)
            return 7000 if fighting_count < 1 else 100
        return 50  # タケルライコex以外への闘エネは低優先
    if card.id == Basic_Lightning_Energy:
        return ENERGY_POLICY.attach_priority(pokemon, o.inPlayArea == AreaType.ACTIVE)
    return 0


# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}
attack_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築する"""
    global card_table
    if not card_table:
        card_table = {c.cardId: c for c in all_card_data()}
    return card_table


def _build_attack_table() -> dict:
    """attack_table（attackId -> Attack）を初回のみ構築する"""
    global attack_table
    if not attack_table:
        attack_table = {a.attackId: a for a in all_attack()}
    return attack_table


def _attack_id_by_name(name: str) -> "int | None":
    """技名からattackIdを逆引きする（cg.apiはKaggle環境でしか実行できないため、
    マジックナンバーを決め打ちせずattack_tableから解決する）"""
    for attack_id, attack in attack_table.items():
        if attack.name == name:
            return attack_id
    return None


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
        from decks.jamoraiko_20260713 import DECK
        my_deck = [card_id for card_id, count in DECK for _ in range(count)]
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


# ==================== PLAYスコアリングのポリシー登録制 ====================
@dataclass
class PlayScoringContext:
    """OptionType.PLAY のスコアリングに必要な情報をまとめる。
    将来カードが増えても、ポリシークラス側のシグネチャを変えずに済む"""
    obs: Observation
    o: Option
    my_index: int
    fs: FieldState
    my_state: PlayerState
    plan: AttackPlan


class TrainerCardPolicy(ABC):
    """1枚のトレーナーズカード（サポート/グッズ/スタジアム）のPLAY判断を表す"""
    @abstractmethod
    def play_score(self, ctx: PlayScoringContext) -> int: ...


class FixedScorePolicy(TrainerCardPolicy):
    """固定スコアを返すだけのカード用（ハイパーボール等、条件分岐が無いもの）"""
    def __init__(self, score: int):
        self._score = score

    def play_score(self, ctx: PlayScoringContext) -> int:
        return self._score


class LillieDeterminationPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        consumption = _deck_consumption(Lillie_Determination, ctx.my_state, ctx.fs.hand_counts)
        if consumption is not None and consumption > _safe_draws(ctx.my_state):
            return -1
        return 3100


class BossOrdersPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        return 8800 if ctx.plan.is_lethal else 500


class EnergySwitchPolicy(TrainerCardPolicy):
    """既存のENERGY_POLICYに委譲する（EnergyPolicy自体は変更しない）"""
    def play_score(self, ctx: PlayScoringContext) -> int:
        return ENERGY_POLICY.play_score(ctx.my_state)


TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Lillie_Determination: LillieDeterminationPolicy(),
    Boss_Orders: BossOrdersPolicy(),
    Energy_Switch: EnergySwitchPolicy(),
    Buddy_Buddy_Poffin: FixedScorePolicy(8000),
    Ultra_Ball: FixedScorePolicy(6000),
    Night_Stretcher: FixedScorePolicy(4800),
    Energy_Retrieval: FixedScorePolicy(6100),
    Max_Rod: FixedScorePolicy(5500),
    Switch: FixedScorePolicy(2500),
    Canari: FixedScorePolicy(5900),
    Levincia: FixedScorePolicy(8500),
}


# ==================== PLAYオプションのスコアリング ====================
def _score_play_option(obs, o, my_index: int, fs: FieldState, my_state, plan: AttackPlan) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]

    if data.cardType == CardType.POKEMON:
        return 20000

    policy = TRAINER_CARD_POLICIES.get(card.id)
    if policy is None:
        return 1000

    ctx = PlayScoringContext(obs=obs, o=o, my_index=my_index, fs=fs, my_state=my_state, plan=plan)
    return policy.play_score(ctx)


# ==================== CARDオプションのスコアリング ====================
def _score_setup_active(card_id: int) -> int:
    """OptionType.CARD / SelectContext.SETUP_ACTIVE_POKEMON のスコアを返す"""
    line = POKEMON_LINES.get(card_id)
    return line.setup_active_priority if line else 0


def _is_attack_ready(card_id: int, energy_count: int) -> bool:
    """このポケモンが今すぐ攻撃可能な技を持つか（ATTACKERSテーブルの再利用）"""
    for atk in ATTACKERS:
        if atk.id != card_id:
            continue
        if energy_count < atk.energy_required:
            continue
        return True
    return False


def _score_switch_target(card, o, my_index: int, plan: AttackPlan) -> int:
    """OptionType.CARD / SelectContext.SWITCH・TO_ACTIVE のスコアを返す"""
    if not isinstance(card, Pokemon):
        # 当該コンテキストは仕様上Pokemonしか提示されないが、
        # 想定外のCard型が来た場合にcard.hp/card.energies参照でAttributeError落ちしないための防御
        # （grimmsnarl_agentのisinstanceガードと同じスタイル）
        return 0
    if o.playerIndex != my_index:
        # ボスの指令：現在の攻撃プラン(plan.damage)で確定KOできるベンチを最優先、次に低HP
        score = -card.hp
        if plan.attacker_id != -1 and plan.damage >= card.hp:
            score += 100000
        return score
    # 自分の交代先／強制昇格先
    energy_count = len(card.energies)
    score = energy_count * 10
    if _is_attack_ready(card.id, energy_count):
        score += 5000
    return score


def _score_search_candidate(card_id: int, fs: FieldState) -> int:
    """OptionType.CARD / SelectContext.TO_HAND・TO_BENCH のスコアを返す"""
    line = POKEMON_LINES.get(card_id)
    if line is not None:
        owned = fs.field_counts[card_id] + fs.hand_counts[card_id]
        if owned >= line.max_field_copies:
            return -1000  # もう十分
        score = 300
        if line.pre_evo_id is not None and fs.field_counts[line.pre_evo_id] == 0:
            score -= 200  # 進化前が場にいないなら優先度を下げる
        return score
    if card_id == Basic_Lightning_Energy:
        return 150
    return 0


def _score_discard_candidate(card_id: int, fs: FieldState) -> int:
    """OptionType.CARD / SelectContext.DISCARD のスコアを返す"""
    line = POKEMON_LINES.get(card_id)
    if line is not None:
        owned = fs.field_counts[card_id] + fs.hand_counts[card_id]
        return 50 if owned > line.max_field_copies else -300
    if card_id == Basic_Lightning_Energy:
        return 30 if fs.hand_counts[Basic_Lightning_Energy] >= 3 else -50
    if card_id == Basic_Fighting_Energy:
        return -100  # 希少なので温存
    if card_id in (Boss_Orders, Lillie_Determination, Max_Rod):
        return -200  # キーカード・ACE SPECは温存
    return 10


def _score_card_option(obs, o, context, my_index: int, fs: FieldState, plan: AttackPlan) -> int:
    """OptionType.CARD のスコアをコンテキスト別に返す"""
    card = get_card(obs, o.area, o.index, o.playerIndex)
    if card is None:
        return 0
    match context:
        case SelectContext.SETUP_ACTIVE_POKEMON:
            return _score_setup_active(card.id)
        case SelectContext.SWITCH | SelectContext.TO_ACTIVE:
            return _score_switch_target(card, o, my_index, plan)
        case SelectContext.TO_HAND | SelectContext.TO_BENCH:
            return _score_search_candidate(card.id, fs)
        case SelectContext.DISCARD:
            return _score_discard_candidate(card.id, fs)
        case SelectContext.ATTACH_FROM:
            return ENERGY_POLICY.switch_destination_score(card)
        case _:
            return 0


def _score_energy_card_option(obs, o, context, my_index: int) -> int:
    """OptionType.ENERGY_CARD のスコアをコンテキスト別に返す"""
    match context:
        case SelectContext.SWITCH_ENERGY_CARD:
            return ENERGY_POLICY.switch_source_score(obs, o, my_index)
        case SelectContext.DISCARD_ENERGY_CARD:
            return ENERGY_POLICY.discard_for_damage_score()
        case _:
            return 0


# ==================== オプション全体のスコアリング ====================
def _score_option(obs, o, context, my_index: int, state, my_state,
                  fs: FieldState, plan: AttackPlan) -> int:
    """1つのオプションにヒューリスティックスコアを付ける"""
    match o.type:
        case OptionType.NUMBER:
            return o.number
        case OptionType.YES:
            return 1
        case OptionType.CARD:
            return _score_card_option(obs, o, context, my_index, fs, plan)
        case OptionType.PLAY:
            return _score_play_option(obs, o, my_index, fs, my_state, plan)
        case OptionType.ATTACH:
            return _score_attach_option(obs, o, my_index)
        case OptionType.EVOLVE:
            return 9000
        case OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if card.id == Iono_Bellibolt_ex:
                return 9500  # エレキストリーマーは常に高優先
            if card.id == Iono_Kilowattrel:
                if fs.hand_has_basic_lightning_energy:
                    return -1  # 手札にまだ雷エネがあるなら伸ばせる見込みがあるため自滅ループ防止で温存
                consumption = _flashing_draw_consumption(my_state, fs.hand_counts)
                return 8000 if consumption <= _safe_draws(my_state) else -1
            return -1
        case OptionType.ENERGY_CARD:
            return _score_energy_card_option(obs, o, context, my_index)
        case OptionType.RETREAT:
            return -1
        case OptionType.ATTACK:
            return 10000 if o.attackId == plan.attack_id else 100
        case _:
            return 0


# ==================== メインエージェント ====================
def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG エージェント（ジャモライコ）。

    Returns:
        list[int]: 選択するオプションのインデックスリスト
    """
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return _load_deck()

    _build_card_table()
    _build_attack_table()

    state    = obs.current
    select   = obs.select
    context  = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]

    fs = _collect_field_state(my_state)

    my_active = my_state.active[0] if my_state.active else None
    op_active_hp = op_state.active[0].hp if op_state.active and op_state.active[0] is not None else 10000
    plan = calc_attack_plan(my_active, op_active_hp, fs, my_state)

    scores = [
        _score_option(obs, o, context, my_index, state, my_state, fs, plan)
        for o in select.option
    ]

    desc_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return desc_indices[:select.maxCount]
