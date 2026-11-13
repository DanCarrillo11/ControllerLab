"""Build transparent PNG and Windows ICO assets from the controller cutout."""
from pathlib import Path
import struct

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter


root = Path(__file__).resolve().parents[1] / "assets"
source = QImage(str(root / "branding" / "controller-cutout.png"))
if source.isNull() or not source.hasAlphaChannel() or source.pixelColor(0, 0).alpha() != 0:
    raise SystemExit("The controller cutout must be a readable PNG with a transparent background.")

sizes = (16, 24, 32, 48, 64, 128, 256)
entries, data = [], []
offset = 6 + 16 * len(sizes)
for size in sizes:
    scaled = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.drawImage((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise OSError(f"Could not encode icon size {size}.")
    png = bytes(buffer.data())
    dimension = size if size < 256 else 0
    entries.append(struct.pack('<BBBBHHII', dimension, dimension, 0, 0, 1, 32, len(png), offset))
    data.append(png)
    offset += len(png)
    if size == 256:
        # The same photograph works in both existing README image slots.
        (root / "app.png").write_bytes(png)
        (root / "app-dark.png").write_bytes(png)
(root / "app.ico").write_bytes(struct.pack('<HHH', 0, 1, len(sizes)) + b''.join(entries) + b''.join(data))
print("Built transparent controller PNGs and seven Windows icon sizes.")
