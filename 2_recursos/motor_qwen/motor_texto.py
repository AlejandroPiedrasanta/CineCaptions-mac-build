# CineCaptions · By Cinema Productions
# 2_recursos/motor_qwen/motor_texto.py — IA de texto Qwen3 Instruct: correcciones, pesos y emojis por frase (modo servidor).
"""IA de texto de CineCaptions (Qwen3 Instruct, local, sin coste por uso).

Corre en el MISMO Python 3.14 del motor de voz (motor_qwen.py). Recibe la
transcripcion palabra por palabra y devuelve:

  * correcciones: errores claros de la transcripcion (palabra mal oida,
    tilde, nombre propio), SIEMPRE una palabra por una palabra en la misma
    posicion, para no mover ningun tiempo;
  * pesos: cuanto importa cada palabra en su frase (0..1). Con eso
    sugerencias_ia arma los grupos contexto / principal / complemento con
    sus reglas de siempre: el modelo aporta el criterio, las reglas el
    diseño, y una respuesta rara no puede romper el layout.

Protocolo por stdout (igual que motor_qwen.py): PROGRESO|f, ESTADO|t,
LISTO|ruta, ERROR|t.

    python motor_texto.py --entrada in.json --salida out.json [--modelo auto|4B|1.7B]
    python motor_texto.py --descargar [--modelo ...]
in.json: {"idioma": "es", "palabras": ["Hoy", "te", ...]}
"""
import argparse
import difflib
import json
import os
import re
import sys
import time
import unicodedata

os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')

REPOS = {'4B': 'Qwen/Qwen3-4B-Instruct-2507', '1.7B': 'Qwen/Qwen3-1.7B'}
# v5.3 (medido con 96 palabras en una RTX 5070 Ti): tramos de 90 palabras -> 23,4 s; de 40 -> 10,1 s; de 28 -> 8,2 s; de 20 -> 6,8 s,
# con casi las mismas correcciones, pesos y emojis. La GPU decodifica varios tramos a la vez casi al precio de uno: el tiempo
# lo manda lo que tarda el tramo MAS LARGO, asi que tramos cortos en lote = mucho mas rapido.
TRAMO = 28          # palabras por consulta (cortando en final de frase)
LOTE = 12           # consultas a la vez en la GPU (en lote cuesta casi lo mismo que una)
IDIOMAS = {'es': 'español', 'en': 'inglés', 'pt': 'portugués', 'fr': 'francés', 'de': 'alemán',
           'it': 'italiano', 'ja': 'japonés', 'ko': 'coreano', 'ru': 'ruso', 'zh': 'chino'}

# v5.2: la paleta de emojis de los videos virales. La IA elige SOLO de aqui
# (todos tienen imagen en el catalogo del programa: lo que llega a Resolve).
PALETA = ('🔥 💰 💸 🤑 📈 📉 🚀 ✅ ❌ ⚠️ 💡 🎯 ⏰ ⏳ 🧠 💪 👀 😱 🤯 😂 😍 🥰 😎 🤔 😅 😭 😡 🙌 👏 👍 '
          '👎 🙏 💯 ⭐ ✨ 🏆 🥇 🎉 🎁 ❤️ 💔 🔑 🔒 📱 💻 🎬 🎥 📸 🎤 🎧 🎵 ⚡ 💥 🌍 ✈️ 🏠 🚗 ⚽ '
          '🍔 ☕ 🍕 🛒 📦 💳 🏦 📊 📝 📚 🎓 💊 🏋️ 😴 🍀 🌱 ☀️ 🌙 ❄️ 🔋 📅 🆕 🆓 💎 👑 🤝 💬 '
          '📣 🔔 👶 🐶 🤫 🤩 😬 🙄 👋 🧩 🛠️ 🔍 📍 💼 🏃 🔄 🗣️ 😤 🥳 🤷 💀 🫡 🧨 🎮 🖥️ 💤 🍿')

SISTEMA = (
    'Eres el mejor editor de subtítulos virales (TikTok, Reels, Shorts, estilo Hormozi). Recibes la '
    'transcripción automática de un vídeo dividida en frases (F1, F2…); cada palabra lleva delante su '
    'número entre corchetes. Devuelve SOLO un JSON:\n'
    '1) "correcciones": errores claros del reconocimiento de voz: palabra mal oída que no encaja '
    '(«bentas» -> «ventas»), tildes que faltan («como» en una pregunta directa o indirecta -> «cómo», '
    '«esta» verbo -> «está», «despues» -> «después», «mas» de cantidad -> «más»), FALTAS DE ORTOGRAFÍA '
    '(letras cambiadas, de más o de menos: «ablando» -> «hablando», «kiero» -> «quiero», '
    '«enpezamos» -> «empezamos», «proyeto» -> «proyecto», «jente» -> «gente», «tambien» -> «también»; '
    'revisa CADA palabra), nombres propios o marcas mal escritos. UNA palabra por UNA palabra: nunca juntes, partas, añadas ni quites '
    'palabras. No cambies el estilo de quien habla: solo errores. Corrige en el MISMO idioma del texto: NUNCA traduzcas una palabra a otro '
    'idioma (en un vídeo en inglés, «Number» y «effects» están bien: no son «Número» ni «efectos»).\n'
    '2) "frases": para CADA frase, sin saltarte ninguna:\n'
    '   "principal": la palabra que hace que alguien deje de deslizar: la cifra, el resultado, la '
    'emoción, el sustantivo que da el giro o el verbo de acción fuerte («duplicamos», «estalló», '
    '«gratis», «nunca», «secreto», «error»). Nunca un verbo genérico («contar», «saber», «hacer», '
    '«ir», «ser», «tener», «decir»), ni artículos, preposiciones, conjunciones, pronombres o muletillas.\n'
    '   "secundaria": otra palabra con carga de la misma frase, o null.\n'
    '   "emoji": un emoji de esta paleta que represente el SIGNIFICADO de la frase (si es figurado, '
    'el sentido figurado: «está que arde» -> 🔥), o null. Ponlo solo en las frases con una idea '
    'visual o emocional clara (más o menos la mitad), sin repetir el mismo en frases seguidas. '
    'Paleta: __PALETA__\n'
    'Ejemplo. Entrada:\n'
    'F1: [0]Así [1]ganamos [2]10.000 [3]euros [4]en [5]un [6]mes.\n'
    'F2: [7]Y [8]nadie [9]te [10]cuenta [11]este [12]error.\n'
    'F3: [13]Te [14]lo [15]boy [16]a [17]explicar [18]paso [19]a [20]paso.\n'
    'Salida:\n'
    '{"correcciones": [[15, "boy", "voy"]], "frases": [{"f": 1, "principal": [2, "10.000"], "secundaria": [1, "ganamos"], '
    '"emoji": "💰"}, {"f": 2, "principal": [12, "error"], "secundaria": [8, "nadie"], "emoji": "❌"}, '
    '{"f": 3, "principal": [18, "paso"], "secundaria": null, "emoji": null}]}\n'
    'Copia el número Y la palabra exactamente como aparecen.'
).replace('__PALETA__', PALETA)


