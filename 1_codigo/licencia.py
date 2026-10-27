# CineCaptions · By Cinema Productions
# 1_codigo/licencia.py — la licencia (claves CC- de cinecaptions.shop): activar, verificar, desactivar, estado firmado, 7 días sin internet.
"""
licencia.py  (v5.52)
--------------------
Licencia de CineCaptions: las claves CC-XXXX-XXXX-XXXX-XXXX que vende cinecaptions.shop.

Pedido (27-10-2026): la web vende con Recurrente y da una clave CC-; «ya no quiero Gumroad,
Hotmart ni Lemon Squeezy». Antes (v5.2.1-5.51) eran Lemon Squeezy y Gumroad, como CineSlide 9.20.

  - Habla con el servidor de licencias de la web (LIC_API, POST form-urlencoded, sin ninguna
    clave secreta): accion=activar (ocupa uno de los LIC_MAX_EQUIPOS equipos de la clave),
    verificar (antes de trabajar y en segundo plano al abrir) y desactivar (libera el equipo al
    momento). Responde JSON con «codigo»: activa, invalida (404), bloqueada (403: reembolso o
    contracargo), en_uso (409: límite de equipos) o desactivada (este equipo ya no está).
  - Solo se acepta el formato CC- (regex _RX_CC, sin distinguir mayúsculas ni espacios).
  - Estado local: ~/DaVinciSubtitles/licencia/licencia.dat, firmado (HMAC) con el ID de ESTA
    computadora: copiado a otra no vale, y si se edita a mano deja de valer. Sin internet
    funciona LIC_DIAS_SIN_INTERNET días desde la última verificación correcta (si el reloj se
    atrasa, pide verificar en línea).
  - Se exige en la interfaz (al abrir, en GO, al generar y al regenerar) y TAMBIÉN en el motor
    (_run_pipeline): sin licencia vigente no se transcribe ni se coloca nada.

Las licencias de antes (v5.1: correo + código HP; v5.2.1-5.51: Lemon Squeezy y Gumroad) ya no
valen: local() no las lee y hay que activar una clave CC-.
"""
import hashlib
import hmac
import json
import os
import platform
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from i18n import tr

# ---------------------------------------------------------------- configuración
# Las direcciones van AQUÍ y no en un archivo que el cliente pueda editar: si no, cualquiera pondría
# su propio servidor. Solo valores públicos (ninguna clave secreta).
LIC_API = 'https://cinecaptions.shop/pagos/licencia.php'   # servidor de licencias de la web (pagos/licencia.php)
LIC_URL_COMPRA = 'https://cinecaptions.shop/#precio'       # botón «Comprar licencia»
LIC_TIENDA = 'cinecaptions.shop'
LIC_MAX_EQUIPOS = 2                     # computadoras por clave (lo decide el servidor: MAX_EQUIPOS de pagos/config.php)
LIC_WHATSAPP = ''                       # soporte por WhatsApp: número con código de país ('' = sin botón)
LIC_DIAS_SIN_INTERNET = 7               # días que funciona sin conexión desde la última verificación
LIC_REVALIDAR_HORAS = 12                # con la ventana abierta se vuelve a verificar cada tantas horas
_SAL = b'cinecaptions-licencia-v1'
_RX_CC = re.compile(r'^CC(-[A-Z2-9]{4}){4}$')   # el alfabeto de la web: sin 0/O/1/I
CODIGOS_DEFINITIVOS = ('bloqueada', 'desactivada', 'invalida')
TIMEOUT_S = 12
_CACHE = {'equipo': None}


class ErrorLicencia(RuntimeError):
    """CineCaptions no tiene una licencia activa en esta computadora (la lanza el motor)."""


class SinConexion(Exception):
    """La tienda no respondió (sin internet, servidor caído o demasiadas peticiones)."""


class ResultadoLicencia:
    """ok, codigo (activa, sin_licencia, invalida, en_uso, bloqueada, desactivada, sin_conexion,
    sin_conexion_ok, error), mensaje para el cliente y los datos guardados de la licencia."""
    __slots__ = ('ok', 'codigo', 'mensaje', 'datos')

    def __init__(self, ok, codigo, mensaje, datos=None):
        self.ok, self.codigo, self.mensaje, self.datos = bool(ok), codigo, mensaje, dict(datos or {})

    def __repr__(self):
        return 'ResultadoLicencia(%r, %r, %r)' % (self.ok, self.codigo, self.mensaje)


