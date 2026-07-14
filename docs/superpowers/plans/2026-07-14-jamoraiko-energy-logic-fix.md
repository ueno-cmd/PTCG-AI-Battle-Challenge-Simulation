# ジャモライコ エネルギー運用ロジック修正 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/superpowers/specs/2026-07-14-jamoraiko-energy-logic-fix-design.md` の5つの修正方針を`src/jamoraiko_agent/main.py`と`decks/jamoraiko_20260713.py`に実装し、勝率0.015の3つの根本原因（タイカイデン自滅ループ／タケルライコexへのエネルギー供給不足／`OptionType.ENERGY`未実装）を解消する。

**Architecture:** 既存の`FieldState`/`_score_option`/`calc_attack_plan`のヒューリスティック・スコアリング構造を踏襲し、新しいフィールド・分岐・ヘルパー関数を追加する形で実装する。新規ファイルは作成しない。

**Tech Stack:** Python 3.12 / pytest / dataclasses（既存プロジェクト構成を継続）

## Global Constraints

- 全コード内コメント・ドキュメントは日本語で書く（CLAUDE.md ルール）
- 既存の451件＋471件のテストスイート全体が最後まで回帰なく通ること（各タスク末尾で`uv run pytest -q`を実行）
- カードID定数：`Raging_Bolt_ex=63`, `Iono_Voltorb=265`, `Iono_Tadbulb=268`, `Iono_Bellibolt_ex=269`, `Iono_Wattrel=270`, `Iono_Kilowattrel=271`, `Basic_Lightning_Energy=4`, `Basic_Fighting_Energy=6`, `Energy_Switch=1116`（エネルギーつけかえ、新規追加）
- `Energy_Search=1119`（エネルギー転送）はデッキから削除するため、関連する定数・スコアリング分岐も削除する（未使用コードを残さない）
- ハラバリーexの攻撃「Thunderous Bolt」の`energy_required=4`、タイカイデンの攻撃「Mach Bolt」の`energy_required=3`は`ATTACKERS`テーブル（`src/jamoraiko_agent/main.py:131,133`）で既に定義済みの値を流用し、二重定義しない
- ローカルでは`libcg.so`が動かないため実対戦での検証は不可能。各タスクの単体テストで関数レベルの正しさを保証し、実際の勝率変化はタスク完了後にKaggleで確認する

## 実装上の技術判断（設計書からの補足）

設計書の「修正3」（タケルライコexへのエネルギー供給）と「修正5」（はじけるほうこう抑制）について、実装にあたり以下の技術的な位置づけを確定した：

1. **エネルギーつけかえのCARDサブ選択コンテキスト**：`data/cg/api.py`の`SelectContext`定義を確認した結果、`DETACH_FROM`（"Select the Pokémon to remove the card from"）＝供給元ポケモン選択、`ATTACH_FROM`（"Select the Pokémon to attach the card to"）＝宛先ポケモン選択に対応すると判断した。この2つのコンテキストは現在のデッキ構成では他にトリガーされるカードが無いため、Energy Switch専用として扱って問題ない。**この対応関係はKaggle実測でのみ最終検証できる**（設計書の「未検証事項」を参照）。
2. **はじけるほうこう抑制の実装箇所**：設計書は「`OptionType.ATTACK`のタケルライコex分岐に条件を追加」と書いたが、現在の`_score_option`のATTACKケースは`o.attackId == plan.attack_id`の一致判定のみでポケモン別分岐を持たない。実際に技候補から除外すべき箇所は`calc_attack_plan`内の候補フィルタ（既存の`is_utility`とデッキ薄チェックと同じ場所）であるため、そこに実装する。狙いとする挙動（温存すべき時ははじけるほうこうを選ばせない）は設計書の意図と一致する。

---

### Task 1: タイカイデン自滅ループ防止（`FieldState`拡張 + ABILITY分岐修正）

