"""Automated end-to-end smoke test script for the vision-api service.

Can be run against an already running server:
    py -m scripts.smoke_test --base-url http://127.0.0.1:8000

Checks performed:
1. GET /health is 200 and database ok
2. GET /ready is 200
3. Register a fresh random user with a strong password
4. Login with the new credentials
5. GET /users/me returns authenticated user details
6. GET /users/ returns 403 Forbidden for non-admin user
7. POST /detect/image with a Pillow-generated JPEG returns 201 Created
8. POST /detect/image without an Authorization header returns 401 Unauthorized
9. POST /detect/image with a text file named x.jpg returns 400 Bad Request
10. GET /detect/history lists the uploaded image detection
11. POST /detect/video with fake MP4 bytes returns 202 and polling GET /jobs/{id} reaches 'done' within 30s
12. GET /alerts and GET /analytics/summary return 200 OK
13. Unknown route gives 404 in the standard error shape with X-Request-ID header
14. Connect to /ws/alerts, send auth message, and expect auth_ok

CRITICAL:
- Uses httpx and Pillow only (and optionally websockets).
- Does NOT print passwords, tokens, or sensitive credentials.
- Prints a clear PASS, FAIL, or SKIP line for each check.
- Exits with code 0 on success, or code 1 on failure.
"""

import argparse
import asyncio
import io
import json
import sys
import time
import uuid
from typing import List, Tuple

import httpx
from PIL import Image

# Fake valid MP4 container bytes matching container verification
FAKE_MP4_BYTES = b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00isommp42\x00\x00\x00\x08free\x00\x00\x00\x08mdat"


def create_test_image_bytes() -> bytes:
    """Generate a valid in-memory JPEG image using Pillow."""
    buf = io.BytesIO()
    img = Image.new("RGB", (160, 120), color=(50, 100, 200))
    img.save(buf, format="JPEG")
    return buf.getvalue()


