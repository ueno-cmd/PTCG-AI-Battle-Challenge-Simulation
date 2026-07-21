# ドラパルトexデッキ MVP実装サマリー

**実装日**: 2026-07-21  
**ブランチ**: `feature/dragapult-ex-mvp`  
**ステータス**: DONE

---

## 概要

Kaggle公式サンプルの「ドラパルトex」エージェント（`notebooks/samples/a-sample-rule-based-agent-dragapult-ex-deck.ipynb`）を`src/dragapult_agent/`へ移植し、ボスの指令の使用法を改善した第2提出デッキの実装を完了しました。実戦で遭遇したドラパルトex使用者との対戦ログ分析（34戦中21敗）から、「進化遅延」より「実行力（ファントムダイブの発動率）」の方が勝敗に強く相関することを確認し、MVPファースト方針で最小構成で提出して実測データを集める計画です。

---

## 実装内容（Tasks 1-5）

### Task 1: デッキ定義とACE SPECテスト

**ファイル作成**:
- `decks/dragapult_20260721.py`: Kaggle公式サンプルと同一の60枚構成
- `tests/test_dragapult_deck.py`: デッキテスト（60枚合計、ACE SPEC 1080が1枚のみ）

**内容**: ドラメシヤ×4、ドロンチ×4、ドラパルトex×3を中核とし、進化をサポートする「ふしぎなアメ」「ラティアスex」、ボスの指令×3、ハイパーボール×4、アカマツ×4など全22種60枚。ACE SPEC（アンフェアスタンプ ID 1080）は1枚制限を機械的に検証。

**テスト結果**: 3/3 PASS

---

### Task 2: カードID定数モジュール

**ファイル作成**:
- `src/dragapult_agent/__init__.py`: パッケージ初期化（空）
- `src/dragapult_agent/constants.py`: カードID定数22個
- `tests/test_dragapult_constants.py`: 定数テスト

**内容**: `Dreepy=119`, `Boss_Orders=1182`など、デッキ内の全カードIDを命名定数として定義。他デッキ（ルカリオex）との最小限の一貫性確保。

**テスト結果**: 3/3 PASS

---

### Task 3: Kaggle公式サンプルの移植

**ファイル作成**:
- `src/dragapult_agent/main.py`: 866行（サンプル854行＋遅延初期化2箇所、実測値。最終レビュー指摘#3で867行から修正）
- `tests/test_dragapult_agent_import.py`: importテスト

**実装内容**:
- Kaggle公式サンプル（`notebooks/samples/a-sample-rule-based-agent-dragapult-ex-deck.ipynb` cell3）の854行をそのまま移植
- `deck.csv`読み込みの遅延初期化（`_load_deck()`新設）
  - **計画通り**: ブリーフで指定されたdeck.csvの遅延初期化を実装
- `card_table`構築の遅延初期化（`_build_card_table()`新設、`src/lucario_agent/main.py`の既存パターンを踏襲）
  - **計画外→スコープ拡大承認**: ブリーフではdeck.csvのみを指定していたが、実装中に`all_card_data()`のトップレベル呼び出しがテスト環境でクラッシュすることが判明。実装エージェントが`NEEDS_CONTEXT`として報告・エスカレーションし、コントローラーが範囲拡大を承認。`src/lucario_agent/main.py`（30〜42行目）の既存パターン`_build_card_table()`を踏襲して解決。

**変更理由（deck.csv）**: テスト環境でのモジュールimport時に`deck.csv`が存在しないため、`_load_deck()`で遅延化。`set_card_counts()`呼び出し時に初回のみ実行。

**変更理由（card_table、計画外対応）**: テスト環境でのモジュールimport時に`cg.sim`（ネイティブライブラリ）の読み込みが失敗するため、`all_card_data()`呼び出しを遅延化。`set_card_counts()`呼び出し時に初回のみ実行。実装中に発見されたため、当初ブリーフに記載されていなかった。

**テスト結果**: 582/582 PASS（回帰なし）

---

### Task 4: インライン定数をimportに置き換え

**ファイル修正**:
- `src/dragapult_agent/main.py`: リファクタリング（22行削除、7行追加）

**内容**: `src/dragapult_agent/main.py`のインライン定義22個の定数（`Dreepy = 119`など）を`dragapult_agent.constants`からのimportに置き換え。純粋リファクタリング、動作不変。

**テスト結果**: 582/582 PASS（回帰なし）

---

### Task 5: ボスの指令の探索的先出しロジック

**ファイル修正**:
- `src/dragapult_agent/main.py`: 関数追加・呼び出し置き換え
- `tests/test_dragapult_agent.py`: 単体テスト4件（新規）

**実装内容**:

