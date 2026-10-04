"""Settings from the environment (docker-compose.yml)."""

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class Settings:
    database_url: str
    policy_dir: Path
    providers_dir: Path
    documents_dir: Path
    doc_intel_url: str
    # Pins "today" for document validity so demos are reproducible (SC-001); None = real date.
    as_of_date: date | None = None
    # Browser origins allowed by CORS (the web container, specs/002-demo-web W-04).
    web_origins: tuple[str, ...] = ("http://localhost:8080",)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get(
                "DATABASE_URL", "postgresql://actions_rw:actions_pw@localhost:55432/app"
            ),
            policy_dir=Path(os.environ.get("POLICY_DIR", REPO_ROOT / "policy")),
            providers_dir=Path(os.environ.get("PROVIDERS_DIR", REPO_ROOT / "fixtures" / "providers")),
            documents_dir=Path(os.environ.get("DOCUMENTS_DIR", REPO_ROOT / ".data" / "documents")),
            doc_intel_url=os.environ.get("DOC_INTEL_URL", "http://localhost:8003"),
            as_of_date=date.fromisoformat(os.environ["AS_OF_DATE"]) if os.environ.get("AS_OF_DATE") else None,
            web_origins=tuple(
                origin.strip()
                for origin in os.environ.get("WEB_ORIGINS", "http://localhost:8080").split(",")
                if origin.strip()
            ),
        )
