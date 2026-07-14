# ジャモライコエージェント EnergyPolicyクラス導入 設計書

## 背景

前回の修正（`docs/superpowers/specs/2026-07-14-jamoraiko-energy-logic-fix-design.md`、実装済み・マージ済み）で勝率は0.015→0.045（200試合中3勝→9勝）に改善したが、依然として壊滅的な水準。ユーザーが新たに取得・ダウンロードした`data/jamoraiko_vs_iono_turn_log.json`（10試合分の手番選択ログ）をsystematic-debuggingスキルで解析した結果、以下が判明した。

### 良かった点（前回修正の効果を実測確認）
- タイカイデンの自滅ループ：10試合中**0回**（完全解消）
- MAIN判断でATTACKが提示される割合：10.3%→**29.6%**
- タケルライコexの「きょくらいごう」（本命技、attackId=72）が実際に**5回発動**（前回は一度もエネルギーが1枚を超えず実質未発動だった）

### 新たに判明したバグ（前回の設計上の誤り）

前回の設計書は、「エネルギーつけかえ」（Energy Switch）が`SelectContext.DETACH_FROM`（供給元選択）→`ATTACH_FROM`（宛先選択）という2ステップを通ると推測して実装した。しかし実ログを解析した結果、実際の流れは以下だと判明した：

1. `SelectContext.SWITCH_ENERGY_CARD`（`OptionType.ENERGY_CARD`、SelectType.ATTACHED_CARD）＝**どの添付エネルギーカードを動かすか**を選択
2. `SelectContext.ATTACH_FROM`（`OptionType.CARD`）＝**宛先ポケモン**を選択（api.pyのコメント通り。前回実装は正しかった）

`DETACH_FROM`は10試合を通じて**一度も出現しなかった**（前回実装した`_score_card_option`の`DETACH_FROM`分岐・`_score_energy_switch_source_candidate`は空振りコードだったと確認）。

一方、`_score_option`の`match`文には**`OptionType.ENERGY_CARD`のケースが一つも実装されておらず**、常にスコア0にフォールバックしていた。実際に実ログで確認したところ、序盤（ターン5）で「タケルライコex自身の唯一のエネルギーを供給元として選び、必要としていないベンチのポケモンへ動かしてしまう」という、狙いと真逆の事故が起きていた。

さらに、「きょくらいごう」の追加ダメージ用エネルギー破棄も`SelectContext.DISCARD_ENERGY_CARD`（`OptionType.ENERGY_CARD`）を通ることが判明した。前回実装した`OptionType.ENERGY`（`SelectContext.DISCARD_ENERGY`想定）は誤ったコンテキスト・型を対象にしており、これも空振りコードだった。

これは`OptionType.CARD`丸ごと未実装（勝率0.015の直接原因）→`OptionType.ENERGY`空振り→今回の`OptionType.ENERGY_CARD`未実装、と3回連続で同じ「`match`文のケース漏れ」が発生している（[[feedback_agent_dispatch_coverage]]参照）。

### ユーザーからの追加要望

上記の修正を進める中で、ユーザーから「1セルノートとはいえ、関数手続き型のままだとエネルギー関連のロジックが複数の関数・`match`文に分散し続けるのではないか」という懸念が示された。ブレストの結果、**今回のバグ修正範囲（エネルギー関連のスコアリング）に限定**して、散らばっている自由関数を1つのクラスに集約する方針で合意した。

## 設計

### `EnergyPolicy`クラスの新設

現在`src/jamoraiko_agent/main.py`に散らばっているエネルギー関連の自由関数を、1つのクラスにまとめる。

```python
class EnergyPolicy:
    """雷/闘エネルギーの手張り優先度、エネルギーつけかえの運用、
    きょくらいごうの追加ダメージ用エネルギー破棄を1箇所に集約する。
    OptionType.ATTACH / PLAY / ENERGY_CARD という複数のSelectContextに
    またがるロジックをここに閉じ込め、散逸を防ぐ。
    """

    SURPLUS_THRESHOLD = {
        Iono_Bellibolt_ex: 4,   # Thunderous Boltのenergy_required
        Iono_Kilowattrel: 3,    # Mach Boltのenergy_required
    }

    def attach_priority(self, pokemon: Pokemon, active: bool) -> int:
        """OptionType.ATTACH（基本雷エネルギーの手張り）優先度。
        既存energy_score()と完全に同じロジック（Voltorb/Bellibolt_ex/Kilowattrel/Raging_Bolt_exの分岐）"""

    def find_surplus_source(self, my_state) -> "Pokemon | None":
        """エネルギーつけかえの供給元にできる、自分自身の攻撃条件を満たし
        雷エネルギーに余剰があるナンジャモポケモンを1体返す（無ければNone）。
        既存_find_energy_switch_source()と同じロジック"""

    def needs_lightning(self, my_state) -> bool:
        """場のタケルライコexが雷エネルギーを1枚も持っていないか。
        既存_raging_bolt_ex_needs_lightning()と同じロジック"""

    def has_growth_path(self, fs: FieldState, my_state) -> bool:
        """タケルライコexがまだきょくらいごう着地に伸びる見込みがあるか。
        既存_raging_bolt_ex_has_growth_path()と同じロジック。calc_attack_planから呼ばれる"""

    def play_score(self, my_state) -> int:
        """OptionType.PLAY（エネルギーつけかえを使うか）のスコア。
        既存_score_play_optionのEnergy_Switch分岐と同じロジック（7500 or 200）"""

    def switch_destination_score(self, card) -> int:
        """SelectContext.ATTACH_FROM（付け直す先のポケモン）のスコア。
        既存_score_energy_switch_destination_candidate()と同じロジック"""

    def switch_source_score(self, obs, o, my_index: int) -> int:
        """【新規実装】SelectContext.SWITCH_ENERGY_CARD（動かす元のエネルギー）のスコア。
        get_card(obs, o.area, o.index, o.playerIndex)でエネルギーの持ち主を取得し、
        タケルライコex自身なら-1000（絶対に選ばせない）、
        SURPLUS_THRESHOLD以上のナンジャモポケモンなら+500、未満なら-500、
        それ以外は0（旧_score_energy_switch_source_candidateのロジックをDETACH_FROMから
        SWITCH_ENERGY_CARDへ配線し直したもの）"""

    def discard_for_damage_score(self) -> int:
        """【新規実装】SelectContext.DISCARD_ENERGY_CARD（きょくらいごうの追加ダメージ用破棄）。
        貪欲方針を維持：常に9000（提示されたエネルギーは常に破棄する）"""


ENERGY_POLICY = EnergyPolicy()  # モジュールレベルで1個だけ生成し、状態を持たない
```

