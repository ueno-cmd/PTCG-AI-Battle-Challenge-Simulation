# ジュナイパーexコントロール デッキ定義（20260621生成）
# コンセプト: Judge/Xerosicで相手手札を4枚に固定 → Sniper's Eye発動 → Crushing Arrow が {G}1枚で240ダメ

DECK = [
    # ポケモン (13枚)
    (1020, 4),   # Rowlet (Find a Friend サーチ)
    (1021, 1),   # Dartrix
    (1022, 3),   # Decidueye ex (Sniper's Eye + Crushing Arrow)
    (96,   2),   # Teal Mask Ogerpon ex (Teal Dance: 毎ターン1ドロー、Tera: ベンチ被弾なし)
    (235,  2),   # Budew (Itchy Pollen: 相手アイテム封じ)
    (27,   1),   # Iron Leaves (Recovery Net: 手札からポケモン回収)

    # エネルギー (9枚)
    (1,    9),   # Basic {G} Energy

    # トレーナー (38枚)
    # 妨害・手札コントロール
    (1213, 4),   # Judge (両者4枚リセット → Sniper's Eye即起動)
    (1197, 3),   # Xerosic's Machinations (相手3枚 → 次ターン4枚 → Sniper's Eye ON)
    (1120, 3),   # Crushing Hammer (相手エネルギー剥がし)

    # 進化補助
    (1079, 4),   # Rare Candy (Rowlet → Decidueye ex 直接進化)

    # サーチ・展開
    (1121, 4),   # Ultra Ball (任意ポケモン検索)
    (1086, 3),   # Buddy-Buddy Poffin (基本ポケモン2体展開)
    (1094, 3),   # Bug Catching Set ({G}ポケモン・草エネサーチ)
    (1102, 2),   # Dusk Ball (ポケモン検索)

    # サポーター
    (1182, 2),   # Boss's Orders (相手ポケモン呼び出し)
    (1192, 2),   # Carmine (序盤ドロー・先攻1ターン目使用可)
    (1185, 3),   # Explorer's Guidance (上6枚から2枚選択)

    # 回収・その他
    (1097, 2),   # Night Stretcher (ポケモン回収)
    (1087, 1),   # Hand Trimmer (両者5枚に調整)
    (1088, 1),   # Prime Catcher [ACE SPEC] (入れ替え)
    (1122, 1),   # Pokégear 3.0 (サポーター検索)
]
