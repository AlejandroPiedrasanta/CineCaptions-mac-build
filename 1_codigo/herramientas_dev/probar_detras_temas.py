"""v5.31 (el usuario: «con la PRO activa, en cualquier tema del 1 al 6 que se aplique correctamente… testea con más videos, solo humanos, nada de
artefactos raros… que “detrás de ti” esté perfecto en cualquier video»): «Captions detrás de ti» de punta a punta SIN Resolve, por tema y por video.

Para cada video (ya transcrito por GO: la caché de la voz) y cada tema:
  1. los captions DEL TEMA (Tema 1: los clips neón del kit + la placa con sus zooms; 2–6: el planificador de cada pack, escritos en un
     manifiesto como los deja GO, y edicion_pro._bloques_captions los lee igual que en GO);
  2. la regla de GO (edicion_pro._captions_detras) en automático y con las 3 sugerencias de Efectos › Posición marcadas («solo»): lo que la
     tira sugiere como «queda bien» TIENE que entrar;
  3. el matte de la IA (edicion_pro._encima_de → edicion_pro_persona.mascara_guardada) y lo que se mide de él: ProRes con alfa, islas sueltas
     (manchas que no son la persona), franja semitransparente (halo), parpadeo entre fotogramas, que no tape el cuadro entero;
  4. la vista de cada tramo COMO QUEDA (fotograma + caption subido con su Tilt + la persona del matte encima, con su recorte de abajo) en una
     hoja por video y tema, para mirarla.

    python probar_detras_temas.py <carpeta_salida> <video> [<video> …] [--temas=1,2,3,4,5,6] [--sin-mascara] [--kit] [--auto]

No toca Resolve ni las preferencias reales (se parchean); las máscaras van a <salida>/mascaras (se reutilizan entre pasadas)."""
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PACKS = {1: 'Kinetic', 2: 'Referencia', 3: 'VIRAL', 4: 'Tema4', 5: 'Tema5', 6: 'Tema6'}
W, H = 1080, 1920
OKS, FALLOS, AVISOS = [], [], []


def comprobar(cond, texto, aviso=False):
    (OKS if cond else (AVISOS if aviso else FALLOS)).append(texto)
    print(('  OK    ' if cond else ('  AVISO ' if aviso else '  FALLO ')) + texto, flush=True)
    return cond


def _fotogramas_mov(ruta, indices):
    """{índice: RGBA uint8} de un .mov (en orden, sin seek: los recortes son cortos)."""
    import av
    quiero, out = set(indices), {}
    with av.open(str(ruta)) as c:
        for i, fr in enumerate(c.decode(c.streams.video[0])):
            if i in quiero:
                out[i] = fr.to_ndarray(format='rgba')
            if i >= max(quiero):
                break
    return out


def _encajar(img, w, h):
    """Como GO pone V1 («ajustado»): el video entero dentro de w×h, centrado (bandas negras si no es de la misma proporción)."""
    import numpy as np
    from PIL import Image
    ih, iw = img.shape[:2]
    k = min(w / float(iw), h / float(ih))
    nw, nh = max(1, int(round(iw * k))), max(1, int(round(ih * k)))
    modo = 'RGBA' if img.shape[2] == 4 else 'RGB'
    r = np.asarray(Image.fromarray(img, modo).resize((nw, nh), Image.LANCZOS))
    out = np.zeros((h, w, img.shape[2]), dtype=np.uint8)
    y0, x0 = (h - nh) // 2, (w - nw) // 2
    out[y0:y0 + nh, x0:x0 + nw] = r
    return out


def _lumas(fuente, t0, n, w, h):
    """La luma (suavizada) de n fotogramas de `fuente` desde el segundo t0, al tamaño del recorte."""
    import numpy as np
    import av
    from PIL import ImageFilter
    out = []
    with av.open(str(fuente)) as c:
        vs = c.streams.video[0]
        k0 = int(round(float(t0) * float(vs.average_rate or 30)))
        for i, fr in enumerate(c.decode(vs)):
            if i >= k0:
                img = fr.to_image().convert('L')
                out.append(np.asarray((img if img.size == (w, h) else img.resize((w, h))).filter(ImageFilter.GaussianBlur(2)), np.float32))
            if len(out) >= n:
                break
    return out


