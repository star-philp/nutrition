from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import shutil
import os
import os
# 무거운 라이브러리들은 함수 내부에서 lazy import 하도록 변경하여 시작 속도를 높입니다.

from app.core.db import engine, Base, get_db
from app.models import recipe as models # Keep this for models.Recipe
from app.models.rag import KnowledgeChunk # Keep this for KnowledgeChunk
from app.models.analysis import AnalysisRecord # 추가
from app.schemas import recipe as schemas # Corrected this line
from app.api import analysis_routes, rag_routes, user_routes # 추가된 라우터들
from sqlalchemy import text, func, cast, Float
# Base.metadata.create_all(bind=engine) -> on_startup 내부로 이동하여 확장 기능 설치 후 실행되도록 합니다.

# 업로드된 파일을 저장할 디렉토리
UPLOAD_DIRECTORY = "./uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

# --- AI 모델 로딩 (지연 로딩 방식으로 변경) ---
# 경로를 프로젝트 루트 기준으로 수정합니다.
MODEL_PATH = "ml/model/food_classifier_model.h5"
CLASS_NAMES_PATH = "ml/model/class_names.txt"

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MODEL_PATH_ABS = os.path.join(PROJECT_ROOT, MODEL_PATH)
CLASS_NAMES_PATH_ABS = os.path.join(PROJECT_ROOT, CLASS_NAMES_PATH)

_model = None
_class_names = []

def get_model_and_classes():
    global _model, _class_names
    if _model is not None:
        return _model, _class_names
    
    try:
        import tensorflow as tf # Lazy import
        print("[INFO] AI 모델 로딩 시도 중... (메모리 사용량이 높을 수 있습니다)")
        # 메모리 제한이 있는 환경(Render 무료 티어 등)을 위해 로딩 시점 조절
        _model = tf.keras.models.load_model(MODEL_PATH_ABS)
        with open(CLASS_NAMES_PATH_ABS, 'r', encoding='utf-8') as f:
            _class_names = [line.strip() for line in f.readlines()]
        print("[INFO] AI 모델과 클래스 이름을 성공적으로 불러왔습니다.")
        return _model, _class_names
    except Exception as e:
        print(f"[ERROR] AI 모델 로딩 실패: {e}")
        print("[TIP] Render 무료 티어의 경우 메모리 부족(512MB)으로 로딩이 실패할 수 있습니다.")
        return None, []
# --------------------


app = FastAPI()

# --- CORS 설정 ---
from app.core.config import settings
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:5174",
    settings.FRONTEND_URL,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 라우터 등록 (중복 제거) ---
app.include_router(analysis_routes.router)
app.include_router(rag_routes.router)
app.include_router(user_routes.router)

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/api/v1/recipes", response_model=List[schemas.Recipe])
def read_recipes(db: Session = Depends(get_db)):
    """
    모든 레시피 목록을 반환합니다.
    """
    recipes = db.query(models.Recipe).all()
    return recipes



# 이미지 전처리 함수
def preprocess_image(image_bytes: bytes):
    """업로드된 이미지를 모델 입력에 맞게 전처리합니다."""
    import numpy as np
    import tensorflow as tf
    from PIL import Image
    import io
    
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize((224, 224))
    img_array = tf.keras.preprocessing.image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0) # 배치 차원 추가
    img_array /= 255.0 # 정규화
    return img_array

