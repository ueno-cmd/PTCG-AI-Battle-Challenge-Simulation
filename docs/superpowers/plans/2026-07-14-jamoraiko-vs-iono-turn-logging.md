# ジャモライコ vs イオナサンプル 校正実験：手番選択ログ出力機能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ジャモライコ vs イオナサンプル校正ノートブックに、最初の10試合分の対戦中の手番選択（OptionType/選択肢一覧/盤面/イベントログ）をJSONファイルとして出力する機能を追加する。

**Architecture:** `scripts/build_jamoraiko_vs_iono_notebook.py` にcg非依存の純粋関数群（列挙型の名前引きマップ、選択肢/イベントの圧縮、盤面スナップショット抽出、手番ログレコード組み立て）を追加し、`inspect.getsource()`でノートブックセルに埋め込む。既存の`play_game`/`run_series`にオプション引数を追加し、最初の10試合だけログを収集して新規JSONファイルに保存する。既存200試合の勝率計測ロジック・出力は変更しない。

**Tech Stack:** Python 3.12 / uv / pytest（既存プロジェクトのビルドスクリプト・テストパターンに準拠）

## Global Constraints

- ログ対象は最初の10試合のみ（`LOG_FIRST_N = 10`）。200試合本体は現状のまま実行する
- 新規追加する関数は`cg`ライブラリに一切依存しない、プレーンな`dict`操作のみで構成する（ローカルでの単体テストを可能にするため）
- 出力ファイル名は `jamoraiko_vs_iono_turn_log.json`、保存先は既存の`OUT_DIR`（`/kaggle/working`）
- `select.type`は`SelectType`、`select.context`は`SelectContext`、各`option.type`は`OptionType`という異なる列挙型であることに注意し、混同しない（詳細は設計書参照）
- 設計書: `docs/superpowers/specs/2026-07-14-jamoraiko-vs-iono-turn-logging-design.md`

---

## Task 1: 列挙型の名前引きマップ + compact_option/compact_log_entry

**Files:**
- Modify: `scripts/build_jamoraiko_vs_iono_notebook.py:117-120`（`_patch_iono_deck_load`の終わりと`code_cell`の間に新規関数を追加）
- Test: `tests/test_jamoraiko_vs_iono_notebook_build.py`（末尾に新規テストクラス追加）

**Interfaces:**
- Produces: `SELECT_TYPE_NAMES: dict[int, str]`、`SELECT_CONTEXT_NAMES: dict[int, str]`、`compact_option(option: dict) -> dict`、`compact_log_entry(log: dict) -> dict`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_jamoraiko_vs_iono_notebook_build.py` の末尾に追記：

```python
class TestEnumNameMaps:
    def test_select_type_names_cover_card_and_main(self):
        assert _mod.SELECT_TYPE_NAMES[0] == "MAIN"
        assert _mod.SELECT_TYPE_NAMES[1] == "CARD"

    def test_select_context_names_cover_switch_and_to_hand(self):
        assert _mod.SELECT_CONTEXT_NAMES[3] == "SWITCH"
        assert _mod.SELECT_CONTEXT_NAMES[7] == "TO_HAND"
        assert _mod.SELECT_CONTEXT_NAMES[48] == "RECOVER_SPECIAL_CONDITION"


class TestCompactOption:
    def test_removes_none_fields(self):
        option = {"type": 3, "area": 5, "index": 0, "playerIndex": 0, "cardId": 63,
                   "number": None, "toolIndex": None, "attackId": None}
        result = _mod.compact_option(option)
        assert result == {"type": 3, "area": 5, "index": 0, "playerIndex": 0, "cardId": 63}

    def test_keeps_falsy_but_non_none_fields(self):
        option = {"type": 13, "attackId": 0, "index": None}
        result = _mod.compact_option(option)
        assert result == {"type": 13, "attackId": 0}


class TestCompactLogEntry:
    def test_removes_none_fields(self):
        log = {"type": 16, "playerIndex": 0, "cardId": 63, "value": -30,
               "serial": None, "putDamageCounter": None}
        result = _mod.compact_log_entry(log)
        assert result == {"type": 16, "playerIndex": 0, "cardId": 63, "value": -30}
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_jamoraiko_vs_iono_notebook_build.py -v -k "TestEnumNameMaps or TestCompactOption or TestCompactLogEntry"`
Expected: FAIL（`AttributeError: module 'build_jvi_nb' has no attribute 'SELECT_TYPE_NAMES'`等）

- [ ] **Step 3: 最小実装を書く**

`scripts/build_jamoraiko_vs_iono_notebook.py:117` の直後（`return iono_source.replace(...)`の次、`def code_cell`の前）に挿入：

```python

