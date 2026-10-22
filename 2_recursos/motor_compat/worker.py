# CineCaptions · By Cinema Productions
# Servicio residente Python 3.14 para extensiones nativas no disponibles en 3.15.
"""Worker JSON-lines para Whisper, Argos Translate y ONNX Runtime."""
from __future__ import annotations

import contextlib
import importlib.metadata
import json
import os
import shutil
import sys
import threading
import time
import traceback
import types
import wave
from pathlib import Path

os.environ.setdefault('ARGOS_CHUNK_TYPE', 'MINISBD')
os.environ.setdefault('ARGOS_STANZA_AVAILABLE', '0')
_MODELOS = {}
_LOCK = threading.RLock()
_ACTIVOS = 0
_ULTIMO_USO = 0.0
_PESOS_MODELOS = {'large-v3-turbo': 1_620_000_000, 'large-v3': 3_100_000_000,
                  'medium': 1_530_000_000, 'small': 485_000_000,
                  'base': 145_000_000, 'tiny': 78_000_000}


def _compat_av():
    import av
    if getattr(av.open, '_cinecaptions_compat', False):
        return
    abrir = av.open

    def abrir_compat(*args, **kwargs):
        try:
            return abrir(*args, **kwargs)
        except TypeError:
            if 'metadata_errors' not in kwargs:
                raise
            kwargs.pop('metadata_errors')
            return abrir(*args, **kwargs)

    abrir_compat._cinecaptions_compat = True
    av.open = abrir_compat


def emitir(tipo, valor=''):
    if not isinstance(valor, str):
        valor = json.dumps(valor, ensure_ascii=False)
    sys.stdout.write(f'{tipo}|{valor}\n')
    sys.stdout.flush()


def progreso(valor, detalle=''):
    emitir('PROGRESO', f'{max(0.0, min(1.0, float(valor))):.6f}|{detalle}')


def _duracion(ruta):
    try:
        import av
        with av.open(str(ruta)) as contenedor:
            return float(contenedor.duration or 0) / 1_000_000
    except Exception:
        return 0.0


def _tamano_modelo(nombre):
    try:
        from faster_whisper.utils import _MODELS
        repo = _MODELS.get(nombre, nombre)
        import huggingface_hub
        carpeta = Path(huggingface_hub.constants.HF_HUB_CACHE) / ('models--' + repo.replace('/', '--'))
        return carpeta, repo
    except Exception:
        return Path.home() / '.cache' / 'huggingface' / 'hub', nombre


def _tamano_carpeta(carpeta):
    total = 0
    if carpeta.exists():
        for ruta in carpeta.rglob('*'):
            try:
                if ruta.is_file():
                    total += ruta.stat().st_size
            except OSError:
                continue
    return total


def _descargar_modelo(nombre):
    from faster_whisper.utils import download_model
    carpeta, _ = _tamano_modelo(nombre)
    try:
        download_model(nombre, local_files_only=True)
        progreso(1, 'Modelo ya descargado')
        return
    except Exception:
        pass
    emitir('ESTADO', f'Descargando el modelo Whisper {nombre}…')
    inicio = _tamano_carpeta(carpeta)
    salida = {}

    def descargar():
        try:
            salida['ruta'] = download_model(nombre)
        except Exception as exc:
            salida['error'] = exc

    hilo = threading.Thread(target=descargar, daemon=True, name='whisper-descarga')
    hilo.start()
    ultimo, sin_cambio = inicio, time.monotonic()
    esperado = _PESOS_MODELOS.get(nombre, 1_000_000_000)
    while hilo.is_alive():
        hilo.join(1)
        actual = _tamano_carpeta(carpeta)
        if actual > ultimo:
            ultimo, sin_cambio = actual, time.monotonic()
        progreso(min(.99, max(0, actual - inicio) / esperado),
                 f'{max(0, actual - inicio) / 1e6:.0f} MB')
        if time.monotonic() - sin_cambio > 120:
            raise RuntimeError('La descarga del modelo Whisper no avanza; revisa la conexión y vuelve a intentarlo.')
    if 'error' in salida:
        raise salida['error']
    progreso(1, 'Modelo descargado')


