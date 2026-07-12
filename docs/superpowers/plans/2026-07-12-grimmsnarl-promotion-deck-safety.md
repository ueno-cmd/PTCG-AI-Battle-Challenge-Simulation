# グリムスナールex 立ち往生解消＋山札セーフティ 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 855系ログ12件の敗因分析で特定した4つの構造欠落（交代先選出・RETREAT昇格・ボス早出し・山札セーフティ）を`src/grimmsnarl_agent/main.py`に実装し、セルフ対戦A/Bで効果を実測できる状態にする

**Architecture:** 攻撃準備度ヘルパー（`ATTACK_COSTS`＋`_is_attack_ready`）を共通語彙として新設し、既存スコアリング関数にガード節形式で条件を追加する。全修正は`FEATURE_FLAGS`（3キー）でON/OFFでき、全OFF時は現行挙動と完全一致。A/B実験ノートブックは既存の校正実験ビルダーの方式を流用する。

**Tech Stack:** Python 3.12 / uv / pytest / Kaggleノートブック（libcg.soシミュレータ、グラフはplotly）

**設計書:** `docs/superpowers/specs/2026-07-12-grimmsnarl-promotion-deck-safety-design.md`

## Global Constraints

- コードコメント・ドキュメントは日本語（変数名・関数名は英語）
- `coding-gideline.md`（`docs/steering/`参照）準拠：ネスト2階層まで・ガード節優先・複合条件には名前を付ける
- `FEATURE_FLAGS`は3キー（`attacker_promotion` / `boss_attack_gate` / `deck_safety`）全てTrueが本番設定。**全OFF時は現行挙動と完全一致すること**（回帰テストで保証）
- テストコマンドは`uv run pytest -q`（リポジトリ全体。開始時点303件全PASSが前提）
- デッキ本体（`decks/grimmsnarl_20260701.py`）は変更しない（deck.csv再生成不要）
- 作業ブランチ: `feature/grimmsnarl-promotion-deck-safety`（Task 1冒頭で作成）
- ワザコスト・にげるコストはEN_Card_Data.csvで実測確認済みの値を使う：Shadow Bullet=2エネ、Cruel Arrow=3エネ、Spiky Wheel=3エネ、Clutch=1エネ

---

### Task 1: FEATURE_FLAGS・攻撃準備度ヘルパー・FieldState拡張

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`
- Test: `tests/test_grimmsnarl_agent.py`

**Interfaces:**
- Produces: `FEATURE_FLAGS: dict[str, bool]`（モジュールグローバル）、`ATTACK_COSTS: dict[int, int]`、`_is_attack_ready(pokemon) -> bool`、`_expected_damage(pokemon) -> int`、`CLUTCH_DAMAGE = 20`、`FieldState`の新フィールド`my_active_ready` / `bench_ready_attacker` / `my_deck_count` / `my_prize_left` / `my_hand_count`（Task 2〜4が利用）

- [ ] **Step 0: ブランチ作成**

```bash
git checkout -b feature/grimmsnarl-promotion-deck-safety
```

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_grimmsnarl_agent.py`の`TestCollectFieldState`クラスの直後に追加：

