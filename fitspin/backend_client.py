from __future__ import annotations

import base64
import json
import threading
import time
import urllib.error
import urllib.request
from io import BytesIO
from typing import Any, Callable

from kivy.clock import Clock
from PIL import Image

try:
    import websocket
except ImportError:  # pragma: no cover
    websocket = None


class PoseBackendClient:
    def __init__(
        self,
        on_result: Callable[[dict[str, Any], dict[str, Any]], None],
        on_error: Callable[[str], None],
        on_transport: Callable[[str], None] | None = None,
    ) -> None:
        self._on_result = on_result
        self._on_error = on_error
        self._on_transport = on_transport or (lambda mode: None)
        self._lock = threading.Lock()
        self._request_in_flight = False
        self._last_submit_at = 0.0
        self._control_request_in_flight = False
        self._ws = None
        self._ws_url: str | None = None
        self._transport_mode = "HTTP fallback"
        self._transport_reported = False

    def submit_frame(
        self,
        backend_url: str,
        exercise: str,
        session_id: str,
        rgba_pixels: bytes,
        image_size: tuple[int, int],
        image_pos: tuple[float, float],
        image_scale: float,
        mirror: bool,
        min_interval: float = 0.12,
    ) -> None:
        backend_url = backend_url.strip().rstrip("/")
        if not backend_url:
            return

        now = time.monotonic()
        with self._lock:
            if self._request_in_flight or now - self._last_submit_at < min_interval:
                return
            self._request_in_flight = True
            self._last_submit_at = now

        context = {
            "image_size": image_size,
            "image_pos": image_pos,
            "image_scale": image_scale,
            "mirror": mirror,
        }
        threading.Thread(
            target=self._submit_worker,
            args=(backend_url, exercise, session_id, rgba_pixels, image_size, context),
            daemon=True,
        ).start()

    def reset_session(
        self,
        backend_url: str,
        exercise: str,
        session_id: str,
        on_success: Callable[[dict[str, Any]], None],
    ) -> None:
        backend_url = backend_url.strip().rstrip("/")
        if not backend_url:
            Clock.schedule_once(lambda dt: self._on_error("Backend URL cannot be empty."), 0)
            return

        with self._lock:
            if self._control_request_in_flight:
                return
            self._control_request_in_flight = True

        threading.Thread(
            target=self._reset_session_worker,
            args=(backend_url, exercise, session_id, on_success),
            daemon=True,
        ).start()

    def close_stream(self) -> None:
        with self._lock:
            ws = self._ws
            self._ws = None
            self._ws_url = None
            self._transport_mode = "HTTP fallback"
            self._transport_reported = False

        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    def _submit_worker(
        self,
        backend_url: str,
        exercise: str,
        session_id: str,
        rgba_pixels: bytes,
        image_size: tuple[int, int],
        context: dict[str, Any],
    ) -> None:
        error_message = None
        try:
            image_b64 = self._encode_image(rgba_pixels, image_size)
            payload = {
                "action": "analyze",
                "exercise": exercise,
                "session_id": session_id,
                "image_b64": image_b64,
            }

            if websocket is not None:
                try:
                    result = self._send_via_websocket(backend_url, payload)
                    self._set_transport_mode("WebSocket")
                except Exception:
                    self._close_socket_on_failure()
                    result = self._send_via_http(backend_url, payload)
                    self._set_transport_mode("HTTP fallback")
            else:
                result = self._send_via_http(backend_url, payload)
                self._set_transport_mode("HTTP fallback")

            Clock.schedule_once(lambda dt: self._on_result(result, context), 0)
        except urllib.error.HTTPError as exc:
            try:
                details = exc.read().decode("utf-8")
            except Exception:
                details = ""
            error_message = f"Backend HTTP {exc.code} {details}".strip()
        except urllib.error.URLError:
            error_message = "Backend is unreachable. Check the phone and server are on the same network."
        except Exception as exc:
            error_message = f"Unexpected backend error: {exc}"
        finally:
            with self._lock:
                self._request_in_flight = False
            if error_message:
                Clock.schedule_once(lambda dt: self._on_error(error_message), 0)

    def _reset_session_worker(
        self,
        backend_url: str,
        exercise: str,
        session_id: str,
        on_success: Callable[[dict[str, Any]], None],
    ) -> None:
        error_message = None
        try:
            request = urllib.request.Request(
                url=f"{backend_url}/api/v1/exercise/reset",
                data=json.dumps({"exercise": exercise, "session_id": session_id}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                raw = response.read().decode("utf-8")
            result = json.loads(raw)
            Clock.schedule_once(lambda dt: on_success(result), 0)
        except urllib.error.HTTPError as exc:
            try:
                details = exc.read().decode("utf-8")
            except Exception:
                details = ""
            error_message = f"Backend HTTP {exc.code} {details}".strip()
        except urllib.error.URLError:
            error_message = "Backend is unreachable. Check the phone and server are on the same network."
        except Exception as exc:
            error_message = f"Unexpected backend error: {exc}"
        finally:
            with self._lock:
                self._control_request_in_flight = False
            if error_message:
                Clock.schedule_once(lambda dt: self._on_error(error_message), 0)

    def _send_via_websocket(self, backend_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        ws = self._ensure_websocket(backend_url)
        ws.send(json.dumps(payload))
        raw = ws.recv()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def _send_via_http(self, backend_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url=f"{backend_url}/api/v1/exercise/analyze",
            data=json.dumps(
                {
                    "exercise": payload["exercise"],
                    "session_id": payload["session_id"],
                    "image_b64": payload["image_b64"],
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read().decode("utf-8")
        return json.loads(raw)

    def _ensure_websocket(self, backend_url: str):
        ws_url = self._to_ws_url(backend_url)
        with self._lock:
            existing = self._ws
            existing_url = self._ws_url

        if existing is not None and existing_url == ws_url:
            return existing

        self.close_stream()
        new_ws = websocket.create_connection(ws_url, timeout=5)
        with self._lock:
            self._ws = new_ws
            self._ws_url = ws_url
        return new_ws

    def _close_socket_on_failure(self) -> None:
        with self._lock:
            ws = self._ws
            self._ws = None
            self._ws_url = None
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    def _set_transport_mode(self, mode: str) -> None:
        notify = False
        with self._lock:
            if self._transport_mode != mode or not self._transport_reported:
                self._transport_mode = mode
                self._transport_reported = True
                notify = True
        if notify:
            Clock.schedule_once(lambda dt: self._on_transport(mode), 0)

    @staticmethod
    def _to_ws_url(backend_url: str) -> str:
        if backend_url.startswith("https://"):
            return "wss://" + backend_url[len("https://") :].rstrip("/") + "/ws/exercise"
        if backend_url.startswith("http://"):
            return "ws://" + backend_url[len("http://") :].rstrip("/") + "/ws/exercise"
        return backend_url.rstrip("/") + "/ws/exercise"

    @staticmethod
    def _encode_image(rgba_pixels: bytes, image_size: tuple[int, int]) -> str:
        image = Image.frombytes("RGBA", image_size, rgba_pixels)
        image = image.convert("RGB")
        image.thumbnail((320, 320))
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=72, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("ascii")
