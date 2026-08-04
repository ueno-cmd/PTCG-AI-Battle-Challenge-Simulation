# ルカリオex：オーガポンexの「装着→同ターン退却」ループ解消 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 温存退却の発火条件を「相手のバトル場がex無効化特性を持つとき」に限定し、オーガポンexが「退却のためだけにエネルギーを装着し、同じターンにそれを退却コストで捨てる」ループを断つ。

**Architecture:** 変更は3箇所に閉じる。(1) `combat.py` の `_score_retreat_option` に `op_active_nullifies_ex` 引数を追加し、温存退却の判定を専用ヘルパーへ切り出す。(2) `main.py` の `PlayScoringContext` に同じフラグを通し、`SwitchPolicy` を追従させる（Switchカードは `_score_retreat_option` の戻り値をそのまま発火条件に使う構造のため、片側だけ直すと不整合になる）。(3) `_score_attach_option` のふうせん装着スコアでオーガポンexを最優先にし、既存の同点も解消する。新しい状態計算・新規ファイルは不要。

**Tech Stack:** Python 3.12 / uv / pytest。`cg.api`（Kaggleコンペ提供の型定義。macOSでは実シミュレータが動かないためローカルは単体テストのみ）。

**設計書:** `docs/superpowers/specs/2026-08-04-lucario-ogerpon-retreat-loop-design.md`

## Global Constraints

- **作業種別の明示（CLAUDE.md ルール7）**：Task 1〜2 と Task 4 は **①提出物が変わる作業**。Task 3 は **②提出物が変わらない作業**（計測ツール）。混ぜないこと。
- **コメント・ドキュメントは日本語**（変数名・関数名は英語でよい）。
- **スコア帯の不変条件を破らないこと**：9000〜10000 の帯域は Judge(9000) と EVOLVE(9100+エネ数) のみ。本計画で触るのはどうぐ装着の 7000 番台だけ。
- **既存の呼び出し互換を維持すること**：`_score_retreat_option` は `my_active` / `card_table` を省略した呼び出しが既存テストにある（`tests/test_lucario_agent.py:823-824`）。新規引数もすべてデフォルト値付きで追加する。
- **テスト実行コマンド**：`uv run pytest -q`（全体）、`uv run pytest tests/test_lucario_agent.py::クラス名::メソッド名 -v`（個別）。
- **着手時のテスト件数は 785 件**。Task 4 でこれを下回らないことを確認する。
- **コミットは main 直下で行う**（本リポジトリの既存運用）。push はユーザーが判断する。

---

## File Structure

| ファイル | 責務 | 本計画での扱い |
|---|---|---|
| `src/lucario_agent/combat.py` | 攻撃プラン計算・エネルギー配分スコア・退却スコア | `_score_retreat_option` を修正し、判定ヘルパー `_should_preserve_active` を新設（Task 1） |
| `src/lucario_agent/main.py` | 観測の読み取り・全オプションのスコアリング・`agent()` | RETREAT/PLAY の配線、`PlayScoringContext`、ふうせん装着スコア（Task 1〜2） |
| `tests/test_lucario_agent.py` | ルカリオexエージェントの単体テスト | 既存4件の更新＋新規テスト追加（Task 1〜2） |
| `scripts/analyze_lucario_energy_metrics.py` | 実バトルログからプロセス指標を計測（②） | 効果測定用の指標3つを追加（Task 3） |
| `tests/test_analyze_lucario_energy_metrics.py` | 上記の単体テスト | Task 3 で追加 |

---


## Task 1: 温存退却をex無効化対面限定にし、SwitchPolicyを追従させる（①提出物が変わる）

**Files:**
- Modify: `src/lucario_agent/combat.py:266-274`（`_score_retreat_option`）
- Modify: `src/lucario_agent/main.py:624-629`（`_score_option` の `case OptionType.RETREAT`）
- Modify: `src/lucario_agent/main.py:320-335`（`PlayScoringContext`）
- Modify: `src/lucario_agent/main.py:426-441`（`SwitchPolicy.play_score`）
- Modify: `src/lucario_agent/main.py:477-512`（`_score_play_option`）
- Modify: `src/lucario_agent/main.py:594-599`（`_score_option` の `case OptionType.PLAY`）
- Test: `tests/test_lucario_agent.py`（`TestScoreRetreatOption` / `TestScoreOptionRetreatWiring` / `TestSwitchPolicy` / `TestSwitchPolicyAirBalloon`）

**Interfaces:**
- Produces: `_score_retreat_option(current_plan, my_active=None, card_table=None, op_active_nullifies_ex=False) -> int`（第4引数を新設。位置引数・キーワード引数どちらでも渡せる）
- Produces: `_should_preserve_active(current_plan, my_active, card_table, op_active_nullifies_ex) -> bool`（`combat.py` のモジュール関数。Task 1 の内部でのみ使う）
- Produces: `PlayScoringContext` に `op_active_nullifies_ex: bool = False` フィールドを追加
- Produces: `_score_play_option(..., op_active_nullifies_ex: bool = False)` キーワード引数を追加
- Consumes: `EX_DAMAGE_NULLIFIER_IDS = frozenset({Crustle(345), Sylveon(330)})`（`constants.py:29`、既存）
- Consumes: `_op_active_nullifies_ex(op_state) -> bool`（`main.py:138`、既存。`_score_option` の引数 `op_active_nullifies_ex` として既に届いている）

