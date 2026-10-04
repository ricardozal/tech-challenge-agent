"""Settings from the environment (docker-compose.yml). The agent never knows LLM_MODE."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    actions_url: str
    llm_url: str
    case_lock_timeout_s: float
    web_origins: tuple[str, ...] = ("http://localhost:8080",)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get(
                "DATABASE_URL",
                "postgresql://agent_rw:agent_pw@localhost:55432/app?options=-csearch_path%3Dagent",
            ),
            actions_url=os.environ.get("ACTIONS_URL", "http://localhost:8000"),
            llm_url=os.environ.get("LLM_URL", "http://localhost:8002"),
            case_lock_timeout_s=float(os.environ.get("CASE_LOCK_TIMEOUT_S", "10")),
            web_origins=web_origins_from_env(),
        )


def web_origins_from_env() -> tuple[str, ...]:
    """Browser origins allowed by CORS (the web container, specs/002-demo-web W-04)."""
    raw = os.environ.get("WEB_ORIGINS", "http://localhost:8080")
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())
