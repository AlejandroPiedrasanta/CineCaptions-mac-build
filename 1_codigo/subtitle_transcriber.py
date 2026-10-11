# CineCaptions · By Cinema Productions
# 1_codigo/subtitle_transcriber.py — transcripción con Whisper, traducción con Argos y escritura de .srt / manifiestos.
"""\nsubtitle_transcriber.py\n------------------------\nPieza 1 del sistema: transcribe un video/audio con Whisper (gratis, local)\ny genera archivos .srt controlando caracteres por línea y líneas por bloque.\n\nSoporta múltiples idiomas: transcribe el idioma \"fuente\" directamente con\nWhisper, y traduce a los idiomas adicionales con Argos Translate (gratis,\noffline, sin API keys).\n\nUso básico:\n    python subtitle_transcriber.py mi_video.mp4 --source-lang es --langs es en\n\nEsto genera:\n    ~/DaVinciSubtitles/mi_video.es.srt\n    ~/DaVinciSubtitles/mi_video.en.srt\n    ~/DaVinciSubtitles/subtitles_manifest.json   <- lo lee el script de Resolve\n\nInstalación (una sola vez):\n    pip install faster-whisper argostranslate\n\nPara traducir, la primera vez que uses un par de idiomas, Argos Translate\ndescarga un paquete pequeño (una sola vez, offline después):\n    python -c \"import argostranslate.package as p; p.update_package_index();         pkgs=p.get_available_packages();         [p.install_from_path(x.download()) for x in pkgs if x.from_code==\'es\' and x.to_code==\'en\']\"\n"""
import argparse
import json
import os
import sidecar_lua
from i18n import tr
os.environ['HF_HUB_DISABLE_SYMLINKS'] = '1'
# v5.3.1: igual que la tarea «modelo» del instalador: sin hf-xet (en el programa compilado se queda colgado en Mac) y con
# tiempos de espera cortos, para que una descarga que no avanza falle con un aviso en vez de quedarse parada.
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
os.environ.setdefault('HF_HUB_ETAG_TIMEOUT', '20')
os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '30')
import textwrap
from dataclasses import dataclass
from pathlib import Path
os.environ.setdefault('ARGOS_COMPUTE_TYPE', 'float32')
os.environ.setdefault('ARGOS_CHUNK_TYPE', 'MINISBD')
try:
    import certifi
    os.environ.setdefault('SSL_CERT_FILE', certifi.where())
except Exception:
    pass
SHARED_FOLDER = Path.home() / 'DaVinciSubtitles'
@dataclass
class Cue:
    start: float
    end: float
    text: str
def register_cuda_dlls():
    """Busca las carpetas \'lib\' de los paquetes pip de nvidia y las registra\n    en el DLL path para que ctranslate2 (faster-whisper) encuentre CUDA."""
    import os
    import sys
    from pathlib import Path
    if sys.platform != 'win32':
        return
    try:                                   # v5.4.8: cuBLAS/cuDNN del motor Qwen (torch\lib), de los paquetes nvidia o de la carpeta propia (Reparar GPU)
        import cuda_libs
        cuda_libs.registrar()
    except Exception:
        pass
    else:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            try:
                os.add_dll_directory(sys._MEIPASS)
                print(f'[CUDA] Registrado directorio temporal de PyInstaller: {sys._MEIPASS}')
            except Exception:
                return None
        else:
            for p in sys.path:
                path = Path(p)
                nvidia_path = path / 'nvidia'
                if nvidia_path.is_dir():
                    for lib_dir in nvidia_path.glob('*/lib'):
                        if lib_dir.is_dir():
                            try:
                                os.add_dll_directory(str(lib_dir))
                                print(f'[CUDA] Registrado directorio de DLLs de Nvidia: {lib_dir}')
                            except Exception as e:
                                pass
# v5.3 (bug de siempre): si CUDA falla en la primera transcripcion (faltan las DLL de cuBLAS...) se cae a CPU, pero un segundo
# intento con CUDA en el MISMO proceso se CUELGA para siempre dentro de ctranslate2. Se recuerda el fallo y no se vuelve a intentar.
_CUDA_FALLO = {'v': False}
def _tipo_cuda():
    """El compute_type de Whisper en la GPU según su memoria (float16 con ≥ 6 GB, int8_float16 con 3-6 GB): la mitad de VRAM y casi la misma precisión."""
    try:
        import cuda_libs
        return cuda_libs.tipo_de_calculo() or 'float16'
    except Exception:
        return 'float16'
def _hay_cuda_usable():
    """True si ctranslate2 ve al menos una GPU CUDA.\n\n    Se PREGUNTA en vez de probar. Antes se cargaba el modelo en CUDA \"a ver\n    si suena\", y en una maquina sin GPU eso costaba una carga entera del\n    modelo para nada antes de caer a CPU.\n\n    Que devuelva >0 NO garantiza que la inferencia vaya a funcionar: puede\n    haber GPU y driver pero faltar las DLL de CUDA 12 (es el caso que\n    reventaba). Por eso el reintento en CPU de transcribe() sigue siendo\n    necesario; esto solo evita el intento inutil.\n    """
    if _CUDA_FALLO['v']:
        return False
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() <= 0:
            return False
    except Exception:
        return False
    try:                                   # v5.4.8: con menos de 3 GB de VRAM el modelo no cabe: directo a la CPU (sin cargarlo para nada)
        import cuda_libs
        return cuda_libs.tipo_de_calculo() is not None
    except Exception:
        return True
