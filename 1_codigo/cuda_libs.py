# CineCaptions · By Cinema Productions
# 1_codigo/cuda_libs.py — las librerías CUDA que necesita Whisper en la GPU: detectarlas, registrarlas y repararlas.
"""
cuda_libs.py  (v5.4.8)
----------------------
Whisper (CTranslate2) usa la GPU solo si encuentra `cublas64_12.dll` (y las de cuDNN 9). Si faltan, la transcripción «falla en CUDA» y se repite en CPU
(mucho más lenta) sin que el chequeo de arranque lo avise. Aquí:

  * `carpetas_candidatas()` — dónde pueden estar: las de PyTorch del motor Qwen (`motor_qwen/python/Lib/site-packages/torch/lib`: ya trae cuBLAS y cuDNN
                              de CUDA 12), los paquetes `nvidia-*` y la carpeta propia `~/DaVinciSubtitles/cuda_libs`;
  * `registrar()`           — añade al buscador de DLL (y al PATH, que es lo que mira ctranslate2) las carpetas que SÍ tienen las librerías;
  * `diagnostico()`         — {'estado': 'ok' | 'sin_gpu' | 'faltan', 'gpu', 'vram_gb', 'faltan', 'ubicacion'} para el chequeo de arranque y Ajustes;
  * `reparar()`             — 1) reutiliza las del motor Qwen si están (sin descargar nada); 2) si no, descarga los paquetes oficiales `nvidia-cublas-cu12`
                              y `nvidia-cudnn-cu12` de PyPI (≈1,3 GB; con reanudación y verificación SHA-256, descargas.py) y deja las DLL en `cuda_libs`.
"""
import glob
import os
import sys
import zipfile
from pathlib import Path

DLLS_NECESARIAS = ('cublas64_12.dll', 'cublasLt64_12.dll', 'cudnn64_9.dll')
PAQUETES_PYPI = ('nvidia-cublas-cu12', 'nvidia-cudnn-cu12')
CARPETA_PROPIA = Path.home() / 'DaVinciSubtitles' / 'cuda_libs'
_REGISTRADAS = set()


def _es_windows():
    return sys.platform.startswith('win')


def carpetas_candidatas():
    """Las carpetas donde podrían estar las DLL de CUDA, por orden de preferencia."""
    cands = [CARPETA_PROPIA]
    try:
        import motor_voz
        base = Path(motor_voz.carpeta()) / 'python' / 'Lib' / 'site-packages'
        cands.append(base / 'torch' / 'lib')
        cands += [Path(p) for p in glob.glob(str(base / 'nvidia' / '*' / 'bin'))]
    except Exception:
        pass
    for p in sys.path:
        try:
            cands += [Path(x) for x in glob.glob(str(Path(p) / 'nvidia' / '*' / 'bin'))]
            cands += [Path(x) for x in glob.glob(str(Path(p) / 'nvidia' / '*' / 'lib'))]
        except Exception:
            pass
    vistos, salida = set(), []
    for c in cands:
        k = str(c).lower()
        if k not in vistos and c.is_dir():
            vistos.add(k)
            salida.append(c)
    return salida


def buscar(dll):
    """La ruta de esa DLL en cualquier carpeta candidata (o None)."""
    for c in carpetas_candidatas():
        r = c / dll
        if r.is_file():
            return r
    return None


def registrar():
    """Registra (buscador de DLL + PATH) las carpetas candidatas que tienen alguna de las librerías de CUDA. Devuelve las carpetas registradas AHORA."""
    if not _es_windows():
        return []
    nuevas = []
    for c in carpetas_candidatas():
        k = str(c).lower()
        if k in _REGISTRADAS:
            continue
        if not any((c / d).is_file() for d in DLLS_NECESARIAS):
            continue
        try:
            os.add_dll_directory(str(c))
        except Exception:
            pass
        os.environ['PATH'] = str(c) + os.pathsep + os.environ.get('PATH', '')
        _REGISTRADAS.add(k)
        nuevas.append(c)
    return nuevas


def _carga(ruta):
    """¿Esa DLL carga de verdad (con sus dependencias)? 0x8 = LOAD_WITH_ALTERED_SEARCH_PATH."""
    try:
        import ctypes
        ctypes.WinDLL(str(ruta), winmode=0x8)
        return True
    except Exception:
        return False


def _gpu_nvidia():
    """(nombre, vram_gb) de la primera GPU NVIDIA, o (None, 0)."""
    try:
        import motor_voz
        nombre = None
        if hasattr(motor_voz, 'hay_gpu_nvidia') and not motor_voz.hay_gpu_nvidia():
            return None, 0.0
        vram = float(motor_voz.vram_total_gb() or 0.0) if hasattr(motor_voz, 'vram_total_gb') else 0.0
    except Exception:
        vram = 0.0
    import subprocess
    try:
        r = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=8,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        linea = (r.stdout or '').strip().splitlines()[0]
        nombre, mb = [x.strip() for x in linea.split(',')[:2]]
        return nombre, float(mb) / 1024.0
    except Exception:
        return None, vram


