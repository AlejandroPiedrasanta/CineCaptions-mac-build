# CineCaptions · By Cinema Productions
# 1_codigo/ejemplos_estilo.py — los 48 ejemplos de «Crea tu estilo» (posición, tipografía y colores; 18 con un principal de Amro.Films Captions), su vista y cómo se vuelven un pack o un timeline de Resolve.
"""
Cada ejemplo es una combinación de TRES cosas:

  * posición     : dónde cae el grupo de tres líneas (arriba · tercio alto · centro · tercio bajo · abajo),
  * estilo       : la tipografía y las proporciones de arriba / PRINCIPAL / abajo (Impacto, Editorial, Moderno, Pesado, Fino, TikTok),
  * colores      : el del texto principal (el que lleva el brillo de Luxe Shine) y el de las líneas de arriba y abajo.

Con ellos el programa hace tres cosas:

  * miniatura(ej)      : la imagen de muestra (un fotograma vertical 9:16 pintado con las mismas fuentes y posiciones) para la galería;
  * crear_pack(...)    : hasta 3 ejemplos elegidos → un pack de verdad en la carpeta de packs (variantes 1, 2 y 3, con los nombres
                         principal / arriba / abajo / simple que el programa necesita), usando SOLO los macros reales del Luxe Title Pack;
  * config_resolve(ej) : lo que el taller de Resolve necesita para poner el ejemplo en un timeline con los efectos reales
                         Luxe Shine (principal) y Luxe Slide (arriba y abajo).

Las tipografías son las que el programa ya trae e instala (Montserrat, Inter, Poppins, DM Serif Text).

Los 18 últimos ejemplos llevan de PRINCIPAL un preset de «Amro.Films Captions» (Highlight, Underline, Fire, Strike); arriba y abajo siguen siendo
SIEMPRE Luxe Slide. Su comp se copia tal cual de «Amro principales.drb» (2_recursos/guia_estilo/). Cada ejemplo tiene una vista REAL, renderizada por
Resolve (2_recursos/guia_estilo/vistas/ej_NN.jpg, hechas con construir_guia.py); si falta se pinta una aproximación.
"""
import json
import re
import zlib
from pathlib import Path

# ------------------------------------------------------------------ los ingredientes
# clave: (nombre, y del CENTRO del grupo de tres líneas; 1 = arriba del todo)
POSICIONES = {
    'superior': ('Arriba', 0.80),
    'alto': ('Tercio alto', 0.66),
    'centro': ('Centro', 0.50),
    'bajo': ('Tercio bajo', 0.34),
    'inferior': ('Abajo', 0.22),
}
ORDEN_POSICIONES = ('superior', 'alto', 'centro', 'bajo', 'inferior')

