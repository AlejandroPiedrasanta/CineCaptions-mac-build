#!/usr/bin/env python3
# CineCaptions · By Cinema Productions
# 2_recursos/resolve_scripts/CineCaptions - Detectar Video.py — renderiza el audio del timeline activo para transcribirlo (Studio).
"""
CineCaptions - Detectar Video.py
-----------------------------------------------
Script chico que corre DENTRO de Resolve (Workspace > Scripts > Utility) y le
prepara a la ventana "CineCaptions" el audio de tu LINEA DE
TIEMPO, para no tener que ir a buscar ningun archivo a mano.

Que hace exactamente:
  1. Renderiza SOLO EL AUDIO de la linea de tiempo activa (MP4 / AAC a
     256 kb/s: liviano y rapido de exportar) a la carpeta interna del
     programa (fuera de la vista: AppData en Windows, Application Support
     en Mac). Es la mezcla final: si tu
     timeline esta armado con diez clips distintos, cortes, musica y voz en
     off, se transcribe lo que realmente se escucha, en el tiempo exacto en
     que se escucha.
  2. Deja escrita la ruta de ese archivo donde la ventana la lee.
  3. Vuelve sola a la pagina de Edicion, para no dejarte en Deliver.

Ademas, la primera vez deja creado un preset de render llamado
"CineCaptions - Solo audio", por si algun dia quieres exportar
el audio a mano desde la pagina Deliver sin volver a configurar nada.

Por que existe como script separado: la version gratuita de Resolve NO deja
que un programa Python externo (como la ventana) se conecte solo a Resolve
(eso es "scripting externo" y esta reservado a Studio). Entonces el puente va
al reves: este script corre ADENTRO de Resolve, que si tiene permiso.

Uso:
1. Abre tu timeline en Resolve.
2. Workspace > Scripts > Utility > CineCaptions - Detectar Video
   (deja abierta Workspace > Console para ver el avance)
3. Abre la ventana "CineCaptions" y usa "Detectar de Resolve".

Si el render no se puede hacer, el script NO se queda a medias: cae al plan
B (el archivo del clip mas largo de la pista de video 1) y explica en la
consola exactamente en que paso fallo, para poder corregirlo.
"""

import json
import os
import time
from pathlib import Path

VERSION = "5.41 (detectar video)"

# Archivo de control que lee la ventana. Es un .json de unos pocos bytes, por
# eso sigue viviendo en la carpeta compartida junto a los .srt y las marcas.
SHARED_FOLDER = Path.home() / "DaVinciSubtitles"
SALIDA_PATH = SHARED_FOLDER / "video_detectado.json"

# Marcas de entrada/salida que de verdad se aplicaron al render, o None.
MARCA_APLICADA = None


def marcas_de(timeline):
    """(entrada, salida) en fotogramas absolutos, o None si no hay marcas.

    Devuelve None tambien si esta version de Resolve no expone
    GetMarkInOut (llego en la 18.5). En los dos casos se renderiza el
    timeline entero, que es lo que se hacia siempre: una funcion que no
    existe no puede ser motivo de que el programa deje de funcionar.

    La API devuelve {'video': {'startFrame', 'endFrame'}, 'audio': {...}}.
    Interesa el AUDIO -es lo que se transcribe-, con el video de respaldo
    por si alguien marco solo la pista de video.
    """
    try:
        marcas = timeline.GetMarkInOut()
    except Exception:
        return None
    if not isinstance(marcas, dict):
        return None
    for cual in ("audio", "video"):
        m = marcas.get(cual)
        if not isinstance(m, dict):
            continue
        try:
            ini = int(m.get("startFrame"))
            fin = int(m.get("endFrame"))
        except (TypeError, ValueError):
            continue
        if fin > ini:
            return ini, fin
    return None

# v5.4.45: el audio va a la carpeta INTERNA del programa (nada a la vista del
# usuario, ya no en Descargas): <datos locales>/CineCaptions/audio.
NOMBRE_CARPETA_AUDIO = "audio"

# Los renders viejos se borran solos pasados estos dias, para que la carpeta
# no crezca sin limite.
DIAS_A_CONSERVAR = 7

