"""Desktop prototype for pose-based rep counting with slot-machine rewards.

This script is intentionally simple:
- uses a webcam as a stand-in for the rear phone camera
- uses MediaPipe Pose Landmarker for body landmarks
- counts rough reps with threshold-based state machines
- overlays a basic slot machine on top of the camera feed

Install:
    pip install mediapipe opencv-python

Download the pose model from the MediaPipe docs and place it next to this file:
    pose_landmarker.task

Run:
    python prototype_pose_counter.py --exercise squat --model pose_landmarker.task
"""

from __future__ import annotations

import argparse
import math
import random
import time
from collections import deque
from dataclasses import dataclass
from typing import Iterable, Optional

import cv2
import mediapipe as mp


POSE = mp.solutions.pose
LANDMARK = POSE.PoseLandmark
CONNECTIONS = tuple(POSE.POSE_CONNECTIONS)


def landmark_visible(landmark: object, min_visibility: float = 0.5) -> bool:
    return getattr(landmark, "visibility", 1.0) >= min_visibility


def average(values: Iterable[float]) -> Optional[float]:
    values = [value for value in values if value is not None]
    if not values:
        return None
    return sum(values) / len(values)


def angle_degrees(a: object, b: object, c: object) -> Optional[float]:
    if not (landmark_visible(a) and landmark_visible(b) and landmark_visible(c)):
        return None

    ab_x = a.x - b.x
    ab_y = a.y - b.y
    cb_x = c.x - b.x
    cb_y = c.y - b.y

    ab_norm = math.hypot(ab_x, ab_y)
    cb_norm = math.hypot(cb_x, cb_y)
    if ab_norm == 0 or cb_norm == 0:
        return None

    cosine = (ab_x * cb_x + ab_y * cb_y) / (ab_norm * cb_norm)
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


class RollingAverage:
    def __init__(self, size: int = 5) -> None:
        self.values: deque[float] = deque(maxlen=size)

    def push(self, value: Optional[float]) -> Optional[float]:
        if value is not None:
            self.values.append(value)
        if not self.values:
            return None
        return sum(self.values) / len(self.values)


@dataclass
class CounterState:
    reps: int = 0
    phase: str = "ready"
    last_metric: Optional[float] = None


class ExerciseCounter:
    name = "exercise"

    def __init__(self) -> None:
        self.state = CounterState()

    def update(self, landmarks: list[object]) -> bool:
        raise NotImplementedError

    def debug_text(self) -> str:
        metric = (
            f"{self.state.last_metric:.1f}"
            if self.state.last_metric is not None
            else "n/a"
        )
        return f"{self.name} | phase={self.state.phase} | metric={metric}"


class SquatCounter(ExerciseCounter):
    name = "squat"

    def __init__(self) -> None:
        super().__init__()
        self.knee_smoother = RollingAverage()
        self.state.phase = "up"

    def update(self, landmarks: list[object]) -> bool:
        left_knee = angle_degrees(
            landmarks[LANDMARK.LEFT_HIP],
            landmarks[LANDMARK.LEFT_KNEE],
            landmarks[LANDMARK.LEFT_ANKLE],
        )
        right_knee = angle_degrees(
            landmarks[LANDMARK.RIGHT_HIP],
            landmarks[LANDMARK.RIGHT_KNEE],
            landmarks[LANDMARK.RIGHT_ANKLE],
        )
        knee_angle = self.knee_smoother.push(average([left_knee, right_knee]))
        self.state.last_metric = knee_angle

        if knee_angle is None:
            return False

        down_threshold = 100
        up_threshold = 155

        if self.state.phase == "up" and knee_angle <= down_threshold:
            self.state.phase = "down"
        elif self.state.phase == "down" and knee_angle >= up_threshold:
            self.state.phase = "up"
            self.state.reps += 1
            return True
        return False


