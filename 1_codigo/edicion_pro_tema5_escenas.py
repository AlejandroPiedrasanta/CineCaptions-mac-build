# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_tema5_escenas.py — el «director de escenas» del Tema 5: entiende de qué se habla y lo ILUSTRA en el momento exacto en que se
# dice, como el editor del video de referencia de la skill (skill videos/3 things - Edit v1 + SFX.mp4):
#   «harsh blacks, harsh whites and bright reds» → una muestra de color por cada uno, cuando se nombra · «25% smaller» → el icono se encoge con su
#   marco de selección y la etiqueta −25% · «visual effects / attention» → un ojo con tarjetas de interfaz · «effects» → la barra de uso de efectos ·
#   precios → tarjeta con la cifra que cuenta y su gráfica · crecer / seguidores / vistas → gráfica que sube · minutos / horas → reloj · clientes /
#   personas → avatares con contador · YouTube, TikTok… → fichas con su color · días → calendario · errores → tarjeta roja; lo correcto → verde ·
#   video / contenido / editar → el icono de reproducir · listas de cosas → fichas que van apareciendo.
"""
    escenas(bloques, dur) -> [{'ini', 'fin', 'prioridad', 'mitad': 'arriba'|'completa', 'disposicion': 'objeto'|'fila'|'fichas', 'objetos': [{'tipo', 't', …}],
                               'motivo'}]
Cada objeto lleva su `t` (segundos desde el inicio de la escena) = cuando se dice la palabra que lo trae. Las escenas se eligen después en
edicion_pro_tema5.planificar (prioridad, huecos, que no pisen los elementos en pantalla). Idiomas: español, inglés y portugués.
"""
import re
import unicodedata

# ------------------------------------------------------------------------------------------------------------------- vocabulario
COLORES = {  # palabra plegada -> (nombre de muestra, color vivo, color apagado)
    'black': ('BLACK', '#0B0B0D', '#2B2B30'), 'blacks': ('BLACK', '#0B0B0D', '#2B2B30'), 'negro': ('NEGRO', '#0B0B0D', '#2B2B30'),
    'negros': ('NEGRO', '#0B0B0D', '#2B2B30'), 'preto': ('PRETO', '#0B0B0D', '#2B2B30'), 'pretos': ('PRETO', '#0B0B0D', '#2B2B30'),
    'white': ('WHITE', '#FFFFFF', '#ECE9E2'), 'whites': ('WHITE', '#FFFFFF', '#ECE9E2'), 'blanco': ('BLANCO', '#FFFFFF', '#ECE9E2'),
    'blancos': ('BLANCO', '#FFFFFF', '#ECE9E2'), 'branco': ('BRANCO', '#FFFFFF', '#ECE9E2'), 'brancos': ('BRANCO', '#FFFFFF', '#ECE9E2'),
    'red': ('RED', '#FF2D2D', '#B5524B'), 'reds': ('RED', '#FF2D2D', '#B5524B'), 'rojo': ('ROJO', '#FF2D2D', '#B5524B'), 'rojos': ('ROJO', '#FF2D2D', '#B5524B'),
    'vermelho': ('VERMELHO', '#FF2D2D', '#B5524B'), 'blue': ('BLUE', '#1F5BFF', '#5B7290'), 'blues': ('BLUE', '#1F5BFF', '#5B7290'),
    'azul': ('AZUL', '#1F5BFF', '#5B7290'), 'azules': ('AZUL', '#1F5BFF', '#5B7290'), 'green': ('GREEN', '#18C964', '#6E8B6B'),
    'greens': ('GREEN', '#18C964', '#6E8B6B'), 'verde': ('VERDE', '#18C964', '#6E8B6B'), 'verdes': ('VERDE', '#18C964', '#6E8B6B'),
    'yellow': ('YELLOW', '#FFD400', '#C7B26A'), 'amarillo': ('AMARILLO', '#FFD400', '#C7B26A'), 'amarelo': ('AMARELO', '#FFD400', '#C7B26A'),
    'orange': ('ORANGE', '#FF7A00', '#C08A5B'), 'naranja': ('NARANJA', '#FF7A00', '#C08A5B'), 'laranja': ('LARANJA', '#FF7A00', '#C08A5B'),
    'pink': ('PINK', '#FF4FA3', '#C9939F'), 'rosa': ('ROSA', '#FF4FA3', '#C9939F'), 'purple': ('PURPLE', '#8B3DFF', '#7D6A93'),
    'morado': ('MORADO', '#8B3DFF', '#7D6A93'), 'roxo': ('ROXO', '#8B3DFF', '#7D6A93'), 'gray': ('GRAY', '#8E8E93', '#A5A29B'),
    'grey': ('GREY', '#8E8E93', '#A5A29B'), 'gris': ('GRIS', '#8E8E93', '#A5A29B'), 'cinza': ('CINZA', '#8E8E93', '#A5A29B'),
    'gold': ('GOLD', '#F2B705', '#C2A66B'), 'dorado': ('DORADO', '#F2B705', '#C2A66B'), 'dourado': ('DOURADO', '#F2B705', '#C2A66B'),
    'beige': ('BEIGE', '#E8D8BE', '#D9CCB6'), 'brown': ('BROWN', '#7A4A24', '#8A7462'), 'marron': ('MARRÓN', '#7A4A24', '#8A7462'),
    'cafe': ('CAFÉ', '#7A4A24', '#8A7462'), 'marrom': ('MARROM', '#7A4A24', '#8A7462'),
}
VIVO = {'harsh', 'bright', 'vivid', 'neon', 'loud', 'pure', 'brillante', 'brillantes', 'chillon', 'chillones', 'vivo', 'vivos', 'intenso', 'intensos',
        'fuerte', 'fuertes', 'puro', 'puros', 'forte', 'fortes', 'vibrante', 'vibrantes'}
