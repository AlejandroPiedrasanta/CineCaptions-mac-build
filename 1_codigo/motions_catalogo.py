# CineCaptions · By Cinema Productions
# 1_codigo/motions_catalogo.py — TODOS los motions de la Edición PRO y cuáles puede usar (v5.5.7)
"""
El usuario: «agrega un slider con todos los motions disponibles para que la IA sepa que esos puede usar exclusivamente, y respete la decisión; y deja
el modo automático para que la IA escoja el adecuado».

    catalogo()                 -> [{'id', 'nombre', 'grupo', 'comp', 'detalle'}]   (~150: 100 plantillas por frase, el kit, las escenas, los gráficos
                                   de los Temas 1–4 y las piezas de los Temas 5/6)
    GRUPOS                     -> [(clave, nombre)] en el orden en que se enseñan
    modo(op=None)              -> 'auto' | 'elegidos'           (preferencia `pro_motions_modo`)
    permitido(mid, op=None)    -> bool                          (en «auto», todo)
    id_de_pieza(pieza)         -> el id del motion de una pieza del plan de la PRO (None = no es un motion: captions, velos…)
    filtrar(piezas, op=None)   -> las piezas sin los motions no permitidos (y sin los fondos/velos que solo acompañaban a uno quitado)
    familias_permitidas(fams)  -> las familias del kit/escenas que la IA puede proponer (para su menú)

Se aplica en la fuente (el menú de la IA y las reglas no proponen lo que no está permitido) y, por seguridad, al final del plan (edicion_pro).
"""

GRUPOS = [('plantilla', 'Plantillas por frase'), ('kit', 'Kit de motions'), ('escena', 'Escenas a pantalla completa'),
          ('grafico', 'Gráficos sobre el video'), ('t5', 'Temas 5 y 6')]

NOMBRES_KIT = {'lista': 'Lista de razones', 'ruta': 'Ruta de errores', 'misterio': 'Cajas misterio', 'abanico': 'Abanico de cartas',
               'rueda': 'Rueda de opciones', 'concepto': 'Concepto con icono', 'titulo': 'Título neón', 'mixto': 'Texto + icono',
               'recorte': 'Recorte de revista', 'seleccion': 'Texto seleccionado (iPhone)', 'calendario': 'Cuenta atrás en calendario',
               'red': 'Red neón con interruptor'}
NOMBRES_ESCENA = {'pictograma': 'Pictograma (personaje)', 'tablero': 'Tablero de pistas', 'polaroid': 'Polaroid colgada',
                  'cuaderno': 'Cuaderno con sello', 'fecha': 'Fecha en calendario', 'vidrio': 'Icono de cristal', 'chat': 'Chat de mensajes',
                  'collage': 'Collage de revista', 'movil': 'Móvil con perfil', 'tijeras': 'Tijeras que cortan', 'foto': 'Foto de internet',
                  'personajes': 'Personajes 3D que explican'}
# piezas OGraf de los Temas 1–4 (edicion_pro_planificador) y del mapa
GRAFICOS = [('ograf:titular', 'Titular detrás de la persona'), ('ograf:rotulo', 'Rótulo en bloques'), ('ograf:cifra', 'Cifra grande'),
            ('ograf:lista', 'Lista de puntos'), ('ograf:icono', 'Concepto con icono 3D'), ('ograf:etiqueta', 'Etiqueta y ubicación'),
            ('ograf:orbita', 'Iconos que orbitan la cabeza'), ('ograf:ubicacion', 'Mapa con bandera'), ('ograf:marco', 'Marco de cámara'),
            ('ograf:cta', 'Llamada a la acción'), ('ograf:nombres', 'Nombres de la pareja'), ('acompanante', 'Acompañante bajo el caption')]
T5 = [('t5:escena', 'Escenas de papel'), ('t5:orbita', 'Órbita de iconos 3D'), ('t5:tarjeta', 'Tarjeta sobre la cabeza'),
      ('t5:sticker', 'Sticker congelado del gancho'), ('t5:final', 'Pantalla final con botón'), ('t5:foco', 'Foco en blanco y negro'),
      ('t5:pasos', 'Indicador de pasos'), ('t5:deslizador', 'Deslizador de cristal'), ('t6:visor', 'Visor de cámara (Tema 6)'),
      ('t6:buscar', 'Barra de búsqueda (Tema 6)'), ('t6:perfil', 'Perfil con seguidores (Tema 6)'), ('t6:equipo', 'Píldora del equipo (Tema 6)')]
_COMP_T5 = {'OrbitaT5': 't5:orbita', 'TarjetaT5': 't5:tarjeta', 'AcompananteT5': 'acompanante', 'StickerT5': 't5:sticker', 'FinalT5': 't5:final',
            'PasosT5': 't5:pasos', 'DeslizadorT5': 't5:deslizador', 'EscenaT5': 't5:escena', 'Ubicacion': 'ograf:ubicacion'}
_SIN_MOTION = {'subtitulo', 'velo', 'velo_caption'}
_ACOMPANAN = {'fondo', 'velo'}                        # piezas que solo existen junto a otra (el fondo de una escena, el velo de un titular)


def _kit():
    try:
        import edicion_pro_kit7 as K7
        return dict(K7.COMP)
    except Exception:
        return {}


def _escenas():
    try:
        import edicion_pro_escenas as ES
        return {k: v for k, v in ES.COMP.items() if k not in getattr(ES, 'RETIRADAS', ())}   # v5.5.9: sin muñecos
    except Exception:
        return {}