```python
# ==================== 攻撃準備度ヘルパー ====================
class TestAttackReadiness:
    def test_grimmsnarl_ready_with_2_energies(self):
        """Shadow Bulletは{D}{D}=2エネ（EN_Card_Data.csvで実測確認済み）"""
        assert gm._is_attack_ready(make_pokemon(id=gm.Grimmsnarl_ex, energies=[7, 7])) is True

    def test_grimmsnarl_not_ready_with_1_energy(self):
        assert gm._is_attack_ready(make_pokemon(id=gm.Grimmsnarl_ex, energies=[7])) is False

    def test_fezandipiti_needs_3_energies(self):
        """Cruel Arrowは無色3"""
        assert gm._is_attack_ready(make_pokemon(id=gm.Fezandipiti_ex, energies=[7, 7])) is False
        assert gm._is_attack_ready(make_pokemon(id=gm.Fezandipiti_ex, energies=[7, 7, 7])) is True

    def test_morpeko_needs_3_energies(self):
        """Spiky Wheelは無色3（従来想定の2ではない）"""
        assert gm._is_attack_ready(make_pokemon(id=gm.Marnie_Morpeko, energies=[7, 7])) is False
        assert gm._is_attack_ready(make_pokemon(id=gm.Marnie_Morpeko, energies=[7, 7, 7])) is True

    def test_yveltal_ready_with_1_energy(self):
        """Clutch（わしづかみ）は{D}=1エネ"""
        assert gm._is_attack_ready(make_pokemon(id=gm.Yveltal, energies=[7])) is True

    def test_non_attacker_never_ready(self):
        """コスト表にないポケモン（特性専用等）はエネルギーがあっても準備完了扱いしない"""
        assert gm._is_attack_ready(make_pokemon(id=gm.Shaymin, energies=[7, 7, 7, 7])) is False


class TestExpectedDamage:
    def test_grimmsnarl_expected_damage(self):
        assert gm._expected_damage(make_pokemon(id=gm.Grimmsnarl_ex, energies=[7, 7])) == 180

    def test_fezandipiti_expected_damage(self):
        assert gm._expected_damage(make_pokemon(id=gm.Fezandipiti_ex, energies=[7, 7, 7])) == 100

    def test_morpeko_expected_damage_scales_with_energy(self):
        """スパイキーホイール: 20+40×装着エネ数"""
        assert gm._expected_damage(make_pokemon(id=gm.Marnie_Morpeko, energies=[7, 7, 7])) == 140

    def test_yveltal_expected_damage(self):
        assert gm._expected_damage(make_pokemon(id=gm.Yveltal, energies=[7])) == 20

    def test_unknown_pokemon_expected_damage_is_zero(self):
        assert gm._expected_damage(make_pokemon(id=gm.Shaymin)) == 0


class TestFieldStateReadiness:
    def test_active_e0_bench_ready_detected(self):
        """実ログ85534500の状況：アクティブがエネ0、ベンチにエネ6のオーロンゲ"""
        fezandipiti = make_pokemon(id=gm.Fezandipiti_ex, hp=210, energies=[])
        grimmsnarl  = make_pokemon(id=gm.Grimmsnarl_ex, hp=320, energies=[7] * 6)
        my_ps = make_player_state(active_pokemon=fezandipiti, bench=[grimmsnarl])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.my_active_ready is False
        assert fs.bench_ready_attacker is True

    def test_active_ready_detected(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex, energies=[7, 7]))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.my_active_ready is True
        assert fs.bench_ready_attacker is False

    def test_deck_prize_hand_counts_collected(self):
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex),
            hand=[Card(id=gm.Rare_Candy, serial=1, playerIndex=0)],
            deck_count=12,
            prize_count=4,
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.my_deck_count == 12
        assert fs.my_prize_left == 4
        assert fs.my_hand_count == 1

    def test_hand_count_ignores_none_entries(self):
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex),
            hand=[None, Card(id=gm.Rare_Candy, serial=1, playerIndex=0)],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.my_hand_count == 1
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_grimmsnarl_agent.py::TestAttackReadiness tests/test_grimmsnarl_agent.py::TestExpectedDamage tests/test_grimmsnarl_agent.py::TestFieldStateReadiness -q`
Expected: FAIL（`AttributeError: module ... has no attribute '_is_attack_ready'`等）

- [ ] **Step 3: 実装**

`src/grimmsnarl_agent/main.py`に以下を追加。

(a) `TUNABLE_WEIGHTS`辞書の直後（現72行目付近）：

```python
# ==================== 新ルールのON/OFFフラグ（セルフ対戦A/B用） ====================
# 855系ログ12件の敗因分析で特定した構造欠落への対策。全てTrueが本番設定。
# A/B実験ノートブック側からこの辞書を clear()+update() で差し替えて効果を実測する。
# 設計書: docs/superpowers/specs/2026-07-12-grimmsnarl-promotion-deck-safety-design.md
FEATURE_FLAGS = {
    "attacker_promotion": True,  # 交代先選出の攻撃準備度優先＋RETREAT昇格（修正①②）
    "boss_attack_gate":   True,  # ボスの指令の攻撃可否ゲート（修正③）
    "deck_safety":        True,  # 山札セーフティ（修正④）
}
```

(b) `SPIKY_WHEEL_DAMAGE_PER_ENERGY`定数の直後（現315行目付近）：

```python
CLUTCH_DAMAGE = 20  # Yveltalのわしづかみ（Clutch {D}）の与ダメージ

# ==================== 攻撃準備度（交代・撤退・ボス判断の共通語彙） ====================
# ワザの必要エネルギー数（本デッキは全て悪エネルギーで支払える。EN_Card_Data.csvで実測確認済み）
ATTACK_COSTS = {
    Grimmsnarl_ex:  2,  # Shadow Bullet {D}{D}
    Fezandipiti_ex: 3,  # Cruel Arrow ●●●
    Marnie_Morpeko: 3,  # Spiky Wheel ●●●
    Yveltal:        1,  # Clutch {D}
}


def _is_attack_ready(pokemon: "Pokemon") -> bool:
    """このポケモンは装着済みエネルギーで攻撃できるか"""
    need = ATTACK_COSTS.get(pokemon.id)
    return need is not None and len(pokemon.energies) >= need


def _expected_damage(pokemon: "Pokemon") -> int:
    """交代先の同点比較用の期待ダメージ（実ダメージ計算はシミュレータが行う）"""
    if pokemon.id == Grimmsnarl_ex:
        return SHADOW_BULLET_DAMAGE
    if pokemon.id == Fezandipiti_ex:
        return CRUEL_ARROW_DAMAGE
    if pokemon.id == Marnie_Morpeko:
        return SPIKY_WHEEL_BASE_DAMAGE + len(pokemon.energies) * SPIKY_WHEEL_DAMAGE_PER_ENERGY
    if pokemon.id == Yveltal:
        return CLUTCH_DAMAGE
    return 0
```

