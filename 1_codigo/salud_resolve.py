# CineCaptions · By Cinema Productions
# 1_codigo/salud_resolve.py — ¿Resolve está sano? Diagnóstico único (ok / fantasma / colgado / caído) para Studio (MCP) y Free (Puente), Windows y Mac,
# y la reparación automática de GO: cerrar TODO lo de Resolve (por las buenas y, si no, a la fuerza), reabrirlo, volver al proyecto y repetir el paso.
"""
v5.56 (fallo real del usuario, 2026-10-30): Resolve Studio quedó «fantasma» (Resolve.exe vivo, SIN ventana, tras cerrarse a medias). Su MCP seguía
contestando a los scripts pero CreateProject devolvía None, así que cada GO esperaba 150 s × 3 intentos en «Resolve termina de arrancar…» y acababa en
«Resolve no creó el proyecto (no_creo)». El reintento decía «pero contesta: repito el paso» y nunca lo cerraba: `estado_resolve_ahora()` lo veía como
'caido', pero `_go_reparar_resolve` solo actuaba con 'colgado'. Solo al matarlo a mano GO abrió un Resolve nuevo y siguió.

Pedido del usuario: «arregla eso o pon un parámetro para cerrar todo lo de Resolve si se traba, que se auto repare» y «no puede tardar más de un minuto
sin responder».

Estados (`diagnostico_rapido` mira en milisegundos con lo que ya sabe el vigía; `diagnosticar` sigue mirando lo justo para estar seguro):
  · 'ok'        Resolve abierto y dando señales de vida (o no se puede saber: ante la duda, nunca se toca).
  · 'fantasma'  proceso vivo, de más de EDAD_MINIMA_S, SIN ninguna ventana visible durante FANTASMA_CONFIRMAR_S y con su registro quieto ese tiempo
                (uno que se está cerrando escribe en su registro). Se nota en segundos.
  · 'colgado'   UMBRAL_SIN_RESPONDER_S (60 s) seguidos sin señales de vida: su ventana «No responde» o no contesta a un ping corto (MCP), Y su registro sin
                moverse. Un render o una colocación larga NO cuentan: Resolve contesta o su registro avanza. Nunca se da por colgado antes.
  · 'caido'     no hay proceso de Resolve, o se cayó (volcado de error en su registro).

Reparar (`reparar`) solo si la preferencia `reparar_resolve_auto` (Ajustes > «Reparar Resolve solo si se traba», encendida por defecto) lo permite;
apagada: diagnóstico claro en el Registro y GO se detiene, sin cerrar nada. Cerrar (`cerrar_resolve_del_todo`) toca SOLO: los procesos de Resolve, sus
procesos hijos (scripting de ESE Resolve) y el ResolveMCP que lanzó CineCaptions. Nunca CineCaptions, sus antepasados o sus otros hijos, ni los ResolveMCP
de otros clientes (Claude, otros programas). Primero por las buenas (WM_CLOSE / SIGTERM) y, si en GRACIA_CIERRE_S no salió, a la fuerza.
Todo corre en hilos de trabajo, nunca en el de la ventana (esperas de hasta ~80 s).
"""
import os
import sys
import time
import threading

from i18n import tr

UMBRAL_SIN_RESPONDER_S = float(os.environ.get('CC_UMBRAL_SIN_RESPONDER_S') or os.environ.get('CC_UMBRAL_COLGADO_S') or 60.0)    # el usuario: «no puede tardar más de un minuto sin responder» (= resolve_bridge.UMBRAL_COLGADO_S)
FANTASMA_CONFIRMAR_S = float(os.environ.get('CC_FANTASMA_CONFIRMAR_S') or 8.0)        # seguidos sin ventana (y con el registro quieto) para llamarlo fantasma
EDAD_MINIMA_S = float(os.environ.get('CC_EDAD_MINIMA_RESOLVE_S') or 90.0)             # un Resolve más joven puede estar arrancando (aún sin ventana)
GRACIA_CIERRE_S = float(os.environ.get('CC_GRACIA_CIERRE_S') or 8.0)                  # cuánto se espera al cierre por las buenas antes de forzarlo
PAUSA_TRAS_CIERRE_S = float(os.environ.get('CC_PAUSA_TRAS_CIERRE_S') or 3.0)          # Resolve suelta su base de datos y sus archivos un instante después de morir
PING_S = 8.0                                                                          # tope de cada ping corto al MCP
PREF = 'reparar_resolve_auto'

