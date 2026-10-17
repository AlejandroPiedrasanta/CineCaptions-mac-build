# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_vista_creativo.py — banco de la vista EXACTA del tema en Creativo (vista_tema.py) contra lo que recibió y pintó Resolve.
"""
Sin Resolve ni pantalla. Usa los ejemplos REALES del slider: ~/DaVinciSubtitles/ejemplo_<tema>.marcas.json (palabras y marcas), los cues que GO mandó a
Resolve (ejemplo_<tema>.<idioma>.<guion|kinetic>.json) y los renders de Resolve (2_recursos/vistas_slider/<tema>_captions.mp4).

    A · planificación   el planificador de HOY con esas palabras = los cues que recibió Resolve (texto, rol/clip, x, y, zoom/size, tiempos)
    B · dibujo          los cues de Resolve dibujados por la vista de Creativo, al lado del fotograma real de Resolve en el mismo instante,
                        y una medida de alineación: diferencia de color dentro de la tinta dibujada frente a la misma tinta desplazada
    C · Principal       marcar como Principal otra palabra de un bloque (como en Creativo) la convierte en LA palabra grande de ese bloque en el tema

    python probar_vista_creativo.py <carpeta de salida> [Kinetic,Referencia,VIRAL,Tema4,Tema5,Tema6]
Sale 0 si A y C pasan en todos (B es para mirar la hoja: los renders llevan la Edición PRO encima); deja informe.txt y una hoja PNG por tema y parte.
"""
import json
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AQUI))
os.chdir(AQUI)
sys.stdout.reconfigure(encoding='utf-8')

import ajustes_ui                       # noqa: E402
ajustes_ui.guardar_prefs = lambda *a, **k: None          # (las prefs REALES del usuario no se tocan)

import av                               # noqa: E402
import numpy as np                      # noqa: E402
from PIL import Image, ImageDraw        # noqa: E402

import guion_editor                     # noqa: E402
import render_sin_resolve as RSR        # noqa: E402
import vista_tema as VT                 # noqa: E402

CASA = Path(os.path.expanduser('~')) / 'DaVinciSubtitles'
VISTAS = AQUI.parent / '2_recursos' / 'vistas_slider'
SUFIJO = {'Kinetic': 'kinetic', 'VIRAL': 'kinetic', 'Referencia': 'guion', 'Tema4': 'guion', 'Tema5': 'guion', 'Tema6': 'guion'}
TOL_XY, TOL_T = 0.003, 0.03


def cargar(pack):
    m = json.loads((CASA / f'ejemplo_{pack}.marcas.json').read_text(encoding='utf-8'))
    ruta = next(iter(sorted(CASA.glob(f'ejemplo_{pack}.*.{SUFIJO[pack]}.json'), key=lambda p: p.stat().st_mtime, reverse=True)), None)
    d = json.loads(ruta.read_text(encoding='utf-8'))
    idioma = ruta.name.split('.')[1]
    return m['words'], m['roles'], d['cues'], idioma, ruta


def duracion(ruta):
    with av.open(str(ruta)) as c:
        return float(c.duration / av.time_base)


def planificar_como_go(palabras, roles, pack, idioma, fin_video):
    """Como GO (_generar_con_guion / _generar_con_kinetic con _un_clic): el tema decide solo."""
    est = VT.estilo_de_pack(pack)
    if est['tipo'] == 'guion':
        ancla = str(ajustes_ui.leer_prefs().get('guion_ancla', 'medio'))
        return guion_editor.planear(palabras, roles, pack, ancla=ancla, fin_video=fin_video, idioma=idioma, automatico=True)['cues']
    if est['tipo'] == 'viral':
        import viral_planificador as kp
        return kp.planificar(palabras, idioma=idioma, ancho_tl=1080, alto_tl=1920, ancla=str(ajustes_ui.leer_prefs().get('viral_ancla', 'bajo')),
                             mains=None, fin_video=fin_video)['cues']
    import kinetic_planificador as kp
    return kp.planificar(palabras, idioma=idioma, ancla=str(ajustes_ui.leer_prefs().get('kinetic_ancla', 'bajo')), mains=None, fin_video=fin_video)['cues']


