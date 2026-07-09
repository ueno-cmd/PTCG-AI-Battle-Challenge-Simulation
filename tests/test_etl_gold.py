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
