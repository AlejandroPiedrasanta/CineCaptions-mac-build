# CineCaptions · By Cinema Productions
# 1_codigo/premiere_textos.py — v5.85: GO en Premiere Pro con los TEXTOS en la línea de tiempo (no un video de captions): cada palabra o línea del estilo, un clip de texto editable; lo demás (cajas, aros, rayas, emojis), PNG.
"""
premiere_textos.py  (v5.85)
---------------------------
Pedido del usuario (2026-11-12): «me pones el video de los captions y no quiero; quiero los textos que se vayan armando en la línea de tiempo»,
«tiene que funcionar con sus textos y todo así como DaVinci Resolve».

Hasta la 5.84 GO dibujaba los captions sobre transparente (render_sin_resolve.renderizar_capa, ProRes 4444) y el panel los ponía en V2 como un
solo video. Ahora sale la MISMA composición (render_sin_resolve.preparar: posiciones, tiempos, letras y colores de cada estilo), pero en piezas:

  · cada texto (render_temas.texto deja su ficha en `espec`; el Estilo 5, una ficha por línea) → un clip de texto de Premiere con su letra
    (nombre PostScript; Arial Bold si no está instalada), tamaño, color (el de la mitad si es un degradado), contorno, sombra (o brillo/halo
    como sombra sin desplazar), espaciado, giro, entrada y salida. Cada uno lleva SU plantilla (`mogrt_de_texto`: la «Basic Title» del
    Premiere del usuario con el texto y el estilo escritos dentro), porque en Premiere 26 escribir el «Texto de origen» por ExtendScript no
    se dibuja. Se edita en Premiere como cualquier texto (Gráficos esenciales).
  · lo que no es texto (la caja de las pegatinas, aros, rayas, trazos, la caja del «select», el bloque del Estilo 5, los emojis) → PNG con alfa
    en su sitio (Movimiento), en las pistas de debajo de los textos.

Cada tipo va en carriles que no se pisan (`pista`: 0, 1, 2…): el panel (colocar.jsx) las pone en V2… (imágenes) y encima (textos).
Si el panel no puede poner textos, GO vuelve a la capa de siempre (script principal, `_go_colocar_premiere`).
"""
import hashlib
import math
import struct
import time
from pathlib import Path

import numpy as np
from PIL import Image

CARPETA_SUFIJO = ' (CineCaptions elementos)'
HUECO_S = 0.001                  # dos clips del mismo carril no pueden tocarse


def _nombre_ps(ruta):
    """El nombre PostScript (name ID 6) de un .ttf/.otf/.ttc (la primera cara): lo que Premiere guarda en mFontName."""
    try:
        with open(ruta, 'rb') as f:
            off = 0
            if f.read(4) == b'ttcf':
                f.seek(12)
                off, = struct.unpack('>I', f.read(4))
            f.seek(off + 4)
            n, = struct.unpack('>H', f.read(2))
            f.seek(off + 12)
            tabla = None
            for _ in range(min(n, 512)):
                etq, _c, ini, largo = struct.unpack('>4sIII', f.read(16))
                if etq == b'name':
                    tabla = (ini, largo)
                    break
            if not tabla:
                return None
            f.seek(tabla[0])
            d = f.read(tabla[1])
        _fmt, cuantos, textos = struct.unpack('>HHH', d[:6])
        mejor = None
        for i in range(cuantos):
            pid, _eid, lid, nid, largo, desde = struct.unpack('>HHHHHH', d[6 + 12 * i:18 + 12 * i])
            if nid != 6:
                continue
            crudo = d[textos + desde:textos + desde + largo]
            txt = crudo.decode('utf-16-be', 'ignore') if pid in (0, 3) else crudo.decode('latin-1', 'ignore')
            txt = txt.replace('\x00', '').strip()
            if txt and (mejor is None or (pid == 3 and lid == 1033)):
                mejor = txt
        return mejor
    except Exception:
        return None


_FUENTES = {}


def fuente_de(par):
    """(ruta, nombre PostScript) de una tipografía (familia, estilo), con caché. Si no está en el sistema y CineCaptions la trae, la instala
    (Premiere solo dibuja letras instaladas)."""
    par = (str(par[0]), str(par[1]) if len(par) > 1 else 'Regular')
    if par not in _FUENTES:
        import fuentes_sistema
        try:
            if not fuentes_sistema.esta_en_el_sistema(par[0], par[1], exacto=True):
                import instalar_fuentes
                instalar_fuentes.instalar_faltantes([par])
        except Exception:
            pass
        ruta = None
        try:
            ruta = fuentes_sistema.ruta_de_fuente(par[0], par[1])
        except Exception:
            ruta = None
        ps = _nombre_ps(ruta) if ruta else None
        if ruta and ps and not _registrada(par):
            # (Windows no la tiene registrada o la entrada está rota: Premiere no la encuentra y para con «Resolver fuentes»): se instala de
            # nuevo; si Premiere ya estaba abierto no la verá hasta reiniciarlo (_la_ve_premiere) y esta vez va Arial
            try:
                import instalar_fuentes
                instalar_fuentes.instalar([Path(ruta)])
                _CARAS_REGISTRADAS.clear()
            except Exception:
                pass
            if not _registrada(par):
                ps = None
        # sin la letra en el sistema, Arial Bold (está en todo Windows y Mac): con una letra que falta Premiere para con «Resolver fuentes»
        _FUENTES[par] = (str(ruta), ps) if (ruta and ps) else (None, LETRA_DE_RESPALDO)
    ruta, ps = _FUENTES[par]
    if ruta and not _la_ve_premiere(par, ruta, ps):
        _SIN_VER.add('%s %s' % par)
        return (None, LETRA_DE_RESPALDO)
    return ruta, ps


