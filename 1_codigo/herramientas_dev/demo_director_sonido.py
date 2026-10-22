# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/demo_director_sonido.py — el Tema 1 renderizado SIN Resolve con varias bandas sonoras del AI Sound Director, para compararlas.
"""
    python demo_director_sonido.py [--video V] [--salida CARPETA] [--versiones ABCD]

El MISMO video y los MISMOS captions del Tema 1 (los que GO dejó en ~/DaVinciSubtitles/<video>.es.kinetic.json; si no hay, los del planificador)
dibujados por render_sin_resolve (el render de «GO sin Resolve»), con cuatro bandas sonoras:
    A  ACTUAL (legacy)        lo que pone GO hoy: el sonido de Simple en cada caption (sfx_library)
    B  AI · procedural        el director decide qué suena (la mayoría en silencio) y DISEÑA cada sonido a la medida de la animación real
    C  AI · biblioteca autor  las mismas decisiones con sonidos de la biblioteca del autor que pasan el Quality Gate (si ninguno pasa: silencio)
    D  AI · híbrido           C + una capa procedural (sub y clic en los golpes, aire en los whooshes) ajustada a cada motion
Deja los MP4, el audio de cada versión (WAV), los sonidos del director solos (stem) y `informe_demo.json` (decisiones, motivos, medidas).
No toca Resolve ni las preferencias del usuario.
"""
import copy
import json
import os
import sys
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI))

import numpy as np

SR = 48000


def _cues_de_go(video):
    p = Path.home() / 'DaVinciSubtitles' / f'{Path(video).stem}.es.kinetic.json'
    if p.is_file():
        return json.loads(p.read_text(encoding='utf-8')).get('cues') or [], str(p)
    return None, None


def _base_audio(video, dur):
    import render_sin_resolve as R
    base = R._leer_audio(video)
    n = int(dur * SR) + 1
    x = np.zeros((2, n), np.float32)
    if base is not None:
        x[:, :min(n, base.shape[1])] = base[:, :n]
    return x


def _poner(bus, x, t):
    i = int(round(t * SR))
    if i >= bus.shape[1] or x is None or not x.size:
        return
    if i < 0:
        x, i = x[:, -i:], 0
    k = min(x.shape[1], bus.shape[1] - i)
    bus[:, i:i + k] += x[:, :k]


def _ganancia(x, objetivo_db):
    import director_sonido_sintesis as S
    return x * (10 ** ((objetivo_db - S.rms_activo_db(x)) / 20.0))


def _pico_idx(x):
    m = np.abs(x).max(axis=0)
    env = np.convolve(m, np.ones(96) / 96, 'same')
    return int(np.argmax(env))


def _balance(x, pos):
    if not pos:
        return x
    a = (np.clip(pos, -1, 1) + 1) * np.pi / 4
    return np.vstack((x[0] * np.cos(a) * 1.414, x[1] * np.sin(a) * 1.414)).astype(np.float32)


def sintetizar(e, rng):
    import director_sonido_sintesis as S
    p = e['params']
    t = e['tipo']
    if t == 'golpe':
        return S.golpe(p.get('peso', 0.7), p.get('brillo', 0.5), p.get('cola', 0.4), p.get('pre', 0.09), rng), p.get('pre', 0.0)
    if t == 'whoosh':
        x = S.whoosh(e['dur'] - 0.12, p.get('direccion', 0.0), p.get('easing', 'easeInOutCubic'), p.get('brillo', 0.5), p.get('peso', 0.4), rng)
        return x, e['ancla'] - e['t']
    if t == 'giro':
        return S.giro(e['dur'] - 0.05, p.get('brillo', 0.5), rng), e['ancla'] - e['t']
    if t == 'trazo':
        return S.trazo(e['dur'] - 0.05, p.get('potencia', 2.4), p.get('brillo', 0.5), rng), 0.0
    if t == 'riser':
        return S.riser(e['dur'], p.get('brillo', 0.5), rng=rng), e['dur']
    if t == 'acento':
        return S.acento(p.get('nota', 523.25), e['dur'], p.get('brillo', 0.5)), 0.0
    if t == 'tick':
        return S.tick(p.get('brillo', 0.5), rng), 0.0
    return None, 0.0


