# CineCaptions · By Cinema Productions
# 1_codigo/ficha_equipo.py — la ficha técnica del equipo (sistema, CPU, RAM, GPU con su driver, pantallas, discos, Resolve, motores).
"""
v5.72 (pedido del usuario: «telemetría avanzada: la información del hardware del usuario y verificar si se requieren controladores
adicionales»; «que la app CineCaptions Ventas reciba la telemetría con más información del equipo»).

`recoger()` arma un dict (esquema v1, ver DOCUMENTACION/temas/datos.md «Ficha del equipo») y `revisar()` dice qué le falta al equipo para
CineCaptions (driver de la GPU, Visual C++, RAM, disco, Windows, Resolve). Lo usan:
- la tarea `equipo` del instalador (`tareas_instalador`), que además lo pone al día (`equipo_al_dia`) y guarda la ficha en ARCHIVO;
- la telemetría (`telemetria_errores`): la línea corta de cada error (`resumen`) y la ficha entera a `pagos/equipo.php` (una vez al día
  o cuando cambia), que la app «CineCaptions Ventas» muestra por equipo.

Reglas: sin subprocess en Windows (registro, DXGI y la API de Windows por ctypes: nada de ventanas de consola ni PowerShell, que el
antivirus bloquea) y nunca en el hilo de la interfaz (lee el registro y el disco). Nada personal: ni el nombre del equipo ni del usuario
ni rutas suyas (los discos van por letra y uso).
"""
import json
import os
import platform
import sys
import time
from pathlib import Path

import registro

VERSION_FICHA = 1
ARCHIVO = registro.CARPETA / 'ficha_equipo.json'      # la última ficha completa (la del instalador lleva «puesta_al_dia»)
# driver NVIDIA: la voz (torch) elige CUDA según el driver (motor_voz): ≥ 595 → CUDA 13.2 (lo más rápido); < 528 la GPU no sirve
NVIDIA_RAPIDO = 595
NVIDIA_MINIMO = 528
VCREDIST_MINIMO = (14, 40)       # torch/onnxruntime compilados con VS 17.10+: con un msvcp140 anterior se caen en std::mutex
RAM_MINIMA_MB, RAM_BUENA_MB = 7_500, 15_500
DISCO_MINIMO_GB, DISCO_BUENO_GB = 10, 30
WINDOWS_BUILD_MINIMO = 19041     # Windows 10 2004
_GPU_CLASE = r'SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
_NO_GPU = ('basic display', 'basic render', 'remote', 'parsec', 'virtual', 'citrix', 'vmware', 'hyper-v', 'idd', 'spacedesk')


def _es_windows():
    return sys.platform.startswith('win')


# ---------------------------------------------------------------------------------------------------------------------------------------
# Windows: registro y API
# ---------------------------------------------------------------------------------------------------------------------------------------
def _reg(raiz, ruta, nombre, vista64=True):
    import winreg
    try:
        acceso = winreg.KEY_READ | (winreg.KEY_WOW64_64KEY if vista64 else 0)
        with winreg.OpenKey(raiz, ruta, 0, acceso) as k:
            return winreg.QueryValueEx(k, nombre)[0]
    except OSError:
        return None


def _so():
    if _es_windows():
        import winreg
        ruta = r'SOFTWARE\Microsoft\Windows NT\CurrentVersion'
        build = str(_reg(winreg.HKEY_LOCAL_MACHINE, ruta, 'CurrentBuildNumber') or '')
        ubr = _reg(winreg.HKEY_LOCAL_MACHINE, ruta, 'UBR')
        nombre = str(_reg(winreg.HKEY_LOCAL_MACHINE, ruta, 'ProductName') or 'Windows')
        if build.isdigit() and int(build) >= 22000:
            nombre = nombre.replace('Windows 10', 'Windows 11')       # el registro sigue diciendo «Windows 10» en Windows 11
        return {'nombre': nombre, 'version': str(_reg(winreg.HKEY_LOCAL_MACHINE, ruta, 'DisplayVersion') or ''),
                'build': build + (f'.{ubr}' if ubr is not None else ''), 'arquitectura': _arquitectura()}
    if sys.platform == 'darwin':
        return {'nombre': 'macOS', 'version': platform.mac_ver()[0], 'arquitectura': _arquitectura()}
    return {'nombre': platform.system(), 'version': platform.release(), 'arquitectura': _arquitectura()}


