# tests/test_jamoraiko_agent.py
import jamoraiko_agent.main as jm


class TestAgentDeckSelection:
    def test_agent_returns_deck_when_select_is_none(self):
        result = jm.agent({"select": None})
        assert len(result) == 60
        assert result[0] == 63  # タケルライコex が先頭
