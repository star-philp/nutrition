"""
KDRIs PDF 및 국가표준식품성분표 요약을 추출/청크/임베딩하여 knowledge_chunks 테이블에 저장합니다.
벡터는 pgvector 확장을 사용합니다. (DB에 CREATE EXTENSION IF NOT EXISTS vector; 필요)
"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

import pandas as pd
# sentence-transformers는 TF/Transformers 의존성 충돌이 있을 수 있으므로
# 임베딩은 가능할 때만 사용하고, 실패 시 텍스트만 저장하도록 지연 임포트합니다.
from sqlalchemy.orm import Session
from sqlalchemy import text

import sys
CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from app.core.db import SessionLocal, engine, Base
from app.models.rag import KnowledgeChunk


DOCS = [
    (os.path.join(BACKEND_DIR, "..", "ml", "data", "foods", "01+2020+한국인+영양소+섭취기준+에너지화+다량영양소.pdf"), "pdf", "KDRI-2020"),
    (os.path.join(BACKEND_DIR, "..", "ml", "data", "foods", "02+2020+한국인+영양소+섭취기준+비타민.pdf"), "pdf", "KDRI-2020"),
    (os.path.join(BACKEND_DIR, "..", "ml", "data", "foods", "03+2020+한국인+영양소+섭취기준+무기질.pdf"), "pdf", "KDRI-2020"),
]


def ensure_schema() -> None:
    # 필요한 테이블이 없다면 생성
    Base.metadata.create_all(bind=engine)


def extract_pdf_text(path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(path)
    parts: List[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts)


def chunk_text(text: str, max_chars: int = 1200) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        start = end
    return [c for c in chunks if c]


def index_docs(db: Session) -> None:
    ensure_schema()
    
    # 기존 데이터 초기화 (중복 방지)
    print("[INFO] 기존 지식 베이스를 초기화합니다...")
    db.execute(text("TRUNCATE TABLE knowledge_chunks RESTART IDENTITY CASCADE;"))
    db.commit()

    # 임베딩 사용 가능 여부 확인 (지연 임포트)
    embed_available = False
    model = None
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        print("[INFO] 임베딩 모델 로딩 중 (paraphrase-multilingual-mpnet-base-v2)...")
        model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
        embed_available = True
        print("[INFO] 임베딩 모델 로딩 완료.")
    except Exception as e:
        print(f"[WARNING] 임베딩 비활성화: sentence-transformers 사용 불가 ({e})")
    for path, src_type, version in DOCS:
        if not os.path.exists(path):
            print(f"경고: 파일 없음 → {path}")
            continue
        if src_type == "pdf":
            doc_text = extract_pdf_text(path)
            chunks = chunk_text(doc_text)
        else:
            continue
        if not chunks:
            continue
        if embed_available and model is not None:
            try:
                # 임베딩 저장 시도 (pgvector 설치 환경)
                embeddings = model.encode(chunks, convert_to_numpy=True, normalize_embeddings=True)
                for content, emb in zip(chunks, embeddings):
                    row = KnowledgeChunk(
                        source=path,
                        source_type=src_type,
                        version=version,
                        title=None,
                        content=content,
                        meta=None,
                        embedding=emb.tolist(),
                    )
                    db.add(row)
            except Exception as e:
                print(f"임베딩 저장 실패, 텍스트만 저장합니다: {e}")
                for content in chunks:
                    row = KnowledgeChunk(
                        source=path,
                        source_type=src_type,
                        version=version,
                        title=None,
                        content=content,
                        meta=None,
                    )
                    db.add(row)
        else:
            # 임베딩 비활성화 상태: 텍스트만 저장
            for content in chunks:
                row = KnowledgeChunk(
                    source=path,
                    source_type=src_type,
                    version=version,
                    title=None,
                    content=content,
                    meta=None,
                )
                db.add(row)
        db.commit()
        print(f"인덱싱 완료: {path} ({len(chunks)} 청크)")


def main() -> None:
    db = SessionLocal()
    try:
        index_docs(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()


