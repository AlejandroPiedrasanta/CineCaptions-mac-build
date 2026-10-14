# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_tema5.py — Tema 5 («Edición total»): la edición completa con el sistema de la skill «Edit VIRAL Reels with AI».
"""
La referencia es `skill videos/` (el video crudo, el MISMO video editado por un editor, el tablero de inspiración y la guía de sonido). Su sistema:

  * captions de DOS letras: sans pequeña blanca (Inter) para lo que se dice + la FRASE CLAVE en serif cursiva grande (DM Serif Text) en UNA tinta
    de acento que va con el video (azul en planos fríos, ámbar en cálidos, lima en verdes…), palabra a palabra con un desenfoque suave, a la
    altura del pecho; nada de emojis, brillos ni rebotes.
  * elementos en pantalla cuando el discurso los pide, sobre cristal oscuro y con el video oscurecido detrás: el indicador de pasos (en el gancho
    «tres errores…» en rojo; luego «número uno/dos/tres» marca el paso) y el deslizador «de principiante a profesional».
  * escenas de papel claro con cuadrícula: a pantalla completa (la frase en tinta oscura) o en la mitad de arriba con la persona bajada a la de
    abajo (pantalla dividida): un icono 3D en su tarjeta o una cifra en serif.
  * de vez en cuando, la frase clave enorme DETRÁS de la persona (Magic Mask).

GO pone igual unos captions Text+ (diseño del Tema 4) de RESPALDO; la Edición PRO —con el Tema 5 va siempre— los sustituye por los de aquí (Remotion)
y quita sus piezas de otros estilos (órbita 3D, plantillas doradas…), que no son de este sistema. Si Remotion no sale, quedan los Text+.

    activo(nombre_pack) -> bool
    bloques()          -> los bloques del .guion.json que GO acaba de escribir: [{'ini', 'fin', 'palabras': [{'texto', 't' (relativo), 'rol'}]}]
    acento_de_video(video) -> '#rrggbb'
    planificar(plan, vertical, densidad, video, det_de) -> (piezas, divididas)
    coordinar(piezas)  -> tras la regla de la cara, el indicador / deslizador debajo de los captions
"""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

PACK = 'Tema5'
MANIFIESTO = Path.home() / 'DaVinciSubtitles' / 'subtitles_manifest.json'
Y_NORMAL = {True: 56.0, False: 78.0}          # centro de los captions sobre el video (% del alto): a la altura del pecho
Y_DIVIDIDA, Y_PAPEL, Y_PAPEL_TEXTO = 8.0, 13.0, 46.0
Y_ELEMENTO = 65.0                              # el indicador de pasos / el deslizador, debajo de los captions
CADA = {'sobria': 9.0, 'media': 6.5, 'espectaculo': 4.5}     # segundos entre escenas
CADA_DETRAS = 14.0
ACENTOS = {'azul': '#4C7DFF', 'ambar': '#F5A524', 'lima': '#B9E25B', 'lila': '#A98BFF', 'coral': '#FF7A59'}
PIEZAS_QUE_QUEDAN = ('ubicacion',)            # de la PRO general, con el Tema 5 solo queda el mapa con bandera (y el B-roll y el gris, que van aparte)

CONECTORAS = set('''a al o u e y the and or of in on at to is it its as be by if so we my me i you your our de del la las el los lo un una unos unas en
con por para que se su sus es son era fue muy mas más pero ya le les nos te tu tus mi mis esto este esta eso ese esa this that these those there here
what how just more less do does did not no si sí an um uma uns umas os as do da dos das em no na nos nas com pra é ao à from about into than
desde hasta sobre entre for with without all any can get got has have had was were will would should could them they their there then than when where while who whom which because about after before over under very also into onto upon out up down off again once only own same some such too each both few most other nor yet ever every many much one ones per via vs para por sin sobre entre tras desde hasta cuando donde porque como mientras pero aunque todo toda todos todas cada otro otra otros otras mismo misma mucho mucha muchos muchas poco poca algo nada quien cual cuales este estos estas ese esos esas aquel tambien solo hay ser estar tener hacer puede pueden para pra pelo pela pelos pelas sem sobre entre ate quando onde porque como mas tudo cada outro outra'''.split())
NUMEROS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
           'uno': 1, 'una': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10,
           'um': 1, 'dois': 2, 'duas': 2, 'quatro': 4, 'sete': 7, 'oito': 8, 'nove': 9, 'dez': 10}
ORDINALES = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'primero': 1, 'primera': 1, 'segundo': 2, 'segunda': 2, 'tercero': 3,
             'tercera': 3, 'cuarto': 4, 'cuarta': 4, 'quinto': 5, 'quinta': 5, 'primeiro': 1, 'terceiro': 3}
DEBILES = set('''is are was were be been being have has had make makes made take takes took get gets got go goes went look looks looked use uses
used want need know think see say said tell come give put let keep watch change really just every also only even still thing things way ways lot
something someone then when where which who here's heres there's whats what's okay ok so now yeah well like going gonna want wanna you're youre
ser estar esta están hay tener tengo tiene hacer hace hago ir va voy ver mira decir dice saber creo pienso cosa cosas forma algo alguien cuando donde
entonces tambien también solo sólo aqui aquí alli allí ahi ahí como cómo cada todo todos toda todas usar usa uso puedes puede poder quiero quieres
necesitas vamos bueno pues okey number numero número paso should could would can will very much many some any each other same own create
creating making doing using having being getting always never siempre nunca jamas jamás debes deberías puedo podemos muy mucho muchos algunas algunos'''.split())
ENFASIS = set('''best worst mejor peor secret secreto secretos free gratis huge enorme important importante mistake mistakes
error errores money dinero viral special especial better professional profesional beginner principiante amateur nobody nadie everything everyone
million millones thousand mil dollars dolares dólares percent porciento increible incredible amazing brutal perfect perfecto perfecta attention atención atencion results resultados success éxito exito love amor'''.split())
PREFIJO_NUMERO = {'number', 'numero', 'paso', 'step', 'tip', 'punto', 'regla', 'rule', 'error', 'mistake'}
DESDE = {'from', 'de', 'desde', 'do', 'da'}
HASTA = {'to', 'a', 'hasta', 'al', 'para', 'ao', 'pro'}


