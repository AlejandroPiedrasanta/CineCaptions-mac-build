# CineCaptions · By Cinema Productions
# 1_codigo/salud.py — chequeo de librerías al arrancar (versiones fijadas, motor de IA, MCP).
"""
salud.py  (v5.2)
----------------
El chequeo de librerias que corre SIEMPRE al arrancar (en un hilo, sin frenar
la ventana). Pedido: «que siempre haga chequeos de librerías... no quiero nada
obsoleto».

Mira, para cada pieza:
  * que la libreria cargue y que su version sea la FIJADA en
    3_compilar/requirements.txt (las versiones van fijas a proposito: PyAV 19
    rompe faster-whisper 1.2.1; una mas nueva no es mejor si rompe);
  * el motor de IA (Python 3.14 propio): torch, las librerias del lock y los
    modelos de Qwen3 en la cache;
  * el MCP oficial de Resolve (21.1+).

Devuelve una lista de filas {'nombre', 'ok', 'detalle'} que pintan
«Detalles > Estado del sistema» y Ajustes > Ayuda.
"""
import importlib
import time

# (modulo a importar, nombre visible, version fijada)
LIBRERIAS = (
    ('PySide6', 'Qt (PySide6)', '6.12.0'),
    ('qtawesome', 'Iconos (QtAwesome)', '1.4.2'),
    ('numpy', 'NumPy', '2.5.4'),
    ('PIL', 'Pillow', '13.0.0'),                      # (v5.5.10: subió con 3_compilar/requirements.txt; las dos van juntas)
    ('av', 'PyAV (FFmpeg)', '19.0.1'),
    ('ctranslate2', 'CTranslate2', '4.8.3'),          # (la de 3_compilar/requirements.txt; v5.5.4: decía 4.8.2 y cada arranque salía «Falla al iniciar»)
    ('faster_whisper', 'faster-whisper', '1.2.1'),
    ('onnxruntime', 'ONNX Runtime', '1.31.0'),
    ('tokenizers', 'tokenizers', '0.23.3'),
    ('huggingface_hub', 'Hugging Face Hub', '2.2.0'),
    ('spellchecker', 'pyspellchecker', '0.9.1'),
    ('pynput', 'pynput', '1.8.2'),
    ('argostranslate', 'Argos Translate', None),
)

_ULTIMO = {'filas': None, 'cuando': 0.0}


def _version(mod):
    for attr in ('__version__', 'VERSION', 'version'):
        v = getattr(mod, attr, None)
        if isinstance(v, str):
            return v
    try:
        from importlib.metadata import version
        return version(mod.__name__)
    except Exception:
        return None


def smart_app_control():
    """v5.5.6: el estado del «Control inteligente de aplicaciones» de Windows 11: 'activado', 'evaluacion', 'desactivado' o None (no es Windows 11 o
    no se pudo leer). Activado (o en evaluación) bloquea librerías sin firma digital: error 0xc0e90002, «Bad Image»."""
    import sys
    if not sys.platform.startswith('win'):
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\CI\Policy') as k:
            v, _t = winreg.QueryValueEx(k, 'VerifiedAndReputablePolicyState')
        return {1: 'activado', 2: 'evaluacion', 0: 'desactivado'}.get(int(v))
    except OSError:
        return None


def _bloqueo_de_windows(e):
    """¿La librería no cargó porque Smart App Control la bloqueó? (un fallo al cargar su DLL con el control activado o en evaluación)"""
    t = str(e)
    return ('0xc0e90002' in t.lower() or 'DLL load failed' in t or isinstance(e, OSError)) and smart_app_control() in ('activado', 'evaluacion')


def _compatible(v, fijada):
    """v5.5.4: la misma versión, o un parche más nuevo de la misma serie (4.8.3 con 4.8.2 fijada): eso no es una falla."""
    if v == fijada:
        return True
    try:
        a, b = [int(x) for x in v.split('.')[:3]], [int(x) for x in fijada.split('.')[:3]]
        return len(a) == len(b) == 3 and a[:2] == b[:2] and a[2] >= b[2]
    except ValueError:
        return False