def configurada():
    """Siempre hay licencia que activar (se conserva por los llamadores de la v5.1)."""
    return True


# ---------------------------------------------------------------- equipo
def _carpeta():
    return Path.home() / 'DaVinciSubtitles' / 'licencia'


def _id_bruto():
    """Identificador que da el sistema (Windows: MachineGuid; Mac: IOPlatformUUID; Linux: machine-id)."""
    if sys.platform.startswith('win'):
        import winreg
        for vista in (winreg.KEY_WOW64_64KEY, 0):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Cryptography', 0,
                                    winreg.KEY_READ | vista) as k:
                    valor = str(winreg.QueryValueEx(k, 'MachineGuid')[0])
                    if valor:
                        return valor
            except OSError:
                continue
    elif sys.platform == 'darwin':
        salida = subprocess.run(['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'], capture_output=True,
                                text=True, timeout=15).stdout
        m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', salida or '')
        if m:
            return m.group(1)
    for ruta in ('/etc/machine-id', '/var/lib/dbus/machine-id'):
        try:
            valor = Path(ruta).read_text().strip()
            if valor:
                return valor
        except OSError:
            continue
    raise RuntimeError('No se pudo leer el identificador de esta computadora.')


def id_equipo():
    """ID corto y estable de esta computadora (p. ej. 3F2A-91BC-04DE-77A1): el cliente lo da al
    pedir soporte."""
    if not _CACHE['equipo']:
        try:
            bruto = _id_bruto()
        except Exception:                       # muy raro: la tarjeta de red (también estable)
            import uuid
            bruto = 'red:%012x' % uuid.getnode()
        h = hashlib.sha256(('CineCaptions:%s' % bruto).encode('utf-8')).hexdigest()[:16].upper()
        _CACHE['equipo'] = '-'.join(h[i:i + 4] for i in range(0, 16, 4))
    return _CACHE['equipo']


def nombre_equipo():
    """Nombre con el que esta computadora aparece en la tienda y en el Administrador."""
    return ('%s · %s' % (platform.node() or 'Equipo', id_equipo()))[:100]


# ---------------------------------------------------------------- tiendas
def _ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    ctx = ssl.create_default_context()
    if sys.platform == 'darwin':                # el Python propio de Mac no trae certificados
        for ca in ('/etc/ssl/cert.pem', '/private/etc/ssl/cert.pem'):
            if os.path.isfile(ca):
                try:
                    ctx.load_verify_locations(ca)
                    break
                except Exception:
                    pass
    return ctx


def _version():
    try:
        from version import APP_VERSION
        return APP_VERSION
    except Exception:
        return '?'


def _llamar(url, datos):
    """POST a la API de licencias de una tienda. Devuelve el JSON también cuando la tienda contesta
    con un error de la licencia (400-422, con '_http'); lanza SinConexion si no hay respuesta útil."""
    req = urllib.request.Request(url, data=urllib.parse.urlencode(datos).encode('utf-8'), method='POST',
                                 headers={'Accept': 'application/json',
                                          'Content-Type': 'application/x-www-form-urlencoded',
                                          'User-Agent': 'CineCaptions/%s' % _version()})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=_ssl()) as r:
            d = json.loads(r.read() or b'{}')
            return d if isinstance(d, dict) else {}
    except urllib.error.HTTPError as e:
        if 400 <= e.code < 500 and e.code != 429:
            try:
                d = json.loads(e.read() or b'{}')
                if isinstance(d, dict):
                    d['_http'] = e.code
                    return d
            except ValueError:
                pass
        raise SinConexion(tr('La tienda de licencias no respondió bien ({codigo}).', codigo=e.code))
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise SinConexion(tr('No hay conexión a internet ({motivo}).', motivo=getattr(e, 'reason', None) or e))


def _fecha(ts):
    return time.strftime('%d/%m/%Y', time.localtime(ts)) if ts else ''


def _normalizar(clave):
    """La clave como la guarda el servidor: sin espacios y en mayúsculas."""
    return re.sub(r'\s+', '', str(clave or '')).upper()


def _pedir(accion, clave):
    """accion = activar | verificar | desactivar, para ESTA computadora."""
    return _llamar(LIC_API, {'accion': accion, 'clave': clave, 'equipo': id_equipo(), 'nombre_equipo': nombre_equipo()})


