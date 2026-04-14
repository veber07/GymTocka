from __future__ import annotations

from functools import partial
from pathlib import Path
import time
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.utils import platform

from fitspin.slot_machine import SlotMachineEngine

if TYPE_CHECKING:
    from fitspin.preview import SquatPreview


ASSET_DIR = Path(__file__).resolve().parent / "assets"


def _asset_path(filename: str) -> str:
    path = ASSET_DIR / filename
    return str(path) if path.exists() else ""


EXERCISE_CATALOG = (
    {
        "key": "squat",
        "label": "Squat",
        "title": "SQUAT MODE",
        "subtitle": "Leg power and depth",
    },
    {
        "key": "pullup",
        "label": "Pull-up",
        "title": "PULL-UP MODE",
        "subtitle": "Bar strength and control",
    },
    {
        "key": "pushup",
        "label": "Push-up",
        "title": "PUSH-UP MODE",
        "subtitle": "Plank tension and press",
    },
    {
        "key": "peckdeck",
        "label": "Peck Deck",
        "title": "PECK DECK MODE",
        "subtitle": "Chest squeeze and control",
    },
)
EXERCISE_LOOKUP = {item["key"]: item for item in EXERCISE_CATALOG}

SLOT_SYMBOL_SOURCES = {
    "bell": _asset_path("symbol_bell.png"),
    "seven": _asset_path("symbol_seven.png"),
    "cherry": _asset_path("symbol_cherry.png"),
    "grapes": _asset_path("symbol_grapes.png"),
    "lemon": _asset_path("symbol_lemon.png"),
    "orange": _asset_path("symbol_orange.png"),
    "plum": _asset_path("symbol_plum.png"),
    "watermelon": _asset_path("symbol_watermelon.png"),
}
SLOT_BACKGROUND_SOURCE = _asset_path("slot_machine_bg.png")


