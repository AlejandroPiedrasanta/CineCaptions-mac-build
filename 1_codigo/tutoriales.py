# CineCaptions · By Cinema Productions
# 1_codigo/tutoriales.py — los videos de los tutoriales (uno por página, grabados con la interfaz real) y la guía que sale sola UNA vez por versión nueva.
"""
tutoriales.py  (v5.76)
----------------------
Cada página tiene un video corto que enseña cómo se usa, grabado con la interfaz REAL sin pantalla (cursor, clics y cámara) por
herramientas_dev/hacer_videos_tutorial.py: 2_recursos/tutoriales/<id>.mp4 (960×600, H.264, sin audio) + <id>.jpg (su miniatura).
Los usan la guía (recorrido_ui: la tira con el video bajo la zona iluminada, propuesta C1 que eligió el usuario) y Ajustes › Tutoriales
(el reproductor con la lista de las páginas, propuesta B2).

    TUTORIALES                      [(id, título, texto)] en el orden de las páginas. En español: quien los pinta pasa cada uno por tr()
    ruta_video(id) / ruta_poster(id)   el archivo o None (si falta, la guía y Ajustes siguen sin ese video)
    subtitulos(id)                  [(desde, hasta, frase)]: las frases que el reproductor pinta encima del video (traducidas)
    guia_activa()                   el interruptor de Ajustes › Tutoriales («Guía en cada versión nueva»; de fábrica, encendido)
    poner_guia_activa(si)
    toca_guia()                     ¿sale sola al abrir? = activa y todavía no salió en ESTA versión
    marcar_guia_vista()             se llama al EMPEZAR la guía (así sale una sola vez aunque se cierre el programa a medias)

Preferencias (ajustes_ui.guardar_prefs → archivos_seguros): `guia_activa` (bool) y `guia_version` (la versión en que salió por última vez).
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
]
ORDEN = [t[0] for t in TUTORIALES]


def _base_recursos():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / '2_recursos'


def carpeta():
    return _base_recursos() / 'tutoriales'


def _archivo(ident, ext):
    try:
        ruta = carpeta() / f'{ident}{ext}'
        return ruta if ruta.is_file() and ruta.stat().st_size > 1000 else None
    except Exception:
        return None


def ruta_video(ident):
    return _archivo(ident, '.mp4')


def ruta_poster(ident):
    return _archivo(ident, '.jpg')


_DURACIONES = {}


def duracion(ident):
    """Segundos del video (de 2_recursos/tutoriales/duraciones.json, que escribe el generador; 0 si no está). Se lee una vez."""
    if not _DURACIONES:
        try:
            import json
            _DURACIONES.update(json.loads((carpeta() / 'duraciones.json').read_text(encoding='utf-8')) or {})
        except Exception:
            _DURACIONES['_'] = 0
    try:
        return float(_DURACIONES.get(ident) or 0.0)
    except (TypeError, ValueError):
        return 0.0


_SUBTITULOS = {}


def subtitulos(ident):
    """[(desde, hasta, frase)] del video (2_recursos/tutoriales/subtitulos.json, que escribe el generador con los tiempos reales de cada
    acción). Las frases van en español: el reproductor las pasa por tr() al pintarlas (v5.76, estilo A que eligió el usuario)."""
    if not _SUBTITULOS:
        try:
            import json
            _SUBTITULOS.update(json.loads((carpeta() / 'subtitulos.json').read_text(encoding='utf-8')) or {})
        except Exception:
            _SUBTITULOS['_'] = []
    out = []
    for c in _SUBTITULOS.get(ident) or []:
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
