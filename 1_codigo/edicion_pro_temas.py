# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_temas.py — el «pase ligero» de los Temas 1–4 (pedido del usuario, v5.4.51): sus captions (los Text+ de su pack, que se
# respetan) se ven mejor sin necesidad de la Edición PRO completa:
#   * legibilidad: en un video claro, un velo oscuro suave detrás de cada pila de captions (Remotion «VeloCaptionT», pista PRO-VELO);
#   * acompañantes: la animación pequeña bajo el caption del Tema 5 (país, saludo, redes, cifra, emoji 3D del concepto);
#   * color según el video: la palabra DESTACADA (rol principal) toma el acento que va con el video (estilo «guion»: Temas 2 y 4);
#   * nunca tapar la cara: la regla de la cara de la PRO (edicion_pro._captions_sin_cara) también sin la PRO.
"""
    piezas(info, video, idioma, W, H, fps, mover, plan) -> piezas para el plan (velos + acompañantes)
    color_claves(info, video, fps) -> {'rgb': [r, g, b], 'momentos': [fotograma absoluto, ...]} o None
"""
import json
from pathlib import Path

VELO_CAPTIONS = False                                                     # v5.4.52: el velo ovalado detrás de los captions, apagado


def _hex_a_rgb(h):
    h = h.lstrip('#')
    return [round(int(h[i:i + 2], 16) / 255.0, 4) for i in (0, 2, 4)]


def _con_emoji():
    """Los tramos [ini, fin] (s) en que los captions de GO llevan su emoji."""
    try:
        import edicion_pro as EP
        m = json.loads(EP.MANIFIESTO.read_text(encoding='utf-8'))
        out = []
        for t in m.get('tracks') or []:
            if not t.get('data_path'):
                continue
            for c in json.loads(Path(t['data_path']).read_text(encoding='utf-8')).get('cues') or []:
                if isinstance(c, dict) and c.get('emoji'):
                    a = float(c.get('emoji_ini', c.get('start', 0)) or 0)
                    out.append((a - 0.3, float(c.get('emoji_fin', c.get('end', a + 1)) or a + 1) + 0.3))
        return out
    except Exception:
        return []


def piezas(info, video, idioma, W, H, fps, mover, plan, maximo=None):
    """`maximo` (v5.5.4, Temas 1–4 CON la Edición PRO): como mucho tantos acompañantes, repartidos por el video (la PRO ya pone sus motions)."""
    out = _piezas(info, video, idioma, W, H, fps, mover, plan)
    if maximo is None:
        return out
    acomp = [p for p in out if p.get('pieza') != 'velo_caption']
    if len(acomp) > maximo:
        paso = len(acomp) / float(maximo)
        elegidos = [acomp[int(k * paso + paso / 2)] for k in range(maximo)]
        out = [p for p in out if p.get('pieza') == 'velo_caption' or p in elegidos]
    return out


