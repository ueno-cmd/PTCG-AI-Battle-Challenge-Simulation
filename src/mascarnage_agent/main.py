# src/mascarnage_agent/main.py
import os

from cg.api import (
    AreaType, CardType, EnergyType,
    Observation, SelectContext, OptionType,
    Card, Pokemon, all_card_data, to_observation_class,
)

# =====================================================================
# カードID定数
# ※ Task 6実施前に Kaggle Dataタブでカードプールを確認してから設定する
# =====================================================================
# マスカーニャexデッキ（カード確認後に設定）
NYAHOJA       = 0   # ニャオハ
NYAROTE       = 0   # ニャローテ
MASCARNAGE_EX = 0   # マスカーニャex
# トレーナーズ等も同様に確認後に設定

# フォールバック用：ドラパルトex（カードプール確認済み）
DREEPY       = 119
DRAKLOAK     = 120
DRAGAPULT_EX = 121

# ダメカンを置けない免疫ポケモンID（既知リスト、環境変化で更新）
_IMMUNE_IDS = frozenset({
    28,   # ポットデス
    199,  # エンペルトex
    203,  # スケルジ
    207,  # ミロカロスex
    362,  # ミスティのコイキング
    1136, # むかしのふたのかせき
})

# ダメカンを置けない特殊エネルギーID
_IMMUNE_ENERGY_IDS = frozenset({
    11,  # ミストエネルギー
    20,  # がんせきかくとうエネルギー
})

# =====================================================================
# カードテーブル（遅延初期化 — agent()初回呼び出し時にロード）
# =====================================================================
_card_table: dict = {}


def _load_cards() -> dict:
    """カードテーブルを遅延初期化する"""
    global _card_table
    if not _card_table:
        all_card = all_card_data()
        _card_table = {c.cardId: c for c in all_card}
    return _card_table


# =====================================================================
# デッキ読み込み（モジュールロード時 — Kaggle実行環境用）
# =====================================================================
def _read_deck() -> list[int]:
    file_path = "deck.csv"
    if not os.path.exists(file_path):
        file_path = "/kaggle_simulations/agent/" + file_path
    if not os.path.exists(file_path):
        return []  # テスト環境ではデッキなし
    with open(file_path, "r") as f:
        lines = f.read().split("\n")
    return [int(lines[i]) for i in range(60)]


my_deck = _read_deck()


# =====================================================================
# ヘルパー関数
# =====================================================================

def get_card(obs: Observation, area: AreaType, index: int, player_index: int):
    """エリア×インデックスからカードまたはポケモンを取得する"""
    ps = obs.current.players[player_index]
    match area:
        case AreaType.DECK:
            return obs.select.deck[index]
        case AreaType.HAND:
            return ps.hand[index]
        case AreaType.DISCARD:
            return ps.discard[index]
        case AreaType.ACTIVE:
            return ps.active[index]
        case AreaType.BENCH:
            return ps.bench[index]
        case AreaType.PRIZE:
            return ps.prize[index]
        case AreaType.STADIUM:
            return obs.current.stadium[index]
        case AreaType.LOOKING:
            return obs.current.looking[index]
        case _:
            return None


def no_damage_counter(pokemon: Pokemon) -> bool:
    """相手ポケモンにダメカンを置けないかどうかを判定する"""
    if pokemon.id in _IMMUNE_IDS:
        return True
    for card in pokemon.energyCards:
        if card.id in _IMMUNE_ENERGY_IDS:
            return True
    return False


def prize_count(pokemon: Pokemon, card_table: dict) -> int:
    """ポケモンをKOしたときに相手が取るサイド枚数を返す"""
    data = card_table.get(pokemon.id)
    if data is None:
        return 1
    if data.megaEx:
        return 3
    if data.ex:
        return 2
    return 1


# =====================================================================
# スコアリング関数
# =====================================================================

def bouquet_magic_score(target: Pokemon) -> int:
    """ブーケマジックのターゲット選択スコアを計算する（高いほど優先）"""
    if no_damage_counter(target):
        return -1
    # HPが低いほど高スコア（早期KO優先）
    score = 10000 - target.hp
    # すでにダメカンが乗っていれば追加ボーナス
    if target.hp < target.maxHp:
        score += 5000
    return score


# =====================================================================
# エージェント本体（スコアリングは後続Taskで実装）
# =====================================================================

def agent(obs_dict: dict) -> list[int]:
    """ポケモンカードゲームAIエージェント本体"""
    obs = to_observation_class(obs_dict)

    # 初回呼び出し時のみ実行（カードテーブル初期化）
    card_table = _load_cards()

    # デッキ選択フェーズ（obs.selectがNoneの場合）
    if obs.select is None:
        return my_deck

    state   = obs.current
    select  = obs.select
    context = select.context
    my_index   = state.yourIndex
    my_state   = state.players[my_index]
    op_state   = state.players[1 - my_index]

    scores = []
    for o in select.option:
        score = 0

        if o.type == OptionType.NUMBER:
            score = o.number or 0

        elif o.type == OptionType.YES:
            score = 1

        elif o.type == OptionType.EVOLVE:
            # 進化は最優先（後続ロジックを制御しやすくする）
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            score = 110000 + (len(pokemon.energies) if pokemon else 0)

        elif o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            if card is None:
                score = -1
            elif card_table.get(card.id) and card_table[card.id].cardType == CardType.POKEMON:
                score = 100000
            else:
                score = 70000  # トレーナーズ全般（詳細はデッキ確認後に調整）

        elif o.type == OptionType.ABILITY:
            # ブーケマジック（マスカーニャexの特性）
            card = get_card(obs, o.area, o.index, my_index)
            if card is not None and card.id == MASCARNAGE_EX:
                # ベンチ全体で最もスコアの高いターゲットを基準にする
                bench_scores = [
                    bouquet_magic_score(p) for p in op_state.bench
                ]
                best = max(bench_scores, default=-1)
                score = 60000 + best if best >= 0 else -1
            else:
                score = 40000  # 他のアビリティ

        elif o.type == OptionType.ATTACH:
            score = 50000

        elif o.type == OptionType.RETREAT:
            score = 30000

        elif o.type == OptionType.ATTACK:
            # 攻撃は最後（ターンを終わらせる行動）
            # スクラッチネイル：相手バトルポケモンにダメカンがあれば優先
            base = 1000 + (o.attackId or 0)
            if op_state.active and len(op_state.active) > 0:
                op_active = op_state.active[0]
                if op_active and op_active.hp < op_active.maxHp:
                    base += 5000  # ダメカンあり → スクラッチネイル高威力
            score = base

        elif o.type == OptionType.END:
            score = 0

        scores.append(score)

    sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return sorted_indices[:select.maxCount]
