# 設計書：マリィのグリムスナールex エージェント

**作成日：** 2026-07-01
**ステータス：** 承認済み

---

## 概要

マリィのグリムスナールex（Marnie's Grimmsnarl ex）を単一主軸とした、進化エネルギー加速→連打型のルールベースエージェント。
バトルログ`82986745`（kazuki0123の勝利ログ）で確認された環境デッキを参考に、Rare Candyでの高速進化とPunk Up特性によるエネルギー一括アタッチを軸に構築する。

---

## デッキリスト（60枚）

### ポケモン（12枚）

| カード | Card ID | 枚数 | 役割 |
|---|---|---|---|
| Marnie's Impidimp | 646 | 3 | 進化元・Filchで初動ドロー・Buddy-Buddy Poffin対象（70HP） |
| Marnie's Morgrem | 647 | 1 | 進化中継（Rare Candyがない場合の保険） |
| Marnie's Grimmsnarl ex | 648 | 2 | **メインアタッカー**（Shadow Bullet 180+ベンチ30） |
| Marnie's Morpeko | 649 | 2 | 初動アタッカー・ベンチ要員 |
| Munkidori | 112 | 1 | Adrena-Brainでダメカンを相手に移しKOを補助 |
| Dudunsparce | 66 | 1 | ドローエンジン（Run Away Draw：ドロー3+自身シャッフル戻し） |
| Dunsparce | 305 | 1 | Dudunsparceの進化元・ベンチ要員 |

### エネルギー（10枚）

| カード | Card ID | 枚数 | 役割 |
|---|---|---|---|
| Basic {D} Energy | 7 | 10 | Punk Upが主エンジンのため少なめでよい |

### トレーナー（38枚）

| カード | Card ID | 枚数 | 役割 |
|---|---|---|---|
| Dawn | 1231 | 4 | 進化ライン一式サーチ |
| Rare Candy | 1079 | 4 | Impidimp→Grimmsnarl ex 一気進化 |
| Buddy-Buddy Poffin | 1086 | 4 | Impidimp/Munkidori/Dunsparceをベンチ展開 |
| Lillie's Determination | 1227 | 4 | 手札リフレッシュ（シャッフル+ドロー6） |
| Poké Pad | 1152 | 4 | ポケモンサーチ |
| Night Stretcher | 1097 | 4 | トラッシュからポケモン or 基本エネ回収 |
| Xerosic's Machinations | 1197 | 4 | 相手ハンド圧縮 |
| Energy Recycler | 1139 | 4 | エネルギー再利用 |
| Spikemuth Gym | 1259 | 3 | 毎ターンMarnie's系ポケモンをサーチ |
| Hero's Cape | 1159 | 3 | Grimmsnarl exに装着しHP+100（合計420） |

**枚数合計：** 12（ポケモン）+ 10（エネルギー）+ 38（トレーナー）= **60枚**（確定）

---

## 戦略コンセプト

### 理想展開

```
【1〜2ターン目】
  Impidimp をバトル場 or ベンチに展開
  Rare Candy で Impidimp → Marnie's Grimmsnarl ex に直接進化
  → Punk Up 発動：山から Basic {D} Energy 最大5枚を検索してアタッチ

【以降】
  Shadow Bullet（{D}{D} で 180ダメ + ベンチ1体に30ダメカン）を連打
  → Punk Up は進化時1回のみだが、5エネ蓄積で複数ターン攻撃可能
  → Munkidori がベンチにいれば Adrena-Brain でダメカンを移動しとどめを補助
```

### 状態変数（毎ターン計算）

```python
grimmsnarl_in_active     # バトル場が Grimmsnarl ex か
grimmsnarl_energy_count  # バトル Grimmsnarl ex のエネルギー枚数
impidimp_bench_idx       # ベンチ Impidimp の index（-1=不在）
rare_candy_in_hand       # 手札に Rare Candy があるか
munkidori_bench_idx      # ベンチ Munkidori の index（-1=不在）
op_active_hp             # 相手バトルポケモンのHP残量
op_bench_hp              # 相手ベンチ各ポケモンのHP残量（Shadow Bulletの30ダメ対象選定用）
```

### スコア設計

#### OptionType.EVOLVE（進化）

```
常に最優先（score = 10000 + エネルギー枚数）
Rare Candy による Impidimp → Grimmsnarl ex を最優先で発動（Punk Up起動のため）
```