def _piezas(info, video, idioma, W, H, fps, mover, plan):
    import edicion_pro as EP
    import edicion_pro_tema5 as T5
    import edicion_pro_tema5_acomp as AC
    bloques = EP._bloques_captions()
    if not bloques:
        return []
    subir = {round(int(m['ini']) / fps, 1): float(m.get('subir') or 0.0) for m in mover or []}     # mover va en fotogramas desde el inicio
    out = []
    # 1) legibilidad: velos (solo si el video es claro a la altura de los captions); bloques seguidos a la misma altura, un solo velo
    # v5.4.52: APAGADO (el velo ovalado detrás del caption se veía como una sombra fea); las letras ya llevan su contorno y sombra
    if VELO_CAPTIONS and T5.claro(video):
        velos = []
        for b in bloques:
            s = subir.get(round(b['ini'], 1), 0.0) / H
            y = ((b['arriba'] + b['abajo']) / 2.0 - s) * 100.0
            alto = max(4.0, (b['abajo'] - b['arriba']) * 100.0)
            xs = b.get('xs') or [0.5]
            ancho = max(45.0, min(98.0, (max(xs) - min(xs)) * 100.0 + 40.0))
            if velos and b['ini'] - velos[-1]['fin'] < 0.35 and abs(velos[-1]['y'] - y) < 3.0:
                v = velos[-1]
                v['fin'] = b['fin']
                v['alto'], v['ancho'] = max(v['alto'], alto), max(v['ancho'], ancho)
            else:
                velos.append({'ini': b['ini'], 'fin': b['fin'], 'y': y, 'alto': alto, 'ancho': ancho})
        for v in velos:
            out.append({'pieza': 'velo_caption', 'remotion': 'VeloCaptionT', 'capa': 'velo', 'ini': round(max(0.0, v['ini'] - 0.1), 3),
                        'fin': round(v['fin'] + 0.15, 3), 'motivo': 'legibilidad (video claro)',
                        'valores': {'y': round(v['y'], 1), 'alto': round(v['alto'], 1), 'ancho': round(v['ancho'], 1), 'fuerza': 0.42}})
    # 2) acompañantes bajo la pila de captions
    try:
        conv = []
        for b in bloques:
            ps = [{'texto': str(x), 't': round(max(0.0, float(t) - b['ini']), 3)} for x, t in b.get('palabras') or [] if str(x).strip()]
            if ps:
                conv.append({'ini': b['ini'], 'fin': b['fin'], 'palabras': ps, '_b': b})
        acento = T5.acento_de_video(video)
        aspecto = 'cristal'
        dur = max(b['fin'] for b in bloques)
        ocupado = [(p['ini'] - 0.2, p['fin'] + 0.2) for p in plan.get('piezas') or [] if p.get('capa') in ('delante', 'fondo')]
        ocupado += _con_emoji()                                          # donde el tema ya enseña su emoji, no: serían dos cosas a la vez
        for c in AC.acompanantes(conv, idioma, ocupado, acento, aspecto, dur, frozenset(T5.DEBILES)):
            b = next((x['_b'] for x in conv if abs(x['ini'] - c['_bajo'][0]) < 0.05), None)
            if b is None:
                continue
            s = subir.get(round(b['ini'], 1), 0.0) / H
            y = (b['abajo'] - s) * 100.0 + 5.5
            if y > 86.0:
                continue                                                 # no cabe debajo sin salirse por abajo
            c['valores']['y'] = round(y, 1)
            if c['fin'] > b['fin'] + 0.15 and b['fin'] + 0.15 - c['ini'] >= 1.2:
                c['fin'] = round(b['fin'] + 0.15, 3)                     # v5.5.4: se va con SU caption
            out.append(c)
    except Exception:
        pass
    return out


def color_claves(info, video, fps):
    """La palabra destacada (rol principal) de los captions «guion» (Temas 2 y 4), en el acento del video: el color y los fotogramas en que entra cada una."""
    try:
        import edicion_pro as EP
        import edicion_pro_tema5 as T5
        m = json.loads(EP.MANIFIESTO.read_text(encoding='utf-8'))
        pistas = [t for t in m.get('tracks') or [] if t.get('style') == 'guion' and t.get('data_path')]
        if not pistas:
            return None
        base = int(info.get('base', info.get('inicio', 0)))
        momentos = []
        for t in pistas[:1]:
            pack = str(((t.get('plantilla') or {}).get('pack')) or '')
            roles = {'main', 'complement'} if pack == 'Referencia' else {'main'}      # Tema 2: la negrita es lo destacado; Tema 4: solo la grande
            for c in json.loads(Path(t['data_path']).read_text(encoding='utf-8')).get('cues') or []:
                for r in c.get('runs') or []:
                    if isinstance(r, dict) and r.get('rol') in roles and isinstance(r.get('t'), (int, float)):
                        momentos.append(base + int(round(float(r['t']) * fps)))
        if not momentos:
            return None
        return {'rgb': _hex_a_rgb(T5.acento_de_video(video)), 'momentos': sorted(set(momentos))}
    except Exception:
        return None
