from __future__ import annotations

import base64
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol

import cv2
import mediapipe as mp
import numpy as np


NOSE = 0
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28

MODEL_PATH = Path(__file__).resolve().parent / "models" / "pose_landmarker_full.task"

SUPPORTED_EXERCISES = ("squat", "pullup", "pushup", "peckdeck")


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


def average_landmark_y(landmarks, indices: list[int], visibility_threshold: float = 0.45) -> Optional[float]:
    values = [
        landmarks[index].y
        for index in indices
        if getattr(landmarks[index], "visibility", 1.0) >= visibility_threshold
    ]
    if not values:
        return None
    return sum(values) / len(values)


def decode_image(image_b64: str) -> np.ndarray:
    raw = base64.b64decode(image_b64)
    encoded = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Image could not be decoded.")
    return image


def landmark_visible(landmark, threshold: float = 0.45) -> bool:
    return getattr(landmark, "visibility", 1.0) >= threshold


def normalize_exercise(exercise: str | None) -> str:
    candidate = (exercise or "squat").strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    aliases = {
        "squat": {"squat", "squats"},
        "pullup": {"pullup", "pullups"},
        "pushup": {"pushup", "pushups", "klik", "kliky", "pushupy"},
        "peckdeck": {"peckdeck", "peckdecks", "pecdeck", "pecdecks", "butterfly"},
    }
    for normalized, names in aliases.items():
        if candidate in names:
            return normalized
    return "squat"


def exercise_display_name(exercise: str) -> str:
    if exercise == "peckdeck":
        return "Peck Deck"
    if exercise == "pushup":
        return "Push-up"
    if exercise == "pullup":
        return "Pull-up"
    return "Squat"


def initial_framing_feedback(exercise: str) -> str:
    if exercise == "pullup":
        return "Frame your full body and both hands before starting."
    if exercise == "pushup":
        return "Frame your side profile from head to heels before starting."
    if exercise == "peckdeck":
        return "Frame your upper body, elbows, and both hands before starting."
    return "Frame your whole body before starting."


