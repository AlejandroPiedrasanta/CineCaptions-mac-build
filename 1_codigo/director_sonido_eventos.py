# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_eventos.py — «AI Sound Director»: lo que pasa en pantalla y en la narración, leído de la metadata REAL de GO.
"""
Fase 1 (solo LEER, nada se cambia):

    captions(bloques)       cada caption con texto, palabra clave (rol main), roles, momento, duración, tamaño de la palabra grande, clips de
                            animación del tema ('k hero lima', 'v shatter…'), posición, emoji y los sonidos que ya le puso el modo Simple
    motions(efectos, pro)   cada motion con su metadata: de dónde viene (Efectos / PRO / kit neón), pieza, inicio, duración, capa, entrada
                            (subir / desenfoque / máscara), escala, dirección, función del kit (barrido, órbita…), componente de Remotion; y la
                            lista de campos de metadata que de verdad trae el plan
    narrativa(palabras)     frases con su papel: HOOK, INTRO, PROBLEM, EXPLANATION, EXAMPLE, DATA, REVEAL, SOLUTION, RESULT, CTA (y su importancia)

Fase 3 (primer paso, para la demostración del Tema 1): `disenar_kinetic` = CAPTION_SOUND_SCORE 0–1 y decisiones KEEP / REPLACE / REMOVE / GENERATE /
LEAVE_SILENT por evento, con la animación REAL de cada clip del pack (ANIM_KINETIC).
"""
import re
import unicodedata

import numpy as np

ROLES = ('HOOK', 'INTRO', 'PROBLEM', 'EXPLANATION', 'EXAMPLE', 'DATA', 'REVEAL', 'SOLUTION', 'RESULT', 'CTA')
_CLAVES = {
    'CTA': 'siguenos sigueme suscribete suscribanse comenta comentalo comparte compartelo guarda guardalo link enlace descripcion dale like follow subscribe '
           'comment share save bio segue inscreva comente compartilhe',
    'INTRO': 'hoy soy me llamo bienvenidos bienvenido video te voy a contar today welcome im hoje sou bem vindos',
    'PROBLEM': 'problema error errores dificil malo peor nunca miedo falla fallo problem mistake mistakes hard wrong fail never problema erro',
    'EXAMPLE': 'ejemplo imagina imaginate como cuando example imagine like when exemplo imagine',
    'REVEAL': 'pero secreto clave resulta verdad realmente sorpresa nadie but secret key truth actually surprise nobody mas segredo verdade',
    'SOLUTION': 'solucion respuesta truco tip consejo forma manera hack solution answer trick tip way solucao resposta dica',
    'RESULT': 'resultado resultados final finalmente logre consegui result results finally achieved resultado finalmente',
}
_CLAVES = {k: set(v.split()) for k, v in _CLAVES.items()}
_NUMEROS = set('uno dos tres cuatro cinco seis siete ocho nueve diez cien mil millon millones porciento one two three four five six seven eight nine ten '
               'hundred thousand million percent'.split())


def _plegar(t):
    t = unicodedata.normalize('NFD', str(t).lower())
    return re.sub(r'[^a-z0-9 ]+', ' ', ''.join(c for c in t if unicodedata.category(c) != 'Mn')).strip()


def _texto_de(b):
    if b.get('lines'):
        return ' '.join(str(l.get('text') or '') for l in b['lines'] if isinstance(l, dict)).strip()
    if b.get('runs'):
        return ' '.join(str(r.get('texto') or '') for r in b['runs'] if isinstance(r, dict) and r.get('texto')).strip()
    return str(b.get('text') or b.get('texto') or '').strip()


