# ルカリオex エネルギー事故修正 実装計画

> **エージェント実行者へ:** 必須サブスキル：`superpowers:subagent-driven-development`（推奨）または `superpowers:executing-plans` を使い、タスク単位で実装すること。各ステップはチェックボックス（`- [ ]`）形式。

**ゴール:** メガルカリオexエージェントが「バトル場にエネルギーが乗らないまま動けなくなる」2つの原因（DISCARD時の闘エネルギー自己破棄／バトル場0エネ時にベンチへ装着）を取り除く。

**アーキテクチャ:** 既存のヒューリスティックスコアリング（`src/lucario_agent/main.py` の `_score_card_option` / `_score_attach_option`）のスコア値と分岐条件のみを変更する。関数シグネチャ・データ構造・エージェントの制御フローは一切変えない。加えて、効果測定を再現可能にするため計測スクリプトを `scripts/` に常設する。

**技術スタック:** Python 3.12 / pytest / uv。ポケカ対戦エンジンの型定義は `data/competition/sample_submission/cg/api.py`（macOSでは `cg.sim` をモックしないとロードできない。`tests/conftest.py` が既に処理済み）。

## Global Constraints

- コードコメント・ドキュメントはすべて日本語で書く（変数名・関数名は英語でよい）。
- 既存の 754 件のテストを 1 件も壊さないこと。テスト実行は `uv run pytest`。
- **本計画のスコープは原因1・原因2のみ。** 原因3（オーガポンexが0エネで攻撃も退却もできないデッドロック）とデッキ構成変更（オーガポンex → マクノシタ／ハリテヤマ）は**本計画では扱わない**。ユーザーの明示的な決定事項。
- スコア値を変更する際は、**既存スコアとの同点（タイ）を作らないこと**。同点になると選択肢の提示順（エンジン依存で制御不能）で結果が決まる。2026-07-28 に EVOLVE(9000) と Judge(9000) の同点で実害が出た前例がある。
- 効果判定に勝率・LBスコアを使わない。同一ロジックの20戦バッチで勝率が±20pt動くことが実証済み（Fisher両側 p=0.343）。判定は本計画末尾の「プロセス指標」で行う。

## 前提：確定済みの根本原因（2026-07-29 の systematic-debugging で実データ再現済み）

**原因1 — `src/lucario_agent/main.py:264-265`**

```python
if card.id == Basic_Fighting_Energy:
    return 50 if hand_counts[Basic_Fighting_Energy] >= 2 else -20
```

手札に基本闘エネルギーが2枚以上あるとスコア **50** を返す。これは汎用トレーナーズのデフォルト **10** より高いため、ハイパーボール等のコスト選択でエネルギーが真っ先に捨てられる。

実測（ログ `88607286` step18、ハイパーボールのコスト2枚選択）:

| 手札の候補 | スコア | 結果 |
|---|---|---|
| 基本闘エネルギー | 50 | **捨てられた** |
| 基本闘エネルギー | 50 | **捨てられた** |
| Pokégear 3.0 | 10 | 残った |
| Judge | -100 | 残った |
| Judge | -100 | 残った |

この試合はT1でエネルギー2枚を失い、その後12ターンにわたりバトル場のオーガポンexが0エネで棒立ちになった。

「守っている」つもりの `-20` も不十分で、Boss's Orders / Lillie's Determination（-50）や Judge（-100）より高いため、それらが代替候補のときは手札に1枚しかなくてもエネルギーが捨てられる（`88591718` step11 で実測）。ロック闘エネルギー（-20、デッキ4枚・夜のタンカで回収不可）も同じ理由で `88591718` step19 で Boss's Orders より優先して捨てられていた。

**ver24+ver25 の40戦で、他に捨てられる札があったのにエネルギーを選んだケースが16件（計23枚）。** デッキ内のエネルギーは11枚しかない。

**原因2 — `src/lucario_agent/main.py:535-540` および `src/lucario_agent/combat.py:59-88`**

`energy_score` のバトル場ボーナスは `+10` のみで、ベンチのリオル／メガルカリオexが受け取る `+100`（エネルギー2個未満）に押し負ける。実盤面での再現値：

| 装着先 | スコア |
|---|---|
| バトル場のオーガポンex / 0エネ | **8090** |
| ベンチのリオル / 0エネ | **8100** ← 実際に選ばれた |
| ベンチのメガルカリオex / 1エネ | 8101 |
| ベンチのソルロック / 0エネ | 8020 |
| ベンチのルナトーン / 0エネ | 7900 |

**40戦で30件**、バトル場が0エネなのにベンチへ装着していた（30件すべてでバトル場に付ける選択肢も提示されていた）。バトル場が0エネだと技を撃てないうえ**逃げるコストも払えない**ため、盤面が停止する。

---

## ファイル構成

| ファイル | 変更種別 | 責務 |
|---|---|---|
| `src/lucario_agent/main.py` | 修正（`_score_card_option` の DISCARD 分岐 / `_score_attach_option` のバトル場分岐） | 選択肢スコアリング |
| `tests/test_lucario_agent.py` | 修正＋追加（`TestDiscardContext` の既存2件を更新、新規クラス `TestScoreAttachOptionStuckActive` を追加） | 回帰テスト |
| `scripts/analyze_lucario_energy_metrics.py` | 新規作成 | プロセス指標の計測を再現可能な形で常設する |
| `tests/test_analyze_lucario_energy_metrics.py` | 新規作成 | 計測スクリプトのユニットテスト |

`combat.py` の `energy_score` は**変更しない**。バトル場救済の判断には攻撃プラン（`current_plan`）が必要だが `energy_score` はそれを受け取らないため、`_score_attach_option` 側で処理する。これにより `energy_score` の既存テスト（`tests/test_lucario_agent.py:100-220`）に影響が出ない。

---

## Task 1: DISCARD時に闘エネルギーを温存する

**Files:**
- Modify: `src/lucario_agent/main.py:261-279`
- Test: `tests/test_lucario_agent.py`（既存クラス `TestDiscardContext`、1439行目付近）

