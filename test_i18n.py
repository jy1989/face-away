"""Language auto-detection, immediate switching, persistence, and UI regression."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

import app
from i18n import MESSAGES, resolve_language


class LanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def make_window(self, system="zh-CN", pref="auto"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        filepath = folder / "settings.json"
        filepath.write_text(json.dumps({"language": pref, "auto_monitor_on_startup": False}), encoding="utf-8")
        patches = [
            patch.object(app, "PROFILE_DIR", folder),
            patch.object(app, "SETTINGS_FILE", filepath),
            patch.object(app, "load_embedding", return_value=None),
            patch("app.resolve_language", side_effect=lambda preference: resolve_language(preference,[system])),
        ]
        for p in patches: p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(patches)])
        ui = app.FaceAway(start_worker=False)
        def cleanup():
            ui.exiting = True
            ui.tray.hide()
            ui.close()
            ui.deleteLater()
            QApplication.processEvents()
        self.addCleanup(cleanup)
        return ui, filepath

    def test_system_detection(self):
        for identifier in ("zh-CN", "zh-TW", "zh-HK", "zh_Hans_CN", "zh-Hant"):
            self.assertEqual(resolve_language("auto",[identifier]),"zh")
        for identifier in ("en-US", "de-DE", "ja-JP", "ko-KR", "fr-FR", "es-ES"):
            self.assertEqual(resolve_language("auto",[identifier]),"en")
        self.assertEqual(resolve_language("zh",["de-DE"]),"zh")
        self.assertEqual(resolve_language("en",["zh-CN"]),"en")
        self.assertEqual(resolve_language("unknown",["zh-CN"]),"zh")

    def test_windows_ui_language_api(self):
        from unittest.mock import patch
        for langid, expected in ((0x0804, "zh"), (0x0404, "zh"),
                                 (0x0409, "en"), (0x0407, "en")):
            with patch("i18n.ctypes.windll.kernel32.GetUserDefaultUILanguage",
                       return_value=langid):
                self.assertEqual(resolve_language("auto"), expected)

    def test_complete_dictionaries(self):
        self.assertEqual(set(MESSAGES["zh"]),set(MESSAGES["en"]))
        for key in MESSAGES["zh"]:
            self.assertTrue(MESSAGES["zh"][key], key)
            self.assertTrue(MESSAGES["en"][key], key)

    def test_chinese_system_default(self):
        ui, _ = self.make_window("zh-CN")
        self.assertEqual(ui.language, "zh")
        self.assertEqual(ui.language_combo.currentData(), "auto")
        self.assertIn("离开", ui.windowTitle())
        self.assertIn("收起到托盘", ui.tray_btn.text())

    def test_non_chinese_system_default(self):
        ui, _ = self.make_window("de-DE")
        self.assertEqual(ui.language, "en")
        self.assertIn("step away", ui.windowTitle())
        self.assertEqual(ui.monitor_btn.text(), "Start Monitoring")
        self.assertIn("Monitoring Off",ui.tray.toolTip())

    def test_manual_switch_updates_live_ui_and_status(self):
        ui, path = self.make_window("zh-CN")
        ui.set_status("status.hidden","detail.hidden",count=3)
        ui.armed=True
        ui.refresh_controls()
        ui.language_combo.setCurrentIndex(ui.language_combo.findData("en"))
        self.assertTrue(ui.armed)
        self.assertEqual(ui.language,"en")
        self.assertIn("Minimized 3 windows", ui.status.text())
        self.assertEqual(ui.monitor_btn.text(), "Pause Monitoring")
        self.assertIn("Monitoring",ui.tray.toolTip())
        self.assertEqual(ui.open_action.text(),"Open Settings")
        self.assertIn("Return delay",ui.return_label.text())
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["language"],"en")
        ui.language_combo.setCurrentIndex(ui.language_combo.findData("zh"))
        self.assertEqual(ui.language,"zh")
        self.assertIn("3 个窗口",ui.status.text())
        self.assertEqual(ui.monitor_btn.text(),"停止监控")
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["language"],"zh")

    def test_preference_persists_after_restart(self):
        ui, path = self.make_window("zh-CN")
        ui.language_combo.setCurrentIndex(ui.language_combo.findData("en"))
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["language"],"en")
        with patch.object(app, "load_settings", return_value=json.loads(path.read_text(encoding="utf-8"))):
            restarted = app.FaceAway(start_worker=False)
            self.assertEqual(restarted.language,"en")
            self.assertEqual(restarted.language_combo.currentData(),"en")
            restarted.exiting = True
            restarted.tray.hide()
            restarted.close()
            restarted.deleteLater()
            QApplication.processEvents()


if __name__ == "__main__":
    unittest.main()
