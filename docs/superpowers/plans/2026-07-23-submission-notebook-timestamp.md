# 提出用notebookタイムスタンプ埋め込み Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kaggle提出用notebook（ドラパルトex・ルカリオex）の冒頭Markdownセルに、ビルドスクリプト実行時刻を「生成日時: YYYY-MM-DD HH:MM:SS」の形式で埋め込む。

**Architecture:** 各ビルドスクリプトのモジュールレベル定数`NOTE_MD`を、`datetime`を受け取って文字列を返す関数`note_md(generated_at)`に置き換える。`build_notebook()`に`generated_at`引数を追加し、`main()`が`datetime.now()`を明示的に渡す。既存の他の挙動（`main.py`セルの内容・パッケージングセル）には一切変更を加えない。

**Tech Stack:** Python標準ライブラリ（`datetime`）のみ。追加依存なし。

## Global Constraints

- 表示場所はnotebook冒頭のMarkdownセルのみ（`main.py`側のコードには埋め込まない）
- 時刻基準はビルドスクリプト実行時刻（`datetime.now()`、ローカル時刻）
- タイムスタンプ形式：`生成日時: YYYY-MM-DD HH:MM:SS`
- `generated_at`はデフォルト引数にせず、呼び出し側（`main()`・テスト）が明示的に渡す（`datetime.now()`をデフォルト値にするとimport時に評価されてしまうバグを避けるため）
- ドラパルトex用・ルカリオex用の2スクリプトに同一パターンを適用する
- 参照設計書：`docs/superpowers/specs/2026-07-23-submission-notebook-timestamp-design.md`

---

### Task 1: ドラパルトex用ビルドスクリプトへのタイムスタンプ埋め込み

**Files:**
- Modify: `scripts/build_dragapult_submission_notebook.py`
- Test: `tests/test_build_dragapult_submission_notebook.py`

**Interfaces:**
- Produces: `note_md(generated_at: datetime) -> str`、`build_notebook(combined: str, generated_at: datetime) -> dict`（既存の`build_notebook(combined: str)`から引数追加への破壊的変更）

- [ ] **Step 1: 既存テストを新シグネチャに追従させ、タイムスタンプ検証テストを追加する（失敗する状態で書く）**

`tests/test_build_dragapult_submission_notebook.py`の内容を以下で完全に置き換える。

