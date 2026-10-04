"""One turn at a time per case (R-04, FR-009)."""

import asyncio
import uuid

import psycopg
import pytest

from agent.turn_lock import CaseBusy, TurnStore

pytestmark = pytest.mark.req("FR-009")


@pytest.fixture
async def store(test_db):
    s = TurnStore(test_db.agent_url, poll_s=0.01)
    await s.open()
    yield s
    await s.close()


async def test_second_turn_waits_for_the_first(store):
    case_id = uuid.uuid4()
    order: list[str] = []

    async def turn(name: str, hold: float) -> None:
        async with store.case_turn(case_id, timeout_s=2):
            order.append(f"{name}:start")
            await asyncio.sleep(hold)
            order.append(f"{name}:end")

    first = asyncio.create_task(turn("a", 0.2))
    await asyncio.sleep(0.05)
    await turn("b", 0)
    await first
    assert order == ["a:start", "a:end", "b:start", "b:end"]


async def test_second_turn_gives_up_after_the_timeout(store):
    case_id = uuid.uuid4()
    async with store.case_turn(case_id, timeout_s=1):
        with pytest.raises(CaseBusy):
            async with store.case_turn(case_id, timeout_s=0.1):
                pass
    async with store.case_turn(case_id, timeout_s=0.1):  # released afterwards
        pass


async def test_different_cases_do_not_block_each_other(store):
    async with store.case_turn(uuid.uuid4(), timeout_s=1):
        async with store.case_turn(uuid.uuid4(), timeout_s=0.1):
            pass


async def test_agent_lock_does_not_block_the_actions_api_lock(store, test_db):
    case_id = str(uuid.uuid4())
    async with store.case_turn(case_id, timeout_s=1):
        with psycopg.connect(test_db.actions_url) as conn:
            got = conn.execute("SELECT pg_try_advisory_xact_lock(2, hashtext(%s))", (case_id,)).fetchone()[0]
    assert got is True


async def test_processed_messages_round_trip(store):
    case_id = uuid.uuid4()
    assert await store.get_processed(case_id, "k") is None
    await store.put_processed(case_id, "k", {"reply": "hola"})
    await store.put_processed(case_id, "k", {"reply": "otra"})  # first one wins
    assert await store.get_processed(case_id, "k") == {"reply": "hola"}
