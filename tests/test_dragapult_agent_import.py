# tests/test_dragapult_agent_import.py
from decks.dragapult_20260721 import DECK


def test_module_imports_without_deck_csv_on_disk():
    """deck.csvがカレントディレクトリに存在しない状態でも import できること
    （Kaggle実行時は同ディレクトリにdeck.csvが配置されるが、pytest実行時は存在しない）"""
    import dragapult_agent.main as dm
    assert callable(dm.agent)


def test_my_deck_is_empty_immediately_after_import():
    """import直後はdeck.csvの読み込みが走っておらず、my_deckが空のままであること"""
    import dragapult_agent.main as dm
    assert dm.my_deck == []


def test_agent_initial_selection_returns_full_deck(tmp_path, monkeypatch):
    """obs.select が None の初回デッキ選択で、agent() が60枚のデッキをそのまま返すこと。

    Finding 1 の回帰テスト：修正前は my_deck の遅延読み込み（_load_deck）が
    set_card_counts() 経由でしか呼ばれず、初回選択では空リスト [] が返っていた
    （Kaggleへの提出が空デッキになる致命的バグ）。

    注意：dragapult_agent.main は他のテストファイルで既にimportされ、
    my_deck がその時点のdeck.csvから読み込み済みになっている可能性がある
    （pytestセッション内でモジュールが使い回されるため）。
    そのため、このテストでは dm.my_deck をあえて空リストにリセットしてから
    agent() を呼び、遅延読み込みが実際に発火することを検証する。
    """
    import dragapult_agent.main as dm

    expected_deck = [card_id for card_id, count in DECK for _ in range(count)]
    assert len(expected_deck) == 60

    deck_csv_path = tmp_path / "deck.csv"
    deck_csv_path.write_text("\n".join(str(card_id) for card_id in expected_deck))

    monkeypatch.chdir(tmp_path)
    dm.my_deck = []  # 他テストでの読み込み済み状態をリセットし、遅延読み込みが発火することを保証する

    try:
        result = dm.agent({"select": None, "logs": [], "current": None})
        assert len(result) == 60
        assert result == expected_deck
    finally:
        dm.my_deck = []  # 後続テストにtmp_path由来のデッキを漏らさない
