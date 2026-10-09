# CineCaptions · By Cinema Productions
# 1_codigo/dynamic_subtitles.py — el «cerebro» de los subtítulos dinámicos: frases, roles (contexto/PRINCIPAL/complemento) y bloques.
"""\ndynamic_subtitles.py\n---------------------\nArma subtitulos \"dinamicos\" a partir de las palabras que devuelve Whisper\n(cada una con su timestamp).\n\nLa idea, siguiendo el estilo de referencia:\n\n        texto de contexto      <- linea chica\n        PRINCIPAL              <- linea grande (lo importante de la frase)\n        complemento            <- linea mediana / cursiva\n\nA diferencia del modo normal (que corta cada 18 caracteres sin mirar el\nsentido), aca se agrupa por FRASES completas usando dos senales:\n\n  1. La puntuacion que pone Whisper (punto, coma, signos de interrogacion).\n  2. Las pausas reales del audio, que conocemos porque tenemos el timestamp\n     de cada palabra.\n\nReglas duras por linea (pedidas explicitamente, no son sugerencias):\n  - contexto:     maximo 2 palabras.\n  - principal:    UNA sola palabra, nunca un conector (\"y\", \"de\", \"el\"...).\n  - complemento:  maximo 2 palabras.\n\nSi en un tramo de la frase no hay ninguna palabra que pueda pararse sola\ncomo principal (por ejemplo, un tramo hecho solo de conectores), el bloque\nse arma como 2 lineas (contexto + complemento) en vez de forzar una\nprincipal que no tiene sentido.\n\nLa sugerencia automatica solo usa 3 roles: context / main / complement. En\nel modo manual hay un cuarto rol posible, \'base\', para las palabras que el\nusuario deja sin marcar (subtitulo simple, palabra por palabra) — comparte\npista con \'main\' en Resolve, asi que nunca se multiplican las pistas.\n\nEl criterio para elegir la palabra principal es local y sin modelos de\nlenguaje: puntua verbos, nombres propios y palabras de contenido largas, y\ndescarta conectores, muletillas, adjetivos de relleno y NUMEROS. Acierta\nbastante seguido, pero no siempre; algunos bloques se van a querer retocar a\nmano.\n"""
import re
import unicodedata
from functools import lru_cache
STOPWORDS = {
    'a', 'ahi', 'al', 'alli', 'ante', 'aquel', 'aquella', 'aqui', 'asi',
    'aun', 'aunque', 'bajo', 'bien', 'bueno', 'cada', 'casi', 'cierta',
    'cierto', 'como', 'con', 'contra', 'cuando', 'de', 'del', 'desde',
    'donde', 'e', 'el', 'ella', 'ellas', 'ellos', 'en', 'entonces', 'entre',
    'era', 'es', 'esa', 'esas', 'ese', 'eso', 'esos', 'esta', 'estan',
    'estar', 'estas', 'este', 'esto', 'estos', 'estoy', 'fue', 'gran',
    'grande', 'grandes', 'ha', 'habia', 'hace', 'hacer', 'hacia', 'han',
    'has', 'hasta', 'hay', 'he', 'la', 'las', 'le', 'les', 'lo', 'los',
    'mas', 'me', 'mejor', 'mejores', 'menos', 'mi', 'mis', 'misma', 'mismo',
    'mucha', 'muchas', 'mucho', 'muchos', 'muy', 'ni', 'no', 'nos',
    'nosotros', 'nuestra', 'nuestras', 'nuestro', 'nuestros', 'nueva',
    'nuevas', 'nuevo', 'nuevos', 'o', 'otra', 'otro', 'para', 'peor',
    'pero', 'poca', 'poco', 'por', 'porque', 'primer', 'primera',
    'primeras', 'primero', 'primeros', 'propia', 'propio', 'puede',
    'pueden', 'pues', 'que', 'se', 'segun', 'segundo', 'ser', 'si', 'sin',
    'sino', 'sobre', 'solo', 'son', 'su', 'sus', 'tambien', 'tan', 'te',
    'tengo', 'tiene', 'tienen', 'toda', 'todas', 'todo', 'todos', 'tras',
    'tu', 'tus', 'u', 'ultima', 'ultimo', 'un', 'una', 'unas', 'unos',
    'ustedes', 'va', 'vamos', 'van', 'voy', 'y', 'ya', 'yo'
}
CONECTORES = {
    'a', 'al', 'con', 'de', 'del', 'e', 'el', 'ello', 'en', 'es', 'ha',
    'han', 'has', 'he', 'hemos', 'la', 'las', 'le', 'lo', 'los', 'mas',
    'me', 'mi', 'mis', 'no', 'nos', 'o', 'para', 'por', 'que', 'se', 'si',
    'son', 'su', 'sus', 'te', 'tu', 'tus', 'u', 'un', 'una', 'unas', 'unos',
    'y', 'ya'
}
@lru_cache(maxsize=16384)       # v5.4: pura y llamada ~15 000 veces por cada reconstruccion de bloques del editor
def _normalizar(palabra: str) -> str:
    """Pasa a minusculas y quita tildes y puntuacion, para comparar."""
    limpia = re.sub('[^\\w\\s]', '', palabra, flags=re.UNICODE).lower()
    sin_tildes = unicodedata.normalize('NFD', limpia)
    return ''.join((c for c in sin_tildes if unicodedata.category(c) != 'Mn'))
def es_conector(palabra: str) -> bool:
    return _normalizar(palabra) in CONECTORES
# v5.8 (auditoría del flujo): palabras que NO pueden ser la última de un bloque porque dejan la frase colgando («cómo multiplicamos las | ventas»,
# «cada comentario en | menos de una hora»): los conectores y además preposiciones, demostrativos, numerales y cuantificadores.
COLGANTES = CONECTORES | {
    'sin', 'sobre', 'entre', 'hasta', 'desde', 'tras', 'segun', 'hacia', 'contra', 'durante', 'como', 'cuando', 'donde', 'pero', 'porque', 'aunque',
    'este', 'esta', 'estos', 'estas', 'ese', 'esa', 'esos', 'esas', 'cada', 'algun', 'alguna', 'ningun', 'ninguna', 'muy', 'tan', 'menos',
    'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve', 'diez',
}
EVITAR_COLGANTES = True
def es_colgante(palabra: str) -> bool:
    n = _normalizar(palabra)
    return n in COLGANTES or n.isdigit()
def peso_basico(palabra: str) -> float:
    return 0.5 if es_conector(palabra) else 1.0
MIN_CONTEXTO = 2
MAX_CONTEXTO = 2
MAX_PRINCIPAL = 1
MIN_COMPLEMENTO = 2
MAX_COMPLEMENTO = 2
MAX_BLOQUE_3L = MAX_CONTEXTO + MAX_PRINCIPAL + MAX_COMPLEMENTO
TAMANOS_POR_DEFECTO = (3, MAX_PRINCIPAL, 3)
RANGO_TAMANOS = ((1, 4), (1, 3), (1, 4))
def normalizar_tamanos(tamanos):
    """(contexto, principal, complemento) dentro de RANGO_TAMANOS.\n\n    None, basura o una preferencia rota vuelven a TAMANOS_POR_DEFECTO por\n    linea: una cantidad invalida nunca puede tumbar la sugerencia."""
    salida = []
    for k, (minimo, maximo) in enumerate(RANGO_TAMANOS):
        try:
            valor = int(tamanos[k])
        except (TypeError, ValueError, IndexError, KeyError):
            valor = TAMANOS_POR_DEFECTO[k]
        salida.append(min(maximo, max(minimo, valor)))
    return tuple(salida)
PUNTOS_MINIMOS_PRINCIPAL = 10
RETARDO_ENTRE_LINEAS = 0.1
PAUSA_SILENCIO = 0.45
PAUSA_GRUPO = 1.5
PAUSA_BLOQUE = 0.6
HOLD_MAXIMO = 2.0
ANIM_ENTRADA_S = 0.40       # lo que tarda en entrar el texto de un pack (Luxe: «Anim Engine · Length» ≈ 0,396 s)
MIN_VISIBLE_S = 0.35        # lo mínimo que tiene que verse el texto ya COMPLETO antes de irse
FIN_FUERTE = ('.', '!', '?', '…')
TERMINACIONES_VERBALES = ('ar', 'er', 'ir', 'ando', 'endo', 'iendo', 'ado', 'ido', 'aste', 'iste', 'aron', 'ieron', 'aba', 'abas', 'aban', 'amos', 'emos', 'imos', 'aran', 'eran', 'iran', 'aria', 'erias', 'eria', 'iria', 'arias', 'irias', 'arian', 'erian', 'irian')
VERBOS_PRESENTE = frozenset('\nvende vendes venden compra compras compran gana ganas ganan pierde pierdes\npierden crece creces crecen crea creas crean ayuda ayudas ayudan cambia\ncambias cambian mejora mejoras mejoran funciona funcionan aprende aprendes\naprenden enseña enseñas enseñan empieza empiezas empiezan termina terminas\nterminan logra logras logran consigue consigues consiguen invierte inviertes\ninvierten ahorra ahorras ahorran escala escalas escalan factura facturas\nfacturan cobra cobras cobran paga pagas pagan duplica duplicas duplican\nconvierte conviertes convierten atrae atraes atraen conecta conectas\nconectan construye construyes construyen destruye destruyes destruyen\nrompe rompes rompen arranca arrancas arrancan explota explotas explotan\ndomina dominas dominan aplica aplicas aplican usa usas usan\n'.split())
VERBOS_PRESENTE = frozenset((_normalizar(v) for v in VERBOS_PRESENTE))
VERBOS_DEBILES = frozenset('\ndije dijo dijiste dijeron digo dice dices dicen decia tuve tuvo tiene\ntienes tengo tienen tenia fui fue vas voy vamos van iba hice hizo hace\nhaces hago hacen hacia pude pudo puede puedes puedo pueden podia quise\nquiso quiere quieres quiero quieren queria supe supo sabe sabes sabemos\nsaben sabia vine vino viene vienes vengo vienen venia diste dio doy das\ndan daba puse puso pone pones pongo ponen ponia\n'.split())
def _parece_verbo(palabra: str, limpia: str) -> bool:
    """Heuristica de terminacion verbal. Ver TERMINACIONES_VERBALES.\n\n    Necesita la palabra ORIGINAL ademas de la normalizada porque el preterito\n    de tercera persona se reconoce por la tilde final (\"habló\", \"llegó\"), y\n    _normalizar la quita: despues de normalizar, \"hablo\" y \"libro\" terminan\n    igual y no hay forma de distinguirlos.\n\n    v1.0.62: los VERBOS_DEBILES nunca cuentan («dije», «tiene», «va»...\n    destacarlos deja la frase coja), y el presente de los verbos de\n    contenido entra por VERBOS_PRESENTE (por lista, no por sufijo).\n    """
    if limpia in VERBOS_DEBILES:
        return False
    else:
        if limpia in VERBOS_PRESENTE:
            return True
        else:
            if len(limpia) < 4:
                return False
            else:
                cruda = palabra.strip().rstrip('.,;:!?…\"\'»)').lower()
                if cruda.endswith(('ó', 'ió', 'rá', 'rán', 'rás', 'ré', 'rés')):
                    return True
                else:
                    return limpia.endswith(TERMINACIONES_VERBALES)
