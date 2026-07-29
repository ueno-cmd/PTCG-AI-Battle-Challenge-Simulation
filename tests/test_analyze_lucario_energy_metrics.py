"""scripts/analyze_lucario_energy_metrics.py のユニットテスト"""
import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "analyze_lucario_energy_metrics",
    Path(__file__).resolve().parents[1] / "scripts" / "analyze_lucario_energy_metrics.py",
)
alem = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(alem)

BASIC_F = 6
ROCK_F = 20


def _make_log(my_index, hand, options, chosen, context, select_type=1):
    """1ステップだけの最小バトルログを組み立てる。
    my_index が 1 のときも正しく動くことを確認するために使う"""
    agents = [{"Name": "opponent"}, {"Name": "opponent"}]
    agents[my_index] = {"Name": "Kagura_UT"}
    players = [{"active": [], "bench": [], "hand": []}, {"active": [], "bench": [], "hand": []}]
    players[my_index] = {"active": [], "bench": [], "hand": hand}
    step0 = [{"status": "INACTIVE"}, {"status": "INACTIVE"}]
    step0[my_index] = {
        "status": "ACTIVE",
        "observation": {
            "current": {"turn": 1, "players": players},
            "select": {"type": select_type, "context": context,
                       "minCount": 1, "maxCount": 1, "option": options},
        },
    }
    step1 = [{"action": None}, {"action": None}]
    step1[my_index] = {"status": "INACTIVE", "action": chosen}
    return {"info": {"Agents": agents}, "rewards": [1, -1], "steps": [step0, step1]}


@pytest.mark.parametrize("my_index", [0, 1])
def test_detects_energy_discard_with_alternatives(my_index):
    """他に捨てられる札があるのにエネルギーを捨てた場合を検出する"""
    hand = [{"id": BASIC_F}, {"id": 1122}]  # 基本闘エネ / Pokégear 3.0
    options = [
        {"type": 3, "area": 2, "index": 0, "playerIndex": my_index},
        {"type": 3, "area": 2, "index": 1, "playerIndex": my_index},
    ]
    data = _make_log(my_index, hand, options, chosen=[0], context=8)
    events = alem.measure_energy_discards(data)
    assert len(events) == 1
    assert events[0]["avoidable"] is True
    assert events[0]["discarded"] == [BASIC_F]


@pytest.mark.parametrize("my_index", [0, 1])
def test_marks_unavoidable_when_only_energy_offered(my_index):
    """選択肢がエネルギーしか無い場合（ルナサイクルのコスト等）は回避不能として記録する"""
    hand = [{"id": BASIC_F}]
    options = [{"type": 3, "area": 2, "index": 0, "playerIndex": my_index}]
    data = _make_log(my_index, hand, options, chosen=[0], context=8)
    events = alem.measure_energy_discards(data)
    assert len(events) == 1
    assert events[0]["avoidable"] is False


def test_ignores_non_energy_discard():
    """エネルギー以外を捨てた場合は記録しない"""
    hand = [{"id": 1122}]
    options = [{"type": 3, "area": 2, "index": 0, "playerIndex": 0}]
    data = _make_log(0, hand, options, chosen=[0], context=8)
    assert alem.measure_energy_discards(data) == []


@pytest.mark.parametrize("my_index", [0, 1])
def test_counts_bench_attach_while_active_empty(my_index):
    """バトル場が0エネなのにベンチへ装着した回数を数える"""
    hand = [{"id": BASIC_F}]
    options = [
        {"type": 8, "area": 2, "index": 0, "inPlayArea": 4, "inPlayIndex": 0},
        {"type": 8, "area": 2, "index": 0, "inPlayArea": 5, "inPlayIndex": 0},
    ]
    data = _make_log(my_index, hand, options, chosen=[1], context=0, select_type=0)
    players = data["steps"][0][my_index]["observation"]["current"]["players"]
    players[my_index]["active"] = [{"id": 117, "energies": []}]
    players[my_index]["bench"] = [{"id": 677, "energies": []}]
    stat = alem.measure_attach_targets(data)
    assert stat["to_bench"] == 1
    assert stat["to_active"] == 0
    assert stat["to_bench_while_active_zero"] == 1


@pytest.mark.parametrize("my_index", [0, 1])
def test_counts_active_attach(my_index):
    """バトル場へ装着した場合は to_active に計上し、停滞カウントは増やさない"""
    hand = [{"id": BASIC_F}]
    options = [
        {"type": 8, "area": 2, "index": 0, "inPlayArea": 4, "inPlayIndex": 0},
        {"type": 8, "area": 2, "index": 0, "inPlayArea": 5, "inPlayIndex": 0},
    ]
    data = _make_log(my_index, hand, options, chosen=[0], context=0, select_type=0)
    players = data["steps"][0][my_index]["observation"]["current"]["players"]
    players[my_index]["active"] = [{"id": 117, "energies": []}]
    players[my_index]["bench"] = [{"id": 677, "energies": []}]
    stat = alem.measure_attach_targets(data)
    assert stat["to_active"] == 1
    assert stat["to_bench_while_active_zero"] == 0
