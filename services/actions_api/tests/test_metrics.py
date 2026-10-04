"""Observability report computed only from the action log (P5, FR-049, SC-008)."""

import json
import uuid
from datetime import date

import psycopg
import pytest
from fastapi.testclient import TestClient

from actions_api.config import Settings
from actions_api.main import create_app
from actions_api.metrics import report
from tests.support import testdb
from tests.support.testdb import ROOT

CASES = [uuid.uuid4() for _ in range(4)]
ROWS = [
    (CASES[0], "evaluate_eligibility", [{"type": "vehicle_rejected", "reason": "owner_mismatch", "origin": "declared"}]),
    (CASES[1], "evaluate_eligibility", [{"type": "vehicle_rejected", "reason": "lien_or_debt", "origin": "registry"}]),
    (CASES[2], "evaluate_eligibility", [{"type": "vehicle_rejected", "reason": "owner_mismatch", "origin": "declared"}]),
    (CASES[3], "evaluate_eligibility", [{"type": "key_quoted", "amount": "1850.00", "quote_id": "KQ"}]),
    (CASES[3], "submit_document", [
        {"type": "validation_recorded", "key": "income", "validation_type": "income", "result": "mismatch"},
        {"type": "validation_recorded", "key": "name@income_proof", "validation_type": "name", "result": "passed"},
    ]),
    (CASES[3], "submit_document", [
        {"type": "validation_recorded", "key": "income", "validation_type": "income", "result": "mismatch"},
        {"type": "validation_recorded", "key": "name@identification", "validation_type": "name",
         "result": "low_confidence"},
    ]),
    (CASES[3], "revoke_ok", [{"type": "ok_revoked", "reason": "Documento alterado"}]),
    (CASES[3], "evaluate_eligibility", [{"type": "key_quoted", "amount": "1850.00", "quote_id": "KQ"}]),  # same case
]
EXPECTED = {
    "vehicle_rejections_by_reason": {"lien_or_debt": 1, "owner_mismatch": 2},
    "false_ok_by_reason": {"Documento alterado": 1},
    "mismatches_by_type": {"income": 2, "name": 1},
    "cases_with_key_quote": 1,
    "audit_entries": len(ROWS),
}


@pytest.fixture
def seeded_db():
    """A fresh database so the counts are exact; rows inserted as actions_rw (insert-only log)."""
    if not testdb.available():
        pytest.skip("Postgres not running; run `make up-db`")
    db = testdb.create()
    with psycopg.connect(db.actions_url, autocommit=True) as conn:
        for case_id, tool, events in ROWS:
            conn.execute(
                "INSERT INTO audit.audit_log (case_id, actor, tool, idempotency_key, outcome, events) "
                "VALUES (%s, 'agent', %s, %s, 'accepted', %s)",
                (case_id, tool, f"k-{uuid.uuid4()}", json.dumps(events)),
            )
    with psycopg.connect(db.admin_url, autocommit=True) as conn:
        conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metrics_probe') THEN
                    CREATE ROLE metrics_probe LOGIN PASSWORD 'probe_pw';
                END IF;
            END $$""")
        conn.execute("GRANT USAGE ON SCHEMA audit TO metrics_probe")
        conn.execute("GRANT SELECT ON audit.audit_log TO metrics_probe")
    yield db
    testdb.drop(db)


@pytest.mark.req("FR-049")
@pytest.mark.req("FR-050")
def test_report_counts_come_from_the_action_log(seeded_db):
    with psycopg.connect(seeded_db.url("metrics_probe:probe_pw")) as conn:  # no access to cases.cases
        assert report(conn).model_dump() == EXPECTED


@pytest.mark.req("FR-049")
def test_metrics_endpoint_is_deterministic(seeded_db, tmp_path):
    settings = Settings(database_url=seeded_db.actions_url, policy_dir=ROOT / "policy",
                        providers_dir=ROOT / "fixtures" / "providers", documents_dir=tmp_path,
                        doc_intel_url="http://127.0.0.1:9", as_of_date=date(2026, 10, 4))
    with TestClient(create_app(settings)) as client:
        first, second = client.get("/metrics").json(), client.get("/metrics").json()
    assert first == second == EXPECTED
