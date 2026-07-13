# ジャモライコエージェント OptionType.CARD スコアリング追加 設計書

- 日付: 2026-07-13
- 対象: `src/jamoraiko_agent/main.py`
- 前提分析: 校正ノートブック（`src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`）の実行結果（`data/jamoraiko_vs_iono_results.json`、200試合中3勝197敗＝勝率0.015）
- 関連: `docs/superpowers/plans/2026-07-13-jamoraiko-agent.md`（今回の欠落を生んだ元の実装計画）

## 背景

ジャモライコエージェントをイオナサンプルと200試合対戦させた校正実験で、勝率0.015という壊滅的な結果になった。原因を調査したところ、`_score_option`の`match`文に`OptionType.CARD`のケースが一つも実装されておらず、`case _: return 0`のフォールバックに落ちていたことが判明した。

`OptionType.CARD`は以下のような、ゲーム中の極めて多くの意思決定に使われる型である：

- `SETUP_ACTIVE_POKEMON`：初期アクティブポケモンの選択
- `SWITCH` / `TO_ACTIVE`：交代先の選択（自分の強制昇格・任意交代、および相手への「ボスの指令」）
- `TO_HAND`：サーチ効果でのカード選択（夜のタンカ・つりざおMAX・エネルギー回収・エネルギー転送・ハイパーボール・カナリィ・ハッコウシティ）
- `TO_BENCH`：なかよしポフィンによるデッキからベンチへの直接サーチ
- `DISCARD`：コスト用の破棄選択（ハイパーボール・カナリィ）

これら全てが一律スコア0になると、実質「エンジンが提示した順番の先頭を機械的に選ぶだけ」になり、攻撃できないポケモンを場に出す・キーカードをサーチできない・不要なカードを優先破棄する等の事故が毎試合起きていたと推定される。

原因は実装計画（`docs/superpowers/plans/2026-07-13-jamoraiko-agent.md`）作成時点のスコープ漏れ。ローカルでは`libcg.so`が動かず実機対戦できないため、モックを使った単体テストは「書いたロジックが正しいか」しか検証できず、「必要なロジックを書き忘れていないか」は検証できなかった。詳細な教訓は`feedback_agent_dispatch_coverage`メモリを参照。

## スコープ

以下6つのコンテキストを対象とする（ユーザー承認済み）：

- `SETUP_ACTIVE_POKEMON`
- `SWITCH` / `TO_ACTIVE`
- `TO_HAND`
- `TO_BENCH`（なかよしポフィンがこのデッキの核となるサーチ札〈3枚採用〉のため対象に含める）
- `DISCARD`

**スコープ外**（今回は対応しない）：
- `SETUP_BENCH_POKEMON`：参考実装（イオナサンプル・`lucario_agent`）ともに特別扱いなし（デフォルト0点）。今回もこれに合わせる
- `ATTACH_FROM`：ジャモライコのデッキ内カードで発生するケースが無い（ハラバリーexの特性「エレキストリーマー」は既存の`OptionType.ATTACH`経路で処理済み）ため未実装のまま

実装スタイルは**データ駆動型（テーブル）**を新規設計する。既存の`ATTACKERS`テーブルと同じ思想で、`if/elif`の乱立を避け、CLAUDE.mdのif文設計ガイドライン（ネスト2階層まで・if-elif3分岐以上はdict化検討）にも沿う。

## カードデータ調査（裏取り済み）

`data/card_data_merged.csv`でHP・効果テキストを確認した。

| Card ID | 名前 | HP | 進化段階 |
|---|---|---|---|
| 63 | タケルライコex | 240 | たね |
| 265 | ナンジャモのビリリダマ | 70 | たね |
| 268 | ナンジャモのズピカ | 60 | たね |
| 269 | ナンジャモのハラバリーex | 280 | 1進化（ズピカから） |
| 270 | ナンジャモのカイデン | 60 | たね |
| 271 | ナンジャモのタイカイデン | 120 | 1進化（カイデンから） |

なかよしポフィンの効果テキストは「HPが70以下の【たね】ポケモンを2枚まで」なので、候補はビリリダマ(70)・ズピカ(60)・カイデン(60)の3種に自然に絞られる（タケルライコexは240HPのためエンジン側で候補から除外される）。TO_BENCH側で追加のHPフィルタ実装は不要。

