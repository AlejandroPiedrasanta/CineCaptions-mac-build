# CineCaptions · By Cinema Productions
# 1_codigo/vigilante_pro.py — el VIGILANTE de calidad de la Edición PRO: antes de tocar Resolve revisa el plan con reglas, las animaciones ya hechas
# con ffmpeg (PyAV) y, con la IA local, que lo que se VE encaje con lo que se DICE. Lo que no pasa se arregla o se quita, y queda en el Registro.
"""
vigilante_pro.py
----------------
v5.5.8 (pedido: «que no haya bugs, necesito un vigilante de eso, que también la IA local analice, involucra el ffmpeg para que no pasen errores»).

    revisar_plan(piezas, palabras)        reglas: la cifra de un dato se DICE en ese momento; la moneda es la que se nombra; dos gráficos a la
                                          vez en la misma pista se reparten (colocar_pro saltaba el segundo sin avisar)
    revisar_ia(piezas, palabras, idioma)  la IA local (ia_texto.revisar) marca los gráficos cuyo texto no encaja con lo que se dice; se quitan
                                          solo si además casi nada de su texto se dijo cerca (la IA sola no basta: puede equivocarse)
    revisar_clips(graficos)               ffmpeg: cada animación de Remotion se abre, dura lo que debe y no sale vacía; cada .ograf trae lo suyo
`palabras`: [(t en segundos del timeline, texto)] de lo que se dice (los captions de GO). Todas devuelven la lista de avisos (texto).
"""
import re
import unicodedata
import zipfile
from pathlib import Path

# capas que son una pista de Resolve (colocar_pro.CAPA): dos clips a la vez en una pista no se colocan
PISTAS = ('fondo', 'velo', 'detras', 'delante', 'iconos', 'subs')
TEXTOS = ('titulo', 'texto', 'palabra', 'linea1', 'linea2', 'linea3', 'numero', 'unidad', 'etiqueta', 'items', 'valor', 'nombre', 'kicker', 'pie',
          'clave', 'a', 'b', 'arriba', 'abajo', 'frase', 'subtitulo')
TOL = 0.04                                                                 # un fotograma: dos clips que se tocan no se pisan


def _plegar(t):
    t = unicodedata.normalize('NFKD', str(t or '').lower())
    return re.sub(r'[^a-z0-9 ]', ' ', ''.join(c for c in t if not unicodedata.combining(c)))


def _registro(nivel, texto):
    try:
        import registro
        getattr(registro, nivel)(texto, 'vigilante')
    except Exception:
        pass


def _dicho(palabras, a, z):
    return [x for t, x in palabras if a <= t <= z]


def _texto_visible(v):
    """El texto que un gráfico ENSEÑA (sin imágenes, colores ni números de posición)."""
    out = []
    for k, x in (v or {}).items():
        if k == 'objetos' and isinstance(x, list):
            for o in x:
                out += _texto_visible(o)
        elif k in TEXTOS and isinstance(x, (str, int, float)) and not str(x).startswith('data:'):
            out.append(str(x).replace('|', ' '))
    if v and v.get('signo') and v.get('valor'):
        out.append(f"{v['signo']}{v['valor']}")
    return [s for s in out if s.strip()]


def _digitos(s):
    return re.sub(r'\D', '', str(s or ''))


# ------------------------------------------------------------------------------------------------------------------------------- reglas
def revisar_plan(piezas, palabras):
    avisos = []
    vivas = [p for p in piezas if not p.get('quitar')]
    # 1) los datos (precio, cifra, gráfica): la cifra se dice en ese momento (±4 s) y la moneda es la que se nombra
    try:
        import monedas as M
    except Exception:
        M = None
    for p in vivas:
        v = p.get('valores') or {}
        if p.get('pieza') != 'dato':
            continue
        cerca = _dicho(palabras, p['ini'] - 4.0, p['fin'] + 1.0)
        num = _digitos(v.get('valor'))
        if num and not any(num == _digitos(x) or (len(num) >= 3 and num in _digitos(x)) for x in cerca):
            p['quitar'] = True
            avisos.append(f"quité el dato {v.get('signo', '')}{v.get('valor')} ({p['ini']:.1f} s): esa cifra no se dice ahí")
            continue
        if M is not None and v.get('tipo') in ('precio', 'grafica') and v.get('signo') != '%':
            moneda = M.signo(cerca)
            if moneda and moneda != v.get('signo'):
                avisos.append(f"moneda corregida en {p['ini']:.1f} s: {v.get('signo')} → {moneda} (se dice esa moneda)")
                v['signo'] = moneda
    # 2) dos gráficos a la vez en la misma pista: el segundo pasa a PRO-ICONOS si ahí cabe; si no, se quita (antes se perdía sin aviso)
    for capa in PISTAS:
        en = sorted((p for p in piezas if not p.get('quitar') and p.get('capa') == capa and p.get('fin', 0) > p.get('ini', 0)), key=lambda p: p['ini'])
        fin = -1.0
        for p in en:
            if p['ini'] < fin - TOL:
                libre = capa != 'iconos' and not any(q is not p and not q.get('quitar') and q.get('capa') == 'iconos'
                                                     and p['ini'] < q['fin'] - TOL and q['ini'] < p['fin'] - TOL for q in piezas)
                if libre:
                    p['capa'] = 'iconos'
                    avisos.append(f"{p.get('pieza')} ({p['ini']:.1f} s) pisaba otro gráfico en su pista: lo subí a PRO-ICONOS")
                else:
                    p['quitar'] = True
                    avisos.append(f"quité {p.get('pieza')} ({p['ini']:.1f} s): pisaba otro gráfico y no había otra pista libre")
                continue
            fin = max(fin, p['fin'])
    for a in avisos:
        _registro('aviso', 'Vigilante: ' + a)
    return avisos


