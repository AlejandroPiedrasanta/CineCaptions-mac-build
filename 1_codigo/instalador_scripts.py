# CineCaptions · By Cinema Productions
# 1_codigo/instalador_scripts.py — copia los scripts de CineCaptions al menú de DaVinci Resolve y comprueba que estén al día.
"""\ninstalador_scripts.py\n---------------------\nDeja los scripts de CineCaptions dentro de DaVinci Resolve.\n\nResolve solo lista en su menu los .py que encuentra en SU carpeta de\nscripts. Mientras no esten ahi, no hay forma de correr \'Detectar Video\' ni\nel \'Puente\' -que es el camino de respaldo para la version gratuita- y el\nmenu muestra \"No Scripts\".\n\nPOR QUE ES UN MODULO APARTE\n===========================\nEsto vivia dentro de \"CineCaptions (script principal).py\". El SFX Lab tambien lo\nnecesita, pero no podia importarlo: ese archivo tiene ESPACIOS en el\nnombre, asi que no es un nombre de modulo valido, y en la app compilada\nademas pasa a llamarse __main__. El intento daba siempre\n\n    No module named \'CineCaptions\'\n\ny por eso el boton \"+ Agregar\" del SFX Lab no instalaba nada.\n\nDOS COSAS QUE HAY QUE SABER DE RESOLVE\n======================================\nDel README oficial de scripting de Blackmagic:\n\n  \"On startup, DaVinci Resolve scans the subfolders ... and enumerates the\n   scripts found in the Workspace application menu under Scripts.\"\n\n  -> Resolve arma ese menu UNA sola vez, al arrancar. Si copiamos los\n     scripts con Resolve abierto, no aparecen hasta que lo reinicie.\n\n  \"Place your script under Utility to be listed in all pages ... or under\n   folders for individual pages (Edit, Color or Deliver).\"\n\n  -> Por eso van a \'Utility\' y no a \'Edit\': asi se ven desde cualquier\n     pagina de Resolve, no solo desde la de Edicion.\n"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from i18n import tr
def _base_recursos():
    """Carpeta de los archivos que acompañan al programa.\n\n    Compilado con PyInstaller los datos se extraen a una carpeta temporal\n    (sys._MEIPASS); sin compilar, es la del proyecto.\n    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).resolve().parent.parent / '2_recursos'
BASE_RECURSOS = _base_recursos()
ARCHIVO_REGISTRO = Path.home() / 'DaVinciSubtitles' / 'instalacion_scripts.txt'
ARCHIVO_CARPETA_SCRIPTS = Path.home() / 'DaVinciSubtitles' / 'scripts_dir.txt'
def sfx_ruta_reglas_usuario():
    """Donde queda el sfx_rules.json que el usuario SI puede editar."""
    from sfx_rules import CARPETA_USUARIO
    return CARPETA_USUARIO / 'sfx_rules.json'
MENU_SCRIPTS = tr('Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español)   (en inglés: Workspace > Scripts)')
EXTENSIONES_MENU = ('*.lua',)
def _nuestros_scripts():
    """Los scripts que van al MENU de Resolve (solo .lua)."""
    origen = BASE_RECURSOS / 'resolve_scripts'
    if not origen.is_dir():
        return []
    else:
        archivos = []
        for patron in EXTENSIONES_MENU:
            archivos += origen.glob(patron)
        return sorted(archivos, key=lambda p: p.name)
# v5.4.43: la marca anterior del programa («RCS», antes de llamarse CineCaptions) dejó copias viejas de los scripts en el menú de Resolve («RCS_Puente», «RCS_Subtitulos»…) AL LADO de las
# nuevas «CineCaptions_…»: el menú salía con todo duplicado y el usuario no sabía cuál correr (ni cuál de los dos Puentes estaba vivo). Solo estos nombres, que son nuestros; nunca otro script.
NOMBRES_VIEJOS = (
    'RCS_ArmarVideo.lua', 'RCS_DetectarVideo.lua', 'RCS_Efectos.lua', 'RCS_Exportar_PackDRB.lua', 'RCS_ImportarEstilos.lua', 'RCS_InsertarSFX.lua', 'RCS_Pausas.lua',
    'RCS_Prueba_MediaPool.lua', 'RCS_Puente.lua', 'RCS_SfxMarcadores.lua', 'RCS_SfxReemplazar.lua', 'RCS_Subtitulos.lua', 'RCS_Vista.lua',
    'RCS.py', 'RCS - Detectar Video.py', 'RCS - Importar Estilos.py', 'RCS - Insertar SFX.py', 'RCS - Puente.py', 'RCS - SFX Marcadores.py', 'RCS - SFX Reemplazar.py', 'RCS - Vista Real.py',
)
SUBCARPETAS_DE_SCRIPTS = ('Utility', 'Edit', 'Comp', 'Color', 'Deliver')


