"""バトルログの生JSONを直接解析し、デッキ構成・意思決定パターンを抽出するモジュール。

silver.pyのCSV出力（勝者名・ターン数のみ）では意思決定の深掘りに不十分なため、
生JSONのstepsを直接読み、LogTypeでデコードする。
"""
import collections
import csv
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


def extract_deck_list(data: dict, target_player_index: int) -> list[int]:
    """開幕時点のvisualizeから、target_player_indexの60枚デッキのカードID一覧を取得する"""
    action = data["steps"][0][0]["visualize"][0]["action"]
    return list(action[target_player_index])


def load_card_names(csv_path: Path) -> dict[int, tuple[str, str]]:
    """EN_Card_Data.csvからCard ID -> (Card Name, Rule) のマップを作る（重複IDは最初の行を採用）"""
    mapping: dict[int, tuple[str, str]] = {}
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            card_id = int(row["Card ID"])
            if card_id not in mapping:
                mapping[card_id] = (row["Card Name"], row["Rule"])
    return mapping


def classify_archetype(deck_card_ids: list[int], card_names: dict[int, tuple[str, str]]) -> str:
    """デッキ内のex Pokémonを出現数の多い順に並べたラベルを返す（簡易アーキタイプ分類）。

    Ruleが'Pokémon ex'または'Mega Pokémon ex'のカードのみを対象とする
    （EN_Card_Data.csvのRule列はこの2値以外に'ACE SPEC'と'n/a'のみで、
    いずれも'ex'を含まないため "ex" in rule で安全に判定できる）。
    """
    counts = collections.Counter(deck_card_ids)
    ex_cards = [
        (counts[cid], card_names[cid][0])
        for cid in set(deck_card_ids)
        if cid in card_names and "ex" in card_names[cid][1]
    ]
    if not ex_cards:
        return "(exなし)"
    ex_cards.sort(key=lambda x: (-x[0], x[1]))
    return " + ".join(f"{name}x{count}" for count, name in ex_cards)
