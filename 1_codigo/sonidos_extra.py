# CineCaptions · By Cinema Productions
# 1_codigo/sonidos_extra.py — los sonidos extra de GO (v5.4.8): música de fondo, sonidos de transición en los cortes, riser + golpe + silencio en el gancho.
"""
`planificar(...)` devuelve los EVENTOS de audio de ESTE video (los mismos dicts que el plan de efectos: tipo 'sonido' o 'musica', 'ini' en segundos, 'archivo', 'dur'):

  * MÚSICA (S2)      musica_go.preparar: la música elegida, nivelada, con ducking fino y alineada al pulso con el golpe del gancho (S4);
  * TRANSICIONES (S16) un whoosh / glitch / power-up en cada corte con transición (y un click en cada corte seco del «quitar pausas»), 0,10 s antes del corte;
  * GANCHO (S17+S18) riser que sube hasta 0,2 s antes de la palabra más importante del arranque, UN HUECO de 0,2 s (la música se calla del todo) y el golpe en la palabra;
  * PULSO (S4)       con música: las entradas de iconos, números, pegatinas y énfasis se acercan al golpe de pulso más cercano (a menos de 0,15 s).

Preferencias: `musica_go` (ver musica_go.py), `fx_sonido_cortes` (sí), `fx_sonido_gancho` (sí).
"""
from __future__ import annotations

from pathlib import Path

import efectos_visuales as F

# v5.5: el sonido de cada transición. 'destello' (un fogonazo blanco) suena como el DISPARO de una cámara (los obturadores Shuter 11 y 13 de la carpeta del usuario, categoría «Shutter»);
# lo demás conserva su familia. La página Efectos deja elegir otra (pref fx_sonido_corte: auto | shutter | whoosh | glitch | power_up | ninguno).
SONIDO_CORTE = {'fuga_de_luz': 'Whoosh', 'destello': 'Shutter', 'zoom_blur': 'Whoosh', 'whip': 'Whoosh', 'glitch': 'Glitch'}
SONIDOS_CORTE_ELEGIBLES = (('auto', 'Automático', None), ('shutter', 'Obturador', 'Shutter'), ('whoosh', 'Whoosh', 'Whoosh'), ('glitch', 'Glitch', 'Glitch'), ('power_up', 'Power Up', 'Power Up'),
                           ('ninguno', 'Sin sonido', ''))
ANTICIPO_CORTE_S = 0.03            # el PICO del sonido (whoosh, glitch…) cae 0,03 s antes del corte (v5.5: antes el sonido EMPEZABA 0,10 s antes y su pico llegaba después)
ANTICIPO_POR_CATEGORIA = {'Shutter': 0.03}      # el obturador suena en el instante del corte (su clic está a 0,16-0,24 s del inicio del audio: se compensa abajo)
HUECO_GANCHO_S = 0.20
RISER_MAX_S = 2.0
GANCHO_DESDE_S = 2.6                 # antes de esto ya suena la intro (su riser y su destello)
GANCHO_HASTA_S = 14.0
TIPOS_AL_PULSO = ('icono', 'pegatina', 'numero', 'enfasis')


def opciones(prefs=None):
    if prefs is None:
        try:
            import ajustes_ui
            prefs = ajustes_ui.leer_prefs()
        except Exception:
            prefs = {}
    import musica_go
    return {'musica': musica_go.config(prefs), 'cortes': prefs.get('fx_sonido_cortes', True) is not False, 'gancho': prefs.get('fx_sonido_gancho', True) is not False,
            'corte_sonido': prefs.get('fx_sonido_corte') or 'auto'}


def palabra_del_gancho(palabras, duracion):
    """El instante (s) de la palabra más importante del arranque (entre GANCHO_DESDE_S y GANCHO_HASTA_S): la primera palabra de la mejor frase por `puntuar_frase`. None si no hay."""
    try:
        frases = F.partir_en_frases(palabras)
    except Exception:
        return None
    mejor, mejor_p = None, 0.0
    for fr in frases:
        t = float(fr.get('ini') if fr.get('ini') is not None else fr.get('start', 0.0))
        if not (GANCHO_DESDE_S <= t <= min(GANCHO_HASTA_S, max(GANCHO_DESDE_S, float(duracion or 0) - 3.0))):
            continue
        try:
            p = F.puntuar_frase(fr, es_primera=False)
        except Exception:
            p = 0.0
        if p > mejor_p:
            mejor_p, mejor = p, t
    return round(mejor, 3) if mejor is not None and mejor_p >= 1.0 else None


