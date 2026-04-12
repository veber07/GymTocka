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

    for exercise in ("squat", "pullup"):
        reset = client.post(
            "/api/v1/exercise/reset",
            json={"exercise": exercise, "session_id": f"smoke-{exercise}"},
        )
        assert reset.status_code == 200, reset.text
        reset_json = reset.json()
        assert reset_json["rep_count"] == 0
        assert reset_json["exercise"] == exercise

        analyze = client.post(
            "/api/v1/exercise/analyze",
            json={
                "exercise": exercise,
                "session_id": f"smoke-{exercise}",
                "image_b64": blank_image_b64(),
            },
        )
        assert analyze.status_code == 200, analyze.text
        analyze_json = analyze.json()
        assert "rep_count" in analyze_json
        assert "status" in analyze_json
        assert "framing_feedback" in analyze_json
        assert analyze_json["exercise"] == exercise

    legacy_reset = client.post("/api/v1/squat/reset", json={"session_id": "smoke-legacy"})
    assert legacy_reset.status_code == 200, legacy_reset.text
    assert legacy_reset.json()["exercise"] == "squat"

    with client.websocket_connect("/ws/exercise") as websocket:
        websocket.send_json({"action": "reset", "exercise": "pullup", "session_id": "smoke-ws"})
        reset_result = websocket.receive_json()
        assert reset_result["rep_count"] == 0
        assert reset_result["exercise"] == "pullup"

        websocket.send_json(
            {
                "action": "analyze",
                "exercise": "pullup",
                "session_id": "smoke-ws",
                "image_b64": blank_image_b64(),
            }
        )
        ws_result = websocket.receive_json()
        assert "status" in ws_result
        assert "framing_feedback" in ws_result
        assert ws_result["exercise"] == "pullup"

    print("Smoke test passed.")


if __name__ == "__main__":
    main()
