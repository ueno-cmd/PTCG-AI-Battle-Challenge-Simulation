# 実装サマリー: ルカリオexデッキのリーリエの決意・Judge優先度改修

## 背景

ルカリオexデッキの勝率向上（銀圏安定目標75%の達成）に向け、Alakazam系やハリテヤマなどの環境メタカードへの対策を実装しました。詳細な戦術分析・設計は以下を参照してください：

- **設計書**: `docs/superpowers/specs/2026-07-18-lucario-lillie-judge-priority-design.md`
- **Alakazam/ハリテヤマ対策分析**: `docs/analyses/20260718-lucario-alakazam-deep-dive.md`, `docs/analyses/20260718-lucario-mirror-deep-dive.md`

---

## 実装内容

### Task 1: LillieDeterminationPolicy修正（fix）

**課題**: Mega Lucario exが進化元Rioluなしで手札に単体存在する場合、これを「温存可能な主要ポケモン」と誤認識し、その他の有用な手札まとめて山札に戻していた。

**変更**:
- `KEY_POKEMON_IDS`を`DIRECTLY_PLAYABLE_IDS`に改名し、即座に展開可能なポケモン（Riolu, Ogerpon_ex, Solrock, Lunatone）のみに限定
- Mega Lucario exは「Rioluが場（アクティブまたはベンチ）に存在する場合のみ」温存対象に変更
- 影響ログ: 86363073, 86197001, 86241854, 86295193, 86295949, 86486986 ほか

**ファイル**: `src/lucario_agent/main.py` (`LillieDeterminationPolicy` クラス)

### Task 2: JudgePolicy改修（feat）

**課題**: Alakazam（Psychic Draw×Rare Candy）系ドローエンジンのマッチアップで、相手手札が最大25枚まで膨張しても、Judgeが実際には発動されていない（実測8敗中5敗）。現在のJudge発動スコア（7000）では優先度が不足していた。

**変更**:
- 相手手札が閾値（初期値10枚）以上に膨れている場合、Judgeを最優先（スコア9000）で発動する条件を追加
- `PlayScoringContext`に相手手札枚数`op_hand_count`を追加
- `_score_play_option`関数シグネチャに`op_hand_count`パラメータを追加し、実装元から`op_state.handCount`を伝播

**ファイル**: `src/lucario_agent/main.py` (`JudgePolicy`, `PlayScoringContext`, `_score_play_option`)

### Task 3: DISCARD保護（fix）

**課題**: 手札整理時のDISCARD分岐で、Judgeが誤ってトラッシュ対象に含まれていた。

**変更**:
- `_score_card_option`の DISCARD分岐に Judgeを追加（スコア-100）
- 他の重要なトレーナーと同等の価値で保護

**ファイル**: `src/lucario_agent/main.py` (`_score_card_option`)

---

## テスト結果

```
517 passed in 0.67s
```

リポジトリ全体の回帰テストを実行し、全件PASS。既存機能に対する副作用なし。

---

## コミット範囲

```
beefb28 fix(lucario): JudgeをDISCARD分岐で誤トラッシュから保護
e968246 feat(lucario): Judgeに相手手札枚数トリガーを追加（Alakazam系ドローエンジン対策）
ae8db8b fix(lucario): LillieDeterminationがMega Lucario exの死に札を誤って温存材料にしていた問題を修正
```

親コミット: f36d3f1 (docs: リーリエの決意・Judge改修の実装計画を追加)

---

## 未対応・次回持ち越し

実装はTask 1-3の3コミットで完全に完了しましたが、銀圏安定(75%)到達には以下の追加対応が必要です。優先度順に記載します：

### ① ハリテヤマ対策（高優先）

**スコープ**: 本計画外

- ミラー戦での勝率向上には、ベンチ構成（Solrockの枚数/配置）とSWITCH技の使い方を含む戦略的改修が必要
- 簡単なAIロジック調整では対応不可能（複雑な盤面制御が必要）
- 実装計画書で「スコープ外」と明記済み

### ② オーガポンexのアタッカー化

現在のAIは Mega Lucario exへの依存が強いため、オーガポンexのアタッカー転換ロジックが未実装。

### ③ Alakazam/Kadabra優先撃破仮説の検証

デッキの技構成見直し（例：サイコキネシス採用）による相手ドローエンジン破壊戦術の実測検証が未完了。

### ④ Judgeパラメータの実測チューニング

- `OPPONENT_HAND_THRESHOLD`（現在10枚）の最適値を確認
- Judge発動スコア（現在9000）の実装後の有効性を検証

実装後、実戦ログを分析して調整が必要。

### ⑤ Kaggle提出ノートブックへの反映と再提出

**スコープ**: ユーザー側で別途実施

- ノートブック内のコード（main.py相当部分）への変更反映
- デッキCSV再生成
- Kaggle再提出

**実装完了後、ユーザー側での実施確認が必要です**。

### ⑥ ジャモライコ側LillieDeterminationPolicyへの横展開

ジャモライコデッキにおいても同種の誤認識ロジックが存在する可能性があり、同じパターンの修正を適用する価値あり。実測データで検証が必要。

---

## 結論

本実装により、Alakazam系マッチアップでのJudgeの発動優先度が大幅に改善され、相手ドローエンジンの抑制が期待できます。また、LillieDeterminationの修正により、手札整理における誤判定が解消されました。

Kaggle提出によるスコア向上と、ハリテヤマ対策による銀圏安定化へ向けた基盤が確立されました。