_PREMIERE_DESDE = [None]
_PREMIERE_CORRE = [False]        # ¿Premiere abierto al preparar este GO? (si no, GO lo abre después y verá lo que se cargue ahora)
_SIN_VER = set()                 # las letras de este GO que están instaladas pero el Premiere abierto aún no ve (reiniciarlo)
_FAMILIAS = []                   # las familias de letras CARGADAS en la sesión de Windows (GDI), una vez por GO


def _familias_sesion():
    """v5.87, Windows: los nombres (normalizados) de las familias de letras que la sesión tiene CARGADAS ahora (EnumFontFamiliesExW), que
    son las que ve Premiere. None si no se puede saber (fuera de Windows o sin GDI): entonces se da todo por bueno."""
    import sys
    if sys.platform != 'win32':
        return None
    if _FAMILIAS:
        return _FAMILIAS[0]
    try:
        import ctypes
        from ctypes import wintypes
        import fuentes_sistema as FS

        class LOGFONTW(ctypes.Structure):
            _fields_ = [('lfHeight', wintypes.LONG), ('lfWidth', wintypes.LONG), ('lfEscapement', wintypes.LONG),
                        ('lfOrientation', wintypes.LONG), ('lfWeight', wintypes.LONG), ('lfItalic', wintypes.BYTE),
                        ('lfUnderline', wintypes.BYTE), ('lfStrikeOut', wintypes.BYTE), ('lfCharSet', wintypes.BYTE),
                        ('lfOutPrecision', wintypes.BYTE), ('lfClipPrecision', wintypes.BYTE), ('lfQuality', wintypes.BYTE),
                        ('lfPitchAndFamily', wintypes.BYTE), ('lfFaceName', wintypes.WCHAR * 32)]
        PROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.POINTER(LOGFONTW), ctypes.c_void_p, wintypes.DWORD, wintypes.LPARAM)
        nombres = set()

        def una(plf, _ptm, _tipo, _lp):
            nombres.add(FS.normalizar(plf.contents.lfFaceName.lstrip('@')))
            return 1
        user32, gdi32 = ctypes.WinDLL('user32'), ctypes.WinDLL('gdi32')
        user32.GetDC.restype = wintypes.HDC
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        gdi32.EnumFontFamiliesExW.argtypes = [wintypes.HDC, ctypes.POINTER(LOGFONTW), PROC, wintypes.LPARAM, wintypes.DWORD]
        hdc = user32.GetDC(None)
        try:
            lf = LOGFONTW()
            lf.lfCharSet = 1                     # DEFAULT_CHARSET: todas
            gdi32.EnumFontFamiliesExW(hdc, ctypes.byref(lf), PROC(una), 0, 0)
        finally:
            user32.ReleaseDC(None, hdc)
    except Exception:
        return None
    if not nombres:
        return None
    _FAMILIAS.append(nombres)
    return nombres


def _cargar_en_la_sesion(ruta):
    """Carga ese archivo de letra en la sesión de Windows (lo mismo que hace instalarla) y avisa a los programas. True si Windows lo aceptó."""
    try:
        import ctypes
        from ctypes import wintypes
        gdi32 = ctypes.WinDLL('gdi32')
        gdi32.AddFontResourceExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
        if gdi32.AddFontResourceExW(str(ruta), 0, None) <= 0:
            return False
        ctypes.WinDLL('user32').PostMessageW(0xFFFF, 0x001D, 0, 0)          # WM_FONTCHANGE a todas las ventanas
        _FAMILIAS.clear()
        return True
    except Exception:
        return False


def _en_la_sesion(par, ruta):
    """v5.87 (Estilo 6 en el equipo del autor: «Instrument Serif» registrada y su archivo en su sitio, pero Windows NO la tenía cargada —ni
    GDI ni Premiere la veían— y Premiere la cambiaba EN SILENCIO por una sin serifa más ancha: las palabras se montaban). ¿Está la familia
    cargada en la sesión? Si no y Premiere está cerrado, se carga ahora (GO lo abre después y la verá)."""
    familias = _familias_sesion()
    if familias is None:
        return True
    import fuentes_sistema as FS
    fam = FS.normalizar(str(par[0]))

    def esta(nombres):                           # («poppins», «poppinsextrabold», «inter24pt24pt»: GDI pone el estilo en el nombre)
        return any(n.startswith(fam) for n in nombres)
    if esta(familias):
        return True
    cargada = bool(ruta) and _cargar_en_la_sesion(ruta)   # (también con Premiere abierto: así, al reiniciarlo, ya la tiene)
    if _PREMIERE_CORRE[0] or not cargada:
        return False
    return esta(_familias_sesion() or set())


def _premiere_abierto_desde():
    """v5.87: desde cuándo (segundos epoch) corre el Premiere conectado (su panel carga al arrancar y lo dice en el latido: «inicio»). None si
    no hay ninguno conectado (GO lo abre DESPUÉS de preparar las letras: las verá todas) o el panel es anterior (no lo dice)."""
    try:
        import premiere
        if not premiere.panel_vivo():
            return None
        d = premiere.latido() or {}
        return float(d['inicio']) / 1000.0 if d.get('inicio') else None
    except Exception:
        return None


