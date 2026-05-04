from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime

# Recipe 스키마를 먼저 정의해야 MealLog에서 참조 가능
class RecipeBase(BaseModel):
    recipe_id: str
    recipe_name: str
    category: str

class Recipe(RecipeBase):
    description: Optional[str] = None
    representative_image_path: Optional[str] = None # 경로가 없을 수도 있으므로 Optional로 변경

    class Config:
        from_attributes = True

# 영양소 계산 요청을 위한 스키마
class NutritionCalculationRequest(BaseModel):
    recipe_id: str
    portion: float

# 계산된 영양소 응답을 위한 스키마
class CalculatedNutrition(BaseModel):
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    sugar_g: float = 0.0
    sodium_mg: float = 0.0
    cholesterol_mg: float = 0.0
    saturated_fat_g: float = 0.0
    trans_fat_g: float = 0.0

# --- 식단 일지(MealLog)를 위한 스키마 ---

class MealLogBase(BaseModel):
    recipe_id: str
    portion: float

class MealLogCreate(MealLogBase):
    pass

class MealLog(MealLogBase):
    id: int
    user_id: int
    meal_time: datetime
    # 계산된 영양소 필드 추가
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    sugar_g: float = 0.0
    sodium_mg: float = 0.0
    cholesterol_mg: float = 0.0
    saturated_fat_g: float = 0.0
    trans_fat_g: float = 0.0
    # 연관된 레시피 정보 포함
    recipe: RecipeBase

    class Config:
        from_attributes = True

# --- 사용자(User)를 위한 스키마 ---

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    pass # 지금은 간단하게 username만 받음

class User(UserBase):
    id: int
    birth_date: Optional[datetime] = None
    weight_kg: Optional[float] = None
    allergies: Optional[str] = None
    caution_ingredients: Optional[str] = None
    meal_logs: List[MealLog] = []

    class Config:
        from_attributes = True 

# --- 일일 합계 응답 스키마 ---
class DailyNutritionSummary(BaseModel):
    date: str
    total_calories_kcal: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    total_sugar_g: float = 0.0
    total_sodium_mg: float = 0.0
    total_cholesterol_mg: float = 0.0
    total_saturated_fat_g: float = 0.0
    total_trans_fat_g: float = 0.0

# --- KDRI 기반 분석 요청/응답 스키마 ---
class KDRIProfile(BaseModel):
    # 최소 필수: 에너지/3대영양소/나트륨
    energy_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    sodium_mg: float

class DailyAnalysisRequest(BaseModel):
    user_id: int
    date: str  # 'YYYY-MM-DD'
    kdri_profile: Optional[KDRIProfile] = None

class DailyNutrientTotals(BaseModel):
    date: str
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    sodium_mg: float
    sugar_g: float = 0.0
    cholesterol_mg: float = 0.0
    saturated_fat_g: float = 0.0
    trans_fat_g: float = 0.0

class NutrientCoverage(BaseModel):
    name: str
    total: float
    target: float
    unit: str
    coverage_pct: float
    deficiency: bool
    excess: bool = False

class DailyAnalysisResult(BaseModel):
    totals: DailyNutrientTotals
    coverages: Optional[List[NutrientCoverage]] = None