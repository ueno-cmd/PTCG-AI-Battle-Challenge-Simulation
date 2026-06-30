# tests/test_cinderace_starmie_agent.py
import pytest
from dataclasses import dataclass, field
from collections import defaultdict
from cg.api import CardType, Card, AreaType

import cinderace_starmie_agent.main as cm
from tests.conftest import make_pokemon, make_player_state


@dataclass
class MockCardData:
    cardId:   int
    name:     str      = ""
    megaEx:   bool     = False
    ex:       bool     = False
    stage1:   bool     = False
    stage2:   bool     = False
    cardType: CardType = CardType.POKEMON
    attacks:  list     = field(default_factory=list)


@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        cm.Scorbunny:            MockCardData(cardId=cm.Scorbunny),
        cm.Raboot:               MockCardData(cardId=cm.Raboot, stage1=True),
        cm.Cinderace:            MockCardData(cardId=cm.Cinderace, stage2=True, attacks=[9001]),
        cm.Staryu:               MockCardData(cardId=cm.Staryu),
        cm.Mega_Starmie_ex:      MockCardData(cardId=cm.Mega_Starmie_ex, megaEx=True, attacks=[9002, 9003]),
        cm.Buddy_Buddy_Poffin:   MockCardData(cardId=cm.Buddy_Buddy_Poffin,   cardType=CardType.ITEM),
        cm.Ultra_Ball:           MockCardData(cardId=cm.Ultra_Ball,           cardType=CardType.ITEM),
        cm.Mega_Signal:          MockCardData(cardId=cm.Mega_Signal,          cardType=CardType.ITEM),
        cm.Night_Stretcher:      MockCardData(cardId=cm.Night_Stretcher,      cardType=CardType.ITEM),
        cm.Heros_Cape:           MockCardData(cardId=cm.Heros_Cape,           cardType=CardType.TOOL),
        cm.Pokegear_30:          MockCardData(cardId=cm.Pokegear_30,          cardType=CardType.ITEM),
        cm.Crushing_Hammer:      MockCardData(cardId=cm.Crushing_Hammer,      cardType=CardType.ITEM),
        cm.Salvatore:            MockCardData(cardId=cm.Salvatore,            cardType=CardType.SUPPORTER),
        cm.Hilda:                MockCardData(cardId=cm.Hilda,                cardType=CardType.SUPPORTER),
        cm.Lillie_Determination: MockCardData(cardId=cm.Lillie_Determination, cardType=CardType.SUPPORTER),
        cm.Wallys_Compassion:    MockCardData(cardId=cm.Wallys_Compassion,    cardType=CardType.SUPPORTER),
        cm.Basic_Water_Energy:   MockCardData(cardId=cm.Basic_Water_Energy,   cardType=CardType.BASIC_ENERGY),
        cm.Ignition_Energy:      MockCardData(cardId=cm.Ignition_Energy,      cardType=CardType.SPECIAL_ENERGY),
    }
    monkeypatch.setattr(cm, "card_table",       table)
    monkeypatch.setattr(cm, "Turbo_Flare_ID",   9001)
    monkeypatch.setattr(cm, "Jetting_Blow_ID",  9002)
    monkeypatch.setattr(cm, "Nebula_Beam_ID",   9003)
    return table


# ==================== _collect_field_state ====================
class TestCollectFieldState:
    def test_cinderace_active_with_energy(self):
        cinderace = make_pokemon(id=cm.Cinderace, energies=[3])
        my_ps = make_player_state(active_pokemon=cinderace)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.cinderace_active is True

    def test_cinderace_active_without_energy_is_false(self):
        cinderace = make_pokemon(id=cm.Cinderace, energies=[])
        my_ps = make_player_state(active_pokemon=cinderace)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.cinderace_active is False

    def test_starmie_bench_detected(self):
        starmie = make_pokemon(id=cm.Mega_Starmie_ex, energies=[3, 3, 3])
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=cm.Cinderace),
            bench=[starmie],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.starmie_bench_idx    == 0
        assert fs.starmie_bench_energy == 3

    def test_starmie_bench_absent_returns_minus1(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=cm.Scorbunny))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.starmie_bench_idx == -1

    def test_switch_to_starmie_when_ready(self):
        starmie   = make_pokemon(id=cm.Mega_Starmie_ex, energies=[3])
        scorbunny = make_pokemon(id=cm.Scorbunny)
        my_ps = make_player_state(active_pokemon=scorbunny, bench=[starmie])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.switch_to_starmie is True

    def test_no_switch_when_cinderace_active(self):
        cinderace = make_pokemon(id=cm.Cinderace, energies=[3])
        starmie   = make_pokemon(id=cm.Mega_Starmie_ex, energies=[3])
        my_ps = make_player_state(active_pokemon=cinderace, bench=[starmie])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.switch_to_starmie is False

    def test_wally_in_hand(self):
        wally = Card(id=cm.Wallys_Compassion, serial=1, playerIndex=0)
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=cm.Mega_Starmie_ex, hp=200, max_hp=330),
            hand=[wally],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.wally_in_hand is True

    def test_starmie_active_damage(self):
        starmie = make_pokemon(id=cm.Mega_Starmie_ex, hp=200, max_hp=330)
        my_ps = make_player_state(active_pokemon=starmie)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.starmie_active_damage == 130  # 330 - 200


