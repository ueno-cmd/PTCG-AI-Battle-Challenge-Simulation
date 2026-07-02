import pytest
from dataclasses import dataclass, field
from collections import defaultdict
from cg.api import (
    CardType, Card, AreaType, Observation, State, Option, OptionType, SelectContext,
)

import grimmsnarl_agent.main as gm
from tests.conftest import make_pokemon, make_player_state


@dataclass
class MockCardData:
    cardId:   int
    name:     str      = ""
    ex:       bool     = False
    stage1:   bool     = False
    stage2:   bool     = False
    cardType: CardType = CardType.POKEMON
    attacks:  list     = field(default_factory=list)


@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        gm.Impidimp:        MockCardData(cardId=gm.Impidimp, attacks=[9101]),
        gm.Morgrem:         MockCardData(cardId=gm.Morgrem, stage1=True, attacks=[9101]),
        gm.Grimmsnarl_ex:   MockCardData(cardId=gm.Grimmsnarl_ex, stage2=True, ex=True, attacks=[9102]),
        gm.Munkidori:       MockCardData(cardId=gm.Munkidori, attacks=[9104]),
        gm.Rare_Candy:      MockCardData(cardId=gm.Rare_Candy, cardType=CardType.ITEM),
        gm.Buddy_Buddy_Poffin: MockCardData(cardId=gm.Buddy_Buddy_Poffin, cardType=CardType.ITEM),
        gm.Lillie_Determination: MockCardData(cardId=gm.Lillie_Determination, cardType=CardType.SUPPORTER),
        gm.Team_Rocket_Petrel: MockCardData(cardId=gm.Team_Rocket_Petrel, cardType=CardType.SUPPORTER),
        gm.Basic_D_Energy:  MockCardData(cardId=gm.Basic_D_Energy, cardType=CardType.BASIC_ENERGY),
    }
    monkeypatch.setattr(gm, "card_table", table)
    monkeypatch.setattr(gm, "Shadow_Bullet_ID", 9102)
    return table


# ==================== _collect_field_state ====================
class TestCollectFieldState:
    def test_grimmsnarl_active_detected(self):
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, energies=[7, 7])
        my_ps = make_player_state(active_pokemon=grimmsnarl)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.grimmsnarl_active is True
        assert fs.grimmsnarl_energy_count == 2

    def test_grimmsnarl_not_active_when_absent(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Impidimp))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.grimmsnarl_active is False
        assert fs.grimmsnarl_energy_count == 0

    def test_impidimp_bench_detected(self):
        impidimp = make_pokemon(id=gm.Impidimp)
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=999),
            bench=[impidimp],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.impidimp_bench_idx == 0

    def test_impidimp_bench_absent_returns_minus1(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=999))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.impidimp_bench_idx == -1

    def test_munkidori_bench_detected(self):
        munkidori = make_pokemon(id=gm.Munkidori, energies=[7])
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex),
            bench=[munkidori],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.munkidori_bench_idx == 0

    def test_rare_candy_in_hand_detected(self):
        candy = Card(id=gm.Rare_Candy, serial=1, playerIndex=0)
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Impidimp),
            hand=[candy],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.rare_candy_in_hand is True

    def test_op_active_hp(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=180))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.op_active_hp == 180

    def test_op_bench_hp_list(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex))
        op_bench = [make_pokemon(id=2, hp=30), make_pokemon(id=3, hp=90)]
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200), bench=op_bench)
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.op_bench_hp == [30, 90]

    def test_hand_with_none_entry_does_not_crash(self):
        """手札にNoneが含まれていても_collect_field_stateがクラッシュしないこと"""
        real_card = Card(id=gm.Rare_Candy, serial=1, playerIndex=0)
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex),
            hand=[None, real_card],  # Noneと実カードが混在
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        # クラッシュしないこと、および実カードがカウントされることを確認
        assert fs.hand_counts[gm.Rare_Candy] == 1

    def test_discard_with_none_entry_does_not_crash(self):
        """トラッシュにNoneが含まれていても_collect_field_stateがクラッシュしないこと"""
        real_card = Card(id=gm.Basic_D_Energy, serial=1, playerIndex=0)
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex),
            discard=[None, real_card],  # Noneと実カードが混在
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        # クラッシュしないこと、および実カードがカウントされることを確認
        assert fs.discard_counts[gm.Basic_D_Energy] == 1


