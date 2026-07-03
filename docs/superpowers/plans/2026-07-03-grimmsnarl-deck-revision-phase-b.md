# グリムスナールexデッキ フェーズB（座組整理・キチキギスex採用）実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `decks/grimmsnarl_20260701.py` からスボミー(235)/コダック(858)/シャリタツ(122)を削除しキチキギスex(140)を2枚採用・イベルタルを2枚に増量する。あわせて`src/grimmsnarl_agent/main.py`を新カード構成に追従させる（定数整理、キチキギスexへのエネルギー配分、クルーエルアローの攻撃スコアリング、特性の優先度）。

**Architecture:** デッキ定義ファイルの構成変更（Task 1）→ カードID定数の整理（Task 2）→ エージェントロジックへの追従修正を機能ごとに3タスクに分割（Task 3〜5：エネルギー配分／攻撃スコアリング／特性優先度）→ 全体回帰確認と実装サマリー作成（Task 6）。設計書は`docs/superpowers/specs/2026-07-03-grimmsnarl-deck-revision-phase-b-design.md`。

**Tech Stack:** Python 3.12 / uv / pytest

## Global Constraints

- デッキは必ず合計60枚（ポケモン20体・トレーナーズ28枚・エネルギー12枚の内訳を維持）
- エネルギー以外のカードは1種4枚まで
- ACE SPECカード（Secret Box, ID 1092）は合計1枚まで（今回変更なし）
- 全コメント・ドキュメントは日本語（CLAUDE.md準拠）
- 各タスック終了時に`uv run pytest -q`で回帰なしを確認してからコミットする

---

## Task 1: デッキ構成を新座組に更新する

**Files:**
- Modify: `tests/test_grimmsnarl_deck.py`
- Modify: `decks/grimmsnarl_20260701.py`

**Interfaces:**
- Consumes: `decks.grimmsnarl_20260701.DECK`（`list[tuple[int, int]]`）
- Produces: 新DECK構成（後続タスクのエージェントロジックが前提とするカードID: `140`=キチキギスex, `689`=イベルタル2枚。`235`/`122`/`858`は不在になる）

- [ ] **Step 1: `tests/test_grimmsnarl_deck.py` の末尾に以下のテストを追加する**

```python
def test_phase_b_removed_pokemon_absent():
    ids = {card_id for card_id, _ in DECK}
    assert 235 not in ids, "Budew(スボミー) はフェーズBで削除されたはず"
    assert 122 not in ids, "Tatsugiri(シャリタツ) はフェーズBで削除されたはず"
    assert 858 not in ids, "Psyduck(コダック) はフェーズBで削除されたはず"


def test_fezandipiti_ex_count():
    count = sum(c for i, c in DECK if i == 140)
    assert count == 2, "キチキギスex(140)は2枚採用のはず"


def test_yveltal_count_increased():
    count = sum(c for i, c in DECK if i == 689)
    assert count == 2, "イベルタル(689)はフェーズBで2枚に増量されたはず"
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_grimmsnarl_deck.py -v -k "phase_b or fezandipiti or yveltal_count_increased"`
Expected: 3件すべてFAIL（`test_phase_b_removed_pokemon_absent`は235/122/858がまだDECKに存在するため失敗、`test_fezandipiti_ex_count`は0枚のため失敗、`test_yveltal_count_increased`は現在1枚のため失敗）

- [ ] **Step 3: `decks/grimmsnarl_20260701.py` を編集する**

ファイル冒頭のコメント（1〜6行目）に以下を追記する:

```python
# フェーズB改修（2026-07-03）: 特性専用ポケモンの座組を整理し、バグ影響範囲を縮小。
#   設計書: docs/superpowers/specs/2026-07-03-grimmsnarl-deck-revision-phase-b-design.md
#   スボミー/コダック/シャリタツを削除、キチキギスex(140)を新規採用、イベルタルを増量。
```

ポケモンブロック内の該当行を編集する:

```python
    (235,  1),   # Budew（相手のグッズ使用を1ターン封じる）
```
↓ この行を削除

```python
    (122,  1),   # Tatsugiri（特性: バトル場にいる間、山札上6枚からサポートを回収）
```
↓ この行を削除

```python
    (689,  1),   # Yveltal（わしづかみ：相手を次の番にげられなくする。ガチグマの代替）
```
↓
```python
    (689,  2),   # Yveltal（わしづかみ：相手を次の番にげられなくする。ガチグマの代替）
    (140,  2),   # Fezandipiti ex（キチキギスex。210HP高耐久・悪エネで実際に攻撃可能。
                 #                特性「さかてにとる」はバトル場条件なしで安全に発動）
```

```python
    (858,  1),   # Psyduck（特性: 自傷前提の特性を封じる）
```
↓ この行を削除

