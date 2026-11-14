# -*- coding: utf-8 -*-
"""
Servidor de prueba de pagos/admin.php para probar «CineCaptions Ventas» sin tocar el servidor real.

Imita la API privada con datos inventados: 27 pedidos de Recurrente repartidos en los últimos 70 días (casi todos en los
últimos 30, para la gráfica) y uno más ya eliminado de la lista (un pago sin completar repetido), 3 canjes de Gumroad,
equipos con CineCaptions 5.52, 5.53 y 5.54 (y algunos sin datos de versión), en Windows y en macOS, avisos de
actualización ya mandados, un correo dado de baja, notas e historial, y 5 errores que mandó CineCaptions desde 3 equipos
de 3 licencias (3 sin ver, 2 ya vistos).
Guarda todo en memoria y cambia ese estado con las acciones. Implementa el CONTRATO completo de admin.php (también las
acciones nuevas: panel, version_actual, versiones, candidatos_aviso, avisar_actualizacion, avisos, historial, nota,
limite, editar_cliente, estadisticas y, desde la 5.71 de CineCaptions, errores, error_detalle y error_visto, con el
resumen «errores» en panel, y eliminar_venta: quitar una venta de la lista y de los totales sin borrarla, el estado
'eliminadas' y «eliminada» en cada fila), la telemetría de licencia.php (activar y verificar guardan la versión, del
campo «version» o de la cabecera User-Agent «CineCaptions/5.54», y el sistema, «so») y errores.php (lo que manda el
programa cuando a un cliente le sale un error: el mismo error en el mismo equipo suma «veces» y, si ya se había visto,
vuelve a «sin ver»). Desde la 5.72 de CineCaptions, también equipo.php (la ficha técnica de cada equipo: JSON saneado y
vuelto a codificar, tope de 6 por equipo y hora con Retry-After), la acción equipo_ficha, la ficha en error_detalle y su
resumen en los equipos de detalle; 3 equipos ya la mandaron (Mariana, María Fernanda y Fernando).

Pide la cabecera X-Admin-Clave = «clave-de-prueba» y, como el servidor real, frena 15 minutos una IP después de 5 claves
malas. Nunca manda correos: «mandar» un correo solo lo anota.

Uso:
  python servidor_prueba.py                      escucha en http://127.0.0.1:8799
  python servidor_prueba.py --puerto 8800 --demora 0.4
  python servidor_prueba.py --sin-configurar     responde 503 (como si faltara admin_clave.php)
  python servidor_prueba.py --utc                MySQL en UTC, como en el hosting (la app debe mostrar las mismas horas)
  python servidor_prueba.py --viejo              como el admin.php anterior: sin las acciones ni los campos nuevos
  python servidor_prueba.py --sin-errores        como el admin.php de antes de la 5.71: con panel, pero sin los errores
                                                 (ni eliminar ventas)
  python servidor_prueba.py --sin-fichas         como el admin.php de la 5.71 (con los errores y las capturas), sin las
                                                 fichas de los equipos (equipo.php responde 503)
  python servidor_prueba.py --sin-ventanas       como el admin.php de la 5.72 (con las capturas y las fichas), sin la
                                                 segunda captura (la ventana de CineCaptions 5.73): ni con_ventana ni «cual»
  python servidor_prueba.py --github-caido       version_actual no puede leer el version.json de GitHub
  python servidor_prueba.py --pocos              casi sin datos: una venta en los últimos 30 días, sin canjes ni avisos
  python servidor_prueba.py --sin-cupones        como el admin.php de antes de los cupones (app 2.8): sin cupones ni el
                                                 cupón de cada venta
  python servidor_prueba.py --sin-borrar-errores como el admin.php publicado con la app 2.9: sin errores_borrar
Cupones (app 2.8): LANZAMIENTO (35 %, vencido, con las 3 ventas de $19), NAVIDAD (20 %, activo), AMIGOS100 (100 %, tope 5)
y BLACKFRIDAY (40 %, pausado), con las acciones cupones, cupon_crear, cupon_editar y cupon_borrar.
Los números de las ventas salen como texto ("2900"), igual que PDO en algunos servidores, para probar que la app los convierte.
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import math
import re
import threading
import time
import unicodedata
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CLAVE = 'clave-de-prueba'
VENTANA_FALLOS = 15 * 60
FORMATO = '%Y-%m-%d %H:%M:%S'
DESCARGA = 'https://github.com/AlejandroPiedrasanta/CineCaptions-releases/releases/latest'
NOTAS = {'5.54.0': 'Exporta los subtítulos hasta 2 veces más rápido, trae 6 estilos nuevos y corrige el cierre inesperado '
                   'en Mac al cambiar de proyecto.'}
TOPE_AVISOS_HORA = 90
VIGENCIA_VERSION = 10 * 60   # admin.php guarda 10 minutos lo que dice el version.json
# Lo que agregó el servidor nuevo: con --viejo responden «Acción desconocida.», como el admin.php anterior
ACCIONES_NUEVAS = {'panel', 'version_actual', 'versiones', 'candidatos_aviso', 'avisar_actualizacion', 'avisos', 'historial',
                   'nota', 'limite', 'editar_cliente', 'estadisticas', 'errores', 'error_detalle', 'error_visto',
                   'error_captura', 'eliminar_venta', 'equipo_ficha'}
# Lo de los errores de los clientes (desde la 5.71 de CineCaptions): con --sin-errores responden «Acción desconocida.» y
# panel no trae «errores», como el admin.php que estaba publicado antes. Eliminar ventas es todavía más nuevo: con
# --sin-errores (y con --viejo) tampoco está (ni el estado 'eliminadas', ni «eliminada» en las filas, ni el contador)
ACCIONES_ERRORES = {'errores', 'error_detalle', 'error_visto', 'error_captura'}
ACCIONES_ELIMINAR = {'eliminar_venta'}
# La ficha técnica de los equipos (CineCaptions 5.72, equipo.php): con --sin-fichas (y con los servidores de antes) no está
ACCIONES_FICHAS = {'equipo_ficha'}
FICHA_MAX_BYTES, FICHA_TOPE_HORA, FICHA_NIVELES = 16000, 6, 8   # (los de equipo.php)
FICHA_TEXTO_MAX, FICHA_CAMPO_MAX, FICHA_ELEMENTOS_MAX = 300, 40, 64
# Las capturas de errores.php: 900 KB por imagen y como mucho 30 errores CON captura por licencia (5.73: la de la pantalla y la
# de la ventana del mismo error cuentan como uno; se quitan las de los errores con la captura más vieja)
CAPTURA_MAX_BYTES, CAPTURAS_TOPE = 921600, 30
CUALES_CAPTURA = {'pantalla': 'captura', 'ventana': 'ventana'}   # «cual» de error_captura → dónde va en el error
# Las columnas nuevas de activaciones (telemetria.php): la ficha en JSON, su resumen, cuándo llegó (UTC) y el tope por hora
FICHA_VACIA = {'ficha': None, 'ficha_resumen': None, 'ficha_cuando': None, 'ficha_envios': None, 'ficha_ventana': None}
CAMPOS_NUEVOS_FILA = ('version', 'ultima_vez', 'equipos_desactualizados')
ALFABETO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
# 2.8: los cupones de descuento (cupones.php y las acciones de admin.php). Con --sin-cupones (y los servidores de antes) no están
ACCIONES_CUPONES = {'cupones', 'cupon_crear', 'cupon_editar', 'cupon_borrar'}
# App 2.10: borrar errores (errores_borrar). Con --sin-borrar-errores (el admin.php publicado con la app 2.9) y los de antes, no está
ACCIONES_BORRAR_ERRORES = {'errores_borrar'}
CAMPOS_CUPON = ('cupon_id', 'cupon', 'descuento')
PRECIO = 2900                     # PRECIO_CENTAVOS de config.php
CUPON_PRECIO_MINIMO = 100         # (el de cupones.php)
CODIGO_CUPON = re.compile(r'[A-Z0-9][A-Z0-9_-]{1,31}')


def _precio_con_cupon(precio, porcentaje):
    """precio_con_cupon() de cupones.php: 100 % = 0; si no, nunca menos de $1."""
    porcentaje = max(0, min(100, int(porcentaje)))
    if porcentaje >= 100:
        return 0
    return max(min(precio, CUPON_PRECIO_MINIMO), math.floor(precio * (100 - porcentaje) / 100 + 0.5))   # (round de PHP)
CORREO_QUE_FALLA = 'jose.nunez@example.com'   # su buzón rebota: así se prueban los correos que no salen


def _f(fecha):
    return fecha.strftime(FORMATO) if fecha else None


def _png_demo(ancho, alto, ventana=False):
    """Una «captura» inventada (PNG sin Qt): fondo oscuro, una barra arriba, dos paneles y una franja roja del error.
    ventana=True: la de la ventana de CineCaptions (5.73): la barra de arriba con el verde del programa."""
    import struct
    import zlib

    def color(x, y):
        if y < alto * 0.06:
            return (16, 185, 129) if ventana and x < ancho * 0.18 else (22, 33, 58)
        if alto * 0.42 < y < alto * 0.52 and ancho * 0.12 < x < ancho * 0.55:
            return (239, 68, 68)
        if alto * 0.14 < y < alto * 0.86 and (ancho * 0.05 < x < ancho * 0.62 or ancho * 0.66 < x < ancho * 0.95):
            return (18, 26, 46)
        return (11, 18, 32)
    filas = b''.join(b'\x00' + bytes(c for x in range(ancho) for c in color(x, y)) for y in range(alto))

    def trozo(tipo, datos):
        return struct.pack('>I', len(datos)) + tipo + datos + struct.pack('>I', zlib.crc32(tipo + datos) & 0xFFFFFFFF)
    return (b'\x89PNG\r\n\x1a\n' + trozo(b'IHDR', struct.pack('>IIBBBBB', ancho, alto, 8, 2, 0, 0, 0))
            + trozo(b'IDAT', zlib.compress(filas, 9)) + trozo(b'IEND', b''))


def _local_a_utc(texto):
    """«2026-10-29 15:30:00» en la hora de esta PC → la misma hora en UTC."""
    if not texto:
        return texto
    return _f(dt.datetime.strptime(texto, FORMATO).astimezone(dt.timezone.utc).replace(tzinfo=None))


def _utc_ahora():
    """UTC_TIMESTAMP() de MySQL (equipo.php guarda ficha_cuando en UTC, aunque MySQL vaya en otra hora)."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, microsecond=0)


def _ficha_limpia(valor):
    """Como ficha_limpia() de equipo.php: textos saneados (300 caracteres), nombres de campo saneados (40; los vacíos se
    van), listas y objetos de 64 elementos como mucho, números finitos, sí/no y null; lo demás, null."""
    if isinstance(valor, list):
        return [_ficha_limpia(x) for x in valor[:FICHA_ELEMENTOS_MAX]]
    if isinstance(valor, dict):
        limpia = {}
        for campo, dentro in valor.items():
            if len(limpia) >= FICHA_ELEMENTOS_MAX:
                break
            campo = _saneado(str(campo))[:FICHA_CAMPO_MAX]
            if campo:
                limpia[campo] = _ficha_limpia(dentro)
        return limpia
    if isinstance(valor, str):
        return _saneado(valor)[:FICHA_TEXTO_MAX]
    if isinstance(valor, float):
        return valor if math.isfinite(valor) else None
    return valor if isinstance(valor, (bool, int)) else None


def _niveles(valor):
    """Cuántos niveles de anidación tiene un JSON, como los cuenta json_decode() de PHP (un escalar suelto = 1)."""
    if isinstance(valor, dict):
        return 1 + max((_niveles(x) for x in valor.values()), default=0)
    if isinstance(valor, list):
        return 1 + max((_niveles(x) for x in valor), default=0)
    return 0


def _sin_constantes(texto):
    raise ValueError(texto)   # NaN, Infinity: Python los acepta y json_decode() de PHP no


def _plano(texto):
    """Como el LIKE de MySQL con utf8mb4: sin mayúsculas ni tildes."""
    texto = unicodedata.normalize('NFKD', str(texto or ''))
    return ''.join(c for c in texto if not unicodedata.combining(c)).casefold()


def _como_pdo(fila):
    """Los enteros como texto, igual que PDO con prepares emulados."""
    return {k: (str(v) if isinstance(v, int) and not isinstance(v, bool) else v) for k, v in fila.items()}


_ATEXTO = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
_CORREO = re.compile(rf'(?![^@]{{65}}){_ATEXTO}(?:\.{_ATEXTO})*@(?!.*[^.]{{64}})'
                     r'(?:[A-Za-z0-9]+(?:-+[A-Za-z0-9]+)*\.)+[A-Za-z][A-Za-z0-9]*(?:-+[A-Za-z0-9]+)*')
_DIRECCION = re.compile('[؜‎‏‪-‮⁦-⁩]')   # marcas que cambian la dirección del texto
_BORDES = ' \t\n\r\0\x0b'                                                    # lo que quita trim() de PHP


def _valido(correo):
    """Como correo_valido() de avisos_correo.php: el correo sin espacios en los bordes si FILTER_VALIDATE_EMAIL lo acepta
    (hasta 190 caracteres, sin espacios, comillas ni <>,;); None si no."""
    correo = correo.strip(_BORDES) if isinstance(correo, str) else ''
    return correo if len(correo) <= 190 and _CORREO.fullmatch(correo) else None


def _saneado(texto, lineas=False):
    """Como texto_saneado() de telemetria.php: sin caracteres de control ni marcas de dirección, sin espacios en los
    bordes. Con lineas quedan los saltos (como mucho una línea en blanco seguida); sin lineas, todo en una línea."""
    if not isinstance(texto, str):
        return ''
    for viejo, nuevo in (('\r\n', '\n'), ('\r', '\n'), ('\t', ' '), (' ', '\n'), (' ', '\n')):
        texto = texto.replace(viejo, nuevo)
    texto = _DIRECCION.sub('', texto)
    if lineas:
        texto = re.sub('[\x00-\x09\x0b-\x1f\x7f-\x9f]', '', texto)
        return re.sub('\n{3,}', '\n\n', re.sub('[  ]+\n', '\n', texto)).strip(_BORDES)
    return re.sub(' {2,}', ' ', re.sub('[\x00-\x1f\x7f-\x9f]+', ' ', texto)).strip(_BORDES)


def _partes(texto):
    """Como version_normal() de telemetria.php: dos o tres números de hasta 4 cifras, «5.54» == «5.54.0» y
    5.5.3 < 5.20. None si no se entiende («5.6-beta», «v5.54», «5.54.0.1») o no es texto."""
    m = re.fullmatch(r'[ \t\n\r\f\v]*([0-9]{1,4})\.([0-9]{1,4})(?:\.([0-9]{1,4}))?[ \t\n\r\f\v]*', texto) \
        if isinstance(texto, str) else None
    if not m:
        return None
    partes = [int(p) for p in m.groups() if p is not None]
    while len(partes) > 1 and partes[-1] == 0:
        partes.pop()
    return tuple(partes)


def _texto_version(texto):
    partes = _partes(texto)
    return None if partes is None else '.'.join(str(p) for p in (partes + (0,) if len(partes) == 1 else partes))


def _estado_version(version, ultima):
    propia = _partes(version)
    if propia is None:
        return 'sin_datos'
    nueva = _partes(ultima)
    if nueva is None:
        return 'desconocido'
    return 'al_dia' if propia >= nueva else 'desactualizado'


def _clave(semilla):
    """Una clave CC- con las letras que usa el servidor real (sin 0, 1, I ni O), siempre la misma para la semilla."""
    h = hashlib.sha256(semilla.encode('utf-8')).digest()
    letras = ''.join(ALFABETO[b % len(ALFABETO)] for b in h[:16])
    return 'CC-' + '-'.join(letras[i:i + 4] for i in range(0, 16, 4))


def _huella(semilla):
    """El ID de equipo que manda CineCaptions: «3F2A-91BC-04DE-77A1»."""
    h = hashlib.sha256(f'equipo:{semilla}'.encode('utf-8')).hexdigest()[:16].upper()
    return '-'.join(h[i:i + 4] for i in range(0, 16, 4))


def _monto(centavos, moneda):
    """El monto como lo escribe el historial de admin.php: number_format(monto / 100, 2) y la moneda («29.00 USD»)."""
    enteros, resto = divmod(int(centavos), 100)
    return f"{enteros:,}.{resto:02d} {moneda or ''}".strip()


def _nombre_de_equipo(a):
    """Como nombre_de_equipo() de admin.php: «DESKTOP-7Q2KD1F · 3F2A-…» entre comillas, o «un equipo sin nombre»."""
    nombre = str(a.get('nombre_equipo') or '').strip(_BORDES)
    return f'«{nombre}»' if nombre else 'un equipo sin nombre'


