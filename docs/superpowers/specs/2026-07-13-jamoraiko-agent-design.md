# ジャモライコエージェント 設計書

## 背景・目的

現行のイオナ（ナンジャモ）デッキは`src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb`にインラインで実装されており、KaggleのLBで600〜877と**下落しない安定性**を示している（[[project_ptcg_competition]]参照）。10件のバトルログ解析の結果、以下が判明した。

- 7勝はいずれも「ハラバリーexの特性でエネルギーを一括装填し、ボルトーブのチェインボルトで先制フィニッシュする」速度コンボによるもの。うち5勝はフーディン系（進化を繰り返す遅いデッキ）相手で、進化の組み直しに時間を取られる相手には特に強い
- 3敗はいずれも環境トップメタ（メガルカリオex、Cinderace+メガスターミーex、アルクジラex+Cinderace）に力負けしたもので、デッキアウトや進化事故のような自滅パターンは一切なかった

一方で、現行デッキの主砲であるビリリダマ（HP70、チェインボルト）は火力効率・耐久面でボトルネックであり続けている。

実店舗のジムバトル（イオンモール・カードショップ）で2026年6月〜7/9にかけて6回優勝している「ジャモライコ」構成（ナンジャモ系ポケモン＋タケルライコex）は、この弱点を補う強力な代替フィニッシャーを持つ。本設計は、この構成をルールベースAIとして段階的に移植する**v1**の設計を定める。

## スコープ

### v1に含めるもの
- タケルライコexを含む4アタッカー体制のテーブル駆動スコアリング
- ハラバリーexの特性による雷エネルギー一括装填（既存イオナロジックの延長）
- タケルライコexへの基本闘エネルギーの**手貼りのみ**の優先度スコアリング
- 山札セーフティ（`_safe_draws`/`_deck_consumption`パターン）の最初からの統合

### v1に含めないもの（v2以降で検討）
- 基本闘エネルギーの自動サーチ・トラッシュ回収の周回ループ（エネルギー転送→手貼り→トラッシュ→エネルギー回収/夜のタンカでの意図的な再利用サイクル）。v1ではこれらのカードは既存パターン同様の汎用スコアリングに留め、周回を保証する専用ロジックは実装しない
- Kaggle提出用ノートブックへの転記（デッキCSV生成までを実装のゴールとし、実際のKaggleアップロード・提出はユーザー判断で別途行う）

## 前提として確認済みの事実

以下はゲームの実カードデータ（`data/EN_Card_Data.csv`, `data/JP_Card_Data.csv`）で裏取り済み。

| カード | ID | HP/効果 |
|---|---|---|
| タケルライコex | 63 | HP240。技1「はじけるほうこう」(コスト●・ダメージなし・手札全トラッシュ+6ドロー)。技2「きょくらいごう」(コスト{L}{F}・70×n・自分の場のポケモン全員についている基本エネルギーを好きなだけトラッシュしその枚数×70ダメージ) |
| ナンジャモのビリリダマ | 265 | HP70。「チェインボルト」(コスト●●・20+ナンジャモのポケモン全員についている雷エネ数×20ダメージ) |
| ナンジャモのズピカ | 268 | HP60。ハラバリーexの進化前 |
| ナンジャモのハラバリーex | 269 | HP280。特性「エレキストリーマー」(自分の番に何回でも、手札の基本雷エネルギーをナンジャモのポケモン誰にでも装填可)。「サンダーボルト」(コスト{L}{L}{L}●・230ダメージ・次の自分の番は技が使えない) |
| ナンジャモのカイデン | 270 | HP60。タイカイデンの進化前 |
| ナンジャモのタイカイデン | 271 | HP120。特性「フラッシュドロー」(自分についている基本雷エネルギー1個をトラッシュし、手札が6枚になるまでドロー、1ターン1回)。「マッハボルト」(コスト{L}●●・70ダメージ) |
| エネルギー転送 | 1119 | 山札から基本エネルギー1枚をサーチして手札に加える（**トラッシュ送りではない**。当初の理解を訂正） |
| つりざおMAX | 1110 | ACE SPEC。デッキ内1枚のみ採用（ルール準拠済み） |

