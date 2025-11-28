import os
import sys
import logging
import traceback

# 프로젝트 루트 경로를 sys.path에 추가하여 app 모듈을 찾을 수 있도록 함
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

try:
    from app.core.config import settings
    import psycopg2
    from psycopg2 import OperationalError
except ImportError as e:
    print(f"필수 라이브러리를 찾을 수 없습니다: {e}")
    print("먼저 'pip install -r requirements.txt'를 실행했는지 확인해주세요.")
    sys.exit(1)

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger(__name__)

def test_connection():
    # 'baby_food_db' 대신 기본 'postgres' DB로 연결을 테스트합니다.
    target_db = 'postgres'
    logger.info(f"기본 데이터베이스('{target_db}') 연결 테스트를 시작합니다...")
    logger.info(f"사용될 설정: postgresql://{settings.DB_USER}:****@{settings.DB_HOST}:{settings.DB_PORT}/{target_db}")

    try:
        # psycopg2를 사용하여 직접 연결 시도
        conn = psycopg2.connect(
            dbname=target_db,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            connect_timeout=5
        )
        logger.info(f"✅ 기본 데이터베이스('{target_db}') 연결에 성공했습니다!")
        logger.info("결론: DB 서버 주소, 포트, 사용자, 비밀번호가 모두 올바릅니다.")
        logger.info("다음 단계는 'baby_food_db' 데이터베이스를 생성하는 것입니다.")
        conn.close()
    except OperationalError as e:
        logger.error(f"❌ 기본 데이터베이스('{target_db}') 연결에 실패했습니다! (OperationalError)")
        logger.error("PostgreSQL 서버가 보낸 실제 오류 메시지:")
        logger.error(f"-> {e}")
        logger.error("-" * 50)
        logger.error("가장 가능성이 높은 원인:")
        logger.error("1. .env 파일의 DB_PASSWORD가 실제 PostgreSQL 비밀번호와 다릅니다.")
        logger.error("2. PostgreSQL 서버가 로컬 연결을 허용하도록 설정되지 않았습니다.")
        logger.error("3. 방화벽이 5432 포트로의 연결을 막고 있습니다.")
        
    except Exception as e:
        logger.error("❌ 예상치 못한 오류가 발생했습니다!")
        logger.error("자세한 실패 원인:")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    test_connection()
