# CineCaptions · By Cinema Productions
# 1_codigo/ui_comun.py — Lo que comparten la ventana principal y sus ventanas: constantes, idiomas, colores, fuentes, marcas y ayudantes de la interfaz.
"""
ui_comun.py
-----------
Lo que comparten la ventana principal y sus ventanas: constantes, idiomas, colores, fuentes, marcas y ayudantes de la interfaz.

Salió de «CineCaptions (script principal).py» (v5.4.44) SIN cambiar su código: el principal conserva la ventana principal (SubtitleApp) y vuelve a importar estos nombres, así que `cc_main.NombreDeClase` sigue existiendo.
"""
import json
import datetime
import math
import sys
import time
from pathlib import Path
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontDatabase, QPainterPath
from PySide6.QtWidgets import QVBoxLayout
import qt_kit as ui
from qt_kit import Combo, Etiqueta, correr_en_hilo
from qt_kit import QColor
from i18n import idioma as idioma_ui, nombre_idioma, tr
import subtitle_transcriber as st
import archivos_seguros
import plantillas
import composicion
from sfx_rules import CARPETA_USUARIO as _CARPETA_SFX_USUARIO
import registro

# v5.0.0: la pantalla «Estilos y composición» la muestra siempre (decision del
# rediseño). Con True la composicion elegida viaja en el manifiesto y se carga
# de las preferencias; con False todo sale como la plantilla, como en la v4.
# v5.11: el usuario pidio quitar la tarjeta «Estilo del bloque» (vista aproximada de 3 lineas + Ajuste fino + Icono o imagen): choca con el estilo
# «guion» y el estilo de cada bloque se elige en Creativo. Con False ni se crea ni viaja nada de ella. (ComposicionWindow queda en el codigo, sin usar.)
COMPOSICION_VISIBLE = False
def sfx_ruta_reglas_usuario():
    """Donde queda el sfx_rules.json que el usuario SI puede editar."""
    return _CARPETA_SFX_USUARIO / 'sfx_rules.json'
MODEL_SIZE = 'large-v3-turbo'
ESTILO_PINTADO_DEFECTO = {'font': 'Montserrat', 'style': 'Bold', 'size': 0.07, 'tracking': 1.0, 'color': (1.0, 1.0, 1.0)}
MAX_HISTORIAL = 40
CADUCA_EL = None
MESES = (tr('enero'), tr('febrero'), tr('marzo'), tr('abril'), tr('mayo'), tr('junio'), tr('julio'), tr('agosto'), tr('septiembre'), tr('octubre'), tr('noviembre'), tr('diciembre'))
def fecha_caducidad_texto():
    """'15 de septiembre de 2026', o '' si esta version no caduca.

    Se DERIVA de CADUCA_EL a proposito: la fecha estaba escrita a mano en el
    mensaje y en la etiqueta de la ventana, asi que al mover la constante los
    dos textos seguian anunciando la fecha vieja — el programa mintiendo
    sobre su propia caducidad.
    """
    if CADUCA_EL is None:
        return ''
    return tr('{dia} de {mes} de {anio}', dia=CADUCA_EL.day, mes=MESES[CADUCA_EL.month - 1], anio=CADUCA_EL.year)
MENSAJE_CADUCADA = tr('Esta es una versión de prueba y su periodo de uso terminó') + (tr(' el {fecha_caducidad_texto}', fecha_caducidad_texto=fecha_caducidad_texto()) if CADUCA_EL else '') + tr('.\n\nTus proyectos, tus subtítulos y tus ajustes siguen intactos: lo único que se desactivó es la generación de subtítulos nuevos.\n\nEscríbeme para conseguir la versión completa.')
def prueba_caducada(hoy=None):
    """True si esta compilacion ya no debe generar subtitulos.

    'hoy' existe para poder probarlo con fechas simuladas sin tocar el reloj
    de la maquina.
    """
    if CADUCA_EL is None:
        return False
    return (hoy or datetime.date.today()) > CADUCA_EL
