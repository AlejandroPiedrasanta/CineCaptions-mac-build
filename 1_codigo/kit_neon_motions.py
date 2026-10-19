# CineCaptions · By Cinema Productions
# 1_codigo/kit_neon_motions.py — v5.5.13: los MOTIONS del Tema 1 neón (modo PRO) para cualquier video, con las piezas del kit «TEMA 1» del usuario.
"""
Lo que el ejemplo del kit (ejemplo_xela/escenas.js) ponía a mano, decidido por lo que se DICE (edicion_pro_planificador.candidatos):

    marca / evento nombrado al principio      -> notificacion (arriba)
    3+ conceptos con icono en ~10 s           -> orbita (velo morado; los captions de ese rato bajan a 1292, como en el kit)
    lista de 3 cosas cortas                   -> interruptores        otra lista -> filaEtiqueta (título + píldoras)
    lugar + fecha / hora                      -> tarjetaRuta («apunta bien» a mano)
    «guarda / envía / comparte / sígueme…»    -> checks (+ avion si se envía)
    cambios de sección (cortes o pausas)      -> barrido (2 como mucho)

Las piezas de ABAJO (interruptores, fila, ruta, checks) sustituyen al caption de ese momento: en el kit el motion ya cuenta lo que se dice.
escena_motions(...) -> [{'fn', 'a', 'ini', 'fin', 'abajo', 'capa'}]; ajustar_captions(escena, motions); piezas(motions) -> piezas de la PRO.
"""
import re
import unicodedata

import numpy as np

import kit_neon as KN

ICONO_KIT = {'trophy': 'trophy', 'music': 'music', 'cubiertos': 'utensils', 'utensils': 'utensils', 'calendarDays': 'cal', 'cal': 'cal', 'clock': 'clock',
             'gift': 'gift', 'mic': 'mic', 'users': 'users', 'heart': 'heart', 'corazon': 'heart', 'star': 'star', 'estrella': 'star', 'globe': 'globe',
             'pin': 'pin', 'mapPin': 'pin', 'chat': 'chat', 'gamepad': 'gamepad', 'grad': 'grad', 'graduationCap': 'grad', 'bell': 'bell', 'send': 'send',
             'link': 'link'}
RELLENO_ORBITA = ['star', 'heart', 'music', 'gift', 'users', 'chat']
CTA = {'es': ('guarda', 'guárdalo', 'guardalo', 'envía', 'envia', 'envíaselo', 'enviaselo', 'comparte', 'compártelo', 'sígueme', 'sigueme', 'síguenos',
              'suscríbete', 'suscribete', 'comenta', 'dale', 'activa', 'etiqueta', 'manda', 'mándaselo'),
       'en': ('save', 'send', 'share', 'follow', 'subscribe', 'comment', 'like', 'tag'),
       'pt': ('salva', 'salve', 'envia', 'envie', 'compartilha', 'compartilhe', 'segue', 'siga', 'inscreva', 'comenta', 'comente')}
ENVIO = ('envía', 'envia', 'envíaselo', 'enviaselo', 'comparte', 'compártelo', 'manda', 'mándaselo', 'send', 'share', 'envie', 'compartilhe')
MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'setiembre', 'octubre', 'noviembre', 'diciembre',
         'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december',
         'janeiro', 'fevereiro', 'março', 'maio', 'junho', 'julho', 'setembro', 'outubro', 'novembro', 'dezembro')
DIAS = ('lunes', 'martes', 'miércoles', 'miercoles', 'jueves', 'viernes', 'sábado', 'sabado', 'domingo', 'monday', 'tuesday', 'wednesday', 'thursday',
        'friday', 'saturday', 'sunday', 'segunda', 'terça', 'quarta', 'quinta', 'sexta')
HORA_SIGUE = ('de', 'am', 'pm', 'a', 'p', 'hrs', 'hr', 'horas', 'h', 'oclock')
TEXTOS = {'es': {'apunte': 'apunta bien', 'incluido': 'Todo incluido', 'conectados': 'Conectados'},
          'en': {'apunte': 'save the date', 'incluido': 'All included', 'conectados': 'Connected'},
          'pt': {'apunte': 'anota aí', 'incluido': 'Tudo incluído', 'conectados': 'Conectados'}}


def _plano(t):
    t = unicodedata.normalize('NFD', str(t).lower())
    return re.sub(r'[^a-z0-9%]', '', ''.join(c for c in t if unicodedata.category(c) != 'Mn'))


def _limpio(t):
    return re.sub(r'^\W+|\W+$', '', str(t)).strip()


def _cap(t):
    t = str(t).strip()
    return t[:1].upper() + t[1:]


def insignia(texto, ancho=320):
    """Imagen de relleno (data: URI) cuando no hay logo ni cara: el degradado magenta → violeta del neón con las iniciales."""
    import base64
    import io
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (ancho, ancho))
    d = ImageDraw.Draw(img)
    for y in range(ancho):
        k = y / (ancho - 1)
        d.line([(0, y), (ancho, y)], fill=(int(255 * (1 - k) + 122 * k), int(45 * (1 - k) + 43 * k), int(203 * (1 - k) + 242 * k)))
    letras = ''.join(p[0] for p in str(texto).split()[:2]).upper() or 'CC'
    f = KN._fuente('cond.ttf').font_variant(size=int(ancho * 0.46))
    d.text((ancho / 2, ancho / 2), letras, font=f, fill=(255, 255, 255), anchor='mm')
    b = io.BytesIO()
    img.save(b, 'JPEG', quality=88)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode('ascii')


