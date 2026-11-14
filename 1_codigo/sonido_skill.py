# CineCaptions · By Cinema Productions
# 1_codigo/sonido_skill.py — SONIDO con la biblioteca del autor y las reglas de MAPA_SFX.md (reemplaza el diseño de SFX del «AI Sound Director»).
"""
Es el mismo motor que la skill «sonorizar-sfx» (~/.claude/skills/sonorizar-sfx/scripts/proponer_timeline.py): mantener REGLAS, POOLS y ESTILO
iguales en los dos. Aquí NO se adivina mirando el video: los eventos salen de la metadata REAL de GO (director_sonido_eventos):

    captions(bloques)   animación real de cada clip: 'k hero' → texto grande (golpe en p≈0,37 de 10 f), 'k ring/line trazo' → ARO (KINETIC),
                        VIRAL shatter → acento, drag → swoosh, select → tic; tamaño/escala de la palabra clave → grande o chico
    motions(Efectos, PRO, kit neón)   corte, icono, número, pegatina, énfasis, B-roll y las piezas PRO por su nombre (barra, check, precio, mapa…)
    narrativa(palabras)  DATA con dinero → DINERO; el gancho (riser) si Efectos no puso ya una intro con sonido
    cortes de GO         swoosh corto

API para GO (la misma forma que director_sonido; el resto de la tubería —al_colocar, pistas AI SFX, apagar Simple, confirmar— es la de siempre):
    activo()            preferencia 'sonido_skill' (encendido por defecto)
    preparar(ctx, res)  diseña, hornea cada WAV (recorte + nivel) y deja res['sfx'] = {'eventos': [{'tipo': 'sonido', 'pista', 'ini', 'dur',
                        'archivo', 'asset', 'pico'}], 'puestos': [...]} y el diseño en el estado del video ('sfx_plan', 'sonido_skill');
                        v5.48: también la música de 02_MUSICA (sonido_musica: 3 opciones, res['capas'] y 'music_plan' = la elegida)
Elección (v5.48, lo aprendido de 70 videos de creadores): solo sonidos curados, 1 principal + 3 variantes por tipo con tope del 40 %, nunca la
misma familia seguida, lo APROBADO por el usuario primero y la densidad de los creadores por estilo (max10).
    rehacer(video, …)   la página Sonido rediseña con la foto guardada de GO (estilo, gancho, fiesta) sin volver a hacer GO
Biblioteca: preferencia 'sonido_biblioteca'; si no, 5_SFX de la carpeta de CineCaptions (v5.48, fuera de Git), luego Desktop\\SFX (enlace a
5_SFX; lo usa la skill), luego la copia que viaja en el .exe (v5.56: 2_recursos/biblioteca_sonido, 3_compilar/empaquetar_sonidos.py) y por
último «Mis sonidos» del director. Si la carpeta trae catalogo_sfx.json (lo escribe la skill) se usa; si no, se mide aquí con PyAV y se guarda
en caché. Sin ninguna biblioteca (disponible() = False) GO se queda con los sonidos de siempre.
"""
import json
import math
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np

PREF_ON, PREF_LIB, PREF_ESTILO, PREF_GANCHO, PREF_FIESTA = 'sonido_skill', 'sonido_biblioteca', 'sonido_estilo', 'sonido_gancho', 'sonido_fiesta'
ORIGEN = 'Sonido (biblioteca)'
SR = 48000
LIB_PROPIA = Path(__file__).resolve().parent.parent / '5_SFX'   # v5.48: la biblioteca vive en la carpeta de CineCaptions (fuera de Git)
LIB_AUTOR = Path.home() / 'Desktop' / 'SFX'                     # enlace a 5_SFX (la skill la encuentra aquí)
INCLUIDA = 'biblioteca_sonido'                                   # v5.56: la copia curada que viaja en el .exe (base_recursos() / INCLUIDA)
AUDIO_EXT = ('.wav', '.mp3', '.aif', '.aiff', '.flac', '.ogg', '.m4a')
VERSION = 1

# ---------------------------------------------------------------------------------------------------- reglas (iguales a la skill)
REGLAS = {
    'gancho': ('riser', 10), 'logo': ('impacto', 9), 'aro': ('kinetic', 8), 'flash': ('flash', 8),
    'glitch': ('glitch', 7), 'barrido_luz': ('shine', 7), 'tachado': ('error', 7), 'notificacion': ('notif', 7),
    'boton_on': ('boton_on', 7), 'boton_off': ('boton_off', 7), 'acento': ('acento', 7),
    'neon': ('ding', 6), 'numero_precio': ('dinero', 6), 'check': ('boton_on', 6), 'cursor_click': ('mouse', 6),
    'barra_carga': ('carga', 6), 'positivo': ('positivo', 6), 'negativo': ('error', 6), 'corte_fuerte': ('whoosh', 6),
    'transicion': ('whoosh', 6), 'grafica': ('ding', 5), 'pagina': ('pagina', 5), 'corte': ('swoosh', 5),
    'tarjeta': ('tarjeta', 4), 'icono': ('burbuja', 4), 'foto': ('burbuja', 4), 'texto_grande': ('pop', 3),
    'texto_chico': ('pop', 1), 'golpe_ref': ('pop', 2), 'aparicion': ('pop', 2),
}
POOLS = {
    'riser': r'01_INTRO_RISER/', 'whoosh': r'WHOOSH_TRANSICIONES - Whoosh \d', 'swoosh': r'Swoosh corto',
    'flash': r'FLASH camara', 'pop': r'CAPTIONS_TAP_TECLEO - (TAP_POP|POP \d)', 'acento': r'ACENTO \d',
    'kinetic': r'KINETIC', 'shine': r'SHINE_BARRIDO_LUZ - Shine', 'ding': r'DING neon',
    'burbuja': r'POP_BURBUJA_UI - (Burbuja \d|UI pop \d)', 'tarjeta': r'UI tarjeta \d', 'boton_on': r'ACTIVAR ON',
    'boton_off': r'DESACTIVAR OFF \d', 'mouse': r'CLICK MOUSE', 'notif': r'NOTIFICACION celular',
    'dinero': r'07_DINERO/', 'positivo': r'POSITIVO/', 'error': r'ERROR/', 'impacto': r'IMPACTO_LOGO',
    'carga': r'CARGA corta', 'pagina': r'PAPEL_PAGINA - Pagina \d', 'glitch': r'GLITCH - Glitch \d',
}
ESTILO = {'elegante': {'max10': 7, 'gap_pop': 0.6, 'chicos': False}, 'dinamico': {'max10': 11, 'gap_pop': 0.5, 'chicos': False},
          'lista': {'max10': 11, 'gap_pop': 0.5, 'chicos': False}, 'cinetica': {'max10': 16, 'gap_pop': 0.5, 'chicos': True}}
NOMBRE_ESTILO = {'auto': 'Automático', 'elegante': 'Elegante', 'dinamico': 'Dinámico', 'lista': 'Lista', 'cinetica': 'Tipografía cinética'}
NIVEL = {'INTRO_RISER': -6, 'WHOOSH_TRANSICIONES': -8, 'CAPTIONS_TAP_TECLEO': -10, 'SHINE_BARRIDO_LUZ': -11, 'CLICK_BOTONES_UI': -10,
         'POSITIVO_NEGATIVO': -10, 'DINERO': -9, 'GRITOS_EMOCION': -20, 'BEBIDAS_DESTAPAR': -10, 'AMBIENTE_PLAYA': -22,
         'INFANTIL_RISAS_PANDERETA': -18, 'POP_BURBUJA_UI': -11, 'IMPACTO_LOGO': -7, 'CARGA_PROGRESO': -12, 'GLITCH': -10, 'PAPEL_PAGINA': -10}
OFFSET_VOZ = -3.0          # con voz, todos los SFX 3 dB más bajos (el STEM queda ~10 dB bajo la voz)
PISTA = {'golpe': 'AI SFX IMPACTS', 'whoosh': 'AI SFX MOTION', 'riser': 'AI SFX MOTION', 'trazo': 'AI SFX TEXTURE', 'acento': 'AI SFX TONAL',
         'tick': 'AI SFX UI', 'pop': 'AI SFX UI', 'glitch': 'AI SFX TEXTURE', 'papel': 'AI SFX TEXTURE', 'flash': 'AI SFX MOTION',
         'dinero': 'AI SFX TONAL', 'carga': 'AI SFX MOTION'}
