# CineCaptions · By Cinema Productions
# 1_codigo/emojis_sfx.py — el sonido de cada emoji (fuego → fuego, beso → beso…): qué familia le toca, el que el usuario eligió y los eventos que se mandan a Resolve.
"""
Cada emoji del catálogo (1 391) pertenece a una «familia» de sonido; los audios de las familias viajan dentro del programa
(2_recursos/sfx_emoji/<familia>.wav, sintetizados por 2_recursos/generador_sfx_emoji: sin derechos de nadie).

  * familia_de(id)    : la familia de un emoji. Primero reglas por palabra del nombre (fire → fuego, kiss → beso, money → dinero…),
                        después el grupo (caras, comida, símbolos…) con variantes para que no suene todo igual.
  * ruta_de(familia)  : el audio. Si el usuario deja un .wav/.mp3 con el MISMO nombre en ~/DaVinciSubtitles/sfx_emoji/ manda ese
                        (así puede cambiar cualquier sonido por una grabación real sin tocar el programa).
  * asignados() / asignar() / sonido_de() : el sonido que el usuario eligió emoji por emoji (pestaña «Emojis» del SFX Lab, pref sfx_emoji_sonidos):
                        una familia, un archivo suyo, o '' = ese emoji no suena. Lo que no cambió sigue con el de su familia.
  * agregar_eventos() : a cada bloque con emoji le suma un evento de sonido en el instante en que sale la línea que lo lleva;
                        los scripts de Resolve ya saben colocar 'sfx_eventos' (varios sonidos pueden pisarse: pistas SFX, SFX 2…).

Se enciende con el interruptor «Sonidos de emojis» (SFX Lab, pref sfx_emojis, por defecto sí) y solo cuando los efectos están activos.
"""
import json
import re
import zlib
from pathlib import Path

import emojis
import sfx_rules

CATEGORIA = 'Emojis'
SEPARACION_MIN_S = 0.30         # dos emojis casi a la vez: suena uno solo (si no, se pisan y ensucian)
EXTENSIONES = ('.wav', '.mp3', '.m4a', '.flac', '.ogg')


def carpeta_programa():
    return sfx_rules.base_recursos() / 'sfx_emoji'


def carpeta_usuario():
    return sfx_rules.CARPETA_USUARIO / 'sfx_emoji'