def _la_ve_premiere(par, ruta, ps=None):
    """v5.87: una letra instalada DESPUÉS de abrir Premiere no la ve hasta reiniciarlo (Windows y Mac): Premiere pararía con «Resolver
    fuentes». Se mira la fecha del archivo instalado (la copia del usuario o la del sistema) contra el arranque del Premiere conectado.
    Y que esté CARGADA en la sesión de Windows (`_en_la_sesion`): una registrada que Windows no cargó Premiere no la tiene y la cambia
    en silencio por otra más ancha; con Premiere cerrado se carga ahora (GO lo abre después), con Premiere abierto esta vez va Arial."""
    if ps and ps != LETRA_DE_RESPALDO and not _en_la_sesion(par, ruta):
        return False
    desde = _PREMIERE_DESDE[0]
    if not desde:
        return True
    try:
        import instalar_fuentes
        candidatos = [Path(ruta)]
        dest = instalar_fuentes.carpeta_destino()
        if dest is not None:
            candidatos.insert(0, dest / Path(ruta).name)
        for f in candidatos:
            if f.is_file():
                return f.stat().st_mtime <= desde
    except Exception:
        pass
    return True


_CARAS_REGISTRADAS = []


def _caras_registradas():
    """Windows: las caras («familia estilo», normalizadas) de las letras que el registro conoce Y cuyo archivo existe (HKCU y HKLM).
    Se lee una vez por proceso (se vacía tras instalar)."""
    if _CARAS_REGISTRADAS:
        return _CARAS_REGISTRADAS[0]
    import os
    import winreg
    import fuentes_sistema as FS
    caras = set()
    carpetas = {winreg.HKEY_CURRENT_USER: Path(os.environ.get('LOCALAPPDATA') or '') / 'Microsoft' / 'Windows' / 'Fonts',
                winreg.HKEY_LOCAL_MACHINE: Path(os.environ.get('WINDIR') or r'C:\Windows') / 'Fonts'}
    for raiz, carpeta in carpetas.items():
        try:
            with winreg.OpenKey(raiz, r'Software\Microsoft\Windows NT\CurrentVersion\Fonts') as k:
                i = 0
                while True:
                    try:
                        _n, valor, _t = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    i += 1
                    archivo = Path(str(valor))
                    archivo = archivo if archivo.is_absolute() else carpeta / archivo
                    if not archivo.is_file():
                        continue
                    for fam16, est17, fam1, est2, completo in FS.caras_de(archivo):
                        for f, e in ((fam16, est17), (fam1, est2)):
                            if f:
                                caras.add(FS.normalizar(f'{f} {e or "Regular"}'))
                        if completo:
                            caras.add(FS.normalizar(completo))
        except OSError:
            continue
    _CARAS_REGISTRADAS.append(caras)
    return caras


def _registrada(par):
    """Windows: ¿sabe el sistema que existe esa letra? Hace falta una entrada del registro que apunte a un archivo que exista con esa cara.
    Visto en el equipo del autor: entradas a carpetas temporales ya borradas y archivos en Fonts sin entrada; Premiere no las encuentra y
    para con «Resolver fuentes». Fuera de Windows (o si no se puede mirar), True."""
    import sys
    if sys.platform != 'win32':
        return True
    try:
        import fuentes_sistema as FS
        caras = _caras_registradas()
    except Exception:
        return True
    fam, est = str(par[0]), str(par[1]) if len(par) > 1 else 'Regular'
    return FS.normalizar(f'{fam} {est}') in caras or (est.lower() == 'regular' and FS.normalizar(fam) in caras)

LETRA_DE_RESPALDO = 'Arial-BoldMT'


def _rgb(c, por_defecto=(255, 255, 255)):
    if c is None:
        return list(por_defecto)
    try:
        import render_temas as RT
        return [int(v) for v in RT._rgb255(c)]
    except Exception:
        return list(por_defecto)


def _color_medio(degradado):
    """El color de la mitad de un degradado [(parada, color)] (Premiere no lo lleva en el texto: va el tono de en medio)."""
    pares = sorted(((float(p), _rgb(c)) for p, c in degradado), key=lambda pc: pc[0])
    if not pares:
        return [255, 255, 255]
    if 0.5 <= pares[0][0]:
        return pares[0][1]
    for (p0, c0), (p1, c1) in zip(pares, pares[1:]):
        if p0 <= 0.5 <= p1:
            k = (0.5 - p0) / max(1e-6, p1 - p0)
            return [int(round(a + (b - a) * k)) for a, b in zip(c0, c1)]
    return pares[-1][1]


def _sombra(e):
    """La sombra de Premiere (una por texto) con lo que más se nota del dibujo: la dura del Estilo 7, la sombra, la ancha, el brillo o el halo."""
    em = float(e['em'])
    if e.get('dura'):
        ddx, ddy, col = e['dura']
        return {'color': _rgb(col, (0, 0, 0)), 'opacidad': 100, 'angulo': math.degrees(math.atan2(ddx, -ddy)) % 360,
                'distancia': math.hypot(ddx, ddy) * em, 'desenfoque': 0.0, 'tamano': float(e.get('contorno') or 0.0) * em}
    for sm in (e.get('sombra'), e.get('sombra2')):
        if sm:
            op, baja, blur = sm[:3]
            return {'color': [0, 0, 0], 'opacidad': max(0, min(100, round(float(op) * 100))), 'angulo': 180.0,
                    'distancia': float(baja) * em, 'desenfoque': float(blur) * em, 'tamano': 0.0}
    brillo = e.get('brillo') or e.get('halo')
    if brillo:
        radio, fuerza = brillo[:2]
        if e.get('brillo'):                      # v5.87: render_temas dibuja el brillo con ×1,6 de ganancia (al 42 % en Premiere apenas se veía)
            fuerza = float(fuerza) * 1.6
        if len(brillo) > 2:
            col = _rgb(brillo[2])
        elif e.get('degradado'):
            col = _color_medio(e['degradado'])
        else:
            col = _rgb(e.get('color'))
        return {'color': col, 'opacidad': max(10, min(100, round(float(fuerza) * 100))), 'angulo': 180.0, 'distancia': 0.0,
                'desenfoque': float(radio) * em, 'tamano': 0.0}
    return None


