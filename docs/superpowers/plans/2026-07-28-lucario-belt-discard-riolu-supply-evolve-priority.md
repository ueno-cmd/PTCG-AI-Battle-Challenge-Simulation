# ルカリオex：Maximum Belt温存・Riolu供給ガード緩和・進化優先度 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ver22/ver23の実測40戦で確定した3つの損失（ACE SPECの自己破棄・進化元の供給停止・Judgeとの同点による進化機会損失）を、`src/lucario_agent/main.py`のスコアリング3箇所の局所修正で解消する。

**Architecture:** 3件とも既存のスコアリング関数への局所パッチで、新規クラス・新規ファイルは作らない。それぞれ独立しており相互依存はないが、いずれも「スコアの相対順位」を変える変更なので、値そのものではなく**他の選択肢との大小関係**を検証するテストを添える。構造的リファクタ（スコア階層の定数化・`EvolvePolicy`のABC化）は今回スコープ外。

**Tech Stack:** Python 3 / pytest / uv。ゲームAPIは`data/competition/sample_submission/cg/api.py`（`cg.sim`はmacOSで動かないため実機シミュレーションは不可）。

## Global Constraints

- コードコメントは**日本語**で書く（変数名・関数名は英語でOK）
- 実装は`git worktree`ではなく**通常のfeatureブランチ**で行う（ユーザー方針）
  - ブランチ名: `feature/lucario-belt-discard-riolu-supply-evolve-priority`
- **既存の挙動を変えてよいのは本計画に明記された3箇所のみ。** それ以外のスコア値には触れないこと
- テストは`uv run pytest`で実行する。**リポジトリ全体のテストが全件PASSすること**を各タスクの完了条件とする
  - 本計画着手時点のベースライン: 全体で**738件PASS**（2026-07-26時点の記録。着手時に`uv run pytest -q`で実際の件数を確認し、それを基準にすること）
- カードID定数は`src/lucario_agent/constants.py`のものを使い、**数値リテラルを直接書かない**
- **本計画の修正は実測ログでの勝率検証ができない**（2026-07-28の検証で、20戦バッチでは勝率差を検出できないと実証済み。`docs/analyses/20260728-lucario-ver23-noise-verification.md`）。
  検証は「プロセス指標」＝**その挙動が実際に消えたか**で行う（Task 5参照）

## 背景：なぜこの3件なのか

ver22（20戦）とver23（20戦、ver22からロジック無変更で再提出）の計40戦を実測解析した結果に基づく。
デッキ60枚は40件すべて完全一致を確認済み。詳細は以下の2ドキュメント。

- `docs/analyses/20260728-lucario-ver22-maximum-belt-20-games.md`
- `docs/analyses/20260728-lucario-ver23-noise-verification.md`

**重要な前提として、「進化できたのに進化しなかった」ケースは40戦で0件だった。**
進化の選択肢が提示された49ターンは100%進化しており、進化のスコアリング自体は正常に機能している。
今回修正するのは、進化そのものではなく**進化を支える供給側**と**潜在的な同点リスク**である。

| # | 修正対象 | 実測された損失 |
|---|---|---|
| A | ハイパーボールのコストでMaximum Beltを捨てる | 40戦中**3件**（`88184798` t1、`88186950` t1、`88168475` step10） |
| B | Riolu供給ガードが進化元を枯らす | 手札にMega Lucario exがあるのに場にRioluが0体のターンが**25回**。うちPLAY Rioluの選択肢が出ていたのに出さなかったのが**2回**（`88166297` turn12/turn14、いずれも場にMega Lucario ex 2体・ベンチ4/5で空きあり） |
| C | Judge(9000)とEVOLVE(9000+エネ数)の同点 | 40戦での実害は**0件**。ただし構造として実在し、進化元のエネルギーが0個のとき完全同点になる |

デッキ枚数（`decks/lucario_20260621.py`）: Riolu×4、Mega Lucario ex×3、**Maximum Belt×1（ACE SPEC）**、Ultra Ball×4、Judge×3。

---

## File Structure

