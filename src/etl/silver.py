import csv
import json
from pathlib import Path


def parse_to_silver(bronze_path: Path, catalog_dir: Path) -> tuple[Path, Path]:
    """bronze JSONをパースしてsummaryとturnsのCSVを生成する"""
    # catalog_dirが存在しない場合は作成
    catalog_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(bronze_path.read_text(encoding="utf-8"))

    episode_id = data["info"]["EpisodeId"]
    agents = data["info"]["Agents"]
    rewards = data["rewards"]
    steps = data["steps"]

    # 報酬が最大のエージェントを勝者とする
    winner_index = rewards.index(max(rewards))
    winner_name = agents[winner_index]["Name"]

    summary_path = catalog_dir / f"silver_summary_{episode_id}.csv"
    turns_path = catalog_dir / f"silver_turns_{episode_id}.csv"

    # サマリーCSV（1試合1行）
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "episode_id", "player0_name", "player1_name",
                "winner_index", "winner_name", "total_steps",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "episode_id": episode_id,
            "player0_name": agents[0]["Name"],
            "player1_name": agents[1]["Name"],
            "winner_index": winner_index,
            "winner_name": winner_name,
            "total_steps": len(steps),
        })

    # ターン詳細CSV（1ステップ × 2エージェント = 2行/step）
    with turns_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "episode_id", "step", "agent_index",
                "action", "reward", "status", "logs_count",
            ],
        )
        writer.writeheader()
        for step_idx, step_list in enumerate(steps):
            for agent_index, agent_step in enumerate(step_list):
                # observation に step キーがない場合は、step_idx を使用
                step_val = agent_step["observation"].get("step", step_idx)
                writer.writerow({
                    "episode_id": episode_id,
                    "step": step_val,
                    "agent_index": agent_index,
                    "action": json.dumps(agent_step["action"]),
                    "reward": agent_step["reward"],
                    "status": agent_step["status"],
                    "logs_count": len(agent_step["observation"]["logs"]),
                })

    return summary_path, turns_path