def _png(rgba, carpeta):
    """Guarda una capa RGBA (uint8) como PNG; el nombre es su huella (la misma pieza se importa una sola vez)."""
    datos = np.ascontiguousarray(rgba)
    h = hashlib.sha1(datos.tobytes() + str(datos.shape).encode()).hexdigest()[:16]
    ruta = carpeta / f'el_{h}.png'
    if not ruta.exists():
        Image.fromarray(datos, 'RGBA').save(ruta, optimize=False, compress_level=1)
    return ruta


def _rgba_de_capa(c):
    rgb = np.clip(np.asarray(c['rgb'], dtype=np.float32), 0, 255)
    a = np.clip(np.asarray(c['a'], dtype=np.float32), 0.0, 1.0)
    if a.ndim == 2:
        a = a[..., None]
    return np.concatenate([rgb, a * 255.0], axis=2).round().astype(np.uint8)


def _sprite_rgba(sp):
    return np.asarray(sp.img.convert('RGBA'), dtype=np.uint8)


def _a_fotogramas(items, fps):
    """Entradas, salidas y pasos del recorte a fotogramas enteros del video, con la MISMA regla (medido en Premiere 26.5, Estilo 3: un clip
    que acaba en 9,01 s y el siguiente que empieza en 9,01 s se veían juntos un fotograma —Premiere llevaba la entrada abajo y la salida
    arriba—). Así uno acaba justo donde empieza el otro."""
    if not fps or fps <= 0:
        return
    for it in items:
        f0 = int(round(float(it['t0']) * fps))
        f1 = max(f0 + 1, int(round(float(it['t1']) * fps)))
        it['t0'], it['t1'] = round(f0 / fps, 6), round(f1 / fps, 6)
        for paso in it.get('recorte') or []:
            paso[0] = round(min(max(f0, int(round(float(paso[0]) * fps))), f1 - 1) / fps, 6)


def _carriles(items):
    """Pone `pista` (0, 1, 2…) a cada pieza: en un mismo carril nunca se solapan (por orden de entrada, el primer carril libre)."""
    fines = []
    for it in sorted(items, key=lambda i: (i['t0'], i['t1'])):
        for k, fin in enumerate(fines):
            if fin <= it['t0'] - HUECO_S:
                it['pista'] = k
                fines[k] = it['t1']
                break
        else:
            it['pista'] = len(fines)
            fines.append(it['t1'])
    return len(fines)


# ------------------------------------------------------------------------------------------------ v5.87: la animación de cada pieza
# Hasta la 5.86 cada pieza solo entraba con un fundido: en Premiere todo se veía quieto («hay problemas visuales»). Ahora cada texto e imagen
# lleva la animación de su tipo (vista_tema.estado_animado: la de la vista de Creativo, hecha a imagen de los macros de Resolve: el pop con
# rebote del héroe, el barrido de cintas y subrayados, el aro que gira al entrar, palabras que suben, el emoji que salta…) como FOTOGRAMAS
# CLAVE de Premiere (opacidad, escala, posición, giro y recorte por la derecha). Se muestrea cada fotograma de la entrada y de la salida y
# cada curva se reduce a los pocos puntos que la dibujan sin error visible (Ramer-Douglas-Peucker), para que el panel no tarde más.
ANIM_TOPE_S = 1.8                # la entrada se mira hasta aquí (lo que sigue, quieto hasta la salida)
_TOLERANCIA = {'op': 1.0, 'es': 0.6, 'gi': 0.25, 'po': 0.6, 'cr': 0.25}


def _reducir(puntos, tol):
    """Los puntos [(t, (v…))] imprescindibles para que la interpolación lineal no se aparte más de `tol` de la curva."""
    if len(puntos) <= 2:
        return list(puntos)
    fuera = [False] * len(puntos)
    fuera[0] = fuera[-1] = True
    pila = [(0, len(puntos) - 1)]
    while pila:
        i, j = pila.pop()
        (t0, v0), (t1, v1) = puntos[i], puntos[j]
        peor, k_peor = -1.0, -1
        for k in range(i + 1, j):
            tk, vk = puntos[k]
            f = (tk - t0) / (t1 - t0) if t1 > t0 else 0.0
            d = max(abs(vk[n] - (v0[n] + (v1[n] - v0[n]) * f)) for n in range(len(vk)))
            if d > peor:
                peor, k_peor = d, k
        if peor > tol and k_peor > 0:
            fuera[k_peor] = True
            pila += [(i, k_peor), (k_peor, j)]
    return [p for p, sirve in zip(puntos, fuera) if sirve]