def _motivo(r):
    """None si la clave está activa en esta computadora; si no, (codigo, mensaje para el cliente)."""
    codigo = str(r.get('codigo') or '')
    if r.get('valida') and codigo == 'activa':
        return None
    if codigo == 'invalida':
        return 'invalida', tr('La clave no es válida. Revísala: te llegó por correo al comprar.')
    if codigo == 'bloqueada':
        return 'bloqueada', tr('Tu licencia fue bloqueada. Escribe al vendedor.')
    if codigo == 'en_uso':
        return 'en_uso', tr('Esta licencia ya está activada en el máximo de computadoras. Desactívala en la otra '
                            '(Ajustes > Acerca de > Desactivar este equipo) o escribe al vendedor.')
    if codigo == 'desactivada':
        return 'desactivada', tr('Esta computadora fue desactivada de la licencia. Vuelve a activarla.')
    return 'error', str(r.get('error') or tr('No se pudo verificar la licencia.'))


def _datos(r):
    lic = r.get('licencia') or {}
    return {'cliente': lic.get('cliente') or '', 'correo': lic.get('correo') or '', 'producto': 'CineCaptions',
            'expira_ts': None, 'limite': lic.get('limite') or LIC_MAX_EQUIPOS, 'usados': lic.get('usados')}


def url_compra():
    """El enlace de «Comprar licencia» (la sección de precio de la web)."""
    return LIC_URL_COMPRA


def tiendas():
    """[(nombre, url)] de los botones de compra de la ventana."""
    return [(LIC_TIENDA, LIC_URL_COMPRA)]


def tipo_de_clave(clave):
    """'cinecaptions' | '' según el formato de lo que se escribió."""
    return 'cinecaptions' if _RX_CC.match(_normalizar(clave)) else ''


# ---------------------------------------------------------------- estado local (firmado con el ID de esta computadora)
def _archivo():
    return _carpeta() / 'licencia.dat'


def _firma(datos):
    clave = hashlib.sha256(_SAL + id_equipo().encode('utf-8')).digest()
    return hmac.new(clave, json.dumps(datos, sort_keys=True).encode('utf-8'), 'sha256').hexdigest()


def local():
    """Datos de la licencia activada en ESTA computadora (cliente, correo, plataforma, ultima_ok...)
    o None si no hay, si el archivo se editó o si viene de otra computadora."""
    try:
        contenido = json.loads(_archivo().read_text(encoding='utf-8'))
        datos, firma = contenido['datos'], str(contenido['firma'])
        if (isinstance(datos, dict) and hmac.compare_digest(firma, _firma(datos))
                and datos.get('equipo') == id_equipo() and datos.get('clave')
                and datos.get('plataforma') == 'cinecaptions'):
            return datos
    except Exception:
        pass
    return None


def _guardar(datos):
    datos = dict(datos)
    datos['visto'] = max(float(datos.get('visto') or 0.0), time.time())   # la hora más nueva vista
    ruta = _archivo()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name('%s.%d.tmp' % (ruta.name, os.getpid()))
    tmp.write_text(json.dumps({'datos': datos, 'firma': _firma(datos)}), encoding='utf-8')
    os.replace(tmp, ruta)
    return datos


def _borrar():
    try:
        _archivo().unlink()
    except OSError:
        pass


def _vigente(datos, ahora=None):
    """¿Vale la licencia guardada SIN preguntar a la tienda? Verificada hace menos de
    LIC_DIAS_SIN_INTERNET días, sin vencer y con el reloj sin atrasar."""
    if not datos or not datos.get('ultima_ok'):
        return False
    ahora = time.time() if ahora is None else float(ahora)
    if ahora + 3600 < float(datos.get('visto') or 0.0):
        return False
    if datos.get('expira_ts') and ahora >= float(datos['expira_ts']):
        return False
    return 0 <= ahora - float(datos['ultima_ok']) < LIC_DIAS_SIN_INTERNET * 86400


def vigente():
    """True si CineCaptions puede trabajar ahora en esta computadora (sin red: el estado guardado)."""
    return _vigente(local())


def toca_revalidar(horas=None):
    """True si la última verificación correcta tiene más de LIC_REVALIDAR_HORAS horas."""
    datos = local()
    if not datos:
        return False
    return time.time() - float(datos.get('ultima_ok') or 0) >= (horas or LIC_REVALIDAR_HORAS) * 3600


def mensaje_sin_licencia():
    return tr('Para generar subtítulos CineCaptions necesita una licencia activa en esta computadora. '
              'Activa tu clave (o conéctate a internet para verificarla).')


