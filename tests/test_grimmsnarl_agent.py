import pytest
from dataclasses import dataclass, field
from collections import defaultdict
from cg.api import CardType, Card, AreaType

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
        gm.Morpeko:         MockCardData(cardId=gm.Morpeko, attacks=[9103]),
        gm.Munkidori:       MockCardData(cardId=gm.Munkidori, attacks=[9104]),
        gm.Dudunsparce:     MockCardData(cardId=gm.Dudunsparce, stage1=True, attacks=[9105]),
        gm.Dunsparce:       MockCardData(cardId=gm.Dunsparce, attacks=[9106]),
        gm.Rare_Candy:      MockCardData(cardId=gm.Rare_Candy, cardType=CardType.ITEM),
        gm.Buddy_Buddy_Poffin: MockCardData(cardId=gm.Buddy_Buddy_Poffin, cardType=CardType.ITEM),
        gm.Dawn:            MockCardData(cardId=gm.Dawn, cardType=CardType.SUPPORTER),
        gm.Lillie_Determination: MockCardData(cardId=gm.Lillie_Determination, cardType=CardType.SUPPORTER),
        gm.Basic_D_Energy:  MockCardData(cardId=gm.Basic_D_Energy, cardType=CardType.BASIC_ENERGY),
    }
    monkeypatch.setattr(gm, "card_table", table)
    monkeypatch.setattr(gm, "Shadow_Bullet_ID", 9102)
    monkeypatch.setattr(gm, "Spiky_Wheel_ID", 9103)
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
            active_pokemon=make_pokemon(id=gm.Morpeko),
            bench=[impidimp],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.impidimp_bench_idx == 0

    def test_impidimp_bench_absent_returns_minus1(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Morpeko))
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

    def test_dawn_high_when_line_missing_from_hand(self):
        fs = self._make_fs()
        assert gm._score_play(gm.Dawn, fs, prize_count=6) == 7000

    def test_lillie_determination_first_turn(self):
        fs = self._make_fs()
        assert gm._score_play(gm.Lillie_Determination, fs, prize_count=6) == 5000

    def test_xerosics_machinations_default_score(self):
        fs = self._make_fs()
        assert gm._score_play(gm.Xerosics_Machinations, fs, prize_count=4) == 3000

    def test_unhandled_card_returns_default(self):
        fs = self._make_fs()
        assert gm._score_play(gm.Energy_Recycler, fs, prize_count=4) == 1000


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

    def test_heros_cape_only_for_grimmsnarl(self):
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex)
        morpeko    = make_pokemon(id=gm.Morpeko)
        fs = gm.FieldState(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), grimmsnarl_active=True,
            grimmsnarl_energy_count=0, impidimp_bench_idx=-1,
            munkidori_bench_idx=-1, rare_candy_in_hand=False,
            my_active_hp=200, op_active_hp=200, op_bench_hp=[],
        )
        assert gm._score_attach(grimmsnarl, AreaType.ACTIVE, gm.Heros_Cape, fs) == 8500
        assert gm._score_attach(morpeko,    AreaType.BENCH,  gm.Heros_Cape, fs) == -1


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

    def test_shadow_bullet_always_top_priority(self):
        fs = self._make_fs(op_hp=300)
        assert gm._score_attack(9102, fs) == 2000  # Shadow_Bullet_ID (mocked)

    def test_unknown_attack_returns_default(self):
        fs = self._make_fs()
        assert gm._score_attack(9999, fs) == 1000