def es_verbo(palabra: str) -> bool:
    """True si la palabra parece un verbo DE CONTENIDO (los debiles no).\n\n    v1.0.63 (reporte literal: «rompio la regla de que la principal debe\n    ser solo una palabra y que sea verbo»): la seleccion usa esto para\n    OBLIGAR el verbo de principal — el centro del grupo es el mejor verbo\n    de la oracion cuando existe, y solo sin verbo manda la mejor palabra\n    (eleccion explicita del usuario). Envuelve _parece_verbo con la\n    normalizacion que necesita; VERBOS_DEBILES ya devuelven False ahi.\n    """
    return _parece_verbo(palabra, _normalizar(palabra))
def puntuar_palabra(palabra: str, es_primera: bool) -> int:
    """Que tan candidata es esta palabra a ser \'la importante\' de la frase."""
    limpia = _normalizar(palabra)
    if not limpia:
        return 0
    else:
        if any((c.isdigit() for c in palabra)):
            return 0
        else:
            if limpia in STOPWORDS:
                return 0
            else:
                if len(limpia) <= 2:
                    return 0
                else:
                    if limpia.endswith('mente') and len(limpia) > 6:
                        return 8
                    else:
                        puntos = 0
                        if not es_primera and palabra[:1].isupper():
                                puntos += 55
                        if _parece_verbo(palabra, limpia):
                            puntos += 60
                        if len(limpia) >= 8:
                            puntos += 40
                            return puntos
                        else:
                            if len(limpia) >= 6:
                                puntos += 30
                                return puntos
                            else:
                                if len(limpia) >= 4:
                                    puntos += 15
                                    return puntos
                                else:
                                    puntos += 5
                                    return puntos
_CIERRES_NO_FINALES = '\"\'”»)]'
def termina_oracion(texto: str) -> bool:
    """True si este texto, tal como esta escrito, cierra una oracion."""
    return texto.strip().rstrip(_CIERRES_NO_FINALES).endswith(FIN_FUERTE)
def _hay_corte_fuerte(palabra_actual, siguiente, pause_break):
    """True si despues de esta palabra hay que cerrar el bloque si o si.\n\n    v1.0.61 (reporte literal: «en complemento toma una palabra de la\n    siguiente oracion»): la frontera de oracion se mira TAMBIEN en el flag\n    \'fin_frase\' que la ventana calcula sobre el texto ORIGINAL de Whisper.\n    Sin el, los botones «Sin , .» borraban la puntuacion de word Y orig y\n    la frontera desaparecia del pipeline entero — el bloque cruzaba la\n    oracion aunque la app supiera perfectamente donde terminaba.\n    """
    if palabra_actual.get('fin_frase'):
        return True
    else:
        if termina_oracion(palabra_actual['word']):
            return True
        else:
            if siguiente is None:
                return True
            else:
                return siguiente['start'] - palabra_actual['end'] > pause_break
def _linea_valida(textos, desde, hasta, minimo, maximo, rol):
    """Si ese trozo puede ser una linea, o es solo relleno.\n\n    Un trozo VACIO es valido: significa que el bloque no lleva esa linea, y un\n    bloque de dos lineas esta perfectamente bien.\n    """
    n = hasta - desde
    if n == 0:
        return True
    else:
        if n < minimo or n > maximo:
            return False
        else:
            partes = [textos[i] for i in range(desde, hasta)]
            if all((es_conector(p) for p in partes)):
                return False
            else:
                if rol == 'complement' and es_conector(partes[(-1)]):
                    return False
                else:
                    return True
def repartir_bloque(textos, scores=None):
    """Donde va la principal, cumpliendo TODAS las reglas de linea.\n\n    Devuelve el indice de la palabra principal, o None si con estas palabras\n    no se puede armar un bloque decente (y entonces el tramo va como\n    subtitulo simple, que es lo que es).\n\n    Reglas, todas a la vez:\n\n      - contexto:    vacio, o de MIN_CONTEXTO a MAX_CONTEXTO palabras.\n                     Puede empezar por conector, pero no ser solo conectores.\n      - principal:   UNA palabra, nunca un conector, y que puntue algo.\n      - complemento: vacio, o de MIN_COMPLEMENTO a MAX_COMPLEMENTO palabras.\n                     Ni solo conectores, ni terminando en conector.\n\n    Entre varios repartos validos gana el de mayor peso, y a igualdad de peso\n    el que deja el bloque mas corto: los maximos de 3 estan para absorber\n    conectores, no para alargar por gusto.\n\n    La usan el modo automatico (_armar_bloque) y el boton de IA\n    (sugerencias_ia). Es a proposito: antes cada uno decidia el reparto por su\n    cuenta con reglas parecidas pero no iguales, y se iban separando con cada\n    cambio.\n    """
    candidatos = _repartos_validos(textos, scores)
    if not candidatos:
        return
    else:
        return max(candidatos)[2]
def _repartos_validos(textos, scores=None):
    """TODOS los j que valen como principal: [(completo, peso, j)].\n\n    Es la base comun de repartir_bloque (que se queda con el mejor) y de las\n    variantes de repartir_con_recorte (que necesitan la lista entera: la\n    \"version 2\" de una sugerencia es la SEGUNDA mejor principal, y solo\n    devolviendo el mejor j por recorte esa segunda no existia).\n    """
    m = len(textos)
    if m == 0:
        return []

    def peso(j):
        base = puntuar_palabra(textos[j], j == 0)
        if scores is None or j >= len(scores):
            return base
        return base * (0.4 + 0.6 * max(0.0, min(1.0, scores[j])))

    candidatos = []
    for j in range(m):
        if es_conector(textos[j]):
            continue
        if puntuar_palabra(textos[j], j == 0) < PUNTOS_MINIMOS_PRINCIPAL:
            continue
        if peso(j) <= 0:
            continue
        if not _linea_valida(textos, 0, j, MIN_CONTEXTO, MAX_CONTEXTO,
                             'context'):
            continue
        if not _linea_valida(textos, j + 1, m, MIN_COMPLEMENTO,
                             MAX_COMPLEMENTO, 'complement'):
            continue
        completo = 1 if 0 < j < m - 1 else 0
        candidatos.append((completo, peso(j), j))
    return candidatos
def repartir_con_recorte(textos, scores=None, alternativa=0):
    """Reparte soltando los conectores de los extremos si hace falta.\n\n    Devuelve (arranque, fin, j): el tramo util es textos[arranque:fin] y la\n    principal es su palabra j. Lo que quede fuera sale como subtitulo simple,\n    que es exactamente lo que es. Si no hay forma, (0, len, None).\n\n    Por que hace falta recortar, con dos casos reales:\n\n      \"y el descuento que te dije\" — la palabra buena es \'descuento\', pero\n      esta en la posicion 1 y el contexto quedaria de una sola palabra. Al\n      soltar \'y\' y \'el\' -los dos conectores- \'descuento\' pasa a ser la\n      primera, el contexto queda vacio (que es valido) y se puede destacar.\n\n      \"te lo dejo listo para el\" — el tramo TERMINA en conectores, asi que el\n      complemento acabaria colgando. Soltando \'para el\' por detras, el reparto\n      sale solo.\n\n    Y se prueban TODOS los recortes posibles quedandose con la mejor\n    principal, no con el primero que valga: parando en el primero salia \'dije\'\n    en vez de \'descuento\'.\n\n    \'alternativa\' pide la k-esima mejor principal DISTINTA (0 = la mejor).\n    Es lo que hace que el boton de sugerencias pueda ofrecer varias\n    versiones: misma frase, otra palabra destacada. Si no hay tantas\n    principales distintas, se devuelve la ultima que haya — pedir la\n    variante 5 de un tramo con 2 candidatas da la segunda, no None, para que\n    una variante alta no desarme bloques que las bajas si arman.\n    """
    n = len(textos)
    if n == 0:
        return (0, 0, None)
    else:
        max_ini = 0
        while max_ini < n and es_conector(textos[max_ini]):
                max_ini += 1
        min_fin = n
        while min_fin > 0 and es_conector(textos[min_fin - 1]):
                min_fin -= 1
        candidatos = []
        for arranque in range(max_ini + 1):
            for fin in range(n, max(min_fin, arranque) - 1, (-1)):
                trozo = textos[arranque:fin]
                if trozo:
                    locales = scores[arranque:fin] if scores else None
                    for completo, peso, j in _repartos_validos(trozo, locales):
                        clave = (completo, peso, -(arranque + (n - fin)))
                        candidatos.append((clave, arranque, fin, j))
        if not candidatos:
            return (0, n, None)
        else:
            candidatos.sort(key=lambda c: c[0], reverse=True)
            vistos, distintos = (set(), [])
            for cand in candidatos:
                palabra = _normalizar(textos[cand[1] + cand[3]])
                if palabra in vistos:
                    continue
                else:
                    vistos.add(palabra)
                    distintos.append(cand)
            k = max(0, int(alternativa))
            elegido = distintos[min(k, len(distintos) - 1)]
            return (elegido[1], elegido[2], elegido[3])
