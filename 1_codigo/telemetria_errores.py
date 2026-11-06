# CineCaptions · By Cinema Productions
# 1_codigo/telemetria_errores.py — manda al vendedor (cinecaptions.shop/pagos/errores.php) cada error que le sale a un cliente, en segundo plano.
"""
v5.71 (pedido del usuario: «necesito telemetría para ver si a los usuarios les da error, que lo notifique»): cada anotación de nivel
«error» del Registro se manda, con la clave de la licencia y el id del equipo, a `pagos/errores.php`; la app «CineCaptions Ventas» la
muestra en su página Errores y avisa al dueño. Así un fallo se ve antes de que el cliente escriba.

Qué se manda (lo cuenta la política de privacidad, punto 3): el informe de «Copiar este error» del Registro (qué pasó, qué significa,
el detalle técnico, lo que pasó justo antes, el equipo y los motores), SIN la carpeta del usuario (registro._sin_usuario la cambia
por «~»), más la versión y el sistema. Nunca videos, audio ni texto de subtítulos.

Reglas:
- Nada de esto corre en el hilo de la interfaz: `_al_anotar` (que llama el Registro desde cualquier hilo) solo guarda en memoria y
  despierta al hilo «telemetria-errores», que arma el informe, lo guarda en disco si no hay red y hace la petición.
- El mismo fallo (misma firma: origen + mensaje sin números) no se manda más de una vez cada REPETIR_S: las repeticiones se suman en
  «veces». Como mucho TOPE_SESION envíos por sesión y PENDIENTES_MAX en disco (lo más viejo se cae).
- Sin licencia activada en este equipo no se manda (el servidor solo acepta equipos activados): queda pendiente hasta que la haya.
- Desde el código fuente (no el .exe) NO se manda, para no llenar la tabla con las pruebas del autor; CINECAPTIONS_TELEMETRIA=1 lo
  fuerza. CINECAPTIONS_SIN_TELEMETRIA=1 o la preferencia oculta «enviar_errores»: false lo apagan.

v5.72 (pedido del usuario: «captura de pantalla completa en el instante del fallo» + GPU y RAM): con cada error DISTINTO va una captura
(como mucho CAPTURAS_SESION por sesión). En Windows, la pantalla entera donde está CineCaptions (`QScreen.grabWindow(0)`); en Mac solo la
ventana del programa (capturar la pantalla pide el permiso «Grabación de pantalla» y saldría ese cuadro del sistema en mitad del fallo).
El hilo de la interfaz SOLO toma la imagen (la señal llega en cola: un instante después del error, nunca dentro del gancho); reducirla a
CAPTURA_ANCHO, pasarla a JPEG, guardarla en `errores_capturas/` y mandarla (multipart, `captura_<firma>`) lo hace el hilo de la telemetría.
Los errores que ya estaban en el Registro al abrir (los de la sesión que se cortó) van sin captura: la pantalla de ahora no es la del fallo.
`equipo_datos` (GPU, RAM total y libre, CPU, pantalla) va en cada petición, sin subprocess en Windows.

v5.72 (pedido: «que la app Ventas reciba la telemetría con más información del equipo»): `equipo_datos` sale de la ficha del equipo
(`ficha_equipo`: también la memoria de vídeo y el driver) y la ficha ENTERA (sistema, CPU, RAM, GPU con su driver, pantallas, discos,
Resolve, motores, Visual C++, revisión y lo que el instalador puso al día) va a `pagos/equipo.php` FICHA_ESPERA_S después de abrir,
una vez al día o cuando cambia (`ficha_enviada.json` guarda su huella). Mismas reglas: solo con licencia, pasada por privado().

v5.73 (pedido: «2 capturas, una del programa y una de la pantalla completa, para garantizar la captura»): `_tomar_capturas` saca, cada
una por separado, la pantalla entera (Windows) y la ventana PRINCIPAL del programa (`grab()` de Qt: sale aunque esté tapada o minimizada).
La primera que salga va como siempre («captura_<firma>», `<firma>.jpg`: un errores.php anterior la guarda); la del programa, cuando
también hay pantalla, como «ventana_<firma>» (`<firma>.ventana.jpg`, `ventana: true` en su error). IMAGENES_POR_PETICION = 4.
"""
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import registro

URL = 'https://cinecaptions.shop/pagos/errores.php'
ARCHIVO = registro.CARPETA / 'errores_por_enviar.json'
ESPERA_LOTE_S = 8           # tras el primer error se espera un poco: los que llegan juntos van en una sola petición
REPETIR_S = 600             # el mismo error se vuelve a mandar (con sus «veces») como mucho cada 10 minutos
TOPE_SESION = 40            # envíos por sesión (un bucle de errores no inunda el servidor)
PENDIENTES_MAX = 50
CADUCA_S = 7 * 86400        # lo pendiente de hace más de una semana ya no se manda
POR_PETICION = 20           # lo mismo que acepta errores.php
TIMEOUT_S = 15
DETALLE_MAX = 7500          # caracteres del informe (errores.php guarda 8 000)
CAPTURAS = registro.CARPETA / 'errores_capturas'
CAPTURAS_SESION = 6         # capturas por sesión (cada una ~150-400 KB)
CAPTURA_ANCHO = 1920        # una pantalla 4K se reduce a 1920 de ancho: se lee la interfaz y pesa poco
CAPTURA_MAX_BYTES = 700_000  # errores.php acepta hasta 900 KB por captura
IMAGENES_POR_PETICION = 4   # v5.73: imágenes por petición (dos por error: ≈2,8 MB como mucho; el resto va en la siguiente)
URL_FICHA = 'https://cinecaptions.shop/pagos/equipo.php'      # v5.72: la ficha del equipo
FICHA_ENVIADA = registro.CARPETA / 'ficha_enviada.json'       # {huella, cuando} de la última que aceptó el servidor
FICHA_ESPERA_S = 90         # se manda 90 s después de abrir (el arranque ya pasó)
FICHA_CADA_S = 86400        # la misma ficha, como mucho una vez al día
FICHA_MAX = 16000           # lo que acepta equipo.php