def medir_matte(ruta, fps, recorte_px=0, fuente=None, t0=0.0, diag=None, n_max=None):
    """Lo que delata un matte malo: islas (manchas sueltas que no son la persona), halo (franja semitransparente ancha), parpadeo.
    v5.58: solo lo que SE VE (por encima de `recorte_px`: «detrás de ti» recorta a la persona por debajo del caption: los pies, su sombra en el
    suelo y el hueco entre el brazo y la cintura no se ven) y el parpadeo de VERDAD: con `fuente` (el video del recorte, desde `t0`), el % del
    área de la persona cuyo alfa cambia donde la imagen está QUIETA, en el peor fotograma. Antes era la media del cambio donde no era fijo:
    con una persona que camina o mueve las manos daba 170-180 aunque el recorte estuviera bien (ESPAÑOL.mov, Tema 1)."""
    import numpy as np
    import av
    import edicion_pro_persona as PE
    with av.open(str(ruta)) as c:
        vs = c.streams.video[0]
        fmt = f'{vs.codec_context.name}/{vs.codec_context.pix_fmt}'
        alfas = [fr.to_ndarray(format='rgba')[..., 3].astype(np.float32) / 255.0 for fr in c.decode(vs)]
    if n_max:                                                          # (v5.58: el archivo lleva 0,1 s de más que Resolve no enseña)
        alfas = alfas[:int(n_max)]
    if not alfas:
        return {'fmt': fmt, 'n': 0}
    h, w = alfas[0].shape
    corte = h - max(0, min(h, int(recorte_px or 0)))
    for a in alfas:
        a[corte:] = 0.0
    lumas = _lumas(fuente, t0, len(alfas), w, h) if fuente else []
    islas, halo, cubre, parpadeo = 0, 0.0, 0.0, 0.0
    peor = None                                                        # (el fotograma del peor parpadeo y sus píxeles: para --diag)
    prev = None
    for i, a in enumerate(alfas):
        dura = a > 0.5
        area = dura.sum()
        cubre = max(cubre, area / float(a.size))
        if i % 6 == 0 and area:
            g = dura[::4, ::4]
            trozos = PE.componentes(g, minimo=max(2, int(0.0002 * g.size)))   # (de mayor a menor)
            if len(trozos) > 1:
                grande = float(trozos[0].sum())
                islas = max(islas, sum(1 for t in trozos[1:] if t.sum() < 0.08 * grande))
            halo = max(halo, float(((a > 0.04) & (a < 0.96)).sum()) / max(1.0, float(area)))
        if prev is not None and i < len(lumas):
            quieto = np.abs(lumas[i] - lumas[i - 1]) < 4.0
            quieto[corte:] = False
            malo = (np.abs(a - prev) > 0.3) & quieto
            p = 100.0 * float(malo.sum()) / max(1.0, float(area))
            if p > parpadeo:
                parpadeo, peor = p, (i, malo, a > 0.5)
        prev = a
    if diag and peor is not None:                                      # el peor fotograma: rojo = cambia con la imagen quieta; verde = la persona
        from PIL import Image
        i, malo, dentro = peor
        base = np.repeat(lumas[i][..., None], 3, axis=2).astype(np.uint8)
        base[dentro] = (base[dentro] * 0.5 + np.array([0, 110, 0])).astype(np.uint8)
        base[malo] = [255, 0, 0]
        base[corte:] = (base[corte:] * 0.35).astype(np.uint8)
        Image.fromarray(base).resize((w // 2, h // 2)).save(str(diag))
    return {'fmt': fmt, 'n': len(alfas), 'islas': islas, 'halo': round(halo, 3), 'cubre': round(cubre, 3), 'parpadeo': round(parpadeo, 2),
            'visible': round(corte / float(h), 2), 'peor': peor[0] if peor else None}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 2:
        print(__doc__)
        return 2
    temas = [1, 2, 3, 4, 5, 6]
    for a in sys.argv[1:]:
        if a.startswith('--temas'):
            temas = [int(x) for x in a.split('=', 1)[1].split(',')]
    sin_mascara = '--sin-mascara' in sys.argv
    salida = Path(args[0])
    salida.mkdir(parents=True, exist_ok=True)
    videos = [Path(v) for v in args[1:]]
    tmp = Path(tempfile.mkdtemp(prefix='ccdetras_temas_'))
    import ajustes_ui
    # (v5.58: con --kit, el Tema 1 también con «Kit de motions»: sus motions y la PLACA; sin él, como GO desde la 5.56: ni motions ni placa)
    PREFS = {'go_edicion_pro': True, 'pro_ia_local': False, 'pro_mascara': 'auto', 'pro_detras_intensidad': 'media',
             'pro_neon_extras': ['detras'] + (['kit'] if '--kit' in sys.argv else [])}
    real = ajustes_ui.leer_prefs
    ajustes_ui.leer_prefs = lambda: {**real(), **PREFS}
    ajustes_ui.guardar_prefs = lambda d=None, *x, **k: PREFS.update(d or {})
    if hasattr(ajustes_ui, 'mezclar_prefs'):
        ajustes_ui.mezclar_prefs = lambda d=None, *x, **k: PREFS.update(d or {})
    import registro
    REG = []
    for n in ('info', 'aviso', 'ok'):
        if hasattr(registro, n):
            setattr(registro, n, lambda texto, *a, _n=n, **k: REG.append((_n, str(texto))))
    registro.excepcion = lambda *a, **k: REG.append(('excepcion', repr(k)))
    import numpy as np
    from PIL import Image, ImageDraw
    import edicion_pro as EP
    import edicion_pro_persona as PE
    import efectos_visuales
    import kit_neon as KN
    import kit_neon_motions as KM
    import kit_neon_placa as PLA
    import posiciones_pro as POS
    import render_sin_resolve as RSR
    import vista_tema
    EP.en_juego = lambda: True                                       # (la PRO encendida: la tira usa los bloques del kit en el Tema 1)
    EP.PLAN_JSON = tmp / 'edicion_pro_plan.json'
    EP.DETRAS_CTX = tmp / 'detras_contexto.json'
    EP.CARPETA = salida / 'edicion_pro'                              # (las placas del Tema 1 se reutilizan entre pasadas)
    EP.MANIFIESTO = tmp / 'subtitles_manifest.json'
    PE.MASCARAS = salida / 'mascaras'
    POS.CACHE = salida / 'cache_posiciones'
    resumen = []
    for video in videos:
        if not video.is_file():
            comprobar(False, f'no encuentro {video}')
            continue
        w = POS._voz_de(str(video))
        if not w:
            comprobar(False, f'{video.name}: sin transcribir (pasa GO una vez)')
            continue
        vw, vh, dur, fps = EP.medir(str(video))
        idioma = POS._idioma_de(w)
        cortes = efectos_visuales.detectar_cortes(str(video)) or []
        print(f'\n######## {video.name}: {vw}x{vh} {dur:.1f} s {fps:.2f} fps · {len(w)} palabras ({idioma}) · {len(cortes)} cortes', flush=True)
        inicio = int(round(3600 * fps))
        info = {'fps': fps, 'ancho': W, 'alto': H, 'inicio': inicio, 'base': inicio, 'producto': 'DaVinci Resolve Studio', 'via': 'mcp',
                'nombre': f'CineCaptions · {video.stem}', 'ocupado': [],
                'v1': [{'ruta': str(video), 'ini': inicio, 'fin': inicio + int(round(dur * fps)), 'izq': 0, 'fps': fps, 'res': f'{vw}x{vh}',
                        'zx': 1.0, 'zy': 1.0, 'pan': 0.0, 'tilt': 0.0}]}
        an = POS.analizar_detras(str(video))
        for tema in temas:
            pack = PACKS[tema]
            print(f'== {video.name} · Tema {tema} ({pack})', flush=True)
            REG.clear()
            carpeta = EP.CARPETA / f'{video.stem}_{tema}'
            carpeta.mkdir(parents=True, exist_ok=True)
            neon = tema == 1
            plan = EP.planificar(str(video), w, dur, cortes=cortes, idioma=idioma, opciones=EP.opciones_guardadas(), tema='neon' if neon else None)
            ocupado = [(p['ini'] - 0.1, p['fin'] + 0.1) for p in plan['piezas'] if p['pieza'] != 'marco']
            estilo = vista_tema.estilo_de_pack(pack, 'v')
            placa, a_cuadro, cues = None, None, []
            t0 = time.time()
            if neon:
                plan['kitneon'] = KM.ajustar_captions(KN.escena_captions(w, idioma, fin_video=dur), plan.get('kitneon_motions') or [])
                plan['_neon_ajustado'] = True
                plan['duracion'] = dur
                bl = KN.bloques_pro(plan['kitneon'])
                ocupado += [(m['ini'] - 0.1, m['fin'] + 0.1) for m in plan.get('kitneon_motions') or []]
                if plan.get('kitneon_motions') is not None:            # (como GO: la placa solo con «Kit de motions»)
                    placa = PLA.para_pro(str(video), plan, carpeta, W, H, fps)
                    if not comprobar(placa is not None and Path(placa).is_file(), f'la placa del Tema 1 ({time.time() - t0:.0f} s)'):
                        continue
                    a_cuadro = PLA.mapa_camara(str(video), plan, W, H)
                else:
                    print('     Tema 1 sin «Kit de motions»: sin placa, la persona sale de V1 (como GO)', flush=True)
                cues = vista_tema.planificar(w, [], pack, estilo, idioma=idioma, fin_video=dur, video=str(video))
            else:
                cues = vista_tema.planificar(w, [], pack, estilo, idioma=idioma, fin_video=dur, video=str(video))
                datos = tmp / f'{video.stem}_{tema}.json'
                datos.write_text(json.dumps({'cues': cues}, ensure_ascii=False), encoding='utf-8')
                tipo = 'kinetic' if estilo.get('tipo') in ('kinetic', 'viral') else 'guion'
                EP.MANIFIESTO.write_text(json.dumps({'project': 'zz', 'tracks': [{'language': idioma, 'style': tipo, 'data_path': str(datos),
                                                                                    'plantilla': {'pack': pack}}]}), encoding='utf-8')
                bl = EP._bloques_captions()
            if not comprobar(len(bl) > 0, f'{len(bl)} bloques de captions del tema'):
                continue
            # (a) las sugerencias de la tira con ESTE tema
            POS.tema_de_inicio = lambda pack=pack: pack
            cap = POS.captions_del_video(str(video))
            zonas, _mot = POS.zonas_detras(an, POS.palabras(str(video)), POS.bloques_de(cap))
            t0 = time.time()
            reglas = POS.reglas_go(str(video), cap, analisis=an)           # (lo que hace la tira: cada sugerencia, comprobada con la regla de GO)
            comprobar(reglas is not None, f'la tira tiene la regla de GO de este tema ({len((reglas or {}).get("bloques") or [])} bloques)')
            sug = [t for t, _x in POS.sugerir_go(zonas, an, cap, reglas)]
            print(f'     sugerencias comprobadas en {time.time() - t0:.1f} s', flush=True)
            tr_sug = EP._captions_detras(info, str(video), fps, ocupado, 'media', lambda t: None, W=W, H=H, intensidad='media', bloques=bl,
                                         a_cuadro=a_cuadro, marcas={'modo': 'solo', 'ts': sug}, cortes=cortes)
            con = [t for t in sug if any(tr['ini'] - 0.7 <= t <= tr['fin'] + 0.7 for tr in tr_sug)]
            fuera = [x for _n, x in REG if 'detrás de ti» en' in x]
            comprobar(len(con) == len(sug), f'las {len(sug)} sugerencias de Posición ({sug}) entran en GO: {len(con)}'
                      + (f' · {fuera} · tramos {[(round(t["ini"], 1), round(t["fin"], 1)) for t in tr_sug]}' if len(con) != len(sug) else ''),
                      aviso=not sug)
            # (b) GO en automático
            EP._DETECCIONES.clear()                                    # (v5.58: medir la detección de verdad, sin lo que miró la tira)
            t_sel = time.time()
            tramos = EP._captions_detras(info, str(video), fps, ocupado, 'media', lambda t: None, W=W, H=H, intensidad='media', bloques=bl,
                                         a_cuadro=a_cuadro, marcas=None, cortes=cortes)
            print(f'     automático: {len(tramos)} tramos {[(round(t["ini"], 1), round(t["fin"], 1)) for t in tramos]} '
                  f'(elegidos en {time.time() - t_sel:.1f} s)', flush=True)
            usar = tramos if '--auto' in sys.argv else (tr_sug or tramos)     # (--auto: los tramos que GO elige solo, sin marcas)
            fila = {'video': video.name, 'tema': tema, 'bloques': len(bl), 'sugeridas': sug, 'entran': len(con), 'auto': len(tramos)}
            for tr in usar:
                for c in tr['cues']:
                    b = next(x for x in bl if abs(x['ini'] - c['ini']) < 0.3 or abs(x.get('ini_clip', x['ini']) - c['ini']) < 0.3)
                    arriba, abajo = b['arriba'] - c['subir'], b['abajo'] - c['subir']
                    comprobar(arriba >= 0.079 and abajo <= 0.901,
                              f'{c["ini"]:.1f} s: la pila queda dentro del cuadro ({arriba:.3f}–{abajo:.3f})')
            if sin_mascara or not usar:
                resumen.append(fila)
                continue
            # (c) el matte de la IA y lo que se mide
            t0 = time.time()
            n_reg = len(REG)
            encima = EP._encima_de(usar, info, str(video), fps, W, H, carpeta, a_cuadro, neon, None, False, placa=placa)
            t_m = time.time() - t0
            seg = sum(tr['fin'] - tr['ini'] for tr in usar)
            # v5.58: un tramo cuyo recorte no sale limpio lo quita a propósito el control de calidad de _encima_de (lo dice en el Registro):
            # eso es un AVISO con su % (mirar que sea un recorte malo de verdad); un tramo que falta sin ese motivo, un FALLO. Cada matte va
            # con SU tramo (por tiempo: si se quita uno del medio, zip los cruzaba)
            pares = [(e, min(usar, key=lambda tr: abs(tr['ini'] * fps - e['ini']))) for e in encima]
            quitados = [m for _, m in REG[n_reg:] if 'no salía limpio' in m]
            for tr in usar:
                if any(t_ is tr for _, t_ in pares):
                    continue
                motivo = next((m for m in quitados if f' en {float(tr["ini"]):.1f} s:' in m), None)
                comprobar(False, f'tramo {tr["ini"]:.1f}–{tr["fin"]:.1f} s sin la persona delante: '
                                 + (motivo or 'sin motivo (¿falló el recorte?)'), aviso=motivo is not None)
            comprobar(len(encima) + len(quitados) == len(usar),
                      f'{len(encima)} de {len(usar)} tramos con su matte ({len(quitados)} quitados por el control de calidad; '
                      f'{t_m:.0f} s para {seg:.1f} s de video)')
            fila.update(matte_s=round(t_m, 1), video_s=round(seg, 1), quitados=len(quitados))
            celdas = []
            for e, tr in pares:
                m = medir_matte(e['archivo'], fps, e.get('recorte_px'), placa if (neon and placa) else video, tr['ini'],
                                diag=salida / f'{video.stem}_T{tema}_parpadeo_{tr["ini"]:.1f}.png', n_max=e['fin'] - e['ini'])
                ok = ('prores' in m['fmt'] and 'a' in m['fmt'].split('/')[1] and m['n'] > 0 and m['islas'] == 0 and m['cubre'] < 0.7
                      and m['halo'] < 0.35)
                # (v5.58: parpadeo = % del área que cambia con la imagen quieta: el temblor del borde del pelo da ≤ 2,5; un trozo de fondo,
                # 12-24. Entre 3 y PE.PARPADEO_MAX GO lo deja: AVISO para mirar el peor fotograma —con solo la cabeza a la vista, el borde del
                # pelo ya da 4-5, PRUEBAS (4) a los 35 s—; por encima, GO lo habría quitado: FALLO)
                comprobar(ok and m['parpadeo'] < 3.0, f'matte {tr["ini"]:.1f}–{tr["fin"]:.1f} s: {m}',
                          aviso=ok and m['parpadeo'] <= PE.PARPADEO_MAX)
                fila.setdefault('mattes', []).append(m)
                # la vista: al medio del primer caption y al final del tramo
                for t in (tr['cues'][0]['ini'] + 0.6, tr['fin'] - 0.1):
                    t = max(tr['ini'], min(tr['fin'] - 0.04, t))
                    base = PE.fotograma(str(placa if (neon and placa) else video), t)
                    if base is None:
                        continue
                    base = _encajar(base, W, H)
                    k = int(round((t - tr['ini']) * fps))
                    fr = _fotogramas_mov(e['archivo'], [k]).get(k)
                    arr = base.copy()
                    c0 = min(e['cues'], key=lambda c: abs(c['ini'] / fps - t) if c['ini'] / fps <= t else 9e9)
                    subir = c0['subir']
                    cue = min(cues, key=lambda q: abs(float(q.get('start') or 0) - c0['ini'] / fps)) if cues else None
                    if cue is not None:
                        capas = [x for x in RSR.preparar([cue], W, H, estilo=estilo) if x.get('tipo') != 'emoji']
                        if capas and neon:                      # (Tema 1: el clip neón no se dibuja aquí; el caption del tema, a la altura del bloque)
                            b = min(bl, key=lambda x: abs(x['ini'] - c0['ini'] / fps))
                            fondo = max(x['y'] + x['a'].shape[0] for x in capas)
                            corr = int(round(b['abajo'] * H)) - fondo
                            for x in capas:
                                x['y'] += corr
                        for x in capas:
                            x['y'] -= int(round(subir))
                        RSR.componer(arr, capas, min(float(cue.get('end') or t) - 0.04, t + 0.4))
                    if fr is not None:
                        a = _encajar(fr, W, H) if fr.shape[:2] != (H, W) else fr
                        al = a[..., 3:4].astype(np.float32) / 255.0
                        if e.get('recorte_px'):
                            al[H - int(e['recorte_px']):] = 0.0
                        arr = (a[..., :3] * al + arr * (1 - al)).astype(np.uint8)
                    im = Image.fromarray(arr).resize((270, 480), Image.LANCZOS)
                    ImageDraw.Draw(im).text((6, 4), f'T{tema} {t:.1f}s', fill=(255, 255, 0))
                    celdas.append(im)
            if celdas:
                hoja = Image.new('RGB', (len(celdas) * 274, 484), (16, 16, 16))
                for i, im in enumerate(celdas):
                    hoja.paste(im, (i * 274 + 2, 2))
                hoja.save(salida / f'{video.stem}_T{tema}.jpg', quality=88)
            resumen.append(fila)
    (salida / 'resumen.json').write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\n{len(OKS)} OK · {len(AVISOS)} AVISO · {len(FALLOS)} FALLO', flush=True)
    for f in FALLOS:
        print('  FALLO', f)
    return 1 if FALLOS else 0


if __name__ == '__main__':
    sys.exit(main())
