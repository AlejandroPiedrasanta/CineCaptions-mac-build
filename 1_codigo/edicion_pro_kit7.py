# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_kit7.py — v5.5.2: el kit de motion graphics de la skill (1_codigo/remotion/src/Kit7.tsx), EDITABLE para cualquier video:
#   · QUÉ va y CUÁNDO: la IA local lee las frases y elige del MENÚ de motions (modo 'motions' de motor_texto) con sus textos e iconos; lo que propone
#     se valida (solo palabras que se DICEN, iconos que existen, cuántos caben). Sin IA, o si no propone nada válido, las reglas (`momentos`):
#       «3 razones / reasons / motivos / señales / beneficios»         → lista        «4 errores / mistakes / fallos»          → ruta
#       «3 secretos / secrets / preguntas»                              → misterio     «8 lecciones / ideas / tips / consejos…» → abanico
#       «7 hooks / ganchos / formas / maneras / ways»                   → rueda        «éxito», «fracaso», «proceso», «equipo»… → concepto
#     v5.5.3 (Kit8.tsx, referencias del autor):
#       «dinero», «idea», «cerebro», «tiempo», «trofeo»…  → recorte (icono de revista)  «la clave es…», «recuerda…», «lo importante…» → seleccion
#       «30 días», «faltan 10 días»                       → calendario                  «redes», «Instagram», «consumir / crear»…    → red
#   · CÓMO se ve: cada pieza tiene varias VARIANTES de diseño y se elige la menos usada últimamente (historial entre videos: dos videos seguidos
#     no salen iguales) y los COLORES salen del propio video (`paleta_de_video`: su color dominante), salvo el tema editorial.
"""
    planificar(palabras_txt, plegadas, tiempos, frases, idioma, video, duracion, tema_estilo, ia=True, estado=None) -> [momento]
    momentos(plegadas, textos, tiempos, idioma='es', tema='neon', duracion=None)  -> [momento] (las reglas, sin IA)
    desde_ia(propuestas, frases, plegadas, textos, tiempos, duracion)              -> [momento] (lo que propuso la IA, validado)
    vestir(momentos, video, tema_estilo)                                             -> los mismos, con su variante y sus colores
    paleta_de_video(video) -> (acento, acento2) | (None, None)        tema_de(acento_hex) -> 'neon' | 'rojo' | 'azul' | 'oro'
    momento = {'i', 't', 'id', 'comp', 'props', 'dur', 'alto'}
"""
from __future__ import annotations

import colorsys
import hashlib
import json
import random
import unicodedata
from pathlib import Path

