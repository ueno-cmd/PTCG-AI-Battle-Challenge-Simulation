"""影武者カウントセル（SHADOW_CODE）の単体テスト

ビルドスクリプトがノートブックに埋め込むセルのソースを、スタブの
agent / _score_attach / _rng と同じ名前空間でexecし、計測ロジックを検証する。
実際の対戦エンジン（libcg）はローカルで動かないため使わない。
"""
import importlib.util
import random
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_grimmsnarl_calibration_notebook.py"
_spec = importlib.util.spec_from_file_location("build_calib_nb", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # main()は __main__ ガードで走らない
SHADOW_CODE = _mod.SHADOW_CODE

# 本物のカードID定数の代わりに使う適当な値（名前空間に同名で注入する）
GRIMMSNARL_ID = 101
MORPEKO_ID = 102
ENERGY_ID = 900

WEIGHTS_A = {"grimmsnarl_base": 9000, "morpeko_base": 4500}
WEIGHTS_B = {"grimmsnarl_base": 4500, "morpeko_base": 9000}

# 本物のagent()を模したスタブ。乱数を1回消費し、候補ごとにグローバル名
# _score_attach を呼んで最高点の候補インデックスを返す（本物と同じ参照経路）
STUB_SRC = '''
class FakePokemon:
    def __init__(self, pid):
        self.id = pid
        self.energies = []


def _score_attach(pokemon, area, card_id, fs):
    if pokemon.id == Grimmsnarl_ex:
        return TUNABLE_WEIGHTS["grimmsnarl_base"]
    return TUNABLE_WEIGHTS["morpeko_base"]


def agent(obs_dict):
    _rng.random()  # 本物のε探索に相当する乱数消費
    candidates = obs_dict["candidates"]
    if not candidates:
        return [0]
    scores = [_score_attach(p, None, Basic_D_Energy, None) for p in candidates]
    return [max(range(len(scores)), key=scores.__getitem__)]
'''


def make_ns(seed: int = 0) -> dict:
    """スタブ→SHADOW_CODEの順で同一名前空間にexecし、その名前空間を返す"""
    ns = {
        "TUNABLE_WEIGHTS": dict(WEIGHTS_A),
        "_rng": random.Random(seed),
        "Basic_D_Energy": ENERGY_ID,
        "Grimmsnarl_ex": GRIMMSNARL_ID,
        "Marnie_Morpeko": MORPEKO_ID,
    }
    exec(STUB_SRC, ns)
    exec(SHADOW_CODE, ns)
    return ns


def make_obs(ns: dict, pokemon_ids: list[int]) -> dict:
    fake = ns["FakePokemon"]
    return {"candidates": [fake(pid) for pid in pokemon_ids]}


class TestShadowAgent:
    def test_returns_main_selection(self):
        # AとBで選択が割れる盤面でも、返すのは必ずA（本線）の選択
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        obs = make_obs(ns, [GRIMMSNARL_ID, MORPEKO_ID])
        assert shadow(obs) == [0]  # Aではオーロンゲ（index 0）が最高点

    def test_counts_all_diffs_when_weights_flip_choice(self):
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        shadow(make_obs(ns, [GRIMMSNARL_ID, MORPEKO_ID]))
        stats = ns["SHADOW_STATS"]
        assert stats["calls"] == 1
        assert stats["select_diff"] == 1
        assert stats["attach_calls"] == 1
        assert stats["attach_score_diff"] == 1
        assert stats["attach_top_diff"] == 1
        assert stats["grimmsnarl_morpeko_both"] == 1

    def test_no_diffs_when_shadow_uses_same_weights(self):
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, dict(WEIGHTS_A))
        shadow(make_obs(ns, [GRIMMSNARL_ID, MORPEKO_ID]))
        stats = ns["SHADOW_STATS"]
        assert stats["calls"] == 1
        assert stats["select_diff"] == 0
        assert stats["attach_score_diff"] == 0
        assert stats["attach_top_diff"] == 0
        assert stats["grimmsnarl_morpeko_both"] == 1  # 競合場面自体は数える

    def test_no_competition_count_with_single_candidate(self):
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        shadow(make_obs(ns, [GRIMMSNARL_ID]))
        stats = ns["SHADOW_STATS"]
        assert stats["attach_calls"] == 1
        assert stats["grimmsnarl_morpeko_both"] == 0
        assert stats["select_diff"] == 0  # 候補1体ならどちらの重みでも同じ選択

    def test_attach_calls_not_counted_without_candidates(self):
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        shadow(make_obs(ns, []))
        stats = ns["SHADOW_STATS"]
        assert stats["calls"] == 1
        assert stats["attach_calls"] == 0

    def test_mainline_rng_advances_exactly_once_per_call(self):
        # 影武者（B側）の呼び出しが本線の乱数系列を乱さないこと：
        # 1回のshadow呼び出し後の_rngは「random()を1回消費したRandom(0)」と一致する
        ns = make_ns(seed=0)
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        shadow(make_obs(ns, [GRIMMSNARL_ID, MORPEKO_ID]))
        reference = random.Random(0)
        reference.random()
        assert ns["_rng"].getstate() == reference.getstate()

    def test_tunable_weights_restored_to_main_after_call(self):
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        shadow(make_obs(ns, [GRIMMSNARL_ID, MORPEKO_ID]))
        assert ns["TUNABLE_WEIGHTS"] == WEIGHTS_A

    def test_stats_accumulate_across_calls(self):
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        shadow(make_obs(ns, [GRIMMSNARL_ID, MORPEKO_ID]))
        shadow(make_obs(ns, [GRIMMSNARL_ID]))
        stats = ns["SHADOW_STATS"]
        assert stats["calls"] == 2
        assert stats["select_diff"] == 1
        assert stats["grimmsnarl_morpeko_both"] == 1
