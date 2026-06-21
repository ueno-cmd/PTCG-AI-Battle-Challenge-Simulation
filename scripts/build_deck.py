#!/usr/bin/env python3
"""デッキ定義ファイルから output/deck_YYYYMMDD_HHMMSS.csv を生成する

使い方:
    uv run python scripts/build_deck.py decks/lucario_20260621.py
"""

import sys
from pathlib import Path

# src/ をモジュール検索パスに追加（uv run 実行前提）
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from deck_builder.builder import CardNotFoundError, DeckSizeError, write_deck_csv
from deck_builder.card_lookup import build_card_dict, find_card_id
from deck_builder.deck_loader import load_deck_def

PROJECT_ROOT = Path(__file__).parent.parent
CARD_CSV = PROJECT_ROOT / "data" / "EN_Card_Data.csv"
OUTPUT_DIR = PROJECT_ROOT / "output"


def main() -> None:
    if len(sys.argv) < 2:
        print("使い方: uv run python scripts/build_deck.py <デッキ定義ファイル>")
        sys.exit(1)

    deck_def_path = Path(sys.argv[1])
    if not deck_def_path.exists():
        print(f"エラー: ファイルが見つかりません: {deck_def_path}")
        sys.exit(1)

    if not CARD_CSV.exists():
        print(f"エラー: カードデータが見つかりません: {CARD_CSV}")
        sys.exit(1)

    deck_def = load_deck_def(deck_def_path)
    card_dict = build_card_dict(CARD_CSV)

    card_ids: list[int] = []
    errors: list[str] = []

    for entry in deck_def:
        card_name, count = entry[0], entry[1]
        # 整数IDが直接指定された場合は名前解決をスキップ
        if isinstance(card_name, int):
            card_ids.extend([card_name] * count)
            print(f"✓ (ID: {card_name:<6}) × {count}  [ID直接指定]")
            continue
        card_id, candidates = find_card_id(card_name, card_dict)
        if card_id is not None:
            card_ids.extend([card_id] * count)
            print(f"✓ {card_name:<40} (ID: {card_id}) × {count}")
        else:
            if candidates:
                hint = ", ".join(f'{c} (ID: {card_dict[c]})' for c in candidates[:3])
                print(f'✗ "{card_name}" → 一致なし')
                print(f"  候補: {hint}")
            else:
                print(f'✗ "{card_name}" → 一致なし（候補もなし）')
            errors.append(str(card_name))

    if errors:
        print(f"\nエラー: {len(errors)} 件のカードが見つかりませんでした。")
        print("decks/ ファイルのカード名を修正して再実行してください。")
        sys.exit(1)

    if len(card_ids) != 60:
        print(f"\nエラー: 合計 {len(card_ids)} 枚（60 枚必要）")
        sys.exit(1)

    print(f"\n合計: {len(card_ids)} 枚")
    output_path = write_deck_csv(card_ids, OUTPUT_DIR)
    print(f"出力: {output_path}")


if __name__ == "__main__":
    main()
