# CineCaptions · By Cinema Productions
# 1_codigo/sfx_rules.py — decide el efecto de sonido de cada bloque leyendo resolve_scripts/sfx_rules.json.
"""\nsfx_rules.py\n------------\nDecide que efecto de sonido le toca a cada bloque de subtitulo.\n\nLa logica de decision NO vive aca: vive en resolve_scripts/sfx_rules.json.\nEste modulo solo sabe LEER esas reglas y evaluarlas. Para cambiar cuando\nsuena que cosa, o para agregar una categoria nueva, se edita el JSON — no\nhace falta tocar este archivo.\n\nComo encaja en el resto:\n  1. Aca se le pone a cada bloque su categoria (\"risers\", \"pops\"...).\n  2. Eso se guarda en el .dynamic.json, junto a las lineas del subtitulo.\n  3. El script que corre dentro de Resolve lee esa categoria, elige un audio\n     de la carpeta correspondiente y lo coloca en una pista de audio.\n"""
import bisect
import json
import os
import random
import re
import shutil
import sys
import unicodedata
from pathlib import Path
CARPETA_USUARIO = Path.home() / 'DaVinciSubtitles'
ARCHIVO_FAVORITOS = CARPETA_USUARIO / 'sfx_favoritos.json'
ARCHIVO_CARPETAS = CARPETA_USUARIO / 'sfx_carpetas_usuario.json'
ARCHIVO_MODO = CARPETA_USUARIO / 'sfx_modo.json'
# Modo simple: un efecto al PRINCIPIO de cada bloque, alternando dos sonidos (los de fábrica van en
# sfx_library/Modo simple; el usuario puede cambiarlos desde la pantalla Sonido)
CATEGORIA_SIMPLE = 'Modo simple'
SONIDOS_SIMPLES_DE_FABRICA = ('TAP_POP.mp3', 'typewriter copy.mp3', 'Iphone Taping.wav')
# (5.3) El modo simple tiene 3 secciones: al inicio de cada palabra/bloque, la introducción (primer bloque: un riser) y el final
# (último bloque: un boom). Cada una guarda sonidos para variar (el usuario los cambia desde la pantalla Sonido). v5.5: el sonido por palabra alterna TRES
# (TAP_POP, typewriter, Iphone Taping) y el riser de la introducción de fábrica es el «Viral Hooks Riser».
CATEGORIA_INTRO = 'Modo simple · Introducción'
CATEGORIA_FINAL = 'Modo simple · Final'
SECCIONES_SIMPLES = {'inicio': ('Modo simple', SONIDOS_SIMPLES_DE_FABRICA),
                     'intro': ('Riser', ('Viral Hooks Riser.mp3', 'Riser 2.wav')),
                     'final': ('Bass Hit', ('Bass Hit 1.wav', 'Bass Hit 2.wav'))}
CATEGORIA_DE_SECCION = {'inicio': CATEGORIA_SIMPLE, 'intro': CATEGORIA_INTRO, 'final': CATEGORIA_FINAL}
CUANTOS_SIMPLES = {'inicio': 3, 'intro': 2, 'final': 2}          # cuántos sonidos guarda cada sección
# v5.5: en QUÉ palabras suena el modo simple: en todas, solo en la principal (la grande / el héroe / la del efecto) o en ninguna (quedan la introducción y el final)
DONDE_SIMPLE = ('todas', 'principal', 'ninguna')
# v5.4.29: las tarjetas de la pantalla Sonido que se pueden apagar enteras (palabra = «Sonido por palabra», principal = «Sonido del texto principal», introducción y final)
TARJETAS_SONIDO = ('palabra', 'principal', 'intro', 'final')
def _leer_lista(archivo):
    try:
        datos = json.loads(Path(archivo).read_text(encoding='utf-8'))
        if isinstance(datos, list):
            return [str(x) for x in datos]
    except Exception:
        pass
    return []
