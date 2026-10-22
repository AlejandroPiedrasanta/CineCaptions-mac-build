# CineCaptions · By Cinema Productions
# 2_recursos/resolve_scripts/CineCaptions - Vista Real.py — renderiza las vistas previas reales en un timeline temporal (lo lanza el MCP).
"""
CineCaptions - Vista Real.py  (v5.2)
------------------------------------
Las vistas previas RENDERIZADAS de verdad por Resolve (pedido: «la pestaña de
estilos y composición debe renderizar la vista previa real de los .drb»).

Lo corre la app por el MCP de Resolve (resolve_mcp.ejecutar_py), nunca desde
el menu. Lee el pedido de ~/DaVinciSubtitles/vista_real_pedido.json y deja
las imagenes y vista_real_resultado.json en la carpeta de salida.

Dos modos:
  * 'pack'    un timeline temporal vacio con la resolucion del formato (9:16
              o 16:9): cada set del pack con el texto de muestra, y varios
              fotogramas de su animacion de entrada (la vista animada de la
              pestaña Estilos).
  * 'bloques' una COPIA temporal del timeline actual (con tu video debajo):
              los bloques de muestra de GO en sus tiempos reales, y un
              fotograma de cada uno — la vista previa de GO, real.

Todo lo temporal se marca con el nombre de los temporales del gemelo
(MARCA_TIMELINE_TEMPORAL): NO se borra en caliente (DeleteTimelines sobre un
timeline recien des-seleccionado cerro Resolve una vez) y lo limpia la
siguiente corrida. El timeline, el cabezal y la carpeta del Media Pool del
usuario vuelven a quedar como estaban.
"""
import importlib.util
import json
import os
import time
from pathlib import Path

SHARED = Path.home() / 'DaVinciSubtitles'
PEDIDO = SHARED / 'vista_real_pedido.json'
VERSION = '5.37 (vista real)'


def _gemelo():
    """El modulo del gemelo de subtitulos (CineCaptions.py, en esta carpeta)."""
    ruta = Path(__file__).resolve().parent / 'CineCaptions.py'
    spec = importlib.util.spec_from_file_location('_cinecaptions_gemelo_vista', str(ruta))
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__['resolve'] = resolve        # noqa: F821 (lo pone el MCP)
    mod.__dict__['project'] = project        # noqa: F821
    spec.loader.exec_module(mod)
    return mod


