# CineCaptions · By Cinema Productions
# 1_codigo/hacer_previas_efectos.py — herramienta de desarrollo: las vistas previas (mp4 + jpg) de la página «Efectos».
"""
hacer_previas_efectos.py  (v5.4.6)
----------------------------------
Cada efecto de la página «Efectos» enseña un mp4 corto de 270×480 con el efecto YA puesto sobre una foto de muestra (las de fondos_estilos):

    intro_<id>.mp4 / .jpg     la intro sobre una foto (se mezcla en «Screen», igual que en Resolve);
    corte_<id>.mp4 / .jpg     dos fotos con el corte a mitad y la transición encima;
    iconos_<pack>.mp4 / .jpg  los iconos animados (la misma secuencia que va a Resolve) sobre una foto.

    python hacer_previas_efectos.py [salida=2_recursos/efectos/previas]

Solo hace falta repetirlo si cambian los efectos o su animación.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import efectos_visuales as F

ANCHO, ALTO = 270, 480
FOTOS = ('fondo_03.jpg', 'fondo_07.jpg', 'fondo_01.jpg')


def _ffmpeg():
    return shutil.which('ffmpeg') or 'ffmpeg'


def _foto(k):
    return F.carpeta_efectos().parent / 'fondos_estilos' / FOTOS[k % len(FOTOS)]


def _correr(cmd):
    subprocess.run([_ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y'] + cmd, check=True)


def _poster(mp4, jpg, t):
    _correr(['-ss', str(t), '-i', str(mp4), '-frames:v', '1', '-q:v', '3', str(jpg)])


def hacer_intro(ident, salida):
    clip = F._clip('intro', ident, 'v')
    mp4 = salida / f'intro_{ident}.mp4'
    _correr(['-loop', '1', '-t', '2.2', '-i', str(_foto(0)), '-i', str(clip), '-filter_complex',
             f'[0:v]scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,crop={ANCHO}:{ALTO},fps=30,format=gbrp[bg];'
             f'[1:v]scale={ANCHO}:{ALTO},fps=30,format=gbrp,tpad=stop_mode=add:stop_duration=4:color=black[fx];[bg][fx]blend=all_mode=screen:shortest=1,format=yuv420p',
             '-an', '-t', '2.2', '-c:v', 'libx264', '-preset', 'slow', '-crf', '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(mp4)])
    _poster(mp4, salida / f'intro_{ident}.jpg', 0.4)


def hacer_corte(ident, salida):
    clip = F._clip('corte', ident, 'v')
    mp4 = salida / f'corte_{ident}.mp4'
    # la transición dura ~0.77 s con el punto de más luz a la mitad: arranca a 0.30 s y el corte entre las dos fotos cae en 0.68 s
    _correr(['-loop', '1', '-t', '0.68', '-i', str(_foto(1)), '-loop', '1', '-t', '1.7', '-i', str(_foto(2)), '-i', str(clip), '-filter_complex',
             f'[0:v]scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,crop={ANCHO}:{ALTO},fps=30,format=gbrp[a];'
             f'[1:v]scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,crop={ANCHO}:{ALTO},fps=30,format=gbrp[b];[a][b]concat=n=2:v=1:a=0[bg];'
             f'[2:v]scale={ANCHO}:{ALTO},fps=30,format=gbrp,tpad=start_mode=add:start_duration=0.30:color=black,tpad=stop_mode=add:stop_duration=4:color=black[fx];'
             f'[bg][fx]blend=all_mode=screen:shortest=1,format=yuv420p',
             '-an', '-t', '2.3', '-c:v', 'libx264', '-preset', 'slow', '-crf', '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(mp4)])
    _poster(mp4, salida / f'corte_{ident}.jpg', 0.6)


def _fotograma(k):
    from PIL import Image
    f = Image.open(_foto(k)).convert('RGB')
    esc = max(ANCHO / f.width, ALTO / f.height)
    f = f.resize((int(f.width * esc + 1), int(f.height * esc + 1)), Image.Resampling.LANCZOS)
    return f.crop(((f.width - ANCHO) // 2, (f.height - ALTO) // 2, (f.width - ANCHO) // 2 + ANCHO, (f.height - ALTO) // 2 + ALTO))


from vista_previa_fx import efecto_v1 as _efecto_v1                         # la misma aproximación en numpy que usa la vista previa de 3 s


def hacer_corte_v1(ident, salida):
    """Transición que mueve el video (zoom desenfocado, barrido, glitch): dos fotos con el corte a mitad y el efecto aplicado alrededor del corte."""
    import numpy as np
    A, B = np.asarray(_fotograma(1)), np.asarray(_fotograma(2))
    fps, total, corte, medio = 30, 69, 24, 5
    mp4 = salida / f'corte_{ident}.mp4'
    proc = subprocess.Popen([_ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{ANCHO}x{ALTO}', '-r', str(fps), '-i', '-', '-an',
                             '-c:v', 'libx264', '-preset', 'slow', '-crf', '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(mp4)], stdin=subprocess.PIPE)
    for f in range(total):
        base = A if f < corte else B
        u = max(0.0, 1.0 - abs(f - corte) / medio)
        proc.stdin.write(np.ascontiguousarray(_efecto_v1(ident, base, u, f < corte) if u > 0 else base).tobytes())
    proc.stdin.close()
    proc.wait()
    _poster(mp4, salida / f'corte_{ident}.jpg', corte / fps)


def hacer_iconos(pack, salida, k):
    from PIL import Image
    import numpy as np
    sec = F.secuencia_iconos(pack, 540, 960, 0)
    fondo = Image.open(_foto(k)).convert('RGB')
    esc = max(ANCHO / fondo.width, ALTO / fondo.height)
    fondo = fondo.resize((int(fondo.width * esc + 1), int(fondo.height * esc + 1)), Image.Resampling.LANCZOS)
    fondo = fondo.crop(((fondo.width - ANCHO) // 2, (fondo.height - ALTO) // 2, (fondo.width - ANCHO) // 2 + ANCHO, (fondo.height - ALTO) // 2 + ALTO)).convert('RGBA')
    mp4 = salida / f'iconos_{pack}.mp4'
    proc = subprocess.Popen([_ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{ANCHO}x{ALTO}', '-r', '30', '-i', '-', '-an',
                             '-c:v', 'libx264', '-preset', 'slow', '-crf', '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(mp4)], stdin=subprocess.PIPE)
    for f in range(1, sec['n'] + 1):
        fr = Image.open(sec['patron'] % f).convert('RGBA').resize((ANCHO, ALTO), Image.Resampling.LANCZOS)
        base = fondo.copy()
        base.alpha_composite(fr)
        proc.stdin.write(np.asarray(base.convert('RGB')).tobytes())
    proc.stdin.close()
    proc.wait()
    _poster(mp4, salida / f'iconos_{pack}.jpg', 1.5)


if __name__ == '__main__':
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else F.carpeta_efectos() / 'previas'
    salida.mkdir(parents=True, exist_ok=True)
    for ident, _n, _d in F.INTROS:
        hacer_intro(ident, salida)
    for ident, _n, _d in F.TRANSICIONES:
        (hacer_corte_v1 if ident in F.TRANSICIONES_V1 else hacer_corte)(ident, salida)
    for k, (pack, _n, _d) in enumerate(F.PACKS_ICONOS):
        hacer_iconos(pack, salida, k)
    print('previas listas en', salida, [p.name for p in sorted(salida.iterdir())])
