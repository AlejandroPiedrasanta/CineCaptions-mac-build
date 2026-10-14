# CineCaptions · By Cinema Productions
# 1_codigo/ortografia.py — revisión ortográfica del editor (marca y propone, nunca corrige solo).
"""\nortografia.py\n-------------\nMarca las palabras que el diccionario del idioma no conoce, y propone\nalternativas. Lo usa la ventana de seleccion, tanto en dinamicos como en\nbasicos.\n\nQUE HACE Y QUE NO\n=================\nEsto NO es un corrector automatico, y no puede serlo: los errores tipicos de\nWhisper son homofonos (\"haber\" por \"a ver\", \"hecho\" por \"echo\") y nombres\npropios mal transcritos, y los dos pasan el diccionario sin despeinarse\nporque son palabras que existen. Lo que si detecta son palabras que no\nexisten en el idioma, que es el otro tercio de los errores.\n\nPor eso subraya y sugiere, y la ultima palabra siempre es del usuario. Un\ncorrector que aplicara sus cambios solo destrozaria marcas, nombres y\nterminos tecnicos, que es justo lo que suele ir en la linea destacada.\n\nEL DICCIONARIO\n==============\npyspellchecker: Python puro, sin binarios, sin descargas y sin red. Trae\ndiccionarios por frecuencia de uso. Se importa PEREZOSAMENTE (dentro de la\nfuncion, no arriba) para no pagar la carga en el arranque de quien no abra\nnunca la ventana de palabras.\n"""
import unicodedata
from i18n import tr, nombre_idioma as nombre_idioma_ui
IDIOMAS = {'es': 'español', 'en': 'inglés', 'pt': 'portugués', 'fr': 'francés', 'it': 'italiano', 'de': 'alemán', 'ru': 'ruso', 'ar': 'árabe', 'nl': 'neerlandés', 'eu': 'euskera', 'lv': 'letón', 'fa': 'persa'}
PUNTUACION = '.,;:!¡?¿…\"\'“”«»()[]—–-'
_CACHE = {}
def idioma_soportado(codigo):
    return _normalizar_codigo(codigo) in IDIOMAS
def nombre_idioma(codigo):
    c = _normalizar_codigo(codigo)
    if c in IDIOMAS:
        return nombre_idioma_ui(c, IDIOMAS.get(c, codigo))
    else:
        return codigo
def _normalizar_codigo(codigo):
    """\'es-419\', \'ES\', \'auto\' -> \'es\' / \'\'."""
    if not codigo:
        return ''
    else:
        codigo = str(codigo).strip().lower().replace('_', '-').split('-')[0]
        return '' if codigo == 'auto' else codigo
def _corrector(codigo):
    """El SpellChecker del idioma, cacheado. None si no hay diccionario.\n\n    Cargarlo cuesta un momento (descomprime un JSON de decenas de miles de\n    palabras), asi que se guarda: la ventana lo pide una vez por revision y\n    puede haber varias en la misma sesion.\n    """
    codigo = _normalizar_codigo(codigo)
    if codigo in _CACHE:
        return _CACHE[codigo]
    else:
        corrector = None
        if codigo in IDIOMAS:
            try:
                from spellchecker import SpellChecker
                corrector = SpellChecker(language=codigo, distance=2)
            except Exception:
                corrector = None
        _CACHE[codigo] = corrector
        return corrector
def limpiar(texto):
    """La palabra tal como hay que buscarla en el diccionario."""
    return str(texto or '').strip().strip(PUNTUACION).strip()
def _tiene_letras(palabra):
    return any((unicodedata.category(c).startswith('L') for c in palabra))
def _se_revisa(palabra, es_primera):
    """Si esta palabra entra en la revision, o se deja en paz.\n\n    Se dejan fuera, en este orden:\n\n      - lo que no tiene letras (signos sueltos, guiones);\n      - lo que lleva cifras (\"20%\", \"3x\", \"1ro\"): el diccionario no las\n        conoce y las marcaria todas;\n      - las palabras de una o dos letras, donde cualquier sugerencia es ruido;\n      - las que empiezan por mayuscula EN MEDIO de la frase. Son nombres\n        propios, marcas y siglas, o sea el falso positivo garantizado: en un\n        guion comercial hay decenas y subrayarlos todos hace que se ignore la\n        revision entera. La primera palabra de la frase no cuenta, porque ahi\n        la mayuscula no dice nada.\n    """
    limpia = limpiar(palabra)
    if not limpia or not _tiene_letras(limpia):
        return False
    else:
        if any((c.isdigit() for c in limpia)):
            return False
        else:
            if len(limpia) <= 2:
                return False
            else:
                if not es_primera and limpia[:1].isupper():
                    return False
                else:
                    return True
