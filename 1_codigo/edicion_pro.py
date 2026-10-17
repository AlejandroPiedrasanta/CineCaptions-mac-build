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
import shutil
import random
import os
import threading
from pathlib import Path

import edicion_pro_ograf as OG
import edicion_pro_planificador as PL

CARPETA = Path.home() / 'DaVinciSubtitles' / 'edicion_pro'
PLAN_JSON = Path.home() / 'DaVinciSubtitles' / 'edicion_pro_plan.json'
OPCIONES_POR_DEFECTO = {'pro_genero': 'auto', 'pro_densidad': 'media', 'pro_mascara': 'auto', 'pro_sonidos': True, 'pro_ia_local': True, 'pro_variacion': 0,
                        'pro_internet': True,          # v5.5.3: fotos de internet con licencia (fuentes_web) para las escenas
                        'pro_motions_completo': False,  # v5.5.8: «Motions completo» (motions_completo.py): un video de motions encima de todo, al final
                        'pro_motions_modo': 'auto', 'pro_motions': [],     # v5.5.7: 'auto' (la IA elige entre todos) o 'elegidos' (solo los de la lista)
                        'pro_sonidos_nivel': 'normal',  # v5.5.7 (página Sonido › Edición PRO): 'suave' | 'normal' | 'fuerte'
                        'pro_sonidos_familias': {'whoosh': True, 'textura': True, 'riser': True},   # movimiento · apariciones · riser + golpe
                        # v5.5.8: Temas 5 y 6 con captions de Fusion EDITABLES (Inspector › texto) en vez de las animaciones de Remotion
                        'pro_captions_editables': True,
                        # v5.5.8: en Studio, el gancho del principio (captions detrás de la persona) con Magic Mask aunque el modo sea «auto»
                        'pro_magic_gancho': True}
NIVEL_SONIDOS_DB = {'suave': -5.0, 'normal': 0.0, 'fuerte': 3.0}
FAMILIA_DE_PISTA = {'PRO-WHOOSH': 'whoosh', 'PRO-TEXTURA': 'textura', 'PRO-RISER': 'riser', 'PRO-HIT': 'riser'}
NOMBRES_GENERO = {'auto': 'Automático', 'general': 'General', 'inmobiliaria': 'Inmobiliaria / venta de casas', 'boda': 'Bodas', 'xv': 'XV años',
                  'restaurante': 'Restaurantes', 'bts': 'Detrás de cámara'}
MANIFIESTO = Path.home() / 'DaVinciSubtitles' / 'subtitles_manifest.json'
DETRAS_CAPTIONS = {'sobria': 0.35, 'media': 0.55, 'espectaculo': 0.8}       # de los bloques de captions donde se puede, cuántos van DETRÁS de la persona
TRAMO_DETRAS_MAX_S = 12.0                                                    # un recorte de la persona no pasa de esto (el rastreo del Magic Mask va por tramos)
PUNCH_IN = 1.08                                                              # el «punch-in» que alterna en cada salto de V1 (pausas quitadas), como en la skill
MARGEN_RECORTE_S = 0.8
ICONO3D_CADA = {'sobria': 6.0, 'media': 3.5, 'espectaculo': 2.4}            # segundos mínimos entre dos iconos 3D junto a los captions


# ----------------------------------------------------------------------------------------------------------------------- preferencias
def _prefs():
    try:
        import ajustes_ui
        return ajustes_ui.leer_prefs() or {}
    except Exception:
        return {}


def activado():
    return bool(_prefs().get('go_edicion_pro', False))


TEMAS_PRO = ('Tema5', 'Tema6')            # edicion_pro_tema5.activo: estos temas SON la Edición PRO completa, aunque su interruptor esté apagado


def tema_actual():
    """El tema elegido en el chip «Estilo» de Inicio (preferencia go_pack), o ''."""
    return str(_prefs().get('go_pack') or '')


def en_juego():
    """v5.5.7: ¿la PRO actúa en el próximo GO? Su interruptor, o el tema elegido es el 5 o el 6 (la usan siempre). Las páginas Efectos y Sonido lo
    miran para decir la verdad sobre lo que se aplica (antes, con el Tema 5 y el interruptor apagado, decían «PRO apagada»)."""
    return activado() or tema_actual() in TEMAS_PRO


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
            import rotacion_video as RV                                   # v5.5.8: como lo ve Resolve (videos del celular giran 90°)
            w, h = RV.medidas(vs.codec_context.width, vs.codec_context.height, RV.giro(video))
            return w, h, dur, float(vs.average_rate or 30)
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
                         cortes=cortes, vertical=bool(h and w and h > w), pesos=pesos, semilla=int(op.get('pro_variacion') or 0), video=str(video))   # v5.5.3: la RUTA (colores y fotogramas del video para el kit y las escenas)
    plan['video'] = str(video)
    plan['opciones'] = op
    plan['idioma'] = idioma
    plan['ia_local'] = bool(pesos)
    try:                                             # v5.5.7: solo los motions que el usuario permitió (el seguro final; la IA y las reglas ya no los proponen)
        import motions_catalogo as MC
        plan['piezas'] = MC.filtrar(plan.get('piezas') or [], op)
    except Exception:
        pass
    plan['broll'] = _broll_de(palabras, duracion or dur, idioma, op, plan)
    _referencias(plan)
    soltar_gpu()                                     # v5.5.4: la IA ya eligió: su VRAM, para Resolve (que en ese momento está armando el timeline)
    if plan['broll']:
        plan['resumen'] = plan.get('resumen', '') + f", {len(plan['broll'])} tomas de B-roll"
    return plan


def soltar_gpu(voz=True, texto=True):
    """v5.5.4: descarga las IA locales (voz ~6 GB, texto 4–9,5 GB de VRAM) para que Resolve tenga la GPU entera: con ellas cargadas Resolve
    reproducía a tirones, el Magic Mask iba lento y llegó a cerrarse (16 GB no dan para las tres cosas). Se vuelven a cargar solas si hacen falta."""
    try:
        if voz:
            import motor_voz
            motor_voz.liberar()
        if texto:
            import ia_texto
            ia_texto.liberar()
    except Exception:
        pass


def _referencias(plan):
    """v5.5.3: los enlaces para buscar REFERENCIAS del tema del video en Google Imágenes y Pinterest, en el Registro (los abre el usuario, para
    inspirarse: el programa nunca baja de ahí, esas imágenes tienen derechos; las del video salen de bancos con licencia, fuentes_web)."""
    try:
        import urllib.parse
        import registro
        pf = plan.get('perfil') or {}
        tema = ' '.join(str(pf.get('subtema') or pf.get('categoria') or '').split())[:60]
        if not tema:
            return
        q = urllib.parse.quote(tema)
        registro.info(f'Referencias de «{tema}» para inspirarte: Google Imágenes https://www.google.com/search?tbm=isch&q={q} · '
                      f'Pinterest https://www.pinterest.com/search/pins/?q={q}', 'edición PRO')
    except Exception:
        pass


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
        c = {'ini': it.GetStart(), 'fin': it.GetEnd(), 'izq': it.GetLeftOffset(), 'ruta': ruta, 'fps': fps_clip,
             'res': (mpi.GetClipProperty('Resolution') or '') if mpi else '', 'fx': 'CineCaptions FX' in (it.GetFusionCompNameList() or [])}
        for k, n in (('zx', 'ZoomX'), ('zy', 'ZoomY'), ('pan', 'Pan'), ('tilt', 'Tilt')):
            try:
                c[k] = float(it.GetProperty(n))
            except Exception:
                c[k] = 1.0 if k in ('zx', 'zy') else 0.0
        info['v1'].append(c)
    info['sfx'] = []
    for i in range(1, int(tl.GetTrackCount('audio') or 0) + 1):
        n = str(tl.GetTrackName('audio', i) or '')
        if n.upper().startswith('SFX') or n == 'FX-SONIDO':
            info['sfx'] += [x.GetStart() for x in tl.GetItemListInTrack('audio', i) or []]
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


def _a_timeline(det, clip, W, H):
    """La detección (fracciones de la FUENTE) en fracciones del TIMELINE para ese clip de V1: GO lo pone «ajustado» (un horizontal en un timeline
    vertical queda con bandas), y encima van su zoom (el punch-in), Pan y Tilt. Los puntos del Magic Mask NO pasan por aquí (van en la fuente)."""
    if not det or not det.get('personas') or not clip:
        return det
    try:
        w, h = (int(x) for x in str(clip.get('res') or '').lower().replace(' ', '').split('x')[:2])
    except (TypeError, ValueError):
        w, h = W, H
    if w <= 0 or h <= 0:
        w, h = W, H
    s = min(W / float(w), H / float(h))
    sx, sy = w * s / W, h * s / H
    zx, zy = float(clip.get('zx') or 1.0), float(clip.get('zy') or 1.0)
    pan, tilt = float(clip.get('pan') or 0.0), float(clip.get('tilt') or 0.0)

    def fx(x):
        return 0.5 + (0.5 - sx / 2 + x * sx - 0.5) * zx + pan / W

    def fy(y):
        return 0.5 + (0.5 - sy / 2 + y * sy - 0.5) * zy - tilt / H
    ps = []
    for q in det['personas']:
        x0, y0, x1, y1 = q['bbox']
        n = dict(q, bbox=(fx(x0), fy(y0), fx(x1), fy(y1)), puntos=[(fx(x), fy(y)) for x, y in q.get('puntos') or []])
        if q.get('cabeza'):
            n['cabeza'] = {'alto': q['cabeza'].get('alto', 0) * sy * zy, 'ancho': q['cabeza'].get('ancho', 0) * sx * zx}
        ps.append(n)
    return {'personas': ps, 'arriba': min(q['bbox'][1] for q in ps), 'abajo': max(q['bbox'][3] for q in ps),
            'izq': min(q['bbox'][0] for q in ps), 'der': max(q['bbox'][2] for q in ps)}


