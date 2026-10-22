# CineCaptions · By Cinema Productions
# 3_compilar/encabezados.py — pone (o actualiza) el encabezado de autor y la descripción en cada archivo de código.
"""
encabezados.py
--------------
Cada archivo de código de CineCaptions empieza con dos líneas de comentario:

    # CineCaptions · By Cinema Productions
    # 1_codigo/licencia.py — la licencia (Lemon Squeezy / Gumroad): ...

La primera deja grabado el autor; la segunda dice QUÉ ES ese archivo, y de ahí sale el «ÍNDICE DE
ARCHIVOS» del LEEME (3_compilar/documentar.py). Para un archivo NUEVO: añade su descripción en
DESCRIPCIONES y corre

    python 3_compilar/encabezados.py

(Construir_Instalador.ps1 lo corre solo en cada compilación). Es idempotente: no duplica nada.
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
AUTOR = 'CineCaptions · By Cinema Productions'

DESCRIPCIONES = {
    # ---------------------------------------------------------------- el programa (va dentro del .exe)
    '1_codigo/CineCaptions (script principal).py': 'el programa: ventana principal (Inicio/GO, Proyecto, Editor, SFX Lab), editor de palabras, licencia, generar y colocar en Resolve, main().',
    '1_codigo/actualizaciones.py': 'actualizaciones automáticas: lee un version.json publicado, descarga el instalador, comprueba su huella SHA-256 y lo lanza.',
    '1_codigo/ajustes_ui.py': 'Ajustes: panel rápido y ventana completa (General, Interfaz, Atajos, Acerca de, Ayuda) + notas de la versión.',
    '1_codigo/composicion.py': 'Composición de los bloques dinámicos: layouts (alineación de contexto/complemento) y desplazamientos.',
    '1_codigo/copias.py': 'copias de seguridad de ~/DaVinciSubtitles (crear y restaurar un .zip).',
    '1_codigo/dynamic_subtitles.py': 'el «cerebro» de los subtítulos dinámicos: frases, roles (contexto/PRINCIPAL/complemento) y bloques.',
    '1_codigo/efectos_ui.py': 'animaciones de la interfaz: fondo vivo, vistas reales animadas, entrada escalonada de tarjetas.',
    '1_codigo/emojis.py': 'emojis de las palabras clave: catálogo, biblioteca Fluent 3D, PNG propios y sugerencias por idioma.',
    '1_codigo/ensure_lang_pack.py': 'instala los paquetes de traducción sin internet (Argos Translate) que falten.',
    '1_codigo/fuentes_sistema.py': 'encuentra en el disco el archivo .ttf/.otf de una familia y estilo.',
    '1_codigo/i18n.py': 'idiomas de la interfaz: tr("texto en español") y los catálogos de 2_recursos/locales.',
    '1_codigo/ia_texto.py': 'IA de texto local (Qwen3): corrige, elige palabras clave y emojis virales, quita signos.',
    '1_codigo/instalador_scripts.py': 'copia los scripts de CineCaptions al menú de DaVinci Resolve y comprueba que estén al día.',
    '1_codigo/instalar_fuentes.py': 'instala en el sistema las tipografías de las plantillas (para que Resolve/Fusion las vea).',
    '1_codigo/licencia.py': 'la licencia (Lemon Squeezy / Gumroad): activar, verificar, desactivar, estado firmado, 7 días sin internet.',
    '1_codigo/medir_texto.py': 'mide cuánto ocupa cada palabra en pantalla (look «pintado»).',
    '1_codigo/motor_voz.py': 'motor de voz e IA Qwen3 en su propio Python 3.12: instalar, detectar y transcribir.',
    '1_codigo/ortografia.py': 'revisión ortográfica del editor (marca y propone, nunca corrige solo).',
    '1_codigo/packs_drt.py': 'lee los packs .drt/.drb SIN abrir Resolve (sets, formatos, tipografías).',
    '1_codigo/plantillas.py': 'packs de estilos: leer, guardar, elegir y preparar el pack que se aplica.',
    '1_codigo/proyectos.py': 'registro de proyectos (vídeos) trabajados: recientes, abrir, borrar.',
    '1_codigo/qt_kit.py': 'kit de interfaz Qt: colores, tipografía Inter, controles, mensajes, hilos (correr_en_hilo, despues).',
    '1_codigo/resolve_bridge.py': 'conexión con Resolve: API externa (Studio), Puente (Free) o paso manual; ejecuta los scripts.',
    '1_codigo/resolve_mcp.py': 'conexión con el MCP oficial de Resolve 21.1+: abrir Resolve, proyecto reciente, ejecutar scripts.',
    '1_codigo/mapa_codigo.py': 'consulta el código y la documentación POR TEMA sin leer archivos enteros (mapa, símbolo, módulo, cambios); lo usan el MCP y la línea de comandos.',
    '3_compilar/sincronizar_version.py': 'pone la versión de version.py en todos los sitios que la repiten (scripts de Resolve, Puente) y avisa si algo no cuadra.',
    '1_codigo/vigilancia.py': 'guardián de tareas largas (GO, Generar): detecta atascos, destraba motores, chequeos periódicos y arranque atascado.',
    '1_codigo/salud.py': 'chequeo de librerías al arrancar (versiones fijadas, motor de IA, MCP).',
    '1_codigo/sfx_audio.py': 'audio del SFX Lab: cargar, cambiar tono y velocidad, reproducir.',
    '1_codigo/sfx_editor.py': 'la ventana «Editar» de un sonido: elegir de forma visual qué parte suena (onda con asas) y su volumen.',
    '1_codigo/registro.py': 'el registro de avisos y errores: archivo de log, historial y señal para la interfaz.',
    '1_codigo/registro_ui.py': 'el aviso en la barra de título, el botón del registro con contador y la ventana Registro.',
    '1_codigo/brillo_ui.py': 'barridos de luz y ondas al pulsar para todos los botones.',
    '1_codigo/ritmo_ui.py': 'Regulador del ritmo de las animaciones: si la interfaz va justa (GO usando CPU/GPU, equipo modesto) baja los fotogramas del fondo y de la esfera para que los clics respondan; los sube al aliviarse.',
    '1_codigo/mograf_ui.py': 'Motion Graphics de la interfaz: entrada de tarjetas con marcas, título cinético, traza de luz, formas ambiente y HUD de Inicio.',
    '1_codigo/escena_go.py': 'la escena de Inicio: esfera de partículas 3D, absorción, cometas de pasos y explosión final.',
    '1_codigo/sfx_rules.py': 'decide el efecto de sonido de cada bloque leyendo resolve_scripts/sfx_rules.json.',
    '1_codigo/director_sonido.py': '«AI Sound Director» (v5.34): el sound designer de GO. Analiza el video y dirige el sonido ENCIMA de los motores de siempre.',
    '1_codigo/director_sonido_ambiente.py': '«AI Sound Director» · AI AMBIENCE: el entorno de cada escena y qué hacer con su ambiente.',
    '1_codigo/director_sonido_estado.py': '«AI Sound Director» (v5.34): el estado `sound_design_project` de cada video (lo analizado, decidido y medido).',
    '1_codigo/director_sonido_eventos.py': '«AI Sound Director»: lo que pasa en pantalla y en la narración, leído de la metadata REAL de GO.',
    '1_codigo/director_sonido_identidad.py': '«AI Sound Director»: THEME → SONIC PROFILE → PROJECT SONIC PALETTE.',
    '1_codigo/director_sonido_medir.py': '«AI Sound Director»: leer, filtrar y medir audio con PyAV (ffmpeg dentro del programa), en streaming.',
    '1_codigo/director_sonido_musica.py': '«AI Sound Director»: ¿hay música? ¿la necesita? La decisión de la música (no binaria).',
    '1_codigo/director_sonido_nr.py': '«AI Sound Director»: reducción de ruido de la voz (numpy, sin dependencias nuevas), natural antes que cero ruido.',
    '1_codigo/director_sonido_voz.py': '«AI Sound Director»: diagnóstico de la voz y su restauración (una COPIA), con guardas para que nunca suene robótica.',
    '1_codigo/herramientas_dev/probar_director_sonido.py': 'pruebas del «AI Sound Director» SIN pantalla y SIN el Resolve del usuario.',
    '1_codigo/herramientas_dev/resolve_falso.py': 'un DaVinci Resolve FALSO en memoria para probar los scripts de colocación (colocar_efectos.py) sin el Resolve del usuario.',
    '1_codigo/herramientas_dev/_voz_sapi.py': 'una voz LIMPIA de referencia (SAPI de Windows, por COM) para los casos sintéticos de probar_director_sonido.py.',
    '1_codigo/director_sonido_epidemic.py': '«AI Sound Director»: cliente de la API de Epidemic Sound (solo backend; la clave, solo del entorno).',
    '1_codigo/herramientas_dev/probar_epidemic.py': 'prueba SEGURA del cliente de Epidemic Sound del AI Sound Director (nunca enseña la clave).',
    '1_codigo/director_sonido_sintesis.py': '«AI Sound Director»: sonido PROCEDURAL diseñado alrededor de cada movimiento (no un WAV genérico).',
    '1_codigo/director_sonido_fuentes.py': '«AI Sound Director»: de dónde sale cada sonido (SOUND ASSET STRATEGY) y el QUALITY GATE de cada archivo.',
    '1_codigo/director_sonido_diseno.py': '«AI Sound Director», FASE 3: qué suena y qué se queda en silencio, evento por evento, en los 6 temas.',
    '1_codigo/director_sonido_sfx.py': '«AI Sound Director», FASE 3: cada sonido del diseño hecho a la medida, en su WAV y listo para su pista AI.',
    '1_codigo/director_sonido_capas.py': '«AI Sound Director», FASE 4: la MÚSICA y el AMBIENTE (pistas AI MUSIC y AI AMBIENCE).',
    '1_codigo/director_sonido_mezcla.py': '«AI Sound Director», FASE 5: la mezcla completa, el QC en 3 pasadas y el SOUND SCORE (de métricas reales).',
    '1_codigo/director_sonido_sesion.py': '«AI Sound Director», FASE 6: lo que la página necesita (leer el diseño de un video, controles, retocar, oír, aplicar).',
    '1_codigo/director_sonido_ui.py': 'la página SONIDO = «AI Sound Director» (fase 6): la IA hace el 95 % del sonido; el usuario lo dirige (5 %).',
    '1_codigo/herramientas_dev/probar_pagina_director.py': 'prueba la página SONIDO = «AI Sound Director» (fase 6) SIN pantalla y SIN el Resolve del usuario.',
    '1_codigo/herramientas_dev/demo_director_sonido.py': 'el Tema 1 renderizado SIN Resolve con varias bandas sonoras del AI Sound Director, para compararlas.',
    '1_codigo/sfx_studio.py': 'la pantalla SFX Lab (biblioteca, pad XY, marcadores por color, reemplazar).',
    '1_codigo/emojis_sfx.py': 'el sonido de cada emoji (fuego → fuego, beso → beso…): qué familia le toca, el que el usuario eligió y los eventos que se mandan a Resolve.',
    '1_codigo/emojis_sfx_ui.py': 'pestaña «Emojis» del SFX Lab: todos los emojis en una rejilla y el sonido de cada uno, para cambiarlo.',
    '1_codigo/ejemplos_estilo.py': 'los 48 ejemplos de «Crea tu estilo» (posición, tipografía y colores; 18 con un principal de Amro.Films Captions), su vista y cómo se vuelven un pack o un timeline de Resolve.',
    '1_codigo/vistas_guia.py': 'las vistas REALES (renderizadas por Resolve) de los ejemplos de «Crea tu estilo»: se piden, se reducen y se guardan en caché.',
    '1_codigo/recorrido_ui.py': 'recorrido visual por pasos: una capa sobre la ventana que ilumina cada zona de la interfaz y la explica (se desactiva en Ajustes).',
    '1_codigo/estilos_bloque.py': 'qué estilo (variante del pack) lleva CADA bloque: lo decide la app y lo enseña Creativo, ya no el azar de Resolve.',
    '1_codigo/edicion_pack.py': '«Editar en Resolve»: abre un pack de «Pack de estilos» como timeline para modificarlo y exportarlo de nuevo.',
    '2_recursos/guia_estilo/editar_pack.py': 'corre DENTRO de Resolve: abre un pack de «Pack de estilos» como timeline para editarlo (y exportarlo de nuevo).',
    '1_codigo/crea_estilo_ui.py': '«Crea tu estilo»: la galería de 48 ejemplos (con su vista real de Resolve) para armar un pack en un clic y el popup que explica la estructura de nombres.',
    '2_recursos/guia_estilo/construir_guia.py': 'corre DENTRO de Resolve: arma el timeline «Crea tu estilo» con los 48 ejemplos (Luxe Shine o Amro de principal; Luxe Slide arriba y abajo) y saca sus vistas reales.',
    '1_codigo/archivos_seguros.py': 'escritura atómica de JSON/texto (preferencias, marcas, proyectos): un corte o dos hilos ya no dejan archivos a medias.',
    '1_codigo/editor_ui.py': 'piezas del editor Creativo: barra de herramientas, tarjeta del párrafo, palabras por línea, play y el panel de avance de Asistencia/Generar.',
    '1_codigo/sidecar_lua.py': 'escribe <archivo>.lua junto a cada .json (canal de lectura para Resolve Free 21.1).',
    '1_codigo/subtitle_transcriber.py': 'transcripción con Whisper, traducción con Argos y escritura de .srt / manifiestos.',
    '1_codigo/sugerencias_ia.py': 'sugiere la palabra PRINCIPAL de cada bloque (motor clásico, sin IA instalada).',
    '1_codigo/tareas_instalador.py': 'lo que el instalador pide al programa (--tarea verificar/scripts/fuentes/modelo/motor_ia...).',
    '1_codigo/tema.py': 'temas de la interfaz (superficies, color de resaltado, tamaño) y su traductor de colores.',
    '1_codigo/ui_toast.py': 'avisos que se cierran solos (toasts).',
    '1_codigo/un_clic_ui.py': 'la pantalla de Inicio: botón GO, pasos animados, cinta viral y vista previa.',
    '1_codigo/ventana_licencia.py': 'la ventana «Activa tu licencia» (formato CineSlide: panel animado, clave, confeti).',
    '1_codigo/version.py': 'la versión del programa (APP_VERSION) y el autor, en un solo sitio.',
    '1_codigo/vistas_reales.py': 'vistas previas renderizadas DE VERDAD por Resolve (packs y bloques de GO).',
    # ---------------------------------------------------------------- scripts que corren DENTRO de Resolve
    '2_recursos/resolve_scripts/CineCaptions.py': 'coloca los subtítulos en el timeline (núcleo en Python para Resolve Studio).',
    '2_recursos/resolve_scripts/CineCaptions - Detectar Video.py': 'renderiza el audio del timeline activo para transcribirlo (Studio).',
    '2_recursos/resolve_scripts/CineCaptions - Importar Estilos.py': 'saca un pack de estilos de un timeline con Text+ (Studio).',
    '2_recursos/resolve_scripts/CineCaptions - Insertar SFX.py': 'importa un sonido y lo coloca en el cabezal (Studio).',
    '2_recursos/resolve_scripts/CineCaptions - Puente.py': 'el Puente en Python: vigila ~/DaVinciSubtitles/jobs y ejecuta las órdenes.',
    '2_recursos/resolve_scripts/CineCaptions - SFX Marcadores.py': 'efectos de sonido en los marcadores, por color (Studio).',
    '2_recursos/resolve_scripts/CineCaptions - SFX Reemplazar.py': 'reemplaza el efecto de sonido bajo el cabezal (Studio).',
    '2_recursos/resolve_scripts/CineCaptions - Vista Real.py': 'renderiza las vistas previas reales en un timeline temporal (lo lanza el MCP).',
    '2_recursos/resolve_scripts/CineCaptions_Subtitulos.lua': 'coloca los subtítulos en el timeline (núcleo en Lua para Resolve Free).',
    '2_recursos/resolve_scripts/CineCaptions_Puente.lua': 'el Puente para Resolve Free: vigila la cola de trabajos y ejecuta los scripts.',
    '2_recursos/resolve_scripts/CineCaptions_DetectarVideo.lua': 'renderiza el audio del timeline activo (Resolve Free).',
    '2_recursos/resolve_scripts/CineCaptions_ImportarEstilos.lua': 'saca un pack de estilos de un timeline (Resolve Free).',
    '2_recursos/resolve_scripts/CineCaptions_InsertarSFX.lua': 'importa un sonido y lo coloca en el cabezal (Resolve Free).',
    '2_recursos/resolve_scripts/CineCaptions_SfxMarcadores.lua': 'efectos de sonido en los marcadores por color (Resolve Free).',
    '2_recursos/resolve_scripts/CineCaptions_SfxReemplazar.lua': 'reemplaza el efecto bajo el cabezal (Resolve Free).',
    '2_recursos/resolve_scripts/CineCaptions_Exportar_PackDRB.lua': 'herramienta de desarrollo: exporta un pack como .drb.',
    '2_recursos/resolve_scripts/CineCaptions_Prueba_MediaPool.lua': 'herramienta de prueba: comprueba si se puede meter un Text+ al Media Pool.',
    # ---------------------------------------------------------------- motor de IA (Python 3.12 aparte)
    '2_recursos/motor_qwen/motor_qwen.py': 'motor de voz Qwen3-ASR + alineador (corre en el Python 3.12 del motor).',
    '2_recursos/motor_qwen/motor_texto.py': 'IA de texto Qwen3 Instruct: correcciones, pesos y emojis por frase (modo servidor).',
    # ---------------------------------------------------------------- compilar
    '3_compilar/Construir_Instalador.ps1': 'arma el instalador de Windows de principio a fin (PyInstaller + autoprueba + C#).',
    '3_compilar/cinecaptions.spec': 'receta de PyInstaller del programa (qué módulos y recursos van dentro del .exe).',
    '3_compilar/rthook_stanza_stub.py': 'hook de arranque de PyInstaller (sustituye stanza para que Argos no arrastre torch).',
    '3_compilar/Instalador.cs': 'el instalador y desinstalador (C#, .NET Framework 4): pasos, banner, registro.',
    '3_compilar/encabezados.py': 'pone (o actualiza) el encabezado de autor y la descripción en cada archivo de código.',
    '3_compilar/documentar.py': 'regenera el índice y el mapa del código del LEEME y anota los cambios en el registro.',
    # ---------------------------------------------------------------- diseño
    '4_diseno/plantilla_base_cinema/diseno_base.py': 'el diseño de la plantilla BASE nueva (arriba · principal · abajo · imagen × 3 variantes + simple), solo con Luxe Slide y Luxe Shine → diseno.json.',
    '4_diseno/plantilla_base_cinema/taller_base.py': 'funciones que corren DENTRO de Resolve (por el MCP) para construir y comprobar la plantilla base nueva.',
    '4_diseno/plantilla_base_cinema/generar.py': 'del .drt exportado por Resolve al .drb de la plantilla base nueva, y su instalación en plantillas_incluidas.',
    '4_diseno/plantilla_base_cinema/guia.py': 'construye DENTRO de Resolve el timeline-guía «Crea tu estilo» (.drt): cómo se arma un pack .drb.',
    '4_diseno/plantilla_base_cinema/hoja.py': 'hoja de contacto de la plantilla base nueva (variantes 1..3 y simple, vertical y horizontal).',
    '4_diseno/plantilla_base_cinema/medir_png.py': 'caja (ancho x alto, centro) del texto claro de cada fotograma de medida.',
    '4_diseno/plantillas_virales/diseno.py': 'el diseño de «Plantillas virales cinema»: tamaños, colores, posiciones y sets de los 6 packs → diseno.json.',
    '4_diseno/plantillas_virales/resolve_taller.py': 'funciones que corren DENTRO de Resolve: construir los timelines, importar y verificar los .drb de los packs.',
    '4_diseno/plantillas_virales/sintetizar_drb.py': 'arma un .drb (bin de Text+) a partir de un .drt, con la posición de cada clip.',
    '4_diseno/plantillas_virales/generar_prov.py': 'regenera los 12 .drb de «Plantillas virales cinema» desde sus .drt.',
    '4_diseno/plantillas_virales/instalar.py': 'copia los .drb/.drt de «Plantillas virales cinema» a plantillas_incluidas con su pack.json y posiciones.',
    '4_diseno/plantillas_virales/hoja.py': 'hoja de contacto (sets 1..6 y base) de un pack verificado en Resolve.',
    '4_diseno/plantillas_virales/medir.py': 'mide la caja de texto de las fotos de calibración (cal_v.json / cal_h.json).',
    '4_diseno/banner/crear_banner.py': 'dibuja 3_compilar/banner.jpg, el banner del instalador.',
    '4_diseno/icono/crear_icono.py': 'crea el icono del programa (2_recursos/logo_cinecaptions.png y .ico) desde el logo.',
    # ---------------------------------------------------------------- licencias (Administrador de Licencias, no va en el .exe)
    '5_licencias/administrador/administrador_licencias.py': 'Administrador de Licencias: arranque del panel del vendedor.',
    '5_licencias/administrador/control.py': 'Administrador de Licencias: servidor de control (Supabase): uso, equipos, avisos.',
    '5_licencias/administrador/dialogos.py': 'Administrador de Licencias: ventanas emergentes (Dar licencia, conectar, avisos).',
    '5_licencias/administrador/interfaz.py': 'Administrador de Licencias: componentes animados de la interfaz.',
    '5_licencias/administrador/modelo.py': 'Administrador de Licencias: configuración y modelo de datos (personas, licencias, ventas).',
    '5_licencias/administrador/paginas.py': 'Administrador de Licencias: páginas del panel (Inicio, Personas, Licencias...).',
    '5_licencias/administrador/plataformas.py': 'Administrador de Licencias: APIs de Lemon Squeezy, Hotmart, Gumroad y Polar.',
    '5_licencias/administrador/temas.py': 'Administrador de Licencias: temas de color y hoja de estilos.',
    '5_licencias/administrador/administrador.spec': 'Administrador de Licencias: receta de PyInstaller.',
    '5_licencias/administrador/CONSTRUIR_EXE.bat': 'Administrador de Licencias: crea el .exe portátil.',
    '5_licencias/administrador/INICIAR_MAC_LINUX.sh': 'Administrador de Licencias: lo abre en macOS o Linux.',
    '5_licencias/instalador/CONSTRUIR_INSTALADOR.bat': 'Administrador de Licencias: crea su instalador con NSIS.',
    '5_licencias/instalador/crear_imagenes.py': 'Administrador de Licencias: dibuja las imágenes de su instalador.',
    '5_licencias/instalador/instalador.nsi': 'Administrador de Licencias: receta del instalador (NSIS).',
    '5_licencias/programa/licencia_cliente.py': 'kit de licencias: forma rápida de usar cinema_licencias en un programa.',
    '5_licencias/programa/ejemplo_consola.py': 'kit de licencias: ejemplo sin ventanas.',
    '5_licencias/programa/ejemplo_integracion.py': 'kit de licencias: ejemplo con PySide6.',
    '5_licencias/programa/cinema_licencias/__init__.py': 'kit de licencias (cinema_licencias): lo que se importa.',
    '5_licencias/programa/cinema_licencias/__main__.py': 'kit de licencias: uso desde la línea de comandos.',
    '5_licencias/programa/cinema_licencias/base.py': 'kit de licencias: resultado, mensajes, ID del equipo y HTTP.',
    '5_licencias/programa/cinema_licencias/config.py': 'kit de licencias: configuración (cinema_licencias.json).',
    '5_licencias/programa/cinema_licencias/licencias.py': 'kit de licencias: la clase Licencias.',
    '5_licencias/programa/cinema_licencias/qt.py': 'kit de licencias: ventanas de activación y «Mi licencia» (PySide6).',
    '5_licencias/programa/cinema_licencias/servidor.py': 'kit de licencias: servidor de control y vigilancia.',
    '5_licencias/programa/cinema_licencias/tiendas.py': 'kit de licencias: Lemon Squeezy, Gumroad y Polar.',
    '5_licencias/programa/cinema_licencias/ventanas.py': 'kit de licencias: ventanas sin marco con botones dibujados.',
    '5_licencias/pruebas/simulador.py': 'pruebas: tiendas y servidor FALSOS para probar sin internet.',
    '5_licencias/pruebas/simulador_lemonsqueezy.py': 'pruebas: Lemon Squeezy FALSO para probar sin internet.',
    '5_licencias/pruebas/test_licencias.py': 'pruebas del kit y del Administrador (56 casos, sin internet).',
    '5_licencias/servidor/supabase_cinema.sql': 'servidor de control de licencias (Supabase/PostgreSQL): tablas y reglas.',
}

COMENTARIO = {'.py': '#', '.spec': '#', '.ps1': '#', '.sh': '#', '.lua': '--', '.sql': '--', '.cs': '//',
              '.nsi': ';', '.bat': 'rem'}


def _leer(p):
    datos = p.read_bytes()
    bom = datos.startswith(b'\xef\xbb\xbf')
    texto = datos[3:].decode('utf-8') if bom else datos.decode('utf-8')
    nl = '\r\n' if '\r\n' in texto else '\n'
    return texto.replace('\r\n', '\n'), bom, nl


def _escribir(p, texto, bom, nl):
    datos = texto.replace('\n', nl).encode('utf-8')
    p.write_bytes((b'\xef\xbb\xbf' if bom else b'') + datos)


def poner(rel, descripcion):
    p = RAIZ / rel
    if not p.exists():
        return 'falta'
    c = COMENTARIO[p.suffix.lower()]
    l1 = f'{c} {AUTOR}'
    l2 = f'{c} {rel} — {descripcion}'
    if p.suffix.lower() in ('.bat', '.ps1'):      # Windows PowerShell 5.1 y cmd leen estos sin BOM como ANSI
        l1 = l1.replace('·', '-')
        l2 = l2.replace('—', '-').replace('·', '-').replace('«', '"').replace('»', '"')
    texto, bom, nl = _leer(p)
    lineas = texto.split('\n')
    i = 0                                     # después del shebang, la línea de codificación o @echo off
    while i < len(lineas) and (lineas[i].startswith('#!') or 'coding' in lineas[i][:30] and lineas[i].startswith('#')
                               or lineas[i].lower().startswith('@echo off') or lineas[i].lower().startswith('chcp')):
        i += 1
    if i < len(lineas) and lineas[i].strip() == l1.strip():
        # la 2.ª línea ya es «<comentario> <ruta> — <qué es>» (quizá con una ruta de antes de mover
        # el archivo): se reemplaza, nunca se duplica
        sig = lineas[i + 1] if i + 1 < len(lineas) else ''
        if sig.startswith(f'{c} {rel}') or re.match(rf'^{re.escape(c)} \S[^—]*\.\w+ [—-] ', sig):
            if sig == l2:
                return 'igual'
            lineas[i + 1] = l2
        else:
            lineas.insert(i + 1, l2)
        _escribir(p, '\n'.join(lineas), bom, nl)
        return 'actualizado'
    lineas[i:i] = [l1, l2]
    _escribir(p, '\n'.join(lineas), bom, nl)
    return 'puesto'


def sin_encabezado():
    """Archivos de código que todavía no tienen el encabezado (para avisar al compilar)."""
    faltan = []
    for carpeta in ('1_codigo', '2_recursos/resolve_scripts', '2_recursos/motor_qwen', '3_compilar', '4_diseno', '5_licencias'):
        for p in (RAIZ / carpeta).rglob('*'):
            if p.is_file() and p.suffix.lower() in COMENTARIO and '__pycache__' not in p.parts and 'node_modules' not in p.parts:
                rel = p.relative_to(RAIZ).as_posix()
                if rel not in DESCRIPCIONES:
                    faltan.append(rel)
    return faltan


def main():
    cuenta = {}
    for rel, d in DESCRIPCIONES.items():
        r = poner(rel, d)
        cuenta[r] = cuenta.get(r, 0) + 1
        if r == 'falta':
            print('  (no existe)', rel)
    print('encabezados:', ', '.join(f'{k} {v}' for k, v in sorted(cuenta.items())))
    faltan = sin_encabezado()
    for rel in faltan:
        print('  SIN DESCRIPCIÓN (añádela en DESCRIPCIONES):', rel)
    return 1 if faltan else 0


if __name__ == '__main__':
    sys.exit(main())
