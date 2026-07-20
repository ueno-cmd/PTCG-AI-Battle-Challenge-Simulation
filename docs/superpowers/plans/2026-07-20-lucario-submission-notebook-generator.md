# ルカリオexデッキ Kaggle提出用notebook自動生成スクリプト 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/lucario_agent/{constants,combat,main}.py`を結合した提出用コードを、Kaggle上での手動コピペが不要になる完全な`.ipynb`ファイルとして自動生成する`scripts/build_lucario_submission_notebook.py`を新規作成する。

**Architecture:** 既存の`scripts/build_lucario_submission_main.py`の`build()`関数（結合＋内部import除去、変更なし）をそのまま再利用し、その出力を`ast.parse()`でローカル構文検証してから、3セル（説明markdown・`%%writefile main.py`・tarパッケージング）構成のnotebook JSON（辞書）を組み立てて`notebooks/submissions/lucario_agent_submission.ipynb`へ書き出す。`scripts/build_lucario_selfcheck_notebook.py`の`code_cell`/`md_cell`ヘルパーと同型のパターンを踏襲する。

**Tech Stack:** Python 3.12 / uv / 標準ライブラリのみ（`ast`, `json`, `sys`, `pathlib`）。テストは`pytest`。

## Global Constraints

- 設計書: `docs/superpowers/specs/2026-07-20-lucario-submission-notebook-generator-design.md`（ユーザー承認済み）
- スコープはルカリオexデッキ限定。他デッキへの汎用化は行わない
- `scripts/build_lucario_submission_main.py`は変更しない（`build()`をそのままimportして再利用する）
- 出力先は固定パス`notebooks/submissions/lucario_agent_submission.ipynb`（CLI引数での変更は不要）
- `ast.parse()`が失敗した場合はnotebookファイルを一切書き出さずに`sys.exit(1)`する
- コミットメッセージ・コードコメントは日本語で書く（CLAUDE.md 3節）
- 実装完了後、`docs/implementations/20260720-lucario-submission-notebook-generator.md`に実装サマリーを保存する（CLAUDE.mdフェーズ4）

---

## ファイル構成

- Create: `scripts/build_lucario_submission_notebook.py` — 新規ビルドスクリプト本体
- Create: `tests/test_build_lucario_submission_notebook.py` — 単体テスト＋E2Eテスト
- （既存・変更なし）`scripts/build_lucario_submission_main.py` — importして`build()`を再利用するのみ
- （既存・変更なし）`tests/test_build_lucario_submission_main.py` — 結合ロジック自体の検証は引き続きここが担当

### Task 3完了後の`scripts/build_lucario_submission_notebook.py`全体像（参考）

```python
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
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "scripts"
DST = ROOT / "notebooks" / "submissions" / "lucario_agent_submission.ipynb"

sys.path.insert(0, str(SCRIPTS_DIR))
import build_lucario_submission_main as submission_builder  # noqa: E402


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


def main() -> None:
    combined = submission_builder.build()
    validate_syntax(combined)
    nb = build_notebook(combined)
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {DST}")


if __name__ == "__main__":
    main()
```

各タスクはこのファイルを段階的に組み立てる。Task 1完了時点では`validate_syntax()`のみ、Task 2完了時点ではnotebook組み立て関数群まで、Task 3完了時点で上記の完成形になる。

---

### Task 1: `validate_syntax()` の実装

**Files:**
- Create: `scripts/build_lucario_submission_notebook.py`
- Test: `tests/test_build_lucario_submission_notebook.py`