def exigir():
    """La llama el motor: sin licencia vigente en esta computadora no se genera nada."""
    if not vigente():
        raise ErrorLicencia(mensaje_sin_licencia())


# ---------------------------------------------------------------- activar / comprobar / desactivar
def _sin_conexion(datos, exc):
    if _vigente(datos):
        return ResultadoLicencia(True, 'sin_conexion_ok',
                                 tr('Sin conexión: la licencia se volverá a verificar al conectarte.'), datos)
    return ResultadoLicencia(False, 'sin_conexion',
                             '%s %s' % (exc, tr('Conéctate a internet para verificar tu licencia.')), datos)


def comprobar():
    """Verifica en línea la licencia guardada (al abrir, en segundo plano). Sin internet vale el
    estado guardado."""
    datos = local()
    if not datos:
        return ResultadoLicencia(False, 'sin_licencia', tr('CineCaptions todavía no está activado en esta computadora.'))
    try:
        r = _pedir('verificar', datos['clave'])
    except SinConexion as exc:
        return _sin_conexion(datos, exc)
    fallo, nuevos = _motivo(r), _datos(r)
    if fallo is None:
        nuevos.update(ultima_ok=time.time(), fallo='', fallo_msg='')
        return ResultadoLicencia(True, 'activa', tr('Licencia activa.'), _guardar(dict(datos, **nuevos)))
    if fallo[0] == 'error':                     # la tienda falló pero no dijo nada de la licencia
        return _sin_conexion(datos, fallo[1])
    # bloqueada, desactivada...: la clave se conserva (si el vendedor la desbloquea vuelve a valer
    # sola) pero ya no funciona sin conexión
    _guardar(dict(datos, ultima_ok=0, fallo=fallo[0], fallo_msg=fallo[1]))
    return ResultadoLicencia(False, fallo[0], fallo[1], datos)


def activar(clave):
    """Activa la clave en esta computadora (ocupa uno de los equipos de la licencia; si ya lo
    estaba, el servidor solo lo refresca)."""
    clave = _normalizar(clave)
    if not clave:
        return ResultadoLicencia(False, 'invalida', tr('Escribe tu clave de licencia.'))
    guardada = local()
    if guardada and str(guardada.get('clave') or '').lower() == clave.lower():
        r = comprobar()                         # ya estaba activada aquí: solo se verifica (no gasta otro equipo)
        if r.ok or r.codigo not in ('desactivada', 'sin_licencia'):
            return r
    if not _RX_CC.match(clave):
        return ResultadoLicencia(False, 'invalida', tr('La clave no tiene el formato correcto (CC-XXXX-XXXX-XXXX-XXXX). '
                                                       'Cópiala tal cual del correo de tu compra.'))
    try:
        r = _pedir('activar', clave)
    except SinConexion as exc:
        return ResultadoLicencia(False, 'sin_conexion', '%s %s' % (exc, tr('Para activar hace falta internet.')))
    fallo = _motivo(r)
    if fallo:
        return ResultadoLicencia(False, *fallo)
    datos = _guardar(dict({'plataforma': 'cinecaptions', 'clave': clave, 'equipo': id_equipo(), 'activada': time.time()},
                          **_datos(r), ultima_ok=time.time()))
    return ResultadoLicencia(True, 'activa', tr('Licencia activada.'), datos)


def desactivar():
    """Libera esta computadora en el servidor (al momento) para activar la licencia en otra. Sin
    internet no se quita: el equipo seguiría ocupado en el servidor."""
    datos = local()
    if not datos:
        _borrar()
        return ResultadoLicencia(True, 'sin_licencia', tr('Esta computadora no tenía una licencia activada.'))
    try:
        r = _pedir('desactivar', datos['clave'])
    except SinConexion as exc:
        return ResultadoLicencia(False, 'sin_conexion',
                                 '%s %s' % (exc, tr('Para liberar esta computadora hace falta internet.')), datos)
    codigo = str(r.get('codigo') or '')
    if codigo == 'desactivada':                 # liberada (o ya no estaba en el servidor)
        _borrar()
        return ResultadoLicencia(True, 'desactivada', tr('Esta computadora quedó libre: ya puedes activar tu licencia '
                                                         'en otra.'))
    if codigo in ('invalida', 'bloqueada'):     # no queda nada que liberar
        _borrar()
        return ResultadoLicencia(True, 'desactivada', tr('Licencia quitada de esta computadora.'))
    return ResultadoLicencia(False, 'error', str(r.get('error') or tr('No se pudo verificar la licencia.')), datos)


