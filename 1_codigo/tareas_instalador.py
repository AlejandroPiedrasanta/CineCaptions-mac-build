# CineCaptions · By Cinema Productions
# 1_codigo/tareas_instalador.py — lo que el instalador pide al programa (--tarea verificar/scripts/fuentes/modelo/motor_ia...).
"""
tareas_instalador.py
--------------------
Lo que el instalador (Instalar_CineCaptions.exe) le pide al
programa YA INSTALADO, sin abrir la ventana:

    "CineCaptions.exe" --tarea verificar <estado.txt>
    "CineCaptions.exe" --tarea scripts   <estado.txt>
    "CineCaptions.exe" --tarea quitar_scripts <estado.txt>   (al desinstalar)
    "CineCaptions.exe" --tarea fuentes   <estado.txt>
    "CineCaptions.exe" --tarea modelo    <estado.txt>

Y una para soporte (no la usa el instalador): transcribe un audio de punta a
punta con el .exe compilado, sin tocar la ventana ni Resolve:

    "CineCaptions.exe" --tarea transcribir <estado.txt> <audio> [idioma]

Por que el instalador no lo hace por su cuenta
==============================================
Instalar los scripts en Resolve, las tipografias de las plantillas o el
modelo de Whisper ya lo sabe hacer el programa (instalador_scripts,
instalar_fuentes, faster_whisper). Si el instalador tuviera su propia
copia de esa logica, se desactualizaria en la primera version que cambie
una carpeta o un nombre de script. Asi hay una sola verdad: la del .exe
que se acaba de instalar.

Y "verificar" es la unica forma de saber, EN EL EQUIPO DEL CLIENTE, que el
.exe compilado arranca sus DLL (ctranslate2, onnxruntime, av, Qt):
cada una puede fallar por motivos que en el equipo donde se compila no se
ven (CPU sin AVX, antivirus, Windows recortado).

Protocolo con el instalador
===========================
Cada tarea agrega lineas UTF-8 a <estado.txt>:
    PROGRESO|NN|texto   avance 0-100 de la tarea
    INFO|texto          algo que conviene mostrar en el registro
    OK|texto            termino bien (ultima linea)
    ERROR|texto         no se pudo (ultima linea)
y sale con codigo 0 (OK) o 1 (ERROR). El instalador lee el archivo
mientras la tarea corre: no hay consola (el .exe es de ventana).
"""
import os
import sys
import threading
import time
import traceback
from pathlib import Path

TAREAS = ('verificar', 'scripts', 'quitar_scripts', 'fuentes', 'modelo', 'motor_ia', 'motor_compat', 'transcribir', 'sonda_resolve')
# v5.1: Whisper queda de respaldo (el motor principal es Qwen3-ASR, motor_ia)
MODELO_WHISPER = 'large-v3-turbo'
MODELO_BYTES_APROX = 1_620_000_000


class _Estado:
    """Escribe el archivo de estado que lee el instalador."""

    def __init__(self, ruta):
        self.ruta = Path(ruta) if ruta else None
        self.final = None

    def _linea(self, *partes):
        texto = '|'.join(str(p).replace('\r', ' ').replace('\n', ' ')
                         for p in partes)
        if self.ruta is None:
            print(texto)
            return
        for _ in range(20):
            try:
                with open(self.ruta, 'a', encoding='utf-8') as f:
                    f.write(texto + '\n')
                return
            except OSError:
                time.sleep(0.05)

    def progreso(self, pct, texto=''):
        self._linea('PROGRESO', max(0, min(100, int(pct))), texto)

    def info(self, texto):
        self._linea('INFO', texto)

    def ok(self, texto=''):
        self.final = 0
        self._linea('OK', texto)

    def error(self, texto):
        self.final = 1
        self._linea('ERROR', texto)


def ejecutar(argv):
    """Punto de entrada desde main(). Devuelve el codigo de salida."""
    i = argv.index('--tarea')
    tarea = argv[i + 1] if len(argv) > i + 1 else ''
    estado = _Estado(argv[i + 2] if len(argv) > i + 2 else None)
    if tarea not in TAREAS:
        estado.error(f'Tarea desconocida: {tarea!r} (validas: {", ".join(TAREAS)})')
        return 1
    try:
        globals()['_tarea_' + tarea](estado, *argv[i + 3:])
    except Exception as exc:
        estado.info(traceback.format_exc().strip().splitlines()[-1])
        estado.error(f'{type(exc).__name__}: {exc}')
    if estado.final is None:
        estado.ok()
    return estado.final


