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
    tera:       bool              = False
    cardType:   CardType          = CardType.POKEMON
    weakness:   EnergyType | None = None
    resistance: EnergyType | None = None
    retreatCost: int              = 0


def _card(card_id: int, **kwargs) -> MockCardData:
    return MockCardData(cardId=card_id, **kwargs)


@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    """全テストで card_table をモックに差し替える"""
    table = {
        lm.Lunatone:              _card(lm.Lunatone),
        lm.Solrock:               _card(lm.Solrock),
        lm.Riolu:                 _card(lm.Riolu, retreatCost=2),
        lm.Mega_Lucario_ex:       _card(lm.Mega_Lucario_ex, megaEx=True, retreatCost=2),
        lm.Ogerpon_ex:            _card(lm.Ogerpon_ex, ex=True, tera=True),  # Cornerstone Mask Ogerpon ex
        144:  _card(144,  ex=True),   # Squawkabilly ex
        322:  _card(322),             # Noctowl
        323:  _card(323),             # Fan Rotom
        337:  _card(337,  ex=True),   # Archaludon ex
        112:  _card(112),             # Munkidori
        1267: _card(1267),            # Lumiose City
        12:   _card(12,   cardType=CardType.SPECIAL_ENERGY),  # Legacy Energy
        lm.Rock_Fighting_Energy: _card(lm.Rock_Fighting_Energy, cardType=CardType.SPECIAL_ENERGY),  # ロック闘エネルギー
        1172: _card(1172, cardType=CardType.TOOL),            # Lillie's Pearl
        lm.Premium_Power_Pro:    _card(lm.Premium_Power_Pro,    cardType=CardType.ITEM),
        lm.Boss_Orders:          _card(lm.Boss_Orders,          cardType=CardType.SUPPORTER),
        lm.Lillie_Determination: _card(lm.Lillie_Determination, cardType=CardType.SUPPORTER),
        lm.Gravity_Mountain:     _card(lm.Gravity_Mountain,     cardType=CardType.STADIUM),
        lm.Maximum_Belt:         _card(lm.Maximum_Belt,         cardType=CardType.TOOL),
        lm.Fighting_Gong:        _card(lm.Fighting_Gong,        cardType=CardType.ITEM),
        lm.Poke_Pad:             _card(lm.Poke_Pad,             cardType=CardType.ITEM),
        lm.Ultra_Ball:            _card(lm.Ultra_Ball,            cardType=CardType.ITEM),
        lm.Pokegear:              _card(lm.Pokegear,              cardType=CardType.ITEM),
        lm.Night_Stretcher:       _card(lm.Night_Stretcher,       cardType=CardType.ITEM),
        lm.Judge:                 _card(lm.Judge,                 cardType=CardType.SUPPORTER),
        lm.Hilda:                 _card(lm.Hilda,                 cardType=CardType.SUPPORTER),
        lm.Wally_Compassion:      _card(lm.Wally_Compassion,      cardType=CardType.SUPPORTER),
        lm.Ciphermaniac_Codebreaking: _card(lm.Ciphermaniac_Codebreaking, cardType=CardType.SUPPORTER),
        lm.Switch:                _card(lm.Switch,                cardType=CardType.ITEM),
        lm.Air_Balloon:           _card(lm.Air_Balloon,           cardType=CardType.TOOL),
    }
    monkeypatch.setattr(lm, "card_table", table)
    return table


# ==================== Task 2: prize_count ====================
from cg.api import Card
from tests.conftest import make_pokemon


class TestPrizeCount:
    def test_regular_pokemon_yields_1(self):
        p = make_pokemon(id=lm.Riolu)
        assert lm.prize_count(p, lm.card_table) == 1

    def test_ex_pokemon_yields_2(self):
        p = make_pokemon(id=337)  # Archaludon ex
        assert lm.prize_count(p, lm.card_table) == 2

    def test_mega_ex_yields_3(self):
        p = make_pokemon(id=lm.Mega_Lucario_ex)
        assert lm.prize_count(p, lm.card_table) == 3

    def test_legacy_energy_reduces_count_by_1(self):
        """Legacy Energy(id=12) を装備した ex は 2 - 1 = 1 プライズ"""
        p = make_pokemon(id=337)
        legacy = Card(id=12, serial=12, playerIndex=0)
        object.__setattr__(p, "energyCards", [legacy])
        assert lm.prize_count(p, lm.card_table) == 1

    def test_minimum_prize_is_0(self):
        """複数の減算があっても 0 を下限とする"""
        p = make_pokemon(id=lm.Riolu)  # 通常 → 1
        legacy = Card(id=12, serial=12, playerIndex=0)
        object.__setattr__(p, "energyCards", [legacy, legacy])
        assert lm.prize_count(p, lm.card_table) == 0


# ==================== Task 3: pokemon_score + energy_score ====================
class TestPokemonScore:
    def test_ex_pokemon_scores_higher_than_regular(self):
        ex  = make_pokemon(id=337, hp=200)       # ex → 2 prize
        reg = make_pokemon(id=lm.Riolu, hp=200)  # regular → 1 prize
        assert lm.pokemon_score(ex, lm.card_table) > lm.pokemon_score(reg, lm.card_table)

    def test_more_energies_yields_higher_score(self):
        p_no  = make_pokemon(id=lm.Riolu, hp=100, energies=[])
        p_two = make_pokemon(id=lm.Riolu, hp=100, energies=[6, 6])
        assert lm.pokemon_score(p_two, lm.card_table) > lm.pokemon_score(p_no, lm.card_table)

    def test_special_ids_are_penalised(self, mock_card_table):
        """特殊ID(144) は非ペナルティの同条件 ex より正確に 200 低スコア"""
        mock_card_table[999] = MockCardData(cardId=999, ex=True)  # ペナルティなし ex
        normal_ex = make_pokemon(id=999, hp=70)
        squawk    = make_pokemon(id=144, hp=70)
        diff = lm.pokemon_score(normal_ex, lm.card_table) - lm.pokemon_score(squawk, lm.card_table)
        assert diff == 200

    def test_munkidori_gets_bonus_with_energy(self):
        """Munkidori(112) はエネルギーが 1 枚以上で +300"""
        no_e   = make_pokemon(id=112, hp=90, energies=[])
        with_e = make_pokemon(id=112, hp=90, energies=[6])
        assert lm.pokemon_score(with_e, lm.card_table) > lm.pokemon_score(no_e, lm.card_table)

    def test_stage1_gets_bonus(self, mock_card_table):
        """stage1 ポケモンは同 HP の basic より高スコア"""
        mock_card_table[900] = MockCardData(cardId=900, stage1=True)
        p_stage1 = make_pokemon(id=900, hp=130)
        p_basic  = make_pokemon(id=lm.Riolu, hp=130)
        assert lm.pokemon_score(p_stage1, lm.card_table) > lm.pokemon_score(p_basic, lm.card_table)


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


