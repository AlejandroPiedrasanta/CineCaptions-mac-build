# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/verificar_mac.py — v5.87 (el usuario: «verifica que no haya errores en Mac y que funcionen todas las opciones»):
# todo el programa sin pantalla en una Mac de verdad (las de GitHub: .github/workflows/verificar_mac.yml) o aquí, y un resumen OK/FALLA.
"""
python verificar_mac.py <carpeta de salida> [--solo simular,humo,opciones,go,premiere]

  simular   simular_equipos.py --rapido (los casos de cada equipo, también los de Mac y Premiere)
  humo      probar_ventanas_humo.py: cada página y cada ventana del programa se abre sin error
  opciones  la ventana principal sin pantalla: cada página y las 5 pestañas de Ajustes; cada interruptor y casilla se enciende y se apaga
            (ida y vuelta, sin guardar las preferencias): ninguna excepción ni error en el Registro
  go        GO con «Video sin editores» y cada uno de los 9 estilos (voz fija, sin IA) sobre un video de prueba hecho aquí: el MP4 sale
  premiere  GO con «Usar con Premiere Pro» y un Premiere FALSO (premiere_falso.js con el colocar.jsx real; Node): textos editables
            (con una plantilla «Basic Title» de mentira, hecha aquí) y la capa de video

Escribe <salida>/resumen.txt y un registro por parte; sale con 1 si algo falla. En una Mac de GitHub (variable CI) instala letras y el
panel de Premiere de verdad (es una máquina de usar y tirar); en un equipo de alguien, NUNCA: carpeta de usuario temporal y todo eso anulado.
"""
import base64
import gzip
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path

CODIGO = Path(__file__).resolve().parent.parent
HERR = Path(__file__).resolve().parent
EN_CI = bool(os.environ.get('CI'))
ESTILOS = ('Kinetic', 'Referencia', 'VIRAL', 'Tema4', 'Tema5', 'Tema6', 'Tema7', 'Tema8', 'Tema9')
PALABRAS = ('hola bienvenidos a esta prueba de captions en mac con todos los estilos del programa y sus sonidos '
            'esto tiene que salir perfecto sin errores ni avisos raros').split()


