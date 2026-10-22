# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_medir.py — «AI Sound Director»: leer, filtrar y medir audio con PyAV (ffmpeg dentro del programa), en streaming.
"""
Todo trabaja por TROZOS (un video de una hora no se carga entero): `trozos()` decodifica a 48 kHz float32 (canales × muestras) en el tiempo del
TIMELINE (con «Quitar pausas», solo los tramos que se quedan, pegados); `Grafo` pasa los trozos por una cadena de filtros de ffmpeg (afftdn,
highpass, equalizer, deesser, acompressor, alimiter, ebur128…), `Analizador` saca de cada trozo las medidas que usan la voz, la música y el ambiente,
`Sonometro` da LUFS integrados, LRA y true peak (ebur128) y `EscritorWav` escribe la copia en WAV de 24 bits.

Medidas del Analizador (por marco de 20 ms y por marco «fino» de 8192 muestras ≈ 171 ms):
    rms_db            nivel de cada marco de 20 ms (mezcla de los canales)
    bandas_db         energía de cada marco en BANDAS (sub, graves, cuerpo, barro, medio, m1, m2, presencia, sibilancia, aire, brillo)
    clase             0 = silencio de voz, 2 = voz, 1 = transición (por las palabras si las hay; si no, por el nivel)
    espectro[clase]   espectro medio de alta resolución (5,9 Hz) de cada clase, para hum, resonancias y equilibrio tonal
    planitud / tonal  por marco fino: planitud espectral (300–6000 Hz) y picos tonales en 2–8 kHz (pájaros, pitidos)
    estereo           correlación L/R y diferencia de nivel
    planitud20        planitud espectral (300–6000 Hz) de cada marco de 20 ms (el fondo entre palabras: tonal = música, liso = ruido)
"""
from fractions import Fraction

import numpy as np

SR = 48000
MARCO = 960                     # 20 ms
NFFT = 1024
FINO = 8192                     # marco fino (≈ 171 ms con salto de la mitad)
BANDAS = (('sub', 20, 80), ('graves', 80, 150), ('cuerpo', 150, 300), ('barro', 250, 500), ('medio', 500, 1000), ('m1', 1000, 2000),
          ('m2', 2000, 4000), ('presencia', 4000, 6000), ('sibilancia', 5000, 9000), ('aire', 6000, 10000), ('brillo', 10000, 16000))
NOMBRES_BANDAS = tuple(b[0] for b in BANDAS)
EPS = 1e-12


def db(x):
    return 10.0 * np.log10(np.maximum(np.asarray(x, dtype=np.float64), EPS))


def info(ruta):
    """{'duracion', 'canales', 'tasa', 'video'} del primer audio del archivo (None si no tiene audio)."""
    import av
    with av.open(str(ruta)) as c:
        if not c.streams.audio:
            return None
        a = c.streams.audio[0]
        dur = float(c.duration / 1e6) if c.duration else (float(a.duration * a.time_base) if a.duration else 0.0)
        return {'duracion': dur, 'canales': int(a.codec_context.channels or 1), 'tasa': int(a.codec_context.sample_rate or SR), 'video': bool(c.streams.video)}