# Reglas por palabras del NOMBRE (el id del catálogo, en inglés). La primera que casa gana: lo específico va antes que lo general.
_R = [
    # --- vehículos de emergencia y otros ruidos (antes que «fire»/«car»)
    (r'exploding_head|mind_blow', 'mente_explota'),
    (r'cloud_with_lightning|thunder|storm', 'trueno'),
    (r'fire_engine|police_car|ambulance|oncoming_police|rotating_light|police_cars_light', 'sirena'),
    (r'fire_extinguisher|shower|bathtub|toilet|bucket|water_pistol|sweat_droplets|splash', 'salpicadura'),
    (r'firecracker|bomb|collision|dynamite|volcano|explod|boom', 'explosion'),
    (r'fireworks|sparkler', 'fuegos_artificiales'),
    (r'fire$|^fire_|flame|candle|campfire|hot_face|cooking|frying_pan|pot_of_food|shallow_pan|stew|hot_pepper|hot_springs|lantern_fire|mantelpiece', 'fuego'),
    # --- besos, corazones, amor
    (r'kiss|lips$|^mouth$|biting_lip|face_blowing', 'beso'),
    (r'broken_heart', 'triste'),
    (r'heart_suit|heart_decoration', 'pop_b'),
    (r'heart|(^|_)love($|_)|love_letter|love_hotel|love_you|cupid|couple|family|hugging', 'corazon'),
    # --- dinero y negocios
    (r'chart_increasing|chart_with_upwards|rising', 'acierto'),
    (r'chart_decreasing|chart_with_downwards', 'pulgar_abajo'),
    (r'money|dollar|coin|banknote|credit_card|gem_stone|^bank$|shopping|cash|(^|_)euro($|_)|(^|_)yen($|_)|(^|_)pound($|_)|slot_machine|receipt|label$|diamond_with_a', 'dinero'),
    # --- caras: risa, tristeza, susto, enojo…
    (r'face_with_symbols_on_mouth|zipper_mouth|middle_finger|bleep|face_with_hand_over_mouth', 'censura'),
    (r'tears_of_joy|rolling_on_the_floor|grinning_squinting|laughing|beaming|grinning_cat|cat_with_tears_of_joy|grinning_face', 'risa'),
    (r'star_struck|smiling_cat_with_heart_eyes', 'estrella'),
    (r'heart_eyes|smiling_face_with_hearts', 'corazon'),
    (r'loudly_crying|crying|pleading|disappointed|pensive|sad_|frowning|weary|tired_face|confounded|persevering|downcast|anxious|holding_back_tears|with_tear|melting|sob', 'triste'),
    (r'screaming|astonished|fearful|hushed|face_with_open_mouth|flushed|anguished|peeking_eye|open_eyes_and_hand|distorted|shaking_face|scream', 'susto'),
    (r'angry|pouting|steam_from_nose|with_horns|anger|imp$', 'enojo'),
    (r'thinking|monocle|raised_eyebrow|nerd|shushing', 'pensando'),
    (r'sleeping|sleepy|zzz|yawning|^bed$|bags_under_eyes', 'dormir'),
    (r'ghost|jack_o_lantern|(^|_)bat$|vampire', 'fantasma'),
    (r'skull|crossbones|zombie', 'calavera'),
    (r'alien|space_invader|flying_saucer', 'alien'),
    (r'robot|video_game|joystick|mechanical', 'robot'),
    (r'pile_of_poo|clown|goblin|ogre|zany|upside_down|monkey|tongue|woozy|vomiting|nauseated|joker', 'boing'),
    (r'cold_face|(^|_)ice($|_)|snow|freez|icicle|(^|_)cold($|_)', 'hielo'),
    (r'sneezing|sneeze', 'swish'),
    (r'drooling|savoring|slurp', 'sorbo'),
    (r'partying_face|party_popper|confetti|balloon|pinata|tada|mirror_ball|dancing|bunny_ears', 'fiesta'),
    (r'unamused|rolling_eyes|neutral|expressionless|without_mouth|dotted_line|smirking|lying_face|^eyes$|^eye$|eyes_', 'ojos'),
    (r'winking|sunglasses|cowboy|disguised|salut|relieved', 'ding'),
    # --- manos
    (r'thumbs_up|thumbs_up_light', 'pulgar_arriba'),
    (r'thumbs_down', 'pulgar_abajo'),
    (r'clapping|raising_hands|open_hands|palms_up|person_raising', 'aplauso'),
    (r'folded_hands|praying|lotus|bowing|angel', 'rezo'),
    (r'ok_hand|pinched|pinching|victory|crossed_fingers|love_you|sign_of_the_horns|vulcan', 'ok'),
    (r'flexed_biceps|muscle|lifting', 'musculo'),
    (r'waving_hand|raised_hand|raised_back|fingers_splayed|hand_with|palm_down|leftwards|rightwards|hand_pointing|pointing|index_', 'saludo'),
    (r'fist|punch|boxing|martial|oncoming_fist', 'golpe'),
    (r'writing_hand|memo|pencil|(^|_)pen$|fountain_pen|notebook|ledger|bookmark|page|scroll|newspaper|book|books|clipboard|calendar|spiral|folder|card_index|file', 'libro'),
    (r'call_me|telephone|^mobile_phone_with|pager|fax|^phone', 'telefono'),
    (r'mobile_phone|smartphone|incoming_envelope|envelope|e_mail|email|mailbox|inbox|outbox|ballot_box', 'notificacion'),
    (r'speech|thought_balloon|left_speech|anger_bubble|speaking_head', 'mensaje'),
    (r'selfie|camera|video_camera|movie_camera|film_projector|film_frames|photo|movie', 'camara'),
    (r'clapper', 'claqueta'),
    # --- objetos y sonidos concretos
    (r'alarm_clock|timer_clock', 'alarma'),
    (r'hourglass|stopwatch|watch|clock|o_clock|thirty|timer', 'tictac'),
    (r'light_bulb|bulb|flashlight|lantern|diya|idea', 'idea'),
    (r'bellhop|^bell$|bell_with|bell_slash|^bell_', 'campana'),
    (r'key$|^key_|old_key|chains|^link$|locked_with|keycap_key', 'llave'),
    (r'(^|_)lock($|_)|locked|padlock|(^|_)door($|_)', 'candado'),
    (r'hammer|wrench|toolbox|^gear$|nut_and_bolt|axe|pick$|screwdriver|^saw$|shield|magnet|probing|hook', 'martillo'),
    (r'rocket|comet|satellite|ringed_planet|milky_way|(^|_)earth|globe|world_map', 'cohete'),
    (r'airplane|helicopter|jet|parachute|small_airplane|flight|aerial', 'avion'),
    (r'locomotive|train|railway|tram|monorail|metro|light_rail|station|bullet', 'tren'),
    (r'motorcycle|scooter|moped|racing|bicycle|bike|motor|skateboard|roller', 'motor'),
    (r'automobile|^car$|taxi|(^|_)bus($|_)|minibus|truck|trolley|tractor|parking|oncoming|fuel_pump|kick_scooter|auto_rickshaw|^bus|(^|_)car($|_)', 'claxon'),
    (r'(^|_)ship($|_)|boat|ferry|anchor|sailboat|canoe|speedboat|cruise|ring_buoy|fishing_pole', 'olas'),
    (r'trophy|medal|crown|first_place|military|reminder_ribbon', 'fanfarria'),
    (r'gift|wrapped_present|ribbon|package|shopping_bags', 'regalo'),
    (r'crystal_ball|magic_wand|fairy|genie|mage|wizard|rainbow|dizzy|glowing_star|shooting_star|^star$|^star_|sparkles|sparkle|eight_pointed|twinkl', 'magia'),
    (r'lightning|high_voltage|zap|electric', 'rayo'),
    (r'tornado|(^|_)wind($|_)|wind_chime|windy|dashing|(^|_)fog|leaf_fluttering|cloud$|^cloud|face_in_clouds', 'viento'),
    (r'(^|_)rain($|_)|rainy|umbrella_with_rain|raindrop|cloud_with_rain|^umbrella', 'lluvia'),
    (r'droplet|dew|teardrop', 'gota'),
    (r'ocean|water_wave|(^|_)wave($|_)|whale|dolphin|shark|(^|_)seal($|_)|swim|surf|rowing|diving_mask|octopus|squid|jellyfish|spouting|water_polo', 'olas'),
    (r'^sun($|_)|sunrise|sunset|sunny|sunflower|high_brightness|(^|_)warm', 'sol'),
    (r'moon|crescent|star_and_crescent|night_with_stars|milky', 'luna'),
    (r'musical_note|musical_notes|musical_score|musical_keyboard|piano', 'piano'),
    (r'guitar|banjo|violin|accordion|harp|lute', 'guitarra'),
    (r'trumpet|saxophone|trombone|bugle|elephant|french_horn|(^|_)horn$|postal_horn', 'trompeta'),
    (r'drum|long_drum|bongo|conga', 'tambor'),
    (r'microphone|headphone|loudspeaker|megaphone|speaker|public_address', 'micro'),
    (r'direct_hit|bullseye|dart|archery|bow_and_arrow', 'diana'),
    (r'checkered|chequered|flag_in_hole', 'meta'),
    (r'whistle', 'silbato'),
    (r'basketball|volleyball|tennis|ping_pong|badminton|lacrosse|hockey|cricket|baseball|softball|bowling|game_die|dice|pool_8|billiard|yo_yo|flying_disc', 'rebote'),
    (r'soccer|football|rugby|kick|field_hockey|curling|goal_net', 'patada'),
    (r'check_mark|check_box|white_heavy|ballot_box_with_check|hundred|100|thumbs|heavy_check|sparkle_ok|ok_button|vs_button|cool_button|new_button|free_button|up_button', 'acierto'),
    (r'cross_mark|multiply|prohibited|no_entry|stop_sign|^no_|negative_squared|minus|^x_|forbidden|no_mobile|no_smoking|no_pedestrians|no_littering', 'error'),
    (r'warning|radioactive|biohazard|children_crossing|loud_sound', 'alerta'),
    (r'exclamation|bangbang|interrobang|^ng_button|sos', 'exclamacion'),
    (r'question|grey_question|white_question', 'pregunta'),
    # --- comida y bebida
    (r'bottle_with_popping_cork|champagne', 'champan'),
    (r'beer|clinking|wine|cocktail|tumbler|glass|sake|fork|knife|chopsticks|plate|spoon|bowl|tableware|toast', 'clink'),
    (r'hot_beverage|teacup|teapot|coffee|cup_with_straw|beverage_box|bubble_tea|milk|baby_bottle|mate|juice|thermos|pouring', 'sorbo'),
    (r'bubbles|soap|bubble', 'burbuja'),
    # --- animales
    (r'(^|_)dog($|_)|poodle|guide_dog|service_dog|(^|_)wolf|(^|_)fox|raccoon', 'perro'),
    (r'^cat($|_)|(^|_)cat($|_)', 'gato'),
    (r'(^|_)(lion|tiger|leopard|bear|panda|koala|dragon|rhinoceros|hippopotamus|crocodile|gorilla|orangutan|badger|boar)($|_)|t_rex|sauropod|dragon_face', 'leon'),
    (r'(^|_)cow($|_)|(^|_)ox$|water_buffalo|bison', 'vaca'),
    (r'(^|_)pig($|_)|pig_face|pig_nose', 'cerdo'),
    (r'frog|toad', 'rana'),
    (r'(^|_)(duck|goose|swan)($|_)', 'pato'),
    (r'(^|_)owl($|_)', 'buho'),
    (r'chicken|rooster|chick|(^|_)bird|dove|eagle|flamingo|peacock|parrot|turkey|penguin|blue_jay|dodo|feather|(^|_)nest|hatching|swallow', 'pajaro'),
    (r'snake|lizard|turtle|scorpion|spider|(^|_)worm|caterpillar', 'serpiente'),
    (r'(^|_)bee($|_)|honeybee|(^|_)fly$|mosquito|beetle|(^|_)bug($|_)|(^|_)ant$|cockroach|ladybug|butterfly', 'abeja'),
    (r'fish|blowfish|shrimp|lobster|crab|oyster|snail|coral|clam|tropical', 'burbuja'),
    (r'(^|_)(horse|unicorn|zebra|deer|donkey|camel|llama|giraffe|goat|sheep|ram|ewe|kangaroo|sloth|hedgehog|squirrel|chipmunk|rabbit|mouse|rat|hamster|otter|skunk|moose|beaver|bison)($|_)', 'pop_a'),
    # --- naturaleza y objetos varios
    (r'leaf|maple|fallen_leaf|herb|clover|seedling|plant|palm|tree|cactus|mushroom|ear_of_rice|bamboo|wilted|lotus', 'swish'),
    (r'rose|blossom|cherry|tulip|hibiscus|bouquet|hyacinth|flower|sunflower|wood|rosette', 'ding'),
    (r'broom|scissors|razor|knife|dagger|sword|crossed_swords|saw|sponge|brush|paint|crayon|artist_palette|telescope|magnifying|lotion', 'swish'),
    (r'syringe|pill|stethoscope|test_tube|microscope|dna|hospital|adhesive_bandage|x_ray|thermometer|medical|head_bandage|crutch', 'pop_b'),
    (r'laptop|computer|keyboard|desktop|printer|mouse$|trackball|floppy|dvd|optical|cd$|minidisc|abacus|battery|electric_plug|plug', 'tick'),
    (r'television|tv|video_cassette|vhs|film', 'pop_b'),
    (r'ticket|admission|performing_arts|circus|theater|curtain', 'claqueta'),
    (r'puzzle|chess|jigsaw|mahjong|flower_playing|playing_card|dominoes|spade|club_suit|diamond_suit', 'pop_c'),
    (r'volume|sound|muted|mute', 'micro'),
    (r'arrow|arrows|counterclockwise|clockwise|repeat|back_arrow|end_arrow|on_arrow|soon_arrow|top_arrow|leftwards|rightwards|up_right|up_left|down_right|down_left|curving|shuffle|rewind|fast_forward|eject|play_button|pause|stop_button|record_button|next_track|last_track', 'swish'),
    (r'keycap|input_numbers|input_latin|input_symbols|1234|abc|abcd|plus|minus|divide|heavy|wavy|part_alternation|copyright|registered|trade_mark|infinity|recycling', 'tick'),
    (r'aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces|ophiuchus|zodiac', 'ding'),
    (r'triangular_flag|white_flag|black_flag|rainbow_flag|pirate_flag|crossed_flags|waving_white_flag|waving_black_flag', 'swish'),
    (r'^flag_|flag$', 'ding'),
    # --- lugares, ropa y otros (lo que quedaba sin sonido propio)
    (r'church|mosque|temple|synagogue|shrine|kaaba|place_of_worship|wedding|person_in_tuxedo|person_with_veil|bride|ring$|(^|_)ring($|_)', 'campana'),
    (r'castle|classical_building|prince|princess|elf|troll|merperson|hairy_creature|statue_of_liberty|tokyo_tower', 'magia'),
    (r'stadium', 'aplauso'),
    (r'mountain|desert|cyclone|landslide|national_park|mount_fuji|closed_umbrella', 'viento'),
    (r'fountain|water_closet|potable_water', 'gota'),
    (r'camping|tent|hut|bonfire', 'fuego'),
    (r'construction|building_construction|ladder|shovel|brick|rock$|(^|_)wheel$|barber_pole', 'martillo'),
    (r'orca', 'olas'),
    (r'mammoth', 'trompeta'),
    (r'(^|_)wing$|wing$', 'pajaro'),
    (r'police_officer|guard$', 'silbato'),
    (r'detective|fingerprint|(^|_)ear($|_)|ear_with', 'ojos'),
    (r'person_bouncing_ball|person_golfing|person_juggling|person_cartwheeling|person_playing_handball|people_wrestling|person_fencing', 'rebote'),
    (r'skier|person_climbing|person_mountain_biking|sled|ice_skate', 'swish'),
    (r'goggles|necktie|t_shirt|jeans|scarf|gloves|coat|socks|dress|kimono|sari|briefs|shorts|bikini|clothes|purse|handbag|clutch|backpack|sandal|shoe|boot|hat$|_hat|(^|_)cap$|billed_cap|helmet|vest|ballet|wastebasket|folding_hand_fan|thread|yarn|knot|sewing|safety_pin|basket|roll_of_paper|lab_coat', 'swish'),
    (r'lipstick', 'beso'),
    (r'maracas|nesting|teddy|piñata', 'tambor'),
    (r'treasure_chest', 'dinero'),
    (r'cigarette', 'fuego'),
    (r'coffin|headstone|funeral_urn|nazar|hamsa', 'calavera'),
    (r'balance_scale|white_cane|prayer_beads|compass|luggage|straight_ruler|triangular_ruler|paperclip|black_nib|control_knobs|level_slider|petri_dish|alembic|drop_of_blood|postbox|videocassette', 'tick'),
    (r'mirror|information|(^|_)id_button|atom_symbol|yin_yang|peace_symbol|om$|khanda|menorah|wheel_of_dharma|trident|fleur', 'ding'),
    (r'pregnant|breast_feeding|paw_prints', 'pop_a'),
    (r'baby|(^|_)child($|_)|(^|_)boy($|_)|(^|_)girl($|_)', 'pop_a'),
    (r'santa|claus', 'campana'),
    (r'superhero|supervillain|ninja', 'swish'),
    (r'brain', 'pensando'),
    (r'footprints|walking|running|hiking', 'tick'),
    (r'facepalm|shrug|gesturing|tipping', 'boing'),
]
_REGLAS = [(re.compile(p), f) for p, f in _R]

