from __future__ import annotations

from typing import Any, Callable
from uuid import uuid4

from camera4kivy import Preview
from kivy.clock import mainthread
from kivy.graphics import Color, Ellipse, Line
from kivy.metrics import dp
from kivy.utils import platform

from fitspin.backend_client import PoseBackendClient


POSE_CONNECTIONS = (
    (11, 12),
    (11, 23),
    (12, 24),
    (23, 24),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
    (23, 25),
    (24, 26),
    (25, 27),
    (26, 28),
)


class SquatPreview(Preview):
    def __init__(
        self,
        result_listener: Callable[[dict[str, Any]], None],
        error_listener: Callable[[str], None],
        backend_url_getter: Callable[[], str],
        should_analyze_getter: Callable[[], bool],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._result_listener = result_listener
        self._error_listener = error_listener
        self._backend_url_getter = backend_url_getter
        self._should_analyze_getter = should_analyze_getter
        self._backend_client = PoseBackendClient(
            on_result=self._handle_backend_result,
            on_error=self._handle_backend_error,
            on_transport=self._handle_transport_mode,
        )
        self._session_id = str(uuid4())
        self.annotations: list[dict[str, float]] = []
        self._show_guides = True
        self._connected = False
        self._framing_ok = False

    def connect_rear_camera(self) -> None:
        if self._connected:
            return
        self.connect_camera(
            camera_id="back" if platform == "android" else "0",
            enable_analyze_pixels=True,
            analyze_pixels_resolution=720,
            enable_video=False,
        )
        self._connected = True

    def disconnect_rear_camera(self) -> None:
        if not self._connected:
            return
        self.disconnect_camera()
        self._connected = False
        self._set_annotations([])
        self._backend_client.close_stream()

    def reset_session(
        self,
        on_success: Callable[[dict[str, Any]], None],
    ) -> None:
        self._set_annotations([])
        self._backend_client.reset_session(
            backend_url=self._backend_url_getter(),
            session_id=self._session_id,
            on_success=on_success,
        )

    def clear_annotations(self) -> None:
        self._set_annotations([])

    def close_stream(self) -> None:
        self._backend_client.close_stream()

    def analyze_pixels_callback(
        self,
        pixels: bytes,
        image_size: tuple[int, int],
        image_pos: tuple[float, float],
        image_scale: float,
        mirror: bool,
    ) -> None:
        if not self._should_analyze_getter():
            return
        backend_url = self._backend_url_getter()
        self._backend_client.submit_frame(
            backend_url=backend_url,
            session_id=self._session_id,
            rgba_pixels=pixels,
            image_size=image_size,
            image_pos=image_pos,
            image_scale=image_scale,
            mirror=mirror,
        )

    def canvas_instructions_callback(self, texture: Any, tex_size: Any, tex_pos: Any) -> None:
        if self._show_guides:
            guide_color = (0.4, 0.96, 0.66, 0.75) if self._framing_ok else (0.98, 0.78, 0.18, 0.65)
            guide_x = self.x + dp(34)
            guide_y = self.y + dp(56)
            guide_w = max(dp(80), self.width - dp(68))
            guide_h = max(dp(140), self.height - dp(122))

            Color(*guide_color)
            Line(rounded_rectangle=(guide_x, guide_y, guide_w, guide_h, dp(22), dp(22), dp(22), dp(22)), width=dp(1.6))

            center_x = guide_x + guide_w / 2
            head_y = guide_y + guide_h * 0.83
            shoulder_y = guide_y + guide_h * 0.68
            hip_y = guide_y + guide_h * 0.48
            foot_y = guide_y + guide_h * 0.08
            shoulder_half = guide_w * 0.16
            hip_half = guide_w * 0.11
            leg_offset = guide_w * 0.08

            Color(1, 1, 1, 0.16)
            Line(circle=(center_x, head_y, dp(18)), width=dp(1.2))
            Line(points=[center_x, head_y - dp(18), center_x, hip_y], width=dp(1.2))
            Line(points=[center_x - shoulder_half, shoulder_y, center_x + shoulder_half, shoulder_y], width=dp(1.2))
            Line(points=[center_x - hip_half, hip_y, center_x + hip_half, hip_y], width=dp(1.2))
            Line(points=[center_x, shoulder_y - dp(6), center_x - shoulder_half, guide_y + guide_h * 0.54], width=dp(1.2))
            Line(points=[center_x, shoulder_y - dp(6), center_x + shoulder_half, guide_y + guide_h * 0.54], width=dp(1.2))
            Line(points=[center_x, hip_y, center_x - leg_offset, foot_y], width=dp(1.2))
            Line(points=[center_x, hip_y, center_x + leg_offset, foot_y], width=dp(1.2))

        if not self.annotations:
            return

        Color(0.2, 0.95, 0.55, 0.95)
        points_by_id = {entry["id"]: entry for entry in self.annotations}
        for start, end in POSE_CONNECTIONS:
            if start not in points_by_id or end not in points_by_id:
                continue
            start_point = points_by_id[start]
            end_point = points_by_id[end]
            Line(points=[start_point["x"], start_point["y"], end_point["x"], end_point["y"]], width=dp(1.6))

        Color(1, 1, 1, 0.95)
        for point in self.annotations:
            size = dp(7)
            Ellipse(pos=(point["x"] - size / 2, point["y"] - size / 2), size=(size, size))

    def on_leave(self) -> None:
        self.disconnect_rear_camera()

    def _handle_backend_result(self, result: dict[str, Any], context: dict[str, Any]) -> None:
        self._framing_ok = bool(result.get("framing_ok", False))
        points = []
        image_width, image_height = context["image_size"]
        image_pos_x, image_pos_y = context["image_pos"]
        scale = context["image_scale"]
        mirror = context["mirror"]

        for index, landmark in enumerate(result.get("landmarks", [])):
            visibility = landmark.get("visibility", 0.0)
            if visibility < 0.35:
                continue

            x = float(landmark["x"]) * image_width
            y = (1.0 - float(landmark["y"])) * image_height
            if mirror:
                x = image_width - x
            points.append(
                {
                    "id": index,
                    "x": x * scale + image_pos_x,
                    "y": y * scale + image_pos_y,
                }
            )

        self._set_annotations(points)
        self._notify_result_listener(result)

    @mainthread
    def _set_annotations(self, points: list[dict[str, float]]) -> None:
        if self.camera_connected:
            self.annotations = list(points)
        else:
            self.annotations = []

    @mainthread
    def _notify_result_listener(self, result: dict[str, Any]) -> None:
        self._result_listener(result)

    @mainthread
    def _handle_backend_error(self, message: str) -> None:
        self._error_listener(message)

    @mainthread
    def _handle_transport_mode(self, mode: str) -> None:
        self._result_listener({"transport_mode": mode})