class PullUpCounter(ExerciseCounter):
    name = "pull_up"

    def __init__(self) -> None:
        super().__init__()
        self.elbow_smoother = RollingAverage()
        self.state.phase = "down"

    def update(self, landmarks: list[object]) -> bool:
        left_elbow = angle_degrees(
            landmarks[LANDMARK.LEFT_SHOULDER],
            landmarks[LANDMARK.LEFT_ELBOW],
            landmarks[LANDMARK.LEFT_WRIST],
        )
        right_elbow = angle_degrees(
            landmarks[LANDMARK.RIGHT_SHOULDER],
            landmarks[LANDMARK.RIGHT_ELBOW],
            landmarks[LANDMARK.RIGHT_WRIST],
        )
        elbow_angle = self.elbow_smoother.push(average([left_elbow, right_elbow]))
        self.state.last_metric = elbow_angle

        if elbow_angle is None:
            return False

        nose = landmarks[LANDMARK.NOSE]
        left_shoulder = landmarks[LANDMARK.LEFT_SHOULDER]
        right_shoulder = landmarks[LANDMARK.RIGHT_SHOULDER]
        shoulder_y = average([left_shoulder.y, right_shoulder.y])
        chin_above_shoulders = shoulder_y is not None and nose.y < shoulder_y - 0.03

        if self.state.phase == "down" and elbow_angle <= 85 and chin_above_shoulders:
            self.state.phase = "up"
            self.state.reps += 1
            return True
        if self.state.phase == "up" and elbow_angle >= 145:
            self.state.phase = "down"
        return False


class BenchPressCounter(ExerciseCounter):
    name = "bench_press"

    def __init__(self) -> None:
        super().__init__()
        self.elbow_smoother = RollingAverage()
        self.state.phase = "up"

    def update(self, landmarks: list[object]) -> bool:
        left_elbow = angle_degrees(
            landmarks[LANDMARK.LEFT_SHOULDER],
            landmarks[LANDMARK.LEFT_ELBOW],
            landmarks[LANDMARK.LEFT_WRIST],
        )
        right_elbow = angle_degrees(
            landmarks[LANDMARK.RIGHT_SHOULDER],
            landmarks[LANDMARK.RIGHT_ELBOW],
            landmarks[LANDMARK.RIGHT_WRIST],
        )
        elbow_angle = self.elbow_smoother.push(average([left_elbow, right_elbow]))
        self.state.last_metric = elbow_angle

        if elbow_angle is None:
            return False

        lowered_threshold = 95
        locked_threshold = 155

        if self.state.phase == "up" and elbow_angle <= lowered_threshold:
            self.state.phase = "down"
        elif self.state.phase == "down" and elbow_angle >= locked_threshold:
            self.state.phase = "up"
            self.state.reps += 1
            return True
        return False


class SlotMachine:
    SYMBOLS = ("7", "BAR", "CHERRY", "STAR", "COIN")

    def __init__(self) -> None:
        self.reels = ["-", "-", "-"]
        self.score = 0
        self.last_reward = 0
        self.last_combo = "---"
        self.pending_spins = 0
        self.spin_until = 0.0
        self.final_result: Optional[list[str]] = None

    def trigger(self) -> None:
        self.pending_spins += 1
        if self.final_result is None:
            self._start_next_spin()

    def _start_next_spin(self) -> None:
        if self.pending_spins <= 0:
            return
        self.pending_spins -= 1
        self.final_result = [random.choice(self.SYMBOLS) for _ in range(3)]
        self.spin_until = time.time() + 0.8

    def update(self) -> None:
        if self.final_result is None:
            return

        if time.time() < self.spin_until:
            self.reels = [random.choice(self.SYMBOLS) for _ in range(3)]
            return

        self.reels = self.final_result
        self.last_combo = " ".join(self.reels)
        self.last_reward = self._reward(self.reels)
        self.score += self.last_reward
        self.final_result = None

        if self.pending_spins > 0:
            self._start_next_spin()

    @staticmethod
    def _reward(reels: list[str]) -> int:
        unique = len(set(reels))
        if unique == 1:
            return 100 if reels[0] == "7" else 50
        if unique == 2:
            return 10
        return 2

    @property
    def spinning(self) -> bool:
        return self.final_result is not None


