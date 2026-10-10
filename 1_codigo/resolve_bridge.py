# CineCaptions · By Cinema Productions
# 1_codigo/resolve_bridge.py — conexión con Resolve: API externa (Studio), Puente (Free) o paso manual; ejecuta los scripts.
"""\nresolve_bridge.py\n-----------------\nPuente para hablar con DaVinci Resolve DESDE AFUERA (scripting externo).\n\nSolo funciona con Resolve **Studio**. La version gratuita cerró esa via en\n19.1; ahi el bridge devuelve None y todo cae al camino habitual (guardar la\norden en disco, mostrar un mensaje al usuario para que corra el script del\nmenu).\n\nLa API oficial se activa con dos cosas:\n  - una libreria nativa (fusionscript.dll en Windows, libfusionscript.so en\n    Mac/Linux) que ya viene instalada con Resolve;\n  - un modulo Python (DaVinciResolveScript.py) que sabe hablarle a esa\n    libreria y ademas necesita que sys.path lo encuentre.\n\nCuando esta todo, `conectar()` devuelve un objeto \'resolve\' identico al\nque Resolve inyecta cuando el script corre desde adentro. Con eso, los\nscripts de resolve_scripts/ pueden ejecutarse SIN entrar al menu de\nWorkspace > Scripts, con solo llamar a su funcion main() pasandole el\n\'resolve\'.\n"""
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
import sidecar_lua
from i18n import tr
def _rutas_probables():
    """Ubicaciones tipicas de la libreria de scripting de Resolve por SO."""
    if sys.platform.startswith('win'):
        yield (Path('C:\\ProgramData\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting\\Modules'), Path('C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\fusionscript.dll'))
    else:
        if sys.platform == 'darwin':
            yield (Path('/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules'), Path('/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so'))
        else:
            yield (Path('/opt/resolve/Developer/Scripting/Modules'), Path('/opt/resolve/libs/Fusion/fusionscript.so'))
def _resolve_dir_windows():
    """Devuelve la carpeta de instalacion de DaVinci Resolve en Windows.\n\n    Prueba primero la ruta default (C:\\Program Files\\...), y si no\n    existe, lee la clave del registro que Blackmagic escribe al instalar.\n    Sirve para instalaciones en D:\\, en Program Files (x86), etc.\n    """
    default = 'C:\\Program Files\\Blackmagic Design\\DaVinci Resolve'
    if os.path.isdir(default):
        return default
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for key_path in ('SOFTWARE\\Blackmagic Design\\DaVinci Resolve',
                             'SOFTWARE\\WOW6432Node\\Blackmagic Design\\DaVinci Resolve'):
                try:
                    with winreg.OpenKey(hive, key_path) as k:
                        for value_name in ('ProgramFilesPath', 'InstallDir',
                                           'InstallLocation'):
                            try:
                                val, _ = winreg.QueryValueEx(k, value_name)
                                if val and os.path.isdir(val):
                                    return val
                            except OSError:
                                continue
                except OSError:
                    continue
    except Exception:
        pass
    return default
def _carpeta_del_python3_dll():
    """Carpeta con el python3.dll del interprete que ESTA corriendo ahora.\n\n    fusionscript.dll no es una extension normal de CPython: no se enlaza\n    con python3.dll ni con python3XX.dll. Cuando se importa, se busca un\n    CPython por su cuenta -primero la variable PYTHON3HOME, y si no esta,\n    la clave del registro HKCU\\Software\\Python\\PythonCore\\<ver>\\\n    InstallPath- y de ahi saca por GetProcAddress los simbolos Py_*.\n\n    En la app compilada eso es un desastre: el registro apunta al Python\n    que el usuario tenga instalado (3.14, 3.13, o ninguno), NO al que\n    lleva adentro el .exe. Asi fusionscript mete un SEGUNDO interprete en\n    el proceso, PyInit_fusionscript se ata a la version equivocada y\n    devuelve NULL sin fijar excepcion:\n        SystemError: initialization of fusionscript failed\n                     without raising an exception\n    Y en una maquina sin Python instalado no hay registro que mirar, asi\n    que fallaba practicamente en cualquier equipo.\n\n    Apuntandole a nuestro propio python3.dll queda atado al interprete\n    correcto. Ese python3.dll es solo un reenviador a python312.dll POR\n    NOMBRE, y a ese si lo deduplica el loader con el que ya esta cargado.\n    """
    candidatas = []
    if getattr(sys, 'frozen', False):
        mei = getattr(sys, '_MEIPASS', None)
        if mei:
            candidatas.append(Path(mei))
        try:
            exe_dir = Path(sys.executable).resolve().parent
            candidatas += [exe_dir, exe_dir / '_internal']
        except Exception:
            pass
    candidatas += [Path(sys.prefix), Path(sys.base_prefix)]
    for carpeta in candidatas:
        try:
            if (carpeta / 'python3.dll').is_file():
                return carpeta
        except Exception:
            pass
def _setear_variables_de_entorno():
    """Fija RESOLVE_SCRIPT_API y RESOLVE_SCRIPT_LIB agregando además la carpeta al PATH y precargando DLL en Windows.\n    """
    if sys.platform.startswith('win'):
        carpeta_py3 = _carpeta_del_python3_dll()
        if carpeta_py3 is not None:
            os.environ['PYTHON3HOME'] = str(carpeta_py3)
        resolve_dir = _resolve_dir_windows()
        if os.path.isdir(resolve_dir):
            try:
                os.add_dll_directory(resolve_dir)
            except Exception:
                pass
            if resolve_dir not in os.environ.get('PATH', ''):
                os.environ['PATH'] = resolve_dir + os.pathsep + os.environ.get('PATH', '')
            mod_dir = os.path.join(resolve_dir, 'Developer\\Scripting\\Modules')
            if os.path.isdir(mod_dir) and mod_dir not in sys.path:
                    sys.path.insert(0, mod_dir)
    for modulos, lib in _rutas_probables():
        if modulos.is_dir():
            os.environ['RESOLVE_SCRIPT_API'] = str(modulos.parent)
            if str(modulos) not in sys.path:
                sys.path.insert(0, str(modulos))
            if lib.exists():
                os.environ['RESOLVE_SCRIPT_LIB'] = str(lib)
            return True
    return False
MENSAJE_SCRIPTING_DESACTIVADO = tr('Resolve está abierto, pero no está aceptando scripts externos.\n\nSe arregla en un sitio, y hay que hacerlo una sola vez:\n\n1. En Resolve, abre  Preferencias  >  Sistema  >  General\n   (en inglés: Preferences > System > General).\n2. Busca  «External scripting using»  y ponlo en  «Local».\n3. Acepta, cierra Resolve por completo y vuelve a abrirlo.\n\nSi ya estaba en «Local», cierra Resolve del todo y ábrelo otra vez: la conexión de scripting a veces no llega a levantar cuando Resolve arranca junto con el sistema.\n\n— — —\nHay un segundo camino que no depende de esa preferencia, por si el primero se te resiste: cierra este programa y vuelve a abrirlo (así deja los scripts en el menú de Resolve), y luego corre\n\n    Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Puente\n\nDéjalo corriendo y los botones funcionan igual.')
def es_scripting_cerrado(err):
    """¿El error dice que Resolve no acepta scripts externos? (v3.3.0)\n\n    Hasta la v3.2 la app miraba «scripts externos» en el texto. Los gemelos\n    de Studio lo siguen diciendo en español (sus registros no se traducen),\n    pero MENSAJE_SCRIPTING_DESACTIVADO ahora sale en el idioma de la\n    interfaz: se aceptan las dos formas.\n    """
    texto = str(err or '')
    return 'scripts externos' in texto or MENSAJE_SCRIPTING_DESACTIVADO.split('\n', 1)[0] in texto
def _resolve_en_ejecucion():
    """(5.3) True si hay un proceso Resolve.exe. dvr.scriptapp() con Resolve CERRADO se queda ~4 s dentro de
    fusionscript.dll SIN soltar el GIL de Python: toda la interfaz se congelaba esos segundos (y otra vez cada
    reintento). Con esta comprobacion barata (ms) ni se llama cuando Resolve no esta abierto."""
    if not sys.platform.startswith('win'):
        return True
    try:
        import ctypes
        from ctypes import wintypes

        class _Proc(ctypes.Structure):
            _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                        ('th32DefaultHeapID', ctypes.c_void_p), ('th32ModuleID', wintypes.DWORD),
                        ('cntThreads', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD),
                        ('pcPriClassBase', wintypes.LONG), ('dwFlags', wintypes.DWORD),
                        ('szExeFile', ctypes.c_wchar * 260)]
        k32 = ctypes.windll.kernel32
        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Proc)]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)
        if not snap or snap == wintypes.HANDLE(-1).value:
            return True
        try:
            e = _Proc()
            e.dwSize = ctypes.sizeof(_Proc)
            ok = k32.Process32FirstW(snap, ctypes.byref(e))
            while ok:
                if e.szExeFile.lower() == 'resolve.exe':
                    return True
                ok = k32.Process32NextW(snap, ctypes.byref(e))
            return False
        finally:
            k32.CloseHandle(snap)
    except Exception:
        return True
