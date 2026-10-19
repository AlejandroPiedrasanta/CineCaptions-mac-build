# CineCaptions · By Cinema Productions
# 2_recursos/motor_qwen/motor_qwen.py — motor de voz Qwen3-ASR + alineador (corre en el Python 3.12 del motor).
"""Motor de voz Qwen3-ASR de CineCaptions.

Corre en su PROPIO Python 3.14 (el que instala el paso "Motor de voz"), no
dentro del programa: torch + transformers pesan varios GB y no tienen sitio
en el .exe. El programa lo lanza como proceso aparte y habla con el por
stdout, una linea por mensaje:

    PROGRESO|0.42          fraccion hecha (0..1)
    ESTADO|texto           que esta haciendo
    LISTO|<ruta.json>      termino; las palabras estan en ese json
    ERROR|texto            no pudo

Uso:
    python motor_qwen.py --audio voz16k.wav --idioma Spanish --salida palabras.json
    python motor_qwen.py --servidor [--inactivo 120]     (v5.3: el modelo queda CARGADO y calentado)
    python motor_qwen.py --descargar [--modelo 1.7B|0.6B]
    python motor_qwen.py --comprobar

v5.3, el modo servidor: cargar el motor cuesta ~11 s de imports + ~8 s de modelo y la PRIMERA pasada otros ~20 s (CUDA
inicializa sus nucleos al primer uso); las siguientes tardan ~5 s para 24 s de audio. El servidor paga todo eso UNA vez, en
cuanto el usuario pulsa GO (mientras Resolve renderiza el audio), calienta el modelo con 3 s de audio sintetico y atiende
pedidos por stdin (una linea JSON {"audio","idioma","salida"} por pedido) hasta 'inactivo' segundos sin trabajo. Los tramos
de un audio largo se procesan en LOTE (varios a la vez en la GPU: ~2,6x mas rapido que uno por uno).

v5.5.8 (motor 2.0): Qwen3-ASR NATIVO de Transformers 5 (sin el paquete qwen-asr, que fijaba transformers 4.57): modelos
«-hf» (Qwen/Qwen3-ASR-1.7B-hf, Qwen/Qwen3-ForcedAligner-0.6B-hf), AutoModelForMultimodalLM para el texto y
AutoModelForTokenClassification para los tiempos de cada palabra. Mismo protocolo y mismo json de salida.

El json de salida: {"idioma": "Spanish", "modelo": "...", "palabras":
[{"word": "Hola,", "start": 0.42, "end": 0.71}, ...]} — lo mismo que da
faster-whisper, para que el resto del programa no note la diferencia.
"""
import argparse
import json
import os
import sys
import time
import unicodedata

os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')

REPO_ASR = {'1.7B': 'Qwen/Qwen3-ASR-1.7B-hf', '0.6B': 'Qwen/Qwen3-ASR-0.6B-hf'}
REPO_ALINEADOR = 'Qwen/Qwen3-ForcedAligner-0.6B-hf'
# El alineador acepta hasta 180 s; se corta antes, en un silencio, para que
# cada tramo quepa holgado en max_new_tokens y el progreso avance seguido.
TRAMO_S = 90.0
VERSION_MOTOR = '2.0.0'


def decir(tipo, texto=''):
    sys.stdout.write(f'{tipo}|{texto}\n')
    sys.stdout.flush()


def elegir_dispositivo(pedido):
    import torch
    if pedido == 'cpu' or not torch.cuda.is_available():
        return 'cpu', torch.float32, 0
    vram = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    return 'cuda:0', dtype, vram


def elegir_modelo(pedido, dispositivo, vram):
    if pedido in REPO_ASR:
        return pedido
    # 1.7B en bf16 ocupa ~4 GB + 1,2 GB el alineador: con menos de 8 GB de
    # VRAM, o en CPU, va el 0.6B (mas ligero y bastante mas rapido)
    return '1.7B' if dispositivo.startswith('cuda') and vram >= 7.5 else '0.6B'


def descargar(modelo):
    from huggingface_hub import snapshot_download
    repos = [REPO_ASR[modelo], REPO_ALINEADOR]
    for i, repo in enumerate(repos):
        decir('ESTADO', f'Descargando {repo}')
        snapshot_download(repo_id=repo)
        decir('PROGRESO', f'{(i + 1) / len(repos):.3f}')