SELECT_TYPE_NAMES: dict[int, str] = {
    0: "MAIN", 1: "CARD", 2: "ATTACHED_CARD", 3: "CARD_OR_ATTACHED_CARD",
    4: "ENERGY", 5: "SKILL", 6: "ATTACK", 7: "EVOLVE", 8: "COUNT",
    9: "YES_NO", 10: "SPECIAL_CONDITION",
}

SELECT_CONTEXT_NAMES: dict[int, str] = {
    0: "MAIN", 1: "SETUP_ACTIVE_POKEMON", 2: "SETUP_BENCH_POKEMON", 3: "SWITCH",
    4: "TO_ACTIVE", 5: "TO_BENCH", 6: "TO_FIELD", 7: "TO_HAND", 8: "DISCARD",
    9: "TO_DECK", 10: "TO_DECK_BOTTOM", 11: "TO_PRIZE", 12: "NOT_MOVE",
    13: "DAMAGE_COUNTER", 14: "DAMAGE_COUNTER_ANY", 15: "DAMAGE",
    16: "REMOVE_DAMAGE_COUNTER", 17: "HEAL", 18: "EVOLVES_FROM", 19: "EVOLVES_TO",
    20: "DEVOLVE", 21: "ATTACH_FROM", 22: "ATTACH_TO", 23: "DETACH_FROM", 24: "LOOK",
    25: "EFFECT_TARGET", 26: "DISCARD_ENERGY_CARD", 27: "DISCARD_TOOL_CARD",
    28: "SWITCH_ENERGY_CARD", 29: "DISCARD_CARD_OR_ATTACHED_CARD", 30: "DISCARD_ENERGY",
    31: "TO_HAND_ENERGY", 32: "TO_DECK_ENERGY", 33: "SWITCH_ENERGY", 34: "SKILL_ORDER",
    35: "ATTACK", 36: "DISABLE_ATTACK", 37: "EVOLVE", 38: "DRAW_COUNT",
    39: "DAMAGE_COUNTER_COUNT", 40: "REMOVE_DAMAGE_COUNTER_COUNT", 41: "IS_FIRST",
    42: "MULLIGAN", 43: "ACTIVATE", 44: "FIRST_EFFECT", 45: "MORE_DEVOLVE",
    46: "COIN_HEAD", 47: "AFFECT_SPECIAL_CONDITION", 48: "RECOVER_SPECIAL_CONDITION",
}


def compact_option(option: dict) -> dict:
    """Option dictからNoneのフィールドを除いたコンパクトな辞書を返す"""
    return {k: v for k, v in option.items() if v is not None}


def compact_log_entry(log: dict) -> dict:
    """Log dictからNoneのフィールドを除いたコンパクトな辞書を返す"""
    return {k: v for k, v in log.items() if v is not None}

```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_jamoraiko_vs_iono_notebook_build.py -v -k "TestEnumNameMaps or TestCompactOption or TestCompactLogEntry"`
Expected: PASS（5件）

- [ ] **Step 5: コミット**

```bash
git add scripts/build_jamoraiko_vs_iono_notebook.py tests/test_jamoraiko_vs_iono_notebook_build.py
git commit -m "feat: 手番ログ用の列挙型名前引きマップとcompact_option/compact_log_entryを追加"
```

---

## Task 2: board_snapshot（盤面スナップショット抽出）

**Files:**
- Modify: `scripts/build_jamoraiko_vs_iono_notebook.py`（Task 1で追加した`compact_log_entry`の直後に追加）
- Test: `tests/test_jamoraiko_vs_iono_notebook_build.py`（末尾に新規テストクラス追加）

