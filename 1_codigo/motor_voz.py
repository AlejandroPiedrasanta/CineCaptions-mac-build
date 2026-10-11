# CineCaptions · By Cinema Productions
# 1_codigo/motor_voz.py — motor de voz e IA Qwen3 en su propio Python 3.12: instalar, detectar y transcribir.
"""
motor_voz.py
------------
El motor de voz de CineCaptions desde la v5.1: Qwen3-ASR (Alibaba, 2026) con
su alineador Qwen3-ForcedAligner para los tiempos de cada palabra. Whisper
large-v3-turbo queda de respaldo.

Por que va APARTE del programa
==============================
Qwen3-ASR solo da tiempos por palabra con su alineador, y el alineador solo
corre con PyTorch + transformers: varios GB que no caben en el .exe (y que
ademas piden Python 3.12, no el 3.14 del programa). Asi que el motor vive
en su propia carpeta, con su propio Python 3.12 embebido:

    %LOCALAPPDATA%\\CineCaptions\\motor_qwen\\
        python\\              Python 3.12.10 embebido + torch + qwen-asr
        listo.json           se escribe al final: si no esta, no se usa

Lo instala el paso "Motor de voz" del instalador (o Ajustes > General >
Motor de voz). El programa lo lanza como proceso por cada transcripcion
(2_recursos/motor_qwen/motor_qwen.py) y lee su avance por stdout.

Cuando NO se usa (y se usa Whisper sin que el usuario tenga que hacer nada):
  * no esta instalado, o la instalacion quedo a medias;
  * el idioma no esta entre los 11 que el alineador sabe medir;
  * el usuario eligio Whisper en Ajustes;
  * el motor falla por lo que sea (se avisa y se sigue con Whisper).
"""
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from i18n import tr

VERSION_ENTORNO = '1.0.0'
PYTHON_EMBEBIDO = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
GET_PIP = 'https://bootstrap.pypa.io/get-pip.py'
TORCH = 'torch==2.10.0'
INDICE_TORCH = {'cuda': 'https://download.pytorch.org/whl/cu128',
                'cpu': 'https://download.pytorch.org/whl/cpu'}
SIN_VENTANA = 0x08000000 if sys.platform == 'win32' else 0

# codigo ISO del programa -> nombre que entiende Qwen3-ASR
IDIOMAS_QWEN = {
    'zh': 'Chinese', 'en': 'English', 'yue': 'Cantonese', 'ar': 'Arabic', 'de': 'German',
    'fr': 'French', 'es': 'Spanish', 'pt': 'Portuguese', 'id': 'Indonesian', 'it': 'Italian',
    'ko': 'Korean', 'ru': 'Russian', 'th': 'Thai', 'vi': 'Vietnamese', 'ja': 'Japanese',
    'tr': 'Turkish', 'hi': 'Hindi', 'ms': 'Malay', 'nl': 'Dutch', 'sv': 'Swedish',
    'da': 'Danish', 'fi': 'Finnish', 'pl': 'Polish', 'cs': 'Czech', 'tl': 'Filipino',
    'fil': 'Filipino', 'fa': 'Persian', 'el': 'Greek', 'ro': 'Romanian', 'hu': 'Hungarian',
    'mk': 'Macedonian',
}
# los que el alineador sabe medir palabra a palabra (sin esto no hay subtitulos)
ALINEABLES = {'zh', 'en', 'yue', 'fr', 'de', 'it', 'ja', 'ko', 'pt', 'ru', 'es'}


def _base_recursos():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / '2_recursos'


def carpeta():
    base = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
    return Path(base) / 'CineCaptions' / 'motor_qwen'


def python_motor():
    return carpeta() / 'python' / 'python.exe'


def script_motor():
    return _base_recursos() / 'motor_qwen' / 'motor_qwen.py'


def requisitos():
    return _base_recursos() / 'motor_qwen' / 'requisitos_motor_qwen.txt'


def info_instalado():
    """El listo.json del motor, o None si no esta (o quedo a medias)."""
    if sys.platform != 'win32':
        return None
    try:
        datos = json.loads((carpeta() / 'listo.json').read_text(encoding='utf-8'))
    except Exception:
        return None
    if not python_motor().exists():
        return None
    return datos