def _es_error_de_memoria(exc) -> bool:
    """True si la excepcion huele a \'me quede sin RAM\'.\n\n    v1.0.65 (caso real del usuario: generar con Resolve + Chrome abiertos):\n    el fallo de memoria de ctranslate2/MKL llega como **RuntimeError**\n    (\"mkl_malloc: failed to allocate memory\"), no como MemoryError, asi\n    que el tipo solo no alcanza — se mira tambien el texto. Los\n    marcadores cubren MKL, el allocator de C++ y los mensajes tipicos\n    de CUDA/SO.\n    """
    if isinstance(exc, MemoryError):
        return True
    else:
        texto = str(exc).lower()
        return any((marca in texto for marca in ['mkl_malloc', 'failed to allocate', 'bad_alloc', 'out of memory', 'cannot allocate']))
# ---------------------------------------------------------------------------
# v5.3: el modelo de Whisper se REUTILIZA entre pasadas (cargarlo cuesta 3-10 s y ~3 GB en la GPU) y los audios largos
# se procesan por LOTES (BatchedInferencePipeline de faster-whisper: varios tramos de 30 s a la vez en la GPU).
# ---------------------------------------------------------------------------
import threading as _threading
import time as _time

INACTIVO_WHISPER_S = 240
LARGO_PARA_LOTES_S = 45.0       # por debajo de esto un solo tramo: el lote no aporta nada
_WHISPER = {'clave': None, 'modelo': None, 't': 0.0, 'vigilando': False, 'lock': _threading.Lock()}


_PESO_MODELO = {'large-v3-turbo': 1_620_000_000, 'large-v3': 3_100_000_000, 'medium': 1_530_000_000,
                'small': 485_000_000, 'base': 145_000_000, 'tiny': 78_000_000}
SIN_AVANCE_S = 120               # una descarga que no crece en tanto tiempo se da por colgada


def _tamano_carpeta(carpeta):
    total = 0
    for raiz, _, archivos in os.walk(carpeta):
        for a in archivos:
            try:
                total += os.path.getsize(os.path.join(raiz, a))
            except OSError:
                pass
    return total


def _asegurar_modelo_descargado(tamano, aviso=None):
    """Si los pesos de Whisper no estan en disco, los baja MOSTRANDO el avance (antes la primera transcripcion en un equipo sin el
    modelo se veia como un cuelgue mudo: WhisperModel descarga ~1,6 GB sin decir nada). Si no crece en SIN_AVANCE_S, avisa y falla."""
    from faster_whisper.utils import _MODELS, download_model
    try:
        download_model(tamano, local_files_only=True)
        return
    except Exception:
        pass
    aviso = aviso or (lambda t: None)
    import huggingface_hub
    repo = _MODELS.get(tamano) or str(tamano)
    carpeta = Path(huggingface_hub.constants.HF_HUB_CACHE) / ('models--' + repo.replace('/', '--'))
    total = _PESO_MODELO.get(tamano) or 0
    aviso(tr('Descargando el modelo de voz ({peso}). Solo pasa la primera vez: no cierres el programa.',
             peso=f'{total / 1e9:.1f} GB'.replace('.', ',') if total else tr('puede pesar varios cientos de MB')))
    inicial = _tamano_carpeta(carpeta)
    resultado = {}

    def bajar():
        try:
            resultado['ruta'] = download_model(tamano)
        except Exception as exc:
            resultado['error'] = exc
    hilo = _threading.Thread(target=bajar, daemon=True, name='whisper-descarga')
    hilo.start()
    ultimo, desde = inicial, _time.time()
    while hilo.is_alive():
        hilo.join(2.0)
        hecho = max(0, _tamano_carpeta(carpeta) - inicial)
        actual = inicial + hecho
        if actual > ultimo:
            ultimo, desde = actual, _time.time()
        elif _time.time() - desde > SIN_AVANCE_S:
            raise RuntimeError(tr('La descarga del modelo de voz no avanza desde hace {s} segundos. Revisa tu conexión a internet '
                                  '(o un firewall/VPN) y vuelve a intentarlo: lo que ya bajó no se pierde.', s=SIN_AVANCE_S))
        if total:
            aviso(tr('Descargando el modelo de voz: {a} de {b} MB ({p} %)', a=f'{hecho / 1e6:,.0f}'.replace(',', '.'),
                     b=f'{total / 1e6:,.0f}'.replace(',', '.'), p=int(min(99, 100 * hecho / total))))
        else:
            aviso(tr('Descargando el modelo de voz: {a} MB', a=f'{hecho / 1e6:,.0f}'.replace(',', '.')))
    if 'error' in resultado:
        exc = resultado['error']
        raise RuntimeError(tr('No pude descargar el modelo de voz ({t}: {m}). Revisa tu conexión a internet y vuelve a intentarlo.',
                              t=type(exc).__name__, m=str(exc)[:200]))