### `_score_option`への配線

```python
case OptionType.ATTACH:
    return _score_attach_option(obs, o, my_index)   # 内部でENERGY_POLICY.attach_priority()を呼ぶよう修正
...
case OptionType.ENERGY_CARD:
    return _score_energy_card_option(obs, o, context, my_index)   # 新規ディスパッチ関数
```

`_score_energy_card_option`は既存の`_score_card_option`（`OptionType.CARD`用ディスパッチ）と同じパターンで新設する：

```python
def _score_energy_card_option(obs, o, context, my_index: int) -> int:
    """OptionType.ENERGY_CARD のスコアをコンテキスト別に返す"""
    match context:
        case SelectContext.SWITCH_ENERGY_CARD:
            return ENERGY_POLICY.switch_source_score(obs, o, my_index)
        case SelectContext.DISCARD_ENERGY_CARD:
            return ENERGY_POLICY.discard_for_damage_score()
        case _:
            return 0
```

### 削除するデッドコード

- `_score_card_option`の`case SelectContext.DETACH_FROM:`分岐、および`_score_energy_switch_source_candidate`関数（実戦で一度も通らないと確認済み）
- `_score_option`の`case OptionType.ENERGY: return 9000`（実際のコンテキストは`ENERGY_CARD`であり空振りだったため）
- 旧`energy_score`・`_find_energy_switch_source`・`_raging_bolt_ex_needs_lightning`・`_raging_bolt_ex_has_growth_path`・`_score_energy_switch_destination_candidate`の各自由関数（`EnergyPolicy`のメソッドに統合されるため）

### 呼び出し側の変更

- `_score_attach_option`：雷エネルギー分岐を`ENERGY_POLICY.attach_priority(...)`呼び出しに変更
- `_score_play_option`：Energy_Switchの分岐を`ENERGY_POLICY.play_score(my_state)`呼び出しに変更
- `_score_card_option`：`ATTACH_FROM`分岐を`ENERGY_POLICY.switch_destination_score(card)`呼び出しに変更
- `calc_attack_plan`：Burst Roar抑制条件を`ENERGY_POLICY.has_growth_path(fs, my_state)`呼び出しに変更

## テスト方針

- `tests/test_jamoraiko_agent.py`の`TestEnergyScore`・`TestFindEnergySwitchSource`・`TestRagingBoltExNeedsLightning`等、旧自由関数を直接呼んでいたテストは`EnergyPolicy`のインスタンスメソッド呼び出しに書き換える（内部実装のリファクタリングであり後方互換シムは作らない）
- 新規：`switch_source_score`の単体テスト（タケルライコex自身のエネルギーは-1000、余剰ありのナンジャモポケモンは+500、余剰なしは-500、無関係なポケモンは0）
- 新規：`discard_for_damage_score`の単体テスト（常に9000）
- 新規：`_score_energy_card_option`ディスパッチのテスト（`SWITCH_ENERGY_CARD`/`DISCARD_ENERGY_CARD`それぞれが正しいメソッドに振り分けられること）
- `_score_option`の`OptionType.ENERGY_CARD`ケースのテスト
- 既存の491件のテストスイート全体の回帰確認（`uv run pytest -q`）

## スコープ外（今回はやらないこと）

- `main.py`全体のアーキテクチャ見直し（Attacker/PokemonLine等、他の部分のクラス化）は対象外。今回はエネルギー関連のスコアリングのみに限定する
- `DISCARD_ENERGY_CARD`が将来的に他のカード効果（きょくらいごう以外）でも使われる可能性への対応は、実際にそのようなカードが採用されるまで見送る
- デッキ構成・アタッカー選定ロジックの変更は行わない（前回修正の効果測定が目的であり、今回のスコープはバグ修正のみ）

## 未検証事項・次のステップ

- `switch_source_score`が実戦でタケルライコex自身のエネルギーを避け、余剰のあるナンジャモポケモンを正しく選べるようになったかは、ローカルでは`libcg.so`が動かないためKaggle実測でしか確認できない
- 修正後も勝率が改善しない場合、`ATTACH_FROM`/`ATTACH_TO`がハラバリーexの特性「エレキストリーマー」とエネルギーつけかえの両方から共有されている点（今回のログ解析で判明）が意図しない競合を起こしていないか、さらなるログ解析が必要になる可能性がある