def captions(bloques, duracion=None):
    """Los captions de GO leídos con su metadata real. {'lista', 'n', 'por_minuto', 'con_sonido', 'sonidos', 'tamano_max', 'campos'}."""
    lista, campos = [], set()
    for i, b in enumerate(bloques or []):
        if not isinstance(b, dict):
            continue
        campos.update(b.keys())
        ini, fin = float(b.get('start') or 0.0), float(b.get('end') or b.get('start') or 0.0)
        lines = [l for l in (b.get('lines') or []) if isinstance(l, dict)]
        runs = [r for r in (b.get('runs') or []) if isinstance(r, dict)]
        main = [str(l.get('text') or '') for l in lines if l.get('role') == 'main']
        tam = max([float(r.get('size') or 0.0) for r in runs] or [0.0])                # Kinetic / VIRAL: alto de la palabra (fracción del cuadro)
        escala = max([float(r.get('zoom') or 0.0) for r in runs if r.get('rol') == 'main'] or [0.0])   # «guion»: escala de la palabra clave
        clips = sorted({str(r.get('k')) for r in runs if r.get('k')})
        sonidos = [e for e in (b.get('sfx_eventos') or []) if isinstance(e, dict)]
        lista.append({'i': i, 'ini': round(ini, 3), 'fin': round(fin, 3), 'dur': round(max(0.0, fin - ini), 3), 'texto': _texto_de(b), 'clave': ' '.join(main),
                      'roles': [l.get('role') for l in lines] or [r.get('rol') for r in runs if r.get('rol')], 'tamano': round(tam, 4) if tam else None,
                      'escala_clave': round(escala, 3) if escala else None, 'animacion': clips,
                      'caja': b.get('caja'), 'emoji': b.get('emoji'), 'plantilla': b.get('plantilla'),
                      'sonidos': [{'t': e.get('t'), 'familia': e.get('sfx'), 'archivo': e.get('sfx_nombre')} for e in sonidos]})
    dur = float(duracion or (lista[-1]['fin'] if lista else 0.0))
    con = sum(1 for c in lista if c['sonidos'])
    return {'lista': lista, 'n': len(lista), 'por_minuto': round(len(lista) / max(dur / 60.0, 1e-6), 1) if dur else 0.0, 'con_sonido': con,
            'silenciosos': len(lista) - con, 'sonidos': sum(len(c['sonidos']) for c in lista),
            'tamano_max': max([c['tamano'] or 0.0 for c in lista] or [0.0]) or None,
            'escala_clave_media': round(float(np.mean([c['escala_clave'] for c in lista if c['escala_clave']])), 3) if any(c['escala_clave'] for c in lista) else None,
            'campos': sorted(campos)}


TIPOS_VISUALES_FX = ('intro', 'corte', 'icono', 'numero', 'pegatina', 'enfasis', 'overlay', 'propio', 'outro', 'broll')


def motions(plan_efectos=None, plan_pro=None, duracion=None):
    """Los motions con la metadata que traen los planes (nada se infiere si el plan lo dice). {'lista', 'n', 'por_minuto', 'por_origen', 'campos'}."""
    lista, campos = [], set()
    for e in ((plan_efectos or {}).get('eventos') or []):
        if not isinstance(e, dict) or e.get('tipo') not in TIPOS_VISUALES_FX:
            continue
        campos.update(f'efectos.{k}' for k in e)
        lista.append({'origen': 'Efectos', 'pieza': e.get('tipo'), 'asset': e.get('asset'), 'ini': float(e.get('ini') or 0.0),
                      'dur': float(e['dur']) if e.get('dur') is not None else None, 'capa': None, 'entrada': None, 'escala': None, 'direccion': None})
    for p in ((plan_pro or {}).get('piezas') or []):
        if not isinstance(p, dict) or p.get('quitar'):
            continue
        campos.update(f'pro.{k}' for k in p)
        val = p.get('valores') if isinstance(p.get('valores'), dict) else {}
        campos.update(f'pro.valores.{k}' for k in val)
        ini, fin = float(p.get('ini') or 0.0), float(p.get('fin') or p.get('ini') or 0.0)
        item = {'origen': 'PRO', 'pieza': p.get('pieza'), 'asset': p.get('remotion') or p.get('pieza'), 'ini': round(ini, 3), 'dur': round(max(0.0, fin - ini), 3),
                'capa': p.get('capa'), 'entrada': val.get('entrada'), 'escala': val.get('escala'), 'direccion': val.get('direccion'), 'kit': None}
        if p.get('pieza') == 'neon_motion':                          # el kit «TEMA 1»: cada escena con su función, tiempos y argumentos
            esc = (val.get('escena') or [{}])[0] if isinstance(val.get('escena'), list) else {}
            a = esc.get('a') if isinstance(esc.get('a'), dict) else {}
            item.update({'origen': 'kit neón', 'kit': esc.get('fn'), 'tin': a.get('tin'), 'tout': a.get('tout')})
        lista.append(item)
    lista.sort(key=lambda m: m['ini'])
    dur = float(duracion or (plan_pro or {}).get('duracion') or (plan_efectos or {}).get('duracion') or (lista[-1]['ini'] if lista else 0.0) or 0.0)
    por_origen = {}
    for m in lista:
        por_origen[m['origen']] = por_origen.get(m['origen'], 0) + 1
    return {'lista': lista, 'n': len(lista), 'por_minuto': round(len(lista) / max(dur / 60.0, 1e-6), 1) if dur else 0.0, 'por_origen': por_origen,
            'campos': sorted(campos), 'pro_sonido_al_colocar': bool((plan_pro or {}).get('piezas'))}


