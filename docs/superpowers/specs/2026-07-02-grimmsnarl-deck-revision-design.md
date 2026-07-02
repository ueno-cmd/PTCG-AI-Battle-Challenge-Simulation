# オーロンゲ（グリムスナールex）デッキ改修 設計書

**作成日：** 2026-07-02
**関連メモリ：** project_ptcg_competition.md（2026-07-01 ボスの指令導入時点の状態から更に改修）

## 背景・課題

Kaggle LBでオーロンゲ（グリムスナールex）デッキのスコアが700から500へ下落。連勝できていない。

直近の負けバトルログ5件（83101226, 83110611, 83141570, 83169077, 83173685）を解析した結果、以下2つの敗因パターンが判明した。

1. **デッキアウト負け**：Archaludon ex/Cinderace戦（35ターン）で、ダメージ量は自分優勢（3810 vs 630）だったにもかかわらず山札切れで敗北。`Dawn`（1回で3枚サーチ）・`Xerosic's Machinations`・`Poké Pad`・`Buddy-Buddy Poffin`など山札を掘るカードの重複が主因と推定。
2. **進化事故負け**：miura-iori戦（13ターン）で1回も攻撃できないまま敗北。`Marnie's Morgrem`が1枚のみで、`Rare Candy`不発時の保険が薄いことが一因と推定。

加えて、ユーザーが参加したカードショップ大会（本大会ルールとは異なる環境）で使用されていたオーロンゲデッキのリストを参考情報として取得し、上記課題への対策として採用可能な構成要素を精査した。

## 変更方針

大会リストのうち、本コンペのカードプール（`data/EN_Card_Data.csv` 2103種、ZA環境の新カードは未収録）に存在するカードのみを採用し、以下の2枚は不採用とした。

- **スペシャルレッドカード**：カードプールに該当カードなし
- **ムク**：ZA環境限定カードのためカードプール未収録

さらに、大会リストの「ガチグマ（Bloodmoon Ursaluna）」は特性・ワザともに闘エネルギー依存だが、本デッキは闇エネルギーのみで運用するため機能しないと判明。ユーザー判断により**不採用とし、闇エネルギーで機能する「イベルタル」（わしづかみ：相手を次のターン逃げられなくする）に差し替えた**。

## 新デッキ構成（60枚）

### ポケモン：20体

| Card ID | カード名 | 枚数 | 変更前 |
|---|---|---|---|
| 646 | Marnie's Impidimp | 3 | 4 |
| 647 | Marnie's Morgrem | 2 | 1 |
| 648 | Marnie's Grimmsnarl ex | 3 | 2 |
| 860 | Snorunt | 2 | 0（新規） |
| 104 | Froslass | 2 | 0（新規） |
| 112 | Munkidori | 3 | 1 |
| 235 | Budew | 1 | 0（新規） |
| 343 | Shaymin（特性「はなのカーテン」版） | 1 | 0（新規） |
| 122 | Tatsugiri | 1 | 0（新規） |
| 689 | Yveltal | 1 | 0（新規・ガチグマの代替） |
| 858 | Psyduck | 1 | 0（新規） |

削除：Marnie's Morpeko（649）、Dudunsparce（66）、Dunsparce（305）

### トレーナーズ：28枚

| Card ID | カード名 | 枚数 | 変更前 |
|---|---|---|---|
| 1152 | Poké Pad | 4 | 4 |
| 1079 | Rare Candy | 3 | 4 |
| 1086 | Buddy-Buddy Poffin | 2 | 4 |
| 1097 | Night Stretcher | 2 | 4 |
| 1227 | Lillie's Determination | 4 | 4 |
| 1182 | Boss's Orders | 3 | 2 |
| 1259 | Spikemuth Gym | 3 | 3 |
| 1116 | Energy Switch | 2 | 0（新規） |
| 1092 | Secret Box（ACE SPEC） | 1 | 0（新規） |
| 1174 | Air Balloon | 1 | 0（新規） |
| 1219 | Team Rocket's Petrel | 3 | 0（新規） |

削除：Dawn（1231）、Xerosic's Machinations（1197）、Energy Recycler（1139）、Hero's Cape（1159、ACE SPECをSecret Boxに統合）

### エネルギー：12枚

| Card ID | カード名 | 枚数 |
|---|---|---|
| 7 | Basic {D} Energy | 12（変更なし） |

## 診断済み課題への対応

1. **デッキアウト対策**：`Dawn`（3枚サーチ）と`Xerosic's Machinations`を削除し、山札消費の大きいトレーナーズを整理。
2. **進化事故対策**：`Morgrem` 1→2、`Grimmsnarl ex` 2→3で進化ラインを厚く。`Team Rocket's Petrel`（トレーナーズ全般サーチ）と`Tatsugiri`特性（山札上から6枚を見てサポートを回収）で狙ったカードへのアクセスを補強。
3. **プライズレース強化**：`Boss's Orders` 2→3、`Yveltal`の足止め効果でKO率向上。

## 既知のトレードオフ（ユーザー確認済み）

- ポケモン20体・トレーナーズ28枚という配分は、教科書的な「15-30-15」比率から外れる。これはトールボックス型構成（1枚差しの特性ポケモンを多用）の特性であり、汎用ドロー（Dawn等）を削減した分、状況に応じた1枚を引き当てる力は`Poké Pad`・`Team Rocket's Petrel`・`Tatsugiri`特性に依存する。事故率がやや上がる可能性はあるが、デッキアウト対策とのトレードオフとしてユーザー承認済み。
- 環境上位の超高速デッキ（Mega Lucario ex、アラカザム）への根本対策ではない（相性問題であり60枚構成のみでは解決しきれない範囲）。

## 影響範囲

- `decks/grimmsnarl_20260701.py`：DECKリストを上記内容に更新
- `tests/test_grimmsnarl_deck.py`：削除されたカード（Morpeko/Dudunsparce/Dunsparce/Energy Recycler）や変更された枚数（Boss's Orders等）を検証するアサーションを新デッキ内容に合わせて更新。ACE_SPEC_IDSをHero's Cape（1159）からSecret Box（1092）に更新
- `output/`：新しい`deck_YYYYMMDD_HHMMSS.csv`を生成
- `src/grimmsnarl_agent/main.py`：**変更なし**（今回はデッキ構成のみの修正がスコープ。エージェントロジックは対象外）
