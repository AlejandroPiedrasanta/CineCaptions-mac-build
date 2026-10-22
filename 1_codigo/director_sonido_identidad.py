# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_identidad.py — «AI Sound Director»: THEME → SONIC PROFILE → PROJECT SONIC PALETTE.
"""
Nada de «Tema 1 = sonidos A»: el perfil sonoro SALE de la configuración real del tema elegido —

    estilo de dibujo      vista_tema.estilo_de_pack: 'kinetic' (héroe a pantalla completa), 'viral' (pila fina + efectos shatter/select/drag),
                          'guion' (palabra a palabra) o 3 líneas
    recomendaciones       recomendaciones.RECOMENDACIONES[pack]: dónde suena (principal / todas / ninguna), intro, cortes, zoom (y lo que el usuario
                          cambió en Efectos manda sobre la recomendación)
    Edición PRO           completa (Temas 5 y 6), sobria (Tema 5), editorial (Tema 6), neón (Tema 1 con la PRO), o ninguna
    perfil del video      ia_texto.perfil (categoría y tono) si la PRO ya lo calculó
    captions y motions    ritmo (bloques por minuto), tamaño de la palabra grande, motions por minuto y de qué tipo

— y cada rasgo (0–1) lleva la lista de lo que lo movió (`por`). Rasgos: brightness (brillo), transient character (transitorios), density
(densidad), impact strength (impacto), stereo philosophy (estereo), reverb character (reverb), tonal character (tonal), motion character (motion),
UI character (ui), ambient character (ambiente), music energy (energia_musica).

PROJECT SONIC PALETTE = perfil del tema + contexto del video (voz, ruido, música ya mezclada, ambiente) + narración + motions.
"""
import numpy as np

RASGOS = ('brillo', 'transitorios', 'densidad', 'impacto', 'estereo', 'reverb', 'motion', 'ui', 'ambiente', 'energia_musica')

# lo que cada rasgo de la configuración aporta (documentado aquí: la fórmula es una suma acotada a 0–1 desde 0,5)
APORTES = {
    ('estilo', 'kinetic'): {'transitorios': 0.3, 'impacto': 0.3, 'energia_musica': 0.2, 'densidad': -0.1, 'estereo': 0.2, 'reverb': 0.1},
    ('estilo', 'viral'): {'transitorios': 0.2, 'impacto': 0.15, 'ui': 0.2, 'energia_musica': 0.15, 'estereo': 0.1},
    ('estilo', 'guion'): {'transitorios': -0.15, 'impacto': -0.15, 'densidad': 0.15, 'ui': 0.1, 'reverb': -0.1},
    ('estilo', 'tres_lineas'): {},
    ('donde', 'principal'): {'densidad': -0.2, 'impacto': 0.1},
    ('donde', 'todas'): {'densidad': 0.25, 'impacto': -0.15},
    ('donde', 'ninguna'): {'densidad': -0.25},
    ('fx_cortes', 'zoom_blur'): {'motion': 0.2, 'transitorios': 0.1},
    ('fx_cortes', 'destello'): {'ui': 0.1, 'brillo': 0.1},
    ('fx_cortes', 'fuga_de_luz'): {'reverb': 0.1, 'brillo': 0.05},
    ('fx_cortes', 'glitch'): {'brillo': 0.15, 'transitorios': 0.1},
    ('fx_intro_zoom', 'fuerte'): {'impacto': 0.1, 'energia_musica': 0.05},
    ('fx_intro_zoom', 'suave'): {'impacto': -0.05},
    ('pro', 'activa'): {'motion': 0.15, 'densidad': 0.05},
    ('pro', 'sobria'): {'densidad': -0.1, 'impacto': -0.1, 'estereo': -0.15, 'ui': 0.2, 'reverb': -0.1},
    ('pro', 'editorial'): {'brillo': -0.2, 'transitorios': -0.2, 'impacto': -0.2, 'reverb': 0.1, 'energia_musica': -0.15, 'ambiente': 0.1},
    ('pro', 'neon'): {'brillo': 0.25, 'estereo': 0.1, 'energia_musica': 0.05},
    ('tono', 'energico'): {'energia_musica': 0.15, 'transitorios': 0.05},
    ('tono', 'divertido'): {'ui': 0.1, 'densidad': 0.1, 'brillo': 0.05},
    ('tono', 'elegante'): {'brillo': -0.1, 'impacto': -0.1, 'reverb': 0.1},
    ('tono', 'calmado'): {'energia_musica': -0.15, 'densidad': -0.1},
    ('tono', 'serio'): {'densidad': -0.15, 'energia_musica': -0.2},
    ('tono', 'tecnico'): {'ui': 0.1, 'reverb': -0.1},
    ('tono', 'inspirador'): {'reverb': 0.1, 'energia_musica': 0.05},
}
TONAL = {'neon': 'sintético brillante', 'editorial': 'cálido acústico', 'kinetic': 'cinemático', 'viral': 'digital moderno', 'guion': 'limpio (tecleo)',
         'sobria': 'interfaz suave', 'tres_lineas': 'neutro'}


