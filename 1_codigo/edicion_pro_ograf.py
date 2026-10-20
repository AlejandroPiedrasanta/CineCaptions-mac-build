# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_ograf.py — Edición PRO: los gráficos animados como plantillas OGraf (HTML) de DaVinci Resolve 21.1+.
"""
Cada gráfico de Edición PRO es un archivo `.ograf` (un ZIP con su manifiesto y su componente web) que Resolve importa al Media Pool
como cualquier medio y se coloca con AppendToTimeline (nada de InsertFusionTitleIntoTimeline: con nombres dudosos tumbó Resolve).
En el Inspector salen sus parámetros (textos, colores, tipografía, posición, tiempos) y el usuario los puede retocar.

    construir(pieza, valores, duracion_s, carpeta) -> Path del .ograf      un gráfico concreto (sus valores = los por defecto del Inspector)
    instalar_plantillas()                          -> carpeta | None       las 9 piezas en la caja de herramientas de Resolve («CineCaptions PRO»)
    ESQUEMAS                                                               parámetros de cada pieza (los mismos nombres que DEFAULTS en su pieza.js)

Las piezas viven en 2_recursos/edicion_pro/ograf/<pieza>/pieza.js y comparten lib/motor.js y lib/fonts (OFL). Todo va DENTRO de cada
.ograf (Resolve no garantiza red ni rutas relativas fuera del paquete). Las rutas que se le pasan a Resolve son SIEMPRE largas: con la
ruta corta de Windows («CINEMA~1») Fusion no encuentra el clip del Media Pool y Resolve se cae (Sm2MpObject.cpp, comprobado en 21.1.1).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

SCHEMA_URL = 'https://ograf.ebu.io/v1/specification/json-schemas/graphics/schema.json'
VERSION_PIEZAS = '1.2.0'


def carpeta_ograf() -> Path:
    try:
        from sfx_rules import base_recursos
        return Path(base_recursos()) / 'edicion_pro' / 'ograf'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'edicion_pro' / 'ograf'


def _color(titulo, defecto):
    return {'type': 'string', 'title': titulo, 'gddType': 'color-rrggbb', 'pattern': '^#[0-9a-f]{6}$', 'default': defecto}


def _texto(titulo, defecto=''):
    return {'type': 'string', 'title': titulo, 'default': defecto}


def _num(titulo, defecto, minimo, maximo, entero=False):
    return {'type': 'integer' if entero else 'number', 'title': titulo, 'minimum': minimo, 'maximum': maximo, 'default': defecto}


def _sel(titulo, defecto, opciones):
    return {'type': 'string', 'title': titulo, 'gddType': 'select', 'enum': list(opciones), 'gddOptions': {'labels': dict(opciones)}, 'default': defecto}


def _bool(titulo, defecto):
    return {'type': 'boolean', 'title': titulo, 'default': bool(defecto)}


FUENTES = {'serif': 'Serif editorial', 'grotesk': 'Grotesca', 'redonda': 'Redonda', 'mono': 'Monoespaciada'}
_POS = lambda x, y: [('escala', _num('Tamaño', 1.0, 0.4, 2.5)), ('x', _num('Posición X (%)', x, 0, 100)), ('y', _num('Posición Y (%)', y, 0, 100))]

# Orden = orden del Inspector. Máximo 20 por pieza (límite de Resolve).
ESQUEMAS = {
    'titular': {'nombre': 'Titular', 'salida_ms': 400, 'props': [
        ('linea1', _texto('Línea 1')), ('linea2', _texto('Línea 2', 'TITULAR')), ('linea3', _texto('Línea 3')),
        ('tamanos', _texto('Tamaño de cada línea', '0.45,1,0.6')), ('acentoLinea', _num('Línea en el acento', 2, 0, 3, True)),
        ('tiempos', _texto('Tiempos de cada palabra (s)', '0,0.3,0.6')), ('fuente', _sel('Tipografía', 'serif', FUENTES)),
        ('mayusculas', _bool('Mayúsculas', True)), ('acento', _color('Acento', '#c9a46a')), ('colorTexto', _color('Texto', '#ffffff')),
        ('entrada', _sel('Entrada', 'subir', {'subir': 'Sube', 'desenfoque': 'Desenfoque', 'mascara': 'Ranura'})),
        *_POS(50, 30), ('ancho', _num('Ancho máximo (%)', 92, 20, 100)), ('sombra', _bool('Sombra', True))]},
    'rotulo': {'nombre': 'Rótulo', 'salida_ms': 350, 'props': [
        ('linea1', _texto('Línea 1', 'Una frase')), ('linea2', _texto('Línea 2', 'QUE SE QUEDA')), ('acentoLinea', _num('Línea en el acento', 2, 0, 2, True)),
        ('tiempos', _texto('Tiempos (s)', '0,0.6')), ('fuente', _sel('Tipografía', 'serif', FUENTES)), ('acento', _color('Acento', '#c9a46a')),
        ('colorTexto', _color('Texto', '#ffffff')), ('colorBloque', _color('Bloque', '#141210')), *_POS(50, 22), ('inclinacion', _num('Inclinación (°)', 0, -8, 8))]},
    'cifra': {'nombre': 'Cifra', 'salida_ms': 400, 'props': [
        ('numero', _texto('Número', '3')), ('unidad', _texto('Unidad', 'ACRES')), ('etiqueta', _texto('Etiqueta')),
        ('tiempos', _texto('Tiempos (s)', '0,0.3,0.6')), ('fuente', _sel('Tipografía', 'grotesk', FUENTES)), ('acento', _color('Acento', '#c9a46a')),
        ('colorTexto', _color('Texto', '#ffffff')), ('estilo', _sel('Adorno', 'linea', {'linea': 'Subrayado', 'anillo': 'Anillo', 'bloque': 'Bloque', 'ninguno': 'Ninguno'})),
        *_POS(50, 28)]},
    'lista': {'nombre': 'Lista', 'salida_ms': 400, 'props': [
        ('titulo', _texto('Título')), ('item1', _texto('Elemento 1', 'Uno')), ('item2', _texto('Elemento 2', 'Dos')), ('item3', _texto('Elemento 3')),
        ('item4', _texto('Elemento 4')), ('tiempos', _texto('Tiempos (s)', '0,0.4,0.8,1.2,1.6')),
        ('icono', _sel('Icono', 'check', {'check': 'Check', 'numero': 'Número', 'punto': 'Punto', 'estrella': 'Estrella', 'corazon': 'Corazón'})),
        ('disposicion', _sel('Disposición', 'columna', {'columna': 'Columna', 'fila': 'Fichas'})), ('fuente', _sel('Tipografía', 'grotesk', FUENTES)),
        ('acento', _color('Acento', '#c9a46a')), ('colorTexto', _color('Texto', '#ffffff')), ('colorPanel', _color('Panel', '#121212')), *_POS(50, 28)]},
    'etiqueta': {'nombre': 'Etiqueta', 'salida_ms': 300, 'props': [
        ('kicker', _texto('Antetítulo')), ('texto', _texto('Texto', 'Etiqueta')), ('indice', _texto('Índice')),
        ('icono', _sel('Icono', 'ninguno', {'ninguno': 'Ninguno', 'pin': 'Ubicación'})), ('alinear', _sel('Alineación', 'izq', {'izq': 'Izquierda', 'centro': 'Centro', 'der': 'Derecha'})),
        ('fuente', _sel('Tipografía', 'serif', FUENTES)), ('acento', _color('Acento', '#c9a46a')), ('colorTexto', _color('Texto', '#ffffff')),
        *_POS(7, 74), ('tiempos', _texto('Tiempo de entrada (s)', '0'))]},
    'cta': {'nombre': 'Llamada a la acción', 'salida_ms': 400, 'props': [
        ('kicker', _texto('Antetítulo')), ('titulo', _texto('Título', 'Título')), ('fila1', _texto('Dato 1')), ('fila2', _texto('Dato 2')),
        ('fila3', _texto('Dato 3')), ('boton', _texto('Botón', 'Escríbenos')), ('tiempos', _texto('Tiempos (s)', '0,0.25,0.5,0.75,1.0,1.3')),
        ('fuente', _sel('Tipografía', 'serif', FUENTES)), ('acento', _color('Acento', '#c9a46a')), ('colorTexto', _color('Texto', '#ffffff')),
        ('colorPanel', _color('Panel', '#121110')), *_POS(50, 62), ('icono', _sel('Icono', 'check', {'check': 'Check', 'estrella': 'Estrella', 'corazon': 'Corazón', 'pin': 'Ubicación'}))]},
    'marco': {'nombre': 'Marco', 'salida_ms': 350, 'props': [
        ('estilo', _sel('Estilo', 'elegante', {'elegante': 'Elegante', 'ventana': 'Ventana', 'simple': 'Simple', 'brillo': 'Brillo', 'visor': 'Visor de cámara', 'cinta': 'Película'})),
        ('texto', _texto('Texto')), ('acento', _color('Acento', '#c9a46a')), ('colorTexto', _color('Texto', '#ffffff')),
        ('margen', _num('Margen (%)', 5, 1, 20)), ('grosor', _num('Grosor', 1, 0.3, 4)), ('tiempos', _texto('Tiempo de entrada (s)', '0')),
        ('tcInicio', _num('Código de tiempo inicial (s)', 0, 0, 86400)), ('fps', _num('FPS del código de tiempo', 30, 1, 120, True))]},
    'velo': {'nombre': 'Velo', 'salida_ms': 450, 'props': [
        ('forma', _sel('Forma', 'arriba', {'arriba': 'Arriba', 'abajo': 'Abajo', 'completo': 'Completo', 'vineta': 'Viñeta'})),
        ('color', _color('Color', '#000000')), ('intensidad', _num('Intensidad', 0.45, 0, 1)), ('fundido', _num('Fundido (s)', 0.5, 0.05, 3))]},
    'nombres': {'nombre': 'Nombres', 'salida_ms': 500, 'props': [
        ('nombre1', _texto('Nombre 1', 'Ana')), ('conector', _texto('Conector', '&')), ('nombre2', _texto('Nombre 2', 'Luis')),
        ('subtitulo', _texto('Subtítulo')), ('tiempos', _texto('Tiempos (s)', '0,0.5,0.9,1.4')), ('fuente', _sel('Tipografía', 'serif', FUENTES)),
        ('acento', _color('Acento', '#d8b67a')), ('colorTexto', _color('Texto', '#ffffff')),
        ('adorno', _sel('Adorno', 'lineas', {'lineas': 'Líneas', 'ninguno': 'Ninguno'})), *_POS(50, 30)]},
    # v5.5.8: la tarjeta de precio / cifra / gráfica del Tema 5 y 6, editable en el Inspector (antes un video de Remotion)
    'dato': {'nombre': 'Dato', 'salida_ms': 350, 'props': [
        ('tipo', _sel('Tipo', 'precio', {'precio': 'Precio', 'grafica': 'Gráfica', 'cifra': 'Cifra'})),
        ('valor', _texto('Valor', '80')), ('signo', _texto('Moneda o signo ($, ₦, €, %…)', '$')), ('etiqueta', _texto('Etiqueta', 'TOTAL')),
        ('tendencia', _sel('Tendencia', 'sube', {'sube': 'Sube', 'baja': 'Baja', 'plana': 'Sin signo'})),
        ('tema', _sel('Aspecto', 'oscuro', {'oscuro': 'Cristal oscuro', 'claro': 'Carta blanca'})), ('acento', _color('Acento', '#4c7dff')),
        ('colorTexto', _color('Texto', '#f4f5f9')), ('fuente', _sel('Tipografía', 'grotesk', FUENTES)), ('tiempos', _texto('Entrada (s)', '0.1')),
        *_POS(50, 73)]},
}
ICONOS_CONCEPTO = {'camera': 'Cámara', 'clapperboard': 'Claqueta', 'film': 'Película', 'video': 'Video', 'mic': 'Micrófono', 'music': 'Música',
                   'gift': 'Regalo', 'calendarDays': 'Calendario', 'clock': 'Reloj', 'sun': 'Sol', 'sunrise': 'Amanecer', 'moon': 'Luna', 'users': 'Personas',
                   'key': 'Llave', 'casa': 'Casa', 'building2': 'Edificio', 'store': 'Tienda', 'shoppingCart': 'Carrito', 'coins': 'Monedas',
                   'piggyBank': 'Ahorro', 'trendingUp': 'Crecimiento', 'chartColumn': 'Gráfica', 'percent': 'Porcentaje', 'globe': 'Mundo',
                   'trophy': 'Trofeo', 'medal': 'Medalla', 'crown': 'Corona', 'anillos': 'Anillos', 'corazon': 'Corazón', 'cubiertos': 'Cubiertos',
                   'image': 'Foto', 'palette': 'Paleta', 'lightbulb': 'Idea', 'rocket': 'Cohete', 'target': 'Meta', 'smartphone': 'Teléfono',
                   'mail': 'Correo', 'messageSquare': 'Mensaje', 'bell': 'Aviso', 'timer': 'Temporizador', 'hourglass': 'Reloj de arena',
                   'graduationCap': 'Graduación', 'briefcase': 'Maletín', 'thumbsUp': 'Me gusta', 'zap': 'Rayo', 'pin': 'Ubicación', 'estrella': 'Estrella',
                   'bed': 'Recámara', 'bath': 'Baño', 'trees': 'Jardín', 'waves': 'Agua', 'car': 'Cochera', 'cake': 'Pastel', 'gem': 'Joya',
                   'wine': 'Vino', 'chefHat': 'Chef', 'coffee': 'Café', 'pizza': 'Pizza', 'aperture': 'Lente', 'mountain': 'Montaña', 'sofa': 'Sala',
                   'ruler': 'Terreno', 'flower': 'Flores', 'heartHandshake': 'Amor', 'plane': 'Viaje', 'shieldCheck': 'Seguridad', 'map': 'Mapa',
                   'scissors': 'Tijeras', 'wrench': 'Herramienta'}
ICONOS3D = {'bell-dynamic-color': 'Campana', 'bell-dynamic-premium': 'Campana (oscura)', 'calendar-dynamic-color': 'Calendario',
            'calendar-dynamic-premium': 'Calendario (oscuro)', 'camera-dynamic-premium': 'Cámara', 'crown-dynamic-color': 'Corona',
            'explorer-front-color': 'Brújula', 'fire-front-color': 'Fuego', 'flag-dynamic-color': 'Bandera', 'key-front-premium': 'Llave',
            'lock-front-premium': 'Candado', 'megaphone-dynamic-color': 'Megáfono', 'money-dynamic-premium': 'Dinero (oro)',
            'money-front-color': 'Dinero', 'notify-heart-front-color': 'Me gusta', 'picture-dynamic-premium': 'Foto', 'ribbon-dynamic-color': 'Moño',
            'thumb-down-dynamic-color': 'Pulgar abajo', 'travel-dynamic-color': 'Maleta', 'wallet-front-premium': 'Cartera'}
ESQUEMAS['fondo'] = {'nombre': 'Fondo animado (B-roll)', 'salida_ms': 350, 'props': [
    ('estilo', _sel('Estilo', 'aurora', {'aurora': 'Aurora', 'rejilla': 'Rejilla', 'puntos': 'Puntos', 'liso': 'Liso'})),
    ('entrada', _sel('Entrada', 'iris', {'iris': 'Iris', 'cortina': 'Cortina', 'fundido': 'Fundido'})),
    ('color1', _color('Color 1 (acento)', '#c9a46a')), ('color2', _color('Color 2 (fondo)', '#121110')), ('color3', _color('Color 3', '#3a2f22')),
    ('intensidad', _num('Intensidad', 0.75, 0, 1))]}
ESQUEMAS['icono'] = {'nombre': 'Concepto con icono', 'salida_ms': 350, 'props': [
    ('icono', _sel('Icono', 'camera', ICONOS_CONCEPTO)), ('imagen', _sel('Icono 3D (sustituye al dibujo)', '', {'': 'Ninguno', **ICONOS3D})),
    ('texto', _texto('Texto', 'CONCEPTO')), ('kicker', _texto('Antetítulo')),
    ('fuente', _sel('Tipografía', 'grotesk', FUENTES)), ('acento', _color('Acento', '#c9a46a')), ('colorTexto', _color('Texto', '#ffffff')),
    *_POS(50, 42), ('tiempos', _texto('Tiempos (s)', '0,0.35'))]}
ESQUEMAS['icono3d'] = {'nombre': 'Icono 3D flotante', 'salida_ms': 300, 'props': [
    ('imagen', _sel('Icono 3D', 'fire-front-color', ICONOS3D)), ('tamano', _num('Tamaño (% del alto)', 16, 3, 60)),
    ('brillo', _num('Brillo', 0.7, 0, 1)), ('acento', _color('Color del resplandor', '#ffb020')), ('flotar', _num('Flotar', 1, 0, 3)),
    ('giro', _num('Balanceo (°)', 8, 0, 30)), ('x', _num('Posición X (%)', 82, 0, 100)), ('y', _num('Posición Y (%)', 30, 0, 100)),
    ('tiempos', _texto('Tiempos (s)', '0'))]}
ESQUEMAS['orbita'] = {'nombre': 'Órbita de iconos (gancho)', 'salida_ms': 350, 'props': [
    ('iconos', _texto('Iconos (separados por comas)', 'casa,key,bed,waves')), ('imagenes', _texto('Iconos 3D (separados por comas)')),
    ('mitad', _sel('Mitad', 'todo', {'todo': 'Toda la órbita', 'atras': 'Solo la de atrás (debajo de la persona)', 'delante': 'Solo la de delante'})),
    ('acento', _color('Acento', '#c9a46a')), ('colorTexto', _color('Iconos', '#ffffff')),
    # v5.20 (página Efectos › Gancho del inicio, estilos_pro.py): el trazo de la órbita
    ('estilo', _sel('Anillo', 'limpio', {'limpio': 'Solo iconos', 'rastro': 'Rastro de luz', 'anillo': 'Anillo fino', 'neon': 'Neón', 'chips': 'Burbujas de cristal',
                                         'cometa': 'Cometa', 'doble': 'Doble órbita', 'puntos': 'Puntos', 'halo': 'Halo', 'cinta': 'Cinta'})),
    ('acento2', _color('Segundo color (halo)', '#ff7a1a')), ('colorAnillo', _color('Color del anillo', '#ffffff')),
    ('rx', _num('Radio horizontal (%)', 22, 3, 50)), ('ry', _num('Radio vertical (%)', 4.5, 0.5, 20)), ('inclinacion', _num('Inclinación (°)', -8, -45, 45)),
    ('vueltas', _num('Vueltas por segundo', 0.32, 0.05, 2)), *_POS(50, 30), ('tiempos', _texto('Tiempos (s)', '0'))]}
FUENTES_DE = {'velo': [], 'fondo': [], 'orbita': [], 'icono3d': []}           # las que no usan texto no llevan fuentes (paquete más ligero)


def _normalizar(pieza, valores):
    """Valores válidos para el manifiesto: colores en minúscula, números dentro de su rango, selects con una opción que exista."""
    salida = {}
    for clave, spec in ESQUEMAS[pieza]['props']:
        v = valores.get(clave, spec['default']) if valores else spec['default']
        try:
            if spec.get('gddType', '').startswith('color'):
                v = str(v or spec['default']).strip().lower()
                if len(v) != 7 or not v.startswith('#') or any(c not in '0123456789abcdef' for c in v[1:]):
                    v = spec['default']
            elif spec['type'] in ('number', 'integer'):
                v = float(v)
                v = min(spec['maximum'], max(spec['minimum'], v))
                v = int(round(v)) if spec['type'] == 'integer' else round(v, 4)
            elif spec['type'] == 'boolean':
                v = bool(v)
            elif spec.get('gddType') == 'select':
                v = v if v in spec['enum'] else spec['default']
            else:
                v = str(v if v is not None else '')[:400]
        except (TypeError, ValueError):
            v = spec['default']
        salida[clave] = v
    return salida


def manifiesto(pieza, valores=None, duracion_s=5.0, ident=None, fps=30.0, ancho=None, alto=None):
    """El .ograf.json de una pieza. Los valores van como «default» de cada propiedad: es lo que el Inspector enseña y lo que recibe load().
    `ancho`/`alto`: la resolución del timeline. Sin ella el entorno OGraf de Resolve supone 1920x1080 y escala el gráfico para encajarlo
    (en vertical lo dejaba a 0,56 en una esquina; el motor también lo compensa, pero así no hay ni que compensar)."""
    esq = ESQUEMAS[pieza]
    vals = _normalizar(pieza, valores or {})
    # v5.5.8 (pedido: «un banner de CineCaptions en el Inspector para personalizar todo lo que se puso en la línea de tiempo»): el primer campo
    # del Inspector es el banner (la pieza no lo usa; el texto dice qué se puede cambiar debajo)
    props = {'cinecaptions': {'type': 'string', 'title': '✦  CINECAPTIONS  ✦', 'default': f'Personaliza este {esq["nombre"].lower()}: texto, colores y posición aquí abajo'}}
    for clave, spec in esq['props']:
        p = dict(spec)
        p['default'] = vals[clave]
        props[clave] = p
    return {
        '$schema': SCHEMA_URL,
        'id': ident or f'cinecaptions-pro-{pieza}',
        'version': VERSION_PIEZAS,
        'name': f'CC PRO · {esq["nombre"]}',
        'description': f'CineCaptions Edición PRO · {esq["nombre"]}',
        'author': {'name': 'CineCaptions · Cinema Productions'},
        'main': 'pieza.js',
        'supportsRealTime': False,
        'supportsNonRealTime': True,
        'stepCount': 1,
        'actionDurations': [{'type': 'playAction', 'duration': 600}, {'type': 'stopAction', 'duration': int(esq['salida_ms'])}],
        'schema': {'type': 'object', 'additionalProperties': False, 'properties': props},
        'renderRequirements': [dict({'frameRate': {'ideal': int(round(float(fps or 30)))}},
                                    **({'resolution': {'width': {'ideal': int(ancho)}, 'height': {'ideal': int(alto)}}} if ancho and alto else {}))],
        'v_bmd': {'duration': round(max(0.2, float(duracion_s)), 4)},
    }


def js_empaquetado(pieza):
    """El componente en UN solo módulo: el motor común + la pieza (sin import). Así cada .ograf es autónomo y el linter de
    Blackmagic ve los 8 métodos de OGraf en el archivo principal."""
    import re
    base = carpeta_ograf()
    motor = (base / 'lib' / 'motor.js').read_text(encoding='utf-8')
    motor = re.sub(r'^export (const|function|class|async function|let) ', r'\1 ', motor, flags=re.M)
    motor = motor.replace("'./fonts/'", "'./lib/fonts/'").replace("'./iconos3d/'", "'./lib/iconos3d/'")
    pieza_js = (base / pieza / 'pieza.js').read_text(encoding='utf-8')
    pieza_js = re.sub(r"^import [^;]*from '\./lib/motor\.js';[ \t]*$", '', pieza_js, flags=re.M)
    return motor + '\n' + pieza_js


def iconos3d():
    """Los iconos 3D disponibles (3dicons, CC0): nombre → ruta del PNG."""
    return {f.stem: f for f in sorted((carpeta_ograf() / 'lib' / 'iconos3d').glob('*.png'))}


def _archivos_de(pieza, valores=None):
    """(ruta en el ZIP sin la carpeta raíz, ruta en disco) de lo que lleva una pieza ADEMÁS de pieza.js (que va empaquetado): sus fuentes y
    solo los iconos 3D que nombra (`imagen`, `imagenes`)."""
    base = carpeta_ograf()
    v = valores or {}
    nombres = [str(v.get('imagen') or '')] + str(v.get('imagenes') or '').split(',')
    disp = iconos3d()
    for n in dict.fromkeys(x.strip() for x in nombres if x and x.strip()):
        if n in disp:
            yield f'lib/iconos3d/{n}.png', disp[n]
    fuentes = base / 'lib' / 'fonts'
    if FUENTES_DE.get(pieza, None) != []:
        for f in sorted(fuentes.glob('*.woff2')):
            yield f'lib/fonts/{f.name}', f
        if (fuentes / 'LICENCIAS.txt').exists():
            yield 'lib/fonts/LICENCIAS.txt', fuentes / 'LICENCIAS.txt'


def ruta_larga(ruta) -> Path:
    """La ruta completa sin nombres cortos de Windows (CINEMA~1 → CINEMA PRODUCTIONS)."""
    p = Path(ruta).expanduser().resolve()
    if sys.platform == 'win32' and '~' in str(p):
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(32768)
            if ctypes.windll.kernel32.GetLongPathNameW(str(p), buf, 32768):
                return Path(buf.value)
        except Exception:
            pass
    return p


def construir(pieza, valores, duracion_s, carpeta, fps=30.0, prefijo='pro', ancho=None, alto=None):
    """Escribe el .ograf de UN gráfico en `carpeta` y devuelve su ruta larga. Mismo contenido = mismo archivo (se reaprovecha)."""
    if pieza not in ESQUEMAS:
        raise ValueError(f'pieza desconocida: {pieza}')
    carpeta = ruta_larga(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    vals = _normalizar(pieza, valores or {})
    firma = hashlib.sha1(json.dumps([pieza, vals, round(float(duracion_s), 4), round(float(fps), 3), ancho, alto, VERSION_PIEZAS, hashlib.sha1(js_empaquetado(pieza).encode('utf-8')).hexdigest()], sort_keys=True).encode('utf-8')).hexdigest()[:12]
    nombre = f'{prefijo}_{pieza}_{firma}'
    destino = carpeta / f'{nombre}.ograf'
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    man = manifiesto(pieza, vals, duracion_s, ident=f'cinecaptions-{nombre}'.replace('_', '-'), fps=fps, ancho=ancho, alto=alto)
    tmp = destino.with_suffix('.tmp')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(f'{nombre}/manifest.ograf.json', json.dumps(man, ensure_ascii=False, indent=1))
        z.writestr(f'{nombre}/pieza.js', js_empaquetado(pieza))
        for dentro, real in _archivos_de(pieza, vals):
            z.write(real, f'{nombre}/{dentro}')
    os.replace(tmp, destino)
    return destino


def carpeta_plantillas_resolve() -> Path | None:
    """Donde Resolve busca los títulos del usuario (sin permisos de administrador)."""
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA')
        return Path(base) / 'Blackmagic Design' / 'DaVinci Resolve' / 'Support' / 'Fusion' / 'Templates' / 'Edit' / 'Titles' if base else None
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'Blackmagic Design' / 'DaVinci Resolve' / 'Fusion' / 'Templates' / 'Edit' / 'Titles'
    return None


def instalar_plantillas():
    """Copia las 9 piezas (con sus valores de fábrica) a la caja de herramientas de Resolve, categoría «CineCaptions PRO», para que el
    usuario también las pueda poner a mano. Resolve las ve al reiniciarse. Devuelve la carpeta o None."""
    raiz = carpeta_plantillas_resolve()
    if raiz is None:
        return None
    destino = raiz / 'CineCaptions PRO'
    try:
        destino.mkdir(parents=True, exist_ok=True)
        for pieza in ESQUEMAS:
            d = destino / f'CC PRO {ESQUEMAS[pieza]["nombre"]}'
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True, exist_ok=True)
            man = manifiesto(pieza, None, 5.0)
            (d / 'manifest.ograf.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
            (d / 'pieza.js').write_text(js_empaquetado(pieza), encoding='utf-8')
            todas = {'imagenes': ','.join(iconos3d())} if pieza in ('icono3d', 'orbita', 'icono') else None     # en la caja: todos los iconos 3D
            for dentro, real in _archivos_de(pieza, todas):
                (d / dentro).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(real, d / dentro)
        return destino
    except OSError:
        return None


def lint(ruta_dir):
    """(desarrollo) Pasa el linter oficial de Blackmagic sobre una carpeta de plantilla. Devuelve (ok, texto)."""
    import subprocess
    candidatos = [Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) / 'Blackmagic Design' / 'DaVinci Resolve' / 'Support' / 'Developer' / 'OGraf HTML Templates' / 'Scripts' / 'lint-ograf.py',
                  Path('/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/OGraf HTML Templates/Scripts/lint-ograf.py')]
    script = next((c for c in candidatos if c.exists()), None)
    if script is None:
        return True, 'sin linter'
    r = subprocess.run([sys.executable, str(script), str(ruta_dir)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode == 0, (r.stdout + r.stderr).strip()
