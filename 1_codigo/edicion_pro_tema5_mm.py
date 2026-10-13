# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_tema5_mm.py — las mejoras de motion graphics y Magic Mask del Tema 5 (pedido del usuario, v5.4.52). Decide CUÁNDO va cada
# una (siempre por algo que se DICE; nunca un dato inventado) y prepara las imágenes que necesitan (el recorte de la persona con la IA local):
#   foco        «esto lo cambia TODO», «el secreto», «presta atención»…: el fondo en blanco y negro y la persona a color (Magic Mask)
#   orbita      un icono 3D del concepto gira alrededor de la cabeza: por detrás (debajo de la persona del Magic Mask) y por delante
#   sticker     en el gancho (la pregunta del principio): la imagen se congela y la persona se despega como un sticker con borde blanco
#   sombra      la clave grande DETRÁS de la persona lleva la sombra de la persona encima (se hornea en el clip de Remotion)
#   tarjetas    encima de la cabeza: el mapa del país que se nombra, la gráfica del % que se dice, la frase tachada («deja de…», «el error
#               es…») y la lista que se marca al nombrar cada cosa
#   final       «sígueme / suscríbete» al final: la pantalla final con la cara, el @usuario (si está en las opciones) y el botón que se pulsa
#   transiciones en los cortes (de V1 o del propio video): zoom con desenfoque de movimiento (lo arma colocar_pro con Fusion)
"""
    momentos(bl, dur, idioma, acento, libre, det_de, recorte_de, cara_de, densidad, usuario) -> piezas
    transiciones(cortes, ocupado, dur) -> [segundos]
    mapeo(clip, W, H) -> (fx, fy): fracciones de la FUENTE -> fracciones del TIMELINE (ajuste, zoom, Pan, Tilt del clip de V1)
    imagen_timeline(rgb, fx, fy, W, H, escala) -> PIL RGB del fotograma tal como se ve en el timeline
    sticker(rgb, alfa, fx, fy, W, H) -> (png data URL, caja [x0, y0, x1, y1] del timeline) | (None, None)
    cara(rgb, det) -> JPEG data URL de la cara (cuadrado) | None
    silueta(alfa, fx, fy, W, H, escala) -> numpy (alto, ancho) 0..1 en el timeline
    sombra_en_clip(entrada, salida, silueta) -> bool: la clave de Remotion con la sombra de la persona encima
"""
import base64
import io
import re

import edicion_pro_tema5_acomp as AC
import edicion_pro_tema5_escenas as DIR

FOCO = {  # frases que piden el foco (plegadas, palabras seguidas)
    'es': ['lo cambia todo', 'cambia todo', 'cambio todo', 'el secreto', 'la clave', 'presta atencion', 'pon atencion', 'escucha bien', 'la verdad es',
           'nadie te dice', 'nadie habla', 'lo mas importante', 'esto es importante', 'muy importante', 'imagina', 'nunca olvides', 'atencion'],
    'en': ['changes everything', 'changed everything', 'the secret', 'the key', 'pay attention', 'listen to me', 'the truth is', 'nobody tells you',
           'no one tells you', 'most important', 'this is important', 'really important', 'imagine', 'never forget'],
    'pt': ['muda tudo', 'mudou tudo', 'o segredo', 'a chave', 'presta atencao', 'preste atencao', 'a verdade e', 'ninguem te conta', 'mais importante',
           'isso e importante', 'imagina', 'nunca esqueca'],
}
# lo que ABRE una pregunta al principio de un bloque (sin «que», «como» o «cuando» sueltos: en español casi nunca preguntan sin «¿…?»)
INTERROGA = {'sabias', 'sabes', 'sabian', 'sabiam', 'quieres', 'queres', 'alguna', 'cuanto', 'cuanta', 'cuantos', 'cuantas', 'cual', 'cuales',
             'porque', 'what', 'whats', 'why', 'how', 'which', 'did', 'do', 'does', 'have', 'ever', 'want', 'are', 'can', 'would', 'should',
             'quanto', 'qual', 'voce', 'imagine', 'imagina'}
CTA = {'sigueme': 'seguir', 'siguenos': 'seguir', 'seguirme': 'seguir', 'siganme': 'seguir', 'follow': 'follow', 'segueme': 'seguir', 'sigam': 'seguir',
       'suscribete': 'suscribir', 'suscribanse': 'suscribir', 'subscribe': 'subscribe', 'inscrevase': 'suscribir'}