def rasgos_del_tema(pack, formato='v', prefs=None, pro=None, plan_efectos=None):
    """Lo que la configuración REAL del tema dice de su sonido (sin decidir nada todavía). Transición e intro salen del plan de Efectos de ESTE GO
    (desde la 5.21 Efectos ya no aplica las de `recomendaciones`): lo que no se pone no cuenta."""
    import plantillas
    import recomendaciones
    import vista_tema
    import edicion_pro
    prefs = prefs or {}
    estilo = (vista_tema.estilo_de_pack(pack, formato) or {}).get('tipo') or 'tres_lineas'
    rec = recomendaciones.para(pack) or {}
    evs = [e for e in ((plan_efectos or {}).get('eventos') or []) if isinstance(e, dict)]
    v1 = next((e for e in evs if e.get('tipo') == 'v1'), {})
    fx = {'fx_cortes': next((e.get('asset') for e in evs if e.get('tipo') == 'corte'), None) or v1.get('transicion') or None,
          'fx_intro_zoom': v1.get('zoom_intro') if v1.get('zoom_intro') in ('suave', 'normal', 'fuerte') else None,
          'fx_intro_sonido': next((e.get('asset') for e in evs if e.get('tipo') == 'sonido' and e.get('ini') is not None and float(e['ini']) < 1.0), None)}
    pro = pro or {}
    completa = pack in getattr(edicion_pro, 'TEMAS_PRO', ())
    try:
        activa = completa or bool(edicion_pro.activado())
    except Exception:
        activa = completa
    modo_pro = None
    if pack == 'Tema6' or pro.get('estilo_t5') == 'editorial':
        modo_pro = 'editorial'
    elif pack == 'Tema5' or pro.get('tema5'):
        modo_pro = 'sobria'
    elif activa and (pro.get('tema') == 'neon' or pack == 'Kinetic'):
        modo_pro = 'neon'
    try:
        import sfx_rules
        donde_usuario = sfx_rules.cargar_modo().get('donde')
    except Exception:
        donde_usuario = None
    return {'pack': pack, 'tema': plantillas.nombre_visible(pack) if pack else '—', 'estilo': estilo, 'donde': (rec.get('sonido') or {}).get('donde'),
            'donde_usuario': donde_usuario,
            'fx_cortes': fx.get('fx_cortes'), 'fx_intro_zoom': fx.get('fx_intro_zoom'), 'fx_intro_sonido': fx.get('fx_intro_sonido'),
            'pro_activa': bool(activa), 'pro_completa': bool(completa), 'modo_pro': modo_pro, 'recomendacion': rec.get('resumen')}


