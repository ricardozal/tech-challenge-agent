"""One turn at a time per case (R-04, FR-009) and channel idempotency.

The lock is a session advisory lock in namespace 1 on the agent's own connection (role agent_rw);
actions_api uses namespace 2, so the agent holding the case never blocks its own tool calls.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

AGENT_LOCK_NS = 1


class CaseBusy(RuntimeError):
    pass


class TurnStore:
    def __init__(self, url: str, poll_s: float = 0.05):
        self.pool = AsyncConnectionPool(
            url, min_size=1, max_size=20, open=False, kwargs={"autocommit": True, "row_factory": dict_row}
        )
        self.poll_s = poll_s

    async def open(self) -> None:
        await self.pool.open(wait=True)

    async def close(self) -> None:
        await self.pool.close()

    @asynccontextmanager
    async def case_turn(self, case_id: UUID | str, timeout_s: float) -> AsyncIterator[None]:
        key = str(case_id)
        async with self.pool.connection() as conn:
            deadline = time.monotonic() + timeout_s
            while True:
                row = await (
                    await conn.execute("SELECT pg_try_advisory_lock(%s, hashtext(%s)) AS ok", (AGENT_LOCK_NS, key))
                ).fetchone()
                if row["ok"]:
                    break
                if time.monotonic() >= deadline:
                    raise CaseBusy(key)
                await asyncio.sleep(self.poll_s)
            try:
                yield
            finally:
                await conn.execute("SELECT pg_advisory_unlock(%s, hashtext(%s))", (AGENT_LOCK_NS, key))

    async def get_processed(self, case_id: UUID | str, key: str) -> dict[str, Any] | None:
        async with self.pool.connection() as conn:
            row = await (
                await conn.execute(
                    "SELECT response FROM agent.processed_messages WHERE case_id = %s AND idempotency_key = %s",
                    (str(case_id), key),
                )
            ).fetchone()
        return row["response"] if row else None

    async def put_processed(self, case_id: UUID | str, key: str, response: dict[str, Any]) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO agent.processed_messages (case_id, idempotency_key, response) VALUES (%s, %s, %s) "
                "ON CONFLICT DO NOTHING",
                (str(case_id), key, Jsonb(response)),
            )
