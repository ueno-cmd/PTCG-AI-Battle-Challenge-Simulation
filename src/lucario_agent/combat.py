"""ルカリオexエージェントの戦闘意思決定ロジック（エネルギー配分・攻撃プラン計算）"""
import random
from dataclasses import dataclass

from cg.api import EnergyType, Pokemon

from lucario_agent.constants import (
    Lunatone, Solrock, Riolu, Mega_Lucario_ex, Ogerpon_ex,
    Basic_Fighting_Energy, Rock_Fighting_Energy, Nighttime_Mine,
    EX_DAMAGE_NULLIFIER_IDS,
)

EPSILON = 0.28  # 温存判断時に探索的先出しをする確率
_rng    = random.Random()  # 本番用の実乱数。テストではスタブを注入する


@dataclass
class AttackPlan:
    attacker:     int  = -1
    target:       int  = -1
    attack_index: int  = -1
    remain_hp:    int  = -1
    energy:       bool = False


def prize_count(pokemon: Pokemon, card_table: dict) -> int:
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


def pokemon_score(pokemon: Pokemon, card_table: dict) -> int:
    """対象ポケモンの戦術的価値をヒューリスティックに評価する"""
    data  = card_table[pokemon.id]
    score = prize_count(pokemon, card_table) * 1000
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


def energy_score(pokemon: Pokemon, active: bool, attacker1: bool, op_active_nullifies_ex: bool = False) -> int:
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
        if op_active_nullifies_ex:
            score -= 150  # 相手がex無効化持ちならOgerpon_ex/Solrockへ道を譲る
    elif pokemon.id == Ogerpon_ex:
        if energy_count < 3:
            score += 80
        if attacker1:
            score += 40  # ルカリオ確保済みなら余剰エネルギーをオーガポンexへ
        if op_active_nullifies_ex:
            score += 150  # 相手がex無効化持ちならメガルカリオex系より優先してエネルギーを回す
    return score


def _tera_stadium_cost_bonus(pokemon_id: int, stadium_id: int, card_table: dict) -> int:
    """Nighttime Mine下でテラスタルポケモンが支払う追加コストを返す"""
    if stadium_id == Nighttime_Mine and card_table[pokemon_id].tera:
        return 1
    return 0


def _calc_attack_damage(attacker_id: int, base_damage: int, defender_id: int, defender_data, card_table: dict) -> int:
    """弱点・抵抗力・ex技無効化ポケモンの特性を考慮した実ダメージを1箇所で計算する"""
    damage = base_damage
    attack_ignores_defender_effects = attacker_id == Ogerpon_ex  # ぶちやぶる：相手にかかっている効果を計算しない
    if not attack_ignores_defender_effects:
        if defender_data.weakness == EnergyType.FIGHTING:
            damage *= 2
        elif defender_data.resistance == EnergyType.FIGHTING:
            damage -= 30

    attacker_is_ex = card_table[attacker_id].ex or card_table[attacker_id].megaEx
    defender_nullifies_ex_damage = (
        not attack_ignores_defender_effects  # ぶちやぶるは無効化を貫通するため対象外
        and defender_id in EX_DAMAGE_NULLIFIER_IDS
        and attacker_is_ex
    )
    if defender_nullifies_ex_damage:
        damage = 0  # Crustle/Sylveonの特性：相手のポケモンexの技ダメージを無効化する

    return damage


def calc_attack_plan(
    obs,
    my_state,
    op_state,
    state,
    field_counts,
    hand_counts,
    discard_counts,
    can_switch: bool,
    can_op_switch: bool,
    can_use_mega_brave: bool,
    can_attack: bool,
    my_prize: int,
    card_table: dict,
    stadium_id: int = 0,
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

            energy_required += _tera_stadium_cost_bonus(my_pokemon.id, stadium_id, card_table)

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
                damage = _calc_attack_damage(my_pokemon.id, base_damage, op_pokemon.id, data, card_table)

                prize = 0
                score = pokemon_score(op_pokemon, card_table)
                if op_pokemon.hp <= damage:
                    prize = prize_count(op_pokemon, card_table)
                else:
                    score *= damage / op_pokemon.hp
                score += base_score

                is_mega_brave_choice = my_pokemon.id == Mega_Lucario_ex and a == 1
                if is_mega_brave_choice:
                    base_dmg_normal = _calc_attack_damage(my_pokemon.id, 130, op_pokemon.id, data, card_table)
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


def _score_retreat_option(current_plan: AttackPlan) -> int:
    """OptionType.RETREAT のスコアを返す"""
    return 2000 if current_plan.attacker >= 1 else -1


def _score_attack_option_choice(o, current_plan: AttackPlan) -> int:
    """OptionType.ATTACK のスコアを返す"""
    score = 1000
    if current_plan.attack_index == 1:
        score += 100 if o.attackId == 983 else 0  # Mega Brave 優先
    else:
        score += 0 if o.attackId == 983 else 100
    return score
