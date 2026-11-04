# CineCaptions · By Cinema Productions
# 1_codigo/registro_ayuda.py — traduce cada aviso o error del Registro a lenguaje claro: qué pasó, qué significa y qué hacer.
"""
explicar(entrada) -> Ayuda(titulo, que, pasos, impacto, tecnica)
  * titulo   frase corta y clara («Resolve no está listo»)
  * que      una o dos frases: qué pasó y por qué
  * pasos    lista de cosas concretas que probar, en orden
  * impacto  'bloquea' (GO no pudo terminar) · 'parcial' (algo quedó sin hacer) · 'ninguno' (solo informativo)
  * tecnica  el dato crudo (la última línea del error) para soporte
Las reglas se evalúan en orden: gana la primera que encaja con el mensaje, el origen o el detalle técnico.
"""
import re
from collections import namedtuple

from i18n import tr

Ayuda = namedtuple('Ayuda', 'titulo que pasos impacto tecnica')

# (patrón sobre «origen | mensaje | detalle», título, qué pasó, pasos, impacto)
_REGLAS = [
    # v5.5: «el script de Resolve corrió pero NO colocó nada» (colocacion.CAUSAS): GO deja la marca [causa:clave] en el detalle del error
    (r'\[causa:' + clave + r'\]', titulo, que, pasos, 'bloquea') for _p, clave, titulo, que, pasos, _r in __import__('colocacion').CAUSAS
] + [
    # v5.4.27: los fallos nuevos de Resolve Free / Mac / IA, que antes caían en el genérico «Algo no salió como se esperaba». Van ANTES de las reglas generales (gana la primera que encaja).
    (r'pantalla de proyectos|Organizador de proyectos|no mostr[oó] un proyecto abierto|No veo la ventana principal de DaVinci Resolve|sin proyecto abierto',
     'Resolve está en la pantalla de proyectos',
     'DaVinci Resolve se abrió pero sin un proyecto abierto (solo el Organizador de proyectos): ahí no hay menú de Scripts ni consola y CineCaptions no puede trabajar. '
     'CineCaptions intenta crear un proyecto vacío solo; si llegaste aquí, algo se lo impidió (un cuadro de diálogo de Resolve, o Resolve aún cargando).',
     ['En Resolve abre cualquier proyecto (doble clic) o pulsa «Crear proyecto» y espera a que se vea la página Edición.',
      'Cierra cualquier cuadro de diálogo que Resolve tenga abierto (novedades, licencia, actualización).',
      'Vuelve a soltar el video o a pulsar GO.'], 'bloquea'),
    # v5.5.6: Smart App Control de Windows 11 (error 0xc0e90002, «Bad Image») no deja cargar una librería sin firma digital (salud._bloqueo_de_windows)
    (r'Control inteligente de aplicaciones|Smart App Control|0xc0e90002',
     'Windows bloqueó una parte de CineCaptions',
     'El «Control inteligente de aplicaciones» (Smart App Control) de Windows 11 no deja cargar archivos de programas que aún no conoce y que no llevan '
     'firma digital. Bloqueó una librería de CineCaptions (la que lee el video) y sin ella GO no puede trabajar. No es un virus ni un archivo dañado.',
     ['Abre Configuración > Privacidad y seguridad > Seguridad de Windows > Control de aplicaciones y navegador > Configuración del control inteligente de aplicaciones y elige «Desactivado».',
      'Ojo: Windows no deja volver a activarlo sin reinstalar el sistema. Si prefieres no apagarlo, usa CineCaptions en otro equipo.',
      'Cierra y vuelve a abrir CineCaptions.'], 'bloquea'),
    (r'DLL load failed|is either not designed to run on Windows|no est[aá] dise[ñn]ad[oa] para ejecutarse en Windows|Bad Image',
     'Windows no dejó cargar una librería de CineCaptions',
     'Una librería del programa no cargó. En Windows 11 lo más común es el «Control inteligente de aplicaciones» o un antivirus que la bloquea (no es un virus).',
     ['Si tu Windows tiene el «Control inteligente de aplicaciones» activado o en evaluación: Configuración > Privacidad y seguridad > Seguridad de Windows > '
      'Control de aplicaciones y navegador > Configuración del control inteligente de aplicaciones > «Desactivado» (Windows no deja volver a activarlo sin reinstalar).',
      'Si usas un antivirus (Avast, AVG…), añade a sus excepciones la carpeta de CineCaptions: %LOCALAPPDATA%\\Programs\\CineCaptions.',
      'Si sigue, reinstala CineCaptions con el último instalador.'], 'bloquea'),
    (r'no tom[oó] el foco|no pulso teclas|consola de comandos de Resolve|\(F6\)|no escribo en ella',
     'Resolve no se dejó controlar',
     'En la versión gratuita de Resolve, CineCaptions arranca su Puente escribiendo en la consola de Resolve, y solo lo hace si Resolve tiene el foco (si no, las teclas irían a otra aplicación).',
     ['Deja Resolve al frente unos segundos al pulsar GO y no uses el teclado mientras CineCaptions trabaja.',
      'Cierra ventanas que roban el foco (avisos, chats, grabadores de pantalla).',
      'O arráncalo tú: Área de trabajo > Scripts > CineCaptions_Puente (en inglés: Workspace > Scripts).'], 'bloquea'),
    (r'Falta un clic en Resolve|Para colocar los subt[ií]tulos, en Resolve pulsa',
     'Los subtítulos están listos, falta un clic en Resolve',
     'CineCaptions generó los subtítulos pero Resolve (versión gratuita) no tenía el Puente activo para colocarlos solo.',
     ['En Resolve ve a Área de trabajo > Scripts > CineCaptions_Subtitulos (un clic) y se colocan en tu timeline.',
      'Para que la próxima vez se coloquen solos, deja abierto un proyecto en Resolve al pulsar GO: CineCaptions arranca el Puente por su cuenta.'], 'parcial'),
    (r'IA de texto.*(sin responder|fall[oó]|no pudo|desactivada)|tarda m[aá]s de lo normal|modelo ligero',
     'La IA de texto tardó demasiado o falló',
     'El modelo que corrige el texto y elige las palabras clave no respondió a tiempo (la tarjeta gráfica estaba ocupada o sin memoria). CineCaptions pasó al modelo ligero o a las reglas de siempre: '
     'los subtítulos salen igual, con menos finura en la corrección.',
     ['Cierra programas que usen la tarjeta gráfica (navegador con video, juegos, otro editor) y repite GO.',
      'Si repites GO sobre el mismo video, el resultado de la IA que sí terminó se reutiliza.',
      'Si pasa siempre, en Ajustes > Voz e IA elige el modelo más ligero.'], 'parcial'),
    (r'sin dar se[ñn]ales|sigue sin responder tras|parece atascado|lleva .* sin avanzar',
     'Un paso de GO se quedó atascado',
     'GO lleva demasiado tiempo en un paso sin avanzar (casi siempre esperando a Resolve o a la tarjeta gráfica). CineCaptions lo vigila y, si hace falta, cierra la conexión con Resolve y lo reintenta.',
     ['Mira si Resolve tiene un cuadro de diálogo abierto o está renderizando, y espera a que termine.',
      'Si el paso no avanza en un par de minutos, cierra y abre Resolve y repite GO.'], 'parcial'),
    (r'sin permiso de Accesibilidad|assistive|-25211|-1719|Accesibilidad para CineCaptions',
     'Falta el permiso de Accesibilidad (Mac)',
     'macOS no deja que CineCaptions pulse menús de DaVinci Resolve (arrancar el Puente, expandir la vista) hasta que le des el permiso de Accesibilidad.',
     ['Ajustes del Sistema > Privacidad y seguridad > Accesibilidad: activa CineCaptions (si ya está, quítalo y vuélvelo a añadir).',
      'Cierra y abre CineCaptions.',
      'Vuelve a pulsar GO.'], 'bloquea'),
    (r'No encuentro DaVinci Resolve en este Mac|open -a',
     'No encuentro DaVinci Resolve en este Mac',
     'CineCaptions intentó abrir DaVinci Resolve y macOS no lo encontró (no está instalado en Aplicaciones o tiene otro nombre).',
     ['Comprueba que DaVinci Resolve está en la carpeta Aplicaciones.',
      'Ábrelo tú con un proyecto y vuelve a pulsar GO.'], 'bloquea'),
    (r'no muestra el men[uú] [«"]?Scripts|sin_menu',
     'Resolve no muestra el menú de Scripts',
     'Resolve está abierto pero su menú Área de trabajo > Scripts no tiene CineCaptions_Puente: casi siempre es que no hay un proyecto abierto (la pantalla de proyectos no tiene ese menú) o que los scripts no están instalados.',
     ['Abre un proyecto en Resolve y espera a que se vea la página Edición.',
      'En CineCaptions: Ajustes > «Reinstalar scripts de Resolve» y vuelve a pulsar GO.'], 'bloquea'),
    (r'La interfaz estuvo sin responder|congelaci[oó]n',
     'La ventana se congeló un momento',
     'La ventana de CineCaptions dejó de responder unos segundos (el equipo estaba ocupado con la voz, la IA o Resolve).',
     ['No hace falta hacer nada. Si pasa muchas veces, activa «Reducir animaciones» en Ajustes > Interfaz.'], 'ninguno'),
    (r'No se pudo actualizar|no pude lanzar el instalador|No pude abrir el instalador|No puedo reemplazar la versi[oó]n instalada',
     'No se pudo actualizar',
     'El instalador no pudo reemplazar la versión instalada: algún archivo estaba en uso (DaVinci Resolve abierto desde CineCaptions, el antivirus o una copia de CineCaptions aún abierta).',
     ['Cierra CineCaptions y DaVinci Resolve del todo.',
      'Pulsa «Reintentar» en el instalador (o vuelve a abrirlo).',
      'Si falla otra vez, reinicia sesión de Windows y ábrelo de nuevo.'], 'bloquea'),
    (r'Resolve no arm[oó] el timeline|No pude armar el proyecto con tu video',
     'No pude preparar tu video en Resolve',
     'Para cada video soltado CineCaptions crea un proyecto y un timeline en Resolve y algo falló en ese paso (el detalle técnico de abajo dice cuál). No se tocó ningún otro timeline tuyo.',
     ['Mira el detalle técnico: dice si falta Resolve, si no hay proyecto o si el video no se pudo importar.',
      'Comprueba que el video se reproduce en un reproductor normal y que no está en una unidad desconectada.',
      'Cierra los cuadros de diálogo de Resolve y vuelve a soltar el video.'], 'bloquea'),
    (r'InvalidDataError|Invalid data found|moov atom not found|no es un (video|audio|archivo)|Error opening input',
     'El archivo no se puede leer como video o audio',
     'El archivo está dañado, incompleto (una descarga cortada) o no es de verdad un video/audio aunque se llame así.',
     ['Ábrelo en un reproductor: si no se reproduce, vuelve a descargarlo o a exportarlo.',
      'Si viene de internet o de un móvil, copia el archivo completo al disco local antes de soltarlo.',
      'Prueba con otro archivo para ver si el problema es solo de este.'], 'bloquea'),
    (r'ya no est[aá] donde estaba|Archivo no encontrado|File not found',
     'El video ya no está donde estaba',
     'Resolve (y CineCaptions) apuntan a un archivo que se movió, se renombró o se borró: Resolve lo muestra como «Archivo no encontrado» y por eso no hay audio.',
     ['Devuelve el archivo a su carpeta original con su nombre de siempre (o suéltalo otra vez en la ventana de CineCaptions).',
      'Si el archivo está en una unidad externa o de red, comprueba que esté conectada.',
      'Vuelve a pulsar GO.'], 'bloquea'),
    (r'no devolvi[oó] palabras|sin voz|no hay voz',
     'No se oyó voz en el audio',
     'La transcripción terminó sin encontrar palabras: el audio está vacío, solo tiene música o ruido, o es otro idioma del elegido.',
     ['Comprueba que el video suena y que se oye a alguien hablando.',
      'Si el idioma no es el que CineCaptions espera, elígelo en el chip «Idioma» de Inicio (en vez de «Detectar»).',
      'Si el video está en Resolve, mira que su audio no esté silenciado ni «Archivo no encontrado».'], 'bloquea'),
    (r'no pude preparar el pack|no pude crear el bin|ImportFolderFromFile',
     'Resolve no pudo cargar el pack de estilos',
     'El estilo elegido guarda sus piezas en un bin del Media Pool y Resolve no dejó crearlo o importarlo.',
     ['Espera unos segundos a que Resolve termine lo que esté haciendo y vuelve a pulsar GO.',
      'Abre el Media Pool en Resolve y borra el bin «CC · …» de ese estilo si está a medias; se recrea solo.',
      'Si sigue fallando, elige otro estilo en el chip «Estilo» de Inicio y avisa a soporte con el informe.'], 'bloquea'),
    (r'no cre[oó] el proyecto|no_creo|CreateProject',
     'Resolve no pudo crear el proyecto de CineCaptions',
     'Para cada video nuevo CineCaptions crea un proyecto en Resolve y Resolve no lo permitió (nombre ocupado o base de datos ocupada).',
     ['Cierra los cuadros de diálogo que haya abiertos en Resolve y vuelve a pulsar GO.',
      'Comprueba en el Project Manager de Resolve que no haya un proyecto «CineCaptions» a medio borrar.',
      'En Ajustes puedes elegir que GO trabaje en el proyecto que tengas abierto.'], 'bloquea'),
    (r'Resolve se cay[oó]',
     'DaVinci Resolve se cerró de golpe (se cayó)',
     'Resolve tuvo un error interno mientras CineCaptions cambiaba el timeline y se cerró solo (deja un volcado en su carpeta de registros).',
     ['Abre DaVinci Resolve con tu proyecto: guarda solo cada pocos minutos, así que lo de antes sigue ahí.',
      'Si fue con «Listo» de Efectos › Posición, tus marcas siguen guardadas: pulsa «Listo» otra vez.',
      'Mientras CineCaptions trabaja, no reproduzcas ni edites en Resolve; si se repite, avisa a soporte con el informe.'], 'bloquea'),
    (r'is not running|Resolve se cerr|launch_resolve|DaVinci Resolve no est',
     'Resolve se cerró o no está abierto',
     'CineCaptions perdió el contacto con DaVinci Resolve en mitad del trabajo (Resolve se cerró, se colgó o aún no había terminado de abrir).',
     ['Abre DaVinci Resolve y espera a que cargue por completo (hasta ver el timeline).',
      'Vuelve a pulsar GO: lo que ya estaba transcrito se rehace en unos segundos.',
      'Si Resolve se cierra solo, anota qué estabas haciendo y mira Ajustes > Registro: ahí queda el momento exacto.'], 'bloquea'),
    (r'ResolveMCP no contest|no contest[oó] a tools/call',
     'Resolve no respondió a tiempo',
     'Resolve estaba ocupado (cargando un proyecto, renderizando o con un cuadro de diálogo abierto) y no contestó a CineCaptions.',
     ['Mira si Resolve tiene algún cuadro de diálogo abierto y ciérralo.',
      'Espera a que termine lo que esté haciendo y vuelve a pulsar GO.',
      'Si pasa seguido, cierra y abre Resolve.'], 'bloquea'),
    (r'No hay ning[uú]n timeline activo',
     'No hay un timeline abierto en Resolve',
     'El script de Resolve no encontró un timeline activo donde colocar los títulos.',
     ['En Resolve, abre el timeline que quieres subtitular (doble clic en el Media Pool).',
      'O suelta el video en la ventana de CineCaptions y deja que prepare él mismo el proyecto.'], 'bloquea'),
    # v5.55 (Puente 1.0.42): un Free sin loadfile ni dofile en el que tampoco funcionan bmd.readfile, RunScript ni la consola. Va ANTES que la
    # del Puente perdido: antes esto llegaba como «El puente no respondió en 240 s» y su tarjeta mandaba a relanzar un Puente que no puede leer.
    (r'no deja al Puente leer|sin_lectura|sin_cargador',
     'El Puente no puede leer los trabajos en este Resolve',
     'A los scripts de esta versión de DaVinci Resolve les faltan las funciones con las que el Puente lee los trabajos de CineCaptions (loadfile y dofile), y los caminos de respaldo (bmd.readfile, RunScript y la consola de Resolve) tampoco respondieron.',
     ['Actualiza DaVinci Resolve a su última versión y vuelve a abrirlo.',
      'Vuelve a lanzar CineCaptions_Puente: Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Puente.',
      'Si sigue igual, manda el informe a soporte (Ajustes › Registro): la primera línea del Puente dice qué caminos tiene tu Resolve.'], 'bloquea'),
    (r'Puente perdi|caduca sola|Puente dej[oó] de responder|puente no respondi|Bridge lost',
     'El Puente de Resolve perdió la conexión',
     'En la versión gratuita de Resolve el Puente (el script que deja trabajar a CineCaptions dentro de Resolve) pierde su conexión solo, cada cierto tiempo.',
     ['Si tienes DaVinci Resolve STUDIO no necesitas el Puente: en Resolve ve a Preferencias > Sistema > General, pon «External scripting using» en «Local», cierra Resolve del todo y ábrelo otra vez.',
      'Con Resolve gratuito: Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Puente (en inglés: Workspace > Scripts). En Mac, CineCaptions intenta pulsarlo solo si le das el permiso de Accesibilidad.',
      'Vuelve a pulsar GO.',
      'Si sigue pasando, cierra DaVinci Resolve por completo y ábrelo otra vez.'], 'bloquea'),
    (r'sin_resolve|resolve.*(no está abierto|no responde|cerrado|no se (pudo|puede) conectar)|no (pude|se pudo) (abrir|conectar).*resolve|scripting.*(desactiv|disabled)',
     'Resolve no está listo',
     'CineCaptions habla con DaVinci Resolve a través de su API de scripting y no obtuvo respuesta.',
     ['Abre DaVinci Resolve y espera a que cargue por completo.',
      'Abre un proyecto con un timeline y deja el timeline a la vista.',
      'En Resolve: Preferencias > General > «Uso de scripting externo» = Local.',
      'Vuelve a pulsar GO.'], 'bloquea'),
    # v5.61: «Listo» de «detrás de ti» con otro timeline abierto caía en la de abajo («No pude traer el audio del timeline»)
    (r'abierto otro timeline',
     'En Resolve está abierto otro timeline',
     'Lo que hay en V1 del timeline abierto en Resolve no es lo que dejó tu último GO de este video.',
     ['En Resolve, abre el timeline que dice el aviso (el de tu último GO con este video).',
      'Vuelve a darle a «Listo».'], 'bloquea'),
    (r'GO · timeline|timeline|línea de tiempo',
     'No pude traer el audio del timeline',
     'Resolve no entregó el audio de tu timeline (o no hay uno activo con clips de audio).',
     ['Abre el proyecto en Resolve y haz clic en el timeline que quieres subtitular.',
      'Comprueba que el timeline tiene audio (no está silenciado ni vacío).',
      'También puedes soltar un vídeo en la ventana de CineCaptions y pulsar GO otra vez.'], 'bloquea'),
    # v5.54: el chequeo de arranque de un motor («Falla al iniciar: Motor de IA (Qwen3) — faltan 63 librerías…») caía en la de abajo por «Qwen»
    # y salía como «La transcripción no pudo terminar», con pasos de un audio dañado, sin haber transcrito nada
    (r'Falla al iniciar: Motor (de IA|auxiliar)',
     'A un motor de IA le faltan librerías',
     'Al abrirse, CineCaptions comprobó sus motores de IA y a uno le faltan librerías o no tiene la versión que necesita: una instalación o una actualización quedó a medias. Todavía no se ha transcrito nada; al pulsar GO la voz prueba con el otro motor.',
     ['Si es el motor de IA (Qwen3): en Ajustes › General › Motor de voz pulsa «Reparar el motor» (descarga lo que falta; necesita internet).',
      'Si es el motor auxiliar (Whisper): reinstala CineCaptions con el último instalador, que pone al día sus librerías (se conservan tus ajustes).',
      'Si el antivirus o el Control inteligente de aplicaciones de Windows bloquea la descarga, permite CineCaptions y repite.'], 'parcial'),
    # v5.64: una librería que falta en GO («el motor de IA (Qwen3) no arrancó: ModuleNotFoundError: No module named 'transformers'») caía en la
    # de la voz de abajo y mandaba a revisar el audio; la regla de «Falta un componente» llegaba tarde
    (r'ModuleNotFoundError|No module named',
     'Falta una librería de CineCaptions',
     'Una parte del programa (casi siempre un motor de IA) no encontró una de sus librerías: una instalación o una actualización quedó a medias, '
     'o el antivirus la quitó. No es un problema de tu video.',
     ['Si es el motor de IA (Qwen3): en Ajustes › General › Motor de voz pulsa «Reparar el motor» (descarga lo que falta; necesita internet).',
      'Si no, reinstala CineCaptions con el instalador más reciente (se conservan tus ajustes).',
      'Añade la carpeta de CineCaptions a las excepciones de tu antivirus.'], 'bloquea'),
    # v5.64: las librerías de CUDA que faltan se bajan solas (vigilancia.preparar_gpu_voz); antes caía en «Falla al iniciar» con pasos de reinstalar
    (r'GPU para la voz',
     'La voz va por la CPU mientras se prepara la GPU',
     'A tu tarjeta NVIDIA le faltan las librerías de CUDA (cuBLAS y cuDNN) con las que Whisper transcribe en la GPU. CineCaptions las descarga solo '
     '(≈1,3 GB, una vez); mientras, la voz se transcribe en la CPU, más despacio. No hace falta hacer nada.',
     ['Si la descarga no pudo terminar, abre CineCaptions con internet: lo reintenta solo y sigue donde quedó.',
      'Si el antivirus bloquea la descarga, permite CineCaptions y vuelve a abrirlo.'], 'ninguno'),
    (r'GO · voz|transcri|whisper|qwen|motor de voz',
     'La transcripción no pudo terminar',
     'El motor de voz se detuvo antes de entregar el texto.',
     ['Comprueba que el archivo de audio no esté dañado y se reproduce.',
      'En Ajustes > Voz prueba el otro motor (Qwen3-ASR o Whisper).',
      'Cierra otros programas que usen la tarjeta gráfica y vuelve a intentarlo.'], 'bloquea'),
    (r'out of memory|cuda.*(memory|error)|MemoryError|CUDA_ERROR|no hay memoria',
     'Se acabó la memoria',
     'El modelo de voz necesitó más memoria (RAM o de la tarjeta gráfica) de la que había libre.',
     ['Cierra programas pesados (navegador, otros editores) y reintenta.',
      'En Ajustes > Voz elige el modelo más ligero.',
      'Para audios muy largos, prueba por partes.'], 'bloquea'),
    (r'ffmpeg|ffprobe|códec|codec|no (pude|se pudo) (leer|extraer) el audio',
     'No pude leer el audio',
     'La herramienta que convierte el audio falló o no reconoce el formato.',
     ['Prueba con otro archivo (mp4, wav o mp3 estándar).',
      'Si el archivo está en una unidad externa o en la nube, cópialo al disco local.',
      'Reinstala CineCaptions si el mensaje dice que falta ffmpeg.'], 'bloquea'),
    (r'sin conexi[oó]n|ConnectionError|URLError|getaddrinfo|Name or service|SSL|timed out connecting|ConnectTimeout|NameResolution',
     'Sin conexión a internet',
     'Algo necesitó descargar un recurso y la red no respondió. El resto del programa funciona.',
     ['Comprueba tu conexión y que ningún firewall o VPN bloquee a CineCaptions.',
      'Los recursos que faltan se reintentan solos la próxima vez que abras el programa.'], 'parcial'),
    (r'Timeout|timed out|tiempo (de espera )?agotado|TimeoutError',
     'Tardó demasiado y se canceló',
     'Una operación (normalmente Resolve o una descarga) no respondió a tiempo.',
     ['Si Resolve está ocupado (renderizando o cargando), espera a que termine.',
      'Cierra los cuadros de diálogo abiertos dentro de Resolve.',
      'Vuelve a intentarlo.'], 'bloquea'),
    (r'PermissionError|Acceso denegado|Access is denied|WinError 5\b|WinError 32|being used by another process|otro proceso',
     'El sistema no dejó escribir o abrir el archivo',
     'El archivo está abierto en otro programa o la carpeta está protegida.',
     ['Cierra el archivo en el otro programa (Resolve, explorador, antivirus).',
      'Evita carpetas protegidas como Archivos de programa; usa Documentos o el escritorio.',
      'Si persiste, ejecuta CineCaptions como administrador una vez.'], 'bloquea'),
    (r'FileNotFoundError|No such file|no se encuentra|no existe el archivo|WinError 2\b|WinError 3\b',
     'No encuentro un archivo',
     'Un archivo que CineCaptions esperaba ya no está donde estaba (movido, borrado o en una unidad desconectada).',
     ['Comprueba que el archivo o la unidad externa siguen disponibles.',
      'Vuelve a soltar el archivo en la ventana o haz GO con tu timeline abierto en Resolve.'], 'bloquea'),
    (r'JSONDecodeError|Expecting value|Extra data|Unterminated string|archivo (dañado|corrupto)',
     'Un archivo de datos está dañado',
     'Un archivo de ajustes o de caché no se puede leer (quizá se cortó al guardarlo).',
     ['No hace falta hacer nada: CineCaptions lo recrea con valores por defecto.',
      'Si te falta una configuración, restáurala desde Ajustes > General > Copias.'], 'parcial'),
    (r'ModuleNotFoundError|ImportError|DLL load failed',
     'Falta un componente del programa',
     'Una pieza interna no se instaló bien o la bloqueó un antivirus.',
     ['Reinstala CineCaptions con el instalador más reciente.',
      'Añade la carpeta de CineCaptions a las excepciones de tu antivirus.'], 'bloquea'),
    (r'licencia|license|clave de activaci',
     'Problema con la licencia',
     'No se pudo comprobar o activar la licencia.',
     ['Revisa que la clave esté bien escrita en Ajustes > Licencia.',
      'Comprueba tu conexión: la activación necesita internet una vez.'], 'bloquea'),
    (r'ortograf|corrección de texto|correcci[oó]n',
     'No se pudo corregir la ortografía',
     'El corrector de texto falló. Los subtítulos se generan igual, solo que sin esa corrección.',
     ['Puedes seguir trabajando: revisa el texto a mano en Creativo.',
      'Si se repite, desactiva la corrección en Ajustes.'], 'parcial'),
    (r'emoji',
     'Los emojis animados no se descargaron',
     'Los emojis animados se bajan de internet la primera vez; sin conexión se usan los estáticos.',
     ['Conéctate a internet y vuelve a abrir CineCaptions: se reintenta solo.'], 'parcial'),
    (r'HUD de Inicio|Escena de Inicio|escena_go|orbe',
     'Un efecto visual de Inicio falló',
     'Un adorno animado de la pantalla Inicio tuvo un fallo. No afecta a los subtítulos.',
     ['No hace falta hacer nada.',
      'Si se repite mucho, activa «Reducir animaciones» en Ajustes > Interfaz.'], 'ninguno'),
    (r'^Qt\b|qt\.|QObject|QWidget|QPainter|QFont|QPixmap',
     'Aviso interno de la interfaz',
     'Qt (la librería gráfica) avisó de algo menor. Casi siempre no tiene consecuencias.',
     ['Si la interfaz se ve y se comporta bien, ignóralo.'], 'ninguno'),
    (r'KeyError|IndexError|AttributeError|TypeError|ValueError|NoneType|UnboundLocalError|NameError|AssertionError|RuntimeError|ZeroDivisionError',
     'Error interno del programa',
     'Hubo un fallo inesperado de programación; no es culpa de tu archivo ni de tu equipo.',
     ['Vuelve a intentarlo: a veces fue algo puntual.',
      'Si se repite, pulsa «Copiar informe» aquí abajo y envíalo a soporte: trae los datos para arreglarlo.'], 'bloquea'),
    (r'excepción sin atrapar|Traceback|Exception',
     'Fallo inesperado',
     'Algo salió mal y el programa no tenía previsto ese caso.',
     ['Vuelve a intentarlo.',
      'Si se repite, pulsa «Copiar informe» aquí abajo y envíalo a soporte.'], 'bloquea'),
    # v5.5.6: antes «Falla al iniciar: …» caía en la de abajo («El programa arrancó · No afecta»), en rojo y contradictorio
    (r'Falla al iniciar',
     'Una parte de CineCaptions no cargó al abrirse',
     'Al abrirse, CineCaptions comprueba sus librerías y motores. Esta no cargó o no es la versión esperada: lo que dependa de ella puede fallar.',
     ['Cierra y vuelve a abrir CineCaptions.',
      'Si se repite, reinstala CineCaptions con el último instalador (se conservan tus ajustes).',
      'Si sigue igual, pulsa «Copiar este error» y envíalo a soporte.'], 'parcial'),
    (r'CineCaptions iniciado|sesión|inici',
     'El programa arrancó',
     'Anotación informativa: CineCaptions se abrió correctamente.', [], 'ninguno'),
]
_COMPILADAS = [(re.compile(p, re.I), t, q, s, i) for p, t, q, s, i in _REGLAS]


