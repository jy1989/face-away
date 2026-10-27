"""FaceAway Windows MVP — smooth threaded camera preview and local face recognition."""
from __future__ import annotations

import json
import sys
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QMainWindow,
    QFrame, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QStyle, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from camera_worker import CameraWorker
from i18n import resolve_language, translate
from models import models_ready
from presence import PresenceGate
from profile_store import PROFILE_DIR, load_embedding, save_embedding
from window_manager import WindowManager

SETTINGS_FILE = PROFILE_DIR / "settings.json"


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class FaceAway(QMainWindow):
    def __init__(self, start_worker: bool = True):
        super().__init__()
        self.setWindowTitle("FaceAway")
        self.resize(760, 780)
        self.setMinimumSize(560, 520)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #131822; color: #eff3fc; }
            QLabel { color: #eff3fc; }
            QPushButton { background: #34435b; border-radius: 7px; padding: 11px 14px; font-size: 14px; }
            QPushButton:hover { background: #475d79; }
            QPushButton:disabled { background: #26303e; color: #8692a6; }
            QDoubleSpinBox, QComboBox { background: #232e41; color: white; border: 1px solid #50617b; border-radius: 5px; padding: 6px; }\n            QComboBox QAbstractItemView { background: #232e41; color: white; selection-background-color: #475d79; }
        """)
        self.armed = False
        self.exiting = False
        self.was_visible = False
        self.profile = None
        self.worker = None
        self.worker_ready = False
        self.latest_image = None
        self.windows = WindowManager()
        settings = load_settings()
        self.auto_monitor_on_startup = bool(settings.get("auto_monitor_on_startup", True))
        self.language_preference = settings.get("language", "auto")
        if self.language_preference not in ("auto", "zh", "en"):
            self.language_preference = "auto"
        self.language = resolve_language(self.language_preference)
        self._status_state = ("initializing", None, {})
        self.gate = PresenceGate(
            away_seconds=float(settings.get("away_seconds", 3)),
            return_seconds=float(settings.get("return_seconds", 1)),
        )
        self._build_ui()
        self._build_tray()
        self.apply_language()

        try:
            self.profile = load_embedding()
        except Exception as exc:
            QMessageBox.warning(
                self, self.t("dialog_face_error"),
                self.t("dialog_face_error_detail", error=str(exc)),
            )

        if not models_ready():
            self.set_status("status.missing_models", "detail.missing_models")
        elif start_worker:
            self.worker = CameraWorker(self.profile, self)
            self.worker.ready.connect(self.on_ready)
            self.worker.preview_ready.connect(self.on_preview)
            self.worker.presence_ready.connect(self.on_presence)
            self.worker.enrolled.connect(self.on_enrolled)
            self.worker.enrollment_failed.connect(self.on_enrollment_failed)
            self.worker.camera_lost.connect(self.on_camera_lost)
            self.worker.fatal.connect(self.on_worker_error)
            self.worker.start()
            self.set_status("status.initializing", "detail.initializing")
        else:
            self.set_status("status.test_mode", "detail.test_mode")
        self.refresh_controls()

    def _build_ui(self):
        # Scrollable form prevents clipped controls at 125%-200% Windows DPI.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll)
        panel = QWidget()
        scroll.setWidget(panel)
        root = QVBoxLayout(panel)
        root.setSpacing(10)
        root.setContentsMargins(24, 22, 24, 22)

        title = QLabel("FaceAway")
        title.setStyleSheet("font-size: 29px; font-weight: 700; color: #b4d1ff;")
        self.subtitle = QLabel()
        self.subtitle.setStyleSheet("color: #a6b4c8; font-size: 13px;")
        root.addWidget(title)
        root.addWidget(self.subtitle)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # A QLabel pixmap changes sizeHint() dynamically. Its former expanding
        # policy could make the next layout pass place text over the preview.
        self.preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.preview.setFixedHeight(270)
        self.preview.setScaledContents(False)
        self.preview.setStyleSheet("background: #080e19; color: #98a8ba; border: 1px solid #34405a; border-radius: 12px;")
        root.addWidget(self.preview)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("font-size: 17px; font-weight: 600;")
        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("color: #9eafc7; font-size: 12px;")
        status_card = QFrame(panel)
        self.status_card = status_card
        status_card.setObjectName("statusCard")
        status_card.setStyleSheet("QFrame#statusCard { background: #1e2b3d; border: 1px solid #334963; border-radius: 10px; }")
        card_layout = QVBoxLayout(status_card)
        card_layout.setSpacing(5)
        card_layout.setContentsMargins(16, 11, 16, 11)
        card_layout.addWidget(self.status)
        card_layout.addWidget(self.detail)
        root.addWidget(status_card)

        row = QHBoxLayout()
        self.enroll_btn = QPushButton()
        self.enroll_btn.clicked.connect(self.enroll)
        row.addWidget(self.enroll_btn)
        self.monitor_btn = QPushButton()
        self.monitor_btn.clicked.connect(lambda: self.set_monitoring(not self.armed))
        row.addWidget(self.monitor_btn)
        root.addLayout(row)

        row2 = QHBoxLayout()
        self.restore_btn = QPushButton()
        self.restore_btn.clicked.connect(self.restore_windows)
        row2.addWidget(self.restore_btn)
        self.tray_btn = QPushButton()
        self.tray_btn.clicked.connect(self.hide)
        row2.addWidget(self.tray_btn)
        root.addLayout(row2)

        config = QHBoxLayout()
        self.away_label = QLabel()
        config.addWidget(self.away_label)
        self.away_input = QDoubleSpinBox()
        self.away_input.setRange(1, 20)
        self.away_input.setSingleStep(0.5)
        self.away_input.setValue(self.gate.away_seconds)
        self.away_input.valueChanged.connect(self.save_settings)
        config.addWidget(self.away_input)
        self.return_label = QLabel()
        config.addWidget(self.return_label)
        self.return_input = QDoubleSpinBox()
        self.return_input.setRange(0.5, 10)
        self.return_input.setSingleStep(0.5)
        self.return_input.setValue(self.gate.return_seconds)
        self.return_input.valueChanged.connect(self.save_settings)
        config.addWidget(self.return_input)
        root.addLayout(config)

        self.autostart_checkbox = QCheckBox()
        self.autostart_checkbox.setChecked(self.auto_monitor_on_startup)
        self.autostart_checkbox.toggled.connect(self.save_settings)
        root.addWidget(self.autostart_checkbox)

        language_row = QHBoxLayout()
        self.language_label = QLabel()
        self.language_combo = QComboBox()
        for key in ("auto", "zh", "en"):
            self.language_combo.addItem("", key)
        index = self.language_combo.findData(self.language_preference)
        self.language_combo.setCurrentIndex(max(0, index))
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)
        language_row.addWidget(self.language_label)
        language_row.addWidget(self.language_combo, 1)
        root.addLayout(language_row)

        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color: #778aa3; font-size: 11px;")
        root.addWidget(self.note)
        root.addStretch(1)

    def _build_tray(self):
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("FaceAway")
        menu = QMenu()
        self.open_action = QAction(self)
        self.open_action.triggered.connect(self.open_window)
        menu.addAction(self.open_action)
        self.monitor_action = QAction(self)
        self.monitor_action.setCheckable(True)
        self.monitor_action.triggered.connect(self.set_monitoring)
        menu.addAction(self.monitor_action)
        self.restore_action = QAction(self)
        self.restore_action.triggered.connect(self.restore_windows)
        menu.addAction(self.restore_action)
        menu.addSeparator()
        self.quit_action = QAction(self)
        self.quit_action.triggered.connect(self.exit_program)
        menu.addAction(self.quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_window()

    def open_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def showEvent(self, event):
        super().showEvent(event)
        if self.worker is not None:
            self.worker.set_visible(True)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.worker is not None:
            self.worker.set_visible(False)

    def t(self, key: str, **kwargs) -> str:
        return translate(self.language, key, **kwargs)

    def set_status(self, main_key: str, detail_key: str | None = None, **kwargs):
        # Store message identifiers so switching language also retranslates the
        # most recent status (even while monitoring is paused or hidden).
        self._status_state = (main_key, detail_key, kwargs)
        self.render_status()

    def render_status(self):
        key, detail_key, values = self._status_state
        self.status.setText(self.t(key, **values))
        if detail_key is None:
            self.detail.setText(str(values.get("detail_text", "")))
        else:
            self.detail.setText(self.t(detail_key, **values))

    def on_language_changed(self, _index):
        self.language_preference = self.language_combo.currentData()
        self.language = resolve_language(self.language_preference)
        self.apply_language()
        self.save_settings()

    def apply_language(self):
        self.setWindowTitle(self.t("window_title"))
        self.subtitle.setText(self.t("subtitle"))
        if self.preview.pixmap() is None:
            self.preview.setText(self.t("preview_waiting"))
        self.enroll_btn.setText(self.t("enroll_button"))
        self.restore_btn.setText(self.t("restore_button"))
        self.tray_btn.setText(self.t("tray_button"))
        self.away_label.setText(self.t("away_seconds"))
        self.return_label.setText(self.t("return_seconds"))
        self.autostart_checkbox.setText(self.t("auto_monitor"))
        self.language_label.setText(self.t("language"))
        for i, key in enumerate(("auto", "zh", "en")):
            self.language_combo.setItemText(i, self.t("language_" + key))
        self.note.setText(self.t("note"))
        self.open_action.setText(self.t("tray_open"))
        self.restore_action.setText(self.t("tray_restore"))
        self.quit_action.setText(self.t("tray_exit"))
        self.render_status()
        self.refresh_controls()

    def refresh_controls(self):
        ready = self.worker_ready and self.worker is not None
        self.enroll_btn.setEnabled(ready)
        self.monitor_btn.setEnabled(ready and (self.profile is not None or self.armed))
        self.monitor_btn.setText(self.t("stop_monitor" if self.armed else "start_monitor"))
        self.monitor_action.setEnabled(ready and (self.profile is not None or self.armed))
        self.monitor_action.setChecked(self.armed)
        self.monitor_action.setText(self.t("stop_monitor" if self.armed else "start_monitor"))
        self.tray.setToolTip("FaceAway · " + self.t("tray_active" if self.armed else "tray_inactive"))

    def save_settings(self, _value=None):
        self.gate.away_seconds = self.away_input.value()
        self.gate.return_seconds = self.return_input.value()
        try:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(json.dumps({
                "away_seconds": self.gate.away_seconds,
                "return_seconds": self.gate.return_seconds,
                "auto_monitor_on_startup": self.autostart_checkbox.isChecked(),
                "language": self.language_combo.currentData(),
            }, indent=2), encoding="utf-8")
        except OSError:
            pass

    def on_ready(self):
        self.worker_ready = True
        if self.profile is not None and self.autostart_checkbox.isChecked():
            self.set_monitoring(True)
            self.set_status("status.auto_started", "detail.auto_started")
        elif self.profile is not None:
            self.set_status("status.registered_inactive", "detail.registered_inactive")
        else:
            self.set_status("status.ready_enroll", "detail.ready_enroll")
        self.refresh_controls()

    def on_preview(self, image: QImage):
        # Conversion and painting stay on the GUI thread; ONNX inference does not.
        if not self.isVisible():
            return
        self.latest_image = image
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation))

    def on_presence(self, owner: bool, score, face_count: int):
        if not self.armed:
            if self.profile is not None:
                if owner and score is not None:
                    self.set_status("status.off_enrolled", "detail.off_owner", score=score)
                else:
                    self.set_status("status.off_enrolled", "detail.off_unknown")
            return

        action = self.gate.observe(owner, time.monotonic())
        if action == "hide":
            self.was_visible = self.isVisible()
            count = self.windows.minimize_all()
            self.set_status("status.hidden", "detail.hidden", count=count)
            if self.was_visible:
                self.hide()
        elif action == "restore":
            count = self.windows.restore()
            self.set_status("status.welcome", "detail.welcome", count=count)
            if self.was_visible:
                self.open_window()
            self.was_visible = False
        elif not self.gate.hidden:
            main_key = "status.monitoring_owner" if owner else "status.monitoring_unknown"
            if score is not None:
                self.set_status(main_key, "detail.similarity", score=score)
            else:
                detail_key = "detail.multi_faces" if face_count > 1 else "detail.away_hint"
                self.set_status(main_key, detail_key)

    def enroll(self):
        if self.worker is None or not self.worker_ready:
            QMessageBox.warning(self, self.t("dialog_camera_error"), self.t("dialog_camera_error_detail"))
            return
        if self.armed:
            self.set_monitoring(False)
        self.enroll_btn.setEnabled(False)
        self.set_status("status.enrolling", "detail.enrolling")
        self.worker.request_enrollment()

    def on_enrolled(self, template):
        try:
            save_embedding(template)
            self.profile = template
            self.worker.set_profile(template)
            if self.autostart_checkbox.isChecked() and self.worker_ready:
                self.set_monitoring(True)
                self.set_status("status.enroll_auto", "detail.enroll_auto")
            else:
                self.set_status("status.enroll_saved", "detail.enroll_saved")
        except Exception as exc:
            QMessageBox.warning(self, self.t("dialog_enroll_error"), str(exc))
        self.refresh_controls()

    def on_enrollment_failed(self, error: str):
        self.refresh_controls()
        key = "error." + error
        from i18n import MESSAGES
        if key in MESSAGES["en"]:
            self.set_status("status.enroll_failed", key)
        else:
            self.set_status("status.enroll_failed", detail_text=error)
        QMessageBox.information(self, self.t("dialog_retake"), self.translate_worker_error(error))

    def translate_worker_error(self, value: str) -> str:
        key = "error." + value
        from i18n import MESSAGES
        return self.t(key) if key in MESSAGES["en"] else value

    def on_camera_lost(self, message: str):
        if self.armed:
            self.set_monitoring(False)
            self.set_status("status.camera_lost", "error." + message)
        elif self.isVisible():
            self.set_status("status.camera_wait", "error." + message)

    def on_worker_error(self, message: str):
        if self.armed:
            self.set_monitoring(False)
        self.worker_ready = False
        self.refresh_controls()
        self.set_status("status.worker_stopped", detail_text=message)

    def set_monitoring(self, enabled: bool):
        if enabled and (not self.worker_ready or self.profile is None):
            QMessageBox.warning(self, self.t("dialog_unready"), self.t("dialog_unready_detail"))
            self.refresh_controls()
            return
        self.armed = bool(enabled)
        self.gate.reset()
        if self.worker is not None:
            self.worker.set_armed(self.armed)
        if not self.armed:
            self.restore_windows()
            self.set_status("status.monitor_paused", "detail.monitor_paused")
        else:
            self.set_status("status.monitor_started", "detail.monitor_started")
        self.refresh_controls()

    def restore_windows(self):
        count = self.windows.restore()
        self.gate.reset()
        if self.was_visible:
            self.open_window()
        self.was_visible = False
        self.set_status("status.manual_restored", "detail.manual_restored", count=count)

    def closeEvent(self, event):
        if not self.exiting and self.tray.isVisible():
            event.ignore()
            self.hide()
            return
        super().closeEvent(event)

    def exit_program(self):
        self.exiting = True
        self.armed = False
        self.gate.reset()
        self.windows.restore()
        if self.worker is not None:
            self.worker.set_armed(False)
            self.worker.set_visible(False)
            self.worker.stop()
            self.worker.wait(10000)
        self.tray.hide()
        QApplication.instance().quit()


def main():
    if sys.platform != "win32":
        raise SystemExit("This MVP supports Windows only.")
    if "--self-test" in sys.argv:
        # Safe packaged-build smoke test: no webcam, no window minimization.
        import os
        from pathlib import Path
        import tempfile
        from face_engine import FaceEngine
        import numpy as np
        log = Path(tempfile.gettempdir()) / "FaceAway-self-test.log"
        def checkpoint(stage):
            log.open("a", encoding="utf-8").write(stage + "\n")
        log.write_text("start\n", encoding="utf-8")
        checkpoint("checking bundled model hashes")
        assert models_ready(), "Bundled model weights missing or invalid"
        checkpoint("loading OpenCV inference")
        assert FaceEngine().detect(np.zeros((480, 640, 3), dtype=np.uint8)) == []
        checkpoint("passed inference")
        # Test the actual Windows Qt event loop (without webcam or monitoring).
        os.environ.pop("QT_QPA_PLATFORM", None)
        from PySide6.QtCore import QTimer
        checkpoint("creating QApplication")
        test_app = QApplication([])
        checkpoint("creating FaceAway window without webcam")
        test_window = FaceAway(start_worker=False)
        assert not test_window.armed
        checkpoint("running Qt event loop")
        QTimer.singleShot(300, test_window.exit_program)
        test_app.exec()
        checkpoint("passed")
        return
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = FaceAway()
    app.aboutToQuit.connect(window.windows.restore)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
