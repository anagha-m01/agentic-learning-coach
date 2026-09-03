"""Centralized application configuration and environment validation."""
import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("ENVIRONMENT", "development")

    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    frontend_origins: List[str] = field(
        default_factory=lambda: _split_csv(os.getenv("FRONTEND_ORIGINS", ""))
    )

    session_cookie_name: str = os.getenv("SESSION_COOKIE_NAME", "alc_session")
    session_ttl_hours: int = int(os.getenv("SESSION_TTL_HOURS", "24"))

    rate_limit_default: str = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")
    rate_limit_llm: str = os.getenv("RATE_LIMIT_LLM", "10/minute")

    data_dir: str = os.getenv("DATA_DIR", "data")

    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def default_origins(self) -> List[str]:
        return ["http://localhost:5173", "http://localhost:5174"]

    @property
    def allowed_origins(self) -> List[str]:
        return list(dict.fromkeys(self.default_origins + self.frontend_origins))

    def validate(self) -> None:
        """Validate required environment settings on startup."""
        missing = []
        if not self.groq_api_key:
            missing.append("GROQ_API_KEY")
        if missing:
            raise RuntimeError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                f"Copy backend/.env.example to backend/.env and fill them in."
            )
        if self.is_production and not self.frontend_origins:
            # Warn if CORS origins are unconfigured in production
            import warnings

            warnings.warn(
                "ENVIRONMENT=production but FRONTEND_ORIGINS is empty — "
                "your deployed frontend will be blocked by CORS.",
                stacklevel=2,
            )


settings = Settings()
