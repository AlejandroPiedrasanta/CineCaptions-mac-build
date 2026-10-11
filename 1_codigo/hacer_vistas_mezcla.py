# CineCaptions · By Cinema Productions
# 1_codigo/hacer_vistas_mezcla.py — genera los CLIPS de 6 s de los looks de los Temas 1, 2 y 3 que se ven en «Crea tu estilo», renderizados por Resolve (captions reales).
"""
hacer_vistas_mezcla.py  (v5.4.30)
---------------------------------
Cada look de mezcla_planificador.catalogo() (6 de Tema 1, 8 de Tema 2, 4 de Tema 3) necesita un VIDEO de muestra con su animación real de entrada y de salida, como los 48 ejemplos de
Luxe (hacer_vistas_guia_video.py). Aquí se fabrican con el flujo REAL de la app, en UNA sola pasada:

  1. un video NEGRO de (18 × 6,5 s) con una transcripción inventada (una frase por look, separadas por una pausa larga: cada frase es un «tramo» de la mezcla);
  2. GO de la app sin pantalla con un pack de mezcla que lleva los 18 looks en orden (sin sonidos, emojis ni efectos visuales): proyecto nuevo de Resolve, timeline con el video negro y
     los captions colocados por el planificador de cada tema (la misma colocación que el usuario);
  3. Resolve RENDERIZA ese timeline (cola de render; por el Puente de Free: CineCaptions_Vista.lua, acciones «render» y «render_estado»);
  4. ffmpeg corta un mp4 de 6 s por look sobre fondo NEGRO (la galería lo mezcla en «Screen» sobre una foto) en 2_recursos/guia_estilo/mezcla/<id>.mp4.

    python hacer_vistas_mezcla.py [salida=2_recursos/guia_estilo/mezcla] [--ancho 304] [--crf 29] [--solo-plan] [--render <video ya renderizado>]

--solo-plan solo muestra el plan (sin Resolve). --render corta un render que ya existe (sin GO ni Resolve). Resolve no puede estar con un proyecto tuyo abierto: GO crea «CineCaptions N».
Se repite si cambian los planificadores, los packs o la frase de muestra.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

SEGUNDOS = 6.5                    # lo que dura el tramo de cada look en el timeline
CLIP_S = 6.0                      # lo que dura cada clip final
FRASE = [('Haz', 0.30, 0.55), ('que', 0.58, 0.78), ('tus', 0.80, 1.05), ('videos', 1.10, 1.60), ('se', 1.65, 1.85), ('vean', 1.90, 2.30), ('increíbles', 2.40, 3.60)]
PACK_NOMBRE = 'Mezcla de vistas'


def id_a_archivo(look_id):
    """'t1:lima' -> 't1_lima' (un nombre de archivo seguro)."""
    return look_id.replace(':', '_').replace(' ', '_')


def palabras_de_muestra(n):
    """Las palabras con tiempos del timeline: la frase de muestra repetida n veces, una cada SEGUNDOS."""
    pal = []
    for k in range(n):
        base = k * SEGUNDOS
        for texto, a, b in FRASE:
            pal.append({'word': texto, 'start': round(base + a, 3), 'end': round(base + b, 3)})
    return pal


def escribir_video_negro(ruta, segundos, ancho=1080, alto=1920, fps=30):
    ffmpeg = shutil.which('ffmpeg') or 'ffmpeg'
    cmd = [ffmpeg, '-y', '-f', 'lavfi', '-i', f'color=c=black:s={ancho}x{alto}:r={fps}', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', f'{segundos:.2f}',
           '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(ruta)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not Path(ruta).is_file():
        raise RuntimeError('ffmpeg no pudo hacer el video negro: ' + (r.stderr or '')[-300:])
    return ruta


def plan(looks):
    """El plan de la mezcla sobre las palabras de muestra: lo que se verá en cada tramo (para comprobar que cada frase cae en su look)."""
    import mezcla_planificador as mp
    pal = palabras_de_muestra(len(looks))
    res = mp.planificar(pal, looks, 'es', 1080, 1920, fin_video=len(looks) * SEGUNDOS)
    return pal, res


# ----------------------------------------------------------------------------------------------------------------------------- 2) GO sin pantalla
def _crear_pack_temporal(carpeta, looks):
    """El pack de mezcla con TODOS los looks, en una carpeta de packs de PRUEBA (no toca los del usuario). pack.json a mano: crear_pack() limita a MAX_LOOKS."""
    import archivos_seguros
    pack = Path(carpeta) / PACK_NOMBRE
    pack.mkdir(parents=True, exist_ok=True)
    archivos_seguros.escribir_json(pack / 'pack.json', {'version': 2, 'nombre': PACK_NOMBRE, 'guion': 'mezcla', 'looks': list(looks), 'formatos': {'v': {'mezcla': True}}}, indent=2)
    return pack


def resolve_colgado():
    """True si hay un Resolve abierto que «no responde» (Resolve Free se queda así tras muchos proyectos y renders: GO esperaría 4 min al Puente para nada). Solo Windows."""
    try:
        import ctypes
        import colocacion
        h = colocacion._hwnd_de_resolve()
        return bool(h and ctypes.windll.user32.IsHungAppWindow(h))
    except Exception:
        return False


def resolve_abierto():
    """True si hay un proceso de Resolve (colgado o no). Solo Windows."""
    try:
        import subprocess
        r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Resolve.exe', '/NH'], capture_output=True, text=True)
        return 'Resolve.exe' in (r.stdout or '')
    except Exception:
        return False


def cerrar_resolve(espera_s=60):
    """Le pide a Resolve que se cierre (guarda antes) —solo si su proyecto es de pruebas de CineCaptions— y espera a que el proceso termine. True si ya no hay Resolve."""
    if not resolve_abierto():
        return True
    if resolve_colgado():
        print('Resolve está colgado: no se puede cerrar desde aquí (ciérralo a mano).', flush=True)
        return False
    try:
        _orden_vista({'accion': 'cerrar'}, timeout=30)
    except Exception as exc:
        print('  (cerrar:', exc, ')', flush=True)
    t0 = time.time()
    while time.time() - t0 < espera_s:
        if not resolve_abierto():
            time.sleep(8)                                                    # (Windows tarda en soltar el puerto y los archivos de Resolve: una vuelta que empieza ya falla en 8 s)
            return True
        time.sleep(2)
    return not resolve_abierto()


def _go(video, palabras, carpeta_packs, tope_s=600, pack=PACK_NOMBRE, prefs_extra=None):
    """El botón GO de la app sin pantalla sobre el video negro (como probar_go.py --soltar), con la transcripción inventada, sin sonidos, emojis ni efectos visuales."""
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ.pop('CINECAPTIONS_SIN_MCP', None)
    os.chdir(AQUI)
    if resolve_colgado():
        print('Resolve está colgado («No responde»): ciérralo y vuelve a lanzar esto (GO esperaría 4 min al Puente).', flush=True)
        return False
    import importlib.util
    import faulthandler
    spec = importlib.util.spec_from_file_location('cc_main', str(AQUI / 'CineCaptions (script principal).py'))
    M = importlib.util.module_from_spec(spec)
    sys.modules['cc_main'] = M
    spec.loader.exec_module(M)
    import ajustes_ui
    import cache_voz
    import ia_texto
    import colocacion
    import licencia
    import plantillas
    import qt_kit
    licencia.vigente = lambda: True
    colocacion.reproducir_desde_inicio = lambda *a, **k: (True, 'sin reproducir')       # GO reproduce el timeline al terminar: con 70+ comps de Fusion y el render a la vez, Resolve Free se cierra solo
    M.SubtitleApp._revisar_licencia_al_arrancar = lambda s: None
    if carpeta_packs:
        plantillas.CARPETA_PACKS = Path(carpeta_packs)
        plantillas.invalidar_packs()
    real = ajustes_ui.leer_prefs
    ajustes_ui.leer_prefs = lambda: {**real(), 'plantilla': pack, 'go_pack': pack, 'go_sfx': False, 'go_emojis': False, 'go_efectos_visuales': False, **(prefs_extra or {})}
    ajustes_ui.guardar_prefs = lambda *a, **k: None                                       # NUNCA escribe las preferencias del usuario
    if (prefs_extra or {}).get('sfx_emojis') is False:
        import emojis_sfx
        emojis_sfx.activo = lambda: False                                                  # (esa preferencia vive en preferencias.json de Sonido, no en las prefs de la app)
    if hasattr(ajustes_ui, 'mezclar_prefs'):
        ajustes_ui.mezclar_prefs = lambda *a, **k: None
    import sfx_rules
    sfx_rules.guardar_modo = lambda *a, **k: None
    if palabras is not None:
        cache_voz.leer = lambda *a, **k: [dict(p) for p in palabras]                          # la transcripción inventada (no se transcribe un video negro)
        cache_voz.guardar = lambda *a, **k: False
        ia_texto.marcar_todo = lambda pal, *a, **k: ([dict(p) for p in pal], [None] * len(pal), {})        # sin IA de texto: las palabras tal cual y sin marcas (cada planificador elige solo)

    def _dialogo(tipo, titulo, texto, *a, **k):
        print(f'DIALOGO[{tipo}] {titulo}: {str(texto)[:300]!r}', flush=True)
        return True
    qt_kit.mostrar_mensaje = _dialogo
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    w = M.SubtitleApp()
    w._guardar_preferencias = lambda *a, **k: None
    w.plantilla_sel = pack
    w.show()
    faulthandler.dump_traceback_later(tope_s + 120, exit=True)
    print(f'GO sobre {Path(video).name} con el pack «{pack}»…', flush=True)
    w._soltar_archivo(str(video))
    t0 = time.time()
    while not getattr(w, '_go_corriendo', False) and time.time() - t0 < 15:
        app.processEvents()
        time.sleep(0.05)
    t0 = time.time()
    while getattr(w, '_go_corriendo', False) and time.time() - t0 < tope_s:
        app.processEvents()
        time.sleep(0.05)
    for _ in range(40):
        app.processEvents()
        time.sleep(0.05)
    faulthandler.cancel_dump_traceback_later()
    gp = getattr(w, 'go_panel', None)
    estado = getattr(getattr(gp, 'boton', None), 'estado', '?')
    print('GO terminado en %.0f s · corriendo=%s · estado=%s · paso_fallido=%r' % (time.time() - t0, getattr(w, '_go_corriendo', None), estado, getattr(gp, 'paso_fallido', None)), flush=True)
    return (not getattr(w, '_go_corriendo', False)) and estado == 'hecho'


# ----------------------------------------------------------------------------------------------------------------------------- 3) render por el Puente de Free
def _orden_vista(orden, timeout=90):
    """Una orden a CineCaptions_Vista.lua por el Puente. Devuelve (ok, vista) con lo que Resolve contestó (el campo «vista» del reporte) o (False, texto de error)."""
    import archivos_seguros
    import resolve_bridge
    import sidecar_lua
    ruta = resolve_bridge.CARPETA_COMPARTIDA / 'vista_orden.json'
    archivos_seguros.escribir_json(ruta, orden)
    sidecar_lua.escribir_sidecar(ruta, orden)
    desde = time.time()
    ok, msg = resolve_bridge.ejecutar('vista', timeout=timeout)
    rep = resolve_bridge.ultimo_reporte(desde=desde) or {}
    vista = rep.get('vista')
    if not ok:
        return False, str(msg)
    return True, vista if isinstance(vista, dict) else {}


def _renderizar(destino, nombre='vistas_mezcla', ancho=540, alto=960, tope_s=900, desde_s=None, hasta_s=None, sin_avance_s=120):
    """Manda el timeline actual de Resolve (todo, o el tramo desde_s..hasta_s) a la cola de render, espera a que termine y devuelve la ruta del video.
    Si el avance no se mueve en `sin_avance_s` segundos, para el render (Resolve Free a veces se queda quieto) y avisa."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    for viejo in destino.glob(nombre + '.*'):
        try:
            viejo.unlink()
        except OSError:
            pass
    orden = {'accion': 'render', 'destino': str(destino), 'nombre': nombre, 'ancho': ancho, 'alto': alto}
    if hasta_s is not None:
        orden.update({'desde_s': float(desde_s or 0), 'hasta_s': float(hasta_s)})
    ok, r = _orden_vista(orden)
    if not ok or not r.get('job'):
        raise RuntimeError(f'Resolve no empezó a renderizar: {r}')
    job = r['job']
    print(f'Render empezado (trabajo {job[:8]}…, timeline «{r.get("timeline")}»)', flush=True)
    t0 = time.time()
    ultimo, cambio = None, time.time()
    while time.time() - t0 < tope_s:
        time.sleep(8)
        ok, e = _orden_vista({'accion': 'render_estado', 'job': job}, timeout=60)
        if not ok:
            print('  (sin respuesta del Puente: ' + str(e)[:120] + ')', flush=True)
            continue
        txt = f"{e.get('estado')} {e.get('avance')}%"
        if txt != ultimo:
            print('  render:', txt, flush=True)
            ultimo, cambio = txt, time.time()
        elif e.get('en_curso') and time.time() - cambio > sin_avance_s:
            _orden_vista({'accion': 'render_parar', 'destino': str(destino)}, timeout=60)
            raise RuntimeError(f'El render se quedó quieto en «{txt}» más de {sin_avance_s} s: lo paré.')
        if not e.get('en_curso') and str(e.get('estado')) in ('Complete', 'Failed', 'Cancelled'):
            if e.get('estado') != 'Complete':
                raise RuntimeError(f'El render terminó como {e.get("estado")}.')
            break
    else:
        raise RuntimeError('El render pasó del tiempo máximo.')
    salida = next(iter(sorted(destino.glob(nombre + '.*'))), None)
    if salida is None:
        raise RuntimeError('Resolve dijo que terminó, pero no hay archivo en ' + str(destino))
    time.sleep(2)
    return salida


