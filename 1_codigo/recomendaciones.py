# CineCaptions · By Cinema Productions
# 1_codigo/recomendaciones.py — lo que recomendamos para cada estilo: al elegir VIRAL, Kinetic o Referencia el sonido y la página Efectos quedan ya configurados.
"""
recomendaciones.py  (v5.5)
--------------------------
Cada estilo tiene su carácter y le van unos sonidos y unos efectos distintos; en vez de que el usuario los vaya buscando uno a uno, al ELEGIR el estilo (el chip de GO o la
pantalla Estilos) se escriben las preferencias que mejor le sientan. Es una RECOMENDACIÓN: todo se puede cambiar después en Sonido y en Efectos, y no se vuelve a tocar hasta
que se cambie de estilo. v5.4.23: NO toca los interruptores generales del usuario (Efectos, Emojis y Visuales de Inicio): si los apagó, siguen apagados. No toca lo que cambia el video de forma estructural (quitar pausas, música, B-roll, cierre, overlays, mis efectos, intensidad).

    VIRAL       la clave de cada bloque es la protagonista: sonido SOLO en ella (un golpe que sube con el efecto), intro con riser + destello + zoom, el obturador en las transiciones
                («destello»), movimiento suave y sin iconos flotantes (los efectos de la palabra y los emojis ya llenan el cuadro)
    Kinetic     títulos de gancho a toda pantalla: sonido solo en el héroe, intro con zoom fuerte, transición con zoom desenfocado y un temblor en los golpes
    Referencia  la frase se arma palabra a palabra (como escribir): un toque por palabra, intro suave, transición con fuga de luz e iconos pocos

`aplicar(nombre_del_pack)` escribe las preferencias y devuelve un texto corto para el aviso; `para(nombre)` solo consulta.
"""
RECOMENDACIONES = {
    'VIRAL': {
        'resumen': 'sonido solo en la palabra clave · riser de 2 s con destello y zoom en la intro · obturador en las transiciones · movimiento suave',
        'sonido': {'donde': 'principal'},
        'prefs': {'sfx_emojis': True, 'sfx_curva_energia': False,
                  'fx_intro': 'fuga_de_luz', 'fx_intro_sonido': 'viral_hooks_riser', 'fx_intro_zoom': 'normal',
                  'fx_cortes': 'destello', 'fx_cortes_cuanto': 'pocos', 'fx_sonido_corte': 'auto', 'fx_sonido_cortes': True, 'fx_sonido_gancho': True,
                  'fx_zoom': 'suave', 'fx_temblor': 'suave', 'fx_iconos_activo': False},
    },
    'Kinetic': {
        'resumen': 'sonido solo en el héroe · riser con destello y zoom fuerte en la intro · transición con zoom desenfocado · temblor en los golpes',
        'sonido': {'donde': 'principal'},
        'prefs': {'sfx_curva_energia': False,
                  'fx_intro': 'fuga_de_luz', 'fx_intro_sonido': 'viral_hooks_riser', 'fx_intro_zoom': 'fuerte',
                  'fx_cortes': 'zoom_blur', 'fx_cortes_cuanto': 'pocos', 'fx_sonido_corte': 'auto', 'fx_sonido_cortes': True, 'fx_sonido_gancho': True,
                  'fx_zoom': 'suave', 'fx_temblor': 'normal', 'fx_iconos_activo': False},
    },
    'Referencia': {
        'resumen': 'un toque por palabra (como escribir) · riser con destello y zoom suave en la intro · fuga de luz en las transiciones · pocos iconos',
        'sonido': {'donde': 'todas'},
        'prefs': {'sfx_emojis': True, 'sfx_curva_energia': True,
                  'fx_intro': 'fuga_de_luz', 'fx_intro_sonido': 'viral_hooks_riser', 'fx_intro_zoom': 'suave',
                  'fx_cortes': 'fuga_de_luz', 'fx_cortes_cuanto': 'pocos', 'fx_sonido_corte': 'auto', 'fx_sonido_cortes': True, 'fx_sonido_gancho': True,
                  'fx_zoom': 'normal', 'fx_temblor': 'no', 'fx_iconos_activo': True, 'fx_iconos_cuanto': 'pocos'},
    },
}


# v5.5: con «Solo la principal», el sonido de la palabra principal depende de QUÉ EFECTO lleva (clave = el clip de ese estilo, por prefijo): el cristal se parte (Slices), la caja se
# selecciona (Click), la mano arrastra (Whoosh), el héroe de Kinetic cae (Hit). La principal que no lleva efecto (la clave en negrita de VIRAL, la palabra grande de «guion») usa los
# tres toques del modo simple. Son categorías de la biblioteca de sonidos (sfx_library).
SONIDO_POR_CLAVE = (('v shatter', 'Slices'), ('v select', 'Click'), ('v drag', 'Whoosh'), ('k hero', 'Hit'))


def categoria_de_clave(clave):
    """La categoría de sonido de la palabra principal cuyo clip es `clave` («v shatter rosa» → Slices), o None si no tiene una propia."""
    c = str(clave or '')
    for prefijo, categoria in SONIDO_POR_CLAVE:
        if c == prefijo or c.startswith(prefijo + ' '):
            return categoria
    return None


def para(pack):
    """La recomendación del estilo `pack` (por su nombre, sin distinguir mayúsculas) o None si no tiene."""
    clave = str(pack or '').strip().lower()
    for nombre, r in RECOMENDACIONES.items():
        if nombre.lower() == clave:
            return dict(r, nombre=nombre)
    return None


def activas():
    """False si el usuario apagó las recomendaciones (pref recomendar_estilo = False)."""
    try:
        import ajustes_ui
        return ajustes_ui.leer_prefs().get('recomendar_estilo', True) is not False
    except Exception:
        return True


def aplicar(pack, guardar=None):
    """Escribe las preferencias recomendadas para `pack`. `guardar` = función que recibe un dict de preferencias (por defecto ajustes_ui.guardar_prefs; las pruebas pasan la suya).
    Devuelve el texto del aviso (o '' si ese estilo no tiene recomendación o están apagadas)."""
    r = para(pack)
    if not r or not activas():
        return ''
    if guardar is None:
        import ajustes_ui
        guardar = ajustes_ui.guardar_prefs
    guardar(dict(r['prefs']))
    try:
        import sfx_rules
        if sfx_rules.cargar_modo()['modo'] == 'simple':                # con reglas propias (Avanzado) el usuario ya decidió qué suena y cuándo
            sfx_rules.guardar_modo(donde=r['sonido']['donde'])
    except Exception:
        pass
    return f"{r['nombre']}: {r['resumen']}"
