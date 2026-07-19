"""TOP10メタ分析CLI。data/derived/top10_meta_targets.csvを読み、対象バトルログを
デッキ分布・意思決定パターンの2観点で集約したMarkdownレポートを生成する。

使い方: uv run python scripts/analyze_top10_meta.py [targets_csv]
（省略時は data/derived/top10_meta_targets.csv を使う）
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from etl.bronze import copy_to_bronze
from etl.gold import (
    classify_archetype,
    extract_attack_events,
    extract_deck_list,
    extract_play_events,
    extract_switch_events,
    find_player_index,
    load_card_names,
    load_raw_log,
)
from etl.silver import parse_to_silver


def _read_targets(targets_csv: Path) -> list[tuple[int, str]]:
    """targets_csvから(episode_id, target_player_name)のリストを読む（#始まりはコメント）"""
    targets = []
    with targets_csv.open(encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            # 手作業入力によるカンマ不足を検出し、行番号付きで分かりやすく報告する
            parts = line.split(",", 1)
            if len(parts) != 2:
                raise SystemExit(
                    f"targets_csvの記法が不正です（{line_number}行目: '{line}'）。"
                    "'episode_id,target_player_name' 形式にしてください"
                )
            episode_id_str, player_name = parts
            targets.append((int(episode_id_str), player_name))
    return targets


def build_report(
    targets_csv: Path,
    battle_logs_dir: Path,
    card_data_csv: Path,
    catalog_dir: Path,
) -> str:
    """対象ログを集計し、Markdownレポートを文字列として返す"""
    card_names = load_card_names(card_data_csv)
    deck_rows = []
    attack_rows = []
    play_rows = []

    for episode_id, player_name in _read_targets(targets_csv):
        src_path = battle_logs_dir / f"{episode_id}.json"
        # 手作業ダウンロード漏れ・ファイル名の入力ミスを分かりやすく報告する
        if not src_path.exists():
            raise SystemExit(f"バトルログが見つかりません: {src_path}（episode_id={episode_id}）")
        bronze_path = copy_to_bronze(src_path, catalog_dir)
        summary_path, _ = parse_to_silver(bronze_path, catalog_dir)
        with summary_path.open(encoding="utf-8") as f:
            summary = next(csv.DictReader(f))

        data = load_raw_log(src_path)
        target_index = find_player_index(data, player_name)
        deck_ids = extract_deck_list(data, target_index)
        archetype = classify_archetype(deck_ids, card_names)
        won = summary["winner_name"] == player_name

        deck_rows.append({
            "episode_id": episode_id,
            "player_name": player_name,
            "archetype": archetype,
            "won": won,
            "total_steps": summary["total_steps"],
        })

        for attack in extract_attack_events(data, target_index):
            card_id = attack["card_id"]
            card_label = card_names.get(card_id, (str(card_id), ""))[0]
            attack_rows.append({**attack, "episode_id": episode_id, "card_label": card_label})

        for play in extract_play_events(data, target_index):
            card_id = play["card_id"]
            card_label = card_names.get(card_id, (str(card_id), ""))[0]
            play_rows.append({**play, "episode_id": episode_id, "card_label": card_label})

    return _render_markdown(deck_rows, attack_rows, play_rows)


def _render_markdown(deck_rows: list[dict], attack_rows: list[dict], play_rows: list[dict]) -> str:
    lines = ["# TOP10メタ分析レポート", ""]

    lines.append("## デッキ分布")
    lines.append("")
    lines.append("| episode_id | プレイヤー | アーキタイプ | 勝敗 | ターン数 |")
    lines.append("|---|---|---|---|---|")
    for row in deck_rows:
        result = "勝ち" if row["won"] else "負け"
        lines.append(
            f"| {row['episode_id']} | {row['player_name']} | {row['archetype']} | "
            f"{result} | {row['total_steps']} |"
        )
    lines.append("")

    lines.append("### アーキタイプ別出現回数")
    lines.append("")
    lines.append("| アーキタイプ | 出現回数 |")
    lines.append("|---|---|")
    archetype_counts: dict[str, int] = {}
    for row in deck_rows:
        archetype_counts[row["archetype"]] = archetype_counts.get(row["archetype"], 0) + 1
    for archetype, count in sorted(archetype_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {archetype} | {count} |")
    lines.append("")

    lines.append("## 意思決定パターン：アタッカー別エネルギー数")
    lines.append("")
    lines.append("| アタッカー | 使用回数 | 平均エネルギー数（使用時点） |")
    lines.append("|---|---|---|")
    by_attacker: dict[str, list[int]] = {}
    for row in attack_rows:
        if row["energy_count"] is None:
            continue
        by_attacker.setdefault(row["card_label"], []).append(row["energy_count"])
    for label, counts in sorted(by_attacker.items()):
        avg = sum(counts) / len(counts)
        lines.append(f"| {label} | {len(counts)} | {avg:.1f} |")
    lines.append("")

    lines.append("## 意思決定パターン：サポート/トレーナーズカード使用ターン")
    lines.append("")
    lines.append("| カード | 使用回数 | 平均使用ターン |")
    lines.append("|---|---|---|")
    by_card: dict[str, list[int]] = {}
    for row in play_rows:
        by_card.setdefault(row["card_label"], []).append(row["turn"])
    for label, turns in sorted(by_card.items()):
        avg = sum(turns) / len(turns)
        lines.append(f"| {label} | {len(turns)} | {avg:.1f} |")
    lines.append("")

    lines.append("## 参照した生ログ")
    lines.append("")
    for row in deck_rows:
        lines.append(f"- `data/battle_logs/{row['episode_id']}.json`（{row['player_name']}）")

    return "\n".join(lines)


def main() -> None:
    targets_csv = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/derived/top10_meta_targets.csv")
    repo_root = Path(__file__).parent.parent
    report = build_report(
        targets_csv=targets_csv,
        battle_logs_dir=repo_root / "data" / "battle_logs",
        card_data_csv=repo_root / "data" / "competition" / "EN_Card_Data.csv",
        catalog_dir=repo_root / "data" / "unity-catalog",
    )
    output_dir = repo_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    import datetime
    today = datetime.date.today().isoformat().replace("-", "")
    output_path = output_dir / f"top10_meta_report_{today}.md"
    output_path.write_text(report, encoding="utf-8")
    print(f"レポートを出力しました: {output_path}")


if __name__ == "__main__":
    main()