def _ruta_de_categoria(categoria, k=0):
    import sfx_rules
    rutas = sfx_rules._rutas_de(categoria)
    return Path(rutas[k % len(rutas)]) if rutas else None


def _duracion(ruta):
    return F.duracion_video(ruta) or 1.0


def _evento_sonido(ruta, t, tope_s, asset, db=None, alinear=True):
    """Un evento de sonido ya con el archivo que viaja a Resolve (volumen, normalizado y recorte aplicados). v5.5 `alinear`: el sonido empieza antes de su pico (el remolino de un whoosh) y se
    pone ese tiempo ANTES de `t`, así su PICO cae EN `t` (antes un whoosh de 6 s con el pico a los 0,9 s sonaba casi un segundo tarde)."""
    import sfx_rules
    if not ruta:
        return None
    archivo = sfx_rules.para_resolve(ruta, tope_s, alinear=alinear)
    dur = min(float(tope_s), max(0.2, _duracion(archivo) - 0.02))
    ini = float(t) - (sfx_rules.adelanto_de(archivo) if alinear else 0.0)
    return {'tipo': 'sonido', 'ini': round(max(0.0, ini), 3), 'archivo': str(archivo), 'dur': round(dur, 3), 'asset': asset, 'extra': True}


def categoria_de_corte(transicion, eleccion='auto'):
    """La categoría de sonido de la transición, según la elección del usuario (pref fx_sonido_corte). '' = sin sonido."""
    for ident, _nombre, categoria in SONIDOS_CORTE_ELEGIBLES:
        if ident == eleccion and categoria is not None:
            return categoria
    return SONIDO_CORTE.get(transicion) or ''


def _clic_de(ruta):
    """Cuántos segundos después del inicio del archivo cae su primer golpe fuerte (el clic del obturador no está en el segundo 0). 0.0 si no se puede medir."""
    try:
        import numpy as np
        a = F._decodificar_audio(ruta, 22050)
        m = np.abs(a).max(axis=0)
        pico = float(m.max())
        if pico <= 1e-6:
            return 0.0
        return float(np.nonzero(m > pico * 0.5)[0][0]) / 22050.0
    except Exception:
        return 0.0


def sonidos_de_cortes(cortes, transicion, eleccion='auto'):
    """Un sonido por corte con transición (`transicion` = id de la transición). Alterna entre los de la categoría para no repetir el mismo; el GOLPE del sonido (el clic del obturador,
    el pico del whoosh) cae en el corte, no su principio."""
    categoria = categoria_de_corte(transicion, eleccion)
    if not categoria or not cortes:
        return []
    eventos = []
    for k, t in enumerate(cortes):
        ruta = _ruta_de_categoria(categoria, k)
        golpe = _clic_de(ruta) if (ruta and categoria == 'Shutter') else 0.0
        e = _evento_sonido(ruta, float(t) - ANTICIPO_POR_CATEGORIA.get(categoria, ANTICIPO_CORTE_S) - golpe, 1.4, f'corte · {categoria}', alinear=(categoria != 'Shutter'))
        if e:
            eventos.append(e)
    return eventos


def sonidos_de_saltos(saltos):
    """Un click en cada corte seco del «quitar pausas»."""
    eventos = []
    for k, t in enumerate(saltos or []):
        e = _evento_sonido(_ruta_de_categoria('Click', k), float(t) - 0.02, 0.5, 'salto · Click')
        if e:
            eventos.append(e)
    return eventos


