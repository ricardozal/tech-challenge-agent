"""SC-005: 50 pairs of simultaneous messages on the same case, nothing lost, state consistent (FR-009)."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from scripts.run_demo import ACTIONS_URL, AGENT_URL

PAIRS = 50


@pytest.mark.req("FR-009")
def test_simultaneous_messages_are_serialized_without_losing_data(compose_up):
    with httpx.Client(timeout=60) as http:
        case_id = http.post(f"{AGENT_URL}/cases").json()["case_id"]

        def send(text: str) -> tuple[str, int]:
            key = f"conc-{uuid.uuid4()}"
            resp = http.post(f"{AGENT_URL}/cases/{case_id}/messages", json={"text": text},
                             headers={"Idempotency-Key": key})
            return text, resp.status_code

        results = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            for i in range(PAIRS):
                results += list(pool.map(send, [f"mensaje {i}-a", f"mensaje {i}-b"]))

        case = http.get(f"{ACTIONS_URL}/cases/{case_id}").json()
        audit = http.get(f"{ACTIONS_URL}/cases/{case_id}/audit").json()

    statuses = {status for _, status in results}
    assert statuses <= {200, 409}, statuses  # processed in turn, or an explicit case_busy conflict
    processed = sorted(text for text, status in results if status == 200)
    recorded = sorted(m["text"] for m in case["state"]["messages"] if m["author"] == "client")
    assert recorded == processed  # every processed message recorded exactly once, none lost
    assert len([m for m in case["state"]["messages"] if m["author"] == "agent"]) == len(processed) + 1  # + greeting
    accepted = [e for e in audit if e["outcome"] == "accepted"]
    assert case["version"] == len(accepted)  # one version per accepted action, no lost update
    assert [e["case_version_after"] for e in accepted] == list(range(1, len(accepted) + 1))
    assert not [e for e in audit if e["rejection_code"] == "version_conflict"]
