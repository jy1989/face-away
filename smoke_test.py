"""Noninteractive integration smoke test. Never opens camera or minimizes windows."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import cv2
import numpy as np
import win32crypt
from PySide6.QtWidgets import QApplication
from face_engine import FaceEngine
from models import models_ready
from window_manager import WindowManager
from app import FaceAway

assert models_ready(), "Models not downloaded / SHA256 mismatch"
assert hasattr(cv2, "FaceDetectorYN")
assert hasattr(cv2, "FaceRecognizerSF")
detector = FaceEngine()
faces = detector.detect(np.zeros((480, 640, 3), dtype=np.uint8))
assert len(faces) == 0

original = b"DPAPI roundtrip test"
protected = win32crypt.CryptProtectData(original, "test", None, None, None, 0)
_, unprotected = win32crypt.CryptUnprotectData(protected, None, None, None, 0)
assert unprotected == original
manager = WindowManager()
assert manager.entries == []
assert manager.restore() == 0

qt = QApplication([])
window = FaceAway(start_worker=False)
assert window.armed is False
window.exit_program()
print("PASS: model load, blank-frame inference, DPAPI, Win32 manager, Qt window construction")
