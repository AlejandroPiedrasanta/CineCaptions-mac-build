# CineCaptions · By Cinema Productions
# 1_codigo/resolve_mcp.py — conexión con el MCP oficial de Resolve 21.1+: abrir Resolve, proyecto reciente, ejecutar scripts.
"""
resolve_mcp.py
--------------
La conexion con DaVinci Resolve por su servidor MCP OFICIAL (ResolveMCP.exe,
viene con Resolve 21.1 o mas nuevo). Es el camino preferido desde la v5.1:

  * no hace falta lanzar el Puente en Resolve ni tocar «External scripting»;
  * cada orden tarda ~1 ms dentro de Resolve (el Puente: 0,25-1 s de sondeo);
  * da datos que antes no habia: version exacta, proyecto, timeline, la
    seleccion del timeline, un fotograma para las vistas previas...

Como funciona
=============
ResolveMCP habla JSON-RPC por stdin/stdout (una linea por mensaje). Se lanza
UNA vez y queda abierto mientras el programa viva (arrancarlo cuesta ~0,2 s
con Resolve abierto y ~4 s sin el). La herramienta que usamos es
'run_script_unsafe': ejecuta Python 3.14 DENTRO de Resolve (ResolvePython)
con 'resolve' y 'project' ya puestos. Ese proceso es persistente, asi que:

  * los scripts gemelos (.py de 2_recursos/resolve_scripts) se cargan alli tal
    cual, igual que con la API de Studio;
  * un trabajo largo (colocar 600 bloques) corre en un HILO alli dentro y se
    le pregunta como va: la herramienta corta a los 60 s, el hilo no.

Si ResolveMCP no esta (Resolve 20 o anterior, Mac/Linux sin el binario) o no
contesta, resolve_bridge sigue con los caminos de siempre (API de Studio,
Puente, a mano).
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

PROTOCOLO = '2024-11-05'
SIN_VENTANA = 0x08000000 if sys.platform == 'win32' else 0
REINTENTO_TRAS_FALLO_S = 10.0
CACHE_ESTADO_S = 3.0


def ruta_exe():
    """Donde esta ResolveMCP, o None. RESOLVE_MCP_PATH manda (igual que en el paquete oficial de Blackmagic)."""
    candidatos = []
    forzada = os.environ.get('RESOLVE_MCP_PATH')
    if sys.platform == 'win32':
        for var in ('ProgramW6432', 'ProgramFiles'):
            base = os.environ.get(var)
            if base:
                candidatos.append(Path(base) / 'Blackmagic Design' / 'DaVinci Resolve' / 'ResolveMCP.exe')
        try:
            import resolve_bridge
            d = resolve_bridge._resolve_dir_windows()
            if d:
                candidatos.insert(0, Path(d) / 'ResolveMCP.exe')
        except Exception:
            pass
    elif sys.platform == 'darwin':
        # v5.3.4: la ruta REAL en Mac la dice el paquete oficial de Blackmagic (DaVinciResolve.mcpb > server/index.js):
        #   /Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolveMCP
        # (antes se buscaba en Contents/MacOS y Contents/Libraries: no existe ahí, así que en Mac el MCP nunca se encontraba y GO caía al Puente de Resolve Free)
        for raiz in (Path('/Applications/DaVinci Resolve/DaVinci Resolve.app'), Path('/Applications/DaVinci Resolve.app'), Path.home() / 'Applications' / 'DaVinci Resolve' / 'DaVinci Resolve.app'):
            app = raiz / 'Contents'
            candidatos += [app / 'Applications' / 'ResolveMCP', app / 'MacOS' / 'ResolveMCP', app / 'Libraries' / 'ResolveMCP']
    else:
        candidatos += [Path('/opt/resolve/bin/ResolveMCP'), Path('/opt/resolve/ResolveMCP')]
    if forzada:
        candidatos.insert(0, Path(forzada))
    for c in candidatos:
        try:
            if c.is_file():
                return c
        except OSError:
            pass
    return None


# ResolveMCP abre DaVinci Resolve COMO HIJO suyo, y Resolve es una aplicación Qt: si hereda de CineCaptions (también Qt, y empaquetada con PyInstaller)
# QT_QPA_PLATFORM / QT_PLUGIN_PATH / QT_QPA_PLATFORM_PLUGIN_PATH o las variables de PyInstaller y de Python, no arranca y enseña «This application
# failed to start because no Qt platform plugin could be initialized» (así se rompió el arranque de Resolve en las pruebas con
# QT_QPA_PLATFORM=offscreen). El entorno de Resolve se limpia de todo eso.
_VARIABLES_AJENAS = ('QT_QPA_PLATFORM', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'QT_PLUGIN_PATH', 'QT_QPA_FONTDIR', 'QT_QPA_GENERIC_PLUGINS', 'QT_QPA_EGLFS_INTEGRATION',
                     'QML2_IMPORT_PATH', 'QML_IMPORT_PATH', 'QT_DEBUG_PLUGINS', 'PYTHONHOME', 'PYTHONPATH', 'PYTHONEXECUTABLE', '_MEIPASS2',
                     'DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH', 'DYLD_FALLBACK_LIBRARY_PATH', 'DYLD_INSERT_LIBRARIES', 'LD_LIBRARY_PATH', 'LD_PRELOAD')    # (Mac / Linux: las del programa empaquetado)


def entorno_para_resolve(base=None):
    """Copia del entorno sin las variables de Qt, de Python y de PyInstaller de este proceso (ni las carpetas del programa empaquetado en el PATH)."""
    env = dict(os.environ if base is None else base)
    for k in list(env):
        if k in _VARIABLES_AJENAS or k.startswith('_PYI_'):
            env.pop(k, None)
    propia = getattr(sys, '_MEIPASS', None)
    if propia and env.get('PATH'):
        quitar = os.path.normcase(os.path.abspath(propia))
        env['PATH'] = os.pathsep.join(p for p in env['PATH'].split(os.pathsep) if not os.path.normcase(os.path.abspath(p or '.')).startswith(quitar))
    return env


class _Cliente:
    def __init__(self, exe):
        self.p = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, creationflags=SIN_VENTANA,
                                  cwd=str(Path.home()), env=entorno_para_resolve())
        self.n = 0
        self.esperas = {}
        self.lock = threading.Lock()
        self.instrucciones = ''
        threading.Thread(target=self._leer, daemon=True, name='resolve-mcp').start()

    def _leer(self):
        for linea in iter(self.p.stdout.readline, b''):
            try:
                r = json.loads(linea)
            except Exception:
                continue
            ev = self.esperas.pop(r.get('id'), None)
            if ev:
                ev[1] = r
                ev[0].set()
        for ev in list(self.esperas.values()):
            ev[0].set()

    def vivo(self):
        return self.p.poll() is None

    def _escribir(self, mensaje):
        self.p.stdin.write((json.dumps(mensaje) + '\n').encode('utf-8'))
        self.p.stdin.flush()

    def pedir(self, metodo, params=None, timeout=30):
        with self.lock:
            self.n += 1
            i = self.n
            ev = [threading.Event(), None]
            self.esperas[i] = ev
            self._escribir({'jsonrpc': '2.0', 'id': i, 'method': metodo, 'params': params or {}})
        if not ev[0].wait(timeout):
            self.esperas.pop(i, None)
            raise TimeoutError(f'ResolveMCP no contestó a {metodo} en {timeout} s')
        if ev[1] is None:
            raise ConnectionError('ResolveMCP se cerró')
        if 'error' in ev[1]:
            raise RuntimeError(str(ev[1]['error'].get('message') or ev[1]['error']))
        return ev[1].get('result') or {}

    def iniciar(self):
        r = self.pedir('initialize', {'protocolVersion': PROTOCOLO, 'capabilities': {},
                                      'clientInfo': {'name': 'CineCaptions', 'version': _version_app()}},
                       timeout=20)
        self.instrucciones = r.get('instructions') or ''
        with self.lock:
            self._escribir({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    def herramienta(self, nombre, argumentos=None, timeout=30):
        """Llama una herramienta y devuelve su contenido ya decodificado."""
        r = self.pedir('tools/call', {'name': nombre, 'arguments': argumentos or {}}, timeout=timeout)
        textos = [c.get('text', '') for c in r.get('content') or [] if c.get('type') == 'text']
        texto = '\n'.join(textos)
        try:
            datos = json.loads(texto)
        except Exception:
            return {'texto': texto, 'es_error': bool(r.get('isError'))}
        # launch_resolve contesta una cadena JSON ("DaVinci Resolve is running")
        if not isinstance(datos, dict):
            return {'texto': str(datos), 'es_error': bool(r.get('isError'))}
        return datos

    def cerrar(self):
        try:
            self.p.kill()
        except Exception:
            pass


def _version_app():
    try:
        from version import APP_VERSION
        return APP_VERSION
    except Exception:
        return '5'


_ESTADO = {'cliente': None, 'ultimo_fallo': 0.0, 'cache': None, 'cache_t': 0.0, 'motivo': '', 'fallos_arranque': 0, 'sin_contestar': 0}


def espera_tras_fallo():
    """v5.4.8: cuánto esperar antes de volver a intentar arrancar ResolveMCP: 10 s, 20, 40 y como mucho 60 (antes siempre 10: con Resolve cerrado se reintentaba sin parar)."""
    return min(60.0, REINTENTO_TRAS_FALLO_S * (2 ** min(_ESTADO.get('fallos_arranque', 0), 3)))
_LOCK = threading.Lock()
_TRABAJO = threading.Lock()


def cliente(arrancar=True):
    """El cliente conectado, o None. Arranca ResolveMCP la primera vez."""
    with _LOCK:
        c = _ESTADO['cliente']
        if c is not None and c.vivo():
            return c
        _ESTADO['cliente'] = None
        if not arrancar or time.time() - _ESTADO['ultimo_fallo'] < espera_tras_fallo():
            return None
        if os.environ.get('CINECAPTIONS_SIN_MCP'):
            # pruebas automaticas: nunca tocar el Resolve real del equipo
            _ESTADO['motivo'] = 'MCP desactivado (CINECAPTIONS_SIN_MCP)'
            return None
        exe = ruta_exe()
        if exe is None:
            _ESTADO['motivo'] = 'ResolveMCP no está instalado (hace falta DaVinci Resolve 21.1 o más nuevo)'
            _ESTADO['ultimo_fallo'] = time.time()
            _ESTADO['fallos_arranque'] += 1
            return None
        try:
            c = _Cliente(exe)
            c.iniciar()
        except Exception as e:
            _ESTADO['motivo'] = f'ResolveMCP no arrancó: {e}'
            _ESTADO['ultimo_fallo'] = time.time()
            _ESTADO['fallos_arranque'] += 1
            try:
                c.cerrar()
            except Exception:
                pass
            return None
        _ESTADO['cliente'] = c
        _ESTADO['motivo'] = ''
        _ESTADO['fallos_arranque'] = 0
        return c


def cerrar():
    with _LOCK:
        c = _ESTADO['cliente']
        _ESTADO['cliente'] = None
    if c is not None:
        c.cerrar()


MENSAJE_COLGADO = 'Resolve no responde (su ventana está colgada). Ciérralo desde el Administrador de tareas y ábrelo de nuevo.'


def script(codigo, timeout=20):
    """Ejecuta Python DENTRO de Resolve. Devuelve (ok, result, error)."""
    try:                                         # v5.4.8: Resolve abierto pero «No responde» desde hace rato: se avisa al instante en vez de esperar 25-75 s a un MCP mudo
        import resolve_bridge
        if resolve_bridge.resolve_colgado(25.0):
            return False, None, MENSAJE_COLGADO
    except Exception:
        pass
    c = cliente()
    if c is None:
        return False, None, _ESTADO['motivo'] or 'sin conexión MCP'
    try:
        r = c.herramienta('run_script_unsafe', {'script': codigo, 'timeout': int(max(1, min(60, timeout)))},
                          timeout=timeout + 15)
    except Exception as e:
        _anotar_fallo(f'{type(e).__name__}: {e}', codigo)
        _tras_fallo(e)
        return False, None, str(e)
    _ESTADO['sin_contestar'] = 0
    if 'error' in r:
        _anotar_fallo(str(r['error']), codigo)
        return False, None, str(r['error'])
    if r.get('es_error'):
        _anotar_fallo(r.get('texto') or 'error', codigo)
        return False, None, r.get('texto') or 'error'
    return True, r.get('result'), ''


_ULTIMO_FALLO = {}


def _tras_fallo(e):
    """v5.4.8: recuperarse solo cuando Resolve se reinicia. Si ResolveMCP no contesta dos veces seguidas y Resolve NO está colgado (un Resolve colgado no se arregla
    reiniciando nuestro lado), se cierra el cliente: la próxima llamada arranca uno nuevo y se engancha a la instancia de Resolve de ahora. Si el cliente se cerró solo,
    cliente() ya lo detecta (vivo())."""
    try:
        if isinstance(e, TimeoutError):
            _ESTADO['sin_contestar'] = _ESTADO.get('sin_contestar', 0) + 1
            if _ESTADO['sin_contestar'] >= 2:
                try:
                    import resolve_bridge
                    colgado = resolve_bridge.resolve_colgado(10.0)
                except Exception:
                    colgado = False
                if not colgado:
                    _ESTADO['sin_contestar'] = 0
                    try:
                        import registro
                        registro.aviso('ResolveMCP no contestó dos veces seguidas: lo reinicio por si Resolve se reinició.', 'Resolve')
                    except Exception:
                        pass
                    cerrar()
        elif isinstance(e, ConnectionError):
            cerrar()
    except Exception:
        pass


def _anotar_fallo(mensaje, codigo=''):
    """v5.11: un script que Resolve no pudo correr (o que no contestó a tiempo) quedaba en silencio: ahora va al Registro (una vez por minuto por mensaje,
    para que un sondeo repetido con Resolve cerrado no llene el log)."""
    try:
        clave = str(mensaje)[:120]
        ahora = time.time()
        if ahora - _ULTIMO_FALLO.get(clave, 0) < 60:
            return
        _ULTIMO_FALLO[clave] = ahora
        import registro
        primera = next((l.strip() for l in str(codigo).splitlines() if l.strip() and not l.strip().startswith('#')), '')
        registro.aviso(f'Resolve no pudo con un script: {str(mensaje).strip().splitlines()[0][:200] if str(mensaje).strip() else "sin detalle"}', 'Resolve',
                       detalle=f'{mensaje}\nscript: {primera[:200]}')
    except Exception:
        pass


_INFO = r'''
import sys
pm = resolve.GetProjectManager()
p = pm.GetCurrentProject() if pm else None
tl = p.GetCurrentTimeline() if p else None
info = {'producto': resolve.GetProductName(), 'version': resolve.GetVersionString(),
        'pagina': resolve.GetCurrentPage(), 'proyecto': p.GetName() if p else None,
        'timeline': tl.GetName() if tl else None}
if tl:
    try:
        info['fps'] = float(tl.GetSetting('timelineFrameRate') or 0)
        info['ancho'] = int(tl.GetSetting('timelineResolutionWidth') or 0)
        info['alto'] = int(tl.GetSetting('timelineResolutionHeight') or 0)
        info['inicio'] = tl.GetStartFrame()
        info['fin'] = tl.GetEndFrame()
        info['timecode'] = tl.GetCurrentTimecode()
        info['pistas_video'] = tl.GetTrackCount('video')
        info['pistas_audio'] = tl.GetTrackCount('audio')
        info['pistas_subtitulos'] = tl.GetTrackCount('subtitle')
    except Exception as e:
        info['aviso'] = repr(e)
result = info
'''


def estado(pasivo=False, refrescar=False):
    """{'conectado': bool, 'producto', 'version', 'proyecto', 'timeline', ...}

    pasivo: no arranca ResolveMCP (para las preguntas de estado del arranque).
    Se guarda unos segundos: la ventana pregunta seguido."""
    if not refrescar and time.time() - _ESTADO['cache_t'] < CACHE_ESTADO_S and _ESTADO['cache']:
        return dict(_ESTADO['cache'])
    c = cliente(arrancar=not pasivo)
    if c is None:
        return {'conectado': False, 'mcp': ruta_exe() is not None, 'motivo': _ESTADO['motivo']}
    try:
        st = c.herramienta('get_resolve_status', timeout=10)
    except Exception as e:
        return {'conectado': False, 'mcp': True, 'motivo': str(e)}
    if not st.get('running'):
        d = {'conectado': False, 'mcp': True, 'motivo': 'Resolve está cerrado', 'version': st.get('version')}
    else:
        ok, info, err = script(_INFO, timeout=10)
        d = dict(info or {}) if ok else {'motivo': err}
        d.update(conectado=ok, mcp=True)
    _ESTADO['cache'] = d
    _ESTADO['cache_t'] = time.time()
    return dict(d)


def conectado_recientemente():
    """True si ResolveMCP sigue vivo y su última respuesta (aunque tenga rato) decía que Resolve estaba conectado. Para las preguntas SIN esperar
    (modo pasivo): estado_cacheado() caduca a los 30 s y, tras un GO largo, hacía creer que Resolve «no estaba» y GO acababa con «Falta un clic en
    Resolve» aunque estuviera conectado."""
    c = _ESTADO['cliente']
    return bool(c is not None and c.vivo() and (_ESTADO['cache'] or {}).get('conectado'))


def _refrescar_estado():
    """Vuelve a preguntarle a Resolve (proyecto y timeline nuevos). Antes se ponía la caché a 0: si el programa miraba «¿Resolve conectado?» sin
    preguntar (modo pasivo) en ese instante, la caché vacía decía «no» y GO acababa con «Falta un clic en Resolve» sin haber colocado nada."""
    try:
        estado(refrescar=True)
    except Exception:
        _ESTADO['cache_t'] = 0


def disponible(pasivo=False):
    return bool(estado(pasivo=pasivo).get('conectado'))


def estado_cacheado(max_edad_s=30.0):
    """Lo ultimo que se supo, sin llamar a nada (para el hilo de la ventana)."""
    c = _ESTADO['cliente']
    if _ESTADO['cache'] and time.time() - _ESTADO['cache_t'] < max_edad_s and c is not None and c.vivo():
        return dict(_ESTADO['cache'])
    return {'conectado': False}


def abrir_resolve(timeout=90):
    """Abre DaVinci Resolve (herramienta launch_resolve) y espera a que conteste."""
    c = cliente()
    if c is None:
        return False, _ESTADO['motivo']
    try:
        r = c.herramienta('launch_resolve', timeout=timeout)
    except Exception as e:
        return False, str(e)
    _ESTADO['cache_t'] = 0
    texto = r.get('texto') or json.dumps(r)
    return 'running' in texto.lower(), texto


def arrancar_resolve(decir=None, espera_s=240):
    """Abre Resolve y espera a que conteste, REINTENTANDO: launch_resolve corta a los 60 s («Resolve did not respond») y en un arranque en frío
    (o tras un cierre mal hecho) el primer intento puede no llegar; antes se esperaba sin volver a pedirlo. Devuelve (ok, texto)."""
    from i18n import tr
    inicio = time.time()
    texto, intento = '', 0
    while time.time() - inicio < espera_s:
        intento += 1
        ok, texto = abrir_resolve(timeout=80)
        if ok or resolve_abierto():
            return True, texto
        if decir:
            try:
                decir(tr('Resolve tarda en abrirse… (intento {n})', n=intento + 1))
            except Exception:
                pass
        time.sleep(3.0)
    return False, texto


def se_cerro(err) -> bool:
    """v5.5.1: ¿el error del MCP dice que Resolve no está abierto (se cerró o se cayó)?"""
    t = str(err or '').lower()
    return 'not running' in t or 'no está abierto' in t or 'está cerrado' in t


def responde(timeout=20) -> bool:
    """v5.5.1: ¿Resolve contesta a un script mínimo? (False = colgado o cerrado). Sirve en Windows y en Mac."""
    try:
        ok, r, _e = script('result = 1', timeout=timeout)
        return bool(ok and r == 1)
    except Exception:
        return False


def resolve_abierto():
    """True/False si Resolve esta corriendo (None si no hay MCP)."""
    c = cliente()
    if c is None:
        return None
    try:
        return bool(c.herramienta('get_resolve_status', timeout=10).get('running'))
    except Exception:
        return None


# v5.2 (pedido: «debe abrir automaticamente Resolve si esta cerrado y abrir el
# proyecto mas reciente; utiliza el MCP, que tenga control total»). Si el
# proyecto abierto no es uno guardado (el «Untitled Project» con el que arranca
# Resolve) se busca en TODAS las carpetas de la base de datos el modificado mas
# recientemente que tenga timelines y se abre; luego su timeline y la pagina Edit.
_PREPARAR = r'''
import datetime
pm = resolve.GetProjectManager()
p = pm.GetCurrentProject()
r = {'cargado': None, 'probados': []}

def _fecha(a):
    try:
        return datetime.datetime.fromisoformat(str(a.get('lastModifiedDate'))).timestamp()
    except Exception:
        return 0.0

def _todos():
    salida = []
    def rec(ruta, prof):
        for n, a in (pm.GetProjectAttributesInCurrentFolder() or {}).items():
            salida.append((_fecha(a), ruta, n))
        if prof < 8:
            for c in (pm.GetFolderListInCurrentFolder() or []):
                if pm.OpenFolder(c):
                    rec(ruta + [c], prof + 1)
                    pm.GotoParentFolder()
    pm.GotoRootFolder()
    rec([], 0)
    return sorted(salida, reverse=True)

nombre = p.GetName() if p else None
proyectos = []
# Solo se cambia de proyecto si CineCaptions acaba de abrir Resolve (o se pide):
# con Resolve ya abierto, el proyecto del usuario manda SIEMPRE (un proyecto
# recien creado aun no figura en la lista de guardados y se confundia con el
# «Untitled Project» del arranque).
sin_titulo = p is None or (nombre or '').startswith('Untitled Project')
vacio = (p is not None) and (p.GetTimelineCount() or 0) == 0
if PERMITIR_CAMBIO and (sin_titulo or vacio):
    proyectos = _todos()
    for _, ruta, n in proyectos[:6]:
        if p is not None and n == nombre:
            continue
        pm.GotoRootFolder()
        if not all(pm.OpenFolder(c) for c in ruta):
            continue
        nuevo = pm.LoadProject(n)
        r['probados'].append(n)
        if nuevo and (nuevo.GetTimelineCount() or 0) > 0:
            p = nuevo
            r['cargado'] = n
            break
        if nuevo:
            p = nuevo
p = pm.GetCurrentProject()
tl = p.GetCurrentTimeline() if p else None
if p and tl is None and (p.GetTimelineCount() or 0) > 0:
    tl = p.GetTimelineByIndex(1)
    if tl:
        p.SetCurrentTimeline(tl)
if PAGINA:
    try:
        resolve.OpenPage(PAGINA)
    except Exception:
        pass
r.update(proyecto=p.GetName() if p else None, timeline=tl.GetName() if tl else None,
         timelines=(p.GetTimelineCount() if p else 0), recientes=[n for _, _, n in proyectos[:5]])
result = r
'''


def preparar_resolve(abrir=True, al_estado=None, forzar_reciente=False, pagina='edit', espera_s=150):
    """Deja Resolve listo para trabajar: lo abre si esta cerrado (abrir=True),
    carga el proyecto mas reciente si no hay uno guardado abierto y pone su
    timeline y la pagina Edit. al_estado(texto) va contando lo que hace.
    Devuelve {'ok', 'lanzado', 'cargado', 'proyecto', 'timeline', 'motivo'}."""
    def decir(texto):
        if al_estado:
            try:
                al_estado(texto)
            except Exception:
                pass
    from i18n import tr
    salida = {'ok': False, 'lanzado': False, 'cargado': None, 'proyecto': None, 'timeline': None, 'motivo': ''}
    c = cliente()
    if c is None:
        salida['motivo'] = _ESTADO['motivo'] or 'sin conexión MCP'
        return salida
    abierto = resolve_abierto()
    if abierto:
        _reparar_vistas()
    if not abierto:
        if not abrir:
            salida['motivo'] = tr('DaVinci Resolve está cerrado')
            return salida
        decir(tr('Abriendo DaVinci Resolve…'))
        salida['lanzado'] = True
        ok, texto = arrancar_resolve(decir, max(espera_s, 240))
        if not ok:
            salida['motivo'] = tr('Resolve no terminó de abrirse ({t})', t=str(texto)[:120])
            return salida
        decir(tr('Resolve abierto: buscando tu proyecto más reciente…'))
    codigo = f'PERMITIR_CAMBIO = {bool(forzar_reciente or salida["lanzado"])!r}\nPAGINA = {pagina!r}\n' + _PREPARAR
    # recien abierto, el gestor de proyectos puede tardar unos segundos en contestar
    for intento in range(6):
        ok, r, err = script(codigo, timeout=60)
        if ok and isinstance(r, dict):
            break
        if se_cerro(err) and abrir and intento < 5:                     # v5.5.1: Resolve se cerró entre medias: se vuelve a abrir
            decir(tr('Abriendo DaVinci Resolve…'))
            salida['lanzado'] = True
            arrancar_resolve(decir, max(espera_s, 240))
            codigo = f'PERMITIR_CAMBIO = True\nPAGINA = {pagina!r}\n' + _PREPARAR
            continue
        time.sleep(2.5)
    else:
        salida['motivo'] = f'MCP: {err}'
        return salida
    _ESTADO['cache_t'] = 0
    salida.update(ok=bool(r.get('proyecto')), cargado=r.get('cargado'), proyecto=r.get('proyecto'),
                  timeline=r.get('timeline'), timelines=r.get('timelines'), recientes=r.get('recientes'))
    if r.get('cargado'):
        decir(tr('Proyecto «{p}» abierto · timeline «{t}»', p=r.get('cargado'), t=r.get('timeline') or '—'))
    if not r.get('timeline'):
        salida['ok'] = False
        salida['motivo'] = tr('El proyecto «{p}» no tiene ningún timeline todavía.', p=r.get('proyecto') or '—')
    return salida


# ---------------------------------------------------------------------------
# v5.8: «Crea tu estilo» — el timeline-guia con los 30 ejemplos, hecho dentro de Resolve con los efectos REALES Luxe Shine y Luxe Slide
# ---------------------------------------------------------------------------
_GUIA = threading.Lock()


def abrir_guia(ruta_script, nombre='Crea tu estilo', datos=None):
    """Arma (o abre, si ya está en el proyecto) el timeline «Crea tu estilo» con los 30 ejemplos. El trabajo corre DENTRO de Resolve
    (2_recursos/guia_estilo/construir_guia.py, en un hilo: son ~90 clips) y lee ~/DaVinciSubtitles/guia_estilo_ejemplos.json, que se escribe aquí.
    Devuelve (ok, mensaje)."""
    import archivos_seguros
    with _GUIA:                    # el JSON es uno solo: la galería (vistas) y «Abrir en Resolve» no se pisan
        archivos_seguros.escribir_json(Path.home() / 'DaVinciSubtitles' / 'guia_estilo_ejemplos.json', dict(datos or {}, nombre=nombre))
        return ejecutar_py(ruta_script, timeout=1200 if (datos or {}).get('fotos') else 300)       # las vistas (~340 fotogramas) tardan varios minutos


# ---------------------------------------------------------------------------
# Scripts gemelos: correrlos dentro de Resolve, en un hilo, sin limite de 60 s
# ---------------------------------------------------------------------------
_LANZAR = r'''
import sys, threading, types, importlib.util, traceback, time
est = sys.modules.get('_cinecaptions_mcp')
if est is None:
    est = types.ModuleType('_cinecaptions_mcp')
    est.trabajos = {}
    sys.modules['_cinecaptions_mcp'] = est
JOB, RUTA, NOMBRE, ESTADO = %r, %r, %r, %r

def _dejar(d):
    est.trabajos[JOB] = d
    try:                                                # v5.5.8: el resultado también a un archivo: la app lo lee SIN llamar al MCP
        import json, os
        tmp = ESTADO + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, default=str)
        os.replace(tmp, ESTADO)
    except Exception:
        pass

def _correr(res, proy):
    try:
        open(ESTADO + '.vivo', 'w').close()
    except Exception:
        pass
    registro = []
    def _print(*a, **k):
        registro.append(' '.join(str(x) for x in a))
        del registro[:-400]
    try:
        spec = importlib.util.spec_from_file_location(NOMBRE, RUTA)
        mod = importlib.util.module_from_spec(spec)
        mod.__dict__['resolve'] = res
        mod.__dict__['project'] = proy
        mod.__dict__['print'] = _print
        spec.loader.exec_module(mod)
        if hasattr(mod, 'main'):
            mod.main()
        _dejar({'ok': True, 'mensaje': '', 'registro': registro[-60:]})
    except SystemExit as e:
        texto = '' if (e.code in (None, 0)) else str(e.code)
        _dejar({'ok': e.code in (None, 0), 'mensaje': texto, 'registro': registro[-60:]})
    except BaseException as e:
        _dejar({'ok': False, 'mensaje': type(e).__name__ + ': ' + str(e),
                'traza': traceback.format_exc()[-3000:], 'registro': registro[-60:]})

for _k in [k for k, v in list(est.trabajos.items()) if v is not None]:     # (los ya leídos por archivo: v5.5.8)
    est.trabajos.pop(_k, None)
est.trabajos[JOB] = None
threading.Thread(target=_correr, args=(resolve, project), daemon=True, name=JOB).start()
result = 'lanzado'
'''

_PREGUNTAR = r'''
import sys
est = sys.modules.get('_cinecaptions_mcp')
result = {'estado': 'perdido'} if est is None or %(job)r not in est.trabajos else (
    {'estado': 'corriendo'} if est.trabajos[%(job)r] is None else dict(est.trabajos.pop(%(job)r), estado='hecho'))
'''


def _reparar_vistas():
    """v5.8: si una vista real se cortó a medias, el timeline temporal puede haber quedado como el actual: se restaura antes de cualquier trabajo."""
    try:
        import vistas_reales
        vistas_reales.reparar_pendiente()
    except Exception:
        pass


def ejecutar_py(ruta_script, timeout=600, on_progreso=None):
    """Corre un script gemelo dentro de Resolve. Devuelve (ok, mensaje)."""
    ruta = Path(ruta_script)
    if not ruta.exists():
        return False, f'No encuentro el script en {ruta}'
    _reparar_vistas()
    with _TRABAJO:
        job = f'job{int(time.time() * 1000)}'
        nombre = '_cinecaptions_' + ruta.stem.replace(' ', '_').replace('-', '_')
        import tempfile
        carpeta = Path(tempfile.gettempdir()) / 'cinecaptions_trabajos'
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        estado = carpeta / f'{job}.json'
        vivo = carpeta / f'{job}.json.vivo'
        ok, _, err = script(_LANZAR % (job, str(ruta), nombre, str(estado)), timeout=20)
        if not ok:
            return False, f'MCP: {err}'
        inicio = time.time()
        ultima_pregunta = inicio
        # v5.5.8: mientras el trabajo corre NO se llama al MCP. MEDIDO (Tema 6, traza): cada llamada al MCP hace que Resolve guarde el proyecto;
        # coincidiendo con MediaPool.ImportMedia en el hilo del trabajo, Resolve se quedaba bloqueado (el sondeo no contestaba en 25 s y GO lo
        # cerraba). El trabajo deja su resultado en un archivo; aquí solo se mira ese archivo y que Resolve.exe siga vivo. El MCP solo se usa
        # si el trabajo no pudo escribir su archivo «vivo» al empezar.
        while time.time() - inicio < timeout:
            time.sleep(0.5)
            r = None
            if estado.exists():
                try:
                    r = dict(json.loads(estado.read_text(encoding='utf-8')), estado='hecho')
                except (OSError, ValueError):
                    r = None
                if r is not None:
                    for f in (estado, vivo):
                        try:
                            f.unlink()
                        except OSError:
                            pass
            if r is None and sys.platform.startswith('win'):
                try:
                    import resolve_bridge
                    if resolve_bridge._listar_pids_resolve() == []:
                        return False, 'Resolve se cerró mientras trabajaba'
                    if resolve_bridge.resolve_colgado(120) and resolve_bridge._registro_resolve_callado_s() > 120:
                        return False, 'Resolve dejó de responder mientras trabajaba (2 min «No responde» y sin escribir en su registro)'
                except Exception:
                    pass
            if r is None and not vivo.exists() and time.time() - inicio > 8 and time.time() - ultima_pregunta > 1.5:
                ultima_pregunta = time.time()                          # (sin archivo «vivo»: el trabajo no puede escribir ahí; se pregunta como antes, despacio)
                ok, r, err = script(_PREGUNTAR % {'job': job}, timeout=10)
                if not ok:
                    return False, f'MCP: {err}'
                if r.get('estado') == 'corriendo':
                    r = None
            if r is not None:
                if r.get('estado') == 'hecho':
                    _anotar_registro(ruta.name, r)
                    return bool(r.get('ok')), (r.get('mensaje') or '')
                if r.get('estado') == 'perdido':
                    return False, 'Resolve se reinició mientras trabajaba'
            if on_progreso:
                try:
                    on_progreso(time.time() - inicio)
                except Exception:
                    pass
        return False, f'Resolve no terminó en {timeout} segundos (el trabajo puede seguir dentro de Resolve).'


_FOTOGRAMAS = r'''
import os
tl = project.GetCurrentTimeline() if project else None
salida = []
if tl:
    fps = float(tl.GetSetting('timelineFrameRate') or 24)
    entero = int(round(fps))
    def tc_de(frame, df):
        frame = int(frame)
        if df and entero in (30, 60):
            drop = 2 if entero == 30 else 4
            diez = entero * 600 - drop * 9
            minuto = entero * 60 - drop
            d, m = divmod(frame, diez)
            frame += drop * 9 * d + (drop * ((m - drop) // minuto) if m > drop else 0)
        f = frame % entero
        s = frame // entero
        sep = ';' if df else ':'
        return '%02d:%02d:%02d%s%02d' % (s // 3600, s // 60 % 60, s % 60, sep, f)
    inicio_tl = tl.GetStartFrame()
    df = ';' in str(tl.GetStartTimecode() or '')
    if tc_de(inicio_tl, df) != tl.GetStartTimecode():
        df = not df
    base = MARCA if MARCA is not None else inicio_tl
    antes = tl.GetCurrentTimecode()
    for k, t in enumerate(TIEMPOS):
        ruta = os.path.join(CARPETA, 'fotograma_%02d.png' % k)
        ok = tl.SetCurrentTimecode(tc_de(base + round(float(t) * fps), df)) and project.ExportCurrentFrameAsStill(ruta)
        salida.append(ruta if ok and os.path.exists(ruta) else None)
    tl.SetCurrentTimecode(antes)
result = salida
'''


def fotogramas_de(tiempos_s, marca_entrada=None, carpeta=None):
    """Los fotogramas del timeline en esos segundos (desde el inicio de lo
    transcrito). Mueve el cabezal y lo DEJA donde estaba. Devuelve una lista
    de rutas (None donde no se pudo)."""
    import tempfile
    carpeta = Path(carpeta or Path(tempfile.gettempdir()) / 'cinecaptions_vista_previa')
    carpeta.mkdir(parents=True, exist_ok=True)
    codigo = (f'TIEMPOS = {list(map(float, tiempos_s))!r}\nMARCA = {marca_entrada!r}\nCARPETA = {str(carpeta)!r}\n'
              + _FOTOGRAMAS)
    ok, r, _ = script(codigo, timeout=60)
    return [p if p else None for p in (r or [])] if ok and isinstance(r, list) else [None] * len(tiempos_s)


def ir_a_pagina(pagina='edit'):
    ok, r, _ = script(f'result = bool(resolve.OpenPage({pagina!r}))', timeout=10)
    return bool(ok and r)


# v5.10 (pedido: «arrastrar mi video a Inicio y que lo meta a captions y le ponga los captions»): el video soltado se importa a un bin
# «CineCaptions · videos», se arma un timeline NUEVO con su orientación y sus fps, y queda como el actual para que GO ponga ahí los captions.
_CREAR_TIMELINE = r'''
RUTA = %(ruta)r
BASE = %(nombre)r
ANCHO, ALTO, FPS = %(ancho)r, %(alto)r, %(fps)r
PISTA_BROLL = %(pista_broll)r
res = {'proyecto': project.GetName(), 'previo': (project.GetCurrentTimeline().GetName() if project.GetCurrentTimeline() else None)}
import time
# Recién creado el proyecto, Resolve a veces devuelve None (el Media Pool, la carpeta raíz o la subcarpeta que acaba de crear): se reintenta, y antes de rendirse
# se mira si la carpeta se creó aunque la llamada no la devolviera. Sin su bin propio, el video va a la carpeta raíz.
mp = None
raiz = None
carpeta = None
for intento in range(8):
    mp = project.GetMediaPool()
    raiz = mp.GetRootFolder() if mp else None
    if raiz is not None:
        for c in (raiz.GetSubFolderList() or []):
            if c.GetName() == 'CineCaptions · videos':
                carpeta = c
                break
        if carpeta is None:
            try:
                carpeta = mp.AddSubFolder(raiz, 'CineCaptions · videos')
            except Exception:
                carpeta = None
            if carpeta is None:
                for c in (raiz.GetSubFolderList() or []):
                    if c.GetName() == 'CineCaptions · videos':
                        carpeta = c
                        break
        if carpeta is not None:
            break
    time.sleep(0.8)
res['reintentos_media_pool'] = intento
if carpeta is None:
    carpeta = raiz
if carpeta is None:
    raise Exception('Resolve no entregó el Media Pool del proyecto nuevo')
mp.SetCurrentFolder(carpeta)
clip = None
for it in (carpeta.GetClipList() or []):
    try:
        if it.GetClipProperty('File Path') == RUTA:
            clip = it
            break
    except Exception:
        pass
if clip is None:
    items = mp.ImportMedia([RUTA])
    clip = items[0] if items else None
res['clip'] = bool(clip)
if clip:
    existentes = set()
    for i in range(1, int(project.GetTimelineCount() or 0) + 1):
        t = project.GetTimelineByIndex(i)
        if t:
            existentes.add(t.GetName())
    nombre, k = BASE, 2
    while nombre in existentes:
        nombre = '%%s %%d' %% (BASE, k)
        k += 1
    tl = mp.CreateEmptyTimeline(nombre)
    res['timeline'] = nombre if tl else None
    if tl:
        ajustes = {}
        for clave, valor in (('useCustomSettings', '1'), ('timelineResolutionWidth', str(ANCHO)), ('timelineResolutionHeight', str(ALTO)),
                             ('timelineOutputResolutionWidth', str(ANCHO)), ('timelineOutputResolutionHeight', str(ALTO)), ('timelineFrameRate', str(FPS))):
            try:
                ajustes[clave] = bool(tl.SetSetting(clave, valor))
            except Exception as e:
                ajustes[clave] = repr(e)
        res['ajustes'] = ajustes
        project.SetCurrentTimeline(tl)
        puestos = mp.AppendToTimeline([clip])
        res['anadido'] = len(puestos or [])
        # el audio ORIGINAL del video tiene que estar en A1 y sonar: se comprueba y, si Resolve solo metió la imagen, se añade el audio aparte
        try:
            def _a1():
                return tl.GetItemListInTrack('audio', 1) or []
            tipo = str(clip.GetClipProperty('Type') or '').lower()
            try:
                canales = int(float(clip.GetClipProperty('Audio Ch') or 0))
            except Exception:
                canales = 0
            res['clip_con_audio'] = bool('audio' in tipo or canales > 0)
            res['audio_a1'] = len(_a1())
            if res['clip_con_audio'] and not _a1():
                mp.AppendToTimeline([{'mediaPoolItem': clip, 'mediaType': 2, 'trackIndex': 1, 'recordFrame': tl.GetStartFrame()}])
                res['audio_repuesto'] = len(_a1())
            try:
                tl.SetTrackEnable('audio', 1, True)
                for it in _a1():
                    it.SetClipEnabled(True)
            except Exception:
                pass
        except Exception as e:
            res['audio_error'] = repr(e)
        for it in (tl.GetItemListInTrack('video', 1) or []):
            try:
                it.SetProperty('Scaling', resolve.SCALE_FIT)
            except Exception:
                pass
        res['ancho'] = int(float(tl.GetSetting('timelineResolutionWidth') or 0))
        res['alto'] = int(float(tl.GetSetting('timelineResolutionHeight') or 0))
        res['fps'] = float(tl.GetSetting('timelineFrameRate') or 0)
        res['inicio'] = tl.GetStartFrame()
        res['fin'] = tl.GetEndFrame()
        if PISTA_BROLL:
            # v5.4.8: una pista de video vacía y BLOQUEADA justo encima de V1: los captions (que saltan las pistas bloqueadas) se ponen más arriba y el B-roll queda DEBAJO de ellos
            try:
                if tl.AddTrack('video'):
                    n = int(tl.GetTrackCount('video'))
                    tl.SetTrackName('video', n, 'FX-BROLL')
                    res['pista_broll'] = bool(tl.SetTrackLock('video', n, True))
            except Exception as e:
                res['pista_broll_error'] = repr(e)
result = res
'''


# v5.10 (pedido: «al arrastrar un video debe crear un proyecto completamente NUEVO llamado CineCaptions y, si hay uno abierto, cerrarlo»): cada video
# soltado vive en un proyecto nuevo. Se guarda el que hubiera abierto (nunca se pierde trabajo), se cierra y se crea «CineCaptions»; si ese nombre ya
# existe en la base de datos (en cualquier carpeta) se numera: «CineCaptions 2», «CineCaptions 3»…
_PROYECTO = r'''
BASE = %(nombre)r
pm = resolve.GetProjectManager()
p = pm.GetCurrentProject()
res = {'previo': p.GetName() if p else None, 'accion': None}

def todos(prof, salida):
    for n in (pm.GetProjectListInCurrentFolder() or []):
        salida.add(n)
    if prof < 5:
        for c in (pm.GetFolderListInCurrentFolder() or []):
            if pm.OpenFolder(c):
                todos(prof + 1, salida)
                pm.GotoParentFolder()
    return salida

if p is not None:
    sin_nada = (p.GetName() or '').startswith('Untitled Project') and int(p.GetTimelineCount() or 0) == 0
    if not sin_nada:
        try:
            res['guardado'] = bool(pm.SaveProject())
        except Exception as e:
            res['guardado'] = repr(e)
    try:
        res['cerrado'] = bool(pm.CloseProject(p))
    except Exception as e:
        res['cerrado'] = repr(e)
pm.GotoRootFolder()
existentes = todos(0, set())
pm.GotoRootFolder()
# Un nombre puede estar tomado sin verse en la lista (una entrada borrada a medias de la base de datos): CreateProject devuelve None. En vez de rendirse se
# prueba con el siguiente número; si ninguno vale, se vuelve a abrir el proyecto que había (nunca se deja al usuario en un «Untitled Project»).
nombre, k = BASE, 2
nuevo = None
res['rechazados'] = []
for _intento in range(8):
    while nombre in existentes:
        nombre = '%%s %%d' %% (BASE, k)
        k += 1
    nuevo = pm.CreateProject(nombre)
    if nuevo:
        break
    res['rechazados'].append(nombre)
    existentes.add(nombre)
res['accion'] = 'creado' if nuevo else 'no_creo'
if not nuevo and res.get('previo'):
    try:
        pm.LoadProject(res['previo'])
    except Exception:
        pass
q = pm.GetCurrentProject()
res['proyecto'] = q.GetName() if q else None
try:
    resolve.OpenPage('edit')
except Exception:
    pass
result = res
'''


def preparar_proyecto(nombre='CineCaptions', abrir=True, al_estado=None, espera_s=150):
    """Abre Resolve si está cerrado, guarda y cierra el proyecto que hubiera abierto y CREA uno nuevo («CineCaptions», o «CineCaptions 2»… si el nombre ya
    existe). Devuelve {'ok', 'lanzado', 'proyecto' (el nombre real), 'accion', 'previo', 'cerrado', 'guardado', 'motivo'}."""
    from i18n import tr

    def decir(texto):
        if al_estado:
            try:
                al_estado(texto)
            except Exception:
                pass
    salida = {'ok': False, 'lanzado': False, 'proyecto': None, 'accion': None, 'previo': None, 'motivo': ''}
    if cliente() is None:
        salida['motivo'] = _ESTADO['motivo'] or 'sin conexión MCP'
        return salida
    abierto = resolve_abierto()
    if abierto:
        _reparar_vistas()
    else:
        if not abrir:
            salida['motivo'] = tr('DaVinci Resolve está cerrado')
            return salida
        decir(tr('Abriendo DaVinci Resolve…'))
        salida['lanzado'] = True
        ok, texto = arrancar_resolve(decir, max(espera_s, 240))
        if not ok:
            salida['motivo'] = tr('Resolve no terminó de abrirse ({t})', t=str(texto)[:120])
            return salida
    decir(tr('Creando un proyecto nuevo «{p}» en Resolve…', p=nombre))
    codigo = _PROYECTO % {'nombre': str(nombre)}
    # Recién abierto, Resolve tarda en tener listo el gestor de proyectos: la primera vez CreateProject devuelve None (en la app real salió «no_creo» a los
    # 20 s de abrirse y los captions acabaron en OTRO timeline, sin el video ni su sonido). Se reintenta cada 5 s hasta que lo cree (tope 150 s).
    r, err, ok = None, '', False
    limite = time.time() + 150
    relanzado = False
    while True:
        ok, r, err = script(codigo, timeout=60)
        if ok and isinstance(r, dict) and r.get('accion') == 'creado' and r.get('proyecto'):
            break
        if time.time() > limite:
            break
        if not ok and se_cerro(err) and not relanzado:
            # v5.5.1: Resolve se cerró (o se cayó) justo después de comprobar que estaba abierto: antes se insistía 150 s contra un Resolve muerto
            # y GO paraba con «DaVinci Resolve is not running»; ahora se vuelve a abrir aquí mismo (una vez) y se sigue
            relanzado = True
            decir(tr('Abriendo DaVinci Resolve…'))
            salida['lanzado'] = True
            if arrancar_resolve(decir, max(espera_s, 240))[0]:
                limite = time.time() + 150
            continue
        decir(tr('Resolve termina de arrancar…'))
        time.sleep(5.0)
    if not (ok and isinstance(r, dict)):
        salida['motivo'] = f'MCP: {err}'
        return salida
    _refrescar_estado()
    salida.update(proyecto=r.get('proyecto'), accion=r.get('accion'), previo=r.get('previo'), cerrado=r.get('cerrado'), guardado=r.get('guardado'))
    salida['ok'] = bool(r.get('proyecto')) and r.get('accion') == 'creado'
    if not salida['ok']:
        salida['motivo'] = tr('Resolve no creó el proyecto «{p}» ({a}).', p=nombre, a=r.get('accion') or '—')
    else:
        decir(tr('Proyecto nuevo «{p}» creado.', p=r.get('proyecto')))
    return salida


_FPS_COMUNES = (23.976, 24.0, 25.0, 29.97, 30.0, 48.0, 50.0, 59.94, 60.0)


def medir_medio(ruta):
    """Del video (o audio) soltado, SIN decodificar nada (PyAV lee la cabecera): {'ancho', 'alto', 'fps', 'duracion', 'solo_audio'} y el
    formato del timeline que le corresponde ('tl_ancho', 'tl_alto', 'tl_fps'): vertical 1080×1920, horizontal 1920×1080, cuadrado 1080×1080;
    un audio sin imagen se trata como vertical. Con la rotación de los celulares (metadato «rotate») ya aplicada.
    v5.5: con la opción «Abrir siempre en vertical» (por defecto) el timeline es SIEMPRE 1080×1920, sea cual sea el video."""
    info = {'ancho': 0, 'alto': 0, 'fps': 30.0, 'duracion': None, 'solo_audio': True}
    try:
        import av
        with av.open(str(ruta)) as c:
            if c.duration:
                info['duracion'] = float(c.duration / av.time_base)
            for s in c.streams.video:
                if not (s.width and s.height and s.average_rate):          # la carátula de un mp3 no cuenta como video
                    continue
                w, h = int(s.width), int(s.height)
                try:
                    if int(float((s.metadata or {}).get('rotate', 0))) % 180 == 90:
                        w, h = h, w
                except (TypeError, ValueError):
                    pass
                f = float(s.average_rate)
                cerca = min(_FPS_COMUNES, key=lambda x: abs(x - f))
                info.update(ancho=w, alto=h, fps=cerca if abs(cerca - f) < 0.05 else round(f, 3), solo_audio=False)
                break
    except Exception:
        pass
    w, h = info['ancho'], info['alto']
    if info['solo_audio'] or h > w * 1.05:
        info.update(tl_ancho=1080, tl_alto=1920)
    elif w > h * 1.05:
        info.update(tl_ancho=1920, tl_alto=1080)
    else:
        info.update(tl_ancho=1080, tl_alto=1080)
    try:                                                  # v5.5: «cada vez que abras un proyecto, siempre en vertical» (pref go_vertical, activada por defecto)
        import ajustes_ui
        if ajustes_ui.leer_prefs().get('go_vertical', True) is not False:
            info.update(tl_ancho=1080, tl_alto=1920)
    except Exception:
        pass
    info['tl_fps'] = info['fps']
    return info


def crear_timeline_con_video(ruta, nombre=None, ancho=1080, alto=1920, fps=30.0, pista_broll=False):
    """Importa `ruta` al Media Pool y arma con él un timeline nuevo (el actual al terminar). Devuelve el informe de Resolve
    ({'timeline', 'ancho', 'alto', 'fps', 'inicio', 'fin', 'anadido', ...}) o {'error': texto}."""
    nombre = nombre or ('CineCaptions · ' + Path(str(ruta)).stem)
    codigo = _CREAR_TIMELINE % {'ruta': str(ruta), 'nombre': str(nombre)[:60], 'ancho': int(ancho), 'alto': int(alto), 'fps': '%g' % float(fps), 'pista_broll': bool(pista_broll)}      # «30», «29.97»: Resolve no acepta «30.0»
    ok, r, err = script(codigo, timeout=60)
    _refrescar_estado()
    if not ok or not isinstance(r, dict):
        return {'error': err or 'Resolve no contestó'}
    if not r.get('clip'):
        return {'error': 'Resolve no pudo importar el archivo', **r}
    if not r.get('timeline'):
        return {'error': 'Resolve no pudo crear el timeline', **r}
    return r


_ASEGURAR_AUDIO = r"""
tl = project.GetCurrentTimeline() if project else None
res = {'timeline': tl.GetName() if tl else None, 'v1': 0, 'a1_antes': 0, 'repuestos': 0, 'a1_ahora': 0}
if tl:
    a1 = tl.GetItemListInTrack('audio', 1) or []
    v1 = [it for it in (tl.GetItemListInTrack('video', 1) or []) if it]
    res['v1'], res['a1_antes'] = len(v1), len(a1)
    mp = project.GetMediaPool()
    for it in v1:
        try:
            mpi = it.GetMediaPoolItem()
            if not mpi:
                continue
            tipo = str(mpi.GetClipProperty('Type') or '').lower()
            canales = int(float(mpi.GetClipProperty('Audio Ch') or 0))
            if not ('audio' in tipo or canales > 0):
                continue
            ini, fin = it.GetStart(), it.GetEnd()
            cubierto = any(a.GetStart() < fin and a.GetEnd() > ini for a in a1)
            if not cubierto:
                mp.AppendToTimeline([{'mediaPoolItem': mpi, 'mediaType': 2, 'trackIndex': 1, 'recordFrame': ini,
                                      'startFrame': it.GetLeftOffset(), 'endFrame': it.GetLeftOffset() + it.GetDuration() - 1}])
                res['repuestos'] += 1
                a1 = tl.GetItemListInTrack('audio', 1) or []
        except Exception as e:
            res['error'] = repr(e)
    try:
        tl.SetTrackEnable('audio', 1, True)
        for a in (tl.GetItemListInTrack('audio', 1) or []):
            a.SetClipEnabled(True)
    except Exception:
        pass
    res['a1_ahora'] = len(tl.GetItemListInTrack('audio', 1) or [])
