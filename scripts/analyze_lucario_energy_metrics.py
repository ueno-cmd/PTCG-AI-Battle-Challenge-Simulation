"""ルカリオexエージェントのエネルギー運用プロセス指標を実バトルログから計測する。

2026-07-29の修正（DISCARD時の闘エネルギー温存 / バトル場0エネ時の装着優先）の
効果判定に使う。勝率やLBスコアでは効果を判定できないため（同一ロジックの20戦で
勝率が±20pt動くことが実証済み）、「狙った挙動が実際に何回消えたか」で判定する。

使い方:
    uv run python scripts/analyze_lucario_energy_metrics.py data/battle_logs/*.json
"""
import json
import sys
from collections import defaultdict

# カードID（src/lucario_agent/constants.py と同値）
BASIC_FIGHTING_ENERGY = 6
ROCK_FIGHTING_ENERGY = 20
ENERGY_IDS = frozenset({BASIC_FIGHTING_ENERGY, ROCK_FIGHTING_ENERGY})

# cg.api の列挙値
AREA_HAND = 2
AREA_ACTIVE = 4
AREA_BENCH = 5
OPTION_CARD = 3
OPTION_ATTACH = 8
SELECT_TYPE_MAIN = 0
DISCARD_CONTEXTS = frozenset({8, 29})  # DISCARD / DISCARD_CARD_OR_ATTACHED_CARD


def find_player_index(data: dict, my_name: str = "Kagura_UT") -> int:
    """自分のプレイヤーindexを返す。試合ごとに0/1が入れ替わるため必ず毎試合求めること"""
    for i, agent in enumerate(data["info"]["Agents"]):
        if agent["Name"] == my_name:
            return i
    raise ValueError(f"{my_name} が info.Agents に見つかりません")


def _iter_my_selects(data: dict, my_index: int):
    """自分がACTIVEなステップの (step番号, select, current, 選ばれたインデックス列) を順に返す。

    選択結果は steps[N]['action'] ではなく steps[N+1][my_index]['action'] に入っている
    （1ステップずれ）。この対応を間違えると全く別の選択肢を読むことになる。
    """
    steps = data["steps"]
    for i, step in enumerate(steps):
        me = step[my_index]
        if me.get("status") != "ACTIVE":
            continue
        obs = me.get("observation") or {}
        select = obs.get("select")
        if not select:
            continue
        action = steps[i + 1][my_index].get("action") if i + 1 < len(steps) else None
        yield i, select, obs.get("current") or {}, action or []


def measure_energy_discards(data: dict, my_name: str = "Kagura_UT") -> list:
    """自分の闘エネルギーをコスト等で捨てた場面を列挙する。

    戻り値の各要素:
        step, turn, discarded(捨てたカードIDのリスト), hand_energy(その時点の手札エネ枚数),
        alternatives(エネルギー以外に捨てられた候補のカードIDリスト),
        avoidable(エネルギー以外だけで必要枚数をまかなえたか)
    """
    my_index = find_player_index(data, my_name)
    events = []
    for step_no, select, current, action in _iter_my_selects(data, my_index):
        if select.get("context") not in DISCARD_CONTEXTS:
            continue
        players = current.get("players") or []
        if my_index >= len(players):
            continue
        hand = players[my_index].get("hand") or []
        options = select.get("option") or []

        def _hand_card(option):
            if option.get("type") != OPTION_CARD or option.get("area") != AREA_HAND:
                return None
            if option.get("playerIndex") not in (None, my_index):
                return None
            index = option.get("index")
            if index is None or index >= len(hand):
                return None
            return hand[index]

        discarded = []
        for choice in action:
            if not isinstance(choice, int) or choice >= len(options):
                continue
            card = _hand_card(options[choice])
            if card and card["id"] in ENERGY_IDS:
                discarded.append(card["id"])
        if not discarded:
            continue

        alternatives = []
        for option in options:
            card = _hand_card(option)
            if card and card["id"] not in ENERGY_IDS:
                alternatives.append(card["id"])
        events.append({
            "step": step_no,
            "turn": current.get("turn"),
            "discarded": discarded,
            "hand_energy": sum(1 for c in hand if c and c["id"] in ENERGY_IDS),
            "alternatives": alternatives,
            "avoidable": len(alternatives) >= (select.get("minCount") or 1),
        })
    return events


def measure_attach_targets(data: dict, my_name: str = "Kagura_UT") -> dict:
    """エネルギーの装着先（バトル場 / ベンチ）を集計する。

    戻り値のキー:
        to_active, to_bench, to_bench_while_active_zero
    """
    my_index = find_player_index(data, my_name)
    stat = defaultdict(int)
    for _step_no, select, current, action in _iter_my_selects(data, my_index):
        if select.get("type") != SELECT_TYPE_MAIN:
            continue
        players = current.get("players") or []
        if my_index >= len(players):
            continue
        me = players[my_index]
        hand = me.get("hand") or []
        active_list = me.get("active") or []
        active = active_list[0] if active_list else None
        options = select.get("option") or []
        for choice in action:
            if not isinstance(choice, int) or choice >= len(options):
                continue
            option = options[choice]
            if option.get("type") != OPTION_ATTACH or option.get("area") != AREA_HAND:
                continue
            index = option.get("index")
            if index is None or index >= len(hand):
                continue
            card = hand[index]
            if not card or card["id"] not in ENERGY_IDS:
                continue
            if option.get("inPlayArea") == AREA_ACTIVE:
                stat["to_active"] += 1
            else:
                stat["to_bench"] += 1
                if active is not None and not (active.get("energies") or []):
                    stat["to_bench_while_active_zero"] += 1
    return {
        "to_active": stat["to_active"],
        "to_bench": stat["to_bench"],
        "to_bench_while_active_zero": stat["to_bench_while_active_zero"],
    }


def main(paths: list) -> None:
    total_discard = 0
    avoidable_discard = 0
    attach = defaultdict(int)
    for path in paths:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        events = measure_energy_discards(data)
        for event in events:
            total_discard += len(event["discarded"])
            if event["avoidable"]:
                avoidable_discard += 1
                print(f"{path} step{event['step']} t{event['turn']} "
                      f"回避可能なエネルギー破棄 手札エネ={event['hand_energy']} "
                      f"代替候補={event['alternatives']}")
        for key, value in measure_attach_targets(data).items():
            attach[key] += value
    print(f"\n対象: {len(paths)} 試合")
    print(f"エネルギー破棄: 計{total_discard}枚 / うち回避可能な場面 {avoidable_discard} 件")
    print(f"エネルギー装着: バトル場 {attach['to_active']} 回 / ベンチ {attach['to_bench']} 回")
    print(f"  うちバトル場が0エネなのにベンチへ: {attach['to_bench_while_active_zero']} 回")


if __name__ == "__main__":
    main(sys.argv[1:])
