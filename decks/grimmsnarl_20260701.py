# マリィのグリムスナールex デッキ（20260702改修）
# 設計書: docs/superpowers/specs/2026-07-02-grimmsnarl-deck-revision-design.md
# 背景: LBスコアが700→500に下落。負けログ5件の解析でデッキアウト負け・進化事故負けが
#       判明したため、山札消費の大きいカードを整理し進化ラインを厚くした。
#       あわせてカードショップ大会リスト（本大会ルールとは異なる環境）を参考に
#       トールボックス要素（特性ポケモン群）を導入。

DECK = [
    # --- ポケモン: 20体 ---
    (646,  3),   # Marnie's Impidimp（進化元・Filchで初動ドロー・70HP）
    (647,  2),   # Marnie's Morgrem（進化中継・Rare Candy未引き時の保険を強化）
    (648,  3),   # Marnie's Grimmsnarl ex（メインアタッカー）
    (860,  2),   # Snorunt（Froslassの進化元）
    (104,  2),   # Froslass（特性: 毎ターン全特性持ちポケモンに1ダメカン。攻撃は使わない前提）
    (112,  3),   # Munkidori（Adrena-Brainでダメカン移動。Froslassの副産物ダメカンを転嫁）
    (235,  1),   # Budew（相手のグッズ使用を1ターン封じる）
    (343,  1),   # Shaymin（特性: 自分のルール無しベンチポケモンへのダメージを無効化）
    (122,  1),   # Tatsugiri（特性: バトル場にいる間、山札上6枚からサポートを回収）
    (689,  1),   # Yveltal（わしづかみ：相手を次の番にげられなくする。ガチグマの代替）
    (858,  1),   # Psyduck（特性: 自傷前提の特性を封じる）

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