ALTO_PIEZA = {'cifra': 0.17, 'rotulo': 0.12, 'lista': 0.25, 'etiqueta': 0.08, 'cta': 0.30, 'icono': 0.29, 'titular': 0.15, 'nombres': 0.17}
MARGEN_CARA = 0.02                       # aire entre la cara y cualquier cosa (fracción del alto)


def _caras(det):
    """Las cajas de las CARAS (fracciones del timeline, y desde arriba): de la coronilla a la barbilla y del ancho de la cabeza, con margen.
    Regla del usuario: NADA las tapa (ni gráficos, ni emojis, ni captions)."""
    out = []
    for q in (det or {}).get('personas') or []:
        x0, y0, x1, y1 = q['bbox']
        cab = (q.get('cabeza') or {}).get('alto') or 0.2 * (y1 - y0)
        ancho = (q.get('cabeza') or {}).get('ancho') or min(x1 - x0, cab * 0.9)
        cx = q['puntos'][0][0] if q.get('puntos') else (x0 + x1) / 2.0
        out.append((max(0.0, cx - 0.62 * ancho), max(0.0, y0 - 0.01), min(1.0, cx + 0.62 * ancho), min(1.0, y0 + 1.12 * cab)))
    return out


def _fuera_de_la_cara(y, medio, caras, x0=0.0, x1=1.0):
    """El centro y (fracción) más cercano a `y` para algo de media altura `medio` (y ancho [x0, x1]) que no pise ninguna cara, o None si no cabe."""
    malas = [c for c in caras if c[0] < x1 and x0 < c[2]]
    if not malas:
        return y

    def libre(yy):
        return 0.04 + medio <= yy <= 0.96 - medio and all(yy + medio + MARGEN_CARA <= c[1] or yy - medio - MARGEN_CARA >= c[3] for c in malas)
    if libre(y):
        return y
    opciones = [c[1] - MARGEN_CARA - medio for c in malas] + [c[3] + MARGEN_CARA + medio for c in malas]
    opciones = [o for o in opciones if libre(o)]
    return min(opciones, key=lambda o: abs(o - y)) if opciones else None


MARGEN_EMOJI = 0.07                      # el emoji de un caption de los Temas 1–4 va justo encima o debajo de su pila (fracción del alto)


def _caja_vertical(pieza):
    """(arriba, abajo) en fracción del alto de una pieza ya colocada (su centro `y` y su alto por la escala), o None si no se sabe."""
    v = pieza.get('valores') or {}
    alto = pieza.get('alto') or ALTO_PIEZA.get(pieza['pieza'])
    if not alto and pieza.get('remotion'):
        import edicion_pro_catalogo as PC
        alto = PC.ALTO.get(pieza['remotion'])
    if not alto or pieza.get('pantalla') or v.get('y') is None:
        return None
    y, medio = float(v['y']) / 100.0, float(alto) * float(v.get('escala', 1) or 1) / 2.0
    return (max(0.0, y - medio), min(1.0, y + medio))


def _obstaculos(pieza, bloques_cap, puestos):
    """v5.5.2 (regla oficial): las cajas que una pieza de delante NO puede pisar en su tramo: los captions de los Temas 1–4 (con el sitio de su emoji)
    y lo ya colocado delante a la vez (los captions de la PRO de los Temas 5/6 y los demás gráficos). Cajas a todo el ancho: (x0, y0, x1, y1)."""
    a, b = pieza['ini'], pieza['fin']
    out = [(0.0, max(0.0, c['arriba'] - MARGEN_EMOJI), 1.0, min(1.0, c['abajo'] + MARGEN_EMOJI)) for c in bloques_cap or [] if c['ini'] < b and a < c['fin']]
    out += [(0.0, max(0.0, y0 - 0.01), 1.0, min(1.0, y1 + 0.01)) for (i, f, y0, y1) in puestos if i < b and a < f]
    return out


def _ajustar_posiciones(pieza, det, vertical, extra=()):
    """Coloca cada gráfico SIN TAPAR NINGUNA CARA: los de delante, encima o debajo de la cara (o a un lado en horizontal, o más pequeños); el titular
    «detrás» un poco por debajo de la coronilla (la cabeza lo tapa a él, no al revés); la infografía de una escena con «fondo sustituido»,
    detrás de la persona y encima de su cabeza (si no cabe, la escena va a pantalla completa); la órbita, con la mitad de delante por el pecho.
    `det` ya en fracciones del timeline. `extra`: otras cajas que tampoco se pisan (v5.5.2: los captions, para las piezas del kit de la skill)."""
    v = pieza['valores']
    if not det or not det.get('personas'):
        if not extra or not vertical:
            return
        det = {'personas': [], 'arriba': 1.0}
    arriba = float(det['arriba']) * 100.0
    caras = _caras(det) + [tuple(c) for c in extra]
    if pieza['pieza'] == 'orbita':                                    # centrada en el cuello: atrás pasa por detrás de la cabeza, delante por el pecho
        y0, cab_x, _alto, cab = _cabeza(det)
        ancho = max((q.get('cabeza') or {}).get('ancho', 0) for q in det['personas']) or cab * 0.6
        k = max(0.85, min(1.3, cab / 0.12))
        v['escala'] = round(k, 2)
        tres_d = len([x for x in str(v.get('imagenes') or '').split(',') if x.strip()]) >= 3
        medio = (99.0 if tres_d else 58.0) * k / (1920.0 if vertical else 1080.0)   # media altura del icono de delante (px de U=1 → fracción del alto)
        cy = y0 + 0.85 * cab
        ry = (y0 + 1.12 * cab + MARGEN_CARA) + medio - cy              # lo de delante pasa ENTERO por debajo de la barbilla
        v['x'], v['y'] = round(cab_x * 100, 2), round(cy * 100, 2)
        v['rx'] = round(max(18.0, min(42.0, 240.0 * ancho)), 2)
        v['ry'] = round(max(2.0, min(18.0, ry * 100)), 2)
        v['inclinacion'] = round(max(-5.0, min(5.0, float(v.get('inclinacion', 0)))), 1)
        return
    if pieza['capa'] == 'detras' and pieza['pieza'] in ('icono', 'cifra', 'lista'):
        if vertical:
            if arriba < 24.0:                                         # primer plano: no hay sitio encima de la cabeza
                pieza['forzar_pantalla'] = True
                return
            v['y'] = round(max(13.0, arriba - 11.0), 1)
            v['escala'] = round(min(float(v.get('escala', 1)), 0.78 if arriba < 32 else 0.92), 2)
        else:
            centro = (float(det['izq']) + float(det['der'])) / 2.0
            v['x'], v['y'] = (27 if centro >= 0.5 else 73), 45
            v['escala'] = round(min(float(v.get('escala', 1)), 0.85), 2)
        return
    if pieza['capa'] == 'detras':
        v['y'] = round(min(48.0, max(15.0, arriba + 2.5)), 1)          # el centro del titular un poco por debajo de la coronilla: la cabeza tapa su parte de abajo
        return
    alto = pieza.get('alto') or ALTO_PIEZA.get(pieza['pieza'])         # (las tarjetas del Tema 5 traen su alto: depende de lo que enseñan)
    if pieza.get('remotion') and not alto:                            # plantillas Remotion: su alto está en el catálogo
        import edicion_pro_catalogo as PC
        alto = PC.ALTO.get(pieza['remotion'])
    if not alto or pieza.get('pantalla'):
        return
    if not vertical:                                                  # horizontal: al lado contrario de la persona
        centro = (float(det['izq']) + float(det['der'])) / 2.0
        if pieza['pieza'] not in ('etiqueta',):
            v['x'] = 26 if centro >= 0.5 else 74
            v['escala'] = round(min(float(v.get('escala', 1)), 0.85), 2)
        x = float(v.get('x', 50)) / 100.0
        medio_x = 0.22 * float(v.get('escala', 1))
        y = _fuera_de_la_cara(float(v.get('y', 50)) / 100.0, alto * float(v.get('escala', 1)) / 2.0, caras, x - medio_x, x + medio_x)
        if y is not None:
            v['y'] = round(y * 100, 1)
        return
    for k in (1.0, 0.85, 0.7, 0.58):                                  # vertical: encima o debajo de la cara; si no cabe, más pequeño
        esc = round(min(float(pieza['_valores0'].get('escala', 1)) if pieza.get('_valores0') else float(v.get('escala', 1)), 1.0) * k, 2)
        y = _fuera_de_la_cara(float(v.get('y', 50)) / 100.0, alto * esc / 2.0, caras)
        if y is not None:
            v['y'], v['escala'] = round(y * 100, 1), esc
            return
    pieza['quitar'] = True                                            # no cabe en ningún sitio sin tapar la cara: mejor sin él


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
				CorrectEdges = Input { Value = 1, },
				MatteBlur = Input { Value = 0.4, },
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
                out.append({'ini': ini, 'fin': fin, 'arriba': arriba, 'abajo': abajo, 'linea': max(0.02, linea), 'xs': xs or [0.5],
                            'palabras': [(str(r.get('texto') or ''), float(r['t']) if isinstance(r.get('t'), (int, float)) else ini) for r in runs]})
    out.sort(key=lambda b: b['ini'])
    return out


