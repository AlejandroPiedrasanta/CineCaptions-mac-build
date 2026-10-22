# CineCaptions · By Cinema Productions
# 1_codigo/estilos_pro.py — v5.20: los ESTILOS y COLORES de cada función de la Edición PRO (página Efectos › Edición PRO), en un solo sitio.
"""
estilos_pro.py  (v5.20)
-----------------------
El usuario (2026-10-19): «que todos los efectos de la edición PRO estén en la página de Efectos por sección y que tengan varios ejemplos para escoger
con su render; lo que escoja es lo que va a aplicarse si activo esa función, adaptándose al video y al tiempo; que me dé la opción de personalizar un
poco los colores (con el Tema 1, que tiene mucho rosado, la píldora la quiero blanca o transparente…); 10 ejemplos por cada caso; en «detrás de ti»
que el sujeto tenga sombra, orilla blanca, resplandor o nada». Los diseños salen de su tablero (Desktop/How to Edit VIRAL Reels with AI/inspiration:
azul noche e índigo, cristal oscuro con borde de luz, halos de dos colores, verde terminal, ámbar, carteles blancos con serif azul, el recorte con
orilla blanca de sticker).

Cada sección (= un interruptor del menú lateral de Proyecto, pro_lateral_ui.OPCIONES) tiene «Automático» (lo de siempre: decide el tema o el video)
y 10 estilos; y unos colores que el usuario puede fijar (si no, los del estilo; y si el estilo no trae, los del tema). LO QUE SE DICE no cambia:
el estilo es la forma y el color, el contenido lo sigue poniendo la PRO según el video (la píldora de «pizza» pasa a «hamburguesa» si se habla de eso).

    SECCIONES / seccion(clave)             -> el catálogo (fuente única: la página, los ejemplos y GO lo leen de aquí)
    leer(op) / guardar_variante / guardar_color
    resolver(clave, op) -> (variante | None, colores)   el estilo elegido (None = Automático) y los colores finales
    vestir(plan, op, t56=False)            -> aplica estilo y color a las piezas del plan (edicion_pro.aplicar, justo antes de renderizar)
    efecto_persona(op) -> {...} | None     «Captions detrás de ti»: sombra / orilla / resplandor de la persona (edicion_pro._comp_magic)
    motions_completo(op) -> {...}          las props de MotionsCompleto (fondo, tema, acento, paleta fija)
    previa(clave, ident) -> (mp4, jpg)     el ejemplo de cada estilo (2_recursos/edicion_pro/estilos_pro, herramientas_dev/hacer_estilos_pro.py)

Preferencia: `pro_estilos` = {clave: {'v': id del estilo ('' = Automático), 'c': {hueco: '#RRGGBB'}}} (edicion_pro.OPCIONES_POR_DEFECTO).
v5.33: las secciones con `sonidos` (el gancho) guardan también 's': '' = el de su estilo, el id de otro estilo, 'ninguno' o la ruta de un
archivo del usuario (si ya no existe, vuelve a ''); y con `zooms`, 'z': '' = el de su estilo, un tipo de intros_gancho.ZOOMS o 'ninguno'.
"""
from pathlib import Path

# las paletas del tablero de inspiración: acento, segundo acento, fondo y texto
PALETAS = {
    'indigo':   {'acento': '#2F6BFF', 'acento2': '#8BB4FF', 'fondo': '#0A1033', 'texto': '#FFFFFF'},
    'violeta':  {'acento': '#8B5CFF', 'acento2': '#E07BFF', 'fondo': '#120A2A', 'texto': '#FFFFFF'},
    'noche':    {'acento': '#4C7DFF', 'acento2': '#9BB7FF', 'fondo': '#0B0D12', 'texto': '#F5F6FA'},
    'papel':    {'acento': '#2F5BE7', 'acento2': '#B8894A', 'fondo': '#F5F4F0', 'texto': '#15161B'},
    'terminal': {'acento': '#2CFF7A', 'acento2': '#B6FF3B', 'fondo': '#07130C', 'texto': '#EFFFF4'},
    'ambar':    {'acento': '#FF7A1A', 'acento2': '#FFC24D', 'fondo': '#140B05', 'texto': '#FFFFFF'},
    'cielo':    {'acento': '#2F6BFF', 'acento2': '#7FB2FF', 'fondo': '#E6EEFF', 'texto': '#0E1A3A'},
    'aurora':   {'acento': '#C06BFF', 'acento2': '#4C8DFF', 'fondo': '#1A0B2E', 'texto': '#FFFFFF'},
    'halo':     {'acento': '#2F6BFF', 'acento2': '#FF7A1A', 'fondo': '#0B0C12', 'texto': '#FFFFFF'},
    'rosa':     {'acento': '#FF3D8B', 'acento2': '#FFB3D1', 'fondo': '#1F0712', 'texto': '#FFFFFF'},
    'mono':     {'acento': '#15161B', 'acento2': '#6B6E78', 'fondo': '#F2F1EC', 'texto': '#15161B'},
}
# los colores rápidos de la fila «Colores» (además de «Automático» y de escribir uno): los del tablero + blanco y negro
MUESTRAS = ['#FFFFFF', '#0B0D12', '#2F6BFF', '#8B5CFF', '#C06BFF', '#FF3D8B', '#FF7A1A', '#FFC24D', '#2CFF7A', '#00C2FF', '#F5F4F0', '#15161B']


