import csv
from pathlib import Path


def build_card_dict(csv_path: Path) -> dict[str, int]:
    """EN_Card_Data.csv を読み込み「カード名 → Card ID」辞書を返す"""
    card_dict: dict[str, int] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            card_dict[row["Card Name"]] = int(row["Card ID"])
    return card_dict


def _normalize(name: str) -> str:
    """大文字小文字・前後スペースを正規化する"""
    return name.lower().strip()


def find_card_id(name: str, card_dict: dict[str, int]) -> tuple[int | None, list[str]]:
    """
    カード名からIDを検索する。

    Returns:
        (card_id, candidates)
        - card_id: 一致したID。見つからなければ None
        - candidates: 部分一致候補のカード名リスト（card_id が None のときのみ意味を持つ）
    """
    # 完全一致
    if name in card_dict:
        return card_dict[name], []

    # 大文字小文字・スペース正規化後に一致
    norm = _normalize(name)
    for card_name, card_id in card_dict.items():
        if _normalize(card_name) == norm:
            return card_id, []

    # 部分一致候補
    candidates = [card_name for card_name in card_dict if norm in _normalize(card_name)]
    return None, candidates