APAGADO = {'dull', 'duller', 'muted', 'soft', 'pastel', 'apagado', 'apagados', 'suave', 'suaves', 'opaco', 'opacos', 'desaturado', 'sobrio', 'sobrios',
           'elegante', 'elegantes'}
MARCAS = {  # plataformas y marcas que se nombran: (cómo se escribe, color de la marca)
    'youtube': ('YouTube', '#FF0033'), 'tiktok': ('TikTok', '#111111'), 'instagram': ('Instagram', '#E1306C'), 'facebook': ('Facebook', '#1877F2'),
    'whatsapp': ('WhatsApp', '#25D366'), 'twitter': ('X', '#111111'), 'linkedin': ('LinkedIn', '#0A66C2'), 'spotify': ('Spotify', '#1DB954'),
    'netflix': ('NETFLIX', '#E50914'), 'google': ('Google', '#4285F4'), 'amazon': ('amazon', '#FF9900'), 'apple': ('Apple', '#111111'),
    'iphone': ('iPhone', '#111111'), 'android': ('Android', '#3DDC84'), 'chatgpt': ('ChatGPT', '#10A37F'), 'openai': ('OpenAI', '#111111'),
    'claude': ('Claude', '#D97757'), 'notion': ('Notion', '#111111'), 'canva': ('Canva', '#00C4CC'), 'capcut': ('CapCut', '#111111'),
    'davinci': ('DaVinci Resolve', '#E0473B'), 'premiere': ('Premiere Pro', '#9999FF'), 'photoshop': ('Photoshop', '#31A8FF'), 'figma': ('Figma', '#A259FF'),
    'shopify': ('Shopify', '#5E8E3E'), 'airbnb': ('Airbnb', '#FF5A5F'), 'uber': ('Uber', '#111111'), 'nike': ('NIKE', '#111111'), 'adidas': ('adidas', '#111111'),
    'rolex': ('ROLEX', '#006039'), 'chanel': ('CHANEL', '#111111'), 'dior': ('Dior', '#111111'), 'prada': ('PRADA', '#111111'), 'gucci': ('GUCCI', '#111111'),
    'cartier': ('Cartier', '#8B1A1A'), 'tiffany': ('TIFFANY&CO.', '#81D8D0'), 'zara': ('ZARA', '#111111'), 'tesla': ('TESLA', '#CC0000'),
    'cocacola': ('Coca-Cola', '#F40009'), 'mcdonalds': ("McDonald's", '#FFC72C'), 'starbucks': ('Starbucks', '#00704A'), 'samsung': ('SAMSUNG', '#1428A0'),
    'microsoft': ('Microsoft', '#737373'), 'paypal': ('PayPal', '#003087'), 'stripe': ('stripe', '#635BFF'), 'n8n': ('n8n', '#EA4B71'),
}
LUJO = {'luxury', 'luxurious', 'lujo', 'lujosas', 'lujosos', 'luxo', 'luxuosas', 'luxuosos', 'premium', 'highend', 'exclusivo', 'exclusivas', 'exclusivos'}
MARCAS_LUJO = ['rolex', 'chanel', 'dior', 'prada', 'cartier', 'tiffany']
DINERO = {'money', 'dollars', 'dollar', 'price', 'prices', 'cost', 'costs', 'revenue', 'sales', 'profit', 'income', 'salary', 'budget', 'paid', 'pay',
          'dinero', 'dolares', 'dolar', 'precio', 'precios', 'costo', 'costos', 'cuesta', 'ventas', 'ganancia', 'ganancias', 'ingresos', 'sueldo', 'salario',
          'presupuesto', 'pagar', 'pago', 'quetzales', 'pesos', 'euros', 'dinheiro', 'reais', 'preco', 'custo', 'vendas', 'lucro', 'renda'}