def _v(ident, nombre, detalle, paleta=None, **extra):
    return dict(extra, id=ident, nombre=nombre, detalle=detalle, paleta=paleta)


SECCIONES = [
    {'clave': 'pildora', 'titulo': 'Píldora bajo captions',
     'detalle': 'La píldora animada que sale debajo del texto con lo que dices (un lugar, una cifra, un emoji). Su contenido cambia con el video; aquí eliges cómo se ve.',
     'colores': [('fondo', 'Fondo'), ('texto', 'Texto'), ('acento', 'Acento')],
     'variantes': [
         _v('cristal', 'Cristal oscuro', 'Oscura y translúcida, con un brillo del acento.'),
         _v('blanca', 'Blanca', 'Fondo blanco y letra oscura: se lee en cualquier video.'),
         _v('transparente', 'Transparente', 'Solo un contorno blanco: se ve el video detrás.'),
         _v('vidrio', 'Vidrio claro', 'Cristal esmerilado claro, con un brillo arriba.'),
         _v('neon', 'Neón', 'Un borde del acento que brilla.', 'violeta'),
         _v('solida', 'Color sólido', 'Toda del color de acento, con letra blanca.', 'indigo'),
         _v('halo', 'Halo de luz', 'Negra con un borde de luz de dos colores.', 'halo'),
         _v('etiqueta', 'Etiqueta', 'Blanca y recta, con una barra de color a la izquierda.', 'indigo'),
         _v('sticker', 'Sticker', 'Blanca con borde grueso y sombra dura, un poco girada.'),
         _v('degradado', 'Degradado', 'Un degradado de dos colores.', 'aurora'),
     ]},
    # v5.25 (el usuario: «agrega la opción de emoji con diferentes estilos 3D-2D, siempre animados, archivo Lottie, posición e intensidad»): los
    # 2D son los Lottie animados de Google; los 3D, los de Microsoft con movimiento (remotion/src/EmojiPro.tsx). `ajustes`: filas propias de la
    # sección en Efectos (las mismas preferencias que la píldora del menú lateral).
    {'clave': 'emoji', 'titulo': 'Emojis animados',
     'detalle': 'Un emoji animado con lo que dices, junto a los captions y sin tapar caras. El emoji sale de tus palabras; aquí eliges cómo se mueve, dónde y cuántos.',
     'colores': [('acento', 'Brillo y chispas')],
     'ajustes': [('pro_emoji_donde', 'Dónde', [('auto', 'Automático'), ('lado', 'Junto al caption'), ('encima', 'Encima del caption'),
                                              ('cabeza', 'Junto a tu cabeza')]),
                 ('pro_emoji_intensidad', 'Intensidad', [('suave', 'Suave'), ('media', 'Media'), ('fuerte', 'Fuerte')])],
     'variantes': [
         _v('animado', 'Lottie animado', '2D: el emoji animado de Google, que se mueve solo.'),
         _v('rebote', 'Lottie con rebote', '2D: entra con un rebote y da saltitos.'),
         _v('brillo', 'Lottie con brillo', '2D: con un halo de luz de color que late.', 'ambar'),
         _v('burbuja', 'Burbuja de cristal', '2D: dentro de una burbuja de cristal que tiembla.'),
         _v('sticker', 'Sticker', '2D: borde blanco grueso y sombra, un poco girado.'),
         _v('3d_salto', '3D salto', '3D: sube de un salto y rebota con su sombra.'),
         _v('3d_flota', '3D flotando', '3D: flota y se balancea suave.'),
         _v('3d_giro', '3D giro', '3D: entra girando en 3D y se mece.'),
         _v('3d_gelatina', '3D gelatina', '3D: tiembla como gelatina y vuelve a temblar.'),
         _v('3d_estallido', '3D estallido', '3D: estalla en chispas y sigue latiendo.', 'violeta'),
     ]},
    {'clave': 'detras', 'titulo': 'Captions detrás de ti',
     'detalle': 'Cuando el texto pasa por detrás de ti (Magic Mask), cómo se ve tu silueta: con sombra, con una orilla, con resplandor o sin nada.',
     'colores': [('acento', 'Color del efecto')],
     'variantes': [
         _v('nada', 'Sin efecto', 'Tu silueta tal cual, sin nada alrededor.'),
         _v('sombra', 'Sombra suave', 'Una sombra difuminada detrás de ti: te separa del texto.'),
         _v('sombra_dura', 'Sombra marcada', 'Una sombra nítida desplazada, estilo póster.'),
         _v('orilla', 'Orilla blanca', 'Un borde blanco alrededor de tu silueta.'),
         # (sin «Orilla de color», «Doble orilla» ni «Resplandor»: el usuario, «elimina esto»; lo guardado con ellas vuelve a Automático)
         _v('aura', 'Aura blanca', 'Un halo blanco suave, como una luz de contra.'),
         _v('neon', 'Neón', 'Un trazo fino de color con brillo.', 'rosa'),
         _v('sticker', 'Sticker', 'Borde blanco grueso y una sombra: pareces un recorte.'),
     ]},
    # v5.33 (el usuario: «va a ser intros de overlays con zoom para fuera y su sonido, en el primer segundo; solo 8 opciones que cambien de
    # color, música y tipo de zoom»): cada intro = su luz (intros_gancho: los overlays del usuario coloreados), su zoom y su mezcla de sonido.
    # Ya no hay órbita de iconos ni titular del gancho (lo guardado con aquellos estilos vuelve a Automático).
    {'clave': 'gancho', 'titulo': 'Gancho del inicio',
     'detalle': 'El primer segundo: un destello de luz, el video que se aleja con un zoom y un golpe de sonido. Elige una intro y, si quieres, '
                'cambia su color, su sonido o su zoom en «Personaliza».',
     'colores': [('acento', 'Color de la luz'), ('acento2', 'Segundo color')],
     'sonidos': True,                         # (el usuario: «falta la sección de sonido por si el de la intro no me gusta»: fila «Sonido»)
     'zooms': True,                           # (y «te faltó el botón de efecto de zoom»: el zoom de otra intro o ninguno)
     'variantes': [
         _v('blanco', 'Flash blanco', 'Un fogonazo blanco y el video se aleja de golpe.', a=('#FFFFFF', '#CFE0FF'), luz='destello', zoom='golpe',
            sonido='blanco', blanco=1.0),
         _v('lima', 'Lima eléctrica', 'Luz lima con un borde rosa y un zoom suave.', a=('#D4FF3A', '#FF4FA3'), luz='nube', zoom='suave', sonido='lima'),
         _v('neon', 'Verde neón', 'Destello verde y el video sale desenfocado.', a=('#39FF6A', '#E8FF7A'), luz='destello', zoom='desenfoque',
            sonido='neon'),
         _v('violeta', 'Violeta', 'Luz violeta y el cuadro gira al alejarse.', a=('#8B5CFF', '#E07BFF'), luz='destello', zoom='giro', sonido='violeta'),
         _v('fuego', 'Fuego', 'Una raya de luz roja y amarilla con temblor.', a=('#FF2A1A', '#FFC24D'), luz='raya', zoom='temblor', sonido='fuego',
            tau=0.05),
         _v('atardecer', 'Atardecer', 'Una mancha naranja y rosa; el zoom rebota.', a=('#FF7A1A', '#FF3D8B'), luz='mancha', zoom='rebote',
            sonido='atardecer'),
         _v('hielo', 'Hielo', 'Luz cian y los colores se separan un instante.', a=('#00C2FF', '#7FB2FF'), luz='nube', zoom='rgb', sonido='hielo'),
         _v('rosa', 'Rosa y oro', 'Una brasa rosa y dorada; el video entra de un latigazo.', a=('#FF3D8B', '#FFC24D'), luz='brasa', zoom='latigo',
            sonido='rosa'),
     ]},
    {'clave': 'escenas', 'titulo': 'Escenas completas',
     'detalle': 'Las escenas a pantalla completa (cuaderno, chat, polaroid, calendario…) cuando cuentas algo. Eliges el tono y los colores.',
     'colores': [('fondo', 'Fondo'), ('acento', 'Acento')],
     'variantes': [
         _v('noche', 'Noche', 'Escenas oscuras con brillos azules.', 'noche', tono='oscuro', fondo_estilo='aurora'),
         _v('claro', 'Papel claro', 'Escenas claras, como de papel.', 'papel', tono='claro', fondo_estilo='liso'),
         _v('neon', 'Neón violeta', 'Oscuras con luces violeta.', 'violeta', tono='neon', fondo_estilo='rejilla'),
         _v('indigo', 'Índigo eléctrico', 'Azul profundo con luz eléctrica.', 'indigo', tono='oscuro', fondo_estilo='aurora'),
         _v('cielo', 'Cielo', 'Claras, con azules suaves.', 'cielo', tono='claro', fondo_estilo='puntos'),
         _v('ambar', 'Ámbar', 'Oscuras con un brillo naranja cálido.', 'ambar', tono='oscuro', fondo_estilo='aurora'),
         _v('terminal', 'Terminal', 'Negro y verde de pantalla.', 'terminal', tono='oscuro', fondo_estilo='rejilla'),
         _v('aurora', 'Aurora', 'Violeta y azul, mucho color.', 'aurora', tono='color', fondo_estilo='aurora'),
         _v('rosa', 'Rosa', 'Color con acentos rosas.', 'rosa', tono='color', fondo_estilo='puntos'),
         _v('mono', 'Monocromo', 'Blanco y tinta, sin color.', 'mono', tono='claro', fondo_estilo='liso'),
     ]},
    {'clave': 'kit', 'titulo': 'Kit de motions',
     'detalle': 'Listas, ruletas, rutas, títulos neón y cajas misterio sobre el video. Eliges la paleta y el tipo de diseño.',
     'colores': [('acento', 'Acento'), ('acento2', 'Segundo color')],
     'variantes': [
         _v('neon', 'Neón violeta', 'Violeta con brillos: el clásico del kit.', None, tema='neon', a=('#9B5CFF', '#E07BFF')),
         _v('azul', 'Azul eléctrico', 'Azules fríos y luminosos.', None, tema='azul', a=('#2EA8FF', '#8BE6FF')),
         _v('rojo', 'Rojo', 'Rojo y coral, con fuerza.', None, tema='rojo', a=('#FF3344', '#FF8A5C')),
         _v('oro', 'Oro', 'Dorado cálido.', None, tema='oro', a=('#E9B949', '#FFE7A3')),
         _v('editorial', 'Editorial', 'Papel claro y tinta, de revista.', None, tema='editorial'),
         _v('neoncc', 'Magenta y lima', 'El neón del Tema 1: magenta y lima.', None, tema='neoncc'),
         _v('cristal', 'Cristal', 'Piezas de cristal translúcido.', 'indigo', tema='neon',
            prefiere=('cristal', 'cajas', 'flotante', 'limpio', 'arco', 'fila', 'ola')),
         _v('linea', 'Línea fina', 'Diseños de línea, ligeros.', 'noche', tema='neon',
            prefiere=('linea', 'contorno', 'arco', 'ola', 'limpio', 'subida', 'simple')),
         _v('tarjeta', 'Tarjetas', 'Diseños en tarjetas sólidas.', 'ambar', tema='neon',
            prefiere=('tarjeta', 'cajas', 'pila', 'escalera', 'rueda', 'oscuro')),
         _v('terminal', 'Terminal', 'Verde de pantalla sobre negro.', 'terminal', tema='neon'),
     ]},
    {'clave': 'graficos', 'titulo': 'Gráficos',
     'detalle': 'Cifras, listas, mapas con bandera, rótulos y llamadas a la acción. Eliges la tipografía, el panel y los colores.',
     'colores': [('fondo', 'Panel'), ('texto', 'Texto'), ('acento', 'Acento')],
     'variantes': [
         _v('cristal', 'Cristal oscuro', 'Panel oscuro translúcido, letra grotesca.', 'noche', fuente='grotesk', cifra='linea', dato='oscuro'),
         _v('blanca', 'Carta blanca', 'Panel blanco y tinta oscura.', 'papel', fuente='grotesk', cifra='bloque', dato='claro', colores={'fondo': '#FFFFFF'}),
         _v('neon', 'Neón violeta', 'Violeta con brillo.', 'violeta', fuente='grotesk', cifra='anillo', dato='oscuro'),
         _v('editorial', 'Editorial', 'Serif de revista sobre papel.', 'papel', fuente='serif', cifra='linea', dato='claro'),
         _v('terminal', 'Terminal', 'Monoespaciada en verde.', 'terminal', fuente='mono', cifra='bloque', dato='oscuro'),
         _v('ambar', 'Ámbar', 'Naranja cálido sobre negro.', 'ambar', fuente='grotesk', cifra='anillo', dato='oscuro'),
         _v('redonda', 'Redonda amable', 'Letra redonda y azules claros.', 'cielo', fuente='redonda', cifra='bloque', dato='claro'),
         _v('indigo', 'Índigo eléctrico', 'Azul profundo con luz.', 'indigo', fuente='grotesk', cifra='bloque', dato='oscuro'),
         _v('aurora', 'Aurora', 'Violeta y azul, redonda.', 'aurora', fuente='redonda', cifra='anillo', dato='oscuro'),
         _v('minimal', 'Mínimo', 'Letra blanca y casi sin adornos.', 'noche', fuente='grotesk', cifra='ninguno', dato='oscuro'),
     ]},
    {'clave': 'broll', 'titulo': 'B-roll con fotos',
     'detalle': 'Las fotos de internet (con licencia) que salen cuando nombras algo. Eliges cómo se enmarcan.',
     'colores': [('acento', 'Acento'), ('fondo', 'Fondo')],
     'variantes': [
         _v('completa', 'Pantalla completa', 'La foto llena el cuadro con un movimiento lento.'),
         _v('marco', 'Marco blanco', 'Enmarcada en blanco, con una cinta adhesiva.'),
         _v('circulo', 'Círculo', 'En un círculo con un anillo del acento.'),
         _v('polaroid', 'Polaroid', 'Una polaroid girada con la palabra escrita en el pie.'),
         _v('ventana', 'Ventana', 'Dentro de una ventana de app con su barra.', 'indigo'),
         _v('dividida', 'Pantalla dividida', 'La foto arriba y la palabra grande abajo.', 'indigo'),
         _v('inclinada', 'Inclinada', 'Una tarjeta en perspectiva que se endereza.'),
         _v('neon', 'Marco neón', 'Bordes redondos con un borde que brilla.', 'violeta'),
         _v('cinta', 'Cinta de película', 'Dentro de una tira de película que entra.'),
         _v('cristal', 'Cristal', 'En un panel de cristal sobre la misma foto desenfocada.'),
     ]},
    {'clave': 'motions_completo', 'titulo': 'Motions completo',
     'detalle': 'El video de motions que va encima de todo (el titular palabra a palabra y una tarjeta por idea). Eliges el fondo y los colores.',
     'colores': [('fondo', 'Fondo'), ('acento', 'Acento')],
     'variantes': [
         _v('lavanda', 'Lavanda', 'Fondo lavanda claro y tarjetas de colores.', None, tema='claro'),
         _v('noche', 'Noche', 'Fondo oscuro y tarjetas de colores.', None, tema='oscuro'),
         _v('indigo', 'Índigo', 'Azul noche y todo en azul eléctrico.', 'indigo', tema='oscuro', fija=True),
         _v('violeta', 'Violeta', 'Morado oscuro y violeta.', 'violeta', tema='oscuro', fija=True),
         _v('papel', 'Papel', 'Papel cálido y azul de tinta.', None, tema='claro', fija=True, colores={'fondo': '#F5F0E6', 'acento': '#2F5BE7'}),
         _v('cielo', 'Cielo', 'Azul muy claro y azul vivo.', 'cielo', tema='claro', fija=True),
         _v('terminal', 'Terminal', 'Negro y verde de pantalla.', 'terminal', tema='oscuro', fija=True),
         _v('ambar', 'Ámbar', 'Negro cálido y naranja.', 'ambar', tema='oscuro', fija=True),
         _v('rosa', 'Rosa', 'Rosa claro y fucsia.', None, tema='claro', fija=True, colores={'fondo': '#FCE8F0', 'acento': '#E64B8B'}),
         _v('mono', 'Monocromo', 'Gris claro y tinta, sin color.', 'mono', tema='claro', fija=True),
     ]},
]
_POR_CLAVE = {s['clave']: s for s in SECCIONES}
# de la paleta de un estilo, qué colores toma cada sección (la píldora sólida no debe tomar el «fondo» azul noche de su paleta…)
DE_PALETA = {'pildora': ('acento', 'acento2'), 'detras': ('acento',), 'gancho': ('acento', 'acento2'), 'escenas': ('acento', 'fondo'),
             'kit': ('acento', 'acento2'), 'graficos': ('acento', 'texto', 'fondo'), 'broll': ('acento',), 'motions_completo': ('acento', 'fondo'),
             'emoji': ('acento',)}
