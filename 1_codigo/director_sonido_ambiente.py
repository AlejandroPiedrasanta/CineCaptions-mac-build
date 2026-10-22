# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_ambiente.py — «AI Sound Director» · AI AMBIENCE: el entorno de cada escena y qué hacer con su ambiente.
"""
Nunca ambientes porque sí: alguien explicando en una habitación NO lleva pájaros; puede bastar voz limpia + música + motions, o un room tone muy sutil.

Escenas = los cortes que GO ya encontró (nunca se vuelve a mirar el video para esto). Contexto de cada escena por PRIORIDAD:
    1. metadata del proyecto/escena      (género y perfil de la Edición PRO si ya los calculó)
    2. lo que ya sabe el editor          (las palabras: «calle», «parque», «oficina», «boda»…)
    3. etiquetas de otras partes         (el detector de género de la PRO sobre lo que se dice)
    4. el audio del fondo                (nivel, graves, planitud, picos tonales agudos, cuánto varía)
    5. píxeles                           solo si hiciera falta para AÑADIR algo y hubiera infraestructura (en la fase 1 no hace falta: no se añade nada)
Contextos: INTERIOR, QUIET_INTERIOR, ROOM, OFFICE, STUDIO, STREET, CITY, OUTDOOR, NATURE, FOREST, PARK, CROWD, CAFE, EVENT, WIND, WATER, TRAFFIC
(+ MUSIC_BED cuando el fondo es la música ya mezclada). Decisiones: KEEP_ORIGINAL_AMBIENCE · CLEAN_ORIGINAL_AMBIENCE · ADD_SUBTLE_AMBIENCE ·
REPLACE_AMBIENCE · REDUCE_AMBIENCE · LEAVE_SILENT. La voz siempre gana: un ambiente que compite se reduce, filtra o quita. (Fase 1: decidir y
anotar; diseñar, fundir entre escenas e igualar niveles y espectro es de la fase 4.)
"""
import re
import unicodedata

import numpy as np

import director_sonido_medir as M

DECISIONES = ('KEEP_ORIGINAL_AMBIENCE', 'CLEAN_ORIGINAL_AMBIENCE', 'ADD_SUBTLE_AMBIENCE', 'REPLACE_AMBIENCE', 'REDUCE_AMBIENCE', 'LEAVE_SILENT')
ESCENA_MIN_S = 2.0

# palabras que delatan el entorno (es / en / pt), sin tildes
PALABRAS = {
    'STREET': 'calle calles avenida esquina banqueta acera street streets avenue sidewalk rua avenida',
    'CITY': 'ciudad centro urbano downtown city urban cidade',
    'TRAFFIC': 'trafico carro carros coche coches bus camion moto traffic car cars truck carro onibus',
    'NATURE': 'naturaleza campo montana montanas volcan nature mountain mountains countryside natureza montanha',
    'FOREST': 'bosque selva arboles forest jungle trees floresta mata',
    'PARK': 'parque jardin park garden jardim',
    'WATER': 'mar playa rio lago olas cascada agua beach sea river lake waves waterfall water praia lagoa',
    'CAFE': 'cafe cafeteria restaurante bar comida mesero coffee restaurant cafeteria',
    'EVENT': 'boda fiesta evento concierto quinceanera xv ceremonia recepcion wedding party event concert festa casamento',
    'CROWD': 'gente multitud publico estadio mercado crowd people audience stadium market multidao',
    'OFFICE': 'oficina escritorio empresa reunion office desk meeting escritorio',
    'STUDIO': 'estudio podcast microfono camara grabando studio microphone recording estudio',
    'ROOM': 'casa cuarto habitacion sala cocina recamara dormitorio home room bedroom kitchen living quarto',
}
_PAL = {k: set(v.split()) for k, v in PALABRAS.items()}
GENERO_A_CONTEXTO = {'boda': 'EVENT', 'xv': 'EVENT', 'restaurante': 'CAFE', 'inmobiliaria': 'ROOM', 'bts': 'STUDIO'}      # edicion_pro_planificador.PALABRAS_GENERO
CATEGORIA_A_CONTEXTO = {'boda': 'EVENT', 'xv': 'EVENT', 'restaurante': 'CAFE', 'cocina': 'ROOM', 'inmobiliaria': 'ROOM', 'fotografia': 'STUDIO',
                        'viajes': 'OUTDOOR', 'tecnologia': 'OFFICE', 'negocios': 'OFFICE', 'finanzas': 'OFFICE'}          # ia_texto.CATEGORIAS