編集後のポケモンブロックは以下の20体になる（合計3+2+3+2+2+3+1+2+2=20）:

```python
DECK = [
    # --- ポケモン: 20体 ---
    (646,  3),   # Marnie's Impidimp（進化元・Filchで初動ドロー・70HP）
    (647,  2),   # Marnie's Morgrem（進化中継・Rare Candy未引き時の保険を強化）
    (648,  3),   # Marnie's Grimmsnarl ex（メインアタッカー）
    (860,  2),   # Snorunt（Froslassの進化元）
    (104,  2),   # Froslass（特性: 毎ターン全特性持ちポケモンに1ダメカン。攻撃は使わない前提）
    (112,  3),   # Munkidori（Adrena-Brainでダメカン移動。Froslassの副産物ダメカンを転嫁）
    (343,  1),   # Shaymin（特性: 自分のルール無しベンチポケモンへのダメージを無効化）
    (689,  2),   # Yveltal（わしづかみ：相手を次の番にげられなくする。ガチグマの代替）
    (140,  2),   # Fezandipiti ex（キチキギスex。210HP高耐久・悪エネで実際に攻撃可能。
                 #                特性「さかてにとる」はバトル場条件なしで安全に発動）

    # --- トレーナーズ: 28枚 ---
    (1152, 4),   # Poké Pad（ポケモンサーチ）
    (1079, 3),   # Rare Candy（Impidimp→Grimmsnarl ex 一気進化）
    (1086, 2),   # Buddy-Buddy Poffin（低HP基本ポケモンをベンチ展開）
    (1097, 2),   # Night Stretcher（トラッシュ回収・山札を減らさない）
    (1227, 4),   # Lillie's Determination（手札リフレッシュ）
    (1182, 3),   # Boss's Orders（ベンチの弱ったポケモンを強制的にバトル場へ・KOを補助）
    (1259, 3),   # Spikemuth Gym（毎ターンMarnie's系サーチ）
    (1116, 2),   # Energy Switch（基本エネルギーの付け替え）
    (1092, 1),   # Secret Box（ACE SPEC・手札3枚トラッシュでグッズ/どうぐ/サポートをサーチ）
    (1174, 1),   # Air Balloon（にげるためのエネルギーを2個軽減）
    (1219, 3),   # Team Rocket's Petrel（トレーナーズ全般をサーチ）

    # --- エネルギー: 12枚 ---
    (7,   12),   # Basic {D} Energy
]
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_deck.py -v`
Expected: 全件PASS

- [ ] **Step 5: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add decks/grimmsnarl_20260701.py tests/test_grimmsnarl_deck.py
git commit -m "$(cat <<'EOF'
feat: グリムスナールexデッキの座組を整理しキチキギスexを採用

スボミー/コダック/シャリタツを削除し、210HP高耐久で実際に攻撃可能な
キチキギスex(140)を2枚採用。イベルタルも2枚に増量。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: カードID定数を整理する（Budew/Tatsugiri/Psyduck削除、Fezandipiti_ex追加）

**Files:**
- Modify: `src/grimmsnarl_agent/main.py:11-29`
- Modify: `tests/test_grimmsnarl_agent.py`（`gm.Budew`参照3箇所を`gm.Shaymin`に置換）

**Interfaces:**
- Consumes: なし
- Produces: `gm.Fezandipiti_ex = 140`（Task 3〜5で使用）、`gm.SUPPORT_ONLY_IDS = {Froslass, Shaymin}`（`gm.Budew`/`gm.Tatsugiri`/`gm.Psyduck`は以後存在しない）

- [ ] **Step 1: 既存テストが`gm.Budew`に依存していることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k "support_only or munkidori_not_penalized"`
Expected: 3件PASS（この時点ではまだ`gm.Budew`が存在するため通る。これは削除前のベースライン確認）

- [ ] **Step 2: `tests/test_grimmsnarl_agent.py`内の`gm.Budew`参照3箇所を`gm.Shaymin`に置換する**

1箇所目（`test_switch_support_only_pokemon_scores_lower_than_attacker_same_hp`内）:

```python
    def test_switch_support_only_pokemon_scores_lower_than_attacker_same_hp(self):
        """特性専用ポケモン（シェイミ）はHPが同じでも実戦向きポケモン（イベルタル）より低スコアになること"""
        shaymin = make_pokemon(id=gm.Shaymin, hp=100)
        yveltal = make_pokemon(id=gm.Yveltal, hp=100)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), bench=[shaymin, yveltal])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o_shaymin = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        o_yveltal = Option(type=OptionType.CARD, area=AreaType.BENCH, index=1, playerIndex=0)
        score_shaymin = gm._score_card_option(obs, o_shaymin, SelectContext.SWITCH, 0, fs, defaultdict(int))
        score_yveltal = gm._score_card_option(obs, o_yveltal, SelectContext.SWITCH, 0, fs, defaultdict(int))
        assert score_yveltal > score_shaymin
