# 1_codigo/fuente_usuario.py — v5.5.12: la tipografía que el usuario elige en «Crea tu estilo» para los Temas (texto principal y, aparte, el de
# arriba y abajo). v5.55: se guarda EN EL PACK del estilo (pack.json 'ajustes': 'fuente_principal', 'fuente_secundaria': "Familia|Estilo"; vacío =
# la del tema; las prefs globales con esos nombres ya no se leen: GO pasa los ajustes del pack como `prefs`) y viaja en cada pista
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
    return any(p in k for p in ('hero', 'tapes', 'negrita', 'shatter', 'select', 'drag', 'corte', 'shine', 'resalta', 'linea', 'tipo'))   # v5.75; v5.76 «v tipo»


def _encajar(run, fuente):
    """v5.44 (el Tema 1 con «Arial Black» de texto principal: las palabras grandes se salían de la pantalla): el «Size» del run se calculó con la
    fuente del tema; con otra más ancha se reduce lo justo para que ocupe lo mismo (nunca crece). Guarda el de antes en 'size0' (re-aplicar no
    encoge dos veces). True si cambió."""
    try:
        import kinetic_captions as KC
        clave, size0 = str(run.get('k') or ''), float(run.get('size0') or run.get('size') or 0)
        if not clave or size0 <= 0 or clave == 'v tipo':          # (v5.76: el bloque del Tema 5 lleva sus letras y tamaños dentro de su texto)
            return False
        e = KC._espec(clave)
        tema = KC.ancho_px(clave, run['texto'], size0)
        propia = KC._fuente((fuente[0], fuente[1]), size0 * KC.K_PX)
        if propia is None or tema <= 0:
            return False
        visible = KC.texto_visible(clave, run['texto'])
        suya = propia.getlength(visible) * KC.TINTA + max(0, len(visible) - 1) * (e['esp'] - 1.0) * KC.K_ESP * size0 * KC.K_PX   # (como ancho_px)
        nuevo = round(size0 * min(1.0, tema / suya), 4) if suya > 0 else size0
        if abs(nuevo - float(run.get('size') or 0)) < 1e-4:
            return False
        run['size0'], run['size'] = size0, nuevo
        return True
    except Exception:
        return False


def marcar_runs(data_path, fu_prefs=None):
    """Pone 'fu' en cada run con texto del .json de la pista y, con la fuente elegida (`fu_prefs`), encaja su tamaño. Nunca lanza; True si escribió."""
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
                    if (fu_prefs or {}).get(fu) and _encajar(run, fu_prefs[fu]):
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
    if not fu or not isinstance(track, dict) or track.get('fuente_del_tema'):
        return                     # (v5.45: el Tema 1 con Text+ va siempre con la letra del kit, como sus clips neón: «que sea lo mismo»)
    track['fuente_usuario'] = fu
    if track.get('style') == 'kinetic' and track.get('data_path'):
        marcar_runs(track['data_path'], fu)
