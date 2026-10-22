# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_sesion.py — «AI Sound Director», FASE 6: lo que la página necesita (leer el diseño de un video, controles, retocar, oír, aplicar).
"""
La página (director_sonido_ui) solo pinta; todo esto corre en hilos de trabajo (correr_en_hilo) y nada aquí toca Qt.

    resumen(video)                    lo que pinta la página: cabecera (tema, AI Sonic Style, Sound Score), estado (voz, ruido, música, ambiente,
                                      sonido de motions, mezcla, master), carriles (voz, cortes, captions, música, ambiente) y los eventos (los que
                                      suenan y los que la IA dejó en silencio, cada uno con su diseño, su porqué y su importancia)
    controles() / poner_control(k, v) AUTO o lo que eligió el usuario (prefs `ai_sound_controles`): estilo, intensidad, densidad, voz, música, ambiente
    retocar(video, clave, accion)     SILENCIAR / BLOQUEAR / REGENERAR / MENOS:… / MÁS:… sobre UN evento (solo ese cambia: los demás salen iguales y
                                      sus WAV se reutilizan porque el nombre es el contenido)
    redisenar(video, desde, hasta)    «Rediseñar sonido»: otra ronda de variaciones para todo lo no bloqueado, o solo un tramo (una sección)
    previa(video, cual, desde, hasta) WAV de la mezcla ORIGINAL o AI SOUND de ese tramo (lo que suma Resolve a 0 dB) · reproducir / detener
    aplicar(video, offset_frames)     pone en el timeline ABIERTO de Resolve los sonidos y la voz del director (como GO, plan 'solo_ai')
    interpretar(texto) / ejecutar     «Dile a AI Sound Director qué quieres cambiar»: qué entendió y qué cambia (sin parámetros a la vista)
"""
import random
import re
import sys
import time
import unicodedata
from copy import deepcopy
from pathlib import Path

import numpy as np

import director_sonido as D
import director_sonido_estado as E

SR = 48000
CONTROLES = ('estilo', 'intensidad', 'densidad', 'voz', 'musica', 'ambiente')
NIVELES = ('auto', 'poco', 'medio', 'mucho')                             # (música y ambiente: también 'nada')
ESTILOS = ('auto', 'limpio', 'cinematico', 'energico', 'minimo')
DISENO = {'golpe': 'Golpe diseñado', 'whoosh': 'Whoosh', 'giro': 'Giro con slap', 'riser': 'Riser', 'trazo': 'Trazo de rotulador',
          'acento': 'Acento tonal (el motivo del video)', 'tick': 'Toque de interfaz', 'pop': 'Pop'}
MENOS = (('quitar_capa', 'Quitar una capa'), ('otro_sfx', 'Otro sonido'), ('mas_corto', 'Más corto'), ('mas_limpio', 'Más limpio'),
         ('menos_graves', 'Menos graves'), ('menos_transitorio', 'Menos ataque'), ('mas_simple', 'Más simple'), ('mas_bajo', 'Más bajo'))
MAS = (('otra_capa', 'Otra capa'), ('profundidad', 'Más profundidad'), ('mejor_transitorio', 'Mejor ataque'), ('otra_textura', 'Otra textura'),
       ('mejor_impacto', 'Más impacto'), ('mas_movimiento', 'Más movimiento'), ('mas_alto', 'Más alto'))
CONTEXTO = {'INTERIOR': 'Interior', 'QUIET_INTERIOR': 'Interior tranquilo', 'ROOM': 'Habitación', 'OFFICE': 'Oficina', 'STUDIO': 'Estudio',
            'STREET': 'Calle', 'CITY': 'Ciudad', 'OUTDOOR': 'Exterior', 'NATURE': 'Naturaleza', 'FOREST': 'Bosque', 'PARK': 'Parque',
            'CROWD': 'Gente', 'CAFE': 'Café', 'EVENT': 'Evento', 'WIND': 'Viento', 'WATER': 'Agua', 'TRAFFIC': 'Tráfico',
            'MUSIC_BED': 'Música de fondo'}


def _musica_en_video(estado):
    return bool((((estado.get('analisis') or {}).get('musica') or {}).get('en_la_fuente') or {}).get('presente'))


def _escenas_juntas(escenas):
    """Las escenas seguidas con el mismo entorno y la misma decisión, en un solo tramo: [(ini, fin, contexto, decision)]."""
    out = []
    for e in escenas or []:
        a, b, c, d = float(e.get('ini') or 0), float(e.get('fin') or 0), e.get('contexto'), e.get('decision')
        if out and out[-1][2] == c and out[-1][3] == d:
            out[-1][1] = b
        else:
            out.append([a, b, c, d])
    return [tuple(x) for x in out]


# ------------------------------------------------------------------------------------------------------------------------------ lectura
def _palabras_a_tramos(palabras, hueco=0.35):
    tramos = []
    for p in palabras or []:
        a, b = float(p.get('start') or 0.0), float(p.get('end') or 0.0)
        if tramos and a - tramos[-1][1] <= hueco:
            tramos[-1][1] = max(tramos[-1][1], b)
        else:
            tramos.append([a, b])
    return [(round(a, 2), round(b, 2)) for a, b in tramos]


def _nombre_evento(e, captions):
    o = e.get('origen')
    if o in ('caption', 'dato'):
        c = next((c for c in captions if c.get('cue') == e.get('ref')), None)
        texto = f"«{c['texto']}»" if c and c.get('texto') else 'caption'
        return ('Dato ' if o == 'dato' else '') + texto
    if o == 'gancho':
        return 'Gancho'
    if o == 'cierre':
        return 'Cierre'
    if o == 'corte':
        return f"Corte a {e['ancla']:.1f} s".replace('.', ',')
    que = str(e.get('por_que') or '').split(':')
    return (que[0] + (':' + que[1] if len(que) > 1 and que[0] in ('PRO', 'Efectos') else '')).strip()[:48] or 'Motion'