def _pids_de_resolve():
    """Los PID de Resolve.exe (Windows); [] si no hay o no se pudo mirar."""
    if not sys.platform.startswith('win'):
        return []
    pids = []
    try:
        import ctypes
        from ctypes import wintypes

        class _Proc(ctypes.Structure):
            _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                        ('th32DefaultHeapID', ctypes.c_void_p), ('th32ModuleID', wintypes.DWORD),
                        ('cntThreads', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD),
                        ('pcPriClassBase', wintypes.LONG), ('dwFlags', wintypes.DWORD),
                        ('szExeFile', ctypes.c_wchar * 260)]
        k32 = ctypes.windll.kernel32
        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Proc)]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)
        if not snap or snap == wintypes.HANDLE(-1).value:
            return []
        try:
            e = _Proc()
            e.dwSize = ctypes.sizeof(_Proc)
            ok = k32.Process32FirstW(snap, ctypes.byref(e))
            while ok:
                if e.szExeFile.lower() == 'resolve.exe':
                    pids.append(int(e.th32ProcessID))
                ok = k32.Process32NextW(snap, ctypes.byref(e))
        finally:
            k32.CloseHandle(snap)
    except Exception:
        return []
    return pids


_COLGADO = {'t': 0.0, 'desde': None, 'hilo': None}


def _muestrear_colgado():
    """Una mirada: ¿alguna ventana visible de Resolve.exe «No responde» ahora mismo? (IsHungAppWindow: el hilo de su ventana lleva >5 s sin atender mensajes)."""
    try:
        pids = set(_pids_de_resolve())
        if not pids:
            return False
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.IsHungAppWindow.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        visto = {'colgado': False}

        def cb(hwnd, _lp):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids and user32.IsWindowVisible(hwnd) and user32.IsHungAppWindow(hwnd):
                visto['colgado'] = True
            return True
        user32.EnumWindows(enum_proc(cb), 0)
        return bool(visto['colgado'])
    except Exception:
        return False


def _tomar_muestra(maxima_edad_s=3.0):
    ahora = time.time()
    if ahora - _COLGADO['t'] < maxima_edad_s:
        return
    colgado = _muestrear_colgado()
    _COLGADO['t'] = ahora
    if colgado:
        _COLGADO['desde'] = _COLGADO['desde'] or ahora
    else:
        _COLGADO['desde'] = None


def _vigia_colgado():
    while True:
        time.sleep(3.0)
        try:
            _tomar_muestra(2.5)
        except Exception:
            pass


def resolve_colgado(umbral_s=0.0):
    """v5.4.8: True si Resolve está abierto pero su ventana «No responde» desde hace al menos `umbral_s` s (0 = ahora mismo). Llamar a fusionscript con Resolve colgado deja TODO
    el proceso congelado (no suelta el GIL), así que ni se intenta; y esperar 75 s a un MCP que no va a contestar tampoco ayuda. Un hilo vigía mira cada 3 s (ms de coste) para
    medir cuánto lleva así. En Mac devuelve False."""
    if not sys.platform.startswith('win'):
        return False
    if _COLGADO['hilo'] is None:
        import threading
        _COLGADO['hilo'] = threading.Thread(target=_vigia_colgado, daemon=True, name='vigia-resolve-colgado')
        _COLGADO['hilo'].start()
    _tomar_muestra()
    desde = _COLGADO['desde']
    return desde is not None and (time.time() - desde) >= float(umbral_s)


def _conexion_viva(resolve):
    """True si el objeto responde de verdad, no solo si existe.\n\n    scriptapp() puede devolver un objeto HUECO: no es None, pero sus metodos\n    valen None. La causa mas comun, y la que le vimos a un cliente con\n    STUDIO en Mac, es que Resolve tiene el scripting externo desactivado:\n\n        Preferencias > Sistema > General > \"External scripting using\"\n\n    Si esta en \"None\", Resolve rechaza la conexion pero la libreria devuelve\n    igual un cascaron. Tiene que estar en \"Local\".\n\n    Sin esta comprobacion, conectar() daba ese cascaron por bueno y el script\n    reventaba con un traceback de Python en la cara del usuario:\n\n        File \"CineCaptions.py\", line 1221, in main\n          project = resolve.GetProjectManager().GetCurrentProject()\n        TypeError: \'NoneType\' object is not callable\n\n    ...despues de haber generado los 124 bloques, o sea con todo el trabajo\n    hecho y tirado. Validando aqui, se detecta antes de empezar y se puede\n    decir que hay que tocar (ver MENSAJE_SCRIPTING_DESACTIVADO).\n\n    Es el mismo criterio que usa obtener_resolve() en los scripts .lua: no se\n    da por buena una conexion hasta que GetProjectManager() responde.\n    """
    try:
        get_pm = getattr(resolve, 'GetProjectManager', None)
        if not callable(get_pm):
            return False
        return get_pm() is not None
    except Exception:
        return False
_CACHE = {'resolve': None, 'intentado': False, 'ultimo_fallo': 0.0, 'hueco': False}
REINTENTO_TRAS_FALLO_S = 5.0
def conectar(refrescar=False, pasivo=False):
    """Devuelve el objeto \'resolve\' o None si no se puede.\n\n    El exito se cachea para siempre; el fallo, solo unos segundos. Antes\n    no se cacheaba el fallo en absoluto, asi que cada vez que la ventana\n    preguntaba en que modo estaba se reintentaba el import de\n    fusionscript, se formateaba un traceback y se reescribia\n    bridge_error.txt. Con el enfriamiento se deja de pagar ese costo sin\n    perder la posibilidad de reconectar si el usuario abre Resolve\n    despues del programa.\n\n    v3.3.3, \'pasivo\': NUNCA intenta conectar; devuelve el handle cacheado\n    (revalidado) o None. MEDIDO en el Windows Free del usuario: cada intento\n    de fusionscript.scriptapp tarda 4,1 s y falla, y las preguntas de\n    estado del arranque (modo actual, edicion, scripts instalados) lo\n    pagaban EN EL HILO DE TK — el «lag al iniciar». El intento real lo\n    hace un hilo al arrancar (la app) y lo que el usuario pide (generar,\n    buscar audio, reinstalar) sigue activo con el enfriamiento de siempre.\n    """
    if pasivo and (not refrescar):
        r = _CACHE['resolve']
        if r is not None and _conexion_viva(r):
            return r
        else:
            return None
    else:
        if not refrescar:
            if _CACHE['resolve'] is not None:
                if _conexion_viva(_CACHE['resolve']):
                    return _CACHE['resolve']
                else:
                    _CACHE['resolve'] = None
            else:
                if _CACHE['intentado']:
                    if time.time() - _CACHE['ultimo_fallo'] < REINTENTO_TRAS_FALLO_S:
                        return
        if not _resolve_en_ejecucion():       # (5.3) Resolve cerrado: no se llama a scriptapp() (congela la interfaz ~4 s)
            _CACHE['resolve'], _CACHE['intentado'], _CACHE['hueco'], _CACHE['ultimo_fallo'] = None, True, False, time.time()
            return None
        if resolve_colgado():                  # v5.4.8: abierto pero «No responde»: no se llama a scriptapp (congelaría la app entera)
            _CACHE['resolve'], _CACHE['intentado'], _CACHE['hueco'], _CACHE['ultimo_fallo'] = None, True, False, time.time()
            return None
        _setear_variables_de_entorno()
        log_dir = Path.home() / 'DaVinciSubtitles'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'bridge_error.txt'
        resolve = None
        hueco = False
        try:
            import DaVinciResolveScript as dvr
            resolve = dvr.scriptapp('Resolve')
            if resolve is None:
                log_file.write_text('DaVinciResolveScript imported, but dvr.scriptapp(\'Resolve\') returned None.', encoding='utf-8')
            else:
                if not _conexion_viva(resolve):
                    log_file.write_text('dvr.scriptapp(\'Resolve\') devolvio un objeto sin metodos (GetProjectManager no responde).\n\n' + MENSAJE_SCRIPTING_DESACTIVADO, encoding='utf-8')
                    resolve = None
                    hueco = True
                else:
                    if log_file.exists():
                        try:
                            log_file.unlink()
                        except Exception:
                            pass
        except Exception as e:
            import traceback
            err_msg = f'Error importing DaVinciResolveScript:\n{type(e).__name__}: {e}\n\n{traceback.format_exc()}'
            log_file.write_text(err_msg, encoding='utf-8')
            resolve = None
        _CACHE['resolve'] = resolve
        _CACHE['intentado'] = True
        _CACHE['hueco'] = hueco
        if resolve is None:
            _CACHE['ultimo_fallo'] = time.time()
        return resolve
