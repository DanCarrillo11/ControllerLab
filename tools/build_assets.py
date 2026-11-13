"""Render the chosen joystick's vector artwork into transparent PNG/ICO assets."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import struct
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QBuffer, QIODevice, Qt, QByteArray, QRectF
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

app = QApplication([])
root = Path(__file__).resolve().parents[1] / "assets"
artwork = (root / "branding" / "joystick.svg").read_bytes()
source = QSvgRenderer(QByteArray(artwork))
if not source.isValid():
    raise SystemExit("The chosen joystick vector artwork is missing or unreadable.")

# Transparent native-vector rendering preserves the holes and the gap in the mark.
sizes = (16, 24, 32, 48, 64, 128, 256)
entries, data = [], []
offset = 6 + 16 * len(sizes)
for size in sizes:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    source.render(painter, QRectF(0, 0, size, size))
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not pix.save(buffer, "PNG"):
        raise OSError("Could not encode icon size " + str(size))
    png = bytes(buffer.data())
    entries.append(struct.pack('<BBBBHHII', size if size < 256 else 0, size if size < 256 else 0,
                               0, 0, 1, 32, len(png), offset))
    data.append(png)
    offset += len(png)
    if size == 256 and not pix.save(str(root / "app.png"), "PNG"):
        raise OSError("Could not save the application PNG.")
(root / "app.ico").write_bytes(struct.pack('<HHH', 0, 1, len(sizes)) + b''.join(entries) + b''.join(data))
dark = QSvgRenderer(QByteArray(artwork.replace(b'#ffffff', b'#171719')))
pix = QPixmap(256, 256)
pix.fill(Qt.GlobalColor.transparent)
painter = QPainter(pix)
painter.setRenderHint(QPainter.RenderHint.Antialiasing)
dark.render(painter, QRectF(0, 0, 256, 256))
painter.end()
if not pix.save(str(root / "app-dark.png"), "PNG"):
    raise OSError("Could not save the light-theme README logo.")
print("Built transparent joystick PNGs and seven Windows icon sizes.")