def trozos(ruta, segmentos=None, canales=None, trozo_s=4.0, recortes=None):
    """Genera trozos float32 (canales, n) a 48 kHz en tiempo del TIMELINE. `segmentos` [(a, b)] en segundos de la fuente (Quitar pausas): solo eso,
    pegado. `canales` 1 o 2 (None = los del archivo, máx. 2). `recortes` (dict opcional) cuenta el clipping en las muestras ORIGINALES."""
    import av
    c = av.open(str(ruta))
    try:
        a = c.streams.audio[0]
        n_can = int(a.codec_context.channels or 1)
        salida = min(2, n_can) if canales is None else int(canales)
        rs = av.AudioResampler(format='fltp', layout='stereo' if salida == 2 else 'mono', rate=SR)
        segs = [(int(round(float(x) * SR)), int(round(float(y) * SR))) for x, y in (segmentos or [])]
        pos = 0                                                    # muestra (a 48 kHz) de la fuente por la que vamos
        tasa = int(a.codec_context.sample_rate or SR)
        buf, en_buf = [], 0
        objetivo = int(trozo_s * SR)

        def recortar(x, ini):
            if not segs:
                return x
            fin = ini + x.shape[1]
            partes = [x[:, max(sa, ini) - ini:min(sb, fin) - ini] for sa, sb in segs if sb > ini and sa < fin]
            return np.concatenate(partes, axis=1) if partes else x[:, :0]

        def soltar(frames):
            nonlocal pos, en_buf
            for g in frames:
                x = g.to_ndarray().astype(np.float32, copy=False)
                if x.ndim == 1:
                    x = x[None, :]
                x = recortar(x, pos)
                pos += g.samples
                if x.shape[1]:
                    buf.append(x)
                    en_buf += x.shape[1]
        for fr in c.decode(a):
            if recortes is not None:
                t0 = float(fr.pts * fr.time_base) if fr.pts is not None else None
                if not segs or (t0 is not None and any(sa / SR - 0.05 <= t0 <= sb / SR for sa, sb in segs)):
                    _contar_recortes(_a_flotante(fr.to_ndarray(), n_can, fr.format.is_planar), recortes, tasa)
            soltar(rs.resample(fr))
            if en_buf >= objetivo:
                yield np.concatenate(buf, axis=1)
                buf.clear()
                en_buf = 0
        soltar(rs.resample(None))
        if buf:
            yield np.concatenate(buf, axis=1)
    finally:
        c.close()


def _a_flotante(x, canales, plano):
    """Las muestras nativas de un fotograma como float (canales, n) en [-1, 1] (los PCM enteros se escalan; los intercalados se separan)."""
    x = np.asarray(x)
    if np.issubdtype(x.dtype, np.integer):
        x = x.astype(np.float32) / float(np.iinfo(x.dtype).max)
    else:
        x = x.astype(np.float32, copy=False)
    if not plano and canales > 1:
        x = x.reshape(-1, canales).T
    return x if x.ndim > 1 else x[None, :]


def _contar_recortes(x, cuenta, tasa):
    """Muestras pegadas al máximo (|x| ≥ 0,999) en tramos de 3 o más seguidas = clipping."""
    m = np.abs(x).max(axis=0) if x.ndim > 1 else np.abs(x)
    cuenta['muestras'] = cuenta.get('muestras', 0) + int(m.size)
    pegadas = m >= 0.999
    if not pegadas.any():
        return
    d = np.diff(np.concatenate(([0], pegadas.astype(np.int8), [0])))
    ini, fin = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    largos = fin - ini
    cuenta['recortadas'] = cuenta.get('recortadas', 0) + int(largos[largos >= 3].sum())
    cuenta['tramos'] = cuenta.get('tramos', 0) + int((largos >= 3).sum())
    cuenta['pico'] = max(cuenta.get('pico', 0.0), float(m.max()))


class Grafo:
    """Una cadena de filtros de ffmpeg [(nombre, 'opciones')] para trozos (canales, n) a 48 kHz. empujar(x) devuelve lo que ya salió;
    terminar() vacía la cola. `metadatos` guarda lo último que anotó ebur128 (si va en la cadena)."""

    def __init__(self, cadena, canales):
        import av
        from av.filter import Graph
        self.canales = int(canales)
        disposicion = 'stereo' if self.canales == 2 else 'mono'
        self.g = Graph()
        prev = self.g.add_abuffer(format='fltp', sample_rate=SR, layout=disposicion, channels=self.canales)
        for nombre, opciones in cadena or []:
            n = self.g.add(nombre, opciones or None)
            prev.link_to(n)
            prev = n
        fmt = self.g.add('aformat', f'sample_fmts=fltp:channel_layouts={disposicion}:sample_rates={SR}')
        prev.link_to(fmt)
        sink = self.g.add('abuffersink')
        fmt.link_to(sink)
        self.g.configure()
        self.av = av
        self.pts = 0
        self.metadatos = {}

    def _sacar(self):
        salida = []
        while True:
            try:
                o = self.g.pull()
            except (self.av.BlockingIOError, self.av.EOFError):
                break
            md = getattr(o, 'metadata', None)
            if md:
                self.metadatos = dict(md)
            salida.append(o.to_ndarray().astype(np.float32, copy=False).reshape(self.canales, -1))
        return np.concatenate(salida, axis=1) if salida else np.zeros((self.canales, 0), np.float32)

    def empujar(self, x):
        x = np.ascontiguousarray(x, dtype=np.float32)
        fr = self.av.AudioFrame.from_ndarray(x, format='fltp', layout='stereo' if self.canales == 2 else 'mono')
        fr.sample_rate = SR
        fr.pts = self.pts
        fr.time_base = Fraction(1, SR)
        self.pts += x.shape[1]
        self.g.push(fr)
        return self._sacar()

    def terminar(self):
        try:
            self.g.push(None)
        except Exception:
            pass
        return self._sacar()


