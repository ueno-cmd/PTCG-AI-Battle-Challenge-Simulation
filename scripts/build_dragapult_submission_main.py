"""ドラパルトexエージェントのKaggle提出用main.pyを生成するビルドスクリプト。

src/dragapult_agent/constants.py + main.py の内容を結合し、
dragapult_agent内部の相対import文（結合後は不要になる）を除去した単一ファイルを
標準出力（または --out 指定時はファイル）へ出力する。

main.py/constants.pyを直接編集した後はこのスクリプトを再実行し、
出力をKaggleノートブックの %%writefile main.py セルへコピペすること
（手動での複数ファイル辻褄合わせによるタイポ混入リスクを減らす狙い）。

Usage: uv run python scripts/build_dragapult_submission_main.py [--out PATH]
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PACKAGE_DIR = ROOT / "src" / "dragapult_agent"

# 結合順（依存関係の順）：constants → main
SOURCE_FILES = ["constants.py", "main.py"]

# dragapult_agent内部の相対import文（結合後は不要になるため除去）
INTERNAL_IMPORT_RE = re.compile(
    r"^from dragapult_agent\.constants import \([^)]*\)\n",
    re.MULTILINE,
)


def build() -> str:
    parts = []
    for filename in SOURCE_FILES:
        path = PACKAGE_DIR / filename
        source = path.read_text(encoding="utf-8")
        source = INTERNAL_IMPORT_RE.sub("", source)
        parts.append(f"# {'=' * 20} {filename} {'=' * 20}\n{source}")
    return "\n\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None, help="出力先ファイル（省略時は標準出力）")
    args = parser.parse_args()

    combined = build()

    if "def agent(" not in combined:
        print("エラー: 結合後のソースに agent() が含まれていません", file=sys.stderr)
        sys.exit(1)

    if args.out:
        args.out.write_text(combined, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(combined)


if __name__ == "__main__":
    main()