def instalado():
    return info_instalado() is not None


# ---------------------------------------------------------------------------
# v5.2: saber si YA esta instalado mirando los archivos (pedido: «que revise si
# las IAs ya estan instaladas y no haga ese paso»). Sirve cuando listo.json se
# perdio (una instalacion interrumpida lo borraba al empezar) y para no volver
# a pasar por pip lo que ya esta.
# ---------------------------------------------------------------------------
def _sitio():
    return carpeta() / 'python' / 'Lib' / 'site-packages'


def _normalizar(nombre):
    return nombre.lower().replace('-', '_').replace('.', '_')


def _dist_instalada(nombre, version=None):
    """La version instalada de un paquete del motor (del .dist-info), o None."""
    sitio = _sitio()
    if not sitio.is_dir():
        return None
    buscado = _normalizar(nombre)
    for d in sitio.glob('*.dist-info'):
        n, _, v = d.name[:-len('.dist-info')].partition('-')
        if _normalizar(n) == buscado:
            if version is None or v.split('+')[0] == version:
                return v
    return None


def _requisitos_fijados():
    pares = []
    try:
        for linea in requisitos().read_text(encoding='utf-8').splitlines():
            linea = linea.split('#')[0].strip()
            if '==' in linea:
                n, _, v = linea.partition('==')
                pares.append((n.strip(), v.strip()))
    except OSError:
        pass
    return pares


def _faltan_requisitos():
    return [f'{n}=={v}' for n, v in _requisitos_fijados() if _dist_instalada(n, v) is None]


def _cache_hf():
    hub = os.environ.get('HF_HUB_CACHE')
    if not hub:
        home = os.environ.get('HF_HOME') or str(Path.home() / '.cache' / 'huggingface')
        hub = str(Path(home) / 'hub')
    return Path(hub)


def modelo_descargado(repo, minimo=0):
    """True si el snapshot de ese repo esta entero en la cache de Hugging Face."""
    snaps = _cache_hf() / ('models--' + repo.replace('/', '--')) / 'snapshots'
    try:
        for d in snaps.iterdir():
            total = sum(a.stat().st_size for a in d.glob('*.safetensors'))
            if total >= minimo and (d / 'config.json').exists():
                return True
    except OSError:
        pass
    return False


def detectar_por_archivos():
    """Lo que habria en listo.json si todo esta en su sitio, o None."""
    if sys.platform != 'win32' or not python_motor().exists():
        return None
    torch_v = _dist_instalada('torch')
    if not torch_v or torch_v.split('+')[0] != TORCH.split('==')[1] or _faltan_requisitos():
        return None
    if modelo_descargado('Qwen/Qwen3-ASR-1.7B', 1_000_000_000):
        modelo = '1.7B'
    elif modelo_descargado('Qwen/Qwen3-ASR-0.6B', 400_000_000):
        modelo = '0.6B'
    else:
        return None
    if not modelo_descargado('Qwen/Qwen3-ForcedAligner-0.6B', 400_000_000):
        return None
    texto = ('4B' if modelo_descargado('Qwen/Qwen3-4B-Instruct-2507', 3_000_000_000)
             else '1.7B' if modelo_descargado('Qwen/Qwen3-1.7B', 1_000_000_000) else None)
    return {'version': VERSION_ENTORNO, 'modelo': modelo, 'modelo_texto': texto, 'torch': torch_v,
            'cuda': '+cu' in torch_v, 'gpu': None, 'instalado': time.strftime('%Y-%m-%d %H:%M'),
            'detectado': True}


def asegurar_listo():
    """listo.json si ya esta todo instalado (lo rehace si faltaba). None si no."""
    info = info_instalado()
    if info and info.get('modelo_texto'):
        return info
    datos = detectar_por_archivos()
    if datos and datos.get('modelo_texto'):
        try:
            (carpeta() / 'listo.json').write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding='utf-8')
        except OSError:
            return None
        return info_instalado()
    return info


def soporta(codigo_idioma):
    return (codigo_idioma or '').lower() in ALINEABLES