@app.post("/api/v1/predict")
async def predict_image(db: Session = Depends(get_db), file: UploadFile = File(...)):
    """
    업로드된 이미지를 받아, 훈련된 AI 모델로 예측하고 결과를 반환합니다.
    """
    model, class_names = get_model_and_classes()
    if not model or not class_names:
        raise HTTPException(status_code=503, detail="AI 모델을 불러오지 못했습니다. 서버 메모리가 부족할 가능성이 큽니다.")

    # 파일 내용을 바이트로 읽기
    contents = await file.read()

    # 이미지 전처리
    processed_image = preprocess_image(contents)

    # 예측 수행
    predictions = model.predict(processed_image)[0] # 첫 번째 (그리고 유일한) 결과 사용

    # 예측 결과를 (클래스 이름, 확률) 쌍으로 변환
    prediction_results = []
    for i, score in enumerate(predictions):
        prediction_results.append({"class_name": class_names[i], "score": float(score)})
    
    # 확률 순으로 정렬
    prediction_results.sort(key=lambda x: x["score"], reverse=True)

    # 데이터베이스에서 레시피 정보 가져오기
    # 모델의 클래스 이름이 레시피 이름과 일치한다고 가정합니다.
    # 예: '소고기_브로콜리_죽' -> '소고기 브로콜리 죽'
    top_predictions_with_recipe = []
    for pred in prediction_results:
        recipe_name_in_db = pred["class_name"].replace('_', ' ')
        recipe = db.query(models.Recipe).filter(models.Recipe.recipe_name == recipe_name_in_db).first()
        
        if recipe:
            top_predictions_with_recipe.append({
                "recipe_id": recipe.recipe_id,
                "recipe_name": recipe.recipe_name,
                "score": pred["score"]
            })
        else:
            # 2차 검색: 식약처 Ingredient 데이터베이스 조회 (퍼지 검색)
            ingredient = db.query(models.Ingredient).filter(models.Ingredient.name.ilike(f"%{recipe_name_in_db}%")).first()
            if ingredient:
                top_predictions_with_recipe.append({
                    "recipe_id": f"ing_{ingredient.id}",
                    "recipe_name": ingredient.name,
                    "score": pred["score"]
                })
            else:
                # DB에 없는 경우에도 최소한의 정보는 반환
                top_predictions_with_recipe.append({
                    "recipe_id": "unknown",
                    "recipe_name": recipe_name_in_db,
                    "score": pred["score"]
                })
    
    # 상위 3개만 유지
    top_predictions_with_recipe = top_predictions_with_recipe[:3]
        
    # 1인분 기준 영양 정보 및 오늘의 섭취 상태 조회 (개인화 가이드용)
    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # 1. 오늘의 총 섭취량 조회 (기존 analyze_daily 로직 활용)
    # (여기서는 간단히 합계만 가져옴)
    daily_totals = db.query(
        func.coalesce(func.sum(models.MealLog.calories_kcal), 0),
        func.coalesce(func.sum(models.MealLog.protein_g), 0),
        func.coalesce(func.sum(models.MealLog.carbs_g), 0),
        func.coalesce(func.sum(models.MealLog.fat_g), 0),
    ).filter(
        models.MealLog.user_id == 1,
        func.to_char(models.MealLog.meal_time, 'YYYY-MM-DD') == today_str
    ).one()
    
    # 2. 사용자 프로필 및 알레르기 정보 조회
    user = db.query(models.User).filter(models.User.id == 1).first()
    
    # 3. AI 맞춤형 가이드 생성 (OpenAI 연동)
    ai_guide = "영양 가이드를 생성할 수 없습니다."
    from app.core.config import settings
    if settings.OPENAI_API_KEY and top_predictions_with_recipe:
        try:
            top_recipe = top_predictions_with_recipe[0]
            
            # MAS 파이프라인에 주입할 데이터 정리
            nutrition_data = {} # API에서 이미 calculate 된 것은 없으므로 추후 고도화 가능
            
            daily_totals_dict = {
                'calories': float(daily_totals[0]),
                'protein': float(daily_totals[1]),
                'carbs': float(daily_totals[2]),
                'fat': float(daily_totals[3])
            }
            
            user_allergies = user.allergies if user and user.allergies else ''
            user_caution = user.caution_ingredients if user and user.caution_ingredients else ''
            age_months = calculate_age_months(user.birth_date) if user else 9
            kdri = get_kdri_by_age(age_months)
            
            # 새로 만든 Multi-Agent System 오케스트레이터 호출
            from app.agents.mas_orchestrator import run_mas_scenario
            
            ai_guide = run_mas_scenario(
                recipe_name=top_recipe['recipe_name'],
                nutrition_data=nutrition_data,
                daily_totals=daily_totals_dict,
                kdri=kdri,
                age_months=age_months,
                allergies=user_allergies,
                caution_ingredients=user_caution,
                api_key=settings.OPENAI_API_KEY
            )
            
        except Exception as e:
            print(f"[MAS] 통합 에이전트 실행 중 오류: {e}")
            ai_guide = "에이전트 통합 분석 중 오류가 발생했습니다."

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "predictions": top_predictions_with_recipe,
        "ai_guide": ai_guide
    }