_DETECCIONES = {}


def _personas(ruta, t):
    """edicion_pro_persona.personas con caché por fotograma (los captions detrás y la regla de la cara miran los mismos)."""
    k = (str(ruta), round(float(t), 2))
    if k not in _DETECCIONES:
        import edicion_pro_persona as PE
        _DETECCIONES[k] = PE.personas(ruta, t)
    return _DETECCIONES[k]


def _cabeza(det):
    """(coronilla, x de la cabeza, alto de la persona, alto de la cabeza) de la persona más grande del fotograma (fracciones, y desde ARRIBA), o None."""
    ps = (det or {}).get('personas') or []
    if not ps:
        return None
    p = max(ps, key=lambda q: q['area'])
    x0, y0, x1, y1 = p['bbox']
    cab = (p.get('cabeza') or {}).get('alto') or 0.18 * (y1 - y0)
    return y0, (p['puntos'][0][0] if p.get('puntos') else (x0 + x1) / 2.0), y1 - y0, cab


def _captions_detras(info, video, fps, ocupado, densidad, decir, preferidos=(), W=1080, H=1920):
    """Qué bloques de captions van DETRÁS de la persona y cuánto suben. Un bloque vale si la persona es grande, su cabeza no se sale por arriba,
    está quieta en todo el bloque (misma toma), la pila le cae encima en horizontal y no hay otro gráfico ni B-roll en ese momento. La pila sube (o
    baja) hasta que su borde de abajo queda un poco por debajo de la coronilla: la cabeza tapa la parte de abajo de la palabra grande y el resto se lee.
    El primero que vale entra siempre (el gancho), también los de `preferidos` (las palabras fuertes y las preguntas que la PRO ya no repite en un
    titular) y el resto se alternan (`DETRAS_CAPTIONS`): el contraste también retiene.
    Devuelve los tramos [{'ini', 'fin' (s), 'det', 't_det', 'cues': [{'ini', 'fin', 'subir' (fracción del alto, + = arriba)}]}]."""
    bloques = _bloques_captions()
    if not bloques:
        return []
    decir('Edición PRO: buscando dónde los captions van detrás de la persona…')
    frac = DETRAS_CAPTIONS.get(densidad, 0.55)
    elegidos, acum = [], 1.0 - frac
    for k, b in enumerate(bloques):
        a, z = b['ini'], b['fin']
        if any(a < o1 and o0 < z for o0, o1 in ocupado):
            continue
        acum += frac
        pref = any(a < p1 and p0 < z for p0, p1 in preferidos)
        if acum < 0.999 and not pref:
            continue
        r0, t0, c0 = _fuente_de(info, video, a + 0.12)
        r1, t1, c1 = _fuente_de(info, video, max(a + 0.12, z - 0.15))
        if c0 is not c1:
            continue                                                  # cruza un corte de V1: el recorte no seguiría a la persona
        try:
            d0, d1 = _personas(r0, t0), _personas(r1, t1)
            h0, h1 = _cabeza(_a_timeline(d0, c0, W, H)), _cabeza(_a_timeline(d1, c1, W, H))
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
        acum = max(0.0, acum - 1.0)
        caras = _caras(_a_timeline(d0, c0, W, H)) + _caras(_a_timeline(d1, c1, W, H))
        elegidos.append(dict(b, k=k, subir=-dy, clip=c0, det=d0, t_det=a + 0.12, caras=caras))
    # los bloques seguidos (de la misma toma) comparten un solo recorte de la persona: menos rastreos de Magic Mask
    tramos = []
    for e in elegidos:
        k = e['k']
        sig = bloques[k + 1]['ini'] if k + 1 < len(bloques) else e['fin'] + 0.3
        fin = max(e['ini'] + 0.3, min(e['fin'] + 0.2, sig))           # sin tapar el bloque siguiente (ese va normal, delante)
        cue = {'ini': e['ini'], 'fin': e['fin'], 'subir': round(e['subir'], 4), 'caras': e['caras'],
               'caja': [round(e['arriba'] - e['subir'], 4), round(e['abajo'] - e['subir'], 4)]}     # v5.5.2: dónde queda el caption (sus emojis no lo pisan)
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


def _captions_sin_cara(info, video, ocupado, detras, W, H):
    """REGLA DEL USUARIO: ningún caption tapa una cara. Los bloques que no van detrás de la persona y caerían sobre una cara (al principio o al
    final del bloque) suben encima de la cabeza o bajan debajo de la barbilla (si no cabe en ningún lado, se quedan).
    v5.5.8 (pedido: «some text stay up some stay down… necesito más coherencia»): antes cada bloque iba a lo MÁS CERCANO y en un mismo video
    unos subían a la frente y otros bajaban al pecho. Ahora se elige UN lado para todo el video (debajo de la barbilla, salvo que arriba quepa
    en más bloques) y los bloques seguidos que se mueven comparten la MISMA altura (`_lado_coherente`).
    Devuelve [{'ini', 'fin' (s), 'subir' (fracción, + arriba; 0 si no tapaban), 'caras'}] de los bloques con alguna cara: colocar_pro revisa
    con 'caras' también sus emojis."""
    ya = {round(c['ini'], 3) for t in detras for c in t['cues']}
    filas = []
    for b in _bloques_captions():
        a, z = b['ini'], b['fin']
        if round(a, 3) in ya or any(a < o1 and o0 < z for o0, o1 in ocupado):
            continue
        caras = []
        for t in (a + 0.12, max(a + 0.12, z - 0.15)):
            ruta, t_src, clip = _fuente_de(info, video, t)
            try:
                caras += _caras(_a_timeline(_personas(ruta, t_src), clip, W, H))
            except Exception:
                pass
        if not caras:
            continue
        yc, medio = (b['arriba'] + b['abajo']) / 2.0, (b['abajo'] - b['arriba']) / 2.0
        filas.append({'ini': a, 'fin': z, 'yc': yc, 'medio': medio, 'caras': caras,
                      'x0': max(0.0, min(b['xs']) - 0.2), 'x1': min(1.0, max(b['xs']) + 0.2)})
    out = []
    for f, y in zip(filas, _lado_coherente(filas)):
        yc, medio = f['yc'], f['medio']
        caja = [round(y - medio, 4), round(y + medio, 4)] if y is not None else [round(yc - medio, 4), round(yc + medio, 4)]
        out.append({'ini': f['ini'], 'fin': f['fin'], 'subir': round(yc - y, 4) if y is not None else 0.0, 'caras': f['caras'], 'caja': caja})
    return out


DATOS_OGRAF = {'precio': 1.15, 'grafica': 1.1, 'cifra': 1.0}           # tipo de objeto → su escala en EscenaT5 (ESCALA_OBJ de Skill.tsx)


def _motions_a_ograf(piezas, W, H):
    """v5.5.8 (pedido: «los motions que el usuario pueda retocarlos en el Inspector sin afectar el motion»): las tarjetas de dato de los Temas
    5/6 (precio, cifra, gráfica) van como la pieza OGraf «dato» —valor, moneda, etiqueta, colores, tipografía, posición y tamaño editables en el
    Inspector, la animación se recalcula sola— en vez de un video de Remotion, en el MISMO sitio y tamaño:
      · TarjetaT5 de gráfica (encima de la cabeza): pasa entera a OGraf (su `y` era el borde de arriba; la del dato, el centro);
      · EscenaT5 con un solo objeto de dato: la escena se queda de fondo (Remotion, sin el objeto) y la tarjeta va encima como OGraf, en
        PRO-DELANTE, o en PRO-ICONOS si esa pista ya está ocupada a esa hora (dos clips a la vez en una pista no se colocan)."""
    U = min(W, H) / 1080.0
    ocupado = [(p['ini'], p['fin']) for p in piezas if p.get('capa') == 'delante' and not p.get('quitar')]
    nuevas = []
    for p in piezas:
        v = p.get('valores') or {}
        if p.get('quitar'):
            continue
        if p.get('remotion') == 'TarjetaT5' and v.get('tipo') == 'grafica':
            esc = float(v.get('escala') or 1.0)
            alto = 392 * U * esc / H * 100.0                                # alto de la carta de gráfica de TarjetaT5, en % del cuadro
            sube = float(v.get('sube') or 0)
            p.pop('remotion', None)
            p['pieza'] = 'dato'
            p['valores'] = {'tipo': 'grafica', 'valor': str(v.get('valor') or ''), 'signo': str(v.get('signo') or ''),
                            'etiqueta': str(v.get('etiqueta') or '').upper()[:28], 'tendencia': 'baja' if sube < 0 else 'sube' if sube > 0 else 'plana',
                            'tema': 'claro' if v.get('aspecto') == 'blanco' else 'oscuro', 'acento': v.get('acento') or '#4c7dff',
                            'tiempos': '0.1', 'escala': round(esc * min(W * 0.88, 920 * U) / (700 * U), 3),
                            'x': float(v.get('x', 50)), 'y': round(float(v.get('y', 20)) + alto / 2.0, 2)}
            continue
        objs = v.get('objetos') or []
        if not (p.get('remotion') == 'EscenaT5' and v.get('disposicion', 'objeto') == 'objeto' and len(objs) == 1 and objs[0].get('tipo') in DATOS_OGRAF):
            continue
        o, mitad = objs[0], v.get('mitad', 'completa')
        encima, arriba = mitad == 'encima', mitad == 'arriba'
        tipo = o['tipo']
        k = DATOS_OGRAF[tipo] * (0.8 if (arriba or encima) and tipo != 'cifra' else 1.0) * (0.86 if encima else 1.0)
        ini, fin = round(p['ini'] + max(0.0, float(o.get('t', 0.2)) - 0.1), 3), round(p['fin'] - 0.05, 3)
        if fin - ini < 0.6:
            continue
        sube = float(o.get('sube', 1) or 0)
        nuevas.append({'pieza': 'dato', 'capa': 'iconos' if any(ini < b and a < fin for a, b in ocupado) else 'delante', 'ini': ini, 'fin': fin,
                       'motivo': f'dato editable: {tipo} {o.get("signo", "")}{o.get("valor", "")}',
                       'valores': {'tipo': tipo, 'valor': str(o.get('valor') or ''), 'signo': str(o.get('signo') or ''),
                                   'etiqueta': str(o.get('etiqueta') or ('TOTAL' if tipo == 'precio' else 'GROWTH' if tipo == 'grafica' else '')),
                                   'tendencia': 'baja' if sube < 0 else 'sube', 'tema': 'oscuro' if (encima or v.get('fondo') == 'cristal') else 'claro',
                                   'fuente': 'serif' if v.get('fondo') == 'melocoton' else 'grotesk', 'acento': v.get('acento') or '#4c7dff',
                                   'tiempos': '0.1', 'escala': round(k, 3), 'x': 50.0,
                                   'y': float(v.get('y', 68)) if encima else 29.0 if arriba else 56.0}})
        p['valores'] = dict(v, objetos=[])                                  # la escena, solo de fondo
    piezas.extend(nuevas)
    return len(nuevas)