def hay_gpu_nvidia():
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return True
    except Exception:
        pass
    try:
        r = subprocess.run(['nvidia-smi', '-L'], capture_output=True, text=True, timeout=10,
                           creationflags=SIN_VENTANA)
        return r.returncode == 0 and 'GPU' in r.stdout
    except Exception:
        return False


def _leer_preferencia():
    try:
        prefs = json.loads((Path.home() / 'DaVinciSubtitles' / 'preferencias.json').read_text(encoding='utf-8'))
        return prefs.get('motor_voz') or 'qwen3'
    except Exception:
        return 'qwen3'


def motor_para(codigo_idioma):
    """'qwen3' si se va a usar Qwen3-ASR para este idioma, si no None (Whisper)."""
    if _leer_preferencia() != 'qwen3':
        return None
    if codigo_idioma not in (None, '', 'auto') and not soporta(codigo_idioma):
        return None
    if _FALLOS['n'] >= FALLOS_SEGUIDOS_MAX:
        # v5.11: dos fallos seguidos = no se vuelve a perder tiempo con Qwen3 en esta sesión (Whisper directo); reiniciar el programa lo reactiva
        if not _FALLOS['avisado']:
            _FALLOS['avisado'] = True
            r = _reg()
            if r:
                r.error('Qwen3-ASR falló %d veces seguidas: uso Whisper para el resto de esta sesión. Revisa Ajustes > General > Motor de voz > Reparar.' % _FALLOS['n'], 'motor de voz')
        return None
    return 'qwen3' if instalado() else None


def nombre_motor(codigo_idioma=None):
    """Para mostrar en Inicio / Ajustes."""
    info = info_instalado()
    if info and _leer_preferencia() == 'qwen3':
        modelo = (info.get('modelo') or '1.7B')
        return 'Qwen3-ASR ' + modelo
    return 'Whisper large-v3-turbo'


# ---------------------------------------------------------------------------
# v5.3: el motor de voz RESIDENTE (se carga y se calienta mientras Resolve prepara el audio)
# ---------------------------------------------------------------------------
# Medido con el audio de un reel de 24 s en una RTX 5070 Ti: lanzar el motor cada vez = ~11 s de imports + 8 s de modelo +
# 21,8 s en la primera inferencia (CUDA inicializa sus nucleos) = ~65 s; con el motor ya cargado y calentado = ~5 s.
INACTIVO_VOZ_S = 120          # segundos que queda cargado sin trabajo
SIN_SENAL_VOZ_S = 300         # v5.11: sin ninguna línea del motor durante tanto = colgado (carga fría + calentamiento en CPU caben de sobra)
FALLOS_SEGUIDOS_MAX = 2       # v5.11: tras tantos fallos seguidos de Qwen3 en esta sesión se deja de intentar y se usa Whisper directo
_FALLOS = {'n': 0, 'avisado': False}


def _reg():
    """El Registro, o None si no se puede importar (el motor también corre en pruebas sueltas)."""
    try:
        import registro
        return registro
    except Exception:
        return None


def _fallo_de_qwen(motivo):
    """Un intento de Qwen3 falló: se anota (con el motivo) y se cuenta; al llegar al máximo se apaga solo hasta reiniciar el programa."""
    _FALLOS['n'] += 1
    r = _reg()
    if r:
        r.aviso(f"Qwen3-ASR falló ({_FALLOS['n']}.º fallo seguido): {str(motivo)[:200]}", 'motor de voz')


def _exito_de_qwen():
    if _FALLOS['n']:
        r = _reg()
        if r:
            r.ok('Qwen3-ASR volvió a funcionar.', 'motor de voz')
    _FALLOS['n'] = 0
    _FALLOS['avisado'] = False


def abortar():
    """Mata el motor de voz SIN pedir el candado (el que lo tiene puede ser quien está colgado). Lo llama el vigía: el pedido en curso termina con error y
    transcribir() pasa solo al modelo de respaldo."""
    s = _SRV_VOZ.get('s')
    if s is not None and s.vivo():
        try:
            s.p.kill()
            return True
        except Exception:
            pass
    return False