```

2箇所目（`test_to_active_support_only_pokemon_deprioritized_even_with_higher_hp`内）:

```python
    def test_to_active_support_only_pokemon_deprioritized_even_with_higher_hp(self):
        """低HPの実戦向きポケモンでも、高HPの特性専用ポケモンより優先されること
        （バトルログ83347688 step91・83438721 step125で実際に低HP特性要員が誤って前に出た事例の再現）"""
        shaymin_high_hp = make_pokemon(id=gm.Shaymin, hp=150)
        yveltal_low_hp = make_pokemon(id=gm.Yveltal, hp=50)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), bench=[shaymin_high_hp, yveltal_low_hp])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o_shaymin = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        o_yveltal = Option(type=OptionType.CARD, area=AreaType.BENCH, index=1, playerIndex=0)
        score_shaymin = gm._score_card_option(obs, o_shaymin, SelectContext.TO_ACTIVE, 0, fs, defaultdict(int))
        score_yveltal = gm._score_card_option(obs, o_yveltal, SelectContext.TO_ACTIVE, 0, fs, defaultdict(int))
        assert score_yveltal > score_shaymin
```

3箇所目（`test_switch_munkidori_not_penalized_like_support_only_pokemon`内）:

```python
    def test_switch_munkidori_not_penalized_like_support_only_pokemon(self):
        """マシマシラは特性にエネルギー要求があり攻撃も可能なため、特性専用ポケモンほど減点されないこと"""
        shaymin   = make_pokemon(id=gm.Shaymin, hp=100)
        munkidori = make_pokemon(id=gm.Munkidori, hp=100)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), bench=[shaymin, munkidori])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o_shaymin   = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        o_munkidori = Option(type=OptionType.CARD, area=AreaType.BENCH, index=1, playerIndex=0)
        score_shaymin   = gm._score_card_option(obs, o_shaymin, SelectContext.SWITCH, 0, fs, defaultdict(int))
        score_munkidori = gm._score_card_option(obs, o_munkidori, SelectContext.SWITCH, 0, fs, defaultdict(int))
        assert score_munkidori > score_shaymin
```

- [ ] **Step 3: 置換後もテストが通ることを確認する（`gm.Shaymin`は既存定数のため、この時点でPASSするはず）**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k "support_only or munkidori_not_penalized"`
Expected: 3件PASS

- [ ] **Step 4: `src/grimmsnarl_agent/main.py:11-29` を編集する**

現状:

```python
# ==================== カードID定数 ====================
# 20260702改修：Morpeko/Dudunsparce/Dunsparce/Dawn/Xerosic's Machinations/
# Energy Recycler/Hero's Capeはデッキから削除済みのため定数ごと削除。
# 代わりにTeam Rocket's Petrelを追加（docs/superpowers/specs/2026-07-02-grimmsnarl-deck-revision-design.md）
Impidimp      = 646
Morgrem       = 647
Grimmsnarl_ex = 648
Munkidori     = 112
Froslass      = 104
Budew         = 235
Shaymin       = 343
Tatsugiri     = 122
Yveltal       = 689
Psyduck       = 858

# 特性が「場にいれば無条件で発動」する専用要員。バトル場に出す前提のカードではないため、
# SWITCH/TO_ACTIVEでは他に選択肢がある限り選ばれないよう明確に減点する。
# Munkidoriは特性発動にエネルギー要求があり攻撃も可能なため対象外。
SUPPORT_ONLY_IDS = {Froslass, Budew, Shaymin, Tatsugiri, Psyduck}
```

変更後:

```python
# ==================== カードID定数 ====================
# 20260702改修：Morpeko/Dudunsparce/Dunsparce/Dawn/Xerosic's Machinations/
# Energy Recycler/Hero's Capeはデッキから削除済みのため定数ごと削除。
# 代わりにTeam Rocket's Petrelを追加（docs/superpowers/specs/2026-07-02-grimmsnarl-deck-revision-design.md）
# フェーズB改修（2026-07-03）：Budew/Tatsugiri/Psyduckはデッキから削除済みのため定数ごと削除。
# 代わりにFezandipiti_exを追加（docs/superpowers/specs/2026-07-03-grimmsnarl-deck-revision-phase-b-design.md）
Impidimp       = 646
Morgrem        = 647
Grimmsnarl_ex  = 648
Munkidori      = 112
Froslass       = 104
Shaymin        = 343
Yveltal        = 689
Fezandipiti_ex = 140

# 特性が「場にいれば無条件で発動」する専用要員。バトル場に出す前提のカードではないため、
# SWITCH/TO_ACTIVEでは他に選択肢がある限り選ばれないよう明確に減点する。
# Munkidoriは特性発動にエネルギー要求があり攻撃も可能なため対象外。
# Fezandipiti_exは210HPの実戦アタッカーであり特性もバトル場条件なしのため対象外。
SUPPORT_ONLY_IDS = {Froslass, Shaymin}
```