def disponible(pasivo=False):
    """True si podemos ejecutar scripts en Resolve directamente."""
    return conectar(pasivo=pasivo) is not None
def scripting_desactivado(pasivo=False):
    """True si Resolve contesto, pero con un objeto sin metodos.\n\n    Es un caso distinto de \"no hay conexion\": Resolve ESTA ahi. Lo que falta\n    es el permiso de scripting externo. Se pregunta despues de conectar()\n    para elegir que mensaje mostrar.\n    """
    conectar(pasivo=pasivo)
    return bool(_CACHE.get('hueco'))
def ya_se_intento():
    """Si algun intento de conexion (activo) ya corrio en este proceso:\n    el arranque espera al hilo que lo hace antes de decir el modo."""
    return bool(_CACHE.get('intentado')) or _CACHE.get('resolve') is not None
def ejecutar_script(ruta_script, resolve=None):
    """Corre el script como si estuviera adentro de Resolve."""
    ruta = Path(ruta_script)
    if not ruta.exists():
        return (False, tr('No encuentro el script en {ruta}', ruta=ruta))
    resolve = resolve or conectar()
    if resolve is None:
        return (False, tr('No hay conexión directa con la API de Resolve.'))
    spec = importlib.util.spec_from_file_location(
        '_cinecaptions_' + ruta.stem.replace(' ', '_').replace('-', '_'), ruta)
    modulo = importlib.util.module_from_spec(spec)
    modulo.__dict__['resolve'] = resolve
    try:
        spec.loader.exec_module(modulo)
        if hasattr(modulo, 'main'):
            modulo.main()
        log_file = Path.home() / 'DaVinciSubtitles' / 'bridge_error.txt'
        if log_file.exists():
            try:
                log_file.unlink()
            except Exception:
                pass
        return (True, '')
    except SystemExit as e:
        err_msg = (str(e) if str(e).isdigit() is False
                   else tr('El script terminó con error'))
        return (False, err_msg)
    except Exception as e:
        import traceback
        err_msg = f'{type(e).__name__}: {e}\n\n{traceback.format_exc()}'
        return (False, err_msg)
def _sanear(nombre):
    return '_cinecaptions_' + str(nombre).replace(' ', '_').replace('-', '_')
CARPETA_COMPARTIDA = Path.home() / 'DaVinciSubtitles'
CARPETA_TRABAJOS = CARPETA_COMPARTIDA / 'jobs'
ARCHIVO_LATIDO = CARPETA_COMPARTIDA / 'puente.heartbeat'
ARCHIVO_ARRANQUE = CARPETA_COMPARTIDA / 'puente.arranque.txt'
ARCHIVO_RELEVO = CARPETA_COMPARTIDA / 'puente.relevo'
RELEVO_MAXIMO_S = 3
_RE_LATIDO_NUESTRO = re.compile('^\\d+(\\||$)')
JOB_PENDIENTE = CARPETA_TRABAJOS / 'pendiente.json'
JOB_TOMADO = CARPETA_TRABAJOS / 'pendiente.tomado'
LATIDO_MAXIMO_S = 12
SIN_LATIDO_MAXIMO = 3
SCRIPTS = {'detectar': 'CineCaptions - Detectar Video.py', 'subtitulos': 'CineCaptions.py', 'sfx': 'CineCaptions - Insertar SFX.py', 'sfx_marcadores': 'CineCaptions - SFX Marcadores.py', 'sfx_reemplazar': 'CineCaptions - SFX Reemplazar.py', 'importar_estilos': 'CineCaptions - Importar Estilos.py', 'efectos': 'CineCaptions - Efectos.py', 'armar_video': 'CineCaptions - Armar Video.py', 'pausas': 'CineCaptions - Pausas.py'}      # (efectos: solo por el Puente de Free, que corre CineCaptions_Efectos.lua; en Studio van por el MCP)
def carpeta_de_scripts():
    """Donde viven los .py que ejecuta Studio por la API.\n\n    Van DENTRO del programa (BASE_RECURSOS/resolve_scripts), no en la\n    carpeta del menu de Resolve: ahi solo se instalan los .lua, para Free.\n\n    Existe para que nadie tenga que calcularla a mano. El SFX Lab pasaba la\n    carpeta del MENU y armaba la ruta con el nombre .py viejo, asi que en\n    Studio fallaba siempre con \'No encuentro el script\'.\n    """
    import instalador_scripts
    return instalador_scripts.BASE_RECURSOS / 'resolve_scripts'
def script_de(accion, carpeta_scripts=None):
    """Ruta al script que implementa una accion."""
    nombre = SCRIPTS.get(accion)
    if not nombre:
        return
    else:
        base = Path(carpeta_scripts) if carpeta_scripts else carpeta_de_scripts()
        return base / nombre
ARCHIVO_RESULTADO = CARPETA_COMPARTIDA / 'ultimo_resultado.json'
ARCHIVO_RESULTADO_TXT = CARPETA_COMPARTIDA / 'ultimo_resultado.txt'
ARCHIVO_VIDEO_DETECTADO = CARPETA_COMPARTIDA / 'video_detectado.json'
MARCA_REPORTE = 'CINECAPTIONS_REPORTE|'
_COLA_REGISTRO = 524288
def ruta_registro_resolve():
    if sys.platform.startswith('win'):
        rel = Path('Blackmagic Design') / 'DaVinci Resolve' / 'Support' / 'logs' / 'ResolveDebug.txt'
        por_home = Path.home() / 'AppData' / 'Roaming' / rel
        appdata = os.environ.get('APPDATA')
        if not por_home.exists() and appdata and (Path.home() / 'AppData').exists():
            return Path(appdata) / rel
        else:
            return por_home
    else:
        if sys.platform == 'darwin':
            return Path.home() / 'Library' / 'Application Support' / 'Blackmagic Design' / 'DaVinci Resolve' / 'logs' / 'ResolveDebug.txt'
        else:
            return Path.home() / '.local' / 'share' / 'DaVinciResolve' / 'logs' / 'ResolveDebug.txt'
RUTA_REGISTRO_RESOLVE = ruta_registro_resolve()
def _parsear_reporte(cuerpo):
    try:
        rep = json.loads(cuerpo)
        return rep if isinstance(rep, dict) else None
    except Exception:
        pass
    import re as _re
    m = _re.search('\"script\":\\s*\"([^\"]*)\".*?\"version\":\\s*\"([^\"]*)\".*?\"ok\":\\s*(true|false).*?\"mensaje\":\\s*\"((?:[^\"\\\\]|\\\\.)*)\".*?\"cuando\":\\s*(\\d+)', cuerpo)
    if not m:
        return
    else:
        return {'script': m.group(1), 'version': m.group(2), 'ok': m.group(3) == 'true', 'mensaje': m.group(4).replace('\\\"', '\"').replace('\\n', '\n'), 'cuando': int(m.group(5)), 'recortado': True}
def reportes_del_registro():
    """Los reportes que los scripts dejaron en el registro de Resolve, del\n    mas viejo al mas nuevo. Solo la sesion actual de Resolve: el registro\n    rota a LogArchive/ en cada arranque. Nunca lanza."""
    try:
        ruta = RUTA_REGISTRO_RESOLVE
        tam = ruta.stat().st_size
        with open(ruta, 'rb') as f:
            if tam > _COLA_REGISTRO:
                f.seek(tam - _COLA_REGISTRO)
            datos = f.read().decode('utf-8', errors='replace')
    except Exception:
        return []
    salida = []
    for linea in datos.splitlines():
        pos = linea.find(MARCA_REPORTE)
        if pos < 0:
            continue
        else:
            rep = _parsear_reporte(linea[pos + len(MARCA_REPORTE):].strip())
            if rep is None:
                continue
            else:
                salida.append(rep)
    return salida
def ultimo_reporte(desde=None):
    """El ultimo reporte del registro, o None. Con \'desde\', solo si es\n    posterior (mismo contrato que ultimo_resultado)."""
    reps = reportes_del_registro()
    if not reps:
        return
    else:
        rep = reps[(-1)]
        if desde is not None and (rep.get('cuando') or 0) < desde - 2:
            return
        else:
            return rep
