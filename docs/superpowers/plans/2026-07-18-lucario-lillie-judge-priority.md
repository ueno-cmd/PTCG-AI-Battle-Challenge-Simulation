# ルカリオexエージェント リーリエの決意「死に札誤認」修正＋Judge対Alakazam強化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/lucario_agent/main.py`の2件のトレーナーズカード判断ミスを修正する。①`LillieDeterminationPolicy`が進化先のRioluが場にいないMega Lucario exを「温存すべき有用な手札」と誤認する問題、②`JudgePolicy`が相手の手札膨張（Alakazam系のドローエンジン対策）に無反応で、かつ自身が捨て札から保護されていない問題。

**Architecture:** 既存の`TrainerCardPolicy`レジストリパターン（`docs/superpowers/specs/2026-07-17-lucario-trainer-card-policy-design.md`で導入済み）の枠内で2クラスを修正する。`JudgePolicy`修正には相手の手札枚数（`op_state.handCount`）を`PlayScoringContext`まで新規配線する必要がある。DISCARD分岐（`_score_card_option`内）にはJudgeを保護対象として追加する。

**Tech Stack:** Python 3.12 / pytest / uv（既存スタックそのまま、新規依存なし）

## Global Constraints

- 設計書: `docs/superpowers/specs/2026-07-18-lucario-lillie-judge-priority-design.md`
- 既存テスト（`tests/test_lucario_agent.py`）は原則無改修で全てPASSさせる。ただし
  `test_suppressed_when_mega_lucario_ex_in_hand`（1324-1326行目）は**設計変更により意図的に
  挙動が変わる**ため、Task 1でこのテストの更新が必須（下記参照）
- Kaggle提出ノートブック（`.gitignore`対象）への反映・デッキCSV再生成・Kaggle再提出は
  本計画のスコープ外。全タスク完了後、ユーザーに次のアクションとして明示的に確認する
- コミットは`main`直下へ直接（featureブランチは使わず、過去のルカリオex改修と同じ運用。
  ブランチ分離が必要な規模ではないため、ユーザー確認の上でシンプルに進める）

---

## Task 1: `LillieDeterminationPolicy`修正（Mega Lucario exの死に札判定）

**Files:**
- Modify: `src/lucario_agent/main.py:536-544`（`LillieDeterminationPolicy`クラス）
- Test: `tests/test_lucario_agent.py:1303-1342`（`TestLillieDeterminationHandQualityGuard`クラス）

**Interfaces:**
- Consumes: 既存の`PlayScoringContext`（`hand_counts`, `field_counts`フィールド）、
  既存定数`lm.Riolu`, `lm.Ogerpon_ex`, `lm.Solrock`, `lm.Lunatone`, `lm.Mega_Lucario_ex`
- Produces: `LillieDeterminationPolicy.play_score(ctx) -> int`（シグネチャ変更なし、
  内部判定ロジックのみ変更）

- [ ] **Step 1: 既存テストを新しい期待挙動に更新する（先にテストを直す＝Red化）**

`tests/test_lucario_agent.py`の1324-1326行目を以下に置き換える（Mega Lucario exは
場にRioluがいなければ死に札のため温存されない、という新しい期待挙動に分割）：

```python
    def test_not_suppressed_when_mega_lucario_ex_in_hand_without_riolu_in_field(self):
        """Mega Lucario exは進化元のRioluが場にいなければ死に札。温存しない
        （86486986戦：Riolu不在でMega Lucario exのみ手札にあり、誤って温存され
        続けていたロジックミスの修正）"""
        score = self._score([Card(id=lm.Mega_Lucario_ex, serial=2, playerIndex=0)])
        assert score == 3100

    def test_suppressed_when_mega_lucario_ex_in_hand_with_riolu_in_field(self):
        """場にRioluがいれば、手札のMega Lucario exは次ターン進化できる有用な
        手札のため温存する"""
        lillie = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        extra = Card(id=lm.Mega_Lucario_ex, serial=2, playerIndex=0)
        cards = [lillie, extra]
        obs, my_state = _obs_with_hand(cards, deck_count=20)
        fc = defaultdict(int, {lm.Riolu: 1})
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts(cards), field_counts=fc,
            stadium_id=0,
        )
        assert score == -1
```