- [ ] **Step 5: リポジトリ全体のテストを実行し回帰がないことを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS（`gm.Budew`/`gm.Tatsugiri`/`gm.Psyduck`への他の参照が残っていればここでAttributeErrorになるはずだが、事前のgrep調査で本リポジトリ内に他の参照がないことを確認済み）

- [ ] **Step 6: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "$(cat <<'EOF'
refactor: 削除カードの定数を整理しキチキギスex定数を追加

Budew/Tatsugiri/Psyduckはフェーズ B でデッキから削除済みのため定数と
SUPPORT_ONLY_IDSから除去。Fezandipiti_ex(140)を新規追加。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: キチキギスexへのエネルギー配分ロジックを追加する

**Files:**
- Modify: `src/grimmsnarl_agent/main.py:228-239`（`_score_attach`）
- Modify: `tests/test_grimmsnarl_agent.py`（`TestScoreAttach`クラスにテスト追加）

**Interfaces:**
- Consumes: `gm.Fezandipiti_ex`（Task 2で追加済み）、`FieldState.grimmsnarl_energy_count`（既存）
- Produces: `_score_attach(pokemon, area, card_id, fs)` がキチキギスexを認識するようになる（Task 4の攻撃判断が前提とする「キチキギスexにエネルギーが配分され得る」という挙動）

- [ ] **Step 1: `tests/test_grimmsnarl_agent.py`の`TestScoreAttach`クラス末尾に以下のテストを追加する**

```python
    def test_basic_d_energy_to_fezandipiti_allowed_when_grimmsnarl_attack_ready(self):
        """グリムスナールexがシャドーバレット分（2エネ）を確保済みなら、余剰エネルギーをキチキギスexに貼れること"""
        fezandipiti = make_pokemon(id=gm.Fezandipiti_ex, energies=[])
        fs = self._make_fs_with_grimmsnarl_energy(2)
        score = gm._score_attach(fezandipiti, AreaType.BENCH, gm.Basic_D_Energy, fs)
        assert score > 0

    def test_basic_d_energy_to_fezandipiti_denied_when_grimmsnarl_not_attack_ready(self):
        """グリムスナールexがまだ攻撃可能エネルギー未確保なら、キチキギスexへの分配は認めないこと"""
        fezandipiti = make_pokemon(id=gm.Fezandipiti_ex, energies=[])
        fs = self._make_fs_with_grimmsnarl_energy(0)
        assert gm._score_attach(fezandipiti, AreaType.BENCH, gm.Basic_D_Energy, fs) == -1

    def test_basic_d_energy_to_fezandipiti_denied_when_already_has_3_energy(self):
        """クルーエルアローは悪悪+無色1=3エネで発動するため、3枚目以降は不要"""
        fezandipiti = make_pokemon(id=gm.Fezandipiti_ex, energies=[7, 7, 7])
        fs = self._make_fs_with_grimmsnarl_energy(2)
        assert gm._score_attach(fezandipiti, AreaType.BENCH, gm.Basic_D_Energy, fs) == -1

    def test_fezandipiti_energy_priority_lower_than_grimmsnarl(self):
        """キチキギスexへの配分スコアは、グリムスナールex本体への配分スコアを上回らないこと
        （メインアタッカーの攻撃を絶対に阻害しない既存方針の維持）"""
        grimmsnarl_low = make_pokemon(id=gm.Grimmsnarl_ex, energies=[])
        fezandipiti    = make_pokemon(id=gm.Fezandipiti_ex, energies=[])
        fs = self._make_fs_with_grimmsnarl_energy(2)
        score_grimmsnarl  = gm._score_attach(grimmsnarl_low, AreaType.ACTIVE, gm.Basic_D_Energy, fs)
        score_fezandipiti = gm._score_attach(fezandipiti, AreaType.BENCH, gm.Basic_D_Energy, fs)
        assert score_grimmsnarl > score_fezandipiti
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k fezandipiti`
Expected: 4件すべてFAIL（`_score_attach`はまだキチキギスexを認識せず、常に`-1`を返すため）

- [ ] **Step 3: `src/grimmsnarl_agent/main.py:228-239`の`_score_attach`を編集する**

現状:

```python
def _score_attach(pokemon: "Pokemon", area: AreaType, card_id: int, fs: FieldState) -> int:
    """ATTACH コンテキスト：エネルギー/ツールの付与先スコア"""
    energy_count = len(pokemon.energies)
    if card_id == Basic_D_Energy:
        if pokemon.id == Grimmsnarl_ex:
            return 9000 - energy_count * 1000
        if pokemon.id == Munkidori and energy_count == 0 and fs.grimmsnarl_energy_count >= 2:
            # アドレナブレインはエネルギー1枚で発動するため、グリムスナールexが
            # シャドーバレット分（2エネ）を確保済みの場合のみ余剰分を分配する
            return 4000
        return -1
    return 3000
```

