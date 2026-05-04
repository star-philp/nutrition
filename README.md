# 🍼 영양 정보 기반 이유식 추천 서비스

## 📖 프로젝트 개요

본 프로젝트는 영양학적 데이터에 기반하여 아기의 월령과 특정 요구사항에 맞는 이유식을 추천하는 서비스입니다. 음식 데이터와 영양 정보를 분석하여, 부모님들이 아기에게 가장 적합한 식단을 구성할 수 있도록 돕는 것을 목표로 합니다.

## ✨ 주요 기능

- **월령별 이유식 추천:** 아기의 생년월일을 바탕으로 개월 수를 계산하여 2020 한국인 영양소 섭취기준(KDRI)에 따른 적합한 이유식을 추천합니다.
- **멀티 에이전트 AI 시스템:** 영양 분석 에이전트와 안전 에이전트(Safety Agent)가 협력하여 특정 월령별 금지 식재료(예: 돌 전 꿀)나 나트륨 과다 등을 실시간으로 감지하고 경고합니다.
- **초개인화 프로필 설정:** 아기의 알레르기 및 신체 정보를 반영하여 지식 검색 및 AI가 맞춤형 영양 가이드와 식단을 제안합니다.
- **공공데이터(식품안전나라) 연동:** 식약처 국가표준식품성분표 기반 데이터(3,300여 개)를 로드하여 나트륨, 당류, 콜레스테롤, 지방산 등 세부 영양소를 정밀 분석합니다.
- **유연한 RAG 지식 검색:** 가중치 기반 검색 알고리즘으로 보건복지부 지침서 등 신뢰할 수 있는 영양 데이터를 자연어로 검색할 수 있습니다.

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

### 5. 식약처 (식품안전나라) 공공 데이터 연동
식품성분 DB를 최신화하거나 세부 영양소(나트륨, 당류 등)를 정밀 분석하기 위해 식약처 API를 연동할 수 있습니다.
`backend/.env` 파일에 발급받은 API 키를 설정하세요.
```bash
MFDS_API_KEY=발급받은_식약처_API키_문자열
```
이후 터미널에서 아래 명령어로 데이터를 동기화합니다.
```bash
cd backend
python loaders/import_mfds_api.py
```

---

<p align="center">멀티 에이전트(MAS) 기반 영양 분석 시스템</p>