class Sonometro:
    """LUFS integrados, LRA y true peak (ebur128 de ffmpeg) de lo que se le pase."""

    def __init__(self, canales):
        self.grafo = Grafo([('ebur128', 'metadata=1:peak=true')], canales)

    def medir(self, x):
        self.grafo.empujar(x)

    def resultado(self):
        self.grafo.terminar()
        md = self.grafo.metadatos

        def num(k, defecto=None):
            try:
                return float(md.get(k))
            except (TypeError, ValueError):
                return defecto
        tp = num('lavfi.r128.true_peak')
        return {'lufs': num('lavfi.r128.I'), 'lra': num('lavfi.r128.LRA'), 'tp_db': round(20 * np.log10(max(tp, 1e-9)), 2) if tp is not None else None}


class EscritorWav:
    """WAV PCM de 24 bits por trozos (sin cargar la copia entera en memoria)."""

    def __init__(self, destino, canales):
        import wave
        from pathlib import Path
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        self.w = wave.open(str(destino), 'wb')
        self.w.setnchannels(int(canales))
        self.w.setsampwidth(3)
        self.w.setframerate(SR)
        self.muestras = 0

    def escribir(self, x):
        x = np.clip(np.asarray(x, dtype=np.float64), -1.0, 1.0 - 1.0 / 8388608)
        enteros = np.round(x.T * 8388607.0).astype('<i4')               # (n, canales) intercalado
        b = enteros.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3]
        self.w.writeframes(b.tobytes())
        self.muestras += x.shape[1]

    def cerrar(self):
        self.w.close()


def leer_wav(ruta, trozo_s=4.0):
    """Trozos float32 (canales, n) de un WAV de 16/24/32 bits (las copias del director)."""
    import wave
    with wave.open(str(ruta), 'rb') as w:
        can, ancho = w.getnchannels(), w.getsampwidth()
        n = int(trozo_s * w.getframerate())
        while True:
            b = w.readframes(n)
            if not b:
                break
            if ancho == 3:
                u = np.frombuffer(b, np.uint8).reshape(-1, 3)
                v = (u[:, 0].astype(np.int32) | (u[:, 1].astype(np.int32) << 8) | (u[:, 2].astype(np.int32) << 16))
                v = np.where(v >= 1 << 23, v - (1 << 24), v).astype(np.float32) / 8388608.0
            elif ancho == 2:
                v = np.frombuffer(b, '<i2').astype(np.float32) / 32768.0
            else:
                v = np.frombuffer(b, '<i4').astype(np.float32) / 2147483648.0
            yield v.reshape(-1, can).T.copy()