# tipografía de (arriba, principal, abajo), tamaños (fracción del alto /3 como el Size de Fusion), espaciado, mayúsculas y entrada
ESTILOS = {
    'impacto': dict(nombre='Impacto', fuentes=(('Inter 18pt', 'Light'), ('Montserrat', 'Black'), ('Inter 18pt', 'Light')),
                    tam=(0.128, 0.192, 0.128), esp=(1.02, 0.985, 1.02), mayus=(True, True, True), entrada='pop'),
    'editorial': dict(nombre='Editorial', fuentes=(('Poppins', 'Regular'), ('DM Serif Text', 'Italic'), ('Poppins', 'Regular')),
                      tam=(0.096, 0.262, 0.096), esp=(1.20, 0.99, 1.20), mayus=(True, False, True), entrada='abre'),
    'moderno': dict(nombre='Moderno', fuentes=(('Poppins', 'Regular'), ('Poppins', 'Bold'), ('Poppins', 'Regular')),
                    tam=(0.10, 0.20, 0.10), esp=(1.06, 0.99, 1.06), mayus=(False, False, False), entrada='sube'),
    'pesado': dict(nombre='Pesado', fuentes=(('Montserrat', 'Bold'), ('Montserrat', 'Black'), ('Montserrat', 'Bold')),
                   tam=(0.11, 0.21, 0.11), esp=(1.02, 0.98, 1.02), mayus=(True, True, True), entrada='pop'),
    'fino': dict(nombre='Fino', fuentes=(('Inter 18pt', 'Light'), ('Montserrat', 'Medium'), ('Inter 18pt', 'Light')),
                 tam=(0.09, 0.17, 0.09), esp=(1.30, 1.06, 1.30), mayus=(True, True, True), entrada='abre'),
    'tiktok': dict(nombre='TikTok', fuentes=(('Montserrat', 'SemiBold'), ('Montserrat', 'ExtraBold'), ('Montserrat', 'SemiBold')),
                   tam=(0.085, 0.24, 0.085), esp=(1.04, 0.97, 1.04), mayus=(False, True, False), entrada='sube'),
}
COLORES = {
    'blanco': ('Blanco', (1.0, 1.0, 1.0)), 'crema': ('Crema', (0.98, 0.95, 0.88)), 'oro': ('Oro', (1.0, 0.80, 0.22)),
    'cian': ('Cian', (0.35, 0.92, 1.0)), 'rosa': ('Rosa', (1.0, 0.36, 0.62)), 'lima': ('Lima', (0.62, 1.0, 0.30)),
    'naranja': ('Naranja', (1.0, 0.55, 0.15)), 'rojo': ('Rojo', (1.0, 0.28, 0.28)), 'violeta': ('Violeta', (0.70, 0.50, 1.0)),
    'amarillo': ('Amarillo', (1.0, 0.93, 0.20)), 'menta': ('Menta', (0.40, 1.0, 0.80)),
}

# (posición, estilo, color del principal, color de arriba/abajo): 30 ejemplos, ninguno repite la misma mezcla
_LISTA = (
    ('superior', 'impacto', 'blanco', 'blanco'), ('superior', 'impacto', 'oro', 'crema'), ('alto', 'impacto', 'cian', 'blanco'),
    ('centro', 'impacto', 'rojo', 'blanco'), ('bajo', 'impacto', 'lima', 'blanco'), ('inferior', 'impacto', 'naranja', 'crema'),
    ('superior', 'editorial', 'crema', 'crema'), ('alto', 'editorial', 'rosa', 'crema'), ('centro', 'editorial', 'oro', 'blanco'),
    ('bajo', 'editorial', 'blanco', 'crema'), ('inferior', 'editorial', 'violeta', 'blanco'), ('centro', 'editorial', 'menta', 'crema'),
    ('superior', 'moderno', 'blanco', 'blanco'), ('alto', 'moderno', 'cian', 'blanco'), ('centro', 'moderno', 'amarillo', 'blanco'),
    ('bajo', 'moderno', 'rosa', 'blanco'), ('inferior', 'moderno', 'lima', 'blanco'), ('alto', 'moderno', 'naranja', 'crema'),
    ('centro', 'pesado', 'blanco', 'amarillo'), ('superior', 'pesado', 'amarillo', 'blanco'), ('bajo', 'pesado', 'rojo', 'blanco'),
    ('inferior', 'pesado', 'violeta', 'crema'), ('superior', 'fino', 'blanco', 'blanco'), ('centro', 'fino', 'oro', 'crema'),
    ('inferior', 'fino', 'menta', 'blanco'), ('alto', 'fino', 'rosa', 'crema'), ('bajo', 'tiktok', 'amarillo', 'blanco'),
    ('inferior', 'tiktok', 'blanco', 'amarillo'), ('centro', 'tiktok', 'cian', 'blanco'), ('superior', 'tiktok', 'lima', 'blanco'),
)