def create_counter(name: str) -> ExerciseCounter:
    if name == "squat":
        return SquatCounter()
    if name == "pull_up":
        return PullUpCounter()
    if name == "bench_press":
        return BenchPressCounter()
    raise ValueError(f"Unsupported exercise: {name}")


def draw_pose(frame: object, landmarks: list[object]) -> None:
    height, width = frame.shape[:2]

    for start, end in CONNECTIONS:
        start_lm = landmarks[start]
        end_lm = landmarks[end]
        if not (landmark_visible(start_lm, 0.4) and landmark_visible(end_lm, 0.4)):
            continue
        start_point = (int(start_lm.x * width), int(start_lm.y * height))
        end_point = (int(end_lm.x * width), int(end_lm.y * height))
        cv2.line(frame, start_point, end_point, (80, 220, 120), 2)

    for landmark in landmarks:
        if not landmark_visible(landmark, 0.4):
            continue
        point = (int(landmark.x * width), int(landmark.y * height))
        cv2.circle(frame, point, 4, (255, 255, 255), -1)


def draw_slot_machine(frame: object, slot_machine: SlotMachine) -> None:
    origin_x = 20
    origin_y = 20
    width = 300
    height = 160

    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (origin_x, origin_y),
        (origin_x + width, origin_y + height),
        (20, 20, 20),
        -1,
    )
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    cv2.rectangle(
        frame,
        (origin_x, origin_y),
        (origin_x + width, origin_y + height),
        (0, 210, 255),
        2,
    )

    cv2.putText(
        frame,
        "REP SLOT",
        (origin_x + 12, origin_y + 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    for index, symbol in enumerate(slot_machine.reels):
        reel_x = origin_x + 15 + index * 95
        reel_y = origin_y + 45
        cv2.rectangle(frame, (reel_x, reel_y), (reel_x + 80, reel_y + 58), (255, 255, 255), 2)
        cv2.putText(
            frame,
            symbol,
            (reel_x + 8, reel_y + 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 210, 255),
            2,
            cv2.LINE_AA,
        )

    status = "spinning..." if slot_machine.spinning else f"+{slot_machine.last_reward} coins"
    cv2.putText(
        frame,
        status,
        (origin_x + 12, origin_y + 128),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"score: {slot_machine.score}",
        (origin_x + 150, origin_y + 128),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def draw_status_panel(frame: object, counter: ExerciseCounter, exercise_name: str) -> None:
    height, width = frame.shape[:2]
    panel_x = width - 330
    panel_y = 20

    overlay = frame.copy()
    cv2.rectangle(overlay, (panel_x, panel_y), (width - 20, panel_y + 130), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    cv2.rectangle(frame, (panel_x, panel_y), (width - 20, panel_y + 130), (255, 255, 255), 2)

    text_rows = [
        f"exercise: {exercise_name}",
        f"reps: {counter.state.reps}",
        f"phase: {counter.state.phase}",
        counter.debug_text(),
        "q = quit",
    ]

    for index, row in enumerate(text_rows):
        cv2.putText(
            frame,
            row,
            (panel_x + 12, panel_y + 28 + index * 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exercise",
        choices=("squat", "pull_up", "bench_press"),
        default="squat",
        help="Exercise to detect.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Path to MediaPipe pose_landmarker.task model.",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Camera index. Use the rear camera index on mobile hardware.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Requested camera width.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Requested camera height.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    counter = create_counter(args.exercise)
    slot_machine = SlotMachine()

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {args.camera}.")

    base_options = mp.tasks.BaseOptions(model_asset_path=args.model)
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    with mp.tasks.vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            timestamp_ms = int(time.time() * 1000)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            landmarks = result.pose_landmarks[0] if result.pose_landmarks else None
            if landmarks:
                draw_pose(frame, landmarks)
                if counter.update(landmarks):
                    slot_machine.trigger()

            slot_machine.update()
            draw_slot_machine(frame, slot_machine)
            draw_status_panel(frame, counter, args.exercise)

            cv2.imshow("Gamified Fitness Prototype", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
