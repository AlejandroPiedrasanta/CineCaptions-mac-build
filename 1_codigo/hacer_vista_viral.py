# CineCaptions · By Cinema Productions
# 1_codigo/hacer_vista_viral.py — genera la vista previa INCLUIDA del estilo «VIRAL» (los fotogramas que enseña la tarjeta del slider de Estilos).
"""
Uso:  python hacer_vista_viral.py

Coloca unas frases de muestra con el planificador real (viral_planificador: una pila y los tres efectos —shatter, select, drag—) en el timeline temporal zz_BANCO de
Resolve, sobre NEGRO (la tarjeta compone los fotogramas en modo Screen sobre una foto), lo renderiza y guarda 5 fotogramas reducidos en
2_recursos/plantillas_incluidas/VIRAL/vista/ (+ indice.json con la caja del texto). El pack los lleva incluidos: la tarjeta se ve sin necesitar Resolve
(vistas_reales.cacheadas los lee). Repetir cada vez que cambie el aspecto de los elementos (pack_viral.py) y subir plantillas.REVISION_BIN['VIRAL'].
CUIDADO: toca el Resolve del usuario (timeline temporal zz_BANCO): comprobar el proyecto abierto; termina con banco_pruebas.limpiar().
"""
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / '2_recursos' / 'generador_packs'))
import ajustes_ui

ajustes_ui.guardar_prefs = lambda *a, **k: None          # los arneses ensucian las prefs reales

DESTINO = AQUI.parent / '2_recursos' / 'plantillas_incluidas' / 'VIRAL' / 'vista'
ALTO = 540
# frases de muestra (4 bloques seguidos): pila → shatter → select → drag; cada palabra entra 0,3 s después de la anterior
FRASES = [('Mira esta casa increíble', 0.10), ('Ahora viene lo mejor', 2.30), ('Selecciona lo que quieras', 4.80), ('Arrastra tu mejor idea', 7.60)]


def palabras_de_muestra():
    pal = []
    for frase, t0 in FRASES:
        for k, w in enumerate(frase.split()):
            pal.append({'word': w, 'start': round(t0 + 0.30 * k, 2), 'end': round(t0 + 0.30 * k + 0.26, 2)})
    return pal


def main():
    import banco_pruebas
    import vistas_reales
    import viral_planificador
    from PIL import Image
    import av
    pal = palabras_de_muestra()
    res = viral_planificador.planificar(pal, idioma='es', ancla='medio', fin_video=10.4, efectos={1: 'v shatter', 2: 'v select', 3: 'v drag'}, mains=['mejor', 'selecciona', 'arrastra'])
    print(viral_planificador.resumen(res))
    cues = res['cues']
    tiempos = []
    for c in cues:                                         # una foto por bloque en el momento más vistoso + una segunda de la pila
        if c['plantilla'] in ('v shatter', 'v select', 'v drag'):
            h = next(r['t'] for r in c['runs'] if r['k'] == c['plantilla'])
            tiempos.append(min(h + {'v shatter': 0.55, 'v select': 1.0, 'v drag': 0.72}[c['plantilla']], c['end'] - 0.3))
        else:
            tiempos.append(c['end'] - 0.35)
    tiempos.append(cues[-1]['end'] - 0.15)
    print('tiempos:', [round(t, 2) for t in tiempos])
    ruta = None
    try:
        print('banco:', banco_pruebas.preparar(audio=None, color=(0, 0, 0), frames=340, renovar=('VIRAL',)))
        ok, msg = banco_pruebas.colocar_viral(cues)
        print('colocar:', 'OK' if ok else 'FALLO', str(msg)[-500:])
        if ok:
            ruta = banco_pruebas.renderizar('viral_vista')
            print('render:', ruta)
    finally:
        print('limpiar:', banco_pruebas.limpiar())
    if not ruta:
        return
    DESTINO.mkdir(parents=True, exist_ok=True)
    for viejo in DESTINO.glob('*'):
        viejo.unlink()
    c = av.open(str(ruta))
    s = c.streams.video[0]
    originales, nombres = [], []
    for k, t in enumerate(tiempos):
        c.seek(int(t / s.time_base), stream=s, backward=True)
        for f in c.decode(s):
            if f.time is not None and f.time >= t:
                im = f.to_image().convert('RGB')
                originales.append(im)
                chico = im.resize((round(im.width * ALTO / im.height), ALTO), Image.LANCZOS)
                nombre = f'vir_{k:02d}.jpg'
                chico.save(DESTINO / nombre, quality=88)
                nombres.append(nombre)
                break
    tmp = DESTINO.parent / '_originales'
    tmp.mkdir(exist_ok=True)
    rutas = []
    for k, im in enumerate(originales):
        r = tmp / f'o{k}.png'
        im.save(r)
        rutas.append(str(r))
    caja = vistas_reales._caja_del_texto(rutas)
    for r in rutas:
        Path(r).unlink()
    tmp.rmdir()
    (DESTINO / 'indice.json').write_text(json.dumps({'sets': {'1': nombres}, 'recortes': {'1': caja} if caja else {}, 'ancho_alto': [originales[0].width, originales[0].height]},
                                                    ensure_ascii=False, indent=1), encoding='utf-8')
    print('vista:', DESTINO, nombres, caja)


if __name__ == '__main__':
    main()