def _arquitectura():
    m = platform.machine().lower()
    return {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(m, m)


def _cpu():
    datos = {'hilos': os.cpu_count() or 0}
    try:
        if _es_windows():
            import ctypes
            import winreg
            datos['nombre'] = ' '.join(str(_reg(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0',
                                                'ProcessorNameString') or '').split())
            k32 = ctypes.windll.kernel32
            datos['avx2'] = bool(k32.IsProcessorFeaturePresent(40))       # PF_AVX2_INSTRUCTIONS_AVAILABLE
        elif sys.platform == 'darwin':
            import subprocess
            datos['nombre'] = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], capture_output=True, text=True,
                                             timeout=3).stdout.strip()
    except Exception:
        pass
    return datos


def _ram():
    try:
        import telemetria_errores
        total, libre = telemetria_errores._ram_mb()
        if total:
            return {'total_mb': total, 'libre_mb': libre}
    except Exception:
        pass
    return {}


def _driver_nvidia(version_windows):
    """«32.0.15.9636» (el driver como lo guarda Windows) → «596.36» (como lo llama NVIDIA): las 5 últimas cifras de los dos últimos
    campos. '' si no tiene esa forma."""
    partes = str(version_windows or '').split('.')
    if len(partes) != 4 or not all(p.isdigit() for p in partes[2:]):
        return ''
    cifras = (partes[2] + partes[3].zfill(4))[-5:]
    return f'{int(cifras[:3])}.{cifras[3:]}'


def _fecha_driver(texto):
    """«10-1-2026» (mes-día-año) → «2026-10-01»."""
    try:
        m, d, a = (int(x) for x in str(texto).split('-'))
        return f'{a:04d}-{m:02d}-{d:02d}'
    except Exception:
        return ''


def _fabricante(nombre, proveedor=''):
    t = f'{nombre} {proveedor}'.lower()
    if 'nvidia' in t:
        return 'NVIDIA'
    if 'amd' in t or 'radeon' in t or 'advanced micro' in t or 'ati ' in t:
        return 'AMD'
    if 'intel' in t:
        return 'Intel'
    if 'qualcomm' in t or 'adreno' in t:
        return 'Qualcomm'
    return proveedor or ''


