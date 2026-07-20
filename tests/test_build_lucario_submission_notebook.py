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
