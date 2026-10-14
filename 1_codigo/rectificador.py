# CineCaptions · By Cinema Productions
# 1_codigo/rectificador.py — v5.5.2: el RECTIFICADOR. Lo último antes de tocar Resolve: junta lo que planearon los Efectos (efectos_visuales) y la
# Edición PRO (edicion_pro) y quita lo que se pisa o no tiene sentido, para que la edición no tenga errores visuales ni sonidos que no van:
#   · UNA sola cámara: con la PRO completa, los Efectos no meten su zoom lento / temblor / zoom en los cortes (la PRO pone sus punch-ins y sus
#     transiciones con zoom); un punch-in no cae encima de una transición con zoom.
#   · Nada encima de otra cosa: los iconos, números, pegatinas, énfasis y B-roll de los Efectos no salen mientras hay un gráfico, una escena o un
#     B-roll de la PRO (ni a menos de 0,6 s), ni en el último medio segundo.
#   · El riser SOLO en la intro: ninguno a mitad del video (con su golpe); si los Efectos ya ponen el riser de la intro, la PRO no pone otro.
#   · Cada sonido con su porqué: un whoosh / textura de la PRO sin un gráfico, corte, zoom o B-roll que entre a la vez se quita; dos sonidos en el
#     mismo instante, se queda uno.
"""
    efectos_con_pro(fx_plan, pro_plan, duracion=None) -> [motivos]     (cambia fx_plan['eventos'])
    pro_final(datos, fps, fx_plan=None) -> [motivos]                   (cambia datos['sonidos'], datos['punch'], datos['zoom'])
"""
from __future__ import annotations

INTRO_MAX_S = 4.0                 # un riser solo puede acabar antes de esto (la intro / el gancho)
AIRE_S = 0.6                      # aire mínimo entre un efecto y un gráfico de la PRO
ENCIMA = ('icono', 'numero', 'pegatina', 'enfasis', 'overlay', 'propio', 'broll')
DUR_EFECTO = {'icono': 2.2, 'numero': 2.0, 'pegatina': 2.0, 'enfasis': 1.6, 'overlay': 3.0, 'propio': 2.5, 'broll': 3.0}
PRIORIDAD_SONIDO = {'PRO-HIT': 3, 'PRO-RISER': 2, 'PRO-WHOOSH': 1, 'PRO-TEXTURA': 0}


def _ventanas_pro(pro_plan):
    """Los tramos [(ini, fin)] en los que la PRO ya pone algo en pantalla (gráficos, escenas, la persona recortada) o un B-roll."""
    out = []
    for p in (pro_plan or {}).get('piezas') or []:
        if p.get('quitar') or p.get('pieza') in ('subtitulo', 'velo_caption'):
            continue
        out.append((float(p['ini']), float(p['fin'])))
    for b in (pro_plan or {}).get('broll') or []:
        try:
            a = float(b.get('ini', b.get('t', 0.0)))
            out.append((a, a + float(b.get('dur', 3.0))))
        except Exception:
            pass
    return out


def efectos_con_pro(fx_plan, pro_plan, duracion=None):
    """Lo de los Efectos que se pisa con la Edición PRO, fuera. Devuelve los motivos (para el Registro)."""
    if not fx_plan or not pro_plan:
        return []
    eventos = fx_plan.get('eventos') or []
    completa = bool(pro_plan.get('piezas')) and not pro_plan.get('ligero')
    ventanas = _ventanas_pro(pro_plan)
    dur = float(duracion or fx_plan.get('duracion') or 0.0)
    motivos, quedan = [], []
    for e in eventos:
        tipo, ini = e.get('tipo'), float(e.get('ini') or 0.0)
        if tipo == 'v1' and completa:
            quitado = [k for k in ('zoom', 'temblor', 'zoom_saltos') if e.get(k)]
            for k in ('zoom', 'temblor', 'zoom_saltos'):
                e[k] = None
            e['saltos'], e['golpes'] = [], []
            if pro_plan.get('estilo_t5') or pro_plan.get('tema5'):            # (el Tema 5 hace sus transiciones con zoom en los cortes)
                if e.get('transicion'):
                    quitado.append('transición en los cortes')
                e['transicion'], e['cortes'] = None, []
            if quitado:
                motivos.append('Efectos: sin ' + ', '.join(quitado) + ' (la Edición PRO lleva la cámara: una sola)')
            if not (e.get('transicion') or e.get('fondo') or e.get('zoom_intro')):
                continue
        elif tipo in ENCIMA:
            fin = ini + float(e.get('dur') or DUR_EFECTO.get(tipo, 2.0))
            if any(ini < b + AIRE_S and a - AIRE_S < fin for a, b in ventanas):
                motivos.append(f'Efectos: fuera el {tipo} de {ini:.1f} s (encima de un gráfico de la PRO)')
                continue
            if dur and ini > dur - 0.5:
                motivos.append(f'Efectos: fuera el {tipo} de {ini:.1f} s (en el último medio segundo)')
                continue
        elif tipo == 'sonido' and ini > INTRO_MAX_S:
            motivos.append(f'Efectos: fuera el riser de {ini:.1f} s (solo en la intro)')
            continue
        quedan.append(e)
    fx_plan['eventos'] = quedan
    return motivos