POOL_A_TIPO = {'riser': 'riser', 'whoosh': 'whoosh', 'swoosh': 'whoosh', 'flash': 'flash', 'pop': 'pop', 'acento': 'acento', 'kinetic': 'trazo',
               'shine': 'acento', 'ding': 'acento', 'burbuja': 'pop', 'tarjeta': 'pop', 'boton_on': 'tick', 'boton_off': 'tick', 'mouse': 'tick',
               'notif': 'acento', 'dinero': 'dinero', 'positivo': 'acento', 'error': 'acento', 'impacto': 'golpe', 'carga': 'carga',
               'pagina': 'papel', 'glitch': 'glitch'}
REGLAS_CC = {'pegatina': ('burbuja', 6), 'sube': ('swoosh', 6), 'barrido_kit': ('whoosh', 7), 'tarjeta_kit': ('tarjeta', 6),
             'logo_kit': ('shine', 8)}   # tipos que solo existen en CineCaptions (Tema 1 y su kit neón); REGLAS sigue igual a la skill
DINERO_RX = r'(\$|€|₹|\b(dinero|precio|gratis|gratuit\w*|money|dollars?|price|free|cost\w*|pesos?|quetzal(es)?|millon\w*|millón)\b)'   # palabras ENTERAS: «Quetzaltenango» no es dinero
# v5.48 — lo aprendido de 70 videos de creadores (skill, apoyo_decision.py 2026-10-26): densidad por estilo, 4 sonidos por tipo con tope,
# solo sonidos curados (los extraídos de los creadores suenan pobres en un video nuevo) y lo que el usuario APROBÓ pesa 5×
REFS_CREADORES = Path.home() / '.sonorizar-sfx' / 'datos' / 'refs.json'     # lo escribe la skill (autoentreno.py); sin él, la tabla
DENSIDAD_ESTILO = {'elegante': 0.6, 'dinamico': 1.0, 'lista': 1.0, 'cinetica': 1.4}   # SFX por segundo si no hay datos de creadores
MIN_REFS_ESTILO = 5
APROBADOS = '_datos_catalogo/aprobados.json'      # {"csv": [líneas de tiempo que el usuario aprobó]} en la biblioteca
VARIANTES_POR_ROL, TOPE_REPETIR = 3, 0.40         # 1 principal + 3 de otras familias; ningún archivo en más del 40 % de su tipo
RESPALDO = {'boton_on': 'mouse', 'boton_off': 'mouse', 'mouse': 'pop', 'kinetic': 'pop', 'shine': 'ding', 'ding': 'shine', 'flash': 'swoosh',
            'carga': 'pop', 'notif': 'ding', 'riser': 'swoosh', 'acento': 'pop', 'tarjeta': 'burbuja'}   # pool de 1 familia → el vecino
_DENS = {}
SIEMPRE_SU_SONIDO = ('kinetic', 'boton_on')   # MAPA: «el KINETIC va en TODO caption con aro»; un interruptor suena a interruptor (variantes: rotar)


def _prefs():
    try:
        import ajustes_ui
        return ajustes_ui.leer_prefs() or {}
    except Exception:
        return {}


def poner_pref(**cambios):
    import ajustes_ui
    ajustes_ui.guardar_prefs(cambios)


def activo(prefs=None):
    return (prefs if prefs is not None else _prefs()).get(PREF_ON, True) is True


def log(texto, nivel='info'):
    try:
        import registro
        registro.anotar(nivel, '[SONIDO] ' + str(texto), ORIGEN)
    except Exception:
        pass


def biblioteca(prefs=None):
    p = (prefs if prefs is not None else _prefs()).get(PREF_LIB)
    if p and (Path(p) / '01_SFX').is_dir():                    # v5.56: una carpeta elegida sin 01_SFX no tapa a las demás
        return Path(p)
    # v5.88: en la Mac NO se mira ~/Desktop/SFX (solo existe en el equipo del autor, que es Windows): tocar el Escritorio saca el aviso de
    # macOS «CineCaptions quiere acceder a los archivos de tu carpeta Escritorio» en el primer GO de cada cliente
    for lib in (LIB_PROPIA, lib_incluida()) if sys.platform == 'darwin' else (LIB_PROPIA, LIB_AUTOR, lib_incluida()):
        if (lib / '01_SFX').is_dir():
            return lib
    import director_sonido_estado as E
    return E.CARPETA / 'biblioteca'


def lib_incluida():
    """v5.56 (el usuario: «los SFX ya deben de venir en el exe»): los sonidos curados que viajan con el programa. Antes el .exe solo miraba
    5_SFX y Desktop\\SFX: con el enlace del Escritorio roto salían 0 sonidos y el Tema 1 se quedaba sin ninguno."""
    import sfx_rules
    return sfx_rules.base_recursos() / INCLUIDA


_DISPONIBLE = {}


def disponible(prefs=None):
    """¿Hay una biblioteca de la que salen sonidos (algún grupo de POOLS con archivos curados)? Sin ella GO se queda con los sonidos de siempre (no
    los apaga para no poner nada). Se recuerda por carpeta y fecha de su 01_SFX y de su catálogo."""
    lib = biblioteca(prefs)
    try:
        firma = (str(lib), (lib / '01_SFX').stat().st_mtime, (lib / 'catalogo_sfx.json').stat().st_mtime if (lib / 'catalogo_sfx.json').is_file() else 0)
    except OSError:
        return False
    if firma not in _DISPONIBLE:
        try:
            _DISPONIBLE[firma] = any(pools_de(catalogo(lib), lib).values())
        except Exception:
            _DISPONIBLE[firma] = False
    return _DISPONIBLE[firma]


# ---------------------------------------------------------------------------------------------------- audio (PyAV, ya va en el programa)
def leer_audio(ruta, sr=SR):
    """float32 (2, n) a 48 kHz."""
    import av
    with av.open(str(ruta)) as cont:
        rs = av.AudioResampler(format='fltp', layout='stereo', rate=sr)
        trozos = []
        for fr in cont.decode(audio=0):
            for r in rs.resample(fr) or []:
                trozos.append(r.to_ndarray())
        for r in rs.resample(None) or []:
            trozos.append(r.to_ndarray())
    return np.concatenate(trozos, axis=1).astype(np.float32) if trozos else np.zeros((2, 0), np.float32)


def medir(ruta):
    x = leer_audio(ruta, 8000)
    if not x.shape[1]:
        return None
    m = np.abs(x).max(axis=0)
    env = np.array([m[i:i + 80].max() for i in range(0, max(1, len(m) - 80), 80)])
    mx = float(env.max()) or 1e-9
    aud = np.nonzero(env > mx * 0.03)[0]
    return {'duracion': round(len(m) / 8000, 3), 'pico': round(float(env.argmax()) * 0.01, 3),
            'fin_audible': round((aud[-1] + 1) * 0.01 if aud.size else len(m) / 8000, 3), 'max_db': round(20 * math.log10(mx), 1)}


def _categoria(rel):
    partes = rel.split('/')
    base = partes[1] if partes[0] == '01_SFX' and len(partes) > 2 else partes[0]
    return base.split('_', 1)[1] if '_' in base and base[:1].isdigit() else base


