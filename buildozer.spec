[app]
title = FitSpin
package.name = fitspin
package.domain = cz.spide
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,json,txt,md
source.exclude_dirs = server,__pycache__,.git,.venv,venv,.buildozer,bin
source.exclude_patterns = server/*,__pycache__/*,.git/*,.venv/*,venv/*,.buildozer/*,bin/*
version = 0.1.0
requirements = python3,kivy==2.3.1,requests,filetype,camera4kivy,gestures4kivy,pillow,websocket-client
orientation = portrait
fullscreen = 0
android.entrypoint = org.kivy.android.PythonActivity
android.allow_backup = False

android.api = 33
android.minapi = 24
android.accept_sdk_license = True
android.permissions = CAMERA,INTERNET
android.add_manifest_application = android:usesCleartextTraffic="true"
android.archs = arm64-v8a
p4a.hook = camerax_provider/gradle_options.py
android.logcat_filters = python:D, python.stderr:W, ActivityManager:I, SDL:I, CameraX:I
android.presplash_color = #11181c

[buildozer]
log_level = 2
warn_on_root = 1
