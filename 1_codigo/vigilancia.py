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
# v5.85: un arranque atascado de verdad (sin ventana tras ARRANQUE_TOPE_S y la interfaz sin latir ARRANQUE_SIN_PULSO_S) se cierra solo: si no,
# seguía vivo con el candado de una sola ventana y abrir el programa no hacía nada hasta reiniciar. Un diálogo esperando al usuario late: no cuenta.
ARRANQUE_TOPE_S = 240
ARRANQUE_SIN_PULSO_S = 60


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


def terminar(nombre, ok=True, motivo='', cancelado=False):
    """cancelado=True (v5.82): el usuario la paró a propósito; va al Registro como información, no como «terminó con fallo» (ese aviso caía
    en errores.log con la explicación de otro error)."""
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
        r = _registro()
        if cancelado:
            r.info(f'«{nombre}» se canceló en {_fmt_s(ahora - t.inicio)}' + (f' ({lista})' if lista else ''), 'vigilancia')
            return
        texto = f"«{nombre}» {'terminó' if ok else 'terminó con fallo'} en {_fmt_s(ahora - t.inicio)}" + (f' ({lista})' if lista else '') + (f': {motivo}' if motivo else '')
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
def vigilar_arranque(limite_s=45, tope_s=None):
    """Llamar lo primero en main(): si `arranque_listo()` no llega en `limite_s`, se anota con la pila de todos los hilos; con `tope_s`
    (v5.85), si tampoco llega en `tope_s` y la interfaz no late, el programa se cierra solo (ver ARRANQUE_TOPE_S)."""
    _ARRANQUE.update(listo=False, inicio=time.time(), limite=limite_s, avisado=False, tope=tope_s, cortado=False)
    _marcar_sesion('abriendo · creando la ventana')     # v5.82: la fase va en la marca: el siguiente arranque dice dónde se quedó
    try:
        _registro().vigilar_arranque_nativo(20)      # v5.82: a los 20 s, la pila de todos los hilos en fallo_nativo.log (aunque se cierre a la fuerza)
    except Exception:
        pass
    _asegurar_hilo()


def arranque_listo():
    if _ARRANQUE['listo']:
        return
    _ARRANQUE['listo'] = True
    try:
        _registro().fin_arranque_nativo()
    except Exception:
        pass
    _marcar_sesion('listo')
    try:
        if _ARRANQUE['avisado']:
            _registro().ok(f"El arranque terminó tras {_fmt_s(time.time() - _ARRANQUE['inicio'])}.", 'arranque')
        else:
            _registro().info(f"Arranque completo en {time.time() - _ARRANQUE['inicio']:.1f} s.", 'arranque')
    except Exception:
        pass


def _revisar_arranque():
    if _ARRANQUE['listo']:
        return
    limite = _ARRANQUE.get('limite') or 45
    espera = time.time() - _ARRANQUE['inicio']
    if espera >= limite and not _ARRANQUE['avisado']:
        _ARRANQUE['avisado'] = True
        try:
            _registro().error(f'El programa lleva {_fmt_s(espera)} abriendo y no termina: algo se quedó esperando.', 'arranque', detalle=pilas_de_todos())
        except Exception:
            pass
    tope = _ARRANQUE.get('tope')
    if tope and espera >= tope and not _ARRANQUE.get('cortado'):
        try:
            parado = _registro().segundos_sin_pulso_ui()
        except Exception:
            parado = None
        if parado is not None and parado >= ARRANQUE_SIN_PULSO_S:
            _ARRANQUE['cortado'] = True
            _cortar_arranque(espera, parado)