def revisar(palabras, idioma):
    """Devuelve el conjunto de indices de las palabras dudosas.\n\n    \'palabras\' es la lista de dicts de la ventana (cada uno con \'word\'); el\n    indice es la posicion en esa lista.\n\n    Es la parte BARATA: mirar si una palabra esta en el diccionario es una\n    busqueda y ya. Las sugerencias no se calculan aqui — se piden con\n    sugerencias_para() solo para la palabra en la que el usuario hace clic,\n    porque esa parte cuesta un tercio de segundo por palabra y hacerlo con\n    las 200 del guion serian mas de un minuto de espera para nada.\n\n    Si no hay diccionario para ese idioma devuelve un conjunto vacio, y la\n    ventana lo explica en vez de callarse.\n    """
    corrector = _corrector(idioma)
    if corrector is None or not palabras:
        return set()
    else:
        candidatas, posiciones = ([], [])
        empieza_frase = True
        for i, w in enumerate(palabras):
            texto = str(w.get('word', ''))
            if _se_revisa(texto, empieza_frase):
                candidatas.append(limpiar(texto).lower())
                posiciones.append(i)
            empieza_frase = texto.rstrip(PUNTUACION.replace('.', '').replace('!', '').replace('?', '')).endswith(('.', '!', '?', '…'))
        if not candidatas:
            return set()
        else:
            try:
                desconocidas = corrector.unknown(candidatas)
            except Exception:
                return set()
            if desconocidas and _normalizar_codigo(idioma) == 'es':      # v5.5.7: el diccionario (es) trae casi solo lemas: «voy», «tiene», «gatos» no son faltas
                import ortografia_es
                desconocidas = {p for p in desconocidas if not ortografia_es.conocida(p, corrector)}
            return {i for i, p in zip(posiciones, candidatas) if p in desconocidas}
def sugerencias_para(palabra, idioma, maximo=5):
    """Alternativas para UNA palabra, ordenadas por frecuencia de uso.\n\n    Esta es la parte cara (~330 ms). Se llama al hacer clic en una palabra\n    subrayada, nunca en bucle sobre el guion entero. Devuelve [] si no hay\n    nada razonable que proponer: marcar la palabra sirve igual, aunque no\n    sepamos por que cambiarla.\n    """
    corrector = _corrector(idioma)
    limpia = limpiar(palabra)
    if corrector is None or not limpia:
        return []
    else:
        try:
            candidatas = corrector.candidates(limpia.lower()) or set()
        except Exception:
            return []
        candidatas = {c for c in candidatas if c != limpia.lower()}
        if not candidatas:
            return []
        else:
            ordenadas = sorted(candidatas, key=lambda c: corrector.word_frequency[c], reverse=True)
            return [_con_el_mismo_caso(limpia, c) for c in ordenadas[:maximo]]
def _con_el_mismo_caso(original, sugerencia):
    """\'Desqento\' -> \'Descuento\', \'DESQENTO\' -> \'DESCUENTO\'."""
    if original.isupper():
        return sugerencia.upper()
    else:
        if original[:1].isupper():
            return sugerencia[:1].upper() + sugerencia[1:]
        else:
            return sugerencia
def aplicar(texto_original, sugerencia):
    """Cambia la palabra dejando en su sitio la puntuacion que la rodeaba.\n\n    Whisper escribe \"descuento,\" con la coma pegada; si se sustituyera el\n    token entero se perderia. Se busca el nucleo y se reemplaza solo eso.\n    """
    original = str(texto_original or '')
    limpia = limpiar(original)
    if not limpia:
        return original
    else:
        i = original.find(limpia)
        if i < 0:
            return sugerencia
        else:
            return original[:i] + sugerencia + original[i + len(limpia):]
def resumen(dudosas, total):
    """Frase corta para la barra de la ventana."""
    n = len(dudosas)
    if not n:
        return tr('Ortografía: no encontré palabras raras.')
    else:
        if n == 1:
            return tr('Ortografía: 1 palabra dudosa de {total}. Haz clic en las subrayadas para corregirlas.', total=total)
        else:
            return tr('Ortografía: {n} palabras dudosas de {total}. Haz clic en las subrayadas para corregirlas.', n=n, total=total)