**Interfaces:**
- Consumes: なし（cg非依存のプレーンなdict操作）
- Produces: `board_snapshot(state: dict, my_index: int) -> dict`（内部で`_pokemon_summary(pokemon: dict | None) -> dict | None`を使用）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_jamoraiko_vs_iono_notebook_build.py` の末尾に追記：

```python
class TestBoardSnapshot:
    def _fake_pokemon(self, card_id, hp, max_hp, energy_count):
        return {"id": card_id, "serial": 1, "hp": hp, "maxHp": max_hp,
                "appearThisTurn": False, "energies": [4] * energy_count,
                "energyCards": [], "tools": [], "preEvolution": []}

    def test_extracts_id_hp_maxhp_energycount_for_active_and_bench(self):
        state = {
            "players": [
                {
                    "active": [self._fake_pokemon(63, 90, 190, 2)],
                    "bench": [self._fake_pokemon(71, 130, 130, 1)],
                },
                {
                    "active": [self._fake_pokemon(269, 150, 190, 3)],
                    "bench": [],
                },
            ]
        }
        result = _mod.board_snapshot(state, my_index=0)
        assert result == {
            "mine": {
                "active": [{"id": 63, "hp": 90, "maxHp": 190, "energyCount": 2}],
                "bench": [{"id": 71, "hp": 130, "maxHp": 130, "energyCount": 1}],
            },
            "opponent": {
                "active": [{"id": 269, "hp": 150, "maxHp": 190, "energyCount": 3}],
                "bench": [],
            },
        }

    def test_handles_empty_active_slot_without_crashing(self):
        state = {
            "players": [
                {"active": [None], "bench": []},
                {"active": [self._fake_pokemon(269, 150, 190, 3)], "bench": []},
            ]
        }
        result = _mod.board_snapshot(state, my_index=0)
        assert result["mine"]["active"] == [None]

    def test_resolves_opponent_relative_to_my_index(self):
        state = {
            "players": [
                {"active": [self._fake_pokemon(1, 100, 100, 0)], "bench": []},
                {"active": [self._fake_pokemon(2, 100, 100, 0)], "bench": []},
            ]
        }
        result = _mod.board_snapshot(state, my_index=1)
        assert result["mine"]["active"][0]["id"] == 2
        assert result["opponent"]["active"][0]["id"] == 1
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_jamoraiko_vs_iono_notebook_build.py -v -k TestBoardSnapshot`
Expected: FAIL（`AttributeError: module 'build_jvi_nb' has no attribute 'board_snapshot'`）

- [ ] **Step 3: 最小実装を書く**

`compact_log_entry`関数定義の直後に追加：

```python

def _pokemon_summary(pokemon: dict | None) -> dict | None:
    """Pokemon dictからid・hp・maxHp・energyCountのみを抽出する（Noneならそのまま返す）"""
    if pokemon is None:
        return None
    return {
        "id": pokemon["id"],
        "hp": pokemon["hp"],
        "maxHp": pokemon["maxHp"],
        "energyCount": len(pokemon["energies"]),
    }


def board_snapshot(state: dict, my_index: int) -> dict:
    """obs['current']から両者のアクティブ/ベンチのid・hp・maxHp・energyCountのみを抽出する"""
    players = state["players"]
    mine = players[my_index]
    opponent = players[1 - my_index]
    return {
        "mine": {
            "active": [_pokemon_summary(p) for p in mine["active"]],
            "bench": [_pokemon_summary(p) for p in mine["bench"]],
        },
        "opponent": {
            "active": [_pokemon_summary(p) for p in opponent["active"]],
            "bench": [_pokemon_summary(p) for p in opponent["bench"]],
        },
    }

```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_jamoraiko_vs_iono_notebook_build.py -v -k TestBoardSnapshot`
Expected: PASS（3件）

- [ ] **Step 5: コミット**

```bash
git add scripts/build_jamoraiko_vs_iono_notebook.py tests/test_jamoraiko_vs_iono_notebook_build.py
git commit -m "feat: 手番ログ用のboard_snapshot（盤面スナップショット抽出）を追加"
```

---

## Task 3: build_turn_log_entry（1手番分のログレコード組み立て）

**Files:**
- Modify: `scripts/build_jamoraiko_vs_iono_notebook.py`（Task 2で追加した`board_snapshot`の直後に追加）
- Test: `tests/test_jamoraiko_vs_iono_notebook_build.py`（末尾に新規テストクラス追加）