BOTON = {'seguir': {'es': ('Seguir', 'Siguiendo'), 'pt': ('Seguir', 'Seguindo'), 'en': ('Follow', 'Following')},
         'follow': {'es': ('Seguir', 'Siguiendo'), 'pt': ('Seguir', 'Seguindo'), 'en': ('Follow', 'Following')},
         'suscribir': {'es': ('Suscribirse', 'Suscrito'), 'pt': ('Inscrever-se', 'Inscrito'), 'en': ('Subscribe', 'Subscribed')},
         'subscribe': {'es': ('Suscribirse', 'Suscrito'), 'pt': ('Inscrever-se', 'Inscrito'), 'en': ('Subscribe', 'Subscribed')}}
BAJAR = {'baja', 'bajan', 'bajo', 'bajaron', 'bajar', 'cae', 'caen', 'cayo', 'cayeron', 'menos', 'perdi', 'perdio', 'perdieron', 'perder', 'pierdes',
         'drop', 'dropped', 'drops', 'fell', 'fall', 'falls', 'decrease', 'decreased', 'down', 'lose', 'lost', 'loses', 'less', 'cut',
         'cai', 'caiu', 'caem', 'perdeu', 'perder', 'diminuiu', 'reduce', 'reduced', 'reducir', 'reduje', 'redujo'}
SUBIR = DIR.CRECER | {'sube', 'suben', 'subio', 'subieron', 'subir', 'crece', 'crecen', 'crecio', 'crecieron', 'aumenta', 'aumento', 'aumentaron', 'mas',
                      'gane', 'gano', 'ganaron', 'up', 'rose', 'rise', 'more', 'gained', 'cresceu', 'subiu', 'aumentou'}
DEJA = {('deja', 'de'), ('dejen', 'de'), ('deje', 'de'), ('para', 'de'), ('paren', 'de'), ('pare', 'de'), ('stop',), ('quit',), ('dont',), ('nunca',), ('never',),
        ('evita',), ('eviten',), ('avoid',), ('evite',)}
ERRORES = {'error', 'errores', 'mistake', 'mistakes', 'mito', 'myth', 'erro', 'erros', 'mentira', 'lie'}
ES = {'es', 'is', 'era', 'was', 'e', 'son', 'are', 'sao'}
FUERTES = {'best', 'worst', 'mejor', 'peor', 'secret', 'secreto', 'free', 'gratis', 'huge', 'enorme', 'important', 'importante', 'mistake', 'error',
           'errores', 'million', 'millones', 'nobody', 'nadie', 'everything', 'todo', 'nunca', 'never', 'increible', 'incredible', 'brutal'}
Y = {'y', 'e', 'and', 'o', 'or', 'ou', 'ni', 'nor'}
ARTICULOS = {'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'the', 'a', 'an', 'os', 'as', 'um', 'uma', 'mi', 'mis', 'tu', 'tus', 'su', 'sus',
             'my', 'your', 'our', 'his', 'her', 'their', 'meu', 'minha', 'seu', 'sua'}
CADA_DENSIDAD = {'sobria': 0.5, 'media': 1.0, 'espectaculo': 1.5}


def _p(t):
    return AC.plegar(t)


def _limpio(t):
    return str(t).strip(' .,;:!?¡¿"\'()[]«»…“”')