# Variedad para lo que no tiene sonido propio: el grupo decide el carácter, el id elige la variante (siempre la misma para un emoji).
_POR_GRUPO = {
    'caras': ('pop_a', 'pop_b', 'pop_d'),
    'manos': ('pop_b', 'swish', 'pop_d'),
    'corazones': ('corazon',),
    'personas': ('pop_b', 'pop_c', 'pop_a'),
    'naturaleza': ('pop_a', 'ding', 'swish'),
    'comida': ('crunch',),
    'viajes': ('swish', 'pop_c', 'pop_b'),
    'ocio': ('pop_d', 'tick', 'pop_c'),
    'objetos': ('pop_b', 'tick', 'pop_c'),
    'simbolos': ('ding', 'tick', 'pop_c'),
    'trabajo': ('tick', 'pop_b'),
    'dinero': ('dinero',),
    'varios': ('pop_a', 'pop_c'),
    'mios': ('ding',),
}
_CACHE_FAMILIA = {}


def familia_de(eid, grupo=None):
    """La familia de sonido de un emoji (por su id del catálogo)."""
    eid = str(eid or '')
    if eid in _CACHE_FAMILIA:
        return _CACHE_FAMILIA[eid]
    fam = None
    for patron, f in _REGLAS:
        if patron.search(eid):
            fam = f
            break
    if fam is None:
        if grupo is None:
            try:
                grupo = (emojis.por_id(eid) or {}).get('grupo')
            except Exception:
                grupo = None
        opciones = _POR_GRUPO.get(grupo) or ('pop_a', 'pop_b', 'pop_c', 'pop_d', 'ding')
        fam = opciones[zlib.crc32(eid.encode('utf-8')) % len(opciones)]
    _CACHE_FAMILIA[eid] = fam
    return fam


