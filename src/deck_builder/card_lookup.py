import csv
from pathlib import Path


def build_card_dict(csv_path: Path) -> dict[str, int]:
    """EN_Card_Data.csv を読み込み「カード名 → Card ID」辞書を返す。
    同名カードが複数ある場合は最初のエントリを使用し警告を出力する。
    """
    card_dict: dict[str, int] = {}
    duplicates: dict[str, list[int]] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["Card Name"]
            card_id = int(row["Card ID"])
            if name in card_dict:
                if name not in duplicates:
                    duplicates[name] = [card_dict[name]]
                duplicates[name].append(card_id)
            else:
                card_dict[name] = card_id
    for name, ids in duplicates.items():
        print(f"⚠ 重複カード名 \"{name}\": ID {ids} → 最初の {ids[0]} を使用。別IDが必要な場合はデッキ定義で整数IDを直接指定してください")
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