def _hora_texto(n, resto):
    """«10» + «de la mañana» -> «10:00 a. m.» (kit); «7 pm» -> «7:00 p. m.»; si no se entiende, tal cual."""
    r = ' '.join(resto).lower()
    m = re.match(r'(\d{1,2})(?::(\d\d))?$', n)
    if not m:
        return n
    hh, mm = int(m.group(1)), m.group(2) or '00'
    if re.search(r'mañana|manana|am\b|a\.? ?m', r):
        return f'{hh}:{mm} a. m.'
    if re.search(r'tarde|noche|pm\b|p\.? ?m', r):
        return f'{hh}:{mm} p. m.'
    return f'{hh}:{mm} h'


def _fecha_hora(w, planos, meses, dias, t_ref, st, ventana=9.0):
    """(fecha, hora) dichas cerca de t_ref: fecha = del día de la semana (o el número) al mes («Sábado 10 de octubre»), hora = número + «de la
    mañana / tarde», am / pm u «horas». Cada una (texto, instante en que se dice) o None."""
    import edicion_pro_planificador as PL
    cerca = [i for i in range(len(w)) if abs(st(i) - t_ref) <= ventana]
    fecha = hora = None
    mes = next((i for i in cerca if planos[i] in meses), None)
    dia = next((i for i in cerca if planos[i] in dias and (mes is None or 0 <= mes - i <= 4)), None)
    if mes is not None or dia is not None:
        a = dia if dia is not None else max(cerca[0], mes - 2)
        b = mes if mes is not None else min(cerca[-1], dia + 2)
        txt = ' '.join(x for x in (_limpio(PL._txt(w[k])) for k in range(a, b + 1)) if x)
        fecha = (_cap(txt)[:26], st(a))
    for i in cerca:
        n = PL._txt(w[i]).strip(' .,')
        if not re.fullmatch(r'\d{1,2}(:\d\d)?', n) or i == (dia + 1 if dia is not None else -9) or (mes is not None and mes - 2 <= i < mes):
            continue                                                      # (el «10» de «sábado 10 de octubre» es la fecha)
        resto = [planos[k] for k in range(i + 1, min(len(w), i + 4))]
        if resto and (resto[0] in ('am', 'pm', 'horas', 'hrs', 'h') or (resto[0] == 'de' and len(resto) > 2 and resto[2] in ('manana', 'tarde', 'noche'))):
            hora = (_hora_texto(n, resto), st(i))
            break
    return fecha, hora


PERSONAS = ('jovenes', 'personas', 'amigos', 'amigas', 'influencers', 'chicas', 'chicos', 'invitados', 'invitadas', 'artistas', 'creadores', 'mujeres',
            'hombres', 'ninos', 'ninas', 'expertos', 'people', 'friends', 'guests', 'artists', 'creators', 'pessoas', 'amigos', 'convidados')


def _personas(video, t):
    try:
        import edicion_pro_persona as PE
        if not PE.disponible():
            return []
        return sorted((PE.personas(video, t) or {}).get('personas') or [], key=lambda p: -p.get('area', 0))
    except Exception:
        return []


def cara(video, t, lado=256, persona=None):
    """La cara de la persona más grande del fotograma t como data: URI (cuadrado alrededor de la cabeza), o None."""
    try:
        import base64
        import io
        import edicion_pro_persona as PE
        from PIL import Image
        ps = [persona] if persona else _personas(video, t)
        img = PE.fotograma(video, t)
        if not ps or img is None:
            return None
        h, w = img.shape[:2]
        p = ps[0]
        hx, hy = p['puntos'][0][:2]
        ancho = max(0.16, float((p.get('cabeza') or {}).get('ancho') or 0.12) * 2.1) * w
        cx, cy = hx * w, hy * h + 0.12 * ancho
        x0, y0 = max(0, int(cx - ancho / 2)), max(0, int(cy - ancho / 2))
        x1, y1 = min(w, int(x0 + ancho)), min(h, int(y0 + ancho))
        if x1 - x0 < 24 or y1 - y0 < 24:
            return None
        im = Image.fromarray(img[y0:y1, x0:x1]).resize((lado, lado), Image.LANCZOS)
        b = io.BytesIO()
        im.save(b, 'JPEG', quality=88)
        return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode('ascii')
    except Exception:
        return None


_CARTEL = {}


def _cartel_fotograma(video, dur, paso=1.5):
    """El fotograma MÁS COLORIDO en el que no hay nadie (un póster, la toma de producto, un paisaje), o None (en caché por video)."""
    clave = (str(video), round(float(dur), 1))
    if clave in _CARTEL:
        return _CARTEL[clave]
    mejor = None
    try:
        import edicion_pro_persona as PE
        from PIL import Image
        puntos = 0.0
        t = max(0.5, dur * 0.08)
        while t < dur * 0.95:
            img = PE.fotograma(video, t)
            if img is not None:
                # colorido de Hasler-Süsstrunk (un póster de muchos colores puntúa alto; un primer plano de UN color, no) × nitidez (bordes)
                rgb = np.asarray(Image.fromarray(img).resize((180, 320)), dtype=np.float32)
                rg, yb = rgb[..., 0] - rgb[..., 1], 0.5 * (rgb[..., 0] + rgb[..., 1]) - rgb[..., 2]
                color = float(np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean()))
                gris = rgb.mean(-1)
                detalle = float(np.abs(np.diff(gris, axis=0)).mean() + np.abs(np.diff(gris, axis=1)).mean())
                p = color * min(1.0, detalle / 12.0)
                if p > puntos * 1.05 and not _personas(video, t):
                    mejor, puntos = img, p
            t += paso
        if puntos < 45:
            mejor = None
    except Exception:
        mejor = None
    _CARTEL[clave] = mejor
    return mejor


