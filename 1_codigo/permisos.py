# CineCaptions · By Cinema Productions
# 1_codigo/permisos.py — la ventana «Permisos de CineCaptions» tras instalar o actualizar: qué necesita en este equipo (Mac y Windows) y si ya lo tiene.
"""
permisos.py  (v5.98)
--------------------
Pedido del usuario: «en Mac y Windows, que salga un pop-up para que le den permisos —control de administración, telemetría y más
permisos de control total—; así como en Mac va pidiendo permisos, una vez actualizado o instalado sale el pop-up con el listado de
permisos que necesita, y si ya están activos que ya no vuelva a salir».

Cada permiso = {id, titulo, texto, estado ('ok' | 'falta'), requerido, boton, accion}. Lo que se mira (rápido, sin red):
- Mac: Accesibilidad (AXIsProcessTrusted: pulsar los menús de Resolve), Automatización de «System Events» (AEDeterminePermissionToAutomate-
  Target sin preguntar; -1743 = denegado) y Acceso total al disco (si se puede leer TCC.db). Pedir = la ventana del sistema (osascript a
  System Events la provoca la primera vez) o abrir su panel de Ajustes del Sistema.
- Windows: Administrador = lo que «Tu equipo» dejó pendiente (Visual C++ o el driver de la GPU: ficha_equipo / equipo_al_dia, UNA ventana de
  permiso de Windows), Notificaciones (ToastEnabled del registro) y el Control inteligente de aplicaciones (si está activado, bloquea partes
  sin firma). NO se excluye CineCaptions del antivirus: los antivirus tratan eso como conducta sospechosa.
- Los dos: Informes de errores (telemetria_errores; preferencia enviar_errores) con su interruptor: cuenta como hecho al verlo.

Cuándo sale (revisar_al_abrir, unos segundos después de abrir, fuera de cualquier otra ventana): v5.99 (el usuario: «la ventana no se
cierra hasta que tengas todos los permisos; en Mac todo debe estar permitido, igual en Windows»): TODO es obligatorio (también los informes
de errores, encendidos) y sale en CADA arranque mientras falte algo. Sin X, sin «Más tarde», sin Esc ni clic fuera: «Listo» solo se puede
pulsar con todo permitido; la única otra salida es «Salir de CineCaptions» (cierra el programa; al abrirlo vuelve). Lo que no se puede
saber (None) no bloquea. Lo lento (la ficha del equipo) se lee en un hilo; con la ventana abierta se vuelve a mirar cada 1,5 s.
"""
import os
import sys
import time
from pathlib import Path

ES_MAC = sys.platform == 'darwin'
ES_WIN = sys.platform.startswith('win')
REPETIR_S = 24 * 3600


def _tr(t, **kw):
    try:
        from i18n import tr
        return tr(t, **kw)
    except Exception:
        return t.format(**kw) if kw else t


def _prefs():
    try:
        import ajustes_ui
        return ajustes_ui.leer_prefs()
    except Exception:
        return {}


def _guardar(cambios):
    try:
        import ajustes_ui
        ajustes_ui.guardar_prefs(cambios)
    except Exception:
        pass


def _version():
    try:
        import version
        return str(version.APP_VERSION)
    except Exception:
        return ''


# ------------------------------------------------------------------------------------------------------------------ Mac
def _fourcc(s):
    return int.from_bytes(s.encode('ascii'), 'big')


def mac_accesibilidad():
    """True / False (None si no se puede saber)."""
    try:
        import ctypes
        ax = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
        ax.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(ax.AXIsProcessTrusted())
    except Exception:
        return None