# ---------------------------------------------------------------------------
# sonda_resolve: ¿acepta Resolve la API externa? (la pide resolve_bridge.conectar)
# ---------------------------------------------------------------------------
def _tarea_sonda_resolve(estado):
    """v5.4.45: en Resolve Free dvr.scriptapp() tarda ~4 s SIN soltar el GIL; corrido aqui, en un proceso aparte,
    no congela la ventana. Escribe OK|ok, OK|none, OK|hueco u OK|error: ..."""
    import resolve_bridge
    estado.ok(resolve_bridge._sondear_aqui())


# ---------------------------------------------------------------------------
# verificar: que el programa compilado puede cargar todo lo suyo
# ---------------------------------------------------------------------------
def _base_recursos():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / '2_recursos'


def _tarea_motor_compat(estado):
    """Instala Python 3.14.9 y las ruedas que no pueden ir en Python 3.15."""
    import motor_compat

    def progreso(fraccion, texto=''):
        estado.progreso(fraccion * 100, texto)

    def aviso(texto):
        estado.info(texto)

    datos = motor_compat.instalar(progreso=progreso, aviso=aviso)
    estado.progreso(100)
    estado.ok(f"Python {datos.get('python', '3.14.9')} y dependencias del motor instalados")


def _tarea_verificar(estado):
    import tempfile
    import wave
    base = _base_recursos()
    fallos, avisos = [], []

    pruebas = []

    def prueba(nombre, critica=True):
        def registrar(funcion):
            pruebas.append((nombre, critica, funcion))
            return funcion
        return registrar

    @prueba('Archivos del programa')
    def _():
        faltan = [n for n in ('resolve_scripts', 'locales', 'plantillas_incluidas',
                              'fonts', 'sfx_library', 'emojis', 'logo_cinecaptions.png',
                              'motor_qwen/motor_qwen.py', 'motor_qwen/motor_texto.py',
                              'motor_qwen/requisitos_motor_qwen.txt',
                              'motor_compat/worker.py', 'motor_compat/requirements.txt',
                              'resolve_scripts/CineCaptions - Vista Real.py')
                  if not (base / n).exists()]
        if faltan:
            raise RuntimeError('faltan: ' + ', '.join(faltan))

    @prueba('Ventanas (Qt)')
    def _():
        # v5.0.0: la interfaz es PySide6. Se arranca la aplicacion de verdad
        # (el plugin de ventanas del sistema, no uno de pruebas), se cargan
        # las tipografias de la interfaz y se DIBUJA una ventana en memoria,
        # sin mostrarla: si falta una DLL de Qt o el plugin, falla aqui.
        import qt_kit
        from PySide6.QtWidgets import QApplication
        app = qt_kit.crear_app(['cinecaptions'], carpeta_fuentes=base / 'fonts')
        if not isinstance(app, QApplication):
            raise RuntimeError('no se pudo crear la aplicación')
        if not qt_kit.familia_ui().startswith('Inter'):
            raise RuntimeError('no cargó la tipografía Inter de fonts/')
        prueba_w = qt_kit.Tarjeta(titulo='CineCaptions')
        prueba_w.resize(320, 120)
        if prueba_w.grab().isNull():
            raise RuntimeError('no pudo dibujar una ventana')
        prueba_w.deleteLater()

    @prueba('Imágenes y tipografías (Pillow)')
    def _():
        from PIL import ImageFont
        fuentes = sorted((base / 'fonts').glob('*.[ot]tf'))
        if fuentes:
            ImageFont.truetype(str(fuentes[0]), 24)

    @prueba('Lectura de audio y vídeo (PyAV)')
    def _():
        import av
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / 'silencio.wav'
            with wave.open(str(ruta), 'wb') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16000)
                w.writeframes(b'\x00\x00' * 8000)
            with av.open(str(ruta)) as contenedor:
                audio = contenedor.streams.audio[0]
                # PyAV 19 espera índices de stream en decode(audio=...), no el objeto AudioStream.
                if next(contenedor.decode(audio=audio.index), None) is None:
                    raise RuntimeError('no decodificó el silencio de prueba')

    @prueba('Motor auxiliar Whisper, Argos y ONNX', critica=False)
    def _():
        import motor_compat
        if not motor_compat.instalado():
            raise RuntimeError('Python 3.14 auxiliar aún no está instalado')
        datos = motor_compat.verificar()
        faltan = motor_compat.faltan_requisitos()
        if faltan:
            raise RuntimeError('faltan versiones: ' + ', '.join(faltan[:5]))
        if datos.get('python') != '3.14.9':
            raise RuntimeError('se esperaba Python 3.14.9, encontrado ' + str(datos.get('python')))

    @prueba('Revisor de ortografía')
    def _():
        from spellchecker import SpellChecker
        SpellChecker(language='es')

    @prueba('Atajos de teclado (pynput)', critica=False)
    def _():
        import pynput  # noqa: F401

    @prueba('Iconos de la interfaz (QtAwesome)', critica=False)
    def _():
        # v5.2: los iconos de linea (Phosphor); sin ellos los botones vuelven a su texto
        import qt_kit
        icono = qt_kit.icono_linea('ph.magnifying-glass')
        if icono is None or icono.isNull():
            raise RuntimeError('no cargaron las fuentes de iconos')

    @prueba('Animaciones de la Edición PRO (Remotion)', critica=False)
    def _():
        # v5.4.50: Node + Chrome sin ventana + el renderizador; en la compilación de Mac (sin pantalla) también un render real de 1 s
        import edicion_pro_remotion
        falla = edicion_pro_remotion.comprobar(renderizar_prueba=os.environ.get('CINECAPTIONS_SIN_PANTALLA') == '1')
        if falla:
            raise RuntimeError(falla)

    @prueba('Licencia (Lemon Squeezy)')
    def _():
        # v5.2.1: la ventana «Activa tu licencia» se DIBUJA en memoria (sin mostrarla ni hablar con
        # ninguna tienda) y el ID del equipo se puede leer: sin esto nadie podria activar
        import licencia
        import ventana_licencia
        if len(licencia.id_equipo()) != 19:
            raise RuntimeError('no se pudo leer el ID del equipo')
        v = ventana_licencia.VentanaLicencia()
        v.resize(1000, 640)
        if v.grab().isNull():
            raise RuntimeError('no pudo dibujar la ventana de la licencia')
        v.deleteLater()

    for n, (nombre, critica, funcion) in enumerate(pruebas):
        estado.progreso(100 * n / len(pruebas), nombre)
        try:
            funcion()
            estado.info(f'OK      {nombre}')
        except Exception as exc:
            linea = f'{nombre}: {type(exc).__name__}: {exc}'
            estado.info(('FALLA   ' if critica else 'AVISO   ') + linea)
            (fallos if critica else avisos).append(linea)
    estado.progreso(100)
    if fallos:
        estado.error('No funciona en este equipo: ' + '; '.join(fallos))
    else:
        estado.ok('Todo funciona' + (f' ({len(avisos)} aviso/s)' if avisos else ''))