def _opciones_fuera(yc, medio, caras, x0=0.0, x1=1.0):
    """{'queda': y si no pisa ninguna cara, 'abajo': centro justo debajo de la barbilla más baja, 'arriba': justo encima de la coronilla más
    alta} (None el que no quepa): lo que `_fuera_de_la_cara` elegía por cercanía, por separado."""
    malas = [c for c in caras if c[0] < x1 and x0 < c[2]]

    def libre(yy):
        return 0.04 + medio <= yy <= 0.96 - medio and all(yy + medio + MARGEN_CARA <= c[1] or yy - medio - MARGEN_CARA >= c[3] for c in malas)
    if not malas or libre(yc):
        return {'queda': yc, 'abajo': None, 'arriba': None}
    abajo = max(c[3] for c in malas) + MARGEN_CARA + medio
    arriba = min(c[1] for c in malas) - MARGEN_CARA - medio
    return {'queda': None, 'abajo': abajo if libre(abajo) else None, 'arriba': arriba if libre(arriba) else None}


def _lado_coherente(filas, hueco_s=1.2):
    """El centro final de cada fila ({'yc', 'medio', 'caras', 'x0', 'x1', 'ini', 'fin'}) o None si no cabe: UN lado para todo el video (abajo
    salvo que arriba quepa en más bloques) y una misma altura para los bloques seguidos (a menos de `hueco_s`) que se mueven al mismo lado."""
    ops = [_opciones_fuera(f['yc'], f['medio'], f['caras'], f['x0'], f['x1']) for f in filas]
    n_abajo = sum(1 for o in ops if o['queda'] is None and o['abajo'] is not None)
    n_arriba = sum(1 for o in ops if o['queda'] is None and o['arriba'] is not None)
    lado, otro = ('abajo', 'arriba') if n_abajo >= n_arriba else ('arriba', 'abajo')
    ys, lados = [], []
    for o in ops:
        elegido = None if o['queda'] is not None else lado if o[lado] is not None else otro if o[otro] is not None else None
        ys.append(o['queda'] if elegido is None and o['queda'] is not None else o[elegido] if elegido else None)
        lados.append(elegido)
    # misma altura en las rachas de bloques seguidos movidos al mismo lado (la más baja si van abajo, la más alta si van arriba), si les cabe a todos
    i = 0
    while i < len(filas):
        j = i
        while j + 1 < len(filas) and lados[j + 1] and lados[j + 1] == lados[i] and filas[j + 1]['ini'] - filas[j]['fin'] <= hueco_s:
            j += 1
        if lados[i] and j > i:
            comun = (max if lados[i] == 'abajo' else min)(ys[i:j + 1])
            if all(_opciones_fuera(comun, filas[k]['medio'], filas[k]['caras'], filas[k]['x0'], filas[k]['x1'])['queda'] is not None
                   for k in range(i, j + 1)):
                ys[i:j + 1] = [comun] * (j + 1 - i)
        i = j + 1
    return ys


def _iconos3d_captions(info, ocupado, subidas, caras_de, W, H, densidad):
    """Iconos 3D (3dicons) que FLOTAN arriba a un lado de la pila de captions cuando se nombra algo que tiene uno («precio» → dinero,
    «viral» → fuego…), en vez del emoji plano de ese bloque. Nunca encima de una cara (prueba el otro lado; si no, no va).
    Devuelve [{'ini', 'fin' (s), 'valores'}] y las ventanas donde se apaga el emoji del tema."""
    import edicion_pro_planificador as PL
    disp = OG.iconos3d()
    vertical = H > W
    cada = ICONO3D_CADA.get(densidad, 3.5)
    out, ultimo = [], -99.0
    for b in _bloques_captions():
        a, z = b['ini'], b['fin']
        if a - ultimo < cada or z - a < 0.8 or any(a < o1 and o0 < z for o0, o1 in ocupado):
            continue
        nombre, t_pal = None, a
        for texto, t in b.get('palabras') or []:
            w = PL.plegar(texto)
            n = PL.CONCEPTOS3D.get(w) or PL.ICONO_A_3D.get(PL.CONCEPTOS.get(w, ''))
            if n and n in disp:
                nombre, t_pal = n, max(a, t)
                break
        if not nombre or z - t_pal < 0.6:
            continue
        sube = subidas.get(round(a, 2), 0.0)
        tam = 0.085 if vertical else 0.13
        y = max(tam / 2 + 0.035, b['arriba'] - sube - tam * 0.25)
        ancho = tam * H / W
        caras = caras_de.get(round(a, 2), [])
        x = None
        for cx in (min(0.92 - ancho / 2, max(b['xs']) + 0.12), max(0.08 + ancho / 2, min(b['xs']) - 0.12)):
            if not any(k[0] < cx + ancho / 2 and cx - ancho / 2 < k[2] and k[1] < y + tam / 2 and y - tam / 2 < k[3] for k in caras):
                x = cx
                break
        if x is None:
            continue
        ultimo = a
        out.append({'ini': max(a, t_pal - 0.05), 'fin': z + 0.15, 'valores': {'imagen': nombre, 'tamano': round(tam * 100, 1), 'brillo': 0.75,
                    'flotar': 1.0, 'giro': 8, 'x': round(x * 100, 1), 'y': round(y * 100, 1), 'tiempos': '0'}})
    return out


def _caras_redondas(caras):
    return [[round(float(x), 4) for x in c] for c in caras or []]