#### OptionType.PLAY（手札からカードを使う）

| スコア | カード | 発動条件 |
|---|---|---|
| 9000 | Rare Candy | Impidimpが場におり、手札にGrimmsnarl exがある |
| 8000 | Buddy-Buddy Poffin | ベンチにImpidimp/Munkidori/Dunsparceが不在 |
| 7000 | Dawn | 進化ラインが手札に揃っていない |
| 5000 | Lillie's Determination | 手札が使えるカードに乏しい／先攻1ターン目 |
| 4000 | Poké Pad | 必要ポケモンが場・手札に不足 |
| 3000 | Xerosic's Machinations | 相手の手札が多い（妨害価値が高い） |
| 2000 | Night Stretcher | トラッシュに要復帰ポケモン or 基本エネがある |
| -1 | 上記以外 | 不要と判断された場合 |

#### OptionType.ATTACH（エネルギーをつける）

```
優先順位：
1. Punk Up が発動できない状況（進化前）でも Basic {D} Energy はバトル場ポケモンへ優先
2. Grimmsnarl ex のエネルギーが2枚未満なら最優先で付与（Shadow Bullet起動）
3. それ以外は Morpeko など次点アタッカーへ
```

#### OptionType.ATTACK（ワザ選択）

```
バトルポケモン = Marnie's Grimmsnarl ex：
  → エネルギー{D}{D}が揃っていれば Shadow Bullet を最優先（180 + ベンチ30）
  → ベンチ攻撃対象は相手ベンチの中で「30ダメでKOに近づく／されるポケモン」を優先選択

バトルポケモン = Marnie's Morpeko：
  → Spiky Wheel（20 + 付着{D}エネ1枚につき+40）で計算し、可能な最大ダメージを狙う

バトルポケモン = Dudunsparce：
  → Land Crush（90）を通常時の選択肢に含める
```

#### OptionType.ABILITY（特性）

```
Munkidori Adrena-Brain：{D}エネルギーが付いていれば毎ターン発動
  → 自分のポケモンのダメカンを最大3個、相手の弱いベンチポケモンへ移動しKOを狙う
Dudunsparce Run Away Draw：手札が乏しい時に発動（ドロー3+自身シャッフル戻し）
```

#### OptionType.RETREAT（逃げる）

```
Grimmsnarl exが瀕死（残りHPが相手の想定最大ダメージ以下）→ Morpekoへ逃げる
それ以外は逃げない（score = -1）
```

---

## ファイル構成

```
src/grimmsnarl_agent/
├── __init__.py
└── main.py          # エージェント本体（Kaggle %%writefile で転記）
decks/
└── grimmsnarl_20260701.py   # デッキリスト定義
```

既存の`cinderace_starmie_agent`と同一パターン（`FieldState` dataclass → `_collect_field_state()` → `OptionType`ごとのスコアリング関数 → `agent()`）を踏襲する。攻撃IDは`_build_card_table()`で`cg.api`の`all_card_data()`から実行時に動的解決する（macOSで`libcg.so`が動かないための既存対策）。

---

## 実装メモ

- Grimmsnarl exは **Stage 2** だが、Rare Candyでの直接進化を前提とする（Morgremは保険として1枚のみ採用）
- Punk Upは「進化時」トリガーの特性なので、EVOLVEのタイミングで即座にエネルギー付与処理が走る想定
- Shadow Bulletのベンチ30ダメは弱点・抵抗力を適用しない（カードテキスト通り）
- Munkidori の Adrena-Brain はダメカン移動であり新規ダメージ発生ではない点に注意（スコアリングでは「相手ポケモンをKOに近づける」効果として評価する）

---

## テスト方針

Cinderace+Starmieと同様にTDDで進める。
- デッキ検証テスト（`tests/test_grimmsnarl_deck.py`）：60枚ちょうど・カードID実在・進化ライン整合性
- エージェント単体テスト（`tests/test_grimmsnarl_agent.py`）：`_collect_field_state`のNoneガード、各スコアリング関数、`agent()`の全`OptionType`分岐

---

## 参考

- バトルログ解析結果：`data/unity-catalog/bronze_82986745.json` / `silver_summary_82986745.csv`
- 環境調査メモ：`memory/project_ptcg_competition.md`
- 既存エージェント参考：`docs/superpowers/specs/2026-06-30-cinderace-starmie-agent-design.md`
