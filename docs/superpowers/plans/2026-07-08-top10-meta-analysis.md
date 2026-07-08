# TOP10メタ分析ツール Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 現行LB TOP10プレイヤーの直近バトルログ（各3件・計30件、ユーザーが手動DL）から「デッキ分布」と「意思決定パターン」を分析し、1つのMarkdownレポートに集約するCLIツールを作る。

**Architecture:** 既存ETL（`src/etl/bronze.py`/`silver.py`）を勝者名・ターン数の取得に再利用しつつ、デッキリスト抽出・意思決定イベント抽出は生JSON直読みの新規モジュール`src/etl/gold.py`に実装する。集約CLI `scripts/analyze_top10_meta.py` が `data/top10_meta_targets.csv` を読み、対象ログごとにsilver+goldの結果を合成してMarkdownレポートを出力する。

**Tech Stack:** Python 3.12（uv管理）、標準ライブラリ（`csv`, `json`, `pathlib`, `collections`）のみ。pytest。

## Global Constraints

- 全コードコメント・ドキュメントは日本語で書く（`CLAUDE.md`ルール3）
- TDD：各タスクは「失敗するテストを書く→失敗を確認→最小実装→成功を確認→コミット」の順で進める
- 既存のコーディングスタイルに合わせる：カード定数は`カード名 = ID`形式のモジュール変数（例：`decks/lucario_20260621.py`、`src/lucario_agent/main.py`のパターン）
- 生JSONの`logs`要素のキー名は`data/cg/api.py`のdataclassフィールド名と完全一致（camelCase：`playerIndex`, `cardId`, `serial`, `attackId`, `type`など）
- フィクスチャには実在のバトルログ`data/battle_logs/84580427.json`（Zammaar Shafqat Malhi vs Kagura_UT、166ステップ、Crustleウォールデッキ対Mega Lucario exデッキ）を使う。以下は事前に検証済みの実測値：
  - `info.Agents` = `[{"Name": "Zammaar Shafqat Malhi"}, {"Name": "Kagura_UT"}]`（player_index 0と1）
  - player_index=0視点で再構築したイベントタイムラインの総イベント数：**478件**
  - `playerIndex==1`（Kagura_UT）のATTACK（type=15）イベント数：**14件**、最初の1件は`step=20, attackId=981, cardId=677, serial=66`
  - 上記最初のATTACKイベント時点（step=20）でのserial=66のポケモンのエネルギー数：**1**（`energies=[6]`）
  - `playerIndex==1`のSWITCH（type=8）イベント数：**2件**
  - `playerIndex==1`のPLAY（type=10）イベント数：**25件**
  - player_index=1（Kagura_UT）の60枚デッキ内訳：Riolu(677)=4枚, Mega Lucario ex(678)=3枚, Ogerpon ex(117)=1枚
  - player_index=0（Zammaar Shafqat Malhi）の60枚デッキ内訳：Crustle(345)=4枚
  - `data/EN_Card_Data.csv`の`Rule`列は`{'ACE SPEC', 'Mega Pokémon ex', 'Pokémon ex', 'n/a'}`の4値のみ。ex判定は`"ex" in row["Rule"]`で安全に判定できる（この4値の中で"ex"を含むのは"Pokémon ex"と"Mega Pokémon ex"のみ）
  - `step=20`時点の`current.turn`は**3**

---

## Task 1: `src/etl/silver.py` の None-reward クラッシュ修正

**Files:**
- Modify: `src/etl/silver.py:19`
- Test: `tests/test_etl_silver.py`

**Interfaces:**
- Consumes: なし
- Produces: `parse_to_silver(bronze_path: Path, catalog_dir: Path) -> tuple[Path, Path]`（既存シグネチャ維持、`rewards`に`None`が含まれても例外を投げないことを保証）

- [ ] **Step 1: 既存テストファイルを確認する**

`tests/test_etl_silver.py`を読み、既存のフィクスチャ作成パターン（一時JSONファイルの作り方）を確認する。

- [ ] **Step 2: 失敗するテストを書く**

`tests/test_etl_silver.py`に追記：

