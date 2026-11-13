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


_SALIDA = sys.stdout                      # la tubería con la app (atender() corre con stdout desviado a stderr: lo que imprima una librería no la ensucia)
_SALIDA_LOCK = threading.Lock()


def emitir(tipo, valor=''):
    """v5.57: SIEMPRE a la tubería. Antes, dentro de atender(), ESTADO y PROGRESO iban a stderr con todo lo demás: la app no los veía (ni la
    barra ni el Registro) y, sin señal, cortaba a los 180 s una transcripción en CPU o una descarga larga del modelo."""
    if not isinstance(valor, str):
        valor = json.dumps(valor, ensure_ascii=False)
    with _SALIDA_LOCK:
        _SALIDA.write(f'{tipo}|{valor}\n')
        _SALIDA.flush()


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


_MATE_PIXELES = 3_000_000                 # tope de las sesiones de MODNet guardadas en la GPU, en píxeles de entrada: cada millón ocupa ~0,55 GB
                                          # de memoria de vídeo (medido: 1824×1024 = 1,1 GB); con Resolve abierto, tres sesiones de un 4K la
                                          # desbordaban y cada pasada iba a 0,9 s en vez de 0,03
_MATE = {'gpu': None, 'dims': {}}         # gpu: proveedor elegido ('' = CPU) · dims: nombres de las dimensiones de la entrada por modelo


def _sesion_mate(ort, clave, alto, ancho):
    """v5.57 (el usuario: «no debería tardar 8 minutos»): MODNet en la GPU si este onnxruntime la trae (en Windows, onnxruntime-directml:
    cualquier tarjeta DX12, sin las librerías de CUDA) y, si no, en la CPU como siempre. DirectML solo va rápido con la PRIMERA forma que ve
    una sesión (las demás, 45-50 ms en vez de 3-6): con GPU, una sesión por forma con las dimensiones FIJAS (las _MATE_FORMAS últimas). El alfa
    sale igual que en la CPU (medido: 0,03/255). En CUDA, sin TF32: con TF32 el alfa cambiaba hasta 127/255 en los bordes. Las sesiones de la
    GPU se guardan mientras quepan en _MATE_PIXELES (fuera la usada hace más; antes de crear la nueva, para dejarle sitio). Llamar con _LOCK."""
    opciones = ort.SessionOptions()
    opciones.log_severity_level = 3
    if _MATE['gpu'] is None:
        _MATE['gpu'] = next((p for p in ('DmlExecutionProvider', 'CUDAExecutionProvider', 'CoreMLExecutionProvider')
                             if p in ort.get_available_providers()), '')
    gpu = _MATE['gpu']
    if not gpu:
        sesion = _MODELOS.get(('onnx', clave))
        if sesion is None:
            sesion = _MODELOS[('onnx', clave)] = ort.InferenceSession(clave, sess_options=opciones,
                                                                      providers=['CPUExecutionProvider'])
        return sesion
    k = ('onnx', clave, alto, ancho)
    sesion = _MODELOS.pop(k, None)
    if sesion is None:
        ocupado = alto * ancho
        for x in reversed([x for x in _MODELOS if len(x) == 4 and x[:2] == ('onnx', clave)]):     # (de la más reciente a la más vieja)
            if ocupado + x[2] * x[3] > _MATE_PIXELES:
                del _MODELOS[x]
            else:
                ocupado += x[2] * x[3]
        dims = _MATE['dims'].get(clave)
        if dims is None:                                               # (los nombres que fijar: los de la entrada del modelo)
            dims = _MATE['dims'][clave] = ort.InferenceSession(clave, sess_options=opciones,
                                                               providers=['CPUExecutionProvider']).get_inputs()[0].shape
        for nombre, valor in zip(dims, (1, 3, alto, ancho)):
            if isinstance(nombre, str):
                opciones.add_free_dimension_override_by_name(nombre, valor)
        ajustes = {}
        if gpu == 'DmlExecutionProvider':                             # (DirectML no admite ni lo uno ni lo otro; la tarjeta: la más potente
            opciones.enable_mem_pattern = False                        # de verdad, la dedicada en un portátil con dos)
            opciones.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            ajustes = {'performance_preference': 'high_performance', 'device_filter': 'gpu'}
        elif gpu == 'CUDAExecutionProvider':
            ajustes = {'use_tf32': '0'}
        elif gpu == 'CoreMLExecutionProvider':                         # (v5.86, Mac: la tarjeta de Apple, sin el Neural Engine, que va en
            ajustes = {'ModelFormat': 'MLProgram', 'MLComputeUnits': 'CPUAndGPU'}   # 16 bits; el 1.er alfa se compara con la CPU: _mate_activo)
        try:
            sesion = ort.InferenceSession(clave, sess_options=opciones, providers=[(gpu, ajustes), 'CPUExecutionProvider'])
        except Exception:
            traceback.print_exc(file=sys.stderr)
            sesion = None
        if sesion is None or sesion.get_providers()[0] != gpu:         # (la GPU no arrancó: este motor sigue en la CPU)
            _MATE['gpu'] = ''
            return _sesion_mate(ort, clave, alto, ancho)
    _MODELOS[k] = sesion                                               # (al final: la usada más hace poco)
    return sesion


