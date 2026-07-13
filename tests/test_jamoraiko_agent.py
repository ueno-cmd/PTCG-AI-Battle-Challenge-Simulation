# tests/test_jamoraiko_agent.py
import jamoraiko_agent.main as jm


class TestAgentDeckSelection:
    def test_agent_returns_deck_when_select_is_none(self):
        obs_dict = {"select": None, "logs": [], "current": None, "search_begin_input": None}
        result = jm.agent(obs_dict)
        assert len(result) == 60
        assert result[0] == 63  # タケルライコex が先頭
