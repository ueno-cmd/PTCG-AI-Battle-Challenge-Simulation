# 実装サマリー：グリムスナールexデッキ 第3次改修（モルペコ再導入）

**実装日：** 2026-07-05
**関連設計書：** `docs/superpowers/specs/2026-07-05-grimmsnarl-morpeko-revision-design.md`

## 背景

イワパレス（特性「しんぴのいしやど」：相手の「ポケモン【ex】」からの技ダメージを
受けない）に対して、現行デッキのアタッカー（グリムスナールex・キチキギスex）が
両方exのため、ダメージを与える手段が実質存在しないことが判明した。あわせて、
ユキワラシ・ユキメノコ（Froslass）ラインが自傷ダメージ（特性「いてつくとばり」は
自分・相手両方の特性持ちポケモンにダメカンを乗せる）と展開遅延の原因になっており、
キチキギスexとオーロンゲexが同時気絶する事故が過去にあったため、あわせて整理した。

## 変更内容

### デッキ（`decks/grimmsnarl_20260701.py`）
- ユキワラシ(860)/ユキメノコ(104)/マシマシラ(112)を削除（合計7枚）
- マリィのモルペコ(649)を3枚新規採用（非exアタッカー。スパイキーホイール：
  20+装着悪エネルギー×40、上限なし）
- Buddy-Buddy Poffin(1086)を2→3枚に増量
- ギーマの一手(1230)を2枚、チェレン(1224)を1枚新規採用（展開速度対策）
- ポケモン20体→16体、トレーナーズ28枚→32枚（エネルギー12枚は変更なし）

### エージェントロジック（`src/grimmsnarl_agent/main.py`）
- 削除カード（Froslass/Munkidori）の定数・`SUPPORT_ONLY_IDS`・スコアリング分岐
  （`_score_attach`のMunkidori分岐、`ABILITY`のMunkidori優先度、`TO_BENCH | TO_HAND`の
  Munkidori分岐）を削除
- `FieldState.munkidori_bench_idx`を`morpeko_bench_idx`にリネームし、モルペコの
  装着エネルギー数を追跡する`morpeko_energy_count`を新規追加
- `_score_attach`：グリムスナールexの攻撃分（2エネ）確保後、余剰の基本エネルギーを
  モルペコにも配分できるよう追加（Fezandipiti_exと異なり上限を設けない）
- `_score_attack`：`Spiky_Wheel_ID`を`Shadow_Bullet_ID`/`Cruel_Arrow_ID`と同じパターンで
  `_build_card_table()`から取得し、装着エネルギー数から都度ダメージを計算して
  確定KOなら優先するスコアリングを追加
- `TO_BENCH | TO_HAND`：モルペコが未展開なら優先的にベンチへ出す判断を追加
- `_score_play`：ギーマの一手（ベンチが手薄なら優先）とチェレン（条件なしの安全牌）の
  PLAYスコアリングを追加

## テスト結果

- `tests/test_grimmsnarl_deck.py`：新構成向けテスト追加、全件PASS
- `tests/test_grimmsnarl_agent.py`：モルペコのエネルギー配分・攻撃スコアリング・
  ベンチ配置優先度、ギーマの一手・チェレンのPLAYスコアリングのテストを追加。
  削除カード参照（`gm.Munkidori`/`gm.Froslass`）は完全に除去
- リポジトリ全体：`uv run pytest -q` で全件PASS（回帰なし）

## 未対応・次回持ち越し

- モルペコ専用のRETREAT（撤退）判断ロジックは今回未対応（70HPと低耐久だが、
  既存のRETREATロジックはグリムスナールex専用のまま）
- 特性発動（パンクアップ）でモルペコに悪エネルギーを集中配分する際のカード選択
  （`ATTACH_FROM`等の文脈）への専用スコアリングは未対応。現状は通常のATTACHの
  エネルギー装着（Task 3）でのみモルペコへの配分を評価している
- 超高速デッキ（Mega Lucario ex、アラカザム）との相性問題は今回未対応
- 他デッキへの同種横展開は未着手
- Kaggle再提出後のLBスコア変化確認（本改修のスコープ外、ユーザーが手動で実施）