def narrativa(palabras, duracion=None, perfil=None):
    """Frases con su papel narrativo e importancia (efectos_visuales.partir_en_frases / puntuar_frase, las mismas de Efectos)."""
    import efectos_visuales as F
    frases = F.partir_en_frases([dict(p) for p in (palabras or []) if isinstance(p, dict)])
    dur = float(duracion or (frases[-1]['fin'] if frases else 0.0))
    salida = []
    for k, fr in enumerate(frases):
        ws = set(_plegar(fr['texto']).split())
        puntos = F.puntuar_frase(fr, es_primera=(k == 0))
        rol = 'EXPLANATION'
        if fr['ini'] < 3.5 or k == 0:
            rol = 'HOOK'
        elif dur and fr['ini'] > 0.75 * dur and ws & _CLAVES['CTA']:
            rol = 'CTA'
        elif k <= 2 and ws & _CLAVES['INTRO']:
            rol = 'INTRO'
        elif re.search(r'\d', fr['texto']) or ws & _NUMEROS:
            rol = 'DATA'
        elif fr.get('pregunta') or ws & _CLAVES['PROBLEM']:
            rol = 'PROBLEM'
        elif ws & _CLAVES['REVEAL']:
            rol = 'REVEAL'
        elif ws & _CLAVES['SOLUTION']:
            rol = 'SOLUTION'
        elif ws & _CLAVES['EXAMPLE']:
            rol = 'EXAMPLE'
        elif dur and fr['ini'] > 0.8 * dur and ws & _CLAVES['RESULT']:
            rol = 'RESULT'
        salida.append({'ini': round(fr['ini'], 3), 'fin': round(fr['fin'], 3), 'texto': fr['texto'], 'rol': rol,
                       'importancia': round(float(np.clip((puntos + 3.0) / 12.0, 0.0, 1.0)), 3)})
    cuenta = {}
    for f in salida:
        cuenta[f['rol']] = cuenta.get(f['rol'], 0) + 1
    return {'frases': salida, 'n': len(salida), 'roles': cuenta, 'frases_por_minuto': round(len(salida) / max(dur / 60.0, 1e-6), 1) if dur else 0.0,
            'perfil': perfil or {}}


# ------------------------------------------------------------------------------------------------------------------------------ diseño (fase 3)
# la animación REAL de cada clip del Tema 1 (2_recursos/generador_packs/kinetic_elementos.animacion y comp_trazo): fotogramas, easing y qué hace
ANIM_KINETIC = {
    'pop': {'f': 10, 'easing': 'easeOutBack', 'que': 'entra de 0,38× a 1× con giro −4° y rebote'},
    'sube': {'f': 7, 'easing': 'easeOutBack', 'que': 'sube un poco y aparece'},
    'giro': {'f': 9, 'easing': 'easeOutBack', 'que': 'entra girada −9° y grande, y se asienta'},
    'abre': {'f': 10, 'easing': 'easeOutBack', 'que': 'aparece con calma'},
    'trazo': {'s': 0.45, 'easing': 'easeOutPow', 'k': 2.4, 'que': 'el anillo se dibuja deprisa y frena'},
    'salida': {'f': 5, 'easing': 'linear', 'que': 'la pila se va a la vez'},
}
PISTA = {'golpe': 'AI SFX IMPACTS', 'whoosh': 'AI SFX MOTION', 'giro': 'AI SFX MOTION', 'riser': 'AI SFX MOTION', 'trazo': 'AI SFX TEXTURE',
         'acento': 'AI SFX TONAL', 'tick': 'AI SFX UI', 'pop': 'AI SFX UI'}
