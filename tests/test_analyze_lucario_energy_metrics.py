"""scripts/analyze_lucario_energy_metrics.py のユニットテスト"""
import importlib.util
import json
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


def _make_multi_step_log(my_index, specs):
    """自分がACTIVEな複数ステップからなるバトルログを組み立てる。

    specs の各要素は dict:
        turn, select_type, context, options, chosen, active(省略時は空エネのオーガポン), bench, hand
    選択結果は steps[N+1][my_index]['action'] に入る（1ステップずれ）ので、
    仕様どおり次ステップに action を置く。
    """
    agents = [{"Name": "opponent"}, {"Name": "opponent"}]
    agents[my_index] = {"Name": "Kagura_UT"}
    steps = []
    for spec in specs:
        me = {"active": [dict(spec.get("active", {"id": 117, "energies": []}))],
              "bench": [dict(b) for b in spec.get("bench", [{"id": 677, "energies": []}])],
              "hand": [dict(c) for c in spec.get("hand", [])]}
        players = [{"active": [], "bench": [], "hand": []},
                   {"active": [], "bench": [], "hand": []}]
        players[my_index] = me
        step = [{"status": "INACTIVE"}, {"status": "INACTIVE"}]
        step[my_index] = {
            "status": "ACTIVE",
            "observation": {
                "current": {"turn": spec["turn"], "players": players},
                "select": {"type": spec["select_type"], "context": spec["context"],
                           "minCount": 1, "maxCount": 1, "option": spec["options"]},
            },
        }
        steps.append(step)
    # 各ステップの選択結果を「次のステップ」に載せる
    out = []
    for i, step in enumerate(steps):
        out.append(step)
        action_step = [{"action": None}, {"action": None}]
        action_step[my_index] = {"status": "INACTIVE", "action": specs[i]["chosen"]}
        out.append(action_step)
    return {"info": {"Agents": agents}, "rewards": [1, -1], "steps": out}


@pytest.mark.parametrize("my_index", [0, 1])
def test_counts_supporter_discarded_as_cost(my_index):
    """【副作用指標a】サポートをコストで自己破棄した場面を検出する。
    2026-07-29の修正は「捨てる対象をエネルギー→サポートへ」付け替えるものでもあるため、
    エネルギー破棄の減少が単なる問題の移動でないかを確かめるのに使う"""
    hand = [{"id": 1182}, {"id": BASIC_F}]  # Boss's Orders / 基本闘エネ
    options = [
        {"type": 3, "area": 2, "index": 0, "playerIndex": my_index},
        {"type": 3, "area": 2, "index": 1, "playerIndex": my_index},
    ]
    data = _make_log(my_index, hand, options, chosen=[0], context=8)
    events = alem.measure_supporter_discards(data)
    assert len(events) == 1
    assert events[0]["discarded"] == [1182]


def test_ignores_non_supporter_discard():
    """サポート以外（グッズ等）を捨てた場合は副作用指標aには計上しない"""
    hand = [{"id": 1122}]  # Pokégear 3.0（グッズ）
    options = [{"type": 3, "area": 2, "index": 0, "playerIndex": 0}]
    data = _make_log(0, hand, options, chosen=[0], context=8)
    assert alem.measure_supporter_discards(data) == []


@pytest.mark.parametrize("my_index", [0, 1])
def test_counts_retreat_cost_losing_energy_attached_same_turn(my_index):
    """【副作用指標b】同じターンにバトル場へ装着したエネルギーを、
    その直後の退却コストで捨てた場面を検出する（実ログ88778720 step62-64の再現）"""
    attach_option = {"type": 8, "area": 2, "index": 0, "inPlayArea": 4, "inPlayIndex": 0}
    retreat_option = {"type": 12}
    # 退却コストの支払い：SelectType.ENERGY(4) / SelectContext.DISCARD_ENERGY(30)
    energy_option = {"type": 6, "area": 4, "index": 0, "energyIndex": 0, "playerIndex": my_index}
    data = _make_multi_step_log(my_index, [
        {"turn": 7, "select_type": 0, "context": 0, "options": [attach_option], "chosen": [0],
         "hand": [{"id": BASIC_F}], "active": {"id": 117, "energies": []}},
        {"turn": 7, "select_type": 0, "context": 0, "options": [retreat_option], "chosen": [0],
         "active": {"id": 117, "energies": [BASIC_F]}},
        {"turn": 7, "select_type": 4, "context": 30, "options": [energy_option], "chosen": [0],
         "active": {"id": 117, "energies": [BASIC_F]}},
    ])
    stat = alem.measure_retreat_energy_loss(data)
    assert stat["retreats"] == 1
    assert stat["energy_lost"] == 1
    assert stat["lost_attached_same_turn"] == 1
    assert stat["lost_attached_prev_turn"] == 0


