# CineCaptions · By Cinema Productions
# 1_codigo/archivos_seguros.py — escritura atómica de JSON/texto (preferencias, marcas, proyectos): un corte o dos hilos ya no dejan archivos a medias.
"""
Antes cada módulo hacía `ruta.write_text(...)`: el archivo se VACÍA primero y se llena después. Un corte de luz, un cierre forzado o
un segundo hilo que leyera en ese instante veía un JSON a medias, lo daba por «no hay nada» y, al guardar encima, borraba todas las
preferencias o las marcas del usuario. Aquí:

  * escribir_texto / escribir_json : escribe en un archivo temporal del MISMO directorio, lo fuerza a disco y lo cambia por el
                                     definitivo de un solo paso (os.replace, atómico). Quien lee ve siempre el archivo viejo
                                     completo o el nuevo completo. Con respaldo=True deja antes una copia «.bak» del anterior.
  * leer_json                      : lee un JSON; si el principal está roto prueba con el «.bak»; si no, devuelve el valor por defecto.
  * mezclar_json                   : lee-modifica-escribe bajo un cerrojo (dos hilos que guardan claves distintas no se pisan) y,
                                     si el archivo existía pero estaba roto, lo aparta como «.roto» en vez de borrarlo en silencio.
"""
import json
import os
import shutil
import threading
import time
from pathlib import Path

_CERROJO = threading.RLock()


def _reemplazar(origen, destino):
    """os.replace con reintentos: en Windows un antivirus, el indexador o un lector pueden tener el archivo abierto un instante."""
    for intento in range(20):
        try:
            os.replace(origen, destino)
            return
        except PermissionError:
            if intento == 19:
                raise
            time.sleep(min(0.08, 0.01 * (intento + 1)))


def escribir_texto(ruta, texto, encoding='utf-8', respaldo=False):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(f'{ruta.name}.{os.getpid()}.{threading.get_ident()}.tmp')
    try:
        with open(tmp, 'w', encoding=encoding) as f:
            f.write(texto)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        if respaldo and ruta.exists():
            try:
                shutil.copy2(ruta, ruta.with_name(ruta.name + '.bak'))
            except OSError:
                pass
        _reemplazar(tmp, ruta)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
    return ruta


def escribir_json(ruta, datos, respaldo=False, **opciones):
    opciones.setdefault('ensure_ascii', False)
    return escribir_texto(ruta, json.dumps(datos, **opciones), respaldo=respaldo)


def _leer(ruta):
    """Lee el JSON; si Windows lo tiene bloqueado justo ahora (otro hilo lo está cambiando) reintenta unos milisegundos."""
    for intento in range(8):
        try:
            return json.loads(Path(ruta).read_text(encoding='utf-8'))
        except PermissionError:
            if intento == 7:
                raise
            time.sleep(0.01 * (intento + 1))


def leer_json(ruta, defecto=None, con_respaldo=False):
    ruta = Path(ruta)
    try:
        return _leer(ruta)
    except Exception:
        if con_respaldo:
            try:
                return _leer(ruta.with_name(ruta.name + '.bak'))
            except Exception:
                pass
        return defecto