def _adaptadores_dxgi():
    """[(descripción, vendor_id, VRAM en MB)] de las GPU de verdad (sin el adaptador por software), con DXGI por ctypes (lo que ve
    DirectX: cuenta también la NVIDIA de un portátil que no da imagen, que EnumDisplayDevices no lista). [] si no se puede."""
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [('a', ctypes.c_uint32), ('b', ctypes.c_uint16), ('c', ctypes.c_uint16), ('d', ctypes.c_ubyte * 8)]

    class LUID(ctypes.Structure):
        _fields_ = [('LowPart', wintypes.DWORD), ('HighPart', wintypes.LONG)]

    class DESC1(ctypes.Structure):
        _fields_ = [('Description', wintypes.WCHAR * 128), ('VendorId', ctypes.c_uint), ('DeviceId', ctypes.c_uint),
                    ('SubSysId', ctypes.c_uint), ('Revision', ctypes.c_uint), ('DedicatedVideoMemory', ctypes.c_size_t),
                    ('DedicatedSystemMemory', ctypes.c_size_t), ('SharedSystemMemory', ctypes.c_size_t), ('AdapterLuid', LUID),
                    ('Flags', ctypes.c_uint)]

    # IID_IDXGIFactory1 {770aae78-f26f-4dba-a829-253c83d1b387}
    iid = GUID(0x770aae78, 0xf26f, 0x4dba, (ctypes.c_ubyte * 8)(0xa8, 0x29, 0x25, 0x3c, 0x83, 0xd1, 0xb3, 0x87))
    fabrica = ctypes.c_void_p()
    if ctypes.WinDLL('dxgi').CreateDXGIFactory1(ctypes.byref(iid), ctypes.byref(fabrica)) != 0 or not fabrica.value:
        return []

    def metodo(obj, indice, *tipos):
        vtabla = ctypes.cast(ctypes.cast(obj, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *tipos)(vtabla[indice])

    salida = []
    try:
        for i in range(16):
            adaptador = ctypes.c_void_p()
            # IDXGIFactory1::EnumAdapters1 = 12 (IUnknown 3 + IDXGIObject 4 + IDXGIFactory 5)
            if metodo(fabrica, 12, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(fabrica, i, ctypes.byref(adaptador)) != 0:
                break                                            # DXGI_ERROR_NOT_FOUND: no hay más
            try:
                d = DESC1()
                # IDXGIAdapter1::GetDesc1 = 10 (IUnknown 3 + IDXGIObject 4 + IDXGIAdapter 3)
                if metodo(adaptador, 10, ctypes.POINTER(DESC1))(adaptador, ctypes.byref(d)) == 0 and not (d.Flags & 2):
                    salida.append((' '.join(d.Description.split()), d.VendorId, int(d.DedicatedVideoMemory // 1048576)))
            finally:
                metodo(adaptador, 2)(adaptador)                   # Release
    finally:
        metodo(fabrica, 2)(fabrica)
    return salida


def _drivers_registro():
    """{nombre del adaptador: {driver_windows, fecha, proveedor, vram_mb}} de la clase «Display» del registro."""
    import winreg
    salida = {}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _GPU_CLASE, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as clase:
            for i in range(64):
                try:
                    sub = winreg.EnumKey(clase, i)
                except OSError:
                    break
                if not sub.isdigit():
                    continue
                try:
                    with winreg.OpenKey(clase, sub) as k:
                        def v(n):
                            try:
                                return winreg.QueryValueEx(k, n)[0]
                            except OSError:
                                return None
                        nombre = ' '.join(str(v('DriverDesc') or '').split())
                        if not nombre:
                            continue
                        vram = v('HardwareInformation.qwMemorySize')
                        if vram is None:
                            crudo = v('HardwareInformation.MemorySize')
                            vram = int.from_bytes(crudo[:8], 'little') if isinstance(crudo, (bytes, bytearray)) else crudo
                        salida.setdefault(nombre, {'driver_windows': str(v('DriverVersion') or ''), 'fecha': _fecha_driver(v('DriverDate')),
                                                   'proveedor': str(v('ProviderName') or ''),
                                                   'vram_mb': int(vram) // 1048576 if isinstance(vram, int) and vram > 0 else 0})
                except OSError:
                    continue
    except OSError:
        pass
    return salida


def _gpus():
    if not _es_windows():
        return _gpus_mac() if sys.platform == 'darwin' else []
    try:
        import telemetria_errores
        principales = telemetria_errores._gpus_windows()      # (la que da imagen, primero)
    except Exception:
        principales = []
    drivers = {}
    try:
        drivers = _drivers_registro()
    except Exception:
        pass
    try:
        adaptadores = _adaptadores_dxgi()
    except Exception:
        adaptadores = []
    if not adaptadores:                                        # sin DXGI: lo que diga el registro, filtrado por lo que da imagen
        adaptadores = [(n, 0, d.get('vram_mb', 0)) for n, d in drivers.items() if not principales or n in principales]
    vistos, gpus = set(), []
    for nombre, vendor, vram in adaptadores:
        if not nombre or nombre in vistos or any(x in nombre.lower() for x in _NO_GPU):
            continue
        vistos.add(nombre)
        d = drivers.get(nombre, {})
        fab = _fabricante(nombre, d.get('proveedor', '')) or {0x10de: 'NVIDIA', 0x1002: 'AMD', 0x8086: 'Intel'}.get(vendor, '')
        g = {'nombre': nombre, 'fabricante': fab, 'vram_mb': vram or d.get('vram_mb', 0)}
        if d.get('driver_windows'):
            g['driver'] = _driver_nvidia(d['driver_windows']) if fab == 'NVIDIA' else d['driver_windows']
            g['driver_windows'] = d['driver_windows']
        if d.get('fecha'):
            g['driver_fecha'] = d['fecha']
        if principales and nombre == principales[0]:
            g['principal'] = True
        gpus.append(g)
    gpus.sort(key=lambda g: (not g.get('principal'), -(g.get('vram_mb') or 0)))
    return gpus


def _gpus_mac():
    try:
        import subprocess
        r = subprocess.run(['system_profiler', 'SPDisplaysDataType', '-json'], capture_output=True, text=True, timeout=12)
        datos = json.loads(r.stdout or '{}').get('SPDisplaysDataType') or []
        return [{'nombre': d.get('sppci_model') or d.get('_name') or '', 'fabricante': 'Apple' if 'apple' in str(d.get('sppci_vendor', '')).lower()
                 else str(d.get('sppci_vendor', '')).replace('sppci_vendor_', ''), 'vram_mb': 0} for d in datos]
    except Exception:
        return []


def _pantallas_windows():
    """Resolución REAL de cada pantalla activa (EnumDisplaySettings da los píxeles físicos aunque el proceso no sepa de escalas)."""
    import ctypes
    from ctypes import wintypes

    class DD(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('DeviceName', wintypes.WCHAR * 32), ('DeviceString', wintypes.WCHAR * 128),
                    ('StateFlags', wintypes.DWORD), ('DeviceID', wintypes.WCHAR * 128), ('DeviceKey', wintypes.WCHAR * 128)]

    class DEVMODE(ctypes.Structure):
        _fields_ = [('dmDeviceName', wintypes.WCHAR * 32), ('dmSpecVersion', wintypes.WORD), ('dmDriverVersion', wintypes.WORD),
                    ('dmSize', wintypes.WORD), ('dmDriverExtra', wintypes.WORD), ('dmFields', wintypes.DWORD),
                    ('dmPositionX', ctypes.c_long), ('dmPositionY', ctypes.c_long), ('dmDisplayOrientation', wintypes.DWORD),
                    ('dmDisplayFixedOutput', wintypes.DWORD), ('dmColor', ctypes.c_short), ('dmDuplex', ctypes.c_short),
                    ('dmYResolution', ctypes.c_short), ('dmTTOption', ctypes.c_short), ('dmCollate', ctypes.c_short),
                    ('dmFormName', wintypes.WCHAR * 32), ('dmLogPixels', wintypes.WORD), ('dmBitsPerPel', wintypes.DWORD),
                    ('dmPelsWidth', wintypes.DWORD), ('dmPelsHeight', wintypes.DWORD), ('dmDisplayFlags', wintypes.DWORD),
                    ('dmDisplayFrequency', wintypes.DWORD), ('rest', ctypes.c_byte * 64)]
    u32 = ctypes.windll.user32
    salida = []
    for i in range(16):
        d = DD()
        d.cb = ctypes.sizeof(DD)
        if not u32.EnumDisplayDevicesW(None, i, ctypes.byref(d), 0):
            break
        if not d.StateFlags & 1:                                      # DISPLAY_DEVICE_ATTACHED_TO_DESKTOP
            continue
        m = DEVMODE()
        m.dmSize = ctypes.sizeof(DEVMODE) - 64
        m.dmDriverExtra = 64
        if u32.EnumDisplaySettingsW(d.DeviceName, -1, ctypes.byref(m)):  # ENUM_CURRENT_SETTINGS
            p = {'ancho': int(m.dmPelsWidth), 'alto': int(m.dmPelsHeight), 'hz': int(m.dmDisplayFrequency)}
            if d.StateFlags & 4:
                p['principal'] = True
            salida.append(p)
    return salida


def _discos():
    import shutil
    usos = [('programa', Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent),
            ('datos', registro.CARPETA)]
    try:
        import motor_voz
        usos.append(('motores', motor_voz.carpeta()))
    except Exception:
        pass
    salida, vistos = [], set()
    for uso, ruta in usos:
        try:
            p = Path(ruta)
            while not p.exists() and p != p.parent:
                p = p.parent
            unidad = (p.drive or p.anchor or '/').rstrip('\\') or '/'
            if unidad in vistos:
                continue
            vistos.add(unidad)
            u = shutil.disk_usage(p)
            salida.append({'uso': uso, 'unidad': unidad, 'libre_gb': round(u.free / 1073741824, 1), 'total_gb': round(u.total / 1073741824, 1)})
        except Exception:
            continue
    return salida


def _resolve():
    """Edición y versión de DaVinci Resolve instalado (Windows: la entrada de «Aplicaciones instaladas»; Mac: el Info.plist)."""
    if _es_windows():
        import winreg
        mejor = None
        for raiz, ruta, vista in ((winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall', True),
                                  (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall', True),
                                  (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall', True)):
            try:
                with winreg.OpenKey(raiz, ruta, 0, winreg.KEY_READ | (winreg.KEY_WOW64_64KEY if vista else 0)) as k:
                    for i in range(4000):
                        try:
                            sub = winreg.EnumKey(k, i)
                        except OSError:
                            break
                        try:
                            with winreg.OpenKey(k, sub) as s:
                                nombre = str(winreg.QueryValueEx(s, 'DisplayName')[0])
                                if not nombre.startswith('DaVinci Resolve') or any(x in nombre for x in ('Panels', 'Project Server', 'Keyboard')):
                                    continue
                                try:
                                    version = str(winreg.QueryValueEx(s, 'DisplayVersion')[0])
                                except OSError:
                                    version = ''
                                if mejor is None or 'Studio' in nombre:
                                    mejor = {'instalado': True, 'edicion': 'Studio' if 'Studio' in nombre else 'Free', 'version': version}
                        except OSError:
                            continue
            except OSError:
                continue
        if mejor:
            # el instalador de Studio también se registra como «DaVinci Resolve»: manda la edición que el programa ya vio (la API externa
            # solo conecta en Studio), sin conectarse ahora
            try:
                import instalador_scripts
                vista = instalador_scripts._edicion_guardada()
                if vista:
                    mejor['edicion'] = 'Studio' if vista == 'studio' else 'Free'
                elif 'Studio' not in mejor.get('edicion', ''):
                    mejor['edicion'] = 'sin saber'
            except Exception:
                pass
        return mejor or {'instalado': False}
    if sys.platform == 'darwin':
        import plistlib
        for nombre, edicion in (('DaVinci Resolve Studio', 'Studio'), ('DaVinci Resolve', '')):
            info = Path('/Applications') / 'DaVinci Resolve' / f'{nombre}.app' / 'Contents' / 'Info.plist'
            try:
                with open(info, 'rb') as f:
                    p = plistlib.load(f)
                return {'instalado': True, 'edicion': edicion or ('Studio' if 'Studio' in str(p.get('CFBundleName', '')) else 'Free'),
                        'version': str(p.get('CFBundleShortVersionString') or p.get('CFBundleVersion') or '')}
            except Exception:
                continue
        return {'instalado': False}
    return {}


def _motores():
    salida = {}
    try:
        import motor_voz
        info = motor_voz.info_instalado()
        salida['voz'] = {'instalado': bool(info)}
        if info:
            for k in ('torch', 'cuda', 'modelo', 'modelo_texto'):
                if info.get(k):
                    salida['voz'][k] = info[k]
    except Exception:
        pass
    try:
        import motor_compat
        info = motor_compat.info_instalado()
        salida['auxiliar'] = {'instalado': bool(info)}
        if info and info.get('python'):
            salida['auxiliar']['python'] = info['python']
    except Exception:
        pass
    return salida


def vcredist_x64():
    """Versión del Visual C++ 2015-2022 x64 instalado («14.44.35211») o '' si no está."""
    if not _es_windows():
        return ''
    import winreg
    for ruta in (r'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', r'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64'):
        if _reg(winreg.HKEY_LOCAL_MACHINE, ruta, 'Installed') == 1:
            v = str(_reg(winreg.HKEY_LOCAL_MACHINE, ruta, 'Version') or '').lstrip('v')
            if v:
                return '.'.join(v.split('.')[:3])
    return ''


def winget():
    """Ruta de winget.exe o '' (no está en Windows recortados, LTSC ni en cuentas sin la Microsoft Store)."""
    if not _es_windows():
        return ''
    import shutil
    ruta = shutil.which('winget')
    if ruta:
        return ruta
    p = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'WindowsApps' / 'winget.exe'
    return str(p) if p.exists() else ''


def _version_tupla(texto, partes=3):
    try:
        return tuple(int(x) for x in str(texto).split('.')[:partes])
    except ValueError:
        return ()


# ---------------------------------------------------------------------------------------------------------------------------------------
# la ficha
# ---------------------------------------------------------------------------------------------------------------------------------------
def _ahora_iso(t=None):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t or time.time()))


def recoger(origen='app', pantallas=None):
    """La ficha del equipo (dict, esquema v1). `pantallas`: las de Qt si las hay (con la escala); si no, las de Windows. Tarda ~50-300 ms
    (registro + DXGI): llamarla fuera del hilo de la interfaz. Nunca lanza: lo que no se pueda leer, no va."""
    f = {'v': VERSION_FICHA, 'cuando': _ahora_iso(), 'origen': origen}
    partes = (('app', _app), ('so', _so), ('cpu', _cpu), ('ram', _ram), ('gpus', _gpus), ('discos', _discos), ('resolve', _resolve),
              ('motores', _motores), ('componentes', _componentes))
    for clave, fn in partes:
        try:
            valor = fn()
            if valor:
                f[clave] = valor
        except Exception:
            pass
    try:
        p = pantallas if pantallas else (_pantallas_windows() if _es_windows() else [])
        if p:
            f['pantallas'] = p
    except Exception:
        pass
    f['revision'] = revisar(f)
    previa = cargar()
    if previa.get('puesta_al_dia'):
        f['puesta_al_dia'] = previa['puesta_al_dia']
    return f


_SESION = {'ficha': None}
_LOCK_SESION = __import__('threading').Lock()


def de_esta_sesion(pantallas=None):
    """La ficha de este equipo, leída UNA vez por sesión (la usan el Registro al abrir y la telemetría). Con `pantallas` (las de Qt, con
    su escala) se ponen al día las de la ficha. Fuera del hilo de la interfaz."""
    with _LOCK_SESION:
        if _SESION['ficha'] is None:
            _SESION['ficha'] = recoger(pantallas=pantallas)
        elif pantallas:
            _SESION['ficha']['pantallas'] = pantallas
        return _SESION['ficha']


def _app():
    datos = {'compilado': bool(getattr(sys, 'frozen', False))}
    try:
        from version import APP_VERSION
        datos['version'] = APP_VERSION
    except Exception:
        pass
    try:
        import i18n
        datos['idioma'] = i18n.IDIOMA
    except Exception:
        pass
    return datos


def _componentes():
    if not _es_windows():
        return {}
    return {'vcredist_x64': vcredist_x64() or 'no', 'winget': 'sí' if winget() else 'no'}


def _nvidia(f):
    return next((g for g in f.get('gpus') or [] if g.get('fabricante') == 'NVIDIA'), None)


def version_nvidia(f):
    """El número principal del driver NVIDIA de la ficha (596 de «596.36») o 0."""
    g = _nvidia(f)
    try:
        return int(str(g.get('driver', '')).split('.')[0]) if g else 0
    except ValueError:
        return 0


def revisar(f):
    """Lo que CineCaptions necesita del equipo: [{id, estado: ok|aviso|falta, texto}]."""
    salida = []

    def anotar(i, estado, texto):
        salida.append({'id': i, 'estado': estado, 'texto': texto})

    so = f.get('so') or {}
    if _es_windows() and so.get('build'):
        b = int(str(so['build']).split('.')[0] or 0)
        anotar('windows', 'ok' if b >= WINDOWS_BUILD_MINIMO else 'falta',
               f"{so.get('nombre', 'Windows')} {so.get('version', '')}".strip() + ('' if b >= WINDOWS_BUILD_MINIMO else
                                                                                     ': hace falta Windows 10 2004 o más nuevo'))
    gpus = f.get('gpus') or []
    g = _nvidia(f)
    if g:
        v = version_nvidia(f)
        if not v:
            anotar('driver_gpu', 'aviso', f"{g['nombre']}: no pude leer la versión de su driver")
        elif v < NVIDIA_MINIMO:
            anotar('driver_gpu', 'falta', f"Driver NVIDIA {g.get('driver')}: con este driver la voz no puede usar la GPU (hace falta "
                                          f"{NVIDIA_MINIMO} o más; recomendado {NVIDIA_RAPIDO} o más)")
        elif v < NVIDIA_RAPIDO:
            anotar('driver_gpu', 'aviso', f"Driver NVIDIA {g.get('driver')}: funciona; con {NVIDIA_RAPIDO} o más la voz va más rápida")
        else:
            anotar('driver_gpu', 'ok', f"Driver NVIDIA {g.get('driver')}: al día")
        vram = g.get('vram_mb') or 0
        if vram and vram < 5800:
            anotar('vram', 'aviso', f"{g['nombre']} con {round(vram / 1024)} GB de memoria de vídeo: la IA de texto irá más lenta")
    elif gpus:
        dedicada = next((x for x in gpus if x.get('fabricante') in ('AMD', 'Intel', 'Qualcomm', 'Apple')), gpus[0])
        anotar('driver_gpu', 'ok', f"{dedicada['nombre']}" + (f" (driver {dedicada['driver']})" if dedicada.get('driver') else '')
               + ': la voz va por la CPU y el recorte por DirectML' if _es_windows() else f"{dedicada['nombre']}")
    else:
        anotar('driver_gpu', 'aviso', 'No encontré una tarjeta gráfica: todo irá por la CPU (más lento)')
    if _es_windows():
        vc = (f.get('componentes') or {}).get('vcredist_x64', '')
        if vc in ('', 'no'):
            anotar('vcredist', 'falta', 'Falta Microsoft Visual C++ 2015-2022 (x64): sin él la IA puede cerrarse al cargar')
        elif _version_tupla(vc)[:2] < VCREDIST_MINIMO:
            anotar('vcredist', 'falta', f'Visual C++ {vc} es antiguo: hace falta 14.40 o más (la IA puede cerrarse al cargar)')
        else:
            anotar('vcredist', 'ok', f'Visual C++ {vc}')
    ram = (f.get('ram') or {}).get('total_mb') or 0
    if ram:
        gb = round(ram / 1024)
        anotar('ram', 'falta' if ram < RAM_MINIMA_MB else 'aviso' if ram < RAM_BUENA_MB else 'ok',
               f'{gb} GB de RAM' + (': con menos de 8 GB la IA no cabe' if ram < RAM_MINIMA_MB else
                                   ': funciona; con 16 GB o más va más holgado' if ram < RAM_BUENA_MB else ''))
    for d in f.get('discos') or []:
        libre = d.get('libre_gb') or 0
        if libre < DISCO_BUENO_GB:
            anotar('disco_' + d.get('uso', ''), 'falta' if libre < DISCO_MINIMO_GB else 'aviso',
                   f"Disco {d.get('unidad')} ({d.get('uso')}): {libre:g} GB libres" + (' (hacen falta 10 GB o más)' if libre < DISCO_MINIMO_GB else ''))
    cpu = f.get('cpu') or {}
    if cpu.get('avx2') is False:
        anotar('cpu', 'aviso', f"{cpu.get('nombre') or 'El procesador'} no tiene AVX2: la voz por la CPU irá más lenta")
    r = f.get('resolve') or {}
    if r.get('instalado') is False:
        anotar('resolve', 'aviso', 'DaVinci Resolve no está instalado (CineCaptions coloca los subtítulos en Resolve)')
    elif r.get('version'):
        mayor = _version_tupla(r['version'])[:1]
        anotar('resolve', 'aviso' if mayor and mayor[0] < 19 else 'ok', f"DaVinci Resolve {r.get('edicion', '')} {r['version']}".replace('  ', ' ')
               + (': CineCaptions está probado con la 19 o más nueva' if mayor and mayor[0] < 19 else ''))
    return salida


def resumen(f, ram_libre=True):
    """«GPU NVIDIA GeForce RTX 4070 (12 GB, driver 596.36) · RAM 32 GB (libre 14,2 GB) · CPU … (24 hilos) · Pantalla 3840×2160» (≤ 300)."""
    def gb(mb):
        return ('%.1f GB' % (mb / 1024)).replace('.0 GB', ' GB').replace('.', ',')
    partes = []
    gpus = f.get('gpus') or []
    if gpus:
        trozos = []
        for g in gpus[:3]:
            extra = [x for x in ((gb(g['vram_mb']) if g.get('vram_mb') else ''), (f"driver {g['driver']}" if g.get('driver') else '')) if x]
            trozos.append(g['nombre'] + (f" ({', '.join(extra)})" if extra else ''))
        partes.append('GPU ' + ' + '.join(trozos))
    ram = f.get('ram') or {}
    if ram.get('total_mb'):
        partes.append('RAM ' + gb(ram['total_mb']) + (f" (libre {gb(ram['libre_mb'])})" if ram_libre and ram.get('libre_mb') is not None else ''))
    cpu = f.get('cpu') or {}
    if cpu:
        partes.append('CPU %s(%s hilos)' % ((cpu.get('nombre') + ' ') if cpu.get('nombre') else '', cpu.get('hilos') or '?'))
    ps = f.get('pantallas') or []
    if ps:
        p = next((x for x in ps if x.get('principal')), ps[0])
        partes.append('Pantalla %d×%d' % (p.get('ancho', 0), p.get('alto', 0)) + (' al %d %%' % p['escala'] if p.get('escala') else '')
                      + (f' (+{len(ps) - 1})' if len(ps) > 1 else ''))
    return ' · '.join(partes)[:300]


def pendientes(f):
    """Lo que quedó por resolver (estado «falta» o «aviso» de la revisión), para el Registro."""
    return [r for r in f.get('revision') or [] if r.get('estado') in ('falta', 'aviso')]


def cargar():
    try:
        import archivos_seguros
        datos = archivos_seguros.leer_json(ARCHIVO, defecto={}) or {}
        return datos if isinstance(datos, dict) else {}
    except Exception:
        return {}


def guardar(f):
    try:
        import archivos_seguros
        archivos_seguros.escribir_json(ARCHIVO, f)
        return True
    except Exception:
        return False


def huella(f):
    """Lo que identifica la ficha SIN lo que cambia a cada rato (hora, RAM y disco libres): si cambia, se vuelve a mandar."""
    import hashlib
    fija = {k: v for k, v in f.items() if k not in ('cuando', 'ram', 'discos', 'revision')}
    fija['ram_total'] = (f.get('ram') or {}).get('total_mb')
    fija['discos'] = [(d.get('uso'), d.get('unidad'), round(d.get('total_gb') or 0)) for d in f.get('discos') or []]
    fija['revision'] = [(r.get('id'), r.get('estado')) for r in f.get('revision') or []]
    return hashlib.sha1(json.dumps(fija, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


if __name__ == '__main__':                     # para mirar la ficha de este equipo: python ficha_equipo.py
    ficha = recoger(origen='consola')
    print(json.dumps(ficha, ensure_ascii=False, indent=1))
    print(resumen(ficha))
