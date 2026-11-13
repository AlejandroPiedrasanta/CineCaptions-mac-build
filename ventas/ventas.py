# -*- coding: utf-8 -*-
"""
CineCaptions Ventas: el programa de escritorio del dueño para ver las ventas y manejar las licencias.

Habla con la API privada pagos/admin.php (POST con la cabecera X-Admin-Clave). Arriba, la isla del menú con las páginas:
- Resumen: hoy, este mes, total, reembolsos, licencias y equipos activos en 30 días; la gráfica de ventas de cada día y
  cuántos equipos ya tienen la última versión de CineCaptions;
- Ventas (Recurrente) y Canjes de Gumroad: tablas que se pueden ordenar, filtrar, buscar y exportar a CSV, con la versión
  que usa cada cliente y cuándo abrió CineCaptions por última vez. Una venta se puede eliminar (clic en ella → «Eliminar
  venta» en el panel, o clic derecho): sale de la lista y de los totales pero no se borra, y se restaura desde el filtro
  «Eliminadas»;
- Versiones: arriba, en palabras, cuántos clientes no tienen la última versión y a cuántos ya se les avisó, con «Avisar a
  los N desactualizados…»; abajo, un cliente por fila con su versión y su «Avisar» (los que faltan por avisar primero).
  El anuncio de una versión nueva va por correo, uno por uno (con una pausa entre cada uno, barra de avance y «Detener»);
- Cupones (2.8): los cupones de descuento de la web (pagos/cupones.php). «Nuevo cupón» (código, porcentaje de 1 a 100,
  tope de usos, fecha de vencimiento, nota); doble clic para editarlo o borrarlo y clic derecho para copiar su enlace
  (cinecaptions.shop/?cupon=CODIGO) o pausarlo. Cada uno dice en cuánto queda la licencia, cuántas ventas se hicieron con
  él y cuánto dejaron. Con el 100 % la licencia sale gratis (cupon_gratis.php). En Ventas, el código va debajo del monto;
- Avisos: los correos de actualización que se mandaron;
- Errores: los errores que les salieron a los clientes en CineCaptions (desde la 5.71 el programa los manda a
  pagos/errores.php): por usuario (cada cliente con sus errores agrupados por equipo, los que tienen errores sin ver
  arriba) o todos juntos, con el informe técnico de cada uno. Cuando llega uno nuevo, la app avisa con una notificación
  de Windows (y el contador rojo de la isla).
A la derecha, el panel de la licencia elegida: cliente (con «Editar»), clave, límite de equipos, cada equipo con su
versión, notas internas, historial y las acciones (bloquear o reactivar, liberar equipos, reenviar la clave, avisar que
actualice, consultar el pago en Recurrente, marcar como reembolsado).

Las peticiones salen de UNA en una por una cola de un solo hilo (la ventana nunca se congela): admin.php anota cada
petición en curso para su límite de intentos y varias a la vez podrían dar un 429 falso. «Actualizar» es una sola
petición (la acción panel). Si el servidor publicado todavía es el anterior (sin las acciones nuevas), la app lo dice
y sigue funcionando con lo que hay.

La clave de administrador se guarda cifrada con DPAPI de Windows (solo este usuario de Windows puede leerla) en
%APPDATA%\\CineCaptions Ventas\\config.json. En Mac (2.9) va en el Llavero de macOS (keyring) y config.json, sin la
clave, en ~/Library/Application Support/CineCaptions Ventas. El .dmg de Mac se arma en GitHub (mac/, ver su LEEME).

Desde la terminal:
  ventas.py --importar-clave archivo.txt   guarda la clave que está en ese archivo (cifrada) y sale, sin abrir la ventana
  ventas.py --api http://127.0.0.1:8799    usa otra dirección de la API solo esta vez (por ejemplo, servidor_prueba.py)
  ventas.py --captura carpeta              carga los datos, guarda capturas PNG de cada página y de los diálogos y sale
                                           (revisión visual). SOLO LECTURA: nunca llama a una acción que cambie algo ni
                                           manda correos. Funciona también con QT_QPA_PLATFORM=offscreen.
  ventas.py --captura carpeta --ancho 1100 lo mismo, con la ventana de ese ancho (si no se dice, 1440)
"""
import argparse
import base64
import csv
import ctypes
import datetime as dt
import html
import http.client
import ipaddress
import json
import math
import os
import re
import socket
import ssl
import sys
import tempfile
import time
import traceback
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import (QAbstractTableModel, QByteArray, QDate, QEasingCurve, QEvent, QItemSelectionModel, QLibraryInfo,
                            QModelIndex, QObject, QPoint, QPointF, QPropertyAnimation, QRectF, QRunnable, QSize,
                            QSortFilterProxyModel, QStandardPaths, Qt, QThreadPool, QTimer, QTranslator, QUrl, Signal,
                            Slot)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient, QDesktopServices, QFont, QFontDatabase,
                           QFontMetrics, QGuiApplication, QIcon, QImage, QIntValidator, QKeySequence, QLinearGradient,
                           QMouseEvent,
                           QPainter, QPainterPath, QPalette, QPen, QPixmap, QShortcut, QSyntaxHighlighter,
                           QTextCharFormat, QTextOption)
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QBoxLayout, QButtonGroup, QCheckBox,
                               QComboBox, QDateEdit, QDialog, QFileDialog, QFrame, QGraphicsOpacityEffect, QGridLayout,
                               QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QPlainTextEdit, QProgressBar,
                               QPushButton, QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QStyle,
                               QStyledItemDelegate, QStyleOptionViewItem, QSystemTrayIcon, QTableView, QVBoxLayout,
                               QWidget)

from logo_ventas import icono_app, pixmap_logo   # ícono verde propio: no se confunde con el de CineCaptions

APP = 'CineCaptions Ventas'
VERSION = '2.9.0'   # (2.9: también en Mac —la clave en el Llavero, carpetas de macOS— con su .dmg Apple Silicon e Intel; 2.8: la página Cupones —crear, pausar y borrar cupones de descuento— y el cupón de cada venta; 2.7:el menú es la isla flotante de arriba, sin la barra lateral; 2.6: «Copiar resumen» de los errores; 2.5: las dos capturas del error, pantalla y ventana, de CineCaptions 5.73; 2.4: la ficha del equipo)
API_POR_DEFECTO = 'https://cinecaptions.shop/pagos/admin.php'
SITIO = 'https://cinecaptions.shop'   # (2.8: el enlace de un cupón, si el servidor no manda el suyo)
DESCARGA = 'https://github.com/AlejandroPiedrasanta/CineCaptions-releases/releases/latest'
NOTA_CLAVE = 'Está en CineCaptions_claves\\admin_ventas.txt'
AUTO_MS = 2 * 60 * 1000          # actualización automática: cada 2 minutos
LIMITE_LISTA = 1000              # filas por pedido (el máximo que acepta admin.php)
DIAS_GRAFICA = 30                # la gráfica de ventas del Resumen
VIGENCIA_VERSION_S = 10 * 60     # admin.php guarda 10 minutos lo que dice el version.json de GitHub
PAUSA_AVISOS_MS = 1000           # entre un correo de «hay versión nueva» y el siguiente
MAX_TEXTO = 2000                 # largo máximo de una nota o del mensaje de un aviso (lo mismo que admin.php)
MAX_NOMBRE = 190
LIMITE_EQUIPOS = (1, 10)         # cuántas computadoras puede tener una licencia, como mínimo y como máximo
# Acciones que cambian algo en el servidor (o mandan correos): --captura nunca las llama
ACCIONES_QUE_CAMBIAN = frozenset({'licencia_estado', 'liberar_equipo', 'reenviar_correo', 'marcar_reembolsado',
                                  'avisar_actualizacion', 'nota', 'limite', 'editar_cliente', 'error_visto',
                                  'eliminar_venta', 'cupon_crear', 'cupon_editar', 'cupon_borrar'})
# 2.8: los cupones de descuento (pagos/cupones.php). Un código: de 2 a 32 letras, números, guiones o guiones bajos (como
# codigo_cupon() de cupones.php). Un cupón del 100 % regala la licencia (cupon_gratis.php, sin pasar por Recurrente).
CODIGO_CUPON = re.compile(r'[A-Z0-9][A-Z0-9_-]{1,31}')
FILTROS_CUPONES = [('Todos', ''), ('Activos', 'activo'), ('Sin efecto', 'inactivo')]
USOS_SIN_TOPE = 0                # en el diálogo, «0» = sin tope de usos

# Colores de la marca (los mismos de css/estilos.css). El verde (EXITO) queda solo para «al día», «pagada» y «activa».
FONDO = '#0b0b10'
SUPERFICIE = '#13121a'
SUPERFICIE_2 = '#1c1b24'
BORDE = '#26252e'
BORDE_FUERTE = '#3a3845'
TEXTO = '#f4f2f7'
TEXTO_SUAVE = '#a8a4b3'
TEXTO_TENUE = '#8a8696'
ROJO = '#ef4444'
ROSA = '#e0246e'
VIOLETA = '#7c4dff'
VIOLETA_CLARO = '#b9a3ff'
EXITO = '#7ee2a8'
AVISO = '#ffa463'
PELIGRO = '#ff6b6b'
ENCIMA = '#1a1922'           # la fila que está bajo el mouse
ELEGIDA = '#2a2049'          # la fila elegida (violeta oscuro, sin transparencias que se sumen) y su raya de abajo
ELEGIDA_BORDE = '#3a2c66'
# Radios, en una escala de cuatro: tarjetas y panel 12, cajas dentro de una tarjeta 10, botones y campos 8, chicos 6.
# Los espacios van en la grilla de 4 px (tarjetas con 20 de lado y 16 arriba y abajo; 16 entre una tarjeta y otra).
RADIO, RADIO_CAJA, RADIO_CONTROL, RADIO_CHICO = 12, 10, 8, 6
FUENTES = ['Inter', 'Segoe UI', 'Helvetica Neue']     # (las dos últimas: respaldo en Windows y en Mac)
MONO = ['Cascadia Mono', 'Consolas', 'Menlo']

ESTADOS_VENTA = {'pagado': ('Pagada', EXITO), 'reembolsado': ('Reembolsada', AVISO), 'pendiente': ('Pendiente', TEXTO_SUAVE)}
# El estado de un cupón (estado_cupon() de cupones.php): solo «activo» sirve en la web
ESTADOS_CUPON = {'activo': ('Activo', EXITO), 'pausado': ('Pausado', TEXTO_SUAVE), 'vencido': ('Vencido', AVISO),
                 'agotado': ('Agotado', AVISO)}
BLOQUEOS_CANJE = {None: ('Vigente', VIOLETA_CLARO), 'reembolsada': ('Reembolsada', AVISO),
                  'disputa': ('En disputa', PELIGRO), 'desactivada': ('Desactivada', AVISO), 'revocada': ('Revocada', PELIGRO)}
FILTROS_VENTAS = [('Pagadas y reembolsadas', ''), ('Solo pagadas', 'pagado'), ('Solo reembolsadas', 'reembolsado'),
                  ('Pagos sin completar', 'pendiente'), ('Todas', 'todos'), ('Eliminadas', 'eliminadas')]
FILTROS_FECHA = [('Hoy', 1), ('7 días', 7), ('30 días', 30), ('Todo', 0)]   # días hacia atrás, contando hoy (0 = todo)
# Estado de la versión de un equipo (lo calcula admin.php; 'desconocido' = no se sabe cuál es la última)
ESTADOS_VERSION = {'al_dia': ('Al día', EXITO), 'desactualizado': ('Desactualizado', AVISO),
                   'sin_datos': ('Sin datos', TEXTO_TENUE), 'desconocido': ('Sin comparar', TEXTO_SUAVE)}
# Los filtros de la página Versiones (cuentan clientes con la licencia activa; «Todos», también los bloqueados)
FILTROS_VERSION = [('Todos', 'todos'), ('Desactualizados', 'desactualizado'), ('Al día', 'al_dia'), ('Sin datos', 'sin_datos')]
# Por qué no salió un aviso de actualización (motivo de avisar_actualizacion y de la tabla avisos)
MOTIVOS_AVISO = {None: ('Enviado', VIOLETA_CLARO), 'ya_avisado': ('Ya avisado', TEXTO_SUAVE),
                 'baja': ('Dado de baja', AVISO), 'sin_correo': ('Sin correo', AVISO), 'bloqueada': ('Bloqueada', PELIGRO),
                 'limite': ('Tope por hora', AVISO), 'fallo_envio': ('Falló el envío', PELIGRO)}
FILTROS_AVISOS = [('Todos', ''), ('Enviados', 'ok'), ('No enviados', 'no')]
# Los errores de los clientes (errores.php): cómo se llama cada nivel y su color, y los filtros de la página Errores
NIVELES_ERROR = {'error': ('Error', PELIGRO), 'aviso': ('Aviso', AVISO)}
FILTROS_ERRORES = [('Sin ver', 'sin_ver'), ('Todos', 'todos')]
VISTAS_ERRORES = [('Por cliente', 'usuario'), ('Lista', 'lista')]   # (2.3: el valor «usuario» se queda)
# Eventos del historial: ícono y color de cada tipo
TIPOS_EVENTO = {'compra': ('carrito', TEXTO_SUAVE), 'pago': ('tarjeta', EXITO), 'correo': ('correo', VIOLETA_CLARO),
                'canje': ('regalo', VIOLETA_CLARO), 'activacion': ('equipo', VIOLETA_CLARO),
                'version': ('subir', VIOLETA_CLARO), 'uso': ('reloj', TEXTO_SUAVE), 'admin': ('usuario', TEXTO_SUAVE),
                'aviso': ('megafono', ROSA), 'reembolso': ('reembolso', AVISO)}
DIAS_SEMANA = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']
# Lo que dice Recurrente, en español
ESTADOS_RECURRENTE = {'paid': 'Pagado', 'unpaid': 'Sin pagar', 'pending': 'Pendiente', 'expired': 'Vencido',
                      'refunded': 'Reembolsado', 'partially_refunded': 'Reembolso parcial', 'disputed': 'En disputa',
                      'failed': 'Fallido', 'succeeded': 'Exitoso', 'canceled': 'Cancelado', 'cancelled': 'Cancelado',
                      'voided': 'Anulado', 'processing': 'Procesando', 'requires_action': 'Requiere acción'}
SIMBOLOS = {'USD': '$', 'GTQ': 'Q', 'MXN': '$', 'EUR': '€', 'COP': '$', 'PEN': 'S/', 'CRC': '₡', 'HNL': 'L',
            'NIO': 'C$', 'DOP': 'RD$', 'ARS': '$', 'CLP': '$'}
MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
# Un correo como lo acepta FILTER_VALIDATE_EMAIL de PHP (sin comillas: correo_valido() de admin.php ya las descarta).
# Usuario de hasta 64 letras, dominio con al menos un punto y cada parte de menos de 64. Se usa con fullmatch.
_ATEXTO = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
CORREO_VALIDO = re.compile(rf'(?![^@]{{65}}){_ATEXTO}(?:\.{_ATEXTO})*@(?!.*[^.]{{64}})'
                           r'(?:[A-Za-z0-9]+(?:-+[A-Za-z0-9]+)*\.)+[A-Za-z][A-Za-z0-9]*(?:-+[A-Za-z0-9]+)*')
# La versión de CineCaptions como la entiende version_normal() de telemetria.php: dos o tres números de hasta 4 cifras
VERSION_VALIDA = re.compile(r'[ \t\n\r\f\v]*([0-9]{1,4})\.([0-9]{1,4})(?:\.([0-9]{1,4}))?[ \t\n\r\f\v]*')


# ---------------------------------------------------------------- Utilidades

def carpeta_programa():
    """Desde dónde corre la app: la carpeta del .exe (compilada con PyInstaller, la de la instalación) o la de ventas.py."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def carpeta_instalacion():
    """Donde la deja el instalador (solo para este usuario de Windows): %LOCALAPPDATA%\\Programs\\CineCaptions Ventas.
    En Mac, la app arrastrada a Aplicaciones: /Applications/CineCaptions Ventas.app (el ejecutable va en Contents/MacOS)."""
    if sys.platform == 'darwin':
        return Path('/Applications') / f'{APP}.app' / 'Contents' / 'MacOS'
    return Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'Programs' / APP


def instalada():
    """¿Es la copia instalada? (no un .exe suelto ni ventas.py). En Mac: una .app dentro de Aplicaciones."""
    if not getattr(sys, 'frozen', False):
        return False
    try:
        if sys.platform == 'darwin':
            return carpeta_programa().as_posix().endswith('.app/Contents/MacOS') and \
                carpeta_programa().as_posix().startswith(('/Applications/', str(Path.home() / 'Applications') + '/'))
        return carpeta_programa() == carpeta_instalacion().resolve()
    except OSError:
        return False


def recurso(nombre):
    """Archivo incluido en el programa. PyInstaller deja los archivos en sys._MEIPASS: la carpeta temporal donde se
    descomprime (exe de un solo archivo) o la carpeta _internal junto al .exe (instalada, «onedir»). Si no está ahí, se
    busca en _internal y junto al .exe (por si se armó de otra forma) y, sin compilar, junto a ventas.py."""
    carpetas = [Path(sys._MEIPASS)] if getattr(sys, '_MEIPASS', None) else []
    if getattr(sys, 'frozen', False):
        exe = Path(sys.executable).resolve().parent
        carpetas += [exe / '_internal', exe]
    carpetas.append(Path(__file__).resolve().parent)
    for carpeta in carpetas:
        if (carpeta / nombre).exists():
            return carpeta / nombre
    return carpetas[0] / nombre


def entero(valor, defecto=0):
    """Entero de lo que mande la API: PDO a veces manda «2900» como texto."""
    if valor is None or valor == '':
        return defecto
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, int):
        return valor
    try:
        return int(str(valor).strip())
    except ValueError:
        try:
            return int(float(str(valor).strip()))
        except ValueError:
            return defecto


def entero_o_nada(valor):
    return None if valor is None or valor == '' else entero(valor)


def texto_o_nada(valor):
    return None if valor is None else str(valor)


def plural(n, uno, varios):
    return f'{n:,} {uno if n == 1 else varios}'


def partible(texto, largo=22):
    """Deja que una palabra muy larga (un correo, el nombre de un equipo) se corte en varias líneas: le pone un espacio
    de ancho cero después de @ . _ - / y, si aún queda un pedazo largo, cada «largo» letras. Solo para textos que no se
    copian (el espacio invisible se copiaría con el texto)."""
    def partir(m):
        palabra = m.group(0)
        if len(palabra) <= largo:
            return palabra
        palabra = re.sub(r'([@._/-])', '\\1\u200b', palabra)
        return re.sub('[^\u200b]{%d}(?=[^\u200b])' % largo, lambda t: t.group(0) + '\u200b', palabra)
    return re.sub(r'\S+', partir, texto or '')


def ruta_partible(ruta):
    """Una ruta de Windows que se puede cortar en varias líneas después de cada «\\» (con un espacio de ancho cero, como
    partible: solo para mostrarla, el espacio invisible se copiaría con el texto)."""
    return str(ruta).replace('\\', '\\​')


def dinero(centavos, moneda='USD'):
    """2900 → «$29.00 USD». Con enteros, sin redondeos de float."""
    if centavos is None:
        return '—'
    moneda = (moneda or 'USD').upper()
    enteros, resto = divmod(abs(int(centavos)), 100)
    return f"{'-' if centavos < 0 else ''}{SIMBOLOS.get(moneda, '')}{enteros:,}.{resto:02d} {moneda}"


def dinero_html(centavos, moneda='USD'):
    """El monto grande y la moneda en chico y más tenue, para las tarjetas del resumen."""
    numero, _, codigo = dinero(centavos, moneda).rpartition(' ')
    return (f'{html.escape(numero)}<span style="font-size:13px; font-weight:500; color:{TEXTO_TENUE}">'
            f'&nbsp;{html.escape(codigo)}</span>')


def numero_html(n, unidad=''):
    extra = (f'<span style="font-size:13px; font-weight:500; color:{TEXTO_TENUE}">&nbsp;{html.escape(unidad)}</span>'
             if unidad else '')
    return f'{n:,}{extra}'


class Reloj:
    """Las fechas de la API vienen en la hora de MySQL (NOW()), que en el hosting suele ser UTC. Con «hora_servidor» del
    resumen se mide la diferencia entre MySQL y la hora UTC de esta PC, y todas las fechas se muestran en la hora de esta
    PC: así «Hoy, 15:30» es la hora en que de verdad pagó el cliente (y una venta de las 7 de la noche no sale como
    «mañana a la 1:00»)."""
    desfase = None   # hora de MySQL − hora UTC, en múltiplos de 15 min (None mientras no llegue el primer resumen)
    fijo = None      # solo para las pruebas: «ahora» en hora UTC
    local = None     # solo para las pruebas: la zona horaria de esta PC (None = la de Windows)

    @classmethod
    def utc(cls):
        return cls.fijo or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    @classmethod
    def ajustar(cls, hora_servidor):
        fecha = fecha_mysql(hora_servidor)
        if fecha:
            cuartos = round((fecha - cls.utc()).total_seconds() / 900)
            cls.desfase = dt.timedelta(minutes=15 * cuartos)

    @classmethod
    def ahora(cls):
        """Ahora, en la hora de esta PC."""
        return utc_a_local(cls.utc())

    @classmethod
    def zona(cls):
        """La zona horaria de MySQL: «UTC», «UTC−6»... ('' mientras no se sepa)."""
        if cls.desfase is None:
            return ''
        minutos = round(cls.desfase.total_seconds() / 60)
        if not minutos:
            return 'UTC'
        horas, resto = divmod(abs(minutos), 60)
        return f"UTC{'+' if minutos > 0 else '−'}{horas}" + (f':{resto:02d}' if resto else '')


def fecha_mysql(valor):
    """«2026-10-29 14:05:00» tal como viene de MySQL (sin zona horaria) → datetime, o None."""
    try:
        return dt.datetime.strptime(str(valor).strip()[:19], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None


def utc_a_local(fecha):
    """datetime en hora UTC (sin zona) → la misma hora en esta PC (sin zona)."""
    try:
        con_zona = fecha.replace(tzinfo=dt.timezone.utc)
        return (con_zona.astimezone(Reloj.local) if Reloj.local else con_zona.astimezone()).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        return fecha


def leer_fecha(valor, utc=False):
    """Fecha de la API → datetime en la hora de esta PC.
    «2026-10-29 14:05:00» viene en la hora de MySQL (utc=True para fecha_venta, que admin.php guarda con gmdate);
    las fechas ISO 8601 de Recurrente traen su propia zona."""
    if not valor:
        return None
    texto = str(valor).strip()
    fecha = fecha_mysql(texto)
    if fecha:
        if not utc:
            if Reloj.desfase is None:   # todavía no se sabe la zona del servidor: tal cual
                return fecha
            try:
                fecha -= Reloj.desfase
            except OverflowError:
                return fecha
        return utc_a_local(fecha)
    try:
        fecha = dt.datetime.fromisoformat(texto.replace('Z', '+00:00'))
    except ValueError:
        return None
    return utc_a_local(fecha.astimezone(dt.timezone.utc).replace(tzinfo=None)) if fecha.tzinfo else fecha


def fecha_corta(valor, utc=False):
    """«Hoy, 14:05», «Ayer, 09:12», «27 oct, 18:40» o, si es de otro año, «12 dic 2025» (sin la hora: así cabe en la
    columna; la fecha completa queda en el tooltip)."""
    fecha = leer_fecha(valor, utc)
    if not fecha:
        return '—'
    hoy = Reloj.ahora().date()
    hora = fecha.strftime('%H:%M')
    if fecha.date() == hoy:
        return f'Hoy, {hora}'
    if fecha.date() == hoy - dt.timedelta(days=1):
        return f'Ayer, {hora}'
    if fecha.year == hoy.year:
        return f'{fecha.day} {MESES[fecha.month - 1]}, {hora}'
    return f'{fecha.day} {MESES[fecha.month - 1]} {fecha.year}'


def fecha_larga(valor, utc=False):
    fecha = leer_fecha(valor, utc)
    return f'{fecha.day} {MESES[fecha.month - 1]} {fecha.year}, {fecha:%H:%M}' if fecha else '—'


def fecha_dia(valor, utc=False):
    fecha = leer_fecha(valor, utc)
    return f'{fecha.day} {MESES[fecha.month - 1]} {fecha.year}' if fecha else '—'


def fecha_dia_corta(valor, utc=False):
    """«27 oct» (o «27 oct 2025» si es de otro año)."""
    fecha = leer_fecha(valor, utc)
    if not fecha:
        return '—'
    return f'{fecha.day} {MESES[fecha.month - 1]}' + ('' if fecha.year == Reloj.ahora().year else f' {fecha.year}')


def fecha_frase(valor, utc=False):
    """La fecha para meterla en una frase: «hoy a las 14:05», «ayer a las 09:12», «el 27 oct a las 18:40»."""
    fecha = leer_fecha(valor, utc)
    if not fecha:
        return ''
    hoy = Reloj.ahora().date()
    hora = f"a la{'' if fecha.hour == 1 else 's'} {fecha:%H:%M}"
    if fecha.date() == hoy:
        return f'hoy {hora}'
    if fecha.date() == hoy - dt.timedelta(days=1):
        return f'ayer {hora}'
    return f'el {fecha_dia_corta(valor, utc)} {hora}'


def fecha_csv(valor, utc=False):
    """La fecha en la hora de esta PC, como la entiende Excel («2026-10-29 15:30:00»); vacía si no hay."""
    fecha = leer_fecha(valor, utc)
    return f'{fecha:%Y-%m-%d %H:%M:%S}' if fecha else ''


def hace(valor, utc=False):
    """«hace 5 min», «hace 2 h», «ayer», «hace 3 días». utc: la fecha viene en UTC (ficha_cuando), no en la hora de MySQL."""
    fecha = leer_fecha(valor, utc)
    if not fecha:
        return '—'
    ahora = Reloj.ahora()
    segundos = (ahora - fecha).total_seconds()
    if segundos < 90:
        return 'hace 1 min'   # (corto: «hace un momento» no cabía en la columna «Último uso»)
    if segundos < 3600:
        return f'hace {int(segundos // 60)} min'
    if segundos < 86400 and fecha.date() == ahora.date():
        return f'hace {int(segundos // 3600)} h'
    dias = (ahora.date() - fecha.date()).days
    if dias <= 1:
        return 'ayer'
    if dias < 30:
        return f'hace {dias} días'
    return fecha_dia(valor, utc)


def uso_texto(valor):
    """«Usado hace 5 min», «Usado ayer», «Usado el 12 dic 2025» (o «Sin usar» si no hay fecha)."""
    texto = hace(valor)
    if texto == '—':
        return 'Sin usar'
    return f'Usado {texto}' if texto.startswith('hace') or texto == 'ayer' else f'Usado el {texto}'


def id_corto(equipo):
    """Huella del equipo acortada: «3c1f9a…e07b»."""
    equipo = str(equipo or '')
    return equipo if len(equipo) <= 12 else f'{equipo[:5]}…{equipo[-4:]}'


def nombre_pc(equipo):
    """«DESKTOP-7Q2KD1F · 3F2A-91BC-04DE-77A1», como lo manda CineCaptions → «DESKTOP-7Q2KD1F» (la huella ya se muestra
    aparte)."""
    nombre = ' '.join(str(equipo.get('nombre_equipo') or '').split())
    huella = str(equipo.get('equipo') or '').strip()
    if huella and nombre.endswith(huella) and len(nombre) > len(huella):
        nombre = nombre[:-len(huella)].rstrip(' ·-–|').strip()
    return nombre or 'Equipo sin nombre'


def correo_valido(correo):
    """El correo sin espacios en los bordes si admin.php lo acepta (correo_valido() de avisos_correo.php: hasta 190
    caracteres, sin espacios, comillas ni <>,; y lo que pide FILTER_VALIDATE_EMAIL); None si no."""
    correo = correo.strip(' \t\n\r\0\x0b') if isinstance(correo, str) else ''
    return correo if len(correo) <= 190 and CORREO_VALIDO.fullmatch(correo) else None


def texto_so(so):
    """El sistema que manda CineCaptions (desde la 5.55), un poco más legible: «windows» → «Windows»."""
    so = ' '.join(str(so or '').split())[:60]
    bajo = so.casefold()
    if bajo in ('windows', 'win', 'win32', 'win64', 'nt'):
        return 'Windows'
    if bajo in ('darwin', 'mac', 'macos', 'osx', 'mac os x'):
        return 'macOS'
    return so or None


# ---------------------------------------------------------------- Versiones de CineCaptions

def partes_version(texto):
    """«5.54», «5.54.0», «5.5.3» → (5, 54), (5, 54), (5, 5, 3), para comparar por números: 5.54 == 5.54.0 y
    5.5.3 < 5.20. Entiende lo mismo que admin.php (VERSION_VALIDA): None si no, por ejemplo «5.6-beta», «v5.54» o
    «5.54.0.1» (cuenta como «sin datos» y no se puede anunciar)."""
    m = VERSION_VALIDA.fullmatch(str(texto or ''))
    if not m:
        return None
    partes = [int(p) for p in m.groups() if p is not None]
    while len(partes) > 1 and partes[-1] == 0:
        partes.pop()
    return tuple(partes)


def texto_version(texto):
    """La versión como se muestra: «5.54.0» → «5.54» (así la del version.json y la del programa salen iguales).
    None si no se entiende."""
    partes = partes_version(texto)
    if partes is None:
        return None
    return '.'.join(str(p) for p in (partes + (0,) if len(partes) == 1 else partes))


def estado_de_version(version, ultima):
    """'al_dia' | 'desactualizado' | 'sin_datos' | 'desconocido' (no se sabe cuál es la última), igual que admin.php."""
    propia = partes_version(version)
    if propia is None:
        return 'sin_datos'
    nueva = partes_version(ultima)
    if nueva is None:
        return 'desconocido'
    return 'al_dia' if propia >= nueva else 'desactualizado'


def estado_fila_version(fila, ultima):
    """Estado de la versión de una venta o un canje. Es «desactualizado» si algún equipo de la licencia tiene una versión
    vieja, aunque el que se usó más recientemente ya esté al día. None si la licencia no tiene equipos."""
    if fila.get('licencia_id') is None or not fila.get('equipos'):
        return None
    if (fila.get('equipos_desactualizados') or 0) > 0:
        return 'desactualizado'
    return estado_de_version(fila.get('version'), ultima)


def venta_eliminada(venta):
    """¿La venta está quitada de la lista y de los totales? (eliminar_venta de admin.php: no se borra, se puede restaurar).
    Como VENTA_VISIBLE de admin.php: un pago sin completar que se eliminó y que el cliente pagó DESPUÉS vuelve solo."""
    eliminada = (venta or {}).get('eliminada')
    if not eliminada:
        return False
    pagado = venta.get('pagado')
    return not (pagado and str(pagado) > str(eliminada))


def es_local(host):
    host = (host or '').strip('[]').lower()
    if host == 'localhost' or host.endswith('.localhost'):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validar_api(url):
    """La dirección de la API ya limpia, o ValueError con el motivo."""
    url = (url or '').strip()
    partes = urllib.parse.urlsplit(url)
    if partes.scheme not in ('https', 'http') or not partes.hostname:
        raise ValueError('Escribe la dirección completa, por ejemplo ' + API_POR_DEFECTO)
    if partes.scheme == 'http' and not es_local(partes.hostname):
        raise ValueError('Usa https://. Con http:// la clave de administrador viajaría sin cifrar.')
    return url


def problema_clave(clave):
    """Por qué una clave pegada no sirve (o None si se ve bien)."""
    if not clave:
        return 'Pega la clave para continuar.'
    if any(c.isspace() for c in clave):
        return 'La clave no lleva espacios. Revisa que la copiaste completa.'
    if not all(33 <= ord(c) < 127 for c in clave):
        return 'La clave tiene caracteres que no son válidos. Cópiala otra vez del archivo.'
    if len(clave) < 8:
        return 'La clave es demasiado corta. Revisa que la copiaste completa.'
    return None


def extraer_clave(texto):
    """La clave de administrador de un archivo de texto: sola en una línea o como «Clave: …»."""
    candidatas = []
    for linea in texto.replace('﻿', '').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith(('#', '//', ';')):
            continue
        m = re.match(r'^([^\W\d_][\w .()\-]{0,80}?)\s*[:=]\s*(\S+)$', linea)
        if m and re.search(r'clave|key|token|admin|contrase|password', m.group(1), re.IGNORECASE):
            linea = m.group(2)
        if re.search(r'\s', linea) or '://' in linea:
            continue
        candidatas.append(linea)
    if not candidatas:
        raise ValueError('No encontré una clave en ese archivo.')
    largas = [c for c in candidatas if len(c) >= 16]
    return (largas or candidatas)[0]


def leer_texto(ruta):
    """Texto de un archivo, sea UTF-8 (con o sin BOM), UTF-16 (el «Unicode» del Bloc de notas) o ANSI."""
    datos = Path(ruta).read_bytes()
    if datos[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return datos.decode('utf-16')
    try:
        return datos.decode('utf-8-sig')
    except UnicodeDecodeError:
        return datos.decode('cp1252', errors='replace')


# ---------------------------------------------------------------- Clave cifrada con DPAPI de Windows

class _Blob(ctypes.Structure):
    _fields_ = [('cbData', ctypes.c_uint32), ('pbData', ctypes.POINTER(ctypes.c_char))]


CRYPTPROTECT_UI_FORBIDDEN = 0x01
_ENTROPIA = b'CineCaptions Ventas / clave de administrador'


def _dpapi(datos, cifrar):
    """CryptProtectData / CryptUnprotectData: el resultado solo lo puede abrir este usuario de Windows."""
    if os.name != 'nt':
        raise OSError('El cifrado de la clave (DPAPI) solo existe en Windows.')
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    funcion = crypt32.CryptProtectData if cifrar else crypt32.CryptUnprotectData
    funcion.argtypes = [ctypes.POINTER(_Blob), ctypes.c_wchar_p if cifrar else ctypes.c_void_p, ctypes.POINTER(_Blob),
                        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(_Blob)]
    funcion.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buf_datos = ctypes.create_string_buffer(datos, len(datos))
    buf_entropia = ctypes.create_string_buffer(_ENTROPIA, len(_ENTROPIA))
    entrada = _Blob(len(datos), ctypes.cast(buf_datos, ctypes.POINTER(ctypes.c_char)))
    entropia = _Blob(len(_ENTROPIA), ctypes.cast(buf_entropia, ctypes.POINTER(ctypes.c_char)))
    salida = _Blob()
    if not funcion(ctypes.byref(entrada), APP if cifrar else None, ctypes.byref(entropia), None, None,
                   CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(salida)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(salida.pbData, salida.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(salida.pbData, ctypes.c_void_p))


def cifrar_clave(clave):
    return base64.b64encode(_dpapi(clave.encode('utf-8'), True)).decode('ascii')


def descifrar_clave(guardada):
    return _dpapi(base64.b64decode(guardada), False).decode('utf-8')


def carpeta_config():
    if os.environ.get('CC_VENTAS_CONFIG'):   # las pruebas (Windows y Mac) usan una carpeta aparte, nunca la real
        return Path(os.environ['CC_VENTAS_CONFIG'])
    if os.name == 'nt':
        return Path(os.environ.get('APPDATA') or Path.home() / 'AppData' / 'Roaming') / APP
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / APP
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / APP


# En Mac (y Linux) la clave va en el llavero del sistema (keyring: el Llavero de macOS); config.json solo dice «llavero»
EN_LLAVERO = 'llavero'


def servicio_llavero():
    """Nombre de la entrada del Llavero (las pruebas usan otro con CC_VENTAS_LLAVERO: nunca pisan la clave real)."""
    return os.environ.get('CC_VENTAS_LLAVERO') or APP


def _llavero():
    """El módulo keyring, o None si no está (sin él, en Mac la clave no se puede guardar y se pide cada vez)."""
    try:
        import keyring
        return keyring
    except Exception:
        return None


class Configuracion:
    """%APPDATA%\\CineCaptions Ventas\\config.json: dirección de la API, clave cifrada y preferencias de la ventana.
    En Mac: ~/Library/Application Support/CineCaptions Ventas/config.json y la clave en el Llavero."""

    def __init__(self):
        self.ruta = carpeta_config() / 'config.json'
        try:
            self.datos = json.loads(self.ruta.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.datos = {}
        if not isinstance(self.datos, dict):
            self.datos = {}

    def guardar(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_suffix('.tmp')
        temporal.write_text(json.dumps(self.datos, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporal, self.ruta)

    @property
    def api(self):
        url = self.datos.get('api')
        if isinstance(url, str) and url.strip():
            try:
                return validar_api(url)   # un config.json editado a mano nunca manda la clave por http://
            except ValueError:
                pass
        return API_POR_DEFECTO

    def guardar_api(self, url):
        if url == API_POR_DEFECTO:
            self.datos.pop('api', None)
        else:
            self.datos['api'] = url
        self.guardar()

    def leer_clave(self):
        guardada = self.datos.get('clave')
        if not guardada or not isinstance(guardada, str):
            return None
        if guardada == EN_LLAVERO:
            llavero = _llavero()
            try:
                return (llavero.get_password(servicio_llavero(), 'administrador') or None) if llavero else None
            except Exception:   # Llavero bloqueado o sin permiso: se vuelve a pedir
                return None
        try:
            return descifrar_clave(guardada)
        except (OSError, ValueError, TypeError):   # cifrada por otro usuario de Windows o dañada: se vuelve a pedir
            return None

    def guardar_clave(self, clave):
        if os.name == 'nt':
            self.datos['clave'] = cifrar_clave(clave)
        else:
            llavero = _llavero()
            if llavero is None:
                raise OSError('falta el módulo keyring para usar el Llavero')
            try:
                llavero.set_password(servicio_llavero(), 'administrador', clave)
            except Exception as e:
                raise OSError(str(e)) from e
            self.datos['clave'] = EN_LLAVERO
        self.guardar()


# ---------------------------------------------------------------- CSV para Excel

def separadores_excel():
    """Separador de lista y decimal de la configuración regional de Windows (los que usa Excel al abrir un CSV)."""
    lista, decimal = ',', '.'
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Control Panel\International') as llave:
            lista = winreg.QueryValueEx(llave, 'sList')[0] or ','
            decimal = winreg.QueryValueEx(llave, 'sDecimal')[0] or '.'
    except (OSError, ImportError):
        pass
    if lista not in (',', ';', '\t', '|'):
        lista = ','
    if decimal not in ('.', ',') or decimal == lista:
        decimal = '.' if lista != '.' else ','
    return lista, decimal


def celda_csv(valor):
    """Texto seguro para Excel: lo que escribió un cliente nunca se toma como fórmula (=, +, -, @)."""
    texto = '' if valor is None else str(valor)
    return "'" + texto if texto[:1] in ('=', '+', '-', '@', '\t', '\r') else texto


def monto_csv(centavos, decimal='.'):
    if centavos is None:
        return ''
    enteros, resto = divmod(abs(int(centavos)), 100)
    return f"{'-' if centavos < 0 else ''}{enteros}{decimal}{resto:02d}"


def texto_licencia(estado):
    if not estado:
        return ''
    return 'Activa' if estado == 'activa' else 'Bloqueada'


def _columnas_version(f):
    """Las tres columnas de versión que llevan al final las ventas y los canjes."""
    if f.get('licencia_id') is None:
        return ['', '', '']
    return [celda_csv(texto_version(f.get('version')) or f.get('version') or ''), fecha_csv(f.get('ultima_vez')),
            '' if f.get('equipos_desactualizados') is None else f['equipos_desactualizados']]


def escribir_csv(ruta, filas, tipo, separadores=None):
    """Guarda las filas (ventas, canjes o equipos con su versión) en un CSV UTF-8 con BOM, para que Excel muestre bien
    las tildes. Las columnas nuevas van al final: así un Excel armado con el CSV de antes sigue sirviendo."""
    lista, decimal = separadores or separadores_excel()
    with open(ruta, 'w', newline='', encoding='utf-8-sig') as archivo:
        w = csv.writer(archivo, delimiter=lista)
        if tipo == 'ventas':
            w.writerow(['Pedido', 'Fecha de pago', 'Fecha de creación', 'Estado', 'Cliente', 'Correo', 'Monto', 'Moneda',
                        'Clave', 'Licencia', 'Equipos', 'Límite', 'Checkout de Recurrente', 'Correo con la clave',
                        'Versión', 'Último uso', 'Equipos desactualizados', 'Cupón', 'Descuento'])
            for v in filas:
                w.writerow([v['id'], fecha_csv(v['pagado']), fecha_csv(v['creado']), ESTADOS_VENTA.get(v['estado'], (v['estado'] or '',))[0],
                            celda_csv(v['nombre']), celda_csv(v['correo']), monto_csv(v['monto'], decimal), v['moneda'] or '',
                            celda_csv(v['clave']), texto_licencia(v['licencia_estado']),
                            '' if v['licencia_id'] is None else v['equipos'], '' if v['limite'] is None else v['limite'],
                            celda_csv(v['checkout_id']),
                            ('Enviado' if v['correo_enviado'] else 'No enviado') if v['estado'] != 'pendiente' else '']
                           + _columnas_version(v)
                           + [celda_csv(v.get('cupon') or ''),
                              monto_csv(v['descuento'], decimal) if v.get('cupon') and v.get('descuento') is not None else ''])
        elif tipo == 'canjes':
            w.writerow(['Canje', 'Fecha del canje', 'Venta en Gumroad', 'Estado en Gumroad', 'Cliente', 'Correo', 'Clave',
                        'Licencia', 'Equipos', 'Límite', 'Último canje', 'Versión', 'Último uso', 'Equipos desactualizados'])
            for c in filas:
                w.writerow([c['id'], fecha_csv(c['creado']), fecha_csv(c['fecha_venta'], utc=True),
                            celda_csv(BLOQUEOS_CANJE.get(c['bloqueo'], (c['bloqueo'],))[0]),
                            celda_csv(c['nombre']), celda_csv(c['correo']), celda_csv(c['clave']),
                            texto_licencia(c['licencia_estado']), '' if c['licencia_id'] is None else c['equipos'],
                            '' if c['limite'] is None else c['limite'], fecha_csv(c['ultimo'])] + _columnas_version(c))
        else:
            w.writerow(['Cliente', 'Correo', 'Clave', 'Licencia', 'Origen', 'Pedido', 'Equipo', 'ID del equipo', 'Versión',
                        'Estado de la versión', 'Desde', 'Versión anterior', 'Sistema', 'Activado', 'Último uso',
                        'Aviso enviado', 'Fecha del aviso'])
            for e in filas:
                w.writerow([celda_csv(e['cliente']), celda_csv(e['correo']), celda_csv(e['clave']),
                            texto_licencia(e['licencia_estado']),
                            {'compra': 'Compra', 'canje': 'Canje de Gumroad'}.get(e['origen'], ''),
                            '' if e['pedido_id'] is None else e['pedido_id'], celda_csv(nombre_pc(e)), celda_csv(e['equipo']),
                            celda_csv(texto_version(e['version']) or e['version'] or ''),
                            ESTADOS_VERSION.get(e['estado_version'], ('',))[0], fecha_csv(e['version_desde']),
                            celda_csv(texto_version(e['version_anterior']) or e['version_anterior'] or ''),
                            celda_csv(texto_so(e['so']) or ''), fecha_csv(e['creada']), fecha_csv(e['ultima']),
                            celda_csv(texto_version(e['aviso_version']) or e['aviso_version'] or ''),
                            fecha_csv(e['aviso_fecha'])])
    return len(filas)


# ---------------------------------------------------------------- API (pagos/admin.php)

class ApiError(Exception):
    """Error de la API con un mensaje listo para mostrar (codigo = estado HTTP, 0 si no hubo conexión)."""

    def __init__(self, mensaje, codigo=0, detalle='', reintentar=None):
        super().__init__(mensaje)
        self.mensaje, self.codigo, self.detalle, self.reintentar = mensaje, codigo, detalle, reintentar

    @property
    def desconocida(self):
        """El servidor publicado todavía no tiene esa acción (es el admin.php anterior)."""
        return self.codigo == 400 and 'acción desconocida' in self.mensaje.casefold()


class Cancelada(Exception):
    """Una petición que ni salió: otra igual más nueva la reemplazó mientras esperaba su turno en la cola."""


FALTA_SERVIDOR = 'Esto necesita el servidor nuevo: falta subir pagos/admin.php.'


def mensaje_de(error):
    if isinstance(error, ApiError):
        return error.mensaje
    return f'Ocurrió un error inesperado: {error}'


def _mensaje_red(motivo):
    if isinstance(motivo, (TimeoutError, socket.timeout)) or 'timed out' in str(motivo).lower():
        return 'El servidor tardó demasiado en responder. Revisa tu conexión e intenta de nuevo.'
    if isinstance(motivo, ssl.SSLError):
        return ('No se pudo comprobar la conexión segura con el servidor (certificado). '
                'Revisa que la fecha y la hora de esta PC estén bien.')
    if isinstance(motivo, socket.gaierror):
        return 'No se encontró el servidor. Revisa tu conexión a internet.'
    if isinstance(motivo, ConnectionRefusedError):
        return 'El servidor rechazó la conexión. Revisa la dirección de la API o tu conexión a internet.'
    return 'No se pudo conectar con el servidor. Revisa tu conexión a internet.'


def _error_http(codigo, servidor, cabeceras):
    """Mensaje claro, en español, para cada respuesta de error de admin.php."""
    if codigo == 401:
        return ApiError('La clave de administrador no es correcta. Cámbiala en Configuración → Cambiar clave.', 401,
                        servidor or '')
    if codigo == 429:
        segundos = entero(cabeceras.get('Retry-After') if cabeceras else None, 900) or 900
        minutos = max(1, round(segundos / 60))
        return ApiError(f'Demasiados intentos con una clave incorrecta. Espera {minutos} minutos y vuelve a intentarlo.',
                        429, servidor or '', segundos)
    if codigo == 503:
        return ApiError(servidor or 'El servidor no está disponible en este momento. Intenta de nuevo en unos minutos.', 503)
    if codigo == 500:
        return ApiError('El servidor tuvo un error interno. Intenta de nuevo en un momento.', 500, servidor or '')
    if codigo == 405:
        return ApiError('El servidor no aceptó la petición. Revisa la dirección de la API en Configuración.', 405)
    if codigo == 404 and not servidor:
        return ApiError('No se encontró la API en esa dirección. Comprueba que admin.php esté subido al servidor.', 404)
    if 300 <= codigo < 400:
        destino = (cabeceras.get('Location') if cabeceras else None) or 'otra dirección'
        return ApiError(f'El servidor redirigió la petición a {destino}. La app no la sigue, para no mandar la clave a otro '
                        'lugar: revisa la dirección de la API en Configuración.', codigo)
    if codigo == 200:
        return ApiError('El servidor respondió algo inesperado. Revisa la dirección de la API en Configuración.', 200)
    if servidor:
        return ApiError(str(servidor), codigo)
    return ApiError(f'El servidor respondió con un error ({codigo}). Intenta de nuevo en un momento.', codigo)


def _normalizar(fila, enteros=(), opcionales=(), textos=()):
    """Convierte los campos al tipo correcto (los números pueden venir como texto)."""
    if not isinstance(fila, dict):
        return None
    fila = dict(fila)
    for campo in enteros:
        fila[campo] = entero(fila.get(campo))
    for campo in opcionales:
        fila[campo] = entero_o_nada(fila.get(campo))
    for campo in textos:
        fila[campo] = texto_o_nada(fila.get(campo))
    return fila


# Lo que añadió el servidor nuevo a cada venta y cada canje (con el anterior llegan en None: «sin datos»)
_ENTEROS_VERSION = ('equipos_desactualizados',)
_TEXTOS_VERSION = ('version', 'ultima_vez')


def normalizar_venta(v):
    # («eliminada»: cuándo se quitó de la lista desde la app; None si no, o con un admin.php que todavía no lo manda)
    # (2.8: «cupon», el código con que se compró, y «descuento», en centavos; None sin cupón o con un admin.php de antes)
    return _normalizar(v, ('id', 'correo_enviado'), ('monto', 'licencia_id', 'limite', 'equipos', 'descuento') + _ENTEROS_VERSION,
                       ('estado', 'correo', 'nombre', 'moneda', 'creado', 'pagado', 'checkout_id', 'clave', 'licencia_estado',
                        'eliminada', 'cupon') + _TEXTOS_VERSION)


def normalizar_canje(c):
    c = _normalizar(c, ('id',), ('licencia_id', 'limite', 'equipos') + _ENTEROS_VERSION,
                    ('correo', 'nombre', 'fecha_venta', 'bloqueo', 'creado', 'ultimo', 'clave', 'licencia_estado')
                    + _TEXTOS_VERSION)
    if c is not None and not c['bloqueo']:
        c['bloqueo'] = None   # '' también es «compra vigente» (si no, saldría una pastilla vacía)
    return c


def normalizar_licencia(l):
    return _normalizar(l, ('id', 'limite'), (), ('clave', 'estado', 'correo', 'nombre', 'creada', 'nota', 'nota_fecha'))


def normalizar_pedido(p):
    return _normalizar(p, ('id', 'correo_enviado'), ('monto', 'licencia_id', 'descuento'),
                       ('checkout_id', 'estado', 'correo', 'nombre', 'moneda', 'pago_ids', 'creado', 'pagado', 'eliminada',
                        'cupon'))


def normalizar_cupon(c):
    """2.8: un cupón de la acción cupones (lista_cupones() de admin.php), con sus usos, lo que dejó y su estado."""
    c = _normalizar(c, ('id', 'porcentaje', 'usos', 'ingresos', 'descontado'), ('usos_max', 'precio_final'),
                    ('codigo', 'vence', 'nota', 'creado', 'ultima_venta', 'estado', 'enlace'))
    if c is not None:
        c['activo'] = c.get('activo') in (True, 1, '1', 'true')
        c['vence'] = (c['vence'] or '')[:10] or None
        c['enlace'] = c['enlace'] or f"{SITIO}/?cupon={urllib.parse.quote(c['codigo'] or '')}"
        if c['estado'] not in ESTADOS_CUPON:
            c['estado'] = 'activo' if c['activo'] else 'pausado'
    return c


def texto_descuento(porcentaje):
    """«20 %» o, con el 100 %, «Gratis» (el cupón regala la licencia)."""
    return 'Gratis' if porcentaje >= 100 else f'{porcentaje} %'


def texto_usos(c):
    """«3 de 10» o, sin tope, «3» (con «sin tope» en la ayuda)."""
    return f"{c['usos']:,} de {c['usos_max']:,}" if c.get('usos_max') else f"{c['usos']:,}"


def normalizar_equipo(e):
    # (2.4, CineCaptions 5.72: la línea de su ficha, cuándo llegó —en UTC— y si hay ficha; con un admin.php de antes, nada)
    e = _normalizar(e, (), (), ('equipo', 'nombre_equipo', 'creada', 'ultima', 'version', 'version_desde',
                                'version_anterior', 'so', 'estado_version', 'ficha_resumen', 'ficha_cuando'))
    if e is not None:
        e['con_ficha'] = e.get('con_ficha') in (True, 1, '1', 'true')
    return e


def normalizar_ficha_equipo(valor):
    """2.4: la ficha técnica de un equipo (equipo_ficha y error_detalle): {ficha (dict o None), resumen, cuando (UTC)} o None
    si no hay. La ficha va tal cual (la pinta secciones_ficha(), que no confía en nada de lo que traiga)."""
    if not isinstance(valor, dict):
        return None
    ficha = valor.get('ficha')
    return {'ficha': ficha if isinstance(ficha, dict) else None, 'resumen': texto_o_nada(valor.get('resumen')) or None,
            'cuando': texto_o_nada(valor.get('cuando')) or None}


def normalizar_equipo_version(e):
    """Una fila de la acción versiones (un equipo con su licencia). «id» junta licencia y equipo: así la tabla recupera la
    fila elegida al recargar."""
    e = _normalizar(e, (), ('licencia_id', 'pedido_id'),
                    ('clave', 'cliente', 'correo', 'origen', 'licencia_estado', 'equipo', 'nombre_equipo', 'version',
                     'version_desde', 'version_anterior', 'so', 'creada', 'ultima', 'estado_version', 'aviso_version',
                     'aviso_fecha'))
    if e is not None:
        e['id'] = f"{e['licencia_id']}/{e['equipo']}"
    return e


def normalizar_aviso(a):
    a = _normalizar(a, ('id',), ('licencia_id',), ('cliente', 'correo', 'version', 'enviado', 'motivo'))
    if a is not None:
        a['ok'] = a.get('ok') in (True, 1, '1', 'true')
    return a


def normalizar_evento(e):
    return _normalizar(e, (), (), ('fecha', 'tipo', 'titulo', 'detalle'))


def normalizar_candidato(c):
    return _normalizar(c, ('licencia_id', 'equipos', 'equipos_desactualizados'), (), ('cliente', 'correo', 'ultima_vez'))


def normalizar_error(e):
    """Un error que mandó CineCaptions (las acciones errores y error_detalle; «detalle» solo viene en error_detalle)."""
    e = _normalizar(e, ('id', 'veces'), ('licencia_id',),
                    ('clave', 'cliente', 'correo', 'equipo', 'nombre_equipo', 'nivel', 'titulo', 'mensaje', 'origen',
                     'version', 'so', 'primera', 'ultima', 'detalle', 'equipo_datos'))
    if e is not None:
        e['visto'] = bool(entero(e.get('visto')))
        if e['nivel'] not in NIVELES_ERROR:
            e['nivel'] = 'error'
        # 2.3 (CineCaptions 5.72): la captura de pantalla del fallo. «con_captura» viene en la lista; «captura» (sus datos, sin la
        # imagen) en error_detalle. Con un admin.php anterior no viene ninguno: no hay captura.
        # 2.5 (CineCaptions 5.73): la segunda, la de la ventana de CineCaptions: «con_ventana» en la lista y en error_detalle,
        # «captura_ventana» (sus datos) en error_detalle. Con un admin.php de la 5.72 no viene: solo está la de siempre.
        for clave, con in (('captura', 'con_captura'), ('captura_ventana', 'con_ventana')):
            cap = e.get(clave)
            e[clave] = ({'tipo': texto_o_nada(cap.get('tipo')), 'ancho': entero(cap.get('ancho')), 'alto': entero(cap.get('alto')),
                         'bytes': entero(cap.get('bytes')), 'de': texto_o_nada(cap.get('de')),
                         'creada': texto_o_nada(cap.get('creada'))}
                        if isinstance(cap, dict) else None)
            e[con] = e[clave] is not None or e.get(con) in (True, 1, '1', 'true')
        # 2.4 (CineCaptions 5.72): la ficha técnica de ese equipo, solo en error_detalle. Si el servidor ya conoce las fichas
        # manda «ficha_equipo» (aunque sea null); con un admin.php de antes no viene y no se dice nada de la ficha.
        if 'ficha_equipo' in e:
            e['ficha_equipo'] = normalizar_ficha_equipo(e['ficha_equipo'])
    return e


def normalizar_resumen_errores(valor):
    """Cuántos errores sin ver hay, de cuántos equipos y cuál es el más nuevo (panel, errores y error_visto). None si el
    servidor todavía no tiene la tabla o es uno anterior que no lo manda: la app sigue igual, sin contador ni avisos."""
    if not isinstance(valor, dict):
        return None
    return {'sin_ver': entero(valor.get('sin_ver')), 'equipos': entero(valor.get('equipos')),
            'ultimo_id': entero_o_nada(valor.get('ultimo_id')), 'ultima': texto_o_nada(valor.get('ultima'))}


def _versiones_de(r):
    """El bloque «versiones» del resumen (None si el servidor todavía es el anterior)."""
    valor = r.get('versiones')
    if not isinstance(valor, dict):
        return None
    return {'ultima': texto_o_nada(valor.get('ultima')),
            **{campo: entero(valor.get(campo)) for campo in ('al_dia', 'desactualizados', 'sin_datos', 'activos_30d')}}


def normalizar_resumen(r):
    def tabla(nombre):   # (PHP manda [] en vez de {} si el arreglo viene vacío)
        valor = r.get(nombre)
        return valor if isinstance(valor, dict) else {}

    ventas = {k: entero(v) for k, v in tabla('ventas').items()}
    for campo in ('pagadas', 'reembolsadas', 'pendientes', 'ingresos', 'ventas_hoy', 'ingresos_hoy', 'ventas_mes',
                  'ingresos_mes', 'monto_reembolsado'):
        ventas.setdefault(campo, 0)
    licencias = {k: entero(v) for k, v in tabla('licencias').items()}
    licencias.setdefault('activas', 0)
    licencias.setdefault('bloqueadas', 0)
    return {'ventas': ventas, 'licencias': licencias, 'equipos': entero(r.get('equipos')), 'canjes': entero(r.get('canjes')),
            'monedas': [str(m).upper() for m in (r.get('monedas') or []) if m],
            'hora_servidor': texto_o_nada(r.get('hora_servidor')), 'versiones': _versiones_de(r)}


class _SinRedirecciones(urllib.request.HTTPRedirectHandler):
    """Una redirección no se sigue (urllib la seguiría como GET y con la cabecera X-Admin-Clave, aunque sea a otro
    servidor): llega como error 3xx con un mensaje claro."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ClienteApi:
    """Cliente de pagos/admin.php. Cada método hace un POST y devuelve los datos ya revisados, o lanza ApiError.
    No toca nada de la ventana: se puede usar desde un hilo o desde las pruebas.
    Con solo_lectura=True (--captura) las acciones que cambian algo o mandan correos ni salen: dan ApiError."""

    def __init__(self, url, clave, tiempo=25, solo_lectura=False):
        self.url, self.clave, self.tiempo, self.solo_lectura = url, clave, tiempo, solo_lectura
        manejadores = [urllib.request.HTTPSHandler(context=ssl.create_default_context()), _SinRedirecciones()]
        if es_local(urllib.parse.urlsplit(url).hostname):
            manejadores.append(urllib.request.ProxyHandler({}))   # el servidor de prueba nunca pasa por un proxy
        self._abridor = urllib.request.build_opener(*manejadores)

    def llamar(self, accion, **datos):
        if self.solo_lectura and accion in ACCIONES_QUE_CAMBIAN:
            raise ApiError('En modo captura la app no cambia nada en el servidor.', 0)
        if self.solo_lectura:
            datos.pop('refrescar', None)   # ni siquiera vuelve a pedir el version.json (eso reescribe lo guardado)
        cuerpo = json.dumps({'accion': accion, **datos}).encode('utf-8')
        pedido = urllib.request.Request(self.url, data=cuerpo, method='POST', headers={
            'X-Admin-Clave': self.clave, 'Content-Type': 'application/json', 'Accept': 'application/json',
            'User-Agent': f'CineCaptionsVentas/{VERSION} (Windows)'})
        try:
            with self._abridor.open(pedido, timeout=self.tiempo) as r:
                codigo, crudo, cabeceras = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            codigo, cabeceras = e.code, e.headers
            try:
                crudo = e.read()
            except (OSError, http.client.HTTPException):
                crudo = b''
        except urllib.error.URLError as e:
            raise ApiError(_mensaje_red(e.reason), 0, str(e.reason)) from None
        except (OSError, http.client.HTTPException) as e:   # timeout, conexión cortada, SSL...
            raise ApiError(_mensaje_red(e), 0, str(e)) from None
        try:
            respuesta = json.loads(crudo.decode('utf-8-sig')) if crudo else None
        except (UnicodeDecodeError, ValueError):
            respuesta = None
        error = respuesta.get('error') if isinstance(respuesta, dict) else None
        servidor = str(error) if error else None
        if codigo != 200 or not isinstance(respuesta, dict):
            raise _error_http(codigo, servidor, cabeceras)
        if respuesta.get('ok') is not True:
            raise ApiError(str(servidor or 'El servidor no pudo completar la acción.'), 200)
        return respuesta

    def resumen(self):
        return normalizar_resumen(self.llamar('resumen'))

    def ventas(self, estado='', buscar='', limite=LIMITE_LISTA, desde=0):
        r = self.llamar('ventas', estado=estado, buscar=buscar, limite=limite, desde=desde)
        return [normalizar_venta(v) for v in (r.get('ventas') or []) if isinstance(v, dict)]

    def canjes(self, buscar=''):
        r = self.llamar('canjes', buscar=buscar)
        return [normalizar_canje(c) for c in (r.get('canjes') or []) if isinstance(c, dict)]

    def detalle(self, licencia_id=None, pedido_id=None):
        datos = {}
        if licencia_id:
            datos['licencia_id'] = licencia_id
        if pedido_id:
            datos['pedido_id'] = pedido_id
        r = self.llamar('detalle', **datos)
        return {'licencia': normalizar_licencia(r.get('licencia')), 'pedido': normalizar_pedido(r.get('pedido')),
                'canje': normalizar_canje(r.get('canje')),
                'equipos': [normalizar_equipo(e) for e in (r.get('equipos') or []) if isinstance(e, dict)],
                'version_ultima': texto_o_nada(r.get('version_ultima'))}

    def licencia_estado(self, licencia_id, estado):
        return normalizar_licencia(self.llamar('licencia_estado', licencia_id=licencia_id, estado=estado).get('licencia'))

    def liberar_equipo(self, licencia_id, equipo=''):
        r = self.llamar('liberar_equipo', licencia_id=licencia_id, equipo=equipo)
        return {'liberados': entero(r.get('liberados')),
                'equipos': [normalizar_equipo(e) for e in (r.get('equipos') or []) if isinstance(e, dict)]}

    def reenviar_correo(self, licencia_id):
        return texto_o_nada(self.llamar('reenviar_correo', licencia_id=licencia_id).get('correo')) or ''

    def estado_recurrente(self, pedido_id):
        info = self.llamar('estado_recurrente', pedido_id=pedido_id).get('recurrente')
        return dict(info) if isinstance(info, dict) else {}

    def marcar_reembolsado(self, pedido_id):
        return normalizar_pedido(self.llamar('marcar_reembolsado', pedido_id=pedido_id).get('pedido'))

    # --- Acciones del servidor nuevo (con el anterior dan ApiError con .desconocida)
    def panel(self, estado='', buscar='', limite=LIMITE_LISTA):
        """Resumen, ventas y canjes en UNA petición (lo que usa «Actualizar»), y el resumen de los errores de los
        clientes (None con un admin.php de antes de la 5.71 de CineCaptions, que no lo manda)."""
        r = self.llamar('panel', estado=estado, buscar=buscar, limite=limite)
        resumen, ventas, canjes = r.get('resumen'), r.get('ventas'), r.get('canjes')
        if not isinstance(resumen, dict) or not isinstance(ventas, list) or not isinstance(canjes, list):
            raise ApiError('El servidor respondió algo inesperado al pedir los datos. Intenta de nuevo en un momento.', 200)
        if r.get('hora_servidor'):
            resumen = dict(resumen, hora_servidor=r['hora_servidor'])
        return {'resumen': normalizar_resumen(resumen),
                'ventas': [normalizar_venta(v) for v in ventas if isinstance(v, dict)],
                'canjes': [normalizar_canje(c) for c in canjes if isinstance(c, dict)],
                'errores': normalizar_resumen_errores(r.get('errores'))}

    def eliminar_venta(self, pedido_id, eliminar=True, bloquear_licencia=False):
        """Quita la venta de la lista y de los totales (o la restaura con eliminar=False). No se borra nada: el pago, la
        licencia y su historial siguen en el servidor. bloquear_licencia: también bloquea su licencia (solo al eliminar y
        solo si estaba activa). Devuelve {eliminada, licencia_bloqueada, resumen} (resumen None si no vino)."""
        r = self.llamar('eliminar_venta', pedido_id=entero(pedido_id), eliminar=bool(eliminar),
                        bloquear_licencia=bool(eliminar and bloquear_licencia))
        resumen = r.get('resumen')
        return {'eliminada': r.get('eliminada') in (True, 1, '1', 'true'),
                'licencia_bloqueada': r.get('licencia_bloqueada') in (True, 1, '1', 'true'),
                'resumen': normalizar_resumen(resumen) if isinstance(resumen, dict) else None}

    # --- Los errores de los clientes (desde la 5.71 de CineCaptions; con un admin.php anterior dan .desconocida)
    def errores(self, filtro='todos', buscar='', licencia_id=None, limite=LIMITE_LISTA):
        """filtro: 'sin_ver' o 'todos'. Vienen los sin ver primero y después por la última vez que pasaron."""
        datos = {'filtro': filtro, 'buscar': buscar, 'limite': limite}
        if licencia_id:
            datos['licencia_id'] = licencia_id
        r = self.llamar('errores', **datos)
        return {'errores': [normalizar_error(e) for e in (r.get('errores') or []) if isinstance(e, dict)],
                'resumen': normalizar_resumen_errores(r.get('resumen'))}

    def error_detalle(self, error_id):
        """Un error con su informe técnico («detalle», con saltos de línea)."""
        e = normalizar_error(self.llamar('error_detalle', id=error_id).get('error_cliente'))
        if e is None:
            raise ApiError('El servidor respondió algo inesperado al pedir el error. Intenta de nuevo en un momento.', 200)
        return e

    def error_captura(self, error_id, cual='pantalla'):
        """2.3: la captura de pantalla del error como QImage (se decodifica aquí, en el hilo de la petición) y sus datos.
        2.5: cual = 'pantalla' (la de siempre: se pide igual que antes, sin «cual») | 'ventana' (la de la ventana de
        CineCaptions 5.73). Un admin.php de la 5.72 no conoce «cual» y daría la de siempre: la respuesta tiene que decirlo."""
        c = self.llamar('error_captura', id=error_id, **({'cual': cual} if cual != 'pantalla' else {})).get('captura')
        if not isinstance(c, dict) or not isinstance(c.get('base64'), str):
            raise ApiError('El servidor respondió algo inesperado al pedir la captura.', 200)
        if c.get('cual', 'pantalla') != cual:
            raise ApiError(FALTA_SERVIDOR, 200)
        try:
            datos = base64.b64decode(c['base64'], validate=True)
        except ValueError:
            raise ApiError('La captura llegó dañada.', 200)
        imagen = QImage.fromData(datos)
        if imagen.isNull():
            raise ApiError('La captura llegó dañada.', 200)
        return {'imagen': imagen, 'de': texto_o_nada(c.get('de')), 'creada': texto_o_nada(c.get('creada')),
                'ancho': imagen.width(), 'alto': imagen.height(), 'bytes': len(datos), 'cual': cual}

    def equipo_ficha(self, licencia_id, equipo):
        """2.4: la ficha técnica completa de un equipo (CineCaptions 5.72): {ficha, resumen, cuando} o None si todavía no la
        mandó. Un equipo que ya no está activado da 404; un admin.php de antes, .desconocida."""
        return normalizar_ficha_equipo(self.llamar('equipo_ficha', licencia_id=entero(licencia_id),
                                                   equipo=str(equipo or '')).get('ficha_equipo'))

    def error_visto(self, ids=None, todos=False, visto=True):
        """Marca esos errores (o todos, con todos=True) como vistos; visto=False los vuelve a marcar como nuevos."""
        datos = {'todos': True} if todos else {'ids': [entero(i) for i in ids or []]}
        if not visto:
            datos['visto'] = False
        r = self.llamar('error_visto', **datos)
        return {'cambiados': entero(r.get('cambiados')), 'resumen': normalizar_resumen_errores(r.get('resumen'))}

    def version_actual(self, refrescar=False):
        r = self.llamar('version_actual', **({'refrescar': True} if refrescar else {}))
        return {'version': texto_o_nada(r.get('version')), 'fecha': texto_o_nada(r.get('fecha')),
                'notas': texto_o_nada(r.get('notas')), 'descarga': texto_o_nada(r.get('descarga')) or DESCARGA,
                'consultado': texto_o_nada(r.get('consultado')), 'error': texto_o_nada(r.get('error'))}

    def versiones(self, filtro='todos', buscar=''):
        r = self.llamar('versiones', filtro=filtro, buscar=buscar)
        por_version = [{'version': texto_o_nada(p.get('version')), 'equipos': entero(p.get('equipos'))}
                       for p in (r.get('por_version') or []) if isinstance(p, dict)]
        return {'ultima': texto_o_nada(r.get('ultima')), 'por_version': por_version,
                'equipos': [normalizar_equipo_version(e) for e in (r.get('equipos') or []) if isinstance(e, dict)],
                **{campo: entero(r.get(campo)) for campo in ('al_dia', 'desactualizados', 'sin_datos', 'activos_30d')}}

    def candidatos_aviso(self, version=None, a_quien='desactualizados'):
        r = self.llamar('candidatos_aviso', a_quien=a_quien, **({'version': version} if version else {}))
        excluidos = r.get('excluidos') if isinstance(r.get('excluidos'), dict) else {}
        return {'version': texto_o_nada(r.get('version')) or version,
                'candidatos': [normalizar_candidato(c) for c in (r.get('candidatos') or []) if isinstance(c, dict)],
                'excluidos': {campo: entero(excluidos.get(campo))
                              for campo in ('baja', 'ya_avisados', 'bloqueadas', 'sin_correo', 'al_dia')}}

    def avisar_actualizacion(self, licencia_id, version=None, mensaje=None, forzar=False):
        datos = {'licencia_id': licencia_id}
        if version:
            datos['version'] = version
        if mensaje:
            datos['mensaje'] = mensaje[:MAX_TEXTO]
        if forzar:
            datos['forzar'] = True
        r = self.llamar('avisar_actualizacion', **datos)
        return {'enviado': r.get('enviado') in (True, 1, '1', 'true'), 'correo': texto_o_nada(r.get('correo')),
                'motivo': texto_o_nada(r.get('motivo')), 'reintentar_en': entero_o_nada(r.get('reintentar_en'))}

    def avisos(self, licencia_id=None, limite=200):
        r = self.llamar('avisos', limite=limite, **({'licencia_id': licencia_id} if licencia_id else {}))
        return [normalizar_aviso(a) for a in (r.get('avisos') or []) if isinstance(a, dict)]

    def historial(self, licencia_id=None, pedido_id=None):
        datos = {'licencia_id': licencia_id} if licencia_id else {'pedido_id': pedido_id}
        r = self.llamar('historial', **datos)
        return [normalizar_evento(e) for e in (r.get('eventos') or []) if isinstance(e, dict)]

    def nota(self, licencia_id, texto):
        r = self.llamar('nota', licencia_id=licencia_id, texto=texto[:MAX_TEXTO])
        return {'nota': texto_o_nada(r.get('nota')), 'nota_fecha': texto_o_nada(r.get('nota_fecha'))}

    def limite(self, licencia_id, limite):
        return normalizar_licencia(self.llamar('limite', licencia_id=licencia_id, limite=limite).get('licencia'))

    def editar_cliente(self, licencia_id, nombre=None, correo=None):
        datos = {'licencia_id': licencia_id}
        if nombre is not None:
            datos['nombre'] = nombre
        if correo is not None:
            datos['correo'] = correo
        return normalizar_licencia(self.llamar('editar_cliente', **datos).get('licencia'))

    def estadisticas(self, dias=DIAS_GRAFICA):
        r = self.llamar('estadisticas', dias=dias)
        filas = []
        for d in r.get('dias') or []:
            fecha = None
            if isinstance(d, dict):
                try:
                    fecha = dt.date.fromisoformat(str(d.get('fecha') or '')[:10])
                except ValueError:
                    pass
            if fecha:
                filas.append({'fecha': fecha, 'ventas': entero(d.get('ventas')), 'ingresos': entero(d.get('ingresos')),
                              'reembolsos': entero(d.get('reembolsos'))})
        filas.sort(key=lambda d: d['fecha'])
        return {'dias': filas, 'moneda': (texto_o_nada(r.get('moneda')) or 'USD').upper()}

    # 2.8: los cupones de descuento (pagos/cupones.php)
    def cupones(self):
        """{cupones, precio (el de ahora, en centavos), moneda, hoy (AAAA-MM-DD de Guatemala), sitio}."""
        r = self.llamar('cupones')
        return {'cupones': [normalizar_cupon(c) for c in (r.get('cupones') or []) if isinstance(c, dict)],
                'precio': entero_o_nada(r.get('precio')), 'moneda': (texto_o_nada(r.get('moneda')) or 'USD').upper(),
                'hoy': texto_o_nada(r.get('hoy')), 'sitio': texto_o_nada(r.get('sitio')) or SITIO}

    def cupon_crear(self, codigo, porcentaje, usos_max=None, vence=None, nota=None, activo=True):
        r = self.llamar('cupon_crear', codigo=codigo, porcentaje=porcentaje, usos_max=usos_max, vence=vence, nota=nota,
                        activo=bool(activo))
        return normalizar_cupon(r.get('cupon'))

    def cupon_editar(self, cupon_id, **cambios):
        """Solo lo que cambia: porcentaje, usos_max (None = sin tope), vence (None = no vence), nota, activo."""
        return normalizar_cupon(self.llamar('cupon_editar', id=cupon_id, **cambios).get('cupon'))

    def cupon_borrar(self, cupon_id):
        return entero(self.llamar('cupon_borrar', id=cupon_id).get('borrado'))


# ---------------------------------------------------------------- Trabajo en segundo plano (cola de una petición)

class _Tarea(QRunnable):
    def __init__(self, numero, funcion, avisar):
        super().__init__()
        self.numero, self.funcion, self.avisar = numero, funcion, avisar
        self.cancelada = False
        self.setAutoDelete(False)   # la guarda Trabajos hasta entregar el resultado

    def run(self):
        if self.cancelada:   # la reemplazó otra igual mientras esperaba: no sale
            self.avisar(self.numero, False, Cancelada())
            return
        try:
            resultado, ok = self.funcion(), True
        except Exception as error:   # cualquier fallo vuelve a la ventana como error, nunca se pierde
            resultado, ok = error, False
        self.avisar(self.numero, ok, resultado)


class Trabajos(QObject):
    """Cola de UNA petición a la vez: corre las funciones (las llamadas a la API) de una en una, en un hilo aparte, y
    entrega el resultado en el hilo de la ventana. admin.php anota cada petición en curso para su límite de intentos:
    varias a la vez podrían sumar un 429 falso aunque la clave sea la correcta.
    Una tarea con «clave» reemplaza a la de la misma clave que todavía espera su turno (al escribir en el buscador sale
    solo la última búsqueda); la reemplazada avisa con Cancelada a al_fallar."""
    _terminada = Signal(int, bool, object)
    ocupado = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._pool.setExpiryTimeout(-1)   # el hilo queda listo para la siguiente petición
        self._pendientes = {}             # número → (al_listo, al_fallar, tarea, clave)
        self._numero = 0
        self._terminada.connect(self._entregar, Qt.ConnectionType.QueuedConnection)

    @property
    def activos(self):
        return len(self._pendientes)

    def iniciar(self, funcion, al_listo=None, al_fallar=None, clave=None):
        if clave:
            for _l, _f, tarea, otra in self._pendientes.values():
                if otra == clave:
                    tarea.cancelada = True   # (si ya está corriendo, no cambia nada: termina y entrega lo suyo)
        self._numero += 1
        tarea = _Tarea(self._numero, funcion, self._terminada.emit)
        self._pendientes[self._numero] = (al_listo, al_fallar, tarea, clave)
        if len(self._pendientes) == 1:
            self.ocupado.emit(True)
        self._pool.start(tarea)
        return self._numero

    def cerrar(self, ms):
        """Al salir: lo que espera turno no sale y se espera (hasta ms) a la petición en curso. True si terminó."""
        for _l, _f, tarea, _c in self._pendientes.values():
            tarea.cancelada = True
        self._pool.clear()
        return self._pool.waitForDone(ms)

    @Slot(int, bool, object)
    def _entregar(self, numero, ok, resultado):
        al_listo, al_fallar, _tarea, _clave = self._pendientes.pop(numero, (None, None, None, None))
        try:
            if ok and al_listo:
                al_listo(resultado)
            elif not ok and al_fallar:
                al_fallar(resultado)
            elif not ok and not isinstance(resultado, Cancelada):
                sys.excepthook(type(resultado), resultado, resultado.__traceback__)
        finally:
            if not self._pendientes:
                self.ocupado.emit(False)


# ---------------------------------------------------------------- Íconos (dibujados con QPainter, sin archivos)

def _trazar(p, nombre):
    """Íconos de línea en una cuadrícula de 24×24, al estilo de Lucide."""
    if nombre == 'buscar':
        p.drawEllipse(QPointF(11, 11), 7, 7)
        p.drawLine(QPointF(16.2, 16.2), QPointF(21, 21))
    elif nombre == 'copiar':
        p.drawRoundedRect(QRectF(8, 8, 13, 13), 2.5, 2.5)
        c = QPainterPath(QPointF(4, 16))
        c.cubicTo(2.9, 16, 2, 15.1, 2, 14)
        c.lineTo(2, 4)
        c.cubicTo(2, 2.9, 2.9, 2, 4, 2)
        c.lineTo(14, 2)
        c.cubicTo(15.1, 2, 16, 2.9, 16, 4)
        p.drawPath(c)
    elif nombre == 'actualizar':
        r = QRectF(3, 3, 18, 18)
        p.drawArc(r, 180 * 16, -135 * 16)
        p.drawLine(QPointF(18.36, 5.64), QPointF(21, 8))
        p.drawPolyline([QPointF(21, 3), QPointF(21, 8), QPointF(16, 8)])
        p.drawArc(r, 0, -135 * 16)
        p.drawLine(QPointF(5.64, 18.36), QPointF(3, 16))
        p.drawPolyline([QPointF(8, 16), QPointF(3, 16), QPointF(3, 21)])
    elif nombre == 'exportar':
        p.drawLine(QPointF(12, 15), QPointF(12, 3))
        p.drawPolyline([QPointF(7, 10), QPointF(12, 15), QPointF(17, 10)])
        c = QPainterPath(QPointF(21, 15))
        c.lineTo(21, 19)
        c.quadTo(21, 21, 19, 21)
        c.lineTo(5, 21)
        c.quadTo(3, 21, 3, 19)
        c.lineTo(3, 15)
        p.drawPath(c)
    elif nombre == 'correo':
        p.drawRoundedRect(QRectF(2, 4, 20, 16), 2.5, 2.5)
        p.drawPolyline([QPointF(2.5, 7), QPointF(12, 13), QPointF(21.5, 7)])
    elif nombre in ('candado', 'abierto'):
        p.drawRoundedRect(QRectF(3, 11, 18, 11), 2.5, 2.5)
        c = QPainterPath(QPointF(7, 11))
        c.lineTo(7, 7)
        c.arcTo(QRectF(7, 2, 10, 10), 180, -180 if nombre == 'candado' else -150)
        if nombre == 'candado':
            c.lineTo(17, 11)
        p.drawPath(c)
    elif nombre == 'tarjeta':
        p.drawRoundedRect(QRectF(2, 5, 20, 14), 2.5, 2.5)
        p.drawLine(QPointF(2, 10), QPointF(22, 10))
        p.drawLine(QPointF(6, 15), QPointF(10, 15))
    elif nombre == 'reembolso':
        p.drawPolyline([QPointF(9, 14), QPointF(4, 9), QPointF(9, 4)])
        c = QPainterPath(QPointF(4, 9))
        c.lineTo(14.5, 9)
        c.arcTo(QRectF(9, 9, 11, 11), 90, -180)
        c.lineTo(11, 20)
        p.drawPath(c)
    elif nombre == 'equipo':
        p.drawRoundedRect(QRectF(2, 3, 20, 14), 2.5, 2.5)
        p.drawLine(QPointF(8, 21), QPointF(16, 21))
        p.drawLine(QPointF(12, 17), QPointF(12, 21))
    elif nombre == 'x':
        p.drawLine(QPointF(18, 6), QPointF(6, 18))
        p.drawLine(QPointF(6, 6), QPointF(18, 18))
    elif nombre == 'basura':   # «Eliminar venta»
        p.drawLine(QPointF(3, 6), QPointF(21, 6))
        c = QPainterPath(QPointF(19, 6))
        c.lineTo(19, 20)
        c.quadTo(19, 22, 17, 22)
        c.lineTo(7, 22)
        c.quadTo(5, 22, 5, 20)
        c.lineTo(5, 6)
        p.drawPath(c)
        c = QPainterPath(QPointF(8, 6))
        c.lineTo(8, 4)
        c.quadTo(8, 2, 10, 2)
        c.lineTo(14, 2)
        c.quadTo(16, 2, 16, 4)
        c.lineTo(16, 6)
        p.drawPath(c)
        p.drawLine(QPointF(10, 11), QPointF(10, 17))
        p.drawLine(QPointF(14, 11), QPointF(14, 17))
    elif nombre == 'restaurar':   # flecha que vuelve en círculo («Restaurar venta»)
        p.drawArc(QRectF(3, 3, 18, 18), 180 * 16, 270 * 16)
        c = QPainterPath(QPointF(12, 3))
        c.cubicTo(9.6, 3, 7.1, 3.95, 5.26, 5.74)
        c.lineTo(3, 8)
        p.drawPath(c)
        p.drawPolyline([QPointF(3, 3), QPointF(3, 8), QPointF(8, 8)])
    elif nombre == 'llave':
        p.drawEllipse(QPointF(7.5, 15.5), 5.5, 5.5)
        p.drawLine(QPointF(21, 2), QPointF(11.4, 11.6))
        p.drawPolyline([QPointF(15.5, 7.5), QPointF(18, 10), QPointF(21, 7), QPointF(18.5, 4.5)])
    elif nombre == 'aviso':
        c = QPainterPath(QPointF(12, 3))
        c.lineTo(22, 20)
        c.lineTo(2, 20)
        c.closeSubpath()
        p.drawPath(c)
        p.drawLine(QPointF(12, 9.5), QPointF(12, 13.5))
        p.drawPoint(QPointF(12, 16.8))
    elif nombre == 'ok':
        p.drawEllipse(QPointF(12, 12), 9.5, 9.5)
        p.drawPolyline([QPointF(8, 12.5), QPointF(11, 15.5), QPointF(16.5, 9)])
    elif nombre == 'info':
        p.drawEllipse(QPointF(12, 12), 9.5, 9.5)
        p.drawLine(QPointF(12, 11), QPointF(12, 16.5))
        p.drawPoint(QPointF(12, 7.8))
    elif nombre == 'alerta':   # círculo con «!» (los errores de los clientes)
        p.drawEllipse(QPointF(12, 12), 9.5, 9.5)
        p.drawLine(QPointF(12, 7.5), QPointF(12, 13))
        p.drawPoint(QPointF(12, 16.4))
    elif nombre == 'ojo':
        c = QPainterPath(QPointF(2, 12))
        c.cubicTo(4.5, 7, 8, 5, 12, 5)
        c.cubicTo(16, 5, 19.5, 7, 22, 12)
        c.cubicTo(19.5, 17, 16, 19, 12, 19)
        c.cubicTo(8, 19, 4.5, 17, 2, 12)
        p.drawPath(c)
        p.drawEllipse(QPointF(12, 12), 3, 3)
    elif nombre == 'carpeta':
        c = QPainterPath(QPointF(2.5, 6.5))
        c.quadTo(2.5, 4.5, 4.5, 4.5)
        c.lineTo(9.5, 4.5)
        c.lineTo(11.5, 7)
        c.lineTo(19.5, 7)
        c.quadTo(21.5, 7, 21.5, 9)
        c.lineTo(21.5, 18)
        c.quadTo(21.5, 20, 19.5, 20)
        c.lineTo(4.5, 20)
        c.quadTo(2.5, 20, 2.5, 18)
        c.closeSubpath()
        p.drawPath(c)
    elif nombre == 'usuario':
        p.drawEllipse(QPointF(12, 8), 4, 4)
        c = QPainterPath(QPointF(5, 21))
        c.lineTo(5, 19)
        c.cubicTo(5, 16.8, 6.8, 15, 9, 15)
        c.lineTo(15, 15)
        c.cubicTo(17.2, 15, 19, 16.8, 19, 19)
        c.lineTo(19, 21)
        p.drawPath(c)
    elif nombre == 'abajo':
        p.drawPolyline([QPointF(6, 9), QPointF(12, 15), QPointF(18, 9)])
    elif nombre == 'arriba':
        p.drawPolyline([QPointF(6, 15), QPointF(12, 9), QPointF(18, 15)])
    elif nombre == 'check':
        p.drawPolyline([QPointF(5, 12.5), QPointF(10, 17.5), QPointF(19, 7)])
    elif nombre == 'inicio':   # cuadrícula del resumen
        for x, y, w, h in ((3, 3, 7.5, 9), (13.5, 3, 7.5, 5), (13.5, 11, 7.5, 10), (3, 15, 7.5, 6)):
            p.drawRoundedRect(QRectF(x, y, w, h), 1.8, 1.8)
    elif nombre == 'recibo':
        c = QPainterPath(QPointF(5, 2.5))
        c.lineTo(19, 2.5)
        c.lineTo(19, 21.5)
        for x in (16.7, 14.3, 12, 9.7, 7.3, 5):
            c.lineTo(x, 20 if x in (16.7, 12, 7.3) else 21.5)
        c.closeSubpath()
        p.drawPath(c)
        p.drawLine(QPointF(8.5, 8), QPointF(15.5, 8))
        p.drawLine(QPointF(8.5, 12), QPointF(15.5, 12))
        p.drawLine(QPointF(8.5, 16), QPointF(12.5, 16))
    elif nombre == 'capas':
        c = QPainterPath(QPointF(12, 2.5))
        c.lineTo(21.5, 7.5)
        c.lineTo(12, 12.5)
        c.lineTo(2.5, 7.5)
        c.closeSubpath()
        p.drawPath(c)
        p.drawPolyline([QPointF(2.5, 12), QPointF(12, 17), QPointF(21.5, 12)])
        p.drawPolyline([QPointF(2.5, 16.5), QPointF(12, 21.5), QPointF(21.5, 16.5)])
    elif nombre == 'regalo':
        p.drawRoundedRect(QRectF(3, 8, 18, 4.5), 1.2, 1.2)
        c = QPainterPath(QPointF(5, 12.5))
        c.lineTo(5, 19.5)
        c.quadTo(5, 21, 6.5, 21)
        c.lineTo(17.5, 21)
        c.quadTo(19, 21, 19, 19.5)
        c.lineTo(19, 12.5)
        p.drawPath(c)
        p.drawLine(QPointF(12, 8), QPointF(12, 21))
        p.drawEllipse(QRectF(7, 3.2, 5, 4.8))
        p.drawEllipse(QRectF(12, 3.2, 5, 4.8))
    elif nombre == 'megafono':
        c = QPainterPath(QPointF(3, 10))
        c.lineTo(19, 5)
        c.lineTo(19, 19)
        c.lineTo(3, 14)
        c.closeSubpath()
        p.drawPath(c)
        p.drawPolyline([QPointF(7.5, 15.4), QPointF(8.6, 20), QPointF(12, 20), QPointF(11.2, 16.6)])
        p.drawLine(QPointF(21.5, 9.5), QPointF(21.5, 14.5))
    elif nombre == 'lapiz':
        c = QPainterPath(QPointF(16.2, 3.8))
        c.lineTo(20.2, 7.8)
        c.lineTo(8, 20)
        c.lineTo(3, 21)
        c.lineTo(4, 16)
        c.closeSubpath()
        p.drawPath(c)
        p.drawLine(QPointF(14, 6), QPointF(18, 10))
    elif nombre in ('menos', 'mas'):
        p.drawLine(QPointF(5, 12), QPointF(19, 12))
        if nombre == 'mas':
            p.drawLine(QPointF(12, 5), QPointF(12, 19))
    elif nombre == 'nota':
        p.drawRoundedRect(QRectF(4, 3, 16, 18), 2.5, 2.5)
        p.drawLine(QPointF(8, 8.5), QPointF(16, 8.5))
        p.drawLine(QPointF(8, 12.5), QPointF(16, 12.5))
        p.drawLine(QPointF(8, 16.5), QPointF(12.5, 16.5))
    elif nombre == 'reloj':
        p.drawEllipse(QPointF(12, 12), 9.5, 9.5)
        p.drawPolyline([QPointF(12, 6.8), QPointF(12, 12), QPointF(15.5, 14)])
    elif nombre == 'ajustes':   # deslizadores
        for y, x in ((5, 15), (12, 8), (19, 16)):
            p.drawLine(QPointF(3, y), QPointF(x - 2.2, y))
            p.drawLine(QPointF(x + 2.2, y), QPointF(21, y))
            p.drawEllipse(QPointF(x, y), 2.2, 2.2)
    elif nombre == 'subir':   # círculo con flecha hacia arriba (actualizó)
        p.drawEllipse(QPointF(12, 12), 9.5, 9.5)
        p.drawPolyline([QPointF(8, 12), QPointF(12, 8), QPointF(16, 12)])
        p.drawLine(QPointF(12, 8), QPointF(12, 16.5))
    elif nombre == 'carrito':
        p.drawPolyline([QPointF(2, 3), QPointF(5, 3), QPointF(7.6, 15), QPointF(18.4, 15), QPointF(21, 7),
                        QPointF(6.1, 7)])
        p.drawEllipse(QPointF(9, 19.5), 1.4, 1.4)
        p.drawEllipse(QPointF(17.5, 19.5), 1.4, 1.4)
    elif nombre == 'enviar':
        c = QPainterPath(QPointF(21.5, 2.5))
        c.lineTo(14.6, 21.5)
        c.lineTo(10.9, 13.1)
        c.lineTo(2.5, 9.4)
        c.closeSubpath()
        p.drawPath(c)
        p.drawLine(QPointF(21.5, 2.5), QPointF(10.9, 13.1))
    elif nombre == 'derecha':
        p.drawPolyline([QPointF(9, 6), QPointF(15, 12), QPointF(9, 18)])
    elif nombre == 'detener':
        p.drawRoundedRect(QRectF(6, 6, 12, 12), 2, 2)
    elif nombre == 'cupon':   # 2.8: un boleto con muescas a los lados y un «%» (la página Cupones)
        c = QPainterPath(QPointF(2.5, 6))
        c.lineTo(21.5, 6)
        c.lineTo(21.5, 9.8)
        c.arcTo(QRectF(19.3, 9.8, 4.4, 4.4), 90, 180)
        c.lineTo(21.5, 18)
        c.lineTo(2.5, 18)
        c.lineTo(2.5, 14.2)
        c.arcTo(QRectF(0.3, 9.8, 4.4, 4.4), 270, 180)
        c.closeSubpath()
        p.drawPath(c)
        p.drawLine(QPointF(9.4, 14.8), QPointF(14.6, 9.2))
        p.drawEllipse(QPointF(9.6, 9.8), 1.1, 1.1)
        p.drawEllipse(QPointF(14.4, 14.2), 1.1, 1.1)


def pintar_icono(nombre, color=TEXTO_SUAVE, tam=18, grosor=1.9, escala=3):
    """Pixmap nítido (dibujado al triple) de uno de los íconos de _trazar."""
    pm = QPixmap(tam * escala, tam * escala)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(tam * escala / 24, tam * escala / 24)
    p.setPen(QPen(QColor(color), grosor, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    _trazar(p, nombre)
    p.end()
    pm.setDevicePixelRatio(escala)
    return pm


def icono(nombre, color=TEXTO_SUAVE, tam=18):
    return QIcon(pintar_icono(nombre, color, tam))


def preparar_imagenes_qss():
    """La hoja de estilos necesita archivos para las flechas y la palomita: se dibujan en una carpeta temporal."""
    carpeta = Path(tempfile.gettempdir()) / 'cinecaptions-ventas-ui'
    try:
        carpeta.mkdir(exist_ok=True)
        for archivo, nombre, color, tam, grosor in (('abajo', 'abajo', TEXTO_SUAVE, 16, 2.0),
                                                    ('check', 'check', '#ffffff', 12, 3.0)):
            for escala, sufijo in ((1, ''), (2, '@2x'), (3, '@3x')):
                pm = pintar_icono(nombre, color, tam, grosor, escala)
                pm.setDevicePixelRatio(1)
                pm.save(str(carpeta / f'{archivo}{sufijo}.png'))
    except OSError:
        pass
    return carpeta.as_posix()


# ---------------------------------------------------------------- Estilo (QSS con los colores de la marca)

QSS = """
QMainWindow, QDialog { background: @SUPERFICIE; }
QWidget#raiz { background: @FONDO; }
QWidget { color: @TEXTO; }
QToolTip { background: @SUPERFICIE_2; color: @TEXTO; border: 1px solid @BORDE_FUERTE; border-radius: @RADIO_CHICO;
           padding: 6px 8px; }
QFrame#franja { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @ROJO, stop:0.6 @ROSA, stop:1 @VIOLETA);
                min-height: 2px; max-height: 2px; border: 0; }

QMenu { background: @SUPERFICIE; border: 1px solid @BORDE_FUERTE; padding: 4px; }
QMenu::item { padding: 8px 24px 8px 10px; border-radius: @RADIO_CHICO; color: @TEXTO; }
QMenu::item:selected { background: @SUPERFICIE_2; }
QMenu::item:disabled { color: @TEXTO_TENUE; }
QMenu::separator { height: 1px; background: @BORDE; margin: 4px 8px; }
QMenu::icon { padding-left: 8px; }

QLabel#subtitulo, QLabel#cargando { color: @TEXTO_TENUE; font-size: 12px; }
QLabel#suave { color: @TEXTO_SUAVE; }
QLabel#tenue { color: @TEXTO_TENUE; font-size: 12px; }
QLabel#dialogoTitulo { font-size: 17px; font-weight: 600; }
QLabel#error { color: @PELIGRO; }

QFrame#tarjeta { background: @SUPERFICIE; border: 1px solid @BORDE; border-radius: @RADIO; }
QFrame#tarjeta[destacada="true"] { border: 1px solid rgba(224, 36, 110, 64);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(239, 68, 68, 26), stop:0.6 rgba(224, 36, 110, 20),
                                stop:1 rgba(124, 77, 255, 30)); }
QFrame#tarjeta QLabel { background: transparent; }
QLabel#tarjetaTitulo { color: @TEXTO_TENUE; font-size: 11px; font-weight: 600; }
QLabel#tarjetaValor { color: @TEXTO; font-size: 22px; font-weight: 600; }
QLabel#tarjetaValor[apagada="true"] { color: @TEXTO_TENUE; }
QLabel#tarjetaDetalle { color: @TEXTO_SUAVE; font-size: 12px; }
QFrame#divisor { background: @BORDE; border: 0; }

QFrame#banda { background: rgba(239, 68, 68, 22); border: 1px solid rgba(239, 68, 68, 100); border-radius: @RADIO_CAJA; }
QFrame#banda[tipo="info"] { background: rgba(255, 164, 99, 18); border: 1px solid rgba(255, 164, 99, 90); }
QFrame#banda QLabel { background: transparent; }
QFrame#caja { background: @SUPERFICIE_2; border: 1px solid @BORDE; border-radius: @RADIO_CAJA; }
QFrame#caja QLabel { background: transparent; }

QLineEdit, QComboBox { background: @SUPERFICIE; border: 1px solid @BORDE; border-radius: @RADIO_CONTROL; padding: 0 10px;
                       min-height: 34px; color: @TEXTO; selection-background-color: @VIOLETA; selection-color: #ffffff; }
QLineEdit:hover, QComboBox:hover { border-color: @BORDE_FUERTE; }
QLineEdit:focus, QComboBox:focus, QComboBox:on { border-color: @VIOLETA; }
QLineEdit:disabled, QComboBox:disabled { color: @TEXTO_TENUE; background: @FONDO; border-color: @BORDE; }
QComboBox { padding-right: 30px; combobox-popup: 0; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 30px; border: 0; }
QComboBox::down-arrow { image: url("@IMG/abajo.png"); width: 14px; height: 14px; }
QComboBox QAbstractItemView { background: @SUPERFICIE; border: 1px solid @BORDE_FUERTE; padding: 4px; outline: 0;
                              selection-background-color: @SUPERFICIE_2; selection-color: @TEXTO; }
QComboBox QAbstractItemView::item { min-height: 32px; padding: 0 8px; border-radius: @RADIO_CHICO; }
QDateEdit { background: @SUPERFICIE; border: 1px solid @BORDE; border-radius: @RADIO_CONTROL; padding: 0 30px 0 10px;
            min-height: 34px; color: @TEXTO; selection-background-color: @VIOLETA; selection-color: #ffffff; }
QDateEdit:hover { border-color: @BORDE_FUERTE; }
QDateEdit:focus { border-color: @VIOLETA; }
QDateEdit:disabled { color: @TEXTO_TENUE; background: @FONDO; border-color: @BORDE; }
QDateEdit::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 30px; border: 0; }
QDateEdit::down-arrow { image: url("@IMG/abajo.png"); width: 14px; height: 14px; }
QCalendarWidget QWidget#qt_calendar_navigationbar { background: @SUPERFICIE_2; }
QCalendarWidget QToolButton { color: @TEXTO; background: transparent; border: 0; padding: 4px 8px; font-weight: 600; }
QCalendarWidget QToolButton:hover { background: @SUPERFICIE; border-radius: @RADIO_CHICO; }
QCalendarWidget QAbstractItemView { background: @SUPERFICIE; color: @TEXTO; selection-background-color: @VIOLETA;
                                    selection-color: #ffffff; outline: 0; }
QCalendarWidget QAbstractItemView:disabled { color: @TEXTO_TENUE; }

QPushButton { background: @SUPERFICIE_2; color: @TEXTO; border: 1px solid @BORDE; border-radius: @RADIO_CONTROL;
              padding: 0 14px; min-height: 34px; font-weight: 600; }
QPushButton:hover { border-color: @BORDE_FUERTE; background: #23222d; }
QPushButton:pressed { background: #18171f; border-color: @BORDE; }
QPushButton:disabled { color: @TEXTO_TENUE; background: @SUPERFICIE; border-color: @BORDE; }
QPushButton[tipo="primario"] { color: #ffffff; border: 1px solid transparent;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @ROJO, stop:0.6 @ROSA, stop:1 @VIOLETA); }
QPushButton[tipo="primario"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f25c5c, stop:0.6 #e83d82, stop:1 #8e64ff); }
QPushButton[tipo="primario"]:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d63a3a, stop:0.6 #c51f61, stop:1 #6b3fe6); }
QPushButton[tipo="primario"]:disabled { background: @SUPERFICIE_2; color: @TEXTO_TENUE; border-color: @BORDE; }
QPushButton[tipo="peligro"] { color: #ff9a9a; background: rgba(239, 68, 68, 24); border: 1px solid rgba(239, 68, 68, 110); }
QPushButton[tipo="peligro"]:hover { background: rgba(239, 68, 68, 44); border-color: rgba(239, 68, 68, 170); }
QPushButton[tipo="peligro"]:pressed { background: rgba(239, 68, 68, 16); }
QPushButton[tipo="peligro"]:disabled { color: @TEXTO_TENUE; background: @SUPERFICIE; border-color: @BORDE; }
QPushButton[tipo="enlace"] { background: transparent; border: 0; color: @VIOLETA_CLARO; padding: 0; min-height: 0;
                             font-weight: 500; text-align: left; }
QPushButton[tipo="enlace"]:hover { color: #d6cbff; text-decoration: underline; }
QPushButton[tipo="enlace"]:pressed { color: #a48cf0; }
QPushButton[tipo="enlace"]:disabled { color: @TEXTO_TENUE; }
QPushButton[chico="true"] { min-height: 28px; padding: 0 10px; border-radius: @RADIO_CHICO; font-size: 12px; }
QPushButton[lista="true"] { text-align: left; padding: 0 12px; }
QPushButton[tipo="icono"] { min-height: 0; padding: 0; border: 1px solid transparent; background: transparent;
                            border-radius: @RADIO_CHICO; }
QPushButton[tipo="icono"]:hover { background: #23222d; }
QPushButton[tipo="icono"]:pressed { background: #18171f; }
QPushButton[tipo="icono"]:disabled { background: transparent; }
QPushButton[cuadrado="true"] { padding: 0; min-height: 0; border-radius: @RADIO_CHICO; }

QFrame#segmentos { background: @SUPERFICIE; border: 1px solid @BORDE; border-radius: @RADIO_CONTROL; }
QPushButton[segmento="true"] { background: transparent; border: 1px solid transparent; border-radius: @RADIO_CHICO;
                               min-height: 26px; padding: 0 10px; color: @TEXTO_SUAVE; font-weight: 600; }
QPushButton[segmento="true"]:hover { color: @TEXTO; background: rgba(255, 255, 255, 7); }
QPushButton[segmento="true"]:pressed { background: rgba(255, 255, 255, 4); }
QPushButton[segmento="true"]:checked { background: @SUPERFICIE_2; color: @TEXTO; border-color: @BORDE_FUERTE; }
QPushButton[segmento="true"]:disabled { color: @TEXTO_TENUE; background: transparent; border-color: transparent; }
QPushButton[segmento="true"]:checked:disabled { background: @SUPERFICIE_2; border-color: @BORDE; }

QCheckBox { color: @TEXTO_SUAVE; spacing: 8px; background: transparent; }
QCheckBox:hover { color: @TEXTO; }
QCheckBox:disabled { color: @TEXTO_TENUE; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px; border: 1px solid @BORDE_FUERTE; background: @SUPERFICIE; }
QCheckBox::indicator:hover { border-color: @TEXTO_TENUE; }
QCheckBox::indicator:checked { border: 0; image: url("@IMG/check.png");
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 @ROSA, stop:1 @VIOLETA); }

QPushButton[teclado="true"] { border: 1px solid @VIOLETA; }
QPushButton[tipo="primario"][teclado="true"] { border: 1px solid rgba(255, 255, 255, 200); }
QPushButton[tipo="enlace"][teclado="true"] { border: 0; text-decoration: underline; }
QPushButton[segmento="true"][teclado="true"] { border-color: @VIOLETA; }
QCheckBox[teclado="true"]::indicator { border: 1px solid @VIOLETA; }

QFrame#marcoTabla { background: @SUPERFICIE; border: 1px solid @BORDE; border-radius: @RADIO; }
QTableView { background: @SUPERFICIE; border: 0; gridline-color: transparent; outline: 0;
             selection-background-color: @ELEGIDA; selection-color: @TEXTO; }
QTableView::item { border-bottom: 1px solid #1d1c25; padding: 0 6px; }
QTableView::item:selected { background: @ELEGIDA; color: @TEXTO; border-bottom: 1px solid @ELEGIDA_BORDE; }
QHeaderView { background: @SUPERFICIE; border: 0; }
QTableCornerButton::section { background: @SUPERFICIE; border: 0; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px 4px 2px; }
QScrollBar::handle:vertical { background: @BORDE_FUERTE; border-radius: 3px; min-height: 32px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px 4px 2px 4px; }
QScrollBar::handle:horizontal { background: @BORDE_FUERTE; border-radius: 3px; min-width: 32px; }
QScrollBar::handle:hover { background: #4a4857; }
QScrollBar::handle:pressed { background: #5b5968; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; border: 0; background: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QSplitter::handle { background: transparent; }

QFrame#panel { background: @SUPERFICIE; border: 1px solid @BORDE; border-radius: @RADIO; }
QScrollArea#panelScroll, QWidget#panelContenido { background: transparent; border: 0; }
QLabel#miniatura { background: @FONDO; border: 1px solid @BORDE; border-radius: @RADIO_CONTROL; }
QLabel#iniciales { background: @SUPERFICIE_2; border: 1px solid @BORDE_FUERTE; border-radius: 15px; color: @VIOLETA_CLARO; }
QFrame#bloqueCliente { background: transparent; border: 0; }
QPushButton#pestana { background: transparent; border: 0; border-radius: 0; padding: 0 0 9px 0; color: @TEXTO_SUAVE;
    font-weight: 600; }
QPushButton#pestana:hover { color: @TEXTO; }
QPushButton#pestana:checked { color: @TEXTO; border-bottom: 2px solid @ROSA; }
QLabel#miniatura:hover { border-color: @VIOLETA; }
QScrollArea#visorCaptura, QScrollArea#visorCaptura > QWidget > QWidget { background: @FONDO; border: 0; }
QFrame#seccion { background: transparent; border: 0; border-top: 1px solid @BORDE; border-radius: 0; }
QFrame#seccion QLabel, QFrame#equipo QLabel, QFrame#recurrente QLabel { background: transparent; }
QLabel#seccionTitulo { color: @TEXTO_TENUE; font-size: 11px; font-weight: 600; }
QLabel#nombreCliente { font-size: 18px; font-weight: 600; }
QLabel#claveTexto { font-family: "Cascadia Mono", "Consolas"; font-size: 14px; font-weight: 600; color: @TEXTO;
                    background: @FONDO; border: 1px solid @BORDE; border-radius: @RADIO_CONTROL; padding: 7px 10px; }
QFrame#equipo { background: @SUPERFICIE_2; border: 1px solid @BORDE; border-radius: @RADIO_CAJA; }
QFrame#recurrente { background: rgba(124, 77, 255, 22); border: 1px solid rgba(124, 77, 255, 90); border-radius: @RADIO_CAJA; }
QLabel#iconoCaja { background: rgba(124, 77, 255, 26); border: 1px solid rgba(124, 77, 255, 70); border-radius: @RADIO_CAJA; }
QLabel#iconoCaja[tono="aviso"] { background: rgba(255, 164, 99, 24); border-color: rgba(255, 164, 99, 80); }
QLabel#iconoCaja[tono="peligro"] { background: rgba(255, 107, 107, 24); border-color: rgba(255, 107, 107, 80); }
QLabel#iconoCaja[tono="tenue"] { background: @SUPERFICIE_2; border-color: @BORDE; }

QFrame#avisoCaja { background: @SUPERFICIE_2; border: 1px solid @BORDE_FUERTE; border-radius: @RADIO_CAJA; }
QFrame#avisoCaja QLabel { background: transparent; font-weight: 500; }

QStatusBar { background: @FONDO; color: @TEXTO_TENUE; border-top: 1px solid @BORDE; font-size: 12px; }
QStatusBar::item { border: 0; }
QStatusBar QLabel { color: @TEXTO_TENUE; font-size: 12px; }
QLabel#soloLectura { color: @VIOLETA_CLARO; background: rgba(124, 77, 255, 26); border: 1px solid rgba(124, 77, 255, 70);
                     border-radius: 8px; padding: 0 7px; font-size: 11px; font-weight: 600; }

QLabel#paginaSub { color: @TEXTO_TENUE; font-size: 13px; }
QLabel#numeroGrande { font-size: 28px; font-weight: 600; background: transparent; }
QLabel#cifra { font-size: 17px; font-weight: 600; background: transparent; }

QPlainTextEdit { background: @FONDO; border: 1px solid @BORDE; border-radius: @RADIO_CONTROL; padding: 6px 8px; color: @TEXTO;
                 selection-background-color: @VIOLETA; selection-color: #ffffff; }
QPlainTextEdit:hover { border-color: @BORDE_FUERTE; }
QPlainTextEdit:focus { border-color: @VIOLETA; }
QPlainTextEdit:disabled { color: @TEXTO_TENUE; }

QProgressBar { background: @SUPERFICIE_2; border: 0; border-radius: 4px; min-height: 8px; max-height: 8px; color: transparent; }
QProgressBar::chunk { border-radius: 4px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @ROJO, stop:0.6 @ROSA, stop:1 @VIOLETA); }

QScrollArea#paginaScroll, QWidget#paginaContenido { background: transparent; border: 0; }
"""


def hoja_estilo(carpeta_imagenes):
    valores = {'SUPERFICIE_2': SUPERFICIE_2, 'SUPERFICIE': SUPERFICIE, 'BORDE_FUERTE': BORDE_FUERTE, 'BORDE': BORDE,
               'TEXTO_SUAVE': TEXTO_SUAVE, 'TEXTO_TENUE': TEXTO_TENUE, 'TEXTO': TEXTO, 'FONDO': FONDO, 'ROJO': ROJO,
               'ROSA': ROSA, 'VIOLETA_CLARO': VIOLETA_CLARO, 'VIOLETA': VIOLETA, 'PELIGRO': PELIGRO,
               'ELEGIDA_BORDE': ELEGIDA_BORDE, 'ELEGIDA': ELEGIDA, 'RADIO_CONTROL': f'{RADIO_CONTROL}px',
               'RADIO_CHICO': f'{RADIO_CHICO}px', 'RADIO_CAJA': f'{RADIO_CAJA}px', 'RADIO': f'{RADIO}px',
               'IMG': carpeta_imagenes}
    qss = QSS
    for nombre in sorted(valores, key=len, reverse=True):   # primero los nombres largos (SUPERFICIE_2 antes que SUPERFICIE)
        qss = qss.replace('@' + nombre, valores[nombre])
    return qss


def paleta_oscura():
    pal = QPalette()
    for rol, color in ((QPalette.ColorRole.Window, SUPERFICIE), (QPalette.ColorRole.WindowText, TEXTO),
                       (QPalette.ColorRole.Base, SUPERFICIE), (QPalette.ColorRole.AlternateBase, SUPERFICIE_2),
                       (QPalette.ColorRole.Text, TEXTO), (QPalette.ColorRole.Button, SUPERFICIE_2),
                       (QPalette.ColorRole.ButtonText, TEXTO), (QPalette.ColorRole.Highlight, VIOLETA),
                       (QPalette.ColorRole.HighlightedText, '#ffffff'), (QPalette.ColorRole.ToolTipBase, SUPERFICIE_2),
                       (QPalette.ColorRole.ToolTipText, TEXTO), (QPalette.ColorRole.PlaceholderText, TEXTO_TENUE),
                       (QPalette.ColorRole.Link, VIOLETA_CLARO), (QPalette.ColorRole.Mid, BORDE),
                       (QPalette.ColorRole.Dark, FONDO), (QPalette.ColorRole.Light, BORDE_FUERTE),
                       (QPalette.ColorRole.BrightText, '#ffffff')):
        pal.setColor(rol, QColor(color))
    for rol in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, rol, QColor(TEXTO_TENUE))
    return pal


def cargar_fuentes():
    """Inter va incluida en el programa. Sin fuentes del sistema (plataforma «offscreen» de las capturas) se agregan
    Segoe UI y Consolas de Windows para que el texto no salga en cuadritos."""
    carpeta = recurso('fuentes')
    if carpeta.is_dir():
        for ruta in sorted(carpeta.glob('*.ttf')):
            QFontDatabase.addApplicationFont(str(ruta))
    familias = set(QFontDatabase.families())
    if 'Segoe UI' not in familias or 'Consolas' not in familias:
        windows = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'
        for nombre in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf', 'consola.ttf', 'consolab.ttf', 'seguisym.ttf'):
            if (windows / nombre).is_file():
                QFontDatabase.addApplicationFont(str(windows / nombre))


def sin_alternativas(f):
    """Sin las alternativas contextuales de Inter: en «ch_k7x2» la x no se vuelve ×."""
    try:
        f.setFeature(QFont.Tag('calt'), 0)
    except (AttributeError, TypeError):
        pass
    return f


def fuente(px=13, peso=QFont.Weight.Normal, mono=False, espaciado=None, cifras=False):
    """La letra de la app. cifras: con cifras tabulares, para los números que van en columna o que cambian (montos,
    conteos, fechas de las tablas, la escala de la gráfica): quedan alineados y no bailan. Solo ahí: en Inter, «tnum»
    también ensancha el guion y angosta el espacio («LAPTOP-HP-ML» se veía «LAPTOP - HP - ML»)."""
    f = QFont()
    f.setFamilies(MONO if mono else FUENTES)
    f.setPixelSize(px)
    f.setWeight(peso)
    sin_alternativas(f)
    if cifras:
        con_cifras_tabulares(f)
    if espaciado:
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, espaciado)
    return f


def con_cifras_tabulares(f):
    """Cifras del mismo ancho (los montos quedan alineados en la tabla). Ver fuente()."""
    try:
        f.setFeature(QFont.Tag('tnum'), 1)
    except (AttributeError, TypeError):
        pass
    return f


def oscurecer_barra(ventana):
    """Barra de título oscura y del color del fondo en Windows 10/11 (DwmSetWindowAttribute)."""
    if os.name != 'nt' or QGuiApplication.platformName() != 'windows':
        return
    try:
        hwnd = ctypes.c_void_p(int(ventana.winId()))
        dwm = ctypes.windll.dwmapi
        oscuro = ctypes.c_int(1)
        for atributo in (20, 19):   # DWMWA_USE_IMMERSIVE_DARK_MODE (y su número viejo en Windows 10)
            if dwm.DwmSetWindowAttribute(hwnd, atributo, ctypes.byref(oscuro), ctypes.sizeof(oscuro)) == 0:
                break
        color = ctypes.c_uint32(0x00100B0B)   # COLORREF (0x00BBGGRR) de #0b0b10
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), ctypes.sizeof(color))   # DWMWA_CAPTION_COLOR
    except (OSError, AttributeError, ValueError):
        pass


def fijar_fuente(app):
    """Inter en toda la app. Windows le pone su letra (Segoe UI de 9 puntos) a las tablas y sus encabezados, los menús,
    las cajas de mensaje, los globitos y la barra de estado, y se la vuelve a poner al aplicar la hoja de estilos o al
    cambiar el tema: app.setFont() sin clase quita esas letras de cada clase."""
    app.setFont(fuente(13))


class FiltroVentanas(QObject):
    """Cada ventana o diálogo que se abre recibe la barra de título oscura. Si Windows cambia el tema (claro, oscuro,
    contraste), vuelve a poner Inter en las tablas y los menús (ver fijar_fuente). Un botón o una casilla a la que se
    llega con Tab lleva la propiedad «teclado» (el borde violeta de la hoja de estilos): así el foco se ve al usar el
    teclado, pero no se queda marcado el botón al que se le dio clic."""
    TECLADO = (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason)

    def eventFilter(self, objeto, evento):
        tipo = evento.type()
        if tipo == QEvent.Type.Show and isinstance(objeto, QWidget) and objeto.isWindow() \
                and not objeto.property('_barra_oscura'):
            objeto.setProperty('_barra_oscura', True)
            oscurecer_barra(objeto)
        elif tipo in (QEvent.Type.FocusIn, QEvent.Type.FocusOut) and isinstance(objeto, (QPushButton, QCheckBox)):
            teclado = tipo == QEvent.Type.FocusIn and evento.reason() in self.TECLADO
            if bool(objeto.property('teclado')) != teclado:
                objeto.setProperty('teclado', teclado)
                repulir(objeto)
        elif tipo == QEvent.Type.ThemeChange and QApplication.font('QAbstractItemView') != QApplication.font():
            QTimer.singleShot(0, lambda: fijar_fuente(QApplication.instance()))
        return False


# ---------------------------------------------------------------- Piezas de la ventana

def etiqueta(texto='', nombre=None, plano=True, espaciado=False, seleccionable=False):
    """QLabel con su objectName (para la hoja de estilos). Texto plano por defecto: los nombres los escriben los clientes."""
    lbl = QLabel(texto)
    if nombre:
        lbl.setObjectName(nombre)
    if plano:
        lbl.setTextFormat(Qt.TextFormat.PlainText)
    if espaciado:   # títulos chicos en mayúsculas, un poco separados
        f = lbl.font()
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
        lbl.setFont(f)
    if seleccionable:
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setCursor(Qt.CursorShape.IBeamCursor)
    return lbl


def boton(texto, nombre_icono=None, tipo=None, chico=False, color_icono=None):
    b = QPushButton((' ' + texto) if nombre_icono else texto)   # un espacio entre el ícono y el texto
    if tipo:
        b.setProperty('tipo', tipo)
    if chico:
        b.setProperty('chico', True)
    if nombre_icono:
        color = color_icono or {'primario': '#ffffff', 'peligro': '#ff9a9a', 'enlace': VIOLETA_CLARO}.get(tipo, TEXTO_SUAVE)
        b.setIcon(icono(nombre_icono, color, 16))
        b.setIconSize(QSize(15, 15) if chico else QSize(16, 16))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def vaciar(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().hide()   # (si no, se ve un momento encima de lo nuevo hasta que deleteLater lo borra)
            item.widget().deleteLater()
        elif item.layout():
            vaciar(item.layout())


def repulir(widget):
    """Vuelve a aplicar la hoja de estilos después de cambiar una propiedad dinámica."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class Recortada(QLabel):
    """Etiqueta de una línea que corta con «…» lo que no cabe (el texto completo queda en el tooltip). ajustada: pide
    solo el ancho de su texto (así un botón puesto después queda pegado al texto y no al otro lado del panel)."""

    def __init__(self, texto='', nombre=None, ajustada=False):
        super().__init__()
        if nombre:
            self.setObjectName(nombre)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self._ajustada = ajustada
        self.setSizePolicy(QSizePolicy.Policy.Preferred if ajustada else QSizePolicy.Policy.Ignored,
                           QSizePolicy.Policy.Preferred)
        self._completo = ''
        self.poner(texto)

    def poner(self, texto):
        self._completo = texto or ''
        self._recortar()
        if self._ajustada:
            self.updateGeometry()

    def sizeHint(self):
        if not self._ajustada:
            return super().sizeHint()
        m = self.contentsMargins()
        return QSize(self.fontMetrics().horizontalAdvance(self._completo) + 2 + m.left() + m.right(),
                     super().sizeHint().height())

    def texto(self):
        return self._completo

    def _recortar(self):
        ancho = max(10, self.contentsRect().width())
        corto = self.fontMetrics().elidedText(self._completo, Qt.TextElideMode.ElideRight, ancho)
        super().setText(corto)
        self.setToolTip(self._completo if corto != self._completo else '')

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._recortar()

    def changeEvent(self, evento):
        super().changeEvent(evento)
        if evento.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._recortar()

    def minimumSizeHint(self):
        return QSize(16, super().minimumSizeHint().height())


class CampoBuscar(QLineEdit):
    """Buscador cuyo texto de ayuda se acorta cuando el campo es angosto («Buscar cliente, correo o clave…» →
    «Buscar cliente…» → «Buscar…»): así nunca sale cortado a la mitad. textos: uno o varios, del más largo al más corto."""

    def __init__(self, textos):
        super().__init__()
        self._textos = (textos,) if isinstance(textos, str) else tuple(textos)
        self._ajustar()

    def _ajustar(self):
        libre = self.width() - 66   # (la lupa, el botón de borrar y los márgenes)
        fm = self.fontMetrics()
        texto = next((t for t in self._textos if fm.horizontalAdvance(t) <= libre), self._textos[-1])
        if texto != self.placeholderText():
            self.setPlaceholderText(texto)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._ajustar()

    def changeEvent(self, evento):
        super().changeEvent(evento)
        if evento.type() == QEvent.Type.FontChange:
            self._ajustar()


class Indicador(QWidget):
    """Ruedita de «cargando» con el degradado de la marca."""

    def __init__(self, tam=18, parent=None):
        super().__init__(parent)
        self.setFixedSize(tam, tam)
        self._angulo = 0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._girar)
        politica = self.sizePolicy()
        politica.setRetainSizeWhenHidden(True)
        self.setSizePolicy(politica)
        self.hide()

    def activar(self, activo):
        if activo:
            self._timer.start()
            self.show()
        else:
            self._timer.stop()
            self.hide()

    def _girar(self):
        self._angulo = (self._angulo + 7) % 360
        self.update()

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        p.setPen(QPen(QColor(BORDE_FUERTE), 2.2))
        p.drawEllipse(r)
        g = QConicalGradient(r.center(), -self._angulo)
        g.setColorAt(0.0, QColor(VIOLETA))
        g.setColorAt(0.5, QColor(ROSA))
        g.setColorAt(1.0, QColor(ROJO))
        lapiz = QPen(QBrush(g), 2.4)
        lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(lapiz)
        p.drawArc(r, int(-self._angulo * 16), 110 * 16)


class TituloMarca(QWidget):
    """«CineCaptions Ventas», con «Ventas» en el degradado de la marca."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fuente = fuente(19, QFont.Weight.Bold)
        self._a, self._b = 'CineCaptions ', 'Ventas'
        fm = QFontMetrics(self._fuente)
        self.setFixedSize(fm.horizontalAdvance(self._a + self._b) + 6, fm.height() + 2)

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self._fuente)
        fm = QFontMetrics(self._fuente)
        y = fm.ascent() + 1
        p.setPen(QColor(TEXTO))
        p.drawText(0, y, self._a)
        x = fm.horizontalAdvance(self._a)
        g = QLinearGradient(x, 0, x + fm.horizontalAdvance(self._b), 0)
        g.setColorAt(0.0, QColor('#ff6b6b'))
        g.setColorAt(0.55, QColor('#f0407f'))
        g.setColorAt(1.0, QColor(VIOLETA_CLARO))
        p.setPen(QPen(QBrush(g), 1))
        p.drawText(x, y, self._b)


class Tarjeta(QFrame):
    """Una tarjeta del resumen: título chico, valor grande y una línea de detalle."""

    def __init__(self, titulo, destacada=False):
        super().__init__()
        self.setObjectName('tarjeta')
        self.setProperty('destacada', destacada)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(4)
        self.titulo = etiqueta(titulo.upper(), 'tarjetaTitulo', espaciado=True)
        self.valor = etiqueta('—', 'tarjetaValor', plano=False)
        self.valor.setFont(fuente(22, QFont.Weight.DemiBold, cifras=True))   # (el tamaño lo pone la hoja de estilos)
        self.valor.setTextFormat(Qt.TextFormat.RichText)
        self.detalle = etiqueta(' ', 'tarjetaDetalle')
        lay.addWidget(self.titulo)
        lay.addWidget(self.valor)
        lay.addWidget(self.detalle)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner(self, valor_html, detalle, color=None, ayuda='', apagada=False):
        """apagada: el valor es cero (sale más tenue: lo que sí tiene números resalta)."""
        self.valor.setText(valor_html)
        if bool(self.valor.property('apagada')) != apagada:
            self.valor.setProperty('apagada', apagada)
            repulir(self.valor)
        self.detalle.setText(detalle)
        self.detalle.setStyleSheet(f'color: {color};' if color else '')
        self.setToolTip(ayuda)

    def poner_titulo(self, titulo):
        self.titulo.setText(titulo.upper())

    def tamano_valor(self, px):
        self.valor.setStyleSheet(f'font-size: {px}px;')


class FilaTarjetas(QWidget):
    """Las seis tarjetas en una fila (el número grande se achica si la ventana es angosta); en una ventana muy
    angosta pasan a dos filas de tres."""

    def __init__(self, tarjetas):
        super().__init__()
        self.tarjetas = tarjetas
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(16)
        self._grid.setVerticalSpacing(16)
        self._columnas = 0
        self._px = 0
        self._acomodar(len(tarjetas))

    def _acomodar(self, columnas):
        if columnas == self._columnas:
            return
        self._columnas = columnas
        for t in self.tarjetas:
            self._grid.removeWidget(t)
        for i, t in enumerate(self.tarjetas):
            self._grid.addWidget(t, i // columnas, i % columnas)
        for c in range(len(self.tarjetas)):
            self._grid.setColumnStretch(c, 1 if c < columnas else 0)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        ancho = evento.size().width()
        self._acomodar(len(self.tarjetas) if ancho >= 900 else 3)
        por_tarjeta = (ancho - 16 * (self._columnas - 1)) / self._columnas
        px = 22 if por_tarjeta >= 205 else 19 if por_tarjeta >= 170 else 17
        if px != self._px:
            self._px = px
            for t in self.tarjetas:
                t.tamano_valor(px)


class Banda(QFrame):
    """Aviso de error arriba de las tablas (sin conexión, clave incorrecta...), con «Reintentar».
    Con tipo='info' es el aviso naranja de «falta subir el servidor nuevo» (sin botones)."""
    reintentar = Signal()
    clave = Signal()

    def __init__(self, tipo='error'):
        super().__init__()
        self.setObjectName('banda')
        self.setProperty('tipo', tipo)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 12, 12)
        lay.setSpacing(12)
        ic = QLabel()
        ic.setPixmap(pintar_icono('aviso' if tipo == 'error' else 'info', PELIGRO if tipo == 'error' else AVISO, 20))
        self.texto = etiqueta('')
        self.texto.setWordWrap(True)
        self.btn_clave = boton('Cambiar clave', 'llave', chico=True)
        self.btn_reintentar = boton('Reintentar', 'actualizar', chico=True)
        self.btn_clave.clicked.connect(self.clave)
        self.btn_reintentar.clicked.connect(self.reintentar)
        lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop if tipo == 'info' else Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.texto, 1)
        lay.addWidget(self.btn_clave)
        lay.addWidget(self.btn_reintentar)
        self.btn_reintentar.setVisible(tipo == 'error')
        self.btn_clave.hide()
        self.hide()

    def mostrar(self, mensaje, boton_clave=None):
        self.texto.setText(mensaje)
        self.btn_clave.setVisible(bool(boton_clave))
        if boton_clave:
            self.btn_clave.setText(' ' + boton_clave)
        self.show()


class Aviso(QWidget):
    """Mensajito que aparece abajo unos segundos («Clave copiada», «Licencia bloqueada»...). Va centrado sobre el
    contenido (zona: lo que da ese rectángulo; sin ella, sobre toda la ventana), con una sombra suave, y no tapa los
    clics: lo que está debajo se sigue pudiendo usar."""
    SOMBRA = 14   # lo que se agranda el widget alrededor de la caja para que quepa la sombra

    def __init__(self, parent, zona=None):
        super().__init__(parent)
        self.zona = zona
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        exterior = QHBoxLayout(self)
        exterior.setContentsMargins(self.SOMBRA, self.SOMBRA - 4, self.SOMBRA, self.SOMBRA + 4)
        self.caja = QFrame()
        self.caja.setObjectName('avisoCaja')
        exterior.addWidget(self.caja)
        lay = QHBoxLayout(self.caja)
        lay.setContentsMargins(12, 10, 16, 10)
        lay.setSpacing(10)
        self.ic = QLabel()
        self.texto = etiqueta('')
        lay.addWidget(self.ic)
        lay.addWidget(self.texto)
        self._efecto = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._efecto)
        self._anim = QPropertyAnimation(self._efecto, b'opacity', self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._al_terminar)
        self._reloj = QTimer(self)
        self._reloj.setSingleShot(True)
        self._reloj.timeout.connect(self.ocultar)
        self.hide()

    def mostrar(self, texto, tipo='ok'):
        nombre, color = {'ok': ('ok', VIOLETA_CLARO), 'error': ('aviso', PELIGRO),
                         'info': ('info', VIOLETA_CLARO)}.get(tipo, ('ok', VIOLETA_CLARO))
        self.ic.setPixmap(pintar_icono(nombre, color, 18))
        self.texto.setText(texto)
        self.adjustSize()
        self.acomodar()
        self.raise_()
        visible = self.isVisible()   # (antes de show: si estaba escondido, aparece desde transparente)
        self.show()
        self._anim.stop()
        self._anim.setStartValue(self._efecto.opacity() if visible else 0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._reloj.start(3600 if tipo == 'error' else 2800)

    def ocultar(self):
        self._anim.stop()
        self._anim.setStartValue(self._efecto.opacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _al_terminar(self):
        if self._efecto.opacity() <= 0.01:
            self.hide()

    def acomodar(self):
        padre = self.parentWidget()
        if padre:
            zona = self.zona() if self.zona else padre.rect()
            self.move(zona.center().x() - self.width() // 2, zona.bottom() - self.height() - 8)

    def paintEvent(self, _evento):
        """La sombra: capas redondeadas cada vez más grandes y más tenues, un poco hacia abajo (la caja va encima)."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        caja = QRectF(self.caja.geometry())
        for i, alfa in enumerate((34, 22, 14, 8, 4)):
            p.setBrush(QColor(0, 0, 0, alfa))
            crece = 1.5 + i * 2.2
            p.drawRoundedRect(caja.adjusted(-crece, -crece + 2, crece, crece + 3), RADIO_CAJA + crece, RADIO_CAJA + crece)


class Encabezado(QHeaderView):
    """Encabezado de las tablas: el título chico y, en la columna por la que está ordenada, la flechita justo después
    del título (pegada al borde de la columna parecía de la columna de al lado). La columna ordenada y la que está bajo
    el mouse se ven más claras."""

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._encima = -1
        self._fuente = fuente(12, QFont.Weight.DemiBold)
        self._flechas = {Qt.SortOrder.AscendingOrder: pintar_icono('arriba', TEXTO_SUAVE, 10, 2.6),
                         Qt.SortOrder.DescendingOrder: pintar_icono('abajo', TEXTO_SUAVE, 10, 2.6)}
        self.setMouseTracking(True)

    def mouseMoveEvent(self, evento):
        super().mouseMoveEvent(evento)
        n = self.logicalIndexAt(evento.position().toPoint())
        if n != self._encima:
            self._encima = n
            self.viewport().update()

    def leaveEvent(self, evento):
        super().leaveEvent(evento)
        self._encima = -1
        self.viewport().update()

    def paintSection(self, painter, rect, indice):
        if not rect.isValid() or self.model() is None:
            return
        painter.save()
        painter.fillRect(rect, QColor(SUPERFICIE))
        painter.setPen(QColor(BORDE))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        texto = str(self.model().headerData(indice, self.orientation(), Qt.ItemDataRole.DisplayRole) or '')
        alinear = self.model().headerData(indice, self.orientation(), Qt.ItemDataRole.TextAlignmentRole)
        alinear = getattr(alinear, 'value', alinear) or 0   # (según PySide llega como número o como Qt.AlignmentFlag)
        ordenada = self.isSortIndicatorShown() and self.sortIndicatorSection() == indice
        fm = QFontMetrics(self._fuente)
        derecha = alinear & Qt.AlignmentFlag.AlignRight.value
        # El mismo margen que el texto de las celdas: 9 px (los delegados dibujan ahí y en las celdas comunes son los 6 de
        # «padding» de la hoja de estilos más los 3 que deja el estilo); a la derecha, el de los montos
        area = rect.adjusted(9, 0, -(MARGEN_MONTO if derecha else 9), 0)
        flecha = 14 if ordenada else 0
        texto = fm.elidedText(texto, Qt.TextElideMode.ElideRight, max(0, area.width() - flecha))
        ancho = fm.horizontalAdvance(texto)
        if derecha:
            x = area.right() + 1 - flecha - ancho
        elif alinear & Qt.AlignmentFlag.AlignHCenter.value:
            x = area.left() + (area.width() - flecha - ancho) // 2
        else:
            x = area.left()
        painter.setFont(self._fuente)
        painter.setPen(QColor(TEXTO if indice == self._encima else TEXTO_SUAVE if ordenada else TEXTO_TENUE))
        painter.drawText(QRectF(x, rect.top(), ancho + 2, rect.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, texto)
        if ordenada:
            painter.drawPixmap(QPointF(x + ancho + 4, rect.top() + (rect.height() - 10) / 2), self._flechas[self.sortIndicatorOrder()])
        painter.restore()


MARGEN_MONTO = 16   # lo que se separan los montos (alineados a la derecha) de la columna que sigue


class Tabla(QTableView):
    """Tabla que, si no tiene filas, muestra un mensaje en el centro («No hay ventas con este filtro»), con el ícono de
    su página arriba. En una ventana angosta esconde primero las columnas menos importantes (su dato sigue en el panel de
    la derecha). La fila que está bajo el mouse se ilumina completa (con :hover en la hoja de estilos solo se iluminaba
    la celda)."""

    def __init__(self, nombre_icono=None, mensaje=''):
        super().__init__()
        self.setHorizontalHeader(Encabezado(self))
        self._icono_vacio = pintar_icono(nombre_icono, TEXTO_TENUE, 22) if nombre_icono else None
        self.mensaje_vacio = mensaje   # (al abrir, «Cargando…»: la tabla no se ve vacía y muda mientras llegan los datos)
        self.ocultables = []   # columnas que se esconden si no caben: la primera es la que se va primero
        self.anchos = {}       # columna → el ancho que necesita
        self.minimo = 0        # lo que ocupan las columnas que siempre se ven
        self.fila_encima = -1  # la fila (de la vista) que está bajo el mouse; la pintan los delegados
        self.setMouseTracking(True)
        self.setItemDelegate(DelegadoFila(self))

    def _repintar_fila(self, fila):
        if fila >= 0:
            self.viewport().update(0, self.rowViewportPosition(fila), self.viewport().width(), self.rowHeight(fila))

    def _poner_encima(self, fila):
        if fila != self.fila_encima:
            anterior, self.fila_encima = self.fila_encima, fila
            self._repintar_fila(anterior)
            self._repintar_fila(fila)

    def mouseMoveEvent(self, evento):
        super().mouseMoveEvent(evento)
        self._poner_encima(self.rowAt(int(evento.position().y())))

    def wheelEvent(self, evento):   # al bajar con la rueda, la fila bajo el mouse cambia sin moverlo
        super().wheelEvent(evento)
        self._poner_encima(self.rowAt(int(evento.position().y())))

    def viewportEvent(self, evento):
        if evento.type() == QEvent.Type.Leave:   # (salir hacia el encabezado o fuera de la tabla)
            self._poner_encima(-1)
        return super().viewportEvent(evento)

    def acomodar_columnas(self):
        libre = self.viewport().width() - self.minimo
        mostrar = set()
        for columna in reversed(self.ocultables):   # de la más importante a la menos, mientras quepan
            ancho = self.anchos.get(columna, 100)
            if ancho > libre:
                break   # si una no cabe, las menos importantes tampoco se muestran (no queda un hueco raro)
            mostrar.add(columna)
            libre -= ancho
        for columna in self.ocultables:
            if self.isColumnHidden(columna) == (columna in mostrar):
                self.setColumnHidden(columna, columna not in mostrar)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.acomodar_columnas()

    def paintEvent(self, evento):
        super().paintEvent(evento)
        if self.model() is not None and self.model().rowCount() == 0 and self.mensaje_vacio:
            p = QPainter(self.viewport())
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            if self.mensaje_vacio.startswith('Cargando'):
                self._pintar_cargando(p)
            else:
                pintar_vacio(p, QRectF(self.viewport().rect()), self.mensaje_vacio, self._icono_vacio)

    def _pintar_cargando(self, p):
        """Mientras llegan los datos: filas grises del alto de las de verdad, con una rayita en cada columna donde va su
        texto (dos en las de dos líneas, una pastilla en las de estado y a la derecha en «Monto»), cada vez más tenues
        hacia abajo. Como «Últimas ventas»: al llegar los datos nada salta de lugar."""
        alto = self.verticalHeader().defaultSectionSize()
        ancho_vista = self.viewport().width()
        columnas = [c for c in range(self.model().columnCount()) if not self.isColumnHidden(c)]
        gris = QColor('#1e1d27')
        for i in range(min(12, self.viewport().height() // alto + 1)):
            y = i * alto
            p.setOpacity(max(0.15, 1 - i * 0.13))
            p.setPen(QPen(QColor('#1d1c25'), 1))   # la raya de abajo, como en las filas de verdad
            p.drawLine(QPointF(0, y + alto - 0.5), QPointF(ancho_vista, y + alto - 0.5))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(gris)
            centro = y + alto / 2
            for n, c in enumerate(columnas):
                x, ancho = self.columnViewportPosition(c), self.columnWidth(c)
                delegado = self.itemDelegateForColumn(c)
                libre = max(16.0, ancho - 17.0)
                largo = min(libre, 150.0) * (0.42 + 0.08 * ((i * 3 + n * 5) % 6))   # (de 42 a 82 %, sin repetirse)
                if isinstance(delegado, DelegadoInsignia):
                    p.drawRoundedRect(QRectF(x + 9, centro - 9, min(libre, 44.0 + 4 * ((i + n) % 4)), 18), 9, 9)
                elif isinstance(delegado, DelegadoMonto):
                    largo = min(libre, 72.0)
                    p.drawRoundedRect(QRectF(x + ancho - MARGEN_MONTO - largo, centro - 4.5, largo, 9), 4.5, 4.5)
                elif isinstance(delegado, DelegadoDosLineas):
                    p.drawRoundedRect(QRectF(x + 9, centro - 10, largo, 9), 4.5, 4.5)
                    p.drawRoundedRect(QRectF(x + 9, centro + 4, largo * 0.7, 7), 3.5, 3.5)
                else:
                    p.drawRoundedRect(QRectF(x + 9, centro - 4.5, largo * 0.8, 9), 4.5, 4.5)
        p.setOpacity(1)


def pintar_vacio(p, area, mensaje, icono_pm=None):
    """Un estado vacío: el ícono en un cuadro tenue y el mensaje abajo, juntos y un poco arriba del centro (donde el
    ojo ve el centro). Lo usan las tablas, la gráfica y «Últimas ventas»."""
    f = fuente(13)
    fm = QFontMetrics(f)
    ancho = max(40.0, min(area.width() - 48, 380.0))
    texto = fm.boundingRect(QRectF(0, 0, ancho, 1000).toRect(), int(Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap),
                            mensaje)
    cuadro = 44 if icono_pm is not None and area.height() >= 140 else 0
    alto = cuadro + (14 if cuadro else 0) + texto.height()
    y = area.top() + max(8.0, (area.height() - alto) * 0.44)
    if cuadro:
        caja = QRectF(area.center().x() - cuadro / 2, y, cuadro, cuadro)
        p.setPen(QPen(QColor(BORDE), 1))
        p.setBrush(QColor(SUPERFICIE_2))
        p.drawRoundedRect(caja.adjusted(0.5, 0.5, -0.5, -0.5), RADIO_CAJA, RADIO_CAJA)
        lado = icono_pm.width() / icono_pm.devicePixelRatio()
        p.drawPixmap(QPointF(caja.center().x() - lado / 2, caja.center().y() - lado / 2), icono_pm)
        y += cuadro + 14
    p.setFont(f)
    p.setPen(QColor(TEXTO_TENUE))
    p.drawText(QRectF(area.center().x() - ancho / 2, y, ancho, texto.height() + 2),
               Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, mensaje)


ROL_ORDEN = Qt.ItemDataRole.UserRole + 1      # valor para ordenar la columna
ROL_INSIGNIA = Qt.ItemDataRole.UserRole + 2   # (texto, color, forma, color del texto)


class DelegadoFila(QStyledItemDelegate):
    """Las celdas normales de las tablas: debajo del texto, el fondo de la fila que está bajo el mouse."""

    def fondo_encima(self, painter, option, index):
        if getattr(option.widget, 'fila_encima', -1) == index.row() and not option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(ENCIMA))

    def paint(self, painter, option, index):
        self.fondo_encima(painter, option, index)
        super().paint(painter, option, index)


class DelegadoInsignia(DelegadoFila):
    """Dibuja el estado como pastilla de color («Pagada») o como punto + texto («● Activa»)."""

    def paint(self, painter, option, index):
        datos = index.data(ROL_INSIGNIA)
        if not datos:
            return super().paint(painter, option, index)
        self.fondo_encima(painter, option, index)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ''
        estilo = opt.widget.style() if opt.widget else QApplication.style()
        estilo.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        texto, color, forma, color_texto = datos
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = fuente(12, QFont.Weight.DemiBold)
        painter.setFont(f)
        fm = QFontMetrics(f)
        r = QRectF(opt.rect).adjusted(9, 0, -6, 0)
        c = QColor(color)
        if forma == 'pastilla':
            alto = 22.0
            caja = QRectF(r.left(), r.center().y() - alto / 2, min(fm.horizontalAdvance(texto) + 20.0, r.width()), alto)
            fondo, borde = QColor(c), QColor(c)
            fondo.setAlpha(PASTILLA_FONDO)
            borde.setAlpha(PASTILLA_BORDE)
            painter.setPen(QPen(borde, 1))
            painter.setBrush(fondo)
            painter.drawRoundedRect(caja.adjusted(0.5, 0.5, -0.5, -0.5), alto / 2, alto / 2)
            painter.setPen(c)
            painter.drawText(caja, Qt.AlignmentFlag.AlignCenter, texto)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c)
            painter.drawEllipse(QRectF(r.left() + 1, r.center().y() - 3.5, 7, 7))
            painter.setPen(QColor(color_texto or TEXTO_SUAVE))
            painter.drawText(r.adjusted(15, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             fm.elidedText(texto, Qt.TextElideMode.ElideRight, int(r.width() - 15)))
        painter.restore()


PASTILLA_FONDO, PASTILLA_BORDE = 30, 76   # la transparencia del fondo y del borde de las pastillas («Pagada», «5.54»)


class DelegadoBoton(DelegadoInsignia):
    """Una columna que, además de pastillas y puntos, puede llevar un botón dentro de la celda (forma 'boton': «Avisar»
    en Versiones). Al soltar el clic sobre el botón avisa con «apretado» (la fila de la tabla, ya elegida por el clic).
    El botón se ilumina con la fila que está bajo el mouse."""
    apretado = Signal(object)   # el índice (de la tabla) de la celda
    ALTO = 26.0
    _iconos = {}                # el megáfono de cada color, dibujado una sola vez

    @staticmethod
    def caja(rect, texto):
        """Dónde va el botón dentro de la celda (el mismo cálculo al pintar y al recibir el clic)."""
        fm = QFontMetrics(fuente(12, QFont.Weight.DemiBold))
        r = QRectF(rect).adjusted(9, 0, -6, 0)
        ancho = min(fm.horizontalAdvance(texto) + 30 + 12, r.width())
        return QRectF(r.left(), r.center().y() - DelegadoBoton.ALTO / 2, ancho, DelegadoBoton.ALTO)

    def paint(self, painter, option, index):
        datos = index.data(ROL_INSIGNIA)
        if not datos or datos[2] != 'boton':
            return super().paint(painter, option, index)
        self.fondo_encima(painter, option, index)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ''
        estilo = opt.widget.style() if opt.widget else QApplication.style()
        estilo.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        texto, color = datos[0], QColor(datos[1])
        encima = getattr(option.widget, 'fila_encima', -1) == index.row()
        caja = self.caja(opt.rect, texto)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fondo, borde = QColor(color), QColor(color)
        fondo.setAlpha(64 if encima else 38)
        borde.setAlpha(200 if encima else 130)
        painter.setPen(QPen(borde, 1))
        painter.setBrush(fondo)
        painter.drawRoundedRect(caja.adjusted(0.5, 0.5, -0.5, -0.5), RADIO_CHICO, RADIO_CHICO)
        claro = '#ffffff' if encima else VIOLETA_CLARO
        if claro not in self._iconos:
            self._iconos[claro] = pintar_icono('megafono', claro, 14)
        painter.drawPixmap(QPointF(caja.left() + 10, caja.center().y() - 7), self._iconos[claro])
        painter.setFont(fuente(12, QFont.Weight.DemiBold))
        painter.setPen(QColor(claro))
        painter.drawText(caja.adjusted(30, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, texto)
        painter.restore()

    def editorEvent(self, evento, modelo, opcion, indice):
        if evento.type() == QEvent.Type.MouseButtonRelease and evento.button() == Qt.MouseButton.LeftButton:
            datos = indice.data(ROL_INSIGNIA)
            if datos and datos[2] == 'boton' and self.caja(opcion.rect, datos[0]).contains(evento.position()):
                self.apretado.emit(indice)
                return True
        return super().editorEvent(evento, modelo, opcion, indice)


def partir_monto(texto):
    """«$29.00 USD» → («$29.00», «USD»): el número y la moneda se dibujan con distinto color."""
    numero, _, codigo = (texto or '').rpartition(' ')
    return (numero, codigo) if numero and codigo.isalpha() else (texto or '', '')


class DelegadoMonto(DelegadoFila):
    """La columna «Monto»: el número claro y la moneda («USD») más tenue, alineados a la derecha y con aire antes de la
    columna que sigue. La letra (tachada si se reembolsó) y el color del número vienen del modelo."""

    def paint(self, painter, option, index):
        self.fondo_encima(painter, option, index)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        numero, codigo = partir_monto(opt.text)
        opt.text = ''
        estilo = opt.widget.style() if opt.widget else QApplication.style()
        estilo.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        propia = index.data(Qt.ItemDataRole.FontRole)
        f = propia if isinstance(propia, QFont) else fuente(13, QFont.Weight.Medium, cifras=True)
        fc = QFont(f)
        fc.setPixelSize(max(9, f.pixelSize() - 2))
        fc.setWeight(QFont.Weight.Medium)
        color = index.data(Qt.ItemDataRole.ForegroundRole)
        color = color if isinstance(color, QColor) else QColor(TEXTO)
        r = QRectF(opt.rect).adjusted(8, 0, -MARGEN_MONTO, 0)
        fm, fmc = QFontMetrics(f), QFontMetrics(fc)
        base = r.center().y() + (fm.ascent() - fm.descent()) / 2   # la misma línea de base para el número y la moneda
        abajo = index.data(ROL_SEGUNDA) or ''   # 2.8: el cupón con que se compró, debajo, chico y en violeta
        f2 = fuente(11, QFont.Weight.Medium)
        fm2 = QFontMetrics(f2)
        if abajo:
            base -= (fm2.height() + 1) / 2
        x = r.right()
        painter.save()
        if codigo:
            x -= fmc.horizontalAdvance(codigo)
            painter.setFont(fc)
            painter.setPen(QColor(TEXTO_TENUE))
            painter.drawText(QPointF(x, base), codigo)
            x -= 4
        numero = fm.elidedText(numero, Qt.TextElideMode.ElideLeft, int(max(0.0, x - r.left())))
        painter.setFont(f)
        painter.setPen(color)
        painter.drawText(QPointF(x - fm.horizontalAdvance(numero), base), numero)
        if abajo:
            texto = fm2.elidedText(abajo, Qt.TextElideMode.ElideRight, int(r.width()))
            painter.setFont(f2)
            painter.setPen(QColor(TEXTO_TENUE if color == QColor(TEXTO_TENUE) else VIOLETA_CLARO))
            painter.drawText(QPointF(r.right() - fm2.horizontalAdvance(texto), base + fm.descent() + 1 + fm2.ascent()), texto)
        painter.restore()


# ---------------------------------------------------------------- Piezas nuevas: gráficas, bloques

ROL_SEGUNDA = Qt.ItemDataRole.UserRole + 3    # segunda línea de la celda (el correo debajo del nombre)


class DelegadoDosLineas(DelegadoFila):
    """Celda de dos líneas: el nombre arriba y el correo (u otro dato) abajo, más tenue. Así cabe todo en una ventana
    angosta sin una columna aparte para el correo."""

    def paint(self, painter, option, index):
        self.fondo_encima(painter, option, index)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        arriba, abajo = opt.text, index.data(ROL_SEGUNDA) or ''
        opt.text = ''
        estilo = opt.widget.style() if opt.widget else QApplication.style()
        estilo.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        painter.save()
        r = QRectF(opt.rect).adjusted(9, 0, -8, 0)
        propia = index.data(Qt.ItemDataRole.FontRole)   # (la columna «Desde» usa la letra de las fechas)
        f1, f2 = propia if isinstance(propia, QFont) else fuente(13, QFont.Weight.Medium), fuente(12)
        fm1, fm2 = QFontMetrics(f1), QFontMetrics(f2)
        alto = fm1.height() + (fm2.height() + 1 if abajo else 0)
        y = r.center().y() - alto / 2
        color = index.data(Qt.ItemDataRole.ForegroundRole)
        painter.setFont(f1)
        painter.setPen(color if isinstance(color, QColor) else QColor(TEXTO))
        alinear = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        painter.drawText(QRectF(r.left(), y, r.width(), fm1.height()), alinear,
                         fm1.elidedText(arriba, Qt.TextElideMode.ElideRight, int(r.width())))
        if abajo:
            painter.setFont(f2)
            painter.setPen(QColor(TEXTO_TENUE))
            painter.drawText(QRectF(r.left(), y + fm1.height() + 1, r.width(), fm2.height()), alinear,
                             fm2.elidedText(abajo, Qt.TextElideMode.ElideRight, int(r.width())))
        painter.restore()


class Pastilla(QLabel):
    """Pastilla de color con texto («5.54», «Al día»), para los paneles (en las tablas la dibuja DelegadoInsignia)."""

    def __init__(self, texto='', color=TEXTO_SUAVE):
        super().__init__()
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.poner(texto, color)

    def poner(self, texto, color):
        c = QColor(color)
        rgb = f'{c.red()}, {c.green()}, {c.blue()}'
        self.setText(texto)
        self.setStyleSheet(f'QLabel {{ color: {c.name()}; background: rgba({rgb}, {PASTILLA_FONDO}); '
                           f'border: 1px solid rgba({rgb}, {PASTILLA_BORDE}); border-radius: 9px; padding: 1px 8px; '
                           'font-size: 11px; font-weight: 600; }')
        self.setVisible(bool(texto))


def punto(color, tam=8):
    """Puntito de color (leyendas)."""
    pm = QPixmap(tam * 3, tam * 3)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(0, 0, tam * 3, tam * 3))
    p.end()
    pm.setDevicePixelRatio(3)
    return pm


def boton_cuadrado(nombre_icono, ayuda, tam=28):
    """Botón cuadrado chico solo con un ícono (− y + del límite de equipos, copiar...)."""
    b = QPushButton()
    b.setProperty('cuadrado', True)
    b.setIcon(icono(nombre_icono, TEXTO, 14))
    b.setIconSize(QSize(14, 14))
    b.setFixedSize(tam, tam)
    b.setToolTip(ayuda)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


# ---------------------------------------------------------------- El menú: la isla de arriba (2.7)
# 2.7 (propuesta A «isla arriba», expandida, elegida por el dueño): se fue la barra lateral de 244 px. El menú es una
# cápsula flotante arriba al centro, como la isla de CineCaptions (isla_ui.py): las 6 páginas siempre con su nombre y su
# contador, la pastilla violeta de la elegida que SE DESLIZA con un resorte y Configuración a la derecha. El «vidrio» es
# un degradado opaco y las sombras van en capas: sin desenfoque real ni efectos de Qt (rendimiento).

class Resorte:
    """Un número que va a su objetivo como un resorte (k: rigidez; c: amortiguación), con las parejas de isla_ui.py de
    CineCaptions: rebota natural y se le puede cambiar el objetivo a medio camino sin saltos."""
    __slots__ = ('x', 'v', 'objetivo', 'k', 'c')

    def __init__(self, x=0.0, k=170.0, c=22.0):
        self.x = self.objetivo = float(x)
        self.v = 0.0
        self.k, self.c = float(k), float(c)

    def paso(self, dt):
        """Avanza dt segundos (en trozos de 8 ms: estable con k altos). True si todavía se mueve; al asentarse queda
        justo en el objetivo (así las pruebas comparan el sitio exacto)."""
        while dt > 1e-6:
            h = min(0.008, dt)
            dt -= h
            self.v += (self.k * (self.objetivo - self.x) - self.c * self.v) * h
            self.x += self.v * h
        if abs(self.objetivo - self.x) < 0.01 and abs(self.v) < 0.05:
            self.x, self.v = self.objetivo, 0.0
            return False
        return True

    def poner(self, valor):
        self.x = self.objetivo = float(valor)
        self.v = 0.0


def de_0_a_1(x):
    return min(1.0, max(0.0, x))


def mezclar_color(a, b, t):
    """El color que está a t (de 0 a 1) del camino de a a b (el nombre de la isla se aclara al pasar el mouse)."""
    ca, cb, t = QColor(a), QColor(b), de_0_a_1(t)
    return QColor(round(ca.red() + (cb.red() - ca.red()) * t), round(ca.green() + (cb.green() - ca.green()) * t),
                  round(ca.blue() + (cb.blue() - ca.blue()) * t))


# Los cuantiles de una normal (Φ⁻¹ de 0,05, 0,15 … 0,95): dónde van las capas de sombra_en_capas
CUANTILES_SOMBRA = (1.645, 1.036, 0.674, 0.385, 0.126, -0.126, -0.385, -0.674, -1.036, -1.645)


def sombra_en_capas(p, caja, radio, desenfoque, alfa, color='#000000'):
    """Sombra difuminada sin efectos de Qt: la misma forma, agrandada y achicada en 10 capas tenues (en los cuantiles de
    una normal), que juntas se ven como un box-shadow del CSS con ese desenfoque y esa opacidad."""
    sigma = desenfoque / 2
    c = QColor(color)
    c.setAlpha(round(255 * (1 - (1 - alfa) ** (1 / len(CUANTILES_SOMBRA)))))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    for z in CUANTILES_SOMBRA:
        e = sigma * z
        r = caja.adjusted(-e, -e, e, e)
        if r.width() > 0 and r.height() > 0:
            p.drawRoundedRect(r, max(0.0, radio + e), max(0.0, radio + e))


# El globito del contador sobre el ícono (página cerrada, en una ventana angosta): (fondo, número) según su color
GLOBOS = {AVISO: (AVISO, '#1a1208'), PELIGRO: (ROJO, '#ffffff')}
GLOBO_NEUTRO = ('#34323f', '#d9d6e0')


class BotonIsla(QAbstractButton):
    """Un ítem de la isla: una página (ícono, nombre y contador), Configuración (solo el ícono, que gira un poco al pasar
    el mouse) o el logo. Lo DIBUJA la isla (pintar), encima de su pastilla: así el globito del contador puede salirse del
    ítem como en la propuesta. El botón da el clic, el foco con Tab, el nombre accesible y el contador, como el BotonNav
    de la barra de antes (poner_contador, contador, color_contador). Cerrado (ventana angosta), el contador va en un
    globito sobre el ícono."""
    ALTO = 36

    def __init__(self, isla, nombre_icono, texto, tipo='pagina'):
        super().__init__(isla)
        self.isla, self.texto, self.tipo = isla, texto, tipo
        self.contador, self.color_contador = None, None
        self.abierto = tipo == 'pagina'               # con el nombre a la vista (lo decide la isla)
        # (los resortes de isla_ui.py: mouse k=420 c=26, clic k=620 c=19 y etiqueta k=300 c=24)
        self.hover = Resorte(0.0, 420.0, 26.0)
        self.press = Resorte(0.0, 620.0, 19.0)
        self.ancho = Resorte(40.0, 300.0, 24.0)
        self.alfa = Resorte(1.0 if self.abierto else 0.0, 300.0, 24.0)   # la opacidad del nombre
        if tipo == 'logo':
            self._logo = pixmap_logo(28)
        else:
            self._pixmaps = {c: pintar_icono(nombre_icono, c, 18) for c in (TEXTO, TEXTO_SUAVE)}
        self._f_normal, self._f_elegida = fuente(13, QFont.Weight.Medium), fuente(13, QFont.Weight.DemiBold)
        self._f_contador = con_cifras_tabulares(fuente(11, QFont.Weight.Bold))
        self._f_globo = con_cifras_tabulares(fuente(10, QFont.Weight.Bold))
        self.setCheckable(tipo == 'pagina')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus if tipo == 'logo' else Qt.FocusPolicy.TabFocus)
        self.setAccessibleName(texto)
        self.resize(40, self.ALTO)

    def poner_contador(self, n, color=None):
        if (n, color) != (self.contador, self.color_contador):
            self.contador, self.color_contador = n, color
            self.isla.acomodar()   # (el contador cambia el ancho del ítem: la isla se reacomoda con su resorte)

    def ancho_abierto(self):
        """El ancho con el nombre a la vista: ícono (36) + nombre + contador + 10 de aire, como en la propuesta."""
        if self.tipo != 'pagina':
            return 40.0
        ancho = 36 + QFontMetrics(self._fuente()).horizontalAdvance(self.texto) + 10
        if self.contador:
            ancho += 7 + self._ancho_contador()
        return float(ancho)

    def _fuente(self):
        return self._f_elegida if self.isChecked() else self._f_normal

    def _ancho_contador(self):
        return max(22, QFontMetrics(self._f_contador).horizontalAdvance(f'{self.contador:,}') + 14)

    # (la isla lleva el reloj de todos los resortes: aquí solo se cambia el objetivo)
    def enterEvent(self, evento):
        self.hover.objetivo = 1.0
        self.isla.animar()
        super().enterEvent(evento)

    def leaveEvent(self, evento):
        self.hover.objetivo = 0.0
        self.isla.animar()
        super().leaveEvent(evento)

    def mousePressEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton:
            self.press.objetivo = 1.0
            self.isla.animar()
        super().mousePressEvent(evento)

    def mouseReleaseEvent(self, evento):
        self.press.objetivo = 0.0
        self.isla.animar()
        super().mouseReleaseEvent(evento)

    def focusInEvent(self, evento):
        super().focusInEvent(evento)
        self.isla.update()

    def focusOutEvent(self, evento):
        super().focusOutEvent(evento)
        self.isla.update()

    def paintEvent(self, _evento):
        pass   # (lo dibuja la isla: ver pintar)

    def pintar(self, p):
        """Dibuja el ítem con el pintor de la isla, ya movido a donde está el ítem."""
        r = QRectF(0, 0, self.width(), self.height())
        radio = r.height() / 2
        h, apretado = de_0_a_1(self.hover.x), de_0_a_1(self.press.x)
        if self.tipo == 'logo':   # (el logo solo crece un poco al pasar el mouse)
            esc = (1 + 0.08 * h) * (1 - 0.2 * apretado)
            p.save()
            p.translate(r.center())
            p.scale(esc, esc)
            p.drawPixmap(QRectF(-14, -14, 28, 28), self._logo, QRectF(self._logo.rect()))
            p.restore()
            return
        activo = self.isChecked()
        claro = 1.0 if activo else h
        if h > 0.005 and not activo:   # el realce suave al pasar el mouse (la elegida ya tiene su pastilla)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, round(18 * h)))
            p.drawRoundedRect(r, radio, radio)
        if self.hasFocus():   # (solo con Tab: el clic no le da el foco)
            p.setPen(QPen(QColor(VIOLETA), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), radio - 1, radio - 1)
        # El ícono: crece un 12 % al pasar el mouse y baja a ~0,9 al apretar; el de Configuración además gira
        p.save()
        p.translate(20, r.height() / 2)
        if self.tipo == 'accion':
            p.rotate(70 * h)
        esc = (1 + 0.12 * h) * (1 - 0.2 * apretado)
        p.scale(esc, esc)
        for color, opacidad in ((TEXTO_SUAVE, 1 - claro), (TEXTO, claro)):   # (de gris a blanco, sin salto)
            if opacidad > 0.005:
                p.setOpacity(opacidad)
                p.drawPixmap(QPointF(-9, -9), self._pixmaps[color])
        p.restore()
        if self.tipo != 'pagina':
            return
        # El nombre y el contador, recortados al ítem mientras se abre o se cierra (como el «recorte» de la propuesta)
        a = de_0_a_1(self.alfa.x)
        if a > 0.01:
            p.save()
            camino = QPainterPath()
            camino.addRoundedRect(r, radio, radio)
            p.setClipPath(camino)
            p.setOpacity(a)
            f = self._fuente()
            fm = QFontMetrics(f)
            p.setFont(f)
            p.setPen(mezclar_color(TEXTO_SUAVE, TEXTO, claro))
            ancho_texto = fm.horizontalAdvance(self.texto)
            p.drawText(QRectF(36, 0, ancho_texto + 4, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       self.texto)
            if self.contador:   # (un cero no lleva contador: «Canjes de Gumroad» sin canjes queda limpio)
                caja = QRectF(36 + ancho_texto + 7, (r.height() - 20) / 2, self._ancho_contador(), 20)
                color = QColor(self.color_contador or TEXTO_SUAVE)
                fondo = QColor(color)
                fondo.setAlpha(34 if self.color_contador else 20)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(fondo)
                p.drawRoundedRect(caja, 10, 10)
                p.setFont(self._f_contador)
                p.setPen(color)
                p.drawText(caja, Qt.AlignmentFlag.AlignCenter, f'{self.contador:,}')
            p.restore()
        # Cerrado: el contador en un globito sobre el ícono (rojo lleno en Errores, naranja en Versiones)
        g = 1 - a
        if self.contador and g > 0.01:
            texto = '99+' if self.contador > 99 else str(self.contador)
            fondo, tinta = GLOBOS.get(self.color_contador, GLOBO_NEUTRO)
            caja = QRectF(22, 1, max(16, QFontMetrics(self._f_globo).horizontalAdvance(texto) + 8), 15)
            p.save()
            p.setOpacity(g)
            p.translate(caja.center())
            p.scale(0.5 + 0.5 * g, 0.5 + 0.5 * g)
            p.translate(-caja.center())
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#17161f'))   # (el aro del color de la isla: separa el globito del ícono)
            p.drawRoundedRect(caja.adjusted(-2, -2, 2, 2), 9.5, 9.5)
            p.setBrush(QColor(fondo))
            p.drawRoundedRect(caja, 7.5, 7.5)
            p.setFont(self._f_globo)
            p.setPen(QColor(tinta))
            p.drawText(caja, Qt.AlignmentFlag.AlignCenter, texto)
            p.restore()


class SombraIsla(QWidget):
    """La sombra de la isla, en su propio widget que no recibe el mouse: así pasa por encima del encabezado sin taparle
    los clics («Exportar CSV» queda cerca). La isla mide justo su cápsula."""
    MARGEN = 48   # hasta dónde llega la sombra grande (34 de desenfoque y 14 hacia abajo)

    def __init__(self, padre, isla):
        super().__init__(padre)
        self.isla = isla
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def seguir(self):
        g = self.isla.geometry().adjusted(-self.MARGEN, -self.MARGEN, self.MARGEN, self.MARGEN)
        if g != self.geometry():   # (solo si la isla se movió o cambió de ancho: el mouse sobre un ítem no la repinta)
            self.setGeometry(g)

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        caja = QRectF(self.MARGEN, self.MARGEN, self.isla.width(), self.isla.height())
        radio = caja.height() / 2
        # las de la propuesta: 0 14px 34px al 55 %, 0 4px 10px al 45 % y un aro oscuro de 1 px al 35 %
        sombra_en_capas(p, caja.translated(0, 14), radio, 34, 0.55)
        sombra_en_capas(p, caja.translated(0, 4), radio, 10, 0.45)
        p.setBrush(QColor(0, 0, 0, 89))
        p.drawRoundedRect(caja.adjusted(-1, -1, 1, 1), radio + 1, radio + 1)


class RaizVentana(QWidget):
    """La raíz de la ventana: avisa cuando cambia de tamaño, para que la isla se recentre y vea cuántos nombres caben.
    Con resizeEvent y no con un eventFilter: un filtro en Python corre también con cada evento al cerrar el programa (y
    al salir, Python ya no está para atenderlo)."""
    redimensionada = Signal()

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)   # (una subclase no pinta sola el fondo del QSS)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.redimensionada.emit()


class IslaNav(QWidget):
    """El menú (2.7): la cápsula flotante arriba al centro, hija de la raíz y encima del contenido. Lleva el logo, las
    páginas, un separador y Configuración. Mantiene lo que usaba la barra lateral de antes: botones[clave] (con
    poner_contador), btn_config, marcar() y la señal elegida. reservas() dice cuánto no puede tapar a la izquierda y a la
    derecha (el encabezado de la página): si no cabe con todos los nombres, primero se cierran los de las páginas no
    elegidas (quedan el ícono y el contador en un globito) y, si ni así, también el de la elegida. Nunca se sale."""
    elegida = Signal(str)
    # Las medidas de la propuesta A (px): a 8 del borde de arriba, 44 de alto, ítems de 36, 4 de aire a los lados, 2
    # entre ítem e ítem y separadores de 11
    ARRIBA, ALTO, H_ITEM, PADDING, HUECO, SEP = 8, 44, 36, 4, 2, 11
    NIVELES = ('expandida', 'compacta', 'iconos')

    def __init__(self, padre, paginas, reservas=None):
        super().__init__(padre)
        self.reservas = reservas or (lambda: (0, 0))
        self.actual = None
        self.nivel = 'expandida'
        self._sombra = SombraIsla(padre, self)
        self._sombra.stackUnder(self)
        self.logo = BotonIsla(self, None, APP, 'logo')
        self.logo.clicked.connect(lambda: self.elegida.emit(paginas[0][0]))   # (el logo lleva al Resumen)
        self.botones = {}
        grupo = QButtonGroup(self)
        grupo.setExclusive(True)
        for clave, nombre_icono, texto in paginas:
            b = BotonIsla(self, nombre_icono, texto)
            b.clicked.connect(lambda _c=False, k=clave: self.elegida.emit(k))
            grupo.addButton(b)
            self.botones[clave] = b
        self.btn_config = BotonIsla(self, 'ajustes', 'Configuración', 'accion')
        self._orden = [self.logo, None, *self.botones.values(), None, self.btn_config]   # (None: un separador)
        self._seps = []
        self._pastilla = (Resorte(0.0, 340.0, 26.0), Resorte(0.0, 340.0, 26.0))   # x y ancho (k=340, c=26)
        self._entrada = Resorte(1.0, 90.0, 13.0)   # de 0 a 1: la isla baja desde arriba la primera vez que se ve
        self._entro = False
        self._brillo = None                         # ((ancho, dpr), imagen): el brillo de abajo se hace una vez por ancho
        self._reloj = QTimer(self)                  # UN reloj para todos los resortes; se apaga cuando nada se mueve
        self._reloj.setTimerType(Qt.TimerType.PreciseTimer)   # (el normal de Windows salta de a ~15,6 ms)
        self._reloj.setInterval(16)
        self._reloj.timeout.connect(self._tic)
        self._ultimo = 0.0
        if hasattr(padre, 'redimensionada'):   # (la ventana cambia de tamaño: se recentra y ve cuántos nombres caben)
            padre.redimensionada.connect(self.acomodar)
        self.acomodar(al_instante=True)

    # --- Lo que usa la ventana (lo mismo que la barra lateral de antes)
    def marcar(self, clave):
        b = self.botones.get(clave)
        if b is None:
            return
        if not b.isChecked():
            b.setChecked(True)
        self.actual = clave
        self.acomodar()

    def levantar(self):
        """Encima de todo el contenido (con su sombra justo debajo)."""
        self._sombra.raise_()
        self.raise_()

    def moviendose(self):
        """¿Todavía se mueve algo? (las capturas esperan a que se asiente)"""
        return self._reloj.isActive()

    def rect_pastilla(self):
        """Dónde está la pastilla ahora (en coordenadas de la isla)."""
        return QRectF(self._pastilla[0].x, (self.ALTO - self.H_ITEM) / 2, self._pastilla[1].x, self.H_ITEM)

    # --- Geometría
    def _todos(self):
        return [self.logo, *self.botones.values(), self.btn_config]

    def _abierto(self, clave, nivel):
        return nivel == 'expandida' or (nivel == 'compacta' and clave == self.actual)

    def _ancho_total(self, nivel):
        """Lo que mediría la isla ya asentada con ese nivel."""
        anchos = [self.SEP if it is None else (it.ancho_abierto() if it.tipo == 'pagina' and self._abierto(clave, nivel)
                                               else 40.0)
                  for clave, it in zip([None, None, *self.botones, None, None], self._orden)]
        return 2 * self.PADDING + sum(anchos) + self.HUECO * (len(anchos) - 1)

    def acomodar(self, al_instante=False):
        """Decide cuántos nombres caben, pone el ancho final de cada ítem y lleva la pastilla al sitio FINAL de la página
        elegida (cada ancho llega con su propio resorte, como en la propuesta). Sin la ventana a la vista, todo queda en
        su sitio al instante."""
        izquierda, derecha = self.reservas()
        libre = self.parentWidget().width() - 2 * max(izquierda, derecha)   # (va centrada: manda el lado más ocupado)
        nivel = next((n for n in self.NIVELES if self._ancho_total(n) <= libre), self.NIVELES[-1])
        self.nivel = nivel
        for clave, b in self.botones.items():
            b.abierto = self._abierto(clave, nivel)
            b.ancho.objetivo = b.ancho_abierto() if b.abierto else 40.0
            b.alfa.objetivo = 1.0 if b.abierto else 0.0
            b.setToolTip('' if b.abierto else b.texto)   # (cerrada, como la barra angosta de antes: el nombre encima)
        x = float(self.PADDING)
        elegido = self.botones.get(self.actual)
        for it in self._orden:
            ancho = self.SEP if it is None else it.ancho.objetivo
            if it is not None and it is elegido:
                self._pastilla[0].objetivo, self._pastilla[1].objetivo = x, ancho
            x += ancho + self.HUECO
        quieta = al_instante or not self.isVisible()
        if quieta:
            for b in self._todos():
                b.ancho.poner(b.ancho.objetivo)
                b.alfa.poner(b.alfa.objetivo)
        if quieta or self._pastilla[1].x < 4:   # (la primera vez aparece ya en su sitio, sin venir desde la izquierda)
            for r in self._pastilla:
                r.poner(r.objetivo)
        self._colocar()
        self.animar()

    def _colocar(self):
        """Pone cada ítem según su resorte y la isla centrada arriba (se recentra sola mientras cambia de ancho)."""
        x = float(self.PADDING)
        self._seps = []
        arriba = (self.ALTO - self.H_ITEM) // 2
        for it in self._orden:
            if it is None:
                self._seps.append(x)
                x += self.SEP + self.HUECO
                continue
            izquierda, ancho = round(x), max(0.0, it.ancho.x)
            it.setGeometry(izquierda, arriba, max(1, round(x + ancho) - izquierda), self.H_ITEM)
            x += ancho + self.HUECO
        total = round(x - self.HUECO + self.PADDING)
        padre = self.parentWidget()
        geometria = (max(0, round((padre.width() - total) / 2)), round(self.ARRIBA - 70 * (1 - self._entrada.x)),
                     total, self.ALTO)
        if (self.x(), self.y(), self.width(), self.height()) != geometria:
            self.setGeometry(*geometria)
        self._sombra.seguir()

    # --- Animación: resortes integrados con un QTimer de ~60 fps que se apaga al asentarse
    def animar(self):
        if not self._reloj.isActive():
            self._ultimo = time.perf_counter()
            self._reloj.start()

    def _tic(self):
        ahora = time.perf_counter()
        dt, self._ultimo = min(0.05, ahora - self._ultimo), ahora
        sigue = self._entrada.paso(dt)
        for r in self._pastilla:
            sigue = r.paso(dt) or sigue
        for b in self._todos():
            for r in (b.hover, b.press, b.ancho, b.alfa):
                sigue = r.paso(dt) or sigue
        self._colocar()
        self.update()
        if not sigue:
            self._reloj.stop()

    def showEvent(self, evento):
        super().showEvent(evento)
        if not self._entro:   # la primera vez que se ve, baja desde arriba (k=90, c=13, como en CineCaptions)
            self._entro = True
            self._entrada.poner(0.0)
            self._entrada.objetivo = 1.0
            self._colocar()   # (ya arriba, fuera de la vista: sin un cuadro en su sitio final antes de bajar)
            self.animar()

    # --- Pintura
    def _imagen_brillo(self):
        """El brillo de la marca abajo de la cápsula (rojo → rosa → violeta, que se apaga hacia arriba). Se arma una
        vez por ancho en una QImage con DestinationIn (sin efectos de Qt)."""
        dpr = self.devicePixelRatioF()
        clave = (self.width(), dpr)
        if self._brillo is None or self._brillo[0] != clave:
            w, h = self.width(), self.height()
            imagen = QImage(max(1, round(w * dpr)), max(1, round(h * dpr)), QImage.Format.Format_ARGB32_Premultiplied)
            imagen.setDevicePixelRatio(dpr)
            imagen.fill(Qt.GlobalColor.transparent)
            q = QPainter(imagen)
            g = QLinearGradient(0, 0, w, 0)
            g.setColorAt(0.0, QColor(239, 68, 68, 51))
            g.setColorAt(0.5, QColor(224, 36, 110, 46))
            g.setColorAt(1.0, QColor(124, 77, 255, 61))
            q.fillRect(QRectF(0, 0, w, h), g)
            q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            m = QLinearGradient(0, h, 0, h * 0.28)   # (lleno abajo y nada al 72 % de la altura)
            m.setColorAt(0.0, QColor(0, 0, 0, 255))
            m.setColorAt(1.0, QColor(0, 0, 0, 0))
            q.fillRect(QRectF(0, 0, w, h), m)
            q.end()
            self._brillo = (clave, imagen)
        return self._brillo[1]

    def _pintar_pastilla(self, p):
        pa = self.rect_pastilla()
        r = pa.height() / 2
        sombra_en_capas(p, pa, r, 16, 0.26, VIOLETA)   # el halo violeta (0 0 16px)
        p.setBrush(QColor(124, 77, 255, 26))             # y su aro de 3 px
        p.drawRoundedRect(pa.adjusted(-3, -3, 3, 3), r + 3, r + 3)
        g = QLinearGradient(0, pa.top(), 0, pa.bottom())
        g.setColorAt(0.0, QColor('#352a60'))
        g.setColorAt(1.0, QColor('#261d46'))
        p.setPen(QPen(QColor(ELEGIDA_BORDE), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(pa.adjusted(0.5, 0.5, -0.5, -0.5), r - 0.5, r - 0.5)
        raya = QRectF(pa.left() + 18, pa.bottom() - 4, max(0.0, pa.width() - 36), 2)   # la raya de la marca, debajo
        m = QLinearGradient(raya.left(), 0, raya.right(), 0)
        m.setColorAt(0.0, QColor(ROJO))
        m.setColorAt(0.6, QColor(ROSA))
        m.setColorAt(1.0, QColor(VIOLETA))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(m))
        p.drawRoundedRect(raya, 1, 1)

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        caja = QRectF(self.rect())
        radio = caja.height() / 2
        camino = QPainterPath()
        camino.addRoundedRect(caja, radio, radio)
        # El «vidrio»: un degradado opaco (falso a propósito, como en CineCaptions) con el brillo de la marca abajo
        g = QLinearGradient(0, 0, 0, caja.height())
        g.setColorAt(0.0, QColor('#1e1c29'))
        g.setColorAt(1.0, QColor('#100f17'))
        p.fillPath(camino, QBrush(g))
        p.save()
        p.setClipPath(camino)
        p.drawImage(QPointF(0, 0), self._imagen_brillo())
        p.restore()
        if self.actual is not None and self._pastilla[1].x > 4:   # la pastilla de la elegida (se desliza)
            self._pintar_pastilla(p)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 31))
        for x in self._seps:
            p.drawRect(QRectF(x + 5, (self.ALTO - 22) / 2, 1, 22))
        for b in self._todos():
            p.save()
            p.translate(QPointF(b.pos()))
            b.pintar(p)
            p.restore()
        # Encima de todo, como en la propuesta: el borde de 1 px y la línea de luz de arriba
        p.setOpacity(1)
        p.setPen(QPen(QColor(255, 255, 255, 23), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(caja.adjusted(0.5, 0.5, -0.5, -0.5), radio - 0.5, radio - 0.5)
        luz = QLinearGradient(radio, 0, caja.width() - radio, 0)
        luz.setColorAt(0.0, QColor(255, 255, 255, 0))
        luz.setColorAt(0.5, QColor(255, 255, 255, 77))
        luz.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(radio, 0, caja.width() - 2 * radio, 1), QBrush(luz))


class Segmentos(QFrame):
    """Botones pegados para elegir una sola opción («Hoy · 7 días · 30 días · Todo»). Cada uno puede llevar un número."""
    cambiado = Signal(object)

    def __init__(self, opciones, actual=None):
        super().__init__()
        self.setObjectName('segmentos')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        grupo = QButtonGroup(self)
        grupo.setExclusive(True)
        self.botones, self._textos = {}, {}
        for texto, valor in opciones:
            b = QPushButton(texto)
            b.setProperty('segmento', True)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, v=valor: self._elegir(v))
            grupo.addButton(b)
            self.botones[valor] = b
            self._textos[valor] = texto
            lay.addWidget(b)
        self.valor = actual if actual in self.botones else opciones[0][1]
        self.botones[self.valor].setChecked(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _elegir(self, valor):
        if valor != self.valor:
            self.valor = valor
            self.cambiado.emit(valor)

    def poner(self, valor):
        """Elige una opción desde el código (y avisa con «cambiado», como un clic)."""
        if valor in self.botones:
            self.botones[valor].setChecked(True)
            self._elegir(valor)

    def contar(self, valor, n):
        if valor in self.botones:
            self.botones[valor].setText(self._textos[valor] if n is None else f'{self._textos[valor]}  {n:,}')


# ---------------------------------------------------------------- Gráficas (QPainter)

def escala_bonita(maximo, pasos=4):
    """Un paso «redondo» (1, 2, 2.5 o 5 por una potencia de 10) para que unos 4 pasos cubran el máximo."""
    if maximo <= 0:
        return 1
    crudo = maximo / pasos
    potencia = 10 ** math.floor(math.log10(crudo))
    for m in (1, 2, 2.5, 5, 10):
        if m * potencia >= crudo:
            return max(1, m * potencia)
    return max(1, 10 * potencia)


def monto_eje(unidades, moneda):
    """Monto corto para el eje de la gráfica: «$50», «$1,500», «$12k»."""
    simbolo = SIMBOLOS.get(moneda, '')
    if unidades >= 10000:
        return f'{simbolo}{unidades / 1000:g}k'
    return f'{simbolo}{unidades:,.0f}' if float(unidades).is_integer() else f'{simbolo}{unidades:,.2f}'


class GraficaVentas(QWidget):
    """Los ingresos de cada día en barras. Al pasar el mouse, la barra se ilumina y sale un globito con el monto, las
    ventas y los reembolsos de ese día. Un puntito naranja debajo marca los días con reembolsos. Con pocos días con
    ventas (POCAS o menos) cada barra lleva su monto arriba y la escala deja aire para ese número; sin ventas en el
    período, la escala queda tenue y lo dice en el centro. Mientras carga se ven las líneas de la escala (no salta)."""
    POCAS = 6

    def __init__(self):
        super().__init__()
        self.dias, self.moneda, self.mensaje = [], 'USD', 'Cargando…'
        self._encima = None
        self.setMouseTracking(True)
        self.setMinimumHeight(210)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def poner(self, dias, moneda='USD'):
        self.dias, self.moneda, self.mensaje, self._encima = list(dias), moneda or 'USD', '', None
        self.update()

    def vaciar(self, mensaje):
        self.dias, self.mensaje, self._encima = [], mensaje, None
        self.update()

    def _area(self):
        return QRectF(54, 16, max(10.0, self.width() - 54 - 6), max(10.0, self.height() - 16 - 30))

    def _indice(self, x):
        area = self._area()
        if not self.dias or not area.left() <= x <= area.right():
            return None
        i = int((x - area.left()) // (area.width() / len(self.dias)))
        return i if 0 <= i < len(self.dias) else None

    def mouseMoveEvent(self, evento):
        i = self._indice(evento.position().x())
        if i != self._encima:
            self._encima = i
            self.update()

    def leaveEvent(self, evento):
        self._encima = None
        self.update()
        super().leaveEvent(evento)

    def con_ventas(self):
        """Cuántos días del período tienen ingresos."""
        return sum(1 for d in self.dias if d['ingresos'] > 0)

    def _rejilla(self, p, area, pasos=4):
        """Las líneas tenues de la escala (sin los montos)."""
        for k in range(pasos + 1):
            y = area.bottom() - area.height() * k / pasos
            p.setPen(QPen(QColor(BORDE_FUERTE if k == 0 else '#1e1d27'), 1))
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))

    def _letrero(self, p, area, texto):
        """Un mensaje en una cajita en el centro de la gráfica (tapa las líneas que pasan detrás)."""
        f = fuente(13)
        fm = QFontMetrics(f)
        ancho = max(72.0, min(area.width() - 24, fm.horizontalAdvance(texto) + 32.0))
        caja = fm.boundingRect(QRectF(0, 0, ancho - 32, 400).toRect(),
                               int(Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap), texto)
        alto = caja.height() + 20
        r = QRectF(area.center().x() - ancho / 2, area.top() + (area.height() - alto) * 0.45, ancho, alto)
        p.setPen(QPen(QColor(BORDE), 1))
        p.setBrush(QColor(SUPERFICIE))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), RADIO_CONTROL, RADIO_CONTROL)
        p.setFont(f)
        p.setPen(QColor(TEXTO_TENUE))
        p.drawText(r.adjusted(16, 0, -16, 0), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, texto)

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        if not self.dias:   # cargando o sin datos: la escala tenue y el mensaje
            area = self._area()
            self._rejilla(p, area)
            if self.mensaje:
                self._letrero(p, area, self.mensaje)
            return
        area, ranura, paso, pasos = self._escala()
        tope = paso * pasos
        vacia = not self.con_ventas()
        etiquetas = 0 < self.con_ventas() <= self.POCAS
        f = fuente(11, cifras=True)
        fm = QFontMetrics(f)
        p.setFont(f)
        self._rejilla(p, area, pasos)
        for k in range(pasos + 1):   # el monto de cada línea a la izquierda (sin ventas, solo el $0)
            if vacia and k:
                continue
            y = area.bottom() - area.height() * k / pasos
            p.setPen(QColor(TEXTO_TENUE))
            p.drawText(QRectF(0, y - 9, area.left() - 10, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       monto_eje(k * paso, self.moneda))
        ancho = max(3.0, min(24.0, ranura * 0.62))
        if self._encima is not None:
            p.fillRect(QRectF(area.left() + ranura * self._encima, area.top(), ranura, area.height()), QColor(255, 255, 255, 8))
        degradado = QLinearGradient(0, area.top(), 0, area.bottom())
        degradado.setColorAt(0.0, QColor('#f0407f'))
        degradado.setColorAt(1.0, QColor(VIOLETA))
        fe = fuente(11, QFont.Weight.DemiBold, cifras=True)
        for i, d in enumerate(self.dias):
            x = area.left() + ranura * i + (ranura - ancho) / 2
            alto = area.height() * (d['ingresos'] / 100) / tope
            if d['ingresos'] > 0:
                alto = max(alto, 3.0)
                radio = min(4.0, ancho / 2, alto)
                arriba = area.bottom() - alto
                barra = QPainterPath(QPointF(x, area.bottom()))
                barra.lineTo(x, arriba + radio)
                barra.quadTo(x, arriba, x + radio, arriba)
                barra.lineTo(x + ancho - radio, arriba)
                barra.quadTo(x + ancho, arriba, x + ancho, arriba + radio)
                barra.lineTo(x + ancho, area.bottom())
                barra.closeSubpath()
                p.fillPath(barra, QBrush(QColor(VIOLETA_CLARO)) if i == self._encima else QBrush(degradado))
                if etiquetas and i != self._encima:   # (el globito ya dice el monto de la barra bajo el mouse)
                    texto = monto_eje(d['ingresos'] / 100, self.moneda)
                    w = QFontMetrics(fe).horizontalAdvance(texto) + 4
                    cx = min(max(x + ancho / 2, w / 2), self.width() - w / 2)
                    p.setFont(fe)
                    p.setPen(QColor(TEXTO_SUAVE))
                    p.drawText(QRectF(cx - w / 2, arriba - 20, w, 16), Qt.AlignmentFlag.AlignCenter, texto)
            else:   # día sin ventas: una rayita para que el día se vea
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(BORDE_FUERTE))
                p.drawRoundedRect(QRectF(x, area.bottom() - 2, ancho, 2), 1, 1)
            if d['reembolsos']:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(AVISO))
                p.drawEllipse(QPointF(x + ancho / 2, area.bottom() + 6), 2.4, 2.4)
        hoy = Reloj.ahora().date()
        p.setFont(f)
        p.setPen(QColor(TEXTO_TENUE))
        n = len(self.dias)
        for i, d in enumerate(self.dias):   # una fecha cada 7 días, contando desde hoy hacia atrás
            if (n - 1 - i) % 7:
                continue
            texto = 'Hoy' if d['fecha'] == hoy else f"{d['fecha'].day} {MESES[d['fecha'].month - 1]}"
            cx = area.left() + ranura * (i + 0.5)
            w = fm.horizontalAdvance(texto) + 4
            cx = min(max(cx, area.left() + w / 2), area.right() - w / 2)
            p.drawText(QRectF(cx - w / 2, area.bottom() + 11, w, 16), Qt.AlignmentFlag.AlignCenter, texto)
        if vacia:
            self._letrero(p, area, f'Sin ventas en los últimos {len(self.dias)} días.')
        if self._encima is not None:
            self._globo(p)

    def _escala(self):
        """(área de las barras, ancho de cada día, paso de la escala, cuántos pasos). Con pocos días con ventas, la
        escala sube un poco más que la barra más alta: así cabe el monto encima de ella."""
        area = self._area()
        maximo = max(d['ingresos'] for d in self.dias) / 100
        if 0 < self.con_ventas() <= self.POCAS:
            maximo *= 1.2
        paso = escala_bonita(maximo)
        pasos = max(2, math.ceil(maximo / paso)) if maximo > 0 else 4
        return area, area.width() / len(self.dias), paso, pasos

    def barra(self, i):
        """El rectángulo de la barra del día i (su alto mínimo es el de la rayita de los días sin ventas)."""
        area, ranura, paso, pasos = self._escala()
        ancho = max(3.0, min(24.0, ranura * 0.62))
        alto = max(2.0, area.height() * (self.dias[i]['ingresos'] / 100) / (paso * pasos))
        return QRectF(area.left() + ranura * i + (ranura - ancho) / 2, area.bottom() - alto, ancho, alto)

    def _lineas_globo(self):
        d = self.dias[self._encima]
        fecha = d['fecha']
        detalle = plural(d['ventas'], 'venta', 'ventas')
        if d['reembolsos']:
            detalle += ' · ' + plural(d['reembolsos'], 'reembolso', 'reembolsos')
        return [(f"{DIAS_SEMANA[fecha.weekday()]} {fecha.day} {MESES[fecha.month - 1]}", fuente(11, QFont.Weight.Medium),
                 TEXTO_TENUE),
                (dinero(d['ingresos'], self.moneda), fuente(14, QFont.Weight.DemiBold, cifras=True), TEXTO),
                (detalle, fuente(12), TEXTO_SUAVE)]

    def caja_globo(self):
        """Dónde va el globito del día que está bajo el mouse: arriba de su barra o, si la barra es alta, a un lado (a la
        derecha si cabe), para no taparla. None si el mouse no está sobre un día."""
        if self._encima is None or not self.dias:
            return None
        lineas = self._lineas_globo()
        ancho = max(QFontMetrics(f).horizontalAdvance(t) for t, f, _c in lineas) + 26
        alto = sum(QFontMetrics(f).height() for _t, f, _c in lineas) + 18
        barra = self.barra(self._encima)
        if barra.top() - alto - 10 >= 2:
            x, y = min(max(4.0, barra.center().x() - ancho / 2), self.width() - ancho - 4), barra.top() - alto - 10
        else:
            x = barra.right() + 10 if barra.right() + 10 + ancho <= self.width() - 4 else max(4.0, barra.left() - 10 - ancho)
            y = max(2.0, min(barra.top(), self._area().bottom() - alto))
        return QRectF(x, y, ancho, alto)

    def _globo(self, p):
        caja, lineas = self.caja_globo(), self._lineas_globo()
        p.setPen(Qt.PenStyle.NoPen)
        for i, alfa in enumerate((40, 22, 10)):   # una sombra suave, un poco hacia abajo
            crece = 1 + i * 2.5
            p.setBrush(QColor(0, 0, 0, alfa))
            p.drawRoundedRect(caja.adjusted(-crece, -crece + 2, crece, crece + 3), RADIO_CONTROL + crece, RADIO_CONTROL + crece)
        p.setPen(QPen(QColor(BORDE_FUERTE), 1))
        p.setBrush(QColor(SUPERFICIE_2))
        p.drawRoundedRect(caja.adjusted(0.5, 0.5, -0.5, -0.5), RADIO_CONTROL, RADIO_CONTROL)
        y = caja.top() + 9
        for texto, f, color in lineas:
            p.setFont(f)
            p.setPen(QColor(color))
            h = QFontMetrics(f).height()
            p.drawText(QRectF(caja.left() + 13, y, caja.width() - 26, h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, texto)
            y += h


class GraficaVersiones(QWidget):
    """Equipos por versión en barras horizontales: verde la última (o más nueva), naranja las viejas y gris «sin datos».
    Cuenta los equipos de licencias activas, como admin.php. centrar: con pocas filas en un lugar alto, las barras van
    al medio (no quedan pegadas arriba de una tarjeta vacía). alto_fila: más juntas (24) en la página Versiones."""
    ALTO_FILA = 32

    def __init__(self, centrar=False, alto_fila=None):
        super().__init__()
        self.filas, self.ultima, self.mensaje = [], None, 'Cargando…'
        self.centrar = centrar
        if alto_fila:
            self.ALTO_FILA = alto_fila
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def poner(self, por_version, ultima):
        juntas = {}
        for fila in por_version:   # «5.54» y «5.54.0» son la misma; todo lo que no se entiende va a «sin datos»
            texto = texto_version(fila['version'])
            juntas[texto] = juntas.get(texto, 0) + fila['equipos']
        con = sorted((v for v in juntas if v), key=partes_version, reverse=True)
        self.filas = [(v, juntas[v]) for v in con if juntas[v]] + ([(None, juntas[None])] if juntas.get(None) else [])
        self.ultima, self.mensaje = texto_version(ultima), '' if self.filas else 'Todavía no hay equipos con datos.'
        self.updateGeometry()
        self.update()

    def vaciar(self, mensaje):
        self.filas, self.mensaje = [], mensaje
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        return QSize(320, max(96, len(self.filas) * self.ALTO_FILA + 8))

    def minimumSizeHint(self):
        return QSize(200, max(96, len(self.filas) * self.ALTO_FILA + 8))

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        if not self.filas:
            pintar_vacio(p, QRectF(self.rect()), self.mensaje)
            return
        maximo = max(n for _v, n in self.filas) or 1
        f, fn = fuente(13, QFont.Weight.DemiBold), fuente(13, QFont.Weight.DemiBold, cifras=True)
        etiqueta_ancho, cifra_ancho = 96, 40
        izquierda, derecha = etiqueta_ancho, self.width() - cifra_ancho
        nueva = partes_version(self.ultima)
        alto_filas = len(self.filas) * self.ALTO_FILA + 8
        arriba = max(0.0, (self.height() - alto_filas) / 2) if self.centrar else 0.0
        for i, (version, n) in enumerate(self.filas):
            y = arriba + 4 + i * self.ALTO_FILA
            centro = y + self.ALTO_FILA / 2
            estado = estado_de_version(version, self.ultima)
            color = {'al_dia': EXITO, 'desactualizado': AVISO}.get(estado, TEXTO_TENUE if version is None else TEXTO_SUAVE)
            es_ultima = bool(version and nueva and partes_version(version) == nueva)
            p.setFont(f)
            p.setPen(QColor(TEXTO if version else TEXTO_SUAVE))
            p.drawText(QRectF(0, y, etiqueta_ancho - (50 if es_ultima else 8), self.ALTO_FILA),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, version or 'Sin datos')
            if es_ultima:   # la marca «última»
                fe = fuente(10, QFont.Weight.Bold)
                p.setFont(fe)
                c = QColor(EXITO)
                fondo = QColor(c)
                fondo.setAlpha(30)
                caja = QRectF(etiqueta_ancho - 46, centro - 8, 40, 16)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(fondo)
                p.drawRoundedRect(caja, 8, 8)
                p.setPen(c)
                p.drawText(caja, Qt.AlignmentFlag.AlignCenter, 'última')
            pista = QRectF(izquierda, centro - 4, derecha - izquierda - 8, 8)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#1e1d27'))
            p.drawRoundedRect(pista, 4, 4)
            largo = max(8.0, pista.width() * n / maximo)
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(pista.left(), pista.top(), largo, pista.height()), 4, 4)
            p.setFont(fn)
            p.setPen(QColor(TEXTO))
            p.drawText(QRectF(derecha - 4, y, cifra_ancho + 4, self.ALTO_FILA),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f'{n:,}')


class BarraProporcion(QWidget):
    """Barra partida en colores según cuántos equipos hay en cada grupo (al día, desactualizados, sin datos)."""

    def __init__(self):
        super().__init__()
        self.partes = []
        self.setFixedHeight(8)

    def poner(self, partes):
        self.partes = [(n, color) for n, color in partes if n > 0]
        self.update()

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        camino = QPainterPath()
        camino.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(camino, QColor('#1e1d27'))
        total = sum(n for n, _c in self.partes)
        if not total:
            return
        p.setClipPath(camino)
        x = r.left()
        for i, (n, color) in enumerate(self.partes):
            ancho = r.width() * n / total
            p.fillRect(QRectF(x, r.top(), ancho - (2 if i < len(self.partes) - 1 else 0), r.height()), QColor(color))
            x += ancho


def divisor(vertical=False):
    """Raya de 1 px del color del borde, para separar partes de una tarjeta."""
    raya = QFrame()
    raya.setObjectName('divisor')
    if vertical:
        raya.setFixedWidth(1)
    else:
        raya.setFixedHeight(1)
    return raya


class BloqueVersiones(QFrame):
    """La tarjeta de versiones: cuál es la última, cuántos equipos están al día, desactualizados y sin datos, y el botón
    para anunciarla. con_enlace: el enlace «Ver equipos» (en el Resumen); con_boton: «Anunciar versión…»;
    con_grafica: también los equipos de cada versión en barras (en el Resumen; en Versiones ya está la gráfica grande).
    ancha: en tres columnas separadas por una raya (la versión, cuántos ya la tienen y el botón · el estado de los equipos
    · las barras por versión). Así, en el Resumen, ocupa todo el ancho con todo a la vista; «Anunciar» va justo debajo
    de lo suyo (lo que sobra queda abajo de la columna, nunca un hueco antes del botón) y las barras, al medio de la suya.
    Mientras carga, todo queda en su lugar con «—» (la tarjeta no cambia de tamaño cuando llegan los datos)."""
    ver = Signal()
    anunciar = Signal()

    def __init__(self, con_enlace=True, con_boton=True, con_grafica=False, ancha=False):
        super().__init__()
        self.setObjectName('tarjeta')
        self.ancha = ancha
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Maximum if ancha else QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)   # (como las demás tarjetas)
        lay.setSpacing(12)
        self.btn_ver = boton('Ver equipos', 'derecha', tipo='enlace')
        self.btn_ver.setLayoutDirection(Qt.LayoutDirection.RightToLeft)   # la flecha a la derecha del texto
        self.btn_ver.clicked.connect(self.ver)
        self.btn_ver.setVisible(con_enlace)
        # La última versión: el número grande, «última versión» y cuándo se publicó
        self.numero = etiqueta('—', 'numeroGrande')
        self.lbl_ultima = etiqueta('última versión', 'suave')
        self.lbl_fecha = Recortada('', 'tenue')
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addStretch(1)
        col.addWidget(self.lbl_ultima)
        col.addWidget(self.lbl_fecha)
        col.addStretch(1)
        heroe = QHBoxLayout()
        heroe.setSpacing(12)
        heroe.addWidget(self.numero)
        heroe.addLayout(col, 1)
        # El estado de los equipos: la barra partida y cuántos hay de cada uno
        self.barra = BarraProporcion()
        leyenda = QGridLayout()
        leyenda.setContentsMargins(0, 0, 0, 0)
        leyenda.setHorizontalSpacing(8)
        leyenda.setVerticalSpacing(6)
        leyenda.setColumnStretch(1, 1)
        self.cifras = {}
        for n, (clave, texto, color) in enumerate((('al_dia', 'Al día', EXITO), ('desactualizados', 'Desactualizados', AVISO),
                                                   ('sin_datos', 'Sin datos', TEXTO_TENUE))):
            marca = QLabel()
            marca.setPixmap(punto(color, 8))
            cifra = etiqueta('—')
            cifra.setFont(fuente(13, QFont.Weight.DemiBold, cifras=True))
            cifra.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            leyenda.addWidget(marca, n, 0)
            leyenda.addWidget(etiqueta(texto, 'suave'), n, 1)
            leyenda.addWidget(cifra, n, 2)
            self.cifras[clave] = cifra
        self.leyenda = QWidget()
        self.leyenda.setLayout(leyenda)
        self.lbl_activos = etiqueta('', 'tenue')
        self.lbl_activos.setWordWrap(True)
        self.mensaje = etiqueta('', 'suave')
        self.mensaje.setWordWrap(True)
        self.mensaje.hide()
        self.btn_anunciar = boton('Anunciar versión…', 'megafono', tipo='primario')
        self.btn_anunciar.clicked.connect(self.anunciar)
        self.btn_anunciar.setVisible(con_boton)
        self._con_boton = con_boton
        self.grafica = self.lbl_grafica = None
        self.lbl_adopcion = None   # (ancha) «El 50 % de los equipos ya la tiene», debajo de la versión
        self._extras = ()          # lo de la gráfica que se esconde hasta que llegue la acción versiones (angosta)
        self._columna_grafica = ()  # la columna de la gráfica (ancha): se esconde si no hay datos de versiones
        if con_grafica:
            self.lbl_grafica = etiqueta('EQUIPOS POR VERSIÓN', 'tarjetaTitulo', espaciado=True)
            self.grafica = GraficaVersiones(centrar=ancha)   # (con una o dos versiones, al medio de su columna)
        if ancha:
            self._armar_ancha(lay, heroe)
        else:
            self._armar_angosta(lay, heroe)
        self.cargando()

    def _titulo(self, texto, extra=None):
        """El título chico de una parte, siempre del mismo alto (con o sin enlace): los de las columnas quedan parejos."""
        caja = QWidget()
        caja.setFixedHeight(20)
        fila = QHBoxLayout(caja)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.addWidget(etiqueta(texto, 'tarjetaTitulo', espaciado=True))
        fila.addStretch(1)
        if extra is not None:
            fila.addWidget(extra)
        return caja

    def _armar_angosta(self, lay, heroe):
        lay.addWidget(self._titulo('VERSIONES', self.btn_ver))   # (corto: cabe con «Ver equipos»)
        lay.addLayout(heroe)
        for w in (self.barra, self.leyenda, self.lbl_activos):
            lay.addWidget(w)
        if self.grafica is not None:
            separador = divisor()
            lay.addSpacing(4)
            lay.addWidget(separador)
            lay.addSpacing(4)
            lay.addWidget(self.lbl_grafica)
            lay.addWidget(self.grafica)
            self._extras = (separador, self.lbl_grafica, self.grafica)
            for w in self._extras:
                w.hide()   # hasta que llegue la acción versiones
        lay.addWidget(self.mensaje)
        lay.addWidget(self.btn_anunciar)   # (justo después de lo de arriba: si sobra lugar, queda abajo de la tarjeta)
        lay.addStretch(1)

    def _armar_ancha(self, lay, heroe):
        columnas = QHBoxLayout()
        columnas.setSpacing(24)
        # (de una línea y de alto fijo: mientras carga queda vacía en su lugar y el botón no salta al llegar los datos)
        self.lbl_adopcion = etiqueta('', 'suave', plano=False)
        self.lbl_adopcion.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_adopcion.setFixedHeight(20)
        c1 = QVBoxLayout()
        c1.setSpacing(0)
        c1.addWidget(self._titulo('VERSIONES'))
        c1.addSpacing(12)
        c1.addLayout(heroe)
        c1.addSpacing(8)
        c1.addWidget(self.lbl_adopcion)
        c1.addSpacing(16)
        c1.addWidget(self.btn_anunciar)
        c1.addStretch(1)   # lo que sobra va abajo: nunca un hueco entre la versión y «Anunciar»
        primera = QWidget()
        primera.setLayout(c1)
        primera.setFixedWidth(248)
        c1.setContentsMargins(0, 0, 0, 0)
        c2 = QVBoxLayout()
        c2.setSpacing(12)
        c2.addWidget(self._titulo('ESTADO DE LOS EQUIPOS'))
        for w in (self.barra, self.leyenda, self.lbl_activos, self.mensaje):
            c2.addWidget(w)
        c2.addStretch(1)
        columnas.addWidget(primera, 0)
        columnas.addWidget(divisor(vertical=True))
        columnas.addLayout(c2, 1)
        if self.grafica is not None:
            c3 = QVBoxLayout()
            c3.setSpacing(8)
            c3.addWidget(self._titulo('EQUIPOS POR VERSIÓN', self.btn_ver))
            c3.addWidget(self.grafica, 1)   # (toma el alto de la columna: con pocas versiones, las barras van al medio)
            tercera = QWidget()
            tercera.setLayout(c3)
            c3.setContentsMargins(0, 0, 0, 0)
            raya = divisor(vertical=True)
            columnas.addWidget(raya)
            columnas.addWidget(tercera, 1)
            self._columna_grafica = (raya, tercera)
        lay.addLayout(columnas)

    def poner(self, versiones, info=None):
        """versiones: el bloque «versiones» del resumen (o lo que devuelve la acción versiones); info: version_actual."""
        if versiones is None:
            self.cargando()
            return
        info = info or {}
        ultima = texto_version(versiones.get('ultima')) or texto_version(info.get('version'))
        self.numero.setText(ultima or '—')
        if info.get('error') and not info.get('fecha'):
            self.lbl_fecha.poner('No se pudo leer GitHub')
        else:
            fecha = fecha_dia_corta(info.get('fecha'))   # (una fecha que no se entiende no sale como «publicada el —»)
            self.lbl_fecha.poner(f'publicada el {fecha}' if fecha != '—' else '')
        al, des, sin = versiones.get('al_dia', 0), versiones.get('desactualizados', 0), versiones.get('sin_datos', 0)
        self.barra.poner([(al, EXITO), (des, AVISO), (sin, TEXTO_TENUE)])
        for clave, n in (('al_dia', al), ('desactualizados', des), ('sin_datos', sin)):
            self.cifras[clave].setText(f'{n:,}')
            self.cifras[clave].setStyleSheet('' if n else f'color: {TEXTO_TENUE};')   # (los ceros, más tenues)
        total = al + des + sin   # (sin saber la última versión, admin.php no cuenta a los que sí la mandaron)
        self._poner_adopcion(al, total, texto_version(versiones.get('ultima')))
        activos = versiones.get('activos_30d', 0)
        usados = f"{plural(activos, 'equipo usado', 'equipos usados')} en los últimos 30 días"
        if not texto_version(versiones.get('ultima')):
            self.lbl_activos.setText(f'{usados}.' if activos or total else 'Todavía no hay equipos activados.')
        else:
            self.lbl_activos.setText(f"{usados}, de {plural(total, 'equipo', 'equipos')} con licencia activa." if total else
                                     'Todavía no hay equipos activados.')
        self.btn_anunciar.setText(f' Anunciar versión {ultima}…' if ultima else ' Anunciar versión…')
        self.btn_anunciar.setEnabled(bool(ultima))
        for w in (self.lbl_ultima, self.lbl_fecha, self.barra, self.leyenda, self.lbl_activos) + self._columna_grafica:
            w.show()
        if self.grafica is not None:
            for w in self._extras:
                w.setVisible(bool(self.grafica.filas))
        self.btn_anunciar.setVisible(self._con_boton)
        self.mensaje.hide()

    def _poner_adopcion(self, al_dia, total, ultima):
        """(ancha) Cuántos equipos ya tienen la última versión, en porcentaje y sin pasarse: si falta uno no dice
        «100 %» y si hay uno no dice «0 %»."""
        if self.lbl_adopcion is None:
            return
        if not ultima or not total:
            self.lbl_adopcion.setText('')
            self.lbl_adopcion.setToolTip('')
            return
        verde = f'<span style="color:{EXITO}; font-weight:600">'
        if al_dia >= total:
            texto = f'{verde}Todos</span> los equipos ya la tienen'
        elif not al_dia:
            texto = 'Ningún equipo la tiene todavía'
        else:
            texto = f'{verde}{min(99, max(1, al_dia * 100 // total))}&nbsp;%</span> de los equipos ya la tiene'
        self.lbl_adopcion.setText(texto)
        self.lbl_adopcion.setToolTip(f"{al_dia:,} de {plural(total, 'equipo', 'equipos')} con licencia activa tienen la {ultima}")

    def poner_por_version(self, por_version, ultima):
        """Las barras de equipos por versión (solo si el bloque se armó con_grafica)."""
        if self.grafica is None:
            return
        self.grafica.poner(por_version, ultima)
        for w in self._extras:
            w.setVisible(bool(self.grafica.filas) and self.leyenda.isVisibleTo(self))

    def cargando(self):
        """Mientras llegan los datos: todo en su lugar, con «—»."""
        self.numero.setText('—')
        self.lbl_fecha.poner('')
        self.barra.poner([])
        for cifra in self.cifras.values():
            cifra.setText('—')
            cifra.setStyleSheet(f'color: {TEXTO_TENUE};')
        self.lbl_activos.setText('')
        self._poner_adopcion(0, 0, None)
        for w in (self.lbl_ultima, self.lbl_fecha, self.barra, self.leyenda, self.lbl_activos) + self._columna_grafica:
            w.show()
        for w in self._extras:
            w.hide()
        if self.grafica is not None:
            self.grafica.vaciar('Cargando…')
        self.mensaje.hide()
        self.btn_anunciar.setText(' Anunciar versión…')
        self.btn_anunciar.setEnabled(False)
        self.btn_anunciar.setVisible(self._con_boton)

    def sin_datos(self, texto):
        """Sin datos de versiones (por ejemplo, el servidor publicado todavía es el anterior)."""
        self.numero.setText('—')
        self._poner_adopcion(0, 0, None)
        for w in (self.lbl_fecha, self.barra, self.leyenda, self.lbl_activos, self.btn_anunciar) + self._extras \
                + self._columna_grafica:
            w.hide()
        self.lbl_ultima.show()
        self.mensaje.setText(texto)
        self.mensaje.show()


class PlanVersiones(QFrame):
    """Lo de arriba de la página Versiones: para saber en 3 segundos quién va atrasado y avisarle con un clic.
    A la izquierda, en palabras: cuál es la última versión, cuántos clientes todavía no la tienen y a cuántos ya se les
    avisó, y la barra de clientes al día · con una versión vieja · sin datos con sus números. A la derecha, LA acción:
    «Avisar a los N desactualizados…» (abre «Anunciar versión», que muestra a quiénes antes de mandar). En una tarjeta
    ancha (1920 px), en medio, cuántos equipos hay en cada versión; en una angosta (1100 px) eso no va y la acción pasa
    abajo, a todo lo ancho: nada se corta. Cuenta los clientes con la licencia activa (con una bloqueada CineCaptions no
    funciona), los mismos que los filtros de abajo y que candidatos_aviso de admin.php."""
    anunciar = Signal()
    ANCHO_COLUMNAS = 700    # con la tarjeta más angosta que esto, la acción va debajo
    ANCHO_GRAFICA = 1060    # y con una más ancha, en medio caben los equipos de cada versión

    def __init__(self):
        super().__init__()
        self.setObjectName('tarjeta')
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.cuenta = {}           # lo último que se mostró (clientes, desactualizado, avisados, por_avisar...)
        self._columnas = None
        self._con_grafica = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        self._caja = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._caja.setSpacing(24)
        lay.addLayout(self._caja)
        # El estado, en palabras
        self.lbl_titulo = etiqueta('VERSIONES', 'tarjetaTitulo', espaciado=True)
        self.lbl_frase = etiqueta('', plano=False)
        self.lbl_frase.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_frase.setFont(fuente(18, QFont.Weight.DemiBold))
        self.lbl_frase.setWordWrap(True)
        self.lbl_detalle = etiqueta('', 'suave')
        self.lbl_detalle.setWordWrap(True)
        self.barra = BarraProporcion()
        self.lbl_leyenda = etiqueta('', 'suave', plano=False)
        self.lbl_leyenda.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_leyenda.setWordWrap(True)
        self.lbl_leyenda.setToolTip('Cuenta los clientes con la licencia activa.\n«Sin datos»: ' + SIN_DATOS_VERSION)
        izq = QVBoxLayout()
        izq.setContentsMargins(0, 0, 0, 0)
        izq.setSpacing(0)
        izq.addWidget(self.lbl_titulo)
        izq.addSpacing(8)
        izq.addWidget(self.lbl_frase)
        izq.addSpacing(4)
        izq.addWidget(self.lbl_detalle)
        izq.addSpacing(14)
        izq.addWidget(self.barra)
        izq.addSpacing(8)
        izq.addWidget(self.lbl_leyenda)
        izq.addStretch(1)
        self.izquierda = QWidget()
        self.izquierda.setLayout(izq)
        # En medio (solo si es ancha): los equipos de cada versión
        self.grafica = GraficaVersiones(centrar=True, alto_fila=24)
        med = QVBoxLayout()
        med.setContentsMargins(0, 0, 0, 0)
        med.setSpacing(6)
        med.addWidget(etiqueta('EQUIPOS POR VERSIÓN', 'tarjetaTitulo', espaciado=True))
        med.addWidget(self.grafica, 1)
        self.medio = QWidget()
        self.medio.setLayout(med)
        self.medio.setFixedWidth(300)
        self.raya_medio = divisor(vertical=True)
        # La acción
        self.btn_avisar = boton('Avisar a los desactualizados…', 'megafono', tipo='primario')
        self.btn_avisar.setMinimumHeight(40)
        self.btn_avisar.clicked.connect(self.anunciar)
        self.lbl_accion = etiqueta('', 'tenue')
        self.lbl_accion.setWordWrap(True)
        self._der = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self._der.setContentsMargins(0, 0, 0, 0)
        self._der.setSpacing(8)
        self._der.addWidget(self.btn_avisar)
        self._der.addWidget(self.lbl_accion, 1)
        self.derecha = QWidget()
        self.derecha.setLayout(self._der)
        self.raya_accion = divisor(vertical=True)
        self._caja.addWidget(self.izquierda, 1)
        self._caja.addWidget(self.raya_medio)
        self._caja.addWidget(self.medio)
        self._caja.addWidget(self.raya_accion)
        self._caja.addWidget(self.derecha)
        self._acomodar(1200)
        self.cargando()

    # --- Cómo se acomoda según el ancho
    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._acomodar(evento.size().width())

    def _acomodar(self, ancho):
        columnas = ancho >= self.ANCHO_COLUMNAS
        if columnas != self._columnas:
            self._columnas = columnas
            self._caja.setDirection(QBoxLayout.Direction.LeftToRight if columnas else QBoxLayout.Direction.TopToBottom)
            self._caja.setSpacing(24 if columnas else 14)
            self.raya_accion.setVisible(columnas)
            # (a la derecha: el botón arriba y la nota debajo; abajo: el botón y la nota a la par, a todo lo ancho)
            self._der.setDirection(QBoxLayout.Direction.TopToBottom if columnas else QBoxLayout.Direction.LeftToRight)
            self._der.setSpacing(8 if columnas else 14)
            self._der.setAlignment(self.btn_avisar, Qt.AlignmentFlag.AlignTop if columnas else Qt.AlignmentFlag.AlignVCenter)
            self.lbl_accion.setAlignment(Qt.AlignmentFlag.AlignLeft | (Qt.AlignmentFlag.AlignTop if columnas
                                                                       else Qt.AlignmentFlag.AlignVCenter))
            if columnas:
                self.derecha.setFixedWidth(250)
            else:
                self.derecha.setMinimumWidth(0)
                self.derecha.setMaximumWidth(16777215)
        self._con_grafica = ancho >= self.ANCHO_GRAFICA
        self._mostrar_grafica()

    def _mostrar_grafica(self):
        ver = self._con_grafica and self._columnas and bool(self.grafica.filas)
        self.medio.setVisible(ver)
        self.raya_medio.setVisible(ver)

    # --- Estados
    def cargando(self):
        """Mientras llegan los equipos: todo en su lugar (la tarjeta no cambia de alto al llegar los datos)."""
        self.cuenta = {}
        self.lbl_titulo.setText('VERSIONES')
        self._frase('Cargando…', TEXTO_TENUE)
        self.lbl_detalle.setText(' ')
        self.barra.poner([])
        self.barra.show()
        self.lbl_leyenda.setText(' ')
        self.lbl_leyenda.show()
        self.grafica.vaciar('Cargando…')
        self._poner_accion(None, '', False)
        self.derecha.show()

    def sin_datos(self, texto):
        """Sin datos de versiones (por ejemplo, el servidor publicado todavía es el anterior)."""
        self.cuenta = {}
        self.lbl_titulo.setText('VERSIONES')
        self._frase('Todavía no se pueden ver las versiones', TEXTO_SUAVE)
        self.lbl_detalle.setText(texto)
        self.barra.hide()
        self.lbl_leyenda.hide()
        self.grafica.vaciar(texto)
        self.derecha.hide()
        self.raya_accion.hide()
        self._mostrar_grafica()

    def poner(self, clientes, ultima, info=None, por_version=None):
        """clientes: los de agrupar_versiones (todos: aquí se cuentan los de licencia activa); ultima: la última versión;
        info: lo de version_actual (la fecha en que se publicó); por_version: los equipos de cada versión."""
        info = info or {}
        ultima = texto_version(ultima) or texto_version(info.get('version'))
        activos = [c for c in clientes if c.get('licencia_estado') == 'activa']
        n = {k: sum(1 for c in activos if c['estado'] == k) for k in ('al_dia', 'desactualizado', 'sin_datos', 'desconocido')}
        viejos = [c for c in activos if c['estado'] == 'desactualizado']
        avisados = [c for c in viejos if avisado_de(c, ultima)]
        por_avisar = [c for c in viejos if not avisado_de(c, ultima) and c.get('correo')]
        sin_correo = [c for c in viejos if not avisado_de(c, ultima) and not c.get('correo')]
        equipos_viejos = sum(c['viejos'] for c in viejos)
        self.cuenta = dict(n, clientes=len(activos), avisados=len(avisados), por_avisar=len(por_avisar),
                           sin_correo=len(sin_correo), equipos_viejos=equipos_viejos, bloqueados=len(clientes) - len(activos))
        self.derecha.show()
        self.raya_accion.setVisible(bool(self._columnas))
        fecha = fecha_dia_corta(info.get('fecha')) if info.get('fecha') else '—'
        self.lbl_titulo.setText(f"LA ÚLTIMA ES LA {ultima}" + (f' · SALIÓ EL {fecha.upper()}' if fecha != '—' else '')
                                if ultima else 'VERSIONES')
        anunciar = f' Anunciar versión {ultima}…' if ultima else ' Anunciar versión…'
        if not ultima:
            self._frase('No se sabe cuál es la última versión', AVISO)
            self.lbl_detalle.setText((info.get('error') or 'El servidor no pudo leer la versión publicada en GitHub.')
                                     + ' Vuelve a intentarlo con «Actualizar» en un rato.')
            self._poner_accion(anunciar, 'Puedes anunciar una versión escribiéndola a mano.', True, primario=False)
        elif not activos:
            self._frase('Todavía ningún cliente activó CineCaptions', TEXTO_SUAVE)
            self.lbl_detalle.setText('Cuando alguien active su licencia, aquí vas a ver qué versión usa y si hace falta '
                                     'avisarle que actualice.')
            self._poner_accion(anunciar, '', True, primario=False)
        elif viejos:
            cuantos = len(viejos)
            self._frase(f'<span style="color:{AVISO}">{html.escape(plural(cuantos, "cliente", "clientes"))}</span> todavía '
                        f'no {"tiene" if cuantos == 1 else "tienen"} la {ultima}')
            partes = [f"{'Usa' if cuantos == 1 else 'Usan'} una versión anterior en "
                      f"{plural(equipos_viejos, 'equipo', 'equipos')}."]
            if avisados and not por_avisar and not sin_correo:
                partes.append('Ya les avisaste a todos.' if cuantos > 1 else 'Ya le avisaste.')
            elif avisados:
                partes.append(f"A {plural(len(avisados), 'cliente', 'clientes')} ya les avisaste; "
                              f"{'falta' if len(por_avisar) + len(sin_correo) == 1 else 'faltan'} "
                              f'{len(por_avisar) + len(sin_correo)}.')
            else:
                partes.append('Todavía no les avisaste.' if cuantos > 1 else 'Todavía no le avisaste.')
            if sin_correo:
                partes.append(f"{plural(len(sin_correo), 'licencia no tiene', 'licencias no tienen')} un correo válido.")
            self.lbl_detalle.setText(' '.join(partes))
            if por_avisar:
                k = len(por_avisar)
                if avisados:
                    texto = ' Avisar al que falta…' if k == 1 else f' Avisar a los {k} que faltan…'
                else:
                    texto = ' Avisar al cliente desactualizado…' if k == 1 else f' Avisar a los {k} desactualizados…'
                self._poner_accion(texto, 'Les llega un correo con lo nuevo y el enlace para descargarla. Antes de '
                                          'mandarlo ves a quiénes.', True)
            else:
                self._poner_accion(anunciar, 'Ya les avisaste a todos los que tienen correo.', True, primario=False)
        elif n['sin_datos'] and not n['al_dia']:
            self._frase('Todavía no se sabe qué versión usan tus clientes', TEXTO_SUAVE)
            self.lbl_detalle.setText('Sus equipos no han abierto CineCaptions desde que el servidor empezó a guardar la '
                                     'versión. Aparece sola la próxima vez que lo abran.')
            self._poner_accion(anunciar, '', True, primario=False)
        else:
            if n['sin_datos']:
                self._frase('Nadie va atrasado', EXITO)
                self.lbl_detalle.setText(f"{plural(n['al_dia'], 'cliente ya tiene', 'clientes ya tienen')} la {ultima}; "
                                         f"de {plural(n['sin_datos'], 'cliente', 'clientes')} todavía no se sabe.")
            else:
                self._frase(f'Todos tus clientes tienen la {ultima}', EXITO)
                self.lbl_detalle.setText('No hace falta avisarle a nadie.')
            self._poner_accion(anunciar, '', True, primario=False)
        total = n['al_dia'] + n['desactualizado'] + n['sin_datos'] + n['desconocido']
        self.barra.poner([(n['al_dia'], EXITO), (n['desactualizado'], AVISO), (n['sin_datos'], TEXTO_TENUE),
                          (n['desconocido'], TEXTO_SUAVE)])
        self.barra.setVisible(bool(total))
        punto_html = '<span style="color:{}">&#9679;</span>&nbsp;'.format
        separa = '&nbsp;&nbsp;&nbsp;&nbsp;'
        partes = [punto_html(EXITO) + html.escape(plural(n['al_dia'], 'cliente al día', 'clientes al día')),
                  punto_html(AVISO) + html.escape(f"{n['desactualizado']:,} con una versión vieja"),
                  punto_html(TEXTO_TENUE) + html.escape(f"{n['sin_datos']:,} sin datos")]
        if n['desconocido']:
            partes.append(punto_html(TEXTO_SUAVE) + html.escape(f"{n['desconocido']:,} sin comparar"))
        self.lbl_leyenda.setText(separa.join(partes) if total else '')
        self.lbl_leyenda.setVisible(bool(total))
        if por_version is not None:
            self.grafica.poner(por_version, ultima)
        self._mostrar_grafica()

    def _frase(self, texto_html, color=None):
        self.lbl_frase.setText(f'<span style="color:{color}">{texto_html}</span>' if color else texto_html)

    def _poner_accion(self, texto, nota, activo, primario=True):
        tipo = 'primario' if primario else None
        if self.btn_avisar.property('tipo') != tipo:
            self.btn_avisar.setProperty('tipo', tipo)
            self.btn_avisar.setIcon(icono('megafono', '#ffffff' if primario else TEXTO_SUAVE, 16))
            repulir(self.btn_avisar)
        self.btn_avisar.setText(texto or ' Avisar a los desactualizados…')
        self.btn_avisar.setEnabled(activo)
        self.lbl_accion.setText(nota)
        self.lbl_accion.setVisible(bool(nota))


def pintar_monto(p, derecha, base, texto, f, color):
    """«$29.00 USD» terminado en x = derecha, sobre la línea de base: el número con su color y la moneda un poco más chica
    y tenue. Devuelve dónde empieza."""
    numero, codigo = partir_monto(texto)
    x = derecha
    if codigo:
        fc = QFont(f)
        fc.setPixelSize(max(9, f.pixelSize() - 2))
        fc.setWeight(QFont.Weight.Medium)
        x -= QFontMetrics(fc).horizontalAdvance(codigo)
        p.setFont(fc)
        p.setPen(QColor(TEXTO_TENUE))
        p.drawText(QPointF(x, base), codigo)
        x -= 4
    x -= QFontMetrics(f).horizontalAdvance(numero)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(QPointF(x, base), numero)
    return x


class FilaReciente(QAbstractButton):
    """Una venta en «Últimas ventas» del Resumen: cliente, cuándo y el monto. Con un clic (o Tab y espacio) se abre en
    Ventas. Sin venta (None) es una fila gris de «cargando», del mismo alto: al llegar los datos nada salta."""
    ALTO = 48

    def __init__(self, venta=None):
        super().__init__()
        self.venta = venta
        self._encima = False
        self.setFixedHeight(self.ALTO)
        if venta is None:
            self.setEnabled(False)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            self.setToolTip('Abrir esta venta')

    def enterEvent(self, evento):
        self._encima = True
        self.update()
        super().enterEvent(evento)

    def leaveEvent(self, evento):
        self._encima = False
        self.update()
        super().leaveEvent(evento)

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        if self.venta is None:   # cargando: el punto, el nombre, la fecha y el monto como rayitas grises
            p.setBrush(QColor('#1e1d27'))
            p.drawEllipse(QPointF(12, r.center().y()), 3.5, 3.5)
            p.drawRoundedRect(QRectF(28, 13, min(150.0, r.width() * 0.38), 9), 4.5, 4.5)
            p.drawRoundedRect(QRectF(28, 28, min(96.0, r.width() * 0.24), 8), 4, 4)
            p.drawRoundedRect(QRectF(r.width() - 12 - 64, r.center().y() - 4.5, 64, 9), 4.5, 4.5)
            return
        if self.isDown() or self._encima:
            p.setBrush(QColor(255, 255, 255, 6 if self.isDown() else 9))
            p.drawRoundedRect(r, RADIO_CONTROL, RADIO_CONTROL)
        if self.hasFocus():
            p.setPen(QPen(QColor(VIOLETA), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), RADIO_CONTROL - 1, RADIO_CONTROL - 1)
            p.setPen(Qt.PenStyle.NoPen)
        v = self.venta
        texto, color = ESTADOS_VENTA.get(v['estado'], (v['estado'] or '—', TEXTO_SUAVE))
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(12, r.center().y()), 3.5, 3.5)
        f1, f2 = fuente(13, QFont.Weight.DemiBold), fuente(12)
        fmonto = fuente(13, QFont.Weight.DemiBold, cifras=True)   # (los montos de la lista quedan alineados)
        if v['estado'] == 'reembolsado':
            fmonto.setStrikeOut(True)
        monto = dinero(v['monto'], v['moneda'])
        numero, codigo = partir_monto(monto)
        ancho_monto = QFontMetrics(fmonto).horizontalAdvance(numero) + (
            4 + QFontMetrics(fuente(11, QFont.Weight.Medium)).horizontalAdvance(codigo) if codigo else 0)
        izquierda, derecha = 28, r.width() - 12 - ancho_monto - 16
        p.setFont(f1)
        p.setPen(QColor(TEXTO))
        p.drawText(QRectF(izquierda, 6, derecha - izquierda, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   QFontMetrics(f1).elidedText(v['nombre'] or v['correo'] or 'Sin nombre', Qt.TextElideMode.ElideRight,
                                               int(derecha - izquierda)))
        p.setFont(f2)
        p.setPen(QColor(TEXTO_TENUE))
        abajo = f"{fecha_corta(v['pagado'] or v['creado'])} · {texto}"
        p.drawText(QRectF(izquierda, 25, derecha - izquierda, 17), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   QFontMetrics(f2).elidedText(abajo, Qt.TextElideMode.ElideRight, int(derecha - izquierda)))
        fm = QFontMetrics(fmonto)
        pintar_monto(p, r.width() - 12, r.center().y() + (fm.ascent() - fm.descent()) / 2, monto, fmonto,
                     TEXTO if v['estado'] == 'pagado' else TEXTO_TENUE)


class VacioLista(QWidget):
    """El lugar que sobra en una lista: un ícono en un cuadro tenue y un mensaje (o nada, sin mensaje)."""

    def __init__(self, nombre_icono):
        super().__init__()
        self._icono = pintar_icono(nombre_icono, TEXTO_TENUE, 22)
        self.mensaje, self.con_icono = '', True

    def poner(self, mensaje, con_icono=True):
        self.mensaje, self.con_icono = mensaje, con_icono
        self.update()

    def paintEvent(self, _evento):
        if self.mensaje:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            pintar_vacio(p, QRectF(self.rect()), self.mensaje, self._icono if self.con_icono else None)


class ListaRecientes(QFrame):
    """«Últimas ventas» en el Resumen, a la par de la gráfica: tantas como quepan en la tarjeta (de MINIMO a MAXIMO).
    Mientras carga, filas grises del mismo alto (nada salta al llegar los datos); con pocas ventas, en el lugar que
    sobra dice que ahí van a salir las nuevas; sin ventas, el mensaje en el centro."""
    elegida = Signal(int)
    ver_todas = Signal()
    MINIMO, MAXIMO = 3, 12

    def __init__(self):
        super().__init__()
        self.setObjectName('tarjeta')
        self.ventas, self.cargando, self.mensaje = [], True, ''
        self.cuantas = 6
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 16, 12, 12)
        lay.setSpacing(8)
        cabeza = QHBoxLayout()
        cabeza.setContentsMargins(8, 0, 8, 0)
        cabeza.addWidget(etiqueta('ÚLTIMAS VENTAS', 'tarjetaTitulo', espaciado=True))
        cabeza.addStretch(1)
        todas = boton('Ver todas', 'derecha', tipo='enlace')
        todas.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        todas.clicked.connect(self.ver_todas)
        cabeza.addWidget(todas)
        lay.addLayout(cabeza)
        # (el cuerpo no pide alto: toma el de la fila de la gráfica y ahí se calcula cuántas ventas caben)
        self.cuerpo = QWidget()
        self.cuerpo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.cuerpo.setMinimumHeight(self.MINIMO * FilaReciente.ALTO)
        self.cuerpo.installEventFilter(self)
        lc = QVBoxLayout(self.cuerpo)
        lc.setContentsMargins(0, 0, 0, 0)
        lc.setSpacing(0)
        self._filas = QVBoxLayout()
        self._filas.setSpacing(0)
        lc.addLayout(self._filas)
        self.vacio = VacioLista('recibo')
        lc.addWidget(self.vacio, 1)
        lay.addWidget(self.cuerpo, 1)
        self._pintar()

    def eventFilter(self, objeto, evento):
        if objeto is self.cuerpo and evento.type() == QEvent.Type.Resize:
            cuantas = max(self.MINIMO, min(self.MAXIMO, evento.size().height() // FilaReciente.ALTO))
            if cuantas != self.cuantas:
                self.cuantas = cuantas
                QTimer.singleShot(0, self._pintar)   # (fuera del cambio de tamaño)
        return False

    def poner(self, ventas, mensaje='Todavía no hay ventas.'):
        self.ventas, self.cargando, self.mensaje = list(ventas), False, mensaje
        self._pintar()

    def mostrar_cargando(self):
        self.ventas, self.cargando = [], True
        self._pintar()

    def _pintar(self):
        vaciar(self._filas)
        if self.cargando:
            for _ in range(self.cuantas):
                self._filas.addWidget(FilaReciente())
            self.vacio.poner('')
            return
        for v in self.ventas[:self.cuantas]:
            fila = FilaReciente(v)
            fila.clicked.connect(lambda _c=False, ident=v['id']: self.elegida.emit(ident))
            self._filas.addWidget(fila)
        sobran = self.cuantas - min(len(self.ventas), self.cuantas)
        if not self.ventas:
            self.vacio.poner(self.mensaje)
        elif sobran >= 1:
            self.vacio.poner('Aquí vas a ver cada venta nueva.', con_icono=sobran >= 3)
        else:
            self.vacio.poner('')


# ---------------------------------------------------------------- Modelos de las tablas

def orden_version(texto):
    """Clave para ordenar por versión como números («5.5.3» antes que «5.20»); sin datos va primero."""
    partes = partes_version(texto)
    return '' if partes is None else '.'.join(f'{p:06d}' for p in partes)


EXPLICA_MOTIVO = {'ya_avisado': 'Ya le habías avisado de esta versión.', 'baja': 'Pidió no recibir más avisos de actualización.',
                  'sin_correo': 'La licencia no tiene un correo válido.', 'bloqueada': 'La licencia está bloqueada.',
                  'limite': 'El servidor llegó a su tope de 90 correos por hora.',
                  'fallo_envio': 'El servidor no pudo mandar el correo.'}
SIN_DATOS_VERSION = ('Sin datos: este equipo no ha abierto CineCaptions desde que el servidor empezó a guardar la versión '
                     '(o tiene una versión que no la manda).')


class ModeloBase(QAbstractTableModel):
    COLUMNAS = []       # (clave, título, ancho inicial; 0 = se estira)
    OCULTAR = []        # columnas que se esconden en una ventana angosta; la primera es la que se va primero
    ESTIRADA_MIN = 180  # lo mínimo que necesita la columna que se estira
    DOS_LINEAS = ('cliente',)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filas = []
        self.ultima = None          # la última versión de CineCaptions (para pintar la columna «Versión»)
        self.con_versiones = True   # False: el admin.php publicado es el anterior y no manda versiones ni último uso
        self._mono = fuente(12, QFont.Weight.Medium, mono=True)
        self._tabular = con_cifras_tabulares(fuente(13, QFont.Weight.Medium))
        self._tachada = con_cifras_tabulares(fuente(13))
        self._tachada.setStrikeOut(True)
        self._dato = con_cifras_tabulares(fuente(12))   # fechas y «hace…»: un punto más chico que el cliente y el monto

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.filas)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.COLUMNAS)

    def headerData(self, seccion, orientacion, rol=Qt.ItemDataRole.DisplayRole):
        if orientacion != Qt.Orientation.Horizontal:
            return None
        if rol == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNAS[seccion][1]
        if rol == Qt.ItemDataRole.TextAlignmentRole:
            return self.alineacion(self.COLUMNAS[seccion][0])
        return None

    def cargar(self, filas):
        self.beginResetModel()
        self.filas = list(filas)
        self.endResetModel()

    def agregar(self, filas):
        if filas:
            self.beginInsertRows(QModelIndex(), len(self.filas), len(self.filas) + len(filas) - 1)
            self.filas.extend(filas)
            self.endInsertRows()

    def fila(self, n):
        return self.filas[n] if 0 <= n < len(self.filas) else None

    def buscar(self, campo, valor):
        return [] if valor is None else [i for i, f in enumerate(self.filas) if f.get(campo) == valor]

    def cambiar(self, n, cambios):
        self.filas[n].update(cambios)
        self.dataChanged.emit(self.index(n, 0), self.index(n, len(self.COLUMNAS) - 1))

    def poner_ultima(self, ultima):
        if ultima != self.ultima:
            self.ultima = ultima
            self._todo_cambio()

    def poner_con_versiones(self, valor):
        if valor != self.con_versiones:
            self.con_versiones = valor
            self._todo_cambio()

    def _todo_cambio(self):
        if self.filas:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.filas) - 1, len(self.COLUMNAS) - 1))

    def data(self, indice, rol=Qt.ItemDataRole.DisplayRole):
        if not indice.isValid() or indice.row() >= len(self.filas):
            return None
        f, c = self.filas[indice.row()], self.COLUMNAS[indice.column()][0]
        if rol == Qt.ItemDataRole.DisplayRole:
            return self.texto(f, c)
        if rol == ROL_ORDEN:
            return self.orden(f, c)
        if rol == ROL_INSIGNIA:
            return self.insignia(f, c)
        if rol == ROL_SEGUNDA:
            return self.segunda(f, c)
        if rol == Qt.ItemDataRole.ForegroundRole:
            color = self.color(f, c)
            if color is None and self.texto(f, c) == '—':   # un dato que falta sale tenue en todas las columnas
                color = TEXTO_TENUE
            return QColor(color) if color else None
        if rol == Qt.ItemDataRole.TextAlignmentRole:
            return self.alineacion(c)
        if rol == Qt.ItemDataRole.FontRole:
            return self.fuente(f, c)
        if rol == Qt.ItemDataRole.ToolTipRole:
            return self.ayuda(f, c)
        return None

    def segunda(self, f, c):
        if c == 'cliente' and f.get('nombre'):
            return f.get('correo')
        return None

    # comunes a las tablas
    def alineacion(self, c):
        if c in ('monto',):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if c == 'equipos':
            return Qt.AlignmentFlag.AlignCenter
        return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def _cliente(self, f):
        return f.get('nombre') or f.get('correo') or '—'

    def _licencia(self, f):
        if not f.get('licencia_estado'):
            return None
        if f['licencia_estado'] == 'activa':
            return ('Activa', EXITO, 'punto', TEXTO_SUAVE)
        return ('Bloqueada', PELIGRO, 'punto', PELIGRO)

    def _equipos(self, f):
        if f.get('licencia_id') is None:
            return '—'
        return f"{f.get('equipos') or 0} / {f.get('limite') if f.get('limite') is not None else '?'}"

    def _color_equipos(self, f):
        if f.get('licencia_id') is None or not f.get('equipos'):
            return TEXTO_TENUE
        return AVISO if f.get('limite') and f['equipos'] >= f['limite'] else TEXTO

    def _ayuda_equipos(self, f):
        if f.get('licencia_id') is None:
            return 'Sin licencia'
        return f"{f.get('equipos') or 0} de {f.get('limite') or 0} computadoras activadas"

    # La versión de una venta o un canje (la del equipo usado más recientemente) y su último uso
    def _version_texto(self, f):
        if not self.con_versiones or estado_fila_version(f, self.ultima) is None:
            return '—'
        return texto_version(f.get('version')) or 'Sin datos'

    def _version_insignia(self, f):
        estado = estado_fila_version(f, self.ultima)
        if estado is None or not self.con_versiones:
            return None
        return (self._version_texto(f), ESTADOS_VERSION.get(estado, ESTADOS_VERSION['desconocido'])[1], 'pastilla', None)

    def _version_orden(self, f):
        estado = estado_fila_version(f, self.ultima)
        rango = {'desactualizado': '0', 'sin_datos': '1', 'desconocido': '2', 'al_dia': '3'}.get(estado, '4')
        return rango + orden_version(f.get('version'))

    def _version_ayuda(self, f):
        if not self.con_versiones:
            return FALTA_SERVIDOR
        estado = estado_fila_version(f, self.ultima)
        if estado is None:
            return 'Ningún equipo activado todavía.'
        version = texto_version(f.get('version'))
        partes = [f'Equipo usado más recientemente: {version}' if version else SIN_DATOS_VERSION]
        viejos = f.get('equipos_desactualizados') or 0
        ultima = texto_version(self.ultima)
        if viejos:
            partes.append(f"{viejos} de {plural(f.get('equipos') or 0, 'equipo', 'equipos')} con una versión vieja"
                          + (f' (la última es la {ultima}).' if ultima else '.'))
        elif estado == 'al_dia':
            partes.append(f'Al día: tiene la última ({ultima}).' if ultima else 'Al día.')
        elif estado == 'desconocido':
            partes.append('No se sabe cuál es la última versión publicada.')
        return '\n'.join(partes)

    def _uso(self, f):
        return hace(f.get('ultima_vez')) if f.get('ultima_vez') and self.con_versiones else '—'

    def fuente(self, f, c):
        if c == 'clave' and f.get('clave'):
            return self._mono
        if c == 'equipos':
            return self._tabular
        if c in ('fecha', 'uso', 'venta', 'desde', 'aviso'):
            return self._dato
        return None

    def ayuda(self, f, c):
        if c == 'equipos':
            return self._ayuda_equipos(f)
        if c == 'clave' and f.get('clave'):
            return 'Clic derecho para copiar la clave'
        if c == 'cliente':   # el texto completo, por si la columna lo corta
            return '\n'.join(x for x in (f.get('nombre'), f.get('correo')) if x) or None
        if c == 'version':
            return self._version_ayuda(f)
        if c == 'uso' and f.get('ultima_vez'):
            return f"Abrió CineCaptions por última vez: {fecha_larga(f['ultima_vez'])}"
        return None


class ModeloVentas(ModeloBase):
    COLUMNAS = [('fecha', 'Fecha', 104), ('cliente', 'Cliente', 0), ('monto', 'Monto', 120), ('estado', 'Estado', 114),
                ('version', 'Versión', 92), ('uso', 'Último uso', 100), ('licencia', 'Licencia', 96),
                ('equipos', 'Equipos', 66), ('clave', 'Clave', 182)]
    OCULTAR = ['clave', 'equipos', 'licencia', 'uso']
    ESTIRADA_MIN = 170
    ORDEN_ESTADO = {'pagado': 0, 'reembolsado': 1, 'pendiente': 2}

    def texto(self, f, c):
        if c == 'fecha':
            return fecha_corta(f['pagado'] or f['creado'])
        if c == 'cliente':
            return self._cliente(f)
        if c == 'monto':
            return dinero(f['monto'], f['moneda'])
        if c == 'estado':
            return ESTADOS_VENTA.get(f['estado'], (f['estado'] or '—',))[0]
        if c == 'version':
            return self._version_texto(f)
        if c == 'uso':
            return self._uso(f)
        if c == 'clave':
            return f['clave'] or '—'
        if c == 'licencia':
            return texto_licencia(f['licencia_estado']) or '—'
        if c == 'equipos':
            return self._equipos(f)
        return ''

    def orden(self, f, c):
        if c == 'fecha':
            return f['pagado'] or f['creado'] or ''
        if c == 'cliente':
            return self._cliente(f).casefold()
        if c == 'monto':
            return f['monto'] if f['monto'] is not None else -1
        if c == 'estado':
            return self.ORDEN_ESTADO.get(f['estado'], 3)
        if c == 'version':
            return self._version_orden(f)
        if c == 'uso':
            return f.get('ultima_vez') or ''
        if c == 'clave':
            return f['clave'] or ''
        if c == 'licencia':
            return {'activa': 0, 'bloqueada': 1}.get(f['licencia_estado'], 2 if f['licencia_estado'] else 3)
        if c == 'equipos':
            return f['equipos'] if f['licencia_id'] is not None else -1
        return ''

    def insignia(self, f, c):
        datos = self._insignia(f, c)
        if datos and venta_eliminada(f):   # (una venta eliminada se ve atenuada: todo en gris)
            return (datos[0], TEXTO_TENUE, datos[2], TEXTO_TENUE)
        return datos

    def _insignia(self, f, c):
        if c == 'estado':
            texto, color = ESTADOS_VENTA.get(f['estado'], (f['estado'] or '—', TEXTO_SUAVE))
            return (texto, color, 'pastilla', None)
        if c == 'licencia':
            return self._licencia(f)
        if c == 'version':
            return self._version_insignia(f)
        return None

    def color(self, f, c):
        if venta_eliminada(f):
            return TEXTO_TENUE
        if c == 'cliente' and not (f['nombre'] or f['correo']):
            return TEXTO_TENUE
        if c == 'fecha':
            return TEXTO_SUAVE
        if c in ('clave', 'uso'):
            return TEXTO_SUAVE if f.get('clave' if c == 'clave' else 'ultima_vez') else TEXTO_TENUE
        if c == 'monto':
            return TEXTO if f['estado'] == 'pagado' else TEXTO_TENUE
        if c == 'equipos':
            return self._color_equipos(f)
        if c in ('licencia', 'version') and not f['licencia_estado']:
            return TEXTO_TENUE
        return None

    def fuente(self, f, c):
        if c == 'monto':
            return self._tachada if f['estado'] == 'reembolsado' else self._tabular
        return super().fuente(f, c)

    def segunda(self, f, c):
        # 2.8: debajo del monto, en violeta, el código del cupón con que se compró (la ayuda lo explica)
        if c == 'monto' and f.get('cupon'):
            return f['cupon']
        return super().segunda(f, c)

    def ayuda(self, f, c):
        if c in ('fecha', 'estado') and venta_eliminada(f):
            return (f"Eliminada de la lista: {fecha_larga(f['eliminada'])}. No cuenta en los totales.\n"
                    'Clic derecho o «Restaurar venta» en el panel para que vuelva.')
        if c == 'monto' and f.get('cupon'):
            descuento = f" (descuento de {dinero(f['descuento'], f['moneda'])})" if f.get('descuento') else ''
            gratis = '\nLicencia gratis: el cupón cubría el precio completo.' if f.get('monto') == 0 else ''
            return f"Comprada con el cupón {f['cupon']}{descuento}.{gratis}"
        if c == 'fecha':
            partes = []
            if f['pagado']:
                partes.append(f"Pagada: {fecha_larga(f['pagado'])}")
            partes.append(f"Creada: {fecha_larga(f['creado'])}")
            return '\n'.join(partes)
        if c == 'estado' and f['estado'] == 'pendiente':
            return 'El cliente abrió el pago pero no lo completó.'
        if c == 'monto' and f['estado'] == 'reembolsado':
            return 'Reembolsada: no cuenta en los ingresos.'
        return super().ayuda(f, c)


class ModeloCanjes(ModeloBase):
    COLUMNAS = [('fecha', 'Canjeado', 104), ('cliente', 'Cliente', 0), ('venta', 'Venta en Gumroad', 138),
                ('estado', 'Estado', 112), ('version', 'Versión', 92), ('licencia', 'Licencia', 96),
                ('equipos', 'Equipos', 66), ('clave', 'Clave', 182)]
    OCULTAR = ['clave', 'equipos', 'licencia', 'venta']
    ESTIRADA_MIN = 170

    def texto(self, f, c):
        if c == 'fecha':
            return fecha_corta(f['creado'])
        if c == 'cliente':
            return self._cliente(f)
        if c == 'venta':
            return fecha_dia(f['fecha_venta'], utc=True)
        if c == 'estado':
            return BLOQUEOS_CANJE.get(f['bloqueo'], (f['bloqueo'],))[0]
        if c == 'version':
            return self._version_texto(f)
        if c == 'clave':
            return f['clave'] or '—'
        if c == 'licencia':
            return texto_licencia(f['licencia_estado']) or '—'
        if c == 'equipos':
            return self._equipos(f)
        return ''

    def orden(self, f, c):
        if c == 'fecha':
            return f['creado'] or ''
        if c == 'cliente':
            return self._cliente(f).casefold()
        if c == 'venta':
            return f['fecha_venta'] or ''
        if c == 'estado':
            return f['bloqueo'] or ''
        if c == 'version':
            return self._version_orden(f)
        if c == 'clave':
            return f['clave'] or ''
        if c == 'licencia':
            return {'activa': 0, 'bloqueada': 1}.get(f['licencia_estado'], 3)
        if c == 'equipos':
            return f['equipos'] if f['licencia_id'] is not None else -1
        return ''

    def insignia(self, f, c):
        if c == 'estado':
            texto, color = BLOQUEOS_CANJE.get(f['bloqueo'], ((f['bloqueo'] or '').capitalize(), AVISO))
            return (texto, color, 'pastilla', None)
        if c == 'licencia':
            return self._licencia(f)
        if c == 'version':
            return self._version_insignia(f)
        return None

    def color(self, f, c):
        if c == 'cliente' and not (f['nombre'] or f['correo']):
            return TEXTO_TENUE
        if c in ('fecha', 'venta', 'clave'):
            return TEXTO_SUAVE
        if c == 'equipos':
            return self._color_equipos(f)
        return None

    def ayuda(self, f, c):
        if c == 'fecha':
            return f"Canjeado: {fecha_larga(f['creado'])}\nÚltimo canje: {fecha_larga(f['ultimo'])}"
        if c == 'venta':
            return f"Compra en Gumroad: {fecha_larga(f['fecha_venta'], utc=True)}"
        if c == 'estado' and f['bloqueo']:
            return 'Gumroad marcó esta compra así y la licencia CC- se bloqueó.'
        return super().ayuda(f, c)


def avisado_de(fila, ultima):
    """¿Ya le llegó el aviso de la última versión (o de una más nueva)? fila: un cliente o un equipo de Versiones (con
    aviso_version, el último aviso que SÍ salió)."""
    propia, nueva = partes_version((fila or {}).get('aviso_version')), partes_version(ultima)
    return propia is not None and nueva is not None and propia >= nueva


def agrupar_versiones(equipos, ultima):
    """Los equipos de la acción versiones juntos por cliente (licencia): una fila por cliente, en el orden en que llegó
    su primer equipo (el servidor manda primero el usado más recientemente). Cada cliente lleva sus equipos («filas»),
    su estado (el que importa para avisarle: «desactualizado» si ALGÚN equipo tiene una versión vieja; si no, «al día»
    si alguno manda su versión, o «sin datos» si ninguno; «desconocido» si no se sabe cuál es la última), la versión que
    se muestra (la más vieja de los atrasados o la más nueva), cuántos equipos van atrás y cuándo usó CineCaptions por
    última vez. Así lo cuenta también candidatos_aviso de admin.php."""
    clientes = {}
    for e in equipos:
        lid = e.get('licencia_id')
        if lid is None:
            continue
        c = clientes.get(lid)
        if c is None:
            c = clientes[lid] = {campo: e.get(campo) for campo in ('licencia_id', 'clave', 'cliente', 'correo', 'origen',
                                                                     'pedido_id', 'licencia_estado', 'aviso_version',
                                                                     'aviso_fecha')}
            c.update(id=lid, filas=[])
        c['filas'].append(e)
    for c in clientes.values():
        filas = c['filas']
        estados = [e.get('estado_version') or estado_de_version(e.get('version'), ultima) for e in filas]
        viejos = [e for e, s in zip(filas, estados) if s == 'desactualizado']
        con_datos = [e for e in filas if partes_version(e.get('version'))]
        if viejos:
            estado, version = 'desactualizado', min((e['version'] for e in viejos), key=partes_version)
        elif not con_datos:
            estado, version = 'sin_datos', None
        else:
            estado = 'desconocido' if 'desconocido' in estados else 'al_dia'
            version = max((e['version'] for e in con_datos), key=partes_version)
        c.update(estado=estado, version=version, equipos=len(filas), viejos=len(viejos),
                 ultima=max((e.get('ultima') or '' for e in filas), default='') or None,
                 so=[s for s in dict.fromkeys(texto_so(e.get('so')) for e in filas) if s])
    return list(clientes.values())


class ModeloVersiones(ModeloBase):
    """Un cliente por fila (agrupar_versiones): quién es, sus equipos, su versión (la más vieja si alguno va atrás), el
    aviso de la última versión («Avisar», un botón, si va atrasado y todavía no se le avisó) y cuándo usó CineCaptions
    por última vez. Así se ve de un vistazo quién va atrasado y a quién avisar: de entrada van primero los que faltan
    por avisar. Lo de cada equipo (su versión, desde cuándo, el sistema) está en el panel, al elegir la fila."""
    COLUMNAS = [('cliente', 'Cliente', 0), ('pcs', 'Equipos', 150), ('version', 'Versión', 88), ('aviso', 'Aviso', 128),
                ('uso', 'Último uso', 100)]
    OCULTAR = ['uso', 'pcs']   # (el aviso nunca se esconde: es lo que se hace en esta página)
    ESTIRADA_MIN = 170
    DOS_LINEAS = ('cliente', 'pcs')
    BOTONES = ('aviso',)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enviando = set()   # licencias con un aviso saliendo (su «Avisar» dice «Enviando…» y no se vuelve a mandar)

    def estado(self, f):
        if 'filas' in f:   # un cliente
            return f['estado']
        return f.get('estado_version') or estado_de_version(f.get('version'), self.ultima)

    def aviso(self, f):
        """La columna «Aviso»: (texto, color, forma, color del texto, ayuda). Forma 'boton': «Avisar» se aprieta ahí."""
        ultima = texto_version(self.ultima)
        estado = self.estado(f)
        avisado = avisado_de(f, ultima)
        cuando = fecha_frase(f.get('aviso_fecha'))
        if f.get('licencia_estado') != 'activa':
            return ('Bloqueada', TEXTO_TENUE, 'punto', TEXTO_TENUE,
                    'La licencia está bloqueada: CineCaptions no funciona en sus equipos y no se le avisa.')
        if f['id'] in self.enviando:
            return ('Enviando…', VIOLETA_CLARO, 'punto', TEXTO_SUAVE, 'Mandando el aviso por correo…')
        if avisado and estado != 'al_dia':
            return (f"Avisado {fecha_dia_corta(f.get('aviso_fecha'))}", VIOLETA_CLARO, 'punto', TEXTO_SUAVE,
                    f'Le avisaste de la {ultima} {cuando}. Si quieres mandárselo otra vez: clic derecho.')
        if estado == 'desactualizado' and ultima:
            if not f.get('correo'):
                return ('Sin correo', AVISO, 'punto', TEXTO_SUAVE,
                        'La licencia no tiene un correo válido: cámbialo con «Editar» en el panel para poder avisarle.')
            antes = (f" Le avisaste de la {texto_version(f['aviso_version']) or f['aviso_version']} {cuando}."
                     if f.get('aviso_version') else '')
            return ('Avisar', VIOLETA, 'boton', None,
                    f"Mándale un correo a {f['correo']} con lo nuevo de la {ultima} y el enlace para descargarla.{antes}")
        if estado == 'al_dia':
            return ('—', TEXTO_TENUE, None, None, f'No hace falta: ya tiene la {ultima}.' if ultima else None)
        if estado == 'sin_datos':
            return ('—', TEXTO_TENUE, None, None, 'No se sabe qué versión tiene: si quieres avisarle igual, elígelo y usa '
                                                  '«Avisar que actualice» en el panel.')
        return ('—', TEXTO_TENUE, None, None, None)

    def _rango_aviso(self, f):
        """Para ordenar por «Aviso»: primero los que faltan por avisar, después los avisados, sin datos, al día y al
        final las licencias bloqueadas."""
        texto, _color, forma, _c, _a = self.aviso(f)
        if forma == 'boton' or texto == 'Enviando…':
            return 6
        if texto == 'Sin correo':
            return 5
        if texto.startswith('Avisado'):
            return 4
        if texto == 'Bloqueada':
            return 0
        return {'sin_datos': 3, 'desconocido': 2, 'al_dia': 1}.get(self.estado(f), 1)

    def texto(self, f, c):
        if c == 'cliente':
            return f['cliente'] or f['correo'] or '—'
        if c == 'pcs':
            return nombre_pc(f['filas'][0]) if f['equipos'] == 1 else plural(f['equipos'], 'equipo', 'equipos')
        if c == 'version':
            return texto_version(f['version']) or 'Sin datos'
        if c == 'aviso':
            return self.aviso(f)[0]
        if c == 'uso':
            return hace(f['ultima']) if f['ultima'] else '—'
        return ''

    def segunda(self, f, c):
        if c == 'cliente' and f['cliente']:
            return f['correo']
        if c == 'pcs':
            if f['equipos'] > 1 and f['viejos']:
                return f"{f['viejos']} con una versión vieja"
            return ' · '.join(f['so']) or None
        return None

    def orden(self, f, c):
        if c == 'cliente':
            return (f['cliente'] or f['correo'] or '').casefold()
        if c == 'pcs':
            return f['equipos']
        if c == 'version':
            rango = {'desactualizado': '0', 'sin_datos': '1', 'desconocido': '2', 'al_dia': '3'}.get(self.estado(f), '4')
            return rango + orden_version(f['version'])
        if c == 'aviso':   # (de mayor a menor: los que faltan por avisar arriba y, entre ellos, el que usó hace menos)
            return f"{self._rango_aviso(f)}{f['ultima'] or ''}"
        if c == 'uso':
            return f['ultima'] or ''
        return ''

    def insignia(self, f, c):
        if c == 'version':
            color = ESTADOS_VERSION.get(self.estado(f), ESTADOS_VERSION['desconocido'])[1]
            return (self.texto(f, c), TEXTO_TENUE if f.get('licencia_estado') != 'activa' else color, 'pastilla', None)
        if c == 'aviso':
            texto, color, forma, color_texto, _ayuda = self.aviso(f)
            return (texto, color, forma, color_texto) if forma else None
        return None

    def color(self, f, c):
        if f.get('licencia_estado') != 'activa' and c in ('cliente', 'pcs'):
            return TEXTO_TENUE
        if c in ('uso', 'aviso'):
            return TEXTO_SUAVE if self.texto(f, c) != '—' else TEXTO_TENUE
        return None

    def ayuda(self, f, c):
        ultima = texto_version(self.ultima)
        if c == 'cliente':
            partes = [x for x in (f['cliente'], f['correo'], f['clave']) if x]
            if f['licencia_estado'] != 'activa':
                partes.append('Licencia bloqueada: no cuenta en los números de arriba.')
            return '\n'.join(partes) or None
        if c == 'pcs':
            return '\n'.join(f"{nombre_pc(e)} · {texto_version(e['version']) or 'sin datos'}"
                             + (f" · {texto_so(e['so'])}" if e.get('so') else '') + f" · {uso_texto(e['ultima']).lower()}"
                             for e in f['filas'])
        if c == 'version':
            estado, version = self.estado(f), texto_version(f['version'])
            if estado == 'sin_datos':
                return SIN_DATOS_VERSION
            if estado == 'desactualizado':
                varios = (f" {f['viejos']} de sus {f['equipos']} equipos con una versión vieja." if f['equipos'] > 1 else '')
                return f'Tiene la {version}; la última es la {ultima}.{varios}' if ultima else f'Versión vieja.{varios}'
            if estado == 'al_dia':
                return f'Tiene la última ({ultima}).' if ultima else 'Al día.'
            return 'No se sabe cuál es la última versión publicada.'
        if c == 'aviso':
            return self.aviso(f)[4]
        if c == 'uso' and f['ultima']:
            return f"Abrió CineCaptions por última vez: {fecha_larga(f['ultima'])}"
        return None


def equipo_de_error(e):
    """El nombre del equipo de un error (o su huella corta, si ya no está activado y no se sabe su nombre)."""
    return nombre_pc(e) if e.get('nombre_equipo') else (id_corto(e.get('equipo')) or 'Equipo sin nombre')


def una_linea(texto):
    return ' '.join(str(texto or '').split())


class ModeloErrores(ModeloBase):
    """Los errores que mandó CineCaptions desde los equipos de los clientes (la acción errores): uno por equipo y por
    fallo, con cuántas veces pasó. Los que todavía no se ven llevan el punto de color (rojo si es un error, naranja si es
    un aviso) y el título más claro."""
    COLUMNAS = [('cuando', 'Cuándo', 112), ('cliente', 'Cliente', 176), ('equipo', 'Equipo · sistema', 144),
                ('version', 'Versión', 80), ('error', 'Error', 0), ('veces', 'Veces', 64)]
    OCULTAR = ['version', 'equipo']   # (los dos están en el panel del error)
    ESTIRADA_MIN = 200
    DOS_LINEAS = ('cliente', 'equipo', 'error')

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nuevo = fuente(13, QFont.Weight.DemiBold)

    def texto(self, f, c):
        if c == 'cuando':
            return hace(f['ultima'])
        if c == 'cliente':
            return f['cliente'] or f['correo'] or '—'
        if c == 'equipo':
            return equipo_de_error(f)
        if c == 'version':
            return texto_version(f['version']) or f['version'] or '—'
        if c == 'error':
            return una_linea(f['titulo'] or f['mensaje']) or '—'
        if c == 'veces':
            return f"{f['veces']:,}"
        return ''

    def segunda(self, f, c):
        if c == 'cliente' and f['cliente']:
            return f['correo']
        if c == 'equipo':
            return texto_so(f['so'])
        if c == 'error' and f['titulo'] and f['mensaje'] and una_linea(f['mensaje']) != una_linea(f['titulo']):
            return una_linea(f['mensaje'])
        return None

    def orden(self, f, c):
        if c == 'cuando':
            return f['ultima'] or ''
        if c == 'cliente':
            return (f['cliente'] or f['correo'] or '').casefold()
        if c == 'equipo':
            return equipo_de_error(f).casefold()
        if c == 'version':
            return orden_version(f['version'])
        if c == 'error':
            return una_linea(f['titulo'] or f['mensaje']).casefold()
        if c == 'veces':
            return f'{f["veces"]:010d}'
        return ''

    def insignia(self, f, c):
        if c == 'cuando':   # el punto: de color si todavía no se ve, gris si ya
            if f['visto']:
                return (self.texto(f, c), BORDE_FUERTE, 'punto', TEXTO_TENUE)
            return (self.texto(f, c), NIVELES_ERROR[f['nivel']][1], 'punto', TEXTO)
        if c == 'version' and partes_version(f['version']) is not None:
            estado = estado_de_version(f['version'], self.ultima)
            return (self.texto(f, c), ESTADOS_VERSION.get(estado, ESTADOS_VERSION['desconocido'])[1], 'pastilla', None)
        return None

    def color(self, f, c):
        if c in ('error', 'cliente') and f['visto']:
            return TEXTO_SUAVE
        if c == 'veces':
            return TEXTO if f['veces'] > 1 and not f['visto'] else TEXTO_SUAVE
        return None

    def alineacion(self, c):
        if c == 'veces':
            return Qt.AlignmentFlag.AlignCenter
        return super().alineacion(c)

    def fuente(self, f, c):
        if c == 'error' and not f['visto']:
            return self._nuevo
        if c == 'veces':
            return self._tabular
        return None

    def ayuda(self, f, c):
        if c == 'cuando':
            partes = [f"Última vez: {fecha_larga(f['ultima'])}"]
            if f['primera'] and f['primera'] != f['ultima']:
                partes.append(f"Primera vez: {fecha_larga(f['primera'])}")
            partes.append('Ya lo viste' if f['visto'] else f"{NIVELES_ERROR[f['nivel']][0]} sin ver")
            return '\n'.join(partes)
        if c == 'cliente':
            return '\n'.join(x for x in (f['cliente'], f['correo'], f['clave']) if x) or None
        if c == 'equipo':
            return '\n'.join(x for x in (f['nombre_equipo'] and nombre_pc(f), f"ID {f['equipo']}" if f['equipo'] else None,
                                         f"Sistema: {texto_so(f['so'])}" if f['so'] else None) if x) or None
        if c == 'version' and f['version']:
            return f"CineCaptions {f['version']}"
        if c == 'error':
            return '\n'.join(x for x in (f['titulo'], f['mensaje'] if f['mensaje'] != f['titulo'] else None,
                                         f"En: {f['origen']}" if f['origen'] else None) if x) or None
        if c == 'veces':
            return f"Pasó {plural(f['veces'], 'vez', 'veces')}"
        return None


def texto_informe(e):
    """El informe de un error para pegarlo en otro lado (un correo, un chat): qué pasó, a quién, en qué equipo y versión,
    cuántas veces y, al final, el detalle técnico que mandó CineCaptions."""
    nivel = NIVELES_ERROR.get(e.get('nivel'), NIVELES_ERROR['error'])[0]
    titulo, mensaje = e.get('titulo') or '', e.get('mensaje') or ''
    cabeza = f"{nivel} de CineCaptions #{e.get('id')}"
    lineas = [f'{cabeza}: {titulo or mensaje}' if titulo or mensaje else cabeza]
    if mensaje and mensaje != titulo:
        lineas.append(mensaje)
    lineas.append('')
    veces = entero(e.get('veces'))
    for nombre, valor in (('Cliente', ' · '.join(x for x in (e.get('cliente'), e.get('correo')) if x)),
                          ('Licencia', e.get('clave')), ('Equipo', equipo_de_error(e) if e.get('equipo') else None),
                          ('ID del equipo', e.get('equipo')), ('Sistema', texto_so(e.get('so'))),
                          ('Versión', texto_version(e.get('version')) or e.get('version')), ('Dónde', e.get('origen')),
                          ('Al fallar', e.get('equipo_datos')),                              # (5.72: GPU · RAM · CPU · Pantalla)
                          ('Ficha del equipo', (e.get('ficha_equipo') or {}).get('resumen')),   # (2.4: la línea del día)
                          ('Veces', plural(veces, 'vez', 'veces') if veces else None),
                          ('Primera vez', fecha_larga(e.get('primera')) if e.get('primera') else None),
                          ('Última vez', fecha_larga(e.get('ultima')) if e.get('ultima') else None)):
        if valor:
            lineas.append(f'{nombre}: {valor}')
    detalle = (e.get('detalle') or '').strip('\n')
    if detalle:
        lineas += ['', detalle]
    return '\n'.join(lineas)


def _seccion_informe(detalle, nombre):
    """Las líneas de una sección («── DETALLE TÉCNICO ──…») del informe que manda CineCaptions, sin su cabecera ni líneas vacías
    de los bordes. [] si el informe no la trae."""
    lineas, dentro = [], False
    for linea in (detalle or '').splitlines():
        if linea.lstrip().startswith('──'):
            dentro = nombre in linea.upper()
            continue
        if dentro:
            lineas.append(linea.rstrip())
    while lineas and not lineas[-1].strip():
        lineas.pop()
    while lineas and not lineas[0].strip():
        lineas.pop(0)
    return lineas


def _nombre_corto(e):
    """«Ronniel P.»: el nombre y la inicial del apellido (el resumen va a un chat: sin correo, sin clave)."""
    partes = (e.get('cliente') or '').split()
    if not partes:
        return 'Cliente'
    return partes[0] + (f' {partes[1][0]}.' if len(partes) > 1 and partes[1] else '')


RESUMEN_MAX_DETALLES = 20   # informes técnicos que pide «Copiar resumen» (uno por fallo)


def clave_de_fallo(e):
    """El mismo fallo en varios clientes: nivel + título + mensaje, sin los números (un «KeyError: 7» y un «KeyError: 9» son uno)."""
    titulo, mensaje = una_linea(e.get('titulo') or ''), una_linea(e.get('mensaje') or '')
    return (e.get('nivel'), re.sub(r'\d+', '#', f'{titulo} | {mensaje}'.casefold())[:240])


def representantes_de_errores(errores):
    """El error más reciente de cada fallo (al que se le pide el informe técnico), en el orden del resumen."""
    grupos = {}
    for e in errores:
        grupos.setdefault(clave_de_fallo(e), []).append(e)
    orden = sorted(grupos.values(), key=lambda fs: max((f.get('ultima') or '') for f in fs), reverse=True)
    orden.sort(key=lambda fs: (len({f.get('licencia_id') for f in fs}), sum(entero(f.get('veces')) for f in fs)), reverse=True)
    return [max(fs, key=lambda f: f.get('ultima') or '') for fs in orden]


def resumen_de_errores(errores, ultima=None, filtro=None, busqueda='', ahora=None):
    """2.6 (pedido del dueño: «el reporte de todos los usuarios resumido para pegártelo, no copiar el error uno por uno»): los
    errores que se ven, en UN texto para pegar en un chat y arreglarlos a la vez. Agrupa el mismo fallo (título + mensaje, sin los
    números) de varios clientes; por fallo: clientes, equipos, veces, dónde, una línea por equipo (versión, sistema, GPU/RAM) y del
    informe solo lo útil (el «Detalle técnico» y las librerías «MAL» del último). Sin correos ni claves (va a un chat)."""
    grupos = {}
    for e in errores:
        grupos.setdefault(clave_de_fallo(e), []).append(e)
    # primero el fallo que tienen más clientes (y más veces); a igualdad, el más reciente (el mismo orden que representantes_de_errores)
    orden = sorted(grupos.values(), key=lambda fs: max((f.get('ultima') or '') for f in fs), reverse=True)
    orden.sort(key=lambda fs: (len({f.get('licencia_id') for f in fs}), sum(entero(f.get('veces')) for f in fs)), reverse=True)
    clientes = {e.get('licencia_id') for e in errores}
    sin_ver = sum(1 for e in errores if not e.get('visto'))
    cuando = (ahora or dt.datetime.now()).strftime('%d/%m/%Y %H:%M')
    filtro_txt = {'sin_ver': 'solo sin ver', 'todos': 'todos'}.get(filtro or '', filtro or '')
    cabeza = [f'RESUMEN DE ERRORES DE CINECAPTIONS · {cuando}',
              f"{plural(len(errores), 'error', 'errores')} ({sin_ver} sin ver) de {plural(len(clientes), 'cliente', 'clientes')}, "
              f"en {plural(len(orden), 'fallo distinto', 'fallos distintos')}"
              + (f' · última versión publicada: {ultima}' if ultima else '')
              + (f' · filtro: {filtro_txt}' if filtro_txt else '') + (f' · búsqueda: «{busqueda}»' if busqueda else '')]
    bloques = []
    for n, filas in enumerate(orden, 1):
        filas = sorted(filas, key=lambda f: f.get('ultima') or '', reverse=True)
        ultimo = filas[0]
        nivel = NIVELES_ERROR.get(ultimo.get('nivel'), NIVELES_ERROR['error'])[0]
        titulo, mensaje = una_linea(ultimo.get('titulo') or ''), una_linea(ultimo.get('mensaje') or '')
        veces = sum(entero(f.get('veces')) for f in filas)
        donde = sorted({f.get('origen') for f in filas if f.get('origen')})
        b = [f'{n}) {nivel} · {titulo or mensaje}']
        if mensaje and mensaje != titulo:
            b.append(f'   «{mensaje[:300]}»')
        b.append(f"   {plural(len({f.get('licencia_id') for f in filas}), 'cliente', 'clientes')} · "
                 f"{plural(len({(f.get('licencia_id'), f.get('equipo')) for f in filas}), 'equipo', 'equipos')} · "
                 f"{plural(veces, 'vez', 'veces')} · último: {hace(ultimo.get('ultima'))}"
                 + (f" · dónde: {', '.join(donde)[:120]}" if donde else ''))
        for f in filas[:12]:
            partes = [f"#{f.get('id')} {_nombre_corto(f)}", f"CineCaptions {texto_version(f.get('version')) or f.get('version') or '?'}"]
            if f.get('so'):
                partes.append(texto_so(f.get('so')))
            partes += [hace(f.get('ultima')), plural(entero(f.get('veces')), 'vez', 'veces')]
            if f.get('equipo_datos'):
                partes.append(str(f['equipo_datos'])[:170])
            if not f.get('visto'):
                partes.append('sin ver')
            b.append('   · ' + ' · '.join(p for p in partes if p))
        if len(filas) > 12:
            b.append(f'   · … y {len(filas) - 12} más')
        # del informe, el del error más reciente de este fallo que lo tenga (el botón pide el del más reciente; aquí puede haber otros)
        con_informe = next((f for f in filas if f.get('detalle')), ultimo)
        detalle = con_informe.get('detalle') or ''
        tecnico = [l for l in _seccion_informe(detalle, 'DETALLE TÉCNICO')
                   if l.strip() and 'guardado en' not in l.lower() and not l.strip().startswith('~')]
        if not tecnico and detalle:
            tecnico = [l for l in detalle.splitlines() if l.strip()][-8:]
        if tecnico and ' '.join(t.strip() for t in tecnico) != mensaje:
            b.append(f"   Detalle técnico (#{con_informe.get('id')}):")
            b += ['     ' + l.strip()[:200] for l in tecnico[-10:]]
        mal = [l.strip() for l in _seccion_informe(detalle, 'LIBRERÍAS') if l.strip().startswith('MAL')]
        if mal:
            b.append(f"   Con problemas (#{con_informe.get('id')}): " + ' | '.join(m[:160] for m in mal[:4]))
        bloques.append('\n'.join(b))
    texto = '\n'.join(cabeza) + '\n\n' + '\n\n'.join(bloques)
    return texto if len(texto) <= 30000 else texto[:29900] + '\n… (cortado: hay más; filtra por cliente o error)'


def agrupar_errores(errores):
    """Los errores de cada cliente (cada licencia), para la vista «Por usuario»: cuántos equipos, cuántos sin ver, cuántas
    veces en total y el último. Cada cliente lleva sus errores en «filas» (los mismos diccionarios de la tabla)."""
    clientes = {}
    for e in errores:
        c = clientes.get(e['licencia_id'])
        if c is None:
            c = clientes[e['licencia_id']] = {'id': e['licencia_id'], 'licencia_id': e['licencia_id'], 'cliente': e['cliente'],
                                              'correo': e['correo'], 'clave': e['clave'], 'filas': []}
        c['filas'].append(e)
    for c in clientes.values():
        filas = c['filas']
        ultimo = max(filas, key=lambda e: e['ultima'] or '')
        c.update(equipos=len({e['equipo'] for e in filas}), errores=len(filas), sin_ver=sum(1 for e in filas if not e['visto']),
                 veces=sum(e['veces'] for e in filas), ultima=ultimo['ultima'],
                 ultimo_titulo=una_linea(ultimo['titulo'] or ultimo['mensaje']))
    return list(clientes.values())


class ModeloClientesErrores(ModeloBase):
    """La lista de la vista «Por usuario»: un cliente por fila, con cuántos equipos, cuántas veces en total, cuántos
    errores sin ver (la pastilla roja) y el último. Los que tienen errores sin ver van arriba."""
    COLUMNAS = [('cliente', 'Cliente', 0), ('sin_ver', 'Sin ver', 64), ('ultimo', 'Último error', 112)]
    OCULTAR = ['ultimo']   # (en una ventana angosta; su error y cuándo siguen a la par, en los errores del cliente)
    ESTIRADA_MIN = 128
    DOS_LINEAS = ('cliente', 'ultimo')

    def texto(self, f, c):
        if c == 'cliente':
            return f['cliente'] or f['correo'] or f"Licencia #{f['licencia_id']}"
        if c == 'sin_ver':
            return f"{f['sin_ver']:,}" if f['sin_ver'] else '—'
        if c == 'ultimo':
            return hace(f['ultima'])
        return ''

    def segunda(self, f, c):
        if c == 'cliente':
            return f"{plural(f['equipos'], 'equipo', 'equipos')} · {plural(f['veces'], 'vez', 'veces')}"
        if c == 'ultimo':
            return f['ultimo_titulo'] or None
        return None

    def orden(self, f, c):
        if c == 'cliente':
            return self.texto(f, c).casefold()
        if c == 'sin_ver':
            return f"{f['sin_ver']:06d}{f['ultima'] or ''}"
        if c == 'ultimo':   # (los que tienen errores sin ver primero y, entre ellos, el más reciente)
            return ('1' if f['sin_ver'] else '0') + (f['ultima'] or '')
        return ''

    def insignia(self, f, c):
        if c == 'sin_ver' and f['sin_ver']:
            return (self.texto(f, c), PELIGRO, 'pastilla', None)
        return None

    def color(self, f, c):
        if c == 'cliente' and not f['sin_ver']:
            return TEXTO_SUAVE
        if c == 'ultimo':
            return TEXTO_SUAVE
        return None

    def fuente(self, f, c):
        return self._dato if c == 'ultimo' else None

    def ayuda(self, f, c):
        if c == 'cliente':
            return '\n'.join(x for x in (f['cliente'], f['correo'], f['clave']) if x) or None
        if c == 'sin_ver':
            return (f"{plural(f['sin_ver'], 'error sin ver', 'errores sin ver')} de {plural(f['errores'], 'error', 'errores')}"
                    if f['sin_ver'] else 'Ya viste su error' if f['errores'] == 1 else f"Ya viste sus {f['errores']:,} errores")
        if c == 'ultimo':
            return f"{f['ultimo_titulo']}\n{fecha_larga(f['ultima'])}"
        return None


class ModeloAvisos(ModeloBase):
    """Los correos de actualización (la acción avisos): cada intento, aunque no saliera."""
    COLUMNAS = [('fecha', 'Fecha', 112), ('cliente', 'Cliente', 0), ('version', 'Versión', 86), ('resultado', 'Resultado', 146)]
    ESTIRADA_MIN = 180

    def _resultado(self, f):
        if f['ok']:
            return MOTIVOS_AVISO[None]
        return MOTIVOS_AVISO.get(f['motivo'], ('No se envió', PELIGRO))

    def texto(self, f, c):
        if c == 'fecha':
            return fecha_corta(f['enviado'])
        if c == 'cliente':
            return f['cliente'] or f['correo'] or '—'
        if c == 'version':
            return texto_version(f['version']) or f['version'] or '—'
        if c == 'resultado':
            return self._resultado(f)[0]
        return ''

    def segunda(self, f, c):
        return f['correo'] if c == 'cliente' and f['cliente'] else None

    def orden(self, f, c):
        if c == 'fecha':
            return f['enviado'] or ''
        if c == 'cliente':
            return (f['cliente'] or f['correo'] or '').casefold()
        if c == 'version':
            return orden_version(f['version'])
        if c == 'resultado':
            return ('0' if f['ok'] else '1') + (f['motivo'] or '')
        return ''

    def insignia(self, f, c):
        if c == 'resultado':
            texto, color = self._resultado(f)
            return (texto, color, 'pastilla', None)
        return None

    def color(self, f, c):
        return TEXTO_SUAVE if c in ('fecha', 'version') else None

    def ayuda(self, f, c):
        if c == 'fecha':
            return fecha_larga(f['enviado'])
        if c == 'resultado':
            return f"Le llegó a {f['correo']}." if f['ok'] and f['correo'] else EXPLICA_MOTIVO.get(f['motivo'])
        if c == 'cliente':
            return '\n'.join(x for x in (f['cliente'], f['correo']) if x) or None
        return None


def fecha_cupon(texto):
    """«2026-12-31» (el último día en que sirve un cupón, en hora de Guatemala) → «31 dic 2026», o None."""
    try:
        d = dt.date.fromisoformat(str(texto or '')[:10])
    except ValueError:
        return None
    return f'{d.day} {MESES[d.month - 1]} {d.year}'


class ModeloCupones(ModeloBase):
    """2.8: los cupones de descuento (la acción cupones): el código con su nota debajo, el descuento, en cuánto queda la
    licencia, los usos (ventas pagadas con él), lo que dejó, hasta cuándo sirve y su estado."""
    COLUMNAS = [('codigo', 'Cupón', 0), ('descuento', 'Descuento', 96), ('monto', 'Queda en', 118),
                ('usos', 'Usos', 92), ('ingresos', 'Ingresos', 116), ('vence', 'Vence', 116), ('estado', 'Estado', 104)]
    OCULTAR = ['ingresos', 'vence', 'monto']
    ESTIRADA_MIN = 170
    DOS_LINEAS = ('codigo',)
    ORDEN_ESTADO = {'activo': 0, 'agotado': 1, 'vencido': 2, 'pausado': 3}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.moneda = 'USD'
        self._codigo = fuente(13, QFont.Weight.DemiBold, mono=True)

    def texto(self, f, c):
        if c == 'codigo':
            return f['codigo'] or '—'
        if c == 'descuento':
            return texto_descuento(f['porcentaje'])
        if c == 'monto':
            return dinero(f['precio_final'], self.moneda) if f['precio_final'] is not None else '—'
        if c == 'usos':
            return texto_usos(f)
        if c == 'ingresos':
            return dinero(f['ingresos'], self.moneda) if f['usos'] else '—'
        if c == 'vence':
            return fecha_cupon(f['vence']) or 'No vence'
        if c == 'estado':
            return ESTADOS_CUPON[f['estado']][0]
        return ''

    def segunda(self, f, c):
        return f['nota'] if c == 'codigo' and f.get('nota') else None

    def orden(self, f, c):
        if c == 'codigo':
            return f['codigo'] or ''
        if c == 'descuento':
            return f['porcentaje']
        if c == 'monto':
            return f['precio_final'] if f['precio_final'] is not None else -1
        if c == 'usos':
            return f['usos']
        if c == 'ingresos':
            return f['ingresos']
        if c == 'vence':
            return f['vence'] or '9999'
        if c == 'estado':
            return self.ORDEN_ESTADO.get(f['estado'], 4)
        return ''

    def insignia(self, f, c):
        if c == 'estado':
            texto, color = ESTADOS_CUPON[f['estado']]
            return (texto, color, 'pastilla', None)
        return None

    def alineacion(self, c):
        if c in ('ingresos', 'usos'):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return super().alineacion(c)

    def color(self, f, c):
        if f['estado'] != 'activo' and c != 'estado':
            return TEXTO_TENUE if c != 'codigo' else TEXTO_SUAVE   # (el que no sirve se ve apagado)
        if c == 'descuento':
            return VIOLETA_CLARO
        if c in ('vence', 'ingresos'):
            return TEXTO_SUAVE if (f['vence'] if c == 'vence' else f['usos']) else TEXTO_TENUE
        if c == 'usos':
            return AVISO if f.get('usos_max') and f['usos'] >= f['usos_max'] else TEXTO if f['usos'] else TEXTO_TENUE
        return None

    def fuente(self, f, c):
        if c == 'codigo':
            return self._codigo
        if c in ('usos', 'ingresos', 'monto', 'descuento'):
            return self._tabular
        if c == 'vence':
            return self._dato
        return None

    def ayuda(self, f, c):
        if c == 'codigo':
            return '\n'.join(x for x in (f['enlace'], f['nota']) if x) or None
        if c == 'monto':
            return ('Licencia gratis: el cliente deja su nombre y correo y recibe la clave sin pagar.'
                    if f['porcentaje'] >= 100 else 'Lo que paga el cliente con este cupón, con el precio de ahora.')
        if c == 'usos':
            tope = (f"Tope: {plural(f['usos_max'], 'uso', 'usos')}." if f.get('usos_max') else 'Sin tope de usos.')
            ultima = f"\nÚltima venta: {fecha_larga(f['ultima_venta'])}" if f.get('ultima_venta') else ''
            return f"{plural(f['usos'], 'venta pagada', 'ventas pagadas')} con este cupón. {tope}{ultima}"
        if c == 'ingresos' and f['usos']:
            return f"Ingresos: {dinero(f['ingresos'], self.moneda)} · se descontó {dinero(f['descontado'], self.moneda)}"
        if c == 'vence':
            return (f"Sirve hasta el {fecha_cupon(f['vence'])} (hora de Guatemala)." if f['vence']
                    else 'No tiene fecha de vencimiento.')
        if c == 'estado':
            return {'activo': 'Se puede usar en la web.', 'pausado': 'Pausado: no se puede usar hasta que lo actives.',
                    'vencido': 'Ya pasó su fecha: no se puede usar.',
                    'agotado': 'Llegó a su tope de usos: no se puede usar.'}.get(f['estado'])
        return None


class Orden(QSortFilterProxyModel):
    """Ordena por el valor «crudo» de cada columna (fechas ISO, centavos...), no por el texto que se ve. Con poner_filtro
    deja ver solo las filas que cumplen algo (los filtros rápidos: «Hoy», «Desactualizados»...)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(ROL_ORDEN)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.filtro = None

    def poner_filtro(self, funcion):
        self.filtro = funcion
        self.invalidate()

    def filterAcceptsRow(self, fila, padre):
        if self.filtro is None:
            return True
        datos = self.sourceModel().fila(fila)
        return datos is not None and bool(self.filtro(datos))


# ---------------------------------------------------------------- Diálogos

def carpeta_claves():
    return Path.home() / 'CineCaptions_claves'


class DialogoClave(QDialog):
    """Pide la clave de administrador (campo de contraseña). También la puede leer de un archivo .txt."""

    def __init__(self, parent=None, primera_vez=True):
        super().__init__(parent)
        self.setWindowTitle('Clave de administrador')
        self.setModal(True)
        self.setMinimumWidth(500)
        lay = QVBoxLayout(self)
        margenes_dialogo(lay)
        cabeza_dialogo(lay, 'llave', 'Pega tu clave de administrador' if primera_vez else 'Cambiar la clave de administrador')
        texto = etiqueta('Con esta clave la app lee tus ventas en cinecaptions.shop. Se guarda cifrada en esta PC: '
                         'solo tu usuario de Windows puede leerla.', 'suave')
        texto.setWordWrap(True)
        lay.addWidget(texto)
        lay.addSpacing(4)
        fila = QHBoxLayout()
        fila.setSpacing(8)
        self.campo = QLineEdit()
        self.campo.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo.setPlaceholderText('Clave de administrador')
        self.campo.setMinimumHeight(36)
        self._ver = self.campo.addAction(icono('ojo', TEXTO_TENUE, 18), QLineEdit.ActionPosition.TrailingPosition)
        self._ver.setToolTip('Mostrar u ocultar la clave')
        self._ver.triggered.connect(self._alternar)
        self.campo.textChanged.connect(lambda _t: self.error.hide())
        fila.addWidget(self.campo, 1)
        self.btn_archivo = boton('Abrir archivo…', 'carpeta')
        self.btn_archivo.setMinimumHeight(36)
        self.btn_archivo.clicked.connect(self._abrir_archivo)
        fila.addWidget(self.btn_archivo)
        lay.addLayout(fila)
        self.nota = boton(NOTA_CLAVE, 'info', tipo='enlace', color_icono=VIOLETA_CLARO)
        self.nota.setToolTip(f'Abrir la carpeta {carpeta_claves()}')
        self.nota.clicked.connect(self._abrir_carpeta)
        lay.addWidget(self.nota, 0, Qt.AlignmentFlag.AlignLeft)
        self.error = etiqueta('', 'error')
        self.error.setWordWrap(True)
        self.error.hide()
        lay.addWidget(self.error)
        lay.addSpacing(8)
        cancelar = boton('Cancelar')
        guardar = boton('Guardar clave', 'ok', tipo='primario')
        guardar.setDefault(True)
        cancelar.clicked.connect(self.reject)
        guardar.clicked.connect(self.accept)
        lay.addLayout(fila_botones(cancelar, guardar))

    def clave(self):
        return self.campo.text().strip()

    def _alternar(self):
        normal = self.campo.echoMode() == QLineEdit.EchoMode.Normal
        self.campo.setEchoMode(QLineEdit.EchoMode.Password if normal else QLineEdit.EchoMode.Normal)

    def _abrir_carpeta(self):
        if carpeta_claves().is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(carpeta_claves())))
        else:
            self._abrir_archivo()

    def _abrir_archivo(self):
        inicio = carpeta_claves() if carpeta_claves().is_dir() else Path.home()
        ruta, _ = QFileDialog.getOpenFileName(self, 'Elige el archivo con la clave', str(inicio),
                                              'Texto (*.txt);;Todos los archivos (*)')
        if not ruta:
            return
        try:
            self.campo.setText(extraer_clave(leer_texto(ruta)))
            self.error.hide()
        except (OSError, ValueError) as e:
            self.error.setText(f'No se pudo leer la clave de ese archivo: {e}')
            self.error.show()

    def accept(self):
        problema = problema_clave(self.clave())
        if problema:
            self.error.setText(problema)
            self.error.show()
            self.campo.setFocus()
            return
        super().accept()


class DialogoApi(QDialog):
    """Cambia la dirección de la API (por ejemplo, para usar un servidor de prueba)."""

    def __init__(self, parent, actual):
        super().__init__(parent)
        self.setWindowTitle('Dirección de la API')
        self.setModal(True)
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        margenes_dialogo(lay)
        cabeza_dialogo(lay, 'ajustes', 'Dirección de la API de ventas')
        texto = etiqueta('Normalmente es la del sitio. Solo cámbiala para probar con otro servidor.', 'suave')
        texto.setWordWrap(True)
        lay.addWidget(texto)
        self.campo = QLineEdit(actual)
        self.campo.setMinimumHeight(36)
        self.campo.setPlaceholderText(API_POR_DEFECTO)
        lay.addWidget(self.campo)
        self.error = etiqueta('', 'error')
        self.error.setWordWrap(True)
        self.error.hide()
        lay.addWidget(self.error)
        lay.addSpacing(8)
        restablecer = boton('Usar la del sitio', 'actualizar')
        restablecer.clicked.connect(lambda: self.campo.setText(API_POR_DEFECTO))
        cancelar = boton('Cancelar')
        guardar = boton('Guardar', 'ok', tipo='primario')
        guardar.setDefault(True)
        cancelar.clicked.connect(self.reject)
        guardar.clicked.connect(self.accept)
        lay.addLayout(fila_botones(cancelar, guardar, izquierda=(restablecer,)))
        self._url = actual

    def url(self):
        return self._url

    def accept(self):
        try:
            self._url = validar_api(self.campo.text())
        except ValueError as e:
            self.error.setText(str(e))
            self.error.show()
            return
        super().accept()


def html_texto(texto):
    """Texto plano a HTML: escapado, con sus saltos de línea y sin cortar una clave CC- a la mitad."""
    seguro = html.escape(texto).replace('\n', '<br>')
    return re.sub(r'CC(?:-[A-Z0-9]{4}){4}', lambda m: m.group(0).replace('-', '‑'), seguro)


TONOS = {'marca': VIOLETA_CLARO, 'aviso': AVISO, 'peligro': PELIGRO, 'tenue': TEXTO_SUAVE}


def cuadro_icono(nombre_icono, tono='marca', lado=40):
    """El ícono de un diálogo dentro de un cuadro redondeado, teñido con el color de su tono."""
    ic = QLabel()
    ic.setObjectName('iconoCaja')
    ic.setProperty('tono', tono)
    ic.setPixmap(pintar_icono(nombre_icono, TONOS.get(tono, VIOLETA_CLARO), 20))
    ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ic.setFixedSize(lado, lado)
    return ic


def margenes_dialogo(lay):
    """Los mismos márgenes y espacios en todos los diálogos."""
    lay.setContentsMargins(24, 24, 24, 20)
    lay.setSpacing(12)


def cabeza_dialogo(lay, nombre_icono, titulo, tono='marca'):
    """El ícono en su cuadro y el título grande, centrados entre sí, arriba de un diálogo. Devuelve la etiqueta del
    título."""
    cabeza = QHBoxLayout()
    cabeza.setSpacing(14)
    cabeza.addWidget(cuadro_icono(nombre_icono, tono))
    lbl = etiqueta(titulo, 'dialogoTitulo')   # (corto y en una línea: así la cabeza mide lo mismo que el ícono)
    cabeza.addWidget(lbl, 1)
    lay.addLayout(cabeza)
    return lbl


def fila_botones(*botones, izquierda=()):
    """Los botones de abajo de un diálogo, a la derecha y en el orden de siempre: «Cancelar» primero y la acción al
    final. izquierda: los que van del otro lado (como «Usar la del sitio»)."""
    fila = QHBoxLayout()
    fila.setSpacing(8)
    for b in izquierda:
        fila.addWidget(b)
    fila.addStretch(1)
    for b in botones:
        b.setMinimumWidth(max(b.minimumWidth(), 96))
        fila.addWidget(b)
    return fila


class Caja(QDialog):
    """La ventanita de confirmación o de aviso, con el estilo de los demás diálogos: el ícono en su cuadro con la
    pregunta, la explicación abajo y los botones a la derecha («Cancelar» primero y la acción al final). Reemplaza a
    QMessageBox, que cambia el orden de los botones según Windows y no alinea su ícono con el texto. clickedButton()
    dice qué botón se apretó (None si se cerró con Escape o con la X)."""

    def __init__(self, parent, titulo, texto, nombre_icono='info', tono='marca'):
        super().__init__(parent)
        self.setWindowTitle(APP)
        self.setModal(True)
        self.setFixedWidth(480)   # (con el ancho fijo, el título y la explicación largos saben dónde cortar)
        self._apretado = None
        self.casilla = None       # la casilla de agregar_casilla() (por ejemplo, «Bloquear también su licencia»)
        lay = QVBoxLayout(self)
        self._lay = lay
        margenes_dialogo(lay)
        # (como un aviso: la explicación va justo debajo del título, con su mismo margen, y el ícono a la izquierda)
        fila = QHBoxLayout()
        fila.setSpacing(14)
        fila.addWidget(cuadro_icono(nombre_icono, tono), 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(4)
        self.titulo = etiqueta(titulo, 'dialogoTitulo')
        self.titulo.setWordWrap(True)
        self.titulo.setMinimumHeight(40)   # (una línea queda centrada con el ícono)
        self.texto = etiqueta('', 'suave', plano=False)
        self.texto.setTextFormat(Qt.TextFormat.RichText)
        self.texto.setText(html_texto(texto or ''))
        self.texto.setWordWrap(True)
        self.texto.setVisible(bool(texto))
        col.addWidget(self.titulo)
        col.addWidget(self.texto)
        fila.addLayout(col, 1)
        lay.addLayout(fila)
        lay.addSpacing(12)
        # Con el ancho fijo se sabe cuánto miden el título y la explicación ya cortados en líneas. (Si no, Qt calcula el
        # alto mínimo de un texto que se corta como si fuera angostísimo: la caja salía más alta y con huecos.)
        ancho = self.width() - 48 - 40 - 14   # (los márgenes, el ícono y el espacio después del ícono)
        for lbl in (self.titulo, self.texto):
            lbl.ensurePolished()
        self.titulo.setFixedHeight(max(40, self.titulo.heightForWidth(ancho)))
        if texto:
            self.texto.setFixedHeight(self.texto.heightForWidth(ancho))
        self._botones = QHBoxLayout()
        self._botones.setSpacing(8)
        self._botones.addStretch(1)
        lay.addLayout(self._botones)

    def agregar(self, texto, tipo=None, acepta=False):
        b = boton(texto, tipo=tipo)
        b.setMinimumWidth(96)
        b.clicked.connect(lambda: self._apretar(b, acepta))
        self._botones.addWidget(b)
        return b

    def agregar_casilla(self, texto):
        """Una casilla desmarcada debajo de la explicación, con su mismo margen (su texto puede ocupar dos líneas).
        Devuelve la casilla (CasillaLarga: isChecked() dice si la marcaron)."""
        self.casilla = CasillaLarga(texto)
        fila = QHBoxLayout()
        fila.setContentsMargins(40 + 14, 2, 0, 0)   # (el ícono y su espacio: queda alineada con la explicación)
        fila.addWidget(self.casilla, 1)
        self._lay.insertLayout(1, fila)
        self.casilla.fijar_ancho(self.width() - 48 - 40 - 14)
        return self.casilla

    def _apretar(self, b, acepta):
        self._apretado = b
        if acepta:
            self.accept()
        else:
            self.reject()

    def clickedButton(self):
        return self._apretado


class CasillaLarga(QWidget):
    """Una casilla con un texto que puede ocupar varias líneas (el texto de un QCheckBox no se corta: en una caja de
    ancho fijo se salía). Hacerle clic al texto también la marca o la desmarca."""

    def __init__(self, texto):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.caja = QCheckBox()
        self.caja.setCursor(Qt.CursorShape.PointingHandCursor)
        self.texto = etiqueta(texto, 'suave')
        self.texto.setWordWrap(True)
        self.texto.setCursor(Qt.CursorShape.PointingHandCursor)
        self.texto.installEventFilter(self)
        lay.addWidget(self.caja, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self.texto, 1)

    def eventFilter(self, objeto, evento):
        if (objeto is self.texto and evento.type() == QEvent.Type.MouseButtonRelease
                and evento.button() == Qt.MouseButton.LeftButton and self.caja.isEnabled()):
            self.caja.toggle()
            return True
        return False

    def fijar_ancho(self, ancho):
        """Del alto justo de su texto cortado en ese ancho (ver Caja: Qt lo calcula como si fuera angostísimo)."""
        self.texto.ensurePolished()
        self.texto.setFixedHeight(self.texto.heightForWidth(max(40, ancho - 16 - 8)))

    def isChecked(self):
        return self.caja.isChecked()

    def setChecked(self, valor):
        self.caja.setChecked(valor)


def caja_confirmacion(parent, pregunta, explicacion, texto_boton, peligro=True, nombre_icono='aviso', casilla=None):
    """Arma (sin mostrar) la ventanita de confirmación. Devuelve (caja, botón de aceptar). Enter aprieta «Cancelar».
    casilla: el texto de una casilla desmarcada debajo de la explicación (queda en caja.casilla)."""
    caja = Caja(parent, pregunta, explicacion, nombre_icono, 'aviso' if peligro else 'marca')
    if casilla:
        caja.agregar_casilla(casilla)
    no = caja.agregar('Cancelar')
    si = caja.agregar(texto_boton, 'peligro' if peligro else 'primario', acepta=True)
    no.setDefault(True)
    return caja, si


def confirmar(parent, pregunta, explicacion, texto_boton, peligro=True, nombre_icono='aviso'):
    caja, si = caja_confirmacion(parent, pregunta, explicacion, texto_boton, peligro, nombre_icono)
    caja.exec()
    return caja.clickedButton() is si


def mensaje(parent, titulo, texto, tipo='error'):
    nombre_icono, tono = {'error': ('aviso', 'peligro'), 'info': ('info', 'marca')}.get(tipo, ('ok', 'marca'))
    caja = Caja(parent, titulo, texto, nombre_icono, tono)
    caja.agregar('Entendido', 'primario', acepta=True).setDefault(True)
    caja.exec()


class DialogoAcerca(QDialog):
    """«Acerca de»: la versión, la carpeta desde donde corre la app (la de la instalación, con el .exe; «Abrir carpeta»
    la abre en el Explorador) y la de la configuración. Del alto justo de lo que tiene (ver el final de __init__)."""
    ANCHO = 520

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'Acerca de {APP}')
        self.setModal(True)
        lay = QVBoxLayout(self)
        margenes_dialogo(lay)
        cabeza = QHBoxLayout()
        cabeza.setSpacing(14)
        logo = QLabel()
        logo.setPixmap(pixmap_logo(48))
        logo.setFixedSize(48, 48)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addStretch(1)
        col.addWidget(etiqueta(APP, 'dialogoTitulo'))
        self.version = etiqueta(f'Versión {VERSION}', 'suave')
        col.addWidget(self.version)
        col.addStretch(1)
        cabeza.addWidget(logo)
        cabeza.addLayout(col, 1)
        lay.addLayout(cabeza)
        lay.addSpacing(4)
        texto = etiqueta('Ventas de Recurrente, canjes de Gumroad, licencias, versiones de CineCaptions y los errores que '
                         'les salen a tus clientes. Nuevo en la 2.4: la ficha técnica de cada equipo (sistema, procesador, '
                         'memoria, tarjeta gráfica y su driver, discos, Resolve, motores y lo que revisó CineCaptions), en '
                         'el error y en «Ficha» de los equipos de la licencia.', 'suave')
        texto.setWordWrap(True)
        lay.addWidget(texto)
        caja = QFrame()
        caja.setObjectName('caja')
        lc = QVBoxLayout(caja)
        lc.setContentsMargins(16, 14, 16, 14)
        self.carpeta = carpeta_programa()
        self.ficha = Ficha()
        # (las rutas se cortan después de cada «\»: un nombre largo nunca se sale de la caja. Por el espacio invisible
        # no se seleccionan; «Abrir carpeta» abre la de la app)
        self.ficha.poner([('Instalada en' if instalada() else 'Corre desde', ruta_partible(self.carpeta), None),
                          ('Configuración', ruta_partible(carpeta_config()), None)], seleccionable=False)
        lc.addWidget(self.ficha)
        lay.addWidget(caja)
        if instalada():
            nota = etiqueta('Para desinstalarla: Configuración de Windows › Aplicaciones › Aplicaciones instaladas.',
                            'tenue')
            nota.setWordWrap(True)
            lay.addWidget(nota)
        lay.addSpacing(8)
        abrir = boton('Abrir carpeta', 'carpeta')
        abrir.setToolTip(f'Abrir {self.carpeta}')
        abrir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.carpeta))))
        cerrar = boton('Cerrar', tipo='primario')
        cerrar.setDefault(True)
        cerrar.clicked.connect(self.accept)
        lay.addLayout(fila_botones(cerrar, izquierda=(abrir,)))
        # Del ancho fijo y del alto justo de lo que tiene. (Si no, Qt calcula el alto mínimo de las rutas que se cortan
        # en varias líneas como si fueran angostísimas y el diálogo salía más alto, con un hueco arriba del logo.)
        self.ensurePolished()
        self.setFixedSize(self.ANCHO, lay.totalHeightForWidth(self.ANCHO))


class DialogoCliente(QDialog):
    """Cambia el nombre y el correo de una licencia (admin.php también los cambia en sus compras). Revisa el correo
    antes de mandarlo; cambios() da solo lo que cambió."""

    def __init__(self, parent, nombre, correo):
        super().__init__(parent)
        self.setWindowTitle('Editar cliente')
        self.setModal(True)
        self.setMinimumWidth(500)
        self._original = (nombre or '', correo or '')
        lay = QVBoxLayout(self)
        margenes_dialogo(lay)
        cabeza_dialogo(lay, 'usuario', 'Editar datos del cliente')
        texto = etiqueta('Cambia el nombre y el correo de la licencia y de sus compras. La clave y los avisos de '
                         'actualización se mandan al correo nuevo.', 'suave')
        texto.setWordWrap(True)
        lay.addWidget(texto)
        lay.addSpacing(4)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        self.nombre = QLineEdit(nombre or '')
        self.nombre.setMaxLength(MAX_NOMBRE)
        self.nombre.setPlaceholderText('Nombre del cliente')
        self.correo = QLineEdit(correo or '')
        self.correo.setMaxLength(MAX_NOMBRE)
        self.correo.setPlaceholderText('nombre@gmail.com')
        for n, (titulo, campo) in enumerate((('Nombre', self.nombre), ('Correo', self.correo))):
            campo.setMinimumHeight(36)
            campo.textChanged.connect(lambda _t: self.error.hide())
            grid.addWidget(etiqueta(titulo, 'suave'), n, 0)
            grid.addWidget(campo, n, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        self.error = etiqueta('', 'error')
        self.error.setWordWrap(True)
        self.error.hide()
        lay.addWidget(self.error)
        lay.addSpacing(8)
        cancelar = boton('Cancelar')
        guardar = boton('Guardar cambios', 'ok', tipo='primario')
        guardar.setDefault(True)
        cancelar.clicked.connect(self.reject)
        guardar.clicked.connect(self.accept)
        lay.addLayout(fila_botones(cancelar, guardar))

    def cambios(self):
        nombre, correo = ' '.join(self.nombre.text().split()), self.correo.text().strip()
        cambios = {}
        if nombre != ' '.join(self._original[0].split()):
            cambios['nombre'] = nombre
        if correo != self._original[1].strip():
            cambios['correo'] = correo
        return cambios

    def _problema(self):
        cambios = self.cambios()
        if 'correo' in cambios and not correo_valido(cambios['correo']):   # (el correo que no cambia ni se manda)
            return 'Escribe un correo válido, por ejemplo nombre@gmail.com.', self.correo
        if not cambios:
            return 'No cambiaste nada.', self.nombre
        return None, None

    def accept(self):
        problema, campo = self._problema()
        if problema:
            self.error.setText(problema)
            self.error.show()
            campo.setFocus()
            return
        super().accept()


class DialogoCupon(QDialog):
    """2.8: «Nuevo cupón» o «Editar cupón»: el código (solo al crearlo), el descuento (1 a 100 %), el tope de usos (vacío:
    sin tope), hasta qué día sirve, una nota y si está activo. Dice en vivo en cuánto queda la licencia con el precio de
    ahora y avisa si un cupón del 100 % no tiene tope. datos() da todo (para crear); cambios(), solo lo que cambió.
    En «Editar», «Borrar cupón» cierra el diálogo con quiere_borrar = True."""

    def __init__(self, parent, cupon=None, precio=None, moneda='USD', hoy=None):
        super().__init__(parent)
        self.cupon, self.precio, self.moneda = cupon, precio, moneda
        self.quiere_borrar = False
        nuevo = cupon is None
        self.setWindowTitle('Nuevo cupón' if nuevo else 'Editar cupón')
        self.setModal(True)
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        margenes_dialogo(lay)
        cabeza_dialogo(lay, 'cupon', 'Nuevo cupón de descuento' if nuevo else f"Cupón {cupon['codigo']}")
        ahora = f' (hoy cuesta {dinero(precio, moneda)})' if precio else ''
        texto = etiqueta(f'El cliente lo escribe en la tarjeta de precio de cinecaptions.shop o abre su enlace, y paga '
                         f'menos en Recurrente{ahora}. Con el 100 % la licencia sale gratis, sin pagar. La fecha de '
                         'vencimiento va en hora de Guatemala.' if nuevo else
                         'Los cambios valen para las compras que vienen; las ventas que ya se hicieron no cambian.', 'suave')
        texto.setWordWrap(True)
        lay.addWidget(texto)
        lay.addSpacing(4)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        fila = 0
        self.codigo = QLineEdit(cupon['codigo'] if cupon else '')
        self.codigo.setMaxLength(32)
        self.codigo.setPlaceholderText('Por ejemplo: NAVIDAD20')
        self.codigo.setFont(fuente(13, QFont.Weight.DemiBold, mono=True))
        self.codigo.textEdited.connect(self._mayusculas)
        self.codigo.setEnabled(nuevo)   # (el código no se cambia: sus enlaces ya pueden estar compartidos)
        grid.addWidget(etiqueta('Código', 'suave'), fila, 0)
        grid.addWidget(self.codigo, fila, 1)
        fila += 1
        self.porcentaje = QLineEdit(str(cupon['porcentaje']) if cupon else '20')
        self.porcentaje.setValidator(QIntValidator(1, 100, self))
        self.porcentaje.setMaxLength(3)
        self.porcentaje.setFixedWidth(90)
        self.porcentaje.textChanged.connect(lambda _t: self._poner_precio())
        caja = QHBoxLayout()
        caja.setSpacing(10)
        caja.addWidget(self.porcentaje)
        caja.addWidget(etiqueta('%', 'suave'))
        self.lbl_precio = etiqueta('', 'suave')
        caja.addWidget(self.lbl_precio, 1)
        grid.addWidget(etiqueta('Descuento', 'suave'), fila, 0)
        grid.addLayout(caja, fila, 1)
        fila += 1
        self.usos = QLineEdit(str(cupon['usos_max']) if cupon and cupon.get('usos_max') else '')
        self.usos.setValidator(QIntValidator(1, 1000000, self))
        self.usos.setPlaceholderText('Sin tope')
        self.usos.setFixedWidth(90)
        self.usos.textChanged.connect(lambda _t: self._poner_precio())
        caja = QHBoxLayout()
        caja.setSpacing(10)
        caja.addWidget(self.usos)
        usados = f" · ya se usó {plural(cupon['usos'], 'vez', 'veces')}" if cupon and cupon.get('usos') else ''
        caja.addWidget(etiqueta(f'ventas como máximo (vacío: sin tope){usados}', 'suave'), 1)
        grid.addWidget(etiqueta('Tope de usos', 'suave'), fila, 0)
        grid.addLayout(caja, fila, 1)
        fila += 1
        try:
            base = dt.date.fromisoformat(str(hoy or '')[:10])
        except ValueError:
            base = Reloj.ahora().date()
        vence = None
        if cupon and cupon.get('vence'):
            try:
                vence = dt.date.fromisoformat(cupon['vence'])
            except ValueError:
                vence = None
        self.con_vence = QCheckBox('Vence el')
        self.con_vence.setChecked(vence is not None)
        self.fecha = QDateEdit()
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat('dd/MM/yyyy')
        self.fecha.setMinimumDate(QDate(base.year, base.month, base.day) if nuevo else QDate(2020, 1, 1))
        d = vence or (base + dt.timedelta(days=30))
        self.fecha.setDate(QDate(d.year, d.month, d.day))
        self.fecha.setEnabled(vence is not None)
        self.fecha.setMinimumWidth(150)
        self.con_vence.toggled.connect(self.fecha.setEnabled)
        caja = QHBoxLayout()
        caja.setSpacing(10)
        caja.addWidget(self.con_vence)
        caja.addWidget(self.fecha)
        caja.addWidget(etiqueta('(ese día incluido)', 'suave'), 1)
        grid.addWidget(etiqueta('Fecha', 'suave'), fila, 0)
        grid.addLayout(caja, fila, 1)
        fila += 1
        self.nota = QLineEdit(cupon.get('nota') or '' if cupon else '')
        self.nota.setMaxLength(190)
        self.nota.setPlaceholderText('Para qué es (solo la ves tú)')
        grid.addWidget(etiqueta('Nota', 'suave'), fila, 0)
        grid.addWidget(self.nota, fila, 1)
        fila += 1
        self.activo = QCheckBox('Activo: se puede usar en la web')
        self.activo.setChecked(cupon['activo'] if cupon else True)
        grid.addWidget(self.activo, fila, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        for campo in (self.codigo, self.porcentaje, self.usos, self.nota):
            campo.setMinimumHeight(36)
            campo.textChanged.connect(lambda _t: self.error.hide())
        self.aviso_gratis = etiqueta('Ojo: un cupón del 100 % regala la licencia. Ponle un tope de usos para que no se '
                                     'reparta de más si el código se comparte.')
        self.aviso_gratis.setWordWrap(True)
        self.aviso_gratis.setStyleSheet(f'color: {AVISO};')
        lay.addWidget(self.aviso_gratis)
        self.error = etiqueta('', 'error')
        self.error.setWordWrap(True)
        self.error.hide()
        lay.addWidget(self.error)
        lay.addSpacing(8)
        cancelar = boton('Cancelar')
        guardar = boton('Crear cupón' if nuevo else 'Guardar cambios', 'ok', tipo='primario')
        guardar.setDefault(True)
        cancelar.clicked.connect(self.reject)
        guardar.clicked.connect(self.accept)
        izquierda = ()
        if not nuevo:
            borrar = boton('Borrar cupón', 'basura', tipo='peligro')
            borrar.clicked.connect(self._borrar)
            izquierda = (borrar,)
        lay.addLayout(fila_botones(cancelar, guardar, izquierda=izquierda))
        self._poner_precio()

    def _mayusculas(self, texto):
        limpio = re.sub(r'\s+', '', texto).upper()
        if limpio != texto:
            posicion = self.codigo.cursorPosition() - (len(texto) - len(limpio))
            self.codigo.setText(limpio)
            self.codigo.setCursorPosition(max(0, posicion))

    def _porcentaje(self):
        n = entero_o_nada(self.porcentaje.text().strip())
        return n if n is not None and 1 <= n <= 100 else None

    def _poner_precio(self):
        p = self._porcentaje()
        if p is None:
            self.lbl_precio.setText('de 1 a 100')
        elif p >= 100:
            self.lbl_precio.setText('licencia gratis')
        elif self.precio:
            final = max(min(self.precio, 100), math.floor(self.precio * (100 - p) / 100 + 0.5))   # (precio_con_cupon)
            self.lbl_precio.setText(f'queda en {dinero(final, self.moneda)}')
        else:
            self.lbl_precio.setText('')
        self.aviso_gratis.setVisible(p is not None and p >= 100 and not self.usos.text().strip())

    def datos(self):
        """Todo lo del diálogo, como lo pide cupon_crear (usos_max y vence en None: sin tope, no vence)."""
        q = self.fecha.date()
        return {'codigo': self.codigo.text().strip().upper(), 'porcentaje': self._porcentaje(),
                'usos_max': entero_o_nada(self.usos.text().strip()) or None,
                'vence': f'{q.year():04d}-{q.month():02d}-{q.day():02d}' if self.con_vence.isChecked() else None,
                'nota': ' '.join(self.nota.text().split()) or None, 'activo': self.activo.isChecked()}

    def cambios(self):
        """Solo lo que cambió (para cupon_editar)."""
        datos = self.datos()
        datos.pop('codigo')
        if not self.cupon:
            return datos
        return {k: v for k, v in datos.items() if v != (self.cupon.get(k) or None if k in ('nota', 'vence', 'usos_max')
                                                         else self.cupon.get(k))}

    def _problema(self):
        datos = self.datos()
        if self.cupon is None and not CODIGO_CUPON.fullmatch(datos['codigo']):
            return 'El código tiene que tener de 2 a 32 letras, números, guiones o guiones bajos (sin espacios).', self.codigo
        if datos['porcentaje'] is None:
            return 'El descuento tiene que ser de 1 a 100 %.', self.porcentaje
        if self.cupon is not None and not self.cambios():
            return 'No cambiaste nada.', self.porcentaje
        return None, None

    def _borrar(self):
        self.quiere_borrar = True
        super().accept()

    def accept(self):
        problema, campo = self._problema()
        if problema:
            self.error.setText(problema)
            self.error.show()
            campo.setFocus()
            return
        super().accept()


class DialogoAnunciar(QDialog):
    """«Anunciar versión»: manda a cada cliente un correo de que salió una versión nueva de CineCaptions.
    Primero pregunta a admin.php cuál es la versión publicada (version_actual) y a quiénes les llegaría
    (candidatos_aviso). Al mandar va uno por uno con avisar_actualizacion, con PAUSA_AVISOS_MS entre cada uno, barra de
    avance y «Detener». Si el servidor llega a su tope de correos por hora (motivo 'limite'), espera lo que diga
    reintentar_en y sigue con el mismo cliente. Todas las peticiones van por la cola de la ventana (una a la vez).
    Con solo_ver=True (--captura) no manda nada."""
    A_QUIEN = [('Solo los que no han actualizado', 'desactualizados'), ('Todos los clientes', 'todos')]

    def __init__(self, parent, cliente, trabajos, info=None, solo_ver=False):
        super().__init__(parent)
        self.setWindowTitle('Anunciar versión')
        self.setModal(True)
        self.setMinimumWidth(580)
        self.cliente, self.trabajos, self.solo_ver = cliente, trabajos, solo_ver
        self.info = info
        self.candidatos, self.excluidos, self.consulta = [], {}, None
        self.enviando = self.detener = self.terminado = False
        self.cuenta = dict.fromkeys(('enviados', 'ya_avisados', 'baja', 'fallidos', 'otros'), 0)
        self._cola, self._total, self._errores_red = [], 0, 0
        self._num = self._num_version = 0   # (cada consulta con su número: lo que llegue de una vieja no cuenta)
        self._mensaje_tocado = False
        self._confirmar = lambda pregunta, explicacion, texto_boton: confirmar(self, pregunta, explicacion, texto_boton,
                                                                               False, 'megafono')
        self._timer_candidatos = QTimer(self)
        self._timer_candidatos.setSingleShot(True)
        self._timer_candidatos.setInterval(450)
        self._timer_candidatos.timeout.connect(self._cargar_candidatos)
        self._timer_envio = QTimer(self)
        self._timer_envio.setSingleShot(True)
        self._timer_envio.timeout.connect(self._enviar_siguiente)
        self._timer_espera = QTimer(self)
        self._timer_espera.setInterval(1000)
        self._timer_espera.timeout.connect(self._esperando)
        self._espera_hasta = 0.0

        lay = QVBoxLayout(self)
        margenes_dialogo(lay)
        self.titulo = cabeza_dialogo(lay, 'megafono', 'Anunciar una versión nueva')
        texto = etiqueta('A cada cliente le llega un correo con lo nuevo y el enlace para descargarla. Los que pidieron no '
                         'recibir estos avisos no lo reciben.', 'suave')
        texto.setWordWrap(True)
        lay.addWidget(texto)
        lay.addSpacing(4)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)
        fila_v = QHBoxLayout()
        fila_v.setSpacing(12)
        self.version = QLineEdit()
        self.version.setPlaceholderText('5.54')
        self.version.setFixedWidth(110)
        self.version.textEdited.connect(lambda _t: self._timer_candidatos.start())
        self.lbl_publicada = Recortada('Leyendo la versión publicada…', 'tenue')
        self.btn_github = boton('Volver a consultar', 'actualizar', tipo='enlace')
        self.btn_github.setToolTip('Vuelve a leer el version.json publicado en GitHub')
        self.btn_github.clicked.connect(lambda: self._cargar_version(refrescar=True))
        fila_v.addWidget(self.version)
        fila_v.addWidget(self.btn_github)
        fila_v.addStretch(1)
        col_v = QVBoxLayout()   # la fecha de publicación va abajo, en su propia línea (así no se corta)
        col_v.setSpacing(6)
        col_v.addLayout(fila_v)
        col_v.addWidget(self.lbl_publicada)
        lbl_version = etiqueta('Versión', 'suave')
        lbl_version.setMinimumHeight(34)   # centrada con el campo, no con las dos líneas
        grid.addWidget(lbl_version, 0, 0, Qt.AlignmentFlag.AlignTop)
        grid.addLayout(col_v, 0, 1)
        self.a_quien = Segmentos(self.A_QUIEN, 'desactualizados')
        self.a_quien.cambiado.connect(lambda _v: self._cargar_candidatos())
        grid.addWidget(etiqueta('A quién', 'suave'), 1, 0)
        grid.addWidget(self.a_quien, 1, 1, Qt.AlignmentFlag.AlignLeft)
        self.mensaje = QPlainTextEdit()
        self.mensaje.setPlaceholderText('Lo nuevo de esta versión, en una o dos líneas.')
        self.mensaje.setFixedHeight(104)
        self.mensaje.setTabChangesFocus(True)
        self.mensaje.textChanged.connect(self._mensaje_cambiado)
        self.lbl_largo = etiqueta('', 'tenue')
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self.mensaje)
        col.addWidget(self.lbl_largo, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(etiqueta('Mensaje', 'suave'), 2, 0, Qt.AlignmentFlag.AlignTop)
        grid.addLayout(col, 2, 1)
        lay.addLayout(grid)

        # Cuántos lo recibirán (y, al mandar, el avance)
        self.caja = QFrame()
        self.caja.setObjectName('caja')
        lc = QVBoxLayout(self.caja)
        lc.setContentsMargins(16, 14, 16, 16)
        lc.setSpacing(6)
        self.lbl_cuantos = etiqueta('Buscando a quién avisar…', 'cifra')
        self.lbl_nombres = etiqueta('', 'suave')
        self.lbl_nombres.setWordWrap(True)
        self.lbl_fuera = etiqueta('', 'tenue')
        self.lbl_fuera.setWordWrap(True)
        self.avance = QProgressBar()
        self.avance.setTextVisible(False)
        self.avance.hide()
        self.lbl_avance = etiqueta('', 'suave')
        self.lbl_avance.setWordWrap(True)
        self.lbl_avance.hide()
        for w in (self.lbl_cuantos, self.lbl_nombres, self.lbl_fuera, self.avance, self.lbl_avance):
            lc.addWidget(w)
        lay.addWidget(self.caja)
        self.error = etiqueta('', 'error')
        self.error.setWordWrap(True)
        self.error.hide()
        lay.addWidget(self.error)
        lay.addSpacing(8)
        self.btn_cerrar = boton('Cancelar')
        self.btn_cerrar.clicked.connect(self.reject)
        self.btn_detener = boton('Detener', 'detener', tipo='peligro')
        self.btn_detener.clicked.connect(self._detener)
        self.btn_detener.hide()
        self.btn_mandar = boton('Mandar aviso', 'enviar', tipo='primario')
        self.btn_mandar.setEnabled(False)
        self.btn_mandar.clicked.connect(self._mandar)
        lay.addLayout(fila_botones(self.btn_cerrar, self.btn_detener, self.btn_mandar))
        if info and info.get('version'):
            self._poner_info(info)
            self._cargar_candidatos()
        else:
            self._cargar_version()

    # --- Versión y candidatos
    def _ocupado_envio(self):
        """Ya se está mandando (o ya se mandó): lo que llegue de una consulta no cambia nada de lo que se ve."""
        return self.enviando or self.terminado

    def _cargar_version(self, refrescar=False):
        self.lbl_publicada.poner('Leyendo la versión publicada…')
        self._num_version += 1   # (su propio número: si mientras tanto se escribe una versión, esto igual llega)
        numero, cliente = self._num_version, self.cliente

        def listo(info):
            if numero == self._num_version and not self._ocupado_envio():
                self.info = info
                self._poner_info(info, refrescar)
                self._cargar_candidatos()

        def fallo(error):
            if numero == self._num_version and not isinstance(error, Cancelada) and not self._ocupado_envio():
                self.lbl_publicada.poner('')
                self._error(FALTA_SERVIDOR if getattr(error, 'desconocida', False) else
                            f'No se pudo leer la versión publicada: {mensaje_de(error)}')
                if not texto_version(self.version.text()):
                    self.lbl_cuantos.setText('Escribe la versión que quieres anunciar.')

        self.trabajos.iniciar(lambda: cliente.version_actual(refrescar), listo, fallo, clave='anunciar_version')

    def _poner_info(self, info, refrescar=False):
        version = texto_version(info.get('version'))
        if version and (refrescar or not self.version.text().strip()):
            self.version.setText(version)
        if info.get('notas') and not self._mensaje_tocado:
            self.mensaje.blockSignals(True)
            self.mensaje.setPlainText(info['notas'][:MAX_TEXTO])
            self.mensaje.blockSignals(False)
            self._mensaje_cambiado(tocado=False)
        partes = []
        if fecha_dia(info.get('fecha')) != '—':
            partes.append(f"Publicada el {fecha_dia(info['fecha'])}")
        if info.get('error'):   # (admin.php ya lo dice completo: «GitHub tardó demasiado en responder.»)
            partes.append(info['error'])
        elif info.get('consultado'):
            partes.append(f"consultado en GitHub {hace(info['consultado'])}")
        self.lbl_publicada.poner(' · '.join(partes))
        self._poner_titulo()

    def _poner_titulo(self):
        version = texto_version(self.version.text())
        self.titulo.setText(f'Anunciar la versión {version}' if version else 'Anunciar una versión nueva')

    def _mensaje_cambiado(self, tocado=True):
        texto = self.mensaje.toPlainText()
        if len(texto) > MAX_TEXTO:   # no deja pasar del máximo de admin.php
            cursor = self.mensaje.textCursor()
            self.mensaje.blockSignals(True)
            self.mensaje.setPlainText(texto[:MAX_TEXTO])
            self.mensaje.blockSignals(False)
            cursor.setPosition(MAX_TEXTO)
            self.mensaje.setTextCursor(cursor)
            texto = texto[:MAX_TEXTO]
        self._mensaje_tocado = self._mensaje_tocado or tocado
        self.lbl_largo.setText(f'{len(texto):,} / {MAX_TEXTO:,}')

    def _cargar_candidatos(self):
        self._timer_candidatos.stop()
        self._poner_titulo()
        version, a_quien = texto_version(self.version.text()), self.a_quien.valor
        self.btn_mandar.setEnabled(False)
        if not version:
            self.lbl_cuantos.setText('Escribe una versión válida, por ejemplo 5.54.')
            self.lbl_nombres.clear()
            self.lbl_fuera.clear()
            return
        self.lbl_cuantos.setText('Buscando a quién avisar…')
        self.error.hide()
        self._num += 1
        numero, cliente = self._num, self.cliente

        def listo(r):
            if numero == self._num and not self._ocupado_envio():
                self.candidatos, self.excluidos, self.consulta = r['candidatos'], r['excluidos'], (version, a_quien)
                self._poner_candidatos()

        def fallo(error):
            if numero == self._num and not isinstance(error, Cancelada) and not self._ocupado_envio():
                self.lbl_cuantos.setText('No se pudo saber a quién avisar.')
                self._error(FALTA_SERVIDOR if getattr(error, 'desconocida', False) else mensaje_de(error))

        self.trabajos.iniciar(lambda: cliente.candidatos_aviso(version, a_quien), listo, fallo, clave='candidatos')

    def _poner_candidatos(self):
        n = len(self.candidatos)
        self.lbl_cuantos.setText(f"Recibirán el aviso: {plural(n, 'cliente', 'clientes')}" if n else
                                 'Nadie para avisar con esta selección.')
        nombres = [c['cliente'] or c['correo'] or f"Licencia #{c['licencia_id']}" for c in self.candidatos]
        if nombres:
            mostrar = nombres[:3]
            self.lbl_nombres.setText(', '.join(mostrar) + (f' y {len(nombres) - 3} más' if len(nombres) > 3 else ''))
        else:
            self.lbl_nombres.setText('Todos los que tienen la licencia activa ya tienen esta versión o ya recibieron el '
                                     'aviso.' if self.consulta and self.consulta[1] == 'desactualizados' else '')
        e = self.excluidos
        motivos = ((e.get('ya_avisados'), 'ya avisado', 'ya avisados'), (e.get('baja'), 'de baja', 'de baja'),
                   (e.get('bloqueadas'), 'bloqueada', 'bloqueadas'), (e.get('sin_correo'), 'sin correo', 'sin correo'),
                   (e.get('al_dia'), 'al día', 'al día'))
        partes = [plural(n, uno, varios) for n, uno, varios in motivos if n]
        self.lbl_fuera.setText('Quedan fuera: ' + ' · '.join(partes) if partes else '')
        self.lbl_fuera.setVisible(bool(partes))
        self.btn_mandar.setText(f" Mandar aviso a {plural(n, 'cliente', 'clientes')}" if n else ' Mandar aviso')
        self.btn_mandar.setEnabled(bool(n) and not self.solo_ver and not self.enviando)
        if self.solo_ver:
            self.btn_mandar.setToolTip('En modo captura no se manda nada.')

    def _error(self, texto):
        self.error.setText(texto)
        self.error.show()

    # --- Envío, uno por uno
    def _mandar(self):
        version = texto_version(self.version.text())
        consulta = (version, self.a_quien.valor)
        if self.solo_ver or self._ocupado_envio() or not self.candidatos or not version or self.consulta != consulta:
            return
        candidatos = list(self.candidatos)   # a quiénes se les pregunta (la lista de la pantalla)
        if not self._confirmar(*self.texto_confirmacion(len(candidatos))):
            return
        # Mientras estaba abierta la pregunta pudo llegar otra versión de GitHub u otra lista: no se manda nada que no
        # sea lo que se confirmó
        if self.consulta != consulta or (texto_version(self.version.text()), self.a_quien.valor) != consulta:
            self._error('La versión o la lista cambió mientras confirmabas. Revisa y vuelve a mandar.')
            return
        self.enviando, self.detener = True, False
        self.error.hide()
        self._version_envio, self._mensaje_envio = version, self.mensaje.toPlainText().strip()[:MAX_TEXTO] or None
        self._cola, self._total = candidatos, len(candidatos)
        n = self._total
        for w in (self.version, self.btn_github, self.a_quien, self.mensaje, self.btn_mandar):
            w.setEnabled(False)
        self.btn_mandar.hide()
        self.btn_detener.show()
        self.btn_detener.setEnabled(True)
        self.btn_cerrar.setEnabled(False)
        self.lbl_nombres.hide()
        self.lbl_fuera.hide()
        self.avance.setRange(0, n)
        self.avance.setValue(0)
        self.avance.show()
        self.lbl_avance.show()
        self._enviar_siguiente()

    def texto_confirmacion(self, n):
        """La pregunta antes de mandar: (pregunta, explicación, texto del botón)."""
        version = texto_version(self.version.text()) or ''
        return (f"¿Mandar el aviso a {plural(n, 'cliente', 'clientes')}?",
                f'A cada uno le llega un correo con lo nuevo de la {version} y el enlace para descargarla. '
                'Sale uno por segundo y lo puedes detener.', 'Mandar aviso')

    def _hechos(self):
        return self._total - len(self._cola)

    def _enviar_siguiente(self):
        if self.detener or not self._cola:
            self._terminar()
            return
        c = self._cola[0]
        self.lbl_cuantos.setText(f'Enviando {self._hechos() + 1} de {self._total}…')
        self.lbl_avance.setText(c['cliente'] or c['correo'] or '')
        cliente, version, mensaje_texto = self.cliente, self._version_envio, self._mensaje_envio
        self.trabajos.iniciar(lambda: cliente.avisar_actualizacion(c['licencia_id'], version, mensaje_texto),
                              self._enviado, self._fallo_envio)

    def _siguiente(self):
        self.avance.setValue(self._hechos())
        if self.detener:
            self._terminar()
        else:
            self._timer_envio.start(PAUSA_AVISOS_MS)

    def _enviado(self, r):
        if r['motivo'] == 'limite':   # el tope de correos por hora: se espera y se sigue con el mismo cliente
            self._esperar(max(1, min(3600, r['reintentar_en'] or 60)))
            return
        self._cola.pop(0)
        self._errores_red = 0
        if r['enviado']:
            self.cuenta['enviados'] += 1
        elif r['motivo'] == 'ya_avisado':
            self.cuenta['ya_avisados'] += 1
        elif r['motivo'] == 'baja':
            self.cuenta['baja'] += 1
        elif r['motivo'] in ('sin_correo', 'bloqueada'):
            self.cuenta['otros'] += 1
        else:
            self.cuenta['fallidos'] += 1
        self._siguiente()

    def _fallo_envio(self, error):
        if isinstance(error, Cancelada):   # (no salió: se intenta otra vez con el mismo cliente)
            self._siguiente()
            return
        self._cola.pop(0)
        self.cuenta['fallidos'] += 1
        codigo = getattr(error, 'codigo', None)
        self._errores_red = self._errores_red + 1 if codigo in (0, 500, 502, 503, 504) else 0
        if codigo in (401, 429) or getattr(error, 'desconocida', False) or self._errores_red >= 3:
            self.detener = True   # sin clave válida, sin el servidor nuevo o sin conexión no tiene caso seguir
            self._error(f'Se detuvo el envío: {mensaje_de(error)}')
        self._siguiente()

    def _esperar(self, segundos):
        self._espera_hasta = time.monotonic() + segundos
        self._timer_espera.start()
        self._esperando()

    def _esperando(self):
        if self.detener:
            self._timer_espera.stop()
            self._terminar()
            return
        restante = math.ceil(self._espera_hasta - time.monotonic())
        if restante <= 0:
            self._timer_espera.stop()
            self._enviar_siguiente()
            return
        minutos, segundos = divmod(restante, 60)
        self.lbl_cuantos.setText(f'En pausa: sigo en {minutos}:{segundos:02d}')
        self.lbl_avance.setText('El servidor llegó a su tope de 90 correos por hora. Espera aquí y sigue solo con '
                                'los que faltan, o detenlo.')

    def _detener(self):
        self.detener = True
        self.btn_detener.setEnabled(False)
        self.btn_detener.setText(' Deteniendo…')
        if self._timer_espera.isActive() or self._timer_envio.isActive():   # no hay un correo saliendo: se para ya
            self._timer_espera.stop()
            self._timer_envio.stop()
            self._terminar()

    def _terminar(self):
        if self.terminado:
            return
        self.enviando, self.terminado = False, True
        self._timer_espera.stop()
        self._timer_envio.stop()
        c = self.cuenta
        faltan = len(self._cola)
        if faltan:
            self.lbl_cuantos.setText('Envío detenido')
        elif c['enviados']:
            self.lbl_cuantos.setText(f"Listo: {plural(c['enviados'], 'aviso enviado', 'avisos enviados')}")
        else:
            self.lbl_cuantos.setText('Listo: no salió ningún aviso')
        partes = [f"Enviados: {c['enviados']:,}", f"Ya avisados: {c['ya_avisados']:,}", f"De baja: {c['baja']:,}",
                  f"Fallidos: {c['fallidos']:,}"]
        if c['otros']:
            partes.append(f"Sin correo o bloqueadas: {c['otros']:,}")
        if faltan:
            partes.append(f'Sin mandar: {faltan:,}')
        self.lbl_avance.setText(' · '.join(partes))
        if faltan or c['fallidos']:   # (avisar_actualizacion no repite a quien ya le llegó: se puede volver a intentar)
            self.lbl_fuera.setText('Para mandárselo a los que faltan, anuncia la versión otra vez: a quien ya le llegó '
                                   'no le vuelve a llegar.')
            self.lbl_fuera.show()
        self.avance.setValue(self._hechos())
        self.btn_detener.hide()
        self.btn_cerrar.setText('Cerrar')
        self.btn_cerrar.setProperty('tipo', 'primario')
        repulir(self.btn_cerrar)
        self.btn_cerrar.setEnabled(True)
        self.btn_cerrar.setFocus()

    @property
    def enviados(self):
        return self.cuenta['enviados']

    def reject(self):
        if self.enviando:   # mientras sale un correo no se cierra: primero se detiene
            if confirmar(self, '¿Detener el envío?', 'El correo que va saliendo termina de mandarse; los demás no.',
                         'Detener', True, 'detener'):
                self._detener()
            return
        super().reject()

    def closeEvent(self, evento):
        if self.enviando:
            evento.ignore()
            self.reject()
            return
        super().closeEvent(evento)


# ---------------------------------------------------------------- Panel de la licencia (a la derecha)

class Ficha(QWidget):
    """Pares «Etiqueta   valor» en dos columnas."""

    def __init__(self):
        super().__init__()
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(16)
        self._grid.setVerticalSpacing(8)
        self._grid.setColumnStretch(1, 1)

    def poner(self, filas, seleccionable=True):
        vaciar(self._grid)
        for n, (nombre, valor, color) in enumerate(filas):
            izquierda = etiqueta(nombre, 'tenue')
            derecha = etiqueta(valor or '—', seleccionable=seleccionable)
            derecha.setWordWrap(True)
            # Un valor largo sin espacios (un ID de Recurrente) nunca ensancha el panel: se corta y queda en el tooltip
            derecha.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            if valor and len(valor) > 24:
                derecha.setToolTip(valor)
            if color:
                derecha.setStyleSheet(f'color: {color};')
            self._grid.addWidget(izquierda, n, 0, Qt.AlignmentFlag.AlignTop)
            self._grid.addWidget(derecha, n, 1)


class Seccion(QFrame):
    """Una parte del panel: una raya arriba que la separa de la anterior y su título chico (y algo a la derecha del
    título, si hace falta). Sin caja propia: el panel ya es una tarjeta y una caja dentro de otra se veía pesada."""

    def __init__(self, titulo):
        super().__init__()
        self.setObjectName('seccion')
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 16, 0, 0)
        self.lay.setSpacing(12)
        cabeza = QHBoxLayout()
        cabeza.setSpacing(8)
        self.titulo = etiqueta(titulo.upper(), 'seccionTitulo', espaciado=True)
        self.extra = etiqueta('', plano=False)
        self.extra.setTextFormat(Qt.TextFormat.RichText)
        cabeza.addWidget(self.titulo)
        cabeza.addStretch(1)
        cabeza.addWidget(self.extra)
        self.lay.addLayout(cabeza)
        self.cabeza = cabeza   # para poner un botón chico junto al título

    def poner_titulo(self, titulo, extra_html=''):
        self.titulo.setText(titulo.upper())
        self.extra.setText(extra_html)


def pastilla_html(texto, color):
    return (f'<span style="color:{color}; font-size:12px; font-weight:600">'
            f'&#9679;&nbsp;{html.escape(texto)}</span>')


class FilaEquipo(QFrame):
    """Un equipo activado: nombre y versión arriba; el sistema y desde cuándo tiene esa versión en medio, y la línea de su
    ficha técnica (2.4, CineCaptions 5.72); el último uso, «Ficha» (si la mandó) y «Liberar» abajo."""

    def __init__(self, equipo, ultima, al_liberar, con_version=True, al_ficha=None):
        super().__init__()
        self.setObjectName('equipo')
        self.equipo = equipo
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)
        ic = QLabel()
        ic.setPixmap(pintar_icono('equipo', TEXTO_SUAVE, 20))
        lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(4)
        arriba = QHBoxLayout()
        arriba.setSpacing(8)
        nombre = Recortada(nombre_pc(equipo))
        nombre.setFont(fuente(13, QFont.Weight.DemiBold))
        version = texto_version(equipo.get('version'))
        self.estado = equipo.get('estado_version') or estado_de_version(equipo.get('version'), ultima)
        self.version = Pastilla(version or 'Sin datos', ESTADOS_VERSION.get(self.estado, ESTADOS_VERSION['desconocido'])[1])
        self.version.setToolTip({'al_dia': 'Tiene la última versión.', 'sin_datos': SIN_DATOS_VERSION,
                                 'desactualizado': f'Tiene una versión vieja (la última es la {texto_version(ultima)}).'
                                 }.get(self.estado, 'No se sabe cuál es la última versión publicada.'))
        arriba.addWidget(nombre, 1)
        arriba.addWidget(self.version)
        self.version.setVisible(con_version)   # (con el admin.php anterior no se sabe la versión)
        col.addLayout(arriba)
        # En medio, corto para que quepa en el panel: «Windows 11 · 5.54 desde el 27 oct» (la versión anterior y la
        # huella van en el tooltip)
        partes = []
        so = texto_so(equipo.get('so'))
        if so:
            partes.append(so)
        if version and equipo.get('version_desde'):
            partes.append(f"{version} desde el {fecha_dia_corta(equipo['version_desde'])}")
        if not version and con_version:
            partes.append('todavía no reporta su versión')
        self.detalle = Recortada(' · '.join(partes), 'tenue')
        self.detalle.setVisible(bool(partes))
        col.addWidget(self.detalle)
        # 2.4: la línea de su ficha («GPU … · RAM … · CPU … · Pantalla …», cortada: entera en el tooltip) con «Ficha» al lado,
        # que abre la ficha técnica completa. En su propia fila: abajo, el último uso y «Liberar» siguen cabiendo enteros.
        resumen = equipo.get('ficha_resumen') or ''
        self.fila_ficha = QWidget()
        lf = QHBoxLayout(self.fila_ficha)
        lf.setContentsMargins(0, 0, 0, 0)
        lf.setSpacing(8)
        self.resumen = Recortada(resumen or 'Ficha técnica', 'suave')
        self.btn_ficha = boton('Ficha', 'info', chico=True)
        self.btn_ficha.setToolTip('La ficha técnica completa de este equipo: sistema, procesador, memoria, tarjeta gráfica, '
                                  'discos, Resolve, motores y lo que revisó CineCaptions')
        self.btn_ficha.clicked.connect(lambda: al_ficha(equipo))
        lf.addWidget(self.resumen, 1)
        lf.addWidget(self.btn_ficha)
        self.resumen.setVisible(bool(resumen))
        self.btn_ficha.setVisible(al_ficha is not None and bool(equipo.get('con_ficha')))
        self.fila_ficha.setVisible(bool(resumen) or self.btn_ficha.isVisibleTo(self.fila_ficha))
        col.addWidget(self.fila_ficha)
        abajo = QHBoxLayout()
        abajo.setSpacing(8)
        uso = Recortada(uso_texto(equipo['ultima']), 'tenue')
        self.btn = boton('Liberar', 'x', chico=True)
        self.btn.setToolTip('Liberar este equipo: deja libre su lugar en la licencia')
        self.btn.clicked.connect(lambda: al_liberar(equipo))
        abajo.addWidget(uso, 1)
        abajo.addWidget(self.btn)
        col.addLayout(abajo)
        lay.addLayout(col, 1)
        anterior = texto_version(equipo.get('version_anterior')) or equipo.get('version_anterior')
        self.setToolTip(f"{equipo['nombre_equipo'] or nombre_pc(equipo)}\nID {equipo['equipo']}\n"
                        f"Activado: {fecha_larga(equipo['creada'])}\nÚltima vez: {fecha_larga(equipo['ultima'])}"
                        + (f"\nSistema: {so}" if so else '')
                        + (f"\nTiene la {version} desde el {fecha_larga(equipo['version_desde'])}"
                           if version and equipo.get('version_desde') else '')
                        + (f'\nAntes tenía la {anterior}' if anterior else '')
                        + (f"\nFicha técnica: {fecha_larga(equipo['ficha_cuando'], utc=True)}" if equipo.get('ficha_cuando')
                           else ''))


# ---------------------------------------------------------------- 2.4: la ficha técnica del equipo (CineCaptions 5.72)

# CineCaptions 5.72 manda al abrirse (equipo.php) la ficha técnica del equipo, v1, con TODOS los campos opcionales. La app
# pinta lo que conoce y lo demás sale en bruto en «Otros datos»: un campo nuevo del programa se ve antes de que la app lo
# entienda, y uno con otra forma no rompe nada.
CAMPOS_FICHA = ('v', 'cuando', 'origen', 'app', 'so', 'cpu', 'ram', 'gpus', 'pantallas', 'discos', 'resolve', 'motores',
                'componentes', 'revision', 'puesta_al_dia')
ESTADOS_REVISION = {'falta': ('Falta', PELIGRO), 'aviso': ('Aviso', AVISO), 'ok': ('Bien', EXITO)}   # (en este orden)
NOMBRES_MOTOR = {'voz': 'Voz (IA)', 'auxiliar': 'Auxiliar', 'whisper': 'Whisper'}
NOMBRES_COMPONENTE = {'vcredist_x64': 'Visual C++ (x64)', 'vcredist_x86': 'Visual C++ (x86)', 'winget': 'winget'}
USOS_DISCO = {'programa': 'Programa', 'datos': 'Datos'}
DISCO_POCO_GB = 15   # menos libre que esto (o menos del 10 %) sale en naranja: ahí ya no caben los modelos de voz


def _numero(valor):
    """Un número de la ficha (no un sí/no ni un texto) o None."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return valor if math.isfinite(valor) else None


def _cifra(n, decimales=1):
    """12 → «12», 12.0 → «12», 8.44 → «8,4» (con coma, como los textos del programa)."""
    if not math.isfinite(n):
        return str(n)
    if decimales <= 0 or float(n) == round(n):
        return str(round(n))
    return f'{n:.{decimales}f}'.rstrip('0').rstrip('.').replace('.', ',')


def texto_gb(gb, decimales=1):
    """«8,4 GB», «930,4 GB»; desde 1000 GB, en TB: «1,8 TB»."""
    return f'{_cifra(gb / 1024, 1)} TB' if gb >= 1000 else f'{_cifra(gb, decimales)} GB'


def texto_bruto(valor):
    """Un valor de la ficha tal cual: sí/no, números, textos y, lo demás (listas, objetos), su JSON en una línea."""
    if valor is None:
        return '—'
    if isinstance(valor, bool):
        return 'Sí' if valor else 'No'
    if isinstance(valor, (int, float)):
        return _cifra(valor, 2)
    if isinstance(valor, str):
        return valor
    return json.dumps(valor, ensure_ascii=False, separators=(', ', ': '))


def _texto_ficha(valor):
    """El texto de un campo conocido (None si no viene o viene vacío)."""
    return None if valor is None or valor == '' else texto_bruto(valor)


def _sobrantes(datos, conocidos):
    """Las filas de lo que trae un objeto de la ficha y la app no conoce: (campo, valor en bruto, sin color)."""
    return [(str(k), texto_bruto(x), None) for k, x in datos.items() if k not in conocidos]


def secciones_ficha(ficha):
    """La ficha técnica (un dict) → [{titulo, filas: [(nombre, valor, color)], puntos: [(color, estado, texto)], extra}]: Sistema,
    Procesador, Memoria, Tarjeta gráfica, Pantallas, Discos, DaVinci Resolve, Motores, Componentes, Revisión (los puntos, lo que
    falta primero), Puesta al día y Otros datos. Lo que no viene no sale; lo que viene con otra forma, o no se conoce, va en
    bruto a «Otros datos». Nunca confía en los tipos: todo lo puede mandar mal un programa viejo o roto."""
    ficha = ficha if isinstance(ficha, dict) else {}
    secciones, otros = [], []
    t = _texto_ficha

    def objeto(campo):
        valor = ficha.get(campo)
        if valor is None or isinstance(valor, dict):
            return valor
        otros.append((campo, texto_bruto(valor), None))
        return None

    def lista(campo):   # (una lista de objetos)
        valor = ficha.get(campo)
        if valor is None:
            return []
        if isinstance(valor, list) and all(isinstance(x, dict) for x in valor):
            return valor
        otros.append((campo, texto_bruto(valor), None))
        return []

    def seccion(titulo, filas, puntos=(), extra=''):
        filas = [f for f in filas if f[1]]   # (las que no traen nada no salen)
        if filas or puntos:
            secciones.append({'titulo': titulo, 'filas': filas, 'puntos': list(puntos), 'extra': extra})

    so, app = objeto('so'), objeto('app')
    filas = []
    if so is not None:
        nombre = ' '.join(x for x in (t(so.get('nombre')), t(so.get('version'))) if x)
        build = t(so.get('build'))
        filas.append(('Sistema', ' · '.join(x for x in (nombre, f'build {build}' if build else None, t(so.get('arquitectura')))
                                            if x), None))
        filas += _sobrantes(so, ('nombre', 'version', 'build', 'arquitectura'))
    if app is not None:
        idioma = t(app.get('idioma'))
        filas.append(('CineCaptions', ' · '.join(x for x in (t(app.get('version')), f'idioma {idioma}' if idioma else None)
                                                 if x), None))
        filas += _sobrantes(app, ('version', 'idioma'))
    seccion('Sistema', filas)

    cpu = objeto('cpu')
    if cpu is not None:
        avx2 = cpu.get('avx2')
        seccion('Procesador', [('Modelo', t(cpu.get('nombre')), None), ('Hilos', t(cpu.get('hilos')), None),
                               ('AVX2', t(avx2), AVISO if avx2 is False else None)]   # (sin AVX2, la voz va lenta o no va)
                + _sobrantes(cpu, ('nombre', 'hilos', 'avx2')))

    ram = objeto('ram')
    if ram is not None:
        total, libre = _numero(ram.get('total_mb')), _numero(ram.get('libre_mb'))
        filas = [('Total', texto_gb(total / 1024, 0) if total else t(ram.get('total_mb')), None)]
        if libre is not None and total:
            filas.append(('Libre', f'{texto_gb(libre / 1024)} ({round(libre * 100 / total)} %)',
                          AVISO if libre < total * 0.15 else None))
        else:
            filas.append(('Libre', texto_gb(libre / 1024) if libre is not None else t(ram.get('libre_mb')), None))
        seccion('Memoria', filas + _sobrantes(ram, ('total_mb', 'libre_mb')))

    gpus = lista('gpus')
    filas = []
    for n, g in enumerate(gpus, 1):
        nombre = t(g.get('nombre')) or 'Sin nombre'
        if len(gpus) > 1 and g.get('principal') is True:
            nombre += ' · principal'
        filas.append(('Modelo' if len(gpus) == 1 else f'Tarjeta {n}', nombre, None))
        fabricante = t(g.get('fabricante'))
        if fabricante and fabricante.casefold() not in nombre.casefold():
            filas.append(('Fabricante', fabricante, None))
        vram = _numero(g.get('vram_mb'))
        filas.append(('VRAM', texto_gb(vram / 1024, 0 if vram >= 1024 else 1) if vram else t(g.get('vram_mb')), None))
        driver, fecha = t(g.get('driver')), t(g.get('driver_fecha'))
        if fecha and leer_fecha(fecha):
            fecha = fecha_dia(fecha)
        filas.append(('Driver', ' · '.join(x for x in (driver, f'del {fecha}' if fecha else None) if x), None))
        filas += _sobrantes(g, ('nombre', 'fabricante', 'vram_mb', 'driver', 'driver_fecha', 'principal'))
    seccion('Tarjetas gráficas' if len(gpus) > 1 else 'Tarjeta gráfica', filas)

    pantallas = lista('pantallas')
    filas = []
    for n, p in enumerate(pantallas, 1):
        ancho, alto, escala = _numero(p.get('ancho')), _numero(p.get('alto')), _numero(p.get('escala'))
        valor = f'{_cifra(ancho)}×{_cifra(alto)}' if ancho and alto else None
        if escala:
            valor = f'{valor or "Sin tamaño"} al {_cifra(escala)} %'
        filas.append(('Resolución' if len(pantallas) == 1 else f'Pantalla {n}', valor, None))
        filas += _sobrantes(p, ('ancho', 'alto', 'escala'))
    seccion('Pantallas' if len(pantallas) > 1 else 'Pantalla', filas)

    filas = []
    for d in lista('discos'):
        uso, unidad = t(d.get('uso')), t(d.get('unidad'))
        nombre = USOS_DISCO.get(uso, (uso or 'Disco').capitalize()) + (f' ({unidad})' if unidad else '')
        libre, total = _numero(d.get('libre_gb')), _numero(d.get('total_gb'))
        poco = False
        if libre is not None:
            valor = f'{texto_gb(libre)} libres' + (f' de {texto_gb(total)}' if total else '')
            poco = libre < DISCO_POCO_GB or bool(total and libre < total * 0.1)
        else:
            valor = f'{texto_gb(total)} en total' if total else None
        filas.append((nombre, valor, AVISO if poco else None))
        filas += _sobrantes(d, ('uso', 'unidad', 'libre_gb', 'total_gb'))
    seccion('Discos', filas)

    resolve = objeto('resolve')
    if resolve is not None:
        if resolve.get('instalado') is False:
            filas = [('Instalado', 'No está instalado', AVISO)]
        else:
            filas = [('Edición', t(resolve.get('edicion')), None), ('Versión', t(resolve.get('version')), None)]
            if not any(f[1] for f in filas) and resolve.get('instalado') is True:
                filas = [('Instalado', 'Sí', None)]
        seccion('DaVinci Resolve', filas + _sobrantes(resolve, ('instalado', 'edicion', 'version')))

    motores = objeto('motores')
    if motores is not None:
        filas = []
        for clave, valor in motores.items():
            nombre = NOMBRES_MOTOR.get(clave, str(clave))
            if isinstance(valor, bool):
                filas.append((nombre, 'Instalado' if valor else 'No instalado', None if valor else AVISO))
            elif isinstance(valor, dict):
                instalado = valor.get('instalado')
                partes = ['Instalado' if instalado else 'No instalado'] if isinstance(instalado, bool) else []
                partes += [f"{'Python' if k == 'python' else k} {texto_bruto(x)}" for k, x in valor.items() if k != 'instalado']
                filas.append((nombre, ' · '.join(partes), AVISO if instalado is False else None))
            else:
                filas.append((nombre, texto_bruto(valor), None))
        seccion('Motores', filas)

    componentes = objeto('componentes')
    if componentes is not None:
        seccion('Componentes', [(NOMBRES_COMPONENTE.get(k, str(k)), texto_bruto(x), None) for k, x in componentes.items()])

    revision = ficha.get('revision')
    if isinstance(revision, list):
        orden = list(ESTADOS_REVISION)
        puntos = []
        for r in revision:
            if isinstance(r, dict):
                estado = r.get('estado')
                nombre, color = ESTADOS_REVISION.get(estado, (t(estado) or 'Sin estado', TEXTO_TENUE))
                texto = t(r.get('texto')) or t(r.get('id')) or '—'
            else:
                estado, nombre, color, texto = None, 'Sin estado', TEXTO_TENUE, texto_bruto(r)
            puntos.append((orden.index(estado) if estado in orden else len(orden), color, nombre, texto))
        puntos.sort(key=lambda p: p[0])   # (lo que falta primero; sort es estable: el orden del programa se queda)
        cuenta = {e: sum(1 for p in puntos if p[2] == ESTADOS_REVISION[e][0]) for e in orden}
        extra = ([f"{cuenta['falta']} falta" if cuenta['falta'] == 1 else f"{cuenta['falta']} faltan"] if cuenta['falta'] else []) \
            + ([plural(cuenta['aviso'], 'aviso', 'avisos')] if cuenta['aviso'] else [])
        seccion('Revisión', [], [p[1:] for p in puntos], ' · '.join(extra) if extra else ('Todo bien' if puntos else ''))
    elif revision is not None:
        otros.append(('revision', texto_bruto(revision), None))

    puesta = objeto('puesta_al_dia')
    if puesta is not None:
        def renglones(campo):
            valor = puesta.get(campo)
            return '\n'.join(texto_bruto(x) for x in valor) or None if isinstance(valor, list) else t(valor)

        hecho, pendiente, fallos = renglones('hecho'), renglones('pendiente'), renglones('fallos')
        filas = [('Hecho', hecho, None), ('Pendiente', pendiente, AVISO), ('Falló', fallos, PELIGRO)]
        if not (hecho or pendiente or fallos):
            filas = [('Hecho', 'Nada: ya estaba todo al día', None)]
        cuando = t(puesta.get('cuando'))
        seccion('Puesta al día', filas + _sobrantes(puesta, ('cuando', 'hecho', 'pendiente', 'fallos')),
                extra=(fecha_larga(cuando) if cuando and leer_fecha(cuando) else cuando or ''))

    otros += [(str(k), texto_bruto(x), None) for k, x in ficha.items() if k not in CAMPOS_FICHA]
    seccion('Otros datos', otros)
    return secciones


def texto_ficha(ficha_equipo, titulo=''):
    """La ficha para pegarla en otro lado (un chat con el cliente, una nota): el título, cuándo llegó y cada sección."""
    ficha_equipo = ficha_equipo or {}
    lineas = [titulo] if titulo else []
    if ficha_equipo.get('cuando'):
        lineas.append(f"Ficha técnica del {fecha_larga(ficha_equipo['cuando'], utc=True)}")
    if ficha_equipo.get('resumen'):
        lineas.append(ficha_equipo['resumen'])
    for s in secciones_ficha(ficha_equipo.get('ficha')):
        lineas.append('')
        lineas.append(s['titulo'].upper() + (f" · {s['extra']}" if s['extra'] else ''))
        for nombre, valor, _color in s['filas']:
            lineas.append(f"{nombre}: {valor.replace(chr(10), '; ')}")
        for _color, estado, texto in s['puntos']:
            lineas.append(f'{estado}: {texto}')
    return '\n'.join(lineas).strip()


class FichaEquipo(QWidget):
    """2.4: la ficha técnica de un equipo (secciones_ficha) con el aspecto del panel: cada parte en su Seccion (raya arriba y
    título chico) con sus pares en una Ficha; la revisión, con el punto de color de cada cosa. La usan la pestaña «Cliente y
    equipo» del error y DialogoFicha (el botón «Ficha» de los equipos de la licencia)."""

    def __init__(self, con_cabeza=True):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(16)
        self.con_cabeza = con_cabeza   # «Ficha del equipo · Llegó hace…» arriba (en DialogoFicha ya lo dice su título)
        self.datos = False     # lo último que se puso (False: nada todavía; así None también se pinta la primera vez)
        self.titulos = []      # las secciones que se ven, en orden (para las pruebas)
        self.puntos = []       # (color, estado, texto) de la revisión que se ve

    def poner(self, ficha_equipo, sin_ficha='Este equipo todavía no mandó su ficha técnica (llega con CineCaptions 5.72).'):
        """ficha_equipo: {ficha, resumen, cuando} (normalizar_ficha_equipo) o None. Si llega igual que la que se ve, no se
        rearma (al recargar el error no parpadea ni pierde lo seleccionado)."""
        if ficha_equipo == self.datos:
            return
        self.datos = ficha_equipo
        vaciar(self.lay)
        self.titulos, self.puntos = [], []
        ficha_equipo = ficha_equipo or {}
        cabeza = Seccion('Ficha del equipo')
        cuando = ficha_equipo.get('cuando')
        if cuando:
            cabeza.poner_titulo('Ficha del equipo', f'<span style="color:{TEXTO_TENUE}; font-size:12px">'
                                                    f'{html.escape(f"Llegó {hace(cuando, utc=True)}")}</span>')
            cabeza.setToolTip(f'CineCaptions la mandó el {fecha_larga(cuando, utc=True)}')
        secciones = secciones_ficha(ficha_equipo.get('ficha')) if ficha_equipo.get('ficha') else []
        if not secciones:   # (solo la línea corta, o nada)
            nota = etiqueta(ficha_equipo.get('resumen') or sin_ficha, 'suave' if ficha_equipo.get('resumen') else 'tenue',
                            seleccionable=bool(ficha_equipo.get('resumen')))
            nota.setWordWrap(True)
            cabeza.lay.addWidget(nota)
        if self.con_cabeza or not secciones:
            self.lay.addWidget(cabeza)
            self.titulos.append('Ficha del equipo')
        else:
            cabeza.deleteLater()
        grids = []
        for s in secciones:
            sec = Seccion(s['titulo'])
            if s['extra']:
                sec.poner_titulo(s['titulo'], f'<span style="color:{TEXTO_TENUE}; font-size:12px">{html.escape(s["extra"])}</span>')
            if s['filas']:
                pares = Ficha()
                pares.poner(s['filas'])
                sec.lay.addWidget(pares)
                grids.append(pares._grid)
            if s['puntos']:
                caja = self._puntos(s['puntos'])
                sec.lay.addWidget(caja)
                grids.append(caja.layout())
                self.puntos += s['puntos']
            self.lay.addWidget(sec)
            self.titulos.append(s['titulo'])
        # La columna de los nombres, igual de ancha en todas las secciones: los valores quedan alineados de arriba abajo
        izquierdas = [g.itemAtPosition(n, 0).widget() for g in grids for n in range(g.rowCount()) if g.itemAtPosition(n, 0)]
        for w in izquierdas:
            w.ensurePolished()
        ancho = max((w.sizeHint().width() for w in izquierdas), default=0)
        for g in grids:
            g.setColumnMinimumWidth(0, ancho)

    @staticmethod
    def _puntos(puntos):
        """La revisión: «● Falta» (en su color) a la izquierda y lo que dice CineCaptions a la derecha, como una Ficha."""
        caja = QWidget()
        grid = QGridLayout(caja)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        for n, (color, estado, texto) in enumerate(puntos):
            izquierda = etiqueta(pastilla_html(estado, color), plano=False)
            izquierda.setTextFormat(Qt.TextFormat.RichText)
            derecha = etiqueta(texto, seleccionable=True)
            derecha.setWordWrap(True)
            derecha.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            grid.addWidget(izquierda, n, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(derecha, n, 1)
        return caja


class DialogoFicha(QDialog):
    """2.4: la ficha técnica completa de un equipo de la licencia (el botón «Ficha» de Equipos): el nombre del equipo, de quién
    es y la FichaEquipo con barra de desplazamiento; «Copiar ficha» la copia como texto (texto_ficha)."""
    ANCHO = 600

    def __init__(self, parent, equipo, ficha_equipo, de_quien='', al_copiar=None):
        super().__init__(parent)
        self.alto_fijo = None   # (solo --captura: el alto de la captura, para que se vea casi entera)
        self.scroll = None
        nombre = nombre_pc(equipo)
        self.setWindowTitle(f'{APP} · Ficha de {nombre}')
        self.setModal(True)
        lay = QVBoxLayout(self)
        margenes_dialogo(lay)
        self.titulo = cabeza_dialogo(lay, 'equipo', nombre)
        cuando = (ficha_equipo or {}).get('cuando')
        partes = [x for x in (de_quien, f'ficha de {hace(cuando, utc=True)}' if cuando else None) if x]
        sub = etiqueta(' · '.join(partes), 'suave')
        sub.setWordWrap(True)
        sub.setVisible(bool(partes))
        if cuando:
            sub.setToolTip(f'CineCaptions la mandó el {fecha_larga(cuando, utc=True)}')
        lay.addWidget(sub)
        self.scroll = QScrollArea()
        self.scroll.setObjectName('panelScroll')
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        contenido = QWidget()
        contenido.setObjectName('panelContenido')
        lc = QVBoxLayout(contenido)
        lc.setContentsMargins(0, 0, 10, 0)   # (la barra de desplazamiento no tapa los valores)
        self.ficha = FichaEquipo(con_cabeza=False)
        self.ficha.poner(ficha_equipo)
        lc.addWidget(self.ficha)
        lc.addStretch(1)
        self.scroll.setWidget(contenido)
        lay.addWidget(self.scroll, 1)
        self.texto = texto_ficha(ficha_equipo, f"{nombre}{f' · {de_quien}' if de_quien else ''}")
        self.btn_copiar = boton('Copiar ficha', 'copiar')
        self.btn_copiar.setEnabled(bool(ficha_equipo))
        self.btn_copiar.clicked.connect(lambda: al_copiar(self.texto, 'Ficha copiada') if al_copiar else
                                        QGuiApplication.clipboard().setText(self.texto))
        cerrar = boton('Cerrar', tipo='primario')
        cerrar.setDefault(True)
        cerrar.clicked.connect(self.accept)
        lay.addLayout(fila_botones(cerrar, izquierda=(self.btn_copiar,)))
        self.resize(self.sizeHint())

    def sizeHint(self):
        """Del ancho fijo y del alto de lo que tiene, sin pasar de 820 px ni del 85 % de la pantalla (lo demás, con la barra)."""
        if self.alto_fijo:
            return QSize(self.ANCHO, self.alto_fijo)
        if self.scroll is None or self.scroll.widget() is None:   # (todavía armándose)
            return super().sizeHint()
        pantalla = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        alto = self.layout().sizeHint().height() - self.scroll.sizeHint().height() + self.scroll.widget().sizeHint().height()
        return QSize(self.ANCHO, max(360, min(alto, 820, round(pantalla.height() * 0.85))))


def traducir_recurrente(estado):
    if not estado:
        return '—'
    estado = str(estado)
    return f'{ESTADOS_RECURRENTE[estado]} ({estado})' if estado in ESTADOS_RECURRENTE else estado


HUELLA_EN_TITULO = re.compile(r'\s*·\s*[0-9A-Fa-f]{4}(?:-[0-9A-Fa-f]{4}){3}(?=»)')   # «PC-EDICION · 3F2A-91BC-…»


class EventoHistorial(QWidget):
    """Un evento del historial: un círculo con el ícono de su tipo, el título y la fecha; el detalle abajo. Cada evento
    dibuja su pedazo de la raya que une los círculos."""

    def __init__(self, evento, primero, ultimo):
        super().__init__()
        self.primero, self.ultimo = primero, ultimo
        nombre_icono, self.color = TIPOS_EVENTO.get(evento['tipo'], ('info', TEXTO_SUAVE))
        self._icono = pintar_icono(nombre_icono, self.color, 12, 2.3)
        self._arriba = 0 if primero else 4
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, self._arriba, 0, 0 if ultimo else 12)
        lay.setSpacing(2)
        cabeza = QHBoxLayout()
        cabeza.setSpacing(8)
        # (partible: un correo o un nombre de equipo muy largo se corta en líneas en vez de ensanchar el panel. La huella
        # del equipo no se muestra en el título: lo alargaba a tres o cuatro líneas; queda en el tooltip)
        completo = evento['titulo'] or (evento['tipo'] or 'Evento').capitalize()
        # (y un nombre corto entre «», como «LUCIA-PC», no se parte en el guion: pasa entero a la línea siguiente)
        corto = re.sub(r'«([^»]{1,22})»', lambda m: '«' + m.group(1).replace('-', '‑') + '»',
                       HUELLA_EN_TITULO.sub('', completo))
        titulo = etiqueta(partible(corto))
        titulo.setFont(fuente(13, QFont.Weight.DemiBold))
        titulo.setWordWrap(True)
        if titulo.text() != partible(completo):
            titulo.setToolTip(completo)
        cuando = etiqueta(fecha_corta(evento['fecha']), 'tenue')
        cuando.setToolTip(fecha_larga(evento['fecha']))
        cabeza.addWidget(titulo, 1)
        cabeza.addWidget(cuando, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(cabeza)
        if evento['detalle']:
            detalle = etiqueta(partible(evento['detalle']), 'suave')
            detalle.setFont(fuente(12))
            detalle.setWordWrap(True)
            detalle.setToolTip(evento['detalle'] if len(evento['detalle']) > 40 else '')
            lay.addWidget(detalle)

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = 11.0, self._arriba + 9.0
        p.setPen(QPen(QColor(BORDE_FUERTE), 1.4))
        if not self.primero:
            p.drawLine(QPointF(cx, 0), QPointF(cx, cy - 11))
        if not self.ultimo:
            p.drawLine(QPointF(cx, cy + 11), QPointF(cx, self.height()))
        fondo, borde = QColor(self.color), QColor(self.color)
        fondo.setAlpha(34)
        borde.setAlpha(110)
        p.setPen(QPen(borde, 1))
        p.setBrush(fondo)
        p.drawEllipse(QPointF(cx, cy), 10, 10)
        p.drawPixmap(QPointF(cx - 6, cy - 6), self._icono)


class Historial(QWidget):
    """La línea de tiempo del historial, del evento más nuevo al más viejo: muestra los primeros y «Ver todo»."""
    PRIMEROS = 8

    def __init__(self):
        super().__init__()
        self.eventos, self.todos = [], False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._lista = QVBoxLayout()
        self._lista.setSpacing(0)
        lay.addLayout(self._lista)
        self.vacio = etiqueta('Cargando historial…', 'tenue')
        self.vacio.setWordWrap(True)
        lay.addWidget(self.vacio)
        self.btn_mas = boton('Ver todo', 'abajo', chico=True)
        self.btn_mas.clicked.connect(self._todo)
        self.btn_mas.hide()
        lay.addWidget(self.btn_mas, 0, Qt.AlignmentFlag.AlignLeft)

    def poner(self, eventos):
        self.eventos, self.todos = list(eventos), False
        self._pintar()

    def mensaje(self, texto):
        self.eventos = []
        vaciar(self._lista)
        self.vacio.setText(texto)
        self.vacio.show()
        self.btn_mas.hide()

    def _todo(self):
        self.todos = True
        self._pintar()

    def _pintar(self):
        vaciar(self._lista)
        visibles = self.eventos if self.todos else self.eventos[:self.PRIMEROS]
        for i, e in enumerate(visibles):
            self._lista.addWidget(EventoHistorial(e, i == 0, i == len(visibles) - 1))
        self.vacio.setText('Todavía no hay nada en el historial.')
        self.vacio.setVisible(not self.eventos)
        faltan = len(self.eventos) - len(visibles)
        self.btn_mas.setText(f' Ver todo ({len(self.eventos)})')
        self.btn_mas.setVisible(faltan > 0)


def correo_reenvio(detalle):
    """A dónde manda admin.php la clave con reenviar_correo: solo si la licencia tiene una compra pagada o un canje, al
    correo de la licencia si es válido y, si no, al de esa compra o ese canje. None: el servidor no la reenviaría (por
    ejemplo, la licencia de una venta reembolsada)."""
    lic, ped, can = detalle.get('licencia') or {}, detalle.get('pedido'), detalle.get('canje')
    propio = correo_valido(lic.get('correo'))
    for otro in (ped if ped and ped['estado'] == 'pagado' else None, can):
        correo = otro and (propio or correo_valido(otro.get('correo')))
        if correo:
            return correo
    return None


def correo_aviso(detalle):
    """A dónde manda admin.php los avisos de actualización: el correo de la licencia si es válido; si no, el de su
    compra o su canje (contactos_licencias)."""
    lic, ped, can = detalle.get('licencia') or {}, detalle.get('pedido'), detalle.get('canje')
    for correo in (lic.get('correo'), ped and ped.get('correo'), can and can.get('correo')):
        correo = correo_valido(correo)
        if correo:
            return correo
    return None


class PanelDetalle(QFrame):
    """El panel de la licencia elegida: cliente (con «Editar»), clave, estado y límite de equipos, cada equipo con su
    versión, acciones, notas internas, pedido o canje e historial."""
    accion = Signal(str, object)   # nombre de la acción y sus datos
    copiar = Signal(str, str)      # texto que se copia y el aviso que se muestra
    reintentar = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName('panel')
        self.setMinimumWidth(340)
        self.origen, self.fila, self.detalle, self._ocupado = None, None, None, False
        self.ultima = None             # la última versión de CineCaptions (la pone la ventana)
        self.servidor_nuevo = None     # False: el admin.php publicado es el anterior (sin notas, historial ni avisos)
        self.avisos_licencia = None    # los avisos de actualización de esta licencia (None: todavía no se saben)
        self._borradores = {}          # licencia → nota escrita sin guardar (no se pierde al elegir otra fila)
        self._nota_guardada, self._nota_fecha = '', None
        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(2, 2, 2, 2)
        self.scroll = QScrollArea()
        self.scroll.setObjectName('panelScroll')
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        contenido = QWidget()
        contenido.setObjectName('panelContenido')
        self.lay = QVBoxLayout(contenido)
        self.lay.setContentsMargins(18, 18, 18, 18)
        self.lay.setSpacing(16)
        self.scroll.setWidget(contenido)
        exterior.addWidget(self.scroll)

        # Sin nada elegido
        self.vacio = QWidget()
        lv = QVBoxLayout(self.vacio)
        lv.setContentsMargins(24, 72, 24, 24)
        lv.setSpacing(8)
        lv.addWidget(cuadro_icono('llave', 'tenue', 48), 0, Qt.AlignmentFlag.AlignHCenter)
        lv.addSpacing(8)
        t1 = etiqueta('Elige una fila')
        t1.setFont(fuente(15, QFont.Weight.DemiBold))
        t1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t2 = etiqueta('Selecciona una fila de la tabla para ver su licencia, sus equipos, el historial y las acciones.',
                      'suave')
        t2.setWordWrap(True)
        t2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (t1, t2):
            lv.addWidget(w)
        lv.addStretch(1)

        # Cabecera: tipo, cliente (con «Editar») y correo (con «copiar» pegado al correo)
        self.cabeza = QWidget()
        lc = QVBoxLayout(self.cabeza)
        lc.setContentsMargins(0, 0, 0, 0)
        lc.setSpacing(4)
        fila_tipo = QHBoxLayout()
        self.tipo = etiqueta('', 'seccionTitulo', espaciado=True)
        self.girando = Indicador(16)
        fila_tipo.addWidget(self.tipo)
        fila_tipo.addStretch(1)
        fila_tipo.addWidget(self.girando)
        lc.addLayout(fila_tipo)
        fila_nombre = QHBoxLayout()
        fila_nombre.setSpacing(8)
        self.nombre = Recortada('', 'nombreCliente')
        self.btn_editar = boton('Editar', 'lapiz', chico=True)
        self.btn_editar.setToolTip('Cambiar el nombre o el correo del cliente')
        self.btn_editar.clicked.connect(lambda: self.accion.emit('editar', {}))
        # (2.3: sin la papelera de arriba: con las pestañas, «Eliminar venta» de Acciones ya se ve sin bajar; y está en el
        # clic derecho de la tabla)
        fila_nombre.addWidget(self.nombre, 1)
        fila_nombre.addWidget(self.btn_editar)
        lc.addLayout(fila_nombre)
        fila_correo = QHBoxLayout()
        fila_correo.setSpacing(2)
        self.correo = Recortada('', 'suave', ajustada=True)
        self.btn_correo = QPushButton()
        self.btn_correo.setProperty('tipo', 'icono')
        self.btn_correo.setIcon(icono('copiar', TEXTO_TENUE, 14))
        self.btn_correo.setIconSize(QSize(14, 14))
        self.btn_correo.setFixedSize(24, 24)
        self.btn_correo.setToolTip('Copiar el correo')
        self.btn_correo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_correo.clicked.connect(lambda: self.copiar.emit(self.correo.texto(), 'Correo copiado'))
        fila_correo.addWidget(self.correo)
        fila_correo.addWidget(self.btn_correo)
        fila_correo.addStretch(1)
        lc.addLayout(fila_correo)

        # Licencia: clave, límite de equipos y fecha
        self.sec_lic = Seccion('Licencia')
        fila_clave = QHBoxLayout()
        fila_clave.setSpacing(8)
        self.clave = etiqueta('', 'claveTexto', seleccionable=True)
        self.clave.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.btn_copiar = boton_cuadrado('copiar', 'Copiar la clave', 34)   # solo el ícono: la clave cabe en el panel
        self.btn_copiar.clicked.connect(lambda: self.copiar.emit(self.clave.text(), 'Clave copiada'))
        fila_clave.addWidget(self.clave, 1)
        fila_clave.addWidget(self.btn_copiar)
        self.sec_lic.lay.addLayout(fila_clave)
        self.fila_limite = QWidget()
        fl = QHBoxLayout(self.fila_limite)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(4)
        self.lbl_limite_texto = etiqueta('Equipos permitidos', 'suave')
        self.btn_menos = boton_cuadrado('menos', 'Permitir un equipo menos')
        self.lbl_limite = etiqueta('—')
        self.lbl_limite.setFont(fuente(15, QFont.Weight.DemiBold, cifras=True))
        self.lbl_limite.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_limite.setFixedWidth(30)
        self.btn_mas_limite = boton_cuadrado('mas', 'Permitir un equipo más')
        self.btn_menos.clicked.connect(lambda: self._cambiar_limite(-1))
        self.btn_mas_limite.clicked.connect(lambda: self._cambiar_limite(1))
        fl.addWidget(self.lbl_limite_texto)
        fl.addStretch(1)
        fl.addWidget(self.btn_menos)
        fl.addWidget(self.lbl_limite)
        fl.addWidget(self.btn_mas_limite)
        self.sec_lic.lay.addWidget(self.fila_limite)
        self.lic_meta = etiqueta('', 'tenue')
        self.lic_meta.setWordWrap(True)
        self.sin_lic = etiqueta('', 'suave')
        self.sin_lic.setWordWrap(True)
        self.sec_lic.lay.addWidget(self.lic_meta)
        self.sec_lic.lay.addWidget(self.sin_lic)

        # Pedido (con lo que diga Recurrente) y canje
        self.sec_ped = Seccion('Pedido')
        self.ficha_ped = Ficha()
        self.sec_ped.lay.addWidget(self.ficha_ped)
        self.caja_rec = QFrame()
        self.caja_rec.setObjectName('recurrente')
        lr = QVBoxLayout(self.caja_rec)
        lr.setContentsMargins(12, 12, 12, 12)
        lr.setSpacing(8)
        self.rec_titulo = etiqueta('', 'seccionTitulo', espaciado=True)
        self.ficha_rec = Ficha()
        lr.addWidget(self.rec_titulo)
        lr.addWidget(self.ficha_rec)
        self.sec_ped.lay.addWidget(self.caja_rec)
        self.sec_can = Seccion('Compra en Gumroad')
        self.ficha_can = Ficha()
        self.sec_can.lay.addWidget(self.ficha_can)

        # Equipos
        self.sec_eq = Seccion('Equipos')
        self.lista_eq = QVBoxLayout()
        self.lista_eq.setSpacing(8)
        self.sec_eq.lay.addLayout(self.lista_eq)
        self.eq_vacio = etiqueta('', 'tenue')
        self.sec_eq.lay.addWidget(self.eq_vacio)
        self.btn_liberar_todos = boton('Liberar todos', 'x', chico=True)
        self.btn_liberar_todos.clicked.connect(lambda: self.accion.emit('liberar_todos', {}))
        self.sec_eq.lay.addWidget(self.btn_liberar_todos, 0, Qt.AlignmentFlag.AlignLeft)   # abajo de la lista

        # Acciones
        self.sec_acc = Seccion('Acciones')
        self.btn_bloquear = boton('Bloquear licencia', 'candado')
        self.btn_reenviar = boton('Reenviar correo con la clave', 'correo')
        self.btn_avisar = boton('Avisar que actualice', 'megafono')
        self.nota_avisar = etiqueta('', 'tenue')
        self.nota_avisar.setWordWrap(True)
        self.btn_recurrente = boton('Consultar pago en Recurrente', 'tarjeta')
        self.btn_reembolso = boton('Marcar como reembolsado', 'reembolso', tipo='peligro')
        self.nota_reembolso = etiqueta('No devuelve el dinero: el reembolso se hace en el panel de Recurrente.', 'tenue')
        self.nota_reembolso.setWordWrap(True)
        # «Eliminar venta» (solo en Ventas): la quita de la lista y de los totales sin borrarla; si ya está eliminada,
        # «Restaurar venta». con_eliminar: None si todavía no se sabe si el servidor lo puede hacer, False si no.
        self.con_eliminar = None
        self.btn_eliminar = boton('Eliminar venta', 'basura', tipo='peligro')
        self.nota_eliminar = etiqueta('', 'tenue')
        self.nota_eliminar.setWordWrap(True)
        self.btn_bloquear.clicked.connect(self._bloquear_o_reactivar)
        self.btn_reenviar.clicked.connect(lambda: self.accion.emit('reenviar', {}))
        self.btn_avisar.clicked.connect(lambda: self.accion.emit('avisar', {}))
        self.btn_recurrente.clicked.connect(lambda: self.accion.emit('recurrente', {}))
        self.btn_reembolso.clicked.connect(lambda: self.accion.emit('reembolsar', {}))
        self.btn_eliminar.clicked.connect(self._eliminar_o_restaurar)
        lista = QVBoxLayout()   # (una lista de acciones: el texto a la izquierda, como un menú, y más juntas)
        lista.setSpacing(8)
        for w in (self.btn_bloquear, self.btn_reenviar, self.btn_avisar, self.nota_avisar, self.btn_recurrente,
                  self.btn_reembolso, self.nota_reembolso, self.btn_eliminar, self.nota_eliminar):
            if isinstance(w, QPushButton):
                w.setMinimumHeight(36)
                w.setProperty('lista', True)
            lista.addWidget(w)
        self.sec_acc.lay.addLayout(lista)

        # Notas internas (solo las ve el dueño)
        self.sec_notas = Seccion('Notas internas')
        self.txt_nota = QPlainTextEdit()
        self.txt_nota.setPlaceholderText('Algo que quieras recordar de este cliente. Solo lo ves tú.')
        self.txt_nota.setFixedHeight(108)   # unas 5 líneas sin barra de desplazamiento
        self.txt_nota.setTabChangesFocus(True)
        self.txt_nota.textChanged.connect(self._nota_cambiada)
        fila_nota = QHBoxLayout()
        fila_nota.setSpacing(8)
        self.lbl_nota = Recortada('', 'tenue')
        self.btn_nota = boton('Guardar nota', 'check', tipo='primario', chico=True)
        self.btn_nota.clicked.connect(self._guardar_nota)
        self._nota_enviada = None   # lo que decía la nota al apretar «Guardar nota»
        fila_nota.addWidget(self.lbl_nota, 1)
        fila_nota.addWidget(self.btn_nota)
        self.sec_notas.lay.addWidget(self.txt_nota)
        self.sec_notas.lay.addLayout(fila_nota)

        # Historial
        self.sec_hist = Seccion('Historial')
        self.historial = Historial()
        self.sec_hist.lay.addWidget(self.historial)

        # Error al cargar el detalle
        self.caja_error = QFrame()
        self.caja_error.setObjectName('banda')
        le = QVBoxLayout(self.caja_error)
        le.setContentsMargins(12, 12, 12, 12)
        le.setSpacing(8)
        self.error = etiqueta('')
        self.error.setWordWrap(True)
        reintentar = boton('Reintentar', 'actualizar', chico=True)
        reintentar.clicked.connect(self.reintentar)
        le.addWidget(self.error)
        le.addWidget(reintentar, 0, Qt.AlignmentFlag.AlignLeft)

        self.nota_servidor = etiqueta('Las notas, el historial, el límite de equipos y los avisos de actualización '
                                      'aparecen cuando subas el servidor nuevo (pagos/admin.php).', 'tenue')
        self.nota_servidor.setWordWrap(True)

        # 2.3 (propuesta A elegida por el dueño): pestañas en vez de un panel de ~1 800 px. «Licencia» (lo que más se usa:
        # la clave, los equipos y las acciones), «Pago» (el pedido, Recurrente y Gumroad) y «Notas e historial». Arriba de
        # las pestañas, el cliente, el error de carga y el aviso del servidor viejo.
        self._todas = (self.cabeza, self.caja_error, self.sec_lic, self.sec_eq, self.sec_acc, self.sec_notas, self.sec_ped,
                       self.sec_can, self.sec_hist, self.nota_servidor)
        self.PESTANAS = (('licencia', 'Licencia', (self.sec_lic, self.sec_eq, self.sec_acc)),
                         ('pago', 'Pago', (self.sec_ped, self.sec_can)),
                         ('notas', 'Notas e historial', (self.sec_notas, self.sec_hist)))
        self.barra_pestanas = QWidget()
        bp = QHBoxLayout(self.barra_pestanas)
        bp.setContentsMargins(0, 2, 0, 0)
        bp.setSpacing(22)
        self.grupo_pestanas = QButtonGroup(self)
        self.btn_pestana = {}
        self.pila = QStackedWidget()
        self._paginas = {}
        for n, (clave, texto, secciones) in enumerate(self.PESTANAS):
            b = QPushButton(texto)
            b.setObjectName('pestana')
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, c=clave: self._elegir_pestana(c, manual=True))
            self.grupo_pestanas.addButton(b, n)
            self.btn_pestana[clave] = b
            bp.addWidget(b)
            pagina = QWidget()
            lp = QVBoxLayout(pagina)
            lp.setContentsMargins(0, 0, 0, 0)
            lp.setSpacing(16)
            for s in secciones:
                lp.addWidget(s)
            lp.addStretch(1)
            self.pila.addWidget(pagina)
            self._paginas[clave] = pagina
        bp.addStretch(1)
        self._pestana_elegida = 'licencia'
        self._visibles = set()
        # (sin raya propia debajo de las pestañas: la primera sección de cada una ya trae la suya)
        for w in (self.vacio, self.cabeza, self.caja_error, self.nota_servidor, self.barra_pestanas):
            self.lay.addWidget(w)
        self.lay.addWidget(self.pila)
        self.lay.addStretch(1)
        self.mostrar_vacio()

    # --- Estados del panel
    def _secciones(self, visibles):
        self._visibles = set(visibles)
        for w in self._todas:
            w.setVisible(w in visibles)
        hay = [clave for clave, _t, secciones in self.PESTANAS if any(s in self._visibles for s in secciones)]
        for clave, b in self.btn_pestana.items():
            b.setVisible(clave in hay)
        for w in (self.barra_pestanas, self.pila):
            w.setVisible(bool(hay))
        if hay:
            self._elegir_pestana(self._pestana_elegida if self._pestana_elegida in hay else hay[0])

    def _elegir_pestana(self, clave, manual=False):
        if manual:
            self._pestana_elegida = clave
        self.btn_pestana[clave].setChecked(True)
        self.pila.setCurrentWidget(self._paginas[clave])
        # (el alto de la pila es el de la pestaña que se ve: así no queda espacio vacío debajo de una corta)
        for c, pagina in self._paginas.items():
            pagina.setSizePolicy(QSizePolicy.Policy.Preferred,
                                 QSizePolicy.Policy.Preferred if c == clave else QSizePolicy.Policy.Ignored)
        self.pila.adjustSize()

    def visible(self, seccion):
        """¿Esa sección se muestra (en su pestaña, aunque la pestaña que se ve sea otra)? Para las pruebas y el estado."""
        return seccion in self._visibles and not seccion.isHidden()

    def _licencia_id(self):
        lic = (self.detalle or {}).get('licencia')
        return lic['id'] if lic else (self.fila or {}).get('licencia_id')

    def mostrar_vacio(self):
        self._guardar_borrador()
        self.origen, self.fila, self.detalle, self.avisos_licencia = None, None, None, None
        self.girando.activar(False)
        self._secciones(())
        self.vacio.show()

    def mostrar_fila(self, origen, fila):
        """Lo que ya se sabe por la tabla; el resto llega con «detalle»."""
        self._guardar_borrador()
        self.origen, self.fila, self.detalle, self.avisos_licencia = origen, fila, None, None
        self.vacio.hide()
        if origen == 'venta':
            self.tipo.setText(f"VENTA · PEDIDO #{fila['id']}")
        elif origen == 'canje':
            self.tipo.setText(f"CANJE DE GUMROAD #{fila['id']}")
        else:
            self.tipo.setText(f"LICENCIA #{fila['licencia_id']}")
        nombre = fila.get('nombre') if origen in ('venta', 'canje') else fila.get('cliente')
        self.nombre.poner(nombre or 'Sin nombre')
        self.correo.poner(fila.get('correo') or 'Sin correo')
        self.btn_correo.setVisible(bool(fila.get('correo')))
        self.btn_editar.hide()
        self._poner_licencia(fila.get('clave'), fila.get('licencia_estado'), fila.get('limite'), None)
        self.fila_limite.hide()
        self.caja_rec.hide()
        vaciar(self.lista_eq)
        self.eq_vacio.setText('Cargando equipos…')
        self.eq_vacio.show()
        self.btn_liberar_todos.hide()
        self.sec_eq.poner_titulo('Equipos')
        self.historial.mensaje('Cargando historial…')
        self.sec_hist.poner_titulo('Historial')
        self._secciones((self.cabeza, self.sec_lic) + ((self.sec_eq,) if fila.get('licencia_id') else ()))
        self.girando.activar(True)
        self.scroll.verticalScrollBar().setValue(0)

    def mostrar_error(self, texto):
        self.girando.activar(False)
        self.error.setText(f'No se pudo cargar el detalle. {texto}')
        self.caja_error.show()
        self.sec_eq.hide()

    def mostrar_detalle(self, detalle):
        # Si es otra vez la misma licencia (al actualizar cada 2 minutos o después de una acción), lo que se estaba
        # escribiendo en las notas queda como borrador y no se pierde
        self._guardar_borrador()
        self.detalle = detalle
        self.girando.activar(False)
        lic, ped, can, equipos = detalle['licencia'], detalle['pedido'], detalle['canje'], detalle['equipos']
        if detalle.get('version_ultima'):
            self.ultima = detalle['version_ultima']
        if self.origen == 'venta' and ped:
            self.tipo.setText(f"VENTA · PEDIDO #{ped['id']}" + (' · ELIMINADA' if venta_eliminada(ped) else ''))
        if self.origen == 'licencia':
            self.tipo.setText(f"LICENCIA · COMPRA #{ped['id']}" if ped else 'LICENCIA · CANJE DE GUMROAD' if can
                              else f"LICENCIA #{lic['id'] if lic else ''}")
        # El nombre y el correo de la licencia mandan (editar_cliente los cambia ahí y en sus compras)
        otra = ped if self.origen == 'venta' and ped else (can or ped or self.fila or {})
        nombre = (lic or {}).get('nombre') or otra.get('nombre') or (self.fila or {}).get('cliente')
        correo = (lic or {}).get('correo') or otra.get('correo')
        self.nombre.poner(nombre or 'Sin nombre')
        self.correo.poner(correo or 'Sin correo')
        self.btn_correo.setVisible(bool(correo))
        self.btn_editar.setVisible(bool(lic) and self.servidor_nuevo is not False)
        if lic:
            self._poner_licencia(lic['clave'], lic['estado'], lic['limite'], lic['creada'], len(equipos))
        else:
            self._poner_licencia(None, None, None, None)
        visibles = [self.cabeza, self.sec_lic]
        nuevo = self.servidor_nuevo is not False
        if lic:
            self._poner_equipos(equipos, lic['limite'])
            visibles.append(self.sec_eq)
            if nuevo:
                self._poner_nota(lic)
                visibles.append(self.sec_notas)
        if ped:
            self._poner_pedido(ped)
            visibles.append(self.sec_ped)
        if can:
            self._poner_canje(can)
            visibles.append(self.sec_can)
        visibles.append(self.sec_acc)
        if lic and nuevo:
            visibles.append(self.sec_hist)
        if lic and not nuevo:
            visibles.append(self.nota_servidor)
        self._secciones(visibles)
        self._botones()

    def mostrar_historial(self, eventos):
        self.historial.poner(eventos)
        self.sec_hist.poner_titulo('Historial', f'<span style="color:{TEXTO_TENUE}; font-size:12px">'
                                                f'{plural(len(eventos), "evento", "eventos")}</span>' if eventos else '')

    def historial_error(self, texto):
        self.historial.mensaje(texto)
        self.sec_hist.poner_titulo('Historial')

    def poner_avisos(self, avisos):
        self.avisos_licencia = list(avisos)
        self._botones()

    def aviso_de(self, version):
        """El último aviso que SÍ le llegó de esa versión (o None)."""
        partes = partes_version(version)
        for a in self.avisos_licencia or []:   # vienen del más nuevo al más viejo
            if a['ok'] and partes and partes_version(a['version']) == partes:
                return a
        return None

    def necesita_aviso(self):
        """Si algún equipo está desactualizado o sin datos (y se sabe cuál es la última versión)."""
        d = self.detalle or {}
        lic = d.get('licencia')
        if not lic or lic['estado'] != 'activa' or not texto_version(self.ultima) or self.servidor_nuevo is False:
            return False
        return any((e.get('estado_version') or estado_de_version(e.get('version'), self.ultima))
                   in ('desactualizado', 'sin_datos') for e in d.get('equipos') or [])

    def mostrar_recurrente(self, info):
        self.rec_titulo.setText(f'LO QUE DICE RECURRENTE · {dt.datetime.now():%H:%M}')
        estado_pago = info.get('pago_estado')
        color = EXITO if estado_pago == 'succeeded' or (info.get('estado') == 'paid' and not estado_pago) else AVISO
        self.ficha_rec.poner([
            ('Estado', traducir_recurrente(info.get('estado')), color if info.get('estado') == 'paid' else AVISO),
            ('Total', dinero(entero_o_nada(info.get('total')), info.get('moneda')) if info.get('total') is not None else '—', None),
            ('Pago', texto_o_nada(info.get('pago_id')) or '—', None),
            ('Estado del pago', traducir_recurrente(estado_pago), color if estado_pago else None),
            ('Creado', fecha_larga(info.get('creado')), None)])
        self.caja_rec.show()
        if self.visible(self.sec_ped):
            self._elegir_pestana('pago')   # (2.3: lo que dijo Recurrente está en «Pago»: se muestra ahí)
        self.sec_ped.show()
        QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(self.caja_rec, 0, 16))

    def set_ocupado(self, ocupado):
        self._ocupado = ocupado
        self.girando.activar(ocupado)
        self._botones()

    def set_servidor(self, nuevo):
        self.servidor_nuevo = nuevo
        if self.detalle:
            self.mostrar_detalle(self.detalle)

    def set_eliminar(self, puede):
        """Si el servidor sabe eliminar ventas (True), no (False: el admin.php de antes) o todavía no se sabe (None)."""
        if puede != self.con_eliminar:
            self.con_eliminar = puede
            self._botones()

    # --- Partes
    def _poner_licencia(self, clave, estado, limite, creada, n_equipos=None):
        if clave:
            self.clave.setText(clave)
            self.clave.show()
            self.btn_copiar.show()
            self.sin_lic.hide()
            self.sec_lic.poner_titulo('Licencia', pastilla_html('Activa', EXITO) if estado == 'activa'
                                      else pastilla_html('Bloqueada', PELIGRO) if estado else '')
            nuevo = self.servidor_nuevo is not False and limite is not None and n_equipos is not None
            self.fila_limite.setVisible(nuevo)
            partes = []
            if limite is not None:
                self.lbl_limite.setText(str(limite))
                if not nuevo:
                    partes.append(f"Sirve para {plural(limite, 'computadora', 'computadoras')}")
            if creada:
                partes.append(f'Creada el {fecha_dia(creada)}' if not partes else f'creada el {fecha_dia(creada)}')
            self.lic_meta.setText(' · '.join(partes))
            self.lic_meta.setVisible(bool(partes))
        else:
            self.clave.hide()
            self.btn_copiar.hide()
            self.lic_meta.hide()
            self.fila_limite.hide()
            self.sec_lic.poner_titulo('Licencia')
            pendiente = self.origen == 'venta' and (self.fila or {}).get('estado') == 'pendiente'
            self.sin_lic.setText('Este pedido no tiene licencia: el pago no se completó.' if pendiente
                                 else 'No tiene una licencia CC- asociada.')
            self.sin_lic.show()

    def _poner_equipos(self, equipos, limite):
        vaciar(self.lista_eq)
        self.sec_eq.poner_titulo(f'Equipos · {len(equipos)} de {limite}',
                                 pastilla_html('Lleno', AVISO) if limite and len(equipos) >= limite else '')
        for e in equipos:
            self.lista_eq.addWidget(FilaEquipo(e, self.ultima, lambda eq: self.accion.emit('liberar_equipo', eq),
                                               self.servidor_nuevo is not False,
                                               al_ficha=lambda eq: self.accion.emit('ficha_equipo', eq)))   # (2.4)
        self.eq_vacio.setText('Ningún equipo activado todavía.')
        self.eq_vacio.setVisible(not equipos)
        self.btn_liberar_todos.setVisible(len(equipos) > 1)

    def _poner_pedido(self, ped):
        texto, color = ESTADOS_VENTA.get(ped['estado'], (ped['estado'] or '—', TEXTO_SUAVE))
        eliminada = venta_eliminada(ped)
        self.sec_ped.poner_titulo(f"Pedido #{ped['id']}", pastilla_html(texto, TEXTO_TENUE if eliminada else color)
                                  + ('&nbsp;&nbsp;' + pastilla_html('Eliminada', TEXTO_TENUE) if eliminada else ''))
        filas = [('Monto', dinero(ped['monto'], ped['moneda']), None)]
        if ped.get('cupon'):   # 2.8: el cupón con que se compró y lo que se descontó
            descuento = f" · −{dinero(ped['descuento'], ped['moneda'])}" if ped.get('descuento') else ''
            filas.append(('Cupón', ped['cupon'] + (' · licencia gratis' if ped.get('monto') == 0 else descuento),
                          VIOLETA_CLARO))
        if eliminada:
            filas.append(('Eliminada', f"{fecha_larga(ped['eliminada'])} · no cuenta en los totales", TEXTO_SUAVE))
        if ped['pagado']:
            filas.append(('Pagado', fecha_larga(ped['pagado']), None))
        filas.append(('Creado', fecha_larga(ped['creado']), None))
        filas.append(('Checkout', ped['checkout_id'] or '—', None))
        if ped['pago_ids']:
            filas.append(('Pago', ped['pago_ids'], None))
        if ped['estado'] != 'pendiente':
            filas.append(('Correo con la clave', 'Enviado' if ped['correo_enviado'] else 'No enviado',
                          None if ped['correo_enviado'] else AVISO))
        self.ficha_ped.poner(filas)

    def _poner_canje(self, can):
        texto, color = BLOQUEOS_CANJE.get(can['bloqueo'], ((can['bloqueo'] or '').capitalize(), AVISO))
        self.sec_can.poner_titulo('Compra en Gumroad', pastilla_html(texto, color))
        self.ficha_can.poner([('Canjeado', fecha_larga(can['creado']), None),
                              ('Venta en Gumroad', fecha_larga(can['fecha_venta'], utc=True), None),
                              ('Último canje', fecha_larga(can['ultimo']), None),
                              ('En Gumroad', texto if can['bloqueo'] else 'Compra vigente', color if can['bloqueo'] else None)])

    # --- Notas internas
    def _poner_nota(self, lic):
        self._nota_guardada = lic.get('nota') or ''
        texto = self._borradores.pop(lic['id'], None)
        texto = self._nota_guardada if texto is None else texto
        if self.txt_nota.toPlainText() != texto:   # (si no cambió no se toca: el cursor queda donde estaba)
            self.txt_nota.blockSignals(True)
            self.txt_nota.setPlainText(texto)
            self.txt_nota.blockSignals(False)
        self._nota_fecha = lic.get('nota_fecha')
        self._nota_cambiada()

    def _guardar_nota(self):
        self._nota_enviada = self.txt_nota.toPlainText()
        self.accion.emit('nota', self._nota_enviada.strip())

    def nota_guardada(self, resultado):
        """Llegó la respuesta de «nota»: lo que quedó guardado en el servidor (admin.php quita espacios de más). Si
        mientras se guardaba se siguió escribiendo, eso queda como borrador sin guardar."""
        lic = (self.detalle or {}).get('licencia')
        if lic:
            lic['nota'], lic['nota_fecha'] = resultado.get('nota'), resultado.get('nota_fecha')
            self._borradores.pop(lic['id'], None)
            if self.txt_nota.toPlainText() != self._nota_enviada:
                self._borradores[lic['id']] = self.txt_nota.toPlainText()
            self._poner_nota(lic)

    def _nota_cambiada(self):
        texto = self.txt_nota.toPlainText()
        if len(texto) > MAX_TEXTO:   # no deja pasar del máximo de admin.php
            self.txt_nota.blockSignals(True)
            self.txt_nota.setPlainText(texto[:MAX_TEXTO])
            self.txt_nota.blockSignals(False)
            cursor = self.txt_nota.textCursor()
            cursor.setPosition(MAX_TEXTO)
            self.txt_nota.setTextCursor(cursor)
            texto = texto[:MAX_TEXTO]
        cambio = texto.strip() != self._nota_guardada.strip()
        if cambio:
            self.lbl_nota.poner(f'Sin guardar · {len(texto):,} / {MAX_TEXTO:,}')
        elif self._nota_guardada:
            fecha = getattr(self, '_nota_fecha', None)
            self.lbl_nota.poner(f'Guardada {fecha_corta(fecha).lower()}' if fecha else 'Guardada')   # (corto: cabe junto al botón)
        else:
            self.lbl_nota.poner('Sin nota')
        self.lbl_nota.setStyleSheet(f'color: {AVISO};' if cambio else '')
        self.btn_nota.setEnabled(cambio and not self._ocupado)

    def _guardar_borrador(self):
        lid = self._licencia_id() if self.detalle else None
        if lid and self.txt_nota.toPlainText().strip() != self._nota_guardada.strip():
            self._borradores[lid] = self.txt_nota.toPlainText()

    # --- Límite de equipos
    def _cambiar_limite(self, paso):
        lic = (self.detalle or {}).get('licencia')
        if lic:
            nuevo = lic['limite'] + paso
            if LIMITE_EQUIPOS[0] <= nuevo <= LIMITE_EQUIPOS[1]:
                self.accion.emit('limite', nuevo)

    def _botones(self):
        d = self.detalle or {}
        lic, ped = d.get('licencia'), d.get('pedido')
        libre = not self._ocupado and self.detalle is not None
        self.btn_bloquear.setVisible(bool(lic))
        if lic:
            activa = lic['estado'] == 'activa'
            self.btn_bloquear.setText(' Bloquear licencia' if activa else ' Reactivar licencia')
            self.btn_bloquear.setIcon(icono('candado' if activa else 'abierto', TEXTO_SUAVE, 16))
            n = len(d.get('equipos') or [])
            self.btn_menos.setEnabled(libre and lic['limite'] > max(LIMITE_EQUIPOS[0], n))
            self.btn_menos.setToolTip(f'Primero libera equipos: hay {n} activados.' if n and lic['limite'] <= n
                                      else 'Permitir un equipo menos')
            self.btn_mas_limite.setEnabled(libre and lic['limite'] < LIMITE_EQUIPOS[1])
        correo = correo_reenvio(d) if lic else None
        self.btn_reenviar.setVisible(bool(lic))
        self.btn_reenviar.setEnabled(libre and bool(correo))
        self.btn_reenviar.setToolTip(f'Se manda a {correo}' if correo else
                                     'Solo se reenvía la clave de una compra pagada o de un canje con un correo válido.')
        # «Avisar que actualice»: si algún equipo está desactualizado o sin datos. Si ya le llegó el aviso de esa
        # versión, el botón ofrece reenviarlo (forzar=true).
        version = texto_version(self.ultima)
        avisar = self.necesita_aviso()
        self.btn_avisar.setVisible(avisar)
        ya = self.aviso_de(version) if avisar else None
        self.btn_avisar.setText(f' Reenviar aviso de la {version}' if ya else f' Avisar que actualice a la {version}')
        aviso = correo_aviso(d) if lic else None
        self.btn_avisar.setEnabled(libre and bool(aviso))
        self.btn_avisar.setToolTip(f'Se manda a {aviso}' if aviso else 'La licencia no tiene un correo válido.')
        self.nota_avisar.setText(f"Ya le avisaste de la {version} {fecha_frase(ya['enviado'])}." if ya else '')
        self.nota_avisar.setVisible(bool(ya))
        self.btn_recurrente.setVisible(bool(ped and ped['checkout_id']))
        eliminada = venta_eliminada(ped)
        self.btn_reembolso.setVisible(bool(ped and ped['estado'] == 'pagado') and not eliminada)
        self.nota_reembolso.setVisible(self.btn_reembolso.isVisibleTo(self.sec_acc))
        self._boton_eliminar(ped, eliminada, libre)
        self.sec_acc.setVisible(self.detalle is not None and any(
            b.isVisibleTo(self.sec_acc) for b in (self.btn_bloquear, self.btn_reenviar, self.btn_avisar, self.btn_recurrente,
                                                  self.btn_reembolso, self.btn_eliminar)))
        for b in (self.btn_bloquear, self.btn_recurrente, self.btn_reembolso, self.btn_liberar_todos, self.btn_editar):
            b.setEnabled(libre)
        self.btn_nota.setEnabled(libre and self.txt_nota.toPlainText().strip() != self._nota_guardada.strip())
        for i in range(self.lista_eq.count()):
            w = self.lista_eq.itemAt(i).widget()
            if isinstance(w, FilaEquipo):
                w.btn.setEnabled(libre)

    def _boton_eliminar(self, ped, eliminada, libre):
        """«Eliminar venta» (rojo, como las acciones que se pueden lamentar) o, si ya está eliminada, «Restaurar venta»
        (normal: deshace). Solo para una venta elegida en Ventas. Sin el servidor nuevo queda apagado y lo dice abajo."""
        es_venta = self.origen == 'venta' and bool(ped)
        self.btn_eliminar.setVisible(es_venta)
        if not es_venta:
            self.nota_eliminar.hide()
            return
        tipo = None if eliminada else 'peligro'
        if self.btn_eliminar.property('tipo') != tipo:
            self.btn_eliminar.setProperty('tipo', tipo)
            repulir(self.btn_eliminar)
        self.btn_eliminar.setText(' Restaurar venta' if eliminada else ' Eliminar venta')
        color = TEXTO_SUAVE if eliminada else '#ff9a9a'
        self.btn_eliminar.setIcon(icono('restaurar' if eliminada else 'basura', color, 16))
        puede = self.con_eliminar is not False
        self.btn_eliminar.setEnabled(libre and puede)
        if not puede:
            nota = 'Para eliminar ventas falta subir el pagos/admin.php nuevo.'
        elif eliminada:
            nota = f"La eliminaste {fecha_frase(ped['eliminada'])}: no sale en la lista ni en los totales."
        else:
            nota = 'Sale de la lista y de los totales, pero no se borra: la puedes restaurar.'
        self.btn_eliminar.setToolTip('Vuelve a la lista y a los totales' if eliminada else
                                     'La quita de la lista y de los totales (no se borra)')
        self.nota_eliminar.setText(nota)
        self.nota_eliminar.setVisible(True)

    def _eliminar_o_restaurar(self):
        ped = (self.detalle or {}).get('pedido')
        if ped and self.origen == 'venta':
            self.accion.emit('restaurar' if venta_eliminada(ped) else 'eliminar', {})

    def _bloquear_o_reactivar(self):
        lic = (self.detalle or {}).get('licencia')
        if lic:
            self.accion.emit('bloquear' if lic['estado'] == 'activa' else 'reactivar', {})


# ---------------------------------------------------------------- Vista «Por usuario» de la página Errores

class FilaErrorCliente(QAbstractButton):
    """Un error en la vista «Por usuario»: el punto (rojo si es un error sin ver, naranja si es un aviso sin ver, gris si
    ya se vio), el título y el mensaje y, a la derecha, cuándo pasó por última vez y cuántas veces. El elegido va con el
    fondo violeta de las filas elegidas."""
    ALTO = 52

    def __init__(self, error):
        super().__init__()
        self.error = error
        self.elegido = False
        self._encima = False
        self.setFixedHeight(self.ALTO)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAccessibleName(error['titulo'] or error['mensaje'] or 'Error')
        self.setToolTip('\n'.join(x for x in (error['titulo'], error['mensaje'] if error['mensaje'] != error['titulo'] else None,
                                              f"Última vez: {fecha_larga(error['ultima'])}") if x))

    def poner_elegido(self, elegido):
        if elegido != self.elegido:
            self.elegido = elegido
            self.update()

    def enterEvent(self, evento):
        self._encima = True
        self.update()
        super().enterEvent(evento)

    def leaveEvent(self, evento):
        self._encima = False
        self.update()
        super().leaveEvent(evento)

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(self.rect())
        e = self.error
        p.setPen(Qt.PenStyle.NoPen)
        if self.elegido:
            p.setBrush(QColor(ELEGIDA))
            p.drawRoundedRect(r, RADIO_CONTROL, RADIO_CONTROL)
        elif self.isDown() or self._encima:
            p.setBrush(QColor(255, 255, 255, 6 if self.isDown() else 9))
            p.drawRoundedRect(r, RADIO_CONTROL, RADIO_CONTROL)
        if self.hasFocus():
            p.setPen(QPen(QColor(VIOLETA), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), RADIO_CONTROL - 1, RADIO_CONTROL - 1)
            p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(BORDE_FUERTE if e['visto'] else NIVELES_ERROR[e['nivel']][1]))
        p.drawEllipse(QPointF(14, r.center().y()), 3.5, 3.5)
        f1 = fuente(13, QFont.Weight.Medium if e['visto'] else QFont.Weight.DemiBold)
        f2, f3 = fuente(12), con_cifras_tabulares(fuente(12))
        cuando, veces = hace(e['ultima']), plural(e['veces'], 'vez', 'veces')
        fm3 = QFontMetrics(f3)
        derecha = r.width() - 12
        limite = derecha - max(fm3.horizontalAdvance(cuando), fm3.horizontalAdvance(veces)) - 14
        izquierda = 28.0
        ancho = int(max(0.0, limite - izquierda))
        alinear = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        p.setFont(f1)
        p.setPen(QColor(TEXTO_SUAVE if e['visto'] else TEXTO))
        p.drawText(QRectF(izquierda, 8, ancho, 18), alinear, QFontMetrics(f1).elidedText(
            una_linea(e['titulo'] or e['mensaje']) or 'Sin título', Qt.TextElideMode.ElideRight, ancho))
        abajo = una_linea(e['mensaje']) if e['mensaje'] and e['mensaje'] != e['titulo'] else (e['origen'] or '')
        p.setFont(f2)
        p.setPen(QColor(TEXTO_TENUE))
        p.drawText(QRectF(izquierda, 27, ancho, 17), alinear,
                   QFontMetrics(f2).elidedText(abajo, Qt.TextElideMode.ElideRight, ancho))
        a_la_derecha = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        p.setFont(f3)
        p.setPen(QColor(TEXTO_SUAVE))
        p.drawText(QRectF(limite, 8, derecha - limite, 18), a_la_derecha, cuando)
        p.setPen(QColor(AVISO if e['veces'] > 1 and not e['visto'] else TEXTO_TENUE))
        p.drawText(QRectF(limite, 27, derecha - limite, 17), a_la_derecha, veces)


class ErroresCliente(QFrame):
    """La vista «Por usuario», a la par de la lista de clientes: el cliente elegido, «Marcar todo lo de este cliente como
    visto» y sus errores agrupados por equipo (el nombre, la versión de CineCaptions y el sistema), del más reciente al
    más viejo (primero el equipo con el error más reciente). Al elegir uno, su informe sale en el panel de la derecha."""
    elegido = Signal(object)   # el error que se eligió
    todo_visto = Signal()

    def __init__(self, en_bloque=False):
        """en_bloque (2.3, propuesta A): un cliente DENTRO de la lista «Por cliente» (ErroresPorCliente): cabecera compacta
        (iniciales, nombre, su equipo, «N sin ver» y «Marcar visto») y sus errores debajo, sin marco ni barra propia."""
        super().__init__()
        self.en_bloque = en_bloque
        self.setObjectName('bloqueCliente' if en_bloque else 'marcoTabla')
        self.licencia_id = None
        self.filas = {}   # id del error → su fila
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0) if en_bloque else lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(0)
        self.cabeza = QWidget()
        self.nombre = Recortada('')
        self.nombre.setFont(fuente(14 if en_bloque else 15, QFont.Weight.DemiBold))
        self.sub = Recortada('', 'tenue')
        self.btn_todo = boton('Marcar visto' if en_bloque else 'Marcar todo lo de este cliente como visto', 'check', chico=True)
        self.btn_todo.setToolTip('Sus errores sin ver dejan de salir en «Sin ver» y en el contador de la barra')
        self.btn_todo.clicked.connect(self.todo_visto)
        if en_bloque:
            lc = QHBoxLayout(self.cabeza)
            lc.setContentsMargins(10, 12, 8, 6)
            lc.setSpacing(10)
            self.iniciales = QLabel()
            self.iniciales.setObjectName('iniciales')
            self.iniciales.setFixedSize(30, 30)
            self.iniciales.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.iniciales.setFont(fuente(11, QFont.Weight.Bold))
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(self.nombre)
            col.addWidget(self.sub)
            self.pastilla = Pastilla()
            lc.addWidget(self.iniciales, 0, Qt.AlignmentFlag.AlignTop)
            lc.addLayout(col, 1)
            lc.addWidget(self.pastilla, 0, Qt.AlignmentFlag.AlignVCenter)
            lc.addWidget(self.btn_todo, 0, Qt.AlignmentFlag.AlignVCenter)
        else:
            lc = QVBoxLayout(self.cabeza)
            lc.setContentsMargins(16, 14, 16, 12)
            lc.setSpacing(2)
            lc.addWidget(self.nombre)
            lc.addWidget(self.sub)
            lc.addSpacing(8)
            lc.addWidget(self.btn_todo, 0, Qt.AlignmentFlag.AlignLeft)
        self.raya = divisor()
        self.scroll = QScrollArea()
        self.scroll.setObjectName('panelScroll')
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        contenido = QWidget()
        contenido.setObjectName('panelContenido')
        self.lista = QVBoxLayout(contenido)
        self.lista.setContentsMargins(48, 0, 4, 6) if en_bloque else self.lista.setContentsMargins(8, 4, 8, 8)
        self.lista.setSpacing(2)
        self.vacio = VacioLista('usuario')
        if en_bloque:   # (sin barra propia: la lista de afuera es la que se desplaza)
            self.scroll.hide()
            lay.addWidget(self.cabeza)
            lay.addWidget(contenido)
            self.raya.hide()
            self.vacio.hide()
            return
        self.scroll.setWidget(contenido)
        for w in (self.cabeza, self.raya):
            lay.addWidget(w)
        lay.addWidget(self.scroll, 1)
        lay.addWidget(self.vacio, 1)
        self.mostrar_vacio('')

    def mostrar_vacio(self, mensaje):
        self.licencia_id = None
        vaciar(self.lista)
        self.filas = {}
        for w in (self.cabeza, self.raya, self.scroll):
            w.hide()
        self.vacio.poner(mensaje)
        self.vacio.show()

    def poner(self, errores, elegido=None):
        """errores: todos los del cliente (también los ya vistos), del más reciente al más viejo."""
        primero = errores[0]
        mismo = self.licencia_id == primero['licencia_id']
        posicion = self.scroll.verticalScrollBar().value() if mismo and not self.en_bloque else 0
        self.licencia_id = primero['licencia_id']
        quien = primero['cliente'] or primero['correo'] or f"Licencia #{primero['licencia_id']}"
        self.nombre.poner(quien)
        sin_ver = sum(1 for e in (getattr(self, '_todos', None) or errores) if not e['visto'])
        self.btn_todo.setEnabled(sin_ver > 0)
        equipos = {}
        for e in errores:   # (el equipo con el error más reciente queda primero)
            equipos.setdefault(e['equipo'], []).append(e)
        if self.en_bloque:
            letras = [p[0] for p in re.findall(r'[^\W\d_]+', quien)][:2]
            self.iniciales.setText(''.join(letras).upper() or '?')
            reciente = errores[0]
            version = texto_version(reciente['version'])
            self.sub.poner(' · '.join(x for x in (equipo_de_error(reciente), version, texto_so(reciente['so'])) if x)
                           if len(equipos) == 1 else f"{len(equipos)} equipos · {primero['correo'] or primero['clave'] or ''}")
            self.pastilla.poner(f'{sin_ver} sin ver' if sin_ver else 'Todo visto', PELIGRO if sin_ver else TEXTO_TENUE)
            self.btn_todo.setVisible(sin_ver > 0)
        else:
            self.sub.poner(' · '.join(x for x in (primero['correo'] if primero['cliente'] else None, primero['clave']) if x))
        vaciar(self.lista)
        self.filas = {}
        for n, lista in enumerate(equipos.values()):
            reciente = lista[0]
            version = texto_version(reciente['version'])
            datos = ' · '.join(x for x in (f'CineCaptions {version}' if version else None, texto_so(reciente['so']),
                                           plural(len(lista), 'error', 'errores')) if x)
            if self.en_bloque and len(equipos) == 1:   # (su único equipo ya va en la cabecera del cliente)
                for e in lista:
                    self._fila(e, elegido)
                continue
            cabeza = etiqueta('', plano=False)
            cabeza.setTextFormat(Qt.TextFormat.RichText)
            cabeza.setWordWrap(True)
            cabeza.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            cabeza.setContentsMargins(6, 8 if n == 0 else 16, 6, 4)
            cabeza.setText(f'<span style="font-weight:600">{html.escape(partible(equipo_de_error(reciente)))}</span>'
                           f'&nbsp;&nbsp;<span style="color:{TEXTO_TENUE}; font-size:12px">{html.escape(datos)}</span>')
            self.lista.addWidget(cabeza)
            for e in lista:
                self._fila(e, elegido)
        if self.en_bloque:
            return
        self.lista.addStretch(1)
        self.vacio.hide()
        for w in (self.cabeza, self.raya, self.scroll):
            w.show()
        if posicion:
            QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(posicion))   # (ya con el alto nuevo)

    def _fila(self, e, elegido):
        fila = FilaErrorCliente(e)
        fila.poner_elegido(e['id'] == elegido)
        fila.clicked.connect(lambda _c=False, error=e: self.elegido.emit(error))
        self.lista.addWidget(fila)
        self.filas[e['id']] = fila

    def marcar(self, ident):
        """Ilumina el error elegido (None: ninguno)."""
        for clave, fila in self.filas.items():
            fila.poner_elegido(clave == ident)
        if ident in self.filas and not self.en_bloque:
            self.scroll.ensureWidgetVisible(self.filas[ident], 0, 8)


class ErroresPorCliente(QFrame):
    """2.3 (propuesta A elegida por el dueño): la vista «Por cliente» en UNA columna: cada cliente (los que pasan el
    filtro, en el orden de su lista) con sus errores debajo (ErroresCliente en_bloque). Así el panel del error de la
    derecha puede ser ancho. La lista de clientes (tabla_cli) sigue detrás, escondida: manda el orden, el filtro y el
    cliente elegido. API como la de ErroresCliente: filas (id → fila, de todos), marcar(), elegido, todo_visto(licencia)."""
    elegido = Signal(object)
    todo_visto = Signal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName('marcoTabla')
        self.bloques = {}   # licencia_id → ErroresCliente
        self.filas = {}
        self.licencia_id = None   # el cliente elegido
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self.scroll = QScrollArea()
        self.scroll.setObjectName('panelScroll')
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        contenido = QWidget()
        contenido.setObjectName('panelContenido')
        self.lista = QVBoxLayout(contenido)
        self.lista.setContentsMargins(6, 2, 6, 8)
        self.lista.setSpacing(4)
        self.scroll.setWidget(contenido)
        self.vacio = VacioLista('usuario')
        lay.addWidget(self.scroll, 1)
        lay.addWidget(self.vacio, 1)
        self.mostrar_vacio('')

    def mostrar_vacio(self, mensaje):
        vaciar(self.lista)
        self.bloques, self.filas = {}, {}
        self.licencia_id = None
        self.scroll.hide()
        self.vacio.poner(mensaje)
        self.vacio.show()

    def poner(self, grupos, elegido=None, cliente=None):
        """grupos: [(errores a la vista del cliente, todos sus errores)], en el orden de la lista de clientes."""
        posicion = self.scroll.verticalScrollBar().value()
        vaciar(self.lista)
        self.bloques, self.filas = {}, {}
        self.licencia_id = cliente
        for visibles, todos in grupos:
            b = ErroresCliente(en_bloque=True)
            b._todos = todos   # («N sin ver» y «Marcar visto» cuentan todos los suyos, no solo los que se ven)
            b.poner(visibles, elegido)
            lid = visibles[0]['licencia_id']
            b.elegido.connect(self.elegido)
            b.todo_visto.connect(lambda l=lid: self.todo_visto.emit(l))
            self.lista.addWidget(b)
            self.bloques[lid] = b
            self.filas.update(b.filas)
        self.lista.addStretch(1)
        self.vacio.hide()
        self.scroll.show()
        if posicion:
            QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(posicion))

    def marcar(self, ident):
        for clave, fila in self.filas.items():
            fila.poner_elegido(clave == ident)
        if ident in self.filas:
            self.scroll.ensureWidgetVisible(self.filas[ident], 0, 24)


# ---------------------------------------------------------------- Panel del error (a la derecha, en la página Errores)

class ResaltadoInforme(QSyntaxHighlighter):
    """2.3: colores en el informe técnico para leerlo de un vistazo: los títulos de sección («── QUÉ PASÓ ──»), las líneas
    «File "…", line N, in función» del traceback (archivo claro, número y función resaltados) y la línea de la excepción
    («ValueError: …») en rojo."""
    _SECCION = re.compile(r'^\s*──\s.*$')
    _ARCHIVO = re.compile(r'^\s*File "(?P<ruta>[^"]*)", line (?P<linea>\d+)(?:, in (?P<func>.+))?$')
    _EXCEPCION = re.compile(r'^\s*(?P<nombre>[A-Za-z_][\w.]*(?:Error|Exception|Warning|Interrupt|Exit|Fault))(?::|$)')
    _TRACEBACK = re.compile(r'^\s*(Traceback \(most recent call last\):|During handling of the above exception.*|'
                            r'The above exception was the direct cause.*)$')

    def __init__(self, documento):
        super().__init__(documento)

        def formato(color, negrita=False, cursiva=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if negrita:
                f.setFontWeight(QFont.Weight.Bold)
            f.setFontItalic(cursiva)
            return f
        self.f_seccion = formato(VIOLETA_CLARO, negrita=True)
        self.f_tenue = formato(TEXTO_TENUE)
        self.f_traceback = formato(TEXTO_TENUE, cursiva=True)
        self.f_archivo = formato(TEXTO)
        self.f_linea = formato(AVISO, negrita=True)
        self.f_funcion = formato(VIOLETA_CLARO)
        self.f_excepcion = formato(PELIGRO, negrita=True)
        self.f_mensaje = formato('#ffd2d2')

    def highlightBlock(self, texto):
        if self._SECCION.match(texto):
            self.setFormat(0, len(texto), self.f_seccion)
            return
        if self._TRACEBACK.match(texto):
            self.setFormat(0, len(texto), self.f_traceback)
            return
        m = self._ARCHIVO.match(texto)
        if m:
            self.setFormat(0, len(texto), self.f_tenue)
            ruta = m.group('ruta')
            corte = max(ruta.rfind('\\'), ruta.rfind('/')) + 1      # el nombre del archivo, más claro que su carpeta
            self.setFormat(m.start('ruta') + corte, len(ruta) - corte, self.f_archivo)
            self.setFormat(m.start('linea'), len(m.group('linea')), self.f_linea)
            if m.group('func'):
                self.setFormat(m.start('func'), len(m.group('func')), self.f_funcion)
            return
        m = self._EXCEPCION.match(texto)
        if m:
            self.setFormat(m.start('nombre'), len(m.group('nombre')), self.f_excepcion)
            self.setFormat(m.end('nombre'), len(texto) - m.end('nombre'), self.f_mensaje)


# 2.5 (CineCaptions 5.73): las capturas que puede traer un error, en orden: «cual» de error_captura → (su marca en la fila del
# error, su nombre). 'pantalla' es la de siempre (en Mac, la ventana: lo dice su «de»); 'ventana', la de la ventana de CineCaptions.
CAPTURAS_ERROR = {'pantalla': ('con_captura', 'Pantalla completa'), 'ventana': ('con_ventana', 'Ventana de CineCaptions')}


def cuales_captura(error):
    """Las capturas que tiene un error (fila de la lista o detalle), en orden: ('pantalla', 'ventana'), ('ventana',)…"""
    return tuple(cual for cual, (con, _n) in CAPTURAS_ERROR.items() if (error or {}).get(con))


def nombre_captura(cual, captura, dos=False):
    """El rótulo de una captura: por su «de» (la de siempre puede ser la ventana, en Mac); sin «de», el de su lugar si
    hay dos o «Captura» si es la única (como en la 2.3)."""
    de = 'ventana' if cual == 'ventana' else (captura or {}).get('de')
    if de in CAPTURAS_ERROR:
        return CAPTURAS_ERROR[de][1]
    return CAPTURAS_ERROR[cual][1] if dos else 'Captura'


class MiniaturaCaptura(QLabel):
    """2.3: la captura de pantalla del fallo, a lo ancho del panel y con su proporción; un clic la abre grande (VisorCaptura)."""
    clic = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName('miniatura')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.imagen = None

    def poner(self, imagen):
        self.imagen = imagen
        self.updateGeometry()
        self._pintar()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, ancho):
        if self.imagen is None or self.imagen.isNull() or not self.imagen.width():
            return 120
        return max(60, min(420, round(ancho * self.imagen.height() / self.imagen.width())))

    def sizeHint(self):
        return QSize(320, self.heightForWidth(320))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._pintar()

    def _pintar(self):
        if self.imagen is None or self.imagen.isNull():
            self.setPixmap(QPixmap())
            return
        dpr = self.devicePixelRatioF()
        pix = QPixmap.fromImage(self.imagen.scaled(QSize(round(self.width() * dpr), round(self.heightForWidth(self.width()) * dpr)),
                                                   Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        pix.setDevicePixelRatio(dpr)
        self.setPixmap(pix)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.imagen is not None:
            self.clic.emit()
        super().mouseReleaseEvent(e)


class VisorCaptura(QDialog):
    """2.3: la captura a pantalla casi completa: ajustada a la ventana o a tamaño real (clic en la imagen o el botón cambian),
    «Guardar imagen…» y Esc para cerrar."""

    def __init__(self, parent, imagen, titulo, archivo='captura_error.png'):
        super().__init__(parent)
        self.setWindowTitle(f'{APP} · {titulo}')
        self.setModal(True)
        self.imagen, self.real = imagen, False
        self.archivo = archivo   # 2.5: el nombre que propone «Guardar imagen…» (cada captura del error con el suyo)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        arriba = QHBoxLayout()
        t = etiqueta(titulo, 'dialogoTitulo')
        arriba.addWidget(t, 1)
        self.btn_tam = boton('Tamaño real', 'buscar', chico=True)
        self.btn_tam.clicked.connect(self._cambiar)
        guardar = boton('Guardar imagen…', 'exportar', chico=True)
        guardar.clicked.connect(self._guardar)
        cerrar = boton('Cerrar', chico=True)
        cerrar.clicked.connect(self.accept)
        for b in (self.btn_tam, guardar, cerrar):
            arriba.addWidget(b)
        lay.addLayout(arriba)
        self.scroll = QScrollArea()
        self.scroll.setObjectName('visorCaptura')
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.vista = QLabel()
        self.vista.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vista.setCursor(Qt.CursorShape.PointingHandCursor)
        self.vista.mouseReleaseEvent = lambda e: self._cambiar()
        self.scroll.setWidget(self.vista)
        lay.addWidget(self.scroll, 1)
        pantalla = (parent.screen() if parent is not None else QGuiApplication.primaryScreen()).availableGeometry()
        self.resize(round(pantalla.width() * 0.9), round(pantalla.height() * 0.9))

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._pintar)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not self.real:
            self._pintar()

    def _cambiar(self):
        self.real = not self.real
        self.btn_tam.setText(' Ajustar a la ventana' if self.real else ' Tamaño real')
        self._pintar()

    def _pintar(self):
        dpr = self.devicePixelRatioF()
        if self.real:
            pix = QPixmap.fromImage(self.imagen)
            pix.setDevicePixelRatio(dpr)   # (un píxel de la captura = un píxel de la pantalla)
            self.scroll.setWidgetResizable(False)
        else:
            area = self.scroll.viewport().size()
            pix = QPixmap.fromImage(self.imagen.scaled(QSize(round(area.width() * dpr), round(area.height() * dpr)),
                                                       Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            pix.setDevicePixelRatio(dpr)
            self.scroll.setWidgetResizable(True)
        self.vista.setPixmap(pix)
        self.vista.adjustSize()

    def _guardar(self):
        ruta, _f = QFileDialog.getSaveFileName(self, 'Guardar captura', str(Path.home() / 'Desktop' / self.archivo),
                                               'Imagen PNG (*.png);;Imagen JPEG (*.jpg)')
        if ruta:
            self.imagen.save(ruta)


class PanelError(QFrame):
    """El panel del error elegido: qué pasó, a qué cliente y en qué equipo, y el informe técnico que mandó CineCaptions
    (en letra monoespaciada y seleccionable), con «Copiar informe», «Marcar como visto» (o «como nuevo») y «Abrir
    licencia». Va en el lugar del panel de la licencia (los dos comparten el espacio de la derecha)."""
    copiar = Signal(str, str)        # texto que se copia y el aviso que se muestra
    marcar = Signal(int, bool)       # el id del error y cómo queda: visto (True) o nuevo (False)
    abrir_licencia = Signal(object)  # el error, para abrir la licencia de ese cliente
    reintentar = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName('panel')
        self.setMinimumWidth(340)
        self.fila, self.detalle, self._ocupado = None, None, False
        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(2, 2, 2, 2)
        self.scroll = QScrollArea()
        self.scroll.setObjectName('panelScroll')
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        contenido = QWidget()
        contenido.setObjectName('panelContenido')
        self.lay = QVBoxLayout(contenido)
        self.lay.setContentsMargins(18, 18, 18, 18)
        self.lay.setSpacing(16)
        self.scroll.setWidget(contenido)
        exterior.addWidget(self.scroll)

        # Sin nada elegido
        self.vacio = QWidget()
        lv = QVBoxLayout(self.vacio)
        lv.setContentsMargins(24, 72, 24, 24)
        lv.setSpacing(8)
        lv.addWidget(cuadro_icono('alerta', 'tenue', 48), 0, Qt.AlignmentFlag.AlignHCenter)
        lv.addSpacing(8)
        t1 = etiqueta('Elige un error')
        t1.setFont(fuente(15, QFont.Weight.DemiBold))
        t1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t2 = etiqueta('Selecciona un error de la tabla para ver el informe que mandó CineCaptions, el cliente y su equipo.',
                      'suave')
        t2.setWordWrap(True)
        t2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (t1, t2):
            lv.addWidget(w)
        lv.addStretch(1)

        # Cabecera: «ERROR #12» con su estado, el título y el mensaje
        self.cabeza = QWidget()
        lc = QVBoxLayout(self.cabeza)
        lc.setContentsMargins(0, 0, 0, 0)
        lc.setSpacing(6)
        fila_tipo = QHBoxLayout()
        fila_tipo.setSpacing(8)
        self.tipo = etiqueta('', 'seccionTitulo', espaciado=True)
        self.estado = Pastilla()
        self.girando = Indicador(16)
        fila_tipo.addWidget(self.tipo)
        fila_tipo.addWidget(self.estado)
        fila_tipo.addStretch(1)
        fila_tipo.addWidget(self.girando)
        lc.addLayout(fila_tipo)
        # (sin seleccionar: llevan espacios invisibles para cortarse; el texto entero sale en «Copiar informe»)
        self.titulo = etiqueta('', 'nombreCliente')
        self.titulo.setWordWrap(True)
        self.mensaje = etiqueta('', 'suave')
        self.mensaje.setWordWrap(True)
        for lbl in (self.titulo, self.mensaje):   # un texto largo sin espacios nunca ensancha el panel
            lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lc.addWidget(self.titulo)
        lc.addWidget(self.mensaje)

        # Acciones (2.3, propuesta A: en fila, debajo del título)
        self.sec_acc = QWidget()
        self.btn_copiar = boton('Copiar informe', 'copiar')
        self.btn_copiar.setToolTip('Copia todo: el cliente, el equipo, la versión y el detalle técnico')
        self.btn_visto = boton('Marcar como visto', 'check')
        self.btn_licencia = boton('Abrir licencia', 'llave')
        self.btn_licencia.setToolTip('Ver la licencia de este cliente: sus equipos, el historial y las acciones')
        self.btn_copiar.clicked.connect(lambda: self.copiar.emit(texto_informe(self.error()), 'Informe copiado'))
        self.btn_visto.clicked.connect(self._marcar)
        self.btn_licencia.clicked.connect(lambda: self.abrir_licencia.emit(dict(self.error())))
        fila_acc = QHBoxLayout(self.sec_acc)
        fila_acc.setContentsMargins(0, 4, 0, 0)
        fila_acc.setSpacing(8)
        for b in (self.btn_copiar, self.btn_visto, self.btn_licencia):
            fila_acc.addWidget(b)
        fila_acc.addStretch(1)
        lc.addWidget(self.sec_acc)

        # 2.3 (propuesta A): pestañas «Captura · Informe técnico · Cliente y equipo» en vez de bajar por todo el panel
        self.barra_pestanas = QWidget()
        bp = QHBoxLayout(self.barra_pestanas)
        bp.setContentsMargins(0, 6, 0, 0)
        bp.setSpacing(22)
        self.grupo_pestanas = QButtonGroup(self)
        self.btn_pestana = {}
        for n, (clave, texto) in enumerate((('captura', 'Captura'), ('informe', 'Informe técnico'), ('cliente', 'Cliente y equipo'))):
            b = QPushButton(texto)
            b.setObjectName('pestana')
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, c=clave: self._elegir_pestana(c, manual=True))
            self.grupo_pestanas.addButton(b, n)
            self.btn_pestana[clave] = b
            bp.addWidget(b)
        bp.addStretch(1)
        self.raya_pestanas = divisor()
        self.pila = QStackedWidget()
        self._pestana_elegida = None   # la que eligió el dueño (se recuerda al pasar a otro error, si la tiene)

        # Captura del momento del fallo (CineCaptions 5.72): grande; un clic la abre a tamaño real. 2.5 (5.73): pueden ser dos,
        # la pantalla entera y la ventana de CineCaptions: lado a lado, cada una con su rótulo; con una sola, como antes (a todo
        # lo ancho y su línea debajo)
        self.sec_cap = QWidget()
        lcap = QVBoxLayout(self.sec_cap)
        lcap.setContentsMargins(0, 4, 0, 0)
        lcap.setSpacing(8)
        fila_cap = QHBoxLayout()
        fila_cap.setSpacing(14)
        self.cuadros_cap = {}   # cual → (caja, rótulo, miniatura, línea de debajo)
        for cual in CAPTURAS_ERROR:
            caja = QWidget()
            lv = QVBoxLayout(caja)
            lv.setContentsMargins(0, 0, 0, 0)
            lv.setSpacing(6)
            rotulo = etiqueta('', 'seccionTitulo', espaciado=True)
            mini = MiniaturaCaptura()
            mini.clic.connect(lambda c=cual: self._ver_captura(c))
            linea = etiqueta('', 'tenue')
            linea.setWordWrap(True)
            for w in (rotulo, mini, linea):
                lv.addWidget(w)
            lv.addStretch(1)   # (si una es más baja que la otra, las dos quedan arriba)
            caja.hide()
            fila_cap.addWidget(caja, 1)
            self.cuadros_cap[cual] = (caja, rotulo, mini, linea)
        self.miniatura = self.cuadros_cap['pantalla'][2]   # (la de siempre)
        self.cap_texto = etiqueta('', 'tenue')   # «Cargando la captura…» o por qué no se pudo
        self.cap_texto.setWordWrap(True)
        self.hardware = etiqueta('', 'suave')
        self.hardware.setWordWrap(True)
        lcap.addLayout(fila_cap)
        for w in (self.cap_texto, self.hardware):
            lcap.addWidget(w)
        lcap.addStretch(1)
        self.capturas = {}   # cual → {'imagen', 'de', 'ancho', 'alto', 'bytes', 'creada'} de las que se ven

        # El informe técnico (lo que CineCaptions vio cuando pasó)
        self.sec_inf = QWidget()
        linf = QVBoxLayout(self.sec_inf)
        linf.setContentsMargins(0, 4, 0, 0)
        self.informe = QPlainTextEdit()
        self.informe.setReadOnly(True)   # (se puede seleccionar y copiar una parte)
        self.informe.setFont(fuente(12, mono=True))
        self.informe.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)   # (las rutas largas se cortan)
        self.informe.setMinimumHeight(280)
        self.informe.setTabChangesFocus(True)
        self._resaltado = ResaltadoInforme(self.informe.document())   # 2.3: el traceback con colores
        linf.addWidget(self.informe, 1)

        # A quién y dónde: cliente, licencia, equipo, versión, veces...
        self.sec_info = QWidget()
        lfi = QVBoxLayout(self.sec_info)
        lfi.setContentsMargins(0, 6, 0, 0)
        lfi.setSpacing(16)
        self.ficha = Ficha()
        lfi.addWidget(self.ficha)
        # 2.4 (CineCaptions 5.72): debajo, la ficha técnica completa de ese equipo (la última que mandó, de error_detalle).
        # «Al fallar» de arriba es la línea del momento del error; esta es la del día. Sin el servidor nuevo, no sale.
        self.ficha_equipo = FichaEquipo()
        self.ficha_equipo.hide()
        lfi.addWidget(self.ficha_equipo)
        lfi.addStretch(1)
        for w in (self.sec_cap, self.sec_inf, self.sec_info):
            self.pila.addWidget(w)

        # Error al cargar el informe
        self.caja_error = QFrame()
        self.caja_error.setObjectName('banda')
        le = QVBoxLayout(self.caja_error)
        le.setContentsMargins(12, 12, 12, 12)
        le.setSpacing(8)
        self.error_texto = etiqueta('')
        self.error_texto.setWordWrap(True)
        reintentar = boton('Reintentar', 'actualizar', chico=True)
        reintentar.clicked.connect(self.reintentar)
        le.addWidget(self.error_texto)
        le.addWidget(reintentar, 0, Qt.AlignmentFlag.AlignLeft)

        for w in (self.vacio, self.cabeza, self.caja_error, self.barra_pestanas, self.raya_pestanas):
            self.lay.addWidget(w)
        self.lay.addWidget(self.pila, 1)   # (la pestaña se queda con el alto que sobra)
        self.lay.addStretch(0)
        self.mostrar_vacio()

    def error(self):
        """Lo que se sabe del error elegido: el detalle si ya llegó; si no, la fila de la tabla."""
        return self.detalle or self.fila or {}

    def _secciones(self, visibles):
        """visibles: cabeza (con las acciones), caja_error y, si van sec_info / sec_inf, las pestañas."""
        self.cabeza.setVisible(self.cabeza in visibles)
        self.sec_acc.setVisible(self.cabeza in visibles)
        self.caja_error.setVisible(self.caja_error in visibles)
        con_pestanas = self.sec_info in visibles or self.sec_inf in visibles
        for w in (self.barra_pestanas, self.raya_pestanas, self.pila):
            w.setVisible(con_pestanas)
        if con_pestanas:
            hay = bool(cuales_captura(self.error()))   # (2.5: la de la pantalla o la de la ventana)
            self.btn_pestana['captura'].setVisible(hay)
            quiere = self._pestana_elegida or ('captura' if hay else 'informe')
            self._elegir_pestana('informe' if quiere == 'captura' and not hay else quiere)

    def _elegir_pestana(self, clave, manual=False):
        if manual:
            self._pestana_elegida = clave
        self.btn_pestana[clave].setChecked(True)
        self.pila.setCurrentIndex(('captura', 'informe', 'cliente').index(clave))

    def mostrar_vacio(self):
        self.fila, self.detalle = None, None
        self._sin_captura()
        self._poner_ficha(None)
        self.girando.activar(False)
        self._secciones(())
        self.vacio.show()

    def mostrar_fila(self, fila):
        """Lo que ya se sabe por la tabla; el informe llega con error_detalle."""
        self.fila, self.detalle = dict(fila), None
        self.vacio.hide()
        self._sin_captura('Cargando la captura…')
        self._poner_ficha(self.fila)   # (la que trajo la fila si ya se había abierto; si no, nada hasta que llegue)
        self._poner()
        self.informe.setPlainText('')
        self.informe.setPlaceholderText('Cargando el informe…')
        self._secciones((self.cabeza, self.sec_info, self.sec_acc, self.sec_inf))
        self.girando.activar(True)
        self.scroll.verticalScrollBar().setValue(0)

    # --- 2.3: la captura (2.5: las capturas)
    def _sin_captura(self, texto=''):
        self.capturas = {}
        for caja, _rotulo, mini, linea in self.cuadros_cap.values():
            mini.poner(None)
            linea.setText('')
            caja.setVisible(False)
        self.cap_texto.setText(texto)
        self.cap_texto.setVisible(bool(texto))

    def poner_captura(self, ident, capturas, fallos=None):
        """Las capturas que llegaron de error_captura (si son del error que se ve): {cual: captura} y, de las que no se
        pudieron cargar (habiendo otra), {cual: por qué}. Dos: lado a lado con su rótulo; una: como en la 2.3."""
        if (self.error() or {}).get('id') != ident:
            return
        fallos = fallos or {}
        cuales = [c for c in CAPTURAS_ERROR if c in capturas or c in fallos]
        dos = len(cuales) > 1
        self.capturas = dict(capturas)
        self.cap_texto.setText('')
        self.cap_texto.setVisible(False)
        for cual, (caja, rotulo, mini, linea) in self.cuadros_cap.items():
            caja.setVisible(cual in cuales)
            cap = capturas.get(cual)
            nombre = nombre_captura(cual, cap, dos)
            rotulo.setText(nombre.upper())
            rotulo.setVisible(dos)
            mini.poner(cap['imagen'] if cap else None)
            mini.setVisible(cap is not None)
            if cap:   # (con una sola, su nombre va en la línea, como antes; con dos ya lo dice el rótulo)
                partes = ([] if dos else [nombre]) + [f"{cap['ancho']}×{cap['alto']}"]
                if cap.get('creada'):
                    partes.append(fecha_larga(cap['creada']))
                linea.setText(' · '.join(partes) + '  —  clic para ampliar')
            else:
                linea.setText(f"No se pudo cargar esta captura. {fallos.get(cual, '')}".strip())

    def captura_fallo(self, ident, texto):
        if (self.error() or {}).get('id') == ident:
            self._sin_captura(f'No se pudo cargar la captura. {texto}')

    def _ver_captura(self, cual='pantalla'):
        cap = self.capturas.get(cual)
        if cap is not None:
            e = self.error()
            titulo = f"Error #{e.get('id')} · {e.get('cliente') or e.get('correo') or 'cliente'}"
            dos = sum(caja.isVisibleTo(self.sec_cap) for caja, *_r in self.cuadros_cap.values()) > 1
            if dos:   # (2.5: cuál de las dos se está viendo)
                titulo += f' · {nombre_captura(cual, cap, True)}'
            VisorCaptura(self.window(), cap['imagen'], titulo,
                         'captura_error.png' if cual == 'pantalla' else 'captura_error_ventana.png').exec()

    def mostrar_detalle(self, error):
        self.detalle = dict(error)
        self.fila = dict(self.fila or {}, **{k: v for k, v in error.items() if k != 'detalle'})
        self.vacio.hide()
        self._poner()
        detalle = (error.get('detalle') or '').strip('\n')
        if detalle != self.informe.toPlainText():   # (si es el mismo, no se pierde lo que se tenía seleccionado)
            self.informe.setPlainText(detalle)
        self.informe.setPlaceholderText('CineCaptions no mandó el detalle técnico de este error.')
        self._poner_ficha(self.detalle)
        self._secciones((self.cabeza, self.sec_info, self.sec_acc, self.sec_inf))
        self.girando.activar(self._ocupado)

    def _poner_ficha(self, error):
        """2.4: la ficha técnica del equipo del error (solo si el servidor ya conoce las fichas: manda «ficha_equipo»)."""
        conoce = bool(error) and 'ficha_equipo' in error
        self.ficha_equipo.setVisible(conoce)
        if conoce:
            self.ficha_equipo.poner(error['ficha_equipo'],
                                    'Este equipo todavía no mandó su ficha técnica (llega con CineCaptions 5.72).'
                                    if error.get('nombre_equipo') else 'El equipo ya no está activado: su ficha se borró.')

    def mostrar_error(self, texto):
        self.girando.activar(False)
        self.error_texto.setText(f'No se pudo cargar el informe. {texto}')
        self._secciones((self.cabeza, self.caja_error, self.sec_info, self.sec_acc))

    def poner_cambios(self, cambios):
        """Lo que cambió del error elegido (al marcarlo o al recargar la tabla), sin volver a pedir el informe."""
        if self.fila is None:
            return
        self.fila.update(cambios)
        if self.detalle is not None:
            self.detalle.update(cambios)
        self._poner()

    def set_ocupado(self, ocupado):
        self._ocupado = ocupado
        self.girando.activar(ocupado or (self.fila is not None and self.detalle is None and self.caja_error.isHidden()))
        self._botones()

    def _marcar(self):
        e = self.error()
        if e.get('id'):
            self.marcar.emit(e['id'], not e.get('visto'))

    def _poner(self):
        e = self.error()
        nivel = NIVELES_ERROR.get(e.get('nivel'), NIVELES_ERROR['error'])[0]
        self.tipo.setText(f"{nivel.upper()} #{e.get('id')}")
        titulo, mensaje = e.get('titulo') or '', e.get('mensaje') or ''
        self.titulo.setText(partible(titulo or mensaje or 'Sin título'))
        self.mensaje.setText(partible(mensaje))
        self.mensaje.setVisible(bool(mensaje) and mensaje != titulo)
        veces = entero(e.get('veces'))
        ultima = fecha_larga(e.get('ultima')) if e.get('ultima') else None
        self.ficha.poner([
            ('Cliente', '\n'.join(x for x in (e.get('cliente'), e.get('correo')) if x) or 'Sin nombre', None),
            ('Licencia', e.get('clave'), None),
            ('Equipo', '\n'.join(x for x in (equipo_de_error(e), texto_so(e.get('so'))) if x), None),
            # (la línea del momento del error; la ficha técnica completa del equipo va debajo, 2.4)
            ('Al fallar', '\n'.join(p.strip() for p in (e.get('equipo_datos') or '').split(' · ') if p.strip()) or None, None),
            ('Versión', texto_version(e.get('version')) or e.get('version'), None),
            ('Dónde', e.get('origen'), None),
            ('Veces', plural(veces, 'vez', 'veces') if veces else None, AVISO if veces > 1 and not e.get('visto') else None),
            ('Última vez', f"{ultima} ({hace(e.get('ultima'))})" if ultima else None, None),
            ('Primera vez', fecha_larga(e.get('primera')) if e.get('primera') and e.get('primera') != e.get('ultima') else None,
             None)])
        datos = [p.strip() for p in (e.get('equipo_datos') or '').split(' · ') if p.strip()]
        self.hardware.setText('   ·   '.join(datos))   # (debajo de la captura: con qué equipo pasó)
        self.hardware.setVisible(bool(datos))
        self._botones()

    def _botones(self):
        e = self.error()
        visto = bool(e.get('visto'))
        color = NIVELES_ERROR.get(e.get('nivel'), NIVELES_ERROR['error'])[1]
        self.estado.poner('Visto' if visto else 'Sin ver', TEXTO_TENUE if visto else color)
        self.btn_visto.setText(' Marcar nuevo' if visto else ' Marcar visto')   # (2.3: corto, cabe en una fila)
        self.btn_visto.setIcon(icono('ojo' if visto else 'check', TEXTO_SUAVE, 16))
        self.btn_visto.setToolTip('Vuelve a salir en «Sin ver» y en el contador' if visto
                                  else 'Deja de salir en «Sin ver» y en el contador (si vuelve a pasar, sale otra vez)')
        self.btn_visto.setEnabled(not self._ocupado and bool(e.get('id')))
        self.btn_licencia.setEnabled(bool(e.get('licencia_id')))
        self.btn_copiar.setEnabled(bool(e))


# ---------------------------------------------------------------- Ventana principal

PAGINAS = [('resumen', 'inicio', 'Resumen'), ('ventas', 'recibo', 'Ventas'), ('versiones', 'capas', 'Versiones'),
           ('canjes', 'regalo', 'Canjes'), ('cupones', 'cupon', 'Cupones'), ('avisos', 'megafono', 'Avisos'),
           ('errores', 'alerta', 'Errores')]
# El título grande de la página, si es más largo que su nombre en la isla (2.8: con Cupones, «Canjes de Gumroad» ya no
# cabía en la isla a 1440 px)
TITULOS = {'canjes': 'Canjes de Gumroad'}
SUBTITULOS = {'resumen': 'Cómo van tus ventas y quién ya tiene la última versión',
              'ventas': 'Los pagos de Recurrente, cada uno con su licencia CC-',
              'versiones': 'Quién ya tiene la última versión de CineCaptions y a quién avisarle',
              'canjes': 'Las compras de Gumroad que se canjearon por una licencia CC-',
              'cupones': 'Descuentos para la web: crea, pausa o borra cupones y mira cuánto vendió cada uno',
              'avisos': 'Los correos de «hay una versión nueva» que mandaste',
              'errores': 'Los errores que les salieron a tus clientes en CineCaptions'}
FALTA_SERVIDOR_ERRORES = ('Los errores de tus clientes aparecen cuando subas el pagos/admin.php nuevo (el de CineCaptions '
                          '5.71, con errores.php).')
FALTA_SERVIDOR_CUPONES = ('Los cupones aparecen cuando subas los archivos nuevos de pagos/ (admin.php, telemetria.php, '
                          'cupones.php, ver_cupon.php, cupon_gratis.php y comprar.php).')
HOLGURA_ISLA = 16   # 2.7: lo que la isla deja libre junto al título y a «Exportar CSV» (si no cabe, cierra nombres)
SERVIDOR_SIN_ELIMINAR = ('Tu servidor todavía no sabe eliminar ventas: falta subir el pagos/admin.php nuevo. La venta '
                         'sigue igual que antes.')
SERVIDOR_VIEJO = ('El servidor publicado todavía es el anterior: falta subir el pagos/admin.php nuevo. Mientras tanto ves '
                  'las ventas, los canjes y las licencias como antes; las versiones, los avisos, el historial y las notas '
                  'aparecen cuando lo subas.')


class VentanaPrincipal(QMainWindow):
    datos_listos = Signal()             # terminó una actualización completa (bien o mal)
    detalle_listo = Signal()            # llegó (o falló) el detalle de la fila elegida
    accion_terminada = Signal(str, bool)

    def __init__(self, config, api_url, captura=False, solo_lectura=False):
        super().__init__()
        self.config, self.api_url, self.captura, self.solo_lectura = config, api_url, captura, solo_lectura
        self.cliente = None
        self.resumen = None
        self.seleccion = None            # ('venta' | 'canje' | 'licencia', id)
        self.ultima = None               # hora de la última actualización que salió bien
        self.intento_listo = False       # ya terminó la primera carga (aunque haya fallado)
        self.servidor_nuevo = None       # None: todavía no se sabe; False: es el admin.php anterior (sin acciones nuevas)
        self.version_ultima = None       # la última versión de CineCaptions, según el resumen («5.54»)
        self.version_info = None         # lo que dijo version_actual (fecha, notas y la versión del version.json)
        self.versiones = None            # la última respuesta de la acción versiones
        self.estadisticas = None
        self.pagina = 'resumen'
        self._cuando = {}                # cuándo se cargó cada cosa (para no volver a pedirla a cada rato)
        self._actualizando = False
        self._clave_mala = False
        self._listas_pendientes = 0
        self._ronda_ok = True
        self._restaurando = False
        self._hay_mas_v = False
        self._consulta_v = None          # (filtro, búsqueda) de las ventas que hay en la tabla
        self._num = dict.fromkeys(('ventas', 'canjes', 'detalle', 'historial', 'avisos_licencia', 'versiones', 'avisos',
                                   'estadisticas', 'version', 'errores', 'error_detalle', 'error_captura', 'equipo_ficha',
                                   'resumen_err', 'cupones'), 0)
        self.cupones_info = None         # 2.8: lo último de la acción cupones (precio, moneda, hoy, sitio)
        self.servidor_cupones = None     # 2.8: False = el admin.php publicado todavía no tiene los cupones
        self._cupon_en_camino = set()    # 2.8: cupones con un cambio enviado (otro clic no lo repite)
        self._cupon_a_elegir = None      # 2.8: el cupón recién creado, que se elige cuando llegue la lista
        self.dialogo_ficha = None        # 2.4: la ficha técnica de un equipo que se está viendo (DialogoFicha)
        self.errores_resumen = None      # cuántos errores sin ver hay (lo último que dijo el servidor; None: no lo manda)
        self.servidor_errores = None     # False: el admin.php publicado todavía no tiene la página Errores
        self.error_elegido = None        # el id del error que se ve en el panel de la página Errores
        self._capturas_pedidas = None    # 2.5: (id, cuáles) de las capturas que se pidieron para ese error
        self._licencia_pendiente = None  # (licencia, equipo) que «Abrir licencia» elige cuando lleguen los equipos
        self._bandeja = None             # el ícono en la bandeja de Windows (solo para las notificaciones)
        self._ronda = 0                  # cada «Actualizar» lleva su número: lo que llegue de una ronda vieja no cuenta
        self._generacion = 0             # sube al cambiar la clave o la API: las respuestas de antes se descartan
        self._pausa_hasta = 0.0          # después de un 429 no se actualiza solo hasta que pase el Retry-After
        self._acciones = 0               # cambios enviados al servidor que todavía no responden
        self._eliminando = set()         # ventas con un «Eliminar» o «Restaurar» en camino (otro clic no lo repite)
        self._suelta = None              # la venta que se acaba de eliminar o restaurar: sigue en el panel aunque ya no
        #                                  esté en la lista (ahí mismo se puede deshacer); se olvida al elegir otra fila
        self._venta_a_elegir = None      # la venta que «Últimas ventas» quiere abrir cuando llegue la lista sin filtro
        self.trabajos = Trabajos(self)
        self.trabajos.ocupado.connect(self._ocupado)
        self._timer_detalle = self._temporizador(140, self._cargar_detalle)
        self._timer_buscar_v = self._temporizador(450, self._cargar_ventas)
        self._timer_buscar_c = self._temporizador(450, self._cargar_canjes)
        self._timer_filtro = self._temporizador(180, self._filtrar_locales)   # versiones, avisos y errores, aquí
        self._timer_error = self._temporizador(140, self._cargar_error)
        self._anchos_lado = {'otras': None}   # el ancho del panel de la derecha en las demás páginas
        try:   # en Errores, la PARTE de la ventana (se mantiene al cambiar el tamaño)
            self._frac_errores = min(0.75, max(0.35, float(self.config.datos.get('frac_errores') or 0.58)))
        except (TypeError, ValueError):
            self._frac_errores = 0.58
        self._auto = QTimer(self)
        self._auto.setInterval(AUTO_MS)
        self._auto.timeout.connect(self._actualizar_solo)
        self.setWindowTitle(APP)
        self.setWindowIcon(icono_app())
        self.setMinimumSize(1100, 620)   # (más angosta, los filtros de Versiones y el panel ya no caben)
        self._armar_atajos()
        self._armar_ui()
        if not captura:   # 2.3 (propuesta A): siempre se actualiza sola, sin casilla (F5 / Ctrl+R siguen)
            self._auto.start()
        guardada = self.config.datos.get('pagina')
        self.ir_a(guardada if not captura and guardada in self._indices else 'resumen')
        self._poner_estado()

    def _temporizador(self, ms, funcion):
        t = QTimer(self)
        t.setSingleShot(True)
        t.setInterval(ms)
        t.timeout.connect(funcion)
        return t

    # --- Armado
    def _armar_atajos(self):
        """Sin barra de menús: la configuración está a la derecha de la isla de arriba y estos atajos siguen funcionando
        (Ctrl+1…6 abren las páginas en el orden de la isla)."""
        for tecla, funcion in (('F5', lambda: self.actualizar_todo()), ('Ctrl+E', self.exportar_csv),
                               ('Ctrl+Q', self.close), ('Ctrl+R', lambda: self.actualizar_todo())):
            a = QAction(self)
            a.setShortcut(QKeySequence(tecla))
            a.triggered.connect(funcion)
            self.addAction(a)
        for n, (clave, _icono, _texto) in enumerate(PAGINAS, 1):
            a = QAction(self)
            a.setShortcut(QKeySequence(f'Ctrl+{n}'))
            a.triggered.connect(lambda _c=False, k=clave: self.ir_a(k))
            self.addAction(a)

    def _armar_ui(self):
        raiz = RaizVentana()   # (2.7: avisa sus cambios de tamaño a la isla)
        raiz.setObjectName('raiz')
        self.setCentralWidget(raiz)
        v = QVBoxLayout(raiz)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        franja = QFrame()
        franja.setObjectName('franja')
        v.addWidget(franja)
        # 2.7: sin la barra lateral, la página usa todo el ancho; el menú (la isla) flota arriba al centro y se arma al
        # final, encima de todo. La cabecera baja 12 px (20 → 32) para que el subtítulo no quede debajo de la isla.
        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(24, 32, 24, 16)
        cuerpo.setSpacing(16)
        v.addLayout(cuerpo, 1)
        self._cuerpo = cuerpo

        # Encabezado: título de la página y, a la derecha, «Exportar CSV» (en las tablas que se exportan). 2.3 (propuesta A
        # elegida por el dueño: «quitar opciones redundantes»): sin la casilla «Actualizar cada 2 min» (siempre se
        # actualiza sola), sin «Actualizar» (F5 / Ctrl+R) y sin «Anunciar versión…» (está en Versiones). 2.7: la ruedita
        # y «Cargando…» bajaron a la barra de estado: aquí, junto a «Exportar CSV», quedaban pegadas a la isla y la
        # obligaban a cerrar los nombres a 1440 px.
        enc = QHBoxLayout()
        enc.setSpacing(8)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.lbl_titulo = etiqueta('', 'paginaTitulo')
        titulo = fuente(22, QFont.Weight.DemiBold)
        titulo.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -0.3)   # (Inter grande se ve mejor un poco más junta)
        self.lbl_titulo.setFont(titulo)
        self.lbl_sub = Recortada('', 'paginaSub')
        col.addWidget(self.lbl_titulo)
        col.addWidget(self.lbl_sub)
        enc.addLayout(col, 1)
        self.btn_exportar = boton('Exportar CSV', 'exportar')
        self.btn_exportar.setToolTip('Guardar esta tabla para Excel (Ctrl+E)')
        self.btn_exportar.clicked.connect(self.exportar_csv)
        enc.addWidget(self.btn_exportar)
        cuerpo.addLayout(enc)

        self.banda = Banda()
        self.banda.reintentar.connect(lambda: self.actualizar_todo())
        self.banda.clave.connect(self.cambiar_clave)
        cuerpo.addWidget(self.banda)
        self.banda_servidor = Banda('info')
        cuerpo.addWidget(self.banda_servidor)

        self.divisor = QSplitter(Qt.Orientation.Horizontal)
        self.divisor.setHandleWidth(16)
        self.divisor.setChildrenCollapsible(False)
        self.paginas = QStackedWidget()
        self._indices = {}
        for clave, armar in (('resumen', self._armar_resumen), ('ventas', self._armar_ventas),
                             ('versiones', self._armar_versiones), ('canjes', self._armar_canjes),
                             ('cupones', self._armar_cupones), ('avisos', self._armar_avisos),
                             ('errores', self._armar_errores)):
            self._indices[clave] = self.paginas.addWidget(armar())
        self.panel = PanelDetalle()
        self.panel.accion.connect(self._accion)
        self.panel.copiar.connect(self._copiar)
        self.panel.reintentar.connect(self._cargar_detalle)
        self.panel_error = PanelError()
        self.panel_error.copiar.connect(self._copiar)
        self.panel_error.marcar.connect(lambda ident, visto: self._marcar_errores([ident], visto))
        self.panel_error.abrir_licencia.connect(self._abrir_licencia)
        self.panel_error.reintentar.connect(self._cargar_error)
        # A la derecha, el panel de la licencia o (en la página Errores) el del error: comparten el lugar (así el divisor
        # sigue con dos partes y su tamaño guardado sirve igual)
        self.lado = QStackedWidget()
        self.lado.addWidget(self.panel)
        self.lado.addWidget(self.panel_error)
        self.divisor.addWidget(self.paginas)
        self.divisor.addWidget(self.lado)
        self.divisor.setStretchFactor(0, 1)
        self.divisor.setStretchFactor(1, 0)
        self.divisor.setSizes([1040, 370])
        self.divisor.splitterMoved.connect(self._lado_movido)
        cuerpo.addWidget(self.divisor, 1)

        # Barra de abajo: a la izquierda cuándo se actualizó (2.7: y, mientras carga, la ruedita y «Cargando…», que
        # estaban en el encabezado); a la derecha la API de prueba, la versión de la app (2.7: estaba abajo en la barra
        # lateral) y «Solo lectura» (en las capturas)
        izquierda = QWidget()
        li = QHBoxLayout(izquierda)
        li.setContentsMargins(16, 0, 0, 0)
        li.setSpacing(6)
        self.ic_estado = QLabel()
        self.lbl_actualizado = etiqueta('')
        self.indicador = Indicador(14)
        self.lbl_cargando = etiqueta('Cargando…', 'cargando')
        self.lbl_cargando.hide()
        li.addWidget(self.ic_estado)
        li.addWidget(self.lbl_actualizado)
        li.addSpacing(8)
        li.addWidget(self.indicador)
        li.addWidget(self.lbl_cargando)
        self.statusBar().addWidget(izquierda)
        derecha = QWidget()
        ld = QHBoxLayout(derecha)
        ld.setContentsMargins(0, 0, 16, 0)
        ld.setSpacing(12)
        self.lbl_estado = etiqueta('')
        self.lbl_solo_lectura = etiqueta('Solo lectura', 'soloLectura')
        self.lbl_solo_lectura.setFixedHeight(18)
        self.lbl_solo_lectura.setToolTip('Modo captura: no se cambia nada ni se manda ningún correo')
        self.lbl_solo_lectura.setVisible(self.solo_lectura)
        self.lbl_version = etiqueta(f'Versión {VERSION}')
        ld.addWidget(self.lbl_estado)
        ld.addWidget(self.lbl_version)
        ld.addWidget(self.lbl_solo_lectura)
        self.statusBar().addPermanentWidget(derecha)
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().setFixedHeight(28)
        # 2.7: el menú, la isla de arriba (encima del contenido; su sombra no tapa clics). Sigue llamándose «barra»: la
        # usan igual que la barra lateral de antes (botones[clave].poner_contador, btn_config, marcar).
        self.barra = IslaNav(raiz, PAGINAS, self._reservas_isla)
        self.barra.elegida.connect(self.ir_a)
        self.barra.btn_config.clicked.connect(self._menu_config)
        self.barra.levantar()
        self.aviso = Aviso(raiz, zona=self._zona_aviso)
        atajo = QShortcut(QKeySequence.StandardKey.Find, self)
        atajo.activated.connect(self._ir_a_buscar)

    def _zona_aviso(self):
        """Donde se centra el mensajito de abajo: el contenido (2.7: todo el ancho, ya sin barra lateral)."""
        return self.centralWidget().rect()

    def _reservas_isla(self):
        """2.7: lo que la isla no puede tapar a cada lado del encabezado, en el peor caso (no el de la página que se ve:
        así la isla no cambia de forma al cambiar de página): a la izquierda, el título más largo; a la derecha,
        «Exportar CSV». Con los tamaños, no con la geometría (la del botón escondido no vale)."""
        margenes = self._cuerpo.contentsMargins()
        fm = QFontMetrics(self.lbl_titulo.font())
        izquierda = margenes.left() + max(fm.horizontalAdvance(TITULOS.get(c, texto)) for c, _i, texto in PAGINAS)
        derecha = margenes.right() + self.btn_exportar.sizeHint().width()
        return izquierda + HOLGURA_ISLA, derecha + HOLGURA_ISLA

    def _tarjeta(self, titulo, contenido, extra=None):
        """Tarjeta con su título chico arriba (y algo a la derecha del título)."""
        marco = QFrame()
        marco.setObjectName('tarjeta')
        lay = QVBoxLayout(marco)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)
        cabeza = QHBoxLayout()
        cabeza.addWidget(etiqueta(titulo.upper(), 'tarjetaTitulo', espaciado=True))
        cabeza.addStretch(1)
        if extra is not None:
            cabeza.addWidget(extra)
        lay.addLayout(cabeza)
        lay.addWidget(contenido, 1)
        return marco

    def _armar_resumen(self):
        """Las seis tarjetas arriba; la gráfica y «Últimas ventas» a la par (las dos crecen con la ventana: caben más
        ventas) y, abajo y a todo lo ancho, la tarjeta de versiones en tres columnas, siempre del alto de lo que tiene."""
        pagina = QScrollArea()
        pagina.setObjectName('paginaScroll')
        pagina.setWidgetResizable(True)
        pagina.setFrameShape(QFrame.Shape.NoFrame)
        pagina.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pagina.viewport().setAutoFillBackground(False)
        contenido = QWidget()
        contenido.setObjectName('paginaContenido')
        lay = QVBoxLayout(contenido)
        lay.setContentsMargins(0, 0, 2, 2)
        lay.setSpacing(16)
        self.t_hoy = Tarjeta('Hoy', destacada=True)
        self.t_mes = Tarjeta('Este mes')
        self.t_total = Tarjeta('Total')
        self.t_reemb = Tarjeta('Reembolsos')
        self.t_lic = Tarjeta('Licencias')
        self.t_equipos = Tarjeta('Equipos activos')
        lay.addWidget(FilaTarjetas([self.t_hoy, self.t_mes, self.t_total, self.t_reemb, self.t_lic, self.t_equipos]))
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        self.grafica = GraficaVentas()
        self.lbl_grafica = etiqueta('', 'tarjetaDetalle', plano=False)
        self.lbl_grafica.setTextFormat(Qt.TextFormat.RichText)
        grid.addWidget(self._tarjeta(f'Ventas por día · últimos {DIAS_GRAFICA} días', self.grafica, self.lbl_grafica), 0, 0)
        self.recientes = ListaRecientes()
        self.recientes.elegida.connect(self._abrir_venta)
        self.recientes.ver_todas.connect(lambda: self.ir_a('ventas'))
        self.recientes.setMinimumWidth(300)
        grid.addWidget(self.recientes, 0, 1)
        # (2.3: sin «Anunciar versión…»: la acción vive en Versiones, junto a quién va atrasado; aquí, «Ver equipos»)
        self.bloque_versiones = BloqueVersiones(con_grafica=True, ancha=True, con_boton=False)
        self.bloque_versiones.ver.connect(lambda: self.ir_a('versiones'))
        self.bloque_versiones.anunciar.connect(self.anunciar)
        grid.addWidget(self.bloque_versiones, 1, 0, 1, 2)
        grid.setColumnStretch(0, 13)
        grid.setColumnStretch(1, 7)
        grid.setRowStretch(0, 1)
        lay.addLayout(grid, 1)
        pagina.setWidget(contenido)
        return pagina

    def _campo_buscar(self, textos, timer, funcion):
        campo = CampoBuscar(textos)
        campo.setClearButtonEnabled(True)
        campo.addAction(icono('buscar', TEXTO_TENUE, 16), QLineEdit.ActionPosition.LeadingPosition)
        campo.textChanged.connect(lambda _t: timer.start())
        campo.returnPressed.connect(lambda: (timer.stop(), funcion()))
        campo.setMinimumWidth(170)
        campo.setMaximumWidth(460)
        return campo

    def _barra_tabla(self, *widgets):
        barra = QHBoxLayout()
        barra.setSpacing(8)
        for w in widgets:
            if w is None:
                barra.addStretch(1)
            else:
                barra.addWidget(w, 3 if isinstance(w, QLineEdit) else 0)
        # (cuando el buscador llega a su ancho máximo, lo que sobra queda a la derecha: si no, los filtros se corrían
        # al centro en una ventana ancha)
        barra.addStretch(0)
        return barra

    def _marco(self, tabla):
        marco = QFrame()
        marco.setObjectName('marcoTabla')
        l = QVBoxLayout(marco)
        l.setContentsMargins(2, 2, 2, 2)
        l.addWidget(tabla)
        return marco

    def _pagina(self, *partes):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        for parte in partes:
            if isinstance(parte, QWidget):
                lay.addWidget(parte, 1 if isinstance(parte, QFrame) and parte.objectName() == 'marcoTabla' else 0)
            else:
                lay.addLayout(parte)
        return w

    def _armar_ventas(self):
        self.fechas_v = Segmentos(FILTROS_FECHA, 0)
        self.fechas_v.cambiado.connect(lambda _d: self._filtrar_fechas())
        self.filtro = QComboBox()
        for texto, valor in FILTROS_VENTAS:
            self.filtro.addItem(texto, valor)
        # Del ancho de la opción más larga («Pagadas y reembolsadas»); en una ventana angosta se achica hasta 150
        self.filtro.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.filtro.setMinimumWidth(150)
        self.filtro.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.filtro.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filtro.currentIndexChanged.connect(lambda _i: self._cargar_ventas())
        self._poner_filtro_eliminadas(None)   # («Eliminadas» se puede elegir cuando se sepa que el servidor las tiene)
        self.buscar_v = self._campo_buscar(('Buscar cliente, correo o clave…', 'Buscar cliente…', 'Buscar…'),
                                           self._timer_buscar_v, self._cargar_ventas)
        self.buscar_v.setToolTip('Busca por nombre, correo, clave CC- o el ID del pago de Recurrente (Ctrl+F)')
        self.modelo_v = ModeloVentas(self)
        self.tabla_v = Tabla('recibo', 'Cargando ventas…')
        self.proxy_v = self._preparar_tabla(self.tabla_v, self.modelo_v)
        pie = QHBoxLayout()
        self.lbl_pie_v = etiqueta('', 'tenue')
        self.btn_mas = boton('Cargar más', 'abajo', chico=True)
        self.btn_mas.clicked.connect(lambda: self._cargar_ventas(mas=True))
        self.btn_mas.hide()
        pie.addWidget(self.lbl_pie_v)
        pie.addStretch(1)
        pie.addWidget(self.btn_mas)
        return self._pagina(self._barra_tabla(self.fechas_v, self.filtro, self.buscar_v), self._marco(self.tabla_v), pie)

    def _armar_versiones(self):
        """Arriba, la tarjeta que dice quién va atrasado y la acción de avisarles (PlanVersiones); abajo, un cliente por
        fila, con los que faltan por avisar primero y su botón «Avisar» (un clic: pregunta y manda el correo)."""
        self.plan_versiones = PlanVersiones()
        self.plan_versiones.anunciar.connect(self.anunciar)
        self.grafica_versiones = self.plan_versiones.grafica   # (los equipos de cada versión, en la tarjeta)
        self.filtro_ver = Segmentos(FILTROS_VERSION, 'todos')
        self.filtro_ver.cambiado.connect(lambda _v: self._filtrar_locales())
        self.filtro_ver.setToolTip('Cuentan los clientes con la licencia activa («Todos» también los bloqueados)')
        self.buscar_ver = self._campo_buscar(('Buscar cliente, correo o equipo…', 'Buscar cliente o equipo…', 'Buscar…'),
                                             self._timer_filtro, self._filtrar_locales)
        self.buscar_ver.setToolTip('Busca por nombre, correo, clave CC-, equipo, versión o sistema (Ctrl+F)')
        self.modelo_ver = ModeloVersiones(self)
        self.tabla_ver = Tabla('capas', 'Cargando clientes…')
        columna = next(i for i, (c, _t, _a) in enumerate(ModeloVersiones.COLUMNAS) if c == 'aviso')
        self.proxy_ver = self._preparar_tabla(self.tabla_ver, self.modelo_ver, columna_orden=columna)
        self.tabla_ver.delegado_boton.apretado.connect(self._boton_de_versiones)
        # (la mano sobre «Avisar»: así se ve que es un botón)
        self.tabla_ver.entered.connect(self._cursor_versiones)
        self.tabla_ver.viewportEntered.connect(lambda: self.tabla_ver.viewport().unsetCursor())
        self.lbl_pie_ver = etiqueta('', 'tenue')
        return self._pagina(self.plan_versiones, self._barra_tabla(self.filtro_ver, self.buscar_ver),
                            self._marco(self.tabla_ver), self.lbl_pie_ver)

    def _cursor_versiones(self, indice):
        datos = indice.data(ROL_INSIGNIA) if indice.isValid() else None
        if datos and datos[2] == 'boton':
            self.tabla_ver.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.tabla_ver.viewport().unsetCursor()

    def _boton_de_versiones(self, indice):
        """«Avisar» dentro de la tabla de Versiones: el aviso a ese cliente (después del clic: la pregunta no se abre en
        medio del clic de la tabla)."""
        fila = self._fila_de(self.tabla_ver, indice)
        if fila:
            QTimer.singleShot(0, lambda: self._avisar_cliente(fila))

    def _armar_canjes(self):
        self.buscar_c = self._campo_buscar(('Buscar por nombre, correo o clave…', 'Buscar…'), self._timer_buscar_c,
                                           self._cargar_canjes)
        self.modelo_c = ModeloCanjes(self)
        self.tabla_c = Tabla('regalo', 'Cargando canjes…')
        self.proxy_c = self._preparar_tabla(self.tabla_c, self.modelo_c)
        self.lbl_pie_c = etiqueta('', 'tenue')
        return self._pagina(self._barra_tabla(self.buscar_c, None), self._marco(self.tabla_c), self.lbl_pie_c)

    def _armar_cupones(self):
        """2.8: los cupones de descuento. Arriba, «Todos · Activos · Sin efecto», el buscador y «Nuevo cupón»; doble clic en
        uno para editarlo (ahí también se borra) y clic derecho para copiar su código o su enlace, pausarlo o borrarlo.
        Sin panel a la derecha: la tabla usa todo el ancho."""
        self.filtro_cup = Segmentos(FILTROS_CUPONES, '')
        self.filtro_cup.cambiado.connect(lambda _v: self._filtrar_locales())
        self.buscar_cup = self._campo_buscar(('Buscar código o nota…', 'Buscar…'), self._timer_filtro,
                                             self._filtrar_locales)
        self.btn_nuevo_cupon = boton('Nuevo cupón', 'mas', tipo='primario')
        self.btn_nuevo_cupon.clicked.connect(lambda: self.nuevo_cupon())
        self.modelo_cup = ModeloCupones(self)
        self.tabla_cup = Tabla('cupon', 'Cargando cupones…')
        self.proxy_cup = self._preparar_tabla(self.tabla_cup, self.modelo_cup)
        estado = next(i for i, (c, _t, _a) in enumerate(ModeloCupones.COLUMNAS) if c == 'estado')
        self.tabla_cup.sortByColumn(estado, Qt.SortOrder.AscendingOrder)   # (los activos primero; luego, los más nuevos)
        self.tabla_cup.doubleClicked.connect(lambda i: self._editar_cupon(self._fila_de(self.tabla_cup, i)))
        self.lbl_pie_cup = etiqueta('', 'tenue')
        return self._pagina(self._barra_tabla(self.filtro_cup, self.buscar_cup, None, self.btn_nuevo_cupon),
                            self._marco(self.tabla_cup), self.lbl_pie_cup)

    def _armar_avisos(self):
        self.filtro_av = Segmentos(FILTROS_AVISOS, '')
        self.filtro_av.cambiado.connect(lambda _v: self._filtrar_locales())
        self.buscar_av = self._campo_buscar(('Buscar cliente, correo o versión…', 'Buscar cliente…', 'Buscar…'),
                                            self._timer_filtro, self._filtrar_locales)
        self.modelo_av = ModeloAvisos(self)
        self.tabla_av = Tabla('megafono', 'Cargando avisos…')
        self.proxy_av = self._preparar_tabla(self.tabla_av, self.modelo_av)
        self.lbl_pie_av = etiqueta('', 'tenue')
        return self._pagina(self._barra_tabla(self.filtro_av, self.buscar_av), self._marco(self.tabla_av), self.lbl_pie_av)

    def _armar_errores(self):
        """Los errores de los clientes. 2.3 (propuesta A): UNA barra con «Sin ver · Todos», el buscador (se filtra aquí,
        como Versiones y Avisos), «Por cliente · Lista» y, a la derecha, «Marcar todo como visto». «Por cliente» (la de
        siempre al abrir): una columna con cada cliente (los de errores sin ver arriba) y sus errores debajo. «Lista»: la
        tabla de todos. El error elegido sale a la derecha, en un panel ancho."""
        self.vista_errores = Segmentos(VISTAS_ERRORES, 'usuario')
        self.vista_errores.cambiado.connect(self._cambiar_vista_errores)
        self.filtro_err = Segmentos(FILTROS_ERRORES, 'sin_ver')
        self.filtro_err.cambiado.connect(lambda _v: self._filtrar_locales())
        self.buscar_err = self._campo_buscar(('Buscar cliente, equipo o error…', 'Buscar cliente o error…', 'Buscar…'),
                                             self._timer_filtro, self._filtrar_locales)
        self.buscar_err.setToolTip('Busca por nombre, correo, clave CC-, equipo, versión o el texto del error (Ctrl+F)')
        self.btn_todo_visto = boton('Marcar todo como visto', 'check', chico=True)
        self.btn_todo_visto.setToolTip('Los errores sin ver dejan de salir en «Sin ver» y en el contador de la barra')
        self.btn_todo_visto.clicked.connect(self._todo_visto)
        self.btn_todo_visto.setEnabled(False)
        # 2.6: todos los errores que se ven (filtro y búsqueda) en un texto agrupado por fallo, para pegarlo en un chat
        self.btn_resumen_err = boton('Copiar resumen', 'copiar', chico=True)
        self.btn_resumen_err.setToolTip('Copia en un solo texto los errores que se ven (con el filtro y la búsqueda de arriba), '
                                        'agrupados por fallo y sin correos ni claves: para pegarlo en un chat y arreglarlos todos a la vez')
        self.btn_resumen_err.clicked.connect(self._copiar_resumen_errores)
        self.btn_resumen_err.setEnabled(False)
        self.modelo_err = ModeloErrores(self)
        self.tabla_err = Tabla('alerta', 'Cargando errores…')
        self.proxy_err = self._preparar_tabla(self.tabla_err, self.modelo_err)
        # Por cliente: la lista de clientes (escondida: manda el orden, el filtro y el elegido) y la columna con cada uno
        self.modelo_cli = ModeloClientesErrores(self)
        self.tabla_cli = Tabla('usuario', 'Cargando errores…')
        self.proxy_cli = self._preparar_tabla(self.tabla_cli, self.modelo_cli, columna_orden=2)
        self.errores_cliente = ErroresPorCliente()
        self.errores_cliente.elegido.connect(self._elegir_error_de_cliente)
        self.errores_cliente.todo_visto.connect(self._todo_visto_de)
        self.cliente_err = None   # la licencia elegida en «Por cliente»
        self._filtro_error = None   # la función del filtro de errores («Sin ver» / buscador), o None
        self.pila_err = QStackedWidget()
        self.pila_err.addWidget(self.errores_cliente)
        self.pila_err.addWidget(self._marco(self.tabla_err))
        self.lbl_pie_err = etiqueta('', 'tenue')
        # («Marcar todo como visto» va en el pie, junto a cuántos hay sin ver: así la barra de arriba es corta y el panel
        # del error, a la derecha, puede ser ancho)
        pie = QHBoxLayout()
        pie.setSpacing(8)
        pie.addWidget(self.lbl_pie_err, 1)
        pie.addWidget(self.btn_resumen_err)
        pie.addWidget(self.btn_todo_visto)
        pagina = self._pagina(self._barra_tabla(self.filtro_err, self.buscar_err, self.vista_errores), self.pila_err, pie)
        pagina.layout().setStretchFactor(self.pila_err, 1)
        self.tabla_cli.setParent(pagina)
        self.tabla_cli.hide()
        return pagina

    def _preparar_tabla(self, tabla, modelo, columna_orden=0):
        proxy = Orden(self)
        proxy.setSourceModel(modelo)
        tabla.setModel(proxy)
        tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabla.setSortingEnabled(True)
        tabla.sortByColumn(columna_orden, Qt.SortOrder.DescendingOrder)
        tabla.verticalHeader().hide()
        tabla.verticalHeader().setMinimumSectionSize(48)
        tabla.verticalHeader().setDefaultSectionSize(48)
        tabla.setShowGrid(False)
        tabla.setWordWrap(False)
        tabla.setTextElideMode(Qt.TextElideMode.ElideRight)
        tabla.setCornerButtonEnabled(False)
        tabla.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        tabla.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        tabla.setMouseTracking(True)
        tabla.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tabla.customContextMenuRequested.connect(lambda pos, t=tabla: self._menu_tabla(t, pos))
        paleta = tabla.palette()   # la fila elegida en un violeta oscuro (sin transparencias que se sumen)
        paleta.setColor(QPalette.ColorRole.Highlight, QColor(ELEGIDA))
        paleta.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXTO))
        tabla.setPalette(paleta)
        h = tabla.horizontalHeader()
        h.setHighlightSections(False)
        h.setFixedHeight(40)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        h.setMinimumSectionSize(56)
        h.setStretchLastSection(False)
        insignia, dos_lineas, monto = DelegadoInsignia(tabla), DelegadoDosLineas(tabla), DelegadoMonto(tabla)
        for i, (clave, _titulo, ancho) in enumerate(modelo.COLUMNAS):
            if ancho:
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                h.resizeSection(i, ancho)
            else:
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            if clave in getattr(modelo, 'BOTONES', ()):   # (una celda con un botón: «Avisar» en Versiones)
                tabla.delegado_boton = DelegadoBoton(tabla)
                tabla.setItemDelegateForColumn(i, tabla.delegado_boton)
            elif clave in ('estado', 'licencia', 'version', 'resultado', 'cuando', 'sin_ver'):
                tabla.setItemDelegateForColumn(i, insignia)
            elif clave == 'monto':
                tabla.setItemDelegateForColumn(i, monto)
            elif clave in modelo.DOS_LINEAS:
                tabla.setItemDelegateForColumn(i, dos_lineas)
        # En una ventana angosta se esconden primero las columnas menos importantes (su dato sigue en el panel)
        indices = {clave: i for i, (clave, _t, _a) in enumerate(modelo.COLUMNAS)}
        tabla.ocultables = [indices[c] for c in modelo.OCULTAR]
        tabla.anchos = {i: ancho for i, (_c, _t, ancho) in enumerate(modelo.COLUMNAS) if ancho}
        tabla.minimo = modelo.ESTIRADA_MIN + sum(ancho for i, (_c, _t, ancho) in enumerate(modelo.COLUMNAS)
                                                 if ancho and i not in tabla.ocultables)
        tabla.selectionModel().currentRowChanged.connect(lambda actual, _anterior, t=tabla: self._fila_elegida(t, actual))
        copiar = QShortcut(QKeySequence.StandardKey.Copy, tabla)
        copiar.setContext(Qt.ShortcutContext.WidgetShortcut)
        copiar.activated.connect(lambda t=tabla: self._copiar_de_tabla(t, 'clave'))
        return proxy

    def _menu_config(self):
        menu = QMenu(self)
        a = menu.addAction(icono('llave'), 'Cambiar clave…')
        a.triggered.connect(self.cambiar_clave)
        # (2.3: sin «Cambiar dirección de la API…»: solo servía para probar con otro servidor; para eso está --api)
        menu.addSeparator()
        a = menu.addAction(icono('info'), f'Acerca de {APP}')
        a.triggered.connect(self._acerca)
        a = menu.addAction('Salir')
        a.setShortcut(QKeySequence('Ctrl+Q'))
        a.triggered.connect(self.close)
        # 2.7: abre hacia abajo, pegado a la derecha del ícono de la isla. popup() en vez de exec(): sin un bucle de
        # eventos anidado dentro del clic, y el menú se borra al cerrarse (antes cada clic dejaba uno colgado de la ventana)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        b = self.barra.btn_config
        menu.popup(b.mapToGlobal(QPoint(b.width() - menu.sizeHint().width(), b.height() + 10)))

    # --- Páginas
    def ir_a(self, pagina):
        if pagina not in self._indices:
            return
        self.pagina = pagina
        self.barra.marcar(pagina)
        self.paginas.setCurrentIndex(self._indices[pagina])
        self.lbl_titulo.setText(TITULOS.get(pagina) or next(texto for clave, _i, texto in PAGINAS if clave == pagina))
        self.lbl_sub.poner(SUBTITULOS[pagina])
        self.lado.setVisible(pagina not in ('resumen', 'cupones'))   # (2.8: Cupones, sin panel: la tabla a todo lo ancho)
        self.lado.setCurrentWidget(self.panel_error if pagina == 'errores' else self.panel)
        self.btn_exportar.setVisible(pagina in ('ventas', 'versiones', 'canjes'))
        self._tamano_lado(pagina)
        if pagina != 'versiones':
            self._licencia_pendiente = None
        if pagina == 'errores' and self._bandeja is not None:
            self._bandeja.hide()   # (ya está viendo los errores: el ícono de la notificación sobra)
        tabla = self._tabla_actual()
        self.seleccion = None
        self._suelta = None
        if tabla is not None:
            self._fila_elegida(tabla, tabla.selectionModel().currentIndex())
        else:
            self.panel.mostrar_vacio()
        self._cargar_pagina()

    def _ir_a_buscar(self):
        campo = {'ventas': self.buscar_v, 'canjes': self.buscar_c, 'versiones': self.buscar_ver,
                 'avisos': self.buscar_av, 'errores': self.buscar_err, 'cupones': self.buscar_cup}.get(self.pagina)
        if campo is None:
            self.ir_a('ventas')
            campo = self.buscar_v
        campo.setFocus()
        campo.selectAll()

    def _abrir_venta(self, pedido_id):
        """Desde «Últimas ventas»: abre Ventas (sin filtros que la escondan) con esa venta elegida. Si la lista es la de
        las eliminadas, vuelve a la normal y la elige cuando llegue."""
        if self.fechas_v.valor:
            self.fechas_v.poner(0)
        if self.filtro.currentData() == 'eliminadas' and not self.modelo_v.buscar('id', pedido_id):
            self._venta_a_elegir = pedido_id
            self.filtro.setCurrentIndex(self.filtro.findData(''))
        self.ir_a('ventas')
        for n in self.modelo_v.buscar('id', pedido_id):
            indice = self.proxy_v.mapFromSource(self.modelo_v.index(n, 0))
            if indice.isValid():
                self.tabla_v.selectRow(indice.row())
                self.tabla_v.scrollTo(indice)

    # --- Ayudantes de selección
    def _elegir_fila(self, tabla, modelo, n):
        """Elige en la tabla la fila n del modelo (si un filtro no la esconde) y la deja a la vista."""
        indice = tabla.model().mapFromSource(modelo.index(n, 0))
        if indice.isValid():
            tabla.selectRow(indice.row())
            tabla.scrollTo(indice)
        return indice.isValid()

    def _abrir_licencia(self, error):
        """«Abrir licencia» (desde un error): la compra o el canje de esa licencia, elegido en su tabla (con la licencia en
        el panel), como «Últimas ventas». Si una búsqueda o un filtro la esconden, el equipo del error en Versiones
        (ahí están todos los equipos activados, y el error viene de uno)."""
        lid = (error or {}).get('licencia_id')
        if not lid:
            return
        if self.modelo_v.buscar('licencia_id', lid) and self.fechas_v.valor:
            self.fechas_v.poner(0)   # (sin el filtro de fechas que la esconda)
        for pagina, tabla, modelo in (('ventas', self.tabla_v, self.modelo_v), ('canjes', self.tabla_c, self.modelo_c)):
            filas = [n for n in modelo.buscar('licencia_id', lid)
                     if tabla.model().mapFromSource(modelo.index(n, 0)).isValid()]
            if filas:
                self.ir_a(pagina)
                self._elegir_fila(tabla, modelo, filas[0])
                return
        if self.filtro_ver.valor != 'todos':
            self.filtro_ver.poner('todos')
        if self.buscar_ver.text():
            self.buscar_ver.clear()
        self._filtrar_locales()
        self.ir_a('versiones')
        self._licencia_pendiente = (lid, f"{lid}/{error.get('equipo')}", error.get('clave'))
        self._elegir_pendiente()

    def _elegir_pendiente(self):
        """La licencia de «Abrir licencia» en Versiones, en cuanto están los equipos."""
        if not self._licencia_pendiente or self.pagina != 'versiones' or not self.modelo_ver.rowCount():
            return
        lid, ident, clave = self._licencia_pendiente
        self._licencia_pendiente = None
        filas = self.modelo_ver.buscar('id', ident) or self.modelo_ver.buscar('licencia_id', lid)
        if filas and self._elegir_fila(self.tabla_ver, self.modelo_ver, filas[0]):
            return
        if clave:   # ya no tiene equipos: se busca la clave en Ventas
            self.ir_a('ventas')
            self.buscar_v.setText(clave)
            self._cargar_ventas()
        self._avisar('Esa licencia ya no tiene equipos activados.', 'info')

    def _tabla_actual(self):
        return {'ventas': self.tabla_v, 'canjes': self.tabla_c, 'versiones': self.tabla_ver, 'avisos': self.tabla_av,
                'cupones': self.tabla_cup,
                'errores': self.tabla_cli if self.vista_errores.valor == 'usuario' else self.tabla_err}.get(self.pagina)

    def _fila_de(self, tabla, indice):
        if not indice.isValid():
            return None
        proxy = tabla.model()
        return proxy.sourceModel().fila(proxy.mapToSource(indice).row())

    def _fila_actual(self, tabla):
        return self._fila_de(tabla, tabla.selectionModel().currentIndex())

    def _origen(self, tabla, fila):
        if tabla is self.tabla_v:
            return ('venta', fila['id'])
        if tabla is self.tabla_c:
            return ('canje', fila['id'])
        return ('licencia', fila['licencia_id']) if fila.get('licencia_id') else None

    def _fila_elegida(self, tabla, actual):
        if self._restaurando or tabla is not self._tabla_actual():
            return
        fila = self._fila_de(tabla, actual)
        if tabla is self.tabla_err:
            self._elegir_error(fila)
            return
        if tabla is self.tabla_cli:
            self._elegir_cliente_err(fila)
            return
        seleccion = self._origen(tabla, fila) if fila else None
        if seleccion != ('venta', self._suelta):
            self._suelta = None   # (eligió otra fila: la venta que se había quedado en el panel ya no)
        if not seleccion:
            self.seleccion = None
            self.panel.mostrar_vacio()
            return
        if self.seleccion == seleccion and self.panel.fila is not None:
            return
        self.seleccion = seleccion
        self.panel.mostrar_fila(seleccion[0], fila)
        self._timer_detalle.start()

    def _recargar(self, tabla, modelo, filas):
        """Pone filas nuevas sin perder la fila elegida ni la posición del scroll."""
        anterior = self._fila_actual(tabla)
        ident = anterior['id'] if anterior else None
        posicion = tabla.verticalScrollBar().value()
        encontrada = False
        self._restaurando = True
        try:
            modelo.cargar(filas)
            for n in modelo.buscar('id', ident):
                indice = tabla.model().mapFromSource(modelo.index(n, 0))
                if not indice.isValid():
                    continue   # la esconde un filtro rápido
                tabla.selectionModel().setCurrentIndex(
                    indice, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
                encontrada = True
            tabla.verticalScrollBar().setValue(posicion)
        finally:
            self._restaurando = False
        if ident is not None and not encontrada and tabla is self._tabla_actual():
            if tabla is self.tabla_err:
                self._elegir_error(None)
            elif tabla is self.tabla_cli:
                self._elegir_cliente_err(None)
            elif tabla is self.tabla_v and self._suelta is not None and self.seleccion == ('venta', self._suelta):
                pass   # la venta que se acaba de eliminar (o restaurar) se va de la lista pero sigue en el panel
            else:
                self.seleccion = None
                self.panel.mostrar_vacio()

    # --- Carga de datos (siempre en segundo plano y de una en una)
    def usar_clave(self, clave):
        """Desde aquí todo va con esta clave y con self.api_url. Lo que todavía no llegó con la clave o la API de antes
        se descarta al llegar (si no, un 401 viejo marcaría como mala la clave nueva, o se verían datos del otro servidor)."""
        self.cliente = ClienteApi(self.api_url, clave, solo_lectura=self.solo_lectura)
        self._generacion += 1
        self._ronda += 1
        for tipo in self._num:
            self._num[tipo] += 1
        self._cuando.clear()
        self._actualizando = False
        self._clave_mala = False
        self._pausa_hasta = 0.0
        self._poner_estado()

    def actualizar_todo(self, auto=False):
        """Una sola petición (panel) trae el resumen, las ventas y los canjes; después, lo de la página abierta y el
        detalle de la fila elegida. Con el admin.php anterior se hace como antes: resumen primero (así una clave mala
        cuenta un solo intento) y después las dos tablas."""
        if not self.cliente:
            self._falta_clave()
            return
        if self._actualizando:
            return
        self._actualizando = True
        self._ronda += 1
        ronda, cliente = self._ronda, self.cliente
        if self.servidor_nuevo is False and auto:   # (con «Actualizar» o F5 se vuelve a probar: quizá ya lo subieron)
            self._actualizar_como_antes(ronda)
            return
        estado, buscar = self.filtro.currentData() or '', self.buscar_v.text().strip()
        self._num['ventas'] += 1
        numero = self._num['ventas']
        self.trabajos.iniciar(lambda: cliente.panel(estado, buscar, LIMITE_LISTA),
                              lambda r: self._panel_listo(ronda, numero, estado, buscar, r),
                              lambda e: self._panel_fallo(ronda, e), clave='panel')

    def _panel_listo(self, ronda, numero, estado, buscar, r):
        if ronda != self._ronda:
            return   # de una clave o una API que ya no se usan
        self._marcar_servidor(True)
        self._clave_mala = False
        self._pausa_hasta = 0.0
        self.banda.hide()
        self._poner_resumen(r['resumen'])
        self._poner_resumen_errores(r['errores'])
        if numero == self._num['ventas']:   # (si mientras tanto salió otra búsqueda, esa manda)
            self._poner_ventas(r['ventas'], estado, buscar)
        if buscar or self.buscar_c.text().strip():
            self._cargar_canjes()   # los canjes del panel no vienen filtrados con la búsqueda de canjes
        else:
            self._num['canjes'] += 1
            self._poner_canjes(r['canjes'], '')
        if self.seleccion:
            self._cargar_detalle()
        self._cargar_pagina(forzar=True)
        self._fin_actualizacion(True)

    def _panel_fallo(self, ronda, error):
        if ronda != self._ronda or isinstance(error, Cancelada):
            return
        if isinstance(error, ApiError) and error.desconocida:   # el admin.php publicado todavía es el anterior
            self._marcar_servidor(False)
            self._actualizar_como_antes(ronda)
            return
        self._error_carga(error)
        self._fin_actualizacion(False)

    def _actualizar_como_antes(self, ronda):
        cliente = self.cliente
        self.trabajos.iniciar(cliente.resumen, lambda r: self._resumen_listo(ronda, r),
                              lambda e: self._resumen_fallo(ronda, e))

    def _resumen_listo(self, ronda, resumen):
        if ronda != self._ronda:
            return
        self._clave_mala = False
        self._pausa_hasta = 0.0
        self.banda.hide()
        self._poner_resumen(resumen)
        self._listas_pendientes = 2
        self._ronda_ok = True
        fin = lambda ok: self._lista_terminada(ronda, ok)
        self._cargar_ventas(fin=fin)
        self._cargar_canjes(fin=fin)
        if self.seleccion:
            self._cargar_detalle()

    def _resumen_fallo(self, ronda, error):
        if ronda != self._ronda:
            return
        self._error_carga(error)
        self._fin_actualizacion(False)

    def _lista_terminada(self, ronda, ok):
        if ronda != self._ronda:
            return
        self._ronda_ok = self._ronda_ok and ok
        self._listas_pendientes -= 1
        if self._listas_pendientes <= 0:
            self._fin_actualizacion(self._ronda_ok)

    def _fin_actualizacion(self, ok):
        self._actualizando = False
        self.intento_listo = True
        if ok:
            self.ultima = dt.datetime.now()
        self._poner_estado()
        self.datos_listos.emit()

    def _marcar_servidor(self, nuevo):
        """Lo que se sabe del admin.php publicado: el nuevo (con versiones, avisos, historial y notas) o el anterior."""
        if self.servidor_nuevo == nuevo:
            return
        self.servidor_nuevo = nuevo
        self.panel.set_servidor(nuevo)
        for modelo in (self.modelo_v, self.modelo_c):   # con el anterior, «Versión» y «Último uso» quedan en «—»
            modelo.poner_con_versiones(bool(nuevo))
        if nuevo:
            self.banda_servidor.hide()
            return
        self.banda_servidor.mostrar(SERVIDOR_VIEJO)
        self.version_ultima = None
        self.modelo_ver.cargar([])
        self.modelo_av.cargar([])
        self.modelo_cup.cargar([])
        self.servidor_cupones = False
        self.btn_nuevo_cupon.setEnabled(False)
        self._vaciar_errores(FALTA_SERVIDOR)
        for tabla in (self.tabla_ver, self.tabla_av, self.tabla_cup):
            tabla.mensaje_vacio = FALTA_SERVIDOR_CUPONES if tabla is self.tabla_cup else FALTA_SERVIDOR
            tabla.viewport().update()
        self.grafica.vaciar(FALTA_SERVIDOR)
        self.grafica_versiones.vaciar(FALTA_SERVIDOR)
        for bloque in (self.bloque_versiones, self.plan_versiones):
            bloque.sin_datos(FALTA_SERVIDOR)
        self.panel.set_eliminar(False)
        self._poner_filtro_eliminadas(None)
        self.lbl_grafica.clear()
        self._poner_pies()

    def _error_carga(self, error):
        codigo = error.codigo if isinstance(error, ApiError) else None
        if codigo == 401:
            self._clave_rechazada(error)
        elif codigo == 429:   # lo provocaron claves malas: se ofrece cambiarla y no se insiste hasta que pase el bloqueo
            self._pausa_hasta = time.monotonic() + (error.reintentar or 900)
            self.banda.mostrar(mensaje_de(error), 'Cambiar clave')
        else:
            self.banda.mostrar(mensaje_de(error))
        for tabla in (self.tabla_v, self.tabla_c, self.tabla_ver, self.tabla_av, self.tabla_err, self.tabla_cli,
                      self.tabla_cup):
            if tabla.model().rowCount() == 0:
                tabla.mensaje_vacio = 'No se pudieron cargar los datos.'
                tabla.viewport().update()
        # (lo del Resumen que todavía esperaba sus datos tampoco se queda en «Cargando…»)
        if not self.grafica.dias:
            self.grafica.vaciar('No se pudieron cargar los datos.')
        if self.recientes.cargando:
            self.recientes.poner([], 'No se pudieron cargar las ventas.')
        for grafica in (self.grafica_versiones, self.bloque_versiones.grafica):
            if grafica is not None and not grafica.filas:
                grafica.vaciar('No se pudieron cargar los datos.')

    def _clave_rechazada(self, error):
        # Desde aquí no sale ninguna petición sola (ni al filtrar, buscar o elegir una fila): cada clave mala cuenta
        # para el bloqueo de 15 minutos. Solo «Reintentar», F5 o una clave nueva vuelven a preguntar.
        self._clave_mala = True
        self.banda.mostrar(mensaje_de(error), 'Cambiar clave')

    def _falta_clave(self):
        self.banda.mostrar('Falta la clave de administrador. Pégala para ver tus ventas.', 'Pegar clave')
        texto = 'Pega la clave de administrador para ver los datos.'
        for tabla in (self.tabla_v, self.tabla_c, self.tabla_ver, self.tabla_av, self.tabla_err, self.tabla_cli):
            tabla.mensaje_vacio = texto
            tabla.viewport().update()
        if not self.grafica.dias:
            self.grafica.vaciar(texto)
        if self.recientes.cargando:
            self.recientes.poner([], texto)
        for grafica in (self.grafica_versiones, self.bloque_versiones.grafica):
            if grafica is not None and not grafica.filas:
                grafica.vaciar(texto)

    def _cargar_ventas(self, fin=None, mas=False):
        self._timer_buscar_v.stop()
        if not self.cliente or self._clave_mala:   # con una clave rechazada no se insiste (ver _clave_rechazada)
            if fin:
                fin(False)
            return
        estado, buscar = self.filtro.currentData() or '', self.buscar_v.text().strip()
        if mas and (estado, buscar) != self._consulta_v:
            mas = False   # cambiaron el filtro o la búsqueda y todavía no se recargó: se empieza desde el principio
        desde = self.modelo_v.rowCount() if mas else 0
        self._num['ventas'] += 1
        numero, cliente = self._num['ventas'], self.cliente
        if not self.modelo_v.rowCount():
            self.tabla_v.mensaje_vacio = 'Cargando ventas…'
            self.tabla_v.viewport().update()

        def listo(filas):
            if numero == self._num['ventas']:
                self._poner_ventas(filas, estado, buscar, mas)
            if fin:
                fin(True)

        def fallo(error):
            vigente = numero == self._num['ventas']
            if vigente and not isinstance(error, Cancelada):
                self._error_carga(error)
            if fin:
                fin(not vigente)

        self.trabajos.iniciar(lambda: cliente.ventas(estado, buscar, LIMITE_LISTA, desde), listo, fallo, clave='ventas')

    def _poner_ventas(self, filas, estado, buscar, mas=False):
        if mas:   # si entró una venta nueva, la página siguiente repite la última fila: no se duplica
            ya = {f['id'] for f in self.modelo_v.filas}
            self.modelo_v.agregar([f for f in filas if f['id'] not in ya])
        else:
            self._recargar(self.tabla_v, self.modelo_v, filas)
            if not estado and not buscar:
                self.recientes.poner(filas)
            if self.fechas_v.valor:   # «Hoy», «7 días»: desde el día de hoy (con la app abierta de un día para otro,
                self._filtrar_fechas()  # «Hoy» pasa a ser el día nuevo)
            # La venta que quedó en el panel (se restauró y volvió a la lista) o la que pidió «Últimas ventas»: elegida
            for pendiente in (self._suelta if self.seleccion == ('venta', self._suelta) else None, self._venta_a_elegir):
                n = self.modelo_v.buscar('id', pendiente)
                if n and self.pagina == 'ventas' and self._elegir_fila(self.tabla_v, self.modelo_v, n[0]):
                    self._suelta = self._venta_a_elegir = None
                    break
            if self._venta_a_elegir is not None and estado != 'eliminadas':
                self._venta_a_elegir = None   # (ya llegó la lista donde tenía que estar: no se busca más)
        self._consulta_v = (estado, buscar)
        self._hay_mas_v = len(filas) >= LIMITE_LISTA
        vacio = {'': 'Todavía no hay ventas.', 'pagado': 'No hay ventas pagadas.',
                 'reembolsado': 'No hay ventas reembolsadas.', 'pendiente': 'No hay pagos sin completar.',
                 'todos': 'Todavía no hay ventas.',
                 'eliminadas': 'No hay ventas eliminadas. Las que elimines quedan aquí y se pueden restaurar.'
                 }.get(estado, 'No hay ventas con este filtro.')
        self.tabla_v.mensaje_vacio = f'No se encontraron ventas para «{buscar}».' if buscar else vacio
        self._poner_pies()

    def _cargar_canjes(self, fin=None):
        self._timer_buscar_c.stop()
        if not self.cliente or self._clave_mala:
            if fin:
                fin(False)
            return
        buscar = self.buscar_c.text().strip()
        self._num['canjes'] += 1
        numero, cliente = self._num['canjes'], self.cliente
        if not self.modelo_c.rowCount():
            self.tabla_c.mensaje_vacio = 'Cargando canjes…'
            self.tabla_c.viewport().update()

        def listo(filas):
            if numero == self._num['canjes']:
                self._poner_canjes(filas, buscar)
            if fin:
                fin(True)

        def fallo(error):
            vigente = numero == self._num['canjes']
            if vigente and not isinstance(error, Cancelada):
                self._error_carga(error)
            if fin:
                fin(not vigente)

        self.trabajos.iniciar(lambda: cliente.canjes(buscar), listo, fallo, clave='canjes')

    def _poner_canjes(self, filas, buscar):
        self._recargar(self.tabla_c, self.modelo_c, filas)
        self.tabla_c.mensaje_vacio = (f'No se encontraron canjes para «{buscar}».' if buscar
                                      else 'Todavía no hay canjes de Gumroad.')
        self._poner_pies()

    def _cargar_resumen(self):
        if self.cliente and not self._clave_mala:
            generacion, cliente = self._generacion, self.cliente

            def listo(resumen):
                if generacion == self._generacion:
                    self._poner_resumen(resumen)

            self.trabajos.iniciar(cliente.resumen, listo, lambda _e: None, clave='resumen')

    def _vigente(self, nombre, segundos):
        return nombre in self._cuando and time.monotonic() - self._cuando[nombre] < segundos

    def _cargar_pagina(self, forzar=False):
        """Lo que necesita la página abierta además del panel (solo con el servidor nuevo)."""
        if not self.cliente or self._clave_mala or self.servidor_nuevo is not True:
            return
        if self.pagina == 'resumen':
            self._cargar_estadisticas(forzar)
            self._cargar_version()
            self._cargar_versiones(forzar)   # (las barras de equipos por versión del bloque de versiones)
        elif self.pagina == 'versiones':
            self._cargar_versiones(forzar)
            self._cargar_version()
        elif self.pagina == 'avisos':
            self._cargar_avisos(forzar)
        elif self.pagina == 'cupones':
            self._cargar_cupones(forzar)
        elif self.pagina == 'errores':
            self._cargar_errores(forzar)

    def _pedir(self, nombre, funcion, al_listo, al_fallar=None):
        """Una carga de la página: con su número (lo que llegue de una vieja no cuenta) y su clave en la cola."""
        self._num[nombre] += 1
        numero = self._num[nombre]

        def listo(resultado):
            if numero == self._num[nombre]:
                self._cuando[nombre] = time.monotonic()
                al_listo(resultado)

        def fallo(error):
            if numero == self._num[nombre] and not isinstance(error, Cancelada):
                if isinstance(error, ApiError) and error.codigo == 401:
                    self._clave_rechazada(error)
                if al_fallar:
                    al_fallar(error)

        self.trabajos.iniciar(funcion, listo, fallo, clave=nombre)

    def _texto_fallo(self, error):
        return FALTA_SERVIDOR if isinstance(error, ApiError) and error.desconocida else mensaje_de(error)

    def _cargar_estadisticas(self, forzar=False):
        if forzar or not self._vigente('estadisticas', AUTO_MS / 1000 - 5):
            cliente = self.cliente
            self._pedir('estadisticas', lambda: cliente.estadisticas(DIAS_GRAFICA), self._poner_estadisticas,
                        lambda e: self.grafica.vaciar(f'No se pudo cargar la gráfica. {self._texto_fallo(e)}'))

    def _poner_estadisticas(self, r):
        self.estadisticas = r
        if r['dias']:
            self.grafica.poner(r['dias'], r['moneda'])
        else:
            self.grafica.vaciar('Sin datos para la gráfica.')
        ingresos, ventas = sum(d['ingresos'] for d in r['dias']), sum(d['ventas'] for d in r['dias'])
        texto = html.escape(f"{dinero(ingresos, r['moneda'])} · {plural(ventas, 'venta', 'ventas')}")
        if any(d['reembolsos'] for d in r['dias']):   # la leyenda del puntito naranja de debajo de las barras
            texto += (f'<span style="color:{TEXTO_TENUE}">&nbsp;&nbsp;·&nbsp;&nbsp;</span><span style="color:{AVISO}">●</span>'
                      f'<span style="color:{TEXTO_TENUE}">&nbsp;día con reembolso</span>')
        self.lbl_grafica.setText(texto)

    def _cargar_version(self, refrescar=False):
        if refrescar or not self._vigente('version', VIGENCIA_VERSION_S):
            cliente = self.cliente
            self._pedir('version', lambda: cliente.version_actual(refrescar), self._poner_version)

    def _poner_version(self, info):
        self.version_info = info
        self._poner_bloques_versiones()

    def _poner_bloques_versiones(self):
        if self.servidor_nuevo is False:
            return
        versiones = (self.resumen or {}).get('versiones')
        if versiones is not None:
            self.bloque_versiones.poner(versiones, self.version_info)
        elif self.resumen is not None:
            self.bloque_versiones.sin_datos('El servidor no mandó los datos de versiones.')
        if self.versiones is not None:
            ultima = self.versiones['ultima'] or self.version_ultima
            self.plan_versiones.poner(self.modelo_ver.filas, ultima, self.version_info, self.versiones['por_version'])
            self.bloque_versiones.poner_por_version(self.versiones['por_version'], ultima)

    def _cargar_versiones(self, forzar=False):
        if forzar or not self._vigente('versiones', AUTO_MS / 1000 - 5):
            cliente = self.cliente
            if not self.modelo_ver.rowCount():
                self.tabla_ver.mensaje_vacio = 'Cargando equipos…'
                self.tabla_ver.viewport().update()

            def fallo(error):
                self.tabla_ver.mensaje_vacio = f'No se pudieron cargar los equipos. {self._texto_fallo(error)}'
                self.tabla_ver.viewport().update()
                for grafica in (self.grafica_versiones, self.bloque_versiones.grafica):   # (no se quedan en «Cargando…»)
                    if grafica is not None and not grafica.filas:
                        grafica.vaciar('No se pudieron cargar los equipos.')
                if self.versiones is None:
                    self.plan_versiones.sin_datos(f'No se pudieron cargar los equipos. {self._texto_fallo(error)}')

            self._pedir('versiones', lambda: cliente.versiones('todos'), self._poner_versiones, fallo)

    def _poner_versiones(self, r):
        """Los equipos llegan uno por uno y en la tabla van juntos por cliente (agrupar_versiones). Los filtros cuentan
        clientes con la licencia activa, como la tarjeta de arriba (así los números de la página coinciden)."""
        self.versiones = r
        if r['ultima']:
            self.version_ultima = r['ultima']
        ultima = r['ultima'] or self.version_ultima
        self.modelo_ver.poner_ultima(ultima)
        clientes = agrupar_versiones(r['equipos'], ultima)
        self._recargar(self.tabla_ver, self.modelo_ver, clientes)
        self.grafica_versiones.poner(r['por_version'], ultima)
        self.tabla_ver.mensaje_vacio = 'Todavía ningún cliente activó CineCaptions.'
        cuenta = contar_estados([c for c in clientes if c['licencia_estado'] == 'activa'], self.modelo_ver)
        self.filtro_ver.contar('todos', len(clientes))
        for valor in ('desactualizado', 'al_dia', 'sin_datos'):
            self.filtro_ver.contar(valor, cuenta.get(valor, 0))
        self._poner_bloques_versiones()
        self._filtrar_locales()
        self._elegir_pendiente()   # («Abrir licencia» desde un error, si esperaba a los equipos)

    def _cargar_avisos(self, forzar=False):
        if forzar or not self._vigente('avisos', AUTO_MS / 1000 - 5):
            cliente = self.cliente
            if not self.modelo_av.rowCount():
                self.tabla_av.mensaje_vacio = 'Cargando avisos…'
                self.tabla_av.viewport().update()

            def fallo(error):
                self.tabla_av.mensaje_vacio = f'No se pudieron cargar los avisos. {self._texto_fallo(error)}'
                self.tabla_av.viewport().update()

            self._pedir('avisos', lambda: cliente.avisos(limite=200), self._poner_avisos, fallo)

    def _poner_avisos(self, avisos):
        self._recargar(self.tabla_av, self.modelo_av, avisos)
        self.tabla_av.mensaje_vacio = 'Todavía no mandaste avisos de actualización.'
        self.filtro_av.contar('ok', sum(1 for a in avisos if a['ok']))
        self.filtro_av.contar('no', sum(1 for a in avisos if not a['ok']))
        self._filtrar_locales()

    # --- Errores de los clientes
    def _cargar_errores(self, forzar=False):
        """Todos los errores (hasta 1000, los sin ver siempre entran: vienen primero); «Sin ver» y la búsqueda se filtran
        aquí, sin pedir nada al servidor."""
        if forzar or not self._vigente('errores', AUTO_MS / 1000 - 5):
            cliente = self.cliente
            if not self.modelo_err.rowCount():
                self._mensaje_errores('Cargando errores…')

            def fallo(error):
                if isinstance(error, ApiError) and error.desconocida:   # admin.php de antes de la 5.71 de CineCaptions
                    self.servidor_errores = False
                    self._vaciar_errores(FALTA_SERVIDOR_ERRORES)
                else:
                    self._mensaje_errores(f'No se pudieron cargar los errores. {self._texto_fallo(error)}')
                self._poner_pies()

            self._pedir('errores', lambda: cliente.errores('todos', '', None, LIMITE_LISTA), self._poner_errores, fallo)

    def _mensaje_errores(self, texto):
        """El mensaje de las dos listas de la página Errores cuando no tienen filas."""
        for tabla in (self.tabla_err, self.tabla_cli):
            tabla.mensaje_vacio = texto
            tabla.viewport().update()

    def _vaciar_errores(self, mensaje):
        """Sin errores a la vista (otro servidor, o uno que todavía no los tiene): las dos listas con su mensaje, sin
        cliente elegido y sin contador."""
        self.modelo_err.cargar([])
        self.modelo_cli.cargar([])
        self.cliente_err = None
        self.errores_cliente.mostrar_vacio('')
        self._mensaje_errores(mensaje)
        self._poner_resumen_errores(None)

    def _poner_errores(self, r):
        self.servidor_errores = True
        self.modelo_err.poner_ultima(self.version_ultima)
        self._recargar(self.tabla_err, self.modelo_err, r['errores'])
        self._mensaje_errores('Ningún cliente ha tenido errores.')
        elegidos = self.modelo_err.buscar('id', self.error_elegido)
        if elegidos and self.pagina == 'errores':   # (el panel muestra lo nuevo: veces, última vez, si se vio)
            fila = self.modelo_err.fila(elegidos[0])
            self.panel_error.poner_cambios({k: fila[k] for k in ('visto', 'veces', 'ultima', 'primera', 'nombre_equipo')})
        if r['resumen'] is not None:
            self._poner_resumen_errores(r['resumen'])
        self._filtrar_locales()
        self._agrupar_errores()

    def _agrupar_errores(self):
        """La vista «Por usuario» con lo último de la tabla: los clientes (sin perder el elegido) y sus errores."""
        self._recargar(self.tabla_cli, self.modelo_cli, agrupar_errores(self.modelo_err.filas))
        self._poner_errores_cliente()
        self._poner_pies()

    def _errores_de_cliente(self, licencia_id):
        """Los errores de un cliente, del más reciente al más viejo."""
        return sorted((e for e in self.modelo_err.filas if e['licencia_id'] == licencia_id),
                      key=lambda e: e['ultima'] or '', reverse=True)

    def _poner_errores_cliente(self):
        """2.3: la columna «Por cliente»: cada cliente de la lista (en su orden y con su filtro) con sus errores que pasan
        el filtro; del elegido, todos los suyos."""
        grupos = []
        for r in range(self.proxy_cli.rowCount()):
            fila = self._fila_de(self.tabla_cli, self.proxy_cli.index(r, 0))
            if not fila:
                continue
            todos = self._errores_de_cliente(fila['licencia_id'])
            visibles = (todos if fila['licencia_id'] == self.cliente_err or self._filtro_error is None
                        else [e for e in todos if self._filtro_error(e)])
            if visibles:
                grupos.append((visibles, todos))
        if grupos:
            self.errores_cliente.poner(grupos, self.error_elegido, self.cliente_err)
        else:
            self.errores_cliente.mostrar_vacio(self.tabla_cli.mensaje_vacio if self.modelo_cli.rowCount() else '')

    def _elegir_error_de_cliente(self, error):
        """Un error en la columna «Por cliente»: su cliente queda elegido en la lista (escondida) y su informe a la derecha."""
        if error['licencia_id'] != self.cliente_err:
            self.cliente_err = error['licencia_id']
            filas = self.modelo_cli.buscar('licencia_id', error['licencia_id'])
            if filas:
                self.tabla_cli.blockSignals(True)
                self.tabla_cli.selectionModel().blockSignals(True)
                self._elegir_fila(self.tabla_cli, self.modelo_cli, filas[0])
                self.tabla_cli.selectionModel().blockSignals(False)
                self.tabla_cli.blockSignals(False)
        self._elegir_error(error)

    def _todo_visto_de(self, licencia_id):
        """«Marcar visto» de un cliente en la columna «Por cliente»."""
        self.cliente_err = licencia_id
        self._todo_visto_cliente()

    def _elegir_cliente_err(self, fila):
        """Un cliente en «Por usuario»: sus errores a la par y, en el panel, el más reciente (si no se estaba viendo ya uno
        de los suyos)."""
        lid = fila['licencia_id'] if fila else None
        self.cliente_err = lid
        if lid is None:
            self._poner_errores_cliente()
            self._elegir_error(None)
            return
        errores = self._errores_de_cliente(lid)
        actual = self.modelo_err.buscar('id', self.error_elegido)
        if errores and (not actual or self.modelo_err.fila(actual[0])['licencia_id'] != lid):
            self._elegir_error(errores[0])
        self._poner_errores_cliente()

    def _cambiar_vista_errores(self, vista):
        """«Por usuario» o «Todos los errores»: el error que se estaba viendo sigue elegido en la otra vista."""
        self.pila_err.setCurrentIndex(0 if vista == 'usuario' else 1)
        self._poner_pies()
        if self.pagina != 'errores':
            return
        actual = self.modelo_err.buscar('id', self.error_elegido)
        error = self.modelo_err.fila(actual[0]) if actual else None
        if vista == 'usuario':
            if error is None:
                self._fila_elegida(self.tabla_cli, self.tabla_cli.selectionModel().currentIndex())
                return
            self.cliente_err = error['licencia_id']
            self._filtrar_locales()   # (así su cliente está en la lista aunque ya no tenga errores sin ver)
            filas = self.modelo_cli.buscar('licencia_id', error['licencia_id'])
            if filas:
                self._elegir_fila(self.tabla_cli, self.modelo_cli, filas[0])
            self._poner_errores_cliente()
        elif not (error and self._elegir_fila(self.tabla_err, self.modelo_err, actual[0])):
            self._fila_elegida(self.tabla_err, self.tabla_err.selectionModel().currentIndex())

    def _contar_errores(self):
        filas = self.modelo_err.filas
        self.filtro_err.contar('sin_ver', sum(1 for e in filas if not e['visto']) if filas else None)
        self.filtro_err.contar('todos', len(filas) if filas else None)

    def _elegir_error(self, fila):
        """El error que se ve en el panel (desde la tabla de todos o desde los errores de un cliente)."""
        self.errores_cliente.marcar(fila['id'] if fila else None)
        if not fila:
            self.error_elegido = None
            self._timer_error.stop()
            self.panel_error.mostrar_vacio()
            return
        if self.error_elegido == fila['id'] and self.panel_error.fila is not None:
            return
        self.error_elegido = fila['id']
        self.panel_error.mostrar_fila(fila)
        self._timer_error.start()

    def _cargar_error(self):
        """El informe del error elegido (error_detalle)."""
        self._timer_error.stop()
        ident = self.error_elegido
        if ident is None or not self.cliente:
            return
        if self._clave_mala:
            self.panel_error.mostrar_error('La clave de administrador no es correcta. Cámbiala en Configuración → '
                                           'Cambiar clave.')
            return
        cliente = self.cliente

        def listo(error):
            if ident != self.error_elegido:
                return   # llegó tarde: ya eligieron otro
            self.panel_error.mostrar_detalle(error)
            # 2.5: si la fila de la lista no sabía de alguna captura (llegó después), se piden las que dice el detalle (lo que
            # entregue la tarea anterior ya no cuenta: _pedir)
            if self._capturas_pedidas != (ident, cuales_captura(error)):
                self._cargar_captura(ident)
            cambio = False
            for n in self.modelo_err.buscar('id', ident):   # la fila de la tabla, con lo último que dijo el servidor
                antes = self.modelo_err.fila(n)
                cambio = cambio or any(antes.get(k) != error.get(k) for k in ('visto', 'veces', 'ultima', 'titulo', 'mensaje'))
                self.modelo_err.cambiar(n, {k: v for k, v in error.items() if k != 'detalle'})
            if cambio:   # (en «Por usuario», la cuenta del cliente y su lista)
                self._agrupar_errores()

        def fallo(error):
            if ident == self.error_elegido:
                self.panel_error.mostrar_error(self._texto_fallo(error))

        self._pedir('error_detalle', lambda: cliente.error_detalle(ident), listo, fallo)
        self._cargar_captura(ident)

    def _cargar_captura(self, ident):
        """2.3: la captura del error elegido (error_captura), si la tiene. Las últimas se guardan en memoria: volver a un error
        no la pide otra vez. 2.5: las dos (la de la pantalla y la de la ventana de CineCaptions) en UNA tarea de la cola, una
        después de la otra; si una falla y la otra no, se ve la que llegó y la otra dice por qué (y no se guarda en memoria)."""
        cuales = cuales_captura(self.panel_error.error())
        self._capturas_pedidas = (ident, cuales)
        if not cuales:
            return
        cache = self.__dict__.setdefault('_capturas', {})
        if ident in cache and set(cache[ident]) == set(cuales):
            self.panel_error.poner_captura(ident, cache[ident])
            return
        cliente = self.cliente

        def pedir():   # (en el hilo de la petición)
            llegaron, fallos = {}, {}
            for cual in cuales:
                try:
                    llegaron[cual] = cliente.error_captura(ident, cual)
                except ApiError as error:
                    if error.codigo == 401:
                        raise   # (la clave: que la vea _pedir)
                    fallos[cual] = error
            if not llegaron:
                raise next(iter(fallos.values()))
            return llegaron, fallos

        def listo(resultado):
            llegaron, fallos = resultado
            if not fallos:
                cache[ident] = llegaron
                while len(cache) > 12:
                    cache.pop(next(iter(cache)))
            self.panel_error.poner_captura(ident, llegaron, {c: self._texto_fallo(x) for c, x in fallos.items()})

        def fallo(error):
            self.panel_error.captura_fallo(ident, self._texto_fallo(error))

        self._pedir('error_captura', pedir, listo, fallo)

    def _poner_resumen_errores(self, resumen, propio=False):
        """El contador de «Errores» en la isla del menú (los sin ver) y, si llegó un error nuevo, el aviso al dueño.
        propio: el resumen que devolvió un cambio hecho desde aquí («Marcar como visto»), que nunca avisa."""
        anterior, self.errores_resumen = self.errores_resumen, resumen
        n = resumen['sin_ver'] if resumen else 0
        self.barra.botones['errores'].poner_contador(n or None, PELIGRO if n else None)
        self.btn_todo_visto.setEnabled(bool(n) or any(not e['visto'] for e in self.modelo_err.filas))
        if resumen is not None and not propio and self._hay_errores_nuevos(resumen, anterior):
            self._avisar_errores(resumen)

    def _hay_errores_nuevos(self, resumen, anterior):
        """¿Llegó un error que todavía no se avisó? Lo dicen ultimo_id (el id más alto de los sin ver) y ultima (la última
        vez que pasó uno sin ver), comparados con lo que ya se avisó: queda en config.json, {'id', 'ultima'} por cada
        dirección de la API (la 2.2.0 guardaba solo el id: se sigue entendiendo). Así no se avisa dos veces al reiniciar
        la app. La primera vez solo se guarda: los errores que ya había no se avisan. Un error ya visto que vuelve a pasar
        conserva su id (errores.php lo reabre con «ultima» nueva): con la app abierta se nota porque hay más sin ver que en
        el resumen anterior y la última vez es más nueva; si pasó con la app cerrada, porque al abrirla la última vez es
        más nueva que la guardada, aunque el id no suba. En las capturas nunca se avisa ni se guarda nada."""
        if self.captura:
            return False
        avisados = self.config.datos.get('errores_avisados')
        avisados = dict(avisados) if isinstance(avisados, dict) else {}
        guardado = avisados.get(self.api_url)
        if isinstance(guardado, int) and not isinstance(guardado, bool):
            guardado = {'id': guardado}
        guardado = guardado if isinstance(guardado, dict) else None
        id_avisado = (guardado or {}).get('id')
        id_avisado = id_avisado if isinstance(id_avisado, int) and not isinstance(id_avisado, bool) else None
        ultima_avisada = (guardado or {}).get('ultima')
        ultima_avisada = ultima_avisada if isinstance(ultima_avisada, str) else None
        ultimo, ultima = resumen['ultimo_id'] or 0, resumen['ultima'] or ''
        nuevo = id_avisado is not None and ultimo > id_avisado
        if anterior is not None:
            volvio = resumen['sin_ver'] > anterior['sin_ver'] and ultima > (anterior['ultima'] or '')
        else:   # recién abierta: lo que pasó con la app cerrada
            volvio = bool(ultima_avisada) and resumen['sin_ver'] > 0 and ultima > ultima_avisada
        if id_avisado is None or ultimo > id_avisado or ultima > (ultima_avisada or ''):
            avisados[self.api_url] = {'id': max(ultimo, id_avisado or 0),
                                      'ultima': max(ultima, ultima_avisada or '') or None}
            self.config.datos['errores_avisados'] = avisados
            self._guardar_config()
        return nuevo or volvio

    def _avisar_errores(self, resumen):
        """El aviso de un error nuevo: la notificación de Windows (al hacerle clic se abre la página Errores) y, adentro,
        el mensajito de abajo y el parpadeo en la barra de tareas, como con una venta nueva."""
        n, equipos = resumen['sin_ver'], max(1, resumen['equipos'])
        texto = f"{plural(n, 'error nuevo', 'errores nuevos')} de {plural(equipos, 'equipo', 'equipos')}"
        self._avisar(f'{texto}: míralos en Errores.' if n != 1 else f'{texto}: míralo en Errores.', 'error')
        QApplication.alert(self)
        self._mostrar_notificacion('Error de un cliente', f"{texto}. Haz clic para {'verlo' if n == 1 else 'verlos'}.")

    def _mostrar_notificacion(self, titulo, texto):
        """La notificación de Windows, con el ícono de la app en la bandeja. Si el sistema no tiene bandeja (o en las
        capturas), nada: queda el aviso de adentro. Devuelve True si salió."""
        if self.captura or not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        if self._bandeja is None:
            self._bandeja = QSystemTrayIcon(icono_app(), self)
            self._bandeja.setToolTip(APP)
            self._bandeja.messageClicked.connect(self._abrir_errores)
            self._bandeja.activated.connect(lambda _motivo: self._abrir_errores())
        self._bandeja.show()
        self._bandeja.showMessage(titulo, texto, icono_app(), 10000)
        return True

    def _abrir_errores(self):
        """Al hacer clic en la notificación: la ventana al frente, en la página Errores."""
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        self.ir_a('errores')

    def _marcar_errores(self, ids, visto=True, todos=False):
        """«Marcar como visto» o «como nuevo» (ids) y «Marcar todo como visto» (todos)."""
        if not self.cliente:
            return
        if self._clave_mala:
            self._mensaje('Primero cambia la clave',
                          'El servidor rechazó la clave de administrador. Cámbiala en Configuración → Cambiar clave.')
            return
        cliente, generacion = self.cliente, self._generacion
        nombre = 'todo_visto' if todos else 'error_visto'
        self._acciones += 1
        self.panel_error.set_ocupado(True)
        self.btn_todo_visto.setEnabled(False)
        self.statusBar().showMessage('Enviando al servidor…')
        self.trabajos.iniciar(lambda: cliente.error_visto(ids, todos, visto),
                              lambda r: self._errores_marcados(ids, visto, todos, generacion, r),
                              lambda e: self._errores_no_marcados(nombre, e, generacion))

    def _todo_visto(self):
        n = (self.errores_resumen or {}).get('sin_ver') or sum(1 for e in self.modelo_err.filas if not e['visto'])
        if not n:
            self._avisar('No hay errores sin ver.', 'info')
            return
        pregunta = ('¿Marcar el error sin ver como visto?' if n == 1
                    else f'¿Marcar los {n:,} errores sin ver como vistos?')
        if self._confirmar(pregunta, 'Dejan de salir en «Sin ver» y en el contador de la barra. Si alguno vuelve a pasar, '
                                     'aparece otra vez como nuevo.', 'Marcar como vistos' if n > 1 else 'Marcar como visto',
                           False, 'check'):
            self._marcar_errores([], True, todos=True)

    def _todo_visto_cliente(self):
        """«Marcar todo lo de este cliente como visto» (vista «Por usuario»)."""
        errores = self._errores_de_cliente(self.cliente_err) if self.cliente_err is not None else []
        ids = [e['id'] for e in errores if not e['visto']]
        if not ids:
            self._avisar('Este cliente no tiene errores sin ver.', 'info')
            return
        quien = errores[0]['cliente'] or errores[0]['correo'] or 'este cliente'
        pregunta = (f'¿Marcar el error sin ver de {quien} como visto?' if len(ids) == 1
                    else f'¿Marcar los {len(ids):,} errores sin ver de {quien} como vistos?')
        if self._confirmar(pregunta, 'Dejan de salir en «Sin ver» y en el contador de la barra. Si alguno vuelve a pasar, '
                                     'aparece otra vez como nuevo.', 'Marcar como vistos' if len(ids) > 1
                           else 'Marcar como visto', False, 'check'):
            self._marcar_errores(ids, True)

    def _errores_marcados(self, ids, visto, todos, generacion, r):
        self._acciones = max(0, self._acciones - 1)
        self.panel_error.set_ocupado(False)
        self.statusBar().clearMessage()
        if generacion != self._generacion:
            return   # (de otra clave u otra API)
        cambiar = set(ids)
        for n, fila in enumerate(self.modelo_err.filas):
            if (todos and visto and not fila['visto']) or fila['id'] in cambiar:
                self.modelo_err.cambiar(n, {'visto': visto})
        if todos:   # todo visto: el panel se vacía y las listas dicen «Todo visto» (sin dejar ninguno a la vista)
            for tabla in (self.tabla_err, self.tabla_cli):
                tabla.clearSelection()
                tabla.selectionModel().setCurrentIndex(QModelIndex(), QItemSelectionModel.SelectionFlag.Clear)
            self.cliente_err = None
            self._elegir_error(None)
        elif self.error_elegido in cambiar:
            self.panel_error.poner_cambios({'visto': visto})
        self._poner_resumen_errores(r['resumen'], propio=True)
        self._filtrar_locales()
        self._agrupar_errores()
        if todos:
            self._avisar('Todo visto.' if r['cambiados'] else 'No había errores sin ver.')
        elif len(ids) > 1:
            self._avisar(f"{plural(len(ids), 'error marcado', 'errores marcados')} como {'vistos' if visto else 'nuevos'}.")
        else:
            self._avisar('Marcado como visto.' if visto else 'Marcado como nuevo.')
        self._cuando.pop('errores', None)   # (la próxima vez que se abra la página, se vuelven a pedir)
        self.accion_terminada.emit('todo_visto' if todos else 'error_visto', True)

    def _errores_no_marcados(self, nombre, error, generacion):
        self.panel_error.set_ocupado(False)
        self._poner_resumen_errores(self.errores_resumen, propio=True)   # (vuelve a encender «Marcar todo como visto»)
        self._accion_fallo(nombre, error, generacion)

    def _filtrar_locales(self):
        """Versiones y avisos se filtran y se buscan aquí (ya están todos cargados): no sale ninguna petición."""
        self._timer_filtro.stop()
        estado, texto = self.filtro_ver.valor, _plano(self.buscar_ver.text().strip())

        def cliente_ver(c):   # (los filtros de estado, solo con la licencia activa: como los cuenta la tarjeta)
            if estado != 'todos' and (c['licencia_estado'] != 'activa' or self.modelo_ver.estado(c) != estado):
                return False
            return not texto or any(texto in _plano(x) for x in (c['cliente'], c['correo'], c['clave'])) or any(
                texto in _plano(x) for e in c['filas'] for x in (e['nombre_equipo'], e['version'], texto_so(e['so'])))

        self.proxy_ver.poner_filtro(cliente_ver if estado != 'todos' or texto else None)
        resultado, texto_av = self.filtro_av.valor, _plano(self.buscar_av.text().strip())

        def aviso(a):
            if resultado == 'ok' and not a['ok'] or resultado == 'no' and a['ok']:
                return False
            return not texto_av or any(texto_av in _plano(x) for x in (a['cliente'], a['correo'], a['version']))

        self.proxy_av.poner_filtro(aviso if resultado or texto_av else None)
        filtro_cup, texto_cup = self.filtro_cup.valor, _plano(self.buscar_cup.text().strip())

        def cupon(c):   # 2.8: «Activos» o «Sin efecto» (pausados, vencidos o agotados) y el código o la nota
            if filtro_cup == 'activo' and c['estado'] != 'activo' or filtro_cup == 'inactivo' and c['estado'] == 'activo':
                return False
            return not texto_cup or any(texto_cup in _plano(x) for x in (c['codigo'], c['nota']))

        self.proxy_cup.poner_filtro(cupon if filtro_cup or texto_cup else None)
        if self.modelo_cup.rowCount():
            self.tabla_cup.mensaje_vacio = (f'No se encontraron cupones para «{self.buscar_cup.text().strip()}».' if texto_cup
                                            else 'No hay cupones con este filtro.')
        filtro_err, texto_err = self.filtro_err.valor, _plano(self.buscar_err.text().strip())

        def error(e):
            # (el error que se está viendo no se va de «Sin ver» al marcarlo como visto: así se puede deshacer)
            if filtro_err == 'sin_ver' and e['visto'] and e['id'] != self.error_elegido:
                return False
            return not texto_err or any(texto_err in _plano(x) for x in (
                e['cliente'], e['correo'], e['clave'], e['nombre_equipo'], e['version'], texto_so(e['so']), e['titulo'],
                e['mensaje'], e['origen']))

        def cliente(c):   # «Por usuario»: los clientes con algún error que pasa el filtro (y el elegido, que no se va)
            return c['licencia_id'] == self.cliente_err or any(error(e) for e in c['filas'])

        filtra = filtro_err != 'todos' or texto_err
        self._filtro_error = error if filtra else None
        self.proxy_err.poner_filtro(error if filtra else None)
        self.proxy_cli.poner_filtro(cliente if filtra else None)
        if self.modelo_err.rowCount():
            self._mensaje_errores(f'No se encontraron errores para «{self.buscar_err.text().strip()}».' if texto_err
                                  else 'Todo visto: no hay errores nuevos.')
        self._poner_errores_cliente()
        ultima = texto_version(self.version_ultima) or 'última versión'
        vacio_ver = {'desactualizado': f'Nadie va atrasado: todos los que mandan su versión tienen la {ultima}.',
                     'al_dia': f'Nadie tiene la {ultima} todavía. Avísales con el botón de arriba.',
                     'sin_datos': 'De todos tus clientes se sabe qué versión usan.'}
        if self.modelo_ver.rowCount():
            self.tabla_ver.mensaje_vacio = (f'No se encontraron clientes para «{self.buscar_ver.text().strip()}».' if texto
                                            else vacio_ver.get(estado, 'Todavía ningún cliente activó CineCaptions.'))
        if self.modelo_av.rowCount():
            self.tabla_av.mensaje_vacio = (f'No se encontraron avisos para «{self.buscar_av.text().strip()}».' if texto_av
                                           else 'No hay avisos con este filtro.')
        self._poner_pies()

    def _filtrar_fechas(self):
        dias = self.fechas_v.valor
        if not dias:
            self.proxy_v.poner_filtro(None)
        else:
            desde = Reloj.ahora().date() - dt.timedelta(days=dias - 1)

            def reciente(f):
                fecha = leer_fecha(f['pagado'] or f['creado'])
                return bool(fecha) and fecha.date() >= desde

            self.proxy_v.poner_filtro(reciente)
        self._poner_pies()

    def _cargar_detalle(self):
        self._timer_detalle.stop()
        if not self.seleccion or not self.cliente:
            return
        if self._clave_mala:
            self.panel.mostrar_error('La clave de administrador no es correcta. Cámbiala en Configuración → Cambiar clave.')
            self.detalle_listo.emit()
            return
        origen, ident = self.seleccion
        if origen == 'venta':
            if not self.modelo_v.buscar('id', ident) and ident != self._suelta:
                return
            argumentos = {'pedido_id': ident}
        elif origen == 'canje':
            filas = self.modelo_c.buscar('id', ident)
            if not filas:
                return
            fila = self.modelo_c.fila(filas[0])
            if not fila['licencia_id']:   # canje sin CC-: no hay nada más que pedir
                canje = {k: fila.get(k) for k in ('id', 'correo', 'nombre', 'fecha_venta', 'bloqueo', 'creado', 'ultimo')}
                self.panel.mostrar_detalle({'licencia': None, 'pedido': None, 'canje': canje, 'equipos': []})
                self.detalle_listo.emit()
                return
            argumentos = {'licencia_id': fila['licencia_id']}
        else:
            argumentos = {'licencia_id': ident}
        self._num['detalle'] += 1
        numero, seleccion, cliente = self._num['detalle'], self.seleccion, self.cliente
        self.trabajos.iniciar(lambda: cliente.detalle(**argumentos),
                              lambda d: self._detalle_listo(numero, seleccion, d),
                              lambda e: self._detalle_fallo(numero, seleccion, e), clave='detalle')

    def _detalle_listo(self, numero, seleccion, detalle):
        if numero != self._num['detalle'] or seleccion != self.seleccion:
            return   # llegó tarde: ya eligieron otra fila
        self.panel.ultima = self.version_ultima or self.panel.ultima
        self.panel.mostrar_detalle(detalle)
        self._parchear(detalle)
        lic = detalle['licencia']
        if lic and self.servidor_nuevo is not False:
            self._cargar_historial()
            if self.panel.necesita_aviso():
                self._cargar_avisos_licencia()
        self.detalle_listo.emit()

    def _detalle_fallo(self, numero, seleccion, error):
        if numero != self._num['detalle'] or seleccion != self.seleccion or isinstance(error, Cancelada):
            return
        if isinstance(error, ApiError) and error.codigo == 401:
            self._clave_rechazada(error)
        self.panel.mostrar_error(mensaje_de(error))
        self.detalle_listo.emit()

    def _cargar_historial(self):
        lic = (self.panel.detalle or {}).get('licencia')
        if not lic or not self.cliente:
            return
        self._num['historial'] += 1
        numero, seleccion, cliente, lid = self._num['historial'], self.seleccion, self.cliente, lic['id']

        def listo(eventos):
            if numero == self._num['historial'] and seleccion == self.seleccion:
                self.panel.mostrar_historial(eventos)

        def fallo(error):
            if numero == self._num['historial'] and seleccion == self.seleccion and not isinstance(error, Cancelada):
                self.panel.historial_error(self._texto_fallo(error))

        self.trabajos.iniciar(lambda: cliente.historial(licencia_id=lid), listo, fallo, clave='historial')

    def _cargar_avisos_licencia(self):
        lic = (self.panel.detalle or {}).get('licencia')
        if not lic or not self.cliente:
            return
        self._num['avisos_licencia'] += 1
        numero, seleccion, cliente, lid = self._num['avisos_licencia'], self.seleccion, self.cliente, lic['id']

        def listo(avisos):
            if numero == self._num['avisos_licencia'] and seleccion == self.seleccion:
                self.panel.poner_avisos(avisos)

        self.trabajos.iniciar(lambda: cliente.avisos(licencia_id=lid, limite=20), listo, lambda _e: None,
                              clave='avisos_licencia')

    def _parchear(self, detalle):
        """Lleva a las tablas lo último que dijo el servidor de esta licencia (sin recargar todo)."""
        lic, ped, can = detalle['licencia'], detalle['pedido'], detalle['canje']
        if lic:
            equipos = detalle['equipos']
            cambios = {'licencia_estado': lic['estado'], 'limite': lic['limite'], 'equipos': len(equipos),
                       'clave': lic['clave']}
            if self.servidor_nuevo:
                reciente = max(equipos, key=lambda e: e['ultima'] or '') if equipos else None
                ultima = detalle.get('version_ultima') or self.version_ultima
                cambios.update(version=reciente and reciente['version'], ultima_vez=reciente and reciente['ultima'],
                               equipos_desactualizados=sum(
                                   1 for e in equipos
                                   if (e['estado_version'] or estado_de_version(e['version'], ultima)) == 'desactualizado'))
            for n in self.modelo_v.buscar('licencia_id', lic['id']):
                self.modelo_v.cambiar(n, cambios)
            for n in self.modelo_c.buscar('licencia_id', lic['id']):
                self.modelo_c.cambiar(n, dict(cambios, **({'bloqueo': can['bloqueo']} if can else {})))
        if ped:
            for n in self.modelo_v.buscar('id', ped['id']):
                self.modelo_v.cambiar(n, {'estado': ped['estado'], 'correo_enviado': ped['correo_enviado'],
                                          'pagado': ped['pagado']})

    # --- Resumen y estado
    def _poner_resumen(self, r, propio=False):
        """propio: el resumen que devolvió un cambio hecho desde aquí (restaurar una venta pagada no es «¡Nueva venta!»)."""
        desfase = Reloj.desfase
        Reloj.ajustar(r['hora_servidor'])
        if Reloj.desfase != desfase:   # ya se sabe la zona del servidor: las fechas de las tablas pasan a la hora local
            for tabla in (self.tabla_v, self.tabla_c, self.tabla_ver, self.tabla_av, self.tabla_err, self.tabla_cli):
                tabla.viewport().update()
            if self.fechas_v.valor:
                self._filtrar_fechas()
        anterior, self.resumen = self.resumen, r
        v, l, monedas, versiones = r['ventas'], r['licencias'], r['monedas'], r.get('versiones')
        moneda = monedas[0] if len(monedas) == 1 else 'USD'
        nota = f"Suma de varias monedas: {', '.join(monedas)}" if len(monedas) > 1 else ''
        # (un cero sale más tenue: lo que sí tiene números resalta, también con pocas ventas)
        self.t_hoy.poner(dinero_html(v['ingresos_hoy'], moneda), plural(v['ventas_hoy'], 'venta', 'ventas'), ayuda=nota,
                         apagada=not v['ingresos_hoy'])
        self.t_mes.poner(dinero_html(v['ingresos_mes'], moneda), plural(v['ventas_mes'], 'venta', 'ventas'), ayuda=nota,
                         apagada=not v['ingresos_mes'])
        self.t_total.poner(dinero_html(v['ingresos'], moneda), plural(v['pagadas'], 'venta pagada', 'ventas pagadas'),
                           ayuda=(nota + '\n' if nota else '') + plural(v['pendientes'], 'pago sin completar', 'pagos sin completar'),
                           apagada=not v['ingresos'])
        self.t_reemb.poner(dinero_html(v['monto_reembolsado'], moneda), plural(v['reembolsadas'], 'reembolso', 'reembolsos'),
                           AVISO if v['reembolsadas'] else None, nota, apagada=not v['monto_reembolsado'])
        self.t_lic.poner(numero_html(l['activas'], 'activas' if l['activas'] != 1 else 'activa'),
                         plural(l['bloqueadas'], 'bloqueada', 'bloqueadas') if l['bloqueadas'] else 'ninguna bloqueada',
                         PELIGRO if l['bloqueadas'] else None, apagada=not l['activas'])
        if versiones is not None:
            self.t_equipos.poner_titulo('Equipos activos')
            self.t_equipos.poner(numero_html(versiones['activos_30d'], 'en 30 días'),
                                 f"de {plural(r['equipos'], 'equipo activado', 'equipos activados')}",
                                 ayuda='Equipos de licencias activas que abrieron CineCaptions en los últimos 30 días',
                                 apagada=not versiones['activos_30d'])
        else:
            self.t_equipos.poner_titulo('Equipos activados')
            self.t_equipos.poner(numero_html(r['equipos']), 'computadoras con la licencia activada', apagada=not r['equipos'])
        self.version_ultima = (versiones or {}).get('ultima') or self.version_ultima
        for modelo in (self.modelo_v, self.modelo_c, self.modelo_ver, self.modelo_err):
            modelo.poner_ultima(self.version_ultima)
        self.panel.ultima = self.version_ultima or self.panel.ultima
        self.barra.botones['canjes'].poner_contador(r['canjes'])   # (sin canjes, sin contador: BotonIsla no dibuja el 0)
        if versiones is not None:
            self.barra.botones['versiones'].poner_contador(versiones['desactualizados'] or None,
                                                           AVISO if versiones['desactualizados'] else None)
        self._poner_bloques_versiones()
        # Las ventas eliminadas: el contador del filtro «Eliminadas» y si se puede eliminar (None: el admin.php de antes)
        eliminadas = v.get('eliminadas') if self.servidor_nuevo is not False else None
        self._poner_filtro_eliminadas(eliminadas)
        self.panel.set_eliminar(eliminadas is not None)
        if anterior and not propio and v['pagadas'] > anterior['ventas']['pagadas']:
            nuevas = v['pagadas'] - anterior['ventas']['pagadas']
            self._avisar('¡Nueva venta!' if nuevas == 1 else f'¡{nuevas} ventas nuevas!')
            QApplication.alert(self)
        self._poner_estado()

    def _poner_filtro_eliminadas(self, n, recargar=True):
        """«Eliminadas (3)» en el filtro de Ventas. n None: el servidor todavía no sabe eliminar ventas y la opción no se
        puede elegir (el admin.php de antes respondería la lista normal, como si fueran las eliminadas). recargar=False:
        si estaba elegida, vuelve a la lista normal sin pedirla (al cambiar de API la pide «Actualizar»)."""
        i = self.filtro.findData('eliminadas')
        if i < 0:
            return
        self.filtro.setItemText(i, f'Eliminadas ({n:,})' if n else 'Eliminadas')
        item = self.filtro.model().item(i) if hasattr(self.filtro.model(), 'item') else None
        if item is not None:
            item.setEnabled(n is not None)
            item.setToolTip('' if n is not None else 'Necesita el pagos/admin.php nuevo')
        if n is None and self.filtro.currentData() == 'eliminadas':
            self.filtro.blockSignals(not recargar)
            self.filtro.setCurrentIndex(self.filtro.findData(''))
            self.filtro.blockSignals(False)

    def _poner_pies(self):
        n, visibles = self.modelo_v.rowCount(), self.proxy_v.rowCount()
        eliminadas = bool(self._consulta_v and self._consulta_v[0] == 'eliminadas')
        if eliminadas and self.resumen:   # (la isla no cuenta las eliminadas: sigue con las de la lista normal)
            normal = self.resumen['ventas']['pagadas'] + self.resumen['ventas']['reembolsadas']
            self.barra.botones['ventas'].poner_contador(normal or None)
        elif not eliminadas:
            self.barra.botones['ventas'].poner_contador(n if n else None)
        if eliminadas and visibles == n:
            texto = (plural(n, 'venta eliminada', 'ventas eliminadas') + (' · no cuenta' if n == 1 else ' · no cuentan')
                     + ' en los totales · clic derecho para restaurar') if n else ''
        elif visibles == n:
            texto = plural(n, 'venta en la lista', 'ventas en la lista')
        else:
            periodo = {1: 'de hoy', 7: 'de los últimos 7 días', 30: 'de los últimos 30 días'}.get(self.fechas_v.valor, '')
            texto = f"{visibles:,} de {plural(n, 'venta', 'ventas')} · {periodo}"
            if not visibles:
                self.tabla_v.mensaje_vacio = f'No hay ventas {periodo} con este filtro.'
        if self._hay_mas_v:
            texto += ' · hay más, usa «Cargar más»'
        self.lbl_pie_v.setText(texto)
        self.btn_mas.setVisible(self._hay_mas_v)
        self.lbl_pie_c.setText(plural(self.modelo_c.rowCount(), 'canje en la lista', 'canjes en la lista'))
        n, visibles = self.modelo_ver.rowCount(), self.proxy_ver.rowCount()
        equipos = sum(c.get('equipos') or 0 for c in self.modelo_ver.filas)
        bloqueados = sum(1 for c in self.modelo_ver.filas if c.get('licencia_estado') != 'activa')
        self.lbl_pie_ver.setText(((plural(n, 'cliente', 'clientes') if visibles == n
                                   else f"{visibles:,} de {plural(n, 'cliente', 'clientes')}")
                                  + f" con {plural(equipos, 'equipo activado', 'equipos activados')}"
                                  + (f" · {plural(bloqueados, 'con la licencia bloqueada (no cuenta', 'con la licencia bloqueada (no cuentan')} arriba)"
                                     if bloqueados else '')) if n else '')
        n, visibles = self.modelo_av.rowCount(), self.proxy_av.rowCount()
        enviados = sum(1 for a in self.modelo_av.filas if a['ok'])
        self.lbl_pie_av.setText((plural(n, 'aviso', 'avisos') if visibles == n else f"{visibles:,} de {plural(n, 'aviso', 'avisos')}")
                                + (f" · {plural(enviados, 'enviado', 'enviados')}" if n else ''))
        n, visibles = self.modelo_cup.rowCount(), self.proxy_cup.rowCount()   # 2.8: los cupones
        cupones = self.modelo_cup.filas
        activos = sum(1 for c in cupones if c['estado'] == 'activo')
        usos, ingresos = sum(c['usos'] for c in cupones), sum(c['ingresos'] for c in cupones)
        self.lbl_pie_cup.setText(((plural(n, 'cupón', 'cupones') if visibles == n else f"{visibles:,} de {plural(n, 'cupón', 'cupones')}")
                                  + f" · {plural(activos, 'activo', 'activos')}"
                                  + f" · {plural(usos, 'venta', 'ventas')} con cupón"
                                  + (f" · {dinero(ingresos, self.modelo_cup.moneda)}" if ingresos else '')
                                  + ' · doble clic para editar, clic derecho para copiar el enlace') if n else '')
        sin_ver = sum(1 for e in self.modelo_err.filas if not e['visto'])
        if self.vista_errores.valor == 'usuario':
            n, visibles, uno, varios = self.modelo_cli.rowCount(), self.proxy_cli.rowCount(), 'cliente', 'clientes'
        else:
            n, visibles, uno, varios = self.modelo_err.rowCount(), self.proxy_err.rowCount(), 'error', 'errores'
        self.lbl_pie_err.setText(((plural(n, uno, varios) if visibles == n else f'{visibles:,} de {plural(n, uno, varios)}')
                                  + f' · {plural(sin_ver, "error sin ver", "errores sin ver")}') if n else '')
        self.btn_resumen_err.setEnabled(bool(self._errores_que_se_ven()))
        self._contar_errores()

    def _poner_estado(self):
        """La barra de abajo: a la izquierda cuándo se actualizó (con un ícono) y que se actualiza sola. 2.3: sin la zona
        del servidor (queda en el tooltip); la API solo si NO es la del sitio (probando con otro servidor, que se note).
        «Solo lectura» va en una pastilla aparte."""
        if self.ultima:
            self.ic_estado.setPixmap(pintar_icono('ok', TEXTO_TENUE, 14))
            self.lbl_actualizado.setText(f'Actualizado a las {self.ultima:%H:%M}'
                                         + ('' if self.captura else ' · se actualiza sola cada 2 min (F5 para ya)'))
        else:
            self.ic_estado.setPixmap(pintar_icono('reloj', TEXTO_TENUE, 14))
            self.lbl_actualizado.setText('Todavía sin datos')
        zona = Reloj.zona()
        self.lbl_estado.setText(f'Servidor de prueba: {urllib.parse.urlsplit(self.api_url).netloc}'
                                if self.api_url != API_POR_DEFECTO else '')
        hora = fecha_mysql((self.resumen or {}).get('hora_servidor'))
        self.lbl_estado.setToolTip(f'Hora del servidor (MySQL): {hora.day} {MESES[hora.month - 1]} {hora.year}, '
                                   f'{hora:%H:%M} ({zona}). Las fechas se muestran en la hora de esta PC.'
                                   if hora and zona else '')
        self.lbl_solo_lectura.setVisible(self.solo_lectura)

    def _ocupado(self, activo):
        self.indicador.activar(activo)
        self.lbl_cargando.setVisible(activo)

    def _actualizar_solo(self):
        if (self._clave_mala or self._actualizando or time.monotonic() < self._pausa_hasta
                or QApplication.activeModalWidget() is not None):
            return
        self.actualizar_todo(auto=True)

    def _avisar(self, texto, tipo='ok'):
        self.aviso.mostrar(texto, tipo)

    def _copiar(self, texto, aviso):
        if texto:
            QGuiApplication.clipboard().setText(texto)
            self._avisar(aviso)

    def _errores_que_se_ven(self):
        """Los errores que pasan el filtro («Sin ver»/«Todos») y la búsqueda de ahora: lo mismo que se ve en las dos vistas."""
        return [e for e in self.modelo_err.filas if self._filtro_error is None or self._filtro_error(e)]

    def _copiar_resumen_errores(self):
        """2.6: «Copiar resumen»: los errores que se ven, agrupados por fallo, en un texto para pegar en un chat. La lista no trae
        el informe técnico: se pide el del último error de cada fallo (uno por fallo, RESUMEN_MAX_DETALLES como mucho) en una
        tarea propia de la cola (no corta lo que carga el panel) y luego se copia."""
        filas = self._errores_que_se_ven()
        if not filas or not self.cliente:
            return
        ids = [e['id'] for e in representantes_de_errores(filas)][:RESUMEN_MAX_DETALLES]
        cliente, version = self.cliente, texto_version(self.version_ultima)
        filtro, busqueda = self.filtro_err.valor, self.buscar_err.text().strip()
        self.btn_resumen_err.setEnabled(False)
        self.btn_resumen_err.setText('Preparando…')

        def trabajo():
            detalles = {}
            for ident in ids:
                try:
                    detalles[ident] = cliente.error_detalle(ident).get('detalle')
                except Exception:
                    pass        # sin su informe: ese fallo va igual, sin «Detalle técnico»
            return detalles

        def terminar():
            self.btn_resumen_err.setText('Copiar resumen')
            self.btn_resumen_err.setEnabled(bool(self._errores_que_se_ven()))

        def listo(detalles):
            terminar()
            con = [dict(e, detalle=detalles.get(e['id']) or e.get('detalle')) for e in filas]
            clientes = len({e.get('licencia_id') for e in filas})
            self._copiar(resumen_de_errores(con, version, filtro, busqueda),
                         f"Resumen copiado: {plural(len(filas), 'error', 'errores')} de {plural(clientes, 'cliente', 'clientes')}. "
                         'Pégalo en el chat.')

        def fallo(error):
            terminar()
            self._avisar(f'No pude preparar el resumen: {self._texto_fallo(error)}', 'error')

        self._pedir('resumen_err', trabajo, listo, fallo)

    def _copiar_de_tabla(self, tabla, campo):
        if tabla is self.tabla_cup:   # (2.8: en Cupones, Ctrl+C copia el código)
            campo = 'codigo'
        fila = self._fila_actual(tabla)
        if fila and fila.get(campo):
            self._copiar(fila[campo], {'clave': 'Clave copiada', 'correo': 'Correo copiado',
                                       'codigo': 'Código copiado'}.get(campo, 'Copiado'))

    def _menu_tabla(self, tabla, posicion):
        indice = tabla.indexAt(posicion)
        if not indice.isValid():
            return
        tabla.selectRow(indice.row())
        fila = self._fila_de(tabla, indice)
        if not fila:
            return
        menu = self._armar_menu_tabla(tabla, fila)
        if not menu.isEmpty():
            menu.exec(tabla.viewport().mapToGlobal(posicion))

    def _armar_menu_tabla(self, tabla, fila):
        """El menú del clic derecho de una fila: copiar la clave, el correo o el nombre y, según la tabla, «Eliminar venta»
        (o «Restaurar venta») en Ventas y «Avisar que actualice» en Versiones. (Aparte de _menu_tabla, para probarlo.)"""
        menu = QMenu(self)
        if tabla is self.tabla_cup:   # 2.8: un cupón
            return self._menu_cupon(menu, fila)
        for campo, nombre_icono, texto, aviso in (('clave', 'copiar', 'Copiar clave', 'Clave copiada'),
                                                  ('correo', 'correo', 'Copiar correo', 'Correo copiado'),
                                                  ('nombre', 'usuario', 'Copiar nombre', 'Nombre copiado'),
                                                  ('cliente', 'usuario', 'Copiar nombre', 'Nombre copiado'),
                                                  ('equipo', 'equipo', 'Copiar ID del equipo', 'ID copiado')):
            if fila.get(campo) and not (campo == 'equipo' and tabla not in (self.tabla_ver, self.tabla_err)):
                a = menu.addAction(icono(nombre_icono), texto)
                a.triggered.connect(lambda _c=False, t=fila[campo], m=aviso: self._copiar(t, m))
        if tabla is self.tabla_v and fila.get('id') is not None:
            eliminada = venta_eliminada(fila)
            if not menu.isEmpty():
                menu.addSeparator()
            a = menu.addAction(icono('restaurar' if eliminada else 'basura', TEXTO_SUAVE if eliminada else PELIGRO),
                               'Restaurar venta…' if eliminada else 'Eliminar venta…')
            if self.panel.con_eliminar is False:
                a.setText(a.text() + '  (falta el servidor nuevo)')
            a.setEnabled(self.panel.con_eliminar is not False and fila['id'] not in self._eliminando)
            a.triggered.connect(lambda _c=False, f=dict(fila), e=not eliminada: self._eliminar_venta(f, e))
        if tabla is self.tabla_ver and fila.get('licencia_id') and fila.get('licencia_estado') == 'activa':
            version = texto_version(self.version_ultima)
            if version:
                if not menu.isEmpty():
                    menu.addSeparator()
                ya = avisado_de(fila, version)
                a = menu.addAction(icono('megafono'), f'Reenviar aviso de la {version}…' if ya
                                   else f'Avisar que actualice a la {version}…')
                a.setEnabled(bool(fila.get('correo')) and fila['licencia_id'] not in self.modelo_ver.enviando)
                a.triggered.connect(lambda _c=False, f=dict(fila): self._avisar_cliente(f))
        return menu

    # --- Acciones del panel (cada una con su confirmación)
    def _confirmar(self, pregunta, explicacion, texto_boton, peligro=True, nombre_icono='aviso'):
        return confirmar(self, pregunta, explicacion, texto_boton, peligro, nombre_icono)

    def _mensaje(self, titulo, texto, tipo='error'):
        mensaje(self, titulo, texto, tipo)

    def _dialogo_cliente(self, nombre, correo):
        """Pide el nombre y el correo nuevos. Devuelve solo lo que cambió (o None si se canceló)."""
        d = DialogoCliente(self, nombre, correo)
        return d.cambios() if d.exec() == QDialog.DialogCode.Accepted else None

    def _accion(self, nombre, datos):
        d = self.panel.detalle
        if not d or not self.cliente:
            return
        if self._clave_mala:
            self._mensaje('Primero cambia la clave',
                          'El servidor rechazó la clave de administrador. Cámbiala en Configuración → Cambiar clave.')
            return
        # La fila elegida se anota antes de la confirmación: mientras está abierta puede llegar una recarga de la tabla
        seleccion, generacion = self.seleccion, self._generacion
        lic, ped, can = d['licencia'], d['pedido'], d['canje']
        persona = lic if lic and lic.get('nombre') else (ped if self.panel.origen == 'venta' and ped else (can or lic or {}))
        quien = persona.get('nombre') or persona.get('correo') or 'este cliente'
        cliente = self.cliente
        exito = None
        if nombre == 'ficha_equipo' and lic:   # (2.4: solo lee; no ocupa el panel ni cuenta como un cambio)
            self._ver_ficha(lic, datos, quien)
            return
        if nombre in ('bloquear', 'reactivar') and lic:
            if nombre == 'bloquear':
                ok = self._confirmar(f'¿Bloquear la licencia de {quien}?',
                                     f"La clave {lic['clave']} dejará de funcionar: CineCaptions se desactiva en sus "
                                     'computadoras cuando vuelve a revisar la licencia.\nPuedes reactivarla cuando quieras.',
                                     'Bloquear licencia', True, 'candado')
            else:
                ojo = '\nOjo: este pedido está marcado como reembolsado.' if ped and ped['estado'] == 'reembolsado' else ''
                if can and can['bloqueo']:
                    ojo = '\nOjo: Gumroad marcó esta compra como «' + BLOQUEOS_CANJE.get(can['bloqueo'], (can['bloqueo'],))[0].lower() + '».'
                ok = self._confirmar(f'¿Reactivar la licencia de {quien}?',
                                     f"La clave {lic['clave']} vuelve a funcionar en sus computadoras.{ojo}",
                                     'Reactivar licencia', bool(ojo), 'abierto')
            if not ok:
                return
            estado = 'bloqueada' if nombre == 'bloquear' else 'activa'
            tarea = lambda: cliente.licencia_estado(lic['id'], estado)
            exito = 'Licencia bloqueada.' if nombre == 'bloquear' else 'Licencia reactivada.'
        elif nombre == 'liberar_equipo' and lic:
            equipo = datos
            if not self._confirmar(f"¿Liberar el equipo «{nombre_pc(equipo)}»?",
                                   f"Deja de ocupar uno de los {lic['limite']} lugares de la licencia {lic['clave']}, "
                                   f'así {quien} puede activar CineCaptions en otra computadora.',
                                   'Liberar equipo', True, 'equipo'):
                return
            tarea = lambda: cliente.liberar_equipo(lic['id'], equipo['equipo'])
        elif nombre == 'liberar_todos' and lic:
            n = len(d['equipos'])
            if not self._confirmar(f'¿Liberar los {n} equipos de esta licencia?',
                                   f"Ninguna computadora queda ocupando lugar en {lic['clave']}: se podrá activar de nuevo "
                                   f"en hasta {plural(lic['limite'], 'computadora', 'computadoras')}.",
                                   'Liberar todos', True, 'equipo'):
                return
            tarea = lambda: cliente.liberar_equipo(lic['id'], '')
        elif nombre == 'reenviar' and lic:
            correo = correo_reenvio(d)
            if not correo:
                return
            if not self._confirmar(f'¿Reenviar la clave a {correo}?',
                                   f"Le llega otra vez el correo con la clave {lic['clave']} y las instrucciones para "
                                   'instalar CineCaptions.', 'Reenviar correo', False, 'correo'):
                return
            tarea = lambda: cliente.reenviar_correo(lic['id'])
        elif nombre == 'recurrente' and ped:
            tarea = lambda: cliente.estado_recurrente(ped['id'])
        elif nombre == 'reembolsar' and ped:
            licencia = f" y la licencia {lic['clave']} queda bloqueada" if lic else ''
            if not self._confirmar(f"¿Marcar el pedido #{ped['id']} como reembolsado?",
                                   f"Venta de {quien} por {dinero(ped['monto'], ped['moneda'])}.\n"
                                   'Esto NO devuelve el dinero: el reembolso se hace en el panel de Recurrente.\n'
                                   f'La venta deja de contar en los ingresos{licencia}.',
                                   'Marcar como reembolsado', True, 'reembolso'):
                return
            tarea = lambda: cliente.marcar_reembolsado(ped['id'])
            exito = 'Pedido marcado como reembolsado.' + (' Licencia bloqueada.' if lic else '')
        elif nombre in ('eliminar', 'restaurar') and ped and self.panel.origen == 'venta':
            self._eliminar_venta(self._venta_del_panel(), nombre == 'eliminar')
            return
        elif nombre == 'limite' and lic:
            nuevo, n = int(datos), len(d['equipos'])
            if not LIMITE_EQUIPOS[0] <= nuevo <= LIMITE_EQUIPOS[1] or nuevo == lic['limite']:
                return
            if not self._confirmar(f"¿Cambiar el límite a {plural(nuevo, 'equipo', 'equipos')}?",
                                   f"La licencia {lic['clave']} podrá estar activada en hasta "
                                   f"{plural(nuevo, 'computadora', 'computadoras')} a la vez (ahora: {lic['limite']})."
                                   + (f"\nAhora tiene {plural(n, 'equipo activado', 'equipos activados')}." if n else ''),
                                   'Cambiar límite', nuevo < lic['limite'], 'equipo'):
                return
            tarea = lambda: cliente.limite(lic['id'], nuevo)
            exito = f"Límite cambiado a {plural(nuevo, 'equipo', 'equipos')}."
        elif nombre == 'editar' and lic:
            otra = ped or can or {}
            cambios = self._dialogo_cliente(lic.get('nombre') or otra.get('nombre') or '',
                                            lic.get('correo') or otra.get('correo') or '')
            if not cambios:
                return
            tarea = lambda: cliente.editar_cliente(lic['id'], **cambios)
            exito = 'Datos del cliente guardados.'
        elif nombre == 'nota' and lic:
            texto = str(datos or '')[:MAX_TEXTO]
            tarea = lambda: cliente.nota(lic['id'], texto)
            exito = 'Nota guardada.' if texto else 'Nota borrada.'
        elif nombre == 'avisar' and lic:
            version = texto_version(self.panel.ultima or self.version_ultima)
            if not version:
                return
            ya = self.panel.aviso_de(version)
            forzar = bool((datos or {}).get('forzar')) or ya is not None
            correo = correo_aviso(d) or 'su correo'
            if (datos or {}).get('confirmado'):   # (ya dijo que sí al «Ya le avisaste… ¿otra vez?»)
                ok = True
            elif forzar:
                cuando = f" {fecha_frase(ya['enviado'])}" if ya else ''
                ok = self._confirmar(f'¿Reenviar el aviso de la {version} a {quien}?',
                                     f'Ya le avisaste de esta versión{cuando}. Le llega otra vez a {correo}, con lo nuevo '
                                     'y el enlace para descargarla.', 'Reenviar aviso', False, 'megafono')
            else:
                ok = self._confirmar(f'¿Avisar a {quien} que actualice a la {version}?',
                                     f'Le llega un correo a {correo} con lo nuevo de la {version} y el enlace para '
                                     'descargarla.', 'Mandar aviso', False, 'megafono')
            if not ok:
                return
            # Lo nuevo del manifiesto solo si es de esta misma versión (si acaba de salir otra y la app todavía no la
            # leyó, el correo no lleva las notas de la anterior: sin mensaje, admin.php pone las de la versión publicada)
            info = self.version_info or {}
            notas = info.get('notas') if partes_version(info.get('version')) == partes_version(version) else None
            tarea = lambda: cliente.avisar_actualizacion(lic['id'], version, notas, forzar)
        else:
            return
        cambia = nombre != 'recurrente'   # consultar Recurrente solo lee
        self._acciones += cambia
        self.panel.set_ocupado(True)
        self.statusBar().showMessage('Enviando al servidor…' if cambia else 'Consultando a Recurrente…')
        self.trabajos.iniciar(tarea, lambda r: self._accion_lista(nombre, r, exito, seleccion, cambia),
                              lambda e: self._accion_fallo(nombre, e, generacion, cambia))

    def _ver_ficha(self, lic, equipo, quien):
        """2.4: «Ficha» de un equipo de la licencia: pide su ficha técnica completa (equipo_ficha) y la abre en DialogoFicha."""
        cliente = self.cliente
        self.statusBar().showMessage('Cargando la ficha del equipo…')

        def listo(ficha_equipo):
            self.statusBar().clearMessage()
            self.abrir_ficha(equipo, ficha_equipo, f"{quien} · {lic['clave']}")

        def fallo(error):
            self.statusBar().clearMessage()
            self._mensaje('No se pudo cargar la ficha', self._texto_fallo(error))

        self._pedir('equipo_ficha', lambda: cliente.equipo_ficha(lic['id'], equipo['equipo']), listo, fallo)

    def abrir_ficha(self, equipo, ficha_equipo, de_quien=''):
        """Muestra la ficha (sin esperar a que se cierre: open, no exec). Si ya había una abierta, la cambia por esta."""
        if self.dialogo_ficha is not None:
            self.dialogo_ficha.close()
        self.dialogo_ficha = DialogoFicha(self, equipo, ficha_equipo, de_quien, self._copiar)
        self.dialogo_ficha.finished.connect(lambda _r, d=self.dialogo_ficha: self._ficha_cerrada(d))
        self.dialogo_ficha.open()
        return self.dialogo_ficha

    def _ficha_cerrada(self, dialogo):
        if self.dialogo_ficha is dialogo:
            self.dialogo_ficha = None
        dialogo.deleteLater()

    def _accion_lista(self, nombre, resultado, exito, seleccion, cambia=True):
        self._acciones = max(0, self._acciones - cambia)
        self.panel.set_ocupado(False)
        self.statusBar().clearMessage()
        if nombre == 'recurrente':
            if seleccion == self.seleccion:
                self.panel.mostrar_recurrente(resultado)
            self._avisar('Consulta a Recurrente lista.', 'info')
            self.accion_terminada.emit(nombre, True)
            return
        if nombre == 'nota':   # solo cambia la nota: no hace falta recargar el panel
            if seleccion == self.seleccion:
                self.panel.nota_guardada(resultado)
                self._cargar_historial()
            self._avisar(exito)
            self.accion_terminada.emit(nombre, True)
            return
        if nombre == 'avisar' and not resultado['enviado']:
            self._aviso_no_enviado(resultado, seleccion)
            self.accion_terminada.emit(nombre, True)
            return
        if nombre in ('liberar_equipo', 'liberar_todos'):
            n = resultado['liberados']
            exito = 'No había equipos para liberar.' if n == 0 else 'Equipo liberado.' if n == 1 else f'Se liberaron {n} equipos.'
        elif nombre == 'reenviar':
            exito = f'Correo enviado a {resultado}.' if resultado else 'Correo enviado.'
        elif nombre == 'avisar':
            exito = f"Aviso enviado a {resultado['correo']}." if resultado['correo'] else 'Aviso enviado.'
        elif nombre == 'editar' and resultado:   # admin.php también cambió sus compras: las filas de ventas lo muestran
            for n in self.modelo_v.buscar('licencia_id', resultado['id']):
                self.modelo_v.cambiar(n, {'nombre': resultado['nombre'], 'correo': resultado['correo']})
        self._avisar(exito)
        self._datos_cambiaron()
        if seleccion == self.seleccion:
            self._cargar_detalle()
        else:
            self._cargar_ventas()
            self._cargar_canjes()
        if nombre != 'avisar':
            self._cargar_resumen()
        self.accion_terminada.emit(nombre, True)

    def _aviso_no_enviado(self, resultado, seleccion):
        """avisar_actualizacion respondió bien pero el correo no salió (por un motivo esperado)."""
        motivo = resultado['motivo']
        if motivo == 'ya_avisado' and seleccion == self.seleccion:
            if self._confirmar('Ya le avisaste de esta versión', '¿Quieres mandarle el aviso otra vez?', 'Reenviar aviso',
                               False, 'megafono'):
                self._accion('avisar', {'forzar': True, 'confirmado': True})
            else:
                self._cargar_avisos_licencia()   # el botón pasa a «Reenviar aviso de la …»
            return
        if motivo == 'limite':
            minutos = max(1, round((resultado['reintentar_en'] or 60) / 60))
            texto = f'El servidor llegó a su tope de 90 correos por hora. Intenta de nuevo en {plural(minutos, "minuto", "minutos")}.'
        else:
            texto = EXPLICA_MOTIVO.get(motivo, 'El servidor no mandó el correo.')
        self._mensaje('No se mandó el aviso', texto, 'info' if motivo in ('baja', 'ya_avisado') else 'error')
        if seleccion == self.seleccion:
            self._cargar_historial()

    def _accion_fallo(self, nombre, error, generacion=None, cambia=True):
        self._acciones = max(0, self._acciones - cambia)
        self.panel.set_ocupado(False)
        self.statusBar().clearMessage()
        if isinstance(error, ApiError) and error.codigo == 401 and generacion in (None, self._generacion):
            self._clave_rechazada(error)   # (un 401 de la clave anterior no marca como mala la clave nueva)
        titulo = {'bloquear': 'No se pudo bloquear la licencia', 'reactivar': 'No se pudo reactivar la licencia',
                  'liberar_equipo': 'No se pudo liberar el equipo', 'liberar_todos': 'No se pudieron liberar los equipos',
                  'reenviar': 'No se pudo reenviar el correo', 'recurrente': 'No se pudo consultar Recurrente',
                  'reembolsar': 'No se pudo marcar como reembolsado', 'limite': 'No se pudo cambiar el límite',
                  'editar': 'No se guardaron los datos del cliente', 'nota': 'No se pudo guardar la nota',
                  'avisar': 'No se pudo mandar el aviso', 'error_visto': 'No se pudo marcar el error',
                  'todo_visto': 'No se pudieron marcar los errores', 'eliminar': 'No se pudo eliminar la venta',
                  'restaurar': 'No se pudo restaurar la venta'}.get(nombre, 'No se pudo completar la acción')
        self._mensaje(titulo, self._texto_fallo(error))
        self.accion_terminada.emit(nombre, False)

    def _datos_cambiaron(self):
        """Después de un cambio, las versiones, los avisos y la gráfica se vuelven a pedir (la próxima vez que se vean)."""
        for nombre in ('versiones', 'avisos', 'estadisticas'):
            self._cuando.pop(nombre, None)
        self._cargar_pagina()

    # --- Eliminar o restaurar una venta (desde el panel o el clic derecho en Ventas)
    def _venta_del_panel(self):
        """La venta del panel como una fila de Ventas, con lo último que dijo el detalle (estado de la licencia, equipos)."""
        d = self.panel.detalle or {}
        ped, lic = d.get('pedido') or {}, d.get('licencia')
        fila = dict(self.panel.fila or {})
        fila.update({campo: ped.get(campo) for campo in ('id', 'estado', 'monto', 'moneda', 'creado', 'pagado', 'eliminada')})
        fila['nombre'] = (lic or {}).get('nombre') or ped.get('nombre') or fila.get('nombre')
        fila['correo'] = (lic or {}).get('correo') or ped.get('correo') or fila.get('correo')
        if lic:
            fila.update(licencia_id=lic['id'], clave=lic['clave'], licencia_estado=lic['estado'],
                        equipos=len(d.get('equipos') or []))
        return fila

    def _textos_eliminar(self, fila, eliminar):
        """(pregunta, explicación, botón, texto de la casilla o None) de la confirmación de eliminar o restaurar."""
        nombre = fila.get('nombre') or fila.get('correo')
        estado = ESTADOS_VENTA.get(fila.get('estado'), (fila.get('estado') or '',))[0].lower()
        monto = dinero(fila['monto'], fila.get('moneda')) if fila.get('monto') is not None else ''
        venta = f"Pedido #{fila['id']}" + (f' · {monto}' if monto else '') + (f' ({estado})' if estado else '') + '.'
        if eliminar:
            casilla = None
            if fila.get('licencia_id') and fila.get('licencia_estado') == 'activa':
                n = fila.get('equipos') or 0
                casilla = ('Bloquear también su licencia ' + (f'(deja de funcionar en sus {n} equipos)' if n > 1 else
                                                             '(deja de funcionar en su equipo)' if n == 1 else
                                                             '(todavía no la activó en ningún equipo)'))
            return (f'¿Eliminar la venta de {nombre}?' if nombre else f"¿Eliminar el pedido #{fila['id']}?",
                    f'{venta}\nSale de la lista y de los totales, pero NO se borra: el pago, la licencia y su historial '
                    'siguen guardados. La puedes restaurar cuando quieras desde el filtro «Eliminadas».',
                    'Eliminar venta', casilla)
        bloqueada = (f"\nSu licencia {fila['clave']} sigue bloqueada: si quieres que vuelva a funcionar, reactívala en "
                     'el panel.') if fila.get('clave') and fila.get('licencia_estado') == 'bloqueada' else ''
        return (f'¿Restaurar la venta de {nombre}?' if nombre else f"¿Restaurar el pedido #{fila['id']}?",
                f'{venta}\nVuelve a la lista y a los totales.{bloqueada}', 'Restaurar venta', None)

    def _preguntar_eliminar(self, pregunta, explicacion, texto_boton, casilla, peligro):
        """La confirmación (con la casilla, desmarcada, si la hay). Devuelve (¿sí?, ¿marcó la casilla?)."""
        caja, si = caja_confirmacion(self, pregunta, explicacion, texto_boton, peligro,
                                     'basura' if peligro else 'restaurar', casilla=casilla)
        caja.exec()
        return caja.clickedButton() is si, bool(caja.casilla is not None and caja.casilla.isChecked())

    def _eliminar_venta(self, fila, eliminar=True):
        """«Eliminar venta» (o «Restaurar venta»): pregunta y la manda UNA vez (otro clic mientras va no manda otra).
        Al terminar se actualizan la lista, las tarjetas, la gráfica y el historial; la venta sigue en el panel (ahí mismo
        se puede deshacer) hasta que se elige otra fila."""
        pid = (fila or {}).get('id')
        if pid is None or not self.cliente or pid in self._eliminando:
            return
        if self._clave_mala:
            self._mensaje('Primero cambia la clave',
                          'El servidor rechazó la clave de administrador. Cámbiala en Configuración → Cambiar clave.')
            return
        if self.panel.con_eliminar is False:
            self._mensaje('Falta el servidor nuevo', SERVIDOR_SIN_ELIMINAR, 'info')
            return
        if eliminar == venta_eliminada(fila):   # (ya está así: nada que hacer)
            return
        generacion, cliente = self._generacion, self.cliente
        pregunta, explicacion, texto_boton, casilla = self._textos_eliminar(fila, eliminar)
        ok, bloquear = self._preguntar_eliminar(pregunta, explicacion, texto_boton, casilla, eliminar)
        if not ok or pid in self._eliminando or generacion != self._generacion:
            return
        self._eliminando.add(pid)
        self._acciones += 1
        self.panel.set_ocupado(True)
        self.statusBar().showMessage('Eliminando la venta…' if eliminar else 'Restaurando la venta…')
        self.trabajos.iniciar(lambda: cliente.eliminar_venta(pid, eliminar, bloquear),
                              lambda r: self._eliminar_listo(pid, eliminar, r, generacion),
                              lambda e: self._eliminar_fallo(pid, eliminar, e, generacion))

    def _eliminar_listo(self, pid, eliminar, r, generacion):
        self._eliminando.discard(pid)
        self._acciones = max(0, self._acciones - 1)
        self.panel.set_ocupado(False)
        self.statusBar().clearMessage()
        if generacion != self._generacion:
            return   # (de la clave o la API de antes)
        if eliminar:
            texto = 'Venta eliminada' + (' y su licencia bloqueada' if r['licencia_bloqueada'] else '') + \
                    ': está en el filtro «Eliminadas».'
        else:
            texto = 'Venta restaurada: vuelve a contar en la lista y en los totales.'
        self._avisar(texto)
        self.statusBar().showMessage(texto, 10000)
        if r['resumen'] is not None:
            self._poner_resumen(r['resumen'], propio=True)   # (las tarjetas y el contador de «Eliminadas»)
        else:
            self._cargar_resumen()
        if self.seleccion == ('venta', pid):
            self._suelta = pid   # sigue en el panel aunque se vaya de la lista
        if eliminar and not self.recientes.cargando:
            self.recientes.poner([f for f in self.recientes.ventas if f['id'] != pid])
        elif (self.filtro.currentData() or '') or self.buscar_v.text().strip():
            self._refrescar_recientes()   # (con otro filtro la lista no trae las de «Últimas ventas»)
        self._datos_cambiaron()   # la gráfica (y, si se bloqueó la licencia, Versiones) se vuelven a pedir
        self._cargar_ventas()
        if self.seleccion == ('venta', pid):
            self._cargar_detalle()   # el panel con «Restaurar venta» (o «Eliminar») y el historial con lo que se hizo
        self.accion_terminada.emit('eliminar' if eliminar else 'restaurar', True)

    def _eliminar_fallo(self, pid, eliminar, error, generacion):
        self._eliminando.discard(pid)
        if isinstance(error, ApiError) and error.desconocida:   # el admin.php publicado todavía es el de antes
            self.panel.set_eliminar(False)
            self._poner_filtro_eliminadas(None)
            error = ApiError(SERVIDOR_SIN_ELIMINAR, 400)
        self._accion_fallo('eliminar' if eliminar else 'restaurar', error, generacion)

    def _refrescar_recientes(self):
        """«Últimas ventas» del Resumen, sin filtro (después de restaurar una venta con otro filtro elegido en Ventas)."""
        cliente, generacion = self.cliente, self._generacion

        def listo(filas):
            if generacion == self._generacion:
                self.recientes.poner(filas)

        self.trabajos.iniciar(lambda: cliente.ventas('', '', 30), listo, lambda _e: None, clave='recientes')

    # --- Avisar a un cliente desde Versiones (el botón «Avisar» de la tabla o el clic derecho)
    def _avisar_cliente(self, fila):
        """El aviso de la última versión a un cliente de la tabla de Versiones, sin tener que abrir el panel: pregunta y
        lo manda una sola vez (mientras sale, su «Avisar» dice «Enviando…»). Si ya se le avisó, ofrece reenviarlo."""
        lid, version = (fila or {}).get('licencia_id'), texto_version(self.version_ultima)
        if not lid or not version or not self.cliente or lid in self.modelo_ver.enviando:
            return
        if self._clave_mala:
            self._mensaje('Primero cambia la clave',
                          'El servidor rechazó la clave de administrador. Cámbiala en Configuración → Cambiar clave.')
            return
        quien = fila.get('cliente') or fila.get('correo') or 'este cliente'
        correo = fila.get('correo') or 'su correo'
        ya = avisado_de(fila, version)
        if ya:
            ok = self._confirmar(f'¿Reenviar el aviso de la {version} a {quien}?',
                                 f"Ya le avisaste de esta versión {fecha_frase(fila.get('aviso_fecha'))}. Le llega otra vez "
                                 f'a {correo}, con lo nuevo y el enlace para descargarla.', 'Reenviar aviso', False, 'megafono')
        else:
            ok = self._confirmar(f'¿Avisar a {quien} que actualice a la {version}?',
                                 f'Le llega un correo a {correo} con lo nuevo de la {version} y el enlace para '
                                 'descargarla.', 'Mandar aviso', False, 'megafono')
        if not ok or lid in self.modelo_ver.enviando:
            return
        info = self.version_info or {}
        notas = info.get('notas') if partes_version(info.get('version')) == partes_version(version) else None
        cliente, generacion = self.cliente, self._generacion
        self.modelo_ver.enviando.add(lid)
        self.modelo_ver._todo_cambio()
        self._acciones += 1
        self.statusBar().showMessage(f'Mandando el aviso a {quien}…')
        self.trabajos.iniciar(lambda: cliente.avisar_actualizacion(lid, version, notas, ya),
                              lambda r: self._aviso_cliente_listo(lid, r, generacion),
                              lambda e: self._aviso_cliente_fallo(lid, e, generacion))

    def _aviso_cliente_terminado(self, lid):
        self.modelo_ver.enviando.discard(lid)
        self.modelo_ver._todo_cambio()
        self.statusBar().clearMessage()

    def _aviso_cliente_listo(self, lid, r, generacion):
        self._acciones = max(0, self._acciones - 1)
        self._aviso_cliente_terminado(lid)
        if generacion != self._generacion:
            return
        if r['enviado']:
            self._avisar(f"Aviso enviado a {r['correo']}." if r['correo'] else 'Aviso enviado.')
        elif r['motivo'] == 'ya_avisado':
            self._avisar('Ya le habías avisado de esta versión.', 'info')
        else:
            self._aviso_no_enviado(r, None)
        self._datos_cambiaron()   # (Versiones vuelve a llegar: su «Avisar» pasa a «Avisado» y la tarjeta se actualiza)
        if self.seleccion == ('licencia', lid):
            self._cargar_detalle()   # el panel, con «Reenviar aviso» y el historial
        self.accion_terminada.emit('avisar', True)

    def _aviso_cliente_fallo(self, lid, error, generacion):
        self._aviso_cliente_terminado(lid)
        self._accion_fallo('avisar', error, generacion)

    def anunciar(self):
        """«Anunciar versión…»: el diálogo pregunta a quiénes y manda los avisos uno por uno."""
        if not self.cliente:
            self._falta_clave()
            return
        if self._clave_mala:
            self._mensaje('Primero cambia la clave',
                          'El servidor rechazó la clave de administrador. Cámbiala en Configuración → Cambiar clave.')
            return
        if self.servidor_nuevo is False:
            self._mensaje('Falta el servidor nuevo', SERVIDOR_VIEJO, 'info')
            return
        d = self.crear_anunciar()
        d.exec()
        if d.enviados or d.terminado:
            self._datos_cambiaron()
            if self.seleccion:
                self._cargar_detalle()

    def crear_anunciar(self):
        info = self.version_info if self._vigente('version', VIGENCIA_VERSION_S) else None
        return DialogoAnunciar(self, self.cliente, self.trabajos, info, solo_ver=self.solo_lectura)

    # --- Configuración
    def _guardar_config(self):
        try:
            self.config.guardar()
        except OSError as e:
            self.statusBar().showMessage(f'No se pudo guardar la configuración: {e}', 8000)

    def pedir_clave_inicial(self, aviso=''):
        d = DialogoClave(self, primera_vez=True)
        if aviso:
            d.error.setText(aviso)
            d.error.show()
        if d.exec() == QDialog.DialogCode.Accepted:
            self._guardar_y_usar(d.clave())
        else:
            self._falta_clave()

    def cambiar_clave(self):
        d = DialogoClave(self, primera_vez=self.cliente is None)
        if d.exec() == QDialog.DialogCode.Accepted:
            self._guardar_y_usar(d.clave())

    def _guardar_y_usar(self, clave):
        if not self.captura:
            try:
                self.config.guardar_clave(clave)
            except OSError as e:
                donde = 'Windows no pudo cifrarla' if os.name == 'nt' else 'No se pudo guardar en el Llavero'
                self._mensaje('No se pudo guardar la clave', f'{donde}: {e}')
                return
        self.usar_clave(clave)
        self._clave_mala = False
        self.banda.hide()
        self._avisar('Clave guardada.')
        self.actualizar_todo()

    def cambiar_api(self):
        d = DialogoApi(self, self.api_url)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        otra = d.url() != self.api_url
        self.api_url = d.url()
        if not self.captura:
            try:
                self.config.guardar_api(self.api_url)
            except OSError as e:
                self.statusBar().showMessage(f'No se pudo guardar la configuración: {e}', 8000)
        if otra:
            self._vaciar_datos()
        if self.cliente:
            self.usar_clave(self.cliente.clave)
            self.actualizar_todo()
        self._poner_estado()

    def _vaciar_datos(self):
        """Con otra API no quedan a la vista los datos del servidor anterior (ni se avisa de «ventas nuevas» al comparar
        con ellos)."""
        self.resumen, self.ultima, self.seleccion = None, None, None
        self.version_ultima, self.version_info, self.versiones, self.estadisticas = None, None, None, None
        self.servidor_nuevo = None
        self._suelta = self._venta_a_elegir = None
        self.panel.set_eliminar(None)
        self._poner_filtro_eliminadas(None, recargar=False)
        self._cuando.clear()
        Reloj.desfase = None
        self.banda.hide()
        self.banda_servidor.hide()
        self.panel.mostrar_vacio()
        self.servidor_errores, self.error_elegido, self._licencia_pendiente = None, None, None
        self.panel_error.mostrar_vacio()
        for modelo in (self.modelo_v, self.modelo_c, self.modelo_ver, self.modelo_av):
            modelo.cargar([])
        self._vaciar_errores('Cargando errores…')
        self._hay_mas_v, self._consulta_v = False, None
        for tarjeta in (self.t_hoy, self.t_mes, self.t_total, self.t_reemb, self.t_lic, self.t_equipos):
            tarjeta.poner('—', ' ')
        self.grafica.vaciar('Cargando…')
        self.grafica_versiones.vaciar('Cargando…')
        self.lbl_grafica.clear()
        for bloque in (self.bloque_versiones, self.plan_versiones):
            bloque.cargando()
        self.recientes.mostrar_cargando()
        for clave in ('canjes', 'versiones'):
            self.barra.botones[clave].poner_contador(None)
        self._poner_pies()

    # --- 2.8: cupones de descuento (página Cupones)
    def _cargar_cupones(self, forzar=False):
        if forzar or not self._vigente('cupones', AUTO_MS / 1000 - 5):
            cliente = self.cliente
            if not self.modelo_cup.rowCount():
                self.tabla_cup.mensaje_vacio = 'Cargando cupones…'
                self.tabla_cup.viewport().update()

            def fallo(error):
                if isinstance(error, ApiError) and error.desconocida:   # el admin.php publicado todavía no los tiene
                    self.servidor_cupones = False
                    self.modelo_cup.cargar([])
                    self.tabla_cup.mensaje_vacio = FALTA_SERVIDOR_CUPONES
                    self.btn_nuevo_cupon.setEnabled(False)
                else:
                    self.tabla_cup.mensaje_vacio = f'No se pudieron cargar los cupones. {self._texto_fallo(error)}'
                self.tabla_cup.viewport().update()
                self._poner_pies()

            self._pedir('cupones', cliente.cupones, self._poner_cupones, fallo)

    def _poner_cupones(self, r):
        self.cupones_info = r
        self.servidor_cupones = True
        self.btn_nuevo_cupon.setEnabled(not self.solo_lectura)
        self.modelo_cup.moneda = r['moneda']
        self._recargar(self.tabla_cup, self.modelo_cup, r['cupones'])
        self.tabla_cup.mensaje_vacio = 'Todavía no hay cupones. Crea el primero con «Nuevo cupón».'
        activos = sum(1 for c in r['cupones'] if c['estado'] == 'activo')
        self.filtro_cup.contar('activo', activos)
        self.filtro_cup.contar('inactivo', len(r['cupones']) - activos)
        self._filtrar_locales()
        elegir, self._cupon_a_elegir = self._cupon_a_elegir, None
        for n in self.modelo_cup.buscar('id', elegir):   # (el que se acaba de crear, elegido y a la vista)
            self._elegir_fila(self.tabla_cup, self.modelo_cup, n)

    def _puede_cambiar_cupones(self):
        """¿Se puede mandar un cambio de cupones? Si no, dice por qué."""
        if not self.cliente:
            self._falta_clave()
            return False
        if self._clave_mala:
            self._mensaje('Primero cambia la clave',
                          'El servidor rechazó la clave de administrador. Cámbiala en Configuración → Cambiar clave.')
            return False
        if self.solo_lectura:
            self._mensaje('Solo lectura', 'En modo captura la app no cambia nada en el servidor.', 'info')
            return False
        if self.servidor_cupones is False:
            self._mensaje('Falta el servidor nuevo', FALTA_SERVIDOR_CUPONES, 'info')
            return False
        return True

    def _dialogo_cupon(self, cupon=None):
        info = self.cupones_info or {}
        d = DialogoCupon(self, cupon, info.get('precio'), info.get('moneda') or 'USD', info.get('hoy'))
        return d if d.exec() == QDialog.DialogCode.Accepted else None

    def nuevo_cupon(self):
        """«Nuevo cupón»: pide los datos, lo crea y lo deja elegido en la tabla (su enlace, en el mensajito de abajo)."""
        if not self._puede_cambiar_cupones():
            return
        d = self._dialogo_cupon()
        if d is None:
            return
        datos, cliente = d.datos(), self.cliente
        self._enviar_cupon('cupon_crear', None, lambda: cliente.cupon_crear(**datos), 'Creando el cupón…',
                           lambda c: f"Cupón {c['codigo']} creado. Clic derecho para copiar su enlace.")

    def _editar_cupon(self, fila):
        """Doble clic en un cupón (o «Editar…»): el diálogo con sus datos; ahí también se borra."""
        if not fila or not self._puede_cambiar_cupones() or fila['id'] in self._cupon_en_camino:
            return
        d = self._dialogo_cupon(fila)
        if d is None:
            return
        if d.quiere_borrar:
            self._borrar_cupon(fila)
            return
        cambios, cliente, cid = d.cambios(), self.cliente, fila['id']
        if cambios:
            self._enviar_cupon('cupon_editar', cid, lambda: cliente.cupon_editar(cid, **cambios), 'Guardando el cupón…',
                               lambda c: f"Cupón {c['codigo']} guardado.")

    def _activar_cupon(self, fila, activo):
        """«Pausar» o «Activar» (clic derecho): sin pregunta, se deshace con el mismo clic."""
        if not fila or not self._puede_cambiar_cupones() or fila['id'] in self._cupon_en_camino:
            return
        cliente, cid = self.cliente, fila['id']
        self._enviar_cupon('cupon_editar', cid, lambda: cliente.cupon_editar(cid, activo=activo),
                           'Activando el cupón…' if activo else 'Pausando el cupón…',
                           lambda c: (f"Cupón {c['codigo']} activo: ya se puede usar." if activo else
                                      f"Cupón {c['codigo']} pausado: no se puede usar hasta que lo actives."))

    def _borrar_cupon(self, fila):
        if not fila or not self._puede_cambiar_cupones() or fila['id'] in self._cupon_en_camino:
            return
        ventas = (f"Sus {plural(fila['usos'], 'venta sigue', 'ventas siguen')} igual y guardan el código. "
                  if fila['usos'] else '')
        if not self._confirmar(f"¿Borrar el cupón {fila['codigo']}?",
                               f'Deja de servir en la web al instante y su enlace ya no da el descuento. {ventas}'
                               'Si solo quieres que no se use por un tiempo, mejor páusalo (clic derecho → Pausar).',
                               'Borrar cupón', True, 'basura'):
            return
        cliente, cid, codigo = self.cliente, fila['id'], fila['codigo']
        self._enviar_cupon('cupon_borrar', cid, lambda: cliente.cupon_borrar(cid), 'Borrando el cupón…',
                           lambda _r: f'Cupón {codigo} borrado.')

    def _enviar_cupon(self, nombre, cid, tarea, ocupado, exito):
        """Manda un cambio de cupones (uno a la vez por cupón) y, al terminar, avisa y recarga la lista."""
        generacion = self._generacion
        if cid is not None:
            self._cupon_en_camino.add(cid)
        self._acciones += 1
        self.statusBar().showMessage(ocupado)

        def terminar():
            self._cupon_en_camino.discard(cid)
            self._acciones = max(0, self._acciones - 1)
            self.statusBar().clearMessage()

        def listo(resultado):
            terminar()
            if generacion != self._generacion:
                return   # (de la clave o la API de antes)
            if nombre == 'cupon_crear' and resultado:
                self._cupon_a_elegir = resultado['id']
                if self.filtro_cup.valor or self.buscar_cup.text():   # (que el nuevo no quede escondido por un filtro)
                    self.buscar_cup.clear()
                    self.filtro_cup.poner('')
            self._avisar(exito(resultado))
            self._cargar_cupones(forzar=True)
            self.accion_terminada.emit(nombre, True)

        def fallo(error):
            terminar()
            if isinstance(error, ApiError) and error.codigo == 401 and generacion == self._generacion:
                self._clave_rechazada(error)
            if isinstance(error, ApiError) and error.desconocida:
                self.servidor_cupones = False
            titulo = {'cupon_crear': 'No se pudo crear el cupón', 'cupon_editar': 'No se pudo guardar el cupón',
                      'cupon_borrar': 'No se pudo borrar el cupón'}[nombre]
            self._mensaje(titulo, FALTA_SERVIDOR_CUPONES if self.servidor_cupones is False else self._texto_fallo(error))
            if cid is not None:
                self._cargar_cupones(forzar=True)   # (quizá ya no existe: la lista se pone al día)
            self.accion_terminada.emit(nombre, False)

        self.trabajos.iniciar(tarea, listo, fallo)

    def _menu_cupon(self, menu, fila):
        """El clic derecho de un cupón: copiar su código o su enlace, editarlo, pausarlo o activarlo, y borrarlo."""
        a = menu.addAction(icono('copiar'), 'Copiar código')
        a.triggered.connect(lambda _c=False, t=fila['codigo']: self._copiar(t, 'Código copiado'))
        a = menu.addAction(icono('enviar'), 'Copiar enlace para compartir')
        a.triggered.connect(lambda _c=False, t=fila['enlace']: self._copiar(t, f'Enlace copiado: {t}'))
        menu.addSeparator()
        puede = not self.solo_lectura and self.servidor_cupones is not False and fila['id'] not in self._cupon_en_camino
        for nombre_icono, texto, funcion in (
                ('lapiz', 'Editar…', lambda _c=False, f=dict(fila): self._editar_cupon(f)),
                ('detener' if fila['activo'] else 'ok', 'Pausar' if fila['activo'] else 'Activar',
                 lambda _c=False, f=dict(fila): self._activar_cupon(f, not f['activo'])),
                ('basura', 'Borrar…', lambda _c=False, f=dict(fila): self._borrar_cupon(f))):
            a = menu.addAction(icono(nombre_icono, PELIGRO if nombre_icono == 'basura' else TEXTO_SUAVE), texto)
            a.setEnabled(puede)
            a.triggered.connect(funcion)
        return menu

    def exportar_csv(self):
        tabla = self._tabla_actual()
        tipo = {id(self.tabla_v): 'ventas', id(self.tabla_c): 'canjes', id(self.tabla_ver): 'versiones'}.get(id(tabla))
        if tipo is None:
            self._avisar('Abre Ventas, Versiones o Canjes para exportar su tabla.', 'info')
            return
        proxy = tabla.model()
        modelo = proxy.sourceModel()
        if proxy.rowCount() == 0:
            self._avisar('No hay filas para exportar.', 'error')
            return
        nombre = {'ventas': 'ventas', 'canjes': 'canjes-gumroad', 'versiones': 'versiones'}[tipo]
        if tipo == 'ventas' and self.filtro.currentData() == 'eliminadas':
            nombre = 'ventas-eliminadas'
        nombre = f'{nombre}-cinecaptions-{dt.date.today():%Y-%m-%d}.csv'
        carpeta = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation) or str(Path.home())
        ruta, _ = QFileDialog.getSaveFileName(self, 'Exportar a CSV', str(Path(carpeta) / nombre), 'CSV para Excel (*.csv)')
        if not ruta:
            return
        filas = [modelo.fila(proxy.mapToSource(proxy.index(i, 0)).row()) for i in range(proxy.rowCount())]
        if tipo == 'versiones':   # (la tabla va por cliente; el CSV, un equipo por fila con todos sus datos)
            filas = [e for c in filas for e in c['filas']]
        try:
            n = escribir_csv(ruta, filas, tipo)
        except (OSError, ValueError, csv.Error) as e:   # por ejemplo, el archivo está abierto en Excel
            self._mensaje('No se pudo guardar el CSV', str(e))
            return
        self._avisar(f"Se exportaron {plural(n, 'fila', 'filas')}.")
        self.statusBar().showMessage(f'CSV guardado en {ruta}', 10000)

    def _acerca(self):
        DialogoAcerca(self).exec()

    # --- Ventana
    def restaurar_tamano(self):
        def guardado(nombre):   # un config.json dañado o editado a mano no impide abrir la app
            valor = self.config.datos.get(nombre)
            try:
                return QByteArray.fromBase64(valor.encode('ascii')) if isinstance(valor, str) and valor else None
            except UnicodeEncodeError:
                return None

        geometria = guardado('ventana')
        if not (geometria and self.restoreGeometry(geometria)):
            pantalla = QGuiApplication.primaryScreen().availableGeometry()
            self.resize(min(1440, int(pantalla.width() * 0.94)), min(900, int(pantalla.height() * 0.92)))
            self.move(pantalla.center() - self.rect().center())
        divisor = guardado('divisor')
        if divisor:
            self.divisor.restoreState(divisor)
        if getattr(self, '_tipo_lado', None) == 'errores':   # (abrió en Errores: lo guardado es el ancho de las demás)
            self._anchos_lado['otras'] = self.divisor.sizes()[1] if self.lado.isVisible() else None
            self._aplicar_errores()

    def _recordar_lado(self):
        """El ancho del panel de la derecha de la página que se ve (si se ve), para volver a él al regresar."""
        tamanos = self.divisor.sizes()
        if getattr(self, '_tipo_lado', None) == 'otras' and len(tamanos) == 2 and tamanos[1] > 0 and self.lado.isVisible():
            self._anchos_lado['otras'] = tamanos[1]

    def _lado_movido(self, _pos, _indice):
        """El dueño arrastró el divisor: en Errores se recuerda la PARTE de la ventana."""
        tamanos = self.divisor.sizes()
        if getattr(self, '_tipo_lado', None) == 'errores' and sum(tamanos) > 0 and tamanos[1] > 0:
            self._frac_errores = min(0.75, max(0.35, tamanos[1] / sum(tamanos)))

    def _aplicar_errores(self):
        total = sum(self.divisor.sizes()) or self.divisor.width()
        if total > 0:
            ancho = min(int(total * self._frac_errores), total - 300)
            self.divisor.blockSignals(True)
            self.divisor.setSizes([total - ancho, ancho])
            self.divisor.blockSignals(False)

    def _tamano_lado(self, pagina):
        """2.3 (propuesta A): en Errores el panel del error es ANCHO (la captura y el informe técnico se leen sin cortar
        las líneas): el 58 % de la ventana la primera vez, también al cambiar su tamaño; las demás páginas, el ancho de
        siempre. Cada uno recuerda lo que el dueño arrastró (el de Errores en config «frac_errores»)."""
        self._recordar_lado()
        if pagina == 'resumen':
            return
        tipo = 'errores' if pagina == 'errores' else 'otras'
        anterior = getattr(self, '_tipo_lado', None)
        self._tipo_lado = tipo
        if tipo == 'errores':
            self._aplicar_errores()
        elif anterior == 'errores' and self._anchos_lado.get('otras'):
            total = sum(self.divisor.sizes()) or self.divisor.width()
            ancho = min(self._anchos_lado['otras'], total - 300)
            self.divisor.setSizes([total - ancho, ancho])

    def resizeEvent(self, evento):
        super().resizeEvent(evento)   # (2.7: la isla se acomoda sola al nuevo ancho: mira el Resize de la raíz)
        if getattr(self, '_tipo_lado', None) == 'errores' and self.pagina == 'errores':
            QTimer.singleShot(0, self._aplicar_errores)   # (con el divisor ya en su tamaño nuevo)
        self.aviso.acomodar()

    def closeEvent(self, evento):
        if self._acciones and not self.captura and not self._confirmar(
                'Todavía se está guardando un cambio',
                'La app espera la respuesta del servidor. Si cierras ahora no sabrás si el cambio se aplicó.',
                'Cerrar de todas formas'):
            evento.ignore()
            return
        self._auto.stop()
        if self._bandeja is not None:
            self._bandeja.hide()
        if not self.captura:
            self.config.datos['ventana'] = bytes(self.saveGeometry().toBase64()).decode('ascii')
            self._recordar_lado()
            self.config.datos['frac_errores'] = round(self._frac_errores, 3)
            if getattr(self, '_tipo_lado', None) == 'errores' and self._anchos_lado.get('otras'):
                total = sum(self.divisor.sizes())   # («divisor» es el de las demás páginas, no el ancho de Errores)
                self.divisor.setSizes([max(300, total - self._anchos_lado['otras']), self._anchos_lado['otras']])
            if getattr(self, '_tipo_lado', None) != 'errores' or self._anchos_lado.get('otras'):
                self.config.datos['divisor'] = bytes(self.divisor.saveState().toBase64()).decode('ascii')
            self.config.datos['pagina'] = self.pagina
            self._guardar_config()
        super().closeEvent(evento)


def contar_estados(equipos, modelo):
    """Cuántos equipos hay en cada estado de versión."""
    cuenta = {}
    for e in equipos:
        estado = modelo.estado(e)
        cuenta[estado] = cuenta.get(estado, 0) + 1
    return cuenta


def _plano(texto):
    """Para buscar sin mayúsculas ni tildes (como el LIKE de MySQL): «Ñúñez» → «nunez»."""
    texto = unicodedata.normalize('NFKD', str(texto or ''))
    return ''.join(c for c in texto if not unicodedata.combining(c)).casefold()


# ---------------------------------------------------------------- Capturas para la revisión visual (--captura)

class Capturador(QObject):
    """Carga los datos y guarda PNG de cada página, del panel y de los diálogos (revisión visual). Cada paso espera a que
    no quede nada cargando. SOLO LECTURA: la ventana usa un cliente con solo_lectura=True (ni siquiera deja salir una
    acción que cambie algo o mande correos), los diálogos solo se muestran (nunca se aceptan) y «Anunciar» no manda nada.
    Con el admin.php anterior se saltan los pasos que necesitan el servidor nuevo. ancho: el de la ventana (--ancho)."""

    def __init__(self, app, ventana, carpeta, ancho=1440):
        super().__init__(ventana)
        self.app, self.v, self.carpeta, self.ancho = app, ventana, Path(carpeta), ancho
        self.carpeta.mkdir(parents=True, exist_ok=True)
        v = ventana
        # Una venta con varios equipos y alguno desactualizado: así se ve casi todo el panel (versiones, avisar, notas)
        completa = (lambda f: (f['equipos'] or 0) >= 2 and (f.get('equipos_desactualizados') or 0) > 0
                    and f['licencia_estado'] == 'activa', lambda f: (f['equipos'] or 0) >= 2)
        self.pasos = [   # (nombre del PNG o None, lo que se prepara, ¿necesita el servidor nuevo?)
            ('01_resumen.png', lambda: v.ir_a('resumen')),
            ('02_grafica_con_el_mouse.png', self._globo),
            ('03_ventas.png', lambda: (v.ir_a('ventas'), self._elegir(v.tabla_v, *completa))),
            ('04_panel_completo.png', lambda: ('completo', v.panel.scroll.widget())),
            ('05_consulta_recurrente.png',
             lambda: v.panel.accion.emit('recurrente', {}) if v.panel.btn_recurrente.isVisibleTo(v.panel) else None),
            (None, lambda: v.filtro.setCurrentIndex(v.filtro.findData('todos'))),
            ('06_pago_sin_completar.png', lambda: self._elegir(v.tabla_v, lambda f: f['estado'] == 'pendiente' and f['correo'])),
            ('07_venta_reembolsada.png', lambda: self._elegir(v.tabla_v, lambda f: f['estado'] == 'reembolsado')),
            # (las eliminadas: atenuadas, con «Restaurar venta» en el panel; después, la lista normal otra vez)
            (None, lambda: v.filtro.setCurrentIndex(v.filtro.findData('eliminadas')) if v.panel.con_eliminar else None,
             True),
            ('07b_ventas_eliminadas.png', lambda: self._elegir(v.tabla_v, lambda f: True), True),
            (None, lambda: v.filtro.setCurrentIndex(v.filtro.findData(''))),
            # (las páginas que cargan sus datos al abrirse: primero se abren y, cuando llegaron, se elige la fila)
            (None, lambda: v.ir_a('versiones')),
            ('08_versiones.png', lambda: self._elegir(v.tabla_ver, lambda f: v.modelo_ver.estado(f) == 'desactualizado')),
            ('09_versiones_desactualizados.png', lambda: v.filtro_ver.poner('desactualizado')),
            ('10_canjes_gumroad.png', lambda: (v.filtro_ver.poner('todos'), v.ir_a('canjes'),
                                               self._elegir(v.tabla_c, lambda f: (f['equipos'] or 0) >= 1))),
            (None, lambda: v.ir_a('avisos')),
            ('11_avisos.png', lambda: self._elegir(v.tabla_av, lambda f: f['ok'])),
            (None, lambda: v.ir_a('cupones'), True),   # (2.8: los cupones, con uno ya usado elegido)
            ('11b_cupones.png', lambda: self._elegir(v.tabla_cup, lambda f: f['usos'] > 0, lambda f: True), True),
            # (los errores: «Por usuario» con el cliente que tiene más sin ver y el informe del más reciente; después la
            # tabla de todos, también los ya vistos)
            (None, lambda: (v.vista_errores.poner('usuario'), v.ir_a('errores'))),
            ('12_errores_por_usuario.png', lambda: self._elegir(v.tabla_cli, lambda f: f['sin_ver'] > 1,
                                                                lambda f: f['sin_ver'] > 0), True),
            # (2.4: la pestaña «Cliente y equipo» de ese error con la ficha técnica del equipo, entera, y la ficha en su
            # ventanita, como sale con «Ficha» en los equipos de la licencia)
            ('12b_error_cliente_y_equipo.png', self._error_cliente_y_equipo, True),
            ('12c_ficha_del_equipo.png', self._ficha_equipo, True),
            ('13_errores_todos.png', lambda: (self._pestana_error(None), v.vista_errores.poner('lista'),
                                              v.filtro_err.poner('todos')), True),
            ('14_ventana_angosta.png', self._angosta),
            ('15_anunciar_version.png', self._anunciar, True),
            ('16_confirmar_anuncio.png', self._confirmar_anuncio, True),
            ('17_editar_cliente.png', self._editar_cliente, True),
            ('18_dialogo_clave.png', self._dialogo_clave),
            ('19_confirmacion.png', self._confirmacion),
            ('20_eliminar_venta.png', self._eliminar_venta, True),
        ]
        self.i = 0
        self.guardadas = []
        self.codigo = None             # cómo terminó (None mientras sigue)
        self._preparado = False
        self._quieto = 0
        self._widget = None
        self._completo = False
        self._dialogo_anunciar = None
        self._reloj = QTimer(self)
        self._reloj.setInterval(100)
        self._reloj.timeout.connect(self._revisar)
        self._limite = QTimer(self)
        self._limite.setSingleShot(True)
        self._limite.setInterval(120000)
        self._limite.timeout.connect(self._agotado)

    def iniciar(self):
        self._reloj.start()
        self._limite.start()

    def _ocupado(self):
        v = self.v
        temporizadores = [v._timer_detalle, v._timer_buscar_v, v._timer_buscar_c, v._timer_filtro, v._timer_error]
        if self._widget is not None and hasattr(self._widget, '_timer_candidatos'):
            temporizadores.append(self._widget._timer_candidatos)
        return (v.trabajos.activos > 0 or v._actualizando or not v.intento_listo
                or any(t.isActive() for t in temporizadores) or v.barra.moviendose())   # (2.7: la isla ya asentada)

    def _revisar(self):
        if self._ocupado():
            self._quieto = 0
            return
        self._quieto += 1
        if self._quieto < 4:   # 400 ms sin nada pendiente: ya se pintó
            return
        self._quieto = 0
        if self._preparado:   # (se avanza antes de guardar: un error en un paso no lo repite cada 100 ms)
            nombre = self.pasos[self.i][0]
            self.i += 1
            self._preparado = False
            if nombre:
                self._guardar(nombre)
        while self.i < len(self.pasos):
            paso = self.pasos[self.i]
            if len(paso) > 2 and paso[2] and self.v.servidor_nuevo is not True:
                print(f'Se salta {paso[0]}: necesita el servidor nuevo', flush=True)
                self.i += 1
                continue
            break
        if self.i >= len(self.pasos):
            self._terminar(0)
            return
        preparar = self.pasos[self.i][1]
        self.v.aviso.hide()   # el aviso del paso anterior no tapa la captura siguiente
        self._preparado = True
        resultado = preparar() if preparar else None
        self._completo = isinstance(resultado, tuple) and len(resultado) == 2 and resultado[0] == 'completo'
        if self._completo:
            resultado = resultado[1]
        self._widget = resultado if isinstance(resultado, QWidget) else None

    def _guardar(self, nombre):
        widget = self._widget or self.v
        if self._completo:   # todo el contenido del panel, aunque no quepa en la ventana (con su fondo)
            imagen = QPixmap(widget.size() * self.v.devicePixelRatioF())
            imagen.setDevicePixelRatio(self.v.devicePixelRatioF())
            imagen.fill(QColor(SUPERFICIE))
            p = QPainter(imagen)
            widget.render(p, QPoint(0, 0))
            p.end()
        else:
            if widget is not self.v and widget.isWindow():
                widget.adjustSize()   # el diálogo ya con lo que cargó
            imagen = widget.grab()
        ruta = self.carpeta / nombre
        if imagen.save(str(ruta)):
            self.guardadas.append(ruta)
            print(f'Captura: {ruta} ({imagen.width()}x{imagen.height()})', flush=True)
        else:
            print(f'No se pudo guardar {ruta}', file=sys.stderr, flush=True)
        # (el diálogo de anunciar queda abierto para el paso siguiente: la confirmación usa sus candidatos)
        if self._widget is not None and not self._completo and self._widget is not self._dialogo_anunciar:
            self._widget.close()
        self._widget, self._completo = None, False

    def _elegir(self, tabla, *condiciones):
        """Elige la primera fila que cumple la primera condición (si ninguna, la segunda...; si no, la primera fila)."""
        proxy = tabla.model()
        tabla.clearSelection()
        for condicion in condiciones:
            for fila in range(proxy.rowCount()):
                datos = self.v._fila_de(tabla, proxy.index(fila, 0))
                if datos and condicion(datos):
                    tabla.selectRow(fila)
                    tabla.scrollTo(proxy.index(fila, 0))
                    return
        if proxy.rowCount():
            tabla.selectRow(0)

    def _globo(self):
        """El mouse sobre la barra del día con más ingresos: sale el globito con el monto."""
        g = self.v.grafica
        if g.dias:
            i = max(range(len(g.dias)), key=lambda n: (g.dias[n]['ingresos'], n))
            area = g._area()
            punto = QPointF(area.left() + area.width() / len(g.dias) * (i + 0.5), area.center().y())
            QApplication.sendEvent(g, QMouseEvent(QEvent.Type.MouseMove, punto, g.mapToGlobal(punto),
                                                  Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                                                  Qt.KeyboardModifier.NoModifier))
        return g.parentWidget()   # la tarjeta de la gráfica

    def _angosta(self):
        self.v.ir_a('ventas')
        self.v.resize(1100, 720)

    def _fuera_de_pantalla(self, widget):
        widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        widget.show()
        widget.adjustSize()
        return widget

    def _anunciar(self):
        self.v.resize(self.ancho, 900)
        self._dialogo_anunciar = self.v.crear_anunciar()   # solo_ver: el botón de mandar queda apagado
        return self._fuera_de_pantalla(self._dialogo_anunciar)

    def _confirmar_anuncio(self):
        d = self._dialogo_anunciar
        pregunta, explicacion, texto_boton = d.texto_confirmacion(max(1, len(d.candidatos)))
        d.close()
        self._dialogo_anunciar = None
        caja, _ = caja_confirmacion(self.v, pregunta, explicacion, texto_boton, False, 'megafono')
        return self._fuera_de_pantalla(caja)

    def _pestana_error(self, clave):
        """La pestaña del panel del error («cliente»…) o, con None, la de siempre (la captura si la tiene)."""
        pe = self.v.panel_error
        pe._pestana_elegida = clave
        if pe.fila is not None:
            pe._elegir_pestana(clave or ('captura' if cuales_captura(pe.error()) else 'informe'))   # (2.5: o solo la ventana)

    def _error_cliente_y_equipo(self):
        self._pestana_error('cliente')
        return ('completo', self.v.panel_error.scroll.widget())

    def _ficha_equipo(self):
        """DialogoFicha con la ficha del equipo del error elegido (ya llegó con error_detalle: no pide nada)."""
        e = self.v.panel_error.detalle or {}
        equipo = {'equipo': e.get('equipo'), 'nombre_equipo': e.get('nombre_equipo'), 'so': e.get('so'),
                  'version': e.get('version')}
        d = DialogoFicha(self.v, equipo, e.get('ficha_equipo'), f"{e.get('cliente') or 'Cliente'} · {e.get('clave') or ''}")
        d.alto_fijo = 1180   # (la pantalla sin pantalla mide 800×600: con su alto normal se vería muy poco)
        return self._fuera_de_pantalla(d)

    def _editar_cliente(self):
        d = self.v.panel.detalle or {}   # (la venta elegida en la ventana angosta)
        lic, otra = d.get('licencia') or {}, d.get('pedido') or d.get('canje') or {}
        return self._fuera_de_pantalla(DialogoCliente(self.v, lic.get('nombre') or otra.get('nombre') or 'Mariana López',
                                                      lic.get('correo') or otra.get('correo') or 'mariana@example.com'))

    def _dialogo_clave(self):
        return self._fuera_de_pantalla(DialogoClave(self.v, primera_vez=True))

    def _confirmacion(self):
        caja, _ = caja_confirmacion(self.v, '¿Marcar el pedido #13 como reembolsado?',
                                    'Venta de Mariana López por $29.00 USD.\nEsto NO devuelve el dinero: el reembolso se '
                                    'hace en el panel de Recurrente.\nLa venta deja de contar en los ingresos y la licencia '
                                    'CC-7K2M-Q9XA-4HBR-T3WZ queda bloqueada.', 'Marcar como reembolsado', True, 'reembolso')
        return self._fuera_de_pantalla(caja)

    def _eliminar_venta(self):
        """La pregunta de «Eliminar venta» de una venta con la licencia activa (con la casilla «Bloquear también su
        licencia»). Solo se muestra: nunca se acepta."""
        filas = [f for f in self.v.modelo_v.filas if f.get('licencia_estado') == 'activa' and (f.get('equipos') or 0) > 1]
        fila = filas[0] if filas else {'id': 13, 'nombre': 'Mariana López', 'estado': 'pagado', 'monto': 2900,
                                       'moneda': 'USD', 'licencia_id': 1, 'licencia_estado': 'activa', 'equipos': 2}
        pregunta, explicacion, texto_boton, casilla = self.v._textos_eliminar(fila, True)
        caja, _ = caja_confirmacion(self.v, pregunta, explicacion, texto_boton, True, 'basura', casilla=casilla)
        return self._fuera_de_pantalla(caja)

    def _agotado(self):
        print('Se acabó el tiempo esperando los datos.', file=sys.stderr, flush=True)
        self._widget, self._completo = None, False
        try:
            self._guardar('99_tiempo_agotado.png')
        finally:   # aunque la captura falle, la app sale (nunca se queda abierta y escondida)
            self._terminar(3)

    def _terminar(self, codigo):
        self._reloj.stop()
        self._limite.stop()
        if codigo == 0 and ERRORES:
            codigo = 4
        self.codigo = codigo
        print(f'Listo: {len(self.guardadas)} capturas en {self.carpeta}', flush=True)
        self.app.exit(codigo)


# ---------------------------------------------------------------- Arranque

ERRORES = []


def instalar_errores(con_ventanas=True):
    """Un error inesperado no cierra la app en silencio: se anota en errores.log y se avisa."""
    avisado = {'abierto': False, 'ultimo': '', 'cuando': 0.0}

    def avisar(valor):
        # Un error que se repite (por ejemplo, al pintar una tabla) no abre una ventana tras otra: una a la vez, y la
        # misma no se repite antes de 30 segundos. Todos quedan en errores.log.
        resumen = f'{type(valor).__name__}: {valor}'
        if avisado['abierto'] or (resumen == avisado['ultimo'] and time.monotonic() - avisado['cuando'] < 30):
            return
        avisado['abierto'] = True
        try:
            mensaje(None, 'Algo falló dentro de la app', f'{valor}\n\nEl detalle quedó en {carpeta_config() / "errores.log"}.')
        finally:
            avisado.update(abierto=False, ultimo=resumen, cuando=time.monotonic())

    def gancho(tipo, valor, rastro):
        texto = ''.join(traceback.format_exception(tipo, valor, rastro))
        ERRORES.append(texto)
        try:
            carpeta_config().mkdir(parents=True, exist_ok=True)
            with open(carpeta_config() / 'errores.log', 'a', encoding='utf-8') as archivo:
                archivo.write(f'--- {dt.datetime.now():%Y-%m-%d %H:%M:%S} {APP} {VERSION}\n{texto}\n')
        except OSError:
            pass
        if sys.stderr:
            print(texto, file=sys.stderr, flush=True)
        if con_ventanas and QApplication.instance():
            avisar(valor)
    sys.excepthook = gancho


def preparar_consola():
    """En el .exe (sin consola) los mensajes no se verían: se usa la consola desde la que lo abrieron, si hay una."""
    if os.name != 'nt' or (sys.stdout is not None and sys.stderr is not None):
        return
    try:
        if ctypes.windll.kernel32.AttachConsole(-1):   # ATTACH_PARENT_PROCESS
            salida = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
            sys.stdout = sys.stdout or salida
            sys.stderr = sys.stderr or salida
    except OSError:
        pass


def importar_clave(ruta):
    """--importar-clave: lee la clave de un archivo, la guarda cifrada con DPAPI y sale (sin ventana)."""
    try:
        clave = extraer_clave(leer_texto(ruta))
        problema = problema_clave(clave)
        if problema:
            raise ValueError(problema)
        Configuracion().guardar_clave(clave)
    except (OSError, ValueError) as e:
        print(f'No se guardó la clave: {e}', file=sys.stderr, flush=True)
        return 1
    print('Clave guardada', flush=True)
    return 0


def crear_app(argumentos_qt):
    """QApplication con la fuente, la paleta y la hoja de estilos de la marca."""
    if os.name == 'nt':
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('CinemaProductions.CineCaptionsVentas')
        except (OSError, AttributeError):
            pass
    app = QApplication(argumentos_qt)
    app.setApplicationName(APP)
    app.setOrganizationName('Cinema Productions')
    app.setApplicationVersion(VERSION)
    traductor = QTranslator(app)   # menús de Qt en español («Copiar», «Pegar»...)
    if traductor.load('qtbase_es', QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(traductor)
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    except AttributeError:
        pass
    cargar_fuentes()
    app.setStyle('Fusion')
    app.setPalette(paleta_oscura())
    app.setStyleSheet(hoja_estilo(preparar_imagenes_qss()))
    fijar_fuente(app)   # (después de la hoja de estilos: al aplicarla, Windows vuelve a poner su letra en tablas y menús)
    app.setWindowIcon(icono_app())
    filtro = FiltroVentanas(app)
    app.installEventFilter(filtro)
    app._filtro_ventanas = filtro
    return app


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    parser = argparse.ArgumentParser(prog='CineCaptions Ventas', description='Ventas y licencias de CineCaptions.')
    parser.add_argument('--importar-clave', metavar='ARCHIVO', help='guarda la clave de ese archivo (cifrada) y sale')
    parser.add_argument('--api', metavar='URL', help='usa otra dirección de la API solo en esta ejecución')
    parser.add_argument('--captura', metavar='CARPETA', help='guarda capturas PNG de la ventana y sale')
    parser.add_argument('--ancho', metavar='PX', type=int, default=1440,
                        help='con --captura: el ancho de la ventana (1100 como mínimo; si no se dice, 1440)')
    args, resto = parser.parse_known_args(argv[1:])
    if args.importar_clave or args.captura:
        preparar_consola()
    if args.importar_clave:
        return importar_clave(args.importar_clave)
    api = None
    if args.api:
        try:
            api = validar_api(args.api)
        except ValueError as e:
            print(f'Dirección de la API no válida: {e}', file=sys.stderr, flush=True)
            return 2
    captura = bool(args.captura)
    instalar_errores(con_ventanas=not captura)
    app = crear_app(argv[:1] + resto)
    config = Configuracion()
    # --captura es SOLO LECTURA: el cliente de la API ni siquiera deja salir una acción que cambie algo o mande correos
    ventana = VentanaPrincipal(config, api or config.api, captura=captura, solo_lectura=captura)
    clave = config.leer_clave()
    if captura:
        if not clave:
            print('No hay una clave guardada: usa primero --importar-clave.', file=sys.stderr, flush=True)
            return 2
        ventana.usar_clave(clave)
        ancho = max(1100, args.ancho)   # (más angosta no se puede: es el mínimo de la ventana)
        capturador = Capturador(app, ventana, args.captura, ancho)
        ventana.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)   # se dibuja completa, pero no aparece
        ventana.resize(ancho, 900)
        ventana.show()
        capturador.iniciar()
        QTimer.singleShot(0, ventana.actualizar_todo)
    else:
        ventana.restaurar_tamano()
        ventana.show()
        if clave:
            ventana.usar_clave(clave)
            QTimer.singleShot(0, ventana.actualizar_todo)
        else:
            # Hay una clave guardada que no se pudo abrir: se cifró con otro usuario de Windows o en otra PC
            aviso = (('La clave guardada no se puede abrir con este usuario de Windows (se guardó en otra PC o con otro '
                      'usuario). Pégala de nuevo.') if os.name == 'nt' else
                     'No se pudo leer la clave del Llavero de esta Mac. Pégala de nuevo.') if config.datos.get('clave') else ''
            QTimer.singleShot(200, lambda: ventana.pedir_clave_inicial(aviso))
    codigo = app.exec()
    if not ventana.trabajos.cerrar(2500):   # una llamada colgada no deja el programa abierto en segundo plano
        sys.stdout and sys.stdout.flush()
        os._exit(codigo)
    return codigo


if __name__ == '__main__':
    sys.exit(main())
