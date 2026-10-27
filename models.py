"""Fetch integrity-verified OpenCV Zoo face models. curl supports resume."""
import hashlib
import subprocess
from pathlib import Path

DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
RECOGNIZER_FILE = "face_recognition_sface_2021dec.onnx"
ROOT = Path(__file__).parent / "models"
MODEL_BASE = "models"

FILES = {
    DETECTOR_FILE: (
        "face_detection_yunet",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    RECOGNIZER_FILE: (
        "face_recognition_sface",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
}


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def models_ready() -> bool:
    return all((ROOT / name).is_file() and checksum(ROOT / name) == sha
               for name, (_, sha) in FILES.items())


def download() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, (directory, expected_sha) in FILES.items():
        dest = ROOT / name
        if dest.exists() and checksum(dest) == expected_sha:
            print("OK:", name, flush=True)
            continue
        temp = ROOT / (name + ".part")
        suffix = f"{MODEL_BASE}/{directory}/{name}"
        urls = [
            f"https://hf-mirror.com/opencv/opencv_zoo/resolve/main/{suffix}",
            f"https://github.com/opencv/opencv_zoo/raw/main/{suffix}",
        ]
        for url in urls:
            print(f"Downloading {name} (resuming {temp.stat().st_size if temp.exists() else 0} bytes)", flush=True)
            result = subprocess.run([
                "curl.exe", "--fail", "--location", "--retry", "3",
                "--retry-delay", "2", "--connect-timeout", "12",
                "--continue-at", "-", "--output", str(temp), url,
            ], check=False)
            if result.returncode == 0 and temp.is_file() and checksum(temp) == expected_sha:
                temp.replace(dest)
                print("Verified:", name, flush=True)
                break
            if result.returncode == 0:
                temp.unlink(missing_ok=True)
                print("SHA256 mismatch; retrying another source", flush=True)
            else:
                print("Download failed; trying alternate host.", flush=True)
        else:
            raise RuntimeError(f"Could not download verified model: {name}. Run setup.bat again.")

if __name__ == "__main__":
    download()
