# 実装サマリー：Cinderace + Mega Starmie ex エージェント

**実装日：** 2026-06-30  
**コミット範囲：** bbd16b5..a4653b2（6コミット）

---

## 概要

Cinderace（エースバーン）の Turbo Flare でエネルギー加速し、Mega Starmie ex（メガスターミーex）が Nebula Beam 210 を連打する高速ワンパン型ルールベースエージェント。

---

## 成果物

| ファイル | 説明 |
|---|---|
| `decks/cinderace_starmie_20260630.py` | 60枚デッキ定義（Task 1） |
| `src/cinderace_starmie_agent/__init__.py` | パッケージエクスポート（Task 2） |
| `src/cinderace_starmie_agent/main.py` | エージェント本体（Task 2-4） |
| `tests/test_cinderace_starmie_deck.py` | デッキ検証テスト（4件） |
| `tests/test_cinderace_starmie_agent.py` | エージェント単体テスト（102件） |
| `src/cinderace_starmie_agent.ipynb` | Kaggle提出用ノートブック（.gitignore対象） |
| `output/deck_20260630_*.csv` | デッキCSV（Kaggleデータセット用） |

**テスト総数：** 106件 全PASS

---

## コミット一覧

| コミット | 内容 |
|---|---|
| `7c54deb` | デッキ定義（60枚・検証テスト4件） |
| `417959d` | エージェント骨格・FieldState・_collect_field_state |
| `6418eb6` | hand/discard の None チェック追加（レビュー修正） |
| `ef41af0` | スコアリング関数群（_score_play/attach/attack/card_option） |
| `9435d7f` | agent() 完成（全 OptionType 対応） |
| `a4653b2` | 最終レビュー Important 修正（PLAY/ATTACH None ガード・RETREAT 閾値） |

---

## 主要設計決定

- **攻撃ID動的解決**: `libcg.so` が macOS 非対応のため、`_build_card_table()` で `all_card_data()` から実行時に取得
- **Ignition Energy 戦略**: ターン終了で自動トラッシュされるため Cinderace に付けて Turbo Flare を毎ターン起動
- **Wally's Compassion ループ**: Mega Starmie ex のダメージ蓄積時に全回復 + エネルギー手札回収 → 次ターン Turbo Flare で再供給
- **攻撃閾値**: 設計書 210 を 170 に調整（HP 171-210 圏内は Nebula Beam でワンパン可能なため Jetting Blow 不要）

---

## 未解消 Minor 所見（次 PR 推奨）

- `_score_card_option` の単体テスト不足（SETUP_ACTIVE/SWITCH/TO_BENCH/DISCARD 各ケース）
- テストファイルの import が中段配置（PEP8）

---

## 次のステップ

1. `output/deck_20260630_*.csv` を Kaggle の新規データセット（例: `cinderace-starmie-deck`）へアップロード
2. `src/cinderace_starmie_agent.ipynb` を Kaggle にアップロードして対戦提出
3. スコア確認後、エージェントロジックの改善検討
