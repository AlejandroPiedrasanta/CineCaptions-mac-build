# CineCaptions · By Cinema Productions
# 1_codigo/mcp_cinecaptions.py — servidor MCP (stdio, sin dependencias) de CineCaptions: estado, packs, transcribir, planificar, colocar, renderizar y comparar.
"""
mcp_cinecaptions.py  (v5.9)
---------------------------
El MCP del programa: deja que Claude (u otro cliente MCP) hable con CineCaptions sin abrir la interfaz. Sirve sobre todo para PROBAR estilos:

    mapa / simbolo / modulo / cambios / resumen   CONSULTAR el proyecto sin leer archivos (v5.3.2): temas con archivos y símbolos, el código de UNA función, qué es un archivo,
                      los últimos cambios y la página de resumen (usan 1_codigo/mapa_codigo.py y DOCUMENTACION/)
    estado            Resolve (proyecto, timeline, fps), versión del programa, banco de pruebas
    packs             los packs de estilos (variantes, formatos, si son de estilo «guion»)
    transcribir       video/audio -> palabras con tiempos (el mismo motor de voz de la app)
    planificar        palabras -> bloques del estilo «guion» (frase, palabra grande, negritas, pila, estilo), con tabla legible
    banco_preparar    timeline temporal «zz_BANCO» (fondo liso + audio): NO toca tu timeline
    colocar           pone los bloques en Resolve (por defecto solo en el banco)
    renderizar        exporta el timeline actual a .mov (cola de render de Resolve)
    cuadros           hoja con cuadros del render (se devuelve como imagen)
    comparar          referencia | render lado a lado
    medir             dónde cae el texto (cajas) y, contra la referencia, el error por línea
    limpiar_banco     borra el banco y deja tu timeline como estaba
    probar_video      TODO el ciclo: transcribe -> planifica -> banco -> coloca -> renderiza -> hoja de cuadros
    go_real           el botón GO de la app (sin pantalla) sobre un video y un pack: el flujo REAL del usuario -> render -> hoja de cuadros
    arrastrar_video   ARRASTRAR un video a Inicio (preferencias reales): timeline nuevo con el video + GO + captions -> render -> hoja -> limpia
    probar_referencia los 15 bloques EXACTOS de REFERENCIA.mp4 con el pack -> render -> al lado del video (prueba de regresión del pack)
    evaluar           el planificador contra los 15 bloques de REFERENCIA.mp4 (palabras grandes, cortes y estilos acertados)
    registro          las últimas líneas de cinecaptions.log

Protocolo: JSON-RPC 2.0 por stdin/stdout, un mensaje por línea (MCP 2024-11-05). Nada más que JSON sale por stdout: lo demás va a stderr.
Se registra en .mcp.json (raíz del proyecto):  {"mcpServers": {"cinecaptions": {"command": "6_compilacion/venv315/Scripts/python.exe", "args": ["1_codigo/mcp_cinecaptions.py"]}}}
"""
import base64
import io
import json
import os
import sys
import traceback
from pathlib import Path

for _f in (sys.stdin, sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding='utf-8')     # el protocolo es UTF-8 (en Windows el de las tuberías sería la página de códigos local)
    except Exception:
        pass
_SALIDA = sys.stdout
sys.stdout = sys.stderr                      # las librerías que impriman no pueden romper el protocolo
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
CARPETA = Path.home() / 'DaVinciSubtitles' / 'mcp'
REFERENCIA = Path.home() / 'Downloads' / 'REFERENCIA.mp4'
VERSION_MCP = '1.0'


# ---------------------------------------------------------------------------------------------------------------------------------- utilidades
def _cargar_palabras(origen):
    """lista de {'word','start','end'} desde una lista, un .json de palabras o un .json {'words': [...]}."""
    if isinstance(origen, list):
        return origen
    datos = json.loads(Path(str(origen)).read_text(encoding='utf-8'))
    return datos.get('words') if isinstance(datos, dict) else datos


def _tabla(cues, plan, palabras=None):
    lineas = []
    for k, c in enumerate(cues, 1):
        textos = []
        for r in sorted(c['runs'], key=lambda r: r.get('t', 0)):
            textos.append(('[%s]' % r['texto'].upper()) if r['rol'] == 'main' else ('*%s*' % r['texto'] if r['rol'] == 'complement' else r['texto']))
        lineas.append('#%02d %6.2f–%6.2f  estilo %-4s %s' % (k, c['start'], c['end'], c.get('estilo') or '-', ' '.join(textos)))
    return '\n'.join(lineas)


def _imagen(ruta, ancho_max=1600):
    from PIL import Image
    im = Image.open(ruta).convert('RGB')
    if im.width > ancho_max:
        im = im.resize((ancho_max, int(im.height * ancho_max / im.width)))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=85)
    return {'type': 'image', 'data': base64.b64encode(buf.getvalue()).decode('ascii'), 'mimeType': 'image/jpeg'}


