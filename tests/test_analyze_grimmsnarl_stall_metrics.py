"""グリムスナールex 3指標計測スクリプトのテスト。

実ログ2件（855系ベースライン）に対する特性化テスト（characterization test）で
計測定義を固定する。ここの期待値は2026-07-12のベースライン計測の実測値であり、
再提出後の新ログとの比較はこの定義・この数字を基準に行う。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from analyze_grimmsnarl_stall_metrics import (
    analyze_log,
    build_report,
    detect_player_index,
)

LOGS_DIR = Path(__file__).parent.parent / "data" / "battle_logs"


def test_worst_stall_case_85534500():
    """最悪の立ち往生例：エネ0キチキギスexを壁にオーロンゲを一度も出せず敗北した試合"""
    r = analyze_log(LOGS_DIR / "85534500.json")
    assert r["won"] is False
    assert r["main_steps"] == 47
    assert r["stall_steps"] == 12
    # にげるコスト不払いでRETREAT選択肢自体が一度も提示されなかった
    assert r["stall_retreat_offered"] == 0
    assert r["boss_plays"] == 1
    assert r["boss_not_ready"] == 1  # T3・攻撃不能時のボス浪費


def test_deckout_case_85541203():
    """デッキアウト負け：山札0で終局した試合（山札セーフティ導入の直接の動機）"""
    r = analyze_log(LOGS_DIR / "85541203.json")
    assert r["won"] is False
    assert r["deck_left"] == 0
    assert r["stall_steps"] == 18
    assert r["stall_retreat_offered"] == 18
    assert r["boss_plays"] == 2


def test_detect_player_index_rejects_mirror_match():
    """完全ミラー戦（両者同一デッキ）は自動判定できずValueErrorになる"""
    deck = sorted(
        cid for cid, count in _own_deck_pairs() for _ in range(count)
    )
    data = {"steps": [[{"visualize": [{"action": [deck, deck]}]}]]}
    with pytest.raises(ValueError, match="player-name"):
        detect_player_index(data)


def _own_deck_pairs():
    sys.path.insert(0, str(Path(__file__).parent.parent / "decks"))
    import grimmsnarl_20260701 as deck_module
    return deck_module.DECK


def test_build_report_aggregates_two_games():
    """レポートに試合別行と全体集計が含まれる"""
    results = [
        analyze_log(LOGS_DIR / "85534500.json"),
        analyze_log(LOGS_DIR / "85541203.json"),
    ]
    report = build_report(results)
    assert "| 85534500 |" in report
    assert "| 85541203 |" in report
    assert "試合数: 2（0勝2敗）" in report
    assert "立ち往生手番数: 計30手番" in report  # 12 + 18
    assert "最小0枚" in report
