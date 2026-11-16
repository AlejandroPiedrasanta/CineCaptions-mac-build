# CineCaptions · By Cinema Productions
# 1_codigo/instalar_mac.py — los pasos 3-7 del instalador de la Mac («Instalar CineCaptions.app», 7_mac/instalador) con la app ya copiada.
"""v5.92 (el usuario: «necesito que funcione el instalador como el de CineSlide»): la ventana nativa del instalador copia la app y le pide
el resto en UNA sola pasada (`CineCaptions --tarea pasos_mac <estado> <idioma>`; abrir la app cuatro veces tardaba): scripts de DaVinci
Resolve, tipografías de los estilos, servicio de actualizaciones (LaunchAgent del usuario, sin contraseña), la app fijada en el Dock y
(paso 7) el motor de voz e IA, que se deja bajando aparte (`--tarea motor_fondo`).

Escribe el avance en el archivo de la ventana (variable CINECAPTIONS_AVANCE): «PASO|OK|AVISO<TAB>texto», en el idioma de la Mac. Nada
de esto detiene la instalación: lo que no se pudo queda de aviso y CineCaptions lo vuelve a intentar al abrirse (scripts, servicio)."""
import os
import plistlib
import re
import subprocess
import urllib.parse

BUNDLE_ID = 'com.cinemaproductions.cinecaptions'


class _Recoge:
    """Hace de «estado» de tareas_instalador para reusar sus tareas tal cual (sin escribir el archivo del instalador de Windows)."""

    def __init__(self):
        self.final = None
        self.texto = ''
        self.infos = []

    def progreso(self, *_a):
        pass

    def info(self, texto):
        self.infos.append(texto)

    def ok(self, texto=''):
        self.final, self.texto = 0, texto

    def error(self, texto):
        self.final, self.texto = 1, texto


def _avance(tipo, texto=''):
    ruta = os.environ.get('CINECAPTIONS_AVANCE')
    if not ruta:
        print(f'{tipo}\t{texto}')
        return
    try:
        with open(ruta, 'a', encoding='utf-8') as f:
            f.write(f"{tipo}\t{str(texto).replace(chr(10), ' ')}\n")
    except OSError:
        pass


def _ruta_tile(t):
    try:
        s = t['tile-data']['file-data']['_CFURLString']
    except (KeyError, TypeError):
        return ''
    if s.startswith('file://'):
        s = urllib.parse.unquote(s[7:])
    return s.rstrip('/')


def fijar_en_dock(app, reiniciar=True):
    """CineCaptions en el Dock (una vez; quita las de otras rutas, p. ej. ~/Applications). Como CineSlide 9.62: se edita persistent-apps
    de com.apple.dock y se reinicia el Dock. Devuelve 'fijada' | 'ya_estaba'."""
    app = str(app).rstrip('/')
    crudo = subprocess.run(['/usr/bin/defaults', 'export', 'com.apple.dock', '-'], capture_output=True, timeout=30).stdout
    d = plistlib.loads(crudo) if crudo.strip() else {}
    antes = d.get('persistent-apps', [])
    apps = [t for t in antes if not (_ruta_tile(t).endswith('/CineCaptions.app') and _ruta_tile(t) != app)]
    if len(apps) == len(antes) and any(_ruta_tile(t) == app for t in apps):
        return 'ya_estaba'
    if not any(_ruta_tile(t) == app for t in apps):
        apps.append({'tile-type': 'file-tile',
                     'tile-data': {'file-label': 'CineCaptions', 'bundle-identifier': BUNDLE_ID,
                                   'file-data': {'_CFURLString': 'file://' + urllib.parse.quote(app) + '/', '_CFURLStringType': 15}}})
    d['persistent-apps'] = apps
    subprocess.run(['/usr/bin/defaults', 'import', 'com.apple.dock', '-'], input=plistlib.dumps(d), check=True, timeout=30)
    if reiniciar:
        subprocess.run(['/usr/bin/killall', 'Dock'], capture_output=True, timeout=30)
    return 'fijada'