def _ruta_render(valor):
    """un nombre del banco («plan1») o una ruta."""
    import banco_pruebas as b
    p = Path(str(valor))
    if p.suffix.lower() in ('.mov', '.mp4') and p.exists():
        return str(p)
    q = b.CARPETA / (str(valor) if p.suffix else str(valor) + '.mov')
    if not q.exists():
        raise FileNotFoundError(f'no encuentro el render «{valor}» (busqué {q})')
    return str(q)


def _tiempos(a, cues=None):
    if a.get('tiempos'):
        return [float(t) for t in a['tiempos']]
    if cues:
        return [round(max(0.0, c['end'] - 0.15), 2) for c in cues]
    raise ValueError('pasa «tiempos» (segundos) o «cues»')


# ---------------------------------------------------------------------------------------------------------------------------------- herramientas
def t_estado(a):
    import banco_pruebas as b
    import plantillas
    import resolve_mcp
    import version
    est = resolve_mcp.estado(refrescar=True)
    packs = [{'nombre': p.nombre, 'incorporado': p.incorporado, 'guion': p.guion, 'formatos': list(p.formatos)} for p in plantillas.listar_packs()]
    banco = None
    try:
        banco = json.loads(b.ESTADO.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {'programa': getattr(version, 'APP_VERSION', '?'), 'resolve': est, 'packs': packs, 'banco': banco, 'carpeta_banco': str(b.CARPETA)}


def t_packs(a):
    import plantillas
    salida = []
    for p in plantillas.listar_packs():
        fila = {'nombre': p.nombre, 'incorporado': p.incorporado, 'guion': p.guion, 'formatos': list(p.formatos), 'variantes': {}}
        for f in p.formatos:
            try:
                fila['variantes'][f] = p.numeros_de_set(f)
            except Exception:
                pass
        salida.append(fila)
    if a.get('pack'):
        import guion_captions as G
        for fila in salida:
            if fila['nombre'] == a['pack']:
                fila['principal_por_variante'] = {n: d for n, d in G.datos_variantes(a['pack']).items()}
    return salida


def t_transcribir(a):
    import subtitle_transcriber as st
    media = str(a['media'])
    idioma = a.get('idioma', 'es')
    palabras = st.transcribe(media, idioma, a.get('modelo', 'large-v3-turbo'))
    palabras = [{'word': w['word'], 'start': round(float(w['start']), 3), 'end': round(float(w['end']), 3)} for w in palabras if str(w.get('word', '')).strip()]
    if a.get('ia'):
        import ia_texto
        palabras, _roles, _resumen = ia_texto.marcar_todo(palabras, idioma)
    CARPETA.mkdir(parents=True, exist_ok=True)
    ruta = CARPETA / f'palabras_{Path(media).stem}.json'
    ruta.write_text(json.dumps(palabras, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'palabras': len(palabras), 'archivo': str(ruta), 'texto': ' '.join(w['word'] for w in palabras)[:600]}


def _planificar(a):
    import guion_captions as G
    import guion_planificador as P
    palabras = _cargar_palabras(a['palabras'])
    pack = a.get('pack', 'Referencia')
    estilos = {int(k): int(v) for k, v in (a.get('estilos') or {}).items()} or None
    bloques, plan = P.planificar(palabras, a.get('idioma', 'es'), pack, ancla=a.get('ancla', 'medio'), mains=a.get('mains') or None, estilos=estilos,
                                 fin_video=a.get('fin_video'))
    cues = G.construir_cues(bloques, pack)
    return cues, plan


def t_planificar(a):
    import guion_captions as G
    cues, plan = _planificar(a)
    CARPETA.mkdir(parents=True, exist_ok=True)
    ruta = G.escribir(cues, a.get('salida') or CARPETA / 'guion_planificado.json', a.get('idioma', 'es'))
    return {'texto': 'Bloques (palabra [GRANDE], *negrita*, fina):\n' + _tabla(cues, plan), 'archivo': ruta}


def t_banco_preparar(a):
    import banco_pruebas as b
    return b.preparar(audio=a.get('audio'), renovar=tuple(a.get('renovar_packs') or ('Referencia',)))


def _estado_timeline():
    import resolve_mcp
    return (resolve_mcp.estado(refrescar=True) or {}).get('timeline')


def t_colocar(a):
    import banco_pruebas as b
    if _estado_timeline() != b.NOMBRE and not a.get('en_timeline_actual'):
        raise RuntimeError(f'El timeline actual no es el banco «{b.NOMBRE}»: prepáralo con banco_preparar, o pasa en_timeline_actual=true si de verdad '
                           'quieres escribir en el timeline abierto.')
    if a.get('cues'):
        datos = json.loads(Path(str(a['cues'])).read_text(encoding='utf-8'))
        cues, idioma = datos['cues'], datos.get('language', 'es')
    else:
        cues, _plan = _planificar(a)
        idioma = a.get('idioma', 'es')
    ok, msg = b.colocar_guion(cues, a.get('pack', 'Referencia'), idioma, archivo=a.get('archivo', 'guion_mcp'))
    return {'ok': bool(ok), 'bloques': len(cues), 'mensaje': str(msg)[-800:]}


def t_renderizar(a):
    import banco_pruebas as b
    ruta = b.renderizar(a.get('nombre', 'mcp'))
    return {'render': ruta}


def t_cuadros(a):
    import banco_pruebas as b
    cues = None
    if a.get('cues'):
        cues = json.loads(Path(str(a['cues'])).read_text(encoding='utf-8'))['cues']
    tiempos = _tiempos(a, cues)
    CARPETA.mkdir(parents=True, exist_ok=True)
    salida = b.hoja(_ruta_render(a['render']), tiempos, CARPETA / 'hoja_mcp.jpg', ancho=int(a.get('ancho', 270)), columnas=int(a.get('columnas', 4)))
    return {'texto': f'{len(tiempos)} cuadros: ' + ', '.join('%.2fs' % t for t in tiempos), 'imagen': salida}


def t_comparar(a):
    import banco_pruebas as b
    referencia = str(a.get('referencia') or REFERENCIA)
    tiempos = _tiempos(a)
    indices = [int(round(t * 30)) for t in tiempos]
    CARPETA.mkdir(parents=True, exist_ok=True)
    salida = b.lado_a_lado(referencia, _ruta_render(a['render']), indices, str(CARPETA / 'comparar_mcp.jpg'), recorte=(0.2, 0.85))
    return {'texto': 'izquierda = referencia, derecha = render', 'imagen': salida}


def t_medir(a):
    import banco_pruebas as b
    ruta = _ruta_render(a['render'])
    if a.get('contra_referencia'):
        import guion_referencia as R
        frames = [int((blq['t1'] - 0.15) * 30) for blq in R.BLOQUES]
        med = b.medir_texto(ruta, frames, umbral=24)
        filas = ['bloque linea   y_obj  y_med    dy    cx_obj cx_med   dx    w_obj  w_med']
        for k, (blq, m) in enumerate(zip(R.BLOQUES, med), 1):
            cajas = list(m['cajas'])
            usadas = set()
            for linea in blq['lineas']:
                tipo, partes, cx, y = linea[:4]
                w = linea[4] if len(linea) > 4 else None
                mejor, dmin = None, 9
                for j, c in enumerate(cajas):
                    if j in usadas:
                        continue
                    d = abs((c[0] + c[1]) / 2 - y)
                    if d < dmin:
                        dmin, mejor = d, j
                if mejor is None or dmin > 0.06:
                    filas.append('%3d  %-10s %s %.3f   (no se ve)' % (k, partes[0][0][:10], tipo, y))
                    continue
                usadas.add(mejor)
                c = cajas[mejor]
                yc, xc, ww = (c[0] + c[1]) / 2, (c[2] + c[3]) / 2, c[3] - c[2]
                filas.append('%3d  %-10s %s %.3f %.3f %+.3f   %.3f %.3f %+.3f   %s %.3f' % (k, partes[0][0][:10], tipo, y, yc, yc - y, cx, xc, xc - cx,
                                                                                      ('%.3f' % w) if w else '  -  ', ww))
        return {'texto': '\n'.join(filas)}
    tiempos = _tiempos(a)
    med = b.medir_texto(ruta, [int(round(t * 30)) for t in tiempos], umbral=int(a.get('umbral', 24)))
    return [{'t': round(m['f'] / 30, 2), 'cajas(y0,y1,x0,x1)': m['cajas']} for m in med]


def t_limpiar_banco(a):
    import banco_pruebas as b
    return b.limpiar()


def t_probar_video(a):
    """Ciclo completo sobre un video: voz -> plan -> banco -> colocar -> render -> hoja de cuadros."""
    import banco_pruebas as b
    import guion_captions as G
    media = str(a['media'])
    pack = a.get('pack', 'Referencia')
    if a.get('palabras'):
        palabras = _cargar_palabras(a['palabras'])
    else:
        palabras = _cargar_palabras(t_transcribir({'media': media, 'idioma': a.get('idioma', 'es')})['archivo'])
    cues, plan = _planificar({**a, 'palabras': palabras, 'pack': pack})
    ruta_cues = G.escribir(cues, CARPETA / 'guion_probar.json', a.get('idioma', 'es'))
    estado = b.preparar(audio=media, renovar=(pack,))
    ok, msg = b.colocar_guion(cues, pack, a.get('idioma', 'es'), archivo='guion_probar')
    if not ok:
        raise RuntimeError(f'Resolve no pudo colocar los bloques: {str(msg)[-500:]}')
    render = b.renderizar(a.get('nombre', 'probar'))
    if not render:
        raise RuntimeError('el render no terminó')
    tiempos = [round(max(0.0, c['end'] - 0.15), 2) for c in cues]
    hoja = b.hoja(render, tiempos, CARPETA / 'hoja_probar.jpg', columnas=int(a.get('columnas', 4)))
    if a.get('limpiar'):
        b.limpiar()
    return {'texto': 'Bloques:\n' + _tabla(cues, plan) + f'\nRender: {render}\nBanco: {estado.get("timeline") if isinstance(estado, dict) else estado}',
            'imagen': hoja}


def t_go_real(a):
    """El botón GO de la app (sin pantalla) sobre un video y un pack: lo MISMO que haría el usuario. Banco → GO → render → hoja de cuadros."""
    import subprocess
    import banco_pruebas as b
    media = str(a['media'])
    pack = a.get('pack', 'Referencia')
    b.preparar(audio=media, renovar=(pack,))
    entorno = {**os.environ, 'DUMP_S': str(int(a.get('timeout', 400)))}
    r = subprocess.run([sys.executable, str(AQUI / 'probar_go.py'), media, pack], capture_output=True, text=True, encoding='utf-8', errors='replace',
                       timeout=int(a.get('timeout', 400)) + 60, env=entorno)
    salida = '\n'.join(l for l in (r.stdout + r.stderr).splitlines() if 'site-packages' not in l)[-1800:]
    if r.returncode != 0:
        raise RuntimeError(f'GO no terminó (código {r.returncode}):\n{salida}')
    render = b.renderizar(a.get('nombre', 'go_real'))
    if not render:
        raise RuntimeError('el render no terminó')
    idioma = a.get('idioma', 'es')
    datos = Path.home() / 'DaVinciSubtitles' / f'{Path(media).stem}.{idioma}.guion.json'
    tiempos = a.get('tiempos')
    if not tiempos and datos.exists():
        cues = json.loads(datos.read_text(encoding='utf-8'))['cues']
        tiempos = [round(max(0.0, c['end'] - 0.15), 2) for c in cues]
    CARPETA.mkdir(parents=True, exist_ok=True)
    hoja = b.hoja(render, tiempos or [1, 3, 5, 7, 9, 11, 13, 15], CARPETA / 'hoja_go.jpg', columnas=int(a.get('columnas', 4)))
    return {'texto': f'GO real con el pack «{pack}»:\n{salida}\nRender: {render}\nBloques: {datos}', 'imagen': hoja}


_BUSCAR_PROYECTO = r"""
def buscar(nombre, prof=0):
    if nombre in (pm.GetProjectListInCurrentFolder() or []):
        return True
    if prof < 5:
        for c in (pm.GetFolderListInCurrentFolder() or []):
            if pm.OpenFolder(c):
                if buscar(nombre, prof + 1):
                    return True
                pm.GotoParentFolder()
    return False
"""

_ESTADO_PREVIO = r"""
pm = resolve.GetProjectManager()
p = pm.GetCurrentProject()
""" + _BUSCAR_PROYECTO + r"""
pm.GotoRootFolder()
existe = buscar(%(nombre)r)
pm.GotoRootFolder()
tl = p.GetCurrentTimeline() if p else None
result = {'proyecto': p.GetName() if p else None, 'timeline': tl.GetName() if tl else None, 'existe': bool(existe)}
"""

_LIMPIAR_ARRASTRE = r"""
STEM, PREVIO_P, PREVIO_TL, BORRAR = %(stem)r, %(previo_p)r, %(previo_tl)r, %(borrar)r
pm = resolve.GetProjectManager()
p = pm.GetCurrentProject()
""" + _BUSCAR_PROYECTO + r"""
res = {'proyecto_actual': p.GetName() if p else None}
creado = None
if p is not None and p.GetName().startswith('CineCaptions') and p.GetName() != PREVIO_P:
    creado = p.GetName()
    mp = p.GetMediaPool()
    for j in (p.GetRenderJobList() or []):
        p.DeleteRenderJob(j['JobId'])
    if not BORRAR:
        # no se puede volver a otro proyecto: al menos se quita el timeline y el bin de la prueba
        tls = [p.GetTimelineByIndex(i) for i in range(1, int(p.GetTimelineCount() or 0) + 1)]
        mio = [t for t in tls if t and t.GetName().startswith('CineCaptions ') and STEM in t.GetName()]
        res['ok_tl'] = bool(mp.DeleteTimelines(mio)) if mio else None
        raiz = mp.GetRootFolder()
        cs = [c for c in (raiz.GetSubFolderList() or []) if c.GetName().startswith('CineCaptions ')]
        mp.SetCurrentFolder(raiz)
        res['bin'] = bool(mp.DeleteFolders(cs)) if cs else None
    try:
        pm.SaveProject()
    except Exception:
        pass
res['proyecto_creado'] = creado
if PREVIO_P and (p is None or p.GetName() != PREVIO_P):
    pm.GotoRootFolder()
    if buscar(PREVIO_P):
        q = pm.LoadProject(PREVIO_P)
        res['restaurado'] = bool(q)
        if q and PREVIO_TL:
            for i in range(1, int(q.GetTimelineCount() or 0) + 1):
                t = q.GetTimelineByIndex(i)
                if t and t.GetName() == PREVIO_TL:
                    q.SetCurrentTimeline(t)
                    break
        if q and BORRAR and creado:
            pm.GotoRootFolder()
            if buscar(creado):
                res['proyecto_borrado'] = bool(pm.DeleteProject(creado))
    pm.GotoRootFolder()
q = pm.GetCurrentProject()
res['abierto_ahora'] = q.GetName() if q else None
res['timeline_ahora'] = (q.GetCurrentTimeline().GetName() if q and q.GetCurrentTimeline() else None)
result = res
"""


_VERIFICAR_TL = r"""
tl = project.GetCurrentTimeline()
res = {'proyecto': project.GetName(), 'timeline': tl.GetName() if tl else None}
if tl:
    a1 = tl.GetItemListInTrack('audio', 1) or []
    v1 = tl.GetItemListInTrack('video', 1) or []
    res['A1'] = [(it.GetName(), bool(it.GetClipEnabled())) for it in a1]
    res['V1'] = [(it.GetName(), bool(it.GetClipEnabled())) for it in v1]
    res['A1_activa'] = bool(tl.GetIsTrackEnabled('audio', 1))
    import re
    res['pistas_texto'] = sum(1 for t in range(1, tl.GetTrackCount('video') + 1) if re.match(r'^[A-Za-z]{2,3}-[KT]\d+$', tl.GetTrackName('video', t)))
    res['pistas_sfx'] = sum(1 for t in range(1, tl.GetTrackCount('audio') + 1) if tl.GetTrackName('audio', t).startswith('SFX'))
result = res
"""


def _volumen(ruta):
    """(tiene_audio, volumen_medio_dB | None) de un archivo, con ffmpeg."""
    import re
    import subprocess
    try:
        r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(ruta), '-vn', '-af', 'volumedetect', '-f', 'null', '-'], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=120)
    except Exception:
        return None, None
    txt = r.stderr or ''
    if 'does not contain any stream' in txt or 'Output file #0 does not contain' in txt:
        return False, None
    m = re.search(r'mean_volume:\s*(-?[\d.]+) dB', txt)
    return bool(m), (float(m.group(1)) if m else None)