result = res
"""


def asegurar_audio_original():
    """Después de colocar los captions: el audio original del video sigue en A1 (y sonando). Si faltara se repone. Devuelve el informe
    {'v1', 'a1_antes', 'repuestos', 'a1_ahora'} o {} si Resolve no contestó. Nunca lanza."""
    try:
        ok, r, _err = script(_ASEGURAR_AUDIO, timeout=30)
        return r if ok and isinstance(r, dict) else {}
    except Exception:
        return {}


def _anotar_registro(nombre, r):
    """Lo que el script imprimio, para el diagnostico (antes iba a la consola de Resolve)."""
    try:
        carpeta = Path.home() / 'DaVinciSubtitles'
        carpeta.mkdir(parents=True, exist_ok=True)
        lineas = [f'== {time.strftime("%Y-%m-%d %H:%M:%S")}  {nombre}  ok={r.get("ok")}  {r.get("mensaje") or ""}']
        lineas += r.get('registro') or []
        if r.get('traza'):
            lineas.append(r['traza'])
        (carpeta / 'mcp_ultimo_script.txt').write_text('\n'.join(lineas) + '\n', encoding='utf-8')
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Funciones nuevas que da el MCP
# ---------------------------------------------------------------------------
def exportar_fotograma(destino):
    """El fotograma actual del timeline como imagen (vistas previas reales).
    Devuelve la ruta o None. ~50 ms con Resolve abierto."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    ok, r, _ = script('result = bool(project and project.ExportCurrentFrameAsStill(%r))' % str(destino), timeout=20)
    return destino if ok and r and destino.exists() else None