def ruta_de(familia):
    """El audio de la familia: el del usuario (mismo nombre) o el que trae el programa. None si no hay."""
    for base in (carpeta_usuario(), carpeta_programa()):
        for ext in EXTENSIONES:
            p = base / f'{familia}{ext}'
            if p.is_file():
                return p
    return None


PREF_SONIDOS = 'sfx_emoji_sonidos'      # {id del emoji: nombre de una familia | ruta de un archivo | '' (sin sonido)}


def familias():
    """Los nombres de todas las familias que tienen audio (los del programa y los que el usuario dejó en su carpeta)."""
    nombres = set()
    for base in (carpeta_programa(), carpeta_usuario()):
        try:
            for p in base.iterdir():
                if p.suffix.lower() in EXTENSIONES:
                    nombres.add(p.stem)
        except OSError:
            continue
    return sorted(nombres)


def asignados():
    """Lo que el usuario eligió emoji por emoji: {id: familia | ruta | ''}. {} si no cambió ninguno."""
    try:
        datos = json.loads((sfx_rules.CARPETA_USUARIO / 'preferencias.json').read_text(encoding='utf-8'))
        valor = datos.get(PREF_SONIDOS)
    except Exception:
        return {}
    if not isinstance(valor, dict):
        return {}
    return {str(k): v for k, v in valor.items() if isinstance(v, str)}