変更後:

```python
def _score_attach(pokemon: "Pokemon", area: AreaType, card_id: int, fs: FieldState) -> int:
    """ATTACH コンテキスト：エネルギー/ツールの付与先スコア"""
    energy_count = len(pokemon.energies)
    if card_id == Basic_D_Energy:
        if pokemon.id == Grimmsnarl_ex:
            return 9000 - energy_count * 1000
        if pokemon.id == Fezandipiti_ex and energy_count < 3 and fs.grimmsnarl_energy_count >= 2:
            # クルーエルアローは悪悪+無色1=3エネで発動。グリムスナールexが
            # シャドーバレット分（2エネ）を確保済みの場合のみ余剰分を分配する
            return 5000 - energy_count * 500
        if pokemon.id == Munkidori and energy_count == 0 and fs.grimmsnarl_energy_count >= 2:
            # アドレナブレインはエネルギー1枚で発動するため、グリムスナールexが
            # シャドーバレット分（2エネ）を確保済みの場合のみ余剰分を分配する
            return 4000
        return -1
    return 3000
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k fezandipiti`
Expected: 4件すべてPASS

- [ ] **Step 5: リポジトリ全体のテストを実行し回帰がないことを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "$(cat <<'EOF'
feat: キチキギスexへの基本エネルギー配分ロジックを追加

グリムスナールexの攻撃分（2エネ）確保後、余剰の基本エネルギーを
キチキギスex（クルーエルアロー悪悪+無色1）にも配分できるようにする。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: クルーエルアローの攻撃スコアリングを追加する

**Files:**
- Modify: `src/grimmsnarl_agent/main.py:47-61`（`_build_card_table`, `Shadow_Bullet_ID`宣言部）
- Modify: `src/grimmsnarl_agent/main.py:242-248`（`_score_attack`）
- Modify: `tests/test_grimmsnarl_agent.py`（`mock_card_table`フィクスチャ、`TestScoreAttack`クラス）

**Interfaces:**
- Consumes: `gm.Fezandipiti_ex`（Task 2）、`FieldState.op_active_hp` / `FieldState.op_bench_hp`（既存）
- Produces: `gm.Cruel_Arrow_ID`（実行時に`_build_card_table()`が設定。テストでは`Shadow_Bullet_ID`と同様に直接monkeypatchする）

- [ ] **Step 1: `tests/test_grimmsnarl_agent.py`冒頭の`mock_card_table`フィクスチャを編集する**

現状:

```python
@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        gm.Impidimp:        MockCardData(cardId=gm.Impidimp, attacks=[9101]),
        gm.Morgrem:         MockCardData(cardId=gm.Morgrem, stage1=True, attacks=[9101]),
        gm.Grimmsnarl_ex:   MockCardData(cardId=gm.Grimmsnarl_ex, stage2=True, ex=True, attacks=[9102]),
        gm.Munkidori:       MockCardData(cardId=gm.Munkidori, attacks=[9104]),
        gm.Rare_Candy:      MockCardData(cardId=gm.Rare_Candy, cardType=CardType.ITEM),
        gm.Buddy_Buddy_Poffin: MockCardData(cardId=gm.Buddy_Buddy_Poffin, cardType=CardType.ITEM),
        gm.Lillie_Determination: MockCardData(cardId=gm.Lillie_Determination, cardType=CardType.SUPPORTER),
        gm.Team_Rocket_Petrel: MockCardData(cardId=gm.Team_Rocket_Petrel, cardType=CardType.SUPPORTER),
        gm.Basic_D_Energy:  MockCardData(cardId=gm.Basic_D_Energy, cardType=CardType.BASIC_ENERGY),
    }
    monkeypatch.setattr(gm, "card_table", table)
    monkeypatch.setattr(gm, "Shadow_Bullet_ID", 9102)
    return table
```

変更後:

