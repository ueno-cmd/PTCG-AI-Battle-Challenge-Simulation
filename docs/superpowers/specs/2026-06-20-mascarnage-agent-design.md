# マスカーニャexエージェント 設計ドキュメント

> 作成日: 2026-06-20
> ブレーンストーミング結果をもとに作成

---

## 概要

PTCG AI Battle Challenge（〜2026/8/17）に向けて、マスカーニャexデッキを使ったルールベーススコアリングエージェントを開発する。マスカーニャexがカードプールに存在しない場合はドラパルトexデッキに即切り替えられる設計とする。

---

## アプローチ

**B+C：クリーンな新実装 × 段階的育成**

- ドラパルトexサンプルを参考資料として、マスカーニャex専用にゼロから書く
- まず動く骨格を作って提出確認 → TDDで精度を上げるサイクルで進める
- RLは対象外（実行環境・評価コストの問題から除外）

---

## デッキ戦略

### マスカーニャexのコンセプト

| 要素 | 内容 |
|------|------|
| 特性「ブーケマジック」 | 手札の草エネ1枚をトラッシュ → 相手ベンチに30ダメ。場のマスカーニャex枚数分使用可 |
| ワザ「スクラッチネイル」 | 無色2個。相手にダメカンが乗っていれば220ダメージ |
| 基本思想 | 特性でベンチを削り、ダメカンが乗った相手をワザで倒す |
| ドラパルトexとの共通点 | 「ベンチにダメカンをばらまいて複数体を同時に追い詰める」思想が同じ |

### フォールバック

カードプールにマスカーニャexが存在しない場合 → ドラパルトexデッキに切り替え。スコアリングの骨格はそのまま流用できる。

---

## アーキテクチャ

### ファイル構成

```
src/
  mascarnage_agent/
    main.py          # エージェント本体（Kaggle Notebookに貼るもの）
    deck.csv         # デッキ構成60枚（カードID確認後に作成）
  tests/
    conftest.py      # モックセットアップ・Observationファクトリ
    test_scoring.py  # スコアリング関数の単体テスト
    test_agent.py    # agent()関数の統合テスト（明らかな誤り検出）
```

### main.pyの構造

```
1. デッキ読み込み + カードテーブル初期化（all_card_data）
2. 定数定義（カードID一覧）
3. ヘルパー関数
     get_card()           : エリア×インデックスからカードを取得
     prize_count()        : KO時のサイド枚数を計算
     no_damage_counter()  : ダメカンを置けない相手の判定
     bouquet_magic_score(): ブーケマジックターゲットのスコア計算
4. agent()本体
     全オプションにスコアを付けて降順でリスト返却
```

---

## スコアリング設計

**スコアは「強さ」ではなく「処理順序」を表す**（ドラパルトexと同じ思想）

| 優先度 | アクション | スコア目安 |
|--------|-----------|-----------|
| 最高 | 進化（EVOLVE） | 110,000+ |
| 高 | ポケモンをプレイ | 100,000+ |
| 高 | アイテムカード | 80,000+ |
| 高 | サポーターカード | 70,000+ |
| 中 | ブーケマジック発動（ABILITY） | 60,000+ |
| 中 | エネルギー付け（ATTACH） | 50,000+ |
| 低 | にげる（RETREAT） | 30,000+ |
| 最低 | 攻撃（ATTACK） | 1,000+ |
| 除外 | やりたくない行動 | -1 |

### ブーケマジックのターゲット選択（早期KO優先）

```python
def bouquet_magic_score(target: Pokemon) -> int:
    # HPが低いほど高スコア（倒しやすい順）
    score = 10000 - target.hp
    # すでにダメカンが乗っていればボーナス
    if target.hp < target.maxHp:
        score += 5000
    # ダメカンを置けない相手は除外
    if no_damage_counter(target):
        return -1
    return score
```

### スクラッチネイルの発動判定

- 相手バトルポケモンにダメカンが乗っている（`hp < maxHp`）→ 220ダメ確定、高スコア
- ダメカンなし → 60ダメのみ、スコアを下げる（他の行動を優先）

---

## ローカルTDD構造

### 目的

「明らかにおかしい挙動を弾く最低限のテスト」。攻撃チャンスなのに無関係なカードを使う等の意図しない挙動を事前に排除する。

### conftest.py

```python
import sys
from unittest.mock import MagicMock

# libcg.soをロードするsim.pyをモック（macOSで必須）
sys.modules['cg.sim'] = MagicMock()
sys.modules['cg.game'] = MagicMock()

from cg.api import (
    Observation, State, PlayerState, Pokemon,
    Card, SelectData, Option, OptionType, SelectContext, AreaType
)

def make_pokemon(id: int, hp: int, max_hp: int = None, **kwargs) -> Pokemon:
    return Pokemon(
        id=id, serial=0, hp=hp, maxHp=max_hp or hp,
        appearThisTurn=False, energies=[], energyCards=[],
        tools=[], preEvolution=[], **kwargs
    )
```

### test_scoring.py（例）

```python
def test_bouquet_prefers_low_hp_target():
    """HPが低い相手を優先的に狙う"""
    low  = make_pokemon(id=1, hp=30)
    high = make_pokemon(id=2, hp=200)
    assert bouquet_magic_score(low) > bouquet_magic_score(high)

def test_bouquet_skips_immune_target():
    """ダメカン免疫の相手はスコア-1"""
    immune = make_pokemon(id=207)  # ミロカロスex
    assert bouquet_magic_score(immune) == -1

def test_agent_attacks_when_ko_available():
    """KOできる状況で攻撃が最高スコアになる"""
    # 相手HPが攻撃で倒せる盤面を作ってagent()の返り値を確認
    ...
```

---

## 開発の流れ

```
Step 1（6/29以降）: カードプール確認
  └── KaggleのDataタブでマスカーニャexのIDを確認
  └── なければドラパルトexで即スタート（deck.csvを差し替えるだけ）

Step 2: デッキ構築
  └── EN_Card_Data.csvを参照してカードIDを特定
  └── deck.csvを作成（60枚、1行1枚）

Step 3: ローカルTDD（Mac）
  └── conftest.pyでモックセットアップ
  └── 明らかな誤りをテストして排除
  └── パスしたらコードをコピー

Step 4: Kaggle Notebookへ貼り付け
  └── %%writefile main.py でエージェント書き出し
  └── tar.gz生成（cg/ + deck.csv + main.py）
  └── 1投目はサンプルそのままで動作確認してから差し替える

Step 5: 提出 → 結果を見て調整（5回/日上限）
```

---

## 制約・リスク

| 制約 | 対応 |
|------|------|
| macOSでlibcg.soが動かない | Kaggle Notebookで実際のバトル確認。ローカルはTDDのみ |
| 提出5回/日 | ローカルTDDで弾いてから投げる。1投目はサンプルそのまま |
| マスカーニャexがカードプールにない可能性 | Step 1で確認。なければドラパルトexに即切替 |
| エラーログが見えにくい | サンプルで1投目を通してから差し替えていく |
