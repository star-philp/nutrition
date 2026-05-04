import openai
import json
import asyncio

def call_openai_agent(api_key: str, system_prompt: str, user_prompt: str, model="gpt-4o-mini") -> str:
    """단일 에이전트 역할을 수행하는 공통 OpenAI 호출 함수"""
    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Agent API 호출 오류: {e}")
        return f"오류 발생: {e}"

# 비동기로 동시에 안전/영양 관련 처리를 하는 것도 가능하지만, 
# 각 에이전트의 출력이 또 다른 에이전트의 입력으로 쓰여야 하므로 순차 및 병렬 구조를 섞습니다.

def run_mas_scenario(recipe_name: str, nutrition_data: dict, daily_totals: dict, kdri: dict, age_months: int, allergies: str, caution_ingredients: str, api_key: str) -> str:
    """
    4개의 에이전트를 오케스트레이션하여 최종 결과를 만듭니다.
    """
    
    # 공통 컨텍스트 포맷팅
    context = f"""
[상황정보]
- 아이 월령: {age_months}개월
- 인식된 음식: {recipe_name}
- 오늘 총 섭취량: 칼로리 {daily_totals.get('calories', 0)}kcal, 단백질 {daily_totals.get('protein', 0)}g, 탄수화물 {daily_totals.get('carbs', 0)}g, 지방 {daily_totals.get('fat', 0)}g
- 권장 기준(KDRI): 칼로리 {kdri.get('energy_kcal', 0)}kcal, 단백질 {kdri.get('protein_g', 0)}g, 나트륨 {kdri.get('sodium_mg', 0)}mg
- 알레르기 수첩: {allergies if allergies else '특이사항 없음'}
- 사용자 등록 주의 식재료: {caution_ingredients if caution_ingredients else '없음'}
"""

    print(f"🚀 [MAS ORCHESTRATOR] 에이전트 워크플로우 시작 (월령: {age_months}개월)...")

    # 1. 영양 분석 에이전트 (Nutrition Agent)
    print("   -> 🧑‍⚕️ 영양 에이전트 호출 중...")
    nutrition_sys = "당신은 영유아 영양 성분을 분석하는 전문 임상 영양사입니다."
    nutrition_prompt = f"{context}\n\n질문: 권장량(KDRI) 대비 현재 영양소 상태를 분석해주세요. 나트륨 과다 섭취 여부를 특히 주의 깊게 봐주세요."
    nutrition_result = call_openai_agent(api_key, nutrition_sys, nutrition_prompt)


    # 2. 안전/병리 에이전트 (Safety Agent)
    print("   -> 🚨 안전 에이전트 호출 중...")
    safety_sys = """당신은 소아 알레르기와 식품 안전을 검증하는 전문의사입니다. 
다음의 엄격한 안전 규칙을 적용하세요:
1. 꿀(Honey): 12개월(돌) 미만 영아에게는 보툴리누스균 위험으로 절대 금지입니다.
2. 나트륨/당분: 영유아에게는 매우 낮게 유지해야 합니다.
3. 질식 위험: 견과류 통째로, 포도 통째로 등은 위험합니다.
4. 사용자가 등록한 알레르기 성분은 최우선으로 경고하세요."""

    safety_prompt = f"{context}\n\n질문: 아이의 월령({age_months}개월)과 알레르기 정보를 바탕으로, 음식({recipe_name})이 의학적으로 안전한지 짧고 단호하게 평가해주세요."
    safety_result = call_openai_agent(api_key, safety_sys, safety_prompt)

    
    # 3. 추천 에이전트 (Recommendation Agent)
    print("   -> 👩‍🍳 식단 추천 에이전트 호출 중...")
    rec_sys = "당신은 영유아 전문 식단 플래너입니다."
    rec_prompt = f"""
{context}

[영양사의 분석]
{nutrition_result}

[전문의의 경고]
{safety_result}

질문: 영양사의 분석(부족한 영양소)과 의사의 경고(피해야 할 성분)를 모두 고려하여, **다음 끼니 거나 간식으로 먹이면 완벽할 식재료 2개와 그 이유**를 추천해주세요.
"""
    rec_result = call_openai_agent(api_key, rec_sys, rec_prompt)


    # 4. 메인 오케스트레이터 (Synthesis Agent)
    print("   -> ✍️ 종합 오케스트레이터 가공 중...")
    orchestrator_sys = "당신은 사용자(부모님)에게 이 어플리케이션의 최종 답변을 전달하는 메인 AI 닥터입니다. 매우 따뜻하고 친절하며 격려하는 톤으로 말합니다."
    orchestrator_prompt = f"""
당신 산하의 3명의 전문가가 의견을 가져왔습니다. 이 의견들을 부모님이 읽기 좋게 하나의 아름다운 글로 종합해주세요.

[영양사 의견]
{nutrition_result}

[전문의 의견]
{safety_result}

[식단 플래너 추천]
{rec_result}

[최종 답변 작성 가이드]
- 첫인사 없이 바로 따뜻한 조언으로 시작합니다.
- 알레르기 경고가 있다면 가장 중요하게(빨간색 느낌표처럼) 언급해주세요.
- 영양 상태 분석을 알기 쉽게 짚어주고, 추천 식단을 제안합니다.
- 중요한 키워드(식재료, 영양소)는 반드시 **단어** 처럼 볼드(Bold) 마크다운 처리를 해주세요.
- 너무 길지 않게 3~4문단으로 깔끔하게 작성해주세요.
"""
    final_synthesis = call_openai_agent(api_key, orchestrator_sys, orchestrator_prompt)

    print("✅ [MAS ORCHESTRATOR] 에이전트 통합 완료!")
    
    return final_synthesis