def _modelo_whisper(tamano, device, compute_type, local_only=False, aviso=None):
    """El WhisperModel cargado (el mismo mientras no cambie tamano/dispositivo)."""
    import compat_av
    compat_av.aplicar()
    from faster_whisper import WhisperModel
    clave = (tamano, device, compute_type)
    with _WHISPER['lock']:
        if _WHISPER['clave'] == clave and _WHISPER['modelo'] is not None:
            _WHISPER['t'] = _time.time()
            return _WHISPER['modelo']
        _WHISPER.update(modelo=None, clave=None)          # suelta el anterior antes de cargar el nuevo
        if not local_only:
            _asegurar_modelo_descargado(tamano, aviso)
        if aviso:
            aviso(tr('Cargando el modelo de voz en memoria…'))
        extra = {}
        if device == 'cpu' and __import__('sys').platform == 'darwin':
            extra['cpu_threads'] = min(8, os.cpu_count() or 4)          # los nucleos de rendimiento del Mac; por defecto usa solo 4
        modelo = WhisperModel(tamano, device=device, compute_type=compute_type, local_files_only=local_only, **extra)
        _WHISPER.update(clave=clave, modelo=modelo, t=_time.time())
        if not _WHISPER['vigilando']:
            _WHISPER['vigilando'] = True
            _threading.Thread(target=_vigilar_whisper, daemon=True, name='whisper-inactivo').start()
        return modelo


def _vigilar_whisper():
    while True:
        _time.sleep(20)
        with _WHISPER['lock']:
            if _WHISPER['modelo'] is None:
                _WHISPER['vigilando'] = False
                return
            if _time.time() - _WHISPER['t'] > INACTIVO_WHISPER_S:
                _WHISPER.update(modelo=None, clave=None, vigilando=False)
                return


def liberar_whisper():
    with _WHISPER['lock']:
        _WHISPER.update(modelo=None, clave=None)


def precargar_whisper(model_size):
    """Carga Whisper en la GPU en segundo plano (al pulsar GO u «Obtener» con Whisper elegido). No hace nada sin CUDA."""
    def trabajo():
        try:
            register_cuda_dlls()
            if _hay_cuda_usable():
                _modelo_whisper(model_size, 'cuda', _tipo_cuda())
        except Exception:
            pass
    _threading.Thread(target=trabajo, daemon=True, name='whisper-precarga').start()


def _duracion_segundos(ruta):
    try:
        import av
        with av.open(str(ruta)) as c:
            return float(c.duration) / 1e6 if c.duration else 0.0
    except Exception:
        return 0.0


def _al_registro(nivel, texto, origen=''):
    """v5.11: lo que antes solo salía por print() (invisible en el programa instalado) también va al Registro de la app, con su archivo errores.log."""
    try:
        import registro
        getattr(registro, nivel)(str(texto), origen)
    except Exception:
        pass


ESCALERA_MODELOS_MEMORIA = ('small', 'base')
_TAMANO_DESCARGA = {'small': '~460 MB', 'base': '~140 MB'}
_IDIOMA_DETECTADO = {'v': None}
_PALABRAS_COMUNES = {
    'es': 'el la los las de del que y en un una es se no por con para su al lo como más pero sus le ya o este sí porque esta entre cuando muy sin sobre también me hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese eso ante ellos e esto mí antes algunos qué unos yo otro otras otra él tanto esa estos mucho quienes nada muchos cual poco ella estar estas algunas algo nosotros mi mis tú te ti tu tus ellas nosotras vosotros vosotras os mío mía míos mías tuyo tuya suyo suya nuestro nuestra'.split(),
    'en': 'the of and to a in is that it was for on are as with his they at be this from have or by one had not but what all were when we there can an your which their said if do will each about how up out them then she many some so these would other into has more her two like him see time could no make than first been its who now people my made over did down only way find use may water long little very after words called just where most know get through back much before go good new write our me man too any day same right look think also around another came come work three word must because does part even place well such here take why things help put years different away again off went old number great tell men say small every found still between name should home big give air line set own under read last never us left end along while might next sound below saw something thing doesn\'t didn\'t i\'m it\'s you\'re we\'re that\'s he she you'.split(),
    'pt': 'o a os as de do da dos das que e em um uma é se não por com para seu ao como mais mas seus já ou este sim porque esta entre quando muito sem sobre também me até há onde quem desde tudo nos durante todos uns ni contra outros esse isso ante eles isto antes alguns qual você vocês nós não está são foi ser tem têm'.split(),
    'fr': 'le la les de du des un une et en est que qui dans pour pas sur au avec ce il elle ils elles nous vous je tu on se ne plus par mais ou où son sa ses leur leurs cette ces être avoir fait très aussi comme tout tous bien sans sous entre chez'.split(),
    'de': 'der die das und in den von zu mit sich des auf für ist im dem nicht ein eine als auch es an werden aus er hat dass sie nach wird bei einer um am sind noch wie einem über einen so zum war haben nur oder aber vor zur bis mehr durch man sein wurde sei ich du wir ihr'.split(),
    'it': 'il lo la i gli le di del della dei delle che e in un una è si non per con su al come più ma suoi già o questo sì perché questa tra quando molto senza sopra anche me fino c\'è dove chi da tutto noi durante tutti uno loro ni contro altri quello ante essi ciò prima alcuni quale io tu lui lei voi sono ho hai ha abbiamo hanno'.split(),
}


