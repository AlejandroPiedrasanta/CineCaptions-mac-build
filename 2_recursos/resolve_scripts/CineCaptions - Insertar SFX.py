#!/usr/bin/env python3
# CineCaptions · By Cinema Productions
# 2_recursos/resolve_scripts/CineCaptions - Insertar SFX.py — importa un sonido y lo coloca en el cabezal (Studio).
"""
CineCaptions - Insertar SFX.py
--------------------------------------------
Script que corre DENTRO de Resolve (Workspace > Scripts > Utility).

Lee la orden que le dejo la ventana "Estudio de sonidos" en
    ~/DaVinciSubtitles/sfx_pendiente.json
y hace tres cosas:
  1) importa ese .wav al Media Pool (una sola vez por archivo);
  2) busca en el timeline la primera pista de audio VACIA en el playhead;
     si no hay ninguna vacia, agrega una nueva llamada 'SFX-Modificado';
  3) coloca el clip en el playhead con su duracion natural.

La orden se borra al terminar bien: correr dos veces seguidas no duplica el
sonido en el timeline.

Por que este puente y no una conexion directa: la version gratuita de
Resolve (19.1+) cerro el scripting externo. Solo se puede correr Python
DESDE ADENTRO de la app.
"""

import json
import os
import time
from pathlib import Path

# Alineada con APP_VERSION desde la v1.0.59 (estaba en "2026-08-06" y la
# carpeta parecia una mezcla de builds — la misma leccion de los
# auxiliares .lua).
VERSION = "5.4.19 (insertar SFX)"

CARPETA_COMPARTIDA = Path.home() / "DaVinciSubtitles"
ARCHIVO_PENDIENTE = CARPETA_COMPARTIDA / "sfx_pendiente.json"
ARCHIVO_HECHO = CARPETA_COMPARTIDA / "sfx_pendiente.hecho.json"

NOMBRE_PISTA_NUEVA = "SFX-Modificado"


def fail(msg):
    print(f"[Insertar SFX] ERROR: {msg}")
    raise SystemExit(1)


# --------------------------------------------------------------------------
# Timeline: buscar hueco en el playhead
# --------------------------------------------------------------------------

def _tc_a_frames(tc, fps):
    """DaVinci devuelve el timecode como 'HH:MM:SS:FF'.

    v1.0.62: en un timeline DROP-FRAME el ultimo separador es ';'
    ('01:00:00;12') y el split por ':' daba 3 partes -> 0 EN SILENCIO:
    delta negativo, forzado a 0, y el clip aterrizaba al INICIO del
    timeline en vez del cabezal. Se acepta ';' como separador.
    """
    partes = tc.replace(";", ":").split(":")
    if len(partes) != 4:
        return 0
    h, m, s, f = (int(p) for p in partes)
    return int(round(((h * 3600 + m * 60 + s) * fps) + f))


def _hay_hueco(timeline, indice_pista, frame_inicio, duracion, fps):
    """True si en esa pista de audio no hay ningun clip entre
    [frame_inicio, frame_inicio + duracion). Se mira una margen chica
    (2 frames) para tolerar solapes triviales."""
    inicio_tl = timeline.GetStartFrame()
    items = timeline.GetItemListInTrack("audio", indice_pista) or []
    fin = frame_inicio + duracion
    margen = 2
    for it in items:
        try:
            a = int(it.GetStart())
            b = int(it.GetEnd())
        except Exception:
            continue
        # GetStart/GetEnd devuelven frames absolutos del proyecto.
        if b - margen <= frame_inicio + margen:
            continue
        if a + margen >= fin - margen:
            continue
        return False
    return True


def _buscar_pista_vacia(timeline, frame_inicio, duracion, fps):
    """Devuelve el indice de la primera pista de audio que este libre en el
    rango pedido, o None si no hay ninguna disponible."""
    cantidad = timeline.GetTrackCount("audio")
    for i in range(1, cantidad + 1):
        try:
            # Saltamos pistas silenciadas o bloqueadas: si no, insertar ahi
            # da un clip que despues nadie ve.
            if timeline.GetIsTrackLocked("audio", i):
                continue
        except Exception:
            pass
        if _hay_hueco(timeline, i, frame_inicio, duracion, fps):
            return i
    return None