def comprobar():
    """Carga cada libreria y compara su version. Tarda 1-3 s: llamar en un hilo."""
    filas = []
    for modulo, nombre, fijada in LIBRERIAS:
        t = time.perf_counter()
        try:
            mod = importlib.import_module(modulo)
            v = _version(mod)
            ok = fijada is None or v is None or _compatible(str(v).split('+')[0], fijada)
            detalle = (v or '?') + ('' if ok else f' (esperada {fijada})')
            filas.append({'nombre': nombre, 'ok': ok, 'detalle': detalle,
                          'ms': round((time.perf_counter() - t) * 1000)})
        except Exception as e:
            detalle = f'no carga: {type(e).__name__}: {e}'[:160]
            if _bloqueo_de_windows(e):
                detalle = 'Windows la bloqueó (Control inteligente de aplicaciones / Smart App Control)'
            filas.append({'nombre': nombre, 'ok': False, 'detalle': detalle})
    # el motor de IA (su propio Python)
    try:
        import motor_voz
        if motor_voz.python_motor().exists():
            faltan = motor_voz._faltan_requisitos()
            torch_v = motor_voz._dist_instalada('torch')
            modelos = motor_voz.detectar_por_archivos()
            ok = not faltan and bool(torch_v) and bool(modelos and modelos.get('modelo_texto'))
            if ok:
                detalle = f"torch {torch_v} · Qwen3-ASR {modelos.get('modelo')} · IA de texto {modelos.get('modelo_texto')}"
            elif faltan:
                detalle = f'faltan {len(faltan)} librerías: ' + ', '.join(faltan[:3])
            else:
                detalle = 'faltan modelos: Ajustes > General > Motor de voz > Reparar'
            filas.append({'nombre': 'Motor de IA (Qwen3)', 'ok': ok, 'detalle': detalle})
        else:
            filas.append({'nombre': 'Motor de IA (Qwen3)', 'ok': None, 'detalle': 'no instalado (se usa Whisper)'})
    except Exception as e:
        filas.append({'nombre': 'Motor de IA (Qwen3)', 'ok': False, 'detalle': str(e)[:160]})
    try:                                   # v5.4.8: la GPU para Whisper (antes el chequeo decía «todo en orden» aunque faltara cuBLAS y la voz cayera a la CPU)
        import cuda_libs
        d = cuda_libs.diagnostico()
        if d['estado'] in ('ok', 'faltan'):
            filas.append({'nombre': 'GPU para la voz (CUDA)', 'ok': d['estado'] == 'ok', 'detalle': cuda_libs.texto_diagnostico(d)})
        elif d['estado'] == 'sin_gpu':
            filas.append({'nombre': 'GPU para la voz (CUDA)', 'ok': None, 'detalle': cuda_libs.texto_diagnostico(d)})
    except Exception as e:
        filas.append({'nombre': 'GPU para la voz (CUDA)', 'ok': False, 'detalle': str(e)[:160]})
    try:
        import resolve_mcp
        exe = resolve_mcp.ruta_exe()
        if exe is not None:
            filas.append({'nombre': 'MCP de DaVinci Resolve', 'ok': True, 'detalle': str(exe)})
        else:                                  # v5.4.18: sin MCP no es una falla: DaVinci Resolve Free (o un Studio sin él) trabaja por el Puente
            filas.append({'nombre': 'MCP de DaVinci Resolve', 'ok': None, 'detalle': 'no hace falta: DaVinci Resolve Free trabaja por el Puente (el MCP es de Studio 21.1)'})
    except Exception as e:
        filas.append({'nombre': 'MCP de DaVinci Resolve', 'ok': False, 'detalle': str(e)[:160]})
    _ULTIMO.update(filas=filas, cuando=time.time())
    return filas


def ultimo():
    return _ULTIMO['filas']


def resumen(filas=None):
    """('Todo al día (12 de 12)', True) o ('2 con problemas: …', False)."""
    filas = filas if filas is not None else (_ULTIMO['filas'] or [])
    if not filas:
        return ('…', None)
    malas = [f for f in filas if f['ok'] is False]
    total = len([f for f in filas if f['ok'] is not None])
    if not malas:
        from i18n import tr
        return (tr('Todo al día ({n} de {t})', n=total, t=total), True)
    from i18n import tr
    return (tr('{n} con problemas: {lista}', n=len(malas), lista=', '.join(f['nombre'] for f in malas[:3])), False)


def informe(filas=None):
    filas = filas if filas is not None else (_ULTIMO['filas'] or [])
    lineas = []
    for f in filas:
        marca = 'OK ' if f['ok'] else ('-- ' if f['ok'] is None else 'MAL')
        lineas.append(f"{marca} {f['nombre']:<26} {f['detalle']}")
    return '\n'.join(lineas)