def perfil(rasgos, captions=None, motions=None, perfil_ia=None):
    """El SONIC PROFILE del tema (con lo que se ve en ESTE video: ritmo de captions y motions). Cada rasgo con su `por`."""
    v = {r: 0.5 for r in RASGOS}
    por = {r: [] for r in RASGOS}

    def aplicar(clave, motivo):
        for r, d in APORTES.get(clave, {}).items():
            v[r] += d
            por[r].append(f'{motivo} ({d:+.2f})')
    aplicar(('estilo', rasgos['estilo']), f"estilo de dibujo «{rasgos['estilo']}»")
    if rasgos.get('donde'):
        aplicar(('donde', rasgos['donde']), f"el tema suena en «{rasgos['donde']}»")
    if rasgos.get('fx_cortes'):
        aplicar(('fx_cortes', rasgos['fx_cortes']), f"transición «{rasgos['fx_cortes']}»")
    if rasgos.get('fx_intro_zoom'):
        aplicar(('fx_intro_zoom', rasgos['fx_intro_zoom']), f"zoom de la intro «{rasgos['fx_intro_zoom']}»")
    if rasgos.get('pro_activa'):
        aplicar(('pro', 'activa'), 'Edición PRO activa')
    if rasgos.get('modo_pro'):
        aplicar(('pro', rasgos['modo_pro']), f"PRO «{rasgos['modo_pro']}»")
    tono = (perfil_ia or {}).get('tono')
    if tono:
        aplicar(('tono', tono), f'tono del video «{tono}»')
    if captions and captions.get('por_minuto'):
        cpm = float(captions['por_minuto'])
        d = float(np.clip((cpm - 20.0) / 40.0, -0.15, 0.15))
        v['densidad'] += d
        v['energia_musica'] += d / 2
        por['densidad'].append(f'{cpm:.0f} captions/min ({d:+.2f})')
        esc = captions.get('escala_clave_media')
        if esc:                                                          # «guion»: la palabra clave crece (Tema 2) o se queda en su tamaño (Tema 4)
            d = float(np.clip((esc - 1.0) * 0.3, -0.1, 0.12))
            v['impacto'] += d
            v['transitorios'] += d / 2
            por['impacto'].append(f'palabra clave a ×{esc:.2f} ({d:+.2f})')
        grande = captions.get('tamano_max')
        if grande:
            d = float(np.clip((grande - 0.15) * 0.8, -0.1, 0.15))
            v['impacto'] += d
            por['impacto'].append(f'palabra grande al {grande:.0%} del cuadro ({d:+.2f})')
    if motions and motions.get('por_minuto') is not None:
        mpm = float(motions['por_minuto'])
        d = float(np.clip((mpm - 6.0) / 30.0, -0.1, 0.2))
        v['motion'] += d
        por['motion'].append(f'{mpm:.1f} motions/min ({d:+.2f})')
    v = {r: round(float(np.clip(x, 0.0, 1.0)), 3) for r, x in v.items()}
    etiquetas = {
        'transitorios': 'suaves' if v['transitorios'] < 0.4 else ('medios' if v['transitorios'] < 0.65 else 'duros'),
        'estereo': 'centrado' if v['estereo'] < 0.4 else ('equilibrado' if v['estereo'] < 0.65 else 'amplio'),
        'reverb': 'seca' if v['reverb'] < 0.4 else ('corta' if v['reverb'] < 0.65 else 'espaciosa'),
        'tonal': TONAL.get(rasgos.get('modo_pro') or rasgos['estilo'], 'neutro'),
        'motion': 'aire suave' if v['motion'] < 0.45 else ('barridos marcados' if v['motion'] < 0.7 else 'movimiento protagonista'),
        'ui': 'mínima' if v['ui'] < 0.45 else ('toques suaves' if v['ui'] < 0.65 else 'clics nítidos'),
        'ambiente': 'mínimo' if v['ambiente'] < 0.45 else ('sutil' if v['ambiente'] < 0.65 else 'presente'),
    }
    return {'valores': v, 'etiquetas': etiquetas, 'por': por, 'rasgos': rasgos,
            'resumen': f"{etiquetas['tonal']} · transitorios {etiquetas['transitorios']} · impacto {v['impacto']:.2f} · densidad {v['densidad']:.2f} · "
                       f"brillo {v['brillo']:.2f} · estéreo {etiquetas['estereo']} · reverb {etiquetas['reverb']} · música {v['energia_musica']:.2f}"}


def paleta(perfil_tema, voz=None, musica=None, ambiente=None, narrativa=None, motions=None):
    """PROJECT SONIC PALETTE: el perfil del tema ajustado a ESTE video (cada ajuste con su porqué)."""
    v = dict(perfil_tema['valores'])
    ajustes = []
    if voz and voz.get('ruido') == 'alto' and not (musica or {}).get('presente'):
        v['densidad'] -= 0.1
        ajustes.append('voz con mucho ruido de fondo: menos sonidos, que se entienda (densidad −0,10)')
    if (musica or {}).get('presente'):
        v['energia_musica'] = max(v['energia_musica'], 0.5)
        v['ambiente'] -= 0.15
        ajustes.append('el video ya trae música: manda su energía; nada de ambientes encima (ambiente −0,15)')
    contextos = {e['contexto'] for e in ((ambiente or {}).get('escenas') or [])}
    if contextos & {'STREET', 'CITY', 'TRAFFIC', 'CROWD', 'CAFE', 'EVENT'}:
        v['ambiente'] += 0.1
        ajustes.append('escenas con ambiente real (calle / gente): se conserva (+0,10)')
    if narrativa and narrativa.get('frases_por_minuto', 0) >= 16:
        v['densidad'] += 0.05
        ajustes.append(f"narración rápida ({narrativa['frases_por_minuto']:.0f} frases/min): +0,05 de densidad")
    if motions and motions.get('por_minuto', 0) >= 10:
        v['impacto'] -= 0.05
        ajustes.append('mucho motion: cada golpe un poco más ligero para que no canse (impacto −0,05)')
    v = {r: round(float(np.clip(x, 0, 1)), 3) for r, x in v.items()}
    return {'valores': v, 'ajustes': ajustes, 'etiquetas': perfil_tema['etiquetas'], 'tema': perfil_tema['rasgos'].get('tema')}
