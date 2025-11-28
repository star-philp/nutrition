import logging
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.recipe import Recipe, Ingredient, RecipeIngredient
from app.initial_data import initial_recipes, initial_ingredients, initial_recipe_ingredients

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_data(db: Session) -> None:
    logger.info("데이터 시딩을 시작합니다...")

    # 1. Ingredients 데이터 시딩
    logger.info("식재료(Ingredients) 데이터 시딩 중...")
    for ingredient_data in initial_ingredients:
        db_ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_data["id"]).first()
        if not db_ingredient:
            new_ingredient = Ingredient(**ingredient_data)
            db.add(new_ingredient)
    db.commit() # 재료 추가 후 커밋

    # 2. Recipes 데이터 시딩
    logger.info("레시피(Recipes) 데이터 시딩 중...")
    for recipe_data in initial_recipes:
        db_recipe = db.query(Recipe).filter(Recipe.recipe_id == recipe_data["recipe_id"]).first()
        if not db_recipe:
            logger.info(f"'{recipe_data['recipe_name']}' 레시피를 추가합니다.")
            new_recipe = Recipe(**recipe_data)
            db.add(new_recipe)
        else:
            logger.info(f"'{recipe_data['recipe_name']}' 레시피는 이미 존재합니다.")
    db.commit() # 레시피 추가 후 커밋

    # 3. RecipeIngredients 데이터 시딩
    logger.info("레시피 구성(RecipeIngredients) 데이터 시딩 중...")
    for rel_data in initial_recipe_ingredients:
        db_rel = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == rel_data["recipe_id"],
            RecipeIngredient.ingredient_id == rel_data["ingredient_id"]
        ).first()
        if not db_rel:
            new_rel = RecipeIngredient(**rel_data)
            db.add(new_rel)
            
    db.commit()
    logger.info("데이터 시딩이 완료되었습니다.")

if __name__ == "__main__":
    db = SessionLocal()
    seed_data(db)
    db.close() 