**Interfaces:**
- Consumes: `SELECT_TYPE_NAMES`/`SELECT_CONTEXT_NAMES`（Task 1）、`compact_option`/`compact_log_entry`（Task 1）、`board_snapshot`（Task 2）
- Produces: `build_turn_log_entry(obs: dict, selected: list[int], game_index: int, step: int, agent_name: str) -> dict`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_jamoraiko_vs_iono_notebook_build.py` の末尾に追記：

```python
class TestBuildTurnLogEntry:
    def _fake_pokemon(self, card_id, hp, max_hp, energy_count):
        return {"id": card_id, "serial": 1, "hp": hp, "maxHp": max_hp,
                "appearThisTurn": False, "energies": [4] * energy_count,
                "energyCards": [], "tools": [], "preEvolution": []}

    def _fake_obs(self):
        return {
            "select": {
                "type": 1,  # SelectType.CARD
                "context": 3,  # SelectContext.SWITCH
                "minCount": 1, "maxCount": 1,
                "option": [
                    {"type": 3, "area": 5, "index": 0, "playerIndex": 0, "cardId": 63,
                     "number": None, "toolIndex": None, "energyIndex": None, "count": None,
                     "inPlayArea": None, "inPlayIndex": None, "attackId": None,
                     "serial": None, "specialConditionType": None},
                    {"type": 3, "area": 5, "index": 1, "playerIndex": 0, "cardId": 71,
                     "number": None, "toolIndex": None, "energyIndex": None, "count": None,
                     "inPlayArea": None, "inPlayIndex": None, "attackId": None,
                     "serial": None, "specialConditionType": None},
                ],
                "deck": None, "contextCard": None, "effect": None,
                "remainDamageCounter": 0, "remainEnergyCost": 0,
            },
            "current": {
                "turn": 2, "turnActionCount": 1, "yourIndex": 0, "firstPlayer": 0,
                "supporterPlayed": False, "stadiumPlayed": False, "energyAttached": False,
                "retreated": False, "result": -1, "stadium": [], "looking": None,
                "players": [
                    {"active": [self._fake_pokemon(63, 90, 190, 2)],
                     "bench": [self._fake_pokemon(71, 130, 130, 1)]},
                    {"active": [self._fake_pokemon(269, 150, 190, 3)], "bench": []},
                ],
            },
            "logs": [
                {"type": 16, "playerIndex": 0, "cardId": 63, "value": -30,
                 "serial": None, "putDamageCounter": None},
            ],
        }

    def test_resolves_selected_options_from_indices(self):
        entry = _mod.build_turn_log_entry(self._fake_obs(), [1], game_index=0, step=3, agent_name="jamoraiko")
        assert entry["selected_indices"] == [1]
        assert entry["selected_options"] == [{"type": 3, "area": 5, "index": 1, "playerIndex": 0, "cardId": 71}]

    def test_labels_select_type_and_context(self):
        entry = _mod.build_turn_log_entry(self._fake_obs(), [1], game_index=0, step=3, agent_name="jamoraiko")
        assert entry["select_type"] == 1
        assert entry["select_type_name"] == "CARD"
        assert entry["select_context"] == 3
        assert entry["select_context_name"] == "SWITCH"

    def test_includes_all_offered_options(self):
        entry = _mod.build_turn_log_entry(self._fake_obs(), [1], game_index=0, step=3, agent_name="jamoraiko")
        assert len(entry["options"]) == 2
        assert entry["options"][0]["cardId"] == 63
        assert entry["options"][1]["cardId"] == 71

    def test_includes_board_snapshot_and_logs(self):
        entry = _mod.build_turn_log_entry(self._fake_obs(), [1], game_index=0, step=3, agent_name="jamoraiko")
        assert entry["board"]["mine"]["active"][0]["id"] == 63
        assert entry["board"]["opponent"]["active"][0]["id"] == 269
        assert entry["logs_since_last"] == [{"type": 16, "playerIndex": 0, "cardId": 63, "value": -30}]

    def test_falls_back_to_question_mark_for_unknown_enum_value(self):
        obs = self._fake_obs()
        obs["select"]["type"] = 999
        obs["select"]["context"] = 999
        entry = _mod.build_turn_log_entry(obs, [0], game_index=0, step=0, agent_name="iono")
        assert entry["select_type_name"] == "?"
        assert entry["select_context_name"] == "?"

    def test_carries_game_index_step_turn_player_and_agent_name(self):
        entry = _mod.build_turn_log_entry(self._fake_obs(), [1], game_index=5, step=12, agent_name="jamoraiko")
        assert entry["game_index"] == 5
        assert entry["step"] == 12
        assert entry["turn"] == 2
        assert entry["player_index"] == 0
        assert entry["agent"] == "jamoraiko"
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_jamoraiko_vs_iono_notebook_build.py -v -k TestBuildTurnLogEntry`
Expected: FAIL（`AttributeError: module 'build_jvi_nb' has no attribute 'build_turn_log_entry'`）

- [ ] **Step 3: 最小実装を書く**

`board_snapshot`関数定義の直後に追加：

```python

