"""The agent cannot read or write the case or the audit log (R-03, Principle III)."""

import psycopg
import pytest


@pytest.mark.req("FR-003")
@pytest.mark.parametrize("table", ["cases.cases", "cases.escalations", "cases.idempotency_keys", "audit.audit_log"])
def test_agent_role_has_no_access_to_case_data(test_db, table):
    with psycopg.connect(test_db.agent_url) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(f"SELECT 1 FROM {table} LIMIT 1")


def test_agent_role_owns_its_schema(test_db):
    with psycopg.connect(test_db.agent_url, autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS agent.probe (id int)")
        conn.execute("DROP TABLE agent.probe")


def test_actions_role_has_no_access_to_agent_schema(test_db):
    with psycopg.connect(test_db.actions_url) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("SELECT 1 FROM agent.processed_messages LIMIT 1")
