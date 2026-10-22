# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido.py — «AI Sound Director» (v5.34): el sound designer de GO. Analiza el video y dirige el sonido ENCIMA de los motores de siempre.
"""
Con el interruptor `ai_sound_director` (preferencia; apagado por defecto) GO, además de lo de siempre:

    contexto(...)        en el hilo de GO, justo tras planificar Efectos y la Edición PRO: una FOTO (datos simples) de lo que el director necesita leer
    preparar(ctx)        en un hilo propio: análisis (tema, voz, ruido, música, ambiente, captions, motions, narrativa), los SONIDOS (fase 3: qué suena
                         y qué se queda en silencio, cada uno hecho a la medida en su WAV) y la voz restaurada (una COPIA)
    al_colocar(plan, …)  lo último antes de Resolve: el director es el ÚNICO dueño del sonido — decide KEEP / REPLACE / REMOVE sobre los sonidos de
                         Efectos, apaga los de Simple (pistas «SFX…», reversible), toma la PRO (sonidos_pro) y añade los suyos en las pistas AI SFX … y
                         'voz_ai' (pista «AI VOICE»; A1 se apaga SOLO después de comprobar que la copia quedó puesta); apagado, un plan que solo
                         limpia sus pistas (A1 vuelve)
    sonidos_pro(plan, …) final de edicion_pro.aplicar: con el director al mando, los sonidos de los gráficos de la PRO se van (ya puso los suyos)

Reglas: APAGADO = GO exactamente como antes (al_colocar devuelve el MISMO plan). Solo se toca AUDIO: captions, motions, cortes, zoom, gráficos y
tiempos visuales no se leen para cambiarlos, solo para entenderlos. Nunca se sobrescribe un original (copias en ~/DaVinciSubtitles/sound_director/).
Cualquier excepción: «[AI SOUND] fallback: motor original» en el Registro y GO sigue con sus planes. Los motores de siempre (sfx_rules,
sonidos_extra, edicion_pro_sonido, rectificador, musica_go, ducking) quedan como motores internos del director.
"""
import copy
import os
import time

import director_sonido_estado as E

PREF = 'ai_sound_director'
ENV = 'CINECAPTIONS_AI_SOUND'                 # '1' / '0' fuerza el interruptor (arneses de prueba)
ORIGEN = 'AI Sound Director'


def activo(prefs=None):
    """¿Está encendido? (preferencia `ai_sound_director`; v5.37: sin preferencia, SÍ —el director es el dueño del sonido—; la variable
    CINECAPTIONS_AI_SOUND manda en las pruebas)."""
    forzado = os.environ.get(ENV)
    if forzado in ('0', '1'):
        return forzado == '1'
    if prefs is None:
        try:
            import ajustes_ui
            prefs = ajustes_ui.leer_prefs()
        except Exception:
            prefs = {}
    return (prefs or {}).get(PREF, True) is True


def log(texto, nivel='info'):
    """Una línea «[AI SOUND] …» en el Registro."""
    try:
        import registro
        registro.anotar(nivel, '[AI SOUND] ' + str(texto), ORIGEN)
    except Exception:
        pass


def fallback(donde):
    """Lo que falló va al Registro (con su traza) y GO sigue con el motor original."""
    try:
        import registro
        registro.excepcion(origen=f'{ORIGEN} · {donde}')
    except Exception:
        pass
    log(f'fallback: motor original ({donde})', 'aviso')


def contexto(video, palabras, pack, formato='v', recorte=None, timeline_de_go=False, cortes=None, bloques=None, plan_efectos=None,
             plan_pro=None, idioma=None):
    """La foto de lo que el director necesita, en datos simples (copias: el hilo del director nunca lee los planes vivos de GO)."""
    return {'video': str(video) if video else '', 'palabras': [dict(p) for p in (palabras or []) if isinstance(p, dict)],
            'pack': str(pack or ''), 'formato': formato or 'v', 'idioma': idioma,
            'recorte': copy.deepcopy(recorte) if recorte else None, 'timeline_de_go': bool(timeline_de_go),
            'cortes': [float(t) for t in (cortes or [])], 'bloques': copy.deepcopy(bloques) if bloques else [],
            'plan_efectos': copy.deepcopy(plan_efectos) if plan_efectos else None, 'plan_pro': _foto_pro(plan_pro)}


def _foto_pro(plan_pro):
    """Del plan de la Edición PRO solo lo que dice QUÉ se mueve y CUÁNDO (piezas con su metadata), sin rutas ni objetos."""
    if not isinstance(plan_pro, dict):
        return None
    try:
        piezas = [{k: copy.deepcopy(v) for k, v in p.items() if not str(k).startswith('_')} for p in (plan_pro.get('piezas') or []) if isinstance(p, dict)]
    except Exception:
        piezas = []
    direccion = plan_pro.get('direccion') if isinstance(plan_pro.get('direccion'), dict) else {}
    return {'piezas': piezas, 'tema5': bool(plan_pro.get('tema5')), 'estilo_t5': plan_pro.get('estilo_t5'), 'tema': plan_pro.get('tema'),
            'ligero': bool(plan_pro.get('ligero')), 'genero': plan_pro.get('genero'), 'duracion': plan_pro.get('duracion'),
            'perfil': copy.deepcopy(plan_pro.get('perfil')) if isinstance(plan_pro.get('perfil'), dict) else None,
            'acento': direccion.get('acento')}