def build_turn_log_entry(obs: dict, selected: list[int], game_index: int, step: int, agent_name: str) -> dict:
    """1手番分のログレコードを組み立てる"""
    select = obs["select"]
    state = obs["current"]
    my_index = state["yourIndex"]
    options = select["option"]
    return {
        "game_index": game_index,
        "step": step,
        "turn": state["turn"],
        "player_index": my_index,
        "agent": agent_name,
        "select_type": select["type"],
        "select_type_name": SELECT_TYPE_NAMES.get(select["type"], "?"),
        "select_context": select["context"],
        "select_context_name": SELECT_CONTEXT_NAMES.get(select["context"], "?"),
        "options": [compact_option(o) for o in options],
        "selected_indices": list(selected),
        "selected_options": [compact_option(options[i]) for i in selected],
        "board": board_snapshot(state, my_index),
        "logs_since_last": [compact_log_entry(entry) for entry in obs.get("logs", [])],
    }

```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_jamoraiko_vs_iono_notebook_build.py -v -k TestBuildTurnLogEntry`
Expected: PASS（6件）

- [ ] **Step 5: 全体回帰を確認してコミット**

Run: `uv run pytest -q`
Expected: 全件PASS（既存451件＋今回追加分）

```bash
git add scripts/build_jamoraiko_vs_iono_notebook.py tests/test_jamoraiko_vs_iono_notebook_build.py
git commit -m "feat: 手番ログ用のbuild_turn_log_entryを追加（enum名前引き・盤面・イベントログを統合）"
```

---

## Task 4: ハーネス/校正実験への配線 + ノートブック生成

**Files:**
- Modify: `scripts/build_jamoraiko_vs_iono_notebook.py:131-146`（`NOTE_MD`）
- Modify: `scripts/build_jamoraiko_vs_iono_notebook.py:157-182`（`HARNESS_CODE`）
- Modify: `scripts/build_jamoraiko_vs_iono_notebook.py:192-223`（`CALIBRATION_CODE`）
- Modify: `scripts/build_jamoraiko_vs_iono_notebook.py`（`SAVE_CODE`の直後に`SAVE_LOG_CODE`を新規追加）
- Modify: `scripts/build_jamoraiko_vs_iono_notebook.py:289-311`（`load_helper_src`の直後に`turn_log_helpers_src`を追加、`main()`内の`cells`リストに2セル追加）
- Test: `tests/test_jamoraiko_vs_iono_notebook_build.py`（先頭に`import json`追加、末尾に新規テストクラス追加）