```python
def test_parse_to_silver_handles_none_reward(tmp_path):
    """rewardsの片方がNone（タイムアウト等）でもクラッシュしないこと"""
    bronze_data = {
        "info": {
            "EpisodeId": 99999999,
            "Agents": [{"Name": "PlayerA"}, {"Name": "PlayerB"}],
        },
        "rewards": [1, None],
        "steps": [
            [
                {"observation": {"step": 0, "logs": []}, "action": None, "reward": 1, "status": "DONE"},
                {"observation": {"step": 0, "logs": []}, "action": None, "reward": None, "status": "DONE"},
            ]
        ],
    }
    bronze_path = tmp_path / "bronze_99999999.json"
    bronze_path.write_text(json.dumps(bronze_data), encoding="utf-8")
    catalog_dir = tmp_path / "catalog"

    summary_path, _ = parse_to_silver(bronze_path, catalog_dir)

    with summary_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["winner_index"] == "0"
    assert rows[0]["winner_name"] == "PlayerA"
```

ファイル冒頭のimportに`csv`と`json`が無ければ追加する。

- [ ] **Step 3: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_etl_silver.py::test_parse_to_silver_handles_none_reward -v`
Expected: FAIL（`TypeError: '>' not supported between instances of 'int' and 'NoneType'`）

- [ ] **Step 4: 最小実装で修正する**

`src/etl/silver.py:19`を修正：

```python
    # 報酬が最大のエージェントを勝者とする（Noneは最小値扱い：タイムアウト等で片方がNoneになる試合対策）
    winner_index = max(range(len(rewards)), key=lambda i: (rewards[i] is not None, rewards[i] or 0))
```

- [ ] **Step 5: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_etl_silver.py -v`
Expected: 全件PASS（既存テストも含めて回帰なし）

- [ ] **Step 6: コミット**

```bash
git add src/etl/silver.py tests/test_etl_silver.py
git commit -m "fix: silver.pyがrewardsのNoneでクラッシュする不具合を修正"
```

---

## Task 2: `src/etl/gold.py` 基盤関数（ログ読み込み・タイムライン再構築・プレイヤー特定）

**Files:**
- Create: `src/etl/gold.py`
- Test: `tests/test_etl_gold.py`
- Fixture: `data/battle_logs/84580427.json`（既存ファイルをそのまま使う）

**Interfaces:**
- Consumes: なし
- Produces:
  - `load_raw_log(log_path: Path) -> dict`
  - `find_player_index(data: dict, player_name: str) -> int`
  - `build_event_timeline(data: dict, player_index: int = 0) -> list[tuple[int, dict]]`（`(step_index, event_dict)`のリスト）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_etl_gold.py`を新規作成：

```python
import json
from pathlib import Path

import pytest

from etl.gold import build_event_timeline, find_player_index, load_raw_log

FIXTURE_PATH = Path(__file__).parent.parent / "data" / "battle_logs" / "84580427.json"


@pytest.fixture
def sample_log():
    return load_raw_log(FIXTURE_PATH)


def test_load_raw_log_reads_json(sample_log):
    assert sample_log["info"]["EpisodeId"] == 84580427


def test_find_player_index_matches_by_name(sample_log):
    assert find_player_index(sample_log, "Zammaar Shafqat Malhi") == 0
    assert find_player_index(sample_log, "Kagura_UT") == 1


def test_find_player_index_raises_when_not_found(sample_log):
    with pytest.raises(ValueError):
        find_player_index(sample_log, "Nonexistent Player")


def test_build_event_timeline_reconstructs_full_game(sample_log):
    timeline = build_event_timeline(sample_log, player_index=0)
    assert len(timeline) == 478
    # 最初のイベントはstep_indexを伴うタプルであること
    step_index, event = timeline[0]
    assert isinstance(step_index, int)
    assert "type" in event
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_etl_gold.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'etl.gold'`）

- [ ] **Step 3: 実装する**

`src/etl/gold.py`を新規作成：

```python
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
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_etl_gold.py -v`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add src/etl/gold.py tests/test_etl_gold.py
git commit -m "feat: gold.pyの基盤関数（ログ読み込み・タイムライン再構築）を追加"
```

---

