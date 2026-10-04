"""Case Actions API: POST /tools/{name} plus read endpoints for advisors and demo scripts."""

import importlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from actions_api import db
from actions_api.config import Settings
from actions_api.policy import PolicyRegistry
from actions_api.providers.bureau import BureauProvider
from actions_api.providers.document_reader import DocumentReader
from actions_api.providers.key_quote import KeyQuoteProvider
from actions_api.providers.vehicle_registry import VehicleRegistryProvider
from actions_api.toolkit import REGISTRY, Services, execute
from contracts.actions import ToolCall, ToolResult
from contracts.case import AuditEntry, CaseSummary, CaseView, Escalation
from contracts.common import Actor

# Tool modules register themselves with @tool on import.
TOOL_MODULES = [
    "actions_api.tools.case",
    "actions_api.tools.eligibility",
    "actions_api.tools.profiling",
    "actions_api.tools.documents",
    "actions_api.tools.gate",
    "actions_api.tools.advisor",
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    for module in TOOL_MODULES:
        importlib.import_module(module)

    database = db.Database(settings.database_url)
    services = Services(
        policies=PolicyRegistry.load(settings.policy_dir),
        extras={
            "settings": settings,
            "vehicle_registry": VehicleRegistryProvider(settings.providers_dir / "vehicle_registry.yaml"),
            "key_quote": KeyQuoteProvider(settings.providers_dir / "key_quotes.yaml"),
            "bureau": BureauProvider(settings.providers_dir / "bureau.yaml"),
            "document_reader": DocumentReader(settings.doc_intel_url),
        },
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        database.open()
        yield
        database.close()

    app = FastAPI(title="Case Actions API", lifespan=lifespan)
    app.state.database = database
    app.state.services = services

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "tools": sorted(REGISTRY), "policy_version": services.policies.current().policy_version}

    @app.post("/tools/{name}", response_model=ToolResult)
    def call_tool(name: str, call: ToolCall, x_actor: Annotated[Actor, Header()]) -> JSONResponse:
        with database.transaction() as conn:
            status, result = execute(conn, services, name, x_actor, call)
        return JSONResponse(status_code=status, content=result.model_dump(mode="json"))

    @app.get("/cases", response_model=list[CaseSummary])
    def list_cases(status: str | None = None, stage: str | None = None) -> list[CaseSummary]:
        with database.read() as conn:
            return [CaseSummary.model_validate(row) for row in db.list_cases(conn, status, stage)]

    @app.get("/cases/{case_id}", response_model=CaseView)
    def get_case(case_id: UUID) -> CaseView:
        with database.read() as conn:
            case = db.load_case(conn, case_id)
        if case is None:
            raise HTTPException(404, "case not found")
        return case

    @app.get("/cases/{case_id}/audit", response_model=list[AuditEntry])
    def case_audit(case_id: UUID) -> list[AuditEntry]:
        with database.read() as conn:
            return [AuditEntry.model_validate(row) for row in db.list_audit(conn, case_id)]

    @app.get("/escalations", response_model=list[Escalation])
    def list_escalations(status: str | None = None) -> list[Escalation]:
        with database.read() as conn:
            return [Escalation.model_validate(row) for row in db.list_escalations(conn, status)]

    @app.get("/escalations/{escalation_id}", response_model=Escalation)
    def get_escalation(escalation_id: UUID) -> Escalation:
        with database.read() as conn:
            row = db.get_escalation(conn, escalation_id)
        if row is None:
            raise HTTPException(404, "escalation not found")
        return Escalation.model_validate(row)

    return app


app = create_app()