def asignar(eid, valor):
    """Fija el sonido de UN emoji: una familia, la ruta de un archivo, '' = sin sonido, o None = volver al de siempre. Devuelve todos."""
    import ajustes_ui
    nuevos = asignados()
    if valor is None:
        nuevos.pop(str(eid), None)
    else:
        nuevos[str(eid)] = str(valor)
    ajustes_ui.guardar_prefs({PREF_SONIDOS: nuevos})
    return nuevos


def restablecer_todos():
    import ajustes_ui
    ajustes_ui.guardar_prefs({PREF_SONIDOS: {}})


FAMILIAS_GENERICAS = {'pop_a', 'pop_b', 'pop_c', 'pop_d', 'ding', 'tick', 'swish'}      # las que no dicen nada del emoji: aquí el contexto decide
FAMILIA_POSITIVA, FAMILIA_NEGATIVA = 'acierto', 'error'


def sonido_de(eid, propios=None, grupo=None, contexto=0):
    """(ruta, origen) del sonido de UN emoji. origen: 'tuyo' (lo eligió el usuario), 'silencio' (lo apagó) o 'original' (el de su familia).
    v5.4.8: `contexto` > 0 (la frase suena positiva) o < 0 (negativa): un emoji con sonido GENÉRICO (un pop, un tick…) suena «acierto» o «error» según la frase;
    los que tienen sonido propio (fuego, dinero, risa…) no cambian y lo que eligió el usuario manda siempre."""
    elegido = (asignados() if propios is None else propios).get(str(eid))
    if elegido == '':
        return None, 'silencio'
    if elegido:
        p = Path(elegido)
        ruta = p if (p.is_absolute() and p.is_file()) else ruta_de(elegido)       # un archivo suyo o el nombre de una familia
        if ruta is not None:
            return ruta, 'tuyo'
    fam = familia_de(eid, grupo)
    if contexto and fam in FAMILIAS_GENERICAS:
        alterna = ruta_de(FAMILIA_POSITIVA if contexto > 0 else FAMILIA_NEGATIVA)
        if alterna is not None:
            return alterna, 'original'
    return ruta_de(fam), 'original'


