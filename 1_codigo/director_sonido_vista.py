# CineCaptions · By Cinema Productions
"""Datos de la vista Sonido. Solo se llama en un trabajador; no importa Qt.

Los bloques vienen del mismo plan que se envía a Resolve. Las ondas son máximos
del audio real, calculados en streaming y guardados en una caché de memoria.
Una pista sin archivo separado nunca recibe una onda inventada.
"""
import math
import wave
from collections import OrderedDict
from pathlib import Path

import numpy as np

_CACHE = OrderedDict()
_MAX_CACHE = 96
PISTAS = (
    ('video', 'Video', 'Referencia del montaje', '#7788A5', '#28344A'),
    ('voz', 'Voz', 'AI VOICE', '#6BC4C7', '#164049'),
    ('musica', 'Música', 'AI MUSIC', '#B19BDA', '#342B4D'),
    ('ambiente', 'Ambiente', 'AI AMBIENCE', '#86B59D', '#233C35'),
    ('movimiento', 'Movimiento', 'AI SFX MOTION', '#C6A674', '#4A3B29'),
    ('acentos', 'Acentos', 'AI SFX IMPACTS', '#C895A4', '#49313C'),
)


def _numero(v, defecto=0.0):
    try:
        v = float(v)
        return v if math.isfinite(v) else defecto
    except (TypeError, ValueError):
        return defecto


def _guardar_cache(clave, dato):
    _CACHE[clave] = dato
    _CACHE.move_to_end(clave)
    while len(_CACHE) > _MAX_CACHE:
        _CACHE.popitem(last=False)
    return dato


def _picos_trozos(trozos, n_muestras, puntos=2048):
    """Pico por bin fijo; memoria independiente de la duración del archivo."""
    n_muestras = max(1, int(n_muestras))
    paso = max(1, math.ceil(n_muestras / max(1, int(puntos))))
    picos = np.zeros(math.ceil(n_muestras / paso), dtype=np.float32)
    pos = 0
    for x in trozos:
        x = np.asarray(x)
        if x.ndim > 1:
            x = np.max(np.abs(x), axis=0)
        else:
            x = np.abs(x)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        ini = 0
        while ini < len(x) and pos < n_muestras:
            n = min(paso - pos % paso, len(x) - ini, n_muestras - pos)
            k = pos // paso
            picos[k] = max(picos[k], float(np.max(x[ini:ini + n])))
            ini += n
            pos += n
        if pos >= n_muestras:
            break
    return np.clip(picos, 0.0, 1.0).tolist()


def onda_wav(archivo, puntos=2048):
    """Duración y picos PCM reales (8/16/24/32 bits), o None si no es legible."""
    p = Path(str(archivo or ''))
    try:
        st = p.stat()
        clave = (str(p.resolve()), st.st_size, st.st_mtime_ns, int(puntos))
        if clave in _CACHE:
            _CACHE.move_to_end(clave)
            return _CACHE[clave]
        with wave.open(str(p), 'rb') as w:
            canales, ancho = w.getnchannels(), w.getsampwidth()
            tasa, muestras = w.getframerate(), w.getnframes()
            if not tasa or not muestras or ancho not in (1, 2, 3, 4):
                return None

            def trozos():
                while True:
                    b = w.readframes(tasa * 4)
                    if not b:
                        break
                    if ancho == 1:
                        v = (np.frombuffer(b, np.uint8).astype(np.float32) - 128) / 128.0
                    elif ancho == 2:
                        v = np.frombuffer(b, '<i2').astype(np.float32) / 32768.0
                    elif ancho == 3:
                        u = np.frombuffer(b, np.uint8).reshape(-1, 3)
                        v = u[:, 0].astype(np.int32) | u[:, 1].astype(np.int32) << 8 | u[:, 2].astype(np.int32) << 16
                        v = np.where(v >= 1 << 23, v - (1 << 24), v).astype(np.float32) / 8388608.0
                    else:
                        v = np.frombuffer(b, '<i4').astype(np.float32) / 2147483648.0
                    yield v.reshape(-1, canales).T

            dato = {'duracion': muestras / tasa, 'picos': _picos_trozos(trozos(), muestras, puntos)}
        return _guardar_cache(clave, dato)
    except (OSError, EOFError, ValueError, wave.Error):
        return None


def _onda_origen(video, segmentos, duracion):
    """Audio de origen en tiempo del montaje; si no hay audio, sin onda."""
    try:
        p = Path(video)
        st = p.stat()
        clave = ('origen', str(p.resolve()), st.st_size, st.st_mtime_ns, tuple(tuple(s) for s in segmentos or []), duracion)
        if clave in _CACHE:
            _CACHE.move_to_end(clave)
            return _CACHE[clave]
        import director_sonido_medir as M
        picos = _picos_trozos(M.trozos(video, segmentos=segmentos or None, canales=1), int(duracion * 48000))
        return _guardar_cache(clave, {'duracion': duracion, 'picos': picos})
    except Exception:
        return None


