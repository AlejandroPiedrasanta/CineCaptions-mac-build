#!/usr/bin/env python3
# CineCaptions · By Cinema Productions
# 2_recursos/resolve_scripts/CineCaptions - Importar Estilos.py — saca un pack de estilos de un timeline con Text+ (Studio).
"""
CineCaptions - Importar Estilos.py
----------------------------------------------
El gemelo en Python de CineCaptions_ImportarEstilos.lua, para Resolve Studio (que si
deja hablar por la API externa). Misma logica: un cambio de comportamiento va
en los dos.

Lee un timeline lleno de Text+ nombrados como siempre -'contexto',
'principal', 'complemento', 'contexto 2'...- y saca de ahi un PACK DE ESTILOS.

Deja:
  ~/DaVinciSubtitles/importar_estilos.json    lo extraido (lo lee la app)
  ~/DaVinciSubtitles/importar_estilos_tmp/    los .setting y las miniaturas

La app (plantillas.py) convierte eso en un pack: mezcla con lo que ya hubiera,
reescala las miniaturas y limpia. Aqui solo se EXTRAE.

OJO CON LAS MINIATURAS: GrabStill() es de la pagina de Color, asi que Resolve
salta a esa pagina al capturarlas. Es normal. Al terminar se vuelve.

No borra nada del proyecto ni modifica los Text+: solo los lee.
"""

import json
import re
import time
from pathlib import Path

VERSION = "5.20 (importar estilos)"

# Los mismos nombres y el mismo tope que el resto del programa.
NOMBRES = {
    "context": "contexto",
    "main": "principal",
    "complement": "complemento",
}
ORDEN_ROLES = ("context", "main", "complement")
MAX_SETS = 10
# v5.3: la estructura nueva (arriba / principal / abajo, variantes 1..3, 'simple' para las
# palabras sueltas y 'imagen' para el icono) y los nombres de antes, que siguen valiendo.
ALIAS = {
    "context": ("arriba", "contexto"),
    "main": ("principal",),
    "complement": ("abajo", "complemento"),
}
MAX_VARIANTES = 10            # con los nombres nuevos (v5.9: antes 3)

CARPETA = Path.home() / "DaVinciSubtitles"
NOMBRE_SCRIPT = "CineCaptions_ImportarEstilos"

_salida = []


def log(texto=""):
    _salida.append(str(texto))
    print(texto)