_CANDADO = threading.Lock()
_DESPERTAR = threading.Event()
_ESTADO = {'iniciado': False, 'enviados': 0, 'pausa_hasta': 0.0, 'ultimo_envio': {}, 'hilo': None, 'capturas': 0, 'capturador': None,
           'pantalla': '', 'equipo_fijo': None}
_COLA = []                  # Entradas del Registro recién llegadas (las procesa el hilo)
_PENDIENTES = {}            # firma -> dict listo para mandar (también en ARCHIVO)
_CONTADAS = {}              # id(Entrada) -> (Entrada, veces ya contadas)
_CAPTURADAS = set()         # firmas que ya pidieron su captura en esta sesión
_CAPTURAS_MEM = {}          # firma -> (QImage, {tipo, pantalla}) recién tomadas en el hilo de la interfaz (el hilo las pasa a JPEG)


def activo():
    """¿Se mandan los errores en esta sesión?"""
    if os.environ.get('CINECAPTIONS_SIN_TELEMETRIA') == '1':
        return False
    if not getattr(sys, 'frozen', False) and os.environ.get('CINECAPTIONS_TELEMETRIA') != '1':
        return False
    try:
        import ajustes_ui
        if ajustes_ui.leer_prefs().get('enviar_errores') is False:
            return False
    except Exception:
        pass
    return True


def firma(origen, mensaje):
    """El mismo fallo da la misma firma aunque cambien números, horas o rutas: sha1 de «origen|mensaje» con los dígitos como #."""
    texto = registro._sin_usuario(f'{origen}|{mensaje}'.lower())
    texto = re.sub(r'\d+', '#', ' '.join(texto.split()))[:400]
    return hashlib.sha1(texto.encode('utf-8')).hexdigest()


def iniciar():
    """Al abrir el programa (después de registro.instalar_ganchos). Nunca lanza ni bloquea."""
    try:
        if _ESTADO['iniciado'] or not activo():
            return False
        _ESTADO.update(iniciado=True, parar=False)
        _ESTADO['capturador'] = _crear_capturador()     # (iniciar corre en el hilo de la interfaz, con la QApplication ya creada)
        try:
            from PySide6.QtCore import Qt
            registro.registro().nueva.connect(_al_anotar, Qt.DirectConnection)
        except Exception:
            registro.registro().nueva.connect(_al_anotar)
        # los errores que llegaron ANTES de conectarse (instalar_ganchos anota ahí «la sesión anterior se cortó / no terminó de abrir»,
        # justo los cuelgues y caídas que más interesa ver: en la sesión que se cayó no dio tiempo a mandarlos). Sin captura: la
        # pantalla de ahora no es la de ese fallo.
        for e in registro.registro().lista('error'):
            _al_anotar(e, capturar=False)
        # al cerrar (main() corre atexit antes de os._exit): lo que aún esté en la cola se guarda en disco y sale en la sesión siguiente
        import atexit
        atexit.register(_al_salir)
        hilo = threading.Thread(target=_bucle, daemon=True, name='telemetria-errores')
        _ESTADO['hilo'] = hilo
        hilo.start()
        return True
    except Exception:
        return False


def _al_salir():
    try:
        _procesar_cola()
        _guardar_capturas()
    except Exception:
        pass


def _al_anotar(e, capturar=True):
    """Lo llama el Registro (desde cualquier hilo, también el de la interfaz): solo memoria, nada de disco ni red."""
    try:
        if getattr(e, 'nivel', '') != 'error':
            return
        with _CANDADO:
            if e not in _COLA:
                _COLA.append(e)
        if capturar:
            _pedir_captura(e)
        _DESPERTAR.set()
    except Exception:
        pass