def _crear_pista_sfx(timeline):
    """Agrega una pista de audio estereo al final y le pone el nombre."""
    antes = timeline.GetTrackCount("audio")
    ok = False
    for args in (("audio", "stereo"), ("audio",)):
        try:
            if timeline.AddTrack(*args):
                ok = True
                break
        except Exception:
            continue
    if not ok:
        return None
    nueva = timeline.GetTrackCount("audio")
    if nueva == antes:            # AddTrack devolvio true pero no sumo
        nueva = antes + 1
    try:
        timeline.SetTrackName("audio", nueva, NOMBRE_PISTA_NUEVA)
    except Exception:
        pass
    return nueva


# --------------------------------------------------------------------------
# Media Pool: importar sin duplicar
# --------------------------------------------------------------------------

def _importar_una_vez(media_pool, ruta_wav):
    """Si el WAV ya esta en el Media Pool, devuelve ese item; si no, lo
    importa. Compara por RUTA completa (v3.3.0; antes por nombre, y un
    clip desconectado con ese nombre se reusaba para siempre)."""
    # v3.3.0: la MISMA RUTA, no el mismo nombre (ver el gemelo .lua): por
    # nombre se reusaba para siempre un clip que quedo desconectado.
    buscada = os.path.normcase(os.path.normpath(str(ruta_wav)))
    root = media_pool.GetRootFolder()

    def buscar(folder):
        for clip in folder.GetClipList():
            try:
                ruta = clip.GetClipProperty("File Path") or ""
                if ruta and os.path.normcase(os.path.normpath(ruta)) == buscada:
                    return clip
            except Exception:
                continue
        for sub in folder.GetSubFolderList():
            r = buscar(sub)
            if r:
                return r
        return None

    existente = buscar(root)
    if existente:
        return existente

    try:
        nuevos = media_pool.ImportMedia([str(ruta_wav)])
    except Exception as e:
        print(f"[Insertar SFX] ImportMedia fallo: {e}")
        return None
    return nuevos[0] if nuevos else None


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def _frames_de_audio(item, fps):
    """Duracion de un clip de audio del Media Pool en fotogramas. v5.4: Resolve 21 deja VACIA la propiedad 'Frames' en los
    clips de audio (solo da 'Duration', HH:MM:SS:FF): sin esto todo sonido se cortaba a 0,5 s (riser, boom, recortes)."""
    try:
        n = int(float(item.GetClipProperty("Frames") or 0))
        if n >= 1:
            return n
    except Exception:
        pass
    try:
        partes = str(item.GetClipProperty("Duration") or "").replace(";", ":").split(":")
        if len(partes) == 4:
            h, m, s, f = (int(p) for p in partes)
            return (h * 3600 + m * 60 + s) * int(round(fps)) + f
    except Exception:
        pass
    return 0