def analizar(ctx, al_estado=None):
    """FASE 1 — solo ANÁLISIS (no cambia nada audible): tema e identidad sonora, voz, ruido, música, ambiente por escena, captions, motions y
    narrativa. Devuelve (analisis, interno); `interno` = medidas y extractos en memoria para la voz (fase 2)."""
    import director_sonido_ambiente as AM
    import director_sonido_eventos as EV
    import director_sonido_identidad as ID
    import director_sonido_musica as MU
    import director_sonido_voz as V
    video = ctx['video']
    recorte = ctx.get('recorte') or None
    segs = [tuple(x) for x in recorte['segmentos']] if recorte and recorte.get('segmentos') else None
    palabras = ctx.get('palabras') or []
    pro = ctx.get('plan_pro') or {}
    perfil_ia = pro.get('perfil') or None
    genero = pro.get('genero')
    if not genero and palabras:
        try:
            import edicion_pro_planificador as PL
            genero = PL.detectar_genero(palabras)[0]
        except Exception:
            genero = None
    try:
        import ajustes_ui
        prefs = ajustes_ui.leer_prefs()
    except Exception:
        prefs = {}
    if al_estado:
        al_estado('AI Sound Director: escuchando el video…')
    extractos = V.elegir_extractos(segs, video)
    diag, med, guardados = V.analizar(video, segs, palabras, extractos=extractos)
    dur = float(diag.get('duracion') or 0.0)
    m_fuente = MU.en_la_fuente(diag, med)
    m_go = MU.de_go(ctx.get('plan_efectos'))
    caps = EV.captions(ctx.get('bloques'), dur)
    mots = EV.motions(ctx.get('plan_efectos'), pro, dur)
    narr = EV.narrativa(palabras, dur, perfil_ia)
    amb = AM.analizar(med, diag, palabras, ctx.get('cortes'), genero, perfil_ia, m_fuente)
    rasgos = ID.rasgos_del_tema(ctx.get('pack'), ctx.get('formato') or 'v', prefs, pro, ctx.get('plan_efectos'))
    perfil = ID.perfil(rasgos, caps, mots, perfil_ia)
    paleta = ID.paleta(perfil, diag, m_fuente, amb, narr, mots)
    nec, nec_motivos = MU.necesidad(paleta['valores'], narr, mots, dur, diag)
    proveedores = MU.proveedores()
    m_estado = MU.sugerir(m_fuente, m_go, nec, nec_motivos, proveedores)
    analisis = {'tema': rasgos['tema'], 'pack': ctx.get('pack'), 'rasgos': rasgos, 'perfil': perfil, 'paleta': paleta, 'genero': genero, 'perfil_ia': perfil_ia,
                'voz': diag, 'musica': {'en_la_fuente': m_fuente, 'de_go': m_go, 'necesidad': nec, 'necesidad_motivos': nec_motivos, 'estado_sugerido': m_estado,
                                         'proveedores': proveedores},
                'ambiente': amb, 'captions': caps, 'motions': mots, 'narrativa': narr, 'timeline_de_go': bool(ctx.get('timeline_de_go')),
                'segmentos': len(segs) if segs else 0}
    _log_analisis(analisis)
    return analisis, {'diag': diag, 'medidas': med, 'extractos': [v for v in guardados.values() if v is not None], 'segmentos': segs,
                      'ventanas': [k for k, v in guardados.items() if v is not None]}


def _log_analisis(a):
    d, mu, amb = a['voz'], a['musica'], a['ambiente']
    log(f"Theme detected: {a['tema']} ({a['pack']} · estilo {a['rasgos']['estilo']}" + (f" · PRO {a['rasgos']['modo_pro']}" if a['rasgos'].get('modo_pro') else '') + ')')
    log(f"Sonic profile: {a['perfil']['resumen']}")
    lo = d.get('loudness') or {}
    log(f"Voice noise: {d.get('ruido')} (fondo {d.get('suelo_ruido_db')} dBFS en {d.get('fuente_suelo')}, SNR {d.get('snr_db')} dB, {lo.get('lufs')} LUFS, "
        f"TP {lo.get('tp_db')} dBTP)" + (' · ' + '; '.join(d['problemas'][:4]) if d.get('problemas') else ''))
    estado = mu['estado_sugerido']
    log(f"Music: {'presente en el video' if mu['en_la_fuente']['presente'] else ('la de GO' if mu['de_go'] else 'ninguna')} → {estado['estado']} "
        f"({estado['por_que']})")
    log(f"Ambience: {amb['resumen']}")
    c = a['captions']
    log(f"Captions detected: {c['n']} ({c['con_sonido']} con sonido de Simple, {c['silenciosos']} en silencio)")
    m = a['motions']
    log(f"Motions detected: {m['n']} ({', '.join(f'{k} {v}' for k, v in m['por_origen'].items()) or 'ninguno'}; {m['por_minuto']}/min)")
    n = a['narrativa']
    log(f"Narrative: {n['n']} frases · " + ', '.join(f'{k} {v}' for k, v in n['roles'].items()))


