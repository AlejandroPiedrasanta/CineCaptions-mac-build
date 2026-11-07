# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/hacer_base_t2.py — la previa del texto base del Estilo 2 de «Crea tu estilo» (2_recursos/guia_estilo/crea/b_t2.mp4).
"""
hacer_base_t2.py  (v5.76)
-------------------------
El usuario: «el Tema 2 tiene fallas, está demasiado rápido, y en texto base no debería cambiar de color, solo el principal». La previa que salía
del render real (hacer_vistas_crea.py, tramo 3) traía «videos» en azul y negrita y el apagado a gris del Estilo 2 (eso es su principal y su
atenuado, no su base) y duraba 2,36 s. La base es solo su LETRA (Poppins Light) en las líneas de arriba y abajo: aquí se dibuja así, en blanco fijo,
«Haz que tus» y «videos se vean» con un fundido suave una tras otra (subiendo 6 px), 3,12 s como las demás bases, 384×216 a 25 fps.

    python hacer_base_t2.py [salida.mp4]        (por defecto, la del programa)
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CODIGO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODIGO))
import fuentes_sistema

W, H, FPS, DUR = 384, 216, 25, 3.12
SS = 3                                              # supermuestreo (bordes suaves)
ANCHO_REF = 186.0                                   # ancho de «Haz que tus» en el render real (px a 384)
LINEAS = (('Haz que tus', 0.10, 0.45), ('videos se vean', 0.85, 0.45))     # (texto, entra a los s, dura el fundido)


def suave(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def hacer(salida):
    ruta = fuentes_sistema.ruta_de_fuente('Poppins', 'Light')
    if not ruta:
        raise SystemExit('falta la letra Poppins Light en el equipo')
    f100 = ImageFont.truetype(str(ruta), 100 * SS)
    fuente = ImageFont.truetype(str(ruta), int(round(100 * SS * ANCHO_REF * SS / f100.getlength('Haz que tus'))))
    asc, desc = fuente.getmetrics()
    alto_linea = int((asc + desc) * 1.02)
    y0 = (H * SS - alto_linea * len(LINEAS)) // 2
    proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16', '-preset', 'slow', '-movflags', '+faststart', str(salida)],
                            stdin=subprocess.PIPE)
    for k in range(int(round(DUR * FPS))):
        t = k / FPS
        lienzo = Image.new('L', (W * SS, H * SS), 0)
        d = ImageDraw.Draw(lienzo)
        for i, (texto, ini, dur) in enumerate(LINEAS):
            a = suave((t - ini) / dur)
            if a > 0:
                x = (W * SS - d.textlength(texto, font=fuente)) / 2
                d.text((x, y0 + i * alto_linea + (1 - a) * 6 * SS), texto, font=fuente, fill=int(round(255 * a)))
        proc.stdin.write(lienzo.resize((W, H), Image.LANCZOS).convert('RGB').tobytes())
    proc.stdin.close()
    return proc.wait() == 0


if __name__ == '__main__':
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else CODIGO.parent / '2_recursos' / 'guia_estilo' / 'crea' / 'b_t2.mp4'
    print('ok' if hacer(destino) else 'FALLO', destino)