def pasos(estado, idioma='es'):
    """Los pasos 3-7. `estado` es el de tareas_instalador (registro); el avance va a CINECAPTIONS_AVANCE."""
    import tareas_instalador

    def T(es, en):
        return es if not str(idioma).lower().startswith('en') else en

    # 3) scripts de DaVinci Resolve (los del menú Espacio de trabajo > Scripts)
    _avance('PASO', '3/7')
    try:
        import instalador_scripts as ins
        r = _Recoge()
        tareas_instalador._tarea_scripts(r)
        for t in r.infos:
            estado.info(f'scripts: {t}')
        if r.final == 1:
            _avance('AVISO', T('Se instalan al abrir CineCaptions', 'Installed when CineCaptions opens'))
            estado.info(f'scripts: {r.texto}')
        elif not ins.resolve_esta_instalado():
            _avance('OK', T('Listos para cuando instales Resolve', 'Ready for when you install Resolve'))
        else:
            n = len(ins._nuestros_scripts())
            _avance('OK', T(f'{n} scripts en el menú de Resolve', f'{n} scripts in the Resolve menu'))
    except Exception as e:                                           # (nunca detiene la instalación)
        estado.info(f'scripts: {type(e).__name__}: {e}')
        _avance('AVISO', T('Se instalan al abrir CineCaptions', 'Installed when CineCaptions opens'))

    # 4) tipografías de los estilos (en ~/Library/Fonts: sin contraseña)
    _avance('PASO', '4/7')
    try:
        r = _Recoge()
        tareas_instalador._tarea_fuentes(r)
        for t in r.infos:
            estado.info(f'fuentes: {t}')
        n = re.match(r'(\d+) tipograf', r.texto or '')
        if r.final == 1:
            _avance('AVISO', T('CineCaptions las ofrece al abrirse', 'CineCaptions offers them when it opens'))
        elif n:
            _avance('OK', T(f'{n.group(1)} tipografías', f'{n.group(1)} fonts'))
        else:
            _avance('OK', T('Ya estaban instaladas', 'Already installed'))
    except Exception as e:
        estado.info(f'fuentes: {type(e).__name__}: {e}')
        _avance('AVISO', T('CineCaptions las ofrece al abrirse', 'CineCaptions offers them when it opens'))

    # 5) actualizaciones automáticas: el servicio del usuario (o el de root de las 5.87-5.90, si ya está)
    _avance('PASO', '5/7')
    try:
        import actualizar_fondo
        r = actualizar_fondo.asegurar_programada()
        estado.info(f'servicio: {r}')
        if r in ('creada', 'al_dia'):
            _avance('OK', T('Cada hora, sin contraseña', 'Every hour, no password'))
        else:
            _avance('AVISO', T('Se activan al abrir CineCaptions', 'Turned on when CineCaptions opens'))
    except Exception as e:
        estado.info(f'servicio: {type(e).__name__}: {e}')
        _avance('AVISO', T('Se activan al abrir CineCaptions', 'Turned on when CineCaptions opens'))

    # 6) la app en el Dock
    _avance('PASO', '6/7')
    try:
        import actualizar_fondo
        r = fijar_en_dock(actualizar_fondo.app_instalada())
        estado.info(f'dock: {r}')
        _avance('OK', T('Fijada en el Dock', 'Pinned to the Dock') if r == 'fijada' else T('Ya estaba en el Dock', 'Already in the Dock'))
    except Exception as e:
        estado.info(f'dock: {type(e).__name__}: {e}')
        _avance('AVISO', T('Arrástrala al Dock desde Aplicaciones', 'Drag it to the Dock from Applications'))

    # 7) el motor de voz e IA: se deja bajando APARTE (sigue aunque el instalador se cierre): el primer GO ya no lo espera
    _avance('PASO', '7/7')
    try:
        r = lanzar_motor_de_fondo()
        estado.info(f'motor: {r}')
        _avance('OK', T('Ya estaba instalado', 'Already installed') if r == 'ya' else T('Bajando en segundo plano', 'Downloading in the background'))
    except Exception as e:
        estado.info(f'motor: {type(e).__name__}: {e}')
        _avance('AVISO', T('Se baja al abrir CineCaptions', 'Downloads when CineCaptions opens'))
    estado.ok('pasos de la Mac hechos')