def preparar(ctx, al_estado=None, res=None):
    """El trabajo del director para ESTE GO (en su hilo): fase 1 (análisis), fase 3 (sonidos) y fase 2 (voz), en ese orden: los sonidos son
    rápidos y no se pierden si la voz de un video largo no acaba a tiempo. Rellena `res` según avanza (GO puede recoger lo que ya esté) y lo
    devuelve: {'estado', 'analisis', 'sfx', 'voz', 'evento_voz', 'segundos'}; nunca lanza (lo que falle: fallback y GO sigue con lo de siempre)."""
    t0 = time.time()
    res = res if res is not None else {}
    res.update({'estado': None, 'analisis': None, 'sfx': None, 'capas': None, 'voz': None, 'evento_voz': None, 'qc': None, 'segundos': 0.0})
    try:
        video = ctx.get('video')
        if not video or not os.path.isfile(str(video)):
            return res
        estado = E.cargar(video)
        analisis, interno = analizar(ctx, al_estado)
        res['analisis'] = analisis
        guardar_contexto(ctx)
        estado.update({'tema': analisis['tema'], 'perfil': analisis['perfil'], 'paleta': analisis['paleta'], 'analisis': analisis,
                       'ambience_analysis': analisis['ambiente'], 'music_decision_state': analisis['musica']['estado_sugerido']})
        try:
            import director_sonido_voz as V
            estado['voice_quality_before'] = V.resumen_calidad(analisis['voz'])
        except Exception:
            pass
        res['estado'] = E.guardar(video, estado)
    except Exception:
        fallback('análisis')
        res['segundos'] = round(time.time() - t0, 2)
        return res
    try:                                                              # FASE 3: los sonidos (si falla, GO sigue con los de siempre)
        if al_estado:
            al_estado('AI Sound Director: diseñando los sonidos…')
        sfx = preparar_sfx(ctx, analisis)
        res['sfx'] = sfx
        _guardar_sfx(estado, sfx)
        res['estado'] = E.guardar(video, estado)
    except Exception:
        res['sfx'] = None
        fallback('sonidos')
    try:                                                              # FASE 4: música y ambiente (si falla, sin capas nuevas y GO sigue)
        if al_estado:
            al_estado('AI Sound Director: música y ambiente…')
        capas = preparar_capas(ctx, analisis)
        res['capas'] = capas
        _guardar_capas(estado, capas)
        res['estado'] = E.guardar(video, estado)
    except Exception:
        res['capas'] = None
        fallback('música y ambiente')
    try:                                                              # FASE 2: la voz (si falla, la original se queda y GO sigue)
        voz, evento = preparar_voz(ctx, analisis, interno, estado, al_estado)
        estado.update({'voz': {k: voz.get(k) for k in ('archivo', 'clave', 'cadena', 'motivo', 'nivel', 'backend', 'fuerza', 'ganancia_db', 'objetivo_lufs',
                                                       'mezclada', 'segundos', 'canales', 'duracion')},
                       'voice_backend': {'nombre': voz.get('backend'), 'nivel': voz.get('nivel'), 'motivo': voz.get('motivo')},
                       'voice_quality_after': voz.get('despues'), 'metricas': dict(estado.get('metricas') or {}, guardas_voz=voz.get('guardas'))})
        sfx = res.get('sfx')
        real = float(analisis['voz'].get('nivel_voz_db') or -30.0) + (float(voz.get('ganancia_db') or 0.0) if evento else 0.0)
        if sfx and abs(real - float(sfx.get('nivel_voz_db') or real)) > 1.0:   # la voz quedó a otro nivel del previsto: los sonidos, a su nivel
            res['sfx'] = preparar_sfx(ctx, analisis, real, sfx.get('diseno'))
            _guardar_sfx(estado, res['sfx'])
            if res.get('capas'):
                res['capas'] = preparar_capas(ctx, analisis, real)
                _guardar_capas(estado, res['capas'])
        res['voz'], res['evento_voz'] = voz, evento
        res['estado'] = E.guardar(video, estado)
    except Exception:
        res['evento_voz'] = None
        fallback('voz')
    try:                                                              # FASE 5: mezcla, QC y Sound Score (si falla, todo sigue como estaba)
        if res.get('sfx') or res.get('capas'):
            sfx, capas, qc = mezclar(ctx, analisis, estado, res.get('sfx'), res.get('capas'), res.get('evento_voz'), al_estado)
            res['sfx'], res['capas'], res['qc'] = sfx, capas, qc
            if sfx:
                _guardar_sfx(estado, sfx)
            if capas:
                _guardar_capas(estado, capas)
            _guardar_qc(estado, qc)
            res['estado'] = E.guardar(video, estado)
    except Exception:
        res['qc'] = None
        fallback('mezcla')
    res['segundos'] = round(time.time() - t0, 2)
    return res


def _nivel_voz_previsto(ctx, analisis):
    """El nivel (dBFS, RMS de la voz activa) al que sonará la voz: el medido + la ganancia que le pondrá la fase 2 si la va a sustituir (la lleva
    a la ventana de director_sonido_voz.OBJETIVO_LUFS). Si luego queda distinta en más de 1 dB, los sonidos se rehacen a su nivel."""
    import numpy as np
    import director_sonido_voz as V
    d = analisis['voz']
    nivel = float(d.get('nivel_voz_db') or -30.0)
    lufs = (d.get('loudness') or {}).get('lufs')
    if ctx.get('timeline_de_go') and lufs is not None and not analisis['musica']['en_la_fuente'].get('presente'):
        if not (V.OBJETIVO_LUFS[0] - 1.0 <= lufs <= V.OBJETIVO_LUFS[1] + 1.0):
            nivel += float(np.clip(lufs, *V.OBJETIVO_LUFS)) - float(lufs)
    return round(nivel, 1)


PREF_CONTROLES = 'ai_sound_controles'          # los 5 controles + el estilo de la página (AUTO = sin clave)


def controles(prefs=None):
    """Lo que el usuario pidió en la página (estilo, intensidad, densidad, voz, música, ambiente); {} = todo en AUTO."""
    if prefs is None:
        try:
            import ajustes_ui
            prefs = ajustes_ui.leer_prefs()
        except Exception:
            prefs = {}
    c = (prefs or {}).get(PREF_CONTROLES)
    return {k: v for k, v in c.items() if v not in (None, 'auto')} if isinstance(c, dict) else {}


def guardar_contexto(ctx):
    """La FOTO de GO (palabras, bloques, planes, cortes) en la carpeta del video: la página rediseña sin volver a hacer GO."""
    try:
        import archivos_seguros
        archivos_seguros.escribir_json(E.carpeta_de(ctx['video']) / 'contexto.json', E.limpio(ctx))
    except Exception:
        pass


