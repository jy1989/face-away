"""Windows DPAPI protected embedding. Never store camera frames or portraits."""
import os
from pathlib import Path

import numpy as np
import win32crypt

PROFILE_DIR = Path(os.getenv("LOCALAPPDATA") or str(Path.home())) / "FaceAway"
PROFILE_FILE = PROFILE_DIR / "face.dat"


def save_embedding(value: np.ndarray) -> None:
    arr = np.asarray(value, dtype=np.float32).ravel()
    if arr.size != 128 or not np.isfinite(arr).all():
        raise ValueError("Invalid face template")
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    encrypted = win32crypt.CryptProtectData(arr.tobytes(), "FaceAway SFace embedding", None, None, None, 0)
    tmp = PROFILE_FILE.with_suffix(".tmp")
    tmp.write_bytes(encrypted)
    tmp.replace(PROFILE_FILE)


def load_embedding() -> np.ndarray | None:
    if not PROFILE_FILE.is_file():
        return None
    _, raw = win32crypt.CryptUnprotectData(PROFILE_FILE.read_bytes(), None, None, None, 0)
    arr = np.frombuffer(raw, dtype=np.float32).copy()
    if arr.size != 128 or not np.isfinite(arr).all():
        raise ValueError("Corrupted face template")
    norm = float(np.linalg.norm(arr))
    if norm < 1e-6:
        raise ValueError("Invalid face template")
    return arr / norm