def frases_de(palabras, desde, hasta, largo_max=16):
    """[(ini, fin)] de las frases del tramo: corta en . ! ? … y, si una frase
    se alarga, en la coma; nunca mas de largo_max palabras."""
    salida, ini = [], desde
    for j in range(desde, hasta):
        w = palabras[j]
        n = j - ini + 1
        fin_fuerte = bool(re.search(r'[.!?…]["»”)]*$', w))
        fin_coma = w.endswith(',') and n >= 9
        if fin_fuerte or fin_coma or n >= largo_max or j == hasta - 1:
            salida.append((ini, j + 1))
            ini = j + 1
    return salida


# v5.4: modo «ortografia»: una pasada que SOLO corrige faltas de ortografia y tildes (sin pesos ni emojis).
SISTEMA_ORTO = (
    'Eres un corrector ortográfico. Corriges en el MISMO idioma del texto y NUNCA traduces palabras a otro idioma. Recibes una transcripción dividida en frases (F1, F2…); cada palabra lleva delante su '
    'número entre corchetes. Devuelve SOLO un JSON {"correcciones": [[n, "palabra mal escrita", "palabra corregida"], ...]}. '
    'Corrige únicamente FALTAS DE ORTOGRAFÍA y tildes: letras cambiadas, de más o de menos (b/v, h, c/s/z, g/j, k/qu, m/n, '
    'rr/r), tildes que faltan o sobran («tambien» -> «también»). UNA palabra por UNA palabra: nunca juntes, partas, añadas ni '
    'quites palabras; no cambies el estilo ni el sentido; no toques nombres propios, números ni palabras de otro idioma. '
    'Revisa CADA palabra. Si no hay faltas devuelve {"correcciones": []}.' + chr(10) +
    'Ejemplo. Entrada:' + chr(10) + 'F1: [0]Enpezamos [1]a [2]ablar [3]del [4]proyeto [5]tenpranito.' + chr(10) +
    'Salida:' + chr(10) + '{"correcciones": [[0, "Enpezamos", "Empezamos"], [2, "ablar", "hablar"], [4, "proyeto", "proyecto"], '
    '[5, "tenpranito.", "tempranito."]]}'
)


def decir(tipo, texto=''):
    sys.stdout.write(f'{tipo}|{texto}\n')
    sys.stdout.flush()


def elegir(pedido):
    import torch
    if not torch.cuda.is_available():
        return '1.7B' if pedido not in REPOS else pedido, 'cpu', torch.float32
    vram = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    if pedido in REPOS:
        return pedido, 'cuda:0', dtype
    return ('4B' if vram >= 9.5 else '1.7B'), 'cuda:0', dtype


def tramos(palabras):
    """Trozos de ~TRAMO palabras que terminan en final de frase si se puede."""
    salida, desde = [], 0
    n = len(palabras)
    while desde < n:
        hasta = min(n, desde + TRAMO)
        if hasta < n:
            for j in range(hasta, max(desde + TRAMO // 2, desde + 1), -1):
                if re.search(r'[.!?…]["»”)]*$', palabras[j - 1]):
                    hasta = j
                    break
        salida.append((desde, hasta))
        desde = hasta
    return salida


def _sin_tildes(t):
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c)[0] in 'LN')


LETRAS_PROPIAS = {'en': set(), 'es': set('áéíóúüñÁÉÍÓÚÜÑ'), 'pt': set('áâãàéêíóôõúçÁÂÃÀÉÊÍÓÔÕÚÇ'), 'fr': set('àâæçéèêëîïôœùûüÿÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ'),
                  'de': set('äöüßÄÖÜ'), 'it': set('àèéìíîòóùúÀÈÉÌÍÎÒÓÙÚ')}


def traduce(original, nueva, idioma):
    """v5.4.51: ¿la «corrección» mete letras que el idioma del texto no usa? (la IA, con instrucciones en español, «corregía» «Number» -> «Número»
    en un vídeo en inglés). Entonces no es una corrección: es una traducción, y se descarta."""
    propias = LETRAS_PROPIAS.get(str(idioma or '')[:2])
    if propias is None:
        return False
    nuevas = {c for c in str(nueva) if ord(c) > 127 and c.isalpha()} - {c for c in str(original)}
    return any(c not in propias for c in nuevas)


def correccion_aceptable(original, nueva, umbral=0.55):
    """Que la 'correccion' se parezca a lo que se oyo (no una reescritura)."""
    a, b = _sin_tildes(original), _sin_tildes(nueva)
    if not b or a == b and original == nueva:
        return False
    if a == b:
        return True  # solo tildes o mayusculas
    return difflib.SequenceMatcher(None, a, b).ratio() >= umbral