def _plegar(t):
    t = unicodedata.normalize('NFD', str(t).lower())
    return re.sub(r'[^a-z0-9ñ ]+', ' ', ''.join(c for c in t if unicodedata.category(c) != 'Mn'))


def escenas(cortes, duracion):
    """[(ini, fin)] entre los cortes (los muy cortos se unen a la anterior)."""
    puntos = [0.0] + sorted(float(t) for t in (cortes or []) if 0.0 < float(t) < duracion) + [float(duracion)]
    salida = []
    for a, b in zip(puntos, puntos[1:]):
        if salida and (b - a < ESCENA_MIN_S or salida[-1][1] - salida[-1][0] < ESCENA_MIN_S):
            salida[-1] = (salida[-1][0], b)
        else:
            salida.append((a, b))
    return salida or [(0.0, float(duracion))]


def _pistas_texto(palabras, a, b):
    """Qué contextos nombra lo que se dice en [a, b] (con 3 s de margen)."""
    cuenta = {}
    for p in palabras or []:
        t = float(p.get('start', 0.0))
        if a - 3.0 <= t <= b + 3.0:
            w = _plegar(p.get('word') or p.get('text') or '').strip()
            for ctx, voc in _PAL.items():
                if w in voc:
                    cuenta[ctx] = cuenta.get(ctx, 0) + 1
    return cuenta


def _audio_de_escena(m, diag, a, b):
    """El fondo de la escena: nivel, nivel respecto a la voz, graves, agudos, planitud, picos tonales agudos y cuánto varía."""
    rms, cl, B = m['rms_db'], m['clase20'], m['bandas_db']
    t = (np.arange(rms.size) * M.MARCO + M.MARCO / 2) / M.SR
    dentro = (t >= a) & (t < b)
    import director_sonido_voz as V
    huecos = V._huecos(m) if m.get('palabras') else np.zeros(rms.size, bool)
    fondo = dentro & (rms > -110) & ((cl == 0) | huecos)
    if fondo.sum() < 5:
        fondo = dentro & (rms > -110) & (rms <= np.percentile(rms[dentro], 10) if dentro.any() else False)
    if not fondo.any():
        return None
    idx = {n: i for i, n in enumerate(M.NOMBRES_BANDAS)}
    bm = {n: V._potencia_media_db(B[fondo, i]) for n, i in idx.items()}
    graves = bm['sub'] - bm['medio']
    gf, mf = m.get('graves_fino'), m.get('medio_fino')
    voz = dentro & (cl == 2)
    nivel_voz = V._potencia_media_db(rms[voz]) if voz.sum() >= 10 else diag.get('nivel_voz_db', -30.0)
    paso = M.FINO // 2
    tf = (np.arange(m['tonal'].size) * paso + M.FINO / 2) / M.SR
    clf = m['clase_fina'][:m['tonal'].size]
    sel_f = (tf >= a) & (tf < b) & (clf == 0) if clf.size == m['tonal'].size else (tf >= a) & (tf < b)
    tonal = float(np.median(m['tonal'][sel_f])) if sel_f.sum() >= 3 else None
    if gf is not None and gf.size == m['tonal'].size and sel_f.sum() >= 3:   # los graves con marcos finos (en 20 ms se cuelan de la ventana)
        graves = V._potencia_media_db(gf[sel_f]) - V._potencia_media_db(mf[sel_f])
    return {'nivel_db': round(float(np.median(rms[fondo])), 1), 'rel_voz_db': round(float(np.median(rms[fondo])) - nivel_voz, 1),
            'graves_db': round(graves, 1), 'agudos_db': round(bm['aire'] - bm['medio'], 1),
            'planitud': round(float(np.median(m['planitud20'][fondo])), 3) if m['planitud20'].size == rms.size else None,
            'variacion_db': round(float(np.std(rms[fondo])), 1), 'tonal_agudo_db': round(tonal, 1) if tonal is not None else None, 'marcos': int(fondo.sum())}


