# 100g당 영양 정보 예시
# 실제 프로덕션에서는 농촌진흥청 식품영양성분 DB 등 공신력 있는 데이터를 사용해야 합니다.
initial_ingredients = [
    # 어제 웹 검색을 통해 찾은 신뢰성 있는 데이터로 업데이트
    # 100g당 영양 정보 (생것 기준)
    # 소고기 (우둔살), 브로콜리, 멥쌀, 닭가슴살, 단호박, 양파, 물
    {"id": 1, "name": "멥쌀", "calories_kcal": 358, "protein_g": 6.5, "carbs_g": 79.15, "fat_g": 0.5, "sodium_mg": 1}, # 나트륨은 기존 값 유지
    {"id": 2, "name": "소고기 (우둔살)", "calories_kcal": 132, "protein_g": 18, "carbs_g": 0, "fat_g": 6.1, "sodium_mg": 63}, # 나트륨은 기존 값 유지
    {"id": 3, "name": "브로콜리", "calories_kcal": 34, "protein_g": 2.82, "carbs_g": 6.64, "fat_g": 0.37, "sodium_mg": 33},
    {"id": 4, "name": "닭가슴살", "calories_kcal": 120, "protein_g": 22.5, "carbs_g": 0, "fat_g": 2.62, "sodium_mg": 74},
    {"id": 5, "name": "단호박", "calories_kcal": 40, "protein_g": 2.0, "carbs_g": 8.8, "fat_g": 0.5, "sodium_mg": 2},
    {"id": 6, "name": "양파", "calories_kcal": 40, "protein_g": 1.1, "carbs_g": 9.3, "fat_g": 0.1, "sodium_mg": 4}, # 기존 데이터 유지
    {"id": 7, "name": "물", "calories_kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "sodium_mg": 0} # 기존 데이터 유지
]

initial_recipes = [
    {
        "recipe_id": "BP001",
        "recipe_name": "소고기 브로콜리 죽",
        "description": "초기 이유식의 대표 메뉴, 소고기와 브로콜리로 영양을 듬뿍 담았습니다.",
        "category": "초기",
        "representative_image_path": "images/BP001.jpg"
    },
    {
        "recipe_id": "CP002",
        "recipe_name": "닭고기 단호박 퓌레",
        "description": "달콤한 단호박과 부드러운 닭가슴살이 어우러진 퓌레입니다.",
        "category": "중기",
        "representative_image_path": "images/CP002.jpg"
    }
]

# 레시피 구성 정보
initial_recipe_ingredients = [
    # 소고기 브로콜리 죽 (BP001) - 쌀 ID 1, 소고기 ID 2, 브로콜리 ID 3으로 변경
    {"recipe_id": "BP001", "ingredient_id": 1, "quantity_grams": 20.0}, # 쌀
    {"recipe_id": "BP001", "ingredient_id": 2, "quantity_grams": 15.0}, # 소고기
    {"recipe_id": "BP001", "ingredient_id": 3, "quantity_grams": 10.0}, # 브로콜리
    {"recipe_id": "BP001", "ingredient_id": 7, "quantity_grams": 300.0},# 물
    
    # 닭고기 단호박 퓌레 (CP002) - 닭가슴살 ID 4, 단호박 ID 5로 변경 (기존과 동일)
    {"recipe_id": "CP002", "ingredient_id": 4, "quantity_grams": 20.0}, # 닭가슴살
    {"recipe_id": "CP002", "ingredient_id": 5, "quantity_grams": 25.0}, # 단호박
    {"recipe_id": "CP002", "ingredient_id": 6, "quantity_grams": 5.0},  # 양파
    {"recipe_id": "CP002", "ingredient_id": 7, "quantity_grams": 200.0} # 물
]