def catalogo(lib=None):
    """{ruta_relativa: {duracion, pico, fin_audible, max_db, categoria, nivel_db}}: el de la skill si existe; si no, medido y en caché."""
    lib = Path(lib or biblioteca())
    import archivos_seguros
    propio = lib / 'catalogo_sfx.json'
    if propio.is_file():
        d = archivos_seguros.leer_json(propio, None)
        if isinstance(d, dict) and d:
            return d
    import director_sonido_estado as E
    cache = E.CARPETA / 'cache' / 'catalogo_biblioteca.json'
    d = archivos_seguros.leer_json(cache, None)
    firma = str(sorted((p.name, int(p.stat().st_mtime)) for p in (lib / '01_SFX').glob('*'))) if (lib / '01_SFX').is_dir() else ''
    if isinstance(d, dict) and d.get('lib') == str(lib) and d.get('firma') == firma:
        return d['cat']
    cat = {}
    for ruta in sorted((lib / '01_SFX').rglob('*')) if (lib / '01_SFX').is_dir() else []:
        if ruta.suffix.lower() not in AUDIO_EXT or any(p.startswith('.') for p in ruta.parts):
            continue
        try:
            info = medir(ruta)
        except Exception:
            info = None
        if info:
            rel = ruta.relative_to(lib).as_posix()
            c = _categoria(rel)
            cat[rel] = dict(info, categoria=c, nivel_db=NIVEL.get(c, -10))
    archivos_seguros.escribir_json(cache, {'lib': str(lib), 'firma': firma, 'cat': cat})
    return cat


# ---------------------------------------------------------------------------------------------------- eventos desde la metadata de GO
def _tipo_pieza(nombre):
    n = str(nombre or '').lower()
    for clave, tipo in (('glitch', 'glitch'), ('logo', 'logo'), ('notif', 'notificacion'), ('whatsapp', 'notificacion'), ('check', 'check'),
                        ('toggle', 'boton_on'), ('interruptor', 'boton_on'), ('switch', 'boton_on'), ('cursor', 'cursor_click'),
                        ('barra', 'barra_carga'), ('progreso', 'barra_carga'), ('progress', 'barra_carga'), ('mapa', 'barra_carga'),
                        ('ruta', 'barra_carga'), ('precio', 'numero_precio'), ('dinero', 'numero_precio'), ('moneda', 'numero_precio'),
                        ('money', 'numero_precio'), ('calendario', 'pagina'), ('pagina', 'pagina'), ('papel', 'pagina'), ('neon', 'neon'),
                        ('barrido', 'barrido_luz'), ('brillo', 'barrido_luz'), ('flash', 'flash'), ('grafic', 'grafica'), ('chart', 'grafica'),
                        ('tache', 'tachado'), ('cruz', 'negativo'), ('error', 'negativo'), ('perfil', 'tarjeta'), ('tarjeta', 'tarjeta'),
                        ('card', 'tarjeta'), ('foto', 'foto'), ('icono', 'icono'), ('icon', 'icono')):
        if clave in n:
            return tipo
    return 'tarjeta'


HEROE_GOLPE = 0.0                 # Tema 1: el pop del héroe va en el PRIMER cuadro de su entrada (antes en p≈0,37 del rebote: +0,12 s, «llega tarde»)
GANCHO_MIN = 0.45                 # lo que necesita un riser para subir antes del primer momento
CORTE_MIN = 0.3                   # un «corte» antes de esto es el comienzo del video, no un corte


def cues_kinetic(ctx):
    """Tema 1 (pack Kinetic): sus bloques con los ELEMENTOS que anima cada uno y cuándo entran (`runs`: k hero/ring/line/tape/label/serif/
    script con su t), del .kinetic.json que GO escribe en DaVinciSubtitles (`{video}.{idioma}.kinetic.json`). Solo si sus bloques coinciden con
    los de este GO (si no, None y se sigue con la metadata general)."""
    if 'kinetic' not in str(ctx.get('pack') or '').lower() or not ctx.get('video'):
        return None
    carpeta, stem = Path.home() / 'DaVinciSubtitles', Path(ctx['video']).stem
    rutas = [carpeta / f"{stem}.{ctx.get('idioma')}.kinetic.json"] + sorted(carpeta.glob(f'{glob_escape(stem)}.*.kinetic.json'),
                                                                           key=lambda p: -p.stat().st_mtime)
    bloques = ctx.get('bloques') or []
    for ruta in rutas:
        try:
            cues = json.loads(ruta.read_text(encoding='utf-8')).get('cues') or []
        except Exception:
            continue
        if cues and len(cues) == len(bloques) and all(abs(float(c['start']) - float(b['start'])) < 0.05 for c, b in zip(cues, bloques)):
            return cues
    return None


def glob_escape(texto):
    import glob
    return glob.escape(texto)


def etiquetas_tema1(cues, frases):
    """Tema 1: el tema no cambia, así que cada bloque suena siempre igual según lo que anima, con las reglas de la biblioteca
    (03_CAPTIONS_TAP_TECLEO/TEMA_1/00_REGLAS_DE_USO.txt y MAPA_SFX.md): UN sonido por bloque — si se dibuja un ARO o SUBRAYADO, el KINETIC
    (va en TODO caption con aro; empieza cuando el aro empieza a dibujarse); si no, el pop del HÉROE en el primer cuadro de su entrada; si solo hay PEGATINA, su
    pop. Las líneas chicas (label, serif) y la palabra a mano (script) no suenan. El dinero solo si la palabra es de dinero de verdad."""
    import director_sonido_eventos as EV
    ev = []
    for c in cues:
        runs = c.get('runs') or []
        texto = ' '.join(str(r.get('texto')) for r in runs if r.get('texto'))[:60]
        trazo = next((r for r in runs if str(r.get('k') or '').startswith(('k ring', 'k line'))), None)
        heroe = next((r for r in runs if str(r.get('k') or '').startswith('k hero')), None)
        cinta = next((r for r in runs if str(r.get('k') or '').startswith('k tape')), None)
        if trazo:
            ev.append({'segundo': round(float(trazo['t']), 3), 'tipo': 'aro', 'fuerza': 9,
                       'detalle': f"Estilo 1: {'aro' if 'ring' in str(trazo['k']) else 'subrayado'} que se dibuja · «{texto}»"})
        elif heroe:
            t, palabra = float(heroe['t']), str(heroe.get('texto') or '')[:30]
            rol, importancia, _ = EV._rol_en(frases, t) if frases else ('EXPLANATION', 0.3, '')
            tipo = 'numero_precio' if re.search(DINERO_RX, palabra.lower()) else 'texto_grande'
            ev.append({'segundo': round(t + HEROE_GOLPE, 3), 'tipo': tipo, 'detalle': f'Estilo 1: héroe «{palabra}» ({rol})',
                       'fuerza': round(8 + 5 * (EV.PESO_ROL.get(rol, 0.0) + float(importancia)), 2)})
        elif cinta:
            ev.append({'segundo': round(float(cinta['t']), 3), 'tipo': 'pegatina', 'detalle': f"Estilo 1: pegatina «{str(cinta.get('texto') or '')[:30]}»",
                       'fuerza': 8})
    return ev


def motions_neon(plan_pro):
    """Los motions del kit neón del Tema 1: `kitneon_motions` del plan de la PRO o, si solo quedan las piezas ya armadas, sus escenas."""
    pro = plan_pro if isinstance(plan_pro, dict) else {}
    if pro.get('kitneon_motions'):
        return pro['kitneon_motions']
    out = []
    for p in pro.get('piezas') or []:
        if isinstance(p, dict) and p.get('pieza') == 'neon_motion' and not p.get('quitar'):
            val = p.get('valores') if isinstance(p.get('valores'), dict) else {}
            esc = (val.get('escena') or [{}])[0] if isinstance(val.get('escena'), list) else {}
            a = esc.get('a') if isinstance(esc.get('a'), dict) else ({'_args': esc['args']} if esc.get('args') else {})
            out.append({'fn': esc.get('fn'), 'a': a, 'ini': float(p.get('ini') or 0.0)})
    return out


