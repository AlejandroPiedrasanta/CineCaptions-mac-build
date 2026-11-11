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


def ruta_video_captions(nombre):
    """v5.5.9: el mismo ejemplo SOLO con los captions (sin la Edición PRO): la píldora «Solo captions» de la tarjeta."""
    return _archivo(nombre, '_captions.mp4')


def ruta_poster_captions(nombre):
    return _archivo(nombre, '_captions.jpg')


# v5.83 (el usuario: «utiliza todos los hilos y memoria para que CineCaptions sea fluido y rápido»): imágenes decodificadas de antemano, en
# varios hilos, y guardadas en memoria. QImage suelta el GIL al decodificar (medido: 240 JPEG en 224 ms con 4 hilos y el hilo de la interfaz
# sin un solo hueco de más de 1,3 ms); antes, los ~100 pósters de las tarjetas de Efectos se decodificaban al armar la página, en el hilo de
# la interfaz (la primera visita a Efectos tardaba ~0,3 s en verse).
_IMAGENES = {}                                         # ruta (str) -> QImage
_IMAGENES_CERROJO = threading.Lock()


def imagen_de(ruta, guardar=True):
    """La QImage de `ruta`: de la memoria si ya la decodificó precargar(); si no, ahora (y se guarda, salvo guardar=False: archivos del
    usuario que pueden rehacerse con el mismo nombre, como la foto de un estilo de «Crea tu estilo»). La misma imagen que QImage(ruta)."""
    from PySide6.QtGui import QImage
    clave = str(ruta)
    with _IMAGENES_CERROJO:
        img = _IMAGENES.get(clave)
    if img is None:
        img = QImage(clave)
        if guardar and not img.isNull():
            with _IMAGENES_CERROJO:
                img = _IMAGENES.setdefault(clave, img)
    return img


def precargar(carpetas, patron='*.jpg', hilos=None):
    """Decodifica en varios hilos de prioridad baja las imágenes (`patron`) de esas carpetas y las guarda en memoria para `imagen_de`.
    No espera: lista y decodifica fuera del hilo de la interfaz."""
    def repartir():
        import os
        rutas = []
        for c in carpetas:
            try:
                rutas += [str(p) for p in sorted(Path(c).glob(patron))]
            except OSError:
                pass
        with _IMAGENES_CERROJO:
            rutas = [r for r in rutas if r not in _IMAGENES]
        n = max(1, min(len(rutas), hilos or max(2, min(8, (os.cpu_count() or 4) // 2))))
        for i in range(n):
            threading.Thread(target=_decodificar, args=(rutas[i::n],), name='precarga-imagenes', daemon=True).start()
    threading.Thread(target=repartir, name='precarga-imagenes', daemon=True).start()


def _decodificar(rutas):
    from PySide6.QtGui import QImage
    try:
        import qt_kit
        qt_kit.prioridad_hilo(-1)                      # (por debajo del hilo de la interfaz)
    except Exception:
        pass
    for r in rutas:
        img = QImage(r)
        if not img.isNull():
            with _IMAGENES_CERROJO:
                _IMAGENES.setdefault(r, img)


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
        self.vueltas = 0              # v5.75: vueltas enteras desde arrancar() («Así queda» de «Crea tu estilo» pasa al siguiente principal)
        self.tam = None               # v5.75: (ancho, alto) en píxeles: el cuadro se escala AQUÍ (FFmpeg, en el hilo) y la tarjeta solo lo copia
        self.posicion = 0.0           # v5.76: segundos del cuadro actual y duración del clip (la barra de avance de los tutoriales)
        self.duracion = 0.0
        self._en_pausa = threading.Event()

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
        self._en_pausa.clear()
        self._img = None
        self.vueltas = 0
        self.posicion = 0.0
        self._hilo = threading.Thread(target=self._correr, args=(self._parar,), name='vista-slider', daemon=True)
        self._hilo.start()

    def parar(self):
        self._parar.set()

    def pausar(self, si=True):
        """v5.76 (tutoriales): congela el cuadro actual (el hilo sigue vivo y espera); pausar(False) sigue desde ahí."""
        if si:
            self._en_pausa.set()
        else:
            self._en_pausa.clear()

    @property
    def en_pausa(self):
        return self._en_pausa.is_set()

    def _correr(self, parar):
        try:
            import av
            import numpy as np
            from PySide6.QtGui import QImage
            # v5.46: decodificador de UN hilo y el archivo abierto una sola vez (en bucle se rebobina). Con thread_type='AUTO' cada
            # tarjeta creaba un hilo de FFmpeg por núcleo y, al abrir/cerrar el mp4 (cada vuelta y al salir de la página), Python
            # quedaba parado 50-90 ms: la vuelta a Inicio desde Efectos se trababa. Son clips pequeños: un hilo sobra.
            with av.open(self.ruta) as contenedor:
                flujo = contenedor.streams.video[0]
                flujo.thread_type = 'NONE'
                flujo.codec_context.thread_count = 1
                try:
                    if flujo.duration is not None:
                        self.duracion = float(flujo.duration * flujo.time_base)
                    elif contenedor.duration:
                        self.duracion = float(contenedor.duration) / 1e6
                except Exception:
                    pass
                primera = True
                while not parar.is_set():
                    if not primera:
                        contenedor.seek(0, stream=flujo)
                    primera = False
                    t0 = time.perf_counter()
                    for cuadro in contenedor.decode(flujo):
                        if parar.is_set():
                            return
                        if self._en_pausa.is_set():                    # v5.76: en pausa el reloj no corre (al seguir, sigue desde aquí)
                            t_p = time.perf_counter()
                            while self._en_pausa.is_set():
                                if parar.wait(0.05):
                                    return
                            t0 += time.perf_counter() - t_p
                        if cuadro.pts is not None:
                            t = float(cuadro.pts * flujo.time_base)
                            self.posicion = t
                            espera = t0 + t - time.perf_counter()
                            if espera > 0:
                                if parar.wait(espera):
                                    return
                            elif espera < -0.25:                      # el equipo se atrasó: se reajusta el reloj, sin acelerar para alcanzarlo
                                t0 = time.perf_counter() - t
                        tam = self.tam
                        if tam and tam[0] > 8 and tam[1] > 8:
                            # ancho MÚLTIPLO DE 16: PyAV 19 a 290 o 292 px de ancho dejaba basura en las primeras columnas cada 13 filas
                            # (rayitas en el borde de la tarjeta); quien pinta encaja la imagen en su rectángulo (1-2 px de diferencia)
                            ancho_d = max(16, int(round(tam[0] / 16.0)) * 16)
                            a = np.ascontiguousarray(cuadro.to_ndarray(format='bgra', width=ancho_d, height=int(tam[1]), interpolation='AREA'))
                        else:
                            a = np.ascontiguousarray(cuadro.to_ndarray(format='bgra'))
                        alto, ancho = a.shape[0], a.shape[1]
                        self._img = QImage(a.data, ancho, alto, ancho * 4, QImage.Format.Format_RGB32).copy()
                    self.vueltas += 1
                    if self._pausa > 0 and parar.wait(self._pausa):
                        return
        except Exception:
            self.fallo = True