# Preset propio que queda creado la primera vez.
PRESET_PROPIO = "CineCaptions - Solo audio"

# Formato pedido: MP4 con AAC a 256 kb/s. Liviano, rapido y mas que
# suficiente para transcribir.
FORMATO = "mp4"
CODEC_AUDIO = "aac"
BITRATE_AUDIO = 256000
SAMPLE_RATE = 48000

# Cuanto esperamos como maximo a que termine el render de audio.
TIMEOUT_RENDER_SEG = 1800

# Extensiones que damos por buenas como audio renderizado.
EXTENSIONES_AUDIO = (".mp4", ".m4a", ".aac", ".wav", ".aif", ".aiff",
                     ".mp3", ".mov", ".mxf")


def fail(msg):
    print(f"[Detectar Video] ERROR: {msg}")
    volver_a_edicion()
    raise SystemExit(1)


def volver_a_edicion():
    """Deja a Resolve en la pagina de Edicion.

    Renderizar manda la interfaz a Deliver, y quedarse ahi obliga a volver a
    mano cada vez. Se llama al terminar, salga bien o mal.
    """
    try:
        resolve.OpenPage("edit")
    except Exception:
        pass


# --------------------------------------------------------------------------
# Carpeta del audio
# --------------------------------------------------------------------------

def carpeta_de_audio():
    """<datos locales>/CineCaptions/audio, creada si no existe.

    Windows: carpeta LOCALAPPDATA, subcarpeta CineCaptions/audio (oculta por defecto).
    Mac: ~/Library/Application Support/CineCaptions/audio (Library esta oculta).
    """
    home = Path.home()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (home / "AppData" / "Local"))
    else:
        base = home / "Library" / "Application Support"
    destino = base / "CineCaptions" / NOMBRE_CARPETA_AUDIO
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def limpiar_renders_viejos(carpeta, log):
    """Borra los audios que generamos hace mas de DIAS_A_CONSERVAR dias.

    Solo toca archivos con nuestro sufijo '_audio', para no llevarse por
    delante nada que el usuario haya dejado ahi.
    """
    limite = time.time() - DIAS_A_CONSERVAR * 86400
    borrados = 0
    for archivo in carpeta.glob("*_audio.*"):
        try:
            if archivo.is_file() and archivo.stat().st_mtime < limite:
                archivo.unlink()
                borrados += 1
        except Exception:
            continue
    if borrados:
        log(f"Borré {borrados} audio(s) de más de {DIAS_A_CONSERVAR} días "
            "para no llenar el disco.")


# --------------------------------------------------------------------------
# Plan A: renderizar el audio de la linea de tiempo
# --------------------------------------------------------------------------

def _nombre_seguro(texto):
    """Nombre de archivo sin caracteres que Windows/macOS rechacen."""
    limpio = "".join(c if (c.isalnum() or c in " -_") else "_" for c in texto)
    return limpio.strip() or "timeline"


def _cargar_preset_de_audio(project, log):
    """Carga un preset de render de solo audio, si hay alguno.

    Se prefiere el nuestro; si no existe todavia, cualquiera que mencione
    audio (Resolve trae 'Audio Only', que en español aparece como 'Solo
    audio'). Es la via mas confiable, porque un preset ya viene con formato y
    codec validos y evita adivinar nombres de la API.
    """
    try:
        presets = [str(p) for p in (project.GetRenderPresetList() or [])]
    except Exception as e:
        log(f"No pude listar los presets de render ({e}).")
        return False

    candidatos = [p for p in presets if p == PRESET_PROPIO]
    candidatos += [p for p in presets
                   if p != PRESET_PROPIO and "audio" in p.lower()]
    if not candidatos:
        log(f"No hay ningún preset de solo audio entre los {len(presets)} "
            "disponibles.")
        return False

    for nombre in candidatos:
        try:
            if project.LoadRenderPreset(nombre):
                log(f"Preset de render cargado: '{nombre}'.")
                return True
        except Exception:
            continue
    log(f"Encontré presets de audio ({', '.join(candidatos)}) pero Resolve "
        "no cargó ninguno.")
    return False


