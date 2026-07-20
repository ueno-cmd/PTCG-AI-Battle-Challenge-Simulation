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