def momentos(bl, dur, idioma='es', acento='#4C7DFF', libre=None, det_de=None, recorte_de=None, cara_de=None, densidad='media', usuario='',
             iconos_3d=frozenset(), listas=()):
    """Las piezas de las mejoras (ver arriba), sin pisarse entre ellas ni con lo que ya está (`libre(a, b)`). Cada pieza lleva 'mm' (su tipo)."""
    lang = (idioma or 'es')[:2]
    k = CADA_DENSIDAD.get(densidad or 'media', 1.0)
    todas = [(b['ini'] + w['t'], _p(w['texto']), w['texto'], n, j) for n, b in enumerate(bl) for j, w in enumerate(b['palabras'])]
    out = []

    def ok(a, z, aire=1.2):
        if libre is not None and not libre(a, z):
            return False
        return not any(a < p['fin'] + aire and p['ini'] - aire < z for p in out)

    def bloque_de(t):
        return next((n for n, b in enumerate(bl) if b['ini'] - 0.05 <= t < b['fin'] + 0.05), None)

    def fin_frase(n, minimo, maximo):
        """El final del bloque n, alargado al siguiente si va pegado y hace falta llegar a `minimo` segundos."""
        a, z = bl[n]['ini'], bl[n]['fin']
        while z - a < minimo and n + 1 < len(bl) and bl[n + 1]['ini'] - z < 0.35:
            n += 1
            z = bl[n]['fin']
        return min(z, a + maximo)

    def hay_persona(t):
        if det_de is None:
            return True
        try:
            return protagonista(det_de(t))
        except Exception:
            return False

    # 1) la pantalla final: se pide seguir / suscribirse en el último tramo
    for t, p, txt, nb, j in todas:
        if p in CTA and t >= max(dur * 0.6, dur - 10.0) and cara_de is not None:
            z = dur + 0.4
            a = max(t - 0.2, z - 4.5)
            if z - a < 1.8:
                a = z - 1.8
            if not ok(a, z, 0.4):
                break
            img = cara_de(min(dur - 0.3, a + 0.3))
            if not img:
                break
            boton, hecho = BOTON[CTA[p]].get(lang, BOTON[CTA[p]]['en'])
            out.append({'pieza': 'final', 'mm': 'final', 'remotion': 'FinalT5', 'capa': 'fondo', 'pantalla': True, 'ini': round(a, 3), 'fin': round(z, 3),
                        'motivo': f'pantalla final: «{_limpio(txt)}»', 'valores': dict(img, usuario=str(usuario or '')[:28], titulo=_limpio(txt).capitalize(),
                                                                                      boton=boton, hecho=hecho, acento=acento)})
            break
    # 2) el sticker del gancho: la pregunta del principio, la presentación («soy Ana», «I'm Ben») o su frase fuerte (énfasis o cifra)
    if recorte_de is not None:
        elegido = None
        for n, b in enumerate(bl):
            if b['ini'] > 8.0:
                break
            ps = b['palabras']
            pl = [_p(w['texto']) for w in ps]
            pregunta = bool(ps) and (pl[0] in INTERROGA or ps[0]['texto'].startswith('¿') or ps[-1]['texto'].endswith('?'))
            presenta = any(x in ('soy', 'im', 'sou') for x in pl[:4]) or any(pl[k:k + 2] in (['me', 'llamo'], ['my', 'name'], ['meu', 'nome'])
                                                                            for k in range(min(3, len(pl))))
            fuerte = any(w.get('clave') and (_p(w['texto']) in FUERTES or re.search(r'\d', w['texto'])) for w in ps)
            if b['ini'] >= 0.5 and (pregunta or presenta or (fuerte and b['ini'] <= 6.0)):
                elegido = n
                break
        if elegido is not None:
            a = bl[elegido]['ini']
            z = min(bl[elegido]['fin'], a + 1.8)
            if z - a >= 1.0 and ok(a, z) and hay_persona(a + 0.05):
                r = recorte_de(a + 0.04)
                if r:
                    out.append({'pieza': 'sticker', 'mm': 'sticker', 'remotion': 'StickerT5', 'capa': 'fondo', 'pantalla': True, 'ini': round(a, 3),
                                'fin': round(z, 3), 'motivo': 'gancho: sticker congelado', 'valores': dict(r, acento=acento)})
    # 3) las tarjetas encima de la cabeza
    try:
        import edicion_pro_planificador as PL
        paises = PL.paises()
    except Exception:
        paises = {}
    cupos = {'mapa': max(1, round(2 * k)), 'grafica': max(1, round(2 * k)), 'tachado': max(1, round(2 * k)), 'lista': max(1, round(2 * k))}
    ultima = {}

    def tarjeta(tipo, a, z, valores, motivo, alto):
        a, z = max(0.0, a), min(dur + 0.3, z)
        if cupos.get(tipo, 0) <= 0 or z - a < 1.6 or a - ultima.get(tipo, -99) < 12.0 or not ok(a, z):
            return False
        cupos[tipo] -= 1
        ultima[tipo] = a
        out.append({'pieza': 'tarjeta', 'mm': tipo, 'remotion': 'TarjetaT5', 'capa': 'delante', 'ajustar': True, 'alto': alto, 'ini': round(a, 3),
                    'fin': round(z, 3), 'motivo': f'tarjeta {tipo}: {motivo}', 'valores': dict(valores, tipo=tipo, acento=acento, y=17.0, escala=1.0)})
        return True

    # 3a) el país que se nombra
    for i in range(len(todas)):
        t, p, txt, nb, j = todas[i]
        for n in (3, 2, 1):
            clave = ''.join(x[1] for x in todas[i:i + n])
            if len(clave) >= 4 and clave in paises:
                iso, nombres = paises[clave]
                estamos = any(x[1] in AC.ESTAMOS for x in todas[max(0, i - 2):i])
                z = max(fin_frase(nb, 3.0, 4.0), t + 2.8)
                tarjeta('mapa', t - 0.15, min(z, t + 3.8), {'pais': iso, 'nombre': nombres.get(lang) or ' '.join(_limpio(x[2]) for x in todas[i:i + n]),
                                                          'kicker': AC.KICKER_LUGAR.get(lang, '') if estamos else ''}, nombres.get(lang, clave), 0.24)
                break
    # 3b) la cifra que sube o baja (un % o un número con «subió / creció / bajó…»)
    for i, (t, p, txt, nb, j) in enumerate(todas):
        c = DIR._cifra(txt)
        if c is None:
            continue
        valor, signo = c
        cerca = todas[max(0, i - 4):i] + todas[i + 1:i + 4]
        sig = todas[i + 1:i + 3]
        if not signo and sig and (sig[0][1] in ('percent', 'porciento', 'percento') or (sig[0][1] == 'por' and len(sig) > 1 and sig[1][1] == 'ciento')):
            signo = '%'
        sube = 1 if any(x[1] in SUBIR for x in cerca) else (-1 if any(x[1] in BAJAR for x in cerca) else 0)
        if (signo != '%' and not sube) or any(x[1] in DIR.TAMANO for x in cerca):
            continue                                                     # («25 % más pequeño»: eso lo cuenta la escena del icono que se encoge)
        if signo not in ('%', '$', '€', '£') and any(x[1] in DIR.DINERO for x in cerca):
            signo = '$'
        etiqueta = next((_limpio(x[2]) for x in reversed(todas[max(0, i - 4):i]) if len(x[1]) >= 4 and x[1] not in DIR.CONECTORAS
                         and x[1] not in SUBIR and x[1] not in BAJAR and not DIR._cifra(x[2])), '')
        tarjeta('grafica', t - 0.35, max(fin_frase(nb, 2.8, 3.6), t + 2.6), {'valor': valor, 'signo': signo, 'sube': sube, 'etiqueta': etiqueta},
                f'{valor}{signo}', 0.21)
    # 3c) la frase tachada: «deja de / stop / don't / evita …» o «el error (número uno) es …»
    for i, (t, p, txt, nb, j) in enumerate(todas):
        desde, kicker = None, ''
        for patron in DEJA:
            if tuple(x[1] for x in todas[i:i + len(patron)]) == patron:
                desde = i + len(patron)
        if desde is None and p in ERRORES:
            m = next((q for q in range(i + 1, min(i + 5, len(todas))) if todas[q][1] in ES), None)
            if m is not None:
                desde, kicker = m + 1, _limpio(txt).upper()
        if desde is None or desde >= len(todas) or todas[desde][3] not in (nb, nb + 1):
            continue
        frase = []
        for q in range(desde, min(desde + 4, len(todas))):
            if frase and ((todas[q][2][:1].isupper() and todas[q][2] not in ("I", "I'm")) or todas[q][0] - frase[-1][0] > 0.85):
                break                                                    # empieza otra oración («… inspección. Revisa…»: mayúscula o pausa)
            frase.append(todas[q])
            if re.search(r'[.!?;:]$', todas[q][2].strip()) or (q + 1 < len(todas) and todas[q + 1][3] != todas[q][3]
                                                                and bl[todas[q + 1][3]]['ini'] - bl[todas[q][3]]['fin'] > 0.35):
                break
        while frase and frase[-1][1] in DIR.CONECTORAS:
            frase.pop()
        texto = ' '.join(_limpio(x[2]) for x in frase)
        if len(frase) < 2 or len(texto) > 34:
            continue
        a = t - 0.2
        t_tachar = round(max(0.5, frase[-1][0] + 0.25 - a), 3)
        tarjeta('tachado', a, max(a + t_tachar + 1.4, fin_frase(nb, 2.2, 3.4)), {'texto': texto, 'kicker': kicker, 't_tachar': t_tachar},
                texto, 0.12 if len(texto) <= 26 else 0.16)
    # 3d) la lista: la que encontró la IA local (validada: cada cosa se dice tal cual) con 3 o más cosas; o «ubicación, precio e inspección»
    #     (cosas cortas separadas por comas y una «y», si la transcripción trae comas)
    for e in listas or []:
        o = (e.get('objetos') or [{}])[0]
        items = [str(x).strip().capitalize() for x in o.get('items') or [] if str(x).strip()][:4]
        tiempos = [float(x) for x in (o.get('tiempos') or [])[:len(items)]]
        if len(items) < 3 or len(tiempos) < len(items):
            continue
        pos = []                                                         # una lista de verdad: las cosas SEGUIDAS (entre una y otra solo «y»,
        for it in items:                                                 # una coma o un artículo); «tus ojos en la línea superior» no lo es
            pi = [_p(x) for x in str(it).split() if _p(x)]
            k = next((q for q in range(len(todas)) if pi and todas[q][1] == pi[0] and (not pos or q > pos[-1][1])), None)
            if k is None:
                break
            pos.append((k, k + len(pi) - 1))
        if len(pos) < len(items) or any(any(todas[q][1] not in Y and todas[q][1] not in ARTICULOS for q in range(pos[n][1] + 1, pos[n + 1][0]))
                                         or pos[n + 1][0] - pos[n][1] > 3 for n in range(len(pos) - 1)):
            continue
        base = float(e['ini']) + float(o.get('t') or 0.0) + 0.2
        a = base + tiempos[0] - 0.35
        z = max(base + tiempos[-1] + 1.5, a + 2.4)
        tarjeta('lista', a, min(z, a + 5.0), {'items': items, 'tiempos': [round(base + x - a, 3) for x in tiempos]}, 'IA: ' + ', '.join(items),
                0.08 + 0.055 * len(items))
    for nb, b in enumerate(bl):
        zona = [(b['ini'] + w['t'], w['texto']) for w in b['palabras']]
        if nb + 1 < len(bl) and bl[nb + 1]['ini'] - b['fin'] < 0.35:
            zona += [(bl[nb + 1]['ini'] + w['t'], w['texto']) for w in bl[nb + 1]['palabras']]
        items, actual, comas = [], [], 0
        for t, txt in zona:
            pl = _p(txt)
            if pl in Y and actual:
                items.append(actual)
                actual = []
                continue
            actual.append((t, txt))
            if txt.rstrip().endswith(','):
                comas += 1
                items.append(actual)
                actual = []
        if actual:
            items.append(actual)
        cortos = []                                                      # el tramo de cosas cortas seguidas (1-2 palabras de contenido)
        for it in items:
            cont = [(t, x) for t, x in it if _p(x) not in DIR.CONECTORAS]
            if 1 <= len(it) <= 3 and 1 <= len(cont) <= 2 and all(len(_p(x)) >= 3 for _t, x in cont):
                cortos.append((cont[0][0], ' '.join(_limpio(x) for _t, x in cont).capitalize()))
            elif len(cortos) >= 3:
                break
            else:
                cortos = []
        if len(cortos) < 3 or comas < 1 or len({c[1].lower() for c in cortos}) < len(cortos):
            try:
                import edicion_pro_tema5 as T5
                debiles = T5.DEBILES
            except Exception:
                debiles = set()
            cortos = _lista_sin_comas([(b['ini'] + w['t'], w['texto']) for w in b['palabras']], debiles)    # sin puntuación (lo normal)
            if not cortos:
                continue
        cortos = cortos[:4]
        a = cortos[0][0] - 0.35
        z = max(cortos[-1][0] + 1.5, a + 2.4)
        tarjeta('lista', a, min(z, a + 5.0), {'items': [c[1] for c in cortos], 'tiempos': [round(c[0] - a, 3) for c in cortos]},
                ', '.join(c[1] for c in cortos), 0.08 + 0.055 * len(cortos))
    # 4) la órbita: el concepto (icono 3D o emoji) gira alrededor de la cabeza; la primera en el gancho
    usados, n_orb, ult_orb = set(), 0, -99.0
    for nb, b in enumerate(bl):
        if n_orb >= (1 if dur < 45 else 2) or b['ini'] - ult_orb < 20.0:
            continue
        iconos = []
        for w in sorted(b['palabras'], key=lambda w: not w.get('clave')):
            pl = _p(w['texto'])
            if len(pl) < 4 or pl in DIR.CONECTORAS:
                continue
            ic = None
            try:
                import edicion_pro_planificador as PL
                ic = PL.CONCEPTOS3D.get(PL.plegar(w['texto'])) or PL.ICONO_A_3D.get(PL.CONCEPTOS.get(PL.plegar(w['texto']), ''))
            except Exception:
                ic = None
            if ic and ic in iconos_3d and ic not in usados:
                iconos.append('3d:' + ic)
                usados.add(ic)
            else:
                eid, _png = AC._sticker(w['texto'], lang, usados)
                if eid:
                    iconos.append('emoji:' + eid)
                    usados.add(eid)
            if len(iconos) >= 2:
                break
        if not iconos:
            continue
        a = b['ini'] + 0.05
        z = fin_frase(nb, 2.6, 3.6)
        if z - a < 2.2 or not ok(a, z) or not hay_persona((a + z) / 2):
            continue
        valores = {'iconos': iconos, 'acento': acento, 'vuelta': 2.8 if len(iconos) == 1 else 3.2, 'inclinacion': -6}
        for lado, capa in (('atras', 'detras'), ('delante', 'delante')):
            out.append({'pieza': 'orbita', 'mm': 'orbita', 'remotion': 'OrbitaT5', 'capa': capa, 'persona': capa == 'detras', 'ajustar': True,
                        'ini': round(a, 3), 'fin': round(z, 3), 'motivo': f"órbita ({lado}): {', '.join(iconos)}", 'valores': dict(valores, lado=lado)})
        n_orb, ult_orb = n_orb + 1, a
    # 5) el foco: el fondo en blanco y negro y la persona a color
    frases = [f.split() for f in FOCO.get(lang, []) + (FOCO['en'] if lang != 'en' else [])]
    n_foco, ult_foco = 0, -99.0
    for i, (t, p, txt, nb, j) in enumerate(todas):
        if n_foco >= max(1, round((1 if dur < 40 else 2) * k)) or t < 1.5 or t - ult_foco < 15.0:
            continue
        if not any(tuple(x[1] for x in todas[i:i + len(f)]) == tuple(f) for f in frases):
            continue
        a = bl[nb]['ini']
        z = fin_frase(nb, 1.4, 3.2)
        if z - a < 1.2 or not ok(a, z, 0.3) or not hay_persona((a + z) / 2):
            continue
        out.append({'pieza': 'foco', 'mm': 'foco', 'capa': 'velo', 'persona': True, 'ini': round(a, 3), 'fin': round(z, 3),
                    'motivo': f'foco: «{" ".join(_limpio(x[2]) for x in todas[i:i + 3])}»', 'valores': {}})
        n_foco, ult_foco = n_foco + 1, t
    if n_foco == 0 and dur >= 12.0:                                      # ninguna frase de foco: una vez, en la palabra más fuerte del cuerpo
        for i, (t, p, txt, nb, j) in enumerate(todas):
            if not (dur * 0.25 <= t <= dur * 0.8) or p not in FUERTES or not bl[nb]['palabras'][j].get('clave'):
                continue
            a = bl[nb]['ini']
            z = fin_frase(nb, 1.4, 3.0)
            if z - a >= 1.2 and ok(a, z) and hay_persona((a + z) / 2):
                out.append({'pieza': 'foco', 'mm': 'foco', 'capa': 'velo', 'persona': True, 'ini': round(a, 3), 'fin': round(z, 3),
                            'motivo': f'foco: «{_limpio(txt)}»', 'valores': {}})
                break
    return out