def _reporte_del_puente():
    """El ultimo reporte que el propio Puente dejo en el registro de Resolve\n    (modo señales: arranque, cierre, sin canal...), o None."""
    for rep in reversed(reportes_del_registro()):
        if rep.get('script') == 'CineCaptions_Puente':
            return rep
    return
def video_detectado():
    """Lo que dejo CineCaptions_DetectarVideo: video_detectado.json (con io) o el\n    ultimo reporte del registro que traiga \'video\' (Free 21.1). Gana el mas\n    nuevo por \'detectado_en\'. None si no hay nada legible."""
    datos = None
    try:
        datos = json.loads(ARCHIVO_VIDEO_DETECTADO.read_text(encoding='utf-8'))
        if not isinstance(datos, dict):
            datos = None
    except Exception:
        datos = None
    for rep in reversed(reportes_del_registro()):
        video = rep.get('video')
        if not isinstance(video, dict):
            continue
        if datos is None or ((video.get('detectado_en') or 0)
                             > (datos.get('detectado_en') or 0)):
            return video
        break
    return datos
def ultimo_resultado(desde=None):
    """Lo que reporto el ultimo script que corrio dentro de Resolve.\n\n    Devuelve el dict {script, version, ok, mensaje, cuando} o None.\n\n    Con \'desde\' (timestamp) solo se devuelve si es POSTERIOR: sirve para\n    saber si el script llego a correr tras pedirselo, en vez de leer el\n    resultado de la vez anterior y confundirlo con este.\n    """
    datos = None
    try:
        datos = json.loads(ARCHIVO_RESULTADO.read_text(encoding='utf-8'))
    except Exception:
        datos = None
    if not isinstance(datos, dict):
        datos = None
    if datos is not None and desde is not None and ((datos.get('cuando') or 0) < desde - 2):
                datos = None
    rep = ultimo_reporte(desde)
    if rep is not None and (datos is None or (rep.get('cuando') or 0) >= (datos.get('cuando') or 0)):
        return rep
    else:
        return datos
_SIN_RESULTADO = object()
def desajuste_de_version(esperada, resultado=_SIN_RESULTADO):
    """La version de los scripts que corrieron, si NO es la esperada.\n\n    Devuelve esa version (str) o None si coinciden o no se puede saber.\n\n    Existe porque el sintoma es mudo y carisimo: con una copia vieja del\n    programa instalada al lado, sus scripts pisan a los nuevos en el menu de\n    Resolve (el instalador compara contenido, no versiones) y el usuario\n    prueba durante dias arreglos que en su maquina no existen.\n    """
    datos = ultimo_resultado() if resultado is _SIN_RESULTADO else resultado
    if not isinstance(datos, dict):
        return
    else:
        version = str(datos.get('version') or '').strip()
        if not version:
            return
        else:
            return None if version.startswith(str(esperada)) else version
def texto_ultimo_resultado(desde=None):
    """Salida completa del ultimo script, para mostrarla o mandarla a soporte.\n\n    Con \'desde\' (timestamp) solo devuelve el texto si el archivo es\n    POSTERIOR: sin el filtro, un registro de dias atras se hacia pasar por\n    el de la corrida actual (el messagebox del Mac con uno del 25/08).\n    """
    try:
        mtime = ARCHIVO_RESULTADO_TXT.stat().st_mtime
    except OSError:
        mtime = None
    rep = ultimo_reporte(desde)
    if rep is not None and (mtime is None
                            or (rep.get('cuando') or 0) >= mtime - 2):
        cabecera = ('(el registro de Resolve recorto la linea del reporte; esto es lo que cupo)\n'
                    if rep.get('recortado') else '')
        return cabecera + str(rep.get('texto') or rep.get('mensaje') or '')
    try:
        if desde is not None and mtime is not None and mtime < desde - 2:
            return ''
        return ARCHIVO_RESULTADO_TXT.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ''
def limpiar_resultado_viejo():
    """ARCHIVA ultimo_resultado.* antes de una corrida nueva.\n\n    Se renombra a *.anterior en vez de borrarse: el rancio deja de poder\n    hacerse pasar por actual, pero el forense queda en disco para soporte\n    (borrarlo dejaba el diagnostico de una corrida muerta-temprano sin la\n    linea \'bmd:\' ni el ultimo motivo — justo lo que cierra casos).\n    """
    for ruta in (ARCHIVO_RESULTADO, ARCHIVO_RESULTADO_TXT):
        try:
            destino = ruta.with_suffix(ruta.suffix + '.anterior')
            try:
                destino.unlink()
            except OSError:
                pass
            ruta.rename(destino)
        except OSError:
            pass
VERSION_PUENTE_ESPERADA = '1.0.38'
VERSION_PUENTE_MINIMA = '1.0.21'
# Desde que version del Puente existe cada accion: un residente mas viejo (el que quedo corriendo en Resolve tras actualizar el programa) responde «Accion desconocida».
VERSION_DE_ACCION = {'importar_estilos': (1, 0, 25), 'sfx_marcadores': (1, 0, 31), 'sfx_reemplazar': (1, 0, 32), 'efectos': (1, 0, 38), 'armar_video': (1, 0, 38), 'pausas': (1, 0, 38)}
def _tupla_version(texto):
    """\"1.0.21\" -> (1, 0, 21). Lo raro cuenta como version 0 (muy vieja)."""
    try:
        return tuple((int(p) for p in str(texto).strip().split('.')))
    except (TypeError, ValueError):
        return (0,)
def puente_incompatible():
    """True solo si el Puente corriendo NO entiende el protocolo actual.\n\n    Un Puente sin version en el latido (anterior a la 1.0.12) tambien es\n    incompatible: es anterior a la ruptura de la 1.0.21.\n    """
    if not puente_activo():
        return False
    else:
        version = version_del_puente()
        if version is None:
            return True
        else:
            return _tupla_version(version) < _tupla_version(VERSION_PUENTE_MINIMA)
def version_del_puente():
    """Version del Puente que esta corriendo, o None si no se sabe.\n\n    El latido es \"<hora>|<version>\". Los Puentes anteriores a la 1.0.12\n    escribian solo \"<hora>\": ahi devolvemos None (no se sabe), y quien\n    pregunte decide que hacer.\n    """
    try:
        contenido = ARCHIVO_LATIDO.read_text(encoding='utf-8', errors='replace').strip()
    except OSError:
        return None
    if not _RE_LATIDO_NUESTRO.match(contenido):
        rep = _reporte_del_puente()
        if rep is None:
            return
        else:
            return str(rep.get('puente') or '').strip() or None
    else:
        if '|' not in contenido:
            return
        else:
            version = contenido.split('|', 1)[1].strip()
            return version or None
def puente_no_conoce(accion):
    """True si hay un Puente latiendo y es tan viejo que no sabe hacer esa accion."""
    minima = VERSION_DE_ACCION.get(accion)
    if minima is None or not puente_activo():
        return False
    version = version_del_puente()
    return version is None or _tupla_version(version) < minima
def puente_desactualizado():
    """True si el Puente corriendo es de una version anterior.\n\n    Solo se afirma cuando hay un puente vivo. Un Puente viejo que no\n    reporta version (None) tambien cuenta: si esta latiendo y no dice\n    quien es, es anterior a la 1.0.12.\n    """
    if not puente_activo():
        return False
    else:
        return version_del_puente() != VERSION_PUENTE_ESPERADA
MENSAJE_PUENTE_VIEJO = tr('El Puente que está corriendo dentro de Resolve es de una versión anterior del programa.\n\nActualizar el programa deja el archivo nuevo en su sitio, pero el Puente que ya estaba corriendo sigue con el código viejo hasta que lo vuelvas a lanzar.\n\n1. Cierra la ventana de consola del Puente en Resolve.\n2. Vuelve a correr:\n       Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Puente\n\n(Si no aparece en el menú, cierra Resolve por completo y vuelve a abrirlo primero.)')
def _cuanto_hace(seg):
    """Una edad en segundos, en la unidad que se lee de un vistazo."""
    if seg < 90:
        return f'{seg:.0f} s'
    else:
        if seg < 5400:
            return f'{seg / 60:.0f} min'
        else:
            if seg < 172800:
                return f'{seg / 3600:.0f} horas'
            else:
                return f'{seg / 86400:.0f} dias'