_ULTIMO = {'texto': '', 't': 0.0}           # el último «está trabado pero no lo cierro» (preferencia apagada): GO lo usa como motivo para detenerse
_DIAG = {}                                  # el último diagnóstico «trabado» de diagnosticar (15 s): otro paso no vuelve a esperar 60 s por el mismo Resolve
_LOCK_REPARAR = threading.Lock()            # dos hilos de GO no reparan a la vez (el segundo espera y vuelve a mirar)


# ---------------------------------------------------------------------------
# preferencia
# ---------------------------------------------------------------------------

def reparar_permitido():
    """v5.69: SIEMPRE (el usuario pidió quitar «Reparar Resolve solo si se traba» de Ajustes y dejarlo encendido); `PREF` ya no se lee."""
    return True


def trabado_sin_permiso(desde=0.0):
    """El diagnóstico que se dejó en el Registro cuando Resolve estaba trabado y la preferencia NO dejó cerrarlo (después de `desde`), o ''."""
    return _ULTIMO['texto'] if _ULTIMO['texto'] and _ULTIMO['t'] >= float(desde or 0.0) else ''


# ---------------------------------------------------------------------------
# diagnóstico
# ---------------------------------------------------------------------------

def _rb():
    import resolve_bridge
    return resolve_bridge


def iniciar_vigia():
    try:
        _rb().iniciar_vigia()
    except Exception:
        pass


