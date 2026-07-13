"""グリムスナールex 3指標計測CLI（立ち往生・ボス浪費・終局時山札残数）

2026-07-12の4修正（攻撃準備アタッカーの交代優先・RETREAT昇格・ボスの指令の
攻撃可否ゲート・山札セーフティ）が実戦ログで効いたかを検証するための計測ツール。
修正前の855系12件で測ったベースラインと、再提出後の新ログを同じ物差しで比較する。

計測する3指標:
1. 立ち往生手番数: 自分のMAIN選択手番のうち「アクティブ攻撃不能×ベンチ攻撃準備完了」
   だった手番の数（あわせてRETREAT選択肢が提示されていた割合も出す）
2. 攻撃不能ターンのボスの指令使用回数: ボス（ID 1182）を使った時点でアクティブが
   攻撃不能だった回数（ε探索の浪費検出）
3. 終局時山札残数: デッキアウト危険度の確認

攻撃準備の判定は src/grimmsnarl_agent/main.py の _collect_field_state / ATTACK_COSTS を
そのまま使い、エージェント本体と同じ定義で測る。

使い方: uv run python scripts/analyze_grimmsnarl_stall_metrics.py data/battle_logs/855*.json
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data" / "sample_submission"))

# macOSではlibcg.soがロードできないため、tests/conftest.pyと同様に
# cg.sim を先にモックしてから cg.api（pure Python部分）をインポートする
from unittest.mock import MagicMock  # noqa: E402

sys.modules.setdefault("cg.sim", MagicMock())
sys.modules.setdefault("cg.game", MagicMock())

from cg.api import OptionType, to_observation_class  # noqa: E402

import grimmsnarl_agent.main as gm  # noqa: E402
from etl.gold import build_event_timeline, extract_deck_list, load_raw_log  # noqa: E402

LOG_TYPE_PLAY = 10
LOG_TYPE_ATTACK = 15
LOG_TYPE_RESULT = 23
RESULT_REASONS = {1: "プライズ0", 2: "デッキアウト", 3: "バトル場0", 4: "カード効果"}


def _load_own_deck() -> list[int]:
    """decks/grimmsnarl_20260701.py の (card_id, count) 定義から60枚のIDリストを作る"""
    sys.path.insert(0, str(ROOT / "decks"))
    import grimmsnarl_20260701 as deck_module
    return [cid for cid, count in deck_module.DECK for _ in range(count)]


def detect_player_index(data: dict) -> int:
    """開幕デッキが自分のグリムスナールexデッキ定義と完全一致する側を自分と判定する。
    ミラー戦で両者一致など判定できない場合はValueError（--player-nameで明示指定してもらう）"""
    own = sorted(_load_own_deck())
    hits = [i for i in (0, 1) if sorted(extract_deck_list(data, i)) == own]
    if len(hits) != 1:
        raise ValueError(
            f"自デッキ定義と一致する側を特定できません（該当side={hits}）。"
            "--player-name で自分のエージェント名を指定してください"
        )
    return hits[0]


def find_player_index_by_name(data: dict, player_name: str) -> int:
    """info.TeamNamesからplayer_nameのplayerIndexを返す"""
    names = data["info"]["TeamNames"]
    if player_name not in names:
        raise ValueError(f"'{player_name}' が TeamNames {names} に見つかりません")
    return names.index(player_name)


def _field_state_at(obs_dict: dict):
    """observation生dictからエージェントと同じFieldStateを計算する"""
    obs = to_observation_class(obs_dict)
    my_index = obs.current.yourIndex
    return gm._collect_field_state(
        obs.current.players[my_index], obs.current.players[1 - my_index]
    )


def collect_stall_metrics(data: dict, our_idx: int) -> dict:
    """指標1: 自分のMAIN選択手番を走査し、立ち往生手番とRETREAT提示状況を数える"""
    main_steps = 0
    stall_steps = 0
    stall_retreat_offered = 0
    stall_turns = set()
    for step in data["steps"]:
        pdata = step[our_idx]
        if pdata["status"] != "ACTIVE":
            continue
        obs_dict = pdata["observation"]
        sel = obs_dict.get("select")
        if not sel or sel.get("type") != 0 or sel.get("context") != 0:  # MAIN選択のみ
            continue
        main_steps += 1
        fs = _field_state_at(obs_dict)
        if fs.my_active_ready or not fs.bench_ready_attacker:
            continue
        stall_steps += 1
        stall_turns.add(obs_dict["current"]["turn"])
        option_types = {o.get("type") for o in sel.get("option") or []}
        if int(OptionType.RETREAT) in option_types:
            stall_retreat_offered += 1
    return {
        "main_steps": main_steps,
        "stall_steps": stall_steps,
        "stall_turns": len(stall_turns),
        "stall_retreat_offered": stall_retreat_offered,
    }


def _active_ready_at_step(data: dict, step_index: int, our_idx: int) -> bool:
    """指定ステップ時点（自分視点の生スナップショット）でアクティブが攻撃可能か"""
    players = data["steps"][step_index][our_idx]["observation"]["current"]["players"]
    return any(
        poke is not None and gm._is_attack_ready(_as_pokemon(poke))
        for poke in players[our_idx]["active"]
    )


def _as_pokemon(poke_dict: dict):
    """生dictから _is_attack_ready が必要とする属性（id/energies）だけを持つ簡易オブジェクトを作る"""
    class _P:
        id = poke_dict["id"]
        energies = poke_dict["energies"]
    return _P


def collect_boss_metrics(data: dict, our_idx: int) -> dict:
    """指標2: 自分のボスの指令使用と、その時点の攻撃可否・同一ターン攻撃有無を数える。

    イベントは自分視点のタイムライン（自分のACTIVEステップで表面化する）を使う。
    ボス使用直後は必ず相手ベンチ選択（TO_ACTIVE）で自分が再度ACTIVEになるため、
    表面化ステップのターン数・盤面は使用時点と同一ターンとみなせる。
    """
    boss_plays = []
    attack_turns = set()
    for step_index, event in build_event_timeline(data, player_index=our_idx):
        if event.get("playerIndex") != our_idx:
            continue
        turn = data["steps"][step_index][our_idx]["observation"]["current"]["turn"]
        if event.get("type") == LOG_TYPE_ATTACK:
            attack_turns.add(turn)
        elif event.get("type") == LOG_TYPE_PLAY and event.get("cardId") == gm.Boss_Orders:
            boss_plays.append({
                "step": step_index,
                "turn": turn,
                "active_ready": _active_ready_at_step(data, step_index, our_idx),
            })
    for play in boss_plays:
        play["attacked_same_turn"] = play["turn"] in attack_turns
    return {
        "boss_plays": len(boss_plays),
        "boss_not_ready": sum(1 for p in boss_plays if not p["active_ready"]),
        "boss_no_attack_turn": sum(1 for p in boss_plays if not p["attacked_same_turn"]),
        "boss_turns": [p["turn"] for p in boss_plays],
    }


def collect_endgame_metrics(data: dict, our_idx: int) -> dict:
    """指標3: 終局時の自分の山札残数と、勝敗・決着理由（ベストエフォート）"""
    final_players = data["steps"][-1][0]["observation"]["current"]["players"]
    reward = data["rewards"][our_idx]
    reason = None
    for _step, event in build_event_timeline(data, player_index=0):
        if event.get("type") == LOG_TYPE_RESULT:
            reason = event.get("reason")
    return {
        "deck_left": final_players[our_idx]["deckCount"],
        "final_turn": data["steps"][-1][0]["observation"]["current"]["turn"],
        "won": reward is not None and reward > 0,
        "result_reason": RESULT_REASONS.get(reason, "-") if reason is not None else "-",
    }


def analyze_log(path: Path, player_name: str | None = None) -> dict:
    """1試合分の3指標を計測する"""
    data = load_raw_log(path)
    our_idx = (
        find_player_index_by_name(data, player_name) if player_name
        else detect_player_index(data)
    )
    opponent = data["info"]["TeamNames"][1 - our_idx]
    return {
        "log_id": path.stem,
        "opponent": opponent,
        **collect_stall_metrics(data, our_idx),
        **collect_boss_metrics(data, our_idx),
        **collect_endgame_metrics(data, our_idx),
    }


def build_report(results: list[dict]) -> str:
    """試合別テーブル＋全体集計のMarkdownレポートを組み立てる"""
    lines = [
        "# グリムスナールex 3指標計測レポート",
        "",
        "| ログID | 相手 | 勝敗 | 終局T | MAIN手番 | 立ち往生手番 | 内RETREAT提示 | ボス使用T | 攻撃不能時ボス | 終局時山札 | 決着理由 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        boss_turns = ",".join(f"T{t}" for t in r["boss_turns"]) or "-"
        lines.append(
            f"| {r['log_id']} | {r['opponent']} | {'勝' if r['won'] else '負'} "
            f"| {r['final_turn']} | {r['main_steps']} | {r['stall_steps']} "
            f"| {r['stall_retreat_offered']} | {boss_turns} | {r['boss_not_ready']} "
            f"| {r['deck_left']} | {r['result_reason']} |"
        )
    games = len(results)
    wins = sum(1 for r in results if r["won"])
    stall_total = sum(r["stall_steps"] for r in results)
    retreat_total = sum(r["stall_retreat_offered"] for r in results)
    boss_total = sum(r["boss_plays"] for r in results)
    boss_not_ready = sum(r["boss_not_ready"] for r in results)
    boss_no_attack = sum(r["boss_no_attack_turn"] for r in results)
    deck_lefts = [r["deck_left"] for r in results]
    retreat_pct = f"{retreat_total / stall_total * 100:.0f}%" if stall_total else "-"
    lines += [
        "",
        "## 全体集計",
        "",
        f"- 試合数: {games}（{wins}勝{games - wins}敗）",
        f"- 立ち往生手番数: 計{stall_total}手番"
        f"（うちRETREAT選択肢の提示 {retreat_total}手番 = {retreat_pct}）",
        f"- ボスの指令使用: 計{boss_total}回"
        f"（攻撃不能時の使用 {boss_not_ready}回 / 攻撃しなかったターンでの使用 {boss_no_attack}回）",
        f"- 終局時山札残数: 平均{sum(deck_lefts) / games:.1f}枚 / 最小{min(deck_lefts)}枚",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="グリムスナールex 3指標計測")
    parser.add_argument("logs", nargs="+", type=Path, help="バトルログJSONのパス（複数可）")
    parser.add_argument(
        "--player-name", default=None,
        help="自分のエージェント名（省略時はデッキ内容から自動判定）",
    )
    args = parser.parse_args()
    results = [analyze_log(p, args.player_name) for p in sorted(args.logs)]
    print(build_report(results))


if __name__ == "__main__":
    main()