# ---------------------------------------------------------------------------------------------------------------------------------------
# la captura (v5.72)
# ---------------------------------------------------------------------------------------------------------------------------------------
def _crear_capturador():
    """Un QObject del hilo de la interfaz con una señal en cola: `_pedir_captura` (desde cualquier hilo) la emite y la captura se toma en
    la siguiente vuelta del bucle de Qt, fuera del gancho del error. None si no hay Qt (pruebas sin interfaz)."""
    try:
        from PySide6.QtCore import QObject, Qt, Signal
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.instance() is None:
            return None

        class _Capturador(QObject):
            pedir = Signal(str)

            def __init__(self):
                super().__init__()
                self.pedir.connect(self._capturar, Qt.QueuedConnection)

            def _capturar(self, f):
                try:
                    tomas = _tomar_capturas()
                    if tomas:
                        with _CANDADO:
                            _CAPTURAS_MEM[f] = tomas
                        _DESPERTAR.set()
                except Exception:
                    pass

        c = _Capturador()
        c.moveToThread(QGuiApplication.instance().thread())
        try:
            p = QGuiApplication.primaryScreen()
            if p is not None:
                g, dpr = p.geometry(), p.devicePixelRatio()
                _ESTADO['pantalla'] = '%d×%d al %d %%' % (round(g.width() * dpr), round(g.height() * dpr), round(dpr * 100))
            # v5.72: todas las pantallas para la ficha del equipo (Qt solo se toca aquí, en el hilo de la interfaz)
            _ESTADO['pantallas'] = [{'ancho': round(s.geometry().width() * s.devicePixelRatio()),
                                     'alto': round(s.geometry().height() * s.devicePixelRatio()),
                                     'escala': round(s.devicePixelRatio() * 100), 'hz': round(s.refreshRate())}
                                    | ({'principal': True} if s is p else {}) for s in QGuiApplication.screens()]
        except Exception:
            pass
        return c
    except Exception:
        return None


def _pedir_captura(e):
    """Una captura por error DISTINTO y como mucho CAPTURAS_SESION por sesión. Solo memoria (se puede llamar desde cualquier hilo)."""
    c = _ESTADO.get('capturador')
    if c is None or _ESTADO['capturas'] >= CAPTURAS_SESION or os.environ.get('CINECAPTIONS_SIN_CAPTURA') == '1':
        return
    f = firma(e.origen, e.mensaje)
    with _CANDADO:
        if f in _CAPTURADAS or _ESTADO['capturas'] >= CAPTURAS_SESION:
            return
        _CAPTURADAS.add(f)
        _ESTADO['capturas'] += 1
    c.pedir.emit(f)


def _ventana_principal():
    from PySide6.QtWidgets import QApplication
    w = QApplication.activeWindow()
    if w is not None:
        return w.window()
    visibles = [v for v in QApplication.topLevelWidgets() if v.isVisible() and v.isWindow() and not v.isMinimized()]
    return max(visibles, key=lambda v: v.width() * v.height(), default=None)


def _ventana_del_programa():
    """v5.73: la ventana PRINCIPAL de CineCaptions (la mayor de primer nivel, visible o minimizada), no un cuadro de diálogo que tenga el
    foco; si no hay ninguna, la de _ventana_principal()."""
    from PySide6.QtWidgets import QApplication, QDialog
    candidatas = [v for v in QApplication.topLevelWidgets()
                  if v.isWindow() and (v.isVisible() or v.isMinimized()) and not isinstance(v, QDialog)]
    if candidatas:
        return max(candidatas, key=lambda v: v.width() * v.height())
    return _ventana_principal()


def _tomar_capturas():
    """[(cual, QImage, info)] en el hilo de la interfaz. v5.73 (pedido del usuario: «2 capturas, una del programa y una de la pantalla
    completa, para garantizar la captura»): Windows → 'pantalla' (la pantalla entera donde está CineCaptions) y 'ventana' (la ventana del
    programa dibujada por Qt con grab(): sale aunque otra ventana la tape, esté minimizada o la de pantalla falle). Mac → solo 'ventana'
    (la pantalla entera pide el permiso «Grabación de pantalla» y saldría ese cuadro en mitad del fallo). Cada una por separado: si una
    falla, la otra va igual."""
    from PySide6.QtGui import QGuiApplication
    tomas = []
    try:
        ventana = _ventana_del_programa()
    except Exception:
        ventana = None
    if sys.platform != 'darwin':
        try:
            pantalla = (ventana.screen() if ventana is not None else None) or QGuiApplication.primaryScreen()
            img = pantalla.grabWindow(0).toImage() if pantalla is not None else None
            if img is not None and not img.isNull():
                tomas.append(('pantalla', img, {'tipo': 'pantalla', 'ancho': img.width(), 'alto': img.height()}))
        except Exception:
            pass
    if ventana is not None:
        try:
            img = ventana.grab().toImage()
            if not img.isNull():
                tomas.append(('ventana', img, {'tipo': 'ventana', 'ancho': img.width(), 'alto': img.height()}))
        except Exception:
            pass
    return tomas