def _idioma_por_palabras(palabras):
    """Un idioma probable (es/en/pt/fr/de/it) contando palabras de función; None si no hay base para decirlo."""
    try:
        textos = [str(w.get('word', '')).lower().strip(".,;:!?¡¿\"'()") for w in (palabras or [])]
        if len(textos) < 8:
            return None
        puntos = {k: sum(1 for t in textos if t in set(v)) for k, v in _PALABRAS_COMUNES.items()}
        orden = sorted(puntos.items(), key=lambda kv: -kv[1])
        if orden[0][1] >= 3 and orden[0][1] >= 1.4 * max(1, orden[1][1]):
            return orden[0][0]
    except Exception:
        pass
    return None


def idioma_detectado(palabras=None):
    """El idioma de lo que se acaba de transcribir: el que detectó Whisper o, si fue otro motor, el que sale de contar las palabras. None = no se sabe."""
    return _IDIOMA_DETECTADO.get('v') or _idioma_por_palabras(palabras)


def transcribe(media_path: str, source_lang: str, model_size: str, progress_callback=None, model_loaded_callback=None, status_callback=None):
    """Transcribe el audio y devuelve una lista de palabras con timestamps.

    progress_callback(fraccion) se llama con un valor 0.0-1.0 a medida que
    avanza la transcripcion (lo usa la ventana grafica para la barra de
    progreso). model_loaded_callback() se llama una sola vez, cuando el
    modelo termino de cargar y empieza la transcripcion de verdad.
    status_callback(texto) recibe los avisos de degradacion (v1.0.65: la
    escalera de memoria) — los print de este modulo son invisibles en el
    build sin consola, y un reintento mudo parece un cuelgue.
    Los tres son opcionales: si no se pasan, el comportamiento es el de
    siempre.

    v5.1: primero el motor Qwen3-ASR (motor_voz) si esta instalado y sabe
    medir este idioma; si no esta o falla, Whisper como siempre.
    """
    ya_aviso = {'modelo': False}

    def _avisar(texto):
        print(texto)
        malo = any(p in str(texto).lower() for p in ('falló', 'fallo', 'memoria', 'pequeñ', 'no devolvió', 'no está descargado', 'poca '))
        _al_registro('aviso' if malo else 'info', texto, 'voz')               # v5.11: antes solo iba a la consola (invisible en el programa instalado) y a la barra de estado
        if status_callback:
            status_callback(texto)

    try:
        import motor_voz
        usar_qwen = motor_voz.motor_para(source_lang) == 'qwen3'
    except Exception:
        usar_qwen = False
    if usar_qwen:
        try:
            palabras = motor_voz.transcribir(media_path, source_lang, progress_callback=progress_callback,
                                             model_loaded_callback=model_loaded_callback,
                                             status_callback=status_callback)
            if palabras:
                return palabras
            _avisar(tr('Qwen3-ASR no devolvió palabras; pruebo con Whisper.'))
        except Exception as e:
            _avisar(tr('El motor Qwen3-ASR falló ({e}); sigo con Whisper.', e=str(e)[:200]))
        if progress_callback:
            progress_callback(0.0)

    register_cuda_dlls()

    def _transcribir_con(device, compute_type, tamano=None, local_only=False):
        """Carga el modelo y devuelve las palabras YA materializadas.

        El bucle que consume el generador vive aqui dentro a proposito: es
        donde ctranslate2 hace el computo de verdad, y por tanto lo unico
        que permite reintentar cuando CUDA falla. Ver el comentario de abajo.

        'tamano' permite a la escalera de memoria (v1.0.65) probar un
        modelo mas chico que el pedido; 'local_only' prueba primero SIN
        descargar nada (una descarga sorpresa en un equipo sin red es un
        cuelgue con la barra parada).
        """
        tamano = tamano or model_size
        print(f"Cargando modelo Whisper '{tamano}' en {device.upper()} (la primera vez descarga los pesos)...")
        model = _modelo_whisper(tamano, device, compute_type, local_only, aviso=_avisar)
        print('Transcribiendo... esto puede tardar según la duración del video.')
        idioma_w = source_lang if source_lang != 'auto' else None
        if device == 'cuda' and _duracion_segundos(media_path) > LARGO_PARA_LOTES_S:
            try:                                           # audios largos: varios tramos a la vez en la GPU
                import compat_av
                compat_av.aplicar()
                from faster_whisper import BatchedInferencePipeline
                segments, info = BatchedInferencePipeline(model=model).transcribe(
                    media_path, language=idioma_w, word_timestamps=True, vad_filter=True, batch_size=8)
            except Exception as e:
                print(f'Lotes no disponibles ({e}); sigo tramo a tramo.')
                segments, info = model.transcribe(media_path, language=idioma_w, word_timestamps=True, vad_filter=True)
        else:
            segments, info = model.transcribe(media_path, language=idioma_w, word_timestamps=True, vad_filter=True)
        if model_loaded_callback and not ya_aviso['modelo']:
            ya_aviso['modelo'] = True
            model_loaded_callback()
        total = getattr(info, 'duration', 0) or 0
        palabras = []
        for seg in segments:
            if seg.words:
                for w in seg.words:
                    palabras.append({'start': w.start, 'end': w.end,
                                     'word': w.word.strip()})
            if progress_callback and total > 0:
                progress_callback(min(1.0, seg.end / total))
        print(f'Idioma detectado/usado: {info.language}  ({len(palabras)} palabras)')
        _IDIOMA_DETECTADO['v'] = str(info.language or '').lower() or None
        _al_registro('info', f'Voz: Whisper {tamano} en {device.upper()} · idioma {info.language} · {len(palabras)} palabras', 'voz')
        return palabras

    if _hay_cuda_usable():
        try:
            return _transcribir_con('cuda', _tipo_cuda())
        except Exception as e:
            _CUDA_FALLO['v'] = True
            liberar_whisper()
            print(f'CUDA falló durante la transcripción ({e}). Repito en CPU...')
            _al_registro('aviso', f'La GPU (CUDA) falló en la transcripción: {str(e)[:200]}. Cambio automáticamente a la CPU (más lenta).', 'voz')
            if status_callback:
                status_callback(tr('La GPU falló; sigo con la CPU (más lento). Se arregla en Ajustes › General › Reparar GPU.'))
            if progress_callback:
                progress_callback(0.0)

    primer_error = None
    try:
        return _transcribir_con('cpu', 'int8')
    except Exception as e:
        if not _es_error_de_memoria(e):
            # v5.11: un modelo que no carga (archivos dañados, descarga a medias...) ya no tumba GO: se anota y se prueba con los más pequeños.
            # Si ninguno sirve, se lanza ESTE error (el original), no el de la escalera.
            if isinstance(e, SystemExit):
                raise
            primer_error = e
            _al_registro('error', f"Whisper '{model_size}' no pudo con la transcripción: {type(e).__name__}: {str(e)[:200]}. Pruebo con un modelo más pequeño.", 'voz')
            _avisar(tr("El modelo de voz falló; pruebo con uno más pequeño..."))
        else:
            _avisar(tr('Se acabó la memoria RAM para el modelo de voz; pruebo con uno más pequeño...'))

    for tamano in ESCALERA_MODELOS_MEMORIA:
        if progress_callback:
            progress_callback(0.0)
        _avisar(tr("Poca memoria: reintento con el modelo '{tamano}' (la transcripción puede ser algo menos fina).",
                   tamano=tamano))
        try:
            return _transcribir_con('cpu', 'int8', tamano=tamano,
                                    local_only=True)
        except Exception as e:
            if _es_error_de_memoria(e):
                continue
        _avisar(tr("El modelo '{tamano}' no está descargado; lo descargo ahora ({peso}). Puede tardar unos minutos.",
                   tamano=tamano,
                   peso=_TAMANO_DESCARGA.get(tamano)
                   or tr('unos cientos de MB')))
        try:
            return _transcribir_con('cpu', 'int8', tamano=tamano)
        except Exception as e:
            if _es_error_de_memoria(e):
                continue
            raise
    if primer_error is not None:
        raise primer_error
    raise SystemExit(tr(
        'El equipo se quedó sin memoria RAM para el modelo de voz (ni la versión pequeña entró).\n\nCierra otros programas y pestañas del navegador y vuelve a intentar — DaVinci Resolve puede seguir abierto.\nSi pasa siempre, reinicia el equipo antes de generar.'))