# el principal de Amro.Films Captions: (clave, efecto, color de la muestra, set del .drb «Amro principales»: 1 Highlight naranja, 2 Highlight rosa,
# 3 Underline verde, 4 Underline amarillo, 5 Fire, 6 Strike rojo). Arriba y abajo: Luxe Slide en Poppins Regular blanco, a distancia fija.
LOOKS_AMRO = (('highlight_naranja', 'Highlight', 'naranja', 1), ('highlight_rosa', 'Highlight', 'rosa', 2), ('underline_verde', 'Underline', 'lima', 3),
              ('underline_amarillo', 'Underline', 'amarillo', 4), ('fire', 'Fire', 'naranja', 5), ('strike_rojo', 'Strike', 'rojo', 6))
POSICIONES_AMRO = ('superior', 'centro', 'inferior')
ESTILOS['amro'] = dict(nombre='Amro', fuentes=(('Poppins', 'Regular'), ('Inter', 'Black'), ('Poppins', 'Regular')), tam=(0.10, 0.17, 0.10),
                       esp=(1.06, 1.0, 1.06), mayus=(False, True, False), entrada='pop', rel=(0.0836, 0.0847))


def _construir():
    lista = []
    for k, (pos, estilo, principal, resto) in enumerate(_LISTA, 1):
        lista.append({
            'id': k, 'familia': 'luxe',
            'nombre': f"{ESTILOS[estilo]['nombre']} {COLORES[principal][0].lower()}",
            'posicion': pos, 'estilo': estilo, 'principal': principal, 'resto': resto,
        })
    k = len(lista)
    for clave, efecto, color, numero in LOOKS_AMRO:
        for pos in POSICIONES_AMRO:
            k += 1
            lista.append({'id': k, 'familia': 'amro', 'nombre': f'Amro {efecto}' + ('' if efecto == 'Fire' else f' {color}'), 'posicion': pos,
                          'estilo': 'amro', 'principal': color, 'resto': 'blanco', 'efecto': efecto, 'set': numero})
    return lista


EJEMPLOS = _construir()
MAX_ELEGIDOS = 3            # un pack lleva como mucho 3 variantes (principal, principal 2, principal 3)
TEXTOS_MUESTRA = ('así se ve', 'TU ESTILO', 'en tu video')
# los segundos del ejemplo de los que sale su vista real: la ANIMACIÓN de entrada (varios fotogramas) y el último, ya con la entrada terminada
CUADROS_VISTA_S = (0.05, 0.12, 0.2, 0.3, 0.45, 0.7, 1.3)
# lo que el generador de packs llama cada rol, y el nombre que el PROGRAMA lee (la estructura de nombres)
NOMBRES_ROL = {'context': 'arriba', 'main': 'principal', 'complement': 'abajo'}


def por_id(k):
    return next((e for e in EJEMPLOS if e['id'] == int(k)), None)


def etiqueta_posicion(ej):
    return POSICIONES[ej['posicion']][0]


def etiqueta_estilo(clave):
    """El nombre del estilo, traducido (Impacto, Editorial, Moderno, Pesado, Fino, TikTok)."""
    from i18n import tr
    return 'Amro' if clave == 'amro' else tr(ESTILOS[clave]['nombre'])


def nombre_visible(ej):
    """«Impacto cian» en el idioma de la app (el nombre guardado en el ejemplo es el español)."""
    from i18n import tr
    if ej.get('familia') == 'amro':
        return f"Amro {ej['efecto']}" + ('' if ej['efecto'] == 'Fire' else f" {tr(COLORES[ej['principal']][0].lower())}")
    return f"{etiqueta_estilo(ej['estilo'])} {tr(COLORES[ej['principal']][0].lower())}"


def y_grupo(ej):
    return POSICIONES[ej['posicion']][1]


def color_de(clave):
    return COLORES[clave][1]


def hexa(c):
    return '#%02X%02X%02X' % tuple(int(round(v * 255)) for v in c[:3])