(c) `FieldState`の末尾にデフォルト値付きフィールドを追加（既存テストの`FieldState(**defaults)`を壊さないため全てデフォルト付き。`my_deck_count`のデフォルト60は「ゲート不発動」の安全側）：

```python
    my_active_ready:      bool = False
    bench_ready_attacker: bool = False
    my_deck_count:        int  = 60
    my_prize_left:        int  = 6
    my_hand_count:        int  = 0
```

(d) `_collect_field_state`のreturn直前に計算を追加し、returnに5フィールドを渡す：

```python
    my_active_ready = any(
        _is_attack_ready(card) for card in my_state.active if card is not None
    )
    bench_ready_attacker = any(
        _is_attack_ready(card) for card in my_state.bench if card is not None
    )
```

```python
        my_active_ready=my_active_ready,
        bench_ready_attacker=bench_ready_attacker,
        my_deck_count=my_state.deckCount,
        my_prize_left=len(my_state.prize),
        my_hand_count=sum(1 for card in my_state.hand if card is not None),
```

- [ ] **Step 4: テストがPASSすることを確認**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -q`
Expected: 全件PASS（既存テスト含む）

- [ ] **Step 5: コミット**

```bash
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "feat: 攻撃準備度ヘルパーとFEATURE_FLAGSを新設（立ち往生対策の基盤）"
```

---

### Task 2: 修正①② 交代先選出の攻撃準備度優先＋RETREAT昇格

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`（`_score_own_switch_target`と`agent()`内`OptionType.RETREAT`分岐）
- Test: `tests/test_grimmsnarl_agent.py`

**Interfaces:**
- Consumes: Task 1の`FEATURE_FLAGS` / `_is_attack_ready` / `_expected_damage` / `fs.my_active_ready` / `fs.bench_ready_attacker`
- Produces: なし（スコアリング挙動の変更のみ）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_grimmsnarl_agent.py`の`_score_card_option`関連テストクラス（`test_to_active_own_pokemon_still_prefers_grimmsnarl`があるクラス）に追加：

```python
    def test_to_active_prefers_ready_grimmsnarl_over_e0_wall(self):
        """実ログ85534500の再現：エネ6のベンチオーロンゲは、エネ0のキチキギスex（壁）より
        優先してバトル場に出されること（立ち往生の入口対策）"""
        grimmsnarl  = make_pokemon(id=gm.Grimmsnarl_ex, hp=320, energies=[7] * 6)
        fezandipiti = make_pokemon(id=gm.Fezandipiti_ex, hp=210, energies=[])
        fs = self._make_fs()
        assert gm._score_own_switch_target(grimmsnarl, fs) > gm._score_own_switch_target(fezandipiti, fs)

    def test_ready_morpeko_outranks_unready_grimmsnarl(self):
        """新優先順位の明示：攻撃準備完了のモルペコ（エネ3）は未準備のオーロンゲ（エネ0）より優先。
        従来はオーロンゲが無条件で最優先だったが、攻撃できないオーロンゲを前に出しても
        立ち往生するだけなので、今攻撃できる方を選ぶ"""
        morpeko    = make_pokemon(id=gm.Marnie_Morpeko, hp=70, energies=[7, 7, 7])
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, hp=320, energies=[])
        fs = self._make_fs()
        assert gm._score_own_switch_target(morpeko, fs) > gm._score_own_switch_target(grimmsnarl, fs)

    def test_ready_grimmsnarl_outranks_ready_fezandipiti(self):
        """準備完了同士は期待ダメージで比較（オーロンゲ180 > キチキギス100）"""
        grimmsnarl  = make_pokemon(id=gm.Grimmsnarl_ex, hp=320, energies=[7, 7])
        fezandipiti = make_pokemon(id=gm.Fezandipiti_ex, hp=210, energies=[7, 7, 7])
        fs = self._make_fs()
        assert gm._score_own_switch_target(grimmsnarl, fs) > gm._score_own_switch_target(fezandipiti, fs)

    def test_crustle_morpeko_still_top_even_over_ready_grimmsnarl(self):
        """Crustle対面では準備完了のオーロンゲより非exモルペコが優先されること（既存挙動の維持）"""
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, hp=320, energies=[7, 7])
        morpeko    = make_pokemon(id=gm.Marnie_Morpeko, hp=70, energies=[7])
        fs = self._make_fs(op_active_id=gm.Crustle)
        assert gm._score_own_switch_target(morpeko, fs) > gm._score_own_switch_target(grimmsnarl, fs)

    def test_promotion_flag_off_restores_old_priority(self, monkeypatch):
        """attacker_promotion=Falseなら現行挙動（オーロンゲ無条件最優先）に戻ること"""
        monkeypatch.setitem(gm.FEATURE_FLAGS, "attacker_promotion", False)
        morpeko    = make_pokemon(id=gm.Marnie_Morpeko, hp=70, energies=[7, 7, 7])
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, hp=320, energies=[])
        fs = self._make_fs()
        assert gm._score_own_switch_target(grimmsnarl, fs) > gm._score_own_switch_target(morpeko, fs)
