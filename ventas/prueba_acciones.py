# -*- coding: utf-8 -*-
"""
Pruebas de «CineCaptions Ventas» contra servidor_prueba.py (nunca contra el servidor real).

1. Funciones sueltas: dinero, fechas, versiones, clave en un archivo, CSV, DPAPI.
2. Cada acción de la API con ClienteApi (las de antes y las nuevas del CONTRATO), revisando cómo cambia el estado del
   servidor de prueba. También la telemetría de licencia.php y el modo solo lectura del cliente.
3. Los errores: clave mala (401), demasiados intentos (429), sin configurar (503), sin conexión, 400, 404, 502.
4. --importar-clave desde la terminal, con un APPDATA aparte.
5. La ventana (plataforma offscreen): carga, cada página, elegir filas y apretar cada botón del panel.
6. Casos difíciles: clave cambiada a media carga, otra API, MySQL en UTC, redirección, «Cargar más», 429, cerrar con un
   cambio en camino, el servidor anterior, la cola de UNA petición, el envío masivo (tope por hora y Detener) y que
   --captura no cambie nada.
7. Los errores de los clientes (desde CineCaptions 5.71): errores, error_detalle, error_visto y errores.php; la página
   Errores (contador, filtros, panel con el informe, marcar como visto o nuevo, «Marcar todo como visto», «Abrir licencia»,
   los estados vacíos) y el aviso de un error nuevo (una sola vez por error, nunca la primera vez, ni al reiniciar).
8. Lo de la instalación y lo visual: recurso() con PyInstaller de un solo archivo y instalado («onedir», con la carpeta
   _internal), «Acerca de», las confirmaciones (el orden de los botones) y la app con pocos datos (servidor --pocos).
9. Eliminar ventas (2.2.0): eliminar_venta (no borra, se restaura, «bloquear también su licencia», el estado
   'eliminadas', los totales y la gráfica sin ellas, el servidor de antes) y, en la ventana, el botón del panel, el clic
   derecho, la confirmación con su casilla, el filtro «Eliminadas» (atenuadas, «Restaurar») y que no se mande dos veces.
10. La página Versiones (2.2.0): un cliente por fila, la tarjeta que dice quién va atrasado y a cuántos ya se les avisó,
   «Avisar a los N…», el «Avisar» de cada fila (un clic de verdad), los textos de cada caso y que quepa a 1100 y 1920 px.
11. La ficha técnica de los equipos (2.4, CineCaptions 5.72): cómo se pinta (también lo que no se conoce), equipo.php (200,
   400, 404, 429 con Retry-After, 503, el saneado), equipo_ficha, la ficha en error_detalle y en los equipos de detalle, que
   se borre al liberar, la pestaña «Cliente y equipo» del error, «Ficha» en los equipos y el admin.php de la 5.71.
12. Las dos capturas del error (2.5, CineCaptions 5.73): errores.php con las dos, solo la pantalla, solo la ventana e
   imágenes que no sirven, el tope de 30 errores con captura, que se borren con su error, error_captura con y sin «cual»
   (la app 2.4) y el admin.php de la 5.72 (--sin-ventanas); en la ventana, las dos miniaturas lado a lado con su rótulo,
   una sola como antes, una que falla, el visor de cada una y «Guardar imagen…».
13. El menú, la isla de arriba (2.7): los 6 ítems + Configuración, un clic en cada uno abre su página y la pastilla se
   desliza (con su resorte) hasta quedar justo en el ítem, los contadores (Errores rojo, Versiones naranja, también en el
   globito de la isla cerrada), Ctrl+1…6, el logo, el menú de Configuración, que a 1100 px se cierren los nombres de las
   demás páginas sin que nada se salga ni tape el encabezado, y que la captura de la ventana la incluya.
14. Los cupones de descuento (2.8): cupones, cupon_crear (y sus errores), cupon_editar, cupon_borrar, el historial, el
   modo captura y el admin.php de antes; en la ventana, la página Cupones (filtros, buscador, pie), el diálogo (mayúsculas,
   en cuánto queda, el aviso del 100 % sin tope), crear, editar, pausar (una sola vez), borrar y el cupón en Ventas.

Uso:  python prueba_acciones.py      (sale con código 0 si todo pasó)
"""
import copy
import csv
import datetime as dt
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TEMPORAL = Path(tempfile.mkdtemp(prefix='cc-ventas-prueba-'))
os.environ['APPDATA'] = str(TEMPORAL / 'appdata')          # nunca la configuración real
os.environ['CC_VENTAS_CONFIG'] = str(TEMPORAL / 'appdata' / 'CineCaptions Ventas')   # (también en Mac, ver carpeta_config)
os.environ['CC_VENTAS_LLAVERO'] = 'CineCaptions Ventas (pruebas)'   # en Mac, nunca la clave real del Llavero
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(AQUI))

import servidor_prueba  # noqa: E402
import ventas as v      # noqa: E402
import shiboken6  # noqa: E402
from PySide6.QtCore import QRect  # noqa: E402

FALLAS = []
# Lo único que puede pedir --captura (todo lo demás cambia algo o manda correos)
SOLO_LEEN = {'resumen', 'panel', 'ventas', 'canjes', 'detalle', 'version_actual', 'versiones', 'candidatos_aviso', 'avisos',
             'historial', 'estadisticas', 'estado_recurrente', 'errores', 'error_detalle', 'error_captura', 'equipo_ficha',
             'cupones'}


def revisar(condicion, descripcion):
    print(('  ok   ' if condicion else '  FALLA ') + descripcion, flush=True)
    if not condicion:
        FALLAS.append(descripcion)


def error_de(funcion):
    try:
        funcion()
    except v.ApiError as e:
        return e
    return None


def puerto_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def servidor(**opciones):
    puerto = puerto_libre()
    srv = servidor_prueba.arrancar_en_hilo(puerto=puerto, **opciones)
    return srv, f'http://127.0.0.1:{puerto}/pagos/admin.php'


def lic_de(datos, nombre):
    return next(l for l in datos.licencias if l['nombre'] == nombre)


def estado_servidor(datos):
    """Todo lo que una acción podría cambiar en el servidor de prueba (para ver que --captura no cambia nada)."""
    return copy.deepcopy([datos.licencias, datos.pedidos, datos.activaciones, datos.canjes, datos.avisos, datos.cambios,
                          sorted(datos.bajas), datos.errores])


# ------------------------------------------------------------------ 1. Funciones sueltas
def prueba_funciones():
    print('Funciones sueltas')
    revisar(v.dinero(2900) == '$29.00 USD', 'dinero(2900) = $29.00 USD')
    revisar(v.dinero(123400) == '$1,234.00 USD', 'dinero(123400) = $1,234.00 USD')
    revisar(v.dinero(5, 'gtq') == 'Q0.05 GTQ', 'dinero en quetzales')
    revisar(v.dinero(None) == '—', 'dinero sin monto')
    revisar(v.entero('2900') == 2900 and v.entero(None) == 0 and v.entero_o_nada('') is None, 'enteros que llegan como texto')
    revisar(v.extraer_clave('abc123def456ghi789\n') == 'abc123def456ghi789', 'clave sola en el archivo')
    revisar(v.extraer_clave('﻿# comentario\nClave de administrador: Zx9_k2-PqLm77Ab\n') == 'Zx9_k2-PqLm77Ab', 'clave con etiqueta')
    revisar(v.extraer_clave('CineCaptions Ventas\nhttps://cinecaptions.shop/pagos/admin.php\n9f86d081884c7d659a2feaa0c55ad015\n')
            == '9f86d081884c7d659a2feaa0c55ad015', 'clave entre otras líneas')
    revisar(error_de(lambda: None) is None, 'ayudante de errores')
    try:
        v.extraer_clave('\n\n   \n')
        revisar(False, 'archivo vacío da error')
    except ValueError:
        revisar(True, 'archivo vacío da error')
    revisar(v.problema_clave('con espacio adentro') is not None and v.problema_clave('clave-de-prueba') is None, 'validación de la clave pegada')
    revisar(v.validar_api('http://127.0.0.1:8799') == 'http://127.0.0.1:8799', 'http permitido solo en local')
    for mala in ('http://cinecaptions.shop/pagos/admin.php', 'ftp://x', 'cinecaptions.shop'):
        try:
            v.validar_api(mala)
            revisar(False, f'rechaza {mala}')
        except ValueError:
            revisar(True, f'rechaza {mala}')
    # Fechas: MySQL en UTC (como en el hosting) y esta PC en Guatemala (UTC−6), con un «ahora» fijo
    v.Reloj.local = dt.timezone(dt.timedelta(hours=-6))
    v.Reloj.fijo = dt.datetime(2026, 10, 29, 21, 0)            # 15:00 en Guatemala
    v.Reloj.ajustar('2026-10-29 21:00:07')                      # NOW() de MySQL, en UTC
    revisar(v.Reloj.zona() == 'UTC', 'se detecta que MySQL va en UTC')
    revisar(v.fecha_corta('2026-10-29 15:05:00') == 'Hoy, 09:05', 'MySQL en UTC: la hora sale en la de esta PC')
    revisar(v.fecha_corta('2026-10-29 05:10:00') == 'Ayer, 23:10', 'una venta de las 11 p. m. es de ayer, no de hoy')
    revisar(v.fecha_corta('2025-12-01 16:00:00') == '1 dic 2025', 'fecha de otro año (sin la hora: cabe en la columna)')
    revisar(v.hace('2026-10-29 20:59:30') == 'hace 1 min', '«hace 1 min» (corto, cabe en «Último uso»)')
    revisar(v.hace('2026-10-29 20:55:00') == 'hace 5 min', 'hace 5 min')
    revisar(v.fecha_dia('2026-07-01 03:30:00', utc=True) == '30 jun 2026', 'fecha_venta (gmdate) también pasa a la hora local')
    revisar(v.fecha_csv('2026-10-29 15:05:00') == '2026-10-29 09:05:00', 'el CSV lleva la hora local')
    revisar(v.fecha_larga('2026-10-29T15:05:00.000-06:00') == '29 oct 2026, 15:05', 'fecha ISO de Recurrente')
    revisar(v.fecha_frase('2026-10-29 15:05:00') == 'hoy a las 09:05' and v.fecha_frase('2026-10-27 19:40:00') == 'el 27 oct a las 13:40'
            and v.fecha_frase('2026-10-29 07:10:00') == 'hoy a la 01:10', 'fecha en una frase («hoy a las…», «el 27 oct a las…»)')
    v.Reloj.ajustar('2026-10-29 15:00:00')                      # MySQL en la hora de Guatemala
    revisar(v.Reloj.zona() == 'UTC−6' and v.fecha_corta('2026-10-29 09:05:00') == 'Hoy, 09:05', 'MySQL en hora local: sin cambios')
    v.Reloj.fijo = v.Reloj.local = v.Reloj.desfase = None
    revisar(v.id_corto('6a99b44c6a9a52836a9af0ba6a9b8ef16a9c2d28') == '6a99b…2d28', 'huella corta del equipo')
    revisar(v.nombre_pc({'nombre_equipo': 'DESKTOP-7Q2KD1F · 3F2A-91BC', 'equipo': '3F2A-91BC'}) == 'DESKTOP-7Q2KD1F',
            'el nombre del equipo sin la huella repetida')
    # Versiones: se comparan por números (5.54 == 5.54.0 y 5.5.3 < 5.20); lo que no se entiende es «sin datos»
    revisar(v.partes_version('5.54') == v.partes_version('5.54.0') == (5, 54) and v.partes_version(' 5.5.3 ') == (5, 5, 3),
            '5.54 y 5.54.0 son la misma versión')
    # Lo mismo que entiende version_normal() de telemetria.php (y el servidor de prueba): dos o tres números de hasta 4 cifras
    raras = ['v5.54', '5', '5.54.0.1', '12345.1', '5.6-beta', '5,54', '５.54', '', None, '5.0', '05.054.000', '9999.9999.9999']
    revisar([v.partes_version(x) for x in raras] == [servidor_prueba._partes(x) for x in raras]
            == [None] * 9 + [(5,), (5, 54), (9999, 9999, 9999)], 'las versiones se entienden igual que en admin.php')
    revisar([v.texto_version(x) for x in ('5.0', '5.0.0', '05.054.000', '5.54.10')] == ['5.0', '5.0', '5.54', '5.54.10'],
            'la versión se escribe como en admin.php (sin el .0 final)')
    # El correo que acepta admin.php (correo_valido con FILTER_VALIDATE_EMAIL de PHP)
    correos = {'ana@example.com': True, ' Ana.Lopez+ventas@Example.COM ': True, "o'brien@x.co": True, 'a@b.c': True,
               'nombre@gmail': False, 'a b@x.com': False, '"a"@x.com': False, 'a,b@x.com': False, 'a@x..com': False,
               '.a@x.com': False, 'a.@x.com': False, 'a@-x.com': False, 'a@x-.com': False, 'a@x.123': False,
               'josé@x.com': False, 'a@exámple.com': False, 'a@x.com.': False, 'a@[1.2.3.4]': False,
               'a' * 64 + '@x.com': True, 'a' * 65 + '@x.com': False, 'a@' + 'b' * 63 + '.com': True,
               'a@' + 'b' * 64 + '.com': False, 'a@' + 'b.' * 92 + 'com': True, 'a@' + 'b.' * 93 + 'com': False,
               'no-es-correo': False, '': False, None: False}
    revisar(all(bool(v.correo_valido(c)) is bueno and bool(servidor_prueba._valido(c)) is bueno for c, bueno in correos.items())
            and v.correo_valido(' ana@example.com ') == 'ana@example.com', 'los correos se validan igual que en admin.php')
    revisar(v.partes_version('5.5.3') < v.partes_version('5.20'), '5.5.3 es más vieja que 5.20')
    revisar(v.partes_version('5.6-beta') is None and v.texto_version('') is None and v.texto_version('5.54.0') == '5.54',
            'una versión que no se entiende cuenta como sin datos')
    revisar([v.estado_de_version(a, b) for a, b in (('5.54', '5.54.0'), ('5.53', '5.54'), ('5.60', '5.54'), (None, '5.54'),
                                                     ('raro', '5.54'), ('5.54', None))]
            == ['al_dia', 'desactualizado', 'al_dia', 'sin_datos', 'sin_datos', 'desconocido'], 'estado de la versión de un equipo')
    revisar(v.estado_fila_version({'licencia_id': 1, 'equipos': 2, 'version': '5.54', 'equipos_desactualizados': 1}, '5.54')
            == 'desactualizado', 'una venta con un equipo viejo es «desactualizada» aunque el último usado esté al día')
    revisar(v.estado_fila_version({'licencia_id': 1, 'equipos': 0, 'version': None}, '5.54') is None,
            'sin equipos no hay estado de versión')
    largo = 'maria.fernanda.castillo.ramirez.producciones@example.org'
    partido = v.partible(f'Correo enviado a {largo}')
    revisar('​' in partido and partido.replace('​', '') == f'Correo enviado a {largo}'
            and v.partible('Pago recibido') == 'Pago recibido', 'un correo muy largo se puede cortar en líneas')
    # A dónde manda admin.php los correos: la clave solo con una compra pagada o un canje; los avisos, al de la licencia
    reembolsada = {'licencia': {'correo': 'ana@example.com'}, 'pedido': {'estado': 'reembolsado', 'correo': 'ana@example.com'},
                   'canje': None}
    revisar(v.correo_reenvio(reembolsada) is None and v.correo_aviso(reembolsada) == 'ana@example.com',
            'venta reembolsada: la clave no se reenvía (admin.php daría 400), los avisos sí tienen a dónde ir')
    mala = {'licencia': {'correo': 'no-es-correo'}, 'pedido': {'estado': 'pagado', 'correo': 'ana@example.com'}, 'canje': None}
    canje = {'licencia': {'correo': None}, 'pedido': None, 'canje': {'correo': 'luis@example.com'}}
    revisar(v.correo_reenvio(mala) == v.correo_aviso(mala) == 'ana@example.com' and v.correo_reenvio(canje) == 'luis@example.com',
            'sin un correo válido en la licencia: el de la compra pagada o el del canje')
    if os.name == 'nt':
        cifrada = v.cifrar_clave('clave-de-prueba')
        revisar(cifrada != 'clave-de-prueba' and v.descifrar_clave(cifrada) == 'clave-de-prueba', 'DPAPI cifra y descifra')
    else:   # Mac: la clave va en el Llavero (keyring)
        revisar(v._llavero() is not None, 'el Llavero (keyring) está disponible')
    filas = [v.normalizar_venta({'id': '1', 'estado': 'pagado', 'correo': '=HYPERLINK("x")', 'nombre': '+Ana', 'monto': '2900',
                                 'moneda': 'USD', 'creado': '2026-10-29 10:00:00', 'pagado': '2026-10-29 10:02:00',
                                 'checkout_id': 'ch_1', 'correo_enviado': '1', 'licencia_id': '3', 'clave': 'CC-AAAA-BBBB-CCCC-DDDD',
                                 'licencia_estado': 'activa', 'limite': '2', 'equipos': '1', 'version': '5.54.0',
                                 'ultima_vez': '2026-10-29 11:00:00', 'equipos_desactualizados': '0'})]
    ruta = TEMPORAL / 'ventas.csv'
    v.escribir_csv(ruta, filas, 'ventas', separadores=(';', ','))
    crudo = ruta.read_bytes()
    revisar(crudo.startswith(b'\xef\xbb\xbf'), 'CSV con BOM para Excel')
    encabezado, fila = list(csv.reader(ruta.read_text(encoding='utf-8-sig').splitlines(), delimiter=';'))[:2]
    revisar(fila[6] == '29,00' and fila[4] == "'+Ana" and fila[5].startswith("'="), 'CSV: decimal regional y fórmulas desactivadas')
    revisar(encabezado[-5:-2] == ['Versión', 'Último uso', 'Equipos desactualizados'] and fila[-5:-2] == ['5.54', '2026-10-29 11:00:00', '0'],
            'CSV de ventas con las columnas nuevas al final')
    revisar(encabezado[-2:] == ['Cupón', 'Descuento'] and fila[-2:] == ['', ''], '2.8: CSV con «Cupón» y «Descuento» al final (vacíos sin cupón)')
    con = [dict(filas[0], cupon='NAVIDAD', descuento=580, monto=2320)]
    v.escribir_csv(ruta, con, 'ventas', separadores=(';', ','))
    fila = list(csv.reader(ruta.read_text(encoding='utf-8-sig').splitlines(), delimiter=';'))[1]
    revisar(fila[-2:] == ['NAVIDAD', '5,80'] and fila[6] == '23,20', '2.8: CSV de una venta con cupón: el código y lo descontado')


# ------------------------------------------------------------------ 2. Acciones de la API
def prueba_acciones():
    print('Acciones contra el servidor de prueba')
    srv, url = servidor()
    datos = srv.datos
    c = v.ClienteApi(url, servidor_prueba.CLAVE)
    r = c.resumen()
    revisar(r['ventas']['pagadas'] == 22 and r['ventas']['ingresos'] == 60800, 'resumen: 22 pagadas, $608.00')
    revisar(r['licencias'] == {'activas': 23, 'bloqueadas': 4} and r['equipos'] == 26 and r['canjes'] == 3,
            'resumen: licencias, equipos, canjes')
    revisar(r['versiones'] == {'ultima': '5.54', 'al_dia': 12, 'desactualizados': 9, 'sin_datos': 3, 'activos_30d': 23},
            'resumen: el bloque de versiones (cuenta equipos de licencias activas)')
    normales = c.ventas()
    revisar(len(normales) == 24 and all(f['estado'] != 'pendiente' for f in normales), "ventas '' = pagadas y reembolsadas (24)")
    revisar(isinstance(normales[0]['monto'], int) and isinstance(normales[0]['licencia_id'], int), 'los números llegan como texto y se convierten')
    revisar(len(c.ventas('pagado')) == 22 and len(c.ventas('reembolsado')) == 2, 'filtro pagadas / reembolsadas')
    revisar(len(c.ventas('pendiente')) == 3 and len(c.ventas('todos')) == 27, 'filtro sin completar / todas')
    revisar(len(c.ventas(buscar='nunez')) == 1, 'buscar sin tildes encuentra a José Ñúñez')
    revisar(len(c.ventas('todos', limite=5)) == 5 and len(c.ventas('todos', limite=5, desde=25)) == 2, 'límite y desde')
    canjes = c.canjes()
    revisar(len(canjes) == 3 and len(c.canjes('andrea')) == 1, 'canjes y búsqueda de canjes')
    mariana = next(f for f in normales if f['nombre'] == 'Mariana López')
    lid, pid = mariana['licencia_id'], mariana['id']
    revisar(mariana['version'] == '5.54' and mariana['ultima_vez'] and mariana['equipos_desactualizados'] == 0,
            'cada venta trae la versión, el último uso y los equipos desactualizados')
    fernanda = next(f for f in normales if (f['nombre'] or '').startswith('María Fernanda'))
    revisar(fernanda['version'] == '5.54' and fernanda['equipos_desactualizados'] == 1, 'venta con un equipo desactualizado')
    andrea = next(f for f in canjes if f['nombre'] == 'Andrea Morales')
    revisar(andrea['version'] == '5.53' and andrea['equipos_desactualizados'] == 1, 'los canjes también traen la versión')

    # panel: todo en UNA petición
    antes = len(srv.acciones_recibidas)
    p = c.panel()
    revisar(len(srv.acciones_recibidas) == antes + 1 and len(p['ventas']) == 24 and len(p['canjes']) == 3
            and p['resumen']['ventas']['pagadas'] == 22 and p['resumen']['hora_servidor'], 'panel: resumen, ventas y canjes en una petición')
    revisar(len(c.panel('pagado')['ventas']) == 22 and len(c.panel(buscar='mariana')['ventas']) == 1, 'panel con estado y búsqueda')
    revisar(c.panel(buscar='mariana')['canjes'] == [] and len(c.panel(buscar='andrea')['canjes']) == 1,
            'panel: la búsqueda también filtra los canjes, como admin.php')

    # detalle con lo nuevo
    d = c.detalle(pedido_id=pid)
    revisar(d['licencia']['id'] == lid and d['pedido']['id'] == pid and len(d['equipos']) == 2, 'detalle por pedido')
    revisar('token' not in d['pedido'], 'el token del pedido no sale del servidor')
    revisar(c.detalle(licencia_id=lid)['pedido']['id'] == pid, 'detalle por licencia')
    revisar(d['version_ultima'] == '5.54' and all(e['version'] == '5.54' and e['so'] == 'Windows 11' and e['estado_version'] == 'al_dia'
                                                    for e in d['equipos']), 'detalle: versión, sistema y estado de cada equipo')
    fd = c.detalle(licencia_id=fernanda['licencia_id'])
    revisar(fd['licencia']['nota'].startswith('Trabaja con dos equipos') and fd['licencia']['nota_fecha']
            and sorted(e['estado_version'] for e in fd['equipos']) == ['al_dia', 'desactualizado']
            and any(e['version_anterior'] == '5.53' and e['version_desde'] for e in fd['equipos']),
            'detalle: nota, versión anterior y desde cuándo')

    # version_actual: lo guardado (10 minutos), refrescar y GitHub caído
    info = c.version_actual()
    revisar(info['version'] == '5.54' and info['notas'].startswith('Exporta') and info['descarga'] == servidor_prueba.DESCARGA
            and info['error'] is None, 'version_actual: versión (ya normalizada: «5.54.0» → «5.54»), notas y descarga')
    consultado = info['consultado']
    revisar(c.version_actual()['consultado'] == consultado, 'version_actual: dentro de 10 minutos no vuelve a leer GitHub')
    revisar(c.version_actual(refrescar=True)['consultado'] != consultado, 'version_actual con refrescar: lee GitHub otra vez')
    datos.github_caido = True
    caida = c.version_actual(refrescar=True)
    revisar(caida['error'] and caida['version'] == '5.54', 'GitHub caído: dice el error y deja la última versión guardada')
    datos.github_caido = False

    # versiones
    vs = c.versiones()
    revisar(len(vs['equipos']) == 26 and vs['ultima'] == '5.54' and (vs['al_dia'], vs['desactualizados'], vs['sin_datos'],
                                                                       vs['activos_30d']) == (12, 9, 3, 23), 'versiones: todos los equipos')
    revisar([(x['version'], x['equipos']) for x in vs['por_version']] == [('5.54', 12), ('5.53', 7), ('5.52', 2), (None, 3)],
            'versiones: equipos por versión')
    revisar(len(c.versiones('desactualizados')['equipos']) == 9 and len(c.versiones('al_dia')['equipos']) == 14
            and len(c.versiones('sin_datos')['equipos']) == 3, 'versiones: filtros')
    e = next(x for x in vs['equipos'] if x['cliente'] == 'Ricardo Alvarado' and x['version'] == '5.53')
    revisar(e['origen'] == 'compra' and e['pedido_id'] and e['so'] == 'Windows 11' and e['version_anterior'] == '5.52'
            and e['aviso_version'] == '5.54' and e['aviso_fecha'] and e['estado_version'] == 'desactualizado',
            'versiones: cada equipo con su licencia, origen y último aviso')
    revisar(len(c.versiones(buscar='macbook')['equipos']) == 4, 'versiones: búsqueda')

    # candidatos_aviso
    ca = c.candidatos_aviso()
    revisar(ca['version'] == '5.54' and len(ca['candidatos']) == 5
            and ca['excluidos'] == {'baja': 1, 'ya_avisados': 3, 'bloqueadas': 4, 'sin_correo': 0, 'al_dia': 9},
            'candidatos_aviso: 5 desactualizados y por qué quedan fuera los demás')
    revisar(len(c.candidatos_aviso(a_quien='todos')['candidatos']) == 18, 'candidatos_aviso a todos')
    revisar(all(x['equipos_desactualizados'] >= 1 and x['correo'] for x in ca['candidatos']), 'cada candidato con su correo')
    orden = [x['ultima_vez'] or '' for x in ca['candidatos']]
    revisar(orden == sorted(orden, reverse=True), 'candidatos: los que usaron CineCaptions hace menos primero, como admin.php')
    errores = [error_de(lambda: c.candidatos_aviso('5.6-beta')), error_de(lambda: c.llamar('candidatos_aviso', a_quien='nadie')),
               error_de(lambda: c.avisar_actualizacion(lic_de(datos, 'Natalia Herrera')['id'], 'v5.54'))]
    revisar(all(e is not None and e.codigo == 400 for e in errores) and 'no se entiende' in errores[0].mensaje,
            'una versión que no se entiende o un a_quien que no existe: 400, como admin.php')

    # avisar_actualizacion: cada motivo (ok es true aunque no se mande)
    natalia = lic_de(datos, 'Natalia Herrera')
    n_avisos = len(datos.avisos)
    a = c.avisar_actualizacion(natalia['id'], '5.54', 'Lo nuevo de la 5.54.')
    revisar(a['enviado'] and a['correo'] == 'natalia.herrera@example.com' and a['motivo'] is None, 'avisar: enviado')
    revisar(len(datos.avisos) == n_avisos + 1 and datos.avisos[-1]['mensaje'] == 'Lo nuevo de la 5.54.', 'avisar: queda en la tabla avisos')
    a = c.avisar_actualizacion(natalia['id'], '5.54.0')
    revisar(not a['enviado'] and a['motivo'] == 'ya_avisado', 'avisar otra vez la misma versión (5.54.0 = 5.54): ya_avisado')
    revisar(c.avisar_actualizacion(natalia['id'], '5.54', forzar=True)['enviado'], 'forzar se salta ya_avisado')
    paola = lic_de(datos, 'Paola Girón')
    revisar(c.avisar_actualizacion(paola['id'], '5.54', forzar=True)['motivo'] == 'baja', 'forzar no se salta la baja')
    luis = lic_de(datos, 'Luis Fernando Gómez')
    revisar(c.avisar_actualizacion(luis['id'], '5.54')['motivo'] == 'bloqueada', 'licencia bloqueada: no se avisa')
    jose = lic_de(datos, 'José Ñúñez')
    revisar(c.avisar_actualizacion(jose['id'], '5.54')['motivo'] == 'fallo_envio', 'correo que rebota: fallo_envio')
    sin = next(l for l in datos.licencias if l['correo'] == 'lucia.vargas@example.org')
    sin['correo'] = None
    datos.canje_de(sin['id'])['correo'] = None
    revisar(c.avisar_actualizacion(sin['id'], '5.54')['motivo'] == 'sin_correo', 'sin un correo válido: sin_correo')
    datos.tope_hora = len(datos.envios_tope)   # se llegó al tope de correos por hora
    a = c.avisar_actualizacion(lic_de(datos, 'Jorge Luis Paz')['id'], '5.54')
    revisar(not a['enviado'] and a['motivo'] == 'limite' and a['reintentar_en'] and a['reintentar_en'] > 0,
            'tope de 90 por hora: limite y en cuántos segundos reintentar')
    datos.tope_hora = servidor_prueba.TOPE_AVISOS_HORA
    e = error_de(lambda: c.llamar('avisar_actualizacion', licencia_id=natalia['id'], mensaje='x' * 2001))
    revisar(e is not None and e.codigo == 400, 'mensaje de más de 2000: 400')
    c.avisar_actualizacion(natalia['id'], '5.54', 'y' * 2500, forzar=True)
    revisar(len(datos.avisos[-1]['mensaje']) == v.MAX_TEXTO, 'la app corta el mensaje a 2000')

    # avisos
    todos = c.avisos()
    revisar(len(todos) == len(datos.avisos) and todos[0]['id'] == datos.avisos[-1]['id'], 'avisos: todos, el más nuevo primero')
    revisar(all(a['licencia_id'] == natalia['id'] for a in c.avisos(natalia['id'])) and len(c.avisos(limite=3)) == 3,
            'avisos de una licencia y con límite')
    revisar(isinstance(todos[0]['ok'], bool) and any(a['motivo'] == 'baja' and not a['ok'] for a in todos), 'avisos: ok y motivo')

    # historial
    eventos = c.historial(licencia_id=lid)
    tipos = {x['tipo'] for x in eventos}
    revisar({'compra', 'pago', 'correo', 'activacion', 'uso'} <= tipos and eventos == sorted(eventos, key=lambda x: x['fecha'], reverse=True),
            'historial: compra, pago, correo, activación y uso, el más nuevo primero')
    revisar(c.historial(pedido_id=pid) == eventos, 'historial por pedido')
    eventos = c.historial(licencia_id=lic_de(datos, 'Ricardo Alvarado')['id'])
    revisar({'version', 'aviso'} <= {x['tipo'] for x in eventos}, 'historial: cambio de versión y avisos')
    avisos_paola = [x['titulo'] for x in c.historial(licencia_id=paola['id']) if x['tipo'] == 'aviso']
    avisos_jose = [x['titulo'] for x in c.historial(licencia_id=jose['id']) if x['tipo'] == 'aviso']
    revisar(avisos_paola == ['Aviso de la 5.53 enviado'] and avisos_jose == ['No se pudo enviar el aviso de la 5.54'],
            'historial: los avisos que salieron y los que fallaron al enviar (no los «de baja»), como admin.php')

    # nota
    n = c.nota(lid, '  Pidió factura a nombre de Estudio ML.  ')
    revisar(n['nota'] == 'Pidió factura a nombre de Estudio ML.' and n['nota_fecha'] and datos.licencia(lid)['nota'] == n['nota'],
            'nota: guardar')
    revisar(c.nota(lid, '')['nota'] is None and datos.licencia(lid)['nota'] is None, 'nota vacía: se borra')
    e = error_de(lambda: c.llamar('nota', licencia_id=lid, texto='x' * 2001))
    revisar(e is not None and e.codigo == 400, 'nota de más de 2000: 400')
    n = c.nota(lid, 'Línea 1  \n\n\n\nLínea 2\t‏')
    cambios = len(datos.cambios)
    c.nota(lid, 'Línea 1\n\nLínea 2')
    revisar(n['nota'] == 'Línea 1\n\nLínea 2' and len(datos.cambios) == cambios,
            'nota: el servidor la limpia como admin.php y la misma nota otra vez no se anota')
    c.nota(lid, '')

    # limite
    e = error_de(lambda: c.limite(lid, 1))
    revisar(e is not None and e.codigo == 400 and '2 activados' in e.mensaje, 'límite menor que los equipos activados: 400')
    revisar(c.limite(lid, 3)['limite'] == 3 and datos.licencia(lid)['limite'] == 3, 'límite: de 2 a 3')
    revisar(error_de(lambda: c.limite(lid, 11)) is not None and error_de(lambda: c.limite(lid, 0)) is not None, 'límite fuera de 1..10: 400')
    c.limite(lid, 2)

    # editar_cliente
    e = error_de(lambda: c.editar_cliente(lid, correo='no-es-correo'))
    revisar(e is not None and e.codigo == 400, 'editar cliente: un correo no válido da 400')
    l = c.editar_cliente(lid, nombre='Mariana López de León', correo='mariana.nueva@example.com')
    revisar(l['nombre'] == 'Mariana López de León' and l['correo'] == 'mariana.nueva@example.com'
            and datos.pedido(pid)['correo'] == 'mariana.nueva@example.com', 'editar cliente: cambia la licencia y sus compras')
    revisar(any(x['tipo'] == 'admin' and 'cliente' in x['titulo'] for x in c.historial(licencia_id=lid)),
            'editar cliente: queda en el historial')
    revisar(c.reenviar_correo(lid) == 'mariana.nueva@example.com', 'reenviar correo: va al correo de la licencia')

    # estadisticas
    st = c.estadisticas(30)
    hoy = dt.date.today()
    revisar(len(st['dias']) == 30 and st['dias'][-1]['fecha'] == hoy and st['dias'][0]['fecha'] == hoy - dt.timedelta(days=29)
            and st['moneda'] == 'USD', 'estadísticas: un día por fila, también los días en 0')
    revisar(st['dias'][-1]['ventas'] == r['ventas']['ventas_hoy'] and st['dias'][-1]['ingresos'] == r['ventas']['ingresos_hoy'],
            'estadísticas: el día de hoy cuadra con el resumen')
    revisar(len(c.estadisticas(3)['dias']) == 7 and len(c.estadisticas(999)['dias']) == 365, 'estadísticas: de 7 a 365 días')

    # Las acciones de antes
    revisar(c.licencia_estado(lid, 'bloqueada')['estado'] == 'bloqueada' and datos.licencia(lid)['estado'] == 'bloqueada', 'bloquear licencia')
    revisar(c.licencia_estado(lid, 'activa')['estado'] == 'activa', 'reactivar licencia')
    equipo = d['equipos'][0]['equipo']
    r2 = c.liberar_equipo(lid, equipo)
    revisar(r2['liberados'] == 1 and len(r2['equipos']) == 1 and datos.contar_equipos(lid) == 1, 'liberar un equipo')
    revisar(c.liberar_equipo(lid, '')['liberados'] == 1 and datos.contar_equipos(lid) == 0, 'liberar todos')
    eventos = c.historial(licencia_id=lid)
    titulos = [x['titulo'] for x in eventos if x['tipo'] == 'admin']
    revisar({'Licencia bloqueada desde la app', 'Licencia reactivada desde la app', 'Equipo liberado desde la app',
             'Equipos liberados desde la app'} <= set(titulos), 'bloquear y liberar quedan en el historial')
    revisar(any(x['tipo'] == 'correo' and x['titulo'] == 'Clave reenviada desde la app' and x['detalle'] == 'A mariana.nueva@example.com.'
                for x in eventos), 'el reenvío de la clave sale como «correo», como en admin.php')
    c.licencia_estado(lid, 'activa')
    revisar(len(c.historial(licencia_id=lid)) == len(eventos), 'reactivar una licencia ya activa no se anota (como admin.php)')
    revisar(c.reenviar_correo(andrea['licencia_id']) == 'andrea.morales@example.com', 'reenviar correo de un canje')
    e = error_de(lambda: c.reenviar_correo(lic_de(datos, 'Gabriela Méndez')['id']))
    revisar(e is not None and e.codigo == 400, 'reenviar la clave de una venta reembolsada: 400, como admin.php')
    e = error_de(lambda: c.llamar('versiones', filtro='inventado'))
    revisar(e is not None and e.codigo == 400, 'versiones con un filtro que no existe: 400')
    e = error_de(lambda: c.llamar('editar_cliente', licencia_id=lid))
    revisar(e is not None and e.codigo == 400, 'editar cliente sin nombre ni correo: 400')
    rec = c.estado_recurrente(pid)
    revisar(rec['estado'] == 'paid' and rec['pago_estado'] == 'succeeded' and v.entero(rec['total']) == 2900, 'consultar Recurrente')
    p = c.marcar_reembolsado(pid)
    revisar(p['estado'] == 'reembolsado' and datos.licencia(lid)['estado'] == 'bloqueada', 'marcar reembolsado bloquea la licencia')
    revisar(c.resumen()['ventas']['pagadas'] == 21, 'el resumen ya no cuenta la venta reembolsada')
    eventos = c.historial(pedido_id=pid)
    revisar(any(x['tipo'] == 'reembolso' and x['titulo'] == 'Marcado como reembolsado desde la app' for x in eventos)
            and any(x['tipo'] == 'pago' and 'después se reembolsó' in (x['detalle'] or '') for x in eventos),
            'marcar reembolsado queda en el historial como «reembolso»')
    st = c.estadisticas(30)
    revisar(st['dias'][-1]['reembolsos'] == 1 and st['dias'][-6]['reembolsos'] == 1 and sum(d['reembolsos'] for d in st['dias']) == 2,
            'estadísticas: un reembolso cuenta en el día de la compra, como admin.php')
    e = error_de(lambda: c.reenviar_correo(jose['id']))
    revisar(e is not None and e.mensaje == 'El servidor no pudo enviar el correo.', 'correo que falla: ok=false se muestra como error')
    pendiente = next(f for f in c.ventas('pendiente') if not f['correo'])
    e = error_de(lambda: c.estado_recurrente(pendiente['id']))
    revisar(e is not None and e.codigo == 502 and 'Recurrente respondió' in e.mensaje, 'Recurrente caído: 502')
    e = error_de(lambda: c.marcar_reembolsado(pendiente['id']))
    revisar(e is not None and e.codigo == 400 and e.mensaje == 'Solo se puede marcar un pedido pagado.', 'no se marca un pedido sin pagar')
    e = error_de(lambda: c.detalle(licencia_id=9999))
    revisar(e is not None and e.codigo == 404, 'detalle que no existe: 404')
    e = error_de(lambda: c.llamar('inventada'))
    revisar(e is not None and e.mensaje == 'Acción desconocida.' and e.desconocida, 'acción desconocida: 400')

    # Solo lectura (--captura): las acciones que cambian algo ni salen
    lectura = v.ClienteApi(url, servidor_prueba.CLAVE, solo_lectura=True)
    antes, estado = len(srv.acciones_recibidas), estado_servidor(datos)
    for accion in (lambda: lectura.nota(natalia['id'], 'x'), lambda: lectura.avisar_actualizacion(natalia['id'], '5.54', forzar=True),
                   lambda: lectura.limite(natalia['id'], 3), lambda: lectura.licencia_estado(natalia['id'], 'bloqueada'),
                   lambda: lectura.editar_cliente(natalia['id'], nombre='X'), lambda: lectura.reenviar_correo(natalia['id'])):
        error_de(accion)
    revisar(len(srv.acciones_recibidas) == antes and estado_servidor(datos) == estado, 'solo lectura: ninguna acción que cambie algo sale')
    revisar(lectura.versiones()['ultima'] == '5.54', 'solo lectura: lo que solo lee sí funciona')

    # Telemetría de licencia.php: activar y verificar guardan la versión (campo o User-Agent) y el sistema
    import urllib.parse
    import urllib.request

    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # 127.0.0.1 nunca pasa por un proxy

    def licencia_php(campos, agente='CineCaptions/5.55'):
        pedido = urllib.request.Request(url.replace('admin.php', 'licencia.php'), data=urllib.parse.urlencode(campos).encode(),
                                        headers={'User-Agent': agente})
        with abridor.open(pedido, timeout=10) as respuesta:
            return json.loads(respuesta.read())

    clave_l = natalia['clave']
    act = next(a for a in datos.activaciones if a['licencia_id'] == natalia['id'])
    respuesta = licencia_php({'accion': 'verificar', 'clave': clave_l, 'equipo': act['equipo'], 'nombre_equipo': 'NATALIA-PC',
                              'so': 'Windows 11 Pro'})
    revisar(respuesta['codigo'] == 'activa' and act['version'] == '5.55' and act['version_anterior'] == '5.52'
            and act['so'] == 'Windows 11 Pro' and act['version_desde'], 'telemetría: la versión del User-Agent, la anterior y el sistema')
    licencia_php({'accion': 'verificar', 'clave': clave_l, 'equipo': act['equipo'], 'version': '5.56'}, agente='otro')
    revisar(act['version'] == '5.56' and act['version_anterior'] == '5.55', 'telemetría: el campo «version» manda')
    licencia_php({'accion': 'verificar', 'clave': clave_l, 'equipo': act['equipo'], 'version': 'abc'}, agente='CineCaptions/5.57.0')
    revisar(act['version'] == '5.57' and act['version_anterior'] == '5.56',
            'telemetría: «5.57.0» queda como 5.57 y un campo «version» que no se entiende no cuenta (como telemetria.php)')
    licencia_php({'accion': 'verificar', 'clave': clave_l, 'equipo': act['equipo']}, agente='CineCaptions/5.58-beta.1')
    revisar(act['version'] == '5.57', 'telemetría: una beta no cambia la versión guardada')
    srv.shutdown()


