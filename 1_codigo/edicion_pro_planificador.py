# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_planificador.py — Edición PRO: qué gráfico va en cada momento de CUALQUIER video (sin Resolve, sin pantalla: se prueba solo).
"""
Lee lo que se dice (palabras con sus tiempos) y decide la edición: titulares detrás de la persona, cifras, listas, rótulos, etiquetas,
marcos en los planos sin voz y la llamada a la acción del final. Nada se inventa: todo texto que sale en pantalla es algo que se DIJO
(o una etiqueta genérica de sección, «Recorrido 01», «Momentos 02»…).

    detectar_genero(palabras)                  -> ('boda' | 'xv' | 'restaurante' | 'inmobiliaria' | 'bts' | 'general', puntos)
    direccion(genero, rng, tema)               -> paleta, tipografías, entradas, marco… (distinta en cada video: semilla del video)
    planificar(palabras, duracion, ...)        -> {'genero', 'direccion', 'piezas': [...], 'resumen'}

Cada pieza: {'pieza': 'titular'|'cifra'|…, 'capa': 'detras'|'delante'|'velo', 'ini', 'fin', 'valores': {…parámetros del .ograf…},
'persona': True si va detrás de la persona (hace falta recortarla), 'ajustar': True si su posición se afina con la persona detectada}.

Variedad: la semilla sale del video (nombre + duración + primeras palabras): el mismo video da la misma edición (repetible) y otro video
da otra paleta, otras tipografías, otras entradas y otro reparto. «Regenerar» suma 1 a la semilla.
"""
from __future__ import annotations

import hashlib
import random
import re
import unicodedata

# ----------------------------------------------------------------------------------------------------------- géneros (estilos de video)
_PAL = {
    'boda': ('boda bodas novia novio novios casamos casamiento matrimonio esposa esposo anillo anillos altar votos ceremonia recepcion '
             'luna miel wedding bride groom married marry vows ring rings ceremony reception honeymoon casamento noiva noivo aliança '
             'aliancas brindis primer baile vals compromiso pedida'),
    'xv': ('quince quinceanera quinceañera xv quinceaños quinceanos vals chambelan chambelanes chambelanes princesa corona tiara '
           'sweet sixteen fifteen debut debutante quinze anos padrino padrinos madrina misa'),
    'restaurante': ('restaurante restaurant comida comer platillo platillos plato platos menu menú chef cocina cocinero receta sabor '
                    'sabores delicioso deliciosa rico rica postre postres bebida bebidas coctel cocteles cafe café mesa reserva reservas '
                    'food dish dishes taste tasty delicious dessert drinks cocktail kitchen dinner lunch brunch breakfast cena almuerzo '
                    'desayuno tacos pizza hamburguesa sushi mariscos carne pasta vino cerveza prato comida sobremesa'),
    'inmobiliaria': ('casa casas propiedad propiedades terreno lote venta vende vendemos renta alquiler departamento depto apartamento '
                     'recamara recamaras recámaras habitacion habitaciones dormitorio dormitorios baño baños cocina sala jardin jardín '
                     'alberca piscina metros m2 hectarea hectareas acre acres cochera estacionamiento fraccionamiento residencial '
                     'property properties house home homes listing lot land bedroom bedrooms bathroom bathrooms sqft square feet pool '
                     'waterfront estate realtor mortgage imovel imóvel quartos apartamento venda aluguel inmobiliaria inmueble'),
    'bts': ('detras camara cámara camaras rodaje rodando grabacion grabación grabando set escena escenas toma tomas plano planos corte '
            'accion acción director directora produccion producción crew equipo luces iluminacion lente lentes edicion edición '
            'behind scenes shoot shooting filming film footage crew lighting lens camera gimbal drone dron making of bastidores filmagem'),
}
PALABRAS_GENERO = {g: set(t.split()) for g, t in _PAL.items()}
_FRASES_GENERO = {'bts': ('detras de camara', 'behind the scenes', 'making of', 'por detras'), 'xv': ('mis xv', 'mis quince', 'quince años', 'quince anos'),
                  'inmobiliaria': ('bienes raices', 'real estate', 'en venta', 'for sale', 'square feet'), 'boda': ('nos casamos', 'el si', 'just married', 'save the date')}

GENEROS = ('auto', 'general', 'inmobiliaria', 'boda', 'xv', 'restaurante', 'bts')

# paletas por género (acento, texto, panel, bloque); varias por género: la semilla elige
PALETAS = {
    'inmobiliaria': [('#c9a46a', '#ffffff', '#12110f', '#141210'), ('#7fb3c8', '#ffffff', '#0f1418', '#101820'), ('#d8c3a5', '#ffffff', '#151311', '#1a1714'),
                     ('#9fbf8f', '#ffffff', '#111511', '#131a13')],
    'boda': [('#d8b67a', '#fffaf2', '#1a1612', '#1c1813'), ('#e8b9b3', '#fffaf7', '#1d1514', '#211817'), ('#b9c7a8', '#fbfcf8', '#141713', '#171b16'),
             ('#cfc1e6', '#fdfbff', '#17141c', '#1a1720')],
    'xv': [('#e7a6c4', '#ffffff', '#1d1219', '#22141d'), ('#c9a2f0', '#ffffff', '#18121f', '#1c1524'), ('#f2c46d', '#ffffff', '#1d1710', '#221b12'),
           ('#7ed0e6', '#ffffff', '#0f1a1e', '#122026')],
    'restaurante': [('#e07a4f', '#fff8f0', '#1b1410', '#211812'), ('#c8a24a', '#fffaf0', '#17140e', '#1c1810'), ('#8fae6e', '#fbfaf2', '#141710', '#181c12'),
                    ('#d9534f', '#ffffff', '#1a1111', '#201414')],
    'bts': [('#ffb020', '#ffffff', '#111111', '#141414'), ('#ff4d3d', '#ffffff', '#121010', '#161212'), ('#3fd0c9', '#ffffff', '#0d1414', '#101919'),
            ('#e8e8e8', '#ffffff', '#121212', '#161616')],
    'general': [('#3e6ef2', '#ffffff', '#0f1220', '#121628'), ('#ffd21f', '#ffffff', '#141210', '#18160f'), ('#ff5a5f', '#ffffff', '#171012', '#1c1214'),
                ('#2fd18b', '#ffffff', '#0f1712', '#111c15'), ('#b17cff', '#ffffff', '#15111d', '#191422')],
}
# (titulares, textos de apoyo) por género
TIPOGRAFIAS = {
    'inmobiliaria': [('serif', 'grotesk'), ('grotesk', 'grotesk'), ('serif', 'redonda')],
    'boda': [('serif', 'serif'), ('serif', 'redonda')],
    'xv': [('serif', 'redonda'), ('redonda', 'redonda'), ('serif', 'grotesk')],
    'restaurante': [('serif', 'grotesk'), ('redonda', 'grotesk'), ('grotesk', 'mono')],
    'bts': [('grotesk', 'mono'), ('mono', 'mono'), ('redonda', 'mono')],
    'general': [('redonda', 'grotesk'), ('grotesk', 'grotesk'), ('serif', 'grotesk')],
}
MARCOS = {'inmobiliaria': ['ventana', 'simple'], 'boda': ['elegante', 'brillo'], 'xv': ['brillo', 'elegante'], 'restaurante': ['simple', 'elegante'],
          'bts': ['cinta', 'simple'], 'general': ['simple', 'ventana']}       # sin visor REC (al usuario no le gusta)
ICONOS_ORBITA = {'inmobiliaria': ['casa', 'key', 'bed', 'waves', 'trees'], 'boda': ['anillos', 'corazon', 'camera', 'flower', 'wine'],
                 'xv': ['crown', 'gift', 'music', 'cake', 'camera'], 'restaurante': ['cubiertos', 'chefHat', 'wine', 'coffee', 'pizza'],
                 'bts': ['camera', 'clapperboard', 'aperture', 'film', 'mic'], 'general': ['lightbulb', 'target', 'trendingUp', 'users', 'rocket']}
