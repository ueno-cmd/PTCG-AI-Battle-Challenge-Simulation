# 実装サマリー：オーロンゲ（グリムスナールex）デッキ改修

**実装日：** 2026-07-02
**関連設計書：** `docs/superpowers/specs/2026-07-02-grimmsnarl-deck-revision-design.md`

## 背景

LBスコアが700から500へ下落し連勝できない状態だった。負けバトルログ5件
（83101226, 83110611, 83141570, 83169077, 83173685）を解析した結果、
デッキアウト負け（35ターン戦でダメージ優勢だったが山札切れ）と
進化事故負け（13ターン戦で1回も攻撃できず敗北）の2パターンが判明した。

## 変更内容

### デッキ（`decks/grimmsnarl_20260701.py`）
- ポケモン: Morpeko/Dudunsparce/Dunsparceを削除し、Froslass・Snorunt・Munkidori増量・
  Budew・Shaymin・Tatsugiri・Yveltal・Psyduckを新規採用（20体、旧構成から総入れ替え）
- トレーナーズ: Dawn・Xerosic's Machinations・Energy Recyclerを削除、
  Rare Candy/Buddy-Buddy Poffin/Night Stretcherを減量、
  Boss's Orders 2→3、Energy Switch・Air Balloon・Team Rocket's Petrelを新規採用（28枚）
- ACE SPEC: Hero's Cape → Secret Box に変更
- エネルギー: Basic {D} Energy 12枚（変更なし）

参考情報として、カードショップ大会（本大会ルールとは別環境）で使用されていた
オーロンゲデッキのリストをユーザーから受領し、カードプール収録カードのみを
採用した。プール未収録の「スペシャルレッドカード」「ムク」（ZA環境限定）は不採用。
「ガチグマ」は闘エネルギー依存で本デッキ（闇単色）では機能しないためユーザー判断で
不採用とし、闇エネルギーで機能する「イベルタル」に差し替えた。

### テスト（`tests/test_grimmsnarl_deck.py`）
- 削除カード（Morpeko/Dudunsparce/Dunsparce/Energy Recycler/Hero's Cape）の
  不在を検証するテストを追加
- Boss's Orders枚数・ACE SPEC種別のアサーションを新構成に合わせて更新

## テスト結果

- `tests/test_grimmsnarl_deck.py`: 10件全てPASS
- リポジトリ全体のテストスイート: 全件PASS（既存の他デッキ・エージェントへの影響なし）

## 未対応・次回持ち越し

- Kaggle再提出後のスコア変化確認（本改修のスコープ外）
- 超高速デッキ（Mega Lucario ex、アラカザム）との相性問題は今回未対応
  （デッキ構成のみでは解決しきれない範囲と判断）
- 「15-30-15」比率から外れたトールボックス構成による事故率増加リスクは
  ユーザー確認済みの既知のトレードオフ
