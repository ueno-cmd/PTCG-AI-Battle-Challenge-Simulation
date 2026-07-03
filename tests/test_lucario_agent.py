# tests/test_lucario_agent.py
import pytest
from dataclasses import dataclass
from cg.api import CardType, EnergyType
import lucario_agent.main as lm


@dataclass
class MockCardData:
    """テスト用 CardData 代替クラス（cg.api.CardData と同一フィールドのみ定義）"""
    cardId:     int
    name:       str               = ""
    megaEx:     bool              = False
    ex:         bool              = False
    stage2:     bool              = False
    stage1:     bool              = False
    cardType:   CardType          = CardType.POKEMON
    weakness:   EnergyType | None = None
    resistance: EnergyType | None = None


def _card(card_id: int, **kwargs) -> MockCardData:
    return MockCardData(cardId=card_id, **kwargs)


@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    """全テストで card_table をモックに差し替える"""
    table = {
        lm.Lunatone:              _card(lm.Lunatone),
        lm.Solrock:               _card(lm.Solrock),
        lm.Riolu:                 _card(lm.Riolu),
        lm.Mega_Lucario_ex:       _card(lm.Mega_Lucario_ex, megaEx=True),
        144:  _card(144,  ex=True),   # Squawkabilly ex
        322:  _card(322),             # Noctowl
        323:  _card(323),             # Fan Rotom
        337:  _card(337,  ex=True),   # Archaludon ex
        112:  _card(112),             # Munkidori
        1267: _card(1267),            # Lumiose City
        12:   _card(12,   cardType=CardType.SPECIAL_ENERGY),  # Legacy Energy
        1172: _card(1172, cardType=CardType.TOOL),            # Lillie's Pearl
        lm.Premium_Power_Pro:    _card(lm.Premium_Power_Pro,    cardType=CardType.ITEM),
        lm.Boss_Orders:          _card(lm.Boss_Orders,          cardType=CardType.SUPPORTER),
        lm.Lillie_Determination: _card(lm.Lillie_Determination, cardType=CardType.SUPPORTER),
        lm.Gravity_Mountain:     _card(lm.Gravity_Mountain,     cardType=CardType.STADIUM),
        lm.Hero_Cape:            _card(lm.Hero_Cape,            cardType=CardType.TOOL),
        lm.Fighting_Gong:        _card(lm.Fighting_Gong,        cardType=CardType.ITEM),
        lm.Poke_Pad:             _card(lm.Poke_Pad,             cardType=CardType.ITEM),
        lm.Ultra_Ball:            _card(lm.Ultra_Ball,            cardType=CardType.ITEM),
        lm.Pokegear:              _card(lm.Pokegear,              cardType=CardType.ITEM),
        lm.Night_Stretcher:       _card(lm.Night_Stretcher,       cardType=CardType.ITEM),
        lm.Judge:                 _card(lm.Judge,                 cardType=CardType.SUPPORTER),
        lm.Hilda:                 _card(lm.Hilda,                 cardType=CardType.SUPPORTER),
        lm.Wally_Compassion:      _card(lm.Wally_Compassion,      cardType=CardType.SUPPORTER),
        lm.Ciphermaniac_Codebreaking: _card(lm.Ciphermaniac_Codebreaking, cardType=CardType.SUPPORTER),
    }
    monkeypatch.setattr(lm, "card_table", table)
    return table


# ==================== Task 2: prize_count ====================
from cg.api import Card
from tests.conftest import make_pokemon