def cargar_contexto(video):
    import archivos_seguros
    d = archivos_seguros.leer_json(E.carpeta_de(video) / 'contexto.json', None)
    return d if isinstance(d, dict) else None


def mezclar(ctx, analisis, estado, sfx, capas, evento_voz, al_estado=None, previas=None):
    """FASE 5: la mezcla completa (lo que suma Resolve), QC en 3 pasadas y SOUND SCORE (director_sonido_mezcla). Si algo pisa a la voz o empuja el
    true peak, se baja SOLO eso (y el bus del director si hace falta), se rehace lo cambiado y se vuelve a medir. `previas` = las correcciones que
    ya llevan `sfx`/`capas` (los retoques de la página las conservan, como un fader; cada GO empieza de cero): las nuevas se SUMAN y quedan en
    estado['mezcla_ajustes']. Devuelve (sfx, capas, qc)."""
    import director_sonido_mezcla as MZ
    if al_estado:
        al_estado('AI Sound Director: mezcla y control de calidad…')
    video = ctx['video']
    voz = (evento_voz or {}).get('archivo')

    def eventos():
        anclas = {e['id']: e.get('ancla') for e in ((sfx or {}).get('diseno') or {}).get('eventos') or []}
        out = [dict(x, ancla=anclas.get((x.get('ai') or {}).get('id'))) for x in (sfx or {}).get('eventos') or []]
        return out + [dict(x) for k in ('musica', 'ambiente') for x in ((capas or {}).get(k) or {}).get('plan') or []]
    med = MZ.medir(video, ctx, eventos(), voz)
    corr, bus = MZ.correcciones(med)
    total = {'eventos': dict((previas or {}).get('eventos') or {}), 'bus': float((previas or {}).get('bus') or 0.0)}
    nivel = float((sfx or {}).get('nivel_voz_db') or 0.0)
    for _vuelta in range(2):                                          # primero, solo lo que pisa a la voz; se vuelve a medir (y una vez más si hace falta)
        if not (corr and sfx):
            break
        for k, v in corr.items():
            total['eventos'][k] = round(float(total['eventos'].get(k, 0.0)) + v, 1)
        sfx = preparar_sfx(ctx, analisis, nivel, mezcla=total)
        log(f"QC: {len(corr)} sonido(s) bajado(s) para no pisar la voz → se vuelve a medir")
        med = MZ.medir(video, ctx, eventos(), voz)
        corr, bus = MZ.correcciones(med)
    if bus and sfx:                                                   # y si el true peak aún lo empujan los del director, su bus (la voz no)
        total['bus'] = round(total['bus'] + float(bus), 1)
        sfx = preparar_sfx(ctx, analisis, nivel, mezcla=total)
        if capas and (capas.get('musica') or {}).get('estado'):
            capas = preparar_capas(ctx, analisis, nivel + total['bus'])
        log(f"QC: bus del director {float(bus):+.1f} dB (true peak) → se vuelve a medir")
        med = MZ.medir(video, ctx, eventos(), voz)
    estado['mezcla_ajustes'] = total
    estado['sfx_plan'] = (sfx or {}).get('eventos') or estado.get('sfx_plan')
    score, partes = MZ.puntuar(med, estado, ((sfx or {}).get('diseno') or {}).get('eventos'))
    mix, master = MZ.textos(med, partes)
    antes = (previas or {}).get('eventos') or {}
    aplicadas = {'eventos': {k: round(v - float(antes.get(k, 0.0)), 1) for k, v in total['eventos'].items() if abs(v - float(antes.get(k, 0.0))) > 0.05},
                 'bus': round(total['bus'] - float((previas or {}).get('bus') or 0.0), 1)}          # (lo que bajó ESTA revisión)
    qc = {'medidas': {k: med[k] for k in ('mezcla', 'voz', 'clipping', 'segundos', 'musica_bajo_voz_db')}, 'correcciones': aplicadas,
          'score': score, 'partes': partes, 'formula': MZ.FORMULA, 'mix': mix, 'master': master}
    lo = med['mezcla'] or {}
    log(f"QC: {'passed' if mix['nivel'] == 'ok' and master['nivel'] == 'ok' else 'revisado'} · mezcla {lo.get('lufs')} LUFS, TP {lo.get('tp_db')} dBTP, "
        f"{med['clipping']} recortes")
    log(f"Sound Score: {score}/100 (" + ', '.join(f"{k} {v['puntos']}" for k, v in partes.items()) + ')')
    return sfx, capas, qc


def _guardar_qc(estado, qc):
    estado.update({'sound_score': qc['score'], 'score_components': qc['partes'], 'mix': qc['mix'], 'master': qc['master'],
                   'qc': {k: qc[k] for k in ('medidas', 'correcciones', 'formula')}})


