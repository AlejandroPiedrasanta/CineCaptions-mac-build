# CineCaptions · By Cinema Productions
# 1_codigo/vigilancia.py — guardián de tareas largas (GO, Generar): detecta atascos, destraba motores, chequeos periódicos y arranque atascado.
"""
vigilancia.py  (v5.11)
----------------------
Pedido: «que no se quede trabado; si algo falla, que se vea en el registro; si el modelo falla, cambiarlo solo; si no pasa del inicio, avisar».

Tres piezas, todas en hilos propios (nunca en el de la interfaz) y sin dependencias fuera de la librería estándar:

  1. TAREAS: `iniciar('go', ...)` / `latido('go', paso)` / `terminar('go')`. Un hilo mira cada 2 s cuánto hace que la tarea no da señales.
     Pasado el umbral de AVISO anota en el Registro el paso, los segundos y la pila del hilo de trabajo; pasado el de ATASCO lo anota como error,
     avisa a la interfaz y llama a `al_atasco` (en la app: matar los motores de voz / IA de texto, lo que hace que cada uno CAMBIE SOLO al motor de respaldo).
     Al terminar deja una línea con lo que tardó cada paso (para ver cuál se arrastra) y borra `tarea_en_curso.json`; si el programa se cae a medias,
     el siguiente arranque lo dice («se cortó durante GO, en el paso voz»).
  2. MONITOR: cada 60 s mira disco libre, memoria libre y que la carpeta de datos se pueda escribir; solo anota cuando algo CAMBIA (aparece / se arregla).
  3. ARRANQUE: si la ventana no termina de abrir en N segundos anota un error con la pila de TODOS los hilos (qué se quedó esperando) y la marca de sesión
     queda en «abriendo» para que el siguiente arranque avise de que el anterior no llegó a abrir.
"""
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

CARPETA = Path.home() / 'DaVinciSubtitles'
TAREA_EN_CURSO = CARPETA / 'tarea_en_curso.json'

# segundos SIN señal (aviso, atasco) por paso; 'defecto' vale para el resto
UMBRALES = {
    'defecto': (45, 150),
    'timeline': (120, 300),      # Resolve abriendo / armando el timeline
    'voz': (120, 360),           # cargar el modelo de voz y transcribir (en CPU un audio largo tarda)
    'ia': (120, 360),
    'diseno': (60, 180),
    'sfx': (60, 180),
    'resolve': (90, 240),        # colocando en el timeline
    'colocar': (90, 240),
}

_LOCK = threading.Lock()
_TAREAS = {}
_HILO = {'v': None}
_MONITOR = {'v': None, 'estado': {}}
_ARRANQUE = {'listo': True, 'inicio': time.time(), 'avisado': False}          # (solo se vigila si main() llama a vigilar_arranque; pruebas y MCP no)


def _registro():
    import registro
    return registro


def _fmt_s(s):
    s = int(s)
    return f'{s // 60} min {s % 60:02d} s' if s >= 60 else f'{s} s'


# ---------------------------------------------------------------------------
# pilas de los hilos (qué estaba haciendo cada uno)
# ---------------------------------------------------------------------------
def pila_de_hilo(ident, ultimas=8):
    marco = sys._current_frames().get(ident)
    if marco is None:
        return ''
    return ''.join(traceback.format_stack(marco)[-ultimas:])


def pilas_de_todos(ultimas=6):
    """Pila resumida de todos los hilos (para el log de un cuelgue)."""
    nombres = {t.ident: t.name for t in threading.enumerate()}
    partes = []
    for ident, marco in sys._current_frames().items():
        pila = ''.join(traceback.format_stack(marco)[-ultimas:])
        partes.append(f'--- hilo {nombres.get(ident, ident)} ---\n{pila}')
    return '\n'.join(partes)


# ---------------------------------------------------------------------------
# tareas
# ---------------------------------------------------------------------------
class _Tarea:
    def __init__(self, nombre, hilo, paso, al_aviso, al_atasco):
        self.nombre = nombre
        self.hilo = hilo
        self.paso = paso or ''
        self.al_aviso = al_aviso
        self.al_atasco = al_atasco
        self.inicio = self.ultimo = self.paso_desde = time.time()
        self.detalle = ''
        self.avisado_en = 0.0          # ultimo aviso (para no repetirlo cada 2 s)
        self.atascada = False
        self.pasos = []                # [(paso, segundos)]
        self.pausada = False           # esperando al usuario (editor abierto, un diálogo): no es un atasco
        self.guardado = 0.0


