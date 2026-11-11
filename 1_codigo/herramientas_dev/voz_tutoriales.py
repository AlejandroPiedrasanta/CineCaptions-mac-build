# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/voz_tutoriales.py — la locución de los tutoriales: cada frase que dicen los guiones (voz de ElevenLabs por Higgsfield, «Andre»), pulida, nivelada y en caché.
"""
voz_tutoriales.py  (v5.82)
--------------------------
    $PY voz_tutoriales.py --motor archivos --voz el_andre --listar pedido.json [--ids inicio,premiere]   (qué falta pedir al servicio)
    $PY voz_tutoriales.py --motor archivos --voz el_andre --desde CARPETA_DE_MP3 [--rehacer]           (importar lo descargado)
    <python con PyTorch> voz_tutoriales.py --motor qwen|sapi [--idiomas es,en,…] [--voz NOMBRE] [--rehacer] [--disenar]

El usuario pidió (2026-11-10) «agrégale voz» a los tutoriales: locución en español, con el volumen nivelado y sincronizada con lo que
pasa en pantalla. No quiso bajar modelos locales y eligió un servicio («utiliza eleven lab o algo para que descargues el mp3»): la voz
que viaja es la de ElevenLabs por el conector de Higgsfield, «Andre» (motor `archivos`; antes «Inés»). Aquí solo se HACEN las frases; el grabador
(hacer_videos_tutorial.py) las usa:

  1. Lee las frases de los guiones: cada `g.decir('…')` de hacer_videos_tutorial.py (en español). En otro idioma se dice su traducción
     (3_compilar/traducciones_extra.json o 2_recursos/locales/<idioma>.json; si falta, esa frase no se hace en ese idioma).
  2. Cada frase se sintetiza UNA vez y queda en la caché, fuera del proyecto: ~/.cache/cinecaptions_tts/frases/<voz>/<idioma>/<huella>.wav
     (mono, 24 kHz, 16 bits): sin silencio en las puntas, con fundidos de 12 ms y nivelada a NIVEL_LUFS (BS.1770, con la puerta de −70 /
     −10 LU) sin pasar de PICO_DB. La huella sale de la voz, el idioma y el texto HABLADO (PRONUNCIA): cambiar una frase rehace solo esa.
  3. Escribe ~/.cache/cinecaptions_tts/frases/<voz>/indice.json = {idioma: {frase en español: [archivo, segundos]}}. El grabador espera a
     que acabe cada frase antes de la acción siguiente y monta con ellas la pista de cada idioma (2_recursos/tutoriales/voz/<idioma>/<id>.m4a).

Motores:
  archivos   (lo que eligió el usuario el 2026-11-10: «utiliza eleven lab o algo para que descargues el mp3») los audios de un servicio de
         voz: ElevenLabs por el conector de Higgsfield, con SU cuenta (solo va el texto de las frases; cada frase cuesta créditos: se
         confirma antes). `--listar pedido.json [--ids inicio,premiere]` escribe lo que falta (texto hablado + huella); se generan con el
         conector, los MP3 se bajan a `--desde`/<idioma>/<huella>.mp3 y `--motor archivos --desde …` los pule (silencios, −17 LUFS) y
         los mete en el índice. PRONUNCIA_SERVICIO: el servicio ya dice bien las marcas en inglés.
  qwen   Qwen3-TTS de Alibaba (Apache-2.0: uso comercial libre; local, en la GPU; habla los 10 idiomas de la app). La voz se DISEÑA una vez
         con Qwen3-TTS-12Hz-1.7B-VoiceDesign a partir de VOCES[nombre] (descripción + frase de muestra) y se guarda como referencia en
         4_diseno/voz_tutoriales/<nombre>.wav + .txt (--disenar la rehace); cada frase la dice Qwen3-TTS-12Hz-1.7B-Base CLONANDO esa
         referencia: la misma voz en todas las frases y en todos los idiomas. Corre en su propio entorno (no en el de la app ni en el motor
         Qwen del usuario): ~/.cache/cinecaptions_tts/venv (Python 3.12 + PyTorch CUDA + qwen-tts).
  sapi   la voz de Windows (Sabina, es-MX) por COM: solo para probar la cadena entera sin GPU (suena robótica; no se entrega).
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
GUIONES = RAIZ / '1_codigo' / 'herramientas_dev' / 'hacer_videos_tutorial.py'
LOCALES = RAIZ / '2_recursos' / 'locales'
EXTRA = RAIZ / '3_compilar' / 'traducciones_extra.json'
DISENO = RAIZ / '4_diseno' / 'voz_tutoriales'
CACHE = Path.home() / '.cache' / 'cinecaptions_tts'
SR = 24000
NIVEL_LUFS = -17.0
PICO_DB = -1.5

IDIOMAS_QWEN = {'es': 'Spanish', 'en': 'English', 'pt': 'Portuguese', 'fr': 'French', 'de': 'German', 'it': 'Italian',
                'ja': 'Japanese', 'ko': 'Korean', 'zh': 'Chinese', 'ru': 'Russian'}

# Las voces que se pueden diseñar (VoiceDesign): una descripción y la frase con la que se graba la referencia que luego se clona.
VOCES = {
    'clara': {
        'instruccion': ('Voz femenina de unos 30 años, cálida, cercana y segura, con acento latinoamericano neutro. Habla claro y a un '
                        'ritmo tranquilo, como una presentadora que enseña a usar una aplicación: sonríe al hablar, sin exagerar.'),
        'muestra': ('Hola. Te enseño en pocos segundos cómo se usa CineCaptions: arrastra tu video, elige tu estilo y pulsa GO. '
                    'Todo queda listo en tu línea de tiempo.'),
    },
    'mateo': {
        'instruccion': ('Voz masculina de unos 30 años, cálida y amable, con acento latinoamericano neutro. Habla claro, a un ritmo '
                        'tranquilo y con buena energía, como un creador de contenido que enseña a usar una aplicación.'),
        'muestra': ('Hola. Te enseño en pocos segundos cómo se usa CineCaptions: arrastra tu video, elige tu estilo y pulsa GO. '
                    'Todo queda listo en tu línea de tiempo.'),
    },
}

# Cómo se DICEN algunas palabras (el subtítulo sigue escrito bien). Se aplica por palabra entera, en este orden.
PRONUNCIA = {
    'es': [('CineCaptions', 'Cine Cápshons'), ('DaVinci Resolve', 'Davinchi Risolv'), ('Resolve', 'Risolv'), ('DaVinci', 'Davinchi'),
           ('Premiere Pro', 'Premier Pro'), ('Premiere', 'Premier'), ('timeline', 'táimlain'), ('GO', 'Gou'), ('MP4', 'eme pe cuatro'),
           ('WhatsApp', 'Guatsap'), ('captions', 'cápshons'), ('PRO', 'Pro')],
}
# Con un servicio (ElevenLabs) las marcas en inglés ya salen bien dentro del español: solo que no deletree las mayúsculas.
# En inglés, «CineCaptions» de una pieza se lee mal: separado suena «Cine Captions».
PRONUNCIA_SERVICIO = {
    'es': [('GO', 'Go'), ('PRO', 'Pro')],
    'en': [('CineCaptions', 'Cine Captions'), ('GO', 'Go'), ('PRO', 'Pro')],
}


def _pronuncia(idioma, motor):
    return (PRONUNCIA if motor == 'qwen' else PRONUNCIA_SERVICIO).get(idioma, [('GO', 'Go'), ('PRO', 'Pro')])


# v5.82: el usuario cambió a «voz de hombre energético y alegre» (ElevenLabs «Andre»). Con `animo`, algunas frases se DICEN exclamadas
# (el subtítulo sigue igual: nada que retraducir). No todas: las explicaciones van normales, así suena alegre y no gritado.
VOCES_SERVICIO = {'el_andre': {'animo': True}, 'el_ines': {}}
ANIMO_ES = {
    'Arrastra tu video a la ventana de CineCaptions': '¡Arrastra tu video a la ventana de CineCaptions!',
    '¡Listo! Todo queda en tu timeline': '¡Listo! ¡Todo queda en tu timeline!',
    'Cada tarjeta es un estilo, con subtítulos de verdad': '¡Cada tarjeta es un estilo, con subtítulos de verdad!',
    'Puedes cambiarlo cuando quieras': '¡Puedes cambiarlo cuando quieras!',
    'Ponle un nombre y créalo': '¡Ponle un nombre y créalo!',
    'Pasa los estilos arrastrando las tarjetas': '¡Pasa los estilos arrastrando las tarjetas!',
    'Cuando te guste uno, haz clic en el del centro para usarlo': 'Cuando te guste uno, ¡haz clic en el del centro para usarlo!',
    '¿Editas en Premiere Pro? Abre los ajustes': '¿Editas en Premiere Pro? ¡Abre los ajustes!',
    'En General, enciende «Usar con Premiere Pro»': 'En General, ¡enciende «Usar con Premiere Pro»!',
    'Suelta tu video y GO arma la secuencia: video, subtítulos y sonidos': '¡Suelta tu video y GO arma la secuencia: video, subtítulos y sonidos!',
    'Si Premiere está cerrado, CineCaptions lo abre solo': 'Si Premiere está cerrado, ¡CineCaptions lo abre solo!',
    '¿No usas editor de video? Abre los ajustes': '¿No usas editor de video? ¡Abre los ajustes!',
    'Enciende «Video sin editores»': '¡Enciende «Video sin editores»!',
    'Suelta tu video y pulsa GO: no hace falta DaVinci ni Premiere': '¡Suelta tu video y pulsa GO! No hace falta DaVinci ni Premiere.',
    'Tu video con subtítulos queda junto al original': '¡Tu video con subtítulos queda junto al original!',
    'Haz clic en la que más te guste': '¡Haz clic en la que más te guste!',
    '¿Algo no funciona? Abre Ayuda en los ajustes': '¿Algo no funciona? ¡Abre Ayuda en los ajustes!',
    'Escríbenos por WhatsApp: el informe de tu equipo va listo para enviar': '¡Escríbenos por WhatsApp! El informe de tu equipo va listo para enviar.',
    'Después de GO, tus palabras aparecen aquí': 'Después de GO, ¡tus palabras aparecen aquí!',
    'Y listo: palabra corregida': '¡Y listo! Palabra corregida.',
    'Elige cómo suena tu video': '¡Elige cómo suena tu video!',
    'Aquí eliges los efectos que GO pone solo': '¡Aquí eliges los efectos que GO pone solo!',
    'GO aplica solo lo que elijas': '¡GO aplica solo lo que elijas!',
    'En Tutoriales están todos estos videos': '¡En Tutoriales están todos estos videos!',
}
# v5.83 (el usuario: «si está en idioma inglés hay que adaptarlo captions y audio»): las mismas frases exclamadas en inglés. La clave es
# la traducción de locales/en.json: si esa traducción cambia, la frase se dice normal (no falla).
ANIMO_EN = {
    'Drag your video into the CineCaptions window': 'Drag your video into the CineCaptions window!',
    'Done! Everything lands in your timeline': 'Done! Everything lands in your timeline!',
    'Each card is a style, with real captions': 'Each card is a style, with real captions!',
    'You can change it anytime': 'You can change it anytime!',
    'Give it a name and create it': 'Give it a name and create it!',
    'Browse the styles by dragging the cards': 'Browse the styles by dragging the cards!',
    'When you like one, click the one in the middle to use it': 'When you like one, click the one in the middle to use it!',
    'Edit in Premiere Pro? Open the settings': 'Edit in Premiere Pro? Open the settings!',
    'In General, turn on "Use with Premiere Pro"': 'In General, turn on "Use with Premiere Pro"!',
    'Drop your video and GO builds the sequence: video, captions and sounds': 'Drop your video and GO builds the sequence: video, captions and sounds!',
    'If Premiere is closed, CineCaptions opens it for you': 'If Premiere is closed, CineCaptions opens it for you!',
    "Don't use a video editor? Open the settings": "Don't use a video editor? Open the settings!",
    'Turn on "Video without editors"': 'Turn on "Video without editors"!',
    'Drop your video and press GO: no need for DaVinci or Premiere': 'Drop your video and press GO! No need for DaVinci or Premiere.',
    'Your captioned video is saved next to the original': 'Your captioned video is saved next to the original!',
    'Click the one you like best': 'Click the one you like best!',
    'Something not working? Open Help in the settings': 'Something not working? Open Help in the settings!',
    "Message us on WhatsApp: your computer's report is ready to send": "Message us on WhatsApp! Your computer's report is ready to send.",
    'After GO, your words show up here': 'After GO, your words show up here!',
    'And done: word fixed': 'And done! Word fixed.',
    'Choose how your video sounds': 'Choose how your video sounds!',
    'Here you choose the effects GO adds on its own': 'Here you choose the effects GO adds on its own!',
    'GO applies whatever you choose on its own': 'GO applies whatever you choose on its own!',
    'All these videos are in Tutorials': 'All these videos are in Tutorials!',
}
ANIMO = {'es': ANIMO_ES, 'en': ANIMO_EN}


# ---------------------------------------------------------------------------------------------------- las frases
def frases(ids=None):
    """Las frases de los guiones, en orden y sin repetir: cada `yield from g.decir('…')` de hacer_videos_tutorial.py (texto literal).
    Con `ids`, solo las de esos guiones (def g_<id>(g): … hasta la siguiente función de nivel superior)."""
    texto = GUIONES.read_text(encoding='utf-8')
    if ids:
        trozos = []
        for ident in ids:
            m = re.search(r'^def g_' + re.escape(ident) + r'\(g\):\n(.*?)(?=^def |^[A-Z_]+ = |\Z)', texto, re.M | re.S)
            if m:
                trozos.append(m.group(1))
        texto = '\n'.join(trozos)
    vistas, out = set(), []
    for m in re.finditer(r"""^\s*yield from g\.decir\(\s*'((?:[^'\\]|\\.)+)'""", texto, re.M):
        f = m.group(1).replace("\\'", "'")
        if f not in vistas:
            vistas.add(f)
            out.append(f)
    return out