def aplicar(plan, al_estado=None, offset_frames=0, info=None):
    """Pone la Edición PRO en el timeline actual. Devuelve (ok, mensaje)."""
    decir = al_estado or (lambda t: None)
    if not plan or not (plan.get('piezas') or plan.get('tema5') or plan.get('ligero')
                        or (plan.get('opciones') or opciones_guardadas()).get('pro_motions_completo')):        # v5.5.8: también solo motions
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
    # v5.5.7: en «auto» la persona la recorta SIEMPRE la IA local (clip ProRes con alfa), también en Studio: el rastreo del Magic Mask dentro de
    # Resolve lo tumbó dos veces colocando la PRO (2026-10-13 y 14). Así Studio y Free hacen lo mismo y Resolve no calcula nada pesado. Magic Mask,
    # solo si se elige a mano en el menú.
    usar_magic = studio and modo_mascara == 'magic'
    usar_ia = modo_mascara in ('auto', 'ia') or (modo_mascara == 'magic' and not studio)
    # v5.5.8 (pedido del usuario): el GANCHO (el primer tramo de captions detrás de la persona, en los primeros segundos) con Magic Mask en Studio
    # también en «auto»; el resto sigue con el recorte de la IA local (Magic Mask en todo el video llegó a cerrar Resolve)
    magic_gancho = studio and modo_mascara == 'auto' and op.get('pro_magic_gancho', True) is not False
    video = plan.get('video') or ''
    t5 = bool(plan.get('tema5'))                     # Tema 5: la edición completa con el sistema de la skill (edicion_pro_tema5); los Text+ de GO, de respaldo
    # v5.5.8: con captions editables (por defecto) los Temas 5 y 6 dejan los Text+ de GO como captions DE VERDAD (Inspector › editar texto) y usan
    # las mismas mecánicas de captions que los Temas 1–4 (detrás de la persona, sin tapar caras, abajo en las escenas); sus gráficos siguen igual.
    # `cap_t5` = el Tema 5/6 con sus captions de Remotion (no editables), solo si el usuario lo apaga.
    cap_t5 = t5 and (plan.get('opciones') or {}).get('pro_captions_editables', True) is False
    soltar_gpu(texto=not t5)                         # v5.5.4: la GPU para Resolve y el Magic Mask (el Tema 5 aún usa la IA de texto: la suelta él al acabar)
    ligero = bool(plan.get('ligero'))              # Temas 1–4 sin la PRO: solo legibilidad, acompañantes, color y la regla de la cara (edicion_pro_temas)
    divididas = []
    # punch-in de 1,08 en V1 alterno cuando hay saltos (pausas quitadas): lo coloca colocar_pro y las cuentas de posición ya lo tienen en cuenta
    # (antes de planificar el Tema 5: el sticker congelado y la pantalla final copian el encuadre de su clip)
    punch = []
    v1 = sorted(info.get('v1') or [], key=lambda c: c['ini'])
    if len(v1) >= 2 and not any(c.get('fx') for c in v1) and not ligero:
        for n, c in enumerate(v1):
            if n % 2 == 1 and abs(float(c.get('zx') or 1.0) - 1.0) < 1e-3 and abs(float(c.get('zy') or 1.0) - 1.0) < 1e-3:
                c['zx'] = c['zy'] = PUNCH_IN
                punch.append([int(c['ini']), PUNCH_IN])
    if t5:
        import edicion_pro_persona as PE5
        import edicion_pro_tema5 as T5

        def det5(t):
            ruta, t_src, clip = _fuente_de(info, video, t)
            try:
                return _a_timeline(PE5.personas(ruta, t_src), clip, W, H) if PE5.disponible() else None
            except Exception:
                return None

        def foto5(t):
            ruta, t_src, _clip = _fuente_de(info, video, t)
            return T5.foto(ruta, t_src)

        def recorte5(t):                             # el sticker del gancho: la persona recortada con la IA local y el fondo, como en el timeline
            ruta, t_src, clip = _fuente_de(info, video, t)
            try:
                import edicion_pro_tema5_mm as MM5
                rgb = PE5.fotograma(ruta, t_src) if PE5.disponible() else None
                return MM5.imagenes_sticker(rgb, PE5.mate(rgb), clip, W, H) if rgb is not None else None
            except Exception:
                return None

        def cara5(t):                                # la pantalla final: la cara en el círculo y el fondo
            ruta, t_src, clip = _fuente_de(info, video, t)
            try:
                import edicion_pro_tema5_mm as MM5
                rgb = PE5.fotograma(ruta, t_src) if PE5.disponible() else None
                det = PE5.personas(ruta, t_src) if rgb is not None else None
                return MM5.imagenes_final(rgb, det, clip, W, H) if det and det.get('personas') else None
            except Exception:
                return None
        if plan.get('estilo_t5') == 'editorial':      # Tema 6: el mapa oscuro a pantalla completa no es de su estilo (va la tarjeta blanca del mapa)
            plan['piezas'] = [p for p in plan['piezas'] if p.get('pieza') not in T5.PIEZAS_QUE_QUEDAN]
        quedan = [p for p in plan['piezas'] if p.get('pieza') in T5.PIEZAS_QUE_QUEDAN]      # órbita, plantillas, escenas OGraf…: no son de este sistema
        nuevas, divididas = T5.planificar(plan, vertical, op.get('pro_densidad') or 'media', video, det_de=det5, foto_de=foto5,
                                          ia=op.get('pro_ia_local', True) is not False, idioma=plan.get('idioma') or 'es', estado=decir,
                                          recorte_de=recorte5, cara_de=cara5, usuario=str(op.get('pro_usuario') or ''),
                                          estilo=plan.get('estilo_t5') or 'skill')
        if not cap_t5:                               # captions editables: fuera los captions de Remotion (y sus velos); los Text+ de GO se quedan
            nuevas = [q for q in nuevas if q.get('pieza') not in ('subtitulo', 'velo_caption')]
        plan['piezas'] = quedan + nuevas
    clave = hashlib.sha1(f'{video}|{W}x{H}@{fps}'.encode('utf-8')).hexdigest()[:10]
    carpeta = OG.ruta_larga(CARPETA / clave)
    carpeta.mkdir(parents=True, exist_ok=True)
    # v5.5.9 (el usuario: «más tareas en paralelo, más rapidez»): lo que no depende de nada de lo de abajo arranca YA, en otro hilo, y se recoge
    # donde antes se hacía: «Motions completo» (su render de Remotion corre mientras se buscan las personas, se recortan y se revisan los
    # gráficos) y la descarga del B-roll de stock (la red, mientras la GPU trabaja)
    fondo = {}

    def _motions_completo():
        try:
            import motions_completo as MCO
            bl = [{'ini': b['ini'], 'fin': b['fin'], 'palabras': [{'texto': x, 't': round(max(0.0, float(t) - b['ini']), 3)} for x, t in b.get('palabras') or []]}
                  for b in _bloques_captions()]
            dur_mc = float(plan.get('duracion') or 0) or (max(b['fin'] for b in bl) + 0.5 if bl else 0.0)
            fondo['mc_dur'] = dur_mc
            # sin la IA de texto: con ella el plan tardaba ~110 s (y volvía a cargar en la GPU el modelo que la PRO suelta para Resolve) para
            # unas pocas propuestas que ya pesan menos que las reglas
            fondo['mc'] = MCO.crear(bl, dur_mc, W, H, fps, carpeta, plan.get('idioma') or 'es', plan.get('perfil') or {}, video, decir,
                                    ia=bool(op.get('pro_motions_ia', False))) if bl and dur_mc > 1.0 else None
        except Exception as e:
            fondo['mc_error'] = e

    def _broll():
        try:
            import broll
            import efectos_visuales
            clave_b = broll.clave_guardada(efectos_visuales.opciones_guardadas())
            fondo['broll'] = list(broll.preparar(plan['broll'], 'v' if vertical else 'h', clave_b, decir))
        except Exception as e:
            fondo['broll_error'] = e

    hilos_fondo = {}
    if op.get('pro_motions_completo'):
        hilos_fondo['mc'] = threading.Thread(target=_motions_completo, name='pro-motions-completo', daemon=True)
    if plan.get('broll'):
        decir('Edición PRO: buscando las tomas de B-roll…')
        hilos_fondo['broll'] = threading.Thread(target=_broll, name='pro-broll', daemon=True)
    for h in hilos_fondo.values():
        h.start()
    import edicion_pro_persona as PE
    hay_ia = PE.disponible()
    graficos, persona = [], []
    ventanas, forzadas = {}, set()                 # forzadas: escenas «fondo sustituido» sin sitio encima de la cabeza → pantalla completa
    decir('Edición PRO: buscando a las personas del video…')
    # v5.5.2 REGLA OFICIAL (usuario): nada tapa una CARA ni un CAPTION — ni los gráficos, ni las plantillas, ni el kit, ni los emojis — y todo queda
    # repartido. Los captions de la PRO (Temas 5/6) se colocan PRIMERO; luego cada gráfico de delante esquiva las caras, los captions de ese momento
    # (los de los Temas 1–4 del manifiesto, con sitio para su emoji arriba o abajo) y los demás gráficos que ya estén en pantalla a la vez.
    bloques_cap = _bloques_captions()
    puestos = []                                                       # [(ini, fin, arriba, abajo)] de lo ya colocado delante (fracción del alto)
    for p in sorted(plan['piezas'], key=lambda q: 0 if q['pieza'] == 'subtitulo' else 1):
        det, clip = None, None
        p['_valores0'] = dict(p['valores'])
        if hay_ia and (p.get('ajustar') or p.get('persona')):
            ruta, t_src, clip = _fuente_de(info, video, (p['ini'] + p['fin']) / 2.0)
            try:
                det = PE.personas(ruta, t_src)
            except Exception:
                det = None
        if p.get('ajustar'):
            extra = _obstaculos(p, bloques_cap, puestos) if p['capa'] == 'delante' and p['pieza'] not in ('subtitulo', 'orbita') else []
            det_tl = _a_timeline(det, clip, W, H)
            _ajustar_posiciones(p, det_tl, vertical, extra)
            if p['pieza'] == 'subtitulo' and det_tl and det_tl.get('personas'):
                p['_caras'] = _caras(det_tl)                           # (T5.coordinar: el acompañante bajo este caption tampoco tapa estas caras)
            if p['pieza'] == 'orbita' and p.get('remotion') and det:     # los iconos de Remotion son algo más grandes: un poco más abajo del mentón
                p['valores']['ry'] = round(float(p['valores'].get('ry', 5.0)) + 1.3, 2)
            if p['pieza'] == 'subtitulo' and p.pop('quitar', False):  # sin sitio libre de caras: abajo y más pequeño (un caption no se quita)
                p['valores'].update(y=84.0 if vertical else 86.0, escala=0.8)
            if t5:
                T5.subir_detras(p)
                # v5.5.10: la clave «detrás» solo se lee si va POR ENCIMA de la cabeza; si la persona está tan arriba que el centro del texto
                # cae a media cabeza o más abajo (p. ej. alguien de cuerpo entero caminando: «Europa» quedó tapado), va delante, normal.
                if p['pieza'] == 'subtitulo' and p['capa'] == 'detras' and det_tl and det_tl.get('personas'):
                    yc = float(p['valores'].get('y', 30.0)) / 100.0
                    if any(yc > k['bbox'][1] + 0.5 * (k.get('cabeza') or {}).get('alto', 0.0) for k in det_tl['personas']):
                        p['valores'] = dict(p['_valores0'], modo='normal', y=T5.Y_NORMAL[vertical]) if p.get('_valores0') else dict(p['valores'], modo='normal', y=T5.Y_NORMAL[vertical])
                        p['capa'], p['persona'] = 'subs', False
            caja = _caja_vertical(p)                                    # (ya en su sitio final: lo que venga después lo esquiva)
            if caja and not p.get('quitar') and (p['capa'] == 'delante' or p['pieza'] == 'subtitulo'):
                puestos.append((p['ini'], p['fin']) + caja)
        if p.get('persona') and p['capa'] in ('detras', 'velo'):
            k = (p['ini'], p['fin'])
            if k not in ventanas:
                ventanas[k] = det
            if p.get('forzar_pantalla'):
                forzadas.add(k)
    # v5.5.3: una escena a pantalla completa del director solo tapa a QUIEN HABLA: si en ese tramo el video ya enseña otra cosa (su propio B-roll,
    #         un cartel, una foto: nadie en cuadro en al menos 2 de 3 fotogramas), se quita: no se tapa el material del usuario
    if hay_ia and not t5:
        for p in plan['piezas']:
            if not p.get('escena_mg') or p.get('quitar'):
                continue
            vistos = 0
            for t in (p['ini'] + 0.3, (p['ini'] + p['fin']) / 2.0, p['fin'] - 0.3):
                try:
                    ruta, t_src, _c = _fuente_de(info, video, t)
                    dd = _personas(ruta, t_src)
                    vistos += 1 if dd and dd.get('personas') else 0
                except Exception:
                    vistos += 1
            if vistos < 2:
                p['quitar'] = True
                p['motivo'] = p.get('motivo', '') + ' · quitada: el video ya enseña otra toma'
    if t5:
        T5.coordinar(plan['piezas'])                 # el indicador de pasos / el deslizador, debajo de los captions ya colocados
    # la persona de cada ventana (si no hay nadie, el titular queda delante y sin velo)
    sin_persona = set(forzadas)
    for (a, b), det in ventanas.items():
        f0, f1 = int(round(a * fps)), int(round(b * fps))
        if (a, b) in forzadas or not hay_ia or not det or not det.get('personas') or modo_mascara == 'no':
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
                    PE.recorte_prores(ruta, t_src, t_src + (b - a) + MARGEN_RECORTE_S, destino)
                persona.append({'ini': f0, 'fin': f1, 'modo': 'clip', 'archivo': str(OG.ruta_larga(destino))})
            except Exception:
                sin_persona.add((a, b))
        else:
            sin_persona.add((a, b))
    # B-roll de stock (se descarga ahora: tras los captions, así GO no espera la red antes)
    tomas = []
    if 'broll' in hilos_fondo:                                         # (se descargaba en paralelo desde el principio)
        hilos_fondo['broll'].join()
        try:
            for ev in fondo.get('broll') or []:
                tomas.append({'ini': int(round(float(ev['ini']) * fps)), 'dur': float(ev['dur']), 'archivo': str(OG.ruta_larga(ev['archivo'])),
                              'palabra': ev.get('palabra', ''), '_s': float(ev['ini'])})
        except Exception:
            tomas = []
    plan['_broll_puesto'] = [{'ini': t['_s']} for t in tomas]
    # captions DETRÁS de la persona (lo que hace que valga la pena el Magic Mask)
    encima, tramos = [], []
    if hay_ia and modo_mascara != 'no' and not cap_t5 and not ligero:
        ocupado = [(p['ini'] - 0.1, p['fin'] + 0.1) for p in plan['piezas'] if p['pieza'] != 'marco']
        ocupado += [(t['_s'] - 0.1, t['_s'] + t['dur'] + 0.1) for t in tomas]
        ocupado += [((a - info['base']) / fps, (b - info['base']) / fps) for a, b in info.get('ocupado') or []]
        try:
            tramos = _captions_detras(info, video, fps, ocupado, op.get('pro_densidad') or 'media', decir,
                                      preferidos=[tuple(x) for x in plan.get('detras_pref') or []], W=W, H=H)
        except Exception:
            tramos = []
        for t in tramos:
            f0, f1 = int(round(t['ini'] * fps)), int(round(t['fin'] * fps))
            ref = max(0, min(f1 - f0 - 1, int(round((t['t_det'] - t['ini']) * fps))))
            e = {'ini': f0, 'fin': f1, 'ref': ref, 'cues': [{'ini': int(round(c['ini'] * fps)), 'fin': int(round(c['fin'] * fps)),
                                                            'subir': round(c['subir'] * H, 1), 'caras': _caras_redondas(c.get('caras')),
                                                            'caja': c.get('caja')}
                                                           for c in t['cues']]}
            gancho = magic_gancho and t is tramos[0] and t['ini'] < 6.0           # (el primero que vale es el gancho: _captions_detras lo mete siempre)
            if usar_magic or gancho:
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
            # v5.5.2: SIN el velo oscuro detrás de estos captions (el usuario: «los captions tienen una sombra fea»); la persona encima ya los separa
            encima.append(e)
    # el resto de los bloques de captions: ninguno tapa una cara (y colocar_pro aparta sus emojis)
    mover = []
    if hay_ia and not cap_t5:
        try:
            pantallas = [(p['ini'] - 0.1, p['fin'] + 0.1) for p in plan['piezas'] if p.get('pantalla') and (p['ini'], p['fin']) not in ventanas]
            pantallas += [(t['_s'] - 0.1, t['_s'] + t['dur'] + 0.1) for t in tomas]
            sin_cara = _captions_sin_cara(info, video, pantallas, tramos, W, H)
            for c in sin_cara:
                mover.append({'ini': int(round(c['ini'] * fps)), 'fin': int(round(c['fin'] * fps)), 'subir': round(c['subir'] * H, 1),
                              'caras': _caras_redondas(c['caras']), 'caja': c.get('caja')})
        except Exception:
            mover, sin_cara = [], []
    else:
        sin_cara = []
    # v5.5.3: mientras dura una escena a pantalla completa del director (Escenas9), los captions de los Temas 1–4 bajan a la parte de abajo
    if not cap_t5:
        try:
            import edicion_pro_escenas as ES
            esc = [(p['ini'], p['fin']) for p in plan['piezas'] if p.get('escena_mg') and not p.get('quitar')]
            for bq in (_bloques_captions() if esc else []):
                a, z = bq['ini'], bq['fin']
                if not any(a < e1 - 0.1 and e0 + 0.1 < z for e0, e1 in esc):
                    continue
                yc, medio = (bq['arriba'] + bq['abajo']) / 2.0, (bq['abajo'] - bq['arriba']) / 2.0
                y = min(ES.Y_CAPTIONS[vertical] / 100.0, 0.97 - medio)
                if yc >= y - 0.02:
                    continue                                          # ya iba abajo
                clave = (int(round(a * fps)), int(round(z * fps)))
                mover = [m for m in mover if (m['ini'], m['fin']) != clave]
                mover.append({'ini': clave[0], 'fin': clave[1], 'subir': round((yc - y) * H, 1), 'caras': [], 'caja': [round(y - medio, 4), round(y + medio, 4)]})
        except Exception:
            pass
    # iconos 3D flotando junto a los captions (en vez del emoji de ese bloque)
    iconos3d, sin_emoji = [], []
    try:
        subidas = {round(c['ini'], 2): c['subir'] for t in tramos for c in t['cues']}
        subidas.update({round(c['ini'], 2): c['subir'] for c in sin_cara})
        caras_de = {round(c['ini'], 2): c.get('caras') or [] for t in tramos for c in t['cues']}
        caras_de.update({round(c['ini'], 2): c['caras'] for c in sin_cara})
        ocupado3d = [(p['ini'] - 0.1, p['fin'] + 0.1) for p in plan['piezas'] if p.get('pantalla')] + [(t['_s'], t['_s'] + t['dur']) for t in tomas]
        iconos3d = [] if (t5 or ligero) else _iconos3d_captions(info, ocupado3d, subidas, caras_de, W, H, op.get('pro_densidad') or 'media')
    except Exception:
        iconos3d = []
    acento = (plan.get('direccion') or {}).get('acento') or '#ffb020'
    for c in iconos3d:
        ruta = OG.construir('icono3d', dict(c['valores'], acento=acento), max(0.4, c['fin'] - c['ini']), carpeta, fps=fps, ancho=W, alto=H)
        graficos.append({'capa': 'iconos', 'ini': int(round(c['ini'] * fps)), 'archivo': str(ruta), 'nombre': 'PRO · Icono 3D'})
        sin_emoji.append([int(round(c['ini'] * fps)) - 2, int(round(c['fin'] * fps))])
    plan['_iconos3d'] = iconos3d
    color_claves = None
    if ligero or not t5:                             # Temas 1–4: el velo de legibilidad y los acompañantes, YA con la regla de la cara aplicada (mover)
        try:                                         # v5.5.4: también CON la Edición PRO (pedido: «algún motion debajo de los captions, aunque sea 1 o 2»)
            import edicion_pro_temas as TM
            extra = TM.piezas(info, video, plan.get('idioma') or 'es', W, H, fps, mover, plan, maximo=None if ligero else 3)
            extra = [p for p in extra if not any(p['ini'] < t['fin'] and t['ini'] < p['fin'] for t in tramos)]   # (no bajo un caption que va detrás)
            plan['piezas'] = list(plan.get('piezas') or []) + extra
            if ligero:
                color_claves = TM.color_claves(info, video, fps)
        except Exception:
            pass
    gris = [[int(round(a * fps)), int(round(b * fps))] for a, b in plan.get('gris') or []]
    try:                                             # v5.5.7: también lo que se añadió al aplicar (Tema 5/6, acompañantes): solo motions permitidos
        import motions_catalogo as MC
        plan['piezas'] = MC.filtrar(plan.get('piezas') or [], op)
    except Exception:
        pass
    decir('Edición PRO: preparando los gráficos animados…')
    try:
        _motions_a_ograf(plan['piezas'], W, H)                     # v5.5.8: las tarjetas de dato, editables en el Inspector (OGraf)
    except Exception:
        pass
    try:                                                           # v5.5.8: el VIGILANTE (reglas + IA local) antes de renderizar nada
        import vigilante_pro as VG
        dichas = [(float(t), str(x)) for b in _bloques_captions() for x, t in b.get('palabras') or []]
        VG.revisar_plan(plan['piezas'], dichas)
        if op.get('pro_ia_local', True):
            decir('Edición PRO: la IA revisa que cada gráfico encaje con lo que se dice…')
            VG.revisar_ia(plan['piezas'], dichas, plan.get('idioma') or 'es', estado=decir)
    except Exception:
        pass
    # las animaciones de Remotion (mapa + bandera…): todas en una tanda, con un solo navegador; sin Remotion, esas escenas no van
    rm_salida, rm_hechos = {}, {}
    try:
        import edicion_pro_remotion as RM
        trab = []
        for p in plan['piezas']:
            if p['pieza'] == 'subtitulo' and p['capa'] == 'detras' and (p['ini'], p['fin']) in sin_persona:
                import edicion_pro_tema5 as T5
                p['valores'] = dict(p['_valores0'], modo='normal', y=T5.Y_NORMAL[vertical])
                p['capa'], p['persona'] = 'subs', False
            if p['pieza'] in ('orbita', 'foco') and t5 and (p['ini'], p['fin']) in sin_persona:
                p['quitar'] = True                                    # sin la persona recortada: ni órbita (taparía la cara) ni foco (todo gris)
            if p.get('remotion') and not p.get('quitar'):
                props = dict(p['valores'], _ancho=W, _alto=H, _fps=fps, _dur=round(max(0.6, p['fin'] - p['ini']), 3))
                sal = RM.salida_para(p['remotion'], props, carpeta)
                rm_salida[id(p)] = sal
                trab.append({'id': p['remotion'], 'props': props, 'salida': sal})
        rm_hechos = RM.renderizar(trab, decir) if trab else {}
    except Exception:
        rm_hechos = {}

    def con_sombra(p, sal):
        """Tema 5: la clave DETRÁS de la persona con la sombra de la persona encima de las letras (la silueta del fotograma del medio)."""
        destino = Path(str(sal)).with_name(Path(str(sal)).stem + '_sombra.mov')
        if destino.exists():
            return destino
        try:
            import edicion_pro_tema5_mm as MM5
            ruta, t_src, clip = _fuente_de(info, video, (p['ini'] + p['fin']) / 2.0)
            rgb = PE.fotograma(ruta, t_src)
            if rgb is None:
                return None
            fx, fy = MM5.mapeo(clip, W, H)
            return destino if MM5.sombra_en_clip(sal, destino, MM5.silueta(PE.mate(rgb), fx, fy, W, H)) else None
        except Exception:
            return None
    gris_foco = []
    for p in plan['piezas']:
        capa = p['capa']
        if p.get('quitar'):
            continue                                                  # no había sitio sin tapar la cara
        if p['pieza'] == 'foco':                                      # Tema 5: el fondo en blanco y negro (colocar_pro) bajo la persona a color
            gris_foco.append([int(round(p['ini'] * fps)), int(round(p['fin'] * fps))])
            continue
        if p.get('remotion'):
            sal = rm_salida.get(id(p))
            if sal is not None and rm_hechos.get(str(sal)):
                if t5 and hay_ia and p['pieza'] == 'subtitulo' and p['capa'] == 'detras':
                    decir('Edición PRO: la sombra de la persona sobre la palabra de detrás…')
                    sal = con_sombra(p, sal) or sal
                graficos.append({'capa': p['capa'], 'ini': int(round(p['ini'] * fps)), 'archivo': str(OG.ruta_larga(sal)), 'alfa': True,
                                 'dur': round(p['fin'] - p['ini'], 3),             # v5.5.8: el vigilante comprueba que el clip dure lo que debe
                                 'nombre': 'PRO · ' + ({'Ubicacion': 'Mapa + bandera', 'Subtitulo': 'Caption', 'PasosT5': 'Pasos', 'DeslizadorT5': 'Deslizador',
                                                         'EscenaT5': 'Escena', 'AcompananteT5': 'Acompañante', 'VeloCaptionT': 'Velo de legibilidad',
                                                         'TarjetaT5': 'Tarjeta', 'OrbitaT5': 'Órbita', 'StickerT5': 'Sticker',
                                                         'FinalT5': 'Pantalla final', 'EditorialT6': 'Editorial'}.get(p['remotion'])
                                                        or p.get('plantilla') or p['remotion'])})
            continue
        if (p['ini'], p['fin']) in sin_persona:
            if p['pieza'] == 'orbita':
                continue                                              # sin nadie a quien rodear, no hay órbita
            if capa == 'velo':
                continue                                              # sin la persona delante, el velo solo oscurecería
            if capa == 'detras':
                capa = 'delante'
            if p.get('pantalla'):
                p['valores'] = dict(p['_valores0'])                     # escena sin persona: a pantalla completa, la pieza centrada
        dur = max(0.4, p['fin'] - p['ini'])
        ruta = OG.construir(p['pieza'], p['valores'], dur, carpeta, fps=fps, ancho=W, alto=H)
        graficos.append({'capa': capa, 'ini': int(round(p['ini'] * fps)), 'archivo': str(ruta), 'nombre': f"PRO · {OG.ESQUEMAS[p['pieza']]['nombre']}"})
    # Tema 5: la transición con zoom en los cortes (los de V1 —pausas quitadas— o, con un solo clip, los del propio video), lejos de lo demás
    zoom, plan['_zoom'] = [], []
    if t5:
        try:
            import edicion_pro_tema5_mm as MM5
            cortes = [(int(c['ini']) - info['base']) / fps for c in v1[1:]]
            if len(v1) == 1:
                c = v1[0]
                desde = (int(c['ini']) - info['base']) / fps - int(c.get('izq') or 0) / float(c.get('fps') or fps)
                cortes += [desde + float(x) for x in plan.get('_cortes_video') or []]
            elif not v1:
                cortes += [float(x) for x in plan.get('_cortes_video') or []]
            puestas = [p for p in plan['piezas'] if not p.get('quitar')]
            ocup = [(p['ini'], p['fin']) for p in puestas if p.get('capa') in ('fondo', 'detras', 'velo') or p.get('pantalla') or p.get('persona')]
            ocup += [(d['ini'], d['fin']) for d in divididas] + [(t['_s'], t['_s'] + t['dur']) for t in tomas]
            for t in MM5.transiciones(cortes, ocup, max([p['fin'] for p in puestas] or [0.0])):
                zoom.append([int(round(t * fps)), 5, 6])
                plan['_zoom'].append(t)
        except Exception:
            zoom = []
    rng = random.Random(PL.semilla_de(video, [], int(op.get('pro_variacion') or 0)))
    sonidos = []
    voz_db = None
    if op.get('pro_sonidos', True):                                   # diseño de sonido profesional (edicion_pro_sonido): whooshes, texturas, risers + hits
        import edicion_pro_sonido as PS
        voz_db = PS.nivel_voz(video)                                  # los efectos, siempre bajo la voz de ESTE video
        familias = dict(op.get('pro_sonidos_familias') or {})          # v5.5.7: lo que el usuario apagó en Sonido › Edición PRO
        extra_db = NIVEL_SONIDOS_DB.get(str(op.get('pro_sonidos_nivel') or 'normal'), 0.0)
        for e in PS.disenar(plan, fps, rng, choques=[] if cap_t5 else [(f - info['base']) / fps for f in info.get('sfx') or []],
                            cortes=[(int(f) - info['base']) / fps for f, _z in punch], voz_db=voz_db):
            if familias.get(FAMILIA_DE_PISTA.get(str(e.get('pista')), 'textura'), True) is False:
                continue
            e['db'] = float(e.get('db') or 0.0) + extra_db
            try:                                                      # el volumen, DENTRO del archivo (Resolve 21 ignora el de clip por script)
                e['archivo'] = str(OG.ruta_larga(_con_ganancia(e['archivo'], e.get('db', 0.0))))
                e['db'] = 0.0
            except Exception:
                e['archivo'] = str(OG.ruta_larga(_copia_de_usuario(e['archivo'])))     # nunca de la carpeta del programa: Resolve la retendría
            sonidos.append(e)
    # v5.5.7 (el usuario, Tema 4: «emojis encima de los captions, iconos y motions juntos»): donde la PRO enseña algo (acompañante, órbita, cifra,
    # escena, tarjeta, titular…), el emoji de GO se apaga: una sola cosa a la vez junto al caption
    if not cap_t5:
        for p in plan['piezas']:
            if p.get('quitar') or p.get('pieza') in ('subtitulo', 'velo', 'velo_caption', 'marco', 'fondo') or p.get('capa') == 'velo':
                continue
            sin_emoji.append([int(round(float(p['ini']) * fps)) - 3, int(round(float(p['fin']) * fps)) + 3])
    subs = [p for p in plan['piezas'] if p['pieza'] == 'subtitulo']
    subs_ok = sum(1 for p in subs if rm_hechos.get(str(rm_salida.get(id(p)))))
    if 'mc' in hilos_fondo:                                        # v5.5.8: «Motions completo», encima de todo (v5.5.9: se hacía en paralelo)
        try:
            import motions_completo as MCO
            if hilos_fondo['mc'].is_alive():
                decir('Edición PRO: terminando «Motions completo»…')
            hilos_fondo['mc'].join()
            if fondo.get('mc_error') is not None:
                raise fondo['mc_error']
            mc, dur_mc = fondo.get('mc'), float(fondo.get('mc_dur') or 0.0)
            if mc:
                graficos.append({'capa': 'motions', 'ini': 0, 'archivo': str(OG.ruta_larga(mc)), 'nombre': 'PRO · Motions completo', 'dur': round(dur_mc, 3),
                                 'opaco': True})
                if op.get('pro_sonidos', True):                           # v5.5.9: sus sonidos (whoosh al entrar cada tarjeta, clics, pops…), bajo la voz
                    import edicion_pro_sonido as PS
                    familias = dict(op.get('pro_sonidos_familias') or {})
                    extra_db = NIVEL_SONIDOS_DB.get(str(op.get('pro_sonidos_nivel') or 'normal'), 0.0)
                    for e in MCO.sonidos(mc, fps, rng, voz_db if voz_db is not None else PS.nivel_voz(video)):
                        if familias.get(FAMILIA_DE_PISTA.get(str(e.get('pista')), 'textura'), True) is False:
                            continue
                        e['db'] = float(e.get('db') or 0.0) + extra_db
                        try:
                            e['archivo'] = str(OG.ruta_larga(_con_ganancia(e['archivo'], e.get('db', 0.0))))
                            e['db'] = 0.0
                        except Exception:
                            e['archivo'] = str(OG.ruta_larga(_copia_de_usuario(e['archivo'])))
                        sonidos.append(e)
        except Exception as e:
            try:
                import registro
                registro.aviso(f'Motions completo no se pudo hacer: {type(e).__name__}: {e}', 'motions')
            except Exception:
                pass
    try:                                                           # v5.5.8: el vigilante con ffmpeg: nada roto, vacío ni incompleto llega a Resolve
        import vigilante_pro as VG
        VG.revisar_clips(graficos, fps)
    except Exception:
        pass
    datos = {'fps': fps, 'inicio': info['base'], 'graficos': graficos, 'persona': persona, 'sonidos': sonidos, 'cache': True,
             'captions_propios': bool(cap_t5 and subs and subs_ok >= 0.9 * len(subs)), 'color_claves': color_claves,
             'dividida': [[int(round(d['ini'] * fps)), int(round(d['fin'] * fps)), round(d['bajar'] * H, 1)] for d in divididas
                          if any(p.get('remotion') == 'EscenaT5' and abs(p['ini'] - d['ini']) < 1e-3 and rm_hechos.get(str(rm_salida.get(id(p))))
                                 for p in plan['piezas'])],
             'broll': [{k: v for k, v in t.items() if k != '_s'} for t in tomas], 'encima': encima, 'mover': mover, 'punch': punch,
             'sin_emoji': sin_emoji, 'gris': gris, 'gris_foco': gris_foco, 'zoom': zoom,
             'resumen': plan.get('resumen', '')}
    try:                                                              # v5.5.2, el rectificador: riser solo en la intro, cada sonido con su porqué, una cámara
        import rectificador
        motivos = rectificador.pro_final(datos, fps, {'eventos': plan.get('_fx_eventos') or []})
        if motivos:
            plan['_rectificado'] = motivos
            decir(f'Edición PRO: el rectificador quitó {len(motivos)} cosas que no iban')
    except Exception:
        pass
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
    limpiar_cache(conservar=carpeta)
    decir('Edición PRO: colocando la edición en Resolve' + (' (Magic Mask)…' if (persona or encima) and usar_magic else '…'))
    if info.get('via') == 'mcp':
        import resolve_mcp
        script = carpeta_recursos() / 'colocar_pro.py'
        if os.environ.get('CINECAPTIONS_TRAZA_PRO'):                    # (pruebas: un envoltorio que anota cada paso en un archivo)
            script = Path(os.environ['CINECAPTIONS_TRAZA_PRO'])
        ok, mensaje = resolve_mcp.ejecutar_py(script, timeout=600)
    else:
        import resolve_bridge
        if resolve_bridge.modo_actual() == 'manual' and not resolve_bridge.lanzar_puente_auto():
            return False, 'La Edición PRO en Resolve Free necesita el Puente de CineCaptions abierto en Resolve.'
        ok, mensaje = resolve_bridge.ejecutar('edicion_pro', timeout=600)
    return ok, mensaje or plan.get('resumen', '')


