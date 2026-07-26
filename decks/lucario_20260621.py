# ルカリオデッキ定義（20260725 Judge増量・Switch/Air Balloon採用）
# 2026-07-03軽量版リビルドをベースに、資源制約(Judge枯渇)と交代手段の
# 欠如という2つの既知ギャップに対応。単発サポート3種(Hilda/Wally's
# Compassion/Ciphermaniac's Codebreaking)を削り採用枠に充てた

DECK = [
    (677, 4),    # Riolu
    (678, 3),    # Mega Lucario ex
    (676, 2),    # Solrock（3→2。オーガポンex増量のため1枚減）
    (675, 2),    # Lunatone
    (117, 2),    # Cornerstone Mask Ogerpon ex（1→2に増量。Crustle対策の要）
    (1142, 4),   # Fighting Gong
    (1121, 4),   # Ultra Ball
    (1152, 2),   # Poké Pad
    (1141, 4),   # Premium Power Pro
    (1097, 2),   # Night Stretcher
    (1122, 4),   # Pokégear 3.0
    (1158, 1),   # Maximum Belt（ACE SPEC。Dragapult ex(HP320)対策、Hero's Capeから差し替え。2026-07-26）
    (1227, 4),   # Lillie's Determination
    (1182, 4),   # Boss's Orders
    (1213, 3),   # Judge（2→3。Alakazam対面のJudge資源枯渇対策）
    (1123, 1),   # Switch（ポケモンいれかえ。自発的な交代手段の欠如への対応、新規採用）
    (1174, 2),   # Air Balloon（ふうせん。にげるコスト-2、新規採用）
    (1252, 1),   # Gravity Mountain
    (6, 7),      # Basic {F} Energy
    (20, 4),     # Rock {F} Energy（Alakazam「ハンドパワー」対策。闘エネルギー1個分＋相手の技の効果を無効化）
]