CRECER = {'grow', 'growth', 'grew', 'increase', 'increased', 'double', 'doubled', 'triple', 'followers', 'subscribers', 'scale', 'boost',
          'crecer', 'crecimiento', 'crece', 'crecio', 'aumentar', 'aumento', 'duplicar', 'duplique', 'triplicar', 'seguidores', 'suscriptores',
          'escalar', 'resultados', 'crescer', 'crescimento', 'aumentar', 'dobrar', 'visualizacoes', 'inscritos'}
TIEMPO = {'second': 1, 'seconds': 1, 'minute': 60, 'minutes': 60, 'mins': 60, 'hour': 3600, 'hours': 3600, 'day': 86400, 'days': 86400, 'week': 604800,
          'weeks': 604800, 'month': 2592000, 'months': 2592000, 'year': 31536000, 'years': 31536000, 'segundo': 1, 'segundos': 1, 'minuto': 60, 'minutos': 60,
          'hora': 3600, 'horas': 3600, 'dia': 86400, 'dias': 86400, 'semana': 604800, 'semanas': 604800, 'mes': 2592000, 'meses': 2592000, 'ano': 31536000,
          'anos': 31536000, 'anio': 31536000, 'anios': 31536000}
PERSONAS = {'clients', 'customers', 'people', 'followers', 'students', 'team', 'audience', 'users', 'members', 'subscribers', 'clientes', 'personas', 'gente',
            'alumnos', 'estudiantes', 'equipo', 'audiencia', 'usuarios', 'miembros', 'invitados', 'pessoas', 'alunos', 'equipe', 'publico'}
VIDEO = {'video', 'videos', 'content', 'reel', 'reels', 'edit', 'edits', 'editing', 'editor', 'editors', 'animation', 'animations', 'youtube', 'shorts', 'clip',
         'clips', 'film', 'contenido', 'edicion', 'ediciones', 'editar', 'editores', 'animacion', 'animaciones', 'conteudo', 'edicao', 'animacao'}
TAMANO = {'smaller': -1, 'small': -1, 'tiny': -1, 'shrink': -1, 'reduce': -1, 'oversizing': 1, 'oversized': 1, 'huge': 1, 'bigger': 1, 'big': 1, 'giant': 1,
          'pequeno': -1, 'pequenos': -1, 'pequenas': -1, 'mas pequeno': -1, 'reducir': -1, 'enorme': 1, 'enormes': 1, 'gigante': 1,
          'gigantes': 1, 'grande': 1, 'grandes': 1, 'menor': -1, 'maior': 1}
EFECTOS = {'effect', 'effects', 'efecto', 'efectos', 'efeito', 'efeitos', 'transitions', 'transiciones', 'filters', 'filtros'}
VISUAL = {'visual', 'visuals', 'attention', 'eye', 'eyes', 'atencion', 'ojo', 'ojos', 'mirada', 'visuales', 'atencao', 'olho', 'olhos'}
ERROR = {'mistake', 'mistakes', 'wrong', 'error', 'errors', 'amateur', 'fail', 'failure', 'avoid', 'errores', 'equivocado', 'evitar', 'erro', 'erros', 'errado'}
BIEN = {'correct', 'perfect', 'professional', 'success', 'correcto', 'perfecto', 'profesional', 'exito', 'certo', 'perfeito', 'profissional', 'sucesso'}
DIAS = {'monday': 'L', 'tuesday': 'M', 'wednesday': 'X', 'thursday': 'J', 'friday': 'V', 'saturday': 'S', 'sunday': 'D', 'lunes': 'L', 'martes': 'M',
        'miercoles': 'X', 'jueves': 'J', 'viernes': 'V', 'sabado': 'S', 'domingo': 'D', 'segunda': 'L', 'terca': 'M', 'quarta': 'X', 'quinta': 'J',
        'sexta': 'V', 'calendar': '', 'calendario': '', 'agenda': '', 'fecha': '', 'date': ''}
