"""バトルログの生JSONを直接解析し、デッキ構成・意思決定パターンを抽出するモジュール。

silver.pyのCSV出力（勝者名・ターン数のみ）では意思決定の深掘りに不十分なため、
生JSONのstepsを直接読み、LogTypeでデコードする。
"""
import json
from pathlib import Path


def load_raw_log(log_path: Path) -> dict:
    """バトルログの生JSONを読み込む"""
    return json.loads(log_path.read_text(encoding="utf-8"))


def find_player_index(data: dict, player_name: str) -> int:
    """info.Agentsからplayer_nameに完全一致するplayerIndex（0または1）を返す"""
    agents = data["info"]["Agents"]
    for i, agent in enumerate(agents):
        if agent["Name"] == player_name:
            return i
    raise ValueError(f"player_name '{player_name}' が info.Agents に見つかりません")


def build_event_timeline(data: dict, player_index: int = 0) -> list[tuple[int, dict]]:
    """指定したplayer_indexのobservationストリームから試合全体のイベント列を再構築する。

    steps[i][player_index]['observation']['logs']は、そのplayerがstatus='ACTIVE'の
    ステップでのみ「前回ACTIVEだった時点からの新規イベント」を保持し、INACTIVEの間は
    直前のACTIVEステップのスナップショットがそのまま残る仕様になっている
    （data/battle_logs/84580427.jsonで実測検証済み）。そのためACTIVEステップのみを
    ステップ順に拾えば、重複なく試合全体のイベント列を再構築できる。
    """
    timeline: list[tuple[int, dict]] = []
    for step_index, step in enumerate(data["steps"]):
        if step[player_index]["status"] == "ACTIVE":
            for event in step[player_index]["observation"]["logs"]:
                timeline.append((step_index, event))
    return timeline