def _entero(valor):
    """Como entero() de admin.php: el número si is_numeric() lo acepta («12», 3.7 → 3); si no, 0."""
    if valor is None or isinstance(valor, bool):
        return 0
    try:
        return int(valor) if isinstance(valor, int) else int(float(str(valor).strip(' \t\n\r\v\f')))
    except (ValueError, OverflowError):
        return 0


def _campo(entrada, nombre, defecto):
    """$entrada[nombre] ?? defecto"""
    valor = entrada.get(nombre)
    return defecto if valor is None else valor


def _php_bool(valor):
    """(bool) de PHP: false, 0, 0.0, '', '0', null y [] son falsos; lo demás (también «false» como texto), verdadero."""
    if isinstance(valor, str):
        return valor not in ('', '0')
    return bool(valor)


def _filtro_bool(valor):
    """filter_var(valor, FILTER_VALIDATE_BOOLEAN) de PHP: verdadero solo con true, 1, «1», «true», «on» o «yes»."""
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in ('1', 'true', 'on', 'yes') if isinstance(valor, (int, str)) else False


class Datos:
    """Las tablas pedidos, licencias, activaciones, canjes, avisos, cambios_admin, ajustes y errores_equipos, en memoria.
    Con utc=True, «MySQL» va en UTC (como en el hosting): las fechas se guardan y salen en UTC. Si no, en la hora de esta
    PC. fecha_venta siempre va en UTC, porque admin.php la guarda con gmdate(). «ahora» fija la hora de arranque (para que
    dos servidores de prueba tengan exactamente los mismos datos)."""

    def __init__(self, ahora=None, utc=False, pocos=False):
        self.utc = utc
        self.desfase = dt.timedelta(0) if utc else dt.datetime.now().astimezone().utcoffset()   # hora de MySQL − UTC
        ahora = (ahora or dt.datetime.now()).replace(microsecond=0)
        hoy = ahora.replace(hour=0, minute=0, second=0)
        self.viejo = False            # como el admin.php anterior (sin las acciones ni los campos nuevos)
        self.sin_errores = False      # como el admin.php de antes de la 5.71 (con panel, sin los errores de los clientes)
        self.sin_fichas = False       # como el admin.php de la 5.71 (con los errores, sin las fichas de los equipos)
        self.sin_ventanas = False     # como el admin.php de la 5.72 (con las fichas, sin la captura de la ventana)
        self.sin_cupones = False      # como el admin.php de antes de los cupones (app 2.8): sin sus acciones ni campos
        self.sin_borrar_errores = False   # como el admin.php publicado con la app 2.9: sin errores_borrar
        self.github_caido = False     # version_actual no puede leer GitHub
        self.tope_hora, self.ventana_tope, self.envios_tope = TOPE_AVISOS_HORA, 3600, []   # avisos por hora (global)

        def dia(dias, hora, minuto=0, segundo=0):
            return (hoy - dt.timedelta(days=dias)).replace(hour=hora, minute=minuto, second=segundo)

        def hoy_hace(minutos):
            # siempre dentro de hoy, aunque el servidor arranque poco después de medianoche
            return max(hoy + dt.timedelta(minutes=1), ahora - dt.timedelta(minutes=minutos))

        self.licencias, self.pedidos, self.activaciones, self.canjes = [], [], [], []
        self.avisos, self.cambios = [], []
        self.bajas = {'paola.giron@example.com'}   # pidió no recibir más avisos de actualización
        publicada = (hoy - dt.timedelta(days=3)).strftime('%Y-%m-%d')
        self.github = {'version': '5.54.0', 'fecha': publicada, 'notas': NOTAS['5.54.0']}   # el version.json publicado
        self.ajustes = {'version': dict(self.github, consultado=_f(ahora - dt.timedelta(minutes=4)),
                                        cuando=time.time() - 240)}

        def licencia(clave, estado, nombre, correo, creada, limite=2, nota=None, nota_fecha=None):
            self.licencias.append({'id': len(self.licencias) + 1, 'clave': clave, 'estado': estado, 'limite': limite,
                                   'correo': correo, 'nombre': nombre, 'creada': _f(creada), 'nota': nota,
                                   'nota_fecha': _f(nota_fecha)})
            return len(self.licencias)

        def pedido(estado, nombre, correo, creado, monto=2900, licencia_id=None, enviado=1, reembolsado=None,
                   eliminada=None):
            numero = len(self.pedidos) + 1
            pagado = creado + dt.timedelta(minutes=2) if estado != 'pendiente' else None
            self.pedidos.append({
                'id': numero, 'token': f'{numero:032x}', 'checkout_id': f'ch_{numero:04d}k7x2q9mw{numero * 7919 % 10000:04d}',
                'estado': estado, 'correo': correo, 'nombre': nombre, 'monto': monto, 'moneda': 'USD',
                'pago_ids': f'pa_{numero:04d}r8v3n1' if estado != 'pendiente' else None, 'licencia_id': licencia_id,
                'correo_enviado': enviado if estado != 'pendiente' else 0, 'creado': _f(creado), 'pagado': _f(pagado),
                'eliminada': _f(eliminada),   # (pedidos.eliminada: se quitó de la lista desde la app)
                'cupon_id': None, 'cupon': None, 'descuento': None})   # (2.8: el cupón con que se compró)
            if reembolsado:   # se marcó desde la app (los reembolsos que llegan por webhook.php no guardan cuándo)
                self.anotar('marcar_reembolsado', licencia_id, 'Marcado como reembolsado desde la app',
                            f'Pedido #{numero}' + ('; su licencia quedó bloqueada.' if licencia_id else '.'), numero,
                            fecha=_f(reembolsado))

        def equipo(licencia_id, pc, creada, ultima, version=None, so=None, desde=None, antes=None):
            huella = _huella(f'{licencia_id}:{pc}')
            self.activaciones.append({'id': len(self.activaciones) + 1, 'licencia_id': licencia_id, 'equipo': huella,
                                      'nombre_equipo': f'{pc} · {huella}', 'creada': _f(creada), 'ultima': _f(ultima),
                                      'version': version, 'so': so, 'version_desde': _f(desde or (creada if version else None)),
                                      'version_anterior': antes, **FICHA_VACIA})

        def venta(creado, nombre, correo, monto=2900, estado='pagado', lic='activa', clave=None, equipos=(), enviado=1,
                  nota=None, nota_fecha=None, reembolsado=None):
            lid = None
            if estado != 'pendiente':
                lid = licencia(clave or _clave(nombre), lic, nombre, correo, creado, nota=nota, nota_fecha=nota_fecha)
            pedido(estado, nombre, correo, creado, monto, lid, enviado, reembolsado)
            for e in equipos:   # activado unos minutos después de pagar, salvo que diga otra cosa
                equipo(lid, e['pc'], e['creada'] or creado + dt.timedelta(minutes=6), e['ultima'], e['version'], e['so'],
                       e['desde'], e['antes'])
            return lid

        def E(pc, ultima, version=None, so=None, desde=None, antes=None, creada=None):
            return {'pc': pc, 'ultima': ultima, 'version': version, 'so': so, 'desde': desde, 'antes': antes, 'creada': creada}

        # Ventas de Recurrente, de la más vieja a la más nueva. La 5.52 salió hace 60 días, la 5.53 hace 20 y la 5.54 hace 3.
        venta(dia(70, 11, 20), 'Diego Herrera', 'diego.herrera@example.com', 1900, clave='CC-M7YC-5JQP-2NVK-X4RW')
        venta(dia(40, 16, 5), 'Daniela Ortiz', 'dani.ortiz@example.net', estado='reembolsado', lic='bloqueada',
              clave='CC-S4GH-6RTZ-9WBE-K8NQ')   # (reembolsada por webhook.php: en el historial no tiene fecha)
        venta(dia(35, 9, 48), 'Roberto Sandoval', 'roberto.sandoval@example.com', 1900, clave='CC-V2PD-7KMA-3QXL-F9HB',
              equipos=[E('PC-ROBERTO', dia(33, 18, 12))])
        venta(dia(28, 8, 52), 'Natalia Herrera', 'natalia.herrera@example.com',
              equipos=[E('NATALIA-PC', dia(3, 20, 41), '5.52', 'Windows 11')])
        venta(dia(26, 17, 35), 'Fernando Batres', 'fer.batres@example.com',
              equipos=[E('MacBook-Pro-de-Fernando', hoy_hace(240), '5.54', 'macOS 15.1', dia(1, 15, 2), '5.52')])
        venta(dia(23, 12, 10), 'Paola Girón', 'paola.giron@example.com',
              equipos=[E('PAOLA-EDICION', dia(4, 19, 8), '5.52', 'Windows 10')])
        venta(dia(21, 19, 48), 'Ricardo Alvarado', 'ricardo.alvarado@example.com',
              equipos=[E('RICARDO-PC', hoy_hace(400), '5.54', 'Windows 11', dia(1, 10, 3), '5.53'),
                       E('LAPTOP-RICARDO', dia(6, 13, 25), '5.53', 'Windows 11', dia(15, 9, 40), '5.52', dia(16, 18, 0))])
        venta(dia(19, 10, 22), 'Isabel Monzón', 'isabel.monzon@example.com',
              equipos=[E('iMac-de-Isabel', dia(1, 11, 7), '5.54', 'macOS 14.6', dia(2, 18, 30), '5.53')])
        venta(dia(17, 15, 16), 'Héctor Juárez', 'hector.juarez@example.com', equipos=[E('HECTOR-WORKSTATION', dia(12, 22, 3))])
        nombre_largo = 'María Fernanda de los Ángeles Castillo Ramírez'
        venta(dia(15, 21, 33), nombre_largo, 'maria.fernanda.castillo.ramirez.producciones@example.org',
              clave='CC-T6WN-4HQX-8ZRM-J3EC', nota_fecha=dia(10, 16, 20),
              nota='Trabaja con dos equipos: la workstation del estudio y una MacBook. Pidió la factura a nombre de '
                   'MF Producciones (NIT 4589217-3).',
              equipos=[E('MARIA-FERNANDA-WORKSTATION-RTX4090', ahora - dt.timedelta(hours=1, minutes=4), '5.54', 'Windows 11',
                         dia(2, 12, 4), '5.53'),
                       E('MacBook-Air-de-Maria', dia(8, 13, 30), '5.53', 'macOS 15.0', creada=dia(13, 9, 15))])
        venta(dia(13, 20, 5), 'Valentina Rosales', 'vale.rosales@example.com',
              equipos=[E('VALE-LAPTOP', dia(1, 21, 14), '5.53', 'Windows 11')])
        venta(dia(12, 11, 47), 'Jorge Luis Paz', 'jorgeluis.paz@example.com',
              equipos=[E('JORGE-PC', dia(2, 8, 55), '5.53', 'Windows 10')])
        venta(dia(11, 18, 30), 'Camila Torres', 'camila.torres@example.net', 1900,
              equipos=[E('CAMILA-MSI', dia(1, 17, 30), '5.54', 'Windows 11', dia(2, 20, 10), '5.53')])
        venta(dia(9, 14, 2), 'José Ñúñez', CORREO_QUE_FALLA, clave='CC-E8RJ-2MZW-6KQB-N5TA', enviado=0,
              equipos=[E('LAPTOP-JOSE', dia(5, 10, 41))])
        venta(dia(8, 9, 58), 'Miguel Ángel Barrios', 'miguel.barrios@example.com',
              equipos=[E('MIGUEL-PC', dia(1, 22, 40), '5.54', 'Windows 11', dia(1, 21, 0), '5.53')])
        venta(dia(7, 13, 25), 'Lucía Fernández', 'lucia.fernandez@example.com',
              equipos=[E('LUCIA-PC', hoy_hace(300), '5.53', 'Windows 11')])
        venta(dia(6, 20, 15), 'Kevin Morales', 'kevin.morales@example.net', estado='pendiente')
        venta(dia(5, 12, 27), 'Gabriela Méndez', 'gaby.mendez@example.com', estado='reembolsado', lic='bloqueada',
              clave='CC-B3KX-9PLC-5TVN-W7QH', reembolsado=dia(4, 9, 31))
        venta(dia(4, 16, 40), 'Sofía Rodríguez', 'sofia.rodriguez@example.com',
              equipos=[E('SOFIA-LAPTOP', dia(1, 9, 12), '5.54', 'Windows 11', dia(2, 11, 0), '5.53')])
        venta(dia(4, 21, 12), 'Andrés Cifuentes', 'andres.cifuentes@example.com',
              equipos=[E('MacBook-Pro-de-Andres', dia(1, 19, 55), '5.53', 'macOS 15.1')])
        venta(dia(3, 18, 50), 'Luis Fernando Gómez', 'luisfer.gomez@example.com', lic='bloqueada',
              clave='CC-Z5QV-6NAE-R8JD-M4XU',
              equipos=[E('DESKTOP-A1B2C3', dia(2, 9, 15), '5.54', 'Windows 11'),
                       E('PC-CYBER-04', dia(2, 11, 3), '5.54', 'Windows 10', creada=dia(3, 23, 50))])
        venta(dia(2, 10, 5), 'Pablo Estrada', 'pablo.estrada@example.com',
              equipos=[E('PABLO-PC', dia(1, 20, 18), '5.54', 'Windows 11')])
        venta(dia(2, 10, 31), 'Valeria Ruiz', 'valeria.r@example.com', estado='pendiente')
        venta(dia(1, 19, 42), 'Ana Sofía Castillo', 'anasofia.c@example.com', clave='CC-H9TR-3WMB-7XYK-C2PG',
              equipos=[E('PC-EDICION', dia(1, 22, 5), '5.54', 'Windows 11')])
        c = hoy_hace(180)
        venta(c, 'Carlos Andrés Pérez', 'carlos.perez@example.com', clave='CC-P4NC-8VDE-2JQS-K6LF',
              equipos=[E('DESKTOP-7Q2KD1F', hoy_hace(120), '5.54', 'Windows 10')])
        venta(hoy_hace(50), None, None, estado='pendiente')
        c = hoy_hace(27)
        venta(c, 'Mariana López', 'mariana.lopez@example.com', clave='CC-7K2M-Q9XA-4HBR-T3WZ',
              equipos=[E('ESTUDIO-MARIANA', hoy_hace(10), '5.54', 'Windows 11', creada=c + dt.timedelta(minutes=4)),
                       E('LAPTOP-HP-ML', hoy_hace(9), '5.54', 'Windows 11', creada=c + dt.timedelta(minutes=5))])
        # Un pago sin completar repetido que el dueño ya eliminó de la lista (va al final: los números de los demás no
        # cambian). No sale en la lista ni en los totales; está en el filtro «Eliminadas».
        pedido('pendiente', 'Kevin Morales', 'kevin.morales@example.net', dia(6, 20, 9), eliminada=dia(5, 10, 0))

        # 2.8: cupones de descuento (cupones.php). Las tres ventas de $19 se pagaron con LANZAMIENTO (ya vencido); NAVIDAD
        # está activo y sin usar, AMIGOS100 regala la licencia (con tope) y BLACKFRIDAY está pausado.
        def cupon(codigo, porcentaje, creado, usos_max=None, vence=None, activo=True, nota=None):
            self.cupones.append({'id': len(self.cupones) + 1, 'codigo': codigo, 'porcentaje': porcentaje,
                                 'usos_max': usos_max, 'vence': vence.strftime('%Y-%m-%d') if vence else None,
                                 'activo': 1 if activo else 0, 'nota': nota, 'creado': _f(creado)})
            return len(self.cupones)

        self.cupones = []
        lanzamiento = cupon('LANZAMIENTO', 35, dia(75, 9, 0), vence=dia(10, 0).date(), nota='Precio de lanzamiento en redes')
        for p in self.pedidos:
            if p['monto'] == 1900:
                p.update(cupon_id=lanzamiento, cupon='LANZAMIENTO', descuento=1000)
        cupon('NAVIDAD', 20, dia(2, 15, 30), usos_max=50, vence=(hoy + dt.timedelta(days=49)).date(),
              nota='Campaña de diciembre')
        cupon('AMIGOS100', 100, dia(1, 11, 0), usos_max=5, nota='Para regalar a colaboradores')
        cupon('BLACKFRIDAY', 40, dia(1, 12, 0), activo=False)

        # Canjes de Gumroad (con su propia CC-)
        def canje(clave, estado, nombre, correo, creado, venta_gumroad, bloqueo=None, ultimo=None, limite=2):
            lid = licencia(clave, estado, nombre, correo, creado, limite)
            self.canjes.append({'id': len(self.canjes) + 1, 'venta': f'gum_{len(self.canjes) + 1:03d}xq',
                                'gumroad_clave': f'{len(self.canjes) + 1:08X}-AAAA1111-BBBB2222-CCCC3333',
                                'licencia_id': lid, 'correo': correo, 'nombre': nombre, 'fecha_venta': _f(venta_gumroad),
                                'bloqueo': bloqueo, 'correo_enviado': 1, 'creado': _f(creado), 'ultimo': _f(ultimo or creado),
                                'revisado': None})
            return lid

        canje('CC-R9JB-4MVX-7TEK-H6QA', 'bloqueada', 'Fernando Ríos', 'fernando.rios@example.com', dia(50, 15, 10),
              dia(150, 12, 0), bloqueo='reembolsada')
        c = dia(20, 8, 55)
        andrea = canje('CC-G5NW-8QKT-3XHR-P2ZM', 'activa', 'Andrea Morales', 'andrea.morales@example.com', c,
                       dia(120, 17, 30), ultimo=dia(2, 16, 20))
        equipo(andrea, 'MacBook-de-Andrea', c + dt.timedelta(minutes=8), dia(2, 16, 21), '5.53', 'macOS 14.7',
               dia(19, 18, 40), '5.52')
        canje('CC-K3XP-6WZC-9NDA-B5TM', 'activa', None, 'lucia.vargas@example.org', dia(4, 11, 12), dia(200, 10, 45), limite=3)

        # Avisos de actualización que ya se mandaron (cada intento, aunque no saliera)
        def aviso(nombre, version, fecha, motivo=None):
            lic = next(l for l in self.licencias if l['nombre'] == nombre)
            self.avisos.append({'id': len(self.avisos) + 1, 'licencia_id': lic['id'], 'correo': lic['correo'],
                                'version': version, 'enviado': _f(fecha), 'ok': motivo is None, 'motivo': motivo})

        for n, nombre in enumerate(('Natalia Herrera', 'Paola Girón', 'Ricardo Alvarado')):
            aviso(nombre, '5.53', dia(19, 10, 0, n))
        for n, (nombre, motivo) in enumerate((('Valentina Rosales', None), ('Paola Girón', 'baja'),
                                              ('Natalia Herrera', 'fallo_envio'), ('Andrea Morales', None),
                                              ('Isabel Monzón', None), ('Ricardo Alvarado', None))):
            aviso(nombre, '5.54', dia(2, 9, 0, n), motivo)
        luis = next(l for l in self.licencias if l['nombre'] == 'Luis Fernando Gómez')
        self.anotar('licencia_estado', luis['id'], 'Licencia bloqueada desde la app', 'Antes estaba activa.',
                    fecha=_f(dia(2, 11, 30)))

        # Errores que mandó CineCaptions (errores.php), del más viejo al más nuevo: dos ya vistos de Fernando, uno de
        # Carlos y dos de Mariana sin ver (el último, un aviso). El programa cambia la carpeta del usuario por «~».
        def error(pc, nivel, titulo, mensaje, primera, ultima, veces=1, visto=0, origen=None, detalle=None):
            a = next(x for x in self.activaciones if x['nombre_equipo'].startswith(pc + ' · '))
            self.errores.append({'id': len(self.errores) + 1, 'licencia_id': a['licencia_id'], 'equipo': a['equipo'],
                                 'firma': hashlib.sha1(f'{origen or ""}|{mensaje}'.encode()).hexdigest(), 'nivel': nivel,
                                 'titulo': titulo, 'mensaje': mensaje, 'origen': origen, 'detalle': detalle,
                                 'version': a['version'], 'so': a['so'], 'veces': veces, 'primera': _f(primera),
                                 'ultima': _f(ultima), 'visto': visto})

        self.errores = []
        error('MacBook-Pro-de-Fernando', 'error', 'El motor de IA se cerró inesperadamente',
              'El proceso del motor Qwen terminó con el código -9 (memoria insuficiente).', dia(6, 14, 20), dia(2, 18, 5),
              7, 1, 'motor_qwen.arrancar',
              'CineCaptions 5.71 · macOS 15.1 · Apple M1 · 8 GB de memoria\n'
              'Pasó al transcribir «Entrevista en la montaña.mov» (12 min 40 s) con la voz en español.\n\n'
              'Traceback (most recent call last):\n'
              '  File "~/Aplicaciones/CineCaptions.app/Contents/Resources/motor_qwen/motor_texto.py", line 214, in arrancar\n'
              '    proceso.wait(timeout=120)\n'
              'RuntimeError: el motor terminó con el código -9 (el sistema lo cerró por falta de memoria)\n\n'
              'Memoria libre al empezar: 1,2 GB. El cliente vio: «Cierra otras aplicaciones y vuelve a intentarlo».')
        error('MacBook-Pro-de-Fernando', 'aviso', 'Sin conexión al buscar actualizaciones',
              'No se pudo leer el version.json de GitHub (se acabó el tiempo de espera).', dia(5, 9, 12), dia(1, 22, 30),
              2, 1, 'actualizaciones.revisar')
        error('DESKTOP-7Q2KD1F', 'error', 'Falta la fuente «Montserrat ExtraBold»',
              'El estilo del Tema 3 usa una fuente que no está instalada en este equipo; se usó Arial en su lugar.',
              hoy_hace(150), hoy_hace(125), 2, 0, 'fuentes.cargar',
              'CineCaptions 5.71 · Windows 10 Pro 22H2\nTema 3 · pack «Neón» · 86 subtítulos\n\nFuentes buscadas:\n'
              '  ~\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Montserrat-ExtraBold.ttf → no existe\n'
              '  C:\\Windows\\Fonts\\Montserrat-ExtraBold.ttf → no existe\n'
              'Se usó Arial (la de respaldo): los subtítulos se ven, pero sin la letra del estilo.')
        error('ESTUDIO-MARIANA', 'error', 'No se pudieron colocar los subtítulos en DaVinci Resolve',
              'Resolve no respondió a tiempo al crear la línea de tiempo «Subtítulos 1».', hoy_hace(20), hoy_hace(8), 3, 0,
              'resolve_bridge.colocar',
              'CineCaptions 5.71 · Windows 11 Pro 24H2 · DaVinci Resolve Studio 20.2\n'
              'Pasó al apretar GO en el Tema 2 con «Reseña cámara.mp4» (3 min 12 s, 148 subtítulos).\n\n'
              'Traceback (most recent call last):\n'
              '  File "~\\CineCaptions\\1_codigo\\resolve_bridge.py", line 812, in colocar\n'
              '    linea = proyecto.CrearLineaDeTiempo(nombre)\n'
              '  File "~\\CineCaptions\\1_codigo\\resolve_bridge.py", line 241, in _esperar\n'
              "    raise TimeoutError('Resolve no respondió en 30 s')\n"
              'TimeoutError: Resolve no respondió en 30 s\n\n'
              'Última acción: «Colocar en Resolve» → pista V3. Se reintentó 2 veces más.')
        # 5.72: ese error llegó con la captura de la pantalla y los datos del equipo; 5.73: también con la de la ventana de
        # CineCaptions (errores_ventanas; con --sin-ventanas el servidor no la tiene)
        self.errores[-1].update(
            equipo_datos='GPU NVIDIA GeForce RTX 3060 · RAM 16 GB (libre 2,1 GB) · CPU Intel Core i7-10700 (16 hilos) · '
                         'Pantalla 1920×1080 al 100 %',
            captura={'tipo': 'image/png', 'ancho': 960, 'alto': 540, 'bytes': 0, 'de': 'pantalla',
                     'creada': self.errores[-1]['ultima'], 'imagen': _png_demo(960, 540)},
            ventana={'tipo': 'image/png', 'ancho': 800, 'alto': 520, 'bytes': 0, 'de': 'ventana',
                     'creada': self.errores[-1]['ultima'], 'imagen': _png_demo(800, 520, ventana=True)})
        for cual in ('captura', 'ventana'):
            self.errores[-1][cual]['bytes'] = len(self.errores[-1][cual]['imagen'])
        error('ESTUDIO-MARIANA', 'aviso', 'La transcripción tardó más de lo normal',
              'Tardó 2 min 40 s; en este equipo lo normal es menos de 1 min.', hoy_hace(14), hoy_hace(14), 1, 0,
              'voz_ia.transcribir',
              'CineCaptions 5.71 · Windows 11 Pro 24H2 · NVIDIA RTX 3060 (CUDA)\n'
              'Video: «Reseña cámara.mp4» · modelo de voz: grande · idioma: español\n'
              'La tarjeta de video estaba ocupada por DaVinci Resolve (uso del 97 %).')
        self.siguiente_error = len(self.errores) + 1

        # Fichas técnicas que mandó CineCaptions 5.72 (equipo.php), en JSON como las guarda la base: la de Mariana (el equipo
        # de su error con captura) con avisos, un disco casi lleno, una puesta al día y un campo que la app no conoce; la de
        # María Fernanda (dos pantallas, dos discos, un fallo al poner al día) y la de Fernando (Mac, sin driver ni VRAM).
        # Los demás equipos todavía no la mandaron (CineCaptions 5.71 o antes). ficha_cuando va siempre en UTC.
        def iso(cuando):
            return cuando.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        def ficha(pc, hace_min, resumen, **campos):
            a = next(x for x in self.activaciones if x['nombre_equipo'].startswith(pc + ' · '))
            cuando = ahora - dt.timedelta(minutes=hace_min)
            datos = {'v': 1, 'cuando': iso(cuando), 'origen': 'app', 'app': {'version': a['version'], 'idioma': 'es'}, **campos}
            a.update(ficha=json.dumps(datos, ensure_ascii=False, separators=(',', ':')), ficha_resumen=resumen,
                     ficha_cuando=_local_a_utc(_f(cuando)))

        ficha('ESTUDIO-MARIANA', 12, 'GPU NVIDIA GeForce RTX 3060 · RAM 16 GB (libre 5,8 GB) · CPU Intel Core i7-10700 (16 hilos) · '
                                     'Pantalla 1920×1080 al 100 %',
              so={'nombre': 'Windows 11 Pro', 'version': '24H2', 'build': '26100.2314', 'arquitectura': 'x64'},
              cpu={'nombre': 'Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz', 'hilos': 16, 'avx2': True},
              ram={'total_mb': 16304, 'libre_mb': 5940},
              gpus=[{'nombre': 'NVIDIA GeForce RTX 3060', 'fabricante': 'NVIDIA', 'vram_mb': 12288, 'driver': '566.36',
                     'driver_fecha': '2024-12-05', 'principal': True},
                    {'nombre': 'Intel(R) UHD Graphics 630', 'fabricante': 'Intel', 'vram_mb': 1024, 'driver': '31.0.101.2125',
                     'driver_fecha': '2024-03-12', 'principal': False}],
              pantallas=[{'ancho': 1920, 'alto': 1080, 'escala': 100}],
              discos=[{'uso': 'programa', 'unidad': 'C:', 'libre_gb': 8.4, 'total_gb': 476.9},
                      {'uso': 'datos', 'unidad': 'D:', 'libre_gb': 612.0, 'total_gb': 1863.0}],
              resolve={'instalado': True, 'edicion': 'Studio', 'version': '20.2.0.11'},
              motores={'voz': {'instalado': True, 'torch': '2.15.0+cu132'}, 'auxiliar': {'instalado': True, 'python': '3.14.10'},
                       'whisper': True},
              componentes={'vcredist_x64': '14.44.35211', 'winget': '1.12.350'},
              revision=[{'id': 'vcredist', 'estado': 'ok', 'texto': 'Visual C++ 14.44 instalado'},
                        {'id': 'driver_gpu', 'estado': 'aviso',
                         'texto': 'Driver NVIDIA 566.36: funciona; con 595 o más la voz va más rápida'},
                        {'id': 'disco_programa', 'estado': 'falta',
                         'texto': 'Quedan 8,4 GB libres en C:; el modelo de voz grande necesita 12 GB'},
                        {'id': 'resolve', 'estado': 'ok', 'texto': 'DaVinci Resolve Studio 20.2 responde'}],
              puesta_al_dia={'cuando': iso(ahora - dt.timedelta(minutes=14)), 'hecho': ['Visual C++ 14.44 instalado'],
                             'pendiente': ['Driver de la GPU: no hay uno más nuevo en Windows Update'], 'fallos': []},
              red={'proxy': False, 'latencia_ms': 84})   # (un campo que la app no conoce: sale en bruto)
        ficha('MARIA-FERNANDA-WORKSTATION-RTX4090', 70, 'GPU NVIDIA GeForce RTX 4090 · RAM 64 GB (libre 41,2 GB) · CPU AMD Ryzen 9 '
                                                       '5900X (24 hilos) · Pantalla 3840×2160 al 150 %',
              so={'nombre': 'Windows 11 Pro', 'version': '24H2', 'build': '26100.2314', 'arquitectura': 'x64'},
              cpu={'nombre': 'AMD Ryzen 9 5900X 12-Core Processor', 'hilos': 24, 'avx2': True},
              ram={'total_mb': 65459, 'libre_mb': 42188},
              gpus=[{'nombre': 'NVIDIA GeForce RTX 4090', 'fabricante': 'NVIDIA', 'vram_mb': 24564, 'driver': '596.36',
                     'driver_fecha': '2026-10-01', 'principal': True}],
              pantallas=[{'ancho': 3840, 'alto': 2160, 'escala': 150}, {'ancho': 2560, 'alto': 1440, 'escala': 100}],
              discos=[{'uso': 'programa', 'unidad': 'C:', 'libre_gb': 120.5, 'total_gb': 930.4},
                      {'uso': 'datos', 'unidad': 'D:', 'libre_gb': 50.0, 'total_gb': 1863.0}],
              resolve={'instalado': True, 'edicion': 'Studio', 'version': '21.2.0.12'},
              motores={'voz': {'instalado': True, 'torch': '2.15.0+cu132'}, 'auxiliar': {'instalado': True, 'python': '3.14.10'},
                       'whisper': True},
              componentes={'vcredist_x64': '14.44.35211', 'winget': '1.12.350'},
              revision=[{'id': 'driver_gpu', 'estado': 'ok', 'texto': 'Driver NVIDIA 596.36 al día'}],
              puesta_al_dia={'cuando': iso(ahora - dt.timedelta(minutes=72)), 'hecho': [], 'pendiente': [],
                             'fallos': ['winget: no se pudo actualizar (falta el permiso de administrador)']})
        ficha('MacBook-Pro-de-Fernando', 300, 'GPU Apple M1 · RAM 8 GB (libre 1,2 GB) · CPU Apple M1 (8 hilos) · '
                                              'Pantalla 2560×1600 al 200 %',
              so={'nombre': 'macOS', 'version': '15.1', 'build': '24B83', 'arquitectura': 'arm64'},
              cpu={'nombre': 'Apple M1', 'hilos': 8},
              ram={'total_mb': 8192, 'libre_mb': 1210},
              gpus=[{'nombre': 'Apple M1', 'fabricante': 'Apple', 'principal': True}],
              pantallas=[{'ancho': 2560, 'alto': 1600, 'escala': 200}],
              discos=[{'uso': 'programa', 'unidad': '/', 'libre_gb': 41.2, 'total_gb': 245.1}],
              resolve={'instalado': True, 'edicion': 'Free', 'version': '20.2.0.11'},
              motores={'voz': {'instalado': False}, 'auxiliar': {'instalado': True, 'python': '3.14.10'}, 'whisper': True},
              revision=[{'id': 'memoria', 'estado': 'aviso',
                         'texto': '8 GB de memoria: el modelo de voz grande puede cerrarse por falta de memoria'}],
              puesta_al_dia={'cuando': iso(ahora - dt.timedelta(minutes=301)), 'hecho': [], 'pendiente': [], 'fallos': []})
        if pocos:   # --pocos: una venta en los últimos 30 días y otra más vieja, sin canjes ni avisos (los estados vacíos)
            self._dejar_pocos(('Diego Herrera', 'Lucía Fernández'))

        for c in self.canjes:   # gmdate() en canjes.php
            c['fecha_venta'] = _local_a_utc(c['fecha_venta'])
        if utc:
            self.ajustes['version']['consultado'] = _local_a_utc(self.ajustes['version']['consultado'])
            for tabla in (self.licencias, self.pedidos, self.activaciones, self.canjes, self.avisos, self.cambios,
                          self.errores):
                for fila in tabla:
                    for campo in ('creada', 'creado', 'pagado', 'ultima', 'ultimo', 'version_desde', 'nota_fecha', 'enviado',
                                  'fecha', 'primera', 'eliminada'):
                        if fila.get(campo):
                            fila[campo] = _local_a_utc(fila[campo])

    def _dejar_pocos(self, nombres):
        """Deja solo las ventas de esos clientes (con sus licencias, equipos e historial): así se ve la app con pocos datos.
        Los canjes, los avisos y los errores se van. Los equipos y los cambios se vuelven a numerar (los nuevos no chocan)."""
        self.pedidos = [p for p in self.pedidos if p['nombre'] in nombres]
        quedan = {p['licencia_id'] for p in self.pedidos if p['licencia_id']}
        self.licencias = [l for l in self.licencias if l['id'] in quedan]
        self.activaciones = [a for a in self.activaciones if a['licencia_id'] in quedan]
        self.cambios = [c for c in self.cambios if c['licencia_id'] in quedan]
        self.canjes, self.avisos, self.errores = [], [], []
        for tabla in (self.activaciones, self.cambios):
            for n, fila in enumerate(tabla, 1):
                fila['id'] = n

    # --- Horas
    def ahora(self):
        """NOW() de MySQL."""
        ahora = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) if self.utc else dt.datetime.now()
        return ahora.replace(microsecond=0)

    def de_local(self, fecha):
        """Una hora de esta PC → la hora de MySQL."""
        return fecha.astimezone(dt.timezone.utc).replace(tzinfo=None) if self.utc else fecha

    def a_local(self, texto):
        """Una fecha de MySQL → datetime en la hora de esta PC (la de Guatemala en admin.php)."""
        fecha = dt.datetime.strptime(texto, FORMATO)
        return fecha.replace(tzinfo=dt.timezone.utc).astimezone().replace(tzinfo=None) if self.utc else fecha

    # --- Ventas eliminadas desde la app (pedidos.eliminada)
    @property
    def con_eliminar(self):
        """El admin.php de ahora sabe eliminar ventas; el anterior (--viejo) y el de antes de la 5.71 (--sin-errores), no."""
        return not (self.viejo or self.sin_errores)

    def pedido_publico(self, p):
        """El pedido como lo manda admin.php (SELECT *): sin el token y, en el de antes, sin la columna «eliminada» (ni,
        antes de los cupones, sin cupon_id, cupon y descuento)."""
        return {k: v for k, v in p.items() if k != 'token' and (self.con_eliminar or k != 'eliminada')
                and (self.con_cupones or k not in CAMPOS_CUPON)}

    # --- Cupones de descuento (cupones.php; app 2.8)
    @property
    def con_cupones(self):
        """El admin.php de ahora tiene los cupones; el de antes (--sin-cupones) y los más viejos, no."""
        return self.con_ventanas and not self.sin_cupones

    @property
    def con_borrar_errores(self):
        """App 2.10: el admin.php nuevo borra errores (errores_borrar); el publicado con la 2.9 (--sin-borrar-errores) y los
        de antes, no."""
        return self.con_cupones and not self.sin_borrar_errores

    def cupon_real(self, cid):
        return next((c for c in self.cupones if c['id'] == cid), None)

    def fila_cupon(self, c):
        """Una fila de lista_cupones() de admin.php: con usos (ventas pagadas), ingresos, descontado, última venta y estado."""
        pagados = [p for p in self.pedidos if p.get('cupon_id') == c['id'] and p['estado'] == 'pagado']
        usos = len(pagados)
        hoy = dt.date.today().isoformat()   # (la de Guatemala en cupones.php)
        if not c['activo']:
            estado = 'pausado'
        elif c['vence'] and c['vence'] < hoy:
            estado = 'vencido'
        elif c['usos_max'] is not None and usos >= c['usos_max']:
            estado = 'agotado'
        else:
            estado = 'activo'
        return dict(c, usos=usos, ingresos=sum(p['monto'] or 0 for p in pagados),
                    descontado=sum(p['descuento'] or 0 for p in pagados),
                    ultima_venta=max((p['pagado'] for p in pagados), default=None), estado=estado,
                    precio_final=_precio_con_cupon(PRECIO, c['porcentaje']),
                    enlace=f"https://cinecaptions.shop/?cupon={urllib.parse.quote(c['codigo'])}")

    def lista_cupones(self):
        return [self.fila_cupon(c) for c in sorted(self.cupones, key=lambda c: (c['creado'], c['id']), reverse=True)]

    def visible(self, p):
        """VENTA_VISIBLE de admin.php: no se eliminó desde la app, o se pagó DESPUÉS de eliminarla (un pago sin completar
        que se eliminó y que el cliente terminó pagando vuelve solo)."""
        eliminada = p.get('eliminada')
        return not self.con_eliminar or not eliminada or bool(p.get('pagado') and p['pagado'] > eliminada)

    # --- Lecturas (como las consultas de admin.php)
    def licencia(self, lid):
        return next((dict(l) for l in self.licencias if l['id'] == lid), None)

    def licencia_real(self, lid):
        return next((l for l in self.licencias if l['id'] == lid), None)

    def pedido(self, pid):
        return next((p for p in self.pedidos if p['id'] == pid), None)

    def canje_de(self, lid):
        return next((c for c in self.canjes if c['licencia_id'] == lid), None)

    def pedido_de(self, lid, pagado=False):
        for p in sorted(self.pedidos, key=lambda p: -p['id']):
            if p['licencia_id'] == lid and (not pagado or p['estado'] == 'pagado'):
                return p
        return None

    def ultima(self):
        """La última versión publicada (la que guardó version_actual), como texto: «5.54»."""
        return _texto_version((self.ajustes.get('version') or {}).get('version'))

    def activaciones_de(self, lid):
        filas = [a for a in self.activaciones if a['licencia_id'] == lid]
        filas.sort(key=lambda a: a['ultima'] or '', reverse=True)
        return filas

    def equipos_de(self, lid):
        """equipos_de() de admin.php; desde la 5.72 (sin --sin-fichas), con ficha_resumen, ficha_cuando y con_ficha."""
        ultima = self.ultima()
        filas = []
        for a in self.activaciones_de(lid):
            fila = {'equipo': a['equipo'], 'nombre_equipo': a['nombre_equipo'], 'creada': a['creada'], 'ultima': a['ultima'],
                    'version': a['version'], 'version_desde': a['version_desde'], 'version_anterior': a['version_anterior'],
                    'so': a['so'], 'estado_version': _estado_version(a['version'], ultima)}
            if self.con_fichas:
                fila.update(ficha_resumen=a.get('ficha_resumen'), ficha_cuando=a.get('ficha_cuando'),
                            con_ficha=a.get('ficha') is not None)
            filas.append(fila)
        return filas

    # --- Fichas de los equipos (equipo.php, CineCaptions 5.72)
    @property
    def con_fichas(self):
        """El admin.php de ahora tiene las fichas; el de la 5.71 (--sin-fichas) y los de antes, no."""
        return not (self.viejo or self.sin_errores or self.sin_fichas)

    @property
    def con_ventanas(self):
        """El admin.php de ahora guarda y da la captura de la ventana (CineCaptions 5.73); el de la 5.72 (--sin-ventanas) y
        los de antes, no (errores.php ignora «ventana_<firma>» y error_captura ignora «cual»)."""
        return self.con_fichas and not self.sin_ventanas

    def ficha_de(self, lid, equipo):
        """ficha_de() de admin.php: {ficha (decodificada), resumen, cuando} o None (sin activar o todavía sin ficha)."""
        a = next((x for x in self.activaciones if x['licencia_id'] == lid and x['equipo'] == equipo), None)
        if not a or (a.get('ficha') is None and a.get('ficha_resumen') is None):
            return None
        ficha = json.loads(a['ficha']) if a.get('ficha') else None
        return {'ficha': ficha if isinstance(ficha, dict) else None, 'resumen': a.get('ficha_resumen'),
                'cuando': a.get('ficha_cuando')}

    def contar_equipos(self, lid):
        return sum(1 for a in self.activaciones if a['licencia_id'] == lid) if lid else 0

    def version_de(self, lid):
        """version (del equipo usado más recientemente), ultima_vez y equipos_desactualizados de una licencia."""
        filas = self.activaciones_de(lid) if lid else []
        ultima = self.ultima()
        return {'version': filas[0]['version'] if filas else None, 'ultima_vez': filas[0]['ultima'] if filas else None,
                'equipos_desactualizados': sum(1 for a in filas if _estado_version(a['version'], ultima) == 'desactualizado')}

    def _contactos(self, lic):
        """La licencia, sus compras (de la más nueva a la más vieja) y su canje: donde contactos_licencias de admin.php
        busca el nombre y el correo, en ese orden."""
        return ([lic] + sorted((p for p in self.pedidos if p['licencia_id'] == lic['id']), key=lambda p: -p['id'])
                + sorted((c for c in self.canjes if c['licencia_id'] == lic['id']), key=lambda c: -c['id']))

    def correo_de(self, lic):
        """A dónde van los avisos de una licencia (contactos_licencias de admin.php): licencias.correo si es válido; si
        no, el primero válido de sus compras o de su canje."""
        return next((c for c in (_valido(f['correo']) for f in self._contactos(lic)) if c), None)

    def correo_reenvio(self, lic):
        """A dónde va reenviar_correo, como en admin.php: solo si hay una compra pagada o un canje; al correo de la
        licencia si es válido y, si no, al de esa compra o ese canje."""
        propio = _valido(lic['correo'])
        for otro in (self.pedido_de(lic['id'], pagado=True), self.canje_de(lic['id'])):
            correo = otro and (propio or _valido(otro['correo']))
            if correo:
                return correo
        return None

    def cliente_de(self, lic):
        """El nombre del cliente (contactos_licencias): el de la licencia o, si no tiene, el de su compra o su canje."""
        return next((n for n in (str(f['nombre'] or '').strip(_BORDES) for f in self._contactos(lic)) if n), None)

    def anotar(self, accion, lid, titulo, detalle=None, pid=None, fecha=None):
        """Lo hecho desde la app queda en cambios_admin con su acción (sale en el historial, como en admin.php)."""
        self.cambios.append({'id': len(self.cambios) + 1, 'accion': accion, 'licencia_id': lid, 'pedido_id': pid,
                             'fecha': fecha or _f(self.ahora()), 'titulo': titulo, 'detalle': detalle})

    def fila_venta(self, p):
        lic = self.licencia(p['licencia_id']) if p['licencia_id'] else None
        fila = {'id': p['id'], 'estado': p['estado'], 'correo': p['correo'], 'nombre': p['nombre'], 'monto': p['monto'],
                'moneda': p['moneda'], 'creado': p['creado'], 'pagado': p['pagado'], 'checkout_id': p['checkout_id'],
                'correo_enviado': p['correo_enviado'], 'licencia_id': lic and lic['id'], 'clave': lic and lic['clave'],
                'licencia_estado': lic and lic['estado'], 'limite': lic and lic['limite'],
                'equipos': self.contar_equipos(lic and lic['id'])}
        if self.con_eliminar:
            fila['eliminada'] = p.get('eliminada')
        if self.con_cupones:   # (2.8: el cupón con que se compró)
            fila.update(cupon=p.get('cupon'), descuento=p.get('descuento'))
        fila.update(self.version_de(lic and lic['id']))
        return fila

    def fila_canje(self, c):
        lic = self.licencia(c['licencia_id']) if c['licencia_id'] else None
        fila = {'id': c['id'], 'correo': c['correo'], 'nombre': c['nombre'], 'fecha_venta': c['fecha_venta'],
                'bloqueo': c['bloqueo'], 'creado': c['creado'], 'ultimo': c['ultimo'], 'licencia_id': lic and lic['id'],
                'clave': lic and lic['clave'], 'licencia_estado': lic and lic['estado'], 'limite': lic and lic['limite'],
                'equipos': self.contar_equipos(lic and lic['id'])}
        fila.update(self.version_de(lic and lic['id']))
        return fila

    def ventas(self, estado='', buscar='', limite=500, desde=0):
        """lista_ventas de admin.php. estado 'eliminadas': solo las eliminadas, de cualquier estado de pago; los demás
        nunca las traen. (El admin.php de antes no conoce 'eliminadas': lo trata como '', la lista normal.)"""
        buscar = _plano(str(buscar or '').strip())
        if estado == 'eliminadas' and not self.con_eliminar:
            estado = ''
        filas = []
        for p in self.pedidos:
            if (estado == 'eliminadas') == self.visible(p):   # (las eliminadas, solo en su filtro; ahí, de todo estado)
                continue
            if estado in ('pagado', 'reembolsado', 'pendiente'):
                if p['estado'] != estado:
                    continue
            elif estado not in ('todos', 'eliminadas') and p['estado'] == 'pendiente':
                continue
            lic = self.licencia(p['licencia_id']) if p['licencia_id'] else None
            if buscar and not any(buscar in _plano(v) for v in (p['correo'], p['nombre'], lic and lic['clave'],
                                                                 p['checkout_id'], p['pago_ids'],
                                                                 p.get('cupon') if self.con_cupones else None)):
                continue
            filas.append(self.fila_venta(p))
        filas.sort(key=lambda f: (f['pagado'] or f['creado'], f['id']), reverse=True)
        return filas[desde:desde + limite]

    def lista_canjes(self, buscar='', limite=1000):
        buscar = _plano(str(buscar or '').strip())
        filas = []
        for c in self.canjes:
            lic = self.licencia(c['licencia_id']) if c['licencia_id'] else None
            if buscar and not any(buscar in _plano(v) for v in (c['correo'], c['nombre'], lic and lic['clave'])):
                continue
            filas.append(self.fila_canje(c))
        filas.sort(key=lambda f: (f['creado'], f['id']), reverse=True)
        return filas[:max(1, min(1000, limite))]

    def resumen(self):
        # «Hoy» y «este mes» en la hora local (la de Guatemala en admin.php), pasados a la hora de MySQL
        medianoche = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        hoy = _f(self.de_local(medianoche))
        mes = _f(self.de_local(medianoche.replace(day=1)))
        visibles = [p for p in self.pedidos if self.visible(p)]   # (las eliminadas no cuentan en los totales)
        pagados = [p for p in visibles if p['estado'] == 'pagado']
        de_hoy = [p for p in pagados if p['pagado'] >= hoy]
        del_mes = [p for p in pagados if p['pagado'] >= mes]
        reembolsados = [p for p in visibles if p['estado'] == 'reembolsado']
        ventas = {'pagadas': len(pagados), 'reembolsadas': len(reembolsados),
                  'pendientes': sum(1 for p in visibles if p['estado'] == 'pendiente'),
                  'ingresos': sum(p['monto'] for p in pagados), 'ventas_hoy': len(de_hoy),
                  'ingresos_hoy': sum(p['monto'] for p in de_hoy), 'ventas_mes': len(del_mes),
                  'ingresos_mes': sum(p['monto'] for p in del_mes),
                  'monto_reembolsado': sum(p['monto'] for p in reembolsados)}
        if self.con_eliminar:
            ventas['eliminadas'] = len(self.pedidos) - len(visibles)
        activas = sum(1 for l in self.licencias if l['estado'] == 'activa')
        monedas = sorted({p['moneda'] for p in visibles if p['moneda'] and p['estado'] != 'pendiente'})
        cuenta = self.contar_versiones()
        return {'ventas': ventas, 'licencias': {'activas': activas, 'bloqueadas': len(self.licencias) - activas},
                'equipos': len(self.activaciones), 'canjes': len(self.canjes), 'monedas': monedas,
                'hora_servidor': _f(self.ahora()),
                'versiones': {'ultima': self.ultima(), **{k: cuenta[k] for k in ('al_dia', 'desactualizados', 'sin_datos',
                                                                                   'activos_30d')}}}

    def contar_versiones(self):
        """Equipos de licencias activas: cuántos al día, desactualizados, sin datos y usados en los últimos 30 días."""
        ultima = self.ultima()
        activas = {l['id'] for l in self.licencias if l['estado'] == 'activa'}
        hace_30 = _f(self.ahora() - dt.timedelta(days=30))
        cuenta = {'al_dia': 0, 'desactualizados': 0, 'sin_datos': 0, 'activos_30d': 0, 'por_version': {}}
        for a in self.activaciones:
            if a['licencia_id'] not in activas:
                continue
            estado = _estado_version(a['version'], ultima)
            if estado == 'al_dia':
                cuenta['al_dia'] += 1
            elif estado == 'desactualizado':
                cuenta['desactualizados'] += 1
            elif estado == 'sin_datos':
                cuenta['sin_datos'] += 1
            if a['ultima'] and a['ultima'] >= hace_30:
                cuenta['activos_30d'] += 1
            texto = _texto_version(a['version'])
            cuenta['por_version'][texto] = cuenta['por_version'].get(texto, 0) + 1
        return cuenta

    def fila_equipo(self, a, lic):
        ultima = self.ultima()
        ped, c = self.pedido_de(lic['id']), self.canje_de(lic['id'])
        aviso = next((x for x in sorted(self.avisos, key=lambda x: (x['enviado'], x['id']), reverse=True)
                      if x['licencia_id'] == lic['id'] and x['ok']), None)
        return {'licencia_id': lic['id'], 'clave': lic['clave'], 'cliente': self.cliente_de(lic), 'correo': self.correo_de(lic),
                'origen': 'compra' if ped else 'canje' if c else None, 'pedido_id': ped and ped['id'],
                'licencia_estado': lic['estado'], 'equipo': a['equipo'], 'nombre_equipo': a['nombre_equipo'],
                'version': a['version'], 'version_desde': a['version_desde'], 'version_anterior': a['version_anterior'],
                'so': a['so'], 'creada': a['creada'], 'ultima': a['ultima'],
                'estado_version': _estado_version(a['version'], ultima),
                'aviso_version': aviso and aviso['version'], 'aviso_fecha': aviso and aviso['enviado']}

    def candidatos(self, version, a_quien):
        """Las licencias que recibirían el aviso de esa versión y por qué quedan fuera las demás (una vez cada una)."""
        candidatos = []
        fuera = {'baja': 0, 'ya_avisados': 0, 'bloqueadas': 0, 'sin_correo': 0, 'al_dia': 0}
        for lic in self.licencias:
            if lic['estado'] != 'activa':
                fuera['bloqueadas'] += 1
                continue
            correo = self.correo_de(lic)
            if not correo:
                fuera['sin_correo'] += 1
                continue
            if correo.casefold() in self.bajas:
                fuera['baja'] += 1
                continue
            lid = lic['id']
            filas = self.activaciones_de(lid)
            viejos = [a for a in filas if _estado_version(a['version'], version) == 'desactualizado']
            if a_quien == 'desactualizados' and not viejos:
                if any(_partes(a['version']) for a in filas):   # sin datos de versión no cuenta como «al día»
                    fuera['al_dia'] += 1
                continue
            if any(x['licencia_id'] == lid and x['ok'] and _partes(x['version']) == _partes(version) for x in self.avisos):
                fuera['ya_avisados'] += 1
                continue
            candidatos.append({'licencia_id': lid, 'cliente': self.cliente_de(lic), 'correo': correo, 'equipos': len(filas),
                               'equipos_desactualizados': len(viejos), 'ultima_vez': filas[0]['ultima'] if filas else None})
        # Como admin.php: los que usaron CineCaptions hace menos primero (y a la par, la licencia más vieja primero)
        candidatos.sort(key=lambda c: c['licencia_id'])
        candidatos.sort(key=lambda c: c['ultima_vez'] or '', reverse=True)
        return candidatos, fuera

    def historial(self, lic=None, ped=None):
        """historial_de() de admin.php, con los mismos tipos, títulos y detalles: todo lo que pasó con una licencia (con
        sus compras) o con un pedido sin licencia, el más nuevo primero (a la misma hora, el que se anotó después).
        El correo con la clave sale a la hora del pago o del canje; un reembolso, solo si se marcó desde la app."""
        eventos = []

        def evento(fecha, tipo, titulo, detalle=None):
            if fecha:
                eventos.append({'fecha': fecha, 'tipo': tipo, 'titulo': titulo, 'detalle': detalle, 'n': len(eventos)})

        pedidos = {p['id']: p for p in sorted(self.pedidos, key=lambda p: p['id']) if lic and p['licencia_id'] == lic['id']}
        if ped:
            pedidos[ped['id']] = ped
        for p in pedidos.values():
            monto = _monto(p['monto'], p['moneda']) if p['monto'] is not None else None
            evento(p['creado'], 'compra', 'Pedido creado', f"Pedido #{p['id']}" + (f' · {monto}' if monto else '') + '.')
            if p['pagado']:
                detalle = [x for x in (monto, 'después se reembolsó' if p['estado'] == 'reembolsado' else None) if x]
                evento(p['pagado'], 'pago', 'Pago confirmado', ' · '.join(detalle) + '.' if detalle else None)
                if p['correo_enviado']:
                    evento(p['pagado'], 'correo', 'Correo con la clave enviado', f"A {p['correo']}." if p['correo'] else None)
        if lic:
            for c in sorted((c for c in self.canjes if c['licencia_id'] == lic['id']), key=lambda c: c['id']):
                evento(c['creado'], 'canje', 'Canjeó su licencia de Gumroad',
                       f"Compra de Gumroad del {c['fecha_venta'][:10]}." if c['fecha_venta'] else None)
                if c['correo_enviado']:
                    evento(c['creado'], 'correo', 'Correo con la clave enviado', f"A {c['correo']}." if c['correo'] else None)
            for a in self.activaciones_de(lic['id']):
                nombre = _nombre_de_equipo(a)
                evento(a['creada'], 'activacion', f'Activada en {nombre}')
                if a['version'] is not None and a['version_desde']:
                    if a['version_anterior']:
                        nueva, antes = _partes(a['version']), _partes(a['version_anterior'])
                        vuelta = nueva is not None and antes is not None and nueva < antes
                        evento(a['version_desde'], 'version',
                               f"{'Volvió' if vuelta else 'Actualizó'} a la {a['version']} en {nombre}",
                               f"Antes tenía la {a['version_anterior']}.")
                    else:
                        evento(a['version_desde'], 'version', f"Usa la {a['version']} en {nombre}")
                if a['ultima'] != a['creada']:
                    detalle = [x for x in (f"Versión {a['version']}" if a['version'] is not None else None, a['so']) if x]
                    evento(a['ultima'], 'uso', f'Abrió CineCaptions en {nombre}', ' · '.join(detalle) + '.' if detalle else None)
        # Lo hecho desde la app: un reenvío de la clave sale como «correo» y un reembolso marcado como «reembolso». Los
        # avisos salen de la tabla avisos (también los que no salieron por un fallo del envío).
        tipos = {'reenviar_correo': 'correo', 'marcar_reembolsado': 'reembolso'}
        for x in self.cambios:
            if ((lic and x['licencia_id'] == lic['id']) or x['pedido_id'] in pedidos) and x['accion'] != 'avisar_actualizacion':
                evento(x['fecha'], tipos.get(x['accion'], 'admin'), x['titulo'], x['detalle'])
        if lic:
            for x in sorted(self.avisos, key=lambda x: x['id']):
                if x['licencia_id'] == lic['id'] and (x['ok'] or x['motivo'] == 'fallo_envio'):
                    evento(x['enviado'], 'aviso', f"Aviso de la {x['version']} enviado" if x['ok']
                           else f"No se pudo enviar el aviso de la {x['version']}", f"A {x['correo']}." if x['correo'] else None)
        eventos.sort(key=lambda e: (e['fecha'], e['n']), reverse=True)
        for e in eventos:
            del e['n']
        return eventos

    # --- Errores de los clientes (errores_equipos: uno por equipo y por firma)
    def resumen_errores(self):
        """resumen_errores() de admin.php: cuántos sin ver, de cuántos equipos, el id más alto y la última vez."""
        sin_ver = [e for e in self.errores if not e['visto']]
        return {'sin_ver': len(sin_ver), 'equipos': len({(e['licencia_id'], e['equipo']) for e in sin_ver}),
                'ultimo_id': max((e['id'] for e in sin_ver), default=None),
                'ultima': max((e['ultima'] for e in sin_ver), default=None)}

    def fila_error(self, e, detalle=False):
        """Una fila de lista_errores() de admin.php; con detalle=True, la de error_detalle (e.* con la licencia y el nombre
        del equipo). nombre_equipo es None si el equipo ya no está activado (el LEFT JOIN con activaciones)."""
        lic = self.licencia_real(e['licencia_id'])
        act = next((a for a in self.activaciones if a['licencia_id'] == e['licencia_id'] and a['equipo'] == e['equipo']), None)
        fila = {'id': e['id'], 'licencia_id': e['licencia_id'], 'clave': lic['clave'], 'cliente': lic['nombre'],
                'correo': lic['correo'], 'equipo': e['equipo'], 'nombre_equipo': act and act['nombre_equipo'],
                **{k: e[k] for k in ('nivel', 'titulo', 'mensaje', 'origen', 'version', 'so', 'veces', 'primera', 'ultima',
                                     'visto')},
                'equipo_datos': e.get('equipo_datos'), 'con_captura': bool(e.get('captura'))}   # (5.72)
        if self.con_ventanas:   # (5.73: la segunda captura, la de la ventana de CineCaptions)
            fila['con_ventana'] = bool(e.get('ventana'))
        if detalle:
            fila.update(firma=e['firma'], detalle=e['detalle'])
            for clave, cual in (('captura', 'captura'), ('captura_ventana', 'ventana')):
                if clave == 'captura_ventana' and not self.con_ventanas:
                    continue
                cap = e.get(cual)
                fila[clave] = {k: cap[k] for k in ('tipo', 'ancho', 'alto', 'bytes', 'de', 'creada')} if cap else None
            fila.pop('con_captura')   # (error_detalle da e.* de la tabla: sin con_captura, con «captura»; 5.73: con con_ventana)
            if self.con_fichas:       # (5.72: la ficha de ese equipo, o null)
                fila['ficha_equipo'] = self.ficha_de(e['licencia_id'], e['equipo'])
        return fila

    def lista_errores(self, entrada):
        """lista_errores() de admin.php: filtro 'sin_ver' | 'todos', licencia_id, buscar (en el error, el cliente, la clave
        y el nombre del equipo) y limite (300 si no se dice; de 1 a 1000). Los sin ver primero y después los más nuevos."""
        lid = _entero(entrada.get('licencia_id'))
        texto = _plano(str(entrada.get('buscar') or '').strip())
        filas = []
        for e in self.errores:
            lic = self.licencia_real(e['licencia_id'])
            if not lic or (entrada.get('filtro', 'todos') == 'sin_ver' and e['visto']) or (lid and e['licencia_id'] != lid):
                continue
            fila = self.fila_error(e)
            if texto and not any(texto in _plano(x) for x in (e['titulo'], e['mensaje'], e['origen'], lic['nombre'],
                                                              lic['correo'], lic['clave'], fila['nombre_equipo'])):
                continue
            filas.append(fila)
        filas.sort(key=lambda f: f['ultima'], reverse=True)
        filas.sort(key=lambda f: f['visto'])
        return filas[:max(1, min(1000, _entero(_campo(entrada, 'limite', 300)) or 300))]

    def limpiar_errores(self):
        """limpiar_errores() de admin.php: se van los de equipos que ya no están activados (se liberaron) y los de hace
        más de 90 días. Como mucho una vez por hora."""
        if time.time() - self.ajustes.get('errores_limpieza', 0) < 3600:
            return
        hace_90 = _f(self.ahora() - dt.timedelta(days=90))
        activados = {(a['licencia_id'], a['equipo']) for a in self.activaciones}
        self.errores = [e for e in self.errores if (e['licencia_id'], e['equipo']) in activados and e['ultima'] >= hace_90]
        self.ajustes['errores_limpieza'] = time.time()

    def recibir_error(self, licencia_id, equipo, firma, nivel, titulo, mensaje, origen=None, detalle=None, version=None,
                      so=None, veces=1, equipo_datos=None, captura=None, ventana=None):
        """El INSERT … ON DUPLICATE KEY UPDATE de errores.php: el mismo error (firma) en el mismo equipo suma «veces», pone
        la última vez y vuelve a «sin ver» (conserva su id); uno nuevo entra con el id siguiente. Devuelve el id.
        5.72: equipo_datos se reemplaza; la captura nueva reemplaza a la anterior (errores_capturas, una por error).
        5.73: lo mismo con la de la ventana (errores_ventanas), cada una por su lado."""
        ahora = _f(self.ahora())
        e = next((x for x in self.errores if (x['licencia_id'], x['equipo'], x['firma']) == (licencia_id, equipo, firma)), None)
        if e is None:   # (como AUTO_INCREMENT: un id nunca se repite, aunque se haya borrado el error que lo tenía)
            e = {'id': self.siguiente_error, 'licencia_id': licencia_id, 'equipo': equipo, 'firma': firma, 'veces': 0,
                 'primera': ahora, 'version': None, 'so': None}
            self.siguiente_error += 1
            self.errores.append(e)
        e.update(nivel=nivel, titulo=titulo, mensaje=mensaje, origen=origen, detalle=detalle, veces=e['veces'] + veces,
                 ultima=ahora, visto=0, version=version or e['version'], so=so or e['so'])
        if equipo_datos:
            e['equipo_datos'] = equipo_datos
        if captura:
            e['captura'] = captura
        if ventana:
            e['ventana'] = ventana
        return e['id']

    def recortar_capturas(self, licencia_id):
        """recortar_capturas() de errores.php: como mucho CAPTURAS_TOPE errores con captura por licencia (la de la pantalla
        y la de la ventana cuentan como uno); a los de la captura más vieja (después, el id más bajo) se les quitan las dos."""
        con = [e for e in self.errores if e['licencia_id'] == licencia_id and (e.get('captura') or e.get('ventana'))]
        con.sort(key=lambda e: (max(e[c]['creada'] for c in ('captura', 'ventana') if e.get(c)), e['id']), reverse=True)
        for e in con[CAPTURAS_TOPE:]:
            e.pop('captura', None)
            e.pop('ventana', None)