class TestEnergyScoreOgerponEx:
    def test_charging_gets_bonus_below_3_energy(self):
        """3エネ未満（充填中）はボーナスが付く"""
        charging = make_pokemon(id=lm.Ogerpon_ex, energies=[6, 6])
        full     = make_pokemon(id=lm.Ogerpon_ex, energies=[6, 6, 6])
        assert lm.energy_score(charging, False, False) > lm.energy_score(full, False, False)

    def test_attacker1_ready_gives_extra_bonus(self):
        """ルカリオ系統(attacker1)が準備済みなら、余剰エネルギーをオーガポンexへ回すため加点される"""
        p = make_pokemon(id=lm.Ogerpon_ex, energies=[6])
        without_flag = lm.energy_score(p, False, False)
        with_flag    = lm.energy_score(p, False, True)
        assert with_flag > without_flag

    def test_op_active_nullifies_ex_gives_priority_over_mega_lucario_ex(self):
        """相手アクティブがex無効化持ちなら、オーガポンexがメガルカリオexより優先される"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, energies=[6])
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[])
        ogerpon_score = lm.energy_score(ogerpon, False, False, op_active_nullifies_ex=True)
        lucario_score = lm.energy_score(lucario, False, True, op_active_nullifies_ex=True)
        assert ogerpon_score > lucario_score

    def test_op_active_nullifies_ex_bonus_only_applies_when_true(self):
        p = make_pokemon(id=lm.Ogerpon_ex, energies=[6])
        without_flag = lm.energy_score(p, False, False, op_active_nullifies_ex=False)
        with_flag    = lm.energy_score(p, False, False, op_active_nullifies_ex=True)
        assert with_flag > without_flag


class TestEnergyScoreNullifierPenaltyForLucarioLine:
    """energy_scoreのMega_Lucario_ex/Riolu分岐に、相手がex無効化持ちのときの減点があることを確認するテスト
    （Ogerpon_exには+150ボーナスがあるのに対応する減点が無かった実バグの回帰テスト）"""

    def test_mega_lucario_ex_penalised_when_op_active_nullifies_ex(self):
        p = make_pokemon(id=lm.Mega_Lucario_ex, energies=[])
        without_flag = lm.energy_score(p, False, False, op_active_nullifies_ex=False)
        with_flag    = lm.energy_score(p, False, False, op_active_nullifies_ex=True)
        assert with_flag < without_flag

    def test_riolu_penalised_when_op_active_nullifies_ex(self):
        p = make_pokemon(id=lm.Riolu, energies=[])
        without_flag = lm.energy_score(p, False, False, op_active_nullifies_ex=False)
        with_flag    = lm.energy_score(p, False, False, op_active_nullifies_ex=True)
        assert with_flag < without_flag

    def test_solrock_beats_mega_lucario_ex_when_op_active_nullifies_ex(self):
        """相手がex無効化持ちのとき、ソルロック(ex無効化されない非exアタッカー)が
        ベンチのメガルカリオex(ex無効化される)より優先される（実ログ86898758で
        確認された実バグの回帰テスト：メガルカリオexへエネルギーが偏り続けていた）"""
        solrock = make_pokemon(id=lm.Solrock, energies=[])
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[])
        solrock_score = lm.energy_score(solrock, False, False, op_active_nullifies_ex=True)
        lucario_score = lm.energy_score(lucario, False, False, op_active_nullifies_ex=True)
        assert solrock_score > lucario_score


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


class TestOpActiveNullifiesEx:
    def test_true_when_op_active_is_crustle(self):
        ps = make_player_state(active_pokemon=make_pokemon(id=lm.Crustle))
        assert lm._op_active_nullifies_ex(ps) is True

    def test_true_when_op_active_is_sylveon(self):
        ps = make_player_state(active_pokemon=make_pokemon(id=lm.Sylveon))
        assert lm._op_active_nullifies_ex(ps) is True

    def test_false_when_op_active_is_regular_pokemon(self):
        ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu))
        assert lm._op_active_nullifies_ex(ps) is False

    def test_false_when_no_active(self):
        ps = make_player_state()
        assert lm._op_active_nullifies_ex(ps) is False


class TestTeraStadiumCostBonus:
    def test_no_bonus_without_nighttime_mine(self):
        assert lm._tera_stadium_cost_bonus(lm.Ogerpon_ex, stadium_id=0, card_table=lm.card_table) == 0

    def test_no_bonus_for_non_tera_pokemon_under_nighttime_mine(self):
        """メガルカリオexはテラスタルではないためコスト変化なし"""
        assert lm._tera_stadium_cost_bonus(lm.Mega_Lucario_ex, stadium_id=lm.Nighttime_Mine, card_table=lm.card_table) == 0

    def test_bonus_for_tera_pokemon_under_nighttime_mine(self):
        assert lm._tera_stadium_cost_bonus(lm.Ogerpon_ex, stadium_id=lm.Nighttime_Mine, card_table=lm.card_table) == 1


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


class TestCalcAttackDamage:
    """弱点/抵抗力/Crustle無効化を1箇所に集約した_calc_attack_damageのテスト"""

    def test_no_modifier_returns_base_damage(self):
        defender = MockCardData(cardId=999)
        assert lm._calc_attack_damage(lm.Mega_Lucario_ex, 130, 999, defender, card_table=lm.card_table) == 130

    def test_weakness_doubles_damage(self):
        defender = MockCardData(cardId=999, weakness=EnergyType.FIGHTING)
        assert lm._calc_attack_damage(lm.Mega_Lucario_ex, 130, 999, defender, card_table=lm.card_table) == 260

    def test_resistance_reduces_damage_by_30(self):
        defender = MockCardData(cardId=999, resistance=EnergyType.FIGHTING)
        assert lm._calc_attack_damage(lm.Mega_Lucario_ex, 130, 999, defender, card_table=lm.card_table) == 100

    def test_ogerpon_ex_ignores_weakness(self):
        """ぶちやぶるは弱点を計算しない"""
        defender = MockCardData(cardId=999, weakness=EnergyType.FIGHTING)
        assert lm._calc_attack_damage(lm.Ogerpon_ex, 140, 999, defender, card_table=lm.card_table) == 140

    def test_crustle_nullifies_mega_lucario_ex_damage(self):
        defender = MockCardData(cardId=lm.Crustle)
        assert lm._calc_attack_damage(lm.Mega_Lucario_ex, 270, lm.Crustle, defender, card_table=lm.card_table) == 0

    def test_crustle_does_not_nullify_ogerpon_ex_damage(self):
        """ぶちやぶるは相手にかかっている効果を計算しないためCrustleの特性を貫通する"""
        defender = MockCardData(cardId=lm.Crustle)
        assert lm._calc_attack_damage(lm.Ogerpon_ex, 140, lm.Crustle, defender, card_table=lm.card_table) == 140

    def test_crustle_does_not_nullify_non_ex_attacker_damage(self):
        """Crustleの特性はexポケモンの技のみを無効化する（Solrock等の非exは通常通り）"""
        defender = MockCardData(cardId=lm.Crustle)
        assert lm._calc_attack_damage(lm.Solrock, 70, lm.Crustle, defender, card_table=lm.card_table) == 70

    def test_sylveon_nullifies_ex_attacker_damage(self):
        """Sylveon(330)もCrustleと同じ効果文の特性を持つため無効化対象に含める"""
        defender = MockCardData(cardId=lm.Sylveon)
        assert lm._calc_attack_damage(lm.Mega_Lucario_ex, 270, lm.Sylveon, defender, card_table=lm.card_table) == 0

    def test_ogerpon_ex_bypasses_sylveon_ability(self):
        """ぶちやぶるはSylveonの特性も貫通する"""
        defender = MockCardData(cardId=lm.Sylveon)
        assert lm._calc_attack_damage(lm.Ogerpon_ex, 140, lm.Sylveon, defender, card_table=lm.card_table) == 140

    def test_generalizes_to_any_ex_attacker_not_just_mega_lucario(self):
        """攻撃側がexなら誰でも無効化される（Mega_Lucario_ex固定ではなくCardData.ex/megaExで判定）"""
        defender = MockCardData(cardId=lm.Crustle)
        assert lm._calc_attack_damage(337, 200, lm.Crustle, defender, card_table=lm.card_table) == 0  # Archaludon ex（ex=True）

    def test_maximum_belt_adds_50_against_ex_defender(self):
        """Maximum Belt装着で相手exへの技ダメージが+50される"""
        defender = MockCardData(cardId=999, ex=True)
        belt = Card(id=lm.Maximum_Belt, serial=1, playerIndex=0)
        assert lm._calc_attack_damage(
            lm.Mega_Lucario_ex, 270, 999, defender, card_table=lm.card_table,
            attacker_tools=[belt],
        ) == 320

    def test_maximum_belt_no_bonus_against_non_ex_defender(self):
        """相手が非exならMaximum Beltの+50は適用されない"""
        defender = MockCardData(cardId=999, ex=False)
        belt = Card(id=lm.Maximum_Belt, serial=1, playerIndex=0)
        assert lm._calc_attack_damage(
            lm.Mega_Lucario_ex, 270, 999, defender, card_table=lm.card_table,
            attacker_tools=[belt],
        ) == 270

    def test_maximum_belt_applied_before_weakness_doubling(self):
        """カード効果文「before applying Weakness and Resistance」の順序確認：
        (130+50)*2=360になる（130*2+50=310ではない）"""
        defender = MockCardData(cardId=999, ex=True, weakness=EnergyType.FIGHTING)
        belt = Card(id=lm.Maximum_Belt, serial=1, playerIndex=0)
        assert lm._calc_attack_damage(
            lm.Mega_Lucario_ex, 130, 999, defender, card_table=lm.card_table,
            attacker_tools=[belt],
        ) == 360

    def test_without_maximum_belt_no_bonus(self):
        """attacker_tools省略時（既存呼び出し）は従来通りボーナス無し"""
        defender = MockCardData(cardId=999, ex=True)
        assert lm._calc_attack_damage(
            lm.Mega_Lucario_ex, 270, 999, defender, card_table=lm.card_table,
        ) == 270


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
            card_table=lm.card_table,
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
            card_table=lm.card_table,
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
            card_table=lm.card_table,
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
            card_table=lm.card_table,
        )
        assert result.attacker     == 0
        assert result.attack_index == 0

    def test_mega_brave_held_when_normal_attack_already_ko(self):
        """通常攻撃(130)で確定KOできる相手には、メガブレイブを温存し通常攻撃を選ぶ"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.attack_index == 0

    def test_mega_brave_explores_when_rng_below_epsilon_and_no_ko_either_way(self):
        """どちらの技でも確定KOできない場面で、rngがEPSILON未満ならメガブレイブを選ぶ"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=1000), prize_count=6)
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
            card_table=lm.card_table,
            rng=_StubRng(0.1),
        )
        assert result.attack_index == 1

    def test_mega_brave_holds_when_rng_above_epsilon_and_no_ko_either_way(self):
        """どちらの技でも確定KOできない場面で、rngがEPSILON以上なら通常攻撃を選ぶ"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=1000), prize_count=6)
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
            card_table=lm.card_table,
            rng=_StubRng(0.9),
        )
        assert result.attack_index == 0

    def test_ogerpon_ex_selected_as_attacker_with_3_energy(self):
        """オーガポンexが3エネルギー確保時にアタッカー候補として選ばれ、140ダメ固定になる"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.attacker  == 0
        assert result.remain_hp == 100 - 140

    def test_ogerpon_ex_ignores_weakness(self):
        """ぶちやぶるは弱点を計算しないため、相手が格闘弱点でも140ダメ固定（280にならない）"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=300), prize_count=6)
        lm.card_table[lm.Riolu] = MockCardData(cardId=lm.Riolu, weakness=EnergyType.FIGHTING)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.remain_hp == 300 - 140

    def test_ogerpon_ex_not_selected_with_insufficient_energy(self):
        """2エネルギーでは「ぶちやぶる」(3エネ必要)を使えずアタッカー候補にならない"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.attacker == -1

    def test_ogerpon_ex_selected_when_only_rock_energy_in_hand(self):
        """手札に基本闘エネルギーが0枚でも、ロック闘エネルギーがあれば
        「あと1エネルギーで技が届く」候補として正しく評価される（潜在バグ修正）"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int, {lm.Rock_Fighting_Energy: 1}), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.attacker == 0

    def test_ogerpon_ex_requires_4_energy_under_nighttime_mine(self):
        """Nighttime Mine下ではオーガポンexの技コストが3→4になり、3エネルギーでは発動しない"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
            stadium_id=lm.Nighttime_Mine,
        )
        assert result.attacker == -1

    def test_ogerpon_ex_attacks_normally_without_nighttime_mine(self):
        """Nighttime Mine以外では従来通り3エネルギーで攻撃候補になる（回帰確認）"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
            stadium_id=lm.Gravity_Mountain,
        )
        assert result.attacker == 0

    def test_mega_lucario_ex_unaffected_by_nighttime_mine(self):
        """メガルカリオexは非テラスタルのためNighttime Mine下でもコスト変化なし（回帰確認）"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
            stadium_id=lm.Nighttime_Mine,
        )
        assert result.attacker     == 0
        assert result.attack_index == 0

    def test_ogerpon_ex_pierces_wall_with_4_energy_under_nighttime_mine(self):
        """テラスタル×スタジアム×ex無効化の複合ケース：Nighttime Mine下ではオーガポンexは
        4エネルギー必要になるが、無効化貫通（ぶちやぶる）は引き続き機能し140ダメージが通る"""
        lm.card_table[lm.Crustle] = MockCardData(cardId=lm.Crustle, weakness=EnergyType.FIRE)
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Crustle, hp=150), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
            stadium_id=lm.Nighttime_Mine,
        )
        assert result.attacker  == 0
        assert result.remain_hp == 150 - 140  # ダメージは通常通り140（無効化を貫通）

    def test_without_maximum_belt_mega_brave_does_not_ko_320hp_ex(self):
        """前提確認：Maximum Belt未装着だとメガブレイブ(270)のみではHP320・exを倒しきれない"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=337, hp=320), prize_count=6)  # Archaludon ex(ex=True)相当
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.remain_hp > 0

    def test_maximum_belt_enables_one_shot_ko_on_320hp_ex_active(self):
        """Maximum Belt装着でメガブレイブ(270)+50=320により、
        HP320・exの相手をちょうど1発でKOできることを確認する統合テスト"""
        belt = Card(id=lm.Maximum_Belt, serial=1, playerIndex=0)
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6], tools=[belt])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=337, hp=320), prize_count=6)  # Archaludon ex(ex=True)相当
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.attacker     == 0
        assert result.attack_index == 1
        assert result.remain_hp    == 0


