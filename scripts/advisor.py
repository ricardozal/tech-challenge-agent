"""Advisor helpers for the demo (make advisor-open-escalations, make advisor-verify)."""

import argparse
import json
import os
import sys
import uuid

import httpx

ACTIONS_URL = os.environ.get("ACTIONS_URL", "http://localhost:8000")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("open-escalations")
    verify = sub.add_parser("verify")
    verify.add_argument("--case", required=True)
    verify.add_argument("--key", required=True)
    verify.add_argument("--justification", required=True)
    args = parser.parse_args()

    with httpx.Client(base_url=ACTIONS_URL, timeout=60) as http:
        if args.command == "open-escalations":
            print(json.dumps(http.get("/escalations", params={"status": "open"}).json(), ensure_ascii=False, indent=2))
            return 0
        case = http.get(f"/cases/{args.case}").json()
        call = {
            "context": {"case_id": args.case, "idempotency_key": f"advisor-{uuid.uuid4()}", "expected_version": case["version"]},
            "input": {"validation_key": args.key, "justification": args.justification, "evidence": ["revision_manual_asesor"]},
        }
        resp = http.post("/tools/verify_validation_manually", json=call, headers={"X-Actor": "advisor"})
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
        return 0 if resp.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