KV = """
#:import dp kivy.metrics.dp
#:set THEME_RED (0.82, 0.12, 0.16, 1)
#:set THEME_RED_DEEP (0.60, 0.07, 0.10, 1)
#:set THEME_RED_SOFT (0.96, 0.84, 0.86, 1)
#:set THEME_WHITE (0.99, 0.99, 1.00, 0.94)
#:set THEME_TEXT (0.14, 0.09, 0.10, 1)
#:set THEME_TEXT_MUTED (0.42, 0.20, 0.22, 1)

<OverlayCard@BoxLayout>:
    orientation: "vertical"
    padding: "14dp"
    spacing: "8dp"
    size_hint: None, None
    canvas.before:
        Color:
            rgba: THEME_WHITE
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [22, 22, 22, 22]
        Color:
            rgba: 1, 1, 1, 0.9
        RoundedRectangle:
            pos: self.x + dp(2), self.top - self.height * 0.24
            size: self.width - dp(4), self.height * 0.24
            radius: [20, 20, 10, 10]
        Color:
            rgba: THEME_RED
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 22, 22, 22, 22)
            width: 1.3
        Color:
            rgba: 0.64, 0.08, 0.11, 0.14
        RoundedRectangle:
            pos: self.x + dp(6), self.y - dp(3)
            size: self.width - dp(12), self.height
            radius: [20, 20, 20, 20]

<AppButton@Button>:
    background_normal: ""
    background_down: ""
    border: 0, 0, 0, 0
    bold: True
    font_size: "15sp"
    color: 1, 1, 1, 1
    canvas.before:
        Color:
            rgba: self.background_color if self.state == "normal" else (self.background_color[0] * 0.88, self.background_color[1] * 0.88, self.background_color[2] * 0.88, self.background_color[3])
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [16, 16, 16, 16]
    canvas.after:
        Color:
            rgba: THEME_RED_DEEP[0], THEME_RED_DEEP[1], THEME_RED_DEEP[2], 0.16
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 16, 16, 16, 16)
            width: 1

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
                color: THEME_RED_DEEP
                font_size: "18sp"
                halign: "left"
                text_size: self.size
            Label:
                text: "Reps: " + str(app.rep_count)
                color: THEME_TEXT
                halign: "left"
                text_size: self.size
            Label:
                text: "Phase: " + app.phase_label
                color: THEME_RED
                halign: "left"
                text_size: self.size
            Label:
                text: app.debug_metric
                color: THEME_TEXT_MUTED
                font_size: "12sp"
                halign: "left"
                text_size: self.size
            Label:
                text: app.calibration_text
                color: (0.16, 0.60, 0.26, 1) if app.calibration_ready else THEME_RED
                font_size: "12sp"
                halign: "left"
                text_size: self.size
            Label:
                text: app.framing_text
                color: THEME_TEXT_MUTED
                font_size: "12sp"
                halign: "left"
                text_size: self.size
            Label:
                text: app.transport_text
                color: THEME_TEXT_MUTED
                font_size: "12sp"
                halign: "left"
                text_size: self.size
            Label:
                text: "Set: " + ("LIVE " + app.set_duration_text if app.calibration_ready else "CAL " + app.set_duration_text if app.set_active else "idle")
                color: (0.16, 0.60, 0.26, 1) if app.set_active else THEME_TEXT_MUTED
                font_size: "12sp"
                halign: "left"
                text_size: self.size

        OverlayCard:
            size: min(root.width * 0.56, dp(336)), "244dp"
            pos_hint: {"right": 0.97, "top": 0.97}
            FloatLayout:
                Image:
                    source: app.slot_background_source
                    fit_mode: "fill"
                    opacity: 0.34 + app.slot_glow * 0.1
                Label:
                    text: "REP SLOT"
                    pos_hint: {"x": 0.08, "top": 0.96}
                    size_hint: 0.52, None
                    height: "28dp"
                    color: THEME_RED_DEEP
                    bold: True
                    font_size: "17sp"
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                Label:
                    text: app.slot_hint_text
                    pos_hint: {"x": 0.08, "top": 0.84}
                    size_hint: 0.72, None
                    height: "20dp"
                    color: THEME_TEXT_MUTED
                    font_size: "11sp"
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                BoxLayout:
                    size_hint: 0.68, None
                    height: "86dp"
                    pos_hint: {"center_x": 0.49, "top": 0.74}
                    spacing: "10dp"
                    FloatLayout:
                        canvas.before:
                            Color:
                                rgba: THEME_RED_SOFT[0], THEME_RED_SOFT[1], THEME_RED_SOFT[2], 0.42 + app.slot_glow * 0.08
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [12, 12, 12, 12]
                        Image:
                            source: app.slot_image_sources[0]
                            size_hint: 0.82, 0.82
                            pos_hint: {"center_x": 0.5, "center_y": 0.5}
                            fit_mode: "contain"
                            opacity: 1 if app.slot_image_sources[0] else 0
                    FloatLayout:
                        canvas.before:
                            Color:
                                rgba: THEME_RED_SOFT[0], THEME_RED_SOFT[1], THEME_RED_SOFT[2], 0.42 + app.slot_glow * 0.08
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [12, 12, 12, 12]
                        Image:
                            source: app.slot_image_sources[1]
                            size_hint: 0.82, 0.82
                            pos_hint: {"center_x": 0.5, "center_y": 0.5}
                            fit_mode: "contain"
                            opacity: 1 if app.slot_image_sources[1] else 0
                    FloatLayout:
                        canvas.before:
                            Color:
                                rgba: THEME_RED_SOFT[0], THEME_RED_SOFT[1], THEME_RED_SOFT[2], 0.42 + app.slot_glow * 0.08
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [12, 12, 12, 12]
                        Image:
                            source: app.slot_image_sources[2]
                            size_hint: 0.82, 0.82
                            pos_hint: {"center_x": 0.5, "center_y": 0.5}
                            fit_mode: "contain"
                            opacity: 1 if app.slot_image_sources[2] else 0
                Label:
                    text: app.slot_reward_text
                    pos_hint: {"x": 0.08, "top": 0.42}
                    size_hint: 0.55, None
                    height: "24dp"
                    color: THEME_RED
                    bold: True
                    font_size: "15sp"
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                Label:
                    text: app.slot_combo_text
                    pos_hint: {"x": 0.08, "top": 0.32}
                    size_hint: 0.74, None
                    height: "28dp"
                    color: THEME_TEXT
                    font_size: "13sp"
                    halign: "left"
                    valign: "middle"
                    text_size: self.size
                BoxLayout:
                    size_hint: 0.72, None
                    height: "34dp"
                    pos_hint: {"x": 0.08, "y": 0.08}
                    spacing: "8dp"
                    Widget:
                        size_hint_x: None
                        width: "28dp"
                        canvas.before:
                            Color:
                                rgba: THEME_RED[0], THEME_RED[1] + app.coin_flash * 0.05, THEME_RED[2] + app.coin_flash * 0.03, 1
                            Ellipse:
                                pos: self.x, self.center_y - dp(13)
                                size: dp(26), dp(26)
                            Color:
                                rgba: 1, 1, 1, 0.38
                            Line:
                                ellipse: (self.x + dp(2), self.center_y - dp(11), dp(22), dp(22))
                    Label:
                        text: "Coins"
                        color: THEME_RED_DEEP
                        font_size: "16sp"
                        bold: True
                        halign: "left"
                        valign: "middle"
                        text_size: self.size
                    Label:
                        text: str(app.coin_score)
                        color: THEME_RED
                        font_size: "18sp"
                        bold: True
                        halign: "right"
                        valign: "middle"
                        text_size: self.size
                Label:
                    text: app.slot_queue_text
                    pos_hint: {"right": 0.9, "y": 0.08}
                    size_hint: 0.25, None
                    height: "20dp"
                    color: THEME_TEXT_MUTED
                    font_size: "11sp"
                    halign: "right"
                    valign: "middle"
                    text_size: self.size

        OverlayCard:
            size_hint: None, None
            width: min(root.width * 0.92, dp(446))
            height: "452dp"
            pos_hint: {"center_x": 0.5, "y": 0.03}
            Label:
                text: "Backend URL"
                bold: True
                color: THEME_RED_DEEP
                font_size: "18sp"
                halign: "left"
                text_size: self.size
            Label:
                text: "Exercise"
                bold: True
                color: THEME_RED_DEEP
                font_size: "17sp"
                halign: "left"
                text_size: self.size
            Label:
                text: "Current: " + app.exercise_display + " | tap to switch modes"
                color: THEME_TEXT_MUTED
                font_size: "12sp"
                halign: "left"
                text_size: self.size
            AppButton:
                text: "Choose Exercise"
                size_hint_y: None
                height: "48dp"
                background_color: THEME_RED
                on_release: app.open_exercise_picker()
            Label:
                text: "Camera"
                bold: True
                color: THEME_RED_DEEP
                font_size: "17sp"
                halign: "left"
                text_size: self.size
            Label:
                text: "Current: " + app.camera_facing_label
                color: THEME_TEXT_MUTED
                font_size: "12sp"
                halign: "left"
                text_size: self.size
            AppButton:
                text: "Use Selfie Camera" if app.camera_facing == "rear" else "Use Rear Camera"
                size_hint_y: None
                height: "48dp"
                background_color: THEME_RED_DEEP
                on_release: app.toggle_camera_facing()
            TextInput:
                id: backend_input
                text: app.backend_url
                multiline: False
                size_hint_y: None
                height: "42dp"
                foreground_color: THEME_TEXT
                background_color: 1, 1, 1, 0.98
                cursor_color: THEME_RED
                padding: ["10dp", "10dp", "10dp", "10dp"]
                on_text_validate: app.update_backend_url(self.text)
            BoxLayout:
                size_hint_y: None
                height: "48dp"
                spacing: "10dp"
                AppButton:
                    text: "Save URL"
                    background_color: THEME_RED
                    on_release: app.update_backend_url(backend_input.text)
                AppButton:
                    text: "Start Camera" if not app.camera_running else "Stop Camera"
                    background_color: THEME_RED if not app.camera_running else THEME_RED_DEEP
                    on_release: app.toggle_camera()
            BoxLayout:
                size_hint_y: None
                height: "48dp"
                spacing: "10dp"
                AppButton:
                    text: "End Set" if app.set_active else "Start Set"
                    background_color: THEME_RED if not app.set_active else THEME_RED_DEEP
                    on_release: app.toggle_set()
                AppButton:
                    text: "Reset Counters"
                    background_color: 1, 1, 1, 1
                    color: THEME_RED_DEEP
                    on_release: app.reset_session()
            Label:
                text: app.current_set_summary
                color: THEME_TEXT
                font_size: "12sp"
                halign: "left"
                text_size: self.width, None
                size_hint_y: None
                height: self.texture_size[1] + dp(4)
            Label:
                text: app.last_set_summary
                color: THEME_TEXT_MUTED
                font_size: "12sp"
                halign: "left"
                text_size: self.width, None
                size_hint_y: None
                height: self.texture_size[1] + dp(4)
            Label:
                text: app.status_text
                color: THEME_TEXT
                font_size: "12sp"
                halign: "left"
                valign: "top"
                text_size: self.width, None
                size_hint_y: None
                height: self.texture_size[1] + dp(6)
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
    debug_metric = StringProperty("metric: --")
    calibration_text = StringProperty("Calibration: pending")
    framing_text = StringProperty("Framing: align your whole body in the guide.")
    transport_text = StringProperty("Transport: connecting...")
    status_text = StringProperty("Choose an exercise, set the backend URL, then start the camera.")
    backend_url = StringProperty("http://192.168.0.10:8000")
    camera_facing = StringProperty("rear")
    camera_facing_label = StringProperty("Rear camera")
    slot_symbols = ListProperty(["cherry", "lemon", "orange"])
    slot_image_sources = ListProperty(["", "", ""])
    slot_reward_text = StringProperty("Warm-up spin")
    slot_combo_text = StringProperty("Every rep kicks the reels")
    slot_hint_text = StringProperty("Fruit combo deck")
    slot_queue_text = StringProperty("")
    slot_glow = NumericProperty(0.18)
    coin_flash = NumericProperty(0.08)
    slot_status = StringProperty("1 rep = 1 spin")
    camera_running = BooleanProperty(False)
    set_active = BooleanProperty(False)
    calibration_ready = BooleanProperty(False)
    slot_background_source = StringProperty(SLOT_BACKGROUND_SOURCE)
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
        self._exercise_popup: Popup | None = None
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
            self._sync_slot_machine_ui()
            Clock.schedule_interval(self._tick_slot_machine, 1 / 18)
            return root
        except Exception as exc:
            self._write_runtime_error(exc)
            return self._build_fallback_ui(exc)

    def on_start(self):
        self.status_text = "Choose an exercise, set the backend URL, then start the camera."
        self._warn_if_android_loopback()

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
        if self._is_android_loopback_url(clean):
            self.transport_text = "Transport: unreachable (127.0.0.1 points to the phone)"
            self.status_text = "Use your computer LAN IP on Android, for example http://192.168.x.x:8000."
        else:
            self.transport_text = "Transport: reconnecting..."
            self.status_text = f"Backend saved: {self.backend_url}"
        if self._preview:
            self._preview.close_stream()

    def select_exercise(self, exercise: str) -> None:
        normalized = exercise if exercise in EXERCISE_LOOKUP else "squat"
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
        self.debug_metric = "metric: --"
        self.calibration_ready = False
        self.calibration_text = "Calibration: pending"
        self.framing_text = f"Framing: {self._default_framing_hint()}"
        self.transport_text = "Transport: connecting..."
        self.current_set_summary = "Current set: inactive"
        self.last_set_summary = f"Last set: no completed {self.exercise_display.lower()} set yet"
        self._last_rep_count = 0
        self._slot_machine.reset()
        self._sync_slot_machine_ui()
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
        self._preview.connect_camera_facing(self.camera_facing)
        self.camera_running = True
        self.status_text = self._camera_started_text()

    def toggle_camera_facing(self) -> None:
        next_facing = "front" if self.camera_facing == "rear" else "rear"
        self._set_camera_facing(next_facing)

        if self.camera_running and self._preview:
            if self.set_active:
                self._finalize_set("Camera switched. Set saved.")
            self._preview.disconnect_rear_camera()
            self._request_android_permissions()
            self._preview.connect_camera_facing(self.camera_facing)
            self.camera_running = True
            self.status_text = f"Switched to {self.camera_facing_label.lower()}. {self._camera_started_text()}"
            return

        self.status_text = f"Camera mode set to {self.camera_facing_label}."

    def reset_session(self) -> None:
        if not self._preview:
            return
        self.set_active = False
        self.calibration_ready = False
        self._set_started_at = None
        self.set_duration_text = "00:00"
        self.current_set_summary = "Current set: inactive"
        self.calibration_text = "Calibration: pending"
        self.framing_text = f"Framing: {self._default_framing_hint()}"
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
        self.framing_text = f"Framing: {self._default_framing_hint()}"
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
                    else str(framing_feedback or f"Please {self._default_framing_hint()}")
                )
            return

        self.calibration_ready = bool(result.get("calibrated", False))
        calibration_progress = int(result.get("calibration_progress", 0))
        calibration_required = int(result.get("calibration_required", 0))
        top_angle = result.get("top_angle")
        metric_label_text = str(result.get("metric_label", "metric")).strip()
        metric_label = metric_label_text.lower()

        if self.calibration_ready:
            self.phase_label = result.get("phase", "up")
            if isinstance(top_angle, (int, float)) and "angle" in metric_label:
                self.calibration_text = f"Calibration: ready ({top_angle:.0f} deg)"
            else:
                self.calibration_text = "Calibration: ready"
        else:
            self.phase_label = "calibrating"
            self.calibration_text = f"Calibration: {calibration_progress}/{calibration_required}"

        self.rep_count = int(result.get("rep_count", 0))

        angle = result.get("primary_angle", result.get("squat_angle"))
        self.debug_metric = f"{metric_label}: {angle:.1f}" if isinstance(angle, (int, float)) else f"{metric_label}: --"

        status = result.get("status") or "Tracking..."
        self.status_text = status

        if self.rep_count > self._last_rep_count or result.get("rep_completed"):
            self._slot_machine.trigger_spin()
        self._last_rep_count = self.rep_count

    def _handle_pose_error(self, message: str) -> None:
        if self._is_android_loopback_url(self.backend_url):
            self.transport_text = "Transport: unreachable (127.0.0.1 points to the phone)"
            self.status_text = "Backend unreachable on Android. Use your computer LAN IP instead of 127.0.0.1."
            return
        self.transport_text = "Transport: disconnected"
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
        self.debug_metric = "metric: --"
        self.calibration_ready = bool(result.get("calibrated", False))
        self.calibration_text = "Calibration: pending"
        self.framing_text = f"Framing: {self._default_framing_hint()}"
        self._last_rep_count = self.rep_count
        self.current_set_summary = "Current set: inactive"
        self._sync_slot_machine_ui()
        self.status_text = result.get("status", "Session reset.")

    def _handle_start_set_result(self, result: dict) -> None:
        self._slot_machine.reset()
        self.rep_count = int(result.get("rep_count", 0))
        self.phase_label = "calibrating"
        self.debug_metric = "metric: --"
        self.calibration_ready = False
        calibration_required = int(result.get("calibration_required", 0))
        self.calibration_text = f"Calibration: 0/{calibration_required}" if calibration_required else "Calibration: pending"
        self.framing_text = f"Framing: {self._default_framing_hint()}"
        self._last_rep_count = self.rep_count
        self.set_active = True
        self._set_started_at = time.monotonic()
        self.set_duration_text = "00:00"
        self.current_set_summary = f"Current set: {self.exercise_display.lower()} | calibrating | 0 reps | 0 coins | 00:00"
        self._sync_slot_machine_ui()
        self.status_text = result.get("status", f"Set started. Hold the {self.exercise_display.lower()} start position for calibration.")

    def _sync_slot_machine_ui(self) -> None:
        state = self._slot_machine.state
        self.slot_symbols = list(state.reels)
        self.slot_image_sources = [SLOT_SYMBOL_SOURCES.get(symbol, "") for symbol in state.reels]
        self.coin_score = state.score
        self.slot_glow = 0.18 + state.spin_mix * 0.38 + state.celebration * 0.4
        self.coin_flash = 0.1 + state.celebration * 0.62

        if state.spinning:
            self.slot_reward_text = "Spinning live"
            self.slot_combo_text = "Reels locking one by one"
            self.slot_hint_text = "Arcade payout chain"
        else:
            self.slot_reward_text = f"+{state.last_reward} coins" if state.last_reward else "Warm-up spin"
            self.slot_combo_text = state.last_combo if state.last_combo else "Every rep kicks the reels"
            self.slot_hint_text = "Fruit combo deck"

        if state.spinning and state.pending_spins:
            self.slot_queue_text = f"x{state.pending_spins + 1}"
        elif state.pending_spins:
            self.slot_queue_text = f"x{state.pending_spins}"
        else:
            self.slot_queue_text = ""

        self.slot_status = (
            "Spinning..."
            if state.spinning
            else (
                f"+{state.last_reward} coins | {state.last_combo}"
                if state.last_reward
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
        self.framing_text = f"Framing: {self._default_framing_hint()}"
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
            self.exercise_key = stored if stored in EXERCISE_LOOKUP else "squat"
        if self._settings is not None and self._settings.exists("camera"):
            stored_facing = self._settings.get("camera").get("facing", self.camera_facing)
            self._set_camera_facing(stored_facing, persist=False)
        else:
            self._set_camera_facing(self.camera_facing, persist=False)

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
        config = EXERCISE_LOOKUP.get(self.exercise_key, EXERCISE_LOOKUP["squat"])
        self.exercise_key = config["key"]
        self.exercise_display = config["label"]
        self.exercise_title = config["title"]
        self.framing_text = f"Framing: {self._default_framing_hint()}"
        if not self._slot_machine.state.spinning and not self._slot_machine.state.last_reward:
            self.slot_reward_text = "Warm-up spin"
            self.slot_combo_text = "Every rep kicks the reels"
            self.slot_hint_text = "Fruit combo deck"
            self.slot_status = f"1 {self.exercise_display.lower()} = 1 spin"

    def open_exercise_picker(self) -> None:
        if self._exercise_popup is not None:
            return

        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
        content.add_widget(
            Label(
                text="Choose a workout mode",
                color=(0.60, 0.07, 0.10, 1),
                bold=True,
                font_size="18sp",
                size_hint_y=None,
                height=dp(28),
            )
        )

        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=(0, 0, 0, dp(4)))
        grid.bind(minimum_height=grid.setter("height"))

        popup = Popup(
            title="Exercise Picker",
            separator_height=0,
            size_hint=(0.9, None),
            height=dp(430),
            auto_dismiss=True,
        )

        for option in EXERCISE_CATALOG:
            selected = option["key"] == self.exercise_key
            button = Button(
                text=f"[b]{option['label']}[/b]\\n[size=12sp]{option['subtitle']}[/size]",
                markup=True,
                size_hint_y=None,
                height=dp(72),
                background_normal="",
                background_down="",
                border=(0, 0, 0, 0),
                bold=True,
                font_size="15sp",
                halign="center",
                valign="middle",
                color=(0.60, 0.07, 0.10, 1) if selected else (1, 1, 1, 1),
                background_color=(1, 1, 1, 1) if selected else (0.82, 0.12, 0.16, 1),
            )
            button.bind(size=self._resize_markup_button)
            button.bind(on_release=partial(self._select_exercise_from_popup, popup, option["key"]))
            grid.add_widget(button)

        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(grid)
        content.add_widget(scroll)

        close_button = Button(
            text="Close",
            size_hint_y=None,
            height=dp(46),
            background_normal="",
            background_down="",
            border=(0, 0, 0, 0),
            bold=True,
            color=(1, 1, 1, 1),
            background_color=(0.60, 0.07, 0.10, 1),
        )
        close_button.bind(on_release=lambda *_args: popup.dismiss())
        content.add_widget(close_button)

        popup.content = content
        self._exercise_popup = popup
        popup.bind(on_dismiss=self._on_exercise_popup_dismiss)
        popup.open()

    @staticmethod
    def _resize_markup_button(button: Button, _size) -> None:
        button.text_size = (button.width - dp(18), button.height - dp(12))

    def _select_exercise_from_popup(self, popup: Popup, exercise: str, *_args) -> None:
        popup.dismiss()
        self.select_exercise(exercise)

    def _on_exercise_popup_dismiss(self, *_args) -> None:
        self._exercise_popup = None

    def _camera_started_text(self) -> str:
        camera_phrase = "selfie camera" if self.camera_facing == "front" else "rear camera"
        if self.exercise_key == "pullup":
            return f"{camera_phrase.capitalize()} started. Step under the bar, show your full body and both hands, then tap Start Set."
        if self.exercise_key == "pushup":
            return f"{camera_phrase.capitalize()} started. Place the phone side-on so head, hips, hands, and heels stay visible, then tap Start Set."
        if self.exercise_key == "peckdeck":
            return f"{camera_phrase.capitalize()} started. Sit facing the phone and keep shoulders, elbows, and hands visible, then tap Start Set."
        return f"{camera_phrase.capitalize()} started. Place the phone so your full body is visible, then tap Start Set."

    def _default_framing_hint(self) -> str:
        if self.exercise_key == "pullup":
            return "align your whole body and both hands in the guide."
        if self.exercise_key == "pushup":
            return "align your side profile from head to heels in the guide."
        if self.exercise_key == "peckdeck":
            return "align your upper body, elbows, and both hands in the guide."
        return "align your whole body in the guide."

    def _set_camera_facing(self, facing: str, persist: bool = True) -> None:
        normalized = "front" if str(facing).strip().lower() in {"front", "selfie"} else "rear"
        self.camera_facing = normalized
        self.camera_facing_label = "Selfie camera" if normalized == "front" else "Rear camera"
        if persist and self._settings is not None:
            self._settings.put("camera", facing=self.camera_facing)

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

    def _warn_if_android_loopback(self) -> None:
        if self._is_android_loopback_url(self.backend_url):
            self.transport_text = "Transport: unreachable (127.0.0.1 points to the phone)"
            self.status_text = "Use your computer LAN IP on Android, not localhost or 127.0.0.1."

    @staticmethod
    def _is_android_loopback_url(url: str) -> bool:
        if platform != "android":
            return False
        hostname = (urlparse(url).hostname or "").strip().lower()
        return hostname in {"127.0.0.1", "localhost", "::1"}