# ==================== _score_play ====================
class TestScorePlay:
    def _make_fs(self, **kwargs):
        defaults = dict(
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int),
            discard_counts=defaultdict(int),
            cinderace_active=False,
            starmie_bench_idx=-1,
            starmie_bench_energy=0,
            starmie_active_damage=0,
            op_active_hp=200,
            wally_in_hand=False,
            switch_to_starmie=False,
        )
        defaults.update(kwargs)
        return cm.FieldState(**defaults)

    def test_lillie_determination_first_turn(self):
        fs = self._make_fs()
        assert cm._score_play(cm.Lillie_Determination, fs, prize_count=6) == 10000

    def test_lillie_determination_normal_turn(self):
        fs = self._make_fs()
        assert cm._score_play(cm.Lillie_Determination, fs, prize_count=4) == 3000

    def test_buddy_buddy_poffin_high_when_lines_missing(self):
        fs = self._make_fs()  # field_counts と hand_counts は空
        score = cm._score_play(cm.Buddy_Buddy_Poffin, fs, prize_count=6)
        assert score == 8000

    def test_salvatore_high_when_staryu_present_starmie_absent(self):
        fc = defaultdict(int, {cm.Staryu: 1})
        fs = self._make_fs(field_counts=fc)
        score = cm._score_play(cm.Salvatore, fs, prize_count=6)
        assert score == 7000

    def test_wally_compassion_high_when_starmie_damaged(self):
        fs = self._make_fs(starmie_active_damage=100)
        score = cm._score_play(cm.Wallys_Compassion, fs, prize_count=6)
        assert score == 6500

    def test_wally_compassion_minus1_when_no_damage(self):
        fs = self._make_fs(starmie_active_damage=0)
        score = cm._score_play(cm.Wallys_Compassion, fs, prize_count=6)
        assert score == -1

    def test_mega_signal_high_when_starmie_absent(self):
        fs = self._make_fs()
        score = cm._score_play(cm.Mega_Signal, fs, prize_count=6)
        assert score == 4500

    def test_mega_signal_low_when_starmie_present(self):
        fc = defaultdict(int, {cm.Mega_Starmie_ex: 1})
        fs = self._make_fs(field_counts=fc)
        score = cm._score_play(cm.Mega_Signal, fs, prize_count=6)
        assert score == 1000


# ==================== _score_attach ====================
class TestScoreAttach:
    def _make_fs(self, **kwargs):
        defaults = dict(
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int),
            discard_counts=defaultdict(int),
            cinderace_active=False,
            starmie_bench_idx=0,
            starmie_bench_energy=0,
            starmie_active_damage=0,
            op_active_hp=200,
            wally_in_hand=False,
            switch_to_starmie=False,
        )
        defaults.update(kwargs)
        return cm.FieldState(**defaults)

    def test_ignition_to_cinderace_with_0_energy(self):
        cinderace = make_pokemon(id=cm.Cinderace, energies=[])
        fs = self._make_fs()
        score = cm._score_attach(cinderace, AreaType.ACTIVE, cm.Ignition_Energy, fs)
        assert score == 9000

    def test_ignition_to_cinderace_with_existing_energy_is_minus1(self):
        cinderace = make_pokemon(id=cm.Cinderace, energies=[17])
        fs = self._make_fs()
        score = cm._score_attach(cinderace, AreaType.ACTIVE, cm.Ignition_Energy, fs)
        assert score == -1

    def test_ignition_to_non_cinderace_is_minus1(self):
        starmie = make_pokemon(id=cm.Mega_Starmie_ex, energies=[])
        fs = self._make_fs()
        score = cm._score_attach(starmie, AreaType.BENCH, cm.Ignition_Energy, fs)
        assert score == -1

    def test_water_to_bench_starmie_low_energy_preferred(self):
        starmie_low  = make_pokemon(id=cm.Mega_Starmie_ex, energies=[])
        starmie_full = make_pokemon(id=cm.Mega_Starmie_ex, energies=[3, 3, 3])
        fs = self._make_fs()
        score_low  = cm._score_attach(starmie_low,  AreaType.BENCH, cm.Basic_Water_Energy, fs)
        score_full = cm._score_attach(starmie_full, AreaType.BENCH, cm.Basic_Water_Energy, fs)
        assert score_low > score_full


# ==================== _score_attack ====================
class TestScoreAttack:
    def _make_fs(self, op_hp=200, **kwargs):
        defaults = dict(
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int),
            discard_counts=defaultdict(int),
            cinderace_active=False,
            starmie_bench_idx=-1,
            starmie_bench_energy=0,
            starmie_active_damage=0,
            op_active_hp=op_hp,
            wally_in_hand=False,
            switch_to_starmie=False,
        )
        defaults.update(kwargs)
        return cm.FieldState(**defaults)

    def test_turbo_flare_always_scores_1000(self):
        fs = self._make_fs(op_hp=300)
        assert cm._score_attack(9001, fs) == 1000

    def test_nebula_beam_preferred_when_hp_high(self):
        fs = self._make_fs(op_hp=300)
        assert cm._score_attack(9003, fs) > cm._score_attack(9002, fs)

    def test_jetting_blow_preferred_when_hp_low(self):
        fs = self._make_fs(op_hp=100)
        assert cm._score_attack(9002, fs) > cm._score_attack(9003, fs)
