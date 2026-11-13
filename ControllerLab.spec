# Build the Windows portable application: pyinstaller --clean --noconfirm ControllerLab.spec
import os
from importlib.metadata import distribution

# Qt expects Windows' ICU exports. Build tools such as Poppler ship an unrelated
# icuuc.dll with the same filename; it must not be collected from PATH.
os.environ['PATH'] = os.pathsep.join(part for part in os.environ.get('PATH', '').split(os.pathsep)
                                   if 'poppler' not in part.lower())
a = Analysis(['app.py'], pathex=[], binaries=[],
             datas=[('LICENSE', '.'), ('THIRD_PARTY_NOTICES.md', '.'), ('third_party', 'third_party'),
                    ('assets/overlays', 'assets/overlays'), ('assets/app.png', 'assets'), ('assets/ui', 'assets/ui'),
                    ('assets/fonts', 'assets/fonts')] +
                   [(str(distribution('vgamepad').locate_file('vgamepad/win/vigem/client/x64/ViGEmClient.dll')),
                     'vgamepad/win/vigem/client/x64')],
             hiddenimports=['pygame._sdl2.controller', 'vgamepad', 'vgamepad.api',
                            'vgamepad.win.virtual_gamepad', 'vgamepad.win.vigem_client'],
             excludes=['tkinter', 'numpy', 'PySide6.QtNetwork', 'PySide6.QtQml',
                       'PySide6.QtQuick', 'PySide6.QtMultimedia'], noarchive=False)
# pygame's unused default font/artwork are not part of this application.
a.datas = [entry for entry in a.datas if not entry[0].endswith(('freesansbold.ttf', 'pygame_icon.bmp'))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ControllerLab',
          debug=False, strip=False, upx=False, console=False, icon='assets/app.ico', version='version_info.txt')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ControllerLab')