def _nota_voz(estado):
    voz, a = estado.get('voz') or {}, (estado.get('analisis') or {}).get('voz') or {}
    despues = estado.get('voice_quality_after') or {}
    snr = despues.get('snr_db') if voz.get('archivo') and despues else a.get('snr_db')
    try:
        snr = float(snr)
    except (TypeError, ValueError):
        snr = None
    grado = 'Excelente' if snr is not None and snr >= 30 else ('Buena' if snr is not None and snr >= 18 else 'Necesita atención')
    if voz.get('archivo'):
        antes = estado.get('voice_quality_before') or {}
        detalle = f"Limpiada ({voz.get('backend')}): fondo {antes.get('suelo_ruido_db')} → {despues.get('suelo_ruido_db')} dBFS"
    else:
        detalle = str(voz.get('motivo') or 'La voz original se queda')
    if grado == 'Necesita atención' and _musica_en_video(estado):       # el «ruido» es la música que el video trae mezclada: la voz se entiende
        grado = 'Buena'
        detalle = 'Con la música del video mezclada debajo (no se separa ni se toca). ' + detalle
    return {'clave': 'voz', 'titulo': 'Voz', 'valor': grado, 'detalle': detalle, 'nivel': 'ok' if grado != 'Necesita atención' else 'aviso'}


def _nota_ruido(estado):
    v = (estado.get('analisis') or {}).get('voz') or {}
    ruido = str(v.get('ruido') or '—')
    problemas = '; '.join((v.get('problemas') or [])[:2])
    if _musica_en_video(estado) and ruido in ('alto', 'moderado'):
        return {'clave': 'ruido', 'titulo': 'Ruido', 'valor': 'Es música, no ruido', 'nivel': 'ok',
                'detalle': 'Lo que suena bajo la voz es la música del video: se deja.' + (f' ({problemas})' if problemas else '')}
    despues = estado.get('voice_quality_after') or {}
    if (estado.get('voz') or {}).get('archivo') and despues:
        return {'clave': 'ruido', 'titulo': 'Ruido', 'valor': f'{ruido.capitalize()} → controlado', 'nivel': 'ok',
                'detalle': f"Fondo {(estado.get('voice_quality_before') or {}).get('suelo_ruido_db')} → {despues.get('suelo_ruido_db')} dBFS" +
                           (f' · {problemas}' if problemas else '')}
    return {'clave': 'ruido', 'titulo': 'Ruido', 'valor': ruido.capitalize(), 'nivel': 'aviso' if ruido == 'alto' else 'ok',
            'detalle': problemas or 'Sin problemas medidos'}


def _nota_musica(estado):
    m = ((estado.get('analisis') or {}).get('musica') or {})
    final = estado.get('music_decision') or {}
    est = final.get('estado') or (m.get('estado_sugerido') or {}).get('estado') or 'NO_MUSIC_REQUIRED'
    textos = {'NO_MUSIC_REQUIRED': 'No hace falta', 'KEEP_EXISTING': 'La del video se queda', 'ADJUST_EXISTING': 'La del video, ajustada',
              'ADD_NEW': 'Añadida', 'REPLACE_ONLY_IF_ALLOWED': 'Se cambiaría solo con permiso'}
    valor = textos.get(est, est)
    detalle = final.get('por_que') or (m.get('estado_sugerido') or {}).get('por_que') or ''
    deseado = (m.get('estado_sugerido') or {}).get('deseado')
    if est == 'NO_MUSIC_REQUIRED' and deseado == 'ADD_NEW' and not final:
        valor = 'Sin música (falta un proveedor autorizado)'
    return {'clave': 'musica', 'titulo': 'Música', 'valor': valor, 'detalle': str(detalle)[:160], 'nivel': 'ok'}


def _nota_ambiente(estado):
    amb = estado.get('ambience_decision') or (estado.get('analisis') or {}).get('ambiente') or {}
    esc = amb.get('escenas') or []
    nombres = {'KEEP_ORIGINAL_AMBIENCE': 'se conserva', 'CLEAN_ORIGINAL_AMBIENCE': 'se limpia', 'ADD_SUBTLE_AMBIENCE': 'ambiente sutil',
               'REPLACE_AMBIENCE': 'se cambia', 'REDUCE_AMBIENCE': 'se reduce', 'LEAVE_SILENT': 'sin añadir nada'}
    partes = []
    for _a, _b, ctx, dec in _escenas_juntas(esc)[:4]:
        partes.append(f"{CONTEXTO.get(ctx, str(ctx or '').title())} → {nombres.get(dec, str(dec or '').lower())}")
    valor = 'Preservado' if all(e.get('decision') in ('KEEP_ORIGINAL_AMBIENCE', 'CLEAN_ORIGINAL_AMBIENCE', 'LEAVE_SILENT') for e in esc) else 'Diseñado'
    return {'clave': 'ambiente', 'titulo': 'Ambiente', 'valor': valor if esc else 'No hace falta', 'detalle': ' · '.join(partes) or str(amb.get('resumen') or ''),
            'nivel': 'ok'}


