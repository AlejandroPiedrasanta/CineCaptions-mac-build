# CineCaptions · By Cinema Productions
# 1_codigo/hacer_vista_kinetic.py — genera la vista previa INCLUIDA del estilo «Kinetic» (los fotogramas que enseña la tarjeta del slider de Estilos).
"""
Uso:  python hacer_vista_kinetic.py

Coloca un bloque de muestra con el planificador real (kinetic_planificador) en el timeline temporal zz_BANCO de Resolve, sobre NEGRO (la tarjeta
compone los fotogramas en modo Screen sobre una foto), lo renderiza y guarda 5 fotogramas reducidos en 2_recursos/plantillas_incluidas/Kinetic/vista/
(+ indice.json con la caja del texto). El pack los lleva incluidos: la tarjeta se ve sin necesitar Resolve (vistas_reales.cacheadas los lee).
Repetir cada vez que cambie el aspecto de los elementos (pack_kinetic.py) y subir plantillas.REVISION_BIN['Kinetic'].
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

DESTINO = AQUI.parent / '2_recursos' / 'plantillas_incluidas' / 'Kinetic' / 'vista'
# «La gente te juzga en segundos»: héroe lima con subrayado, dos líneas pequeñas que lo anuncian
MUESTRA = [('La', 0.15), ('gente', 0.40), ('te', 0.70), ('juzga', 0.85), ('en', 1.15), ('segundos', 1.35)]
# cuándo se hace cada fotograma (s desde el inicio del timeline): las líneas entran, el héroe rebota y se asienta
TIEMPOS = (0.45, 0.90, 1.40, 1.60, 1.78)
ALTO = 540


def main():
    import banco_pruebas
    import kinetic_planificador
    import vistas_reales
    from PIL import Image
    import av
    palabras = [{'word': w, 'start': t, 'end': t + 0.28} for w, t in MUESTRA]
    res = kinetic_planificador.planificar(palabras, ancla='medio', fin_video=3.4)
    print(kinetic_planificador.resumen(res))
    print('banco:', banco_pruebas.preparar(audio=None, color=(0, 0, 0), frames=150, renovar=('Referencia', 'Kinetic')))
    try:
        ok, msg = banco_pruebas.colocar_kinetic(res['cues'])
        print('colocar:', 'OK' if ok else 'FALLO', str(msg)[-500:])
        if not ok:
            return
        ruta = banco_pruebas.renderizar('kin_vista')
        print('render:', ruta)
    finally:
        print('limpiar:', banco_pruebas.limpiar())
    DESTINO.mkdir(parents=True, exist_ok=True)
    for viejo in DESTINO.glob('*'):
        viejo.unlink()
    c = av.open(str(ruta))
    s = c.streams.video[0]
    originales, nombres = [], []
    for k, t in enumerate(TIEMPOS):
        c.seek(int(t / s.time_base), stream=s, backward=True)
        for f in c.decode(s):
            if f.time is not None and f.time >= t:
                im = f.to_image().convert('RGB')
                originales.append(im)
                chico = im.resize((round(im.width * ALTO / im.height), ALTO), Image.LANCZOS)
                nombre = f'kin_{k:02d}.jpg'
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
