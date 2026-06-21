from datetime import datetime
from pathlib import Path


class CardNotFoundError(Exception):
    """デッキ定義内のカード名が EN_Card_Data.csv で見つからなかった場合"""


class DeckSizeError(Exception):
    """デッキの合計枚数が 60 枚でない場合"""


def write_deck_csv(card_ids: list[int], output_dir: Path) -> Path:
    """カード ID リストをタイムスタンプ付き CSV に書き出す"""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"deck_{timestamp}.csv"
    with open(output_path, "w", encoding="utf-8") as f:
        for card_id in card_ids:
            f.write(f"{card_id}\n")
    return output_path