# ---------------------------------------------------------------------------
# scripts: los .lua del menu Workspace > Scripts de DaVinci Resolve
# ---------------------------------------------------------------------------
def _tarea_scripts(estado):
    import instalador_scripts as ins
    estado.progreso(10, 'Buscando DaVinci Resolve')
    instalado = ins.resolve_esta_instalado()
    abierto = instalado and ins.resolve_esta_corriendo()
    estado.progreso(40, 'Copiando los scripts')
    copiados, error, detalle = ins.instalar_scripts_en_resolve(forzar=True)
    for carpeta, c, err in detalle:
        estado.info(f'{carpeta}: ' + (f'error: {err}' if err else f'{len(c)} archivo/s'))
    if error:
        if not instalado:
            estado.ok('DaVinci Resolve no está instalado: el programa dejará los '
                      'scripts cuando lo instales')
            return
        estado.error(error)
        return
    estado.progreso(100)
    texto = f'{len(ins._nuestros_scripts())} scripts listos en el menú de Resolve'
    if not instalado:
        texto += ' (Resolve aún no está instalado: quedan listos para cuando lo instales)'
    elif abierto:
        texto += ' (Resolve está abierto: aparecen en el menú al reiniciarlo)'
    estado.ok(texto)


def _tarea_quitar_scripts(estado):
    """Al desinstalar: solo los nombres que son nuestros (un script propio del
    usuario en la misma carpeta no se toca). Lo de ~/DaVinciSubtitles
    -proyectos, licencia, ajustes- se conserva."""
    import instalador_scripts as ins
    borrados = ins.desinstalar_scripts_del_menu()
    for ruta in borrados:
        estado.info(f'Borrado: {ruta}')
    estado.progreso(100)
    estado.ok(f'{len(borrados)} scripts quitados del menú de Resolve')


# ---------------------------------------------------------------------------
# fuentes: las tipografias de las plantillas incluidas, solo para este usuario
# ---------------------------------------------------------------------------
def _tarea_fuentes(estado):
    import instalar_fuentes
    import plantillas
    from version import APP_VERSION
    estado.progreso(5, 'Revisando las tipografías de las plantillas')
    pares = set()
    for pack in plantillas.packs_incorporados():
        try:
            pares.update(pack.fuentes())
        except Exception as exc:
            estado.info(f'{pack.nombre}: no pude leer sus tipografías ({exc})')
    arreglables, sin_remedio = instalar_fuentes.faltantes(sorted(pares))
    for familia, estilo in sin_remedio:
        estado.info(f'No viene con el programa: {familia} {estilo}')
    rutas = sorted({r for _, r in arreglables})
    if rutas:
        def progreso(i, total, nombre):
            estado.progreso(10 + 85 * i / max(1, total), nombre)
        instaladas, fallos = instalar_fuentes.instalar(rutas, progreso=progreso)
        for nombre, motivo in fallos:
            estado.info(f'No pude instalar {nombre}: {motivo}')
        resumen = f'{len(instaladas)} tipografías instaladas'
        if fallos:
            resumen += f', {len(fallos)} con problemas'
    else:
        resumen = 'Las tipografías ya estaban instaladas'
    # el aviso "¿Las instalo ahora?" del primer arranque ya no hace falta
    try:
        carpeta = Path.home() / 'DaVinciSubtitles'
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / 'fuentes_ofrecidas.txt').write_text(APP_VERSION, encoding='utf-8')
    except OSError:
        pass
    estado.progreso(100)
    estado.ok(resumen)