def _limpio(palabra):
    """Lo que el alineador ve de una palabra: letras y numeros, sin signos."""
    return ''.join(ch for ch in unicodedata.normalize('NFKC', palabra)
                   if unicodedata.category(ch)[0] in 'LNM')


def casar_con_texto(texto, items, offset):
    """Devuelve las palabras CON su puntuacion y con los tiempos del alineador.

    El alineador limpia los signos ("Hola," -> "Hola"); los subtitulos los
    necesitan. Se recorre el texto original por espacios y cada palabra que
    tiene letras toma el siguiente item; los signos sueltos se pegan a la
    palabra anterior. Cada item: {'text', 'start_time', 'end_time'} (segundos).
    """
    palabras = []
    j = 0
    for w in texto.split():
        if not _limpio(w):
            if palabras:
                palabras[-1]['word'] += w
            continue
        if j >= len(items):
            break
        it = items[j]
        j += 1
        palabras.append({'word': w, 'start': round(float(it['start_time']) + offset, 3),
                         'end': round(float(it['end_time']) + offset, 3)})
    # idiomas sin espacios (chino, japones): el alineador parte en sus propias
    # unidades; si el casado por espacios no cubrio, se usan sus items tal cual
    if j < len(items) * 0.5:
        palabras = [{'word': it['text'], 'start': round(float(it['start_time']) + offset, 3),
                     'end': round(float(it['end_time']) + offset, 3)} for it in items]
    return palabras


def tramos(wav, sr, max_s=TRAMO_S, buscar_s=5.0, ventana_ms=100.0):
    """[(trozo, offset_s)]: el audio partido en tramos de hasta max_s, cada corte en el punto mas silencioso de los
    buscar_s de alrededor (ventana de ventana_ms). Los trozos juntos son el audio entero, sin huecos ni solapes."""
    import numpy as np
    total = len(wav)
    maximo = int(max_s * sr)
    if total <= maximo:
        return [(wav, 0.0)]
    margen, ventana = int(buscar_s * sr), max(4, int(ventana_ms / 1000.0 * sr))
    out, ini = [], 0
    while total - ini > maximo:
        corte = ini + maximo
        izq, der = max(ini, corte - margen), min(total, corte + margen)
        if der - izq > ventana:
            energia = np.abs(wav[izq:der])
            sumas = np.convolve(energia, np.ones(ventana, dtype=np.float32), mode='valid')
            k = int(np.argmin(sumas))
            corte = izq + k + int(np.argmin(energia[k:k + ventana]))
        corte = min(max(corte, ini + 1), total)
        out.append((wav[ini:corte], ini / sr))
        ini = corte
    if ini < total:
        out.append((wav[ini:], ini / sr))
    return out


def _lote(dispositivo, vram):
    """Tramos que se procesan a la vez en la GPU (el 1.7B + alineador pasa de ~4,5 GB a ~6 GB con 4)."""
    if not dispositivo.startswith('cuda'):
        return 1
    return 4 if vram >= 20 else 2 if vram >= 7.5 else 1       # con <20 GB se deja margen: la IA de texto se carga a la vez