def animacion(c, punto, fps, giro_base=0.0, ancho_cuadro=None):
    """Las claves de Premiere de la capa `c` (render_sin_resolve.preparar). `punto`: dónde la pone Premiere (el ancla del texto o el centro
    de la imagen; ahí escala y gira). `ancho_cuadro`: solo en textos (su recorte va en % del cuadro; en una imagen, de la imagen).
    → {'op': [[s, %]], 'es': [[s, %]], 'gi': [[s, °]], 'po': [[s, x, y]], 'cr': [[s, %]]} (s desde el inicio del clip; solo lo que cambia)
    o None si la pieza no se mueve."""
    import vista_tema as VT
    if not fps or fps <= 0 or not float(c.get('entrada') or 0.0) > 0.0 or c.get('seco'):
        return None                              # (corte seco: la caja del Estilo 3 que salta de palabra en palabra, el Estilo 7)
    a = np.asarray(c['a'])
    H, W = a.shape[:2]
    sp = {k: v for k, v in c.items() if k not in ('rgb', 'a')}
    sp.update(w=W, h=H)
    t0, t1 = float(c['t0']), float(c['t1'])
    n = max(1, int(round((t1 - t0) * fps)))
    tope, salida = int(math.ceil(ANIM_TOPE_S * fps)), n - int(math.ceil(VT.SALIDA_S * fps)) - 1
    cx, cy = float(c['x']) + W / 2.0, float(c['y']) + H / 2.0
    px, py = float(punto[0]), float(punto[1])
    series = {k: [] for k in _TOLERANCIA}
    for f in range(n):
        if tope < f < salida:
            continue
        rel = f / fps
        st = VT.estado_animado(sp, t0 + rel + 1e-6)
        if st is None:
            continue
        s = float(st['s'])
        series['op'].append((rel, (100.0 * max(0.0, min(1.0, float(st['a']))),)))
        series['es'].append((rel, (100.0 * s,)))
        series['gi'].append((rel, (float(giro_base) + float(st['rot']),)))
        series['po'].append((rel, (px + float(st['dx']) + (1.0 - s) * (cx - px), py + float(st['dy']) + (1.0 - s) * (cy - py))))
        b = st.get('barrido')
        b = 1.0 if b is None else max(0.0, min(1.0, float(b)))
        if ancho_cuadro:                         # (el texto: lo que se ve acaba en el borde derecho del barrido, en el cuadro)
            borde = cx + float(st['dx']) + s * (-W / 2.0 + b * W)
            series['cr'].append((rel, (0.0 if b >= 1.0 else max(0.0, min(100.0, (ancho_cuadro - borde) / ancho_cuadro * 100.0)),)))
        else:
            series['cr'].append((rel, (100.0 * (1.0 - b),)))
    quieto = {'op': (100.0,), 'es': (100.0,), 'gi': (float(giro_base),), 'po': (px, py), 'cr': (0.0,)}
    if str(c.get('k') or '').startswith('v linea'):
        # (Estilo 3: la palabra de la línea está DEBAJO de la de la caja, que entra de golpe en el mismo sitio; si sube, se ve doble)
        series = {'op': series['op']}
    claves = {}
    for k, pts in series.items():
        if len(pts) < 2 or all(max(abs(v[i] - quieto[k][i]) for i in range(len(v))) <= _TOLERANCIA[k] for _t, v in pts):
            continue
        claves[k] = [[round(t, 4)] + [round(x, 3) for x in v] for t, v in _reducir(pts, _TOLERANCIA[k])]
    return claves or None


def _animar(c, punto, fps, giro_base=0.0, ancho_cuadro=None):
    try:
        return animacion(c, punto, fps, giro_base, ancho_cuadro)
    except Exception:                            # (sin animación la pieza entra con su fundido de siempre)
        return None


def _ancho_de(par, px, txt):
    """El avance (px) de `txt` con esa letra a ese tamaño, como lo mide render_temas (None si no se puede)."""
    try:
        import render_temas as RT
        return float(RT._fuente(par, px).getlength(str(txt)))
    except Exception:
        return None


def _encoger_respaldo(e, em):
    """v5.87: con Arial en lugar de la letra del estilo (no instalada o Premiere abierto antes de instalarla), el tamaño que hace que la palabra
    ocupe lo mismo que con su letra: Arial Bold es más ancha que casi todas y se montaba sobre la de al lado (Estilo 6: «metresadrados»)."""
    plan = _ancho_de(e['par'], em, e['txt'])
    arial = _ancho_de(('Arial', 'Bold'), em, e['txt'])
    if not plan or not arial or arial <= plan:
        return em
    return max(em * 0.45, em * plan / arial)


def _ficha_texto(e, ax, ay, rot, c):
    """El texto para el panel: anclado en el centro de su avance y en su línea de base (como lo dibuja render_temas)."""
    ruta, ps = fuente_de(e['par'])
    em = float(e['em'])
    tam = em if ruta else _encoger_respaldo(e, em)
    esp = float(e.get('esp') or 1.0)
    tracking = (esp - 1.0) * 550.0 - (float(e.get('apretar') or 0.0) / max(1.0, em)) * 1000.0
    contorno = float(e.get('contorno') or 0.0) * em
    return {
        'texto': str(e['txt']), 'fuente': ps, 'familia': e['par'][0], 'estilo_fuente': e['par'][1] if len(e['par']) > 1 else '',
        'archivo_fuente': ruta, 'tam': round(tam, 2),
        'color': _color_medio(e['degradado']) if e.get('degradado') else _rgb(e.get('color')),
        'contorno': round(contorno, 2), 'color_contorno': _rgb(e.get('color_contorno'), (0, 0, 0)),
        'sombra': _sombra(e), 'tracking': int(round(tracking)), 'cursiva': abs(float(e.get('inclinacion') or 0.0)) > 0.05,
        'x': round(float(ax), 2), 'y': round(float(ay), 2), 'rot': round(-float(rot or 0.0), 3),        # (Pillow gira a la izquierda; Premiere, a la derecha)
        't0': round(float(c['t0']), 4), 't1': round(max(float(c['t0']) + 0.04, float(c['t1'])), 4), 'entrada': float(c.get('entrada') or 0.0),
        'rol': c.get('rol'), 'k': c.get('k') or c.get('tipo') or '',
    }