PESOS_CONECTOR = (0.0, 0.5, 1.0)
PESO_CONECTOR_DEFECTO = 1.0
def normalizar_peso_conector(valor):
    """v5.7 (pedido: «elimina "2 = 1 palabra", cuentan como palabra»): un conector («de», «la», «que»…) cuenta SIEMPRE como una palabra;
    las palabras por línea son palabra por palabra. El ajuste «Peso de conectores» se quitó: cualquier valor guardado se ignora."""
    return 1.0
def grupo_alrededor(palabras, centro, desde, hasta, n_contexto=MAX_CONTEXTO, n_principal=MAX_PRINCIPAL, n_complemento=MAX_COMPLEMENTO, fin_centro=None, peso_conector=0.0):
    """El grupo 2+1+2 alrededor de \'centro\': {indice: rol}, sin adivinar.\n\n    v3.3.1: \'peso_conector\' (0 / 0.5 / 1) es cuanto descuenta un conector\n    del presupuesto de contexto y complemento; con 0 el resultado es\n    IDENTICO a la v3.1.9 (test_v331 lo compara con la v3.3.0 de git).\n\n    v3.1.9: las tres cantidades son parametros (el selector «Palabras por\n    linea» de la ventana; por defecto 2/1/2 = lo de siempre). La principal\n    arranca en el tramo [centro, fin_centro] — lo que PINTO el usuario,\n    que jamas se recorta (pedido literal: «si el usuario quiso poner 2\n    palabras ahi, respetalo») — y solo si tiene menos de n_principal\n    palabras de contenido se alarga hasta juntarlas (derecha primero,\n    luego izquierda). Sin fin_centro el tramo es el centro solo. El\n    contexto cuenta desde el INICIO del tramo y el complemento desde su\n    FIN.\n\n    v1.0.63 (pedido literal del usuario, con su ejemplo): la principal es\n    \'centro\' SOLA; el contexto son las 2 palabras DE CONTENIDO mas\n    cercanas por la izquierda y el complemento las 2 mas cercanas por la\n    derecha, y los conectores que quedan EN MEDIO viajan ACOPLADOS al\n    tramo («si une el mensaje»): «Trabajamos | con la mejor compañia».\n    Un conector por FUERA del tramo NO entra: el contexto arranca en\n    palabra de contenido y el complemento termina en una — asi ninguna\n    linea queda colgando de un «y» ni un «para el».\n\n    Nunca cruza [desde, hasta): la oracion manda (v1.0.61). Es EL\n    constructor de los grupos nuevos — lo usan la estrella de sugerencias\n    (sugerencias_ia._roles_por_bloque) y el boton «Completar» de la\n    ventana, a proposito: dos copias de esta regla se separarian con cada\n    cambio, como ya paso con el reparto antes de la v1.0.25.\n    (repartir_con_recorte queda para el motor automatico viejo: legaliza\n    VENTANAS con maximos en tokens crudos; esto COMPLETA alrededor de un\n    centro contando solo el contenido — productos distintos.)\n    """
    def _texto(i):
        w = palabras[i]
        if isinstance(w, dict):
            return str(w.get('word', '')).strip()
        return str(w).strip()

    if not desde <= centro < hasta:
        return {}
    ini = fin = centro
    if fin_centro is not None:
        fin = max(centro, min(int(fin_centro), hasta - 1))
    peso = normalizar_peso_conector(peso_conector)
    # v5.7 («los conectores cuentan como palabra»): con peso 1 (siempre) la principal son EXACTAMENTE n_principal palabras seguidas; antes los
    # conectores del medio no contaban y una principal de 3 podía salir de 4 o 5 palabras (pasándose del tope que el usuario puso)
    cuenta = (lambda k: True) if peso >= 1.0 else (lambda k: not es_conector(_texto(k)))
    faltan = max(1, int(n_principal)) - max(1, sum(
        1 for k in range(ini, fin + 1) if cuenta(k)))
    j = fin + 1
    while faltan > 0 and j < hasta:
        if cuenta(j):
            fin = j
            faltan -= 1
        j += 1
    j = ini - 1
    while faltan > 0 and j >= desde:
        if cuenta(j):
            ini = j
            faltan -= 1
        j -= 1
    roles = {k: 'main' for k in range(ini, fin + 1)}

    acum, pendiente, tope = 0.0, 0.0, ini
    i = ini - 1
    while i >= desde:
        if es_conector(_texto(i)):
            pendiente += peso
        else:
            if acum + pendiente + 1.0 > n_contexto:
                break
            acum += pendiente + 1.0
            pendiente = 0.0
            tope = i
        i -= 1
    if acum and tope > desde and all(es_conector(_texto(j))
                                     for j in range(desde, tope)):
        if acum + peso * (tope - desde) <= n_contexto:
            tope = desde
    for k in range(tope, ini):
        roles[k] = 'context'

    acum, pendiente, tope = 0.0, 0.0, fin
    i = fin + 1
    while i < hasta:
        if es_conector(_texto(i)):
            pendiente += peso
        else:
            if acum + pendiente + 1.0 > n_complemento:
                break
            acum += pendiente + 1.0
            pendiente = 0.0
            tope = i
        i += 1
    for k in range(fin + 1, tope + 1):
        roles[k] = 'complement'
    return roles
def _elegir_principal(textos, scores=None):
    """Elige que palabra del tramo va como \'principal\'. SIEMPRE devuelve una.\n\n    Solo se consideran posiciones que, si ganan, dejan contexto <= 2 y\n    complemento <= 2 (o sea, j <= MAX_CONTEXTO y (m-1-j) <= MAX_COMPLEMENTO).\n\n    Se intenta en tres pasadas, de mejor a peor, porque un bloque SIN linea\n    principal se ve mal: queda el hueco del medio vacio y el contexto y el\n    complemento separados por un espacio raro. Antes se devolvia None y el\n    bloque caia a contexto+complemento; ahora eso no pasa nunca.\n\n      1. una palabra con contenido (no conector) que ademas puntue alto;\n      2. si ninguna de esas posiciones sirve, la mejor palabra del tramo\n         ENTERO, aunque deje el contexto o el complemento en tres palabras;\n      3. si ninguna puntua, cualquier palabra que no sea conector;\n      4. si todas son conectores, la mas larga (mal menor).\n\n    El paso 2 existe porque el limite de posiciones puede dejar UNA sola\n    valida, y si ahi cae un numero o una stopword se destacaba eso. Con\n    \"Hoy vendio 20 cursos y\" la unica posicion permitida es la del \"20\", y\n    se perdia \"vendio\". Tres palabras de contexto se ven bien; un \"20\"\n    gigante en el centro, no.\n\n    `scores` es opcional: una lista paralela a `textos` con un peso\n    semantico de 0 a 1 (lo que devuelve el motor de IA). Cuando viene, se\n    multiplica por el puntaje de siempre en vez de reemplazarlo, asi las\n    reglas duras se mantienen: un conector o una stopword puntuan 0 y\n    siguen sin poder ser principal por mucho que la IA los quiera.\n    """
    m = len(textos)
    j_min = max(0, m - 1 - MAX_COMPLEMENTO)
    j_max = min(MAX_CONTEXTO, m - 1)
    if j_min > j_max:
        j_min, j_max = (0, m - 1)
    rango = range(j_min, j_max + 1)
    no_conectores = [j for j in rango if not es_conector(textos[j])]
    def peso(j):
        base = puntuar_palabra(textos[j], j == 0)
        if scores is None or j >= len(scores):
            return base
        else:
            return base * (0.4 + 0.6 * max(0.0, min(1.0, scores[j])))
    con_puntaje = [(peso(j), j) for j in no_conectores]
    buenos = [(p, j) for p, j in con_puntaje if p > 0]
    if buenos:
        return max(buenos)[1]
    else:
        fuera = [(peso(j), j) for j in range(m)
             if not es_conector(textos[j]) and peso(j) > 0]
        if fuera:
            return max(fuera)[1]
        else:
            if no_conectores:
                return max(no_conectores, key=lambda j: len(_normalizar(textos[j])))
            else:
                return max(rango, key=lambda j: len(_normalizar(textos[j])))