```python
BOSS_ORDERS_EXPLORE_EPSILON = 0.28
_dragapult_rng = random.Random()

def _boss_orders_score(has_pull_target: bool, explore_roll: float, epsilon: float) -> int:
    """ボスの指令のスコアリング（3段階判定）"""
    if has_pull_target:
        return 60000  # ベストプランがベンチ狙い：即使用
    elif explore_roll < epsilon:
        return 30000  # 確定的な引き剥がし先なし、でも一定確率で探索的先出し
    else:
        return 0      # 温存
```

**変更理由**: サンプルの元々の動作（`if plan_a.attack > 0`時のみ60000点）から、ルカリオexの`BossOrdersPolicy`と同じ3段階判定へ拡張。確定的な引き剥がし先がなくても、確率`epsilon=0.28`で探索的に先出しすることで、序盤・中盤でも活用機会を増やす。スコア30000は他の高優先度カード（進化40000など）より低く設定。

**テスト結果**: 586/586 PASS（新規4件＋既存582件、回帰なし）

---

## テスト検証結果

### Step 1: 全体テストスイート

```
uv run pytest -q
586 passed in 0.74s
```

**結果**: ✅ 586件全件PASS（既存582件＋新規4件）

### Step 2: デッキビルドスクリプト

```
uv run python scripts/build_deck.py decks/dragapult_20260721.py

合計: 60 枚
出力: /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/output/deck_20260721_123144.csv
```

**結果**: ✅ 合計60枚、CSV出力成功

---

## 設計書への対応関係

本実装は `/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/docs/superpowers/specs/2026-07-21-dragapult-ex-mvp-design.md` の以下項目に対応：

| 設計項目 | Task | 実装内容 | 検証 |
|---------|------|---------|------|
| 1. Kaggle公式サンプル移植 | Task 3 | `src/dragapult_agent/main.py` 854行移植 | `test_dragapult_agent_import.py` |
| 2. カードID定数モジュール | Task 2 | `src/dragapult_agent/constants.py` 22個定数 | `test_dragapult_constants.py` |
| 3. ボスの指令スコアリング改善 | Task 5 | `_boss_orders_score()` 3段階判定 | `test_dragapult_agent.py` 4件 |
| 4. デッキ60枚構成 | Task 1 | `decks/dragapult_20260721.py` 60枚 | `test_dragapult_deck.py` |
| 5. ACE SPEC制限テスト | Task 1 | アンフェアスタンプID 1080が1枚 | `test_dragapult_deck.py` |
| 6. デッキ定義ファイル | Task 1 | `decks/dragapult_20260721.py` | `scripts/build_deck.py`で動作確認 |

---

## 未着手項目（提出後の実測に基づく方針）

### 1. 進化ルートの改修（DEFERRED）

**判断理由**: サンプルは既に「ふしぎなアメ経由」「ドロンチ経由の通常進化」の両方をフォールバックとして実装済み。実戦データから「Kagura勝利13件中9件（69%）は相手がファントムダイブを一度も撃てず、うち6件はドラパルトexへの進化自体が成立していなかった（design doc参照）」ことが分かっているが、この進化遅延は主に手札運による可能性が高く、現時点でロジック上の欠陥と断定できる根拠がない。

**提出後の計画**: 自分のログを [[project_battle_log_parser]] の手法で解析し、以下を確認：
- ドラパルトex進化のタイミング（初発動ターン）
- 進化が遅延したケースでの手札の推移（手札運 vs ロジック判定）
- ファントムダイブ（メイン技 ID 154）の実発動率

ただし、MVPの段階では「ドラパルトexへの進化遅延」は優先度を下げ、実測データを集めた上で原因切り分けから改修を判断する。

### 2. アンフェアスタンプの使いどころ精緻化（DEFERRED）

**実装内容**: サンプルの挙動（確定KO時80000点、それ以外温存80点）をそのまま踏襲。

**未実装の最適化**: 「相手の手札を減らせる」という副次的メリットの評価（ルカリオexの`HandCounterPolicy`的な考え方）。今回スコープ外（ユーザー確認済み）。

**提出後の方針**: 実ログで「アンフェアスタンプの使用タイミング」を観測し、相手の手札サイズとの相関を分析。有意な改善余地がある場合のみ検討。

### 3. その他スコープ外項目

- ジムバトル優勝リスト（`docs/analyses/20260717-...md`）への構成変更：実戦で遭遇した相手と一致しないため、今回はKaggle公式サンプルの構成を採用
- `combat.py`分離やテーブル駆動アタッカー選択などの構造化（YAGNI原則。MVP到達を優先し、実測結果を見てから構造化を検討）
- ボスの指令以外のトレーナーズカード（クラッシュハンマー・タケシのスカウト等）のスコアリング見直し（現時点で明確な問題確認なし）

---

## コミット履歴