def _cartel(video, dur, ancho=1000, alto=400):
    """El cartel recortado a `ancho` × `alto` por la franja del TÍTULO (la más colorida y con detalle, con preferencia por arriba: en un póster el
    título va arriba y es lo más vivo; el bloque de datos de abajo tiene más bordes pero menos color). data: URI o None."""
    try:
        import base64
        import io
        from PIL import Image
        mejor = _cartel_fotograma(video, dur)
        if mejor is None:
            return None
        h, w = mejor.shape[:2]
        cw, ch = (w, int(w * alto / ancho)) if w * alto / ancho <= h else (int(h * ancho / alto), h)
        rgbm = mejor.astype(np.float32)
        rg, yb = rgbm[..., 0] - rgbm[..., 1], 0.5 * (rgbm[..., 0] + rgbm[..., 1]) - rgbm[..., 2]
        filas = np.hypot(rg, yb).mean(axis=1) * np.sqrt(np.abs(np.diff(rgbm.mean(-1), axis=1)).mean(axis=1) + 1.0) * (1.3 - np.arange(h) / h)
        acum = np.concatenate([[0.0], np.cumsum(filas)])
        y0 = int(np.argmax(acum[ch:] - acum[:-ch])) if h > ch else 0
        x0 = (w - cw) // 2
        im = Image.fromarray(mejor[y0:y0 + ch, x0:x0 + cw]).resize((ancho, alto), Image.LANCZOS)
        b = io.BytesIO()
        im.save(b, 'JPEG', quality=88)
        return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode('ascii')
    except Exception:
        return None


def _emblema(video, dur, lado=640):
    """El EMBLEMA del cartel (kit: el «&» del póster en la notificación y en el centro de la órbita): el cuadrado más saturado y brillante por
    DEBAJO de la franja del título (el bloque de datos de abajo es texto claro sobre oscuro: poco color). data: URI o None."""
    try:
        import base64
        import io
        from PIL import Image
        img = _cartel_fotograma(video, dur)
        if img is None:
            return None
        h, w = img.shape[:2]
        rgb = img.astype(np.float32)
        mx, mn = rgb.max(-1), rgb.min(-1)
        sal = (mx - mn) / (mx + 1.0) * (mx / 255.0) ** 1.5             # (saturado y BRILLANTE: el emblema suele brillar sobre el fondo)
        xs = (np.arange(w) - w / 2.0) / (0.22 * w)
        sal = sal * np.exp(-0.5 * xs * xs)[None, :]                    # (en un cartel, el emblema va centrado; las manchas del borde, no)
        # la franja del título (la misma cuenta que _cartel, 1000 × 400)
        ch = min(h, int(w * 0.4))
        rg, yb = rgb[..., 0] - rgb[..., 1], 0.5 * (rgb[..., 0] + rgb[..., 1]) - rgb[..., 2]
        filas = np.hypot(rg, yb).mean(axis=1) * np.sqrt(np.abs(np.diff(rgb.mean(-1), axis=1)).mean(axis=1) + 1.0) * (1.3 - np.arange(h) / h)
        acum = np.concatenate([[0.0], np.cumsum(filas)])
        y_tit = int(np.argmax(acum[ch:] - acum[:-ch])) + ch if h > ch else 0
        s = max(16, int(w * 0.42))
        y_max = int(h * 0.68)                                          # (abajo van los datos: fecha, hora, lugar)
        if y_max - y_tit < s:
            y_tit = max(0, y_max - s)
        ii = np.zeros((h + 1, w + 1), np.float64)
        ii[1:, 1:] = sal.cumsum(0).cumsum(1)
        mejor, pos = -1.0, None
        for y in range(y_tit, y_max - s + 1, 4):
            sumas = ii[y + s, s:] - ii[y, s:] - ii[y + s, :-s] + ii[y, :-s]
            x = int(np.argmax(sumas))
            if sumas[x] > mejor:
                mejor, pos = float(sumas[x]), (x, y)
        if pos is None or mejor / (s * s) < 0.08:
            return None
        x, y = pos
        ven = sal[y:y + s, x:x + s]                                    # (centrado en el centro de masa de lo que brilla, no en la esquina de la ventana)
        if ven.sum() > 0:
            cy, cx = (np.indices(ven.shape) * ven[None]).reshape(2, -1).sum(1) / ven.sum()
            x = int(min(max(0, x + cx - s / 2), w - s))
            y = int(min(max(0, y + cy - s / 2), h - s))
        m = int(s * 0.08)                                              # (un poco de aire alrededor)
        x0, y0 = max(0, x - m), max(0, y - m)
        x1, y1 = min(w, x + s + m), min(h, y + s + m)
        im = Image.fromarray(img[y0:y1, x0:x1]).resize((lado, lado), Image.LANCZOS)
        b = io.BytesIO()
        im.save(b, 'JPEG', quality=88)
        return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode('ascii')
    except Exception:
        return None


COLA_CIERRE = 1.2                  # s de cierre gráfico DESPUÉS del video (panel + cartel + la última palabra), como el kit
# la palabra que dice QUÉ es lo que se nombra (kit: «Glass Collective · Banda»)
CATEGORIAS = {'banda': 'Banda', 'bandas': 'Banda', 'grupo': 'Grupo', 'grupos': 'Grupo', 'artista': 'Artista', 'artistas': 'Artista',
              'cantante': 'Cantante', 'cantantes': 'Cantante', 'chef': 'Chef', 'chefs': 'Chef', 'invitado': 'Invitado', 'invitados': 'Invitado',
              'invitada': 'Invitada', 'ponente': 'Ponente', 'ponentes': 'Ponente', 'marca': 'Marca', 'marcas': 'Marca', 'empresa': 'Empresa',
              'band': 'Band', 'bands': 'Band', 'artist': 'Artist', 'artists': 'Artist', 'singer': 'Singer', 'guest': 'Guest', 'guests': 'Guest',
              'speaker': 'Speaker', 'speakers': 'Speaker', 'brand': 'Brand', 'company': 'Company'}


def _libre(a, b, ocupado, holgura=0.6):
    return all(b + holgura <= x or a >= y + holgura for x, y in ocupado)


