#!/usr/bin/env bash
set -euo pipefail

if ! command -v wslpath >/dev/null 2>&1; then
  echo "Run this script inside WSL."
  exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ROOT="${1:-$HOME/projects/fitspin}"

mkdir -p "$(dirname "$TARGET_ROOT")"
rsync -a --delete \
  --exclude '.venv/' \
  --exclude '.buildozer/' \
  --exclude 'bin/' \
  --exclude '__pycache__/' \
  "$PROJECT_ROOT/" "$TARGET_ROOT/"

cd "$TARGET_ROOT"

python3 -m venv .venv-buildozer
source .venv-buildozer/bin/activate
python -m pip install --upgrade pip
python -m pip install -r android.requirements.txt

buildozer android debug

echo
echo "Build finished."
echo "APK directory: $TARGET_ROOT/bin"