SONIDOS_USUARIO = Path.home() / 'DaVinciSubtitles' / 'edicion_pro_sonidos'      # (no es la caché: los proyectos de Resolve siguen apuntando a ellos)


def _con_ganancia(ruta, db):
    """v5.4.52 (auditoría del render: los efectos sonaban hasta 8 dB POR ENCIMA de la voz): Resolve 21 no aplica el volumen de un clip de audio
    puesto por script (SetProperty('Volume') no existe; es 'AudioVolume' y tampoco lo respeta siempre), así que todos quedaban a 0 dB. Como los
    efectos de GO (sfx_rules.con_volumen), el volumen va DENTRO del archivo: una copia en la carpeta del usuario (nunca la del programa) con la
    ganancia ya aplicada, en estéreo. Se rehace si cambia el original."""
    import av
    import numpy as np
    origen = Path(str(ruta))
    db = round(float(db or 0.0), 1)
    destino = SONIDOS_USUARIO / f'{origen.stem}_v{int(round(db * 10)):+d}.wav'
    if destino.is_file() and destino.stat().st_mtime >= origen.stat().st_mtime:
        return destino
    SONIDOS_USUARIO.mkdir(parents=True, exist_ok=True)
    with av.open(str(origen)) as c:
        st = c.streams.audio[0]
        sr = int(st.rate or 48000)
        rs = av.AudioResampler(format='fltp', layout='stereo', rate=sr)
        partes = [g.to_ndarray() for fr in c.decode(st) for g in rs.resample(fr)]
        partes += [g.to_ndarray() for g in rs.resample(None)]
    x = np.clip(np.concatenate(partes, axis=1) * (10 ** (db / 20.0)), -1.0, 1.0)
    tmp = destino.with_name(destino.stem + '.tmp.wav')
    with av.open(str(tmp), 'w', format='wav') as o:
        s = o.add_stream('pcm_s16le', rate=sr)
        s.layout = 'stereo'
        fr = av.AudioFrame.from_ndarray((x.T.reshape(1, -1) * 32767.0).astype(np.int16), format='s16', layout='stereo')
        fr.sample_rate = sr
        for pk in s.encode(fr):
            o.mux(pk)
        for pk in s.encode():
            o.mux(pk)
    tmp.replace(destino)
    return destino