def retirar_scripts_viejos(respaldar=True):
    """Borra de TODAS las carpetas de scripts de Resolve (Free y Studio, usuario y sistema) las copias de la marca anterior (NOMBRES_VIEJOS). Antes de borrar deja una copia en
    ~/DaVinciSubtitles/respaldo_scripts_viejos/. Devuelve la lista de rutas retiradas. Nunca lanza."""
    retirados = []
    try:
        respaldo = Path.home() / 'DaVinciSubtitles' / 'respaldo_scripts_viejos'
        for raiz in raices_scripts_resolve():
            for sub in SUBCARPETAS_DE_SCRIPTS:
                carpeta = raiz / sub
                if not carpeta.is_dir():
                    continue
                for nombre in NOMBRES_VIEJOS:
                    archivo = carpeta / nombre
                    try:
                        if not archivo.is_file():
                            continue
                        if respaldar:
                            try:
                                respaldo.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(archivo, respaldo / nombre)
                            except Exception:
                                pass
                        archivo.unlink()
                        retirados.append(str(archivo))
                    except Exception as exc:
                        _FALLOS_LIMPIEZA.append(f'{archivo}: {exc}')
        if retirados:
            try:
                import registro
                registro.info(tr('Retiré {n} script(s) viejos de la marca anterior (RCS_…) del menú de Resolve: ahora solo salen los CineCaptions_… (Resolve los quita del menú al abrirse de nuevo).', n=len(retirados)), 'Scripts de Resolve')
            except Exception:
                pass
    except Exception:
        pass
    return retirados


def _todos_los_nombres_del_programa():
    """Nombres de TODOS los scripts que el programa reconoce como suyos\n    (.py + .lua), para poder limpiar copias viejas de la carpeta de\n    Resolve sin tocar scripts ajenos del usuario."""
    origen = BASE_RECURSOS / 'resolve_scripts'
    if not origen.is_dir():
        return set()
    else:
        nombres = set()
        for patron in ['*.py', '*.lua']:
            for p in origen.glob(patron):
                nombres.add(p.name)
        nombres.update({'CineCaptions.py', 'CineCaptions - Insertar SFX.py', 'CineCaptions - Detectar Video.py', 'CineCaptions - Puente.py'})
        nombres.update(NOMBRES_VIEJOS)
        return nombres
SUBCARPETA_SCRIPTS = 'Utility'
_CACHE_RAICES = {'valor': None, 'cuando': 0.0}
_RAICES_VALEN_S = 30.0
def raices_scripts_resolve():
    """Como _raices_scripts_resolve_ahora, con la respuesta valida 30 s\n    (v3.3.3): en el Mac la lista rastrea los contenedores de la App Store y\n    el arranque la pedia media docena de veces."""
    ahora = time.time()
    if _CACHE_RAICES['valor'] is not None and ahora - _CACHE_RAICES['cuando'] < _RAICES_VALEN_S:
        return list(_CACHE_RAICES['valor'])
    else:
        valor = _raices_scripts_resolve_ahora()
        _CACHE_RAICES['valor'] = list(valor)
        _CACHE_RAICES['cuando'] = ahora
        return valor
def _raices_scripts_resolve_ahora():
    """Todas las carpetas donde Resolve busca scripts, segun el sistema.\n\n    Son las documentadas en el README oficial de Blackmagic: una para todos\n    los usuarios y otra para el usuario actual. Se devuelven las dos porque\n    no hay forma de saber de antemano cual va a leer la instalacion de\n    Resolve que tenga enfrente el usuario.\n    """
    if sys.platform == 'darwin':
        soporte = 'Library/Application Support/Blackmagic Design/DaVinci Resolve'
        raices = [Path.home() / soporte / 'Fusion/Scripts', Path('/') / soporte / 'Fusion/Scripts']
        contenedores = Path.home() / 'Library/Containers'
        try:
            for c in sorted(contenedores.iterdir()):
                if 'resolve' not in c.name.lower():
                    continue
                else:
                    if not (c / 'Data').is_dir():
                        continue
                    else:
                        raices.append(c / 'Data' / soporte / 'Fusion/Scripts')
        except Exception:
            pass
        return raices
    else:
        if sys.platform.startswith('win'):
            appdata = Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming'))
            programdata = Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'))
            raices = [appdata / 'Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts', programdata / 'Blackmagic Design/DaVinci Resolve/Fusion/Scripts']
            return raices
        else:
            raices = [Path.home() / '.local/share/DaVinciResolve/Fusion/Scripts', Path('/opt/resolve/Fusion/Scripts')]
            return raices
def carpetas_scripts_resolve():
    """Las carpetas concretas donde hay que dejar nuestros .py."""
    return [r / SUBCARPETA_SCRIPTS for r in raices_scripts_resolve()]
def carpeta_scripts_resolve():
    """La carpeta \'principal\' (la del usuario), para mostrarla en avisos."""
    carpetas = carpetas_scripts_resolve()
    for c in carpetas:
        if c.is_dir():
            return c
    return carpetas[0]
def _universo(carpeta):
    return 'sandbox' if 'Containers' in Path(carpeta).parts else 'normal'
def _indicio_de_uso(carpeta):
    """Cuanto apunta a que Resolve USA de verdad esta carpeta.

    La señal es simple y fiable: las carpetas de soporte las crea Resolve al
    arrancar. Si ya existen, es que hay un Resolve usandolas. Sirve para no
    elegir la carpeta por 'la primera donde pueda escribir', que era el fallo:
    escribir siempre funciona, que Resolve lo lea es otra cosa.

    carpeta es .../DaVinci Resolve/Fusion/Scripts/<sub>, asi que dos niveles
    por encima esta 'Fusion' y tres, 'DaVinci Resolve'.
    """
    try:
        fusion = carpeta.parent.parent
        soporte = fusion.parent
        if fusion.is_dir():
            return 2
        if soporte.is_dir():
            return 1
    except Exception:
        pass
    return 0