TEMAS_KIT_SIN_ACENTO = ('editorial', 'neoncc')        # Kit7.pal: estos temas no se rehacen con el acento


def seccion(clave):
    return _POR_CLAVE.get(clave)


def variante(clave, ident):
    s = _POR_CLAVE.get(clave) or {}
    return next((v for v in s.get('variantes') or [] if v['id'] == ident), None)


def _hex(c):
    c = str(c or '').strip().lstrip('#')
    if len(c) in (6, 8) and all(ch in '0123456789abcdefABCDEF' for ch in c):
        return '#' + c.upper()
    return ''


# ----------------------------------------------------------------------------------------------------------------------- preferencias
def leer(op=None):
    """{clave: {'v': id, 'c': {hueco: hex}}} (lo guardado, limpio)."""
    if op is None:
        try:
            import edicion_pro
            op = edicion_pro.opciones_guardadas()
        except Exception:
            op = {}
    crudo = (op or {}).get('pro_estilos') or {}
    out = {}
    for clave, d in crudo.items() if isinstance(crudo, dict) else ():
        if clave not in _POR_CLAVE or not isinstance(d, dict):
            continue
        v = str(d.get('v') or '')
        huecos = {h for h, _e in _POR_CLAVE[clave]['colores']}
        c = {h: _hex(x) for h, x in (d.get('c') or {}).items() if h in huecos and _hex(x)}
        out[clave] = {'v': v if variante(clave, v) else '', 'c': c}
        if _POR_CLAVE[clave].get('sonidos'):
            out[clave]['s'] = _sonido_valido(clave, d.get('s'))
        if _POR_CLAVE[clave].get('zooms'):
            out[clave]['z'] = _zoom_valido(d.get('z'))
    return out


