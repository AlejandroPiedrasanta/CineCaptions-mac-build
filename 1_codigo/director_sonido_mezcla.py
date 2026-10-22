# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_mezcla.py — «AI Sound Director», FASE 5: la mezcla completa, el QC en 3 pasadas y el SOUND SCORE (de métricas reales).
"""
revisar(video, ctx, estado, eventos, voz_archivo=None) → {'medidas', 'correcciones', 'score', 'partes', 'mix', 'master'}

    1 DISEÑO          lo hecho en las fases 2–4 (voz, sonidos, música, ambiente), cada cosa con su nivel dentro del archivo
    2 ANÁLISIS        la mezcla COMPLETA offline = lo que suma Resolve a 0 dB (la voz que va a sonar —AI VOICE o el audio del timeline, con
                      Quitar pausas— + cada evento en su sitio), en streaming: LUFS integrado, LRA, true peak, clipping, y por evento su nivel
                      contra la voz mientras habla (enmascaramiento), la música contra la voz, la densidad y los clones
    3 AUTOCORRECCIÓN  lo que pisa a la voz baja lo justo (solo ese evento) y, si los SFX/música empujan el true peak por encima de −1 dBTP, el bus
                      del director baja lo necesario (la voz no se toca); se rehace solo lo cambiado y se vuelve a medir

SOUND SCORE /100 = 25 claridad de la voz + 15 control del ruido + 15 sincronía con el motion + 10 balance de música + 10 consistencia de SFX +
15 protección de la voz + 10 mezcla final; cada parte con su número y su porqué (FORMULA, abajo). Referencias: ~−14 LUFS y ≤ −1 dBTP sin aplastar
la dinámica (el máster lo pone Resolve al exportar: aquí se mide y se dice).
"""
import wave
from pathlib import Path

import numpy as np

SR = 48000
TROZO = 4 * SR
PESOS = {'voz': 25, 'ruido': 15, 'sincronia': 15, 'musica': 10, 'consistencia': 10, 'proteccion': 15, 'mezcla': 10}
FORMULA = ('claridad de la voz: SNR 1–4 kHz (≥ 30 dB = 100, 0 dB = 0) · ruido: fondo final (≤ −60 dBFS = 100, −30 = 0; con música mezclada, 85) · '
           'sincronía: error medio «cuándo suena»–ancla (golpe: su pico; tic/pop/acento: su ataque al 50 %; 0 ms = 100, −2 por ms) · '
           'música: bajo la voz al hablar (−16…−26 dB = 100) o decisión coherente · '
           'consistencia: −15 por clon (salvo el motivo) y −10 por ventana de 10 s pasada de tope · protección: % de sonidos sobre la voz ≥ 8 dB por debajo · '
           'mezcla: true peak ≤ −1 dBTP (40) + sin clipping (30) + LUFS en −16…−12 (30)')
MARGEN_VOZ_DB = 8.0
TECHO_TP = -1.0


class Tira:
    """Un WAV leído por trozos con acceso directo (16/24/32 bits): la música de una hora no entra entera en memoria."""
    def __init__(self, ruta):
        self.w = wave.open(str(ruta), 'rb')
        self.can, self.ancho, self.n = self.w.getnchannels(), self.w.getsampwidth(), self.w.getnframes()

    def leer(self, i0, n):
        y = np.zeros((2, n), np.float32)
        if i0 >= self.n or i0 + n <= 0:
            return y
        a = max(0, i0)
        k = min(self.n, i0 + n) - a
        self.w.setpos(a)
        b = self.w.readframes(k)
        if self.ancho == 3:
            u = np.frombuffer(b, np.uint8).reshape(-1, 3)
            v = (u[:, 0].astype(np.int32) | (u[:, 1].astype(np.int32) << 8) | (u[:, 2].astype(np.int32) << 16))
            v = np.where(v >= 1 << 23, v - (1 << 24), v).astype(np.float32) / 8388608.0
        elif self.ancho == 2:
            v = np.frombuffer(b, '<i2').astype(np.float32) / 32768.0
        else:
            v = np.frombuffer(b, '<i4').astype(np.float32) / 2147483648.0
        v = v.reshape(-1, self.can).T
        if v.shape[0] == 1:
            v = np.vstack((v, v))
        y[:, a - i0:a - i0 + k] = v[:2, :k]
        return y

    def cerrar(self):
        try:
            self.w.close()
        except Exception:
            pass