_MATE_TOLERANCIA = 2 / 255                # diferencia máxima con la CPU para quedarse con la GPU (DirectML: 0,03/255)


def _comparar_con_cpu(ort, clave, imagen, alfa):
    """v5.86 (Mac): CoreML puede calcular en 16 bits según el equipo y en las Macs de GitHub no hay tarjeta con la que medirlo. El primer
    alfa de la GPU se compara con el de la CPU: si se aparta más de _MATE_TOLERANCIA, todo el recorte sigue en la CPU (y vale el de la CPU)."""
    import numpy as np
    opciones = ort.SessionOptions()
    opciones.log_severity_level = 3
    with _LOCK:
        cpu = _MODELOS.get(('onnx', clave))
        if cpu is None:
            cpu = _MODELOS[('onnx', clave)] = ort.InferenceSession(clave, sess_options=opciones, providers=['CPUExecutionProvider'])
    referencia = cpu.run(None, {cpu.get_inputs()[0].name: imagen})[0][0, 0]
    diferencia = float(np.abs(np.clip(alfa, 0, 1) - np.clip(referencia, 0, 1)).max())
    with _LOCK:
        if diferencia <= _MATE_TOLERANCIA:
            _MATE['igual_cpu'] = True
            del _MODELOS[('onnx', clave)]                              # (la de la CPU ya no hace falta)
            print(f'mate: CoreML igual que la CPU (máx. {diferencia * 255:.2f}/255)', file=sys.stderr)
            return alfa
        print(f'mate: CoreML se aparta {diferencia * 255:.1f}/255 de la CPU: el recorte sigue en la CPU', file=sys.stderr)
        _MATE['gpu'] = ''
        for x in [x for x in _MODELOS if x[0] == 'onnx' and len(x) == 4]:
            del _MODELOS[x]
    return referencia


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
        sesion = _sesion_mate(ort, clave, alto, ancho)
        _ULTIMO_USO = time.monotonic()
    try:
        alfa = sesion.run(None, {sesion.get_inputs()[0].name: imagen})[0][0, 0]
    except Exception:
        if not _MATE['gpu']:
            raise
        traceback.print_exc(file=sys.stderr)                           # (la GPU falló en marcha: este fotograma y los demás, en la CPU)
        with _LOCK:
            _MATE['gpu'] = ''
            for x in [x for x in _MODELOS if x[0] == 'onnx']:
                del _MODELOS[x]
            sesion = _sesion_mate(ort, clave, alto, ancho)
        alfa = sesion.run(None, {sesion.get_inputs()[0].name: imagen})[0][0, 0]
    if _MATE['gpu'] == 'CoreMLExecutionProvider' and not _MATE.get('igual_cpu'):
        alfa = _comparar_con_cpu(ort, clave, imagen, alfa)
    alfa = np.clip(alfa, 0, 1)
    np.save(salida, alfa, allow_pickle=False)
    return {'alto': int(alfa.shape[0]), 'ancho': int(alfa.shape[1]), 'gpu': _MATE['gpu'] or ''}