def _zoom_valido(z):
    z = str(z or '').strip()
    try:
        import intros_gancho
        return z if z in ('', intros_gancho.SIN_ZOOM) or z in intros_gancho.ZOOMS else ''
    except Exception:
        return ''


def guardar_zoom(clave, valor):
    """v5.33: el zoom de una sección con `zooms` (el gancho): '' (el de su estilo), un tipo de intros_gancho.ZOOMS o 'ninguno'."""
    _guardar(clave, lambda d: d.__setitem__('z', _zoom_valido(valor)))


def _sonido_valido(clave, s):
    s = str(s or '').strip()
    if s in ('', 'ninguno') or variante(clave, s):
        return s
    try:
        return s if Path(s).is_file() else ''
    except (OSError, ValueError):
        return ''


def guardar_sonido(clave, valor):
    """v5.33: el sonido de una sección con `sonidos`: '' (el de su estilo), el id de otro estilo, 'ninguno' o la ruta de un archivo."""
    _guardar(clave, lambda d: d.__setitem__('s', _sonido_valido(clave, valor)))


def _guardar(clave, cambio):
    import edicion_pro
    todo = dict(edicion_pro.opciones_guardadas().get('pro_estilos') or {})
    d = dict(todo.get(clave) or {})
    cambio(d)
    todo[clave] = d
    edicion_pro.guardar_opciones({'pro_estilos': todo})