# ------------------------------------------------------------------------------------------------------------------ lo común
def entorno_aislado(carpeta):
    """En un equipo de verdad (no CI), la carpeta de usuario es una temporal: prefs, Registro, caché y salidas no son las del usuario."""
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['CINECAPTIONS_SIN_MCP'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    if not EN_CI:
        casa = Path(carpeta) / 'casa'
        casa.mkdir(parents=True, exist_ok=True)
        env['HOME'] = env['USERPROFILE'] = str(casa)
        env['CINECAPTIONS_PREMIERE_EXT'] = str(casa / 'extensiones_cep')
    return env


def video_de_prueba(ruta, segundos=8.0, ancho=720, alto=1280, fps=30):
    """Un MP4 vertical con color que cambia y un tono (PyAV, el de CineCaptions): no hace falta ningún video de fuera."""
    import av
    import numpy as np
    ruta = Path(ruta)
    if ruta.is_file():
        return ruta
    with av.open(str(ruta), 'w') as cont:
        v = None
        for codec in ('libx264', 'h264_videotoolbox', 'h264', 'mpeg4'):
            try:
                v = cont.add_stream(codec, rate=fps)
                break
            except Exception:
                v = None
        v.width, v.height, v.pix_fmt = ancho, alto, 'yuv420p'
        a = cont.add_stream('aac', rate=48000)
        a.layout = 'stereo'
        n = int(segundos * fps)
        for i in range(n):
            img = np.zeros((alto, ancho, 3), dtype=np.uint8)
            img[..., 0] = 40 + (i * 2) % 120
            img[..., 1] = 60
            img[..., 2] = 110
            for pk in v.encode(av.VideoFrame.from_ndarray(img, format='rgb24')):
                cont.mux(pk)
        for pk in v.encode():
            cont.mux(pk)
        muestras = int(segundos * 48000)
        t = np.arange(muestras) / 48000.0
        onda = (0.15 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
        estereo = np.vstack([onda, onda])
        paso = 1024
        for k in range(0, muestras, paso):
            fr = av.AudioFrame.from_ndarray(np.ascontiguousarray(estereo[:, k:k + paso]), format='fltp', layout='stereo')
            fr.sample_rate = 48000
            fr.pts = k
            for pk in a.encode(fr):
                cont.mux(pk)
        for pk in a.encode():
            cont.mux(pk)
    return ruta


def plantilla_falsa(app):
    """Una «Basic Title.mogrt» de MENTIRA (no es la de Adobe): la misma estructura que lee premiere_textos (definition.json + project.prgraphic
    con el «Texto de origen» en base64 = 8 bytes de largo + JSON en UTF-16), dentro de una «.app» de Premiere falsa."""
    ruta = Path(app) / 'Contents' / 'Essential Graphics' / 'Basic Title.mogrt'
    if ruta.is_file():
        return ruta
    ruta.parent.mkdir(parents=True, exist_ok=True)
    uno = lambda v: {'mParamValues': [[0, v]]}           # noqa: E731
    js = {'mTextParam': {'mAlignment': 2, 'mDefaultRun': [], 'mHeight': 0, 'mShadowVisible': False, 'mShadowColor': 0, 'mShadowOpacity': 75,
                         'mShadowAngle': 135, 'mShadowOffset': 7, 'mShadowBlur': 40, 'mShadowSize': 0, 'mWidth': 0,
                         'mStyleSheet': {'mText': 'Your Title Here', 'mFontName': uno('MyriadPro-Regular'), 'mFontSize': uno(100),
                                         'mFillColor': uno(16777215), 'mFillVisible': uno(True), 'mStrokeVisible': uno(False),
                                         'mStrokeWidth': uno(1), 'mStrokeColor': uno(16777215), 'mTracking': uno(0), 'mFauxItalic': uno(False)}}}
    datos = json.dumps(js).encode('utf-16-le')
    valor = base64.b64encode(struct.pack('<Q', len(datos)) + datos).decode('ascii')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<PremiereData Version="3">\n<Param><Name>Source Text</Name>\n'
           f'<StartKeyframeValue Encoding="base64" BinaryHash="0">{valor}\n\t\t</StartKeyframeValue>\n</Param>\n'
           '<InstanceName>Your Title Here</InstanceName>\n</PremiereData>\n')
    interior = io.BytesIO()
    with zipfile.ZipFile(interior, 'w', zipfile.ZIP_DEFLATED) as zi:
        zi.writestr('proyecto_falso.prproj', gzip.compress(xml.encode('utf-8')))
    with zipfile.ZipFile(ruta, 'w', zipfile.ZIP_DEFLATED) as zo:
        zo.writestr('definition.json', json.dumps({'capsuleID': '0', 'capsuleName': 'Basic Title', 'clientControls': []}))
        zo.writestr('project.prgraphic', interior.getvalue())
    return ruta


class Resumen:
    def __init__(self, carpeta):
        self.carpeta = Path(carpeta)
        self.lineas = []
        self.fallos = 0

    def anotar(self, ok, parte, texto):
        marca = 'OK   ' if ok is True else ('AVISO' if ok is None else 'FALLA')
        if ok is False:
            self.fallos += 1
        linea = f'{marca} [{parte}] {texto}'
        self.lineas.append(linea)
        print(linea, flush=True)

    def guardar(self):
        (self.carpeta / 'resumen.txt').write_text('\n'.join(self.lineas) + f'\n\n{self.fallos} fallos\n', encoding='utf-8')


def correr(cmd, log, env, tope_s):
    t0 = time.time()
    with open(log, 'w', encoding='utf-8', errors='replace') as f:
        try:
            p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=str(CODIGO), timeout=tope_s)
            codigo = p.returncode
        except subprocess.TimeoutExpired:
            codigo = 'tope'
    return codigo, time.time() - t0, Path(log).read_text(encoding='utf-8', errors='replace')


# ------------------------------------------------------------------------------------------------------------------ las partes
def parte_simular(R, salida, env):
    codigo, seg, txt = correr([sys.executable, str(HERR / 'simular_equipos.py'), '--rapido'], salida / 'simular.txt', env, 1800)
    final = [l for l in txt.splitlines() if 'casos ·' in l]
    fallas = [l.strip() for l in txt.splitlines() if l.strip().startswith('FALLA')]
    R.anotar(codigo == 0 and not fallas, 'simular', (final[-1].strip() if final else f'sin final (código {codigo})') +
             (' · ' + ' | '.join(fallas[:8]) if fallas else '') + f' · {seg:.0f} s')