def etiquetas_neon(motions):
    """Tema 1 con Edición PRO: los MOTIONS del kit neón (`plan_pro['kitneon_motions']`, kit_neon_motions.escena_motions) con sus tiempos
    internos. Cada pieza suena siempre igual, calibrado con la línea de tiempo que el usuario APROBÓ para SOLO VOZ (el mismo kit):
    notificación que baja → NOTIFICACION · tarjeta que sube / tarjeta de ruta / interruptores → swoosh corto ·
    barrido → whoosh (0,1 s antes de su centro) · órbita, avatares, chips y etiquetas → burbuja · cada interruptor → ACTIVAR ON · (todo en el PRIMER cuadro de su animación) la ruta que
    se dibuja → CARGA y el último hito → POSITIVO · tarjetas en cascada → UI tarjeta (cada 0,2 s) · checks → ACTIVAR ON y el último POSITIVO ·
    logo de cierre → SHINE. El avión y el degradado de fondo no suenan (van pegados a otro sonido)."""
    ev = []

    def poner(t, tipo, que):
        if t is not None:
            ev.append({'segundo': round(float(t), 3), 'tipo': tipo, 'detalle': f'motion Estilo 1: {que}', 'fuerza': 8})

    for m in motions or []:
        fn, a, ini = m.get('fn'), m.get('a') or {}, float(m.get('ini') or 0.0)
        args = a.get('_args') or []
        if fn == 'notificacion':
            poner(ini, 'notificacion', 'notificación baja')
        elif fn == 'tarjetaInferior':
            poner(ini, 'sube', 'tarjeta sube')
        elif fn == 'barrido' and args:
            poner(float(args[0]) - 0.1, 'barrido_kit', 'barrido de transición')
        elif fn == 'orbita':
            poner(a.get('tin', ini), 'pegatina', 'íconos en órbita')
        elif fn == 'avataresArco':
            poner(a.get('t0', ini), 'pegatina', 'avatares')
        elif fn == 'interruptores':
            poner(a.get('tin', ini), 'sube', 'tarjeta de opciones')
            for fila in a.get('filas') or []:
                poner(float(fila[-1]), 'boton_on', f'interruptor «{fila[0]}» ON')
            if a.get('tDerecha') is not None:
                poner(float(a['tDerecha']), 'pegatina', f"chip «{a.get('etiqueta') or ''}»")
        elif fn == 'lineaIcono':
            poner(a.get('tin', ini), 'pegatina', f"chip «{a.get('texto') or ''}»")
        elif fn in ('etiquetas', 'filaEtiqueta'):
            for it in a.get('items') or []:
                if isinstance(it, (list, tuple)) and it and isinstance(it[-1], (int, float)):
                    poner(it[-1], 'pegatina', f"etiqueta «{it[1] if len(it) > 2 else ''}»")
        elif fn == 'tarjetaRuta':
            poner(a.get('tin', ini), 'sube', 'tarjeta de ruta')
            poner(float(a.get('tin', ini)) + 0.3, 'barra_carga', 'la ruta se dibuja')
            hitos = [float(h[-1]) for h in a.get('hitos') or [] if isinstance(h, (list, tuple)) and h]
            if hitos:
                poner(max(hitos), 'positivo', 'ruta completa: el pin')
        elif fn == 'tarjetasProducto':
            for k in range(len(a.get('contenidos') or a.get('rects') or [])):
                poner(float(a.get('tin', ini)) + 0.2 * k, 'tarjeta_kit', f'tarjeta {k + 1} en cascada')
        elif fn == 'checks':
            items = [it for it in a.get('items') or [] if isinstance(it, (list, tuple)) and it]
            for k, it in enumerate(items):
                ultimo = k == len(items) - 1 and len(items) > 1
                poner(float(it[-1]), 'positivo' if ultimo else 'check', f'check «{str(it[0])[:30]}»')
        elif fn == 'logoCierre':
            poner(a.get('t', ini), 'logo_kit', 'logo de cierre (brillo)')
    return ev


def etiquetas_de_go(ctx):
    """Los eventos que GO ya conoce, con su tipo de MAPA_SFX.md: [{'segundo', 'tipo', 'detalle', 'fuerza'}]."""
    import director_sonido_eventos as EV
    dur = None
    ev = []
    kin = cues_kinetic(ctx)
    if kin:
        try:
            frases = EV.narrativa(ctx.get('palabras') or [], dur).get('frases') or []
        except Exception:
            frases = []
        ev = etiquetas_tema1(kin, frases)
    caps = [] if kin else EV.captions(ctx.get('bloques') or [], dur).get('lista') or []
    tam = [c.get('tamano') or c.get('escala_clave') or 0 for c in caps]
    grande = float(np.percentile([t for t in tam if t] or [1], 60))
    try:
        frases = EV.narrativa(ctx.get('palabras') or [], dur).get('frases') or []
    except Exception:
        frases = []
    for c in caps:
        anim = [str(a) for a in c.get('animacion') or []]
        sonidos = [float(s['t']) for s in c.get('sonidos') or [] if s.get('t') is not None]
        t = sonidos[0] if sonidos else float(c['ini'])      # donde Simple ponía su toque = cuando sale la palabra clave
        texto = (c.get('clave') or c.get('texto') or '')[:40]
        rol, importancia, _ = EV._rol_en(frases, t) if frases else ('EXPLANATION', 0.3, '')
        peso = EV.PESO_ROL.get(rol, 0.0) + float(importancia)
        v = c.get('tamano') or c.get('escala_clave') or 0
        if any(a.startswith(('k ring trazo', 'k ring lazo', 'k line trazo')) for a in anim):
            ev.append({'segundo': t, 'tipo': 'aro', 'detalle': f'«{texto}» con aro', 'fuerza': 9})
            continue
        if any('shatter' in a for a in anim):
            tipo = 'acento'
        elif any('drag' in a for a in anim):
            tipo = 'corte'
        elif any('select' in a for a in anim):
            tipo = 'check'
        elif any(a.startswith('k hero') for a in anim):
            tipo, t = 'texto_grande', t + 10 / 30 * 0.37         # el héroe llega a su tamaño en p≈0,37 de 10 f
        else:
            tipo = 'texto_grande' if (v and v >= grande) or (not v and c.get('clave')) else 'texto_chico'
        if re.search(DINERO_RX, (c.get('clave') or '').lower()) or (rol == 'DATA' and re.search(DINERO_RX, (c.get('texto') or '').lower())):
            tipo = 'numero_precio'
        ev.append({'segundo': round(t, 3), 'tipo': tipo, 'detalle': f'caption «{texto}» ({rol})',
                   'fuerza': round(5 + 10 * float(v or 0) + 5 * peso, 2)})
    neon = motions_neon(ctx.get('plan_pro'))
    ev += etiquetas_neon(neon)
    mot = EV.motions(ctx.get('plan_efectos'), ctx.get('plan_pro'), dur).get('lista') or []
    fx = {'corte': 'corte', 'icono': 'icono', 'numero': 'grafica', 'pegatina': 'icono', 'enfasis': 'acento', 'broll': 'corte'}
    for m in mot:
        if m['origen'] == 'kit neón' and neon:
            continue                                        # ya sonó con sus tiempos internos (etiquetas_neon)
        if m['origen'] == 'Efectos':
            tipo = fx.get(m['pieza'])
            if not tipo:
                continue                                    # intro / outro / overlay / propio: van con su animación y su sonido
        elif m['origen'] == 'kit neón':
            tipo = 'barrido_luz' if 'barr' in str(m.get('kit') or '') else 'neon'
        else:
            tipo = _tipo_pieza(f"{m.get('pieza')} {m.get('asset')}")
        ev.append({'segundo': round(float(m['ini']), 3), 'tipo': tipo, 'detalle': f"{m['origen']}: {m.get('asset') or m.get('pieza')}",
                   'fuerza': 7})
    # Tema 1 SOLO CAPTIONS: cada sonido sale de un caption; los cortes del video NO suenan (el usuario: «estás confundiendo el Tema 1 solo
    # captions con el PRO, hay sonidos donde no deberían ir»). Un corte suena si lo pide quien lo anima: las transiciones de Efectos (ya
    # vienen arriba como 'corte') o los barridos de la PRO (etiquetas_neon). Los otros temas siguen con los cortes que detecta GO.
    for t in ([] if kin else ctx.get('cortes') or []):
        if float(t) >= CORTE_MIN:
            ev.append({'segundo': round(float(t), 3), 'tipo': 'corte', 'detalle': 'corte del video', 'fuerza': 6})
    return sorted(ev, key=lambda e: e['segundo'])