| ファイル | 役割 | 本計画での扱い |
|---|---|---|
| `src/lucario_agent/main.py` | エージェント本体。全スコアリングロジック（620行） | **3箇所を修正**（DISCARD分岐・PLAY POKEMON分岐・EVOLVE分岐） |
| `src/lucario_agent/constants.py` | カードID定数 | 変更なし（`Maximum_Belt`/`Riolu`/`Mega_Lucario_ex`は定義済み） |
| `tests/test_lucario_agent.py` | エージェントのユニットテスト | **テストを追加**（既存テストは変更しない） |
| `tests/conftest.py` | `make_pokemon` / `make_player_state`ヘルパー | 変更なし |
| `notebooks/submissions/lucario_agent_submission.ipynb` | Kaggle提出用notebook（ビルド成果物、gitignore対象） | Task 4で再生成 |

`main.py`は620行と大きいが、既存の構造（`match/case`＋`TrainerCardPolicy`の登録辞書）が整理されており、
今回の3箇所はいずれも独立した分岐なので**ファイル分割は行わない**。

---

### Task 1: Maximum BeltをDISCARDコンテキストで温存する

**Files:**
- Modify: `src/lucario_agent/main.py:236-248`（`_score_card_option`の`case SelectContext.DISCARD:`）
- Test: `tests/test_lucario_agent.py`（既存の`class TestDiscardContext`にテストを追加）

**Interfaces:**
- Consumes: `lm.Maximum_Belt`（`src/lucario_agent/constants.py`で定義済み、値は1158）
- Produces: なし（他タスクは本タスクの成果に依存しない）

**背景（実装者向け）:**
`SelectContext.DISCARD`は「手札から何を捨てるか」を選ぶ場面。ハイパーボール（手札2枚をトラッシュして
ポケモンをサーチ）のコスト選択などで呼ばれる。**このコンテキストではスコアが高いほど「捨ててよい」**という
向きになっている（予備の基本闘エネルギー=50、キーポケモン=-100、既定=10）。

Maximum Beltは現状どの分岐にも該当せず**既定の10点**に落ちており、「捨ててよいカード」として扱われている。
デッキに1枚しかないACE SPECで、トラッシュからの回収手段も無いため、捨てられると復帰できない。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`class TestDiscardContext`（`test_protects_key_pokemon`の後ろ）に以下2件を追加する。

```python
    def test_protects_maximum_belt(self):
        """Maximum BeltはACE SPEC（デッキに1枚のみ・トラッシュから回収不可）のため、
        ハイパーボールのコスト等で捨てられないよう強く温存する。
        実測：ver22/ver23の40戦で3件、手札に来たMaximum Beltを自己破棄していた"""
        belt = Card(id=lm.Maximum_Belt, serial=1, playerIndex=0)
        obs = self._obs(belt)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == -150

    def test_maximum_belt_protected_more_strongly_than_key_pokemon(self):
        """代替不可のACE SPECは、複数枚あるキーポケモン(Riolu×4等)より強く温存する。
        値そのものではなく相対順位を検証する（値だけのテストは順位の逆転を検出できない）"""
        def _score(card_id):
            card = Card(id=card_id, serial=1, playerIndex=0)
            return lm._score_card_option(
                self._obs(card),
                Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
                context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
                my_state=make_player_state(),
                field_counts=defaultdict(int), hand_counts=defaultdict(int),
                discard_counts=defaultdict(int), attacker1=False,
                current_plan=lm.AttackPlan(), ability_used_flag=False,
            )

        assert _score(lm.Maximum_Belt) < _score(lm.Riolu)
        assert _score(lm.Maximum_Belt) < _score(lm.Mega_Lucario_ex)
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestDiscardContext -v`

Expected: `test_protects_maximum_belt`が**FAIL**（`assert 10 == -150`）、
`test_maximum_belt_protected_more_strongly_than_key_pokemon`も**FAIL**（`assert 10 < -100`）。
既存の`TestDiscardContext`のテストは引き続きPASSすること。

- [ ] **Step 3: 最小限の実装を書く**

`src/lucario_agent/main.py`の`case SelectContext.DISCARD:`ブロック内、
`Rock_Fighting_Energy`の分岐と`if card.id in (Riolu, ...)`の分岐の**間**に以下を挿入する。

```python
            if card.id == Maximum_Belt:
                # ACE SPECのためデッキに1枚のみ・トラッシュからの回収手段も無く、
                # 一度捨てると復帰不可。複数枚あるキーポケモン(-100)より強く温存する。
                # 実測：ver22/ver23の40戦で3件、ハイパーボールのコスト等として
                # 自己破棄していた（88184798 t1 / 88186950 t1 / 88168475 step10）
                return -150
```