class Analizador:
    """Las medidas de un audio, trozo a trozo. `clase_fina` (opcional): la clase (0/1/2) de cada marco fino ya decidida (para comparar ANTES y
    DESPUÉS con los mismos marcos). `palabras` (opcional, tiempo del timeline): la voz sale de ellas."""

    def __init__(self, palabras=None, clase_fina=None):
        self.ventana = np.hanning(MARCO).astype(np.float32)
        self.ventana_fina = np.hanning(FINO).astype(np.float32)
        f = np.fft.rfftfreq(NFFT, 1.0 / SR)
        self.idx_bandas = [(np.searchsorted(f, a), max(np.searchsorted(f, a) + 1, np.searchsorted(f, b))) for _n, a, b in BANDAS]
        self.f_fino = np.fft.rfftfreq(FINO, 1.0 / SR)
        self.rp = (np.searchsorted(self.f_fino, 300), np.searchsorted(self.f_fino, 6000))
        self.rt = (np.searchsorted(self.f_fino, 2000), np.searchsorted(self.f_fino, 8000))
        self.palabras = sorted(((float(p.get('start', 0)), float(p.get('end', p.get('start', 0)))) for p in (palabras or [])
                                if isinstance(p, dict)), key=lambda x: x[0])
        self.inicios = [p[0] for p in self.palabras]
        self.clase_fina_externa = None if clase_fina is None else np.asarray(clase_fina, np.int8)
        self.rms, self.bandas, self.planitud, self.tonal, self.nivel_fino, self.clase_por_palabras = [], [], [], [], [], []
        self.planitud20, self.graves_fino, self.medio_fino, self.f0, self.efimeros = [], [], [], [], []
        self.picos_prev = None
        self.rg = (np.searchsorted(self.f_fino, 20), np.searchsorted(self.f_fino, 150))
        self.rm = (np.searchsorted(self.f_fino, 300), np.searchsorted(self.f_fino, 3000))
        self.r20 = (np.searchsorted(np.fft.rfftfreq(NFFT, 1.0 / SR), 300), np.searchsorted(np.fft.rfftfreq(NFFT, 1.0 / SR), 6000))
        self.esp = {0: np.zeros(FINO // 2 + 1), 1: np.zeros(FINO // 2 + 1), 2: np.zeros(FINO // 2 + 1)}
        self.n_esp = {0: 0, 1: 0, 2: 0}
        self.cubos = np.zeros((24, FINO // 2 + 1))                 # espectro por nivel (cubos de 5 dB), para decidir la clase sin palabras
        self.n_cubos = np.zeros(24, np.int64)
        self.cola = np.zeros((0,), np.float32)                     # lo que sobró del trozo anterior (mezcla mono)
        self.cola_fina = np.zeros((0,), np.float32)
        self.n_fino = 0
        self.est = np.zeros(4)                                     # ΣL², ΣR², ΣLR, n
        self.muestras = 0

    def _clase_de_t(self, t):
        """2 si en t se habla (con 40 ms de margen), 0 si la palabra más cercana está a más de 0,25 s, si no 1."""
        import bisect
        if not self.palabras:
            return None
        i = bisect.bisect_right(self.inicios, t + 0.04) - 1
        cerca = 99.0
        for j in (i, i + 1):
            if 0 <= j < len(self.palabras):
                a, b = self.palabras[j]
                if a - 0.04 <= t <= b + 0.04:
                    return 2
                cerca = min(cerca, abs(t - a), abs(t - b))
        return 0 if cerca > 0.25 else 1

    def alimentar(self, x):
        x = np.asarray(x, dtype=np.float32)
        if x.ndim == 1:
            x = x[None, :]
        if x.shape[0] == 2:
            l, r = x[0].astype(np.float64), x[1].astype(np.float64)
            self.est += (float(np.dot(l, l)), float(np.dot(r, r)), float(np.dot(l, r)), l.size)
        mono = x.mean(axis=0)
        self.muestras += mono.size
        # marcos de 20 ms
        s = np.concatenate((self.cola, mono))
        n = s.size // MARCO
        if n:
            m = s[:n * MARCO].reshape(n, MARCO)
            self.rms.append(db(np.mean(m.astype(np.float64) ** 2, axis=1)).astype(np.float32))
            pad = np.zeros((n, NFFT), np.float32)
            pad[:, :MARCO] = m * self.ventana
            p = np.abs(np.fft.rfft(pad, axis=1)) ** 2
            escala = 2.0 / (NFFT * MARCO * 0.375)                  # Parseval con ventana de Hann: la energía de la banda en dBFS (media cuadrática)
            self.bandas.append(np.stack([db(p[:, a:b].sum(axis=1) * escala) for a, b in self.idx_bandas], axis=1).astype(np.float32))
            q = p[:, self.r20[0]:self.r20[1]] + EPS
            self.planitud20.append((np.exp(np.mean(np.log(q), axis=1)) / np.mean(q, axis=1)).astype(np.float32))
            self.efimeros.append(self._efimeros(p))
        self.cola = s[n * MARCO:]
        # marcos finos (salto de media ventana)
        s = np.concatenate((self.cola_fina, mono))
        paso = FINO // 2
        k = 0
        while k + FINO <= s.size:
            seg = s[k:k + FINO]
            pw = np.abs(np.fft.rfft(seg * self.ventana_fina)) ** 2
            nivel = float(db(np.mean(seg.astype(np.float64) ** 2)))
            t = (self.n_fino * paso + FINO / 2) / SR
            if self.clase_fina_externa is not None:
                cl = int(self.clase_fina_externa[self.n_fino]) if self.n_fino < self.clase_fina_externa.size else 1
            else:
                cl = self._clase_de_t(t)
            if cl is not None:
                self.esp[cl] += pw
                self.n_esp[cl] += 1
                self.clase_por_palabras.append(cl)
            cubo = int(np.clip((nivel + 120) // 5, 0, 23))
            self.cubos[cubo] += pw
            self.n_cubos[cubo] += 1
            escala_fina = 2.0 / (FINO * FINO * 0.375)
            self.graves_fino.append(float(db(pw[self.rg[0]:self.rg[1]].sum() * escala_fina)))       # graves con 5,9 Hz de resolución (en 20 ms se escapan)
            self.medio_fino.append(float(db(pw[self.rm[0]:self.rm[1]].sum() * escala_fina)))
            if (cl == 2 or (cl is None and nivel > -40)) and len(self.f0) < 600 and nivel > -60:
                ac = np.fft.irfft(pw)                                   # autocorrelación = la inversa del espectro de potencia
                i0, i1 = int(SR / 400), int(SR / 70)
                k0 = i0 + int(np.argmax(ac[i0:i1]))
                if ac[k0] > 0.3 * ac[0]:
                    self.f0.append(SR / k0)
            a, b = self.rp
            banda = pw[a:b] + EPS
            self.planitud.append(float(np.exp(np.mean(np.log(banda))) / np.mean(banda)))
            a, b = self.rt
            alto = pw[a:b] + EPS
            self.tonal.append(float(db(alto.max() / np.median(alto))))
            self.nivel_fino.append(nivel)
            self.n_fino += 1
            k += paso
        self.cola_fina = s[k:]

    def _efimeros(self, p):
        """Por marco: picos espectrales (> 9 dB sobre la tendencia local, 300–6000 Hz) que NO estaban en el marco anterior. El ruido musical (lo
        metálico de una mala reducción de ruido) son justo esos picos sueltos que aparecen y desaparecen; un tono real o la música duran."""
        a, b = max(8, self.r20[0]), self.r20[1]                          # (la tendencia usa ±8 bins: desde el bin 8, ~375 Hz)
        L = 10 * np.log10(p[:, a - 8:b + 8] + EPS)
        c = np.cumsum(np.pad(L, ((0, 0), (1, 0))), axis=1)
        tendencia = (c[:, 17:] - c[:, :-17]) / 17.0
        picos = (L[:, 8:8 + tendencia.shape[1]] - tendencia) > 9.0
        vecinos = picos | np.roll(picos, 1, axis=1) | np.roll(picos, -1, axis=1)
        anterior = np.vstack(([self.picos_prev] if self.picos_prev is not None else [np.zeros(picos.shape[1], bool)]) + [vecinos[:-1]])
        self.picos_prev = vecinos[-1]
        return (picos & ~anterior).sum(axis=1).astype(np.int16)

    def resultado(self, umbral_voz=None):
        """Las medidas juntas. Sin palabras ni clase externa, la clase sale del nivel: voz = por encima de `umbral_voz` (por defecto el punto medio
        entre el suelo y el nivel de la voz), silencio = a menos de 6 dB del suelo."""
        rms = np.concatenate(self.rms) if self.rms else np.zeros(0, np.float32)
        bandas = np.concatenate(self.bandas) if self.bandas else np.zeros((0, len(BANDAS)), np.float32)
        nivel_fino = np.asarray(self.nivel_fino, np.float32)
        validos = rms[rms > -100] if rms.size else rms
        suelo_aprox = float(np.percentile(validos, 10)) if validos.size else -100.0
        alto = float(np.percentile(validos, 90)) if validos.size else -100.0
        if self.clase_fina_externa is not None or self.palabras:
            clase_fina = np.asarray(self.clase_por_palabras, np.int8) if self.clase_fina_externa is None else self.clase_fina_externa[:len(self.nivel_fino)]
            esp = {c: self.esp[c] / max(1, self.n_esp[c]) for c in (0, 1, 2)}
            n_esp = dict(self.n_esp)
        else:
            u_voz = umbral_voz if umbral_voz is not None else (suelo_aprox + alto) / 2.0
            clase_fina = np.where(nivel_fino >= u_voz, 2, np.where(nivel_fino <= suelo_aprox + 6.0, 0, 1)).astype(np.int8)
            esp, n_esp = {}, {}
            centros = -120 + 5 * np.arange(24) + 2.5
            for c, sel in ((2, centros >= u_voz), (0, centros <= suelo_aprox + 6.0), (1, (centros > suelo_aprox + 6.0) & (centros < u_voz))):
                n_esp[c] = int(self.n_cubos[sel].sum())
                esp[c] = self.cubos[sel].sum(axis=0) / max(1, n_esp[c])
        # la clase de cada marco de 20 ms (la del marco fino que lo contiene)
        paso = FINO // 2
        t20 = (np.arange(rms.size) * MARCO + MARCO / 2) / SR
        i_fino = np.clip(((t20 * SR - FINO / 2) / paso).round().astype(int), 0, max(0, clase_fina.size - 1))
        clase20 = clase_fina[i_fino] if clase_fina.size else np.ones(rms.size, np.int8)
        l2, r2, lr, n = self.est
        estereo = None
        if n:
            corr = lr / max(np.sqrt(l2 * r2), EPS)
            estereo = {'correlacion': float(corr), 'dif_db': float(db(l2 / n) - db(r2 / n))}
        planitud20 = np.concatenate(self.planitud20) if self.planitud20 else np.zeros(0, np.float32)
        return {'rms_db': rms, 'bandas_db': bandas, 'clase20': clase20, 'planitud20': planitud20, 'palabras': list(self.palabras),
                'graves_fino': np.asarray(self.graves_fino, np.float32), 'medio_fino': np.asarray(self.medio_fino, np.float32),
                'efimeros': np.concatenate(self.efimeros) if self.efimeros else np.zeros(0, np.int16),
                'f0': round(float(np.median(self.f0)), 1) if len(self.f0) >= 10 else None, 'clase_fina': clase_fina, 'nivel_fino': nivel_fino,
                'planitud': np.asarray(self.planitud, np.float32), 'tonal': np.asarray(self.tonal, np.float32), 'espectro': esp, 'n_espectro': n_esp,
                'f_fino': self.f_fino, 'estereo': estereo, 'duracion': self.muestras / SR, 'suelo_aprox': suelo_aprox, 'alto': alto}


def banda_db(espectro, f, a, b):
    """Energía del espectro medio (marcos finos) entre a y b Hz, en dBFS (media cuadrática, Parseval con ventana de Hann)."""
    i, j = np.searchsorted(f, a), max(np.searchsorted(f, a) + 1, np.searchsorted(f, b))
    return float(db(np.sum(espectro[i:j]) * 2.0 / (FINO * FINO * 0.375)))


def tercios(espectro, f, desde=100.0, hasta=10000.0):
    """[(centro, dB)] del espectro medio por tercios de octava."""
    salida = []
    c = desde
    while c <= hasta:
        salida.append((round(c, 1), banda_db(espectro, f, c / 2 ** (1 / 6), c * 2 ** (1 / 6))))
        c *= 2 ** (1 / 3)
    return salida
