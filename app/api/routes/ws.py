"""WebSocket endpoints for real-time alerts and streaming video frame analysis."""

import asyncio
import io
import json
import time
from typing import Optional, Tuple
from urllib.parse import urlparse
from PIL import Image
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.detection import Detection
from app.models.user import User
from app.schemas.detection import DetectionResult
from app.services.alert_service import evaluate_detection
from app.services.ws_manager import ws_manager

logger = get_logger("vision_api.ws")
router = APIRouter(tags=["WebSocket"])


def is_origin_allowed(websocket: WebSocket, settings: Settings) -> bool:
    """Validate request Origin header against configured allowed origins and host."""
    origin = websocket.headers.get("origin")
    if not origin:
        return True

    if "*" in settings.ALLOWED_ORIGINS or origin in settings.ALLOWED_ORIGINS:
        return True

    parsed_origin = urlparse(origin)
    origin_host = parsed_origin.netloc or parsed_origin.path
    host_header = websocket.headers.get("host")
    if host_header and origin_host == host_header:
        return True

    return False


async def authenticate_ws(websocket: WebSocket, settings: Settings) -> Optional[User]:
    """Authenticate WebSocket client via mandatory initial auth message.

    Closes socket with 4401 on missing, timed-out, invalid, or expired credentials.
    """
    try:
        raw_msg = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=settings.WS_AUTH_TIMEOUT_SECONDS,
        )
        data = json.loads(raw_msg)
    except asyncio.TimeoutError:
        await websocket.close(code=4401, reason="Authentication timeout")
        return None
    except (json.JSONDecodeError, WebSocketDisconnect):
        try:
            await websocket.close(code=4401, reason="Invalid authentication format")
        except Exception:
            pass
        return None

    if not isinstance(data, dict) or data.get("type") != "auth" or not data.get("token"):
        await websocket.close(code=4401, reason="Missing or invalid auth message")
        return None

    token = str(data["token"])
    try:
        payload = decode_token(token, expected_type="access")
        user_id = int(payload["sub"])
    except Exception:
        await websocket.close(code=4401, reason="Invalid or expired token")
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None or not user.is_active:
            await websocket.close(code=4401, reason="User inactive or not found")
            return None
    finally:
        db.close()

    if not ws_manager.can_connect(user.id, settings.WS_MAX_CONNECTIONS_PER_USER):
        await websocket.close(code=4429, reason="Connection limit exceeded")
        return None

    await websocket.send_json({"type": "auth_ok"})
    return user


@router.websocket("/ws/alerts")
async def ws_alerts_endpoint(websocket: WebSocket) -> None:
    """Real-time alert push feed for authenticated clients."""
    settings = get_settings()
    await websocket.accept()

    if not is_origin_allowed(websocket, settings):
        await websocket.close(code=4403, reason="Forbidden origin")
        return

    user = await authenticate_ws(websocket, settings)
    if user is None:
        return

    ws_manager.register(websocket, user.id, user.role)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                if isinstance(msg, dict) and msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug(f"Alert WebSocket disconnected: {exc}")
    finally:
        ws_manager.unregister(websocket, user.id)


@router.websocket("/ws/stream")
async def ws_stream_endpoint(websocket: WebSocket) -> None:
    """Real-time streaming frame inference endpoint with latest-frame-wins concurrency."""
    settings = get_settings()
    await websocket.accept()

    if not is_origin_allowed(websocket, settings):
        await websocket.close(code=4403, reason="Forbidden origin")
        return

    detector = getattr(websocket.app.state, "detector", None)
    if detector is None:
        try:
            await websocket.send_json({"type": "error", "message": "Detector not available"})
            await websocket.close(code=1011, reason="Detector not available")
        except Exception:
            pass
        return

    user = await authenticate_ws(websocket, settings)
    if user is None:
        return

    ws_manager.register(websocket, user.id, user.role, channel="stream")

    # Frame buffer and control primitives
    latest_frame: Optional[Tuple[int, Image.Image]] = None
    frame_counter: int = 0
    skipped_counter: int = 0
    new_frame_event = asyncio.Event()
    stop_event = asyncio.Event()

    async def frame_reader() -> None:
        nonlocal latest_frame, frame_counter, skipped_counter
        try:
            while not stop_event.is_set():
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break

                data = message.get("bytes")
                if data is None:
                    continue

                if len(data) > settings.WS_MAX_FRAME_KB * 1024:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Frame size exceeds {settings.WS_MAX_FRAME_KB} KB limit",
                    })
                    continue

                try:
                    img = Image.open(io.BytesIO(data))
                    img.verify()
                    img = Image.open(io.BytesIO(data)).convert("RGB")
                except Exception:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Undecodable or invalid image frame bytes",
                    })
                    continue

                frame_counter += 1
                if latest_frame is not None:
                    skipped_counter += 1
                latest_frame = (frame_counter, img)
                new_frame_event.set()
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug(f"Frame reader disconnected: {exc}")
        finally:
            stop_event.set()
            new_frame_event.set()

    async def frame_processor() -> None:
        nonlocal latest_frame, skipped_counter
        last_alert_time: float = 0.0
        try:
            while not stop_event.is_set():
                await new_frame_event.wait()
                new_frame_event.clear()
                if stop_event.is_set():
                    break
                if latest_frame is None:
                    continue

                curr_frame_id, curr_img = latest_frame
                latest_frame = None
                skipped = skipped_counter
                skipped_counter = 0

                try:
                    result: DetectionResult = await run_in_threadpool(detector.detect, curr_img)
                except Exception as det_exc:
                    logger.error(f"Detector error on stream frame: {det_exc}", exc_info=True)
                    continue

                # Stream alert evaluation with cooldown
                now = time.time()
                if result.total_count >= settings.ALERT_WARNING_THRESHOLD:
                    if now - last_alert_time >= settings.ALERT_COOLDOWN_SECONDS:
                        last_alert_time = now
                        db = SessionLocal()
                        try:
                            det_row = Detection(
                                user_id=user.id,
                                source_type="stream",
                                file_path=None,
                                detector_name=detector.name,
                                total_count=result.total_count,
                                results=result.model_dump(),
                            )
                            db.add(det_row)
                            db.commit()
                            db.refresh(det_row)
                            evaluate_detection(db, det_row)
                        except Exception as alert_err:
                            logger.error(f"Stream alert evaluation failed: {alert_err}", exc_info=True)
                        finally:
                            db.close()

                await websocket.send_json({
                    "type": "detections",
                    "frame_id": curr_frame_id,
                    "skipped_since_last": skipped,
                    "result": result.model_dump(),
                })
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug(f"Frame processor disconnected: {exc}")
        finally:
            stop_event.set()

    try:
        reader_task = asyncio.create_task(frame_reader())
        processor_task = asyncio.create_task(frame_processor())
        done, pending = await asyncio.wait(
            [reader_task, processor_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        stop_event.set()
        new_frame_event.set()
        for task in pending:
            task.cancel()
    finally:
        ws_manager.unregister(websocket, user.id)