def _modelo(nombre, dispositivo, calculo, local_only=False):
    global _ULTIMO_USO
    _compat_av()
    clave = (nombre, dispositivo, calculo)
    with _LOCK:
        modelo = _MODELOS.get(clave)
        if modelo is not None:
            _ULTIMO_USO = time.monotonic()
            return modelo
        if not local_only:
            _descargar_modelo(nombre)
        emitir('ESTADO', f'Cargando Whisper {nombre} en {dispositivo.upper()}…')
        from faster_whisper import WhisperModel
        opciones = {'device': dispositivo, 'compute_type': calculo, 'local_files_only': local_only}
        if dispositivo == 'cpu':
            opciones['cpu_threads'] = min(8, os.cpu_count() or 4)
        modelo = WhisperModel(nombre, **opciones)
        _MODELOS.clear()
        _MODELOS[clave] = modelo
        _ULTIMO_USO = time.monotonic()
        return modelo


def _transcribir(datos):
    global _ACTIVOS, _ULTIMO_USO
    with _LOCK:
        _ACTIVOS += 1
        _ULTIMO_USO = time.monotonic()
    try:
        return _transcribir_activo(datos)
    finally:
        with _LOCK:
            _ACTIVOS = max(0, _ACTIVOS - 1)
            _ULTIMO_USO = time.monotonic()


def _transcribir_activo(datos):
    ruta = datos['audio']
    nombre = datos['modelo']
    idioma = datos.get('idioma') or 'auto'
    contexto = (datos.get('contexto') or '')[:600]
    dispositivo = 'cuda' if datos.get('cuda') else 'cpu'
    calculo = datos.get('compute_type') or 'float16'
    local_only = bool(datos.get('local_only'))
    emitir('ESTADO', f'Preparando Whisper {nombre} en {dispositivo.upper()}…')
    modelo = _modelo(nombre, dispositivo, calculo, local_only)
    emitir('CARGADO', '')
    idioma_modelo = idioma if idioma != 'auto' else None
    opciones = {'language': idioma_modelo, 'word_timestamps': True, 'vad_filter': True}
    if contexto:
        opciones['hotwords'] = contexto
    if dispositivo == 'cuda' and _duracion(ruta) > 45:
        try:
            from faster_whisper import BatchedInferencePipeline
            segmentos, info = BatchedInferencePipeline(modelo).transcribe(
                ruta, batch_size=8, **opciones)
        except Exception as exc:
            emitir('ESTADO', f'Lotes CUDA no disponibles; proceso normal: {exc}')
            segmentos, info = modelo.transcribe(ruta, **opciones)
    else:
        segmentos, info = modelo.transcribe(ruta, **opciones)
    total = float(getattr(info, 'duration', 0) or 0)
    palabras = []
    for segmento in segmentos:
        for palabra in (segmento.words or []):
            palabras.append({'start': palabra.start, 'end': palabra.end,
                             'word': palabra.word.strip()})
        if total:
            progreso(min(1, segmento.end / total), 'Transcribiendo')
    return {'palabras': palabras, 'idioma': str(info.language or '').lower(), 'modelo': nombre}


def _argos_instalados():
    _preparar_argos()
    import argostranslate.package as package
    return package.get_installed_packages()


def _preparar_argos():
    """Evita importar Stanza/PyTorch: Argos usa MiniSBD y solo necesita el símbolo al importar."""
    if 'stanza' in sys.modules:
        return
    stub = types.ModuleType('stanza')

    class PipelineSinStanza:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('El motor de traducción está configurado para MiniSBD y no debe usar Stanza.')

    stub.Pipeline = PipelineSinStanza
    sys.modules['stanza'] = stub


def _paquete_dict(p, instalado):
    return {'from': getattr(p, 'from_code', ''), 'to': getattr(p, 'to_code', ''),
            'nombre_from': getattr(p, 'from_name', '') or getattr(p, 'from_code', ''),
            'nombre_to': getattr(p, 'to_name', '') or getattr(p, 'to_code', ''),
            'instalado': bool(instalado)}


def _traducir(datos):
    _preparar_argos()
    import argostranslate.translate as translate
    origen, destino = datos['origen'], datos['destino']
    pares = {(p.from_code, p.to_code) for p in _argos_instalados()}
    directo = (origen, destino) in pares
    via_ingles = not directo and origen != 'en' and destino != 'en' and (origen, 'en') in pares and ('en', destino) in pares
    if not directo and not via_ingles:
        raise RuntimeError(f'No está instalado el paquete de traducción {origen}->{destino}.')
    textos = datos.get('textos', [])
    salida = []
    for i, texto in enumerate(textos, 1):
        if via_ingles:
            traducido = translate.translate(translate.translate(texto, origen, 'en'), 'en', destino)
        else:
            traducido = translate.translate(texto, origen, destino)
        if (directo and origen != 'en' and destino != 'en'
                and (origen, 'en') in pares and ('en', destino) in pares
                and _fraccion_sin_traducir(texto, traducido) >= .6):
            try:
                alternativo = translate.translate(translate.translate(texto, origen, 'en'), 'en', destino)
                if _fraccion_sin_traducir(texto, alternativo) < _fraccion_sin_traducir(texto, traducido):
                    emitir('ESTADO', f'La frase {origen}->{destino} se recuperó pasando por inglés.')
                    traducido = alternativo
            except Exception:
                pass
        salida.append(str(traducido))
        if textos:
            progreso(i / len(textos), 'Traduciendo')
    return salida