def segmentar(words, pause_break: float=PAUSA_SILENCIO):
    """Parte las palabras en tramos, uno por bloque de subtitulo.\n\n    Corta donde termina una idea: punto/signo fuerte, pausa larga en el\n    audio, o cuando el tramo ya no entra en un bloque de 3 lineas.\n\n    Devuelve una lista de (desde, hasta) sobre la lista de palabras que se\n    le paso (ya filtrada de vacias). Se uso tanto al armar los bloques\n    automaticos como al sugerir roles con IA, para que ambos partan el\n    guion exactamente igual.\n    """
    n = len(words)
    tramos = []
    i = 0
    while i < n:
        limite = i
        while limite < n and limite - i < MAX_BLOQUE_3L:
                siguiente = words[limite + 1] if limite + 1 < n else None
                limite += 1
                if _hay_corte_fuerte(words[limite - 1], siguiente, pause_break):
                    break
        tramos.append((i, limite))
        i = limite
    return tramos
MAX_ORACION_SUGERIDA = 12
def segmentar_oraciones(words, pause_break: float=PAUSA_SILENCIO):
    """Parte las palabras en ORACIONES enteras (tope de cordura aparte).\n\n    Igual que segmentar() pero sin el tope de MAX_BLOQUE_3L: corta SOLO\n    donde termina una idea (fin_frase/puntuacion fuerte/pausa larga).\n    Existe por la v1.0.62 (pedido literal: «que los bloques esten mas\n    separados, delimitando las oraciones»): la seleccion elige UN grupo\n    dinamico por oracion, y para eso necesita la oracion completa, no\n    ventanas de 5 palabras. Las palabras sin tiempos tambien sirven (la\n    pausa simplemente no corta). Un tramo sin NINGUN corte en\n    MAX_ORACION_SUGERIDA palabras se parte por el hueco mas grande.\n    """
    n = len(words)
    crudas = []
    i = 0
    while i < n:
        limite = i
        while limite < n:
            siguiente = words[limite + 1] if limite + 1 < n else None
            limite += 1
            actual = words[limite - 1]
            sin_tiempos = 'end' not in actual or (siguiente is not None and 'start' not in siguiente)
            if sin_tiempos:
                if actual.get('fin_frase') or termina_oracion(str(actual.get('word', ''))) or siguiente is None:
                    break
            else:
                if _hay_corte_fuerte(actual, siguiente, pause_break):
                    break
        crudas.append((i, limite))
        i = limite
    def mejor_corte(desde, tope):
        mejor, donde = ((-1.0), tope)
        # v5.5: nunca un corte que deje 1 o 2 palabras sueltas (con huecos iguales el primero ganaba: «En | solo 30 dias...»);
        # con huecos parecidos gana el mas tardio, que reparte la frase en trozos parejos
        for k in range(min(tope, desde + 3), tope + 1):
            if k >= len(words):
                break
            a, b = (words[k - 1], words[k])
            try:
                hueco = float(b['start']) - float(a['end'])
            except (KeyError, TypeError, ValueError):
                pass
            else:
                if hueco >= mejor - 0.05:
                    mejor, donde = (max(mejor, hueco), k)
        return donde
    oraciones = []
    for desde, hasta in crudas:
        while hasta - desde > MAX_ORACION_SUGERIDA:
            corte = mejor_corte(desde, desde + MAX_ORACION_SUGERIDA)
            oraciones.append((desde, corte))
            desde = corte
        oraciones.append((desde, hasta))
    return oraciones
def _armar_bloque(trozo_palabras):
    """Convierte un tramo de palabras (con timestamps) en sus lineas.\n\n    El bloque SIEMPRE lleva linea principal, asi que los unicos repartos\n    posibles son: contexto+principal+complemento, contexto+principal,\n    principal+complemento, o principal sola.\n    """
    textos = [w['word'].strip() for w in trozo_palabras]
    m = len(textos)
    arranque, fin, j = repartir_con_recorte(textos)
    if j is None:
        return [('base', 0, m)]
    else:
        j_abs = arranque + j
        return [t for t in [('base', 0, arranque), ('context', arranque, j_abs), ('main', j_abs, j_abs + 1), ('complement', j_abs + 1, fin), ('base', fin, m)]
                if t[2] > t[1]]
def build_dynamic_cues(words, pause_break: float=PAUSA_SILENCIO, min_duration: float=0.9, **_ignorado):
    """Devuelve la lista de bloques dinamicos lista para guardar en JSON.\n\n    Cada bloque trae sus lineas con el segundo exacto en que cada una debe\n    aparecer: el momento en que se dice su primera palabra. Asi el contexto\n    entra primero, despues la principal y por ultimo el complemento,\n    siguiendo el habla en vez de aparecer todas de golpe. Todas comparten\n    el mismo final, para poder cerrarlas juntas con un fundido.\n\n    El tramo que se consume por bloque nunca excede lo que un layout puede\n    mostrar (5 palabras si hay principal, 4 si no la hay), para que ninguna\n    linea individual se pase de su limite. Nunca se descarta una palabra:\n    lo que no entra en este bloque arranca el siguiente.\n    """
    palabras = [w for w in words if w['word'].strip()]
    if not palabras:
        return []
    else:
        def cerrar(grupo, palabras_grupo):
            """Un bloque a partir de sus tramos ya decididos."""
            if not grupo:
                return
            else:
                inicio = palabras_grupo[0]['start']
                fin = max(palabras_grupo[(-1)]['end'], inicio + min_duration)
                lineas = []
                for orden, (rol, parte) in enumerate(grupo):
                    lineas.append({'role': rol, 'text': ' '.join((w['word'].strip() for w in parte)), 'start': round(min(inicio + orden * RETARDO_ENTRE_LINEAS, fin), 3)})
                bloques.append({'start': round(inicio, 3), 'end': round(fin, 3), 'fin_hablado': round(palabras_grupo[(-1)]['end'], 3), 'lines': lineas})
        bloques = []
        for desde, hasta in segmentar(palabras, pause_break):
            tramo = palabras[desde:hasta]
            grupo, palabras_grupo = ([], [])
            for rol, ini, fin_t in _armar_bloque(tramo):
                parte = tramo[ini:fin_t]
                if parte:
                    if rol == 'base':
                        cerrar(grupo, palabras_grupo)
                        grupo, palabras_grupo = ([], [])
                        cerrar([('base', parte)], parte)
                    else:
                        grupo.append((rol, parte))
                        palabras_grupo.extend(parte)
            cerrar(grupo, palabras_grupo)
        for k in range(len(bloques) - 1):
            if bloques[k]['end'] > bloques[k + 1]['start']:
                bloques[k]['end'] = bloques[k + 1]['start']
        return _capitalizar_lineas(bloques)
def capitalizar_contenido(texto):
    """Mayuscula inicial en CADA palabra DE CONTENIDO; conectores en baja.\n\n    v1.0.63 (eleccion explicita del usuario: «la primera de cada palabra de\n    cada linea a excepcion de conectores»). Sustituye a\n    capitalizar_arranque (v1.0.58, solo la primera de contenido de la\n    linea): ahora TODAS las palabras de contenido de las lineas con rol\n    arrancan en mayuscula y los conectores van enteros en minuscula (son\n    palabras funcion — jamas un nombre propio, bajarlas no rompe nada; y\n    un «Y» que Whisper capitalizo a inicio de oracion dentro de la linea\n    se veia como error). Se aplica al ARMAR las lineas — UN solo sitio\n    para los dos motores (build_dynamic_cues y build_manual_cues) — y\n    NUNCA sobre las palabras almacenadas de la ventana: puntuar_palabra\n    da +55 a una mayuscula en medio de frase (mutarlas degeneraria el\n    puntaje en la siguiente sugerencia) y la ortografia salta las\n    palabras capitalizadas (cada marcada se volveria invisible al\n    corrector). Solo se sube la PRIMERA letra alfabetica de cada palabra:\n    «IA», «2026» y «compañía» sobreviven tal cual.\n    """
    partes = (texto or '').split(' ')
    for i, palabra in enumerate(partes):
        limpia = palabra.strip('.,;:!?¡¿\"«»()[]…')
        if not limpia:
            continue
        else:
            if es_conector(limpia):
                partes[i] = palabra.lower()
            else:
                for j, ch in enumerate(palabra):
                    if ch.isalpha():
                        partes[i] = palabra[:j] + ch.upper() + palabra[j + 1:]
                        break
    return ' '.join(partes)
def _capitalizar_lineas(bloques):
    for bloque in bloques:
        for linea in bloque.get('lines') or []:
            if linea.get('role') in ['context', 'main', 'complement']:
                linea['text'] = capitalizar_contenido(linea.get('text'))
    return bloques
def cue_to_plain_text(bloque) -> str:
    """La frase completa en una sola linea (para el .srt de respaldo).\n\n    Los bloques del modo destacados tienen dos formas: \'lines\' (hormozi,\n    gadzhi, acumulativo -igual que los del modo dinamico-) o \'palabras\'\n    (pintado, una por Text+). El .srt de respaldo tiene que poder armarse\n    desde cualquiera de las dos, no solo desde la primera que se probo.\n    """
    if 'palabras' in bloque:
        return ' '.join(p['texto'] for p in bloque['palabras']
                        if p.get('texto')).strip()
    else:
        return ' '.join((l['text'] for l in bloque['lines'] if l['text'])).strip()
def hay_corte_de_frase(actual, siguiente, pause_break: float=PAUSA_SILENCIO) -> bool:
    """True si despues de \'actual\' termina una frase.\n\n    Lo usa la ventana de etiquetado para mostrar el texto separado en frases\n    en vez de un parrafo corrido (se lee mucho mejor a la hora de marcar).\n    Mira la puntuacion y, sobre todo, las pausas reales del audio — que es lo\n    unico que queda si el usuario ya quito los puntos y las comas.\n    """
    return _hay_corte_fuerte(actual, siguiente, pause_break)
