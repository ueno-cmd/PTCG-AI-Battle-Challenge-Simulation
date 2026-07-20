# ルカリオexデッキ Kaggle提出用notebook自動生成スクリプト設計書

## 背景・目的

2026-07-19、ルカリオexエージェントをKaggleへ提出したところ「Validation Episode failed」で失敗した。原因調査の結果、`submission.tar.gz`内の`main.py`冒頭に`iimport os`という1文字混入のコピペミスが見つかった。既存の`scripts/build_lucario_submission_main.py`は`src/lucario_agent/{constants,combat,main}.py`を結合した単一ファイルのテキストを標準出力するだけで、そのテキストをKaggle Notebook上の`%%writefile main.py`セルへ**手動で貼り付け直す**運用になっており、この手動貼り付け工程がタイポ混入の直接原因だった。

本タスクは、この手動貼り付け工程そのものを排除することが目的である。`scripts/build_lucario_selfcheck_notebook.py`（`main.py`全文をノートブックに埋め込んでビルドする既存の仕組み、セルフチェック用途）と同じパターンを応用し、Kaggle提出用notebookを**完全な`.ipynb`ファイルとして**生成する。ユーザーはKaggleの「Upload Notebook」機能で生成物をファイルごと差し替えるだけでよく、コードをコピー・貼り付けする作業自体がなくなる。

**スコープ**：ルカリオexデッキ限定。他デッキ（グリムスナールex等）への汎用化は別タスクとする（YAGNI）。

## 現状確認（設計時に検証済み）

- `scripts/build_lucario_submission_main.py`の`build()`関数は、`constants.py → combat.py → main.py`の順で結合し、`lucario_agent`内部の相対import文を正規表現で除去する。既に動作実績があり、既存テスト`tests/test_build_lucario_submission_main.py`（4件）で①`def agent(`を含む、②`ast.parse()`で構文エラーが無い、③`from lucario_agent`が残っていない、④`from cg.api import`は残っている、をいずれも検証済み。今回の設計にあたり実際に実行し全件パス・`ast.parse()` OKを再確認した
- `main.py`は`TrainerCardPolicy`（ABC）とその6サブクラス、`combat.py`は`@dataclass AttackPlan`をそれぞれ定義しているが、単一ファイルへの結合はPythonの通常のトップレベル定義として問題なく機能する（結合順序が`combat.py`→`main.py`のため`AttackPlan`は使用前に定義される）
- ローカルには「ユーザーが実際にKaggleへ提出しているノートブックの現物」は存在しない（`.gitignore`で`*.ipynb`除外、`git ls-files`でも該当なし）。`notebooks/samples/a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb`は未追跡ファイルだが、中身は撤去済みのハリテヤマに言及するなど**Kaggle公式オリジナルサンプルのコピー**であり、ユーザーの現行提出物ではない。ただしtarパッケージング処理（`glob.glob('/kaggle/input/**/cg-lib/cg')`、`glob.glob('/kaggle/input/**/deck.csv')`という、データセット名に依存しない汎用globパターン）は参考として流用する

## コンポーネント構成

```
scripts/build_lucario_submission_notebook.py   ← 新規作成
├─ sys.path に scripts/ を追加し build_lucario_submission_main を import（既存 build() を再利用）
├─ validate_syntax(combined: str) -> None       ← ast.parse()。失敗時はエラー内容をstderrへ出しsys.exit(1)
├─ build_notebook(combined: str) -> dict        ← notebook JSON（辞書）を組み立てる純粋関数
│   ├─ md_cell: タイトル「Rule-Based Agent for Mega Lucario ex」＋簡易説明1〜2行（最小限）
│   ├─ code_cell: "%%writefile main.py\n" + combined
│   └─ code_cell: tarパッケージング（cg / deck.csv を汎用globで検出、main.py同梱、実行後main.py削除）
└─ main(): build() → validate_syntax() → build_notebook() → notebooks/submissions/ へ書き出し
```

`build_lucario_submission_main.py`自体は変更しない（`build()`をそのまま呼び出すのみ）。`md_cell`/`code_cell`ヘルパーは`build_lucario_selfcheck_notebook.py`と同型の小さな関数（10行程度）をそのまま複製する。用途が異なる既存の動作実績スクリプトに触る必要がないため、共通モジュールへの抽出は行わない（YAGNI）。

## データフロー

```
src/lucario_agent/{constants,combat,main}.py（既存・テスト済み、変更なし）
  → build_lucario_submission_main.build()（結合＋内部import除去、既存のまま再利用）
  → validate_syntax()（ast.parse。壊れたソースはここで弾く）
  → build_notebook()（3セル構成のnotebook辞書を構築）
  → notebooks/submissions/lucario_agent_submission.ipynb に書き出し
    （*.ipynbは既存の.gitignoreで自動的に非追跡）
  → ユーザーがKaggle上で「Upload Notebook」等によりファイルごと差し替え（貼り付け作業ゼロ）
```

## エラー処理

- `ast.parse()`が`SyntaxError`を投げた場合：エラー内容（行番号含む）をstderrへ出し`sys.exit(1)`。**この場合はnotebookファイルを一切書き出さない**（中途半端な成果物を残さない）
- `src/lucario_agent/*.py`が読めない等の異常は`build()`側の既存動作（例外がそのまま伝播）に委ねる。開発時スクリプトのため特別なハンドリングは追加しない
- 出力先`notebooks/submissions/`ディレクトリが無ければ`mkdir(parents=True, exist_ok=True)`で作成する（`build_lucario_selfcheck_notebook.py`の`notebooks/experiments/`と同じ扱い）

## テスト方針

新規`tests/test_build_lucario_submission_notebook.py`：

- `build_notebook()`に`"def agent(): pass"`のような最小の疑似ソース文字列を渡し、返却されたnotebook辞書の構造を検証する
  - `nbformat == 4`
  - `"%%writefile main.py"`で始まるコードセルが1つ存在し、その中身が渡した疑似ソース文字列を含む
  - tarパッケージング用コードセルが`deck.csv`と`cg`を`glob`で参照している
- `validate_syntax()`にわざと壊れた文字列（例: `"def agent(:"`）を渡し、`SystemExit`が送出されることを確認する（notebookファイルが書き出されないことの裏付け）
- `main()`をsubprocessで実際に実行し、E2Eで以下を確認する
  - `notebooks/submissions/lucario_agent_submission.ipynb`が生成されること
  - 生成物が`json.load()`できる正しいJSONであること
  - `%%writefile main.py`セルの中身に`"from lucario_agent"`が残っていないこと（既存`test_build_lucario_submission_main.py`と同系統のチェック）

既存の`tests/test_build_lucario_submission_main.py`（結合ロジック自体の構文・import検証）と役割が重複しないよう、新規テストは「notebook組み立て部分」に限定する。

`uv run pytest -q`でリポジトリ全体が既存件数＋新規テストで全てPASSすることを確認する（回帰なし）。

## スコープ外（次回以降の検討候補）

- グリムスナールex等、他デッキへの同種スクリプトの汎用化
- Kaggle API（`kaggle kernels push`等）を用いたアップロード自体の自動化（今回はローカルでの`.ipynb`生成までがスコープ。ユーザー側での手動アップロードは残る）