def activo(nombre_pack) -> bool:
    return str(nombre_pack or '') in (PACK, 'Tema6')                  # el Tema 6 («Editorial») usa este motor con su estilo (edicion_pro_tema6)


def _plegar(t):
    t = unicodedata.normalize('NFD', str(t).lower())
    return re.sub(r'[^a-z0-9%$]', '', ''.join(c for c in t if unicodedata.category(c) != 'Mn'))


def _prioridad_es(fam):
    try:
        import edicion_pro_escenas as ES
        return float(ES.PRIORIDAD.get(fam, 1.0))
    except Exception:
        return 1.0


def _nadie(det_de, t):
    """¿Seguro que no hay nadie en cuadro en t? (sin detección, o si falla, se da por que sí hay alguien)"""
    try:
        d = det_de(t)
    except Exception:
        return False
    return isinstance(d, dict) and not d.get('personas')


def _numero(t):
    p = _plegar(t)
    if p in NUMEROS:
        return NUMEROS[p]
    return int(p) if p.isdigit() and 0 < int(p) <= 10 else None


def bloques():
    """Los bloques de captions del idioma base que GO acaba de poner (pista «guion» del manifiesto), cada palabra con su momento RELATIVO al bloque."""
    try:
        m = json.loads(MANIFIESTO.read_text(encoding='utf-8'))
        pista = next(t for t in m.get('tracks') or [] if t.get('style') == 'guion' and t.get('data_path'))
        cues = json.loads(Path(pista['data_path']).read_text(encoding='utf-8')).get('cues') or []
    except (OSError, ValueError, StopIteration):
        return []
    out = []
    for c in cues:
        try:
            ini, fin = float(c['start']), float(c['end'])
        except (KeyError, TypeError, ValueError):
            continue
        runs = sorted([r for r in c.get('runs') or [] if isinstance(r, dict) and str(r.get('texto') or '').strip()], key=lambda r: float(r.get('t') or ini))
        palabras = []
        for r in runs:
            t = max(0.0, float(r.get('t') or ini) - ini)
            for k, w in enumerate(str(r['texto']).split()):           # un run de varias palabras (otros estilos): una tras otra
                palabras.append({'texto': w, 't': round(t + 0.08 * k, 3), 'rol': r.get('rol') or 'complement'})
        if palabras and fin - ini >= 0.25:
            out.append({'ini': ini, 'fin': fin, 'palabras': palabras})
    propios = {w['texto'] for b in out for w in b['palabras'][1:] if w['texto'][:1].isupper()}       # con mayúscula a mitad de bloque: nombre propio
    for n, b in enumerate(out):                                          # el planificador pone mayúscula a cada bloque; a mitad de frase, no
        w = b['palabras'][0]
        sigue = n > 0 and b['ini'] - out[n - 1]['fin'] < 0.35
        if sigue and w['texto'] not in propios and not w['texto'].isupper() and w['texto'] not in ("I'm", "I've", "I'll", "I'd"):
            w['texto'] = w['texto'][:1].lower() + w['texto'][1:]
    return out