# ------------------------------------------------------------------ 3. Errores
def prueba_errores():
    print('Errores')
    srv, url = servidor()
    mala = v.ClienteApi(url, 'clave-equivocada')
    e = error_de(mala.resumen)
    revisar(e is not None and e.codigo == 401 and 'Cambiar clave' in e.mensaje, 'clave mala: 401 con indicación clara')
    for _ in range(4):
        error_de(mala.resumen)
    e = error_de(v.ClienteApi(url, servidor_prueba.CLAVE).resumen)
    revisar(e is not None and e.codigo == 429 and '15 minutos' in e.mensaje and e.reintentar == 900, '5 claves malas: 429 y espera 15 minutos')
    srv.shutdown()
    srv, url = servidor(sin_configurar=True)
    e = error_de(v.ClienteApi(url, servidor_prueba.CLAVE).resumen)
    revisar(e is not None and e.codigo == 503 and 'admin_clave.php' in e.mensaje, 'sin configurar: 503')
    srv.shutdown()
    e = error_de(v.ClienteApi(f'http://127.0.0.1:{puerto_libre()}/admin.php', 'x', tiempo=3).resumen)
    revisar(e is not None and e.codigo == 0 and 'conexión' in e.mensaje, 'sin servidor: mensaje de conexión')
    srv, url = servidor(viejo=True)
    e = error_de(v.ClienteApi(url, servidor_prueba.CLAVE).panel)
    revisar(e is not None and e.desconocida, 'servidor anterior: las acciones nuevas dan «Acción desconocida»')
    srv.shutdown()


# ------------------------------------------------------------------ 4. --importar-clave
def prueba_importar():
    print('--importar-clave')
    archivo = TEMPORAL / 'admin_ventas.txt'
    archivo.write_text('Clave de administrador de CineCaptions Ventas:\nclave-de-prueba-larga-123\n', encoding='utf-8')
    entorno = dict(os.environ, APPDATA=str(TEMPORAL / 'appdata_cli'), CC_VENTAS_CONFIG=str(TEMPORAL / 'appdata_cli' / v.APP))
    r = subprocess.run([sys.executable, str(AQUI / 'ventas.py'), '--importar-clave', str(archivo)], capture_output=True,
                       text=True, encoding='utf-8', env=entorno, timeout=60)
    revisar(r.returncode == 0 and r.stdout.strip() == 'Clave guardada', f'imprime «Clave guardada» (código {r.returncode})')
    config = json.loads((TEMPORAL / 'appdata_cli' / v.APP / 'config.json').read_text(encoding='utf-8'))
    if os.name == 'nt':
        revisar('clave-de-prueba' not in json.dumps(config) and v.descifrar_clave(config['clave']) == 'clave-de-prueba-larga-123',
                'la clave queda cifrada con DPAPI')
    else:
        guardada = str(config.get('clave') or '')
        revisar(guardada.startswith(v.EN_LLAVERO + ':') and 'clave-de-prueba' not in json.dumps(config)
                and v._llavero().get_password(v.servicio_llavero(), guardada.split(':', 1)[1]) == 'clave-de-prueba-larga-123',
                'la clave queda en el Llavero (no en config.json)')
    r = subprocess.run([sys.executable, str(AQUI / 'ventas.py'), '--importar-clave', str(TEMPORAL / 'no-existe.txt')],
                       capture_output=True, text=True, encoding='utf-8', env=entorno, timeout=60)
    revisar(r.returncode == 1 and 'No se guardó la clave' in r.stderr, 'archivo que no existe: error claro')


# ------------------------------------------------------------------ Ayudantes de la ventana
def aplicacion():
    return v.QApplication.instance() or v.crear_app(['prueba'])


def esperar(condicion, descripcion, segundos=20):
    app = aplicacion()
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        app.processEvents()
        if condicion():
            for _ in range(3):   # que se muestren los widgets nuevos (Qt los muestra en el siguiente ciclo)
                app.processEvents()
            return True
        time.sleep(0.01)
    revisar(False, f'(se acabó el tiempo) {descripcion}')
    return False


def quieto(w):
    return (w.trabajos.activos == 0 and not w._actualizando and not w._timer_detalle.isActive()
            and not w._timer_buscar_v.isActive() and not w._timer_buscar_c.isActive() and not w._timer_filtro.isActive()
            and not w._timer_error.isActive())


def ventana(url, clave=servidor_prueba.CLAVE, cargar=True, mostrar=False):
    w = v.VentanaPrincipal(v.Configuracion(), url, captura=True)
    w.mensajes, w.preguntas = [], []
    w._mensaje = lambda titulo, texto, tipo='error': w.mensajes.append((titulo, texto))
    w._confirmar = lambda pregunta, *a, **k: w.preguntas.append(pregunta) or True
    # (la pregunta de «Eliminar venta», con su casilla: dice que sí, con la casilla desmarcada)
    w._preguntar_eliminar = lambda pregunta, *a, **k: (w.preguntas.append(pregunta) or True, False)
    if mostrar:
        w.setAttribute(v.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        w.resize(1440, 900)
        w.show()
    w.usar_clave(clave)
    if cargar:
        w.actualizar_todo()
        esperar(lambda: w.intento_listo and quieto(w), 'primera carga')
    return w


def elegir(w, tabla, condicion):
    proxy = tabla.model()
    for n in range(proxy.rowCount()):
        fila = w._fila_de(tabla, proxy.index(n, 0))
        if condicion(fila):
            tabla.selectRow(n)
            esperar(lambda: w.panel.detalle is not None and quieto(w), 'detalle de la fila')
            return fila
    revisar(False, 'no se encontró la fila buscada')
    return None


def apretar(w, b, descripcion):
    p = getattr(w, 'panel', None)
    for clave, pagina in (getattr(p, '_paginas', None) or {}).items():   # (2.3: como el dueño, primero la pestaña del botón)
        if pagina.isAncestorOf(b) and p.pila.currentWidget() is not pagina and p.btn_pestana[clave].isVisible():
            p.btn_pestana[clave].click()
    revisar(b.isVisible() and b.isEnabled(), f'botón visible y activo: {descripcion}')
    b.click()
    esperar(lambda: quieto(w), descripcion)


def filas_equipo(w):
    return [w.panel.lista_eq.itemAt(i).widget() for i in range(w.panel.lista_eq.count())
            if isinstance(w.panel.lista_eq.itemAt(i).widget(), v.FilaEquipo)]


def fila_de(modelo, ident):
    return modelo.fila(modelo.buscar('id', ident)[0])


# ------------------------------------------------------------------ 5. La ventana
def prueba_ventana():
    print('Ventana (offscreen)')
    srv, url = servidor()
    datos = srv.datos
    aplicacion()
    w = ventana(url, mostrar=True)
    revisar(w.servidor_nuevo is True and not w.banda_servidor.isVisibleTo(w), 'servidor nuevo: sin el aviso de «falta subir»')
    revisar(w.modelo_v.rowCount() == 24 and w.modelo_c.rowCount() == 3, 'tablas cargadas (24 ventas, 3 canjes)')
    revisar('$58.00' in w.t_hoy.valor.text() and '2 ventas' == w.t_hoy.detalle.text(), 'tarjeta Hoy: $58.00 y 2 ventas')
    revisar('$608.00' in w.t_total.valor.text() and '4 bloqueadas' == w.t_lic.detalle.text(), 'tarjetas Total y Licencias')
    revisar('23' in w.t_equipos.valor.text() and '26' in w.t_equipos.detalle.text(), 'tarjeta de equipos activos en 30 días')
    revisar(w.barra.botones['canjes'].contador == 3 and w.barra.botones['versiones'].contador == 9
            and w.barra.botones['ventas'].contador == 24, 'la isla del menú con los contadores')
    revisar(srv.acciones_recibidas[:1] == ['panel'], '«Actualizar» empieza con una sola petición (panel)')

    # Resumen: gráfica, versiones y últimas ventas
    revisar(w.pagina == 'resumen' and len(w.grafica.dias) == v.DIAS_GRAFICA, f'gráfica de {v.DIAS_GRAFICA} días')
    revisar(w.bloque_versiones.numero.text() == '5.54' and w.bloque_versiones.cifras['al_dia'].text() == '12'
            and w.bloque_versiones.cifras['desactualizados'].text() == '9' and w.bloque_versiones.cifras['sin_datos'].text() == '3',
            'bloque de versiones: la última y cuántos al día, desactualizados y sin datos')
    revisar(w.bloque_versiones.grafica.filas == [('5.54', 12), ('5.53', 7), ('5.52', 2), (None, 3)], 'bloque de versiones: barras por versión')
    revisar(not w.bloque_versiones.btn_anunciar.isVisible() and not hasattr(w, 'chk_auto') and not hasattr(w, 'btn_actualizar'),
            '2.3: el Resumen sin «Anunciar» (está en Versiones) y el encabezado sin «Actualizar» ni la casilla de cada 2 min')
    g = w.grafica
    hoy = len(g.dias) - 1
    area = g._area()
    punto = v.QPointF(area.left() + area.width() / len(g.dias) * (hoy + 0.5), area.center().y())
    v.QApplication.sendEvent(g, v.QMouseEvent(v.QEvent.Type.MouseMove, punto, g.mapToGlobal(punto), v.Qt.MouseButton.NoButton,
                                              v.Qt.MouseButton.NoButton, v.Qt.KeyboardModifier.NoModifier))
    revisar(g._encima == hoy and g.dias[hoy]['ingresos'] == 5800, 'al pasar el mouse por la barra de hoy se ve su monto')
    imagen = g.grab()
    revisar(not imagen.isNull(), 'la gráfica se dibuja con el globito')
    caja = g.caja_globo()
    revisar(caja is not None and not caja.intersects(g.barra(hoy)) and v.QRectF(g.rect()).contains(caja),
            'con la barra más alta, el globito va a un lado: no la tapa y no se sale de la gráfica')
    baja = min((n for n, d in enumerate(g.dias) if d['ingresos']), key=lambda n: g.dias[n]['ingresos'])
    g._encima = baja
    revisar(g.caja_globo().bottom() <= g.barra(baja).top(), 'con una barra baja, el globito va arriba de ella')
    g._encima = None
    # (2.7: con la cabecera 12 px más abajo, la tarjeta puede cambiar de alto al llegar los datos y repintarse en el
    # siguiente ciclo: se espera a que esté asentada)
    esperar(lambda: w.recientes._filas.count() == min(len(w.recientes.ventas), w.recientes.cuantas), '«Últimas ventas» asentada')
    n = w.recientes._filas.count()   # (tantas como caben a la par de la gráfica)
    revisar(n == min(len(w.recientes.ventas), w.recientes.cuantas) and n >= 6, f'«Últimas ventas» con las que caben ({n})')
    revisar(w.recientes.vacio.mensaje == '', '«Últimas ventas» llena: sin el letrero de abajo')

    # Ventas: versión y último uso, filtros rápidos
    w.ir_a('ventas')
    t = w.tabla_v
    y = t.rowViewportPosition(1) + t.rowHeight(1) // 2
    v.QApplication.sendEvent(t.viewport(), v.QMouseEvent(v.QEvent.Type.MouseMove, v.QPointF(40, y), t.viewport().mapToGlobal(v.QPointF(40, y)),
                                                         v.Qt.MouseButton.NoButton, v.Qt.MouseButton.NoButton, v.Qt.KeyboardModifier.NoModifier))
    revisar(t.fila_encima == 1 and not t.viewport().grab().isNull(), 'la fila bajo el mouse se ilumina completa (no solo la celda)')
    v.QApplication.sendEvent(t.viewport(), v.QEvent(v.QEvent.Type.Leave))
    revisar(t.fila_encima == -1, 'al salir de la tabla ya no queda ninguna fila iluminada')
    revisar(isinstance(t.horizontalHeader(), v.Encabezado) and not t.horizontalHeader().grab().isNull(),
            'encabezado con la flechita de orden junto al título')
    app = aplicacion()
    app.setFont(v.QFont('Arial', 9), 'QAbstractItemView')   # lo que hace Windows al aplicar la hoja de estilos o cambiar el tema
    v.QApplication.sendEvent(w, v.QEvent(v.QEvent.Type.ThemeChange))
    esperar(lambda: v.QApplication.font(t).family() == 'Inter', 'Inter otra vez en las tablas')
    revisar(v.QApplication.font('QAbstractItemView') == v.QApplication.font() and v.QApplication.font(t).family() == 'Inter',
            'las tablas vuelven a Inter si Windows les pone su letra')
    fila = elegir(w, w.tabla_v, lambda f: f['nombre'] == 'Mariana López')
    lid = fila['licencia_id']
    col = {c: i for i, (c, _t, _a) in enumerate(v.ModeloVentas.COLUMNAS)}
    indice = w.modelo_v.index(w.modelo_v.buscar('id', fila['id'])[0], col['version'])
    revisar(indice.data(v.ROL_INSIGNIA)[:2] == ('5.54', v.EXITO), 'columna Versión: insignia verde «al día»')
    fernanda = next(f for f in w.modelo_v.filas if (f['nombre'] or '').startswith('María Fernanda'))
    indice = w.modelo_v.index(w.modelo_v.buscar('id', fernanda['id'])[0], col['version'])
    revisar(indice.data(v.ROL_INSIGNIA)[1] == v.AVISO and '1 de 2' in indice.data(v.Qt.ItemDataRole.ToolTipRole),
            'columna Versión: naranja si algún equipo está desactualizado')
    jose = next(f for f in w.modelo_v.filas if f['nombre'] == 'José Ñúñez')
    indice = w.modelo_v.index(w.modelo_v.buscar('id', jose['id'])[0], col['version'])
    revisar(indice.data(v.ROL_INSIGNIA)[:2] == ('Sin datos', v.TEXTO_TENUE), 'columna Versión: gris si no hay datos')
    revisar(w.modelo_v.index(0, col['uso']).data() not in ('', None), 'columna «Último uso»')
    w.fechas_v.poner(1)
    revisar(w.proxy_v.rowCount() == 2 and 'de hoy' in w.lbl_pie_v.text(), 'filtro rápido «Hoy»: 2 ventas')
    w.fechas_v.poner(7)
    revisar(w.proxy_v.rowCount() == sum(1 for f in w.modelo_v.filas
                                        if v.leer_fecha(f['pagado'] or f['creado']).date() >= dt.date.today() - dt.timedelta(days=6)),
            'filtro rápido «7 días»')
    w.fechas_v.poner(0)
    revisar(w.proxy_v.rowCount() == 24, 'filtro rápido «Todo»')
    esperar(lambda: quieto(w), 'quieto')

    revisar(w.panel.clave.text() == 'CC-7K2M-Q9XA-4HBR-T3WZ' and len(filas_equipo(w)) == 2, 'panel: clave y 2 equipos')
    revisar(all(f.version.text() == '5.54' and f.version.isVisibleTo(f) for f in filas_equipo(w))
            and 'Windows 11' in filas_equipo(w)[0].detalle.texto(), 'panel: cada equipo con su versión y su sistema')
    revisar(w.panel.btn_reembolso.isVisible() and w.panel.btn_recurrente.isVisible(), 'panel: acciones de una venta pagada')
    revisar(w.panel.visible(w.panel.sec_hist) and w.panel.historial.eventos and w.panel.historial._lista.count() > 0,
            'panel: historial en línea de tiempo')
    revisar(w.panel.visible(w.panel.sec_notas) and w.panel.fila_limite.isVisible() and w.panel.btn_editar.isVisible(),
            'panel: notas, límite de equipos y «Editar»')
    p = w.panel
    revisar([c for c, b in p.btn_pestana.items() if b.isVisible()] == ['licencia', 'pago', 'notas']
            and p.pila.currentWidget() is p._paginas['licencia'] and p.btn_pestana['licencia'].isChecked(),
            '2.3: el panel en pestañas «Licencia · Pago · Notas e historial»; se abre en «Licencia»')
    p.btn_pestana['notas'].click()
    revisar(p.sec_hist.isVisible() and p.sec_notas.isVisible() and not p.sec_lic.isVisible(), '«Notas e historial»: la nota y el historial')
    clave0 = p.clave.text()
    elegir(w, w.tabla_v, lambda f: f.get('licencia_id') and f.get('clave') != clave0)
    revisar(p.pila.currentWidget() is p._paginas['notas'], 'otra venta: se queda en la pestaña que eligió el dueño')
    p.btn_pestana['licencia'].click()
    elegir(w, w.tabla_v, lambda f: f.get('clave') == clave0)
    revisar(not w.panel.btn_avisar.isVisible(), 'todo al día: no se ofrece «Avisar que actualice»')
    w.panel.btn_copiar.click()
    revisar(v.QGuiApplication.clipboard().text() == 'CC-7K2M-Q9XA-4HBR-T3WZ', 'Copiar pone la clave en el portapapeles')

    apretar(w, w.panel.btn_bloquear, 'bloquear licencia')
    revisar(datos.licencia(lid)['estado'] == 'bloqueada', 'el servidor la bloqueó')
    revisar(fila_de(w.modelo_v, fila['id'])['licencia_estado'] == 'bloqueada', 'la fila de la tabla se actualizó')
    revisar(w.panel.btn_bloquear.text().strip() == 'Reactivar licencia', 'el botón cambia a «Reactivar licencia»')
    revisar(w.resumen['licencias']['bloqueadas'] == 5, 'el resumen se actualizó (5 bloqueadas)')
    revisar(any(e['titulo'] == 'Licencia bloqueada desde la app' for e in w.panel.historial.eventos), 'el historial lo muestra')
    apretar(w, w.panel.btn_bloquear, 'reactivar licencia')
    revisar(datos.licencia(lid)['estado'] == 'activa' and w.panel.btn_bloquear.text().strip() == 'Bloquear licencia', 'reactivada')

    # Límite de equipos con − y +
    revisar(not w.panel.btn_menos.isEnabled() and w.panel.btn_mas_limite.isEnabled(),
            'con 2 equipos y límite 2 no se puede bajar el límite')
    apretar(w, w.panel.btn_mas_limite, 'límite +1')
    revisar(datos.licencia(lid)['limite'] == 3 and w.panel.lbl_limite.text() == '3' and any('límite' in p for p in w.preguntas),
            'límite: pidió confirmación y quedó en 3')
    revisar(fila_de(w.modelo_v, fila['id'])['limite'] == 3, 'la tabla muestra el límite nuevo')
    apretar(w, w.panel.btn_menos, 'límite −1')
    revisar(datos.licencia(lid)['limite'] == 2, 'límite de vuelta en 2')

    apretar(w, filas_equipo(w)[0].btn, 'liberar este equipo')
    revisar(datos.contar_equipos(lid) == 1 and len(filas_equipo(w)) == 1, 'queda 1 equipo (servidor y panel)')
    revisar(fila_de(w.modelo_v, fila['id'])['equipos'] == 1, 'la columna Equipos dice 1')

    w._confirmar = lambda pregunta, *a, **k: w.preguntas.append(pregunta) and False   # «Cancelar»
    antes = len(w.preguntas)
    filas_equipo(w)[0].btn.click()
    esperar(lambda: quieto(w), 'cancelar')
    revisar(len(w.preguntas) == antes + 1 and datos.contar_equipos(lid) == 1, 'si se cancela la confirmación no se libera nada')
    w._confirmar = lambda pregunta, *a, **k: w.preguntas.append(pregunta) or True

    # Notas internas
    w.panel.txt_nota.setPlainText('Pidió factura a nombre de Estudio ML.')
    revisar(w.panel.btn_nota.isEnabled() and 'Sin guardar' in w.panel.lbl_nota.texto(), 'nota escrita: «Sin guardar»')
    apretar(w, w.panel.btn_nota, 'guardar nota')
    revisar(datos.licencia(lid)['nota'] == 'Pidió factura a nombre de Estudio ML.' and 'Guardada' in w.panel.lbl_nota.texto()
            and not w.panel.btn_nota.isEnabled(), 'nota guardada en el servidor')
    w.panel.txt_nota.setPlainText('x' * 2100)
    revisar(len(w.panel.txt_nota.toPlainText()) == v.MAX_TEXTO, 'la nota no pasa de 2000')
    w.panel.txt_nota.setPlainText('Borrador sin guardar')
    elegir(w, w.tabla_v, lambda f: f['nombre'] == 'Carlos Andrés Pérez')
    elegir(w, w.tabla_v, lambda f: f['id'] == fila['id'])
    revisar(w.panel.txt_nota.toPlainText() == 'Borrador sin guardar', 'un borrador de nota no se pierde al elegir otra fila')
    w.actualizar_todo()   # (como la actualización automática de cada 2 minutos: vuelve a pedir el detalle)
    esperar(lambda: quieto(w), 'actualizar con un borrador en la nota')
    revisar(w.panel.txt_nota.toPlainText() == 'Borrador sin guardar' and 'Sin guardar' in w.panel.lbl_nota.texto(),
            'un borrador de nota no se pierde al actualizar')
    w.panel.txt_nota.setPlainText('Nota uno')
    w.panel.btn_nota.click()
    w.panel.txt_nota.setPlainText('Nota uno y algo más')   # se sigue escribiendo mientras se guarda
    esperar(lambda: quieto(w), 'guardar la nota mientras se escribe')
    revisar(datos.licencia(lid)['nota'] == 'Nota uno' and w.panel.txt_nota.toPlainText() == 'Nota uno y algo más'
            and 'Sin guardar' in w.panel.lbl_nota.texto() and w.panel.btn_nota.isEnabled(),
            'lo que se escribe mientras se guarda la nota queda como borrador')
    w.panel.txt_nota.setPlainText('')
    apretar(w, w.panel.btn_nota, 'borrar nota')
    revisar(datos.licencia(lid)['nota'] is None and w.aviso.texto.text() == 'Nota borrada.', 'nota borrada')

    # Editar cliente
    w._dialogo_cliente = lambda nombre, correo: {'nombre': 'Mariana López de León', 'correo': 'mariana.leon@example.com'}
    apretar(w, w.panel.btn_editar, 'editar cliente')
    revisar(datos.licencia(lid)['correo'] == 'mariana.leon@example.com' and datos.pedido(fila['id'])['nombre'] == 'Mariana López de León',
            'editar cliente: el servidor cambió la licencia y la compra')
    revisar(w.panel.nombre.texto() == 'Mariana López de León' and fila_de(w.modelo_v, fila['id'])['correo'] == 'mariana.leon@example.com',
            'editar cliente: el panel y la tabla muestran los datos nuevos')
    d = v.DialogoCliente(w, 'Ana', 'ana@example.com')
    d.correo.setText('no-es-correo')
    d.accept()
    revisar(d.result() != v.QDialog.DialogCode.Accepted and d.error.isVisibleTo(d), 'el diálogo no acepta un correo no válido')
    d.correo.setText('ana@example.com')
    d.nombre.setText('Ana  María ')
    revisar(d.cambios() == {'nombre': 'Ana María'}, 'el diálogo manda solo lo que cambió')

    apretar(w, w.panel.btn_reenviar, 'reenviar correo')
    revisar(w.aviso.texto.text() == 'Correo enviado a mariana.leon@example.com.', 'reenviar: al correo nuevo de la licencia')
    apretar(w, w.panel.btn_recurrente, 'consultar Recurrente')
    revisar(w.panel.caja_rec.isVisible() and 'Pagado (paid)' in [w.panel.ficha_rec._grid.itemAt(i).widget().text()
                                                                 for i in range(w.panel.ficha_rec._grid.count())],
            'la respuesta de Recurrente aparece en el panel')
    apretar(w, w.panel.btn_reembolso, 'marcar como reembolsado')
    revisar(any('reembolsado' in p for p in w.preguntas), 'pidió confirmación para el reembolso')
    revisar(datos.pedido(fila['id'])['estado'] == 'reembolsado' and datos.licencia(lid)['estado'] == 'bloqueada', 'el servidor lo marcó')
    revisar(fila_de(w.modelo_v, fila['id'])['estado'] == 'reembolsado', 'la fila dice Reembolsada')
    revisar(not w.panel.btn_reembolso.isVisible(), 'ya no se ofrece «Marcar como reembolsado»')
    revisar(w.resumen['ventas']['pagadas'] == 21, 'el resumen se actualizó (21 pagadas)')

    # Avisar que actualice (y reenviar con forzar si ya se le avisó)
    fila = elegir(w, w.tabla_v, lambda f: f['nombre'] == 'Lucía Fernández')
    esperar(lambda: quieto(w) and w.panel.avisos_licencia is not None, 'avisos de la licencia')
    revisar(w.panel.btn_avisar.isVisible() and w.panel.btn_avisar.text().strip() == 'Avisar que actualice a la 5.54',
            'equipo desactualizado: «Avisar que actualice a la 5.54»')
    w._confirmar = lambda pregunta, *a, **k: w.preguntas.append(pregunta) and False   # «Cancelar»
    n = len(datos.avisos)
    w.panel.btn_avisar.click()
    esperar(lambda: quieto(w), 'cancelar el aviso')
    revisar(len(datos.avisos) == n and w.preguntas[-1].startswith('¿Avisar a'), 'si se cancela la pregunta, no se manda el aviso')
    w._confirmar = lambda pregunta, *a, **k: w.preguntas.append(pregunta) or True
    apretar(w, w.panel.btn_avisar, 'avisar que actualice')
    revisar(len(datos.avisos) == n + 1 and datos.avisos[-1]['ok'] and datos.avisos[-1]['licencia_id'] == fila['licencia_id']
            and datos.avisos[-1]['version'] == '5.54', 'el servidor mandó el aviso de la 5.54')
    revisar(datos.avisos[-1]['mensaje'].startswith('Exporta'), 'el aviso lleva lo nuevo del manifiesto de esa versión')
    revisar(w.aviso.texto.text() == 'Aviso enviado a lucia.fernandez@example.com.', 'aviso: enviado a su correo')
    esperar(lambda: quieto(w) and w.panel.aviso_de('5.54') is not None, 'avisos de la licencia otra vez')
    revisar(w.panel.btn_avisar.text().strip() == 'Reenviar aviso de la 5.54' and w.panel.nota_avisar.isVisible(),
            'ya avisado: el botón ofrece reenviar')
    info = w.version_info
    w.version_info = dict(info, version='5.53')   # lo que la app leyó es de otra versión (acaba de salir una nueva)
    apretar(w, w.panel.btn_avisar, 'reenviar aviso')
    w.version_info = info
    revisar(len(datos.avisos) == n + 2 and datos.avisos[-1]['ok'] and w.preguntas[-1].startswith('¿Reenviar el aviso'),
            'reenviar aviso: forzar=true y con su pregunta')
    revisar(datos.avisos[-1]['mensaje'] == '', 'si lo leído es de otra versión, el aviso no lleva esas notas')
    w.panel.avisos_licencia = []   # la app no sabe que ya le avisó: el servidor responde ya_avisado
    antes = len(w.preguntas)
    w.panel.btn_avisar.click()
    esperar(lambda: quieto(w), 'avisar sin saber que ya se avisó')
    revisar(len(datos.avisos) == n + 4 and datos.avisos[-2]['motivo'] == 'ya_avisado' and datos.avisos[-1]['ok']
            and 'Ya le avisaste de esta versión' in w.preguntas[antes:] and len(w.preguntas) == antes + 2,
            'ya_avisado: la app pregunta una vez y reenvía con forzar=true')
    fila = elegir(w, w.tabla_v, lambda f: f['nombre'] == 'Paola Girón')
    esperar(lambda: quieto(w) and w.panel.avisos_licencia is not None, 'avisos de Paola')
    w.mensajes.clear()
    apretar(w, w.panel.btn_avisar, 'avisar a quien se dio de baja')
    revisar(w.mensajes and w.mensajes[-1][0] == 'No se mandó el aviso' and 'no recibir' in w.mensajes[-1][1], 'baja: lo explica')

    fila = elegir(w, w.tabla_v, lambda f: (f['nombre'] or '').startswith('María Fernanda'))
    apretar(w, w.panel.btn_liberar_todos, 'liberar todos')
    revisar(datos.contar_equipos(fila['licencia_id']) == 0 and not filas_equipo(w), 'sin equipos después de «Liberar todos»')

    elegir(w, w.tabla_v, lambda f: f['nombre'] == 'Gabriela Méndez')
    revisar(w.panel.btn_reenviar.isVisible() and not w.panel.btn_reenviar.isEnabled(),
            'venta reembolsada: «Reenviar correo» apagado (admin.php no reenvía esa clave)')
    elegir(w, w.tabla_v, lambda f: f['nombre'] == 'José Ñúñez')
    w.mensajes.clear()
    apretar(w, w.panel.btn_reenviar, 'reenviar correo que falla')
    revisar(w.mensajes and w.mensajes[-1] == ('No se pudo reenviar el correo', 'El servidor no pudo enviar el correo.'),
            'el error del servidor se muestra tal cual')

    w.buscar_v.setText('ñúñez')
    esperar(lambda: not w._timer_buscar_v.isActive() and quieto(w) and w.modelo_v.rowCount() == 1, 'búsqueda')
    w.buscar_v.clear()
    w.filtro.setCurrentIndex(w.filtro.findData('pendiente'))
    esperar(lambda: quieto(w) and w.modelo_v.rowCount() == 3, 'filtro «Pagos sin completar»')
    revisar(w.modelo_v.rowCount() == 3, 'filtro «Pagos sin completar»: 3')
    elegir(w, w.tabla_v, lambda f: f['estado'] == 'pendiente')
    revisar(not w.panel.btn_bloquear.isVisible() and w.panel.btn_recurrente.isVisible(), 'pago sin completar: solo consultar Recurrente')
    w.filtro.setCurrentIndex(w.filtro.findData(''))
    esperar(lambda: quieto(w) and w.modelo_v.rowCount() == 24, 'filtro normal')

    # Exportar las ventas a CSV (con las columnas nuevas)
    ruta = TEMPORAL / 'ventas-app.csv'
    original = v.QFileDialog.getSaveFileName
    v.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(ruta), ''))
    try:
        w.exportar_csv()
        lineas = list(csv.reader(ruta.read_text(encoding='utf-8-sig').splitlines(), delimiter=v.separadores_excel()[0]))
        revisar(len(lineas) == 25 and lineas[0][-5:-2] == ['Versión', 'Último uso', 'Equipos desactualizados']
                and lineas[0][-2:] == ['Cupón', 'Descuento']
                and sum(1 for l in lineas[1:] if l[-2] == 'LANZAMIENTO' and l[-1].replace(',', '.') == '10.00') == 3,
                'Exportar CSV de ventas: 24 filas con versión, último uso y el cupón (las 3 de LANZAMIENTO, −$10)')

        # Versiones
        w.ir_a('versiones')
        esperar(lambda: quieto(w) and w.modelo_ver.rowCount() > 0, 'página Versiones')
        clientes = {e['licencia_id'] for e in w.versiones['equipos']}
        revisar(w.modelo_ver.rowCount() == len(clientes) and sum(c['equipos'] for c in w.modelo_ver.filas) == 26 - 2 - 1
                and w.grafica_versiones.filas, 'Versiones: un cliente por fila (con todos sus equipos) y la gráfica')
        activos = [c for c in w.modelo_ver.filas if c['licencia_estado'] == 'activa']
        revisar(w.filtro_ver.botones['desactualizado'].text().endswith(str(v.contar_estados(activos, w.modelo_ver)['desactualizado'])),
                'Versiones: cada filtro con su cantidad (clientes con la licencia activa)')
        w.filtro_ver.poner('desactualizado')
        revisar(w.proxy_ver.rowCount() == sum(1 for c in activos if w.modelo_ver.estado(c) == 'desactualizado') > 0,
                'filtro «Desactualizados»')
        w.filtro_ver.poner('sin_datos')
        revisar(w.proxy_ver.rowCount() == sum(1 for c in activos if not any(v.texto_version(e['version']) for e in c['filas'])),
                'filtro «Sin datos»')
        w.filtro_ver.poner('todos')
        peticiones = len(srv.acciones_recibidas)
        w.buscar_ver.setText('macbook')
        esperar(lambda: quieto(w), 'búsqueda en versiones')
        revisar(w.proxy_ver.rowCount() == 3 and len(srv.acciones_recibidas) == peticiones,
                'búsqueda en versiones, también en el nombre de sus equipos (sin pedir nada al servidor)')
        w.buscar_ver.clear()
        esperar(lambda: quieto(w), 'quieto')
        e = elegir(w, w.tabla_ver, lambda e: e['cliente'] == 'Ricardo Alvarado' and e['version'] == '5.53')
        cv = {c: i for i, (c, _t, _a) in enumerate(v.ModeloVersiones.COLUMNAS)}
        n = w.modelo_ver.buscar('id', e['id'])[0]
        revisar(w.modelo_ver.index(n, cv['version']).data(v.ROL_INSIGNIA)[:2] == ('5.53', v.AVISO)
                and w.modelo_ver.index(n, cv['pcs']).data() == '2 equipos'
                and w.modelo_ver.index(n, cv['pcs']).data(v.ROL_SEGUNDA) == '1 con una versión vieja'
                and w.modelo_ver.index(n, cv['aviso']).data().startswith('Avisado')
                and '5.54' in w.modelo_ver.index(n, cv['aviso']).data(v.Qt.ItemDataRole.ToolTipRole),
                'Versiones: la versión más vieja de sus equipos, cuántos van atrás y el aviso de la 5.54')
        revisar(w.panel.tipo.text().startswith('LICENCIA') and w.panel.nombre.texto() == 'Ricardo Alvarado'
                and w.panel.btn_avisar.text().strip() == 'Reenviar aviso de la 5.54'
                and not w.panel.btn_eliminar.isVisible(),
                'elegir un cliente abre su licencia en el panel (sin «Eliminar venta»: eso es en Ventas)')
        w.exportar_csv()
        lineas = list(csv.reader(ruta.read_text(encoding='utf-8-sig').splitlines(), delimiter=v.separadores_excel()[0]))
        revisar(len(lineas) == len(w.versiones['equipos']) + 1 and 'Versión anterior' in lineas[0] and 'Sistema' in lineas[0],
                'Exportar CSV de versiones: un equipo por fila, con todos sus datos')
    finally:
        v.QFileDialog.getSaveFileName = original

    # Avisos
    w.ir_a('avisos')
    esperar(lambda: quieto(w) and w.modelo_av.rowCount() > 0, 'página Avisos')
    revisar(w.modelo_av.rowCount() == len(datos.avisos), 'Avisos: el historial de los correos de actualización')
    w.filtro_av.poner('no')
    revisar(w.proxy_av.rowCount() == sum(1 for a in datos.avisos if not a['ok']), 'Avisos: filtro «No enviados»')
    w.filtro_av.poner('')

    w.ir_a('canjes')
    fila = elegir(w, w.tabla_c, lambda f: f['nombre'] == 'Fernando Ríos')
    revisar(w.panel.btn_bloquear.text().strip() == 'Reactivar licencia' and not w.panel.btn_recurrente.isVisible(),
            'canje reembolsado en Gumroad: se puede reactivar, sin Recurrente')
    fila = elegir(w, w.tabla_c, lambda f: f['nombre'] == 'Andrea Morales')
    cc = {c: i for i, (c, _t, _a) in enumerate(v.ModeloCanjes.COLUMNAS)}
    revisar(w.modelo_c.index(w.modelo_c.buscar('id', fila['id'])[0], cc['version']).data() == '5.53', 'Canjes con la versión')
    revisar(w.panel.btn_avisar.text().strip() == 'Reenviar aviso de la 5.54', 'canje ya avisado: ofrece reenviar')
    w.close()

    # Clave mala en la ventana: aviso con «Cambiar clave» y sin reintentos automáticos
    fallos = len(srv.fallos)
    w2 = ventana(url, 'clave-equivocada', cargar=False)
    w2.actualizar_todo()
    esperar(lambda: w2.intento_listo and w2.trabajos.activos == 0, 'carga con clave mala')
    revisar(w2._clave_mala and w2.banda.isVisibleTo(w2) and w2.banda.btn_clave.isVisibleTo(w2), 'clave mala: aviso con «Cambiar clave»')
    revisar(len(srv.fallos) == fallos + 1, 'una sola petición con la clave mala')
    w2._actualizar_solo()
    revisar(len(srv.fallos) == fallos + 1, 'la actualización automática no insiste con una clave mala')
    w2.close()
    srv.shutdown()


