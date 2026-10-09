# CineCaptions · By Cinema Productions
# 1_codigo/sfx_audio.py — audio del SFX Lab: cargar, cambiar tono y velocidad, reproducir.
"""\nsfx_audio.py\n------------\nCarga, procesa y reproduce los efectos de sonido de la biblioteca.\n\nEs la parte de bajo nivel del \"Estudio de sonidos\": abre el archivo con av\n(que ya viene por faster-whisper), lo pasa a un array de numpy, y ofrece\ndos efectos que se pueden combinar en vivo:\n\n  - cambiar_tono(audio, semitonos)     -> mismo largo, mas agudo o mas grave\n  - cambiar_velocidad(audio, factor)   -> mismo tono, mas corto o mas largo\n\nLos dos usan el mismo truco: un resample \"estilo vinilo\" (interpolar entre\nlas muestras) para acortar/estirar en el tiempo, combinado con un OLA\n(overlap-add) para compensar el largo cuando queremos cambiar solo el tono.\nNo es studio-grade — para SFX cortos (menos de 5 segundos) alcanza y sobra,\ny evita meter una libreria extra pesada tipo librosa.\n\nPara reproducir sin dependencias nuevas usa las herramientas que ya trae\ncada sistema: winsound en Windows, afplay en macOS, aplay en Linux.\n"""
import io
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
try:
    import av
except Exception:
    av = None
import numpy as np
SAMPLE_RATE = 44100
VENTANA_MS = 30
def _cargar_con_wave(ruta):
    """Carga audios .wav directamente con la librería estándar \'wave\' de Python.\n    Sirve como respaldo nativo si la librería \'av\' (PyAV/FFmpeg) no se puede cargar o falla.\n    """
    with wave.open(str(ruta), 'rb') as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        raw_bytes = wf.readframes(nframes)
    if sampwidth == 2:
        dtype = np.int16
        norm = 32768.0
    else:
        if sampwidth == 1:
            dtype = np.uint8
            norm = 128.0
        else:
            if sampwidth == 4:
                dtype = np.int32
                norm = 2147483648.0
            else:
                raise ValueError(f'Ancho de muestra no soportado: {sampwidth}')
    audio_data = np.frombuffer(raw_bytes, dtype=dtype).astype(np.float32)
    if sampwidth == 1:
        audio_data = (audio_data - 128.0) / norm
    else:
        audio_data = audio_data / norm
    if nchannels > 1:
        audio_data = audio_data.reshape((-1), nchannels).mean(axis=1)
    if framerate != SAMPLE_RATE and len(audio_data) > 0:
            num_muestras = int(len(audio_data) * (SAMPLE_RATE / framerate))
            x_old = np.linspace(0, 1, len(audio_data))
            x_new = np.linspace(0, 1, num_muestras)
            audio_data = np.interp(x_new, x_old, audio_data).astype(np.float32)
    return (audio_data, SAMPLE_RATE)
def cargar(ruta):
    """Devuelve (audio_mono_float32, sample_rate). Estereo se mezcla a mono."""
    if av is not None:
        try:
            contenedor = av.open(str(ruta))
            stream = next(s for s in contenedor.streams if s.type == 'audio')
            resampler = av.audio.resampler.AudioResampler(
                format='s16', layout='mono', rate=SAMPLE_RATE)
            trozos = []
            for frame in contenedor.decode(stream):
                for r in resampler.resample(frame):
                    trozos.append(r.to_ndarray().flatten())
            for r in resampler.resample(None):
                trozos.append(r.to_ndarray().flatten())
            contenedor.close()
            if not trozos:
                return (np.zeros(0, dtype=np.float32), SAMPLE_RATE)
            audio = np.concatenate(trozos).astype(np.float32) / 32768.0
            return (audio, SAMPLE_RATE)
        except Exception:
            pass
    return _cargar_con_wave(ruta)
def _estirar(audio, factor):
    """Cambia la duracion sin cambiar el tono, con OLA (overlap-add).

    factor > 1 alarga (mas lento), factor < 1 acorta (mas rapido). El tono
    no se toca porque las muestras siguen siendo las mismas: solo se
    reordenan y se cruzan.
    """
    if abs(factor - 1.0) < 0.001 or len(audio) < 100:
        return audio.astype(np.float32, copy=False)
    ventana = int(SAMPLE_RATE * VENTANA_MS / 1000)
    if ventana < 32:
        ventana = 32
    salto_sal = ventana // 2
    salto_ent = int(round(salto_sal / factor))
    if salto_ent < 1:
        salto_ent = 1
    n = len(audio)
    hann = np.hanning(ventana).astype(np.float32)
    largo_estimado = int(n * factor) + ventana
    salida = np.zeros(largo_estimado, dtype=np.float32)
    peso = np.zeros(largo_estimado, dtype=np.float32)
    i_ent = 0
    i_sal = 0
    while i_ent + ventana <= n and i_sal + ventana <= largo_estimado:
        trozo = audio[i_ent:i_ent + ventana] * hann
        salida[i_sal:i_sal + ventana] += trozo
        peso[i_sal:i_sal + ventana] += hann
        i_ent += salto_ent
        i_sal += salto_sal
    activo = peso > 1e-06
    salida[activo] /= peso[activo]
    return salida[:i_sal + salto_sal]