# ==================== _score_play ====================
class TestScorePlay:
    def _make_fs(self, **kwargs):
        defaults = dict(
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int),
            discard_counts=defaultdict(int),
            grimmsnarl_active=False,
            grimmsnarl_energy_count=0,
            impidimp_bench_idx=-1,
            munkidori_bench_idx=-1,
            rare_candy_in_hand=False,
            my_active_hp=200,
            op_active_hp=200,
            op_bench_hp=[],
        )
        defaults.update(kwargs)
        return gm.FieldState(**defaults)

    def test_rare_candy_high_when_impidimp_on_field_and_grimmsnarl_in_hand(self):
        fc = defaultdict(int, {gm.Impidimp: 1})
        hc = defaultdict(int, {gm.Grimmsnarl_ex: 1, gm.Rare_Candy: 1})
        fs = self._make_fs(field_counts=fc, hand_counts=hc, rare_candy_in_hand=True)
        assert gm._score_play(gm.Rare_Candy, fs, prize_count=6) == 9000

    def test_rare_candy_low_when_grimmsnarl_not_in_hand(self):
        fc = defaultdict(int, {gm.Impidimp: 1})
        hc = defaultdict(int, {gm.Rare_Candy: 1})
        fs = self._make_fs(field_counts=fc, hand_counts=hc, rare_candy_in_hand=True)
        assert gm._score_play(gm.Rare_Candy, fs, prize_count=6) == -1

    def test_buddy_buddy_poffin_high_when_bench_targets_missing(self):
        fs = self._make_fs()
        assert gm._score_play(gm.Buddy_Buddy_Poffin, fs, prize_count=6) == 8000

    def test_buddy_buddy_poffin_low_when_bench_targets_present(self):
        fs = self._make_fs(impidimp_bench_idx=0, munkidori_bench_idx=1)
        assert gm._score_play(gm.Buddy_Buddy_Poffin, fs, prize_count=6) == 2000

    def test_team_rocket_petrel_score(self):
        """Team Rocket's PetrelはDawnの後継として進化ライン探索を担うため高優先度"""
        fs = self._make_fs()
        assert gm._score_play(gm.Team_Rocket_Petrel, fs, prize_count=6) == 7000

    def test_lillie_determination_first_turn(self):
        fs = self._make_fs()
        assert gm._score_play(gm.Lillie_Determination, fs, prize_count=6) == 5000

    def test_unhandled_card_returns_default(self):
        fs = self._make_fs()
        assert gm._score_play(9999, fs, prize_count=4) == 1000

    def test_boss_orders_high_when_ko_target_exists(self):
        fs = self._make_fs(op_bench_hp=[150, 300])
        assert gm._score_play(gm.Boss_Orders, fs, prize_count=4) == 8800

    def test_boss_orders_holds_when_no_ko_target_and_rng_above_epsilon(self):
        fs = self._make_fs(op_bench_hp=[300])

        class StubRng:
            def random(self):
                return 0.9  # >= EPSILON(0.28) なので温存

        assert gm._score_play(gm.Boss_Orders, fs, prize_count=4, rng=StubRng()) == -1

    def test_boss_orders_explores_when_rng_below_epsilon(self):
        fs = self._make_fs(op_bench_hp=[300])

        class StubRng:
            def random(self):
                return 0.1  # < EPSILON(0.28) なので探索的先出し

        assert gm._score_play(gm.Boss_Orders, fs, prize_count=4, rng=StubRng()) == 6000

    def test_boss_orders_holds_when_bench_empty_even_if_rng_favors_explore(self):
        fs = self._make_fs(op_bench_hp=[])

        class StubRng:
            def random(self):
                return 0.0  # 最も探索されやすい値でも対象不在なら温存

        assert gm._score_play(gm.Boss_Orders, fs, prize_count=4, rng=StubRng()) == -1


