# CineCaptions · By Cinema Productions
# 1_codigo/vistas_slider.py — los VIDEOS que se reproducen dentro de las tarjetas del slider «Pack de estilos» (captions reales de Resolve, no imágenes fijas).
"""
vistas_slider.py  (v5.4.5)
--------------------------
Cada pack de fábrica trae un video corto de ejemplo con SUS captions ya puestos por Resolve (hacer_vista_slider.py: el mismo GO real, render de la línea de
tiempo y reducción a mp4 sin audio) en 2_recursos/vistas_slider/<pack>.mp4, más un `<pack>.jpg` (el fotograma que se ve cuando la tarjeta no está al centro).

    ruta_video(nombre) / ruta_poster(nombre)    el archivo del pack o None
    Reproductor(ruta)                           decodifica el mp4 con PyAV en UN hilo (a su ritmo real, en bucle) y deja el último cuadro como QImage:
        .arrancar()  empieza desde el principio     .parar()  detiene el hilo     .imagen()  el cuadro actual (o None)

PyAV ya viaja en el programa (audio, transcripción), así que no hace falta QtMultimedia. El hilo solo vive mientras la tarjeta está al centro y el
slider se ve; nunca toca la interfaz: el carrusel pide `imagen()` al pintar.
"""
import threading
import time
from pathlib import Path


def _carpeta():
    try:
        import instalador_scripts
        return Path(instalador_scripts.BASE_RECURSOS) / 'vistas_slider'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'vistas_slider'


def _archivo(nombre, ext):
    try:
        ruta = _carpeta() / f'{nombre}{ext}'
        return ruta if ruta.is_file() and ruta.stat().st_size > 1000 else None
    except Exception:
        return None


def ruta_video(nombre):
    return _archivo(nombre, '.mp4')


def ruta_poster(nombre):
    return _archivo(nombre, '.jpg')


class Reproductor:
    """Reproduce un mp4 en bucle en un hilo y guarda el cuadro actual (QImage RGB32). Sin audio."""
    PAUSA_BUCLE_S = 0.8

    def __init__(self, ruta, pausa_s=None):
        self.ruta = str(ruta)
        self._pausa = self.PAUSA_BUCLE_S if pausa_s is None else float(pausa_s)           # «Crea tu estilo»: 0 = el clip da la vuelta sin quedarse parado
        self._img = None
        self._hilo = None
        self._parar = threading.Event()
        self.fallo = False

    def imagen(self):
        return self._img

    @property
    def activo(self):
        return self._hilo is not None and self._hilo.is_alive() and not self._parar.is_set()

    def arrancar(self):
        """Empieza desde el principio (si ya estaba sonando no hace nada)."""
        if self.activo or self.fallo:
            return
        self._parar = threading.Event()
        self._img = None
        self._hilo = threading.Thread(target=self._correr, args=(self._parar,), name='vista-slider', daemon=True)
        self._hilo.start()

    def parar(self):
        self._parar.set()

    def _correr(self, parar):
        try:
            import av
            import numpy as np
            from PySide6.QtGui import QImage
            while not parar.is_set():
                with av.open(self.ruta) as contenedor:
                    flujo = contenedor.streams.video[0]
                    flujo.thread_type = 'AUTO'
                    t0 = time.perf_counter()
                    for cuadro in contenedor.decode(flujo):
                        if parar.is_set():
                            return
                        if cuadro.pts is not None:
                            t = float(cuadro.pts * flujo.time_base)
                            espera = t0 + t - time.perf_counter()
                            if espera > 0:
                                if parar.wait(espera):
                                    return
                            elif espera < -0.25:                      # el equipo se atrasó: se reajusta el reloj, sin acelerar para alcanzarlo
                                t0 = time.perf_counter() - t
                        a = np.ascontiguousarray(cuadro.to_ndarray(format='bgra'))
                        alto, ancho = a.shape[0], a.shape[1]
                        self._img = QImage(a.data, ancho, alto, ancho * 4, QImage.Format.Format_RGB32).copy()
                if self._pausa > 0 and parar.wait(self._pausa):
                    return
                if parar.is_set():
                    return
        except Exception:
            self.fallo = True
