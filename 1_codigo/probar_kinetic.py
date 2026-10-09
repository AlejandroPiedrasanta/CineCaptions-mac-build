# CineCaptions · By Cinema Productions
# 1_codigo/probar_kinetic.py — prueba del estilo «Kinetic» de punta a punta: voz → bloques → Resolve (banco zz_BANCO) → render → hoja de cuadros.
"""
Uso:   python probar_kinetic.py [vista] [--fondo gris|video] [--ancla alto|medio|bajo] [--render nombre] [--sin-render] [--ruta-fondo video.mp4] [--res 2160x3840]

  vista        solo dibuja la maqueta de cada bloque con Pillow (kinetic_vista) en ~/DaVinciSubtitles/banco/vista_kinetic.png: sin Resolve
  --fondo      gris (por defecto: fondo liso, mide limpio) o video (el video de prueba detrás: lo que verá el usuario)
Necesita ~/DaVinciSubtitles/mcp/palabras_voz_kinetic.json (las palabras con tiempos de la voz de prueba). Si no existe, genera la voz con SAPI y avisa:
transcríbela con el MCP `transcribir` (o motor_voz) y guarda el .json ahí.
CUIDADO: toca el Resolve del usuario (timeline temporal zz_BANCO): comprobar el proyecto abierto y acabar con limpiar_banco.
"""
import json
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / '2_recursos' / 'generador_packs'))
import ajustes_ui

ajustes_ui.guardar_prefs = lambda *a, **k: None          # los arneses ensucian las prefs reales (memoria del proyecto)

CARPETA = Path.home() / 'DaVinciSubtitles' / 'banco'
PALABRAS = Path.home() / 'DaVinciSubtitles' / 'mcp' / 'palabras_voz_kinetic.json'
VOZ = CARPETA / 'voz_kinetic.wav'
VIDEO_PRUEBA = Path.home() / 'Desktop' / 'VIDEO PARA HACER PRUEBAS.mp4'
GUION = ('La gente te juzga en segundos, antes de que sepa quién eres. Sin un mensaje claro, no hay resultado. El juego se gana antes de empezar. '
         'Agrega subtítulos para conseguir más tiempo de reproducción. Regla número uno: sin gancho, no hay vistas. Si eres lento, la gente hace scroll. '
         'Enfócate en el gancho, no en el diseño. No los hagas pensar, hazlos sentir.')


def asegurar_voz():
    if VOZ.exists():
        return
    CARPETA.mkdir(parents=True, exist_ok=True)
    txt = CARPETA / 'guion_kinetic.txt'
    txt.write_text(GUION + '\n', encoding='utf-8')
    subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(AQUI / 'tts_prueba.ps1'), '-Salida', str(VOZ), '-Archivo', str(txt)], check=True)


def palabras():
    if not PALABRAS.exists():
        asegurar_voz()
        raise SystemExit(f'Falta {PALABRAS}: transcribe {VOZ} (MCP `transcribir`) y guarda las palabras ahí.')
    p = json.loads(PALABRAS.read_text(encoding='utf-8'))
    return p.get('palabras') or p.get('words') or p if isinstance(p, dict) else p


def planificar(ancla):
    import kinetic_planificador
    res = kinetic_planificador.planificar(palabras(), ancla=ancla)
    print(kinetic_planificador.resumen(res))
    return res


def vista(res):
    from PIL import Image, ImageDraw
    import kinetic_vista
    cues = res['cues']
    cols, w, h = 6, 270, 480
    hoja = Image.new('RGB', (cols * w, ((len(cues) + cols - 1) // cols) * h), (10, 10, 10))
    for k, c in enumerate(cues):
        im = kinetic_vista.dibujar_cue(c, 1080, 1920, fondo=(70, 70, 78)).resize((w, h))
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 150, 14), fill=(0, 0, 0))
        d.text((3, 2), f"{k} {c['plantilla']} {c['start']:.1f}-{c['end']:.1f}", fill=(255, 255, 0))
        hoja.paste(im, ((k % cols) * w, (k // cols) * h))
    ruta = CARPETA / 'vista_kinetic.png'
    CARPETA.mkdir(parents=True, exist_ok=True)
    hoja.save(ruta)
    print('vista:', ruta)


def main(argv):
    ancla = argv[argv.index('--ancla') + 1] if '--ancla' in argv else 'bajo'
    res = planificar(ancla)
    (CARPETA / 'cues_kinetic.json').write_text(json.dumps({'language': 'es', 'cues': res['cues']}, ensure_ascii=False, indent=1), encoding='utf-8') if CARPETA.exists() else None
    if 'vista' in argv:
        vista(res)
        return
    import banco_pruebas
    asegurar_voz()
    modo = argv[argv.index('--fondo') + 1] if '--fondo' in argv else 'gris'
    ruta_fondo = argv[argv.index('--ruta-fondo') + 1] if '--ruta-fondo' in argv else str(VIDEO_PRUEBA)
    fondo = ruta_fondo if modo == 'video' else None
    ancho, alto = (int(v) for v in argv[argv.index('--res') + 1].lower().split('x')) if '--res' in argv else (1080, 1920)
    print('banco:', banco_pruebas.preparar(audio=str(VOZ), fondo=fondo, color=(60, 60, 68), frames=860, ancho=ancho, alto=alto, renovar=('Referencia', 'Kinetic')))
    ok, msg = banco_pruebas.colocar_kinetic(res['cues'])
    print('colocar:', 'OK' if ok else 'FALLO', str(msg)[-800:])
    if '--sin-render' in argv or not ok:
        return
    nombre = argv[argv.index('--render') + 1] if '--render' in argv else 'kinetic'
    ruta = banco_pruebas.renderizar(nombre)
    print('render:', ruta)
    if ruta:
        tiempos = [round(c['end'] - 0.3, 2) for c in res['cues']][:16]
        print('hoja:', banco_pruebas.hoja(ruta, tiempos, str(CARPETA / f'hoja_{nombre}.png'), ancho=270, recorte=(0.2, 0.9), columnas=4))


if __name__ == '__main__':
    main(sys.argv[1:])
