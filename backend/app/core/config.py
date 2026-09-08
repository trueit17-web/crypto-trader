from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
    )

    # App
    APP_NAME: str = 'CryptoTrader Platform'
    APP_VERSION: str = '0.1.0'
    DEBUG: bool = False
    ENVIRONMENT: str = 'development'  # development | staging | production

    # Database
    POSTGRES_USER: str = 'trader'
    POSTGRES_PASSWORD: str = 'trader_secret'
    POSTGRES_HOST: str = 'localhost'
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = 'cryptotrader'

    @property
    def DATABASE_URL(self) -> str:
        return (
            f'postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}'
            f'@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}'
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f'postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}'
            f'@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}'
        )

    # Redis
    REDIS_HOST: str = 'localhost'
    REDIS_PORT: int = 6379
    REDIS_DB_CACHE: int = 0
    REDIS_DB_QUEUE: int = 1
    REDIS_DB_RATELIMIT: int = 2

    @property
    def REDIS_URL(self) -> str:
        return f'redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB_CACHE}'

    # JWT Auth
    JWT_SECRET_KEY: str = 'CHANGE_THIS_IN_PRODUCTION_USE_VAULT'
    JWT_ALGORITHM: str = 'HS256'
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: List[str] = ['http://localhost:3000']

    # Risk defaults (all configurable per exchange/strategy)
    MAX_ACCOUNT_RISK_PER_TRADE: float = 0.01    # 1%
    MAX_PORTFOLIO_EXPOSURE: float = 0.20         # 20%
    MAX_EXCHANGE_EXPOSURE: float = 0.40          # 40%
    MAX_ASSET_EXPOSURE: float = 0.15             # 15%
    MAX_DAILY_DRAWDOWN: float = 0.05             # 5%
    MAX_WEEKLY_DRAWDOWN: float = 0.10            # 10%
    MAX_LEVERAGE: int = 10
    MIN_LIQUIDATION_DISTANCE: float = 0.20       # 20%
    MAX_SIMULTANEOUS_POSITIONS: int = 20
    MAX_CONSECUTIVE_LOSSES: int = 5
    MAX_SLIPPAGE_PCT: float = 0.003              # 0.3%

    # Telegram
    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ''
    TELEGRAM_SESSION_STRING: str = ''

    # Sentry
    SENTRY_DSN: str = ''

    # Rate limiting
    API_RATE_LIMIT_PER_MINUTE: int = 100
    SYSTEM_RATE_LIMIT_PER_MINUTE: int = 1000


settings = Settings()