ORBITA_DUR = 2.8                          # el gancho: los iconos del tema giran alrededor de la cabeza en los primeros segundos
# iconos 3D (3dicons, CC0; 2_recursos/edicion_pro/ograf/lib/iconos3d): de un icono de concepto al 3D que lo cuenta, y palabras que lo llaman
ICONO_A_3D = {'coins': 'money-dynamic-premium', 'piggyBank': 'wallet-front-premium', 'shoppingCart': 'money-front-color', 'calendarDays': 'calendar-dynamic-color',
              'camera': 'camera-dynamic-premium', 'image': 'picture-dynamic-premium', 'crown': 'crown-dynamic-color', 'key': 'key-front-premium',
              'shieldCheck': 'lock-front-premium', 'plane': 'travel-dynamic-color', 'gift': 'ribbon-dynamic-color', 'target': 'flag-dynamic-color',
              'messageSquare': 'notify-heart-front-color', 'bell': 'bell-dynamic-color', 'map': 'explorer-front-color', 'globe': 'explorer-front-color',
              'zap': 'fire-front-color', 'trendingUp': 'fire-front-color', 'clock': 'calendar-dynamic-premium'}
_CONC3D = {
    'fire-front-color': 'viral fuego caliente hot fire trending tendencia increible brutal epico epica',
    'megaphone-dynamic-color': 'anuncio anuncios oferta ofertas promocion promo aviso noticia noticias atencion announcement offer news attention',
    'notify-heart-front-color': 'likes like sigueme siguenos seguidores followers follow comparte share',
    'bell-dynamic-color': 'campana suscribete subscribe notificacion notificaciones',
    'thumb-down-dynamic-color': 'malo mala peor error errores fracaso fail wrong worst bad',
    'lock-front-premium': 'privado privada secreto secret private candado',
}
CONCEPTOS3D = {w: n for n, t in _CONC3D.items() for w in t.split()}
ORBITA_3D = {'inmobiliaria': ['key-front-premium', 'money-dynamic-premium', 'wallet-front-premium', 'lock-front-premium', 'calendar-dynamic-color'],
             'boda': ['notify-heart-front-color', 'ribbon-dynamic-color', 'bell-dynamic-color', 'camera-dynamic-premium', 'picture-dynamic-premium'],
             'xv': ['crown-dynamic-color', 'ribbon-dynamic-color', 'notify-heart-front-color', 'camera-dynamic-premium', 'bell-dynamic-color'],
             'restaurante': ['fire-front-color', 'money-front-color', 'notify-heart-front-color', 'calendar-dynamic-color', 'megaphone-dynamic-color'],
             'bts': ['camera-dynamic-premium', 'picture-dynamic-premium', 'flag-dynamic-color', 'fire-front-color', 'megaphone-dynamic-color'],
             'general': ['fire-front-color', 'megaphone-dynamic-color', 'notify-heart-front-color', 'flag-dynamic-color', 'money-front-color']}
# «modo error»: cuando dice algo malo o se equivoca, el plano se pone en gris (con un sonido de apagón)
_ERROR = {'es': 'malo mala error errores equivoque equivocamos equivocacion peor fracaso fracase desastre terrible horrible fatal falle fallo perdon ups',
          'en': 'bad worst wrong mistake mistakes fail failed failure terrible horrible disaster oops sorry',
          'pt': 'ruim pior erro errei erros fracasso desastre terrivel horrivel falhei desculpa'}
GRIS_MAX, GRIS_SEP = 2, 8.0
ICONO_LISTA = {'inmobiliaria': 'check', 'boda': 'corazon', 'xv': 'estrella', 'restaurante': 'punto', 'bts': 'numero', 'general': 'check'}

# textos genéricos que pone la edición (en el idioma del video)
TEXTOS = {
    'es': {'seccion': {'inmobiliaria': 'Recorrido', 'boda': 'Momentos', 'xv': 'Recuerdos', 'restaurante': 'Sabores', 'bts': 'Detrás de cámara', 'general': 'Escena'},
           'cta': {'inmobiliaria': 'Agenda una visita', 'boda': 'Reserva tu fecha', 'xv': 'Reserva tu fecha', 'restaurante': 'Reserva tu mesa', 'bts': 'Míralo completo', 'general': 'Escríbenos'},
           'kicker_cta': {'inmobiliaria': 'Propiedad', 'boda': 'Nuestra historia', 'xv': 'Mis XV', 'restaurante': 'Te esperamos', 'bts': 'Producción', 'general': 'Siguiente paso'},
           'ubicacion': 'Ubicación', 'escena': 'ESCENA', 'toma': 'TOMA'},
    'en': {'seccion': {'inmobiliaria': 'Tour', 'boda': 'Moments', 'xv': 'Memories', 'restaurante': 'Flavors', 'bts': 'Behind the scenes', 'general': 'Scene'},
           'cta': {'inmobiliaria': 'Book a tour', 'boda': 'Save your date', 'xv': 'Save your date', 'restaurante': 'Book a table', 'bts': 'Watch the full video', 'general': 'Get in touch'},
           'kicker_cta': {'inmobiliaria': 'Property', 'boda': 'Our story', 'xv': 'Sweet fifteen', 'restaurante': 'See you soon', 'bts': 'Production', 'general': 'Next step'},
           'ubicacion': 'Location', 'escena': 'SCENE', 'toma': 'TAKE'},
    'pt': {'seccion': {'inmobiliaria': 'Tour', 'boda': 'Momentos', 'xv': 'Memórias', 'restaurante': 'Sabores', 'bts': 'Bastidores', 'general': 'Cena'},
           'cta': {'inmobiliaria': 'Agende uma visita', 'boda': 'Reserve sua data', 'xv': 'Reserve sua data', 'restaurante': 'Reserve sua mesa', 'bts': 'Veja completo', 'general': 'Fale conosco'},
           'kicker_cta': {'inmobiliaria': 'Imóvel', 'boda': 'Nossa história', 'xv': 'Meus 15', 'restaurante': 'Esperamos você', 'bts': 'Produção', 'general': 'Próximo passo'},
           'ubicacion': 'Localização', 'escena': 'CENA', 'toma': 'TOMADA'},
}