**Interfaces:**
- Consumes: `SELECT_TYPE_NAMES`/`SELECT_CONTEXT_NAMES`/`compact_option`/`compact_log_entry`/`board_snapshot`/`build_turn_log_entry`（Task 1〜3、`inspect.getsource()`で埋め込む）
- Produces: 生成ノートブックに`turn-log-helpers`セルと`save-turn-log`セルが追加される。ノートブック実行結果として`/kaggle/working/jamoraiko_vs_iono_turn_log.json`が出力される（Kaggle実行時のみ、ローカルでは未検証）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_jamoraiko_vs_iono_notebook_build.py` の先頭のimport群に`import json`を追加（`import importlib.util`の前に挿入）：

```python
import importlib.util
import json
import types
from pathlib import Path
```

同ファイル末尾に追記：

```python
class TestMainBuildsNotebookWithTurnLogging:
    """main()が生成する全コードセルが構文的に正しいPythonであること、
    および手番ログ配線が実際にノートブックへ反映されていることを検証する。
    実行そのもの（cg依存）はローカルでは検証できない。"""

    def test_all_code_cells_are_valid_python(self):
        _mod.main()
        nb = json.loads(_mod.DST.read_text(encoding="utf-8"))
        for cell in nb["cells"]:
            if cell["cell_type"] != "code":
                continue
            compile(cell["source"], cell["id"], "exec")

    def test_harness_cell_wires_turn_log_sink(self):
        _mod.main()
        nb = json.loads(_mod.DST.read_text(encoding="utf-8"))
        cells = {c["id"]: c for c in nb["cells"]}
        assert "turn_log_sink" in cells["battle-harness"]["source"]
        assert "build_turn_log_entry" in cells["battle-harness"]["source"]

    def test_turn_log_helpers_cell_defines_build_turn_log_entry(self):
        _mod.main()
        nb = json.loads(_mod.DST.read_text(encoding="utf-8"))
        cells = {c["id"]: c for c in nb["cells"]}
        assert "def build_turn_log_entry" in cells["turn-log-helpers"]["source"]
        assert "SELECT_TYPE_NAMES" in cells["turn-log-helpers"]["source"]

    def test_calibration_cell_logs_first_n_games(self):
        _mod.main()
        nb = json.loads(_mod.DST.read_text(encoding="utf-8"))
        cells = {c["id"]: c for c in nb["cells"]}
        assert "LOG_FIRST_N" in cells["calibration-run"]["source"]
        assert "log_first_n" in cells["calibration-run"]["source"]

    def test_save_turn_log_cell_writes_expected_filename(self):
        _mod.main()
        nb = json.loads(_mod.DST.read_text(encoding="utf-8"))
        cells = {c["id"]: c for c in nb["cells"]}
        assert "jamoraiko_vs_iono_turn_log.json" in cells["save-turn-log"]["source"]

    def test_cell_order_places_helpers_before_harness_before_calibration(self):
        _mod.main()
        nb = json.loads(_mod.DST.read_text(encoding="utf-8"))
        ids = [c["id"] for c in nb["cells"]]
        assert ids.index("turn-log-helpers") < ids.index("battle-harness")
        assert ids.index("battle-harness") < ids.index("calibration-run")
        assert ids.index("save-results") < ids.index("save-turn-log")
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_jamoraiko_vs_iono_notebook_build.py -v -k TestMainBuildsNotebookWithTurnLogging`
Expected: FAIL（`KeyError: 'turn-log-helpers'`または`KeyError: 'save-turn-log'`、現時点ではまだそのセルが存在しないため）

- [ ] **Step 3a: NOTE_MDを更新する**

`scripts/build_jamoraiko_vs_iono_notebook.py:131-146`の`NOTE_MD`定義全体を以下に置き換える：

```python
NOTE_MD = """# ジャモライコ vs イオナサンプル 校正実験

**目的**: ジャモライコエージェント（タケルライコex軸）が、現行のイオナ/ナンジャモ
サンプル（Kaggle LB 600〜877）に対して勝率で上回るかを、Kaggle上の自己対戦
200試合で確認する。macOSでは`libcg.so`が動かずローカル対戦できないための代替。

グリムスナールの校正実験（重みA/Bの差を検出するのに必要な試合数の検証）とは
目的が異なり、今回は**別デッキ同士の勝率そのもの**を測る。

両デッキとも60枚のカードIDリストをノートブックに定数として直接埋め込んでいる
（Kaggleは1データセットしかアップロードできない制約のため、ジャモライコの
`output/deck_jamoraiko_20260713.csv`データセットのみをAdd Inputすればよい。
イオナサンプル側はコード内蔵のため追加データセット不要）。

最初の`LOG_FIRST_N`試合（デフォルト10試合）は、対戦中の手番選択（OptionType/
選択肢一覧/盤面/イベントログ）を`jamoraiko_vs_iono_turn_log.json`として
別途保存する。勝率が想定通り伸びない場合の負け試合深掘り調査に使う。

設計書: docs/superpowers/specs/2026-07-14-jamoraiko-vs-iono-turn-logging-design.md
"""
```

- [ ] **Step 3b: HARNESS_CODEを更新する**

`scripts/build_jamoraiko_vs_iono_notebook.py:157-182`の`HARNESS_CODE`定義全体を以下に置き換える：

```python
HARNESS_CODE = '''# ==================== 対戦ハーネス ====================
from cg.game import battle_finish, battle_select, battle_start

MAX_STEPS_PER_GAME = 700


def play_game(agent_a, agent_b, deck_a, deck_b, max_steps=MAX_STEPS_PER_GAME,
              turn_log_sink=None, agent_a_name="A", agent_b_name="B", game_index=0) -> int:
    """1試合対戦する。agent_a勝ち=+1 / 負け=-1 / 引き分け・打ち切り=0

    turn_log_sinkにlistを渡すと、各手番のbuild_turn_log_entry()の結果を追記する。
    """
    obs, start_data = battle_start(deck_a, deck_b)
    if getattr(start_data, "errorPlayer", -1) >= 0:
        raise ValueError(f"deck error: player={start_data.errorPlayer}, type={start_data.errorType}")
    steps = 0
    try:
        while obs["current"]["result"] < 0 and steps < max_steps:
            your_index = obs["current"]["yourIndex"]
            if your_index == 0:
                selected = agent_a(obs)
                acting_agent_name = agent_a_name
            else:
                selected = agent_b(obs)
                acting_agent_name = agent_b_name
            if turn_log_sink is not None:
                turn_log_sink.append(build_turn_log_entry(obs, selected, game_index, steps, acting_agent_name))
            obs = battle_select(selected)
            steps += 1
        result = obs["current"]["result"]
    finally:
        battle_finish()
    if result == 0:
        return 1
    if result == 1:
        return -1
    return 0'''