def lanzar_motor_de_fondo():
    """v5.92 (el usuario: «que el motor de voz e IA empiece a bajarse desde el instalador, para que el primer GO no tenga que esperarlo»):
    deja corriendo APARTE `CineCaptions --tarea motor_fondo` (nueva sesión: sobrevive al instalador y a cerrar CineCaptions; sin ventana
    ni icono en el Dock). Devuelve 'ya' (motor Qwen3 listo en Apple Silicon) | 'lanzado' (en marcha, o ya lo bajaba otro proceso)."""
    import subprocess
    import sys
    import motor_voz
    if motor_voz.instalando():
        return 'lanzado'
    if motor_voz.SOPORTADO and motor_voz.instalado():
        return 'ya'
    if not getattr(sys, 'frozen', False):
        raise RuntimeError('solo con el programa compilado')
    entorno = {k: v for k, v in os.environ.items() if not k.startswith(('DYLD_', '_PYI', 'PYTHON', 'CINECAPTIONS_AVANCE'))}
    entorno['QT_QPA_PLATFORM'] = 'offscreen'
    registro = os.path.join(os.path.expanduser('~'), 'DaVinciSubtitles', 'motor_de_fondo.txt')
    os.makedirs(os.path.dirname(registro), exist_ok=True)
    subprocess.Popen([sys.executable, '--tarea', 'motor_fondo', registro], start_new_session=True, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=entorno)
    return 'lanzado'


def motor_de_fondo(estado):
    """`--tarea motor_fondo` (lo lanza el instalador de la Mac), a la vez: Whisper, para que el primer GO no lo baje (también en las Intel),
    y en Apple Silicon el motor Qwen3-ASR con la IA de texto (4-15 GB), como lo haría CineCaptions al abrirse (vigilancia._motor_ia_en_mac:
    mismo mínimo de disco y misma marca instalacion_auto.json, así no lo reintenta él el mismo día si falla). Una sola instalación entre
    procesos: si CineCaptions ya lo está instalando, este se aparta."""
    import threading
    import time
    import tareas_instalador
    estado.info(time.strftime('%Y-%m-%d %H:%M:%S') + ' · motor de fondo: empieza')
    # el motor Qwen3 EMPIEZA YA (toma el candado entre procesos: CineCaptions, al abrirse, ve que se está instalando y no empieza otro; si
    # se cierra CineCaptions, este sigue) y Whisper se baja a la vez (el primer GO, mientras Qwen3 no está, va con él)
    resultado = {}
    hilo = threading.Thread(target=lambda: resultado.update(qwen=_instalar_qwen(estado)), daemon=True, name='qwen')
    hilo.start()
    r = _Recoge()
    try:
        tareas_instalador._tarea_modelo(r)
        estado.info(f'whisper: {r.texto}')
    except Exception as e:
        estado.info(f'whisper: {type(e).__name__}: {e}')
    hilo.join()
    estado.ok(f"whisper: {'listo' if r.final == 0 else 'sin bajar'} · qwen3: {resultado.get('qwen')}")


def _instalar_qwen(estado):
    """El motor Qwen3-ASR + la IA de texto en una Mac con Apple Silicon (en las Intel no hay PyTorch nuevo: 'no_aplica')."""
    import time
    from pathlib import Path
    import archivos_seguros
    import motor_voz
    import vigilancia
    if not motor_voz.SOPORTADO:
        return 'no_aplica'
    info = motor_voz.asegurar_listo()
    if info and info.get('modelo_texto'):
        return 'ya estaba'
    if motor_voz.instalando():
        return 'lo instala CineCaptions'
    marca = motor_voz.carpeta() / 'instalacion_auto.json'
    libre = vigilancia._gb_libres(Path.home())
    if libre is not None and libre < vigilancia.MAC_IA_DISCO_GB:
        archivos_seguros.escribir_json(marca, {'fallo': time.time(), 'motivo': f'disco: {libre:.1f} GB libres'})
        return f'sin sitio ({libre:.1f} GB libres, necesita {vigilancia.MAC_IA_DISCO_GB})'
    try:
        modelo = motor_voz.instalar(aviso=lambda t: estado.info(f'qwen3: {t}'))
    except Exception as e:
        if motor_voz.instalando():
            return 'lo instala otro proceso'
        archivos_seguros.escribir_json(marca, {'fallo': time.time(), 'motivo': f'{type(e).__name__}: {e}'[:300]})
        return f'falló: {type(e).__name__}: {e}'
    info = motor_voz.info_instalado() or {}
    if info.get('modelo_texto'):
        archivos_seguros.escribir_json(marca, {'listo': time.strftime('%Y-%m-%d %H:%M')})
        return f'Qwen3-ASR {modelo} + IA de texto listos'
    archivos_seguros.escribir_json(marca, {'fallo': time.time(), 'motivo': 'sin la IA de texto'})
    return f'Qwen3-ASR {modelo} listo, sin la IA de texto'
