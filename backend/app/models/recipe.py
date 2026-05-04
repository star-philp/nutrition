from sqlalchemy import Column, String, Text, Numeric, Integer, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func # 기본 시간 설정을 위해
import datetime

from app.core.db import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    
    # 개인화 프로필 정보 추가
    birth_date = Column(DateTime, nullable=True) # 아기 생년월일
    weight_kg = Column(Float, nullable=True)    # 현재 몸무게
    allergies = Column(Text, nullable=True)     # 알레르기 유발 식품
    caution_ingredients = Column(Text, nullable=True) # 사용자가 직접 등록한 주의 식재료 (꿀 외 추가 관리용)
    
    meal_logs = relationship("MealLog", back_populates="user")

class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True, index=True)
    gov_food_code = Column(String(50), unique=True, index=True, nullable=True) # 정부 API의 FOOD_CD
    name = Column(String(100), nullable=False, index=True)
    description = Column(String(100), nullable=True) # 식품 분류 등
    
    # 100g 당 영양 정보
    calories_kcal = Column(Numeric(10, 2))
    carbs_g = Column(Numeric(10, 2))
    protein_g = Column(Numeric(10, 2))
    fat_g = Column(Numeric(10, 2))
    sugar_g = Column(Numeric(10, 2), nullable=True)
    sodium_mg = Column(Numeric(10, 2), nullable=True)
    cholesterol_mg = Column(Numeric(10, 2), nullable=True)
    saturated_fat_g = Column(Numeric(10, 2), nullable=True)
    trans_fat_g = Column(Numeric(10, 2), nullable=True)
    source = Column(String(50)) # 데이터 출처 (예: 식품의약품안전처)

    recipes = relationship("RecipeIngredient", back_populates="ingredient")

class Recipe(Base):
    __tablename__ = "recipes"

    recipe_id = Column(String(20), primary_key=True, index=True)
    recipe_name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(50), index=True)
    
    representative_image_path = Column(String(255))
    
    ingredients = relationship("RecipeIngredient", back_populates="recipe")
    meal_logs = relationship("MealLog", back_populates="recipe")

class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(String(20), ForeignKey("recipes.recipe_id"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), nullable=False)
    quantity_grams = Column(Float, nullable=False) # 레시피에 사용되는 재료의 양(g)

    recipe = relationship("Recipe", back_populates="ingredients")
    ingredient = relationship("Ingredient", back_populates="recipes")

class MealLog(Base):
    __tablename__ = "meal_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipe_id = Column(String(20), ForeignKey("recipes.recipe_id"), nullable=False)
    
    portion = Column(Numeric(4, 2), nullable=False) # 예: 1.0, 0.75, 0.5
    meal_time = Column(DateTime(timezone=True), server_default=func.now())
    
    # 계산된 최종 영양소
    calories_kcal = Column(Numeric(8, 2))
    protein_g = Column(Numeric(8, 2))
    carbs_g = Column(Numeric(8, 2))
    fat_g = Column(Numeric(8, 2))
    sugar_g = Column(Numeric(8, 2), default=0.0)
    sodium_mg = Column(Numeric(8, 2), default=0.0)
    cholesterol_mg = Column(Numeric(8, 2), default=0.0)
    saturated_fat_g = Column(Numeric(8, 2), default=0.0)
    trans_fat_g = Column(Numeric(8, 2), default=0.0)
    
    user = relationship("User", back_populates="meal_logs")
    recipe = relationship("Recipe", back_populates="meal_logs") 