```python
@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        gm.Impidimp:        MockCardData(cardId=gm.Impidimp, attacks=[9101]),
        gm.Morgrem:         MockCardData(cardId=gm.Morgrem, stage1=True, attacks=[9101]),
        gm.Grimmsnarl_ex:   MockCardData(cardId=gm.Grimmsnarl_ex, stage2=True, ex=True, attacks=[9102]),
        gm.Munkidori:       MockCardData(cardId=gm.Munkidori, attacks=[9104]),
        gm.Fezandipiti_ex:  MockCardData(cardId=gm.Fezandipiti_ex, ex=True, attacks=[9105]),
        gm.Rare_Candy:      MockCardData(cardId=gm.Rare_Candy, cardType=CardType.ITEM),
        gm.Buddy_Buddy_Poffin: MockCardData(cardId=gm.Buddy_Buddy_Poffin, cardType=CardType.ITEM),
        gm.Lillie_Determination: MockCardData(cardId=gm.Lillie_Determination, cardType=CardType.SUPPORTER),
        gm.Team_Rocket_Petrel: MockCardData(cardId=gm.Team_Rocket_Petrel, cardType=CardType.SUPPORTER),
        gm.Basic_D_Energy:  MockCardData(cardId=gm.Basic_D_Energy, cardType=CardType.BASIC_ENERGY),
    }
    monkeypatch.setattr(gm, "card_table", table)
    monkeypatch.setattr(gm, "Shadow_Bullet_ID", 9102)
    monkeypatch.setattr(gm, "Cruel_Arrow_ID", 9105)
    return table
```

- [ ] **Step 2: `TestScoreAttack`クラス末尾に以下のテストを追加する**

```python
    def test_cruel_arrow_non_lethal_score(self):
        fs = self._make_fs(op_hp=200)
        assert gm._score_attack(9105, fs) == 2000  # Cruel_Arrow_ID (mocked)、確定KOでない場合

    def test_cruel_arrow_lethal_on_active_scores_higher(self):
        """相手バトルポケモンのHPが100以下（確定KO）なら、非確定KO時よりスコアが高くなること"""
        fs_lethal     = self._make_fs(op_hp=80)
        fs_non_lethal = self._make_fs(op_hp=200)
        assert gm._score_attack(9105, fs_lethal) > gm._score_attack(9105, fs_non_lethal)

    def test_cruel_arrow_lethal_on_bench_also_scores_higher(self):
        """クルーエルアローはベンチも狙えるため、ベンチにHP100以下の対象がいる場合も高スコアになること"""
        fs = self._make_fs(op_hp=200, op_bench_hp=[90])
        assert gm._score_attack(9105, fs) == 5000

    def test_cruel_arrow_lethal_scores_higher_than_retreat(self):
        fs = self._make_fs(op_hp=80)
        assert gm._score_attack(9105, fs) == 5000
        assert gm._score_attack(9105, fs) > 3000  # RETREATのスコア（agent()内でインライン計算）
```

- [ ] **Step 3: テストが失敗することを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k cruel_arrow`
Expected: 4件すべてFAIL（`_score_attack`は`9105`を未知の攻撃として扱い、常にデフォルトの`1000`を返すため）

- [ ] **Step 4: `src/grimmsnarl_agent/main.py:47-61`を編集し`Cruel_Arrow_ID`を追加する**

現状:

```python
# ==================== アタックID（_build_card_table で設定）====================
Shadow_Bullet_ID: int = 0

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築し、攻撃IDも設定する"""
    global card_table, Shadow_Bullet_ID
    if not card_table:
        card_table       = {c.cardId: c for c in all_card_data()}
        grimmsnarl_data  = card_table[Grimmsnarl_ex]
        Shadow_Bullet_ID = grimmsnarl_data.attacks[0]  # Shadow Bullet
    return card_table
```

変更後:

```python
# ==================== アタックID（_build_card_table で設定）====================
Shadow_Bullet_ID: int = 0
Cruel_Arrow_ID: int = 0

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築し、攻撃IDも設定する"""
    global card_table, Shadow_Bullet_ID, Cruel_Arrow_ID
    if not card_table:
        card_table       = {c.cardId: c for c in all_card_data()}
        grimmsnarl_data  = card_table[Grimmsnarl_ex]
        Shadow_Bullet_ID = grimmsnarl_data.attacks[0]  # Shadow Bullet
        fezandipiti_data = card_table[Fezandipiti_ex]
        Cruel_Arrow_ID   = fezandipiti_data.attacks[0]  # Cruel Arrow
    return card_table
```

- [ ] **Step 5: `src/grimmsnarl_agent/main.py:242-248`の`_score_attack`を編集する**

現状:

```python
def _score_attack(attack_id: int, fs: FieldState) -> int:
    """ATTACK コンテキスト：ワザ選択スコア"""
    if attack_id == Shadow_Bullet_ID:
        # 相手バトルポケモンのHPがSHADOW_BULLET_DAMAGE以下ならShadow Bulletで確実にKOできる
        # （きぜつ確定）ので、RETREATの3000点より高くして撤退より攻撃を優先する
        return 5000 if fs.op_active_hp <= SHADOW_BULLET_DAMAGE else 2000
    return 1000
```

変更後:

```python
CRUEL_ARROW_DAMAGE = 100  # クルーエルアローの与ダメージ（相手1匹を選んで攻撃・ベンチも弱点抵抗力無視で狙える）


def _score_attack(attack_id: int, fs: FieldState) -> int:
    """ATTACK コンテキスト：ワザ選択スコア"""
    if attack_id == Shadow_Bullet_ID:
        # 相手バトルポケモンのHPがSHADOW_BULLET_DAMAGE以下ならShadow Bulletで確実にKOできる
        # （きぜつ確定）ので、RETREATの3000点より高くして撤退より攻撃を優先する
        return 5000 if fs.op_active_hp <= SHADOW_BULLET_DAMAGE else 2000
    if attack_id == Cruel_Arrow_ID:
        # クルーエルアローは相手1匹（バトル場・ベンチ問わず）を選んで攻撃できるため、
        # どちらかにCRUEL_ARROW_DAMAGE以下の確定KO対象がいれば優先する
        op_hps = [fs.op_active_hp, *fs.op_bench_hp]
        return 5000 if any(hp <= CRUEL_ARROW_DAMAGE for hp in op_hps) else 2000
    return 1000
```

- [ ] **Step 6: テストが通ることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k cruel_arrow`
Expected: 4件すべてPASS

- [ ] **Step 7: リポジトリ全体のテストを実行し回帰がないことを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 8: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "$(cat <<'EOF'
feat: キチキギスexのクルーエルアロー攻撃スコアリングを追加

Shadow_Bullet_IDと同じパターンでCruel_Arrow_IDをcard_tableから取得。
相手フィールド（バトル場+ベンチ）に確定KO対象がいれば優先する。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: キチキギスexの特性（さかてにとる）優先度を追加する

**Files:**
- Modify: `src/grimmsnarl_agent/main.py:383-390`（`agent()`関数内 `OptionType.ABILITY` 分岐）
- Modify: `tests/test_grimmsnarl_agent.py`（`TestAgent`クラスにテスト追加）

**Interfaces:**
- Consumes: `gm.Fezandipiti_ex`（Task 2）
- Produces: なし（`agent()`の最終挙動のみ）

- [ ] **Step 1: `tests/test_grimmsnarl_agent.py`の`TestAgent`クラスに、`test_ability_fires_before_non_lethal_attack`の直後として以下のテストを追加する**

```python
    def test_fezandipiti_ability_fires_before_non_lethal_attack(self):
        """キチキギスexの特性（さかてにとる）もマシマシラ同様、確定KOでない攻撃より優先して
        毎ターン使用されること"""
        fezandipiti = make_pokemon(id=gm.Fezandipiti_ex, energies=[7, 7, 7])
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, hp=300, max_hp=320, energies=[7, 7])
        my_ps = make_player_state(active_pokemon=grimmsnarl, bench=[fezandipiti])
        # op_state を指定しない場合、make_main_obs のデフォルトは hp=200（>180、非確定KO）
        options = [
            Option(type=OptionType.ABILITY, area=AreaType.BENCH, index=0),
            Option(type=OptionType.ATTACK, attackId=9102),  # Shadow_Bullet_ID (mocked)、非確定KO
        ]
        obs_dict = make_main_obs(my_state=my_ps, options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.ABILITY
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k fezandipiti_ability`
Expected: FAIL（現状の`ABILITY`分岐は`card.id == Munkidori`のみ2500点、キチキギスexは1200点にしかならず、非確定KO攻撃の2000点を下回るためATTACKが選ばれる）

- [ ] **Step 3: `src/grimmsnarl_agent/main.py:383-390`を編集する**

現状:

```python
            case OptionType.ABILITY:
                card = get_card(obs, o.area, o.index, my_index)
                if card is None:
                    score = 0
                else:
                    # アビリティは無償（ターンを消費しない）ため、非確定KOの攻撃（2000点）より
                    # 優先して毎ターン使用する。ただしEVOLVE（10000+）や確定KO攻撃（5000）は上回らない
                    score = 2500 if card.id == Munkidori else 1200
```

変更後:

```python
            case OptionType.ABILITY:
                card = get_card(obs, o.area, o.index, my_index)
                if card is None:
                    score = 0
                else:
                    # アビリティは無償（ターンを消費しない）ため、非確定KOの攻撃（2000点）より
                    # 優先して毎ターン使用する。ただしEVOLVE（10000+）や確定KO攻撃（5000）は上回らない
                    score = 2500 if card.id in (Munkidori, Fezandipiti_ex) else 1200
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k fezandipiti_ability`
Expected: PASS

- [ ] **Step 5: リポジトリ全体のテストを実行し回帰がないことを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "$(cat <<'EOF'
feat: キチキギスexの特性（さかてにとる）優先度をマシマシラと同格にする

無償で使えるアビリティのため、非確定KOの攻撃より優先して毎ターン使用する。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: 全体回帰確認とデッキCSV生成、実装サマリー作成

**Files:**
- Create: `docs/implementations/20260703-grimmsnarl-deck-revision-phase-b.md`

