from __future__ import annotations

from pathlib import Path
import time
from typing import TYPE_CHECKING

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from fitspin.slot_machine import SlotMachineEngine

if TYPE_CHECKING:
    from fitspin.preview import SquatPreview


KV = """
#:import dp kivy.metrics.dp

<OverlayCard@BoxLayout>:
    orientation: "vertical"
    padding: "12dp"
    spacing: "6dp"
    size_hint: None, None
    canvas.before:
        Color:
            rgba: 0.05, 0.07, 0.08, 0.82
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [18, 18, 18, 18]
        Color:
            rgba: 0.98, 0.78, 0.18, 0.95
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 18, 18, 18, 18)
            width: 1.2

<FitSpinRoot>:
    orientation: "vertical"
    preview_box: preview_box
    FloatLayout:
        BoxLayout:
            id: preview_box
            size_hint: 1, 1

        OverlayCard:
            size: "182dp", "198dp"
            pos_hint: {"x": 0.03, "top": 0.97}
            Label:
                text: app.exercise_title
                bold: True
                color: 1, 1, 1, 1
                font_size: "18sp"
                halign: "left"
                text_size: self.size
            Label:
                text: "Reps: " + str(app.rep_count)
                color: 1, 1, 1, 1
                halign: "left"
                text_size: self.size
            Label:
                text: "Phase: " + app.phase_label
                color: 0.78, 0.9, 1, 1
                halign: "left"
                text_size: self.size
            Label:
                text: app.debug_metric
                color: 0.8, 0.82, 0.85, 1
                font_size: "12sp"
                halign: "left"
                text_size: self.size
            Label:
                text: app.calibration_text
                color: (0.5, 1, 0.72, 1) if app.calibration_ready else (0.98, 0.78, 0.18, 1)
                font_size: "12sp"
                halign: "left"
                text_size: self.size
            Label:
                text: app.framing_text
                color: 0.88, 0.9, 0.92, 1
                font_size: "12sp"
                halign: "left"
                text_size: self.size
            Label:
                text: app.transport_text
                color: 0.88, 0.9, 0.92, 1
                font_size: "12sp"
                halign: "left"
                text_size: self.size
            Label:
                text: "Set: " + ("LIVE " + app.set_duration_text if app.calibration_ready else "CAL " + app.set_duration_text if app.set_active else "idle")
                color: (0.5, 1, 0.72, 1) if app.set_active else (0.88, 0.9, 0.92, 1)
                font_size: "12sp"
                halign: "left"
                text_size: self.size

        OverlayCard:
            size: "226dp", "158dp"
            pos_hint: {"right": 0.97, "top": 0.97}
            Label:
                text: "REP SLOT"
                bold: True
                color: 1, 1, 1, 1
                font_size: "18sp"
                halign: "left"
                text_size: self.size
            BoxLayout:
                size_hint_y: None
                height: "48dp"
                spacing: "6dp"
                Label:
                    text: app.slot_symbols[0]
                    color: 0.98, 0.78, 0.18, 1
                    font_size: "20sp"
                    canvas.before:
                        Color:
                            rgba: 1, 1, 1, 0.08
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10, 10, 10, 10]
                Label:
                    text: app.slot_symbols[1]
                    color: 0.98, 0.78, 0.18, 1
                    font_size: "20sp"
                    canvas.before:
                        Color:
                            rgba: 1, 1, 1, 0.08
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10, 10, 10, 10]
                Label:
                    text: app.slot_symbols[2]
                    color: 0.98, 0.78, 0.18, 1
                    font_size: "20sp"
                    canvas.before:
                        Color:
                            rgba: 1, 1, 1, 0.08
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10, 10, 10, 10]
            Label:
                text: app.slot_status
                color: 1, 1, 1, 1
                halign: "left"
                text_size: self.size
            Label:
                text: "Coins: " + str(app.coin_score)
                color: 0.5, 1, 0.72, 1
                bold: True
                halign: "left"
                text_size: self.size

        OverlayCard:
            size_hint: None, None
            width: min(root.width * 0.92, dp(420))
            height: "336dp"
            pos_hint: {"center_x": 0.5, "y": 0.03}
            Label:
                text: "Backend URL"
                bold: True
                color: 1, 1, 1, 1
                halign: "left"
                text_size: self.size
            Label:
                text: "Exercise"
                bold: True
                color: 1, 1, 1, 1
                halign: "left"
                text_size: self.size
            BoxLayout:
                size_hint_y: None
                height: "42dp"
                spacing: "8dp"
                Button:
                    text: "Squat"
                    background_normal: ""
                    background_color: (0.98, 0.78, 0.18, 1) if app.exercise_key == "squat" else (0.18, 0.2, 0.22, 1)
                    color: (0.04, 0.05, 0.05, 1) if app.exercise_key == "squat" else (1, 1, 1, 1)
                    on_release: app.select_exercise("squat")
                Button:
                    text: "Pull-up"
                    background_normal: ""
                    background_color: (0.98, 0.78, 0.18, 1) if app.exercise_key == "pullup" else (0.18, 0.2, 0.22, 1)
                    color: (0.04, 0.05, 0.05, 1) if app.exercise_key == "pullup" else (1, 1, 1, 1)
                    on_release: app.select_exercise("pullup")
            TextInput:
                id: backend_input
                text: app.backend_url
                multiline: False
                size_hint_y: None
                height: "40dp"
                foreground_color: 1, 1, 1, 1
                background_color: 0.1, 0.12, 0.14, 1
                cursor_color: 1, 1, 1, 1
                on_text_validate: app.update_backend_url(self.text)
            BoxLayout:
                size_hint_y: None
                height: "42dp"
                spacing: "8dp"
                Button:
                    text: "Save URL"
                    background_normal: ""
                    background_color: 0.98, 0.78, 0.18, 1
                    color: 0.04, 0.05, 0.05, 1
                    on_release: app.update_backend_url(backend_input.text)
                Button:
                    text: "Start Camera" if not app.camera_running else "Stop Camera"
                    background_normal: ""
                    background_color: (0.26, 0.87, 0.62, 1) if not app.camera_running else (0.92, 0.36, 0.32, 1)
                    color: 0.04, 0.05, 0.05, 1
                    on_release: app.toggle_camera()
            BoxLayout:
                size_hint_y: None
                height: "42dp"
                spacing: "8dp"
                Button:
                    text: "End Set" if app.set_active else "Start Set"
                    background_normal: ""
                    background_color: (0.92, 0.36, 0.32, 1) if app.set_active else (0.4, 0.73, 0.96, 1)
                    color: 0.04, 0.05, 0.05, 1
                    on_release: app.toggle_set()
                Button:
                    text: "Reset Counters"
                    background_normal: ""
                    background_color: 0.86, 0.86, 0.9, 1
                    color: 0.04, 0.05, 0.05, 1
                    on_release: app.reset_session()
            Label:
                text: app.current_set_summary
                color: 0.88, 0.9, 0.92, 1
                font_size: "12sp"
                halign: "left"
                text_size: self.size
            Label:
                text: app.last_set_summary
                color: 0.78, 0.9, 1, 1
                font_size: "12sp"
                halign: "left"
                text_size: self.size
            Label:
                text: app.status_text
                color: 0.88, 0.9, 0.92, 1
                font_size: "12sp"
                halign: "left"
                text_size: self.size
"""


