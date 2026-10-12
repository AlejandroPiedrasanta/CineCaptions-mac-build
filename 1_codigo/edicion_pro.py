# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro.py — «Edición PRO»: con un interruptor, GO edita el video en la línea de tiempo de Resolve (motion graphics, la persona
# delante del texto con Magic Mask, velos, marcos, sonidos), además de los captions del tema elegido.
"""
Flujo en GO (lo llama el script principal, nunca rompe GO: si algo falla, el video sale con sus captions como siempre):

    planificar(video, palabras, duracion, cortes, idioma)   (en el hilo de GO, tras transcribir)
        -> edicion_pro_planificador: estilo del video (boda, XV, restaurante, inmobiliaria, detrás de cámara o general), dirección de arte
           con la semilla del video (cada video, distinto), y qué gráfico va en cada momento.
    aplicar(plan, al_estado, offset_frames)                  (tras colocar los captions)
        1. lee el timeline de Resolve (resolución, fps, clips de V1) por el MCP (Studio) o lo que dejó el Puente (Free);
        2. busca a las personas (IA local, edicion_pro_persona) donde un titular va DETRÁS de ellas y afina la posición de los demás
           gráficos para no taparles la cara;
        3. escribe cada gráfico como .ograf (edicion_pro_ograf) a la resolución del timeline, la composición del Magic Mask con los puntos
           de cada persona (Studio) o el recorte ProRes con alfa (Free / sin Magic Mask);
        3b. CAPTIONS DETRÁS DE LA PERSONA (Temas 1–4): lee los bloques que GO acaba de colocar (manifiesto: estilos «guion» y «kinetic»/VIRAL),
           busca la cabeza en cada uno y, en los que se puede (persona grande y quieta, sin otro gráfico encima), sube la pila hasta la coronilla
           para que la cabeza tape la parte de abajo; la persona va recortada en la pista de MÁS ARRIBA (PRO-ENCIMA) solo en esos tramos;
        3c. B-roll de stock (Pexels, con la clave del usuario) en las palabras que nombran cosas, si los Efectos no ponen ya el suyo;
        4. deja ~/DaVinciSubtitles/edicion_pro_plan.json (+ sidecar .lua) y lo coloca DENTRO de Resolve: 2_recursos/edicion_pro/colocar_pro.py
           (Studio, por el MCP) o CineCaptions_EdicionPro.lua (Free, por el Puente).

Preferencias (archivos_seguros, vía ajustes_ui): go_edicion_pro (el interruptor de Inicio y de los Temas 1–4), pro_genero, pro_densidad,
pro_mascara ('auto' | 'magic' | 'ia' | 'no'), pro_sonidos, pro_ia_local, pro_variacion.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import edicion_pro_ograf as OG
import edicion_pro_planificador as PL

CARPETA = Path.home() / 'DaVinciSubtitles' / 'edicion_pro'
PLAN_JSON = Path.home() / 'DaVinciSubtitles' / 'edicion_pro_plan.json'
OPCIONES_POR_DEFECTO = {'pro_genero': 'auto', 'pro_densidad': 'media', 'pro_mascara': 'auto', 'pro_sonidos': True, 'pro_ia_local': True, 'pro_variacion': 0}
NOMBRES_GENERO = {'auto': 'Automático', 'general': 'General', 'inmobiliaria': 'Inmobiliaria / venta de casas', 'boda': 'Bodas', 'xv': 'XV años',
                  'restaurante': 'Restaurantes', 'bts': 'Detrás de cámara'}
SONIDOS = {'titular': ('Hit', 'Bass Hit'), 'nombres': ('Riser',), 'cifra': ('Slams', 'Hit'), 'rotulo': ('Whoosh',), 'lista': ('Whoosh',),
           'etiqueta': ('Whoosh', 'Click'), 'cta': ('Whoosh',), 'marco': ('Shutter', 'Whoosh'), 'fondo': ('Whoosh',), 'icono': ('Click', 'Hit'),
           'broll': ('Whoosh',)}
VOLUMEN_DB = -9.0
MANIFIESTO = Path.home() / 'DaVinciSubtitles' / 'subtitles_manifest.json'
DETRAS_CAPTIONS = {'sobria': 0.35, 'media': 0.55, 'espectaculo': 0.8}       # de los bloques de captions donde se puede, cuántos van DETRÁS de la persona
TRAMO_DETRAS_MAX_S = 12.0                                                    # un recorte de la persona no pasa de esto (el rastreo del Magic Mask va por tramos)


# ----------------------------------------------------------------------------------------------------------------------- preferencias
def _prefs():
    try:
        import ajustes_ui
        return ajustes_ui.leer_prefs() or {}
    except Exception:
        return {}


def activado():
    return bool(_prefs().get('go_edicion_pro', False))


def poner_activado(valor):
    import ajustes_ui
    ajustes_ui.guardar_prefs({'go_edicion_pro': bool(valor)})


def opciones_guardadas():
    p = _prefs()
    op = dict(OPCIONES_POR_DEFECTO)
    for k in op:
        if k in p:
            op[k] = p[k]
    return op


def guardar_opciones(cambios):
    import ajustes_ui
    ajustes_ui.guardar_prefs({k: v for k, v in cambios.items() if k in OPCIONES_POR_DEFECTO})


# ----------------------------------------------------------------------------------------------------------------------- plan
def medir(video):
    """(ancho, alto, duración, fps) del archivo, o Nones."""
    try:
        import av
        with av.open(str(video)) as c:
            vs = c.streams.video[0]
            dur = float(c.duration / 1e6) if c.duration else float(vs.duration * vs.time_base) if vs.duration else None
            return vs.codec_context.width, vs.codec_context.height, dur, float(vs.average_rate or 30)
    except Exception:
        return None, None, None, None


def _pesos_ia(palabras, idioma, al_estado=None):
    """Lo importante de cada palabra según la IA local (Qwen, si está instalada). Normalmente ya está en caché (la Asistencia de GO)."""
    try:
        import ia_texto
        if not ia_texto.disponible():
            return None
        if al_estado:
            al_estado('Edición PRO: la IA local elige los titulares…')
        r = ia_texto.analizar(palabras, idioma=idioma)
        return r.get('pesos') or None
    except Exception:
        return None


def planificar(video, palabras, duracion=None, cortes=None, idioma='es', opciones=None, al_estado=None):
    op = dict(OPCIONES_POR_DEFECTO, **(opciones or opciones_guardadas()))
    w, h, dur, _fps = medir(video)
    pesos = _pesos_ia(palabras, idioma, al_estado) if op.get('pro_ia_local') else None
    plan = PL.planificar(palabras, duracion or dur, idioma=idioma, genero=op.get('pro_genero') or 'auto', densidad=op.get('pro_densidad') or 'media',
                         cortes=cortes, vertical=bool(h and w and h > w), pesos=pesos, semilla=int(op.get('pro_variacion') or 0), video=Path(str(video)).name)
    plan['video'] = str(video)
    plan['opciones'] = op
    plan['ia_local'] = bool(pesos)
    plan['broll'] = _broll_de(palabras, duracion or dur, idioma, op, plan)
    if plan['broll']:
        plan['resumen'] = plan.get('resumen', '') + f", {len(plan['broll'])} tomas de B-roll"
    return plan


def _broll_de(palabras, duracion, idioma, op, plan):
    """Tomas de stock (Pexels) en las palabras que nombran cosas filmables: solo con la clave del usuario y si los Efectos no ponen ya su B-roll.
    Las que caen sobre una escena de motion graphics se descartan; lo que iba DETRÁS de la persona en una toma pasa delante (la toma la tapa)."""
    try:
        import broll
        import efectos_visuales
        ef = efectos_visuales.opciones_guardadas()
        if ef.get('fx_broll') or not broll.clave_guardada(ef) or not duracion:
            return []
        cuanto = {'sobria': 'pocos', 'media': 'normal', 'espectaculo': 'muchos'}.get(op.get('pro_densidad'), 'normal')
        momentos = broll.elegir_momentos(palabras, duracion, idioma, cuanto)
    except Exception:
        return []
    pantallas = [(p['ini'], p['fin']) for p in plan['piezas'] if p.get('pantalla')]
    momentos = [m for m in momentos if not any(m['ini'] < b + 0.3 and a - 0.3 < m['ini'] + m['dur'] for a, b in pantallas)]
    quitar = set()
    for m in momentos:
        a, b = m['ini'], m['ini'] + m['dur']
        for k, p in enumerate(plan['piezas']):
            if p['ini'] < b and a < p['fin'] and p['capa'] in ('detras', 'velo'):
                if p['capa'] == 'velo':
                    quitar.add(k)
                else:
                    p['capa'], p['persona'] = 'delante', False
    plan['piezas'] = [p for k, p in enumerate(plan['piezas']) if k not in quitar]
    return momentos


# ----------------------------------------------------------------------------------------------------------------------- Resolve
_INFO = r'''
tl = project.GetCurrentTimeline() if project else None
info = {'producto': resolve.GetProductName(), 'version': resolve.GetVersionString()}
if tl:
    info.update({'fps': float(tl.GetSetting('timelineFrameRate') or 30), 'ancho': int(tl.GetSetting('timelineResolutionWidth') or 1920),
                 'alto': int(tl.GetSetting('timelineResolutionHeight') or 1080), 'inicio': tl.GetStartFrame(), 'v1': []})
    for it in tl.GetItemListInTrack('video', 1) or []:
        mpi = it.GetMediaPoolItem()
        ruta = mpi.GetClipProperty('File Path') if mpi else ''
        try:
            fps_clip = float(mpi.GetClipProperty('FPS') or info['fps']) if mpi else info['fps']
        except Exception:
            fps_clip = info['fps']
        info['v1'].append({'ini': it.GetStart(), 'fin': it.GetEnd(), 'izq': it.GetLeftOffset(), 'ruta': ruta, 'fps': fps_clip})
    info['ocupado'] = []
    for i in range(1, int(tl.GetTrackCount('video') or 0) + 1):
        if tl.GetTrackName('video', i) == 'FX-BROLL':
            info['ocupado'] += [[x.GetStart(), x.GetEnd()] for x in tl.GetItemListInTrack('video', i) or []]
result = info
'''


def _info_timeline():
    """{'fps', 'ancho', 'alto', 'inicio', 'v1': [...], 'producto', 'via': 'mcp'|'puente'} o None."""
    try:
        import resolve_mcp
        if resolve_mcp.ruta_exe() is not None:
            ok, r, _e = resolve_mcp.script(_INFO, timeout=40)
            if ok and isinstance(r, dict) and r.get('fps'):
                r['via'] = 'mcp'
                return r
    except Exception:
        pass
    try:                                     # Free: lo que dejó el Puente al armar el timeline
        import resolve_bridge
        d = resolve_bridge.video_detectado() or {}
        if d.get('fps'):
            v1 = d.get('v1') or []
            return {'fps': float(d['fps']), 'ancho': int(d.get('ancho') or 1920), 'alto': int(d.get('alto') or 1080), 'inicio': int(d.get('inicio') or 0),
                    'v1': v1 if isinstance(v1, list) else [], 'producto': 'DaVinci Resolve', 'via': 'puente'}
    except Exception:
        pass
    return None


def _fuente_de(info, video, t):
    """(archivo, segundo del archivo, clip de V1) del instante t (segundos desde el inicio de lo transcrito)."""
    fps = float(info['fps'])
    f = int(info.get('base', info['inicio'])) + int(round(t * fps))
    for c in info.get('v1') or []:
        if c['ini'] <= f < c['fin'] and c.get('ruta'):
            fps_c = float(c.get('fps') or fps)
            return c['ruta'], int(c['izq']) / fps_c + (f - c['ini']) / fps, c          # el desfase izquierdo va en fotogramas del CLIP
    return str(video), t, None


def _ajustar_posiciones(pieza, det, vertical):
    """Mueve un gráfico «delante» para no tapar la cara, y el titular «detrás» para que la cabeza lo tape un poco."""
    v = pieza['valores']
    if not det or not det.get('personas'):
        return
    arriba = float(det['arriba']) * 100.0
    if pieza['capa'] == 'detras':
        v['y'] = round(min(48.0, max(15.0, arriba + 2.5)), 1)          # el centro del titular un poco por debajo de la coronilla: la cabeza tapa su parte de abajo
        return
    if pieza['pieza'] in ('cifra', 'rotulo', 'lista'):
        if vertical:
            y = min(float(v.get('y', 20)), arriba - 10.0)
            if y < 12.0:
                y, v['escala'] = 12.0, 0.82
            v['y'] = round(y, 1)
        else:
            centro = (float(det['izq']) + float(det['der'])) / 2.0
            v['x'] = 26 if centro >= 0.5 else 74
            v['escala'] = min(float(v.get('escala', 1)), 0.85)
    elif pieza['pieza'] == 'etiqueta' and vertical:
        v['y'] = round(max(12.0, min(float(v.get('y', 22)), arriba - 6.0)), 1)


def _comp_magic(puntos, ref, ruta, herramienta='CCProMagic'):
    """La composición del Magic Mask (MediaIn → MagicMask → MediaOut) con los puntos de cada persona en el fotograma `ref` del clip.
    `herramienta`: el nombre del MagicMask, DISTINTO en cada clip: así colocar_pro sabe que la página Fusion abrió la composición de ESE clip
    (si se queda con la del anterior, ya rastreada, el rastreo se daba por bueno y el clip quedaba sin recortar, tapando los captions)."""
    lineas = ',\n'.join('\t\t\t\t\t\t\t{ %.5f, %.5f }' % (x, y) for x, y in puntos)
    texto = '''Composition {
	CurrentTime = 0,
	Tools = ordered() {
		MediaIn1 = MediaIn { ViewInfo = OperatorInfo { Pos = { 0, 50 } }, },
		%(h)s = MagicMask {
			Inputs = {
				Mode = Input { Value = FuID { "Better" }, },
				ReferenceTime = Input { Value = %(ref)d, Disabled = true, },
				ProcessedFramesLow = Input { Value = %(ref)d, Disabled = true, },
				ProcessedFramesHigh = Input { Value = %(ref)d, Disabled = true, },
				UseLegacyMagicMask = Input { Value = 0, Disabled = true, },
				IsInitialNotify = Input { Value = 0, },
				IsRefineFrame = Input { Value = 1, },
				Strokes = Input { SourceOp = "%(h)sStrokes", Source = "Value", },
				Input = Input { SourceOp = "MediaIn1", Source = "Output", },
			},
			ViewInfo = OperatorInfo { Pos = { 110, 50 } },
		},
		%(h)sStrokes = BezierSpline {
			SplineColor = { Red = 242, Green = 186, Blue = 59 },
			NameSet = true,
			KeyFrames = {
				[%(ref)d] = { 0, Flags = { Linear = true, LockedY = true }, Value = MagicMaskStrokes {
						PosStrokes = {
%(lineas)s
						}
					} }
			}
		},
		MediaOut1 = MediaOut {
			Inputs = {
				Index = Input { Value = "0", },
				Input = Input { SourceOp = "%(h)s", Source = "Output", },
			},
			ViewInfo = OperatorInfo { Pos = { 220, 50 } },
		},
	},
}
''' % {'ref': int(ref), 'lineas': lineas, 'h': herramienta}
    Path(ruta).write_text(texto, encoding='utf-8')
    return Path(ruta)


def _bloques_captions():
    """Los bloques de captions de los Temas 1–4 que GO acaba de colocar (estilos «guion» y «kinetic»/VIRAL del manifiesto, del idioma base):
    [{'ini', 'fin' (s), 'arriba', 'abajo' (la caja de la pila, fracción del alto desde ARRIBA), 'linea' (alto de su línea de abajo),
      'xs': centros de sus palabras (fracción del ancho)}]."""
    try:
        m = json.loads(MANIFIESTO.read_text(encoding='utf-8'))
    except Exception:
        return []
    pistas = [t for t in m.get('tracks') or [] if t.get('style') in ('guion', 'kinetic') and t.get('data_path')]
    if not pistas:
        return []
    idioma = pistas[0].get('language')
    out = []
    for t in pistas:
        if t.get('language') != idioma:
            continue
        try:
            cues = json.loads(Path(t['data_path']).read_text(encoding='utf-8')).get('cues') or []
        except Exception:
            continue
        for c in cues:
            runs = [r for r in c.get('runs') or [] if isinstance(r, dict)]
            ys = [float(r['y']) for r in runs if isinstance(r.get('y'), (int, float)) and 0 <= r['y'] <= 1]
            xs = [float(r['x']) for r in runs if isinstance(r.get('x'), (int, float)) and 0 <= r['x'] <= 1]
            caja = c.get('caja')
            try:
                if isinstance(caja, (list, tuple)) and len(caja) == 2:
                    arriba, abajo = float(caja[0]), float(caja[1])
                elif ys:
                    arriba, abajo = min(ys) - 0.03, max(ys) + 0.03
                else:
                    continue
                ini, fin = float(c['start']), float(c['end'])
            except (KeyError, TypeError, ValueError):
                continue
            fin = max([fin] + [float(r['fin']) for r in runs if isinstance(r.get('fin'), (int, float))])
            if fin - ini >= 0.5 and 0 <= arriba < abajo <= 1:
                linea = 2.0 * (abajo - max(ys)) if ys and max(ys) < abajo else abajo - arriba     # el alto de la línea de ABAJO (la que tapa la cabeza)
                out.append({'ini': ini, 'fin': fin, 'arriba': arriba, 'abajo': abajo, 'linea': max(0.02, linea), 'xs': xs or [0.5]})
    out.sort(key=lambda b: b['ini'])
    return out


def _cabeza(det):
    """(coronilla, x de la cabeza, alto de la persona, alto de la cabeza) de la persona más grande del fotograma (fracciones, y desde ARRIBA), o None."""
    ps = (det or {}).get('personas') or []
    if not ps:
        return None
    p = max(ps, key=lambda q: q['area'])
    x0, y0, x1, y1 = p['bbox']
    cab = (p.get('cabeza') or {}).get('alto') or 0.18 * (y1 - y0)
    return y0, (p['puntos'][0][0] if p.get('puntos') else (x0 + x1) / 2.0), y1 - y0, cab


def _captions_detras(info, video, fps, ocupado, densidad, decir):
    """Qué bloques de captions van DETRÁS de la persona y cuánto suben. Un bloque vale si la persona es grande, su cabeza no se sale por arriba,
    está quieta en todo el bloque (misma toma), la pila le cae encima en horizontal y no hay otro gráfico ni B-roll en ese momento. La pila sube (o
    baja) hasta que su borde de abajo queda un poco por debajo de la coronilla: la cabeza tapa la parte de abajo de la palabra grande y el resto se lee.
    El primero que vale entra siempre (el gancho) y luego se alternan (`DETRAS_CAPTIONS`): el contraste también retiene.
    Devuelve los tramos [{'ini', 'fin' (s), 'det', 't_det', 'cues': [{'ini', 'fin', 'subir' (fracción del alto, + = arriba)}]}]."""
    bloques = _bloques_captions()
    if not bloques:
        return []
    import edicion_pro_persona as PE
    decir('Edición PRO: buscando dónde los captions van detrás de la persona…')
    frac = DETRAS_CAPTIONS.get(densidad, 0.55)
    elegidos, acum = [], 1.0 - frac
    for k, b in enumerate(bloques):
        a, z = b['ini'], b['fin']
        if any(a < o1 and o0 < z for o0, o1 in ocupado):
            continue
        acum += frac
        if acum < 0.999:
            continue
        r0, t0, c0 = _fuente_de(info, video, a + 0.12)
        r1, t1, c1 = _fuente_de(info, video, max(a + 0.12, z - 0.15))
        if c0 is not c1:
            continue                                                  # cruza un corte de V1: el recorte no seguiría a la persona
        try:
            d0 = PE.personas(r0, t0)
            h0, h1 = _cabeza(d0), _cabeza(PE.personas(r1, t1))
        except Exception:
            continue
        if not h0 or not h1 or abs(h0[0] - h1[0]) > 0.05 or abs(h0[1] - h1[1]) > 0.08:
            continue
        coronilla, cab_x, alto_p, cab = (h0[0] + h1[0]) / 2.0, (h0[1] + h1[1]) / 2.0, min(h0[2], h1[2]), min(h0[3], h1[3])
        if coronilla < 0.08 or coronilla > 0.62 or alto_p < 0.3:
            continue
        if not (min(b['xs']) - 0.16 <= cab_x <= max(b['xs']) + 0.16):
            continue
        # cuánto de la pila tapa la cabeza: hasta la frente (~40 % de la cabeza), sin pasar del 45 % de la línea de abajo (la palabra se sigue
        # leyendo); en un plano entero (cabeza pequeña) tapa poco y en un primer plano mucho más
        tapa = max(0.012, min(0.055, 0.4 * cab, 0.45 * b['linea']))
        dy = coronilla + tapa - b['abajo']
        if b['arriba'] + dy < 0.06:
            dy = 0.06 - b['arriba']
        if b['abajo'] + dy < coronilla + 0.012 or b['abajo'] + dy > 0.9:
            continue
        acum -= 1.0
        elegidos.append(dict(b, k=k, subir=-dy, clip=c0, det=d0, t_det=a + 0.12))
    # los bloques seguidos (de la misma toma) comparten un solo recorte de la persona: menos rastreos de Magic Mask
    tramos = []
    for e in elegidos:
        k = e['k']
        sig = bloques[k + 1]['ini'] if k + 1 < len(bloques) else e['fin'] + 0.3
        fin = max(e['ini'] + 0.3, min(e['fin'] + 0.2, sig))           # sin tapar el bloque siguiente (ese va normal, delante)
        cue = {'ini': e['ini'], 'fin': e['fin'], 'subir': round(e['subir'], 4)}
        t = tramos[-1] if tramos else None
        if t and t['k'] == k - 1 and t['clip'] is e['clip'] and fin - t['ini'] <= TRAMO_DETRAS_MAX_S:
            t.update(fin=fin, k=k)
            t['cues'].append(cue)
            continue
        ini = e['ini']
        if k > 0 and bloques[k - 1]['fin'] > ini:
            ini = min(bloques[k - 1]['fin'], fin - 0.3)               # el bloque anterior aún sale: la persona entra cuando se va
        tramos.append({'ini': ini, 'fin': fin, 'k': k, 'clip': e['clip'], 'det': e['det'], 't_det': e['t_det'], 'cues': [cue]})
    return tramos


def _sonidos_de(plan, fps, rng):
    """Un sonido de entrada por gráfico, de la biblioteca de CineCaptions (2_recursos/sfx_library), a −9 dB."""
    try:
        from sfx_rules import base_recursos
        lib = Path(base_recursos()) / 'sfx_library'
    except Exception:
        lib = Path(__file__).resolve().parent.parent / '2_recursos' / 'sfx_library'
    out = []
    for p in plan['piezas'] + [{'pieza': 'broll', 'ini': m['ini']} for m in plan.get('_broll_puesto') or []]:
        cats = SONIDOS.get(p['pieza'])
        if not cats:
            continue
        cat = lib / rng.choice(cats)
        archivos = sorted(x for x in cat.glob('*') if x.suffix.lower() in ('.wav', '.mp3')) if cat.is_dir() else []
        if not archivos:
            continue
        a = rng.choice(archivos)
        out.append({'ini': int(round(max(0.0, p['ini'] + 0.05) * fps)), 'archivo': str(OG.ruta_larga(a)), 'dur': 1.4, 'db': VOLUMEN_DB})
    return out


def aplicar(plan, al_estado=None, offset_frames=0, info=None):
    """Pone la Edición PRO en el timeline actual. Devuelve (ok, mensaje)."""
    decir = al_estado or (lambda t: None)
    if not plan or not plan.get('piezas'):
        return True, ''
    info = info or _info_timeline()
    if not info:
        return False, 'No pude leer el timeline de Resolve (¿está abierto, con el video en V1?)'
    fps, W, H = float(info['fps']), int(info['ancho']), int(info['alto'])
    info['base'] = int(info['inicio']) + int(offset_frames or 0)
    vertical = H > W
    studio = 'studio' in str(info.get('producto') or '').lower() and info.get('via') == 'mcp'
    op = plan.get('opciones') or opciones_guardadas()
    modo_mascara = op.get('pro_mascara') or 'auto'
    usar_magic = studio and modo_mascara in ('auto', 'magic')
    usar_ia = modo_mascara in ('auto', 'ia') or (modo_mascara == 'magic' and not studio)
    video = plan.get('video') or ''
    clave = hashlib.sha1(f'{video}|{W}x{H}@{fps}'.encode('utf-8')).hexdigest()[:10]
    carpeta = OG.ruta_larga(CARPETA / clave)
    carpeta.mkdir(parents=True, exist_ok=True)
    import edicion_pro_persona as PE
    hay_ia = PE.disponible()
    graficos, persona = [], []
    ventanas = {}
    decir('Edición PRO: buscando a las personas del video…')
    for p in plan['piezas']:
        det = None
        if hay_ia and (p.get('ajustar') or p.get('persona')):
            ruta, t_src, _c = _fuente_de(info, video, (p['ini'] + p['fin']) / 2.0)
            try:
                det = PE.personas(ruta, t_src)
            except Exception:
                det = None
        if p.get('ajustar'):
            _ajustar_posiciones(p, det, vertical)
        if p.get('persona') and p['capa'] in ('detras', 'velo'):
            k = (p['ini'], p['fin'])
            if k not in ventanas:
                ventanas[k] = det
    # la persona de cada ventana (si no hay nadie, el titular queda delante y sin velo)
    sin_persona = set()
    for (a, b), det in ventanas.items():
        f0, f1 = int(round(a * fps)), int(round(b * fps))
        if not hay_ia or not det or not det.get('personas') or modo_mascara == 'no':
            sin_persona.add((a, b))
            continue
        ruta, t_src, clip = _fuente_de(info, video, a)
        _r2, _t2, clip2 = _fuente_de(info, video, max(a, b - 1.0 / fps))
        if clip is not None and clip2 is not None and clip is not clip2:
            sin_persona.add((a, b))                                   # cruza un corte de V1 (pausas quitadas): el recorte no seguiría a la persona
            continue
        ref = int(round(((a + b) / 2.0 - a) * fps))
        if usar_magic:
            puntos = PE.puntos_fusion(det)
            comp = _comp_magic(puntos, ref, carpeta / f'magic_{f0}_{f1}.comp', f'CCProMagic{f0}')
            persona.append({'ini': f0, 'fin': f1, 'modo': 'magic', 'comp': str(OG.ruta_larga(comp)), 'ref': ref, 'herramienta': f'CCProMagic{f0}'})
        elif usar_ia:
            decir('Edición PRO: recortando a la persona con IA local…')
            destino = carpeta / f'persona_{f0}_{f1}.mov'
            try:
                if not destino.exists():
                    PE.recorte_prores(ruta, t_src, t_src + (b - a), destino)
                persona.append({'ini': f0, 'fin': f1, 'modo': 'clip', 'archivo': str(OG.ruta_larga(destino))})
            except Exception:
                sin_persona.add((a, b))
        else:
            sin_persona.add((a, b))
    # B-roll de stock (se descarga ahora: tras los captions, así GO no espera la red antes)
    tomas = []
    if plan.get('broll'):
        try:
            import broll
            import efectos_visuales
            clave = broll.clave_guardada(efectos_visuales.opciones_guardadas())
            decir('Edición PRO: buscando las tomas de B-roll…')
            for ev in broll.preparar(plan['broll'], 'v' if vertical else 'h', clave, decir):
                tomas.append({'ini': int(round(float(ev['ini']) * fps)), 'dur': float(ev['dur']), 'archivo': str(OG.ruta_larga(ev['archivo'])),
                              'palabra': ev.get('palabra', ''), '_s': float(ev['ini'])})
        except Exception:
            tomas = []
    plan['_broll_puesto'] = [{'ini': t['_s']} for t in tomas]
    # captions DETRÁS de la persona (lo que hace que valga la pena el Magic Mask)
    encima = []
    if hay_ia and modo_mascara != 'no':
        ocupado = [(p['ini'] - 0.1, p['fin'] + 0.1) for p in plan['piezas'] if p['pieza'] != 'marco']
        ocupado += [(t['_s'] - 0.1, t['_s'] + t['dur'] + 0.1) for t in tomas]
        ocupado += [((a - info['base']) / fps, (b - info['base']) / fps) for a, b in info.get('ocupado') or []]
        try:
            tramos = _captions_detras(info, video, fps, ocupado, op.get('pro_densidad') or 'media', decir)
        except Exception:
            tramos = []
        d = plan.get('direccion') or {}
        for t in tramos:
            f0, f1 = int(round(t['ini'] * fps)), int(round(t['fin'] * fps))
            ref = max(0, min(f1 - f0 - 1, int(round((t['t_det'] - t['ini']) * fps))))
            e = {'ini': f0, 'fin': f1, 'ref': ref, 'cues': [{'ini': int(round(c['ini'] * fps)), 'fin': int(round(c['fin'] * fps)),
                                                            'subir': round(c['subir'] * H, 1)} for c in t['cues']]}
            if usar_magic:
                comp = _comp_magic(PE.puntos_fusion(t['det']), ref, carpeta / f'encima_{f0}_{f1}.comp', f'CCProMagicE{f0}')
                e.update(modo='magic', comp=str(OG.ruta_larga(comp)), herramienta=f'CCProMagicE{f0}')
            elif usar_ia:
                decir('Edición PRO: recortando a la persona con IA local…')
                ruta, t_src, _c = _fuente_de(info, video, t['ini'])
                destino = carpeta / f'encima_{f0}_{f1}.mov'
                try:
                    if not destino.exists():
                        PE.recorte_prores(ruta, t_src, t_src + (t['fin'] - t['ini']), destino)
                    e.update(modo='clip', archivo=str(OG.ruta_larga(destino)))
                except Exception:
                    continue
            else:
                continue
            try:                                                      # un velo suave detrás de los captions: el fondo baja y la persona (encima) sale
                e['velo'] = str(OG.construir('velo', {'forma': d.get('velo') or 'arriba', 'color': '#000000', 'intensidad': 0.32, 'fundido': 0.3},
                                             max(0.4, t['fin'] - t['ini']), carpeta, fps=fps, ancho=W, alto=H))
            except Exception:
                pass
            encima.append(e)
    decir('Edición PRO: preparando los gráficos animados…')
    for p in plan['piezas']:
        capa = p['capa']
        if (p['ini'], p['fin']) in sin_persona:
            if capa == 'velo':
                continue                                              # sin la persona delante, el velo solo oscurecería
            if capa == 'detras':
                capa = 'delante'
        dur = max(0.4, p['fin'] - p['ini'])
        ruta = OG.construir(p['pieza'], p['valores'], dur, carpeta, fps=fps, ancho=W, alto=H)
        graficos.append({'capa': capa, 'ini': int(round(p['ini'] * fps)), 'archivo': str(ruta), 'nombre': f"PRO · {OG.ESQUEMAS[p['pieza']]['nombre']}"})
    rng = random.Random(PL.semilla_de(video, [], int(op.get('pro_variacion') or 0)))
    sonidos = _sonidos_de(plan, fps, rng) if op.get('pro_sonidos', True) else []
    datos = {'fps': fps, 'inicio': info['base'], 'graficos': graficos, 'persona': persona, 'sonidos': sonidos, 'cache': True,
             'broll': [{k: v for k, v in t.items() if k != '_s'} for t in tomas], 'encima': encima, 'resumen': plan.get('resumen', '')}
    try:
        import archivos_seguros
        archivos_seguros.escribir_json(PLAN_JSON, datos, indent=1)
    except Exception:
        PLAN_JSON.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding='utf-8')
    try:
        import sidecar_lua
        sidecar_lua.escribir_sidecar(PLAN_JSON, datos)
    except Exception:
        pass
    instalar_plantillas_una_vez()
    limpiar_cache()
    decir('Edición PRO: colocando la edición en Resolve' + (' (Magic Mask)…' if (persona or encima) and usar_magic else '…'))
    if info.get('via') == 'mcp':
        import resolve_mcp
        script = carpeta_recursos() / 'colocar_pro.py'
        ok, mensaje = resolve_mcp.ejecutar_py(script, timeout=600)
    else:
        import resolve_bridge
        if resolve_bridge.modo_actual() == 'manual' and not resolve_bridge.lanzar_puente_auto():
            return False, 'La Edición PRO en Resolve Free necesita el Puente de CineCaptions abierto en Resolve.'
        ok, mensaje = resolve_bridge.ejecutar('edicion_pro', timeout=600)
    return ok, mensaje or plan.get('resumen', '')


def instalar_plantillas_una_vez():
    """Las 9 piezas en la caja de herramientas de Resolve («CineCaptions PRO», para ponerlas a mano), una vez por versión de las piezas."""
    marca = CARPETA / f'.plantillas_{OG.VERSION_PIEZAS}'
    if marca.exists():
        return
    if OG.instalar_plantillas() is not None:
        try:
            CARPETA.mkdir(parents=True, exist_ok=True)
            marca.write_text('ok', encoding='utf-8')
        except OSError:
            pass


def carpeta_recursos() -> Path:
    try:
        from sfx_rules import base_recursos
        return Path(base_recursos()) / 'edicion_pro'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'edicion_pro'


def limpiar_cache(maximo_mb=1500):
    """Borra lo más viejo de ~/DaVinciSubtitles/edicion_pro si pasa de `maximo_mb` (los .ograf y los recortes se rehacen solos)."""
    try:
        cajas = sorted((d for d in CARPETA.iterdir() if d.is_dir() and d.name not in ('modelos', 'pruebas')), key=lambda d: d.stat().st_mtime)
        total = sum(f.stat().st_size for d in cajas for f in d.rglob('*') if f.is_file())
        while cajas and total > maximo_mb * 1e6:
            d = cajas.pop(0)
            tam = sum(f.stat().st_size for f in d.rglob('*') if f.is_file())
            import shutil
            shutil.rmtree(d, ignore_errors=True)
            total -= tam
    except Exception:
        pass