CATEGORIA = {'golpe': 'golpe', 'whoosh': 'whoosh', 'giro': 'whoosh', 'riser': 'riser', 'trazo': 'trazo', 'acento': 'tonal', 'tick': 'ui'}


def de_biblioteca(e, usados, rng, informe):
    """El mejor archivo de la biblioteca del autor que pasa el Quality Gate, recortado y alineado (pico en el ancla; el riser acaba en él)."""
    import director_sonido_fuentes as F
    tipo = CATEGORIA.get(e['tipo'])
    cands = F.candidatos(tipo)
    objetivo = {'tipo': tipo, 'dur': e['dur'], 'brillo': e['params'].get('brillo', 0.5), 'energia': 0.8 if e['tipo'] == 'golpe' else 0.4}
    ruta, ranking = F.elegir(cands, objetivo, usados)
    rechazados = sum(1 for r in ranking if r[0] < 0)
    informe.append({'evento': e['id'], 'tipo': e['tipo'], 'candidatos': len(ranking), 'rechazados_quality_gate': rechazados,
                    'elegido': Path(ruta).name if ruta else None, 'top3': [(r[0], Path(r[1]).name, r[2]) for r in ranking[:3]]})
    if not ruta:
        return None, 0.0
    usados[ruta] = usados.get(ruta, 0) + 1
    largo = e['dur'] + (0.6 if e['tipo'] in ('golpe', 'acento') else 0.2)
    x = F.leer_para_mezcla(ruta, None if e['tipo'] == 'riser' else largo, 0.25 if e['tipo'] in ('golpe', 'acento') else 0.04)   # (colas largas: fundido largo)
    if x is None:
        return None, 0.0
    if e['tipo'] == 'riser':
        x = x[:, -int(e['dur'] * SR):] if x.shape[1] > e['dur'] * SR else x
        return _balance(x, 0.0), x.shape[1] / SR
    off = _pico_idx(x) / SR
    return _balance(x, e['params'].get('direccion', 0.0)), off


def construir(diseno, nivel_voz, n, modo, rng, informe):
    """El bus de los sonidos del director (2, n): modo 'procedural' | 'biblioteca' | 'hibrido'."""
    import director_sonido_sintesis as S
    bus = np.zeros((2, n), np.float32)
    usados = {}
    puestos = []
    for e in diseno['eventos']:
        if e['decision'] != 'GENERATE':
            continue
        objetivo = nivel_voz + e['nivel_rel_voz_db']
        if modo == 'procedural':
            x, off = sintetizar(e, rng)
            fuente = 'procedural'
        else:
            x, off = de_biblioteca(e, usados, rng, informe)
            fuente = 'biblioteca del autor'
            if x is None and modo == 'hibrido':
                x, off = sintetizar(e, rng)
                fuente = 'procedural (ningún archivo pasó el Quality Gate)'
            if x is None:
                puestos.append({'id': e['id'], 'tipo': e['tipo'], 'fuente': 'LEAVE_SILENT', 'por_que': 'ningún archivo pasó el Quality Gate: mejor silencio'})
                continue
        if x is None:
            continue
        x = _ganancia(x, objetivo)
        inicio = e['ancla'] - off if e['tipo'] != 'riser' else e['ancla'] - off - 0.03
        _poner(bus, x, inicio)
        capa = None
        if modo == 'hibrido' and fuente == 'biblioteca del autor' and e['tipo'] in ('golpe', 'whoosh'):
            if e['tipo'] == 'golpe':                                   # el peso y el clic a la medida del héroe, debajo del archivo
                capa = S.golpe(e['params'].get('peso', 0.7), e['params'].get('brillo', 0.5), 0.15, 0.0, rng)
                _poner(bus, _ganancia(capa, objetivo - 6.0), e['ancla'])
            else:                                                      # el aire que sigue el easing y la dirección del corte
                capa = S.whoosh(e['dur'] - 0.12, e['params'].get('direccion', 0.0), e['params'].get('easing', 'easeInOutCubic'), 0.8, 0.2, rng)
                _poner(bus, _ganancia(capa, objetivo - 8.0), e['t'])
            fuente += ' + capa procedural'
        puestos.append({'id': e['id'], 'tipo': e['tipo'], 't': e['t'], 'fuente': fuente})
    return bus, puestos


