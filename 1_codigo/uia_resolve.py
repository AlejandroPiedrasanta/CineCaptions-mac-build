# CineCaptions · By Cinema Productions
# 1_codigo/uia_resolve.py — la Accesibilidad de Windows (UI Automation) sobre DaVinci Resolve, DESDE PYTHON (v5.5.6)
"""
Antes esto lo hacían cuatro scripts de PowerShell lanzados con `-ExecutionPolicy Bypass -EncodedCommand …` y sin ventana: es exactamente el
patrón que los antivirus asocian a malware. Avast bloqueó `powershell.exe` («IDP.HELU.PSE94: detección de la línea de comandos») y con eso
el Puente de Resolve Free no arrancaba, ni se pasaba la pantalla de proyectos: GO fallaba entero. Ahora lo mismo va por la UI Automation de
Windows (UIAutomationCore.dll, del sistema y firmada por Microsoft) con comtypes, dentro de CineCaptions: ningún proceso extra.

Mismos códigos de salida que los scripts de antes (colocacion.py los interpreta igual):
    organizador(pids, nombre)            -> 'CREADO|<nombre>' | 'SIN_ORGANIZADOR' | 'SIN_BOTON' | 'SIN_DIALOGO' | 'SIN_CREAR' | 'NO_RESOLVE' | 'ERROR …'
    expandir(pids)                       -> 'EXPANDIDA' | 'YA_EXPANDIDA' | 'NO_CAMBIO' | 'SIN_BOTON' | 'SIN_VENTANA' | 'NO_RESOLVE' | 'ERROR …'
    reproducir(pids, menus, items)       -> 'REPRODUCIENDO' | 'SIN_MENU' | 'SIN_ITEM' | 'SIN_VENTANA' | 'ERROR …'
    lanzar_script(pids, script, menus, subs) -> 'LANZANDO' | 'SIN_MENU' | 'SIN_SCRIPT' | 'SIN_VENTANA' | 'ERROR …'
En las dos últimas, la pulsación del menú (Invoke) puede NO volver mientras dura lo que lanza (la reproducción, el Puente): va en un hilo
aparte y la función vuelve en cuanto lo pulsó. Solo Windows; en otro sistema, 'ERROR …'.
"""
import sys
import threading
import time

# ids de UI Automation (UIAutomationClient.h)
_PID, _TIPO, _NOMBRE, _AUTOID, _CLASE = 30002, 30003, 30005, 30011, 30012
_BOTON, _CASILLA, _EDICION, _MENU_ITEM = 50000, 50002, 50004, 50011
_HIJOS, _DESCENDIENTES = 2, 4
_INVOKE, _VALOR, _EXPANDIR, _TOGGLE = 10000, 10002, 10005, 10015

_HILO = threading.local()


def _api():
    """(módulo de tipos, IUIAutomation) de ESTE hilo (COM multihilo, iniciado una vez por hilo)."""
    if not sys.platform.startswith('win'):
        raise RuntimeError('UI Automation solo en Windows')
    if getattr(_HILO, 'u', None) is None:
        if 'comtypes' not in sys.modules:
            sys.coinit_flags = 0                                           # COINIT_MULTITHREADED para el hilo que lo importa (lo recomendado para UIA)
        import comtypes
        import comtypes.client as cc
        try:
            comtypes.CoInitializeEx(0)
        except OSError:
            pass                                                           # (ya iniciado en este hilo, con otro modo: vale igual)
        m = cc.GetModule('UIAutomationCore.dll')
        _HILO.m = m
        _HILO.u = cc.CreateObject(m.CUIAutomation, interface=m.IUIAutomation)
    return _HILO.m, _HILO.u


def _todos(raiz, ambito, cond):
    arr = raiz.FindAll(ambito, cond)
    if not arr:
        return []
    return [arr.GetElement(i) for i in range(arr.Length)]


def _primero(raiz, ambito, cond):
    try:
        e = raiz.FindFirst(ambito, cond)
        return e if e else None
    except Exception:
        return None


def _patron(e, ident, interfaz):
    return e.GetCurrentPattern(ident).QueryInterface(interfaz)


def _ventanas(u, pids):
    """Las ventanas de primer nivel de los procesos de Resolve."""
    out = []
    raiz = u.GetRootElement()
    for pid in pids or []:
        out += _todos(raiz, _HIJOS, u.CreatePropertyCondition(_PID, int(pid)))
    return out


