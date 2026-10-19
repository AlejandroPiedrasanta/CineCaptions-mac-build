# CineCaptions · By Cinema Productions
# 1_codigo/kit_neon_completo.py — v5.5.17: «Motions completo» del Tema 1 (el usuario: «si se activa Motions completo, utilizar los ejemplos del
# Tema 1 para mejorar aún más»): un video OPACO del largo del video, con el fondo morado del kit, los captions neón ARRIBA (Motions completo va
# encima de todo y tapa los de abajo) y, debajo, una pieza del kit «TEMA 1» por idea, elegida por lo que se dice. Mismas cortinillas y cierre.
"""
    crear(palabras, dur, W, H, fps, carpeta, idioma='es', video='', decir=None) -> ruta del .mp4 (H.264 opaco) o None
    planificar(palabras, dur, idioma='es', video='') -> {'escena': [...llamadas al motor del kit...], 'tramos': [...], 'piezas': [...]}
    sonidos(plan, fps, voz_db=None) -> eventos de sonido como los de la PRO (con 'sinc': van con lo que pasa DENTRO del video)

Por tramo (los de motions_completo._segmentos: frases juntas hasta que acaba la idea), en este orden y sin repetir la misma pieza seguida ni
pasar de ~30 % de los tramos: lo que se pide hacer → checks · lugar con fecha u hora → tarjeta de ruta · 3 cosas → interruptores · 2 o 4 cosas →
fila con píldoras · varios nombres → etiquetas con avatar · «3 personas…» → avatares en arco · el evento (al principio) → notificación ·
conceptos con icono → órbita (una vez) o un chip con su icono. Cortinillas cada ~10 s y el cierre del kit (panel + cartel).
"""
import hashlib
import json
import random
import re
from pathlib import Path

TOP_CAPTIONS = 430                  # los captions neón, arriba (las piezas del kit van de 1000 hacia abajo)
TOPE = 0.3                          # ninguna pieza en más del 30 % de los tramos
# sobre el fondo vacío las piezas del kit (pensadas para ir ENCIMA del video) se agrandan desde su sitio: (escala, cx, cy)
ESCALA = {'chipSuelto': (2.1, 540, 1260), 'avataresArco': (1.7, 548, 1300), 'etiquetas': (1.3, 60, 1200), 'interruptores': (1.25, 40, 1180),
          'checks': (1.25, 80, 1170), 'filaEtiqueta': (1.2, 70, 1200)}


def _bloques(palabras, idioma, dur):
    import edicion_pro_planificador as PL
    import kit_neon as KN
    w = PL.unir_partidas([p for p in (palabras or []) if PL._txt(p) and p.get('start') is not None])
    caps = KN.escena_captions(palabras, idioma, fin_video=dur)
    out = []
    for e in caps:
        a, b = float(e['t0']), float(e['a'].get('tout', e['t0']))
        ps = [{'texto': PL._txt(x), 't': float(x['start'])} for x in w if a - 0.05 <= float(x['start']) < max(b, a + 0.1)]
        if ps:
            out.append({'ini': a, 'fin': max(b, a + 0.3), 'palabras': ps, 'cap': e})
    return w, out


