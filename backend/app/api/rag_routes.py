from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.db import get_db
from app.models.rag import KnowledgeChunk
from sqlalchemy import text, or_
from pydantic import BaseModel
import re

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


@router.get("/chunks", response_model=list[dict])
def list_chunks(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(KnowledgeChunk).order_by(KnowledgeChunk.id.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "source": r.source,
            "version": r.version,
            "title": r.title,
        }
        for r in rows
    ]


@router.get("/debug-search", response_model=dict)
def debug_search(q: str, db: Session = Depends(get_db)):
    """간단한 ILIKE 디버그: 서버 측에서 매치 건수를 확인"""
    like = f"%{q}%"
    total = (
        db.query(KnowledgeChunk)
        .filter((KnowledgeChunk.title.ilike(like)) | (KnowledgeChunk.content.ilike(like)))
        .count()
    )
    # 샘플 id 5개
    rows = (
        db.query(KnowledgeChunk)
        .filter((KnowledgeChunk.title.ilike(like)) | (KnowledgeChunk.content.ilike(like)))
        .limit(5)
        .all()
    )
    return {
        "q": q,
        "match_count": int(total),
        "sample_ids": [r.id for r in rows],
    }

class RagSearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/search", response_model=dict)
def semantic_search(payload: RagSearchRequest, db: Session = Depends(get_db)):
    # 텍스트 검색을 먼저 시도하고, 필요한 경우에만 벡터 검색을 수행
    q_text = (payload.query or "").strip()
    if not q_text:
        return {"answer": "", "sources": []}

    sources = []

    # 1) 텍스트 검색 (완화 like → 토큰 AND → 토큰 OR) + dedup + highlight
    try:
        wildcard_q = re.sub(r"[-~∼–—−]+", "%", q_text)
        like_patterns = [f"%{q_text}%", f"%{wildcard_q}%"]

        def run_like(patterns):
            conds = []
            for p in patterns:
                conds.append(KnowledgeChunk.title.ilike(p))
                conds.append(KnowledgeChunk.content.ilike(p))
            if not conds:
                return []
            return (
                db.query(KnowledgeChunk)
                .filter(or_(*conds))
                .limit(int(max(payload.top_k, 5)))
                .all()
            )

        rows = run_like(like_patterns)

        tokens = [t for t in re.split(r"[^0-9A-Za-z가-힣]+", q_text) if t]
        if not rows and tokens:
            query = db.query(KnowledgeChunk)
            for t in tokens:
                tl = f"%{t}%"
                query = query.filter((KnowledgeChunk.title.ilike(tl)) | (KnowledgeChunk.content.ilike(tl)))
            rows = query.limit(int(payload.top_k)).all()
        if not rows and tokens:
            rows = run_like([f"%{t}%" for t in tokens])

        if rows:
            seen = set()
            results = []
            for r in rows:
                key = (r.source or "", r.version or "", (r.title or "")[:60], r.id)
                if key in seen:
                    continue
                seen.add(key)
                content = r.content or ""
                highlight = None
                patterns = [q_text] + tokens
                best_idx = -1
                best_pat = None
                for pat in patterns:
                    if not pat:
                        continue
                    m = re.search(re.escape(pat), content, flags=re.IGNORECASE)
                    if m:
                        best_idx = m.start()
                        best_pat = pat
                        break
                if best_idx >= 0:
                    start = max(0, best_idx - 120)
                    end = min(len(content), best_idx + len(best_pat) + 120)
                    highlight = content[start:end]
                results.append({
                    "id": r.id,
                    "source": r.source,
                    "version": r.version,
                    "title": r.title,
                    "content": r.content,
                    "score": 1.0,
                    "highlight": highlight,
                })
            sources = results[: int(payload.top_k)]
    except Exception:
        pass

    # 2) (옵션) 임베딩/pgvector 검색 — 텍스트/결과가 비었을 때만 시도
    if not sources:
        model = None
        q_emb = None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
            q_emb = model.encode([q_text], normalize_embeddings=True)[0]
            sql = text(
                """
                SELECT id, source, version, title, content, 1 - (embedding <-> :qemb) AS score
                FROM knowledge_chunks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <-> :qemb
                LIMIT :k
                """
            )
            rows = db.execute(sql, {"qemb": q_emb.tolist(), "k": int(payload.top_k)}).fetchall()
            sources = [
                {"id": r.id, "source": r.source, "version": r.version, "title": r.title, "content": r.content, "score": float(r.score)}
                for r in rows
            ]
        except Exception:
            pass

    # 3) OpenAI 문서 요약
    from app.core.config import settings
    answer = "문서에서 검색된 내용이 존재하지 않습니다."
    
    if sources:
        if getattr(settings, "OPENAI_API_KEY", None):
            import openai
            try:
                client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                context_text = "\\n\\n".join([f"[{i+1}] {s.get('content', '')}" for i, s in enumerate(sources)])
                prompt = f"다음은 참고할 문서 조각들입니다:\\n{context_text}\\n\\n위 내용을 참고하여 다음 질문에 한국어로 정리해 답변해주세요.\\n질문: {q_text}\\n\\n(참고한 문서 내용이 있다면 [1], [2] 형식으로 출처 번호를 달아주세요.)"
                
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "당신은 영유아 영양 관리 전문가입니다. 오직 제공된 문서 내용에만 기반하여 질문에 답변하세요."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
                answer = resp.choices[0].message.content
            except Exception as e:
                print(f"OpenAI error: {e}")
                answer = "OpenAI API 호출 중 오류가 발생했습니다. (서버 콘솔 확인)"
        else:
            answer = "OpenAI API 키가 설정되지 않아 문장화된 요약 답변을 제공할 수 없습니다. 대신 아래 참고 문헌을 확인해주세요."

    return {"answer": answer, "sources": sources}


