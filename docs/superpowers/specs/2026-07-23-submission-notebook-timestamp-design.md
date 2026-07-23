# 提出用notebookへのビルド時刻埋め込み 設計書

## 背景・目的

Kaggle提出用notebook（`notebooks/submissions/dragapult_agent_submission.ipynb` /
`lucario_agent_submission.ipynb`）は `scripts/build_*_submission_notebook.py` により
ソース（`src/*_agent/*.py`）から都度自動生成される。生成物自体には「いつビルドされたか」の
情報が一切含まれておらず、Kaggle上でnotebookを開いた際に「最新のソース変更が本当に
反映されているか」をパッと見で判断できない、という課題があった（2026-07-20、ユーザー指摘）。

本タスクでは、notebook冒頭のMarkdownセルにビルド実行時刻を埋め込み、この課題を解消する。

## 要件

- 表示場所：notebook冒頭のMarkdownセル（`NOTE_MD`相当）
- 時刻基準：ビルドスクリプト実行時のローカル時刻（`datetime.now()`）
- 適用範囲：`build_dragapult_submission_notebook.py` / `build_lucario_submission_notebook.py` の両方
  （2スクリプトは完全に同一構造のため、同じ変更を機械的に適用する）

## 設計

### 変更対象ファイル

- `scripts/build_dragapult_submission_notebook.py`
- `scripts/build_lucario_submission_notebook.py`
- `tests/test_build_dragapult_submission_notebook.py`
- `tests/test_build_lucario_submission_notebook.py`

### インターフェース変更

現状、`NOTE_MD`はモジュールレベルの文字列定数であり、`build_notebook(combined: str) -> dict`
がそれをそのまま使っている。これを以下のように変更する。

```python
def note_md(generated_at: datetime) -> str:
    return f"""## Rule-Based Agent for Dragapult ex

生成日時: {generated_at:%Y-%m-%d %H:%M:%S}

Kaggle提出用notebook。`scripts/build_dragapult_submission_notebook.py` により
`src/dragapult_agent/{{constants,main}}.py` から自動生成されている。
手で編集せず、ソース修正後にビルドスクリプトを再実行すること。
"""


def build_notebook(combined: str, generated_at: datetime) -> dict:
    ...
    md_cell("submission-note", note_md(generated_at)),
    ...


def main() -> None:
    combined = submission_builder.build()
    validate_syntax(combined)
    nb = build_notebook(combined, datetime.now())
    ...
```

`generated_at`をデフォルト引数にせず必須パラメータとする。理由：
`datetime.now()`をデフォルト値に置くと関数定義時（モジュールimport時）に評価されてしまい
「実行するたびに違う時刻になる」という意図に反するバグを生みやすいため、
呼び出し側（`main()`・テスト）が明示的に時刻を渡す設計にする。

ルカリオ用スクリプトも同一パターンで変更する（`Lucario ex`表記・パス表記のみ異なる）。

### テスト方針

既存の`TestBuildNotebook`クラスの各テストは`build_notebook("...")`を1引数で呼んでいるため、
固定の`datetime`（例：`datetime(2026, 7, 23, 15, 30, 0)`）を渡す形にシグネチャ変更に追従させる。
その上で、以下を追加する。

- `note_md()`が受け取った`datetime`を`YYYY-MM-DD HH:MM:SS`形式で文字列に含めることを検証するテスト
- `build_notebook()`が生成するMarkdownセルに、渡した`generated_at`のタイムスタンプ文字列が
  含まれることを検証するテスト

`TestMainEndToEnd`（実際に`main()`をサブプロセス実行するテスト）は時刻を固定できないため、
「タイムスタンプらしき行（`生成日時: `というプレフィックス）がMarkdownセルに存在すること」
までを検証し、厳密な時刻一致は求めない。

### 影響範囲

- `notebooks/submissions/*.ipynb`は次回ビルドスクリプト実行時に再生成される
  （既存の運用通り、Kaggleアップロードはユーザー側で実施）
- 生成される`main.py`側のコード内容（アップロードされる実行コード自体）には変更がないため、
  エージェントの挙動には一切影響しない

## スコープ外

- `main.py`側へのコメント埋め込み（ユーザー選定でMarkdownセルのみとする方針）
- git最終更新時刻ベースのタイムスタンプ（ビルド実行時刻を採用）
