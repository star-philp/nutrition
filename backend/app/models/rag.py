from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import LargeBinary
from sqlalchemy.dialects.postgresql import JSONB

# pgvector 사용 가능 여부 확인
try:
    from pgvector.sqlalchemy import Vector  # type: ignore
    VECTOR_AVAILABLE = True
except Exception:  # pragma: no cover
    Vector = None  # type: ignore
    VECTOR_AVAILABLE = False

from app.core.db import Base


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(255), nullable=False)  # 파일 경로 또는 식별자
    source_type = Column(String(50), nullable=False)  # pdf/md/etc
    version = Column(String(50), nullable=True)  # 예: KDRI-2020, KFCDB-10.2
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    meta = Column(JSONB, nullable=True)
    if VECTOR_AVAILABLE:
        embedding = Column(Vector(768))  # type: ignore