_VRAM = {'gb': None}


def vram_total_gb():
    """VRAM total de la primera GPU NVIDIA en GB (0.0 si no hay), memorizada."""
    if _VRAM['gb'] is None:
        gb = 0.0
        try:
            r = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                               capture_output=True, text=True, timeout=8, creationflags=SIN_VENTANA)
            gb = max([float(x) / 1024.0 for x in r.stdout.split() if x.strip().replace('.', '', 1).isdigit()] or [0.0])
        except Exception:
            gb = 0.0
        _VRAM['gb'] = gb
    return _VRAM['gb']


def modo_gpu():
    """Como se reparte la GPU entre la voz (~6 GB) y la IA de texto (~9,5 GB):
      'residente'  (>= 22 GB)   las dos cargadas a la vez;
      'solapado'   (>= 14,5 GB) la IA de texto se carga MIENTRAS la voz trabaja y la voz se descarga al terminar;
      'secuencial' (el resto)   de una en una, como hasta la v5.2."""
    gb = vram_total_gb()
    return 'residente' if gb >= 22 else 'solapado' if gb >= 14.5 else 'secuencial'


class _ServidorVoz:
    """Un proceso de motor_qwen.py --servidor: modelo cargado y calentado, pedidos por stdin."""

    def __init__(self, modelo=None):
        entorno = dict(os.environ)
        entorno['PYTHONIOENCODING'] = 'utf-8'
        entorno['PYTHONUNBUFFERED'] = '1'
        entorno.pop('PYTHONPATH', None)
        entorno.pop('PYTHONHOME', None)
        self.modelo = modelo
        self.p = subprocess.Popen([str(python_motor()), '-u', str(script_motor()), '--servidor',
                                   '--inactivo', str(INACTIVO_VOZ_S)] + (['--modelo', modelo] if modelo else []),
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=entorno, creationflags=SIN_VENTANA, cwd=str(carpeta()))
        self.lineas = queue.Queue()
        self.errores = []
        self.pedido = threading.Lock()
        threading.Thread(target=self._leer, daemon=True, name='voz-out').start()
        threading.Thread(target=self._leer_err, daemon=True, name='voz-err').start()

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

    def pedir(self, wav, idioma, salida, on_linea, timeout=1800, sin_senal=SIN_SENAL_VOZ_S):
        """Manda un audio y espera el LISTO. Devuelve (ok, motivo). Si el motor aun esta cargando, espera (y cuenta).
        v5.11: si pasa `sin_senal` segundos sin NINGUNA linea del motor (ni progreso ni estado) se da por colgado, se mata el proceso y se devuelve el
        fallo: el llamador pasa solo al motor de respaldo en vez de esperar media hora."""
        with self.pedido:
            self.p.stdin.write((json.dumps({'audio': wav, 'idioma': idioma, 'salida': salida}) + '\n').encode('utf-8'))
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
                        return False, f'el motor de voz se quedó sin responder {int(sin_senal)} s'
                    continue
                ultima = time.time()
                if linea is None:
                    break
                tipo, _, resto = linea.partition('|')
                if tipo == 'LISTO':
                    return True, resto
                if tipo == 'ERROR':
                    return False, resto
                if tipo == 'FIN':
                    break
                on_linea(tipo, resto)
        return False, (self.errores[-1] if self.errores else 'el motor de voz se cerró')

    def cerrar(self):
        try:
            self.p.stdin.write(b'salir\n')
            self.p.stdin.flush()
            self.p.wait(timeout=6)
        except Exception:
            try:
                self.p.kill()
            except Exception:
                pass


_SRV_VOZ = {'s': None}
_LOCK_VOZ = threading.Lock()


def precargar():
    """Arranca el motor de voz EN SEGUNDO PLANO (imports + modelo + calentamiento) sin bloquear a nadie. Se llama al
    pulsar GO u «Obtener»: mientras Resolve renderiza el audio, el motor ya se esta cargando. True si quedo en marcha."""
    try:
        if _leer_preferencia() != 'qwen3' or not instalado():
            return False
        with _LOCK_VOZ:
            s = _SRV_VOZ['s']
            if s is not None and s.vivo():
                return True
            _SRV_VOZ['s'] = _ServidorVoz()
            return True
    except Exception:
        _SRV_VOZ['s'] = None
        return False


