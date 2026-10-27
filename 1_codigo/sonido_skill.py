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
Biblioteca: preferencia 'sonido_biblioteca' (por defecto Desktop\\SFX del autor si existe; si no, «Mis sonidos» del director). Si la carpeta trae
catalogo_sfx.json (lo escribe la skill) se usa; si no, se mide aquí con PyAV y se guarda en caché.
"""
import json
import math
import re
import time
import wave
from pathlib import Path

import numpy as np

PREF_ON, PREF_LIB, PREF_ESTILO, PREF_GANCHO, PREF_FIESTA = 'sonido_skill', 'sonido_biblioteca', 'sonido_estilo', 'sonido_gancho', 'sonido_fiesta'
ORIGEN = 'Sonido (biblioteca)'
SR = 48000
LIB_AUTOR = Path.home() / 'Desktop' / 'SFX'
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
DINERO_RX = r'(\$|€|₹|dinero|precio|gratis|gratuit|money|dollar|price|free|cost|pesos|quetzal|millon)'
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
    if p and Path(p).is_dir():
        return Path(p)
    if LIB_AUTOR.is_dir():
        return LIB_AUTOR
    import director_sonido_estado as E
    return E.CARPETA / 'biblioteca'


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


def etiquetas_de_go(ctx):
    """Los eventos que GO ya conoce, con su tipo de MAPA_SFX.md: [{'segundo', 'tipo', 'detalle', 'fuerza'}]."""
    import director_sonido_eventos as EV
    dur = None
    ev = []
    caps = EV.captions(ctx.get('bloques') or [], dur).get('lista') or []
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
    mot = EV.motions(ctx.get('plan_efectos'), ctx.get('plan_pro'), dur).get('lista') or []
    fx = {'corte': 'corte', 'icono': 'icono', 'numero': 'grafica', 'pegatina': 'icono', 'enfasis': 'acento', 'broll': 'corte'}
    for m in mot:
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
    for t in ctx.get('cortes') or []:
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
def curado(rel, info=None):
    """¿Sirve para un video nuevo? Nunca los extraídos de los videos de creadores ni los crudos de ejercicio."""
    return '17_EXTRAIDOS_REFERENCIAS' not in rel and '_DE_REFERENCIAS' not in rel and not (info or {}).get('solo_ejercicio')


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
    """Tope de SFX por ventana de 10 s: la densidad de los creadores en ese estilo (elegante ~3, dinámico ~7, cinética ~15)."""
    d = densidad_creadores().get(estilo) or DENSIDAD_ESTILO.get(estilo)
    return max(1, int(round(d * 10))) if d else ESTILO[estilo]['max10']


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
    return {k: sorted((r for r in cat if re.search(rx, r) and curado(r, cat[r])), key=lambda r: (-usos.get(r, 0), r)) for k, rx in POOLS.items()}


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
    textos = [e for e in ev if e['tipo'] == 'texto_grande']
    ult = -10
    for w in range(0, int(max([e['segundo'] for e in ev] or [0])) + 4, 4):
        grupo = [e for e in textos if w <= e['segundo'] < w + 4]
        if grupo and w - ult >= 8:
            max(grupo, key=lambda e: e['fuerza'])['tipo'] = 'acento'
            ult = w
    out = []
    for e in sorted(ev, key=lambda x: x['segundo']):
        e['pool'], e['prioridad'] = REGLAS.get(e['tipo'], ('pop', 2))
        if out:
            p = out[-1]
            gap = cfg['gap_pop'] if e['pool'] in ('pop', 'acento') and p['pool'] in ('pop', 'acento') else 0.25
            if e['segundo'] - p['segundo'] < gap:
                if e['prioridad'] > p['prioridad']:
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
                out.remove(min(ventana, key=lambda x: (x['prioridad'], x['fuerza'])))
                cambio = True
                break
    return out


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


def hornear(filas, cat, lib, carpeta, con_voz=True):
    """Cada SFX recortado, con fundido y su nivel dentro del archivo (Resolve ignora el volumen de clip por script)."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    eventos, previo, repeticion = [], None, 0
    for i, f in enumerate(filas):
        info = cat[f['archivo']]
        dur = recorte(info, f.get('duracion'))
        x = leer_audio(Path(lib) / f['archivo'])[:, :int(dur * SR)]
        if not x.shape[1]:
            x = np.zeros((2, int(0.05 * SR)), np.float32)       # nunca saltar: sfx_plan[i] va con filas[i]
        variacion_db = 0.0
        repeticion = repeticion + 1 if f['archivo'] == previo else 0
        previo = f['archivo']
        if repeticion:                                          # el mismo archivo seguido: microvariación (tono ±3 %, ±0,7 dB) para que no suene clonado
            factor = 1.0 + 0.03 * (1 if repeticion % 2 else -1)
            n = int(x.shape[1] / factor)
            pos = np.linspace(0, x.shape[1] - 1, n)
            x = np.stack([np.interp(pos, np.arange(x.shape[1]), c) for c in x]).astype(np.float32)
            variacion_db = 0.7 if repeticion % 2 else -0.7
        fade = min(int(0.2 * SR), x.shape[1])
        x[:, -fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
        g = (info['nivel_db'] - info['max_db'] + (OFFSET_VOZ if con_voz else 0.0) + float(f.get('ganancia_db') or 0.0) + variacion_db)
        x *= 10 ** (g / 20)
        pk = float(np.abs(x).max() or 1)
        if pk > 0.89:
            x *= 0.89 / pk
        destino = carpeta / f"sfx_{i:03d}_{f['pool']}.wav"
        _escribir_wav(destino, x)
        tipo = POOL_A_TIPO.get(f['pool'], 'pop')
        eventos.append({'tipo': 'sonido', 'pista': PISTA.get(tipo, 'AI SFX UI'), 'ini': round(max(0.0, f['segundo'] - info['pico']), 3),
                        'dur': round(x.shape[1] / SR, 3), 'archivo': str(destino), 'asset': f"{f['tipo']} · {Path(f['archivo']).stem}"[:80],
                        'pico': info['pico'], 'ai': {'tipo': tipo, 'ancla': f['segundo'], 'origen': ORIGEN, 'fuente': f['archivo'],
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
    if prefs.get(PREF_GANCHO, True) and not intro_con_sonido(ctx):
        ev.append({'segundo': round(min([e['segundo'] for e in ev if e['segundo'] < 1.0] or [0.3]), 3), 'tipo': 'gancho',
                   'detalle': 'gancho del inicio', 'fuerza': 99})
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


def resumen(video):
    """Lo que la página muestra: estilo, biblioteca, filas (con su WAV horneado y pista), guía (captions, cortes) y si está pendiente."""
    import director_sonido_estado as E
    estado = E.cargar(video) if video else {}
    s = estado.get('sonido_skill') or {}
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
    if not (isinstance(d, dict) and d.get('v') == 1 and d.get('miniaturas') and all(Path(m).is_file() for m in d['miniaturas'][:3])):
        import av
        carpeta.mkdir(parents=True, exist_ok=True)
        tomas = {}
        with av.open(str(video)) as c:
            vs = c.streams.video[0]
            vs.codec_context.skip_frame = 'NONKEY'                # solo los fotogramas clave: rápido aun en HEVC 4K
            dur = float(c.duration or 0) / 1e6
            for f in c.decode(video=0):
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
        d = {'v': 1, 'miniaturas': mini, 'voz': voz, 'duracion': dur}
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