def _fijar_formato(project, log):
    """Mejor esfuerzo para dejar MP4/AAC puesto.

    OJO: esto es OPCIONAL y nunca corta el render. SetCurrentRenderFormatAndCodec
    fija el codec de VIDEO, y ademas no esta claro si espera la clave o la
    extension de GetRenderFormats(), asi que se prueban las dos. Si nada
    funciona se renderiza igual con lo que tenga el proyecto: lo unico que
    importa es que salga un archivo con el audio adentro.
    """
    intentos = [(FORMATO, CODEC_AUDIO)]
    try:
        for clave, extension in (project.GetRenderFormats() or {}).items():
            if str(extension).lower() == FORMATO:
                intentos.insert(0, (str(clave), CODEC_AUDIO))
    except Exception:
        pass

    for formato, codec in intentos:
        try:
            if project.SetCurrentRenderFormatAndCodec(formato, codec):
                log(f"Formato de render: '{formato}' / '{codec}'.")
                return True
        except Exception:
            continue
    log("No pude fijar MP4/AAC; sigo con el formato que tenga el proyecto "
        "(da igual, se exporta solo el audio).")
    return False


def _aplicar_ajustes(project, ajustes, log):
    """SetRenderSettings, y si el diccionario completo es rechazado se
    reintenta sin las claves opcionales, y por ultimo con lo minimo.

    Devuelve (ok, incluyo_marcas). Lo SEGUNDO es lo importante: el ultimo
    nivel de reintento se queda con la carpeta y el nombre, o sea que pierde
    MarkIn/MarkOut y vuelve a renderizar el timeline ENTERO. Si el llamante
    no se entera, anota la marca igual, el manifiesto dice que el audio
    empieza en la marca, y TODOS los subtitulos salen corridos — sin un solo
    aviso. El comentario de mas abajo decia proteger justo esto y no lo
    hacia, porque esta funcion solo devolvia True/False.
    """
    claves_marca = ("MarkIn", "MarkOut", "SelectAllFrames")
    for etiqueta, prueba in (
            ("completos", ajustes),
            ("sin bitrate/sample rate",
             {k: v for k, v in ajustes.items()
              if k not in ("AudioBitRate", "AudioSampleRate", "AudioCodec")}),
            ("solo carpeta y nombre",
             {"TargetDir": ajustes["TargetDir"],
              "CustomName": ajustes["CustomName"]})):
        try:
            if project.SetRenderSettings(prueba):
                if etiqueta != "completos":
                    log(f"Resolve rechazó los ajustes completos; usé los "
                        f"'{etiqueta}'.")
                # ¿El nivel que entro llevaba las marcas? Solo cuenta si el
                # que las pedia las tenia: si no habia marcas que aplicar,
                # tampoco hay nada que perder.
                pedia_marcas = any(k in ajustes for k in claves_marca)
                incluyo = all(k in prueba for k in claves_marca
                              if k in ajustes)
                if pedia_marcas and not incluyo:
                    log("OJO: en ese nivel se perdieron las marcas de "
                        "entrada/salida. Se renderiza el timeline entero y "
                        "los subtítulos se colocan desde el principio, para "
                        "que no queden corridos.")
                return True, (incluyo if pedia_marcas else False)
        except Exception as e:
            log(f"SetRenderSettings ({etiqueta}) falló: {e}")
    log("Resolve no aceptó los ajustes de render.")
    return False, False


def _guardar_preset_propio(project, log):
    """Deja el preset creado la primera vez, para poder exportar el audio a
    mano desde Deliver sin configurar nada."""
    try:
        presets = [str(p) for p in (project.GetRenderPresetList() or [])]
        if PRESET_PROPIO in presets:
            return
        if project.SaveAsNewRenderPreset(PRESET_PROPIO):
            log(f"Dejé creado el preset '{PRESET_PROPIO}' para exportar el "
                "audio a mano cuando quieras.")
    except Exception:
        pass


def _lanzar_render(project, job_id, log):
    """StartRendering cambia de firma segun la version; probamos las variantes."""
    intentos = (
        ("StartRendering([job], isInteractiveMode=False)",
         lambda: project.StartRendering([job_id], isInteractiveMode=False)),
        ("StartRendering(job)", lambda: project.StartRendering(job_id)),
        ("StartRendering([job])", lambda: project.StartRendering([job_id])),
        ("StartRendering()", lambda: project.StartRendering()),
    )
    for etiqueta, intento in intentos:
        try:
            if intento():
                log(f"Render arrancado con {etiqueta}.")
                return True
        except Exception:
            continue
    log("No pude arrancar el render con ninguna forma de StartRendering.")
    return False


