# ジャモライコエージェント EnergyPolicyクラス導入 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/superpowers/specs/2026-07-14-jamoraiko-energy-policy-class-design.md`に基づき、`src/jamoraiko_agent/main.py`に散らばっているエネルギー関連ロジックを`EnergyPolicy`クラスへ集約し、あわせて`OptionType.ENERGY_CARD`（`SWITCH_ENERGY_CARD`／`DISCARD_ENERGY_CARD`）の未実装バグを修正する。

**Architecture:** Task 1で既存のエネルギー関連自由関数を`EnergyPolicy`クラスへ振る舞いを変えずに移植し、Task 2で新規メソッド（`switch_source_score`／`discard_for_damage_score`）と`OptionType.ENERGY_CARD`ディスパッチを追加、あわせて実戦で一度も通らないと確認済みのデッドコード（`DETACH_FROM`分岐・`OptionType.ENERGY`分岐）を削除する。

**Tech Stack:** Python 3.12 / pytest / dataclasses（既存プロジェクト構成を継続）

## Global Constraints

- 全コード内コメント・ドキュメントは日本語で書く（CLAUDE.md ルール）
- 既存の491件のテストスイート全体が最後まで回帰なく通ること（各タスク末尾で`uv run pytest -q`を実行）
- `EnergyPolicy`はモジュールレベルで`ENERGY_POLICY = EnergyPolicy()`として1個だけ生成し、状態を持たない（`SURPLUS_THRESHOLD`はクラス属性）
- 旧自由関数（`energy_score`・`_find_energy_switch_source`・`_raging_bolt_ex_needs_lightning`・`_raging_bolt_ex_has_growth_path`・`_score_energy_switch_destination_candidate`）は`EnergyPolicy`のメソッドへ完全移行し、後方互換のためのラッパー関数は残さない
- `_score_card_option`の`SelectContext.DETACH_FROM`分岐と`_score_energy_switch_source_candidate`、`_score_option`の`OptionType.ENERGY`分岐は、実戦ログで一度も通らないと確認済みのデッドコードであるため削除する
- カードID定数：`Raging_Bolt_ex=63`, `Iono_Voltorb=265`, `Iono_Bellibolt_ex=269`, `Iono_Kilowattrel=271`, `Energy_Switch=1116`, `Basic_Lightning_Energy=4`, `Basic_Fighting_Energy=6`（いずれも既存定義を流用、変更しない）

---

### Task 1: `EnergyPolicy`クラスへの移植（振る舞い変更なし）

既存の6つの自由関数（`energy_score`・`_find_energy_switch_source`・`_raging_bolt_ex_needs_lightning`・`_raging_bolt_ex_has_growth_path`・`_score_play_option`内のEnergy_Switch分岐・`_score_energy_switch_destination_candidate`）を`EnergyPolicy`クラスの6メソッドへ1:1で移植する。ロジックは一切変更しない（純粋なリファクタリング）。

**Files:**
- Modify: `src/jamoraiko_agent/main.py`
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Produces: `EnergyPolicy`クラス（`attach_priority`/`find_surplus_source`/`needs_lightning`/`has_growth_path`/`play_score`/`switch_destination_score`の6メソッド）、モジュールレベルインスタンス`ENERGY_POLICY`
- Consumes: 既存の`Iono_Voltorb`/`Iono_Bellibolt_ex`/`Iono_Kilowattrel`/`Raging_Bolt_ex`/`Energy_Switch`/`Basic_Lightning_Energy`/`Basic_Fighting_Energy`定数、`FieldState`、`Pokemon`、`EnergyType`

- [ ] **Step 1: 失敗するテストを書く（新API）**

`tests/test_jamoraiko_agent.py`の`class TestEnergyScore:`（242行目付近）を、以下の`TestEnergyPolicy`クラスに**置き換える**（旧クラスは削除）：

