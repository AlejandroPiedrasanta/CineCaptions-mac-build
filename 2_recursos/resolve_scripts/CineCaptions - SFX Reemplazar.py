#!/usr/bin/env python3
# CineCaptions · By Cinema Productions
# 2_recursos/resolve_scripts/CineCaptions - SFX Reemplazar.py — reemplaza el efecto de sonido bajo el cabezal (Studio).
"""
CineCaptions - SFX Reemplazar.py
---------------------------------------------
Gemelo de Studio de CineCaptions_SfxReemplazar.lua: sustituye el efecto de sonido
que esta BAJO EL CABEZAL por el sonido que el usuario eligio en el SFX
Lab (modo «Reemplazar», v1.0.62 — como el flujo de SickSFX que pidio
El usuario: aparcas el cabezal sobre un clip y picas el sonido nuevo).

La app deja la orden resuelta en
    ~/DaVinciSubtitles/sfx_reemplazo_pendiente.json   ({"wav": ruta})
y este script:
  1) lee la orden (sin orden: explica de donde sale);
  2) localiza el item de audio bajo el cabezal SOLO en pistas nuestras
     (SFX / SFX-Modificado / SFX-Marcadores) y SOLO si dura menos de
     DURACION_MAXIMA_SFX_SEGUNDOS — la regla suprema del producto es no
     destruir trabajo del usuario: un clip largo o en otra pista es, con
     altisima probabilidad, material suyo y NO SE TOCA (se dice);
  3) importa el sonido nuevo ANTES de borrar nada (si el import falla,
     el timeline queda intacto);
  4) borra el viejo y coloca el nuevo en el MISMO frame y la MISMA
     pista;
  5) borra la orden al terminar bien: correr dos veces no duplica.
"""

import json
import os
import time
from pathlib import Path

VERSION = "5.5.11 (sfx reemplazar)"

CARPETA_COMPARTIDA = Path.home() / "DaVinciSubtitles"
ARCHIVO_PENDIENTE = CARPETA_COMPARTIDA / "sfx_reemplazo_pendiente.json"
ARCHIVO_HECHO = CARPETA_COMPARTIDA / "sfx_reemplazo_pendiente.hecho.json"

# Pistas que el producto considera SUYAS (comparadas en mayusculas y sin
# espacios, como hace el gemelo de subtitulos con la pista SFX). Fuera de
# ellas no se reemplaza NADA.
PISTAS_NUESTRAS = ("SFX", "SFX-MODIFICADO", "SFX-MARCADORES")

# Un efecto nuestro nunca dura mas que esto (misma constante que los
# gemelos de subtitulos): un clip mas largo en una pista reutilizada es,
# con altisima probabilidad, contenido del usuario. Si no se puede
# confirmar la duracion, tampoco se arriesga.
DURACION_MAXIMA_SFX_SEGUNDOS = 20


def fail(msg):
    print(f"[SFX Reemplazar] ERROR: {msg}")
    raise SystemExit(1)


def _tc_a_frames(tc, fps):
    """'HH:MM:SS:FF' -> frames. Acepta ';' (drop-frame): con ':' fijo el
    parseo daba 0 en silencio y el cabezal 'estaba' al inicio."""
    partes = str(tc).replace(";", ":").split(":")
    if len(partes) != 4:
        return 0
    h, m, s, f = (int(p) for p in partes)
    return int(round(((h * 3600 + m * 60 + s) * fps) + f))


def _importar_una_vez(media_pool, ruta_wav):
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
        print(f"[SFX Reemplazar] ImportMedia fallo: {e}")
        return None
    return nuevos[0] if nuevos else None


def _nombre_de_pista(timeline, indice):
    try:
        return str(timeline.GetTrackName("audio", indice) or "")
    except Exception:
        return ""


def _es_pista_nuestra(nombre):
    return nombre.strip().upper() in PISTAS_NUESTRAS


