# 設計書：デッキCSVビルダー

作成日：2026-06-21

---

## 概要

Xのポストなどで見つけたデッキレシピを元に、NotebookLMが生成したカード名リストから
`deck.csv`（Kaggle提出用）を自動生成するスクリプトを実装する。

### ワークフロー

```
Xポスト（テキスト or 画像）
  ↓
NotebookLM でカード名と枚数を解釈
  ↓
decks/YYYYMMDD_デッキ名.py（カード名リスト）を生成・貼り付け
  ↓
Claude Code でスクリプトと照合・検証
  ↓
scripts/build_deck.py を実行 → output/deck_YYYYMMDD_HHMMSS.csv 生成
  ↓
Kaggle Dataset にアップロード → 提出
```

---

## ファイル構成

```
decks/                          # デッキ定義ファイル群（git管理）
  lucario_20260621.py           # ルカリオデッキの例
  mascarnage_20260620.py        # マスカーニャデッキの例
scripts/
  build_deck.py                 # 変換スクリプト（今回実装）
output/                         # 提出用一時ファイル（.gitignore対象）
  deck_20260621_143022.csv      # タイムスタンプ付き出力例
data/
  EN_Card_Data.csv              # カードマスターデータ（既存）
```

---

## デッキ定義ファイル形式（`decks/*.py`）

NotebookLMへの指示テンプレートとして、以下のPythonフォーマットで出力させる。

```python
DECK = [
    ("Lucario ex", 2),
    ("Mabosstiff ex", 1),
    ("Munkidori", 2),
    ("Basic {F} Energy", 13),
    # ...
]
```

- `(カード名, 枚数)` のタプルのリスト
- カード名は `EN_Card_Data.csv` の `Card Name` 列に合わせる
- 合計60枚でなければスクリプトがエラーを出して停止する

---

## スクリプト仕様（`scripts/build_deck.py`）

### 実行方法

```bash
uv run python scripts/build_deck.py decks/lucario_20260621.py
```

### 処理フロー

1. 引数のデッキ定義ファイルを読み込み、`DECK` リストを取得
2. `data/EN_Card_Data.csv` を読み込み、`カード名 → Card ID` の辞書を構築
3. `DECK` の各エントリを辞書で検索・ID解決
   - 完全一致 → IDを枚数分リストに追加
   - 大文字小文字・スペース正規化後に一致 → 同上（警告を表示）
   - 部分一致候補あり → 候補を表示してスクリプトを停止
   - 一致なし → エラーを表示してスクリプトを停止
4. 合計枚数が60枚でなければエラーを出して停止
5. `output/deck_YYYYMMDD_HHMMSS.csv` を生成

### 出力例（標準出力）

```
✓ Lucario ex        (ID: 673) × 2
✓ Mabosstiff ex     (ID: 674) × 1
✓ Basic {F} Energy  (ID: 6)   × 13
...
合計: 60 枚
出力: output/deck_20260621_143022.csv
```

### エラー例

```
✗ "Lucario EX" → 一致なし
  候補: "Lucario ex" (ID: 673), "Lucario" (ID: 672)
  deck定義のカード名を修正して再実行してください
```

---

## エラー処理方針

| ケース | 動作 |
|--------|------|
| カード名が完全一致 | 正常処理 |
| 大文字小文字・スペースの違いのみ | 警告表示して処理継続 |
| 部分一致候補がある | 候補を表示してスクリプト停止 |
| 候補なし | エラー表示してスクリプト停止 |
| 合計が60枚以外 | エラー表示してスクリプト停止 |

**設計方針：黙って間違えない。** 曖昧なケースは必ず止まってユーザーに確認を求める。

---

## スコープ外

- 日本語カード名からの変換（JP_Card_Data.csv は使用しない）
- デッキ定義のGUI
- カード名の自動補完・インタラクティブな選択UI
- Kaggle APIへの自動アップロード

---

## テスト方針

- 正常系：既存の `data/deck.csv`（ルカリオデッキ）と同一の出力が得られるか検証
- 異常系：存在しないカード名・合計枚数不足・超過をそれぞれテスト