def diagnostico():
    """Cómo está la GPU para Whisper: {'estado': 'ok'|'sin_gpu'|'faltan'|'no_aplica', 'gpu', 'vram_gb', 'faltan': [...], 'ubicacion'}."""
    if not _es_windows():
        return {'estado': 'no_aplica', 'gpu': None, 'vram_gb': 0.0, 'faltan': [], 'ubicacion': None}
    gpu, vram = _gpu_nvidia()
    if not gpu:
        return {'estado': 'sin_gpu', 'gpu': None, 'vram_gb': 0.0, 'faltan': [], 'ubicacion': None}
    registrar()
    faltan, ubicacion = [], None
    for d in DLLS_NECESARIAS:
        r = buscar(d)
        if r is None or not _carga(r):
            faltan.append(d)
        elif ubicacion is None:
            ubicacion = str(r.parent)
    return {'estado': 'faltan' if faltan else 'ok', 'gpu': gpu, 'vram_gb': round(vram, 1), 'faltan': faltan, 'ubicacion': ubicacion}


def texto_diagnostico(d=None):
    """Una línea para el chequeo de arranque."""
    d = d or diagnostico()
    if d['estado'] == 'ok':
        return f"{d['gpu']} · {d['vram_gb']} GB · CUDA lista"
    if d['estado'] == 'faltan':
        return f"{d['gpu']}: faltan {', '.join(d['faltan'])} (Ajustes › General › Reparar GPU)"
    if d['estado'] == 'sin_gpu':
        return 'sin GPU NVIDIA (se usa la CPU)'
    return 'no aplica en este sistema'


def tipo_de_calculo(vram_gb=None):
    """El `compute_type` de Whisper en la GPU según su memoria: float16 con ≥ 6 GB (o sin dato), int8_float16 con 3–6 GB (la mitad de memoria y casi igual de preciso) y
    None con menos de 3 GB (no cabe: mejor la CPU)."""
    if vram_gb is None:
        vram_gb = _gpu_nvidia()[1]
    if not vram_gb:
        return 'float16'
    if vram_gb >= 6.0:
        return 'float16'
    if vram_gb >= 3.0:
        return 'int8_float16'
    return None


def reparar(aviso=None, permitir_descarga=True):
    """Deja la GPU lista. Devuelve (ok, mensaje). Primero reutiliza las DLL del motor Qwen; si no hay, descarga las oficiales de NVIDIA (≈1 GB)."""
    def decir(t):
        if aviso:
            try:
                aviso(t)
            except Exception:
                pass
    registrar()
    d = diagnostico()
    if d['estado'] == 'ok':
        return True, 'La GPU ya estaba lista: ' + texto_diagnostico(d)
    if d['estado'] == 'sin_gpu':
        return False, 'No hay una GPU NVIDIA: se usa la CPU.'
    if d['estado'] == 'no_aplica':
        return True, 'En este sistema no hace falta.'
    if not permitir_descarga:
        return False, 'Faltan las librerías de CUDA y no hay copia en el motor Qwen.'
    import descargas
    CARPETA_PROPIA.mkdir(parents=True, exist_ok=True)
    for paquete in PAQUETES_PYPI:
        decir(f'Buscando {paquete} en PyPI…')
        try:
            url, sha256, nombre, tam = descargas.rueda_de_pypi(paquete)
        except Exception as e:
            return False, f'No pude consultar PyPI ({paquete}): {e}'
        destino = CARPETA_PROPIA / '_descargas' / nombre
        decir(f'Descargando {paquete} ({tam / 1e6:.0f} MB)…')
        try:
            descargas.descargar(url, destino, sha256=sha256, tam=tam, progreso=lambda f: decir(f'Descargando {paquete}… {int(f * 100)} %'))
        except Exception as e:
            return False, f'La descarga de {paquete} falló: {e}'
        decir(f'Instalando {paquete}…')
        try:
            with zipfile.ZipFile(destino) as z:
                for info in z.infolist():
                    n = info.filename.replace('\\', '/')
                    if n.lower().endswith('.dll') and '/bin/' in n:
                        with z.open(info) as f, open(CARPETA_PROPIA / Path(n).name, 'wb') as out:
                            while True:
                                trozo = f.read(1 << 20)
                                if not trozo:
                                    break
                                out.write(trozo)
        except Exception as e:
            return False, f'No pude abrir {nombre}: {e}'
        try:
            destino.unlink()
        except OSError:
            pass
    registrar()
    d = diagnostico()
    return (d['estado'] == 'ok'), ('GPU lista: ' + texto_diagnostico(d)) if d['estado'] == 'ok' else ('Sigue faltando: ' + texto_diagnostico(d))