7/9優勝レシピ60枚（[[project_ptcg_competition]]に記録）：タケルライコex2/ズピカ3/ハラバリーex3/カイデン3/タイカイデン3/ビリリダマ1/ハイパーボール4/なかよしポフィン4/エネルギー回収2/夜のタンカ3/エネルギー転送2/ポケモンいれかえ2/つりざおMAX1/リーリエの決心3/カナリィ4/ボスの指令2/ハッコウシティ3/基本雷エネルギー12/基本闘エネルギー3。

## アーキテクチャ

### モジュール構成
- `src/jamoraiko_agent/main.py` — エージェント本体。既存の`lucario_agent`/`grimmsnarl_agent`と同じ構成（カードID定数、`get_card`ヘルパー、`agent()`エントリポイント、`_score_*`系関数群）
- `decks/jamoraiko_20260713.py` — 60枚デッキ定義（上記レシピをそのまま移植）
- `tests/test_jamoraiko_deck.py` — デッキ構成テスト
- `tests/test_jamoraiko_agent.py` — スコアリングロジックのテスト

既存のイオナサンプル（`src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb`）は変更しない。ジャモライコは独立した新規デッキ・エージェントとして構築する。

### カードID定数（新規追加分）
```python
Raging_Bolt_ex          = 63    # タケルライコex
Iono_Voltorb             = 265  # ビリリダマ
Iono_Tadbulb             = 268  # ズピカ
Iono_Bellibolt_ex        = 269  # ハラバリーex
Iono_Wattrel             = 270  # カイデン
Iono_Kilowattrel         = 271  # タイカイデン
Basic_Lightning_Energy    = 4
Basic_Fighting_Energy     = 6   # lucario_agentと同じ定数名に統一
Energy_Search             = 1119  # 「エネルギー転送」
Switch                    = 1123  # ポケモンいれかえ
# Buddy_Buddy_Poffin / Night_Stretcher / Max_Rod / Energy_Retrieval /
# Ultra_Ball / Lillie_Determination / Canari / Boss_Orders / Levincia は
# 既存sample_notebookと同一IDのため流用
```

### コアロジック：テーブル駆動の4アタッカー体制

4つの技はダメージ計算式が固定値／盤面依存の可変値と異なるため、ダメージ計算を関数として持たせる。

```python
@dataclass(frozen=True)
class Attacker:
    id: int
    attack_id: int
    energy_required: int
    damage_fn: Callable[[FieldState], int]
    locks_next_turn: bool = False   # ハラバリーexのサンダーボルト用
    is_utility: bool = False        # タケルライコexのはじけるほうこう用

ATTACKERS = [
    Attacker(id=Iono_Voltorb, attack_id=VOLTAIC_CHAIN,
             energy_required=2,
             damage_fn=lambda fs: 20 + 20 * fs.iono_lightning_on_board),
    Attacker(id=Iono_Bellibolt_ex, attack_id=THUNDEROUS_BOLT,
             energy_required=4, damage_fn=lambda fs: 230, locks_next_turn=True),
    Attacker(id=Iono_Kilowattrel, attack_id=MACH_BOLT,
             energy_required=3, damage_fn=lambda fs: 70),
    Attacker(id=Raging_Bolt_ex, attack_id=BELLOWING_THUNDER,
             energy_required=2, damage_fn=lambda fs: 70 * fs.own_board_basic_energy_total),
]
ATTACKER_BY_ID = {a.id: a for a in ATTACKERS}
```

`FieldState`への追加フィールド：
- `iono_lightning_on_board` — 場の「ナンジャモのポケモン」全員についている雷エネルギー数
- `own_board_basic_energy_total` — 自分の場の全ポケモンについている基本エネルギー総数（きょくらいごうの理論上限ダメージ算出用）