def _escribir_lista(archivo, lista):
    try:
        archivo = Path(archivo)
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(json.dumps(list(lista), ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        return None
def cargar_favoritos():
    return set(_leer_lista(ARCHIVO_FAVORITOS))
def guardar_favoritos(favoritos):
    _escribir_lista(ARCHIVO_FAVORITOS, sorted(favoritos))
def cargar_carpetas_usuario():
    return _leer_lista(ARCHIVO_CARPETAS)
def guardar_carpetas_usuario(carpetas):
    _escribir_lista(ARCHIVO_CARPETAS, carpetas)
def cargar_modo():
    """{'modo': 'simple' | 'avanzado', 'donde': 'todas' | 'principal' | 'ninguna', 'sonidos': [3 del inicio], 'intro': [2], 'final': [2]} que dejó el usuario. Por defecto: simple, en todas las palabras."""
    try:
        datos = json.loads(ARCHIVO_MODO.read_text(encoding='utf-8'))
    except Exception:
        datos = {}
    if not isinstance(datos, dict):
        datos = {}
    modo = 'simple'                      # v5.4.29: el modo «Avanzado» ya no existe en la pantalla Sonido: aunque un archivo viejo diga 'avanzado', manda siempre el simple
    salida = {'modo': modo, 'donde': datos.get('donde') if datos.get('donde') in DONDE_SIMPLE else 'todas'}
    for clave in ('sonidos', 'intro', 'final'):
        salida[clave] = [str(x) for x in (datos.get(clave) or []) if isinstance(x, str)][:CUANTOS_SIMPLES[{'sonidos': 'inicio'}.get(clave, clave)]]
    # v5.4.29: el efecto sonoro que el usuario elige para la palabra PRINCIPAL (vacío = automático: el sonido propio de cada efecto del estilo) y el interruptor de cada tarjeta
    salida['principal'] = [str(x) for x in (datos.get('principal') or []) if isinstance(x, str)][:1]
    crudas = datos.get('activas') if isinstance(datos.get('activas'), dict) else {}
    salida['activas'] = {k: crudas.get(k) is not False for k in TARJETAS_SONIDO}
    return salida
def guardar_modo(modo=None, sonidos=None, intro=None, final=None, donde=None, principal=None, activas=None):
    """Guarda el modo, en qué palabras suena el modo simple, los sonidos de cada sección, el sonido elegido para la principal y/o los interruptores de las tarjetas (lo que no se pasa se conserva)."""
    actual = cargar_modo()
    if modo in ('simple', 'avanzado'):
        actual['modo'] = modo
    if donde in DONDE_SIMPLE:
        actual['donde'] = donde
    for clave, valor in (('sonidos', sonidos), ('intro', intro), ('final', final)):
        if valor is not None:
            actual[clave] = [str(x) for x in valor][:CUANTOS_SIMPLES[{'sonidos': 'inicio'}.get(clave, clave)]]
    if principal is not None:
        actual['principal'] = [str(x) for x in principal][:1]
    if isinstance(activas, dict):
        actual['activas'] = {k: bool(activas.get(k, actual['activas'].get(k, True))) for k in TARJETAS_SONIDO}
    try:
        CARPETA_USUARIO.mkdir(parents=True, exist_ok=True)
        ARCHIVO_MODO.write_text(json.dumps(actual, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        return None
def sonido_principal():
    """El efecto sonoro que el usuario eligió para la palabra principal (Path), o None = automático (el sonido propio de cada efecto del estilo)."""
    for r in cargar_modo()['principal']:
        if Path(r).is_file():
            return Path(r)
    return None
def sonidos_de_fabrica(seccion='inicio'):
    """Los dos sonidos con los que viene cada sección del modo simple (dentro del programa)."""
    carpeta, nombres = SECCIONES_SIMPLES[seccion]
    base = base_recursos() / 'sfx_library' / carpeta
    return [base / nombre for nombre in nombres]
def sonidos_simples(seccion='inicio'):
    """Las rutas que usa una sección del modo simple: las que eligió el usuario y, donde no eligió (o el archivo ya
    no existe), las de fábrica. Solo devuelve archivos que existen."""
    clave = {'inicio': 'sonidos'}.get(seccion, seccion)
    elegidos = cargar_modo()[clave]
    fabrica = sonidos_de_fabrica(seccion)
    salida = []
    for i in range(CUANTOS_SIMPLES[seccion]):
        propio = Path(elegidos[i]) if i < len(elegidos) else None
        if propio is not None and propio.is_file():
            salida.append(propio)
        elif fabrica[i].is_file():
            salida.append(fabrica[i])
    return salida
def base_recursos():
    """Donde viven los archivos que acompañan al programa.\n\n    Compilado con PyInstaller, los datos se extraen a una carpeta temporal\n    que se anuncia en sys._MEIPASS; sin compilar, es la carpeta del proyecto.\n    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).resolve().parent.parent / '2_recursos'
def ruta_reglas():
    """El sfx_rules.json del usuario si lo hay; si no, el que trae el programa."""
    propia = CARPETA_USUARIO / 'sfx_rules.json'
    if propia.exists():
        return propia
    else:
        return base_recursos() / 'resolve_scripts' / 'sfx_rules.json'
def carpeta_libreria():
    """La sfx_library del usuario si la hay; si no, la que trae el programa."""
    propia = CARPETA_USUARIO / 'sfx_library'
    if propia.is_dir():
        return propia
    else:
        return base_recursos() / 'sfx_library'
CARPETA_SFX_USADOS = CARPETA_USUARIO / 'sfx_usados'
def ruta_persistente(ruta, carpeta=None):
    """La ruta que puede viajar a Resolve sin morirse al cerrar el programa.

    Un archivo de dentro del programa se copia UNA vez (misma ruta relativa;
    se re-copia si cambia de tamaño) y se devuelve la copia, del mismo tipo
    que la entrada (str o Path). Cualquier otra ruta sale tal cual. Si copiar
    falla (disco lleno, sin permiso) sale la original: nunca peor que antes.
    'carpeta' elige donde van las copias (los emojis van a la suya).
    """
    origen = Path(ruta)
    try:
        relativa = origen.resolve().relative_to(base_recursos().resolve())
    except (ValueError, OSError):
        return ruta
    destino = Path(carpeta or CARPETA_SFX_USADOS) / relativa
    try:
        if (not destino.is_file()
                or destino.stat().st_size != origen.stat().st_size):
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporal = destino.with_name(destino.name + '.copiando')
            shutil.copyfile(origen, temporal)
            os.replace(temporal, destino)
    except OSError:
        return ruta
    return type(ruta)(destino)
# ---------------------------------------------------------------------------------------------------------------------
# (5.3) Volumen por sonido y ajustes del modo Avanzado. Todo se guarda en ~/DaVinciSubtitles y se usa al generar (GO).
ARCHIVO_VOLUMENES = CARPETA_USUARIO / 'sfx_volumenes.json'
ARCHIVO_AVANZADO = CARPETA_USUARIO / 'sfx_avanzado.json'
CARPETA_SFX_VOLUMEN = CARPETA_USUARIO / 'sfx_volumen'
# Las reglas por bloque que se activan con un interruptor en el modo Avanzado (gana la primera que se cumple, de arriba abajo)
REGLAS_PREDEFINIDAS = (
    # v5.5: el modo Avanzado decide PALABRA POR PALABRA (como el simple): cada regla mira la palabra que va a sonar y su
    # entorno (pausas, bloque, rol). Todas vienen APAGADAS: el usuario enciende solo lo que quiere. 'explicacion' es el
    # texto largo que se ve al pasar el mouse por la tarjeta.
    # v5.5.3: reglas por TEMA (la palabra dicha elige el sonido de las categorías nuevas). Van primero (lo concreto gana a lo
    # genérico) y vienen ENCENDIDAS: solo suenan en esas palabras.
    {'id': 'tema_dinero', 'nombre': 'Dinero', 'categoria': 'Dinero', 'on': True,
     'cuando': {'texto_contiene': ['dinero', 'plata', 'pesos', 'dolares', 'euros', 'quetzales', 'pagar', 'pago', 'precio', 'ventas', 'vender',
                                   'ganancias', 'millones', 'millonario', 'rico', 'money', 'cash', 'dollars', 'price', 'sales', 'rich', 'millions']},
     'descripcion': 'Palabras de dinero y precios.', 'explicacion': 'Suena la caja registradora cuando dices dinero, precio, ventas, millones…'},
    {'id': 'tema_tiempo', 'nombre': 'Tiempo', 'categoria': 'Tiempo', 'on': True,
     'cuando': {'texto_contiene': ['tiempo', 'reloj', 'minuto', 'minutos', 'segundo', 'segundos', 'hora', 'horas', 'cronometro',
                                   'time', 'clock', 'minute', 'minutes', 'seconds', 'hours', 'timer', 'deadline']},
     'descripcion': 'Palabras de tiempo.', 'explicacion': 'Suena un tic-tac de cronómetro cuando dices tiempo, minutos, horas, reloj…'},
    {'id': 'tema_aplausos', 'nombre': 'Logros y felicitaciones', 'categoria': 'Aplausos', 'on': True,
     'cuando': {'texto_contiene': ['aplausos', 'aplauso', 'felicidades', 'felicitaciones', 'bravo', 'logramos', 'exito', 'ganamos',
                                   'applause', 'congratulations', 'congrats', 'success']},
     'descripcion': 'Felicitaciones y logros.', 'explicacion': 'Suenan aplausos cuando dices felicidades, bravo, éxito, lo logramos…'},
    {'id': 'tema_correcto', 'nombre': 'Correcto', 'categoria': 'Correcto', 'on': True,
     'cuando': {'texto_contiene': ['correcto', 'exacto', 'perfecto', 'acertaste', 'aprobado', 'correct', 'perfect', 'exactly', 'approved']},
     'descripcion': 'Algo está bien.', 'explicacion': 'Suena el «acierto» (✓) cuando dices correcto, exacto, perfecto…'},
    {'id': 'tema_error', 'nombre': 'Error', 'categoria': 'Error', 'on': True,
     'cuando': {'texto_contiene': ['error', 'errores', 'incorrecto', 'falso', 'fallo', 'falla', 'equivocado', 'equivocas',
                                   'wrong', 'mistake', 'mistakes', 'fail', 'failed', 'false']},
     'descripcion': 'Algo está mal.', 'explicacion': 'Suena el «error» (✗) cuando dices error, falso, incorrecto, equivocado…'},
    {'id': 'tema_camara', 'nombre': 'Cámara y fotos', 'categoria': 'Cámara', 'on': True,
     'cuando': {'texto_contiene': ['camara', 'foto', 'fotos', 'fotografia', 'fotografo', 'selfie', 'camera', 'photo', 'photos', 'photography', 'picture']},
     'descripcion': 'Fotos y cámaras.', 'explicacion': 'Suena el obturador cuando dices foto, cámara, selfie…'},
    {'id': 'tema_corazon', 'nombre': 'Corazón y nervios', 'categoria': 'Latidos', 'on': True,
     'cuando': {'texto_contiene': ['corazon', 'latido', 'latidos', 'nervios', 'nervioso', 'nerviosa', 'heart', 'heartbeat', 'nervous']},
     'descripcion': 'Corazón y nervios.', 'explicacion': 'Suena un latido cuando dices corazón, nervios, latido…'},
    {'id': 'tema_idea', 'nombre': 'Ideas y secretos', 'categoria': 'Idea', 'on': True,
     'cuando': {'texto_contiene': ['idea', 'ideas', 'imagina', 'imaginate', 'secreto', 'truco', 'consejo', 'imagine', 'secret', 'trick']},
     'descripcion': 'Ideas, trucos y secretos.', 'explicacion': 'Suena un brillo de «idea» cuando dices idea, secreto, truco, imagina…'},
    {'id': 'tema_explosion', 'nombre': 'Explosiones', 'categoria': 'Explosiones', 'on': True,
     'cuando': {'texto_contiene': ['explosion', 'explota', 'exploto', 'boom', 'bomba', 'revienta', 'explode', 'exploded', 'bomb']},
     'descripcion': 'Explosiones.', 'explicacion': 'Suena una explosión cuando dices boom, explota, bomba…'},
    {'id': 'tema_fiesta', 'nombre': 'Fiesta y cumpleaños', 'categoria': 'Fiesta', 'on': True,
     'cuando': {'texto_contiene': ['fiesta', 'celebrar', 'celebracion', 'cumpleanos', 'party', 'celebrate', 'birthday']},
     'descripcion': 'Fiestas.', 'explicacion': 'Suena la fiesta cuando dices fiesta, celebrar, cumpleaños…'},
    {'id': 'tema_pirotecnia', 'nombre': 'Fuegos artificiales', 'categoria': 'Pirotecnia', 'on': True,
     'cuando': {'texto_contiene': ['fuegos', 'pirotecnia', 'cohetes', 'fireworks']},
     'descripcion': 'Fuegos artificiales.', 'explicacion': 'Suenan fuegos artificiales cuando dices fuegos, pirotecnia, cohetes…'},
    {'id': 'primero', 'nombre': 'Primera palabra', 'categoria': 'Whoosh', 'cuando': {'es_primer_bloque': True}, 'on': False,
     'descripcion': 'Arranque del video.',
     'explicacion': 'Suena en la PRIMERA palabra del video: un whoosh que abre. Solo una vez.'},
    {'id': 'ultimo', 'nombre': 'Última palabra', 'categoria': 'Power Down', 'cuando': {'es_ultimo_bloque': True}, 'on': False,
     'descripcion': 'Cierre del video.',
     'explicacion': 'Suena en la ÚLTIMA palabra del video: baja la energía para cerrar. Solo una vez.'},
    {'id': 'pregunta', 'nombre': 'Palabra que cierra una pregunta (?)', 'categoria': 'Riser', 'cuando': {'texto_termina_en': ['?']}, 'on': False,
     'descripcion': 'La palabra que termina en «?».',
     'explicacion': 'Suena en cada palabra que termina en «?»: el riser levanta la tensión justo antes de la respuesta.'},
    {'id': 'exclamacion', 'nombre': 'Palabra que cierra una exclamación (!)', 'categoria': 'Slams', 'cuando': {'texto_termina_en': ['!']}, 'on': False,
     'descripcion': 'La palabra que termina en «!».',
     'explicacion': 'Suena en cada palabra que termina en «!»: un impacto seco que subraya la emoción.'},
    {'id': 'gritos', 'nombre': 'Palabra en MAYÚSCULAS', 'categoria': 'Hit', 'cuando': {'texto_en_mayusculas': True}, 'on': False,
     'descripcion': 'Palabras escritas en mayúsculas.',
     'explicacion': 'Suena en cada palabra escrita en MAYÚSCULAS (de 2 letras o más): las que gritas o quieres destacar.'},
    {'id': 'cifras', 'nombre': 'Cifras y precios', 'categoria': 'Bass Hit', 'cuando': {'texto_contiene_numero': True}, 'on': False,
     'descripcion': 'Palabras con números.',
     'explicacion': 'Suena en cada palabra que lleva un número (precios, años, porcentajes): el golpe grave subraya el dato.'},
    {'id': 'pausa_larga', 'nombre': 'Tras una pausa larga (> 1,2 s)', 'categoria': 'Glitch', 'cuando': {'pausa_antes_mayor_a': 1.2},
     'on': False, 'descripcion': 'Primera palabra después de un silencio largo.',
     'explicacion': 'Suena en la palabra que llega después de más de 1,2 s de silencio: marca un cambio brusco de tema.'},
    {'id': 'pausa_media', 'nombre': 'Tras una pausa media (> 0,6 s)', 'categoria': 'Whoosh', 'cuando': {'pausa_antes_mayor_a': 0.6},
     'on': False, 'descripcion': 'Primera palabra después de un respiro.',
     'explicacion': 'Suena en la palabra que llega después de más de 0,6 s de silencio: un cambio de tema suave. Gana la pausa larga si está encendida.'},
    {'id': 'una_palabra', 'nombre': 'Palabra que va sola', 'categoria': 'Click', 'cuando': {'solo_una_palabra': True}, 'on': False,
     'descripcion': 'Bloques de una sola palabra.',
     'explicacion': 'Suena en las palabras que forman un bloque ellas solas en pantalla.'},
    {'id': 'largo', 'nombre': 'Inicio de un bloque largo (≥ 7 palabras)', 'categoria': 'Slices', 'cuando': {'palabras_minimo': 7, 'es_primera_del_bloque': True}, 'on': False,
     'descripcion': 'Primera palabra de las frases largas.',
     'explicacion': 'Suena en la primera palabra de un bloque con 7 palabras o más: avisa que viene una frase larga.'},
    {'id': 'cada_5', 'nombre': 'Cada 5 palabras', 'categoria': 'Click', 'cuando': {'cada_n_bloques': 5}, 'on': False,
     'descripcion': 'Un golpe de ritmo cada 5 palabras.',
     'explicacion': 'Suena en una de cada 5 palabras, de forma regular: marca el ritmo aunque no pase nada especial.'},
    {'id': 'tres_lineas', 'nombre': 'Palabra principal de un bloque de 3 líneas', 'categoria': 'Hit',
     'cuando': {'roles_incluyen': ['context', 'main', 'complement'], 'rol_es': ['main']}, 'on': False,
     'descripcion': 'La palabra clave de los bloques completos.',
     'explicacion': 'Suena en la palabra PRINCIPAL (la que va grande) de los bloques que traen las tres líneas: arriba, principal y abajo.'},
)
AJUSTES_AVANZADO_BASE = {'probabilidad': 100, 'max_por_minuto': 0, 'omitir_inicio_s': 0.0, 'omitir_final_s': 0.0,
                         'no_repetir_categoria': False, 'minimo_segundos': 0.25, 'solo_destacados': False,
                         'volumen_global_db': 0.0, 'categoria_por_defecto': None, 'reglas': {}}
def _leer_dic(archivo):
    try:
        d = json.loads(Path(archivo).read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}
def _escribir_dic(archivo, datos):
    try:
        archivo = Path(archivo)
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        return None
def cargar_volumenes():
    return {str(k): float(v) for k, v in _leer_dic(ARCHIVO_VOLUMENES).items() if isinstance(v, (int, float))}
def _clave_ruta(ruta):
    return os.path.normcase(os.path.abspath(str(ruta)))
def volumen_de(ruta):
    """El volumen guardado para un sonido (1.0 = como viene)."""
    return cargar_volumenes().get(_clave_ruta(ruta), 1.0)
def guardar_volumen(ruta, factor):
    datos = cargar_volumenes()
    factor = max(0.0, min(2.0, float(factor)))
    if abs(factor - 1.0) < 0.005:
        datos.pop(_clave_ruta(ruta), None)
    else:
        datos[_clave_ruta(ruta)] = round(factor, 3)
    _escribir_dic(ARCHIVO_VOLUMENES, datos)
ARCHIVO_RECORTES = CARPETA_USUARIO / 'sfx_recortes.json'
PREFIJO_REGLA = 'Regla · '
def cargar_recortes():
    """{ruta: [inicio_s, fin_s]} de los sonidos a los que se les eligió una parte (ventana «Editar»)."""
    salida = {}
    for k, v in _leer_dic(ARCHIVO_RECORTES).items():
        try:
            if isinstance(v, (list, tuple)) and len(v) == 2 and float(v[1]) > float(v[0]) >= 0.0:
                salida[str(k)] = (float(v[0]), float(v[1]))
        except (TypeError, ValueError):
            pass
    return salida
# v5.5: la parte buena de los sonidos de fábrica del modo simple (el TAP_POP dura 1,07 s con un chasquido de 70 ms; el typewriter son 7,5 s de teclas y sólo suena UNA). Antes
# esto sólo existía como recorte guardado por el usuario en SU instalación (ruta absoluta), así que un programa recién instalado sonaba con el archivo entero (el primer golpe del
# typewriter llega al segundo 1,4: cada palabra sonaba tarde). Lo que el usuario recorte con «Editar» manda sobre esto.
RECORTES_DE_FABRICA = {'modo simple/tap_pop.mp3': (0.048, 0.119), 'modo simple/typewriter copy.mp3': (1.339, 1.523)}
def _de_fabrica(ruta):
    """La clave 'carpeta/archivo' (minúsculas) si el sonido está dentro de la biblioteca que trae el programa o su copia en _internal; si no, None."""
    p = Path(str(ruta))
    if 'sfx_library' not in [x.lower() for x in p.parts]:
        return None
    return f'{p.parent.name}/{p.name}'.lower()
def recorte_de(ruta):
    """(inicio_s, fin_s) guardado para un sonido, o None si se usa entero. Los sonidos de fábrica del modo simple traen su recorte."""
    propio = cargar_recortes().get(_clave_ruta(ruta))
    if propio:
        return propio
    return RECORTES_DE_FABRICA.get(_de_fabrica(ruta) or '')
def guardar_recorte(ruta, inicio, fin, duracion=None):
    """Guarda la parte del sonido que se usa. Si cubre todo el archivo se borra el recorte."""
    datos = {k: list(v) for k, v in cargar_recortes().items()}
    inicio, fin = max(0.0, float(inicio)), float(fin)
    entero = inicio <= 0.005 and (duracion is not None and fin >= float(duracion) - 0.005)
    if entero or fin <= inicio:
        datos.pop(_clave_ruta(ruta), None)
    else:
        datos[_clave_ruta(ruta)] = [round(inicio, 3), round(fin, 3)]
    _escribir_dic(ARCHIVO_RECORTES, datos)
def cargar_avanzado():
    datos = _leer_dic(ARCHIVO_AVANZADO)
    ajustes = dict(AJUSTES_AVANZADO_BASE)
    for k in ajustes:
        if k in datos:
            ajustes[k] = datos[k]
    if not isinstance(ajustes['reglas'], dict):
        ajustes['reglas'] = {}
    return ajustes
def guardar_avanzado(**cambios):
    datos = cargar_avanzado()
    datos.update(cambios)
    _escribir_dic(ARCHIVO_AVANZADO, datos)
def reglas_activas():
    """[{categoria, cuando, descripcion}] de las reglas predefinidas encendidas, con la categoría que eligió el usuario."""
    guardado = cargar_avanzado()['reglas']
    salida = []
    for r in REGLAS_PREDEFINIDAS:
        g = guardado.get(r['id']) or {}
        if g.get('on', r['on']):
            categoria = g.get('categoria', r['categoria'])
            if sonido_de_regla(r['id']):
                categoria = PREFIJO_REGLA + r['id']          # (5.3) la regla usa UN sonido concreto (el que eligió en «Editar»)
            salida.append({'categoria': categoria, 'cuando': r['cuando'], 'descripcion': r['descripcion']})
    return salida
def sonido_de_regla(id_):
    """La ruta del sonido concreto que el usuario eligió para una regla, o None (= cualquiera de su categoría)."""
    ruta = (cargar_avanzado()['reglas'].get(id_) or {}).get('sonido')
    return str(ruta) if ruta and Path(str(ruta)).is_file() else None
# v5.4.8 (S1): normalizar el volumen de los sonidos. Cada sonido se mide una vez (RMS con puerta: solo cuentan los tramos que suenan, no el silencio de la cola) y se sube o baja
# hasta el nivel objetivo; el pico nunca pasa de -1 dBFS. Así un whoosh de una carpeta y un hit de otra suenan igual de fuerte, y el volumen que el usuario fija por sonido o
# el general se suma encima de esa base uniforme. Se apaga con la preferencia sfx_normalizar (SFX Lab / Sonido).
OBJETIVO_DB_DEFECTO = -20.0
ARCHIVO_NIVELES = CARPETA_USUARIO / 'sfx_niveles.json'
def normalizar_activo():
    try:
        import ajustes_ui
        return ajustes_ui.leer_prefs().get('sfx_normalizar', True) is not False
    except Exception:
        return True
def objetivo_db():
    try:
        import ajustes_ui
        return float(ajustes_ui.leer_prefs().get('sfx_objetivo_db', OBJETIVO_DB_DEFECTO))
    except Exception:
        return OBJETIVO_DB_DEFECTO
def nivel_de_audio(audio, sr):
    """(rms_db con puerta, pico_db) de un sonido (array mono o estéreo float). Ventanas de 50 ms: solo cuentan las que están a menos de 30 dB de la más fuerte (y por encima de -70 dBFS)."""
    import numpy as np
    a = np.asarray(audio, dtype='float32')
    if a.ndim > 1:
        a = a.mean(axis=1)
    if not len(a):
        return -120.0, -120.0
    pico = float(np.max(np.abs(a)))
    n = max(1, int(sr * 0.05))
    k = len(a) // n
    if k < 1:
        rms = float(np.sqrt(np.mean(a ** 2)))
        return 20 * np.log10(max(rms, 1e-9)), 20 * np.log10(max(pico, 1e-9))
    potencia = (a[:k * n].reshape(k, n) ** 2).mean(axis=1)
    db = 10 * np.log10(np.maximum(potencia, 1e-12))
    sirve = db >= max(float(db.max()) - 30.0, -70.0)
    rms_db = float(10 * np.log10(max(float(potencia[sirve].mean()), 1e-12)))
    return rms_db, float(20 * np.log10(max(pico, 1e-9)))
# v5.4.51: el objetivo fijo (-20 dB) dejaba los efectos casi tan fuertes como la voz: con «un toque por palabra» (Temas 2 y 4) abrumaba. Ahora,
# si se conoce la voz del video (fijar_voz, lo llama GO al preparar los sonidos), cada efecto queda POR DEBAJO de ella: los de cada palabra
# BAJO_LA_VOZ_PALABRA dB (una textura, no un golpe) y los demás (palabra principal, emojis, intro) BAJO_LA_VOZ_EFECTO dB. Nunca más fuerte que el
# objetivo del usuario.
BAJO_LA_VOZ_PALABRA, BAJO_LA_VOZ_EFECTO = 14.0, 9.0
_VOZ = {'ruta': None, 'db': None}


def fijar_voz(ruta_video):
    """Mide (una vez por archivo) lo fuerte que suena la voz del video con la misma medida que los efectos (nivel_de_audio) y la recuerda. dB o None."""
    try:
        clave = str(Path(str(ruta_video)).resolve())
    except Exception:
        return None
    if _VOZ['ruta'] == clave:
        return _VOZ['db']
    _VOZ.update(ruta=clave, db=None)
    try:
        import av
        import numpy as np
        trozos = []
        with av.open(clave) as c:
            rs = av.AudioResampler(format='flt', layout='mono', rate=16000)
            for fr in c.decode(c.streams.audio[0]):
                for g in rs.resample(fr):
                    trozos.append(g.to_ndarray().ravel())
        if trozos:
            _VOZ['db'] = round(nivel_de_audio(np.concatenate(trozos), 16000)[0], 2)
    except Exception:
        _VOZ['db'] = None
    return _VOZ['db']


def objetivo_para(tope_s=None):
    """El nivel al que se normaliza un efecto: el del usuario, y bajo la voz del video si se conoce (más bajo aún si es de cada palabra)."""
    base = objetivo_db()
    if _VOZ['db'] is None:
        return base
    return min(base, _VOZ['db'] - (BAJO_LA_VOZ_PALABRA if tope_s else BAJO_LA_VOZ_EFECTO))


def ganancia_de_normalizado_db(ruta, objetivo=None):
    """Los dB que hay que sumarle a ese sonido para llegar al objetivo (0.0 si está apagado, si no se puede medir o si ya está en el nivel). Se mide una vez y se recuerda."""
    if not normalizar_activo():
        return 0.0
    try:
        origen = Path(str(ruta))
        clave = _clave_ruta(origen)
        sello = origen.stat().st_mtime_ns
        datos = _leer_dic(ARCHIVO_NIVELES)
        g = datos.get(clave)
        if not (isinstance(g, list) and len(g) == 3 and g[0] == sello):
            import sfx_audio
            audio, sr = sfx_audio.cargar(origen)
            rms_db, pico_db = nivel_de_audio(audio, sr)
            g = [sello, round(rms_db, 2), round(pico_db, 2)]
            datos[clave] = g
            _escribir_dic(ARCHIVO_NIVELES, datos)
        ganancia = max(-24.0, min(9.0, (objetivo_db() if objetivo is None else float(objetivo)) - float(g[1])))
        ganancia = min(ganancia, -1.0 - float(g[2]))               # el pico nunca pasa de -1 dBFS
        return 0.0 if abs(ganancia) < 0.3 else float(ganancia)
    except Exception:
        return 0.0
ADELANTO_MAX_S = 0.40            # lo más que un sonido empieza ANTES de su instante para que su pico caiga en él (el remolino de un whoosh, la subida de un riser corto)
_PICOS = {}


def adelanto_natural(ruta, recorte=None):
    """(adelanto_s, instante_del_pico_s) de un sonido (ya recortado): la ventana de 10 ms más fuerte es su PICO; para que ese pico caiga en el instante de la palabra el sonido tiene que
    empezar `adelanto` segundos antes (como mucho ADELANTO_MAX_S: los golpes secos, cuyo pico está al principio, no se adelantan; un whoosh de 6 s cuyo pico está en el 0,9 s sólo se queda con
    el 0,4 s anterior al pico). Se mide una vez por archivo."""
    try:
        origen = Path(str(ruta))
        clave = (str(origen), origen.stat().st_mtime_ns, tuple(recorte) if recorte else None)
    except OSError:
        return 0.0, 0.0
    if clave in _PICOS:
        return _PICOS[clave]
    salida = (0.0, 0.0)
    try:
        import numpy as np
        import sfx_audio
        audio, sr = sfx_audio.cargar(origen)
        a = np.asarray(audio, dtype='float32')
        if recorte:
            a = a[int(recorte[0] * sr):int(recorte[1] * sr)]
        if a.ndim > 1:
            a = np.abs(a).max(axis=1)
        else:
            a = np.abs(a)
        n = max(1, int(sr * 0.010))
        k = len(a) // n
        if k >= 2:
            energia = (a[:k * n].reshape(k, n) ** 2).sum(axis=1)
            tp = (int(energia.argmax()) + 0.5) * n / float(sr)
            salida = (round(min(ADELANTO_MAX_S, tp), 3) if tp > 0.06 else 0.0, round(tp, 3))
    except Exception:
        salida = (0.0, 0.0)
    _PICOS[clave] = salida
    return salida


def adelanto_de(ruta):
    """El adelanto (s) con el que se preparó un sonido alineado al pico (va en el nombre del archivo: «…_a350.wav»), o 0.0."""
    m = re.search(r'_a(\d+)\.wav$', str(ruta))
    return int(m.group(1)) / 1000.0 if m else 0.0


def con_volumen(ruta, db_extra=0.0, tope_s=None, alinear=False):
    """La ruta del sonido con su volumen guardado (y el general, en dB) y su recorte ya aplicados. Si no hay nada que cambiar sale
    la misma ruta; si no, un WAV en ~/DaVinciSubtitles/sfx_volumen (se rehace solo si cambia). Es lo que viaja a la línea de
    tiempo: Resolve no deja cambiar el volumen de un clip por script, así que el volumen y el recorte quedan dentro del archivo.
    v5.5 `alinear`: el WAV empieza `adelanto` s antes de su pico (adelanto_natural) y el nombre acaba en «_a<ms>.wav»; quien lo coloca lo pone ese tiempo ANTES de su instante (adelanto_de),
    así el PICO del sonido (el golpe del hit, lo más fuerte del whoosh) cae justo cuando entra la palabra y no medio segundo después."""
    g_norm = ganancia_de_normalizado_db(ruta, objetivo_para(tope_s))
    factor = volumen_de(ruta) * (10 ** ((float(db_extra or 0.0) + g_norm) / 20.0))
    recorte = recorte_de(ruta)
    adelanto, tp = adelanto_natural(ruta, recorte) if alinear else (0.0, 0.0)
    if abs(factor - 1.0) < 0.005 and not recorte and not tope_s and not adelanto:
        return ruta
    try:
        import hashlib
        import numpy as np
        import sfx_audio
        origen = Path(str(ruta))
        sello = hashlib.sha1(f'{origen}|{origen.stat().st_mtime_ns}|{factor:.3f}|{recorte}|{tope_s}|{adelanto}'.encode('utf-8')).hexdigest()[:10]
        destino = CARPETA_SFX_VOLUMEN / f'{origen.stem}_g{int(round(factor * 100))}_{sello}{("_a%d" % int(round(adelanto * 1000))) if adelanto else ""}.wav'
        if not destino.is_file():
            audio, sr = sfx_audio.cargar(origen)
            if recorte:
                i, j = int(recorte[0] * sr), int(recorte[1] * sr)
                audio = np.array(audio[i:j], dtype='float32')
                paso = min(int(sr * 0.004), len(audio) // 2)       # 4 ms de entrada y salida: sin clic en los cortes
                if paso > 1:
                    rampa = np.linspace(0.0, 1.0, paso, dtype='float32')
                    audio[:paso] *= rampa
                    audio[-paso:] *= rampa[::-1]
            if adelanto and tp - adelanto > 0.004:
                audio = np.array(audio[int((tp - adelanto) * sr):], dtype='float32')          # sin lo que sobra antes de la subida hacia el pico
                paso = min(int(sr * 0.006), len(audio) // 2)
                if paso > 1:
                    audio[:paso] *= np.linspace(0.0, 1.0, paso, dtype='float32')
            if tope_s and len(audio) > int(float(tope_s) * sr):
                # v5.4: un sonido por PALABRA no puede durar mas que unas palabras: se corta al tope con una salida suave (120 ms)
                audio = np.array(audio[:int(float(tope_s) * sr)], dtype='float32')
                cola = min(int(sr * 0.12), len(audio) // 2)
                if cola > 1:
                    audio[-cola:] *= np.linspace(1.0, 0.0, cola, dtype='float32')
            elif tope_s and abs(factor - 1.0) < 0.005 and not recorte and not adelanto:
                return ruta                       # ya es corto: se usa tal cual
            if not len(audio):
                return ruta
            sfx_audio.guardar_wav(np.clip(audio * factor, -1.0, 1.0).astype('float32'), destino)
        return type(ruta)(destino)
    except Exception:
        return ruta
POR_DEFECTO = {'nombre_pista_audio': 'SFX', 'volumen_db': (-12), 'minimo_segundos_entre_efectos': 0.25, 'categoria_por_defecto': None, 'solo_bloques_destacados': True, 'reglas': []}
def _es_bloque_destacado(bloque):
    """True si el bloque merece un efecto: tiene principal o multilinea.\n\n    Los bloques de una palabra suelta con rol \'base\' (que vienen del modo\n    manual, cuando el usuario deja una palabra sin marcar) no son bloques\n    destacados y por defecto se ignoran para los SFX.\n\n    Los bloques del look \'pintado\' (v1.0.51) no traen \'lines\' sino\n    \'palabras\': ahi el criterio es que la frase tenga alguna palabra clave\n    (\'resaltada\') — sin este caso, el preset Hormozi generaba con la\n    casilla de efectos puesta y no sonaba NADA, sin una linea que lo\n    explicara (la clase de fallo mudo que esta prohibida).\n    """
    palabras = bloque.get('palabras')
    if palabras:
        return any((p.get('resaltada') for p in palabras))
    else:
        lineas = bloque.get('lines', [])
        if len(lineas) >= 2:
            return True
        else:
            roles = {l.get('role') for l in lineas}
            return 'main' in roles
def _tiempo_del_golpe(bloque):
    """En que segundo va a SONAR el efecto de este bloque.\n\n    Desde la v1.0.35 el golpe se coloca con la palabra PRINCIPAL, no con la\n    primera del bloque; la separacion minima entre efectos tiene que medirse\n    sobre ese mismo instante, o dos golpes pueden quedar mas pegados que el\n    minimo prometido (la principal entra hasta 1,5 s despues del inicio).\n    Segundos puros: aqui el fps no pinta nada.\n\n    En un bloque \'pintado\' el instante equivalente es la primera palabra\n    resaltada: es la que se enciende dorada, o sea el golpe visual.\n    """
    for p in bloque.get('palabras') or []:
        if p.get('resaltada'):
            try:
                return float(p.get('start', bloque['start']))
            except (TypeError, ValueError):
                return bloque['start']
    for linea in bloque.get('lines', []):
        if linea.get('role') == 'main':
            try:
                return float(linea.get('start', bloque['start']))
            except (TypeError, ValueError):
                return bloque['start']
    return bloque['start']
def _normalizar(texto):
    """Minusculas y sin tildes, para comparar sin sorpresas."""
    sin_tildes = unicodedata.normalize('NFD', texto.lower())
    return ''.join((c for c in sin_tildes if unicodedata.category(c) != 'Mn'))
def cargar_reglas(ruta=None):
    """Lee el JSON de reglas. Si no existe o esta roto, devuelve los valores\n    por defecto (sin reglas), para que la falta de efectos nunca impida\n    generar los subtitulos."""
    explicita = bool(ruta)
    ruta = Path(ruta) if ruta else ruta_reglas()
    config = dict(POR_DEFECTO)
    try:
        datos = json.loads(ruta.read_text(encoding='utf-8'))
    except Exception:
        return config if explicita else _aplicar_modo(config)
    for clave in POR_DEFECTO:
        if clave in datos:
            config[clave] = datos[clave]
    return config if explicita else _aplicar_modo(config)
def _aplicar_modo(config):
    """Modo simple: todos los bloques suenan, al principio, con la categoría «Modo simple»; las reglas
    (modo avanzado) quedan guardadas pero no mandan."""
    guardado = cargar_modo()
    modo = guardado['modo']
    config['modo'] = modo
    donde = guardado['donde']
    act = guardado['activas']
    if (donde == 'todas' and not act['palabra']) or (donde == 'principal' and not act['principal']):
        donde = 'ninguna'                    # la tarjeta de «Sonido por palabra» / «Sonido del texto principal» está apagada: esas palabras no suenan
    config['simple_donde'] = donde
    config['simple_principal'] = [str(sonido_principal())] if sonido_principal() else []
    if modo == 'simple' and sonidos_simples():
        config['categoria_por_defecto'] = CATEGORIA_SIMPLE
        config['reglas'] = []
        config['solo_bloques_destacados'] = False
        config['al_inicio'] = True
        config['simple_intro'] = bool(act['intro'] and sonidos_simples('intro'))
        config['simple_final'] = bool(act['final'] and sonidos_simples('final'))
    elif modo == 'avanzado':
        # (5.3) los ajustes del panel Avanzado mandan; sfx_rules.json solo pone las reglas si el usuario las escribió a mano
        av = cargar_avanzado()
        config['minimo_segundos_entre_efectos'] = float(av['minimo_segundos'])
        config['solo_bloques_destacados'] = bool(av['solo_destacados'])
        config['categoria_por_defecto'] = av['categoria_por_defecto'] or None
        if not config.get('reglas'):
            config['reglas'] = reglas_activas()
        config['probabilidad'] = av['probabilidad']
        config['max_por_minuto'] = av['max_por_minuto']
        config['omitir_inicio_s'] = av['omitir_inicio_s']
        config['omitir_final_s'] = av['omitir_final_s']
        config['no_repetir_categoria'] = bool(av['no_repetir_categoria'])
        config['volumen_global_db'] = float(av['volumen_global_db'])
    return config
def _texto_del_bloque(bloque):
    if bloque.get('palabras'):
        return ' '.join((p.get('texto', '') for p in bloque['palabras'])).strip()
    else:
        return ' '.join((l.get('text', '') for l in bloque.get('lines', []))).strip()
def _cumple_extra(nombre, valor, bloque, texto, contexto):
    """(5.3) Condiciones nuevas del modo Avanzado: True / False, o None si 'nombre' no es una de ellas."""
    palabras = texto.split()
    try:
        if nombre == 'texto_empieza_con':
            return any(texto.lstrip().lower().startswith(str(v).lower()) for v in (valor if isinstance(valor, list) else [valor]))
        if nombre == 'texto_en_mayusculas':
            letras = [c for c in texto if c.isalpha()]
            return (len(letras) >= 2 and all(c.isupper() for c in letras)) == bool(valor)
        if nombre == 'palabras_minimo':
            return (contexto.get('n_palabras_bloque') or len(palabras)) >= int(valor)
        if nombre == 'palabras_maximo':
            return (contexto.get('n_palabras_bloque') or len(palabras)) <= int(valor)
        if nombre == 'es_primera_del_bloque':
            return bool(contexto.get('es_primera_del_bloque', True)) == bool(valor)
        if nombre == 'rol_es':
            return contexto.get('rol') is None or contexto.get('rol') in (valor if isinstance(valor, list) else [valor])
        if nombre == 'duracion_mayor_a':
            return float(bloque.get('end', 0)) - float(bloque.get('start', 0)) > float(valor)
        if nombre == 'duracion_menor_a':
            return float(bloque.get('end', 0)) - float(bloque.get('start', 0)) < float(valor)
        if nombre == 'pausa_despues_mayor_a':
            return contexto.get('pausa_despues', 0.0) > float(valor)
        if nombre == 'cada_n_bloques':
            n = max(1, int(valor))
            return (contexto.get('indice', 0) + 1) % n == 0
    except (TypeError, ValueError):
        return False
    return None
def _cumple(condiciones, bloque, contexto):
    """True si el bloque cumple TODAS las condiciones de la regla.\n\n    \'contexto\' trae lo que no se puede saber mirando el bloque solo:\n    la pausa que hubo antes y si es el primero o el ultimo.\n    """
    texto = _texto_del_bloque(bloque)
    normalizado = _normalizar(texto)
    for nombre, valor in condiciones.items():
        extra = _cumple_extra(nombre, valor, bloque, texto, contexto)
        if extra is not None:
            if not extra:
                return False
            continue
        if nombre == 'texto_termina_en':
            if not any((texto.rstrip().endswith(s) for s in valor)):
                return False
        else:
            if nombre == 'texto_contiene':
                objetivos = [_normalizar(p) for p in valor]
                palabras = set(re.findall('\\w+', normalizado))
                if not any((o in palabras for o in objetivos)):
                    return False
            else:
                if nombre == 'texto_contiene_numero':
                    tiene = any((c.isdigit() for c in texto))
                    if tiene != bool(valor):
                        return False
                else:
                    if nombre == 'pausa_antes_mayor_a':
                        if contexto['pausa_antes'] <= float(valor):
                            return False
                    else:
                        if nombre == 'es_primer_bloque':
                            if contexto['es_primero'] != bool(valor):
                                return False
                        else:
                            if nombre == 'es_ultimo_bloque':
                                if contexto['es_ultimo'] != bool(valor):
                                    return False
                            else:
                                if nombre == 'solo_una_palabra':
                                    una_sola = (contexto.get('n_palabras_bloque') or len(texto.split())) == 1
                                    if una_sola != bool(valor):
                                        return False
                                else:
                                    if nombre == 'roles_incluyen':
                                        roles = contexto.get('roles_bloque') or {l.get('role') for l in bloque.get('lines', [])}
                                        if not set(valor).issubset(roles):
                                            return False
                                    else:
                                        return False
    return True
def categoria_para(bloque, contexto, config):
    """Devuelve la categoria que le toca a un bloque, o None si no suena."""
    for regla in config.get('reglas', []):
        condiciones = regla.get('cuando') or {}
        if condiciones and _cumple(condiciones, bloque, contexto):
                return regla.get('categoria')
    return config.get('categoria_por_defecto')
def asignar_sfx(bloques, config=None, categoria=None):
    """Le pone a cada bloque su campo \'sfx\' con la categoria que le toca.\n\n    Modifica los bloques en el lugar y los devuelve. Se respeta la separacion\n    minima entre efectos: si dos bloques seguidos caen muy pegados, el\n    segundo se queda sin sonido para no encimar dos audios.\n\n    \'categoria\' (v1.0.65) es la eleccion EXPLICITA del usuario y pisa\n    tanto la \'categoria_por_defecto\' del config como sus reglas. Antes\n    la eleccion viajaba escondida dentro del dict config y la firma no\n    delataba a un llamador olvidadizo — el sintoma era «cualquiera que\n    elijas toma la por defecto» sin una linea que lo explicara.\n    """
    config = config or cargar_reglas()
    if config.get('modo') == 'simple' and config.get('al_inicio'):
        categoria = None        # el modo simple manda sobre la fuente elegida en otro sitio
    if categoria:
        config = dict(config)
        config['categoria_por_defecto'] = categoria
        config['reglas'] = []
    minimo = float(config.get('minimo_segundos_entre_efectos') or 0)
    solo_destacados = bool(config.get('solo_bloques_destacados', True))
    ultimo_sonido = None
    ultima_categoria = None
    tiempos = []
    final_video = max((float(b.get('end', 0)) for b in bloques), default=0.0)
    azar = random.Random(11)        # misma semilla: generar dos veces da los mismos sonidos
    total = len(bloques)
    for i, bloque in enumerate(bloques):
        if solo_destacados and (not _es_bloque_destacado(bloque)):
                bloque.pop('sfx', None)
                continue
        anterior = bloques[i - 1] if i > 0 else None
        siguiente = bloques[i + 1] if i + 1 < total else None
        contexto = {'pausa_antes': bloque['start'] - anterior['end'] if anterior else bloque['start'], 'es_primero': i == 0,
                    'es_ultimo': i == total - 1, 'indice': i,
                    'pausa_despues': (siguiente['start'] - bloque['end']) if siguiente else 0.0}
        categoria = categoria_para(bloque, contexto, config)
        golpe = bloque['start'] if config.get('al_inicio') else _tiempo_del_golpe(bloque)
        if categoria and ultimo_sonido is not None and (golpe - ultimo_sonido < minimo):
                    categoria = None
        if categoria and config.get('modo') == 'avanzado':
            # (5.3) filtros del modo Avanzado
            if golpe < float(config.get('omitir_inicio_s') or 0):
                categoria = None
            elif float(config.get('omitir_final_s') or 0) and golpe > final_video - float(config['omitir_final_s']):
                categoria = None
            elif config.get('no_repetir_categoria') and categoria == ultima_categoria:
                categoria = None
            elif float(config.get('max_por_minuto') or 0) and sum(1 for t in tiempos if golpe - t < 60.0) >= float(config['max_por_minuto']):
                categoria = None
            elif float(config.get('probabilidad', 100)) < 100 and azar.random() * 100 >= float(config['probabilidad']):
                categoria = None
        if categoria:
            bloque['sfx'] = categoria
            ultimo_sonido = golpe
            ultima_categoria = categoria
            tiempos.append(golpe)
        else:
            bloque.pop('sfx', None)
    if config.get('modo') == 'simple' and config.get('al_inicio') and bloques:
        # (5.3) introducción: el primer bloque lleva el riser; final: el último lleva el boom
        if config.get('simple_intro'):
            bloques[0]['sfx'] = CATEGORIA_INTRO
        if config.get('simple_final') and total > 1:
            bloques[-1]['sfx'] = CATEGORIA_FINAL
    return bloques
def resumen(bloques):
    """Cuantos bloques quedaron con cada categoria. Para mostrar en pantalla."""
    cuenta = {}
    for b in bloques:
        cat = b.get('sfx')
        if cat:
            cuenta[cat] = cuenta.get(cat, 0) + 1
    return cuenta
EXTENSIONES_AUDIO = {'.flac', '.aif', '.m4a', '.aiff', '.wav', '.ogg', '.mp3'}
PREFIJO_USUARIO = 'usuario/'
CATEGORIA_FAVORITOS = 'favoritos'
def categorias_disponibles(carpeta=None, incluir_del_usuario=True):
    """Las categorias que de verdad tienen audios: {nombre: [archivos]}.

    Mira tres sitios, no uno:

      1. sfx_library (la del usuario si existe, si no la del programa), y un
         nivel mas abajo, para que 'extra/risers' y compania cuenten: si no,
         las reglas de ejemplo del paquete grande quedarian descartadas por
         inexistentes.
      2. Las carpetas que el usuario agrego desde el SFX Lab, como
         'usuario/<nombre>'.
      3. Sus favoritos, como 'favoritos'.

    Los puntos 2 y 3 son la v1.0.24. Antes esta funcion solo miraba
    sfx_library, y como _preparar_sfx descarta toda categoria que no aparezca
    aqui, elegir una carpeta propia dejaba SIN EFECTO a todos los bloques y
    sin un solo aviso: se veia como "el programa no toma mi carpeta".
    """
    carpeta = Path(carpeta) if carpeta else carpeta_libreria()
    extensiones = EXTENSIONES_AUDIO
    encontradas = {}
    if carpeta.is_dir():
        for sub in sorted(carpeta.iterdir()):
            if not sub.is_dir():
                continue
            for nieta in sorted(sub.iterdir()):
                if not nieta.is_dir():
                    continue
                audios = [a.name for a in sorted(nieta.iterdir())
                          if a.suffix.lower() in extensiones]
                if audios:
                    encontradas[f'{sub.name}/{nieta.name}'] = audios
            audios = [a.name for a in sorted(sub.iterdir())
                      if a.suffix.lower() in extensiones]
            if audios:
                encontradas[sub.name] = audios
    if incluir_del_usuario:
        for nombre, rutas in fuentes_del_usuario().items():
            if rutas:
                encontradas[nombre] = [Path(r).name for r in rutas]
    return encontradas
def fuentes_del_usuario():
    """{categoria: [rutas absolutas]} de lo que el usuario aporto.

    Son las carpetas que agrego desde el SFX Lab y sus favoritos. Se
    devuelven RUTAS ABSOLUTAS, no nombres, porque estan fuera de
    sfx_library y Resolve no tendria como encontrarlas de otra forma (ver
    'sfx_archivos' en el manifiesto).

    v3.3.3: los JSON se leen aqui mismo (cargar_carpetas_usuario /
    cargar_favoritos): importar sfx_studio para esto costaba 1,2 s al
    arrancar (Tk + PyAV + numpy).
    """
    fuentes = {}
    try:
        for ruta in cargar_carpetas_usuario():
            p = Path(ruta)
            if not p.is_dir():
                continue
            audios = [str(a) for a in sorted(p.iterdir())
                      if a.is_file() and a.suffix.lower() in EXTENSIONES_AUDIO]
            if audios:
                fuentes[f'{PREFIJO_USUARIO}{p.name}'] = audios
    except Exception:
        pass
    try:
        for seccion, categoria in CATEGORIA_DE_SECCION.items():
            simples = [str(p) for p in sonidos_simples(seccion)]
            if simples:
                fuentes[categoria] = simples
    except Exception:
        pass
    try:
        for r in REGLAS_PREDEFINIDAS:
            concreto = sonido_de_regla(r['id'])
            if concreto:
                fuentes[PREFIJO_REGLA + r['id']] = [concreto]
    except Exception:
        pass
    try:
        favoritos = [str(Path(r)) for r in sorted(cargar_favoritos())
                     if Path(r).is_file()]
        if favoritos:
            fuentes[CATEGORIA_FAVORITOS] = favoritos
    except Exception:
        pass
    return fuentes
def archivos_de(categoria):
    """Las rutas absolutas de una categoria, venga de donde venga.

    Es lo que se manda en el manifiesto para que el script de Resolve no
    tenga que salir a recorrer carpetas — que ademas es de donde salia uno
    de los parpadeos de consola en Windows.
    """
    db = cargar_avanzado()['volumen_global_db'] if cargar_modo()['modo'] == 'avanzado' else 0.0
    propias = fuentes_del_usuario()
    if categoria in propias:
        rutas = [ruta_persistente(con_volumen(r, db)) for r in propias[categoria]]
        if categoria in (CATEGORIA_INTRO, CATEGORIA_FINAL):
            random.SystemRandom().shuffle(rutas)      # un solo bloque usa esta categoría: así varía entre una generación y otra
        return rutas
    base = carpeta_libreria() / categoria
    if not base.is_dir():
        return []
    return [ruta_persistente(con_volumen(str(a), db)) for a in sorted(base.iterdir(), key=_orden_de_biblioteca)
            if a.is_file() and a.suffix.lower() in EXTENSIONES_AUDIO]


# ---------------------------------------------------------------------------------------------------------------------
# v5.4: QUE ARCHIVO suena en cada bloque. El editor muestra un punto en la palabra donde empieza cada efecto y deja
# cambiarlo; lo que se ve ahi es EXACTAMENTE lo que llega a Resolve (el bloque lleva 'sfx_archivo' y los scripts lo usan).
PRIMEROS_DE_FABRICA = ('Viral Hooks Riser.mp3',)          # v5.5: los sonidos que el usuario pidió «por defecto» salen primero de su categoría (el riser de «Riser»)


def _orden_de_biblioteca(ruta):
    return (0 if ruta.name in PRIMEROS_DE_FABRICA else 1, ruta.name)


def _rutas_de(categoria):
    """Las rutas originales (sin volumen ni recorte) de una categoria, en el orden de siempre."""
    propias = fuentes_del_usuario()
    if categoria in propias:
        return [str(r) for r in propias[categoria]]
    base = carpeta_libreria() / categoria
    if not base.is_dir():
        return []
    return [str(a) for a in sorted(base.iterdir(), key=_orden_de_biblioteca) if a.is_file() and a.suffix.lower() in EXTENSIONES_AUDIO]


def para_resolve(ruta, tope_s=None, alinear=False):
    """La ruta que viaja a Resolve: con el volumen y el recorte elegidos en la pantalla Sonido y fuera del programa. `alinear` (v5.5): empieza antes de su pico, ver con_volumen y adelanto_de."""
    db = cargar_avanzado()['volumen_global_db'] if cargar_modo()['modo'] == 'avanzado' else 0.0
    return str(ruta_persistente(con_volumen(str(ruta), db, tope_s, alinear)))


def _manual_de(bloque, manuales):
    if not manuales:
        return None
    try:
        t = float(bloque.get('start') or 0)
        cerca = min(manuales, key=lambda k: abs(float(k) - t))
        if abs(float(cerca) - t) <= 0.06:
            return manuales[cerca]
    except (TypeError, ValueError):
        pass
    return None


def asignar_archivos(bloques, manuales=None, para_resolver=True):
    """Pone en cada bloque con efecto 'sfx_archivo' (el audio para Resolve) y 'sfx_nombre' (el original, para mostrar).

    'manuales' = {inicio_s: ruta | ''} lo que el usuario cambio a mano en el editor ('' = sin sonido en ese bloque). Sin
    cambio manual los archivos de cada categoria se turnan, sin repetir el mismo dos veces seguidas."""
    turno = {}
    originales = {}
    for b in bloques:
        for k in ('sfx_archivo', 'sfx_nombre', 'sfx_manual'):
            b.pop(k, None)
        m = _manual_de(b, manuales)
        if m == '':
            b.pop('sfx', None)
            continue
        if m and Path(str(m)).is_file():
            b['sfx_manual'] = True
            b['sfx_nombre'] = Path(str(m)).name
            b['sfx_archivo'] = para_resolve(m) if para_resolver else str(m)
            b['sfx'] = Path(str(m)).parent.name or 'Manual'
            b['sfx_original'] = str(m)
            continue
        cat = b.get('sfx')
        if not cat:
            continue
        if cat not in originales:
            originales[cat] = _rutas_de(cat)
        rutas = originales[cat]
        if not rutas:
            continue
        i = turno.get(cat, 0)
        turno[cat] = i + 1
        elegido = rutas[0] if cat in (CATEGORIA_INTRO, CATEGORIA_FINAL) else rutas[i % len(rutas)]
        b['sfx_nombre'] = Path(elegido).name
        b['sfx_original'] = elegido
        b['sfx_archivo'] = para_resolve(elegido) if para_resolver else elegido
    return bloques


# ---------------------------------------------------------------------------------------------------------------------
# v5.4: modo simple = UN sonido al inicio de CADA PALABRA (no solo de cada bloque). Cada palabra es un evento con su
# archivo; los eventos viajan dentro del bloque que los contiene ('sfx_eventos') y los scripts de Resolve los colocan.
TOPE_SONIDO_PALABRA_S = 1.2        # lo que dura, como mucho, el sonido de una palabra (el resto se reparte en pistas SFX, SFX 2…)


def _instantes_principales(bloques, palabras, principales=None, inicios=()):
    """{inicio de la palabra (s, 3 decimales): (instante del sonido, clip del efecto o None)} de las palabras PRINCIPALES. `principales` = los instantes en que el estilo hace entrar su palabra clave (la de VIRAL, el
    héroe de Kinetic, la palabra grande de «guion»): cada uno se casa con la palabra hablada más cercana (a menos de 0,35 s) y el sonido cae cuando ENTRA en pantalla; sin eso se saca el
    rol de cada palabra por su POSICIÓN en el bloque (el diseño de 3 líneas: la línea «main»)."""
    salida = {}
    if principales is not None:
        libres = sorted(float(t) for t in inicios)
        for entrada in sorted(principales, key=lambda x: float(x[0] if isinstance(x, (tuple, list)) else x)):
            p, clave = (float(entrada[0]), entrada[1]) if isinstance(entrada, (tuple, list)) else (float(entrada), None)
            mejor = min(libres, key=lambda t: abs(t - p), default=None)
            if mejor is not None and abs(mejor - p) <= 0.35:
                salida[round(mejor, 3)] = (round(p, 3), clave)
                libres.remove(mejor)
        return salida
    vistas = {}
    inicios_bloques = _inicios_de(bloques)
    for p in sorted((p for p in (palabras or []) if str(p.get('texto', '')).strip()), key=lambda p: float(p['t'])):
        bloque = _dueno_de(bloques, float(p['t']), inicios_bloques)
        k = vistas.get(id(bloque), 0)
        vistas[id(bloque)] = k + 1
        if _rol_por_posicion(bloque, k) == 'main':
            salida[round(float(p['t']), 3)] = (round(float(p['t']), 3), None)
    return salida


def asignar_eventos_por_palabra(bloques, inicios, manuales=None, para_resolver=True, config=None, palabras=None, principales=None):
    """Si el modo es simple (al inicio), reparte un sonido por palabra respetando la separacion minima. 'inicios' = los
    segundos donde empieza cada palabra. Devuelve True si lo aplico (si no, queda lo de asignar_archivos por bloque).
    v5.5: con config['simple_donde'] = 'principal' solo suenan las palabras principales (`principales` = sus instantes, si el estilo los conoce) y con 'ninguna' ninguna."""
    config = config or cargar_reglas()
    if config.get('modo') == 'avanzado' and palabras:
        return _eventos_avanzados(bloques, palabras, manuales, para_resolver, config)
    if not (config.get('modo') == 'simple' and config.get('al_inicio') and inicios):
        return False
    minimo = min(0.12, float(config.get('minimo_segundos_entre_efectos') or 0))     # una palabra = un sonido: solo se salta lo que cae pegado
    simples = [str(r) for r in sonidos_simples('inicio')] or _rutas_de(CATEGORIA_SIMPLE)
    intro = [str(r) for r in sonidos_simples('intro')]
    final = [str(r) for r in sonidos_simples('final')]
    inicios = sorted(float(t) for t in inicios)
    ultimo = None
    eventos = []
    veces_efecto = {}
    energia = None
    donde = config.get('simple_donde') if config.get('simple_donde') in DONDE_SIMPLE else 'todas'
    principales = _instantes_principales(bloques, palabras, principales, inicios) if donde == 'principal' else None
    if curva_energia_activa() and donde == 'todas':
        import energia as _en
        energia = _en.energia_de_palabras([{'start': t, 'end': t + 0.25} for t in inicios])
    for n, t in enumerate(inicios):
        m = _manual_de({'start': t}, manuales)
        if m == '':
            continue
        if energia is not None and not m and 0 < n < len(inicios) - 1:
            import energia as _en
            if not _en.deja_pasar(energia, n):
                continue            # tramo calmado: esta palabra no suena (el video respira)
        if ultimo is not None and t - ultimo < minimo and not m and n != len(inicios) - 1:
            continue
        es_intro = n == 0 and config.get('simple_intro') and intro
        es_final = n == len(inicios) - 1 and config.get('simple_final') and final and len(inicios) > 1
        t_sonido = t
        clave = None
        if not m and not es_intro and not es_final:
            if donde == 'ninguna' or (donde == 'principal' and round(t, 3) not in principales):
                continue            # «solo la principal» / «ninguna»: las demás palabras no suenan (lo que el usuario puso a mano, la introducción y el final sí)
            if donde == 'principal':
                t_sonido, clave = principales[round(t, 3)]          # el golpe cae cuando la palabra ENTRA en pantalla (el estilo puede retrasar un bloque un instante)
        if m and Path(str(m)).is_file():
            ruta, cat, manual = str(m), (Path(str(m)).parent.name or 'Manual'), True
        elif es_intro:
            ruta, cat, manual = intro[0], CATEGORIA_INTRO, False
        elif es_final:
            ruta, cat, manual = final[0], CATEGORIA_FINAL, False
        else:
            propia = None                                   # v5.5: el sonido propio del EFECTO que lleva esta palabra principal (cristal, selección, arrastre, héroe)
            if donde == 'principal' and config.get('simple_principal'):
                propia = (str(config['simple_principal'][0]), CATEGORIA_SIMPLE)          # v5.4.29: el efecto sonoro que el usuario eligió para la principal
            elif clave and callable(config.get('categoria_por_clave')):
                cat_efecto = config['categoria_por_clave'](clave)
                rutas_efecto = _rutas_de(cat_efecto) if cat_efecto else []
                if rutas_efecto:
                    veces_efecto[cat_efecto] = veces_efecto.get(cat_efecto, 0) + 1
                    propia = (str(rutas_efecto[(veces_efecto[cat_efecto] - 1) % len(rutas_efecto)]), cat_efecto)
            if propia:
                ruta, cat, manual = propia[0], propia[1], False
            else:
                if not simples:
                    continue
                ruta, cat, manual = simples[len(eventos) % len(simples)], CATEGORIA_SIMPLE, False
        tope = None if cat in (CATEGORIA_INTRO, CATEGORIA_FINAL) else TOPE_SONIDO_PALABRA_S
        archivo = para_resolve(ruta, tope, alinear=not manual and cat not in (CATEGORIA_INTRO, CATEGORIA_FINAL)) if para_resolver else ruta           # v5.5: lo que el usuario eligió a mano y el riser / boom de la introducción y el final van tal cual; el resto, con su pico en la palabra
        t_ev = max(0.0, t_sonido - adelanto_de(archivo)) if para_resolver else t_sonido
        eventos.append({'t': round(t_ev, 3), 't_dueno': round(t_sonido, 3), 'sfx': cat, 'sfx_nombre': Path(ruta).name, 'sfx_original': ruta, 'sfx_archivo': archivo, 'sfx_manual': manual})
        ultimo = t
    _repartir_eventos(bloques, eventos)
    return True


def curva_energia_activa():
    """True si el usuario encendio la «curva de energia» (Sonido): el ritmo del habla decide cuantas palabras suenan."""
    return False                    # v5.4.29: el interruptor se quitó de la pantalla Sonido; sin él, apagada (que unas palabras no suenen sin que se vea el porqué era incoherente)


def _inicios_de(bloques):
    return [float(b.get('start') or 0) for b in bloques]


def _dueno_de(bloques, t, inicios=None):
    """El último bloque que arranca antes de t (+0,06 s). Con 'inicios' (de _inicios_de) es una búsqueda binaria: antes se recorrían
    todos los bloques por cada palabra (4 000 palabras × 1 500 bloques = más de 1 s al generar o al redibujar el editor)."""
    if inicios is None:
        inicios = _inicios_de(bloques)
    k = bisect.bisect_right(inicios, t + 0.06) - 1
    return bloques[k] if k >= 0 else None


def _repartir_eventos(bloques, eventos):
    """Pone cada evento (un sonido por palabra) dentro del bloque que lo contiene."""
    for b in bloques:
        for k in ('sfx', 'sfx_archivo', 'sfx_nombre', 'sfx_manual', 'sfx_original', 'sfx_eventos'):
            b.pop(k, None)
    inicios = _inicios_de(bloques)
    for ev in eventos:
        dueno = _dueno_de(bloques, ev.pop('t_dueno', ev['t']), inicios)          # el bloque lo decide la hora de la PALABRA; 't' puede ir adelantado (alinear al pico)
        if dueno is None:
            continue
        dueno.setdefault('sfx_eventos', []).append(ev)
        dueno.setdefault('sfx', ev['sfx'])


def _rol_por_posicion(bloque, k):
    """El rol de la palabra numero k (0, 1, 2...) del bloque, contando las palabras de sus lineas en orden; None si no hay."""
    if not bloque:
        return None
    n = 0
    for linea in bloque.get('lines') or []:
        cuantas = len(str(linea.get('text') or '').split())
        if k < n + cuantas:
            return linea.get('role')
        n += cuantas
    return None


def _eventos_avanzados(bloques, palabras, manuales, para_resolver, config):
    """Modo Avanzado PALABRA POR PALABRA: las reglas se evaluan sobre cada palabra (con su entorno: pausas, bloque, rol) y los
    filtros del panel (probabilidad, maximo por minuto, omitir inicio/final, no repetir, separacion minima) tambien.
    'palabras' = [{'t', 'fin', 'texto'}]. Devuelve True si aplico algo (aunque no suene ninguna palabra)."""
    pals = sorted((p for p in palabras if str(p.get('texto', '')).strip()), key=lambda p: float(p['t']))
    if not pals:
        return False
    total = len(pals)
    minimo = float(config.get('minimo_segundos_entre_efectos') or 0)
    solo_destacados = bool(config.get('solo_bloques_destacados', False))
    final_video = max(float(p.get('fin') or p['t']) for p in pals)
    azar = random.Random(11)
    turno, originales, eventos, tiempos = {}, {}, [], []
    ultimo_t, ultima_cat = None, None
    vistas = {}
    energia = None
    inicios_bloques = _inicios_de(bloques)
    if curva_energia_activa():
        import energia as _en
        energia = _en.energia_de_palabras(pals)
    for i, p in enumerate(pals):
        t = float(p['t'])
        m = _manual_de({'start': t}, manuales)
        if m == '':
            continue
        bloque = _dueno_de(bloques, t, inicios_bloques)
        lineas = (bloque or {}).get('lines') or []
        k_bloque = vistas.get(id(bloque), 0)
        vistas[id(bloque)] = k_bloque + 1
        rol = _rol_por_posicion(bloque, k_bloque)
        previa = pals[i - 1] if i else None
        siguiente = pals[i + 1] if i + 1 < total else None
        contexto = {'pausa_antes': t - float(previa.get('fin') or previa['t']) if previa else t,
                    'pausa_despues': float(siguiente['t']) - float(p.get('fin') or t) if siguiente else 0.0,
                    'es_primero': i == 0, 'es_ultimo': i == total - 1, 'indice': i, 'rol': rol,
                    'n_palabras_bloque': sum(len(str(l.get('text') or '').split()) for l in lineas),
                    'roles_bloque': {l.get('role') for l in lineas},
                    'es_primera_del_bloque': k_bloque == 0}
        falsa = {'start': t, 'end': float(p.get('fin') or t), 'lines': [{'text': p['texto'], 'role': rol}]}
        manual = bool(m and Path(str(m)).is_file())
        cat = None
        if manual:
            ruta, cat = str(m), (Path(str(m)).parent.name or 'Manual')
        else:
            if solo_destacados and rol is not None and rol != 'main':
                continue
            cat = categoria_para(falsa, contexto, config)
            if not cat:
                continue
            if energia is not None:
                import energia as _en
                if not _en.deja_pasar(energia, i, importante=(rol == 'main' or i == 0 or i == total - 1)):
                    continue
            if ultimo_t is not None and t - ultimo_t < minimo:
                continue
            if t < float(config.get('omitir_inicio_s') or 0):
                continue
            if float(config.get('omitir_final_s') or 0) and t > final_video - float(config['omitir_final_s']):
                continue
            if config.get('no_repetir_categoria') and cat == ultima_cat:
                continue
            if float(config.get('max_por_minuto') or 0) and sum(1 for x in tiempos if t - x < 60.0) >= float(config['max_por_minuto']):
                continue
            if float(config.get('probabilidad', 100)) < 100 and azar.random() * 100 >= float(config['probabilidad']):
                continue
            if cat not in originales:
                originales[cat] = _rutas_de(cat)
            rutas = originales[cat]
            if not rutas:
                continue
            k = turno.get(cat, 0)
            turno[cat] = k + 1
            ruta = rutas[k % len(rutas)]
        archivo = para_resolve(ruta, TOPE_SONIDO_PALABRA_S, alinear=not manual) if para_resolver else ruta
        t_ev = max(0.0, t - adelanto_de(archivo)) if para_resolver else t
        eventos.append({'t': round(t_ev, 3), 't_dueno': round(t, 3), 'sfx': cat, 'sfx_nombre': Path(ruta).name, 'sfx_original': ruta, 'sfx_archivo': archivo, 'sfx_manual': manual})
        ultimo_t, ultima_cat = t, cat
        tiempos.append(t)
    _repartir_eventos(bloques, eventos)
    return True