def _por_audio(au, viento, musica):
    """Puntos por contexto según el fondo (con su lectura)."""
    p, lectura = {}, []
    if au is None:
        return p, ['sin fondo medible']
    if musica:
        p['MUSIC_BED'] = 1.0
        lectura.append('el fondo es la música ya mezclada')
        return p, lectura
    niv, var, plan, grav = au['nivel_db'], au['variacion_db'], au.get('planitud') or 0.5, au['graves_db']
    if viento:
        p['WIND'] = p.get('WIND', 0) + 0.8
        lectura.append('golpes de graves (viento)')
    agudos = au['agudos_db']
    if niv < -62:
        p['QUIET_INTERIOR'] = 0.8
        lectura.append(f'fondo muy bajo ({niv:.0f} dBFS): interior silencioso')
        return p, lectura
    if niv < -40 and var < 3.5 and (au.get('tonal_agudo_db') or 0) < 22 and agudos > -18:
        p['INTERIOR'] = 0.55
        p['ROOM'] = 0.45
        lectura.append(f'fondo constante ({niv:.0f} dBFS, ±{var:.1f} dB): interior con aire acondicionado / ventilador o sala')
    if niv > -50 and agudos < -18 and var < 4 and grav > -6:
        p['CITY'] = p.get('CITY', 0) + 0.45
        p['STREET'] = p.get('STREET', 0) + 0.3
        lectura.append(f'fondo oscuro y lejano pero con cuerpo ({agudos:.0f} dB de agudos): ciudad de fondo')
    if grav > 3 and var >= 3.5:
        p['TRAFFIC'] = p.get('TRAFFIC', 0) + 0.5
        p['STREET'] = p.get('STREET', 0) + 0.45
        lectura.append(f'graves que van y vienen ({grav:+.0f} dB): tráfico / calle')
    if au.get('tonal_agudo_db') is not None and au['tonal_agudo_db'] > 22 and niv > -70 and agudos > -18:
        p['NATURE'] = p.get('NATURE', 0) + 0.5
        lectura.append(f"picos tonales agudos en el fondo (+{au['tonal_agudo_db']:.0f} dB): pájaros o pitidos")
    if niv > -50 and var >= 3.0 and plan < 0.45 and grav <= 3 and agudos > -18:
        p['CROWD'] = p.get('CROWD', 0) + 0.45
        lectura.append('fondo de voces que varía: gente / lugar con público')
    if au['agudos_db'] > 0 and plan > 0.5 and var < 4 and niv > -60:
        p['WATER'] = p.get('WATER', 0) + 0.3
        lectura.append('fondo liso y brillante: agua o hiss')
    return p, lectura