挿入後、該当ブロックは以下の並びになる（前後の既存コードは変更しない）:

```python
        case SelectContext.DISCARD:
            if o.playerIndex != my_index:
                return 0
            if card.id == Basic_Fighting_Energy:
                return 50 if hand_counts[Basic_Fighting_Energy] >= 2 else -20
            if card.id == Rock_Fighting_Energy:
                # 夜のタンカで回収不可・デッキ内4枚のみのため、手札枚数によらず常時温存
                return -20
            if card.id == Maximum_Belt:
                # （上記のコメント）
                return -150
            if card.id in (Riolu, Mega_Lucario_ex, Solrock, Lunatone, Ogerpon_ex, Judge):
                return -100
            if card.id in (Boss_Orders, Lillie_Determination):
                return -50
            return 10
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestDiscardContext -v`
Expected: 全件PASS

- [ ] **Step 5: リポジトリ全体のテストを実行する**

Run: `uv run pytest -q`
Expected: 着手時に確認したベースライン件数と同数がPASS、新規テスト2件が加算されている。失敗0件。

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix(lucario): Maximum BeltをDISCARDコンテキストで温存する

ACE SPEC(デッキ1枚・回収不可)が既定スコア10点で「捨ててよいカード」
扱いになっており、ハイパーボールのコストとして自己破棄していた。
ver22/ver23の実測40戦で3件確認(88184798/88186950/88168475)。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: EVOLVEをJudgeより優先させる（同点の解消）

**Files:**
- Modify: `src/lucario_agent/main.py:531-533`（`_score_option`の`case OptionType.EVOLVE:`）
- Test: `tests/test_lucario_agent.py`（新規クラス`TestEvolvePriorityOverJudge`を追加）

**Interfaces:**
- Consumes: `lm.JudgePolicy`（`main.py:370-383`で定義済み）、`lm.PlayScoringContext`（`main.py`で定義済み。
  フィールドは`obs, o, my_index, current_plan, can_attack, state, my_state, hand_counts, field_counts, stadium_id, attacker1, rng, op_hand_count`）
- Produces: なし

**背景（実装者向け）:**
現状のスコアは以下の通りで、**進化元のエネルギーが0個のとき完全同点になる**。

```
EVOLVE = 9000 + len(pokemon.energies)     # main.py:533
Judge  = 9000                             # main.py:379（相手の手札が10枚以上のとき）
```

同点時は`sorted(..., reverse=True)`（`main.py:611`）がPythonの安定ソートであるため、
**選択肢の提示順が先の方が勝つ**。提示順はゲームエンジン（`libcg.so`、ソース非公開）側の都合で決まるため、
コードからは勝者を確定できない。Judgeが先に選ばれると**お互いの手札を山札に戻して4枚引き直す**ため、
手札のMega Lucario exが山札に消えて進化機会を失う。

**重要な設計判断:** MAINでは1ターンに複数回行動できる（実ログで、他の行動を2回挟んでから同一ターン内に
進化した例を確認済み：`88170079` turn11で step112 PLAY → step114 PLAY → step115 EVOLVE）。
したがって**先に進化してからJudgeを撃てば両方成立する**。これはトレードオフではなく**順序の問題**であり、
EVOLVEを常にJudgeより上にするのが厳密に有利。Judgeが持つAlakazam対策（相手の手札を削る）の価値は損なわれない。

**値の選定理由:** 9000と10000の間に他のスコアが存在しないことを確認済み
（10000=未登録トレーナー/Gravity Mountain、9000=Judge、8800/6000=Boss's Orders、8500=ルナサイクル、
8000〜8811=エネルギー装着）。9100を採ればJudgeを確実に上回り、かつ上位の分岐には影響しない。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の末尾に新規クラスを追加する。

