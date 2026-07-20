# ルカリオexデッキ 居座りボーナス修正＋RETREATのHP温存観点追加 設計書

## 背景・目的

`docs/analyses/20260720-lucario-submission-notebook-first-run-20-games-analysis.md`（notebook自動生成スクリプト初の実地提出、新規20戦分析）で、居座りボーナスバグ（`combat.py`の`calc_attack_plan`にある`i==0`+220・`j==0`+300の固定加点）が9敗中1敗（`87053177`）で明確に関与していたことを確認した。

このバグは`docs/superpowers/specs/2026-07-20-lucario-combat-split-stay-bonus-fix-design.md`（同日の別セッション）で一度「YAGNIで撤回」と判断されていたが、その後の`docs/analyses/20260720-lucario-ex-nullifier-fix-verification-20-games.md`（同日、さらに後のセッション）で実ログ`86898758`から9ターン連続の0ダメージ攻撃という実害が確認され、今回の20戦解析でも別の実ログで再現した。**過去の「実害を再現できず撤回」という判断は、今回の実測で覆っている**。

併せて、同じ2026-07-20の監査（`docs/reviews/20260720-lucario-combat-decision-logic-audit.md`）で発見されていた関連課題「RETREATスコア式へのHP温存観点の追加（`current_plan.attacker >= 1`のときしか交代を評価せず、攻撃可能な控えがいない瀕死アクティブの温存退却が考慮されない。実ログで3プライズ献上の実害を確認済み）」も、居座りボーナスと同じ「今ターンの攻撃が実質無意味なときにどう動くか」という意思決定の一部であるため、ユーザー判断で今回一体で設計する。

ユーザーの狙いは、居座りボーナス修正によってミラー対面（Mega Lucario ex同士）の戦績が改善する可能性を検証すること。加えて、今回の修正・検証結果は将来Q学習/SARSA/DQN等の強化学習導入を検討する際の判断材料にもなりうる（今回はスコープ外、参考情報として記録）。

## スコープ

### 今回やること

1. `calc_attack_plan`の位置ボーナス（`i==0`+220・`j==0`+300）を、そのプランの実ダメージが0の場合は加算しないよう修正
2. `AttackPlan`に`damage: int = -1`フィールドを追加し、選択したプランの実ダメージ量を保持する
3. `_score_retreat_option`に、現在のアクティブがプライズ価値の高い（ex/megaEx）ポケモンで、かつ今ターンの最善プランが実質ノーダメージ（`damage <= 0`）の場合に温存退却を選ばせる分岐を追加する
4. 上記に対応する単体テスト・回帰テストの追加

### 今回やらないこと

- 相手の技火力を推定した精密な脅威判定（アプローチB、ユーザー判断で見送り。効果不十分ならAプラス実測データを踏まえて次回検討）
- 非ex/非megaExポケモンへの温存退却ロジックの適用（プライズ献上コストが低く、確認された実害の対象外のため）
- ソルロックの「弱点・抵抗力を無視する」効果の未実装（既知だが本修正とは無関係）
- Dragapult ex系トゥールボックス対策（今回の20戦解析で新たに浮上した別課題。次点タスクとして保留）

## 設計1：位置ボーナスのダメージ条件付け

### 対象コード（`src/lucario_agent/combat.py`、`calc_attack_plan`内）

現状：

```python
if i == 0:
    score += 220
if j == 0:
    score += 300
score += energy_count
```

修正後：

```python
if damage > 0:
    if i == 0:
        score += 220
    if j == 0:
        score += 300
score += energy_count
```

`damage`はこのループ内で既に`_calc_attack_damage`により計算済みの変数（Crustle/Sylveonの特性で無効化された場合は0になる）をそのまま使う。KO確定プラン（`score = 50000`の上書き）は`damage > 0`が前提の状況でしか発生しないため、KO確定プラン同士の（不要な退却を避ける）タイブレークとしての位置ボーナスの役割は変わらない。影響が出るのは「実ダメージ0のプランが、位置ボーナスだけで実ダメージありのベンチ交代プランを上回ってしまう」ケースのみ。

### `AttackPlan`への`damage`フィールド追加

```python
@dataclass
class AttackPlan:
    attacker:     int  = -1
    target:       int  = -1
    attack_index: int  = -1
    remain_hp:    int  = -1
    energy:       bool = False
    damage:       int  = -1
```