def t_arrastrar_video(a):
    """Lo mismo que ARRASTRAR un video a Inicio con tus preferencias reales: la app abre Resolve, abre o crea el proyecto «CineCaptions», arma un
    timeline con el video, arranca GO y pone los captions. Renderiza ese timeline, devuelve la hoja de cuadros y (limpiar=true, por defecto) deja
    Resolve como estaba: borra el timeline y el bin que se crearon, vuelve a tu proyecto y timeline, y borra el proyecto «CineCaptions» SOLO si
    lo creó esta prueba."""
    import subprocess
    import banco_pruebas as b
    import resolve_mcp
    media = str(a['media'])
    nombre = a.get('proyecto', 'CineCaptions')
    previo = {}
    if resolve_mcp.resolve_abierto():
        ok, previo, _err = resolve_mcp.script(_ESTADO_PREVIO % {'nombre': nombre}, timeout=40)
        previo = previo if ok and isinstance(previo, dict) else {}
    entorno = {**os.environ, 'DUMP_S': str(int(a.get('timeout', 420)))}
    r = subprocess.run([sys.executable, str(AQUI / 'probar_go.py'), media, '-', '--soltar'], capture_output=True, text=True, encoding='utf-8', errors='replace',
                       timeout=int(a.get('timeout', 420)) + 60, env=entorno)
    salida = '\n'.join(l for l in (r.stdout + r.stderr).splitlines() if 'site-packages' not in l)[-1500:]
    stem = Path(media).stem[:40]
    render = hoja = None
    sonido = None
    try:
        if r.returncode != 0:
            raise RuntimeError(f'GO no terminó (código {r.returncode}):\n{salida}')
        ok_v, estado_tl, _e = resolve_mcp.script(_VERIFICAR_TL, timeout=30)
        estado_tl = estado_tl if ok_v else {}
        render = b.renderizar(a.get('nombre', 'arrastrar'))
        if not render:
            raise RuntimeError('el render no terminó')
        tiene_fuente, vol_fuente = _volumen(media)
        tiene_render, vol_render = _volumen(render)
        sonido = {'timeline': estado_tl, 'audio_en_la_fuente': tiene_fuente, 'volumen_fuente_dB': vol_fuente, 'audio_en_el_render': tiene_render, 'volumen_render_dB': vol_render}
        a1_ok = any(Path(media).name == n and on for n, on in (estado_tl or {}).get('A1', []))
        sonido['VEREDICTO'] = ('OK: el audio del video está en A1 y suena en el render' if (a1_ok and tiene_render and (vol_render is None or vol_render > -60))
                               else 'FALLA: el audio del video no llegó al timeline o al render')
        candidatos = sorted([q for pat in ('.kinetic.json', '.guion.json') for q in (Path.home() / 'DaVinciSubtitles').glob(f'{Path(media).stem}.*{pat}')],
                            key=lambda q: q.stat().st_mtime, reverse=True)
        datos = candidatos[0] if candidatos else Path.home() / 'DaVinciSubtitles' / 'no_existe.json'
        tiempos = a.get('tiempos')
        if not tiempos and datos.exists():
            tiempos = [round(max(0.0, c['end'] - 0.5), 2) for c in json.loads(datos.read_text(encoding='utf-8'))['cues']]          # con todo ya dentro y antes de la salida
        CARPETA.mkdir(parents=True, exist_ok=True)
        hoja = b.hoja(render, tiempos or [1, 3, 5, 7, 9, 11, 13, 15], CARPETA / 'hoja_arrastrar.jpg', columnas=int(a.get('columnas', 4)))
    finally:
        limpieza = None
        if a.get('limpiar', True):
            ok, limpieza, err = resolve_mcp.script(_LIMPIAR_ARRASTRE % {'stem': stem, 'previo_p': previo.get('proyecto'), 'previo_tl': previo.get('timeline'),
                                                                        'borrar': bool(previo.get('proyecto'))}, timeout=60)
            limpieza = limpieza if ok else f'no pude limpiar: {err}'
    return {'texto': f'Arrastrar «{Path(media).name}» a Inicio (Resolve antes: {previo or "cerrado"}):\n{salida}\nRender: {render}\nSonido: {json.dumps(sonido, ensure_ascii=False)}\nLimpieza: {limpieza}', 'imagen': hoja}