def framing_feedback(landmarks, exercise: str) -> dict[str, object]:
    if exercise == "pullup":
        required_points = [
            NOSE,
            LEFT_SHOULDER,
            RIGHT_SHOULDER,
            LEFT_ELBOW,
            RIGHT_ELBOW,
            LEFT_WRIST,
            RIGHT_WRIST,
            LEFT_HIP,
            RIGHT_HIP,
            LEFT_ANKLE,
            RIGHT_ANKLE,
        ]
        visible_points = [landmarks[index] for index in required_points if landmark_visible(landmarks[index])]
        if len(visible_points) < 9:
            return {
                "framing_ok": False,
                "framing_feedback": "Show your full body and both hands clearly before starting pull-ups.",
            }
    elif exercise == "pushup":
        required_points = [
            NOSE,
            LEFT_SHOULDER,
            RIGHT_SHOULDER,
            LEFT_ELBOW,
            RIGHT_ELBOW,
            LEFT_WRIST,
            RIGHT_WRIST,
            LEFT_HIP,
            RIGHT_HIP,
            LEFT_ANKLE,
            RIGHT_ANKLE,
        ]
        visible_points = [landmarks[index] for index in required_points if landmark_visible(landmarks[index])]
        if len(visible_points) < 6:
            return {
                "framing_ok": False,
                "framing_feedback": "Show your side profile from head to heels and keep both hands visible.",
            }
    elif exercise == "peckdeck":
        required_points = [
            NOSE,
            LEFT_SHOULDER,
            RIGHT_SHOULDER,
            LEFT_ELBOW,
            RIGHT_ELBOW,
            LEFT_WRIST,
            RIGHT_WRIST,
        ]
        visible_points = [landmarks[index] for index in required_points if landmark_visible(landmarks[index])]
        if len(visible_points) < 6:
            return {
                "framing_ok": False,
                "framing_feedback": "Sit facing the camera and show your head, elbows, and hands clearly.",
            }
    else:
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
    body_width = max_x - min_x
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    top_margin = min_y
    bottom_margin = 1.0 - max_y

    if exercise == "pushup":
        if min_x < 0.03 or max_x > 0.97 or top_margin < 0.03 or bottom_margin < 0.03 or body_width > 0.94:
            return {
                "framing_ok": False,
                "framing_feedback": "Move farther back so your whole push-up position fits in frame.",
            }
        if max(body_width, body_height) < 0.46:
            return {
                "framing_ok": False,
                "framing_feedback": "Move a bit closer so your full push-up is easier to track.",
            }
        if center_x < 0.34:
            return {
                "framing_ok": False,
                "framing_feedback": "Move a little to the right to center your push-up setup.",
            }
        if center_x > 0.66:
            return {
                "framing_ok": False,
                "framing_feedback": "Move a little to the left to center your push-up setup.",
            }
        if center_y < 0.28:
            return {
                "framing_ok": False,
                "framing_feedback": "Move slightly downward in frame so your full body stays centered.",
            }
        if center_y > 0.72:
            return {
                "framing_ok": False,
                "framing_feedback": "Move slightly upward in frame so your full body stays centered.",
            }
        return {
            "framing_ok": True,
            "framing_feedback": "Push-up framing looks good.",
        }

    if exercise == "peckdeck":
        if top_margin < 0.03 or max_y > 0.88 or body_width > 0.9 or body_height > 0.82:
            return {
                "framing_ok": False,
                "framing_feedback": "Move a bit farther back so your upper body and both hands fit comfortably.",
            }
        if body_width < 0.28 and body_height < 0.24:
            return {
                "framing_ok": False,
                "framing_feedback": "Move a bit closer so your chest and arm motion are easier to track.",
            }
        if center_x < 0.34:
            return {
                "framing_ok": False,
                "framing_feedback": "Move a little to the right to center your upper body.",
            }
        if center_x > 0.66:
            return {
                "framing_ok": False,
                "framing_feedback": "Move a little to the left to center your upper body.",
            }
        if center_y < 0.18:
            return {
                "framing_ok": False,
                "framing_feedback": "Lower the camera slightly so your elbows and hands stay in frame.",
            }
        if center_y > 0.62:
            return {
                "framing_ok": False,
                "framing_feedback": "Raise the camera slightly so your upper body stays centered.",
            }
        return {
            "framing_ok": True,
            "framing_feedback": "Peck deck framing looks good.",
        }

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


class CounterProtocol(Protocol):
    state: object

    def reset(self) -> None: ...

    def update(self, landmarks) -> dict: ...

    def metric_label(self) -> str: ...


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
    CALIBRATION_FRAMES_REQUIRED = 8
    STANDING_ANGLE_THRESHOLD = 140.0

    def __init__(self) -> None:
        self.state = SquatCounterState()

    def metric_label(self) -> str:
        return "Knee angle"

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
            self.state.down_threshold = max(100.0, self.state.top_angle - 52.0)
            self.state.up_threshold = max(self.state.down_threshold + 15.0, self.state.top_angle - 18.0)
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


@dataclass
class PullUpCounterState:
    reps: int = 0
    phase: str = "down"
    last_angle: Optional[float] = None
    smoothed_angles: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    smoothed_gaps: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    calibration_angle_samples: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    calibration_gap_samples: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    calibrated: bool = False
    top_angle: Optional[float] = None
    pull_threshold: float = 102.0
    down_threshold: float = 148.0
    hang_gap: Optional[float] = None
    last_seen_at: float = field(default_factory=time.monotonic)