**Files:**
- Modify: `src/jamoraiko_agent/main.py`（`FieldState`データクラス、`_collect_field_state`、`_score_option`のOptionType.ABILITY分岐）
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Produces: `FieldState.hand_has_basic_lightning_energy: bool`（デフォルト`False`、既存の`_fs()`テストヘルパーは変更不要）

- [ ] **Step 1: 失敗するテストを書く（`FieldState`の新規フィールド）**

`tests/test_jamoraiko_agent.py`の`class TestCollectFieldState:`の最後（`test_field_counts_and_hand_counts_are_tracked`の後）に追加：

```python
    def test_hand_has_basic_lightning_energy_true_when_present(self):
        energy_card = make_pokemon(id=jm.Basic_Lightning_Energy)
        my_state = make_player_state(hand=[energy_card])
        fs = jm._collect_field_state(my_state)
        assert fs.hand_has_basic_lightning_energy is True

    def test_hand_has_basic_lightning_energy_false_when_absent(self):
        canari = make_pokemon(id=jm.Canari)
        my_state = make_player_state(hand=[canari])
        fs = jm._collect_field_state(my_state)
        assert fs.hand_has_basic_lightning_energy is False
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k test_hand_has_basic_lightning_energy`
Expected: FAIL（`AttributeError: 'FieldState' object has no attribute 'hand_has_basic_lightning_energy'`）

- [ ] **Step 3: `FieldState`にフィールドを追加し、`_collect_field_state`で算出する**

`src/jamoraiko_agent/main.py`の`FieldState`データクラス定義（56-65行目）を変更：

```python
@dataclass
class FieldState:
    field_counts: defaultdict
    hand_counts: defaultdict
    discard_counts: defaultdict
    iono_lightning_on_board: int
    own_board_basic_energy_total: int
    active_energy_count: int
    active_fighting_energy_count: int
    hand_has_basic_lightning_energy: bool = False
```

`_collect_field_state`の`return FieldState(...)`（105-113行目）を変更：

```python
    return FieldState(
        field_counts=field_counts,
        hand_counts=hand_counts,
        discard_counts=discard_counts,
        iono_lightning_on_board=iono_lightning_on_board,
        own_board_basic_energy_total=own_board_basic_energy_total,
        active_energy_count=active_energy_count,
        active_fighting_energy_count=active_fighting_energy_count,
        hand_has_basic_lightning_energy=hand_counts[Basic_Lightning_Energy] > 0,
    )
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k test_hand_has_basic_lightning_energy`
Expected: PASS（2件）

- [ ] **Step 5: 失敗するテストを書く（タイカイデンのABILITY分岐）**

`tests/test_jamoraiko_agent.py`の末尾に追加（`TestScoreCardOptionDispatch`クラスの後）：

```python
class TestScoreOptionKilowattrelAbility:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
            active_fighting_energy_count=0, hand_has_basic_lightning_energy=False,
        )
        base.update(overrides)
        return jm.FieldState(**base)

    def test_kilowattrel_ability_suppressed_when_hand_has_lightning_energy(self, mock_card_table):
        from cg.api import Option, SelectContext

        kilowattrel = make_pokemon(id=jm.Iono_Kilowattrel)
        my_state = make_player_state(active_pokemon=kilowattrel, deck_count=40, prize_count=6)
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ABILITY, area=AreaType.ACTIVE, index=0)
        fs = self._fs(hand_has_basic_lightning_energy=True)
        plan = jm.AttackPlan()
        score = jm._score_option(
            obs, o, SelectContext.MAIN, my_index=0,
            state=None, my_state=my_state, fs=fs, plan=plan,
        )
        assert score == -1

    def test_kilowattrel_ability_allowed_when_hand_has_no_lightning_energy_and_deck_safe(self, mock_card_table):
        from cg.api import Option, SelectContext

        kilowattrel = make_pokemon(id=jm.Iono_Kilowattrel)
        my_state = make_player_state(active_pokemon=kilowattrel, deck_count=40, prize_count=6)
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ABILITY, area=AreaType.ACTIVE, index=0)
        fs = self._fs(
            hand_has_basic_lightning_energy=False,
            hand_counts=defaultdict(int, {jm.Canari: 6}),
        )
        plan = jm.AttackPlan()
        score = jm._score_option(
            obs, o, SelectContext.MAIN, my_index=0,
            state=None, my_state=my_state, fs=fs, plan=plan,
        )
        assert score == 8000
```

