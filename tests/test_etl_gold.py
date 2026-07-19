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
