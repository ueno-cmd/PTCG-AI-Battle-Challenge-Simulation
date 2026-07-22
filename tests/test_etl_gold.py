import json
from pathlib import Path

import pytest

from etl.gold import build_event_timeline, classify_archetype, extract_deck_list, find_player_index, load_card_names, load_raw_log

FIXTURE_PATH = Path(__file__).parent.parent / "data" / "battle_logs" / "84580427.json"
CARD_DATA_PATH = Path(__file__).parent.parent / "data" / "competition" / "EN_Card_Data.csv"


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


from etl.gold import GameStateTracker


def test_tracker_move_card_to_active_sets_active_serial():
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({
        "type": 6, "playerIndex": 0, "cardId": 121, "serial": 10,
        "fromArea": 2, "toArea": 4,
    })
    assert tracker.active_serial == 10
    assert tracker.species[10] == 121
    assert tracker.energy_count[10] == 0


def test_tracker_move_card_to_bench_adds_bench_serial():
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({
        "type": 6, "playerIndex": 0, "cardId": 119, "serial": 11,
        "fromArea": 2, "toArea": 5,
    })
    assert 11 in tracker.bench_serials
    assert tracker.species[11] == 119


def test_tracker_move_card_active_to_discard_removes_pokemon():
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 121, "serial": 10, "fromArea": 2, "toArea": 4})
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 121, "serial": 10, "fromArea": 4, "toArea": 3})
    assert tracker.active_serial is None
    assert 10 not in tracker.species
    assert 10 not in tracker.energy_count


def test_tracker_ignores_other_players_move_card():
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({"type": 6, "playerIndex": 1, "cardId": 999, "serial": 50, "fromArea": 2, "toArea": 4})
    assert tracker.active_serial is None
    assert 50 not in tracker.species


def test_tracker_switch_swaps_active_and_bench_correctly():
    """SWITCHのフィールド名は意味と逆(serialActive=退場/serialBench=登場)。
    ここを取り違えると2026-07-22に発覚したのと同じ致命的な誤判定が再発する"""
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 121, "serial": 10, "fromArea": 2, "toArea": 4})
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 119, "serial": 11, "fromArea": 2, "toArea": 5})
    tracker.apply({
        "type": 8, "playerIndex": 0,
        "cardIdActive": 121, "serialActive": 10,
        "cardIdBench": 119, "serialBench": 11,
    })
    assert tracker.active_serial == 11
    assert 10 in tracker.bench_serials
    assert 11 not in tracker.bench_serials


def test_tracker_attach_energy_increments_count():
    tracker = GameStateTracker(target_player_index=0, tool_card_ids=frozenset({1159}))
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 121, "serial": 10, "fromArea": 2, "toArea": 4})
    tracker.apply({"type": 11, "playerIndex": 0, "cardId": 6, "serial": 90, "cardIdTarget": 121, "serialTarget": 10})
    assert tracker.energy_count[10] == 1


def test_tracker_attach_energy_records_card_id_in_energy_cards_list():
    """_attach_score()のenergy_count==1分岐がpokemon.energyCards[0].idを参照するため、
    countだけでなく実際に貼られたエネルギーのcard_idも保持できていないと後段のTask5で
    再現できない（energy_countをintのみで持つ設計だとここが欠落することに自己レビューで気付いた）"""
    tracker = GameStateTracker(target_player_index=0, tool_card_ids=frozenset({1159}))
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 121, "serial": 10, "fromArea": 2, "toArea": 4})
    tracker.apply({"type": 11, "playerIndex": 0, "cardId": 6, "serial": 90, "cardIdTarget": 121, "serialTarget": 10})
    assert tracker.energy_cards[10] == [6]


def test_tracker_attach_tool_does_not_increment_energy_count():
    tracker = GameStateTracker(target_player_index=0, tool_card_ids=frozenset({1159}))
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 121, "serial": 10, "fromArea": 2, "toArea": 4})
    tracker.apply({"type": 11, "playerIndex": 0, "cardId": 1159, "serial": 91, "cardIdTarget": 121, "serialTarget": 10})
    assert tracker.energy_count[10] == 0


def test_tracker_evolve_preserves_position_and_energy():
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 119, "serial": 11, "fromArea": 2, "toArea": 5})
    tracker.apply({"type": 11, "playerIndex": 0, "cardId": 6, "serial": 90, "cardIdTarget": 119, "serialTarget": 11})
    tracker.apply({
        "type": 12, "playerIndex": 0,
        "cardId": 121, "serial": 12,
        "cardIdTarget": 119, "serialTarget": 11,
    })
    assert 12 in tracker.bench_serials
    assert 11 not in tracker.bench_serials
    assert tracker.species[12] == 121
    assert tracker.energy_count[12] == 1
    assert tracker.energy_cards[12] == [6]
    assert 11 not in tracker.species


def test_tracker_asleep_and_paralyzed_toggle_with_is_recover():
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({"type": 19, "playerIndex": 0, "cardId": 121, "serial": 10, "isRecover": False})
    assert tracker.asleep is True
    tracker.apply({"type": 19, "playerIndex": 0, "cardId": 121, "serial": 10, "isRecover": True})
    assert tracker.asleep is False
    tracker.apply({"type": 20, "playerIndex": 0, "cardId": 121, "serial": 10, "isRecover": False})
    assert tracker.paralyzed is True


def test_tracker_opponent_prize_taken_decrements_remaining():
    tracker = GameStateTracker(target_player_index=0)
    assert tracker.opponent_prize_remaining == 6
    tracker.apply({"type": 6, "playerIndex": 1, "fromArea": 6, "toArea": 2, "cardId": 5, "serial": 40})
    assert tracker.opponent_prize_remaining == 5
