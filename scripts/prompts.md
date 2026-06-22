# プロンプト集

このファイルは外部AIツール（NotebookLM など）に貼るプロンプトをまとめたものです。

---

## NotebookLM：デッキID辞書の生成

**ソース：** `data/EN_Card_Data.csv` または `data/Card_ID List_EN.pdf` をアップロード

```
以下の条件でカード名とCard IDのPython辞書を作ってください。

【目的】
ドラパルトexデッキ（Dragapult ex deck）用のデッキCSVを生成するために使います。
Card ID → deck.csv の card_id 列に入ります。

【抽出してほしいカード】
ポケモン:
- Dreepy（ドロンチ）
- Drakloak（ドロンズ）
- Dragapult ex（ドラパルトex）

エネルギー:
- Basic {P} Energy（サイキックエネルギー）
- Basic {C} Energy（コロモスエネルギー / 無色）

トレーナーカード（一般的なものを含めて）:
- Iono（イキリンコ）
- Boss's Orders（アカギのカリスマ）
- Arven（ハマナのレシピ）
- Ultra Ball（ハイパーボール）
- Rare Candy（ふしぎなアメ）
- Nest Ball（モンスターボール系）
- Super Rod（なんでもなおし）
- Night Stretcher（ナイトストレッチャー）
- Buddy-Buddy Poffin（フレンドバフンのレシピ）

【出力形式】
以下のPython辞書形式で出力してください：

DRAGAPULT_DECK_CARDS = {
    "Dreepy": <Card ID>,
    "Drakloak": <Card ID>,
    ...
}

カードが見つからない場合は # NOT FOUND とコメントしてください。
```

**確認手順：**
結果を `src/deck_builder/card_lookup.py` の `build_card_dict()` と突き合わせて一致を確認する。