def guardar_variante(clave, ident):
    _guardar(clave, lambda d: d.__setitem__('v', ident if variante(clave, ident) else ''))


def guardar_color(clave, hueco, color):
    """`color` = '#RRGGBB' o None/'' (vuelve a Automático)."""
    def cambio(d):
        c = dict(d.get('c') or {})
        if _hex(color):
            c[hueco] = _hex(color)
        else:
            c.pop(hueco, None)
        d['c'] = c
    _guardar(clave, cambio)


def colores_de_variante(clave, v):
    """Los colores que trae un estilo (de su paleta, y los suyos propios), solo los huecos de esa sección."""
    if not v:
        return {}
    huecos = [h for h, _e in _POR_CLAVE[clave]['colores']]
    pal = {k: x for k, x in (PALETAS.get(v.get('paleta') or '') or {}).items() if k in DE_PALETA.get(clave, ())}
    if v.get('a'):
        pal['acento'], pal['acento2'] = v['a']
    pal.update(v.get('colores') or {})
    return {h: pal[h] for h in huecos if pal.get(h)}


def resolver(clave, op=None, est=None):
    """(variante elegida o None = Automático, colores finales {hueco: hex}): los del usuario mandan sobre los del estilo."""
    est = leer(op) if est is None else est
    d = est.get(clave) or {}
    v = variante(clave, d.get('v') or '')
    col = colores_de_variante(clave, v)
    col.update(d.get('c') or {})
    return v, col


