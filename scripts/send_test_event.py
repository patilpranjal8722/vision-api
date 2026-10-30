"""Test helper script for validating the CV microservice event intake endpoint.

Can be run as:
    py -m scripts.send_test_event --url http://127.0.0.1:8000 --key YOUR_EVENTS_KEY

Never outputs or logs the secret key.
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
import httpx


def now_utc_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format with trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send test CV microservice events to backend")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="Base URL of backend service (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--key",
        required=True,
        help="CV_EVENTS_API_KEY for X-Service-Key authentication",
    )
    args = parser.parse_args()

    endpoint = f"{args.url.rstrip('/')}/internal/api/v1/cv/events"
    auth_headers = {"X-Service-Key": args.key, "Content-Type": "application/json"}
    bad_auth_headers = {"X-Service-Key": "invalid-wrong-service-key-for-test", "Content-Type": "application/json"}

    print(f"Target intake endpoint: {endpoint}")
    print("Beginning event intake tests...\n")

    client = httpx.Client(timeout=10.0)

    # 1. Valid job.progress event
    event_id_1 = str(uuid.uuid4())
    payload_1 = {
        "contract_version": "1.0",
        "event_id": event_id_1,
        "type": "job.progress",
        "occurred_at": now_utc_iso(),
        "job_id": "test-cv-job-8842",
        "external_job_id": "test-ext-job-001:1",
        "sequence": 1,
        "data": {
            "progress": 35,
            "frames_processed": 210,
        },
    }

    print("Step 1: Sending valid job.progress event...")
    res_1 = client.post(endpoint, headers=auth_headers, json=payload_1)
    print(f"HTTP Status: {res_1.status_code}")
    print(f"Response: {res_1.text}\n")

    # 2. Duplicate event submission (same event_id)
    print("Step 2: Resending the exact same event (expecting 'duplicate')...")
    res_2 = client.post(endpoint, headers=auth_headers, json=payload_1)
    print(f"HTTP Status: {res_2.status_code}")
    print(f"Response: {res_2.text}\n")

    # 3. Batch with one valid worker.status and one invalid event (missing required fields)
    event_id_valid = str(uuid.uuid4())
    event_id_invalid = str(uuid.uuid4())
    payload_3 = {
        "contract_version": "1.0",
        "events": [
            {
                "contract_version": "1.0",
                "event_id": event_id_valid,
                "type": "worker.status",
                "occurred_at": now_utc_iso(),
                "job_id": "test-cv-job-8842",
                "sequence": 2,
                "data": {
                    "track_id": 101,
                    "verdict": "compliant",
                    "items": {
                        "helmet": {"status": "present", "confidence": 0.94},
                        "vest": {"status": "present", "confidence": 0.91},
                    },
                    "flags": [],
                    "why": ["Worker wearing helmet and vest."],
                    "bbox": {"x1": 120.0, "y1": 60.0, "x2": 260.0, "y2": 420.0},
                    "frame_index": 210,
                    "timestamp_s": 8.4,
                },
            },
            {
                "contract_version": "1.0",
                "event_id": event_id_invalid,
                "type": "violation.confirmed",
                "occurred_at": now_utc_iso(),
                "job_id": "test-cv-job-8842",
                "sequence": 3,
                "data": {
                    "violation_key": "vkey-invalid",
                    "track_id": 102,
                    "missing_items": [],  # Invalid: empty missing_items must be rejected
                    "started_at": now_utc_iso(),
                    "started_s": 8.4,
                },
            },
        ],
    }

    print("Step 3: Sending batch with 1 valid and 1 invalid event (expecting accepted + rejected)...")
    res_3 = client.post(endpoint, headers=auth_headers, json=payload_3)
    print(f"HTTP Status: {res_3.status_code}")
    print(f"Response: {res_3.text}\n")

    # 4. Request with wrong key
    payload_4 = {
        "contract_version": "1.0",
        "event_id": str(uuid.uuid4()),
        "type": "job.progress",
        "occurred_at": now_utc_iso(),
        "job_id": "test-cv-job-8842",
        "data": {"progress": 50},
    }

    print("Step 4: Sending request with wrong X-Service-Key (expecting 401)...")
    res_4 = client.post(endpoint, headers=bad_auth_headers, json=payload_4)
    print(f"HTTP Status: {res_4.status_code}")
    print(f"Response: {res_4.text}\n")

    # 5. Body with unsupported contract_version "2.0"
    payload_5 = {
        "contract_version": "2.0",
        "event_id": str(uuid.uuid4()),
        "type": "job.progress",
        "occurred_at": now_utc_iso(),
        "job_id": "test-cv-job-8842",
        "data": {"progress": 50},
    }

    print("Step 5: Sending request with unsupported contract_version '2.0' (expecting 422)...")
    res_5 = client.post(endpoint, headers=auth_headers, json=payload_5)
    print(f"HTTP Status: {res_5.status_code}")
    print(f"Response: {res_5.text}\n")

    print("All test event scenarios completed.")


if __name__ == "__main__":
    main()