# ----------------------------------------------------------------------------------------------------------------------------- 4) cortar
def _duracion(ruta):
    r = subprocess.run([shutil.which('ffprobe') or 'ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(ruta)], capture_output=True, text=True)
    try:
        return float((r.stdout or '').strip())
    except ValueError:
        return 0.0


def cortar(render, looks, salida, ancho=304, crf=29, desfase=None):
    """Un mp4 de CLIP_S s por look (sin audio, sobre negro) en `salida`/<id>.mp4. Devuelve cuántos hizo. `desfase` = segundos del render donde empieza el primer look (con un render por tramos, 0);
    sin él, el look k empieza en k × SEGUNDOS (un render de todo el timeline)."""
    ffmpeg = shutil.which('ffmpeg') or 'ffmpeg'
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    hechos = 0
    for k, look in enumerate(looks):
        destino = salida / (id_a_archivo(look) + '.mp4')
        inicio = k * SEGUNDOS if desfase is None else desfase + k * SEGUNDOS
        cmd = [ffmpeg, '-y', '-ss', f'{inicio:.3f}', '-t', f'{CLIP_S:.3f}', '-i', str(render), '-an', '-vf', f'scale={int(ancho)}:-2:flags=lanczos', '-c:v', 'libx264', '-preset', 'slow',
               '-crf', str(crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(destino)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and destino.is_file() and destino.stat().st_size > 1000:
            hechos += 1
        else:
            print(f'  {look}: ffmpeg falló: ' + (r.stderr or '')[-200:], flush=True)
    return hechos


def _por_temas(looks, trabajo, salida, ancho=304, crf=29):
    """Renderiza el timeline por TRAMOS (un tema cada vez: Resolve Free se atasca a veces con un render largo y con 70+ comps) y corta los clips de cada uno. Devuelve el código de salida."""
    grupos = {}
    for k, look in enumerate(looks):
        grupos.setdefault(look.split(':')[0], []).append((k, look))
    hechos = 0
    for tema, items in grupos.items():
        k0, k1 = items[0][0], items[-1][0] + 1
        print(f'== {tema}: looks {k0}-{k1 - 1}', flush=True)
        try:
            r = _renderizar(trabajo / 'render', nombre=f'tramo_{tema}', desde_s=k0 * SEGUNDOS, hasta_s=k1 * SEGUNDOS)
        except Exception as exc:
            print(f'   falló: {exc}', flush=True)
            continue
        print(f'   render {r.name}: {_duracion(r):.1f} s (esperado {(k1 - k0) * SEGUNDOS:.1f} s)', flush=True)
        hechos += cortar(r, [l for _k, l in items], salida, ancho=ancho, crf=crf, desfase=0.0)
    print(f'{hechos} de {len(looks)} clips en {salida}', flush=True)
    return 0 if hechos == len(looks) else 4


def main():
    argv = sys.argv[1:]
    import mezcla_planificador as mp
    looks = [l['id'] for l in mp.catalogo()]
    if '--solo-plan' in argv:
        pal, res = plan(looks)
        print(mp.resumen(res))
        for motor, c in res['orden']:
            claves = [str(r.get('k') or r.get('rol')) for r in c.get('runs', [])]
            print(f"  {motor:7s} {c['start']:7.2f}-{c['end']:7.2f}  tramo {int(c['start'] // SEGUNDOS):2d}  {claves[:6]}")
        return 0
    valores = {argv[i + 1] for i, a in enumerate(argv) if a in ('--ancho', '--crf', '--render') and i + 1 < len(argv)}
    pos = [a for a in argv if not a.startswith('--') and a not in valores]
    salida = Path(pos[0]) if pos else AQUI.parent / '2_recursos' / 'guia_estilo' / 'mezcla'
    ancho = int(argv[argv.index('--ancho') + 1]) if '--ancho' in argv else 304
    crf = int(argv[argv.index('--crf') + 1]) if '--crf' in argv else 29
    trabajo = Path.home() / 'DaVinciSubtitles' / 'vistas_mezcla'
    trabajo.mkdir(parents=True, exist_ok=True)
    if '--render' in argv:                                                   # solo cortar un render COMPLETO que ya existe
        render = Path(argv[argv.index('--render') + 1])
        dur = _duracion(render)
        print(f'Render: {render} · {dur:.1f} s (esperado {len(looks) * SEGUNDOS:.1f} s)', flush=True)
        if dur < len(looks) * SEGUNDOS - 2:
            print('El render salió más corto de lo esperado: no se corta.', flush=True)
            return 3
        hechos = cortar(render, looks, salida, ancho=ancho, crf=crf)
        print(f'{hechos} de {len(looks)} clips en {salida}', flush=True)
        return 0 if hechos == len(looks) else 4
    if '--solo-render' not in argv:                                          # (con --solo-render Resolve ya tiene el timeline de la corrida anterior)
        n = len(looks)
        video = escribir_video_negro(trabajo / 'negro_vistas.mp4', n * SEGUNDOS + 1.0)
        palabras = palabras_de_muestra(n)
        packs = Path(tempfile.mkdtemp(prefix='cc_vistas_packs_'))
        _crear_pack_temporal(packs, looks)
        if not _go(video, palabras, packs):
            print('GO no terminó bien: no se renderiza.', flush=True)
            return 2
        time.sleep(10)                                                       # (que Resolve termine de asentar el timeline antes de pedirle el render)
    import instalador_scripts
    instalador_scripts.instalar_scripts_en_resolve(forzar=True)
    ok_p, r_p = _orden_vista({'accion': 'render_parar', 'destino': str(trabajo / 'render')}, timeout=60)      # (un render atascado de antes se para y se quita de la cola)
    print('render anterior parado:', ok_p, r_p, flush=True)
    return _por_temas(looks, trabajo, salida, ancho, crf)


if __name__ == '__main__':
    sys.exit(main())
