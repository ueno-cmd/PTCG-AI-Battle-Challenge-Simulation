# tests/test_scoring.py
from mascarnage_agent.main import bouquet_magic_score
from tests.conftest import make_pokemon


def test_bouquet_prefers_lower_hp_target():
    """HPが低い相手を優先する（スコアが高くなる）"""
    low_hp  = make_pokemon(id=1, hp=30,  max_hp=200)
    high_hp = make_pokemon(id=2, hp=200, max_hp=200)
    assert bouquet_magic_score(low_hp) > bouquet_magic_score(high_hp)


def test_bouquet_bonus_for_already_damaged():
    """すでにダメカンが乗っている相手はボーナスが付く"""
    damaged = make_pokemon(id=1, hp=100, max_hp=200)  # 100点ダメージ済み
    fresh   = make_pokemon(id=2, hp=200, max_hp=200)  # ノーダメージ
    assert bouquet_magic_score(damaged) > bouquet_magic_score(fresh)


def test_bouquet_returns_minus1_for_immune_target():
    """ダメカン免疫の相手はスコア -1"""
    immune = make_pokemon(id=207)  # ミロカロスex
    assert bouquet_magic_score(immune) == -1


def test_bouquet_returns_positive_for_normal_target():
    """通常ポケモンへのスコアは正の値"""
    normal = make_pokemon(id=999, hp=100)
    assert bouquet_magic_score(normal) > 0
