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
OPTION_CARD = 3
OPTION_ENERGY = 6
OPTION_ATTACH = 8
OPTION_RETREAT = 12
SELECT_TYPE_MAIN = 0
# SelectContext.DISCARD_ENERGY。退却コストの支払いはRETREATを選んだ直後の
# このコンテキストで行われる（実ログ88778720 step63→step64で確認）。
# 相手の技の効果等でも発生しうるため、直前のRETREAT選択と結びついたものだけを
# 「退却で失った」と数える
CONTEXT_DISCARD_ENERGY = 30

# デッキ内のサポート（EN_Card_Data.csvのCategoryがSupporterのもの）
BOSS_ORDERS = 1182
JUDGE = 1213
LILLIE_DETERMINATION = 1227
SUPPORTER_IDS = frozenset({BOSS_ORDERS, JUDGE, LILLIE_DETERMINATION})
# context=8 (DISCARD、手札からの破棄) のみを計測対象にする。
# context=29 (DISCARD_CARD_OR_ATTACHED_CARD) は場に装着済みのカードの破棄も含むため、
# 「手札のエネルギーをコストとして自分で捨てた回数」とは意味が異なる指標になる。
# なお_hand_card()はarea!=AREA_HANDのoptionを問答無用でNone扱いするため、29を含めても
# 装着済み破棄は捕捉できずdiscarded=[]のまま握りつぶされてしまう（黙って取りこぼす）。
# 意図的に29を除外することで、この取りこぼしを構造的に無くす。
DISCARD_CONTEXTS = frozenset({8})


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


def _hand_card(option: dict, hand: list, my_index: int):
    """選択肢が「自分の手札のカード」を指しているならそのカードを返す。それ以外はNone"""
    if option.get("type") != OPTION_CARD or option.get("area") != AREA_HAND:
        return None
    if option.get("playerIndex") not in (None, my_index):
        return None
    index = option.get("index")
    if index is None or index >= len(hand):
        return None
    return hand[index]