**Step 1のポイント**：`_score`ヘルパー（1308-1318行目）は`field_counts=defaultdict(int)`
固定で呼んでいるため、Riolu在場ケースは`_score`を使わず`_score_play_option`を直接呼ぶ
（上記コードの通り）。

- [ ] **Step 2: テストを実行し、想定通り失敗することを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestLillieDeterminationHandQualityGuard -v`
Expected: `test_not_suppressed_when_mega_lucario_ex_in_hand_without_riolu_in_field`が
`assert -1 == 3100`でFAIL（現行コードはRiolu在場を見ていないため常に温存＝-1を返す）。
`test_suppressed_when_mega_lucario_ex_in_hand_with_riolu_in_field`はPASS
（現行コードでも-1を返すため偶然通るが、Step 3後も同じ理由でPASSし続ける）。

- [ ] **Step 3: `LillieDeterminationPolicy`を修正する**

`src/lucario_agent/main.py`の536-544行目を以下に置き換える：

```python
class LillieDeterminationPolicy(TrainerCardPolicy):
    """手札に「今すぐ場へ展開できる」主要ポケモンがあれば温存する。
    Mega Lucario exは進化元のRioluが場にいなければ死に札のため、温存条件から除外する
    （86363073, 86197001, 86241854, 86295193, 86295949, 86486986等の実ログで、
    有用な手札を持ちながら、あるいは死に札を有用と誤認して山札に戻していた
    ロジックミスの修正）"""
    DIRECTLY_PLAYABLE_IDS = (Riolu, Ogerpon_ex, Solrock, Lunatone)

    def play_score(self, ctx: PlayScoringContext) -> int:
        deployable = any(ctx.hand_counts[pid] >= 1 for pid in self.DIRECTLY_PLAYABLE_IDS)
        deployable = deployable or (
            ctx.hand_counts[Mega_Lucario_ex] >= 1 and ctx.field_counts[Riolu] >= 1
        )
        return -1 if deployable else 3100
```

- [ ] **Step 4: テストを実行し、全てPASSすることを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestLillieDeterminationHandQualityGuard -v`
Expected: 6件全てPASS（`test_suppressed_when_riolu_in_hand`,
`test_not_suppressed_when_mega_lucario_ex_in_hand_without_riolu_in_field`,
`test_suppressed_when_mega_lucario_ex_in_hand_with_riolu_in_field`,
`test_suppressed_when_ogerpon_ex_in_hand`, `test_suppressed_when_solrock_in_hand`,
`test_suppressed_when_lunatone_in_hand`, `test_scores_normally_when_no_key_pokemon_in_hand`）

- [ ] **Step 5: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS（新規失敗なし）

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
fix(lucario): LillieDeterminationがMega Lucario exの死に札を誤って温存材料にしていた問題を修正

Riolu不在で進化できないMega Lucario exを手札に持つだけでリーリエの決意を
温存し続けていた。場にRioluがいる場合のみ温存材料として扱うよう修正。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `JudgePolicy`に相手手札枚数トリガーを追加する

**Files:**
- Modify: `src/lucario_agent/main.py:480-493`（`PlayScoringContext`データクラス）
- Modify: `src/lucario_agent/main.py:600-626`（`_score_play_option`関数シグネチャ・呼び出し）
- Modify: `src/lucario_agent/main.py:667-672`（`_score_option`内のPLAY分岐呼び出し）
- Modify: `src/lucario_agent/main.py:563-565`（`JudgePolicy`クラス）
- Test: `tests/test_lucario_agent.py`（`TestJudgeDeckSafety`クラス周辺、1108-1125行目）