def iniciar(nombre, hilo=None, paso='', al_aviso=None, al_atasco=None):
    """Empieza a vigilar una tarea. `hilo` = el hilo de trabajo (su pila se anota si se atasca); `al_aviso(texto)` y `al_atasco(paso)` los llama el vigía."""
    t = _Tarea(nombre, hilo, paso, al_aviso, al_atasco)
    with _LOCK:
        _TAREAS[nombre] = t
    _guardar_en_curso(t, forzar=True)
    _asegurar_hilo()
    return t


def latido(nombre, paso=None, detalle=''):
    """La tarea sigue viva (llamar con cada mensaje de progreso). Un cambio de `paso` queda medido para el resumen final."""
    t = _TAREAS.get(nombre)
    if t is None:
        return
    ahora = time.time()
    if t.atascada and ahora - t.ultimo > 1:
        try:
            _registro().ok(f'«{nombre}» volvió a responder tras {_fmt_s(ahora - t.ultimo)}.', 'vigilancia')
        except Exception:
            pass
    t.ultimo = ahora
    t.atascada = False
    t.avisado_en = 0.0
    if detalle:
        t.detalle = str(detalle)[:160]
    if paso and paso != t.paso:
        if t.paso:
            t.pasos.append((t.paso, ahora - t.paso_desde))
        t.paso, t.paso_desde = paso, ahora
        _guardar_en_curso(t, forzar=True)


def pausar(nombre):
    """La tarea espera al USUARIO (editor de palabras, un diálogo): el vigía no cuenta ese tiempo."""
    t = _TAREAS.get(nombre)
    if t is not None:
        t.pausada = True


def reanudar(nombre):
    t = _TAREAS.get(nombre)
    if t is not None:
        t.pausada = False
        t.ultimo = time.time()
        t.avisado_en = 0.0


def terminar(nombre, ok=True, motivo=''):
    with _LOCK:
        t = _TAREAS.pop(nombre, None)
    if t is None:
        return
    ahora = time.time()
    if t.paso:
        t.pasos.append((t.paso, ahora - t.paso_desde))
    try:
        TAREA_EN_CURSO.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        lista = ' · '.join(f'{p} {_fmt_s(s)}' for p, s in t.pasos if s >= 1)
        texto = f"«{nombre}» {'terminó' if ok else 'terminó con fallo'} en {_fmt_s(ahora - t.inicio)}" + (f' ({lista})' if lista else '') + (f': {motivo}' if motivo else '')
        r = _registro()
        (r.info if ok else r.aviso)(texto, 'vigilancia')
    except Exception:
        pass


def _guardar_en_curso(t, forzar=False):
    ahora = time.time()
    if not forzar and ahora - t.guardado < 5:
        return
    t.guardado = ahora
    try:
        CARPETA.mkdir(parents=True, exist_ok=True)
        TAREA_EN_CURSO.write_text(json.dumps({'tarea': t.nombre, 'paso': t.paso, 'desde': t.inicio, 'ahora': ahora}), encoding='utf-8')
    except Exception:
        pass


def tarea_cortada_anterior():
    """Si la sesión anterior se cayó en medio de una tarea: (nombre, paso, hace_cuanto_s), si no None. Se borra al leerla."""
    try:
        d = json.loads(TAREA_EN_CURSO.read_text(encoding='utf-8'))
        TAREA_EN_CURSO.unlink(missing_ok=True)
        return d.get('tarea'), d.get('paso'), time.time() - float(d.get('ahora') or 0)
    except Exception:
        return None


def en_curso():
    return list(_TAREAS)


def _asegurar_hilo():
    with _LOCK:
        if _HILO['v'] is not None and _HILO['v'].is_alive():
            return
        _HILO['v'] = threading.Thread(target=_vigilar, daemon=True, name='vigia-tareas')
        _HILO['v'].start()


def _vigilar():
    while True:
        time.sleep(2.0)
        with _LOCK:
            tareas = list(_TAREAS.values())
        for t in tareas:
            try:
                _revisar(t)
            except Exception:
                pass
        _revisar_arranque()
        if not tareas and _ARRANQUE['listo']:
            # sin tareas y arranque resuelto: el hilo duerme más (sigue vivo por si llega otra)
            time.sleep(3.0)