class PullUpCounter:
    CALIBRATION_FRAMES_REQUIRED = 10
    EXTENDED_ELBOW_THRESHOLD = 150.0
    WRISTS_ABOVE_SHOULDERS_MARGIN = 0.02
    WRISTS_ABOVE_NOSE_MARGIN = 0.01
    MIN_HANG_GAP = 0.12
    TOP_GAP_RATIO = 0.72
    DOWN_GAP_RATIO = 0.9

    def __init__(self) -> None:
        self.state = PullUpCounterState()

    def metric_label(self) -> str:
        return "Elbow angle"

    def reset(self) -> None:
        self.state = PullUpCounterState()

    def update(self, landmarks) -> dict:
        left_elbow = angle_degrees(
            landmarks[LEFT_SHOULDER],
            landmarks[LEFT_ELBOW],
            landmarks[LEFT_WRIST],
        )
        right_elbow = angle_degrees(
            landmarks[RIGHT_SHOULDER],
            landmarks[RIGHT_ELBOW],
            landmarks[RIGHT_WRIST],
        )
        elbow_angle = average([left_elbow, right_elbow])
        if elbow_angle is None:
            return self._result(
                rep_completed=False,
                status="Keep shoulders, elbows, and wrists visible for pull-up tracking.",
            )

        avg_shoulder_y = average_landmark_y(landmarks, [LEFT_SHOULDER, RIGHT_SHOULDER])
        avg_wrist_y = average_landmark_y(landmarks, [LEFT_WRIST, RIGHT_WRIST])
        nose_y = average_landmark_y(landmarks, [NOSE])
        if avg_shoulder_y is None or avg_wrist_y is None or nose_y is None:
            return self._result(
                rep_completed=False,
                status="Show your head, shoulders, and both hands clearly.",
            )

        shoulder_wrist_gap = avg_shoulder_y - avg_wrist_y
        wrists_overhead = (
            avg_wrist_y < avg_shoulder_y - self.WRISTS_ABOVE_SHOULDERS_MARGIN
            and avg_wrist_y < nose_y - self.WRISTS_ABOVE_NOSE_MARGIN
        )

        self.state.smoothed_angles.append(elbow_angle)
        self.state.smoothed_gaps.append(shoulder_wrist_gap)
        smooth_angle = sum(self.state.smoothed_angles) / len(self.state.smoothed_angles)
        smooth_gap = sum(self.state.smoothed_gaps) / len(self.state.smoothed_gaps)
        self.state.last_angle = smooth_angle
        self.state.last_seen_at = time.monotonic()

        if not self.state.calibrated:
            return self._calibrate(smooth_angle, smooth_gap, wrists_overhead)

        hang_gap = self.state.hang_gap or self.MIN_HANG_GAP
        top_detected = smooth_angle <= self.state.pull_threshold and smooth_gap <= hang_gap * self.TOP_GAP_RATIO
        full_extension = (
            wrists_overhead
            and smooth_angle >= self.state.down_threshold
            and smooth_gap >= hang_gap * self.DOWN_GAP_RATIO
        )

        rep_completed = False
        if self.state.phase == "down" and top_detected:
            self.state.phase = "up"
        elif self.state.phase == "up" and full_extension:
            self.state.phase = "down"
            self.state.reps += 1
            rep_completed = True

        if not wrists_overhead:
            status = "Keep both hands above your shoulders and stay under the bar."
        elif self.state.phase == "up":
            status = "Lower with control to full extension."
        elif top_detected:
            status = "Great pull. Lower with control."
        else:
            status = "Pull your chest upward."
        return self._result(rep_completed=rep_completed, status=status)

    def _calibrate(self, smooth_angle: float, smooth_gap: float, wrists_overhead: bool) -> dict:
        if wrists_overhead and smooth_angle >= self.EXTENDED_ELBOW_THRESHOLD and smooth_gap >= self.MIN_HANG_GAP:
            self.state.calibration_angle_samples.append(smooth_angle)
            self.state.calibration_gap_samples.append(smooth_gap)
        elif self.state.calibration_angle_samples:
            self.state.calibration_angle_samples.clear()
            self.state.calibration_gap_samples.clear()
            return self._result(
                rep_completed=False,
                status="Hang with straight arms and keep both hands visible to calibrate.",
            )

        collected = len(self.state.calibration_angle_samples)
        if collected >= self.CALIBRATION_FRAMES_REQUIRED:
            self.state.top_angle = sum(self.state.calibration_angle_samples) / collected
            self.state.hang_gap = sum(self.state.calibration_gap_samples) / collected
            self.state.down_threshold = max(138.0, self.state.top_angle - 12.0)
            self.state.pull_threshold = min(118.0, max(82.0, self.state.top_angle - 55.0))
            self.state.calibrated = True
            self.state.phase = "down"
            self.state.calibration_angle_samples.clear()
            self.state.calibration_gap_samples.clear()
            return self._result(
                rep_completed=False,
                status="Calibrated. Start pulling.",
            )

        return self._result(
            rep_completed=False,
            status=f"Calibration {collected}/{self.CALIBRATION_FRAMES_REQUIRED}: hang with straight arms under the bar.",
        )

    def _result(self, rep_completed: bool, status: str) -> dict:
        return {
            "rep_completed": rep_completed,
            "status": status,
            "calibrated": self.state.calibrated,
            "calibration_progress": len(self.state.calibration_angle_samples),
            "calibration_required": self.CALIBRATION_FRAMES_REQUIRED,
            "top_angle": self.state.top_angle,
            "down_threshold": self.state.pull_threshold,
            "up_threshold": self.state.down_threshold,
            "hang_gap": self.state.hang_gap,
        }