def mac_automatizacion(bundle='com.apple.systemevents'):
    """El permiso de Automatización sobre `bundle`, sin preguntar: True (concedido) / False (denegado o sin pedir) / None (no se sabe)."""
    try:
        import ctypes

        class AEDesc(ctypes.Structure):
            _fields_ = [('descriptorType', ctypes.c_uint32), ('dataHandle', ctypes.c_void_p)]
        cs = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreServices.framework/CoreServices')
        cs.AECreateDesc.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_long, ctypes.POINTER(AEDesc)]
        cs.AECreateDesc.restype = ctypes.c_int16
        cs.AEDeterminePermissionToAutomateTarget.argtypes = [ctypes.POINTER(AEDesc), ctypes.c_uint32, ctypes.c_uint32, ctypes.c_bool]
        cs.AEDeterminePermissionToAutomateTarget.restype = ctypes.c_int32
        cs.AEDisposeDesc.argtypes = [ctypes.POINTER(AEDesc)]
        d = AEDesc()
        b = bundle.encode('utf-8')
        if cs.AECreateDesc(_fourcc('bund'), b, len(b), ctypes.byref(d)) != 0:
            return None
        try:
            r = cs.AEDeterminePermissionToAutomateTarget(ctypes.byref(d), _fourcc('****'), _fourcc('****'), False)
        finally:
            cs.AEDisposeDesc(ctypes.byref(d))
        if r == 0:
            return True
        if r in (-1743, -1744):                  # denegado / aún no se ha preguntado
            return False
        return None                              # -600: System Events no está corriendo (se abre al pedirlo)
    except Exception:
        return None


def mac_disco_completo():
    """¿Tiene Acceso total al disco? (se puede leer la base de permisos del usuario, que macOS solo deja leer con ese permiso)."""
    db = Path.home() / 'Library' / 'Application Support' / 'com.apple.TCC' / 'TCC.db'
    try:
        with open(db, 'rb') as f:
            f.read(16)
        return True
    except PermissionError:
        return False
    except OSError:
        return None


def _abrir_panel_mac(ancla):
    import subprocess
    subprocess.Popen(['open', f'x-apple.systempreferences:com.apple.preference.security?{ancla}'])


def _pedir_automatizacion():
    """La primera vez, macOS enseña su ventana «CineCaptions quiere controlar System Events»; si ya se negó, el panel."""
    import subprocess
    try:
        subprocess.run(['osascript', '-e', 'tell application "System Events" to count processes'], capture_output=True, timeout=60)
    except Exception:
        pass
    if mac_automatizacion() is not True:
        _abrir_panel_mac('Privacy_Automation')


def _pedir_accesibilidad():
    try:                                         # (la ventana del sistema «abrir Ajustes del Sistema» la primera vez)
        import subprocess
        subprocess.run(['osascript', '-e', 'tell application "System Events" to get name of every menu bar item of menu bar 1 of '
                        'first process whose frontmost is true'], capture_output=True, timeout=30)
    except Exception:
        pass
    if mac_accesibilidad() is not True:
        _abrir_panel_mac('Privacy_Accessibility')


# ------------------------------------------------------------------------------------------------------------------ Windows
def win_notificaciones():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\PushNotifications') as k:
            v, _t = winreg.QueryValueEx(k, 'ToastEnabled')
            return int(v) != 0
    except FileNotFoundError:
        return True                              # (sin el valor: de fábrica, encendidas)
    except Exception:
        return None


def _ficha():
    try:
        import ficha_equipo
        return ficha_equipo.de_esta_sesion()
    except Exception:
        return {}


def win_admin_pendiente(ficha=None):
    """Lo que «Tu equipo» necesita con permiso de administrador y aún no tiene: [texto…] (Visual C++, driver de la GPU)."""
    f = ficha if ficha is not None else _ficha()
    faltan = [x.get('texto') or x.get('id') for x in (f.get('revision') or []) if x.get('id') in ('vcredist', 'driver_gpu') and x.get('estado') == 'falta']
    faltan += [str(t) for t in ((f.get('puesta_al_dia') or {}).get('pendiente') or []) if str(t) not in faltan]
    return faltan


def win_smart_app_control(ficha=None):
    """True si el Control inteligente de aplicaciones está activado o en evaluación (bloquea partes de CineCaptions). v5.99: se lee EN VIVO
    del registro (la ficha es de la sesión: al apagarlo con la ventana abierta no se enteraba); la ficha, solo si el registro no responde."""
    try:
        import salud
        sac = salud.smart_app_control()
        if sac is not None:
            return sac in ('activado', 'evaluacion')
    except Exception:
        pass
    f = ficha if ficha is not None else _ficha()
    return any(x.get('id') == 'smart_app_control' and x.get('estado') == 'falta' for x in (f.get('revision') or []))


def _pedir_admin():
    import equipo_al_dia
    import ficha_equipo
    f = _ficha()
    puesta = equipo_al_dia.poner_al_dia(f, interactivo=True)
    try:
        f['puesta_al_dia'] = puesta
        ficha_equipo.guardar(f)
    except Exception:
        pass
    try:
        ficha_equipo._SESION['ficha'] = None     # (que se vuelva a leer: el driver o Visual C++ pueden haber cambiado)
    except Exception:
        pass


