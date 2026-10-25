"""Inference protection, worker pool management, and timeout enforcement."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from PIL import Image

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.detection import DetectionResult
from app.services.detector.base import BaseDetector

logger = get_logger("vision_api.inference")


class InferenceError(Exception):
    """Base exception for inference errors."""
    pass


class InferenceTimeout(InferenceError):
    """Raised when detector inference execution exceeds the configured timeout."""
    pass


class ServerBusy(InferenceError):
    """Raised when active/queued inference requests exceed the queue limit."""
    pass


class InferenceManager:
    """Manages worker threads and concurrency limits for detector inference."""

    def __init__(self) -> None:
        self._executor: Optional[ThreadPoolExecutor] = None
        self._active_and_queued: int = 0
        self._lock = threading.Lock()

    def init_executor(self, workers: int) -> None:
        """Initialize the shared ThreadPoolExecutor."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="inference_worker",
            )
            logger.info("Inference ThreadPoolExecutor initialized", extra={"workers": workers})

    def shutdown(self, wait: bool = False) -> None:
        """Shut down the ThreadPoolExecutor."""
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None
            logger.info("Inference ThreadPoolExecutor shut down")

    async def run_inference(
        self,
        detector: BaseDetector,
        image: Image.Image,
        timeout: Optional[float] = None,
        queue_limit: Optional[int] = None,
    ) -> DetectionResult:
        """Execute detector inference with timeout and concurrency protections.

        Submits work to the shared ThreadPoolExecutor and enforces timeouts and queue limits.
        """
        settings = get_settings()
        actual_timeout = timeout if timeout is not None else float(settings.INFERENCE_TIMEOUT_SECONDS)
        actual_queue_limit = queue_limit if queue_limit is not None else settings.INFERENCE_QUEUE_LIMIT

        with self._lock:
            if self._active_and_queued >= actual_queue_limit:
                raise ServerBusy("Server busy, try again shortly")
            self._active_and_queued += 1

        try:
            if self._executor is None:
                self.init_executor(settings.INFERENCE_WORKERS)

            loop = asyncio.get_running_loop()
            future = loop.run_in_executor(self._executor, detector.detect, image)
            return await asyncio.wait_for(future, timeout=actual_timeout)
        except asyncio.TimeoutError as exc:
            # NOTE: Standard operating system threads in Python cannot be forcefully
            # killed or aborted from user space. The worker thread may continue running
            # until the detector method finishes in the background. However, the client
            # connection is promptly unblocked and returned a timeout error.
            raise InferenceTimeout(f"Inference execution timed out after {actual_timeout}s") from exc
        finally:
            with self._lock:
                self._active_and_queued -= 1


# Global inference manager singleton
inference_manager = InferenceManager()


async def run_inference(
    detector: BaseDetector,
    image: Image.Image,
    timeout: Optional[float] = None,
    queue_limit: Optional[int] = None,
) -> DetectionResult:
    """Convenience wrapper for asynchronous detector inference with timeout and concurrency guards."""
    return await inference_manager.run_inference(
        detector, image, timeout=timeout, queue_limit=queue_limit
    )
