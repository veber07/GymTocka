from __future__ import annotations

import base64
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np


NOSE = 0
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28

MODEL_PATH = Path(__file__).resolve().parent / "models" / "pose_landmarker_full.task"


def angle_degrees(a, b, c) -> Optional[float]:
    visibility = [getattr(a, "visibility", 1.0), getattr(b, "visibility", 1.0), getattr(c, "visibility", 1.0)]
    if min(visibility) < 0.35:
        return None

    ab = np.array([a.x - b.x, a.y - b.y], dtype=np.float32)
    cb = np.array([c.x - b.x, c.y - b.y], dtype=np.float32)
    ab_norm = np.linalg.norm(ab)
    cb_norm = np.linalg.norm(cb)
    if ab_norm == 0 or cb_norm == 0:
        return None

    cosine = float(np.dot(ab, cb) / (ab_norm * cb_norm))
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def average(values: list[Optional[float]]) -> Optional[float]:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return sum(filtered) / len(filtered)


def decode_image(image_b64: str) -> np.ndarray:
    raw = base64.b64decode(image_b64)
    encoded = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Image could not be decoded.")
    return image


def landmark_visible(landmark, threshold: float = 0.45) -> bool:
    return getattr(landmark, "visibility", 1.0) >= threshold


def framing_feedback(landmarks) -> dict[str, object]:
    required_points = [
        NOSE,
        LEFT_SHOULDER,
        RIGHT_SHOULDER,
        LEFT_HIP,
        RIGHT_HIP,
        LEFT_ANKLE,
        RIGHT_ANKLE,
    ]
    visible_points = [landmarks[index] for index in required_points if landmark_visible(landmarks[index])]
    if len(visible_points) < 6:
        return {
            "framing_ok": False,
            "framing_feedback": "Show your full body: head, hips, and feet must stay visible.",
        }

    xs = [point.x for point in visible_points]
    ys = [point.y for point in visible_points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    body_height = max_y - min_y
    center_x = (min_x + max_x) / 2
    top_margin = min_y
    bottom_margin = 1.0 - max_y

    if top_margin < 0.03 or bottom_margin < 0.04 or body_height > 0.9:
        return {
            "framing_ok": False,
            "framing_feedback": "Move farther back so your whole body fits comfortably in frame.",
        }
    if body_height < 0.55:
        return {
            "framing_ok": False,
            "framing_feedback": "Move a bit closer so your body fills more of the frame.",
        }
    if center_x < 0.38:
        return {
            "framing_ok": False,
            "framing_feedback": "Move a little to the right to center yourself.",
        }
    if center_x > 0.62:
        return {
            "framing_ok": False,
            "framing_feedback": "Move a little to the left to center yourself.",
        }
    return {
        "framing_ok": True,
        "framing_feedback": "Framing looks good.",
    }


@dataclass
class SquatCounterState:
    reps: int = 0
    phase: str = "up"
    last_angle: Optional[float] = None
    smoothed_angles: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    calibration_samples: deque[float] = field(default_factory=lambda: deque(maxlen=12))
    calibrated: bool = False
    top_angle: Optional[float] = None
    down_threshold: float = 105.0
    up_threshold: float = 155.0
    last_seen_at: float = field(default_factory=time.monotonic)


class SquatCounter:
    CALIBRATION_FRAMES_REQUIRED = 12
    STANDING_ANGLE_THRESHOLD = 145.0

    def __init__(self) -> None:
        self.state = SquatCounterState()

    def reset(self) -> None:
        self.state = SquatCounterState()

    def update(self, landmarks) -> dict:
        left_knee = angle_degrees(
            landmarks[LEFT_HIP],
            landmarks[LEFT_KNEE],
            landmarks[LEFT_ANKLE],
        )
        right_knee = angle_degrees(
            landmarks[RIGHT_HIP],
            landmarks[RIGHT_KNEE],
            landmarks[RIGHT_ANKLE],
        )
        knee_angle = average([left_knee, right_knee])
        if knee_angle is None:
            return self._result(
                rep_completed=False,
                status="Move back so hips, knees, and ankles are visible.",
            )

        self.state.smoothed_angles.append(knee_angle)
        smooth_angle = sum(self.state.smoothed_angles) / len(self.state.smoothed_angles)
        self.state.last_angle = smooth_angle
        self.state.last_seen_at = time.monotonic()

        if not self.state.calibrated:
            return self._calibrate(smooth_angle)

        rep_completed = False
        if self.state.phase == "up" and smooth_angle <= self.state.down_threshold:
            self.state.phase = "down"
        elif self.state.phase == "down" and smooth_angle >= self.state.up_threshold:
            self.state.phase = "up"
            self.state.reps += 1
            rep_completed = True

        if smooth_angle > self.state.up_threshold + 8:
            status = "Ready. Start squatting."
        elif self.state.phase == "down":
            status = "Drive up."
        else:
            status = "Lower into the squat."
        return self._result(rep_completed=rep_completed, status=status)

    def _calibrate(self, smooth_angle: float) -> dict:
        if smooth_angle >= self.STANDING_ANGLE_THRESHOLD:
            self.state.calibration_samples.append(smooth_angle)
        elif self.state.calibration_samples:
            self.state.calibration_samples.clear()
            return self._result(
                rep_completed=False,
                status="Stand tall and hold still to calibrate.",
            )

        collected = len(self.state.calibration_samples)
        if collected >= self.CALIBRATION_FRAMES_REQUIRED:
            self.state.top_angle = sum(self.state.calibration_samples) / collected
            self.state.down_threshold = max(95.0, self.state.top_angle - 60.0)
            self.state.up_threshold = max(self.state.down_threshold + 18.0, self.state.top_angle - 15.0)
            self.state.calibrated = True
            self.state.phase = "up"
            self.state.calibration_samples.clear()
            return self._result(
                rep_completed=False,
                status="Calibrated. Start squatting.",
            )

        return self._result(
            rep_completed=False,
            status=f"Calibration {collected}/{self.CALIBRATION_FRAMES_REQUIRED}: stand upright and stay still.",
        )

    def _result(self, rep_completed: bool, status: str) -> dict:
        return {
            "rep_completed": rep_completed,
            "status": status,
            "calibrated": self.state.calibrated,
            "calibration_progress": len(self.state.calibration_samples),
            "calibration_required": self.CALIBRATION_FRAMES_REQUIRED,
            "top_angle": self.state.top_angle,
            "down_threshold": self.state.down_threshold,
            "up_threshold": self.state.up_threshold,
        }


class PoseService:
    def __init__(self) -> None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Missing pose model at {MODEL_PATH}. Download pose_landmarker_full.task first."
            )

        base_options = mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH))
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)
        self._lock = threading.Lock()
        self._sessions: dict[str, SquatCounter] = {}

    def analyze_squat(self, session_id: str, image_b64: str) -> dict:
        image = decode_image(image_b64)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        timestamp_ms = int(time.monotonic() * 1000)

        with self._lock:
            result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        session = self._sessions.setdefault(session_id, SquatCounter())

        if not result.pose_landmarks:
            return {
                "session_id": session_id,
                "rep_count": session.state.reps,
                "rep_completed": False,
                "phase": session.state.phase,
                "squat_angle": session.state.last_angle,
                "landmarks": [],
                "calibrated": session.state.calibrated,
                "calibration_progress": len(session.state.calibration_samples),
                "calibration_required": session.CALIBRATION_FRAMES_REQUIRED,
                "top_angle": session.state.top_angle,
                "down_threshold": session.state.down_threshold,
                "up_threshold": session.state.up_threshold,
                "framing_ok": False,
                "framing_feedback": "No pose detected. Step back and frame your whole body.",
                "status": "No pose detected. Frame the whole body.",
            }

        landmarks = result.pose_landmarks[0]
        update_result = session.update(landmarks)
        framing_result = framing_feedback(landmarks)

        return {
            "session_id": session_id,
            "rep_count": session.state.reps,
            "rep_completed": update_result["rep_completed"],
            "phase": session.state.phase,
            "squat_angle": session.state.last_angle,
            "landmarks": [
                {
                    "x": landmark.x,
                    "y": landmark.y,
                    "visibility": getattr(landmark, "visibility", 1.0),
                }
                for landmark in landmarks
            ],
            "calibrated": update_result["calibrated"],
            "calibration_progress": update_result["calibration_progress"],
            "calibration_required": update_result["calibration_required"],
            "top_angle": update_result["top_angle"],
            "down_threshold": update_result["down_threshold"],
            "up_threshold": update_result["up_threshold"],
            "framing_ok": framing_result["framing_ok"],
            "framing_feedback": framing_result["framing_feedback"],
            "status": update_result["status"],
        }

    def reset_session(self, session_id: str) -> dict:
        session = self._sessions.setdefault(session_id, SquatCounter())
        session.reset()
        return {
            "session_id": session_id,
            "rep_count": 0,
            "rep_completed": False,
            "phase": session.state.phase,
            "squat_angle": session.state.last_angle,
            "landmarks": [],
            "calibrated": session.state.calibrated,
            "calibration_progress": len(session.state.calibration_samples),
            "calibration_required": session.CALIBRATION_FRAMES_REQUIRED,
            "top_angle": session.state.top_angle,
            "down_threshold": session.state.down_threshold,
            "up_threshold": session.state.up_threshold,
            "framing_ok": False,
            "framing_feedback": "Frame your whole body before starting.",
            "status": "Squat session reset.",
        }
