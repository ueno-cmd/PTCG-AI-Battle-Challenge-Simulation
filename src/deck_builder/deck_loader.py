import importlib.util
from pathlib import Path


def load_deck_def(file_path: Path) -> list[tuple[str, int]]:
    """デッキ定義ファイル (.py) の DECK リストを読み込む"""
    spec = importlib.util.spec_from_file_location("_deck_def", file_path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.DECK