# --- 새로운 영양 계산 헬퍼 함수 ---
def calculate_nutrition_for_recipe(db: Session, recipe_id: str) -> schemas.CalculatedNutrition:
    # 1) 식약처 기본 데이터(Ingredient) 직접 조회 처리 ("ing_" 접두사)
    if recipe_id.startswith("ing_"):
        ing_id = int(recipe_id.replace("ing_", ""))
        ingredient = db.query(models.Ingredient).filter(models.Ingredient.id == ing_id).first()
        if not ingredient:
            raise HTTPException(status_code=404, detail="해당 식약처 데이터를 찾을 수 없습니다.")
        return schemas.CalculatedNutrition(
            calories_kcal=float(ingredient.calories_kcal or 0),
            protein_g=float(ingredient.protein_g or 0),
            carbs_g=float(ingredient.carbs_g or 0),
            fat_g=float(ingredient.fat_g or 0),
            sugar_g=float(ingredient.sugar_g or 0),
            sodium_mg=float(ingredient.sodium_mg or 0),
            cholesterol_mg=float(ingredient.cholesterol_mg or 0),
            saturated_fat_g=float(ingredient.saturated_fat_g or 0),
            trans_fat_g=float(ingredient.trans_fat_g or 0)
        )

    # 2) 복합 레시피(Recipe) 기반 처리
    recipe_ingredients = db.query(models.RecipeIngredient).filter(models.RecipeIngredient.recipe_id == recipe_id).all()
    
    if not recipe_ingredients:
        raise HTTPException(status_code=404, detail="해당 레시피의 재료 정보를 찾을 수 없습니다.")

    total_calories, total_protein, total_carbs, total_fat = 0, 0, 0, 0
    total_sugar, total_sodium, total_cholesterol, total_sat_fat, total_trans_fat = 0, 0, 0, 0, 0

    for item in recipe_ingredients:
        ratio = item.quantity_grams / 100.0
        total_calories += float(item.ingredient.calories_kcal or 0) * ratio
        total_protein += float(item.ingredient.protein_g or 0) * ratio
        total_carbs += float(item.ingredient.carbs_g or 0) * ratio
        total_fat += float(item.ingredient.fat_g or 0) * ratio
        total_sugar += float(item.ingredient.sugar_g or 0) * ratio
        total_sodium += float(item.ingredient.sodium_mg or 0) * ratio
        total_cholesterol += float(item.ingredient.cholesterol_mg or 0) * ratio
        total_sat_fat += float(item.ingredient.saturated_fat_g or 0) * ratio
        total_trans_fat += float(item.ingredient.trans_fat_g or 0) * ratio

    return schemas.CalculatedNutrition(
        calories_kcal=total_calories,
        protein_g=total_protein,
        carbs_g=total_carbs,
        fat_g=total_fat,
        sugar_g=total_sugar,
        sodium_mg=total_sodium,
        cholesterol_mg=total_cholesterol,
        saturated_fat_g=total_sat_fat,
        trans_fat_g=total_trans_fat
    )


@app.post("/api/v1/nutrition/calculate", response_model=schemas.CalculatedNutrition)
def calculate_nutrition(request: schemas.NutritionCalculationRequest, db: Session = Depends(get_db)):
    """
    레시피 ID와 섭취량을 받아, 동적으로 계산된 최종 영양 정보를 반환합니다.
    """
    # 1인분 기준 영양 정보 계산
    base_nutrition = calculate_nutrition_for_recipe(db, request.recipe_id)
    
    # 섭취량(portion) 적용
    final_nutrition = schemas.CalculatedNutrition(
        calories_kcal=base_nutrition.calories_kcal * request.portion,
        protein_g=base_nutrition.protein_g * request.portion,
        carbs_g=base_nutrition.carbs_g * request.portion,
        fat_g=base_nutrition.fat_g * request.portion,
        sugar_g=base_nutrition.sugar_g * request.portion,
        sodium_mg=base_nutrition.sodium_mg * request.portion,
        cholesterol_mg=base_nutrition.cholesterol_mg * request.portion,
        saturated_fat_g=base_nutrition.saturated_fat_g * request.portion,
        trans_fat_g=base_nutrition.trans_fat_g * request.portion,
    )
    
    return final_nutrition