- [ ] **Step 6: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestScoreOptionKilowattrelAbility`
Expected: `test_kilowattrel_ability_suppressed_when_hand_has_lightning_energy`がFAIL（score==8000が返り、-1ではない）

- [ ] **Step 7: `_score_option`のABILITY分岐を修正する**

`src/jamoraiko_agent/main.py`の`_score_option`内、OptionType.ABILITYケース（489-496行目）を変更：

```python
        case OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if card.id == Iono_Bellibolt_ex:
                return 9500  # エレキストリーマーは常に高優先
            if card.id == Iono_Kilowattrel:
                if fs.hand_has_basic_lightning_energy:
                    return -1  # 手札にまだ雷エネがあるなら伸ばせる見込みがあるため自滅ループ防止で温存
                consumption = _flashing_draw_consumption(my_state, fs.hand_counts)
                return 8000 if consumption <= _safe_draws(my_state) else -1
            return -1
```

- [ ] **Step 8: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestScoreOptionKilowattrelAbility`
Expected: PASS（2件）

Run: `uv run pytest -q`
Expected: 全件PASS（回帰なし）

- [ ] **Step 9: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "fix: タイカイデンの自滅ループを防止（手札に雷エネがある間はフラッシュドローを温存）"
```

---

### Task 2: デッキ変更（エネルギー転送→エネルギーつけかえ）

**Files:**
- Modify: `decks/jamoraiko_20260713.py`
- Modify: `src/jamoraiko_agent/main.py`（カードID定数、`_score_play_option`）
- Test: `tests/test_jamoraiko_deck.py`, `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Produces: `jamoraiko_agent.main.Energy_Switch = 1116`（後続タスクが使用する定数）
- Removes: `jamoraiko_agent.main.Energy_Search`（1119、以後未使用のため削除）

- [ ] **Step 1: 失敗するテストを書く（デッキ内容の期待値変更）**

`tests/test_jamoraiko_deck.py`の`test_trainer_counts`内、44行目を変更：

```python
def test_trainer_counts():
    counts = dict(DECK)
    assert counts[1121] == 4   # ハイパーボール
    assert counts[1086] == 4   # なかよしポフィン
    assert counts[1118] == 2   # エネルギー回収
    assert counts[1097] == 3   # 夜のタンカ
    assert counts[1116] == 2   # エネルギーつけかえ
    assert counts[1123] == 2   # ポケモンいれかえ
    assert counts[1110] == 1   # つりざおMAX
    assert counts[1227] == 3   # リーリエの決心
    assert counts[1233] == 4   # カナリィ
    assert counts[1182] == 2   # ボスの指令
    assert counts[1254] == 3   # ハッコウシティ
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_deck.py -v -k test_trainer_counts`
Expected: FAIL（`KeyError: 1116`、デッキにまだ存在しない）

- [ ] **Step 3: デッキ定義を変更する**

`decks/jamoraiko_20260713.py`の15行目を変更：

```python
    (1116, 2),   # エネルギーつけかえ (Energy Switch)
```

（`(1119, 2), # エネルギー転送 (Energy Search)`の行を置き換える）

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_deck.py -v`
Expected: 全件PASS（60枚・ACE SPEC制限等の既存テストも新構成で通ることを確認）

- [ ] **Step 5: `main.py`のカードID定数を更新する**

`src/jamoraiko_agent/main.py`の22行目（`Energy_Search = 1119  # エネルギー転送（山札から基本エネルギー1枚サーチ）`）を削除し、代わりに以下を追加（23行目`Ultra_Ball`の前）：

```python
Energy_Switch            = 1116  # エネルギーつけかえ（自分の場のポケモン間で基本エネルギー1個を付け替え）
```

