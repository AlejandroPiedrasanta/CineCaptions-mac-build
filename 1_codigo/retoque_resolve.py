# CineCaptions · By Cinema Productions
# 1_codigo/retoque_resolve.py — «Aplicar correcciones en DaVinci»: lleva a Resolve SOLO las palabras corregidas, sin volver a generar.
"""v5.95 (un cliente: «que al corregir lo haga en DaVinci de una vez, sin generar nada»).

Hasta ahora una corrección del editor solo llegaba a Resolve con «Generar», que retira y vuelve a colocar TODOS los clips (y sus sonidos y
emojis, y lo que el usuario hubiera movido a mano). Aquí:

  1. `preparar` lee lo que hay colocado (el .guion.json / .kinetic.json que escribió el último Generar o GO), planifica otra vez con las
     palabras de AHORA (los mismos planificadores que Generar, sin escribir nada) y `comparar` saca los cambios palabra por palabra.
     Solo vale si la FORMA no cambia: mismos bloques, mismas palabras por bloque, mismos tiempos y estilos. Y los bloques sin ninguna palabra
     corregida tienen que salir idénticos: si no, lo colocado no se hizo con estas opciones y no se toca nada (hace falta «Generar»).
  2. `aplicar` manda los cambios a Resolve: Studio por el MCP (`CODIGO_STUDIO`, Python dentro de Resolve) y Free por el Puente
     (acción «retocar» de CineCaptions_Vista.lua, su gemela). En cada clip: texto (StyledText), tamaño (Size), posición (Pan/Tilt), giro y zoom.
     No borra ni coloca clips. Un clip que ya no está donde se colocó o con otro texto (lo cambiaron a mano) no se toca y se cuenta.
  3. `guardar` deja el .json (y su gemelo .lua de Free) como quedó Resolve, para la siguiente corrección.

Vale para los estilos que colocan palabra por palabra (2 al 9). El Estilo 1 (Kinetic neón) pone sus textos ya grabados con la Edición PRO:
ese sigue necesitando «Generar». Nada de esto corre en el hilo de la interfaz (`aplicar` habla con Resolve).
"""
import copy
import json
import time
from pathlib import Path

VALORES = ('texto', 'codigo', 'x', 'y', 'size', 'rot', 'zx', 'zy', 'zoom', 'ancho_rel')     # lo que el retoque puede cambiar en un clip
NUMEROS = ('x', 'y', 'size', 'rot', 'zx', 'zy', 'zoom', 'ancho_rel')
TOLERANCIA = {'x': 0.0006, 'y': 0.0006}                                                    # (< 1 px a 1080); lo demás 0,002
ESTILOS_JSON = {'guion': '.guion.json', 'kinetic': '.kinetic.json'}
MOTIVOS = {
    'sin_datos': 'No encuentro lo que hay colocado de este video: genera los subtítulos una vez.',
    'estilo': 'Con este estilo los textos van grabados en video: para cambiarlos hace falta «Generar».',
    'bloques': 'Con esta corrección cambia el número de bloques: hace falta «Generar».',
    'tiempos': 'Con esta corrección cambian los tiempos o el estilo de algún bloque: hace falta «Generar».',
    'palabras': 'Con esta corrección cambia el número de palabras de algún bloque: hace falta «Generar».',
    'forma': 'Con esta corrección cambia el reparto de las palabras (cuál va grande, en qué línea): hace falta «Generar».',
    'base': 'Lo que hay en DaVinci se generó con otras opciones (estilo, marcas o tamaño): hace falta «Generar».',
}


def _texto(run):
    """El texto que lleva el Text+ del clip (StyledText): el bloque codificado del Estilo 5 o la palabra; None si el clip no lleva texto."""
    if run.get('texto') is None and run.get('codigo') is None:
        return None
    return str(run.get('codigo') or run.get('texto') or '').strip()


def _identidad(run):
    """Lo que NO puede cambiar en un retoque: qué clip es, cuándo entra y sale, su estilo."""
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in run.items() if k not in VALORES}