# v5.5.3: un % con estas palabras es un énfasis o una oferta («100 % gratuita», «50 % de descuento»), no una gráfica que crece
ENFASIS = {'gratis', 'gratuita', 'gratuito', 'gratuitas', 'gratuitos', 'free', 'gratuite', 'kostenlos', 'descuento', 'descuentos', 'off', 'discount',
           'desconto', 'rebaja', 'oferta', 'seguro', 'segura', 'garantizado', 'garantia', 'guaranteed', 'natural', 'real', 'original', 'puro', 'pura'}
MESES = set('''enero febrero marzo abril mayo junio julio agosto septiembre setiembre octubre noviembre diciembre january february march april may
june july august september october november december janeiro fevereiro marco maio junho julho setembro outubro novembro dezembro'''.split())
APP = {'app', 'apps', 'aplicacion', 'aplicaciones', 'aplicativo', 'celular', 'telefono', 'movil', 'phone', 'smartphone', 'iphone', 'android', 'instagram',
       'tiktok', 'youtube', 'whatsapp', 'facebook', 'notificacion', 'notificaciones', 'notification', 'notifications', 'telemovel', 'redes', 'social'}
# v5.5.3: lo que tiene que DECIRSE para que el objeto de la IA venga a cuento (un ojo en «nos vemos en el festival» no)
A_CUENTO = {'ojo': VISUAL, 'app': APP, 'avatares': PERSONAS | {'amigos', 'friends', 'comunidad', 'community', 'jovenes', 'seguidores', 'amigas'},
            'calendario': set(DIAS) | MESES}
CONECTORAS = set('''a al o u e y the and or of in on at to is it its as be by if so we my me i you your our de del la las el los lo un una unos unas en
con por para que se su sus es son era fue muy mas más pero ya le les nos te tu tus mi mis esto este esta eso ese esa this that these those there here
what how just more less do does did not no si an um uma os as do da dos das em na nos nas com pra ao from about into than always use'''.split())


def plegar(t):
    t = unicodedata.normalize('NFD', str(t).lower())
    return re.sub(r'[^a-z0-9%$]', '', ''.join(c for c in t if unicodedata.category(c) != 'Mn'))


def _cifra(texto):
    """'25%' -> ('25', '%') · '$1,200' -> ('1,200', '$') · '100' -> ('100', '') · None si no es una cifra."""
    m = re.match(r'^([$€£]?)(\d[\d.,]*)(%|k|K|M|x)?[.,!?]*$', str(texto).strip())
    if not m:
        return None
    return m.group(2).rstrip('.,'), (m.group(1) or m.group(3) or '')