**Interfaces:**
- Consumes: なし（既存の `_score_card_option(obs, o, context, my_index, state, my_state, field_counts, hand_counts, discard_counts, attacker1, current_plan, ability_used_flag, op_active_nullifies_ex=False) -> int` をそのまま使う）
- Produces: `SelectContext.DISCARD` における新しいスコア序列。Task 3 の計測スクリプトはこの序列に依存しない（実ログを読むだけ）ため結合はない。

**設計方針（スコア序列）**

変更後の DISCARD スコアは次の順序になる。値はすべて既存値と重複しない（同点回避）。

| カード | 変更前 | 変更後 | 根拠 |
|---|---|---|---|
| 汎用トレーナーズ（Pokégear 3.0 等） | 10 | 10（据置） | 最も捨ててよい |
| Boss's Orders / Lillie's Determination | -50 | -50（据置） | 複数枚あり代替が効く |
| **基本闘エネルギー（手札3枚以上）** | 50 | **-60** | 3枚目以降は余剰。ただしトレーナーズより価値が高い |
| **基本闘エネルギー（手札2枚以下）** | 50 / -20 | **-90** | 2枚はメガブレイブ（闘闘）にちょうど必要な枚数であり余剰ではない |
| **ロック闘エネルギー** | -20 | **-95** | デッキ4枚のみ・夜のタンカで回収不可のため基本闘より強く温存 |
| キーポケモン / Judge | -100 | -100（据置） | — |
| Maximum Belt | -150 | -150（据置） | ACE SPEC 1枚のみ・回収不可 |

**重要な設計判断：エネルギーをキーポケモン（-100）より下げてはいけない。** 下げると、コスト候補が全部高価値なとき（例：手札が [リオル, 基本闘, 基本闘] でハイパーボールに2枚必要）にリオルを捨ててしまう。ハイパーボールはポケモンをサーチするカードなので、ポケモンを捨ててポケモンを取るのは本末転倒になる。

**ルナサイクル（ルナトーンの特性）への影響はない。** ルナサイクルのコスト支払いでは選択肢が基本闘エネルギーのみ（実測40戦すべてで代替候補ゼロ）であり、`return desc_indices[:select.maxCount]` はスコアの正負に関わらず上位 maxCount 件を返すため、スコアを下げても支払いは成立する。

- [ ] **Step 1: 既存テストが新しい期待値で落ちるように書き換える**

`tests/test_lucario_agent.py` の `TestDiscardContext` 内、既存の2メソッドを次の内容で置き換える。

```python
    def test_basic_fighting_energy_protected_when_exactly_two(self):
        """手札2枚はメガブレイブ(闘闘)にちょうど必要な枚数なので「余剰」ではない。
        2026-07-29の実測40戦で、他に捨てられる札があるのにエネルギーを選んだケースが16件あった"""
        energy = Card(id=lm.Basic_Fighting_Energy, serial=1, playerIndex=0)
        obs = self._obs(energy)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int, {lm.Basic_Fighting_Energy: 2}),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == -90

    def test_basic_fighting_energy_slightly_less_protected_when_three_or_more(self):
        """3枚目以降は余剰なので、2枚以下のときより捨てやすくする（ただしトレーナーズよりは温存）"""
        energy = Card(id=lm.Basic_Fighting_Energy, serial=1, playerIndex=0)
        obs = self._obs(energy)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int, {lm.Basic_Fighting_Energy: 3}),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == -60

    def test_protects_rock_fighting_energy_more_than_basic(self):
        """ロック闘エネルギーは夜のタンカで回収不可・デッキ内4枚のみのため、
        基本闘エネルギーより強く温存する（88591718 step19でBoss's Ordersより先に捨てていた）"""
        energy = Card(id=lm.Rock_Fighting_Energy, serial=1, playerIndex=0)
        obs = self._obs(energy)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int, {lm.Rock_Fighting_Energy: 3}),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == -95
```

**注意：** 削除するのは `test_prefers_spare_fighting_energy`（`assert score == 50`）と `test_protects_rock_fighting_energy_regardless_of_count`（`assert score == -20`）の2つ。この2つは修正前のバグ挙動を固定してしまっているため、残してはいけない。

- [ ] **Step 2: テストを実行して落ちることを確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestDiscardContext -v
```

期待：`test_basic_fighting_energy_protected_when_exactly_two` が `assert 50 == -90` で FAIL、
`test_basic_fighting_energy_slightly_less_protected_when_three_or_more` が `assert 50 == -60` で FAIL、
`test_protects_rock_fighting_energy_more_than_basic` が `assert -20 == -95` で FAIL。

- [ ] **Step 3: 序列を検証する回帰テストを追加する**

`TestDiscardContext` クラスの末尾に次を追加する。個別の数値だけでなく「相対順序」を固定することで、将来スコアを調整しても意図が壊れないようにする。

```python
    def _discard_score(self, card_id, hand_counts=None):
        card = Card(id=card_id, serial=1, playerIndex=0)
        obs = self._obs(card)
        return lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int, hand_counts or {}),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )

    def test_discard_priority_order(self):
        """トレーナーズ > Boss's Orders > 基本闘エネ > ロック闘エネ > キーポケモン > Maximum Belt
        の順に「捨てやすさ」が下がることを固定する（同点が無いことも同時に保証）"""
        generic = self._discard_score(lm.Pokegear)
        boss    = self._discard_score(lm.Boss_Orders)
        basic2  = self._discard_score(lm.Basic_Fighting_Energy, {lm.Basic_Fighting_Energy: 2})
        basic3  = self._discard_score(lm.Basic_Fighting_Energy, {lm.Basic_Fighting_Energy: 3})
        rock    = self._discard_score(lm.Rock_Fighting_Energy, {lm.Rock_Fighting_Energy: 3})
        riolu   = self._discard_score(lm.Riolu)
        belt    = self._discard_score(lm.Maximum_Belt)
        assert generic > boss > basic3 > basic2 > rock > riolu > belt

    def test_energy_never_discarded_before_generic_trainer(self):
        """回帰テスト本体：88607286 step18 の再現。
        Pokégear 3.0 が手札にあるとき、基本闘エネルギーより先に Pokégear が捨てられること"""
        assert self._discard_score(lm.Pokegear) > \
               self._discard_score(lm.Basic_Fighting_Energy, {lm.Basic_Fighting_Energy: 2})

    def test_energy_still_discarded_before_key_pokemon(self):
        """過剰保護の防止：コスト候補が全部高価値なとき、リオルより先にエネルギーを捨てること
        （ハイパーボールはポケモンをサーチする札なので、ポケモンを捨てるのは本末転倒）"""
        assert self._discard_score(lm.Basic_Fighting_Energy, {lm.Basic_Fighting_Energy: 2}) > \
               self._discard_score(lm.Riolu)
