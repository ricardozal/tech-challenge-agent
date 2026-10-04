"""Document Intelligence: stateless, no database (Principle III).

Feature 001 / US3 (T072) adds POST /v1/documents/extract.
"""

from fastapi import FastAPI

app = FastAPI(title="Document Intelligence")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