def atender(datos, entrada):
    """Una petición ya autenticada. Devuelve (código HTTP, respuesta)."""
    accion = str(entrada.get('accion') or '')
    ahora = datos.ahora()
    if ((datos.viejo and accion in ACCIONES_NUEVAS)
            or (datos.sin_errores and accion in ACCIONES_ERRORES | ACCIONES_ELIMINAR)
            or (not datos.con_fichas and accion in ACCIONES_FICHAS)
            or (not datos.con_cupones and accion in ACCIONES_CUPONES)
            or (not datos.con_borrar_errores and accion in ACCIONES_BORRAR_ERRORES)):
        return 400, {'error': 'Acción desconocida.'}

    if accion == 'resumen':
        return 200, {'ok': True, **datos.resumen()}

    def lista_ventas():   # (lista_ventas de admin.php: estado, buscar, limite 1..1000 y desde)
        return [_como_pdo(f) for f in datos.ventas(str(entrada.get('estado') or ''), entrada.get('buscar'),
                                                   max(1, min(1000, _entero(_campo(entrada, 'limite', 500)))),
                                                   max(0, min(10000000, _entero(_campo(entrada, 'desde', 0)))))]

    if accion == 'ventas':
        return 200, {'ok': True, 'ventas': lista_ventas()}

    if accion == 'canjes':
        return 200, {'ok': True, 'canjes': [_como_pdo(f) for f in datos.lista_canjes(entrada.get('buscar'))]}

    if accion == 'eliminar_venta':
        # Como admin.php: quita la venta de la lista y de los totales (eliminada = NOW()) o la restaura (eliminar = false).
        # No borra nada. Solo cambia si hace falta (eliminar una ya eliminada no le cambia la fecha). bloquear_licencia
        # (solo al eliminar) bloquea su licencia si estaba activa. Queda en el historial (cambios_admin).
        ped = datos.pedido(_entero(entrada.get('pedido_id')))
        if not ped:
            return 404, {'error': 'No existe esa venta.'}
        eliminar = 'eliminar' not in entrada or _filtro_bool(entrada['eliminar'])
        cambio = bloqueada = False
        if eliminar and datos.visible(ped):
            ped['eliminada'], cambio = _f(ahora), True
        elif not eliminar and ped.get('eliminada'):
            ped['eliminada'], cambio = None, True
        if eliminar and _php_bool(entrada.get('bloquear_licencia')) and ped['licencia_id']:   # (!empty() de PHP)
            lic = datos.licencia_real(ped['licencia_id'])
            if lic and lic['estado'] == 'activa':
                lic['estado'], bloqueada = 'bloqueada', True
        if cambio or bloqueada:
            quien = str(ped['nombre'] or ped['correo'] or f"pedido {ped['id']}").strip()
            datos.anotar('eliminar_venta', ped['licencia_id'],
                         ('Venta eliminada de la lista' if eliminar else 'Venta restaurada') + ' desde la app',
                         quien + (' · también se bloqueó su licencia.' if bloqueada else '.'), ped['id'])
        return 200, {'ok': True, 'eliminada': eliminar, 'licencia_bloqueada': bloqueada, 'resumen': datos.resumen()}

    if accion == 'panel':
        # Lo mismo que resumen + ventas + canjes en UNA petición, como admin.php: estado, buscar y limite son los de las
        # ventas, y buscar y limite también filtran los canjes (la app los pide aparte con canjes si hay una búsqueda)
        resumen = datos.resumen()
        limite_canjes = _entero(entrada['limite']) if entrada.get('limite') is not None else 1000
        respuesta = {'ok': True, 'resumen': resumen, 'ventas': lista_ventas(),
                     'canjes': [_como_pdo(f) for f in datos.lista_canjes(entrada.get('buscar'), limite_canjes)],
                     'hora_servidor': resumen['hora_servidor']}
        if not datos.sin_errores:   # (desde la 5.71: cuántos errores sin ver hay, para el contador y el aviso de la app)
            respuesta['errores'] = datos.resumen_errores()
        return 200, respuesta

    if accion == 'errores':
        datos.limpiar_errores()
        return 200, {'ok': True, 'errores': datos.lista_errores(entrada), 'resumen': datos.resumen_errores()}

    if accion == 'error_detalle':
        e = next((x for x in datos.errores if x['id'] == _entero(entrada.get('id'))), None)
        if not e or not datos.licencia_real(e['licencia_id']):
            return 404, {'error': 'Ese error ya no existe.'}
        return 200, {'ok': True, 'error_cliente': datos.fila_error(e, detalle=True)}

    if accion == 'error_captura':
        # 5.72: la captura de un error en base64 (la imagen va aparte de error_detalle para que el detalle sea ligero).
        # 5.73: cual = 'pantalla' (la de siempre, también sin «cual») | 'ventana'; otro valor, 400. El admin.php de la 5.72
        # (--sin-ventanas) no lo conoce: siempre da la de siempre y sin «cual» en la respuesta.
        cual = entrada.get('cual') if datos.con_ventanas and entrada.get('cual') not in (None, '') else 'pantalla'
        if not isinstance(cual, str) or cual not in CUALES_CAPTURA:
            return 400, {'error': 'Esa captura no se conoce.'}
        e = next((x for x in datos.errores if x['id'] == _entero(entrada.get('id'))), None)
        c = e and e.get(CUALES_CAPTURA[cual])
        if not c:
            return 404, {'error': 'Ese error no tiene la captura de la ventana.' if cual == 'ventana' else 'Ese error no tiene captura.'}
        respuesta = {'tipo': c['tipo'], 'ancho': c['ancho'], 'alto': c['alto'], 'de': c['de'], 'creada': c['creada'],
                     'base64': base64.b64encode(c['imagen']).decode('ascii')}
        return 200, {'ok': True, 'captura': ({'cual': cual, **respuesta} if datos.con_ventanas else respuesta)}

    if accion == 'equipo_ficha':
        # 5.72: la ficha técnica completa de un equipo (licencia_id + equipo); ficha_equipo = None si todavía no la mandó
        lid, equipo = _entero(entrada.get('licencia_id')), str(entrada.get('equipo') or '')
        if not lid or not equipo or not any(a['licencia_id'] == lid and a['equipo'] == equipo for a in datos.activaciones):
            return 404, {'error': 'Ese equipo ya no está activado.'}
        return 200, {'ok': True, 'ficha_equipo': datos.ficha_de(lid, equipo)}

    if accion == 'error_visto':
        # ids = [1, 2, …] o todos = true; visto = true (si no viene) o false para volver a marcarlo como nuevo
        visto = int(_php_bool(entrada['visto'])) if 'visto' in entrada else 1
        if _php_bool(entrada.get('todos')):
            cambiar = [e for e in datos.errores if e['visto'] != visto]
        else:
            ids = entrada.get('ids')
            ids = list(ids.values()) if isinstance(ids, dict) else ids if isinstance(ids, list) else []
            ids = [n for n in map(_entero, ids) if n][:1000]
            if not ids:
                return 400, {'error': 'Faltan los errores que marcar.'}
            cambiar = [e for e in datos.errores if e['id'] in ids and e['visto'] != visto]   # (MySQL cuenta solo los que cambian)
        for e in cambiar:
            e['visto'] = visto
        return 200, {'ok': True, 'cambiados': len(cambiar), 'resumen': datos.resumen_errores()}

    if accion == 'errores_borrar':
        # App 2.10: borra para siempre (con sus capturas, que viven dentro del error) todos = true o los de ids = [1, 2, …]
        if _php_bool(entrada.get('todos')):
            borrar = list(datos.errores)
        else:
            ids = entrada.get('ids')
            ids = list(ids.values()) if isinstance(ids, dict) else ids if isinstance(ids, list) else []
            ids = [n for n in map(_entero, ids) if n][:1000]
            if not ids:
                return 400, {'error': 'Faltan los errores que borrar.'}
            borrar = [e for e in datos.errores if e['id'] in ids]
        datos.errores = [e for e in datos.errores if e not in borrar]
        return 200, {'ok': True, 'borrados': len(borrar), 'resumen': datos.resumen_errores()}

    if accion == 'detalle':
        lic = datos.licencia(_entero(entrada.get('licencia_id')))
        ped = None
        if not lic and _entero(entrada.get('pedido_id')):
            ped = datos.pedido(_entero(entrada.get('pedido_id')))
            lic = datos.licencia(ped['licencia_id']) if ped and ped['licencia_id'] else None
        if not lic and not ped:
            return 404, {'error': 'No existe esa licencia ni ese pedido.'}
        if lic and not ped:
            ped = datos.pedido_de(lic['id'])
        canje = None
        if lic:
            c = datos.canje_de(lic['id'])
            if c:
                canje = {k: c[k] for k in ('id', 'correo', 'nombre', 'fecha_venta', 'bloqueo', 'creado', 'ultimo')}
        if ped:
            ped = datos.pedido_publico(ped)   # el token no sale del servidor
        return 200, {'ok': True, 'licencia': lic and _como_pdo(lic), 'pedido': ped and _como_pdo(ped),
                     'canje': canje and _como_pdo(canje), 'equipos': datos.equipos_de(lic['id']) if lic else [],
                     'version_ultima': datos.ultima()}

    if accion == 'licencia_estado':
        lic = datos.licencia_real(_entero(entrada.get('licencia_id')))
        estado = str(entrada.get('estado') or '')
        if not lic or estado not in ('activa', 'bloqueada'):
            return 400, {'error': 'Licencia o estado no válido.'}
        if lic['estado'] != estado:   # (como admin.php: solo se anota si cambió)
            datos.anotar('licencia_estado', lic['id'], 'Licencia reactivada desde la app' if estado == 'activa'
                         else 'Licencia bloqueada desde la app', f"Antes estaba {lic['estado']}.")
        lic['estado'] = estado
        return 200, {'ok': True, 'licencia': _como_pdo(dict(lic))}

    if accion == 'liberar_equipo':
        lic = datos.licencia(_entero(entrada.get('licencia_id')))
        equipo = str(entrada.get('equipo') or '')
        if not lic:
            return 400, {'error': 'Licencia no válida.'}
        quitados = [a for a in datos.activaciones if a['licencia_id'] == lic['id'] and (equipo == '' or a['equipo'] == equipo)]
        datos.activaciones = [a for a in datos.activaciones if a not in quitados]
        if quitados:
            nombres = ', '.join(_nombre_de_equipo(a) + (f" ({a['version']})" if a['version'] is not None else '')
                                for a in sorted(quitados, key=lambda a: a['ultima'] or '', reverse=True))
            datos.anotar('liberar_equipo', lic['id'], 'Equipos liberados desde la app' if equipo == ''
                         else 'Equipo liberado desde la app', nombres + '.')
        return 200, {'ok': True, 'liberados': len(quitados), 'equipos': datos.equipos_de(lic['id'])}

    if accion == 'reenviar_correo':
        lic = datos.licencia(_entero(entrada.get('licencia_id')))
        if not lic:
            return 400, {'error': 'Licencia no válida.'}
        correo = datos.correo_reenvio(lic)
        if not correo:
            return 400, {'error': 'Esta licencia no tiene una compra pagada ni un canje con correo válido.'}
        enviado = correo != CORREO_QUE_FALLA   # el correo de José rebota: así se prueba el error
        ped = datos.pedido_de(lic['id'], pagado=True)
        datos.anotar('reenviar_correo', lic['id'], 'Clave reenviada desde la app' if enviado else 'No se pudo reenviar la clave',
                     f'A {correo}.', ped and ped['id'])
        return 200, {'ok': enviado, 'correo': correo, 'error': None if enviado else 'El servidor no pudo enviar el correo.'}

    if accion == 'estado_recurrente':
        ped = datos.pedido(_entero(entrada.get('pedido_id')))
        if not ped or not ped['checkout_id']:
            return 400, {'error': 'Ese pedido no tiene un pago de Recurrente.'}
        if ped['estado'] == 'pendiente' and not ped['correo']:
            return 502, {'error': 'Recurrente respondió 404.'}
        # Recurrente manda created_at en ISO 8601 con su zona (aquí, en UTC)
        creado = (dt.datetime.strptime(ped['creado'], FORMATO) - datos.desfase).isoformat() + '.000Z'
        if ped['estado'] == 'pendiente':
            vencido = ped['creado'] < _f(ahora - dt.timedelta(days=3))
            info = {'estado': 'expired' if vencido else 'unpaid', 'pago_id': None, 'pago_estado': None}
        else:
            info = {'estado': 'paid', 'pago_id': ped['pago_ids'],
                    'pago_estado': 'refunded' if ped['estado'] == 'reembolsado' else 'succeeded'}
        info.update({'total': ped['monto'], 'moneda': ped['moneda'], 'creado': creado})
        return 200, {'ok': True, 'recurrente': info}

    if accion == 'marcar_reembolsado':
        ped = datos.pedido(_entero(entrada.get('pedido_id')))
        if not ped or ped['estado'] == 'pendiente':
            return 400, {'error': 'Solo se puede marcar un pedido pagado.'}
        ped['estado'] = 'reembolsado'
        for l in datos.licencias:
            if l['id'] == ped['licencia_id']:
                l['estado'] = 'bloqueada'
        datos.anotar('marcar_reembolsado', ped['licencia_id'], 'Marcado como reembolsado desde la app',
                     f"Pedido #{ped['id']}" + ('; su licencia quedó bloqueada.' if ped['licencia_id'] else '.'), ped['id'])
        return 200, {'ok': True, 'pedido': _como_pdo(datos.pedido_publico(ped))}

    if accion == 'version_actual':
        guardada = datos.ajustes.get('version')
        vencida = not guardada or time.time() - guardada['cuando'] > VIGENCIA_VERSION
        error = None
        if entrada.get('refrescar') or vencida:
            if datos.github_caido:   # (lo que dice bajar_manifiesto() de telemetria.php si GitHub no contesta en 4 s)
                error = 'GitHub tardó demasiado en responder.'
            else:
                guardada = dict(datos.github, consultado=_f(ahora), cuando=time.time())
                datos.ajustes['version'] = guardada
        guardada = guardada or {'consultado': _f(ahora)}   # (sin nada guardado: «consultado» = cuándo se intentó)
        # Como version_actual() de telemetria.php: la versión ya normalizada («5.54.0» del version.json → «5.54»)
        return 200, {'ok': True, 'version': _texto_version(guardada.get('version')), 'fecha': guardada.get('fecha'),
                     'notas': guardada.get('notas'), 'descarga': DESCARGA, 'consultado': guardada.get('consultado'),
                     'error': error}

    if accion == 'versiones':
        filtro = str(entrada.get('filtro') or 'todos')
        if filtro not in ('todos', 'desactualizados', 'al_dia', 'sin_datos'):
            return 400, {'error': 'Filtro no válido.'}
        filtro = {'desactualizados': 'desactualizado'}.get(filtro, filtro)
        buscar = _plano(str(entrada.get('buscar') or '').strip())
        equipos = []
        for a in sorted(datos.activaciones, key=lambda a: a['ultima'] or '', reverse=True):
            lic = datos.licencia(a['licencia_id'])
            if not lic:
                continue
            fila = datos.fila_equipo(a, lic)
            if filtro in ('desactualizado', 'al_dia', 'sin_datos') and fila['estado_version'] != filtro:
                continue
            # (admin.php busca en la clave, el nombre y el correo de la licencia, el nombre del equipo, la versión y el sistema)
            if buscar and not any(buscar in _plano(v) for v in (lic['clave'], lic['nombre'], lic['correo'],
                                                                 a['nombre_equipo'], a['version'], a['so'])):
                continue
            equipos.append(fila)
        cuenta = datos.contar_versiones()
        por_version = sorted(({'version': v, 'equipos': n} for v, n in cuenta['por_version'].items()),
                             key=lambda p: _partes(p['version']) or (), reverse=True)
        return 200, {'ok': True, 'ultima': datos.ultima(), 'equipos': [_como_pdo(e) for e in equipos],
                     'por_version': por_version, **{k: cuenta[k] for k in ('al_dia', 'desactualizados', 'sin_datos',
                                                                           'activos_30d')}}

    def version_de_aviso():
        """Como version_de_aviso() de admin.php: (la versión del aviso, None) o (None, el error 400)."""
        pedida = entrada.get('version')
        if pedida is not None and pedida != '':
            version = _texto_version(pedida)
            return (version, None) if version else (None, (400, {'error': 'Esa versión no se entiende. Escríbela como '
                                                                           '5.55 o 5.55.1.'}))
        version = datos.ultima()
        return (version, None) if version else (None, (400, {'error': 'No se pudo saber cuál es la última versión '
                                                                       'publicada. Indica la versión del aviso.'}))

    if accion == 'candidatos_aviso':
        a_quien = entrada.get('a_quien') or 'desactualizados'
        if a_quien not in ('desactualizados', 'todos'):
            return 400, {'error': 'a_quien tiene que ser desactualizados o todos.'}
        version, error = version_de_aviso()
        if error:
            return error
        candidatos, fuera = datos.candidatos(version, a_quien)
        return 200, {'ok': True, 'version': version, 'candidatos': candidatos, 'excluidos': fuera}

    if accion == 'avisar_actualizacion':
        lic = datos.licencia(_entero(entrada.get('licencia_id')))
        if not lic:
            return 400, {'error': 'Licencia no válida.'}
        version, error = version_de_aviso()
        if error:
            return error
        mensaje = _saneado(entrada.get('mensaje', ''), True)
        if len(mensaje) > 2000:
            return 400, {'error': 'El mensaje es muy largo: el máximo son 2000 caracteres.'}
        correo = datos.correo_de(lic)
        motivo, reintentar = None, None
        if lic['estado'] != 'activa':
            motivo = 'bloqueada'
        elif not correo:
            motivo = 'sin_correo'
        elif correo.casefold() in datos.bajas:
            motivo = 'baja'
        elif not entrada.get('forzar') and any(x['licencia_id'] == lic['id'] and x['ok']
                                               and _partes(x['version']) == _partes(version) for x in datos.avisos):
            motivo = 'ya_avisado'
        else:
            momento = time.monotonic()
            datos.envios_tope = [t for t in datos.envios_tope if momento - t < datos.ventana_tope]
            if len(datos.envios_tope) >= datos.tope_hora:
                motivo = 'limite'
                # lo que falta para que salga de la ventana el que deja el tope libre (espera_por_tope de admin.php)
                salida = datos.envios_tope[len(datos.envios_tope) - datos.tope_hora] if datos.tope_hora > 0 else momento
                reintentar = max(1, math.ceil(salida + datos.ventana_tope - momento))
            else:
                datos.envios_tope.append(momento)   # (cuenta para el tope aunque el correo no salga, como en admin.php)
                if correo == CORREO_QUE_FALLA:
                    motivo = 'fallo_envio'
        datos.avisos.append({'id': len(datos.avisos) + 1, 'licencia_id': lic['id'], 'correo': correo, 'version': version,
                             'enviado': _f(ahora), 'ok': motivo is None, 'motivo': motivo, 'mensaje': mensaje})
        return 200, {'ok': True, 'enviado': motivo is None, 'correo': correo, 'motivo': motivo, 'reintentar_en': reintentar}

    if accion == 'avisos':
        lid = _entero(entrada.get('licencia_id'))
        limite = max(1, min(1000, _entero(_campo(entrada, 'limite', 200))))
        filas = []
        for x in sorted(datos.avisos, key=lambda x: x['id'], reverse=True):
            if lid > 0 and x['licencia_id'] != lid:
                continue
            lic = datos.licencia(x['licencia_id'])
            filas.append({'id': x['id'], 'licencia_id': x['licencia_id'], 'cliente': lic and datos.cliente_de(lic),
                          'correo': x['correo'], 'version': x['version'], 'enviado': x['enviado'], 'ok': x['ok'],
                          'motivo': x['motivo']})
        return 200, {'ok': True, 'avisos': [_como_pdo(f) for f in filas[:limite]]}

    if accion == 'historial':
        lic, ped = datos.licencia(_entero(entrada.get('licencia_id'))), None
        if not lic and _entero(entrada.get('pedido_id')):
            ped = datos.pedido(_entero(entrada.get('pedido_id')))
            lic = datos.licencia(ped['licencia_id']) if ped and ped['licencia_id'] else None
        if not lic and not ped:
            return 404, {'error': 'No existe esa licencia ni ese pedido.'}
        return 200, {'ok': True, 'eventos': datos.historial(lic, ped)}

    if accion == 'nota':
        lic = datos.licencia_real(_entero(entrada.get('licencia_id')))
        if not lic:
            return 400, {'error': 'Licencia no válida.'}
        texto = _saneado(entrada.get('texto', ''), True)
        if len(texto) > 2000:
            return 400, {'error': 'La nota es muy larga: el máximo son 2000 caracteres.'}
        antes = lic['nota'] or ''
        if texto != antes:   # (si no cambió, queda la fecha de antes y no se anota nada)
            lic['nota'], lic['nota_fecha'] = (texto, _f(ahora)) if texto else (None, None)
            datos.anotar('nota', lic['id'], 'Nota borrada' if not texto else 'Nota añadida' if not antes else 'Nota cambiada',
                         f'Decía: {antes[:300]}' if antes else None)
        return 200, {'ok': True, 'nota': lic['nota'], 'nota_fecha': lic['nota_fecha']}

    if accion == 'limite':
        limite = _entero(entrada.get('limite'))
        if not 1 <= limite <= 10:
            return 400, {'error': 'El límite tiene que ser de 1 a 10 computadoras.'}
        lic = datos.licencia_real(_entero(entrada.get('licencia_id')))
        if not lic:
            return 400, {'error': 'Licencia no válida.'}
        activados = datos.contar_equipos(lic['id'])
        if limite < activados:
            return 400, {'error': f'Primero libera equipos: hay {activados} activados.'}
        if limite != lic['limite']:
            datos.anotar('limite', lic['id'], 'Límite de equipos cambiado desde la app',
                         f"De {lic['limite']} a {limite} computadoras.")
            lic['limite'] = limite
        return 200, {'ok': True, 'licencia': _como_pdo(dict(lic))}

    if accion == 'editar_cliente':
        # Como admin.php: lo que no viene (o viene en null) no cambia; el nombre en una línea y el correo validado
        lic = datos.licencia_real(_entero(entrada.get('licencia_id')))
        if not lic:
            return 400, {'error': 'Licencia no válida.'}
        cambios = []
        if entrada.get('nombre') is not None:
            nombre = _saneado(entrada['nombre'])
            if not isinstance(entrada['nombre'], str) or len(nombre) > 190:
                return 400, {'error': 'El nombre no es válido: puede tener hasta 190 caracteres.'}
            if (nombre or None) != (str(lic['nombre'] or '').strip(_BORDES) or None):
                cambios.append(('nombre', f"Nombre: «{lic['nombre'] or ''}» → «{nombre}»", nombre or None))
        if entrada.get('correo') is not None:
            correo = _valido(entrada['correo'])
            if correo is None:
                return 400, {'error': 'Ese correo no es válido.'}
            if correo != (lic['correo'] or ''):
                cambios.append(('correo', f"Correo: {lic['correo'] or '(sin correo)'} → {correo}", correo))
        if entrada.get('nombre') is None and entrada.get('correo') is None:
            return 400, {'error': 'No hay nada que cambiar.'}
        for campo, _texto, nuevo in cambios:
            lic[campo] = nuevo
            for p in datos.pedidos:
                if p['licencia_id'] == lic['id']:
                    p[campo] = nuevo
        if cambios:
            datos.anotar('editar_cliente', lic['id'], 'Datos del cliente cambiados desde la app',
                         ' · '.join(c[1] for c in cambios) + '.')
        return 200, {'ok': True, 'licencia': _como_pdo(dict(lic))}

    if accion == 'estadisticas':
        # Como ventas_por_dia de admin.php: cada día (el de Guatemala allá, el de esta PC aquí) de los últimos «dias»,
        # contando hoy. Un reembolso cuenta en el día de la compra: la base no guarda cuándo se reembolsó.
        dias = max(7, min(365, _entero(_campo(entrada, 'dias', 30))))
        hoy = dt.datetime.now().date()
        filas = {(hoy - dt.timedelta(days=n)): {'ventas': 0, 'ingresos': 0, 'reembolsos': 0} for n in range(dias)}
        for p in datos.pedidos:
            if not datos.visible(p):   # (una venta eliminada no sale en la gráfica)
                continue
            fila = filas.get(datos.a_local(p['pagado'] or p['creado']).date()) if p['estado'] in ('pagado', 'reembolsado') else None
            if fila and p['estado'] == 'pagado':
                fila['ventas'] += 1
                fila['ingresos'] += p['monto'] if (p['moneda'] or 'USD').upper() == 'USD' else 0   # (solo la moneda de la tienda)
            elif fila:
                fila['reembolsos'] += 1
        return 200, {'ok': True, 'moneda': 'USD',
                     'dias': [_como_pdo({'fecha': d.isoformat(), **filas[d]}) for d in sorted(filas)]}

    # ---- 2.8: cupones de descuento, como admin.php (lista_cupones, datos_cupon y las cuatro acciones)
    if accion == 'cupones':
        return 200, {'ok': True, 'cupones': [_como_pdo(c) for c in datos.lista_cupones()], 'precio': PRECIO,
                     'moneda': 'USD', 'hoy': dt.date.today().isoformat(), 'sitio': 'https://cinecaptions.shop'}

    def datos_cupon():
        """datos_cupon() de admin.php: solo lo que viene, revisado. (datos, error)"""
        cambios = {}
        if 'porcentaje' in entrada:
            p = entrada['porcentaje']
            if isinstance(p, bool) or not isinstance(p, (int, float, str)) or not re.fullmatch(r'\d{1,3}', str(p).strip()) \
                    or not 1 <= int(p) <= 100:
                return None, 'El descuento tiene que ser de 1 a 100 %.'
            cambios['porcentaje'] = int(p)
        if 'usos_max' in entrada:
            u = entrada['usos_max']
            if u in (None, '', 0, '0'):
                cambios['usos_max'] = None
            elif isinstance(u, bool) or not re.fullmatch(r'\d{1,7}', str(u).strip()) or not 1 <= int(u) <= 1000000:
                return None, 'El tope de usos tiene que ser un número de 1 en adelante (o vacío: sin tope).'
            else:
                cambios['usos_max'] = int(u)
        if 'vence' in entrada:
            fecha = entrada['vence']
            if fecha in (None, ''):
                cambios['vence'] = None
            else:
                try:
                    valida = isinstance(fecha, str) and dt.date.fromisoformat(fecha).isoformat() == fecha
                except ValueError:
                    valida = False
                if not valida:
                    return None, 'La fecha de vencimiento no es válida (AAAA-MM-DD).'
                cambios['vence'] = fecha
        if 'nota' in entrada:
            nota = _saneado(entrada['nota']) if isinstance(entrada['nota'], str) else ''
            if entrada['nota'] is not None and not isinstance(entrada['nota'], str) or len(nota) > 190:
                return None, 'La nota puede tener hasta 190 caracteres.'
            cambios['nota'] = nota or None
        if 'activo' in entrada:
            cambios['activo'] = 1 if _filtro_bool(entrada['activo']) else 0
        return cambios, None

    def texto_cupon(c):
        return (f"{c['porcentaje']} %" + (' (licencia gratis)' if c['porcentaje'] >= 100 else '')
                + ' · ' + ('sin tope de usos' if c['usos_max'] is None else f"tope {c['usos_max']} usos")
                + ' · ' + ('no vence' if c['vence'] is None else f"vence el {c['vence']}")
                + ('' if c['activo'] else ' · pausado'))

    if accion == 'cupon_crear':
        codigo = re.sub(r'\s+', '', str(entrada.get('codigo') or '')).upper() if isinstance(entrada.get('codigo'), str) else ''
        if not CODIGO_CUPON.fullmatch(codigo):
            return 400, {'error': 'El código tiene que tener de 2 a 32 letras, números, guiones o guiones bajos (sin espacios).'}
        if 'porcentaje' not in entrada:
            return 400, {'error': 'Falta el descuento.'}
        cambios, error = datos_cupon()
        if error:
            return 400, {'error': error}
        if any(c['codigo'] == codigo for c in datos.cupones):
            return 409, {'error': f'Ya existe un cupón con el código {codigo}.'}
        nuevo = {'id': max((c['id'] for c in datos.cupones), default=0) + 1, 'codigo': codigo, 'usos_max': None,
                 'vence': None, 'activo': 1, 'nota': None, 'creado': _f(ahora)}
        nuevo.update(cambios)
        datos.cupones.append(nuevo)
        fila = datos.fila_cupon(nuevo)
        datos.anotar('cupon', None, f'Cupón {codigo} creado desde la app', texto_cupon(fila) + '.')
        return 200, {'ok': True, 'cupon': _como_pdo(fila)}

    if accion == 'cupon_editar':
        c = datos.cupon_real(_entero(entrada.get('id')))
        if not c:
            return 404, {'error': 'Ese cupón ya no existe.'}
        cambios, error = datos_cupon()
        if error:
            return 400, {'error': error}
        if not cambios:
            return 400, {'error': 'No hay nada que cambiar.'}
        antes = dict(c)
        c.update(cambios)
        if texto_cupon(c) != texto_cupon(antes) or c['nota'] != antes['nota']:
            titulo = (f"Cupón {c['codigo']}" + (' reactivado' if c['activo'] else ' pausado') if list(cambios) == ['activo']
                      else f"Cupón {c['codigo']} cambiado") + ' desde la app'
            datos.anotar('cupon', None, titulo, f'Antes: {texto_cupon(antes)}. Ahora: {texto_cupon(c)}.')
        return 200, {'ok': True, 'cupon': _como_pdo(datos.fila_cupon(c))}

    if accion == 'cupon_borrar':
        c = datos.cupon_real(_entero(entrada.get('id')))
        if not c:
            return 404, {'error': 'Ese cupón ya no existe.'}
        fila = datos.fila_cupon(c)
        datos.cupones.remove(c)
        datos.anotar('cupon', None, f"Cupón {c['codigo']} borrado desde la app", f"{texto_cupon(c)} · {fila['usos']} ventas con él.")
        return 200, {'ok': True, 'borrado': c['id']}

    return 400, {'error': 'Acción desconocida.'}