# palabra que se nombra → icono de la infografía (B-roll de motion graphics). Español, inglés y portugués.
_CONC = {
    'anillos': 'boda bodas matrimonio casamiento anillo anillos compromiso wedding ring rings casamento alianca aliancas',
    'music': 'fiesta fiestas baile bailar musica dj party dance music festa',
    'camera': 'foto fotos fotografia fotografo camara photo photos photographer camera',
    'clapperboard': 'video videos rodaje escena grabacion grabar film filming shoot scene filmagem',
    'cubiertos': 'comida comidas plato platillo menu restaurante cena almuerzo desayuno food dish dinner lunch breakfast comida prato',
    'coins': 'precio precios dinero pesos dolares costo costos pago pagar price money cost pay preco dinheiro',
    'piggyBank': 'ahorro ahorrar ahorras save savings economia',
    'shoppingCart': 'compra compras comprar venta ventas vender buy sale sales venda vendas',
    'users': 'clientes cliente gente personas familia invitados equipo amigos guests people team family friends clientes pessoas',
    'clock': 'horas minutos hours minutes horario',
    'calendarDays': 'fecha calendario date calendar',
    'gift': 'regalo regalos sorpresa gift gifts surprise presente',
    'trophy': 'exito premio premios ganar ganador win winner award success sucesso',
    'lightbulb': 'idea ideas consejo consejos tip tips truco trucos dica',
    'target': 'meta metas objetivo objetivos goal goals objetivo',
    'trendingUp': 'crecer crecimiento resultados growth grow results crescimento',
    'globe': 'mundo internacional pais paises world global country mundo',
    'smartphone': 'celular telefono app instagram tiktok whatsapp phone mobile celular',
    'messageSquare': 'mensaje mensajes comentario comentarios chat message comments mensagem',
    'key': 'llave llaves key keys chave',
    'casa': 'casa casas hogar home house houses propiedad property imovel',
    'building2': 'edificio departamento oficina building apartment office predio',
    'store': 'tienda negocio store shop business loja',
    'sun': 'sol verano playa summer sun beach verao praia',
    'sunrise': 'atardecer amanecer sunset sunrise por-do-sol',
    'moon': 'noche night noite',
    'crown': 'corona princesa reina quinceanera crown princess queen rainha',
    'image': 'recuerdo recuerdos memoria memorias memory memories lembranca',
    'rocket': 'lanzamiento lanzar launch lancamento',
    'graduationCap': 'curso clase aprender escuela course class learn school curso',
    'mic': 'entrevista podcast voz interview voice entrevista',
    'zap': 'rapido rapida energia fast quick energy rapido',
    'bed': 'cuarto cuartos recamara recamaras habitacion habitaciones dormitorio dormitorios bedroom bedrooms quarto quartos',
    'bath': 'bano banos bathroom bathrooms banheiro banheiros',
    'trees': 'jardin jardines arboles bosque garden yard backyard trees forest jardim',
    'waves': 'lago rio mar oceano alberca piscina pool lake river ocean agua water lagoa',
    'car': 'coche carro cochera garaje garage estacionamiento parking car',
    'cake': 'pastel torta cumpleanos cake birthday bolo',
    'gem': 'lujo lujosa lujoso exclusivo exclusiva joya joyas diamante luxury exclusive diamond',
    'wine': 'vino vinos brindis copa copas champagne wine toast',
    'chefHat': 'chef cocinero cocinera cocina kitchen cozinha',
    'coffee': 'cafe cafeteria coffee',
    'pizza': 'pizza pizzas',
    'aperture': 'lente lentes enfoque lens focus',
    'mountain': 'montana montanas vista vistas mountain mountains view views',
    'sofa': 'sala salon living sofa muebles amueblado amueblada furnished',
    'ruler': 'metros terreno superficie hectareas lote lot acre acres',
    'flower': 'flores flor ramo flowers bouquet',
    'heartHandshake': 'amor love',
    'plane': 'viaje viajes vuelo destino travel trip flight viagem',
    'shieldCheck': 'seguro segura seguridad garantia confianza safe security warranty',
    'map': 'mapa ubicacion zona colonia barrio vecindario neighborhood location',
}
CONCEPTOS = {w: icono for icono, texto in _CONC.items() for w in texto.split()}
ESCENA_CADA = {'sobria': 14.0, 'media': 7.5, 'espectaculo': 4.5}
Y_ESCENA = {'icono': 31, 'cifra': 33, 'lista': 32}                   # vertical: la infografía de una escena, por ENCIMA de la zona de los captions (≈ 50–70 %)       # segundos mínimos entre dos B-roll de motion graphics
FONDO_GENERO = {'inmobiliaria': ['puntos', 'aurora'], 'boda': ['aurora'], 'xv': ['aurora', 'puntos'], 'restaurante': ['aurora', 'liso'],
                'bts': ['rejilla', 'puntos'], 'general': ['aurora', 'rejilla', 'puntos']}

STOP = set(('a al ante con contra de del desde el en entre es esta este esto hacia la las le les lo los mas más me mi mis muy no nos o para pero por que qué se si sí sin '
            'sobre su sus te tu tus un una unas uno unos y ya yo él ella ellos ellas eso esa ese aqui aquí alli allí como cómo cuando donde ser estar hay tiene tienen '
            'the a an and or of to in on at for with from by is are was were be been it its this that these those you your we our they their he she his her i me my '
            'so but if then than as just about into over up out do does did have has had will would can could not no yes very really '
            'o os um uma e é de da do das dos em no na nos nas para por com sem que se seu sua'))
NUM_PALABRAS = {
    'cero': 0, 'uno': 1, 'una': 1, 'un': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10,
    'once': 11, 'doce': 12, 'trece': 13, 'catorce': 14, 'quince': 15, 'veinte': 20, 'treinta': 30, 'cuarenta': 40, 'cincuenta': 50, 'cien': 100, 'mil': 1000,
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
    'fifteen': 15, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'hundred': 100, 'thousand': 1000,
    'dois': 2, 'três': 3, 'quatro': 4, 'oito': 8, 'dez': 10, 'quinze': 15, 'vinte': 20, 'cem': 100,
}
_NO_CIFRA = {'un', 'una', 'uno', 'a', 'one', 'um', 'uma'}       # «un día», «a house»: no son datos
_CTA = ('llama', 'llamanos', 'llámanos', 'escribenos', 'escríbenos', 'contactanos', 'contáctanos', 'reserva', 'reservá', 'agenda', 'visitanos', 'visítanos',
        'siguenos', 'síguenos', 'suscribete', 'suscríbete', 'comenta', 'link', 'enlace', 'whatsapp', 'dm', 'mensaje',
        'call', 'contact', 'book', 'reach', 'visit', 'follow', 'subscribe', 'message', 'schedule', 'order', 'ordena', 'pidelo', 'pídelo', 'compra', 'buy',
        'ligue', 'entre', 'reserve', 'agende', 'siga', 'inscreva', 'comentarios', 'comentario', 'cuentame', 'cuéntame', 'dime', 'escribeme',
        'escríbeme', 'comment', 'comments', 'comente', 'comentários')
_ENFASIS = ('increible', 'increíble', 'espectacular', 'impresionante', 'unico', 'único', 'unica', 'única', 'perfecto', 'perfecta', 'mejor', 'nuevo', 'nueva',
            'gratis', 'exclusivo', 'exclusiva', 'hermoso', 'hermosa', 'maravilloso', 'maravillosa', 'inolvidable', 'especial', 'secreto', 'rapido', 'rápido',
            'amazing', 'incredible', 'stunning', 'beautiful', 'unique', 'perfect', 'best', 'new', 'free', 'exclusive', 'unforgettable', 'special', 'secret',
            'rarely', 'never', 'nunca', 'siempre', 'always', 'every', 'todo', 'todos', 'cada', 'real', 'potential', 'potencial', 'flexibility', 'flexibilidad',
            'precioso', 'preciosa', 'guapa', 'guapo', 'show', 'brutal', 'epico', 'épico', 'epica', 'épica', 'magico', 'mágico', 'magica', 'mágica',
            'emocionante', 'locura', 'fiesta', 'gorgeous', 'epic', 'magical', 'wow')


def plegar(t):
    t = unicodedata.normalize('NFKD', str(t or '').lower())
    return ''.join(c for c in t if not unicodedata.combining(c)).strip(' .,;:!?¡¿"\'()[]«»…“”')


def _txt(p):
    return re.sub(r'\{[^}]*\}', '', str(p.get('word') or p.get('text') or p.get('palabra') or '')).strip()


def idioma_de(idioma):
    i = (idioma or 'es').lower()[:2]
    return i if i in TEXTOS else ('es' if i in ('ca', 'gl', 'eu') else 'en')


# ------------------------------------------------------------------------------------------------------------------- género
def detectar_genero(palabras):
    """El estilo de video por lo que se dice. Devuelve (genero, {genero: puntos})."""
    ws = [plegar(_txt(p)) for p in palabras]
    texto = ' ' + ' '.join(ws) + ' '
    puntos = {g: 0.0 for g in PALABRAS_GENERO}
    for w in ws:
        for g, vocab in PALABRAS_GENERO.items():
            if w in vocab:
                puntos[g] += 1.0
    for g, frases in _FRASES_GENERO.items():
        for f in frases:
            puntos[g] += 3.0 * texto.count(' ' + f + ' ')
    if 'xv' in ws or 'quince' in ws and ('anos' in ws or 'años' in ws):
        puntos['xv'] += 4.0
    total = max(1, len(ws))
    mejor = max(puntos, key=puntos.get)
    # hace falta una presencia clara (no por una palabra suelta en un video largo)
    if puntos[mejor] < max(2.0, total * 0.012):
        return 'general', puntos
    return mejor, puntos


def semilla_de(video, palabras, extra=0):
    base = f'{str(video or "")}|{len(palabras)}|' + ' '.join(_txt(p) for p in palabras[:30])
    return int(hashlib.sha1(base.encode('utf-8')).hexdigest()[:8], 16) + int(extra or 0) * 7919


