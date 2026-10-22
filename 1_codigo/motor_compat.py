# CineCaptions · By Cinema Productions
# 1_codigo/motor_compat.py — servicio Python 3.14 para Whisper, Argos y ONNX Runtime.
"""Aísla extensiones nativas que aún no publican ruedas para CPython 3.15.

El programa principal corre en Python 3.15.1. Este servicio usa un Python
3.14.9 embebido en %LOCALAPPDATA% y un protocolo JSON por stdin/stdout; no
comparte módulos ni DLL con el proceso de Qt.
"""
from __future__ import annotations

import json
import atexit
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

VERSION = '1.0.0'
PYTHON_VERSION = (3, 14, 9)
PYTHON_EMBEBIDO = 'https://www.python.org/ftp/python/3.14.9/python-3.14.9-embed-amd64.zip'
GET_PIP = 'https://bootstrap.pypa.io/get-pip.py'
TIEMPO_MAX_PIP_S = 3600
SIN_VENTANA = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
_CACHE = {'info': None, 'cuando': 0.0}
_SERVIDOR = {'s': None}
_LOCK = threading.RLock()


def carpeta() -> Path:
    local = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
    return Path(local) / 'CineCaptions' / 'motor_compat'


def python_motor() -> Path:
    return carpeta() / 'python' / 'python.exe'


def _base_recursos() -> Path:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / '2_recursos'


def script_motor() -> Path:
    return _base_recursos() / 'motor_compat' / 'worker.py'


def requisitos() -> Path:
    return _base_recursos() / 'motor_compat' / 'requirements.txt'


def _fijados() -> dict[str, str]:
    fijados = {'argostranslate': '1.11.0'}
    try:
        for linea in requisitos().read_text(encoding='utf-8').splitlines():
            linea = linea.split('#', 1)[0].strip()
            if '==' in linea:
                n, _, v = linea.partition('==')
                fijados[n.strip().lower().replace('_', '-')] = v.strip()
    except OSError:
        pass
    return fijados


def info_instalado():
    """Marca del entorno separado; no implica que sus DLL ya se hayan cargado."""
    if sys.platform != 'win32' or not python_motor().is_file():
        return None
    try:
        datos = json.loads((carpeta() / 'listo.json').read_text(encoding='utf-8'))
        paquetes = datos.get('paquetes') or {}
        completa = all(paquetes.get(n) == v for n, v in _fijados().items())
        if (datos.get('version') == VERSION and datos.get('python') == '.'.join(map(str, PYTHON_VERSION))
                and completa and (carpeta() / 'python' / 'python314.dll').is_file()):
            return datos
    except Exception:
        pass
    return None


def instalado() -> bool:
    return info_instalado() is not None


def _descargar(url: str, destino: Path, progreso=None):
    destino.parent.mkdir(parents=True, exist_ok=True)
    entorno_cert = os.environ.get('SSL_CERT_FILE')
    if not entorno_cert:
        try:
            import certifi
            os.environ['SSL_CERT_FILE'] = certifi.where()
        except Exception:
            pass
    pedido = urllib.request.Request(url, headers={'User-Agent': 'CineCaptions/5'})
    with urllib.request.urlopen(pedido, timeout=90) as r, destino.open('wb') as f:
        total = int(r.headers.get('Content-Length') or 0)
        hecho = 0
        while True:
            bloque = r.read(1 << 20)
            if not bloque:
                break
            f.write(bloque)
            hecho += len(bloque)
            if progreso and total:
                progreso(hecho / total)


