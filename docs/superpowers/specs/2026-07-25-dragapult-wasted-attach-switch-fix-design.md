# ドラパルトex 所感a・b修正 設計書（2026-07-25）

## 背景

2026-07-25、Kaggle提出後の新規20戦バトルログ実測調査（`docs/analyses/20260725-dragapult-ver8-5symptoms-investigation.md`）で、ユーザー報告の5所感のうち以下2件を確定バグと判定した。ユーザー判断で、優先度最高のこの2件のみ先に修正する。

- **所感a「無駄なエネルギー消費→にげる」**：20戦中12戦(60%)・16件。装着直後に一度も攻撃せず交代し、装着エネルギーがにげるコストで消える。
- **所感b「ドロンチ在場中の無駄なベンチ手張り」**：20戦中8戦(40%)・9件。アクティブの未攻撃可ドロンチを差し置き、無関係なベンチへエネルギーが流れる。

所感aは主因2つ（`do_switch`のBudew節が広すぎる／RETREATのスコアがエネルギー投資額を無視）のうち、**主因の片方（Budew節）のみ**を今回の修正範囲とする（ユーザー選択）。RETREATスコアリング自体と、副因の`_attach_score()`の+400ボーナス（4/16件の一部要因）は対象外。

## 修正1：所感a「Budew節の限定」

### 対象
`src/dragapult_agent/main.py:965`付近、`agent()`内のベタ書き変数`do_switch`。

### 現状のコード
```python
do_switch = (not can_main_attack and (bench_attacker or (active_id != Budew and field_counts[Budew] >= 1 and state.turn >= 2)))
```

### 問題
`bench_attacker`が偽でも、自分の場（アクティブ・ベンチ問わず）にBudewが1体でも存在すれば`do_switch`が真になる。アクティブに直前に装着したエネルギー投資額を一切考慮しないため、装着した直後のターンでも交代が選ばれ、エネルギーがにげるコストで無駄に捨てられる。

### 修正方針
`do_switch`を`_should_switch()`という独立関数へ抽出し（既存の`_attach_score()`・`_own_switch_target_score()`と同じ、テスト可能な純粋関数パターンに揃える）、Budew節に「アクティブの現在のエネルギー枚数が0の時だけ発火」という条件を追加する。`bench_attacker`分岐（攻撃準備済みの控えがいれば無条件に交代）は変更しない。

```python
def _should_switch(
    can_main_attack: bool, bench_attacker: bool, active_id: int,
    active_energy_count: int, budew_in_field: bool, turn: int,
) -> bool:
    """RETREAT(にげる)を検討すべきかを返す。
    bench_attacker: ベンチに攻撃準備済み(2エネ以上)のドラパルトexがいるか
    budew_in_field: 自分の場にスボミー(Budew)が存在するか（アクティブ・ベンチ問わず）
    Budew節は、アクティブにまだエネルギー投資が無い場合のみ発火させる
    （エネルギー装着直後の交代で投資が無駄になる問題への対応。2026-07-25実測20戦で
    12戦・16件確認。docs/analyses/20260725-dragapult-ver8-5symptoms-investigation.md）"""
    if can_main_attack:
        return False
    if bench_attacker:
        return True
    return active_id != Budew and budew_in_field and turn >= 2 and active_energy_count == 0
```

呼び出し側（`agent()`内、`main.py:965`相当）：
```python
active_energy_count = len(my_state.active[0].energies) if my_state.active else 0
do_switch = _should_switch(
    can_main_attack, bench_attacker, active_id, active_energy_count,
    field_counts[Budew] >= 1, state.turn,
)
```

## 修正2：所感b「_attach_score()のアクティブ側種族ボーナス欠落」

### 対象
`src/dragapult_agent/main.py:125-137`付近、`_attach_score()`の`energy_count == 0`分岐。

### 現状のコード
```python
else:  # energy_count == 0
    if active:
        if bench_attacker:
            score += 400
    else:
        if pokemon.id == Dragapult_ex:
            score += 150
        elif pokemon.id == Dreepy:
            score += 100
        else:
            score += 50
        if bench_attacker:
            score -= 200
```

### 問題
ベンチ側にのみ種族ボーナス（+150/+100/+50）があり、アクティブ側には無い。`bench_attacker`が偽の場面では、アクティブは常にscore=20000固定なのに対しベンチは20050〜20150となり、種族に関係なくベンチが必ず勝つ。アクティブの未攻撃可ドロンチを差し置いて無関係なベンチ（ドラパルト系統ですらない場合もある）へエネルギーが流れる。

### 修正方針
種族ボーナスをアクティブ・ベンチ共通で先に計算し、`bench_attacker`による加減点のみをactive/bench で分岐させる（重複コードの解消も兼ねる）。

```python
else:  # energy_count == 0
    if pokemon.id == Dragapult_ex:
        score += 150
    elif pokemon.id == Dreepy:
        score += 100
    else:
        score += 50
    if active:
        if bench_attacker:
            score += 400
    else:
        if bench_attacker:
            score -= 200
```

## テスト方針

- `_should_switch()`：新規関数のため単体テストを新設。最低限のケース：
  1. `bench_attacker=True`なら他の条件によらず`True`
  2. Budew節：`active_energy_count=0`かつBudewが場にいれば`True`
  3. Budew節：`active_energy_count>0`なら（`bench_attacker=False`の場合）`False`（今回の修正で変わる挙動）
  4. `can_main_attack=True`なら常に`False`
- `_attach_score()`：既存テスト（`tests/test_dragapult_agent.py`）に、`energy_count==0`かつ`active=True`かつ`bench_attacker=False`の場面でDragapult_ex/Dreepy/その他の種族ボーナスが加算されることを検証するケースを追加。
- 既存テストスイート全体（現時点704件PASS）が壊れないことを確認する。

## 影響範囲・非目標

- 所感aのRETREATスコアリング自体（`main.py:1172-1176`）と、`_attach_score()`の`+400`ボーナス（副因、4/16件の一部）は**今回のスコープ外**。
- 所感c・d・e、および他の修正候補（バックログ参照）は今回のスコープ外。
- `_should_switch()`は`agent()`内1箇所からのみ呼ばれる新規抽出であり、既存の`bench_attacker`分岐の挙動は変えない。
- `_attach_score()`の変更は既存呼び出し全パターンに影響するため、全体テストスイートの再実行で回帰がないことを確認する。

## フォローアップ（修正後の継続監視）

修正2（所感b）は、今回の調査で「妥当な挙動」と分類した5件・「グレーゾーン」と分類した3件（ベンチ側が既に1エネ投資済みで"完成優先"と解釈できるケース）には影響しない設計だが、ロジック変更が実戦でどう作用するかはコードレビューだけでは確証が持てない。
[[feedback_log_driven_debugging]]の方針に倣い、Kaggle再提出後に新規バトルログが貯まり次第、以下を再確認する：
- 所感bのパターン（アクティブの未攻撃可ドロンチを差し置いたベンチ手張り）が実際に解消しているか
- 種族ボーナスの対称化によって、意図しない副作用（例：ベンチのDragapult_ex完成を過度に遅らせる等）が発生していないか
- 所感aのパターン（無駄なエネルギー→にげる）についても、Budew節の限定で15/16件が解消する想定通りの効果が出ているか

この継続監視はコード修正の完了条件ではなく、次回セッション開始時のバックログ項目として記録する。
