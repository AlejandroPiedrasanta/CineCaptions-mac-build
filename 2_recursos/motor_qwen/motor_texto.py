# CineCaptions · By Cinema Productions
# 2_recursos/motor_qwen/motor_texto.py — IA de texto Qwen3 Instruct: correcciones, pesos y emojis por frase (modo servidor).
"""IA de texto de CineCaptions (Qwen3 Instruct, local, sin coste por uso).

Corre en el MISMO Python 3.12 del motor de voz (motor_qwen.py). Recibe la
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
    'palabras. No cambies el estilo de quien habla: solo errores.\n'
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
    'Eres un corrector ortográfico. Recibes una transcripción dividida en frases (F1, F2…); cada palabra lleva delante su '
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
    palabras = [str(p) for p in datos.get('palabras') or []]
    idioma = IDIOMAS.get(str(datos.get('idioma') or 'es')[:2], 'el idioma del texto')
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
                if g is not None and ' ' not in nueva.strip() and correccion_aceptable(palabras[g], nueva, 0.74 if modo == 'ortografia' else 0.55):
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
