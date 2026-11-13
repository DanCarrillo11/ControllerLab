"""Preserve license texts supplied by the exact installed runtime wheels."""
from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1] / "third_party"
for name in ("pygame-ce", "PySide6-Essentials", "shiboken6", "pyinstaller", "vgamepad"):
    dist = distribution(name)
    count = 0
    for file in dist.files:
        text = str(file).lower()
        if not any(token in text for token in ("license", "licence", "copying", "notice")):
            continue
        source = Path(dist.locate_file(file)).resolve()
        if source.is_file() and source.suffix.lower() not in (".pyc", ".pyd", ".dll"):
            destination = root / name / str(file).replace("..", "up")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            count += 1
    print(name, dist.version, count, "notice files")
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.is_file():
    shutil.copyfile(python_license, root / "Python-LICENSE.txt")