class TestPrizeCount:
    def test_regular_pokemon_yields_1(self):
        p = make_pokemon(id=lm.Riolu)
        assert lm.prize_count(p) == 1

    def test_ex_pokemon_yields_2(self):
        p = make_pokemon(id=337)  # Archaludon ex
        assert lm.prize_count(p) == 2

    def test_mega_ex_yields_3(self):
        p = make_pokemon(id=lm.Mega_Lucario_ex)
        assert lm.prize_count(p) == 3

    def test_legacy_energy_reduces_count_by_1(self):
        """Legacy Energy(id=12) を装備した ex は 2 - 1 = 1 プライズ"""
        p = make_pokemon(id=337)
        legacy = Card(id=12, serial=12, playerIndex=0)
        object.__setattr__(p, "energyCards", [legacy])
        assert lm.prize_count(p) == 1

    def test_minimum_prize_is_0(self):
        """複数の減算があっても 0 を下限とする"""
        p = make_pokemon(id=lm.Riolu)  # 通常 → 1
        legacy = Card(id=12, serial=12, playerIndex=0)
        object.__setattr__(p, "energyCards", [legacy, legacy])
        assert lm.prize_count(p) == 0


# ==================== Task 3: pokemon_score + energy_score ====================
class TestPokemonScore:
    def test_ex_pokemon_scores_higher_than_regular(self):
        ex  = make_pokemon(id=337, hp=200)       # ex → 2 prize
        reg = make_pokemon(id=lm.Riolu, hp=200)  # regular → 1 prize
        assert lm.pokemon_score(ex) > lm.pokemon_score(reg)

    def test_more_energies_yields_higher_score(self):
        p_no  = make_pokemon(id=lm.Riolu, hp=100, energies=[])
        p_two = make_pokemon(id=lm.Riolu, hp=100, energies=[6, 6])
        assert lm.pokemon_score(p_two) > lm.pokemon_score(p_no)

    def test_special_ids_are_penalised(self, mock_card_table):
        """特殊ID(144) は非ペナルティの同条件 ex より正確に 200 低スコア"""
        mock_card_table[999] = MockCardData(cardId=999, ex=True)  # ペナルティなし ex
        normal_ex = make_pokemon(id=999, hp=70)
        squawk    = make_pokemon(id=144, hp=70)
        diff = lm.pokemon_score(normal_ex) - lm.pokemon_score(squawk)
        assert diff == 200

    def test_munkidori_gets_bonus_with_energy(self):
        """Munkidori(112) はエネルギーが 1 枚以上で +300"""
        no_e   = make_pokemon(id=112, hp=90, energies=[])
        with_e = make_pokemon(id=112, hp=90, energies=[6])
        assert lm.pokemon_score(with_e) > lm.pokemon_score(no_e)

    def test_stage1_gets_bonus(self, mock_card_table):
        """stage1 ポケモンは同 HP の basic より高スコア"""
        mock_card_table[900] = MockCardData(cardId=900, stage1=True)
        p_stage1 = make_pokemon(id=900, hp=130)
        p_basic  = make_pokemon(id=lm.Riolu, hp=130)
        assert lm.pokemon_score(p_stage1) > lm.pokemon_score(p_basic)


class TestEnergyScore:
    def test_active_slot_gets_bonus(self):
        p      = make_pokemon(id=lm.Riolu, energies=[])
        active = lm.energy_score(p, True,  False)
        bench  = lm.energy_score(p, False, False)
        assert active > bench

    def test_riolu_low_energy_gets_bonus(self):
        """Riolu にエネルギーが足りない場合はスコアが高い"""
        no_e  = make_pokemon(id=lm.Riolu, energies=[])
        two_e = make_pokemon(id=lm.Riolu, energies=[6, 6])
        assert lm.energy_score(no_e, False, False) > lm.energy_score(two_e, False, False)

    def test_lunatone_deprioritised(self):
        p_luna  = make_pokemon(id=lm.Lunatone, energies=[])
        p_riolu = make_pokemon(id=lm.Riolu,    energies=[])
        assert lm.energy_score(p_riolu, False, False) > lm.energy_score(p_luna, False, False)

    def test_solrock_deprioritised_after_one_energy(self):
        p_no  = make_pokemon(id=lm.Solrock, energies=[])
        p_one = make_pokemon(id=lm.Solrock, energies=[6])
        assert lm.energy_score(p_no, False, False) > lm.energy_score(p_one, False, False)

    def test_attacker1_flag_lowers_score(self):
        """既に attacker1 が準備できている場合、Riolu へのエネルギー優先度を下げる"""
        p            = make_pokemon(id=lm.Riolu, energies=[])
        without_flag = lm.energy_score(p, False, False)
        with_flag    = lm.energy_score(p, False, True)
        assert without_flag > with_flag


