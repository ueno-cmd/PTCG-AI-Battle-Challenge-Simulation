"""ジャモライコ vs イオナサンプル校正ノートブック ビルドスクリプトの単体テスト

生成されるノートブックの実行(cg依存)はローカルでは検証できないため、
ビルドスクリプト自体の純粋なPythonロジック（名前空間分離・デッキ定数・
writefileマジック除去）のみをテストする。
"""
import importlib.util
import json
import types
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_jamoraiko_vs_iono_notebook.py"
_spec = importlib.util.spec_from_file_location("build_jvi_nb", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # main()は __main__ ガードで走らない


class TestLoadAgentModule:
    def test_returns_module_with_agent_function(self):
        source = "def agent(obs_dict):\n    return [0]\n"
        mod = _mod.load_agent_module("fake_agent", source)
        assert isinstance(mod, types.ModuleType)
        assert mod.agent({"select": None}) == [0]

    def test_two_modules_with_colliding_globals_do_not_interfere(self):
        source_a = "card_table = {1: 'A'}\n\ndef agent(obs_dict):\n    return list(card_table.keys())\n"
        source_b = "card_table = {2: 'B'}\n\ndef agent(obs_dict):\n    return list(card_table.keys())\n"
        mod_a = _mod.load_agent_module("agent_a", source_a)
        mod_b = _mod.load_agent_module("agent_b", source_b)
        assert mod_a.agent(None) == [1]
        assert mod_b.agent(None) == [2]
        assert mod_a.card_table != mod_b.card_table


class TestLoadAgentModuleWithRealSources:
    """load_agent_moduleはsys.modulesに未登録のモジュール名前空間でexec()するため、
    dataclassフィールドに文字列型注釈(例: "int | None")があると
    AttributeError: 'NoneType' object has no attribute '__dict__'でクラッシュする
    （Kaggle実行時にjamoraiko_agentのPokemonLineで実際に発生した事故の再発防止）。
    ここではsrc/jamoraiko_agent/main.pyの実ソースをそのままexec()して検証する。
    """

    def test_jamoraiko_agent_source_loads_without_crashing(self):
        source = (Path(__file__).resolve().parent.parent / "src" / "jamoraiko_agent" / "main.py").read_text()
        mod = _mod.load_agent_module("jamoraiko_agent_module_regression", source)
        assert callable(mod.agent)


class TestStripWritefileMagic:
    def test_removes_leading_writefile_line(self):
        source = "%%writefile main.py\nimport os\nprint('hi')\n"
        result = _mod._strip_writefile_magic(source)
        assert result == "import os\nprint('hi')\n"

    def test_source_without_magic_is_unchanged(self):
        source = "import os\nprint('hi')\n"
        result = _mod._strip_writefile_magic(source)
        assert result == source


class TestIonoDeck:
    def test_deck_has_60_cards(self):
        assert len(_mod.IONO_DECK) == 60

    def test_expected_card_counts(self):
        counts = {}
        for card_id in _mod.IONO_DECK:
            counts[card_id] = counts.get(card_id, 0) + 1
        assert counts[265] == 3   # Iono's Voltorb
        assert counts[269] == 3   # Iono's Bellibolt ex
        assert counts[1227] == 4  # Lillie's Determination
        assert counts[4] == 20    # Basic {L} Energy


class TestJamoraikoDeckExpansion:
    def test_expanded_deck_has_60_cards(self):
        from decks.jamoraiko_20260713 import DECK
        expanded = _mod.expand_deck(DECK)
        assert len(expanded) == 60

    def test_expanded_deck_preserves_counts(self):
        from decks.jamoraiko_20260713 import DECK
        expanded = _mod.expand_deck(DECK)
        assert expanded.count(265) == 3  # ナンジャモのビリリダマ


class TestPatchIonoDeckLoad:
    """Critical指摘の修正対象：イオナサンプルのモジュールレベルdeck.csv読み込みを
    try/except + ビルド時埋め込み定数へのフォールバックに書き換えるロジックのテスト。
    """

    def _build_fake_iono_source(self) -> str:
        """イオナサンプルのソース構造を模した最小のソース文字列
        （デッキ読み込みブロックの前後にモジュールレベルコードとagent関数を持つ）"""
        return (
            "import os\n"
            "\n"
            "# Load deck.csv in the dataset\n"
            + _mod._IONO_DECK_LOAD_ORIGINAL
            + "\n\n"
            "def agent(obs_dict):\n"
            "    return my_deck\n"
        )

    def test_patched_source_contains_except_filenotfounderror(self):
        source = self._build_fake_iono_source()
        patched = _mod._patch_iono_deck_load(source, _mod.IONO_DECK)
        assert "except FileNotFoundError" in patched

    def test_patched_source_execs_and_returns_60_card_deck_without_deck_csv(self, tmp_path, monkeypatch):
        """deck.csvが存在しないカレントディレクトリでexec()しても
        FileNotFoundErrorを送出せず、60枚のデッキを返すことを実際に検証する。"""
        monkeypatch.chdir(tmp_path)
        assert not (tmp_path / "deck.csv").exists()

        source = self._build_fake_iono_source()
        patched = _mod._patch_iono_deck_load(source, _mod.IONO_DECK)

        mod = _mod.load_agent_module("test_iono_patched", patched)
        result = mod.agent({"select": None})

        assert len(result) == 60
        assert result == _mod.IONO_DECK

    def test_raises_runtime_error_when_source_does_not_match_expected_block(self):
        unexpected_source = (
            "import os\n"
            "\n"
            "# デッキ読み込みブロックが想定と異なる（例：サンプル側の実装が変更された）\n"
            "my_deck = [1, 2, 3]\n"
            "\n"
            "def agent(obs_dict):\n"
            "    return my_deck\n"
        )
        try:
            _mod._patch_iono_deck_load(unexpected_source, _mod.IONO_DECK)
            assert False, "RuntimeErrorが送出されるはず"
        except RuntimeError as exc:
            assert "想定と異なります" in str(exc)


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
            # nbformatの仕様上sourceは文字列のほか行リストでも許容される
            # （参考ノートブックからコピーしたセルはリスト形式のまま）ため、
            # compile()に渡す前に結合しておく
            source = cell["source"]
            if isinstance(source, list):
                source = "".join(source)
            compile(source, cell["id"], "exec")

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
