# CineCaptions · By Cinema Productions
# 1_codigo/fluidez_resolve.py — reproducción fluida al terminar GO: caché de render de Fusion en nuestros clips y espera a que Resolve la llene.
"""
fluidez_resolve.py  (v5.56)
---------------------------
Pedido del usuario: «al reproducir va todo trabado… que vaya fluido sin tirones en cualquier tema».

Por qué iba a tirones: los captions son títulos de Fusion (Text+/macros Luxe con brillo, sombras, Softness, máscaras), varios apilados (9 pistas
en el Tema 1, 8 en el Tema 3) y Resolve los RENDERIZA en cada cuadro al reproducir. Con GO los captions no se marcaban para la caché (los marcaba
la Edición PRO al terminar: `cache_captions = False`); sin la PRO nadie los marcaba y la caché del proyecto seguía en «none». Visto en el
proyecto del usuario «CineCaptions 16» (Tema 1, 9 pistas, 21.1.2): perfRenderCacheMode = none y su carpeta de caché vacía (solo Info.txt),
frente a «CineCaptions 15»: 5 653 cuadros en caché (2,7 GB).

Qué hace (una sola pasada AL FINAL de GO, con todo ya colocado: marcar mientras un script movía clips tumbaba Resolve, v5.5.8):
  1. preparar(): «Render Cache Fusion Output» = On en NUESTROS clips con Fusion y la caché del proyecto lista.
       · Pistas nuestras: <LANG>, <LANG>-CTX/-MAIN/-CMP/-EMOJI/-K1…/-T1…, FX-*, PRO-* (o «descripción · PRO-…»); en V1 solo los clips con una comp
         «CineCaptions …». En un proyecto que creó GO («CineCaptions», «CineCaptions N», «CineCaptions_nuevo…») todo V2+ y los clips de V1 con comps.
       · Proyecto de GO: caché «smart», caché en segundo plano a los 2 s de reposo, y cachear efectos de Fusion, transiciones y composiciones.
       · Proyecto del usuario: solo lo imprescindible: «none» → «user» (con «none» Resolve no guarda nada aunque el clip lo pida) y la caché en
         segundo plano encendida si estaba apagada. Nada más suyo.
     Studio: por el MCP (resolve_mcp.script, código _PASADA). Free: por el Puente (CineCaptions_Vista.lua, acción «cabezal» con `fluidez = true`;
     un Vista.lua viejo ignora el campo y solo mueve el cabezal: nunca cae en «guardar la disposición»).
  2. esperar_cache(): la API NO dice cuándo termina la caché (no hay ninguna llamada para eso). Se mira la carpeta de caché del proyecto
     (<perfCacheClipsLocation o ~/Videos|~/Movies>/CacheClip/<Project.GetUniqueId()>/…/*.dvcc, un archivo por cuadro) hasta que tenga los
     cuadros de nuestros clips, deje de crecer o pase el tope (15–60 s según los cuadros). Luego colocacion.reproducir_desde_inicio pulsa «Reproducir».
     Mientras se espera no se habla con Resolve (la caché en segundo plano solo corre con Resolve en reposo).
El valor de SetFusionOutputCache es la CONSTANTE resolve.CACHE_ENABLED (1.0; CACHE_AUTO_ENABLED = -1.0, CACHE_DISABLED = 0.0: la API de 21.1.2
la tipa como `str` pero las cadenas «On»/«enabled» devuelven False). Medido en Studio 21.1.2 (2026-10-30): con «On»/«enabled» los 30 clips del
Tema 1 fallaban («Resolve no aceptó ningún valor de caché») y la espera no arrancaba; con la constante → True y GetIsFusionOutputCacheEnabled()
dice «1» (antes «-1» = auto). Se prueba primero la constante y luego los textos de antes (versiones viejas); el bueno queda en el Registro.
Gemelos de la regla del valor: CineCaptions.py (_marcar_cache), CineCaptions_Subtitulos.lua (COLORES_CC.marcar_cache), CineCaptions_Vista.lua
(fluidez) y los que marcan sin sondear: colocar_efectos.py, colocar_pro.py, CineCaptions_Efectos.lua y CineCaptions_EdicionPro.lua.

v5.56 (el usuario: «mejora el render cache para que la preview en Resolve sea fluida sin lags»; y GO de solo captions en < 1 min): GO ya NO
espera a la caché. Al final de GO solo marca (preparar, ~1 s) y termina; `esperar_y_reproducir` (en un hilo, mirando solo el disco) espera a que
Resolve llene la caché en reposo y ENTONCES pulsa «Reproducir». Medido con un video de 24 s del Tema 1: Resolve cachea ~25–35 cuadros/s
(carpetas SourceOne = la salida de cada clip y Sequence = el compuesto); reproducir al instante iba a tirones porque la caché aún no existía.
Arnés de la prueba real: ver DOCUMENTACION/temas/resolve.md (sección «fluidez»).
"""
import os
import re
import time
from pathlib import Path

from i18n import tr

VALORES_ON = ('On', 'enabled', 'Enabled', 'on')     # (tras la constante resolve.CACHE_ENABLED: versiones viejas) el primero que acepte y lea On
DESPUES_S_GO = '2'                                 # proyecto de GO: la caché en segundo plano empieza a los 2 s de reposo (Resolve trae 5)
FPS_CACHE = 16.0                                   # cuadros/s de la SALIDA de clips en Studio 21.1.2 (medido 19–24 con el compuesto intercalado:
                                                   # 26–34 en total; Tema 1, 1080×1920, ProRes 422 HQ), con margen
TOPE_MIN_S, TOPE_MAX_S = 15.0, 240.0               # (ya no frena GO: se espera en un hilo, después de «Listo»)
QUIETO_S = 8.0                                     # sin cuadros nuevos en ese tiempo (tras empezar): Resolve terminó o se paró
ARRANQUE_EXTRA_S = 12.0                            # margen sobre perfAutoRenderCacheAfterTime para el primer cuadro
SALIDA_CLIPS, COMPUESTO = 'SourceOne', 'Sequence'  # carpeta que CONTIENE los .dvcc: la salida de un clip (CacheClip/<uid>/<timeline>/<clip>/<…>/
                                                   # SourceOne) o el compuesto (CacheClip/<uid>/<timeline>/Sequence), medido en 21.1.2
_PROYECTO_GO = re.compile(r'^CineCaptions( \d+)?$|^CineCaptions_nuevo')

# Se ejecuta DENTRO de Resolve (Studio, MCP run_script_unsafe). Todo dentro de una función: con exec y locales aparte, las funciones de nivel
# superior no se verían entre sí. Gemelo: CineCaptions_Vista.lua (fluidez).
_PASADA = r'''
def _fluidez(resolve, project, go, valores, despues):
    import re
    res = {'ok': False}
    p = project or resolve.GetProjectManager().GetCurrentProject()
    tl = p.GetCurrentTimeline() if p else None
    if not p or not tl:
        res['error'] = 'sin proyecto o sin timeline'
        return res
    nombre_p = str(p.GetName() or '')
    if go is None:
        go = bool(re.match(r'^CineCaptions( \d+)?$|^CineCaptions_nuevo', nombre_p))

    def leer(k):
        try:
            v = p.GetSetting(k)
        except Exception:
            return ''
        return '' if v is None else str(v)

    def num(s):
        try:
            return float(s)
        except (TypeError, ValueError):
            return None

    def poner(k, v):
        try:
            p.SetSetting(k, v)
        except Exception:
            pass
        if leer(k) != v:
            try:
                p.SetSettings({k: v})
            except Exception:
                pass
        return leer(k) == v

    modo = leer('perfRenderCacheMode').lower()
    pedidos = []
    if go:
        if modo != 'smart':
            pedidos.append(('perfRenderCacheMode', 'smart'))
        for k in ('perfAutoRenderCacheEnable', 'perfAutoRenderCacheFuEffect', 'perfAutoRenderCacheTransition', 'perfAutoRenderCacheComposite'):
            pedidos.append((k, '1'))
        t = num(leer('perfAutoRenderCacheAfterTime'))
        if t is not None and t > (num(despues) or 2):
            pedidos.append(('perfAutoRenderCacheAfterTime', despues))
    else:
        if modo == 'none':
            pedidos.append(('perfRenderCacheMode', 'user'))
        if leer('perfAutoRenderCacheEnable') == '0':
            pedidos.append(('perfAutoRenderCacheEnable', '1'))
    cambios, fallidos = {}, []
    for k, v in pedidos:
        antes = leer(k)
        if antes == v:
            continue
        if poner(k, v):
            cambios[k] = [antes, v]
        else:
            fallidos.append(k)

    patron = re.compile(r'^[A-Z]{2,3}(-(CTX|MAIN|CMP|EMOJI|[KT]\d+))?$')

    def nuestra(nombre):
        cod = str(nombre or '').rsplit(' · ', 1)[-1].strip().upper()
        return cod.startswith(('PRO-', 'FX-')) or bool(patron.match(cod))

    def es_on(v):
        s = str(v).strip().lower()
        return not (s in ('off', 'false', '0', '0.0', 'none', '-1', '-1.0') or 'disabl' in s or 'auto' in s)     # -1 = CACHE_AUTO_ENABLED

    try:                                                   # v5.56: la constante de la API primero (las cadenas devuelven False en 21.1.2)
        valores = [resolve.CACHE_ENABLED, 1.0] + [v for v in valores]
    except Exception:
        valores = [1.0] + [v for v in valores]

    def con_fusion(it):
        try:
            return int(it.GetFusionCompCount() or 0) > 0
        except Exception:
            return True

    def activo(it):
        try:
            return it.GetClipEnabled() is not False
        except Exception:
            return True

    st = {'valor': None, 'lectura': None, 'antes': None, 'sondeos': 0}

    def marcar(it):
        if st['valor'] is not None:
            try:
                return bool(it.SetFusionOutputCache(st['valor']))
            except Exception:
                return False
        if st['sondeos'] >= 3:
            return False
        st['sondeos'] += 1
        try:
            st['antes'] = str(it.GetIsFusionOutputCacheEnabled())
        except Exception:
            pass
        for v in valores:
            try:
                ok = bool(it.SetFusionOutputCache(v))
            except Exception:
                ok = False
            if not ok:
                continue
            try:
                g = it.GetIsFusionOutputCacheEnabled()
            except Exception:
                g = None
            if g is None or g == '' or es_on(g):
                st['valor'], st['lectura'] = v, (None if g is None else str(g))
                return True
        return False

    marcados = fallos = cuadros = 0
    pistas = []
    for i in range(1, int(tl.GetTrackCount('video') or 0) + 1):
        nombre = str(tl.GetTrackName('video', i) or '')
        try:
            if tl.GetIsTrackEnabled('video', i) is False:
                continue
        except Exception:
            pass
        if i > 1 and not (go or nuestra(nombre)):
            continue
        n_pista = 0
        for it in (tl.GetItemListInTrack('video', i) or []):
            if not activo(it):
                continue
            if i == 1:
                try:
                    comps = [str(c) for c in (it.GetFusionCompNameList() or [])]
                except Exception:
                    comps = []
                if not comps or not (go or any(c.startswith('CineCaptions') for c in comps)):
                    continue
            elif not con_fusion(it):
                continue
            if marcar(it):
                marcados += 1
                n_pista += 1
                try:
                    cuadros += int(it.GetDuration() or 0)
                except Exception:
                    pass
            else:
                fallos += 1
        if n_pista:
            pistas.append([nombre, n_pista])
    try:
        uid = str(p.GetUniqueId() or '')
    except Exception:
        uid = ''
    try:
        fps = str(tl.GetSetting('timelineFrameRate') or '')
    except Exception:
        fps = ''
    foto = {}                                              # v5.56: dónde estaba Resolve al marcar (la reproducción diferida solo va si nada cambió)
    for k, f in (('timeline', lambda: tl.GetName()), ('tc', lambda: tl.GetCurrentTimecode()), ('pagina', lambda: resolve.GetCurrentPage()),
                 ('dur_s', lambda: round((tl.GetEndFrame() - tl.GetStartFrame()) / (float(fps) or 30.0), 1))):
        try:
            foto[k] = f()
        except Exception:
            pass
    res.update(foto)
    res.update(ok=True, proyecto=nombre_p, go=bool(go), uid=uid, ubicacion=leer('perfCacheClipsLocation'), modo=leer('perfRenderCacheMode'),
               despues_s=leer('perfAutoRenderCacheAfterTime'), fondo=leer('perfAutoRenderCacheEnable'), cambios=cambios, fallidos=fallidos,
               marcados=marcados, fallos=fallos, cuadros=cuadros, valor=st['valor'], lectura=st['lectura'], antes=st['antes'], pistas=pistas, fps=fps)
    return res
'''


def codigo_studio(go=None):
    """El código que corre dentro de Resolve (Studio) para una pasada. `go`: None = lo decide el nombre del proyecto; True/False lo fuerza (arnés)."""
    return _PASADA + '\nresult = _fluidez(resolve, project, %r, %r, %r)\n' % (go, VALORES_ON, DESPUES_S_GO)


def es_proyecto_go(nombre):
    return bool(_PROYECTO_GO.match(str(nombre or '')))


def preparar(go=None, timeout=50):
    """La pasada de fluidez en el timeline abierto (al final de GO). Devuelve el informe de Resolve (dict con ok, marcados, cuadros, uid…) o
    {'ok': False, 'error': …}. Nunca lanza."""
    try:
        import resolve_bridge
        if resolve_bridge._mcp_conectado():
            import resolve_mcp
            ok, r, err = resolve_mcp.script(codigo_studio(go), timeout=timeout)
            if ok and isinstance(r, dict):
                r['camino'] = 'mcp'
                return r
            return {'ok': False, 'error': str(err or r), 'camino': 'mcp'}
    except Exception as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}', 'camino': 'mcp'}
    try:                                                   # Free: el Puente corre CineCaptions_Vista.lua (acción «cabezal» + fluidez)
        import archivos_seguros
        import resolve_bridge
        import sidecar_lua
        ruta = resolve_bridge.CARPETA_COMPARTIDA / 'vista_orden.json'
        orden = {'accion': 'cabezal', 'fluidez': True, 'valores': list(VALORES_ON), 'despues': DESPUES_S_GO}
        if go is not None:
            orden['go'] = bool(go)
        archivos_seguros.escribir_json(ruta, orden)
        sidecar_lua.escribir_sidecar(ruta, orden)
        desde = time.time()
        ok, msg = resolve_bridge.ejecutar('vista', timeout=timeout)
        rep = resolve_bridge.ultimo_reporte(desde=desde) or {}
        vista = rep.get('vista') if isinstance(rep, dict) else None
        flu = vista.get('fluidez') if isinstance(vista, dict) else None
        if isinstance(flu, dict):
            flu['camino'] = 'puente'
            return flu
        return {'ok': False, 'camino': 'puente',
                'error': str(msg) if not ok else 'el script de vista no trajo «fluidez» (¿CineCaptions_Vista.lua de otra versión?)'}
    except Exception as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}', 'camino': 'puente'}


def carpeta_cache(info):
    """La carpeta de caché de render del proyecto (CacheClip/<uid>) o None si no aparece. Resolve la crea al abrir el proyecto (con Info.txt)."""
    if not isinstance(info, dict):
        return None
    uid = str(info.get('uid') or '').strip()
    if not uid:
        return None
    bases = []
    ub = str(info.get('ubicacion') or '').strip()
    if ub:
        bases += [Path(ub) / 'CacheClip', Path(ub)]
    casa = Path.home()
    bases += [casa / 'Videos' / 'CacheClip', casa / 'Movies' / 'CacheClip']
    for b in bases:
        c = b / uid
        try:
            if c.is_dir():
                return c
        except OSError:
            continue
    return None


def contar_cuadros(carpeta, desde=0.0, por_carpeta=False):
    """Cuántos cuadros de caché (*.dvcc) hay en la carpeta (con subcarpetas) escritos desde `desde` (time.time()). por_carpeta=True: (total,
    {SALIDA_CLIPS | COMPUESTO | '': cuadros}) según la carpeta que CONTIENE cada .dvcc (en 21.1.2 «SourceOne» está 4 niveles más abajo y
    «Sequence» 2: agrupar por la de primer nivel daba solo el timeline y mezclaba los dos)."""
    n, por = 0, {}
    pila = [str(carpeta)]
    while pila:
        d = pila.pop()
        clave = os.path.basename(d)
        clave = clave if clave in (SALIDA_CLIPS, COMPUESTO) else ''
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            pila.append(e.path)
                        elif e.name.endswith('.dvcc') and e.stat().st_mtime >= desde:
                            n += 1
                            por[clave] = por.get(clave, 0) + 1
                    except OSError:
                        pass
        except OSError:
            pass
    return (n, por) if por_carpeta else n


def tope_espera(cuadros):
    return min(TOPE_MAX_S, max(TOPE_MIN_S, 10.0 + float(cuadros) / FPS_CACHE))


def esperar_cache(info, al_estado=None, desde=None, tope_s=None, arranque_s=None, quieto_s=None, paso_s=1.0, carpeta=None, cancelar=None):
    """Espera a que Resolve llene la caché de nuestros clips. Devuelve {'estado': lista|quieta|tiempo|no_empezo|nada|sin_carpeta|cancelada,
    'cuadros' (salida de los clips), 'total', 'objetivo', 'segundos', 'carpeta'}. Solo mira el disco: no habla con Resolve (la caché en segundo
    plano necesita a Resolve en reposo). `cancelar()` True = deja de esperar (otro GO empezó)."""
    objetivo = int((info or {}).get('cuadros') or 0) if isinstance(info, dict) else 0
    if objetivo <= 0:
        return {'estado': 'nada', 'cuadros': 0, 'objetivo': 0, 'segundos': 0.0}
    carpeta = carpeta or carpeta_cache(info)
    if carpeta is None:
        return {'estado': 'sin_carpeta', 'cuadros': 0, 'objetivo': objetivo, 'segundos': 0.0}
    desde = time.time() - 5 if desde is None else desde
    try:
        despues = float(info.get('despues_s') or 5)
    except (TypeError, ValueError):
        despues = 5.0
    tope = tope_s if tope_s is not None else tope_espera(objetivo)
    arranque = arranque_s if arranque_s is not None else despues + ARRANQUE_EXTRA_S
    quieto = quieto_s if quieto_s is not None else QUIETO_S
    t0 = time.monotonic()
    ultimo_cambio, previos, avisado = t0, -1, -10.0
    estado, hechos, clips = 'tiempo', 0, 0
    while True:
        if cancelar is not None and cancelar():
            estado = 'cancelada'
            break
        ahora = time.monotonic()
        hechos, por = contar_cuadros(carpeta, desde, por_carpeta=True)
        if SALIDA_CLIPS in por or COMPUESTO in por:
            clips = por.get(SALIDA_CLIPS, 0)                # (el compuesto nunca cuenta como salida de clips)
        else:
            clips = hechos                                  # (otra versión, con otras carpetas: el total)
        if hechos != previos:
            previos, ultimo_cambio = hechos, ahora
        # v5.56: lista = la salida de NUESTROS clips en caché (el objetivo es la suma de sus duraciones); antes se comparaba el total (salida +
        # compuesto) con el objetivo y se daba por lista con un 30 % de los clips sin cachear. El compuesto no se espera: crece sin parar hasta
        # el tope y con los clips en caché Resolve ya reproduce fluido
        if clips >= objetivo * 0.99:
            estado = 'lista'
            break
        if hechos == 0 and ahora - t0 > arranque:
            estado = 'no_empezo'
            break
        if hechos > 0 and ahora - ultimo_cambio > quieto:
            estado = 'quieta'
            break
        if ahora - t0 > tope:
            estado = 'tiempo'
            break
        if al_estado and ahora - avisado >= 2.0:
            avisado = ahora
            try:
                al_estado(tr('Preparando la reproducción fluida: Resolve guarda los captions en caché ({p} %)…', p=min(99, int(100 * clips / objetivo))))
            except Exception:
                pass
        time.sleep(paso_s)
    return {'estado': estado, 'cuadros': clips, 'total': hechos, 'objetivo': objetivo, 'segundos': round(time.monotonic() - t0, 1),
            'carpeta': str(carpeta)}


def resumen(info):
    """Una línea para el Registro."""
    if not isinstance(info, dict) or not info.get('ok'):
        return tr('Reproducción fluida: no pude preparar la caché de Resolve ({e}).', e=str((info or {}).get('error') or '?')[:160])
    partes = [tr('{n} clips con caché de Fusion', n=info.get('marcados', 0))]
    if info.get('valor'):
        partes.append(tr('valor «{v}»', v=info['valor']) + (f" → {info['lectura']}" if info.get('lectura') else ''))
    elif info.get('marcados', 0) == 0 and info.get('fallos'):
        partes.append(tr('Resolve no aceptó ningún valor de caché ({n} clips)', n=info['fallos']))
    partes.append(tr('caché del proyecto «{m}»', m=info.get('modo') or '?'))
    if info.get('cambios'):
        partes.append(tr('cambié {k}', k=', '.join(f'{k} {a or "—"}→{b}' for k, (a, b) in info['cambios'].items())))
    if info.get('fallidos'):
        partes.append(tr('Resolve no aceptó {k}', k=', '.join(info['fallidos'])))
    esp = info.get('espera')
    if isinstance(esp, dict) and esp.get('estado') == 'sin_carpeta':
        partes.append(tr('no encontré la carpeta de caché: reproduzco sin esperar'))
    elif isinstance(esp, dict) and esp.get('objetivo'):
        partes.append(tr('caché: {h} de {o} cuadros en {s} s ({e})', h=min(esp.get('cuadros', 0), esp['objetivo']), o=esp['objetivo'],
                         s=esp.get('segundos', 0), e=esp.get('estado')) + (f" · {esp['total']}" if esp.get('total') else ''))
    elif isinstance(esp, dict) and esp.get('estado'):
        partes.append(str(esp['estado']))
    if info.get('no_reproduzco'):
        partes.append(tr('no reproduzco: {m}', m=info['no_reproduzco']))
    return tr('Reproducción fluida: ') + ' · '.join(partes) + '.'


_SIN_CAMBIOS = r'''
p = resolve.GetProjectManager().GetCurrentProject()
tl = p.GetCurrentTimeline() if p else None
result = {'uid': str(p.GetUniqueId() or '') if p else '', 'timeline': tl.GetName() if tl else None,
          'tc': tl.GetCurrentTimecode() if tl else None, 'pagina': resolve.GetCurrentPage()}
'''


def sin_cambios(info):
    """v5.56: ¿Resolve sigue como lo dejó GO (mismo proyecto, timeline y cabezal, y en la página Edit o la de entonces)? (bool, motivo). La
    reproducción diferida solo va si nada cambió: si el usuario ya trabaja en Resolve (otro timeline, la página Color, movió el cabezal,
    escribe en el Inspector…) no se le quita el foco ni se le reproduce encima. Sin el MCP (Free) no hay forma barata de mirarlo: solo con
    la caché «lista» (si Resolve se paró a medias, es que alguien lo estaba usando)."""
    try:
        import resolve_bridge
        if not resolve_bridge._mcp_conectado():
            lista = (info.get('espera') or {}).get('estado') == 'lista'
            return lista, ('' if lista else tr('Resolve se usó mientras guardaba la caché'))
        import resolve_mcp
        ok, r, err = resolve_mcp.script(_SIN_CAMBIOS, timeout=15)
    except Exception as e:
        return False, f'{type(e).__name__}'
    if not ok or not isinstance(r, dict):
        return False, tr('Resolve no contestó ({e})', e=str(err)[:80])
    for k, que in (('uid', tr('cambiaste de proyecto')), ('timeline', tr('cambiaste de timeline')), ('tc', tr('moviste el cabezal'))):
        if info.get(k) not in (None, '') and str(r.get(k)) != str(info.get(k)):
            return False, que
    if str(r.get('pagina') or '') not in ('edit', str(info.get('pagina') or 'edit')):
        return False, tr('estás en otra página de Resolve')
    return True, ''


def esperar_y_reproducir(info, reproducir, al_estado=None, sigue=None, desde=None):
    """v5.56: DESPUÉS de GO (en un hilo): espera a que Resolve llene la caché de los clips que marcó `preparar` (solo mira el disco) y luego
    llama a `reproducir()` (colocacion.reproducir_desde_inicio sin otra pasada). `sigue()` False = otro GO empezó: ni espera ni reproduce.
    Así GO dice «Listo» en su tiempo (solo captions ~20 s) y la reproducción automática empieza ya fluida (antes, al instante y a tirones).
    Devuelve el informe con 'espera' y 'reproducido'. Nunca lanza; lo deja en el Registro."""
    info = dict(info or {})
    try:
        info['espera'] = esperar_cache(info, al_estado=al_estado, desde=desde, cancelar=(lambda: not sigue()) if sigue else None)
    except Exception as e:
        info['espera'] = {'estado': f'error {type(e).__name__}'}
    info['reproducido'] = False
    if sigue is None or sigue():
        try:
            igual, motivo = sin_cambios(info)
            if not igual:
                info['no_reproduzco'] = motivo
            elif sigue is None or sigue():
                if al_estado:
                    al_estado(tr('Reproduciendo el timeline desde el principio…'))
                info['reproducido'] = reproducir()
        except Exception:
            pass
    try:
        import registro
        registro.info(resumen(info), 'GO · fluidez')
    except Exception:
        pass
    return info


def antes_de_reproducir(al_estado=None, esperar=True):
    """Al final de GO, justo antes de pulsar «Reproducir»: la pasada (marcar nuestros clips + caché del proyecto) y la espera a la caché.
    Devuelve el informe (con 'espera'). Nunca lanza; lo deja en el Registro."""
    desde = time.time() - 2
    try:
        if al_estado:
            al_estado(tr('Preparando la reproducción fluida en Resolve…'))
    except Exception:
        pass
    info = preparar()
    if info.get('ok') and esperar:
        try:
            info['espera'] = esperar_cache(info, al_estado=al_estado, desde=desde)
        except Exception as e:
            info['espera'] = {'estado': f'error {type(e).__name__}'}
    try:
        import registro
        (registro.info if info.get('ok') else registro.aviso)(resumen(info), 'GO · fluidez')
    except Exception:
        pass
    try:
        if al_estado:
            al_estado(tr('Reproduciendo el timeline desde el principio…'))
    except Exception:
        pass
    return info