**なぜ必要か：** `SwitchPolicy.play_score` は `_score_retreat_option` の戻り値をそのまま発火条件に使う構造（`main.py:434`）。退却側だけ直すと Switch 側が旧条件のまま残り、「0エネのオーガポンexから0エネのメガルカリオexへ逃げるために、デッキに1枚しかないSwitchを切る」という同じ問題が Switch 経由で残る。**片側だけ直す事故を構造的に防ぐため、同一タスクで一緒に行う。**

- [ ] **Step 1: 既存テスト2件を新しい仕様に合わせて書き換える（まだ実装は変えない）**

`tests/test_lucario_agent.py` の `TestScoreRetreatOption.test_positive_when_ineffective_attack_and_high_value_active`（現在 803-807行）を、次の内容で置き換える。

```python
    def test_positive_when_nullified_and_high_value_active(self):
        """相手のバトル場がex無効化持ち(Crustle等)で攻撃が本当に無意味なときは温存退却する"""
        plan = lm.AttackPlan(attacker=0, damage=0)
        megaex = make_pokemon(id=lm.Mega_Lucario_ex, hp=50)
        assert lm._score_retreat_option(
            plan, megaex, lm.card_table, op_active_nullifies_ex=True,
        ) == 2000
```

同ファイルの `TestScoreOptionRetreatWiring.test_score_option_retreat_uses_current_active_and_card_table`（現在 830-849行）の `op_state` の行を、相手のバトル場を Crustle に変える。

```python
        op_state = make_player_state(active_pokemon=make_pokemon(id=lm.Crustle, hp=100), prize_count=6)
```

そして同メソッドの docstring を実態に合わせる。

```python
    def test_score_option_retreat_uses_current_active_and_card_table(self):
        """_score_optionがRETREATケースでアクティブ・card_table・ex無効化判定を渡す"""
```

- [ ] **Step 2: 本命の失敗テストを書く**

`tests/test_lucario_agent.py` の `TestScoreRetreatOption` クラスの末尾（現在 824行の直後）に追加する。

```python
    def test_negative_when_only_short_on_energy(self):
        """【本命の回帰テスト】実ログ88778720 ターン7の再現。
        0エネのオーガポンexがバトル場にいて相手はex無効化持ちではない場合、
        damage<=0 は「無効化されている」ではなく「まだエネルギーが足りない」なので
        温存退却してはいけない。旧実装はここで2000を返し、
        「退却のために1エネ装着 → 同ターンにそれを退却コストで破棄」を引き起こしていた
        （実測31戦で19回、うち15回はそのターン1回も攻撃できていない）"""
        plan = lm.AttackPlan(attacker=0, damage=0)
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210)
        assert lm._score_retreat_option(
            plan, ogerpon, lm.card_table, op_active_nullifies_ex=False,
        ) == -1

    def test_negative_when_mega_lucario_short_on_energy(self):
        """メガルカリオexでも同じ。エネルギー不足による damage<=0 では温存退却しない"""
        plan = lm.AttackPlan(attacker=0, damage=0)
        megaex = make_pokemon(id=lm.Mega_Lucario_ex, hp=340)
        assert lm._score_retreat_option(
            plan, megaex, lm.card_table, op_active_nullifies_ex=False,
        ) == -1

    def test_positive_when_nullified_and_ogerpon_active(self):
        """ニンフィア(Sylveon)等でも、無効化対面なら従来どおり温存退却する（退行防止）"""
        plan = lm.AttackPlan(attacker=0, damage=0)
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210)
        assert lm._score_retreat_option(
            plan, ogerpon, lm.card_table, op_active_nullifies_ex=True,
        ) == 2000

    def test_switch_attacker_branch_unaffected_by_nullifier_flag(self):
        """ベンチに攻撃できるアタッカーがいる場合の退却は、無効化フラグに関係なく2000のまま"""
        plan = lm.AttackPlan(attacker=1)
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210)
        assert lm._score_retreat_option(
            plan, ogerpon, lm.card_table, op_active_nullifies_ex=False,
        ) == 2000
        assert lm._score_retreat_option(
            plan, ogerpon, lm.card_table, op_active_nullifies_ex=True,
        ) == 2000

    def test_negative_when_nullified_but_regular_pokemon(self):
        """無効化対面でも、アクティブが無印(非ex)なら温存退却しない（既存挙動の維持）"""
        plan = lm.AttackPlan(attacker=0, damage=0)
        regular = make_pokemon(id=lm.Riolu, hp=50)
        assert lm._score_retreat_option(
            plan, regular, lm.card_table, op_active_nullifies_ex=True,
        ) == -1
```