def planificar(palabras, dur, idioma='es', video=''):
    import edicion_pro_planificador as PL
    import kit_neon as KN
    import kit_neon_motions as KM
    import motions_completo as MCO
    lang = PL.idioma_de(idioma)
    T = KM.TEXTOS.get(lang, KM.TEXTOS['es'])
    w, bloques = _bloques(palabras, idioma, dur)
    if not w or not bloques:
        return None
    dur = float(dur or (float(w[-1]['end']) + 1.0))
    fr = PL.frases_de(w)
    cands = PL.candidatos(w, fr, None, idioma)
    planos = [KM._plano(PL._txt(x)) for x in w]
    verbos = {KM._plano(v) for v in KM.CTA.get(lang, ()) + KM.CTA['es']}

    def st(i):
        return round(float(w[i]['start']), 3)

    segs = MCO._segmentos([{k: v for k, v in b.items() if k != 'cap'} for b in bloques], dur)
    emblema = (KM._emblema(video, dur) if video else None)
    marca = next((c for c in cands if c['tipo'] == 'nombre' and len(c['texto'].split()) >= 2 and st(c['i']) < dur * 0.4), None)
    img_marca = emblema or KM.insignia((marca or {}).get('texto') or 'CC')
    ics = []
    for c in sorted([c for c in cands if c['tipo'] == 'concepto' and c.get('icono')], key=lambda c: c['i']):
        ic = KM.ICONO_KIT.get(c['icono'], 'star')
        if ic not in ics:
            ics.append(ic)
    escena, piezas, tramos = [], [], []
    cuenta, ultima = {}, None
    tope = max(2, int(len(segs) * TOPE))
    hecho = {'orbita': False, 'notificacion': False}
    meses, dias = {KM._plano(m) for m in KM.MESES}, {KM._plano(d) for d in KM.DIAS}
    for k, s in enumerate(segs):
        a, b = float(s['ini']), float(s['fin'])
        tin, tout = round(a + 0.08, 3), round(max(a + 0.9, b - 0.28), 3)
        idx = [i for i in range(len(w)) if a <= st(i) < b]
        cs = [c for c in cands if a <= st(c['i']) < b]
        opciones = []
        # lo que se pide hacer → checks
        accion = [i for i in idx if planos[i] in verbos]
        if accion:
            items = []
            for i in accion[:3]:
                j, trozo = i, []
                while j < len(w) and len(trozo) < 5 and (j == i or planos[j] not in verbos):
                    trozo.append(KM._limpio(PL._txt(w[j])))
                    if re.search(r'[,.;!?]$', PL._txt(w[j])):
                        break
                    j += 1
                txt = KM._cap(' '.join(x for x in trozo if x))
                if len(txt) >= 4:
                    items.append([txt[:30], st(i)])
            if items:
                opciones.append(('checks', {'items': items, 'tout': tout, 'y': 1170}))
        # lugar con fecha u hora → tarjeta de ruta
        for c in [c for c in cs if c['tipo'] in ('lugar', 'nombre') and c.get('presencia')] + [c for c in cs if c['tipo'] == 'lugar']:
            fecha, hora = KM._fecha_hora(w, planos, meses, dias, st(c['i']), st, ventana=6.0)
            if fecha or hora:
                hitos = [[c['texto'], st(c['i'])]] + ([[hora[0], hora[1]]] if hora else []) + ([[fecha[0], fecha[1]]] if fecha else [])
                opciones.append(('tarjetaRuta', {'tin': tin, 'tout': tout, 'titulo': c['texto'], 'direccion': '', 'y': 1060,
                                                 'hitos': [[h[0], round(max(tin, h[1]), 3)] for h in hitos], 'calles': [],
                                                 'apunte': [T['apunte'], round(tin + 0.06, 3)]}))
                break
        # listas: 3 cosas → interruptores; 2 o 4 → fila de píldoras
        for c in [c for c in cs if c['tipo'] == 'lista']:
            its = [it for it in c.get('items') or [] if it.get('texto')]
            if not its or any(KM._plano(it['texto'].split()[0]) in verbos for it in its):
                continue
            def clave_de(it):                       # (como el kit: el concepto con icono de la cosa; si no, su primera palabra con contenido)
                n = max(1, len(it['texto'].split()))
                con = next((x for x in cands if x['tipo'] == 'concepto' and it['i'] <= x['i'] < it['i'] + n), None)
                if con:
                    return KM._limpio(PL._txt(w[con['i']]))
                return next((x for x in it['texto'].split() if KM._plano(x) not in PL.STOP and len(KM._plano(x)) > 2), it['texto'].split()[0])
            filas = [[KM._cap(clave_de(it))[:18], ic, round(max(tin, st(it['i'])), 3)]
                     for it, ic in zip(its, ('trophy', 'chat', 'users', 'star'))]
            if len(its) == 3:
                opciones.append(('interruptores', {'tin': tin, 'tout': tout, 'tDerecha': round(min(tout - 0.5, filas[-1][2] + 0.9), 3),
                                                   'etiqueta': T['incluido'], 'filas': filas, 'avatares': [], 'y': 1180}))
            else:
                opciones.append(('filaEtiqueta', {'titulo': KM._cap(its[0]['texto']).upper()[:12], 't': tin, 'tout': tout, 'y': 1200,
                                                  'pills': [[KM._cap(' '.join(it['texto'].split()[:3]))[:22], 'star', f[2]] for it, f in zip(its, filas)]}))
            break
        # varios nombres → etiquetas con avatar
        nombres = [c for c in cs if c['tipo'] == 'nombre' and len(c['texto'].split()) >= 2 and c is not marca]
        if len(nombres) >= 2 or (len(nombres) == 1 and not opciones):
            items = []
            for c in nombres[:3]:
                foto = KM.cara(video, st(c['i']) + 0.3) if video else None
                items.append([foto or KM.insignia(c['texto']), c['texto'][:24], '', round(max(tin, st(c['i'])), 3)])
            opciones.append(('etiquetas', {'items': items, 'tout': tout, 'y': 1200}))
        # «3 jóvenes influencers» → avatares en arco
        for c in [c for c in cs if c['tipo'] == 'cifra']:
            try:
                n = int(str(c.get('numero') or '').strip())
            except ValueError:
                continue
            if 2 <= n <= 5 and video and any(planos[j] in KM.PERSONAS for j in range(c['i'], min(len(w), c['i'] + 4))):
                fotos = [f for f in (KM.cara(video, st(c['i']) + 0.6 + 1.3 * q) for q in range(n)) if f]
                if len(fotos) >= 2:
                    opciones.append(('avataresArco', {'imgs': fotos[:n], 't0': round(tin + 0.2, 3), 'tout': tout, 'y': 1300}))
            break
        # el evento, al principio → notificación
        if marca and not hecho['notificacion'] and a <= st(marca['i']) < b + 0.5:
            otros = [c['texto'] for c in cands if c['tipo'] in ('nombre', 'lugar') and c is not marca and 0 < st(c['i']) - st(marca['i']) <= 6]
            opciones.append(('notificacion', {'img': img_marca, 'titulo': marca['texto'], 'texto': ' · '.join(otros[:2]), 'tin': tin, 'tout': tout, 'y': 1180}))
        # conceptos con icono → la órbita (una vez, con 3 o más temas en todo el video) o un chip con su icono
        con_icono = [c for c in cs if c['tipo'] == 'concepto' and c.get('icono')]
        if con_icono and len(ics) >= 3 and not hecho['orbita'] and b - a >= 2.4:
            lista = (ics + [x for x in KM.RELLENO_ORBITA if x not in ics])[:6]
            anillos = [[ic, 250, -90 + 120 * (j // 2), 8] if j % 2 == 0 else [ic, 400, -30 + 120 * (j // 2), -5] for j, ic in enumerate(lista)]
            opciones.append(('orbita', {'tin': tin, 'tout': tout, 'img': img_marca, 'iconos': anillos, 'cy': 1330, 'desdeY': 1100}))
        for c in con_icono:
            opciones.append(('chipSuelto', {'texto': KM._cap(c['texto'])[:18], 'icono': KM.ICONO_KIT.get(c['icono'], 'star'), 't': round(max(tin, st(c['i'])), 3),
                                            'tout': tout, 'y': 1260, 'grande': True}))
            break
        elegida = next((o for o in opciones if o[0] != ultima and cuenta.get(o[0], 0) < tope), None)
        if elegida is not None:
            fn, args = elegida
            llamada = {'fn': fn, 'a': args}
            if fn in ESCALA:
                llamada.update(escala=ESCALA[fn][0], cx=ESCALA[fn][1], cy=ESCALA[fn][2])
            escena.append(llamada)
            piezas.append({'pieza': 'neon_motion', 'fn': fn, 'ini': a, 'fin': b, 'valores': {'escena': [llamada]}})
            cuenta[fn] = cuenta.get(fn, 0) + 1
            ultima = fn
            if fn in hecho:
                hecho[fn] = True
        tramos.append({'ini': a, 'fin': b, 'tipo': elegida[0] if elegida else 'captions'})
    # los captions neón, cada uno en su tiempo: ARRIBA si hay una pieza a la vez; si no, centrados (la idea va sola, grande en el centro)
    caps = [b['cap'] for b in bloques]
    tc = round(min(dur - 0.15, st(len(w) - 1) + 0.55), 3)
    con_cierre = dur - tc >= 0.15
    con_pieza = [(p['ini'], p['fin']) for p in piezas if p['fn'] != 'barrido']
    for k, e in enumerate(caps):
        if con_cierre and k == len(caps) - 1:
            continue                                   # (la última frase va con el cierre, más abajo)
        a0, b0 = float(e['t0']), float(e['a'].get('tout', e['t0']))
        alto = sum(KN._alto(it) for it in e['a'].get('items') or [])
        top = TOP_CAPTIONS if any(a0 < y and x < b0 for x, y in con_pieza) else int(max(300, 960 - alto / 2))
        escena.append({'fn': 'hook', 'a': dict(e['a'], top=top)})
    # cortinillas cada ~10 s en un cambio de tramo, y el cierre del kit (panel + cartel) cuando ya se dijo la última palabra
    ult = -99.0
    for s in segs[1:]:
        tc = float(s['ini'])
        if tc - ult >= 10.0 and 5.0 < tc < dur - 6.0:
            llamada = {'fn': 'barrido', 'args': [round(tc, 3)]}
            escena.append(llamada)
            piezas.append({'pieza': 'neon_motion', 'fn': 'barrido', 'ini': tc - 0.5, 'fin': tc + 0.45, 'valores': {'escena': [llamada]}})
            ult = tc
    if con_cierre:
        llamada = {'fn': 'barrido', 'args': [tc, True]}
        escena.append(llamada)
        logo = KM._cartel(video, dur, 380, 480) if video else None
        if logo:
            escena.append({'fn': 'logoCierre', 'a': {'img': logo, 't': round(tc + 0.1, 3)}})
        piezas.append({'pieza': 'neon_motion', 'fn': 'barrido', 'ini': tc - 0.1, 'fin': dur, 'valores': {'escena': [llamada]}})
        if caps:                                       # (la última frase, sobre el panel: grande y en lima, como el kit)
            ultima_cap = caps[-1]['a']
            items = [dict(it, size=KN._encaja(it['txt'], 'big', 300), fill='acento') if it['k'] == 'big' else it for it in ultima_cap['items']]
            escena.append({'fn': 'hook', 'a': dict(ultima_cap, items=items, top=1060, tout=round(dur + 5.0, 3))})
    return {'escena': escena, 'tramos': tramos, 'piezas': piezas, 'duracion': round(dur, 3), 'resumen': cuenta}


def sonidos(plan, fps, voz_db=None):
    """Los sonidos de las piezas del kit (los de su proyecto: whoosh en la cortinilla y la órbita, clic en los interruptores, pop en los checks…)."""
    try:
        import edicion_pro_sonido as PS
        evs = PS.disenar({'piezas': list((plan or {}).get('piezas') or [])}, fps, random.Random(11), voz_db=voz_db)
        for e in evs:
            e['sinc'] = True
        return evs
    except Exception:
        return []


def crear(palabras, dur, W, H, fps, carpeta, idioma='es', video='', decir=None):
    """Planifica y renderiza el Motions completo del Tema 1 (H.264 opaco, del largo del video). Devuelve su ruta o None (con caché)."""
    decir = decir or (lambda t: None)
    try:
        import edicion_pro_remotion as RM
        import motions_completo as MCO
    except Exception:
        return None
    if not RM.disponible():
        decir('Motions completo: falta el motor de animaciones (Remotion)')
        return None
    decir('Motions completo (Tema 1): eligiendo una pieza del kit para cada idea…')
    plan = planificar(palabras, dur, idioma, video)
    if not plan or not plan['escena']:
        return None
    props = {'escena': plan['escena'], 'imagenes': {}, 't0': 0.0, 'tema': 'neon', 'subs': 5, 'fondo': 'neon',
             '_ancho': int(W), '_alto': int(H), '_fps': float(fps), '_dur': round(float(plan['duracion']), 3)}
    huella = hashlib.sha1(json.dumps(props, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:14]
    salida = Path(carpeta) / f'motions_completo_neon_{huella}.mp4'
    try:
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.with_suffix('.json').write_text(json.dumps({'tema': 'neon', 'piezas': plan['piezas'], 'tramos': plan['tramos']}, ensure_ascii=False),
                                               encoding='utf-8')
    except OSError:
        pass
    if salida.exists() and salida.stat().st_size > 50_000:
        return salida
    resumen = ', '.join(f'{n} {f}' for f, n in sorted(plan['resumen'].items(), key=lambda x: -x[1])) or 'solo captions'
    decir(f"Motions completo (Tema 1): {len(plan['tramos'])} ideas ({resumen}); animando…")
    ok = MCO._renderizar(RM, props, salida, plan['duracion'], decir, comp='KitNeon')
    try:
        import registro
        if ok:
            registro.info(f"Motions completo (Tema 1): {len(plan['tramos'])} ideas en {salida.name}: {resumen}.", 'motions')
        else:
            registro.aviso('Motions completo (Tema 1): Remotion no pudo hacer el video; el resto de la edición queda igual.', 'motions')
    except Exception:
        pass
    return salida if ok else None


def plan_de(mp4):
    """El plan guardado junto al video (para sus sonidos)."""
    try:
        return json.loads(Path(mp4).with_suffix('.json').read_text(encoding='utf-8'))
    except Exception:
        return None
