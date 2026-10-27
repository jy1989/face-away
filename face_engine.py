"""YuNet detection + SFace single-photo enrollment. No training required."""
from pathlib import Path

import cv2
import numpy as np

from models import DETECTOR_FILE, RECOGNIZER_FILE


class FaceEngine:
    def __init__(self):
        detector_path = str(Path(__file__).parent / "models" / DETECTOR_FILE)
        recognizer_path = str(Path(__file__).parent / "models" / RECOGNIZER_FILE)
        self.detector = cv2.FaceDetectorYN.create(
            detector_path, "", (640, 480), 0.82, 0.3, 30)
        self.recognizer = cv2.FaceRecognizerSF.create(recognizer_path, "")

    def detect(self, bgr: np.ndarray) -> list[np.ndarray]:
        height, width = bgr.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(bgr)
        if faces is None:
            return []
        return [face for face in faces if face[2] >= 65 and face[3] >= 65]

    def embedding(self, bgr: np.ndarray, face: np.ndarray) -> np.ndarray:
        aligned = self.recognizer.alignCrop(bgr, face)
        feature = self.recognizer.feature(aligned).astype(np.float32).ravel()
        norm = float(np.linalg.norm(feature))
        if norm < 1e-6 or not np.isfinite(norm):
            raise ValueError("Invalid face features")
        return feature / norm

    @staticmethod
    def similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))
