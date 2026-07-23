# tests/test_dragapult_agent.py
import pytest
from collections import defaultdict
from dataclasses import dataclass, field as dc_field

from cg.api import CardType, State

import dragapult_agent.main as dm


@dataclass
class _MockCardData:
    cardId: int
    cardType: CardType = CardType.BASIC_ENERGY


@dataclass
class _MockPokemon:
    id: int
    energies: list = dc_field(default_factory=list)
    energyCards: list = dc_field(default_factory=list)


def test_attach_score_active_gets_priority_when_bench_attacker_ready_and_zero_energy():
    """energy_count=0・active=True・bench_attackerありなら+400点される既存挙動を維持"""
    card_table = {dm.Basic_Fire_Energy: _MockCardData(cardId=dm.Basic_Fire_Energy)}
    pokemon = _MockPokemon(id=dm.Dragapult_ex)
    score = dm._attach_score(
        dm.Basic_Fire_Energy, pokemon, True,
        card_table=card_table, can_switch=False, bench_attacker=True,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert score == 20000 + 400


def test_attach_score_returns_minus_one_for_bench_pokemon_with_full_energy():
    """energy_count>=2かつactive=Falseの控えポケモンには、これ以上エネルギーを
    貼る意味がないため-1（非採用）を返す既存挙動を維持"""
    card_table = {dm.Basic_Fire_Energy: _MockCardData(cardId=dm.Basic_Fire_Energy)}
    pokemon = _MockPokemon(id=dm.Dragapult_ex, energies=[1, 1], energyCards=[
        _MockCardData(cardId=dm.Basic_Fire_Energy)])
    score = dm._attach_score(
        dm.Basic_Fire_Energy, pokemon, False,
        card_table=card_table, can_switch=False, bench_attacker=False,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert score == -1


def test_attach_score_topping_up_non_priority_bench_pokemon_is_not_worse_than_fresh():
    """energy_count==1の控えポケモン（ドラパルトex・ドレディア以外）への追加装着は、
    energy_count==0の個体への新規着手と同等以上のスコアであるべき。
    2026-07-22の実ログ検証(20戦・77件のベンチ向け装着イベント中4件)で、
    energy1個体への追加装着が常にenergy0個体への新規着手より不利
    (-200 vs +50)に評価され、結果として「1エネルギー投資済みの個体を
    2エネルギー＝攻撃可能状態まで伸ばす」より「新規個体への着手」を
    常に優先してしまう非対称バグが発覚（docs/analyses/20260722-dragapult-attach-scoring-verified.md）。
    energy_count==1の非優先種族に対する一律ペナルティを撤廃し、
    energy_count==0と同じ+50点にする"""
    card_table = {
        dm.Basic_Fire_Energy: _MockCardData(cardId=dm.Basic_Fire_Energy),
        dm.Basic_Psychic_Energy: _MockCardData(cardId=dm.Basic_Psychic_Energy),
    }
    @dataclass
    class _MockEnergyCard:
        id: int

    already_attached = _MockEnergyCard(id=dm.Basic_Fire_Energy)

    topped_up = _MockPokemon(id=dm.Drakloak, energies=[1], energyCards=[already_attached])
    fresh = _MockPokemon(id=dm.Drakloak, energies=[], energyCards=[])

    topped_up_score = dm._attach_score(
        dm.Basic_Psychic_Energy, topped_up, False,
        card_table=card_table, can_switch=False, bench_attacker=False,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    fresh_score = dm._attach_score(
        dm.Basic_Psychic_Energy, fresh, False,
        card_table=card_table, can_switch=False, bench_attacker=False,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert topped_up_score >= fresh_score


def test_boss_orders_score_confirmed_pull_target():
    """確定的な引き剥がし先がある場合は最優先スコア"""
    assert dm._boss_orders_score(has_pull_target=True, explore_roll=0.99, epsilon=0.28) == 60000


def test_boss_orders_score_exploratory_use_within_epsilon():
    """確定的な引き剥がし先が無くても、乱数がepsilon未満なら探索的に先出しする"""
    assert dm._boss_orders_score(has_pull_target=False, explore_roll=0.1, epsilon=0.28) == 30000


def test_boss_orders_score_conserve_outside_epsilon():
    """確定的な引き剥がし先が無く、乱数もepsilon以上なら温存（0点）"""
    assert dm._boss_orders_score(has_pull_target=False, explore_roll=0.5, epsilon=0.28) == 0


def test_boss_orders_score_boundary_is_exclusive():
    """explore_roll == epsilon ちょうどは温存側（lucario_agentのrng.random() < EPSILONと同じ境界）"""
    assert dm._boss_orders_score(has_pull_target=False, explore_roll=0.28, epsilon=0.28) == 0


def test_own_switch_target_score_dragapult_ex_beats_budew_even_without_bench_attacker():
    """強制入場時のみスボミーへ+100000を与える分岐を削除した後、
    Dragapult_exが常にスボミーより優先されることを確認する回帰テスト。
    2026-07-23、docs/analyses/20260723-dragapult-post-attach-fix-20-games.mdの検証で、
    強制入場時のスボミー優先(旧+100000)が実戦で機能している確証がなく、
    本命アタッカーを出し損ねるリスクの方が明確なため削除した
    （docs/superpowers/specs/2026-07-23-dragapult-forced-switch-budew-priority-design.md）"""
    dragapult_ex_score = dm._own_switch_target_score(dm.Dragapult_ex, energy_count=0, bench_attacker=False)
    budew_score = dm._own_switch_target_score(dm.Budew, energy_count=0, bench_attacker=False)
    assert dragapult_ex_score > budew_score
    assert dragapult_ex_score == 50000
    assert budew_score == 30000


def test_own_switch_target_score_budew_is_zero_when_bench_attacker_ready():
    """既にベンチに攻撃可能な控えがいる場合、スボミーの優先度は0点になる
    （SelectContext.SWITCHでの既存挙動を維持）"""
    assert dm._own_switch_target_score(dm.Budew, energy_count=0, bench_attacker=True) == 0


def test_own_switch_target_score_existing_priorities_unchanged():
    """Dreepy/Drakloak/フェザンディピティex/ニャースex/未知カードの
    既存優先度が変わっていないことの回帰確認"""
    assert dm._own_switch_target_score(dm.Dreepy, energy_count=0, bench_attacker=False) == 10000
    assert dm._own_switch_target_score(dm.Drakloak, energy_count=1, bench_attacker=False) == 20000
    assert dm._own_switch_target_score(dm.Drakloak, energy_count=0, bench_attacker=False) == -10000
    assert dm._own_switch_target_score(dm.Fezandipiti_ex, energy_count=0, bench_attacker=False) == -1000
    assert dm._own_switch_target_score(dm.Meowth_ex, energy_count=0, bench_attacker=False) == -2000
    assert dm._own_switch_target_score(999999, energy_count=0, bench_attacker=False) == 0


def test_crispin_score_low_when_fire_energy_exhausted_in_deck():
    """アカマツは山札から「ちがうタイプの基本エネルギーを2枚まで」探す効果のため、
    炎エネルギーが山札に0枚だと2種探せず効果が弱まる。この場合は他の状況に関わらず
    低評価(10点)であるべき。修正前は`if`が`elif`になっておらず、この分岐が
    直後のif/elseで無条件に上書きされ死んでいた（main.py:604-611）"""
    deck_counts = defaultdict(int, {dm.Basic_Fire_Energy: 0, dm.Basic_Psychic_Energy: 4})
    field_counts = defaultdict(int, {dm.Dragapult_ex: 1})
    score = dm._crispin_score(
        deck_counts=deck_counts, can_main_attack=False, bench_attacker=False,
        field_counts=field_counts,
    )
    assert score == 10


def test_crispin_score_low_when_psychic_energy_exhausted_in_deck():
    """炎エネルギー側と対称に、超エネルギーが山札に0枚の場合も低評価(10点)"""
    deck_counts = defaultdict(int, {dm.Basic_Fire_Energy: 4, dm.Basic_Psychic_Energy: 0})
    field_counts = defaultdict(int, {dm.Dragapult_ex: 1})
    score = dm._crispin_score(
        deck_counts=deck_counts, can_main_attack=False, bench_attacker=False,
        field_counts=field_counts,
    )
    assert score == 10


def test_crispin_score_high_priority_when_energy_available_and_dragapult_ex_needs_it():
    """両タイプが山札に残っており、かつドラパルトexが場にいるのに攻撃準備が
    整っていない（本命技も控えの攻撃可能個体も無い）場合は最優先(55000点)"""
    deck_counts = defaultdict(int, {dm.Basic_Fire_Energy: 2, dm.Basic_Psychic_Energy: 2})
    field_counts = defaultdict(int, {dm.Dragapult_ex: 1})
    score = dm._crispin_score(
        deck_counts=deck_counts, can_main_attack=False, bench_attacker=False,
        field_counts=field_counts,
    )
    assert score == 55000


def test_crispin_score_default_priority_when_already_attack_ready():
    """両タイプが山札に残っていても、既に本命技が撃てる状態なら通常優先度(25000点)"""
    deck_counts = defaultdict(int, {dm.Basic_Fire_Energy: 2, dm.Basic_Psychic_Energy: 2})
    field_counts = defaultdict(int, {dm.Dragapult_ex: 1})
    score = dm._crispin_score(
        deck_counts=deck_counts, can_main_attack=True, bench_attacker=False,
        field_counts=field_counts,
    )
    assert score == 25000


def _make_state(turn: int = 3, supporter_played: bool = False) -> State:
    return State(
        turn=turn, turnActionCount=0, yourIndex=0, firstPlayer=0,
        supporterPlayed=supporter_played, stadiumPlayed=False,
        energyAttached=False, retreated=False, result=-1,
        stadium=[], looking=None, players=[],
    )


def _make_ctx(**overrides) -> dm.PlayTrainerCardContext:
    defaults = dict(
        card_id=0, card_score=0, state=_make_state(), stadium_id=0,
        deck_counts=defaultdict(int), negative_hand_count=0,
        no_draw=False, use_support=0, no_more_dex=False,
    )
    defaults.update(overrides)
    return dm.PlayTrainerCardContext(**defaults)


def test_trainer_card_policy_is_abstract():
    with pytest.raises(TypeError):
        dm.TrainerCardPolicy()


def test_fixed_score_policy_returns_constant():
    policy = dm.FixedScorePolicy(1234)
    assert policy.play_score(_make_ctx()) == 1234


def test_score_play_trainer_card_returns_zero_for_unregistered_card():
    """未登録カードは現行のif/elif連鎖がどれにも一致しない場合のデフォルト値0と一致させる
    （main.py:712の`score = 0  # The default and baseline score is 0.`と同じ）"""
    assert dm._score_play_trainer_card(999999, _make_ctx()) == 0


def test_unfair_stamp_registered():
    assert dm._score_play_trainer_card(dm.Unfair_Stamp, _make_ctx()) == 15000


def test_supporter_selected_policy_scores_when_selected_as_use_support():
    policy = dm.SupporterSelectedPolicy(35000)
    ctx = _make_ctx(card_id=dm.Boss_Orders, use_support=dm.Boss_Orders)
    assert policy.play_score(ctx) == 35000


def test_supporter_selected_policy_returns_minus_one_when_not_selected():
    policy = dm.SupporterSelectedPolicy(35000)
    ctx = _make_ctx(card_id=dm.Boss_Orders, use_support=dm.Lillie_Determination)
    assert policy.play_score(ctx) == -1


def test_supporter_selected_policy_no_draw_gate_suppresses_even_when_selected():
    """no_draw_gate=Trueの場合、use_supportと一致していてもno_draw中は-1
    （現行のelif no_draw連鎖でCrispin/Brock_Scoutingが受けている暗黙の副作用を明示化）"""
    policy = dm.SupporterSelectedPolicy(35000, no_draw_gate=True)
    ctx = _make_ctx(card_id=dm.Crispin, use_support=dm.Crispin, no_draw=True)
    assert policy.play_score(ctx) == -1


def test_supporter_selected_policy_without_gate_ignores_no_draw():
    policy = dm.SupporterSelectedPolicy(35000)
    ctx = _make_ctx(card_id=dm.Boss_Orders, use_support=dm.Boss_Orders, no_draw=True)
    assert policy.play_score(ctx) == 35000


def test_boss_orders_and_lillie_determination_registered():
    assert dm._score_play_trainer_card(
        dm.Boss_Orders, _make_ctx(card_id=dm.Boss_Orders, use_support=dm.Boss_Orders)
    ) == 35000
    assert dm._score_play_trainer_card(
        dm.Lillie_Determination, _make_ctx(card_id=dm.Lillie_Determination, use_support=dm.Lillie_Determination)
    ) == 14000


def test_rare_candy_policy_unnecessary_when_no_more_dex():
    policy = dm.RareCandyPolicy()
    assert policy.play_score(_make_ctx(no_more_dex=True)) == -1


def test_rare_candy_policy_high_priority_otherwise():
    policy = dm.RareCandyPolicy()
    assert policy.play_score(_make_ctx(no_more_dex=False)) == 75000


def test_rare_candy_registered():
    assert dm._score_play_trainer_card(dm.Rare_Candy, _make_ctx(no_more_dex=False)) == 75000


def test_night_stretcher_policy_plays_when_card_score_meets_threshold():
    policy = dm.NightStretcherPolicy()
    assert policy.play_score(_make_ctx(card_score=18000)) == 42000


def test_night_stretcher_policy_holds_below_threshold():
    policy = dm.NightStretcherPolicy()
    assert policy.play_score(_make_ctx(card_score=17999)) == -1


def test_night_stretcher_registered():
    assert dm._score_play_trainer_card(dm.Night_Stretcher, _make_ctx(card_score=20000)) == 42000


def test_buddy_buddy_poffin_policy_plays_when_dreepy_in_deck():
    policy = dm.BuddyBuddyPoffinPolicy()
    ctx = _make_ctx(deck_counts=defaultdict(int, {dm.Dreepy: 1}))
    assert policy.play_score(ctx) == 46000


def test_buddy_buddy_poffin_policy_holds_when_no_dreepy_in_deck():
    policy = dm.BuddyBuddyPoffinPolicy()
    ctx = _make_ctx(deck_counts=defaultdict(int))
    assert policy.play_score(ctx) == -1


def test_buddy_buddy_poffin_policy_suppressed_by_no_draw():
    policy = dm.BuddyBuddyPoffinPolicy()
    ctx = _make_ctx(deck_counts=defaultdict(int, {dm.Dreepy: 1}), no_draw=True)
    assert policy.play_score(ctx) == -1


def test_ultra_ball_policy_plays_when_two_or_more_negative_cards():
    policy = dm.UltraBallPolicy()
    assert policy.play_score(_make_ctx(negative_hand_count=2)) == 44000


def test_ultra_ball_policy_holds_below_threshold():
    policy = dm.UltraBallPolicy()
    assert policy.play_score(_make_ctx(negative_hand_count=1)) == -1


def test_ultra_ball_policy_suppressed_by_no_draw():
    policy = dm.UltraBallPolicy()
    assert policy.play_score(_make_ctx(negative_hand_count=2, no_draw=True)) == -1


def test_poke_pad_policy_plays_when_dreepy_or_drakloak_in_deck():
    policy = dm.PokePadPolicy()
    ctx = _make_ctx(deck_counts=defaultdict(int, {dm.Drakloak: 1}))
    assert policy.play_score(ctx) == 45000


def test_poke_pad_policy_holds_when_neither_in_deck():
    policy = dm.PokePadPolicy()
    ctx = _make_ctx(deck_counts=defaultdict(int))
    assert policy.play_score(ctx) == -1


def test_poke_pad_policy_suppressed_by_no_draw():
    policy = dm.PokePadPolicy()
    ctx = _make_ctx(deck_counts=defaultdict(int, {dm.Dreepy: 1}), no_draw=True)
    assert policy.play_score(ctx) == -1


def test_no_draw_gated_cards_registered():
    assert dm._score_play_trainer_card(
        dm.Buddy_Buddy_Poffin, _make_ctx(deck_counts=defaultdict(int, {dm.Dreepy: 1}))
    ) == 46000
    assert dm._score_play_trainer_card(
        dm.Ultra_Ball, _make_ctx(negative_hand_count=2)
    ) == 44000
    assert dm._score_play_trainer_card(
        dm.Poke_Pad, _make_ctx(deck_counts=defaultdict(int, {dm.Drakloak: 1}))
    ) == 45000
    assert dm._score_play_trainer_card(
        dm.Crispin, _make_ctx(card_id=dm.Crispin, use_support=dm.Crispin)
    ) == 35000
    # no_drawが真なら、use_supportと一致していてもCrispinは-1
    assert dm._score_play_trainer_card(
        dm.Crispin, _make_ctx(card_id=dm.Crispin, use_support=dm.Crispin, no_draw=True)
    ) == -1


def test_trainer_card_policies_cover_exactly_the_migrated_card_set():
    """現行TRAINER_CARD_POLICIESに登録されているカードと過不足なく一致することを保証する"""
    expected = {
        dm.Rare_Candy, dm.Unfair_Stamp, dm.Night_Stretcher,
        dm.Boss_Orders, dm.Lillie_Determination,
        dm.Buddy_Buddy_Poffin, dm.Ultra_Ball, dm.Poke_Pad, dm.Crispin,
    }
    assert set(dm.TRAINER_CARD_POLICIES.keys()) == expected


import importlib.util
from pathlib import Path


def _load_deck_module():
    deck_path = Path(__file__).resolve().parents[1] / "decks" / "dragapult_20260721.py"
    spec = importlib.util.spec_from_file_location("dragapult_deck", deck_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deck_totals_exactly_sixty_cards():
    deck_module = _load_deck_module()
    assert sum(count for _, count in deck_module.DECK) == 60


def test_deck_has_no_duplicate_card_ids():
    deck_module = _load_deck_module()
    card_ids = [card_id for card_id, _ in deck_module.DECK]
    assert len(card_ids) == len(set(card_ids))


def test_deck_ace_spec_limit_is_one():
    """ACE SPECカード(Unfair_Stamp)は1枚制限を遵守する"""
    deck_module = _load_deck_module()
    counts = dict(deck_module.DECK)
    assert counts[dm.Unfair_Stamp] == 1