def _lista_sin_comas(ps, debiles):
    """[(t, texto)] de una frase que ES una lista sin puntuación («ubicación precio e inspección», «la ubicación el precio y la inspección»):
    dos o más cosas de UNA palabra (con su artículo, si lo lleva) antes de la única «y / e / and / o», y una después. Si no, None."""
    pl = [_p(x) for _t, x in ps]
    conj = [k for k, x in enumerate(pl) if x in Y]
    if len(conj) != 1:
        return None
    c = conj[0]

    def cosas(seq):
        out, k = [], 0
        while k < len(seq):
            (t, x), q = seq[k]
            if q in ARTICULOS and k + 1 < len(seq):
                (_t2, x2), q2 = seq[k + 1]
                out.append((t, x2, q2))
                k += 2
            else:
                out.append((t, x, q))
                k += 1
        return out
    antes, despues = cosas(list(zip(ps[:c], pl[:c]))), cosas(list(zip(ps[c + 1:], pl[c + 1:])))
    if len(antes) < 2 or len(despues) != 1:
        return None
    todas = antes + despues
    if len(todas) > 5 or any(len(q) < 4 or q in DIR.CONECTORAS or q in debiles or q in ARTICULOS for _t, _x, q in todas):
        return None
    if len({q for _t, _x, q in todas}) < len(todas):
        return None
    return [(t, _limpio(x).capitalize()) for t, x, _q in todas]