def pro_final(datos, fps, fx_plan=None):
    """Los sonidos y zooms de la PRO, ya en fotogramas, revisados: riser solo en la intro (sin repetir el de los Efectos), cada sonido con algo que
    entra a la vez, nada duplicado y ningún punch-in encima de una transición con zoom. Devuelve los motivos."""
    fps = float(fps or 30.0)
    motivos = []
    sonidos = list(datos.get('sonidos') or [])
    hay_riser_fx = any(e.get('tipo') == 'sonido' and float(e.get('ini') or 0) <= 0.5 for e in (fx_plan or {}).get('eventos') or [])
    # --- risers (y su golpe) solo en la intro
    quitar_hit, transiciones = [], set()
    queda = []
    for s in sonidos:
        if s.get('pista') == 'PRO-RISER':
            fin = (int(s['ini']) + float(s.get('dur') or 2.0) * fps) / fps
            if fin > INTRO_MAX_S + 1.0 or hay_riser_fx:
                motivos.append(f"PRO: fuera el riser de {int(s['ini']) / fps:.1f} s ({'ya está el riser de la intro' if hay_riser_fx else 'a mitad del video'})")
                quitar_hit.append(fin)
                transiciones.add(str(s.get('que') or '').split('·', 1)[-1].strip())      # «riser · video → escena» → su golpe es «hit · video → escena»
                continue
        queda.append(s)
    sonidos = [s for s in queda if not (s.get('pista') == 'PRO-HIT' and (str(s.get('que') or '').split('·', 1)[-1].strip() in transiciones
                                                                          or any(abs(int(s['ini']) / fps - t) < 1.5 for t in quitar_hit)))]
    if len(sonidos) < len(queda):
        motivos.append(f'PRO: fuera {len(queda) - len(sonidos)} golpe(s) que iban con esos risers')
    # --- cada whoosh / textura con algo que entre a la vez (±0,4 s)
    anclas = [int(g['ini']) / fps for g in datos.get('graficos') or []]
    anclas += [int(z[0]) / fps for z in datos.get('zoom') or []] + [int(p[0]) / fps for p in datos.get('punch') or [] if isinstance(p, (list, tuple))]
    anclas += [int(b.get('ini', 0)) / fps for b in datos.get('broll') or [] if isinstance(b, dict)]
    anclas += [int(d[0]) / fps for d in datos.get('dividida') or []] + [int(g[0]) / fps for g in datos.get('gris') or [] if isinstance(g, (list, tuple))]
    anclas += [int(e.get('ini', 0)) / fps for e in datos.get('encima') or [] if isinstance(e, dict)]
    con_razon = []
    for s in sonidos:
        t = int(s['ini']) / fps
        if s.get('pista') in ('PRO-WHOOSH', 'PRO-TEXTURA') and anclas and not any(abs(t - a) < 0.4 or (a - 0.6 < t < a + 0.15) for a in anclas):
            motivos.append(f"PRO: fuera el sonido «{s.get('que', '')}» de {t:.1f} s (no entra nada en pantalla a la vez)")
            continue
        con_razon.append(s)
    # --- dos sonidos de la MISMA pista en el mismo instante: se queda uno (whoosh + pop de una tarjeta son capas, no duplicados)
    con_razon.sort(key=lambda s: (int(s['ini']), -PRIORIDAD_SONIDO.get(s.get('pista'), 0)))
    finales = []
    for s in con_razon:
        if any(f.get('pista') == s.get('pista') and abs(int(s['ini']) - int(f['ini'])) < 0.15 * fps for f in finales[-4:]):
            motivos.append(f"PRO: fuera el sonido duplicado de {int(s['ini']) / fps:.1f} s")
            continue
        finales.append(s)
    datos['sonidos'] = finales
    # --- un punch-in no cae encima de una transición con zoom (una sola cámara)
    zooms = [int(z[0]) for z in datos.get('zoom') or []]
    if zooms and datos.get('punch'):
        antes = len(datos['punch'])
        datos['punch'] = [p for p in datos['punch'] if not (isinstance(p, (list, tuple)) and any(abs(int(p[0]) - z) < 0.8 * fps for z in zooms))]
        if len(datos['punch']) < antes:
            motivos.append(f"PRO: fuera {antes - len(datos['punch'])} punch-in(s) encima de una transición con zoom")
    return motivos