def liberar():
    """Descarga el motor de voz (deja la GPU para la IA de texto o para Resolve)."""
    with _LOCK_VOZ:
        s, _SRV_VOZ['s'] = _SRV_VOZ['s'], None
    if s is not None:
        s.cerrar()


# ---------------------------------------------------------------------------
# transcribir
# ---------------------------------------------------------------------------
def _audio_16k(media_path):
    """El audio del video en un .wav mono 16 kHz (lo que espera el motor)."""
    import wave
    import numpy as np
    try:
        import compat_av
        compat_av.aplicar()
    except ImportError:
        pass
    from faster_whisper.audio import decode_audio
    muestras = decode_audio(str(media_path), sampling_rate=16000)
    fd, ruta = tempfile.mkstemp(prefix='cinecaptions_voz_', suffix='.wav')
    os.close(fd)
    pcm = (np.clip(muestras, -1.0, 1.0) * 32767).astype('<i2')
    with wave.open(ruta, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm.tobytes())
    return ruta


def _lanzar(argumentos, on_linea, timeout=None, sin_senal=None):
    """Corre el motor de voz (motor_qwen.py); ver _lanzar_script."""
    return _lanzar_script(script_motor(), argumentos, on_linea, timeout, sin_senal)


def _lanzar_script(script, argumentos, on_linea, timeout=None, sin_senal=None):
    """Corre un script del motor (voz o texto) en su Python 3.12 y entrega
    cada linea 'TIPO|texto' a on_linea. Devuelve (codigo, ultimas_lineas_de_error).
    v5.11: `sin_senal` = segundos sin ninguna linea tras los que se mata el proceso (antes el timeout solo se miraba al llegar una linea: un motor
    colgado sin imprimir nada dejaba a GO esperando para siempre)."""
    entorno = dict(os.environ)
    entorno['PYTHONIOENCODING'] = 'utf-8'
    entorno['PYTHONUNBUFFERED'] = '1'
    entorno.pop('PYTHONPATH', None)
    entorno.pop('PYTHONHOME', None)
    p = subprocess.Popen([str(python_motor()), '-u', str(script), *argumentos],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=entorno,
                         creationflags=SIN_VENTANA, cwd=str(carpeta()))
    errores = []

    def leer_err():
        for linea in iter(p.stderr.readline, b''):
            errores.append(linea.decode('utf-8', 'replace').rstrip())
            del errores[:-40]

    threading.Thread(target=leer_err, daemon=True).start()
    inicio = time.time()
    pulso = {'t': time.time(), 'colgado': False}
    terminado = threading.Event()
    if sin_senal:
        def guardian():
            while not terminado.wait(2.0):
                if time.time() - pulso['t'] > sin_senal and p.poll() is None:
                    pulso['colgado'] = True
                    try:
                        p.kill()
                    except Exception:
                        pass
                    return
        threading.Thread(target=guardian, daemon=True, name='guardian-motor').start()
    try:
        for linea in iter(p.stdout.readline, b''):
            pulso['t'] = time.time()
            texto = linea.decode('utf-8', 'replace').rstrip()
            tipo, _, resto = texto.partition('|')
            on_linea(tipo, resto)
            if timeout and time.time() - inicio > timeout:
                p.kill()
                break
        p.wait()
    finally:
        terminado.set()
    if pulso['colgado']:
        errores.append(f'el motor se quedó sin responder {int(sin_senal)} s y se cerró')
        return (p.returncode if p.returncode not in (0, None) else -9), errores
    return p.returncode, errores


