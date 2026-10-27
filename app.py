"""FaceAway Windows MVP — smooth threaded camera preview and local face recognition."""
from __future__ import annotations

import json
import sys
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDoubleSpinBox, QHBoxLayout, QLabel, QMainWindow,
    QFrame, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QStyle, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from camera_worker import CameraWorker
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
        self.setWindowTitle("FaceAway · 人离开，桌面自动收起")
        self.resize(760, 780)
        self.setMinimumSize(560, 520)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #131822; color: #eff3fc; }
            QLabel { color: #eff3fc; }
            QPushButton { background: #34435b; border-radius: 7px; padding: 11px 14px; font-size: 14px; }
            QPushButton:hover { background: #475d79; }
            QPushButton:disabled { background: #26303e; color: #8692a6; }
            QDoubleSpinBox { background: #232e41; color: white; border: 1px solid #50617b; border-radius: 5px; padding: 5px; }
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
        self.gate = PresenceGate(
            away_seconds=float(settings.get("away_seconds", 3)),
            return_seconds=float(settings.get("return_seconds", 1)),
        )
        self._build_ui()
        self._build_tray()

        try:
            self.profile = load_embedding()
        except Exception as exc:
            QMessageBox.warning(self, "人脸资料读取失败",
                                f"人脸资料无法解密或已损坏：{exc}\n请重新拍照录入。")

        if not models_ready():
            self.set_status("缺少模型：请运行 setup.bat", "首次需要下载预训练人脸模型。")
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
            self.set_status("初始化摄像头与人脸模型…", "预览 15 FPS，识别每约 0.7 秒执行一次。")
        else:
            self.set_status("测试模式", "摄像头线程未启动。")
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
        subtitle = QLabel("只认你的一张脸 · 离开自动隐藏 · 返回自动恢复")
        subtitle.setStyleSheet("color: #a6b4c8; font-size: 13px;")
        root.addWidget(title)
        root.addWidget(subtitle)

        self.preview = QLabel("等待摄像头画面")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # A QLabel pixmap changes sizeHint() dynamically. Its former expanding
        # policy could make the next layout pass place text over the preview.
        self.preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.preview.setFixedHeight(270)
        self.preview.setScaledContents(False)
        self.preview.setStyleSheet("background: #080e19; color: #98a8ba; border: 1px solid #34405a; border-radius: 12px;")
        root.addWidget(self.preview)

        self.status = QLabel("初始化中…")
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
        self.enroll_btn = QPushButton("拍一张照片录入 / 重录")
        self.enroll_btn.clicked.connect(self.enroll)
        row.addWidget(self.enroll_btn)
        self.monitor_btn = QPushButton("开始监控")
        self.monitor_btn.clicked.connect(lambda: self.set_monitoring(not self.armed))
        row.addWidget(self.monitor_btn)
        root.addLayout(row)

        row2 = QHBoxLayout()
        self.restore_btn = QPushButton("立即恢复窗口")
        self.restore_btn.clicked.connect(self.restore_windows)
        row2.addWidget(self.restore_btn)
        self.tray_btn = QPushButton("收起到托盘")
        self.tray_btn.clicked.connect(self.hide)
        row2.addWidget(self.tray_btn)
        root.addLayout(row2)

        config = QHBoxLayout()
        config.addWidget(QLabel("离开判定 (秒)"))
        self.away_input = QDoubleSpinBox()
        self.away_input.setRange(1, 20)
        self.away_input.setSingleStep(0.5)
        self.away_input.setValue(self.gate.away_seconds)
        self.away_input.valueChanged.connect(self.save_settings)
        config.addWidget(self.away_input)
        config.addWidget(QLabel("回来判定 (秒)"))
        self.return_input = QDoubleSpinBox()
        self.return_input.setRange(0.5, 10)
        self.return_input.setSingleStep(0.5)
        self.return_input.setValue(self.gate.return_seconds)
        self.return_input.valueChanged.connect(self.save_settings)
        config.addWidget(self.return_input)
        root.addLayout(config)

        self.autostart_checkbox = QCheckBox("启动后自动开启监控（默认开启）")
        self.autostart_checkbox.setChecked(self.auto_monitor_on_startup)
        self.autostart_checkbox.toggled.connect(self.save_settings)
        root.addWidget(self.autostart_checkbox)

        note = QLabel("已经录入人脸时，启动后自动监控；也可随时通过托盘暂停。\n只在本机识别，不上传照片。普通摄像头人脸识别不能代替 Windows 锁屏。")
        note.setWordWrap(True)
        note.setStyleSheet("color: #778aa3; font-size: 11px;")
        root.addWidget(note)
        root.addStretch(1)

    def _build_tray(self):
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("FaceAway · 监控关闭")
        menu = QMenu()
        show_action = QAction("打开设置", self)
        show_action.triggered.connect(self.open_window)
        menu.addAction(show_action)
        self.monitor_action = QAction("开始监控", self)
        self.monitor_action.setCheckable(True)
        self.monitor_action.triggered.connect(self.set_monitoring)
        menu.addAction(self.monitor_action)
        restore_action = QAction("立即恢复所有已收起窗口", self)
        restore_action.triggered.connect(self.restore_windows)
        menu.addAction(restore_action)
        menu.addSeparator()
        quit_action = QAction("退出 FaceAway（同时恢复窗口）", self)
        quit_action.triggered.connect(self.exit_program)
        menu.addAction(quit_action)
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

    def set_status(self, main, detail=""):
        self.status.setText(main)
        self.detail.setText(detail)

    def refresh_controls(self):
        ready = self.worker_ready and self.worker is not None
        self.enroll_btn.setEnabled(ready)
        self.monitor_btn.setEnabled(ready and (self.profile is not None or self.armed))
        self.monitor_btn.setText("停止监控" if self.armed else "开始监控")
        self.monitor_action.setEnabled(ready and (self.profile is not None or self.armed))
        self.monitor_action.setChecked(self.armed)
        self.monitor_action.setText("停止监控" if self.armed else "开始监控")
        self.tray.setToolTip("FaceAway · " + ("监控中" if self.armed else "监控关闭"))

    def save_settings(self, _value=None):
        self.gate.away_seconds = self.away_input.value()
        self.gate.return_seconds = self.return_input.value()
        try:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(json.dumps({
                "away_seconds": self.gate.away_seconds,
                "return_seconds": self.gate.return_seconds,
                "auto_monitor_on_startup": self.autostart_checkbox.isChecked(),
            }, indent=2), encoding="utf-8")
        except OSError:
            pass

    def on_ready(self):
        self.worker_ready = True
        if self.profile is not None and self.autostart_checkbox.isChecked():
            self.set_monitoring(True)
            self.set_status("启动成功 · 已自动开启监控", "后台识别人脸中；可通过按钮或托盘菜单暂停。")
        elif self.profile is not None:
            self.set_status("已录入人脸 · 监控尚未开启", "自动监控已在设置中关闭，可手动开始。")
        else:
            self.set_status("准备就绪 · 请拍一张正面照片", "只存加密的人脸特征，不保存照片。")
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
                desc = f"本人 ({score:.2f})" if owner and score is not None else "未确认本人"
                self.set_status("已录入 · 监控关闭", "当前识别：" + desc)
            return

        action = self.gate.observe(owner, time.monotonic())
        if action == "hide":
            self.was_visible = self.isVisible()
            count = self.windows.minimize_all()
            self.set_status(f"人已离开 · 已最小化 {count} 个窗口", "返回并重新识别本人后恢复。")
            if self.was_visible:
                self.hide()
        elif action == "restore":
            count = self.windows.restore()
            self.set_status(f"欢迎回来 · 恢复 {count} 个窗口", "监控仍然开启。")
            if self.was_visible:
                self.open_window()
            self.was_visible = False
        elif not self.gate.hidden:
            detail = f"相似度 {score:.2f}" if score is not None else ("多人出现在镜头中" if face_count > 1 else "离开超时后自动最小化")
            self.set_status("监控中 · " + ("已识别本人" if owner else "暂未识别本人"), detail)

    def enroll(self):
        if self.worker is None or not self.worker_ready:
            QMessageBox.warning(self, "无法拍照", "请先确认模型与摄像头已就绪。")
            return
        if self.armed:
            self.set_monitoring(False)
        self.enroll_btn.setEnabled(False)
        self.set_status("正在采集一张照片…", "请正对摄像头，镜头中只保留一张人脸。")
        self.worker.request_enrollment()

    def on_enrolled(self, template):
        try:
            save_embedding(template)
            self.profile = template
            self.worker.set_profile(template)
            if self.autostart_checkbox.isChecked() and self.worker_ready:
                self.set_monitoring(True)
                self.set_status("录入成功 · 已自动开启监控",
                                "只保存 Windows DPAPI 加密的人脸特征；可通过托盘暂停。")
            else:
                self.set_status("录入成功", "人脸特征已保存。点击“开始监控”即可使用。")
        except Exception as exc:
            QMessageBox.warning(self, "录入失败", str(exc))
        self.refresh_controls()

    def on_enrollment_failed(self, error: str):
        self.refresh_controls()
        self.set_status("拍照未成功，请重试", error)
        QMessageBox.information(self, "请重新拍照", error)

    def on_camera_lost(self, message: str):
        if self.armed:
            self.set_monitoring(False)
            self.set_status("摄像头中断：监控已停止，窗口已恢复", message)
        elif self.isVisible():
            self.set_status("等待摄像头", message)

    def on_worker_error(self, message: str):
        if self.armed:
            self.set_monitoring(False)
        self.worker_ready = False
        self.refresh_controls()
        self.set_status("摄像头线程已停止", message)

    def set_monitoring(self, enabled: bool):
        if enabled and (not self.worker_ready or self.profile is None):
            QMessageBox.warning(self, "未准备好", "请先等待模型加载并拍照录入。")
            self.refresh_controls()
            return
        self.armed = bool(enabled)
        self.gate.reset()
        if self.worker is not None:
            self.worker.set_armed(self.armed)
        if not self.armed:
            self.restore_windows()
            self.set_status("监控已暂停", "所有由本程序最小化的窗口已尝试恢复。")
        else:
            self.set_status("监控已开始", "离开及返回判定时间可在下方调整。")
        self.refresh_controls()

    def restore_windows(self):
        count = self.windows.restore()
        self.gate.reset()
        if self.was_visible:
            self.open_window()
        self.was_visible = False
        self.set_status(f"已尝试恢复 {count} 个窗口", "如果监控仍开启，再次离开时会重新隐藏。")

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