DESENLACES_PUENTE = {'arrancando': 'SE QUEDO A MEDIAS (murio nada mas lanzarlo)', 'ok': 'arranco bien', 'sin_resolve': 'MURIO: Resolve no le respondio (hay que relanzarlo)', 'relevo_fallido': 'MURIO: otro Puente no solto el turno', 'sin_latido': 'ARRANCO PERO NO PUEDE ESCRIBIR SU LATIDO', 'sin_canal': 'MURIO: este Resolve no le deja escribir ni señales (usa CineCaptions_DetectarVideo y CineCaptions_Subtitulos a mano)', 'relevado': 'se retiro: otro Puente mas nuevo tomo el relevo', 'cerrado': 'se cerro bien', 'murio': 'MURIO a mitad del arranque (el error esta en «Que respondio Resolve»)'}
def arranque_del_puente():
    """(cuando, version, desenlace) del ultimo lanzamiento, o None.\n\n    None significa que el Puente no se ha lanzado NUNCA en este equipo -o al\n    menos no desde la v3.1.3-, que es justo lo que no se podia distinguir de\n    \"se lanzo y murio\" antes de que existiera este archivo.\n    """
    try:
        crudo = ARCHIVO_ARRANQUE.read_text(encoding='utf-8', errors='replace').strip()
    except OSError:
        crudo = ''
    trozos = crudo.split('|')
    if len(trozos) >= 3:
        try:
            return (float(trozos[0].strip()), trozos[1].strip(), trozos[2].strip())
        except ValueError:
            pass
        else:
            pass
    rep = _reporte_del_puente()
    if rep is not None and rep.get('arranque'):
        try:
            return (float(rep.get('cuando') or 0), str(rep.get('puente') or '?'), str(rep['arranque']))
        except (TypeError, ValueError):
            return None
    else:
        return None
def edad_del_latido():
    """(edad_por_fecha, edad_por_contenido) en segundos, o None cada una.\n\n    Son DOS relojes distintos y por eso se devuelven por separado:\n\n      - la fecha del archivo la pone el sistema de archivos;\n      - el sello de dentro lo escribe el Puente con os.time() de Lua.\n\n    Normalmente coinciden. Pero con el reloj del equipo desajustado, con la\n    carpeta en una unidad de red, o con zonas horarias de por medio, pueden\n    ir separados varias horas — y ahi la app daba por muerto un Puente que\n    estaba perfectamente vivo. Ver puente_activo.\n    """
    ahora = time.time()
    por_fecha = None
    try:
        por_fecha = ahora - ARCHIVO_LATIDO.stat().st_mtime
    except OSError:
        return (None, None)
    por_contenido = None
    try:
        contenido = ARCHIVO_LATIDO.read_text(encoding='utf-8').strip()
        sello = contenido.split('|', 1)[0].strip()
        if sello:
            por_contenido = ahora - float(sello)
    except (OSError, ValueError):
        pass
    return (por_fecha, por_contenido)
JOB_TOMADO_MAXIMO_S = 600
def _puente_trabajando():
    """True si hay un trabajo reclamado hace poco: el Puente esta VIVO pero\n    bloqueado dentro de dofile y no puede escribir su latido.\n\n    _encolar ya usaba exactamente este criterio para no cancelar trabajos en\n    curso, pero la eleccion de rama de ejecutar() no lo miraba: un segundo\n    pedido durante un dofile largo (el prep de un pack importa un .drt\n    entero) caia a la rama 3 y mostraba el mensaje de preferencias — un\n    diagnostico falso, con el Puente trabajando delante del usuario.\n    """
    try:
        if not JOB_TOMADO.exists():
            return False
        return time.time() - JOB_TOMADO.stat().st_mtime <= JOB_TOMADO_MAXIMO_S
    except Exception:
        return False
def puente_activo():
    """True si el script Puente esta corriendo dentro de Resolve.\n\n    Vale CUALQUIERA de las dos señales. Hasta la v1.0.24 solo se miraba la\n    fecha del archivo, y cuando esa fecha no cuadraba con el reloj del\n    sistema -reloj desajustado, carpeta en red, zonas horarias- la app\n    anunciaba \"el puente dejo de responder\" con el Puente corriendo delante.\n    Ese era el fallo de conexion que reportaban algunos usuarios de Free.\n\n    Se sigue mirando el mtime primero porque es el que nunca se lee a medias:\n    el Puente reescribe el archivo seguido y leer el contenido justo durante\n    una escritura devuelve texto vacio.\n    """
    _podar_relevo()
    por_fecha, por_contenido = edad_del_latido()
    for edad in [por_fecha, por_contenido]:
        if edad is None:
            continue
        else:
            if (-5) <= edad <= LATIDO_MAXIMO_S:
                    return True
    return False
def _podar_relevo():
    """Borra puente.relevo pasados RELEVO_MAXIMO_S (modo señales, v3.1.7).\n\n    El Puente que lo escribe no puede borrarlo, y su bucle lo toma por suyo\n    mientras exista: si nadie lo quita, el SIGUIENTE Puente que lo escriba no\n    se distingue y quedan dos vivos. Va aqui porque puente_activo() es lo que\n    la app consulta sin parar. Nunca lanza."""
    try:
        if time.time() - ARCHIVO_RELEVO.stat().st_mtime > RELEVO_MAXIMO_S:
            ARCHIVO_RELEVO.unlink()
    except OSError:
        pass
def _latido_es_nuestro():
    """False cuando el latido es un archivo-señal escrito por Resolve (modo\n    señales) y no el \"<hora>|<version>\" del backend con io."""
    try:
        contenido = ARCHIVO_LATIDO.read_text(encoding='utf-8', errors='replace').strip()
    except OSError:
        return False
    return bool(_RE_LATIDO_NUESTRO.match(contenido))
