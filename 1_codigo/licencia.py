# CineCaptions · By Cinema Productions
# 1_codigo/licencia.py — la licencia (Lemon Squeezy / Gumroad): activar, verificar, desactivar, estado firmado, 7 días sin internet.
"""
licencia.py  (v5.2.1)
---------------------
Licencia de CineCaptions: Lemon Squeezy (también los compradores de Hotmart) y Gumroad.

Pedido (04-10-2026): «las licencias ahora son de Lemon Squeezy, ya no de Hotmart; aprende todo
de las licencias de CineSlide y aplícalo en CineCaptions». Es el mismo sistema que CineSlide 9.20:

  - Habla con las APIs PÚBLICAS de licencias, que NO usan ninguna clave secreta (las
    credenciales de las tiendas viven solo en el Administrador de Licencias del vendedor):
      Lemon Squeezy: /v1/licenses/validate (antes de activar y en segundo plano al abrir),
      /activate (ocupa un equipo de la licencia) y /deactivate (lo libera). Solo valen las
      claves de la tienda LIC_TIENDA_LS y del producto CineCaptions: las de OTROS productos de
      la misma tienda (CineSlide...) o de otras tiendas se rechazan sin ocupar ningún equipo.
      Gumroad: /v2/licenses/verify con LIC_GUMROAD_PRODUCTO; al activar suma un «uso».
  - Hotmart no genera claves: a quien compra en Hotmart el vendedor le da su licencia desde el
    Administrador («Dar licencia» = una licencia de Lemon Squeezy de este producto) y se activa
    aquí como cualquier otra. Un código de compra de Hotmart (HP...) se reconoce para explicar
    que no es la clave.
  - La tienda se reconoce por el formato de la clave (Gumroad: 4 bloques de 8; Lemon Squeezy:
    8-4-4-4-12).
  - Estado local: ~/DaVinciSubtitles/licencia/licencia.dat, firmado (HMAC) con el ID de ESTA
    computadora: copiado a otra no vale, y si se edita a mano deja de valer. Sin internet
    funciona LIC_DIAS_SIN_INTERNET días desde la última verificación correcta (si el reloj se
    atrasa, pide verificar en línea).
  - Se exige en la interfaz (al abrir, en GO, al generar y al regenerar) y TAMBIÉN en el motor
    (_run_pipeline): sin licencia vigente no se transcribe ni se coloca nada.

La licencia de la v5.1 (correo + código HP contra un servidor propio) ya no se usa: su archivo
viejo (licencia.json) se deja donde está, sin leerlo.
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
# Los IDs van AQUÍ y no en un archivo que el cliente pueda editar: si no, cualquiera pondría su
# propia tienda. Solo valores públicos (ninguna clave secreta).
LIC_TIENDA_LS = 488116                  # tienda «Cinema Productions» en Lemon Squeezy
LIC_PRODUCTOS_LS = ()                   # ID(s) del producto CineCaptions; () = se reconoce por el nombre
LIC_NOMBRES_PRODUCTO_LS = ('cinecaptions',)   # nombre del producto (sin espacios ni mayúsculas) si no hay ID
LIC_URL_COMPRA_LS = ''                  # enlace de compra de CineCaptions («Share» del producto en Lemon Squeezy)
LIC_URL_TIENDA_LS = 'https://cinemaproductions.lemonsqueezy.com'   # sin enlace de compra: la tienda
LIC_GUMROAD_PRODUCTO = 'CkMKwR_nujZt0DyW0WjSZA=='   # «Product ID» de CineCaptions (producto «CineCaptions») en Gumroad
LIC_GUMROAD_MAX_EQUIPOS = 2             # computadoras por clave de Gumroad (0 = sin límite)
LIC_URL_COMPRA_GUMROAD = 'https://cinemaproductions.gumroad.com/l/Cinecaptions'
LIC_URL_COMPRA_HOTMART = ''             # página de venta en Hotmart (solo para el botón)
LIC_WHATSAPP = ''                       # soporte por WhatsApp: número con código de país ('' = sin botón)
LIC_DIAS_SIN_INTERNET = 7               # días que funciona sin conexión desde la última verificación
LIC_REVALIDAR_HORAS = 12                # con la ventana abierta se vuelve a verificar cada tantas horas
LIC_ACEPTAR_PRUEBA = True               # MODO PRUEBAS (como CineSlide 9.21): acepta claves de compras de
#                                         prueba («Test mode»). ¡Poner False ANTES DE VENDER!
_SAL = b'cinecaptions-licencia-v1'
_API_LS = 'https://api.lemonsqueezy.com/v1/licenses/'
_API_GUMROAD = 'https://api.gumroad.com/v2/licenses/'
_RX_GUMROAD = re.compile(r'^[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{8}){3}$')
_RX_LS = re.compile(r'^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$')
_RX_HOTMART = re.compile(r'^HP\d{6,}$', re.I)
CODIGOS_DEFINITIVOS = ('bloqueada', 'vencida', 'desactivada', 'invalida', 'otra_tienda', 'reembolsada')
TIMEOUT_S = 12
_CACHE = {'equipo': None}


class ErrorLicencia(RuntimeError):
    """CineCaptions no tiene una licencia activa en esta computadora (la lanza el motor)."""


class SinConexion(Exception):
    """La tienda no respondió (sin internet, servidor caído o demasiadas peticiones)."""


class ResultadoLicencia:
    """ok, codigo (activa, sin_licencia, invalida, en_uso, bloqueada, vencida, reembolsada,
    desactivada, otra_tienda, sin_conexion, sin_conexion_ok, error), mensaje para el cliente y
    los datos guardados de la licencia."""
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


def _iso_ts(iso):
    if not iso:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(iso).replace('Z', '+00:00')).timestamp()
    except ValueError:
        return None


def _fecha(ts):
    return time.strftime('%d/%m/%Y', time.localtime(ts)) if ts else ''


def _normal(texto):
    return re.sub(r'[^0-9a-z]', '', str(texto or '').lower())


def _es_nuestra_ls(r):
    """True si la clave es de CineCaptions: misma tienda, producto aceptado y (si no se aceptan
    pruebas) no es de prueba."""
    meta = r.get('meta') or {}
    try:
        if int(meta.get('store_id') or 0) != int(LIC_TIENDA_LS):
            return False
        if LIC_PRODUCTOS_LS:
            if int(meta.get('product_id') or 0) not in set(int(p) for p in LIC_PRODUCTOS_LS):
                return False
        else:
            nombre = _normal(meta.get('product_name'))
            if not nombre or not any(n in nombre for n in LIC_NOMBRES_PRODUCTO_LS):
                return False
    except (TypeError, ValueError):
        return False
    return LIC_ACEPTAR_PRUEBA or not (r.get('license_key') or {}).get('test_mode')


def _motivo_ls(r):
    """Respuesta de error de Lemon Squeezy -> (codigo, mensaje para el cliente)."""
    lic = r.get('license_key') or {}
    error = str(r.get('error') or '').lower()
    estado = lic.get('status')
    if estado == 'disabled' or 'disabled' in error:
        return 'bloqueada', tr('Tu licencia fue bloqueada. Escribe al vendedor.')
    if estado == 'expired' or 'expired' in error:
        cuando = _fecha(_iso_ts(lic.get('expires_at')))
        return 'vencida', ((tr('Tu licencia venció el {fecha}.', fecha=cuando) if cuando else tr('Tu licencia venció.'))
                           + ' ' + tr('Renuévala para seguir.'))
    if 'activation limit' in error:
        return 'en_uso', tr('Esta licencia ya está activada en el máximo de computadoras. Desactívala en la otra '
                            '(Ajustes > Acerca de > Desactivar este equipo) o escribe al vendedor.')
    if 'instance' in error:
        return 'desactivada', tr('Esta computadora fue desactivada de la licencia. Vuelve a activarla.')
    if 'not found' in error or r.get('_http') == 404:
        return 'invalida', tr('La clave no es válida. Revísala: te llegó por correo al comprar.')
    return 'error', str(r.get('error') or tr('No se pudo verificar la licencia.'))


def _motivo_no_nuestra_ls(r):
    if (r.get('license_key') or {}).get('test_mode') and not LIC_ACEPTAR_PRUEBA:
        return 'otra_tienda', tr('Esta clave es de una compra de prueba: no sirve para usar CineCaptions.')
    return 'otra_tienda', tr('Esta clave es de otro producto: no es una licencia de CineCaptions.')


def _datos_ls(r):
    lic, meta = r.get('license_key') or {}, r.get('meta') or {}
    return {'cliente': meta.get('customer_name') or '', 'correo': meta.get('customer_email') or '',
            'producto': meta.get('product_name') or '', 'expira_ts': _iso_ts(lic.get('expires_at')),
            'limite': lic.get('activation_limit'), 'usados': lic.get('activation_usage'),
            'prueba': bool(lic.get('test_mode'))}


def _verificar_gumroad(clave, sumar_uso=False):
    return _llamar(_API_GUMROAD + 'verify', {'product_id': LIC_GUMROAD_PRODUCTO, 'license_key': clave,
                                             'increment_uses_count': 'true' if sumar_uso else 'false'})


def _motivo_gumroad(r):
    """None si la clave de Gumroad es válida; si no, (codigo, mensaje)."""
    if not r.get('success'):
        mensaje = str(r.get('message') or '')
        if 'disabled' in mensaje.lower():
            return 'bloqueada', tr('Tu licencia fue bloqueada. Escribe al vendedor.')
        if r.get('_http') == 404 or 'not exist' in mensaje.lower():
            return 'invalida', tr('La clave no es válida. Revísala: te llegó por correo al comprar.')
        return 'error', mensaje or tr('No se pudo verificar la licencia.')
    compra = r.get('purchase') or {}
    if compra.get('refunded') or compra.get('chargebacked') or compra.get('chargedback'):
        return 'reembolsada', tr('Esta compra fue reembolsada: la licencia ya no es válida.')
    if compra.get('disputed') and not compra.get('dispute_won'):
        return 'bloqueada', tr('La compra de esta licencia está en disputa. Escribe al vendedor.')
    if (compra.get('subscription_ended_at') or compra.get('subscription_cancelled_at')
            or compra.get('subscription_failed_at')):
        return 'vencida', tr('Tu suscripción terminó. Renuévala para seguir usando CineCaptions.')
    if compra.get('test') and not LIC_ACEPTAR_PRUEBA:
        return 'otra_tienda', tr('Esta clave es de una compra de prueba: no sirve para usar CineCaptions.')
    if compra.get('product_id') and str(compra['product_id']) != str(LIC_GUMROAD_PRODUCTO):
        return 'otra_tienda', tr('Esta clave es de otro producto: no es una licencia de CineCaptions.')
    return None


def _datos_gumroad(r):
    compra = r.get('purchase') or {}
    return {'cliente': compra.get('full_name') or compra.get('email') or '', 'correo': compra.get('email') or '',
            'producto': compra.get('product_name') or '', 'expira_ts': None,
            'limite': LIC_GUMROAD_MAX_EQUIPOS or None, 'usados': r.get('uses')}


def url_compra():
    """El enlace de «Comprar licencia» (Gumroad)."""
    return LIC_URL_COMPRA_GUMROAD


def tiendas():
    """[(nombre, url)] de los botones de compra de la ventana."""
    return [(n, u) for n, u in (('Gumroad', LIC_URL_COMPRA_GUMROAD),) if u]


def tipo_de_clave(clave):
    """'ls' | 'gumroad' | 'hotmart' | '' según el formato de lo que se escribió."""
    k = re.sub(r'\s+', '', str(clave or ''))
    if _RX_GUMROAD.match(k):
        return 'gumroad'
    return ''


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
                and (datos.get('instancia') or datos.get('plataforma') == 'gumroad')):
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
        if datos.get('plataforma') == 'gumroad':
            if not LIC_GUMROAD_PRODUCTO:
                return ResultadoLicencia(False, 'otra_tienda',
                                         tr('Las claves de Gumroad ya no se aceptan. Escribe al vendedor.'), datos)
            r = _verificar_gumroad(datos['clave'])
            fallo = _motivo_gumroad(r)
            nuevos = _datos_gumroad(r)
        else:                                   # licencia vieja de Lemon Squeezy: ya no se acepta
            _borrar()
            return ResultadoLicencia(False, 'sin_licencia', tr('Tu licencia anterior ya no se acepta: activa tu clave de '
                                                               'Gumroad (te llegó por correo al comprar).'))
    except SinConexion as exc:
        return _sin_conexion(datos, exc)
    if fallo is None:
        nuevos.update(ultima_ok=time.time(), fallo='', fallo_msg='')
        return ResultadoLicencia(True, 'activa', tr('Licencia activa.'), _guardar(dict(datos, **nuevos)))
    if fallo[0] == 'error':                     # la tienda falló pero no dijo nada de la licencia
        return _sin_conexion(datos, fallo[1])
    # bloqueada, vencida, reembolsada...: la clave se conserva (si el vendedor la desbloquea vuelve
    # a valer sola) pero ya no funciona sin conexión
    _guardar(dict(datos, ultima_ok=0, fallo=fallo[0], fallo_msg=fallo[1]))
    return ResultadoLicencia(False, fallo[0], fallo[1], datos)


def _activar_gumroad(clave):
    if not LIC_GUMROAD_PRODUCTO:
        return ResultadoLicencia(False, 'invalida', tr('Esa es una clave de Gumroad, pero CineCaptions todavía no se '
                                                       'vende en Gumroad. Revisa la clave o escribe al vendedor.'))
    try:
        r = _verificar_gumroad(clave)
        fallo = _motivo_gumroad(r)
        if fallo:
            return ResultadoLicencia(False, *fallo)
        if LIC_GUMROAD_MAX_EQUIPOS and int(r.get('uses') or 0) >= LIC_GUMROAD_MAX_EQUIPOS:
            return ResultadoLicencia(False, 'en_uso', tr('Esta licencia ya se activó en el máximo de computadoras '
                                                         '({n}). Pide al vendedor que libere un uso de tu clave.',
                                                         n=LIC_GUMROAD_MAX_EQUIPOS))
        r = _verificar_gumroad(clave, sumar_uso=True)
    except SinConexion as exc:
        return ResultadoLicencia(False, 'sin_conexion', '%s %s' % (exc, tr('Para activar hace falta internet.')))
    fallo = _motivo_gumroad(r)
    if fallo:
        return ResultadoLicencia(False, *fallo)
    datos = _guardar(dict({'plataforma': 'gumroad', 'clave': clave, 'equipo': id_equipo(), 'activada': time.time()},
                          **_datos_gumroad(r), ultima_ok=time.time()))
    return ResultadoLicencia(True, 'activa', tr('Licencia activada.'), datos)


def activar(clave):
    """Activa la clave en esta computadora (ocupa uno de los equipos de la licencia). Reconoce la
    tienda por el formato."""
    clave = re.sub(r'\s+', '', str(clave or ''))
    if not clave:
        return ResultadoLicencia(False, 'invalida', tr('Escribe tu clave de licencia.'))
    guardada = local()
    if guardada and str(guardada.get('clave') or '').lower() == clave.lower():
        r = comprobar()                         # ya estaba activada aquí: solo se verifica (no gasta otro equipo)
        if r.ok or r.codigo not in ('desactivada', 'sin_licencia'):
            return r
    if _RX_GUMROAD.match(clave):
        return _activar_gumroad(clave)
    return ResultadoLicencia(False, 'invalida', tr('La clave no tiene el formato correcto (4 grupos de 8 letras o '
                                                   'números). Cópiala tal cual del correo de tu compra en Gumroad.'))


def desactivar():
    """Libera esta computadora para activar la licencia en otra (Lemon Squeezy devuelve el equipo
    al momento; en Gumroad el vendedor libera el uso desde el Administrador)."""
    datos = local()
    if not datos:
        _borrar()
        return ResultadoLicencia(True, 'sin_licencia', tr('Esta computadora no tenía una licencia activada.'))
    if datos.get('plataforma') == 'gumroad':
        _borrar()
        return ResultadoLicencia(True, 'desactivada', tr('Licencia quitada de esta computadora. Para usarla en otra, pide '
                                                         'al vendedor que libere un uso de tu clave.'))
    _borrar()                                   # (licencia vieja de Lemon Squeezy: solo se quita)
    return ResultadoLicencia(True, 'desactivada', tr('Licencia quitada de esta computadora.'))


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
    return 'Gumroad'


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
        lineas.append(tr('{que}: {u} de {m} · Vence: {cuando}',
                         que=tr('Usos') if datos.get('plataforma') == 'gumroad' else tr('Computadoras'),
                         u=datos.get('usados'), m=datos.get('limite') or tr('ilimitadas'),
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
            return [f'licencia       : sin activar · equipo={id_equipo()} · tienda=Gumroad'
                    f' · pruebas={LIC_ACEPTAR_PRUEBA}']
        ultima = datos.get('ultima_ok')
        return [f"licencia       : {datos.get('plataforma')} vigente={_vigente(datos)} prueba={bool(datos.get('prueba'))}"
                f" clave={clave_enmascarada(datos.get('clave'))} equipo={id_equipo()}",
                f"                 usados={datos.get('usados')}/{datos.get('limite')} fallo={datos.get('fallo') or '-'}"
                f" ultima_ok={time.strftime('%Y-%m-%d %H:%M', time.localtime(float(ultima))) if ultima else '-'}"
                f" sin_internet={LIC_DIAS_SIN_INTERNET}d"]
    except Exception as ex:
        return [f'licencia       : error al leer ({ex})']
