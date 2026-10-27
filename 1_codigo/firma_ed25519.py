# CineCaptions · By Cinema Productions
# 1_codigo/firma_ed25519.py — firma Ed25519 (RFC 8032) en Python puro: el programa comprueba que el version.json lo publicó Cinema Productions.
"""
firma_ed25519.py  (v5.52)
-------------------------
Firmar y verificar con Ed25519 sin librerías de fuera (nada de `cryptography`: otro .pyd sin firma que Smart App Control y los
antivirus bloquean). Es la implementación de referencia del RFC 8032 (sección 6), con sus vectores de prueba comprobados.
Lenta comparada con una en C (unos milisegundos por firma), suficiente para el manifiesto de actualizaciones.

  nueva_privada()                      32 bytes al azar (la clave privada; NUNCA en el repositorio: ~/CineCaptions_claves)
  publica(privada)                     los 32 bytes de la clave pública (la que va dentro del programa)
  firmar(privada, mensaje)             64 bytes de firma
  verificar(publica, mensaje, firma)   True/False (nunca lanza con datos raros)
"""
import hashlib
import os

_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_RAIZ_M1 = pow(2, (_P - 1) // 4, _P)          # raíz cuadrada de -1


def _h(m):
    return hashlib.sha512(m).digest()


def _sumar(a, b):                              # puntos en coordenadas extendidas (X, Y, Z, T)
    x1, y1, z1, t1 = a
    x2, y2, z2, t2 = b
    pa = (y1 - x1) * (y2 - x2) % _P
    pb = (y1 + x1) * (y2 + x2) % _P
    pc = t1 * 2 * _D * t2 % _P
    pd = z1 * 2 * z2 % _P
    e, f, g, h = pb - pa, pd - pc, pd + pc, pb + pa
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _por(s, punto):
    q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            q = _sumar(q, punto)
        punto = _sumar(punto, punto)
        s >>= 1
    return q


def _iguales(a, b):
    return (a[0] * b[2] - b[0] * a[2]) % _P == 0 and (a[1] * b[2] - b[1] * a[2]) % _P == 0


def _x_de(y, signo):
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if signo else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P:
        x = x * _RAIZ_M1 % _P
    if (x * x - x2) % _P:
        return None
    if (x & 1) != signo:
        x = _P - x
    return x


_GY = 4 * pow(5, _P - 2, _P) % _P
_GX = _x_de(_GY, 0)
_G = (_GX, _GY, 1, _GX * _GY % _P)


def _comprimir(punto):
    x, y, z, _ = punto
    zi = pow(z, _P - 2, _P)
    x, y = x * zi % _P, y * zi % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, 'little')


def _descomprimir(b):
    if len(b) != 32:
        return None
    y = int.from_bytes(b, 'little')
    signo, y = y >> 255, y & ((1 << 255) - 1)
    x = _x_de(y, signo)
    return None if x is None else (x, y, 1, x * y % _P)


def _expandir(privada):
    h = _h(bytes(privada))
    a = int.from_bytes(h[:32], 'little')
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def nueva_privada():
    return os.urandom(32)


def publica(privada):
    return _comprimir(_por(_expandir(privada)[0], _G))


def firmar(privada, mensaje):
    a, prefijo = _expandir(privada)
    pub = _comprimir(_por(a, _G))
    r = int.from_bytes(_h(prefijo + mensaje), 'little') % _L
    rb = _comprimir(_por(r, _G))
    k = int.from_bytes(_h(rb + pub + mensaje), 'little') % _L
    return rb + int.to_bytes((r + k * a) % _L, 32, 'little')


def verificar(publica_b, mensaje, firma):
    try:
        publica_b, firma = bytes(publica_b), bytes(firma)
        if len(publica_b) != 32 or len(firma) != 64:
            return False
        pa, pr = _descomprimir(publica_b), _descomprimir(firma[:32])
        s = int.from_bytes(firma[32:], 'little')
        if pa is None or pr is None or s >= _L:
            return False
        k = int.from_bytes(_h(firma[:32] + publica_b + bytes(mensaje)), 'little') % _L
        return _iguales(_por(s, _G), _sumar(pr, _por(k, pa)))
    except Exception:
        return False