- [ ] **Step 6: `_score_play_option`のエネルギー転送スコアリングを削除する**

`src/jamoraiko_agent/main.py`の`_score_play_option`内、以下の2行を削除（361-362行目）：

```python
    if card.id == Energy_Search:
        return 6050
```

- [ ] **Step 7: テスト用モックテーブルの参照を更新する**

`tests/test_jamoraiko_agent.py`の`mock_card_table`フィクスチャ内（98行目）を変更：

```python
        jm.Energy_Switch:            MockCardData(cardId=jm.Energy_Switch, cardType=CardType.ITEM),
```

（`jm.Energy_Search: MockCardData(cardId=jm.Energy_Search, cardType=CardType.ITEM),`の行を置き換える）

- [ ] **Step 8: 全体回帰テストを実行する**

Run: `uv run pytest -q`
Expected: 全件PASS（回帰なし。`Energy_Search`未参照によるエラーが無いことを確認）

- [ ] **Step 9: コミット**

```bash
git add decks/jamoraiko_20260713.py src/jamoraiko_agent/main.py tests/test_jamoraiko_deck.py tests/test_jamoraiko_agent.py
git commit -m "feat: デッキのエネルギー転送をエネルギーつけかえに変更（タケルライコexへのテンポ短縮用）"
```

---

### Task 3: タケルライコexへのエネルギー供給（`energy_score`拡張）

**Files:**
- Modify: `src/jamoraiko_agent/main.py`（`energy_score`関数）
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: `Raging_Bolt_ex`定数（既存）
- Produces: `energy_score()`がタケルライコexに対しても優先度ボーナスを返すようになる（雷エネルギー1枚未満の場合のみ）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_jamoraiko_agent.py`の`class TestEnergyScore:`の最後（`test_kilowattrel_prioritised_below_3_energy`の後）に追加：

```python
    def test_raging_bolt_ex_prioritised_below_1_energy(self):
        no_e  = make_pokemon(id=jm.Raging_Bolt_ex, energies=[])
        one_e = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4])
        assert jm.energy_score(no_e, False) > jm.energy_score(one_e, False)

    def test_raging_bolt_ex_no_bonus_once_at_1_energy(self):
        one_e = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4])
        two_e = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 4])
        assert jm.energy_score(one_e, False) == jm.energy_score(two_e, False)
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k test_raging_bolt_ex_prioritised_below_1_energy`
Expected: FAIL（現在`energy_score`にタケルライコex分岐が無いため、両方とも同じベーススコア8000になる）

- [ ] **Step 3: `energy_score`にタケルライコex分岐を追加する**

`src/jamoraiko_agent/main.py`の`energy_score`関数（224-239行目）を変更：

```python
def energy_score(pokemon: Pokemon, active: bool) -> int:
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
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestEnergyScore`
Expected: 全件PASS（既存3件＋新規2件）

Run: `uv run pytest -q`
Expected: 全件PASS（回帰なし）

- [ ] **Step 5: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: タケルライコexの雷エネルギー1枚目を手張り優先度に追加"
```

---

### Task 4: エネルギーつけかえのスコアリング（PLAY + CARDサブ選択）

**Files:**
- Modify: `src/jamoraiko_agent/main.py`（新規ヘルパー関数、`_score_play_option`、`_score_card_option`）
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: `Energy_Switch`定数（Task 2で追加済み）、`Iono_Bellibolt_ex`/`Iono_Kilowattrel`の`ATTACKERS`テーブル上の`energy_required`（4/3）
- Produces:
  - `_ENERGY_SWITCH_SURPLUS_THRESHOLD: dict[int, int]`
  - `_find_energy_switch_source(my_state) -> Pokemon | None`
  - `_raging_bolt_ex_needs_lightning(my_state) -> bool`
  - （Task 6が`_find_energy_switch_source`を再利用する）

- [ ] **Step 1: 失敗するテストを書く（ヘルパー関数）**

`tests/test_jamoraiko_agent.py`の`class TestScoreAttachOption:`の後に新規クラスを追加：