def _principal(u, pids):
    return next((v for v in _ventanas(u, pids) if 'UiMainWindow' in str(v.CurrentClassName or '')), None)


def _buscar(u, raiz, tipo, termina):
    for e in _todos(raiz, _DESCENDIENTES, u.CreatePropertyCondition(_TIPO, tipo)):
        if str(e.CurrentAutomationId or '').endswith(termina):
            return e
    return None


def _por_nombre(u, raiz, nombres):
    for n in nombres:
        e = _primero(raiz, _DESCENDIENTES, u.CreatePropertyCondition(_NOMBRE, n))
        if e is not None:
            return e
    return None


def _desplegar(m, e):
    try:
        _patron(e, _EXPANDIR, m.IUIAutomationExpandCollapsePattern).Expand()
    except Exception:
        _patron(e, _INVOKE, m.IUIAutomationInvokePattern).Invoke()


def _pulsar_aparte(e, nombre):
    """Invoke en un hilo aparte (puede no volver hasta que acaba lo que lanza). El elemento se pasa entre hilos COM multihilo."""
    def trabajo():
        try:
            m, _u = _api()
            _patron(e, _INVOKE, m.IUIAutomationInvokePattern).Invoke()
        except Exception:
            pass
    threading.Thread(target=trabajo, daemon=True, name=nombre).start()


def _escape(veces=1):
    """Cierra un menú que quedó abierto (Escape) — solo si la ventana en primer plano es de Resolve (colocacion._cerrar_menu_de_resolve)."""
    try:
        import colocacion
        for _ in range(veces):
            colocacion._cerrar_menu_de_resolve()
            time.sleep(0.08)
    except Exception:
        pass


def organizador(pids, nombre=''):
    """Pasa el «Organizador de proyectos» de Resolve: «Crear proyecto» (btnAddProject) → nombre → «Crear» (pushButton_Create). Ids fijos, no
    dependen del idioma."""
    try:
        if not pids:
            return 'NO_RESOLVE'
        m, u = _api()

        def ventanas():
            pm = dlg = None
            for v in _ventanas(u, pids):
                cn = str(v.CurrentClassName or '')
                if 'NewProjectOptionsDlg' in cn:
                    dlg = v
                elif 'UiProjectManagerDialog' in cn:
                    pm = v
            return pm, dlg
        pm, dlg = ventanas()
        if dlg is None:
            if pm is None:
                return 'SIN_ORGANIZADOR'
            b = _buscar(u, pm, _BOTON, 'projActionBottomFrame.btnAddProject')
            if b is None:
                return 'SIN_BOTON'
            _patron(b, _INVOKE, m.IUIAutomationInvokePattern).Invoke()
            for _ in range(32):
                time.sleep(0.25)
                pm, dlg = ventanas()
                if dlg is not None:
                    break
        if dlg is None:
            return 'SIN_DIALOGO'
        ed = _buscar(u, dlg, _EDICION, 'lineEdit_ProjectName')
        puesto = ''
        if ed is not None:
            vp = _patron(ed, _VALOR, m.IUIAutomationValuePattern)
            if nombre:
                try:
                    vp.SetValue(str(nombre))
                except Exception:
                    pass
            puesto = str(vp.CurrentValue or '')
        ok = _buscar(u, dlg, _BOTON, 'pushButton_Create')
        if ok is None:
            return 'SIN_CREAR'
        _patron(ok, _INVOKE, m.IUIAutomationInvokePattern).Invoke()
        return 'CREADO|' + puesto
    except Exception as e:
        return 'ERROR ' + str(e)[:160]


def expandir(pids):
    """Deja ACTIVADA la casilla «Expandir vista» (btnEditExpandViewer) de la página Edit."""
    try:
        if not pids:
            return 'NO_RESOLVE'
        m, u = _api()
        main = _principal(u, pids)
        if main is None:
            return 'SIN_VENTANA'
        b = _buscar(u, main, _CASILLA, 'btnEditExpandViewer')
        if b is None:
            return 'SIN_BOTON'
        t = _patron(b, _TOGGLE, m.IUIAutomationTogglePattern)
        if int(t.CurrentToggleState) == 1:
            return 'YA_EXPANDIDA'
        t.Toggle()
        time.sleep(0.5)
        return 'EXPANDIDA' if int(t.CurrentToggleState) == 1 else 'NO_CAMBIO'
    except Exception as e:
        return 'ERROR ' + str(e)[:160]