# ------------------------------------------------------------------------------------------------ una plantilla de Premiere por cada texto
# Probado en Premiere 26.5 (2026-11-12): escribir el «Texto de origen» por ExtendScript NO sirve (lo guarda pero no lo dibuja: el formato de
# dentro es otro binario), y la plantilla tal cual SÍ se dibuja. Así que cada texto lleva SU .mogrt: la «Basic Title» del propio Premiere con
# el texto y el estilo ya escritos en su formato de origen (8 bytes de largo + JSON en UTF-16, el que Premiere convierte al importar). Se hace
# en el equipo del usuario a partir de SU plantilla (no se reparte nada de Adobe) y no queda ninguna letra que no esté instalada (Myriad Pro).
_BASE_MOGRT = {}


def _base_mogrt(plantilla):
    """(definición, nombre del proyecto interno, xml, miniatura png) de la plantilla de Premiere, con caché."""
    clave = str(plantilla)
    if clave not in _BASE_MOGRT:
        import gzip
        import io
        import json
        import zipfile
        with zipfile.ZipFile(plantilla) as z:
            definicion = json.loads(z.read('definition.json').decode('utf-8-sig'))
            interior = zipfile.ZipFile(io.BytesIO(z.read('project.prgraphic')))
            nombre = interior.namelist()[0]
            xml = gzip.decompress(interior.read(nombre)).decode('utf-8')
            miniatura = z.read('thumb.png') if 'thumb.png' in z.namelist() else None
        _BASE_MOGRT[clave] = (definicion, nombre, xml, miniatura)
    return _BASE_MOGRT[clave]


def _color_int(rgb):
    r, g, b = (int(round(v)) for v in rgb[:3])
    return r * 65536 + g * 256 + b


def json_de_texto(base_json, f):
    """El JSON del «Texto de origen» de la plantilla con el texto y el estilo de la ficha `f` (premiere_textos._ficha_texto)."""
    import json
    j = json.loads(base_json)
    tp = j.get('mTextParam') or j
    ss = tp['mStyleSheet']

    def uno(v):
        return {'mParamValues': [[0, v]]}
    ss['mText'] = f['texto']
    if f.get('fuente'):
        ss['mFontName'] = uno(f['fuente'])
    ss['mFontSize'] = uno(float(f['tam']))
    ss['mFillColor'] = uno(_color_int(f['color']))
    ss['mFillVisible'] = uno(True)
    ss['mStrokeVisible'] = uno(float(f.get('contorno') or 0) > 0)
    if float(f.get('contorno') or 0) > 0:
        ss['mStrokeWidth'] = uno(float(f['contorno']))
        ss['mStrokeColor'] = uno(_color_int(f.get('color_contorno') or (0, 0, 0)))
    ss['mTracking'] = uno(int(f.get('tracking') or 0))
    ss['mFauxItalic'] = uno(bool(f.get('cursiva')))
    s = f.get('sombra')
    tp['mShadowVisible'] = bool(s)
    if s:
        tp.update(mShadowColor=_color_int(s['color']), mShadowOpacity=float(s['opacidad']), mShadowAngle=float(s['angulo']),
                  mShadowOffset=float(s['distancia']), mShadowBlur=float(s['desenfoque']), mShadowSize=float(s['tamano']))
    return json.dumps(j, ensure_ascii=False, separators=(',', ':'))