def protagonista(det):
    """¿Hay alguien que protagonice el plano? La persona más grande ocupa algo (≥ 8 %), su cabeza se ve (≥ 4,5 % del alto) y manda (al menos el
    doble que la segunda): la órbita, el foco y el sticker son de quien habla, no de un invitado al fondo de un plano abierto."""
    ps = sorted((det or {}).get('personas') or [], key=lambda q: -float(q.get('area') or 0))
    if not ps:
        return False
    q = ps[0]
    cab = float((q.get('cabeza') or {}).get('alto') or 0)
    return float(q.get('area') or 0) >= 0.08 and cab >= 0.045 and (len(ps) == 1 or float(q['area']) >= 2.0 * float(ps[1].get('area') or 0))


def transiciones(cortes, ocupado, dur, cada=6.0):
    """Los cortes (s) que llevan la transición con zoom: lejos del principio y del final, de lo que tapa la pantalla o recorta a la persona, y
    uno cada `cada` segundos como mucho."""
    out = []
    for t in sorted(set(round(float(c), 3) for c in cortes or [])):
        if t < 1.0 or t > dur - 0.6 or any(a - 0.4 < t < b + 0.4 for a, b in ocupado or []):
            continue
        if out and t - out[-1] < cada:
            continue
        out.append(t)
    return out