```

agent()レベルのテスト（`test_retreats_when_grimmsnarl_low_hp`があるクラスに追加）：

```python
    def test_retreats_when_active_cannot_attack_and_bench_ready(self):
        """アクティブが攻撃不能（キチキギスexエネ0）でベンチに準備完了のオーロンゲ（エネ2）が
        いるなら、ENDより撤退を優先すること（855系ログの立ち往生対策・昇格ルール）"""
        wall  = make_pokemon(id=gm.Fezandipiti_ex, hp=210, energies=[])
        ready = make_pokemon(id=gm.Grimmsnarl_ex, hp=320, energies=[7, 7])
        my_ps = make_player_state(active_pokemon=wall, bench=[ready])
        options = [
            Option(type=OptionType.RETREAT),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(my_state=my_ps, options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.RETREAT

    def test_does_not_retreat_when_bench_not_ready(self):
        """ベンチのアタッカーも未準備（エネ1のオーロンゲ）なら撤退しないこと"""
        wall     = make_pokemon(id=gm.Fezandipiti_ex, hp=210, energies=[])
        unready  = make_pokemon(id=gm.Grimmsnarl_ex, hp=320, energies=[7])
        my_ps = make_player_state(active_pokemon=wall, bench=[unready])
        options = [
            Option(type=OptionType.RETREAT),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(my_state=my_ps, options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.END

    def test_does_not_retreat_when_active_is_ready(self):
        """アクティブ自身が攻撃可能（モルペコエネ3）なら昇格条件は発動しないこと"""
        ready_active = make_pokemon(id=gm.Marnie_Morpeko, hp=70, energies=[7, 7, 7])
        ready_bench  = make_pokemon(id=gm.Grimmsnarl_ex, hp=320, energies=[7, 7])
        my_ps = make_player_state(active_pokemon=ready_active, bench=[ready_bench])
        options = [
            Option(type=OptionType.RETREAT),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(my_state=my_ps, options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.END

    def test_promotion_retreat_flag_off_keeps_current(self, monkeypatch):
        """attacker_promotion=Falseなら立ち往生状態でも撤退しない（現行挙動）こと"""
        monkeypatch.setitem(gm.FEATURE_FLAGS, "attacker_promotion", False)
        wall  = make_pokemon(id=gm.Fezandipiti_ex, hp=210, energies=[])
        ready = make_pokemon(id=gm.Grimmsnarl_ex, hp=320, energies=[7, 7])
        my_ps = make_player_state(active_pokemon=wall, bench=[ready])
        options = [
            Option(type=OptionType.RETREAT),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(my_state=my_ps, options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.END
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -q`
Expected: 上記の新テストのみFAIL

- [ ] **Step 3: 実装**

(a) `_score_own_switch_target`のCrustle分岐の直後に追加（docstringにも新優先順位を追記）：

```python
    if FEATURE_FLAGS["attacker_promotion"] and _is_attack_ready(card):
        # 攻撃準備完了のアタッカーは最優先で前に出す（855系ログ12件で7敗に関与した
        # 「立ち往生」の入口対策）。準備完了同士は期待ダメージが大きい方を選ぶ
        return 12000 + _expected_damage(card)
```

(b) `agent()`の`OptionType.RETREAT`分岐に昇格条件を追加：

```python
            case OptionType.RETREAT:
                # Grimmsnarl exが瀕死（想定される大技の一撃=180ダメ以下しか耐えられない）なら逃げる。
                # あるいは、ex攻撃者（Grimmsnarl_ex/Fezandipiti_ex）でCrustle対面（技ダメージ無効化）
                # かつベンチにモルペコがいるなら、非exのモルペコに交代して攻撃を通す。
                # さらに、アクティブが攻撃不能でベンチに準備完了アタッカーがいる場合も
                # 撤退して昇格させる（855系ログの立ち往生対策）
                crustle_matchup = (
                    fs.op_active_id == Crustle
                    and fs.my_active_id in EX_ATTACKER_IDS
                    and fs.morpeko_bench_idx != -1
                )
                promotion_needed = (
                    FEATURE_FLAGS["attacker_promotion"]
                    and not fs.my_active_ready
                    and fs.bench_ready_attacker
                )
                if (fs.grimmsnarl_active and fs.my_active_hp <= 180) or crustle_matchup or promotion_needed:
                    score = 3000
                else:
                    score = -1
```

- [ ] **Step 4: テストがPASSすることを確認（既存テストの回帰含む）**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -q`
Expected: 全件PASS。特に既存の`test_switch_grimmsnarl_still_preferred_when_opponent_is_not_crustle`（オーロンゲE2=準備完了は新分岐でも最優先のまま）と`test_attacks_for_lethal_instead_of_retreating`（確定KO攻撃5000 > RETREAT3000は不変）がPASSすること

- [ ] **Step 5: コミット**

```bash
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "feat: 交代先選出の攻撃準備度優先とRETREAT昇格ルールを追加（立ち往生対策）"
```

---

### Task 3: 修正③ ボスの指令の攻撃可否ゲート

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`（`_score_play`のBoss_Orders分岐）
- Test: `tests/test_grimmsnarl_agent.py`（新テスト追加＋既存ボステスト6件の前提条件更新）

**Interfaces:**
- Consumes: Task 1の`FEATURE_FLAGS["boss_attack_gate"]` / `fs.my_active_ready`

- [ ] **Step 1: 失敗するテストを書く**

`TestScorePlay`クラスに追加：

```python
    def test_boss_suppressed_when_active_cannot_attack(self):
        """自分のアクティブが攻撃不能なら、KO確定対象がベンチにいてもボスの指令は温存すること
        （855系ログで負け6試合がT2〜T5に浪費していた対策）"""
        fs = self._make_fs(op_bench_hp=[100], my_active_ready=False)
        assert gm._score_play(gm.Boss_Orders, fs, prize_count=6) == -1

    def test_boss_epsilon_also_suppressed_when_active_cannot_attack(self):
        """ε探索（先出し）も攻撃可否ゲートの内側であること（乱数が探索側でも温存）"""
        fs = self._make_fs(op_bench_hp=[300], my_active_ready=False)
        rng = type("StubRng", (), {"random": lambda self: 0.0})()
        assert gm._score_play(gm.Boss_Orders, fs, prize_count=6, rng=rng) == -1

    def test_boss_immediate_when_ko_target_and_active_ready(self):
        """アクティブが攻撃可能でKO確定対象がいれば従来通り即使用（8800）"""
        fs = self._make_fs(op_bench_hp=[100], my_active_ready=True)
        assert gm._score_play(gm.Boss_Orders, fs, prize_count=6) == 8800

    def test_boss_gate_flag_off_keeps_current(self, monkeypatch):
        """boss_attack_gate=Falseなら攻撃不能でも現行挙動（KO確定なら8800）"""
        monkeypatch.setitem(gm.FEATURE_FLAGS, "boss_attack_gate", False)
        fs = self._make_fs(op_bench_hp=[100], my_active_ready=False)
        assert gm._score_play(gm.Boss_Orders, fs, prize_count=6) == 8800
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_grimmsnarl_agent.py::TestScorePlay -q`
Expected: 新テスト4件のうち`test_boss_suppressed_when_active_cannot_attack`と`test_boss_epsilon_also_suppressed_when_active_cannot_attack`がFAIL

- [ ] **Step 3: 実装**

`_score_play`のBoss_Orders分岐の冒頭にガード節を追加：

```python
    if card_id == Boss_Orders:
        if FEATURE_FLAGS["boss_attack_gate"] and not fs.my_active_ready:
            # 自分が今ターン攻撃できないなら、引きずり出してもダメージゼロで
            # サポート権だけ失う（855系ログで負け6試合がT2〜T5に浪費）。温存する
            return -1
        if not fs.op_bench_hp:
            return -1  # 対象不在なら温存
        （以下、現行のまま）
```

- [ ] **Step 4: 既存ボステスト6件の前提条件を新仕様に合わせて更新**

ゲート追加により「アクティブ攻撃可能」が前提になるため、以下の既存テストを更新する：

- `TestScorePlay`内の4件（`test_boss_orders_high_when_ko_target_exists` / `test_boss_orders_holds_when_no_ko_target_and_rng_above_epsilon` / `test_boss_orders_explores_when_rng_below_epsilon` / `test_boss_orders_holds_when_bench_empty_even_if_rng_favors_explore`）：`self._make_fs(...)`の引数に`my_active_ready=True`を追加
- agent()レベルの2件（`test_prefers_boss_orders_when_ko_target_available` / `test_holds_boss_orders_when_no_ko_target`）：アクティブの生成を`make_pokemon(id=gm.Grimmsnarl_ex)`から`make_pokemon(id=gm.Grimmsnarl_ex, energies=[7, 7])`に変更（攻撃可能な状態にしてゲート以外のロジックをテストし続ける）

- [ ] **Step 5: テストがPASSすることを確認**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -q`
Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "feat: ボスの指令に攻撃可否ゲートを追加（攻撃不能ターンの浪費防止）"
```

---

### Task 4: 修正④ 山札セーフティ（battlecore B方式）

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`（定数`Secret_Box`追加、`_safe_draws`/`_deck_consumption`新設、`_score_play`冒頭にゲート追加）
- Test: `tests/test_grimmsnarl_agent.py`

**Interfaces:**
- Consumes: Task 1の`FEATURE_FLAGS["deck_safety"]` / `fs.my_deck_count` / `fs.my_prize_left` / `fs.my_hand_count`
- Produces: `_safe_draws(fs) -> int`、`_deck_consumption(card_id, fs) -> int | None`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_grimmsnarl_agent.py`に新クラスを追加（`TestScorePlay`の直後）：

```python
# ==================== 山札セーフティ（battlecore B方式） ====================
class TestDeckSafety:
    def _make_fs(self, **kwargs):
        defaults = dict(
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int),
            discard_counts=defaultdict(int),
            grimmsnarl_active=False,
            grimmsnarl_energy_count=0,
            impidimp_bench_idx=-1,
            morpeko_bench_idx=-1,
            morpeko_energy_count=0,
            rare_candy_in_hand=False,
            my_active_hp=200,
            my_active_id=0,
            op_active_hp=200,
            op_active_id=0,
            op_bench_hp=[],
        )
        defaults.update(kwargs)
        return gm.FieldState(**defaults)

    def test_safe_draws_formula(self):
        """safe_draws = 山札残 − 残りプライズ − 1（残りプライズ≒残りターン数の必須ドロー分を温存）"""
        fs = self._make_fs(my_deck_count=12, my_prize_left=4)
        assert gm._safe_draws(fs) == 7

    def test_cheren_suppressed_when_deck_thin(self):
        """チェレン（3枚ドロー）はsafe_drawsが3未満なら温存"""
        fs = self._make_fs(my_deck_count=5, my_prize_left=4)  # safe_draws=0
        assert gm._score_play(gm.Cheren, fs, prize_count=4) == -1

    def test_cheren_allowed_when_deck_healthy(self):
        fs = self._make_fs(my_deck_count=30, my_prize_left=4)
        assert gm._score_play(gm.Cheren, fs, prize_count=4) == 2200

    def test_lillie_big_hand_replenishes_deck_so_not_gated(self):
        """リーリエは手札を山札に戻してから引くため、手札が多いなら山札が痩せず温存不要
        （実ログ85541203：手札11枚のままデッキアウトした状況では、むしろ使うべきだった）"""
        fs = self._make_fs(my_deck_count=5, my_prize_left=3, my_hand_count=11)
        # 消費 = max(0, 6 - (11-1)) = 0 → ゲート発動せず通常スコア
        assert gm._score_play(gm.Lillie_Determination, fs, prize_count=3) == 3500

    def test_lillie_small_hand_gated_when_deck_thin(self):
        """手札が少ないリーリエは実質大量ドロー。山札が細ければ温存"""
        fs = self._make_fs(my_deck_count=5, my_prize_left=3, my_hand_count=2)
        # 消費 = max(0, 6 - (2-1)) = 5 > safe_draws=1 → 温存
        assert gm._score_play(gm.Lillie_Determination, fs, prize_count=3) == -1

    def test_lillie_draws_8_when_six_prizes(self):
        """残りプライズ6ならリーリエは8枚ドローとして消費を計算"""
        fs = self._make_fs(my_deck_count=10, my_prize_left=6, my_hand_count=2)
        # 消費 = max(0, 8 - 1) = 7 > safe_draws=3 → 温存
        assert gm._score_play(gm.Lillie_Determination, fs, prize_count=6) == -1

    def test_secret_box_gated(self):
        fs = self._make_fs(my_deck_count=7, my_prize_left=3)  # safe_draws=3 < 消費4
        assert gm._score_play(gm.Secret_Box, fs, prize_count=3) == -1

    def test_pokepad_gated_only_at_the_very_end(self):
        """サーチ1枚系（ポケパッド等）は消費1なので、safe_drawsが1以上なら使える"""
        fs_ok  = self._make_fs(my_deck_count=5, my_prize_left=3)  # safe_draws=1
        fs_ng  = self._make_fs(my_deck_count=4, my_prize_left=3)  # safe_draws=0
        assert gm._score_play(gm.Poke_Pad, fs_ok, prize_count=3) == 4000
        assert gm._score_play(gm.Poke_Pad, fs_ng, prize_count=3) == -1

    def test_night_stretcher_never_gated(self):
        """ナイトストレッチャーはトラッシュ回収で山札を消費しないため対象外"""
        fs = self._make_fs(my_deck_count=1, my_prize_left=6)
        assert gm._score_play(gm.Night_Stretcher, fs, prize_count=6) == 2000

    def test_deck_safety_flag_off_keeps_current(self, monkeypatch):
        """deck_safety=Falseなら山札が細くても現行挙動"""
        monkeypatch.setitem(gm.FEATURE_FLAGS, "deck_safety", False)
        fs = self._make_fs(my_deck_count=5, my_prize_left=4)
        assert gm._score_play(gm.Cheren, fs, prize_count=4) == 2200
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_grimmsnarl_agent.py::TestDeckSafety -q`
Expected: FAIL（`_safe_draws`未定義等）

- [ ] **Step 3: 実装**

(a) トレーナーズ定数群（`Team_Rocket_Petrel = 1219`の行の後）に追加：

```python
Secret_Box             = 1092
```

(b) `_score_play`の直前にヘルパーを追加：

```python
# ==================== 山札セーフティ（battlecore B方式） ====================
def _safe_draws(fs: FieldState) -> int:
    """安全に消費できる山札枚数。残りプライズ数を残りターン数の見積もりとして使い、
    毎ターンの必須ドロー分を温存する（デッキアウト防止。実ログ85541203が直接の動機）"""
    return fs.my_deck_count - fs.my_prize_left - 1


def _deck_consumption(card_id: int, fs: FieldState) -> "int | None":
    """このカードを使った場合の山札の正味消費枚数。山札を消費しない札はNone"""
    if card_id == Lillie_Determination:
        draws = 8 if fs.my_prize_left == 6 else 6
        # 手札（本札自身を除く）を山札に戻してから引くため、戻す分を差し引く。
        # 手札が多いときは山札がむしろ回復するので消費0として扱う
        return max(0, draws - (fs.my_hand_count - 1))
    if card_id == Cheren:
        return 3
    if card_id == Secret_Box:
        return 4
    if card_id == Buddy_Buddy_Poffin:
        return 2
    if card_id in (Poke_Pad, Team_Rocket_Petrel, Grimsley_Move):
        return 1
    return None
```

(c) `_score_play`のdocstring直後にガード節を追加：

```python
    if FEATURE_FLAGS["deck_safety"]:
        consumption = _deck_consumption(card_id, fs)
        if consumption is not None and consumption > _safe_draws(fs):
            return -1  # 山札温存（デッキアウト防止、battlecore B方式）
```

- [ ] **Step 4: テストがPASSすることを確認**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -q`
Expected: 全件PASS（既存の`TestScorePlay`はFieldStateデフォルト`my_deck_count=60`によりゲート不発動でそのままPASS）

- [ ] **Step 5: コミット**

```bash
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "feat: 山札セーフティを追加（battlecore B方式、デッキアウト防止）"
```

---

### Task 5: セルフ対戦A/B実験ノートブックのビルダー

**Files:**
- Create: `scripts/build_grimmsnarl_feature_ab_notebook.py`
- 生成物: `src/rl_experiments/grimmsnarl_feature_ab_experiment.ipynb`（.gitignore対象、コミットしない）
- 参照（読むだけ）: `scripts/build_grimmsnarl_calibration_notebook.py`

**Interfaces:**
- Consumes: Task 1の`FEATURE_FLAGS`（埋め込まれたmain.py内のモジュールグローバル）
- Produces: Kaggleで実行するとA/B結果JSON（`/kaggle/working/feature_ab_results.json`）を出力するノートブック

- [ ] **Step 1: ビルダーを作成**

`scripts/build_grimmsnarl_calibration_notebook.py`をベースに`scripts/build_grimmsnarl_feature_ab_notebook.py`を作成する。流用と変更の対応：

- **そのまま流用**：`code_cell`/`md_cell`ヘルパー、`COPY_CELL_IDS`による参照ノートブックからの環境セットアップセル複製、デッキ読み込みセル（`load_grimmsnarl_deck`）、main.py全文自動埋め込みの仕組み、`play_game`セル、plotlyグラフセルの構成、`main()`の検証ロジック
- **削除**：影武者カウント関連（`_recording_score_attach`/`_call_with_weights`/`make_shadow_agent`/`SHADOW_STATS`とその集計セル）
- **差し替え**：実験セルを以下の`AB_CODE`に（`run_series`は校正ビルダーの同名関数をそのまま含める）：

```python
AB_CODE = '''# ==================== 新ルールA/B実験（FEATURE_FLAGS ON vs OFF） ====================
import time

GAMES = 1000  # 7/12の校正実験の教訓：200試合では±7ptブレる。1000試合で±3pt精度
CHECKPOINTS = [100, 200, 400, 600, 800, 1000]

FLAGS_ON  = {"attacker_promotion": True,  "boss_attack_gate": True,  "deck_safety": True}
FLAGS_OFF = {"attacker_promotion": False, "boss_attack_gate": False, "deck_safety": False}

DEFAULT_TUNABLE = dict(TUNABLE_WEIGHTS)


def make_flagged_agent(flags: dict):
    """FEATURE_FLAGS（モジュールグローバル）を対局のたびに差し替えるエージェントを作る。
    TUNABLE_WEIGHTSは両設定ともデフォルト値に固定し、フラグの効果だけを比較する"""
    def _agent(obs_dict):
        FEATURE_FLAGS.clear()
        FEATURE_FLAGS.update(flags)
        TUNABLE_WEIGHTS.clear()
        TUNABLE_WEIGHTS.update(DEFAULT_TUNABLE)
        return grimmsnarl_agent(obs_dict)
    return _agent


def run_series(agent_a, agent_b, games, label):
    """agent_a側の視点で対戦を繰り返す。先手後手の偏りを消すため1試合ごとに座席を交代する"""
    results = []
    t0 = time.time()
    for i in range(games):
        if i % 2 == 0:
            r = play_game(agent_a, agent_b, DECK, DECK)
        else:
            r = -play_game(agent_b, agent_a, DECK, DECK)
        results.append(r)
        n = i + 1
        if n in CHECKPOINTS:
            wins = sum(1 for x in results if x > 0)
            losses = sum(1 for x in results if x < 0)
            print(f"[{label}] {n:>4}試合: A勝={wins:>4} A負={losses:>4} 引分={n - wins - losses:>4} A勝率={wins / n:.3f}")
    elapsed = time.time() - t0
    print(f"[{label}] 計{games}試合 {elapsed:.1f}秒（{elapsed / games * 1000:.0f}ms/試合）")
    return {"label": label, "results": results, "elapsed_sec": elapsed}


series_ab = run_series(
    make_flagged_agent(FLAGS_ON), make_flagged_agent(FLAGS_OFF),
    GAMES, "A(新ルールON) vs B(OFF)",
)
series_aa = run_series(
    make_flagged_agent(FLAGS_ON), make_flagged_agent(FLAGS_ON),
    GAMES, "A vs A(ノイズ基準)",
)
'''
```

- **結果保存セル**：`/kaggle/working/feature_ab_results.json`に`{"series_ab": ..., "series_aa": ..., "games": GAMES, "flags_on": FLAGS_ON}`を保存（校正ビルダーの保存セルと同じ形式）
- **`main()`の検証**：`if "FEATURE_FLAGS" not in agent_source: raise RuntimeError(...)`を追加（`TUNABLE_WEIGHTS`チェックと同様）
- **ノートブック冒頭のmdセル**：実験目的（A=4修正ON vs B=OFF、勝率+5pt以上で効果あり判定、A vs Aはノイズ基準）を記載

- [ ] **Step 2: ノートブック生成と静的検証**

```bash
uv run python scripts/build_grimmsnarl_feature_ab_notebook.py
uv run python -c "
import json, ast
nb = json.load(open('src/rl_experiments/grimmsnarl_feature_ab_experiment.ipynb'))
print('セル数:', len(nb['cells']))
for i, c in enumerate(nb['cells']):
    if c['cell_type'] == 'code':
        ast.parse(''.join(c['source']))
print('全コードセルAST構文OK')
src = ''.join(''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code')
assert 'FEATURE_FLAGS' in src and 'make_flagged_agent' in src and 'GAMES = 1000' in src
print('埋め込み検証OK')
"
```

Expected: セル数表示、AST構文OK、埋め込み検証OK

- [ ] **Step 3: コミット（ビルダースクリプトのみ。生成ノートブックは.gitignore対象）**

```bash
git add scripts/build_grimmsnarl_feature_ab_notebook.py
git commit -m "feat: 新ルールA/B実験ノートブックのビルダーを追加（1000試合×2系列）"
```

---

### Task 6: 全体回帰・校正ノートブック追従・実装サマリー

**Files:**
- Create: `docs/implementations/20260712-grimmsnarl-promotion-deck-safety.md`
- 再生成: `src/rl_experiments/grimmsnarl_calibration_experiment.ipynb`（.gitignore対象）

- [ ] **Step 1: リポジトリ全体の回帰テスト**

Run: `uv run pytest -q`
Expected: 全件PASS（開始時303件＋本計画の新規約30件）

- [ ] **Step 2: 既存の校正ノートブックをmain.py変更に追従させる**

```bash
uv run python scripts/build_grimmsnarl_calibration_notebook.py
```

Expected: エラーなく再生成される（FEATURE_FLAGS全Trueのmain.pyが埋め込まれる）

- [ ] **Step 3: 実装サマリーを作成**

`docs/implementations/20260712-grimmsnarl-promotion-deck-safety.md`に以下を記載：

- 背景（855系ログ12件の敗因分析→4修正）と設計書・計画書へのリンク
- 変更ファイル・コミット一覧
- 各修正の内容と対応するテスト
- 設計書「リスクと備考」の確認結果：Shadow Bullet=2エネ確定と既存エネルギー配分ロジックの整合
  （`_score_attach`の現行コメント「シャドーバレット（悪悪=2エネ）」および`grimmsnarl_energy_count >= 2`
  ゲートは既に2エネ前提のため齟齬なし、と確認できたことを記録する。齟齬が見つかった場合は
  修正せずサマリーに記録して報告する）
- 未実施事項：セルフ対戦A/B実験のKaggle実行（ユーザー作業）、提出ノートブック更新、Kaggle再提出

- [ ] **Step 4: コミット**

```bash
git add docs/implementations/20260712-grimmsnarl-promotion-deck-safety.md
git commit -m "docs: 立ち往生解消＋山札セーフティの実装サマリーを追加"
```

---

## 実装完了後の手順（ユーザー作業＋次セッション）

1. `src/rl_experiments/grimmsnarl_feature_ab_experiment.ipynb`をKaggleにアップロードして実行（想定約4分：1000試合×2系列×約92ms/試合＋環境構築）
2. `feature_ab_results.json`をダウンロードし`data/experiments/20260712_grimmsnarl_feature_ab.json`として保存
3. **判定基準**：A(ON) vs B(OFF)の勝率が**55%以上**（+5pt以上、ノイズ±3ptの外）なら効果ありと判定
   - 効果あり → `scripts/build_grimmsnarl_calibration_notebook.py`は再実行済みなので、`src/sample_notebook/grimmsnarl_agent.ipynb`のセル0を現行main.py全文で差し替え→Kaggle再提出
   - 効果なし/悪化 → A vs Aのノイズ基準と比較して原因を切り分け、フラグ単位のA/B（1修正ずつON）で犯人を特定
4. 提出後、次の855系ログで「立ち往生手番数」「攻撃不能ターンのボス使用回数」「終局時山札残数」の3指標を再計測（計測スクリプトは本分析のscratchpad版を流用）