def _sin_campos_nuevos(accion, respuesta):
    """--viejo: la respuesta como la daba el admin.php anterior (sin versión, notas ni el bloque de versiones)."""
    for lista in ('ventas', 'canjes'):
        filas = respuesta.get(lista)
        if not isinstance(filas, list):   # (en el resumen, «ventas» son los totales, no filas)
            continue
        for fila in filas:
            for campo in CAMPOS_NUEVOS_FILA:
                fila.pop(campo, None)
    respuesta.pop('versiones', None)
    respuesta.pop('version_ultima', None)
    if not isinstance(respuesta.get('errores'), list):   # (el resumen de errores de panel; la lista nunca llega aquí)
        respuesta.pop('errores', None)
    if isinstance(respuesta.get('licencia'), dict):
        respuesta['licencia'] = {k: v for k, v in respuesta['licencia'].items() if k not in ('nota', 'nota_fecha')}
    if accion in ('detalle', 'liberar_equipo'):
        respuesta['equipos'] = [{k: e[k] for k in ('equipo', 'nombre_equipo', 'creada', 'ultima')}
                                for e in respuesta.get('equipos') or []]
    return respuesta


def atender_licencia(datos, campos, agente):
    """licencia.php (lo que usa el programa CineCaptions), con la telemetría: en activar y verificar con respuesta
    «activa» se guarda la versión (campo «version» o User-Agent «CineCaptions/5.54») y el sistema («so»). La telemetría
    nunca cambia la respuesta: si algo falla ahí, se sigue igual."""
    accion = campos.get('accion', '')
    clave = re.sub(r'\s+', '', campos.get('clave', '')).upper()
    equipo = campos.get('equipo', '').strip()[:128]
    nombre = campos.get('nombre_equipo', '').strip()[:190]
    if accion not in ('activar', 'verificar', 'desactivar') or not equipo:
        return 400, {'valida': False, 'codigo': 'error', 'error': 'Faltan datos.'}
    lic = next((l for l in datos.licencias if l['clave'] == clave), None)
    if not lic:
        return 404, {'valida': False, 'codigo': 'invalida', 'error': 'La clave no es válida.'}
    ahora = _f(datos.ahora())
    act = next((a for a in datos.activaciones if a['licencia_id'] == lic['id'] and a['equipo'] == equipo), None)
    if accion == 'desactivar':
        datos.activaciones = [a for a in datos.activaciones if a is not act]
        return 200, {'valida': True, 'codigo': 'desactivada'}
    if lic['estado'] != 'activa':
        return 403, {'valida': False, 'codigo': 'bloqueada', 'error': 'La licencia está bloqueada.'}
    if act:
        act['ultima'] = ahora
        act['nombre_equipo'] = nombre or act['nombre_equipo']
    elif accion == 'verificar':
        return 404, {'valida': False, 'codigo': 'desactivada', 'error': 'Esta computadora no está activada con la licencia.'}
    else:
        if datos.contar_equipos(lic['id']) >= lic['limite']:
            return 409, {'valida': False, 'codigo': 'en_uso', 'error': 'La licencia ya está activada en el máximo de computadoras.'}
        act = {'id': len(datos.activaciones) + 1, 'licencia_id': lic['id'], 'equipo': equipo, 'nombre_equipo': nombre,
               'creada': ahora, 'ultima': ahora, 'version': None, 'so': None, 'version_desde': None, 'version_anterior': None,
               **FICHA_VACIA}
        datos.activaciones.append(act)
    try:   # registrar_telemetria() de telemetria.php: la versión ya normalizada («5.54.0» → «5.54») o nada
        version = _texto_version(campos.get('version'))
        m = re.match(r'CineCaptions/([0-9]{1,4}\.[0-9]{1,4}(?:\.[0-9]{1,4})?)(?![A-Za-z0-9_.-])', agente or '')
        version = version or (_texto_version(m.group(1)) if m else None)
        so = _saneado(campos.get('so'))[:80] or None
        if version and version != act['version']:
            if act['version']:
                act['version_anterior'] = act['version']
            act['version'], act['version_desde'] = version, ahora
        if so:
            act['so'] = so
    except Exception:   # la telemetría nunca rompe la licencia
        pass
    return 200, {'valida': True, 'codigo': 'activa', 'licencia': {'clave': lic['clave'], 'estado': lic['estado'],
                                                                   'limite': lic['limite'],
                                                                   'usados': datos.contar_equipos(lic['id'])}}


