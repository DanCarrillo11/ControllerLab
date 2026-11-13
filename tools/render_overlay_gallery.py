"""Export real Qt window/widget captures for all families, using simulated input."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import argparse
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication
from controller_lab.backend import DemoBackend
from controller_lab.controller_art import ControllerView
from controller_lab.ui import Window
from controller_lab.design import CANVAS, SURFACE
from controller_lab.theme import UI_FONT

FAMILIES = (("dualsense", "PS5 · DualSense"), ("playstation", "PS4 · DualShock 4"),
            ("xbox", "Xbox"), ("switch", "Nintendo Switch Pro"),
            ("gamecube", "Nintendo GameCube"), ("wii", "Nintendo Wii Remote"),
            ("generic", "Generic standard layout"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setStyle("Fusion")
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ("segoeui.ttf", "seguisb.ttf", "seguisym.ttf", "consola.ttf"):
        if (fonts / name).is_file():
            QFontDatabase.addApplicationFont(str(fonts / name))
    captures = []
    for family, title in FAMILIES:
        with tempfile.TemporaryDirectory(prefix="controllerlab-gallery-") as temp:
            backend = DemoBackend(family)
            window = Window(backend, temp, demo=True)
            window.timer.stop()
            window.scan_timer.stop()
            window.resize(1280, 840)
            sample = backend.poll(100)
            sample.axes = dict.fromkeys(sample.axes, 0.0)
            sample.buttons = dict.fromkeys(sample.buttons, False)
            sample.raw_axes = tuple(sample.axes.values())
            sample.raw_buttons = tuple(sample.buttons.values())
            window.sample = sample
            window.show()
            app.processEvents()
            window.draw_sample()
            app.processEvents()
            window.grab().save(str(args.output / (family + ".png")), "PNG")
            # Capture every thumbnail at its final pixel size: scaling a screenshot
            # afterwards would make the screen-pixel SVG strokes appear different.
            preview = ControllerView()
            preview.setStyleSheet(f"background-color: {SURFACE};")
            preview.resize(428, 388)
            preview.set_input(family, sample)
            preview.show()
            app.processEvents()
            capture = preview.grab().toImage()
            capture.save(str(args.output / (family + "-overlay.png")), "PNG")
            captures.append((family, title, capture))
            preview.close()
            preview.deleteLater()
            if family == "dualsense":
                write_symbol_detail(window, args.output / "playstation-symbols.png")
            window.close()
            window.deleteLater()
            app.processEvents()
    sheet = QImage(1920, 1040, QImage.Format.Format_ARGB32)
    sheet.fill(QColor(CANVAS))
    painter = QPainter(sheet)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
    painter.setFont(QFont(UI_FONT, 19, QFont.Weight.DemiBold))
    painter.setPen(QColor("#f5f5f7"))
    painter.drawText(28, 42, "Controller Lab · Vector overlays")
    painter.setFont(QFont(UI_FONT, 10))
    painter.setPen(QColor("#9999a5"))
    painter.drawText(28, 69, "Actual application captures · Simulated input · All seven controller families")
    for index, (_, title, capture) in enumerate(captures):
        x, y = (index % 4) * 480 + 12, (index // 4) * 465 + 90
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(SURFACE))
        painter.drawRoundedRect(QRectF(x, y, 456, 445), 12, 12)
        painter.setFont(QFont(UI_FONT, 13, QFont.Weight.DemiBold))
        painter.setPen(QColor("#e1e8f2"))
        painter.drawText(QRectF(x + 14, y + 10, 428, 32), Qt.AlignmentFlag.AlignCenter, title)
        size = capture.size().scaled(428, 388, Qt.AspectRatioMode.KeepAspectRatio)
        painter.drawImage(QRectF(x + 14 + (428 - size.width()) / 2, y + 48 + (388 - size.height()) / 2,
                                size.width(), size.height()), capture)
    painter.setFont(QFont(UI_FONT, 13))
    painter.setPen(QColor("#9999a5"))
    painter.drawText(QRectF(1465, 600, 410, 190), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                     "Choose a model inside the app:\n\nController options → Controller overlay\n\nButtons, sticks and triggers\nrespond to the selected device.")
    painter.end()
    sheet.save(str(args.output / "all-overlays.png"), "PNG")
    print("Saved seven full application screenshots, seven overlay captures, a symbol detail and the overview.")


def write_symbol_detail(window, output):
    model = window.view.model()
    image = QImage(1024, 300, QImage.Format.Format_ARGB32)
    image.fill(QColor(SURFACE))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for index, (key, title) in enumerate((("x", "Square"), ("y", "Triangle"), ("b", "Circle"), ("a", "Cross"))):
        region = model.part_box(key).adjusted(-3, -3, 3, 3)
        target = QRectF(index * 256 + 42, 45, 172, 172)
        painter.save()
        painter.translate(target.topLeft())
        painter.scale(target.width() / region.width(), target.height() / region.height())
        painter.translate(-region.topLeft())
        painter.setClipRect(region)
        model.full.render(painter, model.viewbox)
        painter.restore()
        painter.setPen(QColor("#e1e8f2"))
        painter.setFont(QFont("Segoe UI", 12))
        painter.drawText(QRectF(index * 256, 240, 256, 32), Qt.AlignmentFlag.AlignCenter, title)
    painter.end()
    image.save(str(output), "PNG")


if __name__ == "__main__":
    main()
