# CineCaptions · By Cinema Productions
# 1_codigo/mantenimiento.py — límite y limpieza automática de las cachés del programa (secuencias, vistas, voz, emojis…).
"""
mantenimiento.py  (v5.4.8)
--------------------------
Las cachés (`~/DaVinciSubtitles/…`) crecen con el uso: secuencias de efectos y emojis, vistas reales de los packs, transcripciones. Cada una tiene un TOPE en MB;
al pasarse se borran las entradas menos usadas (la más vieja primero, de a una carpeta o archivo entero) hasta volver al tope. Todo se rehace solo cuando hace falta.
Nunca se toca algo modificado en los últimos 10 minutos (puede estar en uso por un GO).

    limpiar_todo()      -> (mb_liberados, entradas_borradas)     (arranque, 45 s después de abrir, en un hilo)
    resumen()           -> ([(nombre, mb, tope_mb)], total_mb)   (Ajustes)
"""
import shutil
import time
from pathlib import Path

RAIZ = Path.home() / 'DaVinciSubtitles'
# nombre visible: (carpeta, tope en MB, días máximos sin usar o None)
CACHES = {
    'Efectos (iconos animados)': ('efectos_cache', 700, None),
    'Emojis animados': ('emojis_secuencia', 600, None),
    'Emojis': ('emojis_animados', 300, None),
    'Emojis (imágenes)': ('emojis_cache', 200, None),
    'Vistas reales de los packs': ('plantillas_cache', 500, None),
    'Voz (transcripciones)': ('cache_voz', 200, 90),
    'B-roll descargado': ('broll_cache', 400, 45),
    'Sugerencias': ('sugerencias_cache', 50, None),
    'Sonidos usados': ('sfx_usados', 200, None),
    'Pruebas y renders temporales': ('banco', 500, 7),
}
RECIENTE_S = 600


def _tam_entrada(p):
    try:
        if p.is_file():
            return p.stat().st_size
        return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
    except OSError:
        return 0


def _mtime_entrada(p):
    """La fecha más reciente de una entrada (si es una carpeta, la de su archivo más nuevo)."""
    try:
        if p.is_file():
            return p.stat().st_mtime
        return max([p.stat().st_mtime] + [f.stat().st_mtime for f in p.rglob('*') if f.is_file()])
    except (OSError, ValueError):
        return time.time()


def tamano_mb(carpeta):
    try:
        return sum(_tam_entrada(e) for e in Path(carpeta).iterdir()) / 1e6
    except OSError:
        return 0.0


def limpiar_carpeta(carpeta, tope_mb, max_dias=None):
    """Borra entradas de primer nivel (archivo o carpeta) de `carpeta`: primero las que llevan más de `max_dias` días sin usarse y luego, si aún pasa de `tope_mb`, las más viejas.
    Devuelve (mb_liberados, entradas_borradas)."""
    carpeta = Path(carpeta)
    liberado, borradas = 0.0, 0
    try:
        entradas = [(e, _mtime_entrada(e), _tam_entrada(e)) for e in carpeta.iterdir()]
    except OSError:
        return 0.0, 0
    ahora = time.time()
    entradas.sort(key=lambda x: x[1])
    total = sum(x[2] for x in entradas) / 1e6
    for e, m, t in list(entradas):
        if ahora - m < RECIENTE_S:
            continue
        pasa_de_tope = total > tope_mb
        vieja = max_dias is not None and (ahora - m) > max_dias * 86400
        if not (pasa_de_tope or vieja):
            if not max_dias:
                break
            continue
        try:
            shutil.rmtree(e, ignore_errors=True) if e.is_dir() else e.unlink()
            total -= t / 1e6
            liberado += t / 1e6
            borradas += 1
        except OSError:
            pass
    return liberado, borradas


def limpiar_todo():
    """Aplica el tope de cada caché. Devuelve (mb_liberados, entradas_borradas)."""
    mb, n = 0.0, 0
    for _nombre, (sub, tope, dias) in CACHES.items():
        d = RAIZ / sub
        if d.is_dir():
            a, b = limpiar_carpeta(d, tope, dias)
            mb += a
            n += b
    return mb, n


def resumen():
    filas, total = [], 0.0
    for nombre, (sub, tope, _dias) in CACHES.items():
        mb = tamano_mb(RAIZ / sub)
        total += mb
        filas.append((nombre, mb, tope))
    return filas, total
