# ジャモライコ vs イオナサンプル 校正ノートブック 設計書

## 背景・目的

ジャモライコエージェント（`src/jamoraiko_agent/main.py`）の実装が完了したが、macOSでは`libcg.so`が動かずローカルで対戦させられない。Kaggleに実際に提出する前に、**現行のイオナ/ナンジャモサンプル（LB 600〜877）に対して勝率で上回るか**を、Kaggle Notebook上の自己対戦で確認する。

グリムスナールの校正実験（`docs/superpowers/specs/2026-07-12-grimmsnarl-hybrid-tuning-design.md`）とは目的が異なる。あちらは「同一ロジックの重み違い（A/B）を何試合で見分けられるか」という**手法の検証**だったが、今回は**別デッキ同士の勝率そのもの**を測る実験である。

## スコープ

### 含めるもの
- ジャモライコ vs イオナサンプルの200試合対戦、累積勝率の推移記録・プロット
- 先手後手を1試合ごとに交代する座席バイアス対策（グリムスナール校正実験と同じ方式）
- 結果のJSON保存

### 含めないもの
- 影武者カウント（同一ロジックのA/B比較ではないため不要）
- 負け試合の盤面ログ保存・質的分析（ユーザー承認により今回は勝率測定のみに限定）
- チューニング対象の数値辞書化（ジャモライコにはまだ存在しない。将来の別プロジェクト）

## 技術設計

### ファイル
- 生成スクリプト: `scripts/build_jamoraiko_vs_iono_notebook.py`（既存`build_grimmsnarl_calibration_notebook.py`と同じビルド方式：参考ノートブックからcgランタイム起動セルをコピーし、エージェント本体・対戦ハーネス等のセルを合成してノートブックJSONを書き出す）
- 出力: `src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`（`.gitignore`対象のためコミットなし）

### エージェントの名前空間分離

`src/jamoraiko_agent/main.py`と、既存イオナサンプル（`src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb`の`%%writefile main.py`セル全文）は、どちらも`agent()`関数・`card_table`等の同名グローバル変数を持つため、同じセルに並べると衝突する。

対策：`types.ModuleType`で別々の名前空間を作り、`exec()`でそれぞれのソースコードを別モジュールとして評価してから`.agent`属性を取り出す。

```python
import types

def load_agent_module(name: str, source: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    exec(compile(source, name, "exec"), mod.__dict__)
    return mod

jamoraiko_mod = load_agent_module("jamoraiko_agent_module", JAMORAIKO_SOURCE)
iono_mod = load_agent_module("iono_agent_module", IONO_SOURCE)
```

`JAMORAIKO_SOURCE`はビルド時に`src/jamoraiko_agent/main.py`の全文を埋め込む。`IONO_SOURCE`は`src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb`の`cell id="4c4dd070"`（`source`は改行込みの単一文字列）を読み込み、先頭行`%%writefile main.py`（Jupyter magicでPythonとしてexec不可）を取り除いた残りを埋め込む。両方ともビルドスクリプトが自動で読み込む。手で編集しない。

### デッキの定数埋め込み

Kaggleでは1データセットしかアップロードできない制約があるため、**両デッキとも60枚のカードIDリストをノートブックに直接埋め込む**（globでのデータセット読み込みには依存しない）。

- ジャモライコ側：`decks/jamoraiko_20260713.py`の`DECK`（`(card_id, count)`タプルリスト）をビルド時に展開し、60個のintリストとして埋め込む
- イオナサンプル側：`a-sample-rule-based-agent-iono-s-deck.ipynb`の決め打ちデッキ構成（Iono_Voltorb×3, Iono_Tadbulb×3, Iono_Bellibolt_ex×3, Iono_Wattrel×3, Iono_Kilowattrel×3, Buddy_Buddy_Poffin×3, Night_Stretcher×2, Max_Rod×1, Energy_Retrieval×1, Ultra_Ball×3, Poke_Pad×2, Lillie_Determination×4, Canari×4, Levincia×3, Boss_Orders×2, Basic_Lightning_Energy×20＝60枚）を同様に定数として埋め込む

### 対戦ハーネス

グリムスナール校正実験の`play_game`/`run_series`をそのまま流用（`cg.game`の`battle_start`/`battle_select`/`battle_finish`を使用）。影武者カウント関連（`make_shadow_agent`等）は今回不要のため含めない。

```python
def play_game(agent_a, agent_b, deck_a, deck_b, max_steps=700) -> int:
    """1試合対戦する。agent_a勝ち=+1 / 負け=-1 / 引き分け・打ち切り=0"""
    # グリムスナール校正実験と同一実装
```

`run_series`も同様に流用し、`GAMES = 200`、`CHECKPOINTS = [10, 20, 40, 80, 120, 160, 200]`をデフォルトとする。

### 実行

```python
series = run_series(
    lambda obs: jamoraiko_mod.agent(obs),
    lambda obs: iono_mod.agent(obs),
    GAMES, "Jamoraiko vs Iono Sample",
    deck_a=JAMORAIKO_DECK, deck_b=IONO_DECK,
)
```

### 出力
- `calibration_results.json`（`/kaggle/working`、対戦結果・試合数・所要時間）
- matplotlib（Kaggleでplotlyが表示されない実績があるため）で累積勝率の推移をプロット。50%ラインを基準線として描画

## テスト方針

このノートブックはKaggle実行専用（`cg`ライブラリがローカルで動かないため）。生成スクリプト自体はローカルで実行可能なので、以下を確認する：
- `scripts/build_jamoraiko_vs_iono_notebook.py`を実行してノートブックJSONが生成されること
- 生成されたノートブックのセル内に`JAMORAIKO_SOURCE`・`IONO_SOURCE`・両デッキの60枚リストが正しく埋め込まれていること（文字列検証）
- 既存のグリムスナール系ビルドスクリプトと同様、pytestでの自動テストは対象外（生成物の実行確認はKaggle上でユーザーが行う）

## 未解決・次回以降の検討事項
- 負け試合の盤面ログ保存・質的分析（今回は勝率のみ。必要になれば別途追加）
- 実行後、実際の勝率次第でチューニング対象の洗い出しに進むかはユーザー判断
