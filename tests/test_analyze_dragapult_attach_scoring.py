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
    _is_crispin_effect_passthrough, evaluate_attach_event,
    field_counts_from_tracker, is_bench_attacker,
)

DRAGAPULT_EX = 121
DRAKLOAK = 120
DREEPY = 119
BASIC_FIRE_ENERGY = 2
BASIC_PSYCHIC_ENERGY = 5


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


def test_evaluate_attach_event_crispin_bonus_changes_verdict(mock_card_table):
    """クリスピン(ID1198)の効果由来の自動装着ではmain.pyのATTACH_FROM分岐が
    ドラパルトexターゲットに+200ボーナスを追加する。この分岐差を反映しないと
    クリスピン由来の装着イベントで矛盾判定を誤りうる。

    2026-07-25のenergy_count==0分岐修正（アクティブ側にも種族ボーナスを追加）
    により、ドラパルトex(150枠)は場のどこにいても0エネの他種族(最大100枠)より
    常に高スコアになった。そのため「アクティブ=ドラパルトex・ベンチ=ドレディア」
    という組み合わせでは、ボーナス無しの時点で既にアクティブが上回り矛盾ありと
    なってしまい、旧来の「ボーナスの有無で判定が変わる」ケースを再現できなくなった。
    本テストはこの制約を踏まえ、対象(target)をアクティブのドロンチ(1エネ, else枠
    +50+active200=20250)に、非対象のドラパルトex(0エネ, 150枠, ベンチ, bench_attacker
    無しなので加減点なし=20150)をベンチに置く構成に差し替える。
    ボーナス無し: 20150 < 20250 で矛盾なし。+200ボーナス適用でベンチのドラパルトexが
    20350に逆転し矛盾ありに変わる、という決定的な検証にする

    【既知の制約・意図的なギャップ】
    1. 本テストのevent["serialTarget"]はtracker.active_serial(=1)と一致する、
       つまり装着対象(target)はアクティブ自身であり、元テスト(装着対象=ベンチの
       ドレディア)とは逆になっている。本番のbuild_report()はserialTarget ==
       tracker.active_serialの装着イベントをそもそもevaluate_attach_event()に
       渡さない(scripts/analyze_dragapult_attach_scoring.py:191-192の
       `event.get("serialTarget") != tracker.active_serial`フィルタでベンチ対象
       のみ通過させているため)。つまり本テストが再現している「target=active」の
       状況は、本番では発生し得ないケースである。
    2. なぜベンチ対象で再構成できないか: 2026-07-25のenergy_count==0分岐修正
       (アクティブ側にも種族ボーナスを追加、src/dragapult_agent/main.py:125-131)
       により、ドラパルトex候補はenergy_count==0であればactive/bench問わず
       同分岐の上限スコア(+150)を取るようになった。そのため競合するドラパルトex
       候補は、クリスピンボーナス(+200、ドラパルトex種族の候補全般に付与)が
       適用される前の時点で、既に大半の非ドラパルトex候補と同点かそれ以上になって
       しまい、本テストが必要とする「ボーナス適用前は矛盾なし」という前提を
       ベンチ対象のまま満たす組み合わせが構造的に作れない。
    3. 結果として「クリスピンボーナスが矛盾判定をFalse→Trueへ反転させる」という
       挙動自体は本テストで引き続き検証できるが、それは「target=active」の
       ケースに限られる。現状、同じ反転挙動を「target=bench」(本番相当)で
       検証する回帰テストは存在しない。これは見落としではなく、上記の理由により
       現行のスコアリング式では構成不可能と判断した上での既知の受容ギャップである
       (タスクレビュー2026-07-25のImportant指摘を参照)"""
    tracker = GameStateTracker(target_player_index=0)
    tracker.active_serial = 1
    tracker.species[1] = DRAKLOAK
    tracker.energy_count[1] = 1
    tracker.energy_cards[1] = [BASIC_PSYCHIC_ENERGY]
    tracker.bench_serials.add(2)
    tracker.species[2] = DRAGAPULT_EX
    tracker.energy_count[2] = 0

    event = {
        "type": 11, "playerIndex": 0, "cardId": BASIC_FIRE_ENERGY,
        "serial": 99, "cardIdTarget": DRAKLOAK, "serialTarget": 1,
    }
    without_bonus = evaluate_attach_event(
        tracker, event, card_table=mock_card_table, dragapult_ex_id=DRAGAPULT_EX,
    )
    with_bonus = evaluate_attach_event(
        tracker, event, card_table=mock_card_table, dragapult_ex_id=DRAGAPULT_EX,
        dragapult_ex_crispin_bonus=True,
    )
    assert without_bonus["contradiction"] is False
    assert with_bonus["contradiction"] is True


def test_is_crispin_effect_passthrough_accepts_shuffle():
    assert _is_crispin_effect_passthrough({"type": 0, "playerIndex": 0}) is True


def test_is_crispin_effect_passthrough_accepts_deck_to_hand_move():
    assert _is_crispin_effect_passthrough({"type": 6, "playerIndex": 0, "fromArea": 1, "toArea": 2}) is True


def test_is_crispin_effect_passthrough_rejects_other_move_card():
    """山札からの手札移動以外(例: エネルギーゾーンから捨て札等)は通過扱いしない"""
    assert _is_crispin_effect_passthrough({"type": 6, "playerIndex": 0, "fromArea": 8, "toArea": 3}) is False


def test_is_crispin_effect_passthrough_rejects_attack():
    assert _is_crispin_effect_passthrough({"type": 15, "playerIndex": 0}) is False