NUM = {'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10,
       'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
# plegado → (familia, etiqueta en mayúsculas)
NOMBRES = {
    'razones': ('lista', 'RAZÓN'), 'motivos': ('lista', 'MOTIVO'), 'senales': ('lista', 'SEÑAL'), 'beneficios': ('lista', 'BENEFICIO'), 'causas': ('lista', 'CAUSA'),
    'reasons': ('lista', 'REASON'), 'signs': ('lista', 'SIGN'), 'benefits': ('lista', 'BENEFIT'),
    'errores': ('ruta', 'ERRORES'), 'fallos': ('ruta', 'FALLOS'), 'mistakes': ('ruta', 'MISTAKES'), 'errors': ('ruta', 'ERRORS'),
    'secretos': ('misterio', 'SECRETOS'), 'preguntas': ('misterio', 'PREGUNTAS'), 'secrets': ('misterio', 'SECRETS'), 'questions': ('misterio', 'QUESTIONS'),
    'lecciones': ('abanico', 'LECCIONES'), 'ideas': ('abanico', 'IDEAS'), 'tips': ('abanico', 'TIPS'), 'consejos': ('abanico', 'CONSEJOS'),
    'trucos': ('abanico', 'TRUCOS'), 'reglas': ('abanico', 'REGLAS'), 'habitos': ('abanico', 'HÁBITOS'), 'pasos': ('abanico', 'PASOS'),
    'claves': ('abanico', 'CLAVES'), 'cosas': ('abanico', 'COSAS'), 'herramientas': ('abanico', 'HERRAMIENTAS'), 'cambios': ('abanico', 'CAMBIOS'),
    'lessons': ('abanico', 'LESSONS'), 'hacks': ('abanico', 'HACKS'), 'rules': ('abanico', 'RULES'), 'habits': ('abanico', 'HABITS'),
    'steps': ('abanico', 'STEPS'), 'things': ('abanico', 'THINGS'), 'tools': ('abanico', 'TOOLS'), 'shifts': ('abanico', 'SHIFTS'), 'keys': ('abanico', 'KEYS'),
    'hooks': ('rueda', 'HOOKS'), 'ganchos': ('rueda', 'GANCHOS'), 'formas': ('rueda', 'FORMAS'), 'maneras': ('rueda', 'MANERAS'), 'ways': ('rueda', 'WAYS'),
}
TOPE = {'lista': 5, 'ruta': 6, 'misterio': 4, 'abanico': 8, 'rueda': 12}
# plegado → (palabra que se ve, gráfica, icono, tema)
CONCEPTOS = {
    'exito': ('ÉXITO', 'sube', 'diamante', 'azul'), 'success': ('SUCCESS', 'sube', 'diamante', 'azul'),
    'fracaso': ('FRACASO', 'baja', 'diamante', 'rojo'), 'failure': ('FAILURE', 'baja', 'diamante', 'rojo'),
    'proceso': ('PROCESO', 'sube', 'diamante', 'rojo'), 'process': ('PROCESS', 'sube', 'diamante', 'rojo'),
    'disciplina': ('DISCIPLINA', 'sube', 'rayo', 'rojo'), 'discipline': ('DISCIPLINE', 'sube', 'rayo', 'rojo'),
    'equipo': ('EQUIPO', 'ninguna', 'personas', 'rojo'), 'team': ('TEAM', 'ninguna', 'personas', 'rojo'),
}
# v5.5.3: plegado → icono del RecorteK (2_recursos/edicion_pro/recortes, de Fluent). Solo valen los que estén en recortes/indice.json.
RECORTES = {
    'dinero': 'money_bag', 'plata': 'money_bag', 'money': 'money_bag', 'cash': 'money_bag', 'precio': 'dollar_banknote', 'pagar': 'dollar_banknote',
    'price': 'dollar_banknote', 'idea': 'light_bulb', 'cerebro': 'brain', 'mente': 'brain', 'brain': 'brain', 'mind': 'brain',
    'tiempo': 'alarm_clock', 'reloj': 'alarm_clock', 'time': 'alarm_clock', 'clock': 'alarm_clock', 'ganar': 'trophy', 'ganador': 'trophy',
    'campeon': 'trophy', 'premio': 'trophy', 'win': 'trophy', 'winner': 'trophy', 'rey': 'crown', 'reina': 'crown', 'lider': 'crown',
    'king': 'crown', 'queen': 'crown', 'leader': 'crown', 'importante': 'red_exclamation_mark', 'atencion': 'red_exclamation_mark',
    'important': 'red_exclamation_mark', 'attention': 'red_exclamation_mark', 'anuncio': 'megaphone', 'noticia': 'megaphone',
    'news': 'megaphone', 'crecer': 'chart_increasing', 'crecimiento': 'chart_increasing', 'growth': 'chart_increasing', 'grow': 'chart_increasing',
    'meta': 'bullseye', 'objetivo': 'bullseye', 'goal': 'bullseye', 'target': 'bullseye', 'fuego': 'fire', 'fire': 'fire', 'amor': 'red_heart',
    'love': 'red_heart', 'casa': 'house', 'hogar': 'house', 'home': 'house', 'house': 'house', 'cohete': 'rocket', 'despegar': 'rocket',
    'rocket': 'rocket', 'launch': 'rocket', 'regalo': 'wrapped_gift', 'gift': 'wrapped_gift', 'foto': 'camera', 'camara': 'camera',
    'photo': 'camera', 'camera': 'camera', 'musica': 'musical_notes', 'cancion': 'musical_notes', 'music': 'musical_notes', 'song': 'musical_notes',
    'viaje': 'airplane', 'viajar': 'airplane', 'travel': 'airplane', 'trip': 'airplane', 'libro': 'books', 'libros': 'books', 'leer': 'books',
    'book': 'books', 'books': 'books', 'trabajo': 'briefcase', 'negocio': 'briefcase', 'empresa': 'briefcase', 'business': 'briefcase',
    'job': 'briefcase', 'llave': 'key', 'secreto': 'locked', 'secret': 'locked', 'ojos': 'eyes', 'mira': 'eyes', 'eyes': 'eyes', 'look': 'eyes',
    'buscar': 'magnifying_glass_tilted_left', 'search': 'magnifying_glass_tilted_left', 'diamante': 'gem_stone', 'valor': 'gem_stone',
    'diamond': 'gem_stone', 'value': 'gem_stone', 'pregunta': 'red_question_mark', 'question': 'red_question_mark', 'computadora': 'laptop',
    'laptop': 'laptop', 'computer': 'laptop', 'celular': 'mobile_phone', 'telefono': 'mobile_phone', 'phone': 'mobile_phone',
    'escribir': 'writing_hand', 'write': 'writing_hand', 'trato': 'handshake', 'acuerdo': 'handshake', 'deal': 'handshake',
    'fuerza': 'flexed_biceps', 'fuerte': 'flexed_biceps', 'strong': 'flexed_biceps', 'gym': 'flexed_biceps', 'fiesta': 'party_popper',
    'party': 'party_popper', 'cumpleanos': 'birthday_cake', 'birthday': 'birthday_cake', 'cafe': 'hot_beverage', 'coffee': 'hot_beverage',
    'comida': 'hamburger', 'food': 'hamburger', 'comprar': 'shopping_cart', 'tienda': 'shopping_cart', 'buy': 'shopping_cart', 'shop': 'shopping_cart',
    'paquete': 'package', 'envio': 'package', 'package': 'package', 'carro': 'automobile', 'coche': 'automobile', 'auto': 'automobile',
    'car': 'automobile', 'robot': 'robot', 'peligro': 'warning', 'cuidado': 'warning', 'danger': 'warning', 'warning': 'warning',
    'boom': 'collision', 'increible': 'exploding_head', 'mindblowing': 'exploding_head', 'pensar': 'thinking_face', 'think': 'thinking_face',
    'miedo': 'face_screaming_in_fear', 'fear': 'face_screaming_in_fear', 'salud': 'stethoscope', 'doctor': 'stethoscope', 'health': 'stethoscope',
    'ciencia': 'microscope', 'science': 'microscope', 'juego': 'video_game', 'game': 'video_game', 'mensaje': 'speech_balloon',
    'message': 'speech_balloon', 'energia': 'battery', 'energy': 'battery', 'suerte': 'four_leaf_clover', 'luck': 'four_leaf_clover',
    'perro': 'dog_face', 'dog': 'dog_face', 'gato': 'cat_face', 'cat': 'cat_face', 'mundo': 'globe_showing_europe_africa',
    'world': 'globe_showing_europe_africa', 'sol': 'sun', 'sun': 'sun', 'llegada': 'chequered_flag', 'finish': 'chequered_flag',
    'listo': 'check_mark_button', 'done': 'check_mark_button', 'prohibido': 'prohibited', 'mejor': '1st_place_medal', 'best': '1st_place_medal',
}
# «la clave es la constancia», «recuerda: …», «lo importante es…» → SeleccionK con la palabra que sigue
GATILLOS_SELECCION = {'clave', 'importante', 'recuerda', 'recuerden', 'verdad', 'key', 'important', 'remember', 'truth'}
VACIAS = {'es', 'son', 'era', 'fue', 'la', 'el', 'lo', 'los', 'las', 'un', 'una', 'que', 'de', 'del', 'y', 'a', 'en', 'tu', 'tus', 'mi', 'su', 'esto',
          'is', 'are', 'was', 'the', 'a', 'an', 'to', 'of', 'and', 'that', 'this', 'your', 'my', 'it', 'be'}
DIAS = {'dias', 'dia', 'days', 'day'}
CUENTA_ATRAS = {'faltan', 'quedan', 'falta', 'queda', 'left', 'until', 'remaining', 'countdown'}
REDES = {'redes', 'instagram', 'tiktok', 'youtube', 'facebook', 'seguidores', 'followers', 'algoritmo', 'algorithm', 'reels'}
REDES_LOGO = {'instagram': 'instagram', 'tiktok': 'tiktok', 'youtube': 'youtube', 'facebook': 'facebook', 'reels': 'instagram'}
DUR = {'lista': 3.2, 'ruta': 3.6, 'misterio': 2.8, 'abanico': 3.4, 'rueda': 3.2, 'concepto': 2.8, 'titulo': 3.0, 'mixto': 2.8,
       'recorte': 2.6, 'seleccion': 3.2, 'calendario': 3.2, 'red': 3.8}
COMP = {'lista': 'ListaRazonesK', 'ruta': 'RutaK', 'misterio': 'MisterioK', 'abanico': 'AbanicoK', 'rueda': 'RuedaK', 'concepto': 'ConceptoK',
        'titulo': 'TituloNeonK', 'mixto': 'MixtoK', 'recorte': 'RecorteK', 'seleccion': 'SeleccionK', 'calendario': 'CalendarioK', 'red': 'RedNeonK'}
CUANTOS_POR_VIDEO = {'recorte': 2}                                       # el resto, uno de cada tipo por video
# las variantes de diseño de cada pieza (Kit7.tsx, prop `variante`): 23 diseños × los colores de cada video
VARIANTES = {
    'ListaRazonesK': ['pildora', 'cristal', 'linea', 'tarjeta'], 'MisterioK': ['esferas', 'cajas', 'contorno'], 'RuedaK': ['rueda', 'arco'],
    'AbanicoK': ['abanico', 'fila', 'pila'], 'RutaK': ['ola', 'subida', 'escalera', 'gancho'], 'TituloNeonK': ['neon', 'limpio'],
    'ConceptoK': ['tarjeta', 'flotante', 'linea'], 'MixtoK': ['glitch', 'rotulador'],
    'RecorteK': ['trama', 'color', 'neon'], 'SeleccionK': ['azul', 'rosa', 'oscuro'], 'CalendarioK': ['rojo', 'oscuro', 'papel'], 'RedNeonK': ['interruptor', 'simple'],
}
# alto que ocupa cada pieza (fracción del alto en vertical 1080×1920, con su aire): la regla oficial (ni caras ni captions) busca sitio con esto
# v5.5.3: las escenas a pantalla completa (edicion_pro_escenas + remotion/src/Escenas9.tsx) usan el mismo menú, variantes e historial
try:
    import edicion_pro_escenas as _ES
    VARIANTES.update(_ES.VARIANTES)
    ESCENAS_FAM = frozenset(_ES.FAMILIAS)
    SIN_ACENTO = frozenset(_ES.SIN_ACENTO)
except Exception:
    ESCENAS_FAM, SIN_ACENTO = frozenset(), frozenset()
ALTO = {'ListaRazonesK': 0.18, 'RutaK': 0.40, 'MisterioK': 0.15, 'AbanicoK': 0.36, 'RuedaK': 0.30, 'TituloNeonK': 0.16, 'ConceptoK': 0.54, 'MixtoK': 0.16,
        'RecorteK': 0.26, 'SeleccionK': 0.24, 'CalendarioK': 0.22, 'RedNeonK': 0.40}
ICONOS_ABANICO = {'ideas': 'light_bulb', 'lecciones': 'books', 'lessons': 'books', 'tips': 'light_bulb', 'consejos': 'light_bulb', 'trucos': 'sparkles',
                  'hacks': 'sparkles', 'habitos': 'check_mark_button', 'habits': 'check_mark_button', 'herramientas': 'hammer_and_wrench', 'tools': 'hammer_and_wrench'}
CIERRE = ('.', ',', '?', '!', ':', ';')
# EL MENÚ para la IA local (motor_texto, modo 'motions'): qué es cada motion, cuándo va y qué datos lleva. Lo lee el prompt tal cual.
MOTIONS = {
    'lista': ('se anuncian N razones, motivos, beneficios o señales, o se enumeran 2–5 cosas', '{"n": 3, "items": ["…"] (opcional, 1–3 palabras DICHAS)}'),
    'ruta': ('errores o fallos que se cometen, o los pasos de un camino', '{"n": 4, "titulo": "ERRORES", "subtitulo": "…" (opcional, palabras dichas)}'),
    'misterio': ('secretos, preguntas o cosas que aún no se revelan', '{"n": 3}'),
    'abanico': ('N lecciones, ideas, tips, consejos, trucos, reglas, hábitos o herramientas', '{"n": 5, "titulo": "LECCIONES", "subtitulo": "…", "icono": "light_bulb"}'),
    'rueda': ('convertir 1 cosa en N, o N formas / maneras / hooks', '{"n": 7, "titulo": "1 IDEA", "subtitulo": "7 HOOKS"}'),
    'titulo': ('un titular con número que resume de qué va el video', '{"numero": "8", "titulo": "…", "subtitulo": "…"}'),
    'concepto': ('UNA palabra clave con peso: éxito, fracaso, proceso, disciplina, equipo, dinero, tiempo, crecimiento', '{"palabra": "ÉXITO", "tendencia": "sube|baja|ninguna", "icono": "gem_stone"}'),
    'mixto': ('una frase contundente en dos partes («no es X, es Y», «no necesitas X, necesitas Y»)', '{"linea1": "…", "linea2": "…", "clave": "palabra"}'),
    'recorte': ('UN objeto o concepto concreto que se nombra (dinero, idea, cerebro, tiempo, trofeo, corona, megáfono, casa, cohete, cámara…): su icono '
                'recortado de revista. icono: ' + ', '.join(sorted(set(RECORTES.values()))),
                '{"icono": "light_bulb", "palabra": "IDEA" (opcional, la palabra DICHA)}'),
    'seleccion': ('la palabra clave de una frase que hay que recordar («la clave es la constancia», «recuerda: …»), resaltada como texto seleccionado',
                  '{"arriba": "la clave es" (opcional, dicho), "palabra": "constancia" (UNA palabra dicha), "abajo": "…" (opcional, dicho)}'),
    'calendario': ('se dice un número de días (un reto de 30 días, faltan 10 días)', '{"n": 30, "cuenta": "adelante|atras"}'),
    'red': ('se habla de redes sociales, seguidores o de consumir contenido frente a crearlo', '{"izq": "consumir" (opcional, dicho), "der": "crear" (opcional, dicho)}'),
}


def menu_para_ia(genero='general', solo=None):
    """El menú del director de motions: el kit + las escenas a pantalla completa (v5.5.3, edicion_pro_escenas) + las plantillas de la biblioteca
    (catalogo_ia) que le tocan a este tipo de video, por su id. `solo`: solo esas familias (los Temas 5/6 piden solo las escenas)."""
    menu = {k: list(v) for k, v in MOTIONS.items()}
    try:
        import edicion_pro_escenas as ES
        menu.update(ES.menu())
    except Exception:
        pass
    try:                                                   # v5.5.7: la IA solo conoce los motions que el usuario permitió (Efectos > Motions de la PRO)
        import motions_catalogo as MC
        menu = {k: v for k, v in menu.items() if k in MC.familias_permitidas(list(menu))}
    except Exception:
        MC = None
    if solo:
        return {k: v for k, v in menu.items() if k in solo}
    try:
        import catalogo_ia
        pl = catalogo_ia.menu_plantillas(genero)
        if MC is not None:
            pl = [(i, d) for i, d in pl or [] if MC.permitido('plantilla:' + str(i))]
        if pl:
            menu['plantilla'] = ['una plantilla de la biblioteca cuando se dice algo de su tema. Ids: ' + '; '.join(f'{i} ({d})' for i, d in pl),
                                 '{"id": "uno de los ids de la lista"}']
    except Exception:
        pass
    return menu


HISTORIAL = Path.home() / 'DaVinciSubtitles' / 'kit7_historial.json'
PALETAS_CACHE = Path.home() / 'DaVinciSubtitles' / 'kit7_paletas.json'


def _plegar(t):
    t = unicodedata.normalize('NFKD', str(t or '').lower())
    return ''.join(c for c in t if not unicodedata.combining(c)).strip(' .,;:!?¡¿"\'()[]«»…“”')


def tema_de(acento: str | None) -> str:
    """El tema de color del kit que va con el acento del video: morado/rosa → neon, rojo/naranja → rojo, azul/cian → azul, amarillo → oro."""
    try:
        h = str(acento or '').lstrip('#')
        r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        hue, _l, sat = colorsys.rgb_to_hls(r, g, b)
        if sat < 0.25:
            return 'neon'
        hue *= 360
        if hue < 25 or hue >= 335:
            return 'rojo'
        if hue < 65:
            return 'oro'
        if 170 <= hue < 250:
            return 'azul'
        return 'neon'
    except Exception:
        return 'neon'


def alto_de(comp, props):
    """El alto real según lo que lleva (una lista de 5 es más alta que una de 3; la ruta en gancho, más que la ola)."""
    n = int(props.get('n') or 3)
    if comp == 'ListaRazonesK':
        return round((n * 96 + (n - 1) * 18 + 40) / 1920.0, 3)
    if comp == 'RutaK':
        return 0.49 if (props.get('variante') or props.get('forma')) == 'gancho' else 0.38
    if comp == 'AbanicoK' and not (props.get('numero') or props.get('titulo')):
        return 0.22
    if comp == 'ConceptoK' and props.get('variante') in ('flotante', 'linea'):
        return 0.40
    if comp == 'RecorteK' and props.get('palabra'):
        return 0.32
    return ALTO.get(comp, 0.3)


def _numero(p: str):
    if p.isdigit():
        n = int(p)
        return n if 2 <= n <= 12 else None
    return NUM.get(p)


def _resto_de_frase(textos, desde, maximo=5):
    """Las palabras que siguen (hasta el final de la frase, `maximo`), para el subtítulo («para crecer de 0 a 250K»)."""
    out = []
    for j in range(desde, min(len(textos), desde + maximo)):
        w = str(textos[j]).strip()
        limpio = w.rstrip(''.join(CIERRE))
        if limpio:
            out.append(limpio)
        if w.endswith(CIERRE):
            break
    return ' '.join(out) if len(out) >= 2 else ''


def _antes_en_frase(textos, hasta, maximo=4):
    out = []
    for j in range(hasta - 1, max(-1, hasta - 1 - maximo), -1):
        w = str(textos[j]).strip()
        if w.endswith(CIERRE):
            break
        out.insert(0, w)
    return ' '.join(out)


def _momento(fam, i, t, props):
    comp = COMP[fam]
    return {'i': i, 't': float(t), 'id': f'kit_{fam}', 'fam': fam, 'comp': comp, 'props': props, 'dur': DUR[fam], 'alto': alto_de(comp, props)}


# ------------------------------------------------------------------------------------------------------------------------------- v5.5.3: Kit8
def recortes_disponibles():
    """Los iconos del RecorteK que hay (2_recursos/edicion_pro/recortes/indice.json, de herramientas_dev/generar_recortes.py)."""
    try:
        from sfx_rules import base_recursos
        ruta = Path(base_recursos()) / 'edicion_pro' / 'recortes' / 'indice.json'
    except Exception:
        ruta = Path(__file__).resolve().parents[1] / '2_recursos' / 'edicion_pro' / 'recortes' / 'indice.json'
    try:
        return set(json.loads(ruta.read_text(encoding='utf-8')))
    except Exception:
        return set()


def _dias(plegadas, i):
    """«30 días» → 30 (de 2 a 60), si no None."""
    p = plegadas[i]
    n = int(p) if p.isdigit() else NUM.get(p)
    if not n or not 2 <= n <= 60:
        return None
    return n if any(i + k < len(plegadas) and plegadas[i + k] in DIAS for k in (1, 2)) else None


def _sin_signos(w):
    return str(w or '').strip().strip(''.join(CIERRE) + '¡¿"\'«»“”()')


def _redes(logos):
    """Las redes que se nombran (en orden) y, hasta 4, las de siempre."""
    out = []
    for r in list(logos) + ['facebook', 'instagram', 'youtube', 'tiktok']:
        if r not in out:
            out.append(r)
    return ','.join(out[:4])


CREAR = {'crear', 'crea', 'creas', 'creo', 'creando', 'creador', 'creadores', 'create', 'creating', 'creator', 'creators'}


def _kit8(i, plegadas, textos, tiempos, idioma, cuenta, ultimo, recortes):
    """El momento de Kit8 que empieza en la palabra i (por reglas), o None."""
    p = plegadas[i]
    en = str(idioma).startswith('en')
    n = _dias(plegadas, i)
    if n and not cuenta.get('calendario'):
        atras = bool(set(plegadas[max(0, i - 4):i + 5]) & CUENTA_ATRAS)
        return _momento('calendario', i, tiempos[i], {'desde': n if atras else 1, 'hasta': 1 if atras else n, 'etiqueta': 'DAY' if en else 'DÍA', 'y': 38})
    if p in GATILLOS_SELECCION and not cuenta.get('seleccion') and not str(textos[i]).strip().endswith(('.', '!', '?')):   # «…lo importante.» no presenta nada
        for j in range(i + 1, min(len(plegadas), i + 6)):
            if j - 1 > i and str(textos[j - 1]).strip().endswith(CIERRE):
                break                                                         # la frase terminó
            q = plegadas[j]
            if len(q) >= 4 and q not in VACIAS and not q.isdigit():
                fin_frase = str(textos[j]).strip().endswith(CIERRE)            # «…la constancia.» → no hay línea de abajo
                ini = i                                                       # arriba: desde el gatillo (y hasta 2 palabras antes en su frase)
                while ini > max(0, i - 2) and not str(textos[ini - 1]).strip().endswith(CIERRE):
                    ini -= 1
                props = {'arriba': _corto(' '.join(textos[ini:j]), 30), 'palabra': _sin_signos(textos[j]),
                         'abajo': '' if fin_frase else _corto(_resto_de_frase(textos, j + 1, 4), 34), 'idioma': idioma, 'y': 46}
                return _momento('seleccion', i, tiempos[i], props)
        return None
    if (p in REDES or p.startswith('consum')) and not cuenta.get('red'):
        ventana = range(max(0, i - 8), min(len(plegadas), i + 9))
        izq = next((_sin_signos(textos[j]).upper() for j in ventana if plegadas[j].startswith('consum')), '')
        der = next((_sin_signos(textos[j]).upper() for j in ventana if plegadas[j] in CREAR), '')
        if p in REDES or (izq and der):                                      # «consumo de agua» no es de redes
            logos = [REDES_LOGO[plegadas[j]] for j in ventana if plegadas[j] in REDES_LOGO]
            return _momento('red', i, tiempos[i], {'izq': izq if der else '', 'der': der if izq else '', 'centro': 'YOU' if en else 'TÚ',
                                                   'redes': _redes(logos), 'y': 36})
    ic = RECORTES.get(p)
    if ic and ic in recortes and p not in CONCEPTOS and cuenta.get('recorte', 0) < CUANTOS_POR_VIDEO['recorte'] and tiempos[i] - ultimo.get('recorte', -99.0) >= 6.0:
        return _momento('recorte', i, tiempos[i], {'icono': ic, 'palabra': _sin_signos(textos[i]).upper()[:16], 'y': 40})
    return None


# ------------------------------------------------------------------------------------------------------------------------------- reglas
def momentos(plegadas, textos, tiempos, idioma='es', tema='neon', duracion=None, evitar=()):
    """[momento] por reglas (sin IA). Como mucho uno por tipo de cosa contada y unos pocos por video (no es un catálogo de efectos)."""
    plegadas = [str(p or '') for p in plegadas]
    out, usados_familia = [], set()
    cuenta, ultimo, recortes = {}, {}, recortes_disponibles()
    tope_total = max(2, int((duracion or (tiempos[-1] if tiempos else 0) or 0) // 12))
    for i, p in enumerate(plegadas):
        if len(out) >= tope_total:
            break
        if any(abs(tiempos[i] - x) <= 3.0 for x in evitar):                 # (ahí ya hay una escena a pantalla completa)
            continue
        m8 = _kit8(i, plegadas, textos, tiempos, idioma, cuenta, ultimo, recortes)
        if m8 and all(abs(m8['t'] - x['t']) > 2.5 for x in out):
            out.append(m8)
            cuenta[m8['fam']] = cuenta.get(m8['fam'], 0) + 1
            ultimo[m8['fam']] = m8['t']
            continue
        n = _numero(p)
        if n:
            for k in (1, 2):                                                  # «3 razones», «3 grandes razones», «five simple ways»
                if i + k >= len(plegadas):
                    break
                nom = plegadas[i + k]
                if nom not in NOMBRES:
                    continue
                fam, etiqueta = NOMBRES[nom]
                if fam in usados_familia or n > TOPE[fam]:
                    break
                usados_familia.add(fam)
                sub = _resto_de_frase(textos, i + k + 1)
                if fam == 'lista':
                    props = {'n': n, 'prefijo': etiqueta, 'y': 64}
                elif fam == 'ruta':
                    gancho = any(x in plegadas[max(0, i - 6):i + 8] for x in ('hook', 'hooks', 'gancho', 'ganchos', 'anzuelo'))
                    props = {'n': n, 'forma': 'gancho' if gancho else 'ola', 'numero': str(n), 'titulo': etiqueta, 'subtitulo': sub, 'y': 58}
                elif fam == 'misterio':
                    props = {'n': n, 'y': 60}
                elif fam == 'abanico':
                    icono = ICONOS_ABANICO.get(nom)
                    props = {'n': n, 'numero': str(n), 'titulo': etiqueta, 'subtitulo': sub, 'y': 62}
                    if icono and n > 3:
                        props['iconos'] = icono
                else:                                                         # rueda
                    antes = _antes_en_frase(textos, i)
                    props = {'n': n, 'titulo': antes.upper() if antes else f'{n} {etiqueta}', 'subtitulo': f'{n} {etiqueta}' if antes else '', 'y': 60}
                out.append(_momento(fam, i, tiempos[i], props))
                break
            continue
        if p in CONCEPTOS and 'concepto' not in usados_familia:
            palabra, graf, icono, tema_c = CONCEPTOS[p]
            usados_familia.add('concepto')
            props = {'palabra': palabra, 'grafica': graf, 'icono': icono, 'tema': tema_c, 'y': 50, 'sub': _resto_de_frase(textos, i + 1, 6)}
            out.append(_momento('concepto', i, tiempos[i], props))
    return out


# ------------------------------------------------------------------------------------------------------------------------------- IA local
def iconos_disponibles():
    """Los iconos animados que hay (Noto, 2_recursos/edicion_pro/lottie/indice.json): la IA solo puede elegir de estos."""
    try:
        from sfx_rules import base_recursos
        ruta = Path(base_recursos()) / 'edicion_pro' / 'lottie' / 'indice.json'
    except Exception:
        ruta = Path(__file__).resolve().parents[1] / '2_recursos' / 'edicion_pro' / 'lottie' / 'indice.json'
    try:
        d = json.loads(ruta.read_text(encoding='utf-8'))
        return [str(x) for x in (d if isinstance(d, list) else d.keys())]
    except Exception:
        return []


def _dicho(texto, frase_pleg):
    """¿Todas las palabras de `texto` se dicen en la frase? (nada inventado por la IA)."""
    ws = [_plegar(w) for w in str(texto or '').split() if _plegar(w)]
    return bool(ws) and all(w in frase_pleg or w.isdigit() for w in ws)


def _corto(s, maximo=26):
    s = ' '.join(str(s or '').split())
    return s if 0 < len(s) <= maximo else ''


def _plantilla_de_ia(pr, frases, plegadas, tiempos, genero):
    """Una plantilla de la biblioteca propuesta por la IA ({'motion': 'plantilla', 'datos': {'id'}}): el id existe, es de una rama de este tipo
    de video y el ancla se dice en la frase. → momento con las props de la plantilla, o None."""
    try:
        import catalogo_ia
        import edicion_pro_catalogo as PC
        b = int(pr.get('b'))
        pid = str((pr.get('datos') or {}).get('id') or '')
        pl = next((p for p in PC.PLANTILLAS if p['id'] == pid), None)
        if pl is None or pl['rama'] not in catalogo_ia.RAMAS_DE_GENERO.get(genero or 'general', catalogo_ia.RAMAS_DE_GENERO['general']):
            return None
        idx = list(frases[b])
        ancla = _plegar(pr.get('ancla') or '')
        i = next((j for j in idx if ancla and plegadas[j] == ancla), None)
        if i is None:                                                         # sin ancla (o mal): la palabra de la frase que es del tema de la plantilla
            pr_ = pl['props']
            claves = {_plegar(w) for f in pl['frases'] for w in f.split()} | {_plegar(w) for w in str(pr_.get('titulo') or pr_.get('texto') or '').split()}
            claves = {w for w in claves if len(w) > 3}
            i = next((j for j in idx if plegadas[j] in claves), None)
        if i is None:
            return None
        return {'i': i, 't': float(tiempos[i]), 'id': pl['id'], 'fam': 'plantilla', 'comp': pl['comp'], 'props': dict(pl['props']), 'dur': pl['dur'],
                'alto': pl.get('alto') or PC.ALTO.get(pl['comp'], 0.25)}
    except Exception:
        return None


def desde_ia(propuestas, frases, plegadas, textos, tiempos, duracion=None, iconos=None, idioma='es', genero='general', denso=False):
    """Lo que propuso la IA ({'b', 'motion', 'datos', 'ancla'}), VALIDADO: la frase existe, el ancla se dice en ella, los textos se dicen (o son la
    etiqueta del tipo), los números caben, los iconos existen. Lo que no pasa, se descarta (sin inventar nada).
    v5.5.8 `denso` («Motions completo», un video de SOLO motions): sin los topes de «pocos por video»; cada tipo, como mucho uno de cada ~4 frases."""
    iconos = set(iconos if iconos is not None else iconos_disponibles())
    out, usados = [], set()
    tope_total = max(2, int((duracion or (tiempos[-1] if tiempos else 0) or 0) // 12))
    por_tipo = max(2, (len(frases) + 5) // 8) if denso else None
    if denso:
        tope_total = len(frases) + 1
    for pr in propuestas or []:
        try:
            b, fam, datos = int(pr.get('b')), str(pr.get('motion') or ''), pr.get('datos') if isinstance(pr.get('datos'), dict) else {}
        except Exception:
            continue
        if fam == 'plantilla' and len(out) < tope_total and 0 <= b < len(frases):
            m = _plantilla_de_ia(pr, frases, plegadas, tiempos, genero)
            if m and m['id'] not in {x['id'] for x in out}:
                out.append(m)
            continue
        if fam in ESCENAS_FAM and 0 <= b < len(frases):                    # v5.5.3: escena a pantalla completa (edicion_pro_escenas)
            if (not denso and sum(1 for x in out if x.get('pantalla')) >= max(1, int((duracion or 30) // 10))) \
                    or sum(1 for x in out if x['fam'] == fam) >= (por_tipo if denso else _ES.CUANTOS.get(fam, 1)):
                continue
            import edicion_pro_escenas as ES
            m = ES.desde_ia_uno(pr, frases, plegadas, textos, tiempos, idioma)
            if m and all(abs(m['t'] - x['t']) > 2.5 for x in out):
                out.append(m)
            continue
        if fam not in COMP or not (0 <= b < len(frases)) or len(out) >= tope_total:
            continue
        if sum(1 for x in out if x['fam'] == fam) >= (por_tipo if denso else CUANTOS_POR_VIDEO.get(fam, 1)):
            continue
        idx = list(frases[b])
        sig = list(frases[b + 1]) if b + 1 < len(frases) else []
        pleg = set(plegadas[j] for j in idx + sig)
        ancla = _plegar(pr.get('ancla') or '')
        i = next((j for j in idx if ancla and plegadas[j] == ancla), None)
        if i is None and idx:                                                 # sin ancla: el número que se cuenta, la palabra-concepto o la 2.ª parte
            if fam in TOPE:
                i = next((j for j in idx if _numero(plegadas[j])), None)
            elif fam == 'concepto':
                i = next((j for j in idx if plegadas[j] == _plegar(datos.get('palabra'))), None)
            elif fam == 'mixto':
                primera = _plegar(str(datos.get('linea2') or '').split()[0] if str(datos.get('linea2') or '').split() else '')
                i = next((j for j in idx if plegadas[j] == primera and j > idx[0]), None)
            elif fam == 'recorte':
                i = next((j for j in idx if RECORTES.get(plegadas[j]) == str(datos.get('icono') or '')), None)
            elif fam == 'seleccion':
                i = next((j for j in idx if plegadas[j] == _plegar(datos.get('palabra'))), None)
            elif fam == 'calendario':
                i = next((j for j in idx if _dias(plegadas, j)), None)
            i = idx[0] if i is None else i
        if i is None:
            continue
        n = datos.get('n')
        try:
            n = int(n) if n is not None else None
        except Exception:
            n = None
        props = None
        if fam in ('lista', 'ruta', 'misterio', 'abanico', 'rueda'):
            if not n or not (2 <= n <= TOPE[fam]) or str(n) not in ' '.join(textos[j] for j in idx + sig) and not any(NUM.get(plegadas[j]) == n for j in idx + sig):
                continue                                                      # el número tiene que DECIRSE
            # el título: lo que propuso si se DICE; si no, la palabra contada que sí se dijo («5 trucos» → TRUCOS)
            etiqueta = next((NOMBRES[plegadas[j]][1] for j in idx + sig if plegadas[j] in NOMBRES), '')
            de_fam = next((NOMBRES[plegadas[j]][1] for j in idx + sig if NOMBRES.get(plegadas[j], ('',))[0] == fam), '')
            titulo = _corto(datos.get('titulo'), 22).upper() if _dicho(datos.get('titulo'), pleg) else etiqueta
            sub = _corto(datos.get('subtitulo'), 34) if _dicho(datos.get('subtitulo'), pleg) else ''
            if _plegar(sub) == _plegar(titulo):
                sub = ''
            items = [_corto(x, 22) for x in (datos.get('items') or []) if isinstance(x, str) and _dicho(x, pleg)]
            if not de_fam and not (fam == 'lista' and len(items) == n) and not (fam != 'lista' and _dicho(datos.get('titulo'), pleg)):
                continue                                                      # v5.5.4: «tres jóvenes» no son «3 razones»: se nombra lo contado o se dicen las cosas
            if fam == 'lista':
                props = {'n': n, 'items': '|'.join(x.upper() for x in items if x)} if len(items) == n else {'n': n}
                props.update(prefijo=de_fam or ('REASON' if str(idioma).startswith('en') else 'RAZÓN'), y=64)
            elif fam == 'ruta':
                props = {'n': n, 'numero': str(n), 'titulo': titulo or 'ERRORES', 'subtitulo': sub, 'y': 58}
            elif fam == 'misterio':
                props = {'n': n, 'y': 60}
            elif fam == 'abanico':
                ic = str(datos.get('icono') or '')
                props = {'n': n, 'numero': str(n), 'titulo': titulo, 'subtitulo': sub, 'y': 62}
                if ic in iconos and n > 3:
                    props['iconos'] = ic
            else:
                props = {'n': n, 'titulo': titulo or f'{n}', 'subtitulo': _corto(datos.get('subtitulo'), 22).upper() if _dicho(datos.get('subtitulo'), pleg) else '', 'y': 60}
        elif fam == 'titulo':
            num = str(datos.get('numero') or '').strip()
            tit = _corto(datos.get('titulo'), 30)
            if not tit or not _dicho(tit, pleg) or (num and not _dicho(num, pleg)):
                continue
            props = {'numero': num, 'titulo': tit.upper(), 'subtitulo': _corto(datos.get('subtitulo'), 40) if _dicho(datos.get('subtitulo'), pleg) else '', 'y': 26}
        elif fam == 'concepto':
            palabra = _corto(datos.get('palabra'), 16)
            if not palabra or not _dicho(palabra, pleg):
                continue
            tend = str(datos.get('tendencia') or 'sube')
            ic = str(datos.get('icono') or '')
            props = {'palabra': palabra.upper(), 'grafica': tend if tend in ('sube', 'baja', 'ninguna') else 'sube',
                     'icono': f'emoji:{ic}' if ic in iconos else 'diamante', 'y': 50}
        elif fam == 'mixto':
            l1, l2, clave = _corto(datos.get('linea1'), 34), _corto(datos.get('linea2'), 40), _plegar(datos.get('clave'))
            if not (l1 and l2 and _dicho(l1, pleg) and _dicho(l2, pleg)) or clave not in [_plegar(w) for w in l2.split()]:
                continue
            props = {'linea1': l1, 'linea2': l2, 'clave': clave, 'y': 46}
        elif fam == 'recorte':                                                # v5.5.3 (Kit8): el icono tiene que existir; la palabra, decirse
            ic = str(datos.get('icono') or '')
            if ic not in recortes_disponibles():
                continue
            pal = _corto(_sin_signos(datos.get('palabra')), 16)
            props = {'icono': ic, 'palabra': pal.upper() if pal and _dicho(pal, pleg) else '', 'y': 40}
        elif fam == 'seleccion':
            pal = _sin_signos(datos.get('palabra'))
            if not pal or len(pal.split()) != 1 or len(pal) > 16 or not _dicho(pal, pleg):
                continue
            props = {'arriba': _corto(datos.get('arriba'), 30) if _dicho(datos.get('arriba'), pleg) else '', 'palabra': pal,
                     'abajo': _corto(datos.get('abajo'), 34) if _dicho(datos.get('abajo'), pleg) else '', 'idioma': idioma, 'y': 46}
            for k_ in ('arriba', 'abajo'):                                # v5.5.3: sin repetir la palabra grande arriba o abajo («Xela / porque es Xela»)
                if _plegar(pal) in [_plegar(w) for w in str(props[k_]).split()]:
                    props[k_] = ''
        elif fam == 'calendario':
            dicho = n and (str(n) in ' '.join(textos[j] for j in idx + sig) or any(NUM.get(plegadas[j]) == n for j in idx + sig))
            if not n or not 2 <= n <= 60 or not dicho:
                continue
            atras = _plegar(datos.get('cuenta')) in ('atras', 'back', 'down', 'countdown')
            props = {'desde': n if atras else 1, 'hasta': 1 if atras else n, 'etiqueta': 'DAY' if str(idioma).startswith('en') else 'DÍA', 'y': 38}
        elif fam == 'red':
            izq, der = _corto(datos.get('izq'), 16), _corto(datos.get('der'), 16)
            izq = izq.upper() if izq and _dicho(izq, pleg) else ''
            der = der.upper() if der and _dicho(der, pleg) else ''
            logos = [REDES_LOGO[plegadas[j]] for j in idx + sig if plegadas[j] in REDES_LOGO]
            props = {'izq': izq if der else '', 'der': der if izq else '', 'centro': 'YOU' if str(idioma).startswith('en') else 'TÚ', 'redes': _redes(logos), 'y': 36}
        if props is None:
            continue
        usados.add(fam)
        out.append(_momento(fam, i, tiempos[i], props))
    return out


# ------------------------------------------------------------------------------------------------------------------------------- variantes y colores
def _leer(ruta, defecto):
    try:
        return json.loads(ruta.read_text(encoding='utf-8'))
    except Exception:
        return defecto


def _escribir(ruta, datos):
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass


def elegir_variante(comp, semilla, usadas_aqui, recientes, permitidas=None):
    """La variante menos usada en los últimos videos (y nunca la misma dos veces en este); a igualdad, al azar con la semilla del video."""
    opciones = [v for v in (permitidas or VARIANTES.get(comp) or ['']) if (comp, v) not in usadas_aqui] or list(permitidas or VARIANTES.get(comp) or [''])
    rng = random.Random(f'{semilla}|{comp}')
    cuenta = {v: sum(1 for c, x in recientes if c == comp and x == v) for v in opciones}
    rng.shuffle(opciones)
    return min(opciones, key=lambda v: cuenta[v])


def paleta_de_video(video):
    """(acento, acento2): el color dominante con fuerza del video (y otro distinto, o uno más claro), para que el kit vista los colores del video.
    (None, None) si el video es gris o no se pudo leer. Caché por archivo."""
    try:
        p = Path(str(video))
        clave = hashlib.md5(f'{p.resolve()}|{p.stat().st_size}|{p.stat().st_mtime_ns}'.encode('utf-8')).hexdigest()[:16]
    except Exception:
        return None, None
    cache = _leer(PALETAS_CACHE, {})
    if clave in cache:
        a, b = cache[clave]
        return a, b
    acento = acento2 = None
    try:
        import av
        import numpy as np
        muestras = []
        with av.open(str(p)) as c:
            s = c.streams.video[0]
            dur = float(c.duration or 0) / 1e6 or 10.0
            for k in range(8):
                try:
                    c.seek(int((0.05 + 0.9 * k / 7) * dur * 1e6), any_frame=False, backward=True)
                    fr = next(c.decode(s))
                except Exception:
                    continue
                muestras.append(np.asarray(fr.to_image().resize((48, 85))).reshape(-1, 3) / 255.0)
        if muestras:
            px = np.concatenate(muestras)
            mx, mn = px.max(1), px.min(1)
            sat = (mx - mn) / np.maximum(mx, 1e-6)
            vivos = px[(sat > 0.35) & (mx > 0.3)]
            if len(vivos) > 0.01 * len(px):
                hues = np.array([colorsys.rgb_to_hsv(*q)[0] for q in vivos[:: max(1, len(vivos) // 3000)]])
                hist, bordes = np.histogram(hues, bins=24, range=(0, 1))
                orden = np.argsort(hist)[::-1]

                def color(binario):
                    hue = (bordes[binario] + bordes[binario + 1]) / 2
                    r, g, b = colorsys.hls_to_rgb(hue, 0.58, 0.85)            # el mismo tono, vivo y legible sobre el video
                    return '#%02X%02X%02X' % (int(r * 255), int(g * 255), int(b * 255))
                acento = color(orden[0])
                otro = next((o for o in orden[1:6] if hist[o] > 0.15 * hist[orden[0]] and min(abs(o - orden[0]), 24 - abs(o - orden[0])) >= 3), None)
                acento2 = color(otro) if otro is not None else None
    except Exception:
        acento = acento2 = None
    cache[clave] = [acento, acento2]
    _escribir(PALETAS_CACHE, cache)
    return acento, acento2


TEMA_DE_TONO = {'elegante': 'oro', 'energico': 'rojo', 'divertido': 'neon', 'calmado': 'azul', 'serio': 'azul', 'inspirador': 'neon', 'tecnico': 'azul'}


def vestir(lista, video='', tema_estilo='neon', tono=None):
    """Le pone a cada momento su VARIANTE (la menos repetida) y sus COLORES (los del video; si el video es gris, los del TONO que entendió la IA;
    el editorial se respeta) y lo apunta en el historial."""
    hist = _leer(HISTORIAL, {}).get('recientes') or []
    recientes = [tuple(x) for x in hist if isinstance(x, list) and len(x) == 2]
    semilla = hashlib.md5(str(video).encode('utf-8')).hexdigest()[:8]
    acento, acento2 = (None, None) if tema_estilo == 'editorial' else paleta_de_video(video) if video else (None, None)
    if not acento and tono in TEMA_DE_TONO and tema_estilo != 'editorial':
        tema_estilo = TEMA_DE_TONO[tono]
    usadas = set()
    for m in lista:
        comp, pr = m['comp'], m['props']
        if comp not in VARIANTES:                                             # (una plantilla de la biblioteca: va con su propio estilo)
            continue
        permitidas = None
        if comp == 'RutaK':                                                   # el gancho solo si se habla de hooks
            permitidas = ['gancho'] if pr.get('forma') == 'gancho' else ['ola', 'subida', 'escalera']
        v = elegir_variante(comp, semilla, usadas, recientes, permitidas)
        usadas.add((comp, v))
        pr['variante'] = v
        if tema_estilo == 'editorial':
            pr['tema'] = 'editorial' if comp in ('ListaRazonesK', 'AbanicoK', 'RutaK', 'TituloNeonK', 'MixtoK') else 'neon'
        else:
            pr.setdefault('tema', tema_estilo or 'neon')
            if acento and comp != 'ConceptoK' and comp not in SIN_ACENTO:     # (el concepto conserva su rojo/azul; el hilo rojo, el calendario… los suyos)
                pr['acento'] = acento
                if acento2:
                    pr['acento2'] = acento2
        m['alto'] = alto_de(comp, pr)
    _escribir(HISTORIAL, {'recientes': ([list(x) for x in recientes] + [list(x) for x in usadas])[-60:]})
    return lista


def planificar(textos, plegadas, tiempos, frases, idioma='es', video='', duracion=None, tema_estilo='neon', ia=True, estado=None, genero='general',
               perfil=None, solo_escenas=False):
    """Los motions del kit para este video: primero la IA local (si está y propone algo válido, del kit o de la biblioteca de plantillas de este
    tipo de video), si no las reglas; luego variante y colores. `perfil` (ia_texto.perfil: categoría, tono, iconos) orienta a la IA, pone los
    iconos del tema donde falten y elige los colores por el tono si el video es gris. v5.5.3: también las ESCENAS a pantalla completa (marcadas
    'pantalla'); `solo_escenas` (Temas 5/6) pide solo esas."""
    lista = []
    perfil = perfil or {}
    if ia:
        try:
            import ia_texto
            bloques = [' '.join(textos[j] for j in f) for f in frases]
            contexto = ' · '.join(x for x in (perfil.get('categoria'), perfil.get('subtema'), perfil.get('tono') and 'tono ' + perfil['tono'],
                                              perfil.get('publico') and 'para ' + perfil['publico']) if x)
            propuestas = ia_texto.motions(bloques, idioma, estado=estado, genero=genero, contexto=contexto, solo=ESCENAS_FAM if solo_escenas else None)
            lista = desde_ia(propuestas, frases, plegadas, textos, tiempos, duracion, idioma=idioma, genero=genero)
        except Exception:
            lista = []
    # las reglas completan lo que la IA no cubrió (otro tipo de motion y lejos de los suyos, ±3 s); sin IA, son todo
    cuantos = {}
    for m in lista:
        cuantos[m['fam']] = cuantos.get(m['fam'], 0) + 1
    # v5.5.3: las escenas por reglas, las familias MENOS usadas en los últimos videos primero (variedad entre videos); como mucho una cada ~10 s
    try:
        import edicion_pro_escenas as ES
        usos = {}
        for c, _v in [tuple(x) for x in (_leer(HISTORIAL, {}).get('recientes') or []) if isinstance(x, list) and len(x) == 2]:
            usos[c] = usos.get(c, 0) + 1
        tope = max(1, int((duracion or (tiempos[-1] if tiempos else 0) or 0) // 10))
        cands = sorted(ES.reglas(textos, plegadas, tiempos, idioma, ya={m['fam'] for m in lista}), key=lambda m: (usos.get(m['comp'], 0) - ES.PRIORIDAD.get(m['fam'], 1.0), m['t']))
        n_fotos = sum(1 for x in lista if x['fam'] == 'foto')
        for m in cands:
            es_foto = m['fam'] == 'foto'                                  # v5.5.4: las fotos de internet tienen su propio hueco (hasta ES.CUANTOS):
            if es_foto and n_fotos >= ES.CUANTOS.get('foto', 3):          #         antes la IA llenaba el cupo y no entraba ninguna
                continue
            if not es_foto and sum(1 for x in lista if x.get('pantalla')) >= tope:
                continue
            if all(abs(m['t'] - x['t']) > 3.0 for x in lista):
                lista.append(m)
                n_fotos += 1 if es_foto else 0
    except Exception:
        pass
    for m in ([] if solo_escenas else momentos(plegadas, textos, tiempos, idioma, tema_estilo, duracion, evitar=[x['t'] for x in lista])):
        if cuantos.get(m['fam'], 0) < CUANTOS_POR_VIDEO.get(m['fam'], 1) and all(abs(m['t'] - x['t']) > 3.0 for x in lista):
            lista.append(m)
            cuantos[m['fam']] = cuantos.get(m['fam'], 0) + 1
    try:                                                   # v5.5.7: solo los motions que el usuario permitió (las reglas tampoco eligen otros)
        import motions_catalogo as MC
        lista = [m for m in lista if MC.permitido(('plantilla:' + str(m.get('id'))) if m.get('fam') == 'plantilla'
                                                  else ('kit:' + m['fam']) if m.get('fam') in COMP else ('escena:' + m['fam']) if m.get('pantalla') else None)]
    except Exception:
        pass
    lista.sort(key=lambda m: m['t'])
    iconos_tema = [x for x in perfil.get('iconos') or [] if x]
    for m in lista:                                                       # los iconos del TEMA del video donde la pieza los admite y no los trae
        if m['comp'] == 'AbanicoK' and not m['props'].get('iconos') and iconos_tema and int(m['props'].get('n') or 0) > 3:
            m['props']['iconos'] = '|'.join(iconos_tema)
    lista = vestir(lista, video, tema_estilo, perfil.get('tono'))
    try:
        import edicion_pro_escenas as ES
        ES.completar(lista, video, duracion, perfil)                # polaroid, tablero y móvil: fotos de internet del tema (o del video)
    except Exception:
        pass
    return lista