```python
class TestFindEnergySwitchSource:
    def test_returns_bellibolt_ex_when_surplus_lightning(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 雷4=閾値到達
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        assert jm._find_energy_switch_source(my_state) is bellibolt

    def test_returns_none_when_below_threshold(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4])  # 雷3=閾値未満
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        assert jm._find_energy_switch_source(my_state) is None

    def test_ignores_raging_bolt_ex_itself(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 4, 4, 4, 4])
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[])
        assert jm._find_energy_switch_source(my_state) is None


class TestRagingBoltExNeedsLightning:
    def test_true_when_no_lightning_attached(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])  # 闘1のみ
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[])
        assert jm._raging_bolt_ex_needs_lightning(my_state) is True

    def test_false_when_lightning_already_attached(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 6])
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[])
        assert jm._raging_bolt_ex_needs_lightning(my_state) is False

    def test_false_when_raging_bolt_ex_not_on_board(self):
        my_state = make_player_state(active_pokemon=None, bench=[])
        assert jm._raging_bolt_ex_needs_lightning(my_state) is False
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k "TestFindEnergySwitchSource or TestRagingBoltExNeedsLightning"`
Expected: FAIL（`AttributeError: module 'jamoraiko_agent.main' has no attribute '_find_energy_switch_source'`等）

- [ ] **Step 3: ヘルパー関数を実装する**