- [ ] **Step 3: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreRetreatOption tests/test_lucario_agent.py::TestScoreOptionRetreatWiring -v`

Expected: `test_negative_when_only_short_on_energy` と `test_negative_when_mega_lucario_short_on_energy` が **FAIL**（`assert 2000 == -1`）。`test_positive_when_nullified_and_high_value_active` は `_score_retreat_option() got an unexpected keyword argument 'op_active_nullifies_ex'` で **FAIL**。`TestScoreOptionRetreatWiring` は現時点では PASS のまま（Crustle でも旧実装は 2000 を返すため）。

- [ ] **Step 4: `_score_retreat_option` を実装する**

`src/lucario_agent/combat.py:266-274` を次の内容で置き換える。

```python
def _should_preserve_active(
    current_plan: AttackPlan, my_active, card_table: dict | None, op_active_nullifies_ex: bool,
) -> bool:
    """攻撃が「無効化されていて無意味」なので高価値ポケモンを温存退却すべきかを判定する。

    【2026-08-04修正】旧実装は current_plan.damage <= 0 だけを見ていたため、
    「相手の特性で無効化されている」と「まだエネルギーが足りない」を区別できなかった。
    calc_attack_plan はエネルギー不足のアタッカーを continue で読み飛ばすので、
    damage<=0 は両方の意味を持ってしまう。技に闘エネ3個を要求するオーガポンexでは
    後者がほぼ常時成立し、「退却のために1エネ装着 → 同じターンにそれを退却コストで破棄」
    を引き起こしていた（実測ver26+ver27の有効31戦で19回、うち15回はそのターン
    1回も攻撃できていない。実ログ88778720 step62-66 が典型）。
    エネルギー不足は「準備中」であって「詰み」ではない。
    """
    if not op_active_nullifies_ex:
        return False
    if current_plan.damage > 0 or my_active is None or card_table is None:
        return False
    data = card_table[my_active.id]
    return bool(data.megaEx or data.ex)


def _score_retreat_option(
    current_plan: AttackPlan, my_active=None, card_table: dict | None = None,
    op_active_nullifies_ex: bool = False,
) -> int:
    """OptionType.RETREAT のスコアを返す"""
    if current_plan.attacker >= 1:
        return 2000  # より良いアタッカーへ切り替える
    if _should_preserve_active(current_plan, my_active, card_table, op_active_nullifies_ex):
        return 2000  # 無効化されていて攻撃が無意味な高価値ポケモンを温存退却する
    return -1
```

- [ ] **Step 5: `_score_option` の RETREAT ケースを配線する**

`src/lucario_agent/main.py:624-629` を次の内容で置き換える。

```python
        case OptionType.RETREAT:
            return _score_retreat_option(
                current_plan,
                my_state.active[0] if my_state.active else None,
                card_table,
                op_active_nullifies_ex,
            )
```

- [ ] **Step 6: テストを実行して通ることを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreRetreatOption tests/test_lucario_agent.py::TestScoreOptionRetreatWiring -v`

Expected: 全て PASS。

- [ ] **Step 7: 既存テストを新仕様に合わせて書き換え、失敗テストを追加する**

`tests/test_lucario_agent.py` の `TestSwitchPolicy._ctx`（現在 907-913行）に、フラグを渡せるよう引数を追加する。

```python
    def _ctx(self, current_plan, my_state, op_active_nullifies_ex=False):
        return lm.PlayScoringContext(
            obs=MagicMock(), o=Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=current_plan, can_attack=False,
            state=_make_state(), my_state=my_state,
            hand_counts=defaultdict(int), field_counts=defaultdict(int), stadium_id=0,
            op_active_nullifies_ex=op_active_nullifies_ex,
        )
```

`TestSwitchPolicy.test_positive_when_ineffective_attack_and_high_value_active`（現在 925-928行）を次の内容で置き換える。

```python
    def test_positive_when_nullified_and_high_value_active(self):
        """無効化対面(Crustle等)で攻撃が本当に無意味なときは従来どおり発火する"""
        plan = lm.AttackPlan(attacker=0, damage=0)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Mega_Lucario_ex, hp=50))
        assert lm.SwitchPolicy().play_score(
            self._ctx(plan, my_state, op_active_nullifies_ex=True),
        ) == 2100

    def test_negative_when_only_short_on_energy(self):
        """0エネのオーガポンexから逃げるためだけに、1枚しかないSwitchを切ってはいけない。
        交代先も0エネで攻撃できないため、カードを失うだけで状況は変わらない"""
        plan = lm.AttackPlan(attacker=0, damage=0)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Ogerpon_ex, hp=210))
        assert lm.SwitchPolicy().play_score(
            self._ctx(plan, my_state, op_active_nullifies_ex=False),
        ) == -1
```

さらに `TestSwitchPolicy` の末尾（現在 940行の直後）に、配線の統合テストを追加する。

```python
    def test_score_option_play_switch_passes_nullifier_flag(self):
        """_score_optionのPLAYケースがop_active_nullifies_exをSwitchPolicyまで届ける。
        相手のバトル場がCrustleなら発火し、そうでなければ発火しないこと"""
        switch_card = Card(id=lm.Switch, serial=1, playerIndex=0)
        my_state = make_player_state(
            active_pokemon=make_pokemon(id=lm.Ogerpon_ex, hp=210), hand=[switch_card],
        )
        plan = lm.AttackPlan(attacker=0, damage=0)

        def score_against(op_active_id):
            op_state = make_player_state(active_pokemon=make_pokemon(id=op_active_id, hp=100))
            obs = MagicMock()
            obs.current.players = [my_state, op_state]
            return lm._score_option(
                obs=obs, o=Option(type=OptionType.PLAY, index=0),
                context=lm.SelectContext.MAIN, my_index=0,
                state=_make_state(), my_state=my_state, op_state=op_state,
                field_counts=defaultdict(int), hand_counts=defaultdict(int),
                discard_counts=defaultdict(int),
                attacker1=False, current_plan=plan, can_attack=True,
                stadium_id=0, ability_used_flag=False,
                op_active_nullifies_ex=(op_active_id in lm.EX_DAMAGE_NULLIFIER_IDS),
            )

        assert score_against(lm.Crustle) == 2100
        assert score_against(lm.Riolu) == -1
```