def seguro(funcion, *args):
    """Ejecuta una operación de licencia sin dejar escapar excepciones (para los hilos)."""
    try:
        return funcion(*args)
    except Exception as exc:
        return ResultadoLicencia(False, 'error', tr('No se pudo verificar la licencia: {error}', error=exc))


# ---------------------------------------------------------------- textos
def clave_enmascarada(clave):
    clave = str(clave or '')
    return ('••••-' + clave[-8:].upper()) if len(clave) > 8 else clave


def tienda_de(datos):
    return LIC_TIENDA


def resumen(datos=None):
    """{'estado', 'detalle', 'nivel' ('ok'|'aviso'|'error'), 'activa', 'hay_clave'} para la tarjeta
    de Inicio y Ajustes. Sin red."""
    datos = local() if datos is None else datos
    if not datos:
        return {'estado': tr('Sin activar'), 'detalle': tr('Activa tu clave de licencia de CineCaptions.'),
                'nivel': 'error', 'activa': False, 'hay_clave': False}
    partes = [tienda_de(datos)]
    if datos.get('usados') is not None:
        partes.append(tr('{u} de {m} equipos', u=datos.get('usados'), m=datos.get('limite') or '∞'))
    if datos.get('prueba'):
        partes.append(tr('clave de PRUEBA'))
    if _vigente(datos):
        return {'estado': tr('Activa'), 'detalle': ' · '.join(partes), 'nivel': 'ok', 'activa': True, 'hay_clave': True}
    if datos.get('fallo') in CODIGOS_DEFINITIVOS:
        return {'estado': tr('No válida'), 'detalle': str(datos.get('fallo_msg') or ''), 'nivel': 'error',
                'activa': False, 'hay_clave': True}
    return {'estado': tr('Sin verificar'),
            'detalle': tr('Conéctate a internet para verificar tu licencia (pasaron más de {n} días).',
                          n=LIC_DIAS_SIN_INTERNET),
            'nivel': 'aviso', 'activa': False, 'hay_clave': True}


def texto(datos=None):
    """Resumen legible de la licencia guardada (varias líneas)."""
    datos = local() if datos is None else datos
    if not datos:
        return tr('CineCaptions no está activado en esta computadora.')
    lineas = ['%s · %s%s' % (tr('Licencia activa') if _vigente(datos) else tr('Licencia SIN verificar'),
                             tienda_de(datos), (' · ' + tr('clave de PRUEBA')) if datos.get('prueba') else '')]
    if datos.get('cliente') or datos.get('correo'):
        quien = datos.get('cliente') or datos.get('correo')
        if datos.get('cliente') and datos.get('correo'):
            quien += ' (%s)' % datos['correo']
        lineas.append(tr('A nombre de: {quien}', quien=quien))
    lineas.append(tr('Clave: {clave}', clave=clave_enmascarada(datos.get('clave'))))
    if datos.get('usados') is not None:
        lineas.append(tr('{que}: {u} de {m} · Vence: {cuando}', que=tr('Computadoras'), u=datos.get('usados'), m=datos.get('limite') or tr('ilimitadas'),
                         cuando=_fecha(datos.get('expira_ts')) or tr('nunca')))
    lineas.append(tr('Esta computadora: {nombre}', nombre=nombre_equipo()))
    if datos.get('ultima_ok'):
        lineas.append(tr('Última verificación: {cuando}',
                         cuando=time.strftime('%d/%m/%Y %H:%M', time.localtime(float(datos['ultima_ok'])))))
    return '\n'.join(lineas)


def resumen_diagnostico():
    """Líneas para --diagnostico. Sin la clave completa ni el correo."""
    try:
        datos = local()
        if not datos:
            return [f'licencia       : sin activar · equipo={id_equipo()} · tienda={LIC_TIENDA}']
        ultima = datos.get('ultima_ok')
        return [f"licencia       : {datos.get('plataforma')} vigente={_vigente(datos)} prueba={bool(datos.get('prueba'))}"
                f" clave={clave_enmascarada(datos.get('clave'))} equipo={id_equipo()}",
                f"                 usados={datos.get('usados')}/{datos.get('limite')} fallo={datos.get('fallo') or '-'}"
                f" ultima_ok={time.strftime('%Y-%m-%d %H:%M', time.localtime(float(ultima))) if ultima else '-'}"
                f" sin_internet={LIC_DIAS_SIN_INTERNET}d"]
    except Exception as ex:
        return [f'licencia       : error al leer ({ex})']