# ---------------------------------------------------------------------------------------------------------------------
# v5.4: correccion AUTOMATICA en español. El diccionario dice que palabras no existen; para elegir la correcta se usa la
# FONETICA del español (b/v, h muda, k/qu/c, c/s/z, g/j, ll/y, m antes de b/p, tildes): «ablando» -> «hablando» (no «blando»),
# «kiero» -> «quiero» (no «fiero»). Si ningun candidato suena igual ni se parece muchisimo, la palabra se deja como esta.
def _clave_fonetica(palabra):
    import re
    p = ''.join(c for c in unicodedata.normalize('NFD', str(palabra).lower()) if unicodedata.category(c) != 'Mn' or c == '\u0303')
    p = unicodedata.normalize('NFC', p)
    p = p.replace('ch', '#').replace('ll', 'y').replace('qu', 'k')
    p = re.sub(r'gu(?=[ei])', 'g', p)
    p = re.sub(r'g(?=[ei])', 'x', p)
    p = re.sub(r'c(?=[ei])', 's', p)
    p = p.replace('c', 'k').replace('z', 's').replace('v', 'b').replace('j', 'x').replace('h', '').replace('w', 'u')
    p = re.sub(r'm(?=[bp])', 'n', p)
    p = re.sub(r'(.)\1+', r'\1', p)
    return p


_CLAVES = {}


def _por_clave(corrector):
    """{clave fonética: [palabras frecuentes del diccionario]} (una vez, ~1 s, siempre en un hilo). El corrector solo propone lo que está a la
    MENOR distancia: si hay algo a una letra («aser» → «asar»), lo que suena igual a dos («hacer») ni sale. Esto lo encuentra por cómo suena."""
    if id(corrector) not in _CLAVES:
        indice = {}
        try:
            for w, n in corrector.word_frequency.dictionary.items():
                if n >= 8000 and len(w) >= 3:
                    indice.setdefault(_clave_fonetica(w), []).append(w)
        except Exception:
            indice = {}
        _CLAVES.clear()
        _CLAVES[id(corrector)] = indice
    return _CLAVES[id(corrector)]


def corregir_fonetico(palabras, idioma):
    """{indice: palabra corregida} de las palabras que el diccionario no conoce y tienen una correccion clara. Solo español."""
    if _normalizar_codigo(idioma) != 'es':
        return {}
    corrector = _corrector(idioma)
    if corrector is None:
        return {}
    cambios = {}
    for i in sorted(revisar(palabras, idioma)):
        texto = str(palabras[i].get('word', ''))
        orig = limpiar(texto)
        bajo = orig.lower()
        import ortografia_es
        if ortografia_es.ERRATAS.get(bajo, bajo) != bajo:            # v5.5.7: «kiero» → «quiero», «esque» → «es que» (inequívocas)
            cambios[i] = aplicar(texto, _con_el_mismo_caso(orig, ortografia_es.ERRATAS[bajo]))
            continue
        clave = _clave_fonetica(bajo)
        try:
            candidatas = [c for c in (corrector.candidates(bajo) or set()) if c != bajo]
        except Exception:
            candidatas = []
        candidatas += [c for c in _por_clave(corrector).get(clave, ()) if c != bajo]     # v5.5.7: «aser» → «hacer», «kiero» → «quiero» (a 2 letras)
        if not candidatas:
            continue
        elegidas = [c for c in candidatas if _clave_fonetica(c) == clave and corrector.word_frequency[c] >= 8000]   # v5.5.7: nada de rarezas («Voy» → «Boy»)
        tenia_tilde = any(unicodedata.category(c) == 'Mn' for c in unicodedata.normalize('NFD', bajo) if c not in '̃')
        if tenia_tilde:         # nunca se QUITA una tilde («quedó» -> «quedo» seria un error nuevo)
            elegidas = [c for c in elegidas if any(unicodedata.category(x) == 'Mn' for x in unicodedata.normalize('NFD', c))]
        if not elegidas:
            continue
        mejor = max(elegidas, key=lambda c: corrector.word_frequency[c])
        cambios[i] = aplicar(texto, _con_el_mismo_caso(orig, mejor))
    return cambios