def _menu_de_barra(m, u, main, nombres, vecino, despues):
    """El menú de la barra por su nombre; si no (otro idioma), el que va justo antes (despues=False) o después (despues=True) de `vecino`."""
    e = _por_nombre(u, main, nombres)
    if e is not None:
        return e
    ant = None
    for b in _todos(main, _DESCENDIENTES, u.CreatePropertyCondition(_TIPO, _MENU_ITEM)):
        nombre = str(b.CurrentName or '')
        if despues and ant is not None and str(ant.CurrentName or '') == vecino:
            return b
        if not despues and nombre == vecino:
            return ant
        ant = b
    return None


def _menu_reproducir(pids, menus, items, nombre_hilo):
    """Un elemento del menú «Reproducir» (el que va antes de «Fusion» si no se encuentra por nombre). → 'PULSADO' o el código del fallo."""
    try:
        m, u = _api()
        main = _principal(u, pids)
        if main is None:
            return 'SIN_VENTANA'
        menu = _menu_de_barra(m, u, main, [x for x in str(menus).split('|') if x], 'Fusion', despues=False)
        if menu is None:
            return 'SIN_MENU'
        _desplegar(m, menu)
        e = _por_nombre(u, menu, [x for x in str(items).split('|') if x])
        if e is None:
            _escape()
            return 'SIN_ITEM'
        _pulsar_aparte(e, nombre_hilo)
        return 'PULSADO'
    except Exception as e:
        return 'ERROR ' + str(e)[:160]


def reproducir(pids, menus, items):
    """«Reproducir > Reproducir hacia adelante» en el menú de Resolve (sin foco ni teclas)."""
    r = _menu_reproducir(pids, menus, items, 'uia-reproducir')
    return 'REPRODUCIENDO' if r == 'PULSADO' else r


def detener(pids, menus, items):
    """v5.5.7: «Reproducir > Detener». La reproducción lanzada desde el menú deja a Resolve sin contestar a los scripts mientras dura (medido: el MCP
    no contestaba 45 s justo después de cada GO); antes de volver a hablar con Resolve se detiene."""
    r = _menu_reproducir(pids, menus, items, 'uia-detener')
    return 'DETENIDO' if r == 'PULSADO' else r


def lanzar_script(pids, script, menus, subs):
    """Área de trabajo > Scripts > `script` en el menú de Resolve. El submenú se busca por nombre y, si no, se prueban todos hasta ver el script."""
    try:
        m, u = _api()
        main = _principal(u, pids)
        if main is None:
            return 'SIN_VENTANA'
        menu = _menu_de_barra(m, u, main, [x for x in str(menus).split('|') if x], 'Fairlight', despues=True)
        if menu is None:
            return 'SIN_MENU'
        _desplegar(m, menu)
        time.sleep(0.4)
        raiz = u.GetRootElement()
        cond = u.CreatePropertyCondition(_NOMBRE, str(script))
        e = _primero(raiz, _DESCENDIENTES, cond)
        if e is None:
            subs_menu = _todos(menu, _DESCENDIENTES, u.CreatePropertyCondition(_TIPO, _MENU_ITEM))
            primeros = [x for x in str(subs).split('|') if x]
            nombrados = [s for s in subs_menu if str(s.CurrentName or '') in primeros]
            for sm in (nombrados or subs_menu):
                try:
                    _patron(sm, _EXPANDIR, m.IUIAutomationExpandCollapsePattern).Expand()
                except Exception:
                    continue
                for _ in range(5):                                         # el submenú tarda en rellenarse (hasta ~1,5 s)
                    time.sleep(0.3)
                    e = _primero(raiz, _DESCENDIENTES, cond)
                    if e is not None:
                        break
                if e is not None:
                    break
        if e is None:
            _escape(3)
            return 'SIN_SCRIPT'
        _pulsar_aparte(e, 'uia-script')
        return 'LANZANDO'
    except Exception as e:
        return 'ERROR ' + str(e)[:160]
