from functools import lru_cache
from typing import Literal

from pydantic import field_validator
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

    @field_validator("database_url", mode="after")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        """Convert postgresql:// to postgresql+asyncpg:// for async driver."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

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

    # Phase 3: Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_default_requests: int = 30
    rate_limit_default_window: int = 60

    # Phase 3: Code Golf settings
    codegolf_enabled: bool = True
    codegolf_sandbox_timeout: int = 5  # seconds
    codegolf_sandbox_memory: str = "64m"
    codegolf_docker_network: str = "none"
    codegolf_allowed_languages: list[str] = ["python", "javascript", "go"]

    # Phase 3: PWA & Notifications
    vapid_private_key: str = ""  # Set in production .env
    vapid_public_key: str = ""  # Set in production .env
    vapid_email: str = "admin@siliconcasino.ai"
    push_notifications_enabled: bool = True

    # Phase 3: Referral system
    referral_commission_rate: float = 0.10  # 10% of rake
    referral_min_activity: int = 10  # Min hands before earning commissions

    # Phase 3: Admin settings
    admin_oauth_enabled: bool = True
    admin_allowed_emails: list[str] = []  # Whitelist for admin OAuth

    # Phase 3: Metrics
    metrics_enabled: bool = True

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