_CATALOGOS = {}


def traduccion(frase, idioma):
    """La frase en ese idioma (traducciones_extra.json primero: ahí van las nuevas antes de pasar a los catálogos) o None."""
    if idioma == 'es':
        return frase
    if idioma not in _CATALOGOS:
        tabla = {}
        try:
            tabla.update(json.loads((LOCALES / f'{idioma}.json').read_text(encoding='utf-8')).get('textos') or {})
        except Exception:
            pass
        try:
            for es, por in (json.loads(EXTRA.read_text(encoding='utf-8')) or {}).items():
                if isinstance(por, dict) and por.get(idioma):
                    tabla[es] = por[idioma]
        except Exception:
            pass
        _CATALOGOS[idioma] = tabla
    t = _CATALOGOS[idioma].get(frase)
    return t if t and t.strip() else None


def hablado(texto, idioma, motor='qwen', voz=None):
    """El texto tal como se le da a la voz: con el ánimo de la voz (ANIMO_ES / ANIMO_EN), sin comillas ni signos que se leerían, y con
    la pronunciación del motor."""
    t = texto
    if (VOCES_SERVICIO.get(voz) or {}).get('animo'):
        t = (ANIMO.get(idioma) or {}).get(texto, texto)
    for c in '«»“”„「」"':
        t = t.replace(c, '')
    t = t.replace('›', ',').replace('…', '...')
    for escrito, dicho in _pronuncia(idioma, motor):
        t = re.sub(r'(?<![\wÁÉÍÓÚáéíóúñÑ])' + re.escape(escrito) + r'(?![\wÁÉÍÓÚáéíóúñÑ])', dicho, t)
    t = re.sub(r'\s+', ' ', t).strip()
    if t and t[-1] not in '.!?。！？…':                   # (los subtítulos van sin punto final, como siempre; la voz lo necesita para cerrar la frase)
        t += '。' if idioma in ('ja', 'zh') else '.'
    return t


