"""Unit and integration tests for PPE compliance contract, rules engine, and API endpoints."""

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.models.detection import Detection
from app.models.user import User
from app.schemas.detection import BoundingBox, DetectedObject, DetectionResult
from app.schemas.ppe import (
    PpeItem,
    PpeWorkerRaw,
    UnassignedItem,
)
from app.services.detector.base import BaseDetector
from app.services.detector.factory import get_detector
from app.services.detector.ppe_dummy import PpeDummyDetector
from app.services.ppe_rules import (
    InvalidDetectorOutput,
    apply_rules,
    build_summary,
    evaluate_worker,
    parse_required_equipment,
    validate_detector_output,
)


def _generate_test_image(
    width: int = 120,
    height: int = 80,
    format: str = "JPEG",
    color: str = "green",
) -> bytes:
    """Generate in-memory encoded image bytes using Pillow."""
    buffer = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buffer, format=format)
    return buffer.getvalue()


def _auth_header(user: User) -> dict[str, str]:
    """Generate Bearer authorization header for a test user."""
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_users(db_session: Session) -> dict[str, User]:
    """Create standard users and admin user."""
    user1 = User(
        email="ppe_user1@example.com",
        username="ppe_user1",
        hashed_password=hash_password("password123"),
        role="user",
        is_active=True,
    )
    user2 = User(
        email="ppe_user2@example.com",
        username="ppe_user2",
        hashed_password=hash_password("password123"),
        role="user",
        is_active=True,
    )
    admin = User(
        email="ppe_admin@example.com",
        username="ppe_admin",
        hashed_password=hash_password("password123"),
        role="admin",
        is_active=True,
    )
    db_session.add_all([user1, user2, admin])
    db_session.commit()
    db_session.refresh(user1)
    db_session.refresh(user2)
    db_session.refresh(admin)
    return {"user1": user1, "user2": user2, "admin": admin}


# ==============================================================================
# 1. Rules Engine Unit Tests
# ==============================================================================