def _esperar_render(project, log):
    """Espera a que el render termine. Devuelve True si terminó solo."""
    # Puede tardar un instante en aparecer como "en progreso"; si se
    # consultara de una, el bucle terminaria antes de empezar.
    for _ in range(20):
        try:
            if project.IsRenderingInProgress():
                break
        except Exception:
            break
        time.sleep(0.25)

    arranque = time.time()
    limite = arranque + TIMEOUT_RENDER_SEG
    ultimo_aviso = 0
    while True:
        try:
            if not project.IsRenderingInProgress():
                return True
        except Exception:
            return True
        if time.time() > limite:
            log("El render tardó demasiado; lo detengo.")
            try:
                project.StopRendering()
            except Exception:
                pass
            return False
        transcurrido = int(time.time() - arranque)
        if transcurrido >= ultimo_aviso + 15:
            ultimo_aviso = transcurrido
            print(f"    ... renderizando ({transcurrido}s)")
        time.sleep(0.5)


def renderizar_audio_del_timeline(project, timeline, diagnostico):
    """Renderiza solo el audio del timeline activo. Devuelve la ruta o None."""

    def log(msg):
        print(f"  {msg}")
        diagnostico.append(msg)

    try:
        if project.IsRenderingInProgress():
            log("Resolve ya está renderizando otra cosa. Espera a que "
                "termine y vuelve a correr esto.")
            return None
    except Exception:
        pass

    destino = carpeta_de_audio()
    log(f"Carpeta de salida: {destino}")
    limpiar_renders_viejos(destino, log)

    base = _nombre_seguro(timeline.GetName()) + "_audio"
    # Borramos el render anterior de ESTE timeline: si no, Resolve agrega un
    # numero al final y despues no sabriamos cual es el nuevo.
    for viejo in destino.glob(base + ".*"):
        try:
            viejo.unlink()
        except Exception:
            pass

    formato_previo = None
    try:
        formato_previo = project.GetCurrentRenderFormatAndCodec()
    except Exception:
        pass

    # 1) Preset de solo audio (lo mas confiable). 2) MP4/AAC a mano.
    # Ninguno de los dos es obligatorio para poder renderizar.
    _cargar_preset_de_audio(project, log)
    _fijar_formato(project, log)

    ajustes = {
        "TargetDir": str(destino),
        "CustomName": base,
        "SelectAllFrames": True,   # la linea de tiempo entera...
        "ExportVideo": False,
        "ExportAudio": True,
        "AudioCodec": CODEC_AUDIO,
        "AudioBitRate": BITRATE_AUDIO,
        "AudioSampleRate": SAMPLE_RATE,
    }

    # ...salvo que haya marcas de entrada y salida: ahi se transcribe SOLO
    # ese tramo. Hay que anotar el mark_in ademas de recortar el render,
    # porque el audio que sale empieza en la marca: el segundo 0 de la
    # transcripcion es la marca y no el principio del timeline. Sin ese dato
    # los subtitulos se colocarian al principio en vez de donde se hablo.
    marcas = marcas_de(timeline)
    if marcas:
        ajustes["SelectAllFrames"] = False
        ajustes["MarkIn"], ajustes["MarkOut"] = marcas
        log(f"Marcas de entrada/salida: {marcas[0]} -> {marcas[1]}. "
            "Solo se transcribe ese tramo.")

    ok_ajustes, con_marcas = _aplicar_ajustes(project, ajustes, log)
    if not ok_ajustes:
        return None

    # _aplicar_ajustes reintenta con carpeta y nombre nada mas si Resolve
    # rechaza el resto, y ahi el recorte SE PIERDE. Se anota solo lo que de
    # verdad quedo aplicado: si el nivel que entro no llevaba MarkIn, el
    # audio es el timeline entero y anotar la marca correria TODOS los
    # subtitulos. Hasta la v1.0.28 se anotaba igual.
    if marcas and con_marcas:
        global MARCA_APLICADA
        MARCA_APLICADA = marcas

    _guardar_preset_propio(project, log)

    antes = set(os.listdir(destino))

    try:
        job_id = project.AddRenderJob()
    except Exception as e:
        log(f"No pude crear el trabajo de render ({e}).")
        return None
    if not job_id:
        log("Resolve no creó el trabajo de render.")
        return None

    print(f"  Renderizando el audio de '{timeline.GetName()}'...")
    if not _lanzar_render(project, job_id, log):
        try:
            project.DeleteRenderJob(job_id)
        except Exception:
            pass
        return None

    _esperar_render(project, log)

    try:
        project.DeleteRenderJob(job_id)
    except Exception:
        pass
    if formato_previo:
        try:
            project.SetCurrentRenderFormatAndCodec(
                formato_previo.get("format"), formato_previo.get("codec"))
        except Exception:
            pass

    # El archivo puede llamarse distinto de lo pedido (Resolve a veces agrega
    # el timecode o un numero), asi que buscamos lo que aparecio.
    nuevos = [destino / n for n in os.listdir(destino) if n not in antes]
    candidatos = [p for p in nuevos
                  if p.is_file() and p.suffix.lower() in EXTENSIONES_AUDIO]
    if not candidatos:
        candidatos = [p for p in nuevos
                      if p.is_file() and p.suffix.lower() != ".json"]
    candidatos = [p for p in candidatos if p.stat().st_size > 1024]
    if not candidatos:
        log(f"El render terminó pero no apareció ningún archivo de audio en "
            f"{destino}. Archivos nuevos: "
            f"{[p.name for p in nuevos] or 'ninguno'}.")
        return None

    return max(candidatos, key=lambda p: p.stat().st_mtime)