def estilo_de_pack(pack):
    p = str(pack or '').lower()
    if 'viral' in p:
        return 'cinetica'
    if any(k in p for k in ('referencia', 'guion', 'luxe', 'elegan')):
        return 'elegante'
    return 'dinamico'


def intro_con_sonido(ctx):
    return any(e.get('tipo') == 'sonido' and e.get('ini') is not None and float(e['ini']) < 1.0
               for e in ((ctx.get('plan_efectos') or {}).get('eventos') or []))


# ---------------------------------------------------------------------------------------------------- el motor (igual a la skill)
HECHO_POR_IA = ('/_VARIANTES/', '/_SINTETIZADOS/')   # además del campo 'generado' del catálogo (variante | sintetizado | tema)


def hecho_por_ia(rel, info=None):
    """Sonido que hizo una máquina y no es una grabación real: variantes de tono, sintetizados y los de temas armados por la skill.
    El usuario (2026-10-27): «NO USES SONIDOS CREADOS POR IA»."""
    return bool((info or {}).get('generado')) or any(m in '/' + rel.replace('\\', '/') for m in HECHO_POR_IA)


def curado(rel, info=None):
    """¿Sirve para un video nuevo? Nunca los extraídos de los videos de creadores, los crudos de ejercicio ni los hechos por IA."""
    return ('17_EXTRAIDOS_REFERENCIAS' not in rel and '_DE_REFERENCIAS' not in rel and not (info or {}).get('solo_ejercicio')
            and not hecho_por_ia(rel, info))


def densidad_creadores(ruta=None):
    """{estilo: mediana de SFX/s} de los videos de creadores (estilos con ≥ 5 videos) — igual que la skill. {} si no hay datos."""
    ruta = Path(ruta or REFS_CREADORES)
    if str(ruta) not in _DENS:
        try:
            d = json.loads(ruta.read_text(encoding='utf-8'))
            refs = [r for r in (d.values() if isinstance(d, dict) else d) if isinstance(r, dict) and r.get('densidad') is not None]
        except Exception:
            refs = []
        por = {}
        for r in refs:
            por.setdefault(r.get('estilo'), []).append(float(r['densidad']))
        _DENS[str(ruta)] = {e: round(float(np.median(v)), 3) for e, v in por.items() if e and len(v) >= MIN_REFS_ESTILO}
    return _DENS[str(ruta)]


def max10(estilo):
    """Tope de SFX por ventana de 10 s: el MAYOR entre la tabla de ESTILO (elegante 7, dinámico 11, lista 11, cinética 16) y la densidad de
    los creadores en ese estilo. Los videos de CineCaptions llevan un caption cada ~2 s: con solo la densidad de los creadores (dinámico ~7)
    no cabían los cortes y el usuario los oyó «muy pocos» (2026-10-27)."""
    d = densidad_creadores().get(estilo) or DENSIDAD_ESTILO.get(estilo)
    return max(ESTILO[estilo]['max10'], int(round(d * 10)) if d else 0)


def usos_aprobados(lib):
    """{archivo: peso}: cada fila de un CSV aprobado por el usuario suma 5 y cada réplica de creador (EJERCICIO) 1."""
    import csv
    from collections import Counter
    lib = Path(lib)
    c = Counter()
    try:
        aprob = json.loads((lib / APROBADOS).read_text(encoding='utf-8')).get('csv') or []
    except Exception:
        aprob = []
    fuentes = [(p, 1) for p in (lib / '00_REFERENCIAS_CREADORES').glob('*/*/EJERCICIO - linea de tiempo.csv')] + [(Path(p), 5) for p in aprob]
    for p, peso in fuentes:
        try:
            with open(p, encoding='utf-8-sig', newline='') as fh:
                for r in csv.reader(fh):
                    if r and r[0][:1].isdigit() and len(r) > 1:
                        c[r[1].replace('\\', '/')] += peso
        except Exception:
            continue
    return c


def pools_de(cat, lib=None):
    """{pool: [archivos curados]} en orden de preferencia: lo que el usuario aprobó y los creadores usan primero, luego por nombre."""
    usos = usos_aprobados(lib or biblioteca())
    return {k: sorted((r for r in cat if re.search(rx, r) and curado(r, cat[r]) and not (k == 'pop' and any(m in r for m in POP_FUERA))),
                      key=lambda r: (-usos.get(r, 0), r)) for k, rx in POOLS.items()}


class Elector:
    """Igual que la skill: por pool un sonido principal + VARIANTES_POR_ROL de otras familias; nunca la misma familia dos veces seguidas y
    ningún archivo en más del TOPE_REPETIR de los golpes de su pool (en los creadores el más usado cubre 43-57 % y hay 3-4 por tipo)."""

    def __init__(self, pools, familias=None, variantes=VARIANTES_POR_ROL, tope=TOPE_REPETIR):
        from collections import Counter
        self.pools, self.familias, self.variantes, self.tope = pools, familias or {}, variantes, tope
        self.fijos, self.ultimo = {}, None
        self.usos, self.por_pool = Counter(), Counter()

    def fam(self, r):
        return self.familias.get(r) or r

    def lista(self, pool):
        if pool not in self.fijos:
            vistos, fams = [], set()
            for r in self.pools.get(pool) or []:
                if self.fam(r) not in fams:
                    vistos.append(r)
                    fams.add(self.fam(r))
            self.fijos[pool] = vistos[:1 + self.variantes]
        return self.fijos[pool]

    def elegir(self, pool):
        if pool in SIEMPRE_SU_SONIDO and self.pools.get(pool):    # siempre ese sonido: rota sus variantes de tono, sin tope ni vecino
            todos = self.pools[pool]
            arch = todos[self.por_pool[pool] % len(todos)]
            self.usos[arch] += 1
            self.por_pool[pool] += 1
            self.ultimo = arch
            return arch
        lista = self.lista(pool)
        if not lista:
            return None
        ult = self.fam(self.ultimo) if self.ultimo else None
        cand = [r for r in lista if self.fam(r) != ult] or [r for r in self.pools.get(pool) or [] if self.fam(r) != ult]
        if not cand and RESPALDO.get(pool):
            cand = [r for r in self.lista(RESPALDO[pool]) if self.fam(r) != ult]
        if not cand:
            cand = [r for r in lista[1:] + list(self.pools.get(pool) or []) if r != self.ultimo] or lista[:1]
        tope = max(1.0, self.tope * (self.por_pool[pool] + 1))
        dentro = [r for r in cand if self.usos[r] + 1 <= tope]
        if not dentro and RESPALDO.get(pool):
            dentro = [r for r in self.lista(RESPALDO[pool]) if self.fam(r) != ult and self.usos[r] + 1 <= tope]
        arch = dentro[0] if dentro else min(cand, key=lambda r: (self.usos[r], cand.index(r)))
        self.usos[arch] += 1
        self.por_pool[pool] += 1
        self.ultimo = arch
        return arch


def elegir(ev, estilo):
    cfg = dict(ESTILO[estilo], max10=max10(estilo))
    ev = [dict(e) for e in ev if cfg['chicos'] or e['tipo'] != 'texto_chico']
    # Tema 1: el héroe suena SIEMPRE con su pop al entrar; el acento (sube 0,34 s ANTES de la palabra) sonaba sobre las letras chicas que
    # la preceden (el usuario, 50–54 s de ESPAÑOL: «hay sonido que no va» = ACENTO en «PERDER» desde 53,50 s)
    textos = [e for e in ev if e['tipo'] == 'texto_grande' and not str(e.get('detalle') or '').startswith('Estilo 1')]
    ult = -10
    for w in range(0, int(max([e['segundo'] for e in ev] or [0])) + 4, 4):
        grupo = [e for e in textos if w <= e['segundo'] < w + 4]
        if grupo and w - ult >= 8:
            max(grupo, key=lambda e: e['fuerza'])['tipo'] = 'acento'
            ult = w
    out = []
    for e in sorted(ev, key=lambda x: x['segundo']):
        e['pool'], e['prioridad'] = REGLAS.get(e['tipo']) or REGLAS_CC.get(e['tipo'], ('pop', 2))
        if out:
            p = out[-1]
            gap = cfg['gap_pop'] if e['pool'] in ('pop', 'acento') and p['pool'] in ('pop', 'acento') else 0.25
            if e['segundo'] - p['segundo'] < gap:
                if _peso(e) > _peso(p):
                    out[-1] = e
                continue
        out.append(e)
    for e in sorted([e for e in out if e['pool'] == 'impacto'], key=lambda e: -e['fuerza'])[2:]:
        e['pool'], e['tipo'] = 'acento', 'acento'
    cambio = True
    while cambio:
        cambio = False
        for e in out:
            ventana = [x for x in out if e['segundo'] <= x['segundo'] < e['segundo'] + 10]
            if len(ventana) > cfg['max10']:
                out.remove(min(ventana, key=lambda x: (_peso(x), x['fuerza'])))
                cambio = True
                break
    return out