class Motor:
    """Qwen3-ASR + alineador cargados (lo caro, una vez)."""

    def __init__(self, modelo_pedido, dispositivo_pedido):
        from transformers import AutoModelForMultimodalLM, AutoModelForTokenClassification, AutoProcessor
        self.dispositivo, self.dtype, vram = elegir_dispositivo(dispositivo_pedido)
        self.modelo = elegir_modelo(modelo_pedido, self.dispositivo, vram)
        self.lote = _lote(self.dispositivo, vram)
        decir('ESTADO', f'Cargando Qwen3-ASR {self.modelo} en {"GPU" if self.dispositivo != "cpu" else "CPU"}')
        t0 = time.time()
        self.proc = AutoProcessor.from_pretrained(REPO_ASR[self.modelo])
        self.asr = AutoModelForMultimodalLM.from_pretrained(REPO_ASR[self.modelo], dtype=self.dtype, device_map=self.dispositivo).eval()
        self.proc_al = AutoProcessor.from_pretrained(REPO_ALINEADOR)
        self.alineador = AutoModelForTokenClassification.from_pretrained(REPO_ALINEADOR, dtype=self.dtype,
                                                                         device_map=self.dispositivo).eval()
        decir('ESTADO', f'Modelo listo en {time.time() - t0:.1f} s')

    def transcribir(self, audios, idioma, contexto=''):
        """audios: [np.float32 a 16 kHz]. Devuelve [(texto, idioma, [items del alineador])] en el mismo orden.
        contexto (v5.5.17): vocabulario del video (nombres que el usuario ya corrigió, texto que aparece en pantalla) como «system prompt» de
        Qwen3-ASR (contextual biasing: «Xela», «FIFA», «Glass Collective» se oyen bien desde el principio)."""
        import torch
        n = len(audios)
        with torch.inference_mode():
            try:
                ent = self.proc.apply_transcription_request(audio=list(audios), language=[idioma or None] * n,
                                                            **({'prompt': [contexto] * n} if contexto else {}))
            except TypeError:                             # (un Transformers sin «prompt»: sin vocabulario, como siempre)
                ent = self.proc.apply_transcription_request(audio=list(audios), language=[idioma or None] * n)
            ent = ent.to(self.asr.device, self.asr.dtype)
            ids = self.asr.generate(**ent, max_new_tokens=1024, do_sample=False)
            leidos = self.proc.decode(ids[:, ent['input_ids'].shape[1]:], return_format='parsed')
            if isinstance(leidos, dict):
                leidos = [leidos]
            textos = [(r.get('transcription') or '').strip() for r in leidos]
            idiomas = [idioma or r.get('language') or '' for r in leidos]
            items = [[] for _ in range(n)]
            con_texto = [i for i in range(n) if textos[i] and idiomas[i]]
            if con_texto:
                ent_al, listas = self.proc_al.prepare_forced_aligner_inputs(
                    audio=[audios[i] for i in con_texto], transcript=[textos[i] for i in con_texto],
                    language=[idiomas[i] for i in con_texto])
                ent_al = ent_al.to(self.alineador.device, self.alineador.dtype)
                sal = self.alineador(**ent_al)
                tiempos = self.proc_al.decode_forced_alignment(
                    logits=sal.logits, input_ids=ent_al['input_ids'], word_lists=listas,
                    timestamp_token_id=self.alineador.config.timestamp_token_id)
                for i, t in zip(con_texto, tiempos):
                    items[i] = list(t)
        return list(zip(textos, idiomas, items))


def cargar_modelo(modelo_pedido, dispositivo_pedido):
    """(motor, dispositivo, modelo) — lo caro, una vez."""
    m = Motor(modelo_pedido, dispositivo_pedido)
    return m, m.dispositivo, m.modelo


def calentar(motor, dispositivo):
    """Una pasada corta con 3 s de «voz» sintetica: la primera inferencia de CUDA tarda ~20 s (inicializa nucleos y
    manejadores); hecha aqui, la del usuario ya sale en ~5 s. Nunca lanza."""
    try:
        import numpy as np
        sr = 16000
        t = np.arange(3 * sr) / sr
        voz = (0.25 * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
               + 0.12 * np.sin(2 * np.pi * 540 * t)).astype('float32')
        t0 = time.time()
        motor.transcribir([voz], 'Spanish')
        decir('ESTADO', f'Motor calentado en {time.time() - t0:.1f} s')
    except Exception as e:                                 # un calentamiento fallido no impide trabajar
        decir('ESTADO', f'Calentamiento omitido ({type(e).__name__})')