def suggest_roles(words):
    """Etiqueta sugerida por palabra, para no partir de una pantalla en blanco.\n\n    Devuelve una lista paralela a las palabras no vacias de \'words\' (mismo\n    orden, mismo largo), con \'context\' / \'main\' / \'complement\' / None en cada\n    posicion. Son sugerencias: el usuario las puede cambiar todas en la\n    ventana antes de generar.\n\n    No se reimplementa la logica de eleccion: se corre el armado automatico\n    normal y se reconstruye a que palabra le toco cada rol, aprovechando que\n    build_dynamic_cues nunca pierde ni reordena palabras (la concatenacion de\n    todas las lineas, en orden, reproduce el texto original completo).\n    """
    palabras = [w for w in words if w['word'].strip()]
    bloques = build_dynamic_cues(words)
    roles = [None] * len(palabras)
    idx = 0
    for bloque in bloques:
        for linea in bloque['lines']:
            rol = linea['role']
            if rol == 'base':
                rol = None
            for _ in linea['text'].split():
                if idx < len(roles):
                    roles[idx] = rol
                idx += 1
    return roles
ORDEN_ROL = {'context': 0, 'main': 1, 'complement': 2}
# v5.7: 'tamanos' = (arriba, principal, abajo) = el MAXIMO de palabras de cada linea. Una linea nunca lo supera: si hay mas palabras
# seguidas con el mismo rol, el bloque se cierra y el resto abre otro (ninguna palabra se pierde). None = sin tope (como antes).
def build_manual_cues(words, roles, min_duration: float=0.5, palabras_por_basico: int=2, fin_video=None, capitalizar: bool=True, tamanos=None, peso_conector=1.0):
    """Arma los bloques a partir de las etiquetas que puso el usuario a mano.\n\n    \'roles\' es una lista paralela a las palabras no vacias de \'words\': cada\n    posicion es \'context\' / \'main\' / \'complement\' / None.\n\n    COMO SE DECIDE DONDE CORTA UN BLOQUE\n    ------------------------------------\n    Un bloque en pantalla se lee de arriba hacia abajo: contexto, principal,\n    complemento. Entonces, mientras los roles marcados vayan AVANZANDO en ese\n    orden, siguen siendo el mismo bloque; en cuanto uno RETROCEDE, ahi empieza\n    un bloque nuevo. Por ejemplo:\n\n        Los primeros(ctx) pacientes(main) recibiran(cmp) | un(ctx) 20(main)...\n                        un solo bloque                   ^ aca corta\n\n    Dos palabras seguidas con el MISMO rol van juntas en la misma linea\n    (\"Los primeros\" es una sola linea de contexto).\n\n    Esto es lo que responde a \"en base a eso el script tiene que calcular en\n    cuantos bloques debe dividir\": el corte sale de las marcas, no de un\n    conteo de palabras ni de las pausas del audio.\n\n    Las palabras SIN etiquetar se muestran como subtitulos simples, con el\n    rol \'base\'. \'base\' no suma una cuarta pista en Resolve (usa la misma\n    pista que \'main\'), pero es un rol distinto para que, si el usuario dejo\n    un Text+ propio llamado \'base\' en el Media Pool, Resolve lo use ahi en\n    vez de mezclarlo con el estilo de \'principal\'.\n\n    \'palabras_por_basico\' dice cuantas de esas palabras sueltas SEGUIDAS van\n    juntas en un mismo bloque. Con 1 sale una por una, que es como estaba\n    antes y hacia que cada palabra durase muy poco. Con 2 (por defecto) o\n    mas, se leen mas comodas. El grupo se cierra igual en cuanto aparece una\n    palabra etiquetada, para no mezclar los dos modos en un bloque.\n    """
    palabras = [w for w in words if w['word'].strip()]
    n = len(palabras)
    if len(roles) != n:
        raise ValueError(f'\'roles\' tiene {len(roles)} elementos pero hay {n} palabras; tienen que coincidir exactamente.')
    else:
        por_basico = max(1, int(palabras_por_basico or 1))
        tope = None
        if tamanos is not None:
            n_ctx_, n_main_, n_cmp_ = normalizar_tamanos(tamanos)
            tope = {'context': n_ctx_, 'main': n_main_, 'complement': n_cmp_}
        pc_ = max(0.5, normalizar_peso_conector(peso_conector)) if peso_conector else 1.0
        def peso_linea(texto):
            return sum((pc_ if es_conector(t_) else 1.0) for t_ in texto.split())
        bloques = []
        lineas = []
        palabras_bloque = []
        sueltas = []
        def cerrar_bloque():
            if not lineas:
                return
            else:
                inicio = palabras_bloque[0]['start']
                fin = max(palabras_bloque[(-1)]['end'], inicio + min_duration)
                for orden, linea in enumerate(lineas):
                    real = linea.get('start', inicio)
                    linea['start'] = round(min(max(real, inicio), fin), 3)
                bloques.append({'start': round(inicio, 3), 'end': round(fin, 3), 'fin_hablado': round(palabras_bloque[(-1)]['end'], 3), 'lines': list(lineas)})
                lineas.clear()
                palabras_bloque.clear()
        def cerrar_sueltas():
            """Cierra la tanda de palabras sin marcar: sale como UN solo bloque.\n\n        v1.0.66, pedido literal del usuario (11-09): «reparte la frase y lo\n        repite, no tiene por que volver a repetir parte de la misma\n        frase, genera desincronizacion... me genera desorden. Quiero que\n        salga la cantidad de palabras que te pedi como maximo». De la\n        v1.0.28 a la v1.0.65 la tanda era ACUMULATIVA (un bloque por\n        palabra con el texto sumado: «que» -> «que tu» -> «que tu\n        tienes») para que cada palabra entrara al decirse — y esa\n        REPETICION es exactamente lo que el retiro. OJO para el futuro:\n        esto INVIERTE a proposito la regla v1.0.28 «cada palabra entra\n        cuando se dice» EN LOS BASE, con confirmacion explicita: el\n        bloque entero aparece con su PRIMERA palabra y las siguientes se\n        ven un instante antes de pronunciarse — el usuario lo eligio asi\n        («como los subtitulos normales de toda la vida»). No lo\n        «arregles» de vuelta sin una orden suya.\n\n        Consecuencias medidas (exploracion v1.0.66): la clave\n        `continuacion` deja de escribirse (sin acumulado no hay\n        re-animacion que evitar; los gemelos conservan su LECTURA por\n        los manifiestos ya generados), el fundido de entrada vuelve a\n        aplicarse una vez por tanda, y el .srt de respaldo deja de\n        repetir la misma frase en tres entradas.\n        """
            if not sueltas:
                return
            else:
                inicio = sueltas[0]['start']
                bloques.append({'start': round(inicio, 3), 'end': round(max(sueltas[(-1)]['end'], inicio + min_duration), 3), 'fin_hablado': round(sueltas[(-1)]['end'], 3), 'lines': [{'role': 'base', 'text': ' '.join((p['word'].strip() for p in sueltas)), 'start': round(inicio, 3)}]})
                sueltas.clear()
        def hay_silencio_antes(w, anteriores, umbral=PAUSA_SILENCIO):
            """True si entre la palabra anterior y esta se dejo de hablar.\n\n        Sin esto, dos palabras del MISMO rol separadas por siete segundos se\n        juntaban en una sola linea, y el bloque se quedaba en pantalla todo el\n        silencio. Con la regla de \"sin huecos\" de la v1.0.25 eso se nota mas\n        todavia, porque ya no hay nada detras que lo empuje fuera.\n\n        \'umbral\' existe porque un grupo MARCADO aguanta mas que las\n        sueltas (v1.0.63, ver PAUSA_GRUPO): con 0.45 s una respiracion\n        partia el grupo en dos bloques de 1-2 lineas que terminaban en\n        escalera.\n        """
            if not anteriores:
                return False
            else:
                return w['start'] - anteriores[(-1)]['end'] > umbral
        def hay_frontera_antes(anteriores):
            """True si la ultima palabra del bloque cerro una oracion.\n\n        v1.0.61: sin esto, dos palabras del mismo rol a ambos lados de un\n        punto se concatenaban en la misma linea (el merge de mas abajo no\n        mira puntuacion) y el complemento se comia la primera palabra de\n        la oracion siguiente. La frontera manda: el bloque cierra ahi.\n        """
            if not anteriores:
                return False
            else:
                ultima = anteriores[(-1)]
                return bool(ultima.get('corte')) or bool(ultima.get('fin_frase')) or termina_oracion(ultima['word'])
        def peso_sueltas():
            return sum((peso_basico(p['word']) for p in sueltas))
        def resto_huerfano(i):
            """True si la frase, desde palabras[i], deja a lo sumo 1 de\n        contenido y la tanda que la absorbe queda dentro del tope.\n\n        v1.0.64 (pedido literal: «si es de una sola palabra + conector o\n        lo que sea, si ya puso la frase no tiene porque repetir lo\n        mismo»): cuando el cupo se llena pero lo que QUEDA de la frase\n        es una sola palabra de contenido (mas los conectores que la\n        acompañen), cerrar aqui dejaba ese resto huerfano en su propia\n        tanda — la frase corta salia partida en dos bloques pudiendo\n        salir en uno. El resto se mide SOLO hasta donde la tanda\n        cortaria igual (rol marcado, frontera de frase o silencio):\n        contar mas alla seria contar palabras que jamas entrarian.\n\n        v1.0.68: se llama ANTES de añadir palabras[i] (el cierre por\n        cupo paso a pre-insercion), asi que el resto se mide DESDE i\n        inclusive.\n\n        v1.0.69 (eleccion literal del usuario tras el segundo «sigue sin\n        ser tan estricto»): el tope de la absorcion paso de PESO\n        (por_basico + 1.5) a TOKENS VISIBLES — la tanda absorbida\n        jamas puede superar por_basico + 1 palabras EN PANTALLA. Con\n        el tope de peso, una cola de conectores (0.5 cada uno) seguia\n        inflando el bloque hasta 8-9 palabras visibles con cupo 3.\n        """
            contenido = 0
            tokens = len(sueltas)
            j = i
            while j < n and roles[j] is None:
                if j > i:
                    if hay_frontera_antes([palabras[j - 1]]):
                        break
                    else:
                        if palabras[j]['start'] - palabras[j - 1]['end'] > PAUSA_SILENCIO:
                            break
                if not es_conector(palabras[j]['word']):
                    contenido += 1
                    if contenido > 1:
                        return False
                tokens += 1
                j += 1
            return tokens <= por_basico + 1
        for i, w in enumerate(palabras):
            rol = roles[i]
            texto = w['word'].strip()
            if rol is None:
                cerrar_bloque()
                if hay_silencio_antes(w, sueltas):
                    cerrar_sueltas()
                if hay_frontera_antes(sueltas):
                    cerrar_sueltas()
                if por_basico < 2:
                    sueltas.append(w)
                    cerrar_sueltas()
                    continue
                else:
                    if len(sueltas) + 1 > por_basico + 1 or (peso_sueltas() + peso_basico(w['word']) > por_basico and (not resto_huerfano(i))):
                        colgantes = []
                        while sueltas and es_conector(sueltas[(-1)]['word']):
                                colgantes.append(sueltas.pop())
                        colgantes.reverse()
                        if not sueltas:
                            sueltas.extend(colgantes)
                            colgantes = []
                        cerrar_sueltas()
                        sueltas.extend(colgantes)
                    sueltas.append(w)
            else:
                cerrar_sueltas()
                if hay_silencio_antes(w, palabras_bloque, PAUSA_BLOQUE):          # v5.5: un respiro de 0,6 s ya vuelve a armar el bloque (antes 1,5 s)
                    cerrar_bloque()
                if hay_frontera_antes(palabras_bloque):
                    cerrar_bloque()
                lleno = bool(lineas and tope and rol == lineas[(-1)]['role']
                             and peso_linea(lineas[(-1)]['text']) + (pc_ if es_conector(texto) else 1.0) > tope.get(rol, 99) + 1e-6)
                if lineas and rol == lineas[(-1)]['role'] and not lleno:
                    lineas[(-1)]['text'] += ' ' + texto
                    palabras_bloque.append(w)
                else:
                    if lineas and ORDEN_ROL[rol] <= ORDEN_ROL[lineas[(-1)]['role']]:
                            cerrar_bloque()
                    lineas.append({'role': rol, 'text': texto, 'start': round(w['start'], 3)})
                    palabras_bloque.append(w)
        cerrar_bloque()
        cerrar_sueltas()
        for k in range(len(bloques) - 1):
            if bloques[k]['end'] > bloques[k + 1]['start']:
                bloques[k]['end'] = bloques[k + 1]['start']
        _cerrar_huecos(bloques, fin_video)
        proteger_animaciones(bloques)
        if capitalizar:
            return _capitalizar_lineas(bloques)
        else:
            return bloques