def _measure_hand_discards(data: dict, my_name: str, target_ids: frozenset) -> list:
    """手札から target_ids のカードをコスト等で捨てた場面を列挙する（エネ／サポート共通）。

    戻り値の各要素:
        step, turn, discarded(捨てたカードIDのリスト), hand_energy(その時点の手札エネ枚数),
        alternatives(target_ids以外に捨てられた候補のカードIDリスト),
        avoidable(target_ids以外だけで必要枚数をまかなえたか)
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

        discarded = []
        for choice in action:
            if not isinstance(choice, int) or choice >= len(options):
                continue
            card = _hand_card(options[choice], hand, my_index)
            if card and card["id"] in target_ids:
                discarded.append(card["id"])
        if not discarded:
            continue

        alternatives = []
        for option in options:
            card = _hand_card(option, hand, my_index)
            if card and card["id"] not in target_ids:
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


def measure_energy_discards(data: dict, my_name: str = "Kagura_UT") -> list:
    """自分の闘エネルギーをコスト等で捨てた場面を列挙する"""
    return _measure_hand_discards(data, my_name, ENERGY_IDS)


def measure_supporter_discards(data: dict, my_name: str = "Kagura_UT") -> list:
    """【副作用指標a】自分のサポートをコスト等で捨てた場面を列挙する。

    2026-07-29の修正は「コストで捨てる対象をエネルギー→サポート」へ付け替える
    ものでもあるため、エネルギー破棄の減少が単なる問題の移動でないかを確かめる
    ために数える（同修正の最終レビュー指摘）
    """
    return _measure_hand_discards(data, my_name, SUPPORTER_IDS)


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


def measure_retreat_energy_loss(data: dict, my_name: str = "Kagura_UT") -> dict:
    """【副作用指標b】退却コストで失った闘エネルギーを、直前の装着と結びつけて数える。

    2026-07-29の修正はバトル場0エネ時の装着先をベンチ→バトル場へ付け替えるもので、
    「付けた先が退却でそのエネを失うバトル場だった」なら改善ではなく問題の移動になる。

    戻り値のキー:
        retreats                 退却を選んだ回数
        energy_lost              退却コストで失った闘エネルギーの枚数
        lost_attached_same_turn  うち同じターンにバトル場へ装着したエネルギーの枚数
        lost_attached_prev_turn  うち直前の自分のターンに装着したエネルギーの枚数

    同一ターンに複数枚装着した場合、どの1枚が捨てられたかはログから特定できないため、
    「そのターンに装着した枚数」を上限として枚数ベースで対応づける近似を採る。
    """
    my_index = find_player_index(data, my_name)
    attached_by_turn = defaultdict(int)   # ターン -> バトル場へ装着した未清算のエネ枚数
    my_turns = []                         # 自分が行動したターンの出現順
    stat = defaultdict(int)
    retreat_pending = False

    for _step_no, select, current, action in _iter_my_selects(data, my_index):
        turn = current.get("turn")
        if not my_turns or my_turns[-1] != turn:
            my_turns.append(turn)
        players = current.get("players") or []
        me = players[my_index] if my_index < len(players) else {}
        hand = me.get("hand") or []
        active_list = me.get("active") or []
        active = active_list[0] if active_list else None
        options = select.get("option") or []
        chosen = [options[c] for c in action
                  if isinstance(c, int) and c < len(options)]

        if select.get("context") == CONTEXT_DISCARD_ENERGY and retreat_pending:
            lost = _count_active_energy_discarded(chosen, active, my_index)
            stat["energy_lost"] += lost
            same = min(lost, attached_by_turn[turn])
            attached_by_turn[turn] -= same
            stat["lost_attached_same_turn"] += same
            remaining = lost - same
            prev_turn = my_turns[-2] if len(my_turns) >= 2 else None
            if remaining and prev_turn is not None:
                prev = min(remaining, attached_by_turn[prev_turn])
                attached_by_turn[prev_turn] -= prev
                stat["lost_attached_prev_turn"] += prev
            retreat_pending = False
            continue

        for option in chosen:
            if option.get("type") == OPTION_RETREAT:
                stat["retreats"] += 1
                # 次のDISCARD_ENERGYがこの退却のコスト支払いになる
                retreat_pending = True
            elif (option.get("type") == OPTION_ATTACH
                  and option.get("area") == AREA_HAND
                  and option.get("inPlayArea") == AREA_ACTIVE):
                index = option.get("index")
                if index is not None and index < len(hand):
                    card = hand[index]
                    if card and card["id"] in ENERGY_IDS:
                        attached_by_turn[turn] += 1

    return {
        "retreats": stat["retreats"],
        "energy_lost": stat["energy_lost"],
        "lost_attached_same_turn": stat["lost_attached_same_turn"],
        "lost_attached_prev_turn": stat["lost_attached_prev_turn"],
    }


def _count_active_energy_discarded(chosen: list, active, my_index: int) -> int:
    """退却コストとして捨てられた、バトル場の闘エネルギーの枚数を数える"""
    energies = (active or {}).get("energies") or []
    count = 0
    for option in chosen:
        if option.get("type") != OPTION_ENERGY or option.get("area") != AREA_ACTIVE:
            continue
        if option.get("playerIndex") not in (None, my_index):
            continue
        energy_index = option.get("energyIndex")
        if energy_index is None or energy_index >= len(energies):
            continue
        if energies[energy_index] in ENERGY_IDS:
            count += 1
    return count


def main(paths: list) -> None:
    """40件前後をまとめて流す運用が前提のため、1ファイルの欠損や対象外ログで
    バッチ全体を落とさない。読み込み失敗(FileNotFoundError等)と、自分が参加して
    いないログを渡した場合のfind_player_indexのValueErrorはスキップ扱いにし、
    件数を警告として出したうえでサマリーにも反映する
    （2026-07-29最終レビュー指摘4：レビュアーが実際にFileNotFoundErrorを踏んだ）"""
    total_discard = 0
    avoidable_discard = 0
    supporter_discard = 0
    attach = defaultdict(int)
    retreat = defaultdict(int)
    skipped = 0
    processed = 0
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            find_player_index(data)  # 自分が参加していないログを早期に弾く
        except (FileNotFoundError, OSError) as e:
            skipped += 1
            print(f"警告: {path} を読み込めずスキップしました（{e}）")
            continue
        except ValueError as e:
            skipped += 1
            print(f"警告: {path} は対象外のログのためスキップしました（{e}）")
            continue

        processed += 1
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
        for event in measure_supporter_discards(data):
            supporter_discard += len(event["discarded"])
        for key, value in measure_retreat_energy_loss(data).items():
            retreat[key] += value

    print(f"\n対象: {len(paths)} 件中 {processed} 件を集計（スキップ {skipped} 件）")
    print(f"エネルギー破棄: 計{total_discard}枚 / うち回避可能な場面 {avoidable_discard} 件")
    print(f"エネルギー装着: バトル場 {attach['to_active']} 回 / ベンチ {attach['to_bench']} 回")
    print(f"  うちバトル場が0エネなのにベンチへ: {attach['to_bench_while_active_zero']} 回")
    print("--- 副作用指標（修正が問題を移動させただけでないかの確認） ---")
    print(f"(a) サポートをコストで自己破棄: {supporter_discard}枚")
    print(f"(b) 退却{retreat['retreats']}回 / 退却コストで失った闘エネ {retreat['energy_lost']}枚")
    print(f"    うち同ターンにバトル場へ装着した分: {retreat['lost_attached_same_turn']}枚 "
          f"/ 直前の自分のターンに装着した分: {retreat['lost_attached_prev_turn']}枚")


if __name__ == "__main__":
    main(sys.argv[1:])