def _entorno_proceso():
    entorno = dict(os.environ)
    entorno['PYTHONIOENCODING'] = 'utf-8'
    entorno['PYTHONUNBUFFERED'] = '1'
    entorno['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    entorno.pop('PYTHONPATH', None)
    entorno.pop('PYTHONHOME', None)
    return entorno


def _pip(argumentos, timeout=TIEMPO_MAX_PIP_S):
    p = subprocess.run([str(python_motor()), '-s', '-m', 'pip', 'install', '--no-warn-script-location',
                        '--progress-bar', 'off', '--disable-pip-version-check', *argumentos],
                       capture_output=True, text=True, encoding='utf-8', errors='replace',
                       env=_entorno_proceso(), creationflags=SIN_VENTANA, timeout=timeout,
                       cwd=str(carpeta()))
    if p.returncode:
        cola = (p.stderr or p.stdout or '').strip().splitlines()[-8:]
        raise RuntimeError('pip: ' + ' | '.join(cola))


def _versiones():
    try:
        p = subprocess.run([str(python_motor()), '-s', str(script_motor()), '--versiones'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace',
                           env=_entorno_proceso(), creationflags=SIN_VENTANA, timeout=60,
                           cwd=str(carpeta()))
        if p.returncode == 0:
            return json.loads((p.stdout or '').strip().splitlines()[-1])
    except Exception:
        pass
    return {}


def faltan_requisitos():
    actuales = _versiones()
    return [f'{n}=={v}' for n, v in _fijados().items() if actuales.get(n) != v]


def instalar(progreso=None, aviso=None):
    """Prepara el último Python 3.14 y sus ruedas fijadas. No toca el motor Qwen."""
    def pr(f, texto):
        if progreso:
            progreso(max(0.0, min(1.0, f)), texto)

    if sys.platform != 'win32':
        raise RuntimeError('El motor auxiliar Python 3.14 está configurado para Windows x64.')
    base = carpeta()
    base.mkdir(parents=True, exist_ok=True)
    py = python_motor()
    dll = base / 'python' / 'python314.dll'
    version_ok = False
    if py.is_file() and dll.is_file():
        try:
            r = subprocess.run([str(py), '-s', '-c', 'import sys;print(".".join(map(str,sys.version_info[:3])))'],
                               capture_output=True, text=True, timeout=15, creationflags=SIN_VENTANA)
            version_ok = r.returncode == 0 and r.stdout.strip() == '.'.join(map(str, PYTHON_VERSION))
        except Exception:
            pass
    if py.exists() and not version_ok:
        with _LOCK:
            s, _SERVIDOR['s'] = _SERVIDOR['s'], None
        if s:
            s.cerrar()
        shutil.rmtree(base / 'python', ignore_errors=True)
    if not version_ok:
        pr(0.02, 'Descargando Python 3.14.9 auxiliar')
        zip_py = base / 'python_embebido.zip'
        _descargar(PYTHON_EMBEBIDO, zip_py, lambda f: pr(0.02 + 0.12 * f, 'Descargando Python 3.14.9 auxiliar'))
        with zipfile.ZipFile(zip_py) as z:
            z.extractall(base / 'python')
        zip_py.unlink(missing_ok=True)
        pth = next((base / 'python').glob('python*._pth'))
        pth.write_text(pth.stem + '.zip\n.\nLib\\site-packages\nimport site\n', encoding='ascii')
    if not (base / 'python' / 'Lib' / 'site-packages' / 'pip' / '__init__.py').is_file():
        pr(0.16, 'Preparando pip del motor auxiliar')
        get_pip = base / 'get-pip.py'
        _descargar(GET_PIP, get_pip)
        try:
            r = subprocess.run([str(py), '-s', str(get_pip), '--no-warn-script-location', '-q'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace',
                               env=_entorno_proceso(), creationflags=SIN_VENTANA, timeout=600,
                               cwd=str(base))
        finally:
            get_pip.unlink(missing_ok=True)
        if r.returncode:
            raise RuntimeError('get-pip: ' + (r.stderr or r.stdout)[-500:])
    pendientes = faltan_requisitos()
    if pendientes:
        pr(0.22, 'Instalando Whisper, traducción y ONNX Runtime para Python 3.14.9')
        _pip(['--no-deps', '-r', str(requisitos())])
        _pip(['--no-deps', 'argostranslate==1.11.0'])
    versiones = _versiones()
    faltan = [f'{n}=={v}' for n, v in _fijados().items() if versiones.get(n) != v]
    if faltan:
        raise RuntimeError('El motor quedó incompleto: ' + ', '.join(faltan[:8]))
    datos = {'version': VERSION, 'python': '.'.join(map(str, PYTHON_VERSION)),
             'paquetes': versiones, 'instalado': time.strftime('%Y-%m-%d %H:%M')}
    (base / 'listo.json').write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding='utf-8')
    _CACHE.update(info=datos, cuando=time.time())
    pr(1.0, f'Motor auxiliar Python {datos["python"]} listo')
    if aviso:
        aviso(f'Whisper, Argos y ONNX Runtime están aislados en Python {datos["python"]}.')
    return datos


class _Servidor:
    def __init__(self):
        entorno = _entorno_proceso()
        entorno['PYTHONHASHSEED'] = '0'
        entorno.setdefault('HF_HUB_DISABLE_SYMLINKS', '1')
        entorno.setdefault('HF_HUB_DISABLE_XET', '1')
        entorno.setdefault('HF_HUB_ETAG_TIMEOUT', '20')
        entorno.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '30')
        entorno.setdefault('ARGOS_COMPUTE_TYPE', 'float32')
        entorno.setdefault('ARGOS_CHUNK_TYPE', 'MINISBD')
        self.p = subprocess.Popen([str(python_motor()), '-s', '-u', str(script_motor()), '--servidor'],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=entorno, creationflags=SIN_VENTANA, cwd=str(carpeta()))
        self.lineas = queue.Queue()
        self.errores = []
        self.pedido = threading.Lock()
        threading.Thread(target=self._leer, daemon=True, name='compat-out').start()
        threading.Thread(target=self._leer_err, daemon=True, name='compat-err').start()

    def _leer(self):
        for linea in iter(self.p.stdout.readline, b''):
            self.lineas.put(linea.decode('utf-8', 'replace').rstrip())
        self.lineas.put(None)

    def _leer_err(self):
        for linea in iter(self.p.stderr.readline, b''):
            self.errores.append(linea.decode('utf-8', 'replace').rstrip())
            del self.errores[:-40]

    def vivo(self):
        return self.p.poll() is None

    def pedir(self, operacion, datos=None, on_linea=None, timeout=3600, sin_senal=180):
        with self.pedido:
            self.p.stdin.write((json.dumps({'operacion': operacion, **(datos or {})}, ensure_ascii=False) + '\n').encode('utf-8'))
            self.p.stdin.flush()
            inicio = ultima = time.time()
            while time.time() - inicio < timeout:
                try:
                    linea = self.lineas.get(timeout=1.0)
                except queue.Empty:
                    if not self.vivo():
                        break
                    if time.time() - ultima > sin_senal:
                        self.cerrar()
                        raise RuntimeError(f'El motor auxiliar dejó de responder durante {sin_senal} s.')
                    continue
                if linea is None:
                    break
                tipo, _, resto = linea.partition('|')
                if tipo in ('ESTADO', 'PROGRESO', 'CARGADO'):
                    ultima = time.time()
                    if on_linea:
                        on_linea(tipo, resto)
                    continue
                if tipo == 'LISTO':
                    try:
                        return json.loads(resto)
                    except json.JSONDecodeError:
                        return resto
                if tipo == 'ERROR':
                    try:
                        detalle = json.loads(resto)
                    except json.JSONDecodeError:
                        detalle = resto
                    raise RuntimeError(str(detalle))
                if tipo == 'FIN':
                    break
            detalle = self.errores[-1] if self.errores else 'El motor auxiliar se cerró.'
            raise RuntimeError(detalle)

    def cerrar(self):
        try:
            if self.vivo():
                self.p.stdin.write(b'salir\n')
                self.p.stdin.flush()
                self.p.wait(timeout=5)
        except Exception:
            try:
                self.p.kill()
            except Exception:
                pass
        try:
            self.p.stdin.close()
        except Exception:
            pass


def _servidor():
    if not instalado():
        instalar()
    with _LOCK:
        s = _SERVIDOR['s']
        if s is None or not s.vivo():
            _SERVIDOR['s'] = s = _Servidor()
        return s


def _pedir(operacion, datos=None, on_linea=None, **kw):
    return _servidor().pedir(operacion, datos, on_linea, **kw)


def verificar():
    if not instalado():
        return {'instalado': False}
    return _pedir('verificar')


def cuda_disponible():
    if not instalado():
        return False
    try:
        return bool(_pedir('cuda').get('dispositivos'))
    except Exception:
        return False


def transcribir(media_path, source_lang, model_size, contexto='', use_cuda=False, compute_type='float16',
                local_only=False,
                progress_callback=None, model_loaded_callback=None, status_callback=None):
    if not instalado():
        instalar(aviso=status_callback)

    def linea(tipo, texto):
        if tipo == 'PROGRESO' and progress_callback:
            try:
                progress_callback(float(texto.partition('|')[0]))
            except ValueError:
                pass
        elif tipo == 'CARGADO' and model_loaded_callback:
            model_loaded_callback()
        elif tipo == 'ESTADO' and status_callback:
            status_callback(texto)

    return _pedir('transcribir', {'audio': str(media_path), 'idioma': source_lang or 'auto',
                                  'modelo': model_size, 'contexto': contexto or '',
                                  'cuda': bool(use_cuda), 'compute_type': compute_type,
                                  'local_only': bool(local_only)},
                  on_linea=linea, timeout=6 * 3600, sin_senal=180)


def precargar_whisper(model_size, compute_type='float16'):
    if not instalado():
        return False
    try:
        return bool(_pedir('precargar', {'modelo': model_size, 'compute_type': compute_type},
                           timeout=600, sin_senal=180).get('cargado'))
    except Exception:
        return False


def liberar_whisper():
    if instalado() and _SERVIDOR['s'] is not None and _SERVIDOR['s'].vivo():
        try:
            _pedir('liberar')
        except Exception:
            pass


def descargar_modelo(model_size, progreso=None, aviso=None):
    if not instalado():
        instalar(progreso=progreso, aviso=aviso)

    def linea(tipo, texto):
        if tipo == 'PROGRESO' and progreso:
            try:
                f, _, detalle = texto.partition('|')
                progreso(float(f), detalle)
            except Exception:
                pass
        elif tipo == 'ESTADO' and aviso:
            aviso(texto)

    return _pedir('descargar_modelo', {'modelo': model_size}, on_linea=linea,
                  timeout=4 * 3600, sin_senal=180)


def traducir(textos, from_code, to_code, progress_callback=None, status_callback=None):
    if not instalado():
        instalar(aviso=status_callback)

    def linea(tipo, texto):
        if tipo == 'PROGRESO' and progress_callback:
            try:
                progress_callback(float(texto))
            except ValueError:
                pass
        elif tipo == 'ESTADO' and status_callback:
            status_callback(texto)

    return _pedir('traducir', {'textos': list(textos), 'origen': from_code, 'destino': to_code},
                  on_linea=linea, timeout=3600, sin_senal=180)


def paquetes_instalados():
    if not instalado():
        return []
    try:
        return _pedir('paquetes_instalados').get('paquetes', [])
    except Exception:
        return []


def paquetes_disponibles(refrescar=True):
    if not instalado():
        try:
            instalar()
        except Exception:
            return []
    try:
        return _pedir('paquetes_disponibles', {'refrescar': bool(refrescar)}, timeout=300).get('paquetes', [])
    except Exception:
        return paquetes_instalados()


def instalar_paquete(from_code, to_code, log=print):
    if not instalado():
        instalar(aviso=log)

    def linea(tipo, texto):
        if tipo == 'ESTADO' and log:
            log(texto)

    try:
        return bool(_pedir('instalar_paquete', {'origen': from_code, 'destino': to_code},
                           on_linea=linea, timeout=3600).get('instalado'))
    except Exception as e:
        if log:
            log(str(e))
        return False


def audio_16k(media_path):
    """Escribe un WAV mono 16 kHz con el mismo decodificador que Whisper."""
    if not instalado():
        instalar()
    temporal = carpeta() / 'tmp'
    temporal.mkdir(parents=True, exist_ok=True)
    fd, salida = tempfile.mkstemp(prefix='cinecaptions_audio_', suffix='.wav', dir=temporal)
    os.close(fd)
    try:
        _pedir('audio_16k', {'audio': str(media_path), 'salida': salida}, timeout=1800, sin_senal=180)
        return salida
    except Exception:
        Path(salida).unlink(missing_ok=True)
        raise


def mate(rgb, alto=512, modelo=None):
    """Ejecuta MODNet en el servicio 3.14 y devuelve el alfa reducido a 0..1."""
    if not instalado():
        instalar()
    import numpy as np
    ipc = carpeta() / 'ipc'
    ipc.mkdir(parents=True, exist_ok=True)
    trabajo = Path(tempfile.mkdtemp(prefix='mate_', dir=ipc))
    entrada, salida = trabajo / 'entrada.npy', trabajo / 'salida.npy'
    try:
        np.save(entrada, np.asarray(rgb, dtype=np.uint8), allow_pickle=False)
        _pedir('mate', {'entrada': str(entrada), 'salida': str(salida),
                        'modelo': str(modelo or '') if modelo else '', 'alto': int(alto)},
               timeout=300, sin_senal=120)
        return np.load(salida, allow_pickle=False)
    finally:
        shutil.rmtree(trabajo, ignore_errors=True)


def descargar_modnet(destino):
    if not instalado():
        instalar()
    return _pedir('descargar_modnet', {'destino': str(destino)}, timeout=600, sin_senal=120)


def cerrar():
    with _LOCK:
        s, _SERVIDOR['s'] = _SERVIDOR['s'], None
    if s is not None:
        s.cerrar()


atexit.register(cerrar)
