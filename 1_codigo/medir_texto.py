# CineCaptions · By Cinema Productions
# 1_codigo/medir_texto.py — mide cuánto ocupa cada palabra en pantalla (look «pintado»).
"""\nmedir_texto.py\n---------------\nCuanto mide cada palabra en pantalla. Lo necesita el look \'pintado\' del modo\ndestacados: varias palabras en la MISMA linea, cada una su propio Text+,\ncolocadas una al lado de otra -es la unica forma de pintar una sola palabra\nde otro color, porque el estilo por caracter no es accesible por script (ver\nCLAUDE.md, \"El reparto de un bloque\" / modo destacados)-. Sin saber cuanto\nocupa cada palabra no hay forma de colocarlas sin que se separen de mas o se\npisen.\n\nNO hace falta renderizar nada en Resolve para calibrar. El plan original\npreveia una vuelta por GrabStill + ExportStills, pero no hace falta: \'Size\'\nen un Text+ de Fusion es la altura del texto como FRACCION DE LA ALTURA DEL\nFOTOGRAMA -es una convencion documentada de Fusion, no algo que estemos\nadivinando-, asi que el tamano en pixeles es simplemente\n\'Size * alto_del_fotograma\'. Y el ANCHO de una palabra a ese tamano es una\npropiedad del propio archivo de fuente (la tabla \'hmtx\', el avance\nhorizontal de cada glifo): Fusion la lee de ahi para dibujar, y Pillow -que\ntambien usa FreeType- la lee de ahi para medir. Es el MISMO numero, no una\naproximacion, y no depende de como cada uno pinte los pixeles despues (eso\nsi podria variar por el anti-aliasing, pero el ANCHO del glifo no).\n\nOJO CON LA UNIDAD: esto NO devuelve fraccion del ANCHO del fotograma.\nDevuelve fraccion de la ALTURA -el mismo tipo de unidad que \'Size\'-, y a\nproposito: convertir a fraccion del ancho hace falta dividir por la relacion\nde aspecto del timeline (ancho/alto), y esa **solo se conoce dentro de\nResolve**. La app nunca ve la resolucion del timeline, igual que nunca ve el\nfps (ver CLAUDE.md, \"Los tiempos\"). Por eso este modulo no pide una\nresolucion: mide en una unidad que no depende de ninguna, y el script de\nResolve hace la ultima conversion con la resolucion real -exactamente el\nmismo patron que \'adelanto_frames\' y \'offset_frames\'-.\n\nSi la fuente no se encuentra, o Pillow no esta disponible, se devuelve None\ny NO se inventa un ancho aproximado: quien llama tiene que degradar a otro\nlook (aparicion acumulativa), nunca colocar texto a ciegas.\n"""
import fuentes_sistema as fs
TAMANO_REFERENCIA_PX = 1000
FACTOR_TRACKING = 0.06
CACHE_TAMANO = 64
_cache_fuente = {}
def _fuente_pillow(ruta, tam_px):
    """Un ImageFont.FreeTypeFont cacheado. None si Pillow no esta o falla."""
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    clave = (str(ruta), tam_px)
    if clave in _cache_fuente:
        return _cache_fuente[clave]
    else:
        try:
            objeto = ImageFont.truetype(str(ruta), tam_px)
        except Exception:
            objeto = None
        if len(_cache_fuente) >= CACHE_TAMANO:
            _cache_fuente.clear()
        _cache_fuente[clave] = objeto
        return objeto
def medidor(font, style, tamano_rel, tracking=1.0, extras=()):
    """Devuelve una funcion palabras -> anchos, o None si no se puede medir.\n\n    \'tamano_rel\' es el \'size\' del estilo (fraccion de la altura del\n    fotograma, igual que AUTO_STYLES) con el que se va a mostrar el texto.\n\n    La funcion devuelta acepta una lista de textos y devuelve una lista de\n    anchos como fraccion de la ALTURA del fotograma -no del ancho, ver la\n    nota del modulo-. Un espacio simple mide igual que cualquier otra\n    \'palabra\': se puede pedir su ancho como una mas.\n    """
    ruta = fs.ruta_de_fuente(font, style, extras=extras)
    if ruta is None:
        return
    else:
        fuente_ttf = _fuente_pillow(ruta, TAMANO_REFERENCIA_PX)
        if fuente_ttf is None:
            return
        else:
            factor = 1.0 + (float(tracking or 1.0) - 1.0) * FACTOR_TRACKING
            tam = float(tamano_rel or 0.05)
            def medir(textos):
                anchos = []
                for t in textos:
                    try:
                        ancho_px = fuente_ttf.getlength(str(t)) * factor
                    except Exception:
                        return
                    anchos.append(ancho_px / TAMANO_REFERENCIA_PX * tam)
                return anchos
            return medir
def anchos_relativos(textos, font, style, tamano_rel, tracking=1.0, extras=()):
    """Atajo de una sola llamada, para cuando no hace falta medir en bucle."""
    medir = medidor(font, style, tamano_rel, tracking, extras)
    if medir is None:
        return
    else:
        return medir(textos)
def fuente_disponible(font, style='Regular', extras=()):
    """Si hay o no un .ttf/.otf instalado para esa familia+estilo."""
    return fs.ruta_de_fuente(font, style, extras=extras) is not None
CAJA_EM_POR_DEFECTO = 1.2
def caja_em(font, style='Regular', extras=()):
    """Cuanto ocupa de alto una linea, en multiplos del tamaño nominal.\n\n    Es (ascendente + descendente) / tamaño_pedido leido del propio archivo de\n    la fuente. NO es 1.0: casi todas las tipografias dibujan por encima y por\n    debajo de su tamaño nominal. Montserrat da 1.219 y Georgia 1.137 — un\n    7,2% de diferencia que basta para que dos lineas que no se tocaban pasen\n    a solaparse.\n\n    Hace falta para separar bien las tres lineas del diseño de respaldo. Ese\n    calculo usaba un factor fijo (0.47) afinado a ojo para una fuente que ya\n    no se usa, y estaba POR DEBAJO del 0.5 que hace falta para que dos cajas\n    apiladas no se pisen: venia con solape de fabrica, y al cambiar de\n    tipografia se hizo visible.\n\n    Devuelve CAJA_EM_POR_DEFECTO si no se puede medir: sin fuente no se\n    adivina, pero tampoco se deja al llamante sin numero.\n    """
    ruta = fs.ruta_de_fuente(font, style, extras=extras)
    if ruta is None:
        return CAJA_EM_POR_DEFECTO
    fuente_ttf = _fuente_pillow(ruta, TAMANO_REFERENCIA_PX)
    if fuente_ttf is None:
        return CAJA_EM_POR_DEFECTO
    try:
        ascendente, descendente = fuente_ttf.getmetrics()
    except Exception:
        return CAJA_EM_POR_DEFECTO
    alto = (abs(ascendente) + abs(descendente)) / float(TAMANO_REFERENCIA_PX)
    return alto if 0.5 <= alto <= 3.0 else CAJA_EM_POR_DEFECTO
