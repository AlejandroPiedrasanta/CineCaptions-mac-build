# CineCaptions · By Cinema Productions
# 1_codigo/motions_completo.py — v5.5.8 «Motions completo»: un video de SOLO motions a pantalla completa para TODO el video, tramo a tramo, que va
# en PRO-MOTIONS encima de todo (captions, efectos, Edición PRO). El usuario lo corta para que se vea su video debajo.
"""
motions_completo.py
-------------------
Pedido (2026-10-15): «la opción de solo motions para todo el video completo, por encima de todo, un video de solo motions relacionado al tema».
v5.5.9 (2026-10-16), el ESTILO REEL: «agarra el minuto 3:03–3:22 (los reels de «ChatGPT vs Claude Motion Graphics») con su audio y replícalo tal
cual para todas mis animaciones; nada de muñecos ni imágenes de referencia: ese estilo». Así que cada tramo (1,5–4 s, contiguos de 0 al final) es:

  · el FONDO lavanda claro de siempre (uno para todo el video) y el TITULAR fijo arriba, palabra a palabra cuando se dice, con la clave en cursiva
    serif azul, tachada en rojo (lo que se corta), en gris (lo aburrido), en píldora lavanda (la respuesta) o en un recuadro de selección;
  · UNA TARJETA de interfaz que es la metáfora de lo que se dice (Reel.tsx): grabar → visor REC · horas → reloj que corre · material → fotos que
    salen de la carpeta · encontrar → el clip elegido · cortar → línea de tiempo y tijeras · largo/aburrido → reproductor gris · la gente lo
    entiende → móvil y reacciones · lo que te dicen → el mensaje · otra versión → cartas A/B/C · ideas → la nube y los contadores; y los widgets
    claros (Widgets.tsx): contador (una cifra), ruta (pasos), órbita (3+ cosas), conectores (se integran), versiones (con nombre);
  · la transición de las referencias: lo que sale se va bajo un velo esmerilado y lo nuevo sube desde abajo con desenfoque y rebote.

Lo eligen las palabras de cada tramo (REEL) y, si hay IA local, ella (REEL_MENU, un motion por frase). Nunca la misma tarjeta dos veces seguidas.
Sin captions repetidos abajo ni la frase en tipografía (el titular ES lo que se dice). Sin fotos, videos de stock, muñecos ni piezas del kit neón.

    planificar(bloques, dur, idioma, perfil, video, vertical, ia, estado) -> props de la composición MotionsCompleto (Remotion)
    crear(bloques, dur, W, H, fps, carpeta, idioma, perfil, video, decir) -> ruta del .mp4 o None
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

MIN_S, MAX_S = 1.5, 4.0                     # duración de cada tramo (se juntan frases hasta MIN_S, sin pasar de MAX_S): el ritmo de los reels
VACIAS = set('''a al o u e y the and or of in on at to is it its as be by if so we my me i you your our de del la las el los lo un una unos unas en con
por para que se es son su sus mi mis tu tus muy mas más pero como este esta esto eso esa ese ya no si sí le les nos hay fue ser estar tiene tienen
para this that these those there here what when then than just very really also have has had was were are will would can could do does did not
your about from with they them their um eh ah oh ok okay así asi todo toda todos todas cada otro otra otros otras bien aquí aqui ahí ahi
también tambien desde hasta durante sobre entre sin donde cuando porque pues entonces vamos voy van vas va puede pueden hacer hace además ademas
luego antes ahora siempre nunca solo sólo mucho mucha muchos muchas poco poca thats youre youve ill im ive dont cant were theyre whats lets
its weve id hes shes isnt arent wont estas estan estamos habra habran sera seran puedes tienes quieres hay haber
uno una dos tres cuatro cinco seis siete ocho nueve diez cien one two three four five six seven eight nine ten'''.split())
NUMEROS = {'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10, 'cien': 100, 'mil': 1000,
           'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'hundred': 100, 'thousand': 1000}
_VERBO = ('ar', 'er', 'ir', 'ando', 'iendo', 'endo', 'ado', 'ido', 'aba', 'ía')
CONECTORES = {'a', 'hacia', 'para', 'entonces', 'luego', 'despues', 'porque', 'causa', 'lleva', 'llevan', 'convierte', 'convierten', 'hasta', 'genera',
              'to', 'into', 'then', 'because', 'leads', 'becomes', 'turns', 'causes', 'until', 'so'}
# v5.5.9 ESTILO REEL: las palabras (plegadas) que piden cada tarjeta de Reel.tsx
REEL = {
    'rec': 'grabar graba grabo grabas grabando grabamos grabes filmar filma filmando filmes camara camaras rodar rodaje grabacion directo record '
           'recording film filming camera shoot shooting live stream',
    'reloj': 'horas hora noche noches madrugada tiempo minutos dias semanas tardas tardar tardo pierdes perder perdiendo hours hour night nights time '
             'minutes days weeks late',
    'archivos': 'material archivos archivo clips fotos tomas grabaciones carpeta contenido subir sube subes dame mandame envia envias footage files '
                'folder upload uploads content',
    'buscar': 'encontrar encuentro encuentra encuentras buscar busca busco descubrir descubre elegir elijo elige seleccionar historia find search '
              'pick choose discover story',
    'cortar': 'cortar corta corto cortamos recortar recorta quitar quita quito quitamos eliminar elimina borrar borra sobra relleno silencios cut '
              'cuts trim remove delete rambling',
    'largo': 'largo larga largos largas aburrido aburrida aburridos aburridas lento lenta eterno eterna pesado pesada long boring slow endless',
    'movil': 'gente personas audiencia publico seguidores entiendan entienda entender entiende redes instagram tiktok youtube celular movil telefono '
             'vistas people audience understand followers phone viral views viewers',
    'chat': 'dice dices dicen decir dijo dijiste pregunta preguntas preguntan cliente clientes mensaje mensajes comentario comentarios piden pide say '
            'says said ask asks client clients message comment comments',
    'abc': 'version versiones opcion opciones alternativa alternativas diferente diferentes distinto distinta probar probemos probamos cambiar versions '
           'option options alternative different try',
    'ideas': 'ideas idea cabeza mente creatividad creativo creativa inspiracion imaginar imagina ocurre ocurren head mind creative creativity '
             'inspiration imagine',
    # v5.5.9, para cualquier tema (el reel de referencia solo hablaba de editar): las tarjetas de un evento, un negocio, una noticia…
    'fecha': 'fecha fechas calendario agenda lunes martes miercoles jueves viernes sabado domingo monday tuesday wednesday thursday friday saturday sunday enero febrero marzo abril mayo junio julio agosto septiembre setiembre octubre noviembre diciembre january february march april may june july august september october november december date calendar tomorrow tonight',
    'lugar': 'lugar lugares direccion ubicacion centro ciudad parque plaza calle avenida salon estadio teatro restaurante tienda sucursal place '
             'location address city park street venue store restaurant',
    'entrada': 'gratis gratuita gratuito gratuitas gratuitos entrada entradas boleto boletos precio precios cuesta cuestan pagar pago descuento oferta '
               'ofertas promocion quetzales dolares pesos euros free ticket tickets price cost discount offer sale',
    'personas': 'influencers jovenes amigos amigas equipo invitados invitadas artistas gamers comunidad emprendedores creadores familia ninos ninas '
                'mujeres hombres heroes participantes friends team guests artists community creators family kids',
    'musica': 'musica musical concierto conciertos banda bandas dj cancion canciones ritmo cantante cantantes music concert concerts band bands song '
              'songs singer playlist',
    'premio': 'premio premios ganar gana ganas ganador ganadores torneo concurso trofeo beca becas sorteo reconocimiento campeonato prize prizes win '
              'winner tournament contest award awards scholarship giveaway',
    'compartir': 'comparte compartir compartelo envia envialo enviale guarda guardalo guardar suscribete sigueme siguenos etiqueta share save '
                 'subscribe follow send tag',
    # v5.5.9, contra la repetición (el usuario: «repite mucho»): más tarjetas para lo que se dice a menudo
    'lista': 'consejos tips trucos cosas necesitas necesitan requisitos tareas pendientes lista checklist claves things need tricks requirements',
    'buscador': 'google internet web online pagina sitio navegador buscador search googling website',
    'post': 'like likes publicacion publicaciones publicar publica post posts reel reels engagement alcance perfil',
    'encuesta': 'vota votar votacion encuesta prefieres opinas opinion poll vote prefer',
    'carga': 'cargando carga progreso avance casi listo termina terminar completar completo loading progress almost done finish complete',
    'nota': 'recuerda recuerden importante ojo nota apunta anota secreto remember important note secret',
    'antesdespues': 'antes despues transformacion resultado resultados mejora mejoro before after transformation result results improve',
    'cuenta': 'faltan quedan pronto lanzamiento estreno countdown soon launch coming',
    'grafica': 'crecer crece crecimiento ventas aumenta aumentar sube subir duplica triplica crecio estadisticas growth grow sales increase double stats',
}
REEL = {k: set(v.split()) for k, v in REEL.items()}
# las tarjetas que llevan un FOTOGRAMA del video del usuario (el que se ve mientras se dice; no son fotos de internet)
CON_FOTO = {'movil', 'buscar', 'rec', 'largo', 'post', 'antesdespues'}
# las generales (si nada encaja): van rotando, con tope y descanso
GENERALES = ('aviso', 'chat', 'buscar', 'lista', 'nota', 'post')
PALETAS = ('azul', 'naranja', 'morado', 'verde', 'rosa')
DIAS = set('lunes martes miercoles jueves viernes sabado domingo monday tuesday wednesday thursday friday saturday sunday'.split())
MESES = set('enero febrero marzo abril mayo junio julio agosto septiembre setiembre octubre noviembre diciembre january february march april may june july august september october november december'.split())
GRATIS = {'gratis', 'gratuita', 'gratuito', 'gratuitas', 'gratuitos', 'free'}
MONEDA = {'quetzales': 'Q', 'quetzal': 'Q', 'dolares': '$', 'dolar': '$', 'pesos': '$', 'euros': '€', 'euro': '€', 'dollars': '$', 'bucks': '$'}
GRIS = {'aburrido', 'aburrida', 'aburridos', 'aburridas', 'lento', 'lenta', 'pesado', 'pesada', 'eterno', 'eterna', 'boring', 'slow', 'endless'}
DECIR = {'dice', 'dices', 'dicen', 'decir', 'dijo', 'dijiste', 'pide', 'piden', 'pregunta', 'preguntan', 'say', 'says', 'said', 'ask', 'asks'}
# para la IA local (modo denso: un motion por frase): qué tarjeta va en cada frase y su palabra clave (DICHA)
_P = '{"palabra": "…" (la palabra clave, DICHA tal cual)}'
REEL_MENU = {
    'rec': ('se habla de grabar, filmar, la cámara, salir en video o en directo', _P),
    'reloj': ('el tiempo que se pierde o se tarda: horas, noches, días, hacerse tarde', _P),
    'archivos': ('archivos, material, clips, fotos o contenido que se entrega o se sube', _P),
    'buscar': ('encontrar, elegir o descubrir lo mejor: la historia, la idea, el momento', _P),
    'cortar': ('cortar, quitar, recortar o eliminar lo que sobra', '{"palabra": "…" (lo que se corta, DICHO)}'),
    'largo': ('algo largo, lento, aburrido o pesado', _P),
    'movil': ('la gente, el público o los seguidores que lo ven, lo entienden o reaccionan; las redes', _P),
    'chat': ('lo que alguien dice, pregunta o pide: una cita, un cliente, un comentario', _P),
    'abc': ('otra versión, opciones, alternativas, probar algo distinto, la respuesta «sí, se puede»', _P),
    'ideas': ('muchas ideas, la cabeza, la creatividad, tener más de lo que cabe', _P),
    'fecha': ('una fecha, un día o una hora: cuándo pasa algo', _P),
    'lugar': ('un lugar, una dirección, una ciudad: dónde pasa algo', _P),
    'entrada': ('un precio, algo gratis, una entrada, una oferta', _P),
    'personas': ('personas o grupos que se nombran: invitados, artistas, el equipo, los amigos', _P),
    'musica': ('música, conciertos, bandas, canciones', _P),
    'premio': ('un premio, ganar, un torneo, un concurso, una beca', _P),
    'compartir': ('pide compartir, guardar, enviar, seguir o suscribirse', _P),
    'aviso': ('una noticia o un anuncio importante (si nada más encaja)', _P),
    'lista': ('varias cosas, consejos o requisitos que se enumeran', _P),
    'buscador': ('buscar en internet, una página web, google', _P),
    'post': ('una publicación, likes, el perfil, las redes', _P),
    'encuesta': ('una pregunta con opciones, votar, qué prefieres', _P),
    'carga': ('algo que avanza o casi termina: un proceso, un progreso', _P),
    'nota': ('algo importante para recordar, un secreto, «ojo»', _P),
    'antesdespues': ('un antes y un después, un cambio, un resultado', _P),
    'cuenta': ('lo que falta para algo: pronto, un lanzamiento, una cuenta atrás', _P),
    'grafica': ('algo que crece o sube: ventas, números, estadísticas', _P),
}
# los textos fijos de las tarjetas por idioma (lo demás sale de lo que se dice)
TEXTOS = {
    'es': dict(reloj='Todavía editando…', material='Material', material_sub='47 clips · 3 h 12 min', linea='Línea de tiempo', duracion='2 h 47 min',
               movil=('Tu historia,', 'por fin.', 'Clara, corta y que vale la pena ver.', 'Ver ahora', 'Vista completa'), cliente=('Cliente', 'ahora mismo'),
               responder='Responder', abc=['Directa', 'Con historia', 'Minimal'], nueva='Nueva versión', version='VERSIÓN', ideas='Ideas de video',
               dia=('24 h', 'en un día'),
               calendario='Añadir al calendario', fecha_txt='FECHA', llegar='Cómo llegar', entrada='Entrada', gratis='GRATIS', vivo='En vivo', musica='Sonando ahora', compartir='Compartir', enviado='Enviado', ahora='ahora', premio='Premio',
               antes='Antes', despues='Después', megusta='me gusta', cargando='Cargando…', si_no=('Sí', 'No'), cuenta=('días', 'horas', 'min'), usuario='tu_marca'),
    'en': dict(reloj='Still editing…', material='Raw footage', material_sub='47 clips · 3h 12m', linea='Timeline', duracion='2h 47m',
               movil=('Your story,', 'finally.', 'Tight, clear, and actually worth watching.', 'Watch now', 'Watch-through'), cliente=('Client', 'just now'),
               responder='Reply', abc=['Punchy cut', 'Story-first', 'Minimal'], nueva='New version', version='VERSION', ideas='Video ideas',
               dia=('24 hrs', 'In a day'),
               calendario='Add to calendar', fecha_txt='DATE', llegar='Directions', entrada='Ticket', gratis='FREE', vivo='Live', musica='Now playing', compartir='Share', enviado='Sent', ahora='now', premio='Prize',
               antes='Before', despues='After', megusta='likes', cargando='Loading…', si_no=('Yes', 'No'), cuenta=('days', 'hrs', 'min'), usuario='your_brand'),
    'pt': dict(reloj='Ainda editando…', material='Material bruto', material_sub='47 clipes · 3 h 12 min', linea='Linha do tempo', duracion='2 h 47 min',
               movil=('Sua história,', 'finalmente.', 'Clara, curta e que vale a pena ver.', 'Ver agora', 'Vista completa'), cliente=('Cliente', 'agora'),
               responder='Responder', abc=['Direta', 'Com história', 'Minimal'], nueva='Nova versão', version='VERSÃO', ideas='Ideias de vídeo',
               dia=('24 h', 'em um dia'),
               calendario='Adicionar à agenda', fecha_txt='DATA', llegar='Como chegar', entrada='Ingresso', gratis='GRÁTIS', vivo='Ao vivo', musica='Tocando agora', compartir='Compartilhar', enviado='Enviado', ahora='agora', premio='Prêmio',
               antes='Antes', despues='Depois', megusta='curtidas', cargando='Carregando…', si_no=('Sim', 'Não'), cuenta=('dias', 'horas', 'min'), usuario='sua_marca'),
    'fr': dict(reloj='Toujours en montage…', material='Rushes', material_sub='47 clips · 3 h 12 min', linea='Timeline', duracion='2 h 47 min',
               movil=('Ton histoire,', 'enfin.', 'Claire, courte et qui vaut le coup.', 'Regarder', 'Vue complète'), cliente=('Client', "à l'instant"),
               responder='Répondre', abc=['Directe', 'Histoire', 'Minimal'], nueva='Nouvelle version', version='VERSION', ideas='Idées de vidéo',
               dia=('24 h', 'par jour'),
               calendario='Ajouter au calendrier', fecha_txt='DATE', llegar='Itinéraire', entrada='Billet', gratis='GRATUIT', vivo='En direct', musica='En écoute', compartir='Partager', enviado='Envoyé', ahora='maintenant', premio='Prix',
               antes='Avant', despues='Après', megusta='j’aime', cargando='Chargement…', si_no=('Oui', 'Non'), cuenta=('jours', 'h', 'min'), usuario='ta_marque'),
    'de': dict(reloj='Immer noch am Schneiden…', material='Rohmaterial', material_sub='47 Clips · 3 Std 12 Min', linea='Timeline', duracion='2 Std 47 Min',
               movil=('Deine Story,', 'endlich.', 'Klar, kurz und sehenswert.', 'Ansehen', 'Komplett gesehen'), cliente=('Kunde', 'gerade eben'),
               responder='Antworten', abc=['Direkt', 'Story', 'Minimal'], nueva='Neue Version', version='VERSION', ideas='Videoideen',
               dia=('24 Std', 'am Tag'),
               calendario='Zum Kalender', fecha_txt='DATUM', llegar='Route', entrada='Ticket', gratis='GRATIS', vivo='Live', musica='Läuft gerade', compartir='Teilen', enviado='Gesendet', ahora='jetzt', premio='Preis',
               antes='Vorher', despues='Nachher', megusta='Likes', cargando='Lädt…', si_no=('Ja', 'Nein'), cuenta=('Tage', 'Std', 'Min'), usuario='deine_marke'),
    'it': dict(reloj='Ancora a montare…', material='Girato', material_sub='47 clip · 3 h 12 min', linea='Timeline', duracion='2 h 47 min',
               movil=('La tua storia,', 'finalmente.', 'Chiara, breve e da guardare.', 'Guarda ora', 'Visione completa'), cliente=('Cliente', 'adesso'),
               responder='Rispondi', abc=['Diretta', 'Con storia', 'Minimal'], nueva='Nuova versione', version='VERSIONE', ideas='Idee video',
               dia=('24 h', 'al giorno'),
               calendario='Aggiungi al calendario', fecha_txt='DATA', llegar='Indicazioni', entrada='Biglietto', gratis='GRATIS', vivo='Dal vivo', musica='In riproduzione', compartir='Condividi', enviado='Inviato', ahora='ora', premio='Premio',
               antes='Prima', despues='Dopo', megusta='mi piace', cargando='Caricamento…', si_no=('Sì', 'No'), cuenta=('giorni', 'ore', 'min'), usuario='il_tuo_brand'),
}
# lo que vale cada tarjeta (lo de la IA suma; lo general, si no hay otra cosa, poco)
PESO = {'reel': 9.0, 'reel_ia': 8.0, 'general': 3.0, 'golpe': 6.8, 'sigue': 4.6}                # la IA pequeña se equivoca: manda donde las palabras no piden nada
# v5.5.9, los WIDGETS (referencias: los reels de «ChatGPT vs Claude Motion Graphics» 3:04–3:22, Tidio, «Smart Navigation», el panel de reservas)
SECUENCIA = set('''primero primera segundo segunda tercero tercera luego despues proceso paso pasos camino ruta destino llegar llega llegamos
etapa etapas fase fases first then next step steps route journey process stage'''.split())
OPCIONES = set('''opcion opciones version versiones elegir elige escoger escoge alternativa alternativas plan planes estilo estilos paquete paquetes
option options versions choose pick plans'''.split())
CONECTA = set('''conecta conectar conectamos integra integrar integramos automatiza automatizar automatico automatica plataforma sistema herramientas
canales connect integrate automate platform system channels tools'''.split())
UNIDAD = {'horas': 'h', 'hora': 'h', 'h': 'h', 'minutos': ' min', 'min': ' min', 'segundos': ' s', 'dias': ' días', 'semanas': ' sem', 'meses': ' meses',
          'anos': ' años', 'porciento': '%', 'mil': 'K', 'k': 'K', 'millones': 'M', 'hours': 'h', 'days': ' days', 'percent': '%', 'thousand': 'K', 'million': 'M'}
PESO.update(orbita=6.5, ruta=7.0, conectores=6.8, contador=8.5, versiones=7.5)


def _plegar(t):
    t = unicodedata.normalize('NFKD', str(t or '').lower())
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in t if not unicodedata.combining(c)))


def _limpio(t):
    return re.sub(r'^[^\w¿¡$€£¥₦₹]+|[^\w%]+$', '', str(t or ''))


def _corto(s, n=24):
    s = ' '.join(str(s or '').split())
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0]


# ----------------------------------------------------------------------------------------------------------------------------------- iconos
_ACTIVOS = {}
# palabras frecuentes (plegadas, es/en) → emoji del paquete (solo se usan los que existen); completa los de los acompañantes, el kit y los 3D
_SUPL = {
    'party_popper': 'festival festivales fiesta fiestas celebracion celebrar evento eventos party celebration event events',
    'microphone': 'concierto conciertos cantante cantar concert concerts singer sing karaoke',
    'guitar': 'banda bandas rock band bands guitarra',
    'musical_notes': 'musica cancion canciones music song songs ritmo',
    'graduation_cap': 'beca becas maestria universidad universidades estudiar estudio estudios estudiante estudiantes escuela colegio graduacion '
                      'carrera university school student students scholarship master degree',
    'trophy': 'torneo torneos campeonato competencia premios ganador ganadores tournament championship awards prizes',
    'busts_in_silhouette': 'jovenes joven juventud amigos amigas amigo comunidad gente personas publico youth friends community people audience',
    'video_game': 'gamer gamers videojuego videojuegos juego juegos fifa gaming game games',
    'speech_balloon': 'charla charlas conferencia conferencias conversacion mensaje mensajes talk talks chat comentarios',
    'handshake': 'networking contactos alianza alianzas socios acuerdo partners deal colaboracion',
    'rocket': 'emprendimiento emprendimientos emprendedor emprendedores negocio negocios startup startups business lanzamiento lanzar launch',
    'wrapped_gift': 'sorpresa sorpresas regalo regalos surprise surprises gift gifts',
    'calendar': 'fecha fechas sabado domingo lunes martes miercoles jueves viernes calendario date enero febrero marzo abril mayo junio julio '
                'agosto septiembre octubre noviembre diciembre',
    'alarm_clock': 'hora horas tarde noche reloj minutos time hour hours',
    'mobile_phone': 'influencer influencers creador creadores redes seguidores telefono celular movil app aplicacion phone followers',
    'office_building': 'centro edificio oficina empresa empresas lugar sede building office',
    'globe_showing_europe_africa': 'europa europea europeo union mundo mundial internacional world international europe',
    'globe_showing_americas': 'america latinoamerica guatemala mexico paises pais country countries internet online web',
    'money_bag': 'dinero plata ganancias money cash ahorro ahorrar', 'dollar_banknote': 'precio precios pagar pago costo dolares price pay',
    'credit_card': 'tarjeta tarjetas card', 'bank': 'banco bancos bank',
    'light_bulb': 'idea ideas creatividad idea', 'brain': 'cerebro mente pensar inteligencia brain mind', 'microscope': 'ciencia cientifico science',
    'stethoscope': 'salud medico doctor doctora health', 'hospital': 'hospital clinica',
    'house': 'casa hogar casas home house', 'airplane': 'viaje viajes viajar vuelo travel trip flight', 'beach_with_umbrella': 'playa vacaciones beach',
    'automobile': 'coche auto carro car', 'train': 'tren train', 'ship': 'barco crucero ship',
    'soccer_ball': 'deporte deportes futbol soccer football', 'person_lifting_weights': 'gimnasio ejercicio entrenar gym workout',
    'person_running': 'correr carrera running', 'woman_dancing': 'baile bailar dance dancing', 'performing_arts': 'teatro arte cultura cultural culture',
    'red_heart': 'amor corazon love heart', 'two_hearts': 'boda bodas pareja wedding couple',
    'camera': 'foto fotos fotografia camara photo photos', 'clapper_board': 'pelicula peliculas cine movie film',
    'laptop': 'computadora ordenador laptop programar codigo', 'briefcase': 'trabajo empleo trabajar job work career',
    'hammer_and_wrench': 'herramienta herramientas tools', 'gear': 'proceso sistema configurar process system',
    'warning': 'problema problemas peligro cuidado riesgo warning risk', 'cross_mark': 'error errores fallo wrong',
    'check_mark_button': 'correcto done check', 'chart_increasing': 'crecimiento aumento growth',
    'chart_decreasing': 'caida perdida perdidas loss', 'bullseye': 'objetivo objetivos meta metas goal goals',
    'locked': 'seguridad privado contrasena security', 'high_voltage': 'energia rapido rapida fast energy',
    'seedling': 'planta plantas naturaleza ecologia nature', 'water_wave': 'agua mar oceano water ocean', 'sun': 'sol verano sun summer',
    'hot_beverage': 'cafe coffee', 'books': 'libro libros leer lectura book books', 'writing_hand': 'escribir nota notas write',
    'megaphone': 'anuncio noticia noticias news announcement', 'studio_microphone': 'podcast entrevista radio voz interview',
    'shopping_bags': 'comprar compras tienda tiendas shopping store', 'package': 'envio envios paquete paquetes shipping',
    'robot': 'robot ia ai automatizacion', 'red_question_mark': 'pregunta preguntas duda dudas question questions',
    'eyes': 'atencion look', 'thinking_face': 'pensamiento think', 'headphone': 'dj audio auriculares',
    'face_savoring_food': 'comida comidas gastronomia food', 'free_button': 'gratis gratuita gratuito gratuitos free',
}
SUPLEMENTO = {w: e for e, ws in _SUPL.items() for w in ws.split()}


def _public():
    try:
        import edicion_pro_remotion as RM
        p = Path(RM.bundle()) / 'public'
        if p.exists():
            return p
    except Exception:
        pass
    return Path(__file__).resolve().parent / 'remotion' / 'public'


def _activos():
    """Los iconos que hay en el paquete de Remotion: emojis (Lottie animados o PNG 3D), recortes de revista y los 3D grandes."""
    if not _ACTIVOS:
        pub = _public()
        em = {p.stem[len('rcs_emoji_'):] for p in (pub / 'stickers').glob('rcs_emoji_*.png')}
        em |= {p.stem for p in (pub / 'lottie').glob('*.json') if p.stem != 'indice'}
        _ACTIVOS.update(emoji=em, recorte={p.stem for p in (pub / 'recortes' / 'color').glob('*.webp')},
                        i3d={p.stem for p in (pub / 'iconos3d').glob('*.png')})
    return _ACTIVOS


def _mapas():
    out = []
    try:
        import edicion_pro_tema5_acomp as AC
        out.append(('emoji', AC.CONCEPTOS_ACOMP))
    except Exception:
        pass
    try:
        import edicion_pro_kit7 as K7
        out.append(('recorte', K7.RECORTES))
    except Exception:
        pass
    try:
        import edicion_pro_planificador as PL
        out.append(('i3d', PL.CONCEPTOS3D))
    except Exception:
        pass
    return out


def _variantes(pleg):
    """La palabra y sus formas base (plural, género): «conciertos» → concierto, «premios» → premio, «gratuita» → gratuito."""
    out = [pleg]
    if len(pleg) > 4 and pleg.endswith('es'):
        out.append(pleg[:-2])
    if len(pleg) > 3 and pleg.endswith('s'):
        out.append(pleg[:-1])
    for w in list(out):
        if len(w) > 3 and w[-1] in 'ao':
            out.append(w[:-1] + ('o' if w[-1] == 'a' else 'a'))
    return out


def _icono_de(pleg, mapas=None):
    """{'emoji': id} | {'img': 'recortes/color/x.webp'} | {'img': 'iconos3d/x.png'} | None para una palabra plegada (y sus formas base)."""
    a = _activos()
    for w in _variantes(pleg):
        for tipo, mapa in (mapas if mapas is not None else _mapas()) + [('emoji', SUPLEMENTO)]:
            n = mapa.get(w)
            if not n:
                continue
            if n in a['emoji']:
                return {'emoji': n}
            if tipo == 'recorte' and n in a['recorte']:
                return {'img': f'recortes/color/{n}.webp'}
            if tipo == 'i3d' and n in a['i3d']:
                return {'img': f'iconos3d/{n}.png'}
    return None


# ----------------------------------------------------------------------------------------------------------------------------------- tramos
def _partir(bloques):
    """Parte las frases que llevan un punto, una interrogación o una exclamación por dentro («…understand. And when you say,»): así cada tramo
    puede acabar donde acaba la idea, como en los reels de referencia."""
    out = []
    for b in bloques:
        ps = list(b.get('palabras') or [])
        cortes = [k + 1 for k, w in enumerate(ps[:-1]) if str(w.get('texto') or '').rstrip()[-1:] in '.?!']
        if not cortes:
            out.append(b)
            continue
        ini = float(b['ini'])
        for a, z in zip([0] + cortes, cortes + [len(ps)]):
            t0 = float(ps[a].get('t') or 0)
            fin = ini + float(ps[z].get('t') or 0) if z < len(ps) else float(b['fin'])
            out.append(dict(b, ini=round(ini + t0, 3), fin=round(max(ini + t0 + 0.05, fin), 3),
                            palabras=[dict(w, t=round(float(w.get('t') or 0) - t0, 3)) for w in ps[a:z]]))
    return out


def _final(b):
    """Cómo acaba una frase: '.' (punto, interrogación, exclamación), ',' (coma, punto y coma, dos puntos) o ''."""
    w = str((b.get('palabras') or [{}])[-1].get('texto') or '').rstrip()[-1:]
    return '.' if w in '.?!' else ',' if w in ',;:' else ''


def _segmentos(bloques, dur):
    """Los tramos: frases seguidas juntas hasta que acaba la idea (punto: desde 0,6 s; coma: desde 0,7 s, como los reels), sin pasar de MAX_S,
    contiguos de 0 al final; uno muy largo (pausa) se parte en dos."""
    segs, cur = [], None
    for k, b in enumerate(bloques):
        if cur:
            largo = cur['fin'] - cur['ini']
            minimo = 0.6 if cur['final'] == '.' else 0.7 if cur['final'] == ',' else MAX_S          # a media frase: sigue hasta que acabe la idea
            if largo < minimo and b['ini'] - cur['fin'] < 1.0 and b['fin'] - cur['ini'] <= MAX_S:
                cur['fin'] = b['fin']
                cur['bl'].append(k)
                cur['final'] = _final(b)
                continue
            segs.append(cur)
        cur = {'ini': b['ini'], 'fin': b['fin'], 'bl': [k], 'final': _final(b)}
    if cur:
        segs.append(cur)
    if not segs:
        return []
    segs[0]['ini'] = 0.0
    for a, z in zip(segs, segs[1:]):
        a['fin'] = z['ini']
    segs[-1]['fin'] = max(segs[-1]['fin'], float(dur or segs[-1]['fin']))
    out = []
    for s in segs:
        s.pop('final', None)
        if s['fin'] - s['ini'] > MAX_S * 1.6:
            m = round((s['ini'] + s['fin']) / 2, 3)
            out += [dict(s, fin=m, corte=True), dict(s, ini=m, mitad=True)]
        else:
            out.append(s)
    return out


def _palabras_globales(bloques):
    """textos, plegadas, tiempos (absolutos) y frases (índices de palabra por bloque), como los pide el kit."""
    textos, plegadas, tiempos, frases = [], [], [], []
    for b in bloques:
        idx = []
        for w in b['palabras']:
            t = _limpio(w['texto'])
            if not t:
                continue
            idx.append(len(textos))
            textos.append(t)
            plegadas.append(_plegar(t))
            tiempos.append(round(b['ini'] + float(w.get('t') or 0), 3))
        frases.append(idx)
    return textos, plegadas, tiempos, frases


_CORRECTOR = {}


def _comun(texto, idioma='es'):
    """¿Es una palabra corriente del idioma (está en el diccionario, también conjugada o en plural)? Sin diccionario: no se sabe (False)."""
    w = str(texto or '').lower()
    if idioma not in _CORRECTOR:
        try:
            import ortografia
            _CORRECTOR[idioma] = ortografia._corrector(idioma)
        except Exception:
            _CORRECTOR[idioma] = None
    c = _CORRECTOR[idioma]
    if c is None or not w:
        return False
    try:
        if not c.unknown([w]):
            return True
        if str(idioma)[:2] == 'es':
            import ortografia_es
            return bool(ortografia_es.conocida(w, c))
    except Exception:
        pass
    return False


def _contenido(idx, textos, plegadas, mapas, idioma='es'):
    """Las palabras con contenido de un tramo, con su icono (si hay) y si van con mayúscula (candidatas a nombre propio)."""
    out = []
    for n, j in enumerate(idx):
        p = plegadas[j]
        if not p or p in VACIAS or (len(p) < 3 and not p.isdigit()):
            continue
        t = textos[j]
        mayus = (t[:1].isupper() and n > 0) or (t.isupper() and 1 < len(t) <= 5)
        comun = _comun(t, idioma) if mayus else True
        raro = mayus and not comun                                         # un nombre propio no lleva icono («Chela» es Xela, no una cerveza)
        out.append({'j': j, 'texto': t, 'pleg': p, 'icono': None if raro else _icono_de(p, mapas), 'mayus': mayus,
                    'sigla': t.isupper() and 1 < len(t) <= 5 and not comun, 'raro': raro, 'verbo': p.endswith(_VERBO)})
    return out


def _entidades(cont):
    """Los nombres propios: varias palabras con mayúscula seguidas («Unión Europea», «Glass Collective», «Master Cage»), una sigla (FIFA) o una
    palabra con mayúscula que no está en el diccionario (Quetzaltenango). Las palabras corrientes que el guion pone con mayúscula para
    destacarlas («Haciendo», «Interesa») NO lo son."""
    grupos, cur = [], []
    for c in cont:
        if c['mayus'] and cur and c['j'] == cur[-1]['j'] + 1:
            cur.append(c)
            continue
        if cur:
            grupos.append(cur)
        cur = [c] if c['mayus'] else []
    if cur:
        grupos.append(cur)
    def vale(g):
        if any(x['sigla'] or x['raro'] for x in g):
            return True
        return len(g) >= 2 and not any(x['verbo'] for x in g)               # «Unión Europea», «Centro Intercultural»; no «Perder Guarda»
    return [' '.join(x['texto'] for x in g) for g in grupos if vale(g)]


# ----------------------------------------------------------------------------------------------------------------------------------- fuentes
# ----------------------------------------------------------------------------------------------------------------------------------- director
def _textos(idioma):
    return TEXTOS.get(str(idioma or 'es')[:2].lower(), TEXTOS['en'])


def _clave(cont):
    """La palabra clave de un tramo (la que va en cursiva): un nombre propio o con icono antes que una corriente; la más larga."""
    nombres = [c for c in cont if not c['verbo'] or c['raro']] or cont
    return max(nombres, key=lambda c: (bool(c['raro'] or c['icono']), len(c['pleg'])))['j'] if nombres else None


def _cifra(idx, textos, plegadas):
    """La primera cifra que se dice, con su unidad («3 horas» → '3 h'), o None."""
    for n, j in enumerate(idx):
        valor, suf = _numero(textos[j])
        valor = NUMEROS.get(plegadas[j], valor)
        if valor is not None:
            sig = plegadas[idx[n + 1]] if n + 1 < len(idx) else ''
            return valor, (suf or UNIDAD.get(sig, '')).strip()
    return None, ''


_VERBO_MAS = ('aran', 'eran', 'iran', 'aron', 'ieron', 'amos', 'emos', 'imos', 'ados', 'idas', 'ando', 'iendo')   # (plegadas: sin tildes)


def _nombres(cont, excluir=()):
    """Las COSAS de un tramo para una lista o una nota: los nombres propios enteros («Glass Collective») y las palabras con contenido que no son
    verbos, sin repetir («Festival» una vez) y sin las de `excluir`."""
    fuera = {_plegar(x) for x in excluir if x}
    out, vistos = [], set(fuera)
    ent = _entidades(cont)
    dentro = {_plegar(w) for e in ent for w in e.split()}
    for e in ent:
        if _plegar(e) not in vistos:
            vistos.add(_plegar(e))
            out.append(e)
    for x in cont:
        pl = x['pleg']
        if x['verbo'] or pl.endswith(_VERBO_MAS) or pl in dentro or pl in vistos or len(pl) < 3:
            continue
        vistos.add(pl)
        out.append(x['texto'][:1].upper() + x['texto'][1:].lower() if x['texto'].isupper() else x['texto'][:1].upper() + x['texto'][1:])
    return out


def _tarjeta(nombre, idx, cont, textos, plegadas, crudos, L, hits):
    """Una tarjeta del estilo reel para el tramo: {'tipo': 'reel', 'reel', 'wp' (sus textos), '_estilos' {j: estilo del titular}, '_arriba',
    '_cita' (las palabras que van en el mensaje y no en el titular)}."""
    hit = hits[0] if hits else None
    clave = _clave(cont)
    tras = [c['j'] for c in cont if hit is not None and c['j'] > hit and not c['verbo']]             # lo que va detrás del verbo («cortar el relleno»)
    objeto = tras[0] if tras else clave
    ger = next((textos[j] for j in reversed(idx) if plegadas[j].endswith(('ando', 'iendo', 'ing')) and len(plegadas[j]) > 5), None)
    valor, suf = _cifra(idx, textos, plegadas)
    cap = lambda t: t[:1].upper() + t[1:]
    c = {'tipo': 'reel', 'reel': nombre, 'wp': {}, '_estilos': {}}
    if nombre == 'rec':
        c['_estilos'] = {hit: 'clave'}
    elif nombre == 'reloj':
        c['wp'] = {'etiqueta': cap(ger) + '…' if ger else L['reloj']}
        c['_estilos'] = {hit: 'clave'}
    elif nombre == 'archivos':
        sustantivo = hit if hit is not None and not plegadas[hit].endswith(_VERBO) else objeto
        c['wp'] = {'titulo': cap(textos[sustantivo]) if sustantivo is not None else L['material'], 'sub': L['material_sub']}
        c['_estilos'] = {sustantivo if sustantivo is not None else hit: 'clave'}
    elif nombre == 'buscar':
        c['wp'] = {'etiqueta': (cap(textos[objeto]) + ' ✓') if objeto is not None else '✓'}
        c['_estilos'] = {objeto if objeto is not None else hit: 'clave'}
    elif nombre == 'cortar':
        c['wp'] = {'titulo': L['linea']}
        c['_estilos'] = {tras[0]: 'tachado'} if tras else {hit: 'clave'}
    elif nombre == 'largo':
        c['wp'] = {'duracion': f'{valor} {suf}'.strip() if valor and suf else L['duracion']}
        gris = [j for j in idx if plegadas[j] in GRIS]
        c['_estilos'] = {gris[0]: 'gris'} if gris else {hit: 'clave'}
    elif nombre == 'movil':
        t1, t2, sub, boton, eti = L['movil']
        c['wp'] = {'titulo': t1, 'cursiva': t2, 'sub': sub, 'boton': boton, 'etiqueta': eti, 'pct': valor if valor and suf == '%' and valor <= 100 else 96}
        ultimo = [x['j'] for x in cont][-1:] or [None]
        c['_estilos'] = {clave: 'clave'}
        if ultimo[0] is not None and ultimo[0] != clave:
            c['_estilos'][ultimo[0]] = 'caja'
    elif nombre == 'chat':
        decir = [j for j in idx if plegadas[j] in DECIR]
        corte = idx.index(decir[0]) + 1 if decir and len(idx) - idx.index(decir[0]) > 3 else 0
        cita = idx[corte:][:12]
        nombres = [x for x in cont if x['raro'] and x['j'] not in cita]
        cliente = any(plegadas[j] in ('cliente', 'clientes', 'client', 'clients') for j in idx)
        quien = nombres[0]['texto'] if nombres else (L['cliente'][0] if cliente else '')
        resalta = [x['j'] for x in cont if x['j'] in cita and not x['verbo']][-2:] or [clave]
        iconos = [x['icono']['emoji'] for x in cont if x['j'] in cita and x['icono'] and x['icono'].get('emoji')]
        c['wp'] = {'nombre': quien, 'rol': f"{L['cliente'][0]} · {L['cliente'][1]}" if quien else '', 'responder': L['responder'], 'iconos': iconos[:2]}
        c['_cita'] = (cita, set(resalta))
        if corte:
            c['_arriba'] = ' '.join(crudos[j] for j in idx[:corte]).rstrip(',.;:') + '…'
    elif nombre == 'abc':
        c['wp'] = {'etiquetas': list(L['abc']), 'boton': L['nueva'], 'version': L['version']}
        c['_estilos'] = {clave if clave is not None else hit: 'pildora'}
    elif nombre == 'ideas':
        horas = any(plegadas[j] in ('horas', 'hours', 'dia', 'dias', 'day', 'days') for j in idx)
        c['wp'] = {'n1': valor if valor and valor > 9 else 249, 'e1': L['ideas'], 'n2': L['dia'][0] if horas else '', 'e2': L['dia'][1] if horas else ''}
        marcas = [j for j in idx if plegadas[j] in ('videos', 'video', 'ideas', 'idea', 'horas', 'hours', 'tiempo', 'time')][:2] or [clave]
        c['_estilos'] = {j: 'clave' for j in marcas}
    elif nombre == 'fecha':
        dia = next((textos[j] for j in idx if textos[j].isdigit() and 1 <= int(textos[j]) <= 31), '')
        semana = next((textos[j] for j in idx if plegadas[j] in DIAS), '')
        mes = next((textos[j] for j in idx if plegadas[j] in MESES), '')
        hora = ''
        for n, j in enumerate(idx[:-1]):
            if plegadas[j] in ('las', 'la', 'at') and textos[idx[n + 1]].isdigit() and int(textos[idx[n + 1]]) <= 24 and textos[idx[n + 1]] != dia:
                hora = f'{int(textos[idx[n + 1]])}:00'
                break
        c['wp'] = {'dia': dia or (cap(semana)[:3] if semana else '✓'), 'mes': (mes[:3] if mes else L['fecha_txt']).upper(), 'semana': cap(semana) if dia else '',
                   'hora': hora, 'boton': L['calendario']}
        c['_estilos'] = {j: 'clave' for j in idx if plegadas[j] in MESES or plegadas[j] in DIAS}
    elif nombre == 'lugar':
        ent = sorted(_entidades(cont), key=len, reverse=True)
        c['wp'] = {'nombre': _corto(ent[0], 30) if ent else (cap(textos[objeto]) if objeto is not None else ''), 'sub': _corto(ent[1], 30) if len(ent) > 1 else '',
                   'boton': L['llegar']}
        c['_estilos'] = {j: 'clave' for j in idx if ent and textos[j] in ent[0].split()[-1:]} or {clave: 'clave'}
    elif nombre == 'entrada':
        gratis = any(plegadas[j] in GRATIS for j in idx)
        moneda = next((MONEDA[plegadas[j]] for j in idx if plegadas[j] in MONEDA), '')
        precio = f'{moneda}{valor}' if valor and not gratis and suf != '%' else ''
        c['wp'] = {'valor': L['gratis'] if gratis or not precio else precio, 'titulo': L['entrada'],
                   'sub': cap(textos[objeto]) if objeto is not None and plegadas[objeto] not in GRATIS and not textos[objeto][:1].isdigit() else '',
                   'sello': f'{valor}%' if valor and suf == '%' else ''}
        c['_estilos'] = {j: 'clave' for j in idx if plegadas[j] in GRATIS} or {hit: 'clave'}
    elif nombre == 'personas':
        ent = [e for e in _entidades(cont) if len(e) <= 22]
        nombres = ent[:4] or [cap(x['texto']) for x in cont if x['pleg'] in REEL['personas'] or (not x['verbo'] and len(x['pleg']) > 3)][:3]
        c['wp'] = {'nombres': nombres, 'etiqueta': '', 'extra': f'+{valor}' if valor and valor > len(nombres) else ''}
        c['_estilos'] = {hit: 'clave'}
    elif nombre == 'musica':
        ent = _entidades(cont)
        vivo = any(plegadas[j] in ('vivo', 'live', 'directo') for j in idx)
        c['wp'] = {'titulo': _corto(ent[0], 28) if ent else cap(textos[hit]), 'sub': L['vivo'] if vivo else L['musica']}
        c['_estilos'] = {hit: 'clave'}
    elif nombre == 'premio':
        ent = _entidades(cont)
        beca = any(plegadas[j] in ('beca', 'becas', 'scholarship', 'maestria', 'master') for j in idx)
        dinero = any(plegadas[j] in MONEDA or plegadas[j] in ('dinero', 'money', 'efectivo', 'cash') for j in idx)
        otros = [x['texto'] for x in cont if x['j'] != (objeto if objeto is not None else hit) and not x['verbo']][:3]
        c['wp'] = {'titulo': _corto(ent[0], 26) if ent else cap(textos[objeto if objeto is not None else hit]), 'sub': ' · '.join(otros),
                   'icono': 'graduation_cap' if beca else 'money_bag' if dinero else 'trophy'}
        c['_estilos'] = {hit: 'clave'}
    elif nombre == 'compartir':
        iconos = [x['icono']['emoji'] for x in cont if x['icono'] and x['icono'].get('emoji')]
        c['wp'] = {'titulo': L['compartir'], 'listo': L['enviado'], 'iconos': iconos[:2]}
        c['_estilos'] = {hit: 'clave'}
    elif nombre == 'aviso':
        ent = _entidades(cont)
        iconos = [x['icono']['emoji'] for x in cont if x['icono'] and x['icono'].get('emoji')]
        titulo = ent[0] if ent else (cap(textos[clave]) if clave is not None else '')
        otros = [x['texto'] for x in cont if x['j'] != clave and not x['verbo'] and x['texto'] not in titulo.split()][:3]
        c['wp'] = {'icono': iconos[0] if iconos else 'bell', 'app': '', 'hora': L['ahora'], 'titulo': _corto(titulo, 30), 'cuerpo': ' · '.join(otros)}
        c['_estilos'] = {clave: 'clave'}
    elif nombre == 'lista':
        titulo = cap(textos[hit]) if hit is not None and not plegadas[hit].endswith(_VERBO) else ''
        cosas = _nombres(cont, [titulo])[:4]
        if len(cosas) < 3:
            return None
        c['wp'] = {'titulo': titulo, 'items': cosas}
        c['_estilos'] = {hit if hit is not None else clave: 'clave'}
    elif nombre == 'buscador':
        claves = [x['texto'].lower() for x in cont if x['pleg'] not in REEL['buscador']][:5]
        ent = _entidades(cont)
        res = list(dict.fromkeys(([ent[0]] if ent else []) + [cap(x['texto']) for x in cont if not x['verbo'] and x['pleg'] not in REEL['buscador']]))[:3]
        c['wp'] = {'consulta': ' '.join(claves) or (textos[clave].lower() if clave is not None else ''), 'resultados': res}
        c['_estilos'] = {clave: 'clave'}
    elif nombre == 'post':
        ent = _entidades(cont)
        otros = [x['texto'] for x in cont if not x['verbo']][:4]
        c['wp'] = {'usuario': (ent[0] if ent else L['usuario']).replace(' ', '_').lower()[:22], 'texto': ' '.join(otros),
                   'likes': valor if valor and valor > 20 else 1240 + (sum(map(ord, ''.join(otros))) % 8000), 'megusta': L['megusta']}
        c['_estilos'] = {clave: 'clave'}
    elif nombre == 'encuesta':
        dos = []
        for n, j in enumerate(idx[1:-1], 1):
            if plegadas[j] in ('o', 'or', 'ou'):
                dos = [cap(textos[idx[n - 1]]), cap(textos[idx[n + 1]])]
                break
        a = 52 + (sum(map(ord, ''.join(textos[j] for j in idx))) % 31)
        c['wp'] = {'pregunta': (cap(textos[clave]) + '?') if clave is not None else '', 'opciones': dos or list(L['si_no']), 'pcts': [a, 100 - a]}
        c['_estilos'] = {clave: 'clave'}
    elif nombre == 'carga':
        c['wp'] = {'etiqueta': cap(ger) + '…' if ger else L['cargando'], 'pct': valor if valor and suf == '%' and valor <= 100 else 100}
        c['_estilos'] = {hit if hit is not None else clave: 'clave'}
    elif nombre == 'nota':
        cosas = _nombres(cont)[:4]
        if len(cosas) < 2:
            return None
        c['wp'] = {'lineas': cosas}
        c['_estilos'] = {clave: 'clave'}
    elif nombre == 'antesdespues':
        c['wp'] = {'antes': L['antes'], 'despues': L['despues']}
        c['_estilos'] = {hit if hit is not None else clave: 'clave'}
    elif nombre == 'cuenta':
        u = L['cuenta']
        c['wp'] = {'valores': [f'{min(int(valor), 99):02d}' if valor else '03', '12', '45'], 'etiquetas': list(u)}
        c['_estilos'] = {hit if hit is not None else clave: 'clave'}
    elif nombre == 'grafica':
        doble = next((m for j in idx for w, m in (('duplica', '×2'), ('double', '×2'), ('triplica', '×3')) if plegadas[j].startswith(w)), '')
        c['wp'] = {'valor': f'+{valor}%' if valor and suf == '%' else (doble or (f'+{valor}' if valor else '+40%')),
                   'etiqueta': cap(textos[objeto]) if objeto is not None else ''}
        c['_estilos'] = {hit if hit is not None else clave: 'clave'}
    elif nombre == 'golpe':
        palabra = re.sub(r'[^\w\-ÁÉÍÓÚÜÑáéíóúüñ]+', '', crudos[clave]) if clave is not None else ''
        c['wp'] = {'palabra': palabra}
        c['_estilos'] = {}
    c['_estilos'] = {j: e for j, e in c['_estilos'].items() if j is not None}
    return c


def _reel(idx, cont, textos, plegadas, crudos, L):
    """Las tarjetas que piden las palabras del tramo."""
    out = []
    for nombre, claves in REEL.items():
        hits = [j for j in idx if plegadas[j] in claves]
        if hits:
            c = _tarjeta(nombre, idx, cont, textos, plegadas, crudos, L, hits)
            if c is None:
                continue
            c['peso'] = PESO['reel'] + 0.8 * (len(hits) - 1)
            if nombre == 'chat' and c.get('_arriba'):
                c['peso'] += 3.0                                           # «y cuando dices: …»: la cita, con lo que se dice
            out.append(c)
    return out


def _generales(idx, cont, textos, plegadas, crudos, L):
    """Si nada encaja, algo del mismo estilo que sirve para cualquier frase: el aviso (una notificación con lo importante), el mensaje con lo que
    se dice o el clip elegido (lo importante, marcado)."""
    out = []
    if cont:
        c = _tarjeta('aviso', idx, cont, textos, plegadas, crudos, L, [])
        c['peso'] = PESO['general'] + 0.6
        out.append(c)
    if 3 <= len(idx) <= 12:
        c = _tarjeta('chat', idx, cont, textos, plegadas, crudos, L, [])
        c['peso'] = PESO['general'] + 0.2
        out.append(c)
    nombres = [x for x in cont if not x['verbo']]
    extra_de = {'buscar': 0.0, 'lista': 0.3, 'nota': 0.1, 'post': -0.1}
    vale_de = {'buscar': True, 'lista': len(nombres) >= 3, 'nota': len(nombres) >= 2, 'post': len(nombres) >= 2}
    for nombre in GENERALES:
        if nombre in ('aviso', 'chat') or not vale_de.get(nombre):
            continue                                                       # (el aviso y el mensaje, arriba)
        extra = extra_de.get(nombre, 0.0)
        c = _tarjeta(nombre, idx, cont, textos, plegadas, crudos, L, [])
        if c is None:
            continue
        c['peso'] = PESO['general'] + extra
        out.append(c)
    for c in out:
        c['_general'] = True
    return out


def _reel_ia(frases, textos, plegadas, crudos, tiempos, mapas, idioma, estado, contexto, L):
    """La IA local elige la tarjeta de cada frase (modo denso, menú REEL_MENU); la palabra clave tiene que estar DICHA en esa frase."""
    try:
        import ia_texto
        propuestas = ia_texto.motions([' '.join(textos[j] for j in f) for f in frases], idioma, estado=estado, contexto=contexto,
                                      solo=['reel'], denso=True, extra=REEL_MENU) or []
    except Exception:
        return []
    out = []
    for pr in propuestas:
        nombre = str(pr.get('motion') or '')
        try:
            b = int(pr.get('b'))
        except Exception:
            continue
        if nombre not in REEL_MENU or not 0 <= b < len(frases) or not frases[b]:
            continue
        idx = list(frases[b])
        datos = pr.get('datos') if isinstance(pr.get('datos'), dict) else {}
        palabra = _plegar(datos.get('palabra') or pr.get('ancla') or '')
        hits = [j for j in idx if palabra and plegadas[j] == palabra] or [j for j in idx if plegadas[j] in REEL.get(nombre, ())]
        cont = _contenido(idx, textos, plegadas, mapas, idioma)
        if not _evidencia(nombre, idx, cont, textos, plegadas):
            continue
        c = _tarjeta(nombre, idx, cont, textos, plegadas, crudos, L, hits)
        if c is None:
            continue
        c['peso'] = PESO['reel_ia']
        out.append((tiempos[hits[0]] if hits else tiempos[idx[0]], c))
    return out


def _evidencia(nombre, idx, cont, textos, plegadas):
    """Las tarjetas de DATOS solo si el dato se dice (la IA propuso una fecha para «de I de la Unión Europea»)."""
    pleg = {plegadas[j] for j in idx}
    if nombre == 'fecha':
        return bool(pleg & (DIAS | MESES)) or any(textos[j].isdigit() and 1 <= int(textos[j]) <= 31 for j in idx) and bool(pleg & REEL['fecha'])
    if nombre == 'lugar':
        return bool(_entidades(cont))
    if nombre == 'entrada':
        return bool(pleg & GRATIS) or any(plegadas[j] in MONEDA for j in idx) or bool(pleg & REEL['entrada'])
    if nombre in ('personas', 'musica'):
        return bool(pleg & REEL[nombre]) or bool(_entidades(cont))
    if nombre == 'antesdespues':
        return bool(pleg & REEL['antesdespues'])
    return True


def planificar(bloques, dur, idioma='es', perfil=None, video='', vertical=True, ia=True, estado=None):
    bloques = _partir(bloques)
    segs = _segmentos(bloques, dur)
    if not segs:
        return None
    perfil = perfil or {}
    textos, plegadas, tiempos, frases = _palabras_globales(bloques)
    crudos = [str(w['texto']).strip() for b in bloques for w in b['palabras'] if _limpio(w['texto'])]   # con su puntuación, para el titular
    con_video = bool(video) and os.path.isfile(str(video))
    mapas = _mapas()
    L = _textos(idioma)
    cands = [[] for _ in segs]

    def tramo(t):
        for k, s in enumerate(segs):
            if s['ini'] - 0.3 <= t < s['fin'] - 0.2:
                return k
        return None

    # 1) la IA: qué tarjeta va en cada frase
    if ia:
        contexto = ' · '.join(x for x in (perfil.get('categoria'), perfil.get('subtema'), perfil.get('tono') and 'tono ' + perfil['tono']) if x)
        for t, c in _reel_ia(frases, textos, plegadas, crudos, tiempos, mapas, idioma, estado, contexto, L):
            k = tramo(t)
            if k is not None:
                cands[k].append(c)
    # 2) las palabras de cada tramo: sus tarjetas, los widgets claros y, por si nada encaja, las generales
    idx_de = []
    for k, s in enumerate(segs):
        idx = [j for b in s['bl'] for j in frases[b]]
        if s.get('mitad'):
            idx = [j for j in idx if tiempos[j] >= s['ini'] - 0.2] or idx
        idx_de.append(idx)
        cont = _contenido(idx, textos, plegadas, mapas, idioma)
        items, vistos = [], set()
        for e in _entidades(cont):
            if _plegar(e) not in vistos:
                vistos.add(_plegar(e))
                ic = next((c['icono'] for c in cont if c['icono'] and c['texto'] in e.split()), None)
                items.append({'texto': _corto(e, 22), **({'icono': ic} if ic else {})})
        for c in cont:
            if c['icono'] and c['pleg'] not in vistos and not any(c['texto'] in i['texto'].split() for i in items):
                vistos.add(c['pleg'])
                items.append({'texto': c['texto'].capitalize() if c['texto'].isupper() else c['texto'], 'icono': c['icono']})
        cands[k] += [c for c in _reel(idx, cont, textos, plegadas, crudos, L) if c['reel'] != 'antesdespues' or con_video]
        cands[k] += _widgets(idx, cont, items, textos, plegadas)
        cands[k] += _generales(idx, cont, textos, plegadas, crudos, L)
        clave = _clave(cont)                                               # el GOLPE: un momento corto y fuerte = solo la palabra, enorme
        fuerte = bool(idx) and (crudos[idx[-1]].endswith('!') or len(idx) <= 4)
        if clave is not None and fuerte and s['fin'] - s['ini'] <= 2.6 and len(textos[clave]) >= 3:
            g = _tarjeta('golpe', idx, cont, textos, plegadas, crudos, L, [])
            g['peso'] = PESO['golpe']
            cands[k].append(g)
        if k > 0:
            cands[k].append({'tipo': 'reel', 'reel': '_sigue', 'wp': {}, 'peso': PESO['sigue'], '_sigue': True})
    # la idea que no cupo en un tramo puede seguir en el siguiente si este no pide nada («¿otra versión?» → «claro que sí»: las A/B/C)
    for k in range(len(segs) - 1, 0, -1):
        if any(c['tipo'] == 'reel' and c['peso'] >= PESO['reel'] for c in cands[k]):
            continue
        for c in cands[k - 1]:
            if c['tipo'] == 'reel' and c['peso'] >= PESO['reel'] and c['reel'] in ('abc', 'ideas', 'reloj', 'movil', 'buscar', 'largo'):
                idx = idx_de[k]
                h = _tarjeta(c['reel'], idx, _contenido(idx, textos, plegadas, mapas, idioma), textos, plegadas, crudos, L, [])
                if h is not None:
                    h['peso'] = c['peso'] - 3.0
                    cands[k].append(h)
    # 3) una por tramo: la que más vale, nunca la misma seguida y con variedad
    elegidas = _elegir(segs, cands)
    escenas, titulares = [], []
    for k, (s, e) in enumerate(zip(segs, elegidas)):
        quitar = set()
        if e.get('_cita'):
            cita, resalta = e['_cita']
            quitar = set(cita)
            e['wp'] = dict(e['wp'], cita=[{'t': round(max(0.05, tiempos[j] - s['ini']), 3), 'texto': crudos[j], **({'resalta': True} if j in resalta else {})}
                                          for j in cita])
        arriba = e.get('_arriba')
        primero = idx_de[k][0] if idx_de[k] else None                     # «Zane, …»: el nombre al que se habla va en la píldora de arriba
        if not arriba and primero is not None and crudos[primero].endswith(',') and textos[primero][:1].isupper() and not _comun(textos[primero], idioma) \
                and plegadas[primero] not in VACIAS:
            arriba = textos[primero] + ' 👋'
            quitar.add(primero)
        if e.get('_cita') or e.get('reel') == 'golpe':                     # el mensaje y el golpe YA son lo que se dice
            titular = []
        else:
            titular = _palabras_titular(s, frases, textos, plegadas, tiempos, mapas, idioma, crudos, e.get('_estilos'), quitar)
        titulares.append({'ini': round(s['ini'], 3), 'fin': round(s['fin'], 3), 'titular': titular, **({'arriba': arriba} if arriba else {})})
        if e.get('_sigue') and escenas:                                    # la misma tarjeta sigue y la cámara se acerca (cambia solo el titular)
            escenas[-1]['empuje'] = round(escenas[-1]['fin'] - escenas[-1]['ini'], 3)
            escenas[-1]['fin'] = round(s['fin'], 3)
            continue
        e = {x: v for x, v in e.items() if not x.startswith('_') and x != 'peso'}
        e.update(ini=round(s['ini'], 3), fin=round(s['fin'], 3))
        escenas.append(e)
    _variar(escenas)
    fotos = _fotogramas(video, escenas) if con_video else []
    return {'escenas': escenas, 'titulares': titulares, 'fotos': fotos, 'acento': '#2F5BE7', 'tema': 'claro'}


def _palabras_titular(s, frases, textos, plegadas, tiempos, mapas, idioma, crudos=None, estilos=None, quitar=(), maximo=12):
    """Las palabras del tramo para el titular (las que se dicen en él, con su puntuación; si son muchas, desde la frase de la clave), con su
    momento (relativo al tramo) y su estilo: el de la tarjeta (tachado, gris, píldora, recuadro) o la clave en cursiva."""
    idx = [j for b in s['bl'] for j in frases[b] if j not in quitar and (not s.get('mitad') or tiempos[j] >= s['ini'] - 0.3)
           and (not s.get('corte') or tiempos[j] < s['fin'])]
    if not idx:
        return []
    crudos = crudos or textos
    estilos = dict(estilos or {})
    if not estilos:
        clave = _clave(_contenido(idx, textos, plegadas, mapas, idioma))
        if clave is not None:
            estilos[clave] = 'clave'
    if len(idx) > maximo:
        marca = next((j for j in idx if j in estilos), idx[0])
        frase = next((list(frases[b]) for b in s['bl'] if marca in frases[b]), idx)
        frase = [j for j in frase if j in idx] or idx
        k = frase.index(marca) if marca in frase else 0
        a = 0 if k < maximo - 1 else k - 2
        idx = frase[a:a + maximo]
    tope = max(0.1, s['fin'] - s['ini'] - 0.35)                       # una palabra que se dice al final del tramo, que se llegue a ver
    return [{'t': round(min(tope, max(0.08, tiempos[j] - s['ini'])), 3), 'texto': crudos[j], **({'estilo': estilos[j]} if j in estilos else {})} for j in idx]


def _numero(texto):
    t = str(texto).replace(',', '').replace('.', '')
    m = re.match(r'^(\d{1,7})(%|h|k)?$', t.lower())
    return (int(m.group(1)), (m.group(2) or '').replace('k', 'K')) if m else (None, '')


def _widgets(idx, cont, items, textos, plegadas):
    """Los widgets que encajan con lo que se dice en el tramo (órbita, ruta, conectores, contador, versiones)."""
    out = []
    pleg = [plegadas[j] for j in idx]
    nombres = [c for c in cont if not c['verbo'] or c['raro']]
    con_ic = [c for c in nombres if c['icono']]
    clave = max(nombres, key=lambda c: (bool(c['raro'] or c['icono']), len(c['pleg'])), default=None)
    cosa = lambda c: {'texto': _corto(c['texto'].capitalize() if c['texto'].isupper() else c['texto'], 18), **({'icono': c['icono']} if c['icono'] else {})}
    # contador: una cifra que se dice, con su unidad («24 horas», «100%», «más de 500 clientes»)
    for n, j in enumerate(idx):
        valor, suf = _numero(textos[j])
        if valor is None or valor < 2:
            continue
        sig = plegadas[idx[n + 1]] if n + 1 < len(idx) else ''
        suf = suf or UNIDAD.get(sig, '')
        if suf == 'h' and valor > 999:
            continue
        etiqueta = ''
        if sig and sig not in UNIDAD and sig not in VACIAS and len(sig) > 2:
            etiqueta = _limpio(textos[idx[n + 1]])
        elif n + 2 < len(idx) and plegadas[idx[n + 2]] not in VACIAS:
            etiqueta = _limpio(textos[idx[n + 2]])
        mas = n > 0 and plegadas[idx[n - 1]] in ('mas', 'more', 'over') or (n > 1 and plegadas[idx[n - 2]] in ('mas', 'more'))
        out.append({'tipo': 'contador', 'valor': valor, 'sufijo': ('+' if mas and not suf else '') + suf if suf != '%' else '%',
                    'etiqueta': _corto(etiqueta, 18), 'peso': PESO['contador'] + (0.5 if suf else 0)})
        break
    # versiones: opciones, planes, elegir
    if OPCIONES & set(pleg):
        cartas = [cosa(c) for c in nombres if c['pleg'] not in OPCIONES][:3]
        while len(cartas) < 3:
            cartas.append({'texto': ('Opción ' if True else '') + 'ABC'[len(cartas)]})
        out.append({'tipo': 'versiones', 'cartas': cartas, 'peso': PESO['versiones']})
    # ruta: pasos, una secuencia, un destino
    if SECUENCIA & set(pleg) and len(nombres) >= 2:
        pasos = [cosa(c) for c in nombres if c['pleg'] not in SECUENCIA][:3]
        if len(pasos) >= 2:
            out.append({'tipo': 'ruta', 'pasos': pasos, 'titulo': _corto(clave['texto'], 20) if clave else '', 'peso': PESO['ruta']})
    # órbita: 3 o más cosas con icono o nombres propios alrededor de la idea
    if len(items) >= 3 and clave:
        resto = [i for i in items if _plegar(i['texto']) != clave['pleg']][:6]
        if len(resto) >= 3:
            out.append({'tipo': 'orbita', 'centro': cosa(clave), 'items': [dict(i, texto=_corto(i['texto'], 14)) for i in resto],
                        'peso': PESO['orbita'] + 0.3 * min(3, len(resto) - 2)})
    # conectores: varias cosas que se conectan / integran / automatizan y un resultado
    if (CONECTA & set(pleg) and len(con_ic) >= 2) or len(con_ic) >= 4:
        entradas = [cosa(c) for c in con_ic[:3]]
        opciones = [cosa(c) for c in nombres if c not in con_ic[:3]][:4] or [cosa(c) for c in con_ic[1:4]]
        res = nombres[-1] if nombres else clave
        if len(opciones) >= 2 and res:
            out.append({'tipo': 'conectores', 'entradas': entradas, 'opciones': opciones,
                        'resultado': {'texto': _corto(res['texto'], 16), 'icono': {'emoji': 'check_mark_button'}}, 'peso': PESO['conectores']})
    return out


def _familia(c):
    return 'reel:' + str(c.get('reel')) if c['tipo'] == 'reel' else c['tipo']


# lo que cuenta lo MISMO con otra pieza (no van dos seguidas)
_IDEA = {'contador': 'numero', 'reel:ideas': 'numero', 'orbita': 'lista', 'versiones': 'opciones', 'reel:abc': 'opciones', 'reel:personas': 'lista',
         'reel:fecha': 'fecha', 'reel:reloj': 'fecha'}


def _idea(c):
    f = _familia(c)
    return _IDEA.get(f, f)


def _elegir(segs, cands):
    """Una por tramo: la que más vale, nunca la misma seguida, con TOPE por video (~12 % de los tramos, mínimo 2) y DESCANSO (lo usado en los
    4 últimos tramos vale menos); «_sigue» = la tarjeta anterior continúa (solo tras una que no sea general y si cabe en ~5,4 s)."""
    out, cuenta = [], {}
    tope = max(2, round(0.12 * len(segs)))
    golpes = []
    for k in range(len(segs)):
        recientes = [_familia(x) for x in out[-4:]]
        prev_idea = _idea(out[-1]) if out else None
        mejor, nota = None, -1e9
        for c in cands[k]:
            if c.get('_sigue'):
                if not out or out[-1].get('_general') or out[-1].get('_sigue') or out[-1].get('reel') in ('golpe', 'chat'):
                    continue
                if segs[k]['fin'] - segs[k - 1]['ini'] > 5.4 or any(x.get('peso', 0) >= PESO['reel'] for x in cands[k] if x.get('tipo') == 'reel'):
                    continue
                n = c['peso']
                if n > nota:
                    mejor, nota = dict(out[-1], _sigue=True, peso=c['peso']), n
                continue
            f = _familia(c)
            n = c['peso']
            if recientes and f == recientes[-1]:
                n -= 50                                                    # nunca la misma tarjeta seguida (salvo que no haya otra cosa)
            if prev_idea and _idea(c) == prev_idea:
                n -= 8                                                     # ni la misma idea con otra pieza
            n -= 6.0 * recientes.count(f) + 1.5 * cuenta.get(f, 0)          # descanso: lo de hace poco, y lo muy usado, vale menos
            if cuenta.get(f, 0) >= tope:
                n -= 30                                                    # tope por video
            if c.get('reel') == 'golpe' and golpes and (k - golpes[-1] < 6 or len(golpes) >= max(1, len(segs) // 8)):
                n -= 40                                                    # el golpe, pocas veces
            if n > nota:
                mejor, nota = c, n
        mejor = dict(mejor) if mejor else {'tipo': 'reel', 'reel': 'aviso', 'wp': {}, 'peso': 0, '_general': True}
        out.append(mejor)
        if not mejor.get('_sigue'):
            f = _familia(mejor)
            cuenta[f] = cuenta.get(f, 0) + 1
            if mejor.get('reel') == 'golpe':
                golpes.append(k)
    return out


def _variar(escenas):
    """El color y el lado de cada tarjeta: nunca el mismo color seguido ni el que tuvo esa tarjeta la última vez; la mitad entra desde abajo y
    la otra mitad desde un lado (alternando)."""
    ultimo_de, prev = {}, None
    lados = (0, 1, 0, -1)
    for i, e in enumerate(escenas):
        clave = e.get('reel') or e['tipo']
        opciones = [p for p in PALETAS if p != prev and p != ultimo_de.get(clave)] or list(PALETAS)
        pal = 'azul' if i == 0 else opciones[(i * 7 + len(clave)) % len(opciones)]
        e['paleta'] = pal
        ultimo_de[clave], prev = pal, pal
        e['lado'] = 0 if clave in ('chat', 'golpe', 'largo', 'cuenta') else lados[i % len(lados)]


def _fotogramas(video, escenas, maximo=10, alto=720):
    """Los fotogramas del video del usuario para las tarjetas que los llevan (CON_FOTO), del momento en que se dicen: [data:image/jpeg…] y
    `img` (su índice) en cada escena. PyAV + Pillow (van en el programa)."""
    import base64
    import io
    quieren = [e for e in escenas if (e.get('reel') in CON_FOTO)][:maximo]
    if not quieren:
        return []
    fotos = []
    try:
        import av
        with av.open(str(video)) as cont:
            flujo = cont.streams.video[0]
            for e in quieren:
                t = (float(e['ini']) + float(e['fin'])) / 2.0
                try:
                    cont.seek(int(t / float(flujo.time_base)), stream=flujo, any_frame=False, backward=True)
                    img = None
                    for cuadro in cont.decode(flujo):
                        if cuadro.pts is None or float(cuadro.pts * flujo.time_base) >= t - 0.05:
                            img = cuadro.to_image()
                            break
                    if img is None:
                        continue
                    if img.height > alto:
                        img = img.resize((max(2, int(img.width * alto / img.height)), alto))
                    buf = io.BytesIO()
                    img.convert('RGB').save(buf, 'JPEG', quality=80)
                    e['img'] = len(fotos)
                    fotos.append('data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii'))
                except Exception:
                    continue
    except Exception:
        return []
    return fotos


# lo que suena en cada tarjeta (segundos desde que entra): clics del cursor, pops, el pin, el sello…
SFX = {'rec': [('click', 0.85)], 'reloj': [('ui', 0.12)], 'archivos': [('pop', 0.15), ('click', 0.5)], 'buscar': [('click', 0.4), ('correcto', 0.5)],
       'cortar': [('tijera', 0.45)], 'movil': [('pop', 0.5)], 'chat': [('pop', 0.05)], 'abc': [('click', 0.65)], 'ideas': [('pop', 0.3)],
       'fecha': [('click', 0.9), ('correcto', 0.95)], 'lugar': [('pin', 0.45)], 'entrada': [('sello', 0.6)], 'personas': [('pop', 0.15)],
       'musica': [('click', 0.72)], 'premio': [('correcto', 0.3)], 'compartir': [('click', 0.68), ('correcto', 1.0)], 'aviso': [('ui', 0.1)],
       'lista': [('click', 0.37), ('click', 0.59), ('click', 0.81)], 'buscador': [('teclado', 0.15)], 'post': [('pop', 0.6)], 'encuesta': [('click', 0.7)],
       'carga': [('correcto', 1.5)], 'nota': [('papel', 0.05)], 'antesdespues': [('ui', 0.35)], 'cuenta': [('ui', 0.6)], 'grafica': [('pop', 0.9)],
       'golpe': [('hit', 0.0)], 'orbita': [('ui', 0.2)], 'ruta': [('ui', 0.2)], 'conectores': [('click', 0.6)], 'contador': [('ui', 0.2)],
       'versiones': [('click', 0.6)]}


def sonidos(mp4, fps, rng=None, voz_db=None):
    """v5.5.9 (el usuario: sonido sincronizado): un whoosh en cada entrada de tarjeta y los clics/pops de lo que pasa dentro, con la biblioteca
    de la PRO (edicion_pro_sonido), para el video de motions `mp4` (lee su .json). Eventos como los de la PRO: {'pista', 'ini' (cuadros), …}."""
    import random
    try:
        import edicion_pro_sonido as PS
        datos = json.loads(Path(mp4).with_suffix('.json').read_text(encoding='utf-8'))
    except Exception:
        return []
    rng = rng or random.Random(7)
    ev = []
    for k, e in enumerate(datos.get('escenas') or []):
        ini = float(e['ini'])
        if k > 0:
            ev.append(('whoosh', ini + 0.12, 'pico', PS.NIVEL['whoosh'] - 3.0, 'motions · entra'))
        for clave, dt in SFX.get(e.get('reel') or e.get('tipo'), ()):
            ev.append((clave, ini + dt, 'ataque', PS.NIVEL['textura'] - (2.0 if clave != 'hit' else 0.0), f'motions · {e.get("reel") or e.get("tipo")}'))
    out = []
    for clave, t, ancla, nivel, que in ev:
        try:
            f, info = PS._elegir(clave, rng, ancla=ancla, hasta=t)
        except Exception:
            f = None
        if f is None:
            continue
        familia = 'whoosh' if clave == 'whoosh' else ('hit' if clave == 'hit' else 'textura')
        out.append({'pista': PS.PISTAS[familia], 'ini': int(round((t - info[ancla]) * fps)), 'archivo': str(f), 'dur': min(2.0, info['dur']),
                    'db': PS._nivel(familia, nivel, info, voz_db), 'que': que, 'sinc': True})   # sinc: va con lo que pasa DENTRO del video de motions
    return out


# ----------------------------------------------------------------------------------------------------------------------------------- render
def crear(bloques, dur, W, H, fps, carpeta, idioma='es', perfil=None, video='', decir=None, ia=True, estilo=None):
    """Planifica y renderiza el video de motions (H.264 opaco, del largo del video). Devuelve su ruta o None. Con caché por contenido.
    v5.20: `estilo` (estilos_pro.motions_completo: fondo, tema, acento, paleta fija) = el que el usuario eligió en Efectos."""
    decir = decir or (lambda t: None)
    try:
        import edicion_pro_remotion as RM
    except Exception:
        return None
    if not RM.disponible():
        decir('Motions completo: falta el motor de animaciones (Remotion)')
        return None
    decir('Motions completo: eligiendo una tarjeta para cada momento…')
    props = planificar(bloques, dur, idioma, perfil, video, H > W, ia, decir)
    if not props or not props['escenas']:
        return None
    props.update(estilo or {})
    props.update(_ancho=int(W), _alto=int(H), _fps=float(fps), _dur=round(float(dur), 3))
    huella = hashlib.sha1(json.dumps(props, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:14]
    salida = Path(carpeta) / f'motions_completo_{huella}.mp4'
    try:                                                                   # lo que pasa y cuándo (sin fotos): de aquí salen sus sonidos
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.with_suffix('.json').write_text(json.dumps({'escenas': props['escenas']}, ensure_ascii=False), encoding='utf-8')
    except OSError:
        pass
    if salida.exists() and salida.stat().st_size > 50_000:
        return salida
    tipos = {}
    for e in props['escenas']:
        f = e.get('reel') or e['tipo']
        tipos[f] = tipos.get(f, 0) + 1
    resumen = ', '.join(f'{n} {t}' for t, n in sorted(tipos.items(), key=lambda x: -x[1]))
    decir(f"Motions completo: {len(props['escenas'])} motions ({resumen}); animando…")
    ok = _renderizar(RM, props, salida, dur, decir)
    try:
        import registro
        if ok:
            registro.info(f"Motions completo: {len(props['escenas'])} motions en {salida.name} ({salida.stat().st_size / 1e6:.0f} MB): {resumen}.", 'motions')
        else:
            registro.aviso('Motions completo: Remotion no pudo hacer el video de motions; el resto de la edición queda igual.', 'motions')
    except Exception:
        pass
    return salida if ok else None


def _renderizar(RM, props, salida, dur, decir, comp='MotionsCompleto'):
    """Una llamada a render.mjs (modo opaco) leyendo su avance línea a línea."""
    salida.parent.mkdir(parents=True, exist_ok=True)
    RM._permisos()
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'bundle': str(RM.bundle()), 'navegador': RM._chrome(),
                   'trabajos': [{'id': comp, 'props': props, 'salida': str(salida), 'opaco': True}]}, f, ensure_ascii=False)     # (v5.5.17: el Tema 1, KitNeon)
        ruta = f.name
    hecho = False
    try:
        mjs = RM._render_mjs()
        p = subprocess.Popen([RM._node(), str(mjs), ruta], cwd=str(mjs.parent), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                             encoding='utf-8', errors='replace', **RM.opciones_proceso())
        tope = time.time() + max(900.0, float(dur) * 25.0)
        for linea in p.stdout:
            try:
                r = json.loads(linea)
            except ValueError:
                continue
            if 'progreso' in r:
                decir(f"Motions completo: animando… {int(float(r['progreso']) * 100)} %")
            elif r.get('hecho'):
                hecho = True
            if time.time() > tope:
                p.kill()
                break
        p.wait(timeout=60)
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass
    return hecho and salida.exists() and salida.stat().st_size > 50_000