class _JsonPorPartes:
    """El decodificador de leer_json_cediendo. Lee de una VENTANA de texto que se va rellenando con los trozos siguientes (nunca hay
    que juntar el archivo entero: 10 MB de texto eran ~9 ms más sin soltar el GIL); los contenedores de los `niveles` primeros niveles
    van elemento a elemento y lo de dentro de golpe (en C). Antes de cada elemento hay al menos MARGEN de texto por delante; si un
    valor no cabe, la ventana crece hasta que quepa."""
    MARGEN = 1 << 17

    def __init__(self, trozos, cada_s, niveles=1):
        import json.decoder as jd
        self.trozos = iter(trozos)
        self.s = ''
        self.fin = False
        self.dec = json.JSONDecoder()
        self.blanco = jd.WHITESPACE.match
        self.cadena = jd.scanstring
        self.cada = cada_s
        self.NIVELES = niveles
        self.t = time.perf_counter()

    def _ceder(self):
        if time.perf_counter() - self.t >= self.cada:
            time.sleep(0)                                   # suelta el GIL: la interfaz pinta su cuadro
            self.t = time.perf_counter()

    def _ampliar(self, i):
        """Tira lo ya leído (hasta i) y añade el trozo siguiente; la posición pasa a 0. False si ya no queda archivo."""
        try:
            sig = next(self.trozos)
        except StopIteration:
            self.fin = True
            return False
        self.s = self.s[i:] + sig
        return True

    def _asegurar(self, i):
        while not self.fin and len(self.s) - i < self.MARGEN:
            if self._ampliar(i):
                i = 0
        return i

    def _sig(self, i):
        """La posición del siguiente carácter que no es espacio (con la ventana rellena)."""
        i = self._asegurar(i)
        return self.blanco(self.s, i).end()

    def _valor(self, i, nivel):
        i = self._sig(i)
        c = self.s[i:i + 1]
        if nivel < self.NIVELES and c == '[':
            return self._lista(i + 1, nivel + 1)
        if nivel < self.NIVELES and c == '{':
            return self._objeto(i + 1, nivel + 1)
        while True:
            try:
                v, fin = self.dec.raw_decode(self.s, i)
                break
            except ValueError:
                if self.fin:
                    raise
                if self._ampliar(i):                        # el valor no cabía en la ventana: más texto y otra vez
                    i = 0
        self._ceder()
        return v, fin

    def _lista(self, i, nivel):
        salida = []
        i = self._sig(i)
        if self.s[i:i + 1] == ']':
            return salida, i + 1
        while True:
            v, i = self._valor(i, nivel)
            salida.append(v)
            i = self._sig(i)
            c = self.s[i:i + 1]
            if c == ',':
                i += 1
            elif c == ']':
                return salida, i + 1
            else:
                raise ValueError('JSON: se esperaba «,» o «]»')

    def _objeto(self, i, nivel):
        salida = {}
        i = self._sig(i)
        if self.s[i:i + 1] == '}':
            return salida, i + 1
        while True:
            i = self._sig(i)
            if self.s[i:i + 1] != '"':
                raise ValueError('JSON: se esperaba una clave')
            clave, i = self.cadena(self.s, i + 1)
            i = self._sig(i)
            if self.s[i:i + 1] != ':':
                raise ValueError('JSON: se esperaba «:»')
            v, i = self._valor(i + 1, nivel)
            salida[clave] = v
            i = self._sig(i)
            c = self.s[i:i + 1]
            if c == ',':
                i += 1
            elif c == '}':
                return salida, i + 1
            else:
                raise ValueError('JSON: se esperaba «,» o «}»')

    def leer(self):
        v, i = self._valor(0, 0)
        while True:
            i = self.blanco(self.s, i).end()
            if i != len(self.s):
                raise ValueError('JSON: sobra texto al final')
            if not self._ampliar(i):
                return v
            i = 0


def _trozos_de_texto(datos, tam=1 << 20):
    """Los bytes UTF-8 convertidos a texto de 1 MB en 1 MB, soltando el GIL entre trozo y trozo."""
    import codecs
    dec = codecs.getincrementaldecoder('utf-8-sig')()
    for i in range(0, len(datos), tam):
        yield dec.decode(datos[i:i + tam])
        time.sleep(0)
    yield dec.decode(b'', final=True)


def leer_json_cediendo(ruta, niveles=1, cada_s=0.002):
    """v5.49 (el usuario: «revisa para que no haya tirones jamás»): un JSON GRANDE leído en un hilo sin parar la interfaz. json.loads es
    C de principio a fin y no suelta el GIL: el catálogo de emojis (10 MB) eran ~115 ms seguidos y la caché de picos (3,5 MB) ~45 ms con
    Inicio animándose, un tirón aunque fuera en un hilo. Aquí el texto se convierte por trozos de 1 MB y la lista o el diccionario de
    arriba (`niveles` = cuántos niveles se parten: 2 si lo grande es una lista dentro del diccionario) se decodifica elemento a elemento,
    soltando el GIL cada ~2 ms. Mismo resultado que json.loads; un JSON roto lanza ValueError."""
    return _JsonPorPartes(_trozos_de_texto(Path(ruta).read_bytes()), cada_s, niveles).leer()


def mezclar_json(ruta, cambios, **opciones):
    """Mezcla `cambios` en el diccionario guardado (sin tocar el resto de claves) y lo escribe de forma atómica. True si se guardó."""
    ruta = Path(ruta)
    with _CERROJO:
        actual = None
        try:
            actual = _leer(ruta)
        except FileNotFoundError:
            actual = {}
        except Exception:
            # existía pero no se pudo leer: se aparta (para poder recuperarlo) en vez de pisarlo con un diccionario casi vacío
            try:
                shutil.copy2(ruta, ruta.with_name(ruta.name + '.roto'))
            except OSError:
                pass
            actual = {}
        if not isinstance(actual, dict):
            actual = {}
        actual.update(cambios)
        try:
            escribir_json(ruta, actual, **opciones)
            return True
        except OSError:
            return False
