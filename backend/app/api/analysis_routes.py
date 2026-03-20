from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.services.analysis_service import AnalysisService, IAnalyzer
from app.models.analysis import AnalysisRecord
from app.core.config import settings
import openai
import os
import shutil
import pandas as pd
from pypdf import PdfReader

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])

# Concrete OpenAI Analyzer implementation (O: Open-Closed)
class OpenAIAnalyzer(IAnalyzer):
    async def analyze(self, file_path: str) -> dict:
        if not settings.OPENAI_API_KEY:
            return {"error": "OpenAI API Key not set"}
        
        filename = os.path.basename(file_path).lower()
        content_preview = ""

        try:
            # 1. 파일 타입에 따른 텍스트 추출
            if filename.endswith(".pdf"):
                reader = PdfReader(file_path)
                # 처음 3페이지만 요약에 사용 (성능/비용 고려)
                text_list = []
                for i in range(min(len(reader.pages), 3)):
                    text_list.append(reader.pages[i].extract_text())
                content_preview = "\n".join(text_list)[:3000]
            elif filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(file_path)
                # 상위 10개 행만 텍스트화
                content_preview = df.head(10).to_string()
            else:
                content_preview = "지원되지 않는 파일 형식입니다. 파일명만으로 분석합니다."

            # 2. OpenAI를 통한 실제 내용 요약
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            
            prompt = f"""
            파일명: {filename}
            파일 내용(일부): 
            {content_preview}
            
            위 파일의 내용을 분석해서 다음 형식으로 한국어로 요약해줘:
            1. 파일의 주요 주제
            2. 핵심 데이터나 영양학적 시사점 (있는 경우)
            3. 이 파일을 어떻게 활용하면 좋을지에 대한 제안
            
            답변은 3~5문장 내외로 간결하게 작성해줘.
            """

            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 영유아 영양 및 문서 분석 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            summary = resp.choices[0].message.content
            return {
                "summary": summary, 
                "details": f"파일 타입: {filename.split('.')[-1].upper()}, 분석 엔진: GPT-4o-mini"
            }

        except Exception as e:
            return {"summary": "파일 분석 중 오류가 발생했습니다.", "details": str(e)}

@router.post("/upload")
async def upload_for_analysis(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. Registration
    upload_dir = "uploads/analysis"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Analyzer 주입 (D: Dependency Inversion)
    service = AnalysisService(db, OpenAIAnalyzer())
    # 파일 확장자에 따른 타입 분류
    ext = file.filename.split('.')[-1].lower()
    analysis_type = "excel" if ext in ['xlsx', 'xls'] else "pdf" if ext == 'pdf' else "image" if ext in ['jpg', 'jpeg', 'png'] else "general"
    
    record = await service.register_file(file.filename, file_path, analysis_type)

    # 2. Processing (비동기 수행)
    background_tasks.add_task(service.process_analysis, record.id)

    return {"record_id": record.id, "status": record.status}

@router.get("/records")
def list_analysis_records(db: Session = Depends(get_db)):
    service = AnalysisService(db, OpenAIAnalyzer())
    return service.list_records()

@router.get("/records/{record_id}")
def get_analysis_record(record_id: int, db: Session = Depends(get_db)):
    service = AnalysisService(db, OpenAIAnalyzer())
    return service.get_record(record_id)