# ------------------------------------------------------------------ 6. Casos difíciles de la ventana
def prueba_casos_ventana():
    print('Ventana: casos difíciles')
    aplicacion()

    # a) La clave se corrige mientras todavía viaja la petición con la clave mala
    srv, url = servidor(demora=0.8)
    w = ventana(url, 'clave-equivocada', cargar=False)
    w.actualizar_todo()
    w._guardar_y_usar(servidor_prueba.CLAVE)
    esperar(lambda: quieto(w) and w.modelo_v.rowCount() == 24, 'carga con la clave corregida')
    revisar(w.modelo_v.rowCount() == 24 and not w._clave_mala and not w.banda.isVisibleTo(w),
            'clave corregida a medio cargar: se cargan los datos y no queda el aviso de clave mala')
    w.close()
    srv.shutdown()

    # b) Con la clave rechazada, filtrar, buscar, elegir una fila o la actualización automática no mandan más intentos
    srv, url = servidor()
    w = ventana(url)
    srv.clave = 'otra-clave'   # el dueño cambió la clave en el servidor
    w.actualizar_todo()
    esperar(lambda: quieto(w) and w._clave_mala, 'clave rechazada')
    antes = len(srv.fallos)
    w.ir_a('ventas')
    w.filtro.setCurrentIndex(w.filtro.findData('todos'))
    w.buscar_v.setText('ana')
    esperar(lambda: quieto(w), 'filtrar y buscar con la clave rechazada')
    w.tabla_v.selectRow(0)
    esperar(lambda: quieto(w), 'elegir una fila con la clave rechazada')
    w.ir_a('versiones')
    w.ir_a('avisos')
    w._actualizar_solo()
    esperar(lambda: quieto(w), 'actualización automática con la clave rechazada')
    revisar(len(srv.fallos) == antes, f'clave rechazada: no salen más intentos ({len(srv.fallos) - antes} de más)')
    w.ir_a('ventas')
    w.tabla_v.selectRow(1)
    esperar(lambda: quieto(w), 'elegir otra fila')
    revisar(w.panel.caja_error.isVisibleTo(w.panel) and 'clave' in w.panel.error.text(), 'el panel dice que falta una clave válida')
    w.close()
    srv.shutdown()

    # c) Cambiar de API a media carga: no quedan datos del servidor anterior
    viejo, url_viejo = servidor(demora=0.8)
    nuevo, url_nuevo = servidor(sin_configurar=True)
    w = ventana(url_viejo, cargar=False)
    w.actualizar_todo()
    w.api_url = url_nuevo
    w._vaciar_datos()
    w.usar_clave(servidor_prueba.CLAVE)
    w.actualizar_todo()
    esperar(lambda: quieto(w) and viejo.claves_recibidas, 'cambio de API')
    time.sleep(1)
    esperar(lambda: quieto(w), 'respuestas viejas')
    revisar(w.resumen is None and w.modelo_v.rowCount() == 0 and 'admin_clave.php' in w.banda.texto.text(),
            'otra API a media carga: lo que responde el servidor anterior se descarta')
    w.close()
    viejo.shutdown()
    nuevo.shutdown()

    # d) MySQL en UTC (como en el hosting): se ven las mismas horas que con MySQL en la hora de esta PC
    vistas = []
    arranque = dt.datetime.now()
    for opciones in ({}, {'utc': True}):
        srv, url = servidor(ahora=arranque, **opciones)
        w = ventana(url)
        filas = []
        for tabla in (w.tabla_v, w.tabla_c):
            proxy = tabla.model()
            modelo = proxy.sourceModel()
            columnas = [c for c, (clave, _t, _a) in enumerate(modelo.COLUMNAS) if clave != 'uso']   # («hace 5 min» cambia)
            filas += [[proxy.index(n, c).data() for c in columnas] for n in range(proxy.rowCount())]
        vistas.append((filas, w.t_hoy.valor.text(), v.Reloj.zona()))
        w.close()
        srv.shutdown()
    revisar(vistas[1][2] == 'UTC' and vistas[0][2] != '', f'zona del servidor detectada ({vistas[0][2]} y {vistas[1][2]})')
    revisar(vistas[0][0] == vistas[1][0] and vistas[0][1] == vistas[1][1] and len(vistas[0][0]) == 27,
            'MySQL en UTC: las tablas muestran las mismas horas locales')
    v.Reloj.desfase = None

    # e) Una redirección no se sigue (urllib la seguiría con la cabecera X-Admin-Clave)
    destino, url_destino = servidor()
    origen, url_origen = servidor(redirigir=url_destino)
    e = error_de(v.ClienteApi(url_origen, servidor_prueba.CLAVE).resumen)
    revisar(e is not None and e.codigo == 302 and 'redirigió' in e.mensaje, 'redirección: no se sigue y se explica')
    revisar(destino.claves_recibidas == [], 'la clave no llega a la dirección de la redirección')
    destino.shutdown()
    origen.shutdown()

    # f) «Cargar más»: sin filas repetidas si entra una venta nueva, y desde el principio si cambió la búsqueda
    srv, url = servidor()
    limite_original = v.LIMITE_LISTA
    v.LIMITE_LISTA = 4
    try:
        w = ventana(url)
        w.ir_a('ventas')
        revisar(w.modelo_v.rowCount() == 4 and w.btn_mas.isVisibleTo(w), 'con más ventas que el límite aparece «Cargar más»')
        ahora = servidor_prueba._f(srv.datos.ahora())
        n = len(srv.datos.pedidos) + 1
        srv.datos.pedidos.append({'id': n, 'token': f'{n:032x}', 'checkout_id': f'ch_nuevo{n}', 'estado': 'pagado',
                                  'correo': 'nuevo@example.com', 'nombre': 'Cliente Nuevo', 'monto': 2900, 'moneda': 'USD',
                                  'pago_ids': f'pa_nuevo{n}', 'licencia_id': None, 'correo_enviado': 1, 'creado': ahora,
                                  'pagado': ahora, 'reembolsado_en': None})
        w.btn_mas.click()
        esperar(lambda: quieto(w) and w.modelo_v.rowCount() > 4, 'segunda página')
        ids = [f['id'] for f in w.modelo_v.filas]
        revisar(len(ids) == 7 and len(set(ids)) == len(ids), f'«Cargar más» no repite la venta que se corrió ({len(ids)} filas)')
        esperadas = len(v.ClienteApi(url, servidor_prueba.CLAVE).ventas('', 'ana', 4))
        w.buscar_v.setText('ana')   # y se aprieta «Cargar más» antes de que corra la búsqueda
        w.btn_mas.click()
        esperar(lambda: quieto(w), '«Cargar más» con la búsqueda cambiada')
        revisar(w.modelo_v.rowCount() == esperadas, '«Cargar más» con otra búsqueda carga desde el principio')
        w.close()
    finally:
        v.LIMITE_LISTA = limite_original
        srv.shutdown()

    # g) 429: aviso con «Cambiar clave» y sin actualizar solo mientras dura el bloqueo
    srv, url = servidor()
    srv.fallos = [time.monotonic()] * 5   # cinco claves malas desde esta IP
    w = ventana(url)
    revisar(w.banda.isVisibleTo(w) and w.banda.btn_clave.isVisibleTo(w) and '15 minutos' in w.banda.texto.text(),
            '429: aviso con «Cambiar clave»')
    peticiones = len(srv.claves_recibidas)
    w._actualizar_solo()
    esperar(lambda: quieto(w), 'actualización automática durante el bloqueo')
    revisar(len(srv.claves_recibidas) == peticiones, 'durante el bloqueo no se actualiza solo')
    w.close()
    srv.shutdown()

    # h) Cerrar mientras se guarda un cambio pide confirmación
    srv, url = servidor(demora=0.6)
    w = ventana(url)
    w.ir_a('ventas')
    w.tabla_v.selectRow(0)
    esperar(lambda: w.panel.detalle is not None and quieto(w), 'detalle')
    w.captura = False   # (en modo captura no se pregunta nada)
    preguntas = []
    w._confirmar = lambda pregunta, *a, **k: preguntas.append(pregunta) or not pregunta.startswith('Todavía')
    w.panel.btn_bloquear.click()
    cerro = w.close()
    revisar(not cerro and preguntas and preguntas[-1].startswith('Todavía'), 'cerrar con un cambio en camino pide confirmación')
    esperar(lambda: quieto(w), 'que termine el cambio')
    revisar(w.close(), 'sin cambios en camino se cierra sin preguntar')
    srv.shutdown()

    # i) El servidor publicado todavía es el anterior: la app no se rompe y avisa que falta subirlo
    srv, url = servidor(viejo=True)
    w = ventana(url, mostrar=True)
    revisar(w.servidor_nuevo is False and w.modelo_v.rowCount() == 24 and w.modelo_c.rowCount() == 3,
            'servidor anterior: igual se ven las ventas y los canjes')
    revisar(w.banda_servidor.isVisibleTo(w) and 'falta subir' in w.banda_servidor.texto.text(), 'servidor anterior: avisa que falta subirlo')
    revisar(w.bloque_versiones.mensaje.text() == v.FALTA_SERVIDOR and w.t_equipos.titulo.text() == 'EQUIPOS ACTIVADOS'
            and '$608.00' in w.t_total.valor.text(), 'servidor anterior: el resumen sin versiones')
    col = {c: i for i, (c, _t, _a) in enumerate(v.ModeloVentas.COLUMNAS)}
    revisar(all(w.modelo_v.index(n, col['version']).data() == '—' and w.modelo_v.index(n, col['uso']).data() == '—'
                for n in range(w.modelo_v.rowCount())), 'servidor anterior: «Versión» y «Último uso» en «—»')
    w.ir_a('ventas')
    elegir(w, w.tabla_v, lambda f: f['nombre'] == 'Mariana López')
    revisar(w.panel.nota_servidor.isVisible() and not w.panel.btn_editar.isVisible() and not w.panel.visible(w.panel.sec_notas)
            and not w.panel.fila_limite.isVisible() and not w.panel.visible(w.panel.sec_hist) and not w.panel.btn_avisar.isVisible()
            and not filas_equipo(w)[0].version.isVisibleTo(filas_equipo(w)[0]), 'servidor anterior: el panel sin lo nuevo, con su nota')
    apretar(w, w.panel.btn_bloquear, 'bloquear con el servidor anterior')
    revisar(srv.datos.licencia(w.panel.detalle['licencia']['id'])['estado'] == 'bloqueada', 'servidor anterior: las acciones de antes funcionan')
    w.ir_a('versiones')
    esperar(lambda: quieto(w), 'Versiones con el servidor anterior')
    revisar(w.tabla_ver.mensaje_vacio == v.FALTA_SERVIDOR and w.modelo_ver.rowCount() == 0, 'servidor anterior: Versiones lo dice')
    w.mensajes.clear()
    w.anunciar()
    revisar(w.mensajes and w.mensajes[-1][0] == 'Falta el servidor nuevo', 'servidor anterior: «Anunciar» explica que falta subirlo')
    n = len(srv.acciones_recibidas)
    w.actualizar_todo(auto=True)
    esperar(lambda: quieto(w), 'actualización automática con el servidor anterior')
    revisar(srv.acciones_recibidas[n:] == ['resumen', 'ventas', 'canjes', 'detalle'] or srv.acciones_recibidas[n:n + 3] == ['resumen', 'ventas', 'canjes'],
            'servidor anterior: la actualización automática ni prueba «panel»')
    revisar(not v.ERRORES, 'servidor anterior: ningún error inesperado')
    w.close()
    srv.shutdown()

    # j) La cola: UNA petición a la vez, aunque se pidan muchas cosas juntas
    srv, url = servidor(demora=0.12)
    w = ventana(url, mostrar=True)
    w.ir_a('ventas')
    w.tabla_v.selectRow(2)
    w.ir_a('versiones')
    w.ir_a('avisos')
    w.ir_a('resumen')
    w.actualizar_todo()
    w.ir_a('ventas')
    w.buscar_v.setText('mar')
    w.tabla_v.selectRow(0)
    esperar(lambda: quieto(w) and w.panel.detalle is not None, 'muchas cosas a la vez', 40)
    revisar(srv.max_en_curso == 1, f'la cola manda una petición a la vez (máximo en curso: {srv.max_en_curso})')
    numero = {'n': 0}
    hecho = []
    for k in range(6):   # con «clave», una búsqueda nueva reemplaza a la que todavía espera turno
        w.trabajos.iniciar(lambda k=k: (time.sleep(0.05), k)[1], hecho.append, lambda e: numero.update(n=numero['n'] + 1), clave='x')
    esperar(lambda: w.trabajos.activos == 0, 'tareas con clave')
    revisar(hecho[-1] == 5 and len(hecho) + numero['n'] == 6 and len(hecho) < 6, 'una tarea que espera turno la reemplaza la más nueva')
    w.close()
    srv.shutdown()

    # k) «Anunciar versión»: uno por uno, con pausa, tope por hora (espera y sigue) y «Detener»
    srv, url = servidor()
    datos = srv.datos
    w = ventana(url, mostrar=True)
    pausa_original = v.PAUSA_AVISOS_MS
    v.PAUSA_AVISOS_MS = 250
    try:
        d = w.crear_anunciar()
        d.setAttribute(v.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        d.show()
        esperar(lambda: quieto(w) and not d._timer_candidatos.isActive() and d.consulta is not None, 'candidatos')
        revisar(d.version.text() == '5.54' and d.mensaje.toPlainText().startswith('Exporta') and len(d.candidatos) == 5,
                'Anunciar: la versión, el mensaje del manifiesto y 5 candidatos')
        revisar('5 clientes' in d.lbl_cuantos.text() and '3 ya avisados' in d.lbl_fuera.text() and '1 de baja' in d.lbl_fuera.text(),
                'Anunciar: cuántos lo reciben y cuántos quedan fuera')
        d.a_quien.poner('todos')
        esperar(lambda: quieto(w) and d.consulta == ('5.54', 'todos'), 'candidatos a todos')
        revisar(len(d.candidatos) == 18, 'Anunciar a todos: 18')
        d.a_quien.poner('desactualizados')
        esperar(lambda: quieto(w) and d.consulta == ('5.54', 'desactualizados'), 'candidatos otra vez')
        d.mensaje.setPlainText('Lo nuevo: exporta más rápido.')
        preguntas = []
        d._confirmar = lambda pregunta, *a: preguntas.append(pregunta) or True
        datos.tope_hora, datos.ventana_tope = 2, 1.5   # el tope llega con el tercero: espera y sigue solo
        inicio, n = time.monotonic(), len(datos.avisos)
        d.btn_mandar.click()
        revisar(preguntas == ['¿Mandar el aviso a 5 clientes?'], 'pregunta «¿Mandar el aviso a 5 clientes?»')
        vio_pausa = []
        esperar(lambda: (vio_pausa.append(1) if d._timer_espera.isActive() else None) or d.terminado, 'envío de los 5', 60)
        enviados = [a for a in datos.avisos[n:] if a['ok']]
        revisar(len(enviados) == 5 and d.cuenta['enviados'] == 5 and vio_pausa and any(a['motivo'] == 'limite' for a in datos.avisos[n:]),
                'llegó al tope, esperó reintentar_en y siguió hasta mandar los 5')
        revisar(all(a['mensaje'] == 'Lo nuevo: exporta más rápido.' for a in enviados), 'cada aviso con el mensaje editado')
        revisar(time.monotonic() - inicio >= 4 * v.PAUSA_AVISOS_MS / 1000, 'con una pausa entre uno y otro')
        revisar('Listo' in d.lbl_cuantos.text() and 'Enviados: 5' in d.lbl_avance.text() and d.btn_cerrar.text() == 'Cerrar',
                'al final, el resumen del envío')
        d.close()
        # Detener: con el tope largo se queda esperando y «Detener» lo para ya
        for x in datos.avisos[n:]:
            x['ok'] = False   # (como si no se hubieran mandado)
        datos.envios_tope = []
        datos.tope_hora, datos.ventana_tope = 1, 3600
        d = w.crear_anunciar()
        d.setAttribute(v.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        d.show()
        esperar(lambda: quieto(w) and d.consulta is not None, 'candidatos para detener')
        d._confirmar = lambda *a: True
        n = len(datos.avisos)
        d.btn_mandar.click()
        esperar(lambda: d._timer_espera.isActive(), 'que llegue al tope y espere')
        revisar('En pausa' in d.lbl_cuantos.text() and d.btn_detener.isVisible(), 'en pausa por el tope, con «Detener»')
        d.btn_detener.click()
        esperar(lambda: d.terminado, 'detener')
        revisar(d.terminado and not d.enviando and 'Sin mandar: 4' in d.lbl_avance.text() and d.cuenta['enviados'] == 1,
                'Detener: para el envío y dice cuántos quedaron sin mandar')
        revisar(d.lbl_fuera.isVisibleTo(d) and 'anuncia la versión otra vez' in d.lbl_fuera.text(),
                'Detener: dice cómo mandárselo después a los que faltan')
        time.sleep(0.4)
        esperar(lambda: quieto(w), 'quieto')
        revisar(len([a for a in datos.avisos[n:] if a['ok']]) == 1, 'después de Detener no sale nada más')
        d.close()
    finally:
        v.PAUSA_AVISOS_MS = pausa_original
    w.close()
    srv.shutdown()

    # k2) «Anunciar»: lo que llega a destiempo no se pierde ni cambia lo que se manda
    srv, url = servidor(demora=0.3)
    datos = srv.datos
    w = ventana(url, mostrar=True)
    w._cuando.pop('version', None)   # (así el diálogo pregunta la versión publicada)
    d = w.crear_anunciar()
    d.setAttribute(v.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    d.show()
    d.version.setText('5.54')
    d._cargar_candidatos()   # escribió la versión antes de que llegara la publicada
    esperar(lambda: quieto(w) and d.consulta is not None and not d._timer_candidatos.isActive(), 'versión y candidatos')
    revisar('Publicada el' in d.lbl_publicada.texto() and d.mensaje.toPlainText().startswith('Exporta'),
            'Anunciar: la versión publicada llega aunque se escriba la versión antes')
    n = len(datos.avisos)
    d._confirmar = lambda *a: False   # «Cancelar» en «¿Mandar el aviso a N clientes?»
    d.btn_mandar.click()
    esperar(lambda: quieto(w), 'cancelar el anuncio')
    revisar(len(datos.avisos) == n and not d.enviando and d.btn_mandar.isVisibleTo(d) and d.btn_mandar.isEnabled(),
            'Anunciar: si no se confirma, no sale ningún aviso')
    d._confirmar = lambda *a: (d.version.setText('5.53'), True)[1]   # mientras preguntaba, cambió la versión
    d.btn_mandar.click()
    esperar(lambda: quieto(w), 'mandar con la versión cambiada')
    revisar(len(datos.avisos) == n and not d.enviando and d.error.isVisibleTo(d),
            'si la versión cambió mientras confirmaba, no se manda nada y lo dice')
    d.candidatos = [{'licencia_id': 99, 'cliente': None, 'correo': None, 'equipos': 1, 'equipos_desactualizados': 1,
                     'ultima_vez': None}]
    d._poner_candidatos()
    revisar('Licencia #99' in d.lbl_nombres.text(), 'un candidato sin nombre ni correo no rompe el diálogo')
    d.close()
    w.close()
    srv.shutdown()

    # l) --captura (modo solo lectura): guarda las capturas y no cambia nada en el servidor
    srv, url = servidor()
    estado = estado_servidor(srv.datos)
    w = v.VentanaPrincipal(v.Configuracion(), url, captura=True, solo_lectura=True)
    mensajes = []
    w._mensaje = lambda titulo, texto, tipo='error': mensajes.append((titulo, texto))   # (una caja abierta trabaría todo)
    w._confirmar = lambda pregunta, *a, **k: mensajes.append((pregunta, '')) and False
    w.setAttribute(v.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    w.resize(1440, 900)
    w.show()
    carpeta = TEMPORAL / 'capturas'
    capturador = v.Capturador(aplicacion(), w, carpeta)
    w.usar_clave(servidor_prueba.CLAVE)
    capturador.iniciar()
    w.actualizar_todo()
    esperar(lambda: capturador.codigo is not None, 'capturas', 150)
    pngs = sorted(p.name for p in carpeta.glob('*.png'))
    revisar(capturador.codigo == 0 and len(pngs) == len([p for p in capturador.pasos if p[0]]),
            f'--captura: {len(pngs)} capturas sin errores')
    revisar(set(srv.acciones_recibidas) <= SOLO_LEEN, f'--captura solo pidió lo que lee ({sorted(set(srv.acciones_recibidas) - SOLO_LEEN)})')
    revisar(estado_servidor(srv.datos) == estado, '--captura no cambió nada en el servidor')
    revisar(not mensajes, f'--captura no mostró errores ni preguntas {mensajes[:2]}')
    w.close()
    srv.shutdown()


# ------------------------------------------------------------------ 7. Los errores de los clientes (desde CineCaptions 5.71)
def err(datos, ident):
    return next(e for e in datos.errores if e['id'] == ident)


def elegir_error(w, condicion):
    proxy = w.tabla_err.model()
    for n in range(proxy.rowCount()):
        fila = w._fila_de(w.tabla_err, proxy.index(n, 0))
        if condicion(fila):
            w.tabla_err.selectRow(n)
            esperar(lambda: quieto(w) and (w.panel_error.detalle or {}).get('id') == fila['id'], 'informe del error')
            return fila
    revisar(False, 'no se encontró el error buscado')
    return None


def prueba_errores_clientes():
    print('Errores de los clientes: acciones, página Errores y aviso')
    # Funciones sueltas: lo que manda un servidor de antes (sin «errores» o con null) no rompe nada
    revisar(v.normalizar_resumen_errores(None) is None and v.normalizar_resumen_errores([]) is None,
            'resumen de errores ausente o null (servidor de antes o sin la tabla): None')
    revisar(v.normalizar_resumen_errores({'sin_ver': '2', 'equipos': '1', 'ultimo_id': '9', 'ultima': '2026-11-05 10:00:00'})
            == {'sin_ver': 2, 'equipos': 1, 'ultimo_id': 9, 'ultima': '2026-11-05 10:00:00'}
            and v.normalizar_resumen_errores({'sin_ver': 0, 'equipos': 0, 'ultimo_id': None, 'ultima': None})['ultimo_id'] is None,
            'resumen de errores: números como texto y sin errores sin ver')
    e = v.normalizar_error({'id': '3', 'licencia_id': '7', 'veces': '2', 'visto': '0', 'nivel': 'raro', 'titulo': 'X'})
    revisar(e['id'] == 3 and e['veces'] == 2 and e['visto'] is False and e['nivel'] == 'error' and e['detalle'] is None,
            'un error: los números, «visto» y un nivel que no se conoce')
    informe = v.texto_informe({'id': 4, 'nivel': 'aviso', 'titulo': 'Tardó', 'mensaje': 'Tardó 2 min.', 'cliente': 'Ana',
                               'clave': 'CC-AAAA-BBBB-CCCC-DDDD', 'veces': 3, 'detalle': 'Línea 1\nLínea 2'})
    revisar(informe.startswith('Aviso de CineCaptions #4: Tardó\nTardó 2 min.') and 'Licencia: CC-AAAA-BBBB-CCCC-DDDD' in informe
            and 'Veces: 3 veces' in informe and informe.endswith('\n\nLínea 1\nLínea 2'), 'el informe para copiar')

    # Las acciones de la API
    srv, url = servidor()
    datos = srv.datos
    c = v.ClienteApi(url, servidor_prueba.CLAVE)
    resumen = c.panel()['errores']
    revisar(resumen['sin_ver'] == 3 and resumen['equipos'] == 2 and resumen['ultimo_id'] == 5 and resumen['ultima'],
            'panel: el resumen de errores (3 sin ver, de 2 equipos; el más nuevo es el 5)')
    r = c.errores()
    filas = r['errores']
    revisar(len(filas) == 5 and r['resumen'] == resumen, 'errores: todos, con el mismo resumen que panel')
    vistos = [f['visto'] for f in filas]
    revisar(vistos == sorted(vistos) and all(a['ultima'] >= b['ultima'] for a, b in zip(filas, filas[1:]) if a['visto'] == b['visto']),
            'errores: los sin ver primero y después los más nuevos, como admin.php')
    f = next(x for x in filas if x['titulo'].startswith('No se pudieron colocar'))
    revisar(f['cliente'] == 'Mariana López' and f['clave'] == 'CC-7K2M-Q9XA-4HBR-T3WZ' and f['veces'] == 3 and f['visto'] is False
            and f['nombre_equipo'].startswith('ESTUDIO-MARIANA') and f['so'] == 'Windows 11' and f['version'] == '5.54'
            and f['nivel'] == 'error' and f['detalle'] is None, 'cada error con su cliente, clave, equipo, versión y veces (sin el detalle)')
    revisar(len(c.errores('sin_ver')['errores']) == 3 and len(c.errores(licencia_id=f['licencia_id'])['errores']) == 2,
            'errores: «sin ver» y los de una licencia')
    revisar(len(c.errores(buscar='transcripcion')['errores']) == 1 and len(c.errores(buscar='fernando')['errores']) == 2
            and len(c.errores(buscar='estudio-mariana')['errores']) == 2, 'errores: la búsqueda (sin tildes, por cliente y por equipo)')
    revisar(len(c.errores(limite=2)['errores']) == 2, 'errores: con límite')
    d = c.error_detalle(f['id'])
    revisar(d['detalle'].count('\n') >= 5 and 'Traceback' in d['detalle'] and 'Última acción: «Colocar en Resolve»' in d['detalle']
            and d['clave'] == f['clave'] and d['firma'] and d['veces'] == 3, 'error_detalle: el informe de varias líneas (con tildes) y la licencia')
    e = error_de(lambda: c.error_detalle(999))
    revisar(e is not None and e.codigo == 404 and e.mensaje == 'Ese error ya no existe.', 'error_detalle de uno que no existe: 404')
    m = c.error_visto([f['id']])
    revisar(m['cambiados'] == 1 and m['resumen']['sin_ver'] == 2 and err(datos, f['id'])['visto'] == 1, 'error_visto: uno como visto')
    revisar(c.error_visto([f['id']])['cambiados'] == 0, 'error_visto otra vez: no cambia nada (como MySQL)')
    m = c.error_visto([f['id']], visto=False)
    revisar(m['cambiados'] == 1 and m['resumen']['sin_ver'] == 3 and err(datos, f['id'])['visto'] == 0,
            'error_visto con visto=false: vuelve a ser nuevo')
    e = error_de(lambda: c.error_visto([]))
    revisar(e is not None and e.codigo == 400 and e.mensaje == 'Faltan los errores que marcar.', 'error_visto sin ids: 400')

    # errores.php: el mismo error en el mismo equipo suma «veces» y vuelve a «sin ver» con el mismo id; uno nuevo, id nuevo
    import urllib.error
    import urllib.parse
    import urllib.request

    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def errores_php(campos):
        pedido = urllib.request.Request(url.replace('admin.php', 'errores.php'), data=urllib.parse.urlencode(campos).encode(),
                                        headers={'User-Agent': 'CineCaptions/5.71'})
        try:
            with abridor.open(pedido, timeout=10) as respuesta:
                return respuesta.status, json.loads(respuesta.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    visto = next(x for x in datos.errores if x['visto'])
    lic = datos.licencia_real(visto['licencia_id'])
    lote = [{'firma': visto['firma'], 'nivel': 'error', 'titulo': visto['titulo'], 'mensaje': visto['mensaje'], 'veces': 2},
            {'nivel': 'aviso', 'titulo': 'Se reinició la vista previa', 'mensaje': 'La vista previa se cerró y se volvió a abrir.',
             'origen': 'vista_previa', 'detalle': 'Línea uno\r\nLínea dos con tilde: está'}]
    codigo, respuesta = errores_php({'clave': lic['clave'], 'equipo': visto['equipo'], 'so': 'macOS 15.1',
                                     'errores': json.dumps(lote)})
    revisar(codigo == 200 and respuesta == {'ok': True, 'guardados': 2, 'capturas': 0},
            'errores.php: guarda los errores de un equipo activado')
    revisar(visto['visto'] == 0 and visto['veces'] == 9 and visto['id'] == 1 and datos.errores[-1]['id'] == 6
            and datos.errores[-1]['detalle'] == 'Línea uno\nLínea dos con tilde: está' and datos.errores[-1]['version'] == '5.71',
            'el mismo error vuelve a «sin ver» con su id (y suma las veces); el nuevo entra con el id 6')
    codigo, _r = errores_php({'clave': lic['clave'], 'equipo': 'equipo-que-no-existe', 'errores': json.dumps(lote)})
    revisar(codigo == 404, 'errores.php: un equipo que no está activado no puede mandar errores')

    # CineCaptions 5.72: multipart con la captura («captura_<firma>») y equipo_datos; error_captura la da en base64
    png = servidor_prueba._png_demo(64, 36)
    limite = 'prueba123'
    partes = []
    for k, val in {'clave': lic['clave'], 'equipo': visto['equipo'], 'equipo_datos': 'GPU X · RAM 8 GB',
                   'errores': json.dumps([dict(lote[0], captura='pantalla')])}.items():
        partes += [f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n'.encode(), val.encode(), b'\r\n']
    partes += [f'--{limite}\r\nContent-Disposition: form-data; name="captura_{visto["firma"]}"; filename="c.png"\r\n'
               'Content-Type: image/png\r\n\r\n'.encode(), png, b'\r\n', f'--{limite}--\r\n'.encode()]
    pedido = urllib.request.Request(url.replace('admin.php', 'errores.php'), data=b''.join(partes),
                                    headers={'User-Agent': 'CineCaptions/5.72',
                                             'Content-Type': f'multipart/form-data; boundary={limite}'})
    with abridor.open(pedido, timeout=10) as respuesta:
        codigo, respuesta = respuesta.status, json.loads(respuesta.read())
    revisar(codigo == 200 and respuesta.get('capturas') == 1, f'errores.php: guarda la captura ({respuesta})')
    d = c.error_detalle(visto['id'])
    revisar(d['equipo_datos'] == 'GPU X · RAM 8 GB' and d['captura'] and d['captura']['de'] == 'pantalla' and d['con_captura'],
            'error_detalle: equipo_datos y los datos de la captura')
    cap = c.error_captura(visto['id'])
    revisar(cap['ancho'] == 64 and cap['alto'] == 36 and not cap['imagen'].isNull(), 'error_captura: la imagen llega entera')
    e = error_de(lambda: c.error_captura(2))
    revisar(e is not None and e.codigo == 404, 'error_captura de un error sin captura: 404')
    m = c.error_visto(todos=True)
    revisar(m['cambiados'] == 5 and m['resumen'] == {'sin_ver': 0, 'equipos': 0, 'ultimo_id': None, 'ultima': None}
            and all(x['visto'] for x in datos.errores), 'error_visto con todos=true: todo visto (sin último id)')
    lectura = v.ClienteApi(url, servidor_prueba.CLAVE, solo_lectura=True)
    antes = len(srv.acciones_recibidas)
    e = error_de(lambda: lectura.error_visto([1], visto=False))
    revisar(e is not None and len(srv.acciones_recibidas) == antes and err(datos, 1)['visto'] == 1,
            'solo lectura (--captura): error_visto ni sale')
    revisar(len(lectura.errores()['errores']) == 6 and lectura.error_detalle(1)['id'] == 1, 'solo lectura: errores y error_detalle sí')
    srv.shutdown()

    # Un admin.php de antes: sin «errores» en panel y las acciones nuevas dan «Acción desconocida»
    srv, url = servidor(sin_errores=True)
    c = v.ClienteApi(url, servidor_prueba.CLAVE)
    p = c.panel()
    e = error_de(c.errores)
    revisar(p['errores'] is None and len(p['ventas']) == 24 and e is not None and e.desconocida,
            'admin.php sin los errores: panel sin el resumen (None) y errores da «Acción desconocida»')
    srv.shutdown()
    srv, url = servidor(viejo=True)
    e = error_de(v.ClienteApi(url, servidor_prueba.CLAVE).errores)
    revisar(e is not None and e.desconocida, 'servidor anterior (--viejo): errores da «Acción desconocida»')
    srv.shutdown()

    # La página Errores
    aplicacion()
    srv, url = servidor()
    datos = srv.datos
    w = ventana(url, mostrar=True)
    boton_nav = w.barra.botones['errores']
    revisar(boton_nav.contador == 3 and boton_nav.color_contador == v.PELIGRO and w.errores_resumen['ultimo_id'] == 5,
            'isla del menú: «Errores» con 3 sin ver, en rojo')
    w.ir_a('errores')
    esperar(lambda: quieto(w) and w.modelo_err.rowCount() == 5, 'página Errores')
    revisar(w.lbl_titulo.text() == 'Errores' and w.proxy_err.rowCount() == 3 and w.filtro_err.valor == 'sin_ver'
            and w.filtro_err.botones['sin_ver'].text().endswith('3') and w.filtro_err.botones['todos'].text().endswith('5'),
            'Errores: se abre en «Sin ver» (3 de 5)')
    revisar(w.panel_error.isVisible() and not w.panel.isVisible() and w.panel_error.vacio.isVisible(),
            'a la derecha, el panel del error (todavía sin elegir)')
    revisar('3 errores sin ver' in w.lbl_pie_err.texto() and w.btn_todo_visto.isEnabled(),
            'el pie dice cuántos sin ver y «Marcar todo como visto» está activo')

    # Vista «Por usuario» (la de siempre al abrir): los clientes con errores y, al elegir uno, sus errores por equipo
    revisar(w.vista_errores.valor == 'usuario' and w.pila_err.currentIndex() == 0 and w._tabla_actual() is w.tabla_cli,
            'Errores se abre en «Por usuario»')
    revisar(w.modelo_cli.rowCount() == 3 and w.proxy_cli.rowCount() == 2 and '2 de 3 clientes' in w.lbl_pie_err.texto(),
            'por usuario: 3 clientes con errores; en «Sin ver», los 2 que tienen errores sin ver')
    primero = w._fila_de(w.tabla_cli, w.proxy_cli.index(0, 0))
    cc = {c: i for i, (c, _t, _a) in enumerate(v.ModeloClientesErrores.COLUMNAS)}
    revisar(primero['cliente'] == 'Mariana López' and primero['sin_ver'] == 2 and primero['equipos'] == 1 and primero['veces'] == 4
            and primero['ultimo_titulo'].startswith('No se pudieron colocar')
            and w.proxy_cli.index(0, cc['sin_ver']).data(v.ROL_INSIGNIA)[:2] == ('2', v.PELIGRO)
            and w.proxy_cli.index(0, cc['cliente']).data(v.ROL_SEGUNDA) == '1 equipo · 4 veces'
            and w.proxy_cli.index(0, cc['ultimo']).data().startswith('hace'),
            'arriba, el cliente con el error sin ver más reciente: sus equipos, cuántos sin ver, las veces y el último')
    w.filtro_err.poner('todos')
    revisar(w.proxy_cli.rowCount() == 3 and w._fila_de(w.tabla_cli, w.proxy_cli.index(2, 0))['cliente'] == 'Fernando Batres',
            '«Todos»: también el cliente con todo visto, abajo')
    w.filtro_err.poner('sin_ver')
    ec = w.errores_cliente
    lid_m = primero['licencia_id']
    revisar(list(ec.bloques)[:1] == [lid_m] and len(ec.bloques) == 2 and ec.scroll.isVisibleTo(ec) and not w.tabla_cli.isVisible(),
            '2.3: «Por cliente» en una columna: cada cliente con errores sin ver (el más reciente arriba) y sus errores debajo')
    w.tabla_cli.selectRow(0)
    esperar(lambda: quieto(w) and w.panel_error.detalle is not None, 'cliente elegido')
    de_mariana = sorted((x for x in datos.errores if x['licencia_id'] == lid_m), key=lambda x: x['ultima'], reverse=True)
    bm = ec.bloques[lid_m]
    revisar(ec.licencia_id == lid_m and list(bm.filas) == [x['id'] for x in de_mariana] and bm.btn_todo.isEnabled()
            and bm.nombre.texto() == 'Mariana López' and 'ESTUDIO-MARIANA' in bm.sub.texto() and bm.iniciales.text() == 'ML'
            and bm.pastilla.text() == '2 sin ver',
            'el cliente: iniciales, nombre, su equipo, «2 sin ver», «Marcar visto» y sus errores, del más reciente al más viejo')
    revisar(w.panel_error.detalle['id'] == de_mariana[0]['id'] and ec.filas[de_mariana[0]['id']].elegido,
            'y en el panel, el informe de su error más reciente')
    ec.filas[de_mariana[1]['id']].click()
    esperar(lambda: quieto(w) and w.panel_error.detalle['id'] == de_mariana[1]['id'], 'otro error del cliente')
    revisar(ec.filas[de_mariana[1]['id']].elegido and not ec.filas[de_mariana[0]['id']].elegido
            and w.panel_error.tipo.text() == f"AVISO #{de_mariana[1]['id']}", 'al elegir otro de sus errores, su informe')
    otro = next(lid for lid in ec.bloques if lid != lid_m)
    ec.filas[next(iter(ec.bloques[otro].filas))].click()
    esperar(lambda: quieto(w) and w.panel_error.detalle['licencia_id'] == otro, 'error de otro cliente')
    revisar(w.cliente_err == otro and w._fila_actual(w.tabla_cli)['licencia_id'] == otro,
            'un error de otro cliente en la columna: su cliente queda elegido (también en la lista de detrás)')
    ec.filas[de_mariana[1]['id']].click()
    esperar(lambda: quieto(w) and w.panel_error.detalle['id'] == de_mariana[1]['id'], 'de vuelta a Mariana')
    revisar(not ec.grab().isNull(), 'la vista por cliente se dibuja')
    # La agrupación por equipo: el equipo con el error más reciente primero, con su versión y su sistema
    prueba = v.ErroresCliente()
    base = {'licencia_id': 9, 'clave': 'CC-AAAA-BBBB-CCCC-DDDD', 'cliente': 'Ana', 'correo': 'ana@example.com', 'nivel': 'error',
            'mensaje': 'x', 'origen': None, 'veces': '1', 'visto': '0', 'primera': '2026-11-01 10:00:00'}
    sueltos = [v.normalizar_error(dict(base, id=n, equipo=eq, nombre_equipo=f'{nombre} · {eq}', version=ver, so=so, titulo=f'Error {n}',
                                       ultima=f'2026-11-0{dia} 10:00:00'))
               for n, eq, nombre, ver, so, dia in ((1, 'h1', 'PC-ESTUDIO', '5.71', 'Windows 11', 4), (2, 'h2', 'MacBook-de-Ana', '5.70', 'macOS 15.1', 5),
                                                   (3, 'h1', 'PC-ESTUDIO', '5.71', 'Windows 11', 3))]
    prueba.poner(sorted(sueltos, key=lambda x: x['ultima'], reverse=True), 2)
    cabezas = [prueba.lista.itemAt(i).widget().text() for i in range(prueba.lista.count())
               if isinstance(prueba.lista.itemAt(i).widget(), v.QLabel)]
    revisar(len(cabezas) == 2 and 'MacBook-de-Ana' in cabezas[0] and 'CineCaptions 5.70 · macOS 15.1 · 1 error' in cabezas[0]
            and 'PC-ESTUDIO' in cabezas[1] and '2 errores' in cabezas[1] and list(prueba.filas) == [2, 1, 3] and prueba.filas[2].elegido,
            'los errores de un cliente, agrupados por equipo (nombre, versión y sistema), el más reciente primero')
    prueba.deleteLater()
    antes = len(w.preguntas)
    apretar(w, ec.bloques[lid_m].btn_todo, 'marcar todo lo de este cliente como visto')
    ids_mariana = [x['id'] for x in de_mariana]
    revisar(w.preguntas[antes:] == ['¿Marcar los 2 errores sin ver de Mariana López como vistos?']
            and all(err(datos, i)['visto'] for i in ids_mariana) and w.barra.botones['errores'].contador == 1
            and not ec.bloques[lid_m].btn_todo.isEnabled() and w.aviso.texto.text() == '2 errores marcados como vistos.',
            '«Marcar todo lo de este cliente como visto»: con su pregunta, en el servidor y en el contador (1)')
    revisar(w.proxy_cli.rowCount() == 2 and w._fila_actual(w.tabla_cli)['licencia_id'] == primero['licencia_id']
            and w._fila_actual(w.tabla_cli)['sin_ver'] == 0, 'el cliente que se está viendo no se va de «Sin ver»')
    v.ClienteApi(url, servidor_prueba.CLAVE).error_visto(ids_mariana, visto=False)   # (como estaban, para lo que sigue)
    w.actualizar_todo()
    esperar(lambda: quieto(w) and w.barra.botones['errores'].contador == 3, 'actualizar')
    revisar(w._fila_actual(w.tabla_cli)['sin_ver'] == 2 and ec.bloques[lid_m].btn_todo.isEnabled(),
            'al actualizar, el cliente con sus errores sin ver otra vez')
    elegido = w.error_elegido
    w.vista_errores.poner('lista')
    revisar(w.pila_err.currentIndex() == 1 and w._tabla_actual() is w.tabla_err and w._fila_actual(w.tabla_err)['id'] == elegido
            and w.error_elegido == elegido and '3 de 5 errores' in w.lbl_pie_err.texto(),
            '«Todos los errores»: la tabla, con el mismo error elegido')
    col = {c: i for i, (c, _t, _a) in enumerate(v.ModeloErrores.COLUMNAS)}
    resolve = next(x for x in w.modelo_err.filas if x['titulo'].startswith('No se pudieron colocar'))
    n = w.modelo_err.buscar('id', resolve['id'])[0]
    revisar(w.modelo_err.index(n, col['cuando']).data(v.ROL_INSIGNIA)[1:3] == (v.PELIGRO, 'punto')
            and w.modelo_err.index(n, col['cuando']).data().startswith('hace')
            and w.modelo_err.index(n, col['error']).data(v.ROL_SEGUNDA).startswith('Resolve no respondió')
            and w.modelo_err.index(n, col['veces']).data() == '3'
            and w.modelo_err.index(n, col['equipo']).data() == 'ESTUDIO-MARIANA'
            and w.modelo_err.index(n, col['equipo']).data(v.ROL_SEGUNDA) == 'Windows 11',
            'cada fila: el punto rojo de sin ver, cuándo, el error en dos líneas, el equipo y las veces')
    aviso = next(x for x in w.modelo_err.filas if x['nivel'] == 'aviso' and not x['visto'])
    revisar(w.modelo_err.index(w.modelo_err.buscar('id', aviso['id'])[0], col['cuando']).data(v.ROL_INSIGNIA)[1] == v.AVISO,
            'un aviso sin ver lleva el punto naranja')
    revisar(not w.tabla_err.viewport().grab().isNull(), 'la tabla de errores se dibuja')
    fila = elegir_error(w, lambda x: x['id'] == resolve['id'])
    pe = w.panel_error
    revisar(pe.tipo.text() == f"ERROR #{fila['id']}" and pe.estado.text() == 'Sin ver' and pe.btn_visto.text().strip() == 'Marcar visto'
            and 'DaVinci Resolve' in pe.titulo.text(), 'el panel: número, «Sin ver», el título y «Marcar como visto»')
    revisar('Traceback' in pe.informe.toPlainText() and 'Reseña cámara' in pe.informe.toPlainText() and pe.informe.isReadOnly()
            and pe.informe.font().family() in v.MONO, 'el informe técnico entero, en letra monoespaciada y de solo lectura')
    apretar(w, pe.btn_copiar, 'copiar informe')
    copiado = v.QGuiApplication.clipboard().text()
    revisar('CC-7K2M-Q9XA-4HBR-T3WZ' in copiado and 'Mariana López' in copiado and 'Traceback' in copiado
            and w.aviso.texto.text() == 'Informe copiado', 'Copiar informe: el cliente, la clave y el detalle técnico')
    apretar(w, pe.btn_visto, 'marcar como visto')
    revisar(err(datos, fila['id'])['visto'] == 1 and boton_nav.contador == 2 and w.aviso.texto.text() == 'Marcado como visto.',
            'marcar como visto: el servidor y el contador (2)')
    revisar(w.proxy_err.rowCount() == 3 and pe.btn_visto.text().strip() == 'Marcar nuevo' and pe.estado.text() == 'Visto',
            'el que se está viendo no desaparece de «Sin ver» (se puede deshacer)')
    revisar('2 errores sin ver' in w.lbl_pie_err.texto() and w.filtro_err.botones['sin_ver'].text().endswith('2'),
            'el pie y el filtro cuentan 2 sin ver')
    apretar(w, pe.btn_visto, 'marcar como nuevo')
    revisar(err(datos, fila['id'])['visto'] == 0 and boton_nav.contador == 3 and pe.btn_visto.text().strip() == 'Marcar visto',
            'marcar como nuevo: otra vez sin ver')
    peticiones = len(srv.acciones_recibidas)
    w.buscar_err.setText('montserrat')
    esperar(lambda: quieto(w), 'búsqueda en errores')
    revisar(w.proxy_err.rowCount() == 1 and len(srv.acciones_recibidas) == peticiones, 'búsqueda en errores (sin pedir nada al servidor)')
    w.buscar_err.setText('xyz-no-existe')
    esperar(lambda: quieto(w), 'búsqueda sin resultados')
    revisar(w.proxy_err.rowCount() == 0 and 'xyz-no-existe' in w.tabla_err.mensaje_vacio, 'búsqueda sin resultados: lo dice')
    w.buscar_err.clear()
    esperar(lambda: quieto(w), 'quieto')
    fila = elegir_error(w, lambda x: x['id'] == resolve['id'])

    # «Abrir licencia»: la venta de ese cliente; si no está en la tabla, el equipo del error en Versiones
    w.mensajes.clear()
    apretar(w, pe.btn_licencia, 'abrir licencia')
    esperar(lambda: quieto(w) and w.panel.detalle is not None, 'licencia del error')
    revisar(w.pagina == 'ventas' and w.panel.isVisible() and w.panel.clave.text() == 'CC-7K2M-Q9XA-4HBR-T3WZ'
            and w._fila_actual(w.tabla_v)['licencia_id'] == fila['licencia_id'],
            '«Abrir licencia» lleva a la venta de ese cliente, con su licencia en el panel')
    ventas_cargadas = list(w.modelo_v.filas)
    w.modelo_v.cargar([])   # (como si una búsqueda la escondiera)
    w._abrir_licencia(fila)
    esperar(lambda: quieto(w) and w.panel.detalle is not None and w.pagina == 'versiones', 'licencia en Versiones')
    actual = w._fila_actual(w.tabla_ver)
    revisar(actual is not None and actual['licencia_id'] == fila['licencia_id']
            and any(e['equipo'] == fila['equipo'] for e in actual['filas'])
            and w.panel.clave.text() == 'CC-7K2M-Q9XA-4HBR-T3WZ', 'si la venta no está en la tabla: el cliente del error en Versiones')
    w.modelo_v.cargar(ventas_cargadas)

    # «Marcar todo como visto», con confirmación
    w.ir_a('errores')
    esperar(lambda: quieto(w), 'Errores otra vez')
    antes = len(w.preguntas)
    apretar(w, w.btn_todo_visto, 'marcar todo como visto')
    revisar(w.preguntas[antes:] == ['¿Marcar los 3 errores sin ver como vistos?'], 'marcar todo como visto pide confirmación')
    revisar(all(x['visto'] for x in datos.errores) and boton_nav.contador is None and w.proxy_err.rowCount() == 0
            and w.tabla_err.mensaje_vacio.startswith('Todo visto') and w.panel_error.vacio.isVisible()
            and not w.btn_todo_visto.isEnabled(), 'todo visto: sin contador, la tabla dice «Todo visto» y el panel queda vacío')
    revisar(w.proxy_cli.rowCount() == 0 and w.tabla_cli.mensaje_vacio.startswith('Todo visto') and w.cliente_err is None
            and w.errores_cliente.licencia_id is None, 'todo visto: «Por usuario» tampoco deja ningún cliente en «Sin ver»')
    w.filtro_err.poner('todos')
    revisar(w.proxy_err.rowCount() == 5, '«Todos»: también los ya vistos')
    datos.errores = [x for x in datos.errores if x['id'] != 1]   # (se borró en el servidor: limpiar_errores)
    elegido = None
    for k in range(w.proxy_err.rowCount()):
        if w._fila_de(w.tabla_err, w.proxy_err.index(k, 0))['id'] == 1:
            w.tabla_err.selectRow(k)
            elegido = 1
    esperar(lambda: quieto(w) and w.panel_error.caja_error.isVisibleTo(w.panel_error), 'error que ya no existe')
    revisar(elegido == 1 and 'ya no existe' in w.panel_error.error_texto.text(), 'un error que ya se borró: el panel lo dice (404)')
    w.close()
    srv.shutdown()

    # El aviso de un error nuevo: notificación de Windows y el aviso de adentro, una sola vez por error
    srv, url = servidor()
    datos = srv.datos
    config = v.Configuracion()   # (la del APPDATA temporal de la prueba)
    config.datos.pop('errores_avisados', None)
    notificaciones = []

    def ventana_real(config):
        """Como la app de verdad (no en modo captura, que nunca avisa), sin la actualización automática."""
        w = v.VentanaPrincipal(config, url)
        w._auto.stop()
        w.mensajes, w.preguntas = [], []
        w._mensaje = lambda titulo, texto, tipo='error': w.mensajes.append((titulo, texto))
        w._confirmar = lambda pregunta, *a, **k: w.preguntas.append(pregunta) or True
        w._mostrar_notificacion = lambda titulo, texto: notificaciones.append((titulo, texto)) or True
        w.setAttribute(v.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        w.resize(1440, 900)
        w.show()
        w.usar_clave(servidor_prueba.CLAVE)
        return w

    def actualizar(w):
        w.actualizar_todo()
        esperar(lambda: w.intento_listo and quieto(w), 'actualizar')

    w = ventana_real(config)
    actualizar(w)
    ultima_sin_ver = max(x['ultima'] for x in datos.errores if not x['visto'])
    revisar(not notificaciones and v.Configuracion().datos.get('errores_avisados') == {url: {'id': 5, 'ultima': ultima_sin_ver}},
            'la primera vez no avisa de los errores que ya había: solo guarda el último (5) y su última vez en config.json')
    actualizar(w)
    revisar(not notificaciones, 'con el mismo último error no avisa otra vez')
    carlos = next(x for x in datos.errores if x['titulo'].startswith('Falta la fuente'))
    nuevo = datos.recibir_error(carlos['licencia_id'], carlos['equipo'], 'f' * 40, 'error', 'CineCaptions se cerró al exportar',
                                'Falló al guardar el archivo .srt.', 'exportar.srt')
    actualizar(w)
    revisar(len(notificaciones) == 1 and notificaciones[0] == ('Error de un cliente', '4 errores nuevos de 2 equipos. Haz clic para verlos.')
            and v.Configuracion().datos['errores_avisados'][url]['id'] == nuevo == 6,
            'un error nuevo: la notificación de Windows («Error de un cliente», cuántos y de cuántos equipos) y se guarda el 6')
    revisar(w.aviso.texto.text().startswith('4 errores nuevos de 2 equipos') and w.barra.botones['errores'].contador == 4,
            'y también el aviso de adentro y el contador (4)')
    actualizar(w)
    revisar(len(notificaciones) == 1, 'no avisa dos veces del mismo error')
    time.sleep(1.1)   # (la última vez cambia de segundo)
    fernando = next(x for x in datos.errores if x['visto'] and x['nivel'] == 'error')
    datos.recibir_error(fernando['licencia_id'], fernando['equipo'], fernando['firma'], 'error', fernando['titulo'], fernando['mensaje'])
    actualizar(w)
    revisar(len(notificaciones) == 2 and notificaciones[-1][1].startswith('5 errores nuevos de 3 equipos') and fernando['id'] == 1,
            'un error ya visto que vuelve a pasar (conserva su id) también avisa')
    w.ir_a('errores')
    esperar(lambda: quieto(w) and w.modelo_err.rowCount() == 6, 'Errores en la ventana de verdad')
    w._marcar_errores([2], visto=False)   # marcar uno como nuevo desde la app no es un error nuevo
    esperar(lambda: quieto(w), 'marcar como nuevo')
    actualizar(w)
    revisar(len(notificaciones) == 2 and w.barra.botones['errores'].contador == 6, 'marcar uno como nuevo desde la app no avisa')
    w.ir_a('resumen')
    w._abrir_errores()
    revisar(w.pagina == 'errores' and w.lado.currentWidget() is w.panel_error, 'al hacer clic en la notificación se abre la página Errores')
    w.close()
    w2 = ventana_real(v.Configuracion())   # se reinicia la app
    actualizar(w2)
    revisar(len(notificaciones) == 2, 'al reiniciar la app no avisa otra vez de lo que ya avisó')
    salio = v.VentanaPrincipal._mostrar_notificacion(w2, 'Prueba', 'Sin bandeja')
    revisar(salio is v.QSystemTrayIcon.isSystemTrayAvailable() and not v.ERRORES,
            f'la notificación de verdad sin bandeja de sistema no rompe nada (salió: {salio})')
    w2.close()
    # Con la app cerrada, un error ya visto vuelve a pasar: conserva su id (no sube), pero su «ultima» es nueva
    for x in datos.errores:
        x['visto'] = 1
    w3 = ventana_real(v.Configuracion())
    actualizar(w3)
    w3.close()
    revisar(len(notificaciones) == 2, 'sin errores sin ver, al abrir no avisa nada')
    time.sleep(1.1)
    datos.recibir_error(fernando['licencia_id'], fernando['equipo'], fernando['firma'], 'error', fernando['titulo'],
                        fernando['mensaje'])
    guardado = v.Configuracion().datos['errores_avisados'][url]
    w4 = ventana_real(v.Configuracion())   # se abre la app
    actualizar(w4)
    nuevo_guardado = v.Configuracion().datos['errores_avisados'][url]
    revisar(len(notificaciones) == 3 and notificaciones[-1][1].startswith('1 error nuevo de 1 equipo')
            and fernando['id'] == 1 and nuevo_guardado['id'] == guardado['id'] == 6
            and nuevo_guardado['ultima'] == fernando['ultima'] > guardado['ultima'],
            'un error ya visto que vuelve a pasar con la app cerrada avisa al abrirla (por «ultima», aunque el id no suba)')
    w4.close()
    w5 = ventana_real(v.Configuracion())
    actualizar(w5)
    revisar(len(notificaciones) == 3, 'y al volver a abrirla no avisa otra vez del mismo')
    w5.close()
    # Lo que guardaba la 2.2.0 (solo el id) se sigue entendiendo: no avisa de más y pasa a guardar también «ultima»
    config = v.Configuracion()
    config.datos['errores_avisados'] = {url: 6}
    config.guardar()
    w6 = ventana_real(v.Configuracion())
    actualizar(w6)
    revisar(len(notificaciones) == 3 and v.Configuracion().datos['errores_avisados'][url] == {'id': 6, 'ultima': fernando['ultima']},
            'con lo que guardaba la 2.2.0 (solo el id) no avisa de más y pasa a guardar el id y la última vez')
    w6.close()
    srv.shutdown()

    # Sin los errores en el servidor, con el anterior y sin ningún error
    for opciones, esperado, descripcion in (({'sin_errores': True}, v.FALTA_SERVIDOR_ERRORES, 'admin.php sin los errores'),
                                            ({'viejo': True}, v.FALTA_SERVIDOR, 'servidor anterior'),
                                            ({'pocos': True}, 'Ningún cliente ha tenido errores.', 'sin errores')):
        srv, url = servidor(**opciones)
        w = ventana(url, mostrar=True)
        w.ir_a('errores')
        esperar(lambda: quieto(w), f'Errores: {descripcion}')
        revisar(w.tabla_err.mensaje_vacio == w.tabla_cli.mensaje_vacio == esperado and w.modelo_err.rowCount() == 0
                and w.modelo_cli.rowCount() == 0 and w.barra.botones['errores'].contador is None
                and not w.btn_todo_visto.isEnabled() and not w.tabla_err.viewport().grab().isNull() and not v.ERRORES,
                f'{descripcion}: la página Errores lo dice («{esperado[:40]}…») y la app sigue igual')
        w.close()
        srv.shutdown()


# ------------------------------------------------------------------ 8. La instalación y lo visual
def prueba_recurso():
    """recurso() encuentra fuentes\\Inter.ttf compilada con PyInstaller de un solo archivo (sys._MEIPASS = la carpeta
    temporal donde se descomprime) e instalada («onedir»: sys._MEIPASS = la carpeta _internal junto al .exe), y
    carpeta_programa() es la del .exe. Se imita lo que pone PyInstaller en sys (sin armar ningún .exe)."""
    print('Archivos incluidos: un solo archivo e instalada')
    guardado = {nombre: getattr(sys, nombre) for nombre in ('frozen', '_MEIPASS') if hasattr(sys, nombre)}
    ejecutable = sys.executable

    def armar(*partes):
        carpeta = TEMPORAL.joinpath(*partes)
        (carpeta / 'fuentes').mkdir(parents=True, exist_ok=True)
        (carpeta / 'fuentes' / 'Inter.ttf').write_bytes(b'(prueba)')
        return carpeta

    def compilada(exe, meipass):
        sys.frozen, sys._MEIPASS, sys.executable = True, str(meipass), str(exe)

    try:
        instalada = TEMPORAL / 'Programs' / 'CineCaptions Ventas'
        interna = armar('Programs', 'CineCaptions Ventas', '_internal')
        compilada(instalada / 'CineCaptions Ventas.exe', interna)
        revisar(v.recurso('fuentes/Inter.ttf') == interna / 'fuentes' / 'Inter.ttf' and v.recurso('fuentes').is_dir(),
                'instalada («onedir»): la fuente está en _internal (sys._MEIPASS)')
        revisar(v.carpeta_programa() == instalada.resolve(), 'instalada: carpeta_programa() es la del .exe')
        temporal = armar('_MEI48213')
        compilada(TEMPORAL / 'dist' / 'CineCaptions Ventas.exe', temporal)
        revisar(v.recurso('fuentes/Inter.ttf') == temporal / 'fuentes' / 'Inter.ttf',
                'un solo archivo: la fuente está en la carpeta temporal (sys._MEIPASS)')
        revisar(v.carpeta_programa() == (TEMPORAL / 'dist').resolve(), 'un solo archivo: carpeta_programa() es la del .exe')
        junto = armar('junto')   # («onedir» con contents_directory='.': todo al lado del .exe)
        compilada(junto / 'CineCaptions Ventas.exe', TEMPORAL / 'no-existe')
        revisar(v.recurso('fuentes/Inter.ttf') == junto.resolve() / 'fuentes' / 'Inter.ttf',
                'si sys._MEIPASS no la tiene, se busca junto al .exe')
    finally:
        for nombre in ('frozen', '_MEIPASS'):
            if nombre in guardado:
                setattr(sys, nombre, guardado[nombre])
            elif hasattr(sys, nombre):
                delattr(sys, nombre)
        sys.executable = ejecutable
    revisar(v.recurso('fuentes') == AQUI / 'fuentes' and (v.recurso('fuentes') / 'Inter.ttf').is_file(),
            'sin compilar: la fuente junto a ventas.py')
    revisar(v.carpeta_programa() == AQUI, 'sin compilar: carpeta_programa() es la de ventas.py')


def prueba_visual():
    print('Lo visual: diálogos, «Acerca de» y pocos datos')
    aplicacion()
    caja, si = v.caja_confirmacion(None, '¿Seguro?', 'La explicación.', 'Hacerlo')
    botones = [caja._botones.itemAt(i).widget() for i in range(caja._botones.count()) if caja._botones.itemAt(i).widget()]
    revisar([b.text() for b in botones] == ['Cancelar', 'Hacerlo'] and botones[0].isDefault() and botones[1] is si,
            'confirmación: «Cancelar» primero (y es el de Enter) y la acción al final, como en los demás diálogos')
    si.click()
    revisar(caja.clickedButton() is si and caja.result() == v.QDialog.DialogCode.Accepted, 'confirmación: la acción acepta')
    caja, si = v.caja_confirmacion(None, '¿Seguro?', 'La explicación.', 'Hacerlo')
    caja.reject()   # (Escape o la X)
    revisar(caja.clickedButton() is None, 'confirmación: Escape o la X no confirman')
    d = v.DialogoAcerca(None)
    # (las rutas llevan un espacio de ancho cero después de cada «\», para cortarse ahí)
    textos = [d.ficha._grid.itemAt(i).widget().text().replace('​', '') for i in range(d.ficha._grid.count())]
    revisar(d.version.text() == f'Versión {v.VERSION}' and str(v.carpeta_programa()) in textos
            and str(v.carpeta_config()) in textos, '«Acerca de»: la versión y la carpeta desde donde corre la app')
    revisar('Corre desde' in textos and 'Instalada en' not in textos, '«Acerca de»: sin compilar dice «Corre desde»')
    d.setAttribute(v.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    d.show()
    aplicacion().processEvents()
    revisar(all(l.height() >= l.heightForWidth(l.width()) for l in d.ficha.findChildren(v.QLabel) if l.wordWrap())
            and d.height() == d.layout().totalHeightForWidth(d.width()),
            '«Acerca de»: del alto justo de lo que tiene y las rutas largas caben enteras')
    d.close()
    # La copia instalada (el .exe en %LOCALAPPDATA%\Programs\CineCaptions Ventas) dice «Instalada en»
    guardado = {nombre: getattr(sys, nombre) for nombre in ('frozen',) if hasattr(sys, nombre)}
    ejecutable, local = sys.executable, os.environ.get('LOCALAPPDATA')
    try:
        os.environ['LOCALAPPDATA'] = str(TEMPORAL / 'Local')
        sys.frozen, sys.executable = True, str(TEMPORAL / 'Local' / 'Programs' / v.APP / 'CineCaptions Ventas.exe')
        instalada = v.instalada()
        sys.executable = str(TEMPORAL / 'dist' / 'CineCaptions Ventas.exe')
        suelta = v.instalada()
    finally:
        if 'frozen' in guardado:
            sys.frozen = guardado['frozen']
        elif hasattr(sys, 'frozen'):
            del sys.frozen
        sys.executable = ejecutable
        if local is None:
            os.environ.pop('LOCALAPPDATA', None)
        else:
            os.environ['LOCALAPPDATA'] = local
    if os.name == 'nt':
        revisar(instalada and not suelta and not v.instalada(),
                'instalada(): solo la copia de %LOCALAPPDATA%\\Programs (no un .exe suelto ni ventas.py)')
    else:   # Mac: «instalada» es la .app dentro de /Applications (ventas.instalada)
        revisar(not v.instalada(), 'instalada(): ventas.py sin compilar no cuenta como instalada')
    revisar(v.partir_monto('$29.00 USD') == ('$29.00', 'USD') and v.partir_monto('—') == ('—', ''),
            'el monto se dibuja con la moneda aparte')
    e = v.EventoHistorial({'tipo': 'uso', 'titulo': 'Abrió CineCaptions en «PC-EDICION · 3F2A-91BC-04DE-77A1»',
                           'fecha': '2026-10-29 15:05:00', 'detalle': None}, True, True)
    titulos = [l.text() for l in e.findChildren(v.QLabel)]
    revisar('Abrió CineCaptions en «PC‑EDICION»' in titulos,
            'el historial no repite la huella del equipo en el título (y el nombre corto no se parte en el guion)')

    # Con pocos datos: una venta en los últimos 30 días y otra más vieja, sin canjes ni avisos
    srv, url = servidor(pocos=True)
    w = ventana(url, mostrar=True)
    revisar(w.modelo_v.rowCount() == 2 and w.modelo_c.rowCount() == 0, 'pocos datos: 2 ventas y ningún canje')
    revisar(w.t_hoy.valor.property('apagada') and w.t_reemb.valor.property('apagada') and not w.t_total.valor.property('apagada'),
            'las tarjetas en cero salen tenues y las otras no')
    g = w.grafica
    con = [i for i, d in enumerate(g.dias) if d['ingresos']]
    revisar(len(con) == 1 and g.con_ventas() <= g.POCAS and g.barra(con[0]).top() - 20 >= 0,
            'gráfica con una venta: lleva el monto encima y la escala le deja aire')
    revisar(w.recientes._filas.count() == 2 and w.recientes.vacio.mensaje == 'Aquí vas a ver cada venta nueva.',
            '«Últimas ventas» con pocas: en el lugar que sobra dice que ahí van a salir las nuevas')
    revisar(w.bloque_versiones.grafica.filas == [('5.53', 1)],
            'la tarjeta de versiones con un solo equipo')
    g.poner([dict(d, ingresos=0, ventas=0, reembolsos=0) for d in g.dias], 'USD')
    revisar(g.con_ventas() == 0 and not g.grab().isNull(), 'gráfica sin ventas en 30 días: se dibuja con su letrero')
    w.ir_a('canjes')
    esperar(lambda: quieto(w), 'canjes')
    revisar(w.tabla_c.mensaje_vacio == 'Todavía no hay canjes de Gumroad.' and not w.tabla_c.viewport().grab().isNull(),
            'tabla vacía: el ícono y el mensaje')
    w.close()
    srv.shutdown()


# (antes de las capturas de prueba_casos_ventana: el Capturador termina con app.exit() y, en este proceso, un exec() que
# venga después ya no espera)
def prueba_confirmar_eliminar():
    print('La confirmación de «Eliminar venta», de verdad (con la casilla)')
    aplicacion()
    srv, url = servidor()
    w = ventana(url, mostrar=True)
    visto = []

    def responder(marcar, intento=0):   # la confirmación de verdad (con la casilla): la marca o no y dice que sí
        cajas = [c for c in w.findChildren(v.Caja) if c.isVisible()]
        if not cajas:   # (todavía no se abrió: se vuelve a mirar en un momento)
            if intento < 100:
                v.QTimer.singleShot(50, lambda: responder(marcar, intento + 1))
            return
        d = cajas[-1]
        visto.append((d.titulo.text(), d.casilla is not None))
        if d.casilla is not None:
            d.casilla.setChecked(marcar)
        botones = [d._botones.itemAt(i).widget() for i in range(d._botones.count()) if d._botones.itemAt(i).widget()]
        botones[-1].click()

    v.QTimer.singleShot(50, lambda: responder(True))
    ok, bloquear = v.VentanaPrincipal._preguntar_eliminar(w, '¿Eliminar?', 'x', 'Eliminar venta', 'Bloquear también…', True)
    revisar(ok and bloquear and visto == [('¿Eliminar?', True)],
            f'la confirmación de verdad devuelve «sí» y si se marcó la casilla ({ok}, {bloquear}, {visto})')
    w.close()
    srv.shutdown()


# ------------------------------------------------------------------ 9. Eliminar ventas (2.2.0)
def prueba_eliminar():
    print('Eliminar y restaurar ventas: la acción eliminar_venta')
    srv, url = servidor()
    datos = srv.datos
    c = v.ClienteApi(url, servidor_prueba.CLAVE)
    r = c.resumen()
    revisar(r['ventas']['eliminadas'] == 1 and r['ventas']['pendientes'] == 3 and r['ventas']['pagadas'] == 22,
            'resumen: cuántas ventas eliminadas hay (1) y no cuentan en los demás totales')
    elim = c.ventas('eliminadas')
    revisar(len(elim) == 1 and elim[0]['nombre'] == 'Kevin Morales' and elim[0]['estado'] == 'pendiente'
            and v.venta_eliminada(elim[0]), "estado 'eliminadas': solo las eliminadas, de cualquier estado de pago")
    crudas = c.llamar('ventas', estado='todos')['ventas']
    revisar(all('eliminada' in f for f in crudas)
            and not any(v.venta_eliminada(f) for estado in ('', 'pagado', 'reembolsado', 'pendiente', 'todos')
                        for f in c.ventas(estado)), 'cada fila trae «eliminada» y los demás estados nunca traen eliminadas')
    camila = next(f for f in c.ventas() if f['nombre'] == 'Camila Torres')
    antes = c.resumen()['ventas']
    grafica = sum(d['ingresos'] for d in c.estadisticas()['dias'])
    res = c.eliminar_venta(camila['id'], bloquear_licencia=True)
    lic = datos.licencia_real(camila['licencia_id'])
    revisar(res['eliminada'] and res['licencia_bloqueada'] and lic['estado'] == 'bloqueada',
            'eliminar con «bloquear también su licencia»: la bloquea')
    revisar(res['resumen']['ventas']['pagadas'] == antes['pagadas'] - 1 and res['resumen']['ventas']['ingresos'] == antes['ingresos'] - 1900
            and res['resumen']['ventas']['eliminadas'] == 2, 'eliminar: sale de los totales (el resumen nuevo viene en la respuesta)')
    revisar(all(f['id'] != camila['id'] for f in c.ventas('todos')) and any(f['id'] == camila['id'] for f in c.ventas('eliminadas'))
            and sum(d['ingresos'] for d in c.estadisticas()['dias']) == grafica - 1900,
            'eliminar: sale de la lista y de la gráfica, y está en «eliminadas»')
    revisar(datos.pedido(camila['id']) is not None and c.detalle(pedido_id=camila['id'])['pedido']['eliminada'],
            'eliminar no borra nada: el detalle sigue (con la fecha en que se eliminó)')
    revisar(any(e['titulo'] == 'Venta eliminada de la lista desde la app' and e['tipo'] == 'admin'
                and 'también se bloqueó su licencia' in (e['detalle'] or '') for e in c.historial(licencia_id=lic['id'])),
            'eliminar queda en el historial de la licencia')
    fecha, cambios = datos.pedido(camila['id'])['eliminada'], len(datos.cambios)
    res = c.eliminar_venta(camila['id'], bloquear_licencia=True)
    revisar(res['eliminada'] and not res['licencia_bloqueada'] and datos.pedido(camila['id'])['eliminada'] == fecha
            and len(datos.cambios) == cambios, 'eliminar otra vez no cambia nada (ni la fecha; la licencia ya estaba bloqueada)')
    res = c.eliminar_venta(camila['id'], eliminar=False, bloquear_licencia=True)
    revisar(not res['eliminada'] and not res['licencia_bloqueada'] and datos.pedido(camila['id'])['eliminada'] is None
            and res['resumen']['ventas']['pagadas'] == antes['pagadas'] and res['resumen']['ventas']['eliminadas'] == 1,
            'restaurar: vuelve a la lista y a los totales')
    revisar(lic['estado'] == 'bloqueada' and any(e['titulo'] == 'Venta restaurada desde la app'
                                                 for e in c.historial(licencia_id=lic['id'])),
            'restaurar no reactiva la licencia (eso es aparte) y queda en el historial')
    lucia = next(f for f in c.ventas() if f['nombre'] == 'Lucía Fernández')
    res = c.eliminar_venta(lucia['id'])
    revisar(res['eliminada'] and not res['licencia_bloqueada'] and datos.licencia(lucia['licencia_id'])['estado'] == 'activa',
            'eliminar sin la casilla: la licencia sigue funcionando')
    e = error_de(lambda: c.eliminar_venta(9999))
    revisar(e is not None and e.codigo == 404 and e.mensaje == 'No existe esa venta.', 'eliminar una venta que no existe: 404')
    kevin = datos.pedido(elim[0]['id'])   # el cliente termina de pagar el pago que se había eliminado
    kevin['estado'], kevin['pagado'] = 'pagado', servidor_prueba._f(datos.ahora() + dt.timedelta(seconds=5))
    vuelta = next((f for f in c.ventas() if f['id'] == kevin['id']), None)
    revisar(vuelta is not None and not v.venta_eliminada(vuelta) and c.resumen()['ventas']['eliminadas'] == 1,
            'un pago sin completar eliminado que se paga después vuelve solo a la lista (pagado > eliminada)')
    lectura, n = v.ClienteApi(url, servidor_prueba.CLAVE, solo_lectura=True), len(srv.acciones_recibidas)
    e = error_de(lambda: lectura.eliminar_venta(lucia['id'], eliminar=False))
    revisar(e is not None and len(srv.acciones_recibidas) == n and 'eliminar_venta' in v.ACCIONES_QUE_CAMBIAN,
            'solo lectura (--captura): eliminar_venta ni sale')
    srv.shutdown()
    for opciones, nombre in (({'viejo': True}, 'servidor anterior'), ({'sin_errores': True}, 'admin.php de antes de la 5.71')):
        srv, url = servidor(**opciones)
        c = v.ClienteApi(url, servidor_prueba.CLAVE)
        e = error_de(lambda: c.eliminar_venta(1))
        crudas = c.llamar('ventas', estado='eliminadas')['ventas']
        revisar(e is not None and e.desconocida and 'eliminadas' not in c.resumen()['ventas'] and len(crudas) == 24
                and not any('eliminada' in f for f in crudas), f'{nombre}: sin eliminar_venta, sin «eliminadas» ni «eliminada»')
        srv.shutdown()

    print('Eliminar y restaurar ventas en la ventana')
    aplicacion()
    caja, si = v.caja_confirmacion(None, '¿Eliminar la venta?', 'La explicación.', 'Eliminar venta', True, 'basura',
                                   casilla='Bloquear también su licencia (deja de funcionar en sus 2 equipos)')
    caja.setAttribute(v.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    caja.show()
    aplicacion().processEvents()
    t = caja.casilla.texto
    revisar(caja.casilla is not None and not caja.casilla.isChecked()
            and t.text() == 'Bloquear también su licencia (deja de funcionar en sus 2 equipos)'
            and t.height() >= t.heightForWidth(t.width()) and caja.casilla.geometry().right() <= caja.width(),
            'la confirmación con la casilla: desmarcada, y su texto largo cabe entero (en dos líneas)')
    from PySide6.QtTest import QTest
    QTest.mouseClick(t, v.Qt.MouseButton.LeftButton)
    revisar(caja.casilla.isChecked(), 'un clic en el texto de la casilla también la marca')
    caja.close()
    caja, si = v.caja_confirmacion(None, '¿Seguro?', 'x', 'Hacerlo')
    revisar(caja.casilla is None, 'sin casilla, la confirmación es la de siempre')

    srv, url = servidor()
    datos = srv.datos
    w = ventana(url, mostrar=True)

    preguntas = []
    respuesta = {'ok': True, 'bloquear': False}

    def preguntar(pregunta, explicacion, texto_boton, casilla, peligro):
        preguntas.append((pregunta, explicacion, texto_boton, casilla, peligro))
        return respuesta['ok'], respuesta['bloquear']

    w._preguntar_eliminar = preguntar
    i = w.filtro.findData('eliminadas')
    revisar(w.filtro.itemText(i) == 'Eliminadas (1)' and w.filtro.model().item(i).isEnabled() and w.panel.con_eliminar is True,
            'filtro «Eliminadas» con su contador (1)')
    w.ir_a('ventas')
    fila = elegir(w, w.tabla_v, lambda f: f['nombre'] == 'Sofía Rodríguez')
    b = w.panel.btn_eliminar
    revisar(b.isVisible() and b.isEnabled() and b.text().strip() == 'Eliminar venta' and b.property('tipo') == 'peligro'
            and 'no se borra' in w.panel.nota_eliminar.text(), 'al elegir una venta: «Eliminar venta», en rojo, con su nota')
    revisar(not hasattr(w.panel, 'btn_eliminar_arriba') and w.panel.pila.currentWidget() is w.panel._paginas['licencia']
            and b.mapTo(w.panel, v.QPoint(0, 0)).y() < w.panel.height(),
            '2.3: sin la papelera de arriba; en la pestaña «Licencia» se ve «Eliminar venta» sin bajar')
    respuesta['ok'] = False
    b.click()
    esperar(lambda: quieto(w), 'cancelar eliminar')
    pregunta, explicacion, texto_boton, casilla, peligro = preguntas[-1]
    revisar(pregunta == '¿Eliminar la venta de Sofía Rodríguez?' and 'NO se borra' in explicacion
            and 'de la lista y de los totales' in explicacion and '«Eliminadas»' in explicacion and texto_boton == 'Eliminar venta'
            and casilla == 'Bloquear también su licencia (deja de funcionar en su equipo)' and peligro,
            'la pregunta: sale de la lista y de los totales, NO se borra, se restaura desde «Eliminadas»; con la casilla')
    revisar(datos.pedido(fila['id'])['eliminada'] is None and 'eliminar_venta' not in srv.acciones_recibidas,
            'si se cancela, no se manda nada')
    respuesta['ok'] = True
    pagadas = w.resumen['ventas']['pagadas']
    b.click()
    b.click()   # (doble clic: el segundo llega con el panel ocupado)
    w._eliminar_venta(dict(fila), True)   # (y otro desde el menú mientras va)
    esperar(lambda: quieto(w) and w.panel.detalle is not None and v.venta_eliminada(w.panel.detalle['pedido']), 'eliminar')
    revisar(srv.acciones_recibidas.count('eliminar_venta') == 1, 'doble clic o clics repetidos: se manda una sola vez')
    revisar(datos.pedido(fila['id'])['eliminada'] and datos.licencia(fila['licencia_id'])['estado'] == 'activa',
            'eliminada en el servidor y, con la casilla desmarcada, su licencia sigue activa')
    revisar(not w.modelo_v.buscar('id', fila['id']) and w.resumen['ventas']['pagadas'] == pagadas - 1
            and w.filtro.itemText(i) == 'Eliminadas (2)' and not any(f['id'] == fila['id'] for f in w.recientes.ventas),
            'sale de la lista, de las tarjetas y de «Últimas ventas»; el filtro cuenta 2')
    revisar('«Eliminadas»' in w.statusBar().currentMessage() and w.aviso.texto.text().startswith('Venta eliminada'),
            'mensaje en la barra de estado')
    revisar(w.panel.btn_eliminar.text().strip() == 'Restaurar venta' and w.panel.btn_eliminar.property('tipo') is None
            and 'ELIMINADA' in w.panel.tipo.text() and not w.panel.btn_reembolso.isVisible()
            and any(e['titulo'] == 'Venta eliminada de la lista desde la app' for e in w.panel.historial.eventos),
            'la venta sigue en el panel: «Restaurar venta» y el historial con lo que se hizo')
    n = len(srv.acciones_recibidas)
    w.actualizar_todo()   # (como la actualización de cada 2 minutos)
    esperar(lambda: quieto(w), 'actualizar con la venta eliminada en el panel')
    revisar(w.panel.detalle is not None and w.panel.detalle['pedido']['id'] == fila['id'] and len(srv.acciones_recibidas) > n,
            'al actualizar, el panel sigue con ella')
    apretar(w, w.panel.btn_eliminar, 'restaurar desde el panel')
    revisar(datos.pedido(fila['id'])['eliminada'] is None and w.modelo_v.buscar('id', fila['id'])
            and (w._fila_actual(w.tabla_v) or {}).get('id') == fila['id'] and w.resumen['ventas']['pagadas'] == pagadas
            and w.filtro.itemText(i) == 'Eliminadas (1)', 'restaurar desde el panel: vuelve a la lista (elegida) y a los totales')
    revisar(w.aviso.texto.text().startswith('Venta restaurada') and preguntas[-1][0] == '¿Restaurar la venta de Sofía Rodríguez?'
            and preguntas[-1][3] is None and not preguntas[-1][4], 'restaurar pregunta (sin casilla) y no avisa «¡Nueva venta!»')
    # Desde el clic derecho, con la casilla marcada
    respuesta['bloquear'] = True
    fila = next(f for f in w.modelo_v.filas if f['nombre'] == 'Pablo Estrada')
    menu = w._armar_menu_tabla(w.tabla_v, fila)
    acciones = {a.text(): a for a in menu.actions() if a.text()}
    revisar('Eliminar venta…' in acciones and 'Copiar clave' in acciones and acciones['Eliminar venta…'].isEnabled(),
            'clic derecho en una venta: «Eliminar venta…»')
    acciones['Eliminar venta…'].trigger()
    esperar(lambda: quieto(w), 'eliminar desde el menú')
    revisar(datos.pedido(fila['id'])['eliminada'] and datos.licencia(fila['licencia_id'])['estado'] == 'bloqueada'
            and 'licencia bloqueada' in w.aviso.texto.text(), 'con la casilla marcada también se bloquea su licencia')
    # El filtro «Eliminadas»: atenuadas y con «Restaurar»
    w.filtro.setCurrentIndex(i)
    esperar(lambda: quieto(w) and w.modelo_v.rowCount() == 2, 'filtro Eliminadas')
    col = {c: k for k, (c, _t, _a) in enumerate(v.ModeloVentas.COLUMNAS)}
    n = w.modelo_v.buscar('id', fila['id'])[0]
    revisar(all(v.venta_eliminada(f) for f in w.modelo_v.filas)
            and w.modelo_v.index(n, col['cliente']).data(v.Qt.ItemDataRole.ForegroundRole) == v.QColor(v.TEXTO_TENUE)
            and w.modelo_v.index(n, col['estado']).data(v.ROL_INSIGNIA)[1] == v.TEXTO_TENUE
            and 'Eliminada de la lista' in w.modelo_v.index(n, col['fecha']).data(v.Qt.ItemDataRole.ToolTipRole),
            'filtro «Eliminadas»: solo las eliminadas, atenuadas y con el porqué')
    revisar(w.lbl_pie_v.text().startswith('2 ventas eliminadas') and w.barra.botones['ventas'].contador == 23,
            'el pie lo dice y la isla del menú sigue contando las ventas de la lista normal')
    menu = w._armar_menu_tabla(w.tabla_v, w.modelo_v.fila(n))
    acciones = {a.text(): a for a in menu.actions() if a.text()}
    revisar('Restaurar venta…' in acciones and 'Eliminar venta…' not in acciones, 'en «Eliminadas» el clic derecho ofrece «Restaurar venta…»')
    elegir(w, w.tabla_v, lambda f: f['id'] == fila['id'])
    revisar(w.panel.btn_eliminar.text().strip() == 'Restaurar venta', 'y el panel también')
    acciones['Restaurar venta…'].trigger()
    esperar(lambda: quieto(w) and w.modelo_v.rowCount() == 1, 'restaurar desde el menú')
    revisar(datos.pedido(fila['id'])['eliminada'] is None and preguntas[-1][3] is None
            and 'sigue bloqueada' in preguntas[-1][1], 'restaurar desde el menú (y la pregunta avisa que la licencia sigue bloqueada)')
    revisar(w.panel.detalle['pedido']['id'] == fila['id'] and w.panel.btn_eliminar.text().strip() == 'Eliminar venta',
            'la venta restaurada sigue en el panel, con «Eliminar venta» otra vez')
    kevin = w.modelo_v.fila(0)
    pregunta, _e, _b, casilla = w._textos_eliminar(dict(kevin, eliminada=None), True)
    revisar(casilla is None and pregunta == '¿Eliminar la venta de Kevin Morales?', 'un pago sin completar (sin licencia): sin casilla')
    elegir(w, w.tabla_v, lambda f: True)
    respuesta['ok'] = True
    apretar(w, w.panel.btn_eliminar, 'restaurar la última eliminada')
    esperar(lambda: quieto(w) and w.modelo_v.rowCount() == 0, 'sin eliminadas')
    revisar(w.tabla_v.mensaje_vacio.startswith('No hay ventas eliminadas') and w.filtro.itemText(i) == 'Eliminadas',
            'sin eliminadas: la tabla dice qué pasa y el filtro ya no lleva número')
    # «Últimas ventas» abre una venta aunque esté elegido el filtro «Eliminadas»
    w.ir_a('resumen')
    reciente = w.recientes.ventas[0]['id']
    w._abrir_venta(reciente)
    esperar(lambda: quieto(w) and (w._fila_actual(w.tabla_v) or {}).get('id') == reciente, 'abrir desde Últimas ventas')
    revisar(w.filtro.currentData() == '' and w._fila_actual(w.tabla_v)['id'] == reciente,
            '«Últimas ventas» con el filtro «Eliminadas»: vuelve a la lista normal y elige la venta')
    w.close()
    srv.shutdown()

    # El servidor no sabe eliminar (el anterior o el de antes de la 5.71): apagado, con su nota, y si igual se intenta, lo dice
    for opciones in ({'sin_errores': True}, {'viejo': True}):
        srv, url = servidor(**opciones)
        w = ventana(url, mostrar=True)
        w.ir_a('ventas')
        elegir(w, w.tabla_v, lambda f: f['nombre'] == 'Mariana López')
        i = w.filtro.findData('eliminadas')
        revisar(w.panel.con_eliminar is False and w.panel.btn_eliminar.isVisible() and not w.panel.btn_eliminar.isEnabled()
                and 'pagos/admin.php' in w.panel.nota_eliminar.text() and not w.filtro.model().item(i).isEnabled(),
                f"{opciones}: «Eliminar venta» apagado, con la nota de que falta el servidor nuevo, y sin el filtro")
        menu = w._armar_menu_tabla(w.tabla_v, w._fila_actual(w.tabla_v))
        revisar(not [a for a in menu.actions() if a.text().startswith('Eliminar venta')][0].isEnabled(),
                f'{opciones}: en el clic derecho también')
        w.mensajes.clear()
        w._eliminar_venta(w._fila_actual(w.tabla_v), True)
        revisar(w.mensajes and w.mensajes[-1][0] == 'Falta el servidor nuevo' and 'eliminar_venta' not in srv.acciones_recibidas,
                f'{opciones}: si se intenta igual, lo explica y no manda nada')
        if 'sin_errores' in opciones:   # (cuando todavía no se sabía: el servidor responde 400 y la app lo explica)
            w.panel.set_eliminar(None)
            w.mensajes.clear()
            w._eliminar_venta(w._fila_actual(w.tabla_v), True)
            esperar(lambda: quieto(w), 'eliminar con el servidor de antes')
            revisar(w.mensajes and w.mensajes[-1] == ('No se pudo eliminar la venta', v.SERVIDOR_SIN_ELIMINAR)
                    and w.panel.con_eliminar is False and srv.datos.pedido(w._fila_actual(w.tabla_v)['id']).get('eliminada') is None,
                    'servidor de antes (400): mensaje claro de que hay que actualizar el servidor; la venta sigue igual')
        revisar(not v.ERRORES, f'{opciones}: ningún error inesperado')
        w.close()
        srv.shutdown()


# ------------------------------------------------------------------ 10. La página Versiones (2.2.0)
def prueba_versiones():
    print('Versiones: quién va atrasado y a quién avisar')
    from PySide6.QtTest import QTest
    srv, url = servidor()
    datos = srv.datos
    w = ventana(url, mostrar=True)
    w.ir_a('versiones')
    esperar(lambda: quieto(w) and w.modelo_ver.rowCount() > 0, 'Versiones')
    p = w.plan_versiones
    revisar(w.modelo_ver.rowCount() == 22 and sum(c['equipos'] for c in w.modelo_ver.filas) == 26,
            'un cliente por fila (22), con sus 26 equipos')
    revisar({k: p.cuenta[k] for k in ('clientes', 'desactualizado', 'al_dia', 'sin_datos', 'avisados', 'por_avisar',
                                      'equipos_viejos', 'bloqueados')}
            == {'clientes': 21, 'desactualizado': 9, 'al_dia': 9, 'sin_datos': 3, 'avisados': 3, 'por_avisar': 6,
                'equipos_viejos': 9, 'bloqueados': 1},
            'la tarjeta cuenta clientes con la licencia activa: 9 atrasados, a 3 ya se les avisó, faltan 6')
    revisar('9 clientes' in p.lbl_frase.text() and 'todavía no tienen la 5.54' in p.lbl_frase.text()
            and p.lbl_detalle.text() == 'Usan una versión anterior en 9 equipos. A 3 clientes ya les avisaste; faltan 6.'
            and p.lbl_titulo.text().startswith('LA ÚLTIMA ES LA 5.54 · SALIÓ EL'),
            'en palabras: «9 clientes todavía no tienen la 5.54», a cuántos ya se les avisó y cuándo salió')
    revisar('9 clientes al día' in p.lbl_leyenda.text() and '9 con una versión vieja' in p.lbl_leyenda.text()
            and '3 sin datos' in p.lbl_leyenda.text(), 'la barra con sus números en palabras (y su color)')
    revisar(p.btn_avisar.text().strip() == 'Avisar a los 6 que faltan…' and p.btn_avisar.property('tipo') == 'primario'
            and p.btn_avisar.isEnabled() and p.lbl_accion.isVisible(), 'la acción principal a un clic: «Avisar a los 6 que faltan…»')
    revisar([w.filtro_ver.botones[k].text() for k in ('todos', 'desactualizado', 'al_dia', 'sin_datos')]
            == ['Todos  22', 'Desactualizados  9', 'Al día  9', 'Sin datos  3'],
            'los filtros cuentan lo mismo que la tarjeta (los números de la página coinciden)')
    revisar(not hasattr(w, 'btn_anunciar'), 'en Versiones, «Anunciar» no se repite arriba: está en la tarjeta (2.3: ni en el encabezado)')
    cv = {c: i for i, (c, _t, _a) in enumerate(v.ModeloVersiones.COLUMNAS)}
    primeras = [w._fila_de(w.tabla_ver, w.proxy_ver.index(n, 0)) for n in range(w.proxy_ver.rowCount())]
    revisar([w.modelo_ver.aviso(f)[0] for f in primeras[:6]] == ['Avisar'] * 6
            and [w.modelo_ver.aviso(f)[0].split()[0] for f in primeras[6:9]] == ['Avisado'] * 3,
            'de entrada van primero los que faltan por avisar (con «Avisar»), después los ya avisados')
    luis = next(c for c in w.modelo_ver.filas if c['cliente'] == 'Luis Fernando Gómez')
    jose = next(c for c in w.modelo_ver.filas if c['cliente'] == 'José Ñúñez')
    mariana = next(c for c in w.modelo_ver.filas if c['cliente'] == 'Mariana López')
    revisar(w.modelo_ver.aviso(luis)[0] == 'Bloqueada' and w.modelo_ver.aviso(jose)[0] == '—'
            and w.modelo_ver.aviso(mariana)[0] == '—' and 'ya tiene la 5.54' in w.modelo_ver.aviso(mariana)[4]
            and w.modelo_ver.estado(jose) == 'sin_datos' and v.SIN_DATOS_VERSION
            == w.modelo_ver.index(w.modelo_ver.buscar('id', jose['id'])[0], cv['version']).data(v.Qt.ItemDataRole.ToolTipRole),
            'cada estado con su texto y su explicación (bloqueada, sin datos, al día)')
    w.filtro_ver.poner('al_dia')
    revisar(w.proxy_ver.rowCount() == 9 and luis['id'] not in [w._fila_de(w.tabla_ver, w.proxy_ver.index(n, 0))['id']
                                                                for n in range(w.proxy_ver.rowCount())],
            '«Al día»: sin la licencia bloqueada (no cuenta)')
    w.filtro_ver.poner('todos')
    # «Avisar» dentro de la tabla: un clic (de verdad, con el mouse) pregunta y manda el aviso de ese cliente
    lucia = next(c for c in w.modelo_ver.filas if c['cliente'] == 'Lucía Fernández')
    fila_vista = w.proxy_ver.mapFromSource(w.modelo_ver.index(w.modelo_ver.buscar('id', lucia['id'])[0], cv['aviso']))
    w.tabla_ver.scrollTo(fila_vista)
    aplicacion().processEvents()
    caja = v.DelegadoBoton.caja(w.tabla_ver.visualRect(fila_vista), 'Avisar')
    n = len(datos.avisos)
    w._confirmar = lambda pregunta, *a, **k: w.preguntas.append(pregunta) and False   # «Cancelar»
    QTest.mouseClick(w.tabla_ver.viewport(), v.Qt.MouseButton.LeftButton, v.Qt.KeyboardModifier.NoModifier,
                     caja.center().toPoint())
    esperar(lambda: quieto(w) and w.preguntas, 'cancelar el aviso desde la tabla')
    revisar(len(datos.avisos) == n and w.preguntas[-1] == '¿Avisar a Lucía Fernández que actualice a la 5.54?',
            '«Avisar» en la tabla pregunta antes; si se cancela no sale nada')
    w._confirmar = lambda pregunta, *a, **k: w.preguntas.append(pregunta) or True
    QTest.mouseClick(w.tabla_ver.viewport(), v.Qt.MouseButton.LeftButton, v.Qt.KeyboardModifier.NoModifier,
                     caja.center().toPoint())
    w._avisar_cliente(dict(lucia))   # (otro clic mientras sale: no manda otro)
    esperar(lambda: quieto(w) and len(datos.avisos) > n, 'avisar desde la tabla')
    esperar(lambda: quieto(w) and p.cuenta.get('por_avisar') == 5, 'Versiones otra vez')
    revisar(len(datos.avisos) == n + 1 and datos.avisos[-1]['ok'] and datos.avisos[-1]['licencia_id'] == lucia['licencia_id']
            and datos.avisos[-1]['version'] == '5.54' and datos.avisos[-1]['mensaje'].startswith('Exporta'),
            '«Avisar» en la tabla: manda UN aviso de la 5.54 (con lo nuevo) a ese cliente')
    lucia = next(c for c in w.modelo_ver.filas if c['cliente'] == 'Lucía Fernández')
    revisar(w.modelo_ver.aviso(lucia)[0].startswith('Avisado') and p.btn_avisar.text().strip() == 'Avisar a los 5 que faltan…'
            and w.aviso.texto.text() == 'Aviso enviado a lucia.fernandez@example.com.',
            'después: su fila dice «Avisado», la tarjeta cuenta 5 y el mensaje dice a dónde se mandó')
    revisar((w._fila_actual(w.tabla_ver) or {}).get('licencia_id') == lucia['licencia_id']
            and w.panel.nombre.texto() == 'Lucía Fernández', 'el clic también la elige: su licencia queda en el panel')
    menu = w._armar_menu_tabla(w.tabla_ver, lucia)
    acciones = {a.text(): a for a in menu.actions() if a.text()}
    revisar('Reenviar aviso de la 5.54…' in acciones, 'ya avisado: el clic derecho ofrece reenviarlo')
    acciones['Reenviar aviso de la 5.54…'].trigger()
    esperar(lambda: quieto(w) and len(datos.avisos) == n + 2, 'reenviar desde el menú')
    revisar(datos.avisos[-1]['ok'] and w.preguntas[-1].startswith('¿Reenviar el aviso de la 5.54'), 'reenviar: forzar=true, con su pregunta')
    paola = next(c for c in w.modelo_ver.filas if c['cliente'] == 'Paola Girón')
    w.mensajes.clear()
    w._avisar_cliente(paola)
    esperar(lambda: quieto(w), 'avisar a quien se dio de baja')
    revisar(w.mensajes and w.mensajes[-1][0] == 'No se mandó el aviso' and 'no recibir' in w.mensajes[-1][1],
            'si pidió no recibir avisos, lo explica')
    # La acción de la tarjeta abre «Anunciar versión» (a los desactualizados)
    abiertos = []

    class Dialogo:
        enviados, terminado = 0, False

        def exec(self):
            abiertos.append(True)

    w.crear_anunciar = lambda: Dialogo()
    p.btn_avisar.click()
    revisar(abiertos == [True], 'la acción de la tarjeta abre «Anunciar versión»')
    # Los textos de la tarjeta en los demás casos
    al_dia = [dict(c, estado='al_dia', viejos=0) for c in w.modelo_ver.filas if c['licencia_estado'] == 'activa']
    p.poner(al_dia, '5.54')
    revisar('Todos tus clientes tienen la 5.54' in p.lbl_frase.text() and p.btn_avisar.text().strip() == 'Anunciar versión 5.54…'
            and p.btn_avisar.property('tipo') is None, 'todos al día: lo dice y la acción queda como «Anunciar versión 5.54…»')
    p.poner([], '5.54')
    revisar('Todavía ningún cliente activó CineCaptions' in p.lbl_frase.text() and not p.barra.isVisible(),
            'sin equipos: dice qué va a pasar')
    p.poner(w.modelo_ver.filas, None, {'error': 'GitHub tardó demasiado en responder.'})
    revisar('No se sabe cuál es la última versión' in p.lbl_frase.text() and 'GitHub' in p.lbl_detalle.text(),
            'sin saber la última versión: lo dice y qué hacer')
    w._poner_bloques_versiones()
    # Nada cortado ni encimado, a 1100 y a 1920 px
    for ancho, alto in ((1100, 720), (1920, 1040)):
        w.resize(ancho, alto)
        for _ in range(5):
            aplicacion().processEvents()
        etiquetas = [l for l in p.findChildren(v.QLabel) if l.isVisibleTo(p) and l.wordWrap()]
        b = p.btn_avisar
        texto_cabe = b.width() >= b.sizeHint().width()
        aviso_visible = not w.tabla_ver.isColumnHidden(cv['aviso'])
        revisar(all(l.height() >= l.heightForWidth(l.width()) for l in etiquetas) and texto_cabe and aviso_visible
                and p.geometry().bottom() < w.tabla_ver.parentWidget().geometry().top(),
                f'a {ancho} px: los textos de la tarjeta caben enteros, el botón también y la columna «Aviso» se ve')
        revisar(p.medio.isVisible() == (ancho >= 1920) and p._columnas == (ancho >= 1920),
                f'a {ancho} px: ' + ('las barras por versión en medio y la acción a la derecha' if ancho >= 1920
                                     else 'la acción debajo, a todo lo ancho, sin las barras'))
    w.close()
    srv.shutdown()
    srv, url = servidor(viejo=True)
    w = ventana(url, mostrar=True)
    w.ir_a('versiones')
    esperar(lambda: quieto(w), 'Versiones con el servidor anterior')
    revisar(w.plan_versiones.lbl_detalle.text() == v.FALTA_SERVIDOR and not w.plan_versiones.btn_avisar.isVisible(),
            'servidor anterior: la tarjeta dice que falta el servidor nuevo, sin el botón')
    w.close()
    srv.shutdown()


# ------------------------------------------------------------------ 11. La ficha técnica de los equipos (2.4)
FICHA_CONTRATO = {   # (el ejemplo del contrato con CineCaptions 5.72)
    'v': 1, 'cuando': '2026-11-06T10:00:00Z', 'origen': 'app', 'app': {'version': '5.72', 'idioma': 'es'},
    'so': {'nombre': 'Windows 11 Pro', 'version': '24H2', 'build': '26100.2314', 'arquitectura': 'x64'},
    'cpu': {'nombre': 'AMD Ryzen 9 5900X 12-Core Processor', 'hilos': 24, 'avx2': True},
    'ram': {'total_mb': 32694, 'libre_mb': 14210},
    'gpus': [{'nombre': 'NVIDIA GeForce RTX 4070', 'fabricante': 'NVIDIA', 'vram_mb': 12282, 'driver': '596.36',
              'driver_fecha': '2026-10-01', 'principal': True}],
    'pantallas': [{'ancho': 3840, 'alto': 2160, 'escala': 150}],
    'discos': [{'uso': 'programa', 'unidad': 'C:', 'libre_gb': 120.5, 'total_gb': 930.4},
               {'uso': 'datos', 'unidad': 'D:', 'libre_gb': 50.0, 'total_gb': 1863.0}],
    'resolve': {'instalado': True, 'edicion': 'Studio', 'version': '21.2.0.12'},
    'motores': {'voz': {'instalado': True, 'torch': '2.15.0+cu132'}, 'auxiliar': {'instalado': True, 'python': '3.14.10'},
                'whisper': True},
    'componentes': {'vcredist_x64': '14.44.35211', 'winget': '1.12.350'},
    'revision': [{'id': 'driver_gpu', 'estado': 'aviso', 'texto': 'Driver NVIDIA 566.36: funciona; con 595 o más la voz va más rápida'}],
    'puesta_al_dia': {'cuando': '2026-11-06T09:58:00Z', 'hecho': ['Visual C++ 14.44 instalado'],
                      'pendiente': ['Driver de la GPU: no hay uno más nuevo en Windows Update'], 'fallos': []}}


def act_de(datos, pc):
    return next(a for a in datos.activaciones if a['nombre_equipo'].startswith(pc + ' · '))


def prueba_fichas():
    print('Ficha técnica de los equipos (2.4, CineCaptions 5.72): equipo.php, equipo_ficha y la ventana')
    import urllib.error
    import urllib.parse
    import urllib.request

    # Funciones sueltas: el contrato entero, cada sección en su orden y con su formato
    s = v.secciones_ficha(FICHA_CONTRATO)
    por = {x['titulo']: x for x in s}
    filas = {t: dict((f[0], f[1]) for f in x['filas']) for t, x in por.items()}
    revisar([x['titulo'] for x in s] == ['Sistema', 'Procesador', 'Memoria', 'Tarjeta gráfica', 'Pantalla', 'Discos',
                                         'DaVinci Resolve', 'Motores', 'Componentes', 'Revisión', 'Puesta al día'],
            'la ficha del contrato: las secciones en el orden de siempre (sin «Otros datos»: todo se conoce)')
    revisar(filas['Sistema'] == {'Sistema': 'Windows 11 Pro 24H2 · build 26100.2314 · x64', 'CineCaptions': '5.72 · idioma es'}
            and filas['Procesador'] == {'Modelo': 'AMD Ryzen 9 5900X 12-Core Processor', 'Hilos': '24', 'AVX2': 'Sí'}
            and filas['Memoria'] == {'Total': '32 GB', 'Libre': '13,9 GB (43 %)'},
            'sistema, procesador y memoria (en GB, con coma)')
    revisar(filas['Tarjeta gráfica'] == {'Modelo': 'NVIDIA GeForce RTX 4070', 'VRAM': '12 GB', 'Driver': '596.36 · del 1 oct 2026'}
            and filas['Pantalla'] == {'Resolución': '3840×2160 al 150 %'},
            'la tarjeta gráfica con su VRAM y su driver (sin repetir el fabricante) y la pantalla')
    discos = por['Discos']['filas']
    revisar(discos == [('Programa (C:)', '120,5 GB libres de 930,4 GB', None), ('Datos (D:)', '50 GB libres de 1,8 TB', v.AVISO)],
            'los discos: cuánto queda de cuánto; el de datos, casi lleno (menos del 10 %), en naranja')
    revisar(filas['DaVinci Resolve'] == {'Edición': 'Studio', 'Versión': '21.2.0.12'}
            and filas['Motores'] == {'Voz (IA)': 'Instalado · torch 2.15.0+cu132', 'Auxiliar': 'Instalado · Python 3.14.10',
                                     'Whisper': 'Instalado'}
            and filas['Componentes'] == {'Visual C++ (x64)': '14.44.35211', 'winget': '1.12.350'},
            'Resolve, los motores y los componentes')
    revisar(por['Revisión']['puntos'] == [(v.AVISO, 'Aviso', 'Driver NVIDIA 566.36: funciona; con 595 o más la voz va más rápida')]
            and por['Revisión']['extra'] == '1 aviso', 'la revisión: un punto naranja por el aviso')
    revisar(por['Puesta al día']['filas'] == [('Hecho', 'Visual C++ 14.44 instalado', None),
                                              ('Pendiente', 'Driver de la GPU: no hay uno más nuevo en Windows Update', v.AVISO)]
            and por['Puesta al día']['extra'].startswith('6 nov 2026'), 'la puesta al día: lo hecho y lo pendiente (en naranja)')
    raro = v.secciones_ficha({'cpu': 'Ryzen', 'gpus': {'nombre': 'X'}, 'revision': 'mal', 'ram': {'total_mb': 'mucho'},
                              'motores': {'voz': [1, 2]}, 'nuevo': {'a': 1}, 'pantallas': [{'ancho': 1920, 'alto': 1080, 'hz': 144}],
                              'discos': [{'uso': 'cache', 'libre_gb': float('inf')}],
                              'revision_extra': None, 'so': {'nombre': 'Linux', 'kernel': '6.8'}})
    otros = {f[0]: f[1] for x in raro if x['titulo'] == 'Otros datos' for f in x['filas']}
    revisar(otros == {'cpu': 'Ryzen', 'gpus': '{"nombre": "X"}', 'revision': 'mal', 'nuevo': '{"a": 1}', 'revision_extra': '—'}
            and any(('kernel', '6.8', None) in x['filas'] for x in raro) and any(('hz', '144', None) in x['filas'] for x in raro)
            and any(('Voz (IA)', '[1, 2]', None) in x['filas'] for x in raro)
            and any(('Total', 'mucho', None) in x['filas'] for x in raro),
            'lo que no se conoce (o viene con otra forma) sale en bruto, sin romper nada')
    revisar(v.secciones_ficha(None) == [] and v.secciones_ficha({}) == [] and v.secciones_ficha([1]) == [],
            'una ficha vacía o que no es un objeto: nada')
    revisar(v.normalizar_ficha_equipo(None) is None and v.normalizar_ficha_equipo({'ficha': [1], 'resumen': 'R', 'cuando': ''})
            == {'ficha': None, 'resumen': 'R', 'cuando': None}, 'normalizar_ficha_equipo: null, una ficha que no es un objeto')
    e = v.normalizar_equipo({'equipo': 'X', 'con_ficha': '1', 'ficha_resumen': 'GPU X'})
    revisar(e['con_ficha'] is True and e['ficha_resumen'] == 'GPU X' and v.normalizar_equipo({'equipo': 'X'})['con_ficha'] is False,
            'normalizar_equipo: con_ficha y su línea (y sin ellas, con un servidor de antes)')
    revisar('ficha_equipo' not in v.normalizar_error({'id': 1})
            and v.normalizar_error({'id': 1, 'ficha_equipo': None})['ficha_equipo'] is None
            and 'ficha_equipo' not in v.normalizar_error(v.normalizar_error({'id': 1})),
            'normalizar_error: «ficha_equipo» solo si el servidor la conoce (también al normalizar dos veces)')

    # equipo.php
    srv, url = servidor()
    datos = srv.datos
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    destino = url.replace('admin.php', 'equipo.php')

    def equipo_php(campos):
        pedido = urllib.request.Request(destino, data=urllib.parse.urlencode(campos).encode(),
                                        headers={'User-Agent': 'CineCaptions/5.72'})
        try:
            with abridor.open(pedido, timeout=10) as r:
                return r.status, json.loads(r.read()), r.headers
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read()), error.headers

    act = act_de(datos, 'LAPTOP-HP-ML')   # (de Mariana, todavía sin ficha)
    lic = datos.licencia_real(act['licencia_id'])
    base = {'clave': lic['clave'], 'equipo': act['equipo'], 'version': '5.72', 'so': 'Windows 11 Pro 24H2',
            'resumen': 'GPU NVIDIA GeForce RTX 4070 · RAM 32 GB (libre 13,9 GB) · CPU AMD Ryzen 9 5900X (24 hilos) · Pantalla 3840×2160 al 150 %'}
    ficha = copy.deepcopy(FICHA_CONTRATO)
    ficha['so']['nombre'] = 'Windows\u0007 11‮ Pro'           # (un carácter de control y una marca de dirección)
    ficha['cpu']['nombre'] = 'R' * 500
    ficha['ra\u0000ro'] = {'‏': 'sin nombre', 'x' * 60: 1.5}
    codigo, r, _c = equipo_php(dict(base, ficha=json.dumps(ficha, ensure_ascii=False)))
    guardada = json.loads(act['ficha'] or 'null')
    revisar(codigo == 200 and r == {'ok': True} and act['ficha_resumen'] == base['resumen'], 'equipo.php: 200 y guarda la ficha y su línea')
    revisar(guardada['so']['nombre'] == 'Windows 11 Pro' and len(guardada['cpu']['nombre']) == 300
            and guardada['ra ro'] == {'x' * 40: 1.5} and guardada['gpus'] == FICHA_CONTRATO['gpus'],
            'equipo.php: la ficha se vuelve a codificar saneada (sin control ni marcas, textos de 300, campos de 40)')
    cuando = dt.datetime.strptime(act['ficha_cuando'], '%Y-%m-%d %H:%M:%S')
    revisar(abs((cuando - dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)).total_seconds()) < 120,
            'equipo.php: ficha_cuando en UTC')
    for campos, que in ((dict(base, ficha=''), 'sin la ficha'), ({'equipo': act['equipo'], 'ficha': '{}'}, 'sin la clave'),
                        (dict(base, equipo='', ficha='{}'), 'sin el equipo'), (dict(base, ficha='{"a": 1'), 'JSON roto'),
                        (dict(base, ficha='[1, 2]'), 'una lista en vez de un objeto'), (dict(base, ficha='"texto"'), 'un texto'),
                        (dict(base, ficha='{"a": NaN}'), 'NaN (PHP no lo acepta)'),
                        (dict(base, ficha='{"a":' * 9 + '1' + '}' * 9), 'más de 8 niveles'),
                        (dict(base, ficha=json.dumps({'relleno': 'x' * 16001})), 'de más de 16 000 bytes')):
        codigo, r, _c = equipo_php(campos)
        revisar(codigo == 400 and r['ok'] is False, f'equipo.php {que}: 400 ({r.get("error")})')
    codigo, r, _c = equipo_php(dict(base, ficha=json.dumps({'relleno': 'ñ' * 7990}, ensure_ascii=False)))   # (15 995 bytes)
    revisar(codigo == 200, 'equipo.php: el tope es de bytes (16 000), no de letras')
    codigo, r, _c = equipo_php(dict(base, equipo='equipo-que-no-existe', ficha='{}'))
    revisar(codigo == 404 and r['error'] == 'Este equipo no está activado con esa licencia.', 'equipo.php: un equipo sin activar, 404')
    codigo, r, _c = equipo_php(dict(base, clave='CC-AAAA-BBBB-CCCC-DDDD', ficha='{}'))
    revisar(codigo == 404, 'equipo.php: una licencia que no existe, 404')
    for _ in range(4):   # (2 ya entraron: 6 en total)
        codigo, r, _c = equipo_php(dict(base, ficha=json.dumps(FICHA_CONTRATO)))
    revisar(codigo == 200 and act['ficha_envios'] == 6, 'equipo.php: 6 en una hora, todas bien')
    codigo, r, cabeceras = equipo_php(dict(base, ficha='{"v": 1}'))
    espera = int(cabeceras.get('Retry-After') or 0)
    revisar(codigo == 429 and 60 <= espera <= 3600 and json.loads(act['ficha'])['cpu']['hilos'] == 24,
            f'equipo.php: la 7.ª en la hora, 429 con Retry-After ({espera} s) y la ficha de antes se queda')
    otro = act_de(datos, 'ESTUDIO-MARIANA')
    codigo, r, _c = equipo_php(dict(base, equipo=otro['equipo'], ficha=json.dumps(FICHA_CONTRATO)))
    revisar(codigo == 200, 'equipo.php: el tope es por equipo (otro de la misma licencia sí entra)')
    act['ficha_ventana'] = servidor_prueba._f(servidor_prueba._utc_ahora() - dt.timedelta(minutes=61))
    codigo, r, _c = equipo_php(dict(base, ficha=json.dumps(FICHA_CONTRATO)))
    revisar(codigo == 200 and act['ficha_envios'] == 1, 'equipo.php: pasada la hora, la cuenta vuelve a empezar')

    # admin.php: los equipos de detalle, equipo_ficha y la ficha en error_detalle
    c = v.ClienteApi(url, servidor_prueba.CLAVE)
    d = c.detalle(licencia_id=lic['id'])
    eq = {e['nombre_equipo'].split(' · ')[0]: e for e in d['equipos']}
    revisar(eq['LAPTOP-HP-ML']['con_ficha'] and eq['LAPTOP-HP-ML']['ficha_resumen'] == base['resumen']
            and eq['LAPTOP-HP-ML']['ficha_cuando'] == act['ficha_cuando'] and eq['ESTUDIO-MARIANA']['con_ficha'],
            'detalle: cada equipo con la línea de su ficha, cuándo llegó y si hay ficha')
    f = c.equipo_ficha(lic['id'], act['equipo'])
    revisar(f['ficha'] == FICHA_CONTRATO and f['resumen'] == base['resumen'] and f['cuando'] == act['ficha_cuando'],
            'equipo_ficha: la ficha entera, decodificada')
    sin = act_de(datos, 'DESKTOP-7Q2KD1F')
    revisar(c.equipo_ficha(sin['licencia_id'], sin['equipo']) is None, 'equipo_ficha de un equipo que todavía no la mandó: None')
    e = error_de(lambda: c.equipo_ficha(lic['id'], 'no-existe'))
    revisar(e is not None and e.codigo == 404 and e.mensaje == 'Ese equipo ya no está activado.', 'equipo_ficha de un equipo sin activar: 404')
    de_mariana = next(x for x in datos.errores if x['equipo'] == otro['equipo'] and x.get('captura'))
    de_carlos = next(x for x in datos.errores if x['equipo'] == sin['equipo'])
    revisar(c.error_detalle(de_mariana['id'])['ficha_equipo']['ficha']['cpu']['hilos'] == 24
            and c.error_detalle(de_carlos['id'])['ficha_equipo'] is None and 'ficha_equipo' in c.error_detalle(de_carlos['id']),
            'error_detalle: la ficha de ese equipo (o null si todavía no la mandó)')
    revisar(v.ClienteApi(url, servidor_prueba.CLAVE, solo_lectura=True).equipo_ficha(lic['id'], act['equipo']) is not None,
            'solo lectura (--captura): equipo_ficha sí')
    c.liberar_equipo(lic['id'], act['equipo'])
    e = error_de(lambda: c.equipo_ficha(lic['id'], act['equipo']))
    codigo, r, _c = equipo_php(dict(base, ficha='{}'))
    revisar(e is not None and e.codigo == 404 and codigo == 404, 'al liberar el equipo, su ficha se va con él (y ya no puede mandar otra)')
    srv.shutdown()

    # Un admin.php de la 5.71 (--sin-fichas) y uno de antes: nada se rompe y no se dice nada de fichas
    srv, url = servidor(sin_fichas=True)
    datos = srv.datos
    c = v.ClienteApi(url, servidor_prueba.CLAVE)
    act = act_de(datos, 'ESTUDIO-MARIANA')
    d = c.detalle(licencia_id=act['licencia_id'])
    e = error_de(lambda: c.equipo_ficha(act['licencia_id'], act['equipo']))
    de_mariana = next(x for x in datos.errores if x['equipo'] == act['equipo'])
    revisar(e is not None and e.desconocida and not any(x['con_ficha'] or x['ficha_resumen'] for x in d['equipos'])
            and 'ficha_equipo' not in c.error_detalle(de_mariana['id']),
            'admin.php de la 5.71: equipo_ficha desconocida, los equipos sin ficha y error_detalle sin «ficha_equipo»')
    destino = url.replace('admin.php', 'equipo.php')
    codigo, r, cabeceras = equipo_php({'clave': datos.licencia_real(act['licencia_id'])['clave'], 'equipo': act['equipo'],
                                       'ficha': '{}'})
    revisar(codigo == 503 and cabeceras.get('Retry-After') == '3600', 'equipo.php sin las columnas: 503 con Retry-After')
    srv.shutdown()

    # La ventana: la pestaña «Cliente y equipo» del error y «Ficha» en los equipos de la licencia
    aplicacion()
    srv, url = servidor()
    datos = srv.datos
    w = ventana(url, mostrar=True)
    w.ir_a('errores')
    w.vista_errores.poner('lista')
    w.filtro_err.poner('todos')
    esperar(lambda: quieto(w) and w.proxy_err.rowCount() == 5, 'Errores, todos')
    mariana = act_de(datos, 'ESTUDIO-MARIANA')
    fila = elegir_error(w, lambda x: x['equipo'] == mariana['equipo'] and x['titulo'].startswith('No se pudieron colocar'))
    pe = w.panel_error
    pe.btn_pestana['cliente'].click()
    fe = pe.ficha_equipo
    pares = {pe.ficha._grid.itemAtPosition(n, 0).widget().text(): pe.ficha._grid.itemAtPosition(n, 1).widget().text()
             for n in range(pe.ficha._grid.rowCount()) if pe.ficha._grid.itemAtPosition(n, 0)}
    revisar(pe.pila.currentIndex() == 2 and fe.isVisibleTo(pe) and fe.titulos[:5] == ['Ficha del equipo', 'Sistema', 'Procesador',
                                                                                         'Memoria', 'Tarjetas gráficas']
            and 'Revisión' in fe.titulos and 'Otros datos' in fe.titulos and 'RTX 3060' in pares.get('Al fallar', ''),
            '«Cliente y equipo»: la línea del momento del error («Al fallar») y debajo la ficha completa del equipo')
    revisar([p[:2] for p in fe.puntos] == [(v.PELIGRO, 'Falta'), (v.AVISO, 'Aviso'), (v.EXITO, 'Bien'), (v.EXITO, 'Bien')],
            'la revisión con su punto de color: lo que falta primero, después los avisos y lo que está bien')
    revisar(not pe.scroll.widget().grab().isNull(), 'la pestaña con la ficha se dibuja')
    hijos = len(fe.findChildren(v.QLabel))
    w._cargar_error()
    esperar(lambda: quieto(w), 'recargar el error')
    revisar(len(fe.findChildren(v.QLabel)) == hijos, 'al recargar el error con la misma ficha no se rearma')
    carlos = act_de(datos, 'DESKTOP-7Q2KD1F')
    elegir_error(w, lambda x: x['equipo'] == carlos['equipo'])
    revisar(pe.pila.currentIndex() == 2 and fe.isVisibleTo(pe) and fe.titulos == ['Ficha del equipo']
            and any('todavía no mandó su ficha' in l.text() for l in fe.findChildren(v.QLabel) if l.isVisibleTo(fe)),
            'un equipo que todavía no mandó su ficha: lo dice (y la pestaña elegida se queda)')
    apretar(w, pe.btn_copiar, 'copiar informe')
    elegir_error(w, lambda x: x['equipo'] == mariana['equipo'] and x['titulo'].startswith('No se pudieron colocar'))
    apretar(w, pe.btn_copiar, 'copiar informe con ficha')
    copiado = v.QGuiApplication.clipboard().text()
    revisar('Al fallar: GPU NVIDIA GeForce RTX 3060' in copiado and 'Ficha del equipo: GPU NVIDIA GeForce RTX 3060 · RAM 16 GB' in copiado,
            'Copiar informe: también la línea del momento y la de la ficha')

    # Los equipos de la licencia: su línea y «Ficha» (solo si la mandó)
    w.ir_a('ventas')
    esperar(lambda: quieto(w), 'Ventas')
    elegir(w, w.tabla_v, lambda x: x['nombre'] == 'Mariana López')
    filas_eq = {f.equipo['nombre_equipo'].split(' · ')[0]: f for f in filas_equipo(w)}
    con, sin_f = filas_eq['ESTUDIO-MARIANA'], filas_eq['LAPTOP-HP-ML']
    revisar(con.resumen.texto() == mariana['ficha_resumen'] and con.resumen.isVisibleTo(con) and con.btn_ficha.isVisibleTo(con)
            and not sin_f.resumen.isVisibleTo(sin_f) and not sin_f.btn_ficha.isVisibleTo(sin_f),
            'cada equipo con la línea de su ficha y «Ficha»; el que no la mandó, sin nada')
    antes = len(srv.acciones_recibidas)
    apretar(w, con.btn_ficha, 'Ficha del equipo')
    esperar(lambda: w.dialogo_ficha is not None and w.dialogo_ficha.isVisible(), 'la ficha del equipo')
    dlg = w.dialogo_ficha
    revisar(srv.acciones_recibidas[antes:] == ['equipo_ficha'] and dlg.titulo.text() == 'ESTUDIO-MARIANA'
            and dlg.ficha.titulos[:3] == ['Sistema', 'Procesador', 'Memoria'] and len(dlg.ficha.puntos) == 4
            and dlg.width() == v.DialogoFicha.ANCHO and 360 <= dlg.height() <= 820
            and not w.panel._ocupado and w._acciones == 0,
            '«Ficha»: pide equipo_ficha y abre la ficha completa en su ventana (sin ocupar el panel)')
    dlg.btn_copiar.click()
    copiado = v.QGuiApplication.clipboard().text()
    revisar(copiado.startswith('ESTUDIO-MARIANA · Mariana López · CC-7K2M-Q9XA-4HBR-T3WZ') and 'TARJETAS GRÁFICAS' in copiado
            and 'Falta: Quedan 8,4 GB libres en C:' in copiado and w.aviso.texto.text() == 'Ficha copiada',
            'Copiar ficha: el equipo, el cliente y cada sección como texto')
    revisar(not dlg.grab().isNull(), 'la ventana de la ficha se dibuja')
    dlg.accept()
    esperar(lambda: w.dialogo_ficha is None, 'cerrar la ficha')
    datos.activaciones = [a for a in datos.activaciones if a is not mariana]   # (lo liberaron desde otro lado)
    w.mensajes.clear()
    con.btn_ficha.click()
    esperar(lambda: quieto(w) and w.mensajes, 'ficha de un equipo ya liberado')
    revisar(bool(w.mensajes) and w.mensajes[0][0] == 'No se pudo cargar la ficha' and 'ya no está activado' in w.mensajes[0][1]
            and w.dialogo_ficha is None, 'un equipo que ya se liberó: lo dice (404) y no abre nada')
    w.close()
    srv.shutdown()

    # Con el admin.php de la 5.71: ni la ficha en el error ni «Ficha» en los equipos
    srv, url = servidor(sin_fichas=True)
    datos = srv.datos
    w = ventana(url, mostrar=True)
    w.ir_a('errores')
    w.vista_errores.poner('lista')
    w.filtro_err.poner('todos')
    esperar(lambda: quieto(w) and w.proxy_err.rowCount() == 5, 'Errores con el admin.php de la 5.71')
    mariana = act_de(datos, 'ESTUDIO-MARIANA')
    elegir_error(w, lambda x: x['equipo'] == mariana['equipo'])
    revisar(not w.panel_error.ficha_equipo.isVisibleTo(w.panel_error), 'admin.php de la 5.71: el error sin la ficha (ni el aviso)')
    w.ir_a('ventas')
    esperar(lambda: quieto(w), 'Ventas')
    elegir(w, w.tabla_v, lambda x: x['nombre'] == 'Mariana López')
    revisar(all(not f.btn_ficha.isVisibleTo(f) and not f.resumen.isVisibleTo(f) for f in filas_equipo(w)),
            'admin.php de la 5.71: los equipos sin «Ficha»')
    w.close()
    srv.shutdown()


# ------------------------------------------------------------------ 12. Las dos capturas del error (2.5)
def prueba_dos_capturas():
    print('Las dos capturas del error (2.5, CineCaptions 5.73): la pantalla entera y la ventana de CineCaptions')
    import urllib.error
    import urllib.request
    from PySide6.QtTest import QTest

    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def errores_php(url, campos, archivos):
        """errores.php en multipart, como lo manda CineCaptions 5.73 (los archivos con su campo: captura_/ventana_<firma>)."""
        limite = 'prueba573'
        partes = []
        for k, val in campos.items():
            partes += [f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n'.encode(), val.encode(), b'\r\n']
        for k, contenido in archivos.items():
            partes += [f'--{limite}\r\nContent-Disposition: form-data; name="{k}"; filename="{k[:8]}.png"\r\n'
                       'Content-Type: image/png\r\n\r\n'.encode(), contenido, b'\r\n']
        partes.append(f'--{limite}--\r\n'.encode())
        pedido = urllib.request.Request(url.replace('admin.php', 'errores.php'), data=b''.join(partes),
                                        headers={'User-Agent': 'CineCaptions/5.73',
                                                 'Content-Type': f'multipart/form-data; boundary={limite}'})
        try:
            with abridor.open(pedido, timeout=10) as respuesta:
                return respuesta.status, json.loads(respuesta.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def un_error(n, **extra):
        return dict({'firma': f'{n:040x}', 'nivel': 'error', 'titulo': f'Prueba {n}', 'mensaje': f'Fallo de prueba {n}.'}, **extra)

    def por_firma(datos, n):
        return next(x for x in datos.errores if x['firma'] == f'{n:040x}')

    png_p = servidor_prueba._png_demo(64, 36)
    png_v = servidor_prueba._png_demo(48, 30, ventana=True)

    # Funciones sueltas: lo que manda cada servidor
    e = v.normalizar_error({'id': 1, 'con_captura': True, 'con_ventana': '1'})
    revisar(e['con_captura'] and e['con_ventana'] and e['captura_ventana'] is None, 'normalizar: con_ventana en la lista')
    e = v.normalizar_error({'id': 1, 'captura': None, 'con_ventana': True,
                            'captura_ventana': {'tipo': 'image/jpeg', 'ancho': '800', 'alto': '520', 'bytes': '9', 'de': 'ventana'}})
    revisar(not e['con_captura'] and e['con_ventana'] and e['captura_ventana']['ancho'] == 800,
            'normalizar: solo la de la ventana (error_detalle)')
    e = v.normalizar_error({'id': 1, 'con_captura': True})
    revisar(e['con_captura'] and not e['con_ventana'], 'un admin.php de la 5.72 (sin con_ventana): solo la de siempre')
    revisar(v.nombre_captura('pantalla', {'de': 'pantalla'}) == 'Pantalla completa'
            and v.nombre_captura('pantalla', {'de': 'ventana'}) == 'Ventana de CineCaptions'
            and v.nombre_captura('ventana', None, True) == 'Ventana de CineCaptions'
            and v.nombre_captura('pantalla', {'de': None}) == 'Captura' and v.nombre_captura('pantalla', None, True) == 'Pantalla completa',
            'los rótulos (la de siempre, en Mac, es la ventana; sin «de», «Captura» como antes)')

    # La API: la lista, el detalle y error_captura con y sin «cual»
    srv, url = servidor()
    datos = srv.datos
    c = v.ClienteApi(url, servidor_prueba.CLAVE)
    dos = next(x for x in datos.errores if x.get('ventana'))
    filas = c.errores()['errores']
    f = next(x for x in filas if x['id'] == dos['id'])
    revisar(f['con_captura'] and f['con_ventana'] and sum(x['con_ventana'] for x in filas) == 1,
            'errores: con_captura y con_ventana en la lista')
    d = c.error_detalle(dos['id'])
    revisar(d['con_captura'] and d['con_ventana'] and d['captura']['de'] == 'pantalla' and d['captura_ventana']['ancho'] == 800
            and d['captura_ventana']['de'] == 'ventana', 'error_detalle: los datos de las dos')
    p, pp, pv = c.error_captura(dos['id']), c.error_captura(dos['id'], 'pantalla'), c.error_captura(dos['id'], 'ventana')
    revisar(p['ancho'] == pp['ancho'] == 960 and pv['ancho'] == 800 and pv['alto'] == 520 and pv['cual'] == 'ventana'
            and not pv['imagen'].isNull(), 'error_captura: sin «cual» y con «pantalla», la de siempre; con «ventana», la de la ventana')
    r = c.llamar('error_captura', id=dos['id'])   # (la petición de la app 2.4 instalada, tal cual)
    revisar(r['captura']['ancho'] == 960 and r['captura']['de'] == 'pantalla' and isinstance(r['captura']['base64'], str),
            'la app 2.4 (sin «cual»): la de la pantalla, como siempre')
    e = error_de(lambda: c.llamar('error_captura', id=dos['id'], cual='otra'))
    revisar(e is not None and e.codigo == 400 and e.mensaje == 'Esa captura no se conoce.', 'error_captura con un «cual» que no existe: 400')
    sin = next(x for x in datos.errores if not x.get('captura') and not x.get('ventana'))
    e = error_de(lambda: c.error_captura(sin['id'], 'ventana'))
    revisar(e is not None and e.codigo == 404 and 'ventana' in e.mensaje, 'error_captura de la ventana en un error que no la tiene: 404')

    # errores.php: las dos, solo la pantalla, solo la ventana, imágenes que no sirven y una que reemplaza a la anterior
    lic = datos.licencia_real(dos['licencia_id'])
    base = {'clave': lic['clave'], 'equipo': dos['equipo'], 'equipo_datos': 'GPU X · RAM 8 GB'}

    def mandar(errores, archivos):
        return errores_php(url, dict(base, errores=json.dumps(errores)), archivos)

    fi = {n: f'{n:040x}' for n in range(1, 6)}
    codigo, r = mandar([un_error(1, captura='pantalla', ventana=True)], {'captura_' + fi[1]: png_p, 'ventana_' + fi[1]: png_v})
    e1 = por_firma(datos, 1)
    revisar(codigo == 200 and r == {'ok': True, 'guardados': 1, 'capturas': 1, 'ventanas': 1}
            and e1['captura']['ancho'] == 64 and e1['ventana']['ancho'] == 48 and e1['ventana']['de'] == 'ventana',
            f'errores.php: un error con las dos ({r})')
    codigo, r = mandar([un_error(2, captura='pantalla')], {'captura_' + fi[2]: png_p})
    revisar(codigo == 200 and r == {'ok': True, 'guardados': 1, 'capturas': 1, 'ventanas': 0} and not por_firma(datos, 2).get('ventana'),
            f'errores.php: solo la de la pantalla (como la 5.72) ({r})')
    codigo, r = mandar([un_error(3, ventana=True)], {'ventana_' + fi[3]: png_v})
    e3 = por_firma(datos, 3)
    revisar(codigo == 200 and r == {'ok': True, 'guardados': 1, 'capturas': 0, 'ventanas': 1}
            and not e3.get('captura') and e3['ventana']['alto'] == 30,
            f'errores.php: solo la de la ventana (la de la pantalla falló): se guarda igual ({r})')
    pequena = servidor_prueba._png_demo(8, 8)
    codigo, r = mandar([un_error(4, captura='pantalla', ventana=True), un_error(5, captura='pantalla', ventana=True)],
                       {'captura_' + fi[4]: b'esto no es una imagen', 'ventana_' + fi[4]: pequena,
                        'captura_' + fi[5]: png_p, 'ventana_' + fi[5]: png_v + b'\0' * 921600})
    revisar(codigo == 200 and r == {'ok': True, 'guardados': 2, 'capturas': 1, 'ventanas': 0}
            and not por_firma(datos, 4).get('captura') and not por_firma(datos, 4).get('ventana')
            and por_firma(datos, 5).get('captura') and not por_firma(datos, 5).get('ventana'),
            f'errores.php: una que no es imagen, una de 8×8 y una de más de 900 KB no se guardan (los errores sí) ({r})')
    filas = {x['id']: x for x in c.errores()['errores']}
    revisar(filas[e3['id']]['con_ventana'] and not filas[e3['id']]['con_captura'] and filas[e1['id']]['con_ventana']
            and not filas[por_firma(datos, 2)['id']]['con_ventana'] and not filas[por_firma(datos, 4)['id']]['con_captura'],
            'la lista dice cuál tiene cada error')
    e = error_de(lambda: c.error_captura(e3['id']))
    revisar(e is not None and e.codigo == 404 and c.error_captura(e3['id'], 'ventana')['alto'] == 30,
            'solo la de la ventana: sin «cual», 404; con «ventana», la imagen')
    otra_v = servidor_prueba._png_demo(40, 24, ventana=True)
    codigo, r = mandar([un_error(1, ventana=True)], {'ventana_' + fi[1]: otra_v})
    revisar(codigo == 200 and e1['ventana']['ancho'] == 40 and e1['captura']['ancho'] == 64 and e1['veces'] == 2,
            'la nueva de la ventana reemplaza a la anterior; la de la pantalla se queda')

    # El tope: como mucho 30 errores con captura por licencia (las dos del mismo error cuentan como uno)
    nuevos = list(range(100, 130))
    for tanda in (nuevos[:20], nuevos[20:]):
        codigo, r = mandar([un_error(n, captura='pantalla', ventana=True) for n in tanda],
                           {k: img for n in tanda for k, img in (('captura_' + f'{n:040x}', png_p), ('ventana_' + f'{n:040x}', png_v))})
    de_lic = [x for x in datos.errores if x['licencia_id'] == lic['id']]
    con = [x for x in de_lic if x.get('captura') or x.get('ventana')]
    revisar(codigo == 200 and len(con) == 30 and sum(bool(x.get('captura')) + bool(x.get('ventana')) for x in con) == 60
            and {x['firma'] for x in con} == {f'{n:040x}' for n in nuevos},
            'tope: 30 errores con captura (60 imágenes como mucho); a los más viejos se les quitan las dos')
    revisar(not dos.get('captura') and not dos.get('ventana') and not e1.get('ventana') and dos in datos.errores,
            'el tope quita las capturas, no el error')

    # Se borran con su error (FOREIGN KEY … ON DELETE CASCADE): al liberar el equipo se van el error y sus dos capturas
    ultimo = por_firma(datos, nuevos[-1])
    c.liberar_equipo(lic['id'], dos['equipo'])
    datos.ajustes['errores_limpieza'] = 0   # (limpiar_errores corre como mucho una vez por hora)
    c.errores()
    e_p = error_de(lambda: c.error_captura(ultimo['id']))
    e_v = error_de(lambda: c.error_captura(ultimo['id'], 'ventana'))
    revisar(not any(x['equipo'] == dos['equipo'] and x['licencia_id'] == lic['id'] for x in datos.errores)
            and e_p is not None and e_p.codigo == 404 and e_v is not None and e_v.codigo == 404,
            'al liberar el equipo se borran sus errores y las dos capturas de cada uno')
    srv.shutdown()

    # El admin.php de la 5.72 (--sin-ventanas): ignora «ventana_<firma>» y «cual»; la app no le pide la ventana
    srv, url = servidor(sin_ventanas=True)
    datos = srv.datos
    c = v.ClienteApi(url, servidor_prueba.CLAVE)
    crudas = c.llamar('errores')['errores']
    mariana = next(x for x in datos.errores if x.get('captura'))
    revisar(all('con_ventana' not in x for x in crudas) and not any(x['con_ventana'] for x in c.errores()['errores'])
            and not mariana.get('ventana'), 'admin.php de la 5.72: la lista sin con_ventana (para la app: no hay)')
    d = c.error_detalle(mariana['id'])
    revisar(d['con_captura'] and not d['con_ventana'] and d['captura_ventana'] is None, 'admin.php de la 5.72: el detalle con la de siempre')
    e = error_de(lambda: c.error_captura(mariana['id'], 'ventana'))
    revisar(e is not None and e.mensaje == v.FALTA_SERVIDOR and c.error_captura(mariana['id'])['ancho'] == 960,
            'admin.php de la 5.72: pedirle la ventana no da la de la pantalla como si fuera la ventana')
    lic = datos.licencia_real(mariana['licencia_id'])
    codigo, r = errores_php(url, {'clave': lic['clave'], 'equipo': mariana['equipo'],
                                  'errores': json.dumps([un_error(7, captura='pantalla', ventana=True)])},
                            {'captura_' + f'{7:040x}': png_p, 'ventana_' + f'{7:040x}': png_v})
    revisar(codigo == 200 and r == {'ok': True, 'guardados': 1, 'capturas': 1} and not por_firma(datos, 7).get('ventana'),
            f'errores.php de la 5.72: guarda la de siempre e ignora la de la ventana ({r})')
    srv.shutdown()

    # La ventana: las dos miniaturas lado a lado, cada una con su rótulo, su visor y «Guardar imagen…»
    aplicacion()
    srv, url = servidor()
    datos = srv.datos
    dos = next(x for x in datos.errores if x.get('ventana'))   # (el de este servidor, con las dos)
    solo_v = next(x for x in datos.errores if not x.get('captura') and not x.get('ventana'))
    solo_v['ventana'] = {'tipo': 'image/png', 'ancho': 48, 'alto': 30, 'bytes': len(png_v), 'de': 'ventana',
                         'creada': solo_v['ultima'], 'imagen': png_v}
    w = ventana(url, mostrar=True)
    w.ir_a('errores')
    w.vista_errores.poner('lista')
    w.filtro_err.poner('todos')
    esperar(lambda: quieto(w) and w.proxy_err.rowCount() == 5, 'Errores, todos')
    pe = w.panel_error
    cuadros = pe.cuadros_cap
    antes = len(srv.acciones_recibidas)
    fila = elegir_error(w, lambda x: x['id'] == dos['id'])
    (caja_p, rot_p, mini_p, lin_p), (caja_v, rot_v, mini_v, lin_v) = cuadros['pantalla'], cuadros['ventana']
    revisar(srv.acciones_recibidas[antes:].count('error_captura') == 2 and pe.btn_pestana['captura'].isVisible()
            and pe.pila.currentIndex() == 0, 'las dos se piden (en una tarea de la cola) y se abre la pestaña «Captura»')
    revisar(caja_p.isVisible() and caja_v.isVisible() and rot_p.isVisible() and rot_v.isVisible()
            and rot_p.text() == 'PANTALLA COMPLETA' and rot_v.text() == 'VENTANA DE CINECAPTIONS'
            and mini_p.imagen.width() == 960 and mini_v.imagen.width() == 800,
            'dos: «Pantalla completa» y «Ventana de CineCaptions», cada una con su imagen')
    revisar(caja_v.x() > caja_p.x() + caja_p.width() - 1 and caja_p.y() == caja_v.y() and abs(caja_p.width() - caja_v.width()) <= 1
            and mini_p.height() > 40 and mini_v.height() > 40, 'lado a lado, del mismo ancho y arriba')
    revisar(lin_p.text().startswith('960×540') and lin_v.text().startswith('800×520') and 'clic para ampliar' in lin_v.text()
            and not pe.cap_texto.isVisible(), 'debajo de cada una: su tamaño y «clic para ampliar» (el nombre ya va en el rótulo)')
    revisar(not pe.sec_cap.grab().isNull(), 'la pestaña con las dos se dibuja')
    abiertos = []
    exec_antes = v.VisorCaptura.exec
    v.VisorCaptura.exec = lambda self: abiertos.append(self) or 0   # (sin el bucle del diálogo)
    try:
        QTest.mouseClick(mini_v, v.Qt.MouseButton.LeftButton)
        QTest.mouseClick(mini_p, v.Qt.MouseButton.LeftButton)
        revisar(len(abiertos) == 2 and abiertos[0].imagen.width() == 800 and abiertos[1].imagen.width() == 960
                and abiertos[0].windowTitle().endswith('· Ventana de CineCaptions')
                and abiertos[1].windowTitle().endswith('· Pantalla completa'),
                'un clic en cada miniatura abre SU captura grande (el título dice cuál)')
        propuestos = []

        class DialogoArchivo:   # (en vez del de Windows: dice qué nombre se propuso y guarda donde dice la prueba)
            @staticmethod
            def getSaveFileName(_padre, _titulo, propuesto, _filtro):
                propuestos.append(Path(propuesto).name)
                return str(TEMPORAL / f'guardada_{len(propuestos)}.png'), ''

        dialogo_antes, v.QFileDialog = v.QFileDialog, DialogoArchivo
        try:
            abiertos[0]._guardar()
            abiertos[1]._guardar()
        finally:
            v.QFileDialog = dialogo_antes
        g1, g2 = v.QImage(str(TEMPORAL / 'guardada_1.png')), v.QImage(str(TEMPORAL / 'guardada_2.png'))
        revisar(propuestos == ['captura_error_ventana.png', 'captura_error.png'] and (g1.width(), g1.height()) == (800, 520)
                and (g2.width(), g2.height()) == (960, 540),
                '«Guardar imagen…»: cada una con su nombre (la de la ventana, «captura_error_ventana.png») y entera')
        for d in abiertos:
            d.deleteLater()
        abiertos.clear()

        # Una sola (solo la de la ventana): como antes, a todo lo ancho, sin rótulo y con su nombre en la línea
        antes = len(srv.acciones_recibidas)
        elegir_error(w, lambda x: x['id'] == solo_v['id'])
        revisar(srv.acciones_recibidas[antes:].count('error_captura') == 1 and caja_v.isVisible() and not caja_p.isVisible()
                and not rot_v.isVisible() and lin_v.text().startswith('Ventana de CineCaptions · 48×30')
                and caja_v.width() > pe.sec_cap.width() * 0.9 and pe.pila.currentIndex() == 0,
                'una sola (la de la ventana): a todo lo ancho, sin rótulo, su nombre en la línea (como la 2.4)')
        QTest.mouseClick(mini_v, v.Qt.MouseButton.LeftButton)
        revisar(len(abiertos) == 1 and abiertos[0].imagen.width() == 48 and not abiertos[0].windowTitle().endswith('CineCaptions'),
                'una sola: el visor como antes')
        # Una sola de la pantalla (un error de un cliente con CineCaptions 5.72)
        solo_p = next(x for x in datos.errores if x['id'] not in (dos['id'], solo_v['id']) and x['licencia_id'] == dos['licencia_id'])
        solo_p['captura'] = dict(dos['captura'])
        w.actualizar_todo()
        esperar(lambda: quieto(w), 'actualizar')
        elegir_error(w, lambda x: x['id'] == solo_p['id'])
        revisar(caja_p.isVisible() and not caja_v.isVisible() and not rot_p.isVisible()
                and lin_p.text().startswith('Pantalla completa · 960×540'), 'una sola (la de la pantalla): como siempre')

        # La lista todavía no sabía de la de la ventana (llegó después): al llegar el detalle se piden las dos
        solo_p['ventana'] = dict(dos['ventana'])
        antes = len(srv.acciones_recibidas)
        elegir_error(w, lambda x: x['id'] == dos['id'])
        elegir_error(w, lambda x: x['id'] == solo_p['id'])
        revisar(srv.acciones_recibidas[antes:].count('error_captura') in (2, 3) and caja_p.isVisible() and caja_v.isVisible()
                and mini_v.isVisible() and rot_v.isVisible(), 'si el detalle dice que ya tiene la de la ventana, se piden las dos')

        # Las dos, pero la de la ventana llega dañada: se ve la que llegó y la otra dice por qué
        dos['ventana'], buena = dict(dos['ventana'], imagen=b'no es una imagen'), dos['ventana']
        w.__dict__.get('_capturas', {}).pop(dos['id'], None)
        elegir_error(w, lambda x: x['id'] == dos['id'])
        revisar(caja_p.isVisible() and caja_v.isVisible() and mini_p.isVisible() and not mini_v.isVisible()
                and lin_v.text() == 'No se pudo cargar esta captura. La captura llegó dañada.' and rot_v.isVisible()
                and not w.mensajes, 'si una de las dos falla: la otra se ve y la que falta dice por qué (sin ventanas de error)')
        dos['ventana'] = buena
        elegir_error(w, lambda x: x['id'] == solo_v['id'])
        elegir_error(w, lambda x: x['id'] == dos['id'])
        revisar(mini_v.isVisible() and mini_v.imagen.width() == 800, 'la que falló no quedó guardada: al volver se pide otra vez')
        # Volver a uno ya visto no pide nada
        elegir_error(w, lambda x: x['id'] == solo_v['id'])
        antes = len(srv.acciones_recibidas)
        elegir_error(w, lambda x: x['id'] == dos['id'])
        revisar(srv.acciones_recibidas[antes:].count('error_captura') == 0 and mini_v.imagen.width() == 800,
                'las dos quedan en memoria: volver al error no las pide otra vez')
    finally:
        v.VisorCaptura.exec = exec_antes
    w.close()
    srv.shutdown()

    # Con el admin.php de la 5.72 la ventana enseña solo la de siempre, como la 2.4
    srv, url = servidor(sin_ventanas=True)
    w = ventana(url, mostrar=True)
    w.ir_a('errores')
    w.vista_errores.poner('lista')
    w.filtro_err.poner('todos')
    esperar(lambda: quieto(w) and w.proxy_err.rowCount() == 5, 'Errores con el admin.php de la 5.72')
    antes = len(srv.acciones_recibidas)
    elegir_error(w, lambda x: x['con_captura'])
    pe = w.panel_error
    revisar(srv.acciones_recibidas[antes:].count('error_captura') == 1 and pe.cuadros_cap['pantalla'][0].isVisible()
            and not pe.cuadros_cap['ventana'][0].isVisible() and pe.cuadros_cap['pantalla'][3].text().startswith('Pantalla completa'),
            'admin.php de la 5.72: una sola captura, como en la 2.4')
    w.close()
    srv.shutdown()


# ------------------------------------------------------------------ 13. El menú: la isla de arriba (2.7)
def esperar_isla(w, segundos=3):
    """Hasta que la isla se asienta (sus resortes van con un QTimer de ~60 fps que se apaga solo)."""
    app = aplicacion()
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        app.processEvents()
        if not w.barra.moviendose():
            for _ in range(3):
                app.processEvents()
            return True
        time.sleep(0.005)
    return False


def pixeles(imagen, rect, condicion):
    """Cuántos píxeles de ese rectángulo de la imagen cumplen la condición (r, g, b)."""
    r = rect.intersected(imagen.rect())
    return sum(1 for x in range(r.left(), r.right() + 1) for y in range(r.top(), r.bottom() + 1)
               if condicion(*imagen.pixelColor(x, y).getRgb()[:3]))


def rojo(r, g, b):
    return r > 200 and g < 140 and b < 140


def naranja(r, g, b):
    return r > 210 and 120 < g < 200 and b < 140


def en_la_isla(w):
    """Que nada se salga ni tape: cada ítem dentro de la isla, la isla dentro de la ventana y sin tocar el título (su
    texto), «Exportar CSV» o «Informe completo» (2.10, en Errores; si se ven) ni el subtítulo."""
    isla, raiz = w.barra, w.centralWidget()
    g = isla.geometry()
    dentro = all(isla.rect().contains(b.geometry()) for b in [isla.logo, *isla.botones.values(), isla.btn_config])
    t = w.lbl_titulo
    texto = QRect(t.mapTo(raiz, v.QPoint(0, 0)), v.QSize(v.QFontMetrics(t.font()).horizontalAdvance(t.text()), t.height()))
    botones = [QRect(e.mapTo(raiz, v.QPoint(0, 0)), e.size()) for e in (w.btn_exportar, w.btn_informe_err) if e.isVisible()]
    sub = w.lbl_sub.mapTo(raiz, v.QPoint(0, 0)).y()
    return (dentro and raiz.rect().contains(g) and not g.intersects(texto) and not any(g.intersects(b) for b in botones)
            and sub >= g.bottom())


def prueba_isla():
    print('El menú: la isla de arriba (2.7)')
    from PySide6.QtGui import QEnterEvent
    from PySide6.QtTest import QTest
    aplicacion()
    srv, url = servidor()
    w = ventana(url, mostrar=True)
    isla, raiz = w.barra, w.centralWidget()
    revisar(esperar_isla(w), 'la isla se asienta sola (el reloj de los resortes se apaga)')
    claves = [c for c, _i, _t in v.PAGINAS]
    revisar(isinstance(isla, v.IslaNav) and not hasattr(v, 'BarraLateral') and isla.parentWidget() is raiz
            and raiz.childAt(isla.geometry().center()) in [isla, *isla.findChildren(v.QAbstractButton)],
            'la barra lateral se fue: el menú es la isla, flotando encima del contenido')
    revisar(list(isla.botones) == claves and [b.texto for b in isla.botones.values()] == [t for _c, _i, t in v.PAGINAS]
            and isla.btn_config.texto == 'Configuración' and all(b.isVisible() for b in isla.botones.values())
            and isla.btn_config.isVisible(), 'los 7 ítems (Resumen … Errores, con Cupones) + Configuración')
    centro = abs(isla.geometry().center().x() - raiz.rect().center().x()) <= 1
    revisar(w.width() == 1440 and isla.nivel == 'expandida' and centro and isla.y() == v.IslaNav.ARRIBA
            and all(b.abierto and b.width() == round(b.ancho_abierto()) for b in isla.botones.values()),
            'a 1440 px: arriba al centro y TODAS las páginas con su nombre (la propuesta A expandida)')
    revisar(en_la_isla(w), 'a 1440 px nada se sale ni tapa el título ni el subtítulo')
    revisar(w.lbl_version.text() == f'Versión {v.VERSION}' and w.lbl_version.isVisible(),
            'la versión de la app, que estaba abajo en la barra lateral, está en la barra de estado')
    # Los contadores: Errores en rojo, Versiones en naranja, los demás neutros (como en la barra de antes)
    b_err, b_ver = isla.botones['errores'], isla.botones['versiones']
    revisar(b_err.contador == 3 and b_err.color_contador == v.PELIGRO and b_ver.contador == 9
            and b_ver.color_contador == v.AVISO and isla.botones['ventas'].color_contador is None
            and isla.botones['avisos'].contador is None, 'contadores: Errores rojo, Versiones naranja y Avisos sin contador')
    imagen = isla.grab().toImage()
    revisar(pixeles(imagen, b_err.geometry(), rojo) > 15 and pixeles(imagen, b_ver.geometry(), naranja) > 15
            and pixeles(imagen, isla.botones['ventas'].geometry(), rojo) == 0,
            'y se dibujan así: el número de Errores en rojo y el de Versiones en naranja')
    # Un clic en cada página: la abre y la pastilla se DESLIZA (resorte) hasta quedar justo en el ítem
    for clave in claves[1:] + claves[:1]:
        b = isla.botones[clave]
        desde = isla.rect_pastilla().x()
        QTest.mouseClick(b, v.Qt.MouseButton.LeftButton)
        hasta = isla._pastilla[0].objetivo
        fin = time.monotonic() + 0.06
        while time.monotonic() < fin:
            aplicacion().processEvents()
        a_medias = isla.rect_pastilla().x()
        esperar_isla(w)
        p = isla.rect_pastilla()
        revisar(w.pagina == clave and b.isChecked() and w.lbl_titulo.text() == v.TITULOS.get(clave, b.texto)
                and min(desde, hasta) < a_medias < max(desde, hasta)
                and abs(p.x() - b.x()) <= 1 and abs(p.width() - b.width()) <= 1 and p.height() == b.height(),
                f'clic en «{b.texto}»: abre la página y la pastilla se desliza hasta quedar en el ítem')
    # Lo demás que hacía la barra: Ctrl+1…6, el logo lleva al Resumen y la configuración abre su menú
    atajos = {a.shortcut().toString(): a for a in w.actions()}
    atajos['Ctrl+3'].trigger()
    esperar_isla(w)
    revisar(w.pagina == 'versiones' and abs(isla.rect_pastilla().x() - b_ver.x()) <= 1,
            'Ctrl+3 abre Versiones y la pastilla va con ella')
    QTest.mouseClick(isla.logo, v.Qt.MouseButton.LeftButton)
    esperar_isla(w)
    revisar(w.pagina == 'resumen', 'el logo lleva al Resumen')
    QTest.mouseClick(isla.btn_config, v.Qt.MouseButton.LeftButton)
    m = v.QApplication.activePopupWidget()
    textos = [a.text() for a in m.actions() if not a.isSeparator()] if isinstance(m, v.QMenu) else None
    arriba = m.geometry().top() if m is not None else -1
    revisar(textos == ['Cambiar clave…', f'Acerca de {v.APP}', 'Salir'] and w.pagina == 'resumen'
            and arriba >= isla.mapToGlobal(v.QPoint(0, isla.height())).y(),
            'Configuración abre su menú (clave, «Acerca de», salir) debajo de la isla, sin cambiar de página')
    if m is not None:
        m.close()
    v.QApplication.sendPostedEvents(None, v.QEvent.Type.DeferredDelete)
    revisar(m is not None and not shiboken6.isValid(m), 'al cerrarse, el menú se borra (no queda colgado de la ventana)')
    v.QApplication.sendEvent(isla.btn_config, QEnterEvent(v.QPointF(5, 5), v.QPointF(5, 5), v.QPointF(5, 5)))
    esperar_isla(w)
    revisar(isla.btn_config.hover.x == 1.0 and not isla.btn_config.isCheckable(),
            'al pasar el mouse, Configuración se realza y su ícono gira (resorte del mouse asentado)')
    v.QApplication.sendEvent(isla.btn_config, v.QEvent(v.QEvent.Type.Leave))
    esperar_isla(w)
    # Angosta (1100 px, el mínimo): se cierran los nombres de las otras páginas; el contador queda en un globito
    w.ir_a('ventas')
    w.resize(1100, 720)
    revisar(esperar_isla(w) and isla.nivel == 'compacta', 'a 1100 px la isla se cierra sola (con su resorte)')
    abiertas = [c for c, b in isla.botones.items() if b.abierto]
    revisar(abiertas == ['ventas'] and all(b.width() == 40 and b.alfa.x == 0 and b.toolTip() == b.texto
                                           for c, b in isla.botones.items() if c != 'ventas'),
            'a 1100 px: solo la página elegida con su nombre; las demás, ícono (y el nombre al pasar el mouse)')
    imagen = isla.grab().toImage()
    revisar(pixeles(imagen, b_err.geometry().adjusted(0, -4, 12, 0), rojo) > 15
            and pixeles(imagen, b_ver.geometry().adjusted(0, -4, 12, 0), naranja) > 15,
            'cerradas, Errores y Versiones llevan su número en un globito rojo y naranja')
    revisar(w.btn_exportar.isVisible() and en_la_isla(w), 'a 1100 px en Ventas nada se sale ni tapa el título ni «Exportar CSV»')
    fuera = []
    for clave in claves:
        w.ir_a(clave)
        esperar_isla(w)
        if not en_la_isla(w) or isla.botones[clave].width() != round(isla.botones[clave].ancho_abierto()):
            fuera.append(clave)
    revisar(not fuera, f'a 1100 px, en cada página, la elegida abre su nombre y nada se sale ni se tapa {fuera}')
    # La captura de la ventana (--captura) incluye la isla con su pastilla violeta
    imagen = w.grab().toImage()
    pa = isla.rect_pastilla()
    color = imagen.pixelColor(isla.x() + round(pa.center().x()), isla.y() + 7)
    revisar(color.blue() > color.red() and color.blue() > 60, f'la captura de la ventana incluye la isla ({color.name()})')
    w.resize(1440, 900)
    revisar(esperar_isla(w) and isla.nivel == 'expandida' and all(b.abierto for b in isla.botones.values()),
            'de vuelta a 1440 px, todas las páginas abren su nombre otra vez')
    # (se borra ya, con Python vivo: el clic de QTest dejó un botón «bajo el mouse» y, si la ventana se borrara al
    # salir de Python, Qt le mandaría su Leave cuando ya no hay quién lo atienda)
    w.close()
    w.deleteLater()
    v.QApplication.sendPostedEvents(None, v.QEvent.Type.DeferredDelete)
    srv.shutdown()


def prueba_cupones():
    print('Cupones de descuento (2.8): acciones, página Cupones y el cupón de cada venta')
    srv, url = servidor()
    datos = srv.datos
    c = v.ClienteApi(url, servidor_prueba.CLAVE)
    r = c.cupones()
    por = {x['codigo']: x for x in r['cupones']}
    revisar(r['precio'] == 2900 and r['moneda'] == 'USD' and r['hoy'] == dt.date.today().isoformat()
            and list(por) == ['BLACKFRIDAY', 'AMIGOS100', 'NAVIDAD', 'LANZAMIENTO'], 'cupones: los 4, el más nuevo primero, con el precio')
    lz, nv, am, bf = por['LANZAMIENTO'], por['NAVIDAD'], por['AMIGOS100'], por['BLACKFRIDAY']
    revisar(lz['estado'] == 'vencido' and lz['usos'] == 3 and lz['ingresos'] == 5700 and lz['descontado'] == 3000
            and lz['ultima_venta'] and lz['usos_max'] is None and lz['nota'] == 'Precio de lanzamiento en redes',
            'LANZAMIENTO: vencido, 3 ventas de $19 (−$10 cada una), sin tope')
    revisar(nv['estado'] == 'activo' and nv['usos'] == 0 and nv['precio_final'] == 2320 and nv['usos_max'] == 50
            and nv['enlace'] == 'https://cinecaptions.shop/?cupon=NAVIDAD' and isinstance(nv['activo'], bool),
            'NAVIDAD: activo, queda en $23.20, tope 50 y su enlace')
    revisar(am['precio_final'] == 0 and v.texto_descuento(am['porcentaje']) == 'Gratis' and bf['estado'] == 'pausado'
            and not bf['activo'], 'AMIGOS100 regala la licencia; BLACKFRIDAY está pausado')
    revisar(v.texto_usos(nv) == '0 de 50' and v.texto_usos(lz) == '3', 'usos: «0 de 50» y, sin tope, «3»')
    ventas_lz = c.ventas(buscar='lanzamiento')
    revisar(len(ventas_lz) == 3 and all(x['cupon'] == 'LANZAMIENTO' and x['descuento'] == 1000 for x in ventas_lz)
            and all(x['cupon'] is None for x in c.ventas() if x['monto'] != 1900),
            'ventas: cada una con su cupón (y se buscan por el código)')
    pid = ventas_lz[0]['id']
    d = c.detalle(pedido_id=pid)
    revisar(d['pedido']['cupon'] == 'LANZAMIENTO' and d['pedido']['descuento'] == 1000, 'detalle: el pedido con su cupón')

    # Crear
    nuevo = c.cupon_crear('verano 25', 15, usos_max=10, vence=(dt.date.today() + dt.timedelta(days=5)).isoformat(),
                          nota='  Prueba  ')
    revisar(nuevo['codigo'] == 'VERANO25' and nuevo['porcentaje'] == 15 and nuevo['estado'] == 'activo' and nuevo['usos'] == 0
            and nuevo['precio_final'] == 2465 and nuevo['nota'] == 'Prueba' and nuevo['usos_max'] == 10,
            'cupon_crear: en mayúsculas y sin espacios, queda en $24.65')
    for datos_malos, codigo_http, texto in (
            ({'codigo': 'VERANO25', 'porcentaje': 10}, 409, 'Ya existe'),
            ({'codigo': 'X', 'porcentaje': 10}, 400, 'El código'),
            ({'codigo': 'CON ESPACIO!', 'porcentaje': 10}, 400, 'El código'),
            ({'codigo': 'OTRO', 'porcentaje': 0}, 400, 'de 1 a 100'),
            ({'codigo': 'OTRO', 'porcentaje': 101}, 400, 'de 1 a 100'),
            ({'codigo': 'OTRO'}, 400, 'Falta el descuento'),
            ({'codigo': 'OTRO', 'porcentaje': 10, 'vence': '2026-02-30'}, 400, 'fecha'),
            ({'codigo': 'OTRO', 'porcentaje': 10, 'usos_max': -3}, 400, 'tope')):
        e = error_de(lambda: c.llamar('cupon_crear', **datos_malos))
        revisar(e is not None and e.codigo == codigo_http and texto in e.mensaje, f'cupon_crear {datos_malos}: {codigo_http}')
    # Editar, pausar y borrar
    p = c.cupon_editar(nuevo['id'], activo=False)
    revisar(p['estado'] == 'pausado' and not p['activo'], 'cupon_editar activo=false: pausado')
    p = c.cupon_editar(nuevo['id'], activo=True, porcentaje=100, usos_max=None, vence=None)
    revisar(p['estado'] == 'activo' and p['precio_final'] == 0 and p['usos_max'] is None and p['vence'] is None,
            'cupon_editar: 100 %, sin tope y sin fecha')
    e = error_de(lambda: c.cupon_editar(nuevo['id']))
    revisar(e is not None and e.codigo == 400, 'cupon_editar sin cambios: 400')
    e = error_de(lambda: c.cupon_editar(999, activo=False))
    revisar(e is not None and e.codigo == 404, 'cupon_editar de uno que no existe: 404')
    revisar(c.cupon_borrar(nuevo['id']) == nuevo['id'] and 'VERANO25' not in [x['codigo'] for x in c.cupones()['cupones']],
            'cupon_borrar: ya no está')
    e = error_de(lambda: c.cupon_borrar(nuevo['id']))
    revisar(e is not None and e.codigo == 404, 'cupon_borrar otra vez: 404')
    titulos = [x['titulo'] for x in datos.cambios if x['accion'] == 'cupon']
    revisar(titulos == ['Cupón VERANO25 creado desde la app', 'Cupón VERANO25 pausado desde la app',
                        'Cupón VERANO25 cambiado desde la app', 'Cupón VERANO25 borrado desde la app'],
            f'cada cambio de cupones queda anotado (cambios_admin) {titulos}')
    e = error_de(lambda: v.ClienteApi(url, servidor_prueba.CLAVE, solo_lectura=True).cupon_crear('NUEVO', 10))
    revisar(e is not None and e.codigo == 0 and {'cupon_crear', 'cupon_editar', 'cupon_borrar'} <= v.ACCIONES_QUE_CAMBIAN,
            'en modo captura no se crean cupones')

    # El servidor de antes de los cupones
    srv2, url2 = servidor(sin_cupones=True)
    c2 = v.ClienteApi(url2, servidor_prueba.CLAVE)
    e = error_de(c2.cupones)
    revisar(e is not None and e.desconocida and all(x['cupon'] is None and x['descuento'] is None for x in c2.ventas()),
            'admin.php de antes: «Acción desconocida» y las ventas sin cupón')

    # La ventana: la página Cupones
    aplicacion()
    w = ventana(url, mostrar=True)
    w.ir_a('cupones')
    esperar(lambda: quieto(w) and w.modelo_cup.rowCount() == 4, 'cargar los cupones')
    revisar(w.lbl_titulo.text() == 'Cupones' and not w.lado.isVisible() and not w.btn_exportar.isVisible()
            and w.btn_nuevo_cupon.isEnabled(), 'la página Cupones: sin panel a la derecha, con «Nuevo cupón»')
    primera = w._fila_de(w.tabla_cup, w.proxy_cup.index(0, 0))
    revisar(primera['estado'] == 'activo' and w.filtro_cup.botones['activo'].text() == 'Activos  2'
            and w.filtro_cup.botones['inactivo'].text() == 'Sin efecto  2', 'los activos primero y los filtros con su número')
    revisar('4 cupones · 2 activos · 3 ventas con cupón · $57.00 USD' in w.lbl_pie_cup.text(), f'el pie: {w.lbl_pie_cup.text()}')
    w.filtro_cup.poner('inactivo')
    esperar(lambda: quieto(w), 'filtrar')
    revisar(w.proxy_cup.rowCount() == 2, '«Sin efecto»: el vencido y el pausado')
    w.filtro_cup.poner('')
    w.buscar_cup.setText('campaña')
    w._filtrar_locales()
    revisar(w.proxy_cup.rowCount() == 1 and w._fila_de(w.tabla_cup, w.proxy_cup.index(0, 0))['codigo'] == 'NAVIDAD',
            'buscar en la nota: «campaña» encuentra NAVIDAD')
    w.buscar_cup.clear()
    w._filtrar_locales()
    m = w.modelo_cup
    n = m.buscar('codigo', 'NAVIDAD')[0]
    revisar(m.data(m.index(n, 0)) == 'NAVIDAD' and m.data(m.index(n, 0), v.ROL_SEGUNDA) == 'Campaña de diciembre'
            and m.data(m.index(n, 1)) == '20 %' and m.data(m.index(n, 2)) == '$23.20 USD' and m.data(m.index(n, 3)) == '0 de 50'
            and m.data(m.index(n, 6)) == 'Activo', 'la fila de NAVIDAD: código y nota, 20 %, $23.20, 0 de 50, Activo')
    # Nuevo cupón (el diálogo, con sus datos ya puestos)
    d = v.DialogoCupon(w, None, 2900, 'USD', dt.date.today().isoformat())
    d.codigo.setText('')
    d.codigo.textEdited.emit('mi cupon')
    revisar(d.codigo.text() == 'MICUPON', 'el código se escribe en mayúsculas y sin espacios')
    d.porcentaje.setText('20')
    revisar(d.lbl_precio.text() == 'queda en $23.20 USD' and d.aviso_gratis.isHidden(),
            'el diálogo dice en cuánto queda')
    d.porcentaje.setText('100')
    revisar(d.lbl_precio.text() == 'licencia gratis' and not d.aviso_gratis.isHidden(), '100 % sin tope: avisa que se reparte de más')
    d.usos.setText('3')
    revisar(d.aviso_gratis.isHidden(), 'con tope, el aviso se va')
    d.codigo.setText('X')
    revisar(d._problema()[0].startswith('El código'), 'un código de una letra no sirve')
    d.codigo.setText('MICUPON')
    d.con_vence.setChecked(True)
    revisar(d.datos() == {'codigo': 'MICUPON', 'porcentaje': 100, 'usos_max': 3, 'vence': (dt.date.today() + dt.timedelta(days=30)).isoformat(),
                          'nota': None, 'activo': True} and d._problema() == (None, None), 'datos() del diálogo')
    d.close()
    datos_dialogo = {'codigo': 'PRUEBA50', 'porcentaje': 50, 'usos_max': None, 'vence': None, 'nota': 'Desde la app', 'activo': True}
    w._dialogo_cupon = lambda cupon=None: type('D', (), {'datos': lambda self: dict(datos_dialogo), 'quiere_borrar': False,
                                                       'cambios': lambda self: {'porcentaje': 60}})()
    w.filtro_cup.poner('inactivo')
    w.nuevo_cupon()
    esperar(lambda: quieto(w) and w.modelo_cup.rowCount() == 5, 'crear el cupón')
    elegido = w._fila_actual(w.tabla_cup)
    revisar(elegido and elegido['codigo'] == 'PRUEBA50' and w.filtro_cup.valor == ''
            and w.aviso.texto.text().startswith('Cupón PRUEBA50 creado'), 'nuevo cupón: creado, a la vista (sin filtro) y elegido')
    menu = w._armar_menu_tabla(w.tabla_cup, elegido)
    textos = [a.text() for a in menu.actions() if not a.isSeparator()]
    revisar(textos == ['Copiar código', 'Copiar enlace para compartir', 'Editar…', 'Pausar', 'Borrar…']
            and all(a.isEnabled() for a in menu.actions()), f'el clic derecho de un cupón {textos}')
    menu.actions()[1].trigger()
    revisar(v.QGuiApplication.clipboard().text() == 'https://cinecaptions.shop/?cupon=PRUEBA50', 'copiar el enlace')
    ediciones = srv.acciones_recibidas.count('cupon_editar')   # (las de la API de arriba, con este mismo servidor)
    w._editar_cupon(elegido)
    esperar(lambda: quieto(w) and (w._fila_actual(w.tabla_cup) or {}).get('porcentaje') == 60, 'editar el cupón')
    revisar(datos.cupones[-1]['porcentaje'] == 60, 'editar: 60 % en el servidor')
    w._activar_cupon(w._fila_actual(w.tabla_cup), False)
    w._activar_cupon(w._fila_actual(w.tabla_cup), False)   # (otro clic mientras va: no se manda dos veces)
    esperar(lambda: quieto(w) and (w._fila_actual(w.tabla_cup) or {}).get('estado') == 'pausado', 'pausar')
    revisar(srv.acciones_recibidas.count('cupon_editar') == ediciones + 2 and not datos.cupones[-1]['activo'],
            'pausar: una sola vez, y en la tabla queda «Pausado»')
    w.preguntas.clear()
    w._borrar_cupon(w._fila_actual(w.tabla_cup))
    esperar(lambda: quieto(w) and w.modelo_cup.rowCount() == 4, 'borrar')
    revisar(w.preguntas == ['¿Borrar el cupón PRUEBA50?'] and 'PRUEBA50' not in [x['codigo'] for x in datos.cupones],
            'borrar: pregunta primero y lo quita')
    # Ventas: el cupón debajo del monto y en el panel
    w.ir_a('ventas')
    esperar(lambda: quieto(w), 'ventas')
    n = w.modelo_v.buscar('id', pid)[0]
    col = next(i for i, (cl, _t, _a) in enumerate(v.ModeloVentas.COLUMNAS) if cl == 'monto')
    revisar(w.modelo_v.data(w.modelo_v.index(n, col), v.ROL_SEGUNDA) == 'LANZAMIENTO'
            and 'cupón LANZAMIENTO (descuento de $10.00 USD)' in w.modelo_v.data(w.modelo_v.index(n, col), v.Qt.ItemDataRole.ToolTipRole),
            'en Ventas, «LANZAMIENTO» debajo del monto y lo descontado en la ayuda')
    elegir(w, w.tabla_v, lambda f: f['id'] == pid)
    grid = w.panel.ficha_ped._grid
    pares = [(grid.itemAtPosition(i, 0).widget().text(), grid.itemAtPosition(i, 1).widget().text())
             for i in range(grid.rowCount()) if grid.itemAtPosition(i, 0) and grid.itemAtPosition(i, 1)]
    revisar(('Cupón', 'LANZAMIENTO · −$10.00 USD') in pares, f'el panel del pedido muestra el cupón {pares[:3]}')
    w.close()

    # La ventana con el servidor de antes
    w2 = ventana(url2, mostrar=True)
    w2.ir_a('cupones')
    esperar(lambda: quieto(w2) and w2.servidor_cupones is False, 'cupones con el servidor de antes')
    revisar(w2.tabla_cup.mensaje_vacio == v.FALTA_SERVIDOR_CUPONES and not w2.btn_nuevo_cupon.isEnabled(),
            'con el admin.php de antes: dice qué falta subir y «Nuevo cupón» se apaga')
    w2.nuevo_cupon()
    revisar(w2.mensajes and w2.mensajes[-1][0] == 'Falta el servidor nuevo', '«Nuevo cupón» explica que falta el servidor')
    w2.close()
    for ventana_ in (w, w2):
        ventana_.deleteLater()
    v.QApplication.sendPostedEvents(None, v.QEvent.Type.DeferredDelete)
    srv.shutdown()
    srv2.shutdown()


# ------------------------------------------------------------------ 15. Errores: «Informe completo» y «Borrar todo» (2.10)
def prueba_informe_y_borrar():
    print('Errores: «Informe completo» y «Borrar todo» (2.10)')
    # La función del informe, sola: agrupa el mismo fallo, cada caso con su informe (el repetido, una vez), sin correos ni claves
    base = {'licencia_id': 1, 'equipo': 'a', 'nombre_equipo': 'PC-ANA', 'cliente': 'Ana Gómez', 'correo': 'ana@example.com',
            'clave': 'CC-AAAA-BBBB-CCCC-DDDD', 'nivel': 'error', 'titulo': 'KeyError: 7', 'mensaje': 'Falló al colocar',
            'origen': 'colocar', 'version': '5.54', 'so': 'windows', 'veces': 2, 'primera': '2026-11-01 10:00:00',
            'ultima': '2026-11-10 10:00:00', 'visto': False, 'detalle': 'Traceback (most recent call last):\n  línea 1\nKeyError: 7',
            'equipo_datos': 'GPU X · RAM 8 GB'}
    errores = [dict(base, id=1),
               dict(base, id=2, licencia_id=2, equipo='b', nombre_equipo='MAC-LUIS', cliente='Luis Paz', correo='luis@example.com',
                    clave='CC-EEEE-FFFF-GGGG-HHHH', titulo='KeyError: 9', version='5.53', so='macOS 15.1', veces=3, visto=True,
                    ultima='2026-11-12 08:00:00'),
               dict(base, id=3, nivel='aviso', titulo='Sin conexión | GitHub', mensaje='No se pudo leer el version.json',
                    veces=1, origen='actualizar', detalle='```\nbloque raro\n```'),
               dict(base, id=4, titulo='Se cerró el motor', mensaje='Código 3', veces=1, detalle=None)]
    t = v.informe_completo_de_errores(errores, '5.54', ahora=dt.datetime(2026, 11, 13, 9, 30))
    revisar(t.startswith('# Informe de errores de CineCaptions\n')
            and '13/11/2026 09:30 · 4 errores (3 sin ver) de 2 clientes en 2 equipos · 7 veces en total · 3 fallos distintos · '
                'última versión publicada: 5.54' in t, 'informe completo: la cabecera con cuántos, de quiénes y cuántos fallos')
    revisar(t.count('\n| 1 | ') == 1 and t.count('\n| 2 | ') == 1 and t.count('\n| 3 | ') == 1 and '\n| 4 | ' not in t
            and '| Sin conexión / GitHub |' in t, 'la tabla del resumen: un fallo por fila (un «|» del título no rompe la tabla)')
    revisar('## 1. Error · KeyError: 9' in t and '- **Pasó:** 5 veces · 2 clientes · 2 equipos · 1 sin ver' in t
            and '- **Versiones:** 5.53 (1 equipo) · 5.54 (1 equipo)' in t and 'macOS 15.1 (1 equipo)' in t
            and '- **Dónde:** colocar' in t, 'el mismo fallo en dos equipos (KeyError 7 y 9): veces, clientes, versiones y sistemas')
    revisar(t.index('### Informe técnico de #2 · Luis P. · MAC-LUIS') < t.index('### Informe técnico de #1 · Ana G. · PC-ANA')
            and t.count('KeyError: 7\n```') == 1 and '_El mismo informe que #2._' in t and '**Al fallar:** GPU X · RAM 8 GB' in t,
            'cada caso con su informe (el más reciente primero; el mismo informe, una sola vez)')
    revisar('~~~~text\n```\nbloque raro\n```\n~~~~' in t and 'Sin informe técnico' in t,
            'un informe con ``` va en otro cerco y uno sin informe lo dice')
    revisar('example.com' not in t and 'CC-' not in t, 'el informe completo no trae correos ni claves de licencia')
    vacio = v.informe_completo_de_errores([])
    revisar('Ningún cliente tiene errores guardados.' in vacio and '## Resumen' not in vacio, 'sin errores: lo dice')

    # La acción errores_borrar
    srv, url = servidor()
    datos = srv.datos
    c = v.ClienteApi(url, servidor_prueba.CLAVE)
    total = len(datos.errores)
    e = error_de(lambda: c.errores_borrar([]))
    revisar(e is not None and e.codigo == 400 and e.mensaje == 'Faltan los errores que borrar.', 'errores_borrar sin ids: 400')
    uno = next(x for x in datos.errores if not x['visto'])
    r = c.errores_borrar([uno['id'], 999])
    revisar(r['borrados'] == 1 and all(x['id'] != uno['id'] for x in datos.errores) and r['resumen']['sin_ver'] == 2,
            'errores_borrar con ids: solo ese (uno que no existe no cuenta) y el resumen nuevo')
    lectura = v.ClienteApi(url, servidor_prueba.CLAVE, solo_lectura=True)
    antes = len(srv.acciones_recibidas)
    e = error_de(lambda: lectura.errores_borrar(todos=True))
    revisar(e is not None and len(srv.acciones_recibidas) == antes and len(datos.errores) == total - 1,
            'solo lectura (--captura): errores_borrar ni sale')
    r = c.errores_borrar(todos=True)
    revisar(r['borrados'] == total - 1 and datos.errores == []
            and r['resumen'] == {'sin_ver': 0, 'equipos': 0, 'ultimo_id': None, 'ultima': None},
            'errores_borrar con todos=true: no queda ninguno (ni el contador)')
    revisar(c.errores_borrar(todos=True)['borrados'] == 0, 'borrar todo otra vez: 0')
    srv.shutdown()
    for opciones in ({'sin_borrar_errores': True}, {'sin_cupones': True}, {'sin_errores': True}, {'viejo': True}):
        srv, url = servidor(**opciones)
        n = len(srv.datos.errores)
        e = error_de(lambda: v.ClienteApi(url, servidor_prueba.CLAVE).errores_borrar(todos=True))
        revisar(e is not None and e.desconocida and len(srv.datos.errores) == n,
                f'admin.php de antes ({next(iter(opciones))}): errores_borrar da «Acción desconocida» y no borra nada')
        srv.shutdown()

    # En la ventana: «Informe completo» arriba (solo en Errores) y «Borrar todo» en el pie
    aplicacion()
    srv, url = servidor()
    datos = srv.datos
    w = ventana(url, mostrar=True)
    revisar(not w.btn_informe_err.isVisible() and w.barra.nivel == 'expandida',
            '«Informe completo» no sale en Resumen; la isla sigue abierta a 1440 px')
    w.ir_a('errores')
    esperar(lambda: quieto(w) and w.modelo_err.rowCount() == 5, 'página Errores')
    b_inf, b_borrar = w.btn_informe_err, w.btn_borrar_err
    revisar(b_inf.isVisible() and b_inf.isEnabled() and not w.btn_exportar.isVisible() and b_borrar.isVisible()
            and b_borrar.isEnabled() and b_borrar.property('tipo') == 'peligro' and w.proxy_err.rowCount() == 3,
            'Errores: «Informe completo» arriba, «Borrar todo» (rojo) en el pie; la lista en «Sin ver» (3 de 5)')
    esperar_isla(w)
    revisar(w.barra.nivel == 'expandida' and en_la_isla(w), 'a 1440 px la isla no tapa «Informe completo» ni se cierra')

    antes = len(srv.acciones_recibidas)
    b_inf.click()
    revisar(not b_inf.isEnabled() and not b_borrar.isEnabled() and b_inf.text().strip() == 'Preparando…',
            'mientras se arma: «Preparando…» y los dos botones apagados')
    esperar(lambda: quieto(w) and w.dialogo_informe is not None, 'informe completo')
    d = w.dialogo_informe
    pedidas = srv.acciones_recibidas[antes:]
    revisar(d is not None and pedidas.count('errores') == 1 and pedidas.count('error_detalle') == 5 and srv.max_en_curso == 1,
            f'pide la lista de TODOS y el informe de cada uno, de a una petición ({pedidas})')
    texto = d.texto if d else ''
    revisar(all(f"#{x['id']}" in texto for x in datos.errores)
            and all(x['detalle'].strip().splitlines()[-1] in texto for x in datos.errores if x.get('detalle'))
            and not any(datos.licencia_real(x['licencia_id'])['correo'] in texto for x in datos.errores)
            and d.vista.toPlainText().startswith('Informe de errores de CineCaptions') and d.vista.document().blockCount() > 40
            and d.archivo.startswith('errores-cinecaptions-') and d.archivo.endswith('.md'),
            'el informe trae los 5 (no solo los 3 «Sin ver») con su informe técnico, sin correos; se ve formateado en el diálogo')
    revisar(b_inf.isEnabled() and b_inf.text().strip() == 'Informe completo' and b_borrar.isEnabled() and b_inf.minimumWidth() == 0,
            'al terminar, los botones vuelven como estaban')
    if d:
        d.btn_copiar.click()
        revisar(v.QGuiApplication.clipboard().text() == texto and w.aviso.texto.text().startswith('Informe copiado'),
                '«Copiar todo» copia el informe entero')
        ruta = TEMPORAL / 'informe-errores.md'
        revisar(d.guardar_en(str(ruta)) and ruta.read_text(encoding='utf-8') == texto and d.guardado == str(ruta)
                and str(ruta) in d.sub.text(), '«Guardar…» lo escribe en UTF-8 y dice dónde quedó')
        revisar(not d.guardar_en(str(TEMPORAL / 'no-existe' / 'x.md')) and d.guardado == str(ruta)
                and w.mensajes[-1][0] == 'No se pudo guardar el informe', 'si no se puede guardar, lo dice y no cambia nada')
        d.close()
        esperar(lambda: w.dialogo_informe is None, 'cerrar el informe')
    # Un informe que ya no está (404) va sin el suyo; un fallo de la red corta el informe y lo dice
    real = w.cliente.error_detalle
    primero = datos.errores[0]['id']

    def con_404(ident):
        if ident == primero:
            raise v.ApiError('Ese error ya no existe.', 404)
        return real(ident)

    w.cliente.error_detalle = con_404
    b_inf.click()
    esperar(lambda: quieto(w) and w.dialogo_informe is not None, 'informe con un 404')
    revisar(w.dialogo_informe is not None and 'Sin informe técnico' in w.dialogo_informe.texto,
            'un error que se borró a medio camino va sin su informe')
    w.dialogo_informe.close()
    esperar(lambda: w.dialogo_informe is None, 'cerrar')
    w.cliente.error_detalle = lambda ident: (_ for _ in ()).throw(v.ApiError('No hay conexión con el servidor.', 0))
    b_inf.click()
    esperar(lambda: quieto(w) and w._informe_err is None, 'informe que falla')
    revisar(w.dialogo_informe is None and w.aviso.texto.text().startswith('No pude preparar el informe')
            and b_inf.isEnabled() and b_borrar.isEnabled() and b_inf.text().strip() == 'Informe completo',
            'si falla la red: lo dice, no abre nada y los botones vuelven')
    w.cliente.error_detalle = real

    # «Borrar todo»: con su pregunta; si no se confirma, no sale nada
    w._confirmar = lambda pregunta, *a, **k: w.preguntas.append(pregunta) and False
    antes = len(srv.acciones_recibidas)
    apretar(w, b_borrar, 'borrar todo (sin confirmar)')
    revisar(len(datos.errores) == 5 and 'errores_borrar' not in srv.acciones_recibidas[antes:] and w.modelo_err.rowCount() == 5,
            'Borrar todo sin confirmar: no borra nada')
    w._confirmar = lambda pregunta, *a, **k: w.preguntas.append(pregunta) or True
    w.vista_errores.poner('lista')
    w.filtro_err.poner('todos')
    elegir_error(w, lambda f: True)   # (con un error en el panel: al borrar, el panel queda vacío)
    antes = len(w.preguntas)
    apretar(w, b_borrar, 'borrar todo')
    revisar(w.preguntas[antes:] == ['¿Borrar los 5 errores de 3 clientes?'],
            'Borrar todo pregunta antes, con cuántos (todos, no solo los «Sin ver») y de cuántos clientes')
    revisar(datos.errores == [] and w.modelo_err.rowCount() == 0 and w.modelo_cli.rowCount() == 0
            and w.barra.botones['errores'].contador is None and w.panel_error.vacio.isVisible() and w.error_elegido is None
            and not b_borrar.isEnabled() and not b_inf.isEnabled() and not w.btn_todo_visto.isEnabled()
            and not w.btn_resumen_err.isEnabled() and w.aviso.texto.text() == '5 errores borrados.' and w._acciones == 0
            and w.tabla_err.mensaje_vacio == 'Ningún cliente ha tenido errores.' and not v.ERRORES,
            'borrado: las listas vacías, sin contador ni error elegido, los botones apagados y «5 errores borrados.»')
    act = datos.activaciones[0]
    nuevo = datos.recibir_error(act['licencia_id'], act['equipo'], 'e' * 40, 'error', 'Otro fallo', 'Pasó de nuevo.')
    w.actualizar_todo()
    esperar(lambda: w.intento_listo and quieto(w) and w.modelo_err.rowCount() == 1, 'un error nuevo después de borrar')
    revisar(nuevo == 6 and w.barra.botones['errores'].contador == 1 and b_borrar.isEnabled() and b_inf.isEnabled(),
            'después de borrar, un error nuevo entra con su id nuevo (6) y los botones vuelven')
    w.solo_lectura = True   # (--captura: «Borrar todo» nunca se enciende; el informe sí, porque solo lee)
    w._poner_botones_errores()
    revisar(not b_borrar.isEnabled() and b_inf.isEnabled(), 'en solo lectura, «Borrar todo» apagado e «Informe completo» activo')
    w.solo_lectura = False
    # Angosta (1100 px): el pie cabe sin empujar el panel del error (el texto del pie se corta con «…»)
    w.vista_errores.poner('usuario')
    w.resize(1100, 720)
    esperar(lambda: quieto(w), 'a 1100 px')
    esperar_isla(w)
    raiz = w.centralWidget()
    derecha = max(x.mapTo(raiz, v.QPoint(x.width(), 0)).x() for x in (w.btn_resumen_err, w.btn_todo_visto, b_borrar))
    revisar(derecha <= w.panel_error.mapTo(raiz, v.QPoint(0, 0)).x() and w.panel_error.width() >= 400 and en_la_isla(w),
            f'a 1100 px el pie de Errores cabe en su columna y el panel sigue ancho ({w.panel_error.width()} px)')
    w.close()
    srv.shutdown()

    # El admin.php publicado (sin errores_borrar): lo dice y todo sigue igual
    srv, url = servidor(sin_borrar_errores=True)
    w = ventana(url, mostrar=True)
    w.ir_a('errores')
    esperar(lambda: quieto(w) and w.modelo_err.rowCount() == 5, 'Errores con el admin.php publicado')
    apretar(w, w.btn_borrar_err, 'borrar todo con el admin.php publicado')
    revisar(w.mensajes[-1:] == [('Tu servidor todavía no sabe borrar errores', v.SERVIDOR_SIN_BORRAR_ERRORES)]
            and len(srv.datos.errores) == 5 and w.modelo_err.rowCount() == 5 and w.btn_borrar_err.isEnabled()
            and w.btn_todo_visto.isEnabled() and w._acciones == 0 and w.barra.botones['errores'].contador == 3,
            'con el admin.php publicado: avisa que falta subirlo y no cambia nada')
    w.close()
    srv.shutdown()


# ------------------------------------------------------------------ La clave al estrenar la app en un equipo (Windows y Mac)
class LlaveroFalso:
    """keyring de mentira con las reglas del Llavero de macOS (así se prueban también en Windows): una entrada solo la
    cambia o la borra la «app» que la creó (si no, -25244: sin firma de Apple cada versión es otra app) y el dueño puede
    negar el permiso de leerla."""

    def __init__(self):
        self.entradas, self.app, self.negar = {}, 'Ventas 2.9', False

    def get_password(self, servicio, cuenta):
        if self.negar:
            raise RuntimeError('User interaction is not allowed. (-25308)')
        return self.entradas.get((servicio, cuenta), (None,))[0]

    def set_password(self, servicio, cuenta, clave):
        if self.entradas.get((servicio, cuenta), (None, self.app))[1] != self.app:
            raise RuntimeError('(-25244) errSecInvalidOwnerEdit')
        self.entradas[(servicio, cuenta)] = (clave, self.app)

    def delete_password(self, servicio, cuenta):
        if (servicio, cuenta) not in self.entradas:
            raise RuntimeError('The specified item could not be found in the keychain.')
        if self.entradas[(servicio, cuenta)][1] != self.app:
            raise RuntimeError('(-25244) errSecInvalidOwnerEdit')
        del self.entradas[(servicio, cuenta)]


class OsComoMac:
    """os con name 'posix' (lo demás es el os real): ventas.py toma el camino de Mac (el Llavero) también en Windows."""
    name = 'posix'

    def __getattr__(self, nombre):
        return getattr(os, nombre)


def config_nueva(nombre):
    """Una carpeta de configuración vacía: la app recién instalada en un equipo."""
    os.environ['CC_VENTAS_CONFIG'] = str(TEMPORAL / 'estreno' / nombre)
    return v.Configuracion()


def contestar_clave(w, texto, cancelar=False):
    """Contesta el cuadro de la clave en cuanto se abre, como el dueño: pega y «Guardar clave», o «Cancelar».
    Devuelve una lista que se llena con los textos que mostró el cuadro."""
    from PySide6.QtWidgets import QAbstractButton
    visto = []

    def responder(intento=0):
        d = next((x for x in w.findChildren(v.DialogoClave) if x.isVisible()), None)
        if d is None:
            if intento < 400:
                v.QTimer.singleShot(25, lambda: responder(intento + 1))
            return
        visto.extend([l.text() for l in d.findChildren(v.QLabel)] + [b.text() for b in d.findChildren(QAbstractButton)])
        if cancelar:
            d.reject()
        else:
            d.campo.setText(texto)
            d.accept()

    v.QTimer.singleShot(25, responder)
    return visto


def ventana_real(config, url):
    """Como al abrir la app de verdad (no --captura): guarda la clave que se pega."""
    w = v.VentanaPrincipal(config, url)
    w.mensajes = []
    w._mensaje = lambda titulo, texto, tipo='error': w.mensajes.append((titulo, texto))
    w._confirmar = lambda pregunta, *a, **k: True
    w.setAttribute(v.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    w.resize(1440, 900)
    w.show()
    return w


def prueba_clave_estreno():
    en_mac = sys.platform == 'darwin'
    print(f'La clave al estrenar la app en un equipo ({"Mac, con el Llavero de verdad" if en_mac else "Windows"})')
    aplicacion()
    original = os.environ['CC_VENTAS_CONFIG']
    srv, url = servidor()
    try:
        # 1) Primera vez en este equipo: no hay clave → el cuadro sale sin aviso de error; se pega (con espacios) y carga
        cfg = config_nueva('ventana')
        revisar(cfg.leer_clave() is None and v.aviso_sin_clave(cfg) == '',
                'equipo nuevo: no hay clave y el cuadro sale sin aviso de error')
        w = ventana_real(cfg, url)
        visto = contestar_clave(w, f'  {servidor_prueba.CLAVE}\n')
        w.pedir_clave_inicial(v.aviso_sin_clave(cfg))
        esperar(lambda: w.intento_listo and quieto(w), 'primera carga con la clave pegada')
        revisar(bool(visto) and not w.banda.isVisible() and not w._clave_mala and w.modelo_v.rowCount() > 0
                and not w.mensajes, f'pega la clave (con espacios alrededor): carga las ventas sin avisos ({w.mensajes})')
        texto_cuadro = ' '.join(visto)
        if en_mac:
            revisar('Llavero de esta Mac' in texto_cuadro and 'Windows' not in texto_cuadro and '\\' not in texto_cuadro,
                    'en Mac el cuadro habla del Llavero, sin «Windows» ni rutas con «\\»')
        else:
            revisar('usuario de Windows' in texto_cuadro and 'CineCaptions_claves\\admin_ventas.txt' in texto_cuadro,
                    'en Windows el cuadro sigue igual')
        crudo = cfg.ruta.read_text(encoding='utf-8')
        guardada = json.loads(crudo).get('clave') or ''
        revisar(servidor_prueba.CLAVE not in crudo and (guardada.startswith('llavero:administrador-') if en_mac else True),
                'la clave no queda a la vista en config.json' + (' (va al Llavero)' if en_mac else ' (va cifrada)'))
        revisar(v.Configuracion().leer_clave() == servidor_prueba.CLAVE,
                'al volver a abrir la app lee la clave guardada (no la pide otra vez)')

        # 2) «Cambiar clave» con una equivocada: la banda lo dice; con la buena vuelve a cargar
        contestar_clave(w, 'clave-equivocada-0123456789')
        w.cambiar_clave()
        esperar(lambda: quieto(w) and w._clave_mala, 'el servidor rechaza la clave equivocada')
        revisar(w.banda.isVisible() and w.banda.btn_clave.isVisible() and 'Cambiar clave' in w.banda.btn_clave.text(),
                'clave equivocada: la banda pide cambiarla')
        contestar_clave(w, servidor_prueba.CLAVE)
        w.banda.btn_clave.click()
        esperar(lambda: quieto(w) and not w._clave_mala and not w.banda.isVisible(), 'otra vez con la clave buena')
        revisar(w.modelo_v.rowCount() > 0 and v.Configuracion().leer_clave() == servidor_prueba.CLAVE,
                'con «Cambiar clave» y la buena vuelve a cargar y queda guardada la buena')
        if en_mac:   # cada guardado es una entrada NUEVA; la anterior (de esta misma app) se borra
            nueva = v.Configuracion().datos['clave'].split(':', 1)[1]
            anterior = guardada.split(':', 1)[1]
            revisar(nueva != anterior and v._llavero().get_password(v.servicio_llavero(), anterior) is None,
                    'Llavero: la clave nueva va en otra entrada y la anterior se borra')
        w.close()

        # 3) Si cancela el cuadro: banda «Pegar clave» y no se guarda nada; con el botón de la banda se arregla
        cfg = config_nueva('cancelar')
        w = ventana_real(cfg, url)
        contestar_clave(w, '', cancelar=True)
        w.pedir_clave_inicial('')
        revisar(w.banda.isVisible() and 'Pegar clave' in w.banda.btn_clave.text() and cfg.leer_clave() is None
                and 'clave' not in v.Configuracion().datos, 'si cancela: banda «Pegar clave» y no se guarda nada')
        contestar_clave(w, servidor_prueba.CLAVE)
        w.banda.btn_clave.click()
        esperar(lambda: w.intento_listo and quieto(w) and not w.banda.isVisible(), 'pegar la clave desde la banda')
        revisar(w.modelo_v.rowCount() > 0 and v.Configuracion().leer_clave() == servidor_prueba.CLAVE,
                'desde la banda «Pegar clave» también queda guardada y carga')
        w.close()

        # 4) La clave desde el archivo de CineCaptions_claves (con su encabezado), como con «Abrir archivo…»
        revisar(v.extraer_clave(f'Clave de administrador de CineCaptions Ventas:\n{servidor_prueba.CLAVE}\n')
                == servidor_prueba.CLAVE and v.extraer_clave(f'﻿{servidor_prueba.CLAVE}\r\n') == servidor_prueba.CLAVE,
                'el archivo admin_ventas.txt (con encabezado, BOM o fin de línea de Windows) da la clave')

        # 5) Las reglas del Llavero de Mac, también desde Windows (con un Llavero de mentira que se porta igual)
        llavero, os_real, llavero_real = LlaveroFalso(), v.os, v._llavero
        v.os, v._llavero = OsComoMac(), (lambda: llavero)
        try:
            servicio = v.servicio_llavero()
            cfg = config_nueva('mac')
            cfg.guardar_clave('clave-de-la-mac-123456')
            cuenta = cfg.datos['clave'].split(':', 1)[1]
            revisar(len(llavero.entradas) == 1 and len(cuenta) == len('administrador-') + 8
                    and 'clave-de-la-mac' not in cfg.ruta.read_text(encoding='utf-8')
                    and v.Configuracion().leer_clave() == 'clave-de-la-mac-123456',
                    'Mac: la clave va al Llavero («llavero:administrador-…» en config.json) y se lee al reabrir')
            cfg.guardar_clave('otra-clave-de-la-mac-789')
            revisar(len(llavero.entradas) == 1 and (servicio, cuenta) not in llavero.entradas
                    and v.Configuracion().leer_clave() == 'otra-clave-de-la-mac-789',
                    'Mac: cambiar la clave deja una sola entrada (la anterior se borra)')
            llavero.app = 'Ventas 2.10'   # versión nueva instalada: macOS no la deja cambiar ni borrar lo de la 2.9
            revisar(v.Configuracion().leer_clave() == 'otra-clave-de-la-mac-789',
                    'Mac, versión nueva: lee la clave que guardó la anterior (tras «Permitir siempre»)')
            cfg = v.Configuracion()
            cfg.guardar_clave('clave-tras-actualizar-42')
            revisar(v.Configuracion().leer_clave() == 'clave-tras-actualizar-42' and len(llavero.entradas) == 2,
                    'Mac, versión nueva: guarda en una entrada nueva aunque no pueda borrar la vieja (-25244)')
            llavero.negar = True
            cfg = v.Configuracion()
            aviso = v.aviso_sin_clave(cfg)
            revisar(cfg.leer_clave() is None and 'Llavero de esta Mac' in aviso and 'Windows' not in aviso,
                    'Mac: si se niega el permiso del Llavero, no se cae: vuelve a pedir la clave con un aviso de Mac')
            llavero.negar = False
            llavero.entradas.clear()
            revisar(v.Configuracion().leer_clave() is None, 'Mac: si la entrada se borró del Llavero, vuelve a pedirla')
            cfg = config_nueva('mac_vieja')
            cfg.datos['clave'] = v.EN_LLAVERO
            cfg.guardar()
            llavero.entradas[(servicio, 'administrador')] = ('clave-formato-viejo-1', llavero.app)
            revisar(v.Configuracion().leer_clave() == 'clave-formato-viejo-1',
                    'Mac: entiende el config.json viejo («clave»: «llavero»)')
            v._llavero = lambda: None
            cfg = v.Configuracion()
            try:
                cfg.guardar_clave('sin-keyring-123456')
                sin_keyring = 'no avisó'
            except OSError as e:
                sin_keyring = str(e)
            revisar(cfg.leer_clave() is None and 'keyring' in sin_keyring,
                    f'Mac sin el módulo keyring: no se cae y el error es claro ({sin_keyring})')
            v._llavero = lambda: llavero
            d = v.DialogoClave(None, primera_vez=True)
            textos = ' '.join(l.text() for l in d.findChildren(v.QLabel))
            revisar('Llavero de esta Mac' in textos and 'Windows' not in textos,
                    'Mac: el cuadro de la clave dice «Llavero de esta Mac» y no «Windows»')
            d.deleteLater()
        finally:
            v.os, v._llavero = os_real, llavero_real
        nota_bien = ('/' in v.NOTA_CLAVE and '\\' not in v.NOTA_CLAVE and v.ESTE_EQUIPO == 'esta Mac' and v.CTRL == '⌘'
                     if en_mac else '\\' in v.NOTA_CLAVE and v.ESTE_EQUIPO == 'esta PC' and v.CTRL == 'Ctrl+')
        revisar(nota_bien, 'la ruta del archivo, «esta PC/esta Mac» y los atajos (Ctrl+/⌘) van con lo de este sistema')
    finally:
        os.environ['CC_VENTAS_CONFIG'] = original
        srv.shutdown()


if __name__ == '__main__':
    inicio = time.monotonic()
    v.instalar_errores(con_ventanas=False)   # un error dentro de la ventana queda en v.ERRORES (y la prueba falla)
    # (prueba_confirmar_eliminar y prueba_clave_estreno abren diálogos con exec(): antes de las capturas, ver arriba)
    for prueba in (prueba_funciones, prueba_acciones, prueba_errores, prueba_importar, prueba_ventana, prueba_isla,
                   prueba_confirmar_eliminar, prueba_clave_estreno, prueba_casos_ventana, prueba_errores_clientes,
                   prueba_fichas, prueba_dos_capturas, prueba_recurso, prueba_visual, prueba_eliminar, prueba_versiones,
                   prueba_cupones, prueba_informe_y_borrar):
        prueba()
    revisar(not v.ERRORES, f'ningún error inesperado en toda la prueba ({len(v.ERRORES)})')
    print(f'\n{"TODO BIEN" if not FALLAS else f"{len(FALLAS)} FALLAS"} en {time.monotonic() - inicio:.1f} s')
    sys.exit(1 if FALLAS else 0)   # (al desarmar Qt, a veces el proceso se cae DESPUÉS de esto: mac/construir_ventas_mac.sh mira «TODO BIEN»)
