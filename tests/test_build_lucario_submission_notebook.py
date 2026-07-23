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
