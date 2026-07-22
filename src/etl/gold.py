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


def load_tool_card_ids(csv_path: Path) -> frozenset:
    """EN_Card_Data.csvから「Pokémon Tool」カテゴリのCard IDだけを集めたfrozensetを返す。

    cg.apiのCardType.TOOLと同じ意味だが、ネイティブライブラリ(cg.sim)を使わず
    CSVだけから判定できるようにする（macOSではall_card_data()が動かないため）。
    """
    type_column = "Stage (Pokémon)/Type (Energy and Trainer)"
    tool_ids = set()
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row[type_column] == "Pokémon Tool":
                tool_ids.add(int(row["Card ID"]))
    return frozenset(tool_ids)


def load_pokemon_card_ids(csv_path: Path) -> frozenset:
    """EN_Card_Data.csvから「ポケモン」カテゴリ(たね/1進化/2進化)のCard IDだけを
    集めたfrozensetを返す。GameStateTrackerがPLAYイベント(手札からの新規登場)を
    ポケモンの場への配置として扱うべきか判定するために使う。
    """
    type_column = "Stage (Pokémon)/Type (Energy and Trainer)"
    pokemon_categories = {"Basic Pokémon", "Stage 1 Pokémon", "Stage 2 Pokémon"}
    pokemon_ids = set()
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row[type_column] in pokemon_categories:
                pokemon_ids.add(int(row["Card ID"]))
    return frozenset(pokemon_ids)


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


LOG_TYPE_SWITCH = 8
LOG_TYPE_PLAY = 10
LOG_TYPE_ATTACK = 15
LOG_TYPE_RESULT = 23
LOG_TYPE_MOVE_CARD = 6
LOG_TYPE_ATTACH = 11
LOG_TYPE_EVOLVE = 12
LOG_TYPE_ASLEEP = 19
LOG_TYPE_PARALYZED = 20

AREA_HAND = 2
AREA_DISCARD = 3
AREA_ACTIVE = 4
AREA_BENCH = 5
AREA_PRIZE = 6


class GameStateTracker:
    """自分(target_player_index)の場の状態と相手の残りサイド枚数を、
    生イベントを1件ずつ適用してインクリメンタルに追跡する。

    1つの観測ステップに複数ターン分のイベントが混在しうるため、
    ステップ単位のスナップショット(observation.current)は一切参照しない。
    build_event_timeline()が返すフラットなイベント列を順番にapply()するだけで、
    任意の時点の「本当のアクティブ/ベンチ構成」を再現できる。
    """

    INITIAL_PRIZE_COUNT = 6

    def __init__(self, target_player_index: int, tool_card_ids: frozenset = frozenset(),
                 pokemon_card_ids: frozenset = frozenset()):
        self.target_player_index = target_player_index
        self.opponent_index = 1 - target_player_index
        self.tool_card_ids = tool_card_ids
        self.pokemon_card_ids = pokemon_card_ids
        self.active_serial: int | None = None
        self.bench_serials: set = set()
        self.species: dict = {}
        self.energy_count: dict = collections.defaultdict(int)
        self.energy_cards: dict = collections.defaultdict(list)  # serial -> 装着済みエネルギーcard_idのリスト
        self.asleep = False
        self.paralyzed = False
        self.opponent_prize_remaining = self.INITIAL_PRIZE_COUNT

    def apply(self, event: dict) -> None:
        event_type = event.get("type")
        player_index = event.get("playerIndex")

        if (event_type == LOG_TYPE_MOVE_CARD and player_index == self.opponent_index
                and event.get("fromArea") == AREA_PRIZE and event.get("toArea") == AREA_HAND):
            self.opponent_prize_remaining -= 1

        if player_index != self.target_player_index:
            return

        if event_type == LOG_TYPE_MOVE_CARD:
            self._apply_move_card(event)
        elif event_type == LOG_TYPE_SWITCH:
            self._apply_switch(event)
        elif event_type == LOG_TYPE_PLAY and event.get("cardId") in self.pokemon_card_ids:
            self._apply_play(event)
        elif event_type == LOG_TYPE_ATTACH:
            self._apply_attach(event)
        elif event_type == LOG_TYPE_EVOLVE:
            self._apply_evolve(event)
        elif event_type == LOG_TYPE_ASLEEP:
            self.asleep = not event.get("isRecover", False)
        elif event_type == LOG_TYPE_PARALYZED:
            self.paralyzed = not event.get("isRecover", False)

    def _apply_move_card(self, event: dict) -> None:
        serial = event["serial"]
        card_id = event["cardId"]
        from_area = event.get("fromArea")
        to_area = event.get("toArea")
        if to_area == AREA_ACTIVE:
            self.active_serial = serial
            self.bench_serials.discard(serial)
            self.species[serial] = card_id
            self.energy_count[serial]  # defaultdictでキーを作るだけ
        elif to_area == AREA_BENCH:
            self.bench_serials.add(serial)
            self.species[serial] = card_id
            self.energy_count[serial]
        elif to_area == AREA_DISCARD and from_area in (AREA_ACTIVE, AREA_BENCH):
            self._remove_serial(serial)

    def _apply_play(self, event: dict) -> None:
        """手札からのポケモン新規登場。たねポケモンを手札から場に出す動作は
        MOVE_CARDではなくPLAYイベントとしてのみ記録される
        (2026-07-22、実ログdata/battle_logs/87204277.jsonのstep=80で確認済み:
        Dreepy(serial=11)がPLAYのみでMOVE_CARDが一切伴わなかった)。
        アクティブが空ならアクティブへ、埋まっていればベンチへ配置する。"""
        serial = event["serial"]
        card_id = event["cardId"]
        if self.active_serial is None:
            self.active_serial = serial
        else:
            self.bench_serials.add(serial)
        self.species[serial] = card_id
        self.energy_count[serial]  # defaultdictでキーを作るだけ

    def _apply_switch(self, event: dict) -> None:
        # cardIdActive/serialActive: アクティブから退場しベンチへ行く側
        # cardIdBench/serialBench: ベンチから登場しアクティブになる側
        # (cg/api.pyのコメントはフィールド名と意味が逆になっている点に注意。
        #  2026-07-22に一度取り違えて誤診断した実績があるため、この対応関係を変更する際は要注意)
        outgoing_serial = event["serialActive"]
        incoming_serial = event["serialBench"]
        assert self.active_serial == outgoing_serial, (
            f"SWITCH整合性エラー: tracker.active_serial={self.active_serial} "
            f"がイベントのserialActive={outgoing_serial}と一致しない"
        )
        self.bench_serials.discard(incoming_serial)
        self.bench_serials.add(outgoing_serial)
        self.active_serial = incoming_serial

    def _apply_attach(self, event: dict) -> None:
        target_serial = event["serialTarget"]
        card_id = event["cardId"]
        if card_id not in self.tool_card_ids:
            self.energy_count[target_serial] += 1
            self.energy_cards[target_serial].append(card_id)

    def _apply_evolve(self, event: dict) -> None:
        pre_serial = event["serialTarget"]
        post_serial = event["serial"]
        post_card_id = event["cardId"]
        energy = self.energy_count.pop(pre_serial, 0)
        energy_cards = self.energy_cards.pop(pre_serial, [])
        self.species.pop(pre_serial, None)
        if self.active_serial == pre_serial:
            self.active_serial = post_serial
            self.bench_serials.discard(pre_serial)
        elif pre_serial in self.bench_serials:
            self.bench_serials.discard(pre_serial)
            self.bench_serials.add(post_serial)
        self.species[post_serial] = post_card_id
        self.energy_count[post_serial] = energy
        self.energy_cards[post_serial] = energy_cards

    def _remove_serial(self, serial: int) -> None:
        self.species.pop(serial, None)
        self.energy_count.pop(serial, None)
        self.energy_cards.pop(serial, None)
        self.bench_serials.discard(serial)
        if self.active_serial == serial:
            self.active_serial = None


