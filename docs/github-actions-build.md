# GitHub Actions APK Build

If you cannot use WSL2 or BIOS virtualization locally, you can build the APK on GitHub.

## 1. Create a GitHub repository

1. Create a new repository on GitHub.
2. Upload this whole project to that repository.

You need these folders and files included:

- `fitspin/`
- `server/`
- `.github/workflows/android-build.yml`
- `buildozer.spec`
- `main.py`

## 2. Start the build

There are two ways:

1. Push to branch `main` or `master`
2. Or open GitHub:
   - `Actions`
   - `Build Android APK`
   - `Run workflow`

## 3. Wait for the job to finish

The first build can take quite a while because Android dependencies are downloaded and prepared.

## 4. Download the APK

1. Open the finished workflow run
2. Scroll to `Artifacts`
3. Download `fitspin-apk`
4. Extract the ZIP
5. You will get the built `.apk`

## 5. Install it on your phone

If `adb` is available:

```powershell
.\scripts\install_apk_windows.ps1 -ApkPath C:\path\to\your.apk
```

Or manually copy the APK to the phone and open it there.

## Notes

- This workflow uses a Buildozer GitHub Action on Ubuntu.
- If the build fails, open the workflow logs and look at the failed step.
- APK building in GitHub Actions does not require WSL on your PC.