# ------------------------------------------------------------------------------------------------------------------- detección
def escenas(bloques, dur):
    """Escenas candidatas a partir de los bloques [{'ini', 'fin', 'palabras': [{'texto', 't' (relativo)}]}]."""
    ps = [(b['ini'] + w['t'], plegar(w['texto']), w['texto'], n) for n, b in enumerate(bloques) for w in b['palabras']]
    out = []

    def ventana(t0, t1, mitad, disposicion, objetos, prioridad, motivo, minimo=2.2, maximo=6.0):
        a = max(0.05, t0 - 0.45)
        z = min(dur, max(t1 + 1.1, a + minimo), a + maximo)
        for o in objetos:
            o['t'] = round(max(0.12, o.pop('_t') - a), 3)
        out.append({'ini': round(a, 3), 'fin': round(z, 3), 'prioridad': prioridad, 'mitad': mitad, 'disposicion': disposicion, 'objetos': objetos,
                    'motivo': motivo})

    usados = set()
    # 1) colores: una muestra por color nombrado (con su adjetivo: «harsh» vivo · «dull» apagado), en los siguientes 7 s
    i = 0
    while i < len(ps):
        t, p, txt, nb = ps[i]
        if p in COLORES and i not in usados:
            grupo, j = [], i
            while j < len(ps) and ps[j][0] - t < 7.0 and len(grupo) < 4 and (not grupo or ps[j][0] - grupo[-1][0] < 3.0):
                if ps[j][1] in COLORES and ps[j][1] not in [g[1] for g in grupo]:
                    adj = ps[j - 1][1] if j > 0 else ''
                    nombre, vivo, apagado = COLORES[ps[j][1]]
                    tono = apagado if adj in APAGADO else vivo
                    etiqueta = ((ps[j - 1][2].strip('.,') + ' ') if adj in VIVO | APAGADO else '') + nombre.lower()
                    grupo.append((ps[j][0], ps[j][1], {'tipo': 'muestra', '_t': ps[j][0] - 0.15, 'color': tono, 'etiqueta': etiqueta.upper(), 'hex': tono.upper()}))
                    usados.add(j)
                j += 1
            if grupo:
                ventana(grupo[0][0], grupo[-1][0], 'arriba' if len(grupo) <= 3 else 'completa', 'fila', [g[2] for g in grupo], 3 + len(grupo) * 0.3,
                        'colores: ' + ', '.join(g[2]['etiqueta'] for g in grupo))
            i = j
            continue
        i += 1
    # 2) marcas y plataformas nombradas (o «marcas de lujo» → las de lujo), como fichas que van apareciendo alrededor de la frase
    i = 0
    while i < len(ps):
        t, p, txt, nb = ps[i]
        lujo = p in LUJO and any(ps[k][1] in ('brands', 'brand', 'marcas', 'marca') for k in range(i, min(i + 3, len(ps))))
        if p in MARCAS or lujo:
            fichas, j = [], i
            while j < len(ps) and ps[j][0] - t < 6.0:
                if ps[j][1] in MARCAS and ps[j][1] not in [f[1] for f in fichas]:
                    fichas.append((ps[j][0], ps[j][1]))
                j += 1
            if lujo and len(fichas) < 3:                                 # «las marcas de lujo…»: las de siempre, una tras otra mientras habla
                for k, m in enumerate(x for x in MARCAS_LUJO if x not in [f[1] for f in fichas]):
                    fichas.append((t + 0.25 + 0.38 * k, m))
                    if len(fichas) >= 6:
                        break
            if fichas:
                objetos = [{'tipo': 'ficha', '_t': f[0] - 0.1, 'texto': MARCAS[f[1]][0], 'color': MARCAS[f[1]][1],
                            'serif': f[1] in MARCAS_LUJO or lujo} for f in fichas]
                ventana(t, max(f[0] for f in fichas), 'completa', 'fichas', objetos, 3.2, 'marcas: ' + ', '.join(o['texto'] for o in objetos), minimo=3.0)
            i = j
            continue
        i += 1
    # 3) cifras: con su unidad (tiempo → reloj · dinero → tarjeta de precio · % con tamaño → el icono que se encoge · el resto → la cifra grande)
    for i, (t, p, txt, nb) in enumerate(ps):
        c = _cifra(txt)
        if c is None and p in ('one', 'two', 'three', 'five', 'ten', 'hundred', 'thousand', 'million', 'dos', 'tres', 'cinco', 'diez', 'cien', 'mil', 'millon'):
            continue
        if c is None:
            continue
        valor, signo = c
        sig = [ps[k] for k in range(i + 1, min(i + 4, len(ps)))]
        ant = [ps[k] for k in range(max(0, i - 4), i)]
        cerca = {x[1] for x in sig + ant}
        unidad = next((x for x in sig[:2] if x[1] in TIEMPO), None)
        tam = next((x for x in sig[:3] if x[1] in TAMANO), None)
        if not signo and sig and (sig[0][1] in ('percent', 'porciento', 'percento') or (sig[0][1] == 'por' and len(sig) > 1 and sig[1][1] == 'ciento')):
            signo = '%'                                                  # «25 percent», «25 por ciento»
        if not signo and tam and sig and sig[0][1] in TAMANO:
            signo = '%'                                                  # «25 smaller» (el % se perdió al transcribir)
        if unidad:
            ventana(t, unidad[0], 'arriba', 'objeto', [{'tipo': 'reloj', '_t': t - 0.1, 'valor': valor, 'unidad': unidad[2].strip('.,').lower()}], 3.6,
                    f'tiempo: {valor} {unidad[2]}')
        elif signo in ('$', '€', '£') or cerca & DINERO:
            ventana(t, t, 'arriba', 'objeto', [{'tipo': 'precio', '_t': t - 0.1, 'valor': valor, 'signo': signo if signo in ('$', '€', '£') else '$'}], 3.6,
                    f'dinero: {signo}{valor}')
        elif signo == '%' and tam:
            ventana(t, tam[0], 'arriba', 'objeto', [{'tipo': 'app', '_t': t - 0.3, 'escala': round(1 - min(60.0, float(valor.replace(',', '.'))) / 100.0, 3)
                                                     if TAMANO[tam[1]] < 0 else 1.0, 'insignia': ('−' if TAMANO[tam[1]] < 0 else '+') + valor + '%',
                                                     't_escala': round(tam[0] - t + 0.3, 3)}], 3.8, f'tamaño: {valor}% {tam[2]}')
        elif (signo == '%' and re.sub(r'\D', '', valor) != '100' and not cerca & ENFASIS) or cerca & CRECER:
            ventana(t, t, 'arriba', 'objeto', [{'tipo': 'grafica', '_t': t - 0.1, 'valor': valor, 'signo': signo}], 3.4, f'crecimiento: {valor}{signo}')
        else:
            etiqueta = next((x[2].strip('.,') for x in sig[:2] if x[1] not in CONECTORAS), '')
            ventana(t, t, 'arriba', 'objeto', [{'tipo': 'cifra', '_t': t - 0.1, 'valor': valor + signo, 'etiqueta': etiqueta}], 3.0, f'cifra: {valor}')
    # 4) conceptos sin cifra (una escena por concepto; la palabra la trae justo cuando se dice)
    def primero(conjunto, desde=0.0):
        return next(((t, p, txt) for t, p, txt, nb in ps if p in conjunto and t >= desde), None)

    for conj, objeto, pri, mitad, motivo in (
            (PERSONAS, lambda w: {'tipo': 'avatares', 'etiqueta': w[2].strip('.,').capitalize()}, 2.6, 'arriba', 'personas'),
            (CRECER, lambda w: {'tipo': 'grafica', 'valor': '', 'signo': ''}, 2.5, 'arriba', 'crecimiento'),
            (DINERO, lambda w: {'tipo': 'icono3d', 'icono': 'money-dynamic-premium'}, 2.4, 'arriba', 'dinero'),
            (EFECTOS, lambda w: {'tipo': 'barra', 'etiqueta': (w[2].strip('.,') + ' usage').upper() if w[1].startswith('effect') else ('uso de ' + w[2].strip('.,')).upper()}, 2.3, 'arriba', 'efectos'),
            (VISUAL, lambda w: {'tipo': 'ojo'}, 2.2, 'completa', 'lo visual'),
            (DIAS, lambda w: {'tipo': 'calendario', 'dia': DIAS.get(w[1], '')}, 2.2, 'arriba', 'calendario'),
            (VIDEO, lambda w: {'tipo': 'app'}, 1.8, 'arriba', 'video'),
            (ERROR, lambda w: {'tipo': 'estado', 'bien': False, 'etiqueta': w[2].strip('.,').upper()}, 1.6, 'arriba', 'error'),
            (BIEN, lambda w: {'tipo': 'estado', 'bien': True, 'etiqueta': w[2].strip('.,').upper()}, 1.5, 'arriba', 'bien')):
        desde = 0.0
        for _ in range(2):                                               # un concepto, una vez (dos si están muy separadas)
            w = primero(conj, desde)
            if w is None:
                break
            o = objeto(w)
            o['_t'] = w[0] - 0.1
            ventana(w[0], w[0], mitad, 'objeto', [o], pri, f'{motivo}: {w[2]}')
            desde = w[0] + 30.0
    return out