def mogrt_de_texto(plantilla, base_json, f, carpeta, hash_modo='mantener'):
    """El .mogrt de ESTE texto (con su estilo) en `carpeta`; el nombre es su huella (el mismo texto con el mismo estilo se reutiliza).
    hash_modo: el atributo BinaryHash del valor se CONSERVA (medido en Premiere 26.5: sin él toma las letras pero no la letra, el color ni el
    centrado; con él, todo)."""
    import base64
    import gzip
    import io
    import json
    import re
    import uuid
    import zipfile
    from xml.sax.saxutils import escape
    texto_json = json_de_texto(base_json, f)
    huella = hashlib.sha1((texto_json + '|' + hash_modo).encode('utf-8')).hexdigest()[:16]
    ruta = Path(carpeta) / f'tx_{huella}.mogrt'
    if ruta.exists():
        return ruta
    definicion, nombre, xml, miniatura = _base_mogrt(plantilla)
    datos = texto_json.encode('utf-16-le')
    valor = base64.b64encode(struct.pack('<Q', len(datos)) + datos).decode('ascii')
    patron = re.compile(r'(<Name>Source Text</Name>.*?<StartKeyframeValue Encoding="base64")( BinaryHash="[^"]*")?(>)[^<]*(<)', re.S)

    def poner(m):
        return m.group(1) + ('' if hash_modo == 'quitar' else (m.group(2) or '')) + m.group(3) + valor + '\n\t\t' + m.group(4)
    xml2, n = patron.subn(poner, xml, count=1)
    if not n:
        raise ValueError('la plantilla no tiene «Source Text»')
    xml2 = xml2.replace('<InstanceName>Your Title Here</InstanceName>', '<InstanceName>%s</InstanceName>' % escape(f['texto'][:60]), 1)
    d = json.loads(json.dumps(definicion))
    d['capsuleID'] = str(uuid.uuid4())
    d['capsuleName'] = 'CineCaptions'
    for c in d.get('clientControls') or []:
        for s in ((c.get('value') or {}).get('strDB') or []):
            s['str'] = f['texto']
    interior = io.BytesIO()
    with zipfile.ZipFile(interior, 'w', zipfile.ZIP_DEFLATED) as zi:
        zi.writestr(nombre, gzip.compress(xml2.encode('utf-8'), compresslevel=6))
    temporal = ruta.with_suffix('.tmp')
    with zipfile.ZipFile(temporal, 'w', zipfile.ZIP_DEFLATED) as zo:
        zo.writestr('definition.json', json.dumps(d, ensure_ascii=False))
        zo.writestr('project.prgraphic', interior.getvalue())
        if miniatura:
            zo.writestr('thumb.png', miniatura)
    temporal.replace(ruta)
    return ruta


def _lineas_tipo(c, faltan, ancho_cuadro):
    """Las líneas de un bloque del Estilo 5 (render_temas._capas_tipo → tipo_lineas) como textos: su letra, tamaño, color y la sombra suave de
    tipo_vista; anclados en el centro de la línea y su línea de base (relativos a la esquina de la capa). La escritura palabra a palabra va en
    `recorte` ([[segundo, % que se tapa por la derecha]]): el panel lo pone en «Recortar hacia la derecha» de Movimiento, que destapa la línea
    de izquierda a derecha como el Write On de Resolve, y el texto sigue entero y editable."""
    try:
        import tipo_vista
        op, baja, difu = tipo_vista.SOMBRA
    except Exception:
        op, baja, difu = 0.40, 0.003, 0.012
    salida = []
    for ln in c['tipo_lineas']:
        if not str(ln.get('txt') or '').strip():
            continue
        em = float(ln['em'])
        e = {'txt': ln['txt'], 'par': tuple(ln['par']), 'em': em, 'color': c.get('tipo_color') or (1.0, 1.0, 1.0),
             'sombra': (op, baja * float(c.get('tipo_alto') or 1920) / em, difu * float(c.get('tipo_ancho') or 1080) / em)}
        cx = c['x'] + ln['rx']
        ficha = _ficha_texto(e, cx, c['y'] + ln['ry'], 0.0,
                             {'t0': ln['t'], 't1': c.get('tipo_fin') or c['t1'], 'entrada': 0.08, 'k': 'v tipo', 'rol': 'main' if ln.get('grande') else None})
        pasos, ancho_l = ln.get('pasos') or [], float(ln.get('ancho') or 0.0)
        if len(pasos) > 1 and ancho_l > 0 and ancho_cuadro:
            izquierda, holgura = cx - ancho_l / 2.0, 0.12 * em             # (la holgura: la cola de la última letra y su sombra)
            recorte = []
            for t, visto in pasos:
                tapa = 0.0 if visto >= ancho_l - 0.5 else max(0.0, (ancho_cuadro - (izquierda + visto + holgura)) / ancho_cuadro * 100.0)
                if not recorte or abs(recorte[-1][1] - tapa) > 0.01:
                    recorte.append([round(float(t), 4), round(min(100.0, tapa), 3)])
            if len(recorte) > 1:
                ficha['recorte'] = recorte
        if not ficha['archivo_fuente']:
            faltan.add('%s %s' % tuple(e['par'][:2]))
        salida.append(ficha)
    return salida