def preparar_sfx(ctx, analisis, nivel_voz_db=None, diseno=None, ctrl=None, ajustes=None, ronda=None, mezcla=None):
    """FASE 3: el diseño (qué suena, qué no y por qué) y cada sonido hecho a la medida en su WAV (director_sonido_diseno / director_sonido_sfx).
    `ctrl` (None = los guardados de la página), `ajustes` y `ronda` (None = los del estado del video). Devuelve {'diseno', 'eventos' (para el plan
    de Efectos, pistas AI SFX …), 'puestos', 'nivel_voz_db', 'modo', 'segundos'}."""
    import director_sonido_diseno as D3
    import director_sonido_sfx as SFX
    fps = float((ctx.get('plan_efectos') or {}).get('fps') or 30.0)
    if ajustes is None or ronda is None:
        previo = E.cargar(ctx['video'])
        ajustes = (previo.get('ajustes') or {}) if ajustes is None else ajustes
        ronda = int(previo.get('ronda') or 0) if ronda is None else ronda
    diseno = diseno or D3.disenar(analisis, ctx, fps, controles=controles() if ctrl is None else ctrl, ajustes=ajustes, ronda=ronda)
    if mezcla and (mezcla.get('eventos') or mezcla.get('bus')):          # FASE 5: lo que el QC baja (solo esos eventos; el bus, todos)
        diseno = copy.deepcopy(diseno)
        for e in diseno['eventos']:
            e['nivel_rel_voz_db'] = round(float(e['nivel_rel_voz_db']) + float((mezcla.get('eventos') or {}).get(e.get('clave'), 0.0))
                                          + float(mezcla.get('bus') or 0.0), 1)
    nivel = _nivel_voz_previsto(ctx, analisis) if nivel_voz_db is None else round(float(nivel_voz_db), 1)
    hecho = SFX.fabricar(diseno, E.carpeta_de(ctx['video']) / 'sfx', nivel)
    sfx = {'diseno': diseno, 'eventos': hecho['eventos'], 'puestos': hecho['puestos'], 'nivel_voz_db': nivel, 'modo': hecho['modo'],
           'segundos': hecho['segundos']}
    _log_sfx(sfx)
    return sfx


def _log_sfx(sfx):
    r = sfx['diseno']['resumen']
    fuentes = {}
    for p in sfx['puestos']:
        clave = p['fuente'].split(' (')[0]
        fuentes[clave] = fuentes.get(clave, 0) + 1
    log(f"Sound events selected: {len(sfx['eventos'])} (" + ', '.join(f'{k} {v}' for k, v in r['por_tipo'].items()) + f") · modo {sfx['modo']} · "
        + ', '.join(f'{k} {v}' for k, v in fuentes.items()) + f" · voz a {sfx['nivel_voz_db']} dBFS · {sfx['segundos']} s")
    log(f"Captions: {r['con_sonido']} con sonido, {r['en_silencio']} en silencio (umbral {r['umbral']}; acento «{r['acento']}»: {r['por_que_acento']}) · "
        f"motions con sonido {r['motions_con_sonido']} de {r['motions']}")
    v = r['viejos']
    if any(v.values()):
        log(f"Old caption SFX: {v['REPLACE']} REPLACE, {v['REMOVE']} REMOVE, {v['KEEP']} KEEP")


def preparar_capas(ctx, analisis, nivel_voz_db=None, ctrl=None):
    """FASE 4: la música y el ambiente (director_sonido_capas). Devuelve {'musica', 'ambiente', 'nivel_voz_db'}; cada uno con su 'plan' (eventos para
    las pistas AI MUSIC / AI AMBIENCE)."""
    import director_sonido_capas as CA
    nivel = _nivel_voz_previsto(ctx, analisis) if nivel_voz_db is None else round(float(nivel_voz_db), 1)
    c = controles() if ctrl is None else ctrl
    carpeta = E.carpeta_de(ctx['video'])
    m = CA.musica(analisis, ctx, c, carpeta, nivel)
    a = CA.ambiente(analisis, ctx, c, carpeta, nivel)
    log(f"Music: {m['estado']} ({m.get('por_que')})")
    log(f"Ambience: {a.get('resumen') or 'nada que añadir'}" + (f" · {len(a['plan'])} tramo(s) en AI AMBIENCE" if a.get('plan') else ''))
    return {'musica': m, 'ambiente': a, 'nivel_voz_db': nivel}


def _guardar_capas(estado, capas):
    m, a = capas['musica'], capas['ambiente']
    estado.update({'music_decision': {k: m.get(k) for k in ('estado', 'por_que', 'candidatos', 'elegido', 'tramos', 'deseado')},
                   'music_decision_state': {'estado': m.get('estado'), 'por_que': m.get('por_que')}, 'music_plan': m.get('plan') or [],
                   'ambience_decision': {'escenas': a.get('escenas'), 'resumen': a.get('resumen')}, 'ambience_plan': a.get('plan') or []})


def _guardar_sfx(estado, sfx):
    d = sfx['diseno']
    estado.update({'sound_events': [{k: e.get(k) for k in ('id', 'clave', 'tipo', 't', 'ancla', 'dur', 'pista', 'decision', 'por_que', 'importancia', 'origen',
                                                            'ref', 'params', 'bloqueado', 'ajustado')}
                                    for e in d['eventos']],
                   'sound_events_placed': sfx['puestos'], 'sfx_plan': sfx['eventos'], 'caption_decisions': d['captions'], 'motion_decisions': d['motions'],
                   'old_sfx_decisions': d['viejos'], 'sfx_summary': dict(d['resumen'], modo=sfx['modo'], nivel_voz_db=sfx['nivel_voz_db'])})


VERSION_VOZ = 1                                                       # súbela si cambia la restauración: las copias viejas se rehacen


def _clave_voz(video, segs):
    import hashlib
    import director_sonido_voz as V
    base = f"{E.huella(video)}|{segs or ''}|{V.VERSION_CADENA}|{VERSION_VOZ}"
    return hashlib.sha1(base.encode('utf-8')).hexdigest()[:12]


def _pistas_propias():
    """Los nombres de las pistas de audio que pone CineCaptions además de FX-/PRO-/AI/SFX (la de los sonidos de captions es configurable)."""
    try:
        import sfx_rules
        n = sfx_rules.cargar_reglas().get('nombre_pista_audio')
        return [str(n)] if n else []
    except Exception:
        return []