def _copia_de_usuario(ruta):
    """Resolve vigila la carpeta de cada medio que importa y no deja reemplazarla mientras está abierto: si un sonido saliera de la carpeta del
    programa, el instalador fallaría («Acceso denegado a …/Programs/CineCaptions», v5.4.51). Se le da una COPIA en la carpeta del usuario
    (como efectos_visuales._copia_de_usuario); se rehace si falta o cambió de tamaño."""
    r = Path(str(ruta))
    try:
        from sfx_rules import base_recursos
        Path(r).resolve().relative_to(Path(base_recursos()).resolve())
    except Exception:
        return r                                                       # ya es del usuario (o no se sabe): tal cual
    try:
        destino = SONIDOS_USUARIO / r.parent.name / r.name
        if not destino.is_file() or destino.stat().st_size != r.stat().st_size:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(r, destino)
        return destino
    except Exception:
        return r


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


def limpiar_cache(maximo_mb=1500, conservar=None):
    """Borra lo más viejo de ~/DaVinciSubtitles/edicion_pro si pasa de `maximo_mb` (los .ograf y los recortes se rehacen solos). NUNCA la carpeta
    `conservar` (la del video que se acaba de editar): v5.4.52, con muchas pasadas del mismo video esa carpeta sola pasaba del tope y se borraban
    los clips recién hechos (Resolve «no colocó ningún gráfico»)."""
    try:
        guardar = Path(str(conservar)).resolve() if conservar else None
        cajas = sorted((d for d in CARPETA.iterdir() if d.is_dir() and d.name not in ('modelos', 'pruebas')
                        and (guardar is None or d.resolve() != guardar)), key=lambda d: d.stat().st_mtime)
        total = sum(f.stat().st_size for d in cajas for f in d.rglob('*') if f.is_file())
        while cajas and total > maximo_mb * 1e6:
            d = cajas.pop(0)
            tam = sum(f.stat().st_size for f in d.rglob('*') if f.is_file())
            import shutil
            shutil.rmtree(d, ignore_errors=True)
            total -= tam
    except Exception:
        pass
