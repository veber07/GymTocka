# Android Build in WSL2

This project should be built in `WSL2`, not on native Windows.

## 1. Prepare WSL

Install Ubuntu in WSL2, then copy the project into the Linux filesystem, for example:

```bash
mkdir -p ~/projects
cp -r /mnt/c/Users/spide/.nejlepsiApp ~/projects/fitspin
cd ~/projects/fitspin
```

Do not build from `/mnt/c/...`. Buildozer is less reliable there and significantly slower.

## 2. Install system packages

These commands follow the current Buildozer Android installation guidance for Ubuntu:

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-virtualenv autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo6 cmake libffi-dev libssl-dev automake autopoint gettext
```

## 3. Create a virtual environment

```bash
python3 -m venv .venv-buildozer
source .venv-buildozer/bin/activate
pip install --upgrade pip
pip install -r android.requirements.txt
```

## 4. Build the APK

First build:

```bash
buildozer android debug
```

After changing `buildozer.spec`, clean and rebuild:

```bash
buildozer appclean
buildozer android debug
```

## 5. Install on the phone

WSL does not have direct USB access in the common setup, so the easiest path is:

1. Copy the generated APK from `bin/` back to Windows.
2. Install Android platform-tools on Windows.
3. Use Windows `adb install` from a normal Windows terminal.

Example:

```powershell
C:\platform-tools\adb install C:\path\to\fitspin-debug.apk
```

## 6. Useful debugging

```bash
buildozer android deploy run
buildozer android logcat
```
