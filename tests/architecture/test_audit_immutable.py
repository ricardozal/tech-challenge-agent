"""audit.audit_log only accepts inserts (R-06)."""

import psycopg
import pytest

INSERT = (
    "INSERT INTO audit.audit_log (actor, tool, idempotency_key, outcome) "
    "VALUES ('system', 'probe', 'probe-key', 'accepted')"
)


@pytest.fixture
def audit_row(test_db):
    with psycopg.connect(test_db.actions_url, autocommit=True) as conn:
        conn.execute(INSERT)


@pytest.mark.req("FR-008")
@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit.audit_log SET tool = 'tampered'", "DELETE FROM audit.audit_log", "TRUNCATE audit.audit_log"],
)
def test_actions_role_cannot_modify_the_audit_log(test_db, audit_row, statement):
    with psycopg.connect(test_db.actions_url) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(statement)


@pytest.mark.req("FR-008")
@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit.audit_log SET tool = 'tampered'", "DELETE FROM audit.audit_log", "TRUNCATE audit.audit_log"],
)
def test_even_the_admin_cannot_modify_the_audit_log(test_db, audit_row, statement):
    with psycopg.connect(test_db.admin_url) as conn, pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        conn.execute(statement)


def test_inserts_are_allowed(test_db):
    with psycopg.connect(test_db.actions_url, autocommit=True) as conn:
        conn.execute(INSERT)
        assert conn.execute("SELECT count(*) FROM audit.audit_log").fetchone()[0] >= 1