def t_probar_referencia(a):
    """La prueba de regresión del pack: coloca los 15 bloques EXACTOS de REFERENCIA.mp4 (guion_referencia.BLOQUES), renderiza y los pone al lado del video."""
    import banco_pruebas as b
    import guion_captions as G
    import guion_referencia as R
    pack = a.get('pack', 'Referencia')
    CARPETA.mkdir(parents=True, exist_ok=True)
    cues = R.cues_de_la_referencia(1080)
    G.escribir(cues, CARPETA / 'ref_exacta.guion.json', 'es')
    b.preparar(audio=str(a.get('audio') or REFERENCIA), renovar=(pack,))
    ok, msg = b.colocar_guion(cues, pack, 'es', archivo='guion_ref_exacta')
    if not ok:
        raise RuntimeError(f'Resolve no pudo colocar los bloques: {str(msg)[-500:]}')
    render = b.renderizar(a.get('nombre', 'ref_exacta'))
    tiempos = a.get('tiempos') or [1.0, 2.4, 4.0, 5.3, 7.3, 9.9, 12.8, 19.3]
    salida = b.lado_a_lado(str(REFERENCIA), render, [int(round(t * 30)) for t in tiempos], str(CARPETA / 'comparar_mcp.jpg'), recorte=(0.2, 0.85))
    return {'texto': f'15 bloques exactos de la referencia con el pack «{pack}». Render: {render}\nizquierda = referencia, derecha = render', 'imagen': salida}