# --- 초기 데이터 생성 로직 ---
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 애플리케이션 시작 시 실행될 로직
    from app.core.db import SessionLocal
    from sqlalchemy import text
    from app.initial_data import initial_recipes, initial_ingredients, initial_recipe_ingredients
    
    db = SessionLocal()
    try:
        print("[INFO] DB 초기화 시작...")
        # 1. pgvector 확장기능 활성화
        try:
            db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            db.commit()
            print("[INFO] pgvector 확장 기능 활성화 완료.")
        except Exception as e:
            print(f"[WARNING] pgvector 활성화 실패 (권한 문제일 수 있음): {e}")

        # 2. 테이블 생성
        try:
            Base.metadata.create_all(bind=engine)
            print("[INFO] DB 테이블 생성/확인 완료.")
        except Exception as e:
            print(f"[ERROR] 테이블 생성 실패: {e}")

        # 3. 초기 데이터 삽입
        try:
            if db.query(models.Ingredient).count() == 0:
                print("[INFO] 초기 식재료 데이터 삽입 중...")
                for ing_data in initial_ingredients:
                    db.add(models.Ingredient(**ing_data))
                db.commit()
                print("[INFO] 식재료 데이터 삽입 완료.")

            if db.query(models.Recipe).count() == 0:
                print("[INFO] 초기 레시피 데이터 삽입 중...")
                for r_data in initial_recipes:
                    db.add(models.Recipe(**r_data))
                db.commit()
                print("[INFO] 레시피 데이터 삽입 완료.")

            if db.query(models.RecipeIngredient).count() == 0:
                print("[INFO] 초기 레시피 구성 데이터 삽입 중...")
                for ri_data in initial_recipe_ingredients:
                    db.add(models.RecipeIngredient(**ri_data))
                db.commit()
                print("[INFO] 레시피 구성 데이터 삽입 완료.")

            if db.query(models.User).count() == 0:
                print("[INFO] 테스트 사용자 생성 중...")
                db.add(models.User(id=1, username="testuser"))
                db.commit()
                print("[INFO] 테스트 사용자 생성 완료.")
                
        except Exception as e:
            print(f"[ERROR] 초기 데이터 삽입 중 오류 발생: {e}")
            db.rollback()

    finally:
        db.close()
    
    print("[INFO] 애플리케이션 시작 준비 완료!")
    yield
    # 애플리케이션 종료 시 실행될 로직 (필요시)

# FastAPI 인스턴스에 lifespan 적용
app.router.lifespan_context = lifespan

@app.post("/api/v1/meal-logs/", response_model=schemas.MealLog)
def create_meal_log(
    meal_log_data: schemas.MealLogCreate, 
    db: Session = Depends(get_db)
):
    """
    새로운 식단 기록을 생성합니다.
    (현재는 user_id=1인 테스트 사용자에게 귀속됩니다)
    """
    # 섭취 영양소 계산 (새로운 헬퍼 함수 사용)
    base_nutrition = calculate_nutrition_for_recipe(db, meal_log_data.recipe_id)

    calculated_calories = base_nutrition.calories_kcal * meal_log_data.portion
    calculated_protein = base_nutrition.protein_g * meal_log_data.portion
    calculated_carbs = base_nutrition.carbs_g * meal_log_data.portion
    calculated_fat = base_nutrition.fat_g * meal_log_data.portion

    # 데이터베이스 모델 객체 생성
    db_meal_log = models.MealLog(
        user_id=1,  # 임시로 user_id 1 사용
        recipe_id=meal_log_data.recipe_id,
        portion=meal_log_data.portion,
        calories_kcal=calculated_calories,
        protein_g=calculated_protein,
        carbs_g=calculated_carbs,
        fat_g=calculated_fat,
        sugar_g=base_nutrition.sugar_g * meal_log_data.portion,
        sodium_mg=base_nutrition.sodium_mg * meal_log_data.portion,
        cholesterol_mg=base_nutrition.cholesterol_mg * meal_log_data.portion,
        saturated_fat_g=base_nutrition.saturated_fat_g * meal_log_data.portion,
        trans_fat_g=base_nutrition.trans_fat_g * meal_log_data.portion
    )
    
    db.add(db_meal_log)
    db.commit()
    db.refresh(db_meal_log)
    
    return db_meal_log