**Interfaces:**
- Consumes: Task 1〜5の全変更
- Produces: なし（ドキュメントのみ）

- [ ] **Step 1: リポジトリ全体のテストスイートを実行する**

Run: `uv run pytest -q`
Expected: 全件PASS（件数は既存177件 + Task 1で追加3件 + Task 3で追加4件 + Task 4で追加4件 + Task 5で追加1件 = 189件）

- [ ] **Step 2: デッキCSVを生成する**

Run: `uv run python -c "
from decks.grimmsnarl_20260701 import DECK
import datetime
rows = []
for card_id, count in DECK:
    rows.extend([str(card_id)] * count)
assert len(rows) == 60
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
path = f'output/deck_{ts}.csv'
with open(path, 'w') as f:
    f.write('\n'.join(rows))
print(path)
"`
Expected: `output/deck_YYYYMMDD_HHMMSS.csv` が生成され、パスが標準出力に表示される（Kaggleへのアップロードはユーザーが手動で実施）

- [ ] **Step 3: 実装サマリーを作成する**

```markdown
# 実装サマリー：グリムスナールexデッキ フェーズB（座組整理・キチキギスex採用）

**実装日：** 2026-07-03
**関連設計書：** `docs/superpowers/specs/2026-07-03-grimmsnarl-deck-revision-phase-b-design.md`
**関連調査：** `docs/reviews/20260703-grimmsnarl-switch-scoring-investigation.md`（フェーズA）

## 背景

フェーズA（`docs/implementations/20260703-grimmsnarl-switch-scoring-fix.md`）でSWITCH/TO_ACTIVEの
同点デフォルト選択バグを修正した際、「特性専用・バトル場を想定しないポケモンの座組が厚く、
バグの影響範囲を広げている」という仮説が挙がった。本フェーズはその仮説に基づき座組を整理した。

## 変更内容

### デッキ（`decks/grimmsnarl_20260701.py`）
- スボミー(235)/コダック(858)/シャリタツ(122)を削除
  - スボミー・コダックは実際のバトルログで低HPのまま前に出て誤選出された実害あり
  - シャリタツは特性発動に「バトル場にいること」が必須で、今回の方針（弱いポケモンを
    前に出さない）と根本的に矛盾するため削除
- キチキギスex(140)を2枚新規採用（210HP高耐久、悪エネルギー2+無色1で実際に攻撃可能な
  クルーエルアロー100ダメを持ち、特性「さかてにとる」もバトル場条件なしで安全に発動）
- イベルタル(689)を1→2枚に増量

### エージェントロジック（`src/grimmsnarl_agent/main.py`）
- 削除カード（Budew/Tatsugiri/Psyduck）の定数と`SUPPORT_ONLY_IDS`からの参照を削除
- `_score_attach`：グリムスナールexの攻撃分（2エネ）確保後、余剰の基本エネルギーを
  キチキギスexにも配分できるよう追加
- `_score_attack`：`Cruel_Arrow_ID`を`Shadow_Bullet_ID`と同じパターンで
  `_build_card_table()`から取得し、相手フィールド（バトル場+ベンチ）に確定KO対象が
  いれば優先するスコアリングを追加
- `ABILITY`：キチキギスexの特性「さかてにとる」をマシマシラと同格の優先度にし、
  非確定KOの攻撃より優先して毎ターン使用するようにした
- SWITCH/TO_ACTIVEのスコアリングは変更不要（キチキギスexは`SUPPORT_ONLY_IDS`に
  含めないため、既存のHP基準デフォルト式がそのまま適用され、210HPの高さから
  グリムスナールex不在時の次善アタッカーとして自然に優先選出される）

## テスト結果

- `tests/test_grimmsnarl_deck.py`：新構成向けテスト追加、全件PASS
- `tests/test_grimmsnarl_agent.py`：キチキギスexのエネルギー配分・攻撃スコアリング・
  特性優先度のテストを追加。削除カード参照（`gm.Budew`）は`gm.Shaymin`に置換
- リポジトリ全体：`uv run pytest -q` で全件PASS（回帰なし）

## 未対応・次回持ち越し

- 新規採用したキチキギスex以外のトールボックスカード（Shaymin/Yveltal等）への
  専用スコアリングロジック追加は引き続き未着手
- 超高速デッキ（Mega Lucario ex、アラカザム）との相性問題は今回未対応
- 他デッキ（cinderace_starmie_20260630.py等）への同種SWITCH/TO_ACTIVEスコアリング
  改善の横展開は未着手
- Kaggle再提出後のLBスコア変化確認（本改修のスコープ外、ユーザーが手動で実施）
```

- [ ] **Step 4: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add docs/implementations/20260703-grimmsnarl-deck-revision-phase-b.md
git commit -m "$(cat <<'EOF'
docs: グリムスナールexデッキ フェーズBの実装サマリーを追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