class TestCrustleAbilityInteraction:
    """Crustle(345)の特性「ふしぎな岩の宿」対策のテスト"""

    def test_mega_lucario_ex_damage_nullified_by_crustle_ability(self):
        """Crustleの特性は相手のexポケモンの技ダメージを無効化する"""
        lm.card_table[lm.Crustle] = MockCardData(cardId=lm.Crustle, weakness=EnergyType.FIRE)
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Crustle, hp=150), prize_count=6)
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.remain_hp == 150  # 0ダメージなのでHPは変化しない

    def test_ogerpon_ex_bypasses_crustle_ability(self):
        """オーガポンexの「ぶちやぶる」は効果を計算しないためCrustleの特性を貫通する"""
        lm.card_table[lm.Crustle] = MockCardData(cardId=lm.Crustle, weakness=EnergyType.FIRE)
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Crustle, hp=150), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.remain_hp == 150 - 140

    def test_switches_to_ogerpon_ex_over_mega_lucario_ex_against_crustle(self):
        """Crustle相手にはメガルカリオexではなくオーガポンexへの切り替えが選ばれる"""
        lm.card_table[lm.Crustle] = MockCardData(cardId=lm.Crustle, weakness=EnergyType.FIRE)
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=lucario, bench=[ogerpon], prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Crustle, hp=150), prize_count=6)
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=True, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.attacker  == 1  # my_cards=[active, *bench] → bench[0]はindex1
        assert result.remain_hp == 150 - 140


class TestAttackPlanDamageField:
    """AttackPlan.damage フィールド（選択したプランの実ダメージ量）のテスト"""

    def test_damage_matches_selected_plan(self, mock_card_table):
        mock_card_table[999] = MockCardData(cardId=999)
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=999, hp=200), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.damage == 130


class TestStayBonusDamageGating:
    """位置ボーナス(i==0/j==0)がダメージ0のプランに加算されないことを確認する回帰テスト"""

    def test_switches_to_real_damage_plan_over_zero_damage_stay(self, mock_card_table):
        """Crustle対面で、0ダメージの居座りよりOgerpon_exへの切替(実ダメージ)が選ばれる"""
        mock_card_table[lm.Crustle] = MockCardData(cardId=lm.Crustle, weakness=EnergyType.FIRE)
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=lucario, bench=[ogerpon], prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Crustle, hp=2000), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=True, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.attacker == 1  # bench[0]=Ogerpon_exへの切替
        assert result.damage == 140


from tests.conftest import make_pokemon


class TestScoreRetreatOption:
    """OptionType.RETREAT のスコアリング（_score_retreat_option）のテスト"""

    def test_negative_when_plan_keeps_current_attacker(self):
        assert lm._score_retreat_option(lm.AttackPlan(attacker=0)) == -1

    def test_high_score_when_plan_switches_attacker(self):
        assert lm._score_retreat_option(lm.AttackPlan(attacker=1)) == 2000

    def test_negative_when_no_plan_computed(self):
        """plan未計算時のデフォルト(attacker=-1)でも退却は選ばれない"""
        assert lm._score_retreat_option(lm.AttackPlan()) == -1

    def test_positive_when_ineffective_attack_and_high_value_active(self):
        """居座り攻撃が無意味(damage<=0)で、現在のアクティブがex/megaExなら温存退却を推奨する"""
        plan = lm.AttackPlan(attacker=0, damage=0)
        megaex = make_pokemon(id=lm.Mega_Lucario_ex, hp=50)
        assert lm._score_retreat_option(plan, megaex, lm.card_table) == 2000

    def test_negative_when_ineffective_attack_but_regular_pokemon(self):
        """無意味な攻撃でも、現在のアクティブが無印(非ex)なら温存退却は推奨しない"""
        plan = lm.AttackPlan(attacker=0, damage=0)
        regular = make_pokemon(id=lm.Riolu, hp=50)
        assert lm._score_retreat_option(plan, regular, lm.card_table) == -1

    def test_negative_when_attack_is_effective(self):
        """実ダメージのある攻撃プランなら、温存退却の新分岐は発火しない"""
        plan = lm.AttackPlan(attacker=0, damage=130)
        megaex = make_pokemon(id=lm.Mega_Lucario_ex, hp=50)
        assert lm._score_retreat_option(plan, megaex, lm.card_table) == -1

    def test_existing_calls_remain_backward_compatible(self):
        """my_active/card_tableを省略した既存呼び出しは非破壊のまま-1/2000を返す"""
        assert lm._score_retreat_option(lm.AttackPlan(attacker=0)) == -1
        assert lm._score_retreat_option(lm.AttackPlan(attacker=1)) == 2000


