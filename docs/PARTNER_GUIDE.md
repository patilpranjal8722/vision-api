# Partner Handoff Guide: Integrating YOLO & OpenCV into vision-api

Welcome to the team! This guide was written specifically for the **Computer Vision / ML engineer** joining the project.

You did not have to write the HTTP endpoints, database schemas, authentication, or WebSocket plumbing. All of that is already built, tested, and running. Your goal is to plug in real **YOLO object detection** and **OpenCV video decoding** without breaking the existing architecture.

> [!NOTE]
> All code snippets provided in this guide for `YoloDetector` and `OpenCVFrameReader` are marked as **[untested skeleton]** in this repository because heavy ML/CUDA libraries (`torch`, `ultralytics`, `cv2`) are intentionally not installed in the base lightweight environment.

---

## Table of Contents

1. [What is Built vs. What is Intentionally Missing](#1-what-is-built-vs-what-is-intentionally-missing)
2. [Quick Setup on a New Machine](#2-quick-setup-on-a-new-machine)
3. [Plugging in YOLO Step-by-Step](#3-plugging-in-yolo-step-by-step)
4. [Plugging in OpenCV Video Decoding Step-by-Step](#4-plugging-in-opencv-video-decoding-step-by-step)
5. [Inference Performance Optimization](#5-inference-performance-optimization)
6. [How to Test the Real Detector Without Breaking CI](#6-how-to-test-the-real-detector-without-breaking-ci)
7. [Adapting the Template to a Hackathon Theme](#7-adapting-the-template-to-a-hackathon-theme)
8. [Git Collaboration Workflow for Two Developers](#8-git-collaboration-workflow-for-two-developers)
9. [Troubleshooting Guide](#9-troubleshooting-guide)
10. [Demo-Day Presentation & Fallback Plan](#10-demo-day-presentation--fallback-plan)

---

## 1. What is Built vs. What is Intentionally Missing

### What is Already Built
- **FastAPI Core**: Async lifespan management, uniform JSON error structures with `request_id`, security headers, body size limiters, CORS, and structured JSON logging.
- **Authentication & RBAC**: Argon2id password hashing, stateless JWT access/refresh tokens, and role-based permissions (`user` vs `admin`).
- **Database & Migrations**: SQLAlchemy 2.0 ORM with SQLite (WAL mode) and PostgreSQL readiness, managed by Alembic. Models: `User`, `Job`, `Detection`, `Alert`.
- **Validation & File Handling**: Safe image decoding (Pillow) and video streaming upload size enforcement (HTTP 413) with container magic-byte verification (MP4, MOV, WebM, AVI).
- **Asynchronous Video Jobs**: `ThreadPoolExecutor` runner processing video jobs in the background with progress reporting (0–100%) and automatic timeline compilation.
- **Real-Time Push Feeds**: In-process `WebSocketManager` broadcasting alerts (`/ws/alerts`) and handling streaming frames (`/ws/stream`) with latest-frame-wins flow control.
- **Analytics & Health Probes**: Aggregated statistics (`/analytics/summary`, `/analytics/timeseries`), liveness (`/health`), and readiness (`/ready`).

### What is Intentionally Missing (Your Job!)
- **No Heavy ML Dependencies**: `ultralytics`, `torch`, `torchvision`, and `opencv-python` are NOT in `requirements.txt`. They are documented in `requirements-cv.txt`.
- **`DummyDetector`** (`app/services/detector/dummy.py`): Generates simulated deterministic bounding boxes using pixel hashing so frontend and backend engineers can develop without GPUs.
- **`DummyFrameReader`** (`app/services/video/dummy.py`): Generates solid-color synthetic frames with mock timestamps.
- **`YoloDetector` Stub** (`app/services/detector/yolo_detector.py`): Currently raises `NotImplementedError`. You will implement real Ultralytics inference here.
- **`OpenCVFrameReader` Stub** (`app/services/video/opencv_reader.py`): Currently raises `NotImplementedError`. You will implement real `cv2.VideoCapture` frame iteration here.

---

## 2. Quick Setup on a New Machine

Follow these exact steps when cloning the repository to a new workstation:

### Step 1: Clone and Create Virtual Environment
```bash
git clone <repo-url> vision-api
cd vision-api

# Create a clean Python 3.12 or 3.11 virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate
```

### Step 2: Install Dependencies
First, install the base application dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

> [!IMPORTANT]
> **PyTorch CPU-Only Notice**:
> If developing on a machine **without an NVIDIA GPU** (e.g. MacBook or standard laptop), **do not** run `pip install -r requirements-cv.txt` directly. That may download multi-gigabyte CUDA binaries.
> Instead, visit [pytorch.org](https://pytorch.org/get-started/locally/) and install the CPU-only PyTorch wheel first:
> ```bash
> # Example CPU wheel install (check pytorch.org for the latest URL):
> pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
> ```
> After PyTorch is installed, install Ultralytics and OpenCV:
> ```bash
> pip install ultralytics "opencv-python-headless>=4.8.0"
> ```

### Step 3: Configure Environment
Copy the example configuration:
```bash
# Windows
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```
Generate a cryptographically secure random `SECRET_KEY` and save it in `.env`:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 4: Run Migrations and Create Admin
```bash
# Apply database schema
alembic upgrade head

# Create an initial administrator account (prompts for email, username, password)
python -m scripts.create_admin
```

### Step 5: Start Server & Run Smoke Test
Start the Uvicorn development server:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
In a second terminal window, verify everything works with the automated smoke test:
```bash
python -m scripts.smoke_test --base-url http://127.0.0.1:8000
```
All 14 smoke tests should return `PASS`!

---

## 3. Plugging in YOLO Step-by-Step

All detector code lives in `app/services/detector/`.

### 1. Where the Stub Lives
The stub file is [app/services/detector/yolo_detector.py](file:///c:/Users/admin/Desktop/Project/app/services/detector/yolo_detector.py).

### 2. The Contract: What `detect()` Must Return
The base class `BaseDetector` requires `detect(image: Image.Image)` to return a `DetectionResult` Pydantic model (`app/schemas/detection.py`):
```python
class DetectionResult(BaseModel):
    objects: List[DetectedObject]  # label, confidence (0.0-1.0), and BoundingBox(x1, y1, x2, y2)
    total_count: int               # Total qualifying objects detected
    image_width: int               # Width in pixels
    image_height: int              # Height in pixels
    inference_ms: float            # Pure inference time in milliseconds
    detector_name: str             # "yolo"
    extra: Dict[str, Any]          # Optional metadata (weights, device, etc.)
```

### 3. Implementation Skeleton [untested skeleton]
Edit [app/services/detector/yolo_detector.py](file:///c:/Users/admin/Desktop/Project/app/services/detector/yolo_detector.py) as follows:

```python
"""Real YoloDetector implementation using Ultralytics YOLOv8 [untested skeleton]."""

import os
import time
from typing import Optional, List
from PIL import Image

from app.core.config import get_settings
from app.schemas.detection import BoundingBox, DetectedObject, DetectionResult
from app.services.detector.base import BaseDetector


class YoloDetector(BaseDetector):
    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
    ) -> None:
        self.name: str = "yolo"
        self._is_loaded: bool = False
        settings = get_settings()
        self.model_path = model_path or settings.MODEL_PATH
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.CONFIDENCE_THRESHOLD
        )
        self.model = None
        self.device = "cpu"

    @property
    def is_placeholder(self) -> bool:
        return False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def load(self) -> None:
        """Load YOLO model weights into memory with warm-up inference."""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"YOLO weights not found at '{self.model_path}'. "
                f"Please download the weights file into models_store/."
            )

        # Lazy import so top-level app boots without ML libraries
        from ultralytics import YOLO
        import torch

        # Device selection: use CUDA GPU if available, else CPU (or MPS on Apple Silicon)
        if torch.cuda.is_available():
            self.device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        # Load weights
        self.model = YOLO(self.model_path)
        self.model.to(self.device)

        # Warm-up inference (initial inference triggers JIT compilation and memory paging)
        dummy_img = Image.new("RGB", (640, 640), color=(128, 128, 128))
        self.model(dummy_img, device=self.device, verbose=False)

        self._is_loaded = True

    def detect(self, image: Image.Image) -> DetectionResult:
        """Run YOLO inference on a decoded PIL RGB image."""
        if not self._is_loaded or self.model is None:
            raise RuntimeError("YoloDetector is not loaded. Call load() first.")

        t0 = time.perf_counter()

        # Run inference
        results = self.model(
            image,
            conf=self.confidence_threshold,
            device=self.device,
            verbose=False,
        )

        detected_objects: List[DetectedObject] = []
        for r in results:
            boxes = r.boxes
            for box in boxes:
                xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = self.model.names.get(cls_id, str(cls_id))

                detected_objects.append(
                    DetectedObject(
                        label=label,
                        confidence=round(conf, 4),
                        bbox=BoundingBox(
                            x1=round(xyxy[0], 2),
                            y1=round(xyxy[1], 2),
                            x2=round(xyxy[2], 2),
                            y2=round(xyxy[3], 2),
                        ),
                    )
                )

        inference_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return DetectionResult(
            objects=detected_objects,
            total_count=len(detected_objects),
            image_width=image.width,
            image_height=image.height,
            inference_ms=inference_ms,
            detector_name=self.name,
            extra={"weights": self.model_path, "device": self.device},
        )

    def close(self) -> None:
        """Free model handles and release GPU cache."""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        self.model = None
        self._is_loaded = False
```

### 4. Weights Storage & Sharing
- **Where to put weights**: Store files like `yolov8n.pt` inside the `models_store/` folder in the project root.
- **Git Exclusion**: `models_store/*` is listed in `.gitignore` and `.dockerignore`. **NEVER commit `.pt` or `.onnx` files to git**.
- **How to share**: Share weights via Google Drive, OneDrive, or AWS S3. Your partner drops the weights directly into `models_store/yolov8n.pt`.

### 5. Enabling in `.env`
Update your local `.env`:
```env
DETECTOR_BACKEND=yolo
MODEL_PATH=models_store/yolov8n.pt
CONFIDENCE_THRESHOLD=0.30
```

---

## 4. Plugging in OpenCV Video Decoding Step-by-Step

All video reader code lives in `app/services/video/`.

### 1. Where the Stub Lives
The stub file is [app/services/video/opencv_reader.py](file:///c:/Users/admin/Desktop/Project/app/services/video/opencv_reader.py).

### 2. The Contract: What `iter_frames()` Must Yield
The base class `BaseFrameReader` requires `iter_frames(frame_skip: int)` to yield tuples of:
```python
(frame_index: int, timestamp_seconds: float, frame_image: PIL.Image.Image)
```

### 3. Implementation Skeleton [untested skeleton]
Edit [app/services/video/opencv_reader.py](file:///c:/Users/admin/Desktop/Project/app/services/video/opencv_reader.py) as follows:

```python
"""Real OpenCV video capture frame reader [untested skeleton]."""

from typing import Generator, Optional, Tuple
from PIL import Image
from app.services.video.base import BaseFrameReader


class OpenCVFrameReader(BaseFrameReader):
    def __init__(self) -> None:
        self._path: Optional[str] = None
        self._cap = None
        self._fps: float = 25.0
        self._total_frames: int = 0
        self._width: int = 0
        self._height: int = 0

    def open(self, path: str) -> "OpenCVFrameReader":
        """Open video file and inspect metadata."""
        import cv2

        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            raise ValueError(f"OpenCV could not open or decode video file: {path}")

        fps_val = float(self._cap.get(cv2.CAP_PROP_FPS) or 0.0)
        self._fps = fps_val if fps_val > 0.0 else 25.0

        count_val = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self._total_frames = max(count_val, 0)

        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        self._path = path
        return self

    def close(self) -> None:
        """Release native OpenCV capture handle."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def total_frames(self) -> int:
        return self._total_frames

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def iter_frames(
        self, frame_skip: int = 1
    ) -> Generator[Tuple[int, float, Image.Image], None, None]:
        """Iterate video frames efficiently using grab() and retrieve()."""
        import cv2

        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError("Capture handle is not open. Call open() first.")

        stride = max(1, frame_skip)
        frame_idx = 0

        while self._cap.isOpened():
            # grab() advances the stream counter without decompressing the full frame
            grabbed = self._cap.grab()
            if not grabbed:
                break

            if frame_idx % stride == 0:
                # retrieve() decodes only the sampled frames, saving substantial CPU time
                ret, bgr_mat = self._cap.retrieve()
                if ret and bgr_mat is not None:
                    rgb_mat = cv2.cvtColor(bgr_mat, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(rgb_mat)
                    timestamp = round(frame_idx / self._fps, 3)
                    yield frame_idx, timestamp, pil_img

            frame_idx += 1
```

### 4. Enabling in `.env`
Update `.env`:
```env
FRAME_READER_BACKEND=opencv
FRAME_SKIP=5
```

---

## 5. Inference Performance Optimization

When presenting at a hackathon or deploying to cloud VMs, use these performance guidelines:

1. **Use Nano Models First**: Start with `yolov8n.pt` (~6 MB) instead of `yolov8x.pt` (~130 MB). Nano models run at 60+ FPS on modern CPUs and provide ample accuracy for demonstrations.
2. **Input Resolution Sizing**: Default YOLO inference resizes to `640x640`. For high-throughput streaming or lower-end CPUs, use `imgsz=320` inside `self.model(image, imgsz=320)`.
3. **Frame Skipping (`FRAME_SKIP`)**: Never run inference on all 30 frames per second of a recorded video. Setting `FRAME_SKIP=5` or `FRAME_SKIP=10` processes 3 to 6 frames per second, which is more than enough to detect objects and timeline trends while completing jobs 5x–10x faster.
4. **Warm-Up Inference**: The very first PyTorch/YOLO inference on any process incurs significant latency (0.5s–3s) due to GPU memory initialization, CUDA context creation, and kernel caching. The `load()` method in the skeleton performs a 1-frame warm-up at startup so user requests never experience startup stutter.
5. **OpenVINO Export for Intel CPUs**: If running on Intel x86 CPUs (common on AWS/GCP/Azure compute instances without GPUs):
   ```python
   # Export to OpenVINO once:
   model = YOLO("models_store/yolov8n.pt")
   model.export(format="openvino")
   # Load OpenVINO model (2x-3x speedup on Intel CPUs):
   model = YOLO("models_store/yolov8n_openvino_model/")
   ```

---

## 6. How to Test the Real Detector Without Breaking CI

Our GitHub Actions CI runs on GitHub-hosted runners **without GPUs or weights files**. Automated tests must never fail because `models_store/yolov8n.pt` is absent.

### 1. Existing Unit Tests
The test suite in `tests/test_detector.py` and `tests/test_detect_api.py` tests the detector abstraction using `DummyDetector`. Keep those tests intact.

### 2. Testing with Fake Results Object (Mocking)
To test the `YoloDetector` parsing logic in automated tests without model weights, mock the Ultralytics model:

```python
# In tests/test_yolo_mock.py
from unittest.mock import MagicMock
from PIL import Image
from app.services.detector.yolo_detector import YoloDetector


def test_yolo_detector_mocked_results():
    detector = YoloDetector()
    detector._is_loaded = True

    # Fake Box
    mock_box = MagicMock()
    mock_box.xyxy = [[10.0, 20.0, 100.0, 200.0]]
    mock_box.conf = [0.92]
    mock_box.cls = [0]

    # Fake Results
    mock_result = MagicMock()
    mock_result.boxes = [mock_box]

    detector.model = MagicMock()
    detector.model.names = {0: "person"}
    detector.model.return_value = [mock_result]

    test_img = Image.new("RGB", (640, 480))
    result = detector.detect(test_img)

    assert result.total_count == 1
    assert result.objects[0].label == "person"
    assert result.objects[0].confidence == 0.92
```

### 3. Pytest Skip Markers for Tests Requiring Weights
For end-to-end tests that require real model weights on your local machine:
```python
import os
import pytest
from app.services.detector.yolo_detector import YoloDetector

WEIGHTS_PATH = "models_store/yolov8n.pt"

@pytest.mark.skipif(not os.path.exists(WEIGHTS_PATH), reason="YOLO weights file not found")
def test_real_yolo_inference():
    detector = YoloDetector(model_path=WEIGHTS_PATH)
    detector.load()
    # ... test real inference
```

---

## 7. Adapting the Template to a Hackathon Theme

If your hackathon theme is specific (e.g., *Worker Safety*, *Retail Customer Flow*, *Traffic Density*, *Wildlife Tracking*), use this quick checklist:

### A. Adding a New API Endpoint
1. **Schema**: Define input/output DTOs in [app/schemas/](file:///c:/Users/admin/Desktop/Project/app/schemas/).
2. **Service**: Implement core logic in [app/services/](file:///c:/Users/admin/Desktop/Project/app/services/).
3. **Route**: Create endpoint in [app/api/routes/](file:///c:/Users/admin/Desktop/Project/app/api/routes/).
4. **Register**: Include the router in [app/main.py](file:///c:/Users/admin/Desktop/Project/app/main.py) with `app.include_router(...)`.
5. **Test**: Write automated tests in [tests/](file:///c:/Users/admin/Desktop/Project/tests/).

### B. Adding a New Database Table
1. **Model**: Create a SQLAlchemy 2.0 model in [app/models/](file:///c:/Users/admin/Desktop/Project/app/models/).
2. **Export**: Import and expose the model in [app/models/__init__.py](file:///c:/Users/admin/Desktop/Project/app/models/__init__.py).
3. **Generate Migration**:
   ```bash
   alembic revision --autogenerate -m "create new_table"
   ```
4. **Apply Migration**:
   ```bash
   alembic upgrade head
   ```
5. **Verify**: Add model constraint tests in [tests/test_models.py](file:///c:/Users/admin/Desktop/Project/tests/test_models.py).

### C. Adding a Custom Alert Rule
Edit [app/services/alert_service.py](file:///c:/Users/admin/Desktop/Project/app/services/alert_service.py):
- Example: Alert when specific class label (e.g. `"fire"`, `"knife"`, or `"no-helmet"`) is detected.
- The service will persist the alert and automatically push it via WebSocket to active frontend clients.

### D. Adding Custom Analytics
1. **Schema**: Add new metrics fields to `AnalyticsSummaryOut` in [app/schemas/analytics.py](file:///c:/Users/admin/Desktop/Project/app/schemas/analytics.py).
2. **Route**: Update `GET /analytics/summary` in [app/api/routes/analytics.py](file:///c:/Users/admin/Desktop/Project/app/api/routes/analytics.py) to aggregate the new metrics.

---

## 8. Git Collaboration Workflow for Two Developers

### File Ownership Boundaries
- **ML / CV Engineer**:
  - `app/services/detector/yolo_detector.py`
  - `app/services/video/opencv_reader.py`
  - `models_store/` (local only, never commit weights)
  - `requirements-cv.txt`
- **Backend / Platform Engineer**:
  - `app/api/` (all routes & deps)
  - `app/core/` (config, middleware, security, limiter)
  - `app/db/` & `alembic/` (models & migrations)
  - `docker/`, `Dockerfile`, `docker-compose.yml`, `.github/`

### Branching & Commit Discipline
- Create focused feature branches:
  ```bash
  git checkout -b feature/yolo-detector
  # or
  git checkout -b feature/opencv-reader
  ```
- Always pull before starting new edits:
  ```bash
  git pull --rebase origin main
  ```
- Make small, descriptive commits:
  ```bash
  git commit -m "feat(detector): implement YoloDetector load and detect methods"
  ```
- Push and open a Pull Request (PR) on GitHub.

### Files That Must NEVER Be Committed
Verify `git status` before committing:
- `.env` (contains secrets and tokens)
- `models_store/*.pt`, `*.onnx`, `*.bin` (large weights files)
- `*.db`, `*.db-wal`, `*.db-shm` (SQLite database files)
- `uploads/*` (user-uploaded media)
- `.venv/` or `__pycache__/`

### Resolving Merge Conflicts
If you encounter a conflict:
```bash
git fetch origin
git rebase origin/main
# If a conflict occurs, inspect the conflicting file:
# Open file, look for <<<<<<< HEAD and >>>>>>> marks.
# Pick the desired code, save the file.
git add <conflicted-file>
git rebase --continue
```

---

## 9. Troubleshooting Guide

| Issue / Symptom | Root Cause | Solution |
| :--- | :--- | :--- |
| **Port 8000 already in use** (`WinError 10013` or `EADDRINUSE`) | Another process or orphaned Uvicorn instance is holding port 8000. | Find and kill: `netstat -ano \| findstr :8000` followed by `taskkill /F /PID <PID>`, or start server on a different port: `uvicorn app.main:app --port 8001`. |
| **`python` uses wrong version** | Virtual environment is not activated. | Verify prompt shows `(.venv)`. Re-run `.\.venv\Scripts\Activate.ps1` (Windows) or `source .venv/bin/activate` (Linux/macOS). |
| **`uvicorn` not recognized** | Dependencies not installed in active environment. | Run `pip install -r requirements.txt`. |
| **Alembic migration drift / head mismatch** | Multiple branches added migrations concurrently. | Run `alembic heads` to check for multiple heads. Merge heads using `alembic merge heads -m "merge"` then `alembic upgrade head`. |
| **CRLF errors inside Docker** (`/bin/sh: entrypoint.sh: not found`) | Windows CRLF line endings in shell scripts. | Normalization is built into Dockerfile (`sed -i 's/\r$//'`). In git, run: `git config core.autocrlf false`. |
| **PyTorch install downloads 4 GB CUDA package** | Default PyTorch index assumes CUDA support. | Install CPU wheels first: `pip install torch --index-url https://download.pytorch.org/whl/cpu`. |
| **Database locked error (`sqlite3.OperationalError: database is locked`)** | Multiple threads writing to SQLite concurrently. | The template already configures `PRAGMA busy_timeout = 5000` and WAL mode. Keep long-running write transactions minimal or switch to PostgreSQL. |

---

## 10. Demo-Day Presentation & Fallback Plan

When presenting live to judges or an audience:

1. **Pre-Presentation Verification (30 Minutes Before Demo)**:
   - Run the automated smoke test against your live instance:
     ```bash
     python -m scripts.smoke_test --base-url http://127.0.0.1:8000
     ```
   - Ensure all 14 checks return `PASS`.
2. **Local Backup with ngrok**:
   - If Wi-Fi in the presentation hall blocks local port access or mobile devices cannot reach your laptop's IP, use [ngrok](https://ngrok.com/):
     ```bash
     ngrok http 8000
     ```
   - Use the HTTPS URL provided by ngrok in your frontend configuration.
3. **Backup Demo Video**:
   - Always record a 60-second screen capture showing:
     - Live webcam stream detection with bounding boxes.
     - Video upload with progress bar.
     - Real-time alert popup.
   - If the venue Wi-Fi fails or a laptop battery glitch occurs, play the video immediately while explaining the architecture.
4. **Instant Fallback to Dummy Detector**:
   - If a GPU overheats or CUDA runs out of memory on-stage:
     - Change `.env`: `DETECTOR_BACKEND=dummy`
     - Restart Uvicorn: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
     - The application continues working immediately with simulated detections.
