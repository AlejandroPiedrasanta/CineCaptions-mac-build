# CineCaptions · By Cinema Productions
# 1_codigo/motor_compat.py — servicio Python 3.14 para Whisper, Argos y ONNX Runtime.
"""Aísla extensiones nativas que aún no publican ruedas para CPython 3.15.

El programa principal corre en Python 3.15.2. Este servicio usa un Python
3.14.10 embebido en %LOCALAPPDATA% y un protocolo JSON por stdin/stdout; no
comparte módulos ni DLL con el proceso de Qt.

v5.58, Mac (EN_PROCESO): ese Python aparte es solo de Windows. El programa de Mac (Python 3.14 en Apple Silicon, 3.13 en Intel) lleva las
librerías DENTRO (7_mac: requirements del motor + PyInstaller) y aquí worker.atender corre en este mismo proceso (_EnProceso, misma interfaz
que _Servidor). Desde la 5.34 el Mac no tenía motor de voz: GO fallaba en «Transcribiendo» con «configurado para Windows x64».
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
PYTHON_VERSION = (3, 14, 10)
PYTHON_EMBEBIDO = 'https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip'
GET_PIP = 'https://bootstrap.pypa.io/get-pip.py'
TIEMPO_MAX_PIP_S = 3600
SIN_VENTANA = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
_CACHE = {'info': None, 'cuando': 0.0}
_PY = '.'.join(map(str, PYTHON_VERSION))


def _misma_rama(version):
    """v5.46: un 3.14.x ya instalado sigue valiendo (las ruedas son de la rama 3.14): subir el parche (3.14.9 -> 3.14.10) no obliga a
    reinstalar el motor en los equipos que ya lo tienen; los nuevos se instalan con PYTHON_VERSION."""
    return str(version or '').startswith('%d.%d.' % PYTHON_VERSION[:2])
_SERVIDOR = {'s': None}
_LOCK = threading.RLock()
EN_PROCESO = sys.platform != 'win32'      # v5.58: fuera de Windows el worker corre dentro del programa (ver arriba)
_LIBRERIAS = ('faster_whisper', 'ctranslate2', 'onnxruntime', 'argostranslate')


def carpeta() -> Path:
    if EN_PROCESO:                        # (en el Mac solo guarda temporales: el audio a 16 kHz y los .npy del recorte)
        return Path(tempfile.gettempdir()) / 'CineCaptions' / 'motor_compat'
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


def _faltan_en_proceso():
    """v5.58 (Mac): las librerías del worker que este programa NO trae dentro."""
    import importlib.util
    faltan = []
    for modulo in _LIBRERIAS:
        try:
            if importlib.util.find_spec(modulo) is None:
                faltan.append(modulo)
        except (ImportError, ValueError):
            faltan.append(modulo)
    return faltan


def info_instalado():
    """Marca del entorno separado; no implica que sus DLL ya se hayan cargado."""
    if EN_PROCESO:
        if _faltan_en_proceso():
            return None
        return {'version': VERSION, 'python': '.'.join(map(str, sys.version_info[:3])), 'en_proceso': True}
    if sys.platform != 'win32' or not python_motor().is_file():
        return None
    try:
        datos = json.loads((carpeta() / 'listo.json').read_text(encoding='utf-8'))
        paquetes = datos.get('paquetes') or {}
        completa = all(paquetes.get(n) == v for n, v in _fijados().items())
        if (datos.get('version') == VERSION and _misma_rama(datos.get('python'))
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


def _pip_orden(argumentos, timeout=TIEMPO_MAX_PIP_S):
    p = subprocess.run([str(python_motor()), '-s', '-m', 'pip', '--disable-pip-version-check', *argumentos],
                       capture_output=True, text=True, encoding='utf-8', errors='replace',
                       env=_entorno_proceso(), creationflags=SIN_VENTANA, timeout=timeout,
                       cwd=str(carpeta()))
    if p.returncode:
        cola = (p.stderr or p.stdout or '').strip().splitlines()[-8:]
        raise RuntimeError('pip: ' + ' | '.join(cola))


def _pip(argumentos, timeout=TIEMPO_MAX_PIP_S):
    _pip_orden(['install', '--no-warn-script-location', '--progress-bar', 'off', *argumentos], timeout)


_ONNXRUNTIMES = ('onnxruntime', 'onnxruntime-directml', 'onnxruntime-gpu')


def _cambiar_onnxruntime(actuales):
    """v5.57: onnxruntime, onnxruntime-directml (la GPU de «detrás de ti») y onnxruntime-gpu son el MISMO módulo con otro nombre: instalar uno
    encima de otro mezcla sus archivos y quitar el viejo después borraría los del nuevo. Si el fijado es otro, primero se BAJA su rueda (sin
    red, el motor se queda como estaba y sigue funcionando), luego se quita el viejo y se instala la rueda bajada."""
    fijados = _fijados()
    nuevo = next((n for n in _ONNXRUNTIMES if n in fijados), None)
    viejos = [n for n in _ONNXRUNTIMES if n != nuevo and actuales.get(n)]
    if not nuevo or not viejos:
        return
    ruedas = carpeta() / 'ruedas'
    shutil.rmtree(ruedas, ignore_errors=True)
    try:
        _pip_orden(['download', '--no-deps', '--only-binary=:all:', '--progress-bar', 'off', '--dest', str(ruedas),
                    f'{nuevo}=={fijados[nuevo]}'])
        _pip_orden(['uninstall', '-y', *viejos])                       # (si ya estaban los dos, esto borró también archivos del nuevo:
        _pip(['--no-deps', '--no-index', '--find-links', str(ruedas), '--force-reinstall',   # por eso se reinstala entero)
              f'{nuevo}=={fijados[nuevo]}'])
    finally:
        shutil.rmtree(ruedas, ignore_errors=True)


def _versiones():
    if EN_PROCESO:
        try:
            return _worker()._versiones()
        except Exception:
            return {}
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
    if EN_PROCESO:                        # (Mac: las versiones las fija su compilación; aquí solo cuenta que estén dentro)
        return _faltan_en_proceso()
    actuales = _versiones()
    return [f'{n}=={v}' for n, v in _fijados().items() if actuales.get(n) != v]


def _appdata_de_claude():
    """v5.57: ¿el código fuente corre desde Claude desktop (app MSIX) sobre el %LOCALAPPDATA% de verdad? Ahí es una mezcla de la carpeta real y
    una privada: lo que pip BORRA se borra de la real y lo nuevo va a la privada (así se rompió el motor Qwen el 2026-10-15). Las pruebas desde
    Claude usan una copia (LOCALAPPDATA a otra carpeta) o la ruta \\\\localhost\\c$, que no se virtualiza. El programa instalado, nunca."""
    if getattr(sys, 'frozen', False) or not os.environ.get('CLAUDE_CODE_DESKTOP_APP_VERSION'):
        return False
    return str(carpeta()).lower().startswith(str(Path.home() / 'AppData' / 'Local').lower())


_LOCK_INSTALAR = threading.RLock()


def instalar(progreso=None, aviso=None):
    """Prepara el último Python 3.14 y sus ruedas fijadas. No toca el motor Qwen.
    v5.72: de uno en uno (al abrir el programa lo pone al día vigilancia.poner_motores_al_dia en segundo plano, y _servidor() lo llama si
    hace falta): el segundo espera y, como ya no queda nada pendiente, termina en un momento."""
    with _LOCK_INSTALAR:
        return _instalar(progreso, aviso)


def _instalar(progreso=None, aviso=None):
    def pr(f, texto):
        if progreso:
            progreso(max(0.0, min(1.0, f)), texto)

    if EN_PROCESO:                        # v5.58: en el Mac no se instala nada: viene dentro del programa
        datos = info_instalado()
        if datos:
            return datos
        raise RuntimeError('Este CineCaptions no trae dentro el motor de voz (Whisper, Argos y ONNX: falta '
                           + ', '.join(_faltan_en_proceso()) + '). Reinstálalo con el instalador de la última versión.')
    if _appdata_de_claude():
        datos = info_instalado()
        if datos:
            return datos
        raise RuntimeError('El motor auxiliar hay que prepararlo o ponerlo al día, y desde Claude el AppData está virtualizado (pip lo '
                           'dejaría roto): pruébalo con una copia (LOCALAPPDATA a otra carpeta) o con la ruta \\\\localhost\\c$; el '
                           'programa instalado lo pone al día solo.')
    base = carpeta()
    base.mkdir(parents=True, exist_ok=True)
    py = python_motor()
    dll = base / 'python' / 'python314.dll'
    version_ok = False
    if py.is_file() and dll.is_file():
        try:
            r = subprocess.run([str(py), '-s', '-c', 'import sys;print(".".join(map(str,sys.version_info[:3])))'],
                               capture_output=True, text=True, timeout=15, creationflags=SIN_VENTANA)
            version_ok = r.returncode == 0 and _misma_rama(r.stdout.strip())
        except Exception:
            pass
    if py.exists() and not version_ok:
        with _LOCK:
            s, _SERVIDOR['s'] = _SERVIDOR['s'], None
        if s:
            s.cerrar()
        shutil.rmtree(base / 'python', ignore_errors=True)
    if not version_ok:
        pr(0.02, f'Descargando Python {_PY} auxiliar')
        zip_py = base / 'python_embebido.zip'
        _descargar(PYTHON_EMBEBIDO, zip_py, lambda f: pr(0.02 + 0.12 * f, f'Descargando Python {_PY} auxiliar'))
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
    actuales = _versiones()
    fijados = _fijados()
    pendientes = [n for n, v in fijados.items() if actuales.get(n) != v]
    otro_onnxruntime = any(actuales.get(n) for n in _ONNXRUNTIMES if n not in fijados)   # (dos a la vez: archivos mezclados)
    if pendientes or otro_onnxruntime:
        pr(0.22, f'Instalando Whisper, traducción y ONNX Runtime para Python {_PY}')
        _cambiar_onnxruntime(actuales)
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
                        try:
                            on_linea(tipo, resto)
                        except BaseException:
                            # v5.58: cancelar GO sale de aquí (SystemExit) con el pedido a medias: su LISTO se quedaba en la cola y desde ese
                            # momento cada pedido leía la respuesta del anterior (el GO siguiente: 0 palabras) hasta reiniciar el programa. Se
                            # cierra este servicio; el próximo pedido arranca uno limpio
                            try:
                                self.p.kill()
                            except Exception:
                                pass
                            raise
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
            try:                                  # v5.85: la última línea que diga algo (no la barra de descarga de Whisper)
                from motor_voz import motivo_de_errores
                detalle = motivo_de_errores(self.errores, 'El motor auxiliar se cerró.')
            except Exception:
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


_WORKER = {'m': None}


def _worker():
    """v5.58 (Mac): el módulo worker.py cargado en ESTE proceso (una vez), con el entorno que le pone _Servidor."""
    with _LOCK:
        if _WORKER['m'] is None:
            for clave, valor in (('HF_HUB_DISABLE_SYMLINKS', '1'), ('HF_HUB_DISABLE_XET', '1'), ('HF_HUB_ETAG_TIMEOUT', '20'),
                                 ('HF_HUB_DOWNLOAD_TIMEOUT', '30'), ('ARGOS_COMPUTE_TYPE', 'float32'), ('ARGOS_CHUNK_TYPE', 'MINISBD')):
                os.environ.setdefault(clave, valor)
            import importlib.util
            spec = importlib.util.spec_from_file_location('cinecaptions_worker_compat', str(script_motor()))
            modulo = importlib.util.module_from_spec(spec)
            antes, sys.dont_write_bytecode = sys.dont_write_bytecode, True     # (nada de __pycache__ dentro de la .app firmada)
            try:
                spec.loader.exec_module(modulo)
            finally:
                sys.dont_write_bytecode = antes
            _WORKER['m'] = modulo
        return _WORKER['m']


_SIN_CANDADO = ('verificar', 'cuda', 'paquetes_instalados')    # no emiten ni tocan los modelos: no esperan a que acabe una transcripción


class _EnProceso:
    """v5.58 (Mac): worker.atender en este proceso, con la interfaz de _Servidor (pedir / vivo / cerrar). Lo que el worker emite (ESTADO,
    PROGRESO, CARGADO) llega a on_linea igual que por la tubería. Sin corte por tiempo: un hilo no se puede matar (la barra sigue con
    PROGRESO). Un pedido cada vez, como el servidor."""

    def __init__(self):
        self.w = _worker()
        self.pedido = threading.Lock()
        self._on_linea = None
        self._resto = ''
        self.w._SALIDA = self                 # (emitir escribe «TIPO|valor\n» aquí en vez de en la tubería)
        threading.Thread(target=self._soltar_inactivo, daemon=True, name='compat-modelos-inactivos').start()

    def _soltar_inactivo(self):
        """Como worker.servidor: un modelo sin usar 240 s se suelta (si no, Whisper se quedaba en la RAM del programa para siempre)."""
        w = self.w
        while True:
            time.sleep(20)
            try:
                with w._LOCK:
                    if w._MODELOS and not w._ACTIVOS and time.monotonic() - w._ULTIMO_USO > 240:
                        w._MODELOS.clear()
                        w._ULTIMO_USO = 0.0
            except Exception:
                pass

    def write(self, texto):
        self._resto += texto
        while '\n' in self._resto:
            linea, self._resto = self._resto.split('\n', 1)
            tipo, _, resto = linea.partition('|')
            if tipo in ('ESTADO', 'PROGRESO', 'CARGADO') and self._on_linea:
                try:
                    self._on_linea(tipo, resto)
                except Exception:
                    pass
        return len(texto)

    def flush(self):
        pass

    def vivo(self):
        return True

    def _atender(self, operacion, datos):
        try:
            resultado = self.w.atender(operacion, {'operacion': operacion, **(datos or {})})
        except Exception as exc:              # (como el servidor: un fallo vuelve como RuntimeError con su tipo; el SystemExit de cancelar GO,
            raise RuntimeError(f'{type(exc).__name__}: {exc}') from exc    # que sale de on_linea, pasa tal cual: cancelar no es un fallo)
        return json.loads(json.dumps(resultado, ensure_ascii=False))

    def pedir(self, operacion, datos=None, on_linea=None, timeout=3600, sin_senal=180):
        # (v5.86: el recorte de persona —mate, caras, cuerpos— también en el Mac: worker._sesion_mate usa CoreML solo si da el mismo alfa)
        if operacion in _SIN_CANDADO:
            return self._atender(operacion, datos)
        with self.pedido:
            self._on_linea, self._resto = on_linea, ''
            try:
                return self._atender(operacion, datos)
            finally:
                self._on_linea = None

    def cerrar(self):
        """Al salir (atexit): sin esperar si el worker está bajando o cargando un modelo con su candado (el programa no se quedaba abierto)."""
        try:
            if self.w._LOCK.acquire(timeout=0.5):
                try:
                    self.w._MODELOS.clear()
                finally:
                    self.w._LOCK.release()
        except Exception:
            pass


def _servidor():
    if not instalado():
        instalar()
    with _LOCK:
        s = _SERVIDOR['s']
        if s is None or not s.vivo():
            _SERVIDOR['s'] = s = _EnProceso() if EN_PROCESO else _Servidor()
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
                progress_callback(float(texto.partition('|')[0]))     # (v5.57: «0.5|Traduciendo», como en transcribir)
            except ValueError:
                pass
        elif tipo == 'ESTADO' and status_callback:
            status_callback(texto)

    r = _pedir('traducir', {'textos': list(textos), 'origen': from_code, 'destino': to_code},
               on_linea=linea, timeout=3600, sin_senal=180)
    # v5.58: el worker devuelve {'textos': [...]}; desde la 5.34 se devolvía el dict entero y translate_cues lo recorría como lista (la pista
    # traducida salía con la palabra «textos»)
    return r.get('textos', []) if isinstance(r, dict) else r


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


def _detectar(op, rgb, modelo, umbral):
    if not instalado():
        instalar()
    import numpy as np
    ipc = carpeta() / 'ipc'
    ipc.mkdir(parents=True, exist_ok=True)
    trabajo = Path(tempfile.mkdtemp(prefix=f'{op}_', dir=ipc))
    entrada = trabajo / 'entrada.npy'
    try:
        np.save(entrada, np.asarray(rgb, dtype=np.uint8), allow_pickle=False)
        return _pedir(op, {'entrada': str(entrada), 'modelo': str(modelo), 'umbral': float(umbral)},
                      timeout=120, sin_senal=60).get(op) or []
    finally:
        shutil.rmtree(trabajo, ignore_errors=True)


def caras(rgb, modelo, umbral=0.6):
    """v5.58: las caras de una imagen con YuNet en el servicio 3.14 (worker._caras_activo): [[x0, y0, x1, y1, puntuación, 10 coordenadas de
    los 5 puntos]] en fracciones. Mejor mandarla ya pequeña (unos 640 px de lado: así se mide)."""
    return _detectar('caras', rgb, modelo, umbral)


def cuerpos(rgb, modelo, umbral=0.5):
    """v5.58: las personas (de frente, de lado o de espaldas) de una imagen con NanoDet en el servicio 3.14 (worker._cuerpos_activo):
    [[x0, y0, x1, y1, puntuación]] en fracciones. Mejor mandarla ya con el lado mayor a 416 px (la entrada del modelo)."""
    return _detectar('cuerpos', rgb, modelo, umbral)


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
