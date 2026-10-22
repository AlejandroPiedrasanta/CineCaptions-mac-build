# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_musica.py — «AI Sound Director»: ¿hay música? ¿la necesita? La decisión de la música (no binaria).
"""
Estados: NO_MUSIC_REQUIRED · KEEP_EXISTING · ADJUST_EXISTING · ADD_NEW · REPLACE_ONLY_IF_ALLOWED. Un video sin música NO significa añadirla: primero
se decide si se beneficia (necesidad 0–1 con sus motivos). Solo se reemplaza la música original si es claramente inapropiada, hay permiso y una
alternativa legal. Fuentes para música NUEVA (SOUND ASSET STRATEGY del usuario, 2026-10-21): proveedor profesional autorizado (Epidemic Sound solo
si existe EPIDEMIC_API_KEY en el entorno; la clave nunca se guarda, se enseña, se anota ni se escribe) → caché profesional aprobada → biblioteca
premium curada. La música local vieja es LEGACY (DISABLED_FOR_NEW_DESIGN): no se usa solo porque esté. Sin proveedor: NO_MUSIC_REQUIRED diciendo que
falta un proveedor autorizado (mejor sin música que con una mediocre). Nunca música aleatoria de internet. (Fase 1: detectar y SUGERIR; elegir
entre VARIOS candidatos, ajustar y mezclar es de la fase 4.)

`en_la_fuente(diag)`: la música ya MEZCLADA con la voz se reconoce por el fondo entre palabras: cerca de la voz (> −20 dB), tonal (planitud baja,
el ruido es liso) y con más graves que la propia voz; un pulso regular la confirma.
"""
import os

import numpy as np

ESTADOS = ('NO_MUSIC_REQUIRED', 'KEEP_EXISTING', 'ADJUST_EXISTING', 'ADD_NEW', 'REPLACE_ONLY_IF_ALLOWED')
LEGACY_LOCAL = 'DISABLED_FOR_NEW_DESIGN'          # la música local vieja: solo compatibilidad / fallback técnico extremo / assets aprobados uno a uno


def _pulso(rms_db, bandas_db=None):
    """Fuerza (0–1) del pico de autocorrelación de los ataques entre 60 y 180 BPM, en la envolvente de los GRAVES (el bombo y el bajo mandan
    ahí; la voz casi no tiene) o, sin bandas, en el nivel total."""
    env = rms_db
    if bandas_db is not None and bandas_db.size:
        env = 10 * np.log10(10 ** (bandas_db[:, 0] / 10.0) + 10 ** (bandas_db[:, 1] / 10.0) + 1e-12)
    if env is None or env.size < 200:
        return 0.0, None
    sube = np.maximum(0.0, np.diff(env.astype(np.float64)))
    sube -= sube.mean()
    if not sube.any():
        return 0.0, None
    ac = np.correlate(sube, sube, 'full')[sube.size - 1:]
    ac /= max(ac[0], 1e-12)
    lags = np.arange(ac.size) * 0.02
    sel = (lags >= 0.333) & (lags <= 1.0)
    if not sel.any():
        return 0.0, None
    k = int(np.argmax(ac[sel]))
    return float(max(0.0, ac[sel][k])), round(60.0 / float(lags[sel][k]), 1)


def en_la_fuente(diag, medidas=None):
    """¿Hay música en el audio del video? {'presente', 'confianza', 'motivos', 'bpm', 'evidencias'}."""
    fondo = diag.get('fondo') or {}
    rel, plan, graves = fondo.get('rel_voz_db', -100.0), fondo.get('planitud', 1.0), fondo.get('graves_rel_voz_db')
    pulso, bpm = _pulso(medidas.get('rms_db') if medidas else None, medidas.get('bandas_db') if medidas else None)
    ev = {'fondo_rel_voz_db': rel, 'planitud_fondo': plan, 'graves_fondo_rel_voz_db': graves, 'pulso': round(pulso, 3), 'bpm': bpm,
          'medido_en': fondo.get('fuente')}
    s, motivos = 0.0, []
    if rel > -20:
        a = 0.35 * float(np.clip((rel + 20) / 10.0, 0, 1))
        s += a
        motivos.append(f'el fondo suena a {rel:.0f} dB de la voz (casi no baja entre palabras)')
    if plan < 0.35 and rel > -35:
        s += 0.35 * float(np.clip((0.35 - plan) / 0.2, 0, 1))
        motivos.append(f'el fondo es tonal (planitud {plan:.2f}; un ruido sería liso)')
    if graves is not None and graves > -3 and rel > -35:              # los graves siguen sin voz (con música debajo, voz y huecos tienen el mismo bajo)
        s += 0.2 * float(np.clip((graves + 3.0) / 6.0, 0, 1))
        motivos.append(f'los graves no bajan cuando no se habla ({graves:+.0f} dB respecto a la voz)')
    if pulso > 0.15:
        s += 0.2 * float(np.clip((pulso - 0.15) / 0.25, 0, 1))
        motivos.append(f'pulso regular (~{bpm:.0f} BPM)')
    presente = s >= 0.5
    return {'presente': bool(presente), 'confianza': round(float(min(1.0, s)), 3), 'motivos': motivos if presente else (motivos or ['fondo bajo o liso: sin música']),
            'bpm': bpm if presente and pulso > 0.15 else None, 'evidencias': ev}