RELLENO = ('corte', 'corte_fuerte', 'transicion', 'icono', 'foto', 'tarjeta', 'golpe_ref', 'aparicion')


def _peso(e):
    """Qué gana al chocar o al pasar del tope. En CineCaptions mandan los CAPTIONS y las piezas con su animación; los cortes, íconos y
    tarjetas son RELLENO y salen primero (el usuario: «no se aplican bien y son muy pocos»: en ESPAÑOL.mov el tope se comía 20 de 33
    palabras clave para dejar swooshes en los cortes). Entre los de un mismo grupo sigue la prioridad de REGLAS."""
    return e['prioridad'] + (0 if e['tipo'] in RELLENO else 10)


def asignar(out, cat, lib=None):
    pools = pools_de(cat, lib)
    el = Elector(pools, {r: i.get('familia') for r, i in cat.items() if isinstance(i, dict) and i.get('familia')})
    filas = []
    for e in out:
        archivo = el.elegir(e['pool'] if pools.get(e['pool']) else 'pop')
        if not archivo:
            continue
        filas.append({'segundo': e['segundo'], 'archivo': archivo, 'tipo': e['tipo'], 'pool': e['pool'], 'por_que': e['detalle']})
        ts = round(e['segundo'] + 0.55, 3)
        if e['pool'] == 'impacto' and pools['shine'] and all(abs(x['segundo'] - ts) >= 0.25 for x in out):   # nunca dos SFX a < 0,25 s
            filas.append({'segundo': ts, 'archivo': el.elegir('shine'), 'tipo': 'barrido_luz', 'pool': 'shine',
                          'por_que': 'brillo después del impacto (logo)'})
    return filas


def recorte(info, dur=None):
    if dur:
        return dur
    if info['categoria'] == 'WHOOSH_TRANSICIONES' and info['duracion'] > 2.5:
        return info['pico'] + 1.0
    if info['duracion'] > 3.0:
        return min(info['fin_audible'], info['pico'] + 1.5)
    if info['duracion'] - info['fin_audible'] > 0.3:
        return info['fin_audible'] + 0.15
    return info['duracion']