def _detector(activo, datos):
    """_caras_activo / _cuerpos_activo contando como trabajo en curso (el servicio no se cierra por inactividad a mitad)."""
    global _ACTIVOS, _ULTIMO_USO
    with _LOCK:
        _ACTIVOS += 1
        _ULTIMO_USO = time.monotonic()
    try:
        return activo(datos)
    finally:
        with _LOCK:
            _ACTIVOS = max(0, _ACTIVOS - 1)
            _ULTIMO_USO = time.monotonic()


def _sesion_cpu(tipo, modelo):
    """La sesión de ONNX Runtime en la CPU de un detector pequeño (caras, personas), cargada una vez."""
    global _ULTIMO_USO
    import onnxruntime as ort
    clave = (tipo, str(Path(modelo).resolve()))
    with _LOCK:
        sesion = _MODELOS.get(clave)
        if sesion is None:
            opciones = ort.SessionOptions()
            opciones.log_severity_level = 3
            sesion = _MODELOS[clave] = ort.InferenceSession(clave[1], sess_options=opciones, providers=['CPUExecutionProvider'])
        _ULTIMO_USO = time.monotonic()
    return sesion


def _iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _caras_activo(datos):
    """v5.58 (el usuario: «que solo detecte humanos»): las CARAS de una imagen con YuNet (OpenCV Zoo, licencia MIT) sin OpenCV: la entrada en
    BGR 0-255 sin normalizar, con el alto y el ancho múltiplos de 32 (relleno abajo y a la derecha), y la decodificación de FaceDetectorYN
    (por paso 8/16/32: puntuación = √(cls·obj), centro = (celda + desplazamiento)·paso, lado = e^x·paso) con NMS 0,3. En la CPU: es pequeño
    (10-20 ms un fotograma a 640 px) y no se pelea con MODNet por la tarjeta. → {'caras': [[x0, y0, x1, y1, puntuación, y los 5 puntos (ojo
    derecho, ojo izquierdo, nariz, boca derecha, boca izquierda) en x, y]]}, en fracciones de la imagen."""
    import numpy as np
    modelo = datos.get('modelo')
    if not modelo or not Path(modelo).is_file():
        raise RuntimeError('Falta el detector de caras (YuNet).')
    rgb = np.load(Path(datos['entrada']), allow_pickle=False)
    h, w = rgb.shape[:2]
    umbral = float(datos.get('umbral') or 0.6)
    pw, ph = (w + 31) // 32 * 32, (h + 31) // 32 * 32
    lienzo = np.zeros((ph, pw, 3), np.float32)
    lienzo[:h, :w] = rgb[..., ::-1]
    sesion = _sesion_cpu('caras', modelo)
    salidas = dict(zip([o.name for o in sesion.get_outputs()],
                       sesion.run(None, {sesion.get_inputs()[0].name: lienzo.transpose(2, 0, 1)[None]})))
    caras = []
    for paso in (8, 16, 32):
        cols = pw // paso
        cls, obj = salidas[f'cls_{paso}'].reshape(-1), salidas[f'obj_{paso}'].reshape(-1)
        caja, puntos = salidas[f'bbox_{paso}'].reshape(-1, 4), salidas[f'kps_{paso}'].reshape(-1, 10)
        puntuacion = np.sqrt(np.clip(cls, 0, 1) * np.clip(obj, 0, 1))
        for i in np.nonzero(puntuacion >= umbral)[0]:
            r, c = divmod(int(i), cols)
            cx, cy = (c + caja[i, 0]) * paso, (r + caja[i, 1]) * paso
            bw, bh = np.exp(caja[i, 2]) * paso, np.exp(caja[i, 3]) * paso
            f = [(cx - bw / 2) / w, (cy - bh / 2) / h, (cx + bw / 2) / w, (cy + bh / 2) / h, float(puntuacion[i])]
            for j in range(5):
                f += [(puntos[i, 2 * j] + c) * paso / w, (puntos[i, 2 * j + 1] + r) * paso / h]
            caras.append([round(float(x), 5) for x in f])
    caras.sort(key=lambda f: -f[4])
    quedan = []
    for f in caras:
        if all(_iou(f, g) < 0.3 for g in quedan):
            quedan.append(f)
    return {'caras': quedan}