def resumen(video):
    """Todo lo que la página pinta para ESTE video (ver el docstring del módulo). {'hay': False, …} si GO aún no pasó con el director."""
    video = str(video or '')
    activo = D.activo()
    estado = E.cargar(video) if video and Path(video).is_file() else {}
    ultimo_disponible = None
    if estado.get('sound_events') is None:
        ultimo = str(E.general().get('ultimo_video') or '')
        if ultimo and ultimo != video and Path(ultimo).is_file() and E.cargar(ultimo).get('sound_events') is not None:
            ultimo_disponible = {'video': ultimo, 'nombre_video': Path(ultimo).name}
    base = {'video': video, 'nombre_video': Path(video).name if video else '', 'otro_video': False, 'activo': activo,
            'controles': deepcopy(D.controles()), 'hay': False, 'puede_aplicar': False, 'pendiente_resolve': False,
            'en_resolve': None, 'sound_score_viejo': False, 'destino': {}, 'ultimo_disponible': ultimo_disponible}
    if not video or not Path(video).is_file():
        return dict(base, motivo='Elige un video en Inicio y haz GO: AI Sound Director lo escucha y diseña su sonido.')
    if estado.get('sound_events') is None:
        return dict(base, motivo='Haz GO con este video (con AI Sound Director encendido) y aquí verás cómo lo diseñó.')
    a = estado.get('analisis') or {}
    ctx = D.cargar_contexto(video) or {}
    perfil = a.get('perfil') or {}
    et = perfil.get('etiquetas') or {}
    s = estado.get('sfx_summary') or {}
    estilo_usuario = (s.get('controles') or {}).get('estilo')
    sonic = ' · '.join(x for x in (str(et.get('tonal') or '').capitalize(), f"transitorios {et.get('transitorios')}" if et.get('transitorios') else '',
                                   f"reverb {et.get('reverb')}" if et.get('reverb') else '') if x)
    captions = estado.get('caption_decisions') or []
    puestos = {p.get('id'): p for p in estado.get('sound_events_placed') or []}
    ajustes = estado.get('ajustes') or {}
    eventos = []
    for e in estado.get('sound_events') or []:
        p = puestos.get(e.get('id')) or {}
        aj = ajustes.get(e.get('clave') or '') or {}
        eventos.append({'clave': e.get('clave'), 'id': e.get('id'), 'tipo': e.get('tipo'), 't': e.get('t'), 'ancla': e.get('ancla'), 'dur': e.get('dur'),
                        'pista': e.get('pista'), 'decision': e.get('decision'), 'suena': e.get('decision') == 'GENERATE' and bool(p),
                        'por_que': e.get('por_que'), 'importancia': e.get('importancia'), 'origen': e.get('origen'), 'ref': e.get('ref'),
                        'nombre': _nombre_evento(e, captions), 'diseno': DISENO.get(e.get('tipo'), e.get('tipo')),
                        'con_capa': 'capa' in str(p.get('fuente') or ''), 'con_clic': 'clic' in str(p.get('fuente') or ''),
                        'fuente': p.get('fuente'), 'archivo': p.get('archivo'), 'bloqueado': bool(aj.get('bloqueado')), 'silenciado': bool(aj.get('silenciar')),
                        'material': (p.get('eleccion') or {}).get('elegido')})
    n_suenan = sum(1 for e in eventos if e['suena'])
    dur = float((a.get('voz') or {}).get('duracion') or 0.0) or max([float(p.get('end') or 0) for p in ctx.get('palabras') or []] or [0.0])
    mezcla = estado.get('mix') or {}
    notas = [_nota_voz(estado),
             _nota_ruido(estado),
             _nota_musica(estado), _nota_ambiente(estado),
             {'clave': 'motion', 'titulo': 'Sonido de motions', 'valor': f'{n_suenan} sonidos diseñados',
              'detalle': f"{s.get('con_sonido', 0)} de {s.get('captions', 0)} captions con sonido; el resto, en silencio a propósito", 'nivel': 'ok'},
             {'clave': 'mezcla', 'titulo': 'Mezcla', 'valor': mezcla.get('valor') or 'Bajo la voz',
              'detalle': mezcla.get('detalle') or f"Cada sonido a su nivel bajo la voz ({s.get('nivel_voz_db')} dBFS)", 'nivel': mezcla.get('nivel') or 'ok'},
             {'clave': 'master', 'titulo': 'Master', 'valor': (estado.get('master') or {}).get('valor') or '—',
              'detalle': (estado.get('master') or {}).get('detalle') or 'Se mide la mezcla completa (LUFS, true peak)', 'nivel': (estado.get('master') or {}).get('nivel') or 'info'},
             _nota_material()]
    pro = [e for e in estado.get('pro_sound_events') or []]
    if pro:
        n_pro = sum(1 for e in pro if e.get('decision') == 'GENERATE')
        notas[4] = dict(notas[4], detalle=notas[4]['detalle'] + f" · motions de la PRO: {n_pro} rehechos por el director, {len(pro) - n_pro} en silencio")
    amb = (estado.get('ambience_decision') or a.get('ambiente') or {}).get('escenas') or []
    musica_tramos = []
    if ((a.get('musica') or {}).get('en_la_fuente') or {}).get('presente'):
        musica_tramos.append((0.0, dur, 'del video'))
    if (estado.get('music_decision') or {}).get('estado') == 'ADD_NEW':
        for m in (estado.get('music_decision') or {}).get('tramos') or []:
            musica_tramos.append((float(m[0]), float(m[1]), 'IA'))
    ultimo = estado.get('ultimo_go') or {}
    return dict(base, hay=True, tema=estado.get('tema') or a.get('tema'), sonic_style=sonic, estilo_usuario=estilo_usuario,
                sound_score=estado.get('sound_score'), sound_score_viejo=bool(estado.get('sound_score_viejo')),
                score_partes=deepcopy(estado.get('score_components') or {}), notas=notas, eventos=eventos, duracion=round(dur, 2),
                carriles={'voz': _palabras_a_tramos(ctx.get('palabras')), 'cortes': [round(float(t), 2) for t in ctx.get('cortes') or []],
                          'captions': [(c.get('t'), c.get('decision'), c.get('texto')) for c in captions],
                          'musica': musica_tramos, 'ambiente': [(a_, b_, CONTEXTO.get(c_, str(c_ or '').title()), d_) for a_, b_, c_, d_ in _escenas_juntas(amb)]},
                pro_eventos=[(e.get('t'), e.get('dur'), e.get('tipo'), e.get('decision')) for e in pro],
                puede_aplicar=bool(ultimo.get('con_director')) and _destino_valido(ultimo.get('destino')),
                destino=deepcopy(ultimo.get('destino') or {}), ultimo_go=ultimo.get('fecha'), actualizado=estado.get('actualizado'),
                pendiente_resolve=bool(estado.get('pendiente_resolve')) and bool(ultimo.get('con_director')), en_resolve=estado.get('en_resolve'))