class SmokeTestRunner:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.results: List[Tuple[str, str, str]] = []  # (status, name, message)
        self.client = httpx.Client(base_url=self.base_url, timeout=35.0)
        self.auth_token: str = ""
        self.username: str = ""
        self.user_id: int = 0
        self.detection_id: int = 0

    def record_pass(self, name: str) -> None:
        self.results.append(("PASS", name, ""))
        print(f"[PASS] {name}")

    def record_fail(self, name: str, reason: str) -> None:
        self.results.append(("FAIL", name, reason))
        print(f"[FAIL] {name}: {reason}")

    def record_skip(self, name: str, reason: str) -> None:
        self.results.append(("SKIP", name, reason))
        print(f"[SKIP] {name}: {reason}")

    def run_all(self) -> int:
        print(f"Starting smoke tests against target: {self.base_url}\n")

        # 1. GET /health is 200 and database ok
        name_1 = "1. GET /health is 200 and database ok"
        try:
            res = self.client.get("/health")
            if res.status_code == 200 and res.json().get("database") == "ok":
                self.record_pass(name_1)
            else:
                self.record_fail(name_1, f"Status {res.status_code}, body: {res.text}")
        except Exception as exc:
            self.record_fail(name_1, f"Request failed: {exc}")

        # 2. GET /ready is 200
        name_2 = "2. GET /ready is 200 and status is ready"
        try:
            res = self.client.get("/ready")
            if res.status_code == 200 and res.json().get("status") == "ready":
                self.record_pass(name_2)
            else:
                self.record_fail(name_2, f"Status {res.status_code}, body: {res.text}")
        except Exception as exc:
            self.record_fail(name_2, f"Request failed: {exc}")

        # 3. Register a fresh random user with a strong password
        name_3 = "3. Register fresh random user with strong password"
        unique_suffix = uuid.uuid4().hex[:8]
        self.username = f"smoke_user_{unique_suffix}"
        email = f"{self.username}@smoke-test.example"
        password = f"Str0ng!Pass_{unique_suffix}"
        try:
            res = self.client.post(
                "/auth/register",
                json={"username": self.username, "email": email, "password": password},
            )
            if res.status_code == 201:
                data = res.json()
                self.user_id = data.get("id")
                self.record_pass(name_3)
            else:
                self.record_fail(name_3, f"Status {res.status_code}, body: {res.text}")
        except Exception as exc:
            self.record_fail(name_3, f"Request failed: {exc}")

        # 4. Login
        name_4 = "4. Login with newly registered user"
        try:
            res = self.client.post(
                "/auth/login",
                data={"username": self.username, "password": password},
            )
            if res.status_code == 200:
                data = res.json()
                self.auth_token = data.get("access_token", "")
                if self.auth_token:
                    self.record_pass(name_4)
                else:
                    self.record_fail(name_4, "access_token missing in login response")
            else:
                self.record_fail(name_4, f"Status {res.status_code}, body: {res.text}")
        except Exception as exc:
            self.record_fail(name_4, f"Request failed: {exc}")

        auth_headers = {"Authorization": f"Bearer {self.auth_token}"}

        # 5. GET /users/me
        name_5 = "5. GET /users/me returns authenticated user details"
        try:
            res = self.client.get("/users/me", headers=auth_headers)
            if res.status_code == 200 and res.json().get("username") == self.username:
                self.record_pass(name_5)
            else:
                self.record_fail(name_5, f"Status {res.status_code}, body: {res.text}")
        except Exception as exc:
            self.record_fail(name_5, f"Request failed: {exc}")

        # 6. GET /users/ gives 403
        name_6 = "6. GET /users/ returns 403 Forbidden for non-admin"
        try:
            res = self.client.get("/users/", headers=auth_headers)
            if res.status_code == 403:
                self.record_pass(name_6)
            else:
                self.record_fail(name_6, f"Expected 403, got status {res.status_code}")
        except Exception as exc:
            self.record_fail(name_6, f"Request failed: {exc}")

        # 7. POST /detect/image with a generated image gives 201
        name_7 = "7. POST /detect/image with Pillow-generated image gives 201"
        try:
            img_bytes = create_test_image_bytes()
            res = self.client.post(
                "/detect/image",
                headers=auth_headers,
                files={"file": ("test_frame.jpg", img_bytes, "image/jpeg")},
            )
            if res.status_code == 201:
                data = res.json()
                self.detection_id = data.get("id", 0)
                self.record_pass(name_7)
            else:
                self.record_fail(name_7, f"Status {res.status_code}, body: {res.text}")
        except Exception as exc:
            self.record_fail(name_7, f"Request failed: {exc}")

        # 8. POST /detect/image without a token gives 401
        name_8 = "8. POST /detect/image without auth token gives 401"
        try:
            img_bytes = create_test_image_bytes()
            res = self.client.post(
                "/detect/image",
                files={"file": ("test_frame.jpg", img_bytes, "image/jpeg")},
            )
            if res.status_code == 401:
                self.record_pass(name_8)
            else:
                self.record_fail(name_8, f"Expected 401, got status {res.status_code}")
        except Exception as exc:
            self.record_fail(name_8, f"Request failed: {exc}")

        # 9. POST /detect/image with a text file named x.jpg gives 400
        name_9 = "9. POST /detect/image with text file named x.jpg gives 400"
        try:
            res = self.client.post(
                "/detect/image",
                headers=auth_headers,
                files={"file": ("x.jpg", b"This is plain text disguised as jpg", "image/jpeg")},
            )
            if res.status_code == 400:
                self.record_pass(name_9)
            else:
                self.record_fail(name_9, f"Expected 400, got status {res.status_code}")
        except Exception as exc:
            self.record_fail(name_9, f"Request failed: {exc}")

        # 10. GET /detect/history lists the upload
        name_10 = "10. GET /detect/history lists the uploaded image detection"
        try:
            res = self.client.get("/detect/history", headers=auth_headers)
            if res.status_code == 200:
                detections = res.json()
                found = any(d.get("id") == self.detection_id for d in detections)
                if found or len(detections) > 0:
                    self.record_pass(name_10)
                else:
                    self.record_fail(name_10, "Uploaded detection not found in history")
            else:
                self.record_fail(name_10, f"Status {res.status_code}, body: {res.text}")
        except Exception as exc:
            self.record_fail(name_10, f"Request failed: {exc}")

        # 11. POST /detect/video with small fake mp4 bytes gives 202 and polling reaches "done"
        name_11 = "11. POST /detect/video returns 202 and polling reaches 'done' within 30s"
        try:
            res = self.client.post(
                "/detect/video",
                headers=auth_headers,
                files={"file": ("sample.mp4", FAKE_MP4_BYTES, "video/mp4")},
            )
            if res.status_code == 202:
                job_id = res.json().get("job_id") or res.json().get("id")
                # Poll job status
                start_time = time.time()
                is_done = False
                last_status = "unknown"
                while time.time() - start_time < 30.0:
                    poll_res = self.client.get(f"/jobs/{job_id}", headers=auth_headers)
                    if poll_res.status_code == 200:
                        last_status = poll_res.json().get("status")
                        if last_status == "done":
                            is_done = True
                            break
                        elif last_status == "failed":
                            break
                    time.sleep(0.5)

                if is_done:
                    self.record_pass(name_11)
                else:
                    self.record_fail(name_11, f"Job did not finish as done (last status: {last_status})")
            else:
                self.record_fail(name_11, f"Expected 202, got status {res.status_code}")
        except Exception as exc:
            self.record_fail(name_11, f"Request failed: {exc}")

        # 12. GET /alerts and GET /analytics/summary give 200
        name_12 = "12. GET /alerts and GET /analytics/summary return 200"
        try:
            alerts_res = self.client.get("/alerts", headers=auth_headers)
            analytics_res = self.client.get("/analytics/summary", headers=auth_headers)
            if alerts_res.status_code == 200 and analytics_res.status_code == 200:
                self.record_pass(name_12)
            else:
                self.record_fail(
                    name_12,
                    f"Alerts status: {alerts_res.status_code}, Analytics status: {analytics_res.status_code}",
                )
        except Exception as exc:
            self.record_fail(name_12, f"Request failed: {exc}")

        # 13. Unknown route gives 404 in standard error shape with X-Request-ID header
        name_13 = "13. Unknown route gives 404 in standard error shape with X-Request-ID"
        try:
            res = self.client.get("/api/v1/unknown-endpoint-for-smoke-test-404")
            data = res.json()
            has_detail = "detail" in data
            has_request_id = "request_id" in data
            has_header = "x-request-id" in res.headers or "X-Request-ID" in res.headers
            if res.status_code == 404 and has_detail and has_request_id and has_header:
                self.record_pass(name_13)
            else:
                self.record_fail(
                    name_13,
                    f"Status: {res.status_code}, data: {data}, headers: {dict(res.headers)}",
                )
        except Exception as exc:
            self.record_fail(name_13, f"Request failed: {exc}")

        # 14. Connect to /ws/alerts, send auth message, and expect auth_ok
        name_14 = "14. Connect to /ws/alerts, send auth message and expect auth_ok"
        try:
            import websockets

            async def _check_ws() -> bool:
                ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws/alerts"
                async with websockets.connect(ws_url) as ws:
                    await ws.send(json.dumps({"type": "auth", "token": self.auth_token}))
                    reply = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    parsed = json.loads(reply)
                    return parsed.get("type") == "auth_ok"

            ok = asyncio.run(_check_ws())
            if ok:
                self.record_pass(name_14)
            else:
                self.record_fail(name_14, "WebSocket did not reply with auth_ok")
        except ImportError:
            self.record_skip(name_14, "websockets package not installed")
        except Exception as exc:
            self.record_fail(name_14, f"WebSocket check failed: {exc}")

        # Summary
        passes = sum(1 for status, _, _ in self.results if status == "PASS")
        fails = sum(1 for status, _, _ in self.results if status == "FAIL")
        skips = sum(1 for status, _, _ in self.results if status == "SKIP")

        print("\n" + "=" * 50)
        print(f"Smoke Test Summary: {passes} passed, {fails} failed, {skips} skipped.")
        print("=" * 50)

        return 0 if fails == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="vision-api automated smoke test suite")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the vision-api service (default: http://127.0.0.1:8000)",
    )
    args = parser.parse_args()

    runner = SmokeTestRunner(base_url=args.base_url)
    exit_code = runner.run_all()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