def t_evaluar(a):
    """El planificador contra los 15 bloques de la referencia (palabra grande, cortes de bloque)."""
    import guion_planificador as P
    r = P.evaluar(None, pack=a.get('pack', 'Referencia'), ancla=a.get('ancla', 'medio'), fin_video=24.0)
    texto = (f"palabras grandes de la referencia acertadas: {r['mains_ok']}/{r['mains_ref']}  ·  de más: {r['mains_de_mas']}\n"
             f"bloques: referencia {r['bloques_ref']}, planificador {r['bloques_mios']}  ·  cortes de bloque coincidentes: {r['cortes_ok']}/{r['bloques_ref']}\n"
             f"estilo del bloque acertado: {r['estilos_ok']}/{r['estilos_total']}")
    return {'texto': texto}


# ---------------------------------------------------------------------------------------------------------------------------------- documentación y código por temas (v5.3.2)
def _mc():
    import mapa_codigo
    return mapa_codigo


def t_mapa(a):
    return _mc().mapa(a.get('consulta', ''), a.get('id', ''), bool(a.get('completo')), int(a.get('maximo', 5)))


def t_simbolo(a):
    return _mc().simbolo(a['nombre'], int(a.get('lineas', 70)), a.get('archivo', ''))


def t_modulo(a):
    return _mc().modulo(a['nombre'])


