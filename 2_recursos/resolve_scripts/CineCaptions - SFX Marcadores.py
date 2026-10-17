#!/usr/bin/env python3
# CineCaptions · By Cinema Productions
# 2_recursos/resolve_scripts/CineCaptions - SFX Marcadores.py — efectos de sonido en los marcadores, por color (Studio).
"""
CineCaptions - SFX Marcadores.py
---------------------------------------------
Gemelo de Studio de CineCaptions_SfxMarcadores.lua: coloca efectos de sonido en
los MARCADORES del timeline, por COLOR.

La app deja la orden resuelta (color -> rutas absolutas de sonidos) en
    ~/DaVinciSubtitles/sfx_marcadores_pendiente.json
y este script:
  1) lee la orden (sin orden: explica de donde sale);
  2) timeline.GetMarkers() — frameId RELATIVO a GetStartFrame();
  3) por cada marcador con color mapeado, un sonido de su carpeta
     (rotacion sin repetir pegados), importado una vez y colocado en su
     frame, en la primera pista de audio libre (o 'SFX-Marcadores');
  4) los colores sin mapa se saltan Y SE DICE cuales;
  5) borra la orden al terminar bien: correr dos veces no duplica.

v3.1.9 (pedido literal: «que tambien se pueda reemplazar efectos en los
marcadores»): con "reemplazar" en la orden, los efectos NUESTROS que ya
suenan en el marcador (pistas SFX / SFX-Modificado / SFX-Marcadores, clips
cortos: las guardas de «SFX Reemplazar») se quitan y el nuevo va en su
lugar; con "solo_reemplazar" un marcador sin efecto nuestro se deja como
esta. Los efectos nuevos van SOLO a pistas nuestras.
"""

import json
import os
import time
from pathlib import Path

VERSION = "5.5.9 (sfx marcadores)"

CARPETA_COMPARTIDA = Path.home() / "DaVinciSubtitles"
ARCHIVO_PENDIENTE = CARPETA_COMPARTIDA / "sfx_marcadores_pendiente.json"
ARCHIVO_HECHO = CARPETA_COMPARTIDA / "sfx_marcadores_pendiente.hecho.json"

NOMBRE_PISTA_NUEVA = "SFX-Marcadores"

# Pistas SUYAS y largo maximo de un efecto nuestro: las guardas de
# «SFX Reemplazar» (v1.0.62). Fuera de ellas no se reemplaza NADA.
PISTAS_NUESTRAS = ("SFX", "SFX-MODIFICADO", "SFX-MARCADORES")
DURACION_MAXIMA_SFX_SEGUNDOS = 20


def fail(msg):
    print(f"[SFX Marcadores] ERROR: {msg}")
    raise SystemExit(1)


# --------------------------------------------------------------------------
# Timeline: hueco libre (copias de "Insertar SFX")
# --------------------------------------------------------------------------

def _hay_hueco(timeline, indice_pista, frame_inicio, duracion):
    items = timeline.GetItemListInTrack("audio", indice_pista) or []
    fin = frame_inicio + duracion
    margen = 2
    for it in items:
        try:
            a = int(it.GetStart())
            b = int(it.GetEnd())
        except Exception:
            continue
        if b - margen <= frame_inicio + margen:
            continue
        if a + margen >= fin - margen:
            continue
        return False
    return True


def _es_pista_nuestra(timeline, indice):
    try:
        nombre = str(timeline.GetTrackName("audio", indice) or "")
    except Exception:
        nombre = ""
    return nombre.strip().upper() in PISTAS_NUESTRAS


def _pista_bloqueada(timeline, indice):
    try:
        return bool(timeline.GetIsTrackLocked("audio", indice))
    except Exception:
        return False


def _buscar_pista_vacia(timeline, frame_inicio, duracion):
    # v3.1.9: SOLO pistas nuestras. Hasta la v3.1.8 valia cualquier pista
    # libre -tambien las del usuario- y un efecto puesto ahi ya no se podia
    # reemplazar (el reemplazo solo mira pistas nuestras, a proposito).
    cantidad = timeline.GetTrackCount("audio")
    for i in range(1, cantidad + 1):
        if (_es_pista_nuestra(timeline, i)
                and not _pista_bloqueada(timeline, i)
                and _hay_hueco(timeline, i, frame_inicio, duracion)):
            return i
    return None


def _efectos_nuestros_en(timeline, frame, fps, recien=()):
    """([(item, pista)], intocables): los efectos NUESTROS en 'frame'.

    Las guardas de «SFX Reemplazar», pero TODOS (re-colocar con la v3.1.8
    apilaba uno por corrida). Los de una pista con candado se cuentan y no
    se tocan (regla v3.0.3). 'recien' ((pista, inicio)) son los que ESTA
    corrida acaba de poner: con dos marcadores mas juntos que un efecto, el
    segundo borraba el del primero.
    """
    max_frames = int(DURACION_MAXIMA_SFX_SEGUNDOS * fps)
    efectos, intocables = [], 0
    cantidad = int(timeline.GetTrackCount("audio") or 0)
    for i in range(1, cantidad + 1):
        if not _es_pista_nuestra(timeline, i):
            continue
        bloqueada = _pista_bloqueada(timeline, i)
        for it in timeline.GetItemListInTrack("audio", i) or []:
            try:
                a = int(it.GetStart())
                b = int(it.GetEnd())
            except Exception:
                continue
            if a <= frame < b and b - a <= max_frames and (i, a) not in recien:
                if bloqueada:
                    intocables += 1
                else:
                    efectos.append((it, i))
    return efectos, intocables