| Task | SHA | メッセージ |
|------|-----|----------|
| 1 | f1c8356 | feat(dragapult): デッキ定義とACE SPECテストを追加 |
| 2 | c18518c | feat(dragapult): カードID定数モジュールを追加 |
| 3 | 7382bfc | feat(dragapult): Kaggle公式サンプルを移植（deck.csv・card_table読み込みを遅延初期化） |
| 4 | 74f5f37 | refactor(dragapult): main.py内のカードID定数をconstants.pyからのimportに置き換え |
| 5 | 10d2fde | feat(dragapult): ボスの指令に探索的先出しロジックを追加 |
| 6（本実装） | - | docs(dragapult): MVP実装サマリーを追加 |

---

## 次のステップ

### フェーズ1: Kaggle提出

1. ブランチ`feature/dragapult-ex-mvp`をmainにマージ
2. Kaggleへ新規提出（デッキID: dragapult_20260721、エージェント: `dragapult_agent.main.agent`）
3. 初戦～20戦程度の対戦ログを収集（直後は20戦が数十分で溜まる傾向）

### フェーズ2: ログ分析と仮説検証

`data/competition/EN_Card_Data.csv`ベースの [[project_battle_log_parser]] による分析：

1. **ボスの指令の使用パターン**
   - 総使用回数（サンプル一致組との比較：0～1回/試合が大半）
   - 探索的先出しが実際に効果を発揮したケース数
   - 先出し後のベンチのポケモンが実際にKOされたか

2. **自分側のドラパルトex進化**
   - 初進化ターン（手札の準備完了タイミング）
   - ファントムダイブ（ID 154）の初発動ターン
   - 進化遅延（5ターン以上かかった）ケースの有無と原因

3. **勝率と特徴の相関**
   - ボスの指令使用回数 vs 勝敗
   - 進化タイミング vs 勝敗
   - 相手の進化タイミング vs 自分の勝敗

### フェーズ3: 改修判断

- **勝率が下がった場合**: ロジック上の問題を特定し修正
- **勝率が上がった場合**: アンフェアスタンプ・クラッシュハンマーなど他のカードのスコアリング改善を検討
- **進化遅延が頻繁に発生した場合**: ふしぎなアメの優先度やドロンチの進化条件を精査

次回の改修は実測データに基づき、具体的な根拠を持って実施予定。

---

## Task 3での計画外スコープ拡大

Task 3の実装過程で、ブリーフに記載のないもう一つのモジュールトップレベル副作用（`all_card_data()`呼び出し）によるimport失敗が判明しました。

**詳細**:
- **ブリーフの指定内容**: `deck.csv`読み込みの遅延初期化のみ
- **実装中に発見された問題**: テスト環境の`cg.sim`モック下で`all_card_data()`がクラッシュ
- **エスカレーション**: 実装エージェントが`NEEDS_CONTEXT`として報告
- **コントローラー承認**: 範囲拡大を承認し、`src/lucario_agent/main.py`の既存パターンを踏襲する指示
- **対応内容**: `_build_card_table()`関数の新設と`set_card_counts()`冒頭への呼び出し追加
- **結果**: スコープ外だったが、既存の実証済みパターンに基づき問題解決

このように、計画内容と実装過程での発見を分離して記録することで、将来の類似課題でのプロセス改善に活用できます。

---

## ファイル一覧（新規・変更）

### 新規作成（実装）
- `/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/decks/dragapult_20260721.py`
- `/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/src/dragapult_agent/__init__.py`
- `/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/src/dragapult_agent/constants.py`
- `/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/src/dragapult_agent/main.py`

### 新規作成（テスト）
- `/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/tests/test_dragapult_deck.py`
- `/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/tests/test_dragapult_constants.py`
- `/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/tests/test_dragapult_agent_import.py`
- `/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/tests/test_dragapult_agent.py`

### 新規作成（ドキュメント）
- `/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/docs/implementations/20260721-dragapult-ex-mvp.md`（本ファイル）

---

## 既知リスク・制約事項

### リスク: ノートブック抽出コマンドのインデックス依存

Task 3で使用した抽出コマンド：
```bash
nb['cells'][3]  # cell3からsrc抽出
```

ノートブック構造が変わった場合、間違ったセルを抽出する可能性。対策は実装済み（`assert lines[0] == '%%writefile main.py'`で早期失敗）。

### 制約: ボスの指令のepsilon初期値

現在`BOSS_ORDERS_EXPLORE_EPSILON = 0.28`（ルカリオexと同値）を使用。提出後の実測に基づいてチューニング対象になり得るが、初回提出時点では変更予定なし。

---

**作成日**: 2026-07-21  
**確認者**: Claude Code (自己検証)  
**検証状態**: 全テストPASS、ビルドスクリプト動作確認済み