def _fraccion_sin_traducir(origen, salida):
    import re
    palabras_origen = [w for w in re.findall(r"[\w']+", str(origen or '').lower()) if len(w) >= 3]
    if len(palabras_origen) < 3:
        return 0.0
    palabras_salida = set(w for w in re.findall(r"[\w']+", str(salida or '').lower()) if len(w) >= 3)
    if not palabras_salida:
        return 1.0
    return sum(1 for w in palabras_origen if w in palabras_salida) / len(palabras_origen)


def _paquetes_disponibles(refrescar=True):
    _preparar_argos()
    import argostranslate.package as package
    instalados = _argos_instalados()
    pares = {(p.from_code, p.to_code) for p in instalados}
    if refrescar:
        try:
            emitir('ESTADO', 'Actualizando el catálogo de traducciones…')
            package.update_package_index()
        except Exception:
            return [_paquete_dict(p, True) for p in instalados]
    try:
        return [_paquete_dict(p, (p.from_code, p.to_code) in pares)
                for p in package.get_available_packages()]
    except Exception:
        return [_paquete_dict(p, True) for p in instalados]


def _instalar_paquete(datos):
    _preparar_argos()
    import argostranslate.package as package
    import argostranslate.settings as settings
    from urllib.request import urlopen
    if any(p.from_code == datos['origen'] and p.to_code == datos['destino'] for p in _argos_instalados()):
        return {'instalado': True}
    ruta = Path(settings.local_package_index)
    if not ruta.exists():
        emitir('ESTADO', 'Descargando el catálogo de traducciones…')
        with urlopen(settings.remote_package_index, timeout=60) as respuesta:
            contenido = respuesta.read()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(contenido)
    emitir('ESTADO', f'Descargando traducción {datos["origen"]}->{datos["destino"]}…')
    package.update_package_index()
    resultado = package.install_package_for_language_pair(datos['origen'], datos['destino'])
    return {'instalado': bool(resultado)}


def _mate(datos):
    global _ACTIVOS, _ULTIMO_USO
    with _LOCK:
        _ACTIVOS += 1
        _ULTIMO_USO = time.monotonic()
    try:
        return _mate_activo(datos)
    finally:
        with _LOCK:
            _ACTIVOS = max(0, _ACTIVOS - 1)
            _ULTIMO_USO = time.monotonic()


def _mate_activo(datos):
    global _ULTIMO_USO
    import numpy as np
    from PIL import Image
    import onnxruntime as ort
    entrada = Path(datos['entrada'])
    salida = Path(datos['salida'])
    modelo = datos.get('modelo')
    if not modelo or not Path(modelo).is_file():
        raise RuntimeError('Falta el modelo MODNet para recorte de persona.')
    alto = max(32, int(round(int(datos.get('alto', 512)) / 32.0)) * 32)
    rgb = np.load(entrada, allow_pickle=False)
    h, w = rgb.shape[:2]
    ancho = max(32, int(round(w * alto / h / 32.0)) * 32)
    imagen = np.asarray(Image.fromarray(rgb).resize((ancho, alto), Image.BILINEAR), dtype=np.float32)
    imagen = ((imagen / 255.0 - .5) / .5).transpose(2, 0, 1)[None]
    clave = str(Path(modelo).resolve())
    with _LOCK:
        sesion = _MODELOS.get(('onnx', clave))
        if sesion is None:
            opciones = ort.SessionOptions()
            opciones.log_severity_level = 3
            preferidos = [p for p in ('CUDAExecutionProvider', 'DmlExecutionProvider', 'CoreMLExecutionProvider')
                          if p in ort.get_available_providers()]
            sesion = ort.InferenceSession(clave, sess_options=opciones,
                                          providers=preferidos + ['CPUExecutionProvider'])
            _MODELOS[('onnx', clave)] = sesion
        _ULTIMO_USO = time.monotonic()
    alfa = np.clip(sesion.run(None, {sesion.get_inputs()[0].name: imagen})[0][0, 0], 0, 1)
    np.save(salida, alfa, allow_pickle=False)
    return {'alto': int(alfa.shape[0]), 'ancho': int(alfa.shape[1])}


