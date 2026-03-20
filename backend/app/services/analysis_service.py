from abc import ABC, abstractmethod
from typing import Any, List
from sqlalchemy.orm import Session
from app.models.analysis import AnalysisRecord
import os

# Interface for Analyzers (D: Dependency Inversion)
class IAnalyzer(ABC):
    @abstractmethod
    async def analyze(self, file_path: str) -> Any:
        pass

# Concrete Service (S: Single Responsibility)
class AnalysisService:
    def __init__(self, db: Session, analyzer: IAnalyzer):
        self.db = db
        self.analyzer = analyzer

    async def register_file(self, filename: str, file_path: str, analysis_type: str) -> AnalysisRecord:
        record = AnalysisRecord(
            filename=filename,
            file_path=file_path,
            analysis_type=analysis_type,
            status="PENDING"
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    async def process_analysis(self, record_id: int):
        print(f"DEBUG: Starting analysis for record_id={record_id}")
        record = self.db.query(AnalysisRecord).filter(AnalysisRecord.id == record_id).first()
        if not record:
            print(f"DEBUG: Record {record_id} not found")
            return

        try:
            record.status = "PROCESSING"
            self.db.commit()
            print(f"DEBUG: Status updated to PROCESSING for {record.filename}")

            # 실제 분석 수행 (추상화된 analyzer 사용)
            result = await self.analyzer.analyze(record.file_path)
            print(f"DEBUG: Analysis completed for {record.filename}. Result summary length: {len(result.get('summary', ''))}")

            record.status = "COMPLETED"
            record.result = result
        except Exception as e:
            print(f"DEBUG: Analysis failed for {record.filename}: {e}")
            record.status = "FAILED"
            record.result = {"error": str(e)}
        finally:
            self.db.commit()
            self.db.refresh(record)
            print(f"DEBUG: Final status for {record.filename}: {record.status}")

    def get_record(self, record_id: int) -> AnalysisRecord:
        return self.db.query(AnalysisRecord).filter(AnalysisRecord.id == record_id).first()

    def list_records(self, limit: int = 10) -> List[AnalysisRecord]:
        return self.db.query(AnalysisRecord).order_by(AnalysisRecord.created_at.desc()).limit(limit).all()