class TestRulesEngine:
    """Tests for pure rules engine functions."""

    def _make_worker(
        self,
        worker_id: int,
        helmet_status: str,
        vest_status: str,
        helmet_conf: float = 0.9,
        vest_conf: float = 0.9,
    ) -> PpeWorkerRaw:
        return PpeWorkerRaw(
            id=worker_id,
            bbox=BoundingBox(x1=10.0, y1=10.0, x2=50.0, y2=100.0),
            person_confidence=0.95,
            helmet=PpeItem(
                status=helmet_status,
                confidence=helmet_conf if helmet_status != "uncertain" else None,
                bbox=BoundingBox(x1=20.0, y1=12.0, x2=40.0, y2=30.0) if helmet_status == "present" else None,
            ),
            vest=PpeItem(
                status=vest_status,
                confidence=vest_conf if vest_status != "uncertain" else None,
                bbox=BoundingBox(x1=15.0, y1=35.0, x2=45.0, y2=70.0) if vest_status == "present" else None,
            ),
            badge_id=None,
            flags=[],
            notes=[],
        )

    @pytest.mark.parametrize(
        "helmet_status,vest_status,expected_verdict,expected_missing",
        [
            ("present", "present", "compliant", []),
            ("missing", "present", "violation", ["helmet"]),
            ("present", "uncertain", "uncertain", []),
            ("missing", "uncertain", "violation", ["helmet"]),
            ("uncertain", "uncertain", "uncertain", []),
        ],
    )
    def test_evaluate_worker_both_required(
        self,
        helmet_status: str,
        vest_status: str,
        expected_verdict: str,
        expected_missing: list[str],
    ) -> None:
        """Test evaluation table when both helmet and vest are required."""
        raw = self._make_worker(1, helmet_status, vest_status)
        evaluated = evaluate_worker(raw, required=["helmet", "vest"])
        assert evaluated.verdict == expected_verdict
        assert evaluated.missing == expected_missing
        assert "Required equipment: helmet, vest." in evaluated.why[-1]

    def test_evaluate_worker_single_item_required(self) -> None:
        """Test that non-required equipment items never affect the verdict."""
        # Helmet required only: missing vest does not cause violation
        raw1 = self._make_worker(1, helmet_status="present", vest_status="missing")
        eval1 = evaluate_worker(raw1, required=["helmet"])
        assert eval1.verdict == "compliant"
        assert eval1.missing == []

        # Vest required only: missing helmet does not cause violation
        raw2 = self._make_worker(2, helmet_status="missing", vest_status="present")
        eval2 = evaluate_worker(raw2, required=["vest"])
        assert eval2.verdict == "compliant"
        assert eval2.missing == []

    def test_key_constraint_unassigned_item_isolation(self) -> None:
        """Test key constraint: three workers, only worker 1 has helmet.

        Verdicts must be compliant, violation, violation.
        An unassigned helmet beside them must never alter any verdict.
        """
        w1 = self._make_worker(1, "present", "present")
        w2 = self._make_worker(2, "missing", "present")
        w3 = self._make_worker(3, "missing", "present")

        det_result = DetectionResult(
            objects=[
                DetectedObject(label="person", confidence=0.9, bbox=w1.bbox),
                DetectedObject(label="person", confidence=0.9, bbox=w2.bbox),
                DetectedObject(label="person", confidence=0.9, bbox=w3.bbox),
                DetectedObject(label="helmet", confidence=0.9, bbox=BoundingBox(x1=100.0, y1=100.0, x2=120.0, y2=120.0)),
            ],
            total_count=4,
            image_width=640,
            image_height=480,
            inference_ms=10.0,
            detector_name="test",
            extra={
                "schema": "ppe.v1",
                "workers": [w1.model_dump(), w2.model_dump(), w3.model_dump()],
                "unassigned_items": [
                    {
                        "label": "helmet",
                        "confidence": 0.95,
                        "bbox": {"x1": 100.0, "y1": 100.0, "x2": 120.0, "y2": 120.0},
                        "reason": "helmet is not on a head",
                    }
                ],
                "pipeline": {},
            },
        )

        applied = apply_rules(det_result, required=["helmet"])
        workers = applied.extra["workers"]
        assert len(workers) == 3
        assert workers[0]["verdict"] == "compliant"
        assert workers[1]["verdict"] == "violation"
        assert workers[2]["verdict"] == "violation"

        summary = applied.extra["summary"]
        assert summary["workers"] == 3
        assert summary["compliant"] == 1
        assert summary["violations"] == 2
        assert summary["uncertain"] == 0
        assert summary["missing_helmet"] == 2
        assert summary["violating_worker_ids"] == [2, 3]

    def test_summary_counts_consistency(self) -> None:
        """Test summary totals always equal compliant + violations + uncertain."""
        w1 = evaluate_worker(self._make_worker(1, "present", "present"), ["helmet", "vest"])
        w2 = evaluate_worker(self._make_worker(2, "missing", "present"), ["helmet", "vest"])
        w3 = evaluate_worker(self._make_worker(3, "uncertain", "present"), ["helmet", "vest"])
        summary = build_summary([w1, w2, w3], ["helmet", "vest"])

        assert summary.workers == 3
        assert summary.workers == summary.compliant + summary.violations + summary.uncertain
        assert summary.compliance_rate == round(1 / 3, 3)

    def test_summary_zero_workers(self) -> None:
        """Test summary compliance_rate is None when there are no workers."""
        summary = build_summary([], ["helmet", "vest"])
        assert summary.workers == 0
        assert summary.compliance_rate is None

    @pytest.mark.parametrize(
        "input_val,expected",
        [
            ("helmet,vest", ["helmet", "vest"]),
            ("vest, helmet", ["helmet", "vest"]),
            ("HELMET", ["helmet"]),
            ("VEST", ["vest"]),
            ("helmet, vest, helmet", ["helmet", "vest"]),
            ("  vest ,  helmet  ", ["helmet", "vest"]),
        ],
    )
    def test_parse_required_equipment_success(self, input_val: str, expected: list[str]) -> None:
        """Test parsing valid equipment lists preserving canonical ordering."""
        assert parse_required_equipment(input_val) == expected

    @pytest.mark.parametrize("invalid_val", ["hat", "", "   ", "helmet,boots", "invalid"])
    def test_parse_required_equipment_invalid(self, invalid_val: str) -> None:
        """Test invalid equipment lists raise ValueError."""
        with pytest.raises(ValueError):
            parse_required_equipment(invalid_val)


