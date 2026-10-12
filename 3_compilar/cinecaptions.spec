# -*- mode: python ; coding: utf-8 -*-
# CineCaptions · By Cinema Productions
# 3_compilar/cinecaptions.spec — receta de PyInstaller del programa (qué módulos y recursos van dentro del .exe).
# ============================================================================
# CineCaptions -> "CineCaptions.exe" + _internal\
#   Lo usa Construir_Instalador.ps1 (no hace falta llamarlo a mano):
#     pyinstaller --noconfirm --distpath <dist> --workpath <work> cinecaptions.spec
#   Variables de entorno que pone el script:
#     CINECAPTIONS_FUENTES   carpeta con los .py ya preparados (el principal:
#                        "CineCaptions (script principal).py")
#     CINECAPTIONS_RECURSOS  la carpeta recursos del proyecto (resolve_scripts, locales,
#                        plantillas_incluidas, fonts, sfx_library, emojis, logo)
#     CINECAPTIONS_VERSION   la version (APP_VERSION de version.py), para el .exe
# ============================================================================
import os
from PyInstaller.utils.hooks import collect_data_files

FUENTES = os.environ['CINECAPTIONS_FUENTES']
RECURSOS = os.environ['CINECAPTIONS_RECURSOS']
VERSION = os.environ.get('CINECAPTIONS_VERSION', '0.0.0')
AQUI = os.path.dirname(os.path.abspath(SPEC))

# Todo lo que viaja junto al programa y el codigo busca en BASE_RECURSOS
# (sys._MEIPASS = <instalacion>\_internal).
datas = []
for carpeta in ('resolve_scripts', 'locales', 'plantillas_incluidas', 'fonts',
                'sfx_library', 'sfx_emoji', 'emojis', 'motor_qwen', 'guia_estilo', 'generador_packs', 'fondos_estilos', 'vistas_slider', 'efectos', 'edicion_pro'):          # v5.4.49: Edición PRO (plantillas OGraf, modelo de recorte, colocador)
    origen = os.path.join(RECURSOS, carpeta)
    if not os.path.isdir(origen):
        raise SystemExit(f'Falta {origen}: sin eso el programa queda cojo')
    datas.append((origen, carpeta))
datas.append((os.path.join(RECURSOS, 'logo_cinecaptions.png'), '.'))
datas.append((os.path.join(RECURSOS, 'logo_cinema_productions.png'), '.'))      # v5.3.5: la marca «CINEMA PRODUCTIONS» (blanca, transparente): Inicio y Ajustes > Acerca de
datas.append((os.path.join(RECURSOS, 'fondo_esfera.jpg'), '.'))      # v5.2.1: la imagen de referencia de la escena de Inicio

# Datos de librerias que PyInstaller no ve solo (v5.0.0: la interfaz es
# PySide6; su hook ya trae las DLL de Qt y el plugin de ventanas)
datas += collect_data_files('faster_whisper')      # silero_vad*.onnx (filtro de voz)
datas += collect_data_files('spellchecker')        # diccionarios de ortografia
datas += collect_data_files('sacremoses')          # tablas del tokenizador de Argos
datas += collect_data_files('qtawesome')           # v5.2: las fuentes de iconos (Phosphor)

# Modulos propios: casi todos se importan dentro de funciones y alguno puede
# escaparse al analisis; se listan todos para no depender de eso.
propios = sorted(os.path.splitext(n)[0] for n in os.listdir(FUENTES)
                 if n.endswith('.py') and n != 'CineCaptions (script principal).py')

hiddenimports = propios + [
    'argostranslate.translate', 'argostranslate.package', 'argostranslate.settings',
    'argostranslate.sbd', 'minisbd', 'sentencepiece', 'sacremoses',
    'pynput.keyboard._win32', 'pynput.mouse._win32',
    'qtawesome', 'qtpy', 'qtpy.QtCore', 'qtpy.QtGui', 'qtpy.QtWidgets',
]

# Lo que NO va: stanza/spacy (los declara argostranslate, pero arrastran torch:
# ~500 MB y arranque 6x mas lento; ver rthook_stanza_stub.py), las IA pesadas
# opcionales de sugerencias_ia (keybert / sentence-transformers: el programa usa
# el heuristico si no estan), lupa (solo la usa la autoprueba de sidecar_lua) y
# librerias de desarrollo.
excludes = [
    'stanza', 'spacy', 'torch', 'torchvision', 'torchaudio', 'transformers',
    'keybert', 'sentence_transformers', 'lupa',
    'matplotlib', 'scipy', 'pandas', 'IPython', 'jupyter', 'notebook',
    'pytest', 'ruff', 'pyflakes', 'PyInstaller',
    # v5.0.0: la interfaz Tk se retiro del todo
    'tkinter', '_tkinter', 'customtkinter', 'darkdetect',
    # piezas de Qt que el programa no usa
    'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtNetwork', 'PySide6.QtOpenGL',
    'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtXml', 'PySide6.QtDBus',
    'PySide6.QtConcurrent', 'PySide6.QtPrintSupport',
]

a = Analysis(
    [os.path.join(FUENTES, 'CineCaptions (script principal).py')],
    pathex=[FUENTES],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(AQUI, 'rthook_stanza_stub.py')],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
# v5.0.0: de Qt sobran el OpenGL por software (la interfaz no usa OpenGL) y
# las traducciones de Qt (los textos van por i18n.tr, nunca se cargan): ~26 MB.
def _sobra(nombre):
    n = nombre.replace('/', '\\').lower()
    return n.startswith('pyside6\\') and (n.endswith('opengl32sw.dll') or '\\translations\\' in n)
a.binaries = [x for x in a.binaries if not _sobra(x[0])]
a.datas = [x for x in a.datas if not _sobra(x[0])]
pyz = PYZ(a.pure)

# Ficha de version del .exe (Propiedades > Detalles)
partes = (VERSION.split('.') + ['0', '0', '0', '0'])[:4]
tupla = tuple(int(p) if p.isdigit() else 0 for p in partes)
from PyInstaller.utils.win32.versioninfo import (VSVersionInfo, FixedFileInfo, StringFileInfo,
                                                  StringTable, StringStruct, VarFileInfo, VarStruct)
ficha = VSVersionInfo(
    ffi=FixedFileInfo(filevers=tupla, prodvers=tupla),
    kids=[
        StringFileInfo([StringTable('0C0A04B0', [
            StringStruct('ProductName', 'CineCaptions'),
            StringStruct('FileDescription', 'CineCaptions'),
            StringStruct('ProductVersion', VERSION),
            StringStruct('FileVersion', VERSION),
            StringStruct('OriginalFilename', 'CineCaptions.exe'),
            StringStruct('InternalName', 'CineCaptions'),
            StringStruct('CompanyName', 'Cinema Productions'),
            StringStruct('LegalCopyright', '© 2026 Cinema Productions'),
        ])]),
        VarFileInfo([VarStruct('Translation', [0x0C0A, 1200])]),
    ],
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CineCaptions',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(RECURSOS, 'logo_cinecaptions.ico'),
    version=ficha,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='CineCaptions',
)