def _nota_material():
    """De dónde saca el director el sonido: cuánto material de las bibliotecas del autor tiene a mano, por categoría."""
    try:
        import director_sonido_biblioteca as B
        r = B.resumen()
    except Exception:
        r = {}
    total = sum(r.values())
    if not total:
        return {'clave': 'material', 'titulo': 'Material', 'valor': 'Hecho a la medida',
                'detalle': 'Sin bibliotecas propias: cada sonido se sintetiza a la medida (añade los tuyos en «Mis sonidos»)', 'nivel': 'info'}
    nombres = (('whoosh', 'whooshes'), ('golpe', 'golpes'), ('riser', 'risers'), ('tonal', 'tonales'), ('ui', 'clics'), ('cama', 'camas de score'),
               ('ambiente', 'ambientes'))
    return {'clave': 'material', 'titulo': 'Material', 'valor': f'{total:,} sonidos de tus bibliotecas'.replace(',', ' '),
            'detalle': ' · '.join(f'{r[k]} {t}' for k, t in nombres if r.get(k)) + ' (Quality Gate a cada uno)', 'nivel': 'ok'}


# ------------------------------------------------------------------------------------------------------------------------------ controles
def controles():
    return D.controles()


def poner_control(clave, valor):
    """Guarda un control de la página (AUTO = se quita la clave) y devuelve los controles."""
    if clave not in CONTROLES:
        return controles()
    import ajustes_ui
    c = dict((ajustes_ui.leer_prefs() or {}).get(D.PREF_CONTROLES) or {})
    if valor in (None, 'auto'):
        c.pop(clave, None)
    else:
        c[clave] = valor
    ajustes_ui.guardar_prefs({D.PREF_CONTROLES: c})
    return controles()


def poner_activo(si):
    import ajustes_ui
    ajustes_ui.guardar_prefs({D.PREF: bool(si)})
    return D.activo()


# ------------------------------------------------------------------------------------------------------------------------------ retocar
def _rehacer(video, al_estado=None, capas=False):
    """Rehace el diseño y los sonidos con los controles, ajustes y ronda de ahora (solo cambia lo que cambió: el resto reutiliza sus WAV); con
    `capas`, también la música y el ambiente (al cambiar sus controles)."""
    estado = E.cargar(video)
    ctx = D.cargar_contexto(video)
    if not ctx or not estado.get('analisis'):
        raise RuntimeError('Haz GO con este video para que AI Sound Director tenga qué rediseñar.')
    if al_estado:
        al_estado('AI Sound Director: rediseñando…')
    nivel = (estado.get('sfx_summary') or {}).get('nivel_voz_db')
    previas = estado.get('mezcla_ajustes') or None                    # (las bajadas del QC se quedan, como un fader)
    sfx = D.preparar_sfx(ctx, estado['analisis'], nivel, mezcla=previas)
    c = D.preparar_capas(ctx, estado['analisis'], float(nivel) + float((previas or {}).get('bus') or 0.0) if nivel is not None else None) if capas else None
    estado = E.cargar(video)
    D._guardar_sfx(estado, sfx)
    if c is not None:
        D._guardar_capas(estado, c)
    estado['sound_score_viejo'] = True                                # el número anterior ya no describe este diseño
    dur = float(((estado.get('analisis') or {}).get('voz') or {}).get('duracion') or 0.0)
    if dur <= 600.0:                                                  # la mezcla y el Sound Score, al día (en un video largo, en el próximo GO)
        try:
            capas_ahora = c or {'musica': {'plan': estado.get('music_plan') or []}, 'ambiente': {'plan': estado.get('ambience_plan') or []}}
            sfx, c2, qc = D.mezclar(ctx, estado['analisis'], estado, sfx, capas_ahora, (estado.get('ultimo_go') or {}).get('evento_voz'), al_estado,
                                    previas=previas)
            D._guardar_sfx(estado, sfx)
            if c2 and (c2.get('musica') or {}).get('estado'):
                D._guardar_capas(estado, c2)
            D._guardar_qc(estado, qc)
            estado['sound_score_viejo'] = False
        except Exception:
            D.fallback('mezcla (página)')
    else:
        estado['sound_score_viejo'] = True
    estado['pendiente_resolve'] = True                                # (lo cambiado aún no está en el timeline: aplicar_al_momento / Aplicar)
    E.guardar(video, estado)
    return resumen(video)


def _evento(estado, clave):
    return next((e for e in estado.get('sound_events') or [] if e.get('clave') == clave), None)


