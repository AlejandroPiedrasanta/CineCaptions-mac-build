# -*- mode: python ; coding: utf-8 -*-
# CineCaptions · By Cinema Productions
# 7_mac/cinecaptions_mac.spec — receta de PyInstaller para Mac (Apple Silicon e Intel): arma CineCaptions.app.
# ============================================================================
# Gemela de 3_compilar/cinecaptions.spec (la de Windows). Lo usa Construir_Instalador_Mac.sh
# (no hace falta llamarlo a mano). Variables de entorno que pone el script:
#   CINECAPTIONS_FUENTES   carpeta con los .py ya preparados
#   CINECAPTIONS_RECURSOS  la carpeta 2_recursos del proyecto
#   CINECAPTIONS_VERSION   la version (APP_VERSION de version.py)
#   CINECAPTIONS_ICONO     el .icns de la app
#   CINECAPTIONS_ARQ       arm64 (por defecto) o x86_64
#   CINECAPTIONS_FIRMA     (opcional) "Developer ID Application: ..."; vacio = firma ad-hoc
# ============================================================================
import importlib.util
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

FUENTES = os.environ['CINECAPTIONS_FUENTES']
RECURSOS = os.environ['CINECAPTIONS_RECURSOS']
VERSION = os.environ.get('CINECAPTIONS_VERSION', '0.0.0')
ICONO = os.environ.get('CINECAPTIONS_ICONO') or None
FIRMA = os.environ.get('CINECAPTIONS_FIRMA') or None
ARQUITECTURA = os.environ.get('CINECAPTIONS_ARQ', 'arm64')        # arm64 (Apple Silicon) o x86_64 (Intel)
AQUI = os.path.dirname(os.path.abspath(SPEC))
RAIZ = os.path.dirname(AQUI)

datas = []
for carpeta in ('resolve_scripts', 'locales', 'plantillas_incluidas', 'fonts',
                'sfx_library', 'sfx_emoji', 'emojis', 'motor_qwen', 'motor_compat', 'guia_estilo', 'generador_packs', 'fondos_estilos', 'vistas_slider', 'efectos', 'edicion_pro',          # v5.4.49: Edición PRO (plantillas OGraf, modelo de recorte, colocador)
                'motions_resolve', 'creativo',          # v5.5.10: 'creativo' = el móvil de «Así se verá este bloque»; v5.5.9: los motions editables de Resolve (Efectos › Títulos › CineCaptions; generador_packs/drfx_motions.py)
                'biblioteca_sonido'):                   # v5.56: los SFX curados del sonido de GO (3_compilar/empaquetar_sonidos.py)
    origen = os.path.join(RECURSOS, carpeta)
    if not os.path.isdir(origen):
        raise SystemExit(f'Falta {origen}: sin eso el programa queda cojo')
    datas.append((origen, carpeta))
datas.append((os.path.join(RECURSOS, 'logo_cinecaptions.png'), '.'))
datas.append((os.path.join(RECURSOS, 'logo_cinema_productions.png'), '.'))
datas.append((os.path.join(RECURSOS, 'fondo_esfera.jpg'), '.'))

datas += collect_data_files('faster_whisper')
datas += collect_data_files('spellchecker')
datas += collect_data_files('sacremoses')
datas += collect_data_files('qtawesome')

# v5.58 (Mac): el motor de voz (motor_compat/worker.py) corre DENTRO del programa (motor_compat.EN_PROCESO). worker.py viaja como DATO y
# PyInstaller no lo analiza: sus librerias se declaran aqui. Sin ellas el Mac sale SIN voz (paso desde la 5.34): se corta la compilacion.
MOTOR = ('faster_whisper', 'ctranslate2', 'onnxruntime', 'tokenizers', 'huggingface_hub', 'httpx2', 'httpcore2',
         'av', 'argostranslate', 'minisbd', 'sentencepiece', 'sacremoses')
_faltan = [m for m in MOTOR if importlib.util.find_spec(m) is None]
if _faltan:
    raise SystemExit('Faltan en el venv las librerias del motor de voz: ' + ', '.join(_faltan))
datas += collect_data_files('sentencepiece')     # (package_data: lo carga al importarse)
# los .dist-info: OBLIGATORIOS los de httpx2 y httpcore2 (version('httpx2') al importarse, sin respaldo: sin ellos huggingface_hub no baja
# los modelos); el resto, para worker._versiones (el chequeo de salud) y tqdm
for _dist in ('anyio', 'av', 'certifi', 'click', 'cloudpickle', 'colorama', 'ctranslate2', 'faster-whisper', 'filelock',
              'flatbuffers', 'fsspec', 'h11', 'hf-xet', 'httpcore2', 'httpx2', 'huggingface-hub', 'idna', 'joblib',
              'minisbd', 'numpy', 'onnxruntime', 'packaging', 'pillow', 'protobuf', 'PyYAML', 'regex', 'sacremoses',
              'sentencepiece', 'six', 'tokenizers', 'truststore', 'tqdm', 'typing-extensions', 'argostranslate'):
    datas += copy_metadata(_dist)

propios = sorted(os.path.splitext(n)[0] for n in os.listdir(FUENTES)
                 if n.endswith('.py') and n != 'CineCaptions (script principal).py')

