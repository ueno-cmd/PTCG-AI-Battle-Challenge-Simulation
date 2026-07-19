#!/usr/bin/env python3
"""EN + JP カードデータを Card ID でJOINして統合CSVを生成する"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

EN_CSV = DATA_DIR / "competition" / "EN_Card_Data.csv"
JP_CSV = DATA_DIR / "competition" / "JP_Card_Data.csv"
OUT_CSV = DATA_DIR / "derived" / "card_data_merged.csv"

# EN列名 → 出力列名のマッピング
EN_RENAME = {
    "Card ID": "card_id",
    "Card Name": "card_name_en",
    "Expansion": "expansion_en",
    "Collection No.": "collection_no_en",
    "Stage (Pokémon)/Type (Energy and Trainer)": "stage_en",
    "Rule": "rule_en",
    "Category": "category_en",
    "Previous stage": "previous_stage_en",
    "HP": "hp",
    "Type": "type_en",
    "Weakness": "weakness_en",
    "Resistance (Type)": "resistance_en",
    "Retreat": "retreat",
    "Move Name": "move_name_en",
    "Cost": "cost_en",
    "Damage": "damage",
    "Effect Explanation": "effect_en",
}

# JP列名 → 出力列名のマッピング（card_id以外）
JP_RENAME = {
    "カード ID": "card_id",
    "カード名": "card_name_jp",
    "エキスパンションマーク": "expansion_jp",
    "コレクション番号": "collection_no_jp",
    "ポケモンの進化の段階/エネルギー・トレーナーズの種類": "stage_jp",
    "ルール": "rule_jp",
    "カテゴリ": "category_jp",
    "進化前": "previous_stage_jp",
    "HP": "hp_jp",        # hp はENから使うため _jp でキープ
    "タイプ": "type_jp",
    "弱点": "weakness_jp",
    "抵抗力": "resistance_jp",
    "にげる": "retreat_jp",
    "ワザ名": "move_name_jp",
    "コスト": "cost_jp",
    "ダメージ": "damage_jp",
    "効果の説明": "effect_jp",
}


def main() -> None:
    df_en = pd.read_csv(EN_CSV).rename(columns=EN_RENAME)
    df_jp = pd.read_csv(JP_CSV).rename(columns=JP_RENAME)

    # card_id 内の行順序（技の順番）で対応付けるため cumcount をキーに追加
    # EN・JPは同一Card IDに対して同じ行数・同じ順序を持つことを前提とする
    df_en["_row_in_card"] = df_en.groupby("card_id").cumcount()
    df_jp["_row_in_card"] = df_jp.groupby("card_id").cumcount()

    df = df_en.merge(df_jp, on=["card_id", "_row_in_card"], how="inner")
    df = df.drop(columns=["_row_in_card"])

    # 読みやすい列順：識別情報 → EN主要列 → JP主要列 → その他
    col_order = [
        "card_id",
        "card_name_en", "card_name_jp",
        "expansion_en", "expansion_jp",
        "collection_no_en", "collection_no_jp",
        "stage_en", "stage_jp",
        "rule_en", "rule_jp",
        "category_en", "category_jp",
        "previous_stage_en", "previous_stage_jp",
        "hp", "hp_jp",
        "type_en", "type_jp",
        "weakness_en", "weakness_jp",
        "resistance_en", "resistance_jp",
        "retreat", "retreat_jp",
        "move_name_en", "move_name_jp",
        "cost_en", "cost_jp",
        "damage", "damage_jp",
        "effect_en", "effect_jp",
    ]
    df = df[[c for c in col_order if c in df.columns]]

    df.to_csv(OUT_CSV, index=False)
    print(f"出力: {OUT_CSV}")
    print(f"行数: {len(df)} 件")


if __name__ == "__main__":
    main()