def _escribir_wav(destino, x):
    y = np.clip(x.T, -1.0, 1.0)
    with wave.open(str(destino), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((y * 32767).astype('<i2').tobytes())


# Pulido de los sonidos que más se repiten en un video de captions (2026-10-27, el usuario: «los aros… bájale el sonido y hazlo variado para
# que no se repita siempre exactamente; en el texto principal, tap o pop, mejóralo»). Medido: el KINETIC es casi todo siseo (timbre ~10 kHz)
# y sonaba al nivel de la voz; los pops buenos son cortos y medios (900–1300 Hz). Cada sonido sale con su propio tono, nivel y brillo
# (azar fijo por sonido: rehacer da lo mismo) y sin graves sucios.
#   nivel   dB sobre el nivel de su categoría   tono  ±% de velocidad   db  ±dB al azar   agudos  corte de agudos (Hz) entre min y max
#   graves  corte de graves (Hz)                fundido  fundido final (s)
PULIDO = {
    'kinetic': {'nivel': -9.0, 'tono': 0.035, 'db': 1.5, 'agudos': (6000, 9500), 'graves': 180, 'fundido': 0.12},
    'pop': {'nivel': -1.5, 'tono': 0.04, 'db': 1.0, 'agudos': (9000, 14000), 'graves': 140, 'fundido': 0.05},
    'acento': {'nivel': -1.0, 'tono': 0.025, 'db': 0.8, 'agudos': (10000, 15000), 'graves': 110, 'fundido': 0.08},
}
POP_FUERA = ('CAPTIONS_TAP_TECLEO - POP 3',)   # golpe grave (174 Hz) con cola de 0,22 s: suena a tocar una puerta, no a pop de caption


def _filtrar(x, graves, agudos):
    """Corte de graves y de agudos suave en el dominio de frecuencia (rápido para sonidos de < 1 s)."""
    n = x.shape[1]
    if n < 64:
        return x
    X = np.fft.rfft(x, axis=1)
    f = np.fft.rfftfreq(n, 1 / SR)
    h = 1.0 / np.sqrt(1.0 + (graves / np.maximum(f, 1.0)) ** 4)        # paso alto de 2.º orden
    h *= 1.0 / np.sqrt(1.0 + (f / agudos) ** 2)                         # paso bajo de 1.er orden
    return np.fft.irfft(X * h, n=n, axis=1).astype(np.float32)


def pulir(x, p, semilla):
    """(x, variación en dB): tono, brillo y nivel propios para ESTE sonido (azar fijo por la semilla) + el nivel de su categoría."""
    import hashlib
    rng = np.random.default_rng(int(hashlib.sha1(semilla.encode('utf-8')).hexdigest()[:12], 16))
    factor = 1.0 + float(rng.uniform(-p['tono'], p['tono']))
    if abs(factor - 1.0) > 0.002:
        n = max(1, int(x.shape[1] / factor))
        pos = np.linspace(0, x.shape[1] - 1, n)
        x = np.stack([np.interp(pos, np.arange(x.shape[1]), c) for c in x]).astype(np.float32)
    x = _filtrar(x, p['graves'], float(rng.uniform(*p['agudos'])))
    return x, p['nivel'] + float(rng.uniform(-p['db'], p['db']))


SYNC_CATALOGO = ('whoosh', 'swoosh', 'riser', 'acento', 'impacto', 'flash')   # suben hacia el momento: su pico/fin cae en el cuadro
ARRANCAN_CON_LA_ANIMACION = ('sube',)   # tarjeta que sube: el swoosh acompaña el movimiento desde su primer cuadro (no se adelanta como al corte)
UMBRAL_INICIO = 0.03          # primer instante que se oye: 3 % del pico (−30 dB)


def sin_silencio_inicial(x):
    """(audio sin el silencio del comienzo, segundos quitados). Deja 2 ms antes del primer sonido y un fundido de entrada de 2 ms (sin clic)."""
    m = np.abs(x).max(axis=0)
    pk = float(m.max()) if m.size else 0.0
    if pk <= 0:
        return x, 0.0
    k = max(0, int(np.argmax(m > pk * UMBRAL_INICIO)) - int(0.002 * SR))
    if not k:
        return x, 0.0
    y = x[:, k:].copy()
    n = min(int(0.002 * SR), y.shape[1])
    y[:, :n] *= np.linspace(0.0, 1.0, n, dtype=np.float32)
    return y, k / SR


def hornear(filas, cat, lib, carpeta, con_voz=True):
    """Cada SFX recortado, con fundido y su nivel dentro del archivo (Resolve ignora el volumen de clip por script)."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    eventos, previo, repeticion = [], None, 0
    for i, f in enumerate(filas):
        info = cat[f['archivo']]
        dur = recorte(info, f.get('duracion'))
        x = leer_audio(Path(lib) / f['archivo'])[:, :int(dur * SR)]
        # lo que cae en el cuadro del evento es el PUNTO DE SYNC del catálogo (ataque, pico o fin según el sonido: un riser termina en el
        # evento), igual que la skill; antes era siempre el pico (hasta 5 cuadros de error en un riser)
        sync = float(info.get('punto_sync', info['pico']) or 0.0)
        x, inicio = sin_silencio_inicial(x)                     # fuera los milisegundos vacíos del archivo: el clip empieza sonando
        # lo que APARECE (pop, aro, burbuja, notificación, interruptor, check, tarjeta…) suena desde el primer cuadro de su animación: va el
        # PRIMER sonido audible, no su pico (el usuario: «el video pasa y el sonido después… que empiece justo en la animación»). Los que
        # suben HACIA el momento (whoosh al corte, riser, acento, impacto) siguen con el punto de sync del catálogo.
        sync = max(0.0, sync - inicio) if f['pool'] in SYNC_CATALOGO and f['tipo'] not in ARRANCAN_CON_LA_ANIMACION else 0.0
        antes = sync - float(f['segundo'])
        if antes > 0:                                           # empezaría antes del 0: se recorta el comienzo, el sync sigue en su cuadro
            x = x[:, int(antes * SR):]
            sync -= antes
        if not x.shape[1]:
            x = np.zeros((2, int(0.05 * SR)), np.float32)       # nunca saltar: sfx_plan[i] va con filas[i]
        variacion_db = 0.0
        repeticion = repeticion + 1 if f['archivo'] == previo else 0
        previo = f['archivo']
        pulido = PULIDO.get(f['pool'])
        if pulido:                                              # aros y pops de caption: cada uno distinto y más limpio (ver PULIDO)
            x, variacion_db = pulir(x, pulido, f"{f['archivo']}|{i}|{f['segundo']}")
        elif repeticion:                                        # el mismo archivo seguido: microvariación (tono ±3 %, ±0,7 dB) para que no suene clonado
            factor = 1.0 + 0.03 * (1 if repeticion % 2 else -1)
            n = int(x.shape[1] / factor)
            pos = np.linspace(0, x.shape[1] - 1, n)
            x = np.stack([np.interp(pos, np.arange(x.shape[1]), c) for c in x]).astype(np.float32)
            variacion_db = 0.7 if repeticion % 2 else -0.7
        fade = min(int((pulido or {}).get('fundido', 0.2) * SR), x.shape[1])
        x[:, -fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
        g = (info['nivel_db'] - info['max_db'] + (OFFSET_VOZ if con_voz else 0.0) + float(f.get('ganancia_db') or 0.0) + variacion_db)
        x *= 10 ** (g / 20)
        pk = float(np.abs(x).max() or 1)
        if pk > 0.89:
            x *= 0.89 / pk
        destino = carpeta / f"sfx_{i:03d}_{f['pool']}.wav"
        _escribir_wav(destino, x)
        tipo = POOL_A_TIPO.get(f['pool'], 'pop')
        eventos.append({'tipo': 'sonido', 'pista': PISTA.get(tipo, 'AI SFX UI'), 'ini': round(max(0.0, f['segundo'] - sync), 3),
                        'dur': round(x.shape[1] / SR, 3), 'archivo': str(destino), 'asset': f"{f['tipo']} · {Path(f['archivo']).stem}"[:80],
                        'pico': round(sync, 3), 'ai': {'tipo': tipo, 'ancla': f['segundo'], 'origen': ORIGEN, 'fuente': f['archivo'],
                                                     'por_que': f['por_que']}})
    return eventos


def disenar(ctx, prefs=None):
    """La línea de tiempo de SFX de este GO: (estilo, filas, catálogo, biblioteca)."""
    prefs = prefs if prefs is not None else _prefs()
    lib = biblioteca(prefs)
    cat = catalogo(lib)
    estilo = prefs.get(PREF_ESTILO) or 'auto'
    if estilo not in ESTILO:
        estilo = estilo_de_pack(ctx.get('pack'))
    ev = etiquetas_de_go(ctx)
    primero = min([e['segundo'] for e in ev if e['tipo'] != 'corte' and e['segundo'] < 1.0] or [None], key=lambda x: 9 if x is None else x)
    # el riser termina EN el primer momento (≈0,4 s de subida): si el video arranca con algo antes de 0,45 s no cabe (quedaba una cola de
    # 0,06 s): ese primer golpe ya es el gancho
    if prefs.get(PREF_GANCHO, True) and not intro_con_sonido(ctx) and (primero is None or primero >= GANCHO_MIN):
        ev.append({'segundo': round(primero if primero is not None else 0.5, 3), 'tipo': 'gancho', 'detalle': 'gancho del inicio', 'fuerza': 99})
    filas = asignar(elegir(ev, estilo), cat, lib)
    return estilo, filas, cat, lib


def preparar(ctx, res=None, al_estado=None, prefs=None):
    """En el hilo de GO: diseña y hornea. Nunca lanza (si algo falla, GO sigue con sus sonidos de siempre)."""
    res = {} if res is None else res
    try:
        import director_sonido as D
        import director_sonido_estado as E
        video = ctx.get('video') or ''
        D.guardar_contexto(ctx)
        t0 = time.time()
        estilo, filas, cat, lib = disenar(ctx, prefs)
        con_voz = bool(ctx.get('palabras'))
        eventos = hornear(filas, cat, lib, E.carpeta_de(video) / 'sfx_biblioteca', con_voz)
        res['sfx'] = {'eventos': eventos, 'puestos': [{'tipo': f['tipo'], 'segundo': f['segundo'], 'archivo': f['archivo'],
                                                       'por_que': f['por_que'], 'fuente': 'biblioteca'} for f in filas],
                      'segundos': round(time.time() - t0, 2)}
        import sonido_musica as M                                   # v5.48: la música de 02_MUSICA (3 opciones; la 1.ª elegida)
        musica = M.preparar(ctx, filas, lib, E.carpeta_de(video) / 'musica_biblioteca', prefs)
        plan_musica = M.plan(musica)
        if plan_musica:
            res['capas'] = {'musica': {'plan': plan_musica}}
        estado = E.cargar(video)
        estado['sfx_plan'], estado['sonido_musica'], estado['music_plan'] = eventos, musica, plan_musica
        et = etiquetas_de_go(ctx)
        guia = {'captions': [{'t': e['segundo'], 'texto': e['detalle']} for e in et if e['detalle'].startswith('caption')],
                'cortes': [e['segundo'] for e in et if e['tipo'] == 'corte'],
                'bloques': bloques_captions(ctx),
                'duracion': max([float(p.get('end') or 0) for p in ctx.get('palabras') or []] + [f['segundo'] + 1 for f in filas] + [1.0])}
        estado['sonido_skill'] = {'version': VERSION, 'estilo': estilo, 'biblioteca': str(lib), 'filas': filas, 'con_voz': con_voz,
                                  'guia': guia, 'fecha': time.strftime('%Y-%m-%d %H:%M:%S')}
        E.guardar(video, estado)
        log(f'{len(eventos)} sonidos de la biblioteca · estilo {NOMBRE_ESTILO.get(estilo, estilo)} · '
            + (f"música «{musica['candidatos'][0]['titulo']}»" if plan_musica else 'sin música') + f' · {round(time.time() - t0, 2)} s')
    except Exception:
        try:
            import registro
            registro.excepcion(origen=ORIGEN)
        except Exception:
            pass
        res.pop('sfx', None)
    return res


def rehacer(video, prefs=None):
    """La página: rediseña con la foto de GO guardada. Deja el diseño pendiente de «Aplicar a Resolve». (ok, texto)."""
    import director_sonido as D
    import director_sonido_estado as E
    ctx = D.cargar_contexto(video)
    if not ctx:
        return False, 'Haz GO con este video primero.'
    res = preparar(ctx, {}, prefs=prefs)
    if not res.get('sfx'):
        return False, 'No se pudo diseñar el sonido (detalle en el Registro).'
    estado = E.cargar(video)
    estado['pendiente_resolve'] = True
    E.guardar(video, estado)
    return True, f"{len(res['sfx']['eventos'])} sonidos listos. Pulsa «Aplicar a Resolve»."


def bloques_captions(ctx):
    """Los captions de GO para el carril de la página: [{'ini', 'fin', 'texto', 'clave', 't'}] ('t' = cuando sale la palabra clave)."""
    import director_sonido_eventos as EV
    try:
        caps = EV.captions((ctx or {}).get('bloques') or [], None).get('lista') or []
    except Exception:
        return []
    return [{'ini': round(float(c['ini']), 3), 'fin': round(float(c.get('fin') or c['ini']), 3), 'texto': str(c.get('texto') or '')[:80],
             'clave': str(c.get('clave') or ''), 't': round(float(next((s['t'] for s in c.get('sonidos') or [] if s.get('t') is not None),
                                                                       c['ini'])), 3)} for c in caps]


def resumen(video):
    """Lo que la página muestra: estilo, biblioteca, filas (con su WAV horneado y pista), guía (captions, cortes) y si está pendiente."""
    import director_sonido_estado as E
    estado = E.cargar(video) if video else {}
    s = estado.get('sonido_skill') or {}
    if s and not (s.get('guia') or {}).get('bloques'):           # diseño anterior a los carriles de captions: se leen de la foto de GO
        try:
            import director_sonido as D
            s.setdefault('guia', {})['bloques'] = bloques_captions(D.cargar_contexto(video))
        except Exception:
            pass
    filas = [dict(f) for f in s.get('filas') or []]
    for f, e in zip(filas, estado.get('sfx_plan') or []):
        f.update({'wav': e.get('archivo'), 'pista': e.get('pista'), 'ini': e.get('ini'), 'dur': e.get('dur')})
    return {'video': video, 'estilo': s.get('estilo'), 'biblioteca': s.get('biblioteca') or str(biblioteca()), 'filas': filas,
            'guia': s.get('guia') or {}, 'fecha': s.get('fecha'), 'pendiente': bool(estado.get('pendiente_resolve')),
            'en_resolve': estado.get('en_resolve'), 'con_go': bool((estado.get('ultimo_go') or {}).get('con_director')),
            'musica': estado.get('sonido_musica') or {}}


def _envolvente(x, n):
    """n barras 0–1 (pico por tramo) de una señal (2, m) o (m,)."""
    m = np.abs(x).max(axis=0) if x.ndim > 1 else np.abs(x)
    if not m.size:
        return []
    paso = max(1, m.size // n)
    v = m[:paso * (m.size // paso)].reshape(-1, paso).max(axis=1)[:n]
    tope = float(v.max()) or 1.0
    return [round(float(a) / tope, 3) for a in v]


def visual(video, filas=None, ancho=120):
    """(En un hilo) lo que la página dibuja: {'miniaturas': [ruta por segundo], 'voz': [barras], 'ondas': {wav: [barras]}}.
    Miniaturas y voz quedan en caché en la carpeta del video (miniaturas/ y visual.json); las ondas de los SFX se leen de sus WAV."""
    import archivos_seguros
    import director_sonido_estado as E
    carpeta = E.carpeta_de(video) / 'miniaturas'
    cache = E.carpeta_de(video) / 'visual.json'
    d = archivos_seguros.leer_json(cache, None)
    if not (isinstance(d, dict) and d.get('v') == 1 and (d.get('solo_audio') or d.get('miniaturas'))
            and all(Path(m).is_file() for m in d['miniaturas'][:3])):
        import av
        carpeta.mkdir(parents=True, exist_ok=True)
        tomas = {}
        with av.open(str(video)) as c:
            imagen = bool(c.streams.video)                        # v5.67: un audio suelto (.wav/.mp3) no tiene imágenes (antes rompía la página)
            if imagen:
                c.streams.video[0].codec_context.skip_frame = 'NONKEY'   # solo los fotogramas clave: rápido aun en HEVC 4K
            dur = float(c.duration or 0) / 1e6
            for f in (c.decode(video=0) if imagen else ()):
                if f.time is None:
                    continue
                s = int(round(float(f.time)))
                if s in tomas:
                    continue
                img = f.to_image().convert('RGB')
                try:
                    rot = int(round(float(f.rotation or 0))) % 360
                except Exception:
                    rot = 0
                if rot:
                    img = img.rotate(rot, expand=True)
                img = img.resize((ancho, max(1, round(img.height * ancho / img.width))))
                ruta = carpeta / f's_{s:04d}.jpg'
                img.save(ruta, quality=82)
                tomas[s] = str(ruta)
        n = max(1, int(math.ceil(dur or max(tomas or [1]))))
        claves = sorted(tomas)
        mini = [tomas[min(claves, key=lambda k: abs(k - s))] for s in range(n)] if claves else []
        try:
            voz = _envolvente(leer_audio(video, 8000), 1200)
        except Exception:
            voz = []
        d = {'v': 1, 'miniaturas': mini, 'voz': voz, 'duracion': dur, 'solo_audio': not imagen}
        archivos_seguros.escribir_json(cache, d)
    ondas = {}
    for f in filas or []:
        w = f.get('wav')
        if w and w not in ondas and Path(w).is_file():
            try:
                ondas[w] = _envolvente(leer_audio(w, 8000), 48)
            except Exception:
                ondas[w] = []
    return dict(d, ondas=ondas)


def editar(video, i, accion, valor=None):
    """Un cambio a mano desde la línea de tiempo: 'quitar', 'variante' (el siguiente archivo de su familia) o 'mover' (valor en segundos).
    Rehornea (es rápido), deja el diseño pendiente de «Aplicar a Resolve». (ok, texto)."""
    import director_sonido_estado as E
    estado = E.cargar(video)
    s = estado.get('sonido_skill') or {}
    filas = list(s.get('filas') or [])
    if not 0 <= i < len(filas):
        return False, 'Ese sonido ya no está.'
    lib = Path(s.get('biblioteca') or biblioteca())
    cat = catalogo(lib)
    f = dict(filas[i])
    if accion == 'quitar':
        filas.pop(i)
        texto = f"Quitado: {Path(f['archivo']).stem}"
    elif accion == 'variante':
        lista = pools_de(cat, lib).get(f['pool']) or [f['archivo']]
        f['archivo'] = lista[(lista.index(f['archivo']) + 1) % len(lista)] if f['archivo'] in lista else lista[0]
        filas[i] = f
        texto = f"Ahora suena: {Path(f['archivo']).stem}"
    elif accion == 'mover':
        f['segundo'] = round(max(0.0, f['segundo'] + float(valor or 0)), 3)
        filas[i] = f
        filas.sort(key=lambda x: x['segundo'])
        texto = f"Movido a {f['segundo']:.2f} s"
    else:
        return False, 'Acción desconocida.'
    eventos = hornear(filas, cat, lib, E.carpeta_de(video) / 'sfx_biblioteca', s.get('con_voz', True))
    s['filas'], s['fecha'] = filas, time.strftime('%Y-%m-%d %H:%M:%S')
    estado['sonido_skill'], estado['sfx_plan'], estado['pendiente_resolve'] = s, eventos, True
    E.guardar(video, estado)
    return True, texto + ' · pendiente de «Aplicar a Resolve».'


def revisar(filas, cat=None):
    """Revisión crítica (como verificar.py de la skill): avisos cortos para la página. Una familia con UNA sola variante no es un error de
    diseño (se horneó con microvariación) sino material que falta: se avisa una vez como «faltan variantes»."""
    try:
        cat = cat if cat is not None else catalogo()
    except Exception:
        cat = {}
    variantes = {k: sum(1 for r in cat if re.search(rx, r) and curado(r, cat[r])) for k, rx in POOLS.items()}
    avisos, faltan = [], set()
    for a, b in zip(filas, filas[1:]):
        if a['archivo'] == b['archivo']:
            if variantes.get(b.get('pool'), 2) <= 1:
                faltan.add(b.get('pool'))
            else:
                avisos.append(f"{b['segundo']:.2f} s repite el mismo sonido seguido")
        if b['segundo'] - a['segundo'] < 0.25:
            avisos.append(f"{a['segundo']:.2f} s y {b['segundo']:.2f} s se amontonan")
    if sum(1 for f in filas if f['pool'] == 'impacto') > 2:
        avisos.append('más de 2 impactos')
    for p in sorted(x for x in faltan if x):
        avisos.append(f'faltan variantes de «{p}» en la biblioteca (suena el mismo con microvariación)')
    return avisos


def a_json(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1)
