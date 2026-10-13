# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_tema5_acomp.py — los ACOMPAÑANTES del Tema 5: una animación pequeña justo DEBAJO del caption que ilustra lo que se dice
# (Remotion «AcompananteT5»). Pedido del usuario: «hoy estamos en Guatemala → la animación abajo de los captions», «hola amigos → un motion
# relacionado», «crea más estilos para no repetir las tomas con lo mismo».
"""
    acompanantes(bloques, idioma, ocupado, acento, aspecto, dur) -> piezas 'acomp' (capa delante; su `y` la pone coordinar() bajo su caption)

Qué entiende (es/en/pt), en este orden: un PAÍS (pin + bandera + «Estamos en …»), un SALUDO («¡Hola amigos!» con la mano), una acción de REDES
(seguir, like, suscribirse, comentar, compartir, guardar: el botón que se pulsa), una CIFRA con su unidad (tiempo · dinero · %), y si no, el
CONCEPTO de la frase como emoji 3D (el catálogo de emojis del programa: boda, maquillaje, iglesia, café, lluvia…). Nunca dos seguidos, nunca el
mismo tipo dos veces seguidas, nunca el mismo emoji dos veces, y nunca encima de una escena, de un elemento en pantalla o de una clave detrás.
"""
import re
import unicodedata
from pathlib import Path

SALUDOS = {'hola', 'holaa', 'holi', 'hello', 'hi', 'hey', 'buenas', 'bienvenidos', 'bienvenidas', 'bienvenido', 'welcome', 'ola', 'oi', 'saludos'}
A_QUIEN = {'amigos', 'amigas', 'chicos', 'chicas', 'todos', 'todas', 'gente', 'familia', 'guys', 'everyone', 'everybody', 'friends', 'pessoal', 'galera'}
REDES = {'sigueme': 'seguir', 'siguenos': 'seguir', 'seguirme': 'seguir', 'follow': 'follow', 'like': 'like', 'likes': 'like', 'megusta': 'like',
         'suscribete': 'suscribir', 'suscribanse': 'suscribir', 'subscribe': 'subscribe', 'inscrevase': 'suscribir', 'comenta': 'comentar', 'comentame': 'comentar',
         'comenten': 'comentar', 'comment': 'comment', 'comente': 'comentar', 'comparte': 'compartir', 'compartelo': 'compartir', 'share': 'share',
         'compartilhe': 'compartir', 'guarda': 'guardar', 'guardalo': 'guardar', 'save': 'save', 'salve': 'guardar', 'comentarios': 'comentar',
         'comentario': 'comentar', 'comments': 'comment', 'comentarios.': 'comentar', 'comentarios?': 'comentar'}
KICKER_LUGAR = {'es': 'Estamos en', 'en': 'We are in', 'pt': 'Estamos em'}
ESTAMOS = {'estamos', 'estoy', 'aqui', 'here', 'in', 'en', 'desde', 'from', 'em', 'estou', 'somos'}
NEGACION = {'no', 'not', 'nunca', 'never', 'sin', 'without', 'ni', 'nor', 'jamas', 'nao', 'nem', 'dont', 'doesnt', 'didnt', 'isnt', 'arent', 'wasnt',
            'cant', 'wont', 'tampoco', 'nada', 'nadie', 'ningun', 'ninguna'}


def plegar(t):
    t = unicodedata.normalize('NFD', str(t).lower())
    return re.sub(r'[^a-z0-9%$]', '', ''.join(c for c in t if unicodedata.category(c) != 'Mn'))