```python
class TestEnergyPolicy:
    def test_active_slot_gets_bonus(self):
        p = make_pokemon(id=jm.Iono_Voltorb, energies=[])
        assert jm.ENERGY_POLICY.attach_priority(p, True) > jm.ENERGY_POLICY.attach_priority(p, False)

    def test_voltorb_prioritised_below_2_energy(self):
        no_e  = make_pokemon(id=jm.Iono_Voltorb, energies=[])
        two_e = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        assert jm.ENERGY_POLICY.attach_priority(no_e, False) > jm.ENERGY_POLICY.attach_priority(two_e, False)

    def test_bellibolt_ex_prioritised_below_4_energy(self):
        low  = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4])
        full = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])
        assert jm.ENERGY_POLICY.attach_priority(low, False) > jm.ENERGY_POLICY.attach_priority(full, False)

    def test_kilowattrel_prioritised_below_3_energy(self):
        low  = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4])
        full = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4, 4, 4])
        assert jm.ENERGY_POLICY.attach_priority(low, False) > jm.ENERGY_POLICY.attach_priority(full, False)

    def test_raging_bolt_ex_prioritised_below_1_energy(self):
        no_e  = make_pokemon(id=jm.Raging_Bolt_ex, energies=[])
        one_e = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4])
        assert jm.ENERGY_POLICY.attach_priority(no_e, False) > jm.ENERGY_POLICY.attach_priority(one_e, False)

    def test_raging_bolt_ex_no_bonus_once_at_1_energy(self):
        one_e = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4])
        two_e = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 4])
        assert jm.ENERGY_POLICY.attach_priority(one_e, False) == jm.ENERGY_POLICY.attach_priority(two_e, False)

    def test_find_surplus_source_returns_bellibolt_ex_when_surplus_lightning(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 雷4=閾値到達
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        assert jm.ENERGY_POLICY.find_surplus_source(my_state) is bellibolt

    def test_find_surplus_source_returns_none_when_below_threshold(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4])  # 雷3=閾値未満
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        assert jm.ENERGY_POLICY.find_surplus_source(my_state) is None

    def test_find_surplus_source_ignores_raging_bolt_ex_itself(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 4, 4, 4, 4])
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[])
        assert jm.ENERGY_POLICY.find_surplus_source(my_state) is None

    def test_needs_lightning_true_when_no_lightning_attached(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])  # 闘1のみ
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[])
        assert jm.ENERGY_POLICY.needs_lightning(my_state) is True

    def test_needs_lightning_false_when_lightning_already_attached(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 6])
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[])
        assert jm.ENERGY_POLICY.needs_lightning(my_state) is False

    def test_needs_lightning_false_when_raging_bolt_ex_not_on_board(self):
        my_state = make_player_state(active_pokemon=None, bench=[])
        assert jm.ENERGY_POLICY.needs_lightning(my_state) is False
```