def direccion(genero, rng, tema=None):
    """La dirección de arte de ESTE video (cambia con la semilla)."""
    g = genero if genero in PALETAS else 'general'
    acento, texto, panel, bloque = rng.choice(PALETAS[g])
    tit, txt = rng.choice(TIPOGRAFIAS[g])
    return {
        'genero': g, 'acento': acento, 'colorTexto': texto, 'colorPanel': panel, 'colorBloque': bloque,
        'fuenteTitular': tit, 'fuenteTexto': txt,
        'entrada': rng.choice(['subir', 'desenfoque', 'mascara'] if g in ('bts', 'general', 'restaurante') else ['desenfoque', 'subir']),
        'marco': rng.choice(MARCOS[g]), 'velo': rng.choice(['arriba', 'arriba', 'vineta']), 'veloIntensidad': round(rng.uniform(0.32, 0.5), 2),
        'cifraEstilo': rng.choice(['linea', 'anillo', 'bloque'] if g != 'boda' else ['linea', 'anillo']),
        'listaDisposicion': rng.choice(['columna', 'fila']), 'icono': ICONO_LISTA[g],
        'mayusculas': rng.random() < (0.35 if tit == 'serif' and g in ('boda', 'xv') else 0.8),
        'yTitular': round(rng.uniform(24, 31), 1), 'yApoyo': round(rng.uniform(15, 20), 1),
        'etiquetaLado': rng.choice(['izq', 'izq', 'der']),
        'fondoEstilo': rng.choice(FONDO_GENERO[g]), 'fondoEntrada': rng.choice(['iris', 'iris', 'cortina']),
    }


# ------------------------------------------------------------------------------------------------------------------- frases y momentos
def unir_partidas(palabras):
    """Whisper parte «year-round» en «year» + «-round» y «it's» en «it» + «'s»: se vuelven a juntar (el tiempo, el del principio)."""
    out = []
    for p in palabras:
        t = _txt(p)
        if out and re.match(r"^[-'’]\w", t):
            q = dict(out[-1])
            q['word'] = _txt(q) + t
            q['end'] = p.get('end', q.get('end'))
            out[-1] = q
        else:
            out.append(p)
    return out


def frases_de(palabras, pausa=0.62):
    out, cur = [], []
    for k, p in enumerate(palabras):
        cur.append(k)
        t = _txt(p)
        sig = palabras[k + 1] if k + 1 < len(palabras) else None
        hueco = (float(sig.get('start', 0)) - float(p.get('end', 0))) if sig else 99.0
        if re.search(r'[.?!…]["”\')]*$', t) or hueco >= pausa or len(cur) >= 20:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _es_numero(w):
    lw = plegar(w)
    if re.fullmatch(r'[\$€£]?\d+([.,]\d+)?(%|k|m)?', lw.replace(' ', '')):
        return True
    return lw in NUM_PALABRAS and lw not in _NO_CIFRA


def _valor_numero(w):
    lw = plegar(w)
    if re.search(r'\d', lw):
        return re.sub(r'(st|nd|rd|th|º|°)$', '', w.strip(' .,;:!?'))
    v = NUM_PALABRAS.get(lw)
    return str(v) if v is not None else w


def _capital(w):
    s = w.strip(' .,;:!?¡¿"\'()«»')
    return len(s) > 1 and s[0].isupper() and not s.isupper()


def candidatos(palabras, frases, pesos=None, idioma='es'):
    """Momentos con algo que enseñar: cifras, nombres propios, listas, palabras fuertes y la llamada a la acción."""
    pesos = pesos or {}
    out = []
    for fi, idx in enumerate(frases):
        ws = [_txt(palabras[i]) for i in idx]
        lw = [plegar(w) for w in ws]
        # cifras: «3 acres», «15 años», «40 %», «$12»
        for j, w in enumerate(ws):
            if _es_numero(w):
                unidad = []
                for k in range(j + 1, min(j + 3, len(ws))):
                    if lw[k] in STOP or _es_numero(ws[k]):
                        break
                    unidad.append(ws[k].strip(' .,;:!?'))
                    if len(unidad) == 1 and len(lw[k]) > 3:
                        break
                if not unidad and not re.search(r'[%$€£]', w):
                    continue
                out.append({'tipo': 'cifra', 'i': idx[j], 'fin_i': idx[min(j + len(unidad), len(idx) - 1)], 'frase': fi, 'puntos': 6.0,
                            'numero': _valor_numero(w), 'unidad': ' '.join(unidad).upper()})
        # nombres propios seguidos (no la primera palabra de la frase): «Pleasant Pond», «Casa Lomas»
        j = 1
        while j < len(ws):
            inicio_frase = re.search(r'[.?!…:]["”\')]*$', ws[j - 1]) or (float(palabras[idx[j]]['start']) - float(palabras[idx[j - 1]]['end'])) > 0.45
            if _capital(ws[j]) and lw[j] not in STOP and not inicio_frase:
                k = j
                while k + 1 < len(ws) and (_capital(ws[k + 1]) or (lw[k + 1] in ('de', 'del', 'la', 'of') and k + 2 < len(ws) and _capital(ws[k + 2]))):
                    k += 1
                nombre = ' '.join(w.strip(' .,;:!?') for w in ws[j:k + 1])
                prev = lw[j - 1] if j > 0 else ''
                out.append({'tipo': 'lugar' if prev in ('en', 'on', 'in', 'at', 'de', 'em', 'near', 'cerca') else 'nombre', 'i': idx[j], 'fin_i': idx[k],
                            'frase': fi, 'puntos': 4.0 + (k - j), 'texto': nombre})
                j = k + 1
            else:
                j += 1
        # listas: «X, Y y Z» (tres o más elementos cortos separados por comas)
        partes, actual = [], []
        for j, w in enumerate(ws):
            actual.append(j)
            if w.endswith(',') or (j + 1 < len(ws) and lw[j + 1] in ('y', 'and', 'e', 'o', 'or')):
                partes.append(actual)
                actual = []
        if actual:
            partes.append(actual)
        items = []
        for n_parte, parte in enumerate(partes):
            cont = [j for j in parte if lw[j] not in STOP]
            if len(cont) > 3 and n_parte > 0:                  # un trozo largo en medio no es un elemento: es otra frase («summer sunsets on your pontoon boat,»)
                items = []
                break
            if len(cont) > 3:                                  # «Nuestro chef prepara tacos de pescado,» → «tacos de pescado»
                cola = parte[-3:]
                while cola and lw[cola[0]] in STOP:
                    cola = cola[1:]
                cont = cola
            if 1 <= len(cont) <= 3:
                items.append(cont)
        pregunta = any('?' in w or '¿' in w for w in ws)
        items = [it for it in items if any(len(lw[j]) >= 4 and lw[j] not in STOP for j in it)]
        muletilla = ' '.join(lw[:2]) in ('a ver', 'o sea', 'pues bueno', 'you know', 'i mean')
        if len(items) >= 3 and len(partes) <= 6 and not pregunta and not muletilla:
            out.append({'tipo': 'lista', 'i': idx[items[0][0]], 'fin_i': idx[items[-1][-1]], 'frase': fi, 'puntos': 5.5,
                        'items': [{'texto': ' '.join(ws[j].strip(' .,;:!?') for j in it), 'i': idx[it[0]]} for it in items[:4]]})
        # palabras fuertes (pesos de la IA local, o la lista de énfasis): candidato a titular
        fuertes = [j for j, w in enumerate(lw) if (pesos.get(idx[j], 0) >= 0.72 or w in _ENFASIS or re.search(r'isim[oa]s?$', w)) and w not in STOP and len(w) > 2]
        if fuertes:
            j = max(fuertes, key=lambda j: (pesos.get(idx[j], 0.5), len(lw[j])))
            # el titular: la palabra fuerte y la de al lado si forman expresión («stunning water views» → «WATER VIEWS»)
            ini = j
            fin = j
            while fin + 1 < len(ws) and lw[fin + 1] not in STOP and fin - ini < 2 and not ws[fin].endswith(','):
                fin += 1
            out.append({'tipo': 'fuerte', 'i': idx[ini], 'fin_i': idx[fin], 'frase': fi, 'puntos': 3.0 + 3.0 * pesos.get(idx[j], 0.5),
                        'texto': ' '.join(w.strip(' .,;:!?') for w in ws[ini:fin + 1])})
        # parejas («Ana y Luis», también al empezar la frase) y presentaciones («soy Valeria», «me llamo…», «I'm…»)
        for j in range(len(ws) - 2):
            if _capital(ws[j]) and lw[j + 1] in ('y', '&', 'and', 'e') and _capital(ws[j + 2]):
                out.append({'tipo': 'pareja', 'i': idx[j], 'fin_i': idx[j + 2], 'frase': fi, 'puntos': 8.0,
                            'texto': ws[j].strip(' .,;:!?') + ' & ' + ws[j + 2].strip(' .,;:!?')})
        for j in range(len(ws) - 1):
            if (lw[j] in ('soy', "i'm", 'sou') or (j and lw[j - 1] in ('me', 'my') and lw[j] in ('llamo', 'name', 'chamo'))) and _capital(ws[j + 1]):
                k = j + 1 if lw[j] != 'name' else j + 2
                if k < len(ws) and _capital(ws[k]):
                    out.append({'tipo': 'presentacion', 'i': idx[k], 'fin_i': idx[k], 'frase': fi, 'puntos': 7.0, 'texto': ws[k].strip(' .,;:!?')})
        texto_frase = ' ' + ' '.join(lw) + ' '
        for g_frases in _FRASES_GENERO.values():
            for f in g_frases:
                if ' ' + f + ' ' in texto_frase:
                    toks = f.split()
                    for j in range(len(lw) - len(toks) + 1):
                        if lw[j:j + len(toks)] == toks:
                            out.append({'tipo': 'fuerte', 'i': idx[j], 'fin_i': idx[j + len(toks) - 1], 'frase': fi, 'puntos': 7.5,
                                        'texto': ' '.join(w.strip(' .,;:!?') for w in ws[j:j + len(toks)])})
                            break
        for j in range(len(ws) - 1):
            if lw[j] in ('escena', 'scene', 'toma', 'take', 'cena', 'tomada') and _es_numero(ws[j + 1]):
                out.append({'tipo': 'claqueta', 'i': idx[j], 'fin_i': idx[j + 1], 'frase': fi, 'puntos': 5.0,
                            'texto': f'{ws[j].strip(" .,;:!?").capitalize()} {_valor_numero(ws[j + 1])}'})
        # respaldo: lo último con contenido de la frase («… all about the windows» → «WINDOWS»), si no salió nada más fuerte
        if len(idx) >= 3 and not fuertes:
            cont = [j for j, w in enumerate(lw) if w not in STOP and len(w) > 3 and not _es_numero(ws[j])]
            if cont:
                fin = cont[-1]
                ini = fin - 1 if fin - 1 in cont and fin - 1 >= 0 and not ws[fin - 1].endswith(',') else fin
                out.append({'tipo': 'fuerte', 'i': idx[ini], 'fin_i': idx[fin], 'frase': fi, 'puntos': 2.0 + 2.0 * pesos.get(idx[fin], 0.4),
                            'texto': ' '.join(w.strip(' .,;:!?') for w in ws[ini:fin + 1])})
        # concepto con icono: la primera palabra de la frase que está en el mapa
        for j, w in enumerate(lw):
            if w in CONCEPTOS and len(w) > 2:
                out.append({'tipo': 'concepto', 'i': idx[j], 'fin_i': idx[j], 'frase': fi, 'puntos': 3.6, 'icono': CONCEPTOS[w],
                            'texto': ws[j].strip(' .,;:!?¡¿"\'')})
                break
        # pregunta al público («¿tú llevarías niños a tu boda…?»): las primeras palabras con contenido, hasta «o»
        if any(w.endswith('?') for w in ws) and len(ws) >= 4:
            ini = next((j for j, w in enumerate(ws) if w.startswith('¿')), 0)
            toks = list(range(ini, len(ws)))
            if toks and ws[toks[0]].lower().strip('¿?,.;:') in ('tú', 'you', 'você', 'vos'):
                toks = toks[1:]
            corte = next((n for n, j in enumerate(toks) if n >= 2 and lw[j] in ('o', 'or', 'ou')), min(len(toks), 5))
            toks = toks[:min(corte, 5)]
            if len(toks) >= 2:
                texto = ' '.join(ws[j].strip(' ¿?.,;:!') for j in toks)
                out.append({'tipo': 'pregunta', 'i': idx[toks[0]], 'fin_i': idx[toks[-1]], 'frase': fi, 'puntos': 6.0, 'texto': '¿' + texto + '?'})
        # llamada a la acción
        if any(w in _CTA for w in lw):
            out.append({'tipo': 'cta', 'i': idx[0], 'fin_i': idx[-1], 'frase': fi, 'puntos': 5.0, 'texto': ' '.join(ws)})
    return out


