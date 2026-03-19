from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, computed_field

class Settings(BaseSettings):
    # .env 파일 또는 환경변수에서 값을 읽어옵니다.
    DB_USER: str = 'postgres'
    DB_PASSWORD: str = '1234'
    DB_HOST: str = 'localhost'
    DB_PORT: int = 5432
    DB_NAME: str = 'baby_food_db'
    OPENAI_API_KEY: str = ''

    # 다른 필드 값들이 준비된 후, 동적으로 DATABASE_URL 값을 계산합니다.
    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return str(PostgresDsn.build(
            scheme="postgresql",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            path=f"{self.DB_NAME or ''}",
        ))

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding='utf-8'
    )

settings = Settings() 