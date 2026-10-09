# CineCaptions · By Cinema Productions
# 1_codigo/cola_trabajos.py — cola de trabajos de FONDO: máximo 2 a la vez y se apartan mientras GO trabaja.
"""
cola_trabajos.py  (v5.4.8)
--------------------------
Al abrir el programa arrancan varios trabajos de fondo (emojis, ondas de sonido, packs, limpieza de cachés, vistas reales…). Hasta ahora cada uno era su propio hilo y
todos competían entre sí y con GO. Prioridades:

    ALTA   GO y lo que el usuario acaba de pedir: arrancan al instante (no pasan por aquí).
    BAJA   lo de fondo: `lanzar_bajo(fn)`; como mucho `MAXIMO_BAJOS` a la vez y NINGUNO empieza mientras GO esté trabajando (los que ya corrían terminan).

`registrar_alta(f)` le dice cuándo hay trabajo de prioridad alta (f() → True, p. ej. `lambda: app._go_corriendo`).
"""
import threading
import time

MAXIMO_BAJOS = 2
ESPERA_MAX_S = 900                 # un trabajo de fondo que no pudo empezar en 15 min se descarta (no se acumulan para siempre)
_SEMAFORO = threading.BoundedSemaphore(MAXIMO_BAJOS)
_ALTA = {'f': None}
_ESTADO = {'esperando': 0, 'corriendo': 0, 'hechos': 0, 'descartados': 0}
_LOCK = threading.Lock()


def registrar_alta(funcion):
    _ALTA['f'] = funcion


def hay_alta():
    f = _ALTA['f']
    try:
        return bool(f()) if f else False
    except Exception:
        return False


def lanzar_bajo(funcion, nombre='fondo'):
    """Corre `funcion()` en un hilo de baja prioridad. Devuelve el hilo."""
    def correr():
        with _LOCK:
            _ESTADO['esperando'] += 1
        inicio = time.time()
        try:
            while True:
                if time.time() - inicio > ESPERA_MAX_S:
                    with _LOCK:
                        _ESTADO['descartados'] += 1
                    return
                if hay_alta():
                    time.sleep(1.0)
                    continue
                if _SEMAFORO.acquire(timeout=1.0):
                    break
        finally:
            with _LOCK:
                _ESTADO['esperando'] -= 1
        try:
            with _LOCK:
                _ESTADO['corriendo'] += 1
            try:
                import qt_kit
                qt_kit.prioridad_hilo(-1)
            except Exception:
                pass
            funcion()
        except Exception:
            pass
        finally:
            with _LOCK:
                _ESTADO['corriendo'] -= 1
                _ESTADO['hechos'] += 1
            _SEMAFORO.release()
    h = threading.Thread(target=correr, daemon=True, name=f'fondo-{nombre}')
    h.start()
    return h


def estado():
    with _LOCK:
        return dict(_ESTADO)