def _resample(audio, factor):
    """Recorre las muestras a paso \'factor\' — cambia tono y duracion juntos.\n\n    Es el efecto \"vinilo\": subir el factor sube el tono Y acorta el tiempo.\n    Se usa como base para los dos efectos publicos.\n    """
    if abs(factor - 1.0) < 0.001 or len(audio) < 2:
        return audio.astype(np.float32, copy=False)
    else:
        n_salida = max(1, int(round(len(audio) / factor)))
        posiciones = np.arange(n_salida, dtype=np.float32) * factor
        posiciones = np.clip(posiciones, 0, len(audio) - 1)
        return np.interp(posiciones, np.arange(len(audio)), audio).astype(np.float32)
def cambiar_tono(audio, semitonos):
    """Cambia el tono sin cambiar la duracion."""
    if abs(semitonos) < 0.01:
        return audio.astype(np.float32, copy=False)
    else:
        factor = 2 ** (semitonos / 12.0)
        return _estirar(_resample(audio, factor), factor)
def cambiar_velocidad(audio, factor):
    """Cambia la duracion sin cambiar el tono. 0.5 = mitad, 2.0 = doble."""
    if abs(factor - 1.0) < 0.001:
        return audio.astype(np.float32, copy=False)
    else:
        return _estirar(audio, 1.0 / factor)
def cambiar_volumen(audio, factor):
    """Multiplica la amplitud, con clipping suave para no distorsionar."""
    if abs(factor - 1.0) < 0.001:
        return audio.astype(np.float32, copy=False)
    else:
        escalado = audio * factor
        return np.tanh(escalado).astype(np.float32)
def procesar(audio, semitonos=0.0, velocidad=1.0, volumen=1.0):
    """Aplica los tres efectos en el orden que da mejor calidad."""
    salida = cambiar_tono(audio, semitonos)
    salida = cambiar_velocidad(salida, velocidad)
    salida = cambiar_volumen(salida, volumen)
    return salida
def a_wav_bytes(audio):
    """Convierte el array a bytes de un WAV mono 16 bit."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        pcm = np.clip(audio, (-1.0), 1.0) * 32767
        w.writeframes(pcm.astype(np.int16).tobytes())
    return buf.getvalue()
def guardar_wav(audio, destino):
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(a_wav_bytes(audio))
    return destino
class Reproductor:
    """Reproduce sonidos sin bloquear la ventana.\n\n    Todo pasa por un .wav temporal — antes intentabamos evitarlo en Windows\n    pasando los bytes en memoria (SND_MEMORY | SND_ASYNC), pero esa\n    combinacion no existe en la API de winsound moderna: devuelve \"Cannot\n    play asynchronously from memory\". Escribir a disco cuesta un ms y\n    funciona igual en los tres sistemas.\n\n    Cada llamada a reproducir() escribe un archivo NUEVO, aunque el anterior\n    siga sonando. Winsound reserva el archivo mientras suena, asi que borrar\n    el viejo puede fallar; se acumulan en una lista y se limpian al cerrar.\n    """
    def __init__(self):
        self._proceso = None
        self._temporales = []
    def _limpiar(self, agresivo=False):
        pendientes = []
        for p in self._temporales:
            try:
                p.unlink()
            except Exception:
                if not agresivo:
                    pendientes.append(p)
        self._temporales = pendientes
    def reproducir(self, audio):
        self.detener()
        self._limpiar()
        f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False, prefix='cinecaptions_sfx_')
        f.write(a_wav_bytes(audio))
        f.close()
        temp = Path(f.name)
        self._temporales.append(temp)
        if sys.platform.startswith('win'):
            import winsound
            winsound.PlaySound(str(temp), winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            if sys.platform == 'darwin':
                comando = ['afplay', str(temp)]
            else:
                if shutil.which('aplay'):
                    comando = ['aplay', '-q', str(temp)]
                else:
                    if shutil.which('paplay'):
                        comando = ['paplay', str(temp)]
                    else:
                        return None
            self._proceso = subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def detener(self):
        if sys.platform.startswith('win'):
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        if self._proceso is not None:
            try:
                self._proceso.terminate()
            except Exception:
                pass
            self._proceso = None
        self._limpiar(agresivo=True)
EXTENSIONES = {'.m4a', '.ogg', '.flac', '.mp3', '.wav', '.aiff', '.aif'}
def _sonidos_de(carpeta):
    if not carpeta.is_dir():
        return []
    return sorted([a for a in carpeta.iterdir()
                   if a.is_file() and a.suffix.lower() in EXTENSIONES])
def catalogo(carpeta_raiz, carpetas_extra=None):
    """Recorre la biblioteca y devuelve un dict {categoria: [ruta, ...]}.\n\n    Cada carpeta de primer nivel en sfx_library/ es una categoria — su\n    nombre se usa TAL CUAL (respetando mayusculas y espacios), sin prefijos\n    ni renombrados. Es la biblioteca del usuario, no la reorganizamos.\n\n    Las carpetas que el usuario agrega desde el estudio se agregan como\n    categorias mas, tambien con su nombre pelado.\n    """
    resultado = {}
    raiz = Path(carpeta_raiz)
    if raiz.is_dir():
        for sub in sorted(raiz.iterdir()):
            if sub.is_dir():
                audios = _sonidos_de(sub)
                if audios:
                    resultado[sub.name] = audios
    for extra in carpetas_extra or []:
        p = Path(extra)
        if not p.is_dir():
            continue
        else:
            audios = _sonidos_de(p)
            if audios and p.name not in resultado:
                    resultado[p.name] = audios
    return resultado