```python
"""ドラパルトex Kaggle提出用notebook自動生成スクリプトの単体テスト"""
import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_dragapult_submission_notebook.py"
_spec = importlib.util.spec_from_file_location("build_dragapult_submission_notebook", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # main()は__main__ガードで走らないため安全にimportできる

_GENERATED_AT = datetime(2026, 7, 23, 15, 30, 0)


class TestValidateSyntax:
    def test_valid_source_does_not_exit(self):
        _mod.validate_syntax("def agent(): pass\n")  # 例外・SystemExitが起きなければOK

    def test_invalid_source_exits_with_error(self):
        with pytest.raises(SystemExit):
            _mod.validate_syntax("def agent(:\n")


class TestNoteMd:
    def test_contains_formatted_timestamp(self):
        md = _mod.note_md(_GENERATED_AT)
        assert "生成日時: 2026-07-23 15:30:00" in md


class TestBuildNotebook:
    def test_nbformat_is_4(self):
        nb = _mod.build_notebook("def agent(): pass\n", _GENERATED_AT)
        assert nb["nbformat"] == 4

    def test_writefile_cell_contains_combined_source(self):
        nb = _mod.build_notebook("def agent(): pass\n", _GENERATED_AT)
        write_cells = [
            c for c in nb["cells"]
            if c["cell_type"] == "code" and c["source"].startswith("%%writefile main.py")
        ]
        assert len(write_cells) == 1
        assert "def agent(): pass" in write_cells[0]["source"]

    def test_package_cell_references_deck_and_cg_via_glob(self):
        nb = _mod.build_notebook("def agent(): pass\n", _GENERATED_AT)
        code_sources = "\n".join(
            c["source"] for c in nb["cells"] if c["cell_type"] == "code"
        )
        assert "glob.glob" in code_sources
        assert "deck.csv" in code_sources
        assert "cg-lib/cg" in code_sources

    def test_markdown_cell_contains_generated_timestamp(self):
        nb = _mod.build_notebook("def agent(): pass\n", _GENERATED_AT)
        md_cells = [c for c in nb["cells"] if c["cell_type"] == "markdown"]
        assert len(md_cells) == 1
        assert "生成日時: 2026-07-23 15:30:00" in md_cells[0]["source"]


class TestMainEndToEnd:
    def test_generates_valid_notebook_without_internal_imports(self):
        result = subprocess.run(
            [sys.executable, str(_SCRIPT)],
            capture_output=True, text=True, check=True, cwd=_SCRIPT.parent.parent,
        )
        assert "wrote" in result.stdout

        dst = _SCRIPT.parent.parent / "notebooks" / "submissions" / "dragapult_agent_submission.ipynb"
        assert dst.exists()
        nb = json.loads(dst.read_text(encoding="utf-8"))
        assert nb["nbformat"] == 4

        write_cells = [
            c for c in nb["cells"]
            if c["cell_type"] == "code" and c["source"].startswith("%%writefile main.py")
        ]
        assert len(write_cells) == 1
        assert "def agent(" in write_cells[0]["source"]
        assert "from dragapult_agent" not in write_cells[0]["source"]

        md_cells = [c for c in nb["cells"] if c["cell_type"] == "markdown"]
        assert len(md_cells) == 1
        assert "生成日時: " in md_cells[0]["source"]
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_build_dragapult_submission_notebook.py -v`
Expected: `TestNoteMd`が`AttributeError: module ... has no attribute 'note_md'`等で FAIL。`TestBuildNotebook`の各テストは`build_notebook() takes 1 positional argument but 2 were given`で FAIL。

- [ ] **Step 3: `scripts/build_dragapult_submission_notebook.py`を実装する**

ファイル全体を以下で置き換える。

```python
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
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_build_dragapult_submission_notebook.py -v`
Expected: 全件 PASS

- [ ] **Step 5: コミット**

```bash
git add scripts/build_dragapult_submission_notebook.py tests/test_build_dragapult_submission_notebook.py
git commit -m "feat(dragapult): 提出用notebookにビルド時刻を埋め込む

Kaggle上でnotebookを開いた際に最新ソースが反映されているか
一目で判断できるよう、冒頭Markdownセルにビルド実行時刻を追記する。"
```

---

### Task 2: ルカリオex用ビルドスクリプトへのタイムスタンプ埋め込み

**Files:**
- Modify: `scripts/build_lucario_submission_notebook.py`
- Test: `tests/test_build_lucario_submission_notebook.py`

**Interfaces:**
- Consumes: なし（Task 1と同一パターンを別スクリプトに独立して適用するのみ）
- Produces: `note_md(generated_at: datetime) -> str`、`build_notebook(combined: str, generated_at: datetime) -> dict`（Task 1と同名だが別モジュール内の別関数）

- [ ] **Step 1: 既存テストを新シグネチャに追従させ、タイムスタンプ検証テストを追加する（失敗する状態で書く）**

`tests/test_build_lucario_submission_notebook.py`の内容を以下で完全に置き換える。