# --------------------------------------------------------------------------
# Plan B: el archivo del clip mas largo de la pista de video 1
# --------------------------------------------------------------------------

def video_fuente_del_timeline(timeline):
    """Devuelve (ruta_archivo, cantidad_de_clips_en_v1), o (None, 0)."""
    if timeline.GetTrackCount("video") < 1:
        return None, 0

    items = [it for it in (timeline.GetItemListInTrack("video", 1) or [])
             if it]
    if not items:
        return None, 0

    def duracion(it):
        try:
            return it.GetDuration()
        except Exception:
            return 0

    mejor = max(items, key=duracion)
    try:
        mp_item = mejor.GetMediaPoolItem()
    except Exception:
        mp_item = None
    if not mp_item:
        return None, len(items)

    try:
        ruta = mp_item.GetClipProperty("File Path")
    except Exception:
        ruta = None
    if not ruta:
        return None, len(items)

    return ruta, len(items)


def desde_del_clip(timeline, marca):
    """v5.23: el segundo del ARCHIVO del clip principal de V1 que suena en el
    primer instante del audio renderizado (con el clip recortado o con zona
    marcada no es 0). La app lo usa en Efectos > «Posición» para enseñar los
    fotogramas justos de cada segundo. None si no se puede saber."""
    try:
        items = [it for it in (timeline.GetItemListInTrack("video", 1) or [])
                 if it]
        mejor = max(items, key=lambda it: it.GetDuration() or 0)
        fps = float(timeline.GetSetting("timelineFrameRate") or 0)
        if fps <= 0:
            return None
        try:
            fps_c = float(mejor.GetMediaPoolItem().GetClipProperty("FPS") or fps)
        except Exception:
            fps_c = fps
        inicio = marca[0] if marca else int(timeline.GetStartFrame())
        return round(int(mejor.GetLeftOffset()) / (fps_c or fps)
                     + (inicio - int(mejor.GetStart())) / fps, 3)
    except Exception:
        return None


