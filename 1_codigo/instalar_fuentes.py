# CineCaptions · By Cinema Productions
# 1_codigo/instalar_fuentes.py — instala en el sistema las tipografías de las plantillas (para que Resolve/Fusion las vea).
"""\ninstalar_fuentes.py\n-------------------\nInstalar en el sistema operativo las tipografias que viajan dentro del\nprograma (fonts/), para que RESOLVE pueda usarlas.\n\nPor que no basta con incluirlas\n================================\nPillow abre un archivo y dibuja: le da igual donde este. Por eso la vista\nprevia y las medidas funcionan con la carpeta \'fonts/\' del bundle y ya.\n\nFusion NO. Resolve resuelve \"Montserrat / SemiBold\" preguntandole al\nsistema operativo por su registro de fuentes. Una tipografia que solo esta\nen nuestra carpeta es invisible para el: pone otra en su lugar y el pack se\nve distinto, sin avisar. De ahi la separacion en fuentes_sistema.py entre\nruta_de_fuente() (para dibujar) y esta_en_el_sistema() (para saber si\nResolve la va a ver).\n\nEsto TOCA EL SISTEMA DEL USUARIO, asi que nunca se hace solo: siempre\ndetras de un boton que el usuario pulsa a sabiendas.\n\nSin permisos de administrador\n==============================\nEn Windows se instala \"solo para mi\": los archivos van a\n%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts y el registro a HKCU. Es como se\ninstalan casi todas las fuentes hoy y no pide UAC -importa, porque el\ninstalador del producto corre con PrivilegesRequired=lowest-.\nEn macOS basta con copiar a ~/Library/Fonts; no hay registro que tocar.\n"""
import os
import shutil
import sys
from pathlib import Path
import fuentes_sistema
from i18n import tr
def carpeta_destino():
    """Donde hay que dejar el archivo para que el sistema lo vea. O None."""
    if sys.platform.startswith('win'):
        local = os.environ.get('LOCALAPPDATA')
        if not local:
            return
        else:
            return Path(local) / 'Microsoft' / 'Windows' / 'Fonts'
    else:
        if sys.platform == 'darwin':
            return Path.home() / 'Library' / 'Fonts'
        else:
            return Path.home() / '.local' / 'share' / 'fonts'
def _nombre_para_el_registro(ruta):
    """\'Montserrat SemiBold (TrueType)\' — el nombre que espera Windows."""
    sufijo = ' (OpenType)' if ruta.suffix.lower() in ['.otf', '.otc'] else ' (TrueType)'
    try:
        caras = fuentes_sistema.caras_de(ruta)
    except Exception:
        caras = []
    for fam16, est17, fam1, est2, completo in caras:
        if completo:
            return completo + sufijo
        else:
            if fam16:
                return (f'{fam16} {est17}'.strip() if est17 else fam16) + sufijo
            else:
                if fam1:
                    return (f'{fam1} {est2}'.strip() if est2 else fam1) + sufijo
    return ruta.stem + sufijo
def _registrar_en_windows(destino):
    """Le dice a Windows que esa fuente existe. (ok, motivo_si_no)."""
    try:
        import ctypes
        from ctypes import wintypes
    except Exception as exc:
        return (False, tr('no pude cargar ctypes ({exc})', exc=exc))
    try:
        gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
        gdi32.AddFontResourceExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                             ctypes.c_void_p]
        gdi32.AddFontResourceExW.restype = ctypes.c_int
        if gdi32.AddFontResourceExW(str(destino), 0, None) == 0:
            return (False, tr('AddFontResourceExW no la acepto'))
    except Exception as exc:
        return (False, tr('AddFontResourceExW fallo ({exc})', exc=exc))
    try:
        import winreg
        clave = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            'Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts', 0,
            winreg.KEY_SET_VALUE)
        with clave:
            winreg.SetValueEx(clave, _nombre_para_el_registro(destino), 0,
                              winreg.REG_SZ, str(destino))
    except Exception as exc:
        return (False, tr('no pude escribir el registro ({exc})', exc=exc))
    try:
        ctypes.WinDLL('user32').PostMessageW(65535, 29, 0, 0)
    except Exception:
        pass
    return (True, '')
def instalar(rutas, progreso=None):
    """Instala esos archivos. Devuelve (instaladas, fallos).\n\n    \'fallos\' es [(nombre_archivo, motivo)] — nunca se descarta un error en\n    silencio: si una tipografia no entra, el usuario tiene que poder saber\n    cual y por que, porque el sintoma (Resolve pone otra) no lo dice.\n    """
    destino_dir = carpeta_destino()
    if destino_dir is None:
        return ([], [(tr('(todas)'), tr('no se donde instalar fuentes en este sistema'))])
    else:
        try:
            destino_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ([], [(tr('(todas)'), tr('no pude crear {carpeta} ({exc})', carpeta=destino_dir, exc=exc))])
        instaladas, fallos = ([], [])
        rutas = [Path(r) for r in rutas]
        for i, origen in enumerate(rutas):
            if progreso:
                progreso(i, len(rutas), origen.name)
            if not origen.is_file():
                fallos.append((origen.name, tr('no encuentro el archivo')))
                continue
            else:
                destino = destino_dir / origen.name
                try:
                    if not (destino.is_file() and destino.stat().st_size == origen.stat().st_size):
                        shutil.copyfile(origen, destino)
                except OSError as exc:
                    fallos.append((origen.name, tr('no pude copiarla ({exc})', exc=exc)))
                else:
                    if sys.platform.startswith('win'):
                        ok, motivo = _registrar_en_windows(destino)
                        if not ok:
                            fallos.append((origen.name, motivo))
                            continue
                    instaladas.append(destino)
        if instaladas:
            fuentes_sistema.invalidar_cache()
        if progreso:
            progreso(len(rutas), len(rutas), '')
        return (instaladas, fallos)
def faltantes(pares):
    """De [(familia, estilo)], las que faltan y SI podemos instalar.\n\n    Devuelve (arreglables, sin_remedio):\n      arreglables  [((familia, estilo), ruta_en_fonts)]  -> el boton sirve\n      sin_remedio  [(familia, estilo)]                   -> no la traemos;\n                   solo queda que el usuario la instale por su cuenta.\n    """
    arreglables, sin_remedio = ([], [])
    for familia, estilo in pares:
        if fuentes_sistema.esta_en_el_sistema(familia, estilo, exacto=True):
            continue
        else:
            ruta = fuentes_sistema.se_puede_instalar(familia, estilo)
            if ruta is not None:
                arreglables.append(((familia, estilo), ruta))
            else:
                sin_remedio.append((familia, estilo))
    return (arreglables, sin_remedio)
def instalar_faltantes(pares, progreso=None):
    """Atajo: mira cuales faltan de esa lista y instala las que se pueda.

    Devuelve (instaladas, fallos, sin_remedio, verificadas). 'verificadas'
    son las que despues de instalar el sistema SI reconoce — se comprueba
    de verdad en vez de dar por bueno que copiar el archivo alcanzo.
    """
    arreglables, sin_remedio = faltantes(pares)
    if not arreglables:
        return ([], [], sin_remedio, [])
    rutas = []
    for _, ruta in arreglables:
        if ruta not in rutas:
            rutas.append(ruta)
    instaladas, fallos = instalar(rutas, progreso=progreso)
    verificadas = [par for par, _ in arreglables
                   if fuentes_sistema.esta_en_el_sistema(*par, exacto=True)]
    return (instaladas, fallos, sin_remedio, verificadas)
