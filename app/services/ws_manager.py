"""WebSocket connection manager for real-time alerts and streaming feeds.

Provides thread-safe dispatch from worker threads and synchronous routes to
connected async WebSocket clients.
"""

import asyncio
from typing import Any, Dict, Optional, Set
from fastapi import WebSocket
from app.core.logging import get_logger

logger = get_logger("vision_api.ws_manager")


class WebSocketManager:
    """Manages active WebSocket connections partitioned by user ID and role."""

    def __init__(self) -> None:
        # Map user_id -> set of active WebSocket instances (all channels)
        self._user_connections: Dict[int, Set[WebSocket]] = {}
        # Map user_id -> set of active alert WebSocket instances
        self._alert_connections: Dict[int, Set[WebSocket]] = {}
        # Map websocket instance -> user_id
        self._ws_user: Dict[WebSocket, int] = {}
        # Set of admin user IDs currently connected to alerts
        self._admin_users: Set[int] = set()
        # Stored event loop for thread-safe cross-thread execution
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store the running ASGI event loop for thread-safe calls."""
        self._loop = loop

    def can_connect(self, user_id: int, max_connections: int) -> bool:
        """Check if user has not reached their maximum allowed active connections."""
        current_count = len(self._user_connections.get(user_id, set()))
        return current_count < max_connections

    def register(
        self, websocket: WebSocket, user_id: int, role: str, channel: str = "alerts"
    ) -> None:
        """Register an authenticated WebSocket connection."""
        if user_id not in self._user_connections:
            self._user_connections[user_id] = set()
        self._user_connections[user_id].add(websocket)
        self._ws_user[websocket] = user_id

        if channel == "alerts":
            if user_id not in self._alert_connections:
                self._alert_connections[user_id] = set()
            self._alert_connections[user_id].add(websocket)
            if role == "admin":
                self._admin_users.add(user_id)

        logger.info(
            "WebSocket registered",
            extra={
                "user_id": user_id,
                "role": role,
                "channel": channel,
                "active_user_connections": len(self._user_connections[user_id]),
            },
        )

    def unregister(self, websocket: WebSocket, user_id: int) -> None:
        """Unregister a WebSocket connection."""
        if user_id in self._user_connections:
            self._user_connections[user_id].discard(websocket)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]

        if user_id in self._alert_connections:
            self._alert_connections[user_id].discard(websocket)
            if not self._alert_connections[user_id]:
                del self._alert_connections[user_id]
                self._admin_users.discard(user_id)

        self._ws_user.pop(websocket, None)
        logger.info("WebSocket unregistered", extra={"user_id": user_id})

    def get_total_connections(self) -> int:
        """Return the total number of open WebSocket connections across all users."""
        return sum(len(conns) for conns in self._user_connections.values())

    async def _send_json_safe(self, ws: WebSocket, message: Dict[str, Any], user_id: int) -> bool:
        """Send a JSON payload to a single websocket, dropping the connection if broken."""
        try:
            await ws.send_json(message)
            return True
        except Exception as exc:
            logger.warning(
                f"Dropping broken WebSocket client for user {user_id}: {exc}",
                extra={"user_id": user_id},
            )
            self.unregister(ws, user_id)
            return False

    async def send_to_user(self, user_id: int, message: Dict[str, Any]) -> None:
        """Send a message to all active alert WebSocket connections for a specific user."""
        conns = list(self._alert_connections.get(user_id, set()))
        for ws in conns:
            await self._send_json_safe(ws, message, user_id)

    async def broadcast_to_admins(
        self, message: Dict[str, Any], exclude_user_id: Optional[int] = None
    ) -> None:
        """Broadcast a message to all connected administrator connections."""
        for admin_id in list(self._admin_users):
            if exclude_user_id is not None and admin_id == exclude_user_id:
                continue
            await self.send_to_user(admin_id, message)

    async def broadcast_alert(self, alert_data: Dict[str, Any], user_id: Optional[int]) -> None:
        """Broadcast an alert message to the alert owner and all admins."""
        message = {"type": "alert", "alert": alert_data}
        if user_id is not None:
            await self.send_to_user(user_id, message)
        await self.broadcast_to_admins(message, exclude_user_id=user_id)

    def push_alert_threadsafe(self, alert_data: Dict[str, Any], user_id: Optional[int]) -> None:
        """Thread-safe dispatch of an alert from worker threads or sync routes."""
        if self._loop is not None and self._loop.is_running():
            try:
                try:
                    current_loop = asyncio.get_running_loop()
                except RuntimeError:
                    current_loop = None

                if current_loop is self._loop:
                    asyncio.create_task(self.broadcast_alert(alert_data, user_id))
                else:
                    asyncio.run_coroutine_threadsafe(
                        self.broadcast_alert(alert_data, user_id),
                        self._loop,
                    )
            except Exception as exc:
                logger.error(f"Error scheduling threadsafe alert push: {exc}", exc_info=True)
        else:
            logger.warning("No running event loop stored in WebSocketManager for alert push")


# Global singleton instance
ws_manager = WebSocketManager()