```python
class TestEvolvePriorityOverJudge:
    """EVOLVEとJudgeが同点にならないことの検証。
    同点だと選択肢の提示順（エンジン依存で制御不能）次第でJudgeが先に選ばれ、
    手札のMega Lucario exが山札に戻って進化機会を失う"""

    def _evolve_score(self, energies):
        from unittest.mock import MagicMock
        from cg.api import Option, OptionType, SelectContext

        riolu = make_pokemon(id=lm.Riolu, hp=80, energies=energies)
        my_state = make_player_state(bench=[riolu], prize_count=6)
        op_state = make_player_state(prize_count=6)
        obs = MagicMock()
        obs.current.players = [my_state, op_state]
        option = Option(type=OptionType.EVOLVE, inPlayArea=lm.AreaType.BENCH, inPlayIndex=0)
        return lm._score_option(
            obs=obs, o=option, context=SelectContext.MAIN, my_index=0,
            state=_make_state(), my_state=my_state, op_state=op_state,
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int),
            attacker1=False, current_plan=lm.AttackPlan(), can_attack=True,
            stadium_id=0, ability_used_flag=False,
        )

    def _judge_top_priority_score(self):
        """相手の手札が閾値以上でJudgeが最優先になったときのスコア"""
        from unittest.mock import MagicMock
        from cg.api import Option, OptionType

        obs = MagicMock()
        my_state = make_player_state(prize_count=6)
        ctx = lm.PlayScoringContext(
            obs=obs, o=Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=True,
            state=_make_state(), my_state=my_state,
            hand_counts=defaultdict(int), field_counts=defaultdict(int),
            stadium_id=0, attacker1=False, rng=None,
            op_hand_count=lm.JudgePolicy.OPPONENT_HAND_THRESHOLD,
        )
        return lm.JudgePolicy().play_score(ctx)

    def test_evolve_beats_judge_even_with_zero_energy(self):
        """進化元のエネルギーが0個でもJudgeを上回る（旧実装ではここが完全同点だった）"""
        assert self._evolve_score([]) > self._judge_top_priority_score()

    def test_evolve_score_still_increases_with_energy(self):
        """エネルギー数によって優先度が上がる既存の性質は維持する
        （複数の進化元がいる時、投資済みの個体を優先する意図）"""
        assert self._evolve_score([6, 6]) > self._evolve_score([6]) > self._evolve_score([])

    def test_evolve_stays_below_pokemon_deployment(self):
        """ポケモンの展開(20000)より下位である既存の順位は維持する"""
        assert self._evolve_score([6, 6, 6]) < 20000
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestEvolvePriorityOverJudge -v`

Expected: `test_evolve_beats_judge_even_with_zero_energy`が**FAIL**（`assert 9000 > 9000`）。
他2件はPASSする（既存の性質を確認するテストのため）。

- [ ] **Step 3: 最小限の実装を書く**

`src/lucario_agent/main.py`の`case OptionType.EVOLVE:`を以下に置き換える。

```python
        case OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            # 9100始まり：Judge(9000、相手の手札が10枚以上で最優先)と同点にしないため。
            # MAINは1ターンに複数回行動できるので、先に進化してからJudgeを撃てば両方成立する。
            # 同点だと選択肢の提示順（エンジン依存で制御不能）次第でJudgeが先に選ばれ、
            # 手札のMega Lucario exが山札に戻って進化機会を失う。
            # 9000〜10000の間に他のスコアは存在しないため上位分岐への影響はない。
            # （2026-07-28の静的監査で発見。実測40戦での実害は0件だが構造として実在）
            return 9100 + len(pokemon.energies)
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestEvolvePriorityOverJudge -v`
Expected: 3件すべてPASS

- [ ] **Step 5: リポジトリ全体のテストを実行する**

Run: `uv run pytest -q`

Expected: 失敗0件。**EVOLVEのスコア値をハードコードしている既存テストがあれば失敗する可能性がある。**
その場合は、失敗したテストが「9000という値そのもの」を検証しているのか
「他の選択肢との相対順位」を検証しているのかを確認し、**前者なら期待値を9100系に更新**、
後者なら実装側が誤っている可能性があるので**立ち止まって報告**すること。

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix(lucario): EVOLVEをJudgeより優先させ同点を解消する

EVOLVE(9000+エネ数)とJudge(9000)が進化元のエネルギー0個時に完全同点で、
選択肢の提示順次第でJudgeが先に選ばれ手札のMega Lucario exが山札に
戻るリスクがあった。MAINは1ターンに複数回行動できるため、先に進化して
からJudgeを撃てば両方成立する。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Riolu供給ガードを緩和する（進化元の枯渇を防ぐ）

**Files:**
- Modify: `src/lucario_agent/main.py:451-452`（`_score_play_option`のPOKEMON分岐内、Rioluの条件）
- Test: `tests/test_lucario_agent.py`（新規クラス`TestRiolusSupplyGate`を追加）