def _jpeg(img):
    """La QImage reducida a CAPTURA_ANCHO y en JPEG (hilo de la telemetría: QImage se puede usar fuera del de la interfaz); PNG más
    pequeño si no hay JPEG. bytes o None."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    if img.width() > CAPTURA_ANCHO:
        img = img.scaledToWidth(CAPTURA_ANCHO, Qt.SmoothTransformation)

    def codificar(imagen, formato, calidad):
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        ok = imagen.save(buf, formato, calidad)
        buf.close()
        return bytes(ba.data()) if ok else b''

    for calidad in (72, 55, 40):
        datos = codificar(img, 'JPEG', calidad)
        if not datos:
            break
        if len(datos) <= CAPTURA_MAX_BYTES:
            return datos
    chica = img.scaledToWidth(min(img.width(), 1280), Qt.SmoothTransformation)
    datos = codificar(chica, 'PNG', -1)
    return datos if datos and len(datos) <= CAPTURA_MAX_BYTES else None


def _archivo_captura(f, cual='captura'):
    """'captura' = la principal (`<firma>.jpg`, va como «captura_<firma>»); 'ventana' = la segunda (`<firma>.ventana.jpg`, «ventana_<firma>»)."""
    return CAPTURAS / (f'{f}.jpg' if cual == 'captura' else f'{f}.ventana.jpg')


def _borrar_captura(f):
    for cual in ('captura', 'ventana'):
        try:
            _archivo_captura(f, cual).unlink(missing_ok=True)
        except Exception:
            pass


def _guardar_capturas():
    """Las capturas recién tomadas → JPEG en disco, unidas a su error pendiente. Si el error ya se mandó (la interfaz estaba parada más
    de ESPERA_LOTE_S), la captura se descarta.
    v5.73: la PRIMERA toma va como la de siempre (`captura`: la pantalla en Windows, la ventana en Mac o si la pantalla falló), así un
    errores.php anterior la sigue guardando; la ventana del programa, cuando también hay pantalla, va aparte (`ventana`)."""
    with _CANDADO:
        nuevas = dict(_CAPTURAS_MEM)
        _CAPTURAS_MEM.clear()
    hubo = False
    for f, tomas in nuevas.items():
        d = _PENDIENTES.get(f)
        if d is None:
            continue
        for i, (_cual, img, info) in enumerate(tomas[:2]):
            clave = 'captura' if i == 0 else 'ventana'
            try:
                datos = _jpeg(img)
                if not datos:
                    continue
                CAPTURAS.mkdir(parents=True, exist_ok=True)
                destino = _archivo_captura(f, clave)
                tmp = destino.with_name(destino.name + '.tmp')
                tmp.write_bytes(datos)
                os.replace(tmp, destino)
                d[clave] = dict(info or {}, bytes=len(datos))
                hubo = True
            except Exception:
                pass
    if hubo:
        _guardar()


# ---------------------------------------------------------------------------------------------------------------------------------------
# el equipo (v5.72): GPU, RAM, CPU y pantalla en una línea, sin subprocess en Windows
# ---------------------------------------------------------------------------------------------------------------------------------------
def _gpus_windows():
    import ctypes
    from ctypes import wintypes

    class DD(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('DeviceName', wintypes.WCHAR * 32), ('DeviceString', wintypes.WCHAR * 128),
                    ('StateFlags', wintypes.DWORD), ('DeviceID', wintypes.WCHAR * 128), ('DeviceKey', wintypes.WCHAR * 128)]
    nombres = []
    for i in range(16):
        d = DD()
        d.cb = ctypes.sizeof(DD)
        if not ctypes.windll.user32.EnumDisplayDevicesW(None, i, ctypes.byref(d), 0):
            break
        n = ' '.join(d.DeviceString.split())
        if n and n not in nombres and not any(x in n for x in ('Basic Display', 'Basic Render', 'Remote', 'Parsec', 'Virtual')):
            if d.StateFlags & 4:                       # DISPLAY_DEVICE_PRIMARY_DEVICE: la que da imagen, primero
                nombres.insert(0, n)
            else:
                nombres.append(n)
    return nombres


def _cpu():
    try:
        if sys.platform.startswith('win'):
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as k:
                return ' '.join(str(winreg.QueryValueEx(k, 'ProcessorNameString')[0]).split())
        if sys.platform == 'darwin':
            import subprocess
            return subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        pass
    return ''


def _ram_mb():
    """(total, libre) en MB o (None, None)."""
    try:
        if sys.platform.startswith('win'):
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                            ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return int(m.ullTotalPhys / 1048576), int(m.ullAvailPhys / 1048576)
            return None, None
        total = int(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 1048576)
        import vigilancia
        return total, vigilancia.memoria_libre_mb()
    except Exception:
        return None, None


def _gb(mb):
    return ('%.1f GB' % (mb / 1024)).replace('.0 GB', ' GB').replace('.', ',')


def _ficha_ahora():
    """v5.72: la ficha del equipo de esta sesión con la RAM libre y las pantallas de AHORA (copia: la de la sesión no se toca)."""
    import copy
    import ficha_equipo
    f = copy.deepcopy(ficha_equipo.de_esta_sesion(pantallas=_ESTADO.get('pantallas')))
    total, libre = _ram_mb()
    if total:
        f['ram'] = {'total_mb': total, 'libre_mb': libre}
    return f


def datos_equipo():
    """«GPU NVIDIA GeForce RTX 4070 (12 GB, driver 596.36) · RAM 32 GB (libre 14,2 GB) · CPU AMD Ryzen 9 5900X (24 hilos) · Pantalla
    3840×2160 al 150 %». v5.72: sale de la ficha del equipo (con la memoria de vídeo y el driver); si no se puede, la línea de antes."""
    try:
        import ficha_equipo
        linea = ficha_equipo.resumen(_ficha_ahora())
        if linea:
            return privado(linea)[:300]
    except Exception:
        pass
    return _datos_equipo_simple()


def _datos_equipo_simple():
    if _ESTADO['equipo_fijo'] is None:
        partes = []
        gpus = []
        try:
            gpus = _gpus_windows() if sys.platform.startswith('win') else []
        except Exception:
            gpus = []
        # la línea de entorno_detallado() (nvidia-smi al abrir, con la memoria de vídeo) es más precisa que el nombre del adaptador
        nvidia = [l.split(':', 1)[1].strip() for l in (registro._ENTORNO.get('lineas') or [])
                  if l.startswith('GPU') and ':' in l and 'no detectada' not in l]
        if nvidia:
            gpus = nvidia[:1] + [g for g in gpus if 'nvidia' not in g.lower()]
        if gpus:
            partes.append('GPU ' + ' + '.join(gpus[:3]))
        cpu = _cpu()
        partes.append('CPU %s(%s hilos)' % (cpu + ' ' if cpu else '', os.cpu_count() or '?'))
        _ESTADO['equipo_fijo'] = partes
    partes = list(_ESTADO['equipo_fijo'])
    total, libre = _ram_mb()
    if total:
        partes.insert(1 if partes and partes[0].startswith('GPU') else 0,
                      'RAM %s' % _gb(total) + (' (libre %s)' % _gb(libre) if libre is not None else ''))
    if _ESTADO.get('pantalla'):
        partes.append('Pantalla ' + _ESTADO['pantalla'])
    return privado(' · '.join(partes))[:300]


# ---------------------------------------------------------------------------------------------------------------------------------------
# el hilo
# ---------------------------------------------------------------------------------------------------------------------------------------
def detener(espera_s=5.0):
    """Para el hilo (pruebas; al cerrar basta atexit). Desconecta la señal del Registro."""
    _ESTADO['parar'] = True
    _DESPERTAR.set()
    try:
        registro.registro().nueva.disconnect(_al_anotar)
    except Exception:
        pass
    hilo = _ESTADO.get('hilo')
    if hilo is not None and hilo is not threading.current_thread():
        hilo.join(espera_s)
    _ESTADO.update(iniciado=False, hilo=None, capturas=0, capturador=None)
    with _CANDADO:
        _CAPTURADAS.clear()
        _CAPTURAS_MEM.clear()


def _bucle():
    _cargar()
    if _PENDIENTES:
        _DESPERTAR.set()                       # lo que quedó de una sesión anterior (sin red, sin licencia)
    _ESTADO['ficha_en'] = time.time() + FICHA_ESPERA_S
    while not _ESTADO.get('parar'):
        # cada 10 min se reintenta lo pendiente aunque no haya errores nuevos; la ficha del equipo, a su hora
        espera = 600.0 if _ESTADO.get('ficha_hecha') else max(1.0, min(600.0, _ESTADO['ficha_en'] - time.time()))
        _DESPERTAR.wait(timeout=espera)
        _DESPERTAR.clear()
        if _ESTADO.get('parar'):
            break
        try:
            if _COLA:
                time.sleep(ESPERA_LOTE_S)
            _procesar_cola()
            _guardar_capturas()
            _enviar()
        except Exception:
            pass
        try:
            _enviar_ficha()
        except Exception:
            _ESTADO['ficha_hecha'] = True


# ---------------------------------------------------------------------------------------------------------------------------------------
# la ficha del equipo (v5.72): a pagos/equipo.php una vez al día o cuando cambia; la app Ventas la muestra por equipo
# ---------------------------------------------------------------------------------------------------------------------------------------
def _privada(obj):
    """Cada texto de la ficha pasado por privado() (un fallo de la puesta al día puede llevar una ruta)."""
    if isinstance(obj, str):
        return privado(obj)
    if isinstance(obj, list):
        return [_privada(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _privada(v) for k, v in obj.items()}
    return obj


def _ficha_json(f):
    """La ficha en JSON compacto de FICHA_MAX bytes como mucho (si no cabe, primero se cortan las listas largas)."""
    f = _privada(f)
    texto = json.dumps(f, ensure_ascii=False, separators=(',', ':'))
    if len(texto.encode('utf-8')) > FICHA_MAX:
        puesta = f.get('puesta_al_dia') or {}
        for k in ('hecho', 'pendiente', 'fallos'):
            puesta[k] = [t[:200] for t in (puesta.get(k) or [])[:5]]
        for k in ('gpus', 'pantallas', 'discos'):
            f[k] = (f.get(k) or [])[:4]
        texto = json.dumps(f, ensure_ascii=False, separators=(',', ':'))
    return texto if len(texto.encode('utf-8')) <= FICHA_MAX else ''


def _enviar_ficha():
    if _ESTADO.get('ficha_hecha') or time.time() < _ESTADO.get('ficha_en', 0):
        return
    import archivos_seguros
    import ficha_equipo
    import licencia
    datos = licencia.local()
    if not datos or not datos.get('clave'):
        _ESTADO['ficha_hecha'] = True          # sin licencia activada: el servidor no la aceptaría (va en la próxima sesión)
        return
    f = _ficha_ahora()
    huella = ficha_equipo.huella(f)
    previo = archivos_seguros.leer_json(FICHA_ENVIADA, defecto={}) or {}
    if previo.get('huella') == huella and time.time() - float(previo.get('cuando') or 0) < FICHA_CADA_S:
        _ESTADO['ficha_hecha'] = True
        return
    texto = _ficha_json(f)
    if not texto:
        _ESTADO['ficha_hecha'] = True
        return
    codigo, espera, _r = _post({'clave': datos['clave'], 'equipo': licencia.id_equipo(), 'version': licencia._version(),
                                'so': licencia._sistema(), 'resumen': privado(ficha_equipo.resumen(f))[:300], 'ficha': texto},
                               url=URL_FICHA)
    if codigo == 200:
        archivos_seguros.escribir_json(FICHA_ENVIADA, {'huella': huella, 'cuando': time.time()})
        _ESTADO['ficha_hecha'] = True
    elif codigo in (400, 404, 405, 413):
        _ESTADO['ficha_hecha'] = True          # no la quiere (o un servidor sin equipo.php): reintentar en esta sesión no sirve
    else:
        _ESTADO['ficha_en'] = time.time() + (espera or 1800)      # sin red, 429, 5xx


def _procesar_cola():
    with _CANDADO:
        nuevas, _COLA[:] = list(_COLA), []
    if not nuevas:
        return
    for e in nuevas:
        # el Registro junta las repeticiones en la MISMA entrada (e.veces sube): solo cuenta lo que no se contó antes
        veces = max(1, int(getattr(e, 'veces', 1)))
        nuevas_veces = veces - _CONTADAS.get(id(e), (None, 0))[1]
        if nuevas_veces <= 0:
            continue
        _CONTADAS[id(e)] = (e, veces)           # (la entrada va en la tupla: mientras esté aquí su id no se reutiliza)
        if len(_CONTADAS) > 600:
            for k in list(_CONTADAS)[:200]:
                _CONTADAS.pop(k, None)
        f = firma(e.origen, e.mensaje)
        previo = _PENDIENTES.get(f)
        if previo is not None:
            previo['veces'] += nuevas_veces
            previo['cuando'] = time.time()
            continue
        _PENDIENTES[f] = _armar(e, f)
        _PENDIENTES[f]['veces'] = nuevas_veces
    _recortar()
    _guardar()


# Rutas del PROGRAMA (se quedan: dicen dónde falló el código); cualquier otra ruta es del usuario y se anonimiza
_DEL_PROGRAMA = ('program files', '\\_internal', '/_internal', 'site-packages', 'blackmagic', 'cinecaptions', '\\windows\\', 'programdata',
                 '\\appdata\\', '/appdata/', '.app/contents', 'davincisubtitles\\motor', '1_codigo', '2_recursos', 'motor_qwen', 'motor_compat')
_EXT_MEDIOS = r'mp4|mov|mkv|m4v|avi|webm|mxf|wav|mp3|m4a|aac|flac|ogg|drp|drt|drb|srt|png|jpe?g|psd|aep|prproj'
# Una sola pasada: primero la ruta ENTRE comillas (puede llevar espacios), si no, la suelta (hasta el primer espacio). Con dos pasadas la
# segunda volvía a cortar una ruta ya conservada («C:\Program» de «C:\Program Files\…») y la anonimizaba a medias.
_RUTA = re.compile(r'''(['"«“])((?:[A-Za-z]:[\\/]|\\\\|~[\\/]|/(?:Users|Volumes|home|media|mnt|private|tmp)/)[^'"»”\n]*)(['"»”])'''
                   r'''|(?:[A-Za-z]:[\\/]|\\\\[^\s\\]+\\|~[\\/]|/(?:Volumes|home|media|mnt|private|tmp)/)[^\s'"«»“”<>|]*''')
_ARCHIVO_MEDIO = re.compile(r'''(?<![\\/\w])[^\s\\/'"«»“”<>|:]+\.(?:''' + _EXT_MEDIOS + r''')\b''', re.IGNORECASE)


def _ruta_anonima(ruta):
    """«D:\\Clientes\\Maria Lopez\\boda.mp4» → «D:\\…\\archivo.mp4 (33 car.)»: queda lo que sirve para el fallo (disco, extensión, largo, si
    lleva letras no ASCII) y nada de nombres. Las del programa, tal cual."""
    if any(m in ruta.lower().replace('/', '\\') or m in ruta.lower() for m in _DEL_PROGRAMA):
        return ruta
    partes = [p for p in re.split(r'[\\/]', ruta) if p]
    nombre = partes[-1] if partes else ''
    ext = os.path.splitext(nombre)[1] if '.' in nombre[1:] else ''
    sep = '\\' if '\\' in ruta else '/'
    raiz = ruta[:2] if re.match(r'[A-Za-z]:', ruta) else ('~' if ruta.startswith('~') else ('\\\\' if ruta.startswith('\\\\') else ''))
    tildes = ', con letras no ASCII' if any(ord(c) > 127 for c in ruta) else ''
    return f'{raiz}{sep}…{sep}archivo{ext} ({len(ruta)} car.{tildes})'


def privado(texto):
    """El texto sin la carpeta del usuario, sin sus rutas en otros discos y sin nombres de sus videos, audios o proyectos."""
    texto = registro._sin_usuario(str(texto or ''))
    texto = _RUTA.sub(lambda m: (m.group(1) + _ruta_anonima(m.group(2)) + m.group(3)) if m.group(1) else _ruta_anonima(m.group(0)), texto)
    # los nombres sueltos de videos/audios/proyectos (sin carpeta), salvo dentro de una ruta del programa que se conservó
    return _ARCHIVO_MEDIO.sub(lambda m: m.group(0) if _es_del_programa(texto, m) else 'archivo' + os.path.splitext(m.group(0))[1], texto)


def _es_del_programa(texto, m):
    """¿El nombre de archivo `m` está dentro de una ruta del programa (que se deja tal cual)?"""
    inicio = max(texto.rfind(c, 0, m.start()) for c in (' ', '"', "'", '«', '\n', '('))
    return any(x in texto[inicio + 1:m.end()].lower() for x in _DEL_PROGRAMA)


def _armar(e, f):
    """El dict que se manda: el informe de «Copiar este error» SIN «lo que pasó justo antes» (antes=0: esas notas dicen de qué trata el
    video, el nombre del proyecto y del timeline) y pasado por privado()."""
    titulo = ''
    try:
        import registro_ayuda
        titulo = registro_ayuda.explicar(e).titulo
    except Exception:
        pass
    try:
        detalle = registro.informe_de_error(e, antes=0)
    except Exception:
        detalle = e.detalle or ''
    detalle = privado(detalle)
    if len(detalle) > DETALLE_MAX:
        detalle = detalle[:DETALLE_MAX] + '\n…'
    return {'firma': f, 'nivel': 'error', 'titulo': privado(titulo)[:190], 'mensaje': privado(e.mensaje)[:600],
            'origen': privado(e.origen or '')[:120], 'detalle': detalle, 'veces': max(1, int(getattr(e, 'veces', 1))),
            'cuando': time.time()}


def _recortar():
    ahora = time.time()
    for f in [f for f, d in _PENDIENTES.items() if ahora - float(d.get('cuando', 0)) > CADUCA_S]:
        _PENDIENTES.pop(f, None)
        _borrar_captura(f)
    if len(_PENDIENTES) > PENDIENTES_MAX:
        for f, _d in sorted(_PENDIENTES.items(), key=lambda kv: kv[1].get('cuando', 0))[:len(_PENDIENTES) - PENDIENTES_MAX]:
            _PENDIENTES.pop(f, None)
            _borrar_captura(f)


def _cargar():
    try:
        import archivos_seguros
        datos = archivos_seguros.leer_json(ARCHIVO, defecto={}) or {}
        for f, d in (datos.get('pendientes') or {}).items():
            if isinstance(d, dict) and re.fullmatch(r'[0-9a-f]{40}', str(f)) and d.get('mensaje'):
                d['veces'] = max(1, int(d.get('veces') or 1))
                for cual in ('captura', 'ventana'):
                    if d.get(cual) and not _archivo_captura(f, cual).exists():
                        d.pop(cual, None)
                _PENDIENTES[f] = d
        _recortar()
    except Exception:
        pass
    try:                                        # capturas sueltas (su error ya se mandó o caducó, o se cortó al guardarla)
        if CAPTURAS.is_dir():
            for p in CAPTURAS.iterdir():
                firma_p, _, resto = p.name.partition('.')
                cual = {'jpg': 'captura', 'ventana.jpg': 'ventana'}.get(resto)       # (v5.73: «<firma>.ventana.jpg» es la 2.ª)
                if cual is None or firma_p not in _PENDIENTES or not _PENDIENTES[firma_p].get(cual):
                    p.unlink(missing_ok=True)
    except Exception:
        pass


def _guardar():
    try:
        import archivos_seguros
        if _PENDIENTES:
            archivos_seguros.escribir_json(ARCHIVO, {'pendientes': _PENDIENTES})
        elif ARCHIVO.exists():
            ARCHIVO.unlink()
    except Exception:
        pass


def _listos():
    """Los pendientes que toca mandar ahora (el mismo error, no antes de REPETIR_S desde su último envío)."""
    ahora = time.time()
    return [d for f, d in _PENDIENTES.items() if ahora - _ESTADO['ultimo_envio'].get(f, 0.0) >= REPETIR_S][:POR_PETICION]


def _enviar():
    if not _PENDIENTES or time.time() < _ESTADO['pausa_hasta'] or _ESTADO['enviados'] >= TOPE_SESION:
        return
    import licencia
    datos = licencia.local()
    if not datos or not datos.get('clave'):
        return                                  # sin licencia activada en este equipo: se queda pendiente
    lote = _listos()
    if not lote:
        _ESTADO['pausa_hasta'] = time.time() + 60
        return
    campos = [{k: d[k] for k in ('firma', 'nivel', 'titulo', 'mensaje', 'origen', 'detalle', 'veces')} for d in lote]
    archivos = []
    for d, c in zip(lote, campos):              # v5.72: la captura de cada error (multipart «captura_<firma>»)
        if d.get('captura') and len(archivos) < IMAGENES_POR_PETICION:
            try:
                archivos.append(('captura_' + d['firma'], _archivo_captura(d['firma']).read_bytes()))
                c['captura'] = d['captura'].get('tipo') or 'pantalla'
            except OSError:
                d.pop('captura', None)
        # v5.73: la ventana del programa, la 2.ª («ventana_<firma>»; un errores.php anterior la ignora y guarda solo la 1.ª)
        if d.get('ventana') and len(archivos) < IMAGENES_POR_PETICION:
            try:
                archivos.append(('ventana_' + d['firma'], _archivo_captura(d['firma'], 'ventana').read_bytes()))
                c['ventana'] = True
            except OSError:
                d.pop('ventana', None)
    try:
        equipo_datos = datos_equipo()
    except Exception:
        equipo_datos = ''
    codigo, espera, respuesta = _post({'clave': datos['clave'], 'equipo': licencia.id_equipo(), 'version': licencia._version(),
                                       'so': licencia._sistema(), 'equipo_datos': equipo_datos,
                                       'errores': json.dumps(campos, ensure_ascii=False)}, archivos)
    if codigo in (400, 413) and archivos:
        # demasiado grande para el servidor (su tope de subida; si pasa post_max_size PHP tira todo el formulario y un errores.php viejo
        # daría 400 «Faltan datos»): esos errores se mandan sin captura en la siguiente vuelta
        for d in lote:
            if (d.pop('captura', None) is not None) | (d.pop('ventana', None) is not None):
                _borrar_captura(d['firma'])
        _guardar()
        _ESTADO['pausa_hasta'] = time.time() + 30
        _DESPERTAR.set()
        return
    if codigo == 200 or codigo in (400, 404, 413):
        # 200 = guardados; 400/404/413 = el servidor no los quiere (datos raros, equipo no activado): reintentar no sirve.
        # Con 200 el servidor dice cuántos guardó (por el tope por hora pueden ser menos): el resto se queda y se reintenta en una hora.
        hechos = len(lote)
        if codigo == 200 and isinstance(respuesta, dict) and isinstance(respuesta.get('guardados'), int):
            hechos = max(0, min(len(lote), respuesta['guardados']))
        ahora = time.time()
        for d in lote[:hechos] if codigo == 200 else lote:
            _PENDIENTES.pop(d['firma'], None)
            _borrar_captura(d['firma'])
            _ESTADO['ultimo_envio'][d['firma']] = ahora
        _ESTADO['enviados'] += 1
        _guardar()
        if codigo == 200 and hechos < len(lote):
            _ESTADO['pausa_hasta'] = time.time() + 3600
        elif codigo == 200 and _PENDIENTES:
            _DESPERTAR.set()                    # quedan más (más de POR_PETICION o repetidos que ya pueden ir)
        return
    _ESTADO['pausa_hasta'] = time.time() + (espera or 300)      # sin red, 429, 503, 500: se reintenta más tarde


def _multipart(campos, archivos):
    """(cuerpo, Content-Type) de un formulario multipart con los campos y las capturas [(nombre, bytes)]."""
    limite = '----CineCaptions' + os.urandom(12).hex()
    partes = []
    for k, v in campos.items():
        partes += [('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n' % (limite, k)).encode('ascii'),
                   str(v).encode('utf-8'), b'\r\n']
    for nombre, datos in archivos:
        png = datos[:8] == b'\x89PNG\r\n\x1a\n'
        partes += [('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s.%s"\r\nContent-Type: %s\r\n\r\n'
                    % (limite, nombre, nombre, 'png' if png else 'jpg', 'image/png' if png else 'image/jpeg')).encode('ascii'),
                   datos, b'\r\n']
    partes.append(('--%s--\r\n' % limite).encode('ascii'))
    return b''.join(partes), 'multipart/form-data; boundary=' + limite


def _post(campos, archivos=None, url=None):
    """(código HTTP o 0 sin red, segundos de Retry-After o None, el JSON de la respuesta o None). Con `archivos` va en multipart
    (errores.php anterior a la 5.72 lo lee igual: PHP pone los campos en $_POST y no mira las capturas)."""
    import licencia
    if archivos:
        cuerpo, tipo = _multipart(campos, archivos)
    else:
        cuerpo, tipo = urllib.parse.urlencode(campos).encode('utf-8'), 'application/x-www-form-urlencoded'
    req = urllib.request.Request(url or URL, data=cuerpo, method='POST',
                                 headers={'Accept': 'application/json', 'Content-Type': tipo,
                                          'User-Agent': 'CineCaptions/%s' % licencia._version()})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S + (45 if archivos else 0), context=licencia._ssl()) as r:
            cuerpo = r.read(65536)
            try:
                respuesta = json.loads(cuerpo or b'{}')
            except ValueError:
                respuesta = None
            return r.status, None, respuesta
    except urllib.error.HTTPError as e:
        try:
            espera = int(e.headers.get('Retry-After') or 0) or None
        except (TypeError, ValueError):
            espera = None
        return e.code, espera, None
    except Exception:
        return 0, None, None


def esperar_envios(segundos=30.0):
    """Para pruebas: espera a que no quede nada por procesar (True) o a que pase el tiempo (False)."""
    fin = time.time() + segundos
    while time.time() < fin:
        if not _COLA and not _PENDIENTES:
            return True
        time.sleep(0.2)
    return False