def proteger_animaciones(bloques):
    """FIX DE ANIMACIÓN (v5.7, pedido: «algunos textos no aparecen porque pasan muy rápido y no da tiempo a la animación»).

    Cada línea entra cuando se dice su primera palabra y se queda hasta que acaba el bloque (se estira hasta el bloque siguiente, o hasta
    la pausa). Si en habla rápida una línea se ve menos que lo que tarda su animación de entrada MÁS un momento con el texto completo,
    el clip de Resolve termina antes de que el texto llegue a mostrarse. A esas líneas cortas (y solo a ellas) se les marca
    'salto_anim' = segundos que el script de Resolve adelanta el arranque de la animación: entra más rápido, pero SE VE. Las líneas con
    tiempo de sobra no llevan marca y reproducen su entrada entera. Idempotente: recalcula desde cero. Devuelve los mismos bloques."""
    for b in bloques:
        try:
            fin = float(b.get('end') or 0)
            inicio = float(b.get('start') or 0)
        except (TypeError, ValueError):
            continue
        for l in b.get('lines') or []:
            l.pop('salto_anim', None)
            try:
                visible = fin - float(l.get('start', inicio) or inicio)
            except (TypeError, ValueError):
                continue
            falta = ANIM_ENTRADA_S + MIN_VISIBLE_S - visible
            if falta > 0:
                l['salto_anim'] = round(min(ANIM_ENTRADA_S, falta), 3)
    return bloques
def a_dos_lineas(bloques):
    """Convierte bloques de 3 lineas al ritmo de 2 (motor \'dos_lineas\').\n\n    El look Gadzhi pedido literal (v1.0.51): texto corto arriba + palabra\n    clave GRANDE debajo, nunca tres lineas. La linea de complemento se\n    SEPARA a su propio bloque simple (rol \'base\'): sus palabras no se\n    pierden, salen DESPUES de la clave como pantalla propia — el ritmo de\n    pantallas cortas del look.\n\n    Es una transformacion sobre los bloques ya armados, no otro armador:\n    build_manual_cues guarda en cada linea el momento REAL en que se dice\n    su primera palabra (v1.0.28), asi que el corte usa tiempos medidos, no\n    inventados. Y al no tocar repartir_bloque/segmentar, el motor de 3\n    lineas queda intacto.\n\n    Todo el texto pasa a MAYUSCULAS: es rasgo del look, igual que el\n    .upper() de _armar_grupos_cortos en destacados.\n    """
    salida = []
    for b in bloques:
        lineas = b.get('lines') or []
        comp = [l for l in lineas if l.get('role') == 'complement']
        resto = [dict(l, text=(l.get('text') or '').upper()) for l in lineas
                 if l.get('role') != 'complement']
        if not comp:
            salida.append(dict(b, lines=resto))
            continue
        else:
            corte = min((float(l.get('start', b['start'])) for l in comp))
            corte = round(min(max(corte, b['start']), b['end']), 3)
            if resto and corte > b['start']:
                salida.append(dict(b, lines=resto, end=corte, fin_hablado=round(min(b['fin_hablado'], corte), 3)))
            else:
                if resto:
                    pass
            texto = ' '.join((l.get('text') or '' for l in comp)).strip().upper()
            if texto:
                salida.append({'start': corte, 'end': b['end'], 'fin_hablado': b['fin_hablado'], 'lines': [{'role': 'base', 'text': texto, 'start': corte}]})
    return proteger_animaciones(salida)
def _cerrar_huecos(bloques, fin_video=None):
    """Estira cada bloque hasta que empieza el siguiente. Sin huecos.\n\n    \'fin_video\' (segundos, v2.0.6): donde termina el medio transcrito. El\n    ULTIMO bloque termina ahi, no con el hold — ver abajo.\n\n    El texto tiene que seguir en pantalla mientras se termina de hablar. Que\n    cada bloque acabase justo en su ultima palabra dejaba la pantalla en\n    blanco entre bloque y bloque, y se leia como si el subtitulo se borrara\n    antes de tiempo.\n\n    EL TOPE IMPORTA. Sin el, sobre una toma muda de treinta segundos se\n    quedaria colgado el ultimo subtitulo todo ese rato. Con HOLD_MAXIMO, el\n    texto aguanta un par de segundos de mas -que es lo que hace falta para\n    terminar de leerlo- y despues se va.\n\n    OJO: \'fin_hablado\' NO se toca. Es el unico dato que recuerda cuando\n    termino la voz de verdad, y de el depende que el fundido de salida caiga\n    en el tiempo prestado y no encima de la ultima palabra.\n\n    Esto CAMBIA la regla de la v1.0.23 (\"el hueco por silencio sale solo del\n    audio\"). Se hizo a peticion expresa: se prefiere texto de mas en pantalla\n    a texto que desaparece antes de que acabes la frase.\n    """
    for k, bloque in enumerate(bloques):
        limite = max(bloque['end'], bloque['fin_hablado'] + HOLD_MAXIMO)
        if k + 1 < len(bloques):
            limite = min(limite, bloques[k + 1]['start'])
        elif fin_video is not None and fin_video > bloque['start']:
            bloque['end'] = round(fin_video, 3)
            continue
        bloque['end'] = round(max(bloque['end'], limite), 3)
    return bloques