def diagnostico():
    """Todo el estado del Puente en un texto para copiar y pegar.\n\n    Existe porque los fallos de conexion que quedan no se pueden reproducir\n    en desarrollo: llegan como \"no me conecta\" y sin nada mas. Con esto, un\n    solo pegado tiene que bastar para saber que pasa — que es lo que cerro el\n    parpadeo de la v1.0.24.\n\n    Nunca lanza: si algo no se puede leer, lo dice y sigue.\n    """
    def linea(etiqueta, valor):
        return f'  {etiqueta:24} {valor}'
    partes = ['Conexión MCP (Resolve 21.1+)', '==============================================']
    try:
        import resolve_mcp
        partes += ['  ' + l for l in resolve_mcp.diagnostico()]
    except Exception as e:
        partes.append(f'  no se pudo consultar: {e}')
    partes += ['', 'Puente CineCaptions - diagnostico', '==============================================']
    por_fecha, por_contenido = edad_del_latido()
    if por_fecha is None:
        partes.append(linea('latido', 'NO EXISTE el archivo'))
        partes.append(linea('', f'({ARCHIVO_LATIDO})'))
    else:
        partes.append(linea('latido (fecha archivo)', f'hace {por_fecha:.1f} s'))
        partes.append(linea('latido (sello interno)', f'hace {por_contenido:.1f} s' if por_contenido is not None else 'ilegible (se leyo a medio escribir?)'))
        if por_contenido is not None and abs(por_fecha - por_contenido) > 60:
                partes.append(linea('', 'OJO: los dos relojes no coinciden. Reloj del equipo o carpeta en red.'))
    partes.append(linea('se da por vivo', 'SI' if puente_activo() else 'NO'))
    partes.append(linea('tope de latido', f'{LATIDO_MAXIMO_S} s'))
    if por_fecha is not None and (not _latido_es_nuestro()):
            partes.append(linea('modo del Puente', 'SEÑALES (menu sin io, Free 21.1): el latido es un archivo que escribe Resolve; los reportes llegan por su registro'))
    version = version_del_puente()
    texto_version = version or 'no la dice (anterior a la 1.0.12)'
    if version and (not puente_activo()) and (por_fecha is not None):
                texto_version += f'   <- FOSIL: de un Puente que ya no corre, hace {_cuanto_hace(por_fecha)}'
    partes.append(linea('version del Puente', texto_version))
    partes.append(linea('version esperada', VERSION_PUENTE_ESPERADA + ' (numeracion propia del Puente, no la del programa)'))
    if puente_activo() and version != VERSION_PUENTE_ESPERADA:
            partes.append(linea('', 'DESACTUALIZADO: hay que relanzarlo'))
    arranque = arranque_del_puente()
    if arranque is None:
        partes.append(linea('ultimo arranque', 'NINGUNO: el Puente no se ha lanzado nunca en este equipo'))
    else:
        cuando, version_arr, desenlace = arranque
        partes.append(linea('ultimo arranque', f'hace {_cuanto_hace(time.time() - cuando)}  |  Puente {version_arr}  |  ' + DESENLACES_PUENTE.get(desenlace, desenlace)))
    partes.append(linea('carpeta de trabajos', str(CARPETA_TRABAJOS)))
    partes.append(linea('  pendiente.json', 'SI' if JOB_PENDIENTE.exists() else 'no'))
    partes.append(linea('  pendiente.tomado', 'SI (hay trabajo en curso)' if JOB_TOMADO.exists() else 'no'))
    try:
        sobras = [f.name for f in CARPETA_TRABAJOS.glob('*.done.json')]
        partes.append(linea('  respuestas sin recoger', ', '.join(sobras) if sobras else 'ninguna'))
    except Exception as e:
        partes.append(linea('  respuestas sin recoger', f'no pude mirar: {e}'))
    partes.append(linea('modo actual', modo_actual()))
    try:
        import instalador_scripts as ins
        partes.append(linea('edicion de Resolve', ins.edicion_de_resolve()))
        partes.append(linea('Resolve abierto', 'si' if ins.resolve_esta_corriendo() else 'no'))
        partes.append(linea('scripts instalados', 'si' if ins.scripts_instalados() else 'NO'))
    except Exception as e:
        partes.append(linea('instalador', f'no pude consultar: {e}'))
    if scripting_desactivado():
        partes.append(linea('scripting externo', 'DESACTIVADO en preferencias de Resolve'))
    ultimo = CARPETA_COMPARTIDA / 'ultimo_resultado.txt'
    partes.append('')
    partes.append('Ultimo resultado dentro de Resolve:')
    reporte = ultimo_reporte()
    try:
        mtime_txt = ultimo.stat().st_mtime
    except OSError:
        mtime_txt = None
    if reporte is not None and (mtime_txt is None or (reporte.get('cuando') or 0) >= mtime_txt):
        edad_s = time.time() - (reporte.get('cuando') or 0)
        partes.append('  (llego por el registro de Resolve: menu sin io, Free 21.1)')
        if edad_s > 3600:
            partes.append(f'  (OJO: es de hace {_cuanto_hace(edad_s)})')
        if reporte.get('recortado'):
            partes.append('  (el registro recorto la linea: solo la cabecera)')
        texto_rep = str(reporte.get('texto') or reporte.get('mensaje') or '')
        lineas_rep = texto_rep.strip().splitlines()
        for l in lineas_rep:
            if l.strip().startswith('bmd:'):
                partes.append('  ' + l.strip())
        partes.extend(('  ' + l for l in lineas_rep[(-12):]))
        return '\n'.join(partes)
    try:
        if False:
            pass
        try:
            edad_s = time.time() - ultimo.stat().st_mtime
            if edad_s > 3600:
                if edad_s > 86400:
                    cuanto = f'{edad_s / 86400:.0f} dias'
                else:
                    cuanto = f'{edad_s / 3600:.0f} horas'
                partes.append(f'  (OJO: es de hace {cuanto} — el script no llego a correr esta vez)')
        except OSError:
            pass
        texto = ultimo.read_text(encoding='utf-8', errors='replace')
        capacidades = [l for l in texto.splitlines() if l.strip().startswith('bmd:')]
        for l in capacidades:
            partes.append('  ' + l.strip())
        cola = texto.strip().splitlines()[(-12):]
        partes.extend(('  ' + l for l in cola))
    except OSError:
        anterior = CARPETA_COMPARTIDA / 'ultimo_resultado.txt.anterior'
        try:
            texto = anterior.read_text(encoding='utf-8', errors='replace')
        except OSError:
            partes.append('  (no hay: ningun script ha corrido todavia)')
        else:
            try:
                edad = ' de hace ' + _cuanto_hace(time.time() - anterior.stat().st_mtime)
            except OSError:
                edad = ''
            else:
                pass
            partes.append('  (el de ESTA vez no existe: el script no llego a correr.')
            partes.append(f'   Lo ultimo que si corrio,{edad}:)')
            for l in texto.strip().splitlines()[(-12):]:
                partes.append('  ' + l)
    return '\n'.join(partes)
def modo_actual(pasivo=False):
    """Como se van a ejecutar los scripts ahora mismo.\n\n    Devuelve \'studio\', \'puente\' o \'manual\'. Sirve para mostrarselo al\n    usuario y para que el soporte sepa que camino se esta usando. Con\n    \'pasivo\' no intenta conectar (v3.3.3: las preguntas de estado no pagan\n    los 4 s del scriptapp de Free).\n    """
    if _mcp_conectado(pasivo):
        return 'mcp'
    if disponible(pasivo=pasivo):
        return 'studio'
    else:
        if puente_activo():
            return 'puente'
        else:
            return 'manual'
def _mcp_conectado(pasivo=False):
    """v5.1: el servidor MCP oficial de Resolve (resolve_mcp). En modo pasivo
    solo mira lo ultimo que se supo (no arranca nada ni espera a Resolve)."""
    try:
        import resolve_mcp
        if pasivo:
            return bool(resolve_mcp.estado_cacheado().get('conectado') or resolve_mcp.conectado_recientemente())
        return resolve_mcp.disponible()
    except Exception:
        return False
def descripcion_modo(modo=None):
    modo = modo or modo_actual()
    return {'mcp': 'Resolve 21 (MCP oficial)', 'studio': 'Studio (API directa)', 'puente': 'Free (puente activo)', 'manual': 'Free (puente no iniciado)'}.get(modo, modo)
def _barrer_respuestas_huerfanas(max_edad_s=3600):
    """Tira los .done.json que nadie llego a recoger.\n\n    Normalmente los borra quien los lee, pero si el programa se cierra a mitad\n    de una espera quedan ahi para siempre. Listar la carpeta aqui no cuesta\n    nada porque esto es Python: en el puente, que es Lua, listar significaba\n    abrir una consola (ver _encolar).\n    """
    try:
        limite = time.time() - max_edad_s
        for patron in ('*.done.json', '*.hecho.*'):
            for f in CARPETA_TRABAJOS.glob(patron):
                try:
                    if f.stat().st_mtime < limite:
                        f.unlink()
                except Exception:
                    pass
        sidecar = JOB_PENDIENTE.with_name(JOB_PENDIENTE.name + '.lua')
        if (sidecar.exists() and not JOB_PENDIENTE.exists()
                and sidecar.stat().st_mtime < time.time() - 60):
            sidecar.unlink()
    except Exception:
        pass
    _podar_relevo()
def _encolar(accion, datos=None, timeout=90, on_progreso=None):
    """Deja un trabajo para el puente y espera su respuesta.\n\n    Devuelve (ok, mensaje). Si el puente no contesta antes del timeout,\n    devuelve False con un mensaje explicando que paso.\n    """
    CARPETA_TRABAJOS.mkdir(parents=True, exist_ok=True)
    _barrer_respuestas_huerfanas()
    job_id = f'{accion}-{int(time.time() * 1000)}'
    respuesta = CARPETA_TRABAJOS / f'{job_id}.done.json'
    sidecar = JOB_PENDIENTE.with_name(JOB_PENDIENTE.name + '.lua')
    try:
        sidecar_lua.escribir_par(JOB_PENDIENTE, {
            'id': job_id,
            'accion': accion,
            'datos': datos or {},
            'creado_en': time.time(),
        })
    except Exception as e:
        return (False, tr('No pude dejarle el trabajo al puente: {e}', e=e))

    def limpiar(*rutas):
        for f in rutas:
            try:
                f.unlink()
            except Exception:
                pass

    def hecho_por_senal():
        """La respuesta del modo señales: jobs/<id>.hecho.<ok|err>.<resumen>.\n\n        El Puente sin io no puede escribir un .done.json: el veredicto y un\n        resumen corto van en el NOMBRE de una señal (el detalle ya viajo por\n        el registro de Resolve y lo recoge ultimo_resultado)."""
        for f in CARPETA_TRABAJOS.glob(f'{job_id}.hecho.*'):
            resto = f.name[len(job_id) + len('.hecho.'):]
            veredicto, _, resumen = resto.partition('.')
            limpiar(f)
            return (veredicto == 'ok', resumen.strip())

    inicio = time.time()
    sin_latido = 0
    pendiente_retirado = False
    while time.time() - inicio < timeout:
        if respuesta.exists():
            try:
                r = json.loads(respuesta.read_text(encoding='utf-8'))
            except Exception:
                time.sleep(0.2)
                continue
            limpiar(respuesta, sidecar)
            return (bool(r.get('ok')), r.get('mensaje') or '')
        senal = hecho_por_senal()
        if senal is not None:
            limpiar(JOB_PENDIENTE, sidecar, JOB_TOMADO)
            return senal
        if not pendiente_retirado:
            try:
                if (JOB_PENDIENTE.exists() and JOB_TOMADO.exists()
                        and JOB_TOMADO.stat().st_mtime >= inicio - 2):
                    limpiar(JOB_PENDIENTE, sidecar)
                    pendiente_retirado = True
            except OSError:
                pass
        if not puente_activo() and not JOB_TOMADO.exists():
            sin_latido += 1
            if sin_latido >= SIN_LATIDO_MAXIMO:
                limpiar(JOB_PENDIENTE, sidecar, JOB_TOMADO)
                return (False, tr('El puente dejó de responder. Vuelve a correrlo en Resolve: Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Puente.'))
        else:
            sin_latido = 0
        if on_progreso:
            try:
                on_progreso(time.time() - inicio)
            except Exception:
                pass
        time.sleep(0.25)
    limpiar(JOB_PENDIENTE, sidecar, JOB_TOMADO)
    return (False, tr('El puente no respondió en {timeout} segundos. Revisa la ventana de la consola de scripts en Resolve.',
                      timeout=timeout))