@dataclass
class PushUpCounterState:
    reps: int = 0
    phase: str = "up"
    last_angle: Optional[float] = None
    smoothed_angles: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    smoothed_body_angles: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    calibration_angle_samples: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    calibration_body_samples: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    calibrated: bool = False
    top_angle: Optional[float] = None
    plank_angle: Optional[float] = None
    down_threshold: float = 96.0
    up_threshold: float = 152.0
    body_threshold: float = 150.0
    last_seen_at: float = field(default_factory=time.monotonic)


class PushUpCounter:
    CALIBRATION_FRAMES_REQUIRED = 8
    EXTENDED_ELBOW_THRESHOLD = 150.0
    STRAIGHT_BODY_THRESHOLD = 150.0

    def __init__(self) -> None:
        self.state = PushUpCounterState()

    def metric_label(self) -> str:
        return "Elbow angle"

    def reset(self) -> None:
        self.state = PushUpCounterState()

    def update(self, landmarks) -> dict:
        left_elbow = angle_degrees(
            landmarks[LEFT_SHOULDER],
            landmarks[LEFT_ELBOW],
            landmarks[LEFT_WRIST],
        )
        right_elbow = angle_degrees(
            landmarks[RIGHT_SHOULDER],
            landmarks[RIGHT_ELBOW],
            landmarks[RIGHT_WRIST],
        )
        elbow_angle = average([left_elbow, right_elbow])
        if elbow_angle is None:
            return self._result(
                rep_completed=False,
                status="Keep shoulders, elbows, and wrists visible for push-up tracking.",
            )

        left_body = angle_degrees(
            landmarks[LEFT_SHOULDER],
            landmarks[LEFT_HIP],
            landmarks[LEFT_ANKLE],
        )
        right_body = angle_degrees(
            landmarks[RIGHT_SHOULDER],
            landmarks[RIGHT_HIP],
            landmarks[RIGHT_ANKLE],
        )
        body_angle = average([left_body, right_body])
        if body_angle is None:
            return self._result(
                rep_completed=False,
                status="Keep your shoulders, hips, and ankles visible in side view.",
            )

        self.state.smoothed_angles.append(elbow_angle)
        self.state.smoothed_body_angles.append(body_angle)
        smooth_angle = sum(self.state.smoothed_angles) / len(self.state.smoothed_angles)
        smooth_body = sum(self.state.smoothed_body_angles) / len(self.state.smoothed_body_angles)
        self.state.last_angle = smooth_angle
        self.state.last_seen_at = time.monotonic()

        if not self.state.calibrated:
            return self._calibrate(smooth_angle, smooth_body)

        plank_ok = smooth_body >= self.state.body_threshold
        down_position = plank_ok and smooth_angle <= self.state.down_threshold
        top_position = plank_ok and smooth_angle >= self.state.up_threshold

        rep_completed = False
        if self.state.phase == "up" and down_position:
            self.state.phase = "down"
        elif self.state.phase == "down" and top_position:
            self.state.phase = "up"
            self.state.reps += 1
            rep_completed = True

        if not plank_ok:
            status = "Keep your hips in line with your shoulders and heels."
        elif self.state.phase == "down":
            status = "Press back up to a strong plank."
        elif down_position:
            status = "Nice depth. Press back up."
        else:
            status = "Lower your chest with control."
        return self._result(rep_completed=rep_completed, status=status)

    def _calibrate(self, smooth_angle: float, smooth_body: float) -> dict:
        if smooth_angle >= self.EXTENDED_ELBOW_THRESHOLD and smooth_body >= self.STRAIGHT_BODY_THRESHOLD:
            self.state.calibration_angle_samples.append(smooth_angle)
            self.state.calibration_body_samples.append(smooth_body)
        elif self.state.calibration_angle_samples:
            self.state.calibration_angle_samples.clear()
            self.state.calibration_body_samples.clear()
            return self._result(
                rep_completed=False,
                status="Hold a high plank with straight arms to calibrate push-ups.",
            )

        collected = len(self.state.calibration_angle_samples)
        if collected >= self.CALIBRATION_FRAMES_REQUIRED:
            self.state.top_angle = sum(self.state.calibration_angle_samples) / collected
            self.state.plank_angle = sum(self.state.calibration_body_samples) / collected
            self.state.down_threshold = max(82.0, self.state.top_angle - 72.0)
            self.state.up_threshold = max(self.state.down_threshold + 18.0, self.state.top_angle - 16.0)
            self.state.body_threshold = max(145.0, (self.state.plank_angle or 165.0) - 18.0)
            self.state.calibrated = True
            self.state.phase = "up"
            self.state.calibration_angle_samples.clear()
            self.state.calibration_body_samples.clear()
            return self._result(
                rep_completed=False,
                status="Calibrated. Start doing push-ups.",
            )

        return self._result(
            rep_completed=False,
            status=f"Calibration {collected}/{self.CALIBRATION_FRAMES_REQUIRED}: hold a high plank with straight arms.",
        )

    def _result(self, rep_completed: bool, status: str) -> dict:
        return {
            "rep_completed": rep_completed,
            "status": status,
            "calibrated": self.state.calibrated,
            "calibration_progress": len(self.state.calibration_angle_samples),
            "calibration_required": self.CALIBRATION_FRAMES_REQUIRED,
            "top_angle": self.state.top_angle,
            "down_threshold": self.state.down_threshold,
            "up_threshold": self.state.up_threshold,
            "body_threshold": self.state.body_threshold,
        }