def _cuerpos_activo(datos):
    """v5.58 (que cuenten también las personas de ESPALDAS, que no tienen cara): las PERSONAS de una imagen con NanoDet-Plus (OpenCV Zoo,
    licencia Apache 2.0; solo la clase 0 de COCO) sin OpenCV: la imagen (lado mayor ≤ 416) centrada en un lienzo negro de 416 × 416, en BGR
    normalizada como se entrenó (media 103,53/116,28/123,675; desviación 57,375/57,12/58,395), y la decodificación de NanoDet (por paso
    8/16/32: las clases ya salen con sigmoide; cada lado de la caja, la esperanza de sus 8 casillas con softmax × paso desde el centro de la
    celda) con NMS 0,6. En la CPU (15-25 ms). → {'cuerpos': [[x0, y0, x1, y1, puntuación]]}, en fracciones de la imagen."""
    import numpy as np
    modelo = datos.get('modelo')
    if not modelo or not Path(modelo).is_file():
        raise RuntimeError('Falta el detector de personas (NanoDet).')
    rgb = np.load(Path(datos['entrada']), allow_pickle=False)
    lado = 416
    h, w = rgb.shape[:2]
    if max(h, w) > lado:
        from PIL import Image
        k = lado / float(max(h, w))
        rgb = np.asarray(Image.fromarray(rgb).resize((max(1, round(w * k)), max(1, round(h * k))), Image.BILINEAR))
        h, w = rgb.shape[:2]
    umbral = float(datos.get('umbral') or 0.5)
    x0, y0 = (lado - w) // 2, (lado - h) // 2
    lienzo = np.zeros((lado, lado, 3), np.float32)
    lienzo[y0:y0 + h, x0:x0 + w] = rgb[..., ::-1]
    lienzo = (lienzo - np.array([103.53, 116.28, 123.675], np.float32)) / np.array([57.375, 57.12, 58.395], np.float32)
    sesion = _sesion_cpu('cuerpos', modelo)
    por_n = {}
    for o in sesion.run(None, {sesion.get_inputs()[0].name: lienzo.transpose(2, 0, 1)[None]}):
        por_n.setdefault(int(o.shape[1]), {})[int(o.shape[2])] = o[0]          # (clases [1, n, 80] y cajas [1, n, 32] de cada paso, por n)
    cuerpos = []
    for paso in (8, 16, 32):
        n = lado // paso
        par = por_n.get(n * n) or {}
        if 80 not in par or 32 not in par:
            continue
        p = par[80][:, 0]
        k = np.nonzero(p >= umbral)[0]
        if not len(k):
            continue
        r = par[32][k].reshape(-1, 8)
        e = np.exp(r - r.max(axis=1, keepdims=True))
        d = ((e / e.sum(axis=1, keepdims=True)) @ np.arange(8, dtype=np.float32)).reshape(-1, 4) * paso
        cx, cy = (k % n) * paso + 0.5 * (paso - 1), (k // n) * paso + 0.5 * (paso - 1)
        for i in range(len(k)):
            caja = [(cx[i] - d[i, 0] - x0) / w, (cy[i] - d[i, 1] - y0) / h, (cx[i] + d[i, 2] - x0) / w, (cy[i] + d[i, 3] - y0) / h]
            cuerpos.append([round(float(min(1.0, max(0.0, v))), 5) for v in caja] + [round(float(p[k[i]]), 4)])
    cuerpos.sort(key=lambda f: -f[4])
    quedan = []
    for f in cuerpos:
        if all(_iou(f, g) < 0.6 for g in quedan):
            quedan.append(f)
    return {'cuerpos': quedan}


def _versiones():
    paquetes = ('anyio', 'av', 'certifi', 'click', 'cloudpickle', 'colorama',
                'ctranslate2', 'faster-whisper', 'filelock', 'flatbuffers', 'fsspec',
                'h11', 'hf-xet', 'httpcore2', 'httpx2', 'huggingface-hub', 'idna',
                'joblib', 'minisbd', 'numpy', 'onnxruntime', 'onnxruntime-directml', 'onnxruntime-gpu', 'packaging', 'pillow',
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
        versiones.setdefault('onnxruntime', versiones.get('onnxruntime-directml') or versiones.get('onnxruntime-gpu'))   # (v5.57: el chequeo lo muestra igual)
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
    if op == 'caras':
        return _detector(_caras_activo, datos)
    if op == 'cuerpos':
        return _detector(_cuerpos_activo, datos)
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
