# CineCaptions · By Cinema Productions
# 2_recursos/generador_sfx_estilo/preparar_sonidos.py — prepara los sonidos que el usuario aportó para los estilos (riser de gancho, golpecito del iPhone, obturadores de transición).
"""
Uso:   python preparar_sonidos.py [carpeta con los originales]

Deja en el programa (nada se descarga; son los audios de la carpeta «GANCHOS VIRALES / 6-SONIDOS» del usuario):
  efectos/sonidos/viral_hooks_riser.mp3     el riser por defecto de la intro y del gancho (copia tal cual; el programa se queda con sus ÚLTIMOS 2 s, que acaban en el pico)
  sfx_library/Riser/Viral Hooks Riser.mp3   el mismo, para elegirlo en Sonido y como riser de «Introducción» del modo simple
  sfx_library/Modo simple/Iphone Taping.wav UN toque limpio del iPhone (el original dura 52 s), 3.ª variante del sonido por palabra
  sfx_library/Shutter/Shuter 11.wav, 13.wav los obturadores de cámara, sonido de las transiciones «destello» (página Efectos)
"""
import os
import shutil
import sys
import wave

AQUI = os.path.dirname(os.path.abspath(__file__))
RECURSOS = os.path.abspath(os.path.join(AQUI, '..'))
sys.path.insert(0, os.path.join(RECURSOS, '..', '1_codigo'))
# (herramienta del autor, no del programa: la carpeta de origen de los sonidos se cambia con CINECAPTIONS_ORIGEN_SONIDOS)
ORIGEN = os.environ.get('CINECAPTIONS_ORIGEN_SONIDOS') or r'E:\VFX-EDICION VIDEOS\PREMIER PRO\GANCHOS VIRALES\GANCHO VIRALES\6-SONIDOS'
RATE = 48000


def guardar_wav(ruta, a):
    import numpy as np
    pcm = (np.clip(a, -1.0, 1.0) * 32767.0).astype('<i2').T.copy()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with wave.open(ruta, 'wb') as w:
        w.setnchannels(a.shape[0])
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


def toque_limpio(ruta, largo_max=0.30):
    """El toque más limpio de una grabación de toques: el de mayor pico con silencio (< 4 % del pico) en los 0,25 s anteriores. Devuelve (audio estéreo, inicio_s)."""
    import numpy as np
    import efectos_visuales as E
    a = E._decodificar_audio(ruta, RATE)
    m = np.abs(a).max(axis=0)
    pico = float(m.max())
    paso = int(0.005 * RATE)
    env = np.array([m[i:i + paso].max() for i in range(0, len(m) - paso, paso)])
    mejor = None
    for i in range(50, len(env) - 1):
        if env[i] > pico * 0.5 and env[i - 1] < pico * 0.35 and env[i - 50:i - 1].max() < pico * 0.04:
            if mejor is None or env[i] > env[mejor]:
                mejor = i
    if mejor is None:
        raise SystemExit('no encontré un toque limpio')
    ini = max(0, mejor * paso - int(0.004 * RATE))
    # un toque de teclado del iPhone es un clic de ~10 ms con una cola finísima: se deja 0,12 s (clic + resonancia) con una salida suave de 30 ms
    fin = min(len(m), ini + int(min(largo_max, 0.12) * RATE))
    t = a[:, ini:fin].copy()
    f = min(int(0.030 * RATE), t.shape[1] // 3)
    t[:, -f:] *= np.linspace(1.0, 0.0, f, dtype=np.float32)
    t[:, :int(0.002 * RATE)] *= np.linspace(0.0, 1.0, int(0.002 * RATE), dtype=np.float32)
    return t, ini / RATE


def main():
    origen = sys.argv[1] if len(sys.argv) > 1 else ORIGEN
    lib = os.path.join(RECURSOS, 'sfx_library')
    riser = os.path.join(origen, 'Viral Hooks Riser.mp3')
    for destino in (os.path.join(RECURSOS, 'efectos', 'sonidos', 'viral_hooks_riser.mp3'), os.path.join(lib, 'Riser', 'Viral Hooks Riser.mp3')):
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        shutil.copyfile(riser, destino)
        print('copiado', destino)
    toque, t0 = toque_limpio(os.path.join(origen, 'Iphone Taping.mp3'))
    guardar_wav(os.path.join(lib, 'Modo simple', 'Iphone Taping.wav'), toque)
    print('toque del iPhone: %.3f s tomados desde %.3f s del original' % (toque.shape[1] / RATE, t0))
    for n in ('Shuter 11.wav', 'Shuter 13.wav'):
        destino = os.path.join(lib, 'Shutter', n)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        shutil.copyfile(os.path.join(origen, n), destino)
        print('copiado', destino)


if __name__ == '__main__':
    main()