class TestScoreOptionRetreatWiring:
    """main.py側でRETREATケースがmy_state.active[0]とcard_tableを正しく渡すことの統合テスト"""

    def test_score_option_retreat_uses_current_active_and_card_table(self):
        """_score_optionがRETREATケースで現在のアクティブとcard_tableを_score_retreat_optionに渡す"""
        from unittest.mock import MagicMock
        from cg.api import Option, OptionType, SelectContext
        from collections import defaultdict

        megaex = make_pokemon(id=lm.Mega_Lucario_ex, hp=50)
        my_state = make_player_state(active_pokemon=megaex, prize_count=6)
        op_state = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        plan = lm.AttackPlan(attacker=0, damage=0)
        obs = MagicMock()
        option = Option(type=OptionType.RETREAT)
        score = lm._score_option(
            obs=obs, o=option, context=SelectContext.MAIN, my_index=0,
            state=_make_state(), my_state=my_state, op_state=op_state,
            field_counts=defaultdict(int), hand_counts=defaultdict(int), discard_counts=defaultdict(int),
            attacker1=False, current_plan=plan, can_attack=True,
            stadium_id=0, ability_used_flag=False,
        )
        assert score == 2000


class TestScoreAttackOptionChoice:
    """OptionType.ATTACK のスコアリング（_score_attack_option_choice）のテスト"""

    def test_prefers_mega_brave_when_plan_selects_it(self):
        plan = lm.AttackPlan(attack_index=1)
        mega_brave = Option(type=OptionType.ATTACK, attackId=983)
        normal     = Option(type=OptionType.ATTACK, attackId=100)
        assert lm._score_attack_option_choice(mega_brave, plan) > lm._score_attack_option_choice(normal, plan)

    def test_prefers_normal_attack_when_plan_selects_it(self):
        plan = lm.AttackPlan(attack_index=0)
        mega_brave = Option(type=OptionType.ATTACK, attackId=983)
        normal     = Option(type=OptionType.ATTACK, attackId=100)
        assert lm._score_attack_option_choice(normal, plan) > lm._score_attack_option_choice(mega_brave, plan)


class TestAnalyzeMainOptionsSwitch:
    """_analyze_main_options: ポケモンいれかえ(Switch)がPLAY選択肢にあれば、
    RETREATが選択肢に無くてもcan_switchがTrueになることを確認する
    （2026-07-03に削除された旧ロジックの復活。エネルギー不足でRETREATが
    出せない局面でも、Switchがあればベンチ交代を検討できるようにする）"""

    def _analyze(self, hand_cards):
        obs = MagicMock()
        my_state = make_player_state(hand=hand_cards)
        obs.current.players = [my_state, make_player_state()]
        select = MagicMock()
        select.option = [Option(type=OptionType.PLAY, index=0)]
        return lm._analyze_main_options(obs, select, my_index=0)

    def test_can_switch_true_when_switch_in_play_options(self):
        switch_card = Card(id=lm.Switch, serial=1, playerIndex=0)
        can_switch, _, _, _ = self._analyze([switch_card])
        assert can_switch is True

    def test_can_switch_false_when_only_unrelated_card_playable(self):
        other_card = Card(id=lm.Boss_Orders, serial=1, playerIndex=0)
        can_switch, _, _, _ = self._analyze([other_card])
        assert can_switch is False

    def test_can_switch_still_true_when_retreat_option_present(self):
        """既存挙動の回帰確認：RETREATが選択肢にあれば従来通りTrue"""
        obs = MagicMock()
        obs.current.players = [make_player_state(), make_player_state()]
        select = MagicMock()
        select.option = [Option(type=OptionType.RETREAT)]
        can_switch, _, _, _ = lm._analyze_main_options(obs, select, my_index=0)
        assert can_switch is True


class TestSwitchPolicy:
    """SwitchPolicy: ポケモンいれかえのPLAYスコアリング。
    _score_retreat_optionと同条件で発火するが、にげるコスト(エネルギー破棄)を
    伴わないぶんRETREATより優先されるよう+100して返す"""

    def _ctx(self, current_plan, my_state):
        return lm.PlayScoringContext(
            obs=MagicMock(), o=Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=current_plan, can_attack=False,
            state=_make_state(), my_state=my_state,
            hand_counts=defaultdict(int), field_counts=defaultdict(int), stadium_id=0,
        )

    def test_negative_when_plan_keeps_current_attacker_and_active_is_effective(self):
        plan = lm.AttackPlan(attacker=0, damage=130)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Mega_Lucario_ex, hp=50))
        assert lm.SwitchPolicy().play_score(self._ctx(plan, my_state)) == -1

    def test_high_score_when_plan_switches_attacker(self):
        plan = lm.AttackPlan(attacker=1)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Mega_Lucario_ex, hp=50))
        assert lm.SwitchPolicy().play_score(self._ctx(plan, my_state)) == 2100

    def test_positive_when_ineffective_attack_and_high_value_active(self):
        plan = lm.AttackPlan(attacker=0, damage=0)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Mega_Lucario_ex, hp=50))
        assert lm.SwitchPolicy().play_score(self._ctx(plan, my_state)) == 2100

    def test_negative_when_ineffective_attack_but_regular_pokemon(self):
        plan = lm.AttackPlan(attacker=0, damage=0)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=50))
        assert lm.SwitchPolicy().play_score(self._ctx(plan, my_state)) == -1

    def test_scores_higher_than_retreat_when_same_condition_fires(self):
        """RETREATと同条件が成立するとき、エネルギーを失わないSwitchが+100分だけ優先される"""
        plan = lm.AttackPlan(attacker=1)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Mega_Lucario_ex, hp=50))
        retreat_score = lm._score_retreat_option(plan, my_state.active[0], lm.card_table)
        assert lm.SwitchPolicy().play_score(self._ctx(plan, my_state)) == retreat_score + 100


class TestSwitchPolicyAirBalloon:
    """最終レビュー指摘2：Air Balloon装着でアクティブの実効にげるコストが0になった場合、
    RETREATも一切エネルギーを失わなくなるため、1枚しかないSwitchを温存し
    RETREATを優先させる（base-100）。未装着なら従来通りbase+100でSwitchを優先する"""

    def _ctx(self, current_plan, my_state):
        return lm.PlayScoringContext(
            obs=MagicMock(), o=Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=current_plan, can_attack=False,
            state=_make_state(), my_state=my_state,
            hand_counts=defaultdict(int), field_counts=defaultdict(int), stadium_id=0,
        )

    def test_without_air_balloon_still_prefers_switch(self):
        """Air Balloon未装着（にげるコスト実質2）なら従来通り+100でSwitch優先（回帰確認）"""
        plan = lm.AttackPlan(attacker=1)
        my_state = make_player_state(active_pokemon=make_pokemon(id=lm.Mega_Lucario_ex, hp=50))
        base = lm._score_retreat_option(plan, my_state.active[0], lm.card_table)
        assert lm.SwitchPolicy().play_score(self._ctx(plan, my_state)) == base + 100

    def test_with_air_balloon_prefers_retreat_instead(self):
        """Air Balloon装着（にげるコスト実質0）ならSwitchを温存しRETREATを優先（base-100）"""
        plan = lm.AttackPlan(attacker=1)
        balloon = Card(id=lm.Air_Balloon, serial=1, playerIndex=0)
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=50, tools=[balloon])
        my_state = make_player_state(active_pokemon=lucario)
        base = lm._score_retreat_option(plan, my_state.active[0], lm.card_table)
        assert lm.SwitchPolicy().play_score(self._ctx(plan, my_state)) == base - 100