（`VOLTAIC_CHAIN`/`THUNDEROUS_BOLT`/`MACH_BOLT`/`BELLOWING_THUNDER`は説明用の仮名。実際の`attackId`数値は実装時に`card_table`または対局中の`OptionType.ATTACK`選択肢から取得する）

**アタッカー選定ロジック**
1. アクティブなポケモンIDが`ATTACKERS`に一致し、`energy_required`を満たすものを抽出
2. 各`damage_fn(fs)`を評価し、相手アクティブの残りHP以上なら確定KO
3. 確定KOが複数ある場合、**盤面のエネルギーを消費しない技を優先**（きょくらいごうは他にKO手段がない場合のみ使用し、無駄なオーバーキルで場の資産を溶かさない）
   - **既知の制限（v1）**：これは「どの技を選ぶか」レベルでの資産温存であり、きょくらいごう自体を選んだ後の「エネルギーを何枚捨てるか」の選択は現状常に最大枚数を捨てる実装になっている（確定KOに必要な最小枚数に絞る最適化は未実装）。実バトルログで確認したところ、この捨て枚数選択は`SelectContext.DISCARD_ENERGY`（`OptionType.ENERGY`）による1枚ずつの繰り返し選択で実現されており、単純なNUMBER選択のスコア調整では対応できず、複数回の`agent()`呼び出しにまたがるターン内状態追跡の新規実装が必要と判明したため、v2に持ち越した
4. 確定KOがなければ最大ダメージの技を選ぶが、サンダーボルトは`locks_next_turn`ペナルティで減点評価
5. 有効な攻撃がなく手札が詰まっている場合のみ、はじけるほうこう（`is_utility`）を最終手段として選択

### エネルギー装填優先順位
- 基本雷エネルギー：エレキストリーマーは「ナンジャモのポケモン」全員が対象のため、既存イオナサンプルと同じ考え方で攻撃射程に近いポケモンから優先装填
- 基本闘エネルギー：v1では手貼りのみ。タケルライコexが場におり闘エネ未装填なら優先的に手貼りする単純な優先度のみ実装

### 山札セーフティ
`src/lucario_agent/main.py`で実装済みの`_safe_draws`/`_deck_consumption`パターンを実装当初から統合する。対象カード：
- リーリエの決心（3枚、山札を全て戻して6〜8枚ドロー）
- タイカイデンの特性「フラッシュドロー」（実質的な自己ミル）
- タケルライコexの「はじけるほうこう」（手札全トラッシュ+6ドロー）

## テスト方針
- `tests/test_jamoraiko_deck.py`：60枚構成・ACE SPEC（つりざおMAX1枚）準拠テスト
- `tests/test_jamoraiko_agent.py`：
  - `damage_fn`の単体テスト（各アタッカー×代表的な盤面パターン）
  - 確定KO優先・資産温存（きょくらいごう回避）の優先順位テスト
  - サンダーボルトの`locks_next_turn`減点テスト
  - エネルギー装填優先順位のテスト
  - 山札セーフティゲートのテスト（対象・非対象カードの回帰テスト）

## 未解決・次回以降の検討事項
- v2：きょくらいごうの捨て枚数を確定KOに必要な最小枚数に絞る最適化（現状は常に最大枚数を捨てる実装で、次ターン以降のタケルライコexが丸裸になりうる。実装には`SelectContext.DISCARD_ENERGY`の繰り返し選択に対応するターン内状態追跡が必要）
- v2：基本闘エネルギーのサーチ→手貼り→トラッシュ→回収の周回ループの自動化
- さくさくさんの追加の投稿・知見（ユーザーが後日共有予定）を反映するかどうかの再検討
- 実バトルログでの検証（きょくらいごうが本当に決め手として機能するか、イワパレスの特性を素通りできるかは未確認。[[feedback_verify_analysis_claims]]方針に従い、Kaggle提出後の実ログで確認する）