def comparar_cues(a, b):
    """Diferencias entre dos listas de cues (las que importan para el dibujo)."""
    dif = []
    if len(a) != len(b):
        dif.append(f'nº de bloques {len(a)} ≠ {len(b)}')
    for i, (x, y) in enumerate(zip(a, b)):
        for k in ('start', 'end'):
            if abs(float(x.get(k) or 0) - float(y.get(k) or 0)) > TOL_T:
                dif.append(f'bloque {i} {k} {x.get(k)} ≠ {y.get(k)}')
        ra, rb = x.get('runs') or [], y.get('runs') or []
        if len(ra) != len(rb):
            dif.append(f'bloque {i}: {len(ra)} ≠ {len(rb)} elementos')
            continue
        for j, (p, q) in enumerate(zip(ra, rb)):
            for k in ('texto', 'rol', 'k', 'estilo'):
                if p.get(k) != q.get(k):
                    dif.append(f'bloque {i} elem {j} {k} «{p.get(k)}» ≠ «{q.get(k)}»')
            for k in ('x', 'y', 'zoom', 'size'):
                if isinstance(p.get(k), (int, float)) and isinstance(q.get(k), (int, float)) and abs(p[k] - q[k]) > TOL_XY:
                    dif.append(f'bloque {i} elem {j} {k} {p[k]} ≠ {q[k]}')
            if abs(float(p.get('t') or 0) - float(q.get('t') or 0)) > TOL_T:
                dif.append(f'bloque {i} elem {j} t {p.get("t")} ≠ {q.get("t")}')
    return dif


def fotograma(ruta, t):
    with av.open(str(ruta)) as c:
        s = c.streams.video[0]
        c.seek(max(0, int((t - 1.0) / s.time_base)), stream=s, backward=True)
        ultimo = None
        for f in c.decode(s):
            ultimo = f
            if f.time is not None and f.time >= t - 0.5 / float(s.average_rate):
                break
        return np.asarray(ultimo.to_image().convert('RGB'))


def tinta(capas, t, alto, ancho):
    """(rgb dibujado sobre negro, alfa 0..1) de las capas visibles en t."""
    rgb = np.zeros((alto, ancho, 3), np.float32)
    alfa = np.zeros((alto, ancho), np.float32)
    for c in capas:
        k = RSR._fuerza(c, t)
        if k <= 0:
            continue
        h, w = c['a'].shape[:2]
        x0, y0 = max(0, c['x']), max(0, c['y'])
        x1, y1 = min(ancho, c['x'] + w), min(alto, c['y'] + h)
        if x1 <= x0 or y1 <= y0:
            continue
        a = c['a'][y0 - c['y']:y1 - c['y'], x0 - c['x']:x1 - c['x'], 0] * k
        rgb[y0:y1, x0:x1] += (c['rgb'][y0 - c['y']:y1 - c['y'], x0 - c['x']:x1 - c['x']] - rgb[y0:y1, x0:x1]) * a[..., None]
        alfa[y0:y1, x0:x1] = np.maximum(alfa[y0:y1, x0:x1], a)
    return rgb, alfa


def alineacion(real, rgb, alfa, desplazar=0):
    """Diferencia media de color (0..255) entre el fotograma real y lo dibujado, dentro de la tinta (alfa > 0,85), con la tinta movida `desplazar` px."""
    m = alfa > 0.85
    if desplazar:
        m = np.roll(m, desplazar, axis=1)
        rgb = np.roll(rgb, desplazar, axis=1)
    if m.sum() < 30:
        return None
    return float(np.abs(real.astype(np.float32)[m] - rgb[m]).mean())


def referencia(pack, ruta_cues):
    """(render de Resolve hecho con ESOS cues, casa): el .mov del banco si es posterior a los cues (la misma pasada de GO); si no, el ejemplo del
    slider (otra pasada: los estilos elegidos pueden ser otros, solo orientativo)."""
    mov = CASA / 'banco' / f'slider_{pack}.mov'
    if mov.exists() and mov.stat().st_mtime >= ruta_cues.stat().st_mtime:
        return mov, True
    return VISTAS / f'{pack}_captions.mp4', False


