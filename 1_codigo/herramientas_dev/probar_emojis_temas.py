# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_emojis_temas.py — GO solo con emojis por tema + render de los primeros segundos + hoja de fotogramas donde hay emoji (posición y animación). SOLO desarrollo (no entra en el .exe; necesita Resolve abierto y es seguro con el del usuario solo si él lo autoriza: ver memoria «resolve-uso-paralelo»).
"""Emojis de cada tema en Resolve REAL: GO (solo emojis) + render de los primeros segundos + fotogramas donde hay emoji, en una hoja.
python probar_emojis_temas.py <video> <vertical:1|0> <pack> [<pack>...]"""
import json, os, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import hacer_vistas_mezcla as H
from PIL import Image

SP = Path.home() / 'DaVinciSubtitles' / 'pruebas_emojis'
SP.mkdir(parents=True, exist_ok=True)
video, vertical = sys.argv[1], sys.argv[2] == '1'
paquetes = sys.argv[3:]
DS = Path.home() / 'DaVinciSubtitles'

for pack in paquetes:
    t0 = time.time()
    extra = {'go_emojis': True, 'go_sfx': False, 'go_efectos_visuales': False, 'go_vertical': vertical}
    ok = H._go(video, None, None, pack=pack, prefs_extra=extra, tope_s=300)
    print(f'##### {pack}: GO {"ok" if ok else "FALLO"} ({time.time() - t0:.0f} s)', flush=True)
    if not ok:
        break
    # los emojis del bloque: el JSON de datos más reciente que traiga cues con emoji
    cues = []
    for f in sorted(DS.glob('*.json'), key=os.path.getmtime, reverse=True)[:12]:
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        c = [x for x in (d.get('cues') or []) if isinstance(x, dict) and x.get('emoji')] if isinstance(d, dict) else []
        if c:
            cues = c
            break
    tiempos = [round(float(c.get('emoji_ini') if c.get('emoji_ini') is not None else c.get('start') or 0) + 0.6, 2) for c in cues][:4]
    print('   emojis en', tiempos, flush=True)
    hasta = (max(tiempos) + 1.5) if tiempos else 8.0
    r = H._renderizar(SP, nombre=f'e_{pack}', ancho=540, alto=960 if vertical else 304, desde_s=0, hasta_s=hasta, tope_s=500)
    print('   render', r, flush=True)
    imgs = []
    for t in tiempos or [2.0]:
        out = SP / f'{pack}_{t}.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', str(r), '-frames:v', '1', str(out)])
        if out.is_file():
            imgs.append(Image.open(out).convert('RGB'))
    if imgs:
        w, h = imgs[0].size
        hoja = Image.new('RGB', (w * len(imgs), h))
        for i, im in enumerate(imgs):
            hoja.paste(im, (i * w, 0))
        hoja.save(SP / f'hoja_{pack}.png')
        print('   hoja', SP / f'hoja_{pack}.png', hoja.size, flush=True)