サーチ系カードの効果テキスト（一部）：
- 夜のタンカ・つりざおMAX・エネルギー回収：捨て札からポケモンまたは**基本エネルギー（種類指定なし）**をサーチ
- エネルギー転送：山札から**基本エネルギー（種類指定なし）**を1枚サーチ
- ハッコウシティ：捨て札から**基本【雷】エネルギー**を2枚までサーチ（雷限定）

「基本エネルギー」が種類指定なしのカードでは、雷・闘の両方が候補になりうるため、TO_HANDのスコアリングで両者の優先度を作り分ける必要がある。

## 設計

### 1. アーキテクチャ

```python
@dataclass(frozen=True)
class PokemonLine:
    id: int
    pre_evo_id: int | None = None    # 進化前のID（自身が進化ポケモンの場合）
    max_field_copies: int = 1        # 場+手札に置きたい上限（これ以上のサーチ優先度は下げる）
    setup_active_priority: int = 0   # 初期アクティブ選択時の基礎優先度

POKEMON_LINES: dict[int, PokemonLine] = {
    Iono_Voltorb:      PokemonLine(id=Iono_Voltorb, max_field_copies=2, setup_active_priority=300),
    Iono_Tadbulb:      PokemonLine(id=Iono_Tadbulb, max_field_copies=1, setup_active_priority=50),
    Iono_Bellibolt_ex: PokemonLine(id=Iono_Bellibolt_ex, pre_evo_id=Iono_Tadbulb, max_field_copies=1),
    Iono_Wattrel:      PokemonLine(id=Iono_Wattrel, max_field_copies=1, setup_active_priority=50),
    Iono_Kilowattrel:  PokemonLine(id=Iono_Kilowattrel, pre_evo_id=Iono_Wattrel, max_field_copies=1),
    Raging_Bolt_ex:    PokemonLine(id=Raging_Bolt_ex, max_field_copies=1, setup_active_priority=200),
}
```

`_score_option`の`match`文に`case OptionType.CARD:`を追加し、新設する`_score_card_option(obs, o, context, my_index, state, my_state, op_state, fs, plan) -> int`を呼ぶ。この関数はさらに`match context:`で以下の専用ヘルパーへディスパッチする。

### 2. SETUP_ACTIVE_POKEMON

```python
def _score_setup_active(card_id: int) -> int:
    line = POKEMON_LINES.get(card_id)
    return line.setup_active_priority if line else 0
```

候補は基本ポケモンのみ。ビリリダマ（即攻撃可能な20+ダメ技を持つ）を最優先(300)、タケルライコex（240HPの壁役、ただし攻撃には闘エネが必要ですぐには打点が出ない）を次点(200)、ズピカ/カイデン（60HPの脆い中継ぎで単体では攻撃技を持たない）を最低(50)に設定する。

### 3. SWITCH / TO_ACTIVE

```python
def _is_attack_ready(card_id: int, energy_count: int, fighting_count: int) -> bool:
    """このポケモンが今すぐ攻撃可能な技を持つか（ATTACKERSテーブルの再利用）"""
    for atk in ATTACKERS:
        if atk.id != card_id or atk.is_utility:
            continue
        if energy_count < atk.energy_required:
            continue
        if atk.requires_fighting and fighting_count < 1:
            continue
        return True
    return False


def _score_switch_target(card, o, my_index: int, plan: AttackPlan) -> int:
    if o.playerIndex != my_index:
        # ボスの指令：現在の攻撃プラン(plan.damage)で確定KOできるベンチを最優先、次に低HP
        score = -card.hp
        if plan.attacker_id != -1 and plan.damage >= card.hp:
            score += 100000
        return score
    # 自分の交代先／強制昇格先
    energy_count = len(card.energies)
    fighting_count = card.energies.count(EnergyType.FIGHTING)
    score = energy_count * 10
    if _is_attack_ready(card.id, energy_count, fighting_count):
        score += 5000
    return score
```

`plan`はagent()内で既に計算済みの`AttackPlan`をそのまま渡す。ボスの指令のダメージ判定は、現在のアクティブが持つ`plan.damage`（対戦相手のHPに依存しない値）をそのままベンチ候補のHPと比較する方式で、イオナサンプルの`voltaic_dmg`ロジックと同じ考え方。

