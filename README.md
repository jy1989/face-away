# FaceAway

**Face-aware desktop privacy for Windows.** Walk away and your open windows minimize automatically; return and FaceAway restores the windows it hid. Enroll with **one webcam photo**, with no model training, account, or cloud service.

**English** | [简体中文](README.zh-CN.md)

> **MVP / Experimental.** This is a convenience and privacy tool, **not** an authentication or security boundary. It must not replace Windows locking (Win + L). A photo or video may fool ordinary webcam-based recognition.

## Features

- **One-photo enrollment:** store a 128-dimensional facial feature vector, not the photograph.
- **Presence-aware desktop:** minimize visible normal windows after ~3 seconds away; attempt restoration after ~1 second of confirming your face.
- **Remember window state:** preserve already-minimized windows, and try to restore prior normal/maximized placements.
- **Smooth preview:** up to ~15 FPS camera preview and face matching about every 700 ms on a dedicated Qt worker thread, with lower overhead when hidden in the tray.
- **Local-first:** all camera frames and face recognition run locally. The facial template is protected with Windows DPAPI.
- **Auto-monitor on launch (enabled by default):** when a face is enrolled, monitoring activates after startup initialization. The checkbox in settings can disable this preference. First-time users without a face template are never armed until enrollment succeeds.\n- **Tray controls:** pause/resume, restore windows on demand, exit, and adjust away/return delays.

## Requirements

- Windows 10/11 and a working webcam.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (available in the development environment).
- Internet only for the **initial** Python package and pretrained ONNX model download.
- No GPU, model training, or cloud account required. Dependencies include Python 3.11, PySide6 Essentials, OpenCV, NumPy, and pywin32.

## Standalone Windows EXE

You can build a single **console-free** executable with `build_exe.bat` after running `setup.bat` once. Output: `dist/FaceAway-v0.2.exe` (about **132 MiB** in the current Windows build, including both models). Double-click `FaceAway-v0.2.exe` directly: **no BAT window or Python installation is needed on the destination PC**. It uses the same encrypted face profile stored under `%LOCALAPPDATA%/FaceAway/`.

PyInstaller one-file binaries unpack native dependencies into a temporary directory at launch, so startup can be slower than a folder-style install. The EXE is generated locally and is not code-signed; Windows SmartScreen may warn about an unknown publisher. Do not run a second copy while the existing Python app is monitoring the desktop.

## Getting started

```powershell
git clone https://github.com/jy1989/face-away.git
cd face-away
.\setup.bat
.\run.bat
```

Or, if working from the existing local project, just double-click `run.bat`. Run `setup.bat` once if the model weights have not been downloaded.

1. Open the app and wait for the webcam preview.
2. Click **拍一张照片录入 / 重录** (Enroll / retake one photo) once. Face the camera alone and in reasonable lighting.
3. **Monitoring starts automatically by default** if your face is already enrolled. On first enrollment, monitoring begins after the face is saved. To disable automatic monitoring on subsequent launches, uncheck **启动后自动开启监控（默认开启）** (Start monitoring automatically). You can always pause from the tray.
4. Optionally hide settings to the system tray. Right-click the tray icon to pause, restore windows, or quit.
5. To update the code, **exit the previous FaceAway process first** and start again with `run.bat`. Enrollment is retained; you do not have to retake your photo.

The MVP UI is currently in Simplified Chinese; this README and the linked Chinese guide document all options in both languages.

## How it works

```text
Webcam → OpenCV YuNet face detection → OpenCV SFace embedding
                                        ↓
                                  DPAPI-protected
                               enrolled face template
                                        ↓
                   Local cosine-similarity face match
                                        ↓
                    Debounced presence state (3s / 1s)
                                        ↓
                      Win32 window minimize / restore
```

The camera worker keeps capture and inference off the UI thread. Video frames are **never uploaded** and aren't written to disk. Only the encrypted enrolled embedding and delay preferences are persisted locally.

## Privacy and security

- Facial embedding: `%LOCALAPPDATA%\FaceAway\face.dat` — encrypted by Windows DPAPI for the current Windows account.
- Delay settings: `%LOCALAPPDATA%\FaceAway\settings.json`.
- Enrollment photo and webcam frames: **not saved**.
- No login, analytics, telemetry, or photo uploads are implemented.
- `setup.bat` retrieves packages and official pretrained models over the network. Models are validated against SHA-256 hashes.
- Already-minimized windows, elevated apps, games, special windows, virtual desktops, and unusual multi-monitor setups may not restore perfectly. Window z-order isn't guaranteed.
- This is **not** liveness detection. Someone using a photo/video or accessing the computer by other means may defeat it.

## Tests

```powershell
uv run --python 3.11 --with-requirements requirements.txt python -m unittest -v test_presence.py test_auto_monitor.py
uv run --python 3.11 --with-requirements requirements.txt python smoke_test.py
uv run --python 3.11 --with-requirements requirements.txt python test_camera_worker.py
uv run --python 3.11 --with-requirements requirements.txt python -m compileall -q .
```

The simulated-camera test measures throughput without triggering window minimization. Actual speed depends on webcam hardware and drivers. If the app is forcibly terminated while windows are hidden, the in-memory placement snapshot may be lost.

## Project layout

| File | Purpose |
|---|---|
| `app.py` | Qt desktop UI, tray, application state |
| `camera_worker.py` | Background webcam capture and recognition |
| `face_engine.py` | YuNet + SFace detection/embedding |
| `presence.py` | Away/return timing state machine |
| `window_manager.py` | Windows window snapshot/minimize/restore |
| `profile_store.py` | DPAPI-protected facial template |
| `models.py` | Download and verify model weights |
| `setup.bat`, `run.bat` | Windows setup and launcher |
| `test_*.py`, `smoke_test.py` | Tests and smoke checks |

## Open source and third-party notices

FaceAway application **source code** is available under the [MIT License](LICENSE). Downloaded ONNX model weights are **not included in this repository** and keep their own licenses: see [OpenCV Zoo YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) and [OpenCV Zoo SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface) (SFace is Apache-2.0 licensed). Dependencies maintain their respective licenses. Review third-party license and model provenance before redistributing binaries or using them commercially.

Bug reports and contributions are welcome; please avoid uploading photos, facial templates, or private logs in issues.