```

- [ ] **Step 3c: CALIBRATION_CODEを更新する**

`scripts/build_jamoraiko_vs_iono_notebook.py:192-223`の`CALIBRATION_CODE`定義全体を以下に置き換える：

```python
CALIBRATION_CODE = '''# ==================== 校正実験（勝率測定） ====================
import time

GAMES = 200
CHECKPOINTS = [10, 20, 40, 80, 120, 160, 200]
LOG_FIRST_N = 10


def run_series(agent_a, agent_b, deck_a, deck_b, games, label, log_first_n=0):
    """agent_a側の視点で対戦を繰り返す。先手後手の偏りを消すため1試合ごとに座席を交代する。

    log_first_nを指定すると、最初のlog_first_n試合だけ手番選択ログを記録し、
    2つ目の戻り値（turn_log_games）として返す。
    """
    results = []
    turn_log_games = []
    t0 = time.time()
    for i in range(games):
        game_log = [] if i < log_first_n else None
        if i % 2 == 0:
            r = play_game(agent_a, agent_b, deck_a, deck_b,
                          turn_log_sink=game_log, agent_a_name="jamoraiko", agent_b_name="iono", game_index=i)
            seat_first = "jamoraiko"
        else:
            r = -play_game(agent_b, agent_a, deck_b, deck_a,
                           turn_log_sink=game_log, agent_a_name="iono", agent_b_name="jamoraiko", game_index=i)
            seat_first = "iono"
        results.append(r)
        if game_log is not None:
            turn_log_games.append({"game_index": i, "seat_first": seat_first, "result": r, "turns": game_log})
        n = i + 1
        if n in CHECKPOINTS:
            wins = sum(1 for x in results if x > 0)
            losses = sum(1 for x in results if x < 0)
            print(f"[{label}] {n:>3}試合: A勝={wins:>3} A負={losses:>3} 引分={n - wins - losses:>3} A勝率={wins / n:.3f}")
    elapsed = time.time() - t0
    print(f"[{label}] 計{games}試合 {elapsed:.1f}秒（{elapsed / games * 1000:.0f}ms/試合）")
    return {"label": label, "results": results, "elapsed_sec": elapsed}, turn_log_games


series, turn_log_games = run_series(
    jamoraiko_mod.agent, iono_mod.agent,
    JAMORAIKO_DECK, IONO_DECK,
    GAMES, "Jamoraiko vs Iono Sample",
    log_first_n=LOG_FIRST_N,
)'''
```

- [ ] **Step 3d: SAVE_LOG_CODEを新規追加する**

`SAVE_CODE`定義（現行`scripts/build_jamoraiko_vs_iono_notebook.py:225-232`）の直後、`PLOT_CODE`定義の前に追加：

```python
SAVE_LOG_CODE = '''# ==================== 手番選択ログの保存 ====================
log_payload = {"num_games_logged": len(turn_log_games), "games": turn_log_games}
log_out_path = OUT_DIR / "jamoraiko_vs_iono_turn_log.json"
log_out_path.write_text(json.dumps(log_payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"saved: {log_out_path}")'''
```

- [ ] **Step 3e: turn_log_helpers_srcを組み立てて main() の cells リストに配線する**

`scripts/build_jamoraiko_vs_iono_notebook.py:289-293`の`load_helper_src`定義の直後に追加：

```python

    turn_log_helpers_src = (
        "# ==================== 手番選択ログ用ヘルパー ====================\n"
        f"SELECT_TYPE_NAMES = {SELECT_TYPE_NAMES!r}\n\n"
        f"SELECT_CONTEXT_NAMES = {SELECT_CONTEXT_NAMES!r}\n\n\n"
        + inspect.getsource(compact_option) + "\n\n"
        + inspect.getsource(compact_log_entry) + "\n\n"
        + inspect.getsource(_pokemon_summary) + "\n\n"
        + inspect.getsource(board_snapshot) + "\n\n"
        + inspect.getsource(build_turn_log_entry)
    )
