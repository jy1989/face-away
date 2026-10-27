"""Mock camera regression: preview ~15fps; detection ~1.4fps; GUI remains responsive."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import time
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from camera_worker import CameraWorker


class FakeVideoCapture:
    def __init__(self, *args):
        self.frames = 0
    def isOpened(self):
        return True
    def set(self, *args):
        return True
    def read(self):
        self.frames += 1
        return True, np.zeros((240, 320, 3), dtype=np.uint8)
    def release(self):
        pass


class FakeEngine:
    def detect(self, frame):
        return [np.array([20., 20., 100., 100., *([0.] * 11)], dtype=np.float32)]
    def similarity(self, a, b):
        return float(np.dot(a, b))
    def embedding(self, frame, face):
        return np.ones(128, dtype=np.float32) / np.sqrt(128)


qt = QApplication([])
worker = CameraWorker(np.ones(128, dtype=np.float32) / np.sqrt(128))
previews = []
detections = []
enrollments = []
worker.preview_ready.connect(lambda img: previews.append(time.monotonic()))
worker.presence_ready.connect(lambda owner, score, num: detections.append((owner, score, num)))
worker.enrolled.connect(lambda vec: enrollments.append(vec))
worker.set_visible(True)
worker.set_armed(True)
start = time.monotonic()
with patch("camera_worker.cv2.VideoCapture", FakeVideoCapture), patch("camera_worker.FaceEngine", FakeEngine):
    worker.start()
    QTimer.singleShot(350, worker.request_enrollment)
    QTimer.singleShot(1600, qt.quit)
    qt.exec()
    worker.stop()
    assert worker.wait(5000), "worker failed to shut down"
duration = time.monotonic() - start
assert len(previews) >= 11, f"preview too slow: {len(previews)} frames"
assert len(detections) in range(2, 6), f"unexpected recognition rate: {len(detections)} detections"
assert len(enrollments) == 1, f"single-shot enrollment failed: {len(enrollments)}"
assert all(owner and score > 0.99 for owner, score, count in detections)
print(f"PASS: {len(previews)} frames in {duration:.1f}s (~{len(previews)/duration:.1f} FPS), {len(detections)} inferences, 1 enrollment")