def acento_de_video(video):
    """La tinta de acento que va con el video: el tono de los BORDES del cuadro (el fondo, no la piel de la persona del centro)."""
    try:
        import colorsys

        import av
        import numpy as np
        muestras = []
        with av.open(str(video)) as c:
            s = c.streams.video[0]
            dur = float(c.duration or 0) / 1e6
            for f in (0.12, 0.35, 0.6, 0.85):
                c.seek(int(dur * f * 1e6))
                fr = next(c.decode(s)).to_ndarray(format='rgb24')[::6, ::6] / 255.0
                h, w = fr.shape[:2]
                muestras += [fr[:, : w // 5].reshape(-1, 3), fr[:, -w // 5:].reshape(-1, 3), fr[: h // 7].reshape(-1, 3)]
        px = np.concatenate(muestras)
        mx, mn = px.max(1), px.min(1)
        sel = px[((mx - mn) / (mx + 1e-6) > 0.2) & (mx > 0.12)]
        if len(sel) < 0.04 * len(px):
            return ACENTOS['azul']                                     # fondo neutro: el azul de la referencia
        hue = colorsys.rgb_to_hsv(*sel.mean(0))[0] * 360
    except Exception:
        return ACENTOS['azul']
    if 170 <= hue < 265:
        return ACENTOS['azul']
    if hue < 65 or hue >= 340:
        return ACENTOS['ambar']
    if 65 <= hue < 170:
        return ACENTOS['lima']
    return ACENTOS['lila']


def claro(video) -> bool:
    """¿El video es claro a la altura de los captions (franja del 45 al 70 % del alto)? Entonces llevan un velo oscuro suave detrás."""
    try:
        import av
        import numpy as np
        lum = []
        with av.open(str(video)) as c:
            s = c.streams.video[0]
            dur = float(c.duration or 0) / 1e6
            for f in (0.2, 0.5, 0.8):
                c.seek(int(dur * f * 1e6))
                fr = next(c.decode(s)).to_ndarray(format='rgb24')[::6, ::6] / 255.0
                h = fr.shape[0]
                L = fr[int(h * 0.45):int(h * 0.7)] @ np.array([0.2126, 0.7152, 0.0722])
                lum.append((float(L.mean()), float((L > 0.62).mean())))
        return sum(m for m, _ in lum) / len(lum) > 0.36 or sum(b for _, b in lum) / len(lum) > 0.18   # claro de media o con zonas blancas
    except Exception:
        return False


def _marcar_claves(ps):
    """La frase clave del bloque (la serif): la palabra principal (o la de más peso) y su vecina de contenido — «three mistakes», «visual
    effects», «25% smaller». Hasta 3 palabras y 23 letras. Marca `clave` en `ps` y devuelve los índices."""
    def contenido(i):
        p = _plegar(ps[i]['texto'])
        return len(p) >= 3 and p not in CONECTORAS and p not in DEBILES

    def puntaje(i):
        p = _plegar(ps[i]['texto'])
        if re.search(r'\d', p):
            return 2.2
        if not contenido(i):
            return 0.0
        v = min(len(p), 10) / 10.0 + (0.9 if p in ENFASIS else 0.0)
        if i == len(ps) - 1 or not any(contenido(j) for j in range(i + 1, len(ps))):
            v += 0.35                                                    # el foco va al final de la frase
        if i > 0 and ps[i]['texto'][:1].isupper():
            v += 0.3                                                     # nombre propio
        if i > 0 and _numero(ps[i - 1]['texto']):
            v += 0.8                                                     # «three mistakes»
        return v
    if not ps:
        return []
    k = max(range(len(ps)), key=lambda i: (puntaje(i), i))
    if puntaje(k) < (0.85 if len(ps) >= 3 else 1.3):
        return []
    sel = [k]
    cifra = bool(re.search(r'\d', ps[k]['texto']))
    if k - 1 >= 0 and not cifra and (_numero(ps[k - 1]['texto']) or (contenido(k - 1) and _plegar(ps[k - 1]['texto']) not in ENFASIS)):
        sel.insert(0, k - 1)                                             # «visual effects», «three mistakes» (la cifra va con lo que sigue)
    elif cifra and k + 1 < len(ps) and contenido(k + 1):
        sel.append(k + 1)
    while sum(len(ps[i]['texto']) + 1 for i in sel) > 24 and len(sel) > 1:
        sel.pop(0 if sel[0] != k else -1)
    for i in sel:
        ps[i]['clave'] = True
    return sel


def planificar(plan, vertical=True, densidad='media', video='', det_de=None, foto_de=None, ia=True, idioma='es', estado=None,
               recorte_de=None, cara_de=None, usuario='', estilo='skill'):
    """Todas las piezas del Tema 5 (captions, elementos en pantalla, escenas) y las ventanas de pantalla dividida [{'ini', 'fin', 'bajar'}]
    (bajar: fracción del alto que baja la persona). `det_de(t)` → la detección de personas en ese segundo (fracciones del timeline) o None;
    `foto_de(t)` → ese fotograma como 'data:image/jpeg;base64,…' (para la tarjeta) o None; `recorte_de(t)` / `cara_de(t)` → las imágenes del
    sticker y de la pantalla final (edicion_pro_tema5_mm) o None. `estilo`: 'skill' (Tema 5) o 'editorial' (Tema 6, edicion_pro_tema6)."""
    bl = bloques()
    if not bl:
        return [], []
    editorial = estilo == 'editorial'
    import edicion_pro_tema6 as T6
    acento = acento_de_video(video) if video else ACENTOS['azul']
    velo = False                                                          # v5.4.52: sin el velo oscuro ovalado detrás del caption (se veía como una sombra fea); las letras llevan su sombra fina
    import edicion_pro_tema5_video as VI                              # el video, mirado con ffmpeg: tomas, luz, tono, movimiento → el estilo
    analisis = VI.analizar(video) if video else {}
    est = T6.estilo_video() if editorial else VI.estilo(analisis, video)
    plan['_cortes_video'] = list(analisis.get('cortes') or [])           # los cortes del propio video: ahí va la transición con zoom
    for b in bl:
        _marcar_claves(b['palabras'])
    temas = T6.temas_del_video(bl, frozenset(DEBILES)) if editorial else set()   # el tema del video: las claves de verdad que se repiten
    for b in bl:
        if editorial and not any(w.get('clave') for w in b['palabras']):     # Tema 6: cada bloque con su línea grande (como la referencia)
            ps = b['palabras']
            if len(ps) <= 2 and sum(len(w['texto']) for w in ps) <= 16:
                for w in ps:
                    w['clave'] = True
            else:
                k = next((i for i in range(len(ps) - 1, -1, -1) if len(_plegar(ps[i]['texto'])) >= 4 and _plegar(ps[i]['texto']) not in CONECTORAS
                          and _plegar(ps[i]['texto']) not in DEBILES), None)
                if k is not None:
                    ps[k]['clave'] = True
                    if (k > 0 and _plegar(ps[k - 1]['texto']) not in CONECTORAS and _plegar(ps[k - 1]['texto']) not in DEBILES
                            and len(ps[k - 1]['texto']) + len(ps[k]['texto']) <= 17):
                        ps[k - 1]['clave'] = True
    todas = [(b['ini'] + w['t'], _plegar(w['texto']), w['texto'], n, j) for n, b in enumerate(bl) for j, w in enumerate(b['palabras'])]
    dur = max(b['fin'] for b in bl)
    ocupado = [(float(m.get('ini', 0)) - 0.3, float(m.get('ini', 0)) + float(m.get('dur', 0)) + 0.3) for m in plan.get('broll') or []]
    ocupado += [(p['ini'] - 0.3, p['fin'] + 0.3) for p in plan.get('piezas') or [] if p.get('pieza') in PIEZAS_QUE_QUEDAN]

    def libre(a, b, extra=()):
        return not any(a < o1 and o0 < b for o0, o1 in list(ocupado) + list(extra))

    piezas, divididas, elementos, escenas = [], [], [], []

    def elemento(comp, a, b, valores, motivo):
        a, b = max(0.0, a), min(dur + 0.4, b)
        if editorial or b - a < 1.0 or not libre(a, b, [(e['ini'], e['fin']) for e in elementos]):   # (el Tema 6 no lleva pasos ni deslizador)
            return
        elementos.append({'pieza': 'skill', 'remotion': comp, 'capa': 'delante', 'ini': round(a, 3), 'fin': round(b, 3), 'motivo': motivo,
                          'valores': dict(valores, y=Y_ELEMENTO, acento=acento)})

    # --- 1) elementos en pantalla: la lista del gancho, los pasos, el «de A a B»
    n_lista = None
    for i, (t, p, txt, nb, j) in enumerate(todas):
        if t > 8.0:
            break
        n = _numero(txt)
        if n and 2 <= n <= 7 and i + 1 < len(todas) and todas[i + 1][1] not in CONECTORAS:
            n_lista = n
            elemento('PasosT5', t - 0.1, max(bl[nb]['fin'], t + 2.2) + 0.4, {'n': n, 'gancho': True}, f'gancho: {n} cosas')
            break
    vistos = {}
    for i, (t, p, txt, nb, j) in enumerate(todas):
        k = None
        if p in PREFIJO_NUMERO and i + 1 < len(todas):
            k = _numero(todas[i + 1][2])
        elif n_lista and p in ORDINALES and ORDINALES[p] <= n_lista and (j == 0 or todas[i - 1][1] in ('and', 'y', 'e', 'el', 'la', 'the', 'o'))                 and not (i + 1 < len(todas) and todas[i + 1][1] in ('of', 'de', 'do', 'da')):
            k = ORDINALES[p]                                             # «primero…» solo si el gancho anunció una lista (no «Fourth of July»)
        if k and k <= (n_lista or 7) and t - vistos.get(k, -99) > 6.0:            # «número uno» repetido (otra toma): una vez
            vistos[k] = t
            elemento('PasosT5', t - 0.05, t + 2.7, {'n': max(n_lista or 3, k), 'actual': k}, f'paso {k}')
    if n_lista:                                                          # el cierre: «cambia estas tres cosas» → todos hechos
        for t, p, txt, nb, j in todas:
            if t > dur * 0.72 and _numero(txt) == n_lista:
                elemento('PasosT5', t - 0.1, t + 3.0, {'n': n_lista, 'actual': n_lista + 1}, 'los pasos, completos')
                break
    rango_t = -99.0
    for i, (t, p, txt, nb, j) in enumerate(todas):
        if p not in DESDE or t - rango_t <= 10 or i + 3 >= len(todas):
            continue
        izq = todas[i + 1]
        for z in range(i + 2, min(i + 4, len(todas) - 1)):
            der = todas[z + 1]
            if todas[z][1] in HASTA and izq[1] not in CONECTORAS and der[1] not in CONECTORAS and len(izq[1]) >= 4 and len(der[1]) >= 4:
                elemento('DeslizadorT5', t - 0.1, der[0] + 1.6, {'izq': izq[2].strip('.,!?').capitalize(), 'der': der[2].strip('.,!?').capitalize()},
                         f'de {izq[2]} a {der[2]}')
                rango_t = t
                break
    piezas += elementos
    import edicion_pro_tema5_escenas as DIR
    propuestas = []
    if ia:                                                               # la IA local (Qwen3) lee las frases y propone qué ilustrar en CUALQUIER tema
        try:
            import ia_texto
            propuestas = ia_texto.escenas([' '.join(w['texto'] for w in b['palabras']) for b in bl], idioma, estado)
        except Exception:
            propuestas = []
    # v5.5.3: las escenas a pantalla completa del director (edicion_pro_escenas + Escenas9.tsx): pictograma, tablero, polaroid, fecha, chat…
    #         la IA las elige con el mismo menú que en la PRO de los Temas 1–4 (solo esas familias); sin IA, sus reglas
    escenas_mg = []
    try:
        import edicion_pro_kit7 as K7
        txs = [w['texto'] for b in bl for w in b['palabras']]
        tms = [b['ini'] + w['t'] for b in bl for w in b['palabras']]
        frs, k0 = [], 0
        for b in bl:
            frs.append(list(range(k0, k0 + len(b['palabras']))))
            k0 += len(b['palabras'])
        escenas_mg = [m for m in K7.planificar(txs, [K7._plegar(x) for x in txs], tms, frs, idioma, video, dur, ia=ia, estado=estado, solo_escenas=True)
                      if m.get('pantalla')]
    except Exception:
        escenas_mg = []
    if ia:
        try:
            import ia_texto
            ia_texto.liberar()                                           # la GPU, entera para el Magic Mask y Resolve
        except Exception:
            pass
    de_ia = DIR.desde_ia(bl, propuestas, dur)                           # validadas contra lo que se dice

    # --- 1b) las mejoras de v5.4.52 (edicion_pro_tema5_mm): la pantalla final, el sticker del gancho, las tarjetas encima de la cabeza (mapa,
    #         gráfica, tachado, lista), la órbita alrededor de la cabeza y el foco en blanco y negro. Antes que las escenas: lo suyo lo dice ESA frase.
    extra = []
    try:
        import edicion_pro_tema5_mm as MM
        try:
            import edicion_pro_ograf as OG3
            disp3d = frozenset(OG3.iconos3d())
        except Exception:
            disp3d = frozenset()
        # v5.5.4: el hueco de las FOTOS de internet se reserva (la órbita o una tarjeta ya no se lo quitan: el usuario no veía ninguna)
        cortes_v = (analisis or {}).get('cortes')
        reservas = [(m['t'] - 0.6, m['t'] + m['dur'] + 0.3) for m in escenas_mg if m.get('fam') == 'foto' and m['props'].get('foto') and m['t'] >= 1.8
                    and (VI.antes_del_inserto(m['t'] - 0.2, m['t'] + m['dur'], cortes_v) or 0) >= m['t'] + 1.8]
        extra = MM.momentos(bl, dur, idioma, acento, libre=lambda a, b: libre(a, b, [(e['ini'], e['fin']) for e in elementos] + reservas), det_de=det_de,
                            recorte_de=recorte_de, cara_de=cara_de, densidad=densidad, usuario=usuario, iconos_3d=disp3d,
                            listas=[e for e in de_ia if (e['objetos'] or [{}])[0].get('tipo') == 'lista'], cortes=cortes_v)
    except Exception:
        extra = []
    if editorial:                                                        # Tema 6: el visor, la barra de búsqueda, el perfil, el equipo
        for x in extra:
            if x.get('pieza') == 'tarjeta':
                x['valores']['aspecto'] = 'blanco'
        try:
            import edicion_pro as EP

            def caras_de(t):
                return EP._caras(det_de(t)) if det_de else []
            extra += T6.elementos(bl, dur, idioma, libre=lambda a, b: libre(a, b, [(e['ini'], e['fin']) for e in elementos + extra]), det_de=det_de,
                                  cara_de=cara_de, usuario=usuario, debiles=frozenset(DEBILES), caras_de=caras_de)
        except Exception:
            pass
    ocupado += [(p['ini'] - 0.3, p['fin'] + 0.3) for p in extra]
    piezas += extra

    # --- 2) escenas de papel: el director (edicion_pro_tema5_escenas) ilustra lo que se dice; si no hay nada que ilustrar, icono 3D del concepto,
    #        la frase en tinta a pantalla completa o una foto de otro momento. Los cortes de escena caen en los cortes de frase (de bloque).
    try:
        import edicion_pro_ograf as OG
        import edicion_pro_planificador as PL
        disp = OG.iconos3d()
    except Exception:
        PL, disp = None, set()
    cada = CADA.get(densidad or 'media', 6.5)
    ocupado_elem = [(e['ini'], e['fin']) for e in elementos]
    candidatas, usados = [], set()                                       # (prioridad, a, z, valores, motivo)
    for e in DIR.escenas(bl, dur) + de_ia:
        if e['ini'] >= 1.8:
            candidatas.append((e['prioridad'], e['ini'], e['fin'], {'variante': 'objetos', 'mitad': e['mitad'], 'disposicion': e['disposicion'],
                                                                     'objetos': e['objetos'], '_ancla': e['ini'] + min(o['t'] for o in e['objetos'])}, e['motivo']))
    for m in escenas_mg:                                                 # por delante de las de la IA (3,0), pero como mucho una cada ~25 s (cupo)
        if m['t'] >= 1.8:
            candidatas.append((3.1, m['t'] - 0.2, m['t'] + m['dur'], dict(m['props'], mitad='completa', _comp=m['comp'], familia_mg=m['fam'], _ancla=m['t'] - 0.2,
                                                                         _orden=_prioridad_es(m['fam'])),
                               f"a pantalla completa «{m['fam']}»"))
    for nb, b in enumerate(bl):
        a, z = b['ini'], b['fin']
        if a < 2.5:
            continue
        if nb + 1 < len(bl) and z - a < 1.6 and bl[nb + 1]['ini'] - z < 0.3:
            z = bl[nb + 1]['fin']                                        # un bloque corto: la escena dura también el siguiente
        z = min(z, a + 4.5)
        ps = b['palabras']
        if z - a < 1.4 or not any(w.get('clave') for w in ps):
            continue
        if PL is not None:
            ic = None
            for w in ps:
                pl = PL.plegar(w['texto'])
                ic = PL.CONCEPTOS3D.get(pl) or PL.ICONO_A_3D.get(PL.CONCEPTOS.get(pl, ''))
                if ic and ic in disp and ic not in usados:
                    break
                ic = None
            if ic:
                usados.add(ic)
                candidatas.append((2.0, a, z, {'variante': 'icono', 'mitad': 'arriba', 'icono': ic}, f'icono 3D {ic}'))
                continue
        fin_frase = nb + 1 >= len(bl) or bl[nb + 1]['ini'] - b['fin'] > 0.3
        fuerte = any(_plegar(w['texto']) in ENFASIS or re.search(r'\d', w['texto']) for w in ps if w.get('clave'))
        if len(ps) >= 5 and a > dur * 0.4 and fin_frase and (fuerte or len(ps) >= 6) and ps[0]['texto'][:1].isupper():
            candidatas.append((1.0, a, z, {'variante': 'texto', 'mitad': 'completa'}, 'la frase en tinta'))   # una frase entera y con fuerza
        elif foto_de is not None and len(ps) >= 3:
            candidatas.append((0.5, a, z, {'variante': 'tarjeta', 'mitad': 'arriba'}, 'foto de otro momento'))

    def ajustar_a_frases(a, z):
        """[a, z] → del inicio del bloque en que cae  (la palabra que la trae) al final del bloque en que cae z (sin pasarse de 6,5 s)."""
        a2 = next((b['ini'] for b in bl if b['ini'] - 0.05 <= a < b['fin']), None)
        if a2 is None:
            a2 = next((b['ini'] for b in bl if b['ini'] >= a), a)
        z2 = next((b['fin'] for b in bl if b['ini'] < z <= b['fin'] + 0.05), None)
        if z2 is None:
            z2 = max([b['fin'] for b in bl if b['fin'] <= z] or [z])
        while z2 - a2 > 6.5:
            antes = [b['fin'] for b in bl if a2 < b['fin'] < z2]
            if not antes:
                break
            z2 = max(antes)
        return a2, z2

    hueco = max(2.0, cada - 3.0)                                         # segundos de video limpio entre dos escenas
    cupo = {1.0: max(1, int(dur // 30)), 0.5: max(1, int(dur // 45)), 3.1: max(1, int(dur // 25))}
    for pri, a, z, valores, motivo in sorted(candidatas, key=lambda c: (-c[0], -c[3].get('_orden', 0.0), c[1])):   # v5.5.4: a igual prioridad, la familia más importante (la foto de internet, la fecha)
        valores.pop('_orden', None)
        a2, z2 = ajustar_a_frases(valores.pop('_ancla', a), z)
        if valores.get('_comp'):
            z2 = min(z2, max(z, a2 + 2.4) + 0.8)                          # v5.5.4: una escena del director dura lo suyo (no la frase entera: 5,5 s de foto)
        ult_obj = a + max([float(o.get('t') or 0.0) for o in valores.get('objetos') or []] or [0.0]) + 1.0
        z2 = VI.antes_del_inserto(a2, z2, analisis.get('cortes'), minimo=max(2.2, ult_obj - a2)) or a2   # v5.5.3: tu B-roll no se tapa
        if z2 - a2 >= 1.4 and not libre(a2 + 0.02, z2 - 0.02, ocupado_elem):
            tope = min([o0 for o0, o1 in list(ocupado) + ocupado_elem if a2 + 0.02 < o1 and o0 < z2 - 0.02] or [a2])
            if tope - 0.05 - a2 >= max(2.2, ult_obj - a2) and libre(a2 + 0.02, tope - 0.07, ocupado_elem):
                z2 = tope - 0.05                                         # v5.5.4: se acorta antes de lo siguiente en vez de perderse
        if z2 - a2 < 1.4 or cupo.get(pri, 99) <= 0 or not libre(a2 + 0.02, z2 - 0.02, ocupado_elem):
            continue
        if any(a2 < e['fin'] - 0.02 and e['ini'] + 0.02 < z2 for e in escenas):
            continue                                                     # no se pisan
        tipo_de = lambda vv: vv.get('familia_mg') or (vv.get('objetos') or [{}])[0].get('tipo') or vv.get('variante')    # noqa: E731
        if any(tipo_de(e['valores']) == tipo_de(valores) and (abs(e['ini'] - z2) < 12 or abs(a2 - e['fin']) < 12) for e in escenas):
            continue                                                     # dos escenas iguales seguidas, no (dos frases en tinta, dos fotos…)
        pegadas = [e for e in escenas if abs(e['ini'] - z2) < 0.6 or abs(a2 - e['fin']) < 0.6]
        if any(a2 < e['fin'] + hueco and e['ini'] - hueco < z2 for e in escenas if e not in pegadas):
            continue                                                     # o pegadas (escena tras escena, como colores → marcas) o con video limpio entre medias
        if pegadas and (z2 - a2) + sum(e['fin'] - e['ini'] for e in pegadas) > 10.5:
            continue
        if pegadas and (editorial or valores.get('variante') == 'tarjeta' or valores.get('_comp')
                        or any(e.get('escena_mg') or e['valores'].get('variante') == 'tarjeta' for e in pegadas)):
            continue                                                     # v5.5.3: pegadas solo las del Tema 5 que flotan; ni tras el tablero ni a pantalla completa en el 6
        if det_de is not None and sum(1 for t in (a2 + 0.3, (a2 + z2) / 2.0, z2 - 0.3) if _nadie(det_de, t)) >= 2:
            continue                                                     # v5.5.3: ahí el video enseña otra cosa (tu B-roll, un cartel): no se tapa
        if valores['variante'] == 'tarjeta':
            toma = VI.toma_en(analisis, (a2 + z2) / 2.0) or {}
            if any(a2 + 0.2 < c < z2 - 0.2 for c in analisis.get('cortes') or []) or (toma and toma['fin'] - toma['ini'] < 5.0) or z2 > dur - 3.0 or a2 < 6.0:
                continue                                                 # v5.5.3: en tus tomas cortas (tu B-roll), con un corte, en el gancho o en la despedida, la foto de relleno sobra
            img = foto_de(min(dur - 0.5, a2 + dur * 0.35) if a2 < dur * 0.5 else max(0.5, a2 - dur * 0.35))
            if not img:
                continue
            valores = dict(valores, imagen=img)
        if valores.get('objetos'):                                       # los tiempos de los objetos, desde el nuevo inicio
            objs = [dict(o, t=round(max(0.12, o['t'] + (a - a2)), 3)) for o in valores['objetos']]
            if valores.get('disposicion') == 'objeto':                   # uno solo: ya está al empezar (lo que hace, p. ej. encogerse, a su tiempo)
                for o in objs:
                    if 't_escala' in o:
                        o['t_escala'] = round(o['t_escala'] + o['t'] - 0.2, 3)
                    o['t'] = min(o['t'], 0.2)
            valores = dict(valores, objetos=objs)
        cupo[pri] = cupo.get(pri, 99) - 1
        comp = valores.pop('_comp', None)
        if comp:                                                         # v5.5.3: escena del director (Escenas9): su color, salvo las que tienen el suyo
            import edicion_pro_escenas as ES
            escenas.append({'pieza': 'plantilla', 'remotion': comp, 'escena_mg': True, 'pantalla': True, 'capa': 'fondo', 'ini': round(a2, 3), 'fin': round(z2, 3),
                            'plantilla': f"escena_{valores.get('familia_mg')}", 'motivo': f"escena: {motivo}",
                            'valores': valores if comp in ES.SIN_ACENTO else dict(valores, acento=acento)})
            continue
        escenas.append({'pieza': 'skill', 'remotion': 'EscenaT5', 'capa': 'fondo', 'ini': round(a2, 3), 'fin': round(z2, 3),
                        'motivo': f"escena: {motivo}", 'valores': dict(valores, acento=acento)})
    escenas.sort(key=lambda e: e['ini'])
    previa, n_fondo = None, 0
    for e in escenas:
        v = e['valores']
        objs = v.get('objetos') or []
        uno = len(objs) == 1 and objs[0]['tipo'] not in ('ojo',)
        toma = VI.toma_en(analisis, (e['ini'] + e['fin']) / 2.0) or {}
        se_mueve = float(toma.get('movimiento') or 0.0) > 0.06 or not est.get('partir', True)
        if v['mitad'] == 'arriba' and se_mueve:                          # la cámara se mueve: no se parte (la persona se saldría de su mitad)
            v['mitad'] = 'encima' if uno and est.get('encima', True) else 'completa'   # v5.5.3: el Tema 6 no flota objetos (su estilo)
        elif uno and v.get('variante') == 'objetos':                   # un objeto solo: dónde va rota según el estilo del video, sin repetir
            opciones = [m for m in est['orden'] if m != previa] or est['orden']
            v['mitad'] = opciones[0] if not (opciones[0] == 'arriba' and se_mueve) else opciones[1 % len(opciones)]
        if v['mitad'] == 'encima':
            v['y'] = 73.0
        else:
            v['fondo'] = est['fondos'][n_fondo % len(est['fondos'])]
            n_fondo += 1
        previa = v['mitad']
        e['motivo'] += f" · {v['mitad']}" + (f" · {v.get('fondo')}" if v.get('fondo') else '')
    for e in escenas:
        if e['valores']['mitad'] == 'arriba':
            bajar = 0.25
            det = det_de((e['ini'] + e['fin']) / 2.0) if det_de else None
            if det and det.get('personas'):
                bajar = max(0.1, min(0.38, 0.56 - float(det['arriba'])))   # la coronilla, justo debajo del papel
            divididas.append({'ini': e['ini'], 'fin': e['fin'], 'bajar': round(bajar, 3)})
    piezas += escenas

    # --- 3) los captions: uno por bloque; sobre una escena cambian de sitio (y de tinta en el papel); de vez en cuando la clave va DETRÁS
    ultimo_detras = -99.0
    for nb, b in enumerate(bl):
        a, z = b['ini'], b['fin']
        esc = next((e for e in escenas if e['ini'] < z - 0.25 and a + 0.25 < e['fin']), None)
        enc = any(e['ini'] < z and a < e['fin'] for e in elementos)
        pant = next((p for p in extra if p.get('pantalla') and p['ini'] < z - 0.25 and a + 0.25 < p['fin']), None)   # sticker / pantalla final
        enc = enc or pant is not None or any(p['ini'] < z and a < p['fin'] for p in extra)   # con una mejora encima, la clave no va detrás
        if pant is not None:
            esc = None
        if esc is not None and esc['valores']['mitad'] == 'encima':
            esc, enc = None, True                                        # los objetos flotan sobre el video: caption normal, sin clave detrás
        ps = b['palabras']
        claves = [w for w in ps if w.get('clave')]
        if esc is not None and (esc['valores']['variante'] == 'cifra' or any(o['tipo'] in ('cifra', 'reloj', 'precio', 'grafica', 'app') and o.get('valor', o.get('insignia')) for o in esc['valores'].get('objetos') or [])):
            ps = [dict(w, clave=False) for w in ps]                        # la cifra ya está en la escena: el caption no la repite en grande
            claves = []
        fuerte = any(_plegar(w['texto']) in ENFASIS or re.search(r'\d', w['texto']) for w in claves) or nb == 0
        if (esc is None and not enc and fuerte and claves and sum(len(w['texto']) for w in claves) >= 5 and libre(a, z)
                and (nb == 0 or a - ultimo_detras >= CADA_DETRAS) and z - a >= 0.9):
            ultimo_detras = a
            piezas.append({'pieza': 'subtitulo', 'remotion': 'Subtitulo', 'capa': 'detras', 'persona': True, 'ajustar': True, 'ini': a, 'fin': z,
                           'motivo': 'caption Tema 5 (clave detrás)',
                           'valores': dict({'palabras': ps, 'modo': 'detras', 'y': 30.0, 'acento': acento},
                                           **({'estilo': 'editorial', 'acento': T6.LIMA} if editorial else {}))})
            ps = [dict(w, clave=False) for w in ps if not w.get('clave')]
            if not ps:
                continue
        valores = {'palabras': ps, 'modo': 'normal', 'tinta': 'clara', 'y': Y_NORMAL[bool(vertical)], 'escala': 1.0, 'acento': acento, 'velo': velo}
        if editorial:
            valores.update(estilo='editorial', y=T6.Y_NORMAL[bool(vertical)], acento=T6.color_clave(ps, temas, frozenset(ENFASIS)))
        ajustar = True
        if pant is not None:                                             # sobre el sticker o la pantalla final: arriba, claro, sin velo
            ajustar = False
            valores.update(velo=False, tinta='clara', y=Y_PAPEL, escala=1.1)
        if esc is not None and esc.get('escena_mg'):                     # v5.5.3: sobre una escena del director, abajo y en la tinta de su fondo
            import edicion_pro_escenas as ES
            claro_mg = (esc['remotion'], esc['valores'].get('variante')) in ES.CLAROS
            ajustar = False
            valores.update(velo=False, tinta='oscura' if claro_mg else 'clara', y=ES.Y_CAPTIONS[bool(vertical)], escala=0.95)
            esc = None
        if esc is not None and editorial and esc['valores'].get('variante') != 'texto':
            ajustar = False                                              # Tema 6: sobre la escena melocotón, la frase pequeña y en tinta, abajo
            valores.update(velo=False, tinta='oscura', y=T6.Y_ESCENA, escala=0.95)
            esc = None
        if esc is not None:
            ajustar = False
            cristal = esc['valores'].get('fondo') == 'cristal'
            if esc['valores']['mitad'] == 'arriba':
                valores.update(velo=False, tinta='clara' if cristal else 'oscura', y=Y_DIVIDIDA, escala=1.15)   # la frase, DENTRO del papel de arriba (como la referencia)
            elif esc['valores']['variante'] == 'texto':
                valores.update(velo=False, tinta='clara' if cristal else 'oscura', y=Y_PAPEL_TEXTO, escala=1.45)  # la frase ES la escena: más grande
            elif esc['valores'].get('disposicion') == 'fichas':
                valores.update(velo=False, tinta='clara' if cristal else 'oscura', y=Y_PAPEL_TEXTO, escala=1.1)   # la frase al centro y las fichas alrededor
            else:
                valores.update(velo=False, tinta='clara' if cristal else 'oscura', y=Y_PAPEL, escala=1.2)
        piezas.append({'pieza': 'subtitulo', 'remotion': 'Subtitulo', 'capa': 'subs', 'ajustar': ajustar, 'ini': a, 'fin': z, 'valores': valores,
                       'motivo': 'caption Tema 5' + (f" sobre la escena {esc['valores']['variante']}" if esc else '')})

    # --- 4) los acompañantes: una animación pequeña DEBAJO del caption que ilustra lo que se dice (país, saludo, redes, cifra, concepto)
    try:
        import edicion_pro_tema5_acomp as AC
        tapado = [(e['ini'] - 0.2, e['fin'] + 0.2) for e in escenas + elementos]
        tapado += [(p['ini'] - 0.1, p['fin'] + 0.1) for p in piezas if p.get('capa') == 'detras']
        tapado += list(ocupado)
        aspecto = 'blanco' if editorial or (analisis.get('oscuro') and int(hashlib.sha1(str(video).encode('utf-8')).hexdigest()[:2], 16) % 2) else 'cristal'
        piezas += AC.acompanantes(bl, idioma, tapado, acento, aspecto, dur, frozenset(DEBILES))
    except Exception:
        pass
    return piezas, divididas


def foto(video, t, ancho=540):
    """El fotograma `t` (s de la fuente) de `video` como data URL JPEG (la tarjeta de la escena), o None."""
    try:
        import base64
        import io

        import av
        with av.open(str(video)) as c:
            s = c.streams.video[0]
            c.seek(int(max(0.0, t) * 1e6))
            img = next(c.decode(s)).to_image().convert('RGB')
        img.thumbnail((ancho, ancho * 2))
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=84)
        return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return None


def subir_detras(p):
    """La clave «detrás» con su centro justo ENCIMA de la coronilla (la regla de la cara la deja debajo, como los titulares): la cabeza solo tapa
    la parte de abajo de las letras y se lee entera."""
    if p.get('pieza') == 'subtitulo' and p.get('capa') == 'detras':
        p['valores']['y'] = round(max(8.0, float(p['valores'].get('y', 30.0)) - 3.5), 1)


MEDIO_ACOMP = 4.5                       # media altura de un acompañante (% del alto)


def _pisa_cara(y, medio, caras):
    """v5.5.2: ¿algo centrado en `y` (% del alto) con media altura `medio` (%) pisa alguna de las `caras` (cajas en fracción, y desde arriba)?"""
    return any(y - medio < (k[3] + 0.02) * 100.0 and y + medio > (k[1] - 0.02) * 100.0 for k in caras or [])


def coordinar(piezas):
    """Tras la regla de la cara: si un caption bajó hasta el indicador de pasos o el deslizador, estos bajan un poco más; y cada acompañante va
    justo debajo de SU caption (si el caption quedó muy abajo, el acompañante no cabe y se quita)."""
    for c in [p for p in piezas if p.get('pieza') == 'acomp']:
        cap = next((p for p in piezas if p.get('pieza') == 'subtitulo' and p.get('capa') == 'subs' and abs(p['ini'] - c['_bajo'][0]) < 0.05), None)
        if cap is None:
            c['quitar'] = True
            continue
        v = cap['valores']
        dos = any(w.get('clave') for w in v.get('palabras') or []) and any(not w.get('clave') for w in v.get('palabras') or [])
        yc, esc = float(v.get('y', Y_NORMAL[True])), float(v.get('escala', 1.0))
        y = yc + (8.2 if dos else 6.2) * esc
        caras = cap.get('_caras') or []
        if y > 86.0 or _pisa_cara(y, MEDIO_ACOMP, caras):
            # v5.5.2 (regla oficial: ni cara ni caption): debajo no cabe o tapa una cara → sin acompañante. v5.5.4: ya NO se sube encima de su
            # caption (el usuario: «los iconos están muy arriba de los captions»)
            c['quitar'] = True
        else:
            c['valores']['y'] = round(y, 1)
            if c['fin'] > cap['fin'] + 0.15 and cap['fin'] + 0.15 - c['ini'] >= 1.2:
                c['fin'] = round(cap['fin'] + 0.15, 3)                   # v5.5.4: se va con SU caption («Comida» seguía bajo «y sorpresas»)
    for t in [p for p in piezas if p.get('pieza') == 'tarjeta' and not p.get('quitar')]:   # la tarjeta (encima de la cabeza) no pisa su caption
        v = t['valores']
        h = float(t.get('alto') or 0.2) * 100.0 * float(v.get('escala', 1.0))
        for c in piezas:
            if c.get('pieza') == 'subtitulo' and c['capa'] == 'subs' and c['ini'] < t['fin'] and t['ini'] < c['fin']:
                yc, medio = float(c['valores'].get('y', Y_NORMAL[True])), 6.5 * float(c['valores'].get('escala', 1.0))
                y = float(v.get('y', 17.0))
                if y + h / 2 > yc - medio - 1.0 and y - h / 2 < yc + medio + 1.0:
                    nuevo = yc + medio + 2.0 + h / 2
                    if nuevo + h / 2 <= 95.0:
                        v['y'] = round(nuevo, 1)                       # no cabía encima de la cabeza: debajo de los captions
                    else:
                        t['quitar'] = True
                    break
    for e in [p for p in piezas if p.get('pieza') == 'skill' and p['capa'] == 'delante']:
        for c in piezas:
            if c.get('pieza') == 'subtitulo' and c['capa'] == 'subs' and c['ini'] < e['fin'] and e['ini'] < c['fin']:
                yc = float(c['valores'].get('y', Y_NORMAL[True]))
                if yc > e['valores']['y'] - 10:
                    e['valores']['y'] = round(min(84.0, yc + 11.0), 1)