# ==================== Task 4: フィールド状態ヘルパー ====================
from unittest.mock import MagicMock
from cg.api import Card
from tests.conftest import make_player_state


class TestCollectFieldState:
    def test_counts_active_and_bench(self):
        riolu   = make_pokemon(id=lm.Riolu)
        solrock = make_pokemon(id=lm.Solrock)
        ps = make_player_state(active_pokemon=riolu, bench=[solrock])
        fc, hc, dc, a1 = lm._collect_field_state(ps)
        assert fc[lm.Riolu]   == 1
        assert fc[lm.Solrock] == 1

    def test_attacker1_true_when_lucario_has_2_energy(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[6, 6])
        ps = make_player_state(active_pokemon=lucario)
        _, _, _, a1 = lm._collect_field_state(ps)
        assert a1 is True

    def test_no_attacker1_when_energy_insufficient(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[6])  # 1 枚のみ
        ps = make_player_state(active_pokemon=lucario)
        _, _, _, a1 = lm._collect_field_state(ps)
        assert a1 is False


class TestGetStadiumId:
    def test_returns_0_when_no_stadium(self):
        state = MagicMock()
        state.stadium = []
        assert lm._get_stadium_id(state) == 0

    def test_returns_stadium_card_id(self):
        state = MagicMock()
        state.stadium = [Card(id=lm.Gravity_Mountain, serial=1, playerIndex=0)]
        assert lm._get_stadium_id(state) == lm.Gravity_Mountain


# ==================== Task 5: calc_attack_plan ====================
from collections import defaultdict
from cg.api import Option, OptionType
from tests.conftest import make_player_state


def _make_state(turn=3, energy_attached=False, first_player=0):
    state = MagicMock()
    state.turn           = turn
    state.energyAttached = energy_attached
    state.firstPlayer    = first_player
    return state


