import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, all_attack, to_observation_class,
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
Energy_Search           = 1119  # エネルギー転送（山札から基本エネルギー1枚サーチ）
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


# ==================== フィールド状態 ====================
@dataclass
class FieldState:
    field_counts: defaultdict
    hand_counts: defaultdict
    discard_counts: defaultdict
    iono_lightning_on_board: int
    own_board_basic_energy_total: int
    active_energy_count: int


def _collect_field_state(my_state) -> FieldState:
    """バトル場・ベンチ・手札・捨て山のカード枚数と、
    チェインボルト/きょくらいごうのダメージ計算に必要なエネルギー集計を返す。

    own_board_basic_energy_total は雷・闘の基本エネルギーのみを数える
    （本デッキは基本エネルギー2種のみ採用のためv1はこれで正確）。
    """
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)
    iono_lightning_on_board = 0
    own_board_basic_energy_total = 0
    active_energy_count = 0

    active = my_state.active[0] if my_state.active else None

    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        field_counts[card.id] += 1
        lightning = card.energies.count(EnergyType.LIGHTNING)
        fighting  = card.energies.count(EnergyType.FIGHTING)
        if card.id in IONO_POKEMON_IDS:
            iono_lightning_on_board += lightning
        own_board_basic_energy_total += lightning + fighting

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
        own_board_basic_energy_total=own_board_basic_energy_total,
        active_energy_count=active_energy_count,
    )


# ==================== アタッカーテーブル ====================
@dataclass(frozen=True)
class Attacker:
    id: int
    attack_name: str
    energy_required: int
    damage_fn: Callable[[FieldState], int]
    locks_next_turn: bool = False
    is_utility: bool = False


ATTACKERS: list[Attacker] = [
    Attacker(id=Iono_Voltorb, attack_name="Voltaic Chain", energy_required=2,
             damage_fn=lambda fs: 20 + 20 * fs.iono_lightning_on_board),
    Attacker(id=Iono_Bellibolt_ex, attack_name="Thunderous Bolt", energy_required=4,
             damage_fn=lambda fs: 230, locks_next_turn=True),
    Attacker(id=Iono_Kilowattrel, attack_name="Mach Bolt", energy_required=3,
             damage_fn=lambda fs: 70),
    Attacker(id=Raging_Bolt_ex, attack_name="Bellowing Thunder", energy_required=2,
             damage_fn=lambda fs: 70 * fs.own_board_basic_energy_total),
    Attacker(id=Raging_Bolt_ex, attack_name="Burst Roar", energy_required=1,
             damage_fn=lambda fs: 0, is_utility=True),
]


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
    1. 確定KOできる技があれば、場のエネルギーを消費しない技を優先
       （きょくらいごうは他に確定KO手段がない場合のみ使用）
    2. 確定KOがなければ最大ダメージを選ぶが、次ターン技封じの技は減点評価
    3. はじけるほうこう（is_utility）はダメージ0のため、
       他に使える技がない場合のみ自然に選ばれる
    """
    if my_active is None:
        return AttackPlan()

    candidates = []
    for atk in ATTACKERS:
        if atk.id != my_active.id:
            continue
        if fs.active_energy_count < atk.energy_required:
            continue
        if atk.is_utility and 6 > _safe_draws(my_state):
            continue  # 山札温存（Task 6で_safe_drawsを実装）
        damage = atk.damage_fn(fs)
        is_lethal = (not atk.is_utility) and damage >= op_active_hp
        candidates.append((atk, damage, is_lethal))

    if not candidates:
        return AttackPlan()

    lethal = [c for c in candidates if c[2]]
    if lethal:
        # テーブル上、同一ポケモンが同時に2つ以上の確定KO可能技を持つことはない
        # （タケルライコexのはじけるほうこうはダメージ0固定でis_lethalに絶対ならない）ため、
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
    my_index = state.yourIndex

    # Task 3以降でスコアリングを追加するまでは先頭を返す暫定実装
    return list(range(select.minCount))