LOOKS_DESTACADOS = ('hormozi', 'gadzhi', 'acumulativo', 'pintado')
MAX_PALABRAS_GRUPO = {'hormozi': 3, 'gadzhi': 2}
MIN_DURACION_DESTACADOS = 0.35
def _armar_grupos_cortos(palabras, resaltadas, look, min_duration, pause_break):
    """Agrupa de a pocas palabras: usado por \'hormozi\' y \'gadzhi\'.\n\n    Corta el grupo cuando: aparece una palabra marcada (que ademas se queda\n    SOLA en el suyo, ver arriba), hay un silencio real antes de la palabra,\n    la palabra anterior cierra una idea (FIN_FUERTE), o el grupo ya llego al\n    maximo del look.\n    """
    maximo = MAX_PALABRAS_GRUPO.get(look, 3)
    bloques = []
    grupo = []
    def cerrar():
        if not grupo:
            return
        else:
            ws = [w for w, _ in grupo]
            resaltado = any((r for _, r in grupo))
            texto = ' '.join((w['word'].strip() for w in ws)).upper()
            inicio = ws[0]['start']
            fin = max(ws[(-1)]['end'], inicio + min_duration)
            bloques.append({'start': round(inicio, 3), 'end': round(fin, 3), 'fin_hablado': round(ws[(-1)]['end'], 3), 'lines': [{'role': 'resaltada' if resaltado else 'normal', 'text': texto, 'start': round(inicio, 3)}]})
            grupo.clear()
    for i, w in enumerate(palabras):
        if grupo and w['start'] - grupo[(-1)][0]['end'] > pause_break:
                cerrar()
        if resaltadas[i]:
            cerrar()
            grupo.append((w, True))
            cerrar()
        else:
            grupo.append((w, False))
            if len(grupo) >= maximo or w['word'].strip().endswith(FIN_FUERTE):
                cerrar()
    cerrar()
    return bloques
def _armar_acumulativo(palabras, resaltadas, min_duration, pause_break):
    """El look \'acumulativo\': dentro de cada frase, un grupo por cada\n    palabra nueva que se suma (\'hola\' -> \'hola mundo\' -> \'hola mundo\n    bonito\'). No hace falta recentrar nada a mano: el Text+ ya centra su\n    texto solo (HorizontalJustificationNew), asi que basta con ir cambiando\n    el StyledText de un bloque al siguiente.\n\n    Usa segmentar() -la misma particion en frases que el motor automatico-\n    para saber donde empieza y termina cada frase que se va a ir revelando.\n    """
    bloques = []
    for desde, hasta in segmentar(palabras, pause_break):
        tramo = palabras[desde:hasta]
        for k in range(1, len(tramo) + 1):
            parcial = tramo[:k]
            ultima = parcial[(-1)]
            texto = ' '.join((w['word'].strip() for w in parcial))
            inicio = ultima['start']
            fin = max(ultima['end'], inicio + min_duration)
            bloques.append({'start': round(inicio, 3), 'end': round(fin, 3), 'fin_hablado': round(ultima['end'], 3), 'lines': [{'role': 'resaltada' if resaltadas[desde + k - 1] else 'normal', 'text': texto, 'start': round(inicio, 3)}]})
    return bloques
def _armar_pintado(palabras, resaltadas, pause_break, min_duration, medir_ancho):
    """El look \'pintado\': toda la frase en pantalla a la vez, cada palabra\n    en su propio Text+ y con su propio momento de encendido.\n\n    Devuelve None si alguna palabra de algun tramo no se pudo medir -fuente\n    no encontrada, Pillow ausente-: es la señal para que quien llama degrade\n    TODO el resultado a otro look, nunca coloque una frase a medias.\n\n    Cada palabra lleva \'ancho_em\': cuanto ocupa, como fraccion de la ALTURA\n    del fotograma (ver medir_texto.py) -no del ancho-. NO se calcula aca\n    donde va cada palabra en X: eso hace falta dividirlo por la relacion de\n    aspecto del timeline (ancho/alto), y esa solo se conoce DENTRO de\n    Resolve. Por eso el centrado y el acomodo lado a lado los hace el script\n    de Resolve, con la resolucion real -mismo patron que \'adelanto_frames\'\n    y \'offset_frames\': lo que solo se sabe adentro, viaja sin convertir-.\n    """
    bloques = []
    for desde, hasta in segmentar(palabras, pause_break):
        tramo = palabras[desde:hasta]
        textos = [w['word'].strip() for w in tramo]
        anchos = medir_ancho(textos + [' '])
        if anchos is None or len(anchos) != len(textos) + 1:
            return None
        else:
            *anchos_palabras, ancho_espacio = anchos
            if any((a is None for a in anchos_palabras)) or ancho_espacio is None:
                return None
            else:
                inicio = tramo[0]['start']
                fin = max(tramo[(-1)]['end'], inicio + min_duration)
                lista_palabras = [{'texto': textos[i], 'resaltada': resaltadas[desde + i], 'ancho_em': round(anchos_palabras[i], 5), 'start': round(w['start'], 3)} for i, w in enumerate(tramo)]
                bloques.append({'start': round(inicio, 3), 'end': round(fin, 3), 'fin_hablado': round(tramo[(-1)]['end'], 3), 'look': 'pintado', 'espacio_em': round(ancho_espacio, 5), 'palabras': lista_palabras})
    return bloques
CHARS_POR_FILA_PINTADO = {'v': 18, 'c': 24, 'h': 36}
def _segmentar_por_presupuesto(palabras, presupuesto_chars, pause_break):
    """Como segmentar(), pero el techo del tramo es un PRESUPUESTO DE\n    CARACTERES (limite de fila x filas maximas), no un conteo de palabras.\n\n    Es una hermana de segmentar() a proposito: aquella la comparten el\n    motor de 3 lineas y las sugerencias, y cambiarle el techo desviaria\n    todo lo demas. Corta por lo mismo de siempre (FIN_FUERTE, pausa larga)\n    y ademas cuando el texto acumulado ya no cabe en la pantalla pintada.\n    Una palabra sola mas larga que el presupuesto va entera: partir una\n    palabra seria peor.\n    """
    n = len(palabras)
    tramos = []
    i = 0
    while i < n:
        limite = i
        largo = 0
        while limite < n:
            texto = palabras[limite]['word'].strip()
            nuevo = largo + (1 if largo else 0) + len(texto)
            if limite > i and nuevo > presupuesto_chars:
                    break
            largo = nuevo
            siguiente = palabras[limite + 1] if limite + 1 < n else None
            limite += 1
            if _hay_corte_fuerte(palabras[limite - 1], siguiente, pause_break):
                break
        tramos.append((i, limite))
        i = limite
    return tramos
def _filas_por_caracteres(textos, limite):
    """Indices de palabras por fila, greedy por caracteres (espacios\n    incluidos). Una fila nunca queda vacia: una palabra sola mas larga que\n    el limite va entera y sobresale, que es lo menos malo."""
    filas = []
    fila = []
    largo = 0
    for i, t in enumerate(textos):
        nuevo = largo + (1 if fila else 0) + len(t)
        if fila and nuevo > limite:
            filas.append(fila)
            fila = [i]
            largo = len(t)
        else:
            fila.append(i)
            largo = nuevo
    if fila:
        filas.append(fila)
    return filas
def _armar_pintado_v2(palabras, resaltadas, pause_break, min_duration, medir_ancho, limite_chars, filas_max, modo):
    """El pintado v2 (v1.0.52): filas por CARACTERES y datos para los\n    bloques multilinea gemelos de los colocadores (3 capas, no 2 por\n    palabra).\n\n    Cada cue lleva las filas YA armadas (texto por fila) y, por palabra,\n    su fila y dos medidas: \'x_antes_em\' (el ancho del texto de SU fila\n    antes de ella, espacio incluido — el corrimiento del ancla para\n    pintarla encima) y \'ancho_em\'. Todo medido con el MISMO estilo que\n    dibujara la base (fraccion de la ALTURA, como siempre); la conversion\n    a ancho y el centrado los hace el script de Resolve con la resolucion\n    real. \'modo\' viaja tal cual: \"acumula\" (Hormozi: el prefijo dicho se\n    queda pintado) o \"viaja\" (Gadzhi: solo la palabra actual).\n\n    Devuelve None si algo no se pudo medir: quien llama degrada entero,\n    nunca a medias (la regla del pintado v1, intacta).\n    """
    bloques = []
    filas_max = max(1, filas_max)
    presupuesto = max(limite_chars, limite_chars * filas_max)
    pendientes = list(_segmentar_por_presupuesto(palabras, presupuesto, pause_break))
    while pendientes:
        desde, hasta = pendientes.pop(0)
        tramo = palabras[desde:hasta]
        textos = [w['word'].strip() for w in tramo]
        filas = _filas_por_caracteres(textos, limite_chars)
        if len(filas) > filas_max:
            corte = desde + filas[filas_max][0]
            pendientes.insert(0, (corte, hasta))
            hasta = corte
            tramo = palabras[desde:hasta]
            textos = textos[:filas[filas_max][0]]
            filas = filas[:filas_max]
        filas_texto = [' '.join((textos[j] for j in fila)) for fila in filas]
        fila_de = {}
        antes_de = {}
        for i_f, fila in enumerate(filas):
            for k, j in enumerate(fila):
                fila_de[j] = i_f
                antes = ' '.join((textos[m] for m in fila[:k]))
                antes_de[j] = antes + ' ' if antes else ''
        a_medir = filas_texto + [antes_de[i] for i in range(len(textos))] + textos
        medidas = medir_ancho(a_medir)
        if medidas is None or len(medidas) != len(a_medir) or any((m is None for m in medidas)):
            return None
        nf = len(filas_texto)
        anchos_filas = [round(m, 5) for m in medidas[:nf]]
        anchos_antes = medidas[nf:nf + len(textos)]
        anchos_palabra = medidas[nf + len(textos):]
        inicio = tramo[0]['start']
        fin = max(tramo[(-1)]['end'], inicio + min_duration)
        bloques.append({'start': round(inicio, 3), 'end': round(fin, 3), 'fin_hablado': round(tramo[(-1)]['end'], 3), 'look': 'pintado', 'modo': modo, 'filas_texto': filas_texto, 'ancho_filas_em': anchos_filas, 'palabras': [{'texto': textos[i], 'resaltada': resaltadas[desde + i], 'start': round(w['start'], 3), 'fila': fila_de[i], 'x_antes_em': round(anchos_antes[i], 5), 'ancho_em': round(anchos_palabra[i], 5)} for i, w in enumerate(tramo)]})
    return bloques
