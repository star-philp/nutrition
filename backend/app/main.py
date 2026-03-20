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
        import openai
        try:
            top_recipe = top_predictions_with_recipe[0]
            # 상위 인식된 음식의 상세 영양 정보 (임시 계산)
            recipe_nutrition = calculate_nutrition_for_recipe(db, top_recipe["recipe_id"])
            
            user_context = f"""
            - 현재 인식된 음식: {top_recipe['recipe_name']}
            - 오늘 총 섭취량: 칼로리 {float(daily_totals[0])}kcal, 단백질 {float(daily_totals[1])}g, 탄수화물 {float(daily_totals[2])}g, 지방 {float(daily_totals[3])}g
            - 아기 정보: {user.allergies if user and user.allergies else '없음'} 알레르기 주의
            - 권장 기준: {DEFAULT_KDRI}
            """
            
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            guide_prompt = f"""
            당신은 영유아 영양 전문가입니다. 사용자가 방금 찍은 음식 사진과 오늘 하루 전체 섭취 상태를 바탕으로 따뜻하고 전문적인 조언을 해주세요.
            
            {user_context}
            
            [답변 가이드]
            1. 인식된 음식이 아기에게 어떤 영양적 도움을 주는지 설명해주세요.
            2. 오늘 부족한 영양소(예: 아연, 단백질 등)가 있다면 언급하고, 다음 식사로 무엇을 먹으면 좋을지 추천해주세요.
            3. 알레르기 정보가 있다면 반드시 주의 사항을 포함해주세요.
            4. 중요한 단어나 추천 메뉴는 반드시 '**단어**' 형식(볼드 처리)으로 작성해주세요. (예: **단백질**, **소고기 미음**)
            5. 한국어로 친절하게 2~3문장 내외로 작성해주세요.
            """
            
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "친절한 영아 영양 가이드입니다."}, {"role": "user", "content": guide_prompt}],
                temperature=0.7
            )
            ai_guide = resp.choices[0].message.content
        except Exception as e:
            print(f"AI Guide Generation Error: {e}")
            ai_guide = "영양 분석 중 오류가 발생했습니다."

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "predictions": top_predictions_with_recipe,
        "ai_guide": ai_guide
    }

# --- 새로운 영양 계산 헬퍼 함수 ---
def calculate_nutrition_for_recipe(db: Session, recipe_id: str) -> schemas.CalculatedNutrition:
    recipe_ingredients = db.query(models.RecipeIngredient).filter(models.RecipeIngredient.recipe_id == recipe_id).all()
    
    if not recipe_ingredients:
        raise HTTPException(status_code=404, detail="해당 레시피의 재료 정보를 찾을 수 없습니다.")

    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0

    for item in recipe_ingredients:
        # ingredient.calories_kcal는 Numeric(Decimal) 타입이므로 float으로 변환
        total_calories += (float(item.ingredient.calories_kcal) / 100) * item.quantity_grams
        total_protein += (float(item.ingredient.protein_g) / 100) * item.quantity_grams
        total_carbs += (float(item.ingredient.carbs_g) / 100) * item.quantity_grams
        total_fat += (float(item.ingredient.fat_g) / 100) * item.quantity_grams

    return schemas.CalculatedNutrition(
        calories_kcal=total_calories,
        protein_g=total_protein,
        carbs_g=total_carbs,
        fat_g=total_fat
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
        fat_g=calculated_fat
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
        )
        for row in results
    ]


# --- KDRI 프로필 기본값 (6-11개월, 2020) ---
DEFAULT_KDRI = {
    "energy_kcal": 700.0,   # 예시값: 실제 최신 기준으로 보정 필요
    "protein_g": 13.0,
    "carbs_g": 95.0,
    "fat_g": 30.0,
    "sodium_mg": 800.0,
}


@app.post("/api/v1/analysis/daily", response_model=schemas.DailyAnalysisResult)
def analyze_daily(request: schemas.DailyAnalysisRequest, db: Session = Depends(get_db)):
    """
    특정 사용자/특정 일자의 총 섭취량을 집계하고, KDRI 프로필 대비 충족률과 부족 여부를 반환합니다.
    """
    date_str = request.date
    kdri = request.kdri_profile.dict() if request.kdri_profile else DEFAULT_KDRI

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
        schemas.NutrientCoverage(name="에너지", total=total_cal, target=kdri["energy_kcal"], unit="kcal", coverage_pct=cov(total_cal, kdri["energy_kcal"]), deficiency=total_cal < kdri["energy_kcal"] * 0.8),
        schemas.NutrientCoverage(name="단백질", total=total_protein, target=kdri["protein_g"], unit="g", coverage_pct=cov(total_protein, kdri["protein_g"]), deficiency=total_protein < kdri["protein_g"] * 0.8),
        schemas.NutrientCoverage(name="탄수화물", total=total_carbs, target=kdri["carbs_g"], unit="g", coverage_pct=cov(total_carbs, kdri["carbs_g"]), deficiency=total_carbs < kdri["carbs_g"] * 0.8),
        schemas.NutrientCoverage(name="지방", total=total_fat, target=kdri["fat_g"], unit="g", coverage_pct=cov(total_fat, kdri["fat_g"]), deficiency=total_fat < kdri["fat_g"] * 0.8),
        schemas.NutrientCoverage(name="나트륨", total=total_sodium, target=kdri["sodium_mg"], unit="mg", coverage_pct=cov(total_sodium, kdri["sodium_mg"]), deficiency=total_sodium < kdri["sodium_mg"] * 0.8),
    ]

    return schemas.DailyAnalysisResult(totals=result_totals, coverages=coverages)