def con_puntuacion(original, nueva):
    """Si el modelo se comio la puntuacion pegada, se la devolvemos."""
    pre = re.match(r'^[¿¡"«“(\[]*', original).group(0)
    post = re.search(r'[.,;:!?…"»”)\]]*$', original).group(0)
    nucleo = nueva.strip()
    if pre and not nucleo.startswith(pre):
        nucleo = pre + nucleo.lstrip('¿¡"«“([')
    if post and not nucleo.endswith(post):
        nucleo = nucleo.rstrip('.,;:!?…"»”)]') + post
    return nucleo


def ubicar(palabras, desde, hasta, g, texto, corregidas=None):
    """La posicion real de la palabra que el modelo nombro: los modelos se
    equivocan contando, asi que se busca la palabra cerca del numero. Vale
    tambien la palabra YA corregida (el modelo nombra «ventas» donde la
    transcripcion dice «bentas»)."""
    if texto is None:
        return g if desde <= g < hasta else None
    objetivo = _sin_tildes(texto)
    if not objetivo:
        return None
    corregidas = corregidas or {}
    for d in (0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6):
        j = g + d
        if desde <= j < hasta and (_sin_tildes(palabras[j]) == objetivo
                                   or (j in corregidas and _sin_tildes(corregidas[j]) == objetivo)):
            return j
    return None