class TestScoreOptionPlaySwitchWiring:
    """main.py側でPLAYのSwitchケースがTRAINER_CARD_POLICIES経由で
    SwitchPolicyへ正しく配線されていることの統合テスト"""

    def test_score_option_play_switch_uses_switch_policy(self):
        switch_card = Card(id=lm.Switch, serial=1, playerIndex=0)
        my_state = make_player_state(
            active_pokemon=make_pokemon(id=lm.Mega_Lucario_ex, hp=50), hand=[switch_card],
        )
        op_state = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100))
        plan = lm.AttackPlan(attacker=1)
        obs = MagicMock()
        obs.current.players = [my_state, op_state]
        option = Option(type=OptionType.PLAY, index=0)
        score = lm._score_option(
            obs=obs, o=option, context=lm.SelectContext.MAIN, my_index=0,
            state=_make_state(), my_state=my_state, op_state=op_state,
            field_counts=defaultdict(int), hand_counts=defaultdict(int), discard_counts=defaultdict(int),
            attacker1=False, current_plan=plan, can_attack=True,
            stadium_id=0, ability_used_flag=False,
        )
        assert score == 2100


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


def _obs_with_hand(hand_cards, my_index=0, deck_count=50, prize_count=6):
    obs = MagicMock()
    my_ps = make_player_state(hand=hand_cards, deck_count=deck_count, prize_count=prize_count)
    op_ps = make_player_state()
    players = [my_ps, op_ps] if my_index == 0 else [op_ps, my_ps]
    obs.current.players = players
    return obs, players[my_index]


def _hand_counts(cards):
    """テスト用：手札カードリストからhand_counts(defaultdict)を作る"""
    counts = defaultdict(int)
    for c in cards:
        counts[c.id] += 1
    return counts


class TestPlayScoringContextScaffolding:
    """TrainerCardPolicyパターンの土台（まだ_score_play_optionには未配線）"""

    def test_fixed_score_policy_returns_constant(self):
        policy = lm.FixedScorePolicy(1234)
        ctx = lm.PlayScoringContext(
            obs=MagicMock(), o=Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=make_player_state(),
            hand_counts=defaultdict(int), field_counts=defaultdict(int), stadium_id=0,
        )
        assert policy.play_score(ctx) == 1234

    def test_trainer_card_policy_is_abstract(self):
        with pytest.raises(TypeError):
            lm.TrainerCardPolicy()


# ==================== 山札セーフティヘルパー ====================
class TestSafeDraws:
    def test_healthy_deck(self):
        my_state = make_player_state(deck_count=20, prize_count=6)
        assert lm._safe_draws(my_state) == 13

    def test_low_deck_with_few_prizes_left(self):
        my_state = make_player_state(deck_count=5, prize_count=2)
        assert lm._safe_draws(my_state) == 2

    def test_can_go_negative(self):
        """山札が残りプライズ数を下回っていれば負数（=即座に全ドロー系を止める）"""
        my_state = make_player_state(deck_count=1, prize_count=6)
        assert lm._safe_draws(my_state) == -6


class TestDeckConsumption:
    def test_lillie_determination_draws_8_when_6_prizes_left(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Lillie_Determination: 3})
        assert lm._deck_consumption(lm.Lillie_Determination, my_state, hand_counts) == 6

    def test_lillie_determination_draws_6_when_prizes_taken(self):
        my_state = make_player_state(prize_count=3)
        hand_counts = defaultdict(int, {lm.Lillie_Determination: 1})
        assert lm._deck_consumption(lm.Lillie_Determination, my_state, hand_counts) == 6

    def test_judge_draws_4(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Judge: 2})
        assert lm._deck_consumption(lm.Judge, my_state, hand_counts) == 3

    def test_hilda_is_fixed_2(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Hilda: 1})
        assert lm._deck_consumption(lm.Hilda, my_state, hand_counts) == 2

    def test_pokegear_is_fixed_1(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Pokegear: 1})
        assert lm._deck_consumption(lm.Pokegear, my_state, hand_counts) == 1

    def test_ultra_ball_is_fixed_1(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Ultra_Ball: 1})
        assert lm._deck_consumption(lm.Ultra_Ball, my_state, hand_counts) == 1

    def test_poke_pad_is_fixed_1(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Poke_Pad: 1})
        assert lm._deck_consumption(lm.Poke_Pad, my_state, hand_counts) == 1

    def test_ciphermaniac_codebreaking_is_not_gated(self):
        """山札の一番上に戻すだけで山札枚数は変わらない"""
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Ciphermaniac_Codebreaking: 1})
        assert lm._deck_consumption(lm.Ciphermaniac_Codebreaking, my_state, hand_counts) is None

    def test_wally_compassion_is_not_gated(self):
        """山札に一切触れない効果"""
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Wally_Compassion: 1})
        assert lm._deck_consumption(lm.Wally_Compassion, my_state, hand_counts) is None

    def test_night_stretcher_is_not_gated(self):
        """捨て札から回収するだけで山札には触れない"""
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Night_Stretcher: 1})
        assert lm._deck_consumption(lm.Night_Stretcher, my_state, hand_counts) is None

    def test_unrelated_card_returns_none(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Boss_Orders: 1})
        assert lm._deck_consumption(lm.Boss_Orders, my_state, hand_counts) is None


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
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
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
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1

    def test_allowed_when_consumption_equals_safe_draws(self):
        """手札1枚・プライズ6枚時のミツルの思いやりは消費8枚。山札15枚ならsafe_draws=8で丁度一致→許可"""
        card = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=15)
        o = Option(type=OptionType.PLAY, index=0)
        state = _make_state()
        state.supporterPlayed = False
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=state, my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 3100

    def test_suppressed_when_consumption_exceeds_safe_draws(self):
        """山札14枚ならsafe_draws=7<消費8枚→抑制"""
        card = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=14)
        o = Option(type=OptionType.PLAY, index=0)
        state = _make_state()
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=state, my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1


class TestJudgeDeckSafety:
    def test_scores_normally_when_deck_healthy(self):
        card = Card(id=lm.Judge, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=12)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 7000

    def test_suppressed_when_deck_low(self):
        card = Card(id=lm.Judge, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=10)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1


class TestHildaDeckSafety:
    def test_scores_normally_when_deck_healthy(self):
        card = Card(id=lm.Hilda, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=10)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 5300

    def test_suppressed_when_deck_low(self):
        card = Card(id=lm.Hilda, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=8)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1


class TestPokegearDeckSafety:
    def test_scores_normally_when_deck_healthy(self):
        card = Card(id=lm.Pokegear, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=8)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 5200

    def test_suppressed_when_deck_low(self):
        card = Card(id=lm.Pokegear, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=7)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1


class TestUltraBallDeckSafety:
    def test_scores_normally_when_deck_healthy(self):
        card = Card(id=lm.Ultra_Ball, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=8)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 6000

    def test_suppressed_when_deck_low(self):
        card = Card(id=lm.Ultra_Ball, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=7)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1


class TestPokePadDeckSafety:
    def test_scores_normally_when_deck_healthy(self):
        """Poké Padは専用スコアリングが無く汎用デフォルト10000にフォールバックする"""
        card = Card(id=lm.Poke_Pad, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=8)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 10000

    def test_suppressed_when_deck_low(self):
        card = Card(id=lm.Poke_Pad, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=7)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1


class TestNonGatedCardsIgnoreDeckSafety:
    """山札が極端に少なくてもゲートされてはいけないカード群の回帰テスト"""

    def test_ciphermaniac_codebreaking_not_suppressed_at_deck_count_1(self):
        card = Card(id=lm.Ciphermaniac_Codebreaking, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=1, prize_count=6)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 5100

    def test_wally_compassion_not_suppressed_at_deck_count_1(self):
        card = Card(id=lm.Wally_Compassion, serial=1, playerIndex=0)
        damaged_lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=100, max_hp=200)
        obs, my_state = _obs_with_hand([card], deck_count=1, prize_count=6)
        my_state.active = [damaged_lucario]
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 6800

    def test_night_stretcher_not_suppressed_at_deck_count_1(self):
        card = Card(id=lm.Night_Stretcher, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=1, prize_count=6)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 4800


class TestReplays85626724DeckOutLoss:
    """実ログ85626724（T17、山札切れで敗北した対戦）の再現テスト。
    実測：ポケギア3.0使用前=山札4枚・プライズ残3枚。新ゲートで温存されるべき"""

    def test_pokegear_would_be_suppressed_at_the_critical_moment(self):
        card = Card(id=lm.Pokegear, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=4, prize_count=3)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1