続けて、`class TestFindEnergySwitchSource:`と`class TestRagingBoltExNeedsLightning:`（725行目〜756行目付近、上記`TestEnergyPolicy`に統合済みの内容と同一）を**削除**する。

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestEnergyPolicy`
Expected: FAIL（`AttributeError: module 'jamoraiko_agent.main' has no attribute 'ENERGY_POLICY'`）

- [ ] **Step 3: `EnergyPolicy`クラスを実装する**

**この置き換えは2箇所に分かれている。`_score_attach_option`関数（`energy_score`のすぐ後、`_ENERGY_SWITCH_SURPLUS_THRESHOLD`より前にある）はどちらの置き換え範囲にも含まれない。中身を書き換えず、そのまま残すこと（1行だけの変更はStep 5で別途行う）。**

**置き換え1**：`src/jamoraiko_agent/main.py`の`def energy_score(pokemon: Pokemon, active: bool) -> int:`から始まる関数全体（227行目付近、`_score_attach_option`の直前まで）を、以下に置き換える：

```python
# ==================== エネルギー運用ポリシー ====================
class EnergyPolicy:
    """雷/闘エネルギーの手張り優先度、エネルギーつけかえの運用、
    きょくらいごうの追加ダメージ用エネルギー破棄を1箇所に集約する。
    OptionType.ATTACH / PLAY / ENERGY_CARD という複数のSelectContextに
    またがるロジックをここに閉じ込め、散逸を防ぐ。
    """

    SURPLUS_THRESHOLD = {
        Iono_Bellibolt_ex: 4,  # Thunderous Boltのenergy_required（ATTACKERSテーブルより）
        Iono_Kilowattrel: 3,   # Mach Boltのenergy_required（ATTACKERSテーブルより）
    }

    def attach_priority(self, pokemon: Pokemon, active: bool) -> int:
        """雷エネルギー装填先の優先度スコアを返す（攻撃射程に近いほど高スコア）"""
        lightning_count = pokemon.energies.count(EnergyType.LIGHTNING)
        score = 8000
        if active:
            score += 10
        if pokemon.id == Iono_Voltorb:
            if lightning_count < 2:
                score += 100
        elif pokemon.id == Iono_Bellibolt_ex:
            if lightning_count < 4:
                score += 60
        elif pokemon.id == Iono_Kilowattrel:
            if lightning_count < 3:
                score += 40
        elif pokemon.id == Raging_Bolt_ex:
            if lightning_count < 1:
                score += 90
        return score

    def find_surplus_source(self, my_state) -> "Pokemon | None":
        """エネルギーつけかえの供給元にできる、自分自身の攻撃条件を満たし
        雷エネルギーに余剰があるナンジャモポケモンを1体返す（無ければNone）。
        タケルライコex自身は候補に含まない（供給元は常に他のポケモン）。"""
        for card in my_state.active + my_state.bench:
            if card is None:
                continue
            threshold = self.SURPLUS_THRESHOLD.get(card.id)
            if threshold is None:
                continue
            lightning_count = card.energies.count(EnergyType.LIGHTNING)
            if lightning_count >= threshold:
                return card
        return None

    def needs_lightning(self, my_state) -> bool:
        """場のタケルライコexが雷エネルギーを1枚も持っていないか（きょくらいごうのコスト未達）"""
        for card in my_state.active + my_state.bench:
            if card is not None and card.id == Raging_Bolt_ex:
                if card.energies.count(EnergyType.LIGHTNING) < 1:
                    return True
        return False

    def has_growth_path(self, fs: FieldState, my_state) -> bool:
        """タケルライコexがまだきょくらいごう着地に伸びる見込みがあるか
        （手札に闘/雷の基本エネルギーがある、またはエネルギーつけかえの供給元がある）"""
        if fs.hand_counts[Basic_Fighting_Energy] > 0 or fs.hand_counts[Basic_Lightning_Energy] > 0:
            return True
        if fs.hand_counts[Energy_Switch] > 0 and self.find_surplus_source(my_state) is not None:
            return True
        return False

    def play_score(self, my_state) -> int:
        """OptionType.PLAY（エネルギーつけかえを使うか）のスコアを返す"""
        if self.needs_lightning(my_state) and self.find_surplus_source(my_state) is not None:
            return 7500  # タケルライコexが雷0枚で、ベンチに余剰供給元がある時のみ高優先
        return 200

    def switch_destination_score(self, card) -> int:
        """SelectContext.ATTACH_FROM（エネルギーつけかえで付け直す先のポケモン）のスコアを返す"""
        if not isinstance(card, Pokemon):
            return 0
        if card.id == Raging_Bolt_ex:
            return 500 if card.energies.count(EnergyType.LIGHTNING) < 1 else -500
        return 0


ENERGY_POLICY = EnergyPolicy()
```

**置き換え2**：`_score_attach_option`関数より後にある、以下の4つ（`_ENERGY_SWITCH_SURPLUS_THRESHOLD`辞書・`_find_energy_switch_source`・`_raging_bolt_ex_needs_lightning`・`_raging_bolt_ex_has_growth_path`、「エネルギーつけかえ供給元判定」セクション見出しごと、265〜304行目付近）を丸ごと削除する（置き換え1のクラスに統合済みのため）：

```python
# ==================== エネルギーつけかえ供給元判定 ====================
_ENERGY_SWITCH_SURPLUS_THRESHOLD = {
    Iono_Bellibolt_ex: 4,  # Thunderous Boltのenergy_required（ATTACKERSテーブルより）
    Iono_Kilowattrel: 3,   # Mach Boltのenergy_required（ATTACKERSテーブルより）
}


def _find_energy_switch_source(my_state) -> "Pokemon | None":
    """エネルギーつけかえの供給元にできる、自分自身の攻撃条件を満たし
    雷エネルギーに余剰があるナンジャモポケモンを1体返す（無ければNone）。
    タケルライコex自身は候補に含まない（供給元は常に他のポケモン）。"""
    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        threshold = _ENERGY_SWITCH_SURPLUS_THRESHOLD.get(card.id)
        if threshold is None:
            continue
        lightning_count = card.energies.count(EnergyType.LIGHTNING)
        if lightning_count >= threshold:
            return card
    return None