def contexto_activo():
    """Interruptor «Sonido según el contexto»: por defecto encendido."""
    try:
        datos = json.loads((sfx_rules.CARPETA_USUARIO / 'preferencias.json').read_text(encoding='utf-8'))
        return datos.get('sfx_emoji_contexto', True) is not False
    except Exception:
        return True


def activo():
    """Interruptor «Sonidos de emojis» (SFX Lab). Por defecto encendido."""
    try:
        datos = json.loads((sfx_rules.CARPETA_USUARIO / 'preferencias.json').read_text(encoding='utf-8'))
        return datos.get('sfx_emojis', True) is not False
    except Exception:
        return True


def _inicio_de_linea(bloque):
    """El instante en que sale la línea que lleva el emoji (donde se ve el emoji)."""
    t0 = float(bloque.get('start') or 0)
    fin = float(bloque.get('end') or t0)
    try:
        k = int(bloque.get('emoji_linea') or 0)
        lineas = bloque.get('lines') or []
        if 0 <= k < len(lineas):
            t = float(lineas[k].get('start', t0) or t0)
            return min(max(t, t0), max(t0, fin))
    except (TypeError, ValueError):
        pass
    return t0


VENTANA_TOQUE_S = 0.15          # el toque de una palabra que cae a menos de esto del sonido de su emoji se quita


