from __future__ import annotations

from pathlib import Path
import traceback

from fitspin.app import FitSpinApp


def _write_startup_crash(exc: BaseException) -> None:
    try:
        app = FitSpinApp()
        crash_dir = Path(app.user_data_dir)
        crash_dir.mkdir(parents=True, exist_ok=True)
        crash_path = crash_dir / "startup_crash.log"
        crash_path.write_text("".join(traceback.format_exception(exc)), encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        FitSpinApp().run()
    except Exception as exc:
        _write_startup_crash(exc)
        raise
