from __future__ import annotations

import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from server.detector import PoseService


app = FastAPI(title="FitSpin Squat Backend", version="0.1.0")
pose_service = PoseService()


class SquatRequest(BaseModel):
    session_id: str
    image_b64: str


class SessionRequest(BaseModel):
    session_id: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/squat/analyze")
def analyze_squat(payload: SquatRequest) -> dict:
    return pose_service.analyze_squat(
        session_id=payload.session_id,
        image_b64=payload.image_b64,
    )


@app.post("/api/v1/squat/reset")
def reset_squat(payload: SessionRequest) -> dict:
    return pose_service.reset_session(session_id=payload.session_id)


@app.websocket("/ws/squat")
async def squat_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            action = payload.get("action", "analyze")
            if action == "reset":
                result = pose_service.reset_session(session_id=payload["session_id"])
            else:
                result = pose_service.analyze_squat(
                    session_id=payload["session_id"],
                    image_b64=payload["image_b64"],
                )
            await websocket.send_json(result)
    except WebSocketDisconnect:
        return