def _crear_pista_sfx(timeline):
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
    if nueva == antes:
        nueva = antes + 1
    try:
        timeline.SetTrackName("audio", nueva, NOMBRE_PISTA_NUEVA)
    except Exception:
        pass
    return nueva


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
        print(f"[SFX Marcadores] ImportMedia fallo: {e}")
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
             "> Utility > CineCaptions - SFX Marcadores")

    print(f"[SFX Marcadores] versión {VERSION}")

    if not ARCHIVO_PENDIENTE.exists():
        fail("No hay ninguna orden de marcadores pendiente.\n"
             "  Esto se lanza desde el SFX Lab del programa (botón «SFX en "
             "marcadores…»), donde eliges qué carpeta va con cada color de "
             "marcador. El programa deja la orden y corre esto solo.")

    try:
        pendiente = json.loads(ARCHIVO_PENDIENTE.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"La orden de marcadores está dañada: {e}")
    mapa = pendiente.get("mapa")
    if not isinstance(mapa, dict) or not mapa:
        fail("La orden de marcadores está vacía.")
    # v1.0.69: la app manda el analisis de la onda de cada archivo
    # ({ruta: {pico, dur}} en SEGUNDOS — el fps solo se conoce aqui).
    # Una orden vieja sin 'ondas' degrada a la conducta de siempre.
    ondas = pendiente.get("ondas")
    if not isinstance(ondas, dict):
        ondas = {}
    # v3.1.9: una orden vieja sin estas claves = la conducta de siempre.
    reemplazar = pendiente.get("reemplazar") is True
    solo_reemplazar = reemplazar and pendiente.get("solo_reemplazar") is True

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
    start_frame = int(timeline.GetStartFrame() or 0)

    try:
        crudos = timeline.GetMarkers() or {}
    except Exception as e:
        fail(f"Tu Resolve no me dio los marcadores (GetMarkers: {e}).")
    if not isinstance(crudos, dict):
        fail("Tu Resolve no me dio los marcadores (GetMarkers).")

    # {frameId: {color, name, ...}} con el frameId RELATIVO al inicio del
    # timeline. Se ordena por frame: la rotacion de sonidos debe seguir el
    # orden REAL de los marcadores en el tiempo.
    marcadores = []
    for frame_id, m in crudos.items():
        try:
            frame = int(float(frame_id))
        except (TypeError, ValueError):
            continue
        if isinstance(m, dict):
            marcadores.append((frame, str(m.get("color") or "")))
    marcadores.sort()

    if not marcadores:
        fail("El timeline no tiene marcadores. Ponlos con la tecla M "
             "(y su color, con el panel del marcador) y repite.")
    print(f"  Timeline: {timeline.GetName()}  |  marcadores: "
          f"{len(marcadores)}")

    media_pool = project.GetMediaPool()
    colocados = fallidos = 0
    reemplazados = sin_efecto = bloqueados = con_mapa = 0
    recien = set()             # (pista, inicio) de lo puesto en esta corrida
    usados = {}
    sin_mapa = []

    for frame, color in marcadores:
        fuente = mapa.get(color) or {}
        archivos = fuente.get("archivos") if isinstance(fuente, dict) else None
        if not archivos:
            if color and color not in sin_mapa:
                sin_mapa.append(color)
            continue

        con_mapa += 1
        frame_absoluto = start_frame + frame
        previos, intocables = (_efectos_nuestros_en(timeline, frame_absoluto,
                                                    fps, recien)
                               if reemplazar else ([], 0))
        if intocables:
            # Un efecto nuestro en una pista con CANDADO: se queda (v3.0.3)
            # y no se apila otro encima.
            bloqueados += 1
            print(f"  {color} @ {frame}: su efecto está en una pista "
                  "bloqueada; no lo toco ni pongo otro.")
            continue
        if solo_reemplazar and not previos:
            sin_efecto += 1
            continue

        k = usados.get(color, 0)
        ruta = archivos[k % len(archivos)]
        usados[color] = k + 1

        if not Path(ruta).is_file():
            print(f"  Aviso: no encuentro '{ruta}' (marcador {color} en "
                  f"{frame}); lo salto.")
            fallidos += 1
            continue
        item = _importar_una_vez(media_pool, ruta)
        if not item:
            print(f"  Aviso: no pude importar '{Path(ruta).name}'; salto "
                  "ese marcador.")
            fallidos += 1
            continue

        info_onda = ondas.get(ruta)
        duracion = _frames_de_audio(item, fps)
        if duracion < 1:
            # v1.0.69: el respaldo era 0.5 s FIJO y truncaba los mp3
            # recien importados (Frames aun vacio) — el «a veces se
            # corta antes de que suene» del reporte. La duracion medida
            # por la app manda; sin ella, el 0.5 s de siempre.
            dur_s = 0.0
            if isinstance(info_onda, dict):
                try:
                    dur_s = float(info_onda.get("dur") or 0)
                except (TypeError, ValueError):
                    dur_s = 0.0
            duracion = (max(1, int(dur_s * fps + 0.5)) if dur_s > 0
                        else max(1, int(round(0.5 * fps))))

        # v1.0.69 (reporte literal: «donde esta mas alto ponga junto en
        # el marcador... quiza va a tener que iniciar un poco antes»):
        # el PICO de la onda cae en el marcador — el clip arranca antes.
        # floor(x + 0.5) en delta, la regla v1.0.35 de los redondeos.
        # Clamp doble: dentro del propio clip y nunca antes del inicio
        # del timeline (marcador pegado al arranque pierde fase, no
        # revienta). Sin 'ondas', desplaza=0: la conducta de siempre.
        desplaza = 0
        if isinstance(info_onda, dict):
            try:
                desplaza = int(float(info_onda.get("pico") or 0)
                               * fps + 0.5)
            except (TypeError, ValueError):
                desplaza = 0
            desplaza = max(0, min(desplaza, duracion - 1))
        record = frame_absoluto - desplaza
        if record < start_frame:
            record = start_frame

        # Reemplazar: el sonido nuevo YA esta importado; recien ahora se quita
        # lo viejo (import fallido = timeline intacto). Si Resolve no deja
        # quitarlo, no se apila un duplicado.
        quitados = True
        for it, _pista in previos:
            try:
                if not timeline.DeleteClips([it]):
                    quitados = False
            except Exception:
                quitados = False
        if not quitados:
            bloqueados += 1
            print(f"  {color} @ {frame}: Resolve no me dejó quitar su "
                  "efecto; no pongo otro encima.")
            continue
        indice = None
        if previos and _hay_hueco(timeline, previos[0][1], record, duracion):
            indice = previos[0][1]
        if indice is None:
            indice = _buscar_pista_vacia(timeline, record, duracion)
        if indice is None:
            indice = _crear_pista_sfx(timeline)
        puestos = None
        if indice:
            try:
                puestos = media_pool.AppendToTimeline([{
                    "mediaPoolItem": item,
                    "startFrame": 0,
                    "endFrame": duracion - 1,
                    "trackIndex": indice,
                    "mediaType": 2,
                    "recordFrame": record,
                }])
            except Exception as e:
                print(f"  Aviso: AppendToTimeline falló ({e}).")
        if puestos:
            recien.add((indice, record))
            extra = f", pico -{desplaza}f" if desplaza else ""
            if previos:
                reemplazados += 1
                extra += ", reemplaza"
            else:
                colocados += 1
            print(f"  {color} @ {frame} -> '{Path(ruta).name}' "
                  f"(A{indice}{extra})")
        else:
            fallidos += 1
            print(f"  Aviso: no pude colocar '{Path(ruta).name}' en el "
                  f"frame {record}."
                  + (" Ya había quitado el efecto viejo: un Ctrl+Z en "
                     "Resolve lo recupera." if previos else ""))

    # En el modo Reemplazar del Lab la orden trae UN color a proposito: los
    # demas no son «colores sin carpeta».
    if sin_mapa and not solo_reemplazar:
        print("  Colores sin carpeta asignada (se saltan): "
              + ", ".join(sin_mapa)
              + ". Se configuran en el SFX Lab, botón «SFX en marcadores…».")
    if sin_efecto:
        print(f"  {sin_efecto} marcador(es) sin un efecto del programa "
              "debajo: los dejo como están.")

    if not colocados and not reemplazados:
        if solo_reemplazar:
            fail(f"No reemplacé nada: de {con_mapa} marcador(es) de ese "
                 "color, ninguno tenía debajo un efecto del programa (busco "
                 "en las pistas SFX, SFX-Modificado y SFX-Marcadores; tus "
                 "clips no los toco).")
        fail(f"No coloqué ningún sonido ({len(marcadores)} marcadores, "
             f"{fallidos} fallidos, {bloqueados} bloqueados). Revisa el "
             "mapa de colores en el programa.")

    try:
        ARCHIVO_HECHO.write_text(json.dumps({
            "colocados": colocados,
            "reemplazados": reemplazados,
            "marcadores": len(marcadores),
            "insertado_en": time.time(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        ARCHIVO_PENDIENTE.unlink()
    except Exception:
        pass

    if reemplazados:
        print(f"  LISTO: {reemplazados} reemplazado(s) y {colocados} "
              f"sonido(s) nuevos en {len(marcadores)} marcadores.")
    else:
        print(f"  LISTO: {colocados} sonido(s) colocados en "
              f"{len(marcadores)} marcadores.")


if __name__ == "__main__":
    main()
