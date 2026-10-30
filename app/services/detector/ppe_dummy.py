"""PPE Dummy detector implementation returning deterministic mock PPE inspection results."""

import hashlib
import random
import time
from typing import List, Optional
from PIL import Image

from app.core.config import get_settings
from app.schemas.detection import BoundingBox, DetectedObject, DetectionResult
from app.schemas.ppe import (
    PpeExtraRaw,
    PpeItem,
    PpePipelineInfo,
    PpeWorkerRaw,
    UnassignedItem,
)
from app.services.detector.base import BaseDetector


class PpeDummyDetector(BaseDetector):
    """Deterministic simulated detector returning rich PPE worker inspection results.

    Simulates 1 to 5 workers across vertical image slots with realistic equipment
    detections, occlusion flags, visual badge IDs, and unassigned items.
    Does not require any PyTorch, OpenCV, or ML weights.
    """

    def __init__(self, confidence_threshold: Optional[float] = None) -> None:
        self.name: str = "ppe-dummy"
        self._is_loaded: bool = False
        if confidence_threshold is None:
            self.confidence_threshold = get_settings().CONFIDENCE_THRESHOLD
        else:
            self.confidence_threshold = confidence_threshold

    @property
    def is_placeholder(self) -> bool:
        """Indicate that this is a placeholder/mock detector implementation."""
        return True

    @property
    def is_loaded(self) -> bool:
        """Return True after load() has been invoked."""
        return self._is_loaded

    def load(self) -> None:
        """Simulate loading model weights into memory."""
        self._is_loaded = True

    def detect(self, image: Image.Image) -> DetectionResult:
        """Generate deterministic PPE compliance detections for the given image.

        Worker scenarios are sampled according to the following target distribution:
        - all_ppe: 35% (both helmet and vest present)
        - no_helmet: 15% (vest present, helmet missing)
        - no_vest: 15% (helmet present, vest missing)
        - no_ppe: 8% (both helmet and vest missing)
        - helmet_in_hand: 6% (helmet missing on head, helmet_in_hand flag, unassigned helmet beside)
        - hi_vis_not_vest: 6% (vest missing, hi_vis_not_vest flag, note on non-compliant hi-vis)
        - head_hidden: 8% (helmet uncertain, partly_occluded flag)
        - torso_hidden: 7% (vest uncertain, partly_occluded flag)
        Total: 35 + 15 + 15 + 8 + 6 + 6 + 8 + 7 = 100%

        Args:
            image: PIL Image in RGB format.

        Returns:
            DetectionResult: Result with PpeExtraRaw metadata.
        """
        if not self._is_loaded:
            raise RuntimeError("Detector is not loaded. Call load() before running detect().")

        start_time = time.perf_counter()

        width, height = image.size
        w_float, h_float = float(width), float(height)

        # Cheap pixel sampling for deterministic seeding
        sample_w = min(width, 32)
        sample_h = min(height, 32)
        try:
            sample_bytes = image.crop((0, 0, sample_w, sample_h)).tobytes()
        except Exception:
            sample_bytes = b""

        seed_data = f"{width}x{height}:{len(sample_bytes)}:".encode("utf-8") + sample_bytes
        hash_digest = hashlib.sha256(seed_data).hexdigest()
        seed_int = int(hash_digest[:16], 16)
        rng = random.Random(seed_int)

        # Determine 1 to 5 workers ordered left to right
        num_workers = rng.randint(1, 5)
        slot_w = w_float / float(num_workers)

        workers: List[PpeWorkerRaw] = []
        unassigned_items: List[UnassignedItem] = []
        detected_objects: List[DetectedObject] = []

        for idx in range(num_workers):
            worker_id = idx + 1
            slot_x1 = idx * slot_w
            slot_x2 = (idx + 1) * slot_w

            # Person box strictly inside image and slot
            margin_x = max(0.5, 0.05 * slot_w)
            px1 = round(max(0.0, slot_x1 + margin_x), 1)
            px2 = round(min(w_float, slot_x2 - margin_x), 1)
            if px2 - px1 < 1.0:
                px1 = round(slot_x1, 1)
                px2 = round(slot_x2, 1)
                if px2 - px1 < 1.0:
                    px2 = min(w_float, px1 + 1.0)
                    if px2 == px1:
                        px1 = max(0.0, px2 - 1.0)

            py1 = round(max(0.0, h_float * 0.08), 1)
            py2 = round(min(h_float, h_float * 0.92), 1)
            if py2 - py1 < 4.0:
                py1 = 0.0
                py2 = h_float

            p_h = py2 - py1
            p_w = px2 - px1

            person_bbox = BoundingBox(x1=px1, y1=py1, x2=px2, y2=py2)
            person_conf = round(rng.uniform(0.85, 0.98), 4)

            # Pre-compute valid helmet box inside upper 25% of person box
            # Upper 25% band: [py1, py1 + 0.25 * p_h]
            h_band_top = py1
            h_band_bottom = py1 + 0.25 * p_h
            h_pad_y = 0.05 * (h_band_bottom - h_band_top)
            hx1 = round(px1 + 0.15 * p_w, 1)
            hx2 = round(px2 - 0.15 * p_w, 1)
            hy1 = round(h_band_top + h_pad_y, 1)
            hy2 = round(h_band_bottom - h_pad_y, 1)
            if hx2 <= hx1:
                hx1, hx2 = px1, px2
            if hy2 <= hy1:
                hy1, hy2 = round(h_band_top, 1), round(h_band_bottom, 1)

            helmet_bbox = BoundingBox(x1=hx1, y1=hy1, x2=hx2, y2=hy2)

            # Pre-compute valid vest box inside 25% to 65% band of person box
            v_band_top = py1 + 0.25 * p_h
            v_band_bottom = py1 + 0.65 * p_h
            v_pad_y = 0.05 * (v_band_bottom - v_band_top)
            vx1 = round(px1 + 0.1 * p_w, 1)
            vx2 = round(px2 - 0.1 * p_w, 1)
            vy1 = round(v_band_top + v_pad_y, 1)
            vy2 = round(v_band_bottom - v_pad_y, 1)
            if vx2 <= vx1:
                vx1, vx2 = px1, px2
            if vy2 <= vy1:
                vy1, vy2 = round(v_band_top, 1), round(v_band_bottom, 1)

            vest_bbox = BoundingBox(x1=vx1, y1=vy1, x2=vx2, y2=vy2)

            # Sample scenario based on target distribution
            # 35% all_ppe, 15% no_helmet, 15% no_vest, 8% no_ppe,
            # 6% helmet_in_hand, 6% hi_vis_not_vest, 8% head_hidden, 7% torso_hidden
            scenario_roll = rng.random()

            flags: List[str] = []
            notes: List[str] = []

            if scenario_roll < 0.35:
                # 1. all_ppe (35%)
                helmet_item = PpeItem(
                    status="present",
                    confidence=round(rng.uniform(0.85, 0.98), 4),
                    bbox=helmet_bbox,
                )
                vest_item = PpeItem(
                    status="present",
                    confidence=round(rng.uniform(0.85, 0.98), 4),
                    bbox=vest_bbox,
                )
            elif scenario_roll < 0.50:
                # 2. no_helmet (15%)
                helmet_item = PpeItem(
                    status="missing",
                    confidence=round(rng.uniform(0.80, 0.95), 4),
                    bbox=None,
                )
                vest_item = PpeItem(
                    status="present",
                    confidence=round(rng.uniform(0.85, 0.98), 4),
                    bbox=vest_bbox,
                )
            elif scenario_roll < 0.65:
                # 3. no_vest (15%)
                helmet_item = PpeItem(
                    status="present",
                    confidence=round(rng.uniform(0.85, 0.98), 4),
                    bbox=helmet_bbox,
                )
                vest_item = PpeItem(
                    status="missing",
                    confidence=round(rng.uniform(0.80, 0.95), 4),
                    bbox=None,
                )
            elif scenario_roll < 0.73:
                # 4. no_ppe (8%)
                helmet_item = PpeItem(
                    status="missing",
                    confidence=round(rng.uniform(0.80, 0.95), 4),
                    bbox=None,
                )
                vest_item = PpeItem(
                    status="missing",
                    confidence=round(rng.uniform(0.80, 0.95), 4),
                    bbox=None,
                )
            elif scenario_roll < 0.79:
                # 5. helmet_in_hand (6%)
                helmet_item = PpeItem(
                    status="missing",
                    confidence=round(rng.uniform(0.82, 0.95), 4),
                    bbox=None,
                )
                vest_item = PpeItem(
                    status="present",
                    confidence=round(rng.uniform(0.85, 0.98), 4),
                    bbox=vest_bbox,
                )
                flags.append("helmet_in_hand")
                notes.append("Worker is carrying a helmet in hand instead of wearing it on head.")

                # UnassignedItem helmet beside worker
                item_w = min(p_w * 0.4, 20.0)
                item_h = min(p_h * 0.15, 20.0)
                if px1 >= item_w:
                    ux1 = round(px1 - item_w, 1)
                    ux2 = round(px1, 1)
                else:
                    ux1 = round(px2, 1)
                    ux2 = round(min(w_float, px2 + item_w), 1)
                uy1 = round(py1 + 0.45 * p_h, 1)
                uy2 = round(min(h_float, uy1 + item_h), 1)
                if ux2 > ux1 and uy2 > uy1:
                    u_box = BoundingBox(x1=ux1, y1=uy1, x2=ux2, y2=uy2)
                    unassigned_items.append(
                        UnassignedItem(
                            label="helmet",
                            confidence=round(rng.uniform(0.82, 0.95), 4),
                            bbox=u_box,
                            reason="helmet is not on a head",
                        )
                    )
            elif scenario_roll < 0.85:
                # 6. hi_vis_not_vest (6%)
                helmet_item = PpeItem(
                    status="present",
                    confidence=round(rng.uniform(0.85, 0.98), 4),
                    bbox=helmet_bbox,
                )
                vest_item = PpeItem(
                    status="missing",
                    confidence=round(rng.uniform(0.75, 0.90), 4),
                    bbox=None,
                )
                flags.append("hi_vis_not_vest")
                notes.append("High-visibility clothing observed but does not meet safety vest requirements.")
            elif scenario_roll < 0.93:
                # 7. head_hidden (8%)
                helmet_item = PpeItem(
                    status="uncertain",
                    confidence=None,
                    bbox=None,
                )
                vest_item = PpeItem(
                    status="present",
                    confidence=round(rng.uniform(0.85, 0.98), 4),
                    bbox=vest_bbox,
                )
                flags.append("partly_occluded")
                notes.append("Head region is obscured by visual obstruction.")
            else:
                # 8. torso_hidden (7%)
                helmet_item = PpeItem(
                    status="present",
                    confidence=round(rng.uniform(0.85, 0.98), 4),
                    bbox=helmet_bbox,
                )
                vest_item = PpeItem(
                    status="uncertain",
                    confidence=None,
                    bbox=None,
                )
                flags.append("partly_occluded")
                notes.append("Torso region is occluded by equipment or barrier.")

            badge_id = rng.randint(0, 49) if rng.random() < 0.45 else None

            worker_raw = PpeWorkerRaw(
                id=worker_id,
                bbox=person_bbox,
                person_confidence=person_conf,
                helmet=helmet_item,
                vest=vest_item,
                badge_id=badge_id,
                flags=flags,
                notes=notes,
            )
            workers.append(worker_raw)

            # Record in raw objects list
            detected_objects.append(
                DetectedObject(label="person", confidence=person_conf, bbox=person_bbox)
            )
            if helmet_item.status == "present" and helmet_item.bbox is not None:
                detected_objects.append(
                    DetectedObject(
                        label="helmet",
                        confidence=helmet_item.confidence or 0.9,
                        bbox=helmet_item.bbox,
                    )
                )
            if vest_item.status == "present" and vest_item.bbox is not None:
                detected_objects.append(
                    DetectedObject(
                        label="vest",
                        confidence=vest_item.confidence or 0.9,
                        bbox=vest_item.bbox,
                    )
                )

        # Occasionally add one unassigned helmet on a table
        if rng.random() < 0.20:
            tbl_w = min(w_float * 0.1, 30.0)
            tbl_h = min(h_float * 0.1, 30.0)
            tx1 = round(max(0.0, w_float - tbl_w - 2.0), 1)
            tx2 = round(min(w_float, tx1 + tbl_w), 1)
            ty1 = round(max(0.0, h_float - tbl_h - 2.0), 1)
            ty2 = round(min(h_float, ty1 + tbl_h), 1)
            if tx2 > tx1 and ty2 > ty1:
                t_box = BoundingBox(x1=tx1, y1=ty1, x2=tx2, y2=ty2)
                t_conf = round(rng.uniform(0.75, 0.92), 4)
                unassigned_items.append(
                    UnassignedItem(
                        label="helmet",
                        confidence=t_conf,
                        bbox=t_box,
                        reason="no worker nearby",
                    )
                )

        # Add all unassigned items to raw objects list
        for u in unassigned_items:
            detected_objects.append(
                DetectedObject(label=u.label, confidence=u.confidence, bbox=u.bbox)
            )

        inference_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        extra_raw = PpeExtraRaw(
            schema="ppe.v1",
            workers=workers,
            unassigned_items=unassigned_items,
            pipeline=PpePipelineInfo(),
        )

        return DetectionResult(
            objects=detected_objects,
            total_count=len(detected_objects),
            image_width=width,
            image_height=height,
            inference_ms=inference_ms,
            detector_name=self.name,
            extra=extra_raw.model_dump(),
        )
