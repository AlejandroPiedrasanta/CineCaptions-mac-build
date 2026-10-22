# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_nr.py — «AI Sound Director»: reducción de ruido de la voz (numpy, sin dependencias nuevas), natural antes que cero ruido.
"""
El `afftdn` de ffmpeg (el que trae PyAV) casi no baja el ruido real de un video (medido: < 1 dB con ruido rosa a −38 dBFS, ni con perfil por bandas
ni muestreándolo), así que la reducción va aquí:

    STFT de 1024 muestras (21 ms) con salto de 512 y ventana raíz de Hann (reconstrucción perfecta)
    ruido   seguido por MÍNIMOS de la potencia suavizada en ventanas de ~1,5 s (Martin): funciona aunque casi no haya silencios entre palabras
    ganancia Wiener con SNR a priori «decision-directed» (Ephraim-Malah), suavizada en frecuencia y con caída lenta en el tiempo (sin ruido musical)
    TOPE    la ganancia nunca baja de −`reduccion_db` (6–15 dB según el SNR): un poco de ruido natural antes que una voz metálica

Por trozos (canales, n) a 48 kHz, la misma ganancia para todos los canales; la salida dura EXACTAMENTE lo mismo que la entrada y sin desfase.
"""
import numpy as np

N, H = 1024, 512
U, V = 8, 18                   # mínimos: 8 subventanas de 18 marcos (≈ 1,5 s)
SESGO = 2.5                    # el mínimo de una potencia suavizada queda por debajo de la media del ruido (×0,65 medido con ruido rosa: probar_director_sonido)
ALFA_S = 0.85                  # suavizado de la potencia para los mínimos
ALFA_DD = 0.98                 # «decision-directed»
XI_MIN = 10 ** (-25 / 10)


class ReductorEspectral:
    def __init__(self, canales, reduccion_db=10.0, alfa_dd=ALFA_DD, suavizar=True):
        self.c = int(canales)
        self.w = np.sqrt(np.hanning(N + 1)[:N]).astype(np.float64)       # raíz de Hann periódica: análisis × síntesis = Hann (suma 1 con 50 %)
        self.gmin = 10 ** (-float(reduccion_db) / 20.0)
        self.alfa_dd = float(alfa_dd)
        self.suavizar = bool(suavizar)
        self.entrada = np.zeros((self.c, H))                            # H ceros delante: el primer marco también se reconstruye entero
        self.ola = np.zeros((self.c, N))
        self.n_in = 0
        self.n_out = 0
        self.descartar = H
        k = N // 2 + 1
        self.ps = None
        self.sub_min = np.full(k, np.inf)
        self.minimos = []
        self.n_sub = 0
        self.g_prev = np.ones(k)
        self.p_prev = np.zeros(k)
        self.g_suave = np.ones(k)
        self.ruido = None
        self.reduccion_media = []

    def _ruido(self, p):
        """Mínimos de la potencia suavizada en las últimas U·V tramas (×SESGO)."""
        self.ps = p.copy() if self.ps is None else ALFA_S * self.ps + (1 - ALFA_S) * p
        self.sub_min = np.minimum(self.sub_min, self.ps)
        self.n_sub += 1
        if self.n_sub >= V:
            self.minimos.append(self.sub_min)
            self.minimos = self.minimos[-U:]
            self.sub_min = np.full_like(self.ps, np.inf)
            self.n_sub = 0
        actual = np.min(np.vstack(self.minimos + [self.sub_min]), axis=0)
        return np.maximum(actual * SESGO, 1e-14)

    def _marcos(self, final=False):
        x = self.entrada
        if x.shape[1] < N:
            return np.zeros((self.c, 0))
        n_marcos = (x.shape[1] - N) // H + 1
        idx = np.arange(N)[None, :] + H * np.arange(n_marcos)[:, None]
        X = np.fft.rfft(x[:, idx] * self.w, axis=2)                     # (canales, marcos, bins)
        P = np.mean(np.abs(X) ** 2, axis=0)                              # potencia común (la ganancia es la misma para todos los canales)
        G = np.empty_like(P)
        for t in range(n_marcos):
            p = P[t]
            r = self._ruido(p)
            gamma = p / r
            xi = self.alfa_dd * (self.g_prev ** 2) * self.p_prev / r + (1 - self.alfa_dd) * np.maximum(gamma - 1.0, 0.0)
            xi = np.maximum(xi, XI_MIN)
            g = xi / (1.0 + xi)
            if self.suavizar:
                g = np.convolve(g, (0.25, 0.5, 0.25), 'same')
                g = np.where(g > self.g_suave, g, 0.6 * self.g_suave + 0.4 * g)    # sube al momento (la voz entra), baja despacio (sin parpadeo)
            g = np.maximum(g, self.gmin)
            self.g_suave = g
            self.g_prev, self.p_prev = g, p
            G[t] = g
        if n_marcos:
            self.reduccion_media.append(float(np.mean(G)))
        y = np.fft.irfft(X * G[None, :, :], n=N, axis=2) * self.w        # (canales, marcos, N)
        largo = H * (n_marcos - 1) + N
        ola = np.zeros((self.c, max(largo, self.ola.shape[1])))
        ola[:, :self.ola.shape[1]] += self.ola
        for t in range(n_marcos):
            ola[:, t * H:t * H + N] += y[:, t]
        listo = ola[:, :n_marcos * H]
        self.ola = ola[:, n_marcos * H:n_marcos * H + (N - H)]
        self.entrada = x[:, n_marcos * H:]
        return listo

    def _entregar(self, y, final=False):
        if self.descartar:
            q = min(self.descartar, y.shape[1])
            y = y[:, q:]
            self.descartar -= q
        if final:
            y = y[:, :max(0, self.n_in - self.n_out)]
        self.n_out += y.shape[1]
        return y.astype(np.float32)

    def empujar(self, x):
        x = np.asarray(x, dtype=np.float64)
        self.n_in += x.shape[1]
        self.entrada = np.concatenate((self.entrada, x), axis=1)
        return self._entregar(self._marcos())

    def terminar(self):
        self.entrada = np.concatenate((self.entrada, np.zeros((self.c, N + H))), axis=1)
        y = self._marcos(final=True)
        return self._entregar(y, final=True)

    def reduccion_aplicada_db(self):
        """Lo que bajó de media (dB, solo informativo)."""
        return round(float(-20 * np.log10(max(1e-6, np.mean(self.reduccion_media)))), 2) if self.reduccion_media else 0.0