def _multipart(tipo, crudo):
    """(campos, archivos) de un formulario multipart (lo que manda CineCaptions 5.72 con las capturas)."""
    import email.parser
    import email.policy
    msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(b'Content-Type: ' + tipo.encode('ascii') + b'\r\n\r\n' + crudo)
    campos, archivos = {}, {}
    for parte in msg.iter_parts():
        nombre = parte.get_param('name', header='content-disposition')
        if parte.get_filename():
            archivos[nombre] = parte.get_payload(decode=True)
        else:
            campos[nombre] = parte.get_payload(decode=True).decode('utf-8', 'replace')
    return campos, archivos


def _datos_imagen(datos):
    """(tipo, ancho, alto) de un JPEG o PNG de verdad (como getimagesizefromstring de errores.php) o None."""
    if datos[:8] == b'\x89PNG\r\n\x1a\n' and len(datos) > 24:
        return 'image/png', int.from_bytes(datos[16:20], 'big'), int.from_bytes(datos[20:24], 'big')
    if datos[:3] == b'\xff\xd8\xff':
        i = 2
        while i + 9 < len(datos):
            if datos[i] != 0xFF:
                return None
            marca, largo = datos[i + 1], int.from_bytes(datos[i + 2:i + 4], 'big')
            if marca in (0xC0, 0xC1, 0xC2):
                return 'image/jpeg', int.from_bytes(datos[i + 7:i + 9], 'big'), int.from_bytes(datos[i + 5:i + 7], 'big')
            i += 2 + largo
    return None