# ==============================================================================
# 2. validate_detector_output Tests
# ==============================================================================

class TestValidateDetectorOutput:
    """Tests contract validation for detector outputs."""

    def _valid_result(self) -> DetectionResult:
        return DetectionResult(
            objects=[],
            total_count=1,
            image_width=640,
            image_height=480,
            inference_ms=12.0,
            detector_name="ppe-dummy",
            extra={
                "schema": "ppe.v1",
                "workers": [
                    {
                        "id": 1,
                        "bbox": {"x1": 50.0, "y1": 50.0, "x2": 150.0, "y2": 300.0},
                        "person_confidence": 0.92,
                        "helmet": {
                            "status": "present",
                            "confidence": 0.88,
                            "bbox": {"x1": 70.0, "y1": 55.0, "x2": 130.0, "y2": 110.0},
                        },
                        "vest": {
                            "status": "present",
                            "confidence": 0.91,
                            "bbox": {"x1": 65.0, "y1": 120.0, "x2": 135.0, "y2": 210.0},
                        },
                        "badge_id": 12,
                        "flags": ["low_light"],
                        "notes": ["Clear lighting."],
                    }
                ],
                "unassigned_items": [],
                "pipeline": {},
            },
        )

    def test_valid_output_passes(self) -> None:
        """Test valid result passes validation without exception."""
        result = self._valid_result()
        validate_detector_output(result, 640, 480)

    def test_reject_wrong_schema(self) -> None:
        """Test rejection of invalid schema tag."""
        result = self._valid_result()
        result.extra["schema"] = "ppe.v2"
        with pytest.raises(InvalidDetectorOutput, match="Invalid schema"):
            validate_detector_output(result, 640, 480)

    def test_reject_box_outside_image(self) -> None:
        """Test rejection of bounding boxes exceeding image dimensions."""
        result = self._valid_result()
        result.extra["workers"][0]["bbox"]["x2"] = 700.0
        with pytest.raises(InvalidDetectorOutput, match="exceeds image boundaries"):
            validate_detector_output(result, 640, 480)

    def test_reject_inverted_coordinates(self) -> None:
        """Test rejection of x1 >= x2."""
        result = self._valid_result()
        result.extra["workers"][0]["bbox"]["x1"] = 200.0
        result.extra["workers"][0]["bbox"]["x2"] = 100.0
        with pytest.raises(InvalidDetectorOutput, match="inverted coordinates"):
            validate_detector_output(result, 640, 480)

    def test_reject_duplicate_ids(self) -> None:
        """Test rejection of duplicate worker IDs."""
        result = self._valid_result()
        w1 = result.extra["workers"][0]
        w2 = dict(w1)
        result.extra["workers"].append(w2)
        with pytest.raises(InvalidDetectorOutput, match="Duplicate worker id"):
            validate_detector_output(result, 640, 480)

    def test_reject_confidence_above_one(self) -> None:
        """Test rejection of confidence > 1.0."""
        result = self._valid_result()
        result.extra["workers"][0]["person_confidence"] = 1.05
        with pytest.raises(InvalidDetectorOutput, match="person_confidence out of range"):
            validate_detector_output(result, 640, 480)

    def test_reject_invalid_flag(self) -> None:
        """Test rejection of unrecognized flags."""
        result = self._valid_result()
        result.extra["workers"][0]["flags"] = ["flying_helmet"]
        with pytest.raises(InvalidDetectorOutput, match="unrecognized flag"):
            validate_detector_output(result, 640, 480)

    def test_reject_badge_id_out_of_range(self) -> None:
        """Test rejection of badge_id >= 50."""
        result = self._valid_result()
        result.extra["workers"][0]["badge_id"] = 50
        with pytest.raises(InvalidDetectorOutput, match="badge_id.*out of range"):
            validate_detector_output(result, 640, 480)