def _item_bajo_el_cabezal(timeline, frame, fps):
    """(item, pista, inicio) del SFX nuestro bajo el cabezal, o None.

    Recorre SOLO las pistas nuestras. Devuelve tambien las pistas
    nuestras donde habia un clip bajo el cabezal pero NO se toca (largo
    o sin duracion confirmable), para poder decirlo.
    """
    max_frames = int(DURACION_MAXIMA_SFX_SEGUNDOS * fps)
    descartados = []
    cantidad = int(timeline.GetTrackCount("audio") or 0)
    for i in range(1, cantidad + 1):
        nombre = _nombre_de_pista(timeline, i)
        if not _es_pista_nuestra(nombre):
            continue
        items = timeline.GetItemListInTrack("audio", i) or []
        for it in items:
            try:
                a = int(it.GetStart())
                b = int(it.GetEnd())
            except Exception:
                # Sin inicio/fin confirmables no se toca: no arriesgamos.
                continue
            if not (a <= frame < b):
                continue
            if b - a > max_frames:
                descartados.append(f"{nombre} (clip de "
                                   f"{(b - a) / fps:.1f} s)")
                continue
            return it, i, a, descartados
    return None, None, None, descartados


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
             "> Utility > CineCaptions - SFX Reemplazar")

    print(f"[SFX Reemplazar] versión {VERSION}")

    if not ARCHIVO_PENDIENTE.exists():
        fail("No hay ninguna orden de reemplazo pendiente.\n"
             "  Esto se lanza desde el SFX Lab del programa: activa el modo "
             "«Reemplazar», aparca el cabezal sobre el efecto y elige el "
             "sonido nuevo.")

    try:
        pendiente = json.loads(ARCHIVO_PENDIENTE.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"La orden de reemplazo está dañada: {e}")
    wav = pendiente.get("wav")
    if not wav or not Path(wav).is_file():
        fail(f"No encuentro el sonido nuevo:\n  {wav}")

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

    try:
        fps = float(timeline.GetSetting("timelineFrameRate"))
    except Exception:
        fps = 30.0
    tc_actual = timeline.GetCurrentTimecode() or "01:00:00:00"
    try:
        tc_inicio = timeline.GetStartTimecode() or "01:00:00:00"
    except Exception:
        tc_inicio = "01:00:00:00"
    start_frame = int(timeline.GetStartFrame() or 0)
    delta = _tc_a_frames(tc_actual, fps) - _tc_a_frames(tc_inicio, fps)
    if delta < 0:
        delta = 0
    frame = start_frame + delta
    print(f"  Timeline: {timeline.GetName()}  |  cabezal: {tc_actual} "
          f"(frame {frame})")

    item, pista, inicio_viejo, descartados = _item_bajo_el_cabezal(
        timeline, frame, fps)
    if item is None:
        detalle = ""
        if descartados:
            detalle = ("\n  Bajo el cabezal hay: " + "; ".join(descartados)
                       + " — demasiado largo para ser un efecto nuestro, "
                       "no lo toco.")
        fail("No encuentro un efecto NUESTRO bajo el cabezal (busco solo "
             "en pistas llamadas SFX, SFX-Modificado o SFX-Marcadores y "
             "clips de menos de 20 s — tus clips no los toco)." + detalle
             + "\n  Aparca el cabezal SOBRE el efecto a sustituir y "
             "repite.")

    try:
        nombre_viejo = item.GetName()
    except Exception:
        nombre_viejo = "?"

    # Importar ANTES de borrar: si el import falla, el timeline queda
    # exactamente como estaba.
    nuevo = _importar_una_vez(media_pool=project.GetMediaPool(),
                              ruta_wav=wav)
    if not nuevo:
        fail(f"No pude importar '{Path(wav).name}' al Media Pool; no toco "
             "el timeline.")

    duracion = _frames_de_audio(nuevo, fps)
    if duracion < 1:
        duracion = max(1, int(round(0.5 * fps)))

    borrado = False
    try:
        borrado = bool(timeline.DeleteClips([item]))
    except Exception as e:
        fail(f"No pude quitar el efecto viejo ({e}); no coloco nada.")
    if not borrado:
        fail("Resolve no me dejó quitar el efecto viejo; no coloco nada.")

    media_pool = project.GetMediaPool()
    puestos = None
    try:
        puestos = media_pool.AppendToTimeline([{
            "mediaPoolItem": nuevo,
            "startFrame": 0,
            "endFrame": duracion - 1,
            "trackIndex": pista,
            "mediaType": 2,
            "recordFrame": inicio_viejo,
        }])
    except Exception as e:
        print(f"  AppendToTimeline falló: {e}")
    if not puestos or not puestos[0]:
        # El viejo ya no esta: decirlo con el arreglo en la mano.
        fail("Quité el efecto viejo pero no pude colocar el nuevo. "
             "Un Ctrl+Z en Resolve recupera el viejo; luego repite.")

    try:
        ARCHIVO_HECHO.write_text(json.dumps({
            "reemplazado": nombre_viejo,
            "por": Path(wav).name,
            "pista": pista,
            "insertado_en": time.time(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        ARCHIVO_PENDIENTE.unlink()
    except Exception:
        pass

    print(f"  LISTO: '{nombre_viejo}' -> '{Path(wav).name}' "
          f"(pista A{pista}, frame {inicio_viejo}).")


if __name__ == "__main__":
    main()