def _base_recursos():
    """Carpeta de los archivos que acompañan al programa.

    Compilado con PyInstaller los datos se extraen a una carpeta
    temporal (sys._MEIPASS); sin compilar, es la del proyecto.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / '2_recursos'
BASE_RECURSOS = _base_recursos()
LOGO_PATH = BASE_RECURSOS / 'logo_cinecaptions.png'
LOGO_MARCA_PATH = BASE_RECURSOS / 'logo_cinema_productions.png'      # v5.3.5: «CINEMA PRODUCTIONS» (blanco, transparente): Inicio y Ajustes > Acerca de
# v5.2 (pedido: «que diga Cinema Productions en vez de By Alejandro, en todo»)
CREDIT_TEXT = 'Cinema Productions'
CREDIT_URL = ''
def guardar_log_de_error(texto: str):
    """Escribe el detalle de un error en un archivo y devuelve su ruta.

    Como la ventana se abre sin consola, si algo falla no habria donde ver el
    error. Por eso se deja este archivo, que es lo que hay que mandar cuando
    alguien reporta un problema.
    """
    try:
        # v5.2.1: además del archivo de siempre, el error va al registro (cinecaptions.log + aviso en la barra de título)
        try:
            if 'Traceback' in str(texto):
                registro.excepcion(str(texto))
            else:
                registro.error(str(texto).strip().splitlines()[0][:200] if str(texto).strip() else 'Error', 'programa', detalle=str(texto))
        except Exception:
            pass
        ruta = Path.home() / 'DaVinciSubtitles' / 'error_ventana.txt'
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding='utf-8')
        return ruta
    except Exception:
        return None
# Un error dentro de cualquier callback de la interfaz queda en error_ventana.txt
# (v3.3.2: antes iba a una consola que el compilado no tiene).
ui.AL_ERROR = guardar_log_de_error
IDIOMAS_FRECUENTES = [('Español', 'es'), ('Inglés', 'en'), ('Portugués', 'pt'), ('Ruso', 'ru'), ('Ucraniano', 'uk'), ('Árabe', 'ar'), ('Francés', 'fr'), ('Italiano', 'it'), ('Alemán', 'de'), ('Detectar automáticamente', 'auto')]
IDIOMAS_RESTO = [
    ('Afrikáans', 'af'), ('Albanés', 'sq'), ('Amárico', 'am'), ('Armenio', 'hy'),
    ('Asamés', 'as'), ('Azerí', 'az'), ('Bashkir', 'ba'), ('Bengalí', 'bn'),
    ('Bielorruso', 'be'), ('Birmano', 'my'), ('Bosnio', 'bs'), ('Bretón', 'br'),
    ('Búlgaro', 'bg'), ('Camboyano', 'km'), ('Cantonés', 'yue'), ('Catalán', 'ca'),
    ('Checo', 'cs'), ('Chino', 'zh'), ('Cingalés', 'si'), ('Coreano', 'ko'), ('Croata', 'hr'),
    ('Danés', 'da'), ('Eslovaco', 'sk'), ('Esloveno', 'sl'), ('Estonio', 'et'),
    ('Euskera', 'eu'), ('Feroés', 'fo'), ('Filipino (tagalo)', 'tl'), ('Finés', 'fi'),
    ('Galés', 'cy'), ('Gallego', 'gl'), ('Georgiano', 'ka'), ('Griego', 'el'),
    ('Guyaratí', 'gu'), ('Haitiano', 'ht'), ('Hausa', 'ha'), ('Hawaiano', 'haw'),
    ('Hebreo', 'he'), ('Hindi', 'hi'), ('Húngaro', 'hu'), ('Indonesio', 'id'),
    ('Islandés', 'is'), ('Japonés', 'ja'), ('Javanés', 'jw'), ('Canarés', 'kn'),
    ('Kazajo', 'kk'), ('Latín', 'la'), ('Letón', 'lv'), ('Lingala', 'ln'), ('Lituano', 'lt'),
    ('Luxemburgués', 'lb'), ('Macedonio', 'mk'), ('Malayalam', 'ml'), ('Malayo', 'ms'),
    ('Malgache', 'mg'), ('Maltés', 'mt'), ('Maorí', 'mi'), ('Maratí', 'mr'), ('Mongol', 'mn'),
    ('Neerlandés', 'nl'), ('Nepalí', 'ne'), ('Noruego', 'no'), ('Noruego nynorsk', 'nn'),
    ('Occitano', 'oc'), ('Panyabí', 'pa'), ('Pastún', 'ps'), ('Persa', 'fa'), ('Polaco', 'pl'),
    ('Rumano', 'ro'), ('Sánscrito', 'sa'), ('Serbio', 'sr'), ('Shona', 'sn'), ('Sindhi', 'sd'),
    ('Somalí', 'so'), ('Suajili', 'sw'), ('Sueco', 'sv'), ('Sundanés', 'su'),
    ('Tailandés', 'th'), ('Tamil', 'ta'), ('Tártaro', 'tt'), ('Telugu', 'te'),
    ('Tayiko', 'tg'), ('Tibetano', 'bo'), ('Turco', 'tr'), ('Turcomano', 'tk'), ('Urdu', 'ur'),
    ('Uzbeko', 'uz'), ('Vietnamita', 'vi'), ('Yidis', 'yi'), ('Yoruba', 'yo'),
]
IDIOMAS_RENOMBRADOS = {'Espanol': 'Español', 'Ingles': 'Inglés', 'Portugues': 'Portugués', 'Frances': 'Francés', 'Aleman': 'Alemán', 'Detectar automaticamente': 'Detectar automáticamente'}
SEPARADOR_IDIOMAS = tr('──────────  todos los demás  ──────────')
SEPARADOR_FAVORITOS = tr('──────────  ★ favoritos  ──────────')
# En Qt los separadores son de verdad (no se pueden elegir): el desplegable
# los reconoce por estos textos.
Combo.SEPARADORES.update({SEPARADOR_IDIOMAS, SEPARADOR_FAVORITOS})
def _plegar(texto):
    """Minusculas y sin tildes: el buscador de idiomas no exige acentos
    («espanol» encuentra «Español») y el orden por nombre no manda las
    vocales con tilde al final. Gemelo de sfx_studio._fold; aqui
    module-level porque tambien ordena el catalogo de destinos (v1.0.68).
    v3.3.0: por NFD y no por tabla — la tabla solo sabia las vocales del
    español, y en frances o portugues «ç», «ã», «ê» quedaban sin plegar.
    """
    import unicodedata
    texto = unicodedata.normalize('NFD', str(texto).lower())
    return ''.join((c for c in texto if unicodedata.category(c) != 'Mn'))
CODIGO_POR_NOMBRE_ES = {n: c for n, c in IDIOMAS_FRECUENTES + IDIOMAS_RESTO}
def _en_la_interfaz(pares):
    """Los (nombre, codigo) con el nombre en el idioma de la interfaz
    (v3.3.0: nombres de Unicode CLDR en locales/). En español, tal cual."""
    return [(tr('Detectar automáticamente') if c == 'auto' else nombre_idioma(c, n), c) for n, c in pares]
IDIOMAS_FRECUENTES_UI = _en_la_interfaz(IDIOMAS_FRECUENTES)
IDIOMAS_RESTO_UI = _en_la_interfaz(IDIOMAS_RESTO)
if idioma_ui() != 'es':
    IDIOMAS_RESTO_UI.sort(key=lambda par: _plegar(par[0]))
LANGUAGES = IDIOMAS_FRECUENTES_UI + IDIOMAS_RESTO_UI
LANG_NAMES = [name for name, _ in LANGUAGES]
LANG_CODE_BY_NAME = {name: code for name, code in LANGUAGES}
NOMBRE_POR_CODIGO = {code: name for name, code in LANGUAGES}
LANG_MENU = [n for n, _ in IDIOMAS_FRECUENTES_UI] + [SEPARADOR_IDIOMAS] + [n for n, _ in IDIOMAS_RESTO_UI]
def _idioma_en_frase(nombre):
    """Un nombre de idioma DENTRO de una frase (v3.3.0): en minuscula donde
    la lengua lo pide («al inglés», «em inglês», «en anglais», «in
    inglese»); en ingles y aleman llevan mayuscula («to English»)."""
    if idioma_ui() in ['en', 'de']:
        return nombre
    return nombre.lower()
def _combinacion_visible(combinacion):
    """«inferior 2» en el idioma de la interfaz (v3.3.0). Lo que se GUARDA
    sigue siendo el valor interno: casa con los nombres de clip del .drb
    («basico inferior 2»)."""
    pos, _, n = str(combinacion).partition(' ')
    pos = {'inferior': tr('inferior'), 'superior': tr('superior')}.get(pos, pos)
    return f'{pos} {n}'.strip()
def _codigo_de(valor):
    """Codigo de idioma de lo que haya guardado en preferencias: un codigo
    (v3.3.0 en adelante), un nombre en el idioma de la interfaz, o un
    nombre en español de antes (con o sin tildes, IDIOMAS_RENOMBRADOS)."""
    if valor in NOMBRE_POR_CODIGO:
        return valor
    if valor in LANG_CODE_BY_NAME:
        return LANG_CODE_BY_NAME[valor]
    return CODIGO_POR_NOMBRE_ES.get(IDIOMAS_RENOMBRADOS.get(valor, valor))
ACCENT = ui.ACCENT
ACCENT_HOVER = ui.ACCENT_HOVER
BG_COLOR = ui.BG_COLOR
CARD_COLOR = ui.CARD_COLOR
BORDER_COLOR = ui.BORDER_COLOR
TEXT_COLOR = ui.TEXT_COLOR
TEXT_MUTED = ui.TEXT_MUTED
FS_TITULO = 20
FS_SECCION = 15
FS_NORMAL = 13
FS_MENOR = 12
PAD_XS = 4
PAD_SM = 8
PAD_MD = 12
PAD_LG = 16
PAD_SANGRIA = 32
def fuente(tam=FS_NORMAL, negrita=False, **kw):
    """La letra de la casa, en pixeles (ver qt_kit.fuente; acepta peso=)."""
    return ui.fuente(tam, negrita, **kw)
_ICONO_CACHE = {}
def _icono_estrella(lado=18, color='#FFFFFF', n=3.0):
    """Estrella de cuatro puntas, blanca y plana (estilo Gemini).

    Es una astroide: x = R*|cos t|^n, y = R*|sin t|^n. Con n=3 quedan las
    puntas afiladas y los lados concavos. Con n=2 seria un rombo.
    """
    clave = ('estrella', lado, color, n)
    if clave in _ICONO_CACHE:
        return _ICONO_CACHE[clave]
    def dibujar(p, s):
        centro = s / 2
        radio = centro * 0.98
        camino = QPainterPath()
        for k in range(361):
            t = 2 * math.pi * k / 360
            cos_t, sin_t = (math.cos(t), math.sin(t))
            x = centro + radio * math.copysign(abs(cos_t) ** n, cos_t)
            y = centro + radio * math.copysign(abs(sin_t) ** n, sin_t)
            if k == 0:
                camino.moveTo(x, y)
            else:
                camino.lineTo(x, y)
        camino.closeSubpath()
        p.fillPath(camino, QColor(color))
    try:
        icono = ui.icono_dibujado(dibujar, lado)
    except Exception:
        icono = None
    _ICONO_CACHE[clave] = icono
    return icono
def _icono_carpeta(lado=18, color='#FFFFFF'):
    """Carpeta plana, para el boton de proyectos guardados."""
    clave = ('carpeta', lado, color)
    if clave in _ICONO_CACHE:
        return _ICONO_CACHE[clave]
    def dibujar(p, s):
        r = s * 0.06
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(s * 0.08, s * 0.2, s * 0.40, s * 0.14), r, r)
        p.drawRoundedRect(QRectF(s * 0.08, s * 0.28, s * 0.84, s * 0.52), r * 1.6, r * 1.6)
    try:
        icono = ui.icono_dibujado(dibujar, lado)
    except Exception:
        icono = None
    _ICONO_CACHE[clave] = icono
    return icono
_FAMILIA_CACHE = None
def familia_legible():
    """Familia de letra para el panel de palabras, segun el sistema.

    'Segoe UI' solo existe en Windows: pedirla en una Mac hace caer a una
    fuente con serifas que se lee peor y desalinea el panel. Se pregunta que
    hay instalado y se usa la primera de la lista que exista.
    """
    global _FAMILIA_CACHE
    if _FAMILIA_CACHE:
        return _FAMILIA_CACHE
    preferidas = ('Segoe UI', 'SF Pro Text', 'Helvetica Neue', 'Inter', 'Roboto', 'DejaVu Sans', 'Arial')
    _FAMILIA_CACHE = ui.familia_ui()
    try:
        disponibles = {f.lower() for f in QFontDatabase.families()}
        for nombre in preferidas:
            if nombre.lower() in disponibles:
                _FAMILIA_CACHE = nombre
                break
    except Exception:
        pass
    return _FAMILIA_CACHE
def ruta_marcas(project_name):
    return st.SHARED_FOLDER / f'{project_name}.marcas.json'
def guardar_marcas(project_name, palabras, roles):
    """Deja en disco las palabras (ya corregidas) y sus marcas.

    Se guardan las palabras completas — no solo los roles — porque el usuario
    puede haber corregido texto o borrado alguna, y al volver queremos ver
    exactamente lo que dejo, no la transcripcion cruda de Whisper otra vez.
    """
    ruta = ruta_marcas(project_name)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # atómico y con copia del guardado anterior: un corte a mitad del autoguardado ya no puede dejar el trabajo del usuario a medias
    archivos_seguros.escribir_json(ruta, {'project': project_name, 'words': palabras, 'roles': roles, 'guardado_en': time.time()}, respaldo=True, indent=2)
    return ruta
def cargar_marcas(project_name):
    """Devuelve (palabras, roles) de lo guardado, o None si no hay nada
    utilizable para ese proyecto."""
    ruta = ruta_marcas(project_name)
    if not ruta.exists():
        return
    for origen in (ruta, ruta.with_name(ruta.name + '.bak')):          # si el principal está roto, la copia del guardado anterior
        try:
            datos = json.loads(origen.read_text(encoding='utf-8'))
            palabras = datos['words']
            roles = datos['roles']
        except Exception:
            continue
        if palabras and len(palabras) == len(roles):
            return (palabras, roles)
    return None
def _titulo(texto, tam=FS_SECCION, color='#FFFFFF'):
    return Etiqueta(texto, tam=tam, negrita=True, color=color)
def _nota(texto, tam=FS_MENOR, color=TEXT_MUTED, envolver=True):
    return Etiqueta(texto, tam=tam, color=color, envolver=envolver)
def _capa_dialogo(dlg, margenes=(18, 16, 18, 16), espacio=8):
    capa = QVBoxLayout(dlg)
    capa.setContentsMargins(*margenes)
    capa.setSpacing(espacio)
    return capa
# ---------------------------------------------------------------------------
# Vistas previas APROXIMADAS (decision del rediseño: «dibujarlas y marcarlas
# aprox.»). En la v1.0.26 se retiraron las miniaturas dibujadas porque no
# coincidian con el render; aqui vuelven con su etiqueta «aprox.» y, si el pack
# trae miniatura real, se usa esa. Salen de los mismos estilos que mide la app
# (plantillas.estilos_para_medir: fuente, peso, tamaño y color del .drb).
_CACHE_ESTILOS = {}
TEXTOS_MUESTRA = (tr('Cómo'), tr('DUPLICAMOS'), tr('las ventas'))
_ESTILO_DEFECTO = {'context': {'font': 'Montserrat', 'style': 'Medium', 'size': 0.04, 'color': [1.0, 1.0, 1.0]},
                   'main': {'font': 'Montserrat', 'style': 'Black', 'size': 0.075, 'color': [0.961, 0.722, 0.294]},
                   'complement': {'font': 'Montserrat', 'style': 'Regular', 'size': 0.045, 'color': [0.702, 0.533, 1.0]},
                   'base': {'font': 'Montserrat', 'style': 'SemiBold', 'size': 0.05, 'color': [1.0, 1.0, 1.0]}}
def estilos_de_pack(nombre):
    """{formato: {'rol|n': estilo}} del pack, memorizado (leer el .drb cuesta)."""
    if nombre not in _CACHE_ESTILOS:
        try:
            _CACHE_ESTILOS[nombre] = plantillas.estilos_para_medir(nombre) or {}
        except Exception:
            _CACHE_ESTILOS[nombre] = {}
    return _CACHE_ESTILOS[nombre]
def _hex_de(color, defecto='#FFFFFF'):
    try:
        return '#%02X%02X%02X' % tuple(max(0, min(255, int(round(float(c) * 255)))) for c in list(color)[:3])
    except Exception:
        return defecto
def _estilo_rol(estilos, rol):
    """El estilo de ese rol en el set mas bajo que lo traiga."""
    mejor = None
    for clave, est in (estilos or {}).items():
        r, _, n = str(clave).partition('|')
        if r != rol:
            continue
        try:
            n = int(n)
        except ValueError:
            n = 99
        if mejor is None or n < mejor[0]:
            mejor = (n, est)
    return mejor[1] if mejor else None
def _estilo_rol_n(estilos, rol, n):
    """El estilo de ese rol en la variante n (si no la trae, el del set mas bajo)."""
    if n:
        e = (estilos or {}).get(f'{rol}|{n}')
        if e:
            return e
    return _estilo_rol(estilos, rol)
_ESTILO_FIJO = [None]
def estilo_fijo():
    """La variante (1..n) que el usuario dejo fija en «Estilo del bloque» (Proyecto); 0 = ir alternando.
    Sin esa tarjeta (COMPOSICION_VISIBLE False) nadie puede cambiarla ni verla: un valor viejo guardado no puede mandar a escondidas."""
    if not COMPOSICION_VISIBLE:
        return 0
    if _ESTILO_FIJO[0] is None:
        try:
            import ajustes_ui
            _ESTILO_FIJO[0] = max(0, int(ajustes_ui.leer_prefs().get('estilo_fijo') or 0))
        except Exception:
            _ESTILO_FIJO[0] = 0
    return _ESTILO_FIJO[0]
def resumen_composicion(v):
    """«alineación AUTO, altura -5%, horizontal +1%»: lo que el ajuste fino cambia respecto a la posición exacta del estilo ('' si nada)."""
    v = composicion.valida(v)
    cosas = []
    if v['layout'] != 'cc':
        cosas.append(tr('alineación AUTO') if v['layout'] == 'auto' else tr('alineación {c}', c=v['layout'].upper()))
    if v['altura']:
        cosas.append(tr('altura {v}%', v=f"{v['altura'] * 100:+.0f}"))
    if v['horizontal']:
        cosas.append(tr('horizontal {v}%', v=f"{v['horizontal'] * 100:+.0f}"))
    return ', '.join(cosas)
def poner_estilo_fijo(n):
    _ESTILO_FIJO[0] = max(0, int(n or 0))
    try:
        import ajustes_ui
        ajustes_ui.guardar_prefs({'estilo_fijo': _ESTILO_FIJO[0]})
    except Exception:
        pass
def lineas_de_vista(nombre_pack, formato=None, textos=None, roles=('context', 'main', 'complement'), n=None, color_principal=None):
    """Las lineas para un MarcoVista con el estilo del pack (aprox.). 'n' = la variante a dibujar (None = la fija del usuario, o la primera)."""
    if n is None and estilo_fijo():
        n = estilo_fijo()
    textos = list(textos or TEXTOS_MUESTRA)
    por_formato = estilos_de_pack(nombre_pack) if nombre_pack not in ('media_pool', '', None) else {}
    estilos = por_formato.get(formato) if formato in por_formato else next(iter(por_formato.values()), {})
    principal = _estilo_rol_n(estilos, 'main', n) or _ESTILO_DEFECTO['main']
    base_main = float(principal.get('size') or 0.075) or 0.075
    lineas = []
    roles_pack = plantillas.roles_de_variante(nombre_pack, formato, n or 1)
    for texto, rol in zip(textos, roles):
        if not texto:
            continue
        est = _estilo_rol_n(estilos, rol, n) or _ESTILO_DEFECTO.get(rol, _ESTILO_DEFECTO['context'])
        nuevo = roles_pack.get(rol)
        if nuevo:
            # pack nuevo: tipografia exacta de cada palabra, mayusculas y lineas pegadas
            tm = (roles_pack.get('main') or nuevo).get('tam') or 0.19
            f1, f2 = nuevo['f1'], nuevo['f2']
            lineas.append((texto, {'familia': f1[0], 'peso': f1[1], 'italica': 'italic' in str(f1[1]).lower(),
                                   'segundo': {'familia': f2[0], 'peso': f2[1]} if f2 != f1 else None,
                                   'mayus': nuevo.get('mayus'), 'pegado': True, 'degradado': rol == 'main',
                                   'tam': max(0.07, min(0.3, 0.26 * float(nuevo['tam']) / float(tm))),
                                   'color': (_hex_de(color_principal, '#FFFFFF') if (rol == 'main' and color_principal) else str(nuevo.get('color') or '#FFFFFF'))}))
            continue
        rel = float(est.get('size') or base_main) / base_main
        color = _hex_de(est.get('color'), '#FFFFFF')
        if rol == 'main' and color_principal:
            color = _hex_de(color_principal, color)
        lineas.append((texto, {'familia': est.get('font') or 'Montserrat', 'peso': est.get('style') or 'Regular',
                               'tam': max(0.08, min(0.3, 0.26 * rel)), 'color': color}))
    return lineas
def _correr_en_hilo(widget, trabajo, al_terminar, baja=False):
    """Corre `trabajo()` en un hilo y llama `al_terminar(resultado, error)`
    en el hilo de la interfaz (ver qt_kit.correr_en_hilo). La red de las
    licencias no puede congelar la ventana (el «no responde» de Windows)."""
    correr_en_hilo(widget, trabajo, al_terminar, baja=baja)