def _raging_bolt_ex_needs_lightning(my_state) -> bool:
    """場のタケルライコexが雷エネルギーを1枚も持っていないか（きょくらいごうのコスト未達）"""
    for card in my_state.active + my_state.bench:
        if card is not None and card.id == Raging_Bolt_ex:
            if card.energies.count(EnergyType.LIGHTNING) < 1:
                return True
    return False


def _raging_bolt_ex_has_growth_path(fs: FieldState, my_state) -> bool:
    """タケルライコexがまだきょくらいごう着地に伸びる見込みがあるか
    （手札に闘/雷の基本エネルギーがある、またはエネルギーつけかえの供給元がある）"""
    if fs.hand_counts[Basic_Fighting_Energy] > 0 or fs.hand_counts[Basic_Lightning_Energy] > 0:
        return True
    if fs.hand_counts[Energy_Switch] > 0 and _find_energy_switch_source(my_state) is not None:
        return True
    return False
```

この削除により、`_score_attach_option`関数の直後に`EnergyPolicy`クラスで置き換わった空白ができるが、直後は「カードメタデータ（遅延初期化）」セクション（`card_table: dict = {}`）に自然に続く。

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestEnergyPolicy`
Expected: PASS（12件）

- [ ] **Step 5: 呼び出し側を新APIへ更新する**

`_score_attach_option`関数内（`if card.id == Basic_Lightning_Energy:`の直後）：

変更前：
```python
    if card.id == Basic_Lightning_Energy:
        return energy_score(pokemon, o.inPlayArea == AreaType.ACTIVE)
```

変更後：
```python
    if card.id == Basic_Lightning_Energy:
        return ENERGY_POLICY.attach_priority(pokemon, o.inPlayArea == AreaType.ACTIVE)
```

`_score_play_option`関数内のEnergy_Switch分岐：

変更前：
```python
    if card.id == Energy_Switch:
        if _raging_bolt_ex_needs_lightning(my_state) and _find_energy_switch_source(my_state) is not None:
            return 7500  # タケルライコexが雷0枚で、ベンチに余剰供給元がある時のみ高優先
        return 200
```

変更後：
```python
    if card.id == Energy_Switch:
        return ENERGY_POLICY.play_score(my_state)
```

`_score_card_option`関数内の`match context:`のATTACH_FROMケース：

変更前：
```python
        case SelectContext.ATTACH_FROM:
            return _score_energy_switch_destination_candidate(card)
```

変更後：
```python
        case SelectContext.ATTACH_FROM:
            return ENERGY_POLICY.switch_destination_score(card)
```

`calc_attack_plan`関数内の候補フィルタ：

変更前：
```python
        if atk.is_utility and atk.id == Raging_Bolt_ex and _raging_bolt_ex_has_growth_path(fs, my_state):
            continue  # きょくらいごうへの伸びしろが残っている間ははじけるほうこうを温存
```

変更後：
```python
        if atk.is_utility and atk.id == Raging_Bolt_ex and ENERGY_POLICY.has_growth_path(fs, my_state):
            continue  # きょくらいごうへの伸びしろが残っている間ははじけるほうこうを温存
```

- [ ] **Step 6: 旧`_score_energy_switch_destination_candidate`関数を削除する**

`src/jamoraiko_agent/main.py`から以下の関数を削除する（Step 3で移植済みのため）：

```python
def _score_energy_switch_destination_candidate(card) -> int:
    """OptionType.CARD / SelectContext.ATTACH_FROM のスコアを返す
    （エネルギーつけかえで雷エネルギーを付け直す先のポケモンを選ぶ）"""
    if not isinstance(card, Pokemon):
        return 0
    if card.id == Raging_Bolt_ex:
        return 500 if card.energies.count(EnergyType.LIGHTNING) < 1 else -500
    return 0
```

（この関数は`_score_energy_switch_source_candidate`関数の直後、`_score_card_option`関数の直前にある。`_score_energy_switch_source_candidate`自体はTask 2で削除するため、このStepでは触らない）