def retocar(video, clave, accion, al_estado=None):
    """Un retoque del inspector sobre el evento `clave`. accion: 'silenciar' | 'bloquear' | 'regenerar' | 'menos:<op>' | 'mas:<op>' (ver MENOS/MAS).
    Devuelve (resumen, texto de lo que hizo)."""
    estado = E.cargar(video)
    e = _evento(estado, clave)
    if e is None:
        raise RuntimeError('Ese sonido ya no está en el diseño: vuelve a elegirlo.')
    ajustes = dict(estado.get('ajustes') or {})
    aj = dict(ajustes.get(clave) or {})
    hecho = ''
    if accion == 'silenciar':
        aj['silenciar'] = not aj.get('silenciar')
        aj.pop('bloqueado', None)
        hecho = 'Silenciado: este momento queda sin sonido.' if aj['silenciar'] else 'Vuelve a sonar.'
    elif accion == 'bloquear':
        if aj.get('bloqueado'):
            aj.pop('bloqueado', None)
            aj.pop('plan', None)
            hecho = 'Desbloqueado: los rediseños pueden cambiarlo.'
        else:
            plan = next((x for x in estado.get('sfx_plan') or [] if (x.get('ai') or {}).get('clave') == clave), None)
            if plan is None:
                raise RuntimeError('Solo se bloquea un sonido que suena.')
            aj['bloqueado'], aj['plan'] = True, plan
            hecho = 'Bloqueado: «Rediseñar» y los cambios de controles no lo tocan.'
    else:
        if aj.get('bloqueado'):
            raise RuntimeError('Está bloqueado: desbloquéalo para cambiarlo.')
        aj.pop('silenciar', None)
        p = dict(aj.get('params') or {})
        puesto = next((x for x in estado.get('sound_events_placed') or [] if x.get('clave') == clave), {})
        archivo_lib = ((puesto.get('eleccion') or {}).get('archivo'))
        op = accion.split(':', 1)[1] if ':' in accion else accion
        nuevo_azar = random.randint(1, 2 ** 31 - 1)
        if op in ('regenerar', 'otro_sfx', 'otra_textura'):
            aj['semilla'] = nuevo_azar
            if op != 'regenerar' and archivo_lib:
                p['evitar'] = sorted(set(p.get('evitar') or []) | {archivo_lib})
            elif op != 'regenerar':
                p['solo_procedural'] = True
        elif op == 'quitar_capa':
            p['sin_capa'], p['otra_capa'] = True, False
        elif op == 'mas_corto':
            aj['dur_k'] = round(float(aj.get('dur_k') or 1.0) * 0.7, 3)
        elif op == 'mas_limpio':
            p['graves_menos'] = True
            p['brillo'] = round(max(0.0, float(e.get('params', {}).get('brillo', 0.5)) - 0.12), 3)
        elif op == 'menos_graves':
            p['graves_menos'] = True
        elif op == 'menos_transitorio':
            p['transitorio_menos'], p['clic'] = True, False
        elif op == 'mas_simple':
            p['solo_procedural'], p['sin_capa'], p['otra_capa'] = True, True, False
        elif op == 'mas_bajo':
            p['nivel_extra_db'] = round(float(p.get('nivel_extra_db') or 0.0) - 3.0, 1)
        elif op == 'otra_capa':
            p['otra_capa'], p['sin_capa'] = True, False
        elif op == 'profundidad':
            p['cola'] = round(float(p.get('cola') or (e.get('params') or {}).get('cola') or 0.4) + 0.3, 2)
            aj['dur_k'] = round(float(aj.get('dur_k') or 1.0) * 1.25, 3)
        elif op == 'mejor_transitorio':
            p['clic'], p['transitorio_menos'] = True, False
        elif op == 'mejor_impacto':
            p['peso'] = round(min(1.0, float(p.get('peso') or (e.get('params') or {}).get('peso') or 0.6) + 0.2), 2)
            p['nivel_extra_db'] = round(float(p.get('nivel_extra_db') or 0.0) + 1.5, 1)
        elif op == 'mas_movimiento':
            d = float((e.get('params') or {}).get('direccion') or 0.6)
            p['direccion'] = 0.95 if d >= 0 else -0.95
            p['brillo'] = round(min(1.0, float((e.get('params') or {}).get('brillo', 0.5)) + 0.1), 3)
            aj['dur_k'] = round(float(aj.get('dur_k') or 1.0) * 1.15, 3)
        elif op == 'mas_alto':
            p['nivel_extra_db'] = round(float(p.get('nivel_extra_db') or 0.0) + 3.0, 1)
        else:
            raise RuntimeError(f'No sé hacer «{op}».')
        aj['params'] = p
        etiquetas = dict(MENOS + MAS + (('regenerar', 'Regenerado'),))
        hecho = f"{etiquetas.get(op, op)}: hecho solo para «{_nombre_evento(e, estado.get('caption_decisions') or [])}»."
    ajustes[clave] = aj
    estado['ajustes'] = ajustes
    E.guardar(video, estado)
    return _rehacer(video, al_estado), hecho


def redisenar(video, desde=None, hasta=None, al_estado=None, capas=False):
    """«Rediseñar sonido»: otra ronda para todo lo no bloqueado; con `desde`/`hasta`, solo los sonidos de ese tramo (una sección)."""
    estado = E.cargar(video)
    if desde is None and hasta is None:
        estado['ronda'] = int(estado.get('ronda') or 0) + 1
    else:
        ajustes = dict(estado.get('ajustes') or {})
        for e in estado.get('sound_events') or []:
            if float(desde or 0) <= float(e.get('ancla') or 0) <= float(hasta if hasta is not None else 1e9):
                aj = dict(ajustes.get(e.get('clave')) or {})
                if not aj.get('bloqueado'):
                    aj['semilla'] = random.randint(1, 2 ** 31 - 1)
                    ajustes[e.get('clave')] = aj
        estado['ajustes'] = ajustes
    E.guardar(video, estado)
    return _rehacer(video, al_estado, capas=capas)


def deshacer_todo(video, al_estado=None):
    """Todo como lo decidió la IA: sin ajustes, ronda 0 y controles en AUTO."""
    import ajustes_ui
    ajustes_ui.guardar_prefs({D.PREF_CONTROLES: {}})
    estado = E.cargar(video)
    estado['ajustes'], estado['ronda'] = {}, 0
    E.guardar(video, estado)
    return _rehacer(video, al_estado, capas=True)                     # (los controles de música y ambiente también vuelven a Auto)


