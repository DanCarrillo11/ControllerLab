# Third-party runtime components

Controller Lab's own application code uses the MIT
license in `LICENSE`. The portable build also contains separately licensed components:

- Python: PSF license, <https://www.python.org/psf/license/>.
- PySide6 Essentials / Shiboken6 / Qt: LGPL/GPL/commercial options. This project
  uses the open-source distributions; upstream license texts are copied from the
  installed wheels into `third_party/`, alongside the upstream open-source license
  texts in `third_party/Qt-open-source`. Sources and project information:
  <https://code.qt.io/cgit/pyside/pyside-setup.git/> and <https://code.qt.io/cgit/qt/>.
- pygame-ce: LGPL 2.1; SDL2 and the other bundled libraries retain their individual
  upstream licenses. The upstream 2.5.8 license collection is preserved in
  `third_party/pygame-ce-upstream/`, alongside the LGPL 2.1 text.
  Sources: <https://github.com/pygame-community/pygame-ce> and
  <https://github.com/libsdl-org/SDL>.
- PyInstaller bootloader: GPL with the upstream exception permitting distribution
  of bundled applications. <https://pyinstaller.org/en/stable/license.html>.

Runtime DLLs remain separate files in `_internal`; they are not statically linked
into the application. System fallback fonts are read from Windows and are not redistributed.
Brand names identify controller families; no manufacturer affiliation is implied.

## Bundled interface fonts

Plus Jakarta Sans (The Plus Jakarta Sans Project Authors) and JetBrains Mono
(The JetBrains Mono Project Authors) are distributed under the SIL Open Font
License 1.1. Their unchanged variable fonts, full license texts, source URLs and
SHA-256 checksums are included in `assets/fonts/`. They are loaded locally; the
desktop interface does not contact Google Fonts or a CDN. See the bundled OFL
files for the exact upstream copyright notices and reserved font names.

## Optional virtual output

Optional virtual output uses vgamepad 0.2.0 (MIT, Yann Bouteiller) and its bundled
ViGEmClient user-space DLL (MIT, Benjamin Höglinger-Stelzer). License texts are
included under third_party/vgamepad and third_party/ViGEmClient-LICENSE.txt.
ViGEmBus and HidHide kernel drivers are separate prerequisites; their installers
are not distributed or launched by Controller Lab.

## Community vector controller overlays

The PlayStation SVGs are adapted from daidr/dualsense-tester (MIT, copyright
2023 Xuezhou Dai). The Switch SVG is adapted from
AL2009man's Gamepad Asset Pack, originally made for VSCView (MIT, copyright
2024 Al. Lopez). The Xbox, generic-standard and GameCube SVGs are adapted from
datkat21/ControllerOverlays and remain GPL-3.0. The GameCube lettering is taken
from the Nintendo GameCube Official Logo uploaded by JustDanPatrick to Wikimedia
Commons, listed there as a public domain text logo (PD-textlogo). Only the two-line
wordmark is used; its source and attribution are included with the artwork.
The Wii Remote is adapted from Alexanderpas's Wiimote
1 Player Icon and remains CC-BY-SA-3.0; individual 1/2 controls and labels were added.

Original and adapted SVG source files, complete artwork licenses, exact revisions,
checksums and modification notes are bundled in assets/overlays. See
assets/overlays/CREDITS.md and assets/overlays/sources.json. The app's renderer
and input code are separate from these artwork resources and retain their own
MIT license. No manufacturer photographs are included in the current package.