def _abrir(uri):
    try:
        os.startfile(uri)
    except Exception:
        pass


# ------------------------------------------------------------------------------------------------------------------ la lista
def lista(ficha=None):
    """Los permisos de ESTE equipo. Fuera del hilo de la interfaz la primera vez (la ficha del equipo).
    v5.99 (el usuario: «la ventana no se cierra hasta que tengas todos los permisos… en Mac todo debe estar permitido, igual en Windows»):
    TODOS obligatorios, también los informes de errores (encendidos). Lo que no se puede saber (None) no bloquea: si no, nadie saldría."""
    p = _prefs()
    sal = []

    def poner(i, titulo, texto, ok, boton, accion):
        sal.append({'id': i, 'titulo': titulo, 'texto': texto, 'estado': 'ok' if ok else 'falta', 'requerido': True,
                    'boton': boton, 'accion': accion})
    if ES_MAC:
        poner('accesibilidad', _tr('Accesibilidad'), _tr('Para pulsar por ti los menús de DaVinci Resolve (colocar los subtítulos y reproducir).'),
              mac_accesibilidad() is not False, _tr('Permitir'), _pedir_accesibilidad)
        poner('automatizacion', _tr('Automatización'), _tr('Para hablar con DaVinci Resolve y con macOS («System Events»).'),
              mac_automatizacion() is not False, _tr('Permitir'), _pedir_automatizacion)
        poner('disco', _tr('Acceso total al disco'), _tr('Para abrir tus videos de cualquier carpeta sin que macOS pregunte cada vez. Si al activarlo no cambia, sal y vuelve a abrir CineCaptions.'),
              mac_disco_completo() is not False, _tr('Abrir ajustes'), lambda: _abrir_panel_mac('Privacy_AllFiles'))
    elif ES_WIN:
        f = ficha if ficha is not None else _ficha()
        pend = win_admin_pendiente(f)
        poner('admin', _tr('Administrador'), _tr('Para poner tu equipo al día una vez (Visual C++ y el driver de la tarjeta gráfica). Windows te pedirá permiso.')
              + (('\n' + ' · '.join(pend[:2])) if pend else ''), not pend, _tr('Permitir'), _pedir_admin)
        poner('notificaciones', _tr('Notificaciones'), _tr('Para avisarte cuando GO termina o hay una actualización.'),
              win_notificaciones() is not False, _tr('Abrir ajustes'), lambda: _abrir('ms-settings:notifications'))
        poner('smart_app_control', _tr('Control inteligente de aplicaciones'),
              _tr('Mientras esté activado, Windows bloquea partes de CineCaptions. Hay que desactivarlo.'),
              not win_smart_app_control(f), _tr('Abrir ajustes'), lambda: _abrir('windowsdefender://smartapp'))
    on = p.get('enviar_errores') is not False
    sal.append({'id': 'telemetria', 'titulo': _tr('Informes de errores'),
                'texto': _tr('Si algo falla, nos llega el informe (nunca tus videos, audio ni textos) para arreglarlo antes.'),
                'estado': 'ok' if on else 'falta', 'requerido': True, 'boton': None, 'accion': None,
                'interruptor': on})
    return sal


def faltan(items):
    return [x for x in (items or []) if x['estado'] != 'ok']


def hay_que_mostrar(items, ahora=None):
    """v5.99: en CADA arranque mientras falte algo (antes: con versión nueva o, si faltaba algo obligatorio, una vez al día)."""
    return bool(faltan(items))


def marcar_visto(telemetria=None):
    cambios = {'permisos_version': _version(), 'permisos_ultimo': time.time(), 'telemetria_decidida': True}
    if telemetria is not None:
        cambios['enviar_errores'] = bool(telemetria)
    _guardar(cambios)