def transcribir(media_path, codigo_idioma, progress_callback=None, model_loaded_callback=None,
                status_callback=None):
    """Igual que subtitle_transcriber.transcribe: [{'start','end','word'}, ...].
    Lanza RuntimeError si el motor falla (el llamador sigue con Whisper)."""
    idioma = IDIOMAS_QWEN.get((codigo_idioma or '').lower(), '') if codigo_idioma != 'auto' else ''
    try:
        # v5.2: la IA de texto puede seguir cargada (8 GB): la GPU para la voz. v5.3: solo en una GPU justa; con
        # >= 14,5 GB la IA de texto se carga a la vez (y la voz se descarga al terminar), con >= 22 GB conviven.
        if modo_gpu() == 'secuencial':
            import ia_texto
            ia_texto.liberar()
    except Exception:
        pass
    if status_callback:
        status_callback(tr('Preparando el audio para Qwen3-ASR…'))
    wav = _audio_16k(media_path)
    salida = wav[:-4] + '.json'
    estado = {'listo': None, 'error': None, 'cargado': False}

    def linea(tipo, texto):
        if tipo == 'PROGRESO':
            if not estado['cargado']:
                estado['cargado'] = True
                if model_loaded_callback:
                    model_loaded_callback()
            if progress_callback:
                try:
                    progress_callback(float(texto))
                except ValueError:
                    pass
        elif tipo == 'ESTADO' and status_callback:
            status_callback(texto)
        elif tipo == 'LISTO':
            estado['listo'] = texto
        elif tipo == 'ERROR':
            estado['error'] = texto

    try:
        # 1) el motor residente (cargado y calentado: ~5 s); si no pudo, 2) la pasada suelta de siempre
        ok_servidor, motivo_servidor = False, ''
        try:
            with _LOCK_VOZ:
                srv = _SRV_VOZ['s']
                if srv is None or not srv.vivo():
                    _SRV_VOZ['s'] = srv = _ServidorVoz()
            ok_servidor, motivo_servidor = srv.pedir(wav, idioma, salida, linea)
        except Exception as e:
            motivo_servidor = f'{type(e).__name__}: {e}'
        if not ok_servidor:
            r = _reg()
            if r:
                r.aviso(f'El motor de voz residente no pudo ({str(motivo_servidor)[:200]}): pruebo con una pasada suelta.', 'motor de voz')
            liberar()
            estado.update(listo=None, error=None)
            if status_callback:
                status_callback(tr('Preparando el motor de voz…'))
            # v5.11: la pasada suelta también cambia SOLA de modelo si falla: el que elige el programa -> el ligero (0.6B) -> el ligero en CPU.
            # Cada intento queda en el Registro con su motivo; si ninguno sirve, el llamador sigue con Whisper.
            intentos = [([], 'el modelo habitual'), (['--modelo', '0.6B'], 'el modelo ligero 0.6B'), (['--modelo', '0.6B', '--dispositivo', 'cpu'], 'el modelo ligero en CPU')]
            motivo = motivo_servidor
            for extra, nombre in intentos:
                estado.update(listo=None, error=None)
                codigo, errores = _lanzar(['--audio', wav, '--idioma', idioma, '--salida', salida] + extra, linea, sin_senal=SIN_SENAL_VOZ_S)
                if codigo == 0 and estado['listo']:
                    if extra and r:
                        r.ok(f'Qwen3-ASR funcionó con {nombre}.', 'motor de voz')
                    break
                motivo = estado['error'] or (errores[-1] if errores else f'salió con código {codigo}') or motivo
                if r:
                    r.aviso(f'Qwen3-ASR con {nombre} falló: {str(motivo)[:200]}', 'motor de voz', detalle='\n'.join(errores[-12:]))
                if status_callback and extra != intentos[-1][0]:
                    status_callback(tr('El modelo de voz falló; pruebo con uno más ligero…'))
            else:
                _fallo_de_qwen(motivo)
                raise RuntimeError(motivo)
        datos = json.loads(Path(salida).read_text(encoding='utf-8'))
        palabras = [{'start': float(p['start']), 'end': float(p['end']), 'word': str(p['word']).strip()}
                    for p in datos.get('palabras') or [] if str(p.get('word', '')).strip()]
        print(f"Qwen3-ASR: {len(palabras)} palabras en {datos.get('segundos')} s "
              f"({datos.get('modelo')} en {datos.get('dispositivo')})")
        r = _reg()
        if palabras:
            _exito_de_qwen()
            if r:
                r.info(f"Voz: Qwen3-ASR {datos.get('modelo')} en {datos.get('dispositivo')} · {len(palabras)} palabras en {datos.get('segundos')} s", 'motor de voz')
        else:
            _fallo_de_qwen('no devolvió ninguna palabra')
        # la voz ya hizo su parte: en una GPU que no aguanta las dos IA se libera para la IA de texto (que se carga ya)
        try:
            if modo_gpu() != 'residente':
                liberar()
                import ia_texto
                ia_texto.precargar()
        except Exception:
            pass
        return palabras
    finally:
        for f in (wav, salida):
            try:
                os.unlink(f)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# instalar (paso del instalador y Ajustes > General)