- [ ] **Step 7: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v`
Expected: 全件PASS（回帰なし）

Run: `uv run pytest -q`
Expected: 491 passed（旧テスト12件削除・新テスト12件追加で総数不変）

- [ ] **Step 8: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "refactor: エネルギー関連ロジックをEnergyPolicyクラスに集約（振る舞い変更なし）"
```

---

### Task 2: `OptionType.ENERGY_CARD`の実装とデッドコード削除

実ログ解析で判明した「エネルギーつけかえの供給元選択（`SWITCH_ENERGY_CARD`）」と「きょくらいごうの追加ダメージ用破棄（`DISCARD_ENERGY_CARD`）」が、どちらも`OptionType.ENERGY_CARD`という共通の型を通ることが分かった。この型は`_score_option`の`match`文に一つもケース分けされておらず常にスコア0だったため、新規実装する。あわせて、実戦で一度も通らないと確認済みのデッドコード（`DETACH_FROM`分岐・`OptionType.ENERGY`分岐）を削除する。

**Files:**
- Modify: `src/jamoraiko_agent/main.py`
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: Task 1で実装した`EnergyPolicy`クラス・`ENERGY_POLICY`インスタンス、既存の`get_card`関数
- Produces: `EnergyPolicy.switch_source_score(obs, o, my_index)`・`EnergyPolicy.discard_for_damage_score()`の2メソッド、`_score_energy_card_option(obs, o, context, my_index)`ディスパッチ関数

- [ ] **Step 1: 失敗するテストを書く（新メソッド）**

`tests/test_jamoraiko_agent.py`の`class TestEnergyPolicy:`の最後に追加：

```python
    def test_switch_source_score_avoids_raging_bolt_ex_itself(self):
        from cg.api import Option

        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 6])
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[])
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.ACTIVE, index=0, playerIndex=0, energyIndex=0)
        assert jm.ENERGY_POLICY.switch_source_score(obs, o, my_index=0) == -1000

    def test_switch_source_score_prefers_surplus_bench_pokemon(self):
        from cg.api import Option

        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 雷4=余剰あり
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.BENCH, index=0, playerIndex=0, energyIndex=0)
        assert jm.ENERGY_POLICY.switch_source_score(obs, o, my_index=0) == 500

    def test_switch_source_score_penalises_non_surplus_bench_pokemon(self):
        from cg.api import Option

        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4])  # 雷1=余剰なし
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.BENCH, index=0, playerIndex=0, energyIndex=0)
        assert jm.ENERGY_POLICY.switch_source_score(obs, o, my_index=0) == -500

    def test_switch_source_score_neutral_for_unrelated_pokemon(self):
        from cg.api import Option

        voltorb = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        my_state = make_player_state(active_pokemon=None, bench=[voltorb])
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.BENCH, index=0, playerIndex=0, energyIndex=0)
        assert jm.ENERGY_POLICY.switch_source_score(obs, o, my_index=0) == 0

    def test_switch_source_score_returns_zero_when_card_missing(self):
        from cg.api import Option

        my_state = make_player_state(active_pokemon=None, bench=[])
        my_state.active = [None]
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.ACTIVE, index=0, playerIndex=0, energyIndex=0)
        assert jm.ENERGY_POLICY.switch_source_score(obs, o, my_index=0) == 0

    def test_discard_for_damage_score_always_high(self):
        assert jm.ENERGY_POLICY.discard_for_damage_score() == 9000
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k "switch_source_score or discard_for_damage_score"`
Expected: FAIL（`AttributeError: 'EnergyPolicy' object has no attribute 'switch_source_score'`）

- [ ] **Step 3: `EnergyPolicy`に新規メソッドを追加する**

`src/jamoraiko_agent/main.py`の`EnergyPolicy`クラス内、`switch_destination_score`メソッドの直後に追加：

```python
    def switch_source_score(self, obs, o, my_index: int) -> int:
        """SelectContext.SWITCH_ENERGY_CARD（エネルギーつけかえで動かす元の
        エネルギーカードを選ぶ）のスコアを返す"""
        card = get_card(obs, o.area, o.index, o.playerIndex)
        if not isinstance(card, Pokemon):
            return 0
        if card.id == Raging_Bolt_ex:
            return -1000  # タケルライコex自身のエネルギーは動かさない
        threshold = self.SURPLUS_THRESHOLD.get(card.id)
        if threshold is None:
            return 0
        lightning_count = card.energies.count(EnergyType.LIGHTNING)
        return 500 if lightning_count >= threshold else -500

    def discard_for_damage_score(self) -> int:
        """SelectContext.DISCARD_ENERGY_CARD（きょくらいごうの追加ダメージ用エネルギー破棄）
        のスコアを返す。貪欲方針：提示されたエネルギーは常に破棄する"""
        return 9000
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k "switch_source_score or discard_for_damage_score"`
Expected: PASS（6件）