## Task 3: `src/etl/gold.py` デッキリスト抽出・アーキタイプ分類

**Files:**
- Modify: `src/etl/gold.py`
- Test: `tests/test_etl_gold.py`

**Interfaces:**
- Consumes: なし（`data`引数はTask 2と同じ生JSON dict）
- Produces:
  - `extract_deck_list(data: dict, target_player_index: int) -> list[int]`
  - `load_card_names(csv_path: Path) -> dict[int, tuple[str, str]]`（`{card_id: (Card Name, Rule)}`）
  - `classify_archetype(deck_card_ids: list[int], card_names: dict[int, tuple[str, str]]) -> str`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_etl_gold.py`に追記：

```python
from etl.gold import classify_archetype, extract_deck_list, load_card_names

CARD_DATA_PATH = Path(__file__).parent.parent / "data" / "EN_Card_Data.csv"


def test_extract_deck_list_returns_60_cards(sample_log):
    deck0 = extract_deck_list(sample_log, target_player_index=0)
    deck1 = extract_deck_list(sample_log, target_player_index=1)
    assert len(deck0) == 60
    assert len(deck1) == 60
    assert deck0.count(345) == 4  # Crustle x4
    assert deck1.count(677) == 4  # Riolu x4
    assert deck1.count(678) == 3  # Mega Lucario ex x3


def test_load_card_names_maps_id_to_name_and_rule():
    card_names = load_card_names(CARD_DATA_PATH)
    assert card_names[678] == ("Mega Lucario ex", "Mega Pokémon ex")
    assert card_names[345] == ("Crustle", "n/a")


def test_classify_archetype_lists_ex_pokemon_by_count(sample_log):
    card_names = load_card_names(CARD_DATA_PATH)
    deck1 = extract_deck_list(sample_log, target_player_index=1)
    label = classify_archetype(deck1, card_names)
    assert "Mega Lucario ex" in label
    assert "Cornerstone Mask Ogerpon ex" in label


def test_classify_archetype_returns_placeholder_when_no_ex(sample_log):
    card_names = load_card_names(CARD_DATA_PATH)
    label = classify_archetype([1, 2, 3], card_names)  # ex非該当の適当なID
    assert label == "(exなし)"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_etl_gold.py -v -k "deck_list or card_names or archetype"`
Expected: FAIL（該当関数が未定義）

- [ ] **Step 3: 実装する**

`src/etl/gold.py`に追記：

```python
import collections
import csv


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
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_etl_gold.py -v`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add src/etl/gold.py tests/test_etl_gold.py
git commit -m "feat: gold.pyにデッキリスト抽出・アーキタイプ分類を追加"
```

---

## Task 4: `src/etl/gold.py` 意思決定イベント抽出（技選択・入れ替え・サポートカード）

**Files:**
- Modify: `src/etl/gold.py`
- Test: `tests/test_etl_gold.py`

**Interfaces:**
- Consumes: `build_event_timeline`（Task 2）
- Produces:
  - `extract_attack_events(data: dict, target_player_index: int) -> list[dict]`（各要素: `{"step", "turn", "attack_id", "card_id", "serial", "energy_count"}`）
  - `extract_switch_events(data: dict, target_player_index: int) -> list[dict]`（各要素: `{"step", "turn", "card_id_active", "card_id_bench"}`）
  - `extract_play_events(data: dict, target_player_index: int) -> list[dict]`（各要素: `{"step", "turn", "card_id", "serial"}`）
  - `extract_result_reason(data: dict) -> int | None`（決着理由。1=プライズ0/2=デッキアウト/3=バトル場0/4=カード効果。見つからなければNone）

**既知の制約：** フィクスチャ`84580427.json`（166ステップで試合終了、`rewards=[1, -1]`で決着済み）を調査したところ、RESULT（type=23）イベントは一度も記録されていなかった（生ログが決着直前で打ち切られている可能性がある）。そのため`extract_result_reason`は「見つかれば返す、見つからなければNoneを返す」ベストエフォート実装とする。勝敗自体はsilver.pyの`winner_name`で確実に取得できるため、これは情報の欠落であってツールの不具合ではない。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_etl_gold.py`に追記：

```python
from etl.gold import extract_attack_events, extract_play_events, extract_switch_events


