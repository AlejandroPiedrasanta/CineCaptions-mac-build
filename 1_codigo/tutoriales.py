# CineCaptions · By Cinema Productions
# 1_codigo/tutoriales.py — los videos de los tutoriales (uno por página, grabados con la interfaz real) y la guía que sale sola UNA vez por versión nueva.
"""
tutoriales.py  (v5.82)
----------------------
Cada página tiene un video corto que enseña cómo se usa, grabado con la interfaz REAL sin pantalla (cursor, clics y cámara) por
herramientas_dev/hacer_videos_tutorial.py: 2_recursos/tutoriales/<id>.mp4 (960×600, H.264, sin audio) + <id>.jpg (su miniatura).
Los usan la guía (recorrido_ui: la tira con el video bajo la zona iluminada, propuesta C1 que eligió el usuario) y Ajustes › Tutoriales
(el reproductor con la lista, propuesta B2). v5.82 (el usuario: «agrégale voz… y tutoriales de cambiar de DaVinci Resolve por Premiere o sin
editores… más de la interfaz, probando estilos»): cada video lleva su LOCUCIÓN aparte, una por idioma (voz/<idioma>/<id>.m4a, hecha con
herramientas_dev/voz_tutoriales.py: voz natural local, sin servicios de fuera), y hay cinco tutoriales «paso a paso» además de las páginas.
v5.83 (el usuario: «si el usuario coloca inglés los videos tutoriales siguen en español»): un idioma puede tener SU grabación, con la
interfaz en ese idioma, su voz y sus tiempos, en 2_recursos/tutoriales/<idioma>/ (hoy: en). Sin ella, la de español con los subtítulos
traducidos.

    TUTORIALES                      [(id, título, texto)]: las páginas y luego los «paso a paso». En español: quien los pinta pasa cada uno por tr()
    GUIA / GRUPOS                   los ids de la guía (uno por página) y los grupos de la lista de Ajustes › Tutoriales
    carpeta_de(id, idioma=None)     la carpeta de ese tutorial en el idioma de la interfaz (tutoriales/<idioma>/ o la de español)
    ruta_video(id) / ruta_poster(id)   el archivo o None (si falta, la guía y Ajustes siguen sin ese video)
    ruta_voz(id, idioma=None)       la locución en el idioma de la interfaz o None (entonces el video va solo con sus subtítulos)
    subtitulos(id)                  [(desde, hasta, frase)]: las frases que el reproductor pinta encima del video (traducidas)
    voz_activa() / poner_voz_activa(si)   el altavoz del reproductor (de fábrica, con voz)
    guia_activa()                   el interruptor de Ajustes › Tutoriales («Guía en cada versión nueva»; de fábrica, encendido)
    poner_guia_activa(si)
    toca_guia()                     ¿sale sola al abrir? = activa y todavía no salió en ESTA versión
    marcar_guia_vista()             se llama al EMPEZAR la guía (así sale una sola vez aunque se cierre el programa a medias)

Preferencias (ajustes_ui.guardar_prefs → archivos_seguros): `guia_activa` (bool), `guia_version` (la versión en que salió por última vez) y
`tutoriales_voz` (bool, el altavoz).
"""
from pathlib import Path
import sys