# ------------------------------------------------------------------------------------------------------------------ la ventana
def revisar_al_abrir(app, intento=0):
    """Unos segundos después de abrir: si hace falta, la ventana (nunca encima de otra ventana del programa; reintenta un rato)."""
    import qt_kit as ui
    if os.environ.get('CINECAPTIONS_SIN_PERMISOS') == '1':
        return

    def fin(items, error):
        if error is not None or not ui.vivo(app) or not hay_que_mostrar(items):
            if items and all(x['estado'] == 'ok' for x in items):
                _guardar({'permisos_version': _version()})
            return
        if _hay_otra_capa(app) and intento < 8:
            ui.despues(15000, lambda: revisar_al_abrir(app, intento + 1), app)
            return
        mostrar(app, items)
    ui.correr_en_hilo(app, lista, fin)


def _hay_otra_capa(app):
    """¿Hay algo en medio? Otra ventana del programa, la licencia, un GO, el editor, las novedades o la guía (que salen antes)."""
    try:
        from PySide6.QtWidgets import QApplication
        import ajustes_ui
        if QApplication.activeModalWidget() is not None or any(c.isVisible() for c in app.findChildren(ajustes_ui.CapaModal)):
            return True
        if (getattr(app, '_recorrido', None) is not None or getattr(app, '_lic_pidiendo', False) or getattr(app, '_dlg_act_abierto', False)
                or getattr(app, '_editor', None) is not None or not app.isVisible() or app.isMinimized()):
            return True
        if callable(getattr(app, '_trabajando', None)) and app._trabajando():
            return True
        if ajustes_ui.leer_prefs().get('version_vista') != _version():
            return True                          # (las novedades de esta versión aún no se han visto: salen primero)
        import tutoriales
        if tutoriales.toca_guia():
            return True                          # (la guía de esta versión aún tiene que salir)
    except Exception:
        pass
    return False


def mostrar(app, items=None):
    panel = _clase()(app, items if items is not None else lista())
    panel.abrir()
    return panel