def huella(voz, idioma, texto):
    return hashlib.sha1(f'{voz}|{idioma}|{texto}'.encode('utf-8')).hexdigest()[:16]


# ---------------------------------------------------------------------------------------------------- el sonido
def _biquad(x, b, a):
    try:
        from scipy.signal import lfilter
        return lfilter(b, a, x)
    except Exception:                                  # (sin scipy: el filtro a mano; las frases son cortas)
        y = np.zeros_like(x)
        x1 = x2 = y1 = y2 = 0.0
        b0, b1, b2 = b[0] / a[0], b[1] / a[0], b[2] / a[0]
        a1, a2 = a[1] / a[0], a[2] / a[0]
        for i, v in enumerate(x):
            o = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2, x1, y2, y1 = x1, v, y1, o
            y[i] = o
        return y


def lufs(x, sr=SR):
    """Sonoridad integrada (ITU-R BS.1770-4: filtro K, bloques de 400 ms al 75 %, puertas de −70 LUFS y −10 LU)."""
    x = np.asarray(x, dtype=np.float64)
    if len(x) < int(0.4 * sr):
        x = np.pad(x, (0, int(0.4 * sr) - len(x)))
    A = 10 ** (4.0 / 40.0)
    w0 = 2 * math.pi * 1681.974450955533 / sr
    al = math.sin(w0) / (2 * 0.7071752369554196)
    c = math.cos(w0)
    b = [A * ((A + 1) + (A - 1) * c + 2 * math.sqrt(A) * al), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - 2 * math.sqrt(A) * al)]
    a = [(A + 1) - (A - 1) * c + 2 * math.sqrt(A) * al, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - 2 * math.sqrt(A) * al]
    y = _biquad(x, b, a)
    w0 = 2 * math.pi * 38.13547087602444 / sr
    al = math.sin(w0) / (2 * 0.5003270373238773)
    c = math.cos(w0)
    y = _biquad(y, [(1 + c) / 2, -(1 + c), (1 + c) / 2], [1 + al, -2 * c, 1 - al])
    n, paso = int(0.4 * sr), int(0.1 * sr)
    z = np.array([np.mean(y[i:i + n] ** 2) for i in range(0, len(y) - n + 1, paso)])
    z = z[z > 0]
    if not len(z):
        return -120.0
    l = -0.691 + 10 * np.log10(z)
    z = z[l > -70]
    if not len(z):
        return -120.0
    rel = -0.691 + 10 * np.log10(np.mean(z)) - 10
    z = z[(-0.691 + 10 * np.log10(z)) > rel]
    return float(-0.691 + 10 * np.log10(np.mean(z))) if len(z) else -120.0