@dataclass
class PeckDeckCounterState:
    reps: int = 0
    phase: str = "open"
    last_angle: Optional[float] = None
    smoothed_span_ratios: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    calibration_span_samples: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    calibrated: bool = False
    top_angle: Optional[float] = None
    down_threshold: float = 1.0
    up_threshold: float = 1.5
    last_seen_at: float = field(default_factory=time.monotonic)


class PeckDeckCounter:
    CALIBRATION_FRAMES_REQUIRED = 8
    MIN_OPEN_SPAN_RATIO = 1.55
    MAX_WRIST_HEIGHT_DELTA = 0.2
    MAX_ELBOW_HEIGHT_DELTA = 0.18

    def __init__(self) -> None:
        self.state = PeckDeckCounterState()

    def metric_label(self) -> str:
        return "Wrist span"

    def reset(self) -> None:
        self.state = PeckDeckCounterState()

    def update(self, landmarks) -> dict:
        if not all(
            landmark_visible(landmarks[index])
            for index in (
                LEFT_SHOULDER,
                RIGHT_SHOULDER,
                LEFT_ELBOW,
                RIGHT_ELBOW,
                LEFT_WRIST,
                RIGHT_WRIST,
            )
        ):
            return self._result(
                rep_completed=False,
                status="Keep shoulders, elbows, and both hands visible for peck deck tracking.",
            )

        shoulder_span = abs(landmarks[LEFT_SHOULDER].x - landmarks[RIGHT_SHOULDER].x)
        wrist_span = abs(landmarks[LEFT_WRIST].x - landmarks[RIGHT_WRIST].x)
        avg_shoulder_y = average_landmark_y(landmarks, [LEFT_SHOULDER, RIGHT_SHOULDER])
        avg_elbow_y = average_landmark_y(landmarks, [LEFT_ELBOW, RIGHT_ELBOW])
        avg_wrist_y = average_landmark_y(landmarks, [LEFT_WRIST, RIGHT_WRIST])

        if shoulder_span < 0.08 or avg_shoulder_y is None or avg_elbow_y is None or avg_wrist_y is None:
            return self._result(
                rep_completed=False,
                status="Sit facing the camera so shoulders, elbows, and hands are easy to see.",
            )

        wrist_level_ok = abs(avg_wrist_y - avg_shoulder_y) <= self.MAX_WRIST_HEIGHT_DELTA
        elbow_level_ok = abs(avg_elbow_y - avg_shoulder_y) <= self.MAX_ELBOW_HEIGHT_DELTA
        arm_path_ok = wrist_level_ok and elbow_level_ok

        span_ratio = wrist_span / shoulder_span
        self.state.smoothed_span_ratios.append(span_ratio)
        smooth_ratio = sum(self.state.smoothed_span_ratios) / len(self.state.smoothed_span_ratios)
        self.state.last_angle = smooth_ratio
        self.state.last_seen_at = time.monotonic()

        if not self.state.calibrated:
            return self._calibrate(smooth_ratio, arm_path_ok)

        closed_position = arm_path_ok and smooth_ratio <= self.state.down_threshold
        open_position = arm_path_ok and smooth_ratio >= self.state.up_threshold

        rep_completed = False
        if self.state.phase == "open" and closed_position:
            self.state.phase = "closed"
        elif self.state.phase == "closed" and open_position:
            self.state.phase = "open"
            self.state.reps += 1
            rep_completed = True

        if not arm_path_ok:
            status = "Keep your elbows and hands roughly level with your shoulders."
        elif self.state.phase == "closed":
            status = "Open the handles with control."
        elif closed_position:
            status = "Nice squeeze. Open back up slowly."
        else:
            status = "Bring the handles together."
        return self._result(rep_completed=rep_completed, status=status)

    def _calibrate(self, smooth_ratio: float, arm_path_ok: bool) -> dict:
        if arm_path_ok and smooth_ratio >= self.MIN_OPEN_SPAN_RATIO:
            self.state.calibration_span_samples.append(smooth_ratio)
        elif self.state.calibration_span_samples:
            self.state.calibration_span_samples.clear()
            return self._result(
                rep_completed=False,
                status="Open your arms wide at shoulder height to calibrate peck deck mode.",
            )

        collected = len(self.state.calibration_span_samples)
        if collected >= self.CALIBRATION_FRAMES_REQUIRED:
            self.state.top_angle = sum(self.state.calibration_span_samples) / collected
            self.state.down_threshold = max(0.78, (self.state.top_angle or 1.8) * 0.55)
            self.state.up_threshold = max(self.state.down_threshold + 0.22, (self.state.top_angle or 1.8) * 0.82)
            self.state.calibrated = True
            self.state.phase = "open"
            self.state.calibration_span_samples.clear()
            return self._result(
                rep_completed=False,
                status="Calibrated. Start squeezing the handles together.",
            )

        return self._result(
            rep_completed=False,
            status=f"Calibration {collected}/{self.CALIBRATION_FRAMES_REQUIRED}: open your arms wide at shoulder height.",
        )

    def _result(self, rep_completed: bool, status: str) -> dict:
        return {
            "rep_completed": rep_completed,
            "status": status,
            "calibrated": self.state.calibrated,
            "calibration_progress": len(self.state.calibration_span_samples),
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
        self._sessions: dict[tuple[str, str], CounterProtocol] = {}

    def analyze(self, session_id: str, image_b64: str, exercise: str = "squat") -> dict:
        normalized_exercise = normalize_exercise(exercise)
        image = decode_image(image_b64)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        timestamp_ms = int(time.monotonic() * 1000)

        with self._lock:
            result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        session = self._get_session(normalized_exercise, session_id)

        if not result.pose_landmarks:
            return self._build_response(
                exercise=normalized_exercise,
                session_id=session_id,
                session=session,
                rep_completed=False,
                landmarks=[],
                framing_result={
                    "framing_ok": False,
                    "framing_feedback": f"No pose detected. {initial_framing_feedback(normalized_exercise)}",
                },
                update_result={
                    "calibrated": getattr(session.state, "calibrated", False),
                    "calibration_progress": self._calibration_progress(session),
                    "calibration_required": self._calibration_required(session),
                    "top_angle": getattr(session.state, "top_angle", None),
                    "down_threshold": getattr(session.state, "down_threshold", 0.0),
                    "up_threshold": getattr(session.state, "up_threshold", 0.0),
                    "status": f"No pose detected. {initial_framing_feedback(normalized_exercise)}",
                },
            )

        landmarks = result.pose_landmarks[0]
        update_result = session.update(landmarks)
        framing_result = framing_feedback(landmarks, normalized_exercise)

        return self._build_response(
            exercise=normalized_exercise,
            session_id=session_id,
            session=session,
            rep_completed=bool(update_result["rep_completed"]),
            landmarks=[
                {
                    "x": landmark.x,
                    "y": landmark.y,
                    "visibility": getattr(landmark, "visibility", 1.0),
                }
                for landmark in landmarks
            ],
            framing_result=framing_result,
            update_result=update_result,
        )

    def analyze_squat(self, session_id: str, image_b64: str) -> dict:
        return self.analyze(session_id=session_id, image_b64=image_b64, exercise="squat")

    def reset_session(self, session_id: str, exercise: str = "squat") -> dict:
        normalized_exercise = normalize_exercise(exercise)
        session = self._get_session(normalized_exercise, session_id)
        session.reset()
        return {
            "exercise": normalized_exercise,
            "exercise_display": exercise_display_name(normalized_exercise),
            "session_id": session_id,
            "rep_count": 0,
            "rep_completed": False,
            "phase": session.state.phase,
            "primary_angle": session.state.last_angle,
            "metric_label": session.metric_label(),
            "landmarks": [],
            "calibrated": session.state.calibrated,
            "calibration_progress": self._calibration_progress(session),
            "calibration_required": self._calibration_required(session),
            "top_angle": session.state.top_angle,
            "down_threshold": getattr(session.state, "down_threshold", 0.0),
            "up_threshold": getattr(session.state, "up_threshold", 0.0),
            "framing_ok": False,
            "framing_feedback": initial_framing_feedback(normalized_exercise),
            "status": f"{exercise_display_name(normalized_exercise)} session reset.",
        }

    def _get_session(self, exercise: str, session_id: str) -> CounterProtocol:
        key = (exercise, session_id)
        if key not in self._sessions:
            self._sessions[key] = self._create_counter(exercise)
        return self._sessions[key]

    @staticmethod
    def _create_counter(exercise: str) -> CounterProtocol:
        if exercise == "pushup":
            return PushUpCounter()
        if exercise == "peckdeck":
            return PeckDeckCounter()
        if exercise == "pullup":
            return PullUpCounter()
        return SquatCounter()

    @staticmethod
    def _calibration_progress(session: CounterProtocol) -> int:
        if hasattr(session.state, "calibration_samples"):
            return len(session.state.calibration_samples)
        if hasattr(session.state, "calibration_angle_samples"):
            return len(session.state.calibration_angle_samples)
        if hasattr(session.state, "calibration_span_samples"):
            return len(session.state.calibration_span_samples)
        return 0

    @staticmethod
    def _calibration_required(session: CounterProtocol) -> int:
        return getattr(session, "CALIBRATION_FRAMES_REQUIRED", 0)

    def _build_response(
        self,
        *,
        exercise: str,
        session_id: str,
        session: CounterProtocol,
        rep_completed: bool,
        landmarks: list[dict[str, float]],
        framing_result: dict[str, object],
        update_result: dict,
    ) -> dict:
        return {
            "exercise": exercise,
            "exercise_display": exercise_display_name(exercise),
            "session_id": session_id,
            "rep_count": session.state.reps,
            "rep_completed": rep_completed,
            "phase": session.state.phase,
            "primary_angle": session.state.last_angle,
            "metric_label": session.metric_label(),
            "landmarks": landmarks,
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