def _misma_carpeta(a, b):
    try:
        return Path(a).samefile(Path(b))
    except (OSError, ValueError):
        try:
            return str(Path(a).resolve()) == str(Path(b).resolve())
        except Exception:
            return False
_CACHE_CORRIENDO = {'valor': None, 'cuando': 0.0}
_CORRIENDO_VALE_S = 5.0
def resolve_esta_corriendo():
    """True si DaVinci Resolve esta abierto en este momento.\n\n    Importa porque Resolve arma el menu de Scripts UNA sola vez, al\n    arrancar (\"On startup, DaVinci Resolve scans the subfolders...\" dice el\n    README oficial). Si instalamos los scripts con Resolve ya abierto, no\n    aparecen hasta que lo reinicie, y sin avisarlo el usuario cree que la\n    instalacion fallo.\n\n    v3.3.3: la respuesta vale 5 s. MEDIDO: el tasklist/pgrep cuesta 0,3 s\n    y el arranque lo preguntaba varias veces seguidas.\n    """
    ahora = time.time()
    if _CACHE_CORRIENDO['valor'] is not None and ahora - _CACHE_CORRIENDO['cuando'] < _CORRIENDO_VALE_S:
        return _CACHE_CORRIENDO['valor']
    else:
        valor = _resolve_esta_corriendo_ahora()
        _CACHE_CORRIENDO['valor'] = valor
        _CACHE_CORRIENDO['cuando'] = ahora
        return valor
