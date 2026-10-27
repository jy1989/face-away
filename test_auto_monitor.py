"""Regression tests for automatic monitoring on app launch.

No camera or real Win32 window operations are invoked.
"""
import os
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
import numpy as np
from PySide6.QtWidgets import QApplication

import app as face_app


class FakeWorker:
    def __init__(self):
        self.armed = None

    def set_armed(self, value):
        self.armed = value

    def set_profile(self, value):
        self.profile = value

    def set_visible(self, value):
        pass

    def stop(self):
        pass

    def wait(self, timeout):
        return True


class StartupMonitoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QApplication.instance() or QApplication([])

    def make_window(self, settings, enrolled=True):
        stack = []
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        profile_dir = Path(temp.name)
        p_settings = patch.object(face_app, "SETTINGS_FILE", profile_dir / "settings.json")
        p_profile_dir = patch.object(face_app, "PROFILE_DIR", profile_dir)
        p_load = patch.object(face_app, "load_settings", return_value=settings)
        p_template = patch.object(
            face_app, "load_embedding",
            return_value=np.ones(128, dtype=np.float32) if enrolled else None,
        )
        for mock in (p_settings, p_profile_dir, p_load, p_template):
            mock.start()
            stack.append(mock)
        self.addCleanup(lambda: [mock.stop() for mock in reversed(stack)])
        window = face_app.FaceAway(start_worker=False)
        window.worker = FakeWorker()
        self.addCleanup(self.cleanup_window, window)
        return window

    @staticmethod
    def cleanup_window(window):
        window.exiting = True
        window.armed = False
        window.worker = None
        window.tray.hide()
        window.close()
        window.deleteLater()
        QApplication.processEvents()

    def test_default_enabled_with_enrollment(self):
        window = self.make_window({})
        self.assertTrue(window.autostart_checkbox.isChecked())
        window.on_ready()
        self.assertTrue(window.armed)
        self.assertTrue(window.worker.armed)
        self.assertTrue(window.monitor_action.isChecked())

    def test_enrollment_starts_monitoring(self):
        window = self.make_window({}, enrolled=False)
        window.on_ready()
        template = np.ones(128, dtype=np.float32)
        with patch.object(face_app, "save_embedding"):
            window.on_enrolled(template)
        self.assertTrue(window.armed)
        self.assertTrue(window.worker.armed)
        np.testing.assert_array_equal(window.worker.profile, template)

    def test_disabled_preference_remains_off(self):
        window = self.make_window({"auto_monitor_on_startup": False})
        window.on_ready()
        self.assertFalse(window.armed)
        self.assertIsNone(window.worker.armed)
        self.assertFalse(window.monitor_action.isChecked())

    def test_without_enrollment_stays_off(self):
        window = self.make_window({}, enrolled=False)
        window.on_ready()
        self.assertFalse(window.armed)

    def test_preference_persists_after_toggle(self):
        window = self.make_window({})
        window.autostart_checkbox.setChecked(False)
        import json
        saved = json.loads(face_app.SETTINGS_FILE.read_text(encoding="utf-8"))
        self.assertFalse(saved["auto_monitor_on_startup"])


if __name__ == "__main__":
    unittest.main()