def _cortar_arranque(espera, parado, salir=None):
    """v5.85: el arranque está atascado de verdad: se anota (con la pila de todos los hilos), la marca de sesión lo dice para el siguiente
    arranque y el proceso termina, lo que suelta el candado de una sola ventana. `salir` es para las pruebas (por defecto os._exit)."""
    try:
        _registro().error(f'El programa no terminó de abrir en {_fmt_s(espera)} (la interfaz llevaba {_fmt_s(parado)} sin responder): '
                          'se cerró solo para que la próxima vez abra.', 'arranque', detalle=pilas_de_todos())
    except Exception:
        pass
    _marcar_sesion(f'abriendo · cortado tras {int(espera)} s sin responder')
    try:
        import logging
        logging.shutdown()
        for flujo in (sys.stdout, sys.stderr):
            if flujo is not None:
                flujo.flush()
    except Exception:
        pass
    (salir or os._exit)(3)


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
    res.append(_probar_escritura())
    return res


def _probar_escritura(intentos=5):
    """v5.82 (informe de un cliente: «No se puede escribir en … (PermissionError: [WinError 32] …\\.escritura.tmp): no se guardarán ajustes…»):
    el archivo de prueba tenía nombre FIJO y el monitor y el chequeo de arranque lo creaban y borraban a la vez (o el antivirus lo tenía
    abierto un instante); un solo fallo ya era «no se puede escribir». Ahora: nombre único, varios intentos en ~2 s y solo cuenta poder
    ESCRIBIR (si el borrado falla, se limpia en la pasada siguiente)."""
    try:
        CARPETA.mkdir(parents=True, exist_ok=True)
        for viejo in CARPETA.glob('.escritura*.tmp'):          # los de pasadas anteriores que no se pudieron borrar
            try:
                viejo.unlink()
            except OSError:
                pass
    except OSError:
        pass
    error = None
    for k in range(intentos):
        prueba = CARPETA / f'.escritura.{os.getpid()}.{threading.get_ident()}.{k}.tmp'
        try:
            prueba.write_text('ok', encoding='utf-8')
        except OSError as e:
            error = e
            if k < intentos - 1:
                time.sleep(0.2 * (k + 1))
            continue
        try:
            prueba.unlink()
        except OSError:
            pass
        return ('escritura', None, '')
    return ('escritura', 'error', f'No se puede escribir en {CARPETA} ({type(error).__name__}: {error}): mientras siga así no se guardarán '
            'ajustes, marcas ni el registro.')


_LOCK_REVISAR = threading.Lock()


def revisar_ahora():
    """Una pasada del monitor: anota solo lo que CAMBIÓ desde la anterior. Devuelve la lista de problemas actuales.
    v5.82: de una en una (el monitor y el chequeo de arranque la llamaban a la vez desde dos hilos)."""
    r = _registro()
    problemas = []
    with _LOCK_REVISAR:
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
        elif f.get('ok') is None and f.get('aviso'):
            # v5.83: funciona, pero le falta algo (p. ej. la IA de texto: la voz va bien y el texto se corrige con reglas): no es «Falla al
            # iniciar» (ni cuenta para el aviso de fallas), pero va como error para que se vea: la ventana Registro solo enseña Errores e Información
            r.error(f"Al abrir: {f['nombre']} — {f['detalle']}", 'arranque')
    if not fallas:
        r.info('Chequeo de arranque: todo en orden (' + salud.resumen(filas)[0] + ').', 'arranque')
    if any(f.get('cuda') == 'faltan' for f in filas):
        preparar_gpu_voz()
    poner_motores_al_dia()
    avisar_equipo()
    return fallas


_MOTORES_AL_DIA = {'v': None}