**Interfaces:**
- Consumes: `op_state.handCount`（`cg.api.PlayerState.handCount: int`、既存フィールド）
- Produces: `PlayScoringContext.op_hand_count: int`（新規フィールド、デフォルト0）。
  `_score_play_option(..., op_hand_count: int = 0)`（新規キーワード引数、デフォルト0で
  既存呼び出し元との後方互換を維持）

- [ ] **Step 1: 失敗するテストを書く（`op_hand_count`が閾値以上でJudgeが最優先になること）**

`tests/test_lucario_agent.py`の`test_judge_held_when_attacker_ready`
（1114-1125行目）の直後に以下を追加：

```python
    def test_judge_prioritised_when_opponent_hand_is_flooded(self):
        """相手の手札が閾値以上に膨れている場合は、自分のエネルギー状況に
        関わらずJudgeを最優先で発動する（Alakazam系のPsychic Draw×Rare Candy
        ドローエンジン対策。実ログ86139105ほかで、相手手札が最大25枚まで
        膨張しても対抗できていなかった問題の修正）"""
        my_ps = make_player_state(hand=[Card(id=lm.Judge, serial=1, playerIndex=0)])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        score = lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=True,
            state=_make_state(), my_state=my_ps,
            hand_counts=defaultdict(int, {lm.Basic_Fighting_Energy: 1}),
            field_counts=defaultdict(int), stadium_id=0,
            op_hand_count=10,
        )
        assert score == 9000

    def test_judge_not_prioritised_when_opponent_hand_below_threshold(self):
        """相手の手札が閾値未満なら、従来通り自分のエネルギー状況で判断する"""
        my_ps = make_player_state(hand=[Card(id=lm.Judge, serial=1, playerIndex=0)])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        score = lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=True,
            state=_make_state(), my_state=my_ps,
            hand_counts=defaultdict(int, {lm.Basic_Fighting_Energy: 1}),
            field_counts=defaultdict(int), stadium_id=0,
            op_hand_count=9,
        )
        assert score == -1
```

- [ ] **Step 2: テストを実行し、`TypeError`で失敗することを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestNewCardScoring::test_judge_prioritised_when_opponent_hand_is_flooded -v`
Expected: FAIL（`_score_play_option() got an unexpected keyword argument 'op_hand_count'`）

（`test_judge_held_when_attacker_ready`と同じ`TestNewCardScoring`クラス（1073行目〜）に追加する）

- [ ] **Step 3: `PlayScoringContext`に`op_hand_count`フィールドを追加**

`src/lucario_agent/main.py`の480-493行目、`PlayScoringContext`の末尾フィールドに追加：

```python
@dataclass
class PlayScoringContext:
    """OptionType.PLAY のスコアリングに必要な情報をまとめる（_score_play_optionの既存引数を集約）"""
    obs: Observation
    o: Option
    my_index: int
    current_plan: AttackPlan
    can_attack: bool
    state: PlayerState
    my_state: PlayerState
    hand_counts: defaultdict
    field_counts: defaultdict
    stadium_id: int
    attacker1: bool = False
    rng: "random.Random | None" = None
    op_hand_count: int = 0
```

- [ ] **Step 4: `_score_play_option`のシグネチャと`ctx`構築に`op_hand_count`を追加**

`src/lucario_agent/main.py`の600-626行目を以下に置き換える：

```python
def _score_play_option(obs, o, my_index, current_plan, can_attack,
                       state, my_state, hand_counts, field_counts, stadium_id,
                       attacker1: bool = False,
                       rng: "random.Random | None" = None,
                       op_hand_count: int = 0) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]
    consumption = _deck_consumption(card.id, my_state, hand_counts)
    if consumption is not None and consumption > _safe_draws(my_state):
        return -1  # 山札温存
    if data.cardType == CardType.POKEMON:
        if card.id in (Lunatone, Solrock):
            return -1 if field_counts[card.id] >= 1 else 20000
        if card.id == Riolu:
            return -1 if field_counts[Riolu] + field_counts[Mega_Lucario_ex] >= 2 else 20000
        return 20000

    policy = TRAINER_CARD_POLICIES.get(card.id)
    if policy is None:
        return 10000

    ctx = PlayScoringContext(
        obs=obs, o=o, my_index=my_index, current_plan=current_plan, can_attack=can_attack,
        state=state, my_state=my_state, hand_counts=hand_counts, field_counts=field_counts,
        stadium_id=stadium_id, attacker1=attacker1, rng=rng, op_hand_count=op_hand_count,
    )
    return policy.play_score(ctx)
