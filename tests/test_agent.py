# tests/test_agent.py
from unittest.mock import patch
from cg.api import OptionType, AreaType, Option
from mascarnage_agent.main import agent
from tests.conftest import make_pokemon, make_player_state, make_main_obs


def _attack_option(attack_id: int = 100) -> Option:
    return Option(type=OptionType.ATTACK, attackId=attack_id)


def _end_option() -> Option:
    return Option(type=OptionType.END)


def test_agent_returns_deck_when_select_is_none():
    """obs.selectがNoneのとき（デッキ選択フェーズ）はデッキを返す"""
    obs_dict = {"select": None, "logs": [], "current": None,
                "search_begin_input": None}
    # _load_cards をモックして libcg.so 呼び出しを回避する
    with patch("mascarnage_agent.main._load_cards", return_value={}):
        result = agent(obs_dict)
    # deck.csvがない環境では空リストが返る（エラーにならないこと）
    assert isinstance(result, list)


def test_agent_prefers_attack_over_end():
    """攻撃オプションがあるときはターン終了より攻撃を選ぶ"""
    options = [_end_option(), _attack_option(attack_id=100)]
    obs_dict = make_main_obs(options=options)
    with patch("mascarnage_agent.main._load_cards", return_value={}):
        result = agent(obs_dict)
    assert len(result) == 1
    selected_option_index = result[0]
    # 選ばれたオプションがATTACKであること
    assert options[selected_option_index].type == OptionType.ATTACK


def test_agent_returns_valid_indices():
    """返り値のインデックスがoption範囲内かつ重複がないこと"""
    # ABILITYはベンチアクセスが必要なため、ATTACK/ENDのみでテスト
    options = [_attack_option(attack_id=100), _attack_option(attack_id=101), _end_option()]
    obs_dict = make_main_obs(options=options)
    with patch("mascarnage_agent.main._load_cards", return_value={}):
        result = agent(obs_dict)
    assert len(result) >= 1
    assert len(result) == len(set(result))  # 重複なし
    assert all(0 <= i < len(options) for i in result)  # 範囲内