def _crear_panel_clase():
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QFrame
    import qt_kit as ui
    import ajustes_ui as A
    from qt_kit import BooleanVar, Boton, Etiqueta, Interruptor, caja_h, caja_v

    class PanelPermisos(A._Panel):
        def __init__(self, app, items):
            super().__init__(None, radio=20)
            self.app = app
            self.items = items
            self._capa = None
            self._filas = {}
            self.setFixedWidth(780)
            from PySide6.QtWidgets import QVBoxLayout
            cv = QVBoxLayout(self)
            cv.setContentsMargins(34, 28, 34, 26)
            cv.setSpacing(16)
            cab = A._cabecera(_tr('Antes de empezar'), _tr('Permisos de CineCaptions'), lambda: None, tam=26)
            for b in cab.findChildren(A.BotonIcono):         # v5.99: sin la X; no se cierra hasta tenerlo todo
                b.hide()
            cv.addWidget(cab)
            cv.addWidget(Etiqueta(_tr('Para usar CineCaptions hace falta TODO esto en tu equipo. La ventana se cierra cuando esté todo permitido.'),
                                  14, color=ui.TEXT_MUTED, envolver=True))
            grupo, cg = caja_v(espacio=0)
            grupo.setObjectName('grupoAjustes')
            for n, it in enumerate(items):
                if n:
                    raya = QFrame()
                    raya.setFixedHeight(1)
                    raya.setStyleSheet('background-color: #1E2A42; border: none;')
                    cg.addWidget(raya)
                cg.addWidget(self._fila(it))
            cv.addWidget(grupo)
            pie, cp = caja_h(espacio=10)
            self.estado = Etiqueta('', 13, color=ui.TEXT_MUTED)
            cp.addWidget(self.estado, 1)
            cp.addWidget(Boton(_tr('Salir de CineCaptions'), self._salir, tipo='neutro', alto=42, tam=14))   # (sin «Más tarde»)
            self.listo_btn = Boton(_tr('Listo'), self._listo, tipo='primario', alto=42, tam=14)
            cp.addWidget(self.listo_btn)
            cv.addWidget(pie)
            self._reloj = QTimer(self)
            self._reloj.setInterval(1500)
            self._reloj.timeout.connect(self._revisar)
            self._ocupado = False
            self._pintar()

        def _fila(self, it):
            fila, cf = caja_h(espacio=14, margenes=(18, 14, 18, 14))
            col, cc = caja_v(espacio=3)
            t = Etiqueta(it['titulo'], 15, peso='negrita', color='#FFFFFF')
            cc.addWidget(t)
            cc.addWidget(Etiqueta(it['texto'], 13, color=ui.TEXT_MUTED, envolver=True))
            cf.addWidget(col, 1)
            chip = Etiqueta('', 12, peso='negrita')
            cf.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
            ctrl = None
            if 'interruptor' in it:
                var = BooleanVar(bool(it['interruptor']))
                ctrl = Interruptor('', var=var, comando=lambda i=it: self._cambio_telemetria(i))
                self._telemetria = var
            elif it.get('accion'):
                ctrl = Boton(it['boton'], lambda _=False, i=it: self._pedir(i), tipo='neutro', alto=38, tam=13)
            if ctrl is not None:
                cf.addWidget(ctrl, 0, Qt.AlignmentFlag.AlignVCenter)
            self._filas[it['id']] = (chip, ctrl)
            return fila

        def _cambio_telemetria(self, it):
            it['estado'] = 'ok' if self._telemetria.get() else 'falta'
            self._pintar()

        def _pintar(self):
            for it in self.items:
                chip, ctrl = self._filas[it['id']]
                ok = it['estado'] == 'ok'
                chip.setText(('✓ ' + _tr('Listo')) if ok else _tr('Falta'))
                chip.setStyleSheet('color: %s;' % (ui.ACCENT_CLARO if ok else '#FF7A7A'))
                if ctrl is not None and it['id'] != 'telemetria':
                    ctrl.setVisible(not ok)
            n = len(faltan(self.items))
            self.estado.setText(_tr('Todo listo') if not n else (_tr('Falta 1 permiso') if n == 1 else _tr('Faltan {n} permisos', n=n)))
            self.estado.setStyleSheet('color: %s;' % (ui.ACCENT_CLARO if not n else '#FF7A7A'))
            self.listo_btn.setEnabled(not n)                  # v5.99: «Listo» solo con todo permitido

        def _pedir(self, it):
            if self._ocupado:
                return
            self._ocupado = True
            chip, ctrl = self._filas[it['id']]
            chip.setText(_tr('Pidiendo permiso…'))

            def fin(_r, _e):
                self._ocupado = False
                self._revisar()
            ui.correr_en_hilo(self.app, it['accion'], fin)

        def _revisar(self):
            if self._ocupado or not ui.vivo(self):
                return

            def fin(items, error):
                if error is None and items and ui.vivo(self):
                    for x in items:
                        if x['id'] != 'telemetria':
                            for y in self.items:
                                if y['id'] == x['id']:
                                    y['estado'] = x['estado']
                    self._pintar()
            ui.correr_en_hilo(self.app, lista, fin)

        def _cerrar(self):
            marcar_visto(getattr(self, '_telemetria', None).get() if getattr(self, '_telemetria', None) is not None else None)
            self._reloj.stop()
            if self._capa is not None and ui.vivo(self._capa):
                self._capa.cerrar()

        def _salir(self):
            """Sin todos los permisos no se usa: la única salida es cerrar el programa (la ventana vuelve al abrirlo)."""
            self._reloj.stop()
            try:
                self.app.close()
            except Exception:
                from PySide6.QtWidgets import QApplication
                QApplication.quit()

        def _listo(self):
            if faltan(self.items):                            # (por si acaso: no se cierra con algo pendiente)
                self._pintar()
                return
            self._cerrar()

        def abrir(self):
            from PySide6.QtCore import QRect

            def centrado(ancho_v, alto_v, panel):           # (centrado, con su ancho fijo y el alto que pide)
                capa = panel.layout()                       # v5.99: el alto para SU ancho (los textos que saltan de línea; con
                alto_c = capa.heightForWidth(panel.width()) if capa is not None and capa.hasHeightForWidth() else -1   # sizeHint sobraban
                alto = min(alto_c if alto_c > 0 else panel.sizeHint().height(), alto_v - 60)   # huecos entre el título y la lista)
                return QRect((ancho_v - panel.width()) // 2, (alto_v - alto) // 2, panel.width(), alto)
            self._capa = A.CapaModal(self.app, self, cerrar_fuera=False, posicion=centrado)
            self._capa.cerrar_con_esc = False                 # v5.99: ni Esc ni clic fuera la cierran
            self._reloj.start()

    return PanelPermisos


_CLASE = []


def _clase():
    """La clase de la ventana (se crea al usarla: así este módulo se importa sin Qt en las tareas y las pruebas)."""
    if not _CLASE:
        _CLASE.append(_crear_panel_clase())
    return _CLASE[0]
