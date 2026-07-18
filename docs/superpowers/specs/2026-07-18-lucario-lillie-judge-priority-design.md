# ルカリオexエージェント リーリエの決意「死に札誤認」修正＋Judge対Alakazam強化 設計書

## 背景

`docs/analyses/20260718-lucario-alakazam-deep-dive.md`（Alakazam系対面10戦の深掘り）と
`docs/analyses/20260718-lucario-mirror-deep-dive.md`（ミラー戦8戦の深掘り）で、
`src/lucario_agent/main.py`に以下2件のロジック改善余地が実測で確認された。

1. **`LillieDeterminationPolicy`が「手札にMega Lucario exがあること」を無条件に温存材料と
   見なしている**。`86486986`戦（ミラー戦深掘り調査で再検証・結論再確認済み）では、
   場にRioluが1体もおらずMega Lucario exへの進化手段が無い状況で、手札のMega Lucario exが
   死に札のまま`KEY_POKEMON_IDS`判定に引っかかり、盤面崩壊時に使うべきリーリエの決意が
   温存され続けた。既存の判定（`docs/superpowers/specs/2026-07-17-lucario-trainer-card-policy-design.md`
   で導入済み）は「主要ポケモンが手札にあるか」だけを見ており、「今それを場に出せるか」を
   区別していなかったことが根本原因
2. **Judgeが相手の手札膨張（Alakazam系のドローエンジン）に無反応**。Alakazam系10戦の深掘りで、
   Judge（手札を山に戻して4枚引き直す＝相手の手札を強制リセットできる唯一の対抗札）が
   8敗中5敗で一度もプレイされず、2敗ではハイパーボールの捨て札コストに巻き込まれて
   廃棄されていたことが判明。現行の`JudgePolicy`は自分のエネルギー切れのみを条件にしており、
   相手の脅威度（手札枚数）を一切見ていない

## 今回のスコープ判断（ユーザー合意済み）

- 対象は`LillieDeterminationPolicy`の判定精緻化と`JudgePolicy`の改修＋DISCARD保護追加の2点のみ
- Alakazam・ミラー戦で発見されたその他の課題（ハリテヤマ対策・オーガポンexのアタッカー化・
  Alakazam/Kadabra優先撃破仮説の検証）は本設計のスコープ外（別セッションで検討）
- 75%勝率目標との整合性は「方向性の参考値」として扱い、本設計はその中の一施策と位置づける
  （[[project_ptcg_competition]]の2026-07-18ブレスト参照）

## 設計①：`LillieDeterminationPolicy`の判定精緻化

### 現状の問題

```python
class LillieDeterminationPolicy(TrainerCardPolicy):
    KEY_POKEMON_IDS = (Riolu, Mega_Lucario_ex, Ogerpon_ex, Solrock, Lunatone)

    def play_score(self, ctx: PlayScoringContext) -> int:
        if any(ctx.hand_counts[pid] >= 1 for pid in self.KEY_POKEMON_IDS):
            return -1
        return 3100
```

`Mega_Lucario_ex`はRioluから進化するStage1ポケモンで、手札から直接場に出すことはできない
（`_score_play_option`のPOKEMON分岐でも`Mega_Lucario_ex`はPLAYオプションとして提示されない）。
場にRioluが存在しない状態でMega_Lucario_exだけ手札にあっても、それは進化先が無い死に札であり、
「温存すべき有用な手札」として扱うのは誤り。

Riolu/Ogerpon_ex/Solrock/Lunatoneは手札から直接プレイできる（基本ポケモンとして場に出せる）ため、
これらが手札にあれば従来通り温存材料として扱ってよい。

### 採用する設計

```python
class LillieDeterminationPolicy(TrainerCardPolicy):
    """手札に「今すぐ場へ展開できる」主要ポケモンがあれば温存する。
    Mega Lucario exは進化先のRioluが場にいなければ死に札のため、温存条件から除外する
    （86486986戦：Riolu不在でMega Lucario exのみ手札にあり、誤って温存され続けた事例の修正）"""
    DIRECTLY_PLAYABLE_IDS = (Riolu, Ogerpon_ex, Solrock, Lunatone)

    def play_score(self, ctx: PlayScoringContext) -> int:
        deployable = any(ctx.hand_counts[pid] >= 1 for pid in self.DIRECTLY_PLAYABLE_IDS)
        deployable = deployable or (
            ctx.hand_counts[Mega_Lucario_ex] >= 1 and ctx.field_counts[Riolu] >= 1
        )
        return -1 if deployable else 3100
```

## 設計②：`JudgePolicy`改修（相手手札枚数トリガー＋DISCARD保護）

### 2-1. `op_state`の配線追加