def build_cues(words, max_chars_per_line: int, max_lines: int, max_duration: float=6.0, min_duration: float=1.0, gap_break: float=0.5) -> list:
    char_budget = max_chars_per_line * max_lines
    cues = []
    current_words = []
    current_start = None
    def flush():
        nonlocal current_words, current_start
        if not current_words:
            return
        text = ' '.join(w['word'] for w in current_words).strip()
        start = current_start
        end = current_words[-1]['end']
        if end - start < min_duration:
            end = start + min_duration
        cues.append(Cue(start=start, end=end, text=text))
        current_words = []
        current_start = None
    prev_end = None
    for w in words:
        candidate_text = ' '.join([*(x['word'] for x in current_words), w['word']]).strip()
        gap = w['start'] - prev_end if prev_end is not None else 0
        would_be_too_long = len(candidate_text) > char_budget
        would_be_too_slow = current_start is not None and w['end'] - current_start > max_duration
        natural_break = current_words and gap > gap_break and (len(candidate_text) > 12)
        if current_words and (would_be_too_long or would_be_too_slow or natural_break):
                flush()
        if current_start is None:
            current_start = w['start']
        current_words.append(w)
        prev_end = w['end']
    flush()
    for i in range(len(cues) - 1):
        if cues[i].end > cues[i + 1].start:
            cues[i].end = cues[i + 1].start
    return cues
