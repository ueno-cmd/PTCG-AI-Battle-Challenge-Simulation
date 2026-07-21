"""scripts/build_dragapult_submission_main.py が正しく単一ファイルを生成することを確認するテスト"""
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "build_dragapult_submission_main.py"


def _run_build() -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, check=True, cwd=ROOT,
    )
    return result.stdout


def test_build_output_contains_agent_function():
    combined = _run_build()
    assert "def agent(" in combined


def test_build_output_has_no_syntax_errors():
    combined = _run_build()
    ast.parse(combined)  # SyntaxErrorなら例外を投げてテスト失敗になる


def test_build_output_has_no_internal_package_imports():
    """結合後は dragapult_agent.* への相対importが残っていてはいけない
    （提出先には dragapult_agent パッケージ自体が存在しないため）"""
    combined = _run_build()
    assert "from dragapult_agent" not in combined


def test_build_output_preserves_cg_api_imports():
    """cg.api からのimportは strip 処理の対象外であり、結合後も残っていなければならない
    （将来の正規表現バグで cg.api の import まで誤って除去されると、
    構文エラーにはならず実行時エラーになるためこの陽性チェックで検出する）"""
    combined = _run_build()
    assert "from cg.api import" in combined