def parte_humo(R, salida, env):
    codigo, seg, txt = correr([sys.executable, str(HERR / 'probar_ventanas_humo.py'), str(salida / 'humo_huella.txt')],
                              salida / 'humo.txt', env, 600)
    huella = (salida / 'humo_huella.txt').read_text(encoding='utf-8', errors='replace') if (salida / 'humo_huella.txt').is_file() else ''
    fallos = [l for l in huella.splitlines() if 'FALLO' in l]
    R.anotar(codigo == 0 and huella != '' and not fallos, 'humo',
             f'{huella.count("## ")} ventanas y páginas · {len(fallos)} fallos' + (' · ' + ' | '.join(fallos[:6]) if fallos else '') +
             (f' · código {codigo}' if codigo != 0 else '') + f' · {seg:.0f} s')


def parte_opciones(R, salida, env):
    codigo, seg, txt = correr([sys.executable, str(Path(__file__)), '--opciones', str(salida)], salida / 'opciones.txt', env, 900)
    res = [l for l in txt.splitlines() if l.startswith('RESULTADO_OPCIONES ')]
    if not res:
        R.anotar(False, 'opciones', f'no terminó (código {codigo}) · mira opciones.txt: ' + ' | '.join(txt.splitlines()[-4:])[:400])
        return
    d = json.loads(res[-1].split(' ', 1)[1])
    R.anotar(not d['excepciones'] and not d['fallos'], 'opciones',
             f"{d['paginas']} páginas · {d['pestanas']} pestañas de Ajustes · {d['probadas']} opciones encendidas y apagadas · "
             f"{len(d['excepciones'])} excepciones · {len(d['fallos'])} fallos" +
             (' · ' + ' | '.join((d['excepciones'] + d['fallos'])[:6]) if d['excepciones'] or d['fallos'] else '') + f' · {seg:.0f} s')
    for e in d['registro_errores'][:12]:
        R.anotar(None, 'opciones', 'Registro: ' + e)