def desplazamiento(tam_main, tam_otro):
    """Cuánto se separa (fracción del alto) el centro de la línea de arriba/abajo del centro del principal: la MISMA fórmula que
    generar_comps.y_relativa (las líneas pegadas, como en el ejemplo)."""
    return 0.36 * (640.0 / 1920.0) * (tam_main + tam_otro) + 0.010


def lineas(ej):
    """[(rol, fuente, estilo, tamaño, color, mayúsculas, espaciado, y del centro)] de arriba a abajo."""
    e = ESTILOS[ej['estilo']]
    tm = e['tam'][1]
    yg = y_grupo(ej)
    col_main, col_resto = color_de(ej['principal']), color_de(ej['resto'])
    salida = []
    for i, rol in enumerate(('context', 'main', 'complement')):
        familia, peso = e['fuentes'][i]
        if rol == 'main':
            y = yg
        elif rol == 'context':
            y = yg + (e['rel'][0] if e.get('rel') else desplazamiento(tm, e['tam'][0]))
        else:
            y = yg - (e['rel'][1] if e.get('rel') else desplazamiento(tm, e['tam'][2]))
        salida.append((rol, familia, peso, e['tam'][i], col_main if rol == 'main' else col_resto, e['mayus'][i], e['esp'][i], y))
    return salida


# ------------------------------------------------------------------ la imagen de muestra
_CACHE_MINI = {}


def _fuente(familia, peso, px):
    from PySide6.QtGui import QFont, QFontDatabase
    try:
        f = QFontDatabase.font(familia, peso, 12)
        if not f.family():
            raise ValueError
    except Exception:
        f = QFont(familia)
    f.setPixelSize(max(6, int(round(px))))
    return f


