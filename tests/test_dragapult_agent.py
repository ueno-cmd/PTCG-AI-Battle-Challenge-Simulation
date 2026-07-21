# tests/test_dragapult_agent.py
import dragapult_agent.main as dm


def test_boss_orders_score_confirmed_pull_target():
    """確定的な引き剥がし先がある場合は最優先スコア"""
    assert dm._boss_orders_score(has_pull_target=True, explore_roll=0.99, epsilon=0.28) == 60000


def test_boss_orders_score_exploratory_use_within_epsilon():
    """確定的な引き剥がし先が無くても、乱数がepsilon未満なら探索的に先出しする"""
    assert dm._boss_orders_score(has_pull_target=False, explore_roll=0.1, epsilon=0.28) == 30000


def test_boss_orders_score_conserve_outside_epsilon():
    """確定的な引き剥がし先が無く、乱数もepsilon以上なら温存（0点）"""
    assert dm._boss_orders_score(has_pull_target=False, explore_roll=0.5, epsilon=0.28) == 0


def test_boss_orders_score_boundary_is_exclusive():
    """explore_roll == epsilon ちょうどは温存側（lucario_agentのrng.random() < EPSILONと同じ境界）"""
    assert dm._boss_orders_score(has_pull_target=False, explore_roll=0.28, epsilon=0.28) == 0
