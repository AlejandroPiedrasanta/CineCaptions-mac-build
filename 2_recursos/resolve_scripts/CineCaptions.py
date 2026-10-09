#!/usr/bin/env python3
# CineCaptions · By Cinema Productions
# 2_recursos/resolve_scripts/CineCaptions.py — coloca los subtítulos en el timeline (núcleo en Python para Resolve Studio).
"""
CineCaptions.py
-------------------
Pieza 2 del sistema. Este archivo debe vivir DENTRO de la carpeta de Scripts
de DaVinci Resolve (ver README.md para la ruta exacta en Mac/Windows) y se
ejecuta desde el menú Workspace > Scripts > Utility > CineCaptions.

IMPORTANTE (versión gratuita de Resolve):
Desde Resolve 19.1, la versión gratuita SOLO permite scripts que corren
"adentro" de la app (este es ese caso: usa las variables globales `resolve`,
`fusion`, `bmd` que Resolve inyecta automáticamente). No lo ejecutes como
programa Python suelto desde una terminal — ahí sí requiere Studio.

Preparación (una sola vez por proyecto):
1. Ve a Effects > Titles, arrastra un "Text+" a un bin de tu Media Pool.
2. Renómbralo exactamente a: Subtitle Template
   (dale el estilo/fuente/tamaño que quieras: el script clona ESE estilo)
3. Corre subtitle_transcriber.py fuera de Resolve para generar los .srt
   y el subtitles_manifest.json.
4. Con tu timeline activo en Resolve, corre este script desde
   Workspace > Scripts > Utility > CineCaptions.

Qué hace:
- Lee ~/DaVinciSubtitles/subtitles_manifest.json
- Por cada idioma, crea una pista de video nueva llamada con el código de
  idioma (ES, EN, ...) y coloca un clip Text+ por cada línea del .srt,
  en el timecode exacto, con el texto correspondiente. Cada clip queda
  100% editable a mano en Resolve (doble clic para cambiar el texto).
"""

import json
import math
import os
import re
from pathlib import Path

# Debe coincidir con SHARED_FOLDER en subtitle_transcriber.py
SHARED_FOLDER = Path.home() / "DaVinciSubtitles"
MANIFEST_PATH = SHARED_FOLDER / "subtitles_manifest.json"
TEMPLATE_CLIP_NAME = "Subtitle Template"

# La version de ESTE script. En Studio sale del bundle de la app, asi que
# coincide con la del programa (ver version.py). Se estampa en
# ultimo_resultado.json: hasta la v1.0.28 este archivo no tenia version
# ninguna y no habia forma de saber que build habia colocado los subtitulos.
VERSION = "5.4.15 (subtitulos)"

# Donde se escribe el resultado para que la app lo lea. Hasta la v1.0.26 este
# script no escribia nada aca -a diferencia del de Importar Estilos, que si
# lo hace-, asi que despues de generar la app seguia enseñando el ultimo
# mensaje de una IMPORTACION anterior. El sintoma que llegaba: el aviso de
# "importe N estilos" apareciendo despues de darle a Generar.
RESULT_JSON_PATH = SHARED_FOLDER / "ultimo_resultado.json"
RESULT_TXT_PATH = SHARED_FOLDER / "ultimo_resultado.txt"
# Que mecanismo de Resolve funciono para pasar los clips de un pack .drt al
# Media Pool, para no volver a probar los que fallan en cada uno de los ~30
# clips de un pack. Vive junto al manifest, no en el registro de Windows: es
# el mismo Resolve el que puede cambiar de capacidades entre versiones.
CAPACIDADES_PATH = SHARED_FOLDER / "capacidades.json"

# --------------------------------------------------------------------------
# Subtitulos dinamicos de 3 lineas
# --------------------------------------------------------------------------
# Hay dos formas de trabajar, y el script elige sola segun lo que encuentre:
#
#   MODO PLANTILLAS  -> si en el Media Pool existen los tres clips de abajo,
#                       se usan tal cual. TU controlas fuente, tamaño, color
#                       y posicion de cada linea. Es el modo recomendado si
#                       te importa el diseño.
#
#   MODO AUTOMATICO  -> si no existen, se clona 'Subtitle Template' tres
#                       veces y el script le pone fuente, tamaño, peso y
#                       posicion segun AUTO_STYLES. No hay que preparar nada,
#                       pero el diseño es el que viene aca abajo.

DYNAMIC_TEMPLATES = {
    "context": "contexto",
    "main": "principal",
    "complement": "complemento",
}

# Plantilla opcional para las palabras que el usuario dejo SIN marcar en la
# ventana (subtitulo simple, palabra por palabra). Si existe un Text+ con
# este nombre en el Media Pool, se usa tal cual (con SU estilo propio) en
# vez de reciclar el estilo de 'principal'. Si no existe, se cae a
# 'principal' como antes. No es un set numerado: es una sola plantilla.
BASE_TEMPLATE_NAME = "base"

# v5.3: la estructura NUEVA de un pack: arriba / principal / abajo / imagen (+ 'simple' para las
# palabras sueltas), con variantes 1..3 ("arriba 2", "arriba3"...). Los nombres de antes (contexto /
# complemento / base) siguen valiendo: los packs hechos antes no se tocan. Gemela de packs_drt.ALIAS
# (la app) y de NOMBRES_ROL del .lua: los tres tienen que dar lo mismo.
NOMBRES_ROL = {
    "context": ("arriba", "contexto"),
    "main": ("principal",),
    "complement": ("abajo", "complemento"),
}
NOMBRES_BASE = ("simple", "base")
NOMBRE_IMAGEN = "imagen"      # el bloque donde va el icono o la imagen (el emoji)
NOMBRES_SOLO_NUEVOS = ("arriba", "abajo", "imagen")
MAX_VARIANTES = 16            # con los nombres nuevos (v5.9: antes 3; v5.5: 16 por las variantes de barrido de «Referencia», 9-16)

# Si quieres varios estilos que se vayan alternando, duplica las plantillas
# agregando un numero: "contexto 2", "principal 2", "complemento 2", despues
# "contexto 3", etc. El script busca hasta MAX_SETS sets ANTES de empezar,
# se queda con todos los que encuentre, y los va alternando bloque a bloque
# sin repetir nunca el mismo dos veces seguidas. No hace falta numerar de
# corrido: si tienes el 1, el 2 y el 5, usa esos tres.
MAX_SETS = 16

# Formas de numerar que se aceptan: "contexto 2", "contexto2", "contexto-2",
# "contexto_2". Asi un nombre escrito distinto no deja el set afuera.
SUFIJOS_DE_SET = (" {n}", "{n}", "-{n}", "_{n}", " {n:02d}")

# Cuanto dura el fundido con el que las tres lineas desaparecen juntas.
FADE_OUT_SECONDS = 0.35
# La animacion de entrada del camino por valores (v1.0.51). Corta a
# proposito: es un "aparecer con suavidad", no un efecto — los packs traen
# los suyos y no pasan por aqui. Misma constante en el gemelo Lua.
FADE_IN_SECONDS = 0.12

# Separacion entre clips, en fotogramas.
#
# En 0: los bloques van PEGADOS donde el habla es seguida, y el hueco aparece
# solo donde hay silencio de verdad. No hace falta detectar silencios: el fin
# de un bloque ya es el fin de su ultima palabra (ver build_manual_cues en
# dynamic_subtitles.py), no se estira hasta el siguiente, asi que la pausa del
# audio se traduce sola en hueco.
#
# Y no se solapan: 'duracion = fin_frame - inicio_frame' con
# 'endFrame = duracion - 1', o sea que el clip ocupa hasta fin_frame - 1 y el
# siguiente arranca en su propio inicio_frame.
GAP_BASICO_FRAMES = 0   # entre palabras sueltas (rol 'base')
GAP_BLOQUE_FRAMES = 0   # entre bloques de 2 o 3 lineas

# Donde va SIEMPRE la linea principal, y de ahi cuelgan las otras dos.
#
# Las alturas NO son absolutas por rol. Lo fueron hasta la v1.0.24 y daba dos
# problemas a la vez:
#
#   - Un bloque de 2 lineas dejaba el HUECO de la tercera. "contexto +
#     principal" flotaba alto y "principal + complemento" flotaba bajo, porque
#     cada linea iba a su altura fija pasara lo que pasara.
#   - Cada variante de diseño traia su propia 'y', asi que el texto REBOTABA
#     verticalmente entre un bloque y el siguiente.
#
# Con un ancla fija para la principal y el resto colocado en relacion a ella,
# las dos cosas desaparecen: la principal no se mueve nunca -ni entre bloques,
# ni entre variantes, ni segun cuantas lineas haya- y las vecinas se apoyan en
# ella.
ANCLA_Y = 0.196

# Cuanto se separan las lineas vecinas de la principal. Se calcula a partir de
# los TAMAÑOS y no con un numero fijo, para que una variante de letra grande
# no encime las lineas y una de letra chica no las deje sueltas.
#
# 0.54 (v1.0.51, antes 0.66). El 0.66 salia de la caja em teorica de
# Montserrat (1.219/2 = 0.6095 + un 8% de holgura) — pero la caja em
# incluye los ascendentes y descendentes ENTEROS, que un subtitulo casi
# nunca usa a la vez en las dos lineas que se tocan. Medido en unidades de
# la linea chica, con 0.66 el contexto quedaba a ~2 veces su propio em de
# la principal: el bloque se leia como tres tiras sueltas (reporte con
# captura en 9:16, 03-09). 0.54 equivale a un interlineado real de ~1.08
# sobre la suma de tamaños — apretado como un bloque de subtitulo de
# verdad, y todavia por encima del solape de tinta real.
#
# EL 0.47 HISTORICO SI SOLAPABA (-21 px a 1080p, el "textos amontonados"
# de la v1.0.27): no volver ahi. Y desde la v1.0.51 el usuario tiene el
# deslizador «Separación» (viaja como factor_separacion en el diseño), asi
# que esta constante es solo el defecto del modo automatico.
FACTOR_SEPARACION = 0.54

# Diseño del modo automatico. Cambiar estos valores es la forma facil de
# ajustar el look sin tocar el resto del script.
#   size  : tamaño relativo del Text+ (0.05 ~ mediano)
#   color : (rojo, verde, azul) de 0 a 1
# La altura ya no se pone aqui: la calcula altura_de_linea().
# Montserrat, no Open Sans/Georgia: desde la v1.0.27 Montserrat viaja
# incrustada en el programa (ver fonts/ e instalar_fuentes.py). Open Sans NO
# viene instalada en Windows por defecto -era ese el "error" que el diseño
# automatico producia siempre en un equipo recien instalado, sin que nadie
# hubiera tocado nada- y Georgia esta pensada para pantalla chica, no para
# subtitulo grande en video.
AUTO_STYLES = {
    "context": {
        "font": "Montserrat", "style": "Regular", "size": 0.038,
        "tracking": 1.0, "color": (1.0, 1.0, 1.0),
    },
    "main": {
        "font": "Montserrat", "style": "Bold", "size": 0.082,
        "tracking": 0.97, "color": (1.0, 1.0, 1.0),
    },
    "complement": {
        "font": "Montserrat", "style": "Italic", "size": 0.050,
        "tracking": 1.0, "color": (0.88, 0.88, 0.88),
    },
}


def altura_de_linea(rol, estilos_bloque, ancla=None, factor=None):
    """A que altura va esta linea, con la principal como ancla.

    'estilos_bloque' son los estilos ya resueltos de ese bloque, de donde se
    sacan los tamaños para calcular la separacion.

    El contexto va ENCIMA de la principal y el complemento DEBAJO, siempre, y
    da igual cuantas lineas tenga el bloque: por eso un bloque de dos lineas
    ya no deja hueco ni flota.
    """
    # 'ancla'/'factor' llegan SOLO del modo «Diseño dinámico» (v1.0.49):
    # posicion elegida por el usuario. Sin ellos, las constantes de
    # siempre — el camino de packs no cambia ni un pelo.
    ancla = ANCLA_Y if ancla is None else ancla
    factor = FACTOR_SEPARACION if factor is None else factor
    if rol == "main" or rol == "base":
        return ancla
    tam_main = estilos_bloque.get("main", {}).get("size", 0.082)
    tam_mio = estilos_bloque.get(rol, {}).get("size", 0.05)
    separacion = (tam_main + tam_mio) * factor
    return ancla + separacion if rol == "context" else ancla - separacion

# Variantes que se van alternando bloque a bloque para que el video no sea
# siempre el mismo bloque de texto. Cada una es un "delta" sobre AUTO_STYLES:
# solo hace falta poner lo que cambia.
AUTO_PRESETS = [
    {},  # 1. tal cual AUTO_STYLES
    {    # 2. principal mas grande y complemento mas discreto
        "main": {"size": 0.098},
        "context": {"size": 0.034},
        "complement": {"size": 0.044},
    },
    {    # 3. compacto y parejo
        "main": {"size": 0.070},
        "context": {"size": 0.040},
        "complement": {"size": 0.052, "style": "Regular"},
    },
    {    # 4. principal en versalita amplia, complemento pegado
        "main": {"size": 0.076, "tracking": 1.12},
        "context": {"size": 0.036, "tracking": 1.15},
        "complement": {"size": 0.048},
    },
    {    # 5. contexto arriba chico, principal dominante
        "main": {"size": 0.090},
        "context": {"size": 0.032, "color": (0.80, 0.80, 0.80)},
        "complement": {"size": 0.046},
    },
]

# Orden en que se crean las pistas: SIEMPRE 3, ni una mas. Los bloques de
# una o dos lineas simplemente no usan alguna de estas pistas en ese momento.
DYNAMIC_ORDER = ["context", "main", "complement"]
ROLE_SHORT = {"context": "CTX", "main": "MAIN", "complement": "CMP"}


# --------------------------------------------------------------------------
# Modo destacados: Hormozi, Gadzhi, acumulativo y pintado
# --------------------------------------------------------------------------
# Los bloques ya vienen armados desde dynamic_subtitles.build_destacados_cues
# (en la app): aca solo hay que dibujarlos. Tres de los cuatro looks son un
# Text+ por bloque, igual que el motor normal; el cuarto ('pintado') es
# varias palabras, cada una su propio Text+, y necesita su propio colocador
# (ver _colocar_pintado).
# Montserrat, no Open Sans (v1.0.51): Open Sans NO viene en Windows y
# era el primer motivo por el que el modo destacados se escondio en la
# v1.0.26 — Montserrat viaja incrustada en el programa (fonts/), la
# misma regla que AUTO_STYLES y los presets del Diseño dinamico.
DESTACADOS_ESTILOS = {
    "hormozi": {
        "normal": {
            "font": "Montserrat", "style": "ExtraBold", "size": 0.085,
            "tracking": 1.0, "color": (1.0, 1.0, 1.0),
            "outline": {"thickness": 0.24, "color": (0.0, 0.0, 0.0)},
        },
        "resaltada": {
            "font": "Montserrat", "style": "ExtraBold", "size": 0.085,
            "tracking": 1.0, "color": (1.0, 0.85, 0.08),
            "outline": {"thickness": 0.24, "color": (0.0, 0.0, 0.0)},
        },
    },
    "gadzhi": {
        "normal": {
            "font": "Montserrat", "style": "Bold", "size": 0.10,
            "tracking": 1.0, "color": (1.0, 1.0, 1.0),
        },
        "resaltada": {
            "font": "Montserrat", "style": "Bold", "size": 0.10,
            "tracking": 1.0, "color": (1.0, 0.85, 0.08),
        },
    },
    "acumulativo": {
        "normal": {
            "font": "Montserrat", "style": "SemiBold", "size": 0.065,
            "tracking": 1.0, "color": (1.0, 1.0, 1.0),
        },
        "resaltada": {
            "font": "Montserrat", "style": "SemiBold", "size": 0.065,
            "tracking": 1.0, "color": (1.0, 0.85, 0.08),
        },
    },
}

# El estilo de 'pintado' es distinto de proposito: los otros tres solo
# necesitan VERSE bien, pero en pintado el tamaño y la fuente son los MISMOS
# numeros que uso medir_texto.py en la app para calcular donde va cada
# palabra (ver dynamic_subtitles._armar_pintado). Si aca se usara un tamaño
# distinto al que viajo en el manifiesto, las palabras se verian corridas de
# su sitio -mas grandes o mas chicas de lo que el calculo asumio-. Por eso
# 'estilo_pintado' SIEMPRE se lee del manifiesto (track_info); esto de aca
# es solo el respaldo para un manifiesto viejo que no lo traiga, y en ese
# caso las columnas pueden no alinear perfecto.
ESTILO_PINTADO_RESPALDO = {
    "font": "Montserrat", "style": "Bold", "size": 0.07, "tracking": 1.0,
}
# Tres estados por palabra: la que todavia no se dijo (tenue, para poder leer
# adelantado sin que compita con la que se esta diciendo), la que ya se dijo,
# y la que ya se dijo Y era palabra clave.
COLOR_PINTADO_MUDA = (0.5, 0.5, 0.5)
COLOR_PINTADO_DICHA = (1.0, 1.0, 1.0)
COLOR_PINTADO_DICHA_CLAVE = (1.0, 0.85, 0.08)

# Techo de palabras simultaneas en un bloque 'pintado' (coincide con
# MAX_BLOQUE_3L de dynamic_subtitles.py, que es lo que limita segmentar()).
# Cada palabra necesita DOS pistas (ver _colocar_pintado), asi que el techo
# real de pistas es el doble de esto -y solo se crean las que hagan falta
# de verdad, nunca las 9 de entrada-.
MAX_PALABRAS_PINTADO = 9

# Cuanto ANCHO del fotograma puede ocupar una fila del pintado antes de
# envolver a la fila siguiente (v1.0.51). Sin envolver, una frase de 7
# palabras al tamaño de la principal se salia del cuadro en 9:16 — el
# formato de siempre de los clientes de este modo. 0.92 deja un margen
# fino a cada lado; una palabra sola mas ancha que esto no se parte (va en
# su propia fila y sobresale, que es lo menos malo).
ANCHO_MAX_PINTADO = 0.92
# Separacion vertical entre filas del pintado, en multiplos del tamaño del
# texto (interlineado). Fraccion de la ALTURA, como Size.
INTERLINEA_PINTADO = 1.35


import time as _time

# El registro ENTERO de Studio (v2.0.4). Hasta la v2.0.3 este gemelo
# escribia en ultimo_resultado.txt SOLO 'mensaje' y sus 135 print() iban
# a la stdout de la app, que el .app/.exe descarta: tres versiones de
# arreglos de Studio (v2.0.1/2/3) se hicieron A CIEGAS y la «Huella de
# colocacion» de la v2.0.3 nunca se pudo leer. El gemelo Lua envuelve su
# print en _salida desde siempre; aqui se hace lo mismo con un print de
# MODULO: resolve_bridge corre este archivo con module_from_spec, asi que
# el nombre vive solo en este modulo (builtins intacto, la app no lo ve)
# y _salida nace vacia en cada corrida.
_salida = []
_print_original = print


def print(*args, **kwargs):
    _salida.append(" ".join(str(a) for a in args))
    try:
        _print_original(*args, **kwargs)
    except Exception:
        pass


def guardar_resultado(ok, mensaje):
    """Deja el resultado donde la app lo pueda leer.

    Escribe LOS DOS: el .txt (lo que veria un humano, para 'Ver que
    respondio Resolve') y el .json (lo que lee la app para el resumen
    despues de generar). Sin esto, la app le pedia a
    resolve_bridge.ultimo_resultado() -sin 'desde='- lo ultimo que hubiera
    en disco, y si el ultimo en escribir habia sido el script de Importar
    Estilos, el aviso de una importacion vieja aparecia pegado a una
    generacion que no tenia nada que ver.
    """
    try:
        SHARED_FOLDER.mkdir(parents=True, exist_ok=True)
        RESULT_TXT_PATH.write_text("\n".join(_salida) or mensaje,
                                   encoding="utf-8")
        RESULT_JSON_PATH.write_text(json.dumps({
            "script": "CineCaptions",
            # La version, como ya hacen los .lua. Sin ella era imposible
            # saber que build habia corrido: en Studio los scripts salen del
            # bundle de la app, asi que este numero ES el de la app.
            "version": VERSION,
            "ok": bool(ok),
            "mensaje": mensaje,
            "cuando": int(_time.time()),
        }, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        print(f"  Aviso: no pude guardar el resultado para la app ({exc}).")


def vista_final(timeline, manifest, solo_pagina=False):
    """v5.5 — lo último que hace el script cuando termina: deja Resolve como el usuario lo quiere VER. El manifiesto trae «vista» = {'pagina': 'edit', 'preset': 'CineCaptions
    vertical', 'al_inicio': True}: la página (Edit), su disposición de pantalla guardada (resolve.LoadLayoutPreset: vertical y vista expandida, la que el usuario guardó una vez) y el
    cabezal al principio del timeline (la app pulsa luego «reproducir»). Nunca falla; cada cosa que no se puede se anota con una línea clara. Gemelo de vista_final del .lua."""
    v = (manifest or {}).get("vista") if isinstance(manifest, dict) else None
    if not isinstance(v, dict):
        return
    try:
        if v.get("pagina"):
            resolve.OpenPage(str(v["pagina"]))
    except Exception as exc:
        print(f"  Aviso: no pude abrir la página «{v.get('pagina')}» de Resolve ({type(exc).__name__}).")
    if solo_pagina:
        return
    preset = str(v.get("preset") or "").strip()
    if preset:
        try:
            lista = resolve.GetLayoutPresetList() or []
            if preset in lista:
                if resolve.LoadLayoutPreset(preset):
                    print(f"  Vista de Resolve: apliqué tu disposición «{preset}».")
                else:
                    print(f"  Aviso: Resolve no aplicó la disposición «{preset}».")
            else:
                print(f"  Aviso: no tienes guardada la disposición de pantalla «{preset}» (Área de trabajo > Presets de diseño > Guardar como nuevo, "
                      "o el botón «Guardar la vista actual de Resolve» de CineCaptions).")
        except Exception as exc:
            print(f"  Aviso: no pude aplicar la disposición de pantalla ({type(exc).__name__}: {exc}).")
    if v.get("al_inicio", True):
        try:
            timeline.SetCurrentTimecode(timeline.GetStartTimecode())
        except Exception as exc:
            print(f"  Aviso: no pude llevar el cabezal al inicio del timeline ({type(exc).__name__}).")


def a_fotogramas(segundos, fps):
    """Segundos -> fotogramas, redondeando SIEMPRE hacia arriba en la mitad.

    No se usa round() de Python: redondea "al par" (round(0.5)=0,
    round(1.5)=2), mientras que el gemelo en Lua hace floor(x+0.5), que es
    mitad-arriba. En un tiempo que cae justo en medio fotograma -0.50 s a 25
    fps = 12.5- Studio daba 12 y Free 13: el MISMO proyecto colocado un
    fotograma distinto segun con que edicion se abriera.
    """
    try:
        return int(math.floor(float(segundos) * float(fps) + 0.5))
    except (TypeError, ValueError):
        return 0


def fail(msg):
    print(f"[CineCaptions] ERROR: {msg}")
    guardar_resultado(False, msg)
    raise SystemExit(1)


# --------------------------------------------------------------------------
# Parser de .srt (sin dependencias externas)
# --------------------------------------------------------------------------

# La coma es lo estandar, pero hay .srt de otras herramientas con punto
# ("00:00:03.250"): el parser los acepta igual, como el gemelo Lua.
SRT_TIME_RE = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})")


def _srt_time_to_seconds(ts: str):
    """Segundos, o None si eso no es un tiempo. Antes lanzaba
    AttributeError con un bloque malformado y tumbaba el .srt entero:
    un bloque roto se salta, no puede costar los otros 200."""
    m = SRT_TIME_RE.match(ts)
    if m is None:
        return None
    h, mnt, s, ms = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(path: str):
    """Devuelve lista de dicts: {start, end, text} (segundos, texto con \\n)."""
    content = Path(path).read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*\n", content.strip())
    cues = []
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip() != ""]
        if len(lines) < 2:
            continue
        time_line_idx = 0
        for i, l in enumerate(lines):
            if "-->" in l:
                time_line_idx = i
                break
        time_line = lines[time_line_idx]
        partes = time_line.split("-->")
        if len(partes) != 2:
            continue        # bloque sin tiempos: se salta, no tumba el resto
        inicio = _srt_time_to_seconds(partes[0].strip())
        fin = _srt_time_to_seconds(partes[1].strip())
        if inicio is None or fin is None:
            continue
        text = "\n".join(lines[time_line_idx + 1:])
        if not text.strip():
            continue
        cues.append({"start": inicio, "end": fin, "text": text})
    return cues


# --------------------------------------------------------------------------
# Helpers de Resolve
# --------------------------------------------------------------------------

# El prefijo de los bins que crea este programa para los packs .drt. Se
# compara por prefijo y no por nombre exacto porque cada pack y formato tiene
# el suyo ('RCS · Base titulos dinamicos · v').
PREFIJO_BIN_PACK = "RCS · "


def _es_bin_nuestro(folder):
    try:
        return (folder.GetName() or "").startswith(PREFIJO_BIN_PACK)
    except Exception:
        return False


def find_clips_by_name_ci(media_pool, name, carpeta=None):
    """Busca TODOS los clips cuyo nombre coincide, sin importar mayusculas/
    minusculas ni espacios de mas al principio/final (evita que 'Principal 2'
    no matchee 'principal 2'). Devuelve la lista completa, para poder avisar
    si hay nombres duplicados.

    Con 'carpeta' se busca SOLO ahi dentro. Hace falta para los packs .drt:
    sus clips se dejan en un bin propio, y si la busqueda siguiera saliendo
    a todo el Media Pool, cualquier Text+ suelto llamado 'contexto' que el
    usuario tuviera en su proyecto ganaria sobre el pack que acaba de
    elegir — se aplicaria otro diseño sin una sola linea que lo explicara.
    """
    acotada = carpeta is not None
    raiz = carpeta if acotada else media_pool.GetRootFolder()
    if raiz is None:
        return []
    objetivo = name.strip().lower()
    encontrados = []

    def buscar(folder):
        for clip in folder.GetClipList():
            if clip.GetName().strip().lower() == objetivo:
                encontrados.append(clip)
        for sub in folder.GetSubFolderList():
            # Buscando en TODO el Media Pool, los bins de los packs no
            # cuentan: son NUESTROS, no plantillas del usuario.
            #
            # Sin esto, despues de usar un pack .drt una vez, su bin
            # 'RCS · <pack> · <formato>' se queda en el proyecto con clips
            # llamados 'contexto'/'principal'/'complemento'. En la siguiente
            # generacion SIN pack la busqueda los encontraba, daba
            # modo_plantillas por bueno, y el diseño automatico no llegaba a
            # correr: no se escribia ni una posicion y todo caia amontonado
            # donde dijera el PolyPath del pack -encima, en el formato del
            # bin viejo, no en el del timeline actual-. Los dos sintomas del
            # reporte "el automatico amontona y no respeta el formato".
            #
            # NO se borran: estan en el proyecto del usuario y borrarlos
            # rompe la regla de no destruir nada. Solo dejan de contar.
            if not acotada and _es_bin_nuestro(sub):
                continue
            buscar(sub)

    buscar(raiz)
    return encontrados


_AVISADOS_DUPLICADOS = set()


def find_clip_by_name(media_pool, name, carpeta=None):
    """Busca un clip por nombre (sin importar mayusculas/minusculas). Si hay
    varios clips con el mismo nombre, usa el primero que encuentra y avisa
    una sola vez por nombre para no llenar la consola de avisos repetidos."""
    encontrados = find_clips_by_name_ci(media_pool, name, carpeta)
    if not encontrados:
        return None
    if len(encontrados) > 1 and name not in _AVISADOS_DUPLICADOS:
        _AVISADOS_DUPLICADOS.add(name)
        print(f"  Aviso: hay {len(encontrados)} clips llamados '{name}' "
              "(o con distintas mayusculas) en el Media Pool. Uso el primero "
              "que encontré; borra o renombra los duplicados si no es el "
              "que querías.")
    return encontrados[0]


def find_template_clip(media_pool):
    return find_clip_by_name(media_pool, TEMPLATE_CLIP_NAME)


def plantilla_base_del_pack(media_pool):
    """El clip 'base' de un bin RCS (el pack ya preparado), o None.

    La busqueda global EXCLUYE los bins nuestros a proposito (son del pack,
    no plantillas del usuario); para la pista TRADUCIDA es al reves: se
    quiere justamente la 'base' del pack, asi que se entra solo a ellos.
    """
    try:
        raiz = media_pool.GetRootFolder()
        for sub in (raiz.GetSubFolderList() or []):
            try:
                nombre = sub.GetName() or ""
            except Exception:
                continue
            if not str(nombre).startswith(PREFIJO_BIN_PACK):
                continue
            clip = _buscar_base(media_pool, sub)
            if clip:
                return clip
    except Exception:
        return None
    return None


# ------------------- el pack de SUBTITULOS BASICOS (v1.0.69) -------------
# Dos .drb con 12 clips 'basico|traducion {inferior|superior} {1..3}': el
# usuario elige UNA combinacion en la ventana de Plantillas y viste los
# subtitulos del modo normal ('basico') y su pista traducida ('traducion'
# de la MISMA zona y numero — confirmado por el usuario). OJO con los nombres
# REALES: 'traducion' va sin c y con DOBLE espacio dentro de los .drb; se
# compara con el nombre NORMALIZADO y aceptando tambien 'traduccion', para
# que un .drb futuro corregido no rompa nada. Gemela en el .lua.

def _norm_nombre_basico(texto):
    return re.sub(r"\s+", " ", str(texto or "").strip().lower())


def clip_basico_en(carpeta, tipo, pos, n):
    """El clip 'basico/traducion <pos> <n>' dentro del bin, o None."""
    objetivos = {f"{tipo} {pos} {n}"}
    if tipo == "traducion":
        objetivos.add(f"traduccion {pos} {n}")

    def _buscar(f):
        try:
            clips = f.GetClipList() or []
        except Exception:
            clips = []
        for c in clips:
            try:
                if _norm_nombre_basico(c.GetName()) in objetivos:
                    return c
            except Exception:
                continue
        try:
            subs = f.GetSubFolderList() or []
        except Exception:
            subs = []
        for s in subs:
            hallado = _buscar(s)
            if hallado:
                return hallado
        return None

    return _buscar(carpeta)


def pack_basicos_del_manifiesto(track_info, timeline):
    """El bloque 'plantilla_basicos' resuelto a UN formato, o None.

    Misma regla que pack_del_manifiesto: formato_forzado manda; si no,
    la resolucion del timeline (que solo se conoce aqui); si el formato
    que toca no esta, el mas parecido con aviso — nunca en silencio.
    """
    bruto = track_info.get("plantilla_basicos")
    if not isinstance(bruto, dict):
        return None
    formatos = bruto.get("formatos") or {}
    if not isinstance(formatos, dict) or not formatos:
        return None
    formato = bruto.get("formato_forzado")
    if formato not in formatos:
        formato = None
    if formato is None:
        try:
            ancho = int(float(timeline.GetSetting(
                "timelineResolutionWidth")))
            alto = int(float(timeline.GetSetting(
                "timelineResolutionHeight")))
        except Exception:
            ancho = alto = 0
        deseado = "v" if alto > ancho else "h"
        if deseado in formatos:
            formato = deseado
        else:
            # Mismo orden que el gemelo Free (h, v, c): sorted() daba
            # c, h, v — alfabetico, no el mas parecido.
            formato = next(f for f in ("h", "v", "c") + tuple(sorted(formatos))
                           if f in formatos)
            print(f"  Basicos: el pack no trae el formato '{deseado}'; "
                  f"uso '{formato}'.")
    drb = (formatos.get(formato) or {}).get("drb")
    if not drb:
        return None
    try:
        n = int(bruto.get("n") or 0)
    except (TypeError, ValueError):
        return None
    pos = bruto.get("pos")
    if pos not in ("inferior", "superior") or n < 1:
        return None
    transformaciones = (formatos.get(formato) or {}).get("transformaciones")
    return {"nombre": bruto.get("pack") or "Subtitulos basicos",
            "formato": formato, "pos": pos, "n": n, "drb": drb,
            # v3.3.0: la posicion de superior/inferior y de la traduccion.
            "transformaciones": (transformaciones
                                 if isinstance(transformaciones, dict)
                                 else {})}


def preparar_bin_basicos(media_pool, pb):
    """(bin_con_los_clips, None) o (None, aviso). Nunca lanza.

    Idempotente: si el bin ya trae el clip pedido se reutiliza (correr
    dos veces no re-importa). Calco del peldaño drb: foto del current +
    SetCurrentFolder(bin) + ImportFolderFromFile + restaurar (leccion
    v1.0.33). Verificacion PROPIA re-buscando el clip — NUNCA
    buscar_sets_de_plantillas, que busca contexto/principal. El bin
    lleva el prefijo RCS: la busqueda global de plantillas del usuario
    lo salta sola, y no confunde a plantilla_base_del_pack (no trae
    ningun clip 'base').
    """
    nombre_bin = _nombre_bin_pack(pb["nombre"], pb["formato"])
    try:
        raiz = media_pool.GetRootFolder()
    except Exception:
        return None, "el Media Pool no respondio"
    carpeta = _subcarpeta(raiz, nombre_bin)
    if carpeta is not None and clip_basico_en(carpeta, "basico",
                                              pb["pos"], pb["n"]):
        return carpeta, None
    if not Path(pb["drb"]).is_file():
        return None, f"no encuentro el archivo del pack ({pb['drb']})"
    if carpeta is None:
        try:
            carpeta = media_pool.AddSubFolder(raiz, nombre_bin)
        except Exception:
            carpeta = None
    if not carpeta:
        return None, "no pude crear el bin del pack de basicos"
    try:
        previa = media_pool.GetCurrentFolder()
    except Exception:
        previa = None
    try:
        media_pool.SetCurrentFolder(carpeta)
    except Exception:
        pass
    importo = False
    try:
        importo = bool(media_pool.ImportFolderFromFile(str(pb["drb"])))
    except Exception as exc:
        print("  Basicos: ImportFolderFromFile no está en este Resolve "
              f"({exc}).")
    try:
        if previa is not None:
            media_pool.SetCurrentFolder(previa)
    except Exception:
        pass
    if importo and clip_basico_en(carpeta, "basico", pb["pos"], pb["n"]):
        return carpeta, None
    return None, "no pude meter el bin de basicos en el Media Pool"


# Cuanto baja la pista traducida respecto de donde el pack pone la 'base'.
# Fraccion de la ALTURA del fotograma (la unidad de Center Y). 0.10 separa
# sin mandarla lejos; el piso evita pegarla al borde de abajo.
BAJADA_TRADUCIDA = 0.10
PISO_TRADUCIDA = 0.04


def bajar_center(timeline_item, bajada=BAJADA_TRADUCIDA,
                 piso=PISO_TRADUCIDA):
    """Baja el Center del Text+ de ese clip. True solo si se COMPROBO.

    Es el unico toque de posicion del producto y es pedido explicito: la
    pista traducida convive con la original y sin bajarla se tapan. Guardas
    de siempre: leer antes, comprobar que el valor cambio (SetInput no
    lanza aunque no haga nada, la leccion del fundido), restaurar si no
    aplico, y si el comp no expone Center (grupo con PolyPath) se devuelve
    False y quien llama lo dice en el registro, sin tocar nada.
    """
    tool = get_text_plus_tool(timeline_item)
    if tool is None:
        return False
    try:
        centro = tool.GetInput("Center")
        x, y = float(centro[1]), float(centro[2])
    except Exception:
        return False
    nuevo_y = max(float(piso), y - float(bajada))
    if abs(nuevo_y - y) < 1e-6:
        return True         # ya estaba en el piso: no hay nada que bajar
    try:
        tool.SetInput("Center", [x, nuevo_y])
        confirmado = tool.GetInput("Center")
        cy = float(confirmado[2])
    except Exception:
        return False
    if abs(cy - nuevo_y) > 1e-4:
        try:
            tool.SetInput("Center", [x, y])
        except Exception:
            pass
        return False
    return True


def _buscar_base(media_pool, carpeta=None):
    """La plantilla de las palabras sueltas: 'simple' (nombre nuevo) o 'base' (el de siempre)."""
    for nombre in NOMBRES_BASE:
        clip = find_clip_by_name(media_pool, nombre, carpeta)
        if clip:
            return clip
    return None


def find_base_template(media_pool):
    return _buscar_base(media_pool)


def get_text_plus_tool(timeline_item):
    """Devuelve el nodo Text+ dentro de un clip del timeline, o None."""
    comp = timeline_item.GetFusionCompByIndex(1)
    if not comp:
        return None
    herramientas = comp.GetToolList()
    # los packs viralized llevan varios Text+ de apoyo: el que recibe el texto se llama «Template»
    plantilla = comp.FindTool("Template")
    if plantilla:
        try:
            if plantilla.ID == "TextPlus":
                return plantilla
        except Exception:
            pass
    for name, tool in herramientas.items():
        try:
            if tool.ID == "TextPlus":
                return tool
        except Exception:
            continue
    return None


def set_input_safe(tool, nombre, valor):
    """SetInput que nunca revienta. Devuelve True si funciono."""
    try:
        tool.SetInput(nombre, valor)
        return True
    except Exception:
        return False


# El macro calcula el RECORRIDO de la banda con el DataWindow del texto, que dentro de un macro no llega (queda en su valor por defecto): la banda recorre siempre ~0,31 del ancho del
# cuadro, así que en una palabra ancha (IMPACT, REMARKABLE) sólo pasaba por el centro. Medido en Resolve: recorrido (en anchos de cuadro) ~ 2,17 x (0,193 + inputShine). Se pide
# que la banda vaya de antes de la primera letra a después de la última: ancho de la palabra + 0,16.
BARRIDO_K = 2.17
BARRIDO_BASE = 0.193


def ajustar_barrido(item, visible_s, salto_s=0.0, ancho_rel=None):
    """v5.5 — el BARRIDO DE LUZ del macro Luxe Shine (palabras grandes del estilo «guion»). De fábrica empieza a los 0,25 s y tarda 1,5 s, pero una palabra grande se ve
    ~0,55 s (mediana): el barrido se quedaba a medias en casi todas. Aquí empieza justo al entrar (salto = lo que ya se adelantó el comp) y termina antes de que la palabra
    salga: dura lo que la palabra permite (0,16-0,50 s). Usa las entradas inputOffset / inputLength del macro; si el clip no es un Luxe Shine (presets de Amro) no hace nada.
    Gemela de ajustar_barrido del .lua. Devuelve True si pudo."""
    try:
        comp = item.GetFusionCompByIndex(1)
        if not comp:
            return False
        macro = comp.FindTool("LuxeShine")
        if macro is None:
            for _n, herramienta in comp.GetToolList().items():
                try:
                    if herramienta.GetInput("inputLength") is not None:
                        macro = herramienta
                        break
                except Exception:
                    continue
        if macro is None:
            return False
        largo = max(0.16, min(0.50, float(visible_s) - 0.22))           # la entrada del macro tarda 0,14 s y la salida 0,10: el barrido va entre las dos
        a = set_input_safe(macro, "inputOffset", float(salto_s) + 0.10)
        b = set_input_safe(macro, "inputLength", largo)
        if ancho_rel:
            set_input_safe(macro, "inputShine", max(-0.05, (float(ancho_rel) + 0.16) / BARRIDO_K - BARRIDO_BASE))
        return bool(a and b)
    except Exception:
        return False