```

- [ ] **Step 4: テストを実行して新規テストも落ちることを確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestDiscardContext -v
```

期待：`test_discard_priority_order` と `test_energy_never_discarded_before_generic_trainer` が FAIL（変更前は基本闘エネ=50 が generic=10 より上のため）。`test_energy_still_discarded_before_key_pokemon` は変更前でも PASS する（50 > -100）が、これは過剰保護を防ぐガードレールなので残す。

- [ ] **Step 5: 実装する**

`src/lucario_agent/main.py` の 264-268行目を次に置き換える。

```python
            if card.id == Basic_Fighting_Energy:
                # 【2026-07-29修正】旧実装は「手札2枚以上なら余剰」とみなして +50（汎用トレーナーズの
                # 既定値10より高い）を返しており、ハイパーボール等のコストで真っ先に捨てられていた。
                # 2枚はメガブレイブ(闘闘)にちょうど必要な枚数であり余剰ではない。デッキ内の
                # エネルギーは11枚のみ。実測ver24+ver25の40戦で、他に捨てられる札があるのに
                # エネルギーを選んだケースが16件（計23枚）あった（88607286 step18 ほか）。
                # ただしキーポケモン(-100)より下げてはいけない：下げると、コスト候補が全部
                # 高価値なときにリオル等を捨ててしまう（ハイパーボールはポケモンをサーチする
                # 札なので、ポケモンを捨ててポケモンを取るのは本末転倒になる）。
                return -60 if hand_counts[Basic_Fighting_Energy] >= 3 else -90
            if card.id == Rock_Fighting_Energy:
                # 夜のタンカで回収不可・デッキ内4枚のみのため、基本闘エネルギーより強く温存する。
                # 旧値 -20 では Boss's Orders(-50) より先に捨てられていた（88591718 step19で実測）。
                return -95
```

- [ ] **Step 6: テストを実行して通ることを確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestDiscardContext -v
```

期待：全件 PASS。

- [ ] **Step 7: 全テストを実行して他が壊れていないことを確認**

```bash
uv run pytest
```

期待：全件 PASS（着手時 754 件 + 本タスクの追加分）。もし他のテストが落ちた場合は、そのテストが旧スコア値に依存していないか確認する。落ちたテストの期待値を安易に書き換えず、なぜ落ちたかを説明できるようにすること。

- [ ] **Step 8: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix(lucario): DISCARD時に闘エネルギーを温存する

手札2枚以上の基本闘エネルギーに+50を与えていたため、ハイパーボール等の
コストで汎用トレーナーズ(10)より先に捨てられていた。2枚はメガブレイブに
ちょうど必要な枚数で余剰ではない。実測40戦で回避可能な自己破棄が16件。
ロック闘エネルギーも-20ではBoss's Orders(-50)に負けるため-95に強化。"
```

---

## Task 2: バトル場が0エネのときは装着先をバトル場に優先する

**Files:**
- Modify: `src/lucario_agent/main.py:535-541`
- Test: `tests/test_lucario_agent.py`（新規クラス `TestScoreAttachOptionStuckActive` を `TestScoreAttachOptionMaximumBeltVsAirBalloon` の直後に追加）

**Interfaces:**
- Consumes: `lm._score_attach_option(obs, o, my_index, current_plan, attacker1, op_active_nullifies_ex=False) -> int`（既存シグネチャのまま）、`lm.AttackPlan`（`attacker: int`, `energy: bool` を参照）
- Produces: なし（他タスクは依存しない）

**設計方針**

`AttackPlan.energy` は「今ターン攻撃するために、あと1個エネルギーを装着する必要がある」ことを表す（`combat.py:208` の `more_energy = True`）。したがって：

- `current_plan.energy == True` のとき → 今ターン攻撃が成立するプランがある。**そちらを最優先する**（既存の +200 ボーナスがそのまま働く）。救済ボーナスは付けない。
- `current_plan.energy == False` のとき → 追加装着で今ターン攻撃できるプランは存在しない。このときバトル場が0エネなら、そこに付けるのが最善（**攻撃も退却もできないデッドロックを解消できる唯一の手段**）。

**【2026-07-29最終レビューで修正】** ベンチ側の +200 は発動しないが、`Rock_Fighting_Energy` の
アクティブ優先 +500（本ファイル 537-543行目、`_score_attach_option` 冒頭部分）とは**排他ではなく
加算される**（同一の装着先で両方の条件を満たしうるため）。したがって救済ボーナスは素の
`energy_score` 値（7900〜8101）とだけ競合するわけではない。加算後の実際の最大値は
「バトル場0エネの Ogerpon_ex + ロック闘エネルギー + attacker1=True」の
`8000+10+80+40+500(アクティブ優先)+300(救済) = 8930` であり、これが全組み合わせの中の最大値
（総当たり検証済み）。

したがって救済ボーナスは **+300** とする。

- **下限**：ベンチのメガルカリオex(1エネ)の `energy_score = 8101` に確実に勝つ必要がある。
  救済込みの最小値（Lunatone、またはRiolu/Mega_Lucario_exでattacker1・op_active_nullifies_ex
  両方が効いた場合の `7910`）+300 = `8210` で上回る。
- **上限**：ロック闘エネルギーのアクティブ優先 +500 と重なっても 9000 を超えないこと
  （EVOLVE の `9100 + len(pokemon.energies)` の帯域を侵さないこと）。上記の最大値 `8930` は
  この条件を満たす。