**Interfaces:**
- Consumes: `lm.Riolu`, `lm.Mega_Lucario_ex`（定数）、既存テストヘルパー`_obs_with_hand` / `_hand_counts`
  （`tests/test_lucario_agent.py`内で定義済み。使用例は`class TestDeckSafetyGate`を参照）
- Produces: なし

**背景（実装者向け）:**
現状の条件は以下。

```python
        if card.id == Riolu:
            return -1 if field_counts[Riolu] + field_counts[Mega_Lucario_ex] >= 2 else 20000
```

意図は「ベンチをRioluで埋め尽くさない」ことだが、**進化後のMega Lucario exも頭数に数えている**ため、
Mega Lucario exが2体並んだ時点で**3体目以降のRioluを永久に出せなくなる**。
Mega Lucario exは進化元を必要とし続ける（KOされたら次が要る）のに、供給が止まる。

実測（40戦）:
- 手札にMega Lucario exがあるのに場にRioluが1体もいないターンが**25回**
- うち、PLAY Rioluの選択肢が提示されていたのに出さなかったのが**2回**
  （`88166297` turn12 step102 / turn14 step117。いずれも場にMega Lucario ex 2体、ベンチ4/5で空きあり）

**修正方針（最小変更）:** 「場に進化元(Riolu)が1体もいない時は、Mega Lucario exが何体いても展開を許可する」
という例外を1つ足すだけにする。Rioluが1体以上いる場合の挙動は**一切変更しない**ため、
本来の「ベンチを埋め尽くさない」意図は保たれる。

（Mega Lucario exを頭数から完全に外す案も検討したが、Riolu 2体＋Mega 2体のような
過剰展開を新たに許してしまうため見送った。Mega Lucario exはKO時にサイドを3枚献上するので、
体数を増やす方向の変更は別途慎重な検討が必要＝本計画のスコープ外。）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の末尾に新規クラスを追加する。

```python
class TestRiolusSupplyGate:
    """Rioluの展開ガード。進化元が枯れると手札のMega Lucario exが腐るため、
    場にRioluが0体の時は無条件に展開を許可する"""

    def _score(self, field_riolu, field_mega):
        card = Card(id=lm.Riolu, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=30)
        o = Option(type=OptionType.PLAY, index=0)
        field_counts = defaultdict(int, {lm.Riolu: field_riolu, lm.Mega_Lucario_ex: field_mega})
        return lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=field_counts,
            stadium_id=0,
        )

    def test_allows_deployment_when_no_riolu_in_play(self):
        """場にRioluが0体なら、Mega Lucario exが2体いても展開を許可する。
        実測：88166297 turn12/turn14で、Mega 2体・ベンチ空きありの状況で
        Rioluの選択肢が出ていたのに出さず、手札のMegaが腐っていた"""
        assert self._score(field_riolu=0, field_mega=2) == 20000

    def test_allows_deployment_when_no_riolu_and_three_mega(self):
        """Mega Lucario exが3体（デッキ上の最大枚数）でも同様に許可する"""
        assert self._score(field_riolu=0, field_mega=3) == 20000

    def test_still_suppresses_when_riolu_already_in_play_at_capacity(self):
        """Rioluが1体いてMegaが1体なら、従来通り抑制する（既存挙動の維持）"""
        assert self._score(field_riolu=1, field_mega=1) == -1

    def test_still_suppresses_with_two_riolu(self):
        """Rioluが2体いれば従来通り抑制する（既存挙動の維持）"""
        assert self._score(field_riolu=2, field_mega=0) == -1

    def test_still_allows_second_riolu(self):
        """Rioluが1体だけなら2体目は従来通り許可する（既存挙動の維持）"""
        assert self._score(field_riolu=1, field_mega=0) == 20000
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestRiolusSupplyGate -v`

Expected: `test_allows_deployment_when_no_riolu_in_play`と
`test_allows_deployment_when_no_riolu_and_three_mega`が**FAIL**（`assert -1 == 20000`）。
残り3件はPASS（既存挙動を固定するテストのため）。

- [ ] **Step 3: 最小限の実装を書く**

`src/lucario_agent/main.py`のRiolu分岐を以下に置き換える。

```python
        if card.id == Riolu:
            # 場に進化元(Riolu)が1体もいない時は、Mega Lucario exが何体いても展開を許可する。
            # 旧条件(Riolu+Mega>=2で一律-1)では、Mega Lucario exが2体並んだ時点で3体目以降の
            # Rioluを永久に出せず、手札のMega Lucario exが腐っていた。
            # 実測：ver22/ver23の40戦で、手札にMegaがあるのに場にRioluが0体のターンが25回。
            # うちPLAY Rioluの選択肢が出ていたのに出さなかったのが2回
            # （88166297 turn12 step102 / turn14 step117、いずれもベンチ4/5で空きあり）
            if field_counts[Riolu] == 0:
                return 20000
            return -1 if field_counts[Riolu] + field_counts[Mega_Lucario_ex] >= 2 else 20000
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestRiolusSupplyGate -v`
Expected: 5件すべてPASS

- [ ] **Step 5: リポジトリ全体のテストを実行する**

Run: `uv run pytest -q`
Expected: 失敗0件。既存のRiolu展開に関するテストが失敗した場合は、
そのテストが「場にRioluが0体」の条件を含んでいるか確認し、
**含んでいるなら期待値を更新（本修正が意図した変更）、含んでいないなら実装が誤っているので立ち止まって報告**すること。

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix(lucario): 場にRioluが0体なら展開ガードを免除する

Riolu+Mega Lucario ex>=2で一律に展開を止めていたため、Megaが2体
並ぶと3体目以降の進化元を永久に出せず手札のMegaが腐っていた。
ver22/ver23の実測40戦で、手札にMegaがあるのに場にRioluが0体の
ターンが25回、選択肢が出ていたのに出さなかったのが2回。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 提出用notebookの再生成とドキュメント整備

**Files:**
- Regenerate: `notebooks/submissions/lucario_agent_submission.ipynb`（gitignore対象のビルド成果物）
- Create: `docs/implementations/20260728-lucario-belt-discard-riolu-supply-evolve-priority.md`

**Interfaces:**
- Consumes: Task 1〜3の実装（`src/lucario_agent/main.py`）
- Produces: なし

- [ ] **Step 1: 提出用notebookを再生成する**

Run: `uv run python scripts/build_lucario_submission_notebook.py`

- [ ] **Step 2: 生成物に今回の修正が含まれることを確認する**

Run:
```bash
grep -c "9100 + len(pokemon.energies)" notebooks/submissions/lucario_agent_submission.ipynb
grep -c "field_counts\[Riolu\] == 0" notebooks/submissions/lucario_agent_submission.ipynb
grep -c "return -150" notebooks/submissions/lucario_agent_submission.ipynb
```

Expected: 3つとも**1以上**を返す。0を返した場合はビルドスクリプトが
`main.py`の変更を取り込めていないので、立ち止まって報告すること。

- [ ] **Step 3: notebookのビルドテストを実行する**

Run: `uv run pytest tests/test_build_lucario_submission_main.py tests/test_build_lucario_submission_notebook.py -v`
Expected: 全件PASS

- [ ] **Step 4: 実装サマリーを書く**

`docs/implementations/20260728-lucario-belt-discard-riolu-supply-evolve-priority.md`を作成し、
以下を日本語で記載する。

- 対象: Task 1〜3の3件（各々の修正前後のコードと、根拠になった実測データ）
- 変更ファイルとコミットハッシュ
- テスト結果（着手時のベースライン件数 → 完了時の件数）
- **検証方法（重要）**: 勝率では検証できないため、次バッチのログで以下のプロセス指標を数えること
  1. Maximum Beltがハイパーボールのコスト等で自己破棄された回数（**期待値: 0件**。ver22/ver23は40戦で3件）
  2. 手札にMega Lucario exがあるのに場にRioluが0体のターン数（**期待値: 25回/40戦より減少**）
  3. Maximum Beltの装着率（ver22: 30%、ver23: 45% → 上昇するはず）
- 本計画でスコープ外にした項目（下記「スコープ外」節をそのまま転記）

- [ ] **Step 5: コミット**