class TestSwitchContext:
    """SWITCH/TO_ACTIVEコンテキストでのオーガポンex優先度テスト"""

    def _score(self, energies, op_active_nullifies_ex=False):
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=energies)
        my_ps = make_player_state(bench=[ogerpon])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        return lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.BENCH, index=0, playerIndex=0),
            context=lm.SelectContext.SWITCH, my_index=0, state=_make_state(),
            my_state=my_ps,
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
            op_active_nullifies_ex=op_active_nullifies_ex,
        )

    def test_ogerpon_ex_prioritized_when_charged(self):
        """3エネルギー確保済み（ぶちやぶる可能）なら高優先度になる"""
        assert self._score([6, 6, 6]) == 3 * 2 + 20  # energy_count*2 + 充填済みボーナス

    def test_ogerpon_ex_low_priority_when_not_charged(self):
        """2エネルギー以下（ぶちやぶる不可）では優先度が低いまま"""
        assert self._score([6, 6]) == 2 * 2 + 6  # energy_count*2 + 充填中ボーナス

    def test_op_active_nullifies_ex_adds_extra_priority(self):
        """相手アクティブがex無効化持ちなら追加で優先度が上がる"""
        base    = self._score([6, 6, 6], op_active_nullifies_ex=False)
        boosted = self._score([6, 6, 6], op_active_nullifies_ex=True)
        assert boosted == base + 30


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

    def test_protects_rock_fighting_energy_regardless_of_count(self):
        """ロック闘エネルギーは夜のタンカで回収不可・デッキ内4枚のみのため、
        手札枚数によらず常に温存する（基本闘エネルギーは2枚以上あれば捨てて良いのと対照的）"""
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
        assert score == -20

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

    def test_protects_ogerpon_ex(self):
        """1枚しかないオーガポンexも誤トラッシュから保護する"""
        ogerpon = Card(id=lm.Ogerpon_ex, serial=1, playerIndex=0)
        obs = self._obs(ogerpon)
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