def wrap_cue_text(text: str, max_chars_per_line: int, max_lines: int) -> str:
    lines = textwrap.wrap(text, width=max_chars_per_line, break_long_words=False)
    if len(lines) <= max_lines:
        return '\n'.join(lines)
    else:
        words = text.split()
        n = max_lines
        chunk = max(1, len(words) // n + (1 if len(words) % n else 0))
        balanced = [' '.join(words[i:i + chunk]) for i in range(0, len(words), chunk)]
        return '\n'.join(balanced[:max_lines])
TOPE_PALABRAS_ORACION = 60
UMBRAL_SIN_TRADUCIR = 0.6
def _agrupar_cues_por_oracion(cues):
    """Corta la lista de cues en oraciones (o al tope, si no hay punto)."""
    import dynamic_subtitles as dyn
    grupos, actual, palabras = ([], [], 0)
    for cue in cues:
        actual.append(cue)
        palabras += len(cue.text.split())
        if dyn.termina_oracion(cue.text) or palabras >= TOPE_PALABRAS_ORACION:
            grupos.append(actual)
            actual, palabras = ([], 0)
    if actual:
        grupos.append(actual)
    return grupos
def _repartir_palabras(palabras, pesos):
    """Reparte una lista de palabras en len(pesos) tramos proporcionales.\n\n    Corte acumulativo con redondeo, y despues una pasada que le roba una\n    palabra al vecino mas cargado para que ningun tramo quede vacio\n    mientras haya de donde: un subtitulo en blanco a mitad de frase se ve\n    como un parpadeo. El orden de las palabras jamas cambia.\n    """
    m = len(palabras)
    total = float(sum(pesos)) or 1.0
    cortes, acum = ([], 0.0)
    for p in pesos[:(-1)]:
        acum += p
        cortes.append(int(round(acum / total * m)))
    cortes.append(m)
    partes, prev = ([], 0)
    for corte in cortes:
        corte = max(prev, min(corte, m))
        partes.append(list(palabras[prev:corte]))
        prev = corte
    for i, parte in enumerate(partes):
        if parte:
            continue
        else:
            vecinos = sorted((j for j in [i - 1, i + 1] if 0 <= j < len(partes)), key=lambda j: -len(partes[j]))
            for j in vecinos:
                if len(partes[j]) >= 2:
                    parte.append(partes[j].pop() if j < i else partes[j].pop(0))
                    break
    return partes
def _nucleos_para_comparar(texto):
    """Las palabras 'de contenido' de un texto, en minuscula y sin signos."""
    import re
    return [w for w in re.findall("[\\w']+", (texto or '').lower())
            if len(w) >= 3]
def _fraccion_sin_traducir(origen, salida):
    """Que fraccion del contenido del origen reaparece IGUAL en la salida.\n\n    1.0 = copia (o salida vacia); un texto corto (< 3 nucleos) devuelve\n    0.0 — con tan poco no se puede juzgar y un falso positivo reintenta\n    de balde.\n    """
    o = _nucleos_para_comparar(origen)
    if len(o) < 3:
        return 0.0
    else:
        s = set(_nucleos_para_comparar(salida))
        if not s:
            return 1.0
        else:
            return sum((1 for w in o if w in s)) / float(len(o))
def translate_cues(cues: list, from_code: str, to_code: str, progress_callback=None) -> list:
    try:
        import argostranslate.translate as at_translate
    except ImportError as e:
        que_falta = getattr(e, 'name', None) or ''
        if que_falta and (not que_falta.startswith('argostranslate')):
            raise SystemExit(tr('argostranslate está instalado pero le falta \'{modulo}\'.\nSi esto pasa en el programa compilado (no corriendo el código), es un problema del build, no tuyo: avisa para que se corrija el empaquetado.\nPara seguir mientras tanto: pip install {modulo}', modulo=que_falta))
        else:
            raise SystemExit(tr('Falta \'argostranslate\'. Instálalo con: pip install argostranslate\ny descarga el paquete de idioma una vez (ver docstring del script).'))
    def _pares_instalados():
        try:
            import argostranslate.package as package
            return {(p.from_code, p.to_code) for p in package.get_installed_packages()}
        except Exception:
            return set()
    pares = _pares_instalados()
    directo = (from_code, to_code) in pares
    via_en = not directo and from_code != 'en' and (to_code != 'en') and ((from_code, 'en') in pares) and (('en', to_code) in pares)
    if not directo and (not via_en):
            via_en = False
    def _traducir(texto):
        if via_en:
            return at_translate.translate(at_translate.translate(texto, from_code, 'en'), 'en', to_code)
        else:
            return at_translate.translate(texto, from_code, to_code)
    if via_en:
        print(f'  Traduccion {from_code}->{to_code} via ingles (no hay paquete directo).')
    grupos = _agrupar_cues_por_oracion(cues)
    translated = []
    total = len(grupos)
    for i, grupo in enumerate(grupos, start=1):
        texto_origen = ' '.join((' '.join(c.text.split()) for c in grupo))
        try:
            new_text = _traducir(texto_origen)
        except Exception as e:
            texto_error = str(e)
            cabeza = tr('No se pudo traducir {origen}->{destino}:', origen=from_code, destino=to_code)
            if 'stanza' in texto_error.lower():
                raise SystemExit(f'{cabeza} {texto_error}')
            else:
                if isinstance(e, OSError) or 'download' in texto_error.lower() or 'urlopen' in texto_error.lower():
                    raise SystemExit(f'{cabeza} {type(e).__name__}: {texto_error}\n' + tr('La primera traducción descarga el separador de frases (MiniSBD): necesita internet esa única vez. Revisa tu conexión y vuelve a intentarlo.'))
                else:
                    raise SystemExit(f'{cabeza} {type(e).__name__}: {texto_error}\n' + tr('¿Está instalado el paquete de ese par (o los dos eslabones {origen}->en y en->{destino})?', origen=from_code, destino=to_code))
        if from_code != to_code and _fraccion_sin_traducir(texto_origen, new_text) >= UMBRAL_SIN_TRADUCIR:
                alternativa = None
                if directo and from_code != 'en' and (to_code != 'en') and ((from_code, 'en') in pares) and (('en', to_code) in pares):
                                    try:
                                        alternativa = at_translate.translate(at_translate.translate(texto_origen, from_code, 'en'), 'en', to_code)
                                    except Exception:
                                        alternativa = None
                if alternativa is not None and _fraccion_sin_traducir(texto_origen, alternativa) < _fraccion_sin_traducir(texto_origen, new_text):
                    print(f'  Aviso: una frase salio sin traducir a la primera; la repesque via ingles: \'{texto_origen[:60]}\'')
                    new_text = alternativa
                else:
                    print(f'  Aviso: esta frase pudo salir sin traducir (revisala): \'{texto_origen[:60]}\'')
        partes = _repartir_palabras(new_text.split(), [max(1, len(c.text.split())) for c in grupo])
        for cue, parte in zip(grupo, partes):
            translated.append(Cue(start=cue.start, end=cue.end, text=' '.join(parte)))
        if progress_callback and total > 0:
                progress_callback(i / total)
    return translated
def format_timestamp(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
def write_dynamic(bloques: list, project_name: str, lang: str, out_dir: Path):
    """Guarda los subtitulos de 3 lineas y devuelve (json_path, srt_path).\n\n    Se guardan dos archivos:\n      - un .json con las tres partes separadas, que es lo que lee Resolve\n        para armar las 3 lineas con tipografias distintas;\n      - un .srt normal con la frase completa, util para revisar el texto\n        o para usarlo en cualquier otro programa.\n    """
    import dynamic_subtitles as dyn
    json_path = out_dir / f'{project_name}.{lang}.dynamic.json'
    _datos_din = {'language': lang, 'cues': bloques}
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(_datos_din, f, ensure_ascii=False, indent=2)
    sidecar_lua.escribir_sidecar(json_path, _datos_din)
    print(f'  -> {json_path}')
    srt_path = out_dir / f'{project_name}.{lang}.srt'
    cues_planos = [Cue(start=b['start'], end=b['end'], text=dyn.cue_to_plain_text(b)) for b in bloques]
    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, cue in enumerate(cues_planos, start=1):
            f.write(f'{i}\n')
            f.write(f'{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}\n')
            f.write(f'{cue.text}\n\n')
    print(f'  -> {srt_path}')
    return (json_path, srt_path)
def write_destacados(bloques: list, look: str, project_name: str, lang: str, out_dir: Path, estilo_pintado: dict=None, colores_pintado: dict=None, estilo_destacados: dict=None, pintado: dict=None):
    """Guarda los bloques del modo destacados y devuelve (json_path, srt_path).\n\n    Mismo formato de archivos que write_dynamic (un .json con los bloques\n    para Resolve, y un .srt de respaldo con la frase completa), pero el\n    .json lleva ademas \'look\' -y, si el look es \'pintado\', \'estilo_pintado\':\n    el font/size/tracking con el que dynamic_subtitles.build_destacados_cues\n    midio cada palabra. Tiene que viajar exacto: si el script de Resolve\n    dibujara con otro tamaño, las palabras quedarian corridas de su sitio\n    (ver medir_texto.py).\n\n    Desde v1.0.51 (los presets con motor) tambien pueden viajar:\n    \'colores_pintado\' {muda, dicha, clave} —el dorado editable del preset,\n    en vez de las constantes de fabrica de los gemelos— y\n    \'estilo_destacados\' {normal, resaltada} para los looks de un Text+ por\n    bloque (hoy: la degradacion del pintado a \'acumulativo\' conservando el\n    look elegido).\n    """
    import dynamic_subtitles as dyn
    json_path = out_dir / f'{project_name}.{lang}.destacados.json'
    datos = {'language': lang, 'look': look, 'cues': bloques}
    if estilo_pintado:
        datos['estilo_pintado'] = estilo_pintado
    if colores_pintado:
        datos['colores_pintado'] = colores_pintado
    if estilo_destacados:
        datos['estilo_destacados'] = estilo_destacados
    if pintado:
        datos['pintado'] = pintado
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    sidecar_lua.escribir_sidecar(json_path, datos)
    print(f'  -> {json_path}')
    srt_path = out_dir / f'{project_name}.{lang}.srt'
    cues_planos = [Cue(start=b['start'], end=b['end'], text=dyn.cue_to_plain_text(b)) for b in bloques]
    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, cue in enumerate(cues_planos, start=1):
            f.write(f'{i}\n')
            f.write(f'{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}\n')
            f.write(f'{cue.text}\n\n')
    print(f'  -> {srt_path}')
    return (json_path, srt_path)
def write_srt(cues: list, max_chars_per_line: int, max_lines: int, out_path: Path):
    partes = []
    for i, cue in enumerate(cues, start=1):
        wrapped = wrap_cue_text(cue.text, max_chars_per_line, max_lines)
        partes.append(f'{i}\n')
        partes.append(f'{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}\n')
        partes.append(f'{wrapped}\n\n')
    contenido = ''.join(partes)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(contenido)
    sidecar_lua.escribir_sidecar(out_path, {'texto': contenido})
    print(f'  -> {out_path}')
def main():
    parser = argparse.ArgumentParser(description='Transcribe video/audio y genera .srt para DaVinci Resolve')
    parser.add_argument('media', help='Ruta al archivo de video o audio')
    parser.add_argument('--source-lang', default='es', help='Idioma hablado en el archivo (código, ej: es, en). \'auto\' para detectar.')
    parser.add_argument('--langs', nargs='+', default=['es', 'en'], help='Idiomas de salida deseados, ej: --langs es en. El primero debe coincidir con el idioma predominante hablado si no usas --source-lang auto.')
    parser.add_argument('--max-chars', type=int, default=42, help='Máximo de caracteres por línea (default 42, estándar Netflix/YouTube)')
    parser.add_argument('--max-lines', type=int, default=2, help='Máximo de líneas por bloque de subtítulo (default 2)')
    parser.add_argument('--model', default='large-v3-turbo', help='Tamaño del modelo Whisper: tiny, base, small, medium, large-v3, large-v3-turbo')
    parser.add_argument('--project-name', default=None, help='Nombre para agrupar los archivos de salida (default: nombre del archivo de video)')
    parser.add_argument('--dynamic', action='store_true', help='Subtitulos dinamicos de 3 lineas (contexto / principal / complemento), agrupados por frases completas en vez de por cantidad de caracteres')
    parser.add_argument('--font-main', default='Open Sans', help='Tipografia del contexto y la linea principal (solo modo dinamico automatico)')
    parser.add_argument('--font-complement', default='Georgia', help='Tipografia del complemento, idealmente serif o caligrafica')
    parser.add_argument('--tracking', type=float, default=1.0, help='Interletrado de las 3 lineas (1.0 = normal)')
    args = parser.parse_args()
    SHARED_FOLDER.mkdir(parents=True, exist_ok=True)
    media_path = Path(args.media).expanduser().resolve()
    if not media_path.exists():
        raise SystemExit(f'No encuentro el archivo: {media_path}')
    else:
        project_name = args.project_name or media_path.stem
        words = transcribe(str(media_path), args.source_lang, args.model)
        if not words:
            raise SystemExit('Whisper no devolvió palabras. ¿El archivo tiene audio con voz?')
        else:
            base_lang = args.langs[0]
            manifest = {'project': project_name, 'tracks': []}
            if args.dynamic:
                import dynamic_subtitles as dyn
                print(f'\nConstruyendo subtítulos dinámicos de 3 líneas para \'{base_lang}\' (agrupando por frases completas)...')
                bloques = dyn.build_dynamic_cues(words)
                print('\nGenerando archivos:')
                json_path, base_srt_path = write_dynamic(bloques, project_name, base_lang, SHARED_FOLDER)
                manifest['tracks'].append({'language': base_lang, 'style': 'dynamic', 'data_path': str(json_path), 'srt_path': str(base_srt_path), 'fonts': {'main_family': args.font_main, 'complement_family': args.font_complement, 'tracking': args.tracking}})
                base_cues = [Cue(start=b['start'], end=b['end'], text=dyn.cue_to_plain_text(b)) for b in bloques]
            else:
                print(f'\nConstruyendo bloques de subtítulo para \'{base_lang}\' (máx {args.max_chars} car./línea, {args.max_lines} líneas)...')
                base_cues = build_cues(words, args.max_chars, args.max_lines)
                print('\nGenerando archivos .srt:')
                base_srt_path = SHARED_FOLDER / f'{project_name}.{base_lang}.srt'
                write_srt(base_cues, args.max_chars, args.max_lines, base_srt_path)
                manifest['tracks'].append({'language': base_lang, 'srt_path': str(base_srt_path)})
            for lang in args.langs[1:]:
                print(f'Traduciendo a \'{lang}\'...')
                translated_cues = translate_cues(base_cues, base_lang, lang)
                srt_path = SHARED_FOLDER / f'{project_name}.{lang}.srt'
                write_srt(translated_cues, args.max_chars, args.max_lines, srt_path)
                manifest['tracks'].append({'language': lang, 'srt_path': str(srt_path)})
            manifest_path = SHARED_FOLDER / 'subtitles_manifest.json'
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            print(f'\nListo. Manifest escrito en: {manifest_path}')
            print('Ahora abre DaVinci Resolve y corre Workspace > Scripts > CineCaptions')
if __name__ == '__main__':
    main()
