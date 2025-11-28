# backend/search_ingredient_code.py
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 프로젝트의 루트 디렉토리를 sys.path에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# backend 폴더의 .env 파일을 명시적으로 로드
dotenv_path = os.path.join(project_root, 'backend', '.env')
load_dotenv(dotenv_path=dotenv_path)

from backend.app.core.config import settings
from backend.app.models.recipe import Ingredient

def see_the_data_offset():
    """
    DB의 중간 부분(10만 번째)부터 20개 식재료를 가져와 내용을 확인합니다.
    """
    db_url = settings.DATABASE_URL
    print(f"--- DB 데이터 직접 조회 (OFFSET 100000) ---")
    
    engine = create_engine(
        db_url,
        connect_args={"options": "-c client_encoding=utf8"}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # OFFSET을 사용하여 데이터의 중간 부분부터 조회
        ingredients = db.query(Ingredient).order_by(Ingredient.id).limit(20).offset(100000).all()

        if not ingredients:
            print("=> 해당 위치에 데이터가 없습니다.")
            return

        print("=> 데이터베이스에 저장된 식재료 이름 (100,001번째부터 20개):")
        for item in ingredients:
            print(f"  - 코드: {item.gov_food_code}, 이름: {item.name}")

    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        db.close()
        print(f"-----------------------------------------\n")

if __name__ == "__main__":
    see_the_data_offset()