# El concepto -> el emoji 3D (Fluent, de los que trae el programa en 2_recursos/emojis/png). Curado a mano: las claves del catálogo tienen ruido
# («summer» -> jarra de cerveza), y un acompañante que no encaja es peor que ninguno.
_GRUPOS = {
    # bodas y eventos
    'two_hearts': 'boda bodas wedding weddings casamento casamiento matrimonio marriage',
    'heart_with_arrow': 'novia novio novios bride groom noiva noivo pareja couple',
    'gem_stone': 'anillo anillos ring rings alianza alianzas joya joyas jewelry diamante diamond diamantes lujo luxury premium oro gold',
    'folded_hands': 'iglesia church igreja ceremonia ceremony cerimonia oracion prayer gracias thanks thank obrigado obrigada bendicion',
    'party_popper': 'fiesta fiestas party festa celebracion celebrar celebration celebrate evento eventos event',
    'clinking_glasses': 'brindis toast brinde brindar',
    'bottle_with_popping_cork': 'champagne champan champana',
    'birthday_cake': 'pastel torta cake bolo cumpleanos birthday aniversario',
    'wrapped_gift': 'regalo regalos gift gifts presente presentes sorpresa',
    'rose': 'rosa rosas ramo bouquet',
    'cherry_blossom': 'flores flor flowers flower primavera spring',
    'wine_glass': 'vino wine vinho copa',
    'beer_mug': 'cerveza beer cerveja',
    'musical_notes': 'baile bailar dance dancing dancar musica music cancion song cancao',
    'headphone': 'dj auriculares headphones fones',
    'balloon': 'globos globo balloons balloon',
    'confetti_ball': 'confeti confetti',
    'crown': 'xv quinceanera quince princesa princess reina queen rey king vip lider leader',
    'sparkles': 'maquillaje makeup maquiagem brillo brilla sparkle glow magia magic magico',
    'camera': 'foto fotos photo photos fotografia photography fotografo photographer sesion',
    'movie_camera': 'video videos grabar filmar record recording camara camera',
    'clapper_board': 'pelicula movie film cine escena',
    # comida
    'hot_beverage': 'cafe coffee',
    'pizza': 'pizza pizzas', 'hamburger': 'hamburguesa hamburguesas burger burgers hamburger', 'taco': 'taco tacos', 'sushi': 'sushi',
    'french_fries': 'papas fries batatas', 'avocado': 'aguacate avocado abacate guacamole', 'chocolate_bar': 'chocolate',
    'cookie': 'galleta galletas cookie cookies', 'doughnut': 'dona donas donut donuts', 'strawberry': 'fresa fresas strawberry strawberries morango',
    'watermelon': 'sandia watermelon melancia', 'red_apple': 'manzana manzanas apple apples', 'banana': 'banana bananas platano banano',
    'face_savoring_food': 'comida food delicioso delicious rico sabroso comer eat restaurante restaurant receta recipe cocina cooking',
    'cup_with_straw': 'bebida bebidas drink drinks jugo juice smoothie',
    # casa e inmobiliaria
    'house': 'casa casas house houses home hogar lar propiedad property vivienda',
    'key': 'llave llaves key keys chave chaves',
    'bed': 'cama camas bed bedroom dormitorio habitacion recamara quarto',
    'office_building': 'edificio oficina office building oficinas apartamento apartment departamento condominio',
    'beach_with_umbrella': 'playa beach praia', 'desert_island': 'isla island ilha', 'snow_capped_mountain': 'montana mountain montanha volcan volcano',
    'potted_plant': 'jardin garden planta plantas plant plants', 'deciduous_tree': 'arbol arboles tree trees bosque forest',
    'water_wave': 'piscina pool lago lake pond mar sea oceano ocean waterfront rio river',
    'ship': 'barco boat boats lancha ship crucero cruise',
    'package': 'mudanza moving caja cajas box paquete package pacote envio',
    # negocio y dinero
    'money_bag': 'dinero money dinheiro plata lana ganancias profit',
    'dollar_banknote': 'dolares dollars dolar dollar precio price preco pago pay pagar',
    'coin': 'moneda monedas coin coins', 'credit_card': 'tarjeta card cartao', 'bank': 'banco bank',
    'shopping_bags': 'compras shopping comprar buy tienda store loja',
    'shopping_cart': 'carrito cart', 'delivery_truck': 'entrega delivery shipping camion',
    'chart_increasing': 'ventas sales vendas crecimiento growth crecer grow aumento',
    'briefcase': 'negocio negocios business empresa company emprendedor trabajo work job trabalho',
    'busts_in_silhouette': 'clientes clients customers cliente seguidores followers audiencia audience',
    'handshake': 'equipo team equipe trato deal acuerdo socio partner',
    'bullseye': 'meta metas goal goals objetivo objetivos target',
    'light_bulb': 'idea ideas ideia tip tips consejo consejos',
    'trophy': 'exito success sucesso ganar win winner premio award prize campeon champion',
    'free_button': 'gratis free gratuito', 'new_button': 'nuevo nueva new novo nuevos',
    'bar_chart': 'datos data estadisticas stats resultados results',
    'receipt': 'recibo factura invoice receipt', 'writing_hand': 'contrato contract firma firmar sign', 'memo': 'notas notes lista checklist',
    'books': 'libro libros book books livro estudiar study', 'graduation_cap': 'escuela universidad school college graduacion graduation titulo degree curso course',
    # tecnología y redes
    'mobile_phone': 'telefono celular phone smartphone movil iphone app apps',
    'laptop': 'computadora computer ordenador laptop pc',
    'globe_showing_europe_africa': 'internet web mundo world global planeta planet', 'world_map': 'mapa map',
    'robot': 'robot robots ia ai inteligencia automatizacion automation',
    'rocket': 'cohete rocket lanzamiento launch despegar',
    'video_game': 'juego juegos game games gamer videojuego videojuegos',
    'television': 'tele television tv',
    'speech_balloon': 'mensaje mensajes message messages chat dm',
    'bell': 'notificacion notificaciones notification notifications campana bell alerta',
    'megaphone': 'anuncio anuncios announcement ads publicidad marketing',
    'studio_microphone': 'microfono microphone podcast entrevista interview',
    'hammer_and_wrench': 'herramientas tools arreglar fix repair',
    'gear': 'configuracion settings ajustes sistema system',
    'battery': 'bateria battery energia energy',
    'magnifying_glass_tilted_left': 'buscar search busqueda encontrar find',
    'locked': 'seguridad security seguro privado private contrasena password',
    'alarm_clock': 'reloj clock alarma alarm despertador',
    'calendar': 'calendario calendar fecha date agenda',
    'hourglass_not_done': 'pronto soon esperar wait espera',
    # deporte y salud
    'person_lifting_weights': 'gimnasio gym ejercicio workout entrenar entrenamiento training pesas',
    'person_running': 'correr run running maraton marathon', 'person_biking': 'bici bicicleta bike cycling',
    'person_in_lotus_position': 'yoga meditar meditation meditacion calma',
    'flexed_biceps': 'fuerza strong fuerte musculo muscle', 'soccer_ball': 'futbol soccer football futebol', 'basketball': 'basket baloncesto basketball',
    'tennis': 'tenis tennis', 'stethoscope': 'salud health medico doctor saude', 'hospital': 'hospital clinica clinic',
    'pill': 'medicina pastilla pastillas pill pills vitaminas vitamins', 'syringe': 'vacuna vaccine inyeccion',
    'sleeping_face': 'dormir sleep sueno descanso', 'brain': 'cerebro brain mente mind',
    'test_tube': 'ciencia science laboratorio lab',
    # viajes y clima
    'airplane': 'viaje viajes viajar travel trip vacaciones vacation viagem ferias avion airplane vuelo flight plane',
    'automobile': 'carro auto car coche carros autos cars', 'train': 'tren train', 'tent': 'acampar camping carpa tent',
    'sun': 'sol sun soleado sunny verano summer verao', 'cloud_with_rain': 'lluvia rain chuva', 'cloud_with_lightning_and_rain': 'tormenta storm tempestade',
    'snowflake': 'nieve snow invierno winter neve frio cold', 'crescent_moon': 'noche night luna moon noite',
    'star': 'estrella estrellas star stars', 'rainbow': 'arcoiris rainbow', 'statue_of_liberty': 'newyork nuevayork',
    # emociones y otros
    'red_heart': 'amor love amo corazon heart',
    'beaming_face_with_smiling_eyes': 'feliz happy felicidad alegria',
    'face_with_tears_of_joy': 'risa gracioso funny jaja haha',
    'crying_face': 'triste sad llorar cry', 'face_screaming_in_fear': 'miedo scared fear terror',
    'star_struck': 'wow increible amazing incredible impresionante',
    'thinking_face': 'pensando thinking duda doubt', 'shushing_face': 'secreto secret secretos secrets',
    'ok_hand': 'genial cool perfecto perfect', 'fire': 'fuego fire viral hot caliente brutal',
    'exploding_head': 'locura crazy loco mindblowing', 'cross_mark': 'error errores mistake mistakes', 'check_mark_button': 'correcto correct listo done',
    'warning': 'cuidado warning peligro danger', 'prohibited': 'prohibido forbidden',
    'dog_face': 'perro perros dog dogs perrito cachorro', 'cat_face': 'gato gatos cat cats',
    'teddy_bear': 'bebe baby bebes babies ninos kids children hijos familia family',
    'artist_palette': 'arte art pintar paint diseno design', 'guitar': 'guitarra guitar',
}
CONCEPTOS_ACOMP = {w: eid for eid, ws in _GRUPOS.items() for w in ws.split()}