def _voz_por_trozos(video, ctx, voz_archivo):
    """La voz que va a sonar, en trozos de 4 s del timeline: la copia AI VOICE o el audio del video (con Quitar pausas)."""
    if voz_archivo and Path(voz_archivo).is_file():
        t = Tira(voz_archivo)
        try:
            for i in range(0, t.n, TROZO):
                yield t.leer(i, min(TROZO, t.n - i))
        finally:
            t.cerrar()
        return
    import director_sonido_medir as M
    segs = [tuple(x) for x in ((ctx.get('recorte') or {}).get('segmentos') or [])] or None
    resto = np.zeros((2, 0), np.float32)
    for x in M.trozos(str(video), segmentos=segs, canales=2):
        x = np.asarray(x, np.float32)
        if x.shape[0] == 1:
            x = np.vstack((x, x))
        resto = np.concatenate((resto, x[:2]), axis=1)
        while resto.shape[1] >= TROZO:
            yield resto[:, :TROZO]
            resto = resto[:, TROZO:]
    if resto.shape[1]:
        yield resto


def _habla(palabras, n_total):
    """Máscara (a 100 Hz) de dónde se habla."""
    m = np.zeros(int(n_total / SR * 100) + 2, bool)
    for p in palabras or []:
        m[int(float(p.get('start') or 0) * 100):int(float(p.get('end') or 0) * 100) + 1] = True
    return m


def _ataque(e):
    """«Cuándo suena» (s, en el timeline), como lo oye el oído: en un GOLPE, el pico de su envolvente (2 ms; los impactos de biblioteca traen un
    barrido antes); en tics, pops y acentos, el ataque (50 % de la envolvente)."""
    t = Tira(e['archivo'])
    try:
        y = t.leer(0, t.n)
    finally:
        t.cerrar()
    env = np.convolve(np.abs(y).max(axis=0), np.ones(96) / 96, 'same')
    if not env.size or env.max() <= 0:
        return None
    i = int(np.argmax(env)) if (e.get('ai') or {}).get('tipo') == 'golpe' else int(np.argmax(env >= 0.5 * env.max()))
    return round(float(e.get('ini') or 0.0) + i / SR, 4)