def _plantillas():
    try:
        import edicion_pro_catalogo as PC
        return list(PC.PLANTILLAS)
    except Exception:
        return []


def _nombre_plantilla(pl):
    pr = pl.get('props') or {}
    t = str(pr.get('titulo') or pr.get('texto') or pr.get('mensaje') or '').strip()
    rama = str(pl.get('rama') or '').strip()
    base = t or str(pl.get('id') or '').replace('_', ' ').capitalize()
    return f'{base} ({rama})' if rama else base


def catalogo():
    out = []
    for pl in _plantillas():
        out.append({'id': 'plantilla:' + str(pl['id']), 'nombre': _nombre_plantilla(pl), 'grupo': 'plantilla', 'comp': pl.get('comp'),
                    'detalle': ', '.join(pl.get('frases') or [])[:80], 'props': dict(pl.get('props') or {}), 'dur': pl.get('dur')})
    for fam, comp in _kit().items():
        out.append({'id': 'kit:' + fam, 'nombre': NOMBRES_KIT.get(fam, fam.capitalize()), 'grupo': 'kit', 'comp': comp, 'detalle': ''})
    for fam, comp in _escenas().items():
        out.append({'id': 'escena:' + fam, 'nombre': NOMBRES_ESCENA.get(fam, fam.capitalize()), 'grupo': 'escena', 'comp': comp, 'detalle': ''})
    comp_de = {v: k for k, v in _COMP_T5.items()}       # (los que son una composición de Remotion tienen miniatura renderizada)
    out += [{'id': i, 'nombre': n, 'grupo': 'grafico', 'comp': comp_de.get(i), 'detalle': ''} for i, n in GRAFICOS]
    out += [{'id': i, 'nombre': n, 'grupo': 't5', 'comp': comp_de.get(i), 'detalle': ''} for i, n in T5]
    return out


def carpeta_previas():
    """Las miniaturas del carrusel de la página Efectos (herramientas_dev/hacer_previas_motions.py)."""
    from pathlib import Path
    try:
        import edicion_pro
        return Path(edicion_pro.carpeta_recursos()) / 'previas_motions'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'edicion_pro' / 'previas_motions'


def archivo_previa(mid):
    return str(mid).replace(':', '_') + '.jpg'


def _op(op):
    if op is not None:
        return op
    try:
        import edicion_pro
        return edicion_pro.opciones_guardadas()
    except Exception:
        return {}


def modo(op=None):
    """'elegidos' solo con «Solo los que elija» Y al menos uno marcado: sin ninguno, la IA elige entre todos (nunca una PRO sin motions por descuido)."""
    op = _op(op)
    return 'elegidos' if str(op.get('pro_motions_modo') or 'auto') == 'elegidos' and op.get('pro_motions') else 'auto'


def permitido(mid, op=None):
    """¿Puede la PRO usar ese motion? En «auto», todos; en «elegidos», solo los marcados por el usuario. Un id desconocido (None) siempre."""
    if not mid:
        return True
    op = _op(op)
    if modo(op) != 'elegidos':
        return True
    return mid in set(op.get('pro_motions') or [])


def id_de_pieza(p):
    """El id del motion de una pieza del plan (None = no es un motion que el usuario elija: captions, velos de legibilidad…)."""
    if not isinstance(p, dict):
        return None
    pieza = str(p.get('pieza') or '')
    if pieza in _SIN_MOTION:
        return None
    comp = str(p.get('remotion') or '')
    pl = str(p.get('plantilla') or '')
    if pl and any(str(x.get('id')) == pl for x in _plantillas()):
        return 'plantilla:' + pl
    kit = {c: f for f, c in _kit().items()}
    if comp in kit:
        return 'kit:' + kit[comp]
    esc = {c: f for f, c in _escenas().items()}
    if comp in esc:
        return 'escena:' + esc[comp]
    if comp == 'EditorialT6':
        return 't6:' + str((p.get('valores') or {}).get('tipo') or '')
    if comp in _COMP_T5:
        return _COMP_T5[comp]
    if pieza == 'skill':
        return 't5:escena'
    if pieza == 'foco':
        return 't5:foco'
    if pieza in _ACOMPANAN:
        return None
    if pieza:
        return 'ograf:' + pieza
    return None


def filtrar(piezas, op=None):
    """Las piezas sin los motions no permitidos. Un fondo o un velo que solo acompañaba a una pieza quitada (mismo tramo) se va con ella."""
    op = _op(op)
    if modo(op) != 'elegidos':
        return list(piezas or [])
    fuera = [p for p in piezas or [] if not permitido(id_de_pieza(p), op)]
    if not fuera:
        return list(piezas or [])
    quedan = [p for p in piezas or [] if p not in fuera]

    def solo_de_quitada(p):
        if str(p.get('pieza') or '') not in _ACOMPANAN:
            return False
        a, z = float(p.get('ini') or 0), float(p.get('fin') or 0)
        tapa = lambda q: min(z, float(q.get('fin') or 0)) - max(a, float(q.get('ini') or 0)) > 0.5 * max(0.1, z - a)      # noqa: E731
        return any(tapa(q) for q in fuera) and not any(tapa(q) for q in quedan if q is not p and id_de_pieza(q))
    return [p for p in quedan if not solo_de_quitada(p)]


def familias_permitidas(familias, op=None):
    """De las familias del menú de la IA (kit + escenas), las permitidas."""
    op = _op(op)
    kit, esc = _kit(), _escenas()
    out = []
    for f in familias:
        mid = 'kit:' + f if f in kit else ('escena:' + f if f in esc else None)
        if mid is None or permitido(mid, op):
            out.append(f)
    return out
