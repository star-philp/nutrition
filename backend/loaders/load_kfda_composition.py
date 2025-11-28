"""
국가표준식품성분표(엑셀)에서 핵심 영양성분(에너지/단백질/탄수화물/지방/나트륨)을 추출하여
ingredients 테이블에 upsert 합니다.

입력 파일: ml/data/foods/국가표준식품성분표_250426공개.xlsx
대상 시트: "국가표준식품성분 Database 10.2" (우선)

주의: 헤더가 2행 구조(이름/단위)이므로 header=[1,2]를 조합하여 컬럼명을 생성합니다.
"""

from __future__ import annotations

import math
import os
from typing import Dict, Optional
import sys

import pandas as pd
from sqlalchemy.orm import Session

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.core.db import SessionLocal
from sqlalchemy import text
from app.models import recipe as models


SOURCE_XLSX = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
    "ml",
    "data",
    "foods",
    "국가표준식품성분표_250426공개.xlsx",
)
TARGET_SHEET = "국가표준식품성분 Database 10.2"


def _combine_headers(xls: pd.ExcelFile, sheet: str) -> pd.DataFrame:
    # 이름행(header=1), 단위행(header=2)
    df_names = pd.read_excel(xls, sheet_name=sheet, header=1, nrows=0, engine="openpyxl")
    df_units = pd.read_excel(xls, sheet_name=sheet, header=2, nrows=0, engine="openpyxl")
    names = [str(c).strip() for c in df_names.columns]
    units = [str(c).strip() for c in df_units.columns]
    combined = []
    for n, u in zip(names, units):
        if u and u != "nan":
            combined.append(f"{n} ({u})")
        else:
            combined.append(n)
    # 실제 데이터는 header=3부터 시작하는 것으로 관찰됨
    df = pd.read_excel(xls, sheet_name=sheet, header=3, engine="openpyxl")
    df.columns = combined[: len(df.columns)]
    return df


def _find_column_base(df: pd.DataFrame, base_korean: str) -> Optional[str]:
    target = base_korean.replace(" ", "")
    for col in df.columns:
        raw = str(col)
        col_norm = raw.replace(" ", "").replace("\n", "")
        # 예: "단백질 (g)", "단백질 (g.1)" 등 다양한 변형 허용
        if col_norm.startswith(target):
            return raw
    return None


def _to_float(value) -> Optional[float]:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return float(value)
    except Exception:
        return None


def load_into_db(db: Session) -> None:
    if not os.path.exists(SOURCE_XLSX):
        print(f"엑셀 파일을 찾을 수 없습니다: {SOURCE_XLSX}")
        return

    x = pd.ExcelFile(SOURCE_XLSX, engine="openpyxl")
    if TARGET_SHEET not in x.sheet_names:
        print(f"시트를 찾을 수 없습니다: {TARGET_SHEET}")
        return

    df = _combine_headers(x, TARGET_SHEET)

    col_food_name = _find_column_base(df, "식품명")
    col_energy = _find_column_base(df, "에너지")
    col_protein = _find_column_base(df, "단백질")
    col_fat = _find_column_base(df, "지방")
    col_carbs = _find_column_base(df, "탄수화물")
    col_sodium = _find_column_base(df, "나트륨")

    missing = [
        ("식품명", col_food_name),
        ("에너지(kcal)", col_energy),
        ("단백질(g)", col_protein),
        ("지방(g)", col_fat),
        ("탄수화물(g)", col_carbs),
        ("나트륨(mg)", col_sodium),
    ]
    for label, col in missing:
        if col is None:
            print(f"경고: 컬럼을 찾지 못했습니다 → {label}")

    inserted = 0
    updated = 0

    for _, row in df.iterrows():
        name = str(row[col_food_name]).strip() if col_food_name else None
        if not name or name == "nan":
            continue

        calories = _to_float(row[col_energy]) if col_energy else None
        protein = _to_float(row[col_protein]) if col_protein else None
        fat = _to_float(row[col_fat]) if col_fat else None
        carbs = _to_float(row[col_carbs]) if col_carbs else None
        sodium = _to_float(row[col_sodium]) if col_sodium else None

        # upsert by name
        ing = db.query(models.Ingredient).filter(models.Ingredient.name == name).first()
        if ing is None:
            ing = models.Ingredient(
                name=name,
                calories_kcal=calories,
                protein_g=protein,
                fat_g=fat,
                carbs_g=carbs,
                sodium_mg=sodium,
                source="KoreanFoodCompDB10.2",
            )
            db.add(ing)
            inserted += 1
        else:
            changed = False
            if calories is not None:
                ing.calories_kcal = calories; changed = True
            if protein is not None:
                ing.protein_g = protein; changed = True
            if fat is not None:
                ing.fat_g = fat; changed = True
            if carbs is not None:
                ing.carbs_g = carbs; changed = True
            if sodium is not None:
                ing.sodium_mg = sodium; changed = True
            if changed:
                updated += 1

    # 시퀀스 보정: 초기 수동 ID 삽입으로 깨졌을 수 있음
    try:
        db.execute(text("SELECT setval(pg_get_serial_sequence('ingredients','id'), COALESCE(MAX(id),0)) FROM ingredients"))
    except Exception:
        pass

    db.commit()
    print(f"완료: 삽입 {inserted} 건, 업데이트 {updated} 건")


def main() -> None:
    db = SessionLocal()
    try:
        load_into_db(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()