def _sticker(palabra, idioma, usados):
    """El emoji 3D de esa palabra (exacta o su singular) si está en el mapa curado, existe su PNG y no se usó: (id, archivo) o (None, None)."""
    w = plegar(palabra)
    for f in [w] + ([w[:-2]] if w.endswith('es') and len(w) > 4 else []) + ([w[:-1]] if w.endswith('s') and len(w) > 3 else []):
        eid = CONCEPTOS_ACOMP.get(f)
        if eid and eid not in usados:
            try:
                import emojis
                if (emojis.carpeta() / 'png' / f'rcs_emoji_{eid}.png').is_file():
                    return eid, f'rcs_emoji_{eid}.png'
            except Exception:
                return None, None
    return None, None


def acompanantes(bloques, idioma='es', ocupado=(), acento='#4C7DFF', aspecto='cristal', dur=0.0, debiles=frozenset()):
    try:
        import edicion_pro_planificador as PL
        paises = PL.paises()
    except Exception:
        paises = {}
    import edicion_pro_tema5_escenas as DIR
    lang = (idioma or 'es')[:2]
    out, usados, ultimo_tipo, ultimo_bloque, ultimo_fin = [], set(), None, -9, -99.0
    for nb, b in enumerate(bloques):
        a, z = b['ini'], b['fin']
        if nb - ultimo_bloque < 2 or a - ultimo_fin < 1.2 or z - a < 0.9:
            continue
        if any(a < o1 and o0 < z for o0, o1 in ocupado):
            continue
        ps = [(a + w['t'], plegar(w['texto']), w['texto'].strip('.,!?¡¿')) for w in b['palabras']]
        prop = None
        # 1) un país
        for k in range(len(ps)):
            for n in (3, 2, 1):
                clave = ''.join(p for _t, p, _x in ps[k:k + n])
                if len(clave) >= 4 and clave in paises:
                    iso, nombres = paises[clave]
                    estamos = any(p in ESTAMOS for _t, p, _x in ps[max(0, k - 2):k])
                    prop = ('lugar', ps[k][0], {'pais': iso, 'texto': nombres.get(lang) or ' '.join(x for _t, _p, x in ps[k:k + n]),
                                                'kicker': KICKER_LUGAR.get(lang, '') if estamos else ''})
                    break
            if prop:
                break
        # 2) un saludo
        if prop is None:
            for k, (t, p, x) in enumerate(ps[:4]):
                if p in SALUDOS:
                    quien = ps[k + 1][2] if k + 1 < len(ps) and ps[k + 1][1] in A_QUIEN else ''
                    frase = (x.capitalize() + (' ' + quien.lower() if quien else '')).strip()
                    prop = ('saludo', t, {'texto': (('¡' + frase + '!') if lang == 'es' else frase + '!'), 'sticker': 'rcs_emoji_waving_hand.png'})
                    break
        # 3) redes
        if prop is None:
            for k, (t, p, x) in enumerate(ps):
                cl = p + (ps[k + 1][1] if k + 1 < len(ps) else '')
                accion = REDES.get(p) or (REDES.get(cl) if cl in ('megusta',) else None)
                if accion:
                    prop = ('redes', t, {'accion': accion})
                    break
        # 4) una cifra con su unidad
        if prop is None:
            for k, (t, p, x) in enumerate(ps):
                c = DIR._cifra(x)
                if c is None:
                    continue
                valor, signo = c
                sig = [q for q in ps[k + 1:k + 3]]
                unidad = next((q for q in sig if q[1] in DIR.TIEMPO), None)
                if unidad:
                    prop = ('tiempo', t, {'valor': valor, 'unidad': unidad[2].lower()})
                elif signo in ('$', '€', '£') or any(q[1] in DIR.DINERO for q in sig):
                    prop = ('dinero', t, {'valor': valor, 'signo': signo if signo in ('$', '€', '£') else '$'})
                elif signo == '%' or (sig and sig[0][1] in ('percent', 'porciento')):
                    prop = ('cifra', t, {'valor': valor, 'signo': '%'})
                else:
                    etiqueta = next((q[2] for q in sig if q[1] not in DIR.CONECTORAS and len(q[1]) >= 3), '')
                    prop = ('cifra', t, {'valor': valor, 'signo': '', 'unidad': etiqueta.lower()})
                break
        # 5) el concepto, como emoji 3D (primero la frase clave del caption, luego el resto)
        if prop is None:
            orden = sorted(range(len(ps)), key=lambda k: (not b['palabras'][k].get('clave'), -len(ps[k][1])))
            for k in orden:
                t, p, x = ps[k]
                if len(p) < 4 or p in DIR.CONECTORAS or p in debiles:
                    continue
                if any(q in NEGACION for _t, q, _x in ps[max(0, k - 2):k]):
                    continue                                             # «no estoy FELIZ»: la carita feliz diría lo contrario
                eid, png = _sticker(x, lang, usados)
                if eid:
                    usados.add(eid)
                    prop = ('sticker', t, {'sticker': png, 'texto': x.capitalize()})
                    break
        if prop is None:
            continue
        tipo, t, valores = prop
        if tipo == ultimo_tipo and a - ultimo_fin < 3.0:
            continue                                                     # variedad: dos del mismo tipo, solo bien separados
        ini = max(a, t - 0.12)
        pegado = nb + 1 < len(bloques) and bloques[nb + 1]['ini'] - z < 0.35
        fin = min(ini + 2.6, max(z + 0.25, bloques[nb + 1]['fin'] if pegado else z + 0.25))   # la palabra al final de la frase: sigue en la siguiente
        if fin - ini < 0.9:
            continue
        sigue = pegado and fin > z + 0.3
        out.append({'pieza': 'acomp', 'remotion': 'AcompananteT5', 'capa': 'delante', 'ini': round(ini, 3), 'fin': round(fin, 3),
                    'motivo': f'acompañante {tipo}: ' + str(valores.get('texto') or valores.get('valor') or valores.get('accion') or ''),
                    'valores': dict(valores, tipo=tipo, aspecto=aspecto, acento=acento, y=66.0, escala=1.15), '_bajo': (a, z)})
        ultimo_tipo, ultimo_bloque, ultimo_fin = tipo, nb + (1 if sigue else 0), fin
    return out