**旧版（+500）の誤り：** 当初は「ベンチ側+200が発動しないため素のenergy_scoreとだけ競合し、
+500で十分」としていたが、アクティブ優先+500との加算を見落としていた。+500のままだと
最大値が `9130` となり EVOLVE の帯域に食い込むため、最終レビューで +300 に修正した
（総当たり検証で同点自体は未発生と確認済み。詳細は `docs/reviews/` のレビュー記録を参照）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py` に次のクラスを追加する。

```python
class TestScoreAttachOptionStuckActive:
    """【2026-07-29】バトル場が0エネだと技を撃てず、逃げるコストも払えないため盤面が停止する。
    実測ver24+ver25の40戦で、バトル場0エネなのにベンチへ装着していたケースが30件あった
    （30件すべてバトル場に付ける選択肢も提示されていた）。攻撃プランを妨げない範囲で
    バトル場への装着を優先する"""

    def _score(self, target_pokemon, is_active, current_plan, bench=None):
        obs = MagicMock()
        energy = Card(id=lm.Basic_Fighting_Energy, serial=1, playerIndex=0)
        my_state = make_player_state(
            active_pokemon=target_pokemon if is_active else make_pokemon(id=lm.Lunatone),
            bench=bench if bench is not None else ([] if is_active else [target_pokemon]),
            hand=[energy],
        )
        obs.current.players = [my_state, make_player_state()]
        option = Option(
            type=OptionType.ATTACH, area=lm.AreaType.HAND, index=0,
            inPlayArea=lm.AreaType.ACTIVE if is_active else lm.AreaType.BENCH,
            inPlayIndex=0,
        )
        return lm._score_attach_option(
            obs, option, my_index=0, current_plan=current_plan, attacker1=False,
        )

    def test_zero_energy_active_beats_bench_riolu(self):
        """88607286 step15 の再現：バトル場オーガポンex(0エネ)が
        ベンチのリオル(0エネ)に勝つこと。修正前は 8090 対 8100 で負けていた"""
        no_plan = lm.AttackPlan()
        active_score = self._score(make_pokemon(id=lm.Ogerpon_ex), True, no_plan)
        bench_score  = self._score(make_pokemon(id=lm.Riolu), False, no_plan)
        assert active_score > bench_score

    def test_zero_energy_active_beats_bench_mega_lucario(self):
        """88607286 step95 の再現：バトル場オーガポンex(0エネ)が
        ベンチのメガルカリオex(1エネ)に勝つこと。修正前は 8090 対 8101 で負けていた"""
        no_plan = lm.AttackPlan()
        active_score = self._score(make_pokemon(id=lm.Ogerpon_ex), True, no_plan)
        bench_score  = self._score(make_pokemon(id=lm.Mega_Lucario_ex, energies=[6]), False, no_plan)
        assert active_score > bench_score

    def test_zero_energy_lunatone_active_also_rescued(self):
        """88609232 step6 の再現：バトル場がルナトーン(0エネ・非アタッカー)でも救済する。
        救済の目的は「攻撃または退却の可能性を開くこと」。ルナトーンは逃げるコストが1のため、
        1個付ければ次のターンに退却して本来のアタッカーを出せる（リオル・メガルカリオexは
        逃げるコストが2のため1個では退却できず、この効果は限定的。最終レビュー指摘2で修正）"""
        no_plan = lm.AttackPlan()
        active_score = self._score(make_pokemon(id=lm.Lunatone), True, no_plan)
        bench_score  = self._score(make_pokemon(id=lm.Riolu), False, no_plan)
        assert active_score > bench_score

    def test_rock_fighting_energy_rescue_stacks_with_active_priority_and_stays_below_evolve(self):
        """【最終レビュー指摘1の回帰】ロック闘エネルギーのアクティブ優先+500と
        本救済+300は排他ではなく加算される。合計値がEVOLVE(9100+len(energies))の
        帯域を侵さない(9000未満)ことを固定する"""
        no_plan = lm.AttackPlan()
        obs = MagicMock()
        rock_energy = Card(id=lm.Rock_Fighting_Energy, serial=1, playerIndex=0)
        ogerpon = make_pokemon(id=lm.Ogerpon_ex)
        my_state = make_player_state(active_pokemon=ogerpon, hand=[rock_energy])
        obs.current.players = [my_state, make_player_state()]
        option = Option(
            type=OptionType.ATTACH, area=lm.AreaType.HAND, index=0,
            inPlayArea=lm.AreaType.ACTIVE, inPlayIndex=0,
        )
        baseline = lm.energy_score(ogerpon, True, True, op_active_nullifies_ex=False)
        score = lm._score_attach_option(
            obs, option, my_index=0, current_plan=no_plan, attacker1=True,
        )
        assert score == baseline + 500 + 300
        assert score < 9000

    def test_rescue_bonus_not_applied_when_attack_plan_needs_energy(self):
        """今ターン攻撃が成立するプランがあるときは救済しない（攻撃を優先する）。
        current_plan.energy=True はベンチのアタッカーがあと1個で攻撃できる状態を表す"""
        plan = lm.AttackPlan(attacker=1, energy=True)
        active_score = self._score(make_pokemon(id=lm.Ogerpon_ex), True, plan)
        bench_score  = self._score(make_pokemon(id=lm.Mega_Lucario_ex, energies=[6]), False, plan)
        assert bench_score > active_score

    def test_rescue_bonus_not_applied_when_active_already_has_energy(self):
        """バトル場に既にエネルギーがあるならデッドロックではないので救済ボーナスは付かない"""
        no_plan = lm.AttackPlan()
        charged = self._score(make_pokemon(id=lm.Ogerpon_ex, energies=[6]), True, no_plan)
        empty   = self._score(make_pokemon(id=lm.Ogerpon_ex), True, no_plan)
        assert empty > charged
```

- [ ] **Step 2: テストを実行して落ちることを確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestScoreAttachOptionStuckActive -v
```

期待：`test_zero_energy_active_beats_bench_riolu`、`test_zero_energy_active_beats_bench_mega_lucario`、`test_zero_energy_lunatone_active_also_rescued`、`test_rescue_bonus_not_applied_when_active_already_has_energy` が FAIL。
`test_rescue_bonus_not_applied_when_attack_plan_needs_energy` は変更前でも PASS する（既存の +200 が働くため）が、これはデグレ検知用のガードレールなので残す。

- [ ] **Step 3: 実装する**

`src/lucario_agent/main.py` の 535-540行目を次に置き換える。

