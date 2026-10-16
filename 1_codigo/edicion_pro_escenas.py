# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_escenas.py — v5.5.3: el director de las ESCENAS A PANTALLA COMPLETA (B-roll de motion graphics, remotion/src/Escenas9.tsx)
# que explican lo que se dice: pictograma, tablero, polaroid, cuaderno, fecha, vidrio, chat, collage, móvil y tijeras.
#   · QUÉ y CUÁNDO: la IA local las elige del mismo menú que el kit (edicion_pro_kit7.MOTIONS + `menu()`), con los datos DICHOS; `desde_ia_uno`
#     valida (nada inventado). Sin IA, las reglas (`reglas`): palabras que las disparan (trabajar → pictograma trabajando, «17 de octubre» → fecha,
#     «mensaje» → chat, «perfil» → móvil, «editar» → tijeras…). Variedad: las familias menos usadas en los últimos videos ganan (historial del kit).
#   · DÓNDE: tapan el video (capa 'fondo', 'pantalla'); en los Temas 1–4 los captions bajan a la parte de abajo mientras dura la escena
#     (edicion_pro.aplicar → mover) y en los Temas 5/6 van abajo en tinta clara u oscura (edicion_pro_tema5). Todo lo importante de cada escena
#     queda por encima del 78 % del alto.
#   · SUENAN: `sonidos(comp, props)` da los eventos (whoosh de entrada, alfileres, papel, obturador, tic…) para edicion_pro_sonido.
"""
    reglas(textos, plegadas, tiempos, idioma, recortes=None) -> [momento]      desde_ia_uno(pr, frases, plegadas, textos, tiempos, idioma) -> momento | None
    menu() -> {familia: [cuándo, datos]}       completar(momentos, video, duracion)  (fotogramas del video para polaroid / tablero / móvil)
    sonidos(comp, props, dur) -> [(t, clave, qué)]
    momento = {'i', 't', 'id', 'fam', 'comp', 'props', 'dur', 'alto', 'pantalla': True}
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

COMP = {'pictograma': 'PictogramaE', 'tablero': 'TableroE', 'polaroid': 'PolaroidE', 'cuaderno': 'CuadernoE', 'fecha': 'FechaE', 'vidrio': 'VidrioE',
        'chat': 'ChatE', 'collage': 'CollageE', 'movil': 'MovilE', 'tijeras': 'TijerasE', 'foto': 'FotoE'}
FAMILIAS = tuple(COMP)
COMPS = frozenset(COMP.values())
DUR = {'pictograma': 3.2, 'tablero': 3.6, 'polaroid': 3.4, 'cuaderno': 3.6, 'fecha': 3.2, 'vidrio': 3.0, 'chat': 3.4, 'collage': 3.2, 'movil': 3.6, 'tijeras': 3.2, 'foto': 3.0}
VARIANTES = {'PictogramaE': ['oscuro', 'claro', 'neon'], 'TableroE': ['gris', 'corcho', 'oscuro'], 'PolaroidE': ['rojo', 'crema', 'azul'],
             'CuadernoE': ['verde', 'madera', 'gris'], 'FechaE': ['naranja', 'dorado', 'rojo'], 'VidrioE': ['morado', 'azul', 'negro'],
             'ChatE': ['morado', 'whatsapp', 'oscuro'], 'CollageE': ['claro', 'oscuro', 'menta'], 'MovilE': ['oscuro', 'claro', 'rojo'], 'TijerasE': ['neon', 'claro'],
             'FotoE': ['completa', 'marco', 'circulo']}
# las de fondo claro (los captions encima van en tinta oscura en los Temas 5/6)
CLAROS = {('PictogramaE', 'claro'), ('TableroE', 'gris'), ('TableroE', 'corcho'), ('PolaroidE', 'crema'), ('CollageE', 'claro'), ('CollageE', 'menta'),
          ('MovilE', 'claro'), ('TijerasE', 'claro')}
# las que no se pintan con el color del video (su color dice algo: el hilo rojo, el calendario, WhatsApp…)
SIN_ACENTO = {'TableroE', 'PolaroidE', 'CuadernoE', 'FechaE', 'ChatE', 'TijerasE'}
Y_CAPTIONS = {True: 86.0, False: 86.0}
CUANTOS = {'foto': 3}                             # cuántas de una misma familia por video (las demás, una: variedad)
# lo concreto manda: una fecha dicha pesa más que un concepto suelto (se resta a las veces que salió esa escena en los últimos videos)
PRIORIDAD = {'fecha': 3.5, 'tablero': 2.0, 'chat': 2.0, 'movil': 2.0, 'tijeras': 2.0, 'cuaderno': 2.0, 'polaroid': 1.5, 'pictograma': 1.5, 'vidrio': 1.0, 'collage': 1.0, 'foto': 3.2}   # v5.5.4: la foto de internet, primero (el usuario no veía ninguna)           # dónde van los captions mientras dura una escena (centro, % del alto)

NUM = {'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
VACIAS = set('''a al ante con de del desde el en es esta este esto la las le lo los mas me mi mis muy no nos o para pero por que se si sin su sus te tu tus un una
uno unos unas y ya yo the a an and or of to in on at is are was be it this that my your our we you i so de da do e um uma os as no na''' .split())
CIERRE = ('.', ',', '?', '!', ':', ';')

POSE_DE = {
    'trabajando': 'trabajo trabajar trabajando trabaja trabajamos oficina escritorio computadora editando work working office desk',
    'pensando': 'pensar pienso piensa pensando dudas duda preguntarte pregunto think thinking wonder wondering',
    'corriendo': 'correr corriendo corro prisa rapido urgente run running hurry rush',
    'celebrando': 'celebrar celebrando logre logramos gane ganamos lo_logre feliz celebrate celebrating won',
    'cayendo': 'caer cai cayendo fracase fracasar fallar falle perdi fall falling fail failed',
    'subiendo': 'subir subiendo escalar escalando crecer creciendo nivel progreso climb climbing level',
    'gritando': 'jefe gritar grita gritando presion exigir boss yelling yell pressure',
    'senalando': 'mira fijate atencion look notice',
}
POSES = {w: p for p, ws in POSE_DE.items() for w in ws.split()}
PERSONAJES = set('''editor editora cliente clientes jefe jefa equipo creador creadora creadores emprendedor emprendedora estudiante estudiantes fotografo
fotografa disenador disenadora vendedor vendedora usuario usuarios audiencia seguidores client clients boss team creator creators student students
designer seller user users audience followers'''.split())
TABLERO = set('conectado conectados conectar conexion conexiones relacion pistas historia aniversario resumen trayectoria connected connect clues story anniversary recap journey'.split())
POLAROID = set('recuerdo recuerdos momento momentos foto fotos antes pasado memoria nostalgia hace memory memories moment photo photos before throwback ago'.split())
POLAROID_FUERTES = set('recuerdo recuerdos momento momentos foto fotos pasado memoria nostalgia memory memories moment photo photos throwback'.split())
CUADERNO = set('plan planes lista apunta anota anotalo proximamente pronto tarea tareas objetivos agenda pendiente list soon coming todo notes agenda'.split())
CHAT = set('mensaje mensajes dm escribeme escribenos comentario comentarios comenta comentan whatsapp chat preguntan pregunta message messages comment comments text texting'.split())
MOVIL = set('perfil seguidores instagram tiktok publicacion publicaciones post posts likes followers profile bio feed'.split())
TIJERAS = set('editar edicion editando cortar corte cortes recortar clips clip montaje edit editing cut cuts'.split())
GLIFO_DE = {
    'comunidad': 'users', 'equipo': 'users-group', 'personas': 'users', 'lider': 'crown', 'liderazgo': 'crown', 'rey': 'crown', 'reina': 'chess-queen',
    'seguridad': 'shield', 'seguro': 'lock', 'privacidad': 'lock', 'energia': 'bolt', 'amor': 'heart', 'calidad': 'award', 'premio': 'trophy',
    'meta': 'target', 'objetivo': 'target', 'enfoque': 'target', 'musica': 'music', 'mundo': 'world', 'codigo': 'code', 'inteligencia': 'brain',
    'salud': 'heartbeat', 'fuerza': 'barbell', 'aprender': 'school', 'conocimiento': 'book', 'magia': 'wand', 'infinito': 'infinity', 'estrategia': 'chess-knight',
    'crecimiento': 'trending-up', 'ventas': 'chart-line', 'marca': 'diamond', 'valor': 'diamond', 'confianza': 'shield', 'libertad': 'rocket',
    'community': 'users', 'team': 'users-group', 'people': 'users', 'leader': 'crown', 'leadership': 'crown', 'security': 'shield', 'energy': 'bolt',
    'love': 'heart', 'quality': 'award', 'goal': 'target', 'focus': 'target', 'music': 'music', 'world': 'world', 'strategy': 'chess-knight',
    'growth': 'trending-up', 'sales': 'chart-line', 'brand': 'diamond', 'trust': 'shield', 'freedom': 'rocket',
}
MESES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
         'noviembre': 11, 'diciembre': 12, 'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6, 'july': 7, 'august': 8,
         'september': 9, 'october': 10, 'november': 11, 'december': 12, 'janeiro': 1, 'fevereiro': 2, 'marco': 3, 'maio': 5, 'junho': 6, 'julho': 7,
         'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12}
NOMBRE_MES = {'es': ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE'],
              'en': ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'],
              'pt': ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']}
SEMANA = {'lunes': 'LUN', 'martes': 'MAR', 'miercoles': 'MIÉ', 'jueves': 'JUE', 'viernes': 'VIE', 'sabado': 'SÁB', 'domingo': 'DOM',
          'monday': 'MON', 'tuesday': 'TUE', 'wednesday': 'WED', 'thursday': 'THU', 'friday': 'FRI', 'saturday': 'SAT', 'sunday': 'SUN'}
SELLOS = {'es': {'pronto': 'PRONTO', 'proximamente': 'PRONTO', 'nuevo': 'NUEVO', 'urgente': 'URGENTE', '_': 'IMPORTANTE'},
          'en': {'soon': 'SOON', 'coming': 'SOON', 'new': 'NEW', 'urgent': 'URGENT', '_': 'IMPORTANT'},
          'pt': {'breve': 'EM BREVE', 'novo': 'NOVO', '_': 'IMPORTANTE'}}


def plegar(t):
    t = unicodedata.normalize('NFKD', str(t or '').lower())
    return ''.join(c for c in t if not unicodedata.combining(c)).strip(' .,;:!?¡¿"\'()[]«»…“”')


def _sin_signos(w):
    return str(w or '').strip().strip(''.join(CIERRE) + '¡¿"\'«»“”()')


def _corto(s, maximo):
    """El texto si cabe en `maximo` letras, sin palabras sueltas al final («…frente a la» → «…frente»); si no, ''."""
    ws = str(s or '').split()
    while len(ws) > 1 and plegar(ws[-1]) in VACIAS:
        ws.pop()
    s = ' '.join(ws)
    return s if 0 < len(s) <= maximo else ''


def _frase_de(textos, i, antes=4, despues=4):
    """Los índices de la frase de la palabra i (sin pasar de los signos de cierre), con un tope a cada lado."""
    a = i
    while a > max(0, i - antes) and not str(textos[a - 1]).strip().endswith(CIERRE):
        a -= 1
    z = i
    while z < min(len(textos) - 1, i + despues) and not str(textos[z]).strip().endswith(CIERRE):
        z += 1
    return list(range(a, z + 1))


def _sin_conjuncion(s):
    """«y también historias» no es una línea: si empieza por una conjunción, es un trozo de otra idea (fuera)."""
    ws = str(s or '').split()
    return '' if ws and plegar(ws[0]) in ('y', 'e', 'o', 'u', 'pero', 'ni', 'and', 'but', 'or', 'mas') else str(s or '')


def _texto(textos, idx):
    return ' '.join(_sin_signos(textos[k]) for k in idx if _sin_signos(textos[k]))


def ruta_emoji(nombre, recortes=None):
    """La imagen 3D de un emoji para Remotion: 'stickers/…' (los del programa) o 'fluent/…' (Fluent extra), o '' si no hay."""
    raiz = _recursos()
    if (raiz / 'emojis' / 'png' / f'rcs_emoji_{nombre}.png').exists():
        return f'stickers/rcs_emoji_{nombre}.png'
    if (raiz / 'edicion_pro' / 'fluent_extra' / f'{nombre}.png').exists():
        return f'fluent/{nombre}.png'
    return ''


def _recursos():
    try:
        from sfx_rules import base_recursos
        return Path(base_recursos())
    except Exception:
        return Path(__file__).resolve().parents[1] / '2_recursos'


def glifos():
    try:
        d = json.loads((Path(__file__).resolve().parent / 'remotion' / 'src' / 'glifos.json').read_text(encoding='utf-8'))
        return set(d.get('o') or {}) | set(d.get('f') or {})
    except Exception:
        return set(GLIFO_DE.values())


def _momento(fam, i, t, props):
    comp = COMP[fam]
    return {'i': i, 't': float(t), 'id': f'escena_{fam}', 'fam': fam, 'comp': comp, 'props': props, 'dur': DUR[fam], 'alto': 1.0, 'pantalla': True}


# ------------------------------------------------------------------------------------------------------------------------------------ menú (IA)
def menu():
    gl = ', '.join(sorted(set(GLIFO_DE.values())))
    return {
        'pictograma': ['ESCENA A PANTALLA COMPLETA: un personaje-pictograma HACIENDO lo que se cuenta (trabajar, pensar, correr, celebrar, caer, subir, '
                       'señalar, que le griten) o la persona de la que se habla (editor, cliente, jefe…)',
                       '{"pose": "trabajando|pensando|corriendo|celebrando|cayendo|subiendo|senalando|gritando|parado", "texto": "EDITOR" (1–2 palabras DICHAS), '
                       '"icono": "brain" (opcional, emoji de algo dicho)}'],
        'tablero': ['ESCENA A PANTALLA COMPLETA: varias cosas conectadas, las pistas de una historia, un resumen o aniversario (2–5 cosas que se nombran)',
                    '{"titulo": "…" (dicho), "items": ["…", "…", "…"] (palabras dichas)}'],
        'polaroid': ['ESCENA A PANTALLA COMPLETA: un recuerdo, un momento, una foto, «antes» o algo del pasado (sale una foto del propio video)',
                     '{"pie": "…" (dicho, corto), "palabra": "RECUERDOS" (dicha), "numero": "78" (opcional, dicho)}'],
        'cuaderno': ['ESCENA A PANTALLA COMPLETA: un plan, una lista de pendientes, algo que viene pronto o un anuncio',
                     '{"titulo": "…" (dicho, ≤ 5 palabras), "clave": "palabra del título", "nota": "fecha o cifra dicha" (opcional), "lista": ["…"] (opcional)}'],
        'fecha': ['ESCENA A PANTALLA COMPLETA: se dice una fecha concreta (día y mes, o día de la semana con su número)',
                  '{"dia": 17, "mes": "octubre", "nota": "…" (opcional, dicho)}'],
        'vidrio': ['ESCENA A PANTALLA COMPLETA: un concepto con símbolo claro (comunidad, liderazgo, seguridad, energía, crecimiento, calidad, estrategia…). '
                   'icono: ' + gl, '{"icono": "users", "titulo": "COMUNIDAD" (dicho)}'],
        'chat': ['ESCENA A PANTALLA COMPLETA: un mensaje, DM, comentario o pregunta que alguien escribe', '{"mensaje": "…" (dicho, ≤ 40 letras), "respuesta": "…" (opcional, dicho)}'],
        'collage': ['ESCENA A PANTALLA COMPLETA: una frase con una palabra clave fuerte y un objeto concreto (dinero, tiempo, idea, cerebro…): collage de revista',
                    '{"icono": "money_bag", "linea1": "…", "clave": "…", "linea2": "…"} (todo dicho)'],
        'movil': ['ESCENA A PANTALLA COMPLETA: perfil, seguidores, Instagram/TikTok, publicaciones, likes', '{"titulo": "…" (dicho, ≤ 6 palabras), "clave": "perfil"}'],
        'tijeras': ['ESCENA A PANTALLA COMPLETA: editar, edición, cortar, recortar clips, montaje', '{"titulo": "EDICIÓN" (opcional, dicho)}'],
        'foto': ['ESCENA A PANTALLA COMPLETA con una FOTO REAL de internet de algo concreto y visible que se nombra (perritos, comida, la ciudad, la playa, '
                 'desnutrición, el gimnasio, un bebé…): la mejor para ilustrar un tema', '{"buscar": "puppies" (EN INGLÉS, 1–4 palabras: lo que se VE en la foto), '
                 '"palabra": "perritos" (la palabra DICHA)}'],
    }


# ------------------------------------------------------------------------------------------------------------------------------------ reglas
def _fecha(plegadas, textos, i, idioma):
    """«17 de octubre», «el viernes 17», «October 17» → (dia, mes, semana) o None."""
    p = plegadas[i]
    if not p.isdigit() or not 1 <= int(p) <= 31:
        return None
    dia = int(p)
    mes, semana = None, ''
    for k in (1, 2):                                                    # 17 de octubre · 17 octubre
        if i + k < len(plegadas) and plegadas[i + k] in MESES:
            mes = MESES[plegadas[i + k]]
            break
    if mes is None and i > 0 and plegadas[i - 1] in MESES:              # October 17
        mes = MESES[plegadas[i - 1]]
    for k in (1, 2):
        if i - k >= 0 and plegadas[i - k] in SEMANA:
            semana = SEMANA[plegadas[i - k]]
    if mes is None and not semana:
        return None
    nombres = NOMBRE_MES.get(str(idioma)[:2], NOMBRE_MES['es'])
    return dia, (nombres[mes - 1] if mes else ''), semana


# v5.5.4: el LUGAR que se nombra (para su foto de internet): un nombre propio tras «en / desde / hacia», tras «a» con un verbo de ir o traer, o tras «de»
#         con un sustantivo de sitio cerca («el centro intercultural de Quetzaltenango»). La foto, además, tiene que llevar ese nombre (fuentes_web: exigir).
LUGAR_TRAS = {'en', 'desde', 'hacia', 'in', 'from', 'em', 'dans', 'nach'}
IR_TRAER = set('''trae traen trajo llega llegan llegamos llegue vamos voy fuimos fui viajamos viaje viajar viene vino vienen bienvenidos bienvenidas
regreso volvemos volver visitamos visitar welcome travel traveled going went came brings'''.split())
SITIO = set('''centro ciudad pueblo municipio departamento estado provincia region playa lago volcan calle parque plaza mercado catedral iglesia museo
city town state province beach lake park square market cathedral museum'''.split())


def _lugar(textos, plegadas, i):
    crudo = _sin_signos(textos[i])
    if len(plegadas[i]) < 5 or not crudo[:1].isupper() or i < 2 or str(textos[i - 1]).rstrip().endswith(('.', '!', '?')):
        return ''
    prev = plegadas[i - 1]
    if prev in LUGAR_TRAS or (prev in ('a', 'to') and plegadas[i - 2] in IR_TRAER) or (prev in ('de', 'of') and SITIO & set(plegadas[max(0, i - 4):i - 1])):
        return crudo
    return ''


def reglas(textos, plegadas, tiempos, idioma='es', recortes=None, ya=()):
    """[momento] de escenas por reglas (sin IA): todos los candidatos; quien los pone elige separados y sin repetir familia."""
    import broll
    import edicion_pro_kit7 as K7
    recortes = recortes if recortes is not None else K7.recortes_disponibles()
    lang = str(idioma)[:2]
    out = []
    usadas = set(ya)

    def poner(fam, i, props):
        n = sum(1 for m in out if m['fam'] == fam)
        if (fam not in usadas or n < (8 if fam == 'foto' else CUANTOS.get(fam, 1))) and not (fam == 'foto' and any(m['props'].get('buscar') == props.get('buscar') for m in out)):
            out.append(_momento(fam, i, tiempos[i], props))
            usadas.add(fam)

    def cabe_foto(i):
        """v5.5.4: candidatas a foto repartidas por TODO el video (antes las 3 primeras salían en los primeros 12 s y la separación entre escenas
        dejaba una): hasta 8, a 8 s o más entre sí. Cuántas se ponen (CUANTOS) lo decide quien coloca."""
        fotos = [m for m in out if m['fam'] == 'foto']
        return len(fotos) < 8 and all(abs(tiempos[i] - m['t']) >= 8.0 for m in fotos)

    for i, p in enumerate(plegadas):
        lugar = _lugar(textos, plegadas, i)
        if lugar and cabe_foto(i):
            poner('foto', i, {'buscar': lugar, 'palabra': lugar.upper()[:16], 'exigir': lugar})   # v5.5.4: una foto DE ESE SITIO, de internet
            continue
        f = _fecha(plegadas, textos, i, idioma)
        if f:
            fr = _frase_de(textos, i, 2, 5)
            nota = _corto(_texto(textos, [k for k in fr if k > i + 2]), 26)
            poner('fecha', i, {'dia': f[0], 'mes': f[1], 'semana': f[2], 'nota': nota.upper() if nota else ''})
            continue
        if p in CHAT:
            fr = _frase_de(textos, i, 3, 7)
            msg = _corto(_texto(textos, fr), 48) or _corto(_texto(textos, [k for k in fr if k >= i]), 48)
            if msg:
                poner('chat', i, {'mensaje': msg[:1].upper() + msg[1:], 'idioma': idioma})
            continue
        if p in MOVIL:
            fr = _frase_de(textos, i, 4, 4)
            poner('movil', i, {'titulo': _corto(_texto(textos, fr), 40) or _sin_signos(textos[i]), 'clave': _sin_signos(textos[i]), 'idioma': idioma})
            continue
        if p in TIJERAS:
            poner('tijeras', i, {'titulo': _sin_signos(textos[i]).upper()[:14]})
            continue
        if p in POLAROID:
            fr = _frase_de(textos, i, 3, 3)
            nums = [str(NUM.get(plegar(textos[k]), _sin_signos(textos[k]))) for k in fr if _sin_signos(textos[k]).isdigit() or plegar(textos[k]) in NUM]
            nums = [x for x in nums if x.isdigit() and len(x) <= 3]
            pie = _corto(_texto(textos, fr), 28) or _corto(_texto(textos, fr[:4]), 28) or _sin_signos(textos[i])
            palabra = _sin_signos(textos[i]).upper() if p in POLAROID_FUERTES else {'en': 'MEMORIES', 'pt': 'MEMÓRIAS'}.get(lang, 'RECUERDOS')
            poner('polaroid', i, {'pie': pie[:1].upper() + pie[1:], 'palabra': palabra, 'numero': nums[0] if nums else ''})
            continue
        if p in CUADERNO:
            fr = _frase_de(textos, i, 1, 5)
            tit = _corto(_texto(textos, fr), 34)
            if tit:
                cont = [_sin_signos(textos[k]) for k in fr if plegar(textos[k]) not in VACIAS and len(plegar(textos[k])) >= 4]
                nums = [_sin_signos(textos[k]) for k in _frase_de(textos, i, 4, 8) if any(c.isdigit() for c in textos[k])]
                sellos = SELLOS.get(lang, SELLOS['es'])
                poner('cuaderno', i, {'titulo': tit[:1].upper() + tit[1:], 'clave': max(cont, key=len) if cont else '', 'nota': nums[0] if nums else '',
                                      'sello': sellos.get(p, sellos['_'])})
            continue
        if p in TABLERO:
            fr = _frase_de(textos, i, 6, 8)
            cosas = []
            for k in fr:
                w = plegar(textos[k])
                if k != i and w not in VACIAS and len(w) >= 4 and not w.isdigit() and _sin_signos(textos[k]).capitalize() not in cosas:
                    cosas.append(_sin_signos(textos[k]).capitalize())
            if len(cosas) >= 2:
                imgs = [f'recortes/color/{K7.RECORTES[plegar(c)]}.webp' for c in cosas if K7.RECORTES.get(plegar(c)) in recortes]
                poner('tablero', i, {'titulo': _sin_signos(textos[i]).upper()[:12], 'items': '|'.join(cosas[:4]), 'imagenes': '|'.join(imgs)})
            continue
        if p in POSES:
            fr = _frase_de(textos, i, 5, 5)
            quien = next((_sin_signos(textos[k]).upper() for k in fr if plegar(textos[k]) in PERSONAJES), '')
            img = next((ruta_emoji(K7.RECORTES[plegar(textos[k])]) for k in fr if plegar(textos[k]) in K7.RECORTES), '')
            poner('pictograma', i, {'pose': POSES[p], 'texto': quien or _sin_signos(textos[i]).upper()[:14], 'imagen': img})
            continue
        q = broll.SUSTANTIVOS.get(p)                                 # v5.5.4: la foto real (de internet) antes que el icono de cristal
        if q and len(p) >= 4 and cabe_foto(i):
            poner('foto', i, {'buscar': q, 'palabra': _sin_signos(textos[i]).upper()[:16]})
            continue
        if p in GLIFO_DE:
            poner('vidrio', i, {'icono': GLIFO_DE[p], 'titulo': _sin_signos(textos[i]).upper()[:16]})
            continue
        ic = K7.RECORTES.get(p)
        if ic and ic in recortes and 'collage' not in usadas:
            fr = _frase_de(textos, i, 4, 4)
            l1, l2 = _texto(textos, [k for k in fr if k < i]), _texto(textos, [k for k in fr if k > i])
            if l1 or l2:
                poner('collage', i, {'imagen': f'recortes/trama/{ic}.webp', 'linea1': _corto(l1, 30), 'clave': _sin_signos(textos[i]), 'linea2': _sin_conjuncion(_corto(l2, 30))})
    return out


# ------------------------------------------------------------------------------------------------------------------------------------ IA
def desde_ia_uno(pr, frases, plegadas, textos, tiempos, idioma='es', recortes=None):
    """Una propuesta de la IA para una escena ({'b', 'motion', 'datos', 'ancla'}), validada contra lo que se dice. → momento o None."""
    import edicion_pro_kit7 as K7
    fam = str(pr.get('motion') or '')
    try:
        b = int(pr.get('b'))
    except Exception:
        return None
    if fam not in COMP or not 0 <= b < len(frases):
        return None
    datos = pr.get('datos') if isinstance(pr.get('datos'), dict) else {}
    idx = list(frases[b])
    sig = list(frases[b + 1]) if b + 1 < len(frases) else []
    pleg = set(plegadas[j] for j in idx + sig)

    def dicho(s):
        ws = [plegar(w) for w in str(s or '').split() if plegar(w)]
        return bool(ws) and all(w in pleg or w.isdigit() for w in ws)

    def dicho_o(s, maximo):
        s = _corto(_sin_signos(s), maximo)
        return s if s and dicho(s) else ''

    ancla = plegar(pr.get('ancla') or '')
    i = next((j for j in idx if ancla and plegadas[j] == ancla), idx[0] if idx else None)
    if i is None:
        return None
    lang = str(idioma)[:2]
    props = None
    if fam == 'pictograma':
        pose = str(datos.get('pose') or 'parado')
        texto = dicho_o(datos.get('texto'), 16)
        ic = str(datos.get('icono') or '')
        props = {'pose': pose if pose in set(POSES.values()) | {'parado'} else 'parado', 'texto': texto.upper(), 'imagen': ruta_emoji(ic) if ic else ''}
    elif fam == 'tablero':
        items = [dicho_o(x, 16) for x in (datos.get('items') or []) if isinstance(x, str)]
        items = [x.capitalize() for x in items if x][:5]
        if len(items) < 2:
            return None
        recortes = recortes if recortes is not None else K7.recortes_disponibles()
        imgs = [f'recortes/color/{K7.RECORTES[plegar(c)]}.webp' for c in items if K7.RECORTES.get(plegar(c)) in recortes]
        props = {'titulo': dicho_o(datos.get('titulo'), 14).upper() or items[0].upper(), 'items': '|'.join(items), 'imagenes': '|'.join(imgs)}
    elif fam == 'polaroid':
        num = str(datos.get('numero') or '')
        props = {'pie': dicho_o(datos.get('pie'), 28), 'palabra': dicho_o(datos.get('palabra'), 14).upper(), 'numero': num if num.isdigit() and dicho(num) else ''}
        if not props['pie'] and not props['palabra']:
            return None
    elif fam == 'cuaderno':
        tit = dicho_o(datos.get('titulo'), 34)
        if not tit:
            return None
        clave = dicho_o(datos.get('clave'), 16)
        lista = [dicho_o(x, 16) for x in (datos.get('lista') or []) if isinstance(x, str)]
        sellos = SELLOS.get(lang, SELLOS['es'])
        props = {'titulo': tit[:1].upper() + tit[1:], 'clave': clave if clave and plegar(clave) in plegar(tit) else '', 'nota': dicho_o(datos.get('nota'), 12),
                 'sello': sellos['_'], 'lista': '|'.join(x for x in lista if x)}
    elif fam == 'fecha':
        try:
            dia = int(datos.get('dia'))
        except Exception:
            return None
        mes = MESES.get(plegar(datos.get('mes')))
        if not 1 <= dia <= 31 or not dicho(str(dia)) or (mes and plegar(datos.get('mes')) not in pleg):
            return None
        nombres = NOMBRE_MES.get(lang, NOMBRE_MES['es'])
        semana = next((SEMANA[plegadas[j]] for j in idx + sig if plegadas[j] in SEMANA), '')
        props = {'dia': dia, 'mes': nombres[mes - 1] if mes else '', 'semana': semana, 'nota': dicho_o(datos.get('nota'), 26).upper()}
        if not props['mes'] and not semana:
            return None
    elif fam == 'vidrio':
        ic = str(datos.get('icono') or '')
        tit = dicho_o(datos.get('titulo'), 16)
        if ic not in glifos() or not tit:
            return None
        props = {'icono': ic, 'titulo': tit.upper()}
    elif fam == 'chat':
        msg = dicho_o(datos.get('mensaje'), 40)
        if not msg:
            return None
        props = {'mensaje': msg[:1].upper() + msg[1:], 'respuesta': dicho_o(datos.get('respuesta'), 30), 'idioma': idioma}
    elif fam == 'collage':
        recortes = recortes if recortes is not None else K7.recortes_disponibles()
        ic = str(datos.get('icono') or '')
        clave = dicho_o(datos.get('clave'), 16)
        if ic not in recortes or not clave:
            return None
        props = {'imagen': f'recortes/trama/{ic}.webp', 'linea1': dicho_o(datos.get('linea1'), 30), 'clave': clave, 'linea2': _sin_conjuncion(dicho_o(datos.get('linea2'), 30))}
    elif fam == 'movil':
        tit = dicho_o(datos.get('titulo'), 40)
        if not tit:
            return None
        clave = dicho_o(datos.get('clave'), 16)
        props = {'titulo': tit, 'clave': clave, 'idioma': idioma}
    elif fam == 'tijeras':
        props = {'titulo': dicho_o(datos.get('titulo'), 14).upper()}
    elif fam == 'foto':
        import broll
        palabra = dicho_o(datos.get('palabra'), 16)
        buscar = ' '.join(str(datos.get('buscar') or '').split())[:40]
        if not re.fullmatch(r"[A-Za-z][A-Za-z '\-]{1,39}", buscar or ''):
            buscar = broll.SUSTANTIVOS.get(plegar(palabra)) or ''
        if not palabra or not buscar:
            return None
        props = {'buscar': buscar.lower(), 'palabra': palabra.upper()}
    if props is None:
        return None
    return _momento(fam, i, tiempos[i], props)


# ------------------------------------------------------------------------------------------------------------------------------------ fotos
def _internet_activo():
    try:
        import edicion_pro
        return bool(edicion_pro.opciones_guardadas().get('pro_internet', True))
    except Exception:
        return True


def _formato(video):
    try:
        import edicion_pro
        w, h, _d, _f = edicion_pro.medir(video)
        return 'h' if w and h and w > h else 'v'
    except Exception:
        return 'v'


def foto_del_tema(textos, perfil=None, formato='v', evitar=(), lado=900):
    """v5.5.8 (pedido: «que busque imágenes de referencia en internet del tema que se está hablando, para que el motion no capture siempre la
    misma imagen del video»): una foto de internet con licencia de lo que se dice en `textos` (una cosa concreta: broll.SUSTANTIVOS) o, si no, del
    TEMA del video (las búsquedas en inglés que da la IA local en su perfil: `perfil['fotos']`). Solo las que no piden el crédito en pantalla
    (va a creditos_broll.txt). Devuelve (data URI, info de fuentes_web) o None (sin internet, apagado en Ajustes o sin resultados)."""
    if not _internet_activo():
        return None
    try:
        import broll
        import fuentes_web as FW
    except Exception:
        return None
    consultas = []
    for w in textos or []:
        q = broll.SUSTANTIVOS.get(plegar(str(w)))
        if q and q not in consultas:
            consultas.append(q)
    consultas += [q for q in (perfil or {}).get('fotos') or [] if q and q not in consultas]
    for q in consultas[:4]:
        try:
            r = FW.buscar_foto(q, formato, evitar=evitar, sin_atribucion=True, sin_texto=True)
        except Exception:
            r = None
        if r:
            uri = FW.foto_data_uri(r, lado=lado)
            if uri:
                return uri, r
    return None


def fotos_de_internet(momentos, video):
    """v5.5.3: FotoE con su foto y el tablero con fotos de lo que nombra (si son cosas concretas), de internet y con licencia (fuentes_web),
    todas a la vez. La FotoE que no encuentra foto se quita. Créditos en creditos_broll.txt y en el Registro."""
    if not any(m.get('comp') in ('FotoE', 'TableroE') for m in momentos):
        return momentos
    pedidos = []
    if _internet_activo():
        try:
            import broll
            import fuentes_web as FW
            for m in momentos:
                if m.get('comp') == 'FotoE' and m['props'].get('buscar'):
                    pedidos.append((m, m['props']['buscar']))
                elif m.get('comp') == 'TableroE' and not m['props'].get('imagenes_web'):
                    qs = [broll.SUSTANTIVOS.get(plegar(x)) for x in str(m['props'].get('items') or '').split('|') if x]
                    if sum(1 for q in qs if q) >= 2:
                        pedidos += [(m, q) for q in qs if q]
            if pedidos and FW.hay_red():
                from concurrent.futures import ThreadPoolExecutor
                formato = _formato(video)
                with ThreadPoolExecutor(4) as ex:
                    res = list(ex.map(lambda pq: FW.buscar_foto(pq[1], formato, exigir=pq[0]['props'].get('exigir', '') if pq[0].get('comp') == 'FotoE' else ''), pedidos))
                usadas, de_tablero = [], {}
                for (m, _q), r in zip(pedidos, res):
                    if not r or r['id'] in {u['id'] for u in usadas}:
                        continue
                    uri = FW.foto_data_uri(r)
                    if not uri:
                        continue
                    usadas.append(r)
                    if m['comp'] == 'FotoE':
                        m['props'].update(foto=uri, credito=r['credito'])
                    else:
                        de_tablero.setdefault(id(m), (m, []))[1].append(uri)
                for m, uris in de_tablero.values():
                    if len(uris) >= 2:
                        m['props']['imagenes'] = '|'.join(uris)
                        m['props']['imagenes_web'] = True
                FW.anotar_creditos(usadas, video)
                if usadas:
                    try:
                        import registro
                        registro.info(f'Edición PRO: {len(usadas)} fotos de internet con licencia (créditos en DaVinciSubtitles/creditos_broll.txt).', 'edición PRO')
                    except Exception:
                        pass
        except Exception:
            pass
    momentos[:] = [m for m in momentos if m.get('comp') != 'FotoE' or m['props'].get('foto')]
    return momentos


def completar(momentos, video, duracion, perfil=None):
    """Las fotos de internet (fotos_de_internet) y polaroid, tablero y móvil: v5.5.8, primero con fotos de internet DEL TEMA (lo que se nombra
    en esa escena o el tema del video según la IA local: `foto_del_tema`), distintas entre sí; si no hay internet o no aparece nada, con
    FOTOGRAMAS del propio video (de otro momento, como un recuerdo)."""
    fotos_de_internet(momentos, video)
    if not video or not Path(str(video)).exists():
        return momentos
    try:
        import edicion_pro_tema5 as T5
    except Exception:
        return momentos
    dur = float(duracion or 0) or 30.0
    formato, usadas = _formato(video), []
    for m in momentos:
        if m.get('comp') not in ('PolaroidE', 'TableroE', 'MovilE') or (m['comp'] == 'TableroE' and m['props'].get('imagenes')):
            continue
        textos = ' '.join(str(v) for k, v in (m.get('props') or {}).items() if k in ('palabra', 'pie', 'titulo', 'clave', 'items')).replace('|', ' ').split()
        cuantas = 1 if m['comp'] == 'PolaroidE' else 3
        fotos = []
        for _ in range(cuantas):
            r = foto_del_tema(textos, perfil, formato, evitar=[u['id'] for u in usadas], lado=600)
            if not r:
                break
            fotos.append(r[0])
            usadas.append(r[1])
        if len(fotos) < cuantas:                                            # sin internet o sin bastantes: lo que falte, del propio video
            t0 = float(m['t'])
            otros = [x for x in (dur * 0.12, dur * 0.3, dur * 0.5, dur * 0.7, dur * 0.88) if abs(x - t0) > 2.0][:4]
            fotos += [f for f in (T5.foto(video, x, ancho=480) for x in otros) if f][:cuantas - len(fotos)]
        if not fotos:
            continue
        if m['comp'] == 'PolaroidE':
            m['props']['foto'] = fotos[0]
        elif m['comp'] == 'TableroE' and not m['props'].get('imagenes'):
            m['props']['imagenes'] = '|'.join(fotos)
        elif m['comp'] == 'MovilE':
            m['props']['imagenes'] = '|'.join(fotos)
    if usadas:
        try:
            import fuentes_web as FW
            FW.anotar_creditos(usadas, video)
        except Exception:
            pass
    return momentos


# ------------------------------------------------------------------------------------------------------------------------------------ sonido
def sonidos(comp, props, dur):
    """Los eventos de sonido de una escena (segundos desde que empieza): [(t, clave de edicion_pro_sonido.CARPETAS, qué)]. El whoosh de entrada y
    de salida lo pone edicion_pro_sonido."""
    v = props or {}
    ev = []
    if comp == 'PictogramaE':
        pose = v.get('pose')
        ev.append((0.35, 'pop', 'aparece el personaje'))
        if pose == 'gritando':
            ev.append((0.3, 'hit', 'el jefe golpea la mesa'))
        elif pose == 'celebrando':
            ev.append((0.45, 'correcto', 'celebra'))
        elif pose == 'cayendo':
            ev.append((0.5, 'error', 'se cae'))
        elif pose == 'trabajando':
            ev.append((0.4, 'teclado', 'teclea'))
        if v.get('imagen'):
            ev.append((1.25, 'pop', 'aparece el icono'))
    elif comp == 'TableroE':
        n = max(2, len(str(v.get('items') or '').split('|')))
        for k in range(min(n, 5)):
            ev.append((0.3 + k * 0.16, 'pin', 'se clava una foto'))
        ev.append((0.25 + n * 0.16 + 0.4, 'sello', 'el título'))
    elif comp == 'PolaroidE':
        ev.append((0.12, 'camara', 'la foto'))
        ev.append((0.4, 'click', 'la pinza'))
        if v.get('numero'):
            ev.append((0.95, 'pop', 'la pegatina'))
    elif comp == 'CuadernoE':
        n = len(str(v.get('titulo') or ''))
        ev.append((0.35, 'teclado', 'se escribe a máquina'))
        ev.append((0.6, 'papel', 'la nota'))
        if v.get('sello'):
            ev.append((0.35 + n * max(0.025, min(0.06, 0.9 / max(1, n))) + 0.55, 'sello', 'el sello'))
    elif comp == 'FechaE':
        ev.append((0.35, 'pop', 'se enciende el día'))
        ev.append((0.5, 'papel', 'vuelan los papeles'))
    elif comp == 'VidrioE':
        ev.append((0.1, 'ui', 'entra el cristal'))
        ev.append((0.7, 'ui', 'brillo'))
    elif comp == 'ChatE':
        ev.append((0.1, 'pop', 'burbuja'))
        ev.append((1.0, 'teclado', 'escribe el mensaje'))
        if v.get('respuesta'):
            ev.append((1.0 + len(str(v.get('mensaje') or '')) * 0.045 + 0.4, 'pop', 'la respuesta'))
    elif comp == 'CollageE':
        ev.append((0.12, 'papel', 'el recorte'))
        ev.append((0.55, 'pop', 'la palabra'))
    elif comp == 'MovilE':
        ev.append((0.6, 'ui', 'cuentan las cifras'))
        ev.append((1.5, 'click', 'se pulsa seguir'))
    elif comp == 'FotoE':
        ev.append((0.06, 'camara', 'la foto'))
        ev.append((0.3, 'pop', 'la palabra'))
    elif comp == 'TijerasE':
        ev.append((1.25, 'tijera', 'primer corte'))
        ev.append((1.55, 'tijera', 'segundo corte'))
        ev.append((1.9, 'pop', 'salen los clips'))
    return [(round(t, 3), c, q) for t, c, q in ev if t < float(dur or 3.0) - 0.2]