```

- [ ] **Step 5: `_score_option`のPLAY分岐から`op_state.handCount`を渡す**

`src/lucario_agent/main.py`の667-672行目を以下に置き換える：

```python
        case OptionType.PLAY:
            return _score_play_option(
                obs, o, my_index, current_plan, can_attack,
                state, my_state, hand_counts, field_counts, stadium_id,
                attacker1, op_hand_count=op_state.handCount,
            )
```

- [ ] **Step 6: `JudgePolicy`に閾値ロジックを追加**

`src/lucario_agent/main.py`の563-565行目を以下に置き換える：

```python
class JudgePolicy(TrainerCardPolicy):
    """相手の手札が閾値以上に膨れている場合は最優先で発動する
    （Alakazam系のPsychic Draw×Rare Candyドローエンジン対策。実ログ86139105ほかで、
    相手手札が最大25枚まで膨張しても8敗中5敗でJudgeが一度も使われていなかった問題の修正。
    閾値は暫定値）"""
    OPPONENT_HAND_THRESHOLD = 10

    def play_score(self, ctx: PlayScoringContext) -> int:
        if ctx.op_hand_count >= self.OPPONENT_HAND_THRESHOLD:
            return 9000
        return 7000 if ctx.hand_counts[Basic_Fighting_Energy] == 0 and not ctx.attacker1 else -1
```

- [ ] **Step 7: テストを実行し、Step 1で追加した2件がPASSすることを確認**

Run: `uv run pytest tests/test_lucario_agent.py -k judge -v`
Expected: `test_judge_used_when_hand_is_dead`, `test_judge_held_when_attacker_ready`,
`test_judge_prioritised_when_opponent_hand_is_flooded`,
`test_judge_not_prioritised_when_opponent_hand_below_threshold`の4件全てPASS

- [ ] **Step 8: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS（`_score_play_option`のシグネチャ変更は既存呼び出し元が
すべてキーワード引数で`op_hand_count`を指定していないため、デフォルト値0で
後方互換を維持できているはず。もし失敗した場合は、`_score_play_option`を
位置引数で呼んでいる箇所が無いか`grep -n "_score_play_option(" src/ tests/`で確認する）

- [ ] **Step 9: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
feat(lucario): Judgeに相手手札枚数トリガーを追加（Alakazam系ドローエンジン対策）

op_state.handCountをPlayScoringContextまで配線し、相手の手札が閾値
（暫定10枚）以上に膨れている場合はJudgeを最優先で発動するよう変更。
Alakazam系の深掘り調査で、相手手札が最大25枚まで膨張しても
Judgeが機能していなかった問題への対策。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: DISCARD分岐でJudgeを保護対象に追加する

**Files:**
- Modify: `src/lucario_agent/main.py:438-447`（`_score_card_option`のDISCARD分岐）
- Test: `tests/test_lucario_agent.py:915-988`（`TestDiscardContext`クラス）

**Interfaces:**
- Consumes: 既存の`_score_card_option`引数（変更なし）
- Produces: `_score_card_option(...)`（シグネチャ変更なし、DISCARD分岐の
  戻り値のみ変更。`card.id == lm.Judge`のとき`-100`を返すようになる）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`test_protects_key_supporters`（963-974行目）の
直後に以下を追加：

```python
    def test_protects_judge(self):
        """JudgeはAlakazam系対面での実質唯一の対抗札のため、要注意ポケモンと
        同格で保護する（実ログ86139105, 86374453で、ハイパーボールの捨て札
        コストに巻き込まれて廃棄されていた問題の修正）"""
        judge = Card(id=lm.Judge, serial=1, playerIndex=0)
        obs = self._obs(judge)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == -100