```python
    if o.inPlayArea == AreaType.ACTIVE:
        if current_plan.attacker == 0 and current_plan.energy:
            score += 200
        elif not current_plan.energy and not pokemon.energies:
            # 【2026-07-29追加、2026-07-29最終レビューで+500→+300に修正】
            # バトル場が0エネだと「技を撃てない」だけでなく「にげるコストを払えない」ため、
            # 自力では絶対に場を離れられないデッドロックになる。実測ver24+ver25の40戦で、
            # バトル場0エネなのにベンチへ装着したケースが30件あり（30件すべてバトル場への
            # 装着も提示されていた）、オーガポンexはバトル場に95ターン居座って73%が0エネ・
            # 攻撃はわずか18回だった。current_plan.energy が False = 「あと1個の装着で今ターン
            # 攻撃できるプラン」が無い、という条件なので、成立している攻撃プランを横取りする
            # ことはない。
            #
            # 【注意】この救済ボーナスは、数行上のロック闘エネルギーのアクティブ優先+500と
            # 排他ではなく加算される（同一の装着先で両方の条件を満たしうるため）。したがって
            # 素のenergy_score(7900〜8101)とだけ競合するわけではない。加算後の実際の最大値は
            # 「バトル場0エネのOgerpon_ex + ロック闘エネルギー + attacker1=True」の
            # 8000+10+80+40+500(アクティブ優先)+300(本救済)=8930。
            # +300 という値の根拠：
            #   下限：ベンチのメガルカリオex(1エネ)のenergy_score=8101に確実に勝つ必要がある
            #   （救済込みの最小値は7910+300=8210で上回る）。
            #   上限：ロック闘エネルギーのアクティブ優先+500と重なっても9000を超えないこと
            #   （最大値8930はEVOLVE(9100始まり)の帯域を侵さない）。
            # +500のままだと最大値が9130となりEVOLVE(9100+len(energies))の帯域に食い込むため、
            # 最終レビューの指摘で+300に引き下げた（同点自体は総当たり検証で未発生と確認済み）。
            score += 300
    else:
        if current_plan.attacker == 1 + o.inPlayIndex and current_plan.energy:
            score += 200
    return score
```

- [ ] **Step 4: テストを実行して通ることを確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestScoreAttachOptionStuckActive -v
```

期待：全6件 PASS（最終レビュー指摘1の回帰テスト `test_rock_fighting_energy_rescue_stacks_with_active_priority_and_stays_below_evolve` を含む）。

- [ ] **Step 5: 全テストを実行**

```bash
uv run pytest
```

期待：全件 PASS。

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix(lucario): バトル場が0エネのときは装着先をバトル場に優先する

バトル場0エネは技も退却も不可能なデッドロックだが、energy_scoreの
バトル場ボーナス+10がベンチの+100(エネ2個未満)に負けて放置されていた。
実測40戦で30件。今ターン攻撃が成立するプラン(current_plan.energy)が
無い場合に限り+500して救済する。"
```

---

## Task 3: プロセス指標の計測スクリプトを常設する

**Files:**
- Create: `scripts/analyze_lucario_energy_metrics.py`
- Create: `tests/test_analyze_lucario_energy_metrics.py`

**Interfaces:**
- Consumes: なし
- Produces: `measure_energy_discards(data: dict, my_name: str = "Kagura_UT") -> list[dict]` と `measure_attach_targets(data: dict, my_name: str = "Kagura_UT") -> dict`。どちらもバトルログJSONを `json.load` した dict をそのまま受け取る。

**なぜ必要か:** 2026-07-28 の修正では「修正前の測定手順が残っていなかった」ため、次の検証時にベースラインを測り直す羽目になった。同じ轍を踏まないよう、今回の2指標は最初からスクリプトとして残す。既存の `scripts/analyze_dragapult_attach_scoring.py` と同じ配置・同じテスト方針に揃える。

**実装上の必須事項（過去に事故った罠）:**
- 自分のプレイヤーindexは `data['info']['Agents']` の `Name` から毎試合求める。**0固定にしてはいけない**（試合ごとに0/1が入れ替わる。ver24+ver25の40戦では index0が17戦・index1が23戦）。
- ある観測ステップ `steps[N]` の `select.option` に対して実際に選ばれたインデックスは `steps[N]['action']` ではなく **`steps[N+1][my_index]['action']`** に入っている（1ステップずれ）。
- カードIDは `src/lucario_agent/constants.py` の定数を使う（基本闘エネルギー=6、ロック闘エネルギー=20）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_analyze_lucario_energy_metrics.py` を新規作成する。

```python
"""scripts/analyze_lucario_energy_metrics.py のユニットテスト"""
import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "analyze_lucario_energy_metrics",
    Path(__file__).resolve().parents[1] / "scripts" / "analyze_lucario_energy_metrics.py",
)
alem = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(alem)

BASIC_F = 6
ROCK_F = 20


def _make_log(my_index, hand, options, chosen, context, select_type=1):
    """1ステップだけの最小バトルログを組み立てる。
    my_index が 1 のときも正しく動くことを確認するために使う"""
    agents = [{"Name": "opponent"}, {"Name": "opponent"}]
    agents[my_index] = {"Name": "Kagura_UT"}
    players = [{"active": [], "bench": [], "hand": []}, {"active": [], "bench": [], "hand": []}]
    players[my_index] = {"active": [], "bench": [], "hand": hand}
    step0 = [{"status": "INACTIVE"}, {"status": "INACTIVE"}]
    step0[my_index] = {
        "status": "ACTIVE",
        "observation": {
            "current": {"turn": 1, "players": players},
            "select": {"type": select_type, "context": context,
                       "minCount": 1, "maxCount": 1, "option": options},
        },
    }
    step1 = [{"action": None}, {"action": None}]
    step1[my_index] = {"status": "INACTIVE", "action": chosen}
    return {"info": {"Agents": agents}, "rewards": [1, -1], "steps": [step0, step1]}


@pytest.mark.parametrize("my_index", [0, 1])
def test_detects_energy_discard_with_alternatives(my_index):
    """他に捨てられる札があるのにエネルギーを捨てた場合を検出する"""
    hand = [{"id": BASIC_F}, {"id": 1122}]  # 基本闘エネ / Pokégear 3.0
    options = [
        {"type": 3, "area": 2, "index": 0, "playerIndex": my_index},
        {"type": 3, "area": 2, "index": 1, "playerIndex": my_index},
    ]
    data = _make_log(my_index, hand, options, chosen=[0], context=8)
    events = alem.measure_energy_discards(data)
    assert len(events) == 1
    assert events[0]["avoidable"] is True
    assert events[0]["discarded"] == [BASIC_F]