# ------------------------------------------------------------------------------------------------------------------------------ oír (A/B)
def _ventana(chunks, desde, hasta):
    """Las muestras [desde, hasta) (segundos) de un generador de trozos (canales, n) en tiempo del timeline, en estéreo."""
    i0, i1 = int(desde * SR), int(hasta * SR)
    out, pos = [], 0
    for x in chunks:
        x = np.asarray(x, np.float32)
        if x.ndim == 1:
            x = x[None, :]
        if x.shape[0] == 1:
            x = np.vstack((x, x))
        n = x.shape[1]
        a, b = max(i0, pos), min(i1, pos + n)
        if b > a:
            out.append(x[:2, a - pos:b - pos])
        pos += n
        if pos >= i1:
            break
    y = np.concatenate(out, axis=1) if out else np.zeros((2, 0), np.float32)
    return np.pad(y, ((0, 0), (0, max(0, (i1 - i0) - y.shape[1]))))


def previa(video, cual='ai', desde=0.0, hasta=None, largo=15.0):
    """El tramo [desde, hasta) como sonaría: 'original' = el audio del video (con Quitar pausas, como en el timeline); 'ai' = la voz del director
    (si GO la puso) + sus sonidos (+ música y ambiente del director). WAV estéreo 16 bits en la carpeta del video. Devuelve la ruta."""
    import wave
    import director_sonido_medir as M
    estado = E.cargar(video)
    ctx = D.cargar_contexto(video) or {}
    desde = max(0.0, float(desde or 0.0))
    hasta = float(hasta) if hasta is not None else desde + largo
    segs = [tuple(x) for x in ((ctx.get('recorte') or {}).get('segmentos') or [])] or None
    voz_ai = (estado.get('voz') or {}).get('archivo') if (estado.get('ultimo_go') or {}).get('voz') else None
    if cual == 'ai' and voz_ai and Path(voz_ai).is_file():
        x = _ventana(M.leer_wav(voz_ai), desde, hasta)
    else:
        x = _ventana(M.trozos(video, segmentos=segs, canales=2), desde, hasta)
    if cual == 'ai':
        for ev in (estado.get('sfx_plan') or []) + (estado.get('music_plan') or []) + (estado.get('ambience_plan') or []):
            ini, d = float(ev.get('ini') or 0.0), float(ev.get('dur') or 0.0)
            if ini >= hasta or ini + d <= desde or not Path(str(ev.get('archivo') or '')).is_file():
                continue
            y = np.concatenate(list(M.leer_wav(ev['archivo'])), axis=1)
            if y.shape[0] == 1:
                y = np.vstack((y, y))
            k = int(round((ini - desde) * SR))
            if k < 0:
                y, k = y[:, -k:], 0
            n = min(y.shape[1], x.shape[1] - k)
            if n > 0:
                x[:, k:k + n] += y[:2, :n]
    destino = E.carpeta_de(video) / f'previa_{cual}.wav'
    destino.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(x, -1.0, 1.0) * 32767).astype('<i2').T.reshape(-1)
    tmp = destino.with_suffix('.tmp.wav')
    with wave.open(str(tmp), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    try:
        tmp.replace(destino)
    except OSError:                                                   # (Windows: el anterior aún suena) → otro nombre
        destino = destino.with_name(f'previa_{cual}_{int(time.time())}.wav')
        tmp.replace(destino)
    return destino


_SONANDO = {'proc': None}


def reproducir(ruta):
    """Suena el WAV sin bloquear (winsound en Windows, afplay en Mac)."""
    detener()
    if sys.platform.startswith('win'):
        import winsound
        winsound.PlaySound(str(ruta), winsound.SND_FILENAME | winsound.SND_ASYNC)
    elif sys.platform == 'darwin':
        import subprocess
        _SONANDO['proc'] = subprocess.Popen(['afplay', str(ruta)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def detener():
    if sys.platform.startswith('win'):
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
    p = _SONANDO.get('proc')
    if p is not None:
        try:
            p.terminate()
        except Exception:
            pass
        _SONANDO['proc'] = None


# ------------------------------------------------------------------------------------------------------------------------------ Resolve
def plan_para_resolve(video):
    """El plan 'solo_ai' con lo que el director tiene ahora para ese video (sus sonidos y, si GO la puso, la voz)."""
    return _plan_del_estado(video, E.cargar(video))


def _plan_del_estado(video, estado):
    """Una copia del mismo diseño validado: no vuelve a cargar un estado que pudo cambiar."""
    ultimo = estado.get('ultimo_go') or {}
    eventos = deepcopy((estado.get('sfx_plan') or []) + (estado.get('music_plan') or []) + (estado.get('ambience_plan') or []))
    if ultimo.get('evento_voz'):
        eventos.append(deepcopy(ultimo['evento_voz']))
    dur = float(((estado.get('analisis') or {}).get('voz') or {}).get('duracion') or 0.0)
    return {'eventos': eventos, 'duracion': dur, 'resumen': '', 'zonas': [], 'solo_audio': True, 'solo_ai': True,
            'apagar_sfx': deepcopy(ultimo.get('apagar_sfx') or ['SFX']), 'video': str(video),
            'destino_ai': deepcopy(ultimo.get('destino') or {})}


def _destino_valido(destino):
    return isinstance(destino, dict) and all(str(destino.get(k) or '').strip() for k in ('proyecto', 'timeline'))


def _comprobar_destino(esperado):
    """Comprueba el destino sin Qt; nunca inicia ni cambia un proyecto de Resolve."""
    try:
        actual = D.destino_actual_resolve()
    except Exception:
        actual = None
    if not _destino_valido(actual):
        return False, 'No pude verificar el proyecto y timeline de Resolve. Abre el destino del último GO y reintenta.'
    claves = ('proyecto', 'timeline', 'timeline_id') if esperado.get('timeline_id') else ('proyecto', 'timeline')
    if any(str(esperado.get(k) or '') != str(actual.get(k) or '') for k in claves):
        return False, (f'El destino de Resolve cambió. Abre «{esperado["proyecto"]} / {esperado["timeline"]}» '
                       'o haz GO en el nuevo destino antes de aplicar el sonido.')
    return True, ''


def _revision_para_aplicar(estado):
    """Lo que se está enviando, sin fechas de escritura ni marcas de sincronización."""
    return deepcopy({k: estado.get(k) for k in ('ultimo_go', 'sfx_plan', 'music_plan', 'ambience_plan', 'sound_events',
                                               'ajustes', 'ronda', 'mezcla_ajustes')})


def aplicar(video, offset_frames=0, al_estado=None):
    """Aplica al destino del último GO; confirma sincronía solo tras éxito y sin cambios de diseño o destino."""
    estado = E.cargar(video)
    ultimo = estado.get('ultimo_go') or {}
    if not ultimo.get('con_director'):
        return False, 'Haz GO con AI Sound Director encendido para ponerlo en Resolve.'
    destino = deepcopy(ultimo.get('destino') or {})
    if not _destino_valido(destino):
        return False, 'Este diseño no tiene un destino vinculado. Haz GO con esta versión para vincular proyecto y timeline antes de aplicar.'
    ok, msg = _comprobar_destino(destino)
    if not ok:
        return False, msg
    revision = _revision_para_aplicar(estado)
    plan = _plan_del_estado(video, estado)
    import efectos_visuales
    ok, msg = efectos_visuales.aplicar(plan, al_estado=al_estado, offset_frames=offset_frames)
    if ok is not True:
        return False, str(msg or 'Resolve no confirmó la colocación del sonido. Los cambios siguen pendientes.')
    ok, comprobacion = _comprobar_destino(destino)
    if not ok:
        return False, comprobacion + ' No se pudo confirmar la sincronización del sonido.'
    estado = E.cargar(video)
    if _revision_para_aplicar(estado) != revision:
        return False, 'El diseño cambió durante el envío. Los cambios actuales siguen pendientes: vuelve a aplicar.'
    estado['pendiente_resolve'] = False
    estado['en_resolve'] = time.strftime('%Y-%m-%d %H:%M:%S')
    E.guardar(video, estado)
    E.poner_general(ai_puesto=True)
    return True, str(msg or 'Sonido aplicado al destino del último GO.')


def aplicar_al_momento(video, offset_frames=0, al_estado=None):
    """Tras un cambio en la página, al timeline sin pedirlo (la página «hace» de verdad): si el último GO de este video fue con el director y
    Resolve está abierto. (True | False | None, texto); None = no se intentó: queda pendiente para «Aplicar a Resolve» o el próximo GO."""
    estado = E.cargar(video)
    if not estado.get('pendiente_resolve'):
        return None, ''
    if not (estado.get('ultimo_go') or {}).get('con_director'):
        return None, 'Listo para el próximo GO.'
    try:
        import resolve_mcp
        if resolve_mcp.ruta_exe() is not None and resolve_mcp.resolve_abierto() is False:
            return None, 'Resolve está cerrado: se pondrá con «Aplicar a Resolve» o en el próximo GO.'
    except Exception:
        pass
    try:
        ok, msg = aplicar(video, offset_frames, al_estado)
    except Exception as e:
        ok, msg = False, f'{type(e).__name__}: {e}'
    return bool(ok), str(msg or '')


# ------------------------------------------------------------------------------------------------------------------------------ «dile a AI Sound Director»
def _plegar(t):
    t = unicodedata.normalize('NFD', str(t).lower())
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', ''.join(c for c in t if unicodedata.category(c) != 'Mn'))).strip()


_REGLAS = [   # (patrón, acción, lo que se entendió) — en orden: lo más concreto primero
    (r'\b(como estaba|automatico|todo en auto|reset|deshaz todo|deshacer todo|vuelve a empezar)\b', ('reset',), 'todo como lo decidió la IA'),
    (r'\b(sin musica|quita la musica|no music|sem musica)\b', ('control', 'musica', 'nada'), 'sin música'),
    (r'\b(musica mas suave|musica suave|menos musica|baja la musica)\b', ('control', 'musica', 'poco'), 'música más suave'),
    (r'\b(musica (mas )?energica|mas musica|musica con energia|sube la musica)\b', ('control', 'musica', 'mucho'), 'música con más energía'),
    (r'\b(sin ambiente|quita el ambiente)\b', ('control', 'ambiente', 'nada'), 'sin ambiente'),
    (r'\b(mas ambiente|ambiente inmersivo|mas inmersivo)\b', ('control', 'ambiente', 'mucho'), 'ambiente más inmersivo'),
    (r'\b(voz (mas )?clara|que se (oiga|entienda) (la|mejor la) voz|se entienda|voz primero|proteg\w* la voz|clear voice)\b', ('control', 'voz', 'mucho'),
     'la voz por encima de todo'),
    (r'\b(menos (sonidos|efectos|golpes|sfx)|mas silencio|fewer|less sounds?)\b', ('control', 'densidad', 'poco'), 'menos sonidos'),
    (r'\b(mas (sonidos|efectos|sfx)|more sounds?)\b', ('control', 'densidad', 'mucho'), 'más sonidos'),
    (r'\b(mas (fuerte|potente|impacto|pegada)|louder|more impact)\b', ('control', 'intensidad', 'mucho'), 'más intensidad'),
    (r'\b(mas (suave|bajo|sutil)|menos fuerte|softer|quieter)\b', ('control', 'intensidad', 'poco'), 'más suave'),
    (r'\b(mas limpio|limpio|clean)\b', ('control', 'estilo', 'limpio'), 'estilo limpio'),
    (r'\b(cine\w*|epico|cinematic)\b', ('control', 'estilo', 'cinematico'), 'estilo cinematográfico'),
    (r'\b(energ\w*|dinamico|mas ritmo)\b', ('control', 'estilo', 'energico'), 'estilo enérgico'),
    (r'\b(minim\w*)\b', ('control', 'estilo', 'minimo'), 'estilo mínimo'),
]


def interpretar(texto, duracion=None):
    """Lo que el usuario pide en palabras → ({'entendido': [...], 'acciones': [...]}). No toca nada (ejecutar lo aplica)."""
    t = _plegar(texto)
    # Las reglas son literales: una negación nunca puede caer en su coincidencia positiva.
    t = re.sub(r'\bno (?:(?:quiero|deseo|necesito|pongas|agregues|anadas) )?(?:mas )?(sonidos|efectos|golpes|sfx)\b',
               r'menos \1', t)
    t = re.sub(r'\bsin mas (sonidos|efectos|golpes|sfx)\b', r'menos \1', t)
    t = re.sub(r'\bno (?:(?:quiero|deseo|necesito) )?musica\b|\bno music\b', 'sin musica', t)
    t = re.sub(r'\bno (?:(?:quiero|deseo|necesito) )?ambiente\b', 'sin ambiente', t)
    if re.search(r'\b(no|nunca|tampoco|evita|evitar)\b', t):
        return {'entendido': ['No puedo interpretar esa negación con seguridad. Usa un pedido compatible, por ejemplo «menos sonidos» o «sin música».'],
                'acciones': [], 'requiere_aclaracion': True}
    # Los controles afectan a todo el video. Solo rediseñar eventos admite un tramo.
    # Separar cláusulas permite «sin música y rediseña el final», sin ampliar «sin música al final».
    clausulas = re.split(r'\b(?:y|luego|despues|ademas)\b', t)
    alcance_temporal = r'\b(inicio|principio|gancho|intro|final|cierre|cta|ultim[oa]s?|primer[oa]s?|segundos?|minutos?|desde|hasta|seccion|tramo|entre)\b|\b(solo aqui|esta parte|este momento)\b'
    for clausula in clausulas:
        if re.search(alcance_temporal, clausula) and any(re.search(p, clausula) and a[0] in ('control', 'reset') for p, a, _ in _REGLAS):
            return {'entendido': ['Ese cambio por tramo no está disponible. Música, ambiente y dirección se ajustan para todo el video; '
                                  'puedes pedir «sin música» para todo el video o «rediseña el final» para variar solo sus eventos.'],
                    'acciones': [], 'requiere_aclaracion': True}
    entendido, acciones = [], []
    m = re.search(r'\b(quita|silencia|sin sonido en|calla)\b (el sonido (de|en) )?(la palabra )?(.+)$', t)
    if m and not re.search(r'\b(musica|ambiente|todo)\b', m.group(5)):
        palabra = m.group(5).strip()
        acciones.append(('silenciar_texto', palabra))
        entendido.append(f'silenciar el sonido de «{palabra}»')
    rehacer = re.search(r'\b(regenera|rediseña|redisena|rehaz|otra version|cambia los sonidos|otros sonidos)\b', t)
    if rehacer:
        if re.search(r'\b(inicio|principio|gancho|intro)\b', t):
            acciones.append(('seccion', 0.0, 6.0))
            entendido.append('rediseñar el inicio')
        elif re.search(r'\b(final|cierre|cta|ultimo)\b', t):
            d = float(duracion or 0.0)
            acciones.append(('seccion', max(0.0, d - 8.0), d + 1.0))
            entendido.append('rediseñar el final')
        else:
            acciones.append(('redisenar',))
            entendido.append('rediseñar todo el sonido')
    for patron, accion, texto_ok in _REGLAS:
        if re.search(patron, t) and accion not in acciones:
            if accion[0] == 'control' and any(a[0] == 'control' and a[1] == accion[1] for a in acciones):
                continue
            acciones.append(accion)
            entendido.append(texto_ok)
    if ('reset',) in acciones and len(acciones) > 1:
        return {'entendido': ['Restaurar el diseño IA y aplicar otros cambios son acciones distintas. Envía primero el pedido que quieres realizar.'],
                'acciones': [], 'requiere_aclaracion': True}
    return {'entendido': entendido, 'acciones': acciones}


def ejecutar(video, acciones, al_estado=None):
    """Aplica lo que interpretar entendió. Devuelve (resumen, texto)."""
    if not acciones:
        return resumen(video), 'No se aplicó ningún cambio. Usa un pedido compatible.'
    hechos = []
    estado = E.cargar(video)
    capas = False
    for a in acciones:
        if a[0] == 'reset':
            return deshacer_todo(video, al_estado), 'Todo vuelve a como lo decidió la IA.'
        if a[0] == 'control':
            poner_control(a[1], a[2])
            hechos.append(a)
            capas = capas or a[1] in ('musica', 'ambiente')
        elif a[0] == 'silenciar_texto':
            caps = estado.get('caption_decisions') or []
            refs = {c.get('cue') for c in caps if a[1] in _plegar(c.get('texto') or '')}
            ajustes = dict(estado.get('ajustes') or {})
            n = 0
            for e in estado.get('sound_events') or []:
                if e.get('ref') in refs and e.get('origen') in ('caption', 'dato'):
                    aj = dict(ajustes.get(e.get('clave')) or {})
                    aj['silenciar'] = True
                    aj.pop('bloqueado', None)
                    ajustes[e.get('clave')] = aj
                    n += 1
            estado['ajustes'] = ajustes
            E.guardar(video, estado)
            hechos.append(('silenciados', n))
    seccion = next((a for a in acciones if a[0] in ('seccion', 'redisenar')), None)
    if seccion and seccion[0] == 'seccion':
        return redisenar(video, seccion[1], seccion[2], al_estado, capas=capas), 'Hecho.'
    if seccion:
        return redisenar(video, al_estado=al_estado, capas=capas), 'Hecho.'
    return _rehacer(video, al_estado, capas=capas), 'Hecho.'