# ------------------------------------------------------------------------------------------------------------- imágenes (IA local)
def mapeo(clip, W, H):
    """(fx, fy): una fracción de la FUENTE → la fracción del TIMELINE para ese clip de V1 (ajustado al cuadro, con su zoom, Pan y Tilt)."""
    try:
        w, h = (int(x) for x in str((clip or {}).get('res') or '').lower().replace(' ', '').split('x')[:2])
    except (TypeError, ValueError):
        w, h = W, H
    if w <= 0 or h <= 0:
        w, h = W, H
    s = min(W / float(w), H / float(h))
    sx, sy = w * s / W, h * s / H
    zx, zy = float((clip or {}).get('zx') or 1.0), float((clip or {}).get('zy') or 1.0)
    pan, tilt = float((clip or {}).get('pan') or 0.0), float((clip or {}).get('tilt') or 0.0)
    return (lambda x: 0.5 + (0.5 - sx / 2 + x * sx - 0.5) * zx + pan / W), (lambda y: 0.5 + (0.5 - sy / 2 + y * sy - 0.5) * zy - tilt / H)


def _pegar(lienzo, img, fx, fy):
    """Pega `img` (la fuente entera) en el lienzo del timeline donde la deja el mapeo."""
    from PIL import Image
    Wl, Hl = lienzo.size
    x0, y0, x1, y1 = fx(0.0) * Wl, fy(0.0) * Hl, fx(1.0) * Wl, fy(1.0) * Hl
    ancho, alto = max(1, int(round(x1 - x0))), max(1, int(round(y1 - y0)))
    pieza = img.resize((ancho, alto), Image.BICUBIC)
    lienzo.paste(pieza, (int(round(x0)), int(round(y0))))
    return lienzo


