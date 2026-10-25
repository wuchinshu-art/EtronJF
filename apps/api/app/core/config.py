from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "ETJ EtronJF8 Management System"
    API_V1_STR: str = "/api/v1"
    
    # 資料庫設定 (Database Settings)
    DATABASE_PATH: Path = Path(__file__).resolve().parent.parent.parent / "data" / "etronjf8.db"
    SQLITE_BUSY_TIMEOUT_MS: int = 5000
    SQLITE_SYNCHRONOUS: str = "FULL"  # 財務資料耐久性優先
    SQLITE_JOURNAL_MODE: str = "WAL"
    
    # 預設時區 (Default Timezones)
    DEFAULT_TIMEZONE_TAIPEI: str = "Asia/Taipei"
    DEFAULT_TIMEZONE_TOKYO: str = "Asia/Tokyo"
    
    # 安全與會話設定 (Security & Session Settings)
    SESSION_COOKIE_NAME: str = "etj_session"
    SESSION_MAX_AGE_SECONDS: int = 86400  # 24 小時
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @property
    def sqlite_url(self) -> str:
        self.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.DATABASE_PATH.as_posix()}"


settings = Settings()