```bash
git add docs/implementations/20260728-lucario-belt-discard-riolu-supply-evolve-priority.md
git commit -m "docs(lucario): Belt温存・Riolu供給・進化優先度の実装サマリーを追加

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## スコープ外（意図的に今回は着手しない）

以下は2026-07-28の静的監査・実ログ検証で判明しているが、本計画には含めない。
実装サマリーに転記し、バックログとして残すこと。

1. **Mega Lucario exの体数上限ガードが無い** — ドラパルトexには「場に2体なら-1」があるが、
   ルカリオexには無く無制限に並ぶ。Mega Lucario exはKO時にサイドを**3枚**献上するため、
   非exデッキ（Alakazam軸等、1体倒しても1枚）相手のサイド枚数の非対称性に直結する。
   ユーザー判断で今回は見送り（影響が大きく慎重な設計が必要）
2. **`UltraBallPolicy.already_found`の数え方** — 場と手札のRiolu＋Mega＋Ogerponの合計が3以上で
   スコアを100点に落とす（`main.py:358-367`）。**Mega Lucario exを1枚も持っていなくても**、
   Riolu 2体＋Ogerpon 1体がベンチにいるだけでハイパーボールが実質封印される。
   進化ライン別に分離集計する案があるが、ハイパーボールの使用が増えて手札2枚コストで
   事故る可能性があるため要検討
3. **スコア階層の定数化** — 9000/10000/20000等のマジックナンバーが散在しており、
   今回のJudge同点はその帰結。`PRIORITY_ABILITY`/`PRIORITY_EVOLVE`等の定数化と、
   同点が生じないことを保証するテストの追加が恒久対策
4. **`_score_card_option`のスコアリング漏れ** — `SETUP_BENCH_POKEMON(2)` / `EVOLVES_FROM(18)` /
   `EVOLVES_TO(19)` / `TO_BENCH(5)` / `TO_FIELD(6)`のケースが無く`case _: return 0`に落ちる
   （既知の`ATTACH_TO(22)`漏れと同種）。現デッキで毎試合通るのは`SETUP_BENCH_POKEMON`のみで、
   ゲーム開始時のベンチ選択が手札順依存になっている
5. **`_score_play_option`の山札温存ゲートの位置** — `main.py:446`の`return -1`が
   ポケモン分岐より**上**にある既知の危険形。現状は`_deck_consumption`がポケモンに`None`を返すため
   無害だが、**将来ここに進化系トレーナー（ふしぎなアメ等）を足すと即座に踏む**
6. **`Hero_Cape`定数のデッドコード化** — `src/lucario_agent/constants.py:9`。
   デッキから外れており参照はゼロ。削除可否は未判断
7. **`get_card`が`PRE_EVOLUTION(10)`等で`None`を返す** — `main.py:102-103`。
   EVOLVEブランチが`None.energies`で例外化する理論的リスク（実測では未発生）
8. **Air Balloonのトラッシュコスト温存** — 今回Maximum Beltのみ保護した。
   Air Balloon（2枚採用）も既定10点のままで、同様に捨てられうる。実測での損失は未確認

## 前提の確認（実装前に必ず読むこと）

- **`cg.sim`はmacOSで動かない**ため、実機でのシミュレーション検証はできない。
  修正が実際のゲームエンジン上で意図通り動くかは、Kaggle再提出後の新規バトルログでのみ確認可能
- **選択肢の提示順はエンジン（`libcg.so`、ソース非公開）が決める**ため、同点時にどちらが選ばれるかは
  コードから制御できない。Task 2はこの制御不能性を「同点を作らない」ことで回避する設計
- **メガ進化がターンを終了させる仕様かどうかは資料から確認できていない。**
  Task 2はEVOLVEの相対順位をJudge(9000)に対してのみ変えるもので、
  エネルギー装着(8000〜8811)や攻撃(1000)との順位は**元から**EVOLVEが上なので、
  この不明点によって新たなリスクは生じない。**ただしEVOLVEを10000以上に上げる変更は
  この確認が取れるまで行わないこと**

## Self-Review 結果

- **スコープ網羅**: ユーザーが選択したA（Task 1）・B（Task 3）・C（Task 2）の3項目すべてにタスクが対応。
  選択されなかったD（Mega Lucario exの体数上限）はスコープ外1に記載
- **プレースホルダ**: なし。全ステップに実際のコード・コマンド・期待値を記載済み
- **型・名前の一貫性**: `field_counts`（`defaultdict(int)`）、`hand_counts`、`_obs_with_hand`、
  `_hand_counts`、`make_pokemon`、`make_player_state`、`_make_state`はいずれも
  `tests/test_lucario_agent.py`と`tests/conftest.py`の既存定義に一致。
  `lm.PlayScoringContext`のフィールド名は`main.py:459-463`の実際の呼び出しから転記