def atender_errores_php(datos, campos, agente, archivos=None):
    """errores.php (lo que manda CineCaptions desde la 5.71 cuando a un cliente le sale un error): clave, equipo, version,
    so y errores = JSON [{firma, nivel, titulo, mensaje, origen, detalle, veces}, …] (20 como mucho). Solo de un equipo
    activado en esa licencia. Con --sin-errores responde 503, como si la tabla todavía no existiera.
    Desde la 5.72: equipo_datos y una captura por error («captura_<firma>», JPEG o PNG de 900 KB como mucho).
    5.73: y la de la ventana de CineCaptions («ventana_<firma>»), aunque no venga la otra; con --sin-ventanas se ignora."""
    archivos = archivos or {}
    clave = re.sub(r'\s+', '', campos.get('clave', '')).upper()
    equipo = campos.get('equipo', '').strip()[:128]
    try:
        lista = json.loads(campos.get('errores', ''))
    except ValueError:
        lista = None
    if not re.fullmatch(r'CC(-[A-Z2-9]{4}){4}', clave) or not equipo or not isinstance(lista, list) or not lista:
        return 400, {'ok': False, 'error': 'Faltan datos.'}
    if datos.sin_errores:
        return 503, {'ok': False, 'error': 'Todavía no se reciben errores.'}
    lic = next((l for l in datos.licencias if l['clave'] == clave), None)
    if not lic or not any(a['licencia_id'] == lic['id'] and a['equipo'] == equipo for a in datos.activaciones):
        return 404, {'ok': False, 'error': 'Este equipo no está activado con esa licencia.'}
    m = re.match(r'CineCaptions/([0-9]{1,4}\.[0-9]{1,4}(?:\.[0-9]{1,4})?)(?![A-Za-z0-9_.-])', agente or '')
    version = _texto_version(campos.get('version')) or (_texto_version(m.group(1)) if m else None)
    so = _saneado(campos.get('so'))[:80] or None
    equipo_datos = _saneado(campos.get('equipo_datos'))[:300] or None
    guardados = capturas = ventanas = 0

    def imagen(campo, de):   # (captura_subida de errores.php: solo JPEG o PNG de verdad, de 16 a 8000 px y 900 KB)
        img = archivos.get(campo)
        info = _datos_imagen(img) if img and len(img) <= CAPTURA_MAX_BYTES else None
        if info and 16 <= info[1] <= 8000 and 16 <= info[2] <= 8000:
            return {'tipo': info[0], 'ancho': info[1], 'alto': info[2], 'bytes': len(img), 'de': de,
                    'creada': _f(datos.ahora()), 'imagen': img}
        return None

    for e in lista[:20]:
        mensaje = _saneado(e.get('mensaje') if isinstance(e, dict) else None)[:600]
        if not mensaje:
            continue
        origen = _saneado(e.get('origen'))[:120]
        firma = e.get('firma')
        if not (isinstance(firma, str) and re.fullmatch('[0-9a-f]{40}', firma)):
            firma = hashlib.sha1(f'{origen}|{mensaje}'.encode()).hexdigest()
        titulo = _saneado(e.get('titulo'))[:190] or mensaje[:190]
        detalle = _saneado(e.get('detalle'), True)[:12000]
        captura = imagen('captura_' + firma, e.get('captura') if e.get('captura') in ('pantalla', 'ventana') else None)
        ventana = imagen('ventana_' + firma, 'ventana') if datos.con_ventanas else None
        capturas += captura is not None
        ventanas += ventana is not None
        datos.recibir_error(lic['id'], equipo, firma, e.get('nivel') if e.get('nivel') in ('error', 'aviso') else 'error',
                            titulo, mensaje, origen or None, detalle or None, version, so,
                            max(1, min(10000, _entero(e.get('veces') or 1))), equipo_datos, captura, ventana)
        guardados += 1
    if capturas or ventanas:
        datos.recortar_capturas(lic['id'])
    respuesta = {'ok': True, 'guardados': guardados, 'capturas': capturas}
    if datos.con_ventanas and archivos:   # (como errores.php: «ventanas» solo si llegaron archivos y existe la tabla nueva)
        respuesta['ventanas'] = ventanas
    return 200, respuesta