- [ ] **Step 5: 失敗するテストを書く（`_score_energy_card_option`ディスパッチ）**

`tests/test_jamoraiko_agent.py`の`class TestScoreCardOptionDispatch:`の後に新規クラスを追加：

```python
class TestScoreEnergyCardOptionDispatch:
    def test_dispatches_switch_energy_card(self):
        from cg.api import Option, SelectContext

        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.BENCH, index=0, playerIndex=0, energyIndex=0)
        score = jm._score_energy_card_option(obs, o, SelectContext.SWITCH_ENERGY_CARD, my_index=0)
        assert score == jm.ENERGY_POLICY.switch_source_score(obs, o, my_index=0)

    def test_dispatches_discard_energy_card(self):
        from cg.api import Option, SelectContext

        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.ACTIVE, index=0, playerIndex=0, energyIndex=0)
        score = jm._score_energy_card_option(obs=MagicMock(), o=o, context=SelectContext.DISCARD_ENERGY_CARD, my_index=0)
        assert score == 9000

    def test_unknown_context_defaults_to_zero(self):
        from cg.api import Option, SelectContext

        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.ACTIVE, index=0, playerIndex=0, energyIndex=0)
        score = jm._score_energy_card_option(obs=MagicMock(), o=o, context=SelectContext.MAIN, my_index=0)
        assert score == 0
```

- [ ] **Step 6: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestScoreEnergyCardOptionDispatch`
Expected: FAIL（`AttributeError: module 'jamoraiko_agent.main' has no attribute '_score_energy_card_option'`）

- [ ] **Step 7: `_score_energy_card_option`ディスパッチ関数を実装する**

`src/jamoraiko_agent/main.py`の`_score_card_option`関数の直後（「オプション全体のスコアリング」セクションの直前）に追加：

```python
def _score_energy_card_option(obs, o, context, my_index: int) -> int:
    """OptionType.ENERGY_CARD のスコアをコンテキスト別に返す"""
    match context:
        case SelectContext.SWITCH_ENERGY_CARD:
            return ENERGY_POLICY.switch_source_score(obs, o, my_index)
        case SelectContext.DISCARD_ENERGY_CARD:
            return ENERGY_POLICY.discard_for_damage_score()
        case _:
            return 0
```

- [ ] **Step 8: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestScoreEnergyCardOptionDispatch`
Expected: PASS（3件）

- [ ] **Step 9: 失敗するテストを書く（`_score_option`への配線）**

`tests/test_jamoraiko_agent.py`の`class TestScoreOptionEnergyType:`（805行目付近）を、以下に**置き換える**：

```python
class TestScoreOptionEnergyCardType:
    def test_routes_energy_card_type_through_dispatcher(self):
        from cg.api import Option, SelectContext

        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.ACTIVE, index=0, playerIndex=0, energyIndex=0)
        fs = jm.FieldState(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
            active_fighting_energy_count=0,
        )
        plan = jm.AttackPlan()
        score = jm._score_option(
            obs=MagicMock(), o=o, context=SelectContext.DISCARD_ENERGY_CARD, my_index=0,
            state=None, my_state=make_player_state(), fs=fs, plan=plan,
        )
        assert score == 9000
```

- [ ] **Step 10: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestScoreOptionEnergyCardType`
Expected: FAIL（`OptionType.ENERGY_CARD`は`match`文の`case _: return 0`に落ち、score==0）

- [ ] **Step 11: `_score_option`に`OptionType.ENERGY_CARD`ケースを追加し、デッドコードを削除する**

`src/jamoraiko_agent/main.py`の`_score_option`関数内、以下の部分：

変更前：
```python
        case OptionType.ENERGY:
            return 9000  # きょくらいごうの追加ダメージ用：提示された基本エネルギーは常に捨てる
        case OptionType.RETREAT:
