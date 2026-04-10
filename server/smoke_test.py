from __future__ import annotations

import base64
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from server.app import app


def blank_image_b64(width: int = 320, height: int = 320) -> str:
    image = Image.new("RGB", (width, height), color=(0, 0, 0))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=70)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def main() -> None:
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200, health.text
    assert health.json()["status"] == "ok"

    reset = client.post("/api/v1/squat/reset", json={"session_id": "smoke"})
    assert reset.status_code == 200, reset.text
    assert reset.json()["rep_count"] == 0

    analyze = client.post(
        "/api/v1/squat/analyze",
        json={
            "session_id": "smoke",
            "image_b64": blank_image_b64(),
        },
    )
    assert analyze.status_code == 200, analyze.text
    analyze_json = analyze.json()
    assert "rep_count" in analyze_json
    assert "status" in analyze_json
    assert "framing_feedback" in analyze_json

    with client.websocket_connect("/ws/squat") as websocket:
        websocket.send_json({"action": "reset", "session_id": "smoke-ws"})
        reset_result = websocket.receive_json()
        assert reset_result["rep_count"] == 0

        websocket.send_json(
            {
                "action": "analyze",
                "session_id": "smoke-ws",
                "image_b64": blank_image_b64(),
            }
        )
        ws_result = websocket.receive_json()
        assert "status" in ws_result
        assert "framing_feedback" in ws_result

    print("Smoke test passed.")


if __name__ == "__main__":
    main()
