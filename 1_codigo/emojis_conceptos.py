# CineCaptions · By Cinema Productions
# 1_codigo/emojis_conceptos.py — el emoji que de verdad va con una palabra (v5.5.7)
"""
El usuario vio emojis que no iban con lo que se decía: 💰 en «la entrada es 100 % gratuita», 💬 en «un torneo con premios», 💼 en «historias», 💡 en
«emprendimientos de comida», ➡️ en «vives». Dos causas:
  1. el emoji que la IA ponía en una palabra se MOVÍA a la palabra destacada más cercana de la frase (el 💼 de «empresa» acababa en «historias»);
  2. las claves del catálogo (CLDR) dan cosas raras: «festival» → pastel de luna, «comida» → taco, «haciendo» → cuernos con la mano.
Aquí está el diccionario curado (español, inglés y portugués) que manda por encima de la IA y del catálogo, y la regla de coherencia: un emoji de la
IA solo se acepta si va con SU palabra (el diccionario o el catálogo lo confirman); si no, no hay emoji (mejor ninguno que uno equivocado).

    concepto(palabra) -> id del emoji o None
    coherente(palabra, eid, sugeridos) -> bool
"""
import re
import unicodedata

# id del emoji -> palabras (plegadas). Una palabra larga (≥ 5 letras) vale también con su final («premios», «festivales», «gratuitas»).
_MAPA = {
    'free_button': 'gratis gratuita gratuito gratuitas gratuitos free gratuitamente',
    'trophy': 'premio premios trofeo trofeos torneo torneos campeon campeona campeones ganador ganadora ganadores ganar gane award awards prize tournament winner premiacao',
    'fork_and_knife_with_plate': 'comida comidas comer almuerzo cena desayuno restaurante restaurantes food lunch dinner breakfast restaurant comidinha',
    'party_popper': 'fiesta fiestas festival festivales celebrar celebracion celebramos party festa celebration',
    'musical_notes': 'musica musical cancion canciones concierto conciertos banda bandas ritmo music song songs concert band musica',
    'headphone': 'dj djs audifonos headphones playlist',
    'microphone': 'cantar cantante karaoke singer',
    'briefcase': 'empresa empresas negocio negocios emprendimiento emprendimientos emprendedor emprendedores trabajo oficina business company startup trabalho empresa',
    'open_book': 'historia historias libro libros leer cuento story stories book books',
    'graduation_cap': 'beca becas maestria universidad graduacion estudiar estudios estudiantes curso cursos escuela scholarship university graduation students school bolsa faculdade',
    'globe_showing_europe_africa': 'europa europe mundo world internacional international',
    'airplane': 'viaje viajes viajar vuelo avion travel trip flight viagem',
    'spiral_calendar': 'fecha fechas calendario sabado domingo lunes martes miercoles jueves viernes enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre date calendar saturday sunday',
    'alarm_clock': 'hora horas manana temprano minutos time clock',
    'video_game': 'gamer gamers videojuego videojuegos juego juegos gaming game games esports',
    'bookmark': 'guarda guardalo guardar guardar save',
    'outbox_tray': 'envia enviale envialo enviaselo enviar comparte compartelo compartir share send',
    'money_bag': 'dinero plata precio precios pagar pago ganancias money price pay dinheiro',
    'mobile_phone': 'celular telefono movil influencer influencers redes instagram tiktok phone',
    'busts_in_silhouette': 'jovenes gente personas publico comunidad people community youth',
    'people_hugging': 'amigos amigas amistad friends friendship amigos',
    'handshake': 'networking alianza acuerdo socios partners deal',
    'speech_balloon': 'charla charlas conferencia conferencias hablar talk talks',
    'round_pushpin': 'lugar ubicacion direccion centro location place address local',
    'wrapped_gift': 'sorpresa sorpresas regalo regalos surprise gift',
    'house': 'casa hogar home house',
    'red_heart': 'amor love corazon heart',
    'light_bulb': 'idea ideas tip tips consejo consejos truco trucos',
    'rocket': 'lanzamiento crecer crecimiento launch growth',
    'camera': 'foto fotos fotografia photo photos',
    'dog': 'perro perros perrito perritos dog dogs puppy',
    'warning': 'cuidado peligro atencion warning careful danger',
    'hundred_points': 'cien',
}
_PALABRA = {}
for _eid, _ps in _MAPA.items():
    for _p in _ps.split():
        _PALABRA.setdefault(_p, _eid)
_LARGAS = sorted((p for p in _PALABRA if len(p) >= 5), key=len, reverse=True)


def plegar(texto):
    t = unicodedata.normalize('NFD', str(texto or '').lower())
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in t if unicodedata.category(c) != 'Mn'))


def concepto(palabra):
    """El emoji curado para esa palabra (exacta, o una palabra larga del diccionario con su final: «premiados», «festivales»), o None."""
    w = plegar(palabra)
    if len(w) < 3:
        return None
    if w in _PALABRA:
        return _PALABRA[w]
    for p in _LARGAS:
        if w.startswith(p) and len(w) - len(p) <= 3:
            return _PALABRA[p]
    return None


def coherente(palabra, eid, sugeridos=()):
    """¿Va ese emoji con esa palabra? Sí si el diccionario o las claves del catálogo lo confirman."""
    c = concepto(palabra)
    if c is not None:
        return eid == c
    return eid in (sugeridos or ())