現状`PlayScoringContext`には相手の手札枚数（`op_state.handCount`）が渡っていない。
`_score_option`内で計算済みの`op_state`（371行目付近`op_state = state.players[1 - my_index]`）を
`_score_play_option`経由で`PlayScoringContext`まで伝播させる。

```python
@dataclass
class PlayScoringContext:
    # ...既存フィールド...
    op_hand_count: int = 0  # 追加：相手の手札枚数
```

`_score_play_option`の引数に`op_hand_count`を追加し、呼び出し元の`_score_option`
（`OptionType.PLAY`分岐）から`op_state.handCount`を渡す。

### 2-2. 発動条件の追加

```python
class JudgePolicy(TrainerCardPolicy):
    """相手の手札が閾値以上に膨れている場合は最優先で発動する
    （Alakazam系のPsychic Draw×Rare Candyドローエンジン対策。閾値は暫定値で
    実装時のテストケースを書きながら調整する）"""
    OPPONENT_HAND_THRESHOLD = 10

    def play_score(self, ctx: PlayScoringContext) -> int:
        if ctx.op_hand_count >= self.OPPONENT_HAND_THRESHOLD:
            return 9000
        return 7000 if ctx.hand_counts[Basic_Fighting_Energy] == 0 and not ctx.attacker1 else -1
```

9000点はハイパーボール（6000/5500）やエネルギー切れ時の温存判断より優先されるが、
`OptionType.EVOLVE`（9000+α）や確定KO攻撃より優先されない水準を意図している
（実装時に既存スコアの優先順位表と突き合わせて確認する）。

### 2-3. DISCARD分岐での保護追加

```python
case SelectContext.DISCARD:
    ...
    if card.id in (Riolu, Mega_Lucario_ex, Solrock, Lunatone, Ogerpon_ex, Judge):
        return -100
```

Judgeを要注意ポケモンと同格の`-100`に設定する（ユーザー承認済み：2026-07-17実装の
`Boss_Orders`/`Lillie_Determination`の`-50`より強い保護。Alakazam対面での実質唯一の
対抗札であるため）。

## テスト方針

1. **既存回帰テスト**：`tests/test_lucario_agent.py`の既存テストは全てPASSさせる
   （`_score_play_option`のシグネチャ変更・DISCARD分岐の追加条件のみで、既存の挙動を変えない）
2. **`LillieDeterminationPolicy`（改修）**：
   - Mega Lucario exのみ手札にあり場にRioluがいない → 3100（温存しない）
   - Mega Lucario exのみ手札にあり場にRioluがいる → -1（温存する）
   - Riolu/Ogerpon_ex/Solrock/Lunatoneが手札にある → 従来通り-1（温存する）
   - 何もない → 3100
   - `86486986`戦の開幕手札条件を再現するテストを追加（実ログ再現テスト、既存の
     `TestReplays85626724DeckOutLoss`のパターンを踏襲）
3. **`JudgePolicy`（改修）**：
   - `op_hand_count`が閾値未満 → 従来通りの挙動（エネルギー切れ判定）を維持
   - `op_hand_count`が閾値以上 → 9000を返す（エネルギー切れ条件を満たさなくても最優先）
   - 閾値ちょうど・閾値-1の境界値テスト
4. **DISCARD保護（新規）**：Judgeが要注意ポケモンと同じ`-100`を返すことを確認
5. **最後に`uv run pytest -q`でリポジトリ全体を実行し回帰が無いことを確認**

## スコープ外（今回はやらないこと）

- ハリテヤマ対策（ベンチ構成・SWITCH/TO_ACTIVEスコアリング側の改修）
- オーガポンexのアタッカー化（サブアタッカーとしての優先度見直し）
- Alakazam/Kadabraの能動的優先撃破ロジックの検証・実装
- タイプ相性・プライズ非対称性への対応（デッキ構成変更）
- ジャモライコ側`LillieDeterminationPolicy`への同種修正の横展開
- RETREAT未実装への対応

## 未検証事項・次のステップ

- `OPPONENT_HAND_THRESHOLD`（暫定10）・Judge発動スコア（暫定9000）は実装時のテストケースを
  書きながら適切な値かどうかを再検討する
- 実装完了後、デッキCSV再生成は不要（デッキ構成自体は変更しない）。Kaggle提出用ノートブックの
  `main.py`内容差し替え・再提出はユーザー側で別途実施（[[feedback_scope_out_needs_explicit_confirmation]]
  の教訓に沿い、実装完了後に改めて明示的に確認する）
- ハリテヤマ対策・オーガポンexのアタッカー化・Alakazam優先撃破の検証は、本設計と並行して
  実施予定の「ロジック全体の網羅的バグ洗い出し」の結果と合わせて次の設計対象として検討する
