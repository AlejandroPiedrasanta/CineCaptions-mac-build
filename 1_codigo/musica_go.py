# CineCaptions · By Cinema Productions
# 1_codigo/musica_go.py — música de fondo automática para GO (v5.4.8): elige, alinea al pulso, nivela y baja sola cuando se habla.
"""
El usuario elige UNA música o una CARPETA de músicas (pestaña Sonido). Al hacer GO, con la transcripción ya hecha:

  1. elegir()     si es una carpeta, la música que más pega (BPM entre 85 y 130; si hay varias, una distinta por video, siempre la misma para el mismo video);
  2. bpm          se detecta su pulso y se empieza la música DENTRO del archivo en el punto justo para que un golpe de pulso caiga en el golpe de la palabra clave del gancho;
  3. preparar()   se hornea un WAV (Resolve no deja cambiar el volumen de un clip por script): en bucle con fundido si el archivo es más corto que el video, nivelada a un nivel
                  de fondo, con ducking fino (ducking.curva_fina: baja más cuanto más rápido se habla, sube deprisa en las pausas largas y se queda casi muda en el «hueco» de 0,2 s
                  antes del golpe) y con fundido de entrada y de salida.

La preferencia es `musica_go` = {'activo': bool, 'ruta': archivo o carpeta, 'db': ajuste fino en dB (-6…+6), 'alinear': bool (pulso ↔ golpe y efectos al pulso)}.
"""
from __future__ import annotations

import hashlib
import wave
from pathlib import Path

CARPETA_CACHE = Path.home() / 'DaVinciSubtitles' / 'musica_go_cache'
EXTENSIONES = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.opus'}
OBJETIVO_DB = -23.0                       # nivel de la música (RMS con puerta) antes del ducking: con -10 dB de ducking queda ~13 dB por debajo de una voz normal
FUNDIDO_ENTRADA_S = 0.8
FUNDIDO_SALIDA_S = 2.2
CRUCE_BUCLE_S = 0.6


def config(prefs=None):
    """La configuración de la música de GO (con valores por defecto)."""
    if prefs is None:
        try:
            import ajustes_ui
            prefs = ajustes_ui.leer_prefs()
        except Exception:
            prefs = {}
    m = prefs.get('musica_go') if isinstance(prefs.get('musica_go'), dict) else {}
    return {'activo': bool(m.get('activo')), 'ruta': str(m.get('ruta') or ''), 'db': float(m.get('db') or 0.0), 'alinear': m.get('alinear', True) is not False}


def archivos_de(ruta):
    p = Path(str(ruta or ''))
    if p.is_file():
        return [p] if p.suffix.lower() in EXTENSIONES else []
    if p.is_dir():
        return sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in EXTENSIONES)
    return []


def elegir(ruta, semilla=''):
    """(archivo, info_bpm) de la música a usar. Con una carpeta: hasta 12 candidatas, las de 85-130 BPM primero, y una por semilla (el nombre del video)."""
    import bpm
    lista = archivos_de(ruta)
    if not lista:
        return None, None
    if len(lista) == 1:
        return lista[0], bpm.detectar(lista[0])
    candidatas = []
    for f in lista[:12]:
        info = bpm.detectar(f)
        if info and 85.0 <= float(info['bpm']) <= 130.0:
            candidatas.append((f, info))
    if not candidatas:
        f = lista[int(hashlib.md5(str(semilla).encode('utf-8')).hexdigest(), 16) % len(lista)]
        return f, bpm.detectar(f)
    return candidatas[int(hashlib.md5(str(semilla).encode('utf-8')).hexdigest(), 16) % len(candidatas)]


def _escribir_wav(audio, tasa, destino):
    import numpy as np
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(tasa)
        w.writeframes((np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes())
    return destino


def _en_bucle(audio, tasa, inicio_s, largo_s):
    """Exactamente `largo_s` de música desde `inicio_s` dentro del archivo; si se acaba, vuelve al principio con un cruce de CRUCE_BUCLE_S."""
    import numpy as np
    n = int(round(largo_s * tasa))
    o = max(0, min(int(inicio_s * tasa), max(0, len(audio) - 2 * tasa)))
    salida = audio[o:o + n]
    cruce = int(CRUCE_BUCLE_S * tasa)
    while len(salida) < n and len(audio) > 2 * cruce:
        falta = n - len(salida) + cruce
        siguiente = audio[:falta]
        rampa = np.linspace(0.0, 1.0, cruce, dtype=np.float32)[:, None]
        mezcla = salida[-cruce:] * (1.0 - rampa) + siguiente[:cruce] * rampa
        salida = np.concatenate([salida[:-cruce], mezcla, siguiente[cruce:]])
    return salida[:n].astype(np.float32)


def preparar(ruta_musica, palabras, duracion, db_ajuste=0.0, desplazamiento=0.0, hoyos=None, destino=None):
    """Hornea la música de fondo (WAV 48 kHz estéreo) para un video de `duracion` s. Devuelve la ruta."""
    import numpy as np
    import ducking
    import sfx_rules
    ruta_musica = Path(str(ruta_musica))
    firma = hashlib.sha1('|'.join([str(ruta_musica.resolve()), str(ruta_musica.stat().st_mtime_ns), '%.1f' % duracion, '%.2f' % db_ajuste, '%.3f' % desplazamiento,
                                   str(ducking.intervalos_de_voz(palabras)), str(hoyos), 'r1']).encode('utf-8')).hexdigest()[:14]
    destino = Path(destino) if destino else CARPETA_CACHE / f'{ruta_musica.stem[:40]}_{firma}.wav'
    if destino.is_file() and destino.stat().st_size > 10000:
        return destino
    audio, tasa = ducking._cargar_estereo(ruta_musica)
    seg = _en_bucle(audio, tasa, desplazamiento, duracion)
    # nivel de fondo: el RMS con puerta va al objetivo (+ el ajuste del usuario), sin pasar de -1 dBFS de pico
    rms_db, pico_db = sfx_rules.nivel_de_audio(seg, tasa)
    ganancia_db = OBJETIVO_DB + float(db_ajuste) - rms_db
    ganancia_db = min(ganancia_db, -1.0 - pico_db)                            # el pico nunca pasa de -1 dBFS (el ducking solo baja)
    seg = seg * (10 ** (ganancia_db / 20.0))
    curva = ducking.curva_fina(palabras, duracion, hoyos)
    t_curva = np.arange(len(curva)) / float(ducking.PASO)
    t_audio = np.arange(len(seg)) / float(tasa)
    seg = seg * np.interp(t_audio, t_curva, curva).astype(np.float32)[:, None]
    # fundidos de entrada y de salida
    fi, fo = int(FUNDIDO_ENTRADA_S * tasa), int(min(FUNDIDO_SALIDA_S, duracion / 3.0) * tasa)
    if fi > 1 and len(seg) > fi:
        seg[:fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)[:, None]
    if fo > 1 and len(seg) > fo:
        seg[-fo:] *= np.linspace(1.0, 0.0, fo, dtype=np.float32)[:, None]
    return _escribir_wav(seg, tasa, destino)