# ==============================================================================
# 3. PpeDummyDetector Tests
# ==============================================================================

class TestPpeDummyDetector:
    """Tests for PpeDummyDetector."""

    def test_deterministic_output(self) -> None:
        """Test running twice on identical image produces identical results."""
        detector = PpeDummyDetector()
        detector.load()

        img = Image.new("RGB", (320, 240), color="red")
        res1 = detector.detect(img)
        res2 = detector.detect(img)

        assert res1.total_count == res2.total_count
        assert res1.extra["workers"] == res2.extra["workers"]
        assert res1.extra["unassigned_items"] == res2.extra["unassigned_items"]

    @pytest.mark.parametrize("size", [(32, 32), (640, 480), (6000, 6000)])
    def test_boxes_valid_at_various_sizes(self, size: tuple[int, int]) -> None:
        """Test bounding boxes remain valid across tiny, standard, and large sizes."""
        w, h = size
        detector = PpeDummyDetector()
        detector.load()
        img = Image.new("RGB", (w, h), color="gray")

        result = detector.detect(img)
        validate_detector_output(result, w, h)

    def test_bands_placement(self) -> None:
        """Test helmet is in upper 25% and vest is in 25-65% band of person box."""
        detector = PpeDummyDetector()
        detector.load()
        img = Image.new("RGB", (640, 480), color="blue")
        result = detector.detect(img)

        for worker in result.extra["workers"]:
            p = worker["bbox"]
            p_h = p["y2"] - p["y1"]

            helmet = worker["helmet"]
            if helmet["status"] == "present":
                hb = helmet["bbox"]
                assert hb["y1"] >= p["y1"] - 1.0
                assert hb["y2"] <= p["y1"] + 0.25 * p_h + 1.0
                assert hb["x1"] >= p["x1"] - 1.0
                assert hb["x2"] <= p["x2"] + 1.0

            vest = worker["vest"]
            if vest["status"] == "present":
                vb = vest["bbox"]
                assert vb["y1"] >= p["y1"] + 0.25 * p_h - 1.0
                assert vb["y2"] <= p["y1"] + 0.65 * p_h + 1.0
                assert vb["x1"] >= p["x1"] - 1.0
                assert vb["x2"] <= p["x2"] + 1.0

    def test_scenario_coverage_over_200_images(self) -> None:
        """Test that over at least 200 synthetic images, all scenarios appear at least once."""
        detector = PpeDummyDetector()
        detector.load()

        seen_scenarios = set()

        for idx in range(250):
            # Deterministic variation of size and pixels
            w = 50 + (idx * 17) % 300
            h = 50 + (idx * 23) % 300
            color = (idx % 256, (idx * 3) % 256, (idx * 7) % 256)
            img = Image.new("RGB", (w, h), color=color)

            res = detector.detect(img)
            validate_detector_output(res, w, h)

            for worker in res.extra["workers"]:
                h_status = worker["helmet"]["status"]
                v_status = worker["vest"]["status"]
                flags = worker.get("flags", [])

                if "helmet_in_hand" in flags:
                    seen_scenarios.add("helmet_in_hand")
                elif "hi_vis_not_vest" in flags:
                    seen_scenarios.add("hi_vis_not_vest")
                elif h_status == "uncertain":
                    seen_scenarios.add("head_hidden")
                elif v_status == "uncertain":
                    seen_scenarios.add("torso_hidden")
                elif h_status == "present" and v_status == "present":
                    seen_scenarios.add("all_ppe")
                elif h_status == "missing" and v_status == "present":
                    seen_scenarios.add("no_helmet")
                elif h_status == "present" and v_status == "missing":
                    seen_scenarios.add("no_vest")
                elif h_status == "missing" and v_status == "missing":
                    seen_scenarios.add("no_ppe")

        expected_scenarios = {
            "all_ppe",
            "no_helmet",
            "no_vest",
            "no_ppe",
            "helmet_in_hand",
            "hi_vis_not_vest",
            "head_hidden",
            "torso_hidden",
        }
        missing = expected_scenarios - seen_scenarios
        assert not missing, f"Missing scenarios in 250 images: {missing}"

    def test_factory_returns_ppe_dummy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_detector returns PpeDummyDetector when DETECTOR_BACKEND='ppe_dummy'."""
        settings = get_settings()
        monkeypatch.setattr(settings, "DETECTOR_BACKEND", "ppe_dummy")
        det = get_detector(settings)
        assert isinstance(det, PpeDummyDetector)
        assert det.name == "ppe-dummy"


# ==============================================================================
# 4. POST /detect/image & Error Handling Tests
# ==============================================================================

class TestDetectImageEndpoint:
    """Tests for POST /detect/image with PPE backend."""

    def test_upload_image_ppe_defaults(
        self,
        client: TestClient,
        test_users: dict[str, User],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test image detection with ppe_dummy detector returns ppe.v1 schema."""
        settings = get_settings()
        monkeypatch.setattr(settings, "DETECTOR_BACKEND", "ppe_dummy")
        client.app.state.detector = get_detector(settings)
        client.app.state.detector.load()

        user = test_users["user1"]
        img_bytes = _generate_test_image(width=300, height=200)

        response = client.post(
            "/detect/image",
            headers=_auth_header(user),
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        assert response.status_code == 201
        data = response.json()
        results = data["results"]
        extra = results["extra"]

        assert extra["schema"] == "ppe.v1"
        assert "summary" in extra
        summary = extra["summary"]
        assert summary["workers"] == len(extra["workers"])
        assert summary["compliant"] + summary["violations"] + summary["uncertain"] == summary["workers"]
        assert data["total_count"] == summary["workers"]

    def test_required_equipment_override_and_camera_name(
        self,
        client: TestClient,
        test_users: dict[str, User],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test overriding required_equipment to helmet only and providing camera_name."""
        settings = get_settings()
        monkeypatch.setattr(settings, "DETECTOR_BACKEND", "ppe_dummy")
        client.app.state.detector = get_detector(settings)
        client.app.state.detector.load()

        user = test_users["user1"]
        img_bytes = _generate_test_image(width=300, height=200)

        response = client.post(
            "/detect/image",
            headers=_auth_header(user),
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
            data={"required_equipment": "helmet", "camera_name": "Gate-1 South"},
        )
        assert response.status_code == 201
        extra = response.json()["results"]["extra"]
        assert extra["required_equipment"] == ["helmet"]
        assert extra["camera_name"] == "Gate-1 South"

    def test_invalid_required_equipment_returns_422(
        self,
        client: TestClient,
        test_users: dict[str, User],
    ) -> None:
        """Test invalid required_equipment values return HTTP 422 with correct loc."""
        user = test_users["user1"]
        img_bytes = _generate_test_image()

        # Unknown equipment item
        res_bad = client.post(
            "/detect/image",
            headers=_auth_header(user),
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
            data={"required_equipment": "hat"},
        )
        assert res_bad.status_code == 422
        bad_detail = res_bad.json()["detail"]
        assert any("required_equipment" in loc for err in bad_detail for loc in [err.get("loc", [])])

        # Empty equipment string
        res_empty = client.post(
            "/detect/image",
            headers=_auth_header(user),
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
            data={"required_equipment": ""},
        )
        assert res_empty.status_code == 422
        empty_detail = res_empty.json()["detail"]
        assert any("required_equipment" in loc for err in empty_detail for loc in [err.get("loc", [])])

    def test_invalid_camera_name_returns_422(
        self,
        client: TestClient,
        test_users: dict[str, User],
    ) -> None:
        """Test invalid camera_name characters return HTTP 422 with correct loc."""
        user = test_users["user1"]
        img_bytes = _generate_test_image()

        res = client.post(
            "/detect/image",
            headers=_auth_header(user),
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
            data={"camera_name": "Gate#1 @BadChars!"},
        )
        assert res.status_code == 422
        detail = res.json()["detail"]
        assert any("camera_name" in loc for err in detail for loc in [err.get("loc", [])])

    def test_malformed_detector_output_returns_clean_500(
        self,
        client: TestClient,
        test_users: dict[str, User],
    ) -> None:
        """Test detector returning invalid PPE structure returns sanitized 500 error."""
        class MalformedPpeDetector(BaseDetector):
            name = "malformed-ppe"
            _is_loaded = True

            def detect(self, image: Image.Image) -> DetectionResult:
                return DetectionResult(
                    objects=[],
                    total_count=0,
                    image_width=image.width,
                    image_height=image.height,
                    inference_ms=5.0,
                    detector_name=self.name,
                    extra={
                        "schema": "ppe.v1",
                        "workers": [{"id": 1, "bbox": {"x1": 50.0, "y1": 50.0, "x2": 40.0, "y2": 30.0}}],
                    },
                )

        client.app.state.detector = MalformedPpeDetector()
        user = test_users["user1"]
        img_bytes = _generate_test_image()

        res = client.post(
            "/detect/image",
            headers=_auth_header(user),
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        assert res.status_code == 500
        data = res.json()
        assert data["detail"] == "Detector returned an invalid result"
        assert "request_id" in data

    def test_generic_dummy_returns_old_shape(
        self,
        client: TestClient,
        test_users: dict[str, User],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that generic DummyDetector preserves its original non-PPE output."""
        settings = get_settings()
        monkeypatch.setattr(settings, "DETECTOR_BACKEND", "dummy")
        client.app.state.detector = get_detector(settings)
        client.app.state.detector.load()

        user = test_users["user1"]
        img_bytes = _generate_test_image()

        res = client.post(
            "/detect/image",
            headers=_auth_header(user),
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        assert res.status_code == 201
        data = res.json()["results"]
        # Generic dummy does not have ppe.v1 schema in extra
        assert data["extra"].get("schema") != "ppe.v1"


# ==============================================================================
# 5. GET /detect/config Tests
# ==============================================================================

class TestDetectConfigEndpoint:
    """Tests for GET /detect/config endpoint."""

    def test_config_requires_authentication(self, client: TestClient) -> None:
        """Test GET /detect/config requires Bearer token."""
        res = client.get("/detect/config")
        assert res.status_code == 401

    def test_config_returns_expected_fields(
        self,
        client: TestClient,
        test_users: dict[str, User],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test GET /detect/config returns expected schema and fields."""
        settings = get_settings()
        monkeypatch.setattr(settings, "DETECTOR_BACKEND", "ppe_dummy")
        client.app.state.detector = get_detector(settings)
        client.app.state.detector.load()

        user = test_users["user1"]
        res = client.get("/detect/config", headers=_auth_header(user))
        assert res.status_code == 200

        data = res.json()
        assert "detector" in data
        assert data["detector"]["name"] == "ppe-dummy"
        assert data["detector"]["is_placeholder"] is True
        assert data["detector"]["loaded"] is True

        assert "ppe" in data
        assert data["ppe"]["schema"] == "ppe.v1"
        assert "helmet" in data["ppe"]["supported_equipment"]
        assert "vest" in data["ppe"]["supported_equipment"]
        assert data["ppe"]["default_required_equipment"] == ["helmet", "vest"]

        assert "upload" in data
        assert data["upload"]["max_image_mb"] == settings.MAX_UPLOAD_MB
        assert "confidence_threshold" in data

    def test_config_not_treated_as_numeric_id(
        self,
        client: TestClient,
        test_users: dict[str, User],
    ) -> None:
        """Test that the route /detect/config matches the config endpoint, not /{detection_id}."""
        user = test_users["user1"]
        res = client.get("/detect/config", headers=_auth_header(user))
        assert res.status_code == 200
        # If it were matched against /{detection_id}, it would return 422 or 404
        assert "detector" in res.json()


# ==============================================================================
# 6. GET /detect/{id}/image Tests
# ==============================================================================

class TestDetectImageDownloadEndpoint:
    """Tests for GET /detect/{id}/image endpoint."""

    def test_owner_gets_image_with_cache_control(
        self,
        client: TestClient,
        test_users: dict[str, User],
    ) -> None:
        """Test record owner gets 200, image content type, and Cache-Control header."""
        user = test_users["user1"]
        img_bytes = _generate_test_image(format="JPEG")

        post_res = client.post(
            "/detect/image",
            headers=_auth_header(user),
            files={"file": ("source.jpg", img_bytes, "image/jpeg")},
        )
        assert post_res.status_code == 201
        det_id = post_res.json()["id"]

        get_res = client.get(f"/detect/{det_id}/image", headers=_auth_header(user))
        assert get_res.status_code == 200
        assert get_res.headers.get("content-type", "").startswith("image/")
        assert get_res.headers.get("cache-control") == "private, max-age=300"
        assert len(get_res.content) > 0

    def test_another_user_gets_404(
        self,
        client: TestClient,
        test_users: dict[str, User],
    ) -> None:
        """Test non-owner non-admin user receives 404 for another user's image."""
        user1 = test_users["user1"]
        user2 = test_users["user2"]
        img_bytes = _generate_test_image()

        post_res = client.post(
            "/detect/image",
            headers=_auth_header(user1),
            files={"file": ("source.jpg", img_bytes, "image/jpeg")},
        )
        det_id = post_res.json()["id"]

        get_res = client.get(f"/detect/{det_id}/image", headers=_auth_header(user2))
        assert get_res.status_code == 404

    def test_admin_gets_200(
        self,
        client: TestClient,
        test_users: dict[str, User],
    ) -> None:
        """Test administrator can download any user's detection image."""
        user1 = test_users["user1"]
        admin = test_users["admin"]
        img_bytes = _generate_test_image()

        post_res = client.post(
            "/detect/image",
            headers=_auth_header(user1),
            files={"file": ("source.jpg", img_bytes, "image/jpeg")},
        )
        det_id = post_res.json()["id"]

        get_res = client.get(f"/detect/{det_id}/image", headers=_auth_header(admin))
        assert get_res.status_code == 200
        assert get_res.headers.get("content-type", "").startswith("image/")

    def test_missing_image_file_returns_404(
        self,
        client: TestClient,
        test_users: dict[str, User],
        db_session: Session,
    ) -> None:
        """Test detection pointing to missing file on disk returns 404."""
        user = test_users["user1"]
        det = Detection(
            user_id=user.id,
            source_type="image",
            file_path="uploads/images/nonexistent_file.jpg",
            detector_name="dummy",
            total_count=0,
            results={"objects": [], "total_count": 0, "image_width": 100, "image_height": 100, "inference_ms": 1.0, "detector_name": "dummy"},
        )
        db_session.add(det)
        db_session.commit()
        db_session.refresh(det)

        res = client.get(f"/detect/{det.id}/image", headers=_auth_header(user))
        assert res.status_code == 404

    def test_video_detection_returns_404(
        self,
        client: TestClient,
        test_users: dict[str, User],
        db_session: Session,
    ) -> None:
        """Test detection with source_type='video' returns 404."""
        user = test_users["user1"]
        det = Detection(
            user_id=user.id,
            source_type="video",
            file_path="uploads/videos/some_video.mp4",
            detector_name="dummy",
            total_count=0,
            results={"objects": [], "total_count": 0, "image_width": 100, "image_height": 100, "inference_ms": 1.0, "detector_name": "dummy"},
        )
        db_session.add(det)
        db_session.commit()
        db_session.refresh(det)

        res = client.get(f"/detect/{det.id}/image", headers=_auth_header(user))
        assert res.status_code == 404

    def test_stored_path_outside_upload_dir_returns_404(
        self,
        client: TestClient,
        test_users: dict[str, User],
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """Test path traversal or file stored outside UPLOAD_DIR returns 404."""
        user = test_users["user1"]
        outside_file = tmp_path / "outside.jpg"
        outside_file.write_bytes(b"dummy image data")

        det = Detection(
            user_id=user.id,
            source_type="image",
            file_path=str(outside_file),
            detector_name="dummy",
            total_count=0,
            results={"objects": [], "total_count": 0, "image_width": 100, "image_height": 100, "inference_ms": 1.0, "detector_name": "dummy"},
        )
        db_session.add(det)
        db_session.commit()
        db_session.refresh(det)

        res = client.get(f"/detect/{det.id}/image", headers=_auth_header(user))
        assert res.status_code == 404