@pytest.mark.parametrize("my_index", [0, 1])
def test_marks_unavoidable_when_only_energy_offered(my_index):
    """選択肢がエネルギーしか無い場合（ルナサイクルのコスト等）は回避不能として記録する"""
    hand = [{"id": BASIC_F}]
    options = [{"type": 3, "area": 2, "index": 0, "playerIndex": my_index}]
    data = _make_log(my_index, hand, options, chosen=[0], context=8)
    events = alem.measure_energy_discards(data)
    assert len(events) == 1
    assert events[0]["avoidable"] is False


def test_ignores_non_energy_discard():
    """エネルギー以外を捨てた場合は記録しない"""
    hand = [{"id": 1122}]
    options = [{"type": 3, "area": 2, "index": 0, "playerIndex": 0}]
    data = _make_log(0, hand, options, chosen=[0], context=8)
    assert alem.measure_energy_discards(data) == []


@pytest.mark.parametrize("my_index", [0, 1])
def test_counts_bench_attach_while_active_empty(my_index):
    """バトル場が0エネなのにベンチへ装着した回数を数える"""
    hand = [{"id": BASIC_F}]
    options = [
        {"type": 8, "area": 2, "index": 0, "inPlayArea": 4, "inPlayIndex": 0},
        {"type": 8, "area": 2, "index": 0, "inPlayArea": 5, "inPlayIndex": 0},
    ]
    data = _make_log(my_index, hand, options, chosen=[1], context=0, select_type=0)
    players = data["steps"][0][my_index]["observation"]["current"]["players"]
    players[my_index]["active"] = [{"id": 117, "energies": []}]
    players[my_index]["bench"] = [{"id": 677, "energies": []}]
    stat = alem.measure_attach_targets(data)
    assert stat["to_bench"] == 1
    assert stat["to_active"] == 0
    assert stat["to_bench_while_active_zero"] == 1


@pytest.mark.parametrize("my_index", [0, 1])
def test_counts_active_attach(my_index):
    """バトル場へ装着した場合は to_active に計上し、停滞カウントは増やさない"""
    hand = [{"id": BASIC_F}]
    options = [
        {"type": 8, "area": 2, "index": 0, "inPlayArea": 4, "inPlayIndex": 0},
        {"type": 8, "area": 2, "index": 0, "inPlayArea": 5, "inPlayIndex": 0},
    ]
    data = _make_log(my_index, hand, options, chosen=[0], context=0, select_type=0)
    players = data["steps"][0][my_index]["observation"]["current"]["players"]
    players[my_index]["active"] = [{"id": 117, "energies": []}]
    players[my_index]["bench"] = [{"id": 677, "energies": []}]
    stat = alem.measure_attach_targets(data)
    assert stat["to_active"] == 1
    assert stat["to_bench_while_active_zero"] == 0
```

- [ ] **Step 2: テストを実行して落ちることを確認**

```bash
uv run pytest tests/test_analyze_lucario_energy_metrics.py -v
```

期待：`FileNotFoundError` または `spec_from_file_location` が None を返して ERROR。スクリプトがまだ無いため。

- [ ] **Step 3: スクリプトを実装する**

`scripts/analyze_lucario_energy_metrics.py` を新規作成する。

```python
"""ルカリオexエージェントのエネルギー運用プロセス指標を実バトルログから計測する。

2026-07-29の修正（DISCARD時の闘エネルギー温存 / バトル場0エネ時の装着優先）の
効果判定に使う。勝率やLBスコアでは効果を判定できないため（同一ロジックの20戦で
勝率が±20pt動くことが実証済み）、「狙った挙動が実際に何回消えたか」で判定する。

使い方:
    uv run python scripts/analyze_lucario_energy_metrics.py data/battle_logs/*.json
"""
import json
import sys
from collections import defaultdict

# カードID（src/lucario_agent/constants.py と同値）
BASIC_FIGHTING_ENERGY = 6
ROCK_FIGHTING_ENERGY = 20
ENERGY_IDS = frozenset({BASIC_FIGHTING_ENERGY, ROCK_FIGHTING_ENERGY})

# cg.api の列挙値
AREA_HAND = 2
AREA_ACTIVE = 4
AREA_BENCH = 5
OPTION_CARD = 3
OPTION_ATTACH = 8
SELECT_TYPE_MAIN = 0
# context=8 (DISCARD、手札からの破棄) のみを計測対象にする。
# context=29 (DISCARD_CARD_OR_ATTACHED_CARD) は場に装着済みのカードの破棄も含むため、
# 「手札のエネルギーをコストとして自分で捨てた回数」とは意味が異なる指標になる。
# なお_hand_card()はarea!=AREA_HANDのoptionを問答無用でNone扱いするため、29を含めても
# 装着済み破棄は捕捉できずdiscarded=[]のまま握りつぶされてしまう（黙って取りこぼす）。
# 意図的に29を除外することで、この取りこぼしを構造的に無くす。
DISCARD_CONTEXTS = frozenset({8})


def find_player_index(data: dict, my_name: str = "Kagura_UT") -> int:
    """自分のプレイヤーindexを返す。試合ごとに0/1が入れ替わるため必ず毎試合求めること"""
    for i, agent in enumerate(data["info"]["Agents"]):
        if agent["Name"] == my_name:
            return i
    raise ValueError(f"{my_name} が info.Agents に見つかりません")


def _iter_my_selects(data: dict, my_index: int):
    """自分がACTIVEなステップの (step番号, select, current, 選ばれたインデックス列) を順に返す。

    選択結果は steps[N]['action'] ではなく steps[N+1][my_index]['action'] に入っている
    （1ステップずれ）。この対応を間違えると全く別の選択肢を読むことになる。
    """
    steps = data["steps"]
    for i, step in enumerate(steps):
        me = step[my_index]
        if me.get("status") != "ACTIVE":
            continue
        obs = me.get("observation") or {}
        select = obs.get("select")
        if not select:
            continue
        action = steps[i + 1][my_index].get("action") if i + 1 < len(steps) else None
        yield i, select, obs.get("current") or {}, action or []


