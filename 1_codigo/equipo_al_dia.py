# CineCaptions · By Cinema Productions
# 1_codigo/equipo_al_dia.py — pone el equipo al día para CineCaptions (lo llama la tarea «equipo» del instalador).
"""
v5.72 (pedido del usuario: «que el .exe actualice el PC: dependencias y drivers, sin ventanas de CMD ni interrumpir; dejar el entorno
optimizado para evitar errores de compatibilidad»).

Qué hace, en este orden, siempre con las ventanas ocultas (CREATE_NO_WINDOW / SW_HIDE):
1. Sin permisos de administrador: la GPU de alto rendimiento para CineCaptions y sus motores en los equipos con dos tarjetas (la
   preferencia «Gráficos» de Windows, por usuario; sin ella un portátil corre la IA en la gráfica integrada). No pisa lo que el usuario
   ya eligió.
2. Lo que pide administrador, en UN solo proceso elevado (`--tarea equipo_admin`: una sola ventana de permiso de Windows, que NO se
   puede esconder: es la protección de Windows), y solo si hace falta:
   - Microsoft Visual C++ 2015-2022 x64 si falta o es anterior a 14.40 (con winget si está; si no, el instalador oficial de Microsoft
     de aka.ms, comprobando su firma);
   - el driver de la GPU desde Windows Update (lo oficial: drivers firmados que Microsoft da para esa tarjeta) si el de NVIDIA es
     anterior a 595. Solo con DaVinci Resolve CERRADO (instalar un driver reinicia la imagen y tumbaría Resolve) y sin reiniciar.
   En la instalación silenciosa (las actualizaciones automáticas) NO se pide permiso: lo pendiente queda en la ficha y en el Registro,
   y se hace en la próxima instalación con ventana.
Lo que no se pudo queda en `pendiente`/`fallos` de la ficha (la app Ventas lo ve por equipo).

Reglas: nada de PowerShell ni cmd (el antivirus los bloquea); los programas de terceros se bajan SOLO de Microsoft; nunca se actualizan
otros programas del usuario.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import ficha_equipo

SIN_VENTANA = 0x08000000 if sys.platform.startswith('win') else 0     # CREATE_NO_WINDOW
WINGET_VCREDIST = 'Microsoft.VCRedist.2015+.x64'
URL_VCREDIST = 'https://aka.ms/vs/17/release/vc_redist.x64.exe'
TIMEOUT_ADMIN_S = 45 * 60          # bajar e instalar un driver de ~800 MB
TIMEOUT_BUSQUEDA_S = 6 * 60        # buscar en Windows Update (normalmente 20-90 s)
_PREFERENCIAS_GPU = r'Software\Microsoft\DirectX\UserGpuPreferences'


def _ahora():
    return ficha_equipo._ahora_iso()


# ---------------------------------------------------------------------------------------------------------------------------------------
# 1. GPU de alto rendimiento (sin administrador)
# ---------------------------------------------------------------------------------------------------------------------------------------
def _ejecutables():
    """CineCaptions.exe y el Python de cada motor (solo el programa instalado: desde el código no se toca nada)."""
    if not getattr(sys, 'frozen', False):
        return []
    exes = [Path(sys.executable)]
    for modulo in ('motor_voz', 'motor_compat'):
        try:
            exes.append(Path(__import__(modulo).python_motor()))
        except Exception:
            pass
    return [p for p in exes if p.is_file()]


def gpu_preferida(ficha, exes=None):
    """Con dos o más GPU, «alto rendimiento» (GpuPreference=2) para cada ejecutable que no tenga ya una preferencia. Devuelve los
    nombres de los que se pusieron."""
    if not sys.platform.startswith('win') or len(ficha.get('gpus') or []) < 2:
        return []
    import winreg
    puestos = []
    exes = _ejecutables() if exes is None else exes
    if not exes:
        return []
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _PREFERENCIAS_GPU, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
        for exe in exes:
            nombre = str(exe)
            try:
                winreg.QueryValueEx(k, nombre)
                continue                                  # ya tiene una (suya o de una instalación anterior): se respeta
            except OSError:
                pass
            winreg.SetValueEx(k, nombre, 0, winreg.REG_SZ, 'GpuPreference=2;')
            puestos.append(Path(nombre).name)
    return puestos


# ---------------------------------------------------------------------------------------------------------------------------------------
# 2a. Windows Update: el driver de la GPU
# ---------------------------------------------------------------------------------------------------------------------------------------
def _sesion_wu():
    import comtypes
    import comtypes.client
    try:
        comtypes.CoInitialize()
    except OSError:
        pass
    s = comtypes.client.CreateObject('Microsoft.Update.Session', dynamic=True)
    try:
        s.ClientApplicationID = 'CineCaptions'
    except Exception:
        pass
    return s


def _atributo(obj, nombre, defecto=''):
    try:
        valor = getattr(obj, nombre)
        return valor if defecto is None else str(valor or '')
    except Exception:
        return defecto


def _version_en_titulo(texto):
    m = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,5}\.\d{1,5})\b', str(texto or ''))
    return m.group(1) if m else ''


def _fecha_iso(valor):
    try:
        return valor.strftime('%Y-%m-%d')
    except Exception:
        return str(valor or '')[:10]


def buscar_driver(gpu, buscar=None):
    """El driver más nuevo que Windows Update ofrece para esta GPU y que sea MÁS nuevo que el instalado: {id, titulo, version, driver,
    fecha} o None. Solo busca (no hace falta ser administrador). `buscar` (pruebas): función que devuelve la lista de candidatos."""
    fab = (gpu.get('fabricante') or '').upper()
    if not fab:
        return None
    if buscar is None:
        def buscar():
            s = _sesion_wu()
            r = s.CreateUpdateSearcher().Search("IsInstalled=0 and Type='Driver' and IsHidden=0")
            salida = []
            for i in range(r.Updates.Count):
                u = r.Updates.Item(i)
                try:
                    titulo = str(u.Title)
                    salida.append({'id': str(u.Identity.UpdateID), 'titulo': titulo,
                                   # (las propiedades de driver, por si el objeto no las diera: el título es «NVIDIA - Display - 32.0…»)
                                   'clase': _atributo(u, 'DriverClass') or ('Display' if ' - display - ' in titulo.lower() else ''),
                                   'fabricante': _atributo(u, 'DriverManufacturer') or titulo.split(' - ')[0],
                                   'modelo': _atributo(u, 'DriverModel'), 'fecha': _fecha_iso(_atributo(u, 'DriverVerDate', None))})
                except Exception:
                    continue
            return salida
    actual = gpu.get('driver_windows') or ''
    mejor = None

    def tupla(v):
        return ficha_equipo._version_tupla(v, partes=4)
    for c in buscar() or []:
        if c.get('clase', '').lower() != 'display':
            continue
        if fab not in (c.get('fabricante', '') + ' ' + c.get('titulo', '')).upper().replace('ADVANCED MICRO DEVICES', 'AMD'):
            continue
        version = _version_en_titulo(c.get('titulo')) or _version_en_titulo(c.get('modelo'))
        if actual and version and tupla(version) <= tupla(actual):
            continue
        if actual and not version and c.get('fecha', '') <= (gpu.get('driver_fecha') or ''):
            continue
        if mejor is None or tupla(version) > tupla(mejor['version']):
            mejor = dict(c, version=version, driver=ficha_equipo._driver_nvidia(version) if fab == 'NVIDIA' else version)
    return mejor


def instalar_driver(id_update):
    """(ok, texto). En el proceso elevado: baja e instala ESE driver de Windows Update, sin reiniciar."""
    import comtypes.client
    s = _sesion_wu()
    r = s.CreateUpdateSearcher().Search(f"IsInstalled=0 and Type='Driver' and UpdateID='{id_update}'")
    if not r.Updates.Count:
        return False, 'Windows Update ya no lo ofrece'
    coleccion = comtypes.client.CreateObject('Microsoft.Update.UpdateColl', dynamic=True)
    u = r.Updates.Item(0)
    try:
        if not u.EulaAccepted:
            u.AcceptEula()
    except Exception:
        pass
    coleccion.Add(u)
    bajada = s.CreateUpdateDownloader()
    bajada.Updates = coleccion
    rb = bajada.Download()
    if int(rb.ResultCode) not in (2, 3):
        return False, f'no se pudo descargar (código {int(rb.ResultCode)})'
    instalador = s.CreateUpdateInstaller()
    instalador.Updates = coleccion
    try:
        instalador.ForceQuiet = True
    except Exception:
        pass
    ri = instalador.Install()
    codigo = int(ri.ResultCode)
    if codigo in (2, 3):
        return True, 'instalado' + (' (pide reiniciar para terminar)' if bool(ri.RebootRequired) else '')
    return False, f'Windows Update no pudo instalarlo (código {codigo})'


# ---------------------------------------------------------------------------------------------------------------------------------------
# 2b. Visual C++
# ---------------------------------------------------------------------------------------------------------------------------------------
def _vcredist_ok():
    v = ficha_equipo._version_tupla(ficha_equipo.vcredist_x64())
    return bool(v) and v[:2] >= ficha_equipo.VCREDIST_MINIMO


def _firma_valida(ruta):
    """WinVerifyTrust: ¿el .exe lleva una firma Authenticode válida y de confianza? (sin PowerShell)."""
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [('a', ctypes.c_uint32), ('b', ctypes.c_uint16), ('c', ctypes.c_uint16), ('d', ctypes.c_ubyte * 8)]

    class FILE_INFO(ctypes.Structure):
        _fields_ = [('cbStruct', wintypes.DWORD), ('pcwszFilePath', wintypes.LPCWSTR), ('hFile', wintypes.HANDLE),
                    ('pgKnownSubject', ctypes.c_void_p)]

    class TRUST_DATA(ctypes.Structure):
        _fields_ = [('cbStruct', wintypes.DWORD), ('pPolicyCallbackData', ctypes.c_void_p), ('pSIPClientData', ctypes.c_void_p),
                    ('dwUIChoice', wintypes.DWORD), ('fdwRevocationChecks', wintypes.DWORD), ('dwUnionChoice', wintypes.DWORD),
                    ('pFile', ctypes.POINTER(FILE_INFO)), ('dwStateAction', wintypes.DWORD), ('hWVTStateData', wintypes.HANDLE),
                    ('pwszURLReference', wintypes.LPCWSTR), ('dwProvFlags', wintypes.DWORD), ('dwUIContext', wintypes.DWORD),
                    ('pSignatureSettings', ctypes.c_void_p)]
    # WINTRUST_ACTION_GENERIC_VERIFY_V2 {00AAC56B-CD44-11d0-8CC2-00C04FC295EE}
    accion = GUID(0x00AAC56B, 0xCD44, 0x11d0, (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE))
    archivo = FILE_INFO(ctypes.sizeof(FILE_INFO), str(ruta), None, None)
    datos = TRUST_DATA()
    datos.cbStruct = ctypes.sizeof(TRUST_DATA)
    datos.dwUIChoice = 2                    # WTD_UI_NONE
    datos.dwUnionChoice = 1                 # WTD_CHOICE_FILE
    datos.pFile = ctypes.pointer(archivo)
    datos.dwStateAction = 1                 # WTD_STATEACTION_VERIFY
    wt = ctypes.WinDLL('wintrust')
    wt.WinVerifyTrust.argtypes = [wintypes.HWND, ctypes.POINTER(GUID), ctypes.c_void_p]
    wt.WinVerifyTrust.restype = ctypes.c_long
    r = wt.WinVerifyTrust(None, ctypes.byref(accion), ctypes.byref(datos))
    datos.dwStateAction = 2                 # WTD_STATEACTION_CLOSE
    wt.WinVerifyTrust(None, ctypes.byref(accion), ctypes.byref(datos))
    return r == 0


def instalar_vcredist(info=None):
    """(ok, texto). En el proceso elevado. winget primero (verifica el paquete); si no hay winget o no funcionó, el instalador oficial."""
    exe_winget = ficha_equipo.winget()
    if exe_winget:
        orden = 'upgrade' if ficha_equipo.vcredist_x64() else 'install'
        try:
            subprocess.run([exe_winget, orden, '--id', WINGET_VCREDIST, '-e', '--silent', '--accept-package-agreements',
                            '--accept-source-agreements', '--disable-interactivity'], capture_output=True, timeout=15 * 60,
                           creationflags=SIN_VENTANA)
        except Exception as e:
            if info:
                info(f'winget no respondió ({type(e).__name__}); uso el instalador de Microsoft')
        if _vcredist_ok():
            return True, f'Visual C++ {ficha_equipo.vcredist_x64()} instalado (winget)'
    import tempfile
    import urllib.request
    destino = Path(tempfile.gettempdir()) / f'cinecaptions_vc_redist_{os.getpid()}.x64.exe'
    try:
        try:
            import licencia
            contexto = licencia._ssl()
        except Exception:
            contexto = None
        with urllib.request.urlopen(URL_VCREDIST, timeout=60, context=contexto) as r, open(destino, 'wb') as f:
            while True:
                bloque = r.read(1 << 20)
                if not bloque:
                    break
                f.write(bloque)
        if not _firma_valida(destino):
            return False, 'el instalador de Visual C++ descargado no tiene una firma válida (no lo ejecuto)'
        p = subprocess.run([str(destino), '/install', '/quiet', '/norestart'], capture_output=True, timeout=15 * 60, creationflags=SIN_VENTANA)
        if _vcredist_ok() or p.returncode in (0, 1638, 3010):
            return True, f'Visual C++ {ficha_equipo.vcredist_x64() or ""} instalado'.replace('  ', ' ') + (' (pide reiniciar)' if p.returncode == 3010 else '')
        return False, f'el instalador de Visual C++ terminó con el código {p.returncode}'
    finally:
        try:
            destino.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------------------------------------------------------------------
# el proceso elevado
# ---------------------------------------------------------------------------------------------------------------------------------------
def es_administrador():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ejecutar_admin(plan, info=None):
    """Lo que necesita administrador (ya elevado). plan = {'vcredist': bool, 'driver': {id, titulo, ...}}. → {hecho, fallos}."""
    hecho, fallos = [], []
    if plan.get('vcredist'):
        try:
            ok, texto = instalar_vcredist(info)
        except Exception as e:
            ok, texto = False, f'{type(e).__name__}: {e}'
        (hecho if ok else fallos).append(texto if ok else 'Visual C++: ' + texto)
    d = plan.get('driver')
    if d:
        if resolve_abierto():
            fallos.append('Driver de la GPU: DaVinci Resolve se abrió mientras tanto; lo instalo la próxima vez')
        else:
            try:
                ok, texto = instalar_driver(d['id'])
            except Exception as e:
                ok, texto = False, f'{type(e).__name__}: {e}'
            nombre = f"Driver {d.get('driver') or d.get('version') or ''} de la GPU".replace('  ', ' ')
            (hecho if ok else fallos).append(f'{nombre}: {texto}')
    return {'hecho': hecho, 'fallos': fallos}


def _lanzar_elevado(argumentos, timeout_s):
    """Corre CineCaptions.exe con `argumentos` como administrador (ShellExecuteEx «runas», ventana oculta) y espera. (código de
    salida o None, 'cancelado'|'') — 'cancelado' si el usuario dijo que no en la ventana de permiso."""
    import ctypes
    from ctypes import wintypes

    class SEI(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('fMask', ctypes.c_ulong), ('hwnd', wintypes.HWND), ('lpVerb', wintypes.LPCWSTR),
                    ('lpFile', wintypes.LPCWSTR), ('lpParameters', wintypes.LPCWSTR), ('lpDirectory', wintypes.LPCWSTR),
                    ('nShow', ctypes.c_int), ('hInstApp', wintypes.HINSTANCE), ('lpIDList', ctypes.c_void_p),
                    ('lpClass', wintypes.LPCWSTR), ('hkeyClass', wintypes.HKEY), ('dwHotKey', wintypes.DWORD),
                    ('hIconOrMonitor', wintypes.HANDLE), ('hProcess', wintypes.HANDLE)]
    sei = SEI()
    sei.cbSize = ctypes.sizeof(SEI)
    sei.fMask = 0x00000040 | 0x00000400      # SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_NO_UI
    sei.hwnd = ctypes.windll.user32.GetForegroundWindow()   # el instalador: así la ventana de permiso sale delante y no parpadeando abajo
    sei.lpVerb = 'runas'
    sei.lpFile = sys.executable
    sei.lpParameters = subprocess.list2cmdline(argumentos)
    sei.lpDirectory = str(Path(sys.executable).parent)
    sei.nShow = 0                            # SW_HIDE
    shell32, k32 = ctypes.windll.shell32, ctypes.windll.kernel32
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SEI)]
    if not shell32.ShellExecuteExW(ctypes.byref(sei)):
        return None, 'cancelado' if ctypes.GetLastError() == 1223 else f'error {ctypes.GetLastError()}'
    try:
        k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        if k32.WaitForSingleObject(sei.hProcess, int(timeout_s * 1000)) != 0:
            k32.TerminateProcess(sei.hProcess, 1)
            return None, 'tiempo'
        codigo = wintypes.DWORD()
        k32.GetExitCodeProcess(sei.hProcess, ctypes.byref(codigo))
        return int(codigo.value), ''
    finally:
        k32.CloseHandle(sei.hProcess)


def resolve_abierto():
    try:
        import motor_voz
        return bool(motor_voz.resolve_abierto())
    except Exception:
        return False


# ---------------------------------------------------------------------------------------------------------------------------------------
# el plan completo (tarea «equipo» del instalador)
# ---------------------------------------------------------------------------------------------------------------------------------------
def poner_al_dia(ficha, interactivo=True, info=None, progreso=None, simular=None, elevar=None):
    """Pone el equipo al día y devuelve «puesta_al_dia» para la ficha: {cuando, hecho, pendiente, fallos}.
    `simular` (pruebas): dict con lo que devolverían las partes que tocan el sistema ('gpu_preferida', 'buscar', 'admin').
    `elevar` (pruebas): función(plan) → {hecho, fallos} en vez de lanzar el proceso elevado."""
    info = info or (lambda _t: None)
    progreso = progreso or (lambda _p, _t='': None)
    hecho, pendiente, fallos = [], [], []
    simular = simular or {}
    win = sys.platform.startswith('win')

    # 1) GPU de alto rendimiento
    if win:
        try:
            puestos = simular['gpu_preferida'] if 'gpu_preferida' in simular else gpu_preferida(ficha)
            if puestos:
                hecho.append('GPU de alto rendimiento para ' + ', '.join(puestos))
        except Exception as e:
            fallos.append(f'GPU de alto rendimiento: {type(e).__name__}: {e}')

    # 2) lo que pide administrador
    plan = {}
    revision = {r['id']: r for r in ficha.get('revision') or []}
    if win and revision.get('vcredist', {}).get('estado') == 'falta':
        plan['vcredist'] = True
    g = ficha_equipo._nvidia(ficha)
    if win and g and 0 < ficha_equipo.version_nvidia(ficha) < ficha_equipo.NVIDIA_RAPIDO:
        progreso(30, 'Buscando un driver más nuevo para ' + g['nombre'] + ' en Windows Update')
        candidato, tardo = None, False
        if 'buscar' in simular or not simular:
            # en un hilo con tope: un Windows Update lento no deja la instalación esperando (el hilo es daemon; si se pasa, se abandona)
            res = {}

            def _buscar():
                try:
                    res['c'] = buscar_driver(g, buscar=simular.get('buscar'))
                except Exception as e:
                    res['e'] = e
            h = __import__('threading').Thread(target=_buscar, daemon=True, name='buscar-driver')
            h.start()
            h.join(simular.get('tope_busqueda', TIMEOUT_BUSQUEDA_S))
            tardo = h.is_alive()
            candidato = res.get('c')
            if tardo:
                pendiente.append(f'Driver de la GPU: Windows Update tardó más de {TIMEOUT_BUSQUEDA_S // 60} minutos en contestar; se busca en la próxima instalación')
            elif 'e' in res:
                fallos.append(f"Windows Update no respondió al buscar el driver ({type(res['e']).__name__})")
        if tardo or (candidato is None and fallos and fallos[-1].startswith('Windows Update')):
            pass
        elif candidato:
            if resolve_abierto() and not simular.get('resolve_cerrado'):
                pendiente.append(f"Driver NVIDIA {candidato.get('driver')}: DaVinci Resolve está abierto (instalarlo lo cerraría); "
                                 'se instala en la próxima instalación con Resolve cerrado')
            else:
                plan['driver'] = candidato
        else:
            pendiente.append(f"Driver NVIDIA {g.get('driver')}: Windows Update no tiene uno más nuevo para esta tarjeta (con la app de "
                             f"NVIDIA se puede poner el {ficha_equipo.NVIDIA_RAPIDO} o más)")
    if plan:
        que = ' y '.join((['Visual C++'] if plan.get('vcredist') else []) + (['el driver de la GPU'] if plan.get('driver') else []))
        if not interactivo:
            pendiente.append(f'{que[0].upper() + que[1:]}: se instala en la próxima instalación (pide permiso de administrador)')
        else:
            progreso(55, f'Instalando {que}')
            info(f'Instalando {que} (Windows pide permiso una vez)')
            try:
                if elevar is not None:
                    res = elevar(plan)
                elif 'admin' in simular:
                    res = simular['admin']
                elif es_administrador():
                    res = ejecutar_admin(plan, info)
                else:
                    res = _elevar(plan)
            except Exception as e:
                res = {'hecho': [], 'fallos': [f'{type(e).__name__}: {e}']}
            hecho += res.get('hecho', [])
            fallos += res.get('fallos', [])
            pendiente += res.get('pendiente', [])
    progreso(100, '')
    return {'cuando': _ahora(), 'hecho': hecho, 'pendiente': pendiente, 'fallos': fallos}


def _elevar(plan):
    """Lanza `CineCaptions.exe --tarea equipo_admin <estado> <plan> <salida>` elevado y lee su resultado."""
    if not getattr(sys, 'frozen', False):
        return {'hecho': [], 'fallos': [], 'pendiente': ['Desde el código fuente no se instala nada del sistema']}
    import tempfile
    base = Path(tempfile.gettempdir()) / f'cinecaptions_equipo_{os.getpid()}'
    archivos = {k: base.with_name(base.name + f'_{k}.' + ('txt' if k == 'estado' else 'json')) for k in ('estado', 'plan', 'salida')}
    archivos['plan'].write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
    try:
        codigo, motivo = _lanzar_elevado(['--tarea', 'equipo_admin', str(archivos['estado']), str(archivos['plan']), str(archivos['salida'])],
                                         TIMEOUT_ADMIN_S)
        if motivo == 'cancelado':
            return {'hecho': [], 'fallos': [], 'pendiente': ['No se dio el permiso de administrador: se intenta en la próxima instalación']}
        try:
            return json.loads(archivos['salida'].read_text(encoding='utf-8'))
        except Exception:
            return {'hecho': [], 'fallos': [f'El proceso de administrador no terminó bien ({motivo or "código " + str(codigo)})']}
    finally:
        for p in archivos.values():
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