def poner_motores_al_dia():
    """v5.72 (pedido: «que el .exe actualice las dependencias en segundo plano, sin ventanas ni interrumpir»): si una instalación anterior
    dejó un motor con librerías que no son las fijadas (la tarea del instalador se cortó o se omitió), se ponen al día AL ABRIR, en un
    hilo, con pip sin ventana y solo lo que falta (--no-deps). Mientras, los arranques del motor esperan (motor_voz.esperar_puesta_al_dia;
    motor_compat.instalar va de uno en uno). Solo el programa instalado en Windows; desde Claude el AppData está virtualizado (no).
    v5.86: en la Mac, _motor_ia_en_mac (el motor de voz e IA lo instala el programa, no el .pkg)."""
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        _motor_ia_en_mac()
        return
    if not sys.platform.startswith('win') or not getattr(sys, 'frozen', False):
        return
    with _LOCK:
        if _MOTORES_AL_DIA['v'] is not None:
            return
        _MOTORES_AL_DIA['v'] = True
    r = _registro()

    def trabajo():
        try:
            import motor_compat
            if motor_compat.python_motor().is_file() and not motor_compat.instalado() and not motor_compat._appdata_de_claude():
                r.info('Motor auxiliar: le faltan librerías de esta versión; las pongo al día en segundo plano.', 'arranque')
                motor_compat.instalar()
                r.ok('Motor auxiliar al día.', 'arranque')
        except Exception as e:
            r.aviso(f'Motor auxiliar: no pude ponerlo al día ({type(e).__name__}: {e}); lo reintento al usarlo.', 'arranque')
        try:
            import motor_voz
            puestas = motor_voz.completar_requisitos()          # (sin motor instalado o ya al día: no hace nada)
            if puestas:
                r.ok(f'Motor de voz e IA: {len(puestas)} librerías puestas al día en segundo plano '
                     f'({", ".join(p.split("==")[0] for p in puestas[:6])}{"…" if len(puestas) > 6 else ""}).', 'arranque')
        except Exception as e:
            r.aviso(f'Motor de voz e IA: no pude poner al día sus librerías ({type(e).__name__}: {e}). Si la voz falla, «Reparar el motor» '
                    'en Ajustes.', 'arranque')
    _MOTORES_AL_DIA['v'] = threading.Thread(target=trabajo, daemon=True, name='motores-al-dia')
    _MOTORES_AL_DIA['v'].start()


MAC_IA_ESPERA_S = 90                     # tras abrir, antes de empezar la descarga (el arranque y un primer GO van primero)
MAC_IA_REINTENTO_S = 24 * 3600           # tras un intento fallido, el siguiente automático (con «Instalar» en Ajustes, cuando quiera)


def _motor_ia_en_mac():
    """v5.86 (pedido: «en Mac aún no están todos los estilos y funciones»): en Windows el instalador pone el motor de voz e IA (Qwen3-ASR + la
    IA de texto: de 4 a 15 GB); el .pkg de la Mac no puede esperar tanto. Así que en la Mac con Apple Silicon lo instala el programa solo, al
    abrir y en segundo plano (mientras, Whisper y las reglas; Ajustes › General enseña el avance). Ya instalado, solo pone al día sus librerías.
    Si falla (o queda sin la IA de texto), lo dice en el Registro y no lo reintenta solo hasta pasado un día (motor_qwen/instalacion_auto.json)."""
    import motor_voz
    if not motor_voz.SOPORTADO:
        return
    with _LOCK:
        if _MOTORES_AL_DIA['v'] is not None:
            return
        _MOTORES_AL_DIA['v'] = True
    r = _registro()

    def trabajo():
        import archivos_seguros
        marca = motor_voz.carpeta() / 'instalacion_auto.json'
        try:
            info = motor_voz.asegurar_listo()
            if info and info.get('modelo_texto'):
                puestas = motor_voz.completar_requisitos()
                if puestas:
                    r.ok(f'Motor de voz e IA: {len(puestas)} librerías puestas al día en segundo plano.', 'arranque')
                return
            ultimo = archivos_seguros.leer_json(marca, {}) or {}
            if time.time() - float(ultimo.get('fallo') or 0) < MAC_IA_REINTENTO_S:
                return
            time.sleep(MAC_IA_ESPERA_S)
            if motor_voz.instalando() or motor_voz.instalado():       # (ya la pidió Ajustes en este rato)
                return
            r.info('Motor de voz e IA (Qwen3-ASR y la IA de texto): lo instalo en segundo plano, de 4 a 15 GB según la memoria de esta Mac; '
                   'mientras, la voz va con Whisper. El avance se ve en Ajustes › General.', 'arranque')
            modelo = motor_voz.instalar(aviso=None)
            info = motor_voz.info_instalado() or {}
            if info.get('modelo_texto'):
                archivos_seguros.escribir_json(marca, {'listo': time.strftime('%Y-%m-%d %H:%M')})
                r.ok(f'Motor de voz e IA listo: Qwen3-ASR {modelo} + IA de texto ({info.get("gpu") or "Apple Silicon"}).', 'arranque')
            else:
                archivos_seguros.escribir_json(marca, {'fallo': time.time(), 'motivo': 'sin la IA de texto'})
        except Exception as e:
            try:
                archivos_seguros.escribir_json(marca, {'fallo': time.time(), 'motivo': f'{type(e).__name__}: {e}'[:300]})
            except Exception:
                pass
            r.aviso(f'Motor de voz e IA: no se pudo instalar solo ({type(e).__name__}: {e}); lo reintento mañana, o ahora con «Instalar '
                    'motor Qwen3-ASR» en Ajustes › General. Mientras, la voz va con Whisper.', 'arranque')
    _MOTORES_AL_DIA['v'] = threading.Thread(target=trabajo, daemon=True, name='motor-ia-mac')
    _MOTORES_AL_DIA['v'].start()