`calc_attack_plan`が最良プランを更新する箇所で`new_plan.damage = damage`を追加する（`remain_hp`の隣に併記）。既存フィールドの意味・デフォルト値は変更しないため、既存テストの`AttackPlan(...)`呼び出しは非破壊。

## 設計2：RETREATのHP温存観点追加

### 対象コード（`src/lucario_agent/combat.py`、`_score_retreat_option`）

現状：

```python
def _score_retreat_option(current_plan: AttackPlan) -> int:
    """OptionType.RETREAT のスコアを返す"""
    return 2000 if current_plan.attacker >= 1 else -1
```

修正後：

```python
def _score_retreat_option(current_plan: AttackPlan, my_active=None, card_table: dict | None = None) -> int:
    """OptionType.RETREAT のスコアを返す"""
    if current_plan.attacker >= 1:
        return 2000  # より良いアタッカーへ切り替える
    if current_plan.damage <= 0 and my_active is not None and card_table is not None:
        data = card_table[my_active.id]
        if data.megaEx or data.ex:
            return 2000  # 無効化等で攻撃が無意味な高価値ポケモンを温存退却する
    return -1
```

`my_active`・`card_table`はデフォルト`None`とし、既存の単一引数呼び出し（`test_negative_when_plan_keeps_current_attacker`等）は非破壊のまま`-1`を返す（`my_active is None`でガードされるため）。

新分岐の条件は次の3つ全てを満たす場合のみ発動する：
- `current_plan.attacker < 1`（今ターンの最善プランがベンチ交代を提案していない＝「今の相手を殴り続ける」か「有効な攻撃が見つからない」状態）
- `current_plan.damage <= 0`（実質ダメージが出ない：デフォルト値-1、またはCrustle/Sylveon等による無効化で0）
- 現在のアクティブがex/megaEx（KOされるとプライズ2〜3枚を献上する高価値ポケモン）

相手の技火力を推定する脅威判定は行わない（アプローチB、今回は見送り）。「今ターン攻撃しても得るものがない」ことだけをトリガーにする現実的な着地点とする。

### `main.py`側の呼び出し変更

```python
case OptionType.RETREAT:
    return _score_retreat_option(
        current_plan,
        my_state.active[0] if my_state.active else None,
        card_table,
    )
```

`_score_option`は既に`my_state`・`card_table`（モジュールグローバル）を参照できるため、追加の引数受け渡しは不要。

## データフロー

`calc_attack_plan`の出力（`AttackPlan`、新たに`damage`を含む）は従来通り`agent()`内のグローバル`plan`に格納され、`_score_option`経由で各オプションのスコアリングに使われる。変更が影響するのはRETREATのスコアリング時のみで、ATTACK/PLAY/CARD等の他のオプションのスコアリングロジックへの影響はない。

## エラーハンドリング

既存のcard_table参照パターン（未知IDは想定しない）を踏襲する。`my_active`が`None`（アクティブ不在）の場合は新分岐をスキップし従来通り`-1`を返す。

## テスト方針（TDD）

1. **位置ボーナスのダメージ条件付け**：既存の`TestCrustleAbilityInteraction`（Crustle対面でOgerpon_exへの切替が選ばれることを確認するテスト群）に、ダメージ0時は位置ボーナスが加算されないことを直接確認する回帰テストを追加する
2. **`AttackPlan.damage`フィールド**：`calc_attack_plan`が返す`AttackPlan.damage`が実際のダメージ値と一致することを確認する単体テスト
3. **RETREATのHP温存分岐**：`TestScoreRetreatOption`に以下を追加
   - `damage<=0`かつ`my_active`がmegaEx/exのとき2000を返す
   - `damage<=0`だが`my_active`が非ex（無印ポケモン）のとき-1を返す
   - `damage>0`のとき（有効な攻撃がある）は新分岐が発火せず-1を返す
   - 既存3テスト（引数なし呼び出し）が非破壊で継続PASSすること
4. **既存テストの回帰確認**：`uv run pytest -q`でリポジトリ全体（既存567件）が全件PASSを維持することを確認する

## 構造面の確認（YAGNI判断）

今回touchする`calc_attack_plan`・`_score_retreat_option`はいずれも既存の条件分岐に1〜2行の条件を追加するのみで、新しい責務や分岐構造を増やすものではない。相手の脅威推定（アプローチB）は明確に別スコープとして見送っており、今回の実測結果次第で改めて検討する。