def main():
    try:
        resolve
    except NameError:
        fail("Este script debe correrse desde Resolve: Workspace > Scripts "
             "> Edit > CineCaptions - Insertar SFX")

    print(f"[Insertar SFX] versión {VERSION}")

    if not ARCHIVO_PENDIENTE.exists():
        # Se distinguen los dos caminos a proposito: este script inserta UN
        # sonido suelto, y al usuario le confundia correrlo esperando los
        # efectos por bloque, que los coloca el script de subtitulos.
        fail(
            "No hay ningún sonido pendiente.\n"
            "  Este script inserta UN sonido suelto: elígelo primero en la "
            "ventana 'Estudio de sonidos', retócalo con el pad, y presiona "
            "'Enviar a Resolve'.\n"
            "  Si lo que querías son los efectos POR BLOQUE, no hace falta "
            "correr nada a mano: marca 'Agregar efectos de sonido por bloque' "
            "en el programa y genera; se colocan junto con los subtítulos."
        )

    try:
        pendiente = json.loads(ARCHIVO_PENDIENTE.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"La orden pendiente está dañada: {e}")

    wav = Path(pendiente.get("video_path") or pendiente.get("wav") or "")
    if not wav or not wav.exists():
        fail(f"No encuentro el WAV que la ventana dejó: {wav}")

    # 'resolve' puede existir y estar hueco (metodos a None) si Resolve tiene
    # el scripting externo apagado. Ver la explicacion larga en
    # "CineCaptions.py".
    _get_pm = getattr(resolve, "GetProjectManager", None)
    if not callable(_get_pm):
        fail("Resolve no está aceptando scripts externos. Abre "
             "Preferencias > Sistema > General, pon «External scripting "
             "using» en «Local» y reinicia Resolve.")
    _pm = _get_pm()
    if _pm is None:
        fail("Resolve no me dio el gestor de proyectos. Cierra Resolve por "
             "completo, vuelve a abrirlo e inténtalo otra vez.")

    project = _pm.GetCurrentProject()
    if not project:
        fail("No hay proyecto abierto en Resolve.")
    timeline = project.GetCurrentTimeline()
    if not timeline:
        fail("No hay timeline activo.")

    fps = float(timeline.GetSetting("timelineFrameRate"))
    tc_actual = timeline.GetCurrentTimecode() or "01:00:00:00"
    try:
        tc_inicio = timeline.GetStartTimecode() or "01:00:00:00"
    except Exception:
        tc_inicio = "01:00:00:00"
    start_frame = int(timeline.GetStartFrame() or 0)

    # Calculamos el offset del cabezal desde el inicio del timeline
    # comparando los timecodes, y despues lo sumamos al frame absoluto
    # de arranque. Asi funciona sin importar si GetCurrentTimecode()
    # devuelve TC absoluto ('01:00:05:00') o relativo ('00:00:05:00'),
    # y respeta el startFrame interno del proyecto.
    frames_actual = _tc_a_frames(tc_actual, fps)
    frames_inicio = _tc_a_frames(tc_inicio, fps)
    delta = frames_actual - frames_inicio
    if delta < 0:
        # El playhead es anterior al inicio del timeline: caso raro,
        # forzamos al arranque para no colocar el clip fuera.
        delta = 0
    frame_absoluto = start_frame + delta

    print(f"  Timeline: {timeline.GetName()}  |  fps: {fps}")
    print(f"  Playhead TC: {tc_actual}  |  Inicio TC: {tc_inicio}")
    print(f"  start_frame: {start_frame}  |  delta: {delta}  |  frame_absoluto: {frame_absoluto}")
    print(f"  WAV: {wav}")

    media_pool = project.GetMediaPool()
    item = _importar_una_vez(media_pool, wav)
    if not item:
        fail("No pude importar el WAV al Media Pool.")

    duracion = _frames_de_audio(item, fps)
    if duracion < 1:
        duracion = max(1, int(round(0.5 * fps)))

    indice = _buscar_pista_vacia(timeline, frame_absoluto, duracion, fps)
    creada = False
    if indice is None:
        print(f"  Todas las pistas tienen algo en el playhead; creando "
              f"'{NOMBRE_PISTA_NUEVA}'.")
        indice = _crear_pista_sfx(timeline)
        creada = True
        if not indice:
            fail("No pude crear una pista de audio.")
    else:
        try:
            nombre = timeline.GetTrackName("audio", indice)
        except Exception:
            nombre = f"A{indice}"
        print(f"  Uso la pista vacía A{indice} ('{nombre}').")

    clip_info = {
        "mediaPoolItem": item,
        "startFrame": 0,
        "endFrame": duracion - 1,
        "trackIndex": indice,
        "mediaType": 2,          # 2 = audio
        "recordFrame": frame_absoluto,
    }
    try:
        colocados = media_pool.AppendToTimeline([clip_info])
    except Exception as e:
        fail(f"AppendToTimeline falló: {e}")
    if not colocados:
        fail("Resolve no colocó el clip (posiblemente hay algo pisando el "
             "hueco).")

    # Al terminar bien: la orden ya no vale.
    try:
        ARCHIVO_HECHO.write_text(json.dumps({
            **pendiente,
            "colocado_en_pista": indice,
            "pista_creada": creada,
            "insertado_en": time.time(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        ARCHIVO_PENDIENTE.unlink()
    except Exception:
        pass

    print(f"  LISTO: '{wav.name}' insertado en la pista A{indice}, "
          f"frame {frame_absoluto}.")


if __name__ == "__main__":
    main()