def remuestrear(x, sr_de, sr_a=SR):
    if sr_de == sr_a:
        return np.asarray(x, dtype=np.float32)
    try:
        from scipy.signal import resample_poly
        g = math.gcd(int(sr_de), int(sr_a))
        return resample_poly(x, sr_a // g, sr_de // g).astype(np.float32)
    except Exception:
        t = np.arange(int(len(x) * sr_a / sr_de)) * (sr_de / sr_a)
        return np.interp(t, np.arange(len(x)), x).astype(np.float32)


def acortar_pausas(x, sr=SR, umbral_db=-38.0, desde=0.28, resto=0.2):
    """Las pausas de dentro de la frase (bajo `umbral_db` del pico, más de `desde` s) se acortan a desde + resto × lo que sobraba: la voz
    del servicio para hasta 1,9 s en cada coma o dos puntos y los tutoriales iban lentos. Se quita el CENTRO del silencio (la voz no se
    toca) y se une con un fundido de 12 ms."""
    v = int(0.01 * sr)
    n = len(x) // v
    if n < 10:
        return x
    env = np.sqrt(np.mean(x[:n * v].astype(np.float64).reshape(n, v) ** 2, axis=1))
    voz = env > env.max() * 10 ** (umbral_db / 20)
    idx = np.nonzero(voz)[0]
    if len(idx) < 2:
        return x
    cortes, k = [], int(idx[0])
    while k <= idx[-1]:
        if voz[k]:
            k += 1
            continue
        j = k
        while j <= idx[-1] and not voz[j]:
            j += 1
        p = (j - k) * 0.01
        if p > desde:
            quitar = (p - desde) * (1.0 - resto)
            c0 = int((k * 0.01 + (p - quitar) / 2.0) * sr)
            cortes.append((c0, c0 + int(quitar * sr)))
        k = j
    if not cortes:
        return x
    partes, pos = [], 0
    for c0, c1 in cortes:
        partes.append(x[pos:c0])
        pos = c1
    partes.append(x[pos:])
    f = int(0.012 * sr)
    out = partes[0]
    for p in partes[1:]:
        if len(out) > f and len(p) > f:
            r = np.linspace(0.0, 1.0, f, dtype=np.float32)
            out = np.concatenate([out[:-f], out[-f:] * (1.0 - r) + p[:f] * r, p[f:]])
        else:
            out = np.concatenate([out, p])
    return out.astype(np.float32)


def pulir(x, sr=SR):
    """Sin silencio en las puntas (−40 dB del pico, con 70 ms antes y 140 ms después), pausas internas acortadas (acortar_pausas),
    fundidos de 12 ms y nivelada a NIVEL_LUFS sin pasar de PICO_DB (si el pico mandaría, baja todo: nunca se recorta)."""
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    x = x - float(np.mean(x)) if len(x) else x
    pico = float(np.max(np.abs(x))) if len(x) else 0.0
    if pico <= 1e-6:
        return x
    v = int(0.01 * sr)
    env = np.sqrt(np.convolve(x.astype(np.float64) ** 2, np.ones(v) / v, mode='same'))
    voz = np.nonzero(env > pico * 10 ** (-40 / 20))[0]
    if len(voz):
        i0 = max(0, voz[0] - int(0.07 * sr))
        i1 = min(len(x), voz[-1] + int(0.14 * sr))
        x = x[i0:i1]
    x = acortar_pausas(x, sr)
    f = min(len(x) // 4, int(0.012 * sr))
    if f > 1:
        rampa = np.linspace(0.0, 1.0, f, dtype=np.float32)
        x[:f] *= rampa
        x[-f:] *= rampa[::-1]
    ganancia = 10 ** ((NIVEL_LUFS - lufs(x, sr)) / 20)
    pico = float(np.max(np.abs(x))) * ganancia
    tope = 10 ** (PICO_DB / 20)
    if pico > tope:
        ganancia *= tope / pico
    return (x * ganancia).astype(np.float32)


def guardar_wav(ruta, x, sr=SR):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix('.tmp.wav')
    with wave.open(str(tmp), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
    os.replace(tmp, ruta)


def leer_wav(ruta):
    with wave.open(str(ruta), 'rb') as w:
        sr, n, canales = w.getframerate(), w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), dtype='<i2').astype(np.float32) / 32768.0
    if canales > 1:
        x = x.reshape(-1, canales).mean(axis=1)
    return x, sr


# ---------------------------------------------------------------------------------------------------- los motores
class MotorSapi:
    """La voz de Windows por COM (solo para probar la cadena)."""
    nombre = 'sapi'

    def __init__(self, _voz):
        import comtypes.client
        self._cc = comtypes.client
        self.v = comtypes.client.CreateObject('SAPI.SpVoice')
        voces = self.v.GetVoices()
        for i in range(voces.Count):
            d = voces.Item(i).GetDescription()
            if any(k in d for k in ('Spanish', 'Español', 'Sabina', 'Helena', 'Laura', 'Pablo')):
                self.v.Voice = voces.Item(i)
                break

    def decir(self, textos, idioma):
        out = []
        for texto in textos:
            tmp = CACHE / 'tmp_sapi.wav'
            tmp.parent.mkdir(parents=True, exist_ok=True)
            s = self._cc.CreateObject('SAPI.SpFileStream')
            fmt = self._cc.CreateObject('SAPI.SpAudioFormat')
            fmt.Type = 34                                   # SAFT24kHz16BitMono
            s.Format = fmt
            s.Open(str(tmp), 3, False)
            self.v.AudioOutputStream = s
            self.v.Rate = 0
            self.v.Speak(texto)
            s.Close()
            x, sr = leer_wav(tmp)
            out.append(remuestrear(x, sr))
            tmp.unlink(missing_ok=True)
        return out


class MotorQwen:
    """Qwen3-TTS: la voz diseñada una vez (VoiceDesign) y clonada en cada frase (Base), en la GPU."""
    nombre = 'qwen'
    DISENO = 'Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign'
    BASE = 'Qwen/Qwen3-TTS-12Hz-1.7B-Base'

    def __init__(self, voz, redisenar=False):
        import torch
        from qwen_tts import Qwen3TTSModel
        self.torch, self.Modelo = torch, Qwen3TTSModel
        self.voz = voz
        self.ref_wav = DISENO / f'{voz}.wav'
        self.ref_txt = DISENO / f'{voz}.txt'
        if redisenar or not self.ref_wav.is_file():
            self._disenar()
        self.modelo = self._cargar(self.BASE)
        self.prompt = self.modelo.create_voice_clone_prompt(ref_audio=str(self.ref_wav), ref_text=self.ref_txt.read_text(encoding='utf-8').strip())

    def _cargar(self, nombre):
        t0 = time.perf_counter()
        m = self.Modelo.from_pretrained(nombre, device_map='cuda:0', dtype=self.torch.bfloat16)
        print(f'  modelo {nombre.split("/")[-1]} cargado en {time.perf_counter() - t0:.1f} s', flush=True)
        return m

    def _disenar(self):
        d = VOCES[self.voz]
        m = self._cargar(self.DISENO)
        texto = hablado(d['muestra'], 'es')
        wavs, sr = m.generate_voice_design(text=texto, language='Spanish', instruct=d['instruccion'])
        x = pulir(remuestrear(np.asarray(wavs[0], dtype=np.float32), sr))
        guardar_wav(self.ref_wav, x)
        self.ref_txt.parent.mkdir(parents=True, exist_ok=True)
        self.ref_txt.write_text(texto + '\n', encoding='utf-8')
        print(f'  voz «{self.voz}» diseñada: {self.ref_wav} ({len(x) / SR:.1f} s)', flush=True)
        del m
        self.torch.cuda.empty_cache()

    def decir(self, textos, idioma):
        wavs, sr = self.modelo.generate_voice_clone(text=list(textos), language=[IDIOMAS_QWEN.get(idioma, 'Auto')] * len(textos),
                                                    voice_clone_prompt=self.prompt)
        return [remuestrear(np.asarray(w, dtype=np.float32), sr) for w in wavs]


# ---------------------------------------------------------------------------------------------------- todo
def carpeta_voz(voz):
    return CACHE / 'frases' / voz


def leer_indice(voz):
    try:
        return json.loads((carpeta_voz(voz) / 'indice.json').read_text(encoding='utf-8'))
    except Exception:
        return {}


def leer_audio(ruta):
    """Cualquier audio (MP3 del servicio, WAV…) → mono float32 a SR (PyAV, que ya viaja con la app)."""
    import av
    partes = []
    with av.open(str(ruta)) as c:
        rs = av.AudioResampler(format='flt', layout='mono', rate=SR)
        for fr in c.decode(c.streams.audio[0]):
            for g in rs.resample(fr):
                partes.append(g.to_ndarray().reshape(-1))
        for g in rs.resample(None):
            partes.append(g.to_ndarray().reshape(-1))
    return np.concatenate(partes).astype(np.float32) if partes else np.zeros(0, dtype=np.float32)


def pendientes(voz, idioma, motor, indice, rehacer=False, solo=None):
    """[(frase, texto hablado, archivo)] que faltan de esa voz e idioma (`solo`: limitar a esas frases)."""
    base, tabla, out = carpeta_voz(voz), indice.get(idioma) or {}, []
    for f in frases():
        if solo and f not in solo:
            continue
        t = traduccion(f, idioma)
        if not t:
            print(f'  [{idioma}] sin traducción: {f}', flush=True)
            continue
        dicho = hablado(t, idioma, motor, voz)
        arch = f'{idioma}/{huella(voz, idioma, dicho)}.wav'
        if not rehacer and (base / arch).is_file() and f in tabla and tabla[f][0] == arch:
            continue
        out.append((f, dicho, arch))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--motor', default='qwen', choices=('qwen', 'sapi', 'archivos'),
                    help='archivos: los audios ya hechos por un servicio de voz (ElevenLabs por Higgsfield), en --desde')
    ap.add_argument('--voz', default='clara')
    ap.add_argument('--idiomas', default='es')
    ap.add_argument('--rehacer', action='store_true', help='vuelve a decir todas las frases (si no, solo las que falten)')
    ap.add_argument('--disenar', action='store_true', help='vuelve a diseñar la voz de referencia (qwen)')
    ap.add_argument('--lote', type=int, default=6)
    ap.add_argument('--listar', help='solo escribe en este .json lo que falta (idioma, frase, texto hablado, huella): lo que se le pide al servicio')
    ap.add_argument('--desde', help='(archivos) carpeta con <idioma>/<huella>.mp3|.wav descargados del servicio')
    ap.add_argument('--solo', help='(listar) un .json con una lista de frases: solo esas')
    ap.add_argument('--ids', help='(listar) solo las frases de estos tutoriales, separados por comas (p. ej. los de las muestras)')
    a = ap.parse_args()
    voz = 'sapi' if a.motor == 'sapi' else a.voz
    idiomas = [x.strip() for x in a.idiomas.split(',') if x.strip()]
    solo = set(json.loads(Path(a.solo).read_text(encoding='utf-8'))) if a.solo else None
    if a.ids:
        solo = (solo or set()) | set(frases([x.strip() for x in a.ids.split(',') if x.strip()]))
    print(f'{len(frases())} frases · voz «{voz}» · idiomas {", ".join(idiomas)}', flush=True)
    base = carpeta_voz(voz)
    indice = leer_indice(voz)
    if a.listar:
        lista = [{'idioma': i, 'frase': f, 'dicho': d, 'huella': Path(arch).stem}
                 for i in idiomas for f, d, arch in pendientes(voz, i, a.motor, indice, a.rehacer, solo)]
        Path(a.listar).write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'{len(lista)} frases por hacer → {a.listar} ({sum(len(x["dicho"]) for x in lista)} letras)', flush=True)
        return
    motor = None
    for idioma in idiomas:
        tabla = indice.setdefault(idioma, {})
        faltan = pendientes(voz, idioma, a.motor, indice, a.rehacer)
        if not faltan:
            print(f'  [{idioma}] al día ({len(tabla)} frases)', flush=True)
            continue
        t0 = time.perf_counter()
        if a.motor == 'archivos':                       # los MP3 que hizo el servicio: se pulen igual que los propios
            hechas = 0
            for f, dicho, arch in faltan:
                src = next((p for p in (Path(a.desde) / idioma / (Path(arch).stem + e) for e in ('.mp3', '.wav', '.m4a')) if p.is_file()), None)
                if src is None:
                    continue
                x = pulir(leer_audio(src))
                guardar_wav(base / arch, x)
                tabla[f] = [arch, round(len(x) / SR, 3)]
                hechas += 1
                print(f'  [{idioma}] {len(x) / SR:4.1f} s  {f}', flush=True)
            print(f'  [{idioma}] {hechas} de {len(faltan)} importadas', flush=True)
        else:
            if motor is None:
                motor = MotorSapi(voz) if a.motor == 'sapi' else MotorQwen(voz, redisenar=a.disenar)
            for i in range(0, len(faltan), max(1, a.lote)):
                parte = faltan[i:i + a.lote]
                audios = motor.decir([d for _f, d, _a in parte], idioma)
                for (f, dicho, arch), x in zip(parte, audios):
                    x = pulir(x)
                    guardar_wav(base / arch, x)
                    tabla[f] = [arch, round(len(x) / SR, 3)]
                    print(f'  [{idioma}] {len(x) / SR:4.1f} s  {f}', flush=True)
                (base / 'indice.json').write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding='utf-8')
            print(f'  [{idioma}] {len(faltan)} frases en {time.perf_counter() - t0:.0f} s', flush=True)
    base.mkdir(parents=True, exist_ok=True)
    (base / 'indice.json').write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding='utf-8')
    print('índice:', base / 'indice.json', flush=True)


if __name__ == '__main__':
    main()
