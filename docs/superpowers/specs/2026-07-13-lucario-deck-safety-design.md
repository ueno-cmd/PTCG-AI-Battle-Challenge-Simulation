# ルカリオexデッキ 山札セーフティ移植 設計書

- 日付: 2026-07-13
- 対象: `src/lucario_agent/main.py`
- 前提分析: ルカリオの直近バトルログ12件（2勝10敗、`Kagura_UT`視点）の敗因分析（本設計の根拠。下記「背景」参照）
- 関連: `docs/superpowers/specs/2026-07-12-grimmsnarl-promotion-deck-safety-design.md`（移植元の設計）

## 背景（ログ分析で確定した敗因）

ユーザーが手動DLしたルカリオの直近ログ12件（85600090〜85666055）を解析した。全てクラッシュなし（`statuses`は全`DONE`）、使用デッキは現行`decks/lucario_20260621.py`（60枚）と完全一致。

- 2勝10敗。うち9敗（85600090, 85601749, 85603730, 85604334, 85606033, 85614705, 85621789, 85643894, 85654828）はプライズ先取レースで相手が1〜4枚先行し押し切られたもので、目立つ立ち往生・クラッシュ・誤選出は確認できなかった（対戦相手のデッキパワー・相性の問題である可能性が高く、本設計のスコープ外）
- **85626724（対メガガルーラex×4）だけが明確な構造上のバグによる負け**：32ターンの長期戦で、自分がプライズ3枚先取（相手は1枚）と有利だったにもかかわらず、**山札が0枚になりデッキアウトで敗北**した
- 原因を特定：`lucario_agent`の山札対策は`DECK_SAFETY_THRESHOLD = 15`という固定しきい値で、**「ミツルの思いやり」（Lillie's Determination）と「ルナサイクル」（Lunatoneの特性）の2つだけ**を止める仕組みだった。ヒルダ・ポケギア3.0・ハイパーボール・暗号マニアの解読など他のドロー/サーチ系カードは山札残数を一切見ずに使用され続けており、実際にT17で山札残9枚の状態でポケギア3.0を使うなど終盤も歯止めがかからなかった
- これは2026-07-02〜07-12にグリムスナールexで発見・修正済みの「山札セーフティ」バグと同じ種類の穴であり、修正パターン（`_safe_draws`＝山札残数−残りプライズ数−1で全ドロー系カードを一括ゲート）をそのまま移植できると判断した

## スコープ

グリムスナールexの`_safe_draws`方式をルカリオに移植する。ユーザー承認済みの方針：
- **フラグ化・Kaggle校正実験は行わない**（既にグリムスナールで実戦検証済みの安全側の仕組みであり、A/Bで効果を測るまでもなく直接有効化する）
- 既存の`DECK_SAFETY_THRESHOLD`（`Lillie's Determination`とLunatone特性の2箇所のみをゲート）は廃止し、新しい仕組みに一本化する
- グリムスナールの`FieldState`ラッパーは導入しない。ルカリオの既存コードは`my_state`・`hand_counts`を直接関数に渡すスタイルのため、それに合わせる

**スコープ外**：9敗（プライズレース負け）の分析・対策、デッキ構成の変更（deck.csv再生成不要）、メガルカリオexミラー戦の意思決定差の深掘り。

## 設計

### 1. 新設ヘルパー

```python
def _safe_draws(my_state) -> int:
    """安全に消費できる山札枚数。残りプライズ数を残りターン数の見積もりとして使い、
    毎ターンの必須ドロー分を温存する（デッキアウト防止。実ログ85626724が直接の動機）"""
    return my_state.deckCount - len(my_state.prize) - 1


def _deck_consumption(card_id: int, my_state, hand_counts: defaultdict) -> "int | None":
    """このカードを使った場合の山札の正味消費枚数。山札を消費しない札はNone"""
    hand_count = sum(hand_counts.values())
    if card_id == Lillie_Determination:
        draws = 8 if len(my_state.prize) == 6 else 6
        return max(0, draws - (hand_count - 1))
    if card_id == Judge:
        return max(0, 4 - (hand_count - 1))
    if card_id == Hilda:
        return 2
    if card_id in (Pokegear, Ultra_Ball, Poke_Pad):
        return 1
    return None
```

`DECK_SAFETY_THRESHOLD`定数は削除する。

### 2. カードごとの消費枚数（EN_Card_Data.csvのカードテキストで裏取り済み）

