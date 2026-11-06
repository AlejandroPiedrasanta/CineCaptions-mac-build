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
DETALLE_MAX = 11000         # caracteres del informe (errores.php guarda 12 000)

_CANDADO = threading.Lock()
_DESPERTAR = threading.Event()
_ESTADO = {'iniciado': False, 'enviados': 0, 'pausa_hasta': 0.0, 'ultimo_envio': {}, 'hilo': None}
_COLA = []                  # Entradas del Registro recién llegadas (las procesa el hilo)
_PENDIENTES = {}            # firma -> dict listo para mandar (también en ARCHIVO)
_CONTADAS = {}              # id(Entrada) -> (Entrada, veces ya contadas)


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
        _ESTADO['iniciado'] = True
        try:
            from PySide6.QtCore import Qt
            registro.registro().nueva.connect(_al_anotar, Qt.DirectConnection)
        except Exception:
            registro.registro().nueva.connect(_al_anotar)
        hilo = threading.Thread(target=_bucle, daemon=True, name='telemetria-errores')
        _ESTADO['hilo'] = hilo
        hilo.start()
        return True
    except Exception:
        return False


def _al_anotar(e):
    """Lo llama el Registro (desde cualquier hilo, también el de la interfaz): solo memoria, nada de disco ni red."""
    try:
        if getattr(e, 'nivel', '') != 'error':
            return
        with _CANDADO:
            if e not in _COLA:
                _COLA.append(e)
        _DESPERTAR.set()
    except Exception:
        pass


# ---------------------------------------------------------------------------------------------------------------------------------------
# el hilo
# ---------------------------------------------------------------------------------------------------------------------------------------
def _bucle():
    _cargar()
    if _PENDIENTES:
        _DESPERTAR.set()                       # lo que quedó de una sesión anterior (sin red, sin licencia)
    while True:
        _DESPERTAR.wait(timeout=600)           # cada 10 min se reintenta lo pendiente aunque no haya errores nuevos
        _DESPERTAR.clear()
        try:
            if _COLA:
                time.sleep(ESPERA_LOTE_S)
            _procesar_cola()
            _enviar()
        except Exception:
            pass


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


def _armar(e, f):
    """El dict que se manda: el informe de «Copiar este error» sin la carpeta del usuario."""
    titulo = ''
    try:
        import registro_ayuda
        titulo = registro_ayuda.explicar(e).titulo
    except Exception:
        pass
    try:
        detalle = registro.informe_de_error(e)
    except Exception:
        detalle = registro._sin_usuario(e.detalle or '')
    if len(detalle) > DETALLE_MAX:
        detalle = detalle[:DETALLE_MAX] + '\n…'
    return {'firma': f, 'nivel': 'error', 'titulo': str(titulo)[:190], 'mensaje': registro._sin_usuario(e.mensaje)[:600],
            'origen': registro._sin_usuario(e.origen or '')[:120], 'detalle': detalle, 'veces': max(1, int(getattr(e, 'veces', 1))),
            'cuando': time.time()}


def _recortar():
    ahora = time.time()
    for f in [f for f, d in _PENDIENTES.items() if ahora - float(d.get('cuando', 0)) > CADUCA_S]:
        _PENDIENTES.pop(f, None)
    if len(_PENDIENTES) > PENDIENTES_MAX:
        for f, _d in sorted(_PENDIENTES.items(), key=lambda kv: kv[1].get('cuando', 0))[:len(_PENDIENTES) - PENDIENTES_MAX]:
            _PENDIENTES.pop(f, None)


def _cargar():
    try:
        import archivos_seguros
        datos = archivos_seguros.leer_json(ARCHIVO, defecto={}) or {}
        for f, d in (datos.get('pendientes') or {}).items():
            if isinstance(d, dict) and re.fullmatch(r'[0-9a-f]{40}', str(f)) and d.get('mensaje'):
                d['veces'] = max(1, int(d.get('veces') or 1))
                _PENDIENTES[f] = d
        _recortar()
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
    codigo, espera = _post({'clave': datos['clave'], 'equipo': licencia.id_equipo(), 'version': licencia._version(),
                            'so': licencia._sistema(), 'errores': json.dumps(campos, ensure_ascii=False)})
    if codigo == 200 or codigo in (400, 404, 413):
        # 200 = guardados; 400/404/413 = el servidor no los quiere (datos raros, equipo no activado): reintentar no sirve
        ahora = time.time()
        for d in lote:
            _PENDIENTES.pop(d['firma'], None)
            _ESTADO['ultimo_envio'][d['firma']] = ahora
        _ESTADO['enviados'] += 1
        _guardar()
        if codigo == 200 and _PENDIENTES:
            _DESPERTAR.set()                    # quedan más (más de POR_PETICION o repetidos que ya pueden ir)
        return
    _ESTADO['pausa_hasta'] = time.time() + (espera or 300)      # sin red, 429, 503, 500: se reintenta más tarde


def _post(campos):
    """(código HTTP o 0 sin red, segundos de Retry-After o None)."""
    import licencia
    req = urllib.request.Request(URL, data=urllib.parse.urlencode(campos).encode('utf-8'), method='POST',
                                 headers={'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded',
                                          'User-Agent': 'CineCaptions/%s' % licencia._version()})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=licencia._ssl()) as r:
            r.read()
            return r.status, None
    except urllib.error.HTTPError as e:
        try:
            espera = int(e.headers.get('Retry-After') or 0) or None
        except (TypeError, ValueError):
            espera = None
        return e.code, espera
    except Exception:
        return 0, None


def esperar_envios(segundos=30.0):
    """Para pruebas: espera a que no quede nada por procesar (True) o a que pase el tiempo (False)."""
    fin = time.time() + segundos
    while time.time() < fin:
        if not _COLA and not _PENDIENTES:
            return True
        time.sleep(0.2)
    return False
