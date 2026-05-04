import os
import sys
import requests
import time
from math import ceil

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.db import SessionLocal
from app.core.config import settings
from app.models.recipe import Ingredient

# 식약처 API 기본 설정
# I2790: 식품영양성분 DB (전국 통합식품영양성분정보표준데이터)
MFDS_API_URL = "http://openapi.foodsafetykorea.go.kr/api/{key}/I2790/json/{start}/{end}"
MAX_ROWS_PER_REQ = 1000

def safe_float(val):
    if not val or val == 'N/A' or val == '-':
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0

def fetch_and_store_data(api_key: str, limit: int = None):
    db = SessionLocal()
    
    try:
        print(f"식약처 식품영양성분 연동 시작 (API Key 검증 중...)")
        
        # 전체 개수 파악을 위해 1건만 먼저 요청
        test_url = MFDS_API_URL.format(key=api_key, start=1, end=1)
        res = requests.get(test_url)
        
        if res.status_code != 200:
            print("API 서버 오류:", res.status_code)
            return
        
        data = res.json()
        if 'I2790' not in data:
            print("API 응답 구조 오류 또는 올바르지 않은 API 키입니다.")
            print(data)
            return

        total_count = int(data['I2790']['list_total_count'])
        print(f"식품영양성분 총 데이터 건수: {total_count}건")
        
        # 사용자가 테스트용으로 limit을 걸었다면 반영
        if limit and total_count > limit:
            total_count = limit
            print(f"테스트 목적으로 {limit}건만 가져옵니다.")

        pages = ceil(total_count / MAX_ROWS_PER_REQ)
        inserted_count = 0
        updated_count = 0

        for page in range(pages):
            start = page * MAX_ROWS_PER_REQ + 1
            end = min((page + 1) * MAX_ROWS_PER_REQ, total_count)
            
            print(f"데이터 조회 중... ({start} ~ {end}/{total_count})")
            req_url = MFDS_API_URL.format(key=api_key, start=start, end=end)
            response = requests.get(req_url)
            
            if response.status_code != 200:
                print(f"오류 발생 ({start}~{end}): HTTP {response.status_code}")
                time.sleep(1)
                continue
            
            items = response.json().get('I2790', {}).get('row', [])
            
            for item in items:
                # API 명세 구조
                # DESC_KOR: 식품이름, FOOD_CD: 코드, NUTR_CONT1: 열량, NUTR_CONT2: 탄수, ...
                food_cd = item.get('NUM', item.get('FOOD_CD', ''))
                name = item.get('DESC_KOR', '').strip()
                
                if not name:
                    continue
                
                # 기존 데이터 확인 (food_cd 및 name 기준)
                existing_item = db.query(Ingredient).filter(Ingredient.name == name).first()
                if not existing_item and food_cd:
                     existing_item = db.query(Ingredient).filter(Ingredient.gov_food_code == food_cd).first()

                # 영양성분 파싱 (100g/1회제공량 기준)
                cal = safe_float(item.get('NUTR_CONT1'))
                carbs = safe_float(item.get('NUTR_CONT2'))
                protein = safe_float(item.get('NUTR_CONT3'))
                fat = safe_float(item.get('NUTR_CONT4'))
                sugar = safe_float(item.get('NUTR_CONT5'))
                sodium = safe_float(item.get('NUTR_CONT6'))
                cholesterol = safe_float(item.get('NUTR_CONT7'))
                sat_fat = safe_float(item.get('NUTR_CONT8'))
                trans_fat = safe_float(item.get('NUTR_CONT9'))
                
                maker = item.get('MAKER_NAME', '')
                desc = f"제조사: {maker}" if maker else "기본(식약처 통합데이터)"

                if existing_item:
                    # Update
                    existing_item.calories_kcal = cal
                    existing_item.carbs_g = carbs
                    existing_item.protein_g = protein
                    existing_item.fat_g = fat
                    existing_item.sugar_g = sugar
                    existing_item.sodium_mg = sodium
                    existing_item.cholesterol_mg = cholesterol
                    existing_item.saturated_fat_g = sat_fat
                    existing_item.trans_fat_g = trans_fat
                    existing_item.source = "MFDS"
                    existing_item.gov_food_code = food_cd
                    updated_count += 1
                else:
                    # Insert
                    new_item = Ingredient(
                        name=name,
                        gov_food_code=food_cd,
                        description=desc,
                        calories_kcal=cal,
                        carbs_g=carbs,
                        protein_g=protein,
                        fat_g=fat,
                        sugar_g=sugar,
                        sodium_mg=sodium,
                        cholesterol_mg=cholesterol,
                        saturated_fat_g=sat_fat,
                        trans_fat_g=trans_fat,
                        source="MFDS"
                    )
                    db.add(new_item)
                    inserted_count += 1

            # 청크 단위 Commit 및 sleep (API Rate Limiting 방지)
            db.commit()
            time.sleep(0.5)
            
        print(f"완료! (신규: {inserted_count}건, 업데이트: {updated_count}건)")

    except Exception as e:
        print(f"실행 중 구조 에러: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if not settings.MFDS_API_KEY:
        print("====== 🛑 오류 🛑 ======")
        print(".env 파일에 'MFDS_API_KEY'가 설정되어 있지 않습니다.")
        print("식품안전나라(https://www.foodsafetykorea.go.kr)에서 API 키를 발급받아 환경변수에 추가해주세요.")
        print("예시: MFDS_API_KEY=당신의발급키")
        sys.exit(1)
        
    print("가져올 데이터 개수를 입력하세요 (숫자). 전체를 가져오려면 빈 칸으로 두고 Enter:")
    user_input = input("> ")
    limit_val = int(user_input) if user_input.isdigit() else None
    
    fetch_and_store_data(settings.MFDS_API_KEY, limit=limit_val)
