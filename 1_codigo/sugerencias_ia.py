# CineCaptions · By Cinema Productions
# 1_codigo/sugerencias_ia.py — sugiere la palabra PRINCIPAL de cada bloque (motor clásico, sin IA instalada).
"""\nsugerencias_ia.py\n-----------------\nSugiere que palabras destacar en los subtitulos dinamicos.\n\nCOMO PIENSA\n===========\nNo decide palabra por palabra: decide POR BLOQUE, que es como se ven en\npantalla. El guion se parte en bloques igual que lo hace el modo automatico\n(`dynamic_subtitles.segmentar`), y dentro de cada bloque:\n\n  - Se elige UNA sola palabra principal, la de mas peso. Nunca puede ser un\n    conector, un articulo, un numero, un simbolo ni una palabra de una o dos\n    letras: eso lo garantiza `dynamic_subtitles.puntuar_palabra`, que\n    devuelve 0 para todas esas y por lo tanto quedan descartadas por\n    construccion, diga lo que diga el motor semantico.\n  - Lo que quede antes de la principal es contexto; lo que quede despues,\n    complemento. Si no hay palabras de un lado, el bloque sale de dos\n    lineas. Eso da los repartos que se ven bien:\n        contexto + principal + complemento\n        contexto + principal\n        principal + complemento\n  - Si en todo el bloque no hay nada que valga la pena destacar, el bloque\n    entero va como subtitulo normal (rol \"base\").\n\nEl motor de IA solo aporta UNA cosa: cuanto pesa semanticamente cada\npalabra dentro del tema del video (un numero de 0 a 1). Las reglas de\narmado son siempre las mismas, venga ese numero de donde venga. Asi una\nrespuesta rara del modelo no puede romper el layout.\n\nMOTORES (en orden de preferencia)\n=================================\n  1. KeyBERT local con embeddings BERT multilenguaje (si esta instalado).\n  2. Heuristico puro: sin dependencias, siempre disponible.\n\n(La rama LLM por API key existio de la v1.0.58 a la v1.0.61 y se RETIRO\nen la v1.0.62 — pedido literal: «incluye un gasto extra para el usuario\nque no creo que quieran pagarlo, elimina eso». La mejora vive en el\nheuristico y en el armado por oraciones.)\n"""
global _MODELO
global _MODELO_ERROR
import hashlib
import json
import threading
import time
from pathlib import Path
import dynamic_subtitles as dyn
SHARED_FOLDER = Path.home() / 'DaVinciSubtitles'
CACHE_DIR = SHARED_FOLDER / 'sugerencias_cache'
_MODELO = None
_MODELO_LOCK = threading.Lock()
_MODELO_ERROR = None
DENSIDAD_POR_DEFECTO = 0.85
VERSION_REGLAS = 11
VARIANTES = 4
_ALTERNATIVA = {0: 0, 1: 1, 2: 2, 3: 0}
_AJUSTE_DENSIDAD = {0: 0.0, 1: (-0.15), 2: 0.15, 3: (-0.3)}
def _texto_de(palabras):
    return ' '.join((str(w.get('word', '')).strip() for w in palabras))
def _hash_transcript(palabras, densidad, variante=0, tamanos=None, peso_conector=None):
    tam = ''.join((str(x) for x in dyn.normalizar_tamanos(tamanos)))
    peso = dyn.normalizar_peso_conector(peso_conector)
    clave = f'r{VERSION_REGLAS}|v{int(variante)}|{densidad:.2f}|t{tam}|c{peso:.1f}|{_texto_de(palabras)}'
    return hashlib.sha1(clave.encode('utf-8')).hexdigest()[:20]
def _cache_get(clave):
    ruta = CACHE_DIR / f'{clave}.json'
    if not ruta.exists():
        return
    else:
        try:
            return json.loads(ruta.read_text(encoding='utf-8'))
        except Exception:
            return None
def _cache_put(clave, sugerencias):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f'{clave}.json').write_text(json.dumps(sugerencias, ensure_ascii=False), encoding='utf-8')
    except Exception:
        return None
def precargar():
    """Dispara la carga del modelo en un hilo aparte. Idempotente.\n\n    El modelo BERT tarda unos segundos en cargar la primera vez. Se\n    arranca al abrir el programa para que, cuando el usuario llegue a la\n    pantalla de palabras, ya este listo.\n    """
    if _MODELO is not None or _MODELO_ERROR is not None:
        return None
    else:
        def _cargar():
            global _MODELO
            global _MODELO_ERROR
            with _MODELO_LOCK:
                if _MODELO is not None:
                    return
                else:
                    try:
                        from keybert import KeyBERT
                        from sentence_transformers import SentenceTransformer
                        encoder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                        _MODELO = KeyBERT(model=encoder)
                    except Exception as e:
                        _MODELO_ERROR = str(e)
        threading.Thread(target=_cargar, daemon=True).start()
def modelo_listo():
    return _MODELO is not None