NIVEL_REL_VOZ = {'golpe': -9.0, 'whoosh': -15.0, 'giro': -17.0, 'riser': -13.0, 'trazo': -19.0, 'acento': -17.0, 'tick': -22.0, 'pop': -20.0}
PESO_ROL = {'HOOK': 0.45, 'CTA': 0.35, 'REVEAL': 0.3, 'DATA': 0.3, 'RESULT': 0.2, 'SOLUTION': 0.2, 'PROBLEM': 0.15, 'INTRO': 0.1, 'EXAMPLE': 0.05}


def anim_de_clip(k):
    k = str(k or '')
    if k.startswith('k hero'):
        return 'pop'
    if k in ('k sup', 'k label'):
        return 'sube'
    if k.startswith(('k tape', 'k tapes', 'k script')):
        return 'giro'
    if k.startswith(('k ring trazo', 'k ring lazo', 'k line trazo')):
        return 'trazo'
    return 'abre'


def _rol_en(frases, t):
    for f in frases:
        if f['ini'] - 0.25 <= t <= f['fin'] + 0.25:
            return f['rol'], f['importancia'], f['texto']
    return 'EXPLANATION', 0.3, ''


def disenar_kinetic(cues, narrativa, cortes, paleta, duracion, fps=30.0):
    """El diseño de sonido del Tema 1 a partir de su metadata REAL (clips de cada run, momentos, tamaños) y de la narrativa: CAPTION_SOUND_SCORE
    0–1 por caption (la mayoría en silencio), un golpe diseñado para el «pop» del héroe que importa, el anillo que se dibuja como un rotulador, la
    cinta que gira, un riser en el gancho, whooshes en los cortes de escena que respiran, y un MOTIVO tonal (la misma campana) para los datos y el
    cierre. Densidad por ventanas de 10 s y anti-repetición. Qué pasa con cada sonido viejo (KEEP / REPLACE / REMOVE) con su porqué.
    Devuelve {'eventos': [...], 'decisiones': [...], 'captions': [...], 'resumen'}."""
    v = (paleta or {}).get('valores') or {}
    densidad, impacto, brillo = float(v.get('densidad', 0.3)), float(v.get('impacto', 0.7)), float(v.get('brillo', 0.5))
    umbral = 0.55 + 0.3 * (0.4 - densidad)
    frases = (narrativa or {}).get('frases') or []
    eventos, decisiones, captions = [], [], []
    ultimo_golpe, n_datos, gancho_usado = -99.0, 0, False
    nota = 523.25 if brillo >= 0.5 else 392.0                      # el motivo del video: siempre la misma campana (do5 / sol4)

    def ev(tipo, t, ancla, dur, motivo, imp, capa=None, **params):
        eventos.append({'id': f'{tipo}-{len(eventos) + 1:02d}', 'tipo': tipo, 't': round(max(0.0, t), 3), 'ancla': round(ancla, 3), 'dur': round(dur, 3),
                        'pista': capa or PISTA[tipo], 'nivel_rel_voz_db': NIVEL_REL_VOZ[tipo], 'params': params, 'decision': 'GENERATE',
                        'por_que': motivo, 'importancia': round(float(imp), 2)})
    for i, c in enumerate(cues or []):
        runs = [r for r in (c.get('runs') or []) if isinstance(r, dict) and r.get('k')]
        heroe = next((r for r in runs if str(r['k']).startswith('k hero')), None) or max(runs, key=lambda r: float(r.get('size') or 0), default=None)
        if heroe is None:
            continue
        t = float(heroe.get('t') or c.get('start') or 0.0)
        size = float(heroe.get('size') or 0.2)
        rol, imp, frase = _rol_en(frases, t)
        if i == 0:
            rol = 'HOOK'
        texto = str(heroe.get('texto') or '')
        anillo = next((r for r in runs if anim_de_clip(r['k']) == 'trazo'), None)
        cinta = next((r for r in runs if anim_de_clip(r['k']) == 'giro'), None)
        peso_rol = PESO_ROL.get(rol, 0.0)
        if rol == 'HOOK' and gancho_usado:
            peso_rol = 0.15                                          # el gancho se marca UNA vez (con su riser); los héroes que siguen, como uno más
        s = 0.15 + peso_rol + 0.25 * float(imp) + float(np.clip((size - 0.2) * 0.8, 0, 0.2))
        s += 0.1 if anillo else 0.0
        s += 0.15 if any(ch.isdigit() for ch in texto) else 0.0
        hueco = t - ultimo_golpe
        s -= 0.35 if hueco < 3.0 else (0.15 if hueco < 5.0 else 0.0)
        if hueco < 2.0 and not any(ch.isdigit() for ch in texto):
            s = min(s, umbral - 0.01)                                # dos golpes a menos de 2 s se pisan (salvo una cifra)
        s = float(np.clip(s, 0, 1))
        viejos = [e for e in (c.get('sfx_eventos') or []) if isinstance(e, dict)]
        info = {'cue': i, 't': round(t, 3), 'texto': texto, 'rol': rol, 'caption_sound_score': round(s, 2), 'clips': sorted({r['k'] for r in runs})}
        if s < umbral:
            info['decision'] = 'LEAVE_SILENT'
            info['por_que'] = (f'score {s:.2f} < {umbral:.2f}' + (f' (otro golpe hace {hueco:.1f} s)' if hueco < 5 else '') +
                               f': {rol.lower()}, lo dice la voz y el tema ya lo anima')
            for e in viejos:
                decisiones.append({'cue': i, 'viejo': e.get('sfx_nombre') or e.get('sfx'), 't': e.get('t'), 'decision': 'REMOVE',
                                   'por_que': 'un «Hit» genérico en casi cada caption cansa y tapa la voz: este caption va en silencio'})
            captions.append(info)
            continue
        info['decision'] = 'REPLACE' if viejos else 'GENERATE'
        a = ANIM_KINETIC['pop']
        dur_pop = a['f'] / fps
        t_golpe = t + 0.37 * dur_pop                                  # easeOutBack llega al tamaño final en p ≈ 0,37 (luego rebota a 1,1)
        pre = 0.09
        peso = float(np.clip(0.35 + 1.4 * size * impacto, 0.3, 1.0))
        ev('golpe', t_golpe - pre, t_golpe, 0.6, f"«{texto}» ({rol.lower()}): el héroe entra con «pop» {a['f']} f easeOutBack (×2,6, giro −4°); el golpe cae "
           f"cuando llega a su tamaño (p≈0,37) con {int(pre * 1000)} ms de aire antes; peso {peso:.2f} por su tamaño ({size:.2f})", s,
           peso=peso, brillo=brillo, cola=0.35 + 0.3 * float(v.get('reverb', 0.5)), pre=pre)
        info['por_que'] = f'score {s:.2f} ≥ {umbral:.2f}: {rol.lower()}' + (' con cifra' if any(ch.isdigit() for ch in texto) else '') + (' y anillo' if anillo else '')
        for e in viejos:
            decisiones.append({'cue': i, 'viejo': e.get('sfx_nombre') or e.get('sfx'), 't': e.get('t'), 'decision': 'REPLACE',
                               'por_que': 'el «Hit» genérico se cambia por un golpe diseñado para ESTE «pop» (tiempo, tamaño y paleta)'})
        ultimo_golpe = t
        gancho_usado = gancho_usado or rol == 'HOOK'
        if anillo and rol in ('HOOK', 'DATA', 'REVEAL', 'CTA'):
            ta = float(anillo.get('t') or t)
            ev('trazo', ta, ta, ANIM_KINETIC['trazo']['s'] + 0.05, f'el anillo se dibuja en 0,45 s frenando (1 − (1 − p)^2,4): rotulador con esa energía', s * 0.8,
               potencia=2.4, brillo=brillo)
        if cinta and rol in ('HOOK', 'REVEAL', 'CTA'):
            tc = float(cinta.get('t') or t)
            ev('giro', tc, tc + 0.6 * ANIM_KINETIC['giro']['f'] / fps, ANIM_KINETIC['giro']['f'] / fps + 0.05,
               f"la cinta entra girada −9° en {ANIM_KINETIC['giro']['f']} f: whoosh que da la vuelta y el slap al pegarse", s * 0.7, brillo=brillo)
        if rol == 'DATA' and n_datos < 3:
            ev('acento', t_golpe + 0.02, t_golpe, 1.1, 'motivo de los datos: la misma campana en cada cifra (identidad del video)', s * 0.7, nota=nota, brillo=brillo)
            n_datos += 1
        captions.append(info)
    # el gancho: un riser corto que acaba en el primer golpe (si llega pronto)
    golpes = [e for e in eventos if e['tipo'] == 'golpe']
    if golpes and golpes[0]['ancla'] <= 4.0 and golpes[0]['ancla'] > 0.9:
        g = golpes[0]
        dur_r = min(1.6, g['ancla'] - 0.05)
        ev('riser', g['ancla'] - dur_r, g['ancla'], dur_r, f'gancho: sube {dur_r:.1f} s y se corta 30 ms antes del primer golpe (payoff)', 0.9, brillo=brillo)
    # el cierre: el motivo, más largo, en el último caption de llamada a la acción
    cta = [c for c in captions if c['rol'] == 'CTA' and c.get('decision') != 'LEAVE_SILENT']
    if cta:
        tf = cta[-1]['t'] + 0.15
        ev('acento', tf, tf, 1.6, 'cierre (CTA): el motivo del video, más largo — firma sonora del final', 0.8, nota=nota * 0.75, brillo=brillo)
    # transiciones: whoosh en los cortes de escena que respiran (lejos de los golpes, como mucho uno cada 6 s)
    ultimo_w, dirs = -99.0, 1.0
    for tc in sorted(float(x) for x in (cortes or [])):
        if tc - ultimo_w < 6.0 or any(abs(tc - e['ancla']) < 0.6 for e in eventos if e['tipo'] in ('golpe', 'riser')):
            continue
        d_w = 0.42
        ev('whoosh', tc - d_w * 0.55, tc, d_w + 0.12, f'corte de escena a {tc:.2f} s: aire que pasa con easeInOutCubic (pico en el corte), de lado alterno', 0.5,
           direccion=dirs * 0.8, easing='easeInOutCubic', brillo=brillo, peso=0.4)
        dirs, ultimo_w = -dirs, tc
    # densidad: como mucho 2 + 4·densidad sonidos por ventana de 10 s (se quitan los de menos importancia)
    tope = int(round(2 + 4 * densidad))
    eventos.sort(key=lambda e: e['t'])
    for k0 in np.arange(0, max(duracion, 1.0), 10.0):
        dentro = [e for e in eventos if k0 <= e['ancla'] < k0 + 10 and e['decision'] == 'GENERATE']
        for e in sorted(dentro, key=lambda e: e['importancia'])[:max(0, len(dentro) - tope)]:
            if e['tipo'] in ('golpe', 'riser'):
                continue
            e['decision'] = 'REMOVE'
            e['por_que'] += f' — QUITADO: más de {tope} sonidos en {int(k0)}–{int(k0) + 10} s'
    activos = [e for e in eventos if e['decision'] == 'GENERATE']
    resumen = {'captions': len(captions), 'con_sonido': sum(1 for c in captions if c['decision'] != 'LEAVE_SILENT'),
               'en_silencio': sum(1 for c in captions if c['decision'] == 'LEAVE_SILENT'), 'eventos': len(activos),
               'por_tipo': {t: sum(1 for e in activos if e['tipo'] == t) for t in sorted({e['tipo'] for e in activos})},
               'viejos': {d: sum(1 for x in decisiones if x['decision'] == d) for d in ('REPLACE', 'REMOVE', 'KEEP')}, 'umbral': round(umbral, 2)}
    return {'eventos': eventos, 'decisiones': decisiones, 'captions': captions, 'resumen': resumen}
