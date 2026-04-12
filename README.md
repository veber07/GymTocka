# FitSpin MVP

Android-first prototype for a gamified squat tracker built in Python.

## What is included

- `main.py`: Kivy Android client
- `fitspin/`: rear camera preview, backend networking, slot machine UI
- `server/`: FastAPI backend with MediaPipe squat tracking
- `run_backend.py`: simple local backend launcher
- `scripts/`: helper scripts for backend run, WSL build, and APK install
- `buildozer.spec`: Android packaging starting point
- `.github/workflows/android-build.yml`: remote APK build via GitHub Actions and official Buildozer Docker image

## Why the backend exists

This MVP keeps the Android app in Python, but offloads pose inference to a Python backend.
That is the most practical route for a working prototype because MediaPipe Python wheels are easy on desktop/server and much harder to ship inside a Kivy Android build.

## Backend setup

1. Create a virtual environment.
2. Install dependencies:

```bash
pip install -r server/requirements.txt
```

3. Run the API:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

or:

```bash
python run_backend.py
```

4. Find your computer's LAN IP, for example `192.168.0.10`.

Backend smoke test:

```bash
python -m server.smoke_test
```

Windows helpers:

```powershell
.\scripts\start_backend_windows.ps1
.\scripts\check_backend_windows.ps1
```

## Backend with Docker

If you already have Docker Desktop, this is the fastest path:

```bash
docker compose up --build
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

The phone should use your computer's LAN IP, for example:

```text
http://192.168.0.10:8000
```

Do not use `http://127.0.0.1:8000` or `http://localhost:8000` on the phone.
On Android, those addresses point back to the phone itself, not to your computer.

## Android app setup

Buildozer is most reliable on Linux or WSL2, not native Windows.

1. In Linux or WSL, create a build environment.
2. Install Python tooling:

```bash
pip install -r android.requirements.txt
```

3. Install the usual Android build dependencies for Buildozer and python-for-android.
4. Build the APK:

```bash
buildozer android debug
```

5. Install the APK on the phone.
6. Open the app.
7. Set `Backend URL` to your server IP, for example `http://192.168.0.10:8000`.
   Never use `127.0.0.1` or `localhost` there unless the backend is running on the phone itself.
8. Start the camera and place the phone so the whole body is visible.

Useful Buildozer commands:

```bash
buildozer android deploy run
buildozer android logcat
```

Detailed WSL2 build notes:

- [docs/android-build-wsl.md](c:/Users/spide/.nejlepsiApp/docs/android-build-wsl.md)
- [docs/device-test-checklist.md](c:/Users/spide/.nejlepsiApp/docs/device-test-checklist.md)
- [docs/github-actions-build.md](c:/Users/spide/.nejlepsiApp/docs/github-actions-build.md)

WSL helper:

```bash
bash scripts/build_android_wsl.sh
```

Windows APK install helper:

```powershell
.\scripts\install_apk_windows.ps1
```

If WSL2 is blocked on your machine, use GitHub Actions instead:

```text
.github/workflows/android-build.yml
```

## Architecture snapshot

- `fitspin/` is the Android client.
- `server/` is the squat detection backend.
- The app sends compressed camera frames to the backend every ~180ms.
- The app prefers a persistent WebSocket stream and falls back to HTTP if needed.
- The backend returns landmarks, squat angle, phase, and rep events.
- Each rep event triggers one slot machine spin in the app.
- The app can reset the active squat session without restarting.
- Tracking only runs during an active set, started from the app UI.
- Each new set begins with a short standing calibration to personalize squat thresholds.
- The camera preview includes a framing guide that changes color when the body is centered well.

## Current behavior

- Squat only
- Rear camera
- One completed squat triggers one slot spin
- Very simple threshold-based rep counting
- Pose inference runs on the backend, not directly on the phone
- `Start Set` begins a fresh timed series and clears counters
- The first seconds of a set are used for standing calibration before reps count
- `End Set` stops tracking and stores the last set summary
- `Reset Counters` clears the session without starting a new set
- Framing hints tell the user to move closer, farther back, or re-center
- Transport status in the UI shows whether streaming is using WebSocket or HTTP fallback

## Known limitations

- Requires the phone and backend machine to be on the same network
- Network latency affects rep feedback speed
- Bench press and pull-up are not implemented yet
- Squat counting is threshold-based, so edge cases and false counts still exist
- Android APK build was prepared here, but not executed in this workspace

## Next recommended steps

- Add offline or on-device inference later with a native bridge or non-Python mobile inference layer