def leer_json(texto):
    m = re.search(r'\{.*\}', texto, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        try:
            return json.loads(re.sub(r',\s*([\]}])', r'\1', m.group(0)))
        except Exception:
            return {}


def _segmento(texto, clave):
    """El [...] que sigue a "clave": en el texto, con los corchetes
    equilibrados (ignorando los que van dentro de comillas), o None."""
    m = re.search(r'"%s"\s*:\s*\[' % re.escape(clave), texto)
    if not m:
        return None
    i = m.end() - 1
    nivel, en_cadena, escape = 0, False, False
    for j in range(i, len(texto)):
        c = texto[j]
        if en_cadena:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == '"':
                en_cadena = False
            continue
        if c == '"':
            en_cadena = True
        elif c == '[':
            nivel += 1
        elif c == ']':
            nivel -= 1
            if nivel == 0:
                return texto[i:j + 1]
    return None


def leer_tolerante(texto):
    """Como leer_json, pero si el JSON entero no vale (el modelo a veces
    escribe «"a" -> "b"»), lee cada seccion por su lado."""
    r = leer_json(texto)
    if r:
        return r
    r = {}
    seg = _segmento(texto, 'frases')
    if seg:
        for intento in (seg, re.sub(r',\s*([\]}])', r'\1', seg)):
            try:
                r['frases'] = json.loads(intento)
                break
            except Exception:
                continue
    seg = _segmento(texto, 'correcciones') or ''
    pares = [[int(n), a, b] for n, a, b in re.findall(r'\[\s*(\d+)\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]', seg)]
    pares += [[None, a, b] for a, b in re.findall(r'"([^"]+)"\s*-+>\s*"([^"]+)"', seg)]
    r['correcciones'] = pares
    return r


def cargar(pedido):
    """(tokenizador, modelo, repo, dispositivo) — lo caro, una vez."""
    import torch  # noqa: F401
    from transformers import AutoModelForCausalLM, AutoTokenizer
    modelo_clave, dispositivo, dtype = elegir(pedido)
    repo = REPOS[modelo_clave]
    decir('ESTADO', f'Cargando la IA de texto ({repo.split("/")[1]})')
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(repo)
    tok.padding_side = 'left'
    modelo = AutoModelForCausalLM.from_pretrained(repo, dtype=dtype, device_map=dispositivo)
    modelo.eval()
    decir('ESTADO', f'IA de texto lista en {time.time() - t0:.1f} s')
    return tok, modelo, repo, dispositivo


def analizar(entrada, salida, pedido):
    tok, modelo, repo, dispositivo = cargar(pedido)
    analizar_con(tok, modelo, repo, dispositivo, entrada, salida)


def calentar(tok, modelo):
    """Una generacion corta: la primera de CUDA inicializa nucleos y tarda varios segundos; asi la del usuario no la paga."""
    try:
        import torch
        t0 = time.time()
        conversacion = [{'role': 'system', 'content': 'Responde con una sola palabra.'},
                        {'role': 'user', 'content': 'F1: [0]Hola [1]mundo.'}]
        try:
            texto = tok.apply_chat_template(conversacion, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            texto = tok.apply_chat_template(conversacion, tokenize=False, add_generation_prompt=True)
        entradas = tok([texto, texto], return_tensors='pt', padding=True).to(modelo.device)
        with torch.inference_mode():
            modelo.generate(**entradas, max_new_tokens=16, do_sample=False, pad_token_id=tok.pad_token_id or tok.eos_token_id)
        decir('ESTADO', f'IA de texto calentada en {time.time() - t0:.1f} s')
    except Exception as e:
        decir('ESTADO', f'Calentamiento omitido ({type(e).__name__})')


def servidor(pedido, inactivo):
    """v5.2: el modelo queda cargado y atiende pedidos por stdin (una linea
    JSON {"entrada", "salida"} por pedido) hasta 'inactivo' segundos sin
    trabajo: «Marcar con IA» la segunda vez tarda segundos, no lo que tarda
    cargar 8 GB. Al terminar escribe FIN (y libera la memoria de la GPU)."""
    import queue
    import threading
    tok, modelo, repo, dispositivo = cargar(pedido)
    calentar(tok, modelo)
    cola = queue.Queue()

    def leer():
        for linea in sys.stdin:
            cola.put(linea)
        cola.put(None)
    threading.Thread(target=leer, daemon=True).start()
    decir('LISTA', repo)
    while True:
        try:
            linea = cola.get(timeout=inactivo)
        except queue.Empty:
            break
        if linea is None or linea.strip() == 'salir':
            break
        linea = linea.strip()
        if not linea:
            continue
        try:
            orden = json.loads(linea)
            analizar_con(tok, modelo, repo, dispositivo, orden['entrada'], orden['salida'])
        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stderr)
            decir('ERROR', f'{type(e).__name__}: {e}'.replace('\n', ' ')[:500])
    decir('FIN', 'inactivo')


def analizar_con(tok, modelo, repo, dispositivo, entrada, salida):
    import torch
    t0 = time.time()
    datos = json.loads(open(entrada, encoding='utf-8').read())
    if datos.get('modo') == 'escenas':                       # v5.4.51: el director de escenas del Tema 5
        return analizar_escenas(tok, modelo, repo, dispositivo, datos, salida)
    if datos.get('modo') == 'motions':                       # v5.5.2: el director de motions del kit de la skill (cualquier tema)
        return analizar_motions(tok, modelo, repo, dispositivo, datos, salida)
    if datos.get('modo') == 'perfil':                        # v5.5.2: de qué va el video (categoría, tono, iconos)
        return analizar_perfil(tok, modelo, repo, dispositivo, datos, salida)
    if datos.get('modo') == 'revisar':                       # v5.5.8: el vigilante: ¿lo que muestra cada gráfico encaja con lo que se dice?
        return revisar_graficos(tok, modelo, repo, dispositivo, datos, salida)
    palabras = [str(p) for p in datos.get('palabras') or []]
    idioma = IDIOMAS.get(str(datos.get('idioma') or 'es')[:2], 'el idioma del texto')
    codigo = str(datos.get('idioma') or '')[:2]
    modo = str(datos.get('modo') or '')
    trozos = tramos(palabras)
    correcciones, pesos, emojis = {}, {}, {}
    hechos = 0
    decir('PROGRESO', '0.0')
    for k in range(0, len(trozos), LOTE):
        lote = trozos[k:k + LOTE]
        mensajes = []
        for desde, hasta in lote:
            lineas = []
            for f, (a, b) in enumerate(frases_de(palabras, desde, hasta), 1):
                lineas.append(f'F{f}: ' + ' '.join(f'[{i - desde}]{palabras[i]}' for i in range(a, b)))
            usuario = f'Idioma: {idioma}.\n' + '\n'.join(lineas)
            conversacion = [{'role': 'system', 'content': SISTEMA_ORTO if modo == 'ortografia' else SISTEMA}, {'role': 'user', 'content': usuario}]
            try:
                texto = tok.apply_chat_template(conversacion, tokenize=False, add_generation_prompt=True,
                                                enable_thinking=False)
            except TypeError:
                texto = tok.apply_chat_template(conversacion, tokenize=False, add_generation_prompt=True)
            mensajes.append(texto)
        entradas = tok(mensajes, return_tensors='pt', padding=True).to(modelo.device)
        with torch.inference_mode():
            out = modelo.generate(**entradas, max_new_tokens=(400 if modo == 'ortografia' else 900), do_sample=False,
                                  pad_token_id=tok.pad_token_id or tok.eos_token_id)
        for (desde, hasta), fila in zip(lote, out):
            respuesta = tok.decode(fila[entradas['input_ids'].shape[1]:], skip_special_tokens=True)
            if os.environ.get('CINECAPTIONS_DEPURAR_IA'):
                sys.stderr.write('RESPUESTA:\n' + respuesta + '\n')
            r = leer_tolerante(respuesta)
            for par in r.get('correcciones') or []:
                try:
                    if len(par) >= 3:
                        i, vieja, nueva = (int(par[0]) if par[0] is not None else None), str(par[1]), str(par[2])
                    else:
                        i, vieja, nueva = int(par[0]), None, str(par[1])
                except Exception:
                    continue
                if i is None:
                    # sin numero: la palabra tal cual, la primera vez que aparece en el tramo
                    objetivo = _sin_tildes(vieja)
                    g = next((j for j in range(desde, hasta) if _sin_tildes(palabras[j]) == objetivo), None)
                else:
                    g = ubicar(palabras, desde, hasta, desde + i, vieja)
                if g is not None and ' ' not in nueva.strip() and not traduce(palabras[g], nueva, codigo) \
                        and correccion_aceptable(palabras[g], nueva, 0.74 if modo == 'ortografia' else 0.55):
                    correcciones[g] = con_puntuacion(palabras[g], nueva)
            for frase in r.get('frases') or []:
                if not isinstance(frase, dict):
                    continue
                principal = None
                for clave, peso in (('principal', 1.0), ('secundaria', 0.6)):
                    par = frase.get(clave)
                    try:
                        i, texto = int(par[0]), str(par[1])
                    except Exception:
                        continue
                    g = ubicar(palabras, desde, hasta, desde + i, texto, correcciones)
                    if g is not None:
                        pesos[g] = max(pesos.get(g, 0.0), peso)
                        if clave == 'principal':
                            principal = g
                glifo = str(frase.get('emoji') or '').strip()
                if principal is not None and glifo and glifo.lower() != 'null' and len(glifo) <= 8:
                    emojis[principal] = glifo
            hechos += 1
        decir('PROGRESO', f'{hechos / max(1, len(trozos)):.3f}')
    resultado = {'modelo': repo, 'dispositivo': dispositivo, 'segundos': round(time.time() - t0, 1),
                 'correcciones': {str(k): v for k, v in correcciones.items()},
                 'pesos': {str(k): v for k, v in pesos.items()},
                 'emojis': {str(k): v for k, v in emojis.items()}}
    with open(salida, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False)
    decir('LISTO', salida)


# ---------------------------------------------------------------------------------------------------------------------------------------------
# v5.4.51: el DIRECTOR DE ESCENAS del Tema 5 (modo 'escenas'). Recibe las frases de los captions (B1, B2…) y decide qué ilustrar, como el editor
# del video de referencia de la skill «Edit VIRAL Reels with AI»: cada escena es UN objeto (o unos pocos) que dibuja lo que se dice y entra
# justo cuando se nombra (las «anclas» son palabras literales de la frase). Sirve para cualquier tema: cocina, bodas, negocios, deporte…
# in.json: {"modo": "escenas", "idioma": "es", "bloques": ["texto del bloque 1", ...]}  ->  out.json: {"escenas": [{"b", "tipo", "datos", "anclas"}]}
# ---------------------------------------------------------------------------------------------------------------------------------------------
TIPOS_ESCENA = ('lista', 'fichas', 'comparacion', 'pregunta', 'cifra', 'precio', 'grafica', 'reloj', 'avatares', 'calendario', 'estado', 'muestras',
                'app', 'ojo', 'icono')
SISTEMA_ESCENAS = (
    'Eres el mejor editor de motion graphics para reels virales. Recibes las frases de un vídeo, numeradas (B1, B2…). Elige las POCAS frases '
    'que merecen una escena animada que ILUSTRE exactamente lo que se dice, y sus datos. Es mejor no poner escena que poner una que no encaja.\n'
    'Reglas estrictas: (1) usa SOLO cosas que se dicen literalmente en la frase o en la siguiente; NUNCA inventes cifras, colores, preguntas, '
    'nombres ni opciones; (2) como mucho una escena cada 3 frases y nunca en dos frases seguidas; (3) textos cortos (1–3 palabras) copiados de '
    'lo que se dice; (4) si dudas, no pongas escena.\n'
    'Tipos (UNO por escena):\n'
    '  "lista": {"items": [...]}  — se enumeran 2–5 cosas («harina, azúcar y huevos»)\n'
    '  "comparacion": {"a": "...", "b": "..."}  — dos opciones opuestas que se DICEN («de principiante a profesional», «antes y después»)\n'
    '  "fichas": {"items": [...]}  — se nombran 2 o más nombres propios (marcas, apps, lugares, personas)\n'
    '  "cifra": {"valor": "...", "etiqueta": "..."}  — se dice un número (el valor lleva el número tal cual: «25%», «3», «100»)\n'
    '  "precio": {"valor": "...", "signo": "$"} — se dice una cantidad de dinero   "reloj": {"valor": "20", "unidad": "minutos"} — un tiempo\n'
    '  "grafica": {"valor": "...", "signo": "%"} — algo que crece o aumenta     "avatares": {"etiqueta": "..."} — clientes, gente, seguidores\n'
    '  "calendario": {"dia": "..."} — un día o una fecha   "estado": {"bien": true|false, "etiqueta": "..."} — un error / algo correcto\n'
    '  "muestras": {"colores": [...]} — SOLO si se nombran colores (rojo, negro, azul…)\n'
    '  "pregunta": {"pregunta": "...", "opciones": ["...", "..."]} — SOLO si quien habla le hace una pregunta al público\n'
    '  "app": {} — vídeos, contenido, editar, redes sociales   "ojo": {} — lo visual, la atención\n'
    '"anclas": la PALABRA EXACTA de la frase en la que aparece cada objeto (copiada tal cual).\n'
    'Devuelve SOLO un JSON: {"escenas": [...]}\n'
    'Ejemplo 1. Entrada:\n'
    'B1: Hoy te enseño a preparar el mejor pastel\nB2: solo necesitas harina azúcar y huevos\nB3: y lo tienes listo en 20 minutos\n'
    'B4: el error que todos cometen es el horno\nB5: así que guárdalo para después\n'
    'Salida:\n{"escenas": [{"b": 2, "tipo": "lista", "datos": {"items": ["Harina", "Azúcar", "Huevos"]}, "anclas": ["harina", "azúcar", "huevos"]}, '
    '{"b": 4, "tipo": "estado", "datos": {"bien": false, "etiqueta": "EL HORNO"}, "anclas": ["error"]}]}\n'
    'Ejemplo 2. Entrada:\n'
    'B1: We went from 0 to 10,000 followers\nB2: in just three months\nB3: and the secret was simple\nB4: we posted on TikTok and Instagram every day\n'
    'Salida:\n{"escenas": [{"b": 1, "tipo": "grafica", "datos": {"valor": "10,000", "signo": ""}, "anclas": ["10,000"]}, '
    '{"b": 4, "tipo": "fichas", "datos": {"items": ["TikTok", "Instagram"]}, "anclas": ["TikTok", "Instagram"]}]}'
)
BLOQUES_POR_CONSULTA = 18


def analizar_escenas(tok, modelo, repo, dispositivo, datos, salida):
    import torch
    t0 = time.time()
    bloques = [str(b) for b in datos.get('bloques') or []]
    idioma = IDIOMAS.get(str(datos.get('idioma') or 'es')[:2], 'el idioma del texto')
    tandas = [(k, bloques[k:k + BLOQUES_POR_CONSULTA]) for k in range(0, len(bloques), BLOQUES_POR_CONSULTA)]
    escenas = []
    decir('PROGRESO', '0.0')
    for j in range(0, len(tandas), LOTE):
        lote = tandas[j:j + LOTE]
        mensajes = []
        for desde, trozo in lote:
            usuario = f'Idioma: {idioma}.\n' + '\n'.join(f'B{n + 1}: {t}' for n, t in enumerate(trozo))
            conversacion = [{'role': 'system', 'content': SISTEMA_ESCENAS}, {'role': 'user', 'content': usuario}]
            try:
                texto = tok.apply_chat_template(conversacion, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            except TypeError:
                texto = tok.apply_chat_template(conversacion, tokenize=False, add_generation_prompt=True)
            mensajes.append(texto)
        entradas = tok(mensajes, return_tensors='pt', padding=True).to(modelo.device)
        with torch.inference_mode():
            out = modelo.generate(**entradas, max_new_tokens=900, do_sample=False, pad_token_id=tok.pad_token_id or tok.eos_token_id)
        for (desde, trozo), fila in zip(lote, out):
            respuesta = tok.decode(fila[entradas['input_ids'].shape[1]:], skip_special_tokens=True)
            if os.environ.get('CINECAPTIONS_DEPURAR_IA'):
                sys.stderr.write('RESPUESTA ESCENAS:\n' + respuesta + '\n')
            for e in (leer_json(respuesta).get('escenas') or []):
                try:
                    b = int(e.get('b')) - 1
                    tipo = str(e.get('tipo') or '')
                except Exception:
                    continue
                if 0 <= b < len(trozo) and tipo in TIPOS_ESCENA:
                    escenas.append({'b': desde + b, 'tipo': tipo, 'datos': e.get('datos') if isinstance(e.get('datos'), dict) else {},
                                    'anclas': [str(x) for x in (e.get('anclas') or []) if isinstance(x, (str, int, float))][:6]})
        decir('PROGRESO', f'{min(1.0, (j + len(lote)) / max(1, len(tandas))):.3f}')
    with open(salida, 'w', encoding='utf-8') as f:
        json.dump({'modelo': repo, 'segundos': round(time.time() - t0, 1), 'escenas': escenas}, f, ensure_ascii=False)
    decir('LISTO', salida)


# ---------------------------------------------------------------------------------------------------------------------------------------------
# v5.5.2: el DIRECTOR DE MOTIONS (modo 'motions'), para el kit de la skill (1_codigo/edicion_pro_kit7.py + remotion/src/Kit7.tsx). Recibe las frases
# (B1, B2…), el MENÚ de motions (qué es cada uno, cuándo va y qué datos lleva: lo manda el programa, así crece sin tocar este archivo) y los iconos
# que existen, y elige los POCOS momentos que merecen un motion, con sus textos copiados de lo que se dice. El programa valida todo después.
# in.json: {"modo": "motions", "idioma": "es", "bloques": [...], "menu": {"lista": ["cuándo", "datos"], ...}, "iconos": ["light_bulb", ...]}
# out.json: {"motions": [{"b", "motion", "datos", "ancla"}]}
# ---------------------------------------------------------------------------------------------------------------------------------------------
def sistema_motions(menu, iconos, denso=False):
    lineas = '\n'.join(f'  "{k}": {v[0]}. Datos: {v[1]}' for k, v in menu.items())
    if denso:       # v5.5.8, «Motions completo»: un video de SOLO motions encima de todo: cada frase necesita su motion (nada de captions)
        cabeza = ('Eres el director de un vídeo explicativo hecho SOLO de motion graphics (como los de las cuentas de divulgación). Recibes las frases '
                  'de un vídeo, numeradas (B1, B2…). Para CADA frase elige el motion del menú que mejor ILUSTRA lo que se dice (escenas, iconos, '
                  'datos, fotos o vídeos del tema) y rellena sus datos. No repitas la frase como texto: muéstrala con imágenes.\n'
                  'Reglas estrictas: (1) los textos se COPIAN de lo que se dice en esa frase o en la siguiente; NUNCA inventes números, palabras ni '
                  'datos (las búsquedas "buscar" van en INGLÉS: lo que se ve); (2) un motion en cada frase; nunca el mismo tipo en dos frases '
                  'seguidas y cada tipo como mucho una de cada cuatro frases; ')
    else:
        cabeza = ('Eres el director de motion graphics de reels virales. Recibes las frases de un vídeo, numeradas (B1, B2…). Elige las POCAS frases que '
                  'merecen un motion del menú y rellena sus datos. Es mejor no poner nada que poner algo que no encaja.\n'
                  'Reglas estrictas: (1) los textos se COPIAN de lo que se dice en esa frase o en la siguiente; NUNCA inventes números, palabras ni datos; '
                  '(2) un motion de cada tipo como mucho y nunca en dos frases seguidas; ')
    return (
        cabeza + '(3) textos cortos (1–4 palabras); (4) "ancla": la palabra EXACTA '
        'de la frase en la que debe aparecer (la del número o la clave); (5) "icono" solo de esta lista: ' + ', '.join(iconos[:120]) + '.\n'
        'Menú:\n' + lineas + '\n'
        'Devuelve SOLO un JSON: {"motions": [{"b": 2, "motion": "lista", "datos": {...}, "ancla": "razones"}]}\n'
        'Ejemplo. Entrada:\nB1: Te voy a dar 3 razones para empezar hoy\nB2: la primera es la constancia\nB3: el éxito no es suerte\n'
        'B4: no necesitas motivación, necesitas disciplina\n'
        'Salida:\n{"motions": [{"b": 1, "motion": "lista", "datos": {"n": 3}, "ancla": "razones"}, '
        '{"b": 3, "motion": "concepto", "datos": {"palabra": "éxito", "tendencia": "sube", "icono": "gem_stone"}, "ancla": "éxito"}, '
        '{"b": 4, "motion": "mixto", "datos": {"linea1": "no necesitas motivación,", "linea2": "necesitas disciplina", "clave": "disciplina"}, "ancla": "disciplina"}]}'
        + (('\nEjemplo 2 (v5.5.3, escenas a pantalla completa: ilustran lo que se cuenta). Entrada:\nB1: soy editor y trabajo todo el día\n'
            'B2: al principio mi jefe me gritaba\nB3: el 17 de octubre lanzo mi curso\nB4: me encanta esto\nB5: todo está conectado: ideas, equipo y clientes\n'
            'B6: hay que seguir\nB7: muchos me mandan un mensaje preguntando el precio\n'
            'Salida:\n{"motions": [{"b": 1, "motion": "pictograma", "datos": {"pose": "trabajando", "texto": "editor"}, "ancla": "editor"}, '
            '{"b": 3, "motion": "fecha", "datos": {"dia": 17, "mes": "octubre", "nota": "lanzo mi curso"}, "ancla": "17"}, '
            '{"b": 5, "motion": "tablero", "datos": {"titulo": "conectado", "items": ["ideas", "equipo", "clientes"]}, "ancla": "conectado"}, '
            '{"b": 7, "motion": "chat", "datos": {"mensaje": "preguntando el precio"}, "ancla": "mensaje"}]}')
           if 'pictograma' in menu else '')
    )


def analizar_motions(tok, modelo, repo, dispositivo, datos, salida):
    import torch
    t0 = time.time()
    bloques = [str(b) for b in datos.get('bloques') or []]
    idioma = IDIOMAS.get(str(datos.get('idioma') or 'es')[:2], 'el idioma del texto')
    menu = {str(k): list(v) for k, v in (datos.get('menu') or {}).items() if isinstance(v, (list, tuple)) and len(v) >= 2}
    denso = bool(datos.get('denso'))
    sistema = sistema_motions(menu, [str(x) for x in datos.get('iconos') or []], denso)
    tandas = [(k, bloques[k:k + BLOQUES_POR_CONSULTA]) for k in range(0, len(bloques), BLOQUES_POR_CONSULTA)]
    motions = []
    decir('PROGRESO', '0.0')
    for j in range(0, len(tandas), LOTE):
        lote = tandas[j:j + LOTE]
        mensajes = []
        for desde, trozo in lote:
            contexto = str(datos.get('contexto') or '').strip()                # v5.5.2: de qué va el video (ia_texto.perfil)
            usuario = f'Idioma: {idioma}.\n' + (f'El vídeo trata de: {contexto}.\n' if contexto else '') + '\n'.join(f'B{n + 1}: {t}' for n, t in enumerate(trozo))
            conversacion = [{'role': 'system', 'content': sistema}, {'role': 'user', 'content': usuario}]
            try:
                texto = tok.apply_chat_template(conversacion, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            except TypeError:
                texto = tok.apply_chat_template(conversacion, tokenize=False, add_generation_prompt=True)
            mensajes.append(texto)
        entradas = tok(mensajes, return_tensors='pt', padding=True).to(modelo.device)
        with torch.inference_mode():
            out = modelo.generate(**entradas, max_new_tokens=1500 if denso else 700, do_sample=False, pad_token_id=tok.pad_token_id or tok.eos_token_id)
        for (desde, trozo), fila in zip(lote, out):
            respuesta = tok.decode(fila[entradas['input_ids'].shape[1]:], skip_special_tokens=True)
            if os.environ.get('CINECAPTIONS_DEPURAR_IA'):
                sys.stderr.write('RESPUESTA MOTIONS:\n' + respuesta + '\n')
            for e in (leer_json(respuesta).get('motions') or []):
                try:
                    b = int(e.get('b')) - 1
                    tipo = str(e.get('motion') or '')
                except Exception:
                    continue
                if 0 <= b < len(trozo) and tipo in menu:
                    motions.append({'b': desde + b, 'motion': tipo, 'datos': e.get('datos') if isinstance(e.get('datos'), dict) else {},
                                    'ancla': str(e.get('ancla') or '')[:40]})
        decir('PROGRESO', f'{min(1.0, (j + len(lote)) / max(1, len(tandas))):.3f}')
    with open(salida, 'w', encoding='utf-8') as f:
        json.dump({'modelo': repo, 'segundos': round(time.time() - t0, 1), 'motions': motions}, f, ensure_ascii=False)
    decir('LISTO', salida)


# ---------------------------------------------------------------------------------------------------------------------------------------------
# v5.5.2: el PERFIL del video (modo 'perfil'): de qué va (categoría), cómo suena (tono) y qué iconos le van. La edición elige con esto el tipo de
# video, los motions, los iconos y los colores. in.json: {"modo": "perfil", "idioma", "texto", "categorias": [...], "tonos": [...], "iconos": [...]}
# out.json: {"perfil": {"categoria", "subtema", "tono", "iconos": [...], "publico"}}
# ---------------------------------------------------------------------------------------------------------------------------------------------
def revisar_graficos(tok, modelo, repo, dispositivo, datos, salida):
    """v5.5.8, el VIGILANTE: in.json {"modo": "revisar", "idioma", "items": [{"i", "dicho", "muestra"}]} → out.json {"malos": [{"i", "motivo"}]}:
    los gráficos cuyo texto contradice o no tiene que ver con lo que se dice en ese momento (otra cifra, otra moneda, otro tema)."""
    import torch
    t0 = time.time()
    items = [it for it in datos.get('items') or [] if isinstance(it, dict)][:40]
    # un veredicto POR gráfico (encaja sí/no) con un ejemplo: con «dame la lista de los malos» el modelo ligero (1.7B) contestaba siempre
    # la lista vacía (medido: «Bitcoin a 50.000 dólares» sobre una receta de paella pasaba)
    sistema = ('Eres el control de calidad de un editor de vídeo. Para cada gráfico tienes lo que se DICE en ese momento y lo que el gráfico '
               'MUESTRA en pantalla. Un gráfico NO encaja si lo que muestra contradice lo que se dice o no tiene nada que ver: otra cifra, '
               'otra moneda, otro tema, un nombre o una palabra que no se dijo. Si lo ilustra, lo resume o lo destaca, SÍ encaja.\n'
               'Ejemplo: DICE «vamos a hablar del partido de fútbol de ayer» — MUESTRA «Receta de pasta» → no encaja (otro tema). '
               'DICE «cuesta unos veinte dólares» — MUESTRA «$20» → encaja.\n'
               'Contesta TODOS los gráficos, en orden. Devuelve SOLO un JSON: '
               '{"veredictos": [{"i": 0, "encaja": false, "motivo": "pocas palabras"}, {"i": 1, "encaja": true}]}')
    usuario = '\n'.join(f'{it.get("i")}. DICE: «{str(it.get("dicho") or "")[:300]}» — MUESTRA: «{str(it.get("muestra") or "")[:160]}»' for it in items)
    conversacion = [{'role': 'system', 'content': sistema}, {'role': 'user', 'content': usuario}]
    try:
        plantilla = tok.apply_chat_template(conversacion, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        plantilla = tok.apply_chat_template(conversacion, tokenize=False, add_generation_prompt=True)
    entradas = tok([plantilla], return_tensors='pt').to(modelo.device)
    with torch.inference_mode():
        out = modelo.generate(**entradas, max_new_tokens=500, do_sample=False, pad_token_id=tok.pad_token_id or tok.eos_token_id)
    respuesta = tok.decode(out[0][entradas['input_ids'].shape[1]:], skip_special_tokens=True)
    if os.environ.get('CINECAPTIONS_DEPURAR_IA'):
        sys.stderr.write('RESPUESTA REVISAR:\n' + respuesta + '\n')
    r = leer_json(respuesta)
    validos = {int(it.get('i')) for it in items if str(it.get('i')).isdigit()}
    malos = []
    lista = []
    if isinstance(r, dict):
        lista = [x for x in r.get('veredictos') or [] if isinstance(x, dict) and x.get('encaja') in (False, 'false', 'no', 0)]
        lista += [x for x in r.get('malos') or [] if isinstance(x, dict)]           # (el formato de antes, por si el modelo lo usa)
    for x in lista:
        try:
            i = int(x.get('i'))
        except (TypeError, ValueError, AttributeError):
            continue
        if i in validos and all(m['i'] != i for m in malos):
            malos.append({'i': i, 'motivo': str(x.get('motivo') or '')[:120]})
    with open(salida, 'w', encoding='utf-8') as f:
        json.dump({'modelo': repo, 'segundos': round(time.time() - t0, 1), 'malos': malos}, f, ensure_ascii=False)
    decir('LISTO', salida)


def analizar_perfil(tok, modelo, repo, dispositivo, datos, salida):
    import torch
    t0 = time.time()
    texto = str(datos.get('texto') or '')[:6000]
    cats = [str(x) for x in datos.get('categorias') or []]
    tonos = [str(x) for x in datos.get('tonos') or []]
    iconos = [str(x) for x in datos.get('iconos') or []]
    sistema = ('Eres editor de vídeo. Lee la transcripción de un vídeo corto y di de qué va, para elegir sus gráficos, iconos y colores.\n'
               f'"categoria": UNA de: {", ".join(cats)}.\n"tono": UNO de: {", ".join(tonos)}.\n'
               f'"iconos": 3 a 6 iconos que encajan con el tema, SOLO de esta lista: {", ".join(iconos[:120])}.\n'
               '"subtema": 1–4 palabras (p. ej. «recetas fáciles», «boda en la playa»). "publico": a quién habla, 1–4 palabras.\n'
               '"fotos": 2 a 4 búsquedas EN INGLÉS (2–4 palabras cada una) de fotos de banco que ilustren el tema con cosas concretas que se ven '
               '(p. ej. "street food lagos", "naira banknotes", "wedding beach sunset"); nada de personas famosas ni marcas.\n'
               'Devuelve SOLO un JSON: {"categoria": "...", "subtema": "...", "tono": "...", "iconos": ["..."], "publico": "...", "fotos": ["..."]}')
    conversacion = [{'role': 'system', 'content': sistema}, {'role': 'user', 'content': texto}]
    try:
        plantilla = tok.apply_chat_template(conversacion, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        plantilla = tok.apply_chat_template(conversacion, tokenize=False, add_generation_prompt=True)
    entradas = tok([plantilla], return_tensors='pt').to(modelo.device)
    with torch.inference_mode():
        out = modelo.generate(**entradas, max_new_tokens=320, do_sample=False, pad_token_id=tok.pad_token_id or tok.eos_token_id)
    respuesta = tok.decode(out[0][entradas['input_ids'].shape[1]:], skip_special_tokens=True)
    if os.environ.get('CINECAPTIONS_DEPURAR_IA'):
        sys.stderr.write('RESPUESTA PERFIL:\n' + respuesta + '\n')
    r = leer_json(respuesta)
    perfil = {'categoria': str(r.get('categoria') or ''), 'subtema': str(r.get('subtema') or '')[:40], 'tono': str(r.get('tono') or ''),
              'iconos': [str(x) for x in (r.get('iconos') or []) if str(x) in iconos][:6], 'publico': str(r.get('publico') or '')[:40],
              # v5.5.8: qué fotos de internet ilustran el tema (en inglés: los bancos de fotos buscan en inglés); solo letras y espacios
              'fotos': [q for q in (' '.join(re.sub(r'[^a-z ]', ' ', str(x).lower()).split()[:4]) for x in (r.get('fotos') or []) if isinstance(x, str))
                        if len(q) >= 3][:4]}
    if perfil['categoria'] not in cats:
        perfil['categoria'] = ''
    if perfil['tono'] not in tonos:
        perfil['tono'] = ''
    with open(salida, 'w', encoding='utf-8') as f:
        json.dump({'modelo': repo, 'segundos': round(time.time() - t0, 1), 'perfil': perfil}, f, ensure_ascii=False)
    decir('LISTO', salida)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entrada')
    ap.add_argument('--salida')
    ap.add_argument('--modelo', default='auto')
    ap.add_argument('--descargar', action='store_true')
    ap.add_argument('--servidor', action='store_true')
    ap.add_argument('--inactivo', type=float, default=180.0)
    a = ap.parse_args()
    try:
        if a.servidor:
            servidor(a.modelo, a.inactivo)
        elif a.descargar:
            from huggingface_hub import snapshot_download
            clave, _, _ = elegir(a.modelo)
            decir('ESTADO', f'Descargando {REPOS[clave]}')
            snapshot_download(repo_id=REPOS[clave])
            decir('LISTO', clave)
        else:
            analizar(a.entrada, a.salida, a.modelo)
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        decir('ERROR', f'{type(e).__name__}: {e}'.replace('\n', ' ')[:500])
        sys.exit(1)


if __name__ == '__main__':
    main()