def analizar(medidas, diag, palabras, cortes=None, genero=None, perfil=None, musica=None):
    """Contexto y decisión de ambiente por escena (y el resumen). Nunca propone AÑADIR sin coherencia de texto Y de imagen (la imagen, en la fase 4)."""
    dur = float(medidas.get('duracion') or diag.get('duracion') or 0.0)
    musica_en_fuente = bool((musica or {}).get('presente'))
    viento = bool(diag.get('viento'))
    ctx_proyecto = {}
    if genero and genero in GENERO_A_CONTEXTO:
        ctx_proyecto[GENERO_A_CONTEXTO[genero]] = 0.35
    cat = (perfil or {}).get('categoria')
    if cat in CATEGORIA_A_CONTEXTO:
        ctx_proyecto[CATEGORIA_A_CONTEXTO[cat]] = ctx_proyecto.get(CATEGORIA_A_CONTEXTO[cat], 0) + 0.35
    salida = []
    for k, (a, b) in enumerate(escenas(cortes, dur)):
        au = _audio_de_escena(medidas, diag, a, b)
        p_audio, lectura = _por_audio(au, viento, musica_en_fuente)
        texto = _pistas_texto(palabras, a, b)
        puntos = dict(p_audio)
        fuentes = []
        if ctx_proyecto:
            fuentes.append('metadata del proyecto: ' + ', '.join(ctx_proyecto))
        for c, v in ctx_proyecto.items():
            puntos[c] = puntos.get(c, 0) + v
        for c, n in texto.items():
            puntos[c] = puntos.get(c, 0) + min(0.6, 0.3 * n)
        if texto:
            fuentes.append('lo que se dice: ' + ', '.join(f'{c} ×{n}' for c, n in texto.items()))
        if lectura:
            fuentes.append('audio del fondo: ' + '; '.join(lectura))
        if not puntos:
            contexto, conf = 'INTERIOR', 0.2
        else:
            contexto = max(puntos, key=puntos.get)
            conf = float(min(1.0, puntos[contexto]))
        dec, por_que = decidir(contexto, conf, au, texto)
        salida.append({'escena': k + 1, 'ini': round(a, 2), 'fin': round(b, 2), 'contexto': contexto, 'confianza': round(conf, 2), 'fuentes': fuentes,
                       'audio': au, 'decision': dec, 'por_que': por_que, 'visual': 'sin analizar (no hace falta: no se añade nada sin coherencia visual)'})
    resumen = _resumen(salida)
    return {'escenas': salida, 'resumen': resumen, 'escenas_n': len(salida)}


def decidir(contexto, conf, au, texto):
    """KEEP / CLEAN / ADD_SUBTLE / REPLACE / REDUCE / LEAVE_SILENT para una escena (la voz siempre gana)."""
    rel = (au or {}).get('rel_voz_db', -100.0)
    niv = (au or {}).get('nivel_db', -100.0)
    if contexto == 'MUSIC_BED':
        return 'KEEP_ORIGINAL_AMBIENCE', 'el fondo es la música ya mezclada con la voz: no se separa, se conserva'
    if rel > -15 and contexto not in ('QUIET_INTERIOR',):
        return 'REDUCE_AMBIENCE', f'el ambiente compite con la voz ({rel:.0f} dB de ella): bajarlo / filtrarlo'
    if contexto == 'WIND':
        return 'CLEAN_ORIGINAL_AMBIENCE', 'viento en el micrófono: se limpia (paso alto y reducción), no es un ambiente que aporte'
    if contexto in ('INTERIOR', 'ROOM', 'OFFICE', 'STUDIO') and niv > -52:
        return 'CLEAN_ORIGINAL_AMBIENCE', f'fondo constante de interior ({niv:.0f} dBFS): se limpia con la voz, sin añadir nada'
    if contexto in ('QUIET_INTERIOR', 'INTERIOR', 'ROOM', 'OFFICE', 'STUDIO'):
        if niv < -80:
            return 'ADD_SUBTLE_AMBIENCE', 'silencio digital entre frases: un room tone extremadamente sutil evita los huecos muertos (fase 4)'
        return 'KEEP_ORIGINAL_AMBIENCE', 'interior tranquilo: el fondo natural se queda (nada de pájaros inventados)'
    if contexto in ('STREET', 'CITY', 'TRAFFIC', 'CROWD', 'CAFE', 'EVENT', 'NATURE', 'FOREST', 'PARK', 'WATER', 'OUTDOOR'):
        if (au or {}).get('nivel_db', -100) < -70 and texto.get(contexto):
            return 'LEAVE_SILENT', f'se nombra {contexto.lower()} pero el audio está limpio: añadirlo pide coherencia visual (fase 4); por ahora, nada'
        return 'KEEP_ORIGINAL_AMBIENCE', f'ambiente real de {contexto.lower()}: se conserva, muy por debajo de la voz'
    return 'LEAVE_SILENT', 'sin contexto claro: no se añade nada'


def _resumen(escenas_):
    if not escenas_:
        return 'sin escenas'
    cuenta = {}
    for e in escenas_:
        clave = f"{e['contexto'].lower()} / {e['decision'].split('_')[0].lower()}"
        cuenta[clave] = cuenta.get(clave, 0) + 1
    return ', '.join(f'{k}' + (f' ×{n}' if n > 1 else '') for k, n in cuenta.items())
