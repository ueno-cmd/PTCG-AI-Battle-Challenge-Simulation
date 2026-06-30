# 設計書：エースバーン + メガスターミーex エージェント

**作成日：** 2026-06-30  
**ステータス：** 承認済み

---

## 概要

Cinderace（エースバーン）のエネルギー加速特性を活かし、Mega Starmie ex（メガスターミーex）が毎ターン高火力ワザを叩き込む高速ワンパン型エージェント。  
環境トップランカー（keidroid・Yushin Ito）が使用するデッキをベースに、Wally's Compassion（ミツルの思いやり）による耐久ループを組み込む。

---

## デッキリスト（60枚）

### ポケモン（18枚）

| カード | Card ID | 枚数 | 役割 |
|---|---|---|---|
| Scorbunny | 664 | 4 | Cinderace進化元・Buddy-Buddy Poffin対象（70HP） |
| Raboot | 665 | 2 | 中間進化 |
| Cinderace | 666 | 4 | エネ加速役（Explosiveness特性でバトル場スタート可） |
| Staryu | 1030 | 4 | Mega Starmie ex進化元・Buddy-Buddy Poffin対象（70HP） |
| Mega Starmie ex | 1031 | 4 | メインアタッカー（HP330、Hero's Cape装着で430） |

### トレーナー（27枚）

| カード | Card ID | 枚数 | 役割 |
|---|---|---|---|
| Buddy-Buddy Poffin | 1086 | 4 | Scorbunny + Staryu を1枚で同時ベンチへ |
| Ultra Ball | 1121 | 3 | 万能サーチ（手札2枚コスト） |
| Mega Signal | 1145 | 3 | Mega Starmie ex専用サーチ |
| Night Stretcher | 1097 | 2 | トラッシュからポケモン or 基本エネ回収 |
| Hero's Cape | 1159 | 1 | Mega Starmie ex に装着 → HP+100（合計430） |
| Pokégear 3.0 | 1122 | 3 | 山上7枚からサポート1枚を手札へ |
| Crushing Hammer | 1120 | 1 | 相手エネルギー破壊（妨害） |
| Salvatore | 1189 | 3 | Staryu → Mega Starmie ex を直接進化（アビリティなし対象） |
| Hilda | 1225 | 3 | 進化ポケモン + エネルギーカードを同時サーチ |
| Lillie's Determination | 1227 | 2 | 手札シャッフル後ドロー6枚（先攻1ターン目ボーナス） |
| Wally's Compassion | 1229 | 2 | メガシンカex全回復 + 付属エネを手札回収（ループの核） |

### エネルギー（15枚）

| カード | Card ID | 枚数 | 役割 |
|---|---|---|---|
| Basic Water Energy | 3 | 11 | Turbo Flare付与先・Jetting Blow / Nebula Beam の燃料 |
| Ignition Energy | 17 | 4 | Cinderace Turbo Flare起動用（ターン終了時自己トラッシュ） |

---

## 戦略コンセプト

### 理想展開

```
【1ターン目】
  Cinderace バトル場（Explosiveness特性でたね扱いなしスタート）
  → Ignition Energy を Cinderace にアタッチ
  → Turbo Flare 発動：山から基本水エネ3枚 → ベンチ Mega Starmie ex へ
  → ターン終了：Ignition Energy 自動トラッシュ

【2ターン目】
  Salvatore / Mega Signal で Staryu → Mega Starmie ex に進化
  → リトリートまたは入れ替えで Mega Starmie ex をバトル場へ
  → Nebula Beam 210（弱点・抵抗力・効果を無視）

【以降：Wally's Compassionループ】
  Mega Starmie ex がダメージを蓄積したら
  → Wally's Compassion：全ダメージ回復 + エネルギーを手札へ
  → 次ターン Cinderace Turbo Flare でエネルギー再供給
  → Mega Starmie ex 再登場 → Nebula Beam 210
```

---

## エージェントロジック設計

### 状態変数（毎ターン計算）

```python
cinderace_in_active    # バトル場がCinderace でエネ1枚以上あるか
starmie_bench_idx      # ベンチのMega Starmie ex のindex（-1=不在）
starmie_bench_energy   # ベンチStarmieのエネルギー枚数
op_active_hp           # 相手バトルポケモンのHP残量
wally_in_hand          # 手札にWally's Compassionがあるか
starmie_active_dmg     # バトルStarmieが受けているダメージ
```

### スコア設計

#### OptionType.PLAY（手札からカードを使う）

