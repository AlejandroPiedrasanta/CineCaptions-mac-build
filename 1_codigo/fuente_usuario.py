# 1_codigo/fuente_usuario.py — v5.5.12: la tipografía que el usuario elige en «Crea tu estilo» para los Temas (texto principal y, aparte, el de
# arriba y abajo). Se guarda en las prefs ('fuente_principal', 'fuente_secundaria': "Familia|Estilo"; vacío = la del tema) y viaja en cada pista
# de los temas como track['fuente_usuario'] = {'main': [familia, estilo], 'extra': [familia, estilo]}; los gemelos de Resolve escriben Font/Style
# DESPUÉS del texto. Cada run del .json lleva 'fu' = 'main' | 'extra' para saber cuál es cuál (lo marca `marcar_runs`).
import json
from pathlib import Path

PREF_PRINCIPAL = 'fuente_principal'
PREF_SECUNDARIA = 'fuente_secundaria'

# (familia, estilo, etiqueta). Solo salen en la tira las que el equipo tiene instaladas.
OPCIONES = (
    ('Anton', 'Regular', 'Anton'),
    ('Bebas Neue', 'Regular', 'Bebas'),
    ('Montserrat', 'ExtraBold', 'Montserrat'),
    ('Poppins', 'Bold', 'Poppins'),
    ('Oswald', 'Bold', 'Oswald'),
    ('Archivo Black', 'Regular', 'Archivo'),
    ('Bangers', 'Regular', 'Bangers'),
    ('Playfair Display', 'Bold Italic', 'Playfair'),
    ('Impact', 'Regular', 'Impact'),
    ('Arial Black', 'Regular', 'Arial Black'),
)


def a_texto(familia, estilo):
    return f'{familia}|{estilo}' if familia else ''


def de_texto(valor):
    """"Familia|Estilo" -> [familia, estilo]; None si es «la del tema»."""
    partes = str(valor or '').split('|')
    if not partes[0].strip():
        return None
    return [partes[0].strip(), (partes[1].strip() if len(partes) > 1 and partes[1].strip() else 'Regular')]


def de_prefs(prefs):
    """{'main': [...], 'extra': [...]} con lo elegido; {} si las dos son «la del tema»."""
    out = {}
    for clave, pref in (('main', PREF_PRINCIPAL), ('extra', PREF_SECUNDARIA)):
        f = de_texto((prefs or {}).get(pref))
        if f:
            out[clave] = f
    return out


def es_principal(run):
    """La línea grande de cada bloque: héroe (Kinetic, VIRAL), rol 'main' (Tema 4) o un efecto de palabra (shatter/select/drag)."""
    if run.get('heroe') or run.get('rol') == 'main' or run.get('principal'):
        return True
    k = str(run.get('k') or '').lower()
    return any(p in k for p in ('hero', 'tapes', 'negrita', 'shatter', 'select', 'drag'))


def marcar_runs(data_path):
    """Pone 'fu' en cada run con texto del .json de la pista. Nunca lanza; True si escribió."""
    try:
        import archivos_seguros
        ruta = Path(data_path)
        datos = json.loads(ruta.read_text(encoding='utf-8'))
        cambiado = False
        for cue in datos.get('cues') or []:
            for run in cue.get('runs') or []:
                if isinstance(run, dict) and run.get('texto'):
                    fu = 'main' if es_principal(run) else 'extra'
                    if run.get('fu') != fu:
                        run['fu'] = fu
                        cambiado = True
        if cambiado:
            archivos_seguros.escribir_json(ruta, datos)
            import sidecar_lua                                         # Resolve Free (sin io) lee el gemelo «.lua»: sin esto no veía los 'fu'
            sidecar_lua.escribir_sidecar(ruta, datos)
        return cambiado
    except Exception:
        return False


def aplicar_a_pista(track, prefs):
    """Mete la fuente elegida en la pista de un tema (y marca sus runs). Sin elección no toca nada."""
    fu = de_prefs(prefs)
    if not fu or not isinstance(track, dict):
        return
    track['fuente_usuario'] = fu
    if track.get('style') == 'kinetic' and track.get('data_path'):
        marcar_runs(track['data_path'])