### 4. TO_HAND / TO_BENCH

```python
def _score_search_candidate(card_id: int, fs: FieldState) -> int:
    line = POKEMON_LINES.get(card_id)
    if line is not None:
        owned = fs.field_counts[card_id] + fs.hand_counts[card_id]
        if owned >= line.max_field_copies:
            return -1000  # もう十分
        score = 300
        if line.pre_evo_id is not None and fs.field_counts[line.pre_evo_id] == 0:
            score -= 200  # 進化前が場にいないなら優先度を下げる（先に進化前を確保すべき）
        return score
    if card_id == Basic_Lightning_Energy:
        return 150
    if card_id == Basic_Fighting_Energy:
        raging_needs_fighting = (fs.field_counts[Raging_Bolt_ex] > 0
                                  and fs.active_fighting_energy_count < 1)
        return 180 if raging_needs_fighting else 20
    return 0
```

TO_HAND・TO_BENCHは同じ優先度関数を共有する（欲しいものは変わらないため）。雷エネルギーは常に一定の需要があるため基礎150点、闘エネルギーはタケルライコexが場にいて闘エネ0の場合のみ優先度を上げる（180点）、それ以外は低優先（20点）とする。

### 5. DISCARD

```python
def _score_discard_candidate(card_id: int, fs: FieldState) -> int:
    line = POKEMON_LINES.get(card_id)
    if line is not None:
        owned = fs.field_counts[card_id] + fs.hand_counts[card_id]
        return 50 if owned > line.max_field_copies else -300
    if card_id == Basic_Lightning_Energy:
        return 30 if fs.hand_counts[Basic_Lightning_Energy] >= 3 else -50
    if card_id == Basic_Fighting_Energy:
        return -100  # 希少なので温存
    if card_id in (Boss_Orders, Lillie_Determination, Max_Rod):
        return -200  # キーカード・ACE SPECは温存
    return 10
```

ハイパーボール・カナリィのコスト（トラッシュ）選択で使用する。既に十分な数がある駒は気軽に切れる一方、キーサポート・ACE SPECは温存する。

## テスト方針

- `tests/test_jamoraiko_agent.py`に追加。既存の`_score_option`系テストパターン（モックの`obs`/`o`/`fs`を組み立てて期待値を比較）を踏襲
- 新規ヘルパー（`_score_setup_active`/`_is_attack_ready`/`_score_switch_target`/`_score_search_candidate`/`_score_discard_candidate`）を個別に単体テスト
- `_score_option`経由で`OptionType.CARD`が正しくディスパッチされる結合テストを最低1本追加（`feedback_agent_dispatch_coverage`メモリで指摘された「match文の分岐漏れ」の再発防止を兼ねる）
- 優先度の設計が中心なので、絶対値の一致ではなく相対順位（A の方が B よりスコアが高い）を検証するテストを中心にする
- `uv run pytest -q`でリポジトリ全体の回帰確認

## 検証方法

1. リポジトリ全体のテストがPASSすることを確認
2. `scripts/build_jamoraiko_vs_iono_notebook.py`を再実行し、`src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`のセル0（`%%writefile main.py`）を修正後のコードで再生成する（ビルド時にmain.py全文を埋め込む方式のため、コード改修後は再ビルドが必須）
3. ユーザーがKaggleで校正ノートブックを再実行し、イオナサンプル相手の勝率が0.015からどこまで改善したかを確認する

## リスクと備考

- `POKEMON_LINES`テーブルの優先度（300/200/150/180等のマジックナンバー）は、既存のイオナサンプル・`lucario_agent`のスコア体系を参考にした初期値であり、微調整はチューニング対象になりうる。今回はまず「壊滅的な事故を無くす」ことを目的とし、細かい数値の最適化は次回以降の課題とする
- ボスの指令のダメージ判定（`plan.damage`をそのままベンチ候補のHPと比較）は、対戦相手のポケモンごとの弱点・抵抗力を計算しない前提（本デッキのATTACKERSテーブルは元々そのような計算をしていない）。この前提は変更しない
- `TO_HAND`と`TO_BENCH`を同一関数で扱う設計だが、将来的に両者で優先度を分けたくなった場合は`_score_search_candidate`にコンテキスト引数を追加する形で拡張可能