# ----------------------------------------------------------------------------------------------------------------------------- IA local
def revisar_ia(piezas, palabras, idioma='es', estado=None):
    """La IA local revisa los gráficos con texto; se quita el que la IA marca Y del que casi nada se dijo cerca (< 40 % de sus palabras)."""
    items, ref = [], {}
    for k, p in enumerate(piezas):
        if p.get('quitar'):
            continue
        muestra = ' · '.join(_texto_visible(p.get('valores')))[:160]
        if len(_plegar(muestra).split()) < 1:
            continue
        dicho = ' '.join(_dicho(palabras, p['ini'] - 2.5, p['fin'] + 0.5))[:300]
        if not dicho:
            continue
        ref[len(items)] = k
        items.append({'i': len(items), 'dicho': dicho, 'muestra': muestra})
    if not items:
        return []
    try:
        import ia_texto
        malos = ia_texto.revisar(items[:40], idioma, estado=estado)
    except Exception:
        malos = []
    avisos = []
    for i, motivo in malos:
        if i not in ref:
            continue
        p = piezas[ref[i]]
        vis = [w for w in _plegar(items[i]['muestra']).split() if len(w) >= 4 or w.isdigit()]
        dicho = set(_plegar(items[i]['dicho']).split())
        parecido = sum(1 for w in vis if w in dicho) / max(1, len(vis))
        if parecido < 0.4:
            p['quitar'] = True
            avisos.append(f"quité {p.get('pieza')} «{items[i]['muestra'][:50]}» ({p['ini']:.1f} s): {motivo or 'no encaja con lo que se dice'}")
        else:
            _registro('info', f"Vigilante (IA): dudó de «{items[i]['muestra'][:50]}» ({p['ini']:.1f} s) pero se dice casi todo: se queda")
    for a in avisos:
        _registro('aviso', 'Vigilante (IA): ' + a)
    return avisos


# ------------------------------------------------------------------------------------------------------------------------------- ffmpeg
def _clip_sano(ruta, dur_esperada=None, alfa=True):
    """(ok, motivo) de una animación de Remotion: abre, dura al menos la mitad de lo esperado y no está vacía (con alfa: algo opaco; opaca
    —«Motions completo»—: que no sea toda negra)."""
    try:
        import av
        import numpy as np
        with av.open(str(ruta)) as c:
            if not c.streams.video:
                return False, 'sin video'
            vs = c.streams.video[0]
            dur = float(c.duration / 1e6) if c.duration else (float(vs.duration * vs.time_base) if vs.duration else 0.0)
            if dur_esperada and dur < 0.5 * dur_esperada:
                return False, f'dura {dur:.1f} s de {dur_esperada:.1f}'
            hay = False
            for n, fr in enumerate(c.decode(vs)):
                if n % 12 == 0:
                    x = fr.to_ndarray(format='rgba')[::8, ::8]
                    if (x[..., 3] > 16).mean() > 0.001 if alfa else float(x[..., :3].mean()) > 6.0:
                        hay = True
                        break
                if n > 120:
                    break
            return (True, '') if hay else (False, 'sale vacío (transparente)')
    except Exception as e:
        return False, f'no se abre ({type(e).__name__})'


def revisar_clips(graficos, fps=30.0):
    """Quita de `graficos` (la lista que va a colocar_pro) las animaciones rotas o vacías y los .ograf incompletos."""
    avisos, buenos = [], []
    for g in graficos:
        ruta = Path(str(g.get('archivo') or ''))
        if not ruta.exists():
            avisos.append(f"falta el archivo de «{g.get('nombre')}»")
            continue
        if ruta.suffix.lower() == '.ograf':
            try:
                with zipfile.ZipFile(ruta) as z:
                    nombres = z.namelist()
                ok = any(n.endswith('.ograf.json') for n in nombres) and any(n.endswith('pieza.js') for n in nombres)
            except Exception:
                ok = False
            if not ok:
                avisos.append(f"«{g.get('nombre')}» (OGraf) está incompleto")
                continue
        elif g.get('alfa') or g.get('opaco'):
            ok, motivo = _clip_sano(ruta, g.get('dur'), alfa=bool(g.get('alfa')))
            if not ok:
                avisos.append(f"quité «{g.get('nombre')}»: {motivo}")
                continue
        buenos.append(g)
    graficos[:] = buenos
    for a in avisos:
        _registro('aviso', 'Vigilante (ffmpeg): ' + a)
    return avisos