def parte_b(pack, cues, salida, ruta):
    """Fotograma de Resolve | la vista de Creativo con esos cues | contorno de lo dibujado encima del real. Devuelve las puntuaciones."""
    est = VT.estilo_de_pack(pack)
    ancho, alto = 540, 960
    cu = VT.Cuadros(cues, est, ancho, alto)
    ks = sorted({max(0, min(len(cues) - 1, int(len(cues) * f))) for f in (0.2, 0.45, 0.7, 0.9)})
    filas, notas = [], []
    for k in ks:
        t = cu.instante_quieto(k)
        real = np.asarray(Image.fromarray(fotograma(ruta, t)).resize((ancho, alto), Image.LANCZOS))
        rgb, alfa = tinta(cu.capas, t, alto, ancho)
        dentro, fuera = alineacion(real, rgb, alfa), alineacion(real, rgb, alfa, desplazar=max(8, ancho // 30))
        notas.append((round(t, 2), dentro, fuera))
        nuestro = (real.astype(np.float32) * 0.35)
        nuestro += (rgb - nuestro) * alfa[..., None]
        borde = Image.fromarray(real.copy())
        contorno = (alfa > 0.5).astype(np.uint8)
        filo = (contorno ^ np.roll(contorno, 1, 0)) | (contorno ^ np.roll(contorno, 1, 1))
        arr = np.asarray(borde).copy()
        arr[filo > 0] = (255, 40, 40)
        fila = Image.new('RGB', (ancho * 3 + 20, alto), (14, 14, 22))
        fila.paste(Image.fromarray(real), (0, 0))
        fila.paste(Image.fromarray(np.clip(nuestro, 0, 255).astype(np.uint8)), (ancho + 10, 0))
        fila.paste(Image.fromarray(arr), (2 * ancho + 20, 0))
        d = ImageDraw.Draw(fila)
        d.text((6, 6), f'Resolve  t={t:.2f}', fill=(255, 255, 0))
        d.text((ancho + 16, 6), 'Creativo', fill=(255, 255, 0))
        d.text((2 * ancho + 26, 6), 'contorno de Creativo sobre Resolve', fill=(255, 255, 0))
        filas.append(fila)
    hoja = Image.new('RGB', (filas[0].width, sum(f.height for f in filas) + 10 * len(filas)), (14, 14, 22))
    y = 0
    for f in filas:
        hoja.paste(f, (0, y))
        y += f.height + 10
    hoja = hoja.resize((hoja.width // 2, hoja.height // 2))
    hoja.save(salida / f'B_{pack}.png')
    return notas


def es_principal(pack, cue, i_run):
    r = cue['runs'][i_run]
    tipo = VT.estilo_de_pack(pack)['tipo']
    if tipo == 'guion':
        return r.get('rol') == 'main'
    # Temas 1 y 3: el héroe del bloque es la línea con rol «main» del cue (el clip cambia con la receta: k hero, k serif, k script, k tapes…)
    mains = [str(l.get('text') or '').lower() for l in cue.get('lines') or [] if l.get('role') == 'main']
    if mains:
        return any(str(r.get('texto') or '').lower() in m or m in str(r.get('texto') or '').lower() for m in mains if m)
    tam = [float(x.get('size') or 0) for x in cue['runs']]
    return float(r.get('size') or 0) >= max(tam) - 1e-6


def parte_c(pack, palabras, roles, idioma, fin_video, salida):
    """Marca como Principal (como en Creativo) una palabra que el tema NO eligió y mira que sea la grande de su bloque; y cómo se ve antes/después."""
    est = VT.estilo_de_pack(pack)
    roles = list(roles)
    antes = VT.planificar(palabras, roles, pack, est, idioma=idioma, fin_video=fin_video)
    resultados, imgs = [], []
    probados = 0
    for k in range(1, len(antes) - 1):
        c = antes[k]
        a, b = float(c['start']), float(c['end'])
        idx = [i for i, w in enumerate(palabras) if a <= float(w['start']) < b]
        grandes = {str(r.get('texto') or '').lower() for j, r in enumerate(c.get('runs') or []) if es_principal(pack, c, j)}
        cand = [i for i in idx if len(str(palabras[i]['word']).strip('.,¡!¿?')) >= 4
                and str(palabras[i]['word']).strip('.,¡!¿?').lower() not in ' '.join(grandes)]
        if not cand:
            continue
        i = max(cand, key=lambda j: len(palabras[j]['word']))
        nuevos = list(roles)
        for j in set(idx) | set(range(max(0, i - 4), min(len(nuevos), i + 5))):   # la Principal pasa a la palabra elegida (sin otra marcada al lado:
            if nuevos[j] == 'main':                                               # dos seguidas son UNA palabra grande en los temas «guion»)
                nuevos[j] = None
        nuevos[i] = 'main'
        despues = VT.planificar(palabras, nuevos, pack, est, idioma=idioma, fin_video=fin_video)
        palabra = str(palabras[i]['word']).strip('.,¡!¿?').lower()
        t = float(palabras[i]['start'])
        k_cue = VT.cue_de_palabra(despues, palabras[i]['word'], t)            # (el mismo bloque que enseña Creativo al tocar la palabra)
        cue = despues[k_cue] if k_cue is not None else None
        ok = False
        if cue is not None:
            for j, r in enumerate(cue.get('runs') or []):
                if palabra in str(r.get('texto') or '').lower() and es_principal(pack, cue, j):
                    ok = True
        resultados.append((palabras[i]['word'], ok))
        if len(imgs) < 2:
            for cues_, nombre in ((antes, 'antes'), (despues, f'Principal = «{palabras[i]["word"]}»')):
                cu = VT.Cuadros(cues_, est, 270, 585)
                im = Image.fromarray(cu.cuadro_array(cu.instante_quieto(cu.cue_de_palabra(palabras[i]['word'], t))))
                ImageDraw.Draw(im).text((6, 6), nombre, fill=(255, 255, 0))
                imgs.append(im)
        probados += 1
        if probados >= 4:
            break
    if imgs:
        hoja = Image.new('RGB', (sum(im.width + 8 for im in imgs), imgs[0].height), (14, 14, 22))
        x = 0
        for im in imgs:
            hoja.paste(im, (x, 0))
            x += im.width + 8
        hoja.save(salida / f'C_{pack}.png')
    return resultados


def main():
    salida = Path(sys.argv[1])
    salida.mkdir(parents=True, exist_ok=True)
    packs = sys.argv[2].split(',') if len(sys.argv) > 2 else ['Kinetic', 'Referencia', 'VIRAL', 'Tema4', 'Tema5', 'Tema6']
    informe, fallos = [], 0
    for pack in packs:
        palabras, roles, cues_resolve, idioma, ruta_cues = cargar(pack)
        fin_video = duracion(VISTAS / f'{pack}_captions.mp4')
        informe.append(f'## {pack} (Tema {list(VT.plantillas.FABRICA).index(pack) + 1}) · {len(palabras)} palabras · {len(cues_resolve)} bloques · {ruta_cues.name}')
        # A
        hoy = planificar_como_go(palabras, roles, pack, idioma, fin_video)
        dif = comparar_cues(hoy, cues_resolve)
        informe.append(f'  A planificación: {"OK, idéntica a lo que recibió Resolve" if not dif else f"{len(dif)} diferencias"}')
        informe += ['     ' + d for d in dif[:8]]
        fallos += bool(dif)
        # B
        ruta_ref, casa = referencia(pack, ruta_cues)
        notas = parte_b(pack, cues_resolve, salida, ruta_ref)
        malas = [n for n in notas if n[1] is not None and n[2] is not None and n[1] > 0.75 * n[2]]
        informe.append(f'  B dibujo vs Resolve ({ruta_ref.name}{"" if casa else ", OTRA pasada: solo orientativo"}): '
                       + '  '.join(f't={t}: dentro {d:.0f} / desplazado {f:.0f}' if d is not None and f is not None else f't={t}: sin tinta'
                                   for t, d, f in notas) + ('  → OK' if not malas else f'  → {len(malas)} instantes a revisar en B_{pack}.png'))
        # (B no hace fallar el banco: los renders del slider llevan la Edición PRO —captions que esquivan caras, motions encima—; se revisa la hoja)
        # C
        res = parte_c(pack, palabras, roles, idioma, fin_video, salida)
        malos = [w for w, ok in res if not ok]
        informe.append(f'  C Principal: {len(res) - len(malos)}/{len(res)} palabras marcadas salen como la grande del bloque' + (f'  ✗ {malos}' if malos else '  → OK'))
        fallos += bool(malos) or not res
        print('\n'.join(informe[-4:]), flush=True)
    (salida / 'informe.txt').write_text('\n'.join(informe) + '\n', encoding='utf-8')
    print(f'\nFALLOS: {fallos}  ->  {salida / "informe.txt"}', flush=True)
    sys.exit(1 if fallos else 0)


if __name__ == '__main__':
    main()