def build_destacados_cues(words, roles, look='hormozi', min_duration=MIN_DURACION_DESTACADOS, pause_break: float=PAUSA_SILENCIO, medir_ancho=None, limite_chars=None, filas_max=3, modo_pintado='acumula', fin_video=None):
    """Arma los bloques del modo destacados.\n\n    \'roles\' es la MISMA lista paralela que usa build_manual_cues -una por\n    cada palabra no vacia de \'words\'-: cualquier rol que no sea None cuenta\n    como palabra \"marcada\" (la que lleva el color de realce), la haya\n    marcado el usuario a mano o la IA. No hace falta un esquema de marcas\n    distinto: \'destacados\' reusa el mismo.\n\n    El look \'pintado\' necesita \'medir_ancho\' (ver medir_texto.py): sin saber\n    cuanto ocupa cada palabra no hay forma de colocarlas sin que se separen\n    de mas o se pisen. Si ese look no puede medir, esta funcion devuelve\n    None -nunca un resultado a medias- y quien llama decide degradar a\n    \'acumulativo\', que no necesita anchos.\n    """
    if look not in LOOKS_DESTACADOS:
        raise ValueError(f'look desconocido: {look!r}. Debe ser uno de {LOOKS_DESTACADOS}')
    else:
        palabras = [w for w in words if w['word'].strip()]
        n = len(palabras)
        if len(roles) != n:
            raise ValueError(f'\'roles\' tiene {len(roles)} elementos pero hay {n} palabras; tienen que coincidir exactamente.')
        else:
            if not palabras:
                return []
            else:
                resaltadas = [r is not None for r in roles]
                if look == 'pintado':
                    if medir_ancho is None:
                        raise ValueError('el look \'pintado\' necesita \'medir_ancho\': sin eso no se puede saber donde colocar cada palabra.')
                    else:
                        if limite_chars:
                            bloques = _armar_pintado_v2(palabras, resaltadas, pause_break, min_duration, medir_ancho, limite_chars, filas_max, modo_pintado)
                        else:
                            bloques = _armar_pintado(palabras, resaltadas, pause_break, min_duration, medir_ancho)
                        if bloques is None:
                            return
                else:
                    if look == 'acumulativo':
                        bloques = _armar_acumulativo(palabras, resaltadas, min_duration, pause_break)
                    else:
                        bloques = _armar_grupos_cortos(palabras, resaltadas, look, min_duration, pause_break)
                for k in range(len(bloques) - 1):
                    if bloques[k]['end'] > bloques[k + 1]['start']:
                        bloques[k]['end'] = bloques[k + 1]['start']
                _cerrar_huecos(bloques, fin_video)
                return bloques


# ---------------------------------------------------------------------------------------------------------------------
# v5.4: grupos ESTRICTOS. «Arriba 2 · Principal 1 · Abajo 1» es una regla: cada grupo lleva EXACTAMENTE esas palabras
# (los conectores cuentan como palabra) y la principal es la palabra importante, no la que cae por azar. Se planifica toda
# la oracion de una vez (programacion dinamica) para que los grupos no se pisen, cubran lo mas posible y cada principal sea
# la de mas peso que cabe con la estructura completa.
def grupos_estrictos(palabras, importancia, n_ctx, n_main, n_cmp, premio_cobertura=0.3, por_pausas=False):
    """{indice: 'context'|'main'|'complement'} para todo el guion. 'importancia' = lista paralela (0..1+, <0 = no puede ser
    principal). Una oracion mas corta que el grupo completo usa un grupo reducido (siempre con su principal)."""
    n_ctx, n_main, n_cmp = (max(0, int(n_ctx)), max(1, int(n_main)), max(0, int(n_cmp)))
    # por_pausas: la frase (lo que va entre dos pausas o signos) se arma ENTERA en un solo bloque, aunque pase de lo pedido:
    # el bloque aguanta hasta el suspiro y recien ahi se arma otro (sin palabras que se borran a media frase).
    # v5.7 (pedido: «solo obedece las palabras por linea de principal»): Arriba y Abajo son topes ESTRICTOS, igual que Principal. Antes, con
    # por_pausas, una frase podia pasar hasta el doble (min. 4) de lo pedido; ahora la frase solo se queda en UN bloque si cabe en lo pedido.
    tope_ctx, tope_cmp = n_ctx, n_cmp
    roles = {}

    def _pal(j):
        w = palabras[j]
        return str(w.get('word', '')) if isinstance(w, dict) else str(w)
    for desde, hasta in segmentar_oraciones(palabras):
        m = hasta - desde
        if m <= 0:
            continue
        if por_pausas and m <= tope_ctx + n_main + tope_cmp:
            # la frase CABE en un bloque: UN solo grupo con toda la frase (sin esto el reparto por importancia la trocea en
            # grupos de una palabra, cada una «principal»). La principal es la palabra de mas peso; antes, el contexto; despues, el complemento.
            mejor_j, mejor_v = None, None
            for j in range(0, m - n_main + 1):
                c, k = j, m - j - n_main
                if c > tope_ctx or k > tope_cmp:
                    continue
                imp = [importancia[desde + j + q] for q in range(n_main)]
                if min(imp) < 0:
                    continue
                # un poco de preferencia por una principal hacia el centro-izquierda (el ritmo natural: contexto corto, remate largo)
                v = sum(imp) - 0.03 * abs(c - min(n_ctx, m // 2))
                if mejor_v is None or v > mejor_v:
                    mejor_j, mejor_v = j, v
            if mejor_j is not None:
                for q in range(m):
                    roles[desde + q] = 'context' if q < mejor_j else ('main' if q < mejor_j + n_main else 'complement')
                continue
        # candidatos: (inicio_local, c, k) -> grupo [inicio, inicio + c + n_main + k) con 'c' de contexto y 'k' de complemento.
        # v5.7: dos grupos NUNCA quedan pegados «principal con principal» (un grupo sin complemento seguido de otro sin contexto formaba una
        # racha de 2×n palabras del mismo rol: en el editor parecía pasarse del tope aunque los bloques sí lo respetaran). Se lleva un
        # estado: libre[fin] = mejor valor sin grupo que termine justo en 'fin' sin complemento; pegado[fin] = con uno que sí termina así.
        libre = [0.0] + [None] * m
        pegado = [None] * (m + 1)
        e_libre = [None] * (m + 1)        # cómo se llegó: ('salto', estado_previo) o ('grupo', ini, c, k, estado_previo)
        e_pegado = [None] * (m + 1)
        for fin in range(1, m + 1):
            previo = [v for v in (libre[fin - 1], pegado[fin - 1]) if v is not None]
            libre[fin] = max(previo)
            e_libre[fin] = ('salto', 0 if (libre[fin - 1] is not None and libre[fin - 1] >= (pegado[fin - 1] if pegado[fin - 1] is not None else -1e18)) else 1)
            for c in range(tope_ctx, -1, -1):
                for k in range(tope_cmp, -1, -1):
                    tam = c + n_main + k
                    ini = fin - tam
                    if ini < 0:
                        continue
                    p_main = range(desde + ini + c, desde + ini + c + n_main)
                    imp = [importancia[j] for j in p_main]
                    if min(imp) < 0:
                        continue                         # una principal no puede ser un conector ni una muletilla
                    # el grupo anterior: con contexto delante, cualquiera; sin contexto, uno que NO termine en principal
                    opciones = [(0, libre[ini])] + ([] if c == 0 else [(1, pegado[ini])])
                    opciones = [(f, v) for f, v in opciones if v is not None]
                    if not opciones:
                        continue
                    f_prev, v_prev = max(opciones, key=lambda o: o[1])
                    faltan = max(0, n_ctx - c) + max(0, n_cmp - k)
                    valor = v_prev + sum(imp) + premio_cobertura * tam - 0.6 * faltan - (1.2 if por_pausas else 0.0)   # cada grupo de mas cuesta: la frase prefiere quedarse en UN bloque
                    if k == 0:
                        if pegado[fin] is None or valor > pegado[fin] + 1e-9:
                            pegado[fin], e_pegado[fin] = valor, ('grupo', ini, c, k, f_prev)
                    elif valor > libre[fin] + 1e-9:
                        libre[fin], e_libre[fin] = valor, ('grupo', ini, c, k, f_prev)
        fin = m
        estado = 1 if (pegado[m] is not None and pegado[m] > libre[m] + 1e-9) else 0
        while fin > 0:
            e = (e_pegado if estado else e_libre)[fin]
            if e is None:
                fin -= 1
                estado = 0
                continue
            if e[0] == 'salto':
                estado = e[1]
                fin -= 1
                continue
            _t, ini, c, k, estado_previo = e
            for j in range(c):
                roles[desde + ini + j] = 'context'
            for j in range(n_main):
                roles[desde + ini + c + j] = 'main'
            # v5.8: el bloque no acaba en un conector («cómo multiplicamos las | ventas»): se recortan del complemento las palabras colgantes del final
            # y abren el bloque siguiente («las ventas»). El grupo elegido es el mismo; solo se le quita la cola.
            k_ef = k
            if EVITAR_COLGANTES:
                while k_ef > 0 and es_colgante(_pal(desde + ini + c + n_main + k_ef - 1)):
                    k_ef -= 1
            for j in range(k_ef):
                roles[desde + ini + c + n_main + j] = 'complement'
            fin = ini
            estado = estado_previo
    return roles