def avisar_equipo():
    """v5.72: lo que le falta al equipo (ficha_equipo.revisar: driver de la GPU, Visual C++, RAM, disco…) y lo que el instalador no pudo
    poner al día, al Registro (sin cuadros). Una vez por sesión, en el hilo de la comprobación de arranque."""
    r = _registro()
    try:
        import ficha_equipo
        f = ficha_equipo.de_esta_sesion()
    except Exception:
        return
    for x in f.get('revision') or []:
        if x.get('estado') == 'falta':
            r.aviso(f"Tu equipo: {x['texto']}.", 'equipo')
        elif x.get('estado') == 'aviso' and x.get('id') == 'driver_gpu':
            r.info(f"Tu equipo: {x['texto']}.", 'equipo')
    puesta = f.get('puesta_al_dia') or {}
    for t in (puesta.get('fallos') or [])[:4]:
        r.aviso(f'Tu equipo: el instalador no pudo poner al día esto: {t}.', 'equipo')


_GPU_VOZ = {'v': None}


def preparar_gpu_voz():
    """v5.64 (un usuario con una RTX 3050 Ti veía «Falla al iniciar: GPU para la voz (CUDA) — faltan cublas64_12.dll…» en cada arranque y la voz
    iba por la CPU): las librerías de NVIDIA que usa Whisper (cuBLAS y cuDNN, ≈1,3 GB de PyPI, con reanudación) se bajan SOLAS en un hilo, una
    vez por sesión; si no se puede (sin internet), aviso y se reintenta al volver a abrir. Lo mismo que «Reparar GPU» de Ajustes, sin preguntar."""
    r = _registro()
    with _LOCK:
        if _GPU_VOZ['v'] is not None:
            return
        _GPU_VOZ['v'] = threading.current_thread()

    def trabajo():
        import cuda_libs
        r.info('GPU para la voz: faltan las librerías de NVIDIA (cuBLAS y cuDNN). Las descargo una sola vez (≈1,3 GB); mientras, la voz va por la CPU.',
               'arranque')
        try:
            ok, msg = cuda_libs.reparar(permitir_descarga=True)
        except Exception as e:
            ok, msg = False, f'{type(e).__name__}: {e}'
        if ok:
            r.ok(f'GPU para la voz lista: {msg}', 'arranque')
        else:
            r.aviso(f'GPU para la voz: no pude preparar las librerías de NVIDIA ({msg}). La voz sigue por la CPU; lo reintento la próxima vez que '
                    'abras CineCaptions.', 'arranque')
    _GPU_VOZ['v'] = threading.Thread(target=trabajo, daemon=True, name='gpu-voz')
    _GPU_VOZ['v'].start()
