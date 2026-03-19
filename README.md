# 🍼 영양 정보 기반 이유식 추천 서비스

## 📖 프로젝트 개요

본 프로젝트는 영양학적 데이터에 기반하여 아기의 월령과 특정 요구사항에 맞는 이유식을 추천하는 서비스입니다. 음식 데이터와 영양 정보를 분석하여, 부모님들이 아기에게 가장 적합한 식단을 구성할 수 있도록 돕는 것을 목표로 합니다.

## ✨ 주요 기능

- **월령별 이유식 추천:** 아기의 개월 수에 따라 적합한 이유식 레시피를 추천합니다.
- **영양소 기반 검색:** 특정 영양소가 풍부한 음식 재료나 레시피를 검색할 수 있습니다.
- **알레르기 정보 필터링:** 특정 음식에 알레르기가 있는 아기를 위해 해당 재료를 제외한 메뉴를 추천합니다.
- **데이터 시각화:** 영양소 정보를 차트나 그래프로 시각화하여 쉽게 이해할 수 있도록 제공합니다.

## 🛠️ 기술 스택

- **Backend:** Python (FastAPI, Flask 등)
- **Frontend:** HTML, CSS, JavaScript (필요시 프레임워크 명시)
- **Machine Learning / Data Analysis:** Pandas, Scikit-learn, Matplotlib
- **Database:** SQLite, PostgreSQL 등

## 📂 디렉토리 구조

```
.
├── backend/            # 백엔드 API 및 비즈니스 로직
├── frontend/           # 프론트엔드 UI/UX
├── ml/                 # 머신러닝 모델 및 데이터 분석 스크립트
├── .gitignore          # Git 버전 관리 제외 파일 목록
└── README.md           # 프로젝트 소개 파일
```

## 🚀 실행 방법

### 1. 데이터베이스 준비 (PostgreSQL)
현재 프로젝트는 PostgreSQL을 사용합니다. 아래 정보로 DB와 사용자를 생성해야 합니다.
- **사용자명:** `postgres`
- **비밀번호:** `1234`
- **데이터베이스명:** `baby_food_db`
- **필수 확장:** DB 내에서 `CREATE EXTENSION IF NOT EXISTS vector;` 실행

### 2. 백엔드 서버 실행

```bash
cd backend
# 가상환경 활성화 (필수)
source ../venv/bin/activate
# 패키지 설치
pip install -r requirements.txt
pip install Pillow # 이미지 처리 필수
# 서버 실행 (포트 8080)
PYTHONPATH=. python -m uvicorn app.main:app --port 8080 --reload
```

### 3. 프론트엔드 서버 실행 (React + Vite)

```bash
cd frontend
# 의존성 모듈 설치 (최초 1회)
npm install
# 개발 서버 실행
npm run dev
```
- 실행 후 브라우저에서 `http://localhost:5173/` 로 접속합니다.

### 4. RAG AI 요약 기능 (OpenAI 연동)
지식 검색(RAG) 결과를 자연스러운 문장으로 요약해서 보려면 `backend/.env` 파일을 만들고 아래와 같이 API 키를 설정해야 합니다.
```bash
OPENAI_API_KEY=sk-본인의_오픈AI_키
```

---

<p align="center">프로젝트에 대한 더 자세한 설명이나 기여 방법을 추가할 수 있습니다.</p>
