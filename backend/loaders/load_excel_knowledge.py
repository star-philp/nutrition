import os
import pandas as pd
import sys
from sqlalchemy.orm import Session

# 프로젝트 루트 경로 추가
CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.core.db import SessionLocal, engine, Base
from app.models.rag import KnowledgeChunk

def load_excel_to_rag(file_path: str, db: Session):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"Loading Excel file: {file_path}")
    
    # 데이터 읽기 (국가표준식품성분표 구조에 맞춰 로직 작성)
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return

    # 데이터 전처리 및 텍스트화
    # 예: "식품명: 쌀, 에너지: 350kcal, 단백질: 6g..." 형태의 문장 생성
    chunks = []
    for _, row in df.iterrows():
        # 데이터가 있는 컬럼들만 조합하여 상세한 설명 문장 생성
        info = []
        for col in df.columns:
            val = row[col]
            if pd.notna(val):
                info.append(f"{col}: {val}")
        
        content = ", ".join(info)
        
        chunk = KnowledgeChunk(
            source=file_path,
            source_type="excel",
            version="2024-v1",
            title=str(row.get('식품명', '식품 영양 정보')),
            content=content,
            meta={"filename": os.path.basename(file_path)}
        )
        chunks.append(chunk)

    # 데이터베이스 저장
    try:
        db.add_all(chunks)
        db.commit()
        print(f"Successfully indexed {len(chunks)} items from {os.path.basename(file_path)}")
    except Exception as e:
        db.rollback()
        print(f"Database error: {e}")

if __name__ == "__main__":
    db = SessionLocal()
    # ml/data/foods 디렉토리의 모든 엑셀 파일 처리
    DATA_DIR = os.path.join(BACKEND_DIR, "..", "ml", "data", "foods")
    
    for file in os.listdir(DATA_DIR):
        if file.endswith(".xlsx"):
            load_excel_to_rag(os.path.join(DATA_DIR, file), db)
    
    db.close()