def _esperar_modelo(timeout_s=60):
    if _MODELO is not None:
        return _MODELO
    else:
        if _MODELO_ERROR is not None:
            return
        else:
            precargar()
            t0 = time.time()
            while time.time() - t0 < timeout_s:
                if _MODELO is not None:
                    return _MODELO
                if _MODELO_ERROR is not None:
                    return
                time.sleep(0.2)
            return None
def _scores_keybert(palabras, idioma):
    """Peso semantico 0-1 por palabra, segun el tema del guion completo.\n\n    KeyBERT compara el embedding de cada palabra con el del texto entero,\n    o sea que puntua alto lo que representa DE QUE VA el video, no lo que\n    simplemente es largo.\n    """
    modelo = _esperar_modelo()
    if modelo is None:
        return
    else:
        transcript = _texto_de(palabras)
        if not transcript.strip():
            return {}
        else:
            try:
                pares = modelo.extract_keywords(transcript, keyphrase_ngram_range=(1, 1), stop_words=None, top_n=max(30, len(palabras) // 2), use_mmr=True, diversity=0.35)
            except Exception:
                return
            tabla = {}
            for kw, sc in pares:
                tabla[dyn._normalizar(kw)] = max(0.0, min(1.0, float(sc)))
            return {i: tabla.get(dyn._normalizar(str(w.get('word', ''))), 0.0) for i, w in enumerate(palabras)}
def _scores_heuristico(palabras, idioma):
    """Normaliza el puntaje de siempre a 0-1. Sin dependencias.\n\n    v1.0.61 («su IA no es muy inteligente»): puntuar_palabra mira cada\n    palabra SOLA — no sabe de que trata el video. La unica señal global\n    barata que si «entiende el mensaje» es la repeticion: una palabra de\n    contenido que aparece varias veces en el guion ES el tema (los\n    conectores y stopwords ya puntuan 0 y no se cuelan). El empujon es\n    multiplicativo para no tocar puntuar_palabra, que comparten los dos\n    motores y pinen los guardianes.\n    """
    crudos = [dyn.puntuar_palabra(str(w.get('word', '')), i == 0) for i, w in enumerate(palabras)]
    apariciones = {}
    for w in palabras:
        nucleo = dyn._normalizar(str(w.get('word', '')))
        if not nucleo:
            continue
        else:
            apariciones[nucleo] = apariciones.get(nucleo, 0) + 1
    def con_tema(i, puntos):
        if puntos <= 0:
            return 0.0
        else:
            veces = apariciones.get(dyn._normalizar(str(palabras[i].get('word', ''))), 1)
            if veces >= 3:
                return puntos * 1.5
            else:
                if veces == 2:
                    return puntos * 1.25
                else:
                    return float(puntos)
    ajustados = [con_tema(i, c) for i, c in enumerate(crudos)]
    tope = max(ajustados) if ajustados else 0
    if tope <= 0:
        return {i: 0.0 for i in range(len(palabras))}
    else:
        return {i: c / tope for i, c in enumerate(ajustados)}
def _roles_por_bloque(palabras, scores, densidad_objetivo, variante=0, tamanos=None, peso_conector=None):
    """Convierte puntajes en roles: UNA oracion aporta a lo sumo UN grupo.\n\n    v1.0.62 (pedido literal: «que los bloques esten mas separados,\n    delimitando las oraciones» + «que seleccione mas grupos de\n    dinamicos», con eleccion explicita del usuario: un grupo por oracion,\n    en casi todas): la unidad de seleccion es la ORACION entera\n    (dyn.segmentar_oraciones — la pausa larga tambien corta: en un guion\n    hablado separa ideas igual que un punto). De cada oracion elegida se\n    destaca UN grupo alrededor de su mejor palabra; el resto de esa\n    oracion queda en subtitulo simple. Desde la v1.0.63 el grupo lo arma\n    dyn.grupo_alrededor (2 de contenido + verbo/mejor + 2 de contenido,\n    conectores del medio acoplados) y el centro es el mejor VERBO de la\n    oracion cuando existe.\n\n    La densidad se mide EN ORACIONES con algo destacable: 0.85 = casi\n    todas (solo el relleno puro queda fuera). \'variante\' mueve el CENTRO\n    de la ventana (la 2a/3a mejor palabra de la oracion): con la oracion\n    entera por fin hay de donde elegir — con tramos de 5 y ctx/cmp fijos\n    en 2 la alternativa era casi inerte y solo se veia la densidad.\n\n    v3.1.9: \'tamanos\' = (contexto, principal, complemento) en palabras de\n    contenido, el selector «Palabras por linea» de la ventana (None = 2/1/2).\n\n    Devuelve {indice: rol} con rol en main/context/complement/base.\n    """
    n = len(palabras)
    if n == 0:
        return {}
    else:
        n_ctx, n_main, n_cmp = dyn.normalizar_tamanos(tamanos)
        oraciones = dyn.segmentar_oraciones(palabras)
        def efectivo(i):
            texto = str(palabras[i].get('word', ''))
            if dyn.es_conector(texto):
                return 0.0
            else:
                if dyn.puntuar_palabra(texto, False) < dyn.PUNTOS_MINIMOS_PRINCIPAL:
                    return 0.0
                else:
                    return scores.get(i, 0.0)
        destacables = []
        for desde, hasta in oraciones:
            idx = [i for i in range(desde, hasta) if efectivo(i) > 0]
            idx.sort(key=efectivo, reverse=True)
            destacables.append(idx)
        candidatos = [k for k in range(len(oraciones)) if destacables[k]]
        candidatos.sort(key=lambda k: efectivo(destacables[k][0]), reverse=True)
        objetivo = max(0.0, min(1.0, densidad_objetivo))
        cupo = min(len(candidatos), int(objetivo * len(candidatos) + 0.9999))
        if candidatos and objetivo > 0 and (cupo == 0):
                    cupo = 1
        roles = {i: 'base' for i in range(n)}
        def _asignar_oracion(k):
            """Un grupo para la oracion k, o False si no dio para grupo."""
            desde, hasta = oraciones[k]
            cand = destacables[k]
            verbos = [i for i in cand if dyn.es_verbo(str(palabras[i].get('word', '')))]
            resto = [i for i in cand if i not in set(verbos)]
            utiles = []
            if verbos:
                piso = 0.5 * efectivo(verbos[0])
                utiles += [i for i in verbos if efectivo(i) >= piso]
            if resto:
                piso = 0.5 * efectivo(resto[0])
                utiles += [i for i in resto if efectivo(i) >= piso]
            if not utiles:
                return False
            else:
                evaluados = []
                for orden, i in enumerate(utiles):
                    grupo = dyn.grupo_alrededor(palabras, i, desde, hasta, n_ctx, n_main, n_cmp, peso_conector=peso_conector)
                    lineas = len(set(grupo.values()))
                    if lineas < 2:
                        continue
                    else:
                        mains = [j for j, r in grupo.items() if r == 'main']
                        if roles.get(min(mains) - 1) == 'main' or roles.get(max(mains) + 1) == 'main':
                            continue
                        else:
                            peso = dyn.normalizar_peso_conector(peso_conector)
                            contenido = sum((1.0 if not dyn.es_conector(str(palabras[j].get('word', ''))) else peso for j in grupo))
                            evaluados.append((-lineas, -contenido, orden, i, grupo))
                if not evaluados:
                    return False
                else:
                    evaluados.sort(key=lambda e: (e[0], e[1], e[2]))
                    alt = _ALTERNATIVA.get(variante, 0)
                    roles.update(evaluados[min(alt, len(evaluados) - 1)][4])
                    return True
        con_grupo = 0
        for k in candidatos:
            if con_grupo >= cupo:
                break
            if _asignar_oracion(k):
                con_grupo += 1
        return roles
def sugerir(palabras, idioma='es', modo='auto', densidad_objetivo=DENSIDAD_POR_DEFECTO, usar_cache=True, variante=0, tamanos=None, peso_conector=None):
    """Devuelve {indice_palabra: rol} con rol main/context/complement/base.\n\n    `palabras` es la lista de dicts de Whisper (word, start, end).\n    `modo`: \'auto\' | \'keybert\' | \'heuristico\' (la rama LLM por API key se\n    retiro en la v1.0.62 — costaba dinero al usuario).\n    `variante`: 0..VARIANTES-1. Cada una da una version distinta del mismo\n    guion (otro centro de ventana por oracion, mas o menos oraciones con\n    grupo); el boton de sugerir las rota para que picarlo de nuevo no\n    repita lo mismo.\n    `tamanos`: (contexto, principal, complemento) en palabras de contenido\n    (v3.1.9, el selector de la ventana); None = 2/1/2.\n    `peso_conector`: 0 / 0.5 / 1 (v3.3.1, la opcion «Conectores»); None =\n    el defecto del producto (0.5 desde la v3.3.3; 0 = lo de la v3.1.9).\n    """
    if not palabras:
        return {}
    else:
        variante = int(variante) % VARIANTES
        densidad_objetivo = max(0.1, min(1.0, densidad_objetivo + _AJUSTE_DENSIDAD.get(variante, 0.0)))
        clave = _hash_transcript(palabras, densidad_objetivo, variante, tamanos, peso_conector)
        if usar_cache:
            guardado = _cache_get(clave)
            if guardado:
                return {int(k): v for k, v in guardado.items()}
        scores = None
        if modo == 'heuristico':
            scores = _scores_heuristico(palabras, idioma)
        else:
            scores = _scores_keybert(palabras, idioma)
        if scores is None:
            scores = _scores_heuristico(palabras, idioma)
        roles = _roles_por_bloque(palabras, scores, densidad_objetivo, variante, tamanos, peso_conector)
        if usar_cache:
            _cache_put(clave, {str(k): v for k, v in roles.items()})
        return roles