# Los clips de las plantillas tienen SU frame rate (los .drb se crearon
# a 30 fps: lo dice su FieldsBlob) y startFrame/endFrame de
# AppendToTimeline son fotogramas DE ORIGEN: Resolve los convierte al
# timeline con floor((endFrame - startFrame) * fps_timeline / fps_clip).
# Medido en el registro de la Mac del usuario (v2.0.4, timeline a 24 fps,
# 40 clips sin excepcion): pedi 19 -> 14, 52 -> 40, 84 -> 66 =
# floor((N - 1) * 24/30). En Windows (timeline a 30 fps) la misma
# formula da N - 1: el «fotograma de menos» de la v2.0.3 era el caso
# k = 1 de esta regla. Por eso Free iba 10/10 en Windows y la Mac salia
# en escalera y con huecos con el MISMO codigo: no era Studio, era el
# fps del timeline. Se pide el mayor span de origen que no se pasa
# (_span_para) con el factor k del clip: GetClipProperty("FPS") si
# contesta, y siempre VERIFICADO con la primera medida — si no cuadra,
# k se aprende del cociente medido (ajustado al frame rate mas cercano:
# el floor pierde precision en clips cortos) y el clip se recoloca.
_FACTORES = {}      # nombre del clip -> fotogramas de timeline por fotograma de origen
_CALIBRADOS = set()  # nombres ya verificados con una medida real
_OFF = {"valor": 0}   # 1 si este Resolve CUENTA el fotograma final (inclusivo)
_FPS_CLIP_CANDIDATOS = (23.976, 24.0, 25.0, 29.97, 30.0, 48.0, 50.0,
                        59.94, 60.0, 120.0)


def _duracion_de(item):
    try:
        return int(float(item.GetDuration() or 0))
    except Exception:
        return 0


def _nombre_clip(plantilla):
    try:
        return str(plantilla.GetName() or "")
    except Exception:
        return ""


def _factor_de(plantilla, fps):
    """Fotogramas de timeline por fotograma de origen de ese clip; 1.0
    si no hay forma de saberlo todavia."""
    nombre = _nombre_clip(plantilla)
    if nombre in _FACTORES:
        return _FACTORES[nombre]
    if fps:
        try:
            fps_clip = float(plantilla.GetClipProperty("FPS") or 0)
        except Exception:
            fps_clip = 0.0
        if fps_clip > 0:
            _FACTORES[nombre] = float(fps) / fps_clip
            return _FACTORES[nombre]
    return 1.0


def _ajustar_factor(k_medido, fps):
    """El factor medido, llevado al cociente de frame rates mas cercano
    (a menos de un 4%); None si ninguno cuadra — entonces NO es un frame
    rate: es un recorte real (comp mas corto que el bloque) y no se toca
    el factor. Sin eso, un comp de 150 sobre un bloque de 270 daba
    k = 0.556, y las hermanas salian LARGAS (solapando al siguiente)."""
    if not fps or k_medido <= 0:
        return None
    mejor = min(_FPS_CLIP_CANDIDATOS,
                key=lambda c: abs(float(fps) / c - k_medido))
    k = float(fps) / mejor
    return k if abs(k - k_medido) <= 0.04 * k else None


def _span_para(duracion, k):
    """Fotogramas de ORIGEN a pedir: el mayor span con
    floor(span * k) <= duracion (con k = 1 es duracion; con k < 1 cae
    exacto; con k > 1 puede quedar uno corto, nunca uno largo)."""
    return max(1, int(math.ceil((duracion - _OFF["valor"] + 1) / k - 1e-9))
               - 1)


def _colocar_medido_base(media_pool, timeline, plantilla, desde, duracion, pista,
                         record, fps=None):
    """AppendToTimeline con la duracion EXACTA en el timeline. Devuelve
    (item, puesto); item None si no se pudo colocar. Sin 'timeline' no
    se puede borrar y recolocar: se usa el factor conocido y no se
    calibra."""
    nombre = _nombre_clip(plantilla)
    k = _factor_de(plantilla, fps)

    def _pedir(k_uso):
        span = _span_para(duracion, k_uso)
        ini = int(round(desde / k_uso)) if desde else 0
        try:
            nuevos = media_pool.AppendToTimeline([{
                "mediaPoolItem": plantilla,
                "startFrame": ini,
                "endFrame": ini + span,
                "trackIndex": pista,
                "mediaType": 1,
                "recordFrame": record,
            }])
        except Exception:
            return None, span
        return (nuevos[0] if nuevos else None), span

    def _recolocar(viejo, k_uso):
        """Borra 'viejo' y vuelve a pedir; si lo nuevo no entra, repone
        con el factor anterior. Devuelve (item, span, puesto); span None
        = no se pudo borrar, el viejo sigue puesto."""
        try:
            timeline.DeleteClips([viejo])
        except Exception:
            return viejo, None, _duracion_de(viejo)
        nuevo, span_n = _pedir(k_uso)
        if nuevo is None:
            nuevo, span_n = _pedir(k)
        return nuevo, span_n, (_duracion_de(nuevo) if nuevo else 0)

    item, span = _pedir(k)
    if item is None:
        return None, 0
    puesto = _duracion_de(item)
    if (timeline is not None and puesto > 0 and puesto != duracion
            and duracion > 1 and nombre not in _CALIBRADOS):
        _CALIBRADOS.add(nombre)
        # 1) ¿Otro frame rate? Solo si el cociente medido se aleja mas
        #    de un 1% del factor en uso (29.97 frente a 30 no cuenta).
        k2 = _ajustar_factor((puesto - _OFF["valor"]) / float(span), fps)
        if k2 is not None and abs(k2 - k) > 0.01 * k:
            _FACTORES[nombre] = k2
            item, span2, puesto = _recolocar(item, k2)
            if item is None:
                return None, 0
            if span2 is None or puesto not in (duracion, duracion + 1):
                # No era el frame rate (un recorte que por casualidad
                # cuadraba): el factor vuelve; el clip queda como salio.
                _FACTORES[nombre] = k
                return item, puesto
            k, span = k2, span2
            print(f"  La plantilla '{nombre}' corre a otro frame rate que "
                  f"el timeline (factor {k2:.3f}): pido {span2} fotogramas "
                  f"de origen por cada {duracion} del timeline.")
        # 2) ¿Fin inclusivo? Un fotograma de MAS con el factor bueno.
        if puesto == duracion + 1 and _OFF["valor"] == 0:
            _OFF["valor"] = 1
            item, span2, puesto = _recolocar(item, k)
            if item is None:
                return None, 0
            if span2 is None:
                _OFF["valor"] = 0
            else:
                print("  Resolve cuenta el fotograma final: pido uno menos "
                      "en todos los clips.")
    elif puesto > 0 and puesto == duracion:
        _CALIBRADOS.add(nombre)
    return item, puesto


# v5.7 (pedido: «colorea los textos y sonidos de naranja, los emojis con su sonido de amarillo y los sonidos de entrada y salida de
# morado para identificarlos en la línea de tiempo»). Nombres de color de Resolve (TimelineItem.SetClipColor).
COLOR_TEXTO = "Orange"
COLOR_SFX = "Orange"
COLOR_EMOJI = "Yellow"
COLOR_SFX_EMOJI = "Yellow"
COLOR_SFX_ENTRADA_SALIDA = "Purple"


def _pintar_clip(item, color):
    """Le pone color al clip en la línea de tiempo. Nunca falla: es solo para identificarlo."""
    if item is None or not color:
        return
    try:
        item.SetClipColor(color)
    except Exception:
        pass


def _color_sfx(categoria):
    c = str(categoria or "")
    if "Introducci" in c or c.endswith("Final"):
        return COLOR_SFX_ENTRADA_SALIDA        # el sonido de entrada y el de salida
    if c == "Emojis":
        return COLOR_SFX_EMOJI
    return COLOR_SFX


def colocar_medido(media_pool, timeline, plantilla, desde, duracion, pista,
                   record, fps=None, color=None):
    """_colocar_medido_base + el color del clip (texto naranja, emoji amarillo)."""
    item, puesto = _colocar_medido_base(media_pool, timeline, plantilla, desde,
                                        duracion, pista, record, fps)
    _pintar_clip(item, color)
    return item, puesto


def set_center_safe(tool, x, y):
    """Mueve el texto. La API de Fusion acepta el punto de varias formas,
    asi que probamos las conocidas hasta que una funcione."""
    for valor in ({1: x, 2: y}, [x, y], (x, y)):
        if set_input_safe(tool, "Center", valor):
            return True
    return False


# La transformacion de pagina Edicion del DISEÑO (v3.3.0; ver el gemelo
# .lua, aplicar_transformacion). La posicion y el zoom de cada clip de un
# pack viven en el project.xml del .drb, no en su comp; la mayoria de los
# Resolve la aplican solos al colocar y en 4 clientes de 550 no — las tres
# lineas salian ENCIMADAS en el centro. Solo se escribe si el clip llego con
# la transformacion NEUTRA. Pan/Tilt en pixeles del timeline.
_TRANSF = {"ya": 0, "puestas": 0, "fallidas": 0, "motivo": None,
           "medida": None}


def _prop_de(item, clave):
    try:
        return float(item.GetProperty(clave))
    except Exception:
        return None


def _poner_props(item, props):
    """21.1 trae SetProperties (y da SetProperty por forma vieja); las
    versiones anteriores solo SetProperty. Se prueban las dos."""
    try:
        if item.SetProperties(props):
            return True
    except Exception:
        pass
    todo = True
    for clave, valor in props.items():
        try:
            if not item.SetProperty(clave, valor):
                todo = False
        except Exception:
            todo = False
    return todo


def _pan_px(x, ancho):
    """Las UNIDADES de Pan/Tilt, en un solo sitio (v3.3.1; ver el gemelo
    .lua): fraccion del ancho/alto del cuadro -> pixeles del timeline."""
    return x * ancho


def _tilt_px(y, alto):
    return y * alto


# ---------------------------------------------------------------------
# La «Composición» (v3.4.0; la definicion vive en composicion.py de la app
# y ESTAS son sus copias gemelas, como en el .lua — test_v340 las compara).
# El layout es la alineacion horizontal de contexto y complemento respecto
# a la PRINCIPAL: dos letras (contexto, complemento) en i/c/d; 'c' = donde
# la dejo la plantilla; "auto" = uno por bloque, elegido por el fotograma en
# que arranca el bloque. Altura/Horizontal desplazan el grupo entero. Sin
# composicion (o "cc" con 0/0) NO se escribe nada: la plantilla manda, como
# desde la v1.0.32. Es opcional: el usuario lo pidio para «ajustar la posicion
# de los textos ya puestos» (recomponer).
# ---------------------------------------------------------------------
ANILLO_AUTO = ("id", "cc", "di", "ic", "dd", "ci", "ii", "cd", "dc")
COMP_TOPE = 0.4
_COMP = {"movidas": 0, "alineadas": 0, "sin_medida": 0, "fallidas": 0,
         "layout": None}


def composicion_normal(c):
    if not isinstance(c, dict):
        c = {}
    layout = str(c.get("layout") or "cc").lower()
    if layout != "auto" and not (len(layout) == 2 and layout[0] in "icd"
                                 and layout[1] in "icd"):
        layout = "cc"

    def _num(v):
        try:
            v = float(v or 0)
        except (TypeError, ValueError):
            v = 0.0
        return max(-COMP_TOPE, min(COMP_TOPE, v))
    try:
        semilla = int(c.get("semilla") or 0) % len(ANILLO_AUTO)
    except (TypeError, ValueError):
        semilla = 0
    return {"layout": layout, "altura": _num(c.get("altura")),
            "horizontal": _num(c.get("horizontal")), "semilla": semilla}


def composicion_es_defecto(comp):
    return (comp["layout"] == "cc" and not comp["altura"]
            and not comp["horizontal"])


def composicion_activa(c):
    """La composicion ACTIVA del track, o None si es la plantilla tal cual."""
    if not isinstance(c, dict):
        return None
    comp = composicion_normal(c)
    return None if composicion_es_defecto(comp) else comp