@app.get("/api/v1/users/{user_id}/meal-logs/", response_model=List[schemas.MealLog])
def read_user_meal_logs(user_id: int, db: Session = Depends(get_db)):
    """
    특정 사용자의 모든 식단 기록을 조회합니다.
    """
    meal_logs = db.query(models.MealLog).filter(models.MealLog.user_id == user_id).order_by(models.MealLog.meal_time.desc()).all()
    return meal_logs 

@app.get("/api/v1/users/{user_id}/daily-summary", response_model=List[schemas.DailyNutritionSummary])
def read_daily_summary(user_id: int, db: Session = Depends(get_db)):
    """
    특정 사용자의 일자별 총 섭취 영양 합계를 반환합니다.
    """
    results = (
        db.query(
            func.to_char(models.MealLog.meal_time, 'YYYY-MM-DD').label('date'),
            func.sum(models.MealLog.calories_kcal).label('total_calories_kcal'),
            func.sum(models.MealLog.protein_g).label('total_protein_g'),
            func.sum(models.MealLog.carbs_g).label('total_carbs_g'),
            func.sum(models.MealLog.fat_g).label('total_fat_g'),
            func.sum(models.MealLog.sugar_g).label('total_sugar_g'),
            func.sum(models.MealLog.sodium_mg).label('total_sodium_mg'),
            func.sum(models.MealLog.cholesterol_mg).label('total_cholesterol_mg'),
            func.sum(models.MealLog.saturated_fat_g).label('total_saturated_fat_g'),
            func.sum(models.MealLog.trans_fat_g).label('total_trans_fat_g'),
        )
        .filter(models.MealLog.user_id == user_id)
        .group_by(func.to_char(models.MealLog.meal_time, 'YYYY-MM-DD'))
        .order_by(func.to_char(models.MealLog.meal_time, 'YYYY-MM-DD').desc())
        .all()
    )

    return [
        schemas.DailyNutritionSummary(
            date=row[0],
            total_calories_kcal=float(row[1] or 0),
            total_protein_g=float(row[2] or 0),
            total_carbs_g=float(row[3] or 0),
            total_fat_g=float(row[4] or 0),
            total_sugar_g=float(row[5] or 0),
            total_sodium_mg=float(row[6] or 0),
            total_cholesterol_mg=float(row[7] or 0),
            total_saturated_fat_g=float(row[8] or 0),
            total_trans_fat_g=float(row[9] or 0),
        )
        for row in results
    ]


# --- KDRI 계산 유틸리티 (2020 한국인 영양소 섭취기준 적용) ---
def calculate_age_months(birth_date) -> int:
    if not birth_date:
        return 9 # 생년월일 없을 경우 기본 9개월(6-11개월 구간)로 가정
    from datetime import datetime
    today = datetime.now()
    delta = today - birth_date
    return delta.days // 30

def get_kdri_by_age(age_months: int) -> dict:
    # 0-5개월
    if age_months < 6:
        return {
            "energy_kcal": 550.0,
            "protein_g": 9.0,
            "carbs_g": 60.0,
            "fat_g": 30.0,
            "sodium_mg": 110.0,
        }
    # 6-11개월
    elif age_months < 12:
        return {
            "energy_kcal": 700.0,
            "protein_g": 13.0,
            "carbs_g": 95.0,
            "fat_g": 30.0,
            "sodium_mg": 810.0,
        }
    # 1-2세 (12-24개월+)
    elif age_months < 36:
        return {
            "energy_kcal": 1000.0,
            "protein_g": 20.0,
            "carbs_g": 130.0,
            "fat_g": 30.0,
            "sodium_mg": 810.0,
        }
    # 3-5세 이상 (확장 가능)
    else:
        return {
            "energy_kcal": 1400.0,
            "protein_g": 25.0,
            "carbs_g": 200.0,
            "fat_g": 45.0,
            "sodium_mg": 1000.0,
        }

DEFAULT_KDRI = get_kdri_by_age(9)


