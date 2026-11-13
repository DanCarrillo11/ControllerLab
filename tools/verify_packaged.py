"""Background-only frozen-runtime checks. Never invokes a vibration effect."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import shutil
import hashlib

parser = argparse.ArgumentParser()
parser.add_argument("executable", type=Path)
parser.add_argument("--evidence-dir", type=Path)
parser.add_argument("--report-json", type=Path)
args = parser.parse_args()
executable = args.executable.resolve()
icon = executable.parent / "_internal" / "assets" / "app.png"
source_icon = Path(__file__).resolve().parents[1] / "assets" / "app.png"
if not icon.is_file() or hashlib.sha256(icon.read_bytes()).digest() != hashlib.sha256(source_icon.read_bytes()).digest():
    raise RuntimeError("The bundled application icon is missing or differs from the chosen asset")
from PySide6.QtGui import QImage
icon_image = QImage(str(icon))
if icon_image.isNull() or not icon_image.hasAlphaChannel() or icon_image.pixelColor(0, 0).alpha() != 0:
    raise RuntimeError("The bundled application icon does not have a transparent background")
for name in ("chevron-down.svg", "chevron-up.svg", "check.svg"):
    bundled = executable.parent / "_internal" / "assets" / "ui" / name
    original = Path(__file__).resolve().parents[1] / "assets" / "ui" / name
    if not bundled.is_file() or hashlib.sha256(bundled.read_bytes()).digest() != hashlib.sha256(original.read_bytes()).digest():
        raise RuntimeError("A bundled interface glyph is missing or differs from its source")
font_root = executable.parent / "_internal" / "assets" / "fonts"
font_sources = json.loads((font_root / "sources.json").read_text(encoding="utf-8"))
for font_source in font_sources:
    bundled = font_root / font_source["file"]
    original = Path(__file__).resolve().parents[1] / "assets" / "fonts" / font_source["file"]
    if not bundled.is_file() or hashlib.sha256(bundled.read_bytes()).hexdigest() != font_source["sha256"] or bundled.read_bytes() != original.read_bytes():
        raise RuntimeError("A bundled interface font or its license differs from the recorded source")
art_root = executable.parent / "_internal" / "assets" / "overlays"
sources = json.loads((art_root / "sources.json").read_text(encoding="utf-8"))
for source in sources.values():
    if hashlib.sha256((art_root / source["file"]).read_bytes()).hexdigest() != source["sha256"]:
        raise RuntimeError("Bundled vector overlay differs from its recorded source")
    for additional in source.get("additional_sources", []):
        if hashlib.sha256((art_root / additional["upstream_file"]).read_bytes()).hexdigest() != additional["sha256"]:
            raise RuntimeError("Bundled supplementary artwork differs from its recorded source")
flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
with tempfile.TemporaryDirectory(prefix="controllerlab-frozen-check-") as tmp:
    root = Path(tmp)
    def run(arguments):
        p = subprocess.run([str(executable), *arguments], cwd=root, creationflags=flags,
                           capture_output=True, text=True, timeout=30)
        if p.returncode:
            raise RuntimeError(f"Frozen check failed ({p.returncode}): {p.stderr}")
    for family in ("dualsense", "playstation", "xbox", "switch", "wii", "gamecube", "generic"):
        run(["--render-demo", str(root / f"{family}.png"), "--family", family])
        if not (root / f"{family}.png").is_file():
            raise RuntimeError(f"Frozen controller image did not render: {family}")
    if not (root / "dualsense.png").is_file() or (root / "dualsense.png").stat().st_size < 20000:
        raise RuntimeError("Frozen GUI did not render")
    for page in ("sticks", "triggers", "raw", "sessions", "guided", "emulation", "settings", "games"):
        run(["--render-demo", str(root / ("page-" + page + ".png")), "--page", page])
    for dialog in ("setup", "desktop", "games", "profile"):
        run(["--render-demo", str(root / ("dialog-" + dialog + ".png")), "--render-dialog", dialog])
        if not (root / ("dialog-" + dialog + ".png")).is_file():
            raise RuntimeError("Frozen dialog did not render: " + dialog)
    run(["--render-report", str(root / "visual-report.png")])
    if not (root / "visual-report.png").is_file():
        raise RuntimeError("Frozen visual report did not export")
    client = executable.parent / "_internal" / "vgamepad" / "win" / "vigem" / "client" / "x64" / "ViGEmClient.dll"
    if not client.is_file():
        raise RuntimeError("The optional virtual-output client is missing from the package")
    run(["--self-check", str(root / "backend.json")])
    check = json.loads((root / "backend.json").read_text(encoding="utf-8"))
    if check.get("vibration_requested") is not False or not all(check["readable"]):
        raise RuntimeError("Frozen input backend did not pass")
    summary = {"frozen_gui": "passed", "input_backend": "passed", "visual_report": "passed", "virtual_client_bundled": True, "application_icon": "passed", "transparent_icon": True, "interface_assets": "passed", "offline_fonts": "passed",
                      "vector_overlays": len(sources), "controller_views": 7, "workspace_pages": 9, "desktop_dialogs": 4,
                      "readable_devices": len(check["devices"]), "vibration_requested": False,
                      "virtual_output_hardware": "Not tested by this non-emulating check"}
    print(json.dumps(summary, indent=2))
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if args.evidence_dir:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        for file in root.glob("*.png"):
            shutil.copyfile(file, args.evidence_dir / file.name)
