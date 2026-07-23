"""ドラパルトexエージェントのKaggle提出用notebookを生成するビルドスクリプト。

scripts/build_dragapult_submission_main.py の結合結果（constants.py + main.py を
1ファイル化したソース）を、完全な .ipynb ファイルとして書き出す。
main.py/constants.pyを直接編集した後はこのスクリプトを再実行し、
生成された notebooks/submissions/dragapult_agent_submission.ipynb を
Kaggle上で「Upload Notebook」等によりファイルごと差し替えること
（手動でのコード貼り付けによるタイポ混入リスクを構造的に無くす狙い）。

Usage: uv run python scripts/build_dragapult_submission_notebook.py
"""
import ast
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "scripts"
DST = ROOT / "notebooks" / "submissions" / "dragapult_agent_submission.ipynb"

sys.path.insert(0, str(SCRIPTS_DIR))
import build_dragapult_submission_main as submission_builder  # noqa: E402


def validate_syntax(combined: str) -> None:
    """結合済みソースの構文を検証する。壊れていれば notebook を書き出さず終了する。"""
    try:
        ast.parse(combined)
    except SyntaxError as e:
        print(f"エラー: 結合後のソースに構文エラーがあります: {e}", file=sys.stderr)
        sys.exit(1)


def note_md(generated_at: datetime) -> str:
    return f"""## Rule-Based Agent for Dragapult ex

生成日時: {generated_at:%Y-%m-%d %H:%M:%S}

Kaggle提出用notebook。`scripts/build_dragapult_submission_notebook.py` により
`src/dragapult_agent/{{constants,main}}.py` から自動生成されている。
手で編集せず、ソース修正後にビルドスクリプトを再実行すること。
"""


TAR_CODE = """import glob
import os
import tarfile

with tarfile.open("submission.tar.gz", "w:gz") as tar:
    tar.add("main.py", arcname="main.py")
    tar.add(glob.glob('/kaggle/input/**/cg-lib/cg', recursive=True)[0], arcname="cg")
    tar.add(glob.glob('/kaggle/input/**/deck.csv', recursive=True)[0], arcname="deck.csv")

os.remove('main.py')"""


def code_cell(cell_id: str, source: str) -> dict:
    return {
        "cell_type": "code", "id": cell_id, "metadata": {},
        "execution_count": None, "outputs": [], "source": source,
    }


def md_cell(cell_id: str, source: str) -> dict:
    return {"cell_type": "markdown", "id": cell_id, "metadata": {}, "source": source}


def build_notebook(combined: str, generated_at: datetime) -> dict:
    """結合済みソースから提出用notebookのセル構造（辞書）を組み立てる。"""
    return {
        "cells": [
            md_cell("submission-note", note_md(generated_at)),
            code_cell("write-main", f"%%writefile main.py\n{combined}"),
            code_cell("package-submission", TAR_CODE),
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    combined = submission_builder.build()
    validate_syntax(combined)
    nb = build_notebook(combined, datetime.now())
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {DST}")


if __name__ == "__main__":
    main()