# ==================== _score_attach ====================
class TestScoreAttach:
    def test_basic_d_energy_to_grimmsnarl_low_energy_preferred(self):
        grimmsnarl_low  = make_pokemon(id=gm.Grimmsnarl_ex, energies=[])
        grimmsnarl_full = make_pokemon(id=gm.Grimmsnarl_ex, energies=[7, 7])
        fs = gm.FieldState(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), grimmsnarl_active=True,
            grimmsnarl_energy_count=0, impidimp_bench_idx=-1,
            munkidori_bench_idx=-1, rare_candy_in_hand=False,
            my_active_hp=200, op_active_hp=200, op_bench_hp=[],
        )
        score_low  = gm._score_attach(grimmsnarl_low,  AreaType.ACTIVE, gm.Basic_D_Energy, fs)
        score_full = gm._score_attach(grimmsnarl_full, AreaType.ACTIVE, gm.Basic_D_Energy, fs)
        assert score_low > score_full

    def test_unhandled_attach_card_returns_default(self):
        """Basic_D_Energy以外のATTACH対象カード（例：Air Balloon等）はデフォルトスコアになる"""
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex)
        fs = gm.FieldState(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), grimmsnarl_active=True,
            grimmsnarl_energy_count=0, impidimp_bench_idx=-1,
            munkidori_bench_idx=-1, rare_candy_in_hand=False,
            my_active_hp=200, op_active_hp=200, op_bench_hp=[],
        )
        assert gm._score_attach(grimmsnarl, AreaType.ACTIVE, 9999, fs) == 3000


# ==================== _score_attack ====================
class TestScoreAttack:
    def _make_fs(self, op_hp=200, op_bench_hp=None):
        return gm.FieldState(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), grimmsnarl_active=True,
            grimmsnarl_energy_count=2, impidimp_bench_idx=-1,
            munkidori_bench_idx=-1, rare_candy_in_hand=False,
            my_active_hp=200, op_active_hp=op_hp, op_bench_hp=op_bench_hp or [],
        )

    def test_shadow_bullet_non_lethal_score(self):
        fs = self._make_fs(op_hp=300)
        assert gm._score_attack(9102, fs) == 2000  # Shadow_Bullet_ID (mocked)、確定KOでない場合

    def test_shadow_bullet_lethal_scores_higher_than_non_lethal(self):
        """相手バトルポケモンのHPが180以下（確定KO）なら、非確定KO時よりスコアが高くなること"""
        fs_lethal     = self._make_fs(op_hp=150)
        fs_non_lethal = self._make_fs(op_hp=300)
        assert gm._score_attack(9102, fs_lethal) > gm._score_attack(9102, fs_non_lethal)

    def test_shadow_bullet_lethal_outranks_retreat_score(self):
        """確定KO時のShadow Bulletスコア（5000）はRETREATのスコア（3000）を上回ること"""
        fs = self._make_fs(op_hp=150)
        assert gm._score_attack(9102, fs) == 5000
        assert gm._score_attack(9102, fs) > 3000  # RETREATのスコア（agent()内でインライン計算）

    def test_unknown_attack_returns_default(self):
        fs = self._make_fs()
        assert gm._score_attack(9999, fs) == 1000