- [ ] **Step 8: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestSwitchPolicy -v`

Expected: `test_positive_when_nullified_and_high_value_active` と `test_score_option_play_switch_passes_nullifier_flag` が `PlayScoringContext.__init__() got an unexpected keyword argument 'op_active_nullifies_ex'` で **FAIL**。`test_negative_when_only_short_on_energy` は Step 4 の `_score_retreat_option` 修正により既に PASS するはず。

- [ ] **Step 9: `PlayScoringContext` にフィールドを追加する**

`src/lucario_agent/main.py:333-335` の3行を次の内容で置き換える。

```python
    attacker1: bool = False
    rng: "random.Random | None" = None
    op_hand_count: int = 0
    op_active_nullifies_ex: bool = False
```

- [ ] **Step 10: `SwitchPolicy.play_score` を追従させる**

`src/lucario_agent/main.py:434` の1行を次の内容で置き換える。

```python
        base = _score_retreat_option(
            ctx.current_plan, my_active, card_table, ctx.op_active_nullifies_ex,
        )
```

- [ ] **Step 11: `_score_play_option` に引数を追加して ctx へ渡す**

`src/lucario_agent/main.py:477-481` のシグネチャを次の内容で置き換える。

```python
def _score_play_option(obs, o, my_index, current_plan, can_attack,
                       state, my_state, hand_counts, field_counts, stadium_id,
                       attacker1: bool = False,
                       rng: "random.Random | None" = None,
                       op_hand_count: int = 0,
                       op_active_nullifies_ex: bool = False) -> int:
```

`src/lucario_agent/main.py:507-511` の `ctx = PlayScoringContext(...)` を次の内容で置き換える。

```python
    ctx = PlayScoringContext(
        obs=obs, o=o, my_index=my_index, current_plan=current_plan, can_attack=can_attack,
        state=state, my_state=my_state, hand_counts=hand_counts, field_counts=field_counts,
        stadium_id=stadium_id, attacker1=attacker1, rng=rng, op_hand_count=op_hand_count,
        op_active_nullifies_ex=op_active_nullifies_ex,
    )
```

- [ ] **Step 12: `_score_option` の PLAY ケースを配線する**

`src/lucario_agent/main.py:594-599` を次の内容で置き換える。

```python
        case OptionType.PLAY:
            return _score_play_option(
                obs, o, my_index, current_plan, can_attack,
                state, my_state, hand_counts, field_counts, stadium_id,
                attacker1, op_hand_count=op_state.handCount,
                op_active_nullifies_ex=op_active_nullifies_ex,
            )
```

- [ ] **Step 13: テストを実行して通ることを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestSwitchPolicy tests/test_lucario_agent.py::TestSwitchPolicyAirBalloon tests/test_lucario_agent.py::TestScoreOptionPlaySwitchWiring -v`

Expected: 全て PASS。

- [ ] **Step 14: リポジトリ全体の回帰を確認する**

Run: `uv run pytest -q`

Expected: **全件 PASS**。件数は着手時の 785 件 + 本タスクで追加した分。**1件でも失敗が残っている状態でコミットしないこと**（退却側の変更と SwitchPolicy の追従は同時に成立して初めて整合するため、本タスクは全件PASSを満たすまで完了ではない）。

- [ ] **Step 15: コミット**

```bash
git add src/lucario_agent/combat.py src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix(lucario): 温存退却をex無効化対面限定にしてエネ浪費ループを断つ

damage<=0が「無効化されている」と「エネルギーが足りないだけ」を区別
できておらず、闘エネ3個要求のオーガポンexでほぼ常時発火していた。
実測31戦で19回の「同ターン装着→退却で破棄」を引き起こし、
うち15回はそのターン1回も攻撃できていなかった(88778720 step62-66)。

Switchカードは_score_retreat_optionの戻り値をそのまま発火条件に使う
構造のため、退却側だけ直すと同じ問題がSwitch経由で残る。
PlayScoringContextにop_active_nullifies_exを追加して同時に追従させる。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: ふうせんをオーガポンexへ優先装着する（①提出物が変わる）

**Files:**
- Modify: `src/lucario_agent/main.py:525-534`（`_score_attach_option` のふうせん分岐）
- Test: `tests/test_lucario_agent.py`（`TestScoreAttachOptionAirBalloon`）

**Interfaces:**
- Consumes: `Ogerpon_ex = 117` / `Air_Balloon = 1174` / `Maximum_Belt = 1158`（`constants.py`、既存。`main.py:17` で既に import 済み）
- Produces: なし（`_score_attach_option` のシグネチャは変えない）

**根拠：** オーガポンexのにげるコストは **1**、ふうせんは **-2**。1枚貼るだけで実効にげるコストが **0** になり、エネルギーを一切払わずに出入りできる。実測ではオーガポンexは31戦で33回バトル場に入っているのに、ふうせんが付いていたのは **2回だけ** だった。

- [ ] **Step 1: 既存テストの期待値を更新し、失敗テストを追加する**

`tests/test_lucario_agent.py` の `TestScoreAttachOptionAirBalloon` の docstring（現在 1663-1665行）を次の内容で置き換える。

```python
class TestScoreAttachOptionAirBalloon:
    """_score_attach_optionのふうせん(Air Balloon)分岐のスコア順位。

    2026-08-04: オーガポンex(にげるコスト1)を最優先にした。ふうせん-2で実効0になり、
    KO後の強制交代で前に出てもエネルギーを払わずに下がれるようになる。
    併せて、ふうせん→メガルカリオex(旧7100)がMaximum Belt→リオル(7100)と
    同点だったのを7050へ下げて解消した（同点だと装着先が選択肢の提示順で決まる）。
    ベーススコアは6900のまま"""
