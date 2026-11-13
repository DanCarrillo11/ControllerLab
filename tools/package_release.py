"""Package the verified directory without installing drivers or overwriting releases."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from controller_lab import VERSION

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, default=ROOT / "dist" / "ControllerLab")
parser.add_argument("--output", type=Path, default=ROOT / "outputs")
parser.add_argument("--test-summary", type=Path)
parser.add_argument("--verification", type=Path)
parser.add_argument("--virtual-check", type=Path)
parser.add_argument("--desktop-check", type=Path)
args = parser.parse_args()
name = "ControllerLab-" + VERSION + "-Portable"
portable = args.output / name
archive = args.output / (name + ".zip")
if portable.exists() or archive.exists():
    raise SystemExit("A package already exists at this destination. Choose another output directory.")
if not (args.source / "ControllerLab.exe").is_file():
    raise SystemExit("Build the Windows executable first.")
def read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else None
tests, checks, virtual = read(args.test_summary), read(args.verification), read(args.virtual_check)
desktop = read(args.desktop_check)
if tests is not None and tests.get("passed") is not True:
    raise SystemExit("The supplied test results did not pass.")
if checks is not None and checks.get("frozen_gui") != "passed":
    raise SystemExit("The supplied packaged GUI check did not pass.")
args.output.mkdir(parents=True, exist_ok=True)
shutil.copytree(args.source, portable)
for filename in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
    shutil.copyfile(ROOT / filename, portable / filename)
shutil.copytree(ROOT / "docs", portable / "docs")
documentation_images = portable / "assets" / "screenshots"
documentation_images.mkdir(parents=True, exist_ok=True)
shutil.copyfile(ROOT / "assets" / "screenshots" / "new-profile.png", documentation_images / "new-profile.png")
(portable / "START_HERE.txt").write_text(f'''Controller Lab {VERSION} - Release candidate

Run ControllerLab.exe. Keep _internal beside it. No Python or installation is needed.

Device lab > Overview: inspect the controller and optionally open Vibration.
Guided test: follow buttons, sticks, triggers, center and optional vibration; save the report.
Sessions: search, rename, delete/restore, compare and export PNG, HTML, JSON or CSV.
Controller summary > Active profile: select a preset directly.
Active profile > New profile, or + beside its title: name and copy the current configuration.
Creating activates the copy. Save adjustments to profile after editing emulation settings.
Controller options > Manage profiles: save alternative mappings and virtual-output settings.
Controller options > Map inputs: use Listen to capture raw controls, review and Save.
Settings > Help: compatibility, diagnostics and setup assistance.
Help > Setup assistant: connect, map and optionally check neutral virtual outputs.
Game profiles in the sidebar: associate a game's .exe with a controller preset.
Settings > General: tray behavior and the global stop shortcut.
Default stop shortcut: Ctrl+Alt+F11. Conflicts are shown in Settings > General.
Emulation > Advanced adjustments: expand tuning, inversions and output remapping.
Stop emulation stays available beside the page title while output is active.
Tray menu: open the app, stop emulation or Quit Controller Lab.

Emulation: choose Xbox 360 or DualShock 4, map the physical input and press Start.
Keep this app open or minimized. Output stops on disconnect, profile change or exit.
ViGEmBus must be working in Windows. Presence of its service does not prove readiness.
The app does not install drivers or enable HidHide. See docs/EMULATION.md for setup,
double-input prevention and the current hardware verification limits.

Settings/reports: %LOCALAPPDATA%\\ControllerLab
Game rules temporarily select a profile while the configured game is running.
The manual profile returns when it closes. Switching profiles stops output; start it manually.
Game detection and close/minimize-to-tray are opt-in. Closing normally exits.
Identical controllers can share a model GUID. Settings never start emulation automatically.
Community artwork credits and source files are in _internal/assets/overlays/.

This candidate needs wider physical controller and game validation before a stable 1.0.
''', encoding="utf-8")
try:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
except (OSError, subprocess.CalledProcessError):
    commit = None
info = {"application": "Controller Lab", "version": VERSION, "channel": "release-candidate", "source_commit": commit,
        "tests": tests, "packaged_verification": checks, "virtual_output_check": virtual,
        "desktop_integration_check": desktop,
        "automatic_vibration_requested": False, "driver_installers_included": False}
(portable / "BUILD_INFO.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as package:
    for file in sorted(portable.rglob("*")):
        if file.is_file():
            package.write(file, file.relative_to(portable.parent))
with zipfile.ZipFile(archive) as package:
    bad = package.testzip()
    if bad:
        raise RuntimeError("Archive integrity failed: " + bad)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
Path(str(archive) + ".sha256").write_text(digest + "  " + archive.name + "\n", encoding="ascii")
print(json.dumps({"executable": str((portable / "ControllerLab.exe").resolve()), "archive": str(archive.resolve()),
                  "sha256": digest, "zip_crc": "passed"}, indent=2))