# ==================== _score_card_option ====================
class TestScoreCardOption:
    """OptionType.CARD のコンテキスト別スコアリングを検証する"""

    def _make_fs(self, **kwargs):
        defaults = dict(
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int),
            discard_counts=defaultdict(int),
            grimmsnarl_active=False,
            grimmsnarl_energy_count=0,
            impidimp_bench_idx=-1,
            munkidori_bench_idx=-1,
            rare_candy_in_hand=False,
            my_active_hp=200,
            op_active_hp=200,
            op_bench_hp=[],
        )
        defaults.update(kwargs)
        return gm.FieldState(**defaults)

    def _make_obs(self, my_ps, op_ps):
        """playerIndex=0がmy_ps、playerIndex=1がop_psとなるObservationを生成する"""
        return Observation(
            select=None,
            logs=[],
            current=State(
                turn=1, turnActionCount=0, yourIndex=0, firstPlayer=0,
                supporterPlayed=False, stadiumPlayed=False, energyAttached=False,
                retreated=False, result=-1, stadium=[], looking=None,
                players=[my_ps, op_ps],
            ),
        )

    # ---------- SETUP_ACTIVE_POKEMON ----------
    def test_setup_active_pokemon_priority_order(self):
        impidimp = make_pokemon(id=gm.Impidimp)
        other    = make_pokemon(id=999, hp=100)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), hand=[impidimp, other])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()

        def score(idx):
            o = Option(type=OptionType.CARD, area=AreaType.HAND, index=idx, playerIndex=0)
            return gm._score_card_option(obs, o, SelectContext.SETUP_ACTIVE_POKEMON, 0, fs, defaultdict(int))

        assert score(0) > score(1)  # Impidimp > その他

    # ---------- SWITCH / TO_ACTIVE ----------
    def test_switch_returns_zero_when_not_my_card(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1))
        op_ps = make_player_state(
            active_pokemon=make_pokemon(id=2, hp=200),
            bench=[make_pokemon(id=gm.Grimmsnarl_ex, energies=[7, 7])],
        )
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=1)  # 相手のカード
        score = gm._score_card_option(obs, o, SelectContext.SWITCH, 0, fs, defaultdict(int))
        assert score == 0

    def test_switch_returns_zero_when_not_pokemon(self):
        non_pokemon_card = Card(id=gm.Basic_D_Energy, serial=1, playerIndex=0)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), bench=[non_pokemon_card])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        score = gm._score_card_option(obs, o, SelectContext.SWITCH, 0, fs, defaultdict(int))
        assert score == 0

    def test_switch_grimmsnarl_scores_higher_than_other_pokemon(self):
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, energies=[7, 7])
        other      = make_pokemon(id=999, energies=[])
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), bench=[grimmsnarl, other])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o_grimmsnarl = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        o_other      = Option(type=OptionType.CARD, area=AreaType.BENCH, index=1, playerIndex=0)
        score_grimmsnarl = gm._score_card_option(obs, o_grimmsnarl, SelectContext.SWITCH, 0, fs, defaultdict(int))
        score_other      = gm._score_card_option(obs, o_other, SelectContext.SWITCH, 0, fs, defaultdict(int))
        assert score_grimmsnarl > score_other

    # ---------- TO_ACTIVE（相手ベンチを強制的にバトル場へ出す場合の対象選択） ----------
    def test_to_active_opponent_bench_targets_lowest_hp(self):
        low_hp  = make_pokemon(id=1, hp=40)
        high_hp = make_pokemon(id=2, hp=180)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=3, hp=200), bench=[low_hp, high_hp])
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o_low  = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=1)
        o_high = Option(type=OptionType.CARD, area=AreaType.BENCH, index=1, playerIndex=1)
        score_low  = gm._score_card_option(obs, o_low, SelectContext.TO_ACTIVE, 0, fs, defaultdict(int))
        score_high = gm._score_card_option(obs, o_high, SelectContext.TO_ACTIVE, 0, fs, defaultdict(int))
        assert score_low > score_high  # HPが低いほど（KOに近いほど）スコアが高い

    def test_to_active_own_pokemon_still_prefers_grimmsnarl(self):
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, energies=[7, 7])
        other      = make_pokemon(id=999, energies=[])
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), bench=[grimmsnarl, other])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o_grimmsnarl = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        o_other      = Option(type=OptionType.CARD, area=AreaType.BENCH, index=1, playerIndex=0)
        score_grimmsnarl = gm._score_card_option(obs, o_grimmsnarl, SelectContext.TO_ACTIVE, 0, fs, defaultdict(int))
        score_other      = gm._score_card_option(obs, o_other, SelectContext.TO_ACTIVE, 0, fs, defaultdict(int))
        assert score_grimmsnarl > score_other

    def test_to_active_non_pokemon_returns_zero(self):
        non_pokemon_card = Card(id=gm.Basic_D_Energy, serial=1, playerIndex=1)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200), bench=[non_pokemon_card])
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=1)
        score = gm._score_card_option(obs, o, SelectContext.TO_ACTIVE, 0, fs, defaultdict(int))
        assert score == 0

    # ---------- TO_BENCH / TO_HAND ----------
    def test_to_bench_grimmsnarl_high_when_none_in_play(self):
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), hand=[grimmsnarl])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs(field_counts=defaultdict(int, {gm.Grimmsnarl_ex: 0}))
        o = Option(type=OptionType.CARD, area=AreaType.HAND, index=0, playerIndex=0)
        score = gm._score_card_option(obs, o, SelectContext.TO_BENCH, 0, fs, defaultdict(int))
        assert score == 100

    def test_to_bench_grimmsnarl_low_when_already_in_play(self):
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), hand=[grimmsnarl])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs(field_counts=defaultdict(int, {gm.Grimmsnarl_ex: 1}))
        o = Option(type=OptionType.CARD, area=AreaType.HAND, index=0, playerIndex=0)
        score = gm._score_card_option(obs, o, SelectContext.TO_BENCH, 0, fs, defaultdict(int))
        assert score == 10

    # ---------- DAMAGE_COUNTER ----------
    def test_damage_counter_targets_lowest_hp(self):
        low_hp  = make_pokemon(id=1, hp=50)
        high_hp = make_pokemon(id=2, hp=150)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=3, hp=200), bench=[low_hp, high_hp])
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o_low  = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=1)
        o_high = Option(type=OptionType.CARD, area=AreaType.BENCH, index=1, playerIndex=1)
        score_low  = gm._score_card_option(obs, o_low, SelectContext.DAMAGE_COUNTER, 0, fs, defaultdict(int))
        score_high = gm._score_card_option(obs, o_high, SelectContext.DAMAGE_COUNTER, 0, fs, defaultdict(int))
        assert score_low > score_high  # HPが低いほど（KOに近いほど）スコアが高い

    def test_damage_counter_non_pokemon_returns_zero(self):
        non_pokemon_card = Card(id=gm.Basic_D_Energy, serial=1, playerIndex=1)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=3, hp=200), bench=[non_pokemon_card])
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=1)
        score = gm._score_card_option(obs, o, SelectContext.DAMAGE_COUNTER, 0, fs, defaultdict(int))
        assert score == 0

    # ---------- DISCARD ----------
    def test_discard_key_cards_score_lower_than_basic_energy(self):
        grimmsnarl_card = Card(id=gm.Grimmsnarl_ex, serial=1, playerIndex=0)
        energy_card     = Card(id=gm.Basic_D_Energy, serial=2, playerIndex=0)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), discard=[grimmsnarl_card, energy_card])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o_grimmsnarl = Option(type=OptionType.CARD, area=AreaType.DISCARD, index=0, playerIndex=0)
        o_energy     = Option(type=OptionType.CARD, area=AreaType.DISCARD, index=1, playerIndex=0)
        score_grimmsnarl = gm._score_card_option(obs, o_grimmsnarl, SelectContext.DISCARD, 0, fs, defaultdict(int))
        score_energy     = gm._score_card_option(obs, o_energy, SelectContext.DISCARD, 0, fs, defaultdict(int))
        assert score_grimmsnarl < score_energy  # 主力カードは温存したいので低スコア

    def test_discard_bonus_and_count_decrement_side_effect(self):
        """discard_hand_counts>=2のボーナスと、呼び出し後のデクリメント副作用を検証する"""
        energy_card = Card(id=gm.Basic_D_Energy, serial=1, playerIndex=0)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), discard=[energy_card])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o = Option(type=OptionType.CARD, area=AreaType.DISCARD, index=0, playerIndex=0)
        dhc = defaultdict(int, {gm.Basic_D_Energy: 2})

        score_first = gm._score_card_option(obs, o, SelectContext.DISCARD, 0, fs, dhc)
        assert score_first == 130  # base(30) + ">=2"ボーナス(100)
        assert dhc[gm.Basic_D_Energy] == 1  # 呼び出し後にデクリメントされている

        score_second = gm._score_card_option(obs, o, SelectContext.DISCARD, 0, fs, dhc)
        assert score_second == 30  # 残数1になりボーナス対象外に戻る
        assert dhc[gm.Basic_D_Energy] == 0

    # ---------- card is None ----------
    def test_card_none_returns_zero_regardless_of_context(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1))
        my_ps.active = [None]  # 裏向き等でカードが取得できない状態を表現
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o = Option(type=OptionType.CARD, area=AreaType.ACTIVE, index=0, playerIndex=0)
        for context in (
            SelectContext.SETUP_ACTIVE_POKEMON,
            SelectContext.SWITCH,
            SelectContext.DISCARD,
            SelectContext.MAIN,
        ):
            assert gm._score_card_option(obs, o, context, 0, fs, defaultdict(int)) == 0

    # ---------- default/未対応コンテキスト ----------
    def test_unhandled_context_returns_zero(self):
        pokemon = make_pokemon(id=gm.Impidimp)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), hand=[pokemon])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o = Option(type=OptionType.CARD, area=AreaType.HAND, index=0, playerIndex=0)
        score = gm._score_card_option(obs, o, SelectContext.MAIN, 0, fs, defaultdict(int))
        assert score == 0