ABANDONO_S = 900          # sin señales durante tanto: se deja de vigilar (la tarea quedó huérfana) para no avisar eternamente


def _revisar(t):
    ahora = time.time()
    if t.pausada:
        return
    sin_senal = ahora - t.ultimo
    if sin_senal > ABANDONO_S:
        terminar(t.nombre, ok=False, motivo=f'sin señales durante {_fmt_s(sin_senal)}; se deja de vigilar')
        return
    aviso_s, atasco_s = UMBRALES.get(t.paso) or UMBRALES['defecto']
    if sin_senal < aviso_s:
        return
    r = _registro()
    pila = pila_de_hilo(t.hilo.ident) if t.hilo is not None and getattr(t.hilo, 'ident', None) else ''
    donde = f' en el paso «{t.paso}»' if t.paso else ''
    extra = f' ({t.detalle})' if t.detalle else ''
    if sin_senal >= atasco_s and not t.atascada:
        t.atascada = True
        r.error(f'«{t.nombre}» lleva {_fmt_s(sin_senal)} sin dar señales{donde}{extra}: parece atascado.', 'vigilancia', detalle=pila or pilas_de_todos())
        _llamar(t.al_aviso, f'Parece atascado{donde} ({_fmt_s(sin_senal)} sin avanzar). Intento destrabarlo; mira el Registro.')
        _llamar(t.al_atasco, t.paso)
        t.avisado_en = ahora
    elif sin_senal < atasco_s and ahora - t.avisado_en > 60:
        t.avisado_en = ahora
        r.aviso(f'«{t.nombre}» lleva {_fmt_s(sin_senal)} sin avanzar{donde}{extra}.', 'vigilancia', detalle=pila)
        _llamar(t.al_aviso, f'Esto está tardando más de lo normal{donde} ({_fmt_s(sin_senal)})…')
    elif t.atascada and ahora - t.avisado_en > 120:
        # sigue atascado: recordarlo cada 2 min con la pila nueva (para ver si cambia)
        t.avisado_en = ahora
        r.error(f'«{t.nombre}» sigue sin responder tras {_fmt_s(sin_senal)}{donde}.', 'vigilancia', detalle=pila)
        _llamar(t.al_atasco, t.paso)


def _llamar(fn, *args):
    if fn is None:
        return
    try:
        fn(*args)
    except Exception:
        try:
            _registro().excepcion(origen='vigilancia · reacción')
        except Exception:
            pass


# ---------------------------------------------------------------------------
# arranque
# ---------------------------------------------------------------------------
def vigilar_arranque(limite_s=45):
    """Llamar lo primero en main(): si `arranque_listo()` no llega en `limite_s`, se anota con la pila de todos los hilos."""
    _ARRANQUE.update(listo=False, inicio=time.time(), limite=limite_s, avisado=False)
    _marcar_sesion('abriendo')
    _asegurar_hilo()


def arranque_listo():
    if _ARRANQUE['listo']:
        return
    _ARRANQUE['listo'] = True
    _marcar_sesion('listo')
    try:
        if _ARRANQUE['avisado']:
            _registro().ok(f"El arranque terminó tras {_fmt_s(time.time() - _ARRANQUE['inicio'])}.", 'arranque')
        else:
            _registro().info(f"Arranque completo en {time.time() - _ARRANQUE['inicio']:.1f} s.", 'arranque')
    except Exception:
        pass


def _revisar_arranque():
    if _ARRANQUE['listo'] or _ARRANQUE['avisado']:
        return
    limite = _ARRANQUE.get('limite') or 45
    espera = time.time() - _ARRANQUE['inicio']
    if espera >= limite:
        _ARRANQUE['avisado'] = True
        try:
            _registro().error(f'El programa lleva {_fmt_s(espera)} abriendo y no termina: algo se quedó esperando.', 'arranque', detalle=pilas_de_todos())
        except Exception:
            pass


def _marcar_sesion(estado):
    """La marca de sesión guarda «hora|estado»: el siguiente arranque distingue una caída en uso de un arranque que nunca terminó."""
    try:
        CARPETA.mkdir(parents=True, exist_ok=True)
        (CARPETA / 'sesion_abierta.flag').write_text(f'{time.time()}|{estado}', encoding='utf-8')
    except Exception:
        pass