def layout_del_bloque(comp, bloque):
    """'bloque' = el fotograma donde arranca el bloque (record de su primera
    linea). El floor(bloque / 9) rompe la periodicidad de 9."""
    if comp["layout"] != "auto":
        return comp["layout"]
    try:
        b = max(0, int(bloque or 0))
    except (TypeError, ValueError):
        b = 0
    return ANILLO_AUTO[(b + b // 9 + comp["semilla"]) % len(ANILLO_AUTO)]


def desplazamiento_layout(lado, w_main, w_linea):
    if lado == "i":
        return -(float(w_main) - float(w_linea)) / 2.0
    if lado == "d":
        return (float(w_main) - float(w_linea)) / 2.0
    return 0.0


def desplazamientos_bloque(comp, bloque, lineas, ancho_tl, alto_tl):
    """Los desplazamientos (px) de las lineas de UN bloque. 'lineas' es una
    lista de {rol, ancho_em (o None), zx}. Devuelve (lista paralela de
    {dx, dy, alineada, sin_medida}, layout): la principal y las base solo
    reciben los globales; contexto/complemento ademas la alineacion, si
    hay medida suya Y de la principal."""
    dx_g = _pan_px(comp["horizontal"], ancho_tl)
    dy_g = _tilt_px(comp["altura"], alto_tl)
    layout = layout_del_bloque(comp, bloque)
    lado = {"context": layout[0], "complement": layout[1]}
    w_main = None
    for l in lineas:
        if l.get("rol") == "main" and l.get("ancho_em") is not None:
            w_main = float(l["ancho_em"]) * alto_tl * float(l.get("zx") or 1)
    fuera = []
    for l in lineas:
        dx, alineada, sin_medida = dx_g, False, False
        ld = lado.get(l.get("rol"))
        if ld and ld != "c":
            if w_main is not None and l.get("ancho_em") is not None:
                dx += desplazamiento_layout(
                    ld, w_main,
                    float(l["ancho_em"]) * alto_tl * float(l.get("zx") or 1))
                alineada = True
            else:
                sin_medida = True
        fuera.append({"dx": dx, "dy": dy_g, "alineada": alineada,
                      "sin_medida": sin_medida})
    return fuera, layout


def _reiniciar_composicion(layout=None):
    _COMP.update(movidas=0, alineadas=0, sin_medida=0, fallidas=0,
                 layout=layout)


def informe_composicion():
    if _COMP["layout"] is None:
        return
    extra = (f", {_COMP['fallidas']} sin poder mover (la API dijo que no)"
             if _COMP["fallidas"] else "")
    print(f"  Composición: layout {_COMP['layout']}, {_COMP['movidas']} "
          f"clip(s) movido(s), {_COMP['alineadas']} línea(s) alineada(s), "
          f"{_COMP['sin_medida']} sin medida{extra}.")


def aplicar_transformacion(item, t, ancho, alto):
    if not isinstance(t, (list, tuple)) or len(t) != 4 or item is None:
        return
    try:
        x, y, zx, zy = (float(v) for v in t)
    except (TypeError, ValueError):
        return
    if (x, y, zx, zy) == (0.0, 0.0, 1.0, 1.0):
        return
    pan, tilt = _prop_de(item, "Pan"), _prop_de(item, "Tilt")
    zoom = _prop_de(item, "ZoomX")
    if ((pan is not None and abs(pan) > 0.01)
            or (tilt is not None and abs(tilt) > 0.01)
            or (zoom is not None and abs(zoom - 1) > 0.0001)):
        _TRANSF["ya"] += 1
        if _TRANSF["medida"] is None and tilt is not None and y:
            _TRANSF["medida"] = f"Tilt {tilt:.1f} para Y {y:.4f}"
        return
    pedido = {"Pan": _pan_px(x, ancho), "Tilt": _tilt_px(y, alto),
              "ZoomX": zx, "ZoomY": zy}
    ok = _poner_props(item, pedido)
    leido = _prop_de(item, "Tilt")
    if ok and (leido is None or abs(leido - pedido["Tilt"]) < 1):
        _TRANSF["puestas"] += 1
    else:
        _TRANSF["fallidas"] += 1
        _TRANSF["motivo"] = _TRANSF["motivo"] or (
            f"pedí Tilt {pedido['Tilt']:.1f} y quedó {leido}" if ok
            else "SetProperty no respondió")


def _reiniciar_transformaciones():
    _TRANSF.update(ya=0, puestas=0, fallidas=0, motivo=None, medida=None)


def informe_transformaciones():
    """Una linea cerca del FINAL del registro (lo que se lee primero)."""
    partes = []
    if _TRANSF["ya"]:
        partes.append(f"Resolve ya la traía en {_TRANSF['ya']} línea(s)")
    if _TRANSF["puestas"]:
        partes.append(f"la apliqué yo en {_TRANSF['puestas']} (tu Resolve "
                      "la había dejado en el centro)")
    if _TRANSF["fallidas"]:
        partes.append(f"NO pude en {_TRANSF['fallidas']}: "
                      f"{_TRANSF['motivo'] or '?'}")
    if partes:
        extra = f" ({_TRANSF['medida']})" if _TRANSF["medida"] else ""
        print("  Posición del diseño: " + "; ".join(partes) + extra + ".")


# v3.0.3: las pistas BLOQUEADAS se RESPETAN (decision explicita de
# El usuario, 15-09: «imagina si hay algun efecto o tengo planeado poner algo
# ahi: que respete lo bloqueado y no toque nada de las pistas ocupadas»).
# Reporte de origen (Mac Studio): «tenia bloqueada una pista y no busco
# crear nueva pista; cuando la desbloquee funciono normal» — hasta la
# v3.0.1 el candado se ignoraba, Resolve rechazaba cada clip y la linea
# desaparecia sin decir por que. La v3.0.2 QUITABA el candado para
# trabajar y lo reponia: RETIRADO el mismo dia por esa orden — no lo
# revivas. Una pista con candado cuenta como NO reutilizable, igual que
# una con contenido ajeno (_pista_*_reutilizable la rechazan): se deja
# tal cual y se crea otra encima, diciendolo una vez. Consecuencia
# asumida: los subtitulos viejos de una pista bloqueada se quedan (no se
# pueden vaciar sin tocar el candado). Un Resolve sin GetIsTrackLocked se
# comporta como siempre.
_BLOQUEADAS_AVISADAS = set()


def _pista_bloqueada(timeline, tipo, indice):
    try:
        bloqueada = bool(timeline.GetIsTrackLocked(tipo, indice))
    except Exception:
        return False
    if bloqueada and (tipo, indice) not in _BLOQUEADAS_AVISADAS:
        _BLOQUEADAS_AVISADAS.add((tipo, indice))
        print(f"  La pista {tipo} {indice} está bloqueada: no la toco "
              "(si tiene subtítulos viejos, seguirán ahí).")
    return bloqueada


def _limpiar_pista(timeline, tipo, indice):
    """Borra TODOS los clips de una pista (video o audio) para poder
    re-generar sin solaparlos con los anteriores.

    Se usa cuando se reutiliza una pista existente (ES-CTX, ES-MAIN,
    ES-CMP, SFX). Devuelve la cantidad de clips borrados. Best-effort:
    si DeleteClips no esta disponible o falla en algunos items, sigue
    con los que si pudo borrar.
    """
    if not indice:
        return 0
    try:
        items = timeline.GetItemListInTrack(tipo, indice) or []
    except Exception:
        items = []
    if not items:
        return 0
    # v3.0.2: DeleteClips devuelve False EN SILENCIO (pista bloqueada) y
    # aqui se contaba «N borrados» sin borrar nada; solo cuenta si dijo
    # que si, y si no, el bucle de abajo mide clip a clip.
    try:
        if timeline.DeleteClips(items):
            return len(items)
    except Exception:
        pass
    borrados = 0
    for it in items:
        try:
            if timeline.DeleteClips([it]):
                borrados += 1
        except Exception:
            continue
    return borrados


def _crear_pista_verificada(timeline, tipo, nombre, args_extra=None):
    """Crea una pista y devuelve (indice, error).

    NUNCA calcula el indice a ojo (eso es lo que rompia esto: si AddTrack
    fallaba en silencio, 'cantidad + 1' apuntaba a una pista YA EXISTENTE
    -normalmente V1, con el b-roll del usuario- y ahi se le escribian
    encima los ~150 clips de subtitulo a lo largo de todo el timeline).

    Aca se confirma en dos pasos independientes que la pista es de verdad
    nueva:
      1. GetTrackCount tiene que haber subido en exactamente 1.
      2. La pista en ese indice tiene que estar VACIA.
    Si cualquiera de los dos falla, se devuelve (None, motivo) y el que
    llama tiene que abortar esa parte en vez de usar un indice dudoso.
    """
    try:
        antes = timeline.GetTrackCount(tipo)
    except Exception as e:
        return None, f"no pude leer GetTrackCount('{tipo}'): {e}"

    try:
        if args_extra:
            ok = timeline.AddTrack(tipo, *args_extra)
        else:
            ok = timeline.AddTrack(tipo)
    except Exception as e:
        ok = False
        motivo_add = str(e)
    else:
        motivo_add = None

    try:
        despues = timeline.GetTrackCount(tipo)
    except Exception as e:
        return None, f"no pude releer GetTrackCount('{tipo}'): {e}"

    if despues != antes + 1:
        detalle = f" ({motivo_add})" if motivo_add else ""
        return None, (f"AddTrack('{tipo}') no sumo una pista nueva "
                      f"(antes={antes}, despues={despues}, ok={ok}){detalle}")

    idx = despues
    try:
        items = timeline.GetItemListInTrack(tipo, idx) or []
    except Exception as e:
        return None, f"no pude comprobar si la pista {idx} esta vacia: {e}"

    if items:
        # No deberia pasar nunca (acabamos de crearla), pero si pasa es
        # justo el escenario peligroso: mejor abortar que arriesgar.
        return None, (f"la pista {tipo} {idx} recien creada ya tiene "
                      f"{len(items)} clip(s); no la uso")

    try:
        timeline.SetTrackName(tipo, idx, nombre)
    except Exception:
        pass  # el nombre es cosmetico; el indice ya esta verificado

    return idx, None


def _es_clip_texto_nuestro(item):
    """True si un item del timeline es un Text+ (lo que nosotros ponemos).

    Se usa para decidir si una pista que YA EXISTE con ese nombre es
    segura de limpiar y reutilizar, o si en realidad es una pista ajena
    (b-roll, musica) que por casualidad -o por un run anterior fallado-
    quedo con un nombre que coincide con el nuestro.
    """
    try:
        if get_text_plus_tool(item) is not None:
            return True
    except Exception:
        pass
    # v3.3.0: tambien NUESTROS emojis (rcs_emoji_*.png); sin esto la pista
    # EMOJI contaba como ajena y cada corrida apilaba otra (ver el .lua).
    # v5.8: y las SECUENCIAS animadas (e_[0001-0023].png, en .../emojis_secuencia/<emoji>/): su nombre no
    # empieza por rcs_emoji_, asi que al volver a generar la pista de emojis se apilaba otra (se ve doble).
    try:
        nombre = str(item.GetName() or "").lower()
        if nombre.startswith("rcs_emoji_"):
            return True
        if nombre.startswith("e_["):
            mpi = item.GetMediaPoolItem()
            ruta = str(mpi.GetClipProperty("File Path") or "") if mpi else ""
            return "emojis_secuencia" in ruta.replace("\\", "/").lower()
        return False
    except Exception:
        return False


def _pista_video_reutilizable(timeline, indice):
    """True si una pista de video existente es SOLO nuestra: vacia, o con
    puros clips Text+. Si encuentra aunque sea uno que no es Text+ (video
    real, imagen, lo que sea), la pista no se toca. Con candado (v3.0.3)
    tampoco: cuenta como ajena."""
    if _pista_bloqueada(timeline, "video", indice):
        return False
    try:
        items = timeline.GetItemListInTrack("video", indice) or []
    except Exception:
        return False
    return all(_es_clip_texto_nuestro(it) for it in items)


def _pista_audio_reutilizable(timeline, indice, duracion_maxima_frames):
    """True si una pista de audio existente es segura de limpiar: vacia, o
    con clips cortos (duracion tipica de un efecto de sonido). Si hay algo
    mas largo que 'duracion_maxima_frames' (musica, voz, ambiente), se
    trata como ajeno y no se toca. Con candado (v3.0.3) tampoco."""
    if _pista_bloqueada(timeline, "audio", indice):
        return False
    try:
        items = timeline.GetItemListInTrack("audio", indice) or []
    except Exception:
        return False
    for it in items:
        try:
            dur = it.GetDuration()
        except Exception:
            return False  # si no podemos confirmar que es corto, no arriesgamos
        if dur is None or dur > duracion_maxima_frames:
            return False
    return True


# Un efecto de sonido nuestro nunca dura mas que esto. Cualquier clip mas
# largo en una pista que reutilizamos por nombre es, con altisima
# probabilidad, contenido del usuario y no nuestro.
DURACION_MAXIMA_SFX_SEGUNDOS = 20


def find_any_generator_clip(media_pool):
    """Busca CUALQUIER Text+/generador ya presente en el Media Pool, sin
    depender de un nombre exacto. Muchos proyectos ya traen un titulo
    arrastrado a mano; reusarlo es gratis y de riesgo cero (es una
    busqueda, no toca el timeline).

    El tipo de clip lo expone GetClipProperty('Type'); segun la version
    de Resolve puede decir 'Generator', 'Fusion Title', 'Title', etc.
    Se acepta cualquiera que mencione alguna de esas palabras.
    """
    # Mismas palabras que _es_generador (localizadas incluidas) y un
    # respaldo por NOMBRE: un clip llamado «Text+» (el arrastre de Effects
    # conserva ese nombre) se acepta aunque su Type venga en un idioma que
    # no conozcamos.
    palabras = ("generator", "fusion title", "title", "texto", "text",
                "generador", "titulo", "título")
    root = media_pool.GetRootFolder()

    def buscar(folder):
        for clip in folder.GetClipList():
            try:
                tipo = str(clip.GetClipProperty("Type") or "").lower()
            except Exception:
                tipo = ""
            if any(p in tipo for p in palabras):
                return clip
            try:
                nombre = str(clip.GetName() or "").lower()
            except Exception:
                nombre = ""
            if "text+" in nombre or "texto+" in nombre:
                return clip
        for sub in folder.GetSubFolderList():
            encontrado = buscar(sub)
            if encontrado:
                return encontrado
        return None

    return buscar(root)


def crear_text_plus_en_zona_vacia(timeline, media_pool):
    """Crea un Text+ SIN arriesgar tocar el contenido del usuario.

    'InsertFusionTitleIntoTimeline' inserta en la pista de video activa,
    en el playhead — si el playhead esta sobre el b-roll, hay riesgo de
    pisarlo. Aca se mueve el playhead a una zona GARANTIZADO vacia (varios
    segundos despues del ultimo clip de cualquier pista) antes de insertar,
    y se restaura el playhead original al terminar, pase lo que pase.

    Devuelve el MediaPoolItem, o None si no se pudo (por ejemplo porque
    esta version de Resolve no expone 'InsertFusionTitleIntoTimeline' —
    es el caso de Resolve Free, confirmado en la consola del usuario).
    """
    # No se corta por hasattr: se intenta y se comprueba el resultado, igual
    # que el gemelo Lua. Si el metodo no esta, el try de abajo lo absorbe.
    try:
        fps = float(timeline.GetSetting("timelineFrameRate"))
    except Exception:
        fps = 30.0

    try:
        tc_original = timeline.GetCurrentTimecode()
    except Exception:
        tc_original = None

    try:
        fin = int(timeline.GetEndFrame())
        inicio_tl = int(timeline.GetStartFrame())
    except Exception:
        return None

    zona_vacia = fin + a_fotogramas(5, fps)  # 5s despues del ultimo clip

    def _frame_a_tc(frame):
        total = max(0, frame)
        h = total // (3600 * int(round(fps)))
        resto = total % (3600 * int(round(fps)))
        m = resto // (60 * int(round(fps)))
        resto = resto % (60 * int(round(fps)))
        s = resto // int(round(fps))
        f = resto % int(round(fps))
        return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

    moved = False
    try:
        timeline.SetCurrentTimecode(_frame_a_tc(zona_vacia))
        moved = True
    except Exception:
        pass

    mp_item = None
    via = None
    try:
        # Las dos inserciones que documenta la API; la segunda no se
        # intentaba nunca.
        for metodo in ("InsertFusionTitleIntoTimeline",
                       "InsertFusionGeneratorIntoTimeline"):
            for nombre in ("Text+", "Texto+", "Text"):
                try:
                    item = getattr(timeline, metodo)(nombre)
                except Exception:
                    item = None
                if not item:
                    continue
                try:
                    mp_item = item.GetMediaPoolItem()
                except Exception:
                    mp_item = None
                if mp_item:
                    via = f"{metodo} + GetMediaPoolItem"
                else:
                    # Free no promueve con GetMediaPoolItem, pero la
                    # insercion PUEDE dejar el generador en el Media Pool.
                    # Aqui solo se llega si no habia ninguno (lo busco
                    # obtener_text_plus_base), asi que el que aparezca ahora
                    # es el nuestro. Mismo truco de la foto que salva al .drt.
                    mp_item = find_any_generator_clip(media_pool)
                    if mp_item:
                        via = f"{metodo} + lo dejó en el Media Pool"
                try:
                    timeline.DeleteClips([item])
                except Exception:
                    pass
                if not mp_item:
                    mp_item = find_any_generator_clip(media_pool)
                    if mp_item:
                        via = f"{metodo} + apareció al borrar el clip"
                if mp_item:
                    break
            if mp_item:
                break
    finally:
        if moved and tc_original:
            try:
                timeline.SetCurrentTimecode(tc_original)
            except Exception:
                pass

    if mp_item:
        print(f"  Creé un Text+ automáticamente en una zona vacía del "
              f"timeline (vía {via}).")
    else:
        print("  No pude crear un Text+: ni InsertFusionTitleIntoTimeline ni "
              "InsertFusionGeneratorIntoTimeline dejaron uno en el Media Pool "
              "en esta versión de Resolve.")
    return mp_item


def obtener_text_plus_base(timeline, media_pool):
    """Consigue un Text+ para clonar, probando en orden de menor a mayor
    riesgo. Nunca toca el contenido existente del usuario:

      1. Plantilla con nombre exacto ('base' o 'Subtitle Template').
      2. Cualquier generador/Text+ que ya este en el Media Pool.
      3. (Studio) crear uno nuevo en una zona vacia del timeline.

    Si ninguna funciona, devuelve None: el llamador debe avisar y NO
    colocar nada, en vez de arriesgar.
    """
    plantilla = find_template_clip(media_pool) or find_base_template(media_pool)
    if plantilla:
        return plantilla

    encontrado = find_any_generator_clip(media_pool)
    if encontrado:
        print(f"  Usando el Text+ '{encontrado.GetName()}' que ya estaba "
              "en tu Media Pool.")
        return encontrado

    return crear_text_plus_en_zona_vacia(timeline, media_pool)


def _buscar_plantilla_numerada(media_pool, base, numero, carpeta=None):
    """Busca 'contexto 3' probando las formas de numerar mas comunes. El set 1 es el nombre a secas ('arriba'),
    pero tambien vale con el 1 puesto ('arriba 1', 'arriba1'...): quien arma un pack sigue la misma regla en los tres."""
    if numero == 1:
        clip = find_clip_by_name(media_pool, base, carpeta)
        if clip:
            return clip
    for patron in SUFIJOS_DE_SET:
        clip = find_clip_by_name(media_pool, base + patron.format(n=numero),
                                 carpeta)
        if clip:
            return clip
    return None


def buscar_sets_de_plantillas(media_pool, carpeta=None):
    """Busca TODOS los sets numerados que existan, del 1 al MAX_SETS.

    Devuelve (sets, informe). 'sets' es una lista de diccionarios {rol: clip}
    y 'informe' es una lista de textos para imprimir en consola, para que se
    vea exactamente que encontro y que le falto a cada set — si uno no
    aparece, ahi se ve por que.

    Un set esta COMPLETO cuando tiene los tres roles. Si hay al menos uno
    completo se usan SOLO los completos, y los incompletos se omiten con una
    linea en el registro -"trabaja con los que haya y omite el incompleto"-.

    Hasta la v1.0.29 se devolvia cualquier set con AL MENOS UNA plantilla y
    los roles que faltaran se tomaban del set 1... y si el set 1 tampoco lo
    tenia, la linea acababa usando la plantilla de 'principal'. Eso es lo que
    se veia en Windows Free como "el bloque usa el estilo del principal donde
    tocaba complemento": con clips sueltos a medio arrastrar en la raiz del
    Media Pool (10 principales, 6 contextos, 2 complementos) TODOS los
    complementos caian a la plantilla de principal, sin una sola linea que lo
    explicara. En Mac no paso porque alli el bin del pack se preparo entero.

    Cuando NINGUN set esta completo se devuelven tal cual, sin rellenar: la
    colocacion elige por bloque un set que tenga los roles de ESE bloque, y
    omite el bloque si no hay ninguno. Mezclar roles de sets distintos se
    veia como "el pack no respeta el diseño" (v1.0.32), y sustituir un rol
    por 'principal' era el aviso de "falta x texto" en la cara del usuario.
    """
    crudos = []
    for numero in range(1, MAX_SETS + 1):
        encontrado = {}
        faltan = []
        for rol, base in DYNAMIC_TEMPLATES.items():
            clip = None
            for nombre_base in NOMBRES_ROL.get(rol, (base,)):
                clip = _buscar_plantilla_numerada(media_pool, nombre_base, numero, carpeta)
                if clip:
                    break
            if clip:
                encontrado[rol] = clip
            else:
                nombre_nuevo = NOMBRES_ROL.get(rol, (base,))[0]
                faltan.append(f"{nombre_nuevo} {numero}" if numero > 1 else nombre_nuevo)
        if encontrado:
            # El numero del BIN viaja con el set (v1.0.61): el indice de la
            # lista NO es ese numero (los incompletos se descartan) y el
            # veto de tildes del manifiesto se expresa en numeros de bin.
            encontrado["numero"] = numero
            crudos.append((numero, encontrado, faltan))

    if not crudos:
        return [], []

    def _nombres(encontrado):
        return ", ".join(sorted(c.GetName() for r, c in encontrado.items()
                                if r != "numero"))

    completos = [(n, e) for n, e, f in crudos if not f]
    informe = []

    if completos:
        # El caso normal: hay sets con los tres roles, y los incompletos
        # sobran. Se OMITEN, no se rellenan.
        for i, (numero, encontrado) in enumerate(completos, 1):
            informe.append(f"  Set {i} (numero {numero}): {_nombres(encontrado)}")
        omitidos = [str(n) for n, e, f in crudos if f]
        if omitidos:
            # A registro, no a la cara del usuario: trabajar con los que hay
            # y callar el incompleto es exactamente lo que se pidio.
            informe.append(
                f"  Omito el/los set(s) {', '.join(omitidos)}: no tienen los "
                f"tres roles. Uso solo los {len(completos)} completos.")
        return [e for _, e in completos], informe

    # Ningun set completo: se devuelven TAL CUAL, sin rellenar.
    #
    # Hasta la v1.0.32 aqui se completaba cada set con el rol que faltara,
    # tomandolo de otro set. Eso mezclaba diseños dentro de un mismo bloque
    # (contexto de un set, principal de otro) y era el reporte de "no
    # respeta la posicion, el color ni la tipografia" con un pack propio.
    # Ahora la colocacion elige, bloque a bloque, un set que tenga TODOS los
    # roles de ESE bloque, y si no hay ninguno omite el bloque entero —
    # pedido literal: "si falta x bloque debe ignorar por completo ese
    # bloque". Un set incompleto sigue sirviendo para los bloques de dos
    # lineas cuyos roles si tenga.
    sets = []
    for numero, encontrado, faltan in crudos:
        sets.append(encontrado)
        detalle = f"  Set {len(sets)} (numero {numero}): {_nombres(encontrado)}"
        if faltan:
            detalle += f"  [incompleto: le falta {', '.join(faltan)}]"
        informe.append(detalle)
    informe.append(
        "  Ningun set tiene los tres roles. Uso cada uno solo en los bloques "
        "cuyos roles tenga; los que no encajen se omiten (no mezclo estilos "
        "de sets distintos).")
    return sets, informe


# Los 14 caracteres que una caligrafica puede no traer (Tempting.otf no
# mapea ninguno). Copia gemela en CineCaptions_Subtitulos.lua (tiene_acentos):
# alli son secuencias UTF-8 literales — un test las compara byte a byte.
ACENTOS = "áéíóúÁÉÍÓÚñÑüÜ"


def tiene_acentos(texto):
    return any(c in ACENTOS for c in (texto or ""))


def _set_para(sets, preferido, roles, vetado=None):
    """El set que sirve para un bloque con esos roles, o None.

    Se prueba primero el que le tocaba por rotacion y despues los demas
    SIGUIENDO LA RUEDA desde ese (v2.0.2, reporte literal: «no esta
    mezclado bien las combinaciones»): hasta la v2.0.1 el respaldo
    recorria los sets en orden ascendente desde el 0, asi que cada bloque
    cuyo set programado no servia — el veto de tildes tumba el
    complemento de 4 de los 10 sets de «Titulos dinamicos II», y casi
    todo complemento en español lleva tilde — caia al set 1, uno tras
    otro. NUNCA se mezclan dos sets en el mismo bloque: el diseño de un
    bloque sale entero de un solo set o el bloque no se coloca.

    'vetado' (v1.0.61, pedido literal: «si la palabra tiene tilde no uses
    la combinacion de la tipografia Tempting») es {rol: [numeros de bin]}
    SOLO con los roles cuyo texto de ESTE bloque lleva tilde: un set cuyo
    numero este ahi no sirve. Un set sin numero parseable no se veta
    nunca — mejor el riesgo de una tilde fea que omitir diseño sano.
    """
    if not sets:
        return None
    orden = [(preferido + k) % len(sets) for k in range(len(sets))]
    for i in orden:
        if not all(sets[i].get(rol) for rol in roles):
            continue
        if vetado:
            numero = sets[i].get("numero")
            if numero is not None and any(
                    numero in (vetado.get(rol) or ())
                    for rol in vetado):
                continue
        return sets[i]
    return None


# --------------------------------------------------------------------------
# Packs .drt: importar el timeline y pasar sus clips al Media Pool
# --------------------------------------------------------------------------
# Un pack .drt es el timeline exportado tal cual: cada rol es en realidad un
# GroupOperator (SoftGlow + TextPlus + StyledTextFollower + PolyPath +
# curvas), no un Text+ suelto. La API de Resolve no tiene una llamada oficial
# para "promover" un clip ya puesto en un timeline a un item del Media Pool
# CON su estilo -por eso esto es una escalera que se prueba a si misma, no
# una sola llamada de la que fiarse-.

def _leer_capacidades():
    try:
        return json.loads(CAPACIDADES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _recordar_capacidad(clave, valor):
    datos = _leer_capacidades()
    if valor is None:
        # Olvidar: la clave desaparece del archivo, no queda un null que
        # el lector confunda con "ya se probo y no hay".
        datos.pop(clave, None)
    else:
        datos[clave] = valor
    try:
        CAPACIDADES_PATH.write_text(
            json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass    # no es grave: en el peor caso se vuelve a probar la proxima vez


def _nombre_bin_pack(nombre_pack, formato):
    # El prefijo tiene que ser el mismo que mira _es_bin_nuestro(): de eso
    # depende que estos bins no se confundan con las plantillas del usuario.
    return f"{PREFIJO_BIN_PACK}{nombre_pack} · {formato}"


def _subcarpeta(folder, nombre):
    for sub in folder.GetSubFolderList():
        if sub.GetName() == nombre:
            return sub
    return None


def parsear_nombre_pack(bruto):
    """Gemela de packs_drt.parsear_nombre() (la app). 'Arriba 2' -> ('context', 2),
    'Contexto 8' -> ('context', 8), 'simple' -> ('base', 0), 'imagen 3' -> ('image', 3).
    Los tres (esta, la de la app y la del .lua) tienen que dar lo mismo o el pack se ve
    distinto segun quien lo lea."""
    n = (bruto or "").strip().lower()
    n = re.sub(r"\.[a-z]+$", "", n)
    if n in NOMBRES_BASE:
        return "base", 0
    for rol, palabras in list(NOMBRES_ROL.items()) + [("image", (NOMBRE_IMAGEN,))]:
        for palabra in palabras:
            if n == palabra:
                return rol, 1
            m = re.match(r"^" + re.escape(palabra) + r"[\s\-_.]*0*(\d+)$", n)
            if m:
                k = int(m.group(1))
                tope = MAX_VARIANTES if palabra in NOMBRES_SOLO_NUEVOS else MAX_SETS
                return (rol, k) if 1 <= k <= tope else (rol, -1)
    return None, 0


def _renombrar_clip(clip, nombre):
    """Le pone ese nombre a un MediaPoolItem. True si lo consiguio.

    Se prueban las dos formas: SetClipProperty("Clip Name", ...) es la
    documentada, pero no todas las versiones la aceptan para generadores.
    Y se COMPRUEBA leyendo el nombre de vuelta, porque las dos devuelven
    algo verdadero sin haber hecho nada.
    """
    for intento in ("propiedad", "setname"):
        try:
            if intento == "propiedad":
                clip.SetClipProperty("Clip Name", nombre)
            else:
                clip.SetName(nombre)
            if (clip.GetName() or "").strip().lower() == nombre.strip().lower():
                return True
        except Exception:
            continue
    return False


def _promover_uno(metodo, media_pool, timeline_importado, item, nombre,
                  carpeta_destino):
    """MUEVE un clip del timeline importado al bin del pack, con su nombre.

    Devuelve True solo si al final existe un clip con ese nombre dentro de
    'carpeta_destino'. Se comprueba mirando el bin, no confiando en que la
    llamada devolviera algo: devuelve objetos que parecen validos aunque no
    hayan dejado nada donde hace falta.

    POR QUE SOLO SE MUEVE, Y NO SE COMPONE
    ======================================
    Hasta la v1.0.27 se probaba antes 'Timeline:CreateFusionClip', por ser la
    unica llamada documentada. Era un error, y de los caros:
    CreateFusionClip ENVUELVE el clip -aunque le pases uno solo- en un
    "Fusion Clip". El Text+ deja de estar en el nivel superior del comp, asi
    que get_text_plus_tool() devuelve None al generar y CADA LINEA ENTRA SIN
    TEXTO. Doscientos clips vacios.

    Y la verificacion de entonces no podia detectarlo, porque comparaba
    NOMBRES: los Fusion Clips renombrados a 'contexto'/'principal' pasaban el
    filtro. La generacion no pregunta como se llama un clip, pregunta si trae
    un TextPlus de primer nivel. De ahi _sirve_para_subtitulos().
    """
    if metodo != "media_item":
        return False
    try:
        mpi = item.GetMediaPoolItem()
        if not mpi:
            return False
        # Traerlo al bin del pack. Si no se puede mover, no sirve: la
        # busqueda esta limitada a ese bin a proposito.
        try:
            media_pool.MoveClips([mpi], carpeta_destino)
        except Exception:
            return False
        _renombrar_clip(mpi, nombre)
    except Exception:
        return False

    return bool(find_clips_by_name_ci(media_pool, nombre, carpeta_destino))


def _sirve_para_subtitulos(timeline_desechable, media_pool, clip):
    """¿Este clip del Media Pool sirve de plantilla de subtitulo?

    LA pregunta, y la unica que vale: se coloca de verdad y se mira si trae
    un TextPlus DE PRIMER NIVEL -exactamente lo que hara get_text_plus_tool()
    al generar-.

    Hasta la v1.0.27 esto se comprobaba por NOMBRE, y por eso un clip
    precompuesto pasaba el filtro y luego salia sin texto en las ~200 lineas.
    Un nombre no dice nada de lo que hay dentro.

    Se prueba en el timeline IMPORTADO del pack, que es de usar y tirar, no
    en el del usuario: asi la comprobacion no le deja ni una pista ni un clip
    en su montaje, pase lo que pase.

    Devuelve True, False, o None cuando no se pudo comprobar -que no es lo
    mismo que False y quien llama tiene que distinguirlo-.
    """
    if timeline_desechable is None:
        return None
    colocado = None
    try:
        indice = timeline_desechable.GetTrackCount("video") or 1
        nuevos = media_pool.AppendToTimeline([{
            "mediaPoolItem": clip, "startFrame": 0, "endFrame": 11,
            "trackIndex": indice, "mediaType": 1,
            "recordFrame": timeline_desechable.GetStartFrame() + 1,
        }])
        if not nuevos or not nuevos[0]:
            return None
        colocado = nuevos[0]
        return get_text_plus_tool(colocado) is not None
    except Exception:
        return None
    finally:
        try:
            if colocado:
                timeline_desechable.DeleteClips([colocado])
        except Exception:
            pass    # el timeline entero se borra despues de todos modos


# Como se marca el timeline importado que ya cumplio su proposito. Se borra
# en la corrida siguiente (ver _limpiar_temporales y el comentario de
# preparar_pack_drt): borrarlo en caliente cerraba Resolve.
MARCA_TIMELINE_TEMPORAL = "RCS · temporal (se limpia solo)"


def _limpiar_temporales(project, media_pool):
    """Borra los timelines temporales que dejaron corridas anteriores.

    Se llama al ARRANCAR, no al terminar: aqui ninguno de ellos es el
    timeline actual del usuario, que es justo lo que hacia peligroso
    borrarlos antes.
    """
    try:
        actual = project.GetCurrentTimeline()
        nombre_actual = actual.GetName() if actual else None
    except Exception:
        nombre_actual = None
    sobras = []
    try:
        for i in range(1, int(project.GetTimelineCount() or 0) + 1):
            tl = project.GetTimelineByIndex(i)
            if tl is None:
                continue
            nombre = tl.GetName() or ""
            if nombre.startswith(MARCA_TIMELINE_TEMPORAL) and nombre != nombre_actual:
                sobras.append(tl)
    except Exception:
        return 0
    if not sobras:
        return 0
    try:
        media_pool.DeleteTimelines(sobras)
    except Exception:
        return 0
    return len(sobras)


def _clips_de_carpeta(folder):
    """{nombre: clip} de esa carpeta. {} si no se puede leer.

    Por NOMBRE, no por id(): cada GetClipList() devuelve wrappers NUEVOS de
    la API, asi que el id() del mismo clip cambia entre dos llamadas y una
    foto indexada por id() no coincide jamas. Con eso la foto _bin_antes de
    la v1.0.34 era un no-op (el gate seguia vaciando el bin entero, con los
    sets buenos de corridas anteriores dentro — el "solo importa el sfx" de
    Studio) y la foto de la raiz creia que TODOS los clips eran nuevos, asi
    que un 'principal' suelto del usuario se movia al bin. El gemelo Lua ya
    indexaba por nombre; ahora los dos comparan lo mismo.
    """
    fotos = {}
    try:
        for c in (folder.GetClipList() or []):
            try:
                fotos[c.GetName()] = c
            except Exception:
                continue
    except Exception:
        return {}
    return fotos


def foto_del_pool(media_pool):
    """{nombre: cuantos} de TODO el Media Pool, recursivo.

    Por nombre, no por id(): cada GetClipList() devuelve wrappers NUEVOS.
    Y se CUENTA -no true/false-: con un booleano, importar un segundo
    'principal' teniendo ya uno en el pool pasaba por "no hay nada nuevo".
    """
    mapa = {}
    try:
        raiz = media_pool.GetRootFolder()
    except Exception:
        return mapa

    def recorrer(folder):
        try:
            for clip in (folder.GetClipList() or []):
                try:
                    nombre = clip.GetName()
                except Exception:
                    continue
                mapa[nombre] = mapa.get(nombre, 0) + 1
        except Exception:
            pass
        try:
            for sub in (folder.GetSubFolderList() or []):
                recorrer(sub)
        except Exception:
            pass

    recorrer(raiz)
    return mapa


def _nuevos_del_pool(media_pool, antes):
    """Los clips que aparecieron en el pool desde la foto, miren donde miren.

    Se recorre el pool ENTERO, el bin del pack incluido: la foto tambien lo
    conto, y las dos mitades tienen que mirar el mismo universo. Excluyendo
    el bin del recorrido pero no de la foto, un 'contexto' que quedara dentro
    de una corrida a medias tapaba a un 'contexto' NUEVO de fuera (antes=1,
    vistos=1, y 1 > 1 es falso). Contar por nombre ya impide re-mover lo que
    esta dentro: no cuenta como nuevo.
    """
    vistos, nuevos = {}, []
    try:
        raiz = media_pool.GetRootFolder()
    except Exception:
        return nuevos

    def recorrer(folder):
        try:
            for clip in (folder.GetClipList() or []):
                try:
                    nombre = clip.GetName()
                except Exception:
                    continue
                vistos[nombre] = vistos.get(nombre, 0) + 1
                if vistos[nombre] > antes.get(nombre, 0):
                    nuevos.append((clip, nombre))
        except Exception:
            pass
        try:
            for sub in (folder.GetSubFolderList() or []):
                recorrer(sub)
        except Exception:
            pass

    recorrer(raiz)
    return nuevos


def _es_generador(tipo):
    """¿El 'Type' de ese clip lo delata como generador/Text+?

    OJO: GetClipProperty('Type') esta LOCALIZADO. En un Resolve en español
    dice «Generador»/«Título…» y con solo las palabras inglesas el lienzo
    arrastrado era invisible (caso real, 02-09).
    """
    tipo = str(tipo or "").lower()
    return any(p in tipo for p in ("generator", "fusion title", "title",
                                   "texto", "text",
                                   "generador", "titulo", "título"))


def _recoger_importados(media_pool, antes, carpeta_destino,
                        orden_importado=None):
    """Mueve al bin los clips que dejo la IMPORTACION del .drt.

    Devuelve cuantos entraron. 'antes' es la foto del POOL ENTERO de antes
    de importar, y los nuevos se recogen MIREN DONDE MIREN: hasta la
    v1.0.38 se miraban solo la raiz y la carpeta donde estaba el usuario,
    asi que un Resolve que dejara los clips en un bin propio los perdia en
    silencio y mandaba al paso manual con los clips ya delante.

    'orden_importado' son los nombres de rol EN EL ORDEN de las pistas del
    timeline: sirve para cuando Resolve materializa los generadores sin el
    nombre del rol ('Text+'). Entonces se renombran por ese orden, y SOLO
    si la cuenta cuadra exactamente — renombrar a ojo pintaria un rol con
    el diseño de otro.

    Esto existe por Free: alli GetMediaPoolItem() no promueve, pero Resolve
    deja los clips del timeline importado sueltos igualmente.
    """
    nuevos, sin_rol = [], []
    for clip, nombre in _nuevos_del_pool(media_pool, antes):
        try:
            rol, numero = parsear_nombre_pack(nombre)
        except Exception:
            rol, numero = None, 0
        if rol is not None and numero != -1:
            nuevos.append(clip)
            continue
        try:
            if _es_generador(clip.GetClipProperty("Type")):
                sin_rol.append(clip)
        except Exception:
            continue

    if (not nuevos and sin_rol and orden_importado
            and len(sin_rol) == len(orden_importado)):
        print(f"  Peldaño 'importados': aparecieron {len(sin_rol)} "
              "generadores sin nombre de rol; les pongo el del timeline "
              "por orden.")
        for clip, nombre in zip(sin_rol, orden_importado):
            if _renombrar_clip(clip, nombre):
                nuevos.append(clip)

    if not nuevos:
        return 0
    try:
        media_pool.MoveClips(nuevos, carpeta_destino)
    except Exception:
        return 0
    # Se comprueba mirando el bin, no fiandose de que MoveClips devolviera
    # algo: es la regla de siempre en esta escalera.
    try:
        dentro = {c.GetName() for c in (carpeta_destino.GetClipList() or [])}
    except Exception:
        return 0
    entraron = 0
    for clip in nuevos:
        try:
            if clip.GetName() in dentro:
                entraron += 1
        except Exception:
            continue
    return entraron


def _promover_a_media_pool(media_pool, timeline_importado, items_por_nombre,
                           carpeta_destino):
    """MUEVE al bin del pack los clips del timeline importado.

    Devuelve (cuantos_entraron, metodo). Un solo mecanismo:

      'media_item'   item.GetMediaPoolItem() + MediaPool.MoveClips(). Mueve
                     el clip tal cual, sin envolverlo en nada. Ojo: si dos
                     roles devuelven el MISMO item, es el generador
                     compartido sin estilar, y usarlo pintaria 'contexto'
                     igual que 'principal' — por eso se comprueba.

    'fusion_clip' (Timeline:CreateFusionClip) se quito en la v1.0.28: PRE
    COMPONE, y un clip precompuesto no tiene el TextPlus en el nivel superior,
    asi que al generar sale sin texto. Quitarlo de esta lista ademas
    NEUTRALIZA la cache de quien ya lo tenia grabado en capacidades.json: el
    guardia 'if probado in orden' deja de reconocerlo y lo ignora solo.

    Si no deja nada, devuelve (0, None): el llamador tiene que dejar el
    timeline importado y decir que arrastrar a mano, no fallar en silencio.
    """
    orden = ["media_item"]
    probado = _leer_capacidades().get("pasar_a_media_pool")
    if probado in orden:
        orden.remove(probado)
        orden.insert(0, probado)     # el que funciono la ultima vez, primero

    for metodo in orden:
        # Se prueba con UNO antes de gastar 30 llamadas en una via que no
        # funciona en este Resolve.
        primer_nombre, primer_item = next(iter(items_por_nombre.items()))
        if not _promover_uno(metodo, media_pool, timeline_importado,
                             primer_item, primer_nombre, carpeta_destino):
            continue

        entraron, vistos = 1, {primer_nombre}
        for nombre, item in items_por_nombre.items():
            if nombre in vistos:
                continue
            if _promover_uno(metodo, media_pool, timeline_importado, item,
                             nombre, carpeta_destino):
                entraron += 1
            vistos.add(nombre)

        # Todos apuntando al mismo item = generador compartido sin estilar.
        try:
            distintos = {c.GetName() for c in carpeta_destino.GetClipList()}
        except Exception:
            distintos = set()
        if len(distintos) < 2 and len(items_por_nombre) > 1:
            continue
        _recordar_capacidad("pasar_a_media_pool", metodo)
        return entraron, metodo
    if probado:
        # La memoria mintio: el metodo que funciono la ultima vez ya no
        # funciona (la API es caprichosa entre corridas). Se olvida para
        # que capacidades.json no documente una capacidad que hoy no existe.
        _recordar_capacidad("pasar_a_media_pool", None)
        print(f"  El método recordado '{probado}' ya no funciona: "
              "lo olvido para reprobar en limpio.")
    return 0, None


def slug_pack(nombre):
    """El slug ASCII gemelo del pack (identico byte a byte al del Lua).

    Trabaja sobre los BYTES UTF-8 como hace el Lua: cada byte no-ascii se
    vuelve '_' (una tilde son dos), minusculas, tope 40, mas el checksum
    de los bytes originales para separar packs que solo difieren en
    acentos. Un test compara las tres copias (este, CineCaptions_Subtitulos y
    CineCaptions_Exportar_PackDRB).
    """
    datos = str(nombre or "").encode("utf-8")
    suma = sum(datos) % 100000
    letras = []
    for b in datos:
        c = chr(b).lower()
        letras.append(c if c in "abcdefghijklmnopqrstuvwxyz0123456789"
                      else "_")
    limpio = "".join(letras)[:40] or "pack"
    return f"{limpio}-{suma}"


def _tam_de_archivo(ruta):
    try:
        return Path(ruta).stat().st_size
    except OSError:
        return 0


def _ruta_respaldo_drb(nombre_pack, formato, ruta_drt):
    # El tamaño del .drt viaja en el NOMBRE (mismo patron que
    # plantillas_cache): sin esto un pack actualizado EN SITIO perdia
    # contra el respaldo rancio para siempre, en silencio.
    return SHARED_FOLDER / (
        f"respaldo_bin_{slug_pack(nombre_pack)}_{formato}"
        f"_{_tam_de_archivo(ruta_drt)}.drb")


# Tabla de plegado de tildes: las MISMAS secuencias que el gemelo Lua
# reemplaza byte a byte. NUNCA unicodedata aqui: produciria plegados que
# el Lua no hace y los dos dejarian de dar el mismo nombre (comparar lo
# mismo con lo mismo, la leccion de Tk/Fusion).
_PLEGADO = (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
            ("ñ", "n"), ("ü", "u"), ("Á", "a"), ("É", "e"), ("Í", "i"),
            ("Ó", "o"), ("Ú", "u"), ("Ñ", "n"), ("Ü", "u"))

NOMBRE_FORMATO = {"h": "horizontal", "v": "vertical", "c": "cuadrado"}


def nombre_legible(nombre):
    """'Base títulos dinámicos' -> 'base-titulos-dinamicos' (v1.0.55).

    El usuario tecleo el slug con checksum en el dialogo de exportar de
    Resolve y pidio nombres simples. Las tildes se PLIEGAN (á->a) en vez
    de aplastarse a '_' y no hay checksum: dos packs que solo difieran
    en tildes colisionan — compromiso aceptado a cambio de un nombre que
    una persona puede escribir. Sigue siendo ASCII puro (el io.open del
    Lua en Windows no abre rutas UTF-8) y el nombre viejo con checksum
    se sigue leyendo como fuente 4. Copias identicas en los dos gemelos
    y en CineCaptions_Exportar_PackDRB; un test compara las tres.
    """
    texto = str(nombre or "")
    for con, sin in _PLEGADO:
        texto = texto.replace(con, sin)
    letras = []
    for c in texto.lower():
        letras.append(c if c in "abcdefghijklmnopqrstuvwxyz0123456789"
                      else "-")
    limpio = "".join(letras)
    while "--" in limpio:
        limpio = limpio.replace("--", "-")
    limpio = limpio.strip("-")[:40].rstrip("-")
    return limpio or "pack"


def _ruta_respaldo_manual(nombre_pack, formato):
    # El nombre que se le pide TECLEAR al usuario en la GUI: legible,
    # sin checksum y con el formato en palabra completa.
    palabra = NOMBRE_FORMATO.get(formato, str(formato))
    return SHARED_FOLDER / (
        f"respaldo_{nombre_legible(nombre_pack)}_{palabra}.drb")


def _hay_set_completo(sets):
    # Al menos un set con LOS TRES roles: un respaldo (o un .drb
    # importado) con sets incompletos se clavaria a nivel maquina y
    # bloquearia a la escalera de completarlo.
    for s in sets or []:
        try:
            if s.get("context") and s.get("main") and s.get("complement"):
                return True
        except AttributeError:
            pass
    return False


def respaldar_bin_drb(media_pool, carpeta_bin, nombre_pack, formato,
                      ruta_drt):
    """Exporta el bin SANO a un .drb en la carpeta compartida (v1.0.47).

    Con ese archivo, el peldaño 'drb' de las corridas siguientes importa
    el bin ENTERO directo al Media Pool -posicion y animacion incluidas-
    sin promover nada: el arrastre manual pasa de "una vez por proyecto" a
    "una vez por maquina y formato". Idempotente y JAMAS tumba la
    generacion. Se verifica el archivo escrito con tamaño > 0 (que la
    llamada no reviente no prueba nada: la leccion del fundido).
    """
    try:
        destino = _ruta_respaldo_drb(nombre_pack, formato, ruta_drt)

        def _tam():
            return _tam_de_archivo(destino)

        if _tam() > 0:
            return
        try:
            sets_bin, _ = buscar_sets_de_plantillas(media_pool, carpeta_bin)
        except Exception:
            sets_bin = []
        if not _hay_set_completo(sets_bin):
            # Un bin a medias no merece clavarse como respaldo de maquina.
            return
        try:
            media_pool.ExportFolder(carpeta_bin, str(destino))
        except Exception:
            pass
        if _tam() == 0:
            try:
                carpeta_bin.Export(str(destino))
            except Exception:
                pass
        if _tam() > 0:
            print("  Respaldé el bin del pack en un .drb: las próximas "
                  "corridas lo importan solas, aunque el bin se vacíe "
                  "(Ctrl+Z) o cambies de proyecto.")
        else:
            # Un cadaver de 0 bytes bloquearia el reintento y el peldaño.
            try:
                destino.unlink(missing_ok=True)
            except OSError:
                pass
            # La sonda del 03-09 (Resolve 21.0.4.5, Studio Y Free) midio
            # que ExportFolder ya NI EXISTE en la API. La salida real es
            # la GUI, y hay que decir el NOMBRE EXACTO: el legible de la
            # fuente 3 (v1.0.55) — el usuario valido este flujo en su Mac el
            # mismo dia y pidio un nombre que se pueda teclear.
            ruta_manual = _ruta_respaldo_manual(nombre_pack, formato)
            print("  Tu Resolve no exporta bandejas por script. Para dejar "
                  "el automático permanente hazlo tú UNA vez: clic derecho "
                  f"sobre el bin «RCS · {nombre_pack} · {formato}» en el "
                  "Media Pool → Exportar bandeja… → guarda EXACTO como:")
            print(f"    {ruta_manual}")
            print("  Desde ahí, cada corrida (y cada proyecto nuevo) lo "
                  "importa sola.")
    except Exception:
        pass


def preparar_pack_drt(project, media_pool, nombre_pack, formato, ruta_drt,
                      ruta_drb=None):
    """Envoltura del prep: si el bin quedo SANO (promocion, rescate o
    arrastre previo del usuario), se respalda a .drb antes de devolverlo.
    El respaldo va en su propio try: jamas puede tumbar el prep."""
    carpeta, aviso = _preparar_pack_drt_nucleo(
        project, media_pool, nombre_pack, formato, ruta_drt, ruta_drb)
    if carpeta is not None and ruta_drt:
        # Sin .drt no se respalda (v1.0.57): la estampa de frescura usa el
        # tamaño del .drt, y un pack solo-bin ya viaja con su .drb en el
        # manifiesto — el respaldo seria redundante.
        try:
            respaldar_bin_drb(media_pool, carpeta, nombre_pack, formato,
                              ruta_drt)
        except Exception:
            pass
    return carpeta, aviso


def _preparar_pack_drt_nucleo(project, media_pool, nombre_pack, formato,
                              ruta_drt, ruta_drb=None):
    """Importa un .drt y deja sus clips listos en un bin del Media Pool.

    Devuelve (carpeta_bin, aviso). 'carpeta_bin' es None si no se pudo
    preparar -en ese caso el aviso dice exactamente que hacer a mano, nunca
    se degrada en silencio al diseño automatico sin decirlo-.
    """
    nombre_bin = _nombre_bin_pack(nombre_pack, formato)
    existente = _subcarpeta(media_pool.GetRootFolder(), nombre_bin)
    if existente is not None:
        # Se pregunta LO MISMO que preguntara la generacion, no una
        # heuristica de "parece que hay clips": si el bin de una corrida
        # anterior quedo a medias, hay que rehacerlo, no darlo por bueno.
        ya_listos, _ = buscar_sets_de_plantillas(media_pool, existente)
        if ya_listos:
            return existente, None  # ya se preparo en una corrida anterior

    # Un pack SOLO-bin llega con ruta_drt vacia (v1.0.57): valido — el
    # peldaño drb de abajo hace todo el trabajo. Lo que sigue siendo error
    # es apuntar a un .drt que no existe, o no traer nada de nada.
    if ruta_drt and not Path(ruta_drt).is_file():
        return None, (f"el pack '{nombre_pack}' apunta a "
                      f"'{ruta_drt}', que no encuentro en este equipo.")
    if not ruta_drt and not (ruta_drb and Path(ruta_drb).is_file()):
        return None, (f"el pack '{nombre_pack}' no trae ni timeline ni bin "
                      "que yo encuentre en este equipo.")

    # Peldaño 'drb': el bin exportado, si el pack lo trae. Lo importa
    # DIRECTO al Media Pool (ImportFolderFromFile), sin depender de que
    # Resolve promueva nada — es el "arrastrar a mano", hecho por API, y
    # funciona igual en Free y en Studio. Importa en el bin del pack (el
    # current manda donde cae) y se verifica con la MISMA pregunta que hara
    # la generacion. Si no esta el archivo o la llamada no existe, la
    # escalera de siempre sigue intacta.
    # CUATRO fuentes identificadas para el peldaño drb, en orden: el
    # manifiesto (el .drb embebido junto al .drt — desde la v1.0.55 el
    # pack incorporado lo trae), el respaldo automatico con estampa, el
    # respaldo manual LEGIBLE (v1.0.55: el nombre que imprimen los
    # carteles y escribe la herramienta), y el nombre viejo con slug y
    # checksum — que se SIGUE leyendo: es el archivo que el usuario ya
    # fabrico en su Mac, y un nombre nuevo degrada a «funciona como
    # antes», nunca rompe lo que funcionaba. El pack_<f>.drb generico NO
    # se lee (sin identidad de pack pintaria el diseño de otro pack sin
    # aviso). Los sin-estampa se aceptan sin frescura: exportar a mano o
    # correr la herramienta es un acto deliberado del usuario.
    fuente_drb = "el manifiesto"
    if not (ruta_drb and Path(ruta_drb).is_file()):
        ruta_drb = None
        _candidatas = []
        if ruta_drt:
            # La estampa lleva el tamaño del .drt: sin .drt no existe.
            _candidatas.append(
                (_ruta_respaldo_drb(nombre_pack, formato, ruta_drt),
                 "el respaldo de esta maquina"))
        _candidatas.append((_ruta_respaldo_manual(nombre_pack, formato),
                            "el respaldo manual"))
        _candidatas.append(
            (SHARED_FOLDER / (f"respaldo_bin_{slug_pack(nombre_pack)}"
                              f"_{formato}.drb"),
             "el respaldo con el nombre antiguo"))
        for _candidata, _fuente in _candidatas:
            if _candidata.is_file():
                ruta_drb = str(_candidata)
                fuente_drb = _fuente
                break
    if ruta_drb and Path(ruta_drb).is_file():
        try:
            carpeta_bin = existente or media_pool.AddSubFolder(
                media_pool.GetRootFolder(), nombre_bin)
        except Exception:
            carpeta_bin = None
        if carpeta_bin is not None and existente is None:
            # El peldaño CREO el bin: recordarlo. Sin esto, un drb que
            # falla al importar dejaba 'existente' en None y la escalera
            # de abajo llamaba AddSubFolder OTRA VEZ — dos bins
            # «RCS · <pack> · <f>» duplicados en el proyecto. Camino
            # inalcanzable hasta la v1.0.55 (el manifiesto nunca traia
            # drb); lo cazo test_v1039 al embeber los .drb de verdad.
            existente = carpeta_bin
        if carpeta_bin is not None:
            try:
                previa_drb = media_pool.GetCurrentFolder()
            except Exception:
                previa_drb = None
            try:
                media_pool.SetCurrentFolder(carpeta_bin)
            except Exception:
                pass
            importo = False
            try:
                importo = bool(media_pool.ImportFolderFromFile(str(ruta_drb)))
            except Exception as exc:
                print(f"  Peldaño 'drb': ImportFolderFromFile no está en "
                      f"este Resolve ({exc}).")
            try:
                if previa_drb is not None:
                    media_pool.SetCurrentFolder(previa_drb)
            except Exception:
                pass
            if importo:
                sets_drb, _ = buscar_sets_de_plantillas(media_pool,
                                                        carpeta_bin)
                if _hay_set_completo(sets_drb):
                    print(f"  Peldaño 'drb': el bin del pack entró DIRECTO "
                          f"al Media Pool ({len(sets_drb)} sets, desde "
                          f"{fuente_drb}), sin promover nada.")
                    return carpeta_bin, None
                _sigo = "; sigo con el .drt." if ruta_drt else "."
                print("  Peldaño 'drb': importó pero no encontré sets "
                      f"adentro{_sigo}")
            else:
                _sigo = "; sigo con el .drt." if ruta_drt else "."
                print(f"  Peldaño 'drb': no funcionó en este Resolve{_sigo}")

    if not ruta_drt:
        # Pack SOLO-bin (v1.0.57): sin .drt no hay escalera ni paso manual
        # posible (no existe timeline que arrastrar). Si el bin no entro,
        # la verdad y a seguir: generacion sin pack, nunca cero lineas ni
        # un cartel pidiendo un arrastre imposible.
        return None, (f"no pude meter el bin del pack '{nombre_pack}' en "
                      "el Media Pool y este pack no trae timeline de "
                      "respaldo. Genero sin él, con lo que haya.")

    timeline_previo = project.GetCurrentTimeline()
    # El bin donde el usuario estaba parado. HAY QUE RESTAURARLO: mas abajo
    # se hace SetCurrentFolder(carpeta_bin) y, sin devolverlo, la siguiente
    # ImportMedia (los efectos de sonido) aterriza dentro del bin del pack.
    # Ahi los pillaba el vaciado de "el bin quedo a medias" y los borraba:
    # ese era el reporte de "importa los SFX y despues se ponen en rojo".
    try:
        carpeta_previa = media_pool.GetCurrentFolder()
    except Exception:
        carpeta_previa = None
    # Una lista de un elemento en vez de una variable suelta: 'finally' tiene
    # que poder leerla incluso si el 'try' revento antes de la unica linea
    # que la pondria en True, y una lista mutable evita el UnboundLocalError
    # que daria reasignar la misma variable desde dos alcances.
    _BORRAR_IMPORTADO = [False]
    # La importacion deja los clips sueltos en el CURRENT FOLDER, y la foto
    # con la que se detectan se tomaba de la raiz: con el current apuntando a
    # cualquier otro bin (el del pack de la corrida anterior, una bandeja del
    # usuario), la foto no veia los clips nuevos y el peldaño 0 fallaba en
    # silencio. Se fija la RAIZ como current antes de importar -asi caen
    # siempre en el mismo sitio- y ademas se fotografia TAMBIEN la carpeta
    # donde estaba el usuario, por si algun Resolve los deja alli igual.
    try:
        media_pool.SetCurrentFolder(media_pool.GetRootFolder())
    except Exception:
        pass
    # Un manual viejo de ESTE pack+formato (de un gate fallido anterior)
    # se marca como temporal ANTES de importar el nuevo: cada corrida
    # fallida acumulaba otra pestaña «(arrastrar a mano)» en el proyecto.
    # Renombrar, no borrar (DeleteTimelines en caliente cerro Resolve una
    # vez): la limpieza de la corrida siguiente se lo lleva cuando no es
    # el current de nadie. Y si es el timeline ACTUAL, se deja en paz.
    try:
        objetivo = f"RCS · {nombre_pack} · {formato} (arrastrar a mano)"
        try:
            actual = project.GetCurrentTimeline().GetName()
        except Exception:
            actual = None
        for i in range(1, int(project.GetTimelineCount() or 0) + 1):
            try:
                tl = project.GetTimelineByIndex(i)
                nombre_tl = tl.GetName()
            except Exception:
                continue
            if nombre_tl == objetivo and nombre_tl != actual:
                try:
                    tl.SetName(MARCA_TIMELINE_TEMPORAL)
                except Exception:
                    pass
    except Exception:
        pass

    # Foto del POOL ENTERO (recursiva). Mirar solo la raiz y la carpeta del
    # usuario perdia los clips cuando Resolve los dejaba en un bin propio.
    try:
        _antes_pool = foto_del_pool(media_pool)
    except Exception:
        _antes_pool = {}
    # Con opciones explicitas primero (importSourceClips ya es el defecto
    # documentado, pero pasarlo elimina la duda para siempre); si esta firma
    # no existe en algun Resolve viejo, se reintenta a secas.
    importado, error_import = None, None
    try:
        importado = media_pool.ImportTimelineFromFile(
            str(ruta_drt), {"importSourceClips": True})
    except Exception:
        importado = None
    if not importado:
        try:
            importado = media_pool.ImportTimelineFromFile(str(ruta_drt))
        except Exception as exc:
            error_import = str(exc)
    if not importado:
        # Ya se fijo la raiz como current para importar: restaurar el bin
        # del usuario tambien en este retorno temprano, que ocurre ANTES del
        # try/finally que restaura en los demas caminos. Sin esto, los
        # ImportMedia siguientes (los SFX) aterrizaban en la raiz.
        try:
            if carpeta_previa is not None:
                media_pool.SetCurrentFolder(carpeta_previa)
        except Exception:
            pass
        detalle = f" ({error_import})" if error_import else ""
        return None, (f"no pude importar el pack '{nombre_pack}' "
                      f"({Path(ruta_drt).name}){detalle}.")

    try:
        try:
            project.SetCurrentTimeline(importado)
        except Exception:
            pass

        # Recolectar los items por rol/numero, mirando TODAS las pistas de
        # video -igual que hace el importador de estilos-.
        items_por_nombre = {}
        # Los nombres EN EL ORDEN en que estan en el timeline: es lo unico
        # que permite repartir roles si Resolve materializa los clips sin su
        # nombre. Se arma aqui, donde todavia se tiene el timeline delante.
        orden_importado = []
        try:
            n_pistas = importado.GetTrackCount("video")
        except Exception:
            n_pistas = 0
        for pista in range(1, (n_pistas or 0) + 1):
            for item in (importado.GetItemListInTrack("video", pista) or []):
                try:
                    nombre = item.GetName()
                except Exception:
                    continue
                rol, n = parsear_nombre_pack(nombre)
                if rol is not None and n != -1 and nombre not in items_por_nombre:
                    items_por_nombre[nombre] = item
                    orden_importado.append(nombre)

        if not items_por_nombre:
            # No hay nada que rescatar a mano tampoco: se borra igual, o
            # quedaria un timeline vacio de sobra por cada intento fallido.
            _BORRAR_IMPORTADO[0] = True
            return None, (f"el pack '{nombre_pack}' no trae ningun clip "
                          "llamado 'contexto', 'principal' o 'complemento' "
                          "en ese timeline.")

        carpeta_bin = existente or media_pool.AddSubFolder(
            media_pool.GetRootFolder(), nombre_bin)
        if carpeta_bin is None:
            return None, (f"no pude crear el bin '{nombre_bin}' en el "
                          "Media Pool.")
        try:
            media_pool.SetCurrentFolder(carpeta_bin)
        except Exception:
            pass

        # Foto del bin ANTES de meterle nada: si el gate de mas abajo
        # rechaza esta corrida, SOLO se borra lo que esta corrida metio.
        # Hasta la v1.0.33 el vaciado borraba todos los clips de rol del
        # bin — incluidos los de corridas anteriores que SI funcionaban — y
        # una corrida mala dejaba el proyecto entero sin plantillas ("solo
        # importa el sfx").
        try:
            _bin_antes = set(_clips_de_carpeta(carpeta_bin))
        except Exception:
            _bin_antes = set()

        # Peldaño 0: lo que la importacion ya dejo suelto (raiz, y la
        # carpeta del usuario por si acaso). Es gratis (solo mover) y es el
        # unico que funciona en Free, donde GetMediaPoolItem no promueve.
        entraron = _recoger_importados(media_pool, _antes_pool, carpeta_bin,
                                       orden_importado)
        metodo = "importados" if entraron else None
        if entraron:
            print(f"  Pack '{nombre_pack}': recogí {entraron} clips que dejó "
                  "la importación y los moví al bin.")
        else:
            print(f"  Peldaño 'importados': la importación no dejó clips "
                  "sueltos nuevos; pruebo GetMediaPoolItem.")
            entraron, metodo = _promover_a_media_pool(
                media_pool, importado, items_por_nombre, carpeta_bin)
            print(f"  Peldaño 'media_item': "
                  + (f"movió {entraron} clips." if metodo
                     else "no funcionó en este Resolve."))

        # ¿Hay sets, por nombre? Necesario, pero NO suficiente.
        sets_utiles, _ = buscar_sets_de_plantillas(media_pool, carpeta_bin)

        # Y la que de verdad decide: ¿uno de esos clips trae un TextPlus de
        # primer nivel? Es lo que preguntara la generacion, y la que faltaba
        # en la v1.0.27 — por eso los clips precompuestos pasaban el filtro
        # de nombres y despues salian las ~200 lineas SIN TEXTO.
        estructura = None
        if sets_utiles:
            # El set lleva tambien la clave 'numero' (un ENTERO, v1.0.62):
            # aqui la salva el orden de insercion del dict, pero el gemelo
            # Lua ya se comio un numero por pairs — filtro explicito en
            # los dos, nunca por suerte.
            muestra = next((c for r, c in sets_utiles[0].items()
                            if r != "numero"), None)
            if muestra is not None:
                estructura = _sirve_para_subtitulos(importado, media_pool,
                                                    muestra)
            if estructura is False:
                print(f"  Aviso: los clips de '{nombre_pack}' llegaron al "
                      "Media Pool, pero no traen un Text+ utilizable "
                      "(¿vienen precompuestos?). No los uso: saldrían sin "
                      "texto.")
            elif estructura is None:
                # No se pudo comprobar. No se bloquea por eso -seria peor-,
                # pero queda dicho para que un screenshot lo explique.
                print(f"  Nota: no pude comprobar la estructura de los clips "
                      f"de '{nombre_pack}'. Sigo, pero si salen sin texto es "
                      "por aquí.")

        # Hacen falta LAS TRES: que la via ganara, que haya sets, y que la
        # estructura no sea explicitamente mala. Con menos no alcanza, y esto
        # costo encontrarlo: cuando GetMediaPoolItem devuelve el generador
        # COMPARTIDO, la via se rechaza -bien- pero ese clip ya se movio al
        # bin como efecto colateral y quedo renombrado a 'contexto'. La
        # busqueda encontraba 1 set y daba el bin por bueno: los tres roles
        # habrian salido con el MISMO diseño.
        if metodo is None or not sets_utiles or estructura is False:
            print(f"  Gate del pack: NO paso (vía={metodo}, "
                  f"sets={len(sets_utiles)}, estructura={estructura}).")
            # Y decir QUE hay en el bin: «sets=0» no distingue «se vacio»
            # de «hay clips pero no parsean», y son arreglos distintos. El
            # caso real (01-09): el bin QUEDO VACIO entre dos corridas del
            # mismo proyecto — Ctrl+Z despues de generar deshace tambien
            # el ARRASTRE del usuario (misma pila de deshacer de Resolve).
            if not sets_utiles:
                try:
                    nombres_bin = []
                    for clip in carpeta_bin.GetClipList() or []:
                        try:
                            nombres_bin.append(clip.GetName())
                        except Exception:
                            pass
                    if not nombres_bin:
                        print("  El bin del pack esta VACIO. Si ya habias "
                              "arrastrado los clips, ojo: Ctrl+Z despues "
                              "de generar tambien deshace TU arrastre. "
                              "Vuelve a arrastrarlos (incluido 'base').")
                    else:
                        muestra = ", ".join(nombres_bin[:5])
                        print(f"  El bin tiene {len(nombres_bin)} clips "
                              "pero ninguno forma un set completo. "
                              f"Primeros: {muestra}")
                except Exception:
                    pass
            # Se limpia SOLO lo que esta corrida metio al bin. Los clips de
            # corridas anteriores se quedan: una corrida mala degrada a
            # "como la corrida pasada", nunca a "sin plantillas" — hasta la
            # v1.0.33 aqui se borraba todo el bin, y un gate fallido dejaba
            # el proyecto entero sin plantillas de un plumazo.
            #
            # Y de lo nuevo, SOLO clips con nombre de rol: si algo ajeno
            # acabo aqui (un .wav de efectos), no se toca. Borrar material
            # del usuario por limpiar un bin es lo que prohibe la regla de
            # nunca destruir su trabajo, y paso hasta la v1.0.32.
            try:
                sobras = []
                for clip in (carpeta_bin.GetClipList() or []):
                    try:
                        nom = clip.GetName()
                    except Exception:
                        continue
                    # Por nombre: id() compararia wrappers distintos de la
                    # API y no protegeria nada (ver _clips_de_carpeta).
                    if nom in _bin_antes:
                        continue
                    try:
                        rol, _n = parsear_nombre_pack(nom)
                    except Exception:
                        rol = None
                    if rol is not None:
                        sobras.append(clip)
                if sobras:
                    media_pool.DeleteClips(sobras)
                    print(f"  Limpié {len(sobras)} clips que esta corrida "
                          "metió al bin; los de corridas anteriores quedan.")
            except Exception:
                pass
            # Si el bin conserva sets de una corrida anterior, se usan: es
            # exactamente lo que la generacion habria hecho la semana
            # pasada, y mejor eso que mandar al paso manual con un bin sano.
            try:
                _sets_previos, _ = buscar_sets_de_plantillas(
                    media_pool, carpeta_bin)
            except Exception:
                _sets_previos = []
            if _sets_previos:
                print(f"  El bin conserva {len(_sets_previos)} sets de una "
                      "corrida anterior: genero con esos.")
                _BORRAR_IMPORTADO[0] = True
                return carpeta_bin, None
            # Ultimo peldaño: no se automatiza mas, pero tampoco se falla en
            # silencio. Se deja el timeline importado -con nombre claro,
            # dentro del proyecto- y se dice el paso manual exacto, que es
            # el mismo flujo de hoy: arrastrar del timeline al Media Pool.
            try:
                importado.SetName(
                    f"RCS · {nombre_pack} · {formato} (arrastrar a mano)")
            except Exception:
                pass
            try:
                nombre_tl = importado.GetName()
            except Exception:
                nombre_tl = nombre_bin
            return None, (
                f"tu versión de Resolve no me deja pasar los clips de "
                f"'{nombre_pack}' al Media Pool automáticamente. Dejé el "
                f"timeline «{nombre_tl}» en tu proyecto: selecciona TODOS sus "
                f"clips de texto (contexto/principal/complemento y el "
                f"clip 'base') y arrástralos al Media Pool, al bin "
                f"«{nombre_bin}», y vuelve a generar.")

        if entraron < len(items_por_nombre):
            # Entro parte. Se sigue -es utilizable- pero se dice cuanto
            # falta: un pack a medias no puede parecer completo.
            print(f"  Aviso: del pack '{nombre_pack}' pasaron {entraron} de "
                  f"{len(items_por_nombre)} clips al Media Pool. Un bloque "
                  "cuyo set no llego entero se omite (no se sustituye).")

        _BORRAR_IMPORTADO[0] = True     # se pudo: ya cumplio su proposito
        print(f"  Pack '{nombre_pack}': {len(sets_utiles)} sets listos en el "
              f"bin «{nombre_bin}» (vía {metodo}).")
        return carpeta_bin, None
    finally:
        # El timeline importado se borra SIEMPRE que se pudo promover. Si NO
        # se pudo (ultimo peldaño), _BORRAR_IMPORTADO sigue en False a
        # proposito: ese timeline es el que el usuario tiene que usar a mano,
        # y borrarlo se llevaria por delante el paso manual que se le acaba
        # de pedir.
        try:
            if timeline_previo:
                project.SetCurrentTimeline(timeline_previo)
        except Exception:
            pass
        try:
            if carpeta_previa is not None:
                media_pool.SetCurrentFolder(carpeta_previa)
        except Exception:
            pass
        if _BORRAR_IMPORTADO[0]:
            # NO se borra en caliente: DeleteTimelines sobre un timeline
            # recien des-seleccionado cerraba Resolve entero (reportado en
            # Studio, v1.0.32). Se marca y se limpia al principio de la
            # corrida siguiente, cuando ya no es el current de nadie —
            # _limpiar_temporales(). Un timeline de sobra un rato es mucho
            # menos malo que perder la sesion del usuario.
            try:
                importado.SetName(MARCA_TIMELINE_TEMPORAL)
            except Exception:
                pass


def orden_de_variantes(cantidad_bloques, cantidad_sets, semilla=20260806):
    """Que set le toca a cada bloque, sin repetir nunca dos seguidos.

    En vez de 1,2,3,4,1,2,3,4... (que se nota como patron), se baraja el
    orden en cada vuelta; ademas se comprueba que el primero de una vuelta
    no sea igual al ultimo de la anterior. Con un solo set no hay nada que
    alternar y se devuelve siempre ese.

    La semilla es fija a proposito: dos corridas seguidas del mismo video
    dan el mismo reparto, asi el resultado es reproducible.
    """
    import random

    if cantidad_sets <= 1:
        return [0] * cantidad_bloques

    rnd = random.Random(semilla)
    orden = []
    ultimo = None
    while len(orden) < cantidad_bloques:
        vuelta = list(range(cantidad_sets))
        rnd.shuffle(vuelta)
        if vuelta[0] == ultimo:
            vuelta[0], vuelta[1] = vuelta[1], vuelta[0]
        orden.extend(vuelta)
        ultimo = vuelta[-1]
    return orden[:cantidad_bloques]


def estilos_con_fuentes(fuentes):
    """Devuelve AUTO_STYLES ajustado con las tipografias que eligio el usuario
    en la ventana. Si no eligio nada, quedan las de por defecto.

    Contexto y principal comparten familia (uno Regular y otro Bold) y el
    complemento usa la segunda familia, que es la que suele ser serif o
    caligrafica.
    """
    import copy
    estilos = copy.deepcopy(AUTO_STYLES)
    if not fuentes:
        return estilos

    principal = fuentes.get("main_family")
    complemento = fuentes.get("complement_family")
    tracking = fuentes.get("tracking")

    if principal:
        estilos["context"]["font"] = principal
        estilos["main"]["font"] = principal
    if complemento:
        estilos["complement"]["font"] = complemento
    if tracking is not None:
        for rol in estilos:
            estilos[rol]["tracking"] = tracking

    interlineado = fuentes.get("line_spacing")
    if interlineado is not None:
        for rol in estilos:
            estilos[rol]["line_spacing"] = interlineado

    return estilos


def estilos_del_preset(base, indice):
    """Mezcla el estilo base con la variante numero 'indice'."""
    import copy
    if not AUTO_PRESETS:
        return base
    variante = AUTO_PRESETS[indice % len(AUTO_PRESETS)]
    resultado = copy.deepcopy(base)
    for rol, cambios in variante.items():
        if rol in resultado:
            resultado[rol].update(cambios)
    return resultado


# ----------------------------------------------------------------------
# Packs de estilos
# ----------------------------------------------------------------------
# El pack viaja YA RESUELTO en el manifiesto: la app leyo estilos.json con
# plantillas.py y mando los sets que hay, en el orden en que rotan, con la
# carpeta donde estan los .setting. El script no lee estilos.json: asi la
# validacion vive en un solo sitio y no hay dos parsers que se separen.
#
# Prioridad, y no cambia: las plantillas del Media Pool del usuario mandan
# sobre el pack, y el pack sobre el diseno automatico.
def pack_del_manifiesto(track_info, ancho=None, alto=None):
    """El pack que pidio la app, ya en el formato que toca. None si no hay.

    Los dos formatos viajan en el manifiesto y se elige AQUI, porque la
    resolucion del timeline solo se conoce dentro de Resolve. Eligiendo en la
    app, un pack completo se aplicaria en horizontal sobre un video vertical
    sin que nadie lo notara.

    La excepcion es 'formato_forzado': si el usuario eligio uno a mano, manda
    sobre la deteccion. Adivinar por la resolucion no siempre acierta -un
    timeline cuadrado no es ni una cosa ni la otra-, y la eleccion explicita
    de una persona gana siempre a nuestra heuristica.
    """
    p = track_info.get("plantilla")
    if not isinstance(p, dict):
        return None
    formatos = p.get("formatos")
    if not isinstance(formatos, dict) or not formatos:
        return None

    ETIQ = {"h": "horizontal", "v": "vertical", "c": "cuadrado"}
    forzado = p.get("formato_forzado")
    if forzado in ("h", "v", "c"):
        quiere = forzado
    else:
        a, b = float(ancho or 0), float(alto or 0)
        if a > 0 and b > 0 and abs(a - b) <= 0.05 * max(a, b):
            quiere = "c"
        else:
            quiere = "v" if b > a else "h"
    usado, aviso = quiere, None
    if quiere not in formatos:
        # Se usa el que haya (el mas parecido antes que el primero de la
        # lista), pero se DICE: los tamaños de letra no se traducen entre
        # formatos y el resultado se va a ver distinto.
        orden = {"c": ("v", "h"), "v": ("c", "h"), "h": ("c", "v")}[quiere]
        usado = next((f for f in orden if f in formatos), list(formatos)[0])
        aviso = (f"el pack no trae versión {ETIQ[quiere]}: uso la "
                 f"{ETIQ[usado]}. Los tamaños de letra no se traducen entre "
                 "formatos, revisa cómo queda.")

    bloque = formatos.get(usado) or {}
    sets = [s for s in (bloque.get("sets") or []) if isinstance(s, dict)]
    base = bloque.get("base") if isinstance(bloque.get("base"), dict) else None
    drt = bloque.get("drt") if isinstance(bloque.get("drt"), str) else None
    drb = bloque.get("drb") if isinstance(bloque.get("drb"), str) else None
    # Un pack SOLO-bin tambien vale (v1.0.57): trae drb sin drt y el
    # peldaño drb lo importa entero.
    if not sets and not base and not drt and not drb:
        return None
    return {
        "drb": drb,
        # la revisión (v5.8) hace que un bin del pack importado ANTES, con otros clips, no se reutilice
        "nombre": (p.get("pack") or "?") + (f" · {p['revision']}" if p.get("revision") else ""),
        "formato": usado,
        "carpeta": bloque.get("carpeta") or "",
        "sets": sets,
        "base": base,
        "aviso": aviso,
        "drt": drt,
        "sets_drt": bloque.get("sets_drt") or [],
        "base_drt": bool(bloque.get("base_drt")),
        # {rol: [numeros de set]} cuya tipografia NO dibuja tildes
        # (v1.0.61). Lo mide la app con los archivos de fuente delante;
        # aqui solo se aplica al elegir set. Vacio = sin veto.
        "sets_sin_acentos": (bloque.get("sets_sin_acentos")
                             if isinstance(bloque.get("sets_sin_acentos"),
                                           dict) else {}),
        # {"rol|numero": ["Arial", estilo]} para los clips cuya tipografia
        # NO esta en el equipo (v2.0.2). Tambien lo mide la app; aqui se
        # escribe Font/Style tras el texto. Vacio = nada que sustituir.
        "fuentes_respaldo": (bloque.get("fuentes_respaldo")
                             if isinstance(bloque.get("fuentes_respaldo"),
                                           dict) else {}),
        # Los .setting de la cache instalada no traen posicion: el que
        # coloca tiene que reponer la altura por rol (ver rama 'cargado').
        "settings_sin_posicion": bool(bloque.get("settings_sin_posicion")),
        # {"rol|numero": [x, y, zoom_x, zoom_y]} (v3.3.0): la posicion de
        # pagina Edicion del diseño, clip por clip, normalizada. La aplica
        # aplicar_transformacion SOLO si Resolve no la aplico al colocar.
        "transformaciones": (bloque.get("transformaciones")
                             if isinstance(bloque.get("transformaciones"),
                                           dict) else {}),
    }


def estilos_del_pack(pack, indice, auto):
    """Los tres roles de un set del pack, completos.

    Un set al que le falte un rol lo toma del diseno automatico: si devolviera
    un diccionario incompleto, altura_de_linea se quedaria sin el tamano y el
    bucle de colocacion reventaria con KeyError a mitad del render.
    """
    import copy
    resultado = copy.deepcopy(auto)
    if not pack["sets"]:
        return resultado, None
    entrada = pack["sets"][indice % len(pack["sets"])]
    for rol in ("context", "main", "complement"):
        if isinstance(entrada.get(rol), dict):
            resultado[rol] = dict(entrada[rol])
    return resultado, entrada.get("n")


def ruta_de_setting(pack, n, rol):
    """Donde vive el nodo entero de ese rol. Mismo nombre que puso el
    importador; si el archivo no esta, quien llame se queda con los valores."""
    if not pack or not pack.get("carpeta") or n is None:
        return None
    nombre = ("base.setting" if rol == "base"
              else "%02d-%s.setting" % (int(n), rol))
    return str(Path(pack["carpeta"]) / nombre)


# EL FUNDIDO
#
# Hasta la v1.0.24 esto era 'SetInput("Blend", v, fotograma)' a secas, y
# devolvia True con que la llamada no lanzara. La prueba
# herramientas/CineCaptions_Prueba_Animaciones demostro que esa llamada NO crea ningun
# fotograma clave: en Fusion un input es un VALOR FIJO hasta que se le conecta
# una curva, y pasarle un fotograma no la crea. La llamada no falla —no hace
# nada—, asi que el contador "con fundido: N" del informe llevaba versiones
# contando fundidos que nunca existieron.
#
# Y habia una mina debajo: si SetInput ignora el fotograma, la SEGUNDA llamada
# deja el input en 0.0 como valor fijo, o sea el subtitulo INVISIBLE.
#
# Ademas 'Blend' NO EXISTE en un Text+. El volcado de las 310 entradas reales
# (CineCaptions_Prueba_Animaciones) lo confirmo: la opacidad del texto es 'Alpha1'. O
# sea que el fundido llevaba versiones escribiendo en un sitio inexistente —
# de ahi que la mina de arriba no reventara nunca.
#
# Y de las tres formas de animar, solo UNA funciona en Resolve 21:
# comp:BezierSpline() + tool.X = curva + curva:SetKeyFrames{...}. Va primera
# para no gastar dos intentos fallidos en el primer clip; las otras se dejan
# detras por si otra version se comporta distinto.
#
# Se COMPRUEBA que el valor cambie de verdad entre los dos fotogramas, y si no
# cambia se devuelve el input a su valor original y se dice que no hubo
# fundido.
#
# Tiene que dar lo mismo que aplicar_fade() del .lua: hay un test que compara
# los dos con lupa.

# Donde escribir la opacidad, en orden de preferencia. 'Blend' queda detras
# como respaldo: no esta en un Text+, pero si en otros nodos de Fusion.
_FADE_ENTRADAS = ("Alpha1", "Blend")

_FADE_VIA = None      # None sin averiguar, False imposible, o el indice
_FADE_ENTRADA = None  # cual de _FADE_ENTRADAS resulto existir
_FADE_MOTIVO = None


def _fade_anima(tool, entrada, desde, fin):
    """La UNICA definicion util de 'se animo': que el valor cambie."""
    try:
        a = tool.GetInput(entrada, desde)
        b = tool.GetInput(entrada, fin)
    except Exception:
        return False
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    return abs(b - a) > 0.01


def _fade_por_curva(comp, tool, entrada, claves):
    # La unica que funciona en Resolve 21, medida por CineCaptions_Prueba_Animaciones.
    # 'claves' es {fotograma: [valor]}: TODOS los fotogramas del clip (la
    # entrada y la salida juntas) van en la MISMA curva — asignar una curva
    # nueva al input desconecta la anterior, asi que dos llamadas separadas
    # no suman: la segunda borra la primera (v1.0.51).
    curva = comp.BezierSpline({})
    if curva is None:
        raise RuntimeError("sin BezierSpline")
    setattr(tool, entrada, curva)
    curva.SetKeyFrames(claves)


def _fade_por_curva_indice(comp, tool, entrada, claves):
    curva = comp.BezierSpline({})
    if curva is None:
        raise RuntimeError("sin BezierSpline")
    setattr(tool, entrada, curva)
    for f, v in claves.items():
        curva[f] = v[0]


def _fade_por_indice(comp, tool, entrada, claves):
    for f, v in claves.items():
        getattr(tool, entrada)[f] = v[0]


def _fade_por_setinput(comp, tool, entrada, claves):
    # La de siempre. Va la ultima porque esta demostrado que no anima, pero si
    # una version futura la hiciera funcionar, funcionaria sin tocar nada.
    for f, v in claves.items():
        tool.SetInput(entrada, v[0], f)


_FADE_FORMAS = (
    ("BezierSpline + SetKeyFrames", _fade_por_curva),
    ("BezierSpline por indice", _fade_por_curva_indice),
    ("tool.<entrada>[fotograma]", _fade_por_indice),
    ("SetInput con fotograma", _fade_por_setinput),
)


def _fade_limpiar(tool, entrada, original):
    """Desconectar la curva y devolver el valor fijo. Sin esto, un intento
    fallido con la ultima forma deja el subtitulo invisible."""
    try:
        setattr(tool, entrada, None)
    except Exception:
        pass
    if original is not None:
        try:
            tool.SetInput(entrada, original)
        except Exception:
            pass


def apply_fades(timeline_item, entrada_frames, salida_frames):
    """Fundido de entrada y/o de salida, en UNA sola curva por input.

    Devuelve (entrada_ok, salida_ok): cada uno True SOLO si se comprobo que
    el valor cambia entre sus dos fotogramas. Los dos extremos viajan
    JUNTOS a proposito: asignar una curva nueva al input desconecta la
    anterior, asi que aplicar la entrada y despues la salida en llamadas
    separadas dejaria solo la ultima (v1.0.51).
    """
    global _FADE_VIA, _FADE_ENTRADA, _FADE_MOTIVO

    entrada_frames = max(0, int(entrada_frames or 0))
    salida_frames = max(0, int(salida_frames or 0))
    if entrada_frames < 1 and salida_frames < 1:
        return False, False
    # Averiguar la via en cada uno de los 200 subtitulos seria tirar el
    # tiempo: la respuesta no cambia dentro de la misma sesion.
    if _FADE_VIA is False:
        return False, False

    comp = timeline_item.GetFusionCompByIndex(1)
    if not comp:
        return False, False

    tool = None
    for _, t in comp.GetToolList().items():
        try:
            if t.ID == "TextPlus":
                tool = t
                break
        except Exception:
            continue
    if tool is None:
        return False, False

    try:
        attrs = comp.GetAttrs() or {}
        fin = attrs.get("COMPN_GlobalEnd")
        ini = attrs.get("COMPN_GlobalStart", 0)
    except Exception:
        return False, False
    if fin is None:
        return False, False

    hasta_entrada = ini + entrada_frames
    if entrada_frames and hasta_entrada >= fin:
        entrada_frames, hasta_entrada = 0, ini
    desde = max(ini, fin - salida_frames)
    if salida_frames and desde >= fin:
        salida_frames = 0
    # Clip demasiado corto para las dos: gana la salida (que el texto se
    # borre limpio importa mas que como aparecio).
    if entrada_frames and salida_frames and hasta_entrada >= desde:
        entrada_frames, hasta_entrada = 0, ini
    if entrada_frames < 1 and salida_frames < 1:
        return False, False

    claves = {}
    if entrada_frames:
        claves[ini] = [0.0]
        claves[hasta_entrada] = [1.0]
    if salida_frames:
        claves[desde] = [1.0]
        claves[fin] = [0.0]

    # Cual de las entradas de opacidad existe en ESTE nodo.
    entrada, original = _FADE_ENTRADA, None
    if entrada is not None:
        try:
            original = tool.GetInput(entrada)
        except Exception:
            original = None
    else:
        for candidata in _FADE_ENTRADAS:
            try:
                valor = tool.GetInput(candidata)
            except Exception:
                valor = None
            if valor is not None:
                entrada, original = candidata, valor
                break
    if entrada is None or original is None:
        # No es que la llamada falle: es que en este nodo no hay donde
        # escribir. Distinguirlo importa, porque son arreglos distintos.
        _FADE_VIA = False
        _FADE_MOTIVO = ("este Text+ no tiene ninguna entrada de opacidad ("
                        + ", ".join(_FADE_ENTRADAS) + ")")
        return False, False
    _FADE_ENTRADA = entrada

    def intentar(i):
        global _FADE_VIA, _FADE_MOTIVO
        nombre, hacer = _FADE_FORMAS[i]
        try:
            hacer(comp, tool, entrada, claves)
        except Exception:
            pass
        # Se comprueba CADA tramo pedido, no uno solo: una via que animara
        # la salida pero no la entrada mentiria en el resumen.
        e_ok = (not entrada_frames
                or _fade_anima(tool, entrada, ini, hasta_entrada))
        s_ok = (not salida_frames
                or _fade_anima(tool, entrada, desde, fin))
        if e_ok and s_ok:
            _FADE_VIA = i
            _FADE_MOTIVO = f"{nombre} sobre '{entrada}'"
            return bool(entrada_frames), bool(salida_frames)
        _fade_limpiar(tool, entrada, original)
        return None

    if _FADE_VIA is not None:
        resultado = intentar(_FADE_VIA)
        return resultado if resultado else (False, False)
    for i in range(len(_FADE_FORMAS)):
        resultado = intentar(i)
        if resultado:
            return resultado
    _FADE_VIA = False
    _FADE_MOTIVO = "esta version de Resolve no acepta fotogramas clave por script"
    return False, False


def apply_fade_out(timeline_item, fade_frames):
    """(compat) Solo el fundido de salida de siempre. Ver apply_fades."""
    return apply_fades(timeline_item, 0, fade_frames)[1]


# CARGAR UN PACK DE ESTILOS
#
# Un pack guarda cada Text+ ENTERO en un .setting (ver plantillas.py). Cargarlo
# es lo fiel: se lleva degradados, formas y fondos, cosas que no caben en un
# puñado de valores.
#
# La prueba del Paso 0 confirmo que LoadSettings responde en Resolve 21, pero
# es API de FUSION y no de Resolve, y no esta en la documentacion oficial de
# scripting: puede no responder en otra version. Se prueba una vez y se
# recuerda; si no va, el pack se sigue aplicando por sus VALORES (estilos.json),
# que es exactamente para lo que ese archivo existe.
_PACK_CARGA = None      # None sin averiguar, True/False despues
_PACK_MOTIVO = None


def cargar_setting(item, tool, ruta, estilo=None):
    """Aplica el nodo entero de un pack sobre este Text+. True si se pudo.

    Deja el clip utilizable pase lo que pase. El .setting guarda dentro el
    GlobalIn/GlobalOut y el Width/Height del timeline donde se diseñó (en el
    de prueba: 1080x1920 y GlobalOut 149), y si se quedaran puestos el texto
    se cortaría a mitad del clip o saldría con el tamaño de otra resolución.
    """
    global _PACK_CARGA, _PACK_MOTIVO

    if _PACK_CARGA is False or not ruta:
        return False
    try:
        if not Path(ruta).is_file():
            return False
    except (OSError, TypeError):
        return False

    # Solo el PRIMER intento decide si esta versión de Resolve sabe cargar
    # settings. Después, un fallo es de ESE archivo (corrupto, de otra versión
    # de Fusion) y no puede apagar el pack entero.
    primero = _PACK_CARGA is None

    try:
        tool.LoadSettings(str(ruta))
    except Exception as exc:                   # noqa: BLE001
        if primero:
            _PACK_CARGA = False
            _PACK_MOTIVO = f"LoadSettings no respondió ({exc})"
        return False

    # Que la llamada no lance NO basta — es el mismo error que se descubrió en
    # el fundido. Se comprueba que de verdad aplicó algo, comparando con lo que
    # el pack dice que tiene ese set.
    if estilo:
        try:
            fuente = str(tool.GetInput("Font") or "")
            tam = float(tool.GetInput("Size") or 0)
        except Exception:                      # noqa: BLE001
            fuente, tam = "", 0.0
        esperada = str(estilo.get("font") or "")
        esp_tam = float(estilo.get("size") or 0)
        # Se exige que fallen LAS DOS para darlo por no aplicado. Resolve
        # devuelve a veces el nombre de la fuente escrito distinto del que se
        # guardó, y con un solo criterio un pack que sí se cargó quedaría
        # descartado. Que fallen las dos ya no es una diferencia de nombre.
        if esperada and fuente != esperada and abs(tam - esp_tam) > 0.001:
            if primero:
                _PACK_CARGA = False
                _PACK_MOTIVO = ("LoadSettings no dio error pero no aplicó "
                                f"nada (esperaba '{esperada}', quedó "
                                f"'{fuente}')")
            return False

    _PACK_CARGA = True

    # Reponer lo que el .setting trae de su timeline de origen.
    comp = None
    try:
        comp = item.GetFusionCompByIndex(1)
    except Exception:                          # noqa: BLE001
        comp = None
    if comp:
        try:
            attrs = comp.GetAttrs() or {}
            ini = attrs.get("COMPN_GlobalStart", 0)
            fin = attrs.get("COMPN_GlobalEnd")
            if fin is not None:
                tool.SetInput("GlobalIn", ini)
                tool.SetInput("GlobalOut", fin)
        except Exception:                      # noqa: BLE001
            pass
    # A 1 significa "usa el tamaño de ESTE timeline". Si el diseñador lo dejó
    # en 0, el texto saldría dimensionado para la resolución en la que se
    # diseñó, que es justo lo que no queremos al reusar un pack.
    try:
        tool.SetInput("UseFrameFormatSettings", 1)
    except Exception:                          # noqa: BLE001
        pass
    return True


def apply_auto_style(tool, estilo, y):
    """Aplica fuente / tamaño / peso / posicion cuando NO hay plantillas
    propias y el script tiene que decidir el diseño el mismo.

    La altura llega de fuera (ver altura_de_linea): depende de que roles tiene
    el bloque, no solo del rol de esta linea, asi que no puede salir del
    diccionario de estilo.

    Devuelve la lista de cosas que no se pudieron aplicar, para poder
    avisarle al usuario en vez de fallar en silencio.
    """
    fallos = []

    if not set_input_safe(tool, "Size", estilo["size"]):
        fallos.append("tamaño")
    if not set_input_safe(tool, "Font", estilo["font"]):
        fallos.append("fuente")
    if not set_input_safe(tool, "Style", estilo["style"]):
        fallos.append("peso")
    if not set_center_safe(tool, 0.5, y):
        fallos.append("posicion")
    if "tracking" in estilo:
        # OJO: el input NO se llama 'Tracking'.
        #
        # Hasta la v1.0.25 aqui decia "Tracking" y no existe: el volcado de
        # las 310 entradas de un Text+ (CineCaptions_Prueba_Animaciones) lo confirmo.
        # set_input_safe atrapaba la excepcion y devolvia... True, asi que el
        # interletrado de los disenos automaticos NUNCA se aplico y nadie se
        # entero. Se llama 'CharacterSpacing'.
        if not set_input_safe(tool, "CharacterSpacing", estilo["tracking"]):
            fallos.append("interletrado")
    if "line_spacing" in estilo:
        set_input_safe(tool, "LineSpacing", estilo["line_spacing"])

    # Color (0-1). Si la plantilla ya trae color, esto solo lo uniforma.
    for canal, valor in (("Red1", estilo["color"][0]),
                         ("Green1", estilo["color"][1]),
                         ("Blue1", estilo["color"][2])):
        set_input_safe(tool, canal, valor)

    # El contorno (modo Hormozi). Confirmado por la prueba del Paso 0:
    # Enabled2/Red2/Green2/Blue2/Thickness2 responden. Es opcional -la
    # mayoria de los estilos no lo llevan-, asi que solo se toca si el
    # estilo trae la clave.
    contorno = estilo.get("outline")
    if contorno:
        if not set_input_safe(tool, "Enabled2", 1):
            fallos.append("contorno")
        set_input_safe(tool, "Thickness2", contorno.get("thickness", 0.2))
        color_c = contorno.get("color", (0.0, 0.0, 0.0))
        for canal, valor in (("Red2", color_c[0]), ("Green2", color_c[1]),
                             ("Blue2", color_c[2])):
            set_input_safe(tool, canal, valor)

    return fallos


def set_text_on_clip(timeline_item, text):
    """Busca el nodo Text+ dentro del clip y le cambia el texto."""
    comp = timeline_item.GetFusionCompByIndex(1)
    if not comp:
        return False
    tool = None
    for name, t in comp.GetToolList().items():
        try:
            if t.ID == "TextPlus":
                tool = t
                break
        except Exception:
            continue
    if tool is None:
        return False
    try:
        tool.StyledText = text
    except Exception:
        try:
            tool.SetInput("StyledText", text)
        except Exception:
            return False
    return True


def _usa_set(cue):
    """True si el bloque es destacado (2 o 3 lineas) y no una palabra suelta.

    Un bloque 'base' tiene una sola linea con ese rol; cualquier otra cosa es
    un bloque con contexto/principal/complemento. Se usa para repartir las
    variantes de diseño, elegir la separacion y decidir el adelanto, asi que
    tiene que ser LA MISMA definicion en los tres sitios.
    """
    if not cue:
        return False
    return any(l.get("role") != "base" for l in cue.get("lines", []))


def _adelanto_de(track_info):
    """Fotogramas de adelanto que pidio la app, saneados."""
    try:
        n = int(track_info.get("adelanto_frames") or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, n)


# main() no captura los retornos de los colocadores (tienen returns
# tempranos); esta señal dice si ALGO llego al timeline, para que el
# epilogo no diga "Listo" con cero lineas.
_ALGO_COLOCADO = [False]
_TOTAL = [0]          # v5.5: cuántas líneas / palabras / clips se colocaron en total (lo que el resultado le dice a la app: «Listo» sólo si > 0)


def place_guion_track(timeline, media_pool, track_info, base_template,
                      fps, timeline_start_frame, project=None):
    """v5.9 — estilo «guion»: cada PALABRA (o tramo de palabras) es su propio clip, con su estilo, su posición y su momento.

    El archivo de datos trae bloques {start, end, estilo, runs: [{rol, texto, t, fin, x, y, estilo, zoom}]}; el planificador de la app
    (guion_captions.py) ya decidió qué palabras son la principal, cuáles van en fino y cuáles en negrita, dónde cae cada una y cuándo entra:
      rol 'main'       -> el clip «principal» de la variante del bloque (o de la propia palabra, si trae 'estilo')
      rol 'context'    -> el clip «arriba» (línea pequeña FINA)
      rol 'complement' -> el clip «abajo»  (línea pequeña en NEGRITA)
    x, y = centro de la palabra en fracción del cuadro (0-1; y desde ARRIBA). Cada palabra va en la primera pista libre («ES-T1», «ES-T2»…):
    las que están a la vez se apilan en pistas distintas. Reutiliza todo lo demás (pack .drb, sets, texto, Pan/Tilt, SFX) de place_dynamic_track.
    """
    lang = track_info["language"]
    L = str(lang).upper()
    data_path = Path(track_info["data_path"])
    if not data_path.exists():
        print(f"  Aviso: no encuentro {data_path}, salto '{lang}'")
        return
    datos = json.loads(data_path.read_text(encoding="utf-8"))
    cues = datos.get("cues", [])
    if not cues:
        print(f"  Aviso: '{data_path.name}' no tiene bloques.")
        return
    if track_info.get("sfx_library") or track_info.get("sfx_archivos"):
        place_sfx_track(timeline, media_pool, cues, track_info, fps, timeline_start_frame)

    def _res(clave, por_defecto):
        try:
            v = timeline.GetSetting(clave)
            return int(float(v)) if v else por_defecto
        except Exception:
            return por_defecto
    ancho_tl = _res("timelineResolutionWidth", 1080)
    alto_tl = _res("timelineResolutionHeight", 1920)

    # el pack de estilos (la misma preparación que place_dynamic_track)
    carpeta_pack_drt = None
    pack_previo = None
    p_manifiesto = track_info.get("plantilla")
    if isinstance(p_manifiesto, dict):
        print(f"  El manifiesto pide el pack '{p_manifiesto.get('pack')}' (estilo guion).")
    if isinstance(p_manifiesto, dict) and project is not None:
        pack_previo = pack_del_manifiesto(track_info, ancho_tl, alto_tl)
        if pack_previo and (pack_previo.get("drt") or pack_previo.get("drb")):
            try:
                carpeta_pack_drt, aviso_drt = preparar_pack_drt(
                    project, media_pool, pack_previo["nombre"],
                    pack_previo["formato"], pack_previo["drt"],
                    pack_previo.get("drb"))
            except Exception as exc:
                carpeta_pack_drt = None
                aviso_drt = f"fallo preparando el pack ({type(exc).__name__}: {exc})."
            if aviso_drt:
                print(f"  Aviso (pack '{pack_previo['nombre']}'): {aviso_drt}")
    sets, informe_sets = buscar_sets_de_plantillas(media_pool, carpeta_pack_drt)
    if not sets:
        fail(f"el estilo «guion» necesita un pack con sets (principal / arriba / abajo) y no encontré ninguno para '{lang}'. "
             "Elige un pack de estilos (por ejemplo «Referencia»).")
    print(f"\nIdioma '{lang}': {len(cues)} bloques (estilo guion), {len(sets)} sets en el pack.")
    for linea in informe_sets:
        print(linea)

    # fuera lo de otras corridas (dinámico / normal) y lo propio de la anterior
    _retirar_pistas_nuestras(
        timeline, [f"{L}-CTX", f"{L}-MAIN", f"{L}-CMP", L, f"{L}-EMOJI"] + [f"{L}-K{k}" for k in range(1, 25)],
        "subtítulos", "esta corrida es de estilo guion")

    # PISTAS. Las palabras GRANDES van en las pistas de abajo y las pequeñas encima: el macro «Luxe Shine» es de cristal y refracta lo que tiene
    # debajo (con la línea pequeña en una pista inferior se le colaba dentro de las letras, volteada). Primero se reparte cada palabra en su hueco
    # (el primero libre de su grupo), luego se crean en orden «ES-T1…» (las grandes primero) y por último se coloca.
    colocados = sin_texto = sin_pista = 0
    uso = {}
    # la salida del macro (un fundido de ~6 fotogramas) empieza ANTES del fin del clip: se alarga un poco para que la frase se vea entera hasta su final
    try:
        extra_fin = float(track_info.get("extra_fin_s", 0.04))
    except (TypeError, ValueError):
        extra_fin = 0.04
    min_frames = a_fotogramas(0.3, fps)
    pendientes = []
    for cue in cues:
        estilo_cue = cue.get("estilo")
        for run in cue.get("runs") or []:
            texto = (run.get("texto") or "").strip()
            if not texto:
                continue
            rol = run.get("rol") if run.get("rol") in ("main", "context", "complement") else "context"
            n_estilo = run.get("estilo") or estilo_cue
            juego = next((s for s in sets if s.get("numero") == n_estilo), None) if n_estilo else None
            if juego is None:
                juego = next((s for s in sets if s.get(rol)), sets[0])
            plantilla = juego.get(rol) or juego.get("main")
            if not plantilla:
                sin_pista += 1
                continue
            ini = max(timeline_start_frame, timeline_start_frame + a_fotogramas(float(run.get("t") or cue["start"]), fps))
            fin_s = run.get("fin")
            fin = timeline_start_frame + a_fotogramas(float(fin_s if isinstance(fin_s, (int, float)) else cue["end"]) + extra_fin, fps)
            fin = max(fin, ini + min_frames)          # una palabra que dura muy poco no llegaría a verse entera (entrada + salida del macro)
            pendientes.append({"run": run, "texto": texto, "rol": rol, "juego": juego, "plantilla": plantilla, "ini": ini, "fin": fin})
    pendientes.sort(key=lambda d: (d["ini"], 0 if d["rol"] == "main" else 1))
    huecos = {"main": [], "peq": []}          # fotograma desde el que está libre cada hueco de cada grupo
    for d in pendientes:
        lista = huecos["main" if d["rol"] == "main" else "peq"]
        for k, libre in enumerate(lista):
            if libre <= d["ini"]:
                d["hueco"] = k
                lista[k] = d["fin"]
                break
        else:
            d["hueco"] = len(lista)
            lista.append(d["fin"])
    n_main = len(huecos["main"])
    for d in pendientes:
        d["n"] = d["hueco"] + 1 if d["rol"] == "main" else n_main + d["hueco"] + 1
    total_pistas = n_main + len(huecos["peq"])
    idx_pista = {}
    for n in range(1, total_pistas + 1):
        idx, error = _conseguir_pista_video(timeline, f"{L}-T{n}")
        if error:
            print(f"  ERROR: no pude crear la pista '{L}-T{n}' de forma segura ({error}).")
            continue
        idx_pista[n] = idx
    pistas = list(range(total_pistas))
    for d in pendientes:
        run, texto, rol, juego, plantilla, ini, fin = d["run"], d["texto"], d["rol"], d["juego"], d["plantilla"], d["ini"], d["fin"]
        idx = idx_pista.get(d["n"])
        if idx is None:
            sin_pista += 1
            continue
        # la entrada del macro tarda ~14 fotogramas en verse entera: con la palabra a la vista solo 0.3-0.5 s, el comp arranca ya adelantado
        # (la referencia entra en 3-4 fotogramas). 'salto' (s) por palabra manda; si no, el del rol que trae el manifiesto.
        try:
            salto = float(run.get("salto")) if run.get("salto") is not None else float(
                track_info.get("salto_principal_s", 0.0) if rol == "main" else track_info.get("salto_pequena_s", 0.0))
        except (TypeError, ValueError):
            salto = 0.0
        desfase = max(0, a_fotogramas(salto, fps))
        item, puesto = colocar_medido(media_pool, timeline, plantilla, desfase, fin - ini, idx, ini, fps, color=COLOR_TEXTO)
        if item is None and desfase:
            item, puesto = colocar_medido(media_pool, timeline, plantilla, 0, fin - ini, idx, ini, fps, color=COLOR_TEXTO)
        if item is None:
            print(f"  Aviso: no pude colocar «{texto}» en {run.get('t')}s")
            continue
        tool = get_text_plus_tool(item)
        if tool is None or not set_input_safe(tool, "StyledText", texto):
            sin_texto += 1
            continue
        props = {}
        if isinstance(run.get("x"), (int, float)):
            props["Pan"] = _pan_px(float(run["x"]) - 0.5, ancho_tl)
        if isinstance(run.get("y"), (int, float)):
            props["Tilt"] = _tilt_px(0.5 - float(run["y"]), alto_tl)
        if isinstance(run.get("zoom"), (int, float)) and run["zoom"] > 0:
            props["ZoomX"] = props["ZoomY"] = float(run["zoom"])
        if props:
            _poner_props(item, props)
        if rol == "main":
            ajustar_barrido(item, (fin - ini) / float(fps), salto, run.get("ancho_rel"))
        colocados += 1
        clave = (juego.get("numero"), rol)
        uso[clave] = uso.get(clave, 0) + 1
    # v5.10 — EMOJIS: el del bloque entra con su palabra grande (cue.emoji_ini) y se queda hasta que se va la pila; va encima o debajo de la caja de
    # la pila (cue.caja, fracción del alto desde ARRIBA) según emoji_posicion. Misma colocación y animación que los de 3 líneas (colocar_emojis).
    planes_emoji = []
    for cue in cues:
        eid = cue.get("emoji")
        if not eid:
            continue
        caja = cue.get("caja")
        ys = [float(r["y"]) for r in (cue.get("runs") or []) if isinstance(r.get("y"), (int, float))]
        try:
            if isinstance(caja, (list, tuple)) and len(caja) == 2:
                arriba_y, abajo_y = 0.5 - float(caja[0]), 0.5 - float(caja[1])
            elif ys:
                arriba_y, abajo_y = 0.5 - min(ys), 0.5 - max(ys)
            else:
                continue
            ini_s = cue.get("emoji_ini")
            ini_p = max(timeline_start_frame, timeline_start_frame + a_fotogramas(float(ini_s if ini_s is not None else cue["start"]), fps))
            fin_p = timeline_start_frame + a_fotogramas(float(cue["end"]) + extra_fin, fps)
        except (TypeError, ValueError):
            continue
        if fin_p > ini_p + 1:
            planes_emoji.append({"emoji": eid, "ini": ini_p, "fin": fin_p, "y_arriba": arriba_y, "y_abajo": abajo_y})
    try:
        colocar_emojis(timeline, media_pool, track_info, planes_emoji, fps)
    except Exception as exc:
        print(f"  Aviso: no pude colocar los emojis del estilo guion ({type(exc).__name__}: {exc}).")
    # pistas de corridas anteriores que ya no hacen falta (la corrida anterior tenía más palabras a la vez)
    _retirar_pistas_nuestras(timeline, [f"{L}-T{k}" for k in range(len(pistas) + 1, len(pistas) + 25)],
                             "palabras", "esta corrida necesita menos pistas")
    print(f"  Colocadas {colocados} palabras en {len(pistas)} pista(s) ({L}-T1…{L}-T{len(pistas)}).")
    if sin_texto:
        print(f"  Aviso: {sin_texto} palabra(s) se colocaron pero no pude escribir su texto.")
    if sin_pista:
        print(f"  Aviso: {sin_pista} palabra(s) no se colocaron (sin pista o sin clip para ese rol).")
    if colocados:
        _ALGO_COLOCADO[0] = True
        _TOTAL[0] += colocados


def preparar_pack_kinetic(media_pool, nombre_pack, formato, ruta_drb, clip_prueba=None):
    """v5.4 — el bin del pack «Kinetic»: se importa el .drb una vez (ImportFolderFromFile) en su propio bin y se reutiliza. Devuelve (carpeta, aviso).
    No usa preparar_pack_drt: aquel da por bueno un bin solo si trae sets completos (principal / arriba / abajo) y este pack tiene otros clips."""
    clip_prueba = clip_prueba or KINETIC_CLIP_PRUEBA            # el clip que prueba que el bin del pack está completo (el pack «VIRAL» trae otros: v fina…)
    nombre_bin = _nombre_bin_pack(nombre_pack, formato)
    raiz = media_pool.GetRootFolder()
    existente = _subcarpeta(raiz, nombre_bin)
    if existente is not None and find_clip_by_name(media_pool, clip_prueba, existente):
        return existente, None
    if not ruta_drb or not Path(ruta_drb).is_file():
        return None, f"el pack '{nombre_pack}' no trae su .drb en este equipo ({ruta_drb or 'sin ruta'})."
    # Resolve a veces devuelve None (o falla) justo después de crear el proyecto o el timeline: se reintenta unas veces, y antes de rendirse se mira si el bin
    # se creó aunque la llamada no lo dijera (si no, quedaría un bin huérfano y el siguiente intento chocaría con su nombre).
    carpeta = existente
    ultimo_error = None
    for intento in range(5):
        if carpeta is not None:
            break
        try:
            carpeta = media_pool.AddSubFolder(media_pool.GetRootFolder(), nombre_bin)
        except Exception as exc:
            carpeta, ultimo_error = None, exc
        if carpeta is None:
            carpeta = _subcarpeta(media_pool.GetRootFolder(), nombre_bin)
        if carpeta is None:
            _time.sleep(0.8)
    if carpeta is None:
        return None, f"no pude crear el bin '{nombre_bin}' en el Media Pool" + (f" ({type(ultimo_error).__name__}: {ultimo_error})." if ultimo_error else " (Resolve no devolvió la carpeta).")
    try:
        previa = media_pool.GetCurrentFolder()
    except Exception:
        previa = None
    try:
        media_pool.SetCurrentFolder(carpeta)
    except Exception:
        pass
    importo = False
    try:
        importo = bool(media_pool.ImportFolderFromFile(str(ruta_drb)))
    except Exception as exc:
        print(f"  ImportFolderFromFile no está en este Resolve ({exc}).")
    try:
        if previa is not None:
            media_pool.SetCurrentFolder(previa)
    except Exception:
        pass
    if importo and find_clip_by_name(media_pool, clip_prueba, carpeta):
        print(f"  El bin del pack '{nombre_pack}' entró DIRECTO al Media Pool (desde el .drb).")
        return carpeta, None
    return None, f"importé el .drb del pack '{nombre_pack}' pero no encuentro sus clips («{clip_prueba}»…)."


KINETIC_CLIP_PRUEBA = "k hero blanco"


def _grupo_kinetic(nombre):
    """Capa del elemento: de la de abajo (héroe) a la de arriba (líneas pequeñas). Cada capa tiene sus propias pistas."""
    n = str(nombre).lower()
    if n.startswith("v "):                  # pack «VIRAL»: las palabras con efecto (negrita, shatter, select, drag) y, aparte, las líneas finas
        return 1 if n == "v fina" else 0
    if n.startswith("k hero"):
        return 0
    if n.startswith("k line"):
        return 1
    if n.startswith("k ring"):
        return 3
    if n.startswith("k sup") or n.startswith("k label"):
        return 4
    return 2          # cintas, serif, pincel


def place_kinetic_track(timeline, media_pool, track_info, base_template,
                        fps, timeline_start_frame, project=None):
    """v5.4 — estilo «Kinetic» (títulos de gancho): cada ELEMENTO de la pila (héroe, línea pequeña, serif, pincel, cinta, anillo, subrayado) es su propio
    clip del pack «Kinetic», con su posición, su tamaño, su giro y su momento.

    El archivo de datos trae bloques {start, end, runs: [{k, texto, t, x, y, size, rot, zx, zy}]} que ya armó la app (kinetic_planificador.py /
    kinetic_captions.py): `k` es el clip del pack («k hero lima»), `texto` y `size` van al Text+ «Template» del clip (el Size es una entrada del
    Text+: el texto se rasteriza al tamaño final), x/y = centro en fracción del cuadro (y desde ARRIBA), `rot` = giro en grados y zx/zy = zoom de los
    trazos (anillo, subrayado). Cada elemento va en la primera pista libre de su capa («ES-K1»…): los héroes abajo y las líneas pequeñas arriba.
    """
    lang = track_info["language"]
    L = str(lang).upper()
    data_path = Path(track_info["data_path"])
    if not data_path.exists():
        print(f"  Aviso: no encuentro {data_path}, salto '{lang}'")
        return
    datos = json.loads(data_path.read_text(encoding="utf-8"))
    cues = datos.get("cues", [])
    if not cues:
        print(f"  Aviso: '{data_path.name}' no tiene bloques.")
        return
    if track_info.get("sfx_library") or track_info.get("sfx_archivos"):
        place_sfx_track(timeline, media_pool, cues, track_info, fps, timeline_start_frame)

    def _res(clave, por_defecto):
        try:
            v = timeline.GetSetting(clave)
            return int(float(v)) if v else por_defecto
        except Exception:
            return por_defecto
    ancho_tl = _res("timelineResolutionWidth", 1080)
    alto_tl = _res("timelineResolutionHeight", 1920)

    pack_previo = pack_del_manifiesto(track_info, ancho_tl, alto_tl) if isinstance(track_info.get("plantilla"), dict) else None
    if not pack_previo or not pack_previo.get("drb"):
        fail("el estilo «Kinetic» necesita su pack (.drb) y el manifiesto no lo trae. Elige el pack «Kinetic» en Estilos.")
    carpeta, aviso = preparar_pack_kinetic(media_pool, pack_previo["nombre"], pack_previo["formato"], pack_previo.get("drb"), track_info.get("clip_prueba"))
    if carpeta is None:
        fail(f"no pude preparar el pack «{pack_previo['nombre']}»: {aviso}")
    clips = {}

    def _clip(nombre):
        if nombre not in clips:
            clips[nombre] = find_clip_by_name(media_pool, nombre, carpeta)
        return clips[nombre]
    print(f"\nIdioma '{lang}': {len(cues)} bloques (estilo Kinetic).")

    _retirar_pistas_nuestras(
        timeline, [f"{L}-CTX", f"{L}-MAIN", f"{L}-CMP", L, f"{L}-EMOJI"] + [f"{L}-T{k}" for k in range(1, 25)],
        "subtítulos", "esta corrida es de estilo Kinetic")

    try:
        extra_fin = float(track_info.get("extra_fin_s", 0.05))
    except (TypeError, ValueError):
        extra_fin = 0.05
    min_frames = a_fotogramas(0.45, fps)          # la entrada (8 fotogramas) y la salida (5) del comp necesitan ~13 fotogramas para verse enteras
    pendientes = []
    sin_clip = set()
    for cue in cues:
        for run in cue.get("runs") or []:
            nombre = run.get("k")
            plantilla = _clip(nombre) if nombre else None
            if plantilla is None:
                if nombre:
                    sin_clip.add(nombre)
                continue
            ini = max(timeline_start_frame, timeline_start_frame + a_fotogramas(float(run.get("t") or cue["start"]), fps))
            fin_s = run.get("fin")
            fin = timeline_start_frame + a_fotogramas(float(fin_s if isinstance(fin_s, (int, float)) else cue["end"]) + extra_fin, fps)
            fin = max(fin, ini + min_frames)
            pendientes.append({"run": run, "nombre": nombre, "plantilla": plantilla, "ini": ini, "fin": fin, "grupo": _grupo_kinetic(nombre)})
    pendientes.sort(key=lambda d: (d["grupo"], d["ini"]))
    huecos = {}               # capa -> [fotograma desde el que está libre cada hueco]
    for d in pendientes:
        lista = huecos.setdefault(d["grupo"], [])
        for k, libre in enumerate(lista):
            if libre <= d["ini"]:
                d["hueco"] = k
                lista[k] = d["fin"]
                break
        else:
            d["hueco"] = len(lista)
            lista.append(d["fin"])
    orden = {}
    n_pista = 0
    for g in sorted(huecos):
        for k in range(len(huecos[g])):
            n_pista += 1
            orden[(g, k)] = n_pista
    idx_pista = {}
    for (g, k), n in sorted(orden.items(), key=lambda kv: kv[1]):
        idx, error = _conseguir_pista_video(timeline, f"{L}-K{n}")
        if error:
            print(f"  ERROR: no pude crear la pista '{L}-K{n}' de forma segura ({error}).")
            continue
        idx_pista[n] = idx
    colocados = sin_pista = sin_texto = 0
    for d in pendientes:
        run, plantilla = d["run"], d["plantilla"]
        idx = idx_pista.get(orden[(d["grupo"], d["hueco"])])
        if idx is None:
            sin_pista += 1
            continue
        item, puesto = colocar_medido(media_pool, timeline, plantilla, 0, d["fin"] - d["ini"], idx, d["ini"], fps, color=COLOR_TEXTO)
        if item is None:
            print(f"  Aviso: no pude colocar «{run.get('texto') or d['nombre']}» en {run.get('t')}s")
            continue
        if run.get("texto") is not None:
            tool = get_text_plus_tool(item)
            if tool is None or not set_input_safe(tool, "StyledText", str(run["texto"])):
                sin_texto += 1
                continue
            if isinstance(run.get("size"), (int, float)):
                set_input_safe(tool, "Size", float(run["size"]))
        props = {}
        if isinstance(run.get("x"), (int, float)):
            props["Pan"] = _pan_px(float(run["x"]) - 0.5, ancho_tl)
        if isinstance(run.get("y"), (int, float)):
            props["Tilt"] = _tilt_px(0.5 - float(run["y"]), alto_tl)
        if isinstance(run.get("rot"), (int, float)) and abs(run["rot"]) > 0.01:
            props["RotationAngle"] = float(run["rot"])
        if isinstance(run.get("zx"), (int, float)) and run["zx"] > 0:
            props["ZoomX"] = float(run["zx"])
        if isinstance(run.get("zy"), (int, float)) and run["zy"] > 0:
            props["ZoomY"] = float(run["zy"])
        if props:
            _poner_props(item, props)
        colocados += 1
    # v5.5 — EMOJIS (los manda el estilo VIRAL; Kinetic no): igual que place_guion_track, el del bloque entra con su palabra clave (cue.emoji_ini) y se queda hasta que
    # se va la pila, encima o debajo de su caja (cue.caja, fracción del alto desde ARRIBA). Sin cue.emoji no se hace nada.
    planes_emoji = []
    for cue in cues:
        eid = cue.get("emoji")
        if not eid:
            continue
        try:
            caja = cue.get("caja")
            if isinstance(caja, (list, tuple)) and len(caja) == 2:
                arriba_y, abajo_y = 0.5 - float(caja[0]), 0.5 - float(caja[1])
            else:
                ys = [float(r["y"]) for r in (cue.get("runs") or []) if isinstance(r.get("y"), (int, float))]
                if not ys:
                    continue
                arriba_y, abajo_y = 0.5 - min(ys), 0.5 - max(ys)
            ini_s = cue.get("emoji_ini")
            ini_p = max(timeline_start_frame, timeline_start_frame + a_fotogramas(float(ini_s if ini_s is not None else cue["start"]), fps))
            fin_p = timeline_start_frame + a_fotogramas(float(cue["end"]) + extra_fin, fps)
        except (TypeError, ValueError):
            continue
        if fin_p > ini_p + 1:
            planes_emoji.append({"emoji": eid, "ini": ini_p, "fin": fin_p, "y_arriba": arriba_y, "y_abajo": abajo_y})
    if planes_emoji:
        try:
            colocar_emojis(timeline, media_pool, track_info, planes_emoji, fps)
        except Exception as exc:
            print(f"  Aviso: no pude colocar los emojis ({type(exc).__name__}: {exc}).")
    _retirar_pistas_nuestras(timeline, [f"{L}-K{k}" for k in range(n_pista + 1, n_pista + 25)], "elementos", "esta corrida necesita menos pistas")
    print(f"  Colocados {colocados} elementos en {n_pista} pista(s) ({L}-K1…{L}-K{n_pista}).")
    if sin_clip:
        print(f"  Aviso: el pack no trae estos clips: {', '.join(sorted(sin_clip))}.")
    if sin_texto:
        print(f"  Aviso: {sin_texto} elemento(s) se colocaron pero no pude escribir su texto.")
    if sin_pista:
        print(f"  Aviso: {sin_pista} elemento(s) no se colocaron (sin pista).")
    if colocados:
        _ALGO_COLOCADO[0] = True
        _TOTAL[0] += colocados


def place_dynamic_track(timeline, media_pool, track_info, base_template,
                        fps, timeline_start_frame, project=None):
    """Coloca subtitulos de 3 lineas (contexto / principal / complemento).

    Crea una pista de video por cada linea y va poniendo un Text+ por bloque
    en cada una, saltando las lineas que quedaron vacias.
    """
    lang = track_info["language"]
    data_path = Path(track_info["data_path"])
    if not data_path.exists():
        print(f"  Aviso: no encuentro {data_path}, salto '{lang}'")
        return

    datos = json.loads(data_path.read_text(encoding="utf-8"))
    cues = datos.get("cues", [])
    if not cues:
        print(f"  Aviso: '{data_path.name}' no tiene bloques.")
        return

    # Los efectos van en su propia pista de audio y no dependen de las
    # plantillas de texto, asi que se colocan aparte.
    if track_info.get("sfx_library") or track_info.get("sfx_archivos"):
        place_sfx_track(timeline, media_pool, cues, track_info, fps,
                        timeline_start_frame)

    # ¿La app pidio un pack en modo .drt? Si es asi, se prepara ANTES de
    # buscar_sets_de_plantillas: si se logra pasar sus clips al Media Pool,
    # la busqueda de "TUS plantillas" los encuentra sola -son exactamente
    # los mismos nombres ('contexto', 'principal'...) que ya reconoce-, y
    # se hereda gratis todo el camino que ya funciona (solo StyledText, sin
    # tocar posicion ni animacion). La busqueda se limita a SU bin para que
    # un 'contexto' suelto que el usuario tenga en otro lado del proyecto no
    # le gane al pack que acaba de elegir.
    carpeta_pack_drt = None
    pack_previo = None
    p_manifiesto = track_info.get("plantilla")
    # QUE pidio el manifiesto. Sin esta linea, "la app no pidio pack" y "el
    # script no pudo prepararlo" acaban las dos en «no encontre ningun
    # Text+», y cada una se arregla en un sitio distinto (la v1.0.35 se
    # diagnostico a ciegas por esto).
    if isinstance(p_manifiesto, dict):
        print(f"  El manifiesto pide el pack '{p_manifiesto.get('pack')}'"
              + ("" if project is not None
                 else " (pero no tengo el proyecto: no puedo prepararlo)"))
    else:
        print("  El manifiesto NO trae pack: uso tus plantillas del Media "
              "Pool, o el diseño automático si no tienes.")
    if isinstance(p_manifiesto, dict) and project is not None:
        def _res_tl(clave, por_defecto):
            try:
                v = timeline.GetSetting(clave)
                return int(float(v)) if v else por_defecto
            except Exception:
                return por_defecto
        pack_previo = pack_del_manifiesto(
            track_info, _res_tl("timelineResolutionWidth", 1920),
            _res_tl("timelineResolutionHeight", 1080))
        if pack_previo and (pack_previo.get("drt")
                            or pack_previo.get("drb")):
            # El prep NO puede tumbar la generacion. La leccion de la
            # v1.0.34 en Free: el fix de aridad activo de golpe seis
            # versiones de codigo del prep nunca corrido en produccion, y
            # cualquier error a mitad abortaba place_dynamic entero — cero
            # lineas y cero SFX, peor que la corrida sin pack de la semana
            # anterior. Un prep roto degrada a "sin pack" (el bin de una
            # corrida anterior si existe, o las plantillas del usuario, o el
            # diseño automatico), diciendolo; nunca a cero lineas.
            try:
                carpeta_pack_drt, aviso_drt = preparar_pack_drt(
                    project, media_pool, pack_previo["nombre"],
                    pack_previo["formato"], pack_previo["drt"],
                    pack_previo.get("drb"))
            except Exception as exc:
                carpeta_pack_drt = None
                aviso_drt = (f"fallo preparando el pack "
                             f"({type(exc).__name__}: {exc}). Genero sin el, "
                             "con lo que haya.")
                # Mismo rescate que hace el gate: si el bin del pack quedo
                # listo en una corrida anterior, se genera con ese.
                try:
                    _bin_previo = _subcarpeta(
                        media_pool.GetRootFolder(),
                        _nombre_bin_pack(pack_previo["nombre"],
                                         pack_previo["formato"]))
                    if _bin_previo is not None:
                        _sets_bin, _ = buscar_sets_de_plantillas(
                            media_pool, _bin_previo)
                        if _sets_bin:
                            carpeta_pack_drt = _bin_previo
                            aviso_drt = (
                                f"fallo preparando el pack "
                                f"({type(exc).__name__}: {exc}). Genero con "
                                "los sets que su bin ya tenia de una corrida "
                                "anterior.")
                except Exception:
                    pass
            if aviso_drt:
                print(f"  Aviso (pack '{pack_previo['nombre']}'): {aviso_drt}")

    # ¿Tiene sus propias plantillas (una o varias numeradas)? Si el pack .drt
    # se preparo arriba, se busca SOLO en su bin.
    sets, informe_sets = buscar_sets_de_plantillas(media_pool, carpeta_pack_drt)
    modo_plantillas = bool(sets)

    # Plantilla para las palabras sueltas sin marcar (rol 'base'). La del
    # BIN DEL PACK manda: la busqueda global salta los bins RCS a proposito
    # (un pack de ayer no debe contaminar una generacion sin pack), y por
    # eso el 'base' del propio pack era INVISIBLE aqui — 55 de 65 bloques
    # de un video real salieron pintados de principal (reporte del 01-09).
    # Misma prioridad que la pista SRT: primero el pack, despues el usuario.
    base_simple_template = None
    if carpeta_pack_drt is not None:
        base_simple_template = _buscar_base(media_pool, carpeta_pack_drt)
        if base_simple_template:
            print("  Plantilla 'simple' (base): la del bin del pack.")
    if not base_simple_template:
        base_simple_template = find_base_template(media_pool)
        if base_simple_template:
            print("  Encontré una plantilla 'simple' (o 'base') separada "
                  "para las palabras sueltas (subtítulo simple).")
    # Y si hay lineas 'base' sin plantilla propia, DECIRLO: el respaldo a
    # la principal es visible en pantalla y sin esta linea era un misterio.
    if modo_plantillas and not base_simple_template:
        hay_lineas_base = any(
            l.get("role") == "base"
            for c in cues for l in (c.get("lines") or []))
        if hay_lineas_base:
            print("  Aviso: hay líneas simples (rol 'base') y no encontré "
                  "plantilla 'base': saldrán con el estilo de la principal. "
                  "Arrastra también el clip 'base' del timeline del pack "
                  "al bin y vuelve a generar.")

    if modo_plantillas:
        print(f"\nIdioma '{lang}': {len(cues)} bloques dinámicos")
        print(f"  Usando TUS plantillas: encontré {len(sets)} "
              f"{'set' if len(sets) == 1 else 'sets'} de "
              f"{MAX_SETS} posibles (tipografía, tamaño y POSICIÓN las "
              "pones tú).")
        for linea in informe_sets:
            print(linea)
        if len(sets) > 1:
            print(f"  Los {len(sets)} sets se van alternando bloque a "
                  "bloque, sin repetir el mismo dos veces seguidas.")
    else:
        if not base_template:
            base_template = obtener_text_plus_base(timeline, media_pool)
        if not base_template:
            if pack_previo is not None:
                # Con un pack pedido, decir QUE gana cada salida: la
                # rapida (un lienzo cualquiera) ya da el automatico
                # entero con los estilos del pack; la completa da ademas
                # la posicion y animacion exactas.
                print(f"  Aviso: para '{lang}' no hay NINGÚN Text+ en el "
                      "Media Pool que me sirva de lienzo y tu versión de "
                      "Resolve no me deja crear uno por script. Salida "
                      "RÁPIDA (una vez): arrastra UN Text+ cualquiera "
                      "(Effects > Titles) al Media Pool y vuelve a "
                      "generar — con ese lienzo genero TODO en automático "
                      "con los estilos del pack (posición aproximada por "
                      "rol). La COMPLETA es el arrastre del bin del aviso "
                      "de arriba (posición y animación exactas).")
            else:
                print(f"  Aviso: para '{lang}' no encontré ningún Text+ para usar "
                      "y no pude crear uno automáticamente (tu versión de Resolve "
                      "no lo permite por script). Arrastra un Text+ (Effects > "
                      f"Titles) al Media Pool -llámalo '{TEMPLATE_CLIP_NAME}' o "
                      "déjalo con cualquier nombre- y vuelve a generar.")
            # QUE tipos vio: sin esta linea, un idioma que no conozcamos en
            # GetClipProperty('Type') seria otra ronda a ciegas.
            try:
                vistos = []

                def _recorrer(folder):
                    for clip in folder.GetClipList():
                        if len(vistos) >= 6:
                            return
                        try:
                            n = str(clip.GetName())
                        except Exception:
                            n = "?"
                        try:
                            t = str(clip.GetClipProperty("Type"))
                        except Exception:
                            t = "?"
                        vistos.append(f"{n} ({t})")
                    for sub in folder.GetSubFolderList():
                        if len(vistos) >= 6:
                            return
                        _recorrer(sub)

                _recorrer(media_pool.GetRootFolder())
                print("  En el Media Pool vi: "
                      + (", ".join(vistos) if vistos else "nada") + ".")
            except Exception:
                pass
            print("  Para saber QUÉ es lo que tu Resolve no deja hacer, corre "
                  "una vez: Área de trabajo > Scripts > Utility > "
                  "CineCaptions_Prueba_MediaPool. Escribe un informe para pegar.")
            return
        if pack_previo is not None:
            # El manifiesto pedia un pack y estamos en el diseño automatico:
            # sus clips no llegaron al Media Pool. Se genera con sus VALORES
            # (viajan desde la v1.0.37 justo para esto), y se DICE que se
            # pierde: si no, el resultado no es el pack y nadie sabe por que.
            print(f"\nIdioma '{lang}': {len(cues)} bloques dinámicos con los "
                  f"ESTILOS del pack '{pack_previo.get('nombre')}' "
                  "(tipografía, tamaño y color).")
            print("  Sus clips no llegaron al Media Pool en esta versión de "
                  "Resolve, así que va sin la animación ni la posición exacta "
                  "del pack. El texto se coloca igual.")
        else:
            print(f"\nIdioma '{lang}': {len(cues)} bloques dinámicos "
                  "(modo automático)")
        print(f"  Diseño aplicado por script, con {len(AUTO_PRESETS)} "
              "variantes que se van alternando.")

    # Reusar pistas existentes si ya fueron creadas anteriormente en el
    # timeline. Si la pista ya existe, se limpian sus clips previos para
    # que la re-generacion no los solape (el usuario ya no tiene que
    # borrar la linea de tiempo a mano).
    #
    # NUNCA se calcula el indice de una pista nueva a ojo (esa cuenta -
    # "cantidad + 1" sin comprobar que AddTrack realmente la creo- fue lo
    # que en algun momento hizo que se le escribiera encima al b-roll del
    # usuario: si AddTrack fallaba en silencio, el "+1" apuntaba a una
    # pista YA EXISTENTE). Ahora _crear_pista_verificada comprueba en dos
    # pasos independientes que la pista es nueva y esta vacia antes de
    # devolver su indice; si algo no cuadra, se aborta ese rol entero en
    # vez de arriesgar.
    #
    # Y al reutilizar una pista por nombre, se verifica que su contenido
    # sea SOLO nuestro (puros clips Text+) antes de limpiarla: si tiene
    # aunque sea un clip que no es Text+ (video real, b-roll), se trata
    # como ajena y no se toca.
    indices = {}
    limpiadas_total = 0
    huboerror = False
    for rol in DYNAMIC_ORDER:
        nombre_deseado = f"{lang.upper()}-{ROLE_SHORT[rol]}"
        # Se busca la primera pista con ese nombre QUE ADEMAS SEA
        # REUTILIZABLE (vacia o con puros Text+ nuestros).
        #
        # Antes se tomaba la primera que coincidiera de nombre y, si tenia
        # contenido ajeno, se abortaba el idioma entero. Pero si el usuario
        # borro los subtitulos y puso una imagen suya en esa pista, no poder
        # generar nunca mas es peor que crear otra: no tocar lo suyo esta
        # bien, no colocar nada por eso no.
        idx_existente = None
        ocupadas_por_el_usuario = 0
        for t in range(1, timeline.GetTrackCount("video") + 1):
            if timeline.GetTrackName("video", t).strip().upper() != nombre_deseado.upper():
                continue
            if _pista_video_reutilizable(timeline, t):
                idx_existente = t
                break
            ocupadas_por_el_usuario += 1
        if idx_existente is None:
            if ocupadas_por_el_usuario:
                print(f"  La pista '{nombre_deseado}' tiene contenido tuyo: "
                      "la dejo intacta y creo una nueva encima.")
            idx, error = _crear_pista_verificada(timeline, "video", nombre_deseado)
            if error:
                print(f"  ERROR: no pude crear la pista '{nombre_deseado}' de "
                      f"forma segura ({error}). Salto '{lang}' entero para no "
                      "arriesgar tu timeline.")
                huboerror = True
                break
            indices[rol] = idx
        else:
            borrados = _limpiar_pista(timeline, "video", idx_existente)
            if borrados:
                limpiadas_total += borrados
                print(f"  Pista existente '{nombre_deseado}' limpiada "
                      f"({borrados} clips previos borrados).")
            indices[rol] = idx_existente
    if huboerror:
        # fail() en vez de un return silencioso: si nos plantamos aqui NO se
        # coloca nada, y quien nos ejecuta (la app, o el Puente en Free)
        # tiene que enterarse. Antes salia "terminó bien" con el timeline
        # vacio, que es lo peor de los dos mundos.
        fail(f"no pude preparar las pistas de '{lang}' de forma segura "
             "(el motivo esta justo arriba). No coloque nada.")
    if limpiadas_total:
        print(f"  Total: {limpiadas_total} clips previos removidos antes "
              "de re-generar.")
    _retirar_pistas_nuestras(timeline, [lang.upper()] + [f"{lang.upper()}-K{k}" for k in range(1, 25)],
                             "subtítulos normales", "esta corrida es dinámica")

    estilos = estilos_con_fuentes(track_info.get("fonts"))

    # El modo «Diseño dinámico» (v1.0.49): los estilos y la posicion los
    # eligio el usuario en el programa y viajan POR VALORES en el track.
    # No toca el Media Pool ni el prep de packs. Prioridad: los sets del
    # pool del usuario (si los tiene) ganan; despues este diseño; despues
    # pack; despues los presets de fabrica.
    diseno = track_info.get("diseno")
    diseno_activo = False
    ancla_dis = factor_dis = None
    if isinstance(diseno, dict) and isinstance(diseno.get("estilos"), dict):
        diseno_activo = True
        # 'base' solo viene cuando el preset lo define (el motor de 2
        # lineas, v1.0.51): es el estilo de los bloques simples. Sin el,
        # 'base' sigue cayendo al estilo de 'main', como siempre.
        for _rol in ("context", "main", "complement", "base"):
            _e = diseno["estilos"].get(_rol)
            if isinstance(_e, dict):
                _mio = dict(estilos.get(_rol) or {})
                _mio.update(_e)
                estilos[_rol] = _mio
        try:
            ancla_dis = float(diseno.get("ancla_y"))
        except (TypeError, ValueError):
            ancla_dis = None
        try:
            factor_dis = float(diseno.get("factor_separacion"))
        except (TypeError, ValueError):
            factor_dis = None
        print(f"  Diseño dinámico: preset "
              f"'{diseno.get('preset') or 'personalizado'}' (estilos y "
              "posición elegidos en el programa).")
    fade_frames = a_fotogramas(FADE_OUT_SECONDS, fps)
    # El fundido de ENTRADA (v1.0.51) es solo del camino por valores puro
    # (diseño dinamico / automatico): a un pack, a las plantillas del
    # usuario o a un .setting cargado no se les toca la entrada — pueden
    # traer su propia animacion y no es nuestro diseño. El gate fino por
    # clip esta abajo, junto a apply_fades.
    entrada_frames = a_fotogramas(FADE_IN_SECONDS, fps)
    if diseno_activo and diseno.get("entrada") == "ninguna":
        entrada_frames = 0

    # Con un pack .drt NO se aplica fundido. Sus comps traen su PROPIA
    # animacion de entrada y salida (StyledTextFollower + PolyPath + curvas),
    # y nuestro fundido escribe Alpha1/Blend: pelearia contra ella y ademas
    # pisaria el modo de fusion, que es de lo que el pack decide.
    # La regla del pack es una sola: el diseño lo pone el pack, el script
    # solo escribe el texto.
    if carpeta_pack_drt is not None and fade_frames:
        fade_frames = 0
        print("  Fundido: lo pone el pack (trae su propia animación), "
              "así que no le añado el mío.")

    colocados = 0
    sin_texto = 0
    con_fundido = 0
    con_entrada = 0
    # 'con_hold' cuenta los bloques que TENIAN tiempo de sobra detras del
    # habla. Sin ese dato, un proyecto donde todos los bloques van pegados
    # salia acusando a Resolve de no dejar poner keyframes, cuando lo que
    # pasaba es que no habia hueco donde desvanecer.
    con_hold = 0
    # Cuantas lineas entraron con el NODO ENTERO del pack (degradados, formas,
    # fondos) y no solo con sus valores. Si el pack se pidio y esto queda en
    # cero, hay que decirlo: el resultado se parece pero no es el diseño.
    con_pack = 0
    fallos_estilo = set()
    uso_por_variante = {}  # cuantos bloques usaron cada set/preset
    # Bloques que ningun set del pack podia vestir enteros. Se omiten (no se
    # mezclan estilos) y se cuentan para decirlo al final, en el registro.
    omitidos_sin_set = 0

    # El veto de tildes del manifiesto (v1.0.61): {rol: [numeros de set]}
    # cuya tipografia no dibuja acentos. Se aplica solo a los bloques cuyo
    # texto de ese rol lleva tilde; manifiestos viejos no lo traen y todo
    # sigue como siempre.
    sets_sin_acentos = (pack_previo or {}).get("sets_sin_acentos") or {}
    bloques_con_veto = 0
    veto_sin_salida = 0
    # Arial donde falta la tipografia del clip (v2.0.2): {"rol|numero":
    # ["Arial", estilo]}, medido por la app. Se cuenta para decirlo.
    fuentes_respaldo = (pack_previo or {}).get("fuentes_respaldo") or {}
    con_arial = 0
    # La posicion del diseño por clip (v3.3.0): de pack_previo, como el
    # veto y el Arial. SOLO si los sets salieron del bin del pack: con el
    # prep fallido la busqueda es global y los clips serian las plantillas
    # del USUARIO, cuya posicion no es asunto del pack.
    transformaciones = ((pack_previo or {}).get("transformaciones") or {}
                        if carpeta_pack_drt is not None else {})
    try:
        ancho_tl = int(float(timeline.GetSetting("timelineResolutionWidth")))
        alto_tl = int(float(timeline.GetSetting("timelineResolutionHeight")))
    except Exception:
        ancho_tl, alto_tl = 1920, 1080
    _reiniciar_transformaciones()
    # v3.4.0: la Composicion del manifiesto (None = la plantilla tal cual).
    # Las medidas de las lineas van por formato: el que decidio el pack (o
    # el de la resolucion).
    comp_activa = composicion_activa(track_info.get("composicion"))
    formato_comp = ((pack_previo or {}).get("formato")
                    if isinstance(pack_previo, dict) else None) \
        or ("v" if alto_tl > ancho_tl else "h")
    _reiniciar_composicion(comp_activa["layout"] if comp_activa else None)
    # Los emojis de los bloques (v3.3.0): se anotan al colocar cada bloque
    # y se colocan al final, en su propia pista (ver colocar_emojis).
    planes_emoji = []
    # Sets usados de verdad, bloque a bloque (v2.0.2): 'uso_por_variante'
    # contaba el set PEDIDO por la rueda, no el que _set_para devolvia
    # tras el veto — el registro juraba «ningun set dos veces seguidas»
    # mientras el set 1 salia cinco veces seguidas.
    ultimo_set_usado = None
    repetidos_seguidos = 0

    # El reparto se calcula ACA, con lo que Resolve realmente encontro — no
    # se lee nada del JSON. Solo cuentan los bloques que de verdad usan un
    # set: las palabras sueltas van siempre con la plantilla 'base', y si
    # consumieran turno, dos bloques dinamicos separados por muchas palabras
    # sueltas podrian caer en el mismo set.
    # El pack de estilos, si la app pidió uno. Las plantillas del Media Pool
    # del usuario siguen mandando sobre él: esa regla no se toca.
    def _res(clave, por_defecto):
        try:
            v = timeline.GetSetting(clave)
            return int(float(v)) if v else por_defecto
        except Exception:
            return por_defecto

    pack = (None if modo_plantillas else pack_del_manifiesto(
        track_info, _res("timelineResolutionWidth", 1920),
        _res("timelineResolutionHeight", 1080)))
    if pack and pack.get("drt") and not pack["sets"]:
        # Llegar aca significa que el pack pedido ES un .drt pero no se pudo
        # preparar (preparar_pack_drt ya avisó el motivo mas arriba, y por
        # eso modo_plantillas quedó en False). No hay valores de respaldo
        # -este pack nunca los tuvo, es puro .drt-, asi que no queda mas
        # remedio que el diseño automatico. Que quede dicho, no en silencio.
        print(f"  El pack '{pack['nombre']}' no se pudo aplicar (ver aviso "
              "arriba): sigo con el diseño automático para no dejar "
              "este idioma sin subtítulos.")
        pack = None
    elif pack:
        etiqueta = "vertical" if pack["formato"] == "v" else "horizontal"
        print(f"  Pack de estilos: '{pack['nombre']}' "
              f"({len(pack['sets'])} sets, {etiqueta}).")
        if pack.get("aviso"):
            print(f"  Aviso: {pack['aviso']}")

    if modo_plantillas:
        n_variantes = len(sets)
    elif pack and pack["sets"]:
        n_variantes = len(pack["sets"])
    else:
        n_variantes = len(AUTO_PRESETS)
    bloques_con_set = sum(1 for c in cues if _usa_set(c))
    reparto = orden_de_variantes(bloques_con_set, n_variantes)
    # «Estilo fijo»: la variante que el usuario eligio en Composicion del bloque (0 = ir alternando)
    try:
        fijo = int(track_info.get("estilo_fijo") or 0)
    except (TypeError, ValueError):
        fijo = 0
    if 1 <= fijo <= n_variantes:
        reparto = [fijo - 1] * max(1, len(reparto))
    siguiente_turno = 0

    # Cuantos fotogramas ANTES de que se diga la palabra tiene que aparecer el
    # bloque destacado. Lo pide la app en el manifiesto y se aplica aqui
    # porque el fps solo se conoce dentro de Resolve.
    #
    # Solo se adelantan los bloques de 2 y 3 lineas: son los que llevan
    # animacion y necesitan margen para entrar. Las palabras sueltas no se
    # tocan, van pegadas al habla.
    adelanto = _adelanto_de(track_info)
    if adelanto:
        print(f"  Adelanto: los bloques destacados entran {adelanto} "
              "fotograma(s) antes.")

    def inicio_de(cue, ini_anterior, fin_hablado_anterior=None):
        """En que fotograma arranca un bloque, ya con el adelanto aplicado.

        El adelanto NO puede comerse al bloque anterior. Con un adelanto mas
        grande que la duracion del bloque de delante -por ejemplo 30
        fotogramas y una palabra suelta que dura 15- el bloque adelantado
        arrancaba ANTES de que empezara el anterior, y los dos clips se
        encabalgaban. Por eso se pasa el inicio ya fijado del anterior y se
        deja siempre al menos un fotograma de por medio.

        Y tampoco puede comerse el HABLA del anterior (v2.0.2, reporte
        literal: «desaparecen antes de que termine de decir la palabra...
        todo debe ser acorde al audio»): el fin del bloque anterior se
        recorta al inicio adelantado de este, asi que con adelanto > 0 la
        palabra suelta de delante se cortaba a medias. El adelanto se
        acorta hasta donde el anterior deja de hablar (nunca mas tarde
        del inicio real de este, por si Whisper solapa dos palabras).
        """
        if cue is None:
            return None
        real = timeline_start_frame + a_fotogramas(cue["start"], fps)
        ini = real - (adelanto if _usa_set(cue) else 0)
        if fin_hablado_anterior is not None:
            ini = max(ini, min(real, fin_hablado_anterior))
        ini = max(timeline_start_frame, ini)
        if ini_anterior is not None and ini <= ini_anterior:
            ini = ini_anterior + 1
        return ini

    ini_bloque = inicio_de(cues[0] if cues else None, None)
    # Huella de colocacion (v2.0.3): los 3 primeros bloques con set
    # imprimen el inicio-fin REAL de cada linea, para que el proximo
    # reporte de escalera se lea en numeros y no en capturas.
    bloques_huella = 0

    for i_cue, cue in enumerate(cues):
        usa_set = _usa_set(cue)
        if usa_set:
            bloques_huella += 1
        # v3.4.0: las lineas de ESTE bloque, para la Composicion.
        bloque_comp = []

        # Hay que saber donde arranca el SIGUIENTE para saber donde termina
        # este: si el que viene se adelanto, este tiene que cerrar justo
        # antes. Es lo unico que hace falta para que sigan pegados y no se
        # encabalguen.
        # Donde deja de hablarse de verdad. 'end' viene estirado para que no
        # queden huecos, asi que no sirve para saberlo. Un manifiesto viejo no
        # trae este dato: ahi se toma el final del bloque, que deja el fundido
        # en cero — preferible a volver a borrar sobre la voz.
        # v1.0.63: la clave puede venir con null (float(None) tumbaba la
        # colocacion ENTERA donde el gemelo Lua degradaba solo con
        # tonumber(nil) — alineados: si no es numero, cae a 'end').
        # Va ANTES de inicio_de(siguiente): el adelanto del siguiente no
        # puede pisar este habla (v2.0.2).
        fin_hablado_crudo = cue.get("fin_hablado")
        if not isinstance(fin_hablado_crudo, (int, float)):
            fin_hablado_crudo = cue["end"]
        fin_hablado_frame = timeline_start_frame + a_fotogramas(
            float(fin_hablado_crudo), fps)

        siguiente = cues[i_cue + 1] if i_cue + 1 < len(cues) else None
        ini_siguiente = inicio_de(siguiente, ini_bloque, fin_hablado_frame)

        # Separacion con el bloque siguiente. Antes los clips quedaban
        # pegados: el ultimo frame de uno era el primero del otro.
        gap = GAP_BLOQUE_FRAMES if usa_set else GAP_BASICO_FRAMES
        fin_frame = timeline_start_frame + a_fotogramas(cue["end"], fps) - gap

        # Cortar solo si de verdad invade. Cuando hay silencio de por medio el
        # final natural ya cae antes, asi que el hueco se conserva: lo unico
        # que pasa es que se acorta lo que el siguiente se adelanto, que es
        # exactamente lo que se quiere.
        if ini_siguiente is not None and fin_frame > ini_siguiente:
            fin_frame = ini_siguiente

        # v1.0.63 (reporte literal: «dejan fotogramas vacios entre
        # medios»): el bump anti-solape de inicio_de (ini_anterior + 1)
        # empuja el arranque del siguiente sin extender el fin de este —
        # con un cue de menos de medio fotograma quedaba EXACTAMENTE un
        # frame vacio que nadie cerraba. Un hueco de 1-2 frames solo
        # puede ser nuestro: los silencios que la app deja a proposito
        # miden mas de HOLD_MAXIMO (2 s), decenas de frames.
        if (ini_siguiente is not None and fin_frame < ini_siguiente
                and (ini_siguiente - fin_frame) <= 2):
            fin_frame = ini_siguiente

        # El turno se GASTA tras elegir el set (v2.0.2): un bloque omitido
        # por falta de set no consume rueda.
        if usa_set:
            variante = reparto[min(siguiente_turno, len(reparto) - 1)]
            # v5.8: la APP decide el estilo de cada bloque (cue['estilo'] = el número de la variante del pack) y lo enseña en Creativo;
            # la rueda de arriba solo vale si la app no mandó nada (manifiestos viejos)
            if modo_plantillas and cue.get("estilo") is not None:
                for j, s_pack in enumerate(sets):
                    if s_pack.get("numero") == cue["estilo"]:
                        variante = j
                        break
        else:
            variante = None

        # Un bloque de pura palabra suelta normalmente usa la plantilla
        # 'base'; el set 1 queda como respaldo por si esa plantilla no
        # existe, para no dejar 'juego'/'estilos_bloque' sin definir.
        indice_estilo = 0 if variante is None else variante
        n_set_pack = None
        if modo_plantillas:
            # Que roles necesita ESTE bloque (base comparte pista con main).
            roles_bloque = {("main" if l.get("role") == "base"
                             else l.get("role"))
                            for l in cue.get("lines", [])
                            if (l.get("text") or "").strip()}
            # El veto por tildes (v1.0.61): solo los roles de ESTE bloque
            # cuyo texto lleva acento y cuyo rol figura en el veto.
            vetado = {}
            if sets_sin_acentos:
                for l in cue.get("lines", []):
                    rol = ("main" if l.get("role") == "base"
                           else l.get("role"))
                    if (rol in sets_sin_acentos
                            and tiene_acentos(l.get("text") or "")):
                        vetado[rol] = sets_sin_acentos[rol]
            if vetado:
                bloques_con_veto += 1
            juego = _set_para(sets, indice_estilo, roles_bloque, vetado)
            if juego is None and vetado:
                # Sin el veto habria set: mejor una tilde con la fuente
                # equivocada que omitir un bloque que la version anterior
                # colocaba. Se dice, no en silencio.
                juego = _set_para(sets, indice_estilo, roles_bloque)
                if juego is not None:
                    veto_sin_salida += 1
            if juego is None:
                # Ningun set tiene los roles de este bloque: se omite ENTERO,
                # que es lo pedido. Mezclar sets o sustituir por 'principal'
                # es lo que se veia como "el pack no respeta su diseño".
                omitidos_sin_set += 1
                # El omitido TAMBIEN deja el inicio avanzado (v2.0.1, como
                # el goto del gemelo Free): sin esto el bloque siguiente
                # anclaba sus lineas al inicio de ESTE.
                ini_bloque = ini_siguiente
                continue
            if usa_set:
                # El set que SALIO, no el pedido: tras el veto pueden
                # diferir, y el registro tiene que decir la verdad.
                usado = sets.index(juego)
                # v5.8: si la APP decidio el estilo (alternar, uno fijo o el que el usuario eligio en Creativo) repetirlo es una eleccion, no un fallo
                if usado == ultimo_set_usado and cue.get("estilo") is None:
                    repetidos_seguidos += 1
                ultimo_set_usado = usado
                uso_por_variante[usado] = uso_por_variante.get(usado, 0) + 1
                siguiente_turno += 1
        elif diseno_activo:
            # El look es EL ELEGIDO: sin rotacion de variantes.
            estilos_bloque = estilos
        elif pack:
            estilos_bloque, n_set_pack = estilos_del_pack(
                pack, indice_estilo, estilos)
        else:
            estilos_bloque = estilos_del_preset(estilos, indice_estilo)
        if usa_set and not modo_plantillas:
            if variante == ultimo_set_usado:
                repetidos_seguidos += 1
            ultimo_set_usado = variante
            uso_por_variante[variante] = uso_por_variante.get(variante, 0) + 1
            siguiente_turno += 1

        def _plantilla_de(linea):
            rol = linea.get("role")
            # 'base' (palabra suelta sin marcar) comparte la pista de
            # 'main', para no sumar una cuarta pista en Resolve.
            rol_pista = "main" if rol == "base" else rol
            if not (linea.get("text") or "").strip() or rol_pista not in indices:
                return None
            usa_base_propia = rol == "base" and base_simple_template is not None
            if usa_base_propia:
                plantilla = base_simple_template
            elif modo_plantillas:
                # El set ya se eligio para que TENGA estos roles (_set_para),
                # asi que aqui no hace falta ningun respaldo. Y no debe
                # haberlo: hasta la v1.0.32 la cadena acababa en
                # juego['main'] y el complemento salia con el estilo de la
                # principal — "no respeta el diseño" en el reporte.
                plantilla = juego.get(rol_pista)
            else:
                plantilla = base_template
            if not plantilla:
                return None
            return rol, rol_pista, usa_base_propia, plantilla

        # La escalera de Studio (reporte literal 14-09, y de nuevo tras la
        # v2.0.1: «los bloques desaparecen en escalera... las primeras
        # deben esperar a la ultima y salir juntas, como en Free»): un
        # titulo Fusion del pool tiene la duracion de su comp (~98-247
        # fotogramas en los .drb) y Studio RECORTA en silencio cada linea
        # a esa duracion cuando el bloque dura mas — la que entro primero
        # se cortaba primero. La v2.0.1 intento pre-calcularlo con
        # GetClipProperty("Frames") del item del pool, que para un
        # generador devuelve VACIO: el clamp nunca corria y nada lo decia
        # (test_v201 lo certifico con un doble que siempre contestaba). La
        # verdad se mide DESPUES de colocar (GetDuration, abajo): la
        # primera linea colocada fija el fin que sus hermanas pueden
        # alcanzar. Para eso se colocan en orden de entrada — la mas
        # temprana es la mas restrictiva (inicio + largo del comp).
        # ponytail: en un bloque mas largo que el comp el texto se va
        # antes de acabar la frase; partirlo en dos clips re-animaria la
        # entrada.
        lineas_en_orden = sorted(
            cue.get("lines", []),
            key=lambda l: (l.get("start") or cue["start"]))
        primera_colocada = True

        for linea in lineas_en_orden:
            sel = _plantilla_de(linea)
            if sel is None:
                continue
            rol, rol_pista, usa_base_propia, plantilla = sel
            texto = (linea.get("text") or "").strip()

            # Cada linea entra cuando se dice su primera palabra; las tres
            # terminan en el mismo frame para poder cerrarlas juntas. El
            # escalonado se mide respecto al BLOQUE, no al timeline, para que
            # se conserve aunque el arranque del bloque se haya movido.
            retardo = a_fotogramas(
                ((linea.get("start") or cue["start"]) - cue["start"]), fps)
            inicio_frame = max(timeline_start_frame, ini_bloque + retardo)
            # NUNCA terminar despues que los hermanos (v1.0.57): cuando el
            # adelanto del bloque SIGUIENTE recorta fin_frame por debajo
            # del inicio de una linea tardia, el max(1,...) de abajo dejaba
            # ese clip de 1 frame acabando DESPUES de fin_frame-1 — la
            # «salida en escalera» del reporte. Con el clamp, esa linea
            # sale como un destello de 1 frame que cierra CON los demas.
            inicio_frame = min(inicio_frame, fin_frame - 1)
            duracion = max(1, fin_frame - inicio_frame)

            # Desde donde arranca el COMP dentro del clip (no en el timeline).
            #
            # v1.0.68 (reporte literal 12-09: «entran como que cortados, no
            # desde el principio y por ello no se les ve la animacion»): el
            # comp arranca SIEMPRE en su fotograma 0 — cada linea reproduce
            # su animacion de entrada ENTERA al entrar en su tiempo real.
            # Esto INVIERTE a proposito la fase v1.0.25/v1.0.33 (el comp
            # empezaba avanzado en 'retardo' para que las curvas fueran en
            # fase y cerraran juntas — con retardos reales de 12-45
            # fotogramas eso SALTABA la entrada entera): el FIN comun del
            # grupo NO cambia (fin_frame es el mismo para las tres lineas;
            # startFrame no toca recordFrame ni duracion), lo unico cedido
            # es que la salida de las lineas 2/3 puede quedar a mitad de
            # curva. Elegido por orden literal — no lo «arregles» de vuelta
            # sin una orden suya.
            #
            # 'continuacion' (manifiestos <= v1.0.65, base acumulativo)
            # conserva su lectura: la palabra que se suma no re-anima la
            # entrada del texto que ya estaba en pantalla.
            desfase = 0
            try:
                viene_de = cue.get("continuacion")
                if viene_de is not None:
                    desfase = a_fotogramas(cue["start"] - float(viene_de), fps)
            except (TypeError, ValueError):
                desfase = 0
            desfase = max(0, desfase)
            # v5.7 (FIX DE ANIMACIÓN, pedido: «algunos textos no aparecen porque pasan muy rápido y no da tiempo a la animación»): si la
            # línea se ve tan poco que su entrada no alcanzaría a mostrar el texto, la app marca 'salto_anim' (segundos) y el comp arranca
            # ya adelantado esos segundos: entra rápido pero SE VE. Solo en esas líneas cortas: las normales siguen reproduciendo su entrada
            # entera desde el fotograma 0 (la regla v1.0.68 no cambia). Solo con packs / plantillas (su animación vive en el comp).
            if pack or modo_plantillas:
                try:
                    salto_anim = float(linea.get("salto_anim") or 0)
                except (TypeError, ValueError):
                    salto_anim = 0.0
                if salto_anim > 0:
                    desfase = max(desfase, a_fotogramas(salto_anim, fps))

            def _colocar(desde):
                return colocar_medido(media_pool, timeline, plantilla, desde,
                                      duracion, indices[rol_pista],
                                      inicio_frame, fps, color=COLOR_TEXTO)

            item, puesto = _colocar(desfase) if desfase else _colocar(0)
            if item is None and desfase:
                # El generador puede ser mas corto que el desfase pedido.
                # Caer DIRECTO a 0 dejaba esa linea animando 'retardo'
                # fotogramas por detras de sus hermanas — su animacion de
                # salida cerraba tarde: la otra mitad de la «salida en
                # escalera» del reporte (v1.0.57). Primero se recorta el
                # desfase a lo que el generador permita (fase parcial, lo
                # mas cerca posible de cerrar juntas) y solo despues se
                # cae a 0, DICIENDOLO.
                desfase_max = 0
                try:
                    desfase_max = max(0, int(float(
                        plantilla.GetClipProperty("Frames") or 0)) - duracion)
                except Exception:
                    desfase_max = 0
                if 0 < desfase_max < desfase:
                    item, puesto = _colocar(desfase_max)
                    if item is not None:
                        print(f"  Aviso: el generador de '{rol}' es corto "
                              f"para su desfase ({desfase}); lo recorté a "
                              f"{desfase_max} para que cierre casi en fase.")
                if item is None:
                    item, puesto = _colocar(0)
                    if item is not None:
                        print(f"  Aviso: '{rol}' anima sin desfase "
                              "(generador corto): su salida puede no "
                              "cerrar exacta con las otras líneas.")
            if item is None:
                print(f"  Aviso: no pude colocar '{rol}' en {cue['start']:.2f}s")
                continue

            # v1.0.63: nadie verificaba que Resolve respetara la duracion
            # pedida — si la recorta EN SILENCIO (en vez de devolver
            # falso), esa linea termina ANTES que sus hermanas: escalera
            # real sin una linea que la explique. Que la llamada no
            # reviente no prueba nada (la leccion del fundido).
            # v2.0.2: si recorto la PRIMERA linea del bloque, ese es el
            # fin que las demas pueden alcanzar — se baja fin_frame y las
            # hermanas cierran con ella. v2.0.3: 'puesto' viene del
            # colocador, que ya compenso el fotograma de menos de Resolve
            # — lo que quede corto aqui es un recorte de verdad.
            if usa_set and bloques_huella <= 3 and puesto:
                if bloques_huella == 1 and primera_colocada:
                    print("  Huella de colocación (3 primeros bloques con "
                          "set): inicio-fin real (fotogramas).")
                print(f"    {cue['start']:.2f}s {rol}: {inicio_frame}-"
                      f"{inicio_frame + puesto - 1} ({puesto} f)")
            if puesto and puesto != duracion:
                if primera_colocada and puesto < duracion:
                    fin_frame = inicio_frame + puesto
                    print(f"  La plantilla de '{rol}' dura {puesto} "
                          f"fotogramas: el bloque de {cue['start']:.2f}s "
                          f"se acorta de {duracion} a {puesto} para que "
                          "las líneas cierren juntas.")
                else:
                    print(f"  Aviso: Resolve colocó '{rol}' con {puesto} "
                          f"fotogramas (pedí {duracion}) en "
                          f"{cue['start']:.2f}s — esa línea puede no "
                          "cerrar junto a sus hermanas.")
            primera_colocada = False
            tool = get_text_plus_tool(item)
            if tool is None:
                sin_texto += 1
                continue

            # EL ORDEN IMPORTA: primero el nodo entero del pack, después el
            # texto. Al revés, LoadSettings borraría lo que acabamos de
            # escribir (el .setting trae su propio StyledText dentro).
            cargado = False
            if pack and not usa_base_propia:
                estilo_del_rol = (pack["base"] if rol == "base" and pack["base"]
                                  else estilos_bloque[rol_pista])
                cargado = cargar_setting(
                    item, tool,
                    ruta_de_setting(pack,
                                    "base" if (rol == "base" and pack["base"])
                                    else n_set_pack,
                                    "base" if (rol == "base" and pack["base"])
                                    else rol_pista),
                    estilo_del_rol)
                if cargado:
                    con_pack += 1

            if not set_input_safe(tool, "StyledText", texto):
                sin_texto += 1
                continue

            # Arial donde falta la tipografia del clip (v2.0.2, pedido
            # literal: «en el caso de no tener la tipografia se use Arial
            # en el grosor o inclinacion de la que falta»). Es la UNICA
            # excepcion nueva al «solo StyledText» del modo plantillas, y
            # solo entra con la medicion de la app delante: sin entrada
            # en el mapa no se toca ni Font ni Style. DESPUES del texto
            # (LoadSettings pisaria lo escrito).
            if modo_plantillas and fuentes_respaldo and juego is not None:
                clave_f = ("base|0" if usa_base_propia
                           else f"{rol_pista}|{juego.get('numero')}")
                arial = fuentes_respaldo.get(clave_f)
                if (isinstance(arial, (list, tuple)) and len(arial) == 2
                        and set_input_safe(tool, "Font", arial[0])
                        and set_input_safe(tool, "Style", arial[1])):
                    con_arial += 1
            # La posicion del diseño, si Resolve la dejo en el centro
            # (v3.3.0).
            if modo_plantillas and transformaciones and juego is not None:
                aplicar_transformacion(
                    item, transformaciones.get(
                        "base|0" if usa_base_propia
                        else f"{rol_pista}|{juego.get('numero')}"),
                    ancho_tl, alto_tl)

            if cargado:
                # El pack decide EL LOOK Y LA POSICIÓN. Hasta la v1.0.25 aquí
                # se pisaba el Center con altura_de_linea(), pensando en
                # tapar el hueco de la tercera línea en bloques de 2 — pero
                # en un pack el usuario YA colocó contexto/principal/
                # complemento donde los quiere: esa disposición ES el
                # diseño. Pisarla es exactamente lo que la regla de "nunca
                # destruir el trabajo del usuario" prohíbe (ver
                # crear_pista_verificada / plantillas del Media Pool, que
                # tampoco tocan posición). Si un pack deja el hueco de la
                # tercera línea en sus bloques de 2, es una decisión de
                # quien diseñó el pack, no algo que el script deba corregir.
                #
                # EXCEPCION declarada: los .setting de la cache instalada
                # (pack incorporado) no traen posicion — vive en el PolyPath
                # del grupo, irreproducible offline. Sin esto, los tres
                # roles salian apilados al centro del fotograma.
                if pack and pack.get("settings_sin_posicion"):
                    set_center_safe(tool, 0.5,
                                    altura_de_linea(rol, estilos_bloque))
            elif not modo_plantillas and not usa_base_propia:
                # El estilo automatico solo se aplica cuando el script decide
                # el diseño el mismo (ni plantillas propias, ni 'base' propia).
                # Con un pack cuyo .setting no cargó, aquí entran igual sus
                # VALORES: para eso viajan en el manifiesto.
                #
                # 'base' con estilo propio (v1.0.51): si el diseño lo trae
                # (motor de 2 lineas), los bloques simples lo usan; si no,
                # caen al de 'main' como siempre — sin esto, lo que era el
                # complemento saldria grande y dorado como otra clave.
                if rol == "base" and pack and pack["base"]:
                    estilo_linea = pack["base"]
                elif rol == "base" and estilos_bloque.get("base"):
                    estilo_linea = estilos_bloque["base"]
                else:
                    estilo_linea = estilos_bloque[rol_pista]
                fallos_estilo.update(apply_auto_style(
                    tool, estilo_linea,
                    altura_de_linea(rol, estilos_bloque,
                                    ancla_dis, factor_dis)))

            # El fundido SOLO en el tiempo prestado.
            #
            # Antes se aplicaba en los ultimos fade_frames del clip a secas, y
            # como el bloque terminaba justo con su ultima palabra, el texto se
            # estaba borrando MIENTRAS aun se hablaba. Ahora se mide contra
            # 'fin_hablado': si detras del habla no sobra tiempo, no hay
            # fundido y el bloque corta limpio para que entre el siguiente.
            hold = fin_frame - fin_hablado_frame
            fade = min(fade_frames, max(0, hold), duracion - 1)
            # La entrada solo en el camino por valores puro: ni plantillas
            # del usuario, ni .setting cargado (traen su animacion), ni el
            # 'base' propio del usuario. Y nunca sobre un clip continuacion
            # (re-animar la entrada del texto que ya estaba en pantalla era
            # exactamente el parpadeo entre palabras).
            entrada = 0
            if (entrada_frames and not modo_plantillas and not cargado
                    and not usa_base_propia
                    and cue.get("continuacion") is None):
                entrada = min(entrada_frames, duracion - 1)
            if fade >= 1:
                con_hold += 1
            if entrada >= 1 or fade >= 1:
                e_ok, s_ok = apply_fades(item, entrada, fade)
                if e_ok:
                    con_entrada += 1
                if s_ok:
                    con_fundido += 1

            if comp_activa is not None:
                clave_c = ("base|0" if usa_base_propia else
                           f"{rol_pista}|{juego.get('numero') if juego else 1}")
                m = (linea.get("medidas") or {}).get(formato_comp) \
                    if isinstance(linea.get("medidas"), dict) else None
                ancho_em = None
                if isinstance(m, dict) and m.get(clave_c) is not None:
                    try:
                        ancho_em = float(m[clave_c])
                    except (TypeError, ValueError):
                        ancho_em = None
                bloque_comp.append({"rol": rol, "item": item,
                                    "ancho_em": ancho_em,
                                    "zx": _prop_de(item, "ZoomX") or 1.0})
            colocados += 1

        # v3.4.0: la Composicion del bloque, SOBRE lo que la plantilla (o
        # Resolve) dejo: se lee el Pan/Tilt actual y se le suma. Con "cc"
        # y 0/0 aqui ni se entra (comp_activa es None).
        if comp_activa is not None and bloque_comp:
            d, _layout = desplazamientos_bloque(comp_activa, ini_bloque,
                                                bloque_comp, ancho_tl, alto_tl)
            for k, l in enumerate(bloque_comp):
                pan = _prop_de(l["item"], "Pan") or 0.0
                tilt = _prop_de(l["item"], "Tilt") or 0.0
                if _poner_props(l["item"], {"Pan": pan + d[k]["dx"],
                                            "Tilt": tilt + d[k]["dy"]}):
                    _COMP["movidas"] += 1
                    if d[k]["alineada"]:
                        _COMP["alineadas"] += 1
                else:
                    _COMP["fallidas"] += 1
                if d[k]["sin_medida"]:
                    _COMP["sin_medida"] += 1

        # El emoji del bloque (v3.3.0; ver el gemelo .lua): entra con la
        # PRINCIPAL y dura hasta el fin del bloque; su altura sale de la de
        # las lineas (centro = 0, arriba positivo).
        if cue.get("emoji"):
            plan = {"emoji": cue["emoji"], "fin": fin_frame, "ini": None,
                    "y_arriba": None, "y_abajo": None}
            # v5.3: si el pack trae el bloque 'imagen', ESE bloque manda donde y de que tamaño va
            # el emoji (su Pan/Tilt/Zoom en el bin); sin el, va debajo de las lineas.
            if modo_plantillas and juego is not None:
                slot = (transformaciones.get(f"image|{juego.get('numero')}")
                        or transformaciones.get("image|1"))
                if slot:
                    plan["slot"] = list(slot)
            # v3.4.0: el emoji se mueve con el grupo (Altura/Horizontal).
            if comp_activa is not None:
                plan["dx_n"] = comp_activa["horizontal"]
                plan["dy_n"] = comp_activa["altura"]
            # v3.3.1: el emoji pertenece a UNA linea (emoji_linea, base 0) y
            # la app mando el ancho de esa linea (emoji_medidas): se coloca
            # al FINAL de ella (ver el gemelo .lua).
            try:
                k_emoji = int(cue.get("emoji_linea") or 0)
            except (TypeError, ValueError):
                k_emoji = 0
            for k, l in enumerate(cue.get("lines") or []):
                if not (l.get("text") or "").strip():
                    continue
                rol_l = l.get("role")
                tr = None
                if modo_plantillas and juego is not None:
                    clave = ("base|0" if rol_l == "base"
                             and base_simple_template is not None else
                             f"{'main' if rol_l == 'base' else rol_l}|"
                             f"{juego.get('numero')}")
                    tr = transformaciones.get(clave)
                    y = float(tr[1]) if tr else 0.0
                else:
                    y = altura_de_linea(rol_l, estilos_bloque or {},
                                        ancla_dis, factor_dis) - 0.5
                if k == k_emoji:
                    medidas = l.get("emoji_medidas")
                    plan["medidas"] = (medidas if isinstance(medidas, dict)
                                       else None)
                    # 'juego' solo esta ligado en modo plantillas (el
                    # cortocircuito de arriba lo protege igual).
                    plan["numero"] = (juego.get("numero")
                                      if modo_plantillas and juego is not None
                                      else None)
                    plan["y"] = y
                    plan["x"] = float(tr[0]) if tr else 0.0
                    plan["zx"] = float(tr[2]) if tr else 1.0
                plan["y_arriba"] = (y if plan["y_arriba"] is None
                                    else max(plan["y_arriba"], y))
                plan["y_abajo"] = (y if plan["y_abajo"] is None
                                   else min(plan["y_abajo"], y))
                if rol_l == "main" or plan["ini"] is None:
                    r = a_fotogramas(((l.get("start") or cue["start"])
                                      - cue["start"]), fps)
                    plan["ini"] = max(timeline_start_frame,
                                      min(ini_bloque + r, fin_frame - 1))
            # v4.1.0: tambien EMPIEZA con la palabra (emoji_ini); sin la
            # clave, como siempre (ver el gemelo .lua).
            if plan["ini"] is not None and cue.get("emoji_ini") is not None:
                try:
                    f0 = ini_bloque + a_fotogramas(
                        float(cue["emoji_ini"]) - cue["start"], fps)
                    plan["ini"] = max(ini_bloque, min(f0, fin_frame - 2))
                except (TypeError, ValueError):
                    pass
            # v3.3.3: el emoji termina con la PALABRA (emoji_fin, segundos),
            # no con el bloque; minimo 2 fotogramas. Sin la clave, como
            # siempre (ver el gemelo .lua).
            if plan["ini"] is not None and cue.get("emoji_fin") is not None:
                try:
                    f = ini_bloque + a_fotogramas(
                        float(cue["emoji_fin"]) - cue["start"], fps)
                    plan["fin"] = max(plan["ini"] + 2, min(fin_frame, f))
                except (TypeError, ValueError):
                    pass
            if plan["ini"] is not None:
                planes_emoji.append(plan)

        # El inicio que acabamos de calcular para el siguiente pasa a ser el
        # del bloque en curso. Asi no se recalcula (y no se puede recalcular
        # distinto, que es como se cuelan los desajustes de un fotograma).
        ini_bloque = ini_siguiente

    if omitidos_sin_set:
        print(f"  Omití {omitidos_sin_set} bloques: ningún set de tus "
              "plantillas tenía todos los roles que ese bloque necesitaba. "
              "No mezclo estilos de sets distintos.")
    if bloques_con_veto:
        detalle_veto = "; ".join(
            f"{rol}: sets {', '.join(str(n) for n in nums)}"
            for rol, nums in sorted(sets_sin_acentos.items()))
        print(f"  Tildes: en {bloques_con_veto} bloque(s) evité los sets "
              f"cuya tipografía no dibuja acentos ({detalle_veto}).")
    if veto_sin_salida:
        print(f"  Aviso: en {veto_sin_salida} bloque(s) NINGÚN set libre de "
              "ese veto tenía los roles necesarios; usé el que había — esa "
              "tilde puede salir con la fuente sustituida.")

    # Colocar CERO no es haber colocado.
    if colocados == 0:
        fail(f"no pude colocar ni una sola línea de '{lang}' (había "
             f"{len(cues)} bloques). Revisa que tus plantillas Text+ sigan "
             "en el Media Pool.")

    if colocados:
        _ALGO_COLOCADO[0] = True
        _TOTAL[0] += colocados
    print(f"  Colocadas {colocados} líneas en las pistas "
          f"{lang.upper()}-CTX / -MAIN / -CMP.")
    print("  Las líneas van apareciendo una tras otra, siguiendo el audio.")
    if len(uso_por_variante) > 1:
        detalle = ", ".join(f"variante {v+1}: {c} bloques"
                            for v, c in sorted(uso_por_variante.items()))
        print(f"  Rotación de estilo confirmada — {detalle}.")
        if repetidos_seguidos:
            print(f"  Aviso: {repetidos_seguidos} vez/veces salió el mismo "
                  "set dos bloques seguidos (por el veto de tildes o por "
                  "roles que faltan en el set que tocaba).")
        else:
            print("  Ningún set se usó dos bloques seguidos.")
    elif modo_plantillas and len(sets) == 1:
        print("  Solo hay 1 set de plantillas (arriba/principal/abajo), "
              "por eso no rota. Crea 'arriba 2', 'principal 2', "
              "'abajo 2'... para que alterne (con los nombres nuevos, hasta "
              f"{MAX_VARIANTES}; con los de siempre, hasta {MAX_SETS}).")
    if con_arial:
        print(f"  Tipografías: {con_arial} línea(s) salieron en Arial "
              "porque a este equipo le falta la del clip (instálala desde "
              "el programa para ver el diseño original).")
    if pack:
        if con_pack:
            print(f"  Pack '{pack['nombre']}': {con_pack} de {colocados} "
                  "líneas con el diseño completo.")
        else:
            print(f"  Aviso: el pack '{pack['nombre']}' entró solo con sus "
                  "valores (fuente, tamaño, color). Los degradados, formas y "
                  f"fondos NO. Motivo: {_PACK_MOTIVO or 'no encontré los .setting'}.")

    # Tres finales distintos, porque son tres cosas distintas y hasta la
    # v1.0.24 las tres se contaban como la misma (y encima la primera se daba
    # por buena sin comprobar nada).
    if con_entrada:
        print(f"  Entrada con fundido en {con_entrada} de {colocados}.")
    if con_fundido:
        print(f"  Fundido de salida aplicado en {con_fundido} de {con_hold} "
              f"(vía: {_FADE_MOTIVO}).")
    elif colocados and not con_hold:
        print("  Sin fundido: ningún bloque tenía tiempo de sobra detrás del "
              "habla. Es lo correcto, van pegados y cortan limpio.")
    elif colocados:
        print(f"  Aviso: no pude aplicar el fundido en {con_hold} bloques que "
              f"sí tenían sitio. Motivo: {_FADE_MOTIVO}. Los subtítulos "
              "funcionan igual, solo cortan seco.")
    if sin_texto:
        print(f"  Aviso: {sin_texto} clips quedaron colocados pero sin texto "
              "automático (escríbelos a mano con doble clic).")
    informe_transformaciones()
    informe_composicion()
    colocar_emojis(timeline, media_pool, track_info, planes_emoji, fps)
    if fallos_estilo:
        print(f"  Aviso: no pude aplicar {', '.join(sorted(fallos_estilo))} "
              "por script. Los textos están bien, solo ajusta el diseño a mano "
              "(o crea las 3 plantillas para tener control total).")


# --------------------------------------------------------------------------
# Los emojis (v3.3.0; el porque completo esta en el gemelo .lua)
# --------------------------------------------------------------------------
EMOJI_ALTO = {"v": 0.085, "h": 0.13}
EMOJI_MARGEN = {"v": 0.065, "h": 0.10}
# v3.3.1: al final de su linea, el lado es el alto de la letra por este
# factor (la perilla; ver el gemelo .lua) y el hueco, 0.3 lados.
FACTOR_EMOJI_LINEA = 1.15
HUECO_EMOJI_LINEA = 0.3


def _importar_emoji(media_pool, ruta):
    """El PNG del emoji en el Media Pool: la MISMA ruta se reusa, otro clip
    con el mismo nombre no (la leccion de los SFX desconectados)."""
    buscada = os.path.normcase(os.path.normpath(str(ruta)))

    def buscar(carpeta):
        for clip in carpeta.GetClipList() or []:
            try:
                r = clip.GetClipProperty("File Path") or ""
            except Exception:
                continue
            if r and os.path.normcase(os.path.normpath(r)) == buscada:
                return clip
        for sub in carpeta.GetSubFolderList() or []:
            x = buscar(sub)
            if x is not None:
                return x
        return None

    try:
        ya = buscar(media_pool.GetRootFolder())
        if ya is not None:
            return ya
    except Exception:
        pass
    previa = None
    try:
        previa = media_pool.GetCurrentFolder()
        media_pool.SetCurrentFolder(media_pool.GetRootFolder())
    except Exception:
        pass
    try:
        nuevos = media_pool.ImportMedia([str(ruta)])
    except Exception:
        nuevos = None
    if previa is not None:
        try:
            media_pool.SetCurrentFolder(previa)
        except Exception:
            pass
    return nuevos[0] if nuevos else None


def _importar_secuencia(media_pool, datos):
    """La secuencia de PNG de un emoji animado como UN clip del Media Pool (se reusa si ya esta)."""
    try:
        patron, n = str(datos["patron"]), int(datos["n"])
    except (KeyError, TypeError, ValueError):
        return None
    buscada = os.path.normcase(os.path.normpath(patron.replace("%04d", "[0001-%04d]" % n)))

    def buscar(carpeta):
        for clip in carpeta.GetClipList() or []:
            try:
                r = clip.GetClipProperty("File Path") or ""
            except Exception:
                continue
            if r and os.path.normcase(os.path.normpath(r)) == buscada:
                return clip
        for sub in carpeta.GetSubFolderList() or []:
            x = buscar(sub)
            if x is not None:
                return x
        return None

    try:
        ya = buscar(media_pool.GetRootFolder())
        if ya is not None:
            return ya
    except Exception:
        pass
    previa = None
    try:
        previa = media_pool.GetCurrentFolder()
        media_pool.SetCurrentFolder(media_pool.GetRootFolder())
    except Exception:
        pass
    try:
        nuevos = media_pool.ImportMedia([{"FilePath": patron, "StartIndex": 1, "EndIndex": n}])
    except Exception:
        nuevos = None
    if previa is not None:
        try:
            media_pool.SetCurrentFolder(previa)
        except Exception:
            pass
    return nuevos[0] if nuevos else None


def _comp_animacion_emoji(largo, entrada, salida):
    """Texto de la comp de Fusion que le da al emoji su ENTRADA (rebote de 8 fotogramas) y/o su SALIDA (6 fotogramas)."""
    t = "(math.min(1,math.max(0,time/8))-1)"
    pop = "(1+2.70158*%s^3+1.70158*%s^2)" % (t, t) if entrada else "1"
    fuera = "math.max(0,math.min(1,(%d-time)/6))" % largo if salida else "1"
    expr = "math.max(0.001,%s*%s)" % (pop, fuera)
    return ("Composition {\n\tCurrentTime = 0,\n\tRenderRange = { 0, %d },\n\tGlobalRange = { 0, %d },\n\tTools = ordered() {\n"
            "\t\tTransform1 = Transform {\n\t\t\tInputs = {\n\t\t\t\tSize = Input { Value = 1, Expression = \"%s\", },\n"
            "\t\t\t\tInput = Input { SourceOp = \"MediaIn1\", Source = \"Output\", },\n\t\t\t},\n"
            "\t\t\tViewInfo = OperatorInfo { Pos = { 200, 50 } },\n\t\t},\n"
            "\t\tMediaIn1 = MediaIn {\n\t\t\tViewInfo = OperatorInfo { Pos = { 0, 50 } },\n\t\t},\n"
            "\t\tMediaOut1 = MediaOut {\n\t\t\tInputs = {\n\t\t\t\tIndex = Input { Value = \"0\", },\n"
            "\t\t\t\tInput = Input { SourceOp = \"Transform1\", Source = \"Output\", },\n\t\t\t},\n"
            "\t\t\tViewInfo = OperatorInfo { Pos = { 400, 50 } },\n\t\t},\n\t},\n}\n") % (largo, largo, expr)


def _animar_emoji(colocado, largo, entrada, salida):
    """Le pone al clip del emoji su comp de entrada/salida. Si Resolve no la acepta, el emoji sigue ahi (sin rebote)."""
    try:
        import tempfile
        ruta = os.path.join(tempfile.gettempdir(), "cinecaptions_emoji_%d_%d%d.comp" % (largo, int(entrada), int(salida)))
        if not os.path.isfile(ruta):          # la comp depende solo de (largo, entrada, salida): se escribe una vez
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(_comp_animacion_emoji(largo, entrada, salida))
        return bool(colocado.ImportFusionComp(ruta))
    except Exception:
        return False


def colocar_emojis(timeline, media_pool, track_info, planes, fps):
    L = str(track_info.get("language") or "??").upper()
    rutas = track_info.get("emojis") or {}
    if not isinstance(rutas, dict):
        rutas = {}
    secuencias = track_info.get("emojis_secuencias") or {}
    if not isinstance(secuencias, dict):
        secuencias = {}
    animados = 0
    con = [p for p in planes or []
           if p.get("emoji") in rutas and p["fin"] > p["ini"]]
    if not con:
        # Sin emojis esta vez: fuera los de una corrida anterior.
        _retirar_pistas_nuestras(timeline, [f"{L}-EMOJI"], "emojis",
                                 "esta corrida no lleva emojis")
        return 0
    idx, error = _conseguir_pista_video(timeline, f"{L}-EMOJI")
    if error:
        print(f"  Aviso: no pude crear la pista de emojis de forma segura "
              f"({error}): los subtítulos van sin emojis.")
        return 0
    try:
        ancho = int(float(timeline.GetSetting("timelineResolutionWidth")))
        alto = int(float(timeline.GetSetting("timelineResolutionHeight")))
    except Exception:
        ancho, alto = 1920, 1080
    f = "v" if alto > ancho else "h"
    # v5.3: 'abajo' (por defecto: debajo de las lineas, o en el bloque 'imagen' del pack), 'arriba'
    # o 'linea' (al final de su linea, como en la v3.3.1).
    modo = str(track_info.get("emoji_posicion") or "abajo")
    arriba = modo == "arriba"
    razon = alto / ancho
    ajustar = getattr(resolve, "SCALE_FIT", 2) if "resolve" in globals() else 2
    items, puestos, sin_poner, sin_mover = {}, 0, 0, 0
    junto = encima = en_slot = 0
    for p in con:
        if p["emoji"] not in items:
            item = _importar_secuencia(media_pool, secuencias[p["emoji"]]) if p["emoji"] in secuencias else None
            if item is None:
                item = _importar_emoji(media_pool, rutas[p["emoji"]])
            items[p["emoji"]] = item
            if item is not None:
                # Un PNG no calibra nada: el factor y el fotograma final ya
                # los aprendio el texto.
                n = _nombre_clip(item)
                _FACTORES[n] = 1.0
                _CALIBRADOS.add(n)
        item = items[p["emoji"]]
        colocado = None
        trozos = []
        if item is not None:
            largo_plan = p["fin"] - p["ini"]
            sec = secuencias.get(p["emoji"])
            es_secuencia = False
            try:
                es_secuencia = bool(sec) and "[" in str(item.GetClipProperty("File Path") or "")
            except Exception:
                es_secuencia = False
            if es_secuencia:
                # secuencia animada: se repite (en bucle) hasta cubrir el bloque; la entrada va en el 1.o y la salida en el ultimo
                cuadros = max(2, int(sec.get("n") or 2))
                pos = 0
                while pos < largo_plan:
                    seg = min(cuadros, largo_plan - pos)
                    c, _ = colocar_medido(media_pool, timeline, item, 0, seg, idx, p["ini"] + pos, fps, color=COLOR_EMOJI)
                    if c is None:
                        break
                    trozos.append((c, seg))
                    pos += seg
                if trozos:
                    colocado = trozos[0][0]
            else:
                colocado, _ = colocar_medido(media_pool, timeline, item, 0,
                                             p["fin"] - p["ini"], idx, p["ini"],
                                             fps, color=COLOR_EMOJI)
                if colocado is not None:
                    trozos = [(colocado, largo_plan)]
        if colocado is None:
            sin_poner += 1
            continue
        # v5.3: el bloque 'imagen' del pack manda (posicion y tamano); sin el, DEBAJO de las
        # lineas, centrado. 'linea' = al final de su linea (v3.3.1), 'arriba' = encima del bloque.
        lado, y, cx = EMOJI_ALTO[f], None, 0.5
        slot = p.get("slot")
        if slot and not track_info.get("emoji_forzar"):      # el usuario eligio Abajo/Arriba: manda su eleccion
            try:
                lado = max(0.03, min(0.5, EMOJI_ALTO[f] * float(slot[2])))
                cx = 0.5 + float(slot[0])
                y = float(slot[1])
                en_slot += 1
            except (TypeError, ValueError, IndexError):
                lado, y, cx = EMOJI_ALTO[f], None, 0.5
        if y is None and modo == "linea":
            par = None
            medidas = p.get("medidas")
            if isinstance(medidas, dict) and isinstance(medidas.get(f), dict):
                m = medidas[f]
                par = (m.get(str(p.get("numero"))) if p.get("numero") is not None
                       else None) or m.get("*")
            try:
                ancho_em, alto_em = float(par[0]), float(par[1])
            except (TypeError, ValueError, IndexError):
                ancho_em = alto_em = None
            if ancho_em is not None and alto_em is not None:
                zx = float(p.get("zx") or 1.0)
                lado_l = max(0.04, min(EMOJI_ALTO[f],
                                       alto_em * zx * FACTOR_EMOJI_LINEA))
                borde = 0.5 + float(p.get("x") or 0.0) + (ancho_em * zx * razon) / 2
                cx_l = borde + (HUECO_EMOJI_LINEA * lado_l + lado_l / 2) * razon
                if cx_l + (lado_l * razon) / 2 <= 0.99:
                    lado, cx, y = lado_l, cx_l, float(p.get("y") or 0.0)
                    junto += 1
        if y is None:
            if arriba:
                y = (p["y_arriba"] or 0.0) + EMOJI_MARGEN[f] + lado / 2
            else:
                y = (p["y_abajo"] or 0.0) - EMOJI_MARGEN[f] - lado / 2
            encima += 1
        tope = 0.5 - lado / 2 - 0.01
        y = max(-tope, min(tope, y))
        zoom = lado * alto / min(ancho, alto)
        bien = True
        for k_t, (c_t, largo_t) in enumerate(trozos):
            _poner_props(c_t, {"Scaling": ajustar})
            if not _poner_props(c_t, {
                    "ZoomX": zoom, "ZoomY": zoom,
                    "Pan": _pan_px(cx - 0.5 + float(p.get("dx_n") or 0.0), ancho),
                    "Tilt": _tilt_px(y + float(p.get("dy_n") or 0.0), alto)}):
                bien = False
            # entrada (rebote) en el primero y salida en el ultimo: el icono no aparece ni desaparece de golpe
            if _animar_emoji(c_t, max(2, int(largo_t)), k_t == 0, k_t == len(trozos) - 1):
                animados += 1
        if bien:
            puestos += 1
        else:
            sin_mover += 1
    print(f"  Emojis: {puestos} de {len(con)} en la pista '{L}-EMOJI' "
          f"({en_slot} en el bloque 'imagen', {junto} al final de su línea, "
          f"{encima} {'encima' if arriba else 'debajo'} del bloque).")
    if animados:
        print(f"  Emojis con animación: {animados} clip(s) con entrada y salida (los animados de Google, en bucle).")
    if sin_mover:
        print(f"  Aviso: {sin_mover} emoji(s) quedaron sin tamaño ni "
              "posición (tu Resolve no aceptó SetProperty): quedan en el "
              "centro, muévelos a mano.")
    if sin_poner:
        print(f"  Aviso: {sin_poner} emoji(s) no se pudieron colocar (no "
              "pude importar su PNG).")
    return puestos


# --------------------------------------------------------------------------
# Modo destacados
# --------------------------------------------------------------------------

def _conseguir_pista_video(timeline, nombre_deseado):
    """Una pista de video lista para usar: la reutiliza (limpiandola de sus
    clips previos) si ya existe y es nuestra, la crea si no. Mismo criterio
    que el bucle de DYNAMIC_ORDER en place_dynamic_track -aca separado
    porque el modo destacados no tiene un numero fijo de pistas (depende del
    look y, en 'pintado', de cuantas palabras tenga el bloque mas largo)-.

    Devuelve (indice, error). Si hay contenido ajeno en una pista con ese
    nombre, se la deja intacta y se crea otra encima: no se aborta ni se
    sobrescribe (ver crear_pista_verificada en CLAUDE.md).
    """
    ocupada_por_el_usuario = 0
    for t in range(1, timeline.GetTrackCount("video") + 1):
        if timeline.GetTrackName("video", t).strip().upper() != nombre_deseado.upper():
            continue
        if _pista_video_reutilizable(timeline, t):
            borrados = _limpiar_pista(timeline, "video", t)
            if borrados:
                print(f"  Pista existente '{nombre_deseado}' limpiada "
                      f"({borrados} clips previos borrados).")
            return t, None
        ocupada_por_el_usuario += 1

    if ocupada_por_el_usuario:
        print(f"  La pista '{nombre_deseado}' tiene contenido tuyo: la dejo "
              "intacta y creo una nueva encima.")

    return _crear_pista_verificada(timeline, "video", nombre_deseado)


def _retirar_pistas_nuestras(timeline, nombres, que, motivo):
    """Vacia TODAS las pistas de video con esos nombres que sean solo
    nuestras (v2.0.2, pedido literal: «si pusimos dinamicos, solo
    dinamicos y viceversa»). Generar en un modo dejaba delante los
    subtitulos del otro (la rama SRT ademas apilaba una pista LANG nueva
    por corrida): la dinamica retira la pista LANG y la SRT retira
    LANG-CTX/-MAIN/-CMP y las LANG sobrantes. Una pista con un clip que
    no es Text+ se deja intacta, como siempre; se dice cuantas y por que.
    """
    pistas, clips = 0, 0
    for nombre in nombres:
        try:
            cantidad = timeline.GetTrackCount("video")
        except Exception:
            return 0
        for t in range(1, cantidad + 1):
            try:
                actual = (timeline.GetTrackName("video", t) or "").strip()
            except Exception:
                continue
            if actual.upper() != nombre.upper():
                continue
            if not _pista_video_reutilizable(timeline, t):
                continue
            borrados = _limpiar_pista(timeline, "video", t)
            if borrados:
                pistas += 1
                clips += borrados
    if clips:
        print(f"  Retiré {clips} {que} anteriores ({pistas} pista(s)): "
              f"{motivo}.")
    return clips


def _colocar_texto(media_pool, plantilla, pista, inicio_frame, fin_frame,
                   texto, estilo, x, y):
    """Coloca un Text+ y le aplica texto + estilo. Devuelve el 'item' del
    timeline colocado, o None si algo fallo (y ya avisa por que)."""
    duracion = max(1, fin_frame - inicio_frame)
    # Sin timeline a mano no se mide: se aplica el ajuste ya aprendido.
    item, _ = colocar_medido(media_pool, None, plantilla, 0, duracion,
                             pista, inicio_frame, color=COLOR_TEXTO)
    if item is None:
        return None, "no pude colocar el clip"
    tool = get_text_plus_tool(item)
    if tool is None:
        return item, "sin Text+ dentro del clip"
    if not set_input_safe(tool, "StyledText", texto):
        return item, "no pude escribir el texto"
    apply_auto_style(tool, estilo, y)
    if x is not None:
        set_center_safe(tool, x, y)
    return item, None


def _colocar_grupos(timeline, media_pool, lang, cues, look, base_template,
                    fps, timeline_start_frame, fade_frames,
                    estilos_look=None, ancla=None):
    """Los looks de un Text+ por bloque: hormozi, gadzhi, acumulativo.

    A diferencia del motor de 3 lineas, aca los bloques nunca se superponen
    en el tiempo -cada uno es una sola linea-, asi que basta con UNA pista.

    'estilos_look' y 'ancla' (v1.0.51) llegan del Diseño dinamico cuando el
    manifiesto los trae: el look conserva los colores/tipografia del preset
    elegido y la altura del deslizador, en vez de las constantes de fabrica.
    """
    estilos = estilos_look or DESTACADOS_ESTILOS[look]
    y = ANCLA_Y if ancla is None else ancla
    idx, error = _conseguir_pista_video(timeline, f"{lang.upper()}-DEST")
    if error:
        fail(f"no pude preparar la pista de '{lang}' de forma segura "
             f"({error}). No coloqué nada.")

    colocados, sin_texto, con_fundido, con_hold = 0, 0, 0, 0
    for i, cue in enumerate(cues):
        linea = (cue.get("lines") or [{}])[0]
        texto = (linea.get("text") or "").strip()
        if not texto:
            continue
        rol = linea.get("role", "normal")
        estilo = estilos.get(rol) or estilos.get("normal") or {}

        inicio_frame = timeline_start_frame + a_fotogramas(cue["start"], fps)
        fin_frame = timeline_start_frame + a_fotogramas(cue["end"], fps)
        if i + 1 < len(cues):
            ini_siguiente = timeline_start_frame + a_fotogramas(
                cues[i + 1]["start"], fps)
            if fin_frame > ini_siguiente:
                fin_frame = ini_siguiente
        duracion = max(1, fin_frame - inicio_frame)

        item, motivo = _colocar_texto(media_pool, base_template, idx,
                                      inicio_frame, fin_frame, texto, estilo,
                                      0.5, y)
        if item is None:
            print(f"  Aviso: {motivo} en {cue['start']:.2f}s")
            continue
        if motivo:
            sin_texto += 1
            continue

        fin_hablado_frame = timeline_start_frame + a_fotogramas(
            float(cue.get("fin_hablado", cue["end"])), fps)
        hold = fin_frame - fin_hablado_frame
        fade = min(fade_frames, max(0, hold), duracion - 1)
        if fade >= 1:
            con_hold += 1
            if apply_fade_out(item, fade):
                con_fundido += 1

        colocados += 1

    return colocados, sin_texto, con_fundido, con_hold


def _colocar_pintado(timeline, media_pool, lang, cues, base_template, fps,
                     timeline_start_frame, estilo_pintado, fade_frames,
                     razon_aspecto, colores=None, ancla=None):
    """El look 'pintado': cada palabra en su propio Text+, dos veces.

    Una copia "muda" (color tenue) cubre TODA la duracion de la frase, para
    que se pueda leer adelantado. Encima, una copia "dicha" (blanca, o
    dorada si la palabra estaba marcada) empieza justo cuando esa palabra se
    dice y dura hasta el final de la frase. Como las dos ocupan el MISMO
    lugar en pantalla, la de encima tapa a la de abajo en cuanto arranca: es
    el efecto de "se va pintando". No hace falta ningun fotograma clave -la
    unica tecnica que se sabe que funciona en cualquier Resolve es colocar
    clips en el tiempo, que es justo lo que esto hace-.

    Necesita DOS pistas por cada posicion de palabra dentro de un bloque
    (word[0], word[1], ...), reutilizadas entre bloques -igual que las 3
    pistas de contexto/principal/complemento se reutilizan para todos los
    bloques del video-. Solo se crean las que hagan falta para el bloque mas
    largo de este idioma, nunca las 9 posibles de entrada.

    'razon_aspecto' es alto/ancho del timeline REAL. Los anchos que trae
    cada palabra ('ancho_em') viajan como fraccion de la ALTURA -la app
    nunca ve la resolucion del timeline, igual que nunca ve el fps-, asi que
    ACA es donde se convierten a fraccion del ANCHO (la unidad que usa
    'Center'), multiplicando por esta razon.

    Las frases se ENVUELVEN en filas (v1.0.51): con el ancho real de cada
    palabra ya convertido, las que no caben en ANCHO_MAX_PINTADO bajan a la
    fila siguiente, y las filas se centran verticalmente alrededor del
    ancla. Es lo que hace al look usable en 9:16 — antes toda la frase iba
    en una sola fila y se salia del cuadro por los dos lados.

    'colores' {muda, dicha, clave} y 'ancla' llegan del Diseño dinamico
    cuando el manifiesto los trae (el dorado editable del preset); sin
    ellos, las constantes de fabrica de siempre.
    """
    maximo = min(MAX_PALABRAS_PINTADO,
                max((len(c.get("palabras") or []) for c in cues), default=0))
    if maximo == 0:
        return 0, 0, 0, 0

    colores = colores or {}
    color_muda = tuple(colores.get("muda") or COLOR_PINTADO_MUDA)
    color_dicha = tuple(colores.get("dicha") or COLOR_PINTADO_DICHA)
    color_clave = tuple(colores.get("clave") or COLOR_PINTADO_DICHA_CLAVE)
    y_ancla = ANCLA_Y if ancla is None else ancla

    pistas_muda, pistas_dicha = [], []
    for n in range(1, maximo + 1):
        idx_m, error = _conseguir_pista_video(
            timeline, f"{lang.upper()}-PINT{n}-MUDA")
        if error:
            fail(f"no pude preparar la pista de pintado de '{lang}' "
                 f"(palabra {n}, muda): {error}. No coloqué nada.")
        pistas_muda.append(idx_m)
    for n in range(1, maximo + 1):
        idx_d, error = _conseguir_pista_video(
            timeline, f"{lang.upper()}-PINT{n}-DICHA")
        if error:
            fail(f"no pude preparar la pista de pintado de '{lang}' "
                 f"(palabra {n}, dicha): {error}. No coloqué nada.")
        pistas_dicha.append(idx_d)

    estilo_muda = dict(estilo_pintado, color=color_muda)

    colocados, sin_texto = 0, 0
    for i_cue, cue in enumerate(cues):
        palabras = cue.get("palabras") or []
        if not palabras:
            continue
        fin_frame = timeline_start_frame + a_fotogramas(cue["end"], fps)
        if i_cue + 1 < len(cues):
            ini_siguiente = timeline_start_frame + a_fotogramas(
                cues[i_cue + 1]["start"], fps)
            if fin_frame > ini_siguiente:
                fin_frame = ini_siguiente

        # Convertir 'ancho_em' (fraccion de ALTURA) a fraccion de ANCHO. Se
        # hace ACA, por bloque, porque cada frase tiene su propio ancho.
        anchos_ancho = [float(p.get("ancho_em", 0.0)) * razon_aspecto
                        for p in palabras]
        espacio_ancho = float(cue.get("espacio_em", 0.0)) * razon_aspecto

        # Envolver en filas: las palabras que no caben bajan de fila. Una
        # fila jamas queda vacia (la palabra que abre fila entra aunque sola
        # ya se pase del maximo).
        filas = []
        fila_actual = []
        ancho_fila = 0.0
        for n, ancho in enumerate(anchos_ancho):
            extra = ancho if not fila_actual else ancho + espacio_ancho
            if fila_actual and ancho_fila + extra > ANCHO_MAX_PINTADO:
                filas.append(fila_actual)
                fila_actual = [n]
                ancho_fila = ancho
            else:
                fila_actual.append(n)
                ancho_fila += extra
        if fila_actual:
            filas.append(fila_actual)

        # La posicion de cada palabra: su fila centrada en X, y las filas
        # centradas en Y alrededor del ancla (la primera fila arriba — en
        # Fusion la Y crece hacia ARRIBA, la trampa de siempre).
        interlinea = (float(estilo_pintado.get("size") or 0.07)
                      * INTERLINEA_PINTADO)
        n_filas = len(filas)
        x_de, y_de = {}, {}
        for i_fila, fila in enumerate(filas):
            ancho_total = (sum(anchos_ancho[j] for j in fila)
                           + espacio_ancho * (len(fila) - 1))
            x_cursor = 0.5 - ancho_total / 2
            y_fila = y_ancla + (n_filas - 1 - 2 * i_fila) * interlinea / 2
            for j in fila:
                x_de[j] = x_cursor + anchos_ancho[j] / 2
                y_de[j] = y_fila
                x_cursor += anchos_ancho[j] + espacio_ancho

        for n, palabra in enumerate(palabras):
            texto = (palabra.get("texto") or "").strip()
            if not texto:
                continue
            x, y = x_de[n], y_de[n]

            # La copia "muda": desde que arranca la FRASE.
            inicio_frase = timeline_start_frame + a_fotogramas(cue["start"], fps)
            item, motivo = _colocar_texto(
                media_pool, base_template, pistas_muda[n], inicio_frase,
                fin_frame, texto, estilo_muda, x, y)
            if item is None:
                print(f"  Aviso: {motivo} en {cue['start']:.2f}s ('{texto}')")
            elif motivo:
                sin_texto += 1
            else:
                colocados += 1

            # La copia "dicha": desde que se dice ESA palabra.
            inicio_palabra = timeline_start_frame + a_fotogramas(
                float(palabra.get("start", cue["start"])), fps)
            inicio_palabra = max(inicio_frase, min(inicio_palabra,
                                                    fin_frame - 1))
            color = (color_clave if palabra.get("resaltada")
                     else color_dicha)
            estilo_dicha = dict(estilo_pintado, color=color)
            item, motivo = _colocar_texto(
                media_pool, base_template, pistas_dicha[n], inicio_palabra,
                fin_frame, texto, estilo_dicha, x, y)
            if item is None:
                print(f"  Aviso: {motivo} en {cue['start']:.2f}s ('{texto}')")
            elif motivo:
                sin_texto += 1
            else:
                colocados += 1

    return colocados, sin_texto, 0, 0


# --------------------------------------------------------------------------
# Pintado v3 (v1.0.53): TODOS los clips son Text+ de UNA linea colocados
# por MEDIDAS — centro = borde izquierdo de la fila + offset medido en la
# app (x_antes_em / ancho_em, con el MISMO estilo del texto). Cero
# propiedades de layout de Fusion: la v1.0.52 verifico
# HorizontalJustificationNew leyendo un 0 que resulto ser el DEFAULT
# (centrado), y todo salio corrido — un enum no se verifica leyendo el
# valor que ya tenia. Posicionar con numeros propios es lo unico que no
# puede mentir.
# --------------------------------------------------------------------------


def _retirar_pistas_pintado_viejas(timeline, lang):
    """Barre las pistas del pintado v1 (ES-PINTn-MUDA/DICHA: hasta 18 por
    idioma — el 'demasiadas capas' del reporte). Solo pistas NUESTRAS
    (nombre del patron y contenido reutilizable); se limpian y se intenta
    DeleteTrack — API nunca usada antes en este producto, asi que va bajo
    try y VERIFICANDO que el conteo baje. Si no se puede borrar, quedan
    vacias y se dice. Contenido ajeno: intacto (nunca destruir).

    Las pistas del propio v3 (-PINT-BASE/BASE2/PINTA/CLAVE) que esta
    corrida no vaya a reutilizar solo se LIMPIAN: dejar los clips de la
    corrida anterior en una capa que ya no se escribe duplicaria texto en
    pantalla."""
    import re as _re
    patron = _re.compile(
        rf"^{_re.escape(lang.upper())}-PINT\d+-(MUDA|DICHA)$")
    fijas = {f"{lang.upper()}-PINT-{s}"
             for s in ("BASE", "BASE2", "PINTA", "CLAVE")}
    borradas, vaciadas, ajenas = 0, 0, 0
    for idx in range(timeline.GetTrackCount("video"), 0, -1):
        try:
            nombre = (timeline.GetTrackName("video", idx) or "").strip()
        except Exception:
            continue
        if nombre.upper() in fijas:
            if _pista_video_reutilizable(timeline, idx):
                _limpiar_pista(timeline, "video", idx)
            continue
        if not patron.match(nombre.upper()):
            continue
        if not _pista_video_reutilizable(timeline, idx):
            ajenas += 1
            continue
        _limpiar_pista(timeline, "video", idx)
        antes = timeline.GetTrackCount("video")
        ok = False
        try:
            ok = bool(timeline.DeleteTrack("video", idx))
        except Exception:
            ok = False
        if ok and timeline.GetTrackCount("video") < antes:
            borradas += 1
        else:
            vaciadas += 1
    if borradas or vaciadas or ajenas:
        partes = []
        if borradas:
            partes.append(f"{borradas} borradas")
        if vaciadas:
            partes.append(f"{vaciadas} vaciadas (este Resolve no borra "
                          "pistas por script)")
        if ajenas:
            partes.append(f"{ajenas} con contenido tuyo, intactas")
        print("  Pistas del pintado anterior: " + ", ".join(partes) + ".")


def _colocar_pintado_v2(timeline, media_pool, lang, cues, base_template,
                        fps, timeline_start_frame, cfg, razon_aspecto,
                        ancla):
    """El pintado v3: capas de UNA linea, posicionadas por medidas.

    - modo 'acumula' (Hormozi, 1 fila por pantalla): BASE = la fila tenue
      centrada; PINTA = el prefijo dicho de la fila, un clip por palabra
      (consecutivos), con el CENTRO en izq + ancho_prefijo/2 — el borde
      izquierdo coincide EXACTO con el de la base y lo pintado tapa lo
      tenue letra a letra; CLAVE = la palabra marcada (dorada, contorno),
      persistente hasta el fin de la frase.
    - modo 'viaja' (Gadzhi, 2 filas): BASE y BASE2 = una fila por pista,
      centradas, texto visible; PINTA = la palabra actual en Bold sobre su
      gemela (la resaltada ademas con el color de main).

    Las Y son NUESTRAS (ancla +- interlinea/2, con interlinea = size *
    INTERLINEA_PINTADO): con clips de una linea no dependemos de como
    Fusion acomode nada. Tiene que dar lo mismo que el gemelo Lua (lupa).
    """
    estilo_base = dict(cfg.get("estilo_base") or ESTILO_PINTADO_RESPALDO)
    estilo_dicha = dict(cfg.get("estilo_dicha") or estilo_base)
    estilo_clave = dict(cfg.get("estilo_clave") or estilo_dicha)
    modo = cfg.get("modo") if cfg.get("modo") in ("acumula", "viaja") \
        else "acumula"
    y_ancla = ANCLA_Y if ancla is None else ancla
    interlinea = (float(estilo_base.get("size") or 0.06)
                  * INTERLINEA_PINTADO)

    _retirar_pistas_pintado_viejas(timeline, lang)

    max_filas = max((len(c.get("filas_texto") or []) for c in cues),
                    default=1)
    hay_clave = (modo == "acumula") and any(
        p.get("resaltada") for c in cues for p in (c.get("palabras") or []))

    idx_base, error = _conseguir_pista_video(
        timeline, f"{lang.upper()}-PINT-BASE")
    if error:
        fail(f"no pude preparar la pista base del pintado de '{lang}' "
             f"({error}). No coloqué nada.")
    idx_base2 = None
    if max_filas >= 2:
        idx_base2, error = _conseguir_pista_video(
            timeline, f"{lang.upper()}-PINT-BASE2")
        if error:
            fail(f"no pude preparar la segunda fila del pintado de "
                 f"'{lang}' ({error}). No coloqué nada.")
    idx_pinta, error = _conseguir_pista_video(
        timeline, f"{lang.upper()}-PINT-PINTA")
    if error:
        fail(f"no pude preparar la pista de pintado de '{lang}' "
             f"({error}). No coloqué nada.")
    idx_clave = None
    if hay_clave:
        idx_clave, error = _conseguir_pista_video(
            timeline, f"{lang.upper()}-PINT-CLAVE")
        if error:
            fail(f"no pude preparar la pista de claves de '{lang}' "
                 f"({error}). No coloqué nada.")

    colocados, sin_texto = 0, 0
    aviso_filas = False
    for i_cue, cue in enumerate(cues):
        palabras = cue.get("palabras") or []
        filas_texto = [str(t) for t in (cue.get("filas_texto") or [])]
        if not palabras or not filas_texto:
            continue
        if len(filas_texto) > 2:
            # Solo hay dos pistas de base: un manifiesto raro con mas
            # filas se acota (el armador de la app ya no las produce).
            if not aviso_filas:
                print("  Aviso: un bloque pintado trae mas de 2 filas; "
                      "coloco solo las dos primeras.")
                aviso_filas = True
            filas_texto = filas_texto[:2]
        n_filas = len(filas_texto)
        anchos_filas = [float(a or 0.0)
                        for a in (cue.get("ancho_filas_em") or [])]
        while len(anchos_filas) < n_filas:
            anchos_filas.append(0.0)
        # Borde izquierdo de cada fila (fraccion del ANCHO) y su altura.
        izq = [0.5 - (anchos_filas[r] * razon_aspecto) / 2.0
               for r in range(n_filas)]
        y_fila = [y_ancla + (n_filas - 1 - 2 * r) * interlinea / 2.0
                  for r in range(n_filas)]

        ini_frase = timeline_start_frame + a_fotogramas(cue["start"], fps)
        fin_frame = timeline_start_frame + a_fotogramas(cue["end"], fps)
        if i_cue + 1 < len(cues):
            ini_sig = timeline_start_frame + a_fotogramas(
                cues[i_cue + 1]["start"], fps)
            if fin_frame > ini_sig:
                fin_frame = ini_sig
        if fin_frame <= ini_frase:
            fin_frame = ini_frase + 1

        # LAS BASES: un clip de una linea por fila, centrado.
        pistas_base = (idx_base, idx_base2)
        for r in range(n_filas):
            item, motivo = _colocar_texto(
                media_pool, base_template, pistas_base[r], ini_frase,
                fin_frame, filas_texto[r], estilo_base, 0.5, y_fila[r])
            if item is None:
                print(f"  Aviso: {motivo} en {cue['start']:.2f}s (base)")
            elif motivo:
                sin_texto += 1
            else:
                colocados += 1

        # LA PINTA: un clip por palabra, consecutivos (sin solapes).
        for k, p in enumerate(palabras):
            texto_p = (p.get("texto") or "").strip()
            if not texto_p:
                continue
            fila = min(int(p.get("fila") or 0), n_filas - 1)
            ini_p = timeline_start_frame + a_fotogramas(
                float(p.get("start", cue["start"])), fps)
            ini_p = max(ini_frase, min(ini_p, fin_frame - 1))
            if k + 1 < len(palabras):
                fin_p = timeline_start_frame + a_fotogramas(
                    float(palabras[k + 1].get("start", cue["end"])), fps)
                fin_p = max(ini_p + 1, min(fin_p, fin_frame))
            else:
                fin_p = fin_frame
            x_antes = float(p.get("x_antes_em") or 0.0)
            ancho = float(p.get("ancho_em") or 0.0)
            if modo == "acumula":
                # El prefijo dicho de SU fila, con el borde izquierdo
                # clavado en el de la base: centro = izq + la mitad del
                # ancho MEDIDO del prefijo (x_antes + ancho).
                texto_clip = " ".join(
                    (palabras[i].get("texto") or "").strip()
                    for i in range(k + 1)
                    if min(int(palabras[i].get("fila") or 0),
                           n_filas - 1) == fila)
                x_clip = izq[fila] \
                    + ((x_antes + ancho) * razon_aspecto) / 2.0
                estilo_p = estilo_dicha
            else:
                texto_clip = texto_p
                x_clip = izq[fila] \
                    + (x_antes + ancho / 2.0) * razon_aspecto
                estilo_p = (estilo_clave if p.get("resaltada")
                            else estilo_dicha)
            item, motivo = _colocar_texto(
                media_pool, base_template, idx_pinta, ini_p, fin_p,
                texto_clip, estilo_p, x_clip, y_fila[fila])
            if item is None:
                print(f"  Aviso: {motivo} en {cue['start']:.2f}s "
                      f"('{texto_p}')")
            elif motivo:
                sin_texto += 1
            else:
                colocados += 1

        # LA CLAVE (solo 'acumula'): la palabra marcada, dorada, en su
        # sitio exacto, hasta el fin de la frase; una clave posterior
        # recorta a la anterior (una sola pista, sin solapes).
        if modo == "acumula" and idx_clave is not None:
            claves = [p for p in palabras if p.get("resaltada")]
            for j, p in enumerate(claves):
                texto_p = (p.get("texto") or "").strip()
                if not texto_p:
                    continue
                fila = min(int(p.get("fila") or 0), n_filas - 1)
                ini_c = timeline_start_frame + a_fotogramas(
                    float(p.get("start", cue["start"])), fps)
                ini_c = max(ini_frase, min(ini_c, fin_frame - 1))
                if j + 1 < len(claves):
                    fin_c = timeline_start_frame + a_fotogramas(
                        float(claves[j + 1].get("start", cue["end"])),
                        fps)
                    fin_c = max(ini_c + 1, min(fin_c, fin_frame))
                else:
                    fin_c = fin_frame
                x_c = (izq[fila]
                       + (float(p.get("x_antes_em") or 0.0)
                          + float(p.get("ancho_em") or 0.0) / 2.0)
                       * razon_aspecto)
                item, motivo = _colocar_texto(
                    media_pool, base_template, idx_clave, ini_c, fin_c,
                    texto_p, estilo_clave, x_c, y_fila[fila])
                if item is None:
                    print(f"  Aviso: {motivo} en {cue['start']:.2f}s "
                          f"('{texto_p}')")
                elif motivo:
                    sin_texto += 1
                else:
                    colocados += 1

    return colocados, sin_texto, 0, 0


def place_destacados_track(timeline, media_pool, track_info, base_template,
                           fps, timeline_start_frame):
    """El modo destacados: Hormozi, Gadzhi, acumulativo o pintado.

    A diferencia del modo dinamico (3 lineas), aca NO se respetan las
    plantillas del Media Pool del usuario: el estilo (mayusculas, contorno,
    tamaño) es parte del look, y los 11 sets de un pack no tienen donde
    encajar en un esquema de 1-2 estados por palabra. Es un modo mas
    automatico a proposito.
    """
    lang = track_info["language"]
    data_path = Path(track_info["data_path"])
    if not data_path.exists():
        print(f"  Aviso: no encuentro {data_path}, salto '{lang}'")
        return

    datos = json.loads(data_path.read_text(encoding="utf-8"))
    cues = datos.get("cues", [])
    if not cues:
        print(f"  Aviso: '{data_path.name}' no tiene bloques.")
        return

    look = datos.get("look", "hormozi")
    if look not in DESTACADOS_ESTILOS and look != "pintado":
        print(f"  Aviso: look '{look}' desconocido, uso 'hormozi'.")
        look = "hormozi"

    # El Diseño dinamico puede venir en la pista (v1.0.51, presets con
    # motor): el ancla del deslizador, el dorado editable del preset y —
    # para los looks de un Text+ por bloque— sus estilos {normal,
    # resaltada}. Sin ellos, las constantes de fabrica de siempre.
    diseno = track_info.get("diseno")
    ancla_dis = None
    if isinstance(diseno, dict):
        try:
            ancla_dis = float(diseno.get("ancla_y"))
        except (TypeError, ValueError):
            ancla_dis = None
        if diseno.get("preset"):
            print(f"  Diseño dinámico: preset '{diseno.get('preset')}' "
                  "(estilos y posición elegidos en el programa).")
    estilos_look = (datos.get("estilo_destacados")
                    if isinstance(datos.get("estilo_destacados"), dict)
                    else None)

    if not base_template:
        base_template = obtener_text_plus_base(timeline, media_pool)
    if not base_template:
        print(f"  Aviso: para '{lang}' no encontré ningún Text+ para usar y "
              "no pude crear uno automáticamente. Arrastra un Text+ "
              f"(Effects > Titles) al Media Pool y vuelve a generar.")
        return

    print(f"\nIdioma '{lang}': {len(cues)} bloques, modo destacados ({look})")

    fade_frames = a_fotogramas(FADE_OUT_SECONDS, fps)

    if look == "pintado":
        try:
            ancho_t = float(timeline.GetSetting("timelineResolutionWidth"))
            alto_t = float(timeline.GetSetting("timelineResolutionHeight"))
        except Exception:
            ancho_t, alto_t = 1920.0, 1080.0
        if ancho_t <= 0 or alto_t <= 0:
            ancho_t, alto_t = 1920.0, 1080.0
        razon_aspecto = alto_t / ancho_t
        cfg_v2 = datos.get("pintado")
        if (isinstance(cfg_v2, dict) and cues
                and cues[0].get("filas_texto")):
            # v2 (v1.0.52): filas por caracteres, 3 capas multilinea.
            colocados, sin_texto, con_fundido, con_hold = \
                _colocar_pintado_v2(
                    timeline, media_pool, lang, cues, base_template, fps,
                    timeline_start_frame, cfg_v2, razon_aspecto, ancla_dis)
        else:
            # v1 (manifiestos viejos): dos pistas por palabra.
            estilo_pintado = (datos.get("estilo_pintado")
                              or ESTILO_PINTADO_RESPALDO)
            if not datos.get("estilo_pintado"):
                print("  Aviso: el manifiesto no trae el estilo con el que "
                      "se midieron los anchos; uso un respaldo, las "
                      "palabras pueden no alinear perfecto.")
            colocados, sin_texto, con_fundido, con_hold = _colocar_pintado(
                timeline, media_pool, lang, cues, base_template, fps,
                timeline_start_frame, estilo_pintado, fade_frames,
                razon_aspecto, colores=datos.get("colores_pintado"),
                ancla=ancla_dis)
    else:
        colocados, sin_texto, con_fundido, con_hold = _colocar_grupos(
            timeline, media_pool, lang, cues, look, base_template, fps,
            timeline_start_frame, fade_frames,
            estilos_look=estilos_look, ancla=ancla_dis)

    if colocados == 0:
        fail(f"no pude colocar ni un bloque de '{lang}' (había {len(cues)}). "
             "Revisa que tengas un Text+ en el Media Pool.")

    if colocados:
        _ALGO_COLOCADO[0] = True
        _TOTAL[0] += colocados
    print(f"  Colocados {colocados} clips en modo destacados ({look}).")
    if con_fundido:
        print(f"  Fundido de salida en {con_fundido} de {con_hold}.")
    if sin_texto:
        print(f"  Aviso: {sin_texto} clips quedaron sin texto automático.")

    # Los efectos van en su propia pista, igual que en el modo dinamico
    # (v1.0.51): hasta aqui esta rama no los colocaba NUNCA — la app
    # mandaba las claves sfx_* del manifiesto y nadie las leia, o sea
    # efectos en silencio con la casilla puesta.
    if track_info.get("sfx_library") or track_info.get("sfx_archivos"):
        place_sfx_track(timeline, media_pool, cues, track_info, fps,
                        timeline_start_frame)


# --------------------------------------------------------------------------
# Efectos de sonido
# --------------------------------------------------------------------------

EXTENSIONES_SFX = (".wav", ".mp3", ".aif", ".aiff", ".m4a", ".flac", ".ogg")


def audios_de_categoria(carpeta_libreria, categoria, sfx_archivos=None):
    """Los archivos de audio de una categoria, ordenados. [] si no hay.

    Primero se mira lo que la app dejo escrito en el manifiesto
    ('sfx_archivos'), que trae las RUTAS COMPLETAS. Es el unico camino que
    funciona cuando los sonidos vienen de una carpeta del usuario o de sus
    favoritos: esos viven fuera de sfx_library y no hay forma de deducir
    donde estan a partir del nombre de la categoria.

    Recorrer la carpeta queda como respaldo, para manifiestos de versiones
    anteriores que no traen ese campo.
    """
    dados = (sfx_archivos or {}).get(categoria)
    if dados:
        rutas = [Path(r) for r in dados]
        existentes = [r for r in rutas if r.is_file()]
        if existentes:
            return sorted(existentes)
        print(f"  Aviso: el manifiesto lista {len(rutas)} sonidos de "
              f"'{categoria}' pero ninguno existe ya en disco. "
              "¿Se movió la carpeta?")

    carpeta = Path(carpeta_libreria) / categoria
    if not carpeta.is_dir():
        return []
    return sorted(a for a in carpeta.iterdir()
                  if a.is_file() and a.suffix.lower() in EXTENSIONES_SFX)


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



def place_sfx_track(timeline, media_pool, cues, track_info, fps,
                    timeline_start_frame):
    """Coloca un efecto de sonido en la palabra PRINCIPAL de cada bloque.

    El golpe suena cuando entra la palabra principal, no con la primera del
    bloque: el contexto entra antes (0,8 s de media, picos de 1,5 s en
    manifiestos reales) y el efecto sonando ahi parecia adelantado. Un
    bloque sin linea principal suena al inicio, como siempre.

    La categoria de cada bloque ya viene decidida en el JSON (la calcularon
    las reglas de sfx_rules.json). Aca solo se elige QUE archivo de esa
    categoria usar — rotando para no repetir el mismo dos veces seguidas — y
    se coloca en una pista de audio nueva.
    """
    libreria = track_info.get("sfx_library")
    sfx_archivos = track_info.get("sfx_archivos") or {}
    # Con las rutas en el manifiesto ya no hace falta que exista sfx_library:
    # los sonidos pueden venir enteros de una carpeta del usuario.
    if not sfx_archivos and (not libreria or not Path(libreria).is_dir()):
        print(f"\n  Aviso: no encuentro la carpeta de efectos "
              f"('{libreria}'). Salto los efectos de sonido.")
        return

    con_efecto = [c for c in cues if c.get("sfx")]
    if not con_efecto:
        return

    config = track_info.get("sfx_config") or {}
    nombre_pista = config.get("nombre_pista_audio") or "SFX"

    # El efecto se mueve CON su bloque. Si el bloque entra 6 fotogramas antes
    # y el sonido no, el golpe suena tarde y se nota mas que el propio
    # adelanto.
    #
    # Y se calcula igual que en place_dynamic_track, recorriendo TODOS los
    # cues en orden: si aqui se restara el adelanto a secas, en los casos en
    # que alli hubo que recortarlo (para no comerse el bloque anterior) el
    # sonido quedaria unos fotogramas antes que su propio subtitulo.
    adelanto = _adelanto_de(track_info)
    inicio_de_cue = {}
    ini_anterior = None
    for c in cues:
        ini = (timeline_start_frame + a_fotogramas(c["start"], fps)
               - (adelanto if _usa_set(c) else 0))
        ini = max(timeline_start_frame, ini)
        if ini_anterior is not None and ini <= ini_anterior:
            ini = ini_anterior + 1
        inicio_de_cue[id(c)] = ini
        ini_anterior = ini

    # Un solo import por archivo: importar el mismo wav 30 veces llenaria el
    # Media Pool de duplicados.
    importados = {}

    def item_de(ruta):
        clave = str(ruta)
        if clave in importados:
            return importados[clave]
        # ImportMedia deja el archivo en el CURRENT FOLDER, no en la raiz.
        # Si algo dejo el current apuntando al bin del pack, los efectos
        # aterrizan ahi dentro y la limpieza de ese bin se los lleva (clips
        # en rojo). Se fija la raiz a proposito y se devuelve como estaba.
        previa = None
        try:
            previa = media_pool.GetCurrentFolder()
            media_pool.SetCurrentFolder(media_pool.GetRootFolder())
        except Exception:
            previa = None
        try:
            nuevos = media_pool.ImportMedia([clave])
        except Exception:
            nuevos = None
        finally:
            if previa is not None:
                try:
                    media_pool.SetCurrentFolder(previa)
                except Exception:
                    pass
        item = nuevos[0] if nuevos else None
        importados[clave] = item
        return item

    # Cuantos bloques va a usar cada categoria, para repartir sus archivos
    # sin repetir seguidos (mismo criterio que los sets de plantillas).
    por_categoria = {}
    for cue in con_efecto:
        por_categoria.setdefault(cue["sfx"], []).append(cue)

    turnos = {}
    faltantes = []
    for categoria, lista in por_categoria.items():
        archivos = audios_de_categoria(libreria, categoria,
                                       sfx_archivos)
        if not archivos:
            faltantes.append(categoria)
            continue
        turnos[categoria] = {
            "archivos": archivos,
            "orden": orden_de_variantes(len(lista), len(archivos)),
            "siguiente": 0,
        }

    if not turnos and not any(c.get("sfx_archivo") for c in con_efecto):
        print(f"\n  Aviso: ninguna categoría de efectos tiene audios en "
              f"{libreria}.")
        return

    # (Aqui habia un segundo 'nombre_pista = config.get("nombre_pista",
    # "SFX")' que PISABA el valor bueno leido mas arriba. La app escribe la
    # clave 'nombre_pista_audio', nunca 'nombre_pista', asi que esta linea
    # devolvia siempre "SFX" por defecto: quien renombrara la pista en su
    # sfx_rules.json se encontraba los efectos en otra pista distinta de la
    # que habia pedido.)
    max_frames_sfx = a_fotogramas(DURACION_MAXIMA_SFX_SEGUNDOS, fps)

    # Igual que con las pistas de video: la primera con ese nombre que ADEMAS
    # sea reutilizable. Si el usuario dejo audio suyo en la pista 'SFX', se le
    # respeta y se crea otra, en vez de quedarse sin efectos.
    idx_sfx = None
    ocupadas_por_el_usuario = 0
    for t in range(1, timeline.GetTrackCount("audio") + 1):
        if timeline.GetTrackName("audio", t).strip().upper() != nombre_pista.upper():
            continue
        if _pista_audio_reutilizable(timeline, t, max_frames_sfx):
            idx_sfx = t
            break
        ocupadas_por_el_usuario += 1

    if idx_sfx is None:
        if ocupadas_por_el_usuario:
            print(f"  La pista '{nombre_pista}' tiene audio tuyo: la dejo "
                  "intacta y creo una nueva encima.")
        indice, error = _crear_pista_verificada(
            timeline, "audio", nombre_pista, args_extra=("stereo",))
        if error:
            # Reintento sin el argumento "stereo": algunas versiones de la
            # API no lo aceptan y devuelven False si se lo pasamos.
            indice, error = _crear_pista_verificada(timeline, "audio", nombre_pista)
        if error:
            print(f"\n  ERROR: no pude crear la pista de audio para los "
                  f"efectos de forma segura ({error}). No coloco ningún "
                  "efecto para no arriesgar tu timeline.")
            return
    else:
        indice = idx_sfx
        # Ya se comprobo al elegirla que esta pista es nuestra (vacia o con
        # puros efectos cortos).
        # La pista SFX ya existia: limpiamos los clips previos para no
        # solapar sonidos de una generacion anterior con los nuevos.
        borrados = _limpiar_pista(timeline, "audio", indice)
        if borrados:
            print(f"  Pista SFX existente limpiada ({borrados} clips "
                  "previos borrados).")

    # v5.4: los sonidos son POR PALABRA y pueden pisarse: cada uno va en la primera pista (SFX, SFX 2, SFX 3…) donde cabe
    # entero, sin recortarlo. Las pistas «SFX n» de una corrida anterior se limpian (si solo tienen efectos nuestros).
    pistas_extra_existentes = {}
    for t in range(1, timeline.GetTrackCount("audio") + 1):
        nombre_t = timeline.GetTrackName("audio", t).strip().upper()
        pref = nombre_pista.upper() + " "
        if t != indice and nombre_t.startswith(pref) and nombre_t[len(pref):].isdigit():
            if _pista_audio_reutilizable(timeline, t, max_frames_sfx):
                _limpiar_pista(timeline, "audio", t)
                pistas_extra_existentes[int(nombre_t[len(pref):])] = t

    def pista_sfx_extra(n):
        """El indice de la pista 'SFX n+1' (la reutiliza o la crea). None si no se pudo."""
        if (n + 1) in pistas_extra_existentes:
            return pistas_extra_existentes[n + 1]
        ind, err = _crear_pista_verificada(timeline, "audio", f"{nombre_pista} {n + 1}", args_extra=("stereo",))
        if err:
            ind, err = _crear_pista_verificada(timeline, "audio", f"{nombre_pista} {n + 1}")
        return None if err else ind

    print(f"\nEfectos de sonido: {len(con_efecto)} bloques con efecto "
          f"-> pista '{nombre_pista}'")

    colocados = 0
    uso = {}
    por_colocar = []
    for cue in con_efecto:
        # v5.4 (modo simple): un sonido por PALABRA; la app manda los eventos dentro del bloque ('sfx_eventos')
        if cue.get("sfx_eventos"):
            base_ini = inicio_de_cue.get(id(cue), timeline_start_frame + a_fotogramas(cue["start"], fps))
            for ev in cue["sfx_eventos"]:
                ruta_ev = ev.get("sfx_archivo")
                if not ruta_ev or not Path(ruta_ev).is_file():
                    continue
                item_ev = item_de(Path(ruta_ev))
                if not item_ev:
                    continue
                ini_ev = base_ini + max(0, a_fotogramas(float(ev.get("t", cue["start"])) - float(cue["start"]), fps))
                dur_ev = _frames_de_audio(item_ev, fps) or max(1, a_fotogramas(0.5, fps))
                por_colocar.append((ini_ev, item_ev, ev.get("sfx") or cue["sfx"], dur_ev))
            continue
        categoria = cue["sfx"]
        # v5.4: la app dice QUE archivo suena en cada bloque (el punto que se ve en el editor); sin el, se turnan los de la categoria
        directo = cue.get("sfx_archivo")
        if directo and Path(directo).is_file():
            archivo = Path(directo)
        else:
            turno = turnos.get(categoria)
            if not turno:
                continue
            archivo = turno["archivos"][turno["orden"][turno["siguiente"]]]
            turno["siguiente"] += 1

        item = item_de(archivo)
        if not item:
            continue

        inicio = inicio_de_cue.get(
            id(cue), timeline_start_frame + a_fotogramas(cue["start"], fps))
        # El mismo retardo que place_dynamic_track le aplica a la linea
        # 'main' (la resta EN DELTA, no restando dos a_fotogramas: la otra
        # forma redondea distinto y el golpe caeria un fotograma al lado del
        # texto). Se suma DESPUES del clamping de inicio_de_cue para no
        # desalinear el efecto de su propio bloque adelantado.
        retardo_main = 0
        for _linea in (cue.get("lines") or []):
            if _linea.get("role") == "main":
                try:
                    retardo_main = max(0, a_fotogramas(
                        float(_linea.get("start", cue["start"]))
                        - float(cue["start"]), fps))
                except (TypeError, ValueError):
                    retardo_main = 0
                break
        if not retardo_main:
            # Bloques 'pintado' (v1.0.51): el golpe visual es la primera
            # palabra resaltada — el MISMO instante que midio sfx_rules
            # (_tiempo_del_golpe) para la separacion minima entre efectos.
            for _p in (cue.get("palabras") or []):
                if _p.get("resaltada"):
                    try:
                        retardo_main = max(0, a_fotogramas(
                            float(_p.get("start", cue["start"]))
                            - float(cue["start"]), fps))
                    except (TypeError, ValueError):
                        retardo_main = 0
                    break
        if config.get("al_inicio"):
            retardo_main = 0     # modo simple: el efecto suena al PRINCIPIO del bloque
        if retardo_main:
            # Tope: dentro del bloque. 'end' esta estirado hasta el bloque
            # siguiente, asi que el margen sobra; es solo para que un bloque
            # rarisimo no suelte su golpe ya empezado el siguiente.
            try:
                tope = (timeline_start_frame
                        + a_fotogramas(float(cue.get("end", cue["start"])),
                                       fps) - 1)
            except (TypeError, ValueError):
                tope = None
            inicio_sfx = inicio + retardo_main
            if tope is not None and tope > inicio and inicio_sfx > tope:
                inicio_sfx = tope
            inicio = inicio_sfx
        duracion = _frames_de_audio(item, fps)
        if duracion < 1:
            duracion = max(1, a_fotogramas(0.5, fps))

        por_colocar.append((inicio, item, categoria, duracion))

    # v5.4: con la duracion REAL de cada sonido (antes todos se cortaban a 0,5 s) los largos se pisan entre si y Resolve
    # rechaza el clip que no cabe en la pista. Cada efecto dura lo que dura su sonido (o el recorte elegido en la
    # pantalla Sonido) pero, como mucho, hasta que empieza el siguiente.
    por_colocar.sort(key=lambda p: p[0])
    pistas = [indice]
    fin_pista = [-1]                  # donde termina lo ultimo colocado en cada pista (fotograma absoluto)
    sin_sitio = 0
    for (inicio, item, categoria, duracion) in por_colocar:
        k = next((j for j, f in enumerate(fin_pista) if f <= inicio), None)
        if k is None:
            if len(pistas) >= 8:
                sin_sitio += 1
                continue
            nueva = pista_sfx_extra(len(pistas))
            if nueva is None:
                sin_sitio += 1
                continue
            pistas.append(nueva)
            fin_pista.append(-1)
            k = len(pistas) - 1
        fin_pista[k] = inicio + duracion
        clip_info = {
            "mediaPoolItem": item,
            "startFrame": 0,
            "endFrame": duracion - 1,
            "trackIndex": pistas[k],
            "mediaType": 2,          # 2 = audio
            "recordFrame": inicio,
        }
        try:
            nuevos = media_pool.AppendToTimeline([clip_info])
        except Exception:
            nuevos = None
        if not nuevos:
            continue
        _pintar_clip(nuevos[0], _color_sfx(categoria))
        colocados += 1
        uso[categoria] = uso.get(categoria, 0) + 1

    reparto = ", ".join(f"{c}: {n}" for c, n in sorted(uso.items()))
    print(f"  Colocados {colocados} efectos ({reparto}) en {len(pistas)} pista(s) de audio.")
    if sin_sitio:
        print(f"  Aviso: {sin_sitio} efecto(s) no cupieron en las {len(pistas)} pistas y se omitieron.")
    if faltantes:
        print(f"  Aviso: sin audios para {', '.join(sorted(faltantes))}; "
              "esos bloques quedaron sin efecto.")
    volumen = config.get("volumen_db")
    if volumen is not None:
        print(f"  La pista '{nombre_pista}' queda a 0 dB. Bájala a "
              f"{volumen} dB en el Mezclador si te tapa la voz.")


# ---------------------------------------------------------------------
# Recomponer (v3.4.0; ver el gemelo .lua): mover los textos YA PUESTOS. La
# app deja composicion_pendiente.json y corre la accion 'subtitulos' de
# siempre; main() mira la orden ANTES del manifiesto y, si es fresca (menos
# de 10 min), recompone en vez de colocar. La base de cada clip = lo que
# tiene ahora − lo que ya se le aplico (los tramos 'anterior').
# ---------------------------------------------------------------------
ORDEN_COMPOSICION = SHARED_FOLDER / "composicion_pendiente.json"
ORDEN_VALE_S = 600


def _tc_a_frames(tc, fps):
    partes = str(tc).replace(";", ":").split(":")
    if len(partes) != 4:
        return 0
    try:
        h, m, s, f = (int(p) for p in partes)
    except ValueError:
        return 0
    return int(round((h * 3600 + m * 60 + s) * fps + f))


def _frame_del_cabezal(timeline, fps, start_frame):
    try:
        tc_actual = timeline.GetCurrentTimecode() or "01:00:00:00"
    except Exception:
        tc_actual = "01:00:00:00"
    try:
        tc_inicio = timeline.GetStartTimecode() or "01:00:00:00"
    except Exception:
        tc_inicio = "01:00:00:00"
    delta = _tc_a_frames(tc_actual, fps) - _tc_a_frames(tc_inicio, fps)
    return start_frame + max(0, delta)


# v3.4.1: el ROL lo dice la PISTA (ES-CTX / -MAIN / -CMP; las base viven en
# la MAIN) y el SET se busca en cadena: el nombre del clip del Media Pool,
# el del timeline, y el ESTILO del Text+ (Size; Font solo desempata) contra
# los estilos del pack que trae la orden. La v3.4.0 identificaba SOLO por
# nombre y en el Resolve del usuario ninguno parseaba («19 clips no son de una
# plantilla conocida», 0 movidos). Gemela del .lua (identificar_clip).
ROL_DE_PISTA = {"-CTX": "context", "-MAIN": "main", "-CMP": "complement"}


def _estilo_del_tool(tool):
    try:
        fuente = str(tool.GetInput("Font") or "")
    except Exception:
        fuente = ""
    try:
        tam = float(tool.GetInput("Size"))
    except Exception:
        tam = None
    return fuente, tam


def _casa_fuente(a, b):
    a, b = str(a or "").lower(), str(b or "").lower()
    return bool(a and b) and (a == b or a in b or b in a)


def identificar_clip(item, tool, rol_pista, estilos_f):
    """(rol, n, como, huella): 'como' = 'pool' | 'nombre' | 'estilo' | None
    (sin identificar: n None, solo Altura/Horizontal); 'huella' = lo que se
    vio, para el registro."""
    try:
        nombre_tl = str(item.GetName() or "")
    except Exception:
        nombre_tl = ""
    nombre_pool = None
    try:
        mpi = item.GetMediaPoolItem()
        if mpi:
            nombre_pool = str(mpi.GetName() or "")
    except Exception:
        nombre_pool = None

    def acepta(nombre):
        if not nombre:
            return None
        rol, n = parsear_nombre_pack(nombre)
        if rol == "base" and rol_pista == "main":
            return "base", 0
        if rol == rol_pista and n and n >= 1:
            return rol, n
        return None

    r = acepta(nombre_pool)
    if r:
        return r[0], r[1], "pool", None
    r = acepta(nombre_tl)
    if r:
        return r[0], r[1], "nombre", None
    fuente, tam = _estilo_del_tool(tool)
    huella = (f"timeline '{nombre_tl}', pool "
              + (f"'{nombre_pool}'" if nombre_pool else "sin respuesta")
              + f", Font '{fuente}', Size {tam}")
    if tam is not None and isinstance(estilos_f, dict):
        candidatos = []
        for clave, est in estilos_f.items():
            m = re.match(r"^([a-z]+)\|(\d+)$", str(clave))
            if not m or not isinstance(est, dict):
                continue
            try:
                s = float(est.get("size"))
            except (TypeError, ValueError):
                continue
            r_ = m.group(1)
            if (r_ == rol_pista or (r_ == "base" and rol_pista == "main")) \
                    and abs(s - tam) <= 0.002:
                # Desempate determinista: fuente que casa primero, despues
                # la clave menor (como el .lua).
                candidatos.append((0 if _casa_fuente(fuente, est.get("font")) else 1,
                                   str(clave), r_, int(m.group(2))))
        if candidatos:
            candidatos.sort()
            _, _, r_, num = candidatos[0]
            return r_, num, "estilo", huella
    return rol_pista, None, None, huella


def _tramo_para(tramos, frame):
    actual = None
    for t in tramos or []:
        try:
            if int(t.get("desde") or 0) <= frame:
                actual = t.get("composicion")
        except (TypeError, ValueError, AttributeError):
            continue
    return composicion_normal(actual) if actual is not None else None


def recomponer(timeline, orden, fps, start_frame):
    nueva = composicion_normal(orden.get("nueva"))
    L = str(orden.get("language") or "es").upper()
    try:
        ancho = int(float(timeline.GetSetting("timelineResolutionWidth")))
        alto = int(float(timeline.GetSetting("timelineResolutionHeight")))
    except Exception:
        ancho, alto = 1920, 1080
    formato = "v" if alto > ancho else "h"
    medidas = orden.get("medidas") if isinstance(orden.get("medidas"), dict) else {}
    medidas_f = medidas.get(formato)
    if not isinstance(medidas_f, dict):
        medidas_f = next((m for m in medidas.values() if isinstance(m, dict)), {})
    estilos = orden.get("estilos") if isinstance(orden.get("estilos"), dict) else {}
    estilos_f = estilos.get(formato)
    if not isinstance(estilos_f, dict):
        estilos_f = next((m for m in estilos.values() if isinstance(m, dict)), {})
    desde = start_frame
    if orden.get("desde") != "todo":
        desde = _frame_del_cabezal(timeline, fps, start_frame)
    print(f"  Recomposición: layout {nueva['layout']}, altura "
          f"{nueva['altura']:+.3f}, horizontal {nueva['horizontal']:+.3f}, "
          f"desde el fotograma {desde} "
          f"({'todo' if orden.get('desde') == 'todo' else 'el cabezal'}).")

    lineas, emojis_clips, ajenos = [], [], 0
    como_cuenta = {"pool": 0, "nombre": 0, "estilo": 0, "ninguno": 0}
    huellas = []
    try:
        cantidad = int(timeline.GetTrackCount("video") or 0)
    except Exception:
        cantidad = 0
    for t in range(1, cantidad + 1):
        try:
            nombre_p = (timeline.GetTrackName("video", t) or "").strip().upper()
        except Exception:
            continue
        rol_pista = ROL_DE_PISTA.get(nombre_p[len(L):]) if nombre_p.startswith(L) else None
        es_emoji = nombre_p == L + "-EMOJI"
        if not (rol_pista or es_emoji):
            continue
        try:
            items = timeline.GetItemListInTrack("video", t) or []
        except Exception:
            items = []
        for it in items:
            try:
                record, fin = int(it.GetStart()), int(it.GetEnd())
            except Exception:
                continue
            # v3.4.1: fin > desde — el bloque que esta BAJO el cabezal
            # tambien entra (es lo que uno espera al parar a mitad).
            if fin <= desde:
                continue
            if es_emoji:
                if _es_clip_texto_nuestro(it):
                    emojis_clips.append({"item": it, "record": record})
                continue
            try:
                tool = get_text_plus_tool(it)
            except Exception:
                tool = None
            if tool is None:
                # Sin Text+ no es nuestro: no se toca.
                ajenos += 1
                continue
            rol, n, como, huella = identificar_clip(it, tool, rol_pista, estilos_f)
            como_cuenta[como or "ninguno"] += 1
            if como is None and len(huellas) < 3:
                huellas.append(huella)
            texto = None
            try:
                v = tool.GetInput("StyledText")
                if isinstance(v, str):
                    texto = v
            except Exception:
                pass
            ancho_em = None
            por_texto = medidas_f.get(f"{rol}|{n}") if n is not None else None
            if isinstance(por_texto, dict) and texto is not None \
                    and por_texto.get(texto) is not None:
                try:
                    ancho_em = float(por_texto[texto])
                except (TypeError, ValueError):
                    ancho_em = None
            lineas.append({"item": it, "rol": rol, "record": record,
                           "fin": fin, "ancho_em": ancho_em,
                           "zx": _prop_de(it, "ZoomX") or 1.0})

    # Los bloques: las lineas que CIERRAN en el mismo fotograma (±1).
    lineas.sort(key=lambda l: (l["fin"], l["record"]))
    bloques = []
    for l in lineas:
        if bloques and abs(l["fin"] - bloques[-1]["fin"]) <= 1:
            bloques[-1]["lineas"].append(l)
            bloques[-1]["record"] = min(bloques[-1]["record"], l["record"])
        else:
            bloques.append({"fin": l["fin"], "record": l["record"],
                            "lineas": [l]})

    # El fotograma que se anota en el estado: donde ARRANCA el primer bloque
    # tocado (puede ser antes del cabezal), o el cabezal si no hay ninguno.
    desde_efectivo = min([desde] + [b["record"] for b in bloques]
                         + [e["record"] for e in emojis_clips])

    cuenta = {"movidos": 0, "fallidos": 0}

    def _mover(item, dx, dy):
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return True
        pan = _prop_de(item, "Pan") or 0.0
        tilt = _prop_de(item, "Tilt") or 0.0
        if _poner_props(item, {"Pan": pan + dx, "Tilt": tilt + dy}):
            cuenta["movidos"] += 1
            return True
        cuenta["fallidos"] += 1
        return False

    alineadas = sin_medida = 0
    ceros = {"dx": 0.0, "dy": 0.0}
    for b in bloques:
        d_nueva, _lay = desplazamientos_bloque(nueva, b["record"], b["lineas"],
                                               ancho, alto)
        ant = _tramo_para(orden.get("anterior"), b["record"])
        d_ant = (desplazamientos_bloque(ant, b["record"], b["lineas"],
                                        ancho, alto)[0] if ant else None)
        for k, l in enumerate(b["lineas"]):
            da = d_ant[k] if d_ant else ceros
            _mover(l["item"], d_nueva[k]["dx"] - da["dx"],
                   d_nueva[k]["dy"] - da["dy"])
            if d_nueva[k]["alineada"]:
                alineadas += 1
            if d_nueva[k]["sin_medida"]:
                sin_medida += 1
    for e in emojis_clips:
        ant = _tramo_para(orden.get("anterior"), e["record"])
        dx = _pan_px(nueva["horizontal"] - (ant["horizontal"] if ant else 0.0), ancho)
        dy = _tilt_px(nueva["altura"] - (ant["altura"] if ant else 0.0), alto)
        _mover(e["item"], dx, dy)
    print(f"  Recompuse {len(bloques)} bloque(s) ({len(lineas)} línea(s)) y "
          f"{len(emojis_clips)} emoji(s) desde el fotograma {desde_efectivo}: "
          f"{cuenta['movidos']} clip(s) movido(s), {alineadas} línea(s) "
          f"alineada(s), {sin_medida} sin medida (se quedan donde la "
          "plantilla las puso).")
    if lineas:
        print(f"  Identificación: {como_cuenta['pool']} por el Media Pool, "
              f"{como_cuenta['nombre']} por el nombre, {como_cuenta['estilo']} "
              f"por el estilo, {como_cuenta['ninguno']} sin identificar (solo "
              "Altura/Horizontal).")
        for h in huellas:
            print(f"    sin identificar: {h}")
    if sin_medida and not medidas_f:
        print("  Aviso: la orden no trae medidas de esta plantilla (Media Pool "
              "o .drb sin estilos): solo se aplican Altura y Horizontal.")
    if cuenta["fallidos"]:
        print(f"  Aviso: {cuenta['fallidos']} clip(s) no se pudieron mover (tu "
              "Resolve no aceptó SetProperty).")
    if ajenos:
        print(f"  Aviso: {ajenos} clip(s) de las pistas de subtítulos no son "
              "Text+: no los toco.")
    if not bloques and not emojis_clips:
        print("  No hay subtítulos nuestros desde ese fotograma: nada que "
              "mover (¿el cabezal está después del último bloque, o el "
              "timeline no lleva subtítulos de este programa?).")
    # El fotograma va en el resumen: la app lo lee para anotar el estado.
    return (f"Recomposición: {cuenta['movidos']} clips movidos en "
            f"{len(bloques)} bloques desde el fotograma {desde_efectivo} · v{VERSION}")


def _orden_de_composicion():
    """La orden fresca (< ORDEN_VALE_S), o None (y dice si hay una vieja)."""
    if not ORDEN_COMPOSICION.exists():
        return None
    try:
        orden = json.loads(ORDEN_COMPOSICION.read_text(encoding="utf-8"))
        edad = _time.time() - float(orden.get("creada_en") or 0)
    except Exception:
        return None
    if -5 <= edad <= ORDEN_VALE_S:      # -5: relojes con decimales
        return orden
    print(f"  Aviso: hay una orden de composición de hace {int(edad)} s: la "
          "ignoro y coloco los subtítulos como siempre.")
    return None


def main():
    try:
        resolve
    except NameError:
        fail("Este script debe correrse desde Resolve: Workspace > Scripts > Utility > CineCaptions")

    # El objeto 'resolve' puede EXISTIR y estar hueco: sus metodos valen None.
    # Pasa cuando Resolve tiene el scripting externo apagado
    # (Preferencias > Sistema > General > "External scripting using" = None).
    # Sin esta comprobacion el usuario recibia un traceback crudo,
    #     TypeError: 'NoneType' object is not callable
    # y encima despues de generar todos los bloques: el trabajo hecho y tirado.
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

    # v3.4.0: una ORDEN de composicion fresca manda sobre el manifiesto.
    orden = _orden_de_composicion()
    if orden is not None:
        fps_o = float(timeline.GetSetting("timelineFrameRate") or 30)
        try:
            nombre_proy_o = project.GetName()
        except Exception:
            nombre_proy_o = "?"
        print(f"Proyecto: {nombre_proy_o}  |  Timeline: {timeline.GetName()}"
              f"  |  fps: {fps_o}")
        resumen = recomponer(timeline, orden, fps_o,
                             int(timeline.GetStartFrame() or 0))
        for f in (ORDEN_COMPOSICION,
                  ORDEN_COMPOSICION.with_name(ORDEN_COMPOSICION.name + ".lua")):
            try:
                f.unlink()
            except OSError:
                pass
        guardar_resultado(True, resumen)
        return

    if not MANIFEST_PATH.exists():
        fail(f"No encuentro {MANIFEST_PATH}. Corre primero subtitle_transcriber.py")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    media_pool = project.GetMediaPool()
    template_clip = find_template_clip(media_pool)

    # (v2.0.1: aqui habia un fail() si faltaba 'Subtitle Template' y no
    # habia pistas dinamicas — cortaba los subtitulos NORMALES de Studio
    # antes de mirar la plantilla de basicos incrustada (reporte literal
    # 14-09: «buscan plantilla en la media pool y eso ya no debe pasar...
    # debe tomar las plantillas incrustadas»). Cada pista decide sola,
    # con la cascada del gemelo Free.)

    # Lo que dejo la corrida anterior (ver MARCA_TIMELINE_TEMPORAL). Se
    # limpia AQUI, cuando ninguno es el timeline actual.
    _sobras = _limpiar_temporales(project, media_pool)
    if _sobras:
        print(f"  Limpié {_sobras} timeline(s) temporal(es) de la corrida "
              "anterior.")

    fps = float(timeline.GetSetting("timelineFrameRate"))
    inicio_timeline = timeline.GetStartFrame()

    # El PROYECTO va en el registro: una corrida en cero por estar en el
    # proyecto equivocado era indistinguible de un fallo real (01-09).
    try:
        _nombre_proy = project.GetName()
    except Exception:
        _nombre_proy = "?"
    print(f"Proyecto: {_nombre_proy}  |  Timeline: {timeline.GetName()}"
          f"  |  fps: {fps}")
    # v3.3.0: la version de Resolve del cliente en el registro. El caso de
    # las lineas encimadas llego sin ella y no se podia saber que era.
    try:
        print(f"Resolve: {resolve.GetVersionString()}")
    except Exception:
        pass

    def origen_de(track_info):
        """El fotograma donde arranca lo transcrito.

        Normalmente es el inicio del timeline, como siempre. Pero si el
        usuario marco un punto de entrada, lo que se transcribio EMPIEZA
        ahi: el segundo 0 de los bloques es la marca, no el principio. Ese
        numero lo manda la app en el manifiesto; sin el, los subtitulos de
        un tramo marcado en el minuto 5 se colocarian en el minuto 0.
        """
        try:
            offset = int(track_info.get("offset_frames") or 0)
        except (TypeError, ValueError):
            return inicio_timeline
        if offset <= 0:
            return inicio_timeline
        print(f"  Zona marcada: los bloques arrancan en el fotograma "
              f"{offset}, no en {inicio_timeline}.")
        return offset

    for track_info in manifest["tracks"]:
        lang = track_info["language"]
        timeline_start_frame = origen_de(track_info)

        if track_info.get("style") == "kinetic":
            place_kinetic_track(timeline, media_pool, track_info,
                                template_clip, fps, timeline_start_frame,
                                project)
            continue

        if track_info.get("style") == "guion":
            place_guion_track(timeline, media_pool, track_info,
                              template_clip, fps, timeline_start_frame,
                              project)
            continue

        if track_info.get("style") == "dynamic":
            place_dynamic_track(timeline, media_pool, track_info,
                                template_clip, fps, timeline_start_frame,
                                project)
            continue

        if track_info.get("style") == "destacados":
            place_destacados_track(timeline, media_pool, track_info,
                                   template_clip, fps, timeline_start_frame)
            continue

        srt_path = track_info["srt_path"]
        if not Path(srt_path).exists():
            print(f"  Aviso: no encuentro {srt_path}, salto '{lang}'")
            continue

        # La plantilla de BASICOS elegida (v1.0.69): 'basico <pos> <n>'
        # para la pista normal y 'traducion <pos> <n>' para la traducida.
        # Cualquier tropiezo degrada a la cascada de siempre, diciendolo —
        # nunca cero lineas.
        es_traducida = bool(track_info.get("traducida"))
        clip_basico = None
        pb = pack_basicos_del_manifiesto(track_info, timeline)
        if pb:
            # Envuelto (v2.0.1): _subcarpeta no lleva try y el gemelo Free
            # si protege su llamada — un prep roto degrada, nunca tumba.
            try:
                carpeta_b, aviso_b = preparar_bin_basicos(media_pool, pb)
            except Exception as e:
                carpeta_b, aviso_b = None, f"no pude preparar el bin ({e})"
            if aviso_b:
                print(f"  Aviso (basicos): {aviso_b}. Genero como siempre.")
            if carpeta_b is not None:
                tipo = "traducion" if es_traducida else "basico"
                clip_basico = clip_basico_en(carpeta_b, tipo,
                                             pb["pos"], pb["n"])
                if clip_basico is not None:
                    print(f"  Plantilla de basicos: '{tipo} {pb['pos']} "
                          f"{pb['n']}' (pack '{pb['nombre']}').")
                elif es_traducida:
                    print("  Aviso: el pack de basicos no trae 'traducion "
                          f"{pb['pos']} {pb['n']}': la traducida va como "
                          "siempre.")

        cues = parse_srt(srt_path)
        print(f"\nIdioma '{lang}': {len(cues)} bloques -> {srt_path}")

        # La pista TRADUCIDA va con la plantilla 'base' (la del pack si se
        # preparo, la del usuario si existe) y un escalon mas abajo: convive
        # en pantalla con la original y sin bajarla se tapan. Con plantilla
        # de basicos, ni escalon ni cascada: el clip del pack ya viene
        # colocado donde el diseñador lo quiso (la posicion la decide el
        # pack, la regla de siempre).
        # v2.0.1: la cascada en el MISMO orden que place_srt del gemelo
        # Free — basicos, 'base' del pack (traducida), 'base'/'Subtitle
        # Template' del usuario y, al final, cualquier Text+ utilizable.
        usa_basicos = clip_basico is not None
        plantilla_srt = clip_basico
        if plantilla_srt is None and es_traducida:
            plantilla_srt = plantilla_base_del_pack(media_pool)
            if plantilla_srt is not None:
                print("  Pista traducida: uso la plantilla 'base' del pack.")
        if plantilla_srt is None:
            plantilla_srt = (find_base_template(media_pool)
                             or template_clip
                             or obtener_text_plus_base(timeline, media_pool))
        if plantilla_srt is None:
            print(f"  Aviso: '{lang}' necesita un Text+ de plantilla y no "
                  "encontré ninguno. Salto este idioma.")
            continue

        # Un modo, un juego de subtitulos (v2.0.2): fuera los dinamicos de
        # una corrida anterior y las pistas LANG apiladas (hasta la v2.0.1
        # cada corrida normal CREABA una pista nueva encima de la
        # anterior); despues se reutiliza la primera LANG que sea nuestra
        # o se crea, con el mismo criterio que las dinamicas.
        L = lang.upper()
        _retirar_pistas_nuestras(
            timeline, [f"{L}-CTX", f"{L}-MAIN", f"{L}-CMP", L, f"{L}-EMOJI"] + [f"{L}-K{k}" for k in range(1, 25)],
            "subtítulos", "esta corrida es de subtítulos normales")
        new_track_index, error = _conseguir_pista_video(timeline, L)
        if error:
            print(f"  ERROR: no pude crear la pista '{lang.upper()}' de "
                  f"forma segura ({error}). Salto '{lang}' para no "
                  "arriesgar tu timeline.")
            continue

        placed = 0
        bajados, sin_bajar = 0, 0
        # La posicion del clip de basicos (v3.3.0), por su clave del .drb.
        transf_basico = None
        ancho_tl, alto_tl = 1920, 1080
        if usa_basicos:
            transf_basico = pb["transformaciones"].get(
                f"{'traducion' if es_traducida else 'basico'}|{pb['pos']}|"
                f"{pb['n']}")
            try:
                ancho_tl = int(float(timeline.GetSetting(
                    "timelineResolutionWidth")))
                alto_tl = int(float(timeline.GetSetting(
                    "timelineResolutionHeight")))
            except Exception:
                pass
        _reiniciar_transformaciones()
        for cue in cues:
            start_frame = timeline_start_frame + a_fotogramas(cue["start"], fps)
            end_frame = timeline_start_frame + a_fotogramas(cue["end"], fps)
            duration = max(1, end_frame - start_frame)

            # Con la duracion EXACTA (v2.0.3): el fotograma de menos que
            # Resolve pone a cada clip era el hueco entre subtitulos.
            item_srt, _ = colocar_medido(media_pool, timeline, plantilla_srt,
                                         0, duration, new_track_index,
                                         start_frame, fps, color=COLOR_TEXTO)
            new_items = [item_srt] if item_srt is not None else []
            if not new_items:
                print(f"  Aviso: no pude colocar el bloque en {cue['start']:.2f}s")
                continue

            ok = set_text_on_clip(new_items[0], cue["text"])
            if ok and transf_basico:
                aplicar_transformacion(new_items[0], transf_basico,
                                       ancho_tl, alto_tl)
            if not ok:
                print(f"  Aviso: coloqué el clip en {cue['start']:.2f}s pero no pude "
                      "setear el texto automáticamente (edítalo a mano con doble clic).")
            else:
                placed += 1
            if es_traducida and ok and not usa_basicos:
                if bajar_center(new_items[0]):
                    bajados += 1
                else:
                    sin_bajar += 1

        if placed:
            _ALGO_COLOCADO[0] = True
            _TOTAL[0] += placed
        print(f"  Colocados {placed}/{len(cues)} bloques en la pista '{lang.upper()}'.")
        informe_transformaciones()
        if bajados:
            print(f"  Pista traducida: {bajados} bloques bajados un escalón "
                  "para no tapar la original.")
        if sin_bajar:
            # No es un fallo de colocacion: el texto esta. Solo que ese comp
            # no expone Center (grupo con animacion) y no se toca.
            print(f"  Aviso: {sin_bajar} bloques traducidos quedaron en la "
                  "posición original de la plantilla (su diseño no deja "
                  "moverlos por script).")

    if _ALGO_COLOCADO[0]:
        print("\nListo. Revisa la línea de tiempo: cada bloque es un Text+ "
              "editable (doble clic sobre el clip para retocar texto, "
              "estilo o posición).")
        # El resultado se escribe TAMBIEN en el exito. Hasta la v1.0.41
        # solo lo escribia fail(): una corrida buena jamas refrescaba
        # ultimo_resultado.*, y la app le enseñaba al usuario el FALLO de
        # dias atras como si fuera el de hoy (paso en el Mac del cliente
        # con uno del 25/08 leido el 31/08). El gemelo Lua siempre lo hizo.
        vista_final(timeline, manifest)          # antes de guardar: sus líneas (y avisos) tienen que quedar en ultimo_resultado.txt
        guardar_resultado(True, f"{_TOTAL[0]} líneas colocadas · v" + VERSION)
    else:
        # Decir "Listo" con cero lineas era mentirle al registro.
        print("\nNO se colocó ninguna línea. El motivo está unas líneas más "
              "arriba (las que empiezan por «Aviso»).")
        vista_final(timeline, manifest, solo_pagina=True)
        guardar_resultado(False, "No se colocó ninguna línea (mira el "
                          "registro: el motivo está en los avisos) · v"
                          + VERSION)


if __name__ == "__main__":
    main()
