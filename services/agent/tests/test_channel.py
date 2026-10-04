"""Channel API against the running compose (contracts/agent-channel.md)."""

import uuid

import pytest


@pytest.mark.req("FR-001")
def test_create_case_starts_empty_and_asks_for_the_full_name(stack):
    http = stack["http"]
    resp = http.post(f"{stack['agent']}/cases")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["stage"] == "eligibility" and body["status"] == "active"
    assert body["reply"].endswith("¿Me compartes tu nombre completo?")

    case = http.get(f"{stack['actions']}/cases/{body['case_id']}").json()
    assert case["state"]["client"]["full_name"] is None
    assert case["state"]["vehicle"]["make"] is None


@pytest.mark.req("FR-001")
def test_repeated_message_with_the_same_key_is_processed_once(stack):
    http = stack["http"]
    case_id = http.post(f"{stack['agent']}/cases").json()["case_id"]
    key = f"smoke-{uuid.uuid4()}"
    first = http.post(f"{stack['agent']}/cases/{case_id}/messages", json={"text": "hola"}, headers={"Idempotency-Key": key})
    version = http.get(f"{stack['actions']}/cases/{case_id}").json()["version"]
    second = http.post(f"{stack['agent']}/cases/{case_id}/messages", json={"text": "hola"}, headers={"Idempotency-Key": key})

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert http.get(f"{stack['actions']}/cases/{case_id}").json()["version"] == version


def test_message_requires_an_idempotency_key(stack):
    http = stack["http"]
    case_id = http.post(f"{stack['agent']}/cases").json()["case_id"]
    assert http.post(f"{stack['agent']}/cases/{case_id}/messages", json={"text": "hola"}).status_code == 422