class TestScoreCardOptionAttachFrom:
    """SelectContext.ATTACH_FROM のスコアリング（_score_card_option）で
    op_active_nullifies_exが正しくenergy_scoreへ転送されることを確認するテスト"""

    def _score(self, pokemon, op_active_nullifies_ex):
        obs = MagicMock()
        my_state = make_player_state(bench=[pokemon])
        obs.current.players = [my_state, make_player_state()]
        option = Option(type=OptionType.CARD, area=lm.AreaType.BENCH, index=0, playerIndex=0)
        return lm._score_card_option(
            obs, option, context=lm.SelectContext.ATTACH_FROM, my_index=0,
            state=_make_state(), my_state=my_state,
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
            op_active_nullifies_ex=op_active_nullifies_ex,
        )

    def test_ogerpon_ex_gets_nullify_bonus_via_attach_from(self):
        """ATTACH_FROM経由でop_active_nullifies_exが転送され、
        オーガポンexのスコアが相手ex無効化持ち時に上がることを確認する
        （転送漏れの実バグの回帰テスト）"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, energies=[])
        without_flag = self._score(ogerpon, op_active_nullifies_ex=False)
        with_flag    = self._score(ogerpon, op_active_nullifies_ex=True)
        assert with_flag > without_flag


class TestScoreAttachOptionAirBalloon:
    """_score_attach_optionのふうせん(Air Balloon)分岐：メガルカリオex最優先、
    次いでリオル（両者ともにげるコスト2で、-2の効果を最大限活かせるため）。
    ベーススコアは優先ツール(Maximum Belt, 7000)との同点回避のため6900（最終レビュー指摘対応）"""

    def _score(self, pokemon):
        obs = MagicMock()
        air_balloon_card = Card(id=lm.Air_Balloon, serial=1, playerIndex=0)
        my_state = make_player_state(active_pokemon=pokemon, hand=[air_balloon_card])
        obs.current.players = [my_state, make_player_state()]
        option = Option(
            type=OptionType.ATTACH, area=lm.AreaType.HAND, index=0,
            inPlayArea=lm.AreaType.ACTIVE, inPlayIndex=0,
        )
        return lm._score_attach_option(
            obs, option, my_index=0, current_plan=lm.AttackPlan(), attacker1=False,
        )

    def test_mega_lucario_ex_highest_priority(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex)
        assert self._score(lucario) == 7100

    def test_riolu_second_priority(self):
        riolu = make_pokemon(id=lm.Riolu)
        assert self._score(riolu) == 7000

    def test_other_pokemon_base_score(self):
        solrock = make_pokemon(id=lm.Solrock)
        assert self._score(solrock) == 6900

    def test_mega_lucario_ex_scores_higher_than_riolu(self):
        assert self._score(make_pokemon(id=lm.Mega_Lucario_ex)) > self._score(make_pokemon(id=lm.Riolu))


class TestScoreAttachOptionMaximumBeltVsAirBalloon:
    """2026-07-26: Dragapult ex対策としてACE SPECをHero's CapeからMaximum Beltへ
    差し替えた。Maximum Belt(ACE SPEC・相手のアクティブexへの技ダメージ+50の恒久バフ)は
    Air Balloon(にげるコスト-2)より長期的価値が高いため、同一ポケモンを対象とした場合
    Maximum Beltのスコアが常にAir Balloonを上回ることを確認する回帰テスト"""

    def _score(self, card_id, pokemon):
        obs = MagicMock()
        card = Card(id=card_id, serial=1, playerIndex=0)
        my_state = make_player_state(active_pokemon=pokemon, hand=[card])
        obs.current.players = [my_state, make_player_state()]
        option = Option(
            type=OptionType.ATTACH, area=lm.AreaType.HAND, index=0,
            inPlayArea=lm.AreaType.ACTIVE, inPlayIndex=0,
        )
        return lm._score_attach_option(
            obs, option, my_index=0, current_plan=lm.AttackPlan(), attacker1=False,
        )

    def test_maximum_belt_beats_air_balloon_for_mega_lucario_ex(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex)
        maximum_belt_score = self._score(lm.Maximum_Belt, lucario)
        air_balloon_score  = self._score(lm.Air_Balloon, lucario)
        assert maximum_belt_score > air_balloon_score

    def test_maximum_belt_beats_air_balloon_for_riolu(self):
        riolu = make_pokemon(id=lm.Riolu)
        maximum_belt_score = self._score(lm.Maximum_Belt, riolu)
        air_balloon_score  = self._score(lm.Air_Balloon, riolu)
        assert maximum_belt_score > air_balloon_score

    def test_maximum_belt_deprioritized_for_non_attacker(self):
        """アタッカーになり得ないポケモン（Solrock等）への装着は、1枚しかない
        ACE SPECを浪費しないよう-1（温存）を返すことを確認する回帰テスト"""
        solrock = make_pokemon(id=lm.Solrock)
        assert self._score(lm.Maximum_Belt, solrock) == -1


class TestScoreAttachOptionRockFightingEnergy:
    """_score_attach_optionのRock_Fighting_Energy「アクティブ優先+500」ボーナスが、
    相手がex無効化持ち・対象がexのときは抑制されることを確認するテスト"""

    def _score(self, pokemon, op_active_nullifies_ex):
        obs = MagicMock()
        rock_energy_card = Card(id=lm.Rock_Fighting_Energy, serial=1, playerIndex=0)
        my_state = make_player_state(active_pokemon=pokemon, hand=[rock_energy_card])
        obs.current.players = [my_state, make_player_state()]
        option = Option(
            type=OptionType.ATTACH, area=lm.AreaType.HAND, index=0,
            inPlayArea=lm.AreaType.ACTIVE, inPlayIndex=0,
        )
        return lm._score_attach_option(
            obs, option, my_index=0, current_plan=lm.AttackPlan(),
            attacker1=False, op_active_nullifies_ex=op_active_nullifies_ex,
        )

    def test_bonus_suppressed_for_ex_attacker_when_op_active_nullifies_ex(self):
        """相手がex無効化持ちのとき、ex系アタッカー(メガルカリオex)への
        +500ボーナスが抑制される（実バグの回帰テスト）"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[])
        baseline = lm.energy_score(lucario, True, False, op_active_nullifies_ex=True)
        attach_score = self._score(lucario, op_active_nullifies_ex=True)
        assert attach_score == baseline

    def test_bonus_still_applies_when_op_active_nullifies_ex_is_false(self):
        """相手がex無効化持ちでなければ、ex系アタッカーにも+500ボーナスが
        従来通り付与される（回帰確認）"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[])
        baseline = lm.energy_score(lucario, True, False, op_active_nullifies_ex=False)
        attach_score = self._score(lucario, op_active_nullifies_ex=False)
        assert attach_score == baseline + 500

    def test_bonus_still_applies_for_non_ex_attacker_even_when_nullifier_present(self):
        """対象が非ex(ソルロック)なら、相手がex無効化持ちでも+500ボーナスは
        維持される（回帰確認）"""
        solrock = make_pokemon(id=lm.Solrock, energies=[])
        baseline = lm.energy_score(solrock, True, False, op_active_nullifies_ex=True)
        attach_score = self._score(solrock, op_active_nullifies_ex=True)
        assert attach_score == baseline + 500


class TestLunaCycleAbilityScore:
    def _obs_with_active_lunatone(self):
        lunatone = Card(id=lm.Lunatone, serial=1, playerIndex=0)
        obs = MagicMock()
        obs.current.players = [make_player_state(), make_player_state()]
        return obs, lunatone

    def _score(self, obs, my_state, field_counts=None, hand_counts=None):
        return lm._score_option(
            obs, Option(type=OptionType.ABILITY, area=lm.AreaType.ACTIVE, index=0),
            context=lm.SelectContext.MAIN, my_index=0, state=_make_state(),
            my_state=my_state, op_state=make_player_state(),
            field_counts=field_counts if field_counts is not None else defaultdict(int),
            hand_counts=hand_counts if hand_counts is not None else defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), can_attack=False,
            stadium_id=0, ability_used_flag=False,
        )

    def test_scores_high_when_deck_healthy(self, mock_card_table):
        """ソルロックが場におり、手札に闘エネルギーの予備(2枚)があれば発動許可"""
        obs, lunatone = self._obs_with_active_lunatone()
        obs.current.players[0].active = [lunatone]
        my_state = make_player_state(deck_count=20, prize_count=6)
        score = self._score(
            obs, my_state,
            field_counts=defaultdict(int, {lm.Solrock: 1}),
            hand_counts=defaultdict(int, {lm.Basic_Fighting_Energy: 2}),
        )
        assert score == 8500

    def test_allowed_when_safe_draws_equals_3(self, mock_card_table):
        """山札10枚・プライズ6枚ならsafe_draws=3。消費3枚と丁度一致→許可"""
        obs, lunatone = self._obs_with_active_lunatone()
        obs.current.players[0].active = [lunatone]
        my_state = make_player_state(deck_count=10, prize_count=6)
        score = self._score(
            obs, my_state,
            field_counts=defaultdict(int, {lm.Solrock: 1}),
            hand_counts=defaultdict(int, {lm.Basic_Fighting_Energy: 2}),
        )
        assert score == 8500

    def test_suppressed_when_safe_draws_below_3(self, mock_card_table):
        """山札9枚・プライズ6枚ならsafe_draws=2<消費3枚→抑制"""
        obs, lunatone = self._obs_with_active_lunatone()
        obs.current.players[0].active = [lunatone]
        my_state = make_player_state(deck_count=9, prize_count=6)
        score = self._score(
            obs, my_state,
            field_counts=defaultdict(int, {lm.Solrock: 1}),
            hand_counts=defaultdict(int, {lm.Basic_Fighting_Energy: 2}),
        )
        assert score == -1

    def test_suppressed_when_solrock_absent(self, mock_card_table):
        """カードテキスト上ソルロックが場にいないとルナサイクルは発動できない"""
        obs, lunatone = self._obs_with_active_lunatone()
        obs.current.players[0].active = [lunatone]
        my_state = make_player_state(deck_count=20, prize_count=6)
        score = self._score(
            obs, my_state,
            field_counts=defaultdict(int),  # Solrock不在
            hand_counts=defaultdict(int, {lm.Basic_Fighting_Energy: 2}),
        )
        assert score == -1

    def test_suppressed_when_only_one_energy_in_hand(self, mock_card_table):
        """手札の基本闘エネルギーが最後の1枚のときは温存し発動しない
        （実ログ86456814ほかで、手札唯一のエネルギーがルナサイクルのコストで
        失われるケースが多発していたことの再現テスト）"""
        obs, lunatone = self._obs_with_active_lunatone()
        obs.current.players[0].active = [lunatone]
        my_state = make_player_state(deck_count=20, prize_count=6)
        score = self._score(
            obs, my_state,
            field_counts=defaultdict(int, {lm.Solrock: 1}),
            hand_counts=defaultdict(int, {lm.Basic_Fighting_Energy: 1}),
        )
        assert score == -1


# ==================== Task 2: ATTACH優先度 ====================
class TestAttachRockFightingEnergyPriority:
    """ロック闘エネルギーは、アクティブのポケモンへの装着時に基本闘エネルギーより優先される
    （Alakazam「ハンドパワー」はアクティブのポケモンのみを狙う技のため）"""

    def _score(self, card_id, in_play_area):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[])
        my_ps = make_player_state(
            active_pokemon=lucario,
            bench=[lucario] if in_play_area == lm.AreaType.BENCH else [],
            hand=[Card(id=card_id, serial=1, playerIndex=0)],
        )
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        option = Option(
            type=OptionType.ATTACH, index=0,
            inPlayArea=in_play_area, inPlayIndex=0,
        )
        return lm._score_attach_option(
            obs, option, my_index=0, current_plan=lm.AttackPlan(), attacker1=False,
        )

    def test_rock_energy_scores_higher_than_basic_on_active(self):
        rock  = self._score(lm.Rock_Fighting_Energy, lm.AreaType.ACTIVE)
        basic = self._score(lm.Basic_Fighting_Energy, lm.AreaType.ACTIVE)
        assert rock > basic

    def test_rock_energy_has_no_bonus_on_bench(self):
        """ベンチへの装着では基本闘エネルギーと同スコア（アクティブ限定のボーナスのため）"""
        rock  = self._score(lm.Rock_Fighting_Energy, lm.AreaType.BENCH)
        basic = self._score(lm.Basic_Fighting_Energy, lm.AreaType.BENCH)
        assert rock == basic


class TestAttachOgerponExPriority:
    def _score(self, energies, op_active_nullifies_ex):
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, energies=energies)
        my_ps = make_player_state(
            bench=[ogerpon],
            hand=[Card(id=lm.Basic_Fighting_Energy, serial=1, playerIndex=0)],
        )
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        option = Option(type=OptionType.ATTACH, index=0, inPlayArea=lm.AreaType.BENCH, inPlayIndex=0)
        return lm._score_attach_option(
            obs, option, my_index=0, current_plan=lm.AttackPlan(), attacker1=False,
            op_active_nullifies_ex=op_active_nullifies_ex,
        )

    def test_op_active_nullifies_ex_boosts_ogerpon_ex_attach_priority(self):
        without_flag = self._score([6], op_active_nullifies_ex=False)
        with_flag    = self._score([6], op_active_nullifies_ex=True)
        assert with_flag > without_flag


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

    def test_judge_not_self_triggered_when_only_rock_energy_in_hand(self):
        """手札にロック闘エネルギーのみ（基本闘エネルギー0枚）でも
        「エネルギー切れ」と誤判定しない（潜在バグ修正）"""
        my_ps = make_player_state(hand=[Card(id=lm.Judge, serial=1, playerIndex=0)])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        score = lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=my_ps,
            hand_counts=defaultdict(int, {lm.Rock_Fighting_Energy: 1}),
            field_counts=defaultdict(int), stadium_id=0,
        )
        assert score == -1

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


class TestPremiumPowerProScoring:
    """パワープロテインのスコアリング（既存挙動の固定化テスト）"""

    def _score(self, remain_hp, can_attack, supporter_played,
               boss_in_hand=0, lillie_in_hand=0):
        my_ps = make_player_state(hand=[Card(id=lm.Premium_Power_Pro, serial=1, playerIndex=0)])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        state = _make_state()
        state.supporterPlayed = supporter_played
        plan = lm.AttackPlan(remain_hp=remain_hp)
        hand_counts = defaultdict(int, {
            lm.Boss_Orders: boss_in_hand,
            lm.Lillie_Determination: lillie_in_hand,
        })
        return lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=plan, can_attack=can_attack,
            state=state, my_state=my_ps,
            hand_counts=hand_counts, field_counts=defaultdict(int), stadium_id=0,
        )

    def test_holds_when_supporter_played_and_ko_already_confirmed(self):
        score = self._score(remain_hp=0, can_attack=True, supporter_played=True)
        assert score == -1

    def test_used_freely_when_can_attack(self):
        """攻撃可能な場面では確定KO済みでない限り優先的に使う"""
        score = self._score(remain_hp=50, can_attack=True, supporter_played=False)
        assert score == 5000

    def test_used_as_backup_supporter_when_no_other_option(self):
        """攻撃不可・サポーター未使用・他の有力サポーターも手札にない場合は温存せず使う"""
        score = self._score(remain_hp=50, can_attack=False, supporter_played=False)
        assert score == 3050

    def test_held_when_attack_impossible_but_supporter_already_played(self):
        score = self._score(remain_hp=50, can_attack=False, supporter_played=True)
        assert score == -1

    def test_held_when_better_supporter_available_in_hand(self):
        """ボスの指令が手札にあるならパワープロテインは温存"""
        score = self._score(
            remain_hp=50, can_attack=False, supporter_played=False, boss_in_hand=1,
        )
        assert score == -1


# ==================== Task 6: ボスの指令のε-greedy ====================
class _StubRng:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


class TestBossOrdersEpsilonGreedy:
    def _score(self, target, remain_hp, rng=None):
        my_ps = make_player_state(hand=[Card(id=lm.Boss_Orders, serial=1, playerIndex=0)])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        plan = lm.AttackPlan(attacker=0, target=target, attack_index=0, remain_hp=remain_hp)
        return lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=plan, can_attack=True,
            state=_make_state(), my_state=my_ps,
            hand_counts=defaultdict(int), field_counts=defaultdict(int),
            stadium_id=0, attacker1=True, rng=rng,
        )

    def test_holds_when_no_target(self):
        assert self._score(target=-1, remain_hp=0) == -1

    def test_uses_immediately_when_ko_confirmed(self):
        assert self._score(target=1, remain_hp=0) == 8800

    def test_explores_when_rng_below_epsilon(self):
        score = self._score(target=1, remain_hp=50, rng=_StubRng(0.1))
        assert score == 6000

    def test_holds_when_rng_above_epsilon(self):
        score = self._score(target=1, remain_hp=50, rng=_StubRng(0.9))
        assert score == -1


# ==================== ロジック不整合修正: Ogerpon_exのサーチ優先度 ====================
class TestToHandContext:
    """SelectContext.TO_HAND（山札サーチ時の候補選択）でのOgerpon_ex優先度テスト"""

    def _score(self, card_id, field_counts=None, hand_counts=None):
        card = Card(id=card_id, serial=1, playerIndex=0)
        obs = MagicMock()
        obs.select.deck = [card]
        return lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.DECK, index=0, playerIndex=0),
            context=lm.SelectContext.TO_HAND, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=field_counts or defaultdict(int),
            hand_counts=hand_counts or defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )

    def test_prioritized_when_not_yet_secured(self):
        """場に1枚もいなければ、リオル等と同様にサーチ優先度を上げる"""
        assert self._score(lm.Ogerpon_ex) == 200 + 40

    def test_slightly_deprioritized_with_1_in_play(self):
        fc = defaultdict(int, {lm.Ogerpon_ex: 1})
        assert self._score(lm.Ogerpon_ex, field_counts=fc) == 200 - 3

    def test_deprioritized_when_both_copies_in_play(self):
        """デッキの採用枚数(2枚)を場で使い切っていれば探す必要はない"""
        fc = defaultdict(int, {lm.Ogerpon_ex: 2})
        assert self._score(lm.Ogerpon_ex, field_counts=fc) == 200 - 150

    def test_rock_energy_prioritized_over_basic_energy(self):
        """コスト機能は同等だが効果無効化のボーナスがあるため、
        基本闘エネルギーより優先してサーチする"""
        rock  = self._score(lm.Rock_Fighting_Energy)
        basic = self._score(lm.Basic_Fighting_Energy)
        assert rock > basic


class TestUltraBallAlreadyFoundIncludesOgerponEx:
    """Ultra_Ballの使用判定(already_found)にOgerpon_exも含まれることの確認"""

    def _score(self, field_counts=None, hand_counts=None):
        obs = MagicMock()
        my_ps = make_player_state(hand=[Card(id=lm.Ultra_Ball, serial=1, playerIndex=0)])
        obs.current.players = [my_ps, make_player_state()]
        return lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=my_ps,
            hand_counts=hand_counts or defaultdict(int),
            field_counts=field_counts or defaultdict(int), stadium_id=0,
        )

    def test_lower_priority_when_ogerpon_ex_already_on_field(self):
        """リオル/メガルカリオexが未確保でも、オーガポンexが場にいれば優先度を下げる"""
        fc = defaultdict(int, {lm.Ogerpon_ex: 1})
        assert self._score(field_counts=fc) == 5500

    def test_lower_priority_when_ogerpon_ex_already_in_hand(self):
        hc = defaultdict(int, {lm.Ogerpon_ex: 1})
        assert self._score(hand_counts=hc) == 5500


class TestLillieDeterminationHandQualityGuard:
    """★修正：手札に主要ポケモンがあれば温存する。
    実ログ86363073, 86197001, 86241854, 86295193, 86295949等で、有用な手札を
    持ちながら山札に戻していたロジックミスの修正"""

    def _score(self, extra_hand_cards):
        lillie = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        cards = [lillie] + extra_hand_cards
        obs, my_state = _obs_with_hand(cards, deck_count=20)
        o = Option(type=OptionType.PLAY, index=0)
        return lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts(cards), field_counts=defaultdict(int),
            stadium_id=0,
        )

    def test_suppressed_when_riolu_in_hand(self):
        score = self._score([Card(id=lm.Riolu, serial=2, playerIndex=0)])
        assert score == -1

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

    def test_suppressed_when_ogerpon_ex_in_hand(self):
        score = self._score([Card(id=lm.Ogerpon_ex, serial=2, playerIndex=0)])
        assert score == -1

    def test_suppressed_when_solrock_in_hand(self):
        score = self._score([Card(id=lm.Solrock, serial=2, playerIndex=0)])
        assert score == -1

    def test_suppressed_when_lunatone_in_hand(self):
        score = self._score([Card(id=lm.Lunatone, serial=2, playerIndex=0)])
        assert score == -1

    def test_scores_normally_when_no_key_pokemon_in_hand(self):
        score = self._score([Card(id=lm.Pokegear, serial=2, playerIndex=0)])
        assert score == 3100


class TestUltraBallAlreadyFoundSuppression:
    """★修正：主要ポケモンを十分確保済み（already_found>=3）ならスコアを大幅に下げる。
    実ログ86197001で、手札がボスの指令とメガルカリオexの2枚しかない状況でもハイパー
    ボールを撃ち両方とも巻き込んで捨てていたロジックミスの修正"""

    def _score(self, field_counts=None, hand_counts=None):
        my_ps = make_player_state(hand=[Card(id=lm.Ultra_Ball, serial=1, playerIndex=0)])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        return lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=my_ps,
            hand_counts=hand_counts or defaultdict(int),
            field_counts=field_counts or defaultdict(int), stadium_id=0,
        )

    def test_still_high_priority_when_already_found_is_2(self):
        fc = defaultdict(int, {lm.Riolu: 1, lm.Mega_Lucario_ex: 1})
        assert self._score(field_counts=fc) == 5500

    def test_suppressed_when_already_found_is_3(self):
        fc = defaultdict(int, {lm.Riolu: 1, lm.Mega_Lucario_ex: 1, lm.Ogerpon_ex: 1})
        assert self._score(field_counts=fc) == 100

    def test_suppressed_when_already_found_exceeds_3(self):
        fc = defaultdict(int, {lm.Riolu: 2, lm.Mega_Lucario_ex: 1, lm.Ogerpon_ex: 1})
        assert self._score(field_counts=fc) == 100


class TestSetupActivePokemonOgerponPriority:
    """SelectContext.SETUP_ACTIVE_POKEMONでのオーガポンex優先度テスト。
    実ログ86197001：開幕手札にRiolu/Solrockが無く、Lunatone(攻撃不可)とOgerpon_ex
    (3エネで攻撃可能)が両方あった場面で同点(0)によりLunatoneが選ばれ、以後
    エネルギー無しで自力退場できず20ターン無攻撃のまま敗北していたロジックミスの修正"""

    def _score(self, card_id):
        card = Card(id=card_id, serial=1, playerIndex=0)
        obs = MagicMock()
        obs.select.deck = [card]
        return lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.DECK, index=0, playerIndex=0),
            context=lm.SelectContext.SETUP_ACTIVE_POKEMON, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )

    def test_ogerpon_ex_score_is_1(self):
        assert self._score(lm.Ogerpon_ex) == 1

    def test_lunatone_score_unchanged_at_0(self):
        assert self._score(lm.Lunatone) == 0

    def test_ogerpon_ex_beats_lunatone_reproducing_log_86197001(self):
        assert self._score(lm.Ogerpon_ex) > self._score(lm.Lunatone)

    def test_riolu_still_takes_priority_over_ogerpon_ex(self):
        assert self._score(lm.Riolu) > self._score(lm.Ogerpon_ex)

    def test_solrock_still_takes_priority_over_ogerpon_ex(self):
        assert self._score(lm.Solrock) > self._score(lm.Ogerpon_ex)