def sonidos_del_gancho(t_palabra, hay_intro=False):
    """v5.5: el riser (el mismo de la intro, por defecto el Viral Hooks Riser: sus últimos 2 s) con su PICO exactamente en la palabra clave, y el golpe EN la palabra. Devuelve (eventos, hueco)
    con hueco = (t0, t1) el silencio donde la música se calla justo antes del golpe. `hay_intro`: ya suena el riser de la intro; el del gancho espera a que pase para no encadenar dos."""
    eventos = []
    riser = F.fuente_sonido_intro() or (F.carpeta_efectos() / 'sonidos' / 'viral_hooks_riser.mp3')
    if riser is not None and Path(riser).is_file():
        try:
            wav, dur, pico = F.preparar_riser(riser, antes_s=RISER_MAX_S)
        except Exception:
            wav, dur, pico = None, 0.0, 0.0
        if wav and dur > 0.3:
            ini = float(t_palabra) - pico
            if ini >= (F.SONIDO_INTRO_S + 1.2 if hay_intro else GANCHO_DESDE_S - 0.5):
                eventos.append({'tipo': 'sonido', 'ini': round(ini, 3), 'archivo': str(wav), 'dur': round(dur, 3), 'asset': 'gancho · riser', 'extra': True, 'pico': round(pico, 3)})
    golpe = _evento_sonido(_ruta_de_categoria('Hit', 0), float(t_palabra), 1.0, 'gancho · golpe')
    if golpe:
        eventos.append(golpe)
    return eventos, (round(float(t_palabra) - HUECO_GANCHO_S, 3), round(float(t_palabra) + 0.02, 3))


def planificar(video, palabras, duracion, cortes=None, transicion=None, saltos=None, eventos_visuales=None, prefs=None, al_estado=None):
    """Los eventos de audio extra y su resumen. `eventos_visuales`: la lista del plan de efectos (se modifica en el sitio para acercar sus entradas al pulso)."""
    op = opciones(prefs)
    eventos, resumen = [], []
    duracion = float(duracion or 0.0)
    try:                                                                  # v5.4.52: el golpe del gancho y los de los cortes, bajo la voz de ESTE video
        import sfx_rules
        if video:
            sfx_rules.fijar_voz(video)
    except Exception:
        pass
    t_gancho = palabra_del_gancho(palabras, duracion) if op['gancho'] else None
    hoyos = None
    if t_gancho is not None:
        ev_g, hueco = sonidos_del_gancho(t_gancho, hay_intro=F.fuente_sonido_intro() is not None and bool(F.activado()))
        eventos.extend(ev_g)
        hoyos = [hueco]
        if ev_g:
            resumen.append('riser y golpe en el gancho')
    if op['cortes']:
        ev_c = sonidos_de_cortes(cortes, transicion, op.get('corte_sonido', 'auto'))
        ev_s = sonidos_de_saltos(saltos)
        eventos.extend(ev_c + ev_s)
        if ev_c or ev_s:
            resumen.append(f'{len(ev_c) + len(ev_s)} sonidos de corte')
    m = op['musica']
    if m['activo'] and m['ruta'] and duracion > 3.0:
        import bpm
        import musica_go
        try:
            if al_estado:
                al_estado('Preparando la música de fondo…')
            archivo, info = musica_go.elegir(m['ruta'], Path(str(video)).stem if video else '')
            if archivo is not None:
                desp = 0.0
                if m['alinear'] and info and t_gancho is not None:
                    desp = bpm.desplazamiento_para(info, t_gancho)                  # un golpe de pulso cae EN el golpe de la palabra clave
                wav = musica_go.preparar(archivo, palabras, duracion, m['db'], desp, hoyos)
                eventos.append({'tipo': 'musica', 'ini': 0.0, 'archivo': str(wav), 'dur': round(duracion, 3), 'asset': Path(archivo).name, 'bpm': (info or {}).get('bpm'), 'extra': True})
                resumen.append(f"música «{Path(archivo).stem[:30]}»" + (f" ({info['bpm']:.0f} BPM)" if info else ''))
                if m['alinear'] and info and eventos_visuales:
                    golpes = bpm.golpes_hasta(info, duracion, desp)
                    movidos = 0
                    for e in eventos_visuales:
                        if e.get('tipo') in TIPOS_AL_PULSO and float(e.get('ini', 0)) > 0.3:
                            nuevo = bpm.acercar_al_pulso([float(e['ini'])], golpes, 0.15)[0]
                            if abs(nuevo - float(e['ini'])) > 1e-6:
                                e['ini'] = round(nuevo, 3)
                                movidos += 1
                    if movidos:
                        resumen.append(f'{movidos} efectos al pulso')
        except Exception:
            try:
                import registro
                registro.excepcion(origen='GO · música de fondo')
            except Exception:
                pass
    return eventos, resumen