def _find_energy_count(data: dict, step_index: int, owner_index: int, serial: int) -> int | None:
    """指定ステップ時点で、指定シリアルのポケモンが持つエネルギー数を返す（見つからなければNone）"""
    state = data["steps"][step_index][0]["observation"]["current"]
    player_state = state["players"][owner_index]
    candidates = list(player_state["active"]) + list(player_state["bench"])
    for poke in candidates:
        if poke and poke.get("serial") == serial:
            return len(poke["energies"])
    return None


def _find_turn_number(data: dict, step_index: int) -> int:
    """指定ステップ時点のターン数を返す"""
    return data["steps"][step_index][0]["observation"]["current"]["turn"]


def extract_attack_events(data: dict, target_player_index: int) -> list[dict]:
    """target_player_indexの技使用イベントを、その時点のエネルギー数付きで抽出する"""
    result = []
    for step_index, event in build_event_timeline(data, player_index=0):
        if event.get("type") != LOG_TYPE_ATTACK or event.get("playerIndex") != target_player_index:
            continue
        result.append({
            "step": step_index,
            "turn": _find_turn_number(data, step_index),
            "attack_id": event["attackId"],
            "card_id": event["cardId"],
            "serial": event["serial"],
            "energy_count": _find_energy_count(data, step_index, target_player_index, event["serial"]),
        })
    return result


def extract_switch_events(data: dict, target_player_index: int) -> list[dict]:
    """target_player_indexの入れ替え（SWITCH）イベントを抽出する"""
    result = []
    for step_index, event in build_event_timeline(data, player_index=0):
        if event.get("type") != LOG_TYPE_SWITCH or event.get("playerIndex") != target_player_index:
            continue
        result.append({
            "step": step_index,
            "turn": _find_turn_number(data, step_index),
            "card_id_active": event["cardIdActive"],
            "card_id_bench": event["cardIdBench"],
        })
    return result


def extract_play_events(data: dict, target_player_index: int) -> list[dict]:
    """target_player_indexのカードプレイ（PLAY）イベントを抽出する（トレーナーズ・サポート含む）"""
    result = []
    for step_index, event in build_event_timeline(data, player_index=0):
        if event.get("type") != LOG_TYPE_PLAY or event.get("playerIndex") != target_player_index:
            continue
        result.append({
            "step": step_index,
            "turn": _find_turn_number(data, step_index),
            "card_id": event["cardId"],
            "serial": event["serial"],
        })
    return result


def extract_result_reason(data: dict) -> int | None:
    """試合の決着理由を返す（1=プライズ0/2=デッキアウト/3=バトル場0/4=カード効果）。
    RESULTログイベントが記録されていない試合ではNoneを返す（ベストエフォート）。"""
    for _step_index, event in build_event_timeline(data, player_index=0):
        if event.get("type") == LOG_TYPE_RESULT:
            return event.get("reason")
    return None