def huecos_sin_voz(palabras, duracion, minimo=2.4):
    """Tramos sin habla (B-roll, música): [(ini, fin)]."""
    out, prev = [], 0.0
    for p in palabras:
        s = float(p.get('start', 0))
        if s - prev >= minimo:
            out.append((prev + 0.25, s - 0.2))
        prev = max(prev, float(p.get('end', 0)))
    if duracion - prev >= minimo:
        out.append((prev + 0.25, duracion - 0.3))
    return out


def _cruza_corte(a, b, cortes):
    return any(a + 0.05 < c < b - 0.05 for c in (cortes or []))


def _mejor_tramo(a, b, cortes):
    """El trozo más largo de [a, b] que no cruza ningún corte."""
    puntos = [a] + [c for c in sorted(cortes or []) if a < c < b] + [b]
    mejor = max(zip(puntos, puntos[1:]), key=lambda x: x[1] - x[0])
    return mejor[0] + (0.06 if mejor[0] != a else 0), mejor[1] - (0.06 if mejor[1] != b else 0)


def _ajustar_a_corte(a, b, cortes):
    """Recorta [a, b] para que no cruce un corte (se queda con la parte que contiene a)."""
    for c in sorted(cortes or []):
        if a + 0.05 < c < b:
            return a, c - 0.06
    return a, b


# ------------------------------------------------------------------------------------------------------------------- plan
DENSIDAD = {'sobria': 6.5, 'media': 3.6, 'espectaculo': 2.0}        # segundos mínimos entre dos gráficos