# ---------------------------------------------------------------------------
# modelo: los pesos de Whisper que el programa bajaria en la primera
# transcripcion (sin esto, la primera vez la barra se queda quieta varios
# minutos mientras baja ~1,5 GB)
# ---------------------------------------------------------------------------
def _tamano_carpeta(carpeta):
    total = 0
    for raiz, _, archivos in os.walk(carpeta):
        for a in archivos:
            try:
                total += os.path.getsize(os.path.join(raiz, a))
            except OSError:
                pass
    return total


def _tarea_modelo(estado):
    """Descarga Whisper en el motor auxiliar, mostrando avance al instalador."""
    import motor_compat
    estado.progreso(0, 'Comprobando si el motor auxiliar está listo')

    def progreso(fraccion, detalle=''):
        estado.progreso(fraccion * 100, detalle)

    def aviso(texto):
        estado.info(texto)

    try:
        motor_compat.descargar_modelo(MODELO_WHISPER, progreso=progreso, aviso=aviso)
    except Exception as exc:
        estado.error(f'No pude preparar el modelo de voz ({type(exc).__name__}: {exc}). '
                     'El programa lo descargará la primera vez que transcribas.')
        return
    estado.progreso(100)
    estado.ok('Modelo de voz descargado')


# ---------------------------------------------------------------------------
# motor_ia (v5.1): Qwen3-ASR + alineador + la IA de texto (Qwen3), en su propio
# Python 3.14 (motor_voz.instalar). Pesa de 4 a 15 GB segun la tarjeta: si
# falla, el programa funciona igual con Whisper y se reintenta desde Ajustes.
# ---------------------------------------------------------------------------
def _tarea_motor_ia(estado):
    import motor_voz
    if sys.platform != 'win32':
        estado.ok('El motor Qwen3 por ahora solo está para Windows: se usa Whisper')
        return
    # v5.2: mirando los archivos (no solo listo.json), en un segundo
    info = motor_voz.asegurar_listo()
    if info and info.get('modelo_texto'):
        # v5.5.8: ya instalado, solo se ponen al dia las librerias que cambiaron en los requisitos (sin torch ni modelos)
        ya = f"Ya estaba instalado (Qwen3-ASR {info.get('modelo')} + IA de texto)"
        try:
            puestas = motor_voz.completar_requisitos(aviso=estado.info)
        except Exception as e:
            estado.progreso(100)
            estado.error(f'{ya}; no pude poner al día sus librerías ({e}): sigue con las que tenía')
            return
        estado.progreso(100)
        estado.ok(ya + (f'; {len(puestas)} librería(s) al día' if puestas else ''))
        return
    modelo = motor_voz.instalar(progreso=lambda f, texto: estado.progreso(100 * f, texto),
                                aviso=estado.info)
    info = motor_voz.info_instalado() or {}
    estado.progreso(100)
    estado.ok(f"Qwen3-ASR {modelo} listo" + (' + IA de texto' if info.get('modelo_texto') else ''))


# ---------------------------------------------------------------------------
# transcribir (soporte): Whisper de punta a punta con el .exe compilado
# ---------------------------------------------------------------------------
def _tarea_transcribir(estado, audio=None, idioma='es'):
    if not audio or not Path(audio).is_file():
        estado.error(f'No encuentro el audio: {audio!r}')
        return
    import subtitle_transcriber as st
    inicio = time.time()
    palabras = st.transcribe(
        str(audio), idioma, MODELO_WHISPER,
        progress_callback=lambda f: estado.progreso(100 * f, 'Transcribiendo'),
        status_callback=estado.info)
    cues = st.build_cues(palabras, 42, 2)
    texto = ' '.join(p['word'] for p in palabras)
    estado.info(f'{len(palabras)} palabras, {len(cues)} bloques, '
                f'{time.time() - inicio:.0f} s')
    estado.info('Comienza: ' + texto[:160])
    if not palabras:
        estado.error('Whisper no devolvió ninguna palabra')
        return
    estado.ok(f'{len(palabras)} palabras transcritas')