def preparar_voz(ctx, analisis, interno, estado, al_estado=None):
    """FASE 2: la voz restaurada (una COPIA en ~/DaVinciSubtitles/sound_director/<huella>/) y el evento 'voz_ai' para «AI VOICE».
    Solo en un timeline que armó GO con el video soltado (A1 = el audio de ese archivo desde el fotograma 0); con el audio del timeline (la mezcla de
    sus pistas) la voz original se queda. Con caché: la misma voz con la misma cadena no se procesa dos veces. Devuelve (voz, evento | None)."""
    import director_sonido_voz as V
    video = ctx['video']
    if not ctx.get('timeline_de_go'):
        voz = {'archivo': None, 'nivel': 0, 'backend': 'sin proceso', 'motivo': 'el audio viene del timeline de Resolve (la mezcla de sus pistas): la voz original se queda',
               'antes': V.resumen_calidad(analisis['voz'])}
        log('Voice: ' + voz['motivo'])
        return voz, None
    segs = interno.get('segmentos')
    clave = _clave_voz(video, segs)
    previa = estado.get('voz') or {}
    if previa.get('clave') == clave and previa.get('archivo') and os.path.isfile(previa['archivo']):
        voz = dict(previa, despues=estado.get('voice_quality_after'), antes=estado.get('voice_quality_before'), guardas=(estado.get('metricas') or {}).get('guardas_voz'),
                   desde_cache=True)
        log(f"Voice backend: {voz.get('backend')} (la misma copia de antes, sin procesar otra vez)")
    else:
        destino = E.carpeta_de(video) / f'AI_VOICE_{clave}.wav'
        mezclada = bool(analisis['musica']['en_la_fuente'].get('presente'))
        voz = V.restaurar(video, destino, segs, ctx.get('palabras'), interno['diag'], interno['medidas'], interno.get('extractos'), mezclada, al_estado,
                          ambiente=analisis.get('ambiente'), ventanas=interno.get('ventanas'))
        voz['clave'] = clave
        _log_voz(voz)
    if not voz.get('archivo'):
        return voz, None
    evento = {'tipo': 'voz_ai', 'ini': 0.0, 'archivo': voz['archivo'], 'dur': voz.get('duracion'), 'asset': 'AI VOICE', 'canales': voz.get('canales', 2),
              'backend': f"{voz.get('backend')} nivel {voz.get('nivel')}", 'propias': _pistas_propias()}
    return voz, evento


def _log_voz(voz):
    log(f"Voice backend: {voz.get('backend')} (nivel {voz.get('nivel')}) · {voz.get('motivo')}")
    if voz.get('cadena'):
        log('Voice chain: ' + ' → '.join(c['filtro'] for c in voz['cadena']) + f" · ganancia {voz.get('ganancia_db')} dB (fuerza {voz.get('fuerza')})")
    a, d = voz.get('antes') or {}, voz.get('despues') or {}
    if d:
        log(f"Voice before/after: fondo {a.get('suelo_ruido_db')} → {d.get('suelo_ruido_db')} dBFS · {a.get('lufs')} → {d.get('lufs')} LUFS · "
            f"TP {a.get('tp_db')} → {d.get('tp_db')} dBTP · sibilancia {a.get('sibilancia')} → {d.get('sibilancia')}")
    g = (voz.get('guardas') or {}).get('final') or {}
    log('QC voz: ' + ('passed' if voz.get('archivo') else 'reverted (' + str(voz.get('motivo')) + ')') + (' · ' + '; '.join(g.get('motivos') or []) if g.get('motivos') else ''))


def plan_de_limpieza(video):
    """Un plan de Efectos que SOLO toca las pistas AI (colocar_efectos: 'solo_ai'): sin evento 'voz_ai' quita AI VOICE y A1 vuelve a sonar."""
    return {'eventos': [], 'duracion': None, 'resumen': '', 'zonas': [], 'solo_audio': True, 'solo_ai': True, 'video': str(video or '')}


def decidir_efectos(e):
    """KEEP / REPLACE con su porqué para un sonido que puso Efectos (el director es el único dueño del sonido)."""
    asset = str(e.get('asset') or '')
    if e.get('extra'):
        return {'asset': asset, 'ini': e.get('ini'), 'decision': 'REPLACE',
                'por_que': 'sonido de la biblioteca de siempre (legacy: DISABLED_FOR_NEW_DESIGN): el gancho y los cortes los diseña el director a su medida'}
    if asset.lower().startswith('outro') or e.get('crudo'):
        return {'asset': asset, 'ini': e.get('ini'), 'decision': 'KEEP', 'por_que': 'va pegado a la animación de la outro: se diseñó con ella'}
    if float(e.get('ini') or 0.0) < 1.0:
        return {'asset': asset, 'ini': e.get('ini'), 'decision': 'KEEP', 'por_que': 'va pegado a la intro (luz, zoom): se diseñó con ella'}
    return {'asset': asset, 'ini': e.get('ini'), 'decision': 'KEEP', 'por_que': 'sonido propio de un efecto visual de Efectos: se respeta'}


def _pistas_sfx_captions():
    """Las pistas de audio de los sonidos de Simple (un toque por palabra y el de cada emoji): «SFX…» y la que diga sfx_rules."""
    return sorted({'SFX'} | set(_pistas_propias()))