def atender_equipo_php(datos, campos):
    """equipo.php (CineCaptions 5.72: la ficha técnica del equipo al abrir el programa): clave, equipo, version, so, resumen
    y ficha (JSON de 16 000 bytes como mucho, un objeto). 400 si falta algo o el JSON no sirve, 404 si el equipo no está
    activado, 429 con Retry-After después de 6 en una hora (por equipo) y, con --sin-fichas (o un servidor de antes), 503
    como si faltaran las columnas. Devuelve (código, respuesta, cabeceras)."""
    clave = re.sub(r'\s+', '', campos.get('clave', '')).upper()
    equipo = campos.get('equipo', '').strip()[:128]
    texto = campos.get('ficha', '').strip()
    if not re.fullmatch(r'CC(-[A-Z2-9]{4}){4}', clave) or not equipo or not texto:
        return 400, {'ok': False, 'error': 'Faltan datos.'}, None
    if len(texto.encode('utf-8')) > FICHA_MAX_BYTES:
        return 400, {'ok': False, 'error': 'La ficha es demasiado grande.'}, None
    try:
        ficha = json.loads(texto, parse_constant=_sin_constantes)
    except (ValueError, RecursionError):
        ficha = None
    if not isinstance(ficha, dict) or _niveles(ficha) > FICHA_NIVELES:
        return 400, {'ok': False, 'error': 'La ficha no es un JSON válido.'}, None
    lic = next((l for l in datos.licencias if l['clave'] == clave), None)
    act = lic and next((a for a in datos.activaciones if a['licencia_id'] == lic['id'] and a['equipo'] == equipo), None)
    if not act:
        return 404, {'ok': False, 'error': 'Este equipo no está activado con esa licencia.'}, None
    if not datos.con_fichas:
        return 503, {'ok': False, 'error': 'Todavía no se reciben fichas.'}, {'Retry-After': '3600'}
    # El tope (el UPDATE de equipo.php): si pasó la hora de ficha_ventana, la cuenta vuelve a 1 y la hora empieza ahora
    ahora = _utc_ahora()
    ventana = dt.datetime.strptime(act['ficha_ventana'], FORMATO) if act.get('ficha_ventana') else None
    if ventana is None or ventana <= ahora - dt.timedelta(hours=1) or act.get('ficha_envios') is None:
        act['ficha_envios'], act['ficha_ventana'], ventana = 1, _f(ahora), ahora
    else:
        act['ficha_envios'] += 1
    if act['ficha_envios'] > FICHA_TOPE_HORA:
        quedan = int((ventana + dt.timedelta(hours=1) - ahora).total_seconds())
        return 429, {'ok': False, 'error': 'Demasiadas fichas en una hora.'}, {'Retry-After': str(max(60, min(3600, quedan)))}
    resumen = _saneado(campos.get('resumen'))[:300]
    act.update(ficha=json.dumps(_ficha_limpia(ficha), ensure_ascii=False, separators=(',', ':')),
               ficha_resumen=resumen or None, ficha_cuando=_f(ahora))
    return 200, {'ok': True}, None


