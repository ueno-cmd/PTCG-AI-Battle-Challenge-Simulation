"""ドラパルトex `_attach_score()` ベンチ配分の再検証CLI

前回(2026-07-22)の分析はステップ単位のスナップショットで「今どちらがアクティブか」を
判定しており、1ステップに複数ターン分のイベントが混在しうる問題とSWITCHのフィールド名の
意味の取り違えにより結果が汚染された。本スクリプトはGameStateTrackerでイベントを
1件ずつ再生し、本番と同じ_attach_score()を使って矛盾件数を数え直す。

使い方: uv run python scripts/analyze_dragapult_attach_scoring.py \
    --target-player Kagura_UT data/battle_logs/8720*.json data/battle_logs/8721*.json
"""
import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data" / "competition" / "sample_submission"))

from unittest.mock import MagicMock  # noqa: E402

sys.modules.setdefault("cg.sim", MagicMock())
sys.modules.setdefault("cg.game", MagicMock())

from cg.api import Card, CardType  # noqa: E402

import dragapult_agent.main as dm  # noqa: E402
from etl.gold import (  # noqa: E402
    GameStateTracker, LOG_TYPE_ATTACH, build_event_timeline,
    find_player_index, load_pokemon_card_ids, load_raw_log, load_tool_card_ids,
)

CARD_DATA_CSV = ROOT / "data" / "competition" / "EN_Card_Data.csv"


def field_counts_from_tracker(tracker: GameStateTracker) -> dict:
    counts = {}
    for card_id in tracker.species.values():
        counts[card_id] = counts.get(card_id, 0) + 1
    return counts


def is_bench_attacker(tracker: GameStateTracker, dragapult_ex_id: int) -> bool:
    for serial in tracker.bench_serials:
        if tracker.species.get(serial) == dragapult_ex_id and tracker.energy_count[serial] >= 2:
            return True
    return False


def _own_candidates(tracker: GameStateTracker) -> list:
    """(serial, is_active)のリストを返す。アクティブ + ベンチ全員が候補"""
    candidates = []
    if tracker.active_serial is not None:
        candidates.append((tracker.active_serial, True))
    for serial in tracker.bench_serials:
        candidates.append((serial, False))
    return candidates


def evaluate_attach_event(tracker: GameStateTracker, event: dict, *, card_table: dict,
                           dragapult_ex_id: int) -> dict:
    """ATTACHイベント時点(適用前)の状態で、実際に選ばれた対象より高スコアの候補が
    存在するかを判定する。can_switchはTrue/False両方で試し、結果が割れる場合は
    'needs_manual_review'をTrueにする。

    dm.can_main_attackはagent()内部でしか更新されないモジュールグローバルなので、
    このスクリプトではagent()を一度も呼ばないため常にFalseのまま(呼び出し忘れではなく
    未設定のまま放置すると、既にファントムダイブが撃てる状態のアクティブを"まだ攻撃不可"と
    誤認し、本来正しいベンチ配分を誤って矛盾と判定してしまう)。そのためtracker状態から
    ここで明示的に再計算して都度セットする。閾値2は`bench_attacker`判定
    (main.py:398 `len(card.energies) >= 2`)と同じ、ファントムダイブの必要エネルギー数。
    """
    target_serial = event["serialTarget"]
    field_counts = field_counts_from_tracker(tracker)
    bench_attacker = is_bench_attacker(tracker, dragapult_ex_id)
    no_more_dex = field_counts.get(dragapult_ex_id, 0) * 2 >= tracker.opponent_prize_remaining
    dm.can_main_attack = (
        tracker.species.get(tracker.active_serial) == dragapult_ex_id
        and tracker.energy_count[tracker.active_serial] >= 2
    )

    class _Pokemon:
        def __init__(self, id, energies, energy_cards):
            self.id = id
            self.energies = energies
            self.energyCards = energy_cards

    def score_for(serial: int, is_active: bool, can_switch: bool) -> int:
        species_id = tracker.species[serial]
        energy_n = tracker.energy_count[serial]
        # pokemon.energyCards[0].idはenergy_count==1分岐で参照されるため、
        # tracker.energy_cards(装着済みエネルギーのcard_id列)から実際のCardを組み立てる。
        # energiesはlen()しか使われないためダミー値で十分
        energy_card_objs = [Card(id=cid, serial=0, playerIndex=0) for cid in tracker.energy_cards[serial]]
        pokemon = _Pokemon(species_id, [0] * energy_n, energy_card_objs)
        return dm._attach_score(
            event["cardId"], pokemon, is_active,
            card_table=card_table, can_switch=can_switch, bench_attacker=bench_attacker,
            no_more_dex=no_more_dex, field_counts=field_counts,
            my_asleep=tracker.asleep, my_paralyzed=tracker.paralyzed,
        )

    results = {}
    for can_switch in (True, False):
        candidates = _own_candidates(tracker)
        scores = {serial: score_for(serial, is_active, can_switch) for serial, is_active in candidates}
        chosen_score = scores[target_serial]
        better = [s for s, sc in scores.items() if sc > chosen_score]
        results[can_switch] = bool(better)

    contradiction_true = results[True]
    contradiction_false = results[False]
    return {
        "contradiction": contradiction_true or contradiction_false,
        "needs_manual_review": contradiction_true != contradiction_false,
    }