def limitar(x, techo_dbtp=-1.0):
    """Limitador (−1,5 dBFS de muestra) y, si los picos ENTRE muestras pasan de −1 dBTP, se baja lo justo (true peak medido con ebur128)."""
    import director_sonido_medir as M
    G = M.Grafo([('alimiter', 'limit=0.8414:attack=5:release=80:level=false:latency=1')], 2)
    y = np.concatenate([G.empujar(x[:, i:i + SR * 4]) for i in range(0, x.shape[1], SR * 4)] + [G.terminar()], axis=1)
    y = y[:, :x.shape[1]] if y.shape[1] >= x.shape[1] else np.pad(y, ((0, 0), (0, x.shape[1] - y.shape[1])))
    tp = medir(y).get('tp_db')
    if tp is not None and tp > techo_dbtp:
        y = y * (10 ** ((techo_dbtp - 0.1 - tp) / 20.0))
    return y.astype(np.float32)


def medir(x):
    import director_sonido_medir as M
    S = M.Sonometro(2)
    for i in range(0, x.shape[1], SR * 4):
        S.medir(x[:, i:i + SR * 4])
    return S.resultado()


def _leeme(salida, informe, diseno, nombres):
    """Un LEEME para comparar: qué es cada versión, qué decidió el director y por qué."""
    r = diseno['resumen']
    lin = ['AI Sound Director — Tema 1 (Kinetic) con 4 bandas sonoras. Mismo video, mismos captions (los que puso GO); solo cambia el sonido.', '',
           f"Video: {Path(informe['video']).name} · tema {informe['tema']} · perfil: {informe['perfil']}",
           f"Música: {informe['musica']['estado']} — {informe['musica']['por_que']}",
           f"Voz: ruido {informe['voz']['ruido']} — el video trae música mezclada con la voz: se deja la voz original (no se separa ni se toca la música).", '',
           'VERSIONES', '']
    textos = {'A': 'lo que pone GO hoy: un «Hit» de la biblioteca vieja (sfx_library) en casi cada caption',
              'B': 'el director decide qué suena y DISEÑA cada sonido (procedural) a la medida de la animación real del Tema 1',
              'C': 'las mismas decisiones con sonidos de TU biblioteca (UTILES) que pasan el Quality Gate y encajan por su nombre; si ninguno encaja: silencio',
              'D': 'C + una capa procedural ajustada al motion (sub y clic en los golpes, aire en los whooshes); lo que no tiene archivo, procedural',
              'E': 'la FASE 3 tal como la pone GO (director_sonido_diseno + director_sonido_sfx, modo híbrido): los mismos WAV y tiempos de las pistas AI SFX'}
    for v, d in informe['versiones'].items():
        lo = d['loudness']
        lin.append(f"{v}  {nombres[v]}.mp4 — {textos[v]} · {d['sonidos']} sonidos · {lo.get('lufs')} LUFS · true peak {lo.get('tp_db')} dBTP")
    lin += ['', f"DECISIONES (B, C y D): {r['captions']} captions → {r['con_sonido']} con sonido, {r['en_silencio']} en silencio (CAPTION_SOUND_SCORE ≥ {r['umbral']}); "
            f"de los «Hit» viejos: {r['viejos'].get('REPLACE', 0)} sustituidos por un golpe diseñado, {r['viejos'].get('REMOVE', 0)} quitados.", '']
    for c in diseno['captions']:
        lin.append(f"  caption {c['cue'] + 1:2d} {c['t']:6.2f} s «{c['texto']}» {c['rol']:<11} score {c['caption_sound_score']:.2f} → {c['decision']}: {c.get('por_que', '')}")
    lin += ['', 'SONIDOS DEL DIRECTOR', '']
    for e in diseno['eventos']:
        lin.append(f"  {e['id']:<11} {e['t']:6.2f} s  {e['pista']:<16} {e['decision']:<7} {e['por_que']}")
    d3 = informe.get('diseno_fase3')
    if d3:
        r3 = d3['resumen']
        lin += ['', f"FASE 3 (E): {r3['con_sonido']} de {r3['captions']} captions con sonido (umbral {r3['umbral']}, acento «{r3['acento']}»: {r3['por_que_acento']})", '']
        for e in d3['eventos']:
            lin.append(f"  {e['id']:<11} {e['ancla']:6.2f} s  {e['pista']:<16} {e['decision']:<8} {e['por_que']}")
    sel = (informe['versiones'].get('C') or {}).get('seleccion_biblioteca') or []
    if sel:
        lin += ['', 'TU BIBLIOTECA (versión C): el elegido de cada sonido entre varios candidatos (semantic, quality, duration, spectral, energy, repetición)', '']
        for s_ in sel:
            lin.append(f"  {s_['evento']:<11} → {s_['elegido'] or 'SILENCIO (nada encaja)'}  ({s_['candidatos']} candidatos, {s_['rechazados_quality_gate']} rechazados)")
    (salida / 'LEEME.txt').write_text('\n'.join(lin) + '\n', encoding='utf-8')


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    args = sys.argv[1:]
    video = Path(args[args.index('--video') + 1]) if '--video' in args else Path.home() / 'Desktop' / 'VIDEOS EN ESPAÑOL' / 'PRUEBA ESPAÑOL.mp4'
    salida = Path(args[args.index('--salida') + 1]) if '--salida' in args else Path(tempfile.gettempdir()) / 'cc_demo_sonido'
    versiones = args[args.index('--versiones') + 1] if '--versiones' in args else 'ABCD'
    salida.mkdir(parents=True, exist_ok=True)
    import registro
    registro.anotar = lambda *a, **k: None                           # (nada al Registro real del usuario)
    import ajustes_ui
    real = ajustes_ui.leer_prefs
    ajustes_ui.leer_prefs = lambda: dict(real())
    ajustes_ui.guardar_prefs = lambda *a, **k: None
    import director_sonido_estado as Es
    Es.CARPETA = salida / 'sound_director'
    import director_sonido as D
    import director_sonido_eventos as EV
    import efectos_visuales
    import ia_texto
    import render_sin_resolve as R
    ia_texto.disponible = lambda: False
    sys.path.insert(0, str(AQUI))
    import probar_director_sonido as P
    t0 = time.time()
    palabras = P._palabras_de_cache(video)
    cues, origen = _cues_de_go(video)
    if not cues:
        import vista_tema
        cues = vista_tema.planificar(palabras, {}, 'Kinetic', vista_tema.estilo_de_pack('Kinetic', 'v'), idioma='es', fin_video=float(palabras[-1]['end']))
        origen = 'kinetic_planificador (sin GO previo)'
    import av
    with av.open(str(video)) as c:
        vs = c.streams.video[0]
        fps = float(vs.average_rate or 30)
        dur = float(c.duration / 1e6)
    cortes = [t for t, _f in efectos_visuales.detectar_cortes(str(video))]
    ctx = D.contexto(video, palabras, 'Kinetic', 'v', bloques=cues, idioma='es')
    ctx['cortes'] = cortes
    analisis, _i = D.analizar(ctx)
    diseno = EV.disenar_kinetic(cues, analisis['narrativa'], cortes, analisis['paleta'], dur, fps)
    nivel_voz = float(analisis['voz']['nivel_voz_db'])
    print(f"video {video.name} · {dur:.1f} s · {fps:.2f} fps · captions de: {origen}")
    print(f"tema {analisis['tema']} · perfil: {analisis['perfil']['resumen']}")
    print(f"música: {analisis['musica']['estado_sugerido']['estado']} · voz: {analisis['voz']['ruido']} · nivel de la voz {nivel_voz:.1f} dBFS")
    print('diseño:', json.dumps(diseno['resumen'], ensure_ascii=False))
    base = _base_audio(video, dur)
    n = base.shape[1]
    rng = np.random.default_rng(11)
    informe = {'video': str(video), 'captions_de': origen, 'tema': analisis['tema'], 'perfil': analisis['perfil']['resumen'], 'paleta': analisis['paleta'],
               'musica': analisis['musica']['estado_sugerido'], 'voz': {'ruido': analisis['voz']['ruido'], 'problemas': analisis['voz']['problemas']},
               'diseno': diseno, 'versiones': {}}
    nombres = {'A': 'TEMA1_A_actual_legacy', 'B': 'TEMA1_B_AI_procedural', 'C': 'TEMA1_C_AI_biblioteca_autor', 'D': 'TEMA1_D_AI_hibrido',
               'E': 'TEMA1_E_fase3_como_en_GO'}
    modos = {'B': 'procedural', 'C': 'biblioteca', 'D': 'hibrido'}
    import director_sonido_medir as M
    real_mezcla = R.mezclar_audio
    for v in versiones:
        t = time.time()
        if v == 'A':
            mezcla = real_mezcla(video, cues, dur)
            puestos = [{'t': e.get('t'), 'archivo': e.get('sfx_nombre'), 'fuente': 'legacy sfx_library'} for c in cues for e in (c.get('sfx_eventos') or [])]
            stem = None
            cues_v = cues
            sel = []
        else:
            sel = []
            if v == 'E':                                               # fase 3 tal cual: los WAV y los tiempos que GO manda a las pistas AI SFX
                sfx = D.preparar_sfx(ctx, analisis)
                stem = np.zeros((2, n), np.float32)
                for x in sfx['eventos']:
                    _poner(stem, np.concatenate(list(M.leer_wav(x['archivo'])), axis=1), x['ini'])
                puestos = sfx['puestos']
                informe['diseno_fase3'] = sfx['diseno']
            else:
                stem, puestos = construir(diseno, nivel_voz, n, modos[v], np.random.default_rng(11), sel)
            mezcla = limitar(base + stem)
            cues_v = [dict(c, sfx_eventos=[]) for c in cues]
        R.mezclar_audio = (lambda m: (lambda video_, cues_, dur_: m))(mezcla)
        destino = salida / f'{nombres[v]}.mp4'
        try:
            R.renderizar(video, cues_v, salida=str(destino), estilo={'tipo': 'kinetic', 'pack': 'Kinetic'})
        finally:
            R.mezclar_audio = real_mezcla
        W = M.EscritorWav(salida / f'{nombres[v]}.wav', 2)
        W.escribir(mezcla)
        W.cerrar()
        if stem is not None:
            Ws = M.EscritorWav(salida / f'{nombres[v]}_solo_sonidos.wav', 2)
            Ws.escribir(limitar(stem))
            Ws.cerrar()
        lo = medir(mezcla)
        informe['versiones'][v] = {'archivo': str(destino), 'sonidos': len([p for p in puestos if p.get('fuente') != 'LEAVE_SILENT']), 'detalle': puestos,
                                   'loudness': lo, 'segundos': round(time.time() - t, 1), 'seleccion_biblioteca': sel}
        print(f"  {v}: {destino.name} · {informe['versiones'][v]['sonidos']} sonidos · {lo.get('lufs')} LUFS · TP {lo.get('tp_db')} dBTP · {time.time() - t:.1f} s")
    (salida / 'informe_demo.json').write_text(json.dumps(Es.limpio(informe), ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    _leeme(salida, informe, diseno, nombres)
    print(f'listo en {time.time() - t0:.1f} s → {salida}')
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main()