def parte_go(R, salida, env, video, modo, estilos):
    for pack in estilos:
        etiqueta = f'{modo} {pack}'
        env2 = dict(env)
        servidor = None
        if modo.startswith('premiere'):
            base = (Path(env2['HOME']) / 'Library' / 'Application Support') if sys.platform == 'darwin' else (salida / 'datos_premiere')
            if not (EN_CI and sys.platform == 'darwin'):
                env2['CINECAPTIONS_PREMIERE_COLA'] = str(base / 'CineCaptions' / 'premiere')
            app = salida / 'Adobe Premiere Pro 2026' / 'Adobe Premiere Pro 2026.app'
            if modo == 'premiere':                       # textos editables: con la plantilla falsa dentro de la «.app»
                plantilla_falsa(app)
            else:                                        # 'premiere_capa': sin plantilla → la capa de video de siempre
                app = salida / 'Premiere sin plantilla.app'
                app.mkdir(parents=True, exist_ok=True)
            env2['CINECAPTIONS_PREMIERE_EXE'] = str(app)
            cola = Path(env2.get('CINECAPTIONS_PREMIERE_COLA') or (base / 'CineCaptions' / 'premiere'))
            shutil.rmtree(cola, ignore_errors=True)
            jsx = CODIGO.parent / '2_recursos' / 'premiere' / 'com.cinecaptions.premiere' / 'jsx' / 'colocar.jsx'
            servidor = subprocess.Popen(['node', str(HERR / 'premiere_falso.js'), str(jsx), str(base), '900'], stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
            time.sleep(1.5)
        codigo, seg, txt = correr([sys.executable, str(Path(__file__)), '--go', modo, pack, str(video), str(salida)],
                                  salida / f'go_{modo}_{pack}.txt', env2, 1200)
        res = [l for l in txt.splitlines() if l.startswith('RESULTADO_GO ')]
        falso = ''
        if servidor is not None:
            try:
                falso = servidor.communicate(timeout=20)[0]
            except subprocess.TimeoutExpired:
                servidor.kill()
                falso = servidor.communicate()[0]
            (salida / f'premiere_falso_{modo}_{pack}.txt').write_text(falso or '', encoding='utf-8')
        if not res:
            R.anotar(False, 'go', f'{etiqueta}: no terminó (código {codigo}) · ' + ' | '.join(txt.splitlines()[-5:])[:500])
            continue
        d = json.loads(res[-1].split(' ', 1)[1])
        ok = d['termino'] and not d['excepciones']
        extra = ''
        if modo == 'mp4':
            ok = ok and d.get('mp4_bytes', 0) > 10000
            extra = f" · MP4 {d.get('mp4_bytes', 0) // 1024} KB"
        else:
            linea = [l for l in (falso or '').splitlines() if l.startswith('PREMIERE_FALSO')]
            extra = ' · panel: ' + (linea[-1][15:300] if linea else 'sin respuesta')
            ok = ok and bool(linea) and '"ok":true' in linea[-1]
            if modo == 'premiere' and linea:                 # (todos los textos puestos; la animación depende del estilo: el 5 y el 7 no animan)
                pf = json.loads(linea[-1].split(' ', 1)[1])
                ok = ok and pf.get('con_textos') is True and pf.get('textos') == pf.get('textos_total') and (pf.get('textos') or 0) > 0
        R.anotar(bool(ok), 'go', f"{etiqueta}: {'terminó' if d['termino'] else 'NO terminó'} en {seg:.0f} s · «{d['linea'][:90]}»" + extra +
                 (' · ' + ' | '.join(d['excepciones'][:3]) if d['excepciones'] else ''))
        for e in d['registro_errores'][:6]:
            R.anotar(None, 'go', f'{etiqueta} · Registro: {e}')


# ------------------------------------------------------------------------------------------------------------------ dentro de la app
def _cargar_app(prefs_extra=None):
    import faulthandler
    import importlib.util
    sys.path.insert(0, str(CODIGO))
    os.chdir(str(CODIGO))
    faulthandler.dump_traceback_later(1100, exit=True)
    excepciones = []

    def gancho(t, v, tb):
        excepciones.append(''.join(traceback.format_exception(t, v, tb))[-600:].replace('\n', ' ⏎ '))
    sys.excepthook = gancho
    import threading
    threading.excepthook = lambda a: gancho(a.exc_type, a.exc_value, a.exc_traceback)
    spec = importlib.util.spec_from_file_location('cc_main', str(CODIGO / 'CineCaptions (script principal).py'))
    M = importlib.util.module_from_spec(spec)
    sys.modules['cc_main'] = M
    spec.loader.exec_module(M)
    import ajustes_ui
    import archivos_seguros
    import cache_voz
    import ia_texto
    import instalador_scripts
    import licencia
    import proyectos
    import qt_kit
    import render_sin_resolve
    import resolve_mcp
    licencia.vigente = lambda: True
    M.SubtitleApp._revisar_licencia_al_arrancar = lambda s: None
    _leer = ajustes_ui.leer_prefs
    extra = dict(prefs_extra or {})
    ajustes_ui.leer_prefs = lambda: {**_leer(), **extra}
    ajustes_ui.guardar_prefs = lambda *a, **k: None
    if hasattr(ajustes_ui, 'mezclar_prefs'):
        ajustes_ui.mezclar_prefs = lambda *a, **k: None
    ajustes_ui.mostrar_novedades = lambda *a, **k: None
    proyectos.guardar = lambda *a, **k: None
    render_sin_resolve.mostrar_en_carpeta = lambda r: None
    resolve_mcp.ruta_exe = lambda: None
    M.instalar_scripts_en_resolve = instalador_scripts.instalar_scripts_en_resolve = lambda *a, **k: (0, None, '')
    qt_kit.mostrar_mensaje = lambda *a, **k: True
    M.ui.error_con_acciones = lambda *a, **k: None
    pal = [{'word': w, 'start': round(0.32 * i + 0.2, 2), 'end': round(0.32 * i + 0.48, 2), 'probability': 0.99} for i, w in enumerate(PALABRAS)]
    cache_voz.leer = lambda *a, **k: [dict(p) for p in pal]
    cache_voz.guardar = lambda *a, **k: False
    ia_texto.disponible = lambda *a, **k: False
    M.SubtitleApp._precargar_motores = lambda s, *a, **k: None
    M.SubtitleApp._precargar_al_abrir = lambda s, *a, **k: None
    import motor_voz
    motor_voz.instalar = lambda *a, **k: False                # (nada de descargar motores de GB)
    try:
        import vigilancia
        vigilancia._motor_ia_en_mac = lambda *a, **k: None
    except Exception:
        pass
    if not EN_CI:                                             # en un equipo de verdad: nada de letras ni registro de Windows
        import instalar_fuentes
        instalar_fuentes.instalar = lambda *a, **k: ([], [])
        instalar_fuentes.instalar_faltantes = lambda *a, **k: ([], [], [], [])
        import premiere
        premiere._modo_depuracion = lambda: False
    # nunca abrir ni tocar DaVinci Resolve (ni su Puente): quien lo tenga instalado puede estar usándolo
    import colocacion
    import resolve_bridge
    import vistas_reales
    for mod, nombres in ((resolve_mcp, ('preparar_proyecto', 'preparar_resolve', 'arrancar_resolve', 'abrir_resolve', 'crear_timeline_con_video')),
                         (resolve_bridge, ('conectar', 'asegurar_conexion', 'lanzar_puente_auto', 'relanzar_puente_tras_detener')),
                         (colocacion, ('detener_reproduccion', 'lanzar_puente_por_menu_windows', 'abrir_resolve_windows', 'preparar_resolve_para_go')),
                         (vistas_reales, ('renderizar_pack',))):
        for n in nombres:
            if hasattr(mod, n):
                setattr(mod, n, (lambda *a, **k: {'ok': False, 'motivo': 'verificación'}) if n.startswith('preparar') else (lambda *a, **k: None))
    for n in ('_esperar_vistas_reales', '_go_reparar_resolve', '_go_detectar_en_resolve', '_renderizar_reales', '_vigilar_conexion'):
        if hasattr(M.SubtitleApp, n):
            setattr(M.SubtitleApp, n, lambda s, *a, **k: None)
    import premiere
    premiere.abrir = lambda *a, **k: True                     # (Premiere «lo abre» el falso, que ya está en marcha)
    app = M.ui.crear_app(['verificar'], carpeta_fuentes=M.BASE_RECURSOS / 'fonts')
    return M, app, excepciones


def _bombear(app, seg):
    t = time.time()
    while time.time() - t < seg:
        app.processEvents()
        time.sleep(0.02)


def _errores_registro():
    """Los errores y avisos del Registro (los avisos salen en el resumen como AVISO, para mirarlos; no cuentan como fallo)."""
    import registro
    return [f"{e.nivel.upper()} {e.origen} · {' '.join(str(e.mensaje).split())[:200]}" for e in registro.registro().lista()
            if e.nivel in ('error', 'aviso')]


def dentro_opciones(salida):
    M, app, excepciones = _cargar_app()
    import ajustes_ui
    from PySide6.QtWidgets import QAbstractButton, QCheckBox
    import qt_kit
    fallos, probadas = [], 0
    w = M.SubtitleApp()
    w._guardar_preferencias = lambda *a, **k: None
    w.show()
    _bombear(app, 2.0)

    def alternar(contenedor, donde):
        nonlocal probadas
        for b in contenedor.findChildren(QAbstractButton):
            if not isinstance(b, (qt_kit.Interruptor, QCheckBox)) or not b.isVisible() or not b.isEnabled():
                continue
            nombre = (b.text() or type(b).__name__).strip()[:50]
            antes = len(excepciones)
            try:
                b.click()
                _bombear(app, 0.25)
                if ui_vivo(b):
                    b.click()
                    _bombear(app, 0.25)
                probadas += 1
            except Exception as e:
                fallos.append(f'{donde} «{nombre}»: {type(e).__name__}: {e}')
            if len(excepciones) > antes:
                fallos.append(f'{donde} «{nombre}»: excepción')

    def ui_vivo(x):
        try:
            return M.ui.vivo(x)
        except Exception:
            return True
    paginas = [c for c, _n in M.SubtitleApp.PAGINAS]
    for p in paginas:
        try:
            w.ir_a(p, animar=False)
            _bombear(app, 0.8)
            alternar(w, f'página {p}')
        except Exception as e:
            fallos.append(f'página {p}: {type(e).__name__}: {e}')
    pestanas = list(ajustes_ui.VentanaAjustes.PESTANAS)
    for pest in pestanas:
        try:
            v = ajustes_ui.VentanaAjustes(w, pest)
            v.abrir()
            _bombear(app, 1.0)
            alternar(v, f'Ajustes › {pest}')
            try:
                v.cerrar()
            except Exception:
                v.close()
            _bombear(app, 0.5)
        except Exception as e:
            fallos.append(f'Ajustes › {pest}: {type(e).__name__}: {e}')
    _bombear(app, 3.0)                                        # (lo que esos clics lanzaron en hilos)
    print('RESULTADO_OPCIONES ' + json.dumps({'paginas': len(paginas), 'pestanas': len(pestanas), 'probadas': probadas, 'fallos': fallos,
                                               'excepciones': excepciones, 'registro_errores': _errores_registro()}, ensure_ascii=False), flush=True)
    os._exit(0)


def dentro_go(modo, pack, video, salida):
    prefs = {'go_pack': pack, 'plantilla': pack, 'go_salida_mp4': modo == 'mp4', 'go_premiere': modo.startswith('premiere'),
             'precargar_al_abrir': False}
    M, app, excepciones = _cargar_app(prefs)
    copia = Path(salida) / f'video_{modo}_{pack}.mp4'
    shutil.copyfile(video, copia)
    w = M.SubtitleApp()
    w._guardar_preferencias = lambda *a, **k: None
    w.plantilla_sel = pack
    w.show()
    _bombear(app, 2.0)
    w._go_archivo = str(copia)
    w._go()
    t0 = time.time()
    while getattr(w, '_go_corriendo', False) and time.time() - t0 < 1000:
        _bombear(app, 0.2)
    _bombear(app, 1.0)
    linea = w.go_panel.linea.text() if callable(getattr(w.go_panel.linea, 'text', None)) else ''
    mp4 = copia.with_name(copia.stem + ' (CineCaptions).mp4')
    print('RESULTADO_GO ' + json.dumps({'termino': bool(getattr(w, '_go_termino', False)), 'linea': linea, 'segundos': round(time.time() - t0, 1),
                                         'mp4_bytes': mp4.stat().st_size if mp4.is_file() else 0, 'excepciones': excepciones,
                                         'registro_errores': _errores_registro()}, ensure_ascii=False), flush=True)
    os._exit(0)


# ------------------------------------------------------------------------------------------------------------------ principal
def main():
    if '--opciones' in sys.argv:
        return dentro_opciones(sys.argv[sys.argv.index('--opciones') + 1])
    if '--go' in sys.argv:
        i = sys.argv.index('--go')
        return dentro_go(*sys.argv[i + 1:i + 5])
    salida = Path([a for a in sys.argv[1:] if not a.startswith('--')][0]).resolve()
    salida.mkdir(parents=True, exist_ok=True)
    solo = sys.argv[sys.argv.index('--solo') + 1].split(',') if '--solo' in sys.argv else ['simular', 'humo', 'opciones', 'go', 'premiere']
    global ESTILOS
    if '--estilos' in sys.argv:                                # (para probar rápido: --estilos Kinetic,Tema4)
        ESTILOS = tuple(sys.argv[sys.argv.index('--estilos') + 1].split(','))
    env = entorno_aislado(salida)
    R = Resumen(salida)
    import platform
    R.anotar(True, 'equipo', f'{sys.platform} · {platform.platform()} · {platform.machine()} · Python {platform.python_version()} · CI={EN_CI}')
    t0 = time.time()
    try:
        video = video_de_prueba(salida / 'zz_verificar_mac.mp4')
    except Exception as e:
        video = None
        R.anotar(False, 'video', f'no pude hacer el video de prueba: {type(e).__name__}: {e}')
    partes = {'simular': lambda: parte_simular(R, salida, env), 'humo': lambda: parte_humo(R, salida, env),
              'opciones': lambda: parte_opciones(R, salida, env),
              'go': lambda: video and parte_go(R, salida, env, video, 'mp4', ESTILOS),
              'premiere': lambda: video and (parte_go(R, salida, env, video, 'premiere', ESTILOS) or
                                             parte_go(R, salida, env, video, 'premiere_capa', ('Tema4',)))}
    for nombre in solo:
        try:
            partes[nombre]()
        except Exception:
            R.anotar(False, nombre, 'el verificador falló: ' + traceback.format_exc()[-500:].replace('\n', ' ⏎ '))
        R.guardar()
    R.lineas.append(f"{'OK   ' if R.fallos == 0 else 'FALLA'} [final] {R.fallos} fallos en {time.time() - t0:.0f} s")
    print(R.lineas[-1], flush=True)
    R.guardar()
    sys.exit(1 if R.fallos else 0)


if __name__ == '__main__':
    main()