_SELECCION = r'''
tl = project.GetCurrentTimeline() if project else None
items = []
if tl:
    try:
        for it in (tl.GetSelectedClips() or []):
            items.append({'nombre': it.GetName(), 'inicio': it.GetStart(), 'fin': it.GetEnd()})
    except Exception as e:
        items = [{'error': repr(e)}]
result = items
'''


def seleccion_timeline():
    """Los clips seleccionados en el timeline (API de Resolve 21.0.4+)."""
    ok, r, _ = script(_SELECCION, timeout=10)
    return r if ok and isinstance(r, list) else []


def ir_a_timecode(tc):
    ok, r, _ = script('tl = project.GetCurrentTimeline()\nresult = bool(tl and tl.SetCurrentTimecode(%r))' % str(tc),
                      timeout=10)
    return bool(ok and r)


def diagnostico():
    """Lineas para el diagnostico del programa."""
    exe = ruta_exe()
    lineas = [f'ResolveMCP: {exe or "no encontrado"}']
    if exe:
        d = estado(refrescar=True)
        if d.get('conectado'):
            lineas.append(f"  conectado: {d.get('producto')} {d.get('version')} · proyecto «{d.get('proyecto')}»"
                          f" · timeline «{d.get('timeline')}»")
            t = time.time()
            ok, _, err = script('result = 1', timeout=10)
            lineas.append(f'  latencia de una orden: {(time.time() - t) * 1000:.0f} ms' + ('' if ok else f' (error: {err})'))
        else:
            lineas.append(f"  sin conexión: {d.get('motivo') or '—'}")
    return lineas