# ----------------------------------------------------------------------------------------------------------------------- en GO
def seccion_de_pieza(p):
    """La sección (clave) a la que pertenece una pieza del plan, o None (captions, velos, piezas del kit neón del Tema 1…)."""
    if not isinstance(p, dict):
        return None
    if p.get('pieza') == 'fondo':                       # el fondo animado de una escena (va con su escena)
        return 'escenas'
    try:
        import motions_catalogo as MC
        import pro_lateral_ui as LAT
        ident = MC.id_de_pieza(p)
    except Exception:
        return None
    if not ident:
        return None
    for o in LAT.OPCIONES:
        if ident in set(LAT.ids_de(o['clave'])) or (o['clave'] == 'pildora' and ident == 'acompanante'):
            return o['clave']
    return None


def _mezcla(h, con, q):
    h = _hex(h)[1:7] or '000000'
    return '#' + ''.join(f'{round(int(h[i:i + 2], 16) + (con - int(h[i:i + 2], 16)) * q):02X}' for i in (0, 2, 4))


def _claro(h):
    h = _hex(h)[1:7]
    if not h:
        return False
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b > 150


def _og(c):
    """Un color para una pieza OGraf: su manifiesto pide '#rrggbb' en minúsculas (gddType color-rrggbb)."""
    return _hex(c)[:7].lower()


def _props_ograf(pieza):
    try:
        import edicion_pro_ograf as OG
        return {n for n, _d in OG.ESQUEMAS[pieza]['props']}
    except Exception:
        return set()


def _vestir_pildora(p, v, c, _ctx):
    val = p.setdefault('valores', {})
    if v:
        val['variante'] = v['id']
    for h in ('acento', 'acento2', 'fondo'):
        if c.get(h):
            val[h] = c[h]
    if c.get('texto'):
        val['tinta'] = c['texto']


def _vestir_gancho(p, v, c, _ctx):
    val = p.setdefault('valores', {})
    comp, pieza = str(p.get('remotion') or ''), str(p.get('pieza') or '')
    if comp == 'OrbitaT5':
        if v:
            val['estilo'] = v['id']
        for h, k in (('acento', 'acento'), ('acento2', 'acento2'), ('texto', 'tinta')):
            if c.get(h):
                val[k] = c[h]
    elif comp == 'StickerT5':
        if c.get('acento'):
            val['acento'] = c['acento']
    elif pieza == 'orbita':
        if v:
            val['estilo'] = v['id']
        for h, k in (('acento', 'acento'), ('acento2', 'acento2'), ('texto', 'colorAnillo')):
            if c.get(h):
                val[k] = _og(c[h])
    elif pieza == 'titular':
        if v and v.get('fuente'):
            val['fuente'] = v['fuente']
        if c.get('acento'):
            val['acento'] = _og(c['acento'])
        if c.get('texto'):
            val['colorTexto'] = _og(c['texto'])


def _tono_escena(comp, var):
    try:
        import edicion_pro_escenas as ES
        if (comp, var) in ES.CLAROS:
            return 'claro'
    except Exception:
        pass
    if var in ('neon', 'morado'):
        return 'neon'
    if var in ('oscuro', 'negro', 'azul', 'gris', 'madera', 'estudio'):
        return 'oscuro'
    return 'color'