def test_extract_attack_events_includes_energy_count_at_that_time(sample_log):
    attacks = extract_attack_events(sample_log, target_player_index=1)
    assert len(attacks) == 14
    first = attacks[0]
    assert first["step"] == 20
    assert first["turn"] == 3
    assert first["attack_id"] == 981
    assert first["card_id"] == 677
    assert first["serial"] == 66
    assert first["energy_count"] == 1


def test_extract_switch_events_count(sample_log):
    switches = extract_switch_events(sample_log, target_player_index=1)
    assert len(switches) == 2


def test_extract_play_events_count(sample_log):
    plays = extract_play_events(sample_log, target_player_index=1)
    assert len(plays) == 25


def test_extract_result_reason_returns_none_when_absent(sample_log):
    # フィクスチャ84580427.jsonはRESULTログイベントが記録されていない既知のケース
    from etl.gold import extract_result_reason
    assert extract_result_reason(sample_log) is None
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_etl_gold.py -v -k "attack_events or switch_events or play_events or result_reason"`
Expected: FAIL（該当関数が未定義）

- [ ] **Step 3: 実装する**

`src/etl/gold.py`に追記：

```python
LOG_TYPE_SWITCH = 8
LOG_TYPE_PLAY = 10
LOG_TYPE_ATTACK = 15
LOG_TYPE_RESULT = 23


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
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_etl_gold.py -v`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add src/etl/gold.py tests/test_etl_gold.py
git commit -m "feat: gold.pyに技選択・入れ替え・カードプレイ・決着理由のイベント抽出を追加"
```

---

## Task 5: `scripts/analyze_top10_meta.py` 集約CLI

**Files:**
- Create: `scripts/analyze_top10_meta.py`
- Create: `data/top10_meta_targets.csv`（サンプル：既存ログのうち`84580427,Kagura_UT`のみを含む1行、実運用ではユーザーがTOP10の30行に差し替える）
- Test: `tests/test_analyze_top10_meta.py`

**Interfaces:**
- Consumes:
  - `etl.bronze.copy_to_bronze(src_path: Path, catalog_dir: Path) -> Path`（既存）
  - `etl.silver.parse_to_silver(bronze_path: Path, catalog_dir: Path) -> tuple[Path, Path]`（既存、Task 1で修正済み）
  - `etl.gold.load_raw_log`, `find_player_index`, `extract_deck_list`, `load_card_names`, `classify_archetype`, `extract_attack_events`, `extract_play_events`（Task 2〜4）
- Produces: `build_report(targets_csv: Path, battle_logs_dir: Path, card_data_csv: Path, catalog_dir: Path) -> str`（Markdown文字列を返す。CLIの`main()`はこれをファイルに書き出す薄いラッパー）

**スコープ判断：** Task 4で実装する`extract_switch_events`/`extract_result_reason`は、本タスクのレポートには含めない（意図的）。設計書の「意思決定パターンの記述統計」は「アタッカー別エネルギー数」「サポートカード使用ターン」を代表例として挙げているのみで網羅を求めていない。入れ替えタイミング・決着理由は、レポートを見て個別のログをさらに深掘りしたくなった際に`gold.py`の関数を直接呼んで使う「再利用可能な部品」として提供する（設計書の「将来の別調査にも再利用できる汎用モジュール」という位置づけ通り）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_analyze_top10_meta.py`を新規作成：

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analyze_top10_meta import build_report

DATA_DIR = Path(__file__).parent.parent / "data"


def test_build_report_includes_deck_and_decision_sections(tmp_path):
    targets_csv = tmp_path / "targets.csv"
    targets_csv.write_text(
        "# 形式: episode_id,target_player_name\n"
        "84580427,Kagura_UT\n",
        encoding="utf-8",
    )
    catalog_dir = tmp_path / "catalog"

    report = build_report(
        targets_csv=targets_csv,
        battle_logs_dir=DATA_DIR / "battle_logs",
        card_data_csv=DATA_DIR / "EN_Card_Data.csv",
        catalog_dir=catalog_dir,
    )

    assert "# TOP10メタ分析レポート" in report
    assert "Kagura_UT" in report
    assert "Mega Lucario ex" in report  # デッキ分布に含まれる
    assert "アーキタイプ別出現回数" in report  # 集計セクションが存在する
    assert "84580427" in report  # 生ログへのリンクとして残る
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_analyze_top10_meta.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'analyze_top10_meta'`）