def _proceso_corriendo_windows(nombre_exe):
    """True si hay un proceso con ese .exe. v5.4: ToolHelp32 (~2 ms) en vez de lanzar 'tasklist' (~0,3 s), que se
    pagaba en el hilo de la interfaz cada vez que se miraba si Resolve estaba abierto."""
    import ctypes
    from ctypes import wintypes

    class _Proc(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', ctypes.c_long), ('dwFlags', wintypes.DWORD),
                    ('szExeFile', ctypes.c_wchar * 260)]

    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Proc)]
    k32.Process32FirstW.restype = wintypes.BOOL
    k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Proc)]
    k32.Process32NextW.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    invalido = (1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1
    foto = k32.CreateToolhelp32Snapshot(0x2, 0)
    if foto is None or foto == invalido:
        raise OSError('no pude listar los procesos')
    try:
        entrada = _Proc()
        entrada.dwSize = ctypes.sizeof(_Proc)
        objetivo = nombre_exe.lower()
        ok = k32.Process32FirstW(foto, ctypes.byref(entrada))
        while ok:
            if entrada.szExeFile.lower() == objetivo:
                return True
            ok = k32.Process32NextW(foto, ctypes.byref(entrada))
        return False
    finally:
        k32.CloseHandle(foto)
def _resolve_esta_corriendo_ahora():
    try:
        if sys.platform.startswith('win'):
            try:
                return _proceso_corriendo_windows('Resolve.exe')
            except Exception:
                pass
            import subprocess
            r = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq Resolve.exe', '/NH'],
                capture_output=True, text=True, timeout=6,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return 'Resolve.exe' in (r.stdout or '')
        import subprocess
        r = subprocess.run(['pgrep', '-x', 'Resolve'],
                           capture_output=True, text=True, timeout=6)
        if (r.stdout or '').strip():
            return True
        r = subprocess.run(['pgrep', '-f', 'DaVinci Resolve.app'],
                           capture_output=True, text=True, timeout=6)
        return bool((r.stdout or '').strip())
    except Exception:
        return False
def resolve_esta_instalado():
    """True si parece haber un DaVinci Resolve en esta maquina.\n\n    Sirve para no molestar con avisos de instalacion en un equipo donde\n    Resolve simplemente no esta.\n    """
    if sys.platform == 'darwin':
        marcas = [Path('/Applications/DaVinci Resolve/DaVinci Resolve.app'), Path('/Applications/DaVinci Resolve.app'), Path.home() / 'Library/Application Support/Blackmagic Design/DaVinci Resolve']
    else:
        if sys.platform.startswith('win'):
            appdata = Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming'))
            marcas = [Path('C:\\Program Files\\Blackmagic Design\\DaVinci Resolve'), appdata / 'Blackmagic Design/DaVinci Resolve']
        else:
            marcas = [Path('/opt/resolve')]
    return any((m.exists() for m in marcas))
def resolve_ejecutable():
    """v5.4.48: la ruta del PROGRAMA DaVinci Resolve (Resolve.exe / la app de Mac) o None si no está. A diferencia de resolve_esta_instalado,
    no cuenta la carpeta de ajustes (%APPDATA%\\Blackmagic Design, ~/Library/Application Support), que queda al desinstalar Resolve:
    con ella un equipo sin Resolve parecía tenerlo y GO no entregaba el video. Si no se puede mirar, lanza la excepción (quien pregunta decide)."""
    if sys.platform.startswith('win'):
        import resolve_bridge
        exe = Path(resolve_bridge._resolve_dir_windows()) / 'Resolve.exe'
        return exe if exe.is_file() else None
    if sys.platform == 'darwin':
        for base in (Path('/Applications'), Path.home() / 'Applications'):
            for app in (base / 'DaVinci Resolve' / 'DaVinci Resolve.app', base / 'DaVinci Resolve.app',
                        base / 'DaVinci Resolve Studio' / 'DaVinci Resolve Studio.app', base / 'DaVinci Resolve Studio.app'):
                if (app / 'Contents' / 'MacOS').is_dir():
                    return app
        return None
    exe = Path('/opt/resolve/bin/resolve')
    return exe if exe.is_file() else None
def _quitar_cuarentena(ruta):
    """Le saca a un archivo la marca de cuarentena de macOS.\n\n    Todo lo que baja de internet queda marcado con com.apple.quarantine, y\n    un script marcado puede no ser tomado en cuenta por Resolve. Es\n    best-effort: si el atributo no esta, xattr devuelve error y da igual.\n    """
    if sys.platform != 'darwin':
        return
    else:
        try:
            subprocess.run(['xattr', '-d', 'com.apple.quarantine', str(ruta)], capture_output=True, timeout=5)
        except Exception:
            return None
        return
def _copiar(archivo, final):
    """Copia un script a la carpeta de Resolve.\n\n    Se usa copyfile y NO copy2 a proposito. copy2 llama a copystat, que a\n    su vez copia los atributos extendidos, y en macOS eso incluye\n    com.apple.quarantine: como nuestro programa llega dentro de un .zip\n    descargado, sus archivos vienen marcados y la marca viajaba con ellos\n    a la carpeta de scripts de Resolve.\n\n    copyfile copia solo el contenido, que es lo unico que importa aca.\n    Ademas evita el otro problema de copy2: fallar al copiar permisos en\n    volumenes de red y en carpetas sincronizadas (OneDrive, iCloud) aunque\n    el archivo en si se pueda escribir perfectamente.\n    """
    shutil.copyfile(archivo, final)
    _quitar_cuarentena(final)
_IGUALES = set()
def _mismo_contenido(a, b):
    """True solo si los dos archivos son identicos byte a byte.\n\n    Ante cualquier duda devuelve False, para que se copie: es mucho peor\n    saltarse una actualizacion que reescribir un archivo de 40 KB.\n    """
    try:
        sa, sb = a.stat(), b.stat()
        if sa.st_size != sb.st_size:
            return False
        llave = (str(a), sa.st_size, sa.st_mtime_ns, str(b), sb.st_size, sb.st_mtime_ns)
        if llave in _IGUALES:                  # v5.4: ya comparados y sin tocar desde entonces: no se vuelven a leer (~0,6 MB)
            return True
        igual = a.read_bytes() == b.read_bytes()
        if igual:
            _IGUALES.add(llave)
        return igual
    except Exception:
        return False
def _instalar_en_una_carpeta(destino, archivos, forzar):
    """Copia los scripts a UNA carpeta. Devuelve (copiados, error)."""
    try:
        destino.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return ([], f'no pude crear la carpeta ({e})')
    copiados = []
    for archivo in archivos:
        final = destino / archivo.name
        try:
            if not forzar and final.exists() and _mismo_contenido(archivo, final):
                        continue
            _copiar(archivo, final)
            copiados.append(archivo.name)
        except Exception as e:
            return (copiados, f'no pude copiar \'{archivo.name}\' ({e})')
    return (copiados, None)
def _registrar(detalle, archivos, error):
    """Deja en disco todo lo que paso en esta instalacion.

    Se escribe SIEMPRE, salga bien o mal. Es lo unico que permite saber
    que fallo en la maquina de alguien que compro el programa y no tiene
    forma de abrir una terminal: se le pide este archivo y viene la causa
    exacta.
    """
    origen = BASE_RECURSOS / 'resolve_scripts'

    def _carpetas_utility_candidatas():
        fuera = []
        try:
            for raiz in raices_scripts_resolve():
                c = raiz / 'Utility'
                if c.is_dir():
                    fuera.append(c)
        except Exception:
            pass
        return fuera

    def _version_del_puente_en(carpeta):
        try:
            texto = (carpeta / 'CineCaptions_Puente.lua').read_text(encoding='utf-8', errors='replace')
        except OSError:
            return '(no esta)'
        version = paquete = None
        for linea in texto.splitlines()[:80]:
            if version is None and 'VERSION' in linea and '"' in linea:
                version = linea.split('"')[1]
            elif paquete is None and 'PAQUETE' in linea and '"' in linea:
                paquete = linea.split('"')[1]
        if version and paquete:
            return f'{version} (del programa v{paquete})'
        return version or '?'

    def _version_de_los_scripts(carpeta):
        """La VERSION que declara CineCaptions_Subtitulos.lua, o '?' si no se puede."""
        try:
            texto = (carpeta / 'CineCaptions_Subtitulos.lua').read_text(encoding='utf-8', errors='replace')
        except OSError:
            return '?'
        for linea in texto.splitlines()[:60]:
            if 'VERSION' in linea and '"' in linea:
                return linea.split('"')[1]
        return '?'

    lineas = [
        f"fecha            : {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f'sistema          : {sys.platform}',
        f"compilado        : {bool(getattr(sys, 'frozen', False))}",
        f'BASE_RECURSOS    : {BASE_RECURSOS}',
        f'scripts en el app: {origen}',
        f'   existe        : {origen.is_dir()}',
        f"   cuantos       : {len(archivos)} ({', '.join(a.name for a in archivos)})",
        f'   version       : {_version_de_los_scripts(origen)}',
        *[f'   Puente en {c}: {_version_del_puente_en(c)}'
          for c in _carpetas_utility_candidatas()],
        *([f'   LIMPIEZA FALLIDA: {f}' for f in _FALLOS_LIMPIEZA] or []),
        f'Resolve instalado: {resolve_esta_instalado()}',
        f'Resolve abierto  : {resolve_esta_corriendo()}',
        f"resultado global : {'OK' if not error else error}",
        '',
        'carpetas destino:',
    ]
    for carpeta, copiados, err in detalle:
        lineas.append(f'  {carpeta}')
        lineas.append(f'      existe     : {carpeta.is_dir()}')
        try:
            escribible = carpeta.is_dir() and os.access(carpeta, os.W_OK)
        except Exception:
            escribible = False
        lineas.append(f'      escribible : {escribible}')
        lineas.append(f"      copiados   : {len(copiados)} {copiados or ''}")
        lineas.append(f"      error      : {err or 'ninguno'}")
    try:
        ARCHIVO_REGISTRO.parent.mkdir(parents=True, exist_ok=True)
        ARCHIVO_REGISTRO.write_text('\n'.join(lineas), encoding='utf-8')
    except Exception:
        pass
ARCHIVO_EDICION = Path.home() / 'DaVinciSubtitles' / 'edicion.json'
DESCRIPCION_EDICION = {'studio': 'Studio (la API funciona: no hace falta el menú ni el Puente)', 'free': 'Free (los botones necesitan el Puente corriendo en Resolve)', 'desconocida': 'no la sé todavía (abre Resolve y vuelve a mirar)'}
def _edicion_guardada():
    try:
        datos = json.loads(ARCHIVO_EDICION.read_text(encoding='utf-8'))
        edicion = datos.get('edicion')
        return edicion if edicion in ('studio', 'free') else None
    except Exception:
        return None
def _guardar_edicion(edicion):
    try:
        ARCHIVO_EDICION.parent.mkdir(parents=True, exist_ok=True)
        ARCHIVO_EDICION.write_text(json.dumps({'edicion': edicion, 'visto_en': time.strftime('%Y-%m-%d %H:%M:%S')}, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        return None
_CACHE_EDICION = {'valor': None, 'cuando': 0.0}
_EDICION_VALE_S = 60.0
def _titulo_de_resolve():
    """El título de la ventana principal de Resolve («DaVinci Resolve Studio - <proyecto>» / «DaVinci Resolve - <proyecto>»), '' si no se sabe (Windows)."""
    try:
        if sys.platform.startswith('win'):
            import colocacion
            return next((t for _h, t in colocacion._ventanas_de_resolve() if t.startswith('DaVinci Resolve')), '')
    except Exception:
        pass
    return ''


def edicion_de_resolve(refrescar=False):
    """\'studio\', \'free\' o \'desconocida\'.\n\n    La unica senal fiable es si la API externa conecta: eso solo pasa en\n    Studio. Pero con Resolve CERRADO tampoco conecta, y ahi no se puede\n    distinguir de Free. Por eso:\n\n      - API conecta                   -> studio  (y se recuerda)\n      - Resolve abierto y no conecta  -> free    (y se recuerda)\n      - Resolve cerrado               -> lo ultimo que vimos, o desconocida\n\n    Con \'desconocida\' se instala igual (ver instalar_scripts_en_resolve):\n    Free es el caso que se rompe si faltan los scripts, y si despues resulta\n    ser Studio la limpieza pasa sola en la siguiente pasada.\n\n    El import de resolve_bridge va adentro a proposito: resolve_bridge nos\n    importa a nosotros, y a nivel de modulo seria un ciclo.\n    """
    if not refrescar and _CACHE_EDICION['valor'] is not None and (time.time() - _CACHE_EDICION['cuando'] < _EDICION_VALE_S):
        return _CACHE_EDICION['valor']
    else:
        edicion = None
        try:
            import resolve_bridge
            if resolve_bridge.disponible(pasivo=True):
                edicion = 'studio'
        except Exception:
            pass
        if edicion is None and resolve_esta_corriendo():
            # v5.5.7: «abierto pero sin API» NO prueba que sea Free: un Studio ocupado (reproduciendo) o colgado tampoco contesta, y pasaba a «free»
            # (el GO lanzaba el Puente en Studio y lo bloqueaba). Se mira el título de su ventana; si no se sabe, se respeta lo guardado.
            titulo = _titulo_de_resolve()
            if 'DaVinci Resolve Studio' in titulo:
                edicion = 'studio'
            elif titulo.startswith('DaVinci Resolve') or _edicion_guardada() != 'studio':
                edicion = 'free'
        if edicion is not None:
            _guardar_edicion(edicion)
        else:
            edicion = _edicion_guardada() or 'desconocida'
        _CACHE_EDICION['valor'] = edicion
        _CACHE_EDICION['cuando'] = time.time()
        return edicion
def desinstalar_scripts_del_menu():
    """Saca nuestros scripts del menu de Resolve (caso Studio).\n\n    Solo borra los nombres que sabemos que son nuestros\n    (_todos_los_nombres_del_programa), asi que un script propio del usuario\n    que viva en la misma carpeta queda intacto.\n\n    Devuelve la lista de rutas borradas.\n    """
    nuestros = _todos_los_nombres_del_programa()
    borrados = []
    borrados += retirar_scripts_viejos(respaldar=False)               # v5.4.43: también las copias de la marca anterior (RCS_…)
    if not nuestros:
        return borrados
    else:
        for raiz in raices_scripts_resolve():
            for sub in ['Utility', 'Edit', 'Comp', 'Color', 'Deliver']:
                carpeta = raiz / sub
                if carpeta.is_dir():
                    for nombre in nuestros:
                        archivo = carpeta / nombre
                        try:
                            if archivo.exists():
                                archivo.unlink()
                                borrados.append(str(archivo))
                        except Exception:
                            pass
        return borrados
def _apuntar_carpeta_de_scripts(carpeta):
    """Le deja escrito al Puente donde quedaron los scripts."""
    try:
        ARCHIVO_CARPETA_SCRIPTS.parent.mkdir(parents=True, exist_ok=True)
        ARCHIVO_CARPETA_SCRIPTS.write_text(str(carpeta), encoding='utf-8')
        import sidecar_lua
        sidecar_lua.escribir_sidecar(ARCHIVO_CARPETA_SCRIPTS, {'texto': str(carpeta)})
    except Exception:
        return None
_FALLOS_LIMPIEZA = []
def _limpiar_instalaciones_viejas(carpetas_activas):
    """Borra copias viejas de nuestros scripts que ya no van al menu.\n\n    Se limpia SOLO lo que sabemos que es nuestro (los nombres conocidos\n    del programa, incluidos los .py de versiones anteriores que ya no van\n    al menu). Nunca se toca un archivo con otro nombre: eso podria ser un\n    script propio del usuario.\n\n    Se limpia en:\n      - Otras subcarpetas de la MISMA raiz (Edit/Comp/Color/Deliver): en\n        versiones viejas se instalaba en \'Edit\'.\n      - La otra raiz (usuario vs sistema) que YA NO usamos: hoy se\n        instala en una sola, asi que si quedo algo en la otra hay que\n        borrarlo para que Resolve no muestre duplicados en el menu.\n\n    Y NO se limpia -esto es nuevo- en un universo donde no acabamos de\n    instalar. Antes se limpiaba en todos, y en Mac eso significaba: instalar\n    en la carpeta normal y acto seguido borrar la copia del contenedor de\n    sandbox, que era justo la unica que ese Resolve podia leer. Si alguna vez\n    caia bien, la siguiente instalacion la quitaba.\n    """
    _FALLOS_LIMPIEZA.clear()
    nuestros = _todos_los_nombres_del_programa()
    if not nuestros:
        return
    else:
        activas = [Path(c) for c in carpetas_activas]
        universos_activos = {_universo(c) for c in activas}
        for raiz in raices_scripts_resolve():
            for sub in ['Utility', 'Edit', 'Comp', 'Color', 'Deliver']:
                carpeta = raiz / sub
                if not carpeta.is_dir():
                    continue
                else:
                    if _universo(carpeta) not in universos_activos:
                        continue
                    else:
                        if any((_misma_carpeta(carpeta, a) for a in activas)):
                            continue
                        else:
                            for nombre in nuestros:
                                try:
                                    (carpeta / nombre).unlink(missing_ok=True)
                                except Exception as exc:
                                    _FALLOS_LIMPIEZA.append(f'{carpeta / nombre}: {exc}')
def carpetas_templates_resolve():
    """v5.5.9: la carpeta Fusion/Templates del usuario (de ahí saca Resolve los títulos de Efectos › Títulos)."""
    if sys.platform == 'darwin':
        return [Path.home() / 'Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates']
    if sys.platform.startswith('win'):
        appdata = Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming'))
        return [appdata / 'Blackmagic Design/DaVinci Resolve/Support/Fusion/Templates']
    return [Path.home() / '.local/share/DaVinciResolve/Fusion/Templates']


def instalar_motions_en_resolve(forzar=False):
    """v5.5.9 (pedido: «no se crea .drfx para personalizar; los motions en el Inspector tienen que ser para editar»): los motions editables de
    CineCaptions (2_recursos/motions_resolve, hechos con generador_packs/drfx_motions.py: títulos de Fusion con el banner y el logo arriba y sus
    textos, colores, posición y tamaño publicados) en Efectos › Títulos › CineCaptions. Copia solo lo que cambió; Resolve los lee al abrirse.
    Devuelve (copiados, error)."""
    origen = BASE_RECURSOS / 'motions_resolve' / 'Edit' / 'Titles' / 'CineCaptions'
    if not origen.is_dir():
        return [], 'no están los motions dentro del programa'
    archivos = sorted(p for p in origen.iterdir() if p.suffix in ('.setting', '.png'))
    copiados, error = [], None
    for raiz in carpetas_templates_resolve():
        c, err = _instalar_en_una_carpeta(raiz / 'Edit' / 'Titles' / 'CineCaptions', archivos, forzar)
        copiados += c
        error = err or error
    return copiados, error


def instalar_scripts_en_resolve(destino=None, forzar=False):
    """Copia nuestros .lua a UNA carpeta de scripts de Resolve.

    Devuelve (copiados, error, detalle):
      copiados -> nombres escritos en la carpeta elegida
      error    -> None si funciono, o el motivo del ultimo intento fallido
      detalle  -> lista de (carpeta, copiados, error) para diagnosticar

    Antes se copiaba en TODAS las carpetas candidatas (usuario + sistema +
    contenedores de sandbox), pero Resolve leia de las dos y el menu
    mostraba cada script dos veces. Peor: el usuario corria el 'Puente'
    desde las dos carpetas y quedaban dos Puentes procesando el mismo
    trabajo -> renders duplicados, "Accion desconocida: nil", errores
    aleatorios. Ahora se instala en UNA sola (la del usuario, que siempre
    es escribible); si falla, se prueba la siguiente candidata como
    fallback, pero NUNCA en dos a la vez.

    Ademas, siempre se limpian las OTRAS carpetas para que no queden
    copias viejas que Resolve tambien liste.
    """
    try:                                                              # v5.5.9: y los motions editables (Efectos › Títulos › CineCaptions), en Studio y Free
        instalar_motions_en_resolve(forzar)
    except Exception:
        pass
    origen = BASE_RECURSOS / 'resolve_scripts'
    if not origen.is_dir():
        err = tr('No encuentro los scripts dentro del programa: {origen}',
                 origen=origen)
        _registrar([], [], err)
        return ([], err, [])
    archivos = _nuestros_scripts()
    if not archivos:
        err = tr('No hay ningún script para copiar en: {origen}',
                 origen=origen)
        _registrar([], archivos, err)
        return ([], err, [])
    if destino:
        destinos = [Path(destino)]
    else:
        destinos = carpetas_scripts_resolve()
        destinos.sort(key=_indicio_de_uso, reverse=True)
        nombres = [a.name for a in archivos]
        ya_instalado = next((c for c in destinos if c.is_dir() and all((c / n).exists() for n in nombres)),
                            None)
        if ya_instalado is not None:
            destinos = [ya_instalado] + [c for c in destinos
                                         if c != ya_instalado]
    detalle, copiados, activas = [], [], []
    universos_hechos = set()
    for carpeta in destinos:
        if _universo(carpeta) in universos_hechos:
            continue
        c, err = _instalar_en_una_carpeta(carpeta, archivos, forzar)
        detalle.append((carpeta, c, err))
        if err is not None:
            continue
        universos_hechos.add(_universo(carpeta))
        activas.append(carpeta)
        for nombre in c:
            if nombre not in copiados:
                copiados.append(nombre)
    alguna_ok = bool(activas)
    try:
        reglas = origen / 'sfx_rules.json'
        propia = sfx_ruta_reglas_usuario()
        if reglas.exists() and not propia.exists():
            propia.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(reglas, propia)
    except Exception:
        pass
    if alguna_ok:
        _apuntar_carpeta_de_scripts(activas[0])
        _limpiar_instalaciones_viejas(activas)
        retirar_scripts_viejos()                                      # v5.4.43: y las de la marca anterior (RCS_…), también en la carpeta activa
        _registrar(detalle, archivos, None)
        return (copiados, None, detalle)
    motivos = '\n'.join(f'  • {c}\n      {e}' for c, c2, e in detalle if e)
    _registrar(detalle, archivos, 'no se pudo escribir en ninguna carpeta')
    return ([], tr('No pude dejar los scripts en ninguna carpeta de Resolve:')
            + '\n\n' + motivos, detalle)
def scripts_instalados():
    """True si no falta nada para que Resolve pueda ejecutar lo nuestro.\n\n    En Studio siempre es True: los scripts del menu no se usan (la API\n    corre los .py de adentro del programa), asi que no hay nada que\n    instalar. Sin esto, toda maquina con Studio veria el aviso de \"No pude\n    dejar los scripts en Resolve\" por algo que no es un problema.\n    """
    if edicion_de_resolve() == 'studio':
        return True
    else:
        nuestros = [a.name for a in _nuestros_scripts()]
        if not nuestros:
            return False
        else:
            for carpeta in carpetas_scripts_resolve():
                if carpeta.is_dir():
                    if all(((carpeta / n).exists() for n in nuestros)):
                        return True
            return False
def scripts_desactualizados():
    """Scripts instalados en Resolve que NO son los que trae el programa.\n\n    Devuelve una lista de (nombre, carpeta). Vacia = todo al dia.\n\n    Existe porque un script viejo corriendo dentro de Resolve es\n    indistinguible de un bug: el usuario actualiza, reinicia, y sigue\n    viendo el mismo error, sin nada que se lo explique. Paso durante cuatro\n    versiones seguidas.\n\n    En Studio no aplica: ahi el menu no se usa.\n    """
    if edicion_de_resolve() == 'studio':
        return []
    else:
        viejos = []
        for archivo in _nuestros_scripts():
            for carpeta in carpetas_scripts_resolve():
                final = carpeta / archivo.name
                if final.exists() and (not _mismo_contenido(archivo, final)):
                        viejos.append((archivo.name, carpeta))
        return viejos
MENSAJE_MAC_APP_STORE = tr('DaVinci Resolve está instalado desde la Mac App Store. Esa versión corre aislada por macOS y no me deja actualizar los scripts que usa: los que tiene son de una versión anterior, y por eso el Puente no conecta por más que lo lances.\n\nLa solución es instalar DaVinci Resolve desde la web de Blackmagic. Es la misma aplicación y también es gratuita:\n\n1. Cierra DaVinci Resolve.\n2. Descárgalo de blackmagicdesign.com (sección Soporte).\n3. Instálalo y vuelve a abrir este programa.\n\nLa versión de la App Store puedes dejarla o desinstalarla, da igual.')
def problema_mac_app_store():
    """Aviso cuando el Resolve aislado se quedo con scripts viejos.\n\n    Se mira DESPUES de instalar: si los scripts del contenedor de Resolve\n    siguen sin ser los nuestros, es que no se pudieron reemplazar. Mirar el\n    permiso con os.access no vale en macOS: TCC deja pasar la pregunta y\n    niega la escritura.\n    """
    if sys.platform != 'darwin':
        return
    else:
        for nombre, carpeta in scripts_desactualizados():
            if _universo(carpeta) == 'sandbox':
                return MENSAJE_MAC_APP_STORE
        return
def python_para_resolve():
    """Ruta del Python que Resolve podria usar, o None si no hay ninguno.\n\n    Resolve NO usa el Python que lleva adentro nuestro programa: para\n    ejecutar un .py del menu necesita un interprete instalado en el\n    sistema. El README oficial lo pone entre los prerequisitos:\n        \"DaVinci Resolve scripting requires one of the following to be\n         installed (for all users): Lua 5.1, Python >= 3.6 64-bit...\"\n\n    En Mac esto pesa mucho: desde macOS 12.3 Apple dejo de traer Python,\n    asi que en un equipo recien formateado NO hay ninguno y Resolve\n    directamente no lista los .py en su menu.\n\n    Se miran rutas absolutas y no solo el PATH, porque el PATH de nuestra\n    app dentro de un .app no es el mismo que ve Resolve.\n    """
    if sys.platform.startswith('win'):
        rutas = []
    else:
        rutas = [Path('/usr/bin/python3'), Path('/usr/local/bin/python3'), Path('/opt/homebrew/bin/python3')]
        marco = Path('/Library/Frameworks/Python.framework/Versions')
        try:
            for v in sorted(marco.iterdir(), reverse=True):
                rutas.append(v / 'bin' / 'python3')
        except Exception:
            pass
    del_path = shutil.which('python3') or shutil.which('python')
    if del_path:
        rutas.append(Path(del_path))
    for ruta in rutas:
        if _python_funciona(ruta):
            return ruta
def _python_funciona(ruta):
    """True solo si el Python de esa ruta EJECUTA de verdad y es >= 3.6.

    No alcanza con que el archivo exista y sea ejecutable: en macOS,
    /usr/bin/python3 es un ATAJO que existe pero, si no estan las Command
    Line Tools de Xcode, al correrlo abre el instalador y devuelve error.
    Ese fue el caso del usuario ('xcode-select: No developer tools were
    found'): la version anterior lo daba por bueno y mentia diciendo que
    habia Python. Por eso hay que ejecutarlo.
    """
    try:
        if not Path(ruta).is_file():
            return False
        r = subprocess.run(
            [str(ruta), '-c', 'import sys; print(sys.version_info[:2])'],
            capture_output=True, text=True, timeout=8,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            if sys.platform.startswith('win') else 0)
        if r.returncode != 0:
            return False
        m = re.search('\\((\\d+),\\s*(\\d+)\\)', r.stdout or '')
        if not m:
            return False
        mayor, menor = int(m.group(1)), int(m.group(2))
        return (mayor, menor) >= (3, 6)
    except Exception:
        return False
def _python_del_sistema():
    """Version legible del Python disponible, para el diagnostico.\n\n    Ya no es un requisito duro: en Free ahora se usan los scripts .lua, que\n    Resolve corre con su Lua incorporado sin necesitar nada instalado. Esta\n    linea queda solo como dato: si hay Python, los .py del menu tambien\n    andan; si no, no pasa nada porque estan los .lua.\n    """
    ruta = python_para_resolve()
    if ruta is None:
        return 'no hay (no hace falta: en Free se usan los scripts .lua, que Resolve corre con su Lua incorporado)'
    else:
        try:
            r = subprocess.run([str(ruta), '--version'], capture_output=True, text=True, timeout=6, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform.startswith('win') else 0)
            version = (r.stdout or r.stderr or '').strip()
        except Exception:
            version = '(no pude preguntarle la versión)'
        return f'{version}  ({ruta})'
def informe_scripts_resolve():
    """Texto legible del estado de cada carpeta de scripts.\n\n    Es lo primero que hay que mirar cuando el menu de Resolve no muestra\n    los scripts, asi que va al diagnostico y a los avisos de error.\n    """
    nuestros = sorted((a.name for a in _nuestros_scripts()))
    edicion = edicion_de_resolve()
    lineas = [f'Edición de Resolve   : {DESCRIPCION_EDICION.get(edicion, edicion)}', f"Resolve abierto ahora: {('sí' if resolve_esta_corriendo() else 'no')}", f'Python para Resolve  : {_python_del_sistema()}']
    if edicion == 'studio':
        lineas.append('  (Studio no usa el menú: los scripts corren por la API)')
    viejos = scripts_desactualizados()
    if viejos:
        lineas.append('OJO: hay scripts DESACTUALIZADOS en Resolve (no son los que trae este programa):')
        if problema_mac_app_store():
            lineas.append('      ^ es el Resolve de la Mac App Store: corre aislado y macOS no deja actualizarlos. Hay que instalar Resolve desde la web de Blackmagic.')
        for nombre, carpeta in viejos:
            lineas.append(f'      {nombre}  en  {carpeta}')
    else:
        lineas.append('Scripts en Resolve   : al día')
    for carpeta in carpetas_scripts_resolve():
        lineas.append(f'  {carpeta}')
        if not carpeta.is_dir():
            lineas.append('      no existe')
            continue
        else:
            puestos = sum((1 for n in nuestros if (carpeta / n).exists()))
            escribible = os.access(carpeta, os.W_OK)
            lineas.append(f"      {puestos} de {len(nuestros)} scripts  |  escribible: {('sí' if escribible else 'no')}")
    return '\n'.join(lineas)
