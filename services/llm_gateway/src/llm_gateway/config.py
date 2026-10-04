"""Settings from the environment. Only this service knows LLM_MODE (Principle V)."""

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
MODES = ("fake", "record", "ollama")


@dataclass(frozen=True)
class Settings:
    mode: str
    ollama_url: str
    fixtures_dir: Path
    esquemas_path: Path
    model: str = "gemma4:12b"
    ocr_model: str = "glm-ocr"

    @classmethod
    def from_env(cls) -> "Settings":
        mode = os.environ.get("LLM_MODE", "fake")
        if mode not in MODES:
            raise ValueError(f"LLM_MODE must be one of {MODES}, got {mode!r}")
        return cls(
            mode=mode,
            ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            fixtures_dir=Path(os.environ.get("FIXTURES_DIR", REPO_ROOT / "fixtures" / "llm")),
            esquemas_path=Path(os.environ.get("ESQUEMAS_PATH", REPO_ROOT / "eval" / "esquemas.json")),
        )