def preparar(video, cues, carpeta=None, emoji_arriba=True, estilo=None, cancelado=None, plantilla=None):
    """Las piezas del pedido de Premiere. → {'ok', 'textos', 'imagenes', 'carriles_texto', 'carriles_imagen', 'ancho', 'alto', 'fps',
    'duracion', 'carpeta', 'faltan_fuentes', 'segundos'} · {'ok': False, 'error'} · {'ok': False, 'cancelado': True}."""
    import render_sin_resolve as RSR
    t_ini = time.time()
    video = Path(video)
    try:
        m = RSR.medir_video(video)
    except Exception as e:
        return {'ok': False, 'error': f'no pude leer el video: {e}'}
    if m.get('solo_audio'):
        return {'ok': False, 'error': 'un audio suelto va con la capa de siempre'}
    ancho, alto = int(m['ancho']), int(m['alto'])
    # v5.88: con Windows sin rutas largas, el nombre de la carpeta se recorta para que quepan sus PNG (~30 letras más)
    hueco = CARPETA_SUFIJO + '/' + 'x' * 30
    destino = Path(carpeta) if carpeta else video.with_name(RSR.nombre_que_cabe(video.parent, video.stem, hueco) + CARPETA_SUFIJO)
    try:
        if not RSR.rutas_largas_permitidas() and len(str(destino)) + 31 + RSR.MARGEN_TEMPORAL > RSR.TOPE_RUTA_WIN:
            raise OSError('ruta demasiado larga para este Windows')
        destino.mkdir(parents=True, exist_ok=True)
        (destino / '.prueba').write_bytes(b'')
        (destino / '.prueba').unlink()
    except OSError:
        casa = RSR.carpeta_videos() / 'CineCaptions'     # (v5.88: la Videos real, también con OneDrive)
        destino = casa / (RSR.nombre_que_cabe(casa, video.stem, hueco) + CARPETA_SUFIJO)
        destino.mkdir(parents=True, exist_ok=True)
    capas = RSR.preparar(cues, ancho, alto, emoji_arriba=emoji_arriba, estilo=estilo)
    fps = float(m['fps'])
    _PREMIERE_DESDE[:] = [_premiere_abierto_desde()]
    try:
        import premiere
        _PREMIERE_CORRE[:] = [bool(_PREMIERE_DESDE[0]) or premiere.panel_vivo() or premiere.abierto()]
    except Exception:
        _PREMIERE_CORRE[:] = [False]
    _SIN_VER.clear()
    _FAMILIAS.clear()
    textos, imagenes, faltan = [], [], set()
    bloques_tipo = set()
    for c in capas:
        if cancelado and cancelado():
            return {'ok': False, 'cancelado': True}
        if c.get('k') == 'v tipo' and c.get('tipo_lineas'):
            # Estilo 5 (la máquina de escribir): un texto por línea, que entra con su primera palabra (en vez de una imagen por estado)
            if id(c['tipo_lineas']) not in bloques_tipo:
                bloques_tipo.add(id(c['tipo_lineas']))
                textos += _lineas_tipo(c, faltan, ancho)
            continue
        a = np.asarray(c['a'])
        H, W = a.shape[:2]
        e = c.get('espec') if c.get('parte') != 'caja' else None
        if e and str(e.get('txt') or '').strip():
            ancla = e.get('ancla')
            ax, ay = (c['x'] + ancla[0], c['y'] + ancla[1]) if ancla else (c['x'] + W / 2.0, c['y'] + H / 2.0)
            ficha = _ficha_texto(e, ax, ay, c.get('rot'), c)
            if not ficha['archivo_fuente']:
                faltan.add('%s %s' % tuple(e['par'][:2]))
            anim = _animar(c, (ax, ay), fps, ficha['rot'], ancho)
            if anim:
                ficha['anim'] = anim
            textos.append(ficha)
            if e.get('caja'):                     # la pegatina: la caja (sin letras) en PNG, debajo del texto y con el mismo ancla y giro
                try:
                    import render_temas as RT
                    sp = RT.texto(e['txt'], e['par'], e['em'], esp=e.get('esp') or 1.0, apretar=e.get('apretar') or 0.0,
                                  inclinacion=e.get('inclinacion') or 0.0, caja=e['caja'], solo_caja=True)
                    if sp is not None:
                        sp.girar(float(c.get('rot') or 0.0))
                        caja = _sprite_rgba(sp)
                        im = {'ruta': str(_png(caja, destino)), 'x': round(ax, 2), 'y': round(ay, 2), 'ancho': caja.shape[1],
                              'alto': caja.shape[0], 't0': ficha['t0'], 't1': ficha['t1'], 'entrada': ficha['entrada'], 'k': 'caja'}
                        anim = _animar(c, (ax, ay), fps)          # (la caja, con su texto: el mismo movimiento)
                        if anim:
                            im['anim'] = anim
                        imagenes.append(im)
                except Exception:
                    pass
            continue
        rgba = _rgba_de_capa(c)
        if not rgba[..., 3].any():
            continue
        im = {'ruta': str(_png(rgba, destino)), 'x': round(c['x'] + W / 2.0, 2), 'y': round(c['y'] + H / 2.0, 2), 'ancho': W, 'alto': H,
              't0': round(float(c['t0']), 4), 't1': round(max(float(c['t0']) + 0.04, float(c['t1'])), 4),
              'entrada': float(c.get('entrada') or 0.0), 'k': c.get('k') or c.get('tipo') or ''}
        anim = _animar(c, (im['x'], im['y']), fps)
        if anim:
            im['anim'] = anim
        imagenes.append(im)
    _a_fotogramas(textos + imagenes, fps)
    try:                                         # la plantilla de Premiere de cada texto (con el texto y el estilo dentro)
        import premiere
        plantilla = plantilla or premiere.plantilla_texto()
        base = premiere.texto_base(plantilla)
        if not plantilla or not base:
            return {'ok': False, 'error': 'no encuentro la plantilla de texto de Premiere («Basic Title»)'}
        carpeta_textos = destino / 'textos'
        carpeta_textos.mkdir(parents=True, exist_ok=True)
        for t in textos:
            if cancelado and cancelado():
                return {'ok': False, 'cancelado': True}
            t['mogrt'] = str(mogrt_de_texto(plantilla, base, t, carpeta_textos))
    except Exception as e:
        return {'ok': False, 'error': f'no pude preparar las plantillas de texto: {type(e).__name__}: {e}'}
    return {'ok': True, 'textos': textos, 'imagenes': imagenes, 'carriles_texto': _carriles(textos), 'carriles_imagen': _carriles(imagenes),
            'ancho': ancho, 'alto': alto, 'fps': float(m['fps']), 'duracion': float(m.get('duracion') or 0.0), 'carpeta': str(destino),
            'faltan_fuentes': sorted(faltan - _SIN_VER), 'fuentes_reiniciar': sorted(_SIN_VER), 'segundos': round(time.time() - t_ini, 2),
            'plantilla': str(plantilla)}