# ---------------------------------------------------------------------------
# monitor periódico (disco, memoria, escritura)
# ---------------------------------------------------------------------------
def memoria_libre_mb():
    """Memoria disponible en MB (Windows, Mac y Linux) o None si no se pudo saber."""
    try:
        if sys.platform.startswith('win'):
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                            ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return int(m.ullAvailPhys / 1048576)
        if sys.platform == 'darwin':
            import subprocess
            salida = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=3).stdout
            pagina = 16384 if 'page size of 16384' in salida else 4096
            paginas = 0
            for linea in salida.splitlines():
                if linea.startswith(('Pages free', 'Pages inactive', 'Pages speculative')):
                    paginas += int(linea.split(':')[1].strip().rstrip('.'))
            return int(paginas * pagina / 1048576)
        with open('/proc/meminfo', encoding='utf-8') as f:
            for linea in f:
                if linea.startswith('MemAvailable'):
                    return int(linea.split()[1]) // 1024
    except Exception:
        pass
    return None


def _comprobaciones():
    """[(clave, nivel|None, mensaje)]: nivel None = todo bien."""
    import shutil
    res = []
    try:
        libre = shutil.disk_usage(str(Path.home())).free / 1024 ** 3
        if libre < 1.0:
            res.append(('disco', 'error', f'Quedan solo {libre:.1f} GB libres en el disco: los renders, los modelos y el registro pueden fallar.'))
        elif libre < 3.0:
            res.append(('disco', 'aviso', f'Quedan {libre:.1f} GB libres en el disco.'))
        else:
            res.append(('disco', None, ''))
    except Exception:
        pass
    mem = memoria_libre_mb()
    if mem is not None:
        if mem < 500:
            res.append(('memoria', 'aviso', f'Memoria libre muy baja ({mem} MB): los modelos de voz e IA pueden fallar o ir muy lentos. Cierra otros programas.'))
        else:
            res.append(('memoria', None, ''))
    try:
        CARPETA.mkdir(parents=True, exist_ok=True)
        prueba = CARPETA / '.escritura.tmp'
        prueba.write_text('ok', encoding='utf-8')
        prueba.unlink()
        res.append(('escritura', None, ''))
    except Exception as e:
        res.append(('escritura', 'error', f'No se puede escribir en {CARPETA} ({type(e).__name__}: {e}): no se guardarán ajustes, marcas ni el registro.'))
    return res


def revisar_ahora():
    """Una pasada del monitor: anota solo lo que CAMBIÓ desde la anterior. Devuelve la lista de problemas actuales."""
    r = _registro()
    problemas = []
    for clave, nivel, mensaje in _comprobaciones():
        antes = _MONITOR['estado'].get(clave)
        _MONITOR['estado'][clave] = nivel
        if nivel:
            problemas.append((clave, nivel, mensaje))
            if antes != nivel:
                (r.error if nivel == 'error' else r.aviso)(mensaje, 'monitor')
        elif antes:
            r.ok(f'Resuelto: {clave} vuelve a estar bien.', 'monitor')
    return problemas


def iniciar_monitor(intervalo_s=60):
    if _MONITOR['v'] is not None and _MONITOR['v'].is_alive():
        return

    def bucle():
        while True:
            try:
                revisar_ahora()
            except Exception:
                pass
            time.sleep(intervalo_s)
    _MONITOR['v'] = threading.Thread(target=bucle, daemon=True, name='monitor-salud')
    _MONITOR['v'].start()


# ---------------------------------------------------------------------------
# comprobación de arranque: librerías, motores, MCP → al Registro (y devuelve las fallas para avisar en pantalla)
# ---------------------------------------------------------------------------
def revisar_salud_al_arrancar():
    """Corre salud.comprobar() (1-3 s: en un hilo) y anota cada falla como error con qué hacer. Devuelve la lista de fallas [(nombre, detalle)]."""
    r = _registro()
    fallas = []
    try:
        import salud
        filas = salud.comprobar()
    except Exception:
        r.excepcion(origen='arranque · chequeo de librerías')
        return fallas
    for f in filas:
        if f.get('ok') is False:
            fallas.append((f['nombre'], f['detalle']))
            r.error(f"Falla al iniciar: {f['nombre']} — {f['detalle']}", 'arranque')
    if not fallas:
        r.info('Chequeo de arranque: todo en orden (' + salud.resumen(filas)[0] + ').', 'arranque')
    return fallas
