"""Settings from the environment (docker-compose.yml)."""

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class Settings:
    database_url: str
    policy_dir: Path
    providers_dir: Path
    documents_dir: Path
    doc_intel_url: str

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
        )