**Interfaces:**
- Produces: `validate_syntax(combined: str) -> None`（構文エラーなら`sys.exit(1)`、正常なら何もせずreturn）。Task 2・Task 3で使用する

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_build_lucario_submission_notebook.py`を新規作成する：

```python
"""ルカリオex Kaggle提出用notebook自動生成スクリプトの単体テスト"""
import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_lucario_submission_notebook.py"
_spec = importlib.util.spec_from_file_location("build_lucario_submission_notebook", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # main()は__main__ガードで走らないため安全にimportできる


class TestValidateSyntax:
    def test_valid_source_does_not_exit(self):
        _mod.validate_syntax("def agent(): pass\n")  # 例外・SystemExitが起きなければOK

    def test_invalid_source_exits_with_error(self):
        with pytest.raises(SystemExit):
            _mod.validate_syntax("def agent(:\n")
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_build_lucario_submission_notebook.py -v`
Expected: FAIL（`scripts/build_lucario_submission_notebook.py`が存在しないため、収集(collection)時に`FileNotFoundError: ... build_lucario_submission_notebook.py`で失敗する）

- [ ] **Step 3: 最小限の実装を書く**

`scripts/build_lucario_submission_notebook.py`を新規作成する：

```python
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
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_build_lucario_submission_notebook.py -v`
Expected: PASS（2件とも）

- [ ] **Step 5: コミット**

```bash
git add scripts/build_lucario_submission_notebook.py tests/test_build_lucario_submission_notebook.py
git commit -m "feat(lucario): 提出用notebook生成スクリプトにvalidate_syntax()を追加"
```

---

### Task 2: `build_notebook()` の実装

**Files:**
- Modify: `scripts/build_lucario_submission_notebook.py`
- Modify: `tests/test_build_lucario_submission_notebook.py`

**Interfaces:**
- Consumes: なし（Task 1の`validate_syntax`とは独立した純粋関数）
- Produces: `build_notebook(combined: str) -> dict`（`nbformat`/`nbformat_minor`/`cells`を持つnotebook辞書）。Task 3の`main()`が使用する

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_build_lucario_submission_notebook.py`の末尾（`TestValidateSyntax`クラスの後）に追記する：

```python


class TestBuildNotebook:
    def test_nbformat_is_4(self):
        nb = _mod.build_notebook("def agent(): pass\n")
        assert nb["nbformat"] == 4

    def test_writefile_cell_contains_combined_source(self):
        nb = _mod.build_notebook("def agent(): pass\n")
        write_cells = [
            c for c in nb["cells"]
            if c["cell_type"] == "code" and c["source"].startswith("%%writefile main.py")
        ]
        assert len(write_cells) == 1
        assert "def agent(): pass" in write_cells[0]["source"]

    def test_package_cell_references_deck_and_cg_via_glob(self):
        nb = _mod.build_notebook("def agent(): pass\n")
        code_sources = "\n".join(
            c["source"] for c in nb["cells"] if c["cell_type"] == "code"
        )
        assert "glob.glob" in code_sources
        assert "deck.csv" in code_sources
        assert "cg-lib/cg" in code_sources
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_build_lucario_submission_notebook.py -v`
Expected: FAIL（`TestBuildNotebook`の3件が`AttributeError: module ... has no attribute 'build_notebook'`で失敗。`TestValidateSyntax`の2件はPASSのまま）

- [ ] **Step 3: 実装を書く**

`scripts/build_lucario_submission_notebook.py`の`validate_syntax`関数の後に追記する：

```python


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
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_build_lucario_submission_notebook.py -v`
Expected: PASS（5件とも）

- [ ] **Step 5: コミット**

```bash
git add scripts/build_lucario_submission_notebook.py tests/test_build_lucario_submission_notebook.py
git commit -m "feat(lucario): 提出用notebook生成スクリプトにbuild_notebook()を追加"
```

---

### Task 3: `main()`の実装・結線とE2Eテスト、全体回帰確認

**Files:**
- Modify: `scripts/build_lucario_submission_notebook.py`
- Modify: `tests/test_build_lucario_submission_notebook.py`

**Interfaces:**
- Consumes: `scripts/build_lucario_submission_main.py`の`build() -> str`（既存・変更なし）、Task 1の`validate_syntax`、Task 2の`build_notebook`
- Produces: `main()`（CLIエントリポイント）、`notebooks/submissions/lucario_agent_submission.ipynb`（生成物、`.gitignore`により非追跡）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_build_lucario_submission_notebook.py`冒頭のimport部分を次のように置き換える（`import json`, `import subprocess`, `import sys`を追加）：

置き換え前：
```python
"""ルカリオex Kaggle提出用notebook自動生成スクリプトの単体テスト"""
import importlib.util
from pathlib import Path

import pytest
```

置き換え後：
```python
"""ルカリオex Kaggle提出用notebook自動生成スクリプトの単体テスト"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
```

続けて、ファイル末尾（`TestBuildNotebook`クラスの後）に追記する：

```python


class TestMainEndToEnd:
    def test_generates_valid_notebook_without_internal_imports(self):
        result = subprocess.run(
            [sys.executable, str(_SCRIPT)],
            capture_output=True, text=True, check=True, cwd=_SCRIPT.parent.parent,
        )
        assert "wrote" in result.stdout

        dst = _SCRIPT.parent.parent / "notebooks" / "submissions" / "lucario_agent_submission.ipynb"
        assert dst.exists()
        nb = json.loads(dst.read_text(encoding="utf-8"))
        assert nb["nbformat"] == 4

        write_cells = [
            c for c in nb["cells"]
            if c["cell_type"] == "code" and c["source"].startswith("%%writefile main.py")
        ]
        assert len(write_cells) == 1
        assert "def agent(" in write_cells[0]["source"]
        assert "from lucario_agent" not in write_cells[0]["source"]
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_build_lucario_submission_notebook.py -v`
Expected: FAIL（`TestMainEndToEnd`の1件が失敗。`main()`が未実装のため`subprocess.run(..., check=True)`が非ゼロ終了コードで`CalledProcessError`を送出する。他の5件はPASSのまま）

- [ ] **Step 3: 実装を書く**

`scripts/build_lucario_submission_notebook.py`冒頭のimport部分を次のように置き換える：

置き換え前：
```python
import ast
import sys


def validate_syntax(combined: str) -> None:
```

置き換え後：
```python
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "scripts"
DST = ROOT / "notebooks" / "submissions" / "lucario_agent_submission.ipynb"

sys.path.insert(0, str(SCRIPTS_DIR))
import build_lucario_submission_main as submission_builder  # noqa: E402


def validate_syntax(combined: str) -> None:
```

続けて、ファイル末尾（`build_notebook`関数の後）に追記する：

```python


def main() -> None:
    combined = submission_builder.build()
    validate_syntax(combined)
    nb = build_notebook(combined)
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {DST}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_build_lucario_submission_notebook.py -v`
Expected: PASS（6件とも）

- [ ] **Step 5: リポジトリ全体で回帰確認**

Run: `uv run pytest -q`
Expected: 既存テスト全件＋今回追加した6件が全てPASS（失敗0件）。カレントの合計件数（561件）に今回の6件を加えた件数がPASSすること

- [ ] **Step 6: 生成物を実際に目視確認する**

Run: `cat notebooks/submissions/lucario_agent_submission.ipynb | python3 -m json.tool | head -50`
Expected: `cells`配列の1つ目がmarkdown（タイトル説明）、2つ目が`%%writefile main.py`から始まるコードセルであることを目視確認する

- [ ] **Step 7: コミット**

```bash
git add scripts/build_lucario_submission_notebook.py tests/test_build_lucario_submission_notebook.py
git commit -m "feat(lucario): 提出用notebook生成スクリプトにmain()を実装しCLIとして完成させる"
```

---

## 実装後の確認事項（次回持ち越し候補、設計書より再掲）

- グリムスナールex等、他デッキへの同種スクリプトの汎用化
- Kaggle API（`kaggle kernels push`等）を用いたアップロード自体の自動化（今回はローカルでの`.ipynb`生成までがスコープ）