def _url(img, fmt='JPEG', calidad=84):
    b = io.BytesIO()
    if fmt == 'JPEG':
        img.convert('RGB').save(b, 'JPEG', quality=calidad)
    else:
        img.save(b, 'PNG', optimize=True)
    return f'data:image/{fmt.lower()};base64,' + base64.b64encode(b.getvalue()).decode('ascii')


def imagen_timeline(rgb, fx, fy, W, H, escala=0.5):
    from PIL import Image
    lienzo = Image.new('RGB', (max(2, int(W * escala)), max(2, int(H * escala))), (0, 0, 0))
    return _pegar(lienzo, Image.fromarray(rgb), fx, fy)


def alfa_completo(rgb, alfa_modelo):
    """El alfa de MODNet (a ALTO_MODELO px) al tamaño del fotograma, con los bordes refinados y sin agujeros."""
    import edicion_pro_persona as PE
    h, w = rgb.shape[:2]
    import numpy as np
    b = PE.rellenar_huecos(alfa_modelo > 0.5)
    a = np.maximum(alfa_modelo, b.astype(np.float32) * 0.98)
    return PE.refinar_alfa(a, w, h)


def sticker(rgb, alfa, fx, fy, W, H, lado_max=900):
    """El recorte de la persona (RGBA, recortado a su caja) y dónde queda en el timeline [x0, y0, x1, y1] (fracciones)."""
    import numpy as np
    from PIL import Image
    ys, xs = np.where(alfa > 128)
    if len(xs) < 50:
        return None, None
    h, w = alfa.shape
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    img = Image.fromarray(np.dstack([rgb, alfa]).astype(np.uint8), 'RGBA').crop((x0, y0, x1, y1))
    if max(img.size) > lado_max:
        img.thumbnail((lado_max, lado_max), Image.LANCZOS)
    caja = [round(fx(x0 / w), 4), round(fy(y0 / h), 4), round(fx(x1 / w), 4), round(fy(y1 / h), 4)]
    return _url(img, 'PNG'), caja