# (id, título, texto). El id es el nombre del video y la página de la guía. Los textos dicen QUÉ se hace; el video enseña DÓNDE.
TUTORIALES = [
    ('inicio', 'Empieza en un clic',
     'Arrastra un video a la ventana y listo: CineCaptions le crea su proyecto en Resolve y lo subtitula. '
     '¿Ya tienes tu timeline abierto en DaVinci Resolve? Solo pulsa GO.'),
    ('estilo', 'Elige tu estilo',
     'Toca una tarjeta de los lados (o arrastra) para pasarlas y haz clic en la del centro para usarla. Cada tarjeta enseña cómo '
     'quedan tus subtítulos; «Con PRO» suma la edición de video.'),
    ('crea', 'Crea tu estilo',
     'La última tarjeta de Estilo. Elige un texto base y los textos principales que quieras (se turnan frase a frase), '
     'cambia la letra y el color debajo de la previa y guárdalo con su nombre.'),
    ('corrector', 'Corrector',
     'Después de GO tus palabras aparecen aquí. Elige un pincel (Arriba, Principal, Abajo) y toca las palabras para decidir '
     'cuál va grande; con doble clic corriges lo que se oyó mal. «Generar» lo vuelve a colocar en Resolve.'),
    ('sonido', 'Sonido',
     'Elige cómo suena tu video: automático según el estilo, elegante, dinámico… y si lleva gancho al inicio o música. '
     'GO pone los efectos solo; aquí los escuchas y los cambias uno por uno.'),
    ('efectos', 'Efectos',
     'El gancho del inicio, los captions detrás de ti, las transiciones y más. Toca una tarjeta para elegirla y apaga '
     'lo que no quieras con su interruptor: GO los aplica solos.'),
    ('ajustes', 'Ajustes',
     'Idioma, fondo, motor de voz y aquí mismo, en Tutoriales, todos estos videos. Desde ahí también apagas esta guía '
     'o la vuelves a ver cuando quieras.'),
    # v5.82: paso a paso (solo en Ajustes › Tutoriales; la guía sigue con una página por paso)
    ('probar', 'Prueba los estilos',
     'Pasa los estilos arrastrando o con la rueda del ratón. «Solo captions» enseña solo los subtítulos y «Con PRO» suma la edición '
     'de video; cuando te guste uno, haz clic en él para usarlo.'),
    ('premiere', 'Usar con Premiere Pro',
     'En Ajustes › General enciende «Usar con Premiere Pro»: GO arma una secuencia nueva con tu video, los subtítulos y los sonidos. '
     'Para volver, enciende «Usar con DaVinci Resolve».'),
    ('sin_editores', 'Video sin editores',
     'En Ajustes › General enciende «Video sin editores (DaVinci y Premiere)»: GO graba los subtítulos y los sonidos en una copia MP4 '
     'de tu video, junto al original.'),
    ('interfaz', 'Cambia la interfaz',
     'En Ajustes › Interfaz eliges la escena de Inicio, el fondo, el color de resaltado, el idioma y el tamaño. Pasa el ratón por una '
     'tarjeta para verla en movimiento.'),
    ('ayuda', '¿Necesitas ayuda?',
     'En Ajustes › Ayuda nos escribes por WhatsApp con el informe de tu equipo ya listo, ejecutas el diagnóstico y ves tu versión y '
     'tu licencia.'),
]
ORDEN = [t[0] for t in TUTORIALES]
GUIA = ('inicio', 'estilo', 'crea', 'corrector', 'sonido', 'efectos', 'ajustes')         # la guía: un paso por página
GRUPOS = (('Las páginas', GUIA), ('Paso a paso', tuple(i for i in ORDEN if i not in GUIA)))


def _base_recursos():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / '2_recursos'


def carpeta():
    return _base_recursos() / 'tutoriales'


def _idioma_ui():
    try:
        import i18n
        return i18n.idioma() or 'es'
    except Exception:
        return 'es'


_CARPETAS = {}


def carpeta_de(ident, idioma=None):
    """v5.83 (el usuario: «si el usuario coloca inglés los videos tutoriales siguen en español»): la carpeta de ESE tutorial en el idioma
    de la interfaz: 2_recursos/tutoriales/<idioma>/ si allí está grabado (la interfaz en ese idioma, con su voz y sus tiempos) o la de
    siempre (la interfaz en español; los subtítulos se traducen al pintarse). El video, su miniatura, su duración, sus subtítulos y su voz
    salen SIEMPRE de la misma carpeta: los tiempos de una grabación no valen para la otra."""
    idioma = str(idioma or _idioma_ui())
    clave = (ident, idioma)
    if clave not in _CARPETAS:
        base = carpeta()
        if idioma != 'es':
            try:
                ruta = base / idioma / f'{ident}.mp4'
                if ruta.is_file() and ruta.stat().st_size > 1000:
                    base = base / idioma
            except Exception:
                pass
        _CARPETAS[clave] = base
    return _CARPETAS[clave]


def _archivo(ident, ext):
    for base in dict.fromkeys((carpeta_de(ident), carpeta())):     # la miniatura que falte en otro idioma, la de español
        try:
            ruta = base / f'{ident}{ext}'
            if ruta.is_file() and ruta.stat().st_size > 1000:
                return ruta
        except Exception:
            pass
    return None