`src/jamoraiko_agent/main.py`の`_score_attach_option`関数（242-255行目）の直後に追加：

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
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k "TestFindEnergySwitchSource or TestRagingBoltExNeedsLightning"`
Expected: PASS（6件）

- [ ] **Step 5: 失敗するテストを書く（PLAYスコアリング）**

`tests/test_jamoraiko_agent.py`の`class TestScorePlayOption:`の最後に追加：

```python
    def test_energy_switch_scores_high_when_raging_bolt_ex_needs_lightning_and_source_exists(self, mock_card_table):
        mock_card_table[jm.Energy_Switch] = MockCardData(cardId=jm.Energy_Switch, cardType=CardType.ITEM)
        energy_switch = make_pokemon(id=jm.Energy_Switch)
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])  # 雷0闘1
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 雷4=供給可能
        my_state = make_player_state(
            active_pokemon=raging_bolt, bench=[bellibolt],
            hand=[energy_switch], deck_count=40, prize_count=6,
        )
        obs, o = self._make_obs_with_hand_card(jm.Energy_Switch, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score >= 7000

    def test_energy_switch_scores_low_when_no_source_available(self, mock_card_table):
        mock_card_table[jm.Energy_Switch] = MockCardData(cardId=jm.Energy_Switch, cardType=CardType.ITEM)
        energy_switch = make_pokemon(id=jm.Energy_Switch)
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])  # 雷0闘1
        my_state = make_player_state(
            active_pokemon=raging_bolt, bench=[],
            hand=[energy_switch], deck_count=40, prize_count=6,
        )
        obs, o = self._make_obs_with_hand_card(jm.Energy_Switch, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score < 7000
```

- [ ] **Step 6: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k test_energy_switch_scores`
Expected: FAIL（`_score_play_option`が未知カードとしてデフォルトの1000を返すため`test_energy_switch_scores_high...`がFAIL。もう一方は1000<7000でPASSしてしまうが、次のStepで両方を正しく検証する）

- [ ] **Step 7: `_score_play_option`にエネルギーつけかえの分岐を追加する**

`src/jamoraiko_agent/main.py`の`_score_play_option`関数内、`if card.id == Energy_Retrieval:`ブロック（359-360行目）の直後に追加：

```python
    if card.id == Energy_Switch:
        if _raging_bolt_ex_needs_lightning(my_state) and _find_energy_switch_source(my_state) is not None:
            return 7500  # タケルライコexが雷0枚で、ベンチに余剰供給元がある時のみ高優先
        return 200
```

- [ ] **Step 8: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k test_energy_switch_scores`
Expected: PASS（2件）

- [ ] **Step 9: 失敗するテストを書く（CARDサブ選択：DETACH_FROM / ATTACH_FROM）**

`tests/test_jamoraiko_agent.py`の`class TestScoreCardOptionDispatch:`の最後に追加：

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

    def test_dispatches_attach_from_prefers_raging_bolt_ex_needing_lightning(self):
        from cg.api import Option, SelectContext

        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])  # 雷0闘1
        other = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4, 4, 4])
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[other])
        obs = MagicMock()
        obs.current.players = [my_state]
        o_raging = Option(type=OptionType.CARD, area=AreaType.ACTIVE, index=0, playerIndex=0)
        o_other = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score_raging = jm._score_card_option(obs, o_raging, SelectContext.ATTACH_FROM, my_index=0, fs=fs, plan=plan)
        score_other = jm._score_card_option(obs, o_other, SelectContext.ATTACH_FROM, my_index=0, fs=fs, plan=plan)
        assert score_raging > score_other
```

- [ ] **Step 10: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k "test_dispatches_detach_from or test_dispatches_attach_from"`
Expected: FAIL（`DETACH_FROM`/`ATTACH_FROM`は`_score_card_option`の`match`文で`case _: return 0`に落ち、両者同スコアでassertが失敗）

- [ ] **Step 11: `_score_card_option`に新規ケースとスコアリング関数を追加する**

`src/jamoraiko_agent/main.py`の`_score_discard_candidate`関数（439-451行目）の直後に追加：

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


def _score_energy_switch_destination_candidate(card) -> int:
    """OptionType.CARD / SelectContext.ATTACH_FROM のスコアを返す
    （エネルギーつけかえで雷エネルギーを付け直す先のポケモンを選ぶ）"""
    if not isinstance(card, Pokemon):
        return 0
    if card.id == Raging_Bolt_ex:
        return 500 if card.energies.count(EnergyType.LIGHTNING) < 1 else -500
    return 0
```

`_score_card_option`関数内の`match context:`（459-469行目）に2ケース追加：

```python
def _score_card_option(obs, o, context, my_index: int, fs: FieldState, plan: AttackPlan) -> int:
    """OptionType.CARD のスコアをコンテキスト別に返す"""
    card = get_card(obs, o.area, o.index, o.playerIndex)
    if card is None:
        return 0
    match context:
        case SelectContext.SETUP_ACTIVE_POKEMON:
            return _score_setup_active(card.id)
        case SelectContext.SWITCH | SelectContext.TO_ACTIVE:
            return _score_switch_target(card, o, my_index, plan)
        case SelectContext.TO_HAND | SelectContext.TO_BENCH:
            return _score_search_candidate(card.id, fs)
        case SelectContext.DISCARD:
            return _score_discard_candidate(card.id, fs)
        case SelectContext.DETACH_FROM:
            return _score_energy_switch_source_candidate(card)
        case SelectContext.ATTACH_FROM:
            return _score_energy_switch_destination_candidate(card)
        case _:
            return 0
```

- [ ] **Step 12: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k "test_dispatches_detach_from or test_dispatches_attach_from"`
Expected: PASS（2件）

Run: `uv run pytest -q`
Expected: 全件PASS（回帰なし）

- [ ] **Step 13: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: エネルギーつけかえのPLAY/CARDスコアリングを実装（タケルライコexへのテンポ短縮）"
```

---

### Task 5: `OptionType.ENERGY`実装（きょくらいごうの捨てエネルギー選択）

**Files:**
- Modify: `src/jamoraiko_agent/main.py`（`_score_option`の`match`文）
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Produces: `_score_option`が`OptionType.ENERGY`を常に高スコア（9000）で返すようになる

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_jamoraiko_agent.py`の末尾（Task 1で追加した`TestScoreOptionKilowattrelAbility`クラスの後）に追加：

```python
class TestScoreOptionEnergyType:
    def test_energy_option_always_scores_high(self):
        from cg.api import Option, SelectContext

        o = Option(type=OptionType.ENERGY, area=AreaType.ACTIVE, index=0, energyIndex=0, count=1)
        fs = jm.FieldState(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
            active_fighting_energy_count=0,
        )
        plan = jm.AttackPlan()
        score = jm._score_option(
            obs=MagicMock(), o=o, context=SelectContext.DISCARD_ENERGY, my_index=0,
            state=None, my_state=make_player_state(), fs=fs, plan=plan,
        )
        assert score == 9000
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestScoreOptionEnergyType`
Expected: FAIL（`OptionType.ENERGY`は`match`文の`case _: return 0`に落ち、score==0）

- [ ] **Step 3: `_score_option`に`OptionType.ENERGY`ケースを追加する**

`src/jamoraiko_agent/main.py`の`_score_option`関数内、`case OptionType.RETREAT:`（497-498行目）の直前に追加：

```python
        case OptionType.ENERGY:
            return 9000  # きょくらいごうの追加ダメージ用：提示された基本エネルギーは常に捨てる
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestScoreOptionEnergyType`
Expected: PASS

Run: `uv run pytest -q`
Expected: 全件PASS（回帰なし）

- [ ] **Step 5: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: OptionType.ENERGYを実装（きょくらいごうの捨てエネルギーは常に貪欲に選択）"
```

---

### Task 6: タケルライコexの「はじけるほうこう」抑制

**Files:**
- Modify: `src/jamoraiko_agent/main.py`（`calc_attack_plan`、新規ヘルパー`_raging_bolt_ex_has_growth_path`）
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: `_find_energy_switch_source`（Task 4で実装済み）、`Energy_Switch`定数（Task 2で実装済み）
- Produces: `calc_attack_plan`が、まだ伸びる見込みがある間ははじけるほうこうを候補から除外する

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_jamoraiko_agent.py`の`class TestCalcAttackPlan:`の最後（`test_bellowing_thunder_excluded_when_no_fighting_energy_even_if_lethal`の後）に追加：

```python
    def test_burst_roar_suppressed_when_hand_has_lightning_energy(self):
        """手札に雷エネがまだあり、きょくらいごうへの伸びしろが残っている間は
        はじけるほうこう（ダメージ0・手札全トラッシュ）を選ばせない"""
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])  # 雷0闘1＝はじけるほうこうのみ発動可能
        fs = self._fs(
            active_energy_count=1, active_fighting_energy_count=1,
            own_board_basic_energy_total=1,
            hand_counts=defaultdict(int, {jm.Basic_Lightning_Energy: 1}),
        )
        my_state = make_player_state(active_pokemon=raging_bolt, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(raging_bolt, op_active_hp=200, fs=fs, my_state=my_state)
        assert plan.attacker_id == -1  # 温存のため候補なし

    def test_burst_roar_allowed_when_no_growth_path_remains(self):
        """手札に闘・雷どちらも無く、エネルギーつけかえの供給元も無い時は
        従来通りはじけるほうこうが選ばれる（山札に余裕がある前提）"""
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])
        fs = self._fs(
            active_energy_count=1, active_fighting_energy_count=1,
            own_board_basic_energy_total=1,
        )
        my_state = make_player_state(active_pokemon=raging_bolt, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(raging_bolt, op_active_hp=200, fs=fs, my_state=my_state)
        assert plan.attack_id == 1005  # Burst Roar

    def test_burst_roar_suppressed_when_energy_switch_source_available(self):
        """手札にエネルギーつけかえがあり、ベンチに供給元があるなら
        まだ伸びる見込みがあるため温存する"""
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])
        fs = self._fs(
            active_energy_count=1, active_fighting_energy_count=1,
            own_board_basic_energy_total=1,
            hand_counts=defaultdict(int, {jm.Energy_Switch: 1}),
        )
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 供給元あり
        my_state = make_player_state(
            active_pokemon=raging_bolt, bench=[bellibolt], deck_count=40, prize_count=6,
        )
        plan = jm.calc_attack_plan(raging_bolt, op_active_hp=200, fs=fs, my_state=my_state)
        assert plan.attacker_id == -1
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k "test_burst_roar_suppressed_when_hand_has_lightning_energy or test_burst_roar_allowed_when_no_growth_path_remains or test_burst_roar_suppressed_when_energy_switch_source_available"`
Expected: `test_burst_roar_suppressed_when_hand_has_lightning_energy`と`test_burst_roar_suppressed_when_energy_switch_source_available`がFAIL（現状ではじけるほうこうが無条件で選ばれ`plan.attacker_id == jm.Raging_Bolt_ex`になる）。`test_burst_roar_allowed_when_no_growth_path_remains`は現状の動作と一致するためPASSする（回帰確認用）

- [ ] **Step 3: `_raging_bolt_ex_has_growth_path`ヘルパーを追加する**

`src/jamoraiko_agent/main.py`の`_raging_bolt_ex_needs_lightning`関数（Task 4で追加済み）の直後に追加：

```python
def _raging_bolt_ex_has_growth_path(fs: FieldState, my_state) -> bool:
    """タケルライコexがまだきょくらいごう着地に伸びる見込みがあるか
    （手札に闘/雷の基本エネルギーがある、またはエネルギーつけかえの供給元がある）"""
    if fs.hand_counts[Basic_Fighting_Energy] > 0 or fs.hand_counts[Basic_Lightning_Energy] > 0:
        return True
    if fs.hand_counts[Energy_Switch] > 0 and _find_energy_switch_source(my_state) is not None:
        return True
    return False