- [ ] **Step 3: 実装する**

`scripts/analyze_top10_meta.py`を新規作成：

```python
"""TOP10メタ分析CLI。data/top10_meta_targets.csvを読み、対象バトルログを
デッキ分布・意思決定パターンの2観点で集約したMarkdownレポートを生成する。

使い方: uv run python scripts/analyze_top10_meta.py [targets_csv]
（省略時は data/top10_meta_targets.csv を使う）
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from etl.bronze import copy_to_bronze
from etl.gold import (
    classify_archetype,
    extract_attack_events,
    extract_deck_list,
    extract_play_events,
    extract_switch_events,
    find_player_index,
    load_card_names,
    load_raw_log,
)
from etl.silver import parse_to_silver


def _read_targets(targets_csv: Path) -> list[tuple[int, str]]:
    """targets_csvから(episode_id, target_player_name)のリストを読む（#始まりはコメント）"""
    targets = []
    with targets_csv.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            episode_id_str, player_name = line.split(",", 1)
            targets.append((int(episode_id_str), player_name))
    return targets


def build_report(
    targets_csv: Path,
    battle_logs_dir: Path,
    card_data_csv: Path,
    catalog_dir: Path,
) -> str:
    """対象ログを集計し、Markdownレポートを文字列として返す"""
    card_names = load_card_names(card_data_csv)
    deck_rows = []
    attack_rows = []
    play_rows = []

    for episode_id, player_name in _read_targets(targets_csv):
        src_path = battle_logs_dir / f"{episode_id}.json"
        bronze_path = copy_to_bronze(src_path, catalog_dir)
        summary_path, _ = parse_to_silver(bronze_path, catalog_dir)
        with summary_path.open(encoding="utf-8") as f:
            summary = next(csv.DictReader(f))

        data = load_raw_log(src_path)
        target_index = find_player_index(data, player_name)
        deck_ids = extract_deck_list(data, target_index)
        archetype = classify_archetype(deck_ids, card_names)
        won = summary["winner_name"] == player_name

        deck_rows.append({
            "episode_id": episode_id,
            "player_name": player_name,
            "archetype": archetype,
            "won": won,
            "total_steps": summary["total_steps"],
        })

        for attack in extract_attack_events(data, target_index):
            card_id = attack["card_id"]
            card_label = card_names.get(card_id, (str(card_id), ""))[0]
            attack_rows.append({**attack, "episode_id": episode_id, "card_label": card_label})

        for play in extract_play_events(data, target_index):
            card_id = play["card_id"]
            card_label = card_names.get(card_id, (str(card_id), ""))[0]
            play_rows.append({**play, "episode_id": episode_id, "card_label": card_label})

    return _render_markdown(deck_rows, attack_rows, play_rows)


def _render_markdown(deck_rows: list[dict], attack_rows: list[dict], play_rows: list[dict]) -> str:
    lines = ["# TOP10メタ分析レポート", ""]

    lines.append("## デッキ分布")
    lines.append("")
    lines.append("| episode_id | プレイヤー | アーキタイプ | 勝敗 | ターン数 |")
    lines.append("|---|---|---|---|---|")
    for row in deck_rows:
        result = "勝ち" if row["won"] else "負け"
        lines.append(
            f"| {row['episode_id']} | {row['player_name']} | {row['archetype']} | "
            f"{result} | {row['total_steps']} |"
        )
    lines.append("")

    lines.append("### アーキタイプ別出現回数")
    lines.append("")
    lines.append("| アーキタイプ | 出現回数 |")
    lines.append("|---|---|")
    archetype_counts: dict[str, int] = {}
    for row in deck_rows:
        archetype_counts[row["archetype"]] = archetype_counts.get(row["archetype"], 0) + 1
    for archetype, count in sorted(archetype_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {archetype} | {count} |")
    lines.append("")

    lines.append("## 意思決定パターン：アタッカー別エネルギー数")
    lines.append("")
    lines.append("| アタッカー | 使用回数 | 平均エネルギー数（使用時点） |")
    lines.append("|---|---|---|")
    by_attacker: dict[str, list[int]] = {}
    for row in attack_rows:
        if row["energy_count"] is None:
            continue
        by_attacker.setdefault(row["card_label"], []).append(row["energy_count"])
    for label, counts in sorted(by_attacker.items()):
        avg = sum(counts) / len(counts)
        lines.append(f"| {label} | {len(counts)} | {avg:.1f} |")
    lines.append("")

    lines.append("## 意思決定パターン：サポート/トレーナーズカード使用ターン")
    lines.append("")
    lines.append("| カード | 使用回数 | 平均使用ターン |")
    lines.append("|---|---|---|")
    by_card: dict[str, list[int]] = {}
    for row in play_rows:
        by_card.setdefault(row["card_label"], []).append(row["turn"])
    for label, turns in sorted(by_card.items()):
        avg = sum(turns) / len(turns)
        lines.append(f"| {label} | {len(turns)} | {avg:.1f} |")
    lines.append("")

    lines.append("## 参照した生ログ")
    lines.append("")
    for row in deck_rows:
        lines.append(f"- `data/battle_logs/{row['episode_id']}.json`（{row['player_name']}）")

    return "\n".join(lines)


def main() -> None:
    targets_csv = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/top10_meta_targets.csv")
    repo_root = Path(__file__).parent.parent
    report = build_report(
        targets_csv=targets_csv,
        battle_logs_dir=repo_root / "data" / "battle_logs",
        card_data_csv=repo_root / "data" / "EN_Card_Data.csv",
        catalog_dir=repo_root / "data" / "unity-catalog",
    )
    output_dir = repo_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    import datetime
    today = datetime.date.today().isoformat().replace("-", "")
    output_path = output_dir / f"top10_meta_report_{today}.md"
    output_path.write_text(report, encoding="utf-8")
    print(f"レポートを出力しました: {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_analyze_top10_meta.py -v`