```

変更後：
```python
        case OptionType.ENERGY_CARD:
            return _score_energy_card_option(obs, o, context, my_index)
        case OptionType.RETREAT:
```

- [ ] **Step 12: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestScoreOptionEnergyCardType`
Expected: PASS

- [ ] **Step 13: デッドコードを削除する（`DETACH_FROM`関連）**

`_score_card_option`関数内の`match context:`から以下の2行を削除：

```python
        case SelectContext.DETACH_FROM:
            return _score_energy_switch_source_candidate(card)
```

`src/jamoraiko_agent/main.py`から以下の関数を削除：

```python
def _score_energy_switch_source_candidate(card) -> int:
    """OptionType.CARD / SelectContext.DETACH_FROM のスコアを返す
    （エネルギーつけかえで雷エネルギーを外す元のポケモンを選ぶ）"""
    if not isinstance(card, Pokemon):
        return 0
    if card.id == Raging_Bolt_ex:
        return -1000  # タケルライコex自身からは外さない
    threshold = _ENERGY_SWITCH_SURPLUS_THRESHOLD.get(card.id)
    if threshold is None:
        return 0
    lightning_count = card.energies.count(EnergyType.LIGHTNING)
    return 500 if lightning_count >= threshold else -500
```

`tests/test_jamoraiko_agent.py`から以下のテストを削除（`class TestScoreCardOptionDispatch:`内、692〜706行目付近）：

```python
    def test_dispatches_detach_from_prefers_surplus_source_over_raging_bolt_ex(self):
        from cg.api import Option, SelectContext

        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 雷4=余剰あり
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 6])
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[bellibolt])
        obs = MagicMock()
        obs.current.players = [my_state]
        o_bellibolt = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        o_raging = Option(type=OptionType.CARD, area=AreaType.ACTIVE, index=0, playerIndex=0)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score_bellibolt = jm._score_card_option(obs, o_bellibolt, SelectContext.DETACH_FROM, my_index=0, fs=fs, plan=plan)
        score_raging = jm._score_card_option(obs, o_raging, SelectContext.DETACH_FROM, my_index=0, fs=fs, plan=plan)
        assert score_bellibolt > score_raging
```

（このテストの直後にある`test_dispatches_attach_from_prefers_raging_bolt_ex_needing_lightning`は変更せず残す）

最後に、`_ENERGY_SWITCH_SURPLUS_THRESHOLD`というモジュールレベル辞書がまだ他のどこかから参照されていないかを確認する：

Run: `grep -n "_ENERGY_SWITCH_SURPLUS_THRESHOLD" src/jamoraiko_agent/main.py`
Expected: 0件（Task 1で`EnergyPolicy.SURPLUS_THRESHOLD`に統合済みのはずだが、Task 1後にこの名残が残っていないか最終確認する。もし残っていれば削除する）

- [ ] **Step 14: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v`
Expected: 全件PASS（回帰なし）

Run: `uv run pytest -q`
Expected: 全件PASS（Task1の491件から、Step1で6件追加・Step5で3件追加・Step9で1件置換（旧1件→新1件、net 0）・Step13で1件削除 = 491+6+3-1 = 499件）

- [ ] **Step 15: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "fix: OptionType.ENERGY_CARDを実装（SWITCH_ENERGY_CARD/DISCARD_ENERGY_CARD）し、実戦で未到達のデッドコードを削除"
```

---

## 全タスク完了後の最終確認

- [ ] `uv run pytest -q`で全件PASSを確認
- [ ] `git log --oneline`でTask 1〜2の2コミットが積まれていることを確認
- [ ] 最終ブランチ全体レビュー（`superpowers:requesting-code-review`のcode-reviewer.mdテンプレート使用）を実施
- [ ] レビュー完了後、`docs/implementations/[日付]-jamoraiko-energy-policy-class.md`に実装サマリーを保存
- [ ] レビュー結果を`docs/reviews/[日付]-jamoraiko-energy-policy-class.md`に保存
- [ ] マージ後、ユーザーがKaggle上でノートブックを再実行し、`jamoraiko_vs_iono_results.json`（勝率）と`jamoraiko_vs_iono_turn_log.json`（手番ログ）を再取得して効果を検証する
