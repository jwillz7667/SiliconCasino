from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://silicon:casino_dev_123@localhost:5432/silicon_casino"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    api_key_prefix: str = "sk_"

    # Poker defaults
    default_starting_chips: int = 10000

    # Rake settings
    rake_percentage: float = 0.05  # 5% rake
    rake_cap: int = 500  # Maximum rake per hand (in chips)
    rake_threshold: int = 100  # Minimum pot to collect rake

    # Crypto settings (USDC on Polygon)
    polygon_rpc_url: str = "https://polygon-rpc.com"
    polygon_chain_id: int = 137
    usdc_contract_address: str = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Polygon USDC
    hot_wallet_private_key: str = ""  # Set in production .env
    deposit_confirmations: int = 12
    min_withdrawal: int = 1000  # Minimum withdrawal in chips

    # Anti-collusion settings
    collusion_detection_enabled: bool = True
    min_hands_for_analysis: int = 50
    suspicious_win_rate_threshold: float = 0.75

    # Tournament settings
    min_tournament_players: int = 2
    max_tournament_players: int = 1000

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
