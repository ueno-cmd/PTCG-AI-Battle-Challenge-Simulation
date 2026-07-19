import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analyze_top10_meta import build_report

DATA_DIR = Path(__file__).parent.parent / "data"


def test_build_report_includes_deck_and_decision_sections(tmp_path):
    targets_csv = tmp_path / "targets.csv"
    targets_csv.write_text(
        "# 形式: episode_id,target_player_name\n"
        "84580427,Kagura_UT\n",
        encoding="utf-8",
    )
    catalog_dir = tmp_path / "catalog"

    report = build_report(
        targets_csv=targets_csv,
        battle_logs_dir=DATA_DIR / "battle_logs",
        card_data_csv=DATA_DIR / "competition" / "EN_Card_Data.csv",
        catalog_dir=catalog_dir,
    )

    assert "# TOP10メタ分析レポート" in report
    assert "Kagura_UT" in report
    assert "Mega Lucario ex" in report  # デッキ分布に含まれる
    assert "アーキタイプ別出現回数" in report  # 集計セクションが存在する
    assert "84580427" in report  # 生ログへのリンクとして残る


def test_build_report_missing_battle_log_raises_system_exit_with_episode_id(tmp_path):
    """存在しないepisode_idを指定した場合、生のFileNotFoundErrorではなく
    分かりやすいSystemExitが送出されることを確認する"""
    targets_csv = tmp_path / "targets.csv"
    missing_episode_id = 99999999
    targets_csv.write_text(
        f"{missing_episode_id},Kagura_UT\n",
        encoding="utf-8",
    )
    catalog_dir = tmp_path / "catalog"

    with pytest.raises(SystemExit) as exc_info:
        build_report(
            targets_csv=targets_csv,
            battle_logs_dir=DATA_DIR / "battle_logs",
            card_data_csv=DATA_DIR / "competition" / "EN_Card_Data.csv",
            catalog_dir=catalog_dir,
        )

    assert str(missing_episode_id) in str(exc_info.value)


def test_read_targets_missing_comma_raises_system_exit_with_line_number(tmp_path):
    """CSV行にカンマが不足している場合、行番号と行内容を含む
    分かりやすいSystemExitが送出されることを確認する"""
    targets_csv = tmp_path / "targets.csv"
    targets_csv.write_text(
        "# 形式: episode_id,target_player_name\n"
        "84580427,Kagura_UT\n"
        "invalid_line_without_comma\n",
        encoding="utf-8",
    )
    catalog_dir = tmp_path / "catalog"

    with pytest.raises(SystemExit) as exc_info:
        build_report(
            targets_csv=targets_csv,
            battle_logs_dir=DATA_DIR / "battle_logs",
            card_data_csv=DATA_DIR / "competition" / "EN_Card_Data.csv",
            catalog_dir=catalog_dir,
        )

    message = str(exc_info.value)
    assert "3行目" in message
    assert "invalid_line_without_comma" in message
