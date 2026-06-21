# 実装サマリー：Task 2〜5 + カードプール確認

**作業日**: 2026-06-20  
**計画ファイル**: `docs/superpowers/plans/2026-06-20-mascarnage-agent.md`

---

## 実施内容

### Task 2: テスト基盤（conftest.py）
- `tests/conftest.py` 作成
- `cg.sim` / `cg.game` を `sys.modules` でモック（libcg.so 非実行環境対応）
- ファクトリ関数 3点: `make_pokemon()` / `make_player_state()` / `make_main_obs()`

### Task 3: main.py骨格 + ヘルパー関数（TDD）
- `src/mascarnage_agent/main.py` 作成
- ヘルパー関数: `get_card()` / `no_damage_counter()` / `prize_count()`
- `agent()` 骨格（暫定ランダム返却）
- `tests/test_helpers.py`（5件）作成・全パス

### Task 4: ブーケマジックスコアリング（TDD）
- `bouquet_magic_score()` を main.py に追加
- `tests/test_scoring.py`（4件）作成・全パス

### Task 5: agent()スコアリング本体（TDD）
- `agent()` のスコアリングを実装（優先度付き降順ソート方式）
- `tests/test_agent.py`（3件）作成・全パス
- `_load_cards()` をテスト内でモック（`all_card_data()` が libcg.so を呼ぶため）

### 全テスト結果
```
tests/test_agent.py   3/3 PASS
tests/test_helpers.py 5/5 PASS
tests/test_scoring.py 4/4 PASS
合計: 12/12 PASS
```

---

## カードプール確認結果

### マスカーニャexライン → **カードプールに存在しない**

`EN_Card_Data.csv` を確認したところ、**Meowscarada ex（マスカーニャex）は未収録**。

| カード名 | 和名 | Card ID | 状態 |
|----------|------|---------|------|
| Sprigatito | ニャオハ | 922 | 非ex通常版のみ |
| Floragato | ニャローテ | 923 | 非ex通常版のみ |
| Meowscarada | マスカーニャ | 924 | 非ex通常版のみ（特性あり） |
| Meowscarada ex | マスカーニャex | **なし** | **カードプール未収録** |

**結論: ドラパルトexデッキにフォールバック確定。**

### ドラパルトexライン → 存在確認済み ✅

| カード名 | 和名 | Card ID | コード定数 |
|----------|------|---------|-----------|
| Dreepy | ドレディア | 119 | `DREEPY = 119` ✅ |
| Drakloak | ドロンチ | 120 | `DRAKLOAK = 120` ✅ |
| Dragapult ex | ドラパルトex | 121 | `DRAGAPULT_EX = 121` ✅ |

ドラパルトexの技「Phantom Dive」: 200ダメ + 相手ベンチに6枚ダメカン分散配布。

---

## コード修正が必要な箇所（Task 6実施前に対応）

### `_IMMUNE_IDS` の誤記

`src/mascarnage_agent/main.py` の免疫IDリストに2点の誤りあり：

| コード記載 | コメント | 実際のカード | 対処 |
|-----------|----------|-------------|------|
| ID 199 | 「エンペルトex」 | **Scatterbug（コンテッキー）** | → 835に修正 |
| ID 203 | 「スケルジ」 | **Skeledirge（スケルダイル系炎Stage2）** | → コメント修正 or 要確認 |

**正しいエンペルトex**: Card ID **835**（Emperor's Stance: 攻撃の効果を無効化、ダメカンは別途要確認）  
**Skeledirge (203)**: Unaware特性（攻撃の効果無効）→ダメカンは置ける可能性あり。除外検討。

修正案:
```python
_IMMUNE_IDS = frozenset({
    28,   # ポットデス（Poltchageist）- ベンチで全ダメ無効
    207,  # ミロカロスex - テラポケモンからの攻撃ダメ無効
    362,  # ミスティのコイキング - ベンチで全ダメ無効
    1136, # むかしのふたのかせき - 効果無効
    # 835, # エンペルトex - 効果無効（ダメカン可否要確認）
})
```

---

## 次のステップ（Task 6）

1. `_IMMUNE_IDS` の ID修正（199→削除、835→追加検討）
2. カードID定数の更新（マスカーニャex未収録のため、定数 `MASCARNAGE_EX = 0` を削除 or コメントアウト）
3. ドラパルトexデッキの `deck.csv`（60枚）作成
4. Kaggle提出準備（サンプルノートブック5本の動作確認後）

---

## ファイルマップ（現状）

```
src/mascarnage_agent/
  __init__.py
  main.py          ← エージェント本体（Kaggle貼り付け用）
tests/
  __init__.py
  conftest.py      ← cg.simモック + 3ファクトリ
  test_helpers.py  ← ヘルパー関数テスト（5件）
  test_scoring.py  ← ブーケマジックスコアリングテスト（4件）
  test_agent.py    ← エージェント統合テスト（3件）
pyproject.toml
uv.lock
```