def transcribir_con(motor, ruta_audio, idioma, salida, dispositivo, modelo, t0=None, contexto=''):
    """Transcribe con el modelo YA cargado y escribe el json. Los tramos van en lote."""
    import numpy as np
    import soundfile as sf
    t0 = t0 or time.time()
    wav, sr = sf.read(ruta_audio, dtype='float32', always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1).astype(np.float32)
    if sr != 16000:
        import librosa
        wav = librosa.resample(wav, orig_sr=sr, target_sr=16000).astype(np.float32)
        sr = 16000
    partes = [(trozo, offset) for trozo, offset in tramos(wav, sr) if len(trozo) >= sr * 0.3]
    total = len(wav) / sr
    palabras, idiomas = [], []
    decir('PROGRESO', '0.0')
    lote = max(1, int(getattr(motor, 'lote', 1) or 1))
    for k in range(0, len(partes), lote):
        grupo = partes[k:k + lote]
        resultados = motor.transcribir([trozo for trozo, _ in grupo], idioma or None, contexto)
        for (trozo, offset), (texto, idioma_res, items) in zip(grupo, resultados):
            if idioma_res:
                idiomas.append(idioma_res)
            if texto and items:
                palabras.extend(casar_con_texto(texto, items, offset))
        ultimo, off = grupo[-1][0], grupo[-1][1]
        decir('PROGRESO', f'{min(1.0, (off + len(ultimo) / sr) / total):.3f}')
    resultado = {'motor': 'qwen3-asr', 'version_motor': VERSION_MOTOR, 'modelo': REPO_ASR[modelo],
                 'dispositivo': dispositivo, 'idioma': idioma or (max(set(idiomas), key=idiomas.count) if idiomas else ''),
                 'segundos': round(time.time() - t0, 1), 'contexto': contexto, 'palabras': palabras}
    with open(salida, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False)
    decir('LISTO', salida)


def transcribir(ruta_audio, idioma, salida, modelo_pedido, dispositivo_pedido, contexto=''):
    """Una sola pasada (sin servidor): carga, transcribe y termina."""
    t0 = time.time()
    motor, dispositivo, modelo = cargar_modelo(modelo_pedido, dispositivo_pedido)
    transcribir_con(motor, ruta_audio, idioma, salida, dispositivo, modelo, t0, contexto)


def servidor(modelo_pedido, dispositivo_pedido, inactivo):
    """El motor queda cargado y calentado; atiende pedidos por stdin hasta 'inactivo' segundos sin trabajo."""
    import queue
    import threading
    motor, dispositivo, modelo = cargar_modelo(modelo_pedido, dispositivo_pedido)
    calentar(motor, dispositivo)
    cola = queue.Queue()

    def leer():
        for linea in sys.stdin:
            cola.put(linea)
        cola.put(None)
    threading.Thread(target=leer, daemon=True).start()
    decir('LISTA', REPO_ASR[modelo])
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
            transcribir_con(motor, orden['audio'], orden.get('idioma') or '', orden['salida'], dispositivo, modelo,
                            contexto=str(orden.get('contexto') or '')[:2000])
        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stderr)
            decir('ERROR', f'{type(e).__name__}: {e}'.replace('\n', ' ')[:500])
    decir('FIN', 'inactivo')


def comprobar():
    import torch
    import transformers
    from transformers import AutoModelForMultimodalLM, AutoModelForTokenClassification  # noqa: F401
    disp, _, vram = elegir_dispositivo('auto')
    info = {'torch': torch.__version__, 'transformers': transformers.__version__,
            'cuda': torch.cuda.is_available(), 'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else '',
            'vram_gb': round(vram, 1), 'modelo_auto': elegir_modelo('auto', disp, vram), 'version_motor': VERSION_MOTOR}
    decir('LISTO', json.dumps(info))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audio')
    ap.add_argument('--idioma', default='')
    ap.add_argument('--salida')
    ap.add_argument('--modelo', default='auto')
    ap.add_argument('--dispositivo', default='auto')
    ap.add_argument('--descargar', action='store_true')
    ap.add_argument('--comprobar', action='store_true')
    ap.add_argument('--servidor', action='store_true')
    ap.add_argument('--inactivo', type=float, default=120.0)
    ap.add_argument('--contexto', default='')
    a = ap.parse_args()
    try:
        if a.servidor:
            servidor(a.modelo, a.dispositivo, a.inactivo)
        elif a.comprobar:
            comprobar()
        elif a.descargar:
            if a.modelo not in REPO_ASR:
                disp, _, vram = elegir_dispositivo(a.dispositivo)
                a.modelo = elegir_modelo('auto', disp, vram)
            descargar(a.modelo)
            decir('LISTO', a.modelo)
        else:
            transcribir(a.audio, a.idioma, a.salida, a.modelo, a.dispositivo, a.contexto)
    except Exception as e:  # el programa necesita el motivo en una linea
        import traceback
        traceback.print_exc(file=sys.stderr)
        decir('ERROR', f'{type(e).__name__}: {e}'.replace('\n', ' ')[:500])
        sys.exit(1)


if __name__ == '__main__':
    main()
