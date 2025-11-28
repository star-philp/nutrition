"""
식단 엑셀(날짜, 생후, 끼니, 식품군, 재료명, 중량, 단위, 유형) -> MealLog 적재.
매핑 전략: 재료명은 Ingredient.name 과 일치 시도. 중량 단위가 g가 아닐 경우 단순 변환(ml->g는 물 가정:1ml=1g) 적용.

엑셀 파일 경로:
 - ml/data/foods/meals_2025-08-20_GwBk.xlsx
 - ml/data/foods/meals_2025-08-20_hOUQ.xlsx

테스트용으로 recipe_id가 없으므로, 각 재료명을 단일 재료 레시피로 가정하는 가상 레시피를 생성해 기록합니다.
"""

from __future__ import annotations

import os
from datetime import datetime
import sys
from typing import List

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import or_
import re

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.core.db import SessionLocal
from app.models import recipe as models


MEAL_FILES: List[str] = [
    os.path.join("ml", "data", "foods", "meals_2025-08-20_GwBk.xlsx"),
    os.path.join("ml", "data", "foods", "meals_2025-08-20_hOUQ.xlsx"),
]


def ensure_single_ingredient_recipe(db: Session, ingredient_id: int, ingredient_name: str) -> str:
    recipe_id = f"ING_{ingredient_id}"
    recipe = db.query(models.Recipe).filter(models.Recipe.recipe_id == recipe_id).first()
    if not recipe:
        recipe = models.Recipe(
            recipe_id=recipe_id,
            recipe_name=f"{ingredient_name} 단일 재료",
            category="단일",
            description="단일 재료 섭취 자동 생성 레시피",
        )
        db.add(recipe)
        db.commit()
    # 구성도 보장
    exists = (
        db.query(models.RecipeIngredient)
        .filter(models.RecipeIngredient.recipe_id == recipe_id,
                models.RecipeIngredient.ingredient_id == ingredient_id)
        .first()
    )
    if not exists:
        ri = models.RecipeIngredient(
            recipe_id=recipe_id,
            ingredient_id=ingredient_id,
            quantity_grams=100.0,  # 1인분=100g 기준
        )
        db.add(ri)
        db.commit()
    return recipe_id


def to_grams(amount, unit: str) -> float:
    unit = (unit or "").strip().lower()
    try:
        value = float(amount)
    except Exception:
        return 0.0
    if unit in ("g", "그램", "gram"):
        return value
    if unit in ("ml", "밀리리터"):
        return value  # 물 가정
    if unit in ("kg"):
        return value * 1000.0
    # 기타 단위는 일단 무시
    return value


def load_file(db: Session, path: str) -> None:
    if not os.path.exists(path):
        print(f"건너뜀(없음): {path}")
        return
    x = pd.ExcelFile(path, engine="openpyxl")
    df = pd.read_excel(x, sheet_name=0)

    # 기대 컬럼
    col_date = "날짜"
    col_name = "재료명"
    col_amount = "중량"
    col_unit = "단위"

    for _, row in df.iterrows():
        name = str(row.get(col_name, "")).strip()
        if not name:
            continue
        amount = row.get(col_amount, 0)
        unit = str(row.get(col_unit, "")).strip()
        grams = to_grams(amount, unit)
        # 날짜
        raw_date = row.get(col_date)
        try:
            meal_time = pd.to_datetime(raw_date)
        except Exception:
            meal_time = datetime.now()

        ing = find_best_ingredient(db, name)
        if not ing:
            print(f"재료 미존재: {name}")
            continue

        recipe_id = ensure_single_ingredient_recipe(db, ing.id, ing.name)

        # portion: grams / 100g (단일레시피 1인분=100g 설정)
        portion = float(grams) / 100.0 if grams else 0.0
        if portion <= 0:
            continue

        # 영양 계산을 위해 MealLog 생성 전 계산 값이 필요하므로 main의 헬퍼 로직을 재사용하는 대신, DB 트리거는 생략하고 그대로 기록
        # 단, MealLog에는 계산된 영양소가 필요하므로 100g 기준 영양소 * portion 으로 기록
        calories = float(ing.calories_kcal or 0) * portion
        protein = float(ing.protein_g or 0) * portion
        carbs = float(ing.carbs_g or 0) * portion
        fat = float(ing.fat_g or 0) * portion

        log = models.MealLog(
            user_id=1,
            recipe_id=recipe_id,
            portion=portion,
            meal_time=meal_time.to_pydatetime() if hasattr(meal_time, 'to_pydatetime') else meal_time,
            calories_kcal=calories,
            protein_g=protein,
            carbs_g=carbs,
            fat_g=fat,
        )
        db.add(log)
    db.commit()
    print(f"완료: {path} 적재")


def normalize_name(raw: str) -> str:
    s = (raw or "").strip()
    # 괄호 내용 제거
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("  ", " ").strip()
    return s


SYNONYMS = {
    "소고기": "쇠고기",
    "닭안심": "닭가슴살",
    "알배추": "배추",
    "적채": "양배추",
    "양송이버섯": "양송이",
    "새송이버섯": "새송이",
}


def find_best_ingredient(db: Session, raw_name: str):
    name = normalize_name(raw_name)
    # 특수 케이스: '쌀죽'류는 죽 카테고리 검색
    if "쌀죽" in name or name == "쌀죽":
        cand = (
            db.query(models.Ingredient)
            .filter(
                models.Ingredient.name.ilike("%죽%"),
                or_(
                    models.Ingredient.name.ilike("%쌀%"),
                    models.Ingredient.name.ilike("%백미%"),
                ),
            )
            .first()
        )
        if cand:
            return cand

    # 동의어
    if name in SYNONYMS:
        name = SYNONYMS[name]

    # 1) 정확히 일치
    ing = db.query(models.Ingredient).filter(models.Ingredient.name == name).first()
    if ing:
        return ing

    # 2) 부분 일치
    ing = db.query(models.Ingredient).filter(models.Ingredient.name.ilike(f"%{name}%")).first()
    if ing:
        return ing

    # 3) 토큰 단위로 검색(마지막 토큰 우선)
    tokens = re.split(r"[\s,]", name)
    tokens = [t for t in tokens if t]
    for tok in reversed(tokens):
        ing = db.query(models.Ingredient).filter(models.Ingredient.name.ilike(f"%{tok}%")).first()
        if ing:
            return ing
    return None


def main() -> None:
    db = SessionLocal()
    try:
        for path in MEAL_FILES:
            load_file(db, path)
    finally:
        db.close()


if __name__ == "__main__":
    main()


