"""Postgres access for the Case Actions API (role actions_rw)."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from contracts.case import CaseState, CaseView, Escalation

# Advisory lock namespace of actions_api; the agent uses 1 (R-04).
ACTIONS_LOCK_NS = 2


class Database:
    def __init__(self, url: str):
        self.pool = ConnectionPool(url, min_size=1, max_size=10, kwargs={"row_factory": dict_row}, open=False)

    def open(self) -> None:
        self.pool.open(wait=True)

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def transaction(self) -> Iterator[psycopg.Connection]:
        with self.pool.connection() as conn, conn.transaction():
            yield conn

    @contextmanager
    def read(self) -> Iterator[psycopg.Connection]:
        with self.pool.connection() as conn:
            yield conn


def lock_key(conn: psycopg.Connection, key: str) -> None:
    conn.execute("SELECT pg_advisory_xact_lock(%s, hashtext(%s))", (ACTIONS_LOCK_NS, key))


# --- cases ---------------------------------------------------------------------------------------

_CASE_COLUMNS = "id, stage, status, version, policy_version, state, created_at, updated_at"


def _case_from_row(row: dict[str, Any]) -> CaseView:
    return CaseView(
        id=row["id"],
        stage=row["stage"],
        status=row["status"],
        version=row["version"],
        policy_version=row["policy_version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        state=CaseState.model_validate(row["state"]),
    )


def load_case(conn: psycopg.Connection, case_id: UUID, *, for_update: bool = False) -> CaseView | None:
    sql = f"SELECT {_CASE_COLUMNS} FROM cases.cases WHERE id = %s" + (" FOR UPDATE" if for_update else "")
    row = conn.execute(sql, (case_id,)).fetchone()
    return _case_from_row(row) if row else None


def list_cases(conn: psycopg.Connection, status: str | None, stage: str | None) -> list[dict[str, Any]]:
    sql = "SELECT id, stage, status, version, updated_at FROM cases.cases WHERE true"
    params: list[Any] = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if stage:
        sql += " AND stage = %s"
        params.append(stage)
    return conn.execute(sql + " ORDER BY updated_at DESC", params).fetchall()


def insert_case(conn: psycopg.Connection, case: CaseView) -> None:
    conn.execute(
        f"INSERT INTO cases.cases ({_CASE_COLUMNS}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            case.id,
            case.stage,
            case.status,
            case.version,
            case.policy_version,
            Jsonb(case.state.model_dump(mode="json")),
            case.created_at,
            case.updated_at,
        ),
    )


def update_case(conn: psycopg.Connection, case: CaseView) -> None:
    conn.execute(
        "UPDATE cases.cases SET stage = %s, status = %s, version = %s, state = %s, updated_at = %s WHERE id = %s",
        (case.stage, case.status, case.version, Jsonb(case.state.model_dump(mode="json")), case.updated_at, case.id),
    )


# --- audit ---------------------------------------------------------------------------------------


def insert_audit(conn: psycopg.Connection, entry: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO audit.audit_log (
            case_id, at, actor, on_behalf_of, tool, stage_before, status_before, stage_after, status_after,
            idempotency_key, expected_version, case_version_after, outcome, rejection_code,
            input, result, events, policy_version
        ) VALUES (
            %(case_id)s, %(at)s, %(actor)s, %(on_behalf_of)s, %(tool)s, %(stage_before)s, %(status_before)s,
            %(stage_after)s, %(status_after)s, %(idempotency_key)s, %(expected_version)s,
            %(case_version_after)s, %(outcome)s, %(rejection_code)s, %(input)s, %(result)s, %(events)s,
            %(policy_version)s
        )
        """,
        {
            **entry,
            "input": Jsonb(_jsonable(entry.get("input", {}))),
            "result": Jsonb(_jsonable(entry.get("result", {}))),
            "events": Jsonb(_jsonable(entry.get("events", []))),
        },
    )


def list_audit(conn: psycopg.Connection, case_id: UUID | None = None) -> list[dict[str, Any]]:
    if case_id is None:
        return conn.execute("SELECT * FROM audit.audit_log ORDER BY id").fetchall()
    return conn.execute("SELECT * FROM audit.audit_log WHERE case_id = %s ORDER BY id", (case_id,)).fetchall()


# --- idempotency ---------------------------------------------------------------------------------


def get_idempotency(conn: psycopg.Connection, scope: str, key: str) -> dict[str, Any] | None:
    return conn.execute(
        "SELECT tool, request_hash, http_status, response FROM cases.idempotency_keys "
        "WHERE scope = %s AND idempotency_key = %s",
        (scope, key),
    ).fetchone()


def put_idempotency(
    conn: psycopg.Connection, scope: str, key: str, tool: str, request_hash: str, http_status: int, response: dict
) -> None:
    conn.execute(
        "INSERT INTO cases.idempotency_keys (scope, idempotency_key, tool, request_hash, http_status, response) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (scope, key, tool, request_hash, http_status, Jsonb(_jsonable(response))),
    )


# --- escalations ---------------------------------------------------------------------------------


def insert_escalation(conn: psycopg.Connection, esc: Escalation) -> None:
    conn.execute(
        """
        INSERT INTO cases.escalations
            (id, case_id, reason, evidence, summary, suggested_action, agent_note, status, resolution,
             created_at, resolved_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            esc.id,
            esc.case_id,
            esc.reason,
            Jsonb(_jsonable(esc.evidence)),
            esc.summary,
            esc.suggested_action,
            esc.agent_note,
            esc.status,
            Jsonb(_jsonable(esc.resolution)) if esc.resolution else None,
            esc.created_at,
            esc.resolved_at,
        ),
    )


def resolve_escalation(conn: psycopg.Connection, escalation_id: UUID, resolution: dict, at: datetime) -> None:
    conn.execute(
        "UPDATE cases.escalations SET status = 'resolved', resolution = %s, resolved_at = %s WHERE id = %s",
        (Jsonb(_jsonable(resolution)), at, escalation_id),
    )


def get_escalation(conn: psycopg.Connection, escalation_id: UUID) -> dict[str, Any] | None:
    return conn.execute("SELECT * FROM cases.escalations WHERE id = %s", (escalation_id,)).fetchone()


def list_escalations(conn: psycopg.Connection, status: str | None) -> list[dict[str, Any]]:
    if status:
        return conn.execute(
            "SELECT * FROM cases.escalations WHERE status = %s ORDER BY created_at", (status,)
        ).fetchall()
    return conn.execute("SELECT * FROM cases.escalations ORDER BY created_at").fetchall()


def _jsonable(value: Any) -> Any:
    """Round-trip through JSON so Decimal, UUID and datetime become plain JSON values."""
    return json.loads(json.dumps(value, default=str))