def planificar(palabras, duracion, idioma='es', genero='auto', densidad='media', cortes=None, vertical=True, pesos=None, semilla=0, tema=None, video='',
               con_captions=True):
    """`con_captions` (GO con los Temas 1–4: siempre): los captions ya escriben lo que se dice, así que la PRO NO lo repite (ni titulares ni rótulos
    con las mismas palabras; esos momentos fuertes pasan a `plan['detras_pref']`: ahí los captions van detrás de la persona) y pone lo que los
    captions no dan: escenas de motion graphics e infografía (iconos, cifras, listas, lugares), con la persona recortada delante del fondo
    animado («fondo sustituido») o a pantalla completa, nombres, secciones, marcos y la ficha final."""
    palabras = unir_partidas([p for p in (palabras or []) if _txt(p) and p.get('start') is not None])
    # cortes: segundos sueltos o (segundo, fuerza) como los da efectos_visuales.detectar_cortes, o {'t': …}
    cortes = sorted(float(c['t'] if isinstance(c, dict) else c[0] if isinstance(c, (list, tuple)) else c) for c in (cortes or []))
    duracion = float(duracion or (float(palabras[-1]['end']) + 1.0 if palabras else 0.0))
    lang = idioma_de(idioma)
    puntos_genero = {}
    if genero in (None, '', 'auto'):
        genero, puntos_genero = detectar_genero(palabras)
    rng = random.Random(semilla_de(video, palabras, semilla))
    d = direccion(genero, rng, tema)
    g = d['genero']
    T = TEXTOS[lang]
    sep = DENSIDAD.get(densidad, 3.6)
    frases = frases_de(palabras)
    cands = candidatos(palabras, frases, pesos, lang)
    piezas, ocupado = [], []          # ocupado: [(ini, fin)] de los gráficos «grandes» (nunca dos a la vez)
    detras_pref = []                  # con captions: momentos fuertes (palabra remarcada, pregunta) en los que los captions van DETRÁS de la persona

    def libre(a, b, holgura=sep):
        return all(b + holgura * 0.35 <= x or a >= y + holgura * 0.35 for x, y in ocupado)

    def poner(p, grande=True):
        piezas.append(p)
        if grande:
            ocupado.append((p['ini'], p['fin']))

    def rel(t_abs, t0):
        return round(max(0.0, t_abs - t0), 3)

    def st(i):
        return float(palabras[i]['start'])

    # --- 1) la llamada a la acción (al final, si se pide algo) ---
    cta = next((c for c in reversed(cands) if c['tipo'] == 'cta' and st(c['i']) > duracion * 0.55), None)
    datos_cta = []
    # --- 1b) bodas y XV: los nombres primero («Ana & Luis», «Mis XV · Valeria»), detrás de la persona ---
    if g in ('boda', 'xv'):
        nombres = [c for c in cands if c['tipo'] in ('pareja', 'presentacion')] or [c for c in cands if c['tipo'] == 'nombre']
        if nombres:
            c = max(nombres, key=lambda c: (c['puntos'], -st(c['i'])))
            a = max(0.0, st(c['i']) - 0.2)
            b = min(duracion - 0.2, max(float(palabras[c['fin_i']]['end']) + 1.6, a + 3.2))
            a, b = _ajustar_a_corte(a, b, cortes)
            if b - a >= 1.6:
                partes = c['texto'].split(' & ')
                n1, n2 = (partes[0], partes[1]) if len(partes) > 1 else (c['texto'], '')
                conector = '&' if n2 else ({'es': 'Mis XV', 'pt': 'Meus 15', 'en': 'Sweet 15'}.get(lang, 'XV') if g == 'xv' else '')
                poner({'pieza': 'nombres', 'capa': 'detras', 'ini': a, 'fin': b, 'persona': True, 'ajustar': True, 'motivo': f"nombres «{c['texto']}»",
                       'valores': {'nombre1': n1, 'conector': conector, 'nombre2': n2, 'subtitulo': '', 'tiempos': '0.15,0.5,0.85,1.3', 'fuente': 'serif',
                                   'acento': d['acento'], 'colorTexto': d['colorTexto'], 'adorno': 'lineas', 'escala': 1.0, 'x': 50, 'y': d['yTitular']}})
                piezas.append({'pieza': 'velo', 'capa': 'velo', 'ini': a, 'fin': b, 'persona': True, 'motivo': 'velo de los nombres',
                               'valores': {'forma': 'vineta', 'color': '#000000', 'intensidad': d['veloIntensidad'], 'fundido': 0.45}})
                datos_cta.append(c['texto'])
    # --- 1c) el GANCHO con Magic Mask (skill: «iconos que le rodean»): los iconos de lo que se dice (y los del estilo) giran alrededor de la
    #         cabeza; la mitad de atrás pasa por DETRÁS de la persona recortada y la de delante, por delante. aplicar() la centra en su cabeza.
    if duracion >= 6.0:
        a, b = 0.15, min(duracion - 0.5, 0.15 + ORBITA_DUR)
        primero = [st(c['i']) for c in cands if c['tipo'] in ('cifra', 'lista') and st(c['i']) < a + ORBITA_DUR + 0.4]
        if primero:                                                   # un dato en los primeros segundos manda: la órbita acaba antes
            b = min(b, min(primero) - 0.45)
        a, b = _ajustar_a_corte(a, b, cortes)
        if b - a >= 1.6 and libre(a, b, 0.0):
            iconos = []
            for c in sorted((c for c in cands if c['tipo'] == 'concepto'), key=lambda c: st(c['i'])):
                if c['icono'] not in iconos:
                    iconos.append(c['icono'])
            for x in ICONOS_ORBITA[g]:
                if len(iconos) >= 5:
                    break
                if x not in iconos:
                    iconos.append(x)
            imgs = []
            for x in [ICONO_A_3D.get(i) for i in iconos] + ORBITA_3D[g]:
                if x and x not in imgs and len(imgs) < 5:
                    imgs.append(x)
            v = {'iconos': ','.join(iconos[:5]), 'imagenes': ','.join(imgs), 'acento': d['acento'], 'colorTexto': d['colorTexto'], 'x': 50, 'y': 30, 'rx': 22, 'ry': 4.5,
                 'inclinacion': rng.choice([-9, -6, 6, 9]), 'vueltas': round(rng.uniform(0.28, 0.36), 2), 'escala': 1.0, 'tiempos': '0'}
            poner({'pieza': 'orbita', 'capa': 'detras', 'ini': a, 'fin': b, 'persona': True, 'ajustar': True, 'motivo': 'gancho: órbita (atrás)',
                   'valores': dict(v, mitad='atras')})
            piezas.append({'pieza': 'orbita', 'capa': 'delante', 'ini': a, 'fin': b, 'ajustar': True, 'motivo': 'gancho: órbita (delante)',
                           'valores': dict(v, mitad='delante')})
    # --- 2) el gancho: el mejor candidato de los primeros segundos va DETRÁS de la persona ---
    orden = sorted(cands, key=lambda c: (-c['puntos'] - (2.5 if st(c['i']) < min(8.0, duracion * 0.25) else 0), st(c['i'])))
    titulares = 0
    ultima_escena = [-99.0]
    n_escenas = [0]
    iconos_usados = set()                 # una escena por concepto: «clientes» no sale dos veces en el mismo video
    cada_escena = ESCENA_CADA.get(densidad, 7.5)

    def escena(a, b, pieza, valores, motivo):
        """Un B-roll de motion graphics. Se alternan dos formas (la primera, la del Magic Mask): «fondo sustituido» (el fondo animado tapa la
        sala, la persona recortada queda DELANTE y la infografía va detrás de ella, encima de su cabeza o a un lado) y pantalla completa
        (el fondo tapa el video entero y la pieza va centrada). Sin persona en ese momento, aplicar() la deja centrada (pantalla completa)."""
        oscuro = '#' + ''.join('%02x' % int(int(d['acento'][k:k + 2], 16) * 0.28) for k in (1, 3, 5))
        con_persona = n_escenas[0] % 2 == 0
        n_escenas[0] += 1
        poner({'pieza': 'fondo', 'capa': 'fondo', 'ini': a if con_persona else a - 0.08, 'fin': b, 'pantalla': True, 'persona': con_persona,
               'motivo': ('fondo sustituido de ' if con_persona else 'fondo de ') + motivo,
               'valores': {'estilo': d['fondoEstilo'], 'entrada': d['fondoEntrada'], 'color1': d['acento'], 'color2': d['colorPanel'],
                           'color3': oscuro, 'intensidad': 0.8}})
        piezas.append({'pieza': pieza, 'capa': 'detras' if con_persona else 'delante', 'ini': a, 'fin': b, 'pantalla': True, 'persona': con_persona,
                       'ajustar': con_persona, 'motivo': motivo, 'valores': valores})
        ultima_escena[0] = a

    def puede_escena(a):
        return a >= 1.2 and a - ultima_escena[0] >= cada_escena

    for c in orden:
        if c['tipo'] in ('cta', 'pareja', 'presentacion') and not (c['tipo'] == 'presentacion' and g not in ('boda', 'xv')):
            continue
        a = st(c['i']) - 0.15
        fin_voz = float(palabras[c['fin_i']]['end'])
        if c['tipo'] in ('cifra',):
            b = min(duracion - 0.2, max(fin_voz + 1.6, a + 2.6))
        elif c['tipo'] == 'lista':
            b = min(duracion - 0.2, max(fin_voz + 2.0, a + 2.0 + 0.6 * len(c['items'])))
        else:
            b = min(duracion - 0.2, max(fin_voz + 1.4, a + 2.4))
        a, b = _ajustar_a_corte(a, b, cortes)
        if not libre(a, b):
            # se acorta para acabar antes del siguiente gráfico (sin pisar la voz de lo que enseña) en vez de perderlo
            despues = [x for x, y in ocupado if x > a]
            if despues:
                b = min(b, min(despues) - sep * 0.35 - 0.02)          # (0,02: que el redondeo no lo deje justo en el borde)
            if b < fin_voz + 0.5 or not libre(a, b):
                continue
        if b - a < 1.4:
            continue
        if cta and a >= st(cta['i']) - 1.0:
            continue
        if c['tipo'] == 'cifra' and puede_escena(a):
            datos_cta.append(f"{c['numero']} {c['unidad'].lower()}".strip())
            escena(a, b, 'cifra', {'numero': c['numero'], 'unidad': c['unidad'], 'etiqueta': '', 'tiempos': f"{rel(st(c['i']), a)},{rel(st(c['i']) + 0.3, a)},{rel(st(c['i']) + 0.6, a)}",
                                   'fuente': d['fuenteTexto'] if d['fuenteTexto'] != 'mono' else 'grotesk', 'acento': d['acento'], 'colorTexto': d['colorTexto'],
                                   'estilo': d['cifraEstilo'], 'escala': 1.15, 'x': 50, 'y': Y_ESCENA['cifra'] if vertical else 44}, f"cifra «{c['numero']} {c['unidad']}»")
        elif c['tipo'] == 'cifra':
            datos_cta.append(f"{c['numero']} {c['unidad'].lower()}".strip())
            poner({'pieza': 'cifra', 'capa': 'delante', 'ini': a, 'fin': b, 'ajustar': True, 'motivo': f"cifra «{c['numero']} {c['unidad']}»",
                   'valores': {'numero': c['numero'], 'unidad': c['unidad'], 'etiqueta': '', 'tiempos': f"{rel(st(c['i']), a)},{rel(st(c['i']) + 0.3, a)},{rel(st(c['i']) + 0.6, a)}",
                               'fuente': d['fuenteTexto'] if d['fuenteTexto'] != 'mono' else 'grotesk', 'acento': d['acento'], 'colorTexto': d['colorTexto'],
                               'estilo': d['cifraEstilo'], 'escala': 1.0, 'x': 50, 'y': d['yApoyo'] + 8}})
        elif c['tipo'] == 'lista' and puede_escena(a):
            items = c['items']
            ts = [rel(st(c['i']) - 0.2, a)] + [rel(st(it['i']), a) for it in items]
            datos_cta.extend(it['texto'] for it in items[:2])
            escena(a, b, 'lista', {'titulo': '', **{f'item{k + 1}': items[k]['texto'] if k < len(items) else '' for k in range(4)},
                                   'tiempos': ','.join(str(x) for x in ts), 'icono': d['icono'], 'disposicion': 'columna',
                                   'fuente': d['fuenteTexto'] if d['fuenteTexto'] != 'mono' else 'grotesk', 'acento': d['acento'], 'colorTexto': d['colorTexto'],
                                   'colorPanel': d['colorPanel'], 'escala': 1.1, 'x': 50, 'y': Y_ESCENA['lista'] if vertical else 42}, 'lista')
        elif c['tipo'] == 'lista':
            items = c['items']
            ts = [rel(st(c['i']) - 0.2, a)] + [rel(st(it['i']), a) for it in items]
            datos_cta.extend(it['texto'] for it in items[:2])
            poner({'pieza': 'lista', 'capa': 'delante', 'ini': a, 'fin': b, 'ajustar': True, 'motivo': 'lista',
                   'valores': {'titulo': '', **{f'item{k + 1}': items[k]['texto'] if k < len(items) else '' for k in range(4)},
                               'tiempos': ','.join(str(x) for x in ts), 'icono': d['icono'], 'disposicion': d['listaDisposicion'] if len(items) <= 4 else 'columna',
                               'fuente': d['fuenteTexto'] if d['fuenteTexto'] != 'mono' else 'grotesk', 'acento': d['acento'], 'colorTexto': d['colorTexto'],
                               'colorPanel': d['colorPanel'], 'escala': 1.0, 'x': 50, 'y': d['yApoyo'] + 8}})
        elif c['tipo'] == 'pregunta' and con_captions:
            detras_pref.append((a, b))                                # la pregunta la escriben los captions, detrás de la persona
            continue
        elif c['tipo'] == 'pregunta':
            pal = c['texto'].split()
            corte = max(1, (len(pal) + 1) // 2)
            l1, l2 = ' '.join(pal[:corte]), ' '.join(pal[corte:])
            if not l2:
                l1, l2 = '', l1
            ts2 = [rel(st(k), a) for k in range(c['i'], c['fin_i'] + 1)]
            poner({'pieza': 'rotulo', 'capa': 'delante', 'ini': a, 'fin': b, 'ajustar': True, 'motivo': 'pregunta al público',
                   'valores': {'linea1': l1, 'linea2': l2.upper(), 'acentoLinea': 2, 'tiempos': f"{ts2[0] if ts2 else 0},{ts2[min(corte, len(ts2) - 1)] if ts2 else 0.5}",
                               'fuente': d['fuenteTitular'], 'acento': d['acento'], 'colorTexto': d['colorTexto'], 'colorBloque': d['colorBloque'],
                               'escala': 1.0, 'x': 50, 'y': d['yApoyo'], 'inclinacion': 0}})
        elif c['tipo'] == 'lugar' and puede_escena(a) and (titulares >= 1 or con_captions):
            escena(a, b, 'icono', {'icono': 'pin', 'texto': c['texto'], 'kicker': T['ubicacion'], 'fuente': d['fuenteTitular'] if d['fuenteTitular'] != 'mono' else 'grotesk',
                                   'acento': d['acento'], 'colorTexto': d['colorTexto'], 'escala': 1.0, 'x': 50, 'y': Y_ESCENA['icono'] if vertical else 42,
                                   'tiempos': f"0,{rel(st(c['i']), a)}"}, f"lugar «{c['texto']}»")
        elif c['tipo'] == 'concepto':
            if not puede_escena(a) or c['icono'] in iconos_usados:
                continue
            iconos_usados.add(c['icono'])
            escena(a, b, 'icono', {'icono': c['icono'], 'imagen': ICONO_A_3D.get(c['icono'], ''), 'texto': c['texto'], 'kicker': '', 'fuente': d['fuenteTexto'] if d['fuenteTexto'] != 'mono' else 'grotesk',
                                   'acento': d['acento'], 'colorTexto': d['colorTexto'], 'escala': 1.0, 'x': 50, 'y': Y_ESCENA['icono'] if vertical else 42,
                                   'tiempos': f"0,{rel(st(c['i']), a)}"}, f"concepto «{c['texto']}»")
        elif c['tipo'] == 'claqueta':
            poner({'pieza': 'etiqueta', 'capa': 'delante', 'ini': a, 'fin': b, 'ajustar': True, 'motivo': f"claqueta «{c['texto']}»",
                   'valores': {'kicker': T['escena'] + ' · ' + T['toma'], 'texto': c['texto'], 'indice': '', 'icono': 'ninguno', 'alinear': d['etiquetaLado'],
                               'fuente': d['fuenteTexto'] if d['fuenteTexto'] != 'serif' else 'grotesk', 'acento': d['acento'], 'colorTexto': d['colorTexto'],
                               'escala': 1.0, 'x': 7 if d['etiquetaLado'] == 'izq' else 93, 'y': 22, 'tiempos': '0.1'}}, grande=False)
            ocupado.append((a, b))
        elif c['tipo'] in ('nombre', 'lugar', 'fuerte', 'presentacion'):
            texto = c['texto']
            nws = texto.split()
            if len(nws) > 4:
                continue
            ts = [rel(st(k), a) for k in range(c['i'], c['fin_i'] + 1)][:len(nws)]
            if c['tipo'] == 'lugar' and (titulares >= 1 or con_captions):
                poner({'pieza': 'etiqueta', 'capa': 'delante', 'ini': a, 'fin': b, 'ajustar': True, 'motivo': f'lugar «{texto}»',
                       'valores': {'kicker': T['ubicacion'], 'texto': texto, 'icono': 'pin', 'alinear': d['etiquetaLado'], 'fuente': d['fuenteTitular'],
                                   'acento': d['acento'], 'colorTexto': d['colorTexto'], 'escala': 1.0, 'x': 7 if d['etiquetaLado'] == 'izq' else 93,
                                   'y': 22, 'tiempos': str(ts[0] if ts else 0)}}, grande=False)
                ocupado.append((a, b))
                continue
            if con_captions:                                          # lo dicen los captions: ahí van DETRÁS de la persona (sin repetirlo)
                detras_pref.append((a, b))
                continue
            # titular gigante detrás de la persona (+ velo que apaga el fondo); máximo uno cada ~9 s. Variedad: a veces un rótulo
            # aunque cupiera otro titular (la semilla decide), para que dos videos no tengan la misma estructura
            if any(abs(a - p['ini']) < 9.0 for p in piezas if p['pieza'] == 'titular') or (titulares >= 1 and rng.random() < 0.3):
                # un rótulo en bloques en vez de otro titular
                if len(nws) <= 4 and g != 'boda':
                    fr = frases[c['frase']]
                    antes = [k for k in fr if k < c['i']]
                    comas = [n for n, k in enumerate(antes) if _txt(palabras[k]).endswith(',')]
                    if comas:
                        antes = antes[comas[-1] + 1:]
                    antes = antes[-3:]
                    while antes and plegar(_txt(palabras[antes[0]])) in STOP:
                        antes = antes[1:]
                    l1 = ' '.join(_txt(palabras[k]) for k in antes).strip(' ,.;:')
                    if len(antes) < 2:
                        l1, antes = '', antes
                    poner({'pieza': 'rotulo', 'capa': 'delante', 'ini': a, 'fin': b, 'ajustar': True, 'motivo': f'rótulo «{texto}»',
                           'valores': {'linea1': l1, 'linea2': texto.upper(), 'acentoLinea': 2,
                                       'tiempos': f"{rel(st(antes[0]), a) if l1 and antes else 0},{ts[0] if ts else 0}",
                                       'fuente': d['fuenteTitular'], 'acento': d['acento'], 'colorTexto': d['colorTexto'], 'colorBloque': d['colorBloque'],
                                       'escala': 1.0, 'x': 50, 'y': d['yApoyo'], 'inclinacion': 0}})
                continue
            lineas = ['', texto, ''] if len(nws) <= 2 else [' '.join(nws[:len(nws) // 2]), ' '.join(nws[len(nws) // 2:]), '']
            tam = '0.5,1,0.6' if len(nws) <= 2 else '1,1,0.6'
            poner({'pieza': 'titular', 'capa': 'detras', 'ini': a, 'fin': b, 'persona': True, 'ajustar': True, 'motivo': f'titular «{texto}»',
                   'valores': {'linea1': lineas[0], 'linea2': lineas[1], 'linea3': lineas[2], 'tamanos': tam, 'acentoLinea': 2 if len(nws) <= 2 else 2,
                               'tiempos': ','.join(str(x) for x in ts), 'fuente': d['fuenteTitular'], 'mayusculas': d['mayusculas'], 'acento': d['acento'],
                               'colorTexto': d['colorTexto'], 'entrada': d['entrada'], 'escala': 1.0, 'x': 50, 'y': d['yTitular'] if vertical else 30,
                               'ancho': 92, 'sombra': True}})
            piezas.append({'pieza': 'velo', 'capa': 'velo', 'ini': a, 'fin': b, 'persona': True, 'motivo': 'velo del titular',
                           'valores': {'forma': d['velo'], 'color': '#000000', 'intensidad': d['veloIntensidad'], 'fundido': 0.45}})
            titulares += 1
            if datos_cta == [] and c['tipo'] in ('lugar', 'nombre'):
                datos_cta.append(texto)
    # --- 3) los planos sin voz (B-roll, música): marco del estilo o etiqueta de sección numerada ---
    n_seccion = 0
    for a, b in huecos_sin_voz(palabras, duracion):
        a2, b2 = _mejor_tramo(a, b, cortes)
        b2 = min(b2, a2 + 5.5)
        if b2 - a2 < 1.8 or not libre(a2, b2, sep * 0.6):
            continue
        n_seccion += 1
        if g in ('bts',) or (g in ('boda', 'xv') and rng.random() < 0.5) or rng.random() < 0.15:
            poner({'pieza': 'marco', 'capa': 'delante', 'ini': a2, 'fin': b2, 'motivo': 'marco en plano sin voz',
                   'valores': {'estilo': d['marco'], 'texto': (f"{T['escena']} {n_seccion} · {T['toma']} {rng.randint(1, 4)}" if d['marco'] in ('visor', 'cinta') else ''),
                               'acento': d['acento'], 'colorTexto': d['colorTexto'], 'margen': 5, 'grosor': 1, 'tiempos': '0', 'tcInicio': round(a2, 2), 'fps': 30}})
        else:
            poner({'pieza': 'etiqueta', 'capa': 'delante', 'ini': a2, 'fin': b2, 'motivo': 'sección en plano sin voz',
                   'valores': {'kicker': '', 'texto': T['seccion'][g], 'indice': f'{n_seccion:02d}', 'icono': 'ninguno', 'alinear': d['etiquetaLado'],
                               'fuente': d['fuenteTitular'], 'acento': d['acento'], 'colorTexto': d['colorTexto'], 'escala': 1.0,
                               'x': 7 if d['etiquetaLado'] == 'izq' else 93, 'y': 74 if vertical else 82, 'tiempos': '0'}})
    # --- 5) la ficha final ---
    if cta:
        a = st(cta['i']) - 0.1
        b = duracion - 0.05
        if b - a >= 1.4:                                      # (al final del video la ficha puede ser corta: se queda en el último fotograma)
            nombre = (next((c['texto'] for c in cands if c['tipo'] == 'pareja'), '') or next((c['texto'] for c in cands if c['tipo'] == 'lugar'), '')
                      or next((c['texto'] for c in cands if c['tipo'] in ('nombre', 'presentacion')), '') or T['seccion'][g])
            filas = []
            for x in datos_cta:
                if x and x.lower() not in [f.lower() for f in filas] and x.lower() != nombre.lower():
                    filas.append(x[:1].upper() + x[1:])
            dicho = [w.strip(' .,;:!¡¿?') for w in cta['texto'].split()]
            boton = ' '.join(dicho) if 2 <= len(dicho) <= 6 and not con_captions else T['cta'][g]
            boton = boton[:1].upper() + boton[1:]
            piezas[:] = [p for p in piezas if not (p['ini'] < b and p['fin'] > a and p['capa'] != 'velo')]
            poner({'pieza': 'cta', 'capa': 'delante', 'ini': a, 'fin': b, 'ajustar': True, 'motivo': 'llamada a la acción',
                   'valores': {'kicker': T['kicker_cta'][g], 'titulo': nombre, 'fila1': filas[0] if len(filas) > 0 else '', 'fila2': filas[1] if len(filas) > 1 else '',
                               'fila3': filas[2] if len(filas) > 2 else '', 'boton': boton, 'tiempos': '0,0.25,0.5,0.75,1.0,1.35',
                               'fuente': d['fuenteTitular'], 'acento': d['acento'], 'colorTexto': d['colorTexto'], 'colorPanel': d['colorPanel'],
                               'escala': 1.0 if vertical else 0.8, 'x': 50 if vertical else 72, 'y': 32 if vertical else 50,
                               'icono': {'boda': 'corazon', 'xv': 'estrella'}.get(g, 'check')}})
    # --- 6) «modo error»: algo malo o una equivocación → el plano en gris un momento (no pisa escenas ni el principio) ---
    malas = set(_ERROR.get(lang, _ERROR['es']).split())
    gris = []
    for k, w in enumerate(palabras):
        t0 = st(k)
        if plegar(_txt(w)) not in malas or t0 < 1.5 or len(gris) >= GRIS_MAX or (gris and t0 - gris[-1][0] < GRIS_SEP):
            continue
        a, b = t0 - 0.08, min(duracion - 0.1, max(float(w['end']) + 1.1, t0 + 1.6), t0 + 2.6)
        if b - a >= 1.0 and not any(p['ini'] < b and a < p['fin'] and (p.get('pantalla') or p.get('persona')) for p in piezas):
            gris.append((round(a, 3), round(b, 3)))
    # quitar velos huérfanos y ordenar
    titulos = [(p['ini'], p['fin']) for p in piezas if p['pieza'] in ('titular', 'nombres')]
    piezas = [p for p in piezas if p['pieza'] != 'velo' or (p['ini'], p['fin']) in titulos]
    piezas.sort(key=lambda p: (p['ini'], {'fondo': 0, 'velo': 1}.get(p['capa'], 2)))
    for p in piezas:
        p['ini'], p['fin'] = round(max(0.0, p['ini']), 3), round(min(duracion, p['fin']), 3)
    cuenta = {}
    for p in piezas:
        cuenta[p['pieza']] = cuenta.get(p['pieza'], 0) + 1
    resumen = ', '.join(f'{n} {k}' for k, n in sorted(cuenta.items()))
    return {'version': 1, 'genero': g, 'genero_puntos': puntos_genero, 'idioma': lang, 'direccion': d, 'duracion': duracion,
            'piezas': piezas, 'detras_pref': [(round(a, 3), round(b, 3)) for a, b in detras_pref], 'gris': gris,
            'resumen': f'estilo {g}: {resumen}' if piezas else f'estilo {g}: sin gráficos'}