class _CardTypeEntry:
    """_attach_score()が参照するのは`.cardType`属性1つだけなので、
    CardData全体を組み立てず最小限のダミーで代用する"""
    def __init__(self, card_type):
        self.cardType = card_type


def _build_local_card_table(tool_card_ids: frozenset) -> dict:
    """全カードIDに対応する必要はなく、_attach_score()内の
    `card_table[attach_id].cardType == CardType.TOOL`という等価比較さえ
    再現できればよいため、Tool判定さえ分かればBASIC_ENERGY扱いで十分。

    dm._build_card_table()は実機(Kaggle)専用のネイティブライブラリ(cg.sim)を
    呼び出すため、macOS上のこのスクリプトからは使えない(呼ぶとクラッシュする)。
    """
    return collections.defaultdict(
        lambda: _CardTypeEntry(CardType.BASIC_ENERGY),
        {cid: _CardTypeEntry(CardType.TOOL) for cid in tool_card_ids},
    )


def build_report(battle_log_paths: list, target_player_name: str) -> str:
    tool_card_ids = load_tool_card_ids(CARD_DATA_CSV)
    pokemon_card_ids = load_pokemon_card_ids(CARD_DATA_CSV)
    local_card_table = _build_local_card_table(tool_card_ids)
    contradictions = []
    manual_review = []
    total_bench_attach = 0

    for log_path in battle_log_paths:
        data = load_raw_log(log_path)
        target_index = find_player_index(data, target_player_name)
        tracker = GameStateTracker(
            target_player_index=target_index, tool_card_ids=tool_card_ids,
            pokemon_card_ids=pokemon_card_ids,
        )
        timeline = build_event_timeline(data, player_index=target_index)
        for step_index, event in timeline:
            if (event.get("type") == LOG_TYPE_ATTACH
                    and event.get("playerIndex") == target_index
                    and event.get("cardId") not in tool_card_ids
                    and event.get("serialTarget") != tracker.active_serial):
                total_bench_attach += 1
                verdict = evaluate_attach_event(
                    tracker, event, card_table=local_card_table, dragapult_ex_id=dm.Dragapult_ex,
                )
                if verdict["needs_manual_review"]:
                    manual_review.append((log_path.stem, step_index))
                elif verdict["contradiction"]:
                    contradictions.append((log_path.stem, step_index))
            tracker.apply(event)

    lines = [
        "# ドラパルトex ベンチ向けエネルギー装着 再検証レポート",
        "",
        f"検証対象試合数: {len(battle_log_paths)}",
        f"ベンチ向けATTACHイベント総数: {total_bench_attach}",
        f"矛盾件数: {len(contradictions)}",
        f"要目視確認件数(can_switchの値次第で判定が割れる): {len(manual_review)}",
        "",
        "## 矛盾事例",
    ]
    for episode_id, step_index in contradictions:
        lines.append(f"- 試合{episode_id} step={step_index}")
    lines.append("")
    lines.append("## 要目視確認事例")
    for episode_id, step_index in manual_review:
        lines.append(f"- 試合{episode_id} step={step_index}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("battle_logs", nargs="+", type=Path)
    parser.add_argument("--target-player", required=True)
    args = parser.parse_args()
    print(build_report(args.battle_logs, args.target_player))


if __name__ == "__main__":
    main()