def al_colocar(plan, res, video, plan_pro=None):
    """Lo último antes de Resolve (hilo de GO). Encendido: una COPIA del plan de Efectos en la que el director es el ÚNICO dueño del sonido —sus
    sonidos en las pistas AI SFX …, los de Efectos con KEEP / REPLACE, los de Simple apagados ('apagar_sfx': colocar_efectos apaga sus clips, no los
    borra) y la PRO marcada para que sonidos_pro quite los suyos— y el evento 'voz_ai' si hay voz restaurada. Sin nada del director pero con sus
    pistas de una vez anterior: el plan (o uno que solo limpia) para que se vayan y A1 vuelva. En cualquier otro caso devuelve el MISMO plan
    (apagado = GO de siempre). Nunca lanza."""
    try:
        encendido = activo()
        ev = (res or {}).get('evento_voz') if encendido else None
        sfx = (res or {}).get('sfx') if encendido else None
        capas = (res or {}).get('capas') if encendido else None
        capas_ev = [dict(x) for k in ('musica', 'ambiente') for x in ((capas or {}).get(k) or {}).get('plan') or []]
        if not ev and not sfx and not capas_ev:
            g = E.general()
            if not (g.get('voz_ai_puesta') or g.get('ai_puesto')):
                return plan
            E.poner_general(voz_ai_puesta=False, ai_puesto=False)
            log('sin AI Sound Director en este GO: quito sus pistas de la vez anterior y A1 vuelve a sonar')
            if plan and plan.get('eventos'):
                return plan                                           # colocar_efectos quita las pistas AI que no van en el plan
            return plan_de_limpieza(video)
        nuevo = copy.deepcopy(plan) if plan else plan_de_limpieza(video)
        eventos = [e for e in (nuevo.get('eventos') or []) if e.get('tipo') != 'voz_ai' and not (e.get('tipo') == 'sonido' and e.get('pista'))]
        if sfx:
            quedan, decisiones = [], []
            for e in eventos:
                if e.get('tipo') != 'sonido':
                    quedan.append(e)
                    continue
                d = decidir_efectos(e)
                decisiones.append(d)
                if d['decision'] == 'KEEP':
                    quedan.append(e)
            eventos = quedan + [dict(x) for x in sfx.get('eventos') or []]
            nuevo['apagar_sfx'] = _pistas_sfx_captions()
            if isinstance(plan_pro, dict):
                plan_pro['_ai_sound'] = True
            if decisiones:
                log('Efectos SFX: ' + ' · '.join(f"{d['asset']} → {d['decision']}" for d in decisiones))
            try:
                estado = E.cargar(video)
                estado['efectos_sfx_decisions'] = decisiones
                estado['pendiente_resolve'], estado['en_resolve'] = False, time.strftime('%Y-%m-%d %H:%M:%S')
                estado['ultimo_go'] = {'con_director': True, 'fecha': time.strftime('%Y-%m-%d %H:%M:%S'), 'voz': bool(ev), 'apagar_sfx': nuevo['apagar_sfx'],
                                       'evento_voz': dict(ev) if ev else None, 'pro': isinstance(plan_pro, dict)}
                E.guardar(video, estado)
            except Exception:
                pass
            log(f"Events placed: {len(sfx.get('eventos') or [])} en las pistas AI SFX · sonidos de Simple apagados ({', '.join(nuevo['apagar_sfx'])})"
                + (' · la PRO deja los suyos al director' if isinstance(plan_pro, dict) else ''))
        if capas_ev:
            if any(x.get('pista') == 'AI MUSIC' for x in capas_ev):     # la música del director manda: la de Efectos (si la hubiera) sale
                eventos = [e for e in eventos if not (e.get('tipo') == 'musica' and not e.get('pista'))]
            eventos += capas_ev
            log(f"Layers placed: {', '.join(sorted({x['pista'] for x in capas_ev}))}")
        if ev:
            eventos.append(dict(ev))
        nuevo['eventos'] = eventos
        if not plan:
            nuevo['duracion'] = (ev or {}).get('dur')
        E.poner_general(voz_ai_puesta=bool(ev), ai_puesto=True, ultimo_video=str(video or ''))
        return nuevo
    except Exception:
        fallback('al colocar')
        return plan


def sonidos_pro(plan, sonidos, fps=30.0):
    """Final de edicion_pro.aplicar. Con el director al mando en este GO (plan['_ai_sound'], lo pone al_colocar), los sonidos de la PRO (gráficos,
    kit neón, Motions completo: lo que la PRO arma AL APLICAR y el director no podía ver antes) se REDISEÑAN: el mismo instante y el mismo tipo de
    movimiento, hechos por el director (rediseñar_pro). Si eso fallara, los de la PRO se quitan salvo los de «Motions completo». Sin la marca,
    devuelve la MISMA lista."""
    if not (isinstance(plan, dict) and plan.get('_ai_sound')):
        return sonidos
    try:
        nuevos, n_silencio = redisenar_pro(plan, sonidos or [], fps)
        log(f"PRO SFX: {len(nuevos)} rediseñados por el director (mismo instante, sonido a la medida), {n_silencio} en silencio (pisaban un acento o "
            f"sobraban), de {len(sonidos or [])}")
        return nuevos
    except Exception:
        fallback('sonidos de la PRO')
        quedan = [e for e in (sonidos or []) if e.get('origen') == 'motions']
        log(f"PRO SFX: {len(sonidos or []) - len(quedan)} REMOVE, {len(quedan)} KEEP (Motions completo)")
        return quedan


_PRO_TIPO = {'PRO-WHOOSH': 'whoosh', 'PRO-RISER': 'riser', 'PRO-HIT': 'golpe'}
_PRO_POP = ('pop', 'pin', 'chincheta', 'check', 'píldora', 'pildora', 'icono', 'cae', 'aparece', 'llega', 'sticker')


