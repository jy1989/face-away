"""Dedicated capture/inference thread: ~15 FPS preview, ~1.4 Hz face recognition.

All OpenCV camera and inference operations live on this thread. The UI thread
receives copied QImages and small immutable presence signals only.
"""
from __future__ import annotations

import threading
import time

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from face_engine import FaceEngine


class CameraWorker(QThread):
    ready = Signal()
    preview_ready = Signal(QImage)
    presence_ready = Signal(bool, object, int)
    enrolled = Signal(object)
    enrollment_failed = Signal(str)
    camera_lost = Signal(str)
    fatal = Signal(str)

    FRAME_INTERVAL = 1.0 / 15.0
    INFERENCE_INTERVAL = 0.70
    RETRY_INTERVAL = 5.0

    def __init__(self, profile=None, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._visible = False
        self._armed = False
        self._enroll_requested = False
        self._profile = profile

    def set_visible(self, value: bool) -> None:
        with self._lock:
            self._visible = bool(value)

    def set_armed(self, value: bool) -> None:
        with self._lock:
            self._armed = bool(value)

    def set_profile(self, profile) -> None:
        with self._lock:
            self._profile = profile

    def request_enrollment(self) -> None:
        with self._lock:
            self._enroll_requested = True

    def stop(self) -> None:
        self._stop.set()

    def _open_camera(self):
        for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
            camera = cv2.VideoCapture(0, backend)
            if camera.isOpened():
                camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                return camera
            camera.release()
        return None

    def run(self) -> None:
        camera = None
        last_retry = -self.RETRY_INTERVAL
        last_inference = -self.INFERENCE_INTERVAL
        last_faces = []
        last_owner = False
        notified_missing = False
        try:
            cv2.setNumThreads(2)
            engine = FaceEngine()
            self.ready.emit()

            while not self._stop.is_set():
                with self._lock:
                    visible = self._visible
                    armed = self._armed
                    profile = self._profile
                    should_enroll = self._enroll_requested

                if not (visible or armed):
                    if camera is not None:
                        camera.release()
                        camera = None
                    self._stop.wait(0.10)
                    continue

                start = time.monotonic()
                if camera is None:
                    if start - last_retry < self.RETRY_INTERVAL:
                        self._stop.wait(0.15)
                        continue
                    last_retry = start
                    camera = self._open_camera()
                    if camera is None:
                        if not notified_missing:
                            self.camera_lost.emit("camera_unavailable")
                            notified_missing = True
                        self._stop.wait(0.15)
                        continue

                ok, frame = camera.read()
                if not ok or frame is None:
                    camera.release()
                    camera = None
                    last_retry = time.monotonic()
                    if not notified_missing:
                        self.camera_lost.emit("camera_interrupted")
                        notified_missing = True
                    continue
                notified_missing = False

                # Detect/enroll in the worker. No expensive OpenCV call on the UI thread.
                if should_enroll:
                    with self._lock:
                        self._enroll_requested = False
                    try:
                        faces = engine.detect(frame)
                        if len(faces) != 1:
                            self.enrollment_failed.emit("single_face_required")
                        else:
                            self.enrolled.emit(engine.embedding(frame, faces[0]))
                    except Exception as exc:
                        self.enrollment_failed.emit(str(exc))

                if start - last_inference >= self.INFERENCE_INTERVAL:
                    last_inference = start
                    faces = engine.detect(frame)
                    last_faces = faces
                    last_owner = False
                    score = None
                    if len(faces) == 1 and profile is not None:
                        score = engine.similarity(engine.embedding(frame, faces[0]), profile)
                        last_owner = score >= 0.42
                    # UI handles the debounce/window state changes.
                    self.presence_ready.emit(last_owner, score, len(faces))

                if visible:
                    for face in last_faces:
                        x, y, w, h = [int(v) for v in face[:4]]
                        cv2.rectangle(frame, (x, y), (x + w, y + h),
                                      (0, 190, 100) if last_owner else (60, 175, 255), 2)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    height, width = rgb.shape[:2]
                    image = QImage(rgb.data, width, height, rgb.strides[0],
                                   QImage.Format.Format_RGB888).copy()
                    self.preview_ready.emit(image)

                self._stop.wait(max(0.0, self.FRAME_INTERVAL - (time.monotonic() - start)))
        except Exception as exc:
            if not self._stop.is_set():
                self.fatal.emit(str(exc))
        finally:
            if camera is not None:
                camera.release()