ORDEN_TONO = {'oscuro': ('oscuro', 'neon', 'color'), 'claro': ('claro', 'color', 'oscuro'), 'neon': ('neon', 'oscuro', 'color'), 'color': ('color', 'neon', 'oscuro')}


def _vestir_escenas(p, v, c, ctx):
    val = p.setdefault('valores', {})
    comp = str(p.get('remotion') or '')
    if p.get('pieza') == 'fondo':                       # el fondo animado (OGraf): siempre oscuro (lo de encima va en letra clara)
        if v and v.get('fondo_estilo'):
            val['estilo'] = v['fondo_estilo']
        ac = c.get('acento')
        base = c.get('fondo')
        if base and _claro(base):
            base = _mezcla(ac or base, 0, 0.82)
        if ac:
            val['color1'] = _og(ac)
        if base:
            val['color2'], val['color3'] = _og(base), _og(_mezcla(base, 255, 0.18))
        return
    try:
        import edicion_pro_escenas as ES
    except Exception:
        return
    if comp in ES.VARIANTES and v and v.get('tono'):
        opciones = list(ES.VARIANTES.get(comp) or [])
        actual = str(val.get('variante') or '')
        if ctx.get('t56') and actual:                   # Temas 5/6: los captions ya van en la tinta de ese fondo: solo variantes igual de claras
            claro = _tono_escena(comp, actual) == 'claro'
            opciones = [o for o in opciones if (_tono_escena(comp, o) == 'claro') == claro]
        for tono in ORDEN_TONO.get(v['tono'], (v['tono'],)):
            elegida = next((o for o in opciones if _tono_escena(comp, o) == tono), None)
            if elegida:
                val['variante'] = elegida
                break
    if c.get('acento') and comp not in ES.SIN_ACENTO:
        val['acento'] = c['acento']
    fondo = c.get('fondo')                              # el fondo del estilo o del usuario, solo si es igual de claro que el diseño (la letra se lee)
    if fondo and comp in ES.VARIANTES and comp not in ('FotoE', 'Pictos3DE'):
        tono = _tono_escena(comp, str(val.get('variante') or ''))
        if tono != 'color' and _claro(fondo) == (tono == 'claro'):
            val['fondoEscena'] = fondo


def _vestir_kit(p, v, c, ctx):
    val = p.setdefault('valores', {})
    comp = str(p.get('remotion') or '')
    try:
        import edicion_pro_kit7 as K7
        permitidas = list(K7.VARIANTES.get(comp) or [])
    except Exception:
        permitidas = []
    if v:
        if v.get('tema'):
            val['tema'] = v['tema']
        for pref in v.get('prefiere') or ():
            if pref in permitidas:
                val['variante'] = pref
                break
    tema = str(val.get('tema') or '')
    if tema == 'neoncc' and (ctx.get('usuario') or {}).get('acento'):
        val['tema'] = tema = 'neon'                     # el Tema 1 con el acento del usuario: la paleta se rehace con SU color
    if tema in TEMAS_KIT_SIN_ACENTO:                    # editorial (papel) y magenta-lima: paleta fija (Kit7.pal no usa el acento)
        val.pop('acento', None)
        val.pop('acento2', None)
        return
    for h in ('acento', 'acento2'):
        if c.get(h):
            val[h] = c[h]


def _vestir_graficos(p, v, c, ctx):
    val = p.setdefault('valores', {})
    if p.get('remotion'):                               # mapa con bandera, tarjetas y pantallas de los Temas 5/6: su acento
        if c.get('acento'):
            val['acento'] = c['acento']
        return
    pieza = str(p.get('pieza') or '')
    props = _props_ograf(pieza)
    if v:
        if 'fuente' in props and v.get('fuente'):
            val['fuente'] = v['fuente']
        if pieza == 'cifra' and v.get('cifra'):
            val['estilo'] = v['cifra']
        if pieza == 'dato' and v.get('dato'):
            val['tema'] = v['dato']
    if c.get('acento') and 'acento' in props:
        val['acento'] = _og(c['acento'])
    con_panel = bool(props & {'colorPanel', 'colorBloque'}) or (pieza == 'dato' and val.get('tema') == 'claro')
    texto = c.get('texto')
    if texto and not con_panel and 'texto' not in (ctx.get('usuario') or {}) and not _claro(texto):
        texto = None                                    # la tinta oscura de una paleta clara es para el panel: sin panel (sobre el video), blanca
    if texto and 'colorTexto' in props:
        val['colorTexto'] = _og(texto)
    if c.get('fondo'):
        for k in ('colorPanel', 'colorBloque'):
            if k in props:
                val[k] = _og(c['fondo'])


def _vestir_broll(p, v, c, _ctx):
    val = p.setdefault('valores', {})
    if v:
        val['variante'] = v['id']
    for h in ('acento', 'fondo'):
        if c.get(h):
            val[h] = c[h]