def measure_energy_discards(data: dict, my_name: str = "Kagura_UT") -> list:
    """自分の闘エネルギーをコスト等で捨てた場面を列挙する。

    戻り値の各要素:
        step, turn, discarded(捨てたカードIDのリスト), hand_energy(その時点の手札エネ枚数),
        alternatives(エネルギー以外に捨てられた候補のカードIDリスト),
        avoidable(エネルギー以外だけで必要枚数をまかなえたか)
    """
    my_index = find_player_index(data, my_name)
    events = []
    for step_no, select, current, action in _iter_my_selects(data, my_index):
        if select.get("context") not in DISCARD_CONTEXTS:
            continue
        players = current.get("players") or []
        if my_index >= len(players):
            continue
        hand = players[my_index].get("hand") or []
        options = select.get("option") or []

        def _hand_card(option):
            if option.get("type") != OPTION_CARD or option.get("area") != AREA_HAND:
                return None
            if option.get("playerIndex") not in (None, my_index):
                return None
            index = option.get("index")
            if index is None or index >= len(hand):
                return None
            return hand[index]

        discarded = []
        for choice in action:
            if not isinstance(choice, int) or choice >= len(options):
                continue
            card = _hand_card(options[choice])
            if card and card["id"] in ENERGY_IDS:
                discarded.append(card["id"])
        if not discarded:
            continue

        alternatives = []
        for option in options:
            card = _hand_card(option)
            if card and card["id"] not in ENERGY_IDS:
                alternatives.append(card["id"])
        events.append({
            "step": step_no,
            "turn": current.get("turn"),
            "discarded": discarded,
            "hand_energy": sum(1 for c in hand if c and c["id"] in ENERGY_IDS),
            "alternatives": alternatives,
            "avoidable": len(alternatives) >= (select.get("minCount") or 1),
        })
    return events


def measure_attach_targets(data: dict, my_name: str = "Kagura_UT") -> dict:
    """エネルギーの装着先（バトル場 / ベンチ）を集計する。

    戻り値のキー:
        to_active, to_bench, to_bench_while_active_zero
    """
    my_index = find_player_index(data, my_name)
    stat = defaultdict(int)
    for _step_no, select, current, action in _iter_my_selects(data, my_index):
        if select.get("type") != SELECT_TYPE_MAIN:
            continue
        players = current.get("players") or []
        if my_index >= len(players):
            continue
        me = players[my_index]
        hand = me.get("hand") or []
        active_list = me.get("active") or []
        active = active_list[0] if active_list else None
        options = select.get("option") or []
        for choice in action:
            if not isinstance(choice, int) or choice >= len(options):
                continue
            option = options[choice]
            if option.get("type") != OPTION_ATTACH or option.get("area") != AREA_HAND:
                continue
            index = option.get("index")
            if index is None or index >= len(hand):
                continue
            card = hand[index]
            if not card or card["id"] not in ENERGY_IDS:
                continue
            if option.get("inPlayArea") == AREA_ACTIVE:
                stat["to_active"] += 1
            else:
                stat["to_bench"] += 1
                if active is not None and not (active.get("energies") or []):
                    stat["to_bench_while_active_zero"] += 1
    return {
        "to_active": stat["to_active"],
        "to_bench": stat["to_bench"],
        "to_bench_while_active_zero": stat["to_bench_while_active_zero"],
    }


def main(paths: list) -> None:
    total_discard = 0
    avoidable_discard = 0
    attach = defaultdict(int)
    for path in paths:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        events = measure_energy_discards(data)
        for event in events:
            total_discard += len(event["discarded"])
            if event["avoidable"]:
                avoidable_discard += 1
                print(f"{path} step{event['step']} t{event['turn']} "
                      f"回避可能なエネルギー破棄 手札エネ={event['hand_energy']} "
                      f"代替候補={event['alternatives']}")
        for key, value in measure_attach_targets(data).items():
            attach[key] += value
    print(f"\n対象: {len(paths)} 試合")
    print(f"エネルギー破棄: 計{total_discard}枚 / うち回避可能な場面 {avoidable_discard} 件")
    print(f"エネルギー装着: バトル場 {attach['to_active']} 回 / ベンチ {attach['to_bench']} 回")
    print(f"  うちバトル場が0エネなのにベンチへ: {attach['to_bench_while_active_zero']} 回")


if __name__ == "__main__":
    main(sys.argv[1:])
```

- [ ] **Step 4: テストを実行して通ることを確認**

```bash
uv run pytest tests/test_analyze_lucario_energy_metrics.py -v
```

期待：全9件（parametrize込み）PASS。

- [ ] **Step 5: 実ログで動作確認し、修正前の実測値を再現する**

ver24+ver25 の40件を明示して実行する（ワイルドカードを使うと他バッチのログが混ざり、ベースライン値と一致しなくなる）。

```bash
IDS="88583911 88584371 88584854 88585358 88585443 88585842 88586348 88586840 88587329 88587842 \
88588334 88588814 88589306 88589804 88590282 88590772 88591250 88591718 88592295 88592674 \
88601539 88602034 88602140 88602501 88602962 88603452 88603939 88604421 88604905 88605377 \
88605873 88606319 88606821 88607286 88607767 88608256 88608386 88608751 88609232 88609709"
FILES=""
for id in $IDS; do FILES="$FILES data/battle_logs/$id.json"; done
uv run python scripts/analyze_lucario_energy_metrics.py $FILES | tail -6
```

**期待される出力（修正前のベースライン。これと一致しなければ計測ロジックが誤っている）:**
- 回避可能な場面: **16 件**
- バトル場が0エネなのにベンチへ: **30 回**
- エネルギー装着: バトル場 129 回 / ベンチ 56 回

一致しない場合は、スクリプトを直すこと。**期待値のほうを書き換えてはいけない。**

- [ ] **Step 6: 全テストを実行**

```bash
uv run pytest
```

期待：全件 PASS。

- [ ] **Step 7: コミット**

```bash
git add scripts/analyze_lucario_energy_metrics.py tests/test_analyze_lucario_energy_metrics.py
git commit -m "feat(scripts): ルカリオexのエネルギー運用プロセス指標の計測スクリプトを追加