@app.post("/api/v1/analysis/daily", response_model=schemas.DailyAnalysisResult)
def analyze_daily(request: schemas.DailyAnalysisRequest, db: Session = Depends(get_db)):
    """
    특정 사용자/특정 일자의 총 섭취량을 집계하고, KDRI 프로필 대비 충족률과 부족 여부를 반환합니다.
    """
    date_str = request.date
    
    # 1. 사용자 월령 기반 KDRI 자동 결정
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    age_months = calculate_age_months(user.birth_date) if user else 9
    kdri = request.kdri_profile.dict() if request.kdri_profile else get_kdri_by_age(age_months)

    # 일자 범위 계산 (00:00~23:59)
    # PostgreSQL에서 날짜 문자열 비교를 위해 to_char 사용
    totals = (
        db.query(
            func.coalesce(func.sum(models.MealLog.calories_kcal), 0),
            func.coalesce(func.sum(models.MealLog.protein_g), 0),
            func.coalesce(func.sum(models.MealLog.carbs_g), 0),
            func.coalesce(func.sum(models.MealLog.fat_g), 0),
        )
        .filter(
            models.MealLog.user_id == request.user_id,
            func.to_char(models.MealLog.meal_time, 'YYYY-MM-DD') == date_str,
        )
        .one()
    )

    # 나트륨은 레시피 구성/재료를 통해 동적 합산
    total_cal, total_protein, total_carbs, total_fat = [float(x or 0) for x in totals]
    sodium_total_query = (
        db.query(
            func.coalesce(
                func.sum(
                    cast(models.MealLog.portion, Float)
                    * (
                        (cast(func.coalesce(models.Ingredient.sodium_mg, 0), Float) / 100.0)
                        * cast(models.RecipeIngredient.quantity_grams, Float)
                    )
                ),
                0.0,
            )
        )
        .join(
            models.RecipeIngredient,
            models.RecipeIngredient.recipe_id == models.MealLog.recipe_id,
        )
        .join(
            models.Ingredient,
            models.Ingredient.id == models.RecipeIngredient.ingredient_id,
        )
        .filter(
            models.MealLog.user_id == request.user_id,
            func.to_char(models.MealLog.meal_time, 'YYYY-MM-DD') == date_str,
        )
    )
    total_sodium = float(sodium_total_query.scalar() or 0.0)

    result_totals = schemas.DailyNutrientTotals(
        date=date_str,
        calories_kcal=total_cal,
        protein_g=total_protein,
        carbs_g=total_carbs,
        fat_g=total_fat,
        sodium_mg=total_sodium,
    )

    def cov(total: float, target: float) -> float:
        if target <= 0:
            return 0.0
        return max(0.0, min(200.0, round((total / target) * 100.0, 1)))

    coverages = [
        schemas.NutrientCoverage(
            name="에너지", total=total_cal, target=kdri["energy_kcal"], unit="kcal", 
            coverage_pct=cov(total_cal, kdri["energy_kcal"]), 
            deficiency=total_cal < kdri["energy_kcal"] * 0.8,
            excess=total_cal > kdri["energy_kcal"] * 1.5
        ),
        schemas.NutrientCoverage(
            name="단백질", total=total_protein, target=kdri["protein_g"], unit="g", 
            coverage_pct=cov(total_protein, kdri["protein_g"]), 
            deficiency=total_protein < kdri["protein_g"] * 0.8,
            excess=total_protein > kdri["protein_g"] * 2.0
        ),
        schemas.NutrientCoverage(
            name="탄수화물", total=total_carbs, target=kdri["carbs_g"], unit="g", 
            coverage_pct=cov(total_carbs, kdri["carbs_g"]), 
            deficiency=total_carbs < kdri["carbs_g"] * 0.8,
            excess=total_carbs > kdri["carbs_g"] * 2.0
        ),
        schemas.NutrientCoverage(
            name="지방", total=total_fat, target=kdri["fat_g"], unit="g", 
            coverage_pct=cov(total_fat, kdri["fat_g"]), 
            deficiency=total_fat < kdri["fat_g"] * 0.8,
            excess=total_fat > kdri["fat_g"] * 2.0
        ),
        schemas.NutrientCoverage(
            name="나트륨", total=total_sodium, target=kdri["sodium_mg"], unit="mg", 
            coverage_pct=cov(total_sodium, kdri["sodium_mg"]), 
            deficiency=total_sodium < kdri["sodium_mg"] * 0.5, # 나트륨은 부족 판단 완화
            excess=total_sodium > kdri["sodium_mg"] * 1.2 # 나트륨은 120%만 넘어도 과다 표시
        ),
    ]

    return schemas.DailyAnalysisResult(totals=result_totals, coverages=coverages)

if __name__ == "__main__":
    import uvicorn
    # 직접 실행 시 포트 8080으로 실행되도록 설정
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)