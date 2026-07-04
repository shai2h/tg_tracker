from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# определяем абсолютный путь до корня проекта
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    DB_HOST: str
    DB_NAME: str
    DB_USER: str
    DB_PASS: str
    DB_PORT: int

    DB_ECHO: bool = False

    BOT_TOKEN: str

    GIGACHAT_AUTH_KEY: str
    GIGACHAT_SCOPE: str = "GIGACHAT_API_PERS"
    GIGACHAT_MODEL: str = "GigaChat"
    GIGACHAT_OAUTH_URL: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    GIGACHAT_API_BASE_URL: str = "https://gigachat.devices.sberbank.ru/api/v1"
    GIGACHAT_VERIFY_SSL: bool = False
    GIGACHAT_TIMEOUT_SECONDS: int = 30
    GIGACHAT_MAX_TOKENS: int = 50
    GIGACHAT_TEMPERATURE: float = 0.1

    @property
    def DB_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR / ".env.dev"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