hiddenimports = propios + [
    'argostranslate.translate', 'argostranslate.package', 'argostranslate.settings',
    'argostranslate.sbd', 'minisbd', 'sentencepiece', 'sacremoses',
    'pynput.keyboard._darwin', 'pynput.mouse._darwin',
    'qtawesome', 'qtpy', 'qtpy.QtCore', 'qtpy.QtGui', 'qtpy.QtWidgets',
]
# v5.58: el motor de voz (ver arriba). 'worker' = motor_compat/worker.py (pathex), para que el analisis siga tambien sus imports
hiddenimports += [
    'worker',
    'contextlib', 'importlib.metadata', 'importlib.util', 'json', 'shutil', 'threading', 'traceback', 'types', 'wave',
    're', 'urllib.request',
    'ctranslate2', 'ctranslate2._ext', 'ctranslate2.models', 'ctranslate2.extensions', 'ctranslate2.logging',
    'tokenizers', 'onnxruntime', 'onnxruntime.capi._pybind_state', 'onnxruntime.capi.onnxruntime_pybind11_state',
    'av', 'tqdm', 'tqdm.auto', 'numpy', 'PIL.Image', 'yaml', 'filelock',
    'huggingface_hub', 'huggingface_hub.file_download', 'huggingface_hub._snapshot_download', 'huggingface_hub.hf_api',
    'huggingface_hub.constants', 'huggingface_hub.errors', 'huggingface_hub.utils',
    'httpx2', 'httpcore2', 'httpcore2._backends.sync', 'truststore', 'truststore._macos', 'hf_xet',
    'argostranslate.tokenizer', 'argostranslate.models', 'argostranslate.utils', 'argostranslate.networking',
    'sacremoses.normalize', 'sacremoses.tokenize', 'regex', 'packaging.version',
]
hiddenimports += collect_submodules('faster_whisper')
hiddenimports += collect_submodules('huggingface_hub')
hiddenimports += collect_submodules('anyio')
hiddenimports += collect_submodules('httpx2')
hiddenimports += collect_submodules('httpcore2')
hiddenimports += collect_submodules('minisbd')
hiddenimports += collect_submodules('argostranslate', filter=lambda n: n not in ('argostranslate.cli', 'argostranslate.argospm'))
hiddenimports += collect_submodules('tokenizers', filter=lambda n: not n.startswith('tokenizers.tools'))   # (tools importa IPython)

excludes = [
    'stanza', 'spacy', 'torch', 'torchvision', 'torchaudio', 'transformers',
    'keybert', 'sentence_transformers', 'lupa',
    'matplotlib', 'scipy', 'pandas', 'IPython', 'jupyter', 'notebook',
    'pytest', 'ruff', 'pyflakes', 'PyInstaller',
    'sympy', 'onnx', 'onnxruntime.transformers', 'onnxruntime.quantization', 'onnxruntime.tools',        # v5.58: el motor no los usa
    'ctranslate2.converters', 'ctranslate2.specs', 'tensorflow',
    'tkinter', '_tkinter', 'customtkinter', 'darkdetect',
    'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtNetwork', 'PySide6.QtOpenGL',
    'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtXml', 'PySide6.QtDBus',
    'PySide6.QtConcurrent', 'PySide6.QtPrintSupport',
]

a = Analysis(
    [os.path.join(FUENTES, 'CineCaptions (script principal).py')],
    pathex=[FUENTES, os.path.join(RECURSOS, 'motor_compat')],          # (v5.58: para 'worker', ver hiddenimports)
    binaries=collect_dynamic_libs('ctranslate2'),                       # (v5.58: sus .dylibs; el analisis ya las sigue, por si acaso)
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(RAIZ, '3_compilar', 'rthook_stanza_stub.py')],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
# las traducciones de Qt sobran (los textos van por i18n.tr)
def _sobra(nombre):
    n = nombre.replace('\\', '/').lower()
    if n.startswith('edicion_pro/remotion/runtime/'):
        # v5.4.52: el runtime de Remotion (node, su compositor y el Chrome sin ventana) NO pasa por PyInstaller: sus binarios ya vienen firmados y
        # no admiten el cambio de rutas (install_name_tool fallaba con libEGL.dylib de Chrome y la compilación de Mac se cortaba).
        # Construir_Instalador_Mac.sh lo copia tal cual en la app después
        return True
    return n.startswith('pyside6/') and '/translations/' in n
a.binaries = [x for x in a.binaries if not _sobra(x[0])]
a.datas = [x for x in a.datas if not _sobra(x[0])]
pyz = PYZ(a.pure)

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
    argv_emulation=False,
    target_arch=ARQUITECTURA,
    codesign_identity=FIRMA,
    entitlements_file=os.path.join(AQUI, 'entitlements.plist'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='CineCaptions',
)
app = BUNDLE(
    coll,
    name='CineCaptions.app',
    icon=ICONO,
    bundle_identifier='com.cinemaproductions.cinecaptions',
    version=VERSION,
    info_plist={
        'CFBundleName': 'CineCaptions',
        'CFBundleDisplayName': 'CineCaptions',
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': VERSION,
        'LSMinimumSystemVersion': '14.0',      # v5.58: lo real (PySide6 6.12, av 19 y onnxruntime 1.24 piden macOS 14; antes decía 12)
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': '© 2026 Cinema Productions',
        'NSAppleEventsUsageDescription':
            'CineCaptions necesita avisar a DaVinci Resolve y traer su ventana al frente.',
        'NSDocumentsFolderUsageDescription':
            'CineCaptions guarda tus proyectos y copias de seguridad en Documentos.',
        'NSDesktopFolderUsageDescription':
            'CineCaptions lee los videos que arrastras desde el Escritorio.',
        'NSDownloadsFolderUsageDescription':
            'CineCaptions lee los videos que arrastras desde Descargas.',
        'NSRemovableVolumesUsageDescription':
            'CineCaptions lee los videos que estan en discos externos.',
    },
)
