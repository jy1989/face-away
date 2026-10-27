"""Offscreen UI layout regression checks for camera preview and controls."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QScrollArea

from app import FaceAway

qt = QApplication([])
ui = FaceAway(start_worker=False)
ui.show()
qt.processEvents()

def verify(size):
    ui.resize(*size)
    qt.processEvents()
    scroll = ui.centralWidget()
    assert isinstance(scroll, QScrollArea)
    # Camera image should never resize the QLabel's layout geometry.
    first = ui.preview.geometry()
    ui.on_preview(QImage(640, 480, QImage.Format.Format_RGB888))
    qt.processEvents()
    preview = ui.preview.geometry()
    status = ui.status_card.geometry()
    assert preview.height() == 270, (size, preview)
    assert preview.bottom() < status.top(), (size, preview, status)
    assert ui.preview.parentWidget() is ui.status_card.parentWidget()
    assert preview.height() == first.height()
    assert ui.monitor_btn.geometry().height() >= 30
    print(f"PASS {size}: preview={preview.getRect()}, status={status.getRect()}, scroll={scroll.verticalScrollBar().isVisible()}")

for size in [(760, 780), (620, 630), (560, 520)]:
    verify(size)

ui.exiting = True
ui.tray.hide()
ui.close()
qt.quit()
