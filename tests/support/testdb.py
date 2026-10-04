"""Throwaway Postgres database per test session, created from db/init.sql."""

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
HOST = os.environ.get("TEST_DB_HOST", "localhost:55432")
ADMIN = os.environ.get("TEST_DB_ADMIN", "app_admin:admin_pw")


@dataclass(frozen=True)
class TestDatabase:
    name: str

    def url(self, user: str) -> str:
        return f"postgresql://{user}@{HOST}/{self.name}"

    @property
    def admin_url(self) -> str:
        return self.url(ADMIN)

    @property
    def actions_url(self) -> str:
        return self.url("actions_rw:actions_pw")

    @property
    def agent_url(self) -> str:
        return self.url("agent_rw:agent_pw") + "?options=-csearch_path%3Dagent"


def available() -> bool:
    try:
        with psycopg.connect(f"postgresql://{ADMIN}@{HOST}/app", connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


def create() -> TestDatabase:
    db = TestDatabase(f"test_{uuid.uuid4().hex[:10]}")
    with psycopg.connect(f"postgresql://{ADMIN}@{HOST}/app", autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{db.name}"')
    with psycopg.connect(db.admin_url, autocommit=True) as conn:
        conn.execute((ROOT / "db" / "init.sql").read_text(encoding="utf-8"))
    return db


def drop(db: TestDatabase) -> None:
    with psycopg.connect(f"postgresql://{ADMIN}@{HOST}/app", autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{db.name}" WITH (FORCE)')
