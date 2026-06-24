import sys
from pathlib import Path

# src/ を import パスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from etl.bronze import copy_to_bronze
from etl.silver import parse_to_silver


def main() -> None:
    if len(sys.argv) != 2:
        print("使い方: python scripts/etl_battle_log.py <path_to_json>")
        sys.exit(1)

    src_path = Path(sys.argv[1])
    if not src_path.exists():
        print(f"エラー: {src_path} が見つかりません")
        sys.exit(1)

    catalog_dir = Path("data/unity-catalog")

    bronze_path = copy_to_bronze(src_path, catalog_dir)
    print(f"Bronze: {bronze_path}")

    summary_path, turns_path = parse_to_silver(bronze_path, catalog_dir)
    print(f"Silver summary: {summary_path}")
    print(f"Silver turns:   {turns_path}")


if __name__ == "__main__":
    main()