class Manejador(BaseHTTPRequestHandler):
    server_version = 'PruebaCineCaptions/2.0'

    def log_message(self, formato, *args):  # el registro propio va en _responder
        pass

    def _responder(self, codigo, datos, accion='', cabeceras=None):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(cuerpo)))
        for nombre, valor in (cabeceras or {}).items():
            self.send_header(nombre, valor)
        self.end_headers()
        self.wfile.write(cuerpo)
        if self.server.registro:
            print(f'[prueba] {codigo} {accion or "-"}', flush=True)

    def do_GET(self):
        self.server.claves_recibidas.append(self.headers.get('X-Admin-Clave'))
        self._responder(405, {'error': 'Método no permitido.'})

    def do_POST(self):
        srv = self.server
        with srv.candado_cuenta:   # cuántas peticiones hay en curso a la vez (la app manda de una en una)
            srv.en_curso += 1
            srv.max_en_curso = max(srv.max_en_curso, srv.en_curso)
        try:
            self._post()
        finally:
            with srv.candado_cuenta:
                srv.en_curso -= 1

    def _post(self):
        srv = self.server
        largo = _entero(self.headers.get('Content-Length'))
        crudo = self.rfile.read(largo) if largo > 0 else b''
        if self.path.split('?')[0].endswith('licencia.php'):
            campos = {k: v[0] for k, v in urllib.parse.parse_qs(crudo.decode('utf-8', 'replace')).items()}
            with srv.candado:
                codigo, respuesta = atender_licencia(srv.datos, campos, self.headers.get('User-Agent', ''))
            return self._responder(codigo, respuesta, 'licencia:' + campos.get('accion', ''))
        if self.path.split('?')[0].endswith('errores.php'):
            tipo = self.headers.get('Content-Type') or ''
            archivos = {}
            if tipo.startswith('multipart/form-data'):   # (CineCaptions 5.72: con las capturas)
                campos, archivos = _multipart(tipo, crudo)
            else:
                campos = {k: v[0] for k, v in urllib.parse.parse_qs(crudo.decode('utf-8', 'replace')).items()}
            with srv.candado:
                codigo, respuesta = atender_errores_php(srv.datos, campos, self.headers.get('User-Agent', ''), archivos)
            return self._responder(codigo, respuesta, 'errores.php')
        if self.path.split('?')[0].endswith('equipo.php'):   # (CineCaptions 5.72: la ficha técnica del equipo)
            campos = {k: v[0] for k, v in urllib.parse.parse_qs(crudo.decode('utf-8', 'replace')).items()}
            with srv.candado:
                codigo, respuesta, cabeceras = atender_equipo_php(srv.datos, campos)
            return self._responder(codigo, respuesta, 'equipo.php', cabeceras)
        srv.claves_recibidas.append(self.headers.get('X-Admin-Clave'))
        if srv.redirigir:
            self.send_response(302)
            self.send_header('Location', srv.redirigir)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        try:
            entrada = json.loads(crudo.decode('utf-8')) if crudo else {}
        except ValueError:
            entrada = {}
        entrada = entrada if isinstance(entrada, dict) else {}
        accion = str(entrada.get('accion') or '')
        srv.acciones_recibidas.append(accion)
        if srv.demora:
            time.sleep(srv.demora)
        with srv.candado:
            ahora = time.monotonic()
            srv.fallos = [t for t in srv.fallos if ahora - t < VENTANA_FALLOS]
            if len(srv.fallos) >= srv.fallos_max:
                return self._responder(429, {'error': 'Demasiados intentos con una clave incorrecta. Espera 15 minutos.'},
                                       accion, {'Retry-After': str(VENTANA_FALLOS)})
            if srv.sin_configurar:
                return self._responder(503, {'error': 'La app de ventas no está configurada en el servidor (falta admin_clave.php).'}, accion)
            if self.headers.get('X-Admin-Clave', '') != srv.clave:
                srv.fallos.append(ahora)
                return self._responder(401, {'error': 'Clave de administrador incorrecta.'}, accion)
            try:
                codigo, respuesta = atender(srv.datos, entrada)
                if srv.datos.viejo and codigo == 200:
                    respuesta = _sin_campos_nuevos(accion, respuesta)
            except Exception as error:  # igual que el catch de admin.php
                print(f'[prueba] error interno: {error!r}', flush=True)
                codigo, respuesta = 500, {'error': 'Error interno del servidor.'}
        self._responder(codigo, respuesta, accion)


def crear(puerto=8799, clave=CLAVE, demora=0.0, sin_configurar=False, fallos_max=5, registro=False, utc=False,
          redirigir=None, viejo=False, github_caido=False, ahora=None, pocos=False, sin_errores=False, sin_fichas=False,
          sin_ventanas=False, sin_cupones=False, sin_borrar_errores=False):
    """Crea el servidor (sin arrancarlo). Sirve también para las pruebas automáticas.
    sin_cupones: como el admin.php de antes de los cupones (app 2.8): sin sus acciones ni el cupón de cada venta.
    sin_borrar_errores: como el admin.php publicado con la app 2.9 (con los cupones, sin errores_borrar).
    utc: MySQL en UTC, como en el hosting. redirigir: responde 302 hacia esa dirección (la app no debe seguirla).
    viejo: como el admin.php anterior. ahora: la hora de arranque de los datos (fija, para comparar dos servidores).
    pocos: casi sin datos (una venta en los últimos 30 días, sin canjes, avisos ni errores). sin_errores: como el
    admin.php de antes de la 5.71 de CineCaptions (con panel y lo demás, pero sin los errores de los clientes).
    sin_fichas: como el admin.php de la 5.71 (con los errores y las capturas, sin las fichas de los equipos de la 5.72).
    sin_ventanas: como el admin.php de la 5.72 (con las fichas, sin la captura de la ventana de CineCaptions 5.73)."""
    srv = ThreadingHTTPServer(('127.0.0.1', puerto), Manejador)
    srv.daemon_threads = True
    srv.datos = Datos(ahora=ahora, utc=utc, pocos=pocos)
    srv.datos.viejo, srv.datos.github_caido, srv.datos.sin_errores = viejo, github_caido, sin_errores
    srv.datos.sin_fichas, srv.datos.sin_ventanas, srv.datos.sin_cupones = sin_fichas, sin_ventanas, sin_cupones
    srv.datos.sin_borrar_errores = sin_borrar_errores
    if viejo or sin_errores:   # (en esos servidores nunca se pudo eliminar una venta: no hay ninguna eliminada)
        srv.datos.pedidos = [p for p in srv.datos.pedidos if not p.get('eliminada')]
    if not srv.datos.con_ventanas:   # (sin errores_ventanas nunca llegó la captura de la ventana)
        for e in srv.datos.errores:
            e.pop('ventana', None)
    srv.clave, srv.demora, srv.sin_configurar, srv.fallos_max, srv.registro = clave, demora, sin_configurar, fallos_max, registro
    srv.redirigir = redirigir
    srv.claves_recibidas = []    # la cabecera X-Admin-Clave de cada petición que llegó
    srv.acciones_recibidas = []  # la acción de cada petición (también las que fallaron)
    srv.fallos = []
    srv.candado = threading.Lock()
    srv.candado_cuenta = threading.Lock()
    srv.en_curso = srv.max_en_curso = 0
    return srv


def arrancar_en_hilo(**opciones):
    """Arranca el servidor en un hilo aparte y lo devuelve (para las pruebas)."""
    srv = crear(**opciones)
    threading.Thread(target=srv.serve_forever, name='servidor-prueba', daemon=True).start()
    return srv


def main():
    parser = argparse.ArgumentParser(description='Servidor de prueba de pagos/admin.php (datos inventados).')
    parser.add_argument('--puerto', type=int, default=8799)
    parser.add_argument('--demora', type=float, default=0.25, help='segundos de espera por petición (para ver el indicador)')
    parser.add_argument('--sin-configurar', action='store_true', help='responder 503 como si faltara admin_clave.php')
    parser.add_argument('--fallos-max', type=int, default=5, help='claves malas antes de responder 429')
    parser.add_argument('--utc', action='store_true', help='MySQL en UTC, como en el hosting (las fechas salen en UTC)')
    parser.add_argument('--viejo', action='store_true', help='como el admin.php anterior (sin las acciones nuevas)')
    parser.add_argument('--github-caido', action='store_true', help='version_actual no puede leer GitHub')
    parser.add_argument('--pocos', action='store_true', help='casi sin datos: una venta en 30 días, sin canjes ni avisos')
    parser.add_argument('--sin-errores', action='store_true',
                        help='como el admin.php de antes de la 5.71 (sin los errores de los clientes)')
    parser.add_argument('--sin-fichas', action='store_true',
                        help='como el admin.php de la 5.71 (con los errores, sin las fichas de los equipos)')
    parser.add_argument('--sin-ventanas', action='store_true',
                        help='como el admin.php de la 5.72 (con las fichas, sin la captura de la ventana de CineCaptions)')
    parser.add_argument('--sin-cupones', action='store_true', help='como el admin.php de antes de los cupones (app 2.8)')
    parser.add_argument('--sin-borrar-errores', action='store_true',
                        help='como el admin.php publicado con la app 2.9 (sin errores_borrar)')
    args = parser.parse_args()
    srv = crear(args.puerto, demora=args.demora, sin_configurar=args.sin_configurar, fallos_max=args.fallos_max, registro=True,
                utc=args.utc, viejo=args.viejo, github_caido=args.github_caido, pocos=args.pocos,
                sin_errores=args.sin_errores, sin_fichas=args.sin_fichas, sin_ventanas=args.sin_ventanas,
                sin_cupones=args.sin_cupones, sin_borrar_errores=args.sin_borrar_errores)
    print(f'Servidor de prueba en http://127.0.0.1:{args.puerto}  (X-Admin-Clave: {CLAVE})', flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == '__main__':
    main()