```

`test_mega_lucario_ex_highest_priority`（現在 1680-1682行）を次の内容で置き換える。

```python
    def test_ogerpon_ex_highest_priority(self):
        """にげるコスト1がふうせん-2で0になり、出入りが完全に無償になるため最優先"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex)
        assert self._score(ogerpon) == 7150

    def test_mega_lucario_ex_second_priority(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex)
        assert self._score(lucario) == 7050
```

`test_mega_lucario_ex_scores_higher_than_riolu`（現在 1692-1693行）の直後に、共通ヘルパーと、順位を固定するテスト2件を追加する。

**共通ヘルパーを先に足すこと**（`_score` はふうせん固定なので、カードIDも変えられる版が要る）。

```python
    # 上の _score はふうせん固定なので、カードIDも指定できる版を用意する
    TOOL_ATTACH_TARGETS = (lm.Mega_Lucario_ex, lm.Riolu, lm.Ogerpon_ex, lm.Solrock)

    def _score_tool(self, card_id, pokemon_id):
        obs = MagicMock()
        card = Card(id=card_id, serial=1, playerIndex=0)
        my_state = make_player_state(active_pokemon=make_pokemon(id=pokemon_id), hand=[card])
        obs.current.players = [my_state, make_player_state()]
        option = Option(
            type=OptionType.ATTACH, area=lm.AreaType.HAND, index=0,
            inPlayArea=lm.AreaType.ACTIVE, inPlayIndex=0,
        )
        return lm._score_attach_option(
            obs, option, my_index=0, current_plan=lm.AttackPlan(), attacker1=False,
        )

    @pytest.mark.parametrize("card_id, pokemon_id, expected", [
        (lm.Maximum_Belt, lm.Mega_Lucario_ex, 7200),
        (lm.Air_Balloon,  lm.Ogerpon_ex,      7150),
        (lm.Maximum_Belt, lm.Riolu,           7100),
        (lm.Air_Balloon,  lm.Mega_Lucario_ex, 7050),
        (lm.Air_Balloon,  lm.Riolu,           7000),
        (lm.Air_Balloon,  lm.Solrock,         6900),
        (lm.Maximum_Belt, lm.Solrock,           -1),
    ])
    def test_tool_attach_score_ordering(self, card_id, pokemon_id, expected):
        """どうぐ装着スコアの順位を固定する"""
        assert self._score_tool(card_id, pokemon_id) == expected

    def test_no_ties_among_tool_attach_scores(self):
        """どうぐ装着スコアに同点が無いことを、実際に_score_attach_optionを呼んで確認する。
        同点だと装着先がエンジン依存の選択肢提示順で決まってしまうため、
        将来スコアをいじって同点が生まれたらこのテストが落ちる必要がある。
        -1は「温存」を表すセンチネル値なので、複数の組合せが-1になるのは正常"""
        combinations = [
            (card_id, pokemon_id)
            for card_id in (lm.Maximum_Belt, lm.Air_Balloon)
            for pokemon_id in self.TOOL_ATTACH_TARGETS
        ]
        scored = [(combo, self._score_tool(*combo)) for combo in combinations]
        real_scores = [score for _combo, score in scored if score != -1]
        assert len(real_scores) == len(set(real_scores)), f"同点がある: {scored}"
```

**注意：** この2件目は上のパラメタライズドの期待値をコピーするのではなく、**必ず `_score_tool` 経由で実コードからスコアを集めること**。ベタ書きのリストに重複が無いことを確認するだけのテストはコードを一切検証しないので不可。

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreAttachOptionAirBalloon -v`

Expected: `test_ogerpon_ex_highest_priority` が **FAIL**（`assert 6900 == 7150`）、`test_mega_lucario_ex_second_priority` が **FAIL**（`assert 7100 == 7050`）、`test_tool_attach_score_ordering` のうち Ogerpon/Air_Balloon と Mega_Lucario_ex/Air_Balloon の2ケースが **FAIL**、`test_no_ties_among_tool_attach_scores` が **FAIL**。

最後の1件は修正前のスコアに実際に同点が2組あるため落ちる（ふうせん→メガルカリオex 7100 と Maximum Belt→リオル 7100、ふうせん→オーガポンex 6900 と ふうせん→ソルロック 6900）。**ここが FAIL しない場合はテストが実コードを呼べていない**ので、`_score_tool` の配線を疑うこと。

- [ ] **Step 3: ふうせん分岐を実装する**

`src/lucario_agent/main.py:525-534` を次の内容で置き換える。

```python
    if card.id == Air_Balloon:
        pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
        # ベーススコアは優先ツール(Maximum Belt, 7200/7100)より低い6900とし、同一ポケモン対象での
        # 同点（装着先が実質ランダムに決まる問題）を避ける（最終レビュー指摘）
        score = 6900
        if pokemon.id == Ogerpon_ex:
            # 【2026-08-04追加】オーガポンexのにげるコストは1なので、ふうせん(-2)1枚で
            # 実効0になり、エネルギーを一切払わずに出入りできる。オーガポンexは技に
            # 闘エネ3個を要求するためバトル場で手詰まりになりやすく、実測ver26+ver27の
            # 有効31戦では33回バトル場に入って27回が0エネ、ふうせん装着は2回だけだった。
            # 7150 は Maximum Belt→メガルカリオex(7200)の次、Maximum Belt→リオル(7100)より上。
            score += 250
        elif pokemon.id == Mega_Lucario_ex:
            # 旧値7100は Maximum Belt→リオル(7100)と同点で、装着先が選択肢の
            # 提示順（エンジン依存で制御不能）で決まっていたため7050へ下げた
            score += 150
        elif pokemon.id == Riolu:
            score += 100
        return score
```

- [ ] **Step 4: テストを実行して通ることを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreAttachOptionAirBalloon tests/test_lucario_agent.py::TestScoreAttachOptionMaximumBeltVsAirBalloon -v`

Expected: 全て PASS。`TestScoreAttachOptionMaximumBeltVsAirBalloon` の3件（Maximum Belt がふうせんに勝つこと）も維持されていること。

- [ ] **Step 5: リポジトリ全体の回帰を確認する**

Run: `uv run pytest -q`

Expected: 全件 PASS。

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat(lucario): ふうせんをオーガポンexへ優先装着し、どうぐの同点を解消

オーガポンexのにげるコスト1はふうせん-2で実効0になり、エネルギーを
払わずに出入りできる。実測31戦で33回バトル場に入りながら装着は2回だけ
だった。併せて ふうせん→メガルカリオex(7100) と Maximum Belt→リオル(7100)
の同点を7050へ下げて解消する。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 効果測定用の指標を計測スクリプトに追加する（②提出物は変わらない）

**Files:**
- Modify: `scripts/analyze_lucario_energy_metrics.py`
- Test: `tests/test_analyze_lucario_energy_metrics.py`

**Interfaces:**
- Consumes: `find_player_index(data, my_name="Kagura_UT") -> int`（既存、`scripts/analyze_lucario_energy_metrics.py:47`）
- Consumes: `_iter_my_selects(data, my_index)`（既存、同 55行。`(step番号, select, current, 選ばれたインデックス列)` を返す）
- Consumes: `OPTION_ATTACH = 8` / `OPTION_RETREAT = 12` / `AREA_ACTIVE = 4` / `CONTEXT_DISCARD_ENERGY = 30`（既存の定数）
- Produces: `measure_turn_activity(data, my_name="Kagura_UT") -> dict`
  戻り値のキー：`my_turns` / `turns_with_attack` / `wasted_turns` / `wasted_no_attack`
- Produces: `measure_ogerpon_active_entries(data, my_name="Kagura_UT") -> dict`
  戻り値のキー：`entries` / `entries_zero_energy` / `entries_with_air_balloon`

**これは②です。エージェント本体は変更しません。** 次のバッチ（20戦×2＝40戦）で Task 1〜2 の効果を判定するために必要な指標を用意する。

**注意（設計書の再現手順に記載済み）：** 解析時は**相手の事故勝ち（勝ち試合のうち終局時の自分のサイド残が6のもの）を必ず除外**すること。除外を怠ると分母（自分のターン数）だけが縮み、1ターンあたり指標が一律2割ほど水増しされる（罠8）。

- [ ] **Step 1: 失敗テストを書く**

`tests/test_analyze_lucario_energy_metrics.py` の末尾に追加する。

**このテストファイルの既存の作法に必ず合わせること：**
- モジュールは `importlib.util` で読み込まれ、**別名は `alem`**（`am` ではない）。同ファイル冒頭の 8-13行を参照
- 1ステップのログを組み立てる既存ヘルパー **`_make_log(my_index, hand, options, chosen, context, select_type=1)`**（同ファイル 20行付近）がある。複数ステップが必要な今回のテストでは、これを読んで同じ構造の複数ステップ版ヘルパーを書く
- **選択結果は `steps[N]['action']` ではなく `steps[N+1][my_index]['action']` に入る（1ステップずれ）。** ここを間違えると全く別の選択肢を読むことになる

```python
class TestMeasureTurnActivity:
    """『バトル場に装着 → 同ターン退却でそのエネを破棄』したターンに、
    実際に攻撃できたのかを数える。2026-08-04の温存退却修正の効果測定用"""

    def test_counts_wasted_turn_without_attack(self):
        """装着→退却→エネ破棄をして、そのターン攻撃しなかったら wasted_no_attack が1"""
        data = _build_log_attach_then_retreat(attacked=False)
        result = alem.measure_turn_activity(data)
        assert result["wasted_turns"] == 1
        assert result["wasted_no_attack"] == 1
        assert result["turns_with_attack"] == 0

    def test_counts_wasted_turn_with_attack(self):
        """同じ動きでも、そのターンに攻撃できていれば wasted_no_attack には数えない"""
        data = _build_log_attach_then_retreat(attacked=True)
        result = alem.measure_turn_activity(data)
        assert result["wasted_turns"] == 1
        assert result["wasted_no_attack"] == 0
        assert result["turns_with_attack"] == 1

    def test_retreat_without_same_turn_attach_is_not_wasted(self):
        """前のターンから乗っていたエネで退却した場合は浪費ではない（誤検出防止）"""
        data = _build_log_retreat_only()
        result = alem.measure_turn_activity(data)
        assert result["wasted_turns"] == 0


class TestMeasureOgerponActiveEntries:
    """オーガポンexがバトル場に入った回数と、そのときのエネルギー数・ふうせん装着状況。
    ふうせん優先装着（2026-08-04）の効果測定用"""

    def test_counts_entry_without_air_balloon(self):
        data = _build_log_ogerpon_enters_active(energies=0, tools=[])
        result = alem.measure_ogerpon_active_entries(data)
        assert result["entries"] == 1
        assert result["entries_zero_energy"] == 1
        assert result["entries_with_air_balloon"] == 0

    def test_counts_entry_with_air_balloon(self):
        data = _build_log_ogerpon_enters_active(energies=0, tools=[alem.AIR_BALLOON])
        result = alem.measure_ogerpon_active_entries(data)
        assert result["entries"] == 1
        assert result["entries_with_air_balloon"] == 1

    def test_does_not_double_count_while_staying_active(self):
        """バトル場に居座っている間は入場を再カウントしない（遷移だけ数える）"""
        data = _build_log_ogerpon_stays_active(turns=3)
        result = alem.measure_ogerpon_active_entries(data)
        assert result["entries"] == 1
```

ログ組み立てヘルパー `_build_log_attach_then_retreat` / `_build_log_retreat_only` / `_build_log_ogerpon_enters_active` / `_build_log_ogerpon_stays_active` も同ファイルに書くこと。実ログ `data/battle_logs/88778720.json` の step62〜66 が実物の構造なので、迷ったらそこを読んで合わせる。

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_analyze_lucario_energy_metrics.py -v`

Expected: 新規クラス2つが `AttributeError: module has no attribute 'measure_turn_activity'` 等で **FAIL**。既存テスト21件は PASS のまま。

- [ ] **Step 3: `measure_turn_activity` を実装する**

`scripts/analyze_lucario_energy_metrics.py` に追加する。定数 `OGERPON_EX = 117` と `AIR_BALLOON = 1174` もカードID定数の並びに追加すること。

判定ロジックの要点：
- 自分のターン番号ごとに「バトル場への ATTACH を選んだか」「RETREAT を選んだか」「`attackId` を持つ選択肢を選んだか」を記録する
- **退却コストの支払いは `OptionType.RETREAT` を選んだ直後の `SelectContext.DISCARD_ENERGY(30)` で起きる。`DISCARD_ENERGY` は相手の技の効果等でも発生するため、直前の RETREAT 選択と紐付いたものだけを数える**（既存 `measure_retreat_energy_loss` と同じ扱い）
- `wasted_turns` = そのターンに「バトル場へのATTACH」と「RETREATに紐づくDISCARD_ENERGY」が両方あったターン数
- `wasted_no_attack` = `wasted_turns` のうち `attackId` の選択が1つも無かったターン数

- [ ] **Step 4: `measure_ogerpon_active_entries` を実装する**

自分の select を順に見て、`current.players[my_index].active[0].id` が **前回の観測ではオーガポンex以外だったのに今回オーガポンexになった** 遷移だけを数える。同時にその時点の `energies` の枚数と `tools` に `AIR_BALLOON` が含まれるかを記録する。

- [ ] **Step 5: テストを実行して通ることを確認する**

Run: `uv run pytest tests/test_analyze_lucario_energy_metrics.py -v`

Expected: 全て PASS。

- [ ] **Step 6: 修正前の実ログで実行し、既知の値を再現できることを確認する**

Run:

```bash
EXCL="88778193 88783510 88784593 88786195 88788366 88797654 88798724 88799753 88807298"
FILES=$(ls data/battle_logs/*.json | awk -F/ '{print $NF}' | sed 's/.json//' \
  | awk '$1>=88778193 && $1<=88807298' | grep -vE "$(echo $EXCL | tr ' ' '|')" \
  | sed 's|^|data/battle_logs/|;s|$|.json|')
uv run python scripts/analyze_lucario_energy_metrics.py ${=FILES}
```

Expected: ver26+ver27 の有効31戦に対し、本セッションで計測済みの次の値と一致すること。**一致しなければ実装を疑うこと**（この31戦は修正前のログなので値は変わらないはず）。

| 指標 | 期待値 |
|---|---|
| `wasted_turns` | 19 |
| `wasted_no_attack` | 15 |
| `turns_with_attack` | 119 |
| `my_turns` | 297 |
| オーガポンexの入場回数 `entries` | 33 |
| うち0エネ `entries_zero_energy` | 27 |
| うちふうせん装着済み `entries_with_air_balloon` | 2 |

- [ ] **Step 7: コミット**

```bash
git add scripts/analyze_lucario_energy_metrics.py tests/test_analyze_lucario_energy_metrics.py
git commit -m "feat(scripts): 退却ループ修正の効果測定に必要な指標3つを追加

measure_turn_activity()で『装着→同ターン退却』のターンに攻撃できたかを、
measure_ogerpon_active_entries()でオーガポンexの入場回数とふうせん装着率を
数える。修正前31戦での値(wasted_turns=19/wasted_no_attack=15/entries=33)を
再現することを確認済み。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 全体検証・提出用notebook再生成・実装サマリー（①提出物が変わる）

**Files:**
- Create: `docs/implementations/20260804-lucario-ogerpon-retreat-loop.md`
- Regenerate: `notebooks/submissions/lucario_agent_submission.ipynb`（`scripts/build_lucario_submission_notebook.py` が生成する。生成後にパスと生成日時を報告する）

**Interfaces:** なし（検証と文書化のみ）

- [ ] **Step 1: リポジトリ全体のテストを実行する**

Run: `uv run pytest -q`

Expected: 全件 PASS。**着手時の 785 件を下回らないこと**。実際の件数を控えて実装サマリーに書く。

- [ ] **Step 2: 変更したスコアが 9000〜10000 の帯域を侵していないことを確認する**

Run: `uv run pytest tests/test_lucario_agent.py -k "score" -q`

加えて、Task 2 で変更したどうぐ装着スコアの最大値が **7200** であり、エネルギー装着の実測最大 **8930**・Judge **9000**・EVOLVE **9100+エネ数** の帯域に触れていないことを目視で確認する。Task 1 は退却スコア（2000/2100）のみを扱っており帯域に影響しない。

- [ ] **Step 3: 提出用notebookを再生成する**

Run: `uv run python scripts/build_lucario_submission_notebook.py`

Expected: 生成成功。出力先のパスと生成日時を控える。

- [ ] **Step 4: 実装サマリーを書く**

`docs/implementations/20260804-lucario-ogerpon-retreat-loop.md` に次を含めて記録する。

- **冒頭に「提出物が変わったか」を書く**（CLAUDE.md ルール7）。今回は **①変わった**
- 変更した関数と行（`_score_retreat_option` / `_should_preserve_active` / `SwitchPolicy` / `PlayScoringContext` / `_score_play_option` / `_score_attach_option`）
- 根本原因の要約と、実ログ `88778720` step62-66 の再現手順
- テスト件数（着手時 785 → 完了時 N）
- **次バッチでの検証項目**（設計書の効果測定表をそのまま転記し、修正前の値 19/15/119/297/33/27/2 をベースラインとして明記する）
- **明記しておく懸念**：オーガポンexがバトル場に残る時間が増えること。悪化した場合の次の打ち手は案B（交代先が今ターン実際に攻撃できるときだけ退却する）

- [ ] **Step 5: コミット**

```bash
git add docs/implementations/20260804-lucario-ogerpon-retreat-loop.md
git commit -m "docs(lucario): オーガポンex退却ループ解消の実装サマリーを保存

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 6: ユーザーへ完了報告する**

報告には次を必ず含める（CLAUDE.md ルール7）。

1. **最初に「提出物が変わったか」**：今回は **変わった**。Kaggleへ再提出すると中身が前回（ver26/ver27）と異なる
2. テスト件数と全件PASSの事実（実行結果そのまま）
3. 提出用notebookの生成パスと生成日時
4. push と Kaggle へのアップロードはユーザーが実施する旨
5. 次バッチ（20戦×2＝40戦）で見る指標と、そのベースライン値

---

## Self-Review 記録

**1. 設計書のカバレッジ**

| 設計書の項目 | 対応タスク |
|---|---|
| 変更1：温存退却をex無効化対面限定にする | Task 1 |
| 変更2：ふうせんをオーガポンexへ優先装着 | Task 2 |
| 変更3：呼び出し側の追従（`_score_option` RETREAT） | Task 1 Step 5 |
| 変更3：呼び出し側の追従（`SwitchPolicy`） | Task 1 Step 10 |
| テスト方針1（実ログ88778720の再現） | Task 1 Step 2 `test_negative_when_only_short_on_energy` |
| テスト方針2（Crustle/Sylveonの退行防止） | Task 1 Step 2 `test_positive_when_nullified_and_*` |
| テスト方針3（`attacker >= 1` が無影響） | Task 1 Step 2 `test_switch_attacker_branch_unaffected_by_nullifier_flag` |
| テスト方針4（SwitchPolicyの追従） | Task 1 Step 7 |
| テスト方針5（どうぐ装着スコア7通り・同点なし） | Task 2 Step 1 |
| テスト方針6（全体回帰785件） | Task 1 Step 14 / Task 2 Step 5 / Task 4 Step 1 |
| 効果測定：新規計測3つ | Task 3（②として分離） |

**2. プレースホルダ確認**：「TBD」「適切に」「同様に」等は使用していない。全コードブロックに実際の内容を記載済み。

**3. 型・名前の一貫性**：`op_active_nullifies_ex`（全箇所で同一）、`_should_preserve_active`（Task 1 でのみ定義・使用）、`measure_turn_activity` / `measure_ogerpon_active_entries`（Task 3 で定義、Task 4 の検証で参照）。`PlayScoringContext.op_active_nullifies_ex` は Task 1 Step 9 で定義し Step 10 で使用。

**4. 壊れた中間コミットの排除**：当初は退却側とSwitchPolicyの追従を別タスクに分けており、前者のみのコミットでテストが1件失敗する構造になっていた。両者は同時に成立して初めて整合するため1タスクに統合し、全件PASSを満たしてから1コミットする形に改めた。