```

- [ ] **Step 4: `calc_attack_plan`の候補フィルタに抑制条件を追加する**

`src/jamoraiko_agent/main.py`の`calc_attack_plan`関数内、候補ループ（184-196行目）を変更：

```python
    candidates = []
    for atk in ATTACKERS:
        if atk.id != my_active.id:
            continue
        if fs.active_energy_count < atk.energy_required:
            continue
        if atk.requires_fighting and fs.active_fighting_energy_count < 1:
            continue
        if atk.is_utility and 6 > _safe_draws(my_state):
            continue  # 山札温存
        if atk.is_utility and atk.id == Raging_Bolt_ex and _raging_bolt_ex_has_growth_path(fs, my_state):
            continue  # きょくらいごうへの伸びしろが残っている間ははじけるほうこうを温存
        damage = atk.damage_fn(fs)
        is_lethal = (not atk.is_utility) and damage >= op_active_hp
        candidates.append((atk, damage, is_lethal))
```

- [ ] **Step 5: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k "test_burst_roar_suppressed_when_hand_has_lightning_energy or test_burst_roar_allowed_when_no_growth_path_remains or test_burst_roar_suppressed_when_energy_switch_source_available"`
Expected: PASS（3件）

Run: `uv run pytest -q`
Expected: 全件PASS（回帰なし。特に既存の`test_burst_roar_only_chosen_when_no_other_attack_available`と`test_burst_roar_blocked_when_deck_thin`が新条件の影響を受けないことを確認）

- [ ] **Step 6: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "fix: きょくらいごうへの伸びしろが残る間ははじけるほうこうを選ばせないよう抑制"
```

---

## 全タスク完了後の最終確認

- [ ] `uv run pytest -q`で全件PASSを確認（Task 1〜6の新規テスト分だけ増分し、既存分は0件failであること）
- [ ] `git log --oneline`でTask 1〜6の6コミットが積まれていることを確認
- [ ] 最終ブランチ全体レビュー（`superpowers:requesting-code-review`のcode-reviewer.mdテンプレート使用）を実施
- [ ] レビュー完了後、`docs/implementations/[日付]-jamoraiko-energy-logic-fix.md`に実装サマリーを保存
- [ ] レビュー結果を`docs/reviews/[日付]-jamoraiko-energy-logic-fix.md`に保存
- [ ] マージ後、ユーザーがKaggle上でノートブックを再実行し、`jamoraiko_vs_iono_results.json`（勝率）と`jamoraiko_vs_iono_turn_log.json`（手番ログ）を再取得して効果を検証する