def cara(rgb, det, lado=360):
    """La cara de la persona más grande (det en fracciones de la FUENTE), en un cuadrado con aire, como JPEG data URL."""
    from PIL import Image
    ps = (det or {}).get('personas') or []
    if not ps:
        return None
    q = max(ps, key=lambda p: p['area'])
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = q['bbox']
    cab = (q.get('cabeza') or {}).get('alto') or 0.2 * (y1 - y0)
    cx = (q['puntos'][0][0] if q.get('puntos') else (x0 + x1) / 2.0) * w
    cy = (y0 + cab * 0.55) * h
    r = max(24.0, cab * h * 0.95)
    caja = (int(max(0, cx - r)), int(max(0, cy - r)), int(min(w, cx + r)), int(min(h, cy + r)))
    img = Image.fromarray(rgb).crop(caja).resize((lado, lado), Image.LANCZOS)
    return _url(img)


def imagenes_sticker(rgb, alfa_modelo, clip, W, H):
    """Las props del StickerT5 para ese fotograma de la fuente: {'fondo', 'recorte', 'caja'} o None."""
    fx, fy = mapeo(clip, W, H)
    png, caja = sticker(rgb, alfa_completo(rgb, alfa_modelo), fx, fy, W, H)
    if not png:
        return None
    return {'fondo': _url(imagen_timeline(rgb, fx, fy, W, H, 0.5)), 'recorte': png, 'caja': caja}


def imagenes_final(rgb, det, clip, W, H):
    """Las props del FinalT5 para ese fotograma de la fuente (det en fracciones de la fuente): {'fondo', 'cara'} o None."""
    c = cara(rgb, det) if protagonista(det) else None                  # la cara de quien habla, no la de alguien del fondo
    if not c:
        return None
    fx, fy = mapeo(clip, W, H)
    return {'fondo': _url(imagen_timeline(rgb, fx, fy, W, H, 0.5)), 'cara': c}


def silueta(alfa, fx, fy, W, H, escala=0.25):
    """La silueta de la persona en el TIMELINE (a `escala` del tamaño), 0..1."""
    import numpy as np
    from PIL import Image
    lienzo = Image.new('L', (max(2, int(W * escala)), max(2, int(H * escala))), 0)
    a = Image.fromarray(alfa if alfa.dtype == np.uint8 else (np.clip(alfa, 0, 1) * 255).astype(np.uint8), 'L')
    Wl, Hl = lienzo.size
    x0, y0, x1, y1 = fx(0.0) * Wl, fy(0.0) * Hl, fx(1.0) * Wl, fy(1.0) * Hl
    lienzo.paste(a.resize((max(1, int(round(x1 - x0))), max(1, int(round(y1 - y0)))), Image.BILINEAR), (int(round(x0)), int(round(y0))))
    return np.asarray(lienzo).astype(np.float32) / 255.0


def sombra_en_clip(entrada, salida, sil, desp=(0.03, 0.016), suave=0.012, fuerza=0.55):
    """La clave de Remotion (ProRes 4444 con alfa) con la sombra de la persona ENCIMA: solo oscurece las letras (donde el clip tiene alfa), con la
    silueta corrida abajo a la derecha y desenfocada. Devuelve True si quedó escrito `salida`."""
    import av
    import numpy as np
    from PIL import Image, ImageFilter
    from pathlib import Path
    salida = Path(salida)
    tmp = salida.with_suffix('.tmp.mov')
    try:
        with av.open(str(entrada)) as c:
            vs = c.streams.video[0]
            W, H = vs.codec_context.width, vs.codec_context.height
            fps = vs.average_rate or 30
            s = Image.fromarray((np.clip(sil, 0, 1) * 255).astype(np.uint8), 'L').resize((W, H), Image.BILINEAR)
            corrida = Image.new('L', (W, H), 0)
            corrida.paste(s, (int(desp[0] * W), int(desp[1] * H)))
            corrida = corrida.filter(ImageFilter.GaussianBlur(max(1.0, suave * W)))
            k = 1.0 - fuerza * (np.asarray(corrida).astype(np.float32) / 255.0)
            with av.open(str(tmp), 'w') as o:
                os_ = o.add_stream('prores_ks', rate=fps)
                os_.width, os_.height, os_.pix_fmt = W, H, 'yuva444p10le'
                os_.options = {'profile': '4', 'vendor': 'apl0', 'qscale': '9'}
                n = 0
                for fr in c.decode(vs):
                    x = fr.to_ndarray(format='rgba')
                    rgb = (x[..., :3].astype(np.float32) * k[..., None]).astype(np.uint8)
                    nuevo = av.VideoFrame.from_ndarray(np.dstack([rgb, x[..., 3]]), format='rgba')
                    for pk in os_.encode(nuevo):
                        o.mux(pk)
                    n += 1
                for pk in os_.encode():
                    o.mux(pk)
        if n == 0:
            tmp.unlink(missing_ok=True)
            return False
        tmp.replace(salida)
        return True
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return False