def t_cambios(a):
    return _mc().cambios(int(a.get('n', 6)))


def t_resumen(a):
    return _mc().resumen()


def t_registro(a):
    ruta = Path.home() / 'DaVinciSubtitles' / 'cinecaptions.log'
    try:
        lineas = ruta.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError as e:
        return f'no hay registro ({e})'
    return '\n'.join(lineas[-int(a.get('lineas', 40)):])


# ---------------------------------------------------------------------------------------------------------------------------------- catálogo
def _esq(props, requeridos=()):
    return {'type': 'object', 'properties': props, 'required': list(requeridos)}


_S, _N, _L = {'type': 'string'}, {'type': 'number'}, {'type': 'array', 'items': {'type': 'number'}}
_PLAN = {'palabras': {'description': 'ruta de un .json de palabras [{word,start,end}] o la lista misma', 'anyOf': [_S, {'type': 'array', 'items': {'type': 'object'}}]},
         'pack': {'type': 'string', 'description': 'nombre del pack de estilos (por defecto «Referencia»)'},
         'ancla': {'type': 'string', 'enum': ['medio', 'alto', 'bajo', 'alterna'], 'description': 'dónde va la pila de texto'},
         'mains': {'type': 'array', 'items': {'type': ['string', 'integer']}, 'description': 'fuerza estas palabras (texto o índice) como palabras grandes'},
         'estilos': {'type': 'object', 'description': '{"índice de bloque": n de variante} para forzar el estilo de un bloque'},
         'fin_video': _N, 'idioma': _S}
