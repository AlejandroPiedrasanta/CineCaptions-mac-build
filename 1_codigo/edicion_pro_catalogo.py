# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_catalogo.py — las 100 plantillas Remotion reutilizables de la Edición PRO, por ramas (bodas, XV y eventos sociales,
# fotografía y servicios, saludos y generales, negocio estilo SaaS).
"""
Cada plantilla: {'id', 'rama', 'comp' (composición de 1_codigo/remotion/src), 'props', 'dur' (s), 'frases' (lo que se dice y la dispara, plegado:
sin acentos ni mayúsculas), 'alto' (fracción del alto que ocupa, para colocarla sin tapar caras)}.

    PLANTILLAS                        la lista
    por_frase(palabras_plegadas)      [(índice de la palabra, plantilla)] de lo que se dice
    galeria(...)                      (herramientas_dev/galeria_remotion.py) renderiza una hoja de todas
"""
from __future__ import annotations

ALTO = {'Subtitulo': 0.15, 'Titulo': 0.24, 'Saludo': 0.26, 'Capitulos': 0.08, 'Fecha': 0.42, 'Pareja': 0.22, 'Pastilla': 0.06, 'Encuesta': 0.30, 'Comentario': 0.22,
        'Sesion': 0.22, 'Ninas': 0.2, 'Notificacion': 0.13, 'Tarjeta': 0.40, 'Grafica': 0.38, 'Pasos': 0.34, 'Interruptor': 0.11}
PLANTILLAS: list[dict] = []


def _p(id_, rama, comp, props, frases, dur=3.0):
    PLANTILLAS.append({'id': id_, 'rama': rama, 'comp': comp, 'props': props, 'dur': dur, 'frases': [f for f in frases if f], 'alto': ALTO.get(comp, 0.25)})


def _t(id_, rama, titulo, frases, kicker='', sub='', estilo='dorado', letra='script', adorno='lineas', sticker='', tarjeta=False):
    _p(id_, rama, 'Titulo', {'titulo': titulo, 'kicker': kicker, 'subtitulo': sub, 'estilo': estilo, 'letra': letra, 'adorno': adorno,
                             'sticker': sticker, 'tarjeta': tarjeta}, frases)


