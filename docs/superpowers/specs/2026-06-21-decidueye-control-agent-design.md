# ジュナイパーexコントロール エージェント 設計書

作成日: 2026-06-21

---

## 概要

ジュナイパーexの特性「Sniper's Eye」を核にした手札コントロールデッキのルールベースエージェント。  
相手の手札を4枚に固定して特性を常時発動させ、草エネルギー1枚で240ダメージ＋エネルギー剥がしを繰り返す。

---

## ファイル配置

```
src/decidueye_agent/
├── __init__.py
└── main.py          ← 単一ファイル（Kaggle %%writefile で転記）

tests/
└── test_decidueye_agent.py
```

---

## アーキテクチャ

Lucarioエージェント（`src/lucario_agent/main.py`）と同一構造を踏襲する。

```
main.py
├── カードID定数
├── card_table / my_deck（遅延初期化）
├── ターン状態管理（SnipersEyePlan dataclass）
├── ユーティリティ（get_card, prize_count, pokemon_score）
├── フィールド状態収集（_collect_field_state）
├── 攻撃プラン計算（calc_attack_plan）
├── スコアリング関数群
│   ├── _score_play_option
│   ├── _score_attach_option
│   └── _score_option
└── agent()  ← エントリーポイント
```

---

## コアロジック：Sniper's Eye 起動判定

```
op_hand_count = len(op_state.hand)

op_hand_count == 4  →  Sniper's Eye ON  → Crushing Arrow（{G}1枚）で240ダメ＋エネ剥がし
op_hand_count > 4   →  Judge を最優先（両者を4枚にリセット）
op_hand_count < 4   →  待機（相手がドローして4枚になるまで待つ）
```

---

## カードプレイ優先度

| スコア | カード | 発動条件 |
|---|---|---|
| 20000+ | ジュナイパーexへの進化 | 場にDartrix/Rowletあり |
| 10000+ | Judge | op_hand ≠ 4 かつ Decidueye ex 展開済み |
| 9000+ | Rare Candy | 手札にDecidueye ex + 場にRowlet |
| 8000+ | Xerosic's Machinations | op_hand > 4 |
| 7000+ | Ultra Ball / Bug Catching Set | Decidueye ex 未展開 |
| 5000+ | Buddy-Buddy Poffin | 序盤・ベンチ空き |
| 4000+ | Crushing Hammer | 相手ポケモンにエネルギーあり |
| 3000+ | Boss's Orders | 逃げポケを前に引き出す必要あり |
| 2000+ | Explorer's Guidance / Carmine | ドロー補充 |

---

## 攻撃プラン

- Decidueye ex が場にいてエネルギー ≥ 1 **かつ** op_hand == 4 → **Crushing Arrow**（attack index 1）
- それ以外 → 攻撃しない（0点）

---

## エネルギー付与先優先度

1. アクティブの Decidueye ex（エネルギー < 2）
2. ベンチの Decidueye ex
3. Teal Mask Ogerpon ex（Myriad Leaf Shower 用途）
4. その他

---

## テスト計画（最低5件）

1. 初回呼び出し（obs.select is None）でデッキリストを返す
2. op_hand == 4 かつ Decidueye ex にエネルギーあり → 攻撃スコアが最高
3. op_hand ≠ 4 かつ手札に Judge → Judge スコアが最高
4. Rowlet 在場 + 手札に Rare Candy + Decidueye ex → 進化スコアが最高
5. エネルギー付与選択肢 → Decidueye ex が最優先

---

## 制約・前提

- `cg.api` の `Observation`, `SelectContext`, `OptionType` など Kaggle 環境の API に依存
- ローカルテストは `tests/conftest.py` のモックを使用
- `main.py` は1ファイル完結（import はすべてトップレベル）
- ACE SPEC カード（Prime Catcher）は1枚のみ採用のため重複チェック不要
