"""ルカリオexエージェントのKaggle提出用notebookを生成するビルドスクリプト。

scripts/build_lucario_submission_main.py の結合結果（constants.py + combat.py +
main.py を1ファイル化したソース）を、完全な .ipynb ファイルとして書き出す。
main.py/combat.py/constants.pyを直接編集した後はこのスクリプトを再実行し、
生成された notebooks/submissions/lucario_agent_submission.ipynb を
Kaggle上で「Upload Notebook」等によりファイルごと差し替えること
（手動でのコード貼り付けによるタイポ混入リスクを構造的に無くす狙い）。

Usage: uv run python scripts/build_lucario_submission_notebook.py
"""
import ast
import sys


def validate_syntax(combined: str) -> None:
    """結合済みソースの構文を検証する。壊れていれば notebook を書き出さず終了する。"""
    try:
        ast.parse(combined)
    except SyntaxError as e:
        print(f"エラー: 結合後のソースに構文エラーがあります: {e}", file=sys.stderr)
        sys.exit(1)