class TestCalcAttackPlan:
    def test_no_attackers_returns_default_plan(self):
        """攻撃可能なポケモンがいない場合はデフォルト AttackPlan(-1) を返す"""
        solrock = make_pokemon(id=lm.Solrock, hp=80, energies=[])
        my_ps = make_player_state(active_pokemon=solrock)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=60), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=False, my_prize=6,
        )
        assert result.attacker == -1
        assert result.target   == -1

    def test_lucario_plans_mega_brave_when_it_can_ko(self):
        """Mega Lucario ex に 2 エネ・相手 HP200 → Mega Brave(270) でのみ KO 可 → attack_index=1"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=200), prize_count=6)
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
        )
        assert result.attacker     == 0
        assert result.attack_index == 1

    def test_win_condition_is_detected(self):
        """KO で相手の残りプライズが 0 になる局面を選択する"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=4)
        # Archaludon ex(337): ex → 2 prize、残りプライズも 2 → KO で勝ち
        op_ps = make_player_state(active_pokemon=make_pokemon(id=337, hp=60), prize_count=2)
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=4,
        )
        assert result.attacker == 0

    def test_fighting_weakness_doubles_damage(self):
        """格闘弱点の相手は実質ダメージが 2 倍になり、HP200 も通常攻撃(130→260)で KO 可能"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=200), prize_count=6)
        # Riolu の weakness を FIGHTING に設定
        lm.card_table[lm.Riolu] = MockCardData(cardId=lm.Riolu, weakness=EnergyType.FIGHTING)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
        )
        assert result.attacker     == 0
        assert result.attack_index == 0


# ==================== Task 6: agent() 統合テスト ====================
from unittest.mock import patch
from tests.conftest import make_main_obs


class TestAgent:
    def test_returns_deck_when_select_is_none(self):
        """select が None のとき my_deck を返す"""
        obs_dict = {"select": None, "logs": [], "current": None, "search_begin_input": None}
        with patch.object(lm, "my_deck", [1] * 60):
            result = lm.agent(obs_dict)
        assert result == [1] * 60

    def test_returns_valid_indices(self):
        """返り値が option の範囲内で重複なし"""
        options = [
            Option(type=OptionType.ATTACK, attackId=100),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(options=options)
        result = lm.agent(obs_dict)
        assert all(0 <= i < len(options) for i in result)
        assert len(result) == len(set(result))

    def test_prefers_attack_over_end(self):
        """ATTACK オプションは END より優先される"""
        options = [
            Option(type=OptionType.END),
            Option(type=OptionType.ATTACK, attackId=100),
        ]
        obs_dict = make_main_obs(options=options)
        result = lm.agent(obs_dict)
        assert options[result[0]].type == OptionType.ATTACK

    def test_resets_plan_on_new_turn(self):
        """ターンが変わったら plan と ability_used がリセットされる"""
        lm.pre_turn     = 5
        lm.plan         = lm.AttackPlan(attacker=1, target=1, attack_index=0)
        lm.ability_used = True
        obs_dict = make_main_obs(options=[Option(type=OptionType.END)], turn=6)
        lm.agent(obs_dict)
        assert lm.plan.attacker == -1
        assert lm.ability_used  is False


# ==================== Task 3: デッキアウト防止ゲート ====================
from unittest.mock import MagicMock as _MM


def _obs_with_hand(hand_cards, my_index=0, deck_count=50):
    obs = MagicMock()
    my_ps = make_player_state(hand=hand_cards, deck_count=deck_count)
    op_ps = make_player_state()
    players = [my_ps, op_ps] if my_index == 0 else [op_ps, my_ps]
    obs.current.players = players
    return obs, players[my_index]


class TestDeckSafetyGate:
    def test_lillie_determination_scores_normally_when_deck_healthy(self):
        card = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=20)
        o = Option(type=OptionType.PLAY, index=0)
        state = _make_state()
        state.supporterPlayed = False
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=state, my_state=my_state,
            hand_counts=defaultdict(int), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 3100

    def test_lillie_determination_suppressed_when_deck_low(self):
        card = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=10)
        o = Option(type=OptionType.PLAY, index=0)
        state = _make_state()
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=state, my_state=my_state,
            hand_counts=defaultdict(int), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1

    def test_threshold_boundary_is_inclusive(self):
        """山札残数がちょうどしきい値なら通常スコア"""
        card = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=lm.DECK_SAFETY_THRESHOLD)
        o = Option(type=OptionType.PLAY, index=0)
        state = _make_state()
        state.supporterPlayed = False
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=state, my_state=my_state,
            hand_counts=defaultdict(int), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 3100


# ==================== Task 4: ルナサイクル ====================
class TestDiscardContext:
    def _obs(self, hand_card):
        obs = MagicMock()
        my_ps = make_player_state(hand=[hand_card])
        obs.current.players = [my_ps, make_player_state()]
        return obs

    def test_prefers_spare_fighting_energy(self):
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
        assert score == 50

    def test_protects_key_pokemon(self):
        riolu = Card(id=lm.Riolu, serial=1, playerIndex=0)
        obs = self._obs(riolu)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == -100

    def test_protects_key_supporters(self):
        boss = Card(id=lm.Boss_Orders, serial=1, playerIndex=0)
        obs = self._obs(boss)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == -50

    def test_default_trainer_is_low_priority_but_positive(self):
        stretcher = Card(id=1097, serial=1, playerIndex=0)  # Night Stretcher（まだ定数化前）
        obs = self._obs(stretcher)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == 10


class TestLunaCycleAbilityScore:
    def _obs_with_active_lunatone(self):
        lunatone = Card(id=lm.Lunatone, serial=1, playerIndex=0)
        obs = MagicMock()
        obs.current.players = [make_player_state(), make_player_state()]
        return obs, lunatone

    def test_scores_high_when_deck_healthy(self, mock_card_table):
        obs, lunatone = self._obs_with_active_lunatone()
        obs.current.players[0].active = [lunatone]
        my_state = make_player_state(deck_count=20)
        score = lm._score_option(
            obs, Option(type=OptionType.ABILITY, area=lm.AreaType.ACTIVE, index=0),
            context=lm.SelectContext.MAIN, my_index=0, state=_make_state(),
            my_state=my_state, op_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), can_attack=False,
            stadium_id=0, ability_used_flag=False,
        )
        assert score == 8500

    def test_suppressed_when_deck_low(self, mock_card_table):
        obs, lunatone = self._obs_with_active_lunatone()
        obs.current.players[0].active = [lunatone]
        my_state = make_player_state(deck_count=10)
        score = lm._score_option(
            obs, Option(type=OptionType.ABILITY, area=lm.AreaType.ACTIVE, index=0),
            context=lm.SelectContext.MAIN, my_index=0, state=_make_state(),
            my_state=my_state, op_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), can_attack=False,
            stadium_id=0, ability_used_flag=False,
        )
        assert score == -1


# ==================== Task 5: 新規カードのスコアリング ====================
class TestNewCardScoring:
    def _score(self, card_id, my_state=None, hand_counts=None, field_counts=None,
               attacker1=False, can_attack=False, state=None):
        obs = MagicMock()
        my_ps = my_state or make_player_state(hand=[Card(id=card_id, serial=1, playerIndex=0)])
        obs.current.players = [my_ps, make_player_state()]
        return lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=can_attack,
            state=state or _make_state(), my_state=my_ps,
            hand_counts=hand_counts or defaultdict(int),
            field_counts=field_counts or defaultdict(int), stadium_id=0,
        )

    def test_ultra_ball_prioritised_when_riolu_not_found(self):
        score = self._score(lm.Ultra_Ball, hand_counts=defaultdict(int))
        assert score == 6000

    def test_ultra_ball_still_positive_when_riolu_present(self):
        fc = defaultdict(int, {lm.Riolu: 1})
        score = self._score(lm.Ultra_Ball, field_counts=fc)
        assert score == 5500

    def test_pokegear_flat_priority(self):
        assert self._score(lm.Pokegear) == 5200

    def test_night_stretcher_flat_priority(self):
        assert self._score(lm.Night_Stretcher) == 4800

    def test_hilda_flat_priority(self):
        assert self._score(lm.Hilda) == 5300

    def test_ciphermaniac_codebreaking_flat_priority(self):
        assert self._score(lm.Ciphermaniac_Codebreaking) == 5100

    def test_judge_used_when_hand_is_dead(self):
        score = self._score(
            lm.Judge, hand_counts=defaultdict(int), attacker1=False,
        )
        assert score == 7000

    def test_judge_held_when_attacker_ready(self):
        my_ps = make_player_state(hand=[Card(id=lm.Judge, serial=1, playerIndex=0)])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        score = lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=my_ps,
            hand_counts=defaultdict(int, {lm.Basic_Fighting_Energy: 1}),
            field_counts=defaultdict(int), stadium_id=0,
        )
        assert score == -1

    def test_wally_compassion_used_when_lucario_damaged(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=200, max_hp=440)
        my_ps = make_player_state(
            active_pokemon=lucario,
            hand=[Card(id=lm.Wally_Compassion, serial=1, playerIndex=0)],
        )
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        score = lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=my_ps,
            hand_counts=defaultdict(int), field_counts=defaultdict(int), stadium_id=0,
        )
        assert score == 6800

    def test_wally_compassion_held_when_lucario_full_hp(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=440, max_hp=440)
        my_ps = make_player_state(
            active_pokemon=lucario,
            hand=[Card(id=lm.Wally_Compassion, serial=1, playerIndex=0)],
        )
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        score = lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=my_ps,
            hand_counts=defaultdict(int), field_counts=defaultdict(int), stadium_id=0,
        )
        assert score == -1