修正前ベースライン（ver24+ver25の40戦）:
回避可能なエネルギー自己破棄16件 / バトル場0エネなのにベンチ装着30回。
2026-07-28の修正時に測定手順が残っておらずベースラインを測り直す羽目に
なったため、今回は最初から常設する。"
```

---

## Task 4: 提出用ノートブックを再生成する

**Files:**
- Generate: `notebooks/submissions/lucario_agent_submission.ipynb`（`scripts/build_lucario_submission_notebook.py` が生成する。出力先は同スクリプト20行目の `DST` 定数）
  - **注意：このファイルは `.gitignore` の `*.ipynb` により意図的に git 追跡対象外です。コミットしないこと。生成後はローカルからユーザーが Kaggle へアップロードします。**

**Interfaces:**
- Consumes: Task 1・Task 2 で修正した `src/lucario_agent/main.py`
- Produces: なし

- [ ] **Step 1: ノートブックを再生成する**

引数は不要（`main()` が `DST` へ書き出す）。

```bash
uv run python scripts/build_lucario_submission_notebook.py
```

期待：`wrote /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/notebooks/submissions/lucario_agent_submission.ipynb` と表示される。

- [ ] **Step 2: 生成物に今回の修正が反映されているか確認する**

```bash
grep -c "バトル場が0エネだと" notebooks/submissions/lucario_agent_submission.ipynb
grep -c "ちょうど必要な枚数" notebooks/submissions/lucario_agent_submission.ipynb
```

期待：どちらも `1` 以上。`0` の場合は、Task 1・Task 2 のコメント文言が計画どおりに入っているかを `src/lucario_agent/main.py` で確認する（notebookはソースを結合して埋め込むだけなので、0 ならソース側に文言が無い）。

- [ ] **Step 4: ノートブック関連のテストを実行**

```bash
uv run pytest tests/test_build_lucario_submission_notebook.py tests/test_build_lucario_submission_main.py -v
```

期待：全件 PASS。

- [ ] **Step 5: 全テストを実行**

```bash
uv run pytest
```

期待：全件 PASS。

- [ ] **Step 6: ノートブックファイルの確認**

ノートブックは `.gitignore` により自動的に git 追跡対象外です。コミットは不要。生成されたファイルをローカルで確認し、Kaggle へのアップロードに備えます。

```bash
ls -la notebooks/submissions/lucario_agent_submission.ipynb
```

期待：生成したファイルがローカルに存在すること。

---

## 完了後の検証（プロセス指標）

**次回バッチのログが貯まったら、以下を `scripts/analyze_lucario_energy_metrics.py` で測定する。勝率・LBスコアでは判定しない。**

| 指標 | 修正前（ver24+ver25 40戦） | 期待 |
|---|---|---|
| 回避可能なエネルギー自己破棄 | **16 件** | **0 件** |
| バトル場0エネなのにベンチへ装着 | **30 回** | **大幅減**（0にはならない。攻撃プラン成立時は意図的にベンチを選ぶため） |
| エネルギー装着のバトル場比率 | 129/185 = 70% | 上昇 |

**注意：** 指標1は「0件」を期待するが、選択肢がエネルギーしか無い場面（ルナサイクルのコスト支払い等）は `avoidable=False` として除外済みなので、この分は 0 件のカウントに含まれない。1件でも出た場合は、その場面の代替候補を確認してから「修正失敗」と判断すること。

**参考として同時に見る（判定には使わない）:** 自分のターンでバトル場のエネルギーが2個未満だった割合（修正前：負け試合で94.2%、勝ち試合で68.5%）。

**【2026-07-29最終レビュー指摘5】副作用側の指標（次バッチで併せて数える）：**

現在のプロセス指標は「狙った挙動が消えたか」しか見ていない。しかし今回の修正は、DISCARD時に
捨てる対象をエネルギーから Boss's Orders / Lillie's Determination（-50）へ、装着先をベンチの
アタッカーから退却時にそのエネルギーを失うバトル場へ、それぞれ**付け替える**ものでもある。
現状の指標だけでは、これが改善なのか単に問題を移動させただけなのかを区別できない。
次バッチで以下も併せて数えること：

- **サポート系カード（Boss's Orders / Lillie's Determination）をコストで自己破棄した回数**
  （今回の修正でエネルギーの代わりに捨てられるようになっていないか。増えていた場合、
  Task 1のDISCARD序列変更が別の問題を作っただけの可能性がある）
- **バトル場に装着した次のターンに、退却でそのエネルギーを失った回数**
  （Task 2の救済ボーナスが無駄撃ちになっていないか。バトル場へ救済したエネルギーが
  技を撃つ前に退却で失われているなら、救済の効果が薄い可能性がある）

## 本計画で扱わない事項（次回以降の判断材料）

1. **原因3：オーガポンexのデッドロック** — 技「ぶちやぶる」は闘エネ3個が必要、にげるコストは1。0エネだと攻撃も退却もできない。40戦でバトル場に95ターン居座り（最多）、うち73%が0エネ、攻撃はわずか18回。本計画の修正で緩和されるかを実測してから対処を判断する。
2. **デッキ構成変更（オーガポンex → マクノシタ2／ハリテヤマ2）** — ハリテヤマの「ワイルドプレス」も闘エネ3個要求・にげるコスト3なので、**エネルギー事故の解決にはならない**。ただし特性「どすこいキャッチャー」（手札から出して進化させたとき、相手のベンチポケモンをバトル場に引きずり出す）はテンポ面で価値が高い。原因1・2の効果測定後に別途検討する。
3. **`UltraBallPolicy` 側でのコスト回避** — 順位付け（スコアの大小）による温存では、選択肢が高価値な札しかない場合に「捨てない」を選べない。恒久対策は「コスト候補が全部高価値ならハイパーボール自体を撃たない」判定だが、本計画のスコア修正で実測16件が0件になるかを先に確認する。
4. **フーディン（Alakazam）対策** — 40戦中8戦で2勝6敗。技「パワフルハンド」は相手の手札枚数×20のダメカン直接配置で、HP・どうぐ・特性による無効化を全て貫通する。4回目の再現だが未着手。