| カード | 効果概要 | 消費枚数 | 根拠 |
|---|---|---|---|
| ミツルの思いやり（Lillie's Determination） | 手札を山札に戻し6枚（プライズ残6枚時8枚）ドロー | `max(0, 引く枚数-(手札-1))` | 既存グリムスナールの式を踏襲。手札−1は本札自身を除いて山札へ戻る分 |
| ジャッジマン（Judge） | 両者手札を山札に戻し4枚ドロー | `max(0, 4-(手札-1))` | カードテキスト「shuffles hand into deck, draws 4」 |
| ヒルダ（Hilda） | 進化ポケモン1枚＋エネルギー1枚をサーチ | 2（固定） | 2種類を確実に1枚ずつ持ってくる効果 |
| ポケギア3.0（Pokégear 3.0） | 上7枚を見てサポート1枚を任意で回収 | 1（見つかった前提の最悪ケース） | 「may reveal」だが安全側に倒し常に1消費とみなす |
| ハイパーボール（Ultra Ball） | 手札2枚を捨てて山札からポケモン1枚サーチ | 1（同上） | 手札の2枚は捨て札行きで山札には無関係。山札からの1枚だけが対象 |
| ポケパッド（Poké Pad） | 無印ポケモン1枚サーチ | 1 | グリムスナール側の既存値を踏襲（同カードID） |
| 暗号マニアの解読（Ciphermaniac's Codebreaking） | 山札から2枚選び**山札の一番上に戻す** | **None（ゲート対象外）** | カードテキスト上、手札には来ず山札内で並べ替えるだけなので山札枚数は変化しない |
| ワイの思いやり（Wally's Compassion） | ダメージ回復＋エネルギーを手札に戻す | **None** | 山札に一切触れない効果 |
| 夜のタンカ（Night Stretcher） | 捨て札から回収 | **None** | 山札ではなく捨て札が対象 |

### 3. 組み込み箇所

- `_score_play_option()`の冒頭（`CardType.POKEMON`判定より前）に追加：
  ```python
  consumption = _deck_consumption(card.id, my_state, hand_counts)
  if consumption is not None and consumption > _safe_draws(my_state):
      return -1  # 山札温存
  ```
- `_score_option()`のLunatone特性（ルナサイクル：闘エネ1枚捨てて3枚ドロー）分岐を次のように変更：
  ```python
  if card.id == Lunatone:
      return 8500 if _safe_draws(my_state) >= 3 else -1
  ```
  （現行の`my_state.deckCount >= DECK_SAFETY_THRESHOLD`を置き換え）

いずれも既存関数が既に受け取っている`my_state`・`hand_counts`引数だけで完結する。

### 4. 検証（テスト）

1. 既存の`TestDeckSafetyGate`（ミツルの思いやり×3件）を新しい計算式ベースの期待値に更新
2. 既存の`TestLunaCycleAbilityScore`（ルナサイクル×2件）を新しい`_safe_draws`ベースの期待値に更新
3. 新規テスト追加：ヒルダ・ポケギア3.0・ハイパーボール・ポケパッド・ジャッジマンそれぞれについて「健全時は通常スコア／`_safe_draws`未満に消費量が収まらない時は-1」の境界値テスト
4. 新規の回帰テスト：暗号マニアの解読・ワイの思いやり・夜のタンカは山札残数が極端に少なくてもゲートされない（スコアが通常通り出る）ことを保証する
5. 85626724の実測値（T17時点で山札残9のところポケギア3.0使用→3に急減）を模した盤面で、新しいゲートが機能して-1になることを確認するテストを1件追加
6. `uv run pytest -q`でリポジトリ全体を実行し、回帰がないことを確認

### 5. 実装後のフォロー（次回以降）

- デッキ本体（`decks/lucario_20260621.py`）は変更しないため`output/`のCSV再生成は不要
- 提出用ノートブック`src/sample_notebook/a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb`のセル0（`%%writefile main.py`）を今回の修正後の`main.py`で差し替える必要がある（ユーザー側での提出判断）
- 次にルカリオの新しいバトルログが取れたら、デッキアウト負けが解消したか（今回のような「有利なのに山札切れ」パターンが再発しないか）を確認する

## リスクと備考

- グリムスナール側とは異なり`FieldState`ラッパーを使わない設計のため、`_safe_draws`/`_deck_consumption`はどちらも`my_state`（生のPlayerState）を直接受け取る。将来ルカリオ側でも`FieldState`化する場合はこの2関数のシグネチャ変更が必要になる
- 「ポケギア3.0」「ハイパーボール」の消費量1は「見つかった場合」の最悪ケース想定であり、実際に対象カードが尽きている盤面では過剰に温存的になる可能性があるが、グリムスナール側と同じ簡略化方針を踏襲する（安全側に倒すことを優先）
- 9敗（プライズレース負け）への対策は本設計に含まれない。メガルカリオexミラー戦の2敗を含め、必要であれば別セッションで改めてブレストする