def redisenar_pro(plan, sonidos, fps=30.0):
    """Cada sonido que la PRO puso, rehecho por el director: el instante sale del pico del sonido original (lo que la PRO sincronizó con su
    animación), el tipo de su pista y de lo que describe (whoosh, riser, golpe, pop o tic). Nada a < 0,15 s de un acento de caption (salvo risers),
    densidad por ventanas de 10 s con lo que ya suena del director, mismo modo híbrido y nivel bajo la voz. Devuelve (eventos para colocar_pro,
    cuántos quedaron en silencio)."""
    import numpy as np
    import director_sonido_diseno as D3
    import director_sonido_eventos as EV
    import director_sonido_medir as M
    import director_sonido_sfx as SFX
    video = str(plan.get('video') or '')
    estado = E.cargar(video) if video else {}
    nivel = float((estado.get('sfx_summary') or {}).get('nivel_voz_db') or -18.0)
    v = ((estado.get('paleta') or {}).get('valores') or {})
    brillo, densidad = float(v.get('brillo', 0.5)), float(v.get('densidad', 0.3))
    suenan = [e for e in estado.get('sound_events') or [] if e.get('decision') == 'GENERATE']
    acentos = [float(e['ancla']) for e in suenan if e.get('origen') in ('caption', 'dato', 'gancho', 'cierre')]
    hechos = [float(e['ancla']) for e in suenan if e.get('origen') == 'motion']       # (los motions que el director ya vio y sonorizó: no se repiten)
    candidatos = []
    for k, e in enumerate(sonidos):
        try:
            import wave
            with wave.open(str(e['archivo']), 'rb') as w:
                sr = float(w.getframerate())
            x = np.concatenate(list(M.leer_wav(e['archivo'])), axis=1)
        except Exception:
            x = None
        if x is None or not x.size:
            continue
        env = np.convolve(np.abs(x).max(axis=0), np.ones(int(sr // 500)) / int(sr // 500), 'same')
        pico = float(np.argmax(env)) / sr
        largo = x.shape[1] / sr
        que = str(e.get('que') or '').lower()
        pista = str(e.get('pista') or '')
        tipo = _PRO_TIPO.get(pista) or ('pop' if any(w in que for w in _PRO_POP) else 'tick')
        t0 = float(e.get('ini') or 0) / float(fps)
        ancla = t0 + (largo if tipo == 'riser' else pico)
        imp = {'riser': 0.6, 'golpe': 0.6, 'whoosh': 0.55 if 'grande' in que or 'escena' in que or 'cortinilla' in que else 0.5, 'pop': 0.42}.get(tipo, 0.35)
        if (tipo not in ('riser',) and any(abs(ancla - a) < D3.CHOQUE_S for a in acentos)) or any(abs(ancla - a) < 0.3 for a in hechos):
            continue
        d = float(np.clip(largo, 0.25, 1.2)) if tipo == 'whoosh' else (min(2.0, largo) if tipo == 'riser' else (0.6 if tipo == 'golpe' else 0.25))
        params = {'brillo': brillo, 'semilla': D3._semilla('pro', tipo, round(ancla, 3), video)}
        if tipo == 'whoosh':
            params.update(direccion=0.6 if k % 2 else -0.6, easing='easeInOutCubic', peso=0.45 if imp > 0.5 else 0.35)
        elif tipo == 'golpe':
            params.update(peso=0.55, cola=0.3, pre=0.05)
        t = ancla - (0.55 * d if tipo == 'whoosh' else (d if tipo == 'riser' else 0.0))
        candidatos.append({'id': f'pro-{tipo}-{k + 1:02d}', 'tipo': tipo, 't': round(max(0.0, t), 3), 'ancla': round(ancla, 3),
                           'dur': round(d + (0.12 if tipo == 'whoosh' else 0.0), 3), 'pista': EV.PISTA[tipo], 'nivel_rel_voz_db': EV.NIVEL_REL_VOZ[tipo],
                           'params': params, 'decision': 'GENERATE', 'por_que': f"PRO: {e.get('que') or pista}", 'importancia': imp, 'origen': 'pro',
                           'ref': None, 'clave': f"pro|{tipo}|{round(ancla, 1)}", '_pista_pro': pista or 'PRO-TEXTURA'})
    tope = int(round(2 + 4 * densidad)) + 1                           # (los de la PRO acompañan a motions que se VEN: uno más de margen)
    ya = [float(e['ancla']) for e in suenan]
    for k0 in np.arange(0, max([c['ancla'] for c in candidatos] or [0.0]) + 10.0, 10.0):
        dentro = [c for c in candidatos if k0 <= c['ancla'] < k0 + 10 and c['decision'] == 'GENERATE']
        sitio = max(0, tope - sum(1 for a in ya if k0 <= a < k0 + 10))
        for c in sorted(dentro, key=lambda c: (c['importancia'], -c['t']))[:max(0, len(dentro) - sitio)]:
            c['decision'] = 'REMOVE'
    activos = [c for c in candidatos if c['decision'] == 'GENERATE']
    hecho = SFX.fabricar({'eventos': activos}, E.carpeta_de(video) / 'sfx', nivel) if activos else {'eventos': [], 'puestos': []}
    pistas = {c['id']: c['_pista_pro'] for c in activos}
    try:
        from edicion_pro_ograf import ruta_larga
    except Exception:
        ruta_larga = str
    salida = [{'pista': pistas.get((x.get('ai') or {}).get('id'), 'PRO-TEXTURA'), 'ini': int(round(float(x['ini']) * fps)), 'archivo': str(ruta_larga(x['archivo'])),
               'dur': x['dur'], 'db': 0.0, 'que': f"AI · {(x.get('ai') or {}).get('id')}"} for x in hecho['eventos']]
    try:
        estado = E.cargar(video)
        estado['pro_sound_events'] = [{k: c.get(k) for k in ('id', 'clave', 'tipo', 't', 'ancla', 'dur', 'decision', 'por_que', 'importancia', 'origen')}
                                      for c in candidatos]
        estado['pro_sfx_plan'] = [dict(x) for x in hecho['eventos']]
        E.guardar(video, estado)
    except Exception:
        pass
    return salida, len(sonidos) - len(salida)