# ==================== agent() 統合テスト ====================
from unittest.mock import patch
from cg.api import Option, OptionType
from tests.conftest import make_main_obs


class TestAgent:
    def test_returns_deck_when_select_is_none(self):
        obs_dict = {"select": None, "logs": [], "current": None, "search_begin_input": None}
        with patch.object(gm, "my_deck", [1] * 60):
            result = gm.agent(obs_dict)
        assert result == [1] * 60

    def test_returns_valid_indices(self):
        options = [
            Option(type=OptionType.ATTACK, attackId=9102),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(options=options)
        result = gm.agent(obs_dict)
        assert all(0 <= i < len(options) for i in result)
        assert len(result) == len(set(result))

    def test_prefers_attack_over_end(self):
        options = [
            Option(type=OptionType.END),
            Option(type=OptionType.ATTACK, attackId=9102),
        ]
        obs_dict = make_main_obs(options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.ATTACK

    def test_retreats_when_grimmsnarl_low_hp(self):
        low_hp_grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, hp=100, max_hp=320)
        my_ps = make_player_state(active_pokemon=low_hp_grimmsnarl)
        options = [
            Option(type=OptionType.RETREAT),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(my_state=my_ps, options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.RETREAT

    def test_does_not_retreat_when_grimmsnarl_healthy(self):
        healthy_grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, hp=300, max_hp=320)
        my_ps = make_player_state(active_pokemon=healthy_grimmsnarl)
        options = [
            Option(type=OptionType.RETREAT),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(my_state=my_ps, options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.END

    def test_attacks_for_lethal_instead_of_retreating(self):
        """Grimmsnarl exが瀕死でも、相手をワザ一撃で確実にきぜつさせられる（確定KO）なら
        撤退せず攻撃を選ぶこと（エネルギー投資を無駄にしないための挙動保証）"""
        low_hp_grimmsnarl = make_pokemon(
            id=gm.Grimmsnarl_ex, hp=100, max_hp=320, energies=[7, 7],
        )
        my_ps = make_player_state(active_pokemon=low_hp_grimmsnarl)
        # 相手バトルポケモンのHPを180以下（Shadow Bulletで確定KO）に設定
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=150))
        options = [
            Option(type=OptionType.RETREAT),
            Option(type=OptionType.ATTACK, attackId=9102),  # Shadow_Bullet_ID (mocked)
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(my_state=my_ps, op_state=op_ps, options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.ATTACK

    def test_ability_fires_before_non_lethal_attack(self):
        """アビリティ（Munkidori）は無償で使えるため、確定KOでない攻撃より優先して
        毎ターン使用されること（Adrena-Brainの仕様意図の挙動保証）"""
        munkidori = make_pokemon(id=gm.Munkidori, energies=[7])
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, hp=300, max_hp=320, energies=[7, 7])
        my_ps = make_player_state(active_pokemon=grimmsnarl, bench=[munkidori])
        # op_state を指定しない場合、make_main_obs のデフォルトは hp=200（>180、非確定KO）
        options = [
            Option(type=OptionType.ABILITY, area=AreaType.BENCH, index=0),
            Option(type=OptionType.ATTACK, attackId=9102),  # Shadow_Bullet_ID (mocked)、非確定KO
        ]
        obs_dict = make_main_obs(my_state=my_ps, options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.ABILITY

    def test_prefers_boss_orders_when_ko_target_available(self):
        """相手ベンチにKO可能な対象がいる場合、ボスの指令(PLAY)がENDより優先されること"""
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex))
        op_bench = [make_pokemon(id=2, hp=150)]  # 180以下 → KO可能
        op_ps = make_player_state(active_pokemon=make_pokemon(id=3, hp=300), bench=op_bench)
        options = [
            Option(type=OptionType.PLAY, index=0),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(my_state=my_ps, op_state=op_ps, options=options)
        obs_dict["current"]["players"][0]["hand"] = [
            {"id": gm.Boss_Orders, "serial": 1, "playerIndex": 0}
        ]
        obs_dict["current"]["players"][0]["handCount"] = 1

        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.PLAY

    def test_holds_boss_orders_when_no_ko_target(self):
        """相手ベンチにKO可能な対象がいない場合、探索が発生しない限りボスの指令(PLAY)より
        ENDが優先されること（_rngの実乱数を使うため、EPSILON=0.28よりかなり大きい閾値になる
        乱数値が出ても温存側に倒れることをrandomのシードで固定して検証する）"""
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex))
        op_bench = [make_pokemon(id=2, hp=300)]  # 180超 → KO不可
        op_ps = make_player_state(active_pokemon=make_pokemon(id=3, hp=300), bench=op_bench)
        options = [
            Option(type=OptionType.PLAY, index=0),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(my_state=my_ps, op_state=op_ps, options=options)
        obs_dict["current"]["players"][0]["hand"] = [
            {"id": gm.Boss_Orders, "serial": 1, "playerIndex": 0}
        ]
        obs_dict["current"]["players"][0]["handCount"] = 1

        original_random = gm._rng.random
        gm._rng.random = lambda: 0.9  # EPSILON(0.28)を超える値に固定 → 温存
        try:
            result = gm.agent(obs_dict)
        finally:
            gm._rng.random = original_random
        assert options[result[0]].type == OptionType.END

    def test_play_option_with_none_card_does_not_crash(self):
        """PLAY オプションで get_card() が None を返す場合、AttributeError でクラッシュしないこと"""
        # make_main_obs で基本的な obs_dict を生成してから手札を None で置き換える
        options = [
            Option(type=OptionType.PLAY, index=0),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(options=options)

        # obs_dict 内の手札を None エントリを含む形式に変更
        # hand が通常は [] で、agent は None で get_card() が返すことを想定
        obs_dict["current"]["players"][0]["hand"] = [None]
        obs_dict["current"]["players"][0]["handCount"] = 1

        # agent() を呼び出してもクラッシュしないこと
        # (AttributeError: 'NoneType' object has no attribute 'id' が発生しないこと)
        result = gm.agent(obs_dict)
        assert isinstance(result, list)
        assert len(result) > 0
        # 有効なインデックスリストが返ること
        assert all(0 <= i < len(options) for i in result)

    def test_ability_option_with_none_card_does_not_crash(self):
        """ABILITY オプションで get_card() が None を返す場合、AttributeError でクラッシュしないこと"""
        options = [
            Option(type=OptionType.ABILITY, area=AreaType.ACTIVE, index=0),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(options=options)

        # obs_dict 内のバトル場を None エントリを含む形式に変更
        obs_dict["current"]["players"][0]["active"] = [None]

        # agent() を呼び出してもクラッシュしないこと
        # (AttributeError: 'NoneType' object has no attribute 'id' が発生しないこと)
        result = gm.agent(obs_dict)
        assert isinstance(result, list)
        assert len(result) > 0
        # 有効なインデックスリストが返ること
        assert all(0 <= i < len(options) for i in result)

    def test_attach_option_with_none_card_does_not_crash(self):
        """ATTACH オプションで card が None の場合、AttributeError でクラッシュしないこと"""
        # make_main_obs で基本的な obs_dict を生成
        options = [
            Option(type=OptionType.ATTACH, area=AreaType.HAND, index=0, inPlayArea=AreaType.ACTIVE, inPlayIndex=0),
            Option(type=OptionType.END),
        ]
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex, energies=[7]))
        obs_dict = make_main_obs(my_state=my_ps, options=options)

        # obs_dict 内の手札を None エントリを含む形式に変更
        obs_dict["current"]["players"][0]["hand"] = [None]
        obs_dict["current"]["players"][0]["handCount"] = 1

        # agent() を呼び出してもクラッシュしないこと
        # (AttributeError: 'NoneType' object has no attribute 'id' が発生しないこと)
        result = gm.agent(obs_dict)
        assert isinstance(result, list)
        assert len(result) > 0
        # 有効なインデックスリストが返ること
        assert all(0 <= i < len(options) for i in result)