_VESTIR = {'pildora': _vestir_pildora, 'gancho': _vestir_gancho, 'escenas': _vestir_escenas, 'kit': _vestir_kit, 'graficos': _vestir_graficos,
           'broll': _vestir_broll}


def vestir(plan, op=None, t56=False):
    """Pone el estilo y los colores elegidos en las piezas del plan (las que no son «Automático» sin colores no se tocan). Devuelve
    {clave: cuántas piezas}. Va al final (edicion_pro.aplicar, antes de renderizar): manda sobre el color del video y el neón del Tema 1."""
    est = leer(op if op is not None else (plan or {}).get('opciones'))
    cuenta = {}
    ctx = {'t56': bool(t56)}
    for p in (plan or {}).get('piezas') or []:
        clave = seccion_de_pieza(p)
        if clave not in _VESTIR:
            continue
        v, c = resolver(clave, est=est)
        if v is None and not c:
            continue
        try:
            ctx['usuario'] = (est.get(clave) or {}).get('c') or {}
            _VESTIR[clave](p, v, c, ctx)
            cuenta[clave] = cuenta.get(clave, 0) + 1
        except Exception:
            pass
    return cuenta


# «Captions detrás de ti»: lo que se le hace a la silueta (edicion_pro._comp_magic lo convierte en nodos de Fusion). Medidas en fracción del ANCHO
# del clip (ErodeDilate, Blur y el desplazamiento de la sombra lo son); `color` de las orillas / resplandor.
EFECTOS_PERSONA = {
    # (dx en fracción del ANCHO y dy del ALTO, como el Center de Fusion; probado en Resolve 21.1.1: la capa de la persona se corta bajo el
    #  caption, así que la sombra va sobre todo AL LADO, sobre las letras de detrás; hacia abajo quedaba fuera y no se veía)
    'sombra':       {'sombra': {'opacidad': 0.85, 'blur': 0.02, 'dx': 0.02, 'dy': -0.006}},
    'sombra_dura':  {'sombra': {'opacidad': 0.9, 'blur': 0.003, 'dx': 0.028, 'dy': -0.008}},
    'orilla':       {'orillas': [{'ancho': 0.006, 'color': '#FFFFFF'}]},
    'aura':         {'brillo': {'ancho': 0.002, 'blur': 0.028, 'fuerza': 1.0, 'color': '#FFFFFF'}},
    'neon':         {'brillo': {'ancho': 0.004, 'blur': 0.02, 'fuerza': 1.8, 'color': 'acento'}, 'orillas': [{'ancho': 0.003, 'color': 'acento'}]},
    'sticker':      {'sombra': {'opacidad': 0.6, 'blur': 0.012, 'dx': 0.014, 'dy': -0.005}, 'orillas': [{'ancho': 0.012, 'color': '#FFFFFF'}]},
}


def efecto_persona(op=None, ident=None, colores=None):
    """El efecto de la silueta de «Captions detrás de ti» con los colores ya puestos, o None (Automático / Sin efecto)."""
    if ident is None:
        v, c = resolver('detras', op)
        ident = v['id'] if v else ''
    else:
        c = dict(colores_de_variante('detras', variante('detras', ident)), **(colores or {}))
    base = EFECTOS_PERSONA.get(ident)
    if not base:
        return None
    acento = c.get('acento') or '#2F6BFF'
    import copy
    ef = copy.deepcopy(base)
    for o in ef.get('orillas') or []:
        o['color'] = acento if o['color'] == 'acento' else o['color']
    if ef.get('brillo') and ef['brillo']['color'] == 'acento':
        ef['brillo']['color'] = acento
    ef['id'] = ident
    return ef


def motions_completo(op=None):
    """Las props de MotionsCompleto del estilo elegido ({} = Automático: lavanda y tarjetas de colores, como siempre)."""
    return props_motions_completo(*resolver('motions_completo', op))


def props_motions_completo(v, c):
    out = {}
    if v:
        out['tema'] = v.get('tema') or 'claro'
        out['fija'] = bool(v.get('fija'))
    if c.get('fondo'):                                  # el tema (tinta de las tarjetas) sigue a lo claro u oscuro del fondo
        out['fondo'] = c['fondo']
        out['tema'] = 'claro' if _claro(c['fondo']) else 'oscuro'
    if c.get('acento'):
        out['acento'] = c['acento']
        if not v:
            out['fija'] = True
    return out


def elegido_algo(clave, op=None):
    v, c = resolver(clave, op)
    return bool(v or c)


# ----------------------------------------------------------------------------------------------------------------------- ejemplos
def carpeta_previas() -> Path:
    try:
        import edicion_pro
        return Path(edicion_pro.carpeta_recursos()) / 'estilos_pro'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'edicion_pro' / 'estilos_pro'


def previa(clave, ident):
    """(mp4 | None, jpg | None) del ejemplo de un estilo ('' = Automático: `<clave>_auto`), 9:16 como las tarjetas de la página."""
    base = carpeta_previas() / f'{clave}_{ident or "auto"}'
    m, j = base.with_suffix('.mp4'), base.with_suffix('.jpg')
    return (m if m.is_file() else None), (j if j.is_file() else None)
