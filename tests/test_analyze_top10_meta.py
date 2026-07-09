import sys
from pathlib import Path

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
        card_data_csv=DATA_DIR / "EN_Card_Data.csv",
        catalog_dir=catalog_dir,
    )

    assert "# TOP10メタ分析レポート" in report
    assert "Kagura_UT" in report
    assert "Mega Lucario ex" in report  # デッキ分布に含まれる
    assert "アーキタイプ別出現回数" in report  # 集計セクションが存在する
    assert "84580427" in report  # 生ログへのリンクとして残る
