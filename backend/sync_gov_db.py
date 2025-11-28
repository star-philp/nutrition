import os
import sys
import requests
import logging
from decimal import Decimal, InvalidOperation
import time

# 프로젝트 루트 경로를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.recipe import Ingredient

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SQLAlchemy 엔진 및 세션 설정
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"options": "-c client_encoding=utf8"}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

API_ENDPOINT = "http://apis.data.go.kr/1471000/FoodNtrCpntDbInfo02/getFoodNtrCpntDbInq02"
# 서비스키를 URL 인코딩합니다.
API_SERVICE_KEY = "pqApmovkluNvCD3xudS7N89p3iI1/6hwhU5hODfNXSRbx4tnjiCi+GElH+D57NwaaeFfh2w2LuLvvszL8liFNw==" # 원본 디코딩 키

def sync_ingredients_from_gov_api():
    db = SessionLocal()
    page_no = 1
    num_of_rows = 100  # 한 번에 가져올 데이터 수
    total_synced_count = 0
    total_updated_count = 0
    total_inserted_count = 0

    logger.info("정부 식품영양성분 DB 동기화를 시작합니다...")

    while True:
        # 매번 인코딩된 키를 사용하지 않고, requests가 처리하도록 원본 키를 전달합니다.
        # 공공데이터 포털의 많은 API는 인코딩된 키를 직접 URL에 넣으면 이중 인코딩 문제로 실패하고,
        # params로 전달하면 requests 라이브러리가 알아서 인코딩해주는 것이 더 안정적입니다.
        params = {
            "serviceKey": API_SERVICE_KEY,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows),
            "type": "json"
        }

        try:
            # 재시도 로직 추가
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    response = requests.get(API_ENDPOINT, params=params, timeout=30)
                    response.raise_for_status() # 200번대 상태 코드가 아닐 경우 예외 발생
                    break # 성공 시 루프 탈출
                except (requests.exceptions.RequestException, ConnectionResetError) as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"API 요청 오류 발생 (시도 {attempt + 1}/{max_retries}): {e}. 5초 후 재시도합니다.")
                        time.sleep(5)
                    else:
                        raise # 마지막 시도도 실패하면 예외를 다시 발생시킴
            
            # 일부 공공 API는 Content-Type 헤더가 json이 아니어도 json 응답을 주는 경우가 있어, 응답 텍스트를 직접 파싱 시도
            try:
                data = response.json()
            except requests.exceptions.JSONDecodeError:
                logger.error(f"JSON 디코딩 실패. 응답 내용: {response.text[:200]}")
                break

            # API 응답 구조를 더 안전하게 확인
            if "header" in data and data["header"]["resultCode"] == "00":
                if "body" in data and "items" in data["body"]:
                    items = data['body']['items']
                    if not items:
                        logger.info("더 이상 가져올 데이터가 없습니다. (마지막 페이지)")
                        break
                else:
                    logger.info("데이터 본문(body) 또는 아이템(items)이 없습니다. 마지막 페이지일 수 있습니다.")
                    break
                
                for item in items:
                    def to_decimal(value, default=Decimal('0.0')):
                        if value is None or value in ['N/A', '']:
                            return default
                        try:
                            return Decimal(str(value).replace(',', ''))
                        except (InvalidOperation, ValueError):
                            return default

                    ingredient_data = {
                        'gov_food_code': item.get("FOOD_CD"),
                        'name': item.get("DESC_KOR", "이름 없음"),
                        'description': item.get("GROUP_NAME", ""),
                        'calories_kcal': to_decimal(item.get("NUTR_CONT1")),
                        'carbs_g': to_decimal(item.get("NUTR_CONT2")),
                        'protein_g': to_decimal(item.get("NUTR_CONT3")),
                        'fat_g': to_decimal(item.get("NUTR_CONT4")),
                        'sugar_g': to_decimal(item.get("NUTR_CONT5")),
                        'sodium_mg': to_decimal(item.get("NUTR_CONT6")),
                        'cholesterol_mg': to_decimal(item.get("NUTR_CONT7")),
                        'saturated_fat_g': to_decimal(item.get("NUTR_CONT8")),
                        'trans_fat_g': to_decimal(item.get("NUTR_CONT9")),
                        'source': "식품의약품안전처"
                    }

                    # 데이터베이스에 UPSERT (gov_food_code 기준)
                    gov_code = ingredient_data.get('gov_food_code')
                    if not gov_code:
                        # FOOD_CD가 없는 데이터는 건너뜁니다.
                        continue

                    existing_ingredient = db.query(Ingredient).filter(Ingredient.gov_food_code == gov_code).first()
                    
                    if existing_ingredient:
                        # UPDATE
                        for key, value in ingredient_data.items():
                            setattr(existing_ingredient, key, value)
                        total_updated_count += 1
                    else:
                        # INSERT
                        new_ingredient = Ingredient(**ingredient_data)
                        db.add(new_ingredient)
                        total_inserted_count += 1
                
                total_synced_count += len(items)
                db.commit()
                logger.info(f"{page_no} 페이지 처리 완료. (총 {total_synced_count}개 동기화, {total_inserted_count}개 추가, {total_updated_count}개 업데이트)")
                page_no += 1
            else:
                error_code = data.get('header', {}).get('resultCode', 'N/A')
                error_msg = data.get('header', {}).get('resultMsg', 'Unknown Error')
                logger.error(f"API 오류 발생: 코드({error_code}), 메시지({error_msg})")
                break

        except requests.exceptions.RequestException as e:
            logger.error(f"네트워크 또는 API 요청 중 오류 발생: {e}")
            break
        except Exception as e:
            logger.error(f"데이터 처리 또는 DB 작업 중 오류 발생: {e}", exc_info=True)
            db.rollback()
            break
            
    db.close()
    logger.info(f"동기화 완료. 총 {total_inserted_count}개의 새로운 식재료를 추가하고, {total_updated_count}개의 식재료 정보를 업데이트했습니다.")

if __name__ == "__main__":
    sync_ingredients_from_gov_api()