def _tc(tl, frame):
    """Timecode de un fotograma absoluto (con drop frame si el timeline lo usa)."""
    fps = float(tl.GetSetting('timelineFrameRate') or 24)
    entero = int(round(fps))
    df = ';' in str(tl.GetStartTimecode() or '')
    frame = int(frame)
    if df and entero in (30, 60):
        drop = 2 if entero == 30 else 4
        diez = entero * 600 - drop * 9
        minuto = entero * 60 - drop
        d, m = divmod(frame, diez)
        frame += drop * 9 * d + (drop * ((m - drop) // minuto) if m > drop else 0)
    f = frame % entero
    s = frame // entero
    return '%02d:%02d:%02d%s%02d' % (s // 3600, s // 60 % 60, s % 60, ';' if df else ':', f)


def _ir_a(tl, frame):
    try:
        return bool(tl.SetCurrentTimecode(_tc(tl, frame)))
    except Exception:
        return False


def _exportar(tl, frame, ruta):
    if not _ir_a(tl, frame):
        return None
    # Fusion necesita un instante para el primer fotograma de un clip recien puesto
    for intento in range(3):
        try:
            if project.ExportCurrentFrameAsStill(str(ruta)) and os.path.exists(str(ruta)):   # noqa: F821
                return str(ruta)
        except Exception:
            pass
        time.sleep(0.15)
    return None


def _set_de(sets, numero):
    for s in sets:
        if s.get('numero') == numero:
            return s
    return None


def main():
    g = _gemelo()
    pedido = json.loads(PEDIDO.read_text(encoding='utf-8'))
    salida = Path(pedido['salida'])
    salida.mkdir(parents=True, exist_ok=True)
    media_pool = project.GetMediaPool()                    # noqa: F821
    resultado = {'version': VERSION, 'ok': False, 'imagenes': [], 'avisos': []}
    previo = project.GetCurrentTimeline()                  # noqa: F821
    try:
        tc_previo = previo.GetCurrentTimecode() if previo else None
    except Exception:
        tc_previo = None
    try:
        carpeta_previa = media_pool.GetCurrentFolder()
    except Exception:
        carpeta_previa = None
    temporal = None
    try:
        try:
            g._limpiar_temporales(project, media_pool)    # noqa: F821
        except Exception:
            pass
        formato = pedido.get('formato') or 'v'
        carpeta_bin, aviso = g.preparar_pack_drt(project, media_pool, pedido['pack'], formato,   # noqa: F821
                                                 pedido.get('drt') or '', pedido.get('drb'))
        if aviso:
            resultado['avisos'].append(str(aviso))
        if carpeta_bin is None:
            raise RuntimeError(aviso or 'no pude meter el pack en el Media Pool')
        sets, _ = g.buscar_sets_de_plantillas(media_pool, carpeta_bin)
        if not sets:
            raise RuntimeError('el pack no trae sets completos')
        try:
            media_pool.SetCurrentFolder(media_pool.GetRootFolder())
        except Exception:
            pass
        nombre = f"{g.MARCA_TIMELINE_TEMPORAL} · vista {time.strftime('%H%M%S')}"
        modo = pedido.get('modo') or 'pack'
        if modo == 'bloques' and previo is not None:
            temporal = previo.DuplicateTimeline(nombre)
        if temporal is None:
            modo_real = 'pack' if modo == 'pack' else ('guion' if modo == 'guion' else 'bloques_sin_video')
            temporal = media_pool.CreateEmptyTimeline(nombre)
            if temporal is None:
                raise RuntimeError('Resolve no creó el timeline temporal')
            ancho, alto = (1080, 1920) if formato == 'v' else (1920, 1080) if formato == 'h' else (1080, 1080)
            try:
                temporal.SetSetting('useCustomSettings', '1')
                temporal.SetSetting('timelineResolutionWidth', str(ancho))
                temporal.SetSetting('timelineResolutionHeight', str(alto))
            except Exception as e:
                resultado['avisos'].append(f'resolución: {e!r}')
        else:
            modo_real = 'bloques'
            # en la copia, las pistas de subtitulos de corridas anteriores se
            # apagan: la vista tiene que mostrar SOLO lo nuevo
            for i in range(1, int(temporal.GetTrackCount('video') or 0) + 1):
                try:
                    n = str(temporal.GetTrackName('video', i) or '').upper()
                    if n.endswith(('-CTX', '-MAIN', '-CMP', '-EMOJI')) or 'EMOJI' in n:
                        temporal.SetTrackEnable('video', i, False)
                except Exception:
                    pass
        project.SetCurrentTimeline(temporal)               # noqa: F821
        fps = float(temporal.GetSetting('timelineFrameRate') or 30)
        base_pistas = int(temporal.GetTrackCount('video') or 0)
        if modo_real == 'pack':
            base_pistas = 0
        for _ in range(3):
            temporal.AddTrack('video')
        pista = {'context': base_pistas + 1, 'main': base_pistas + 2, 'complement': base_pistas + 3}
        inicio_tl = int(temporal.GetStartFrame())
        textos = pedido.get('textos') or {'context': 'Así se', 'main': 'VE', 'complement': 'tu pack'}
        if modo_real == 'pack':
            dur = max(12, int(round(float(pedido.get('duracion_s') or 2.4) * fps)))
            cuadros = [float(c) for c in (pedido.get('cuadros') or [0.1, 0.3, 0.6, 1.2])]
            numeros = pedido.get('sets') or [s.get('numero') for s in sets]
            k = 0
            for numero in numeros:
                s = _set_de(sets, numero)
                if s is None:
                    continue
                record = inicio_tl + k * (dur + 6)
                puestos = 0
                for rol in ('context', 'main', 'complement'):
                    plantilla = s.get(rol)
                    if plantilla is None or not textos.get(rol):
                        continue
                    item, _ = g.colocar_medido(media_pool, temporal, plantilla, 0, dur, pista[rol], record, fps)
                    if item is not None:
                        g.set_text_on_clip(item, textos[rol])
                        puestos += 1
                if not puestos:
                    continue
                for j, c in enumerate(cuadros):
                    ruta = salida / f'set{int(numero):02d}_{j:02d}.png'
                    hecho = _exportar(temporal, record + min(dur - 1, int(round(c * fps))), ruta)
                    if hecho:
                        resultado['imagenes'].append({'set': int(numero), 'cuadro': j, 'ruta': hecho})
                k += 1
        elif modo_real == 'guion':
            # v5.10: UN bloque del estilo «guion» colocado con el MISMO place_guion_track que usa Generar (cada palabra su clip, su sitio y su momento),
            # y un fotograma a los segundos pedidos: «Comprobar en Resolve» del editor Creativo
            g.place_guion_track(temporal, media_pool, pedido['track'], None, fps, inicio_tl, project)         # noqa: F821
            for j, seg in enumerate(pedido.get('cuadros_s') or [0.6]):
                ruta = salida / f'guion_{j:02d}.png'
                hecho = _exportar(temporal, inicio_tl + int(round(float(seg) * fps)), ruta)
                if hecho:
                    resultado['imagenes'].append({'cuadro': j, 'ruta': hecho})
        else:
            marca = pedido.get('marca')
            base = int(marca) if marca is not None else inicio_tl
            for b, bloque in enumerate(pedido.get('bloques') or []):
                s = sets[b % len(sets)]
                ini = base + int(round(float(bloque['start']) * fps))
                dur = max(6, int(round((float(bloque['end']) - float(bloque['start'])) * fps)))
                for linea in bloque.get('lines') or []:
                    rol = linea.get('role')
                    plantilla = s.get(rol) or s.get('main')
                    if plantilla is None or not linea.get('text'):
                        continue
                    item, _ = g.colocar_medido(media_pool, temporal, plantilla, 0, dur, pista.get(rol, pista['main']), ini, fps)
                    if item is not None:
                        g.set_text_on_clip(item, linea['text'])
                ruta = salida / f'bloque_{b:02d}.png'
                hecho = _exportar(temporal, ini + min(dur - 1, int(round(0.6 * fps))), ruta)
                resultado['imagenes'].append({'bloque': b, 'ruta': hecho})
        resultado['ok'] = bool(resultado['imagenes'])
        resultado['modo'] = modo_real
        resultado['ancho'] = int(temporal.GetSetting('timelineResolutionWidth') or 0)
        resultado['alto'] = int(temporal.GetSetting('timelineResolutionHeight') or 0)
    except Exception as e:
        resultado['error'] = f'{type(e).__name__}: {e}'
    finally:
        try:
            if previo is not None:
                project.SetCurrentTimeline(previo)          # noqa: F821
                if tc_previo:
                    previo.SetCurrentTimecode(tc_previo)
        except Exception:
            pass
        try:
            if carpeta_previa is not None:
                media_pool.SetCurrentFolder(carpeta_previa)
        except Exception:
            pass
        (salida / 'vista_real_resultado.json').write_text(json.dumps(resultado, ensure_ascii=False, indent=1),
                                                          encoding='utf-8')
    if not resultado['ok']:
        raise SystemExit(resultado.get('error') or 'sin imágenes')