# ------------------------------------------------------------------------------------------------------------------- lo que propone la IA local
ICONO_IA = {'dinero': 'money-dynamic-premium', 'money': 'money-dynamic-premium', 'fuego': 'fire-front-color', 'fire': 'fire-front-color',
            'calendario': 'calendar-dynamic-premium', 'calendar': 'calendar-dynamic-premium', 'campana': 'bell-dynamic-color', 'bell': 'bell-dynamic-color',
            'anuncio': 'megaphone-dynamic-color', 'megafono': 'megaphone-dynamic-color', 'corazon': 'notify-heart-front-color', 'heart': 'notify-heart-front-color',
            'candado': 'lock-front-premium', 'lock': 'lock-front-premium', 'llave': 'key-front-premium', 'key': 'key-front-premium',
            'corona': 'crown-dynamic-color', 'crown': 'crown-dynamic-color', 'bandera': 'flag-dynamic-color', 'flag': 'flag-dynamic-color',
            'camara': 'camera-dynamic-premium', 'camera': 'camera-dynamic-premium', 'foto': 'picture-dynamic-premium', 'photo': 'picture-dynamic-premium',
            'viaje': 'travel-dynamic-color', 'travel': 'travel-dynamic-color', 'cartera': 'wallet-front-premium', 'wallet': 'wallet-front-premium'}
