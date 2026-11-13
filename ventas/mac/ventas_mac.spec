# -*- mode: python ; coding: utf-8 -*-
# CineCaptions Ventas · By Cinema Productions
# programa/mac/ventas_mac.spec — PyInstaller para macOS: «CineCaptions Ventas.app» (gemelo de «CineCaptions Ventas.spec»
# de Windows en lo que va dentro: ventas.py + fuentes/Inter.ttf). Lo arma mac/construir_ventas_mac.sh en una Mac de
# GitHub (PyInstaller no compila para Mac desde Windows). A mano, desde programa/:
#   python mac/icono_mac.py build/ventas.icns
#   python -m PyInstaller --noconfirm --distpath build/dist_mac --workpath build/work_mac mac/ventas_mac.spec
# La clave de administrador va en el Llavero (keyring): sus «backends» se cargan por entry points, por eso se copian sus
# metadatos y todos sus submódulos.
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

AQUI = Path(SPECPATH).parent          # programa/
NOMBRE = 'CineCaptions Ventas'

hallado = re.search(r"^VERSION = '(\d+(?:\.\d+){1,3})'", (AQUI / 'ventas.py').read_text(encoding='utf-8'), re.M)
if not hallado:
    raise SystemExit("No encontré VERSION = '...' en ventas.py")
VERSION = hallado.group(1)
ICONO = AQUI / 'build' / 'ventas.icns'
if not ICONO.is_file():
    raise SystemExit('Falta build/ventas.icns: corre primero «python mac/icono_mac.py build/ventas.icns»')

# Qt: la app solo usa QtCore, QtGui y QtWidgets
QT_SOBRA = ['PySide6.QtNetwork', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtWebEngineCore',
            'PySide6.QtWebEngineWidgets', 'PySide6.QtWebChannel', 'PySide6.Qt3DCore', 'PySide6.QtMultimedia',
            'PySide6.QtPdf', 'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtOpenGL', 'PySide6.QtSql',
            'PySide6.QtTest', 'PySide6.QtBluetooth', 'PySide6.QtPositioning', 'PySide6.QtLocation', 'PySide6.QtAsyncio']
PY_SOBRA = ['tkinter', '_tkinter', 'unittest', 'doctest', 'pydoc', 'pydoc_data', 'test', 'lib2to3', 'idlelib', 'turtle',
            'turtledemo', 'curses', 'ensurepip', 'venv', 'distutils', 'setuptools', 'pip', 'sqlite3', 'numpy', 'PIL',
            'pytest', 'IPython']

a = Analysis(
    [str(AQUI / 'ventas.py')],
    pathex=[str(AQUI)],
    binaries=[],
    datas=[(str(AQUI / 'fuentes' / 'Inter.ttf'), 'fuentes')] + copy_metadata('keyring'),
    hiddenimports=collect_submodules('keyring.backends') + ['keyring.backends.macOS'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=QT_SOBRA + PY_SOBRA,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NOMBRE,
    console=False,
    debug=False,
    strip=False,
    upx=False,
    argv_emulation=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NOMBRE)
app = BUNDLE(
    coll,
    name=NOMBRE + '.app',
    icon=str(ICONO),
    bundle_identifier='com.cinemaproductions.cinecaptions-ventas',
    version=VERSION,
    info_plist={
        'CFBundleDisplayName': NOMBRE,
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': VERSION,
        'LSMinimumSystemVersion': '12.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,      # modo oscuro como el resto de la app
        'NSHumanReadableCopyright': '© 2026 Cinema Productions',
        'LSApplicationCategoryType': 'public.app-category.business',
    },
)
