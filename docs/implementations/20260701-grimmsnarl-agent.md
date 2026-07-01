# 実装サマリー：マリィのグリムスナールex エージェント

**実装日：** 2026-07-01
**コミット範囲：** e56513e..b3fa497（9コミット）

---

## 概要

環境調査（バトルログ`82986745`解析）で発見した「マリィのオーロンゲ（グリムスナールex）」デッキを参考に、Rare Candyでの高速進化 + Punk Upによるエネルギー一括アタッチ + Shadow Bullet連打で戦うルールベースエージェントを実装した。

---

## 成果物

| ファイル | 説明 |
|---|---|
| `decks/grimmsnarl_20260701.py` | 60枚デッキ定義 |
| `src/grimmsnarl_agent/__init__.py` | パッケージエクスポート |
| `src/grimmsnarl_agent/main.py` | エージェント本体 |
| `tests/test_grimmsnarl_deck.py` | デッキ検証テスト（5件） |
| `tests/test_grimmsnarl_agent.py` | エージェント単体テスト（152件） |
| `src/grimmsnarl_agent.ipynb` | Kaggle提出用ノートブック（.gitignore対象） |
| `output/deck_20260701_160629.csv` | デッキCSV（Kaggleデータセット用） |

**テスト総数：** 157件 全PASS

---

## コミット一覧

| コミット | 内容 |
|---|---|
| `9294bad` | 設計書追加 |
| `e56513e` | 実装計画追加 |
| `6171977` | 設計書/計画書のデッキ59枚バグ修正（Impidimp 3→4） |
| `4035ce3` | デッキ定義（60枚・検証テスト5件） |
| `531ec67` | エージェント骨格・FieldState・_collect_field_state |
| `86cc128` | hand/discardループにNoneガード追加（レビュー修正） |
| `ead51ea` | スコアリング関数群（_score_play/attach/attack/card_option） |
| `764fc41` | _score_card_optionテスト追加（レビュー修正） |
| `022023b` | agent()完成・Kaggleノートブック作成 |
| `58dc11b` | PLAY/ATTACHにNoneガード追加（レビュー修正） |
| `b3fa497` | ABILITY/ATTACK/RETREATのスコア優先度修正（最終レビュー修正） |

---

## 主要設計決定

- **単一主軸アタッカー**: Grimmsnarl ex一本染め（Cinderace+Starmieのような二段構えではなく、進化+Punk Upで完結するシンプル設計）
- **Shadow Bulletのベンチ狙い撃ち**: `SelectContext.DAMAGE_COUNTER`で相手ベンチの中で最もHPが低い（KOに近い）ポケモンを狙う
- **スコア優先度の全体設計**: EVOLVE(10000+) > 確定KO可能なATTACK(5000) > ABILITY(2500/1200) > RETREAT(3000) > 非確定ATTACK(2000/1500/1000)
  - 当初はABILITYが低すぎて実質発動せず、RETREATが確定KOより優先されエネルギーを無駄にするバグがあったが、最終レビューで発見・修正
- **攻撃ID動的解決**: `_build_card_table()`で`all_card_data()`から実行時に取得（macOSで`libcg.so`が動かない対策、既存エージェントと同一パターン）

---

## レビューで発見・修正したバグ

1. **デッキ枚数バグ**（Task 1着手時）: 設計書・計画書ともに「12枚」と記載していたポケモン内訳が実際は11枚（合計59枚）だった → Impidimp 3→4枚に修正
2. **hand/discardループのNoneガード欠落**（Task 2レビュー）: 既存のCinderace+Starmieエージェントで一度修正済みの既知バグクラスが計画書に再度混入 → 修正・回帰テスト追加
3. **_score_card_optionのテスト欠落**（Task 3レビュー）: 最も複雑な分岐を持つ関数のテストが計画に含まれていなかった → 全分岐+DISCARD副作用のテストを追加
4. **agent()のPLAY/ATTACHのNoneガード欠落**（Task 4レビュー）: 同じく既知バグクラスの再混入 → 修正・回帰テスト追加
5. **ABILITY未発動・RETREATが確定KOより優先**（最終ブランチ全体レビュー）: 単体では気づけないスコアの相対的な大小関係の設計ミス → スコア帯を再設計して修正

---

## 未解消 Minor 所見（次PR推奨）

- `OptionType.EVOLVE`のNoneガード未対応（PLAY/ATTACH/ABILITY/CARDは対応済みだがEVOLVEのみ未対応）
- Munkidori Adrena-Brainのダメカン移動先・移動量の厳密な最適化（現状はABILITY選択の優先度のみ）
- Spiky Wheel（Morpeko）・Land Crush（Dudunsparce）のダメージ計算は簡易実装（付着エネルギー数に応じた動的スコアリングは未実装）

---

## 次のステップ

1. `output/deck_20260701_160629.csv` を Kaggle 新規データセット（例: `grimmsnarl-deck`）へアップロード
2. `src/grimmsnarl_agent.ipynb` を Kaggle にアップロードして対戦提出
3. スコア確認後、エージェントロジックの改善検討