HERRAMIENTAS = {
    'mapa': ('USAR ANTES DE ABRIR ARCHIVOS. Busca por palabras qué tema del programa tiene lo que buscas y devuelve sus archivos y símbolos (compacto); con id="go-inicio" da el detalle de ese tema; '
             'con completo=true incluye el texto. Sin argumentos lista los grupos.', _esq({'consulta': _S, 'id': _S, 'completo': {'type': 'boolean'}, 'maximo': _N}), t_mapa),
    'simbolo': ('Devuelve SOLO el código de una función, clase o método (p. ej. "_go_generar", "WordTagWindow._continuar", "Instalacion.Desinstalar") con archivo:líneas; las clases grandes dan la lista de métodos. '
                'Evita leer el script principal (12 000 líneas).', _esq({'nombre': _S, 'lineas': _N, 'archivo': _S}, ['nombre']), t_simbolo),
    'modulo': ('Qué es un archivo de código (descripción, clases y funciones con su línea), p. ej. "vigilancia", "sfx_rules", "principal".', _esq({'nombre': _S}, ['nombre']), t_modulo),
    'cambios': ('Las últimas n entradas EXPLICADAS del registro de cambios (el porqué de cada cambio reciente).', _esq({'n': _N}), t_cambios),
    'resumen': ('Una página: qué es CineCaptions, flujo de GO, pantallas, quién decide qué y reglas que no se rompen.', _esq({}), t_resumen),
    'estado': ('Estado de CineCaptions: versión, Resolve (proyecto, timeline, fps), packs y banco de pruebas.', _esq({}), t_estado),
    'packs': ('Lista los packs de estilos (variantes, formatos, estilo «guion»). Con «pack» añade el tipo de letra y tamaño del principal de cada variante.',
              _esq({'pack': _S}), t_packs),
    'transcribir': ('Transcribe un video/audio con el motor de voz de la app (Qwen3-ASR o Whisper) y guarda las palabras con tiempos.',
                    _esq({'media': _S, 'idioma': _S, 'ia': {'type': 'boolean', 'description': 'además corrige el texto con la IA de la app (carga el modelo: lento)'}}, ['media']), t_transcribir),
    'planificar': ('Convierte palabras con tiempos en bloques del estilo «guion» (frases, palabra grande, negritas, pila, estilo por bloque). Devuelve una tabla legible '
                   'y el .json listo para colocar. Con «mains»/«estilos» se corrige a mano lo que elija el planificador.', _esq(_PLAN, ['palabras']), t_planificar),
    'banco_preparar': ('Crea en Resolve el timeline temporal «zz_BANCO» (fondo gris + audio) y lo deja como actual. No toca tu timeline; se restaura con limpiar_banco.',
                       _esq({'audio': _S, 'renovar_packs': {'type': 'array', 'items': {'type': 'string'}}}), t_banco_preparar),
    'colocar': ('Coloca los bloques en Resolve (script «subtitulos» de la app). Solo en el banco, salvo en_timeline_actual=true. Pasa «cues» (.json de planificar) o «palabras».',
                _esq({**_PLAN, 'cues': _S, 'en_timeline_actual': {'type': 'boolean'}, 'archivo': _S}), t_colocar),
    'renderizar': ('Renderiza el timeline actual a ~/DaVinciSubtitles/banco/<nombre>.mov (cola de render de Resolve, ~1-2 min).', _esq({'nombre': _S}), t_renderizar),
    'cuadros': ('Hoja de cuadros del render en los instantes pedidos (o al final de cada bloque si pasas «cues»). Devuelve la imagen.',
                _esq({'render': _S, 'tiempos': _L, 'cues': _S, 'ancho': _N, 'columnas': _N}, ['render']), t_cuadros),
    'comparar': ('Referencia (izquierda) y render (derecha) lado a lado en esos instantes. Devuelve la imagen.',
                 _esq({'render': _S, 'tiempos': _L, 'referencia': _S}, ['render', 'tiempos']), t_comparar),
    'medir': ('Mide dónde cae el texto del render sobre el fondo liso. Con contra_referencia=true da el error por línea contra los 15 bloques de REFERENCIA.mp4.',
              _esq({'render': _S, 'tiempos': _L, 'contra_referencia': {'type': 'boolean'}, 'umbral': _N}, ['render']), t_medir),
    'limpiar_banco': ('Borra el timeline de pruebas y vuelve al timeline que había.', _esq({}), t_limpiar_banco),
    'probar_video': ('Ciclo completo sobre un video: transcribe, planifica, prepara el banco, coloca, renderiza y devuelve la hoja de cuadros con la tabla de bloques.',
                     _esq({**_PLAN, 'media': _S, 'nombre': _S, 'columnas': _N, 'limpiar': {'type': 'boolean'}}, ['media']), t_probar_video),
    'go_real': ('El botón GO de la app (sin pantalla) sobre un video y un pack, como lo usaría el usuario: banco → GO → render → hoja de cuadros. Prueba TODO el flujo real '
                '(voz, IA, planificador, colocación), no solo el planificador.',
                _esq({'media': _S, 'pack': _S, 'nombre': _S, 'tiempos': _L, 'columnas': _N, 'timeout': _N, 'idioma': _S}, ['media']), t_go_real),
    'arrastrar_video': ('Lo mismo que ARRASTRAR un video a Inicio con las preferencias reales del usuario: la app arma en Resolve un timeline nuevo con el video, '
                        'arranca GO y pone los captions; renderiza ese timeline, devuelve la hoja de cuadros y limpia lo que creó (limpiar=false lo deja).',
                        _esq({'media': _S, 'nombre': _S, 'tiempos': _L, 'columnas': _N, 'timeout': _N, 'idioma': _S, 'limpiar': {'type': 'boolean'}}, ['media']), t_arrastrar_video),
    'probar_referencia': ('Prueba de regresión del pack: coloca los 15 bloques EXACTOS de REFERENCIA.mp4, renderiza y los pone al lado del video (izquierda = referencia).',
                          _esq({'pack': _S, 'tiempos': _L, 'nombre': _S, 'audio': _S}), t_probar_referencia),
    'evaluar': ('Mide el planificador contra REFERENCIA.mp4 (palabras grandes, cortes de bloque y estilos acertados). Úsalo tras tocar guion_planificador.py.',
                _esq({'pack': _S, 'ancla': _S}), t_evaluar),
    'registro': ('Últimas líneas del registro de la app (cinecaptions.log).', _esq({'lineas': _N}), t_registro),
}


