# tests/test_dragapult_agent_import.py
def test_module_imports_without_deck_csv_on_disk():
    """deck.csvがカレントディレクトリに存在しない状態でも import できること
    （Kaggle実行時は同ディレクトリにdeck.csvが配置されるが、pytest実行時は存在しない）"""
    import dragapult_agent.main as dm
    assert callable(dm.agent)


def test_my_deck_is_empty_immediately_after_import():
    """import直後はdeck.csvの読み込みが走っておらず、my_deckが空のままであること"""
    import dragapult_agent.main as dm
    assert dm.my_deck == []