| スコア | カード | 発動条件 |
|---|---|---|
| 10000 | Lillie's Determination | 残プライズ = 6（先攻1ターン目） |
| 8000 | Buddy-Buddy Poffin | 両ラインのたねがベンチに不在 |
| 7000 | Salvatore | Staryuがいて、Starmieが場・手札に不在 |
| 6500 | Wally's Compassion | バトルStarmieにダメージがある |
| 5000 | Hilda | Cinderace または Starmie が不足 |
| 4500 | Mega Signal | Starmieが場に不在 |
| 4000 | Pokégear 3.0 | 手札にサポートがない |
| 3000 | Ultra Ball | 必要ポケモンが手札・場に不足 |
| 3000 | Lillie's Determination | 通常時（ドロー目的） |
| 2000 | Night Stretcher | トラッシュにStaryu or 水エネがある |
| 1000 | Crushing Hammer | 妨害（低優先） |
| -1 | 上記以外 | 不要と判断された場合 |

#### OptionType.ATTACH（エネルギーをつける）

```
優先順位：
1. Ignition Energy → Cinderace（Turbo Flare起動用）
2. 基本水エネルギー → ベンチ Mega Starmie ex（エネ2枚以下のとき）
3. 基本水エネルギー → バトル Mega Starmie ex（Jetting Blow維持）
4. その他（Scorbunny・Staryu等には基本的につけない）
```

#### OptionType.ATTACK（ワザ選択）

```
バトルポケモン = Cinderace：
  → Turbo Flare を最優先（ベンチStarmieへ水エネ3枚付与）

バトルポケモン = Mega Starmie ex：
  → 相手HP > 210、または相手バトルに効果がかかっている
      → Nebula Beam（210・弱点/抵抗力/効果を無視）
  → 相手HP ≤ 210、またはベンチへのプレッシャーが有効
      → Jetting Blow（120 + ベンチ50）
```

#### OptionType.SWITCH / TO_ACTIVE（入れ替え）

```
スイッチを優先する場面：
  - ベンチStarmieのエネ ≥ 1 かつ Cinderaceのターボ済み
  - Cinderaceが瀕死（HP少ない）
  - ベンチStarmieのエネ ≥ 3（Nebula Beam即撃ち可能）

スイッチしない場面：
  - Turbo Flare未発動でStarmieのエネが0
  - バトルStarmieが安全に攻撃できる
```

#### OptionType.EVOLVE（進化）

```
常に最優先（score = 10000 + エネルギー枚数）
進化は遅らせない。
```

#### OptionType.TO_BENCH / TO_HAND（ベンチ・手札への追加）

```
優先順位（高→低）：
  1. Mega Starmie ex（場にいない場合）
  2. Cinderace（Explosiveness特性でバトル場候補）
  3. Staryu（Mega Starmie ex の進化元）
  4. Scorbunny（Cinderace 進化元）
```

#### OptionType.ABILITY（特性）

```
Cinderace Explosiveness（初期設置）：使用可能なら常に発動（score = 5000）
```

#### OptionType.RETREAT（逃げる）

```
バトルStarmieにダメージ + 手札にWally's Compassion → score = 3000（回復ループ準備）
ベンチにStarmieが準備完了（エネ≥3） → score = 2000
それ以外 → score = -1（逃げない）
```

---

## ファイル構成

```
src/cinderace_starmie_agent/
└── main.py          # エージェント本体（Kaggle %%writefile で転記）
decks/
└── cinderace_starmie_20260630.py   # デッキリスト定義
```

---

## 実装メモ

- Cinderaceは **Stage 2** だが `Explosiveness` 特性により初期バトル場に置ける（`SETUP_ACTIVE_POKEMON` コンテキストで高スコア付与）
- Salvatore は「アビリティを持たない進化先」のみ対象 → Staryu→Mega Starmie ex に使える（Mega Starmie exはアビリティなし）
- Salvatore は Cinderace（Explosiveness特性あり）には使えない
- Ignition Energy はターン終了で自動トラッシュされるため、Turbo Flare の付与先として使い回せる
- Wally's Compassion はエネルギーを手札に戻すため、Turbo Flare での再供給と相性が良い
- 攻撃IDは `cg.api` の `all_card_data()` で取得した実値を使う

---

## 参考

- バトルログ解析結果（`data/unity-catalog/`）
- 環境調査メモ：`memory/project_ptcg_competition.md`
- 既存エージェント参考：`src/a-sample-rule-based-agent-mega-abomasnow-ex-deck.ipynb`
