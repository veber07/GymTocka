from __future__ import annotations

import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from server.detector import PoseService


app = FastAPI(title="FitSpin Workout Backend", version="0.2.0")
pose_service = PoseService()


class ExerciseRequest(BaseModel):
    session_id: str
    image_b64: str
    exercise: str = "squat"


class SessionRequest(BaseModel):
    session_id: str
    exercise: str = "squat"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/exercise/analyze")
def analyze_exercise(payload: ExerciseRequest) -> dict:
    return pose_service.analyze(
        session_id=payload.session_id,
        image_b64=payload.image_b64,
        exercise=payload.exercise,
    )


@app.post("/api/v1/exercise/reset")
def reset_exercise(payload: SessionRequest) -> dict:
    return pose_service.reset_session(session_id=payload.session_id, exercise=payload.exercise)


@app.post("/api/v1/squat/analyze")
def analyze_squat(payload: ExerciseRequest) -> dict:
    return pose_service.analyze(
        session_id=payload.session_id,
        image_b64=payload.image_b64,
        exercise="squat",
    )


@app.post("/api/v1/squat/reset")
def reset_squat(payload: SessionRequest) -> dict:
    return pose_service.reset_session(session_id=payload.session_id, exercise="squat")


@app.websocket("/ws/exercise")
async def exercise_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            action = payload.get("action", "analyze")
            exercise = payload.get("exercise", "squat")
            if action == "reset":
                result = pose_service.reset_session(session_id=payload["session_id"], exercise=exercise)
            else:
                result = pose_service.analyze(
                    session_id=payload["session_id"],
                    image_b64=payload["image_b64"],
                    exercise=exercise,
                )
            await websocket.send_json(result)
    except WebSocketDisconnect:
        return


@app.websocket("/ws/squat")
async def squat_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            action = payload.get("action", "analyze")
            if action == "reset":
                result = pose_service.reset_session(session_id=payload["session_id"], exercise="squat")
            else:
                result = pose_service.analyze(
                    session_id=payload["session_id"],
                    image_b64=payload["image_b64"],
                    exercise="squat",
                )
            await websocket.send_json(result)
    except WebSocketDisconnect:
        return