def construir(video, resumen, estado=None, contexto=None):
    """Una foto simple del plan exportable. Nunca escribe estado ni toca Resolve."""
    if not (resumen or {}).get('hay'):
        return {'pistas': [], 'duracion': 0.0, 'avisos': []}
    if estado is None:
        import director_sonido_estado as E
        estado = E.cargar(video)
    if contexto is None:
        import director_sonido as D
        contexto = D.cargar_contexto(video) or {}
    estado, contexto = estado or {}, contexto or {}
    planes = [(k, e) for k in ('sfx_plan', 'music_plan', 'ambience_plan') for e in estado.get(k) or [] if isinstance(e, dict)]
    dur = max(_numero(resumen.get('duracion')), max((_numero(e.get('ini')) + max(0.0, _numero(e.get('dur'))) for _, e in planes), default=0.0))
    pistas = [dict(clave=k, nombre=n, detalle=d, color=c, fondo=f, clips=[]) for k, n, d, c, f in PISTAS]
    por_clave = {p['clave']: p for p in pistas}
    avisos = []
    cortes = sorted({0.0, dur} | {max(0.0, min(dur, _numero(c))) for c in (resumen.get('carriles') or {}).get('cortes') or []})
    for a, b in zip(cortes, cortes[1:]):
        if b > a:
            por_clave['video']['clips'].append(dict(ini=a, dur=b - a, nombre=Path(str(video)).name, pista='Video de referencia'))
    ultimo = estado.get('ultimo_go') or {}
    voz = (ultimo.get('evento_voz') or {}) if ultimo.get('voz') else {}
    archivo_voz = voz.get('archivo') or ((estado.get('voz') or {}).get('archivo') if ultimo.get('voz') else None)
    onda = onda_wav(archivo_voz) if archivo_voz else None
    if onda:
        ini = max(0.0, _numero(voz.get('ini')))
        largo = min(dur - ini, _numero(voz.get('dur'), onda['duracion']))
        if largo > 0:
            por_clave['voz']['clips'].append(dict(ini=ini, dur=largo, nombre='Voz principal', pista='AI VOICE', archivo=archivo_voz, onda=onda))
    elif dur > 0:
        segmentos = (contexto.get('recorte') or {}).get('segmentos') or []
        onda = _onda_origen(video, segmentos, dur)
        por_clave['voz']['detalle'] = 'Audio del video'
        por_clave['voz']['clips'].append(dict(ini=0.0, dur=dur, nombre='Audio original del montaje', pista='Audio del video', archivo=video, onda=onda))
    for origen, e in planes:
        pista, tipo = str(e.get('pista') or ''), str(e.get('tipo') or '')
        if origen == 'music_plan' or pista == 'AI MUSIC':
            grupo = 'musica'
        elif origen == 'ambience_plan' or pista == 'AI AMBIENCE':
            grupo = 'ambiente'
        elif any(s in pista.upper() for s in ('MOTION', 'TEXTURE', 'WHOOSH', 'RISER')) or tipo in ('whoosh', 'riser', 'giro', 'trazo'):
            grupo = 'movimiento'
        else:
            grupo = 'acentos'
        ini, largo = _numero(e.get('ini')), max(0.0, _numero(e.get('dur')))
        a, b = max(0.0, ini), min(dur, ini + largo)
        if b <= a:
            continue
        archivo = str(e.get('archivo') or '')
        onda = onda_wav(archivo)
        if onda is None:
            avisos.append('No se puede leer el audio de ' + (Path(archivo).name or pista))
        nombre = str(e.get('asset') or e.get('nombre') or tipo or pista)
        for prefijo in ('AI MUSIC · ', 'AI AMBIENCE · ', 'AI SFX · '):
            if nombre.startswith(prefijo):
                nombre = nombre[len(prefijo):]
        por_clave[grupo]['clips'].append(dict(ini=a, dur=b - a, fuente_desde=a - ini, nombre=nombre, pista=pista,
                                            archivo=archivo, onda=onda, clave=e.get('clave') or e.get('id')))
    if not por_clave['musica']['clips'] and (((estado.get('analisis') or {}).get('musica') or {}).get('en_la_fuente') or {}).get('presente'):
        por_clave['musica']['detalle'] = 'Integrada en el video'
        por_clave['musica']['clips'].append(dict(ini=0.0, dur=dur, nombre='Música del video · se conserva', pista='Audio original', integrada=True))
    for pista in pistas:
        pista['clips'].sort(key=lambda c: (c['ini'], c['dur']))
        reales = list(dict.fromkeys(c.get('pista') for c in pista['clips'] if c.get('pista')))
        if len(reales) > 1:
            pista['detalle'] = ' / '.join(reales)
        # Apilar solapamientos según su pista real: nunca tapar un sonido con otro.
        ocupados = []
        for clip in pista['clips']:
            fila = next((i for i, hasta in enumerate(ocupados) if hasta <= clip['ini'] + .001), len(ocupados))
            if fila == len(ocupados):
                ocupados.append(0.0)
            ocupados[fila] = clip['ini'] + clip['dur']
            clip['subfila'] = fila
        pista['subfilas'] = max(1, len(ocupados))
    reales = {c['pista'] for p in pistas[1:] for c in p['clips'] if not c.get('integrada')}
    return {'pistas': pistas, 'duracion': dur, 'avisos': list(dict.fromkeys(avisos)), 'n_pistas_audio': len(reales)}
