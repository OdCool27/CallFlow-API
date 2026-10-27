"""Local configuration; environment variables take precedence over .env."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./callflow.db"))
    ami_enabled: bool = field(default_factory=lambda: os.getenv("AMI_ENABLED", "false").lower() == "true")
    ami_host: str = field(default_factory=lambda: os.getenv("AMI_HOST", "192.168.56.101"))
    ami_port: int = field(default_factory=lambda: int(os.getenv("AMI_PORT", "5038")))
    ami_username: str = field(default_factory=lambda: os.getenv("AMI_USERNAME", "callflow"))
    ami_secret: str = field(default_factory=lambda: os.getenv("AMI_SECRET", ""), repr=False)
    ami_timeout: float = field(default_factory=lambda: float(os.getenv("AMI_TIMEOUT", "5")))
    ami_reconnect_attempts: int = field(default_factory=lambda: int(os.getenv("AMI_RECONNECT_ATTEMPTS", "5")))
    ami_reconnect_delay: float = field(default_factory=lambda: float(os.getenv("AMI_RECONNECT_DELAY", "2")))

    def __post_init__(self):
        if self.ami_timeout <= 0 or self.ami_reconnect_delay < 0 or self.ami_reconnect_attempts < 1:
            raise ValueError("AMI timeout/attempts must be positive; reconnect delay cannot be negative")


settings = Settings()
