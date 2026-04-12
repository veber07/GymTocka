# Device Test Checklist

## Before the test

1. Start the backend:

```powershell
.\scripts\start_backend_windows.ps1
```

2. Confirm the backend responds:

```powershell
.\scripts\check_backend_windows.ps1
```

3. Make sure the phone and computer are on the same Wi-Fi.
4. Build and install the APK.
5. Open the app and enter the computer LAN IP, for example `http://192.168.0.10:8000`.
6. Do not enter `127.0.0.1` or `localhost` on the phone. That targets the phone, not the backend PC.

## In-app test flow

1. Tap `Start Camera`.
2. Adjust your position until the framing guide turns green.
3. Tap `Start Set`.
4. Stand tall until calibration finishes.
5. Do 5 slow squats.
6. Confirm:
   - reps increment
   - slot machine spins on each rep
   - framing hints update when you move out of frame
   - transport shows `WebSocket` or `HTTP fallback`
7. Tap `End Set`.
8. Check the last set summary.

## If something fails

1. Check backend logs.
2. Check `Transport` in the app.
3. If the guide never turns green, move farther back and center your body.
4. If reps never count, redo calibration with a stable standing pose.
5. For Android runtime issues, inspect:

```bash
buildozer android logcat
```