INTERROGATIVAS = {'que', 'como', 'cual', 'cuales', 'cuanto', 'cuanta', 'cuantos', 'cuando', 'donde', 'quien', 'porque', 'what', 'how', 'which', 'why',
                  'when', 'where', 'who', 'do', 'does', 'did', 'are', 'is', 'can', 'would', 'should', 'have', 'quem', 'qual', 'quanto', 'onde', 'sabias'}


def desde_ia(bloques, propuestas, dur):
    """Las escenas que propone la IA local (ia_texto.escenas), VALIDADAS contra lo que de verdad se dice: un dato que no está en la frase (o en
    la siguiente) se descarta, y con él la escena. Cada objeto entra en su «ancla» (la palabra en que se nombra). Mismo formato que escenas()."""
    out = []
    for e in propuestas or []:
        try:
            b = int(e.get('b'))
        except Exception:
            continue
        if not 0 <= b < len(bloques):
            continue
        tipo, datos = str(e.get('tipo') or ''), (e.get('datos') if isinstance(e.get('datos'), dict) else {})
        zona = bloques[b:b + 2]                                              # la frase y la siguiente
        pal = [(z['ini'] + w['t'], plegar(w['texto']), w['texto']) for z in zona for w in z['palabras']]
        dichas = {p for _t, p, _x in pal}

        secuencia = [p for _t, p, _x in pal]

        def igual(p, d):
            return p == d or (len(d) >= 4 and len(p) >= 4 and (p in d or d in p))

        def dicho(frase):
            """La frase se DICE tal cual: sus palabras seguidas y en orden (no sueltas por ahí: «more is less» no es «less is more»)."""
            ps = [plegar(x) for x in str(frase).split() if plegar(x)]
            if not ps:
                return False
            return any(all(igual(p, secuencia[i + k]) for k, p in enumerate(ps)) for i in range(len(secuencia) - len(ps) + 1))

        def momento(frase, defecto):
            ps = [plegar(x) for x in str(frase).split() if plegar(x)]
            for t, p, _x in pal:
                if ps and (p == ps[0] or (len(p) >= 4 and len(ps[0]) >= 4 and (p in ps[0] or ps[0] in p))):
                    return t
            return defecto

        t0 = bloques[b]['ini'] + 0.25
        anclas = [str(a) for a in e.get('anclas') or []]
        objetos, mitad, disp, motivo = [], 'arriba', 'objeto', f'IA: {tipo}'
        if tipo in ('lista', 'fichas'):
            items = [str(x).strip()[:28] for x in datos.get('items') or [] if str(x).strip()]
            items = [x for x in items if dicho(x)]
            if len(items) < (3 if tipo == 'fichas' else 2):
                continue                                                 # v5.5.3: dos fichas solas a pantalla completa = pantalla vacía
            if tipo == 'lista' and len(items) < 3 and not any(p in ('y', 'e', 'and', 'o', 'or', 'ou') for p in dichas):
                continue                                                 # «la ceremonia preciosa» no es una lista: hace falta «y» u «o», o 3 cosas
            if tipo == 'fichas':
                objetos = [{'tipo': 'ficha', '_t': momento(x, t0 + 0.4 * k) - 0.1, 'texto': x, 'color': '#1D1D21', 'serif': False} for k, x in enumerate(items[:6])]
                mitad, disp = 'completa', 'fichas'
            else:
                objetos = [{'tipo': 'lista', '_t': momento(items[0], t0) - 0.2, 'items': items[:5],
                            'tiempos': [round(momento(x, t0 + 0.5 * k) - momento(items[0], t0), 3) for k, x in enumerate(items[:5])]}]
            motivo += ': ' + ', '.join(items[:5])
        elif tipo == 'comparacion':
            a, z = str(datos.get('a') or '').strip()[:24], str(datos.get('b') or '').strip()[:24]
            if not (a and z and dicho(a) and dicho(z)) or sorted(plegar(x) for x in a.split()) == sorted(plegar(x) for x in z.split()):
                continue                                                 # (A y B no pueden ser las mismas palabras reordenadas)
            objetos = [{'tipo': 'comparacion', '_t': momento(a, t0) - 0.2, 'a': a.capitalize(), 'b': z.capitalize(), 't_b': round(momento(z, t0 + 0.8) - momento(a, t0), 3)}]
            motivo += f': {a} / {z}'
        elif tipo in ('cifra', 'precio', 'grafica', 'reloj'):
            valor = str(datos.get('valor') or '').strip()
            num = re.sub(r'[^\d.,]', '', valor)
            if not num or not any(re.sub(r'[^\d]', '', num) == re.sub(r'[^\d]', '', x) for _t, _p, x in pal if re.search(r'\d', x)):
                continue                                                     # la cifra tiene que DECIRSE (y con números: «three» lo cubren las reglas)
            if tipo == 'precio' and ('%' in valor or not (dichas & DINERO or any(s in x for _t, _p, x in pal for s in '$€£'))):
                continue                                                     # v5.5.3: «100 % gratuita» no es un precio de 100
            if tipo == 'grafica' and not dichas & CRECER and (re.sub(r'\D', '', num) == '100' or dichas & ENFASIS):
                continue                                                     # v5.5.3: ni una gráfica que crece
            o = {'tipo': tipo, '_t': momento(num, t0) - 0.1, 'valor': num}
            if tipo == 'cifra':
                o['valor'] = valor if re.search(r'\d', valor) else num
                o['etiqueta'] = str(datos.get('etiqueta') or '')[:24] if dicho(datos.get('etiqueta') or '') else ''
            elif tipo == 'precio':
                o['signo'] = str(datos.get('signo') or '$')[:2]
            elif tipo == 'grafica':
                o['signo'] = '%' if '%' in valor or str(datos.get('signo') or '') == '%' else ''
            else:
                unidad = str(datos.get('unidad') or '')
                if not dicho(unidad):
                    continue
                o['unidad'] = unidad[:14]
            objetos = [o]
            motivo += f': {valor}'
        elif tipo == 'muestras':
            colores = []
            for c in datos.get('colores') or []:
                k = next((plegar(x) for x in str(c).split() if plegar(x) in COLORES), None)
                if k and k in dichas and k not in [x[0] for x in colores]:
                    colores.append((k, str(c)))
            if not colores:
                continue
            for k, c in colores[:4]:
                nombre, vivo, apagado = COLORES[k]
                tono = apagado if any(plegar(x) in APAGADO for x in c.split()) else vivo
                objetos.append({'tipo': 'muestra', '_t': momento(k, t0) - 0.15, 'color': tono, 'etiqueta': c.upper()[:20], 'hex': tono.upper()})
            disp = 'fila'
            motivo += ': ' + ', '.join(c for _k, c in colores)
        elif tipo == 'pregunta':
            if not pal or pal[0][1] not in INTERROGATIVAS:
                continue                                                     # solo si la frase ES una pregunta
            opciones = [str(x)[:18] for x in datos.get('opciones') or [] if str(x).strip()][:3]
            if len(opciones) < 2:
                continue
            objetos = [{'tipo': 'pregunta', '_t': t0, 'pregunta': str(datos.get('pregunta') or '')[:60], 'opciones': opciones}]
        elif tipo == 'estado':
            if not anclas or not any(dicho(a) for a in anclas):
                continue
            objetos = [{'tipo': 'estado', '_t': momento(anclas[0], t0) - 0.1, 'bien': bool(datos.get('bien')), 'etiqueta': str(datos.get('etiqueta') or anclas[0]).upper()[:22]}]
        elif tipo in ('app', 'ojo', 'avatares', 'calendario'):
            if not anclas or not any(dicho(a) for a in anclas) or not (dichas & A_CUENTO[tipo]):
                continue
            o = {'tipo': tipo, '_t': momento(anclas[0], t0) - 0.1}
            if tipo == 'avatares':
                o['etiqueta'] = str(datos.get('etiqueta') or anclas[0]).capitalize()[:20]
            if tipo == 'calendario':
                o['dia'] = DIAS.get(plegar(datos.get('dia') or ''), '')
            if tipo == 'ojo':
                mitad = 'completa'
            objetos = [o]
        elif tipo == 'icono':
            icono = ICONO_IA.get(plegar(datos.get('concepto') or ''))
            if not icono or not anclas or not any(dicho(a) for a in anclas):
                continue
            objetos = [{'tipo': 'icono3d', '_t': momento(anclas[0], t0) - 0.1, 'icono': icono}]
        else:
            continue
        a = max(0.05, min(o['_t'] for o in objetos) - 0.45)
        fin = max(o['_t'] for o in objetos)
        z = min(dur, max(fin + 1.2, a + 2.4), a + 6.0)
        for o in objetos:
            o['t'] = round(max(0.12, o.pop('_t') - a), 3)
        out.append({'ini': round(a, 3), 'fin': round(z, 3), 'prioridad': 3.0, 'mitad': mitad, 'disposicion': disp, 'objetos': objetos, 'motivo': motivo})
    return out