```python
"""ルカリオex Kaggle提出用notebook自動生成スクリプトの単体テスト"""
import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_lucario_submission_notebook.py"
_spec = importlib.util.spec_from_file_location("build_lucario_submission_notebook", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # main()は__main__ガードで走らないため安全にimportできる

_GENERATED_AT = datetime(2026, 7, 23, 15, 30, 0)


class TestValidateSyntax:
    def test_valid_source_does_not_exit(self):
        _mod.validate_syntax("def agent(): pass\n")  # 例外・SystemExitが起きなければOK

    def test_invalid_source_exits_with_error(self):
        with pytest.raises(SystemExit):
            _mod.validate_syntax("def agent(:\n")


class TestNoteMd:
    def test_contains_formatted_timestamp(self):
        md = _mod.note_md(_GENERATED_AT)
        assert "生成日時: 2026-07-23 15:30:00" in md


class TestBuildNotebook:
    def test_nbformat_is_4(self):
        nb = _mod.build_notebook("def agent(): pass\n", _GENERATED_AT)
        assert nb["nbformat"] == 4

    def test_writefile_cell_contains_combined_source(self):
        nb = _mod.build_notebook("def agent(): pass\n", _GENERATED_AT)
        write_cells = [
            c for c in nb["cells"]
            if c["cell_type"] == "code" and c["source"].startswith("%%writefile main.py")
        ]
        assert len(write_cells) == 1
        assert "def agent(): pass" in write_cells[0]["source"]

    def test_package_cell_references_deck_and_cg_via_glob(self):
        nb = _mod.build_notebook("def agent(): pass\n", _GENERATED_AT)
        code_sources = "\n".join(
            c["source"] for c in nb["cells"] if c["cell_type"] == "code"
        )
        assert "glob.glob" in code_sources
        assert "deck.csv" in code_sources
        assert "cg-lib/cg" in code_sources

    def test_markdown_cell_contains_generated_timestamp(self):
        nb = _mod.build_notebook("def agent(): pass\n", _GENERATED_AT)
        md_cells = [c for c in nb["cells"] if c["cell_type"] == "markdown"]
        assert len(md_cells) == 1
        assert "生成日時: 2026-07-23 15:30:00" in md_cells[0]["source"]


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

        md_cells = [c for c in nb["cells"] if c["cell_type"] == "markdown"]
        assert len(md_cells) == 1
        assert "生成日時: " in md_cells[0]["source"]
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_build_lucario_submission_notebook.py -v`
Expected: `TestNoteMd`が`AttributeError: module ... has no attribute 'note_md'`等で FAIL。`TestBuildNotebook`の各テストは`build_notebook() takes 1 positional argument but 2 were given`で FAIL。

- [ ] **Step 3: `scripts/build_lucario_submission_notebook.py`を実装する**

ファイル全体を以下で置き換える。

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
from datetime import datetime
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


def note_md(generated_at: datetime) -> str:
    return f"""## Rule-Based Agent for Mega Lucario ex

生成日時: {generated_at:%Y-%m-%d %H:%M:%S}

Kaggle提出用notebook。`scripts/build_lucario_submission_notebook.py` により
`src/lucario_agent/{{constants,combat,main}}.py` から自動生成されている。
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
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_build_lucario_submission_notebook.py -v`
Expected: 全件 PASS

- [ ] **Step 5: コミット**

```bash
git add scripts/build_lucario_submission_notebook.py tests/test_build_lucario_submission_notebook.py
git commit -m "feat(lucario): 提出用notebookにビルド時刻を埋め込む

Kaggle上でnotebookを開いた際に最新ソースが反映されているか
一目で判断できるよう、冒頭Markdownセルにビルド実行時刻を追記する。"
```

---

### Task 3: リポジトリ全体テスト確認と実装サマリー保存

**Files:**
- Create: `docs/implementations/20260723-submission-notebook-timestamp.md`

**Interfaces:**
- Consumes: Task 1・Task 2の変更結果

- [ ] **Step 1: リポジトリ全体のテストを実行し、既存テストに悪影響がないことを確認する**

Run: `uv run pytest -q`
Expected: 変更前から存在する失敗・エラー件数から増えていないこと（Task 1・2で変更した2ファイル分のテストは全件PASSであること）

- [ ] **Step 2: 実装サマリーを保存する**

`docs/implementations/20260723-submission-notebook-timestamp.md`を作成し、以下を記載する。
- 背景（2026-07-20のユーザー要望）
- 変更内容（`note_md(generated_at)`関数の新設、`build_notebook()`への引数追加、`main()`が`datetime.now()`を渡す）
- テスト結果（Step 1の実行結果）
- 次回notebook再生成時から新形式のタイムスタンプが反映される旨

- [ ] **Step 3: コミット**

```bash
git add docs/implementations/20260723-submission-notebook-timestamp.md
git commit -m "docs: 提出用notebookタイムスタンプ埋め込みの実装サマリーを追加"
```