def guardar_resultado(ok, mensaje):
    """Los scripts corren dentro de Resolve, donde print() va a una consola
    que nadie tiene abierta. Esto es lo que la app muestra."""
    try:
        CARPETA.mkdir(parents=True, exist_ok=True)
        (CARPETA / "ultimo_resultado.txt").write_text(
            "\n".join(_salida), encoding="utf-8")
        (CARPETA / "ultimo_resultado.json").write_text(json.dumps({
            "script": NOMBRE_SCRIPT, "version": VERSION,
            "ok": bool(ok), "mensaje": str(mensaje),
            "cuando": int(time.time()),
        }, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


class Abortar(Exception):
    """Abortar lanzando, nunca con return: quien nos llama daba por bueno un
    script que se rendia en silencio."""


def fail(mensaje):
    guardar_resultado(False, mensaje)
    raise Abortar(mensaje)


def lista(coleccion):
    """Las listas de la API de Resolve son dicts {1: obj, 2: obj, ...}."""
    if not coleccion:
        return []
    if isinstance(coleccion, dict):
        return [v for _, v in sorted(coleccion.items())]
    return list(coleccion)


# ----------------------------------------------------------------------
# Que set y que rol es cada clip
# ----------------------------------------------------------------------
def parsear_nombre(nombre):
    """('main', 3) para 'principal 3'. ('base', 0) para 'base'.

    Se aceptan las mismas formas de numerar que en el Media Pool:
    'contexto 2', 'contexto2', 'contexto-2', 'contexto_2', 'contexto 02'.
    Devuelve (rol, -1) si el numero se pasa de MAX_SETS, para poder DECIRLO
    en vez de dejar el clip fuera en silencio.
    """
    n = str(nombre or "").strip().lower()
    # Solo extensiones de LETRAS: con digitos, 'contexto.2' perderia su numero.
    n = re.sub(r"\.[a-z]+$", "", n)
    if n in ("simple", "base"):
        return "base", 0
    for rol in ORDEN_ROLES:
        for palabra in ALIAS[rol]:
            if n == palabra:
                return rol, 1
            m = re.match(r"^" + re.escape(palabra) + r"[\s\-_.]*0*(\d+)$", n)
            if m:
                k = int(m.group(1))
                tope = MAX_VARIANTES if palabra in ("arriba", "abajo") else MAX_SETS
                return (rol, k) if 1 <= k <= tope else (rol, -1)
    # 'imagen' (el bloque del icono) no lleva estilo de texto: no es un set que importar.
    return None, None


# ----------------------------------------------------------------------
# Sacarle los valores a un Text+
# ----------------------------------------------------------------------
def leer(tool, id_):
    try:
        return tool.GetInput(id_)
    except Exception:
        return None


def numero(tool, id_, por_defecto=None):
    try:
        v = leer(tool, id_)
        return por_defecto if v is None else float(v)
    except (TypeError, ValueError):
        return por_defecto


def estilo_de(tool):
    e = {
        "font": str(leer(tool, "Font") or "Open Sans"),
        "style": str(leer(tool, "Style") or "Regular"),
        "size": numero(tool, "Size", 0.05),
        # 'CharacterSpacing', no 'Tracking': ese input no existe en un Text+
        # (ver CineCaptions_Prueba_Animaciones). Leyendo el que no es, todos los packs
        # se importarian con interletrado 1.0 pasara lo que pasara.
        "tracking": numero(tool, "CharacterSpacing", 1.0),
        "color": [numero(tool, "Red1", 1.0),
                  numero(tool, "Green1", 1.0),
                  numero(tool, "Blue1", 1.0)],
    }
    esp = numero(tool, "LineSpacing")
    if esp is not None:
        e["line_spacing"] = esp

    # El contorno. La prueba del Paso 0 confirmo que estas entradas responden,
    # y de ellas depende el modo Hormozi.
    grosor = numero(tool, "Thickness2", 0) or 0
    activo = numero(tool, "Enabled2", 0) or 0
    if activo > 0 and grosor > 0:
        e["outline"] = {
            "thickness": grosor,
            "color": [numero(tool, "Red2", 0.0),
                      numero(tool, "Green2", 0.0),
                      numero(tool, "Blue2", 0.0)],
        }
    return e


def text_plus_de(item):
    try:
        comp = item.GetFusionCompByIndex(1)
    except Exception:
        return None
    if not comp:
        return None
    try:
        for _, t in comp.GetToolList().items():
            try:
                if t.ID == "TextPlus":
                    return t
            except Exception:
                continue
    except Exception:
        return None
    return None


# ----------------------------------------------------------------------
# Miniaturas
# ----------------------------------------------------------------------
def timecode_de(frame_abs, fps):
    fps_i = max(1, int(round(float(fps or 24))))
    f = int(frame_abs or 0)
    total_s = f // fps_i
    return "%02d:%02d:%02d:%02d" % (
        total_s // 3600, (total_s // 60) % 60, total_s % 60, f % fps_i)


def capturar_miniatura(project, timeline, item, fps, destino, n):
    """Devuelve (prefijo, None) o (None, motivo).

    Se exporta con un PREFIJO DISTINTO por set a proposito: ExportStills
    nombra los archivos por TIMECODE ('cinecaptions_prueba_5.3.1.png'), no en orden,
    asi que sin prefijo propio no habria forma de saber cual es de quien.
    """
    try:
        timeline.SetCurrentTimecode(
            timecode_de((item.GetStart() or 0) + 2, fps))
    except Exception:
        return None, "no pude mover el cursor al clip"

    try:
        still = timeline.GrabStill()
    except Exception:
        still = None
    if not still:
        return None, "GrabStill no devolvio nada"

    try:
        album = project.GetGallery().GetCurrentStillAlbum()
    except Exception:
        album = None
    if not album:
        return None, "no pude llegar al album de la galeria"

    prefijo = "cinecaptions_set_%02d" % n
    try:
        album.ExportStills([still], str(destino), prefijo, "png")
    except Exception as exc:
        try:
            album.DeleteStills([still])
        except Exception:
            pass
        return None, f"ExportStills fallo ({exc})"

    # No dejarle basura en la galeria del proyecto.
    try:
        album.DeleteStills([still])
    except Exception:
        pass
    return prefijo, None


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
# Modulo, no local de _trabajo(): la limpieza (borrar el timeline importado
# y devolver el que estaba activo) tiene que correr SIEMPRE, incluso si
# _trabajo() aborta a mitad con fail() ("no encontré ningún Text+", por
# ejemplo). main() las lee despues de llamar a _trabajo(), pase lo que pase.
_project_global = None
_timeline_previo = None
_timeline_importado = None


def _ruta_drt_pendiente():
    """El .drt que el usuario eligio importar, o None si viene del timeline
    abierto de siempre. Archivo de nombre fijo (como jobs/pendiente.json),
    con la ruta en una sola linea -no hace falta JSON para un dato suelto-.
    Se borra al leerlo: un marcador viejo no puede repetir la importacion."""
    marcador = CARPETA / "importar_drt.txt"
    if not marcador.is_file():
        return None
    try:
        ruta = marcador.read_text(encoding="utf-8").strip().splitlines()[0]
    except (OSError, IndexError):
        ruta = ""
    try:
        marcador.unlink()
    except OSError:
        pass
    return ruta or None


def _trabajo():
    global _project_global, _timeline_previo, _timeline_importado

    log(f"CineCaptions Importar estilos  v{VERSION}")

    r = globals().get("resolve")
    if r is None:
        fail("No pude conectar con Resolve.")

    project = r.GetProjectManager().GetCurrentProject()
    if not project:
        fail("No hay ningún proyecto abierto en Resolve.")
    _project_global = project
    media_pool = project.GetMediaPool()

    # Si el usuario eligió "Importar desde un archivo .drt", el timeline no
    # está abierto: hay que traerlo primero. Se importa, se usa, y se borra
    # al terminar -es un timeline nuestro, de usar y tirar, no algo del
    # usuario-. El timeline que estuviera activo se restaura para no dejar a
    # alguien mirando un timeline que no eligió.
    ruta_drt = _ruta_drt_pendiente()
    if ruta_drt:
        log(f"  Importando desde {ruta_drt}...")
        _timeline_previo = project.GetCurrentTimeline()
        try:
            importado = media_pool.ImportTimelineFromFile(ruta_drt)
        except Exception:
            importado = None
        if not importado:
            fail(f"No pude importar '{ruta_drt}'. ¿Es un .drt exportado de "
                 "Resolve (Archivo > Exportar > Timeline)?")
        _timeline_importado = importado
        try:
            project.SetCurrentTimeline(importado)
        except Exception:
            pass
        timeline = importado
    else:
        timeline = project.GetCurrentTimeline()

    if not timeline:
        fail("No hay ningún timeline abierto. Abre el timeline del pack de "
             "estilos y vuelve a pulsar Importar.")

    def ajuste(clave, por_defecto):
        for fuente in (timeline, project):
            try:
                v = fuente.GetSetting(clave)
                if v:
                    return float(v)
            except Exception:
                continue
        return por_defecto

    ancho = int(ajuste("timelineResolutionWidth", 1920))
    alto = int(ajuste("timelineResolutionHeight", 1080))
    fps = ajuste("timelineFrameRate", 24.0)
    formato = "v" if alto > ancho else "h"

    log(f"  Timeline '{timeline.GetName()}'  {ancho}x{alto} @ {fps:.3f} fps "
        f" -> formato {formato}")

    tmp = CARPETA / "importar_estilos_tmp"
    tmp_min = tmp / "miniaturas"
    try:
        tmp_min.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        fail(f"No pude crear la carpeta de trabajo en {tmp} ({exc}). "
             "Sin ella no puedo guardar los estilos.")

    entradas = []
    avisos = []
    clip_de_set = {}
    vistos = 0

    for pista in range(1, (timeline.GetTrackCount("video") or 0) + 1):
        for item in lista(timeline.GetItemListInTrack("video", pista)):
            try:
                nombre = item.GetName()
            except Exception:
                continue
            rol, n = parsear_nombre(nombre)
            if rol is None:
                continue
            vistos += 1
            if n == -1:
                avisos.append(f"'{nombre}' tiene un número mayor que "
                              f"{MAX_SETS}: lo salté")
                continue
            tool = text_plus_de(item)
            if tool is None:
                avisos.append(f"'{nombre}' no tiene un Text+ dentro: lo salté")
                continue

            e = estilo_de(tool)
            nombre_setting = ("base.setting" if rol == "base"
                              else "%02d-%s.setting" % (n, rol))
            # El .setting es lo FIEL: se lleva degradados, formas y fondos. El
            # estilos.json de al lado es el plan B, y lo único que se puede
            # dibujar en la ventana de previsualización.
            try:
                tool.SaveSettings(str(tmp / nombre_setting))
                if not (tmp / nombre_setting).is_file():
                    raise OSError("no apareció el archivo")
            except Exception:
                avisos.append(f"no pude guardar el nodo entero de '{nombre}' "
                              "(se usarán solo sus valores)")
                nombre_setting = None

            entradas.append({"rol": rol, "n": n, "estilo": e,
                             "setting": nombre_setting})
            clave = "base" if rol == "base" else n
            # La miniatura sale del clip 'principal', que es el que manda
            # visualmente. Si no hay, vale el que haya.
            if clave not in clip_de_set or rol == "main":
                clip_de_set[clave] = item

    if not entradas:
        fail(f"En el timeline '{timeline.GetName()}' no encontré ningún Text+ "
             "con los nombres del pack. Tienen que llamarse 'arriba', "
             "'principal', 'abajo' (y 'arriba 2', 'principal 2'... "
             "hasta 3 variantes), más 'simple' e 'imagen' si quieres.")

    # Las miniaturas van al final y aparte: saltan a la página de Color, y si
    # fallan el pack sigue siendo perfectamente usable.
    try:
        pagina_previa = r.GetCurrentPage()
    except Exception:
        pagina_previa = None

    miniaturas = []
    for clave, item in clip_de_set.items():
        n = 0 if clave == "base" else clave
        prefijo, motivo = capturar_miniatura(
            project, timeline, item, fps, tmp_min, n)
        if prefijo:
            miniaturas.append({"clave": str(clave), "prefijo": prefijo})
        else:
            avisos.append(f"sin miniatura para el set {clave} ({motivo})")

    try:
        r.OpenPage(pagina_previa or "edit")
    except Exception:
        pass

    datos = {
        "ok": True,
        "version": VERSION,
        "timeline": str(timeline.GetName()),
        "resolucion": [ancho, alto],
        "fps": fps,
        "formato": formato,
        "carpeta": str(tmp),
        "entradas": entradas,
        "miniaturas": miniaturas,
        "avisos": avisos,
        "cuando": int(time.time()),
    }
    destino = CARPETA / "importar_estilos.json"
    try:
        destino.write_text(json.dumps(datos, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    except OSError as exc:
        fail(f"Extraje los estilos pero no pude escribir {destino} ({exc})")

    # Contar por set, que es como lo piensa el usuario.
    por_set = {("base" if e["rol"] == "base" else e["n"]) for e in entradas}
    log(f"  Encontrados {len(entradas)} Text+ en {len(por_set)} sets.")
    log(f"  Miniaturas capturadas: {len(miniaturas)}.")
    if avisos:
        log("  Avisos:")
        for a in avisos:
            log(f"    - {a}")

    guardar_resultado(True, "Importados %d estilos en %d sets (%s)." % (
        len(entradas), len(por_set),
        "vertical" if formato == "v" else "horizontal"))


def _limpiar_importado():
    """Borra el timeline que se importo de un .drt y devuelve el que
    estaba activo. Corre SIEMPRE, pase lo que pase adentro de _trabajo() -es
    un timeline nuestro, de usar y tirar, no algo del usuario-."""
    if _timeline_importado is None or _project_global is None:
        return
    try:
        if _timeline_previo is not None:
            _project_global.SetCurrentTimeline(_timeline_previo)
    except Exception:
        pass
    try:
        media_pool = _project_global.GetMediaPool()
        media_pool.DeleteTimelines([_timeline_importado])
    except Exception:
        pass


def main():
    """El punto de entrada. Tiene que llamarse asi y NO ejecutarse al
    importar: resolve_bridge.ejecutar_script() importa el modulo -inyectandole
    el 'resolve' externo- y despues llama a main(). Corriendolo al importar se
    ejecutaria dos veces, y la primera sin conexion."""
    try:
        _trabajo()
    except Abortar:
        raise      # fail() ya dejo escrito el motivo; que lo vea quien llama
    except Exception as exc:                   # noqa: BLE001
        log(f"ERROR: {exc}")
        guardar_resultado(False, str(exc))
        raise
    finally:
        _limpiar_importado()


if __name__ == "__main__":
    main()