class FitSpinRoot(BoxLayout):
    preview_box = ObjectProperty(None)


class FitSpinApp(App):
    rep_count = NumericProperty(0)
    coin_score = NumericProperty(0)
    exercise_key = StringProperty("squat")
    exercise_display = StringProperty("Squat")
    exercise_title = StringProperty("SQUAT MODE")
    phase_label = StringProperty("waiting")
    debug_metric = StringProperty("angle: --")
    calibration_text = StringProperty("Calibration: pending")
    framing_text = StringProperty("Framing: align your whole body in the guide.")
    transport_text = StringProperty("Transport: connecting...")
    status_text = StringProperty("Choose an exercise, set the backend URL, then start the rear camera.")
    backend_url = StringProperty("http://192.168.0.10:8000")
    slot_symbols = ListProperty(["-", "-", "-"])
    slot_status = StringProperty("1 rep = 1 spin")
    camera_running = BooleanProperty(False)
    set_active = BooleanProperty(False)
    calibration_ready = BooleanProperty(False)
    set_duration_text = StringProperty("00:00")
    current_set_summary = StringProperty("Current set: inactive")
    last_set_summary = StringProperty("Last set: no completed set yet")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._settings_path: Path | None = None
        self._settings: JsonStore | None = None
        self._slot_machine = SlotMachineEngine()
        self._root: FitSpinRoot | None = None
        self._preview: SquatPreview | None = None
        self._last_rep_count = 0
        self._set_started_at: float | None = None

    def build(self):
        try:
            self._init_settings()
            Builder.load_string(KV)
            root = FitSpinRoot()
            self._root = root
            self._load_settings()
            self._apply_exercise_ui()
            Clock.schedule_interval(self._tick_slot_machine, 1 / 12)
            return root
        except Exception as exc:
            self._write_runtime_error(exc)
            return self._build_fallback_ui(exc)

    def on_start(self):
        self.status_text = "Choose an exercise, set the backend URL, then start the rear camera."

    def on_stop(self):
        if self._preview:
            self._preview.disconnect_rear_camera()

    def update_backend_url(self, value: str) -> None:
        clean = value.strip().rstrip("/")
        if not clean:
            self.status_text = "Backend URL cannot be empty."
            return
        self.backend_url = clean
        if self._settings is not None:
            self._settings.put("network", backend_url=self.backend_url)
        self.transport_text = "Transport: reconnecting..."
        if self._preview:
            self._preview.close_stream()
        self.status_text = f"Backend saved: {self.backend_url}"

    def select_exercise(self, exercise: str) -> None:
        normalized = "pullup" if exercise == "pullup" else "squat"
        if self.exercise_key == normalized:
            return
        previous_display = self.exercise_display
        self.exercise_key = normalized
        if self._settings is not None:
            self._settings.put("workout", exercise=self.exercise_key)
        if self.set_active:
            self._finalize_set(f"{previous_display} set ended.")
        self._apply_exercise_ui()
        self.rep_count = 0
        self.phase_label = "waiting"
        self.debug_metric = "angle: --"
        self.calibration_ready = False
        self.calibration_text = "Calibration: pending"
        self.framing_text = "Framing: align your whole body in the guide."
        self.transport_text = "Transport: connecting..."
        self.current_set_summary = "Current set: inactive"
        self.last_set_summary = f"Last set: no completed {self.exercise_display.lower()} set yet"
        self._last_rep_count = 0
        if self._preview:
            self._preview.close_stream()
            self._preview.clear_annotations()
        self.status_text = f"Exercise selected: {self.exercise_display}. Start a new set when ready."

    def toggle_camera(self) -> None:
        if self.camera_running:
            if self.set_active:
                self._finalize_set("Camera stopped. Set saved.")
            self._preview.disconnect_rear_camera()
            self.camera_running = False
            self.status_text = "Camera stopped."
            return
        if not self._ensure_preview():
            return
        self._request_android_permissions()
        self._preview.connect_rear_camera()
        self.camera_running = True
        self.status_text = self._camera_started_text()

    def reset_session(self) -> None:
        if not self._preview:
            return
        self.set_active = False
        self.calibration_ready = False
        self._set_started_at = None
        self.set_duration_text = "00:00"
        self.current_set_summary = "Current set: inactive"
        self.calibration_text = "Calibration: pending"
        self.framing_text = "Framing: align your whole body in the guide."
        self.transport_text = "Transport: connecting..."
        self.status_text = f"Resetting {self.exercise_display.lower()} session..."
        self._preview.clear_annotations()
        self._preview.reset_session(self._handle_reset_result)

    def toggle_set(self) -> None:
        if self.set_active:
            self._finalize_set("Set ended.")
            return
        self.start_set()

    def start_set(self) -> None:
        if not self._preview:
            return
        if not self.camera_running:
            self.status_text = "Start the camera first."
            return
        self.set_active = False
        self.calibration_ready = False
        self._set_started_at = None
        self.set_duration_text = "00:00"
        self.current_set_summary = "Current set: preparing..."
        self.calibration_text = "Calibration: pending"
        self.framing_text = "Framing: align your whole body in the guide."
        self.transport_text = "Transport: connecting..."
        self.status_text = f"Starting a new {self.exercise_display.lower()} set..."
        self._preview.clear_annotations()
        self._preview.reset_session(self._handle_start_set_result)

    def _handle_pose_result(self, result: dict) -> None:
        if "transport_mode" in result:
            self.transport_text = f"Transport: {result['transport_mode']}"
            return

        framing_feedback = result.get("framing_feedback")
        framing_ok = bool(result.get("framing_ok", False))
        if isinstance(framing_feedback, str) and framing_feedback:
            self.framing_text = f"Framing: {framing_feedback}"

        if not self.set_active:
            if self.camera_running:
                self.status_text = (
                    "Framing looks good. Tap Start Set, then hold the start position to calibrate."
                    if framing_ok
                    else str(framing_feedback or "Align your whole body in the guide before starting.")
                )
            return

        self.calibration_ready = bool(result.get("calibrated", False))
        calibration_progress = int(result.get("calibration_progress", 0))
        calibration_required = int(result.get("calibration_required", 0))
        top_angle = result.get("top_angle")

        if self.calibration_ready:
            self.phase_label = result.get("phase", "up")
            if isinstance(top_angle, (int, float)):
                self.calibration_text = f"Calibration: ready ({top_angle:.0f} deg)"
            else:
                self.calibration_text = "Calibration: ready"
        else:
            self.phase_label = "calibrating"
            self.calibration_text = f"Calibration: {calibration_progress}/{calibration_required}"

        self.rep_count = int(result.get("rep_count", 0))

        metric_label = str(result.get("metric_label", "angle")).strip().lower()
        angle = result.get("primary_angle", result.get("squat_angle"))
        self.debug_metric = f"{metric_label}: {angle:.1f}" if isinstance(angle, (int, float)) else f"{metric_label}: --"

        status = result.get("status") or "Tracking..."
        self.status_text = status

        if self.rep_count > self._last_rep_count or result.get("rep_completed"):
            self._slot_machine.trigger_spin()
        self._last_rep_count = self.rep_count

    def _handle_pose_error(self, message: str) -> None:
        self.status_text = message

    def _tick_slot_machine(self, dt: float) -> None:
        del dt
        if self.set_active and self._set_started_at is not None:
            elapsed = max(0, int(time.monotonic() - self._set_started_at))
            self.set_duration_text = self._format_duration(elapsed)
        self._slot_machine.tick()
        self._sync_slot_machine_ui()

    def _handle_reset_result(self, result: dict) -> None:
        self._slot_machine.reset()
        self.rep_count = int(result.get("rep_count", 0))
        self.phase_label = result.get("phase", "up")
        self.debug_metric = "angle: --"
        self.calibration_ready = bool(result.get("calibrated", False))
        self.calibration_text = "Calibration: pending"
        self.framing_text = "Framing: align your whole body in the guide."
        self._last_rep_count = self.rep_count
        self.current_set_summary = "Current set: inactive"
        self._sync_slot_machine_ui()
        self.status_text = result.get("status", "Session reset.")

    def _handle_start_set_result(self, result: dict) -> None:
        self._slot_machine.reset()
        self.rep_count = int(result.get("rep_count", 0))
        self.phase_label = "calibrating"
        self.debug_metric = "angle: --"
        self.calibration_ready = False
        calibration_required = int(result.get("calibration_required", 0))
        self.calibration_text = f"Calibration: 0/{calibration_required}" if calibration_required else "Calibration: pending"
        self.framing_text = "Framing: align your whole body in the guide."
        self._last_rep_count = self.rep_count
        self.set_active = True
        self._set_started_at = time.monotonic()
        self.set_duration_text = "00:00"
        self.current_set_summary = f"Current set: {self.exercise_display.lower()} | calibrating | 0 reps | 0 coins | 00:00"
        self._sync_slot_machine_ui()
        self.status_text = result.get("status", f"Set started. Hold the {self.exercise_display.lower()} start position for calibration.")

    def _sync_slot_machine_ui(self) -> None:
        self.slot_symbols = list(self._slot_machine.state.reels)
        self.coin_score = self._slot_machine.state.score
        self.slot_status = (
            "Spinning..."
            if self._slot_machine.state.spinning
            else (
                f"+{self._slot_machine.state.last_reward} coins | {self._slot_machine.state.last_combo}"
                if self._slot_machine.state.last_combo
                else f"1 {self.exercise_display.lower()} = 1 spin"
            )
        )
        if self.set_active:
            set_mode = "live" if self.calibration_ready else "calibrating"
            self.current_set_summary = (
                f"Current set: {self.exercise_display.lower()} | {set_mode} | {self.rep_count} reps | {self.coin_score} coins | {self.set_duration_text}"
            )

    def _finalize_set(self, status_text: str) -> None:
        if self._set_started_at is None:
            self.set_active = False
            self.current_set_summary = "Current set: inactive"
            self.status_text = status_text
            return

        duration_seconds = max(0, int(time.monotonic() - self._set_started_at))
        duration_text = self._format_duration(duration_seconds)
        self.set_active = False
        self.calibration_ready = False
        self._set_started_at = None
        self.set_duration_text = "00:00"
        self.calibration_text = "Calibration: pending"
        self.framing_text = "Framing: align your whole body in the guide."
        self.current_set_summary = "Current set: inactive"
        self.last_set_summary = f"Last set ({self.exercise_display}): {self.rep_count} reps | {self.coin_score} coins | {duration_text}"
        if self._preview:
            self._preview.clear_annotations()
        self.status_text = status_text

    @staticmethod
    def _format_duration(duration_seconds: int) -> str:
        minutes, seconds = divmod(duration_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _load_settings(self) -> None:
        if self._settings is not None and self._settings.exists("network"):
            self.backend_url = self._settings.get("network").get("backend_url", self.backend_url)
        if self._settings is not None and self._settings.exists("workout"):
            stored = self._settings.get("workout").get("exercise", self.exercise_key)
            self.exercise_key = "pullup" if stored == "pullup" else "squat"

    def _init_settings(self) -> None:
        settings_path = Path(self.user_data_dir) / "fitspin_settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path = settings_path
        try:
            self._settings = JsonStore(str(settings_path))
        except Exception:
            self._settings = None

    def _write_runtime_error(self, exc: Exception) -> None:
        try:
            error_dir = Path(self.user_data_dir)
            error_dir.mkdir(parents=True, exist_ok=True)
            error_path = error_dir / "fitspin_runtime_error.txt"
            error_path.write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _build_fallback_ui(exc: Exception) -> BoxLayout:
        root = BoxLayout(orientation="vertical", padding=24, spacing=12)
        root.add_widget(
            Label(
                text=(
                    "App startup failed.\n\n"
                    f"{type(exc).__name__}: {exc}\n\n"
                    "Please reinstall the latest APK or send this message."
                ),
                halign="center",
                valign="middle",
            )
        )
        return root

    def _apply_exercise_ui(self) -> None:
        if self.exercise_key == "pullup":
            self.exercise_display = "Pull-up"
            self.exercise_title = "PULL-UP MODE"
        else:
            self.exercise_display = "Squat"
            self.exercise_title = "SQUAT MODE"
        if not self._slot_machine.state.spinning:
            self.slot_status = f"1 {self.exercise_display.lower()} = 1 spin"

    def _camera_started_text(self) -> str:
        if self.exercise_key == "pullup":
            return "Camera started. Step under the bar, show your full body and both hands, then tap Start Set."
        return "Camera started. Place the phone so your full body is visible, then tap Start Set."

    def _ensure_preview(self) -> bool:
        if self._preview is not None:
            return True
        if not self._root or not self._root.preview_box:
            self.status_text = "Preview container is not ready yet."
            return False
        try:
            from fitspin.preview import SquatPreview

            self._preview = SquatPreview(
                result_listener=self._handle_pose_result,
                error_listener=self._handle_pose_error,
                backend_url_getter=lambda: self.backend_url,
                exercise_getter=lambda: self.exercise_key,
                should_analyze_getter=lambda: self.camera_running,
                aspect_ratio="16:9",
                orientation="portrait",
            )
            self._root.preview_box.add_widget(self._preview)
            return True
        except Exception as exc:
            self.status_text = f"Preview init failed: {exc}"
            self._preview = None
            return False

    def _request_android_permissions(self) -> None:
        try:
            from android.permissions import Permission, request_permissions
        except ImportError:
            return

        Clock.schedule_once(
            lambda dt: request_permissions([Permission.CAMERA]),
            0,
        )