```

（このコードは`main()`関数内、既存の`load_helper_src = (...)`の直後、`nb = {`の前に挿入する。インデントは`main()`内の他の行と揃える）

`scripts/build_jamoraiko_vs_iono_notebook.py:295-311`の`nb = {"cells": [...]}`部分を以下に置き換える：

```python
    nb = {
        "cells": [
            md_cell("calibration-note", NOTE_MD),
            *copied,
            code_cell("deck-load", DECK_CODE),
            code_cell("agent-sources", sources_cell_src),
            code_cell("load-helper", load_helper_src),
            code_cell("agent-load", AGENT_LOAD_CODE),
            code_cell("turn-log-helpers", turn_log_helpers_src),
            code_cell("battle-harness", HARNESS_CODE),
            code_cell("calibration-run", CALIBRATION_CODE),
            code_cell("save-results", SAVE_CODE),
            code_cell("save-turn-log", SAVE_LOG_CODE),
            code_cell("plot-curve", PLOT_CODE),
        ],
        "metadata": ref.get("metadata", {}),
        "nbformat": 4,
        "nbformat_minor": 5,
    }
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_jamoraiko_vs_iono_notebook_build.py -v -k TestMainBuildsNotebookWithTurnLogging`
Expected: PASS（6件）

- [ ] **Step 5: 全体回帰を確認してコミット**

Run: `uv run pytest -q`
Expected: 全件PASS

```bash
git add scripts/build_jamoraiko_vs_iono_notebook.py tests/test_jamoraiko_vs_iono_notebook_build.py
git commit -m "feat: 校正ノートブックに手番選択ログ出力（最初の10試合）を配線"
```

---

## Task 5: ノートブック再生成 + 実装サマリー保存

**Files:**
- Generate: `src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`（gitignore対象、コミット不要）
- Create: `docs/implementations/20260714-jamoraiko-vs-iono-turn-logging.md`

**Interfaces:**
- Consumes: Task 1〜4で完成した`scripts/build_jamoraiko_vs_iono_notebook.py`

- [ ] **Step 1: ノートブックを再生成する**

Run: `uv run python scripts/build_jamoraiko_vs_iono_notebook.py`
Expected: `wrote src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb with 13 cells`のような出力（cell数は実際の構成に合わせる）

- [ ] **Step 2: リポジトリ全体のテストを最終確認する**

Run: `uv run pytest -q`
Expected: 全件PASS（回帰なし）

- [ ] **Step 3: 実装サマリーを作成する**

`docs/implementations/20260714-jamoraiko-vs-iono-turn-logging.md` を新規作成し、以下を記載する：
- 背景（勝率0.015が変化しない原因調査のため）
- 実装内容（Task 1〜4の変更点サマリー）
- 追加したテスト件数
- 出力ファイル（`jamoraiko_vs_iono_turn_log.json`）のスキーマ概要
- 未検証事項（Kaggle実行が必要：実際のファイルサイズ、10試合分のログが正しく出力されるか）
- 次のステップ（ユーザーがKaggleでノートブックを実行し、`jamoraiko_vs_iono_turn_log.json`をダウンロードして負け試合を深掘りする）

- [ ] **Step 4: コミット**

```bash
git add docs/implementations/20260714-jamoraiko-vs-iono-turn-logging.md
git commit -m "docs: 手番選択ログ出力機能の実装サマリーを追加"
```