# ---------------------------------------------------------------------------
def _bajar(url, destino, progreso=None):
    """v5.4.8: descarga reanudable con reintentos (descargas.py); si el módulo no está, la de siempre."""
    try:
        import descargas
        descargas.descargar(url, destino, progreso=progreso)
        return
    except ImportError:
        pass
    try:
        import certifi
        import ssl
        contexto = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        contexto = None
    pedido = urllib.request.Request(url, headers={'User-Agent': 'CineCaptions'})
    with urllib.request.urlopen(pedido, timeout=60, context=contexto) as r, open(destino, 'wb') as f:
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


TIEMPO_MAX_PIP_S = 3600          # una instalación de pip (PyTorch CUDA pesa ~2,5 GB): más de una hora = algo va mal
TIEMPO_MAX_GET_PIP_S = 600


def _pip(argumentos, aviso):
    entorno = dict(os.environ)
    entorno['PYTHONIOENCODING'] = 'utf-8'
    entorno['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    entorno.pop('PYTHONPATH', None)
    entorno.pop('PYTHONHOME', None)
    try:
        p = subprocess.run([str(python_motor()), '-m', 'pip', 'install', '--no-warn-script-location',
                            '--progress-bar', 'off', '--disable-pip-version-check', *argumentos],
                           capture_output=True, text=True, encoding='utf-8', errors='replace',
                           env=entorno, creationflags=SIN_VENTANA, timeout=TIEMPO_MAX_PIP_S)
    except subprocess.TimeoutExpired:
        raise RuntimeError(tr('La descarga tardó más de {min} minutos y se canceló. Revisa tu conexión y vuelve a intentarlo: lo ya descargado se conserva.', min=TIEMPO_MAX_PIP_S // 60))
    if p.returncode != 0:
        cola = (p.stderr or p.stdout or '').strip().splitlines()[-6:]
        raise RuntimeError('pip: ' + ' | '.join(cola))
    if aviso:
        aviso(' '.join(argumentos[:3]))


def instalar(progreso=None, aviso=None, modelo='auto'):
    """Instala (o repara) el motor. progreso(0..1, texto), aviso(texto).
    Lanza excepcion si no se pudo; deja listo.json solo si TODO salio bien."""
    def pr(f, texto):
        if progreso:
            progreso(max(0.0, min(1.0, f)), texto)

    if sys.platform != 'win32':
        raise RuntimeError(tr('El motor Qwen3-ASR por ahora solo está para Windows.'))
    base = carpeta()
    base.mkdir(parents=True, exist_ok=True)
    # v5.2: listo.json ya NO se borra al empezar (una instalacion cortada dejaba
    # el motor entero sin su marca y la siguiente lo reinstalaba todo); se
    # reescribe al final
    py = python_motor()
    if not py.exists():
        pr(0.01, tr('Descargando Python 3.12'))
        zip_py = base / 'python312.zip'
        _bajar(PYTHON_EMBEBIDO, zip_py)
        with zipfile.ZipFile(zip_py) as z:
            z.extractall(base / 'python')
        zip_py.unlink()
        pth = next((base / 'python').glob('python*._pth'))
        pth.write_text('python312.zip\n.\nLib\\site-packages\nimport site\n', encoding='ascii')
        pr(0.03, tr('Preparando pip'))
        get_pip = base / 'get-pip.py'
        _bajar(GET_PIP, get_pip)
        try:
            r = subprocess.run([str(py), str(get_pip), '--no-warn-script-location', '-q'],
                               capture_output=True, text=True, creationflags=SIN_VENTANA, timeout=TIEMPO_MAX_GET_PIP_S)
        except subprocess.TimeoutExpired:
            get_pip.unlink(missing_ok=True)
            raise RuntimeError(tr('Preparar pip tardó más de {min} minutos y se canceló. Revisa tu conexión y vuelve a intentarlo.', min=TIEMPO_MAX_GET_PIP_S // 60))
        get_pip.unlink()
        if r.returncode != 0:
            raise RuntimeError('get-pip: ' + (r.stderr or r.stdout)[-400:])
    gpu = hay_gpu_nvidia()
    torch_v = _dist_instalada('torch', TORCH.split('==')[1])
    if torch_v and (('+cu' in torch_v) == gpu):
        pr(0.35, tr('PyTorch ya estaba instalado ({v})', v=torch_v))
    else:
        pr(0.05, tr('Descargando PyTorch ({tipo}, ~{peso})', tipo='CUDA' if gpu else 'CPU',
                    peso='2,5 GB' if gpu else '200 MB'))
        _pip([TORCH, '--index-url', INDICE_TORCH['cuda' if gpu else 'cpu']], aviso)
    if _faltan_requisitos():
        pr(0.35, tr('Instalando Qwen3-ASR'))
        _pip(['--no-deps', '-r', str(requisitos())], aviso)
    pr(0.45, tr('Comprobando el motor'))
    info = {}

    def linea_comprobar(tipo, texto):
        if tipo == 'LISTO':
            info.update(json.loads(texto))
        elif tipo == 'ERROR':
            info['error'] = texto

    codigo, errores = _lanzar(['--comprobar'], linea_comprobar, timeout=300)
    if codigo != 0 or 'error' in info:
        raise RuntimeError(info.get('error') or (errores[-1] if errores else 'el motor no arrancó'))
    if aviso:
        aviso(f"torch {info.get('torch')} · CUDA {'sí' if info.get('cuda') else 'no'}"
              + (f" · {info.get('gpu')} {info.get('vram_gb')} GB" if info.get('gpu') else ''))
    pr(0.5, tr('Descargando los modelos de Qwen3-ASR'))
    estado = {}
    eleccion = modelo if modelo in ('1.7B', '0.6B') else info.get('modelo_auto') or '0.6B'

    def linea_descarga(tipo, texto):
        if tipo == 'PROGRESO':
            try:
                pr(0.5 + 0.3 * float(texto), tr('Descargando los modelos de Qwen3-ASR'))
            except ValueError:
                pass
        elif tipo == 'ESTADO' and aviso:
            aviso(texto)
        elif tipo == 'ERROR':
            estado['error'] = texto

    codigo, errores = _lanzar(['--descargar', '--modelo', eleccion], linea_descarga)
    if codigo != 0:
        raise RuntimeError(estado.get('error') or (errores[-1] if errores else 'no se descargaron los modelos'))
    # la IA de texto (corregir y elegir palabras): Qwen3-4B con 10 GB de VRAM o
    # mas, Qwen3-1.7B si no. Si falla, el motor de voz queda igual de listo.
    pr(0.8, tr('Descargando la IA de texto (Qwen3)'))
    texto_listo = {}

    def linea_texto(tipo, texto):
        if tipo == 'LISTO':
            texto_listo['modelo'] = texto
        elif tipo == 'ESTADO' and aviso:
            aviso(texto)

    try:
        _lanzar_script(_base_recursos() / 'motor_qwen' / 'motor_texto.py', ['--descargar'], linea_texto)
    except Exception as e:
        if aviso:
            aviso(f'IA de texto: {e}')
    (base / 'listo.json').write_text(json.dumps({
        'version': VERSION_ENTORNO, 'modelo': eleccion, 'modelo_texto': texto_listo.get('modelo'),
        'torch': info.get('torch'), 'cuda': info.get('cuda'), 'gpu': info.get('gpu'),
        'instalado': time.strftime('%Y-%m-%d %H:%M'),
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    pr(1.0, tr('Motor Qwen3-ASR listo'))
    return eleccion
