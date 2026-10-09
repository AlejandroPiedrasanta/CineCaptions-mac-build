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
      'Abre el Media Pool en Resolve y borra el bin «RCS · …» de ese estilo si está a medias; se recrea solo.',
      'Si sigue fallando, elige otro estilo en el chip «Estilo» de Inicio y avisa a soporte con el informe.'], 'bloquea'),
    (r'no cre[oó] el proyecto|no_creo|CreateProject',
     'Resolve no pudo crear el proyecto de CineCaptions',
     'Para cada video nuevo CineCaptions crea un proyecto en Resolve y Resolve no lo permitió (nombre ocupado o base de datos ocupada).',
     ['Cierra los cuadros de diálogo que haya abiertos en Resolve y vuelve a pulsar GO.',
      'Comprueba en el Project Manager de Resolve que no haya un proyecto «CineCaptions» a medio borrar.',
      'En Ajustes puedes elegir que GO trabaje en el proyecto que tengas abierto.'], 'bloquea'),
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
    (r'Puente perdi|caduca sola|Puente dej[oó] de responder|puente no respondi|Bridge lost',
     'El Puente de Resolve perdió la conexión',
     'En la versión gratuita de Resolve el Puente (el script que deja trabajar a CineCaptions dentro de Resolve) pierde su conexión solo, cada cierto tiempo.',
     ['Si tienes DaVinci Resolve STUDIO no necesitas el Puente: en Resolve ve a Preferencias > Sistema > General, pon «External scripting using» en «Local», cierra Resolve del todo y ábrelo otra vez.',
      'Con Resolve gratuito: Área de trabajo > Scripts > Utility > CineCaptions_Puente (en inglés: Workspace > Scripts > Utility). En Mac, CineCaptions intenta pulsarlo solo si le das el permiso de Accesibilidad.',
      'Vuelve a pulsar GO.',
      'Si sigue pasando, cierra DaVinci Resolve por completo y ábrelo otra vez.'], 'bloquea'),
    (r'sin_resolve|resolve.*(no está abierto|no responde|cerrado|no se (pudo|puede) conectar)|no (pude|se pudo) (abrir|conectar).*resolve|scripting.*(desactiv|disabled)',
     'Resolve no está listo',
     'CineCaptions habla con DaVinci Resolve a través de su API de scripting y no obtuvo respuesta.',
     ['Abre DaVinci Resolve y espera a que cargue por completo.',
      'Abre un proyecto con un timeline y deja el timeline a la vista.',
      'En Resolve: Preferencias > General > «Uso de scripting externo» = Local.',
      'Vuelve a pulsar GO.'], 'bloquea'),
    (r'GO · timeline|timeline|línea de tiempo',
     'No pude traer el audio del timeline',
     'Resolve no entregó el audio de tu timeline (o no hay uno activo con clips de audio).',
     ['Abre el proyecto en Resolve y haz clic en el timeline que quieres subtitular.',
      'Comprueba que el timeline tiene audio (no está silenciado ni vacío).',
      'También puedes soltar un vídeo en la ventana de CineCaptions y pulsar GO otra vez.'], 'bloquea'),
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
      'Vuelve a elegir el archivo desde el botón «Obtener» o suéltalo en la ventana.'], 'bloquea'),
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