# ------------------------------------------------------------------------------------------------ bodas (32)
_t('boda_casa_novia', 'bodas', 'Casa de la novia', ['casa de la novia'], 'PREPARATIVOS', estilo='rosa', adorno='petalos', sticker='emoji:rose')
_t('boda_casa_novio', 'bodas', 'Casa del novio', ['casa del novio'], 'PREPARATIVOS', estilo='blanco', sticker='emoji:sparkles')
_t('boda_vestido', 'bodas', 'El vestido', ['el vestido', 'vestido de novia'], 'LA NOVIA', estilo='rosa', adorno='destellos', sticker='emoji:sparkles')
_t('boda_maquillaje', 'bodas', 'Maquillaje', ['maquillaje', 'peinado'], 'GLAM', estilo='rosa', adorno='destellos', sticker='emoji:sparkles')
_t('boda_anillos', 'bodas', 'Los anillos', ['los anillos', 'anillo', 'anillos'], 'DETALLES', estilo='dorado', adorno='destellos', sticker='emoji:gem_stone')
_t('boda_ceremonia', 'bodas', 'La ceremonia', ['la ceremonia', 'ceremonia'], 'EL GRAN DIA', estilo='dorado', sticker='emoji:white_heart')
_t('boda_acepto', 'bodas', 'Sí, acepto', ['acepto', 'si acepto'], 'EL MOMENTO', estilo='dorado', adorno='destellos', sticker='emoji:two_hearts')
_t('boda_votos', 'bodas', 'Los votos', ['los votos', 'votos'], 'PROMESAS', estilo='blanco', sticker='emoji:writing_hand')
_t('boda_beso', 'bodas', 'El primer beso', ['primer beso', 'el beso'], 'Y AHORA SÍ', estilo='rosa', adorno='petalos', sticker='emoji:face_blowing_a_kiss')
_t('boda_iglesia', 'bodas', 'La iglesia', ['la iglesia', 'iglesia'], 'CEREMONIA RELIGIOSA', estilo='dorado', sticker='emoji:white_heart')
_t('boda_civil', 'bodas', 'Boda civil', ['boda civil', 'el civil'], 'CEREMONIA', estilo='editorial', letra='serif', adorno='ninguno', tarjeta=True)
_t('boda_brindis', 'bodas', 'El brindis', ['el brindis', 'brindis', 'salud'], '¡SALUD!', estilo='dorado', adorno='destellos', sticker='emoji:clinking_glasses')
_t('boda_baile', 'bodas', 'El primer baile', ['primer baile'], 'LA PAREJA', estilo='lila', adorno='bokeh', sticker='emoji:musical_notes')
_t('boda_vals', 'bodas', 'El vals', ['el vals', 'vals'], 'LA PAREJA', estilo='dorado', adorno='bokeh', sticker='emoji:musical_note')
_t('boda_fiesta', 'bodas', 'La fiesta', ['la fiesta', 'fiesta'], 'QUE EMPIECE', estilo='noche', letra='sans', adorno='bokeh', sticker='emoji:party_popper')
_t('boda_recepcion', 'bodas', 'La recepción', ['recepcion', 'el banquete'], 'BIENVENIDOS', estilo='dorado', sticker='emoji:wine_glass')
_t('boda_pastel', 'bodas', 'El pastel', ['el pastel', 'pastel', 'la torta'], 'DULCE', estilo='rosa', sticker='emoji:birthday_cake')
_t('boda_ramo', 'bodas', 'El ramo', ['el ramo', 'ramo'], 'TRADICION', estilo='rosa', adorno='petalos', sticker='emoji:rose')
_t('boda_liga', 'bodas', 'La liga', ['la liga'], 'TRADICION', estilo='blanco', sticker='emoji:sparkles')
_t('boda_padrinos', 'bodas', 'Los padrinos', ['padrinos', 'los padrinos'], 'GRACIAS', estilo='dorado', sticker='emoji:folded_hands')
_t('boda_damas', 'bodas', 'Damas de honor', ['damas de honor', 'las damas'], 'LAS MEJORES', estilo='rosa', adorno='petalos', sticker='emoji:cherry_blossom')
_t('boda_familia', 'bodas', 'Fotos familiares', ['fotos familiares', 'la familia'], 'RECUERDOS', estilo='blanco', sticker='emoji:camera')
_t('boda_salida', 'bodas', 'La salida', ['la salida', 'salida de los novios'], 'RECIEN CASADOS', estilo='dorado', adorno='destellos', sticker='emoji:sparkles')
_t('boda_historia', 'bodas', 'Nuestra historia', ['nuestra historia', 'como se conocieron'], 'ASI EMPEZO', estilo='editorial', letra='serif', tarjeta=True)
_t('boda_preboda', 'bodas', 'Sesión preboda', ['preboda', 'pre boda'], 'ANTES DEL SI', estilo='rosa', sticker='emoji:camera')
_t('boda_recien', 'bodas', 'Recién casados', ['recien casados'], 'JUST MARRIED', estilo='blanco', adorno='destellos', sticker='emoji:two_hearts')
_p('boda_pareja', 'bodas', 'Pareja', {'nombre1': 'Ana', 'nombre2': 'Luis', 'texto': 'nuestra boda', 'estilo': 'dorado', 'sticker': 'emoji:gem_stone'}, [])
_p('boda_pareja_rosa', 'bodas', 'Pareja', {'nombre1': 'Ana', 'nombre2': 'Luis', 'texto': 'para siempre', 'estilo': 'rosa', 'sticker': 'emoji:two_hearts'}, [])
_p('boda_fecha', 'bodas', 'Fecha', {'dia': '25', 'mes': 'OCTUBRE', 'anio': '2026', 'texto': 'Save the date', 'estilo': 'dorado'}, ['save the date', 'reserva la fecha', 'nuestra fecha'], 3.4)
_p('boda_momento', 'bodas', 'Pastilla', {'texto': 'MOMENTO DEL DÍA', 'estilo': 'dorado', 'sticker': 'emoji:sparkles'}, ['momento del dia', 'el mejor momento'], 2.6)
_p('boda_esperado', 'bodas', 'Pastilla', {'texto': 'EL MOMENTO MÁS ESPERADO', 'estilo': 'rosa', 'sticker': 'emoji:red_heart'}, ['mas esperado', 'momento mas esperado'], 2.6)
_p('boda_capitulos', 'bodas', 'Capitulos', {'capitulos': 'Preparativos,Ceremonia,Fiesta,Baile', 'actual': 1, 'estilo': 'dorado'}, [], 3.0)
# ------------------------------------------------------------------------------------------------ XV y eventos sociales (24)
_t('xv_mis_xv', 'eventos', 'Mis XV', ['mis xv', 'mis quince', 'xv anos', 'quince anos'], 'CELEBRANDO', estilo='lila', adorno='destellos', sticker='emoji:crown')
_t('xv_quinceanera', 'eventos', 'La quinceañera', ['la quinceanera', 'quinceanera'], 'LA PRINCESA', estilo='rosa', adorno='destellos', sticker='emoji:crown')
_t('xv_vals', 'eventos', 'El vals', ['vals de xv', 'el vals'], 'MIS XV', estilo='lila', adorno='bokeh', sticker='emoji:musical_notes')
_t('xv_entrada', 'eventos', 'La entrada', ['la entrada', 'entrada'], 'ATENCION', estilo='dorado', adorno='destellos', sticker='emoji:sparkles')
_t('xv_sorpresa', 'eventos', 'La sorpresa', ['la sorpresa', 'sorpresa'], 'NO SE LO ESPERABA', estilo='noche', letra='sans', adorno='destellos', sticker='emoji:wrapped_gift')
_t('xv_zapatillas', 'eventos', 'Cambio de zapatillas', ['zapatillas', 'cambio de zapato'], 'TRADICION', estilo='rosa', sticker='emoji:sparkles')
_t('xv_muneca', 'eventos', 'La última muñeca', ['ultima muneca', 'la muneca'], 'TRADICION', estilo='rosa', sticker='emoji:teddy_bear')
_t('xv_corte', 'eventos', 'La corte de honor', ['corte de honor', 'chambelanes'], 'MIS XV', estilo='dorado', sticker='emoji:crown')
_t('xv_hora_loca', 'eventos', 'La hora loca', ['hora loca'], '¡A BAILAR!', estilo='noche', letra='sans', adorno='bokeh', sticker='emoji:partying_face')
_t('xv_show', 'eventos', 'El show', ['el show', 'show'], 'PREPARENSE', estilo='noche', letra='sans', adorno='destellos', sticker='emoji:sparkles')
_t('ev_baby_shower', 'eventos', 'Baby shower', ['baby shower'], 'BIENVENIDO BEBE', estilo='lila', adorno='bokeh', sticker='emoji:balloon')
_t('ev_bautizo', 'eventos', 'El bautizo', ['bautizo', 'bautismo'], 'BENDICIONES', estilo='blanco', sticker='emoji:smiling_face_with_halo')
_t('ev_comunion', 'eventos', 'Primera comunión', ['primera comunion'], 'UN DIA ESPECIAL', estilo='blanco', sticker='emoji:white_heart')
_t('ev_cumple', 'eventos', '¡Feliz cumpleaños!', ['cumpleanos', 'feliz cumple'], 'A CELEBRAR', estilo='noche', letra='sans', adorno='destellos', sticker='emoji:birthday_cake')
_t('ev_graduacion', 'eventos', 'Graduación', ['graduacion', 'me gradue', 'graduados'], 'LO LOGRAMOS', estilo='dorado', adorno='destellos', sticker='emoji:graduation_cap')
_t('ev_aniversario', 'eventos', 'Aniversario', ['aniversario'], 'AÑOS JUNTOS', estilo='dorado', sticker='emoji:two_hearts')
_t('ev_despedida', 'eventos', 'Despedida de soltera', ['despedida de soltera'], 'LAST NIGHT', estilo='rosa', letra='sans', adorno='destellos', sticker='emoji:party_popper')
_t('ev_posada', 'eventos', 'La posada', ['posada', 'navidad'], 'FELICES FIESTAS', estilo='dorado', adorno='destellos', sticker='emoji:glowing_star')
_p('ev_ninas', 'eventos', 'Ninas', {'texto': 'Las niñas', 'estilo': 'lila', 'sticker': 'emoji:unicorn'}, ['las ninas', 'ninas'], 2.8)
_p('ev_ninos', 'eventos', 'Ninas', {'texto': 'Los niños', 'estilo': 'esmeralda', 'sticker': 'emoji:balloon'}, ['los ninos', 'ninos'], 2.8)
_p('ev_amigas', 'eventos', 'Ninas', {'texto': 'Mis amigas', 'sub': 'las de siempre', 'estilo': 'rosa', 'sticker': 'emoji:heart_hands'}, ['mis amigas', 'las amigas'], 2.8)
_p('ev_damitas', 'eventos', 'Ninas', {'texto': 'Las damitas', 'estilo': 'rosa', 'sticker': 'emoji:butterfly'}, ['damitas'], 2.8)
_p('xv_capitulos', 'eventos', 'Capitulos', {'capitulos': 'Maquillaje,Ceremonia,Fiesta,El show', 'actual': 0, 'estilo': 'blanco'}, [], 3.0)
_p('xv_momento', 'eventos', 'Pastilla', {'texto': 'NO TE LO PIERDAS', 'estilo': 'lila', 'sticker': 'emoji:eyes'}, ['no te lo pierdas', 'atentos'], 2.6)
# ------------------------------------------------------------------------------------------------ fotografía y servicios (22)
_p('foto_sesion', 'fotografia', 'Sesion', {'titulo': 'Sesión fotográfica', 'kicker': 'BEHIND THE SCENES'}, ['sesion fotografica', 'sesion de fotos'])
_p('foto_bts', 'fotografia', 'Sesion', {'titulo': 'Detrás de cámaras', 'kicker': 'ASÍ SE HIZO', 'sticker': 'emoji:movie_camera'}, ['detras de camaras', 'detras de camara', 'behind the scenes'])
_p('foto_estudio', 'fotografia', 'Sesion', {'titulo': 'Sesión de estudio', 'kicker': 'EN EL ESTUDIO', 'sticker': 'emoji:light_bulb'}, ['estudio', 'sesion de estudio'])
_p('foto_preboda', 'fotografia', 'Sesion', {'titulo': 'Sesión preboda', 'kicker': 'LOVE STORY', 'estilo': 'rosa', 'sticker': 'emoji:two_hearts'}, ['sesion preboda'])
_p('foto_xv', 'fotografia', 'Sesion', {'titulo': 'Sesión de XV', 'kicker': 'MIS XV', 'estilo': 'lila', 'sticker': 'emoji:crown'}, ['sesion de xv', 'sesion de quince'])
_p('foto_locacion', 'fotografia', 'Sesion', {'titulo': 'La locación', 'kicker': 'DONDE TODO PASA', 'sticker': 'emoji:round_pushpin'}, ['la locacion', 'locacion', 'el lugar'])
_p('foto_equipo', 'fotografia', 'Sesion', {'titulo': 'El equipo', 'kicker': 'CON QUE GRABAMOS', 'sticker': 'emoji:movie_camera'}, ['el equipo', 'equipo'])
_p('foto_edicion', 'fotografia', 'Sesion', {'titulo': 'La edición', 'kicker': 'POSTPRODUCCIÓN', 'sticker': 'emoji:desktop_computer'}, ['edicion', 'editar', 'postproduccion'])
_p('foto_paquete_boda', 'fotografia', 'Tarjeta', {'kicker': 'PAQUETE', 'titulo': 'Boda completa', 'texto': 'Foto + video + dron', 'boton': 'Reservar', 'acento': '#C9A46A', 'icono3d': 'camera-dynamic-premium'}, ['paquete', 'paquetes', 'precio'], 3.4)
_p('foto_paquete_xv', 'fotografia', 'Tarjeta', {'kicker': 'PAQUETE', 'titulo': 'XV Premium', 'texto': 'Sesión + video + álbum', 'boton': 'Reservar', 'acento': '#B58CFF', 'icono3d': 'crown-dynamic-color'}, ['paquete de xv', 'xv premium'], 3.4)
_p('foto_express', 'fotografia', 'Tarjeta', {'kicker': 'SESIÓN EXPRESS', 'titulo': '30 minutos', 'texto': '15 fotos editadas', 'boton': 'Agendar', 'acento': '#3DDC97', 'icono3d': 'picture-dynamic-premium'}, ['sesion express', 'express'], 3.4)
_p('foto_reserva', 'fotografia', 'Tarjeta', {'kicker': 'AGENDA ABIERTA', 'titulo': 'Reserva tu fecha', 'texto': 'Quedan pocas fechas', 'progreso': 85, 'boton': 'Reservar', 'acento': '#FF8A3D', 'icono3d': 'calendar-dynamic-color'}, ['reserva tu fecha', 'agenda', 'reservar', 'aparta tu fecha'], 3.4)
_p('foto_pasos', 'fotografia', 'Pasos', {'pasos': 'Agenda,Sesión,Entrega', 'titulo': 'Así trabajamos', 'acento': '#FF8A3D'}, ['asi trabajamos', 'como trabajamos', 'el proceso'], 3.6)
_p('foto_pasos_boda', 'fotografia', 'Pasos', {'pasos': 'Llamada,Preboda,Tu boda,Álbum', 'titulo': 'Tu boda en 4 pasos', 'acento': '#C9A46A'}, ['pasos'], 3.6)
_p('foto_noti_reserva', 'fotografia', 'Notificacion', {'titulo': '¡Nueva reserva!', 'texto': 'Ana y Luis reservaron su fecha', 'icono3d': 'bell-dynamic-color', 'acento': '#5B8CFF'}, ['nueva reserva', 'reservaron'], 2.8)
_p('foto_noti_fotos', 'fotografia', 'Notificacion', {'titulo': 'Tus fotos están listas', 'texto': '120 fotos editadas · descárgalas', 'icono3d': 'picture-dynamic-premium', 'acento': '#3DDC97'}, ['fotos estan listas', 'entrega de fotos', 'entregamos'], 2.8)
_p('foto_noti_fecha', 'fotografia', 'Notificacion', {'titulo': 'Fecha confirmada', 'texto': 'Sábado 25 · 4:00 pm', 'icono3d': 'calendar-dynamic-premium', 'acento': '#FFB020'}, ['fecha confirmada', 'confirmado'], 2.8)
_p('foto_clientes', 'fotografia', 'Grafica', {'titulo': 'Parejas felices', 'valor': '+500', 'subtitulo': 'en 5 años', 'acento': '#F6A9C8'}, ['parejas felices', 'clientes felices'], 3.4)
_p('foto_reservas', 'fotografia', 'Grafica', {'titulo': 'Reservas', 'valor': '+240%', 'subtitulo': 'este año', 'acento': '#3DDC97'}, ['crecimos', 'reservas'], 3.4)
_p('foto_modo_boda', 'fotografia', 'Interruptor', {'texto': 'Modo boda', 'sub': 'activado', 'acento': '#F6A9C8'}, ['modo boda'], 2.4)
_p('foto_modo_fiesta', 'fotografia', 'Interruptor', {'texto': 'Modo fiesta', 'sub': 'activado', 'acento': '#22D3EE'}, ['modo fiesta'], 2.4)
_p('foto_capitulos', 'fotografia', 'Capitulos', {'capitulos': 'Llegada,Sesión,Edición,Entrega', 'actual': 1, 'estilo': 'blanco'}, [], 3.0)
# ------------------------------------------------------------------------------------------------ saludos y generales (22)
_p('hola_amigos', 'saludos', 'Saludo', {'linea1': '¡Hola', 'linea2': 'amigos!', 'estilo': 'rosa'}, ['hola amigos', 'hola amigas'], 2.6)
_p('hola_todos', 'saludos', 'Saludo', {'linea1': '¡Hola', 'linea2': 'a todos!', 'estilo': 'dorado'}, ['hola a todos', 'hola todos'], 2.6)
_p('hola_familia', 'saludos', 'Saludo', {'linea1': '¡Hola', 'linea2': 'familia!', 'estilo': 'lila'}, ['hola familia'], 2.6)
_p('bienvenidos', 'saludos', 'Saludo', {'linea1': '¡Bienvenidos', 'linea2': 'a mi canal!', 'estilo': 'noche', 'sticker': 'emoji:raising_hands'}, ['bienvenidos', 'bienvenidas'], 2.6)
_p('que_onda', 'saludos', 'Saludo', {'linea1': '¿Qué onda', 'linea2': 'gente?', 'estilo': 'esmeralda', 'sticker': 'emoji:sign_of_the_horns'}, ['que onda', 'que tal gente'], 2.4)
_p('hello', 'saludos', 'Saludo', {'linea1': 'Hey', 'linea2': 'friends!', 'estilo': 'rosa'}, ['hey friends', 'hello everyone', 'hi guys'], 2.4)
_t('hoy_estamos', 'saludos', 'Hoy estamos aquí', ['hoy estamos', 'estamos aqui'], 'HOY', estilo='blanco', letra='sans', adorno='destellos', sticker='emoji:round_pushpin')
_t('listos', 'saludos', '¿Listos?', ['listos', 'estan listos'], 'VAMOS', estilo='noche', letra='sans', adorno='destellos', sticker='emoji:fire')
_t('empezamos', 'saludos', 'Empezamos', ['empezamos', 'comenzamos', 'arrancamos'], 'EPISODIO 1', estilo='blanco', letra='sans', adorno='lineas', sticker='emoji:clapper_board')
_t('vamos_alla', 'saludos', '¡Vamos allá!', ['vamos alla', 'vamonos'], 'ACCION', estilo='esmeralda', letra='sans', adorno='destellos', sticker='emoji:rocket')
_t('gracias', 'saludos', 'Gracias', ['gracias por ver', 'muchas gracias'], 'POR VER', estilo='dorado', sticker='emoji:folded_hands')
_t('final', 'saludos', 'Nos vemos', ['nos vemos', 'hasta la proxima'], 'EN EL PROXIMO', estilo='blanco', letra='sans', sticker='emoji:waving_hand')
_p('encuesta_boda', 'saludos', 'Encuesta', {'pregunta': '¿Boda de día o de noche?', 'op1': 'De día', 'op2': 'De noche', 'pct1': 41}, ['dia o de noche'], 3.4)
_p('encuesta_ninos', 'saludos', 'Encuesta', {'pregunta': '¿Niños en tu boda?', 'op1': 'Sí, todos', 'op2': 'Mejor no', 'pct1': 58}, ['ninos a tu boda', 'llevarias ninos'], 3.4)
_p('encuesta_generica', 'saludos', 'Encuesta', {'pregunta': '¿Tú qué prefieres?', 'op1': 'Opción A', 'op2': 'Opción B', 'pct1': 64}, ['que prefieres'], 3.4)
_p('comenta_boda', 'saludos', 'Comentario', {'palabra': 'BODA', 'texto': 'Comenta', 'hecho': 'Te mando la info'}, ['comenta boda'], 3.6)
_p('comenta_xv', 'saludos', 'Comentario', {'palabra': 'XV', 'texto': 'Comenta', 'hecho': 'Te mando los paquetes'}, ['comenta xv'], 3.6)
_p('comenta_info', 'saludos', 'Comentario', {'palabra': 'INFO', 'texto': 'Comenta', 'hecho': 'Te escribo por DM'}, ['comenta info', 'comenta'], 3.6)
_p('comenta_fotos', 'saludos', 'Comentario', {'palabra': 'FOTOS', 'texto': 'Comenta', 'hecho': 'Te paso el link'}, ['comenta fotos'], 3.6)
_p('sigueme', 'saludos', 'Pastilla', {'texto': 'SÍGUEME PARA MÁS', 'estilo': 'noche', 'sticker': 'emoji:bell'}, ['sigueme', 'siguenos', 'suscribete'], 2.6)
_p('guarda', 'saludos', 'Pastilla', {'texto': 'GUÁRDALO PARA DESPUÉS', 'estilo': 'blanco', 'sticker': 'emoji:pushpin'}, ['guardalo', 'guarda este video'], 2.6)
_p('comparte', 'saludos', 'Pastilla', {'texto': 'COMPÁRTELO CON TU PAREJA', 'estilo': 'rosa', 'sticker': 'emoji:two_hearts'}, ['compartelo', 'comparte'], 2.6)

assert len(PLANTILLAS) == 100, len(PLANTILLAS)
assert len({p['id'] for p in PLANTILLAS}) == 100


def por_frase(plegadas):
    """[(índice de la primera palabra, plantilla)] de las frases disparadoras que aparecen en `plegadas` (palabras sin acentos, minúsculas).
    Gana la frase más larga en cada sitio («comenta boda» antes que «comenta»)."""
    frases = sorted(((f.split(), p) for p in PLANTILLAS for f in p['frases']), key=lambda x: -len(x[0]))
    out, usados = [], set()
    for i in range(len(plegadas)):
        if i in usados:
            continue
        for ws, p in frases:
            if plegadas[i:i + len(ws)] == ws:
                out.append((i, p))
                usados.update(range(i, i + len(ws)))
                break
    return out