def medir(video, ctx, eventos, voz_archivo=None):
    """PASADA 2: la mezcla completa medida en streaming. Devuelve las medidas globales y las de cada evento."""
    import director_sonido_medir as M
    tiras = []
    umbral = {}                                                       # «dónde suena» un evento: −40 dB bajo SU pico (no cambia con su ganancia)
    for e in eventos:
        if Path(str(e.get('archivo') or '')).is_file():
            try:
                t = Tira(e['archivo'])
            except (wave.Error, EOFError, OSError):
                continue
            tiras.append((e, t, int(round(float(e.get('ini') or 0.0) * SR))))
            umbral[id(e)] = max(1e-6, 0.01 * float(np.abs(t.leer(0, t.n)).max())) if t.n <= 6 * SR else 1e-4
    S_mix, S_voz = M.Sonometro(2), M.Sonometro(2)
    clip, pos = 0, 0
    por_ev = {id(e): {'e2': 0.0, 'v2': 0.0, 'n': 0, 'pico': 0.0, 'pico_i': None} for e, _t, _i in tiras}
    musica = {'m2': 0.0, 'v2': 0.0, 'n': 0}
    palabras = ctx.get('palabras') or []
    habla = _habla(palabras, 3600 * 3 * SR if not palabras else float(palabras[-1].get('end') or 0) * SR + 10 * SR)
    try:
        for x_voz in _voz_por_trozos(video, ctx, voz_archivo):
            n = x_voz.shape[1]
            mezcla = x_voz.copy()
            t_ms = (pos + np.arange(0, n, SR // 100)) / SR * 100
            sp = np.repeat(habla[np.clip(t_ms.astype(int), 0, len(habla) - 1)], SR // 100)[:n]
            if sp.size < n:
                sp = np.pad(sp, (0, n - sp.size))
            for e, t, i0 in tiras:
                if i0 >= pos + n or i0 + t.n <= pos:
                    continue
                y = t.leer(pos - i0, n)
                mezcla += y
                d = por_ev[id(e)]
                k = np.abs(y).max(axis=0)
                if k.max() > d['pico']:
                    d['pico'], d['pico_i'] = float(k.max()), pos + int(np.argmax(k))
                activo = (k > umbral[id(e)]) & sp
                if activo.any():
                    d['e2'] += float(np.sum(y[:, activo] ** 2))
                    d['v2'] += float(np.sum(x_voz[:, activo] ** 2))
                    d['n'] += int(activo.sum())
                if e.get('pista') == 'AI MUSIC':
                    musica['m2'] += float(np.sum(y[:, sp] ** 2))
                    musica['v2'] += float(np.sum(x_voz[:, sp] ** 2))
                    musica['n'] += int(sp.sum())
            S_mix.medir(mezcla)
            S_voz.medir(x_voz)
            clip += int(np.sum(np.abs(mezcla) > 0.999))
            pos += n
    finally:
        for _e, t, _i in tiras:
            t.cerrar()
    eventos_m = []
    for e, t, i0 in tiras:
        d = por_ev[id(e)]
        rel = 10 * np.log10((d['e2'] + 1e-12) / (d['v2'] + 1e-12)) if d['n'] > SR * 0.02 else None
        ancla = float(e.get('ancla') or 0.0)
        eventos_m.append({'id': (e.get('ai') or {}).get('id'), 'clave': (e.get('ai') or {}).get('clave'), 'tipo': (e.get('ai') or {}).get('tipo'),
                          'pista': e.get('pista'), 'sobre_voz_db': round(float(rel), 1) if rel is not None else None,
                          'ataque_s': _ataque(e) if t.n <= 6 * SR else None, 'ancla': ancla or None})
    m_rel = 10 * np.log10((musica['m2'] + 1e-12) / (musica['v2'] + 1e-12)) if musica['n'] > SR else None
    return {'mezcla': S_mix.resultado(), 'voz': S_voz.resultado(), 'clipping': clip, 'segundos': round(pos / SR, 2), 'eventos': eventos_m,
            'musica_bajo_voz_db': round(float(m_rel), 1) if m_rel is not None else None}


# ------------------------------------------------------------------------------------------------------------------------------ autocorrección
def correcciones(medidas):
    """PASADA 3: lo que hay que bajar. {clave: dB (negativo)} por evento que pisa la voz y un 'bus' global si los SFX/música empujan el true peak."""
    corr = {}
    for e in medidas['eventos']:
        rel = e.get('sobre_voz_db')
        if rel is not None and e.get('pista') not in ('AI MUSIC', 'AI AMBIENCE') and rel > -MARGEN_VOZ_DB and e.get('clave'):
            corr[e['clave']] = round(-(rel + MARGEN_VOZ_DB) - 0.5, 1)
    tp_mix, tp_voz = (medidas['mezcla'] or {}).get('tp_db'), (medidas['voz'] or {}).get('tp_db')
    bus = 0.0
    if tp_mix is not None and tp_mix > TECHO_TP and (tp_voz is None or tp_voz <= TECHO_TP - 0.2):
        bus = round(-(tp_mix - TECHO_TP) - 0.3, 1)                    # lo empujan los del director: baja su bus, no la voz
    return corr, bus


# ------------------------------------------------------------------------------------------------------------------------------ SOUND SCORE
def _lin(v, a, b):
    """0–100 lineal entre a (0) y b (100), acotado."""
    if v is None:
        return None
    return float(np.clip((float(v) - a) / (b - a) * 100.0, 0, 100))


def puntuar(medidas, estado, diseno_eventos=None):
    """El SOUND SCORE y sus partes, cada una con su número y su porqué (FORMULA)."""
    partes = {}
    a = estado.get('analisis') or {}
    musica_fuente = bool(((a.get('musica') or {}).get('en_la_fuente') or {}).get('presente'))
    despues = estado.get('voice_quality_after') if (estado.get('voz') or {}).get('archivo') else None
    q = despues or estado.get('voice_quality_before') or {}
    snr = q.get('snr_1_4k_db') if q.get('snr_1_4k_db') is not None else q.get('snr_db')
    v = _lin(snr, 0.0, 30.0)
    if musica_fuente and v is not None:
        v = max(v, 70.0)                                              # (la «molestia» medida es la música mezclada: la voz se entiende)
    partes['voz'] = (v if v is not None else 70.0, f"SNR 1–4 kHz {snr} dB" + (' (con música mezclada)' if musica_fuente else ''))
    suelo = q.get('suelo_ruido_db')
    r = 85.0 if musica_fuente else _lin(-float(suelo), 30.0, 60.0) if suelo is not None else 70.0
    partes['ruido'] = (r, 'la música del video está debajo (no es ruido)' if musica_fuente else f'fondo final {suelo} dBFS')
    errores = [abs(float(e['ataque_s']) - float(e['ancla'])) * 1000 for e in medidas['eventos']
               if e.get('ataque_s') is not None and e.get('ancla') and e.get('tipo') in ('golpe', 'tick', 'pop', 'acento')]
    err = float(np.mean(errores)) if errores else 0.0
    partes['sincronia'] = (float(np.clip(100 - 2 * err, 0, 100)), f'cada acento suena a {err:.0f} ms de media de su fotograma ({len(errores)} acentos)')
    md = estado.get('music_decision') or {}
    mb = medidas.get('musica_bajo_voz_db')
    if md.get('estado') == 'ADD_NEW' and mb is not None:
        m = 100.0 if -26.0 <= mb <= -16.0 else max(0.0, 100.0 - 8 * min(abs(mb + 16), abs(mb + 26)))
        partes['musica'] = (m, f'la música va {mb:.1f} dB bajo la voz al hablar')
    elif md.get('deseado') == 'ADD_NEW':
        partes['musica'] = (80.0, 'le iría música y falta un proveedor autorizado: mejor sin ella')
    else:
        partes['musica'] = (100.0 if md.get('estado') != 'KEEP_EXISTING' else 95.0, md.get('por_que') or 'sin música: no la necesita')
    clones = 0
    vistos = {}
    for e in estado.get('sfx_plan') or []:
        if (e.get('ai') or {}).get('tipo') == 'acento':
            continue
        vistos[e.get('archivo')] = vistos.get(e.get('archivo'), 0) + 1
    clones = sum(n - 1 for n in vistos.values() if n > 1)
    pasadas = 0
    if diseno_eventos:
        s = estado.get('sfx_summary') or {}
        tope = int(round(2 + 4 * float(((estado.get('paleta') or {}).get('valores') or {}).get('densidad', 0.3)))) + 1
        act = [e for e in diseno_eventos if e.get('decision') == 'GENERATE']
        dur = max([float(e.get('ancla') or 0) for e in act] or [0.0])
        pasadas = sum(1 for k0 in np.arange(0, dur + 0.1, 10.0) if sum(1 for e in act if k0 <= float(e['ancla']) < k0 + 10) > tope)
    partes['consistencia'] = (float(np.clip(100 - 15 * clones - 10 * pasadas, 0, 100)), f'{clones} clones, {pasadas} ventanas por encima del tope')
    sobre = [e for e in medidas['eventos'] if e.get('sobre_voz_db') is not None and e.get('pista') not in ('AI MUSIC', 'AI AMBIENCE')]
    bien = sum(1 for e in sobre if e['sobre_voz_db'] <= -MARGEN_VOZ_DB + 0.3)
    partes['proteccion'] = (100.0 * bien / len(sobre) if sobre else 100.0, f'{bien} de {len(sobre)} sonidos sobre la voz quedan ≥ {MARGEN_VOZ_DB:.0f} dB por debajo')
    mz = medidas.get('mezcla') or {}
    tp, lufs = mz.get('tp_db'), mz.get('lufs')
    p = (40.0 if tp is not None and tp <= TECHO_TP + 0.05 else 0.0) + (30.0 if not medidas.get('clipping') else 0.0)
    if lufs is not None:
        p += 30.0 if -16.0 <= lufs <= -12.0 else max(0.0, 30.0 - 6 * min(abs(lufs + 16), abs(lufs + 12)))
    partes['mezcla'] = (p, f'{lufs} LUFS · true peak {tp} dBTP · {medidas.get("clipping", 0)} muestras recortadas')
    total = sum(PESOS[k] * partes[k][0] / 100.0 for k in PESOS)
    return int(round(total)), {k: {'puntos': int(round(v_)), 'peso': PESOS[k], 'por_que': t} for k, (v_, t) in partes.items()}


def textos(medidas, score):
    """Las líneas «Mezcla» y «Master» de la página."""
    mz = medidas.get('mezcla') or {}
    tp, lufs, lra = mz.get('tp_db'), mz.get('lufs'), mz.get('lra')
    prot = score['proteccion']
    mix = {'valor': 'La voz manda' if prot['puntos'] >= 90 else 'Revisada', 'nivel': 'ok' if prot['puntos'] >= 80 else 'aviso',
           'detalle': prot['por_que']}
    ok_tp = tp is not None and tp <= TECHO_TP + 0.05
    ok_l = lufs is not None and -16.0 <= lufs <= -12.0
    master = {'valor': f'{lufs} LUFS · {tp} dBTP' if lufs is not None else '—', 'nivel': 'ok' if ok_tp and ok_l else 'aviso',
              'detalle': ('Listo para redes (≈ −14 LUFS, ≤ −1 dBTP)' if ok_tp and ok_l else
                          (f'Al exportar en Resolve, sube el máster {(-14.0 - lufs):+.1f} dB' if lufs is not None and lufs < -16 else
                           ('El audio original ya pasa de −1 dBTP' if not ok_tp else 'Dentro de lo razonable'))) + (f' · LRA {lra}' if lra is not None else '')}
    return mix, master