def _quitar_toque_de_palabra(bloques, t):
    """v5.5: el sonido del emoji ya marca esa palabra: el toque genérico del modo simple (TAP_POP, typewriter, Iphone Taping) que cae encima se quita, para que no suenen dos a la vez
    (con el emoji de la palabra clave sonaba «pop» + «tap» pegados y se oía abrumador). Lo que el usuario puso a mano no se toca."""
    for b in bloques:
        eventos = b.get('sfx_eventos')
        if not eventos:
            continue
        quedan = [e for e in eventos if not (e.get('sfx') == sfx_rules.CATEGORIA_SIMPLE and not e.get('sfx_manual') and abs(float(e.get('t') or 0) - t) <= VENTANA_TOQUE_S)]
        if len(quedan) != len(eventos):
            if quedan:
                b['sfx_eventos'] = quedan
            else:
                b.pop('sfx_eventos', None)
                b.pop('sfx', None)


def agregar_eventos(bloques, pista_sfx=None):
    """Suma el sonido de cada emoji a 'bloques' (en su sitio) y devuelve (cuántos, pista_sfx actualizada para el manifiesto).
    No hace nada si el interruptor está apagado o ningún bloque lleva emoji."""
    pista = dict(pista_sfx or {})
    if not activo():
        return 0, pista
    usados = {}
    n = 0
    ultimo_t = None
    propios = asignados()
    con_contexto = contexto_activo()
    for b in sorted((x for x in bloques if x.get('emoji')), key=lambda x: float(x.get('start') or 0)):
        ctx = 0
        if con_contexto:
            try:
                import sentimiento
                ctx = sentimiento.valencia(sfx_rules._texto_del_bloque(b))
            except Exception:
                ctx = 0
        ruta = sonido_de(b['emoji'], propios, contexto=ctx)[0]            # el que eligió el usuario para ese emoji o el de su familia (None = silencio)
        if ruta is None:
            continue
        t = _inicio_de_linea(b)
        if ultimo_t is not None and t - ultimo_t < SEPARACION_MIN_S:
            continue
        # un bloque que ya traía UN sonido propio (modo por reglas) lo conserva como evento: con 'sfx_eventos' el script ignora el otro
        if not b.get('sfx_eventos') and b.get('sfx'):
            if not b.get('sfx_archivo'):
                continue
            b['sfx_eventos'] = [{'t': round(float(b.get('start') or 0), 3), 'sfx': b['sfx'], 'sfx_nombre': b.get('sfx_nombre') or Path(b['sfx_archivo']).name,
                                 'sfx_original': b.get('sfx_original') or b['sfx_archivo'], 'sfx_archivo': b['sfx_archivo'], 'sfx_manual': bool(b.get('sfx_manual'))}]
        try:
            para_resolve = sfx_rules.para_resolve(ruta, None)
        except Exception:
            para_resolve = str(ruta)
        _quitar_toque_de_palabra(bloques, t)
        b.setdefault('sfx_eventos', []).append({'t': round(t, 3), 'sfx': CATEGORIA, 'sfx_nombre': Path(ruta).name, 'sfx_original': str(ruta),
                                                'sfx_archivo': para_resolve, 'sfx_manual': False, 'emoji': b['emoji']})
        b.setdefault('sfx', CATEGORIA)
        usados[para_resolve] = True
        ultimo_t = t
        n += 1
    if n:
        pista.setdefault('sfx_library', str(sfx_rules.carpeta_libreria()))
        archivos = dict(pista.get('sfx_archivos') or {})
        archivos[CATEGORIA] = sorted(usados)
        pista['sfx_archivos'] = archivos
        resumen = dict(pista.get('sfx_resumen') or {})
        resumen[CATEGORIA] = n
        pista['sfx_resumen'] = resumen
        pista.setdefault('sfx_config', {'nombre_pista_audio': 'SFX', 'volumen_db': None, 'al_inicio': False})
    return n, pista


def resumen_familias(ids=None):
    """{familia: cuántos emojis} — para revisar el reparto."""
    cuenta = {}
    for e in (emojis.catalogo() if ids is None else [{'id': i} for i in ids]):
        f = familia_de(e['id'], e.get('grupo'))
        cuenta[f] = cuenta.get(f, 0) + 1
    return cuenta
