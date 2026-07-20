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


NOTE_MD = """## Rule-Based Agent for Mega Lucario ex

Kaggle提出用notebook。`scripts/build_lucario_submission_notebook.py` により
`src/lucario_agent/{constants,combat,main}.py` から自動生成されている。
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


def build_notebook(combined: str) -> dict:
    """結合済みソースから提出用notebookのセル構造（辞書）を組み立てる。"""
    return {
        "cells": [
            md_cell("submission-note", NOTE_MD),
            code_cell("write-main", f"%%writefile main.py\n{combined}"),
            code_cell("package-submission", TAR_CODE),
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
