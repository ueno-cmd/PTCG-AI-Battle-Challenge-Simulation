# 実装サマリー：デッキCSVビルダー

> 実施日: 2026-06-21
> 対象計画: `docs/superpowers/plans/2026-06-21-deck-builder.md`
> 対象設計: `docs/superpowers/specs/2026-06-21-deck-builder-design.md`

---

## 概要

NotebookLM で解読したデッキレシピ（カード名・枚数のリスト）から、Kaggle 提出用 `deck.csv` を自動生成する CLI スクリプトを実装した。

---

## 作成ファイル

| ファイル | 内容 |
|---|---|
| `decks/lucario_20260621.py` | ルカリオデッキ定義（逆引き生成） |
| `src/deck_builder/__init__.py` | パッケージ初期化（空） |
| `src/deck_builder/card_lookup.py` | `build_card_dict` / `find_card_id` |
| `src/deck_builder/deck_loader.py` | `load_deck_def` |
| `src/deck_builder/builder.py` | `write_deck_csv` / 例外クラス |
| `scripts/build_deck.py` | CLI エントリポイント |
| `tests/test_deck_builder.py` | 10 テスト |

---

## ワークフロー

```
Xポスト（テキスト or 画像）
  ↓
NotebookLM でカード名・枚数を解読
  ↓「このフォーマットで：DECK = [("カード名", 枚数), ...]」
decks/デッキ名.py を保存
  ↓
uv run python scripts/build_deck.py decks/デッキ名.py
  ↓
output/deck_YYYYMMDD_HHMMSS.csv → Kaggle Dataset にアップロード
```

---

## 機能

| 機能 | 動作 |
|---|---|
| カード名→ID変換 | `EN_Card_Data.csv` から完全一致で解決 |
| 表記ゆれ検出 | 大文字小文字・スペース違いは `⚠ [表記ゆれ：処理継続]` で警告して継続 |
| 部分一致 | 候補を最大3件表示してスクリプトを停止 |
| 重複カード名 | 最初のIDを保持して `⚠ 重複カード名` 警告 |
| ID直接指定 | `(677, 3)` のように整数IDで名前解決をスキップ可能 |
| バリデーション | 未発見カード・60枚以外はエラーメッセージを出して停止 |
| タイムスタンプ出力 | `output/deck_YYYYMMDD_HHMMSS.csv` に生成 |

---

## 実装上の判断

### アポストロフィ（U+2019）
`EN_Card_Data.csv` は右シングルクォート `'`（U+2019）を使用。デッキ定義ファイルも同じ文字コードで記述する必要がある。

### 重複カード名（Riolu問題）
`Riolu` が CSV に3エントリ存在（ID: 333/PRE・677/MEG・974/SCR）。
- `build_card_dict` は最初のエントリ（333/PRE）を保持して警告を出す
- MEGセットが必要な場合はデッキ定義で `(677, 3)` と整数IDを直接指定する

---

## テスト結果

```
50 passed in 0.03s（既存 41 件 + 今回追加 9 件）
```

| テストクラス/関数 | 件数 | カバー内容 |
|---|---|---|
| `test_build_card_dict_*` | 2 | 辞書構築・重複時の最初ID保持 |
| `test_find_card_id_*` | 4 | 完全一致・大文字小文字・部分一致・一致なし |
| `test_load_deck_def_*` | 1 | .py からの DECK リスト読み込み |
| `test_write_deck_csv_*` | 2 | ファイル生成・タイムスタンプ命名 |

---

## コミット履歴

| SHA | 内容 |
|---|---|
| `c2d3ce8` | ディレクトリ構造・ルカリオデッキ定義を追加 |
| `164dc68` | アポストロフィを U+2019 に修正 |
| `ba75b53` | カード名→ID検索モジュール（TDD） |
| `283c9b5` | デッキ定義ローダー・CSV書き出し（TDD） |
| `d73b147` | CLI スクリプトを追加 |
| `481bebf` | 重複カード名処理・整数ID直接指定に対応 |
| `c516bcc` | 未使用import削除・表記ゆれ警告を追加 |

---

## Kaggle 提出手順

1. `uv run python scripts/build_deck.py decks/lucario_20260621.py` を実行
2. `output/deck_YYYYMMDD_HHMMSS.csv` を Kaggle Dataset にアップロード
3. ノートブック（ptcg-03）を実行して `submission.tar.gz` を生成・提出