def _ultima_linea(texto):
    lineas = [l.strip() for l in str(texto or '').strip().splitlines() if l.strip()]
    return lineas[-1] if lineas else ''


def explicar(e):
    """Una `Ayuda` para la entrada `e` (registro.Entrada). Nunca lanza."""
    try:
        mensaje = e.mensaje or ''
        origen = e.origen or ''
        detalle = e.detalle or ''
        tecnica = _ultima_linea(detalle) or mensaje
        # un mensaje que es solo un número es el código de salida de un proceso (p. ej. el script de Resolve)
        if re.fullmatch(r'-?\d{1,4}', mensaje.strip()):
            codigo = mensaje.strip()
            extra = (origen + ' | ') if origen else ''
            for patron, titulo, que, pasos, impacto in _COMPILADAS:
                if patron.search(extra):
                    return Ayuda(tr(titulo), tr(que) + ' ' + tr('(El programa externo terminó con el código {c}, sin más explicación.)', c=codigo),
                                 [tr(p) for p in pasos], impacto, tecnica)
            return Ayuda(tr('Un proceso terminó con el código {c}', c=codigo),
                         tr('Un programa auxiliar terminó con un error pero sin explicar el motivo.'),
                         [tr('Vuelve a intentarlo.'), tr('Si se repite, copia el informe y envíalo a soporte.')],
                         'bloquea' if e.nivel == 'error' else 'parcial', tecnica)
        texto = f'{origen} | {mensaje} | {detalle[-1500:]}'
        for patron, titulo, que, pasos, impacto in _COMPILADAS:
            if patron.search(texto):
                if e.nivel == 'info' and impacto != 'ninguno':
                    break
                return Ayuda(tr(titulo), tr(que), [tr(p) for p in pasos], impacto, tecnica)
        if e.nivel == 'error':
            return Ayuda(tr('Algo no salió como se esperaba'), tr('CineCaptions encontró un problema que no reconoce. El mensaje original está abajo.'),
                         [tr('Vuelve a intentarlo.'), tr('Si se repite, pulsa «Copiar informe» y envíalo a soporte.')], 'bloquea', tecnica)
        if e.nivel == 'aviso':
            return Ayuda(tr('Aviso'), tr('Algo no quedó del todo como se esperaba, pero el programa siguió funcionando.'), [], 'parcial', tecnica)
        return Ayuda(tr('Información'), '', [], 'ninguno', tecnica)
    except Exception:
        return Ayuda(tr('Anotación'), '', [], 'ninguno', getattr(e, 'mensaje', ''))


ETIQUETA_IMPACTO = {
    'bloquea': 'Detuvo la tarea',
    'parcial': 'Algo quedó sin hacer',
    'ninguno': 'No afecta a tu trabajo',
}