def _distinto(k, a, b, fino=False):
    """fino: dentro de un bloque que SÍ se retoca va cualquier diferencia (queda igual que con «Generar», al medio píxel)."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) > (1e-6 if fino else TOLERANCIA.get(k, 0.002))
    return a != b


def _cerca(a, b):
    try:
        return abs(float(a) - float(b)) <= 0.002
    except (TypeError, ValueError):
        return a == b


def _cambio(viejo, nuevo, cue, fino=False):
    """Lo que hay que tocar en el clip de `viejo` para que quede como `nuevo` (o None si están iguales)."""
    difs = [k for k in NUMEROS if _distinto(k, viejo.get(k), nuevo.get(k), fino)]
    texto = _texto(viejo) != _texto(nuevo)
    if not difs and not texto:
        return None
    c = {'t': float(viejo.get('t') if viejo.get('t') is not None else cue.get('start') or 0.0), 'antes': _texto(viejo),
         'xa': viejo.get('x'), 'ya': viejo.get('y')}
    if texto:
        c['texto'] = _texto(nuevo)
    for k in ('x', 'y', 'size', 'rot', 'zx', 'zy'):
        if k in difs and isinstance(nuevo.get(k), (int, float)):
            c[k] = float(nuevo[k])
    if 'rol' in viejo:                                   # estilo guion: el zoom va en el clip o dentro del macro Luxe (la palabra grande)
        principal = viejo.get('rol') == 'main'
        if 'zoom' in difs or (principal and ('ancho_rel' in difs or texto)):
            c['zoom'] = float(nuevo.get('zoom') or 1.0)
            c['zoom_antes'] = float(viejo.get('zoom') or 1.0)
            c['main'] = principal
            if principal and isinstance(nuevo.get('ancho_rel'), (int, float)):
                c['ancho_rel'] = float(nuevo['ancho_rel'])
    return c


def comparar(viejos, nuevos):
    """→ {'ok': True, 'cambios': [...], 'bloques': n, 'palabras': n} · {'ok': False, 'motivo': clave de MOTIVOS}"""
    viejos, nuevos = viejos or [], nuevos or []
    if len(viejos) != len(nuevos):
        return {'ok': False, 'motivo': 'bloques'}
    cambios, bloques, palabras = [], 0, 0
    for cv, cn in zip(viejos, nuevos):
        if not _cerca(cv.get('start'), cn.get('start')) or not _cerca(cv.get('end'), cn.get('end')) or cv.get('estilo') != cn.get('estilo'):
            return {'ok': False, 'motivo': 'tiempos'}
        rv, rn = cv.get('runs') or [], cn.get('runs') or []
        if len(rv) != len(rn):
            return {'ok': False, 'motivo': 'palabras'}
        if any(_identidad(a) != _identidad(b) for a, b in zip(rv, rn)):
            return {'ok': False, 'motivo': 'forma'}
        textos = sum(_texto(a) != _texto(b) for a, b in zip(rv, rn))
        del_bloque = [c for c in (_cambio(a, b, cv, fino=bool(textos)) for a, b in zip(rv, rn)) if c]
        if del_bloque and not textos:
            return {'ok': False, 'motivo': 'base'}       # un bloque sin ninguna palabra corregida tiene que salir idéntico
        if del_bloque:
            cambios += del_bloque
            bloques += 1
            palabras += textos
    return {'ok': True, 'cambios': cambios, 'bloques': bloques, 'palabras': palabras}


def nuevos_cues(pack, palabras, roles, idioma='es', fin_video=None, ancho_tl=1080, alto_tl=1920, automatico=False, video=None):
    """Los cues que escribiría «Generar» con estas palabras (sin sonidos ni emojis, que el retoque no toca). → (tipo, cues) · (None, [])
    tipo: 'guion' | 'kinetic' (el nombre del archivo de datos). Los mismos planificadores y parámetros que _generar_con_guion /
    _generar_con_kinetic del script principal (el Estilo 1, Kinetic neón, no: sus textos van grabados)."""
    import guion_editor
    import plantillas
    import vista_tema
    tema = plantillas.tema_base(pack)
    est = vista_tema.estilo_de_pack(tema, 'h' if ancho_tl > alto_tl * 1.2 else 'v') or vista_tema.estilo_de_pack(tema, 'v') or {}
    tipo = est.get('tipo')
    palabras = [dict(w) for w in palabras or []]
    try:
        import ajustes_ui
        prefs = ajustes_ui.leer_prefs() or {}
    except Exception:
        prefs = {}
    if tipo == 'guion':
        r = guion_editor.planear(palabras, roles, tema, ancla=str(prefs.get('guion_ancla', 'medio')), fin_video=fin_video, idioma=idioma,
                                 automatico=automatico, video=video)
        return 'guion', r['cues']
    if tipo != 'viral':
        return None, []
    mains = None if automatico else guion_editor.parametros_de_marcas(palabras, roles)[0]
    propio = {'Tema4': 'pila_planificador', 'Tema5': 'tipo_planificador', 'Tema8': 'ambar_planificador', 'Tema9': 'editorial_planificador'}.get(tema)
    kp = __import__(propio or 'linea_planificador')
    extra = {'perfil': kp.ROJO} if tema == 'Tema7' else {}
    res = kp.planificar(palabras, idioma=idioma, ancho_tl=int(ancho_tl), alto_tl=int(alto_tl), ancla=str(prefs.get('viral_ancla', 'bajo')),
                        mains=mains, fin_video=fin_video, **extra)
    return 'kinetic', res['cues']


def pista_de(manifiesto, proyecto):
    """La pista de datos (guion / kinetic) del manifiesto de ESTE proyecto, o None."""
    if not isinstance(manifiesto, dict) or str(manifiesto.get('project') or '') != str(proyecto or ''):
        return None
    return next((t for t in manifiesto.get('tracks') or [] if isinstance(t, dict) and t.get('style') in ESTILOS_JSON and t.get('data_path')), None)


def preparar(carpeta, proyecto, pack, palabras, roles, idioma='es', fin_video=None, ancho_tl=1080, alto_tl=1920, video=None):
    """Qué habría que tocar en Resolve para llevar las palabras de ahora. No escribe nada ni habla con Resolve.
    → {'ok': True, 'orden', 'cambios', 'bloques', 'palabras', 'ruta', 'datos' (el .json ya retocado, para `guardar`)}
    · {'ok': False, 'motivo', 'texto'}"""
    import archivos_seguros

    def no(motivo):
        return {'ok': False, 'motivo': motivo, 'texto': MOTIVOS[motivo]}
    carpeta = Path(carpeta)
    pista = pista_de(archivos_seguros.leer_json(carpeta / 'subtitles_manifest.json', None), proyecto)
    if pista is None or pista.get('solo_sonidos'):
        return no('estilo' if pista is not None else 'sin_datos')
    ruta = Path(pista['data_path'])
    datos = archivos_seguros.leer_json(ruta, None)
    if not isinstance(datos, dict) or not datos.get('cues'):
        return no('sin_datos')
    intentos = []
    for automatico in (False, True):                     # con las marcas del editor (Generar) o como lo hace GO solo: el que cuadre con lo colocado
        try:
            tipo, cues = nuevos_cues(pack, palabras, roles, idioma, fin_video, ancho_tl, alto_tl, automatico, video)
        except Exception:
            tipo, cues = None, []
        if not tipo:
            return no('estilo')
        if ESTILOS_JSON[tipo] != ESTILOS_JSON.get(pista.get('style')):
            return no('base')
        r = comparar(datos['cues'], cues)
        intentos.append((r, cues))
        if r['ok']:
            break
    r, cues = next((x for x in intentos if x[0]['ok']), intentos[0])
    if not r['ok']:                                      # (de los dos, el motivo que más dice: «base» solo si ninguno apunta a otra cosa)
        return no(next((x[0]['motivo'] for x in intentos if x[0]['motivo'] != 'base'), 'base'))
    retocado = copy.deepcopy(datos)
    for cv, cn in zip(retocado['cues'], cues):
        for a, b in zip(cv.get('runs') or [], cn.get('runs') or []):
            for k in VALORES:
                if k in b:
                    a[k] = b[k]
                else:
                    a.pop(k, None)
        if 'caja' in cn:
            cv['caja'] = cn['caja']
        if cn.get('lines'):
            cv['lines'] = cn['lines']
        elif cv.get('lines') and all('rol' in x for x in cv.get('runs') or []):      # estilo guion: una «línea» por palabra, como Generar
            runs = sorted(cv['runs'], key=lambda x: x.get('t', 0))
            cv['lines'] = [{'role': {'main': 'main', 'context': 'context', 'complement': 'complement'}.get(x['rol'], 'base'),
                            'text': x['texto'], 'start': x.get('t', cv['start'])} for x in runs]
    try:
        offset = int(pista.get('offset_frames') or 0)
    except (TypeError, ValueError):
        offset = 0
    orden = {'accion': 'retocar', 'L': str(pista.get('language') or idioma or 'es').upper(), 'offset': offset, 'cambios': r['cambios']}
    return {'ok': True, 'orden': orden, 'cambios': len(r['cambios']), 'bloques': r['bloques'], 'palabras': r['palabras'], 'ruta': str(ruta),
            'datos': retocado}


# ------------------------------------------------------------------------------------------------------------------ dentro de Resolve (Studio)
# Gemela de `retocar` de CineCaptions_Vista.lua (Free): mismos pasos y mismas cuentas. Corre con `resolve` y `project` del MCP.
CODIGO_STUDIO = r'''
import math, re

_LUXE = (("sizeCtrl", ("StartSize", "EndSize")), ("glow1", ("GlowSize",)), ("shineGlow1", ("GlowSize",)),
         ("positionCtrl", ("StartDistance", "EndDistance")), ("blurCtrl", ("RestingBlur", "StartBlur", "EndBlur")),
         ("shineCtrl", ("ShineWidth", "ShineSoftness")), ("dropShadow", ("shadowBlur", "ShadowDistance")),
         ("Text1", ("SoftnessX4", "SoftnessY4", "SoftnessX5", "SoftnessY5", "Offset4", "Offset5")))


def _retocar(resolve, project, orden):
    if project is None:
        return {'ok': False, 'error': 'No hay ningun proyecto abierto en Resolve.'}
    tl = project.GetCurrentTimeline()
    if tl is None:
        return {'ok': False, 'error': 'No hay timeline abierto.'}

    def num(f, defecto):
        try:
            return float(f())
        except Exception:
            return defecto
    L = str(orden.get('L') or 'ES')
    fps = num(lambda: tl.GetSetting('timelineFrameRate'), 30.0)
    ancho = num(lambda: tl.GetSetting('timelineResolutionWidth'), 1080.0)
    alto = num(lambda: tl.GetSetting('timelineResolutionHeight'), 1920.0)
    inicio = int(num(lambda: tl.GetStartFrame(), 0))
    if int(orden.get('offset') or 0) > 0:
        inicio = int(orden['offset'])

    def text_plus(it):
        try:
            comp = it.GetFusionCompByIndex(1)
            if not comp:
                return None
            p = comp.FindTool('Template')
            if p and p.ID == 'TextPlus':
                return p
            for _n, h in (comp.GetToolList() or {}).items():
                try:
                    if h.ID == 'TextPlus':
                        return h
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def prop(it, k):
        return num(lambda: it.GetProperty(k), 0.0)

    def poner(it, k, v):
        try:
            it.SetProperty(k, v)
        except Exception:
            pass

    def agrandar(it, z):
        try:
            comp = it.GetFusionCompByIndex(1)
            tam = comp.FindTool('sizeCtrl') if comp else None
            if tam is None:
                return
            antes = tam.GetInput('RestingSize')
            if not isinstance(antes, (int, float)) or antes <= 0:
                return
            tam.SetInput('RestingSize', float(antes) * z)
            for nombre, entradas in _LUXE:
                try:
                    h = comp.FindTool(nombre)
                except Exception:
                    continue
                if h is None:
                    continue
                for e in entradas:
                    try:
                        v = h.GetInput(e)
                        if isinstance(v, (int, float)):
                            if v:
                                h.SetInput(e, float(v) * z)
                        elif isinstance(v, dict):
                            x, y = v.get(1, v.get(1.0)), v.get(2, v.get(2.0))
                            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                                h.SetInput(e, {1: float(x) * z, 2: float(y) * z})
                    except Exception:
                        continue
        except Exception:
            pass

    def barrido(it, ancho_rel):
        try:
            comp = it.GetFusionCompByIndex(1)
            macro = comp.FindTool('LuxeShine') if comp else None
            if macro is not None:
                macro.SetInput('inputShine', max(-0.05, (ancho_rel + 0.16) / 2.17 - 0.193))
        except Exception:
            pass

    por_ini, n_clips = {}, 0
    patron = re.compile(re.escape(L) + r'-[TK]\d+$')
    for t in range(1, int(tl.GetTrackCount('video') or 0) + 1):
        if not patron.match(str(tl.GetTrackName('video', t) or '')):
            continue
        for it in tl.GetItemListInTrack('video', t) or []:
            por_ini.setdefault(int(num(lambda: it.GetStart(), -1)), []).append(it)
            n_clips += 1
    usados, hechos, faltan = [], 0, []
    for c in orden.get('cambios') or []:
        f = inicio + int(math.floor(float(c.get('t') or 0.0) * fps + 0.5))
        mejor = tool_m = dist_m = None
        for it in por_ini.get(f) or []:
            if any(it is u for u in usados):
                continue
            tool = text_plus(it)
            if c.get('antes') is not None:
                try:
                    if tool is None or str(tool.GetInput('StyledText') or '').strip() != str(c['antes']).strip():
                        continue
                except Exception:
                    continue
            xa = c.get('xa') if isinstance(c.get('xa'), (int, float)) else 0.5
            ya = c.get('ya') if isinstance(c.get('ya'), (int, float)) else 0.5
            d = abs(prop(it, 'Pan') - (xa - 0.5) * ancho) + abs(prop(it, 'Tilt') - (0.5 - ya) * alto)
            if (c.get('antes') is not None or d <= 4) and (dist_m is None or d < dist_m):
                mejor, tool_m, dist_m = it, tool, d
        if mejor is None:
            faltan.append(str(c.get('antes') or c.get('texto') or '?'))
            continue
        usados.append(mejor)
        if c.get('texto') is not None and tool_m is not None:
            try:
                tool_m.SetInput('StyledText', str(c['texto']))
            except Exception:
                pass
        if isinstance(c.get('size'), (int, float)) and tool_m is not None:
            try:
                tool_m.SetInput('Size', float(c['size']))
            except Exception:
                pass
        if isinstance(c.get('x'), (int, float)):
            poner(mejor, 'Pan', (float(c['x']) - 0.5) * ancho)
        if isinstance(c.get('y'), (int, float)):
            poner(mejor, 'Tilt', (0.5 - float(c['y'])) * alto)
        if isinstance(c.get('rot'), (int, float)):
            poner(mejor, 'RotationAngle', float(c['rot']))
        if isinstance(c.get('zx'), (int, float)):
            poner(mejor, 'ZoomX', float(c['zx']))
        if isinstance(c.get('zy'), (int, float)):
            poner(mejor, 'ZoomY', float(c['zy']))
        if isinstance(c.get('zoom'), (int, float)):
            z, za = float(c['zoom']), float(c.get('zoom_antes') or 1.0)
            dentro = c.get('main') is True and za > 1.005 and abs(prop(mejor, 'ZoomX') - za) > 0.01
            if dentro:
                if abs(z / za - 1) > 0.002:
                    agrandar(mejor, z / za)
            else:
                poner(mejor, 'ZoomX', z)
                poner(mejor, 'ZoomY', z)
            if c.get('main') is True and isinstance(c.get('ancho_rel'), (int, float)):
                barrido(mejor, float(c['ancho_rel']) * (z if dentro else 1.0))
        hechos += 1
    return {'ok': True, 'accion': 'retocar', 'hechos': hechos, 'total': len(orden.get('cambios') or []), 'clips': n_clips, 'faltan': faltan}
'''


def codigo_studio(orden):
    return CODIGO_STUDIO + '\nresult = _retocar(resolve, project, %r)\n' % (orden,)


def aplicar(orden, timeout=120):
    """Manda el retoque a Resolve (Studio: MCP · Free: el Puente con CineCaptions_Vista.lua). Desde un hilo. Nunca lanza.
    → {'ok', 'hechos', 'total', 'clips', 'faltan': [textos], 'camino'} · {'ok': False, 'error', 'camino'}"""
    try:
        import resolve_bridge
        if resolve_bridge._mcp_conectado():
            import resolve_mcp
            ok, r, err = resolve_mcp.script(codigo_studio(orden), timeout=timeout)
            if ok and isinstance(r, dict):
                r['camino'] = 'mcp'
                return r
            return {'ok': False, 'error': str(err or r), 'camino': 'mcp'}
    except Exception as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}', 'camino': 'mcp'}
    try:
        import archivos_seguros
        import resolve_bridge
        import sidecar_lua
        ruta = resolve_bridge.CARPETA_COMPARTIDA / 'vista_orden.json'
        archivos_seguros.escribir_json(ruta, orden)
        sidecar_lua.escribir_sidecar(ruta, orden)
        desde = time.time()
        ok, msg = resolve_bridge.ejecutar('vista', timeout=timeout)
        rep = resolve_bridge.ultimo_reporte(desde=desde) or {}
        vista = rep.get('vista') if isinstance(rep, dict) else None
        if isinstance(vista, dict) and vista.get('accion') == 'retocar':
            vista['camino'] = 'puente'
            return vista
        return {'ok': False, 'camino': 'puente',
                'error': str(msg) if not ok else 'Resolve no contestó al retoque (¿CineCaptions_Vista.lua de otra versión? Reinicia Resolve una vez).'}
    except Exception as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}', 'camino': 'puente'}


def guardar(plan):
    """Deja el archivo de datos (y su gemelo .lua de Free) como quedó Resolve: la siguiente corrección parte de ahí."""
    import archivos_seguros
    ruta = Path(plan['ruta'])
    archivos_seguros.escribir_json(ruta, plan['datos'], indent=1)
    try:
        import sidecar_lua
        sidecar_lua.escribir_sidecar(ruta, plan['datos'])
    except Exception:
        pass
    return str(ruta)