Expected: PASS

- [ ] **Step 5: サンプルの`data/top10_meta_targets.csv`を作成する**

```
# TOP10メタ分析対象ログ一覧
# 形式: episode_id,target_player_name
# target_player_name は info.Agents の名前と完全一致させ、そのログ内で分析対象とする側（TOP10プレイヤー側）を明示する
#
# 以下はサンプル1行（動作確認用）。実運用ではユーザーが現行LB TOP10の30行に差し替える。
84580427,Kagura_UT
```

- [ ] **Step 6: 実際にCLIを実行して確認する**

Run: `uv run python scripts/analyze_top10_meta.py`
Expected: `output/top10_meta_report_<今日の日付>.md` が生成され、標準出力にそのパスが表示される。生成されたファイルを開き、「デッキ分布」「アタッカー別エネルギー数」「サポート/トレーナーズカード使用ターン」「参照した生ログ」の4セクションが存在することを目視確認する。

- [ ] **Step 7: リポジトリ全体の回帰テストを実行する**

Run: `uv run pytest -q`
Expected: 全件PASS（既存テストの回帰なし）

- [ ] **Step 8: コミット**

```bash
git add scripts/analyze_top10_meta.py tests/test_analyze_top10_meta.py data/top10_meta_targets.csv
git commit -m "feat: TOP10メタ分析の集約CLIとサンプルtargetsファイルを追加"
```

---

## 実装後のユーザー作業（このプラン範囲外）

1. Kaggleの現行LB上位10名を確認し、それぞれの直近3試合分のバトルログJSONを手動DLして`data/battle_logs/`に配置する
2. `data/top10_meta_targets.csv`をサンプル1行から実際の30行（`episode_id,target_player_name`）に差し替える
3. `uv run python scripts/analyze_top10_meta.py`を実行し、`output/top10_meta_report_<日付>.md`を確認する
4. レポート内容を踏まえ、次回セッションでRLサブプロジェクト①（デッキ設計）のスコープを決定する