def _versiones():
    paquetes = ('anyio', 'av', 'certifi', 'click', 'cloudpickle', 'colorama',
                'ctranslate2', 'faster-whisper', 'filelock', 'flatbuffers', 'fsspec',
                'h11', 'hf-xet', 'httpcore2', 'httpx2', 'huggingface-hub', 'idna',
                'joblib', 'minisbd', 'numpy', 'onnxruntime', 'packaging', 'pillow',
                'protobuf', 'PyYAML', 'regex', 'sacremoses', 'sentencepiece', 'six',
                'tokenizers', 'truststore', 'tqdm', 'typing-extensions', 'argostranslate')
    salida = {}
    for nombre in paquetes:
        try:
            salida[nombre.lower().replace('_', '-')] = importlib.metadata.version(nombre)
        except importlib.metadata.PackageNotFoundError:
            pass
    salida['_python'] = '.'.join(map(str, sys.version_info[:3]))
    return salida


def atender(op, datos):
    if op == 'verificar':
        versiones = _versiones()
        import ctranslate2
        import faster_whisper  # noqa: F401
        import onnxruntime  # noqa: F401
        _preparar_argos()
        import argostranslate.translate  # noqa: F401
        return {'instalado': True, 'python': versiones.get('_python'), 'versiones': versiones,
                'cuda': int(ctranslate2.get_cuda_device_count())}
    if op == 'cuda':
        import ctranslate2
        return {'dispositivos': int(ctranslate2.get_cuda_device_count())}
    if op == 'precargar':
        import ctranslate2
        if ctranslate2.get_cuda_device_count() <= 0:
            return {'cargado': False}
        nombre = datos['modelo']
        _modelo(nombre, 'cuda', datos.get('compute_type') or 'float16', local_only=True)
        return {'cargado': True}
    if op == 'liberar':
        with _LOCK:
            _MODELOS.clear()
        return {'liberado': True}
    if op == 'transcribir':
        return _transcribir(datos)
    if op == 'descargar_modelo':
        _descargar_modelo(datos['modelo'])
        return {'descargado': True}
    if op == 'traducir':
        return {'textos': _traducir(datos)}
    if op == 'paquetes_instalados':
        return {'paquetes': [_paquete_dict(p, True) for p in _argos_instalados()]}
    if op == 'paquetes_disponibles':
        return {'paquetes': _paquetes_disponibles(bool(datos.get('refrescar', True)))}
    if op == 'instalar_paquete':
        return _instalar_paquete(datos)
    if op == 'audio_16k':
        import numpy as np
        _compat_av()
        from faster_whisper.audio import decode_audio
        muestras = decode_audio(str(datos['audio']), sampling_rate=16000)
        pcm = (np.clip(muestras, -1.0, 1.0) * 32767).astype('<i2')
        with wave.open(str(datos['salida']), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(pcm.tobytes())
        return {'salida': datos['salida']}
    if op == 'mate':
        return _mate(datos)
    if op == 'descargar_modnet':
        from huggingface_hub import hf_hub_download
        destino = Path(datos['destino'])
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = Path(hf_hub_download('Xenova/modnet', 'onnx/model.onnx'))
        if temporal.resolve() != destino.resolve():
            shutil.copy2(temporal, destino)
        return {'destino': str(destino)}
    raise ValueError(f'Operación desconocida: {op}')


def servidor():
    def soltar_inactivo():
        global _ULTIMO_USO
        while True:
            time.sleep(20)
            with _LOCK:
                if _MODELOS and not _ACTIVOS and time.monotonic() - _ULTIMO_USO > 240:
                    _MODELOS.clear()
                    _ULTIMO_USO = 0.0

    threading.Thread(target=soltar_inactivo, daemon=True, name='modelos-inactivos').start()
    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            if linea == 'salir':
                break
            solicitud = json.loads(linea)
            with contextlib.redirect_stdout(sys.stderr):
                resultado = atender(solicitud.get('operacion', ''), solicitud)
            emitir('LISTO', resultado)
        except BaseException as exc:
            detalle = f'{type(exc).__name__}: {exc}'
            emitir('ERROR', detalle)
            traceback.print_exc(file=sys.stderr)
    with _LOCK:
        _MODELOS.clear()


if __name__ == '__main__':
    if '--versiones' in sys.argv:
        print(json.dumps(_versiones(), ensure_ascii=False))
    elif '--servidor' in sys.argv:
        servidor()
    else:
        raise SystemExit('Uso: worker.py --versiones|--servidor')