def escena_motions(palabras, idioma='es', duracion=None, cortes=None, imagen=None, video=None, usuario=None):
    """Los motions del kit para este video (tiempos en s del video). `imagen` = data URI (logo o cara) para la notificación y el centro de la órbita;
    sin ella, una insignia con las iniciales. Con `video` también los que necesitan mirar el video: la etiqueta de quien presenta (con su cara),
    los avatares de las personas que se nombran («3 jóvenes influencers») y el degradado morado en los planos sin nadie (B-roll)."""
    import edicion_pro_planificador as PL
    lang = PL.idioma_de(idioma)
    T = TEXTOS.get(lang, TEXTOS['es'])
    w = PL.unir_partidas([p for p in (palabras or []) if PL._txt(p) and p.get('start') is not None])
    if not w:
        return []
    dur = float(duracion or (float(w[-1]['end']) + 1.0))
    if imagen is None and video:
        imagen = _emblema(video, dur)                    # (kit: el «&» del cartel en la notificación y en la órbita; sin cartel, la insignia)
    fr = PL.frases_de(w)
    cands = PL.candidatos(w, fr, None, idioma)

    def st(i):
        return round(float(w[i]['start']), 3)

    def en(i):
        return round(float(w[i].get('end') or w[i]['start']), 3)

    planos = [_plano(PL._txt(x)) for x in w]
    verbos = {_plano(v) for v in CTA.get(lang, ()) + CTA['es']}
    out, bajos, altos, cortinas = [], [], [], []

    def poner(fn, a, ini, fin, abajo=False, capa='delante', ocupa=None):
        out.append({'fn': fn, 'a': a, 'ini': round(ini, 3), 'fin': round(fin, 3), 'abajo': abajo, 'capa': capa})
        poner.ultimo = out[-1]
        if fn != 'barrido':                    # (una cortinilla es una transición: acompaña a lo que entra, no le quita el sitio)
            (bajos if abajo else altos).append(ocupa or (ini, fin))
        else:
            cortinas.append((ini, fin))

    # 1) llamada a la acción (en el último 45 %): checks con lo que se pide, y el avión si se envía
    items = []
    for i in [i for i in range(len(w)) if planos[i] in verbos and st(i) > dur * 0.55]:
        if items and st(i) <= items[-1][2]:
            continue
        j, trozo = i, []
        while j < len(w) and len(trozo) < 5 and (j == i or planos[j] not in verbos):
            trozo.append(_limpio(PL._txt(w[j])))
            if re.search(r'[,.;!?]$', PL._txt(w[j])):
                break
            j += 1
        txt = _cap(' '.join(x for x in trozo if x))
        if len(txt) >= 4:
            items.append([txt[:30], st(i), en(min(j, len(w) - 1))])
    if items:
        items = items[:3]
        tin, tout = items[0][1] - 0.15, items[-1][2] + 1.4
        poner('checks', {'items': [[t, a] for t, a, _ in items], 'tout': round(tout, 3)}, tin, tout + 0.3, abajo=True)
        envio = next((a for t, a, _ in items if _plano(t.split()[0]) in {_plano(v) for v in ENVIO}), None)
        if envio is not None:
            poner('avion', {'t0': round(envio + 0.07, 3)}, envio, envio + 1.3, capa='iconos')
    # 2) lugar + fecha / hora: la tarjeta de ruta
    meses, dias = {_plano(m) for m in MESES}, {_plano(d) for d in DIAS}
    ruta_info = {}
    lugares = [c for c in cands if c['tipo'] in ('lugar', 'nombre') and c.get('presencia')] or [c for c in cands if c['tipo'] == 'lugar']
    for c in lugares:
        t_l = st(c['i'])
        fecha, hora = _fecha_hora(w, planos, meses, dias, t_l, st)
        if fecha or hora:
            hitos = [[c['texto'], t_l]] + ([[hora[0], hora[1]]] if hora else []) + ([[fecha[0], fecha[1]]] if fecha else [])
            ts = [h[1] for h in hitos]
            tin, tout = min(ts) - 1.9, max(ts) + 1.5
            if _libre(tin, tout, bajos):
                # (kit: debajo del sitio, su dirección; aquí la ciudad o el lugar que se nombra con él, si lo hay)
                dire = next((x['texto'] for x in cands if x['tipo'] in ('lugar', 'pais') and x is not c and 0 <= x['i'] - c['fin_i'] <= 4), '')
                poner('tarjetaRuta', {'tin': round(tin, 3), 'tout': round(tout, 3), 'titulo': c['texto'], 'direccion': dire[:70],
                                      'hitos': [[h[0], round(h[1], 3)] for h in hitos], 'calles': [], 'apunte': [T['apunte'], round(tin + 0.06, 3)]},
                      tin, tout + 0.4, abajo=True)
                ruta_info.update(fin=tout + 0.4, lugar=c['texto'], ciudad=dire, fecha=fecha, hora=hora)
                break
    # 3) listas: 3 cosas cortas -> interruptores; si no, título + píldoras
    for c in [c for c in cands if c['tipo'] == 'lista']:
        its = [it for it in c.get('items') or [] if it.get('texto')]
        if not its or any(_plano(it['texto'].split()[0]) in verbos for it in its):
            continue                                                       # (las acciones ya van en los checks)
        # cada cosa, por su palabra clave (kit: «Premios», «Charlas», «Networking»): la que tiene icono; si no, la primera que no es de relleno
        cortos, iconos, t_on = [], [], []
        for it, defecto in zip(its, ('trophy', 'chat', 'users', 'star')):
            n = max(1, len(it['texto'].split()))
            con = next((x for x in cands if x['tipo'] == 'concepto' and it['i'] <= x['i'] < it['i'] + n), None)
            k = con['i'] if con else next((k for k in range(it['i'], min(len(w), it['i'] + n)) if planos[k] not in PL.STOP and len(planos[k]) > 2), it['i'])
            cortos.append(_limpio(PL._txt(w[k])))
            iconos.append(ICONO_KIT.get((con or {}).get('icono', ''), defecto))
            t_on.append(st(it['i']))
        if len(its) == 3:
            tin, tder = t_on[0] - 0.12, t_on[-1] + 1.0
            tout = tder + 0.55
            if _libre(tin, tout, bajos):
                poner('interruptores', {'tin': round(tin, 3), 'tout': round(tout, 3), 'tDerecha': round(tder, 3), 'etiqueta': T['incluido'],
                                        'filas': [[_cap(x)[:18], ic, t] for x, ic, t in zip(cortos, iconos, t_on)], 'avatares': []},
                      tin, tout + 0.35, abajo=True)
                continue
        titulo = next((x['texto'] for x in cands if x['tipo'] in ('fuerte', 'concepto') and 0 <= t_on[0] - st(x['i']) <= 4), cortos[0])
        tin, tout = t_on[0] - 0.4, t_on[-1] + 1.6
        if _libre(tin, tout, bajos):
            poner('filaEtiqueta', {'titulo': str(titulo).upper()[:12], 't': round(tin, 3), 'tout': round(tout, 3),
                                   'pills': [[_cap(' '.join(it['texto'].split()[:3]))[:22], ic, t] for it, ic, t in zip(its, iconos, t_on)]}, tin, tout + 0.35, abajo=True)
    # 4) la notificación: la marca o el evento que se nombra al principio (dos palabras o más), con lo que la acompaña. Con el video y un «cartel»
    #    (el fotograma más colorido sin nadie: el póster, la toma de producto), como el kit: la notificación entra ANTES de adelanto y al nombrar
    #    el evento el video se encoge a la tarjeta de arriba (pantalla dividida, la placa) con el cartel abajo y sus píldoras; al salir, cortinilla.
    marca = next((c for c in cands if c['tipo'] == 'nombre' and len(c['texto'].split()) >= 2 and st(c['i']) < dur * 0.4), None)
    fin_noti = None
    if marca:
        t_m = st(marca['i'])
        extra = [c['texto'] for c in cands if c['tipo'] in ('nombre', 'lugar') and c is not marca and 0 < st(c['i']) - t_m <= 6]
        if not extra:                         # (sin otro nombre cerca: la segunda línea es el resto de la frase, no el mismo nombre otra vez)
            import edicion_pro_planificador as PL
            k0, trozo = marca['fin_i'] + 1, []
            if not re.search(r'[.!?]$', PL._txt(w[marca['fin_i']]).strip()):
                for k in range(k0, min(len(w), k0 + 6)):
                    trozo.append(_limpio(PL._txt(w[k])))
                    if re.search(r'[.!?]$', PL._txt(w[k]).strip()):
                        break
            resto = ' '.join(x for x in trozo if x)
            extra = [_cap(resto)[:34]] if resto else []
        cartel = _cartel(video, dur) if video else None
        hecho = False
        if cartel and t_m >= 4.5:
            cs = [float(c[0] if isinstance(c, (list, tuple)) else c) for c in (cortes or [])]
            corte = next((c for c in cs if abs(c - t_m) <= 0.6), None)
            s_in = round(corte if corte is not None else t_m - 0.1, 3)
            s_out = round(s_in + 2.33, 3)
            n_in = round(max(2.3, s_in - 2.55), 3)
            if _libre(n_in, s_out + 0.45, altos + bajos, 0.0):
                poner('notificacion', {'img': imagen or insignia(marca['texto']), 'titulo': marca['texto'], 'texto': ' · '.join(extra[:2]),
                                       'tin': n_in, 'tout': round(n_in + 2.23, 3)}, n_in, n_in + 2.6)
                chips = [[marca['texto'][:22], 'globe', round(t_m + 0.0, 3), -5]] + ([[extra[0][:22], 'link', round(t_m + 0.45, 3), 5]] if extra else [])
                poner('tarjetaInferior', {'rect': [40, 1160, 1000, 400, 52], 'img': cartel, 'tin': s_in, 'tout': s_out, 'chips': chips}, s_in, s_out + 0.45,
                      ocupa=(s_in, s_out))               # (kit: la órbita entra MIENTRAS la tarjeta se va)
                out[-1]['split'] = True
                poner('barrido', {'_args': [s_out]}, s_out - 0.5, s_out + 0.45, capa='iconos')
                fin_noti, hecho = s_out - 0.42, True
        if not hecho:
            tin = max(0.3, t_m - 0.1)
            tout = tin + 2.25
            if _libre(tin, tout, altos):
                poner('notificacion', {'img': imagen or insignia(marca['texto']), 'titulo': marca['texto'], 'texto': ' · '.join(extra[:2]),
                                       'tin': round(tin, 3), 'tout': round(tout, 3)}, tin, tout + 0.4)
                fin_noti = tout
    # 5) la órbita (kit: justo tras presentar el evento, los TEMAS de todo el video girando alrededor de su imagen): si el video nombra 3+ conceptos
    #    con icono, en la primera frase que empieza después de la notificación (o hacia el 15 % del video)
    ics = []
    for c in sorted([c for c in cands if c['tipo'] == 'concepto' and c.get('icono')], key=lambda c: c['i']):
        ic = ICONO_KIT.get(c['icono'], 'star')
        if ic not in ics:
            ics.append(ic)
    if len(ics) >= 3:
        desde = (fin_noti + 0.1) if fin_noti else dur * 0.15
        inicio = next((st(i) for i in range(len(w)) if st(i) >= desde), None)          # (kit: en cuanto se va la notificación)
        if inicio is not None:
            tin = max(inicio - 0.2, (fin_noti + 0.42) if fin_noti else 0.0)      # (después de que la notificación termine de salir)
            # (kit: la órbita se va justo antes de lo siguiente que pide su sitio: «3 JÓVENES INFLUENCERS» entra a los 0,2 s de irse)
            sig = min([st(c['i']) for c in cands if c['tipo'] in ('cifra', 'lista', 'cta', 'presentacion') and st(c['i']) > tin + 1.0] or [tin + 99])
            tout = min(tin + 3.5, sig - 0.2)
            if tout - tin >= 2.4 and _libre(tin, tout, bajos, 1.0) and _libre(tin, tout, altos, 0.0) and tout < dur - 2:
                ics = (ics + [x for x in RELLENO_ORBITA if x not in ics])[:6]
                anillos = [[ic, 250, -90 + 120 * (j // 2), 8] if j % 2 == 0 else [ic, 400, -30 + 120 * (j // 2), -5] for j, ic in enumerate(ics)]
                poner('orbita', {'tin': round(tin, 3), 'tout': round(tout, 3), 'img': imagen or insignia((marca or {}).get('texto') or 'CC'),
                                 'iconos': anillos}, tin, tout + 0.42)
    if video:
        _mirar_video(video, w, cands, fr, cortes, dur, st, en, planos, marca, poner, bajos, altos, usuario=usuario, ruta=ruta_info)
        # (kit: los interruptores acaban «Conectados» con dos de las caras que ya salieron en el arco de avatares)
        arco = next((m for m in out if m['fn'] == 'avataresArco'), None)
        for m in out:
            if m['fn'] == 'interruptores' and arco and len(arco['a'].get('imgs') or []) >= 2 and arco['ini'] < m['ini']:
                m['a'].update(avatares=[arco['a']['imgs'][1], arco['a']['imgs'][0]], etiqueta=T['conectados'])
    # 6) cortinillas: dos cambios de sección (cortes del video o pausas largas), separados y lejos de lo demás
    huecos = sorted({round(float(c[0] if isinstance(c, (list, tuple)) else c), 3) for c in (cortes or [])})
    huecos += [round(st(fr[k][0]) - 0.05, 3) for k in range(1, len(fr)) if st(fr[k][0]) - en(fr[k - 1][-1]) >= 0.35]
    puestas = []
    for tc in sorted(set(huecos)):
        if 5 < tc < dur - 6 and all(abs(tc - x) >= 10 for x in puestas + [c[0] + 0.5 for c in cortinas]) and _libre(tc - 0.5, tc + 0.5, bajos + altos + cortinas, 0.3):
            puestas.append(tc)
        if len(puestas) >= 2:
            break
    for tc in puestas:
        poner('barrido', {'_args': [round(tc, 3)]}, tc - 0.5, tc + 0.45, capa='iconos')
    # 7) el cierre del kit: el panel morado sube cuando ya se dijo la ÚLTIMA palabra (kit: «XELA» a 51,14 → barrido a 51,72; el video acaba a 51,93)
    #    y se QUEDA, con la última frase encima, COLA_CIERRE s más que el video (kit: 1,2 s de cierre gráfico, sin congelar fotogramas)
    if dur >= 15 and fr:
        tc = round(min(dur - 0.15, max(st(fr[-1][0]) + 0.6, st(len(w) - 1) + 0.55)), 3)
        fin = round(dur + COLA_CIERRE, 3)
        if 0.15 <= dur - tc <= 5.0 and _libre(tc, dur, bajos, 0.2):
            poner('barrido', {'_args': [tc, True]}, tc - 0.1, fin, capa='delante')
            out[-1]['cierre'] = True
            logo = _cartel(video, dur, 380, 480) if video else None
            if logo:                                                   # (kit: logoCierre, el cartel cae sobre el panel final)
                poner('logoCierre', {'img': logo, 't': round(tc + 0.1, 3)}, tc, fin, capa='delante')
    return sorted(out, key=lambda m: m['ini'])


def _mirar_video(video, w, cands, fr, cortes, dur, st, en, planos, marca, poner, bajos, altos, usuario=None, ruta=None):
    """Los motions que necesitan el video: etiqueta de quien presenta, avatares en arco y degradado en el B-roll."""
    import edicion_pro_planificador as PL
    # a) quien presenta («soy Ana»): la píldora con su cara arriba a la izquierda en el gancho (kit: «Presentadora»)
    pres = next((c for c in cands if c['tipo'] == 'presentacion' and st(c['i']) < 6), None)
    nombre = _cap(pres['texto']) if pres else (str(usuario).strip() if usuario else '')
    if nombre and st(0) < 1.5:
        foto = cara(video, max(0.5, st(pres['i']) if pres else 1.0))
        if foto and _libre(0.3, 2.6, altos, 0.1):
            poner('etiqueta', {'img': foto, 'nombre': nombre[:26], 'sub': (marca or {}).get('texto', ''), 'tin': 0.3, 'tout': 2.55}, 0.3, 2.9)
    # b) «3 jóvenes influencers»: sus caras en arco, sacadas de los planos que siguen (una por plano)
    limites = sorted({0.0, dur} | {float(c[0] if isinstance(c, (list, tuple)) else c) for c in (cortes or [])})
    for c in [c for c in cands if c['tipo'] == 'cifra']:
        try:
            n = int(str(c.get('numero') or '').strip())
        except ValueError:
            continue
        if not 2 <= n <= 5 or _plano(c.get('unidad') or '') not in PERSONAS and not any(planos[k] in PERSONAS for k in range(c['i'], min(len(w), c['i'] + 4))):
            continue
        t0 = st(c['i'])
        fotos = []
        for a, b in zip(limites, limites[1:]):
            if b <= t0 - 0.5 or a > t0 + 12 or len(fotos) >= n:
                continue
            f = cara(video, (max(a, t0 - 0.5) + b) / 2)
            if f:
                fotos.append(f)
        if len(fotos) >= 2 and _libre(t0 + 0.3, t0 + 2.4, altos, 0.0):
            poner('avataresArco', {'imgs': fotos[:n], 't0': round(t0 + 0.4, 3), 'tout': round(min(dur - 0.5, t0 + 2.4), 3), 'y': 980},
                  t0 + 0.3, min(dur, t0 + 2.8))
            # (kit: los avatares van con el degradado morado que sube desde abajo: se leen sobre la toma de B-roll)
            poner('degradado', {'_args': [round(t0 + 0.3, 3), round(min(dur - 0.5, t0 + 2.4), 3)]}, t0 + 0.2, min(dur, t0 + 2.75), capa='fondo')
        break
    # b2) «música en vivo» con los nombres que se dicen después (kit: lineaIcono + etiquetas con avatar: «Glass Collective · Banda · Xela»)
    import edicion_pro_planificador as PL
    for c in [c for c in cands if c['tipo'] == 'concepto' and c.get('icono')]:
        t_c = st(c['i'])
        nombres = [x for x in cands if x['tipo'] == 'nombre' and len(x['texto'].split()) >= 2 and 0.3 < st(x['i']) - t_c <= 12]
        if len(nombres) < 2:
            continue
        tout = st(nombres[-1]['i']) + 1.6
        if not (_libre(t_c, tout, bajos, 0.2) and _libre(t_c, tout, altos, 0.2)):
            continue
        frase = ' '.join(x for x in (_limpio(PL._txt(w[k])) for k in range(c['i'], min(len(w), c['i'] + 3))) if x)
        poner('lineaIcono', {'icono': ICONO_KIT.get(c['icono'], 'star'), 'texto': _cap(frase)[:24], 'tin': round(t_c, 3), 'tout': round(tout, 3)},
              t_c, tout + 0.4)
        items = []
        for x in nombres[:3]:
            tx = st(x['i'])
            nombre = x['texto']
            if x['i'] > 0 and planos[x['i'] - 1] == 'dj' and not _plano(nombre).startswith('dj'):
                nombre = 'DJ ' + nombre
            cat = next((CATEGORIAS[planos[k]] for k in range(x['i'] - 1, max(-1, x['i'] - 4), -1) if planos[k] in CATEGORIAS), '')
            lugar = next((y['texto'] for y in cands if y['tipo'] in ('lugar', 'pais') and y.get('frase') == x.get('frase')
                          and 0 <= st(y['i']) - tx <= 3), '')
            sub = ' · '.join(s for s in (cat, lugar) if s and _plano(s) not in _plano(nombre))
            items.append([cara(video, tx + 0.3) or insignia(nombre), nombre[:24], sub[:24], round(tx, 3)])
        poner('etiquetas', {'items': items, 'tout': round(tout, 3)}, items[0][3] - 0.1, tout + 0.4, abajo=True)
        break
    # d) tras la ruta, la pantalla de 4 (kit: el video arriba y tres tarjetas: el cartel, la FECHA en grande y el LUGAR) mientras se dice lo siguiente
    if ruta and ruta.get('fecha'):
        sig = next((f for f in fr if st(f[0]) >= ruta['fin'] - 0.6), None)
        foto = _cartel(video, dur, 316, 420)
        if sig is not None and foto:
            s_in = round(max(ruta['fin'] - 0.4, st(sig[0]) - 0.25), 3)
            s_out = round(min(dur - 1.0, s_in + 3.4), 3)
            m = re.search(r'(\d{1,2})\s+de\s+(\w+)', ruta['fecha'][0])
            dia_sem = ruta['fecha'][0].split()[0] if not ruta['fecha'][0][0].isdigit() else ''
            otros = [x for x in bajos + altos if abs(float(x[1]) - float(ruta['fin'])) > 0.05]   # (entra mientras la ruta sale: la ruta no la frena)
            if m and s_out - s_in >= 2.4 and _libre(s_in, s_out, otros, 0.0):
                hora = (ruta.get('hora') or ('', 0))[0].replace(' a. m.', '').replace(' p. m.', '')
                sub = ' · '.join(x for x in (_cap(dia_sem), hora) if x)
                poner('tarjetasProducto', {'rects': [[40, 1030, 316, 420, 40], [382, 1030, 316, 420, 40], [724, 1030, 316, 420, 40]], 'tin': s_in, 'tout': s_out,
                                           'contenidos': [{'img': foto}, {'grande': m.group(1), 'kick': m.group(2).upper(), 'sub': sub, 'icono': 'cal'},
                                                          {'texto': ruta['lugar'], 'sub': ruta.get('ciudad') or '', 'icono': 'pin'}]},
                      s_in, s_out + 0.45, abajo=True, ocupa=(s_in, s_out))
                ult = getattr(poner, 'ultimo', None)
                if ult is not None:
                    ult.update(split=True, split_tipo='cuatro',
                               tarjeta={'top': [40, 200, 1000, 800, 52], 'zoom_t': round(s_in + 1.33, 3), 'zoom': 1.12, 'region_w_frac': 0.833, 'dy_cara': 0.04})
    # c) los planos sin nadie (B-roll): el degradado morado que sube desde abajo, para que los captions se lean (kit: influencers, gamers)
    puestos = 0
    for a, b in zip(limites, limites[1:]):
        if b - a < 1.2 or puestos >= 4 or not _libre(a, b, bajos, 0.0):
            continue
        if _personas(video, (a + b) / 2):
            continue
        poner('degradado', {'_args': [round(a + 0.12, 3), round(b - 0.1, 3)]}, a, b + 0.3, capa='fondo')
        puestos += 1


def ajustar_captions(escena, motions):
    """Los captions con los motions: fuera los que coinciden con un motion de ABAJO (el motion ya lo dice) y, durante la órbita, más abajo (1292)."""
    bajos = [(m['ini'], m['fin']) for m in motions if m.get('abajo') and m.get('split_tipo') != 'cuatro']
    orbitas = [(m['ini'], m['fin']) for m in motions if m['fn'] == 'orbita']
    cierre = next((m for m in motions if m.get('cierre')), None)
    splits = [m for m in motions if m.get('split')]
    out, en_cuatro = [], {}
    for e in escena:
        a, b = float(e.get('t0', 0)), float(e['a'].get('tout', 0))
        cruce = [x for x, y in bajos if a < y and x < b and y - a > 0.5]     # (uno que ya se está yendo no lo frena: «HABRÁN CONCIERTOS»)
        if cruce:
            if min(cruce) - a < 1.0:
                continue
            b = round(min(cruce) - 0.05, 3)                                # (kit: «HABRÁN CONCIERTOS en vivo» se va justo antes de las etiquetas)
            e = dict(e, a=dict(e['a'], tout=b))
        if any(a < y and x < b for x, y in orbitas):
            e = dict(e, a=dict(e['a'], top=1292))
        sp = next((m for m in splits if a < m['a']['tout'] and m['a']['tin'] - 0.2 < b), None)
        if sp and sp.get('split_tipo') == 'cuatro':
            # (kit: «LA ENTRADA ES / 100% / GRATUITA» sobre la tarjeta de arriba; lo que se dice después, «no te lo puedes perder», DEBAJO de las tarjetas)
            k = en_cuatro.setdefault(id(sp), [])
            e = dict(e, a=dict(e['a'], top=640 if not k else 1456))
            if k:                                                      # (abajo, UNA línea serif fina: «no te lo puedes perder», 66 px)
                palabras, tiempos = [], []
                for it in e['a']['items']:
                    ws = str(it.get('txt') or '').split()
                    tt = it.get('t') if isinstance(it.get('t'), list) else [it.get('t')] * len(ws)
                    palabras += ws
                    tiempos += [float(x) for x in (list(tt) + [tt[-1]] * len(ws))[:len(ws)]]
                if palabras:
                    txt = ' '.join(palabras).lower()
                    e = dict(e, a=dict(e['a'], deco=[], items=[{'k': 'serif', 'txt': txt, 't': tiempos, 'size': KN._encaja(txt, 'serif', 66)}]))
            k.append(len(out))
        elif sp:
            e = dict(e, a=dict(e['a'], top=862, glide={'t': sp['a']['tout'], 'dy': 1150 - 862}))
        out.append(e)
    for (sid, ks) in en_cuatro.items():                     # (kit: el de arriba se queda mientras el de abajo se lee, si la pista lo permite)
        sp = next(m for m in splits if id(m) == sid)
        if len(ks) >= 2:
            k0 = ks[0]
            limite = float(out[k0 + 2]['t0']) - 0.6 if k0 + 2 < len(out) else 1e9
            nuevo = min(float(sp['a']['tout']) - 0.1, limite)
            if nuevo > float(out[k0]['a'].get('tout', 0)):
                out[k0] = dict(out[k0], a=dict(out[k0]['a'], tout=round(nuevo, 3)))
    if cierre and out and float(out[-1]['a'].get('tout', 0)) > cierre['ini']:
        # (kit: «PORQUE / esto es / XELA» sobre el panel, centrado más arriba, la palabra a 300 px y sin salida)
        ult = out[-1]
        # (kit: la palabra final en lima, letra a letra: «XELA»)
        items = [dict(it, size=KN._encaja(it['txt'], 'big', 300), fill='acento', letras=len(it['txt']) <= 10) if it['k'] == 'big' else it
                 for it in ult['a']['items']]
        out[-1] = dict(ult, a=dict(ult['a'], items=items, top=1060, tout=round(cierre['fin'] + 5.0, 3)))
        out[-1]['fin_clip'] = cierre['fin']
    return out


def piezas(motions):
    """Los motions -> piezas de la Edición PRO (un clip KitNeon por motion; el tiempo 0 del clip es su `ini`). Resolve no pone dos clips a la vez en
    una pista (colocar_pro los salta): cada motion va a una pista libre de su grupo y, si se cruza con otro, a la de ENCIMA (como en el kit, lo que
    se crea después queda encima). Debajo de los captions: PRO-VELO < PRO-DETRAS < PRO-DELANTE; encima: PRO-ICONOS; el degradado, en PRO-FONDO."""
    grupos = {'delante': ['velo', 'detras', 'delante'], 'fondo': ['fondo'], 'iconos': ['iconos']}      # (de abajo arriba)
    z = {'fondo': 0, 'velo': 1, 'detras': 2, 'delante': 3, 'iconos': 9}
    fin_de = {}
    out = []
    for m in sorted(motions, key=lambda m: m['ini']):
        llamada = {'fn': m['fn'], 'args': m['a']['_args']} if '_args' in m['a'] else {'fn': m['fn'], 'a': m['a']}
        opciones = grupos.get(m.get('capa', 'delante'), [m.get('capa', 'delante')])
        # por encima de lo que aún está en pantalla de su grupo (lo nuevo tapa a lo que se va) y en una pista libre
        minimo = max([z[p['capa']] + 1 for p in out if p['fin'] > m['ini'] + 1e-3 and p['capa'] in opciones] or [0])
        capa = next((c for c in opciones if z[c] >= minimo and fin_de.get(c, -1.0) <= m['ini'] + 1e-3), None)
        if capa is None:
            continue                                                  # (no hay pista libre: mejor sin él que tapado o perdido)
        fin_de[capa] = m['fin']
        out.append({'pieza': 'neon_motion', 'remotion': 'KitNeon', 'capa': capa, 'ini': m['ini'], 'fin': m['fin'],
                    'motivo': f"motion neón «{m['fn']}»", 'valores': {'escena': [llamada], 't0': m['ini'], 'tema': 'neon'}})
    return out