@pytest.mark.parametrize("my_index", [0, 1])
def test_counts_retreat_cost_losing_energy_attached_previous_turn(my_index):
    """【副作用指標b】直前の自分のターンに装着したエネルギーを退却コストで失う場面も数える"""
    attach_option = {"type": 8, "area": 2, "index": 0, "inPlayArea": 4, "inPlayIndex": 0}
    retreat_option = {"type": 12}
    energy_option = {"type": 6, "area": 4, "index": 0, "energyIndex": 0, "playerIndex": my_index}
    data = _make_multi_step_log(my_index, [
        {"turn": 3, "select_type": 0, "context": 0, "options": [attach_option], "chosen": [0],
         "hand": [{"id": BASIC_F}], "active": {"id": 117, "energies": []}},
        {"turn": 5, "select_type": 0, "context": 0, "options": [retreat_option], "chosen": [0],
         "active": {"id": 117, "energies": [BASIC_F]}},
        {"turn": 5, "select_type": 4, "context": 30, "options": [energy_option], "chosen": [0],
         "active": {"id": 117, "energies": [BASIC_F]}},
    ])
    stat = alem.measure_retreat_energy_loss(data)
    assert stat["energy_lost"] == 1
    assert stat["lost_attached_same_turn"] == 0
    assert stat["lost_attached_prev_turn"] == 1


def test_energy_discard_without_retreat_is_not_counted_as_retreat_cost():
    """相手の技の効果等で退却を伴わずエネルギーを失った場合は退却コストとして数えない。
    DISCARD_ENERGY(30)は退却以外でも発生するため、直前のRETREAT選択と結びついたものだけを計上する"""
    energy_option = {"type": 6, "area": 4, "index": 0, "energyIndex": 0, "playerIndex": 0}
    data = _make_multi_step_log(0, [
        {"turn": 4, "select_type": 4, "context": 30, "options": [energy_option], "chosen": [0],
         "active": {"id": 117, "energies": [BASIC_F]}},
    ])
    stat = alem.measure_retreat_energy_loss(data)
    assert stat["retreats"] == 0
    assert stat["energy_lost"] == 0


def test_retreat_without_energy_cost_is_counted_but_loses_nothing():
    """ふうせん等でにげるコストが0の場合、退却しても失うエネルギーは無い"""
    retreat_option = {"type": 12}
    data = _make_multi_step_log(0, [
        {"turn": 6, "select_type": 0, "context": 0, "options": [retreat_option], "chosen": [0],
         "active": {"id": 117, "energies": [BASIC_F]}},
        {"turn": 6, "select_type": 1, "context": 3,
         "options": [{"type": 3, "area": 5, "index": 0, "playerIndex": 0}], "chosen": [0],
         "active": {"id": 117, "energies": [BASIC_F]}},
    ])
    stat = alem.measure_retreat_energy_loss(data)
    assert stat["retreats"] == 1
    assert stat["energy_lost"] == 0


def test_find_player_index_raises_value_error_when_not_participating():
    """【2026-07-29最終レビュー指摘4】自分が参加していないログを誤って渡した場合、
    find_player_indexがValueErrorを送出することを確認する。main()側はこれを
    スキップ扱いにしてバッチ全体を落とさないようにする"""
    data = {"info": {"Agents": [{"Name": "opponent_a"}, {"Name": "opponent_b"}]}}
    with pytest.raises(ValueError):
        alem.find_player_index(data)


def test_main_skips_missing_file_and_reports_skip_count(tmp_path, capsys):
    """【2026-07-29最終レビュー指摘4】ファイルが1つ欠けているだけでmain()全体が
    FileNotFoundErrorで停止しないこと。スキップ件数が警告とサマリーの両方に出ること"""
    missing = tmp_path / "does_not_exist.json"
    alem.main([str(missing)])
    out = capsys.readouterr().out
    assert "スキップ" in out
    assert "1" in out.split("スキップ")[-1]  # スキップ件数がサマリーに出ている


def test_main_skips_log_where_self_did_not_participate(tmp_path, capsys):
    """自分が参加していないログ（find_player_indexのValueError）もスキップ扱いにする"""
    path = tmp_path / "not_mine.json"
    path.write_text(json.dumps({
        "info": {"Agents": [{"Name": "opponent_a"}, {"Name": "opponent_b"}]},
        "steps": [],
    }), encoding="utf-8")
    alem.main([str(path)])
    out = capsys.readouterr().out
    assert "対象外のログ" in out