MENSAJE_SIN_PUENTE = tr('Para colocar los subtítulos, en Resolve pulsa una vez:\n\n    Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Subtitulos\n\n(En inglés el menú es Workspace > Scripts.)\nAparecen en tu línea de tiempo al pulsarlo, y este programa se entera solo cuando el script termine.\n\nPara que se coloquen SOLOS cada vez, deja corriendo CineCaptions_Puente (en esa misma carpeta; desde la v3.1.7 también en DaVinci Resolve 21.1).\n\n(Los archivos están en: {carpeta})\n\n(Si no ves los scripts en el menú, cierra Resolve y vuelve a abrirlo: arma el menú de Scripts al arrancar.)', carpeta=CARPETA_COMPARTIDA)
PASOS_SCRIPTING = tr('Tienes DOS formas de arreglarlo (con una basta):\n\nA) Abre DaVinci Resolve > Preferencias > Sistema > General, pon «External scripting using» en «Local», y reinicia Resolve.\n\nB) Sin tocar preferencias: en Resolve, ve a Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) y lanza «CineCaptions_Puente». Déjalo corriendo y vuelve a generar.')
def paso_manual_pendiente(texto_resultado):
    """El paso que el ultimo registro dejo pendiente, o None.\n\n    Devuelve un dict {\"tipo\": \"arrastrar\"|\"sin_textplus\", \"timeline\": ...,\n    \"bin\": ...} para que la app lo muestre EN LA CARA. Existia solo\n    enterrado en el registro, y el usuario generaba una y otra vez sin ver\n    que le faltaba un arrastre de una sola vez.\n    """
    if not texto_resultado:
        return
    else:
        import re as _re
        m = _re.search('Dej[eé] el timeline «([^»]+)»', texto_resultado)
        b = _re.search('al bin «([^»]+)»', texto_resultado)
        if m and b:
            sin_lienzo = 'no encontre ningun Text+' in texto_resultado or 'me sirva de lienzo' in texto_resultado
            tipo = 'elegir' if sin_lienzo else 'arrastrar'
            return {'tipo': tipo, 'timeline': m.group(1), 'bin': b.group(1)}
        else:
            if 'no encontre ningun Text+' in texto_resultado:
                return {'tipo': 'sin_textplus', 'timeline': None, 'bin': None}
def mensaje_para_el_usuario():
    """Que decirle al usuario cuando no se puede ejecutar solo.\n\n    Casi siempre la respuesta es la misma y es UNA: lanzar CineCaptions_Puente. La\n    unica excepcion real es el scripting externo apagado, que manda a otro\n    sitio distinto.\n    """
    if scripting_desactivado():
        return MENSAJE_SCRIPTING_DESACTIVADO + '\n\n' + PASOS_SCRIPTING
    else:
        return MENSAJE_SIN_PUENTE
def _con_motivo_real(ok, mensaje, empezo):
    """Manda lo que reporto el script, no lo que creemos desde afuera.\n\n    Dos cosas:\n\n    1. Si fallo, el script sabe exactamente por que (\'no hay timeline\n       activo\', \'falta un Text+ en el Media Pool\'...), pero eso terminaba\n       solo en la consola de Resolve y a la app llegaba un mensaje pelado.\n       Gana el del script.\n\n    2. Si vino \'ok\', hay que comprobarlo IGUAL. Los scripts atrapaban su\n       propio error sin relanzarlo, asi que el pcall(dofile) del Puente los\n       daba por buenos y la app anunciaba \"ya quedaron puestos en tu\n       timeline\" con el timeline vacio. Ahora los scripts relanzan, pero\n       esta comprobacion queda como segunda capa: si el script dejo\n       ok:false, fallo, diga lo que diga el camino de ejecucion.\n    """
    resultado = ultimo_resultado(desde=empezo)
    if resultado and (not resultado.get('ok')):
        motivo = (resultado.get('mensaje') or '').strip()
        return (False, motivo or mensaje or tr('El script de Resolve terminó con un error.'))
    else:
        return (ok, mensaje)
def ejecutar(accion, carpeta_scripts=None, datos=None, timeout=90, on_progreso=None):
    """Ejecuta una accion en Resolve por el mejor camino disponible.\n\n    accion: \'detectar\' | \'subtitulos\' | \'sfx\'\n    carpeta_scripts: opcional. Si no se pasa se usa la carpeta de adentro\n        del programa, que es la correcta. Antes era obligatoria y cada\n        llamador tenia que acertarla por su cuenta: el SFX Lab pasaba la\n        del menu de Resolve y en Studio fallaba siempre.\n\n    Devuelve (ok, mensaje). Nunca lanza consolas ni automatiza menus.\n    """
    ruta = script_de(accion, carpeta_scripts)
    if ruta is None:
        return (False, tr('Acción desconocida: {accion}', accion=accion))
    else:
        empezo = time.time()
        if _mcp_conectado():
            import resolve_mcp
            ok, mensaje = resolve_mcp.ejecutar_py(str(ruta), timeout=max(timeout, 120), on_progreso=on_progreso)
            # si fallo el TRANSPORTE (no el script), se prueban los otros caminos
            if ok or not str(mensaje).startswith('MCP:'):
                return _con_motivo_real(ok, mensaje, empezo)
        puente_vivo = puente_activo() or _puente_trabajando()
        if puente_vivo and (not puente_incompatible()):
            if puente_no_conoce(accion):
                # el Puente que quedo corriendo es de una version anterior: se le pide que se retire y, si no quedo otro en su lugar, se lanza el nuevo
                if not pedir_retirada_del_puente() or (not puente_activo() and not lanzar_puente_auto(45)) or puente_no_conoce(accion):
                    return (False, MENSAJE_PUENTE_VIEJO)
            ok, mensaje = _encolar(accion, datos=datos, timeout=timeout, on_progreso=on_progreso)
            if (not ok) and _puente_perdido(mensaje) and lanzar_puente_auto():
                ok, mensaje = _encolar(accion, datos=datos, timeout=timeout, on_progreso=on_progreso)       # Mac: el Puente se relanzo solo
            return _con_motivo_real(ok, mensaje, empezo)
        else:
            if disponible():
                if not ruta.exists():
                    if accion in ('efectos', 'armar_video', 'pausas'):          # solo existen como script .lua del Puente de Free; con Studio van por el MCP
                        return (False, tr('Esta función necesita el MCP de DaVinci Resolve Studio 21.1 o el Puente de Resolve Free.'))
                    return (False, tr('No encuentro el script en {ruta}', ruta=ruta))
                else:
                    ok, mensaje = ejecutar_script(str(ruta))
                    return _con_motivo_real(ok, mensaje, empezo)
            else:
                if puente_vivo:
                    return (False, MENSAJE_PUENTE_VIEJO)
                else:
                    if scripting_desactivado():
                        # v5.3.4: Resolve ESTÁ ahí pero no acepta scripts externos (Studio con «External scripting using» en None): el Puente no es el camino,
                        # se le dice lo que hay que cambiar (antes salía «el Puente perdió la conexión» y el usuario de Studio no sabía qué hacer)
                        traer_resolve_al_frente()
                        return (False, mensaje_para_el_usuario())
                    if lanzar_puente_auto():            # Resolve Free: Mac por el menú, Windows por la consola F6 (Resolve Free): se pulsa solo Workspace > Scripts > CineCaptions_Puente
                        ok, mensaje = _encolar(accion, datos=datos, timeout=timeout, on_progreso=on_progreso)
                        return _con_motivo_real(ok, mensaje, empezo)
                    traer_resolve_al_frente()
                    return (False, mensaje_para_el_usuario())
def ejecutar_script_o_menu(ruta_script, datos=None, timeout=90):
    """Obsoleta. Usa ejecutar(accion, carpeta_scripts) en su lugar."""
    ruta = Path(ruta_script)
    accion = None
    for clave, nombre in SCRIPTS.items():
        if ruta.name == nombre:
            accion = clave
            break
    if accion is None:
        return ejecutar_script(str(ruta))
    else:
        return ejecutar(accion, ruta.parent, datos=datos, timeout=timeout)