def ruta_video(ident):
    return _archivo(ident, '.mp4')


def ruta_poster(ident):
    return _archivo(ident, '.jpg')


# v5.82: si la interfaz va en un idioma sin locución, el video va mudo con sus subtítulos traducidos (VOZ_RESPALDO = idiomas que se
# prueban antes de rendirse, p. ej. ('en',); vacío = solo la del idioma de la interfaz)
VOZ_RESPALDO = ()


def ruta_voz(ident, idioma=None):
    """La locución del tutorial (<carpeta_de(id)>/voz/<idioma>/<id>.m4a) en el idioma de la interfaz, o None."""
    if idioma is None:
        idioma = _idioma_ui()
    base = carpeta_de(ident, idioma)
    for cod in (idioma,) + tuple(c for c in VOZ_RESPALDO if c != idioma):
        try:
            ruta = base / 'voz' / str(cod) / f'{ident}.m4a'
            if ruta.is_file() and ruta.stat().st_size > 1000:
                return ruta
        except Exception:
            pass
    return None


def voz_activa():
    """El altavoz del reproductor de los tutoriales (de fábrica, con voz)."""
    try:
        import ajustes_ui
        return ajustes_ui.leer_prefs().get('tutoriales_voz', True) is not False
    except Exception:
        return True


def poner_voz_activa(si):
    try:
        import ajustes_ui
        ajustes_ui.guardar_prefs({'tutoriales_voz': bool(si)})
    except Exception:
        pass


_DURACIONES = {}       # {carpeta: {id: segundos}}
_SUBTITULOS = {}       # {carpeta: {id: [[desde, hasta, frase]]}}


def _json_de(cache, base, nombre):
    """El .json de esa carpeta (lo escribe el generador), leído una vez; {} si no está."""
    clave = str(base)
    if clave not in cache:
        try:
            import json
            datos = json.loads((base / nombre).read_text(encoding='utf-8'))
            cache[clave] = datos if isinstance(datos, dict) else {}
        except Exception:
            cache[clave] = {}
    return cache[clave]


def duracion(ident):
    """Segundos del video (duraciones.json de su carpeta, que escribe el generador; 0 si no está)."""
    try:
        return float(_json_de(_DURACIONES, carpeta_de(ident), 'duraciones.json').get(ident) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def subtitulos(ident):
    """[(desde, hasta, frase)] del video (subtitulos.json de su carpeta, que escribe el generador con los tiempos reales de cada
    acción). Las frases van en español en todas las carpetas: el reproductor las pasa por tr() al pintarlas (v5.76, estilo A)."""
    out = []
    for c in _json_de(_SUBTITULOS, carpeta_de(ident), 'subtitulos.json').get(ident) or []:
        try:
            out.append((float(c[0]), float(c[1]), str(c[2])))
        except (TypeError, ValueError, IndexError):
            pass
    return out


def datos(ident):
    """(título, texto) del tutorial, en español (sin traducir)."""
    for i, t, x in TUTORIALES:
        if i == ident:
            return t, x
    return '', ''


# ---------------------------------------------------------------------------------------------------- la guía: una vez por versión
def _version():
    try:
        from version import APP_VERSION
        return str(APP_VERSION)
    except Exception:
        return ''


def guia_activa():
    try:
        import ajustes_ui
        return ajustes_ui.leer_prefs().get('guia_activa', True) is not False
    except Exception:
        return True


def poner_guia_activa(si):
    try:
        import ajustes_ui
        ajustes_ui.guardar_prefs({'guia_activa': bool(si)})
    except Exception:
        pass


def toca_guia():
    """¿La guía sale sola al abrir? Activa y sin haber salido aún en esta versión (la primera vez que se abre una versión distinta)."""
    try:
        import ajustes_ui
        prefs = ajustes_ui.leer_prefs()
    except Exception:
        return False
    if prefs.get('guia_activa', True) is False:
        return False
    v = _version()
    return bool(v) and str(prefs.get('guia_version') or '') != v


def marcar_guia_vista():
    try:
        import ajustes_ui
        ajustes_ui.guardar_prefs({'guia_version': _version()})
    except Exception:
        pass