def de_go(plan_efectos):
    """La música de fondo que ya puso el motor de GO (musica_go) en el plan de Efectos, o None."""
    for e in ((plan_efectos or {}).get('eventos') or []):
        if e.get('tipo') == 'musica':
            return {'archivo': e.get('archivo'), 'asset': e.get('asset'), 'bpm': e.get('bpm'), 'dur': e.get('dur')}
    return None


def proveedores():
    """De dónde podría salir música NUEVA (sin usarlos todavía), por prioridad. La clave de Epidemic solo se mira si EXISTE; nunca se lee para
    guardarla. La caché profesional y la biblioteca curada se llenan en la fase 4; la música local vieja es legacy (no cuenta)."""
    try:
        import director_sonido_epidemic as EP
        epidemic = EP.configurada()                                # (la clave nunca sale de ese módulo)
    except Exception:
        epidemic = False
    cache = False
    try:
        import director_sonido_estado as E
        cache = any((E.CARPETA / 'cache_profesional' / 'musica').glob('*.json'))
    except Exception:
        pass
    return {'epidemic': epidemic, 'cache_profesional': cache, 'biblioteca_curada': False, 'legacy_local': LEGACY_LOCAL,
            'alguno': bool(epidemic or cache)}


def necesidad(paleta=None, narrativa=None, motions=None, duracion=0.0, voz=None):
    """¿Se beneficia de música? 0–1 con sus motivos (energía del tema, ritmo, motions, duración, tono; una explicación seria y tranquila puede ir sin)."""
    s, motivos = 0.4, []
    if paleta:
        e = float(paleta.get('energia_musica', 0.5))
        s += 0.4 * (e - 0.5)
        motivos.append(f'energía musical del tema {e:.2f}')
    if motions:
        m = float(motions.get('por_minuto', 0.0))
        if m >= 6:
            s += 0.15
            motivos.append(f'{m:.0f} motions por minuto: la música une el montaje')
    if narrativa:
        rpm = float(narrativa.get('frases_por_minuto', 0.0))
        if rpm >= 14:
            s += 0.1
            motivos.append(f'ritmo rápido ({rpm:.0f} frases/min)')
        tono = (narrativa.get('perfil') or {}).get('tono')
        if tono in ('serio', 'tecnico', 'calmado'):
            s -= 0.2
            motivos.append(f'tono {tono}: la voz manda, mejor poca o ninguna música')
        elif tono in ('energico', 'divertido', 'inspirador'):
            s += 0.1
            motivos.append(f'tono {tono}')
    if duracion and duracion <= 75:
        s += 0.1
        motivos.append('reel corto')
    elif duracion and duracion > 600:
        s -= 0.15
        motivos.append('video largo: una cama musical continua cansa')
    return round(float(np.clip(s, 0, 1)), 3), motivos


def sugerir(fuente, go, nec, nec_motivos, prov=None):
    """El estado SUGERIDO en la fase 1 (la fase 4 lo ejecuta) con su porqué. ADD_NEW solo si hay un proveedor autorizado; si no, NO_MUSIC_REQUIRED
    con el aviso (y `deseado`: lo que haría con proveedor)."""
    if fuente.get('presente'):
        return {'estado': 'KEEP_EXISTING', 'por_que': 'el video ya trae música mezclada con la voz (no se separa ni se cambia): se conserva y el resto se adapta a ella'}
    if go:
        return {'estado': 'KEEP_EXISTING', 'por_que': f"GO ya pone la música elegida por el usuario («{go.get('asset')}»): se conserva (la fase 4 afina ducking y nivel)"}
    if nec >= 0.55:
        motivo = 'sin música y el video se beneficiaría (' + '; '.join(nec_motivos[:3]) + ')'
        if prov is not None and not prov.get('alguno'):
            return {'estado': 'NO_MUSIC_REQUIRED', 'deseado': 'ADD_NEW',
                    'por_que': motivo + ', pero no hay proveedor autorizado (EPIDEMIC_API_KEY) ni música profesional en caché: mejor sin música que con una mediocre'}
        return {'estado': 'ADD_NEW', 'por_que': motivo}
    return {'estado': 'NO_MUSIC_REQUIRED', 'por_que': 'sin música y no la necesita (' + '; '.join(nec_motivos[:3] or ['voz y poco montaje']) + ')'}