# ---------------------------------------------------------------------------------------------------------------------------------- protocolo
def _contenido(resultado):
    """str | dict | list -> lista de bloques de contenido MCP (texto + imágenes)."""
    bloques = []
    if isinstance(resultado, dict) and ('imagen' in resultado or 'texto' in resultado):
        resto = {k: v for k, v in resultado.items() if k not in ('imagen', 'texto')}
        texto = resultado.get('texto', '')
        if resto:
            texto = (texto + '\n' if texto else '') + json.dumps(resto, ensure_ascii=False, indent=1, default=str)
        bloques.append({'type': 'text', 'text': texto})
        if resultado.get('imagen'):
            bloques.append(_imagen(resultado['imagen']))
            bloques.append({'type': 'text', 'text': 'imagen: ' + str(resultado['imagen'])})
    elif isinstance(resultado, str):
        bloques.append({'type': 'text', 'text': resultado})
    else:
        bloques.append({'type': 'text', 'text': json.dumps(resultado, ensure_ascii=False, indent=1, default=str)})
    return bloques


def _responder(id_, resultado=None, error=None):
    msg = {'jsonrpc': '2.0', 'id': id_}
    if error is not None:
        msg['error'] = error
    else:
        msg['result'] = resultado
    _SALIDA.write(json.dumps(msg, ensure_ascii=False) + '\n')
    _SALIDA.flush()


_MODULOS_VIVOS = ('guion_captions', 'guion_planificador', 'guion_referencia', 'banco_pruebas', 'mapa_codigo')    # en orden de dependencia
_MTIMES = {}


def _recargar():
    """Recarga en caliente los módulos del estilo «guion» que cambiaron en disco: se edita y se prueba sin reiniciar el servidor."""
    import importlib
    for nombre in _MODULOS_VIVOS:
        mod = sys.modules.get(nombre)
        ruta = AQUI / f'{nombre}.py'
        try:
            t = ruta.stat().st_mtime
        except OSError:
            continue
        if nombre not in _MTIMES:
            _MTIMES[nombre] = t
            continue
        if t != _MTIMES[nombre]:
            _MTIMES[nombre] = t
            if mod is not None:
                importlib.reload(mod)


def _atender(msg):
    metodo, id_ = msg.get('method'), msg.get('id')
    p = msg.get('params') or {}
    if metodo == 'initialize':
        return _responder(id_, {'protocolVersion': p.get('protocolVersion') or '2024-11-05', 'capabilities': {'tools': {}},
                                'serverInfo': {'name': 'cinecaptions', 'version': VERSION_MCP}})
    if metodo in ('notifications/initialized', 'notifications/cancelled') or (metodo or '').startswith('notifications/'):
        return None
    if metodo == 'ping':
        return _responder(id_, {})
    if metodo == 'tools/list':
        return _responder(id_, {'tools': [{'name': n, 'description': d, 'inputSchema': s} for n, (d, s, _f) in HERRAMIENTAS.items()]})
    if metodo == 'tools/call':
        nombre, args = p.get('name'), p.get('arguments') or {}
        if nombre not in HERRAMIENTAS:
            return _responder(id_, error={'code': -32602, 'message': f'herramienta desconocida: {nombre}'})
        try:
            _recargar()
            r = HERRAMIENTAS[nombre][2](args)
            return _responder(id_, {'content': _contenido(r), 'isError': False})
        except Exception as e:
            sys.stderr.write(traceback.format_exc())
            cola = ''.join(traceback.format_exception_only(type(e), e)).strip()
            return _responder(id_, {'content': [{'type': 'text', 'text': f'{nombre}: {cola}'}], 'isError': True})
    if id_ is not None:
        return _responder(id_, error={'code': -32601, 'message': f'método no soportado: {metodo}'})
    return None


def main():
    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            msg = json.loads(linea)
        except ValueError:
            continue
        try:
            _atender(msg)
        except Exception:
            sys.stderr.write(traceback.format_exc())


if __name__ == '__main__':
    main()