def _segundos(s):
    s = int(round(max(0.0, float(s or 0.0))))
    if s < 60:
        return tr('{n} s', n=s)
    return tr('{m} min {s} s', m=s // 60, s=s % 60)


def diagnostico_rapido(desde=None, sin_respuesta_desde=None, muestra_s=3.0):
    """Mirada inmediata (ms; nunca espera): {'estado', 'pids', 'hay_ventana', 'edad_s', 'sin_ventana_s', 'colgado_s', 'mudo_s', 'sin_respuesta_s', 'texto'}.
    Usa lo que el vigía ya sabe (cuánto lleva sin ventana o «No responde»), así que un fantasma viejo se reconoce al momento.
    `desde`: si Resolve escribió un volcado de error después, 'caido'. `sin_respuesta_desde`: primer ping sin respuesta (lo lleva `diagnosticar`)."""
    d = {'estado': 'ok', 'pids': [], 'hay_ventana': None, 'edad_s': 0.0, 'sin_ventana_s': 0.0, 'colgado_s': 0.0, 'mudo_s': 0.0,
         'sin_respuesta_s': 0.0, 'texto': ''}
    if not (sys.platform.startswith('win') or sys.platform == 'darwin'):
        return d
    try:
        b = _rb()
        pids = b._listar_pids_resolve()
        if pids is None:                                       # no se pudo mirar: ante la duda, sano
            return d
        if not pids:
            d.update(estado='caido', texto=texto_diagnostico({'estado': 'caido'}))
            return d
        d['pids'] = list(pids)
        if desde and b.resolve_se_cayo(desde):
            d.update(estado='caido', caida=True)
            d['texto'] = texto_diagnostico(d)
            return d
        b.iniciar_vigia()
        b._tomar_muestra(muestra_s)
        ahora = time.time()
        sv, hd = b._COLGADO.get('sin_ventana_desde'), b._COLGADO.get('desde')
        d['hay_ventana'] = bool(b._MIRADA.get('hay_ventana', True))
        d['sin_ventana_s'] = (ahora - sv) if (sv and not d['hay_ventana']) else 0.0
        d['colgado_s'] = (ahora - hd) if hd else 0.0
        d['sin_respuesta_s'] = (ahora - sin_respuesta_desde) if sin_respuesta_desde else 0.0
        if not d['hay_ventana']:
            d['edad_s'] = b._edad_proceso_resolve_s()          # (sin ventana: ¿es uno que aún arranca?)
        if d['sin_ventana_s'] >= FANTASMA_CONFIRMAR_S or max(d['colgado_s'], d['sin_respuesta_s']) >= UMBRAL_SIN_RESPONDER_S:
            d['mudo_s'] = b._registro_resolve_callado_s()      # (solo se mira cuando hace falta: son dos stat, pero se llama mucho)
            if d['sin_ventana_s'] >= FANTASMA_CONFIRMAR_S and d['edad_s'] >= EDAD_MINIMA_S and d['mudo_s'] >= FANTASMA_CONFIRMAR_S:
                d['estado'] = 'fantasma'
            elif min(max(d['colgado_s'], d['sin_respuesta_s']), d['mudo_s']) >= UMBRAL_SIN_RESPONDER_S:
                d['estado'] = 'colgado'
        d['texto'] = texto_diagnostico(d)
    except Exception:
        pass
    return d


def es_fantasma():
    return diagnostico_rapido()['estado'] == 'fantasma'


def texto_diagnostico(d, motivo=''):
    """El diagnóstico en lenguaje claro para el Registro."""
    est = (d or {}).get('estado')
    if est == 'fantasma':
        t = tr('Resolve está «fantasma»: su proceso sigue abierto pero sin ninguna ventana desde hace {s} y su registro no se mueve (se cerró a medias).',
               s=_segundos(max(d.get('sin_ventana_s') or 0.0, FANTASMA_CONFIRMAR_S)))
    elif est == 'colgado':
        t = tr('Resolve no responde: lleva {s} sin dar señales de vida (ventana «No responde» o sin contestar a CineCaptions) y su registro no se mueve.',
               s=_segundos(min(max(d.get('colgado_s') or 0.0, d.get('sin_respuesta_s') or 0.0), d.get('mudo_s') or 0.0) or UMBRAL_SIN_RESPONDER_S))
    elif est == 'caido':
        t = tr('Resolve se cayó (dejó un volcado de error en su registro).') if d.get('caida') else tr('Resolve no está abierto.')
    else:
        t = tr('Resolve responde.')
    if motivo:
        t += ' ' + tr('(Falló: {m})', m=str(motivo)[:160])
    return t


def mensaje_atascado(d):
    """El texto que devuelven los pasos de Resolve cuando ven a Resolve trabado: diagnóstico + marca que GO reconoce (resolve_bridge.es_resolve_atascado)."""
    b = _rb()
    marca = b.ERR_RESOLVE_FANTASMA if (d or {}).get('estado') == 'fantasma' else b.ERR_RESOLVE_COLGADO
    return f'{texto_diagnostico(d)} ({marca})'


def ping_mcp():
    """Ping corto a Resolve por el MCP (Studio): True = contestó, False = NO contestó (tiempo agotado), None = no se puede saber (sin MCP, trabajo en
    marcha, o contestó con un error: Resolve está vivo). Un ResolveMCP atascado tampoco contesta: tras un fallo se cierra y el siguiente ping arranca otro."""
    try:
        import resolve_mcp
        if resolve_mcp.trabajo_en_marcha() or resolve_mcp.ruta_exe() is None:
            return None
        ok, r, err = resolve_mcp.script('result = 1', timeout=int(PING_S))
        if ok:
            return True
        e = str(err or '').lower()
        if any(x in e for x in ('no contest', 'timed out', 'timeout', 'did not respond', 'no responde')):
            resolve_mcp.cerrar()
            return False
    except Exception:
        pass
    return None


def diagnosticar(ping=None, decir=None, desde=None, tope_s=None):
    """Mira Resolve y, si algo es sospechoso, lo sigue mirando lo justo para estar seguro (corre en hilos de trabajo):
      · sin ventana ahora → se confirma el fantasma en ~FANTASMA_CONFIRMAR_S (al momento si el vigía ya lo sabía);
      · ventana «No responde» o ping sin respuesta → se espera hasta UMBRAL_SIN_RESPONDER_S sin señales de vida (nunca menos); si vuelve a contestar o
        su registro avanza, 'ok';
      · todo bien → 'ok' en milisegundos (un ping si se pasa `ping`).
    Devuelve el dict de `diagnostico_rapido` con 'esperado_s' (lo que se esperó) y 'ocupado' (dio señales de vida pero no contestó del todo)."""
    iniciar_vigia()
    t0 = time.time()
    previo = _DIAG.get('d')
    if previo and time.time() - _DIAG.get('t', 0.0) < 15.0:
        # (otro paso acaba de dar a Resolve por trabado: el mismo Resolve no se vuelve a esperar otros 60 s)
        if set(previo.get('pids') or []) and set(previo.get('pids') or []) == set(_rb()._listar_pids_resolve() or []):
            return dict(previo)
    tope = (UMBRAL_SIN_RESPONDER_S + 20.0) if tope_s is None else float(tope_s)
    falla_desde = None
    dicho = 0.0
    sospecha = False
    while True:
        d = diagnostico_rapido(desde=desde, sin_respuesta_desde=falla_desde, muestra_s=1.0)
        d['esperado_s'] = time.time() - t0
        if d['estado'] in ('fantasma', 'colgado'):
            _DIAG.update(d=dict(d), t=time.time())
        if d['estado'] != 'ok' or not d['pids']:
            return d
        sin_ventana = d['hay_ventana'] is False
        colgada = d['colgado_s'] > 0
        r = None
        if ping is not None and not sin_ventana and not colgada:
            t_ping = time.time()
            try:
                r = ping()
            except Exception:
                r = None
            if r is True:
                falla_desde = None
            elif r is False and falla_desde is None:
                falla_desde = t_ping
            d = diagnostico_rapido(desde=desde, sin_respuesta_desde=falla_desde, muestra_s=1.0)
            d['esperado_s'] = time.time() - t0
            if d['estado'] in ('fantasma', 'colgado'):
                _DIAG.update(d=dict(d), t=time.time())
            if d['estado'] != 'ok' or not d['pids']:
                return d
            sin_ventana = d['hay_ventana'] is False
            colgada = d['colgado_s'] > 0
        if not sin_ventana and not colgada and r is not False:
            if sospecha:
                _registro('info', tr('Resolve tardó {s} en dar señales de vida, pero contestó: sigo.', s=_segundos(d['esperado_s'])))
            return d
        if sin_ventana and d['edad_s'] and d['edad_s'] < EDAD_MINIMA_S:
            return d                                           # recién abierto: aún no enseña su ventana
        sospecha = True
        if time.time() - t0 >= tope:
            d['ocupado'] = True                                # (su registro se movía o contestó a ratos: ocupado, no trabado)
            _registro('aviso', tr('Resolve lleva {s} ocupado (su registro se mueve) pero no está trabado: no lo toco y sigo.', s=_segundos(d['esperado_s'])))
            return d
        if decir and time.time() - dicho >= 5.0:
            dicho = time.time()
            try:
                if sin_ventana:
                    decir(tr('Resolve sigue abierto sin ventana: compruebo si se quedó a medias…'))
                else:
                    sr = max(d['colgado_s'], (time.time() - falla_desde) if falla_desde else 0.0)
                    decir(tr('Resolve no responde desde hace {s}: espero hasta {u} antes de repararlo…', s=_segundos(sr), u=_segundos(UMBRAL_SIN_RESPONDER_S)))
            except Exception:
                pass
        time.sleep(1.0)


# ---------------------------------------------------------------------------
# procesos (Windows: ToolHelp32 + ctypes; Mac: ps / señales). Sin PowerShell (los antivirus lo bloquean).
# ---------------------------------------------------------------------------

_K32 = {}


def _k32():
    k = _K32.get('k')
    if k is None:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL('kernel32', use_last_error=True)          # (instancia propia: los argtypes no chocan con los de otros hilos)
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.TerminateProcess.restype = wintypes.BOOL
        k.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k.WaitForSingleObject.restype = wintypes.DWORD
        k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        _K32['k'] = k
    return k


def _tabla_procesos():
    """{pid: (ppid, nombre en minúsculas)} de todo el sistema; {} si no se pudo."""
    tabla = {}
    try:
        if sys.platform.startswith('win'):
            import ctypes
            from ctypes import wintypes
            k32, _Proc = _rb()._toolhelp()
            snap = k32.CreateToolhelp32Snapshot(0x2, 0)
            if not snap or snap == wintypes.HANDLE(-1).value:
                return {}
            try:
                e = _Proc()
                e.dwSize = ctypes.sizeof(_Proc)
                ok = k32.Process32FirstW(snap, ctypes.byref(e))
                while ok:
                    tabla[int(e.th32ProcessID)] = (int(e.th32ParentProcessID), e.szExeFile.lower())
                    ok = k32.Process32NextW(snap, ctypes.byref(e))
            finally:
                k32.CloseHandle(snap)
        elif sys.platform == 'darwin':
            import subprocess
            r = subprocess.run(['/bin/ps', '-A', '-o', 'pid=,ppid=,comm='], capture_output=True, text=True, errors='replace', timeout=8)
            for linea in r.stdout.splitlines():
                partes = linea.strip().split(None, 2)
                if len(partes) == 3 and partes[0].isdigit() and partes[1].isdigit():
                    tabla[int(partes[0])] = (int(partes[1]), os.path.basename(partes[2]).lower())
    except Exception:
        return {}
    return tabla


def _descendientes(pid, tabla):
    """Todos los descendientes de `pid`. Windows: colocacion._procesos_hijos (solo los nacidos después de su padre: Windows reutiliza los pid)."""
    if sys.platform.startswith('win'):
        try:
            import colocacion
            return set(colocacion._procesos_hijos(int(pid)))
        except Exception:
            return set()
    hijos, pila = set(), [int(pid)]
    while pila:
        p = pila.pop()
        for h, (pp, _n) in tabla.items():
            if pp == p and h not in hijos and h != int(pid):
                hijos.add(h)
                pila.append(h)
    return hijos


def _antepasados(pid, tabla):
    out, p = set(), int(pid)
    for _ in range(64):
        pp = (tabla.get(p) or (None,))[0]
        if not pp or pp in out or pp == p:
            break
        out.add(pp)
        p = pp
    return out


def _abrir(pid):
    """Handle al proceso (Windows; TERMINATE | SYNCHRONIZE | QUERY_LIMITED): matar y esperar por handle garantiza que es ESE proceso aunque Windows
    reutilice su pid. None si no se pudo (p. ej. Resolve abierto como administrador)."""
    try:
        h = _k32().OpenProcess(0x0001 | 0x00100000 | 0x1000, False, int(pid))
        return h or None
    except Exception:
        return None


def _vivo(pid, h=None):
    try:
        if sys.platform.startswith('win'):
            if h:
                return _k32().WaitForSingleObject(h, 0) == 0x102    # WAIT_TIMEOUT = sigue vivo
            return int(pid) in (_rb()._listar_pids_resolve() or []) or int(pid) in _tabla_procesos()
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _matar(pid, h=None):
    try:
        if sys.platform.startswith('win'):
            if h and _k32().TerminateProcess(h, 1):
                return True
            import subprocess
            r = subprocess.run(['taskkill', '/F', '/PID', str(int(pid))], capture_output=True, creationflags=0x08000000, timeout=20)     # CREATE_NO_WINDOW
            return r.returncode == 0
        import signal
        os.kill(int(pid), signal.SIGKILL)
        return True
    except Exception:
        return False


def _pedir_cierre(pids):
    """Cierre por las buenas: WM_CLOSE a las ventanas de nivel superior de esos procesos (Windows) o SIGTERM (Mac). Devuelve a cuántos se pidió."""
    n = 0
    try:
        if sys.platform.startswith('win'):
            import ctypes
            from ctypes import wintypes
            u32 = ctypes.WinDLL('user32')
            u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            u32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            objetivo = set(int(p) for p in pids)
            cuenta = [0]

            def cb(hwnd, _lp):
                pid = wintypes.DWORD()
                u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in objetivo and u32.PostMessageW(hwnd, 0x0010, 0, 0):      # WM_CLOSE
                    cuenta[0] += 1
                return True
            u32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
            n = cuenta[0]
        else:
            import signal
            for p in pids:
                try:
                    os.kill(int(p), signal.SIGTERM)
                    n += 1
                except Exception:
                    pass
    except Exception:
        pass
    return n


def _esperar_muerte(vivos, tope_s):
    """Espera hasta `tope_s` a que mueran; devuelve los que siguen vivos {pid: handle}."""
    t0 = time.time()
    while True:
        vivos = {p: h for p, h in vivos.items() if _vivo(p, h)}
        if not vivos or time.time() - t0 >= tope_s:
            return vivos
        time.sleep(0.25)


def _nombres_mcp():
    return ('resolvemcp.exe', 'resolvepython.exe') if sys.platform.startswith('win') else ('resolvemcp', 'resolvepython')


def cerrar_resolve_del_todo(decir=None, gracia_s=None, espera_s=30.0):
    """Cierra TODO lo de Resolve: sus procesos, los procesos hijos de ESE Resolve (scripting) y el ResolveMCP que lanzó CineCaptions. Primero por las
    buenas y, si en `gracia_s` no salió, a la fuerza (gracia 0 = directamente a la fuerza, como Cancelar). Nunca toca CineCaptions, sus antepasados ni sus
    otros hijos, ni los ResolveMCP de otros clientes. Devuelve {'ok', 'por_las_buenas', 'forzados', 'hijos', 'segundos'}. Nunca lanza; NO desde la ventana."""
    gracia_s = GRACIA_CIERRE_S if gracia_s is None else float(gracia_s)
    t0 = time.time()
    out = {'ok': True, 'por_las_buenas': False, 'forzados': 0, 'hijos': 0, 'segundos': 0.0}
    try:
        try:
            import resolve_mcp
            resolve_mcp.cerrar()                         # el ResolveMCP de CineCaptions (cierra su stdin: sale solo con su ResolvePython; si no, kill a los 2 s)
        except Exception:
            pass
        tabla = _tabla_procesos()
        yo = os.getpid()
        mios = _descendientes(yo, tabla)
        huerfanos_mcp = {p for p in mios if (tabla.get(p) or (0, ''))[1] in _nombres_mcp()}       # ResolveMCP/ResolvePython que lanzó la app y quedaron sueltos
        pids = [p for p in (_rb()._listar_pids_resolve() or []) if p != yo]        # (Resolve suele ser hijo o nieto de CineCaptions: lo abrió ella o su ResolveMCP)
        if not pids and not huerfanos_mcp:
            return out
        if pids and decir:
            try:
                decir(tr('Cerrando Resolve…'))
            except Exception:
                pass
        principales = {p: (_abrir(p) if sys.platform.startswith('win') else None) for p in pids}
        hijos = set()
        for p in pids:
            hijos |= _descendientes(p, tabla)
        hijos -= set(pids)
        if yo in hijos:
            # CineCaptions se abrió DESDE Resolve (su menú de scripts): ni ella, ni sus otros procesos (motor de voz…), ni quien la lanzó se tocan
            hijos -= {yo} | mios | _antepasados(yo, tabla)
        hijos |= huerfanos_mcp
        hijos_h = {h: (_abrir(h) if sys.platform.startswith('win') else None) for h in hijos}
        vivos = dict(principales)
        if vivos and gracia_s > 0:
            pedidos = _pedir_cierre(list(vivos))
            gracia_s = gracia_s if pedidos else min(gracia_s, 3.0)           # (sin ninguna ventana a la que pedírselo, solo un momento por si sale solo)
            vivos = _esperar_muerte(vivos, gracia_s)
            out['por_las_buenas'] = not vivos
        for p, h in vivos.items():
            if _matar(p, h):
                out['forzados'] += 1
        for p, h in hijos_h.items():
            if _vivo(p, h) and _matar(p, h):
                out['hijos'] += 1
        restan = _esperar_muerte({**principales, **hijos_h}, espera_s)
        for h in list(principales.values()) + list(hijos_h.values()):
            if h:
                try:
                    _k32().CloseHandle(h)
                except Exception:
                    pass
        out['ok'] = not any(p in restan for p in principales)
        if out['ok'] and pids:
            time.sleep(PAUSA_TRAS_CIERRE_S)
        out['segundos'] = time.time() - t0
        if pids:
            if not out['ok']:
                _registro('aviso', tr('No pude cerrar Resolve ({n} proceso(s) siguen vivos tras {s}).', n=len([p for p in principales if p in restan]),
                                      s=_segundos(out['segundos'])))
            elif out['por_las_buenas']:
                _registro('info', tr('Resolve se cerró por las buenas en {s} ({h} proceso(s) suyos más).', s=_segundos(out['segundos']), h=out['hijos']))
            elif gracia_s <= 0:
                _registro('info', tr('Cerré Resolve a la fuerza en {s} ({h} proceso(s) suyos más).', s=_segundos(out['segundos']), h=out['hijos']))
            else:
                _registro('info', tr('Resolve no se cerró por las buenas en {g}: lo cerré a la fuerza en {s} ({h} proceso(s) suyos más).',
                                     g=_segundos(gracia_s), s=_segundos(out['segundos']), h=out['hijos']))
    except Exception:
        out['ok'] = not (_rb()._listar_pids_resolve() or [])
        try:
            import registro
            registro.excepcion(origen='Resolve · cerrar del todo')
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# reparar
# ---------------------------------------------------------------------------

def _registro(nivel, texto):
    try:
        import registro
        getattr(registro, nivel)(texto, 'GO · Resolve')
    except Exception:
        pass


def _como_cerrarlo_a_mano():
    if sys.platform == 'darwin':
        return tr('ciérralo tú (menú Apple > Forzar salida > DaVinci Resolve)')
    return tr('ciérralo tú (Administrador de tareas > DaVinci Resolve > Finalizar tarea)')


def _limpiar_puente_muerto():
    """Lo que dejó el Puente de un Resolve que ya no existe (latido, trabajos y sus sidecars)."""
    b = _rb()
    for f in (getattr(b, 'ARCHIVO_LATIDO', None), getattr(b, 'JOB_TOMADO', None), getattr(b, 'JOB_PENDIENTE', None)):
        if f is None:
            continue
        for g in (f, f.with_name(f.name + '.lua'), f.with_name(f.name + '.free.lua')):
            try:
                g.unlink()
            except Exception:
                pass


def reparar(diag=None, decir=None, camino='mcp', volver_a=None, motivo='', relanzar=True):
    """Resolve está trabado (fantasma o colgado según `diag`): lo cierra del todo, espera a que muera, lo vuelve a abrir (camino 'mcp' = Studio por su
    MCP; 'puente' = Free, con el Puente) y, si se pide, abre el proyecto `volver_a` (Studio). Devuelve {'ok', 'parar', 'texto', 'segundos'}:
    parar=True = la preferencia está apagada o no se pudo cerrar: GO se detiene con `texto` (ya anotado en el Registro)."""
    t0 = time.time()
    with _LOCK_REPARAR:
        d = diag or diagnostico_rapido()
        hay = bool(_rb()._listar_pids_resolve() or [])
        texto = texto_diagnostico(d, motivo) if d.get('estado') in ('fantasma', 'colgado') else (str(motivo) or texto_diagnostico(d))
        if hay and not reparar_permitido():
            aviso = tr('{d} No lo cierro porque «Reparar Resolve solo si se traba» está apagado en Ajustes: {como} y pulsa GO otra vez.',
                       d=texto, como=_como_cerrarlo_a_mano())
            clave = (d.get('estado'), tuple(sorted(d.get('pids') or [])))
            if not (_ULTIMO.get('clave') == clave and time.time() - _ULTIMO['t'] < 60.0):    # (varios pasos del mismo GO lo ven: se anota una vez)
                _registro('aviso', aviso)
            _ULTIMO.update(texto=aviso, t=time.time(), clave=clave)
            return {'ok': False, 'parar': True, 'texto': aviso, 'segundos': time.time() - t0}
        if hay:
            espera = d.get('esperado_s')
            if d.get('estado') == 'fantasma':
                _registro('aviso', tr('{d} Lo noté en {e}: lo cierro del todo y lo vuelvo a abrir.', d=texto, e=_segundos(espera or 0.0)))
            else:
                _registro('aviso', tr('{d} Esperé {e} a que diera señales de vida: lo cierro del todo y lo vuelvo a abrir.', d=texto,
                                      e=_segundos(espera if espera is not None else UMBRAL_SIN_RESPONDER_S)))
            if decir:
                try:
                    decir(tr('Resolve se trabó: lo cierro y lo vuelvo a abrir…'))
                except Exception:
                    pass
            c = cerrar_resolve_del_todo(decir)
            _DIAG.clear()
            if not c['ok']:
                aviso = tr('No pude cerrar Resolve: {como} y pulsa GO otra vez.', como=_como_cerrarlo_a_mano())
                _registro('aviso', aviso)
                return {'ok': False, 'parar': True, 'texto': aviso, 'segundos': time.time() - t0}
        if camino == 'puente':
            _limpiar_puente_muerto()
        if not relanzar:
            return {'ok': True, 'parar': False, 'texto': texto, 'segundos': time.time() - t0}
        if decir:
            try:
                decir(tr('Reabriendo Resolve…'))
            except Exception:
                pass
        t1 = time.time()
        ok = False
        try:
            if camino == 'puente':
                ok = bool(_rb().lanzar_puente_auto(forzar=True))
            else:
                import resolve_mcp
                ok = bool(resolve_mcp.arrancar_resolve(decir, espera_s=240)[0])
                if ok and volver_a:
                    if decir:
                        try:
                            decir(tr('Vuelvo a abrir tu proyecto «{p}»…', p=volver_a))
                        except Exception:
                            pass
                    abierto = resolve_mcp.abrir_proyecto(volver_a)
                    _registro('info' if abierto else 'aviso', tr('Proyecto «{p}» abierto otra vez.', p=volver_a) if abierto else
                              tr('No pude volver a abrir tu proyecto «{p}»: GO abre el más reciente.', p=volver_a))
        except Exception:
            try:
                import registro
                registro.excepcion(origen='Resolve · reabrir tras reparar')
            except Exception:
                pass
        if ok:
            _registro('info', tr('Resolve reabierto en {s}: repito el paso (reparación completa en {t}).', s=_segundos(time.time() - t1), t=_segundos(time.time() - t0)))
        else:
            _registro('aviso', tr('Cerré Resolve pero no terminó de abrirse otra vez ({s}): GO lo intenta en el paso siguiente.', s=_segundos(time.time() - t1)))
        return {'ok': ok, 'parar': False, 'texto': texto, 'segundos': time.time() - t0}


def revisar_y_reparar(ping=None, decir=None, camino='mcp', volver_a=None, motivo='', desde=None, relanzar=True):
    """Lo que GO llama antes de un paso de Resolve y cuando uno falla o tarda: `diagnosticar` y, si está fantasma o colgado, `reparar`.
    Devuelve {'estado', 'reparado', 'parar', 'texto', 'diag'}: reparado=True → repetir el paso; parar=True → GO se detiene con `texto`."""
    d = diagnosticar(ping=ping, decir=decir, desde=desde)
    out = {'estado': d['estado'], 'reparado': False, 'parar': False, 'texto': d.get('texto') or '', 'diag': d}
    if d['estado'] in ('fantasma', 'colgado') or (d['estado'] == 'caido' and d.get('caida') and d.get('pids')):
        r = reparar(d, decir=decir, camino=camino, volver_a=volver_a, motivo=motivo, relanzar=relanzar)
        out.update(reparado=bool(r.get('ok')), parar=bool(r.get('parar')), texto=r.get('texto') or out['texto'])
    return out
