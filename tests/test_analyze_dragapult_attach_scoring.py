import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cg.api import CardType

import dragapult_agent.main as dm
from etl.gold import GameStateTracker
from analyze_dragapult_attach_scoring import (
    evaluate_attach_event, field_counts_from_tracker, is_bench_attacker,
)

DRAGAPULT_EX = 121
DRAKLOAK = 120
DREEPY = 119
BASIC_FIRE_ENERGY = 2


@dataclass
class _MockCardData:
    cardId: int
    cardType: CardType = CardType.BASIC_ENERGY


@pytest.fixture(autouse=True)
def _restore_can_main_attack():
    """evaluate_attach_event()はdm.can_main_attackというモジュールグローバルを
    書き換える。テスト内で明示的にTrueへ変えるケースがあり、後始末をしないと
    別のテストファイル(tests/test_dragapult_agent.py等)へ状態が漏れて
    テスト実行順序に依存した失敗を招くため、各テスト終了後に元の値へ戻す"""
    original = dm.can_main_attack
    yield
    dm.can_main_attack = original


@pytest.fixture
def mock_card_table():
    """evaluate_attach_event()にはcard_tableを明示引数で渡す設計のため、
    dm.card_table自体をmonkeypatchする必要はない"""
    return {BASIC_FIRE_ENERGY: _MockCardData(cardId=BASIC_FIRE_ENERGY)}


def _tracker_with_field(active_id, active_serial, bench):
    """bench: list[(card_id, serial, energy_count)]"""
    tracker = GameStateTracker(target_player_index=0)
    tracker.active_serial = active_serial
    tracker.species[active_serial] = active_id
    for card_id, serial, energy in bench:
        tracker.bench_serials.add(serial)
        tracker.species[serial] = card_id
        tracker.energy_count[serial] = energy
    return tracker


def test_field_counts_from_tracker_counts_active_and_bench():
    tracker = _tracker_with_field(DRAGAPULT_EX, 1, [(DREEPY, 2, 0), (DREEPY, 3, 0)])
    counts = field_counts_from_tracker(tracker)
    assert counts[DRAGAPULT_EX] == 1
    assert counts[DREEPY] == 2


def test_field_counts_from_tracker_returns_zero_for_absent_card_id():
    """field_counts[Budew]のように未存在キーへ直接アクセスするproduction側の
    _attach_score()と挙動を合わせるため、defaultdict(int)でなければならない
    (2026-07-22、実ログdata/battle_logs/87205390.json等でKeyErrorとして発覚)"""
    tracker = _tracker_with_field(DRAGAPULT_EX, 1, [])
    counts = field_counts_from_tracker(tracker)
    assert counts[9999999] == 0


def test_is_bench_attacker_true_when_bench_dragapult_ex_has_two_energy():
    tracker = _tracker_with_field(DREEPY, 1, [(DRAGAPULT_EX, 2, 2)])
    assert is_bench_attacker(tracker, DRAGAPULT_EX) is True


def test_is_bench_attacker_false_when_bench_dragapult_ex_has_one_energy():
    tracker = _tracker_with_field(DREEPY, 1, [(DRAGAPULT_EX, 2, 1)])
    assert is_bench_attacker(tracker, DRAGAPULT_EX) is False


def test_evaluate_attach_event_handles_candidate_with_one_energy(mock_card_table):
    """energy_count==1の候補が存在すると_attach_score()内部でpokemon.energyCards[0].idが
    参照される。tracker.energy_cardsを正しく引き継いでいないとAttributeErrorで
    クラッシュする(energy_countをintのみで持つ設計の初期案で実際に踏んだ不具合)"""
    tracker = GameStateTracker(target_player_index=0)
    tracker.active_serial = 1
    tracker.species[1] = DREEPY
    tracker.energy_count[1] = 1
    tracker.energy_cards[1] = [BASIC_FIRE_ENERGY]
    tracker.bench_serials.add(2)
    tracker.species[2] = DREEPY

    event = {
        "type": 11, "playerIndex": 0, "cardId": BASIC_FIRE_ENERGY,
        "serial": 99, "cardIdTarget": DREEPY, "serialTarget": 2,
    }
    result = evaluate_attach_event(tracker, event, card_table=mock_card_table, dragapult_ex_id=DRAGAPULT_EX)
    assert "contradiction" in result


def test_evaluate_attach_event_treats_ready_active_dragapult_as_unable_to_receive_more_energy(mock_card_table):
    """アクティブが既にドラパルトexで2エネ以上(=ファントムダイブ発動可能)なら、
    dm.can_main_attackをここで再計算してTrueにしないと、_attach_score()の
    'if active and can_main_attack: return -1' が発火せず、本来除外されるべき
    アクティブ候補に正のスコアがついて誤って矛盾判定されてしまう"""
    tracker = GameStateTracker(target_player_index=0)
    tracker.active_serial = 1
    tracker.species[1] = DRAGAPULT_EX
    tracker.energy_count[1] = 2
    tracker.bench_serials.add(2)
    tracker.species[2] = DREEPY

    event = {
        "type": 11, "playerIndex": 0, "cardId": BASIC_FIRE_ENERGY,
        "serial": 99, "cardIdTarget": DREEPY, "serialTarget": 2,
    }
    evaluate_attach_event(tracker, event, card_table=mock_card_table, dragapult_ex_id=DRAGAPULT_EX)
    assert dm.can_main_attack is True