def dibujar(p, rect, ej, textos=TEXTOS_MUESTRA, escala_texto=1.3):
    """Pinta el ejemplo dentro de 'rect' (un fotograma vertical). La posición es la real; el tamaño de las letras va un poco
    ampliado (escala_texto) para que se lea en una miniatura."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import (QBrush, QColor, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    ancho, alto = rect.width(), rect.height()
    # el «video»: un degradado oscuro con una luz suave, para que se vea cómo contrasta cada color
    fondo = QLinearGradient(rect.topLeft(), rect.bottomRight())
    fondo.setColorAt(0.0, QColor('#27324A'))
    fondo.setColorAt(0.55, QColor('#141B2B'))
    fondo.setColorAt(1.0, QColor('#0B0F19'))
    p.fillRect(rect, QBrush(fondo))
    luz = QRadialGradient(QPointF(rect.center().x(), rect.top() + alto * 0.38), alto * 0.5)
    luz.setColorAt(0.0, QColor(120, 150, 210, 60))
    luz.setColorAt(1.0, QColor(120, 150, 210, 0))
    p.fillRect(rect, QBrush(luz))
    for (rol, familia, peso, tam, color, mayus, esp, y), texto in zip(lineas(ej), textos):
        px = tam * alto / 3.0 * escala_texto
        fuente = _fuente(familia, peso, px)
        if esp and abs(esp - 1.0) > 0.01:
            from PySide6.QtGui import QFont
            fuente.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100.0 * esp)
        txt = texto.upper() if mayus else texto
        if rol == 'main':
            txt = texto.upper() if mayus else texto.title()
        m = QFontMetricsF(fuente)
        w = m.horizontalAdvance(txt)
        if w > ancho * 0.92:                         # lo largo se encoge, como hace el pack con el ajuste automático
            fuente.setPixelSize(max(6, int(fuente.pixelSize() * ancho * 0.92 / w)))
            m = QFontMetricsF(fuente)
            w = m.horizontalAdvance(txt)
        yg = y_grupo(ej)
        cy = rect.top() + (1.0 - (yg + (y - yg) * escala_texto)) * alto      # las líneas se separan igual que las letras crecen
        base = QPointF(rect.left() + (ancho - w) / 2.0, cy + (m.ascent() - m.descent()) / 2.0)
        ruta = QPainterPath()
        ruta.addText(base, fuente, txt)
        c = QColor.fromRgbF(*color)
        sombra = QPainterPath(ruta)
        sombra.translate(0.0, max(1.0, px * 0.05))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawPath(sombra)
        if rol == 'main':                            # el brillo de Luxe Shine
            for ancho_halo, a in ((px * 0.34, 28), (px * 0.18, 46)):
                p.setPen(QPen(QColor(c.red(), c.green(), c.blue(), a), ancho_halo, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(ruta)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawPath(ruta)
    p.restore()


CARPETA_VISTAS = Path.home() / 'DaVinciSubtitles' / 'plantillas_cache' / 'guia_estilo' / 'vistas'     # las que hace el Resolve de este equipo (vistas_guia.py)


def carpeta_recursos():
    """La carpeta guia_estilo del programa (el .drb de la guía, el de los principales de Amro y construir_guia.py)."""
    from sfx_rules import base_recursos
    return Path(base_recursos()) / 'guia_estilo'


def rutas_vista(ej):
    """Los fotogramas REALES (renderizados por Resolve) de la animación del ejemplo, en orden; [] si todavía no se hicieron. Manda lo que hizo el
    Resolve de este equipo; si no, las de fábrica."""
    try:
        for base in (CARPETA_VISTAS, carpeta_recursos() / 'vistas'):
            lista = [base / f"ej_{int(ej['id']):02d}_{k}.jpg" for k in range(len(CUADROS_VISTA_S))]
            lista = [p for p in lista if p.is_file()]
            if lista:
                return lista
    except Exception:
        pass
    return []


def ruta_video(ej):
    """El clip de 4 s con la animación COMPLETA del ejemplo (entrada, texto y salida; sobre negro) o None. Manda el que hizo el Resolve de este equipo; si no, el de fábrica."""
    try:
        for base in (CARPETA_VISTAS, carpeta_recursos() / 'vistas'):
            ruta = base / f"ej_{int(ej['id']):02d}.mp4"
            if ruta.is_file() and ruta.stat().st_size > 500:
                return ruta
    except Exception:
        pass
    return None


def ruta_vista(ej):
    """La vista REAL estática (el último fotograma, con la entrada terminada) o None."""
    lista = rutas_vista(ej)
    return lista[-1] if lista else None


def olvidar_miniaturas():
    """Tras renderizar vistas nuevas: las miniaturas con caché se vuelven a leer."""
    _CACHE_MINI.clear()


def ruta_amro():
    """El .drb con los textos principales de Amro.Films Captions (sets 1..6)."""
    return carpeta_recursos() / 'Amro principales.drb'


def miniatura(ej, ancho=150, dpr=1.0):
    """La imagen del ejemplo como QPixmap (9:16), con caché: la vista real de Resolve si existe; si no, una aproximación pintada."""
    clave = (ej['id'], int(ancho), round(float(dpr), 2))
    pm = _CACHE_MINI.get(clave)
    if pm is None:
        real = ruta_vista(ej)
        if real is not None:
            from PySide6.QtCore import QRectF, Qt
            from PySide6.QtGui import QImage, QPainter, QPainterPath, QPixmap
            img = QImage(str(real))
            if not img.isNull():
                alto = int(round(ancho * 16 / 9))
                pm = QPixmap(int(ancho * dpr), int(alto * dpr))
                pm.setDevicePixelRatio(dpr)
                pm.fill(Qt.GlobalColor.transparent)
                p = QPainter(pm)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                recorte = QPainterPath()
                recorte.addRoundedRect(QRectF(0, 0, ancho, alto), 12, 12)
                p.setClipPath(recorte)
                p.drawImage(QRectF(0, 0, ancho, alto), img)
                p.end()
                _CACHE_MINI[clave] = pm
                return pm
    if pm is None:
        from PySide6.QtCore import QRectF, Qt
        from PySide6.QtGui import QPainter, QPainterPath, QPixmap
        alto = int(round(ancho * 16 / 9))
        pm = QPixmap(int(ancho * dpr), int(alto * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        recorte = QPainterPath()
        recorte.addRoundedRect(QRectF(0, 0, ancho, alto), 12, 12)
        p.setClipPath(recorte)
        dibujar(p, QRectF(0, 0, ancho, alto), ej)
        p.end()
        _CACHE_MINI[clave] = pm
    return pm


# ------------------------------------------------------------------ hacia el generador de packs
def combinacion(ej):
    """El diccionario que entiende generador_packs/generar_comps.py (como COMBINACIONES[n])."""
    e = ESTILOS[ej['estilo']]
    col_main, col_resto = color_de(ej['principal']), color_de(ej['resto'])

    def rol(i, color, retardo):
        return dict(f1=e['fuentes'][i], f2=e['fuentes'][i], tam=e['tam'][i], esp=e['esp'][i], mayus=e['mayus'][i], color=color, retardo=retardo)
    combo = {'nombre': ej['nombre'], 'context': rol(0, col_resto, 0), 'main': rol(1, col_main, 2), 'complement': rol(2, col_resto, 4),
             'entrada': e['entrada'], 'luxe': True, 'mayus_real': True}
    if ej.get('familia') == 'amro':
        combo['rel'] = e['rel']
        combo['principal_drb'] = {'drb': str(ruta_amro()), 'clip': 'principal' if ej['set'] == 1 else f"principal {ej['set']}"}
    return combo


def _slug(texto):
    s = re.sub(r'[^A-Za-z0-9]+', '_', str(texto)).strip('_')
    return s[:40] or 'estilo'


def crear_pack(nombre, ids, carpeta_packs=None):
    """Arma un pack de hasta 3 variantes con los ejemplos 'ids' (el 1.º es la variante 1, etc.).

    Usa SOLO los macros reales del Luxe Title Pack (Luxe Shine el principal, o un preset de Amro.Films Captions en los ejemplos de Amro; Luxe
    Slide arriba y abajo) y los nombres que el programa
    lee (principal · arriba · abajo · simple, y «2» y «3» para las variantes). Devuelve (nombre, carpeta).
    """
    import sys
    import plantillas
    ids = [int(i) for i in ids][:MAX_ELEGIDOS]
    elegidos = [por_id(i) for i in ids]
    if not elegidos or any(e is None for e in elegidos):
        raise ValueError('elige entre 1 y 3 ejemplos')
    nombre = (nombre or 'Mi estilo')[:40].strip() or 'Mi estilo'
    incluidas = plantillas.carpeta_incluida()
    if incluidas is None:
        raise RuntimeError('no encuentro los packs incluidos')
    contenedor = incluidas / 'Viral Superior' / 'Viral Superior vertical.drb'
    if not contenedor.is_file():
        raise RuntimeError(f'falta {contenedor.name}')
    generador = incluidas.parent / 'generador_packs'
    if str(generador) not in sys.path:
        sys.path.insert(0, str(generador))
    import generar_comps as g
    import construir_pack as C
    base = Path(carpeta_packs) if carpeta_packs else plantillas.carpeta_de_packs()
    carpeta = base / plantillas.nombre_seguro(nombre)           # la misma carpeta que plantillas.buscar_pack(nombre) mira
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f'{nombre} vertical.drb'
    guardadas = {k: g.COMBINACIONES[k] for k in (1, 2, 3)}
    try:
        for k, ej in enumerate(elegidos, 1):
            g.COMBINACIONES[k] = combinacion(ej)
        C.construir(str(contenedor), str(destino), f'{nombre} vertical', 'superior', tuple(range(1, len(elegidos) + 1)),
                    y_por_comb={k: y_grupo(ej) for k, ej in enumerate(elegidos, 1)}, nombres_nuevos=True)
    finally:
        g.COMBINACIONES.update(guardadas)
    try:
        import packs_drt
        pos = packs_drt.posiciones_de_drb(str(destino))
        (carpeta / f'{nombre} vertical.posiciones.json').write_text(
            json.dumps({'origen': destino.name, 'clips': {k: list(v) for k, v in pos.items()}}, indent=1), encoding='utf-8')
    except Exception:
        pass
    (carpeta / 'pack.json').write_text(json.dumps({'version': 2, 'nombre': nombre, 'formatos': {'v': {'drb': destino.name}}},
                                                  ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        plantillas.invalidar_packs()
    except Exception:
        pass
    return nombre, carpeta


# ------------------------------------------------------------------ hacia Resolve (el taller que corre dentro de Resolve)
def config_resolve(ej, alto=1920):
    """Los tres bloques del ejemplo para el taller de Resolve: [{rol, nombre, preset, texto, font, style, size, color, tracking, tilt}].
    preset es el efecto REAL del Luxe Title Pack: Luxe Shine para el principal, Luxe Slide para arriba y abajo. tilt = píxeles desde el
    centro del cuadro (Y arriba), como en el Inspector de Resolve."""
    salida = []
    for (rol, familia, peso, tam, color, mayus, esp, y), texto in zip(lineas(ej), TEXTOS_MUESTRA):
        txt = texto.upper() if mayus else texto
        if rol == 'main' and not mayus:
            txt = texto.title()
        bloque = {'rol': NOMBRES_ROL[rol], 'preset': 'Luxe Shine' if rol == 'main' else 'Luxe Slide', 'texto': txt, 'font': familia,
                  'style': peso, 'size': tam, 'color': list(color), 'tracking': esp, 'tilt': round((y - 0.5) * alto, 1)}
        if rol == 'main' and ej.get('familia') == 'amro':      # el preset de Amro trae su tipografía, color y tamaño: solo se cambia el texto
            bloque.update(preset='Amro', clip_amro='principal' if ej['set'] == 1 else f"principal {ej['set']}", efecto=ej['efecto'], texto='ESTILO')   # una sola palabra: Fire se ajusta al ancho solo y recorta lo largo
        salida.append(bloque)
    return salida


def datos_guia(drb=None, nombre='Crea tu estilo', segundos=4, amro=None, fotos=None, solo=None):
    """Todo lo que construir_guia.py (dentro de Resolve) necesita: los ejemplos con sus tres bloques, el .drb con los macros Luxe y el de los
    principales de Amro. fotos: carpeta donde sacar la vista real de cada ejemplo (solo al generar las vistas que viajan con el programa)."""
    ejemplos = []
    for e in EJEMPLOS:
        if solo is not None and e['id'] not in solo:
            continue
        if e.get('familia') == 'amro':
            nota = ('%s · Amro %s · el principal es un preset de Amro.Films Captions. Para usarlo: ponle a sus 3 clips los nombres principal, arriba y abajo '
                    '(con 2 o 3 al final si es tu 2.ª o 3.ª variante).') % (etiqueta_posicion(e), e['efecto'])
        else:
            nota = ('%s · %s · principal en %s. Para usarlo: ponle a sus 3 clips los nombres principal, arriba y abajo '
                    '(con 2 o 3 al final si es tu 2.ª o 3.ª variante).') % (etiqueta_posicion(e), ESTILOS[e['estilo']]['nombre'], COLORES[e['principal']][0].lower())
        ejemplos.append({'id': e['id'], 'nombre': e['nombre'], 'nota': nota, 'bloques': config_resolve(e)})
    return {'nombre': nombre, 'segundos': segundos, 'drb': str(drb) if drb else '', 'amro': str(amro) if amro else '', 'fotos': str(fotos) if fotos else '',
            'cuadros_s': list(CUADROS_VISTA_S), 'ejemplos': ejemplos}