def main():
    try:
        resolve
    except NameError:
        fail("Este script debe correrse desde Resolve: Workspace > Scripts "
             "> Edit > CineCaptions - Detectar Video")

    print(f"[Detectar Video] versión {VERSION}")

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
        fail("No hay ningún proyecto abierto en Resolve.")
    timeline = project.GetCurrentTimeline()
    if not timeline:
        fail("No hay ningún timeline activo. Abre uno primero.")

    print(f"[Detectar Video] Timeline: {timeline.GetName()}")

    diagnostico = []
    ruta = renderizar_audio_del_timeline(project, timeline, diagnostico)
    desde_timeline = ruta is not None

    if desde_timeline:
        tamano = Path(ruta).stat().st_size / (1024 * 1024)
        print(f"  LISTO: audio de la línea de tiempo ({tamano:.1f} MB)")
        print(f"    {ruta}")
    else:
        ruta_b, cantidad = video_fuente_del_timeline(timeline)
        if not ruta_b:
            fail(
                "No pude renderizar el audio del timeline ni encontrar un "
                f"clip en la pista de video 1 de '{timeline.GetName()}'."
            )
        ruta = ruta_b
        print()
        print("  ATENCIÓN: no se pudo renderizar el audio de la línea de "
              "tiempo, así que uso el archivo del clip más largo de la pista "
              "de video 1:")
        print(f"    {ruta}")
        if cantidad > 1:
            print(f"    Hay {cantidad} clips en esa pista. Si el timeline "
                  "está armado con varios videos distintos, esto va a "
                  "transcribir solo uno y los tiempos no van a coincidir.")
        print("  El motivo del fallo está en las líneas de arriba; si me lo "
              "pasas, se puede corregir.")

    if not Path(str(ruta)).exists():
        print(f"[Detectar Video] Aviso: no encuentro '{ruta}' en el disco "
              "desde acá. Puede ser una unidad de red.")

    # Las marcas solo valen si el audio salio del RENDER del timeline. Si se
    # cayo al plan B (el archivo del clip mas largo de V1), ese audio es el
    # video entero y aplicar un offset descolocaria todo.
    marca = MARCA_APLICADA if desde_timeline else None

    def _numero(f, por_defecto=0):
        try:
            return f()
        except Exception:
            return por_defecto

    # el archivo del clip principal (V1): si ya no está en el disco (lo moverás o le cambiaron el nombre) Resolve lo muestra «Archivo no encontrado»
    # y su audio sale en silencio; la app lo usa para decirlo claro en vez de «Whisper no devolvió palabras».
    try:
        clip_principal = video_fuente_del_timeline(timeline)[0]
    except Exception:
        clip_principal = None
    datos = {
        "video_path": str(ruta),
        "clip_principal": str(clip_principal) if clip_principal else None,
        "timeline_name": timeline.GetName(),
        "project_name": project.GetName(),
        "desde_timeline": desde_timeline,
        # El primer fotograma del timeline (normalmente 86400 =
        # 01:00:00:00) y el fps, para que la app pueda mostrar la zona en
        # timecode en vez de en numeros sueltos.
        "timeline_start_frame": _numero(
            lambda: int(timeline.GetStartFrame())),
        "fps": _numero(
            lambda: float(timeline.GetSetting("timelineFrameRate")), 0.0),
        # La resolucion viaja por el mismo motivo que el fps: solo se conoce
        # DENTRO de Resolve. Con ella la app puede decir, antes de generar,
        # que formato detecto y que version del pack va a usar, en vez de
        # que el usuario se entere al mirar el render.
        "ancho": _numero(
            lambda: int(float(timeline.GetSetting("timelineResolutionWidth")))),
        "alto": _numero(
            lambda: int(float(timeline.GetSetting("timelineResolutionHeight")))),
        "diagnostico": diagnostico,
        "version": VERSION,
        "detectado_en": time.time(),
    }
    if marca:
        datos["mark_in"], datos["mark_out"] = marca
    if desde_timeline and clip_principal:
        desde = desde_del_clip(timeline, marca)
        if desde is not None:
            datos["clip_principal_desde"] = desde

    SHARED_FOLDER.mkdir(parents=True, exist_ok=True)
    SALIDA_PATH.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    if marca:
        print(f"  Zona marcada: fotogramas {marca[0]} a {marca[1]}. Los "
              "subtítulos se van a colocar ahí, no al principio del "
              "timeline.")

    volver_a_edicion()
    print("  Ahora abre (o vuelve a) 'CineCaptions' y usa el "
          "botón 'Detectar de Resolve'.")


if __name__ == "__main__":
    main()