```

- [ ] **Step 2: テストを実行し、想定通り失敗することを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestDiscardContext::test_protects_judge -v`
Expected: FAIL（`assert 10 == -100`、現行コードはJudgeをデフォルト扱いにしている）

- [ ] **Step 3: DISCARD分岐にJudgeを追加**

`src/lucario_agent/main.py`の438-447行目を以下に置き換える：

```python
        case SelectContext.DISCARD:
            if o.playerIndex != my_index:
                return 0
            if card.id == Basic_Fighting_Energy:
                return 50 if hand_counts[Basic_Fighting_Energy] >= 2 else -20
            if card.id in (Riolu, Mega_Lucario_ex, Solrock, Lunatone, Ogerpon_ex, Judge):
                return -100
            if card.id in (Boss_Orders, Lillie_Determination):
                return -50
            return 10
```

- [ ] **Step 4: テストを実行し、`TestDiscardContext`全件がPASSすることを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestDiscardContext -v`
Expected: 6件全てPASS（`test_prefers_spare_fighting_energy`, `test_protects_key_pokemon`,
`test_protects_ogerpon_ex`, `test_protects_key_supporters`, `test_protects_judge`,
`test_default_trainer_is_low_priority_but_positive`）

- [ ] **Step 5: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
fix(lucario): JudgeをDISCARD分岐で誤トラッシュから保護

要注意ポケモンと同格の-100点に設定。Alakazam系対面での実質唯一の
対抗札であるにもかかわらず、ハイパーボールの捨て札コストに
巻き込まれて廃棄されていた問題の修正（実ログ86139105, 86374453）。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 全体回帰確認・実装サマリー作成

**Files:**
- Create: `docs/implementations/20260718-lucario-lillie-judge-priority.md`

**Interfaces:**
- Consumes: Task 1-3で完了した全ての変更
- Produces: 実装サマリードキュメント（CLAUDE.mdフェーズ4の完了条件）

- [ ] **Step 1: リポジトリ全体のテストを実行し、件数と結果を記録する**

Run: `uv run pytest -q`
Expected: 全件PASS。実行結果の末尾（`XXX passed`のサマリー行）を記録しておく
（実装サマリーに記載するため）

- [ ] **Step 2: 変更差分をレビューする**

Run: `git log --oneline -4` と `git diff HEAD~3 -- src/lucario_agent/main.py`
Expected: Task 1-3の3コミットが意図通りの差分になっていることを目視確認

- [ ] **Step 3: 実装サマリーを作成する**

`docs/implementations/20260718-lucario-lillie-judge-priority.md`に以下の構成で記載：
- 背景（`docs/superpowers/specs/2026-07-18-lucario-lillie-judge-priority-design.md`へのリンク）
- 実装内容（Task 1-3の変更点を簡潔に）
- テスト結果（Step 1で記録した件数）
- コミット範囲（`git log`で確認したハッシュ）
- 未対応・次回持ち越し：①ハリテヤマ対策（ミラー戦、ベンチ構成/SWITCH側の改修が必要、
  本計画スコープ外）②オーガポンexのアタッカー化③Alakazam/Kadabra優先撃破仮説の検証
  ④`OPPONENT_HAND_THRESHOLD`（暫定10）・Judge発動スコア（暫定9000）の実測チューニング
  ⑤Kaggle提出ノートブックへの反映・デッキCSV再生成・再提出（ユーザー側で別途実施、
  実装完了後に明示的に確認する）
  ⑥ジャモライコ側`LillieDeterminationPolicy`への同種修正の横展開

- [ ] **Step 4: 実装サマリーをコミット**

```bash
git add docs/implementations/20260718-lucario-lillie-judge-priority.md
git commit -m "$(cat <<'EOF'
docs: リーリエの決意・Judge改修の実装サマリーを追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
