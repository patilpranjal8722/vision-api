"""Manual developer test page for real-time WebSocket feeds (/ws-test).

Active exclusively when DEBUG=true. Returns 404 in production environments.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse
from app.core.config import get_settings

router = APIRouter(tags=["Developer Tools"])

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>vision-api — WebSocket Test Bench</title>
    <style>
        :root {
            --bg: #0f172a;
            --panel: #1e293b;
            --text: #f8fafc;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
            --border: #334155;
            --success: #10b981;
            --error: #ef4444;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
        }
        h1, h2 { margin-top: 0; font-weight: 600; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .card {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
        }
        input[type="text"], input[type="password"], input[type="file"] {
            width: 100%;
            padding: 8px 12px;
            margin: 8px 0 16px 0;
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text);
            box-sizing: border-box;
        }
        button {
            background: var(--accent);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: 500;
            cursor: pointer;
            margin-right: 8px;
            margin-bottom: 8px;
        }
        button:hover { background: var(--accent-hover); }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .log-box {
            background: #020617;
            border: 1px solid var(--border);
            border-radius: 4px;
            height: 220px;
            overflow-y: auto;
            padding: 10px;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 12px;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--error);
            margin-right: 6px;
        }
        .status.connected { background: var(--success); }
        .webcam-container {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <h1>vision-api WebSocket Test Bench</h1>
    <p style="color: #94a3b8;">Manual test harness for verifying first-message authentication, live alert pushes, and binary frame stream inference.</p>

    <!-- 1. Authentication Section -->
    <div class="card">
        <h2>1. Authentication</h2>
        <div style="display: flex; gap: 12px; max-width: 600px;">
            <input type="text" id="username" placeholder="Username or Email" value="alice_vision">
            <input type="password" id="password" placeholder="Password" value="Str0ng!Pass">
            <button id="loginBtn" onclick="login()">Log In</button>
        </div>
        <div id="authStatus" style="font-size: 13px; color: #94a3b8;">Not logged in.</div>
    </div>

    <div class="grid">
        <!-- 2. Alerts WebSocket (/ws/alerts) -->
        <div class="card">
            <h2><span id="alertsDot" class="status"></span>2. Live Alerts (/ws/alerts)</h2>
            <button id="connectAlertsBtn" onclick="connectAlerts()">Connect</button>
            <button id="pingBtn" onclick="sendPing()" disabled>Send Ping</button>
            <button onclick="clearLog('alertsLog')">Clear</button>
            <div id="alertsLog" class="log-box" style="margin-top: 12px;"></div>
        </div>

        <!-- 3. Frame Stream WebSocket (/ws/stream) -->
        <div class="card">
            <h2><span id="streamDot" class="status"></span>3. Video Stream (/ws/stream)</h2>
            <button id="connectStreamBtn" onclick="connectStream()">Connect</button>
            <button onclick="clearLog('streamLog')">Clear</button>
            
            <div style="margin-top: 16px;">
                <label>Send Single Image Frame:</label>
                <input type="file" id="framePicker" accept="image/jpeg,image/png,image/webp" onchange="sendPickedFile(this)">
            </div>

            <div class="webcam-container">
                <input type="checkbox" id="webcamToggle" onchange="toggleWebcam(this.checked)">
                <label for="webcamToggle">Send Webcam Feed (1 frame/sec)</label>
            </div>
            <video id="webcamVideo" autoplay playsinline style="display: none;"></video>
            <canvas id="captureCanvas" style="display: none;"></canvas>

            <div id="streamLog" class="log-box" style="margin-top: 12px;"></div>
        </div>
    </div>

    <script>
        let authToken = "";
        let alertsWs = null;
        let streamWs = null;
        let webcamStream = null;
        let webcamInterval = null;

        function log(boxId, msg) {
            const box = document.getElementById(boxId);
            const ts = new Date().toISOString().split("T")[1].slice(0, 8);
            box.textContent += `[${ts}] ${msg}\\n`;
            box.scrollTop = box.scrollHeight;
        }

        function clearLog(boxId) {
            document.getElementById(boxId).textContent = "";
        }

        async function login() {
            const u = document.getElementById("username").value.trim();
            const p = document.getElementById("password").value;
            const statusDiv = document.getElementById("authStatus");

            statusDiv.textContent = "Authenticating...";
            const body = new URLSearchParams();
            body.append("username", u);
            body.append("password", p);

            try {
                const res = await fetch("/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: body.toString()
                });
                if (res.ok) {
                    const data = await res.json();
                    authToken = data.access_token;
                    statusDiv.textContent = `Logged in as '${u}'. Access token acquired.`;
                    statusDiv.style.color = "var(--success)";
                } else {
                    const err = await res.json();
                    statusDiv.textContent = `Login failed: ${JSON.stringify(err.detail)}`;
                    statusDiv.style.color = "var(--error)";
                }
            } catch (err) {
                statusDiv.textContent = `Network error: ${err.message}`;
                statusDiv.style.color = "var(--error)";
            }
        }

        function getWsUrl(path) {
            const proto = location.protocol === "https:" ? "wss:" : "ws:";
            return `${proto}//${location.host}${path}`;
        }

        function connectAlerts() {
            if (!authToken) {
                alert("Please log in first to acquire an access token.");
                return;
            }
            if (alertsWs) alertsWs.close();

            const url = getWsUrl("/ws/alerts");
            alertsWs = new WebSocket(url);
            log("alertsLog", `Connecting to ${url}...`);

            alertsWs.onopen = () => {
                log("alertsLog", "Connected. Sending auth handshake message...");
                alertsWs.send(JSON.stringify({ type: "auth", token: authToken }));
            };

            alertsWs.onmessage = (event) => {
                log("alertsLog", `RECV: ${event.data}`);
                const data = JSON.parse(event.data);
                if (data.type === "auth_ok") {
                    document.getElementById("alertsDot").classList.add("connected");
                    document.getElementById("pingBtn").disabled = false;
                }
            };

            alertsWs.onclose = (event) => {
                document.getElementById("alertsDot").classList.remove("connected");
                document.getElementById("pingBtn").disabled = true;
                log("alertsLog", `Disconnected (code: ${event.code}, reason: ${event.reason})`);
            };
        }

        function sendPing() {
            if (alertsWs && alertsWs.readyState === WebSocket.OPEN) {
                log("alertsLog", 'SEND: {"type": "ping"}');
                alertsWs.send(JSON.stringify({ type: "ping" }));
            }
        }

        function connectStream() {
            if (!authToken) {
                alert("Please log in first to acquire an access token.");
                return;
            }
            if (streamWs) streamWs.close();

            const url = getWsUrl("/ws/stream");
            streamWs = new WebSocket(url);
            log("streamLog", `Connecting to ${url}...`);

            streamWs.onopen = () => {
                log("streamLog", "Connected. Sending auth handshake message...");
                streamWs.send(JSON.stringify({ type: "auth", token: authToken }));
            };

            streamWs.onmessage = (event) => {
                log("streamLog", `RECV: ${event.data}`);
                const data = JSON.parse(event.data);
                if (data.type === "auth_ok") {
                    document.getElementById("streamDot").classList.add("connected");
                }
            };

            streamWs.onclose = (event) => {
                document.getElementById("streamDot").classList.remove("connected");
                log("streamLog", `Disconnected (code: ${event.code}, reason: ${event.reason})`);
            };
        }

        function sendPickedFile(input) {
            const file = input.files[0];
            if (!file) return;
            if (!streamWs || streamWs.readyState !== WebSocket.OPEN) {
                alert("Please connect to /ws/stream first.");
                return;
            }
            const reader = new FileReader();
            reader.onload = () => {
                log("streamLog", `Sending binary frame (${file.size} bytes)...`);
                streamWs.send(reader.result);
            };
            reader.readAsArrayBuffer(file);
        }

        async function toggleWebcam(enabled) {
            if (!enabled) {
                if (webcamInterval) clearInterval(webcamInterval);
                if (webcamStream) {
                    webcamStream.getTracks().forEach(track => track.stop());
                }
                return;
            }
            if (!streamWs || streamWs.readyState !== WebSocket.OPEN) {
                alert("Please connect to /ws/stream first.");
                document.getElementById("webcamToggle").checked = false;
                return;
            }

            try {
                webcamStream = await navigator.mediaDevices.getUserMedia({ video: true });
                const video = document.getElementById("webcamVideo");
                const canvas = document.getElementById("captureCanvas");
                video.srcObject = webcamStream;
                await video.play();

                canvas.width = 640;
                canvas.height = 480;
                const ctx = canvas.getContext("2d");

                webcamInterval = setInterval(() => {
                    if (!streamWs || streamWs.readyState !== WebSocket.OPEN) return;
                    ctx.drawImage(video, 0, 0, 640, 480);
                    canvas.toBlob((blob) => {
                        if (blob) {
                            blob.arrayBuffer().then((buf) => {
                                streamWs.send(buf);
                            });
                        }
                    }, "image/jpeg", 0.7);
                }, 1000);
                log("streamLog", "Webcam streaming started (1 FPS JPEG capture).");
            } catch (err) {
                log("streamLog", `Webcam access error: ${err.message}`);
                document.getElementById("webcamToggle").checked = false;
            }
        }
    </script>
</body>
</html>
"""


@router.get(
    "/ws-test",
    response_class=HTMLResponse,
    summary="Manual developer test page for WebSocket feeds",
)
def get_ws_test_page() -> HTMLResponse:
    """Serve self-contained test bench for /ws/alerts and /ws/stream.

    Returns 404 in production when DEBUG=false.
    """
    settings = get_settings()
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test page is only available in DEBUG mode",
        )
    return HTMLResponse(content=HTML_CONTENT)