def _puente_perdido(mensaje):
    """True si el Puente contesto que perdio su conexion con Resolve (la caduca sola en la version gratuita) o que dejo de responder."""
    t = str(mensaje or '').lower()
    return 'puente perdio su conexion' in t or 'puente perdió su conexión' in t or 'caduca sola' in t or 'puente dejó de responder' in t         or 'bridge lost' in t or 'bridge stopped' in t


_APPLESCRIPT_PUENTE = '''
on buscar(m, nivel)
    tell application "System Events"
        repeat with it in (menu items of m)
            set nm to ""
            try
                set nm to (name of it) as text
            end try
            if nm is "CineCaptions_Puente" then
                click it
                return true
            end if
            if nivel < 4 then
                try
                    if (count of menus of it) > 0 then
                        if my buscar(menu 1 of it, nivel + 1) then return true
                    end if
                end try
            end if
        end repeat
    end tell
    return false
end buscar

tell application "System Events"
    if not (exists process "DaVinci Resolve") then return "sin_resolve"
    tell process "DaVinci Resolve"
        repeat with b in (menu bar items of menu bar 1)
            try
                if my buscar(menu 1 of b, 1) then return "ok"
            end try
        end repeat
    end tell
end tell
return "sin_menu"
'''


def _menu_puente_mac():
    """Corre el AppleScript que pulsa el menu del Puente: (codigo, salida, error). salida = 'ok' | 'sin_resolve' | 'sin_menu'."""
    import subprocess
    r = subprocess.run(['osascript', '-e', _APPLESCRIPT_PUENTE], capture_output=True, text=True, errors='replace', timeout=30)
    return r.returncode, (r.stdout or '').strip(), (r.stderr or '')


ARCHIVO_STOP = CARPETA_COMPARTIDA / 'puente.stop'


def pedir_retirada_del_puente(espera_s=30):
    """Le pide al Puente que esta corriendo que se retire y espera a que deje de latir; True si se fue. Modo señales (Free 21.1): lo hace `puente.relevo` (cualquier Puente con una
    señal que no es suya se va); con io, `puente.stop` con un token ajeno. Un Puente lanzado desde la consola de Resolve la deja ocupada hasta que termina: por eso hay que sacarlo
    antes de poder escribir ahi el Puente nuevo. Si en la consola habia otra orden esperando, el Puente nuevo arranca solo al irse el viejo: tambien cuenta como «se fue» (cambia la
    version que late). Nunca lanza."""
    try:
        CARPETA_COMPARTIDA.mkdir(parents=True, exist_ok=True)
        version0 = version_del_puente()
        ARCHIVO_STOP.write_text('app', encoding='utf-8')
        ARCHIVO_RELEVO.write_text('app', encoding='utf-8')
        inicio = time.time()
        faltaba_desde = None
        while time.time() - inicio < espera_s:
            version = version_del_puente()
            if not puente_activo() or (version is not None and version != version0):
                return True
            # Un Puente RECIEN lanzado toma por suya la señal hasta que la ve desaparecer (puente_activo() la poda a los 3 s): se la vuelve a dejar cuando ya llevaba 2,5 s sin estar
            if ARCHIVO_RELEVO.exists():
                faltaba_desde = None
            elif faltaba_desde is None:
                faltaba_desde = time.time()
            elif time.time() - faltaba_desde >= 2.5:
                ARCHIVO_RELEVO.write_text('app', encoding='utf-8')
                faltaba_desde = None
            time.sleep(0.5)
        return False
    except Exception:
        return False
    finally:
        for f in (ARCHIVO_STOP, ARCHIVO_RELEVO):
            try:
                f.unlink()
            except Exception:
                pass


def _esperar_latido(segundos, version=None):
    """Espera a que el Puente lata (y, si se pide, a que sea de esa version: el nuevo le pide el relevo al viejo)."""
    inicio = time.time()
    while time.time() - inicio < segundos:
        if puente_activo() and (version is None or version_del_puente() == version):
            return True
        time.sleep(0.5)
    return False


def lanzar_puente_mac(espera_s=25, espera_abrir_s=180, forzar=False):
    """Mac: pulsa solo el menu de Resolve (Workspace > Scripts > CineCaptions_Puente) por «System Events» y espera a que el Puente
    lata. Hace falta el permiso de Accesibilidad para CineCaptions (macOS lo pide la primera vez). Si Resolve esta cerrado lo abre
    (`open -a`, Free no tiene MCP que lo abra) y espera a que muestre el menu de Scripts (= con un proyecto abierto). Devuelve True si el Puente
    quedo vivo. Con `forzar` lo lanza aunque ya haya uno latiendo (uno de una version anterior: el nuevo le pide el relevo) y espera a que lata el de la version actual. Nunca lanza;
    si algo falla deja una linea en el Registro y se sigue con el aviso de siempre."""
    if sys.platform != 'darwin':
        return False
    try:
        import subprocess
        import registro
        version = VERSION_PUENTE_ESPERADA if forzar else None
        if puente_activo() and not forzar:
            return True
        codigo, salida, err = _menu_puente_mac()
        if codigo == 0 and salida == 'sin_resolve':
            ab = subprocess.run(['open', '-a', 'DaVinci Resolve'], capture_output=True, text=True, errors='replace', timeout=30)
            if ab.returncode != 0:
                registro.aviso('No encuentro DaVinci Resolve en este Mac (open -a): abrelo tu con un proyecto y repite.', 'Puente · Mac')
                return False
            registro.info('Abro DaVinci Resolve para lanzar el Puente.', 'Puente · Mac')
            inicio = time.time()
            while time.time() - inicio < espera_abrir_s:
                time.sleep(4.0)
                codigo, salida, err = _menu_puente_mac()
                if codigo != 0 and ('-25211' in err or '-1719' in err or 'assistive' in err.lower()):
                    registro.aviso('No pude lanzar el Puente en Resolve por el menu: sin permiso de Accesibilidad para CineCaptions (Ajustes del Sistema > Privacidad y seguridad > Accesibilidad)', 'Puente · Mac')
                    return False
                if codigo == 0 and salida == 'ok':
                    if _esperar_latido(espera_s, version):
                        registro.info('El Puente se lanzo solo desde el menu de Resolve.', 'Puente · Mac')
                        return True
                    # el menu estaba pero Resolve aun cargaba su proyecto: se vuelve a intentar
            registro.aviso('Resolve no mostro un proyecto abierto en %d s: abrelo tu (la pantalla de proyectos no vale) y repite.' % int(espera_abrir_s), 'Puente · Mac')
            return False
        if codigo != 0 or salida != 'ok':
            if '-25211' in err or '-1719' in err or 'asistencia' in err.lower() or 'assistive' in err.lower():
                motivo = 'sin permiso de Accesibilidad para CineCaptions (Ajustes del Sistema > Privacidad y seguridad > Accesibilidad)'
            else:
                motivo = salida or err.strip()[-200:] or 'sin respuesta'
            registro.aviso('No pude lanzar el Puente en Resolve por el menu: ' + motivo, 'Puente · Mac')
            return False
        if _esperar_latido(espera_s, version):
            registro.info('El Puente se lanzo solo desde el menu de Resolve.', 'Puente · Mac')
            return True
        registro.aviso('Pulse el menu del Puente pero no empezo a latir en %d s.' % espera_s, 'Puente · Mac')
    except Exception:
        try:
            import registro
            registro.excepcion(origen='Puente · Mac')
        except Exception:
            pass
    return False


def lanzar_puente_auto(espera_s=25, forzar=False):
    """Resolve Free sin Puente: lo lanza solo. Mac: por el menú (lanzar_puente_mac); Windows: por la consola de comandos de Resolve (colocacion.lanzar_puente_windows). False si no se pudo."""
    if sys.platform == 'darwin':
        return lanzar_puente_mac(espera_s, forzar=forzar)
    if sys.platform.startswith('win'):
        try:
            import colocacion
            return colocacion.lanzar_puente_windows(espera_s, forzar=forzar)
        except Exception:
            return False
    return False


def traer_resolve_al_frente():
    """Trae la ventana de Resolve al frente cuando no hay API disponible.\n\n    Es best-effort: si algo falla, no pasa nada, el usuario simplemente\n    tiene que hacer alt+tab.\n    """
    if not sys.platform.startswith('win'):
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, None)
        titulo = ctypes.create_unicode_buffer(512)
        encontrada = None

        @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        def enum_cb(h, _):
            nonlocal encontrada
            user32.GetWindowTextW(h, titulo, 512)
            if 'DaVinci Resolve' in titulo.value:
                encontrada = h
                return 0
            return 1

        user32.EnumWindows(enum_cb, 0)
        if encontrada:
            user32.ShowWindow(encontrada, 9)
            user32.SetForegroundWindow(encontrada)
    except Exception:
        pass
