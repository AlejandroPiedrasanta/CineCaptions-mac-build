# CineCaptions · By Cinema Productions
# 1_codigo/pack_personalizado.py — v5.55 «Crea tu estilo»: el pack DERIVADO de un tema de fábrica (Kinetic, Referencia, VIRAL, Tema4/5/6) con la letra y
# los colores del usuario ya puestos en sus comps, con nombre propio («VIRAL · a1b2c3d4») y guardado en una caché por huella.
"""
Contrato 5 de «Crea tu estilo»:  preparar(base, ajustes) -> carpeta del pack derivado, o None si los ajustes están vacíos.

    ajustes = {"fuente_principal": "Familia|Estilo" | "", "fuente_secundaria": ..., "color_principal": "#RRGGBB" | "", "color_secundario": ...}
    vacío = lo del tema; principal = la palabra grande (rol main, héroe); secundaria = la de arriba y abajo (context / complement).

Nada se escribe en Resolve en vivo: los gemelos importan el .drb derivado en su propio bin («CC · VIRAL · a1b2c3d4 · v») como cualquier pack, y
para_manifiesto(carpeta) da su campo 'plantilla' (con 'base' = el tema). Se RETOCA el .drb de fábrica, como construir_pack.premium_sobre_drb: cada comp se
descomprime, se cambian SOLO sus entradas de letra y de color (y los reinicios del Inspector que las seguían; sobre el texto de la comp, por posición: el
resto queda byte a byte) y se vuelve a comprimir.
No se regenera nada: los Temas 4-6 llevan macros Luxe de antes de la v1.09 y regenerarlos cambiaría también sus animaciones.

Qué cambia (rol del clip: en los packs Luxe «principal N»/«simple» = principal y «arriba N»/«abajo N» = secundaria; en Kinetic y VIRAL,
fuente_usuario.es_principal, la misma regla que marca los runs 'fu'):
  LETRA  Font/Style de TODOS los Text+ del clip que llevan la fuente escrita (no por expresión): el Template, el Text1 de dentro del macro Luxe, el
         «Relleno» del héroe de Kinetic (recorta el tinte vivo y la trama), Medida/BrilloTxt/Caja de VIRAL y Text1/Line de los Amro. Así ningún
         auxiliar se queda midiendo o recortando con la letra de antes.
  COLOR  el color elegido sustituye al color BASE del texto y lo que se dibujó a partir de él se DERIVA del elegido (derivar): las paradas de los
         degradados (versiones más claras u oscuras), los brillos y halos (del mismo tono), el tinte vivo, la caja de las pegatinas con su luz y su
         sombra (el texto de encima pasa a tinta o a blanco si deja de leerse), el bisel y la luz del shatter, el relleno del drag (también su
         expresión) y la trama del Impacto. La principal Luxe lleva exactamente el «B · Premium» de fábrica: degradado_premium(elegido).
Y los «reinicios» del Inspector (v5.58, reinicios_al_dia): el Default de cada control que valía lo mismo que su entrada (el valor del clip) la sigue al
recolorear; si no, la flecha de reiniciar volvía al color de fábrica del tema.
Qué NO cambia: animaciones, máscaras, tamaños y posiciones; sombras y contornos oscuros; las luces blancas (VivoLuz, cursor, mano); aros y subrayados
de Kinetic (no son texto: el planificador los pone del color contrario); la caja del Select; las bandas de barrido de Referencia (elegidas para
contrastar); y el COLOR de los cuatro principales Amro de Referencia (3, 6, 7 y 8: degradado metálico + ColorCorrector + fuego; reciben la letra).

La huella sale de (tema, REVISION_BIN del tema, ajustes, GENERADOR, lo que se copia del pack.json, sha1 de cada .drb de fábrica y de sus .variantes.json y
.posiciones.json, degradado premium de los colores): otro ajuste, un pack actualizado o un cambio en este módulo dan otra carpeta y otro bin. La marca guarda
el sha1 de cada archivo del derivado: uno estropeado se rehace. Un pack que no tiene ningún texto con el rol pedido (uno viejo del usuario con el nombre
del tema) da ErrorPersonalizado en vez de un «derivado» igual al original.
La vista previa debe derivar los colores con ESTA función (derivar / degradado_premium) para coincidir con Resolve.
"""
import binascii
import colorsys
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import threading
import time
import zipfile
import zlib
from pathlib import Path

GENERADOR = 'per 2'           # súbelo si cambia lo que se escribe en las comps (la huella cambia: carpeta nueva y bin nuevo en Resolve). per 2 (v5.58): los reinicios del Inspector al día
BASES = {'t1': 'Kinetic', 't2': 'Referencia', 't3': 'VIRAL', 't4': 'Tema4', 't5': 'Tema5', 't6': 'Tema6'}
CLAVES = ('fuente_principal', 'fuente_secundaria', 'color_principal', 'color_secundario')
SEPARADOR = ' · '             # «VIRAL · a1b2c3d4»: los gemelos sacan el tema con nombre.split(" · ")[0]
MARCA = 'personalizado.json'  # se escribe la última: sin ella (o con otra huella) la carpeta se rehace
MAXIMO_CACHE = 30             # packs derivados que se guardan (los menos usados se borran; se rehacen igual si vuelven a pedirse)
_CANDADO = threading.RLock()
_CANDADO_MANIFIESTO = threading.Lock()


class ErrorPersonalizado(RuntimeError):
    """No se pudo armar el pack derivado: quien llama sigue con el pack de fábrica y lo dice en el Registro."""


# ------------------------------------------------------------------------------------------------------------------ ajustes
def nombre_base(base):
    """'t3' / 'VIRAL' / 'viral' / 'Tema 3' -> 'VIRAL'; también un look suelto de los packs de antes ('t3:shatter', 't2:3', 't1:lima': el tema
    de su pack, contrato 1); None si no es uno de los seis temas."""
    b = str(base or '').strip()
    if b.lower() in BASES:
        return BASES[b.lower()]
    for nombre in BASES.values():
        if b.lower() == nombre.lower():
            return nombre
    m = re.fullmatch(r'tema\s*([1-6])', b, re.I)
    if m:
        return BASES['t' + m.group(1)]
    return _base_de_look(b) if ':' in b else None


def _base_de_look(id_):
    """El tema de un look suelto de antes, con la misma regla que la mezcla (mezcla_planificador.pack_de_look(look_de(id))): 't1:…' -> Kinetic,
    't2:…' -> Referencia, 't3:…' -> VIRAL, y solo si ese look existe. Sin el planificador o sin esas dos funciones (no debería pasar), por el prefijo."""
    try:
        import mezcla_planificador as MP
        look_de, pack_de_look = MP.look_de, MP.pack_de_look
    except Exception:
        m = re.fullmatch(r't([1-3]):\S.*', id_)
        return BASES['t' + m.group(1)] if m else None
    try:
        pack = pack_de_look(look_de(id_))
    except Exception:
        return None
    return pack if pack in BASES.values() else None


def _limpio(texto):
    return re.sub(r'[\x00-\x1f"\\|]', '', str(texto or '')).strip()[:80]


def _fuente_texto(valor):
    partes = str(valor or '').split('|')
    familia = _limpio(partes[0])
    if not familia:
        return ''
    estilo = _limpio(partes[1]) if len(partes) > 1 else ''
    return f'{familia}|{estilo or "Regular"}'


def _color_texto(valor):
    t = str(valor or '').strip().lstrip('#')
    if re.fullmatch(r'[0-9a-fA-F]{3}', t):
        t = ''.join(c * 2 for c in t)
    return '#' + t.upper() if re.fullmatch(r'[0-9a-fA-F]{6}', t) else ''


def normalizar(ajustes):
    """Los cuatro ajustes en su forma canónica («Familia|Estilo», «#RRGGBB»); lo que falte o no se entienda queda en '' (= lo del tema)."""
    a = ajustes if isinstance(ajustes, dict) else {}
    return {'fuente_principal': _fuente_texto(a.get('fuente_principal')), 'fuente_secundaria': _fuente_texto(a.get('fuente_secundaria')),
            'color_principal': _color_texto(a.get('color_principal')), 'color_secundario': _color_texto(a.get('color_secundario'))}


def vacio(ajustes):
    return not any(normalizar(ajustes).values())


def a_rgb(hexa):
    t = _color_texto(hexa)
    return tuple(round(int(t[i:i + 2], 16) / 255.0, 4) for i in (1, 3, 5)) if t else None


def a_hex(rgb):
    return '#%02X%02X%02X' % tuple(int(round(max(0.0, min(1.0, float(v))) * 255)) for v in rgb[:3])


def _por_rol(norm):
    def fuente(t):
        return t.split('|', 1) if t else None
    return {'main': {'fuente': fuente(norm['fuente_principal']), 'color': a_rgb(norm['color_principal'])},
            'extra': {'fuente': fuente(norm['fuente_secundaria']), 'color': a_rgb(norm['color_secundario'])}}


# ------------------------------------------------------------------------------------------------------------------ colores
def _lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _r4(c):
    return tuple(round(max(0.0, min(1.0, float(v))), 4) for v in list(c)[:3])


_GRIS_HONDO = (0.84 / 0.92, 0.86 / 0.92, 0.93 / 0.92)     # el «más hondo» de un blanco es un gris frío (como luxe_macro.degradado_premium)


def honda(color, k):
    """Una versión más honda del color: valor × k y algo más saturada (con k = 0,92 es la parada 0 de degradado_premium)."""
    k = max(0.0, min(1.0, float(k)))
    r, g, b = (float(v) for v in color[:3])
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.08:
        return _r4(v * k * f for f in _GRIS_HONDO)
    return _r4(colorsys.hsv_to_rgb(h, min(1.0, s * (1.0 + 1.875 * (1.0 - k)) + (1.0 - k)), v * k))


def clara(color, t):
    """Una versión más clara: el color llevado una fracción t hacia el blanco (con t = 0,5 es la parada 1 de degradado_premium)."""
    t = max(0.0, min(1.0, float(t)))
    return _r4(c + (1.0 - c) * t for c in color[:3])


def derivar(base, color, nuevo):
    """`color` se dibujó a partir de `base` (el color del texto en el tema): el mismo papel con el color `nuevo`, en el TONO del nuevo.
    Igual a la base -> el nuevo; más oscuro -> honda(nuevo, k) con k = cuánto bajó (valor o luminancia); más claro -> clara(nuevo, t) con t = cuánto
    se acercó al blanco. Sirve para el pack y para la vista previa (tienen que dar lo mismo)."""
    b, d, c = _r4(base), _r4(color), _r4(nuevo)
    if max(abs(x - y) for x, y in zip(b, c)) <= 0.004:          # el color elegido ES el del tema: nada cambia
        return d
    if max(abs(x - y) for x, y in zip(b, d)) <= 0.004:
        return c
    lb, ld = _lum(b), _lum(d)
    if ld < lb:
        vb, vd = max(b), max(d)
        k = vd / vb if (vb > 1e-6 and vd < vb - 0.004) else (ld / lb if lb > 1e-6 else 1.0)
        return honda(c, k)
    i = min(range(3), key=lambda j: b[j])
    t = (d[i] - b[i]) / (1.0 - b[i]) if b[i] < 0.999 else 1.0
    if t <= 0.0:
        t = (ld - lb) / (1.0 - lb) if lb < 0.999 else 0.0
    return clara(c, t)


def derivar_brillo(base, color, nuevo):
    """Un brillo o halo del texto: si es tan claro como el texto (un brillo blanco o de su color) pasa a ser del color nuevo; si es más hondo, derivar()."""
    if max(abs(x - y) for x, y in zip(_r4(base), _r4(nuevo))) <= 0.004:
        return _r4(color)
    if _lum(_r4(color)) >= _lum(_r4(base)) - 0.02:
        return _r4(nuevo)
    return derivar(base, color, nuevo)


def _oscuro(c):
    """Sombras y contornos casi negros (el morado #0A0516 del neón, el negro): no salen del color del texto y no se tocan."""
    return _lum(c) < 0.06 and max(c) < 0.2


def _luxe_macro():
    try:
        import luxe_macro
        return luxe_macro
    except ImportError:
        pass
    try:
        from sfx_rules import base_recursos
        generador = Path(base_recursos()) / 'generador_packs'          # (en el .exe, sys._MEIPASS/generador_packs, como ejemplos_estilo.crear_pack)
        if generador.is_dir() and str(generador) not in sys.path:
            sys.path.append(str(generador))                       # al final: no tapa ningún módulo de la app
        import luxe_macro
        return luxe_macro
    except Exception:
        return None


def degradado_premium(color):
    """Las paradas «B · Premium» de una principal Luxe: las de luxe_macro (el generador de los packs) o, si no se puede importar, las mismas aquí."""
    lm = _luxe_macro()
    if lm is not None and hasattr(lm, 'degradado_premium'):
        return [(float(p), _r4(c)) for p, c in lm.degradado_premium(tuple(color[:3]))]
    return [(0.0, honda(color, 0.92)), (0.5, _r4(color)), (1.0, clara(color, 0.5))]


# ------------------------------------------------------------------------------------------------------------------ lector de comps
class _Nodo:
    __slots__ = ('tipo', 'a', 'b', 'valor', 'campos', 'nombre', 'tabla')

    def __init__(self, tipo, a, b, valor=None, campos=None, nombre=None, tabla=None):
        self.tipo, self.a, self.b, self.valor, self.campos, self.nombre, self.tabla = tipo, a, b, valor, campos, nombre, tabla

    def pares(self):
        t = self.tabla if self.tipo == 'llamada' else self
        return t.campos if (t is not None and t.tipo == 'tabla') else []

    def campo(self, clave):
        for k, v in self.pares():
            if k == clave:
                return v
        return None


_RE_BLANCO = re.compile(r'(?:[ \t\r\n]+|--\[\[.*?\]\]|--[^\n]*)+', re.S)
_RE_CADENA = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'', re.S)
_RE_LARGA = re.compile(r'\[(=*)\[(.*?)\]\1\]', re.S)
_RE_NUM = re.compile(r'-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?')
_RE_ID = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*')
_RE_CAMPO = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)[ \t\r\n]*=(?!=)')


class _Lector:
    """Lee el texto de una comp de Fusion (una tabla de Lua: «Nombre = Tipo { … }», «Input { Value = … }», «[0.5] = { r, g, b, a }») guardando la
    posición de cada valor, para poder cambiar uno sin tocar nada más."""

    def __init__(self, texto):
        self.s, self.i = texto, 0

    def _blanco(self):
        m = _RE_BLANCO.match(self.s, self.i)
        if m:
            self.i = m.end()

    def valor(self):
        self._blanco()
        s, a = self.s, self.i
        c = s[a]
        if c == '{':
            return self._tabla()
        if c in '"\'':
            m = _RE_CADENA.match(s, a)
            if not m:
                raise ValueError(f'cadena sin cerrar en {a}')
            self.i = m.end()
            return _Nodo('cadena', a, m.end(), m.group(0)[1:-1])
        if c == '[':
            m = _RE_LARGA.match(s, a)
            if m:
                self.i = m.end()
                return _Nodo('cadena', a, m.end(), m.group(2))
        if c.isdigit() or c in '-.':
            m = _RE_NUM.match(s, a)
            if not m:
                raise ValueError(f'número raro en {a}: {s[a:a + 30]!r}')
            self.i = m.end()
            return _Nodo('numero', a, m.end(), m.group(0))
        m = _RE_ID.match(s, a)
        if not m:
            raise ValueError(f'valor inesperado en {a}: {s[a:a + 30]!r}')
        self.i = m.end()
        if m.group(0) in ('true', 'false', 'nil'):
            return _Nodo('ident', a, m.end(), m.group(0))
        self._blanco()
        if s.startswith('()', self.i):
            self.i += 2
            self._blanco()
        if self.i < len(s) and s[self.i] == '{':
            t = self._tabla()
            return _Nodo('llamada', a, t.b, nombre=m.group(0), tabla=t)
        self.i = m.end()
        return _Nodo('ident', a, m.end(), m.group(0))

    def _tabla(self):
        s, a = self.s, self.i
        self.i += 1
        campos = []
        while True:
            self._blanco()
            c = s[self.i]
            if c == '}':
                self.i += 1
                return _Nodo('tabla', a, self.i, campos=campos)
            if c == '[' and not _RE_LARGA.match(s, self.i):
                self.i += 1
                k = self.valor()
                self._blanco()
                if s[self.i] != ']':
                    raise ValueError(f'clave sin cerrar en {self.i}')
                self.i += 1
                self._blanco()
                if s[self.i] != '=':
                    raise ValueError(f'falta «=» en {self.i}')
                self.i += 1
                campos.append(('[' + k.valor + ']', self.valor()))
            else:
                m = _RE_CAMPO.match(s, self.i)
                if m:
                    self.i = m.end()
                    campos.append((m.group(1), self.valor()))
                else:
                    campos.append((None, self.valor()))
            self._blanco()
            if s[self.i] in ',;':
                self.i += 1


def arbol(texto):
    """El árbol de la comp (las Tools de un clip). Lanza ValueError si el texto no tiene la forma de una tabla de Fusion."""
    lector = _Lector(texto)
    raiz = lector.valor()
    lector._blanco()
    if raiz.tipo != 'tabla' or texto[lector.i:].strip('\x00 \t\r\n'):
        raise ValueError('la comp no es una tabla de herramientas')
    return raiz


def herramientas(tabla, prefijo=''):
    """[(ruta, tipo, nodo)] de todas las herramientas, también las de dentro de macros y grupos («LuxeShine/Text1»)."""
    fuera = []
    for clave, v in tabla.pares():
        if clave is None or clave.startswith('[') or v.tipo != 'llamada':
            continue
        fuera.append((prefijo + clave, v.nombre, v))
        dentro = v.campo('Tools')
        if dentro is not None and dentro.tipo in ('llamada', 'tabla'):
            fuera.extend(herramientas(dentro, prefijo + clave + '/'))
    return fuera


def _num(v):
    v = round(float(v), 4)
    return '0' if abs(v) < 5e-5 else f'{v:.6g}'


def _numero(entrada):
    """El nodo número del Value de un Input («Value = 0.9» o «Value = Number { Value = 0.9 }»), o None."""
    if entrada is None or entrada.tipo != 'llamada':
        return None
    v = entrada.campo('Value')
    if v is not None and v.tipo == 'llamada' and v.nombre == 'Number':
        v = v.campo('Value')
    return v if (v is not None and v.tipo == 'numero') else None


def _tabla(nodo):
    return nodo.tabla if nodo.tipo == 'llamada' else nodo


def _publicados(raiz):
    """{clave: (nodo Default, valor, nodo del valor)} de los controles del PRIMER tool de la comp (el macro o el grupo que enseña el Inspector) que
    llevan un Default numérico y cuya entrada (SourceOp.Source; la de un «…Clone», CharacterSpacingClone -> CharacterSpacing) tiene un valor fijo.
    {} si no hay macro. `raiz` = arbol(texto)."""
    top = [v for k, v in raiz.pares() if k is not None and not k.startswith('[') and v.tipo == 'llamada']
    if not top or top[0].nombre not in ('MacroOperator', 'GroupOperator') or top[0].campo('Inputs') is None:
        return {}
    porn = {r.rsplit('/', 1)[-1]: n for r, _t, n in herramientas(raiz)}
    fuera = {}
    for clave, ii in _tabla(top[0].campo('Inputs')).pares():
        if clave is None or ii.tipo != 'llamada':
            continue
        d, so, src = ii.campo('Default'), ii.campo('SourceOp'), ii.campo('Source')
        if d is None or d.tipo != 'numero' or so is None or src is None or so.valor not in porn:
            continue
        ins = porn[so.valor].campo('Inputs')
        nombre = src.valor[:-len('Clone')] if src.valor.endswith('Clone') else src.valor
        entrada = _tabla(ins).campo(nombre) if ins is not None else None
        valor = _numero(entrada) if entrada is not None and entrada.campo('Expression') is None else None
        if valor is not None:
            fuera[clave] = (d, float(valor.valor), valor)
    return fuera


def reinicios_al_dia(antes, despues):
    """v5.58: los «reinicios» (Default) del Inspector tras un retoque. El Default de cada control que en `antes` valía lo mismo que su entrada (el
    valor del clip: macro_kinetic / inspector_luxe) pasa al valor nuevo de esa entrada en `despues` (el premium de construir_pack; «Crea tu estilo»
    hace lo mismo sin volver a leer la comp: _Retoque.reinicios); si no, la flecha de reiniciar volvía al color de fábrica. Los Default que ya eran
    distintos de su entrada (muchos de fábrica de Luxe y de Amro) no se tocan."""
    if antes == despues:
        return despues
    viejos = _publicados(arbol(antes))
    ediciones = []
    for clave, (d, valor, _n) in _publicados(arbol(despues)).items():
        if clave not in viejos:
            continue
        d_viejo, valor_viejo, _n = viejos[clave]
        if abs(float(d_viejo.valor) - valor_viejo) < 5e-5 and abs(float(d.valor) - valor) >= 5e-5:
            ediciones.append((d.a, d.b, _num(valor)))
    for a, b, nuevo in sorted(ediciones, reverse=True):
        despues = despues[:a] + nuevo + despues[b:]
    return despues


# ------------------------------------------------------------------------------------------------------------------ retoque de una comp
class _Retoque:
    """Las ediciones (posición, texto nuevo) de UNA comp y la lista de lo que cambió: (herramienta, entrada, antes, después)."""

    def __init__(self, texto, clip):
        self.texto, self.clip = texto, clip
        self.raiz = arbol(texto)
        self.lista = herramientas(self.raiz)
        self.tipos = {r: t for r, t, _ in self.lista}
        self.ediciones, self.cambios, self.notas = [], [], []

    def tool(self, ruta, tipo=None):
        """La herramienta de esa ruta («Template», «LuxeShine/Text1»). v5.57: un nombre suelto también vale dentro de un macro (el Tema 1 lleva
        toda su comp dentro del macro que enseña el Inspector: «CineCaptions/Template»); gana el de primer nivel si lo hay."""
        for r, t, n in self.lista:
            if r == ruta and (tipo is None or t == tipo):
                return n
        if '/' not in ruta:
            for r, t, n in self.lista:
                if r.rsplit('/', 1)[-1] == ruta and (tipo is None or t == tipo):
                    return n
        return None

    @staticmethod
    def entrada(tool, nombre):
        ins = tool.campo('Inputs') if tool is not None else None
        return ins.campo(nombre) if ins is not None else None

    # --- escribir
    def _editar(self, nodo, nuevo, ruta, entrada):
        viejo = self.texto[nodo.a:nodo.b]
        if viejo != nuevo:
            self.ediciones.append((nodo.a, nodo.b, nuevo))
            self.cambios.append((ruta, entrada, viejo, nuevo))

    def _poner_num(self, nodo, valor, ruta, entrada):
        if abs(float(nodo.valor) - round(float(valor), 4)) >= 5e-5:
            self._editar(nodo, _num(valor), ruta, entrada)

    def reinicios(self):
        """v5.58: el Default de cada control del Inspector que valía lo mismo que su entrada sigue a la edición de esa entrada (como
        reinicios_al_dia, pero con el árbol ya leído: los nodos Default van en el macro, nunca se pisan con las ediciones de las entradas)."""
        nuevos = {(a, b): nuevo for a, b, nuevo in self.ediciones}
        for d, valor, nodo in _publicados(self.raiz).values():
            nuevo = nuevos.get((nodo.a, nodo.b))
            try:
                nuevo = float(nuevo) if nuevo is not None else None
            except ValueError:
                continue
            if nuevo is not None and abs(float(d.valor) - valor) < 5e-5 and abs(nuevo - valor) >= 5e-5:
                self.ediciones.append((d.a, d.b, _num(nuevo)))

    def aplicar(self):
        texto = self.texto
        fin = len(texto) + 1
        for a, b, nuevo in sorted(self.ediciones, key=lambda e: e[0], reverse=True):
            if b > fin:
                raise ValueError(f'{self.clip}: dos cambios se pisan')
            texto = texto[:a] + nuevo + texto[b:]
            fin = a
        return texto

    # --- leer
    def trio(self, tool, n, con_expresion=False):
        """[nodo Red, nodo Green, nodo Blue] del elemento n, o None (falta alguno o va por expresión)."""
        nodos = []
        for canal in ('Red', 'Green', 'Blue'):
            e = self.entrada(tool, f'{canal}{n}')
            if e is None or (e.campo('Expression') is not None and not con_expresion):
                return None
            x = _numero(e)
            if x is None:
                return None
            nodos.append(x)
        return nodos

    def fondo(self, tool):
        nodos = []
        for canal in ('TopLeftRed', 'TopLeftGreen', 'TopLeftBlue'):
            e = self.entrada(tool, canal)
            if e is None or e.campo('Expression') is not None or _numero(e) is None:
                return None
            nodos.append(_numero(e))
        return nodos

    def tipo1(self, tool):
        x = _numero(self.entrada(tool, 'Type1'))
        return float(x.valor) if x is not None else 0.0

    def paradas(self, tool):
        """[(posición, [nodos r, g, b])] del ShadingGradient1, o None."""
        e = self.entrada(tool, 'ShadingGradient1')
        g = e.campo('Value') if e is not None else None
        if g is None or g.tipo != 'llamada' or g.nombre != 'Gradient':
            return None
        colores = g.campo('Colors')
        fuera = []
        for clave, v in (colores.pares() if colores is not None else []):
            if not clave or not clave.startswith('['):
                continue
            nums = [x for k, x in v.pares() if k is None]
            if len(nums) < 3 or any(x.tipo != 'numero' for x in nums[:3]):
                return None
            fuera.append((float(clave[1:-1]), nums[:3]))
        return fuera or None

    @staticmethod
    def valores(nodos):
        return tuple(float(x.valor) for x in nodos)

    def base_texto(self, tool):
        """El color BASE de un Text+: con degradado, la parada más cercana a la mitad de la letra (color_medio); si no, su relleno."""
        if self.tipo1(tool) == 2:
            par = self.paradas(tool)
            if par:
                return self.valores(min(par, key=lambda pn: (abs(pn[0] - 0.5), -pn[0]))[1])
        t = self.trio(tool, 1)
        return self.valores(t) if t else None

    # --- letra
    def letra(self, familia, estilo):
        for ruta, tipo, tool in self.lista:
            if tipo != 'TextPlus':
                continue
            f = self.entrada(tool, 'Font')
            if f is None or f.campo('Expression') is not None or f.campo('Value') is None or f.campo('Value').tipo != 'cadena':
                continue
            self._editar(f.campo('Value'), f'"{familia}"', ruta, 'Font')
            s = self.entrada(tool, 'Style')
            if s is None:                                        # (ningún pack de fábrica: todos traen Style) se añade detrás de Font
                coma = re.match(r'[ \t\r\n]*,', self.texto[f.b:])
                donde = f.b + (coma.end() if coma else 0)
                extra = f' Style = Input {{ Value = "{estilo}", }},' if coma else f', Style = Input {{ Value = "{estilo}", }}'
                self.ediciones.append((donde, donde, extra))
                self.cambios.append((ruta, 'Style', '', f'"{estilo}"'))
            elif s.campo('Expression') is None and s.campo('Value') is not None and s.campo('Value').tipo == 'cadena':
                self._editar(s.campo('Value'), f'"{estilo}"', ruta, 'Style')

    # --- color
    def _trio_derivado(self, ruta, tool, n, base, nuevo, brillo=False):
        t = self.trio(tool, n)
        if t is None:
            return
        actual = self.valores(t)
        if n > 1 and _oscuro(actual):
            return
        color = derivar_brillo(base, actual, nuevo) if brillo else derivar(base, actual, nuevo)
        for canal, x, v in zip(('Red', 'Green', 'Blue'), t, color):
            self._poner_num(x, v, ruta, f'{canal}{n}')

    def _fondo_derivado(self, ruta, base, nuevo):
        tool = self.tool(ruta, 'Background')
        t = self.fondo(tool) if tool is not None else None
        if t is None:
            return
        color = derivar(base, self.valores(t), nuevo)
        for canal, x, v in zip(('TopLeftRed', 'TopLeftGreen', 'TopLeftBlue'), t, color):
            self._poner_num(x, v, ruta, canal)

    def texto_coloreado(self, ruta, tool, base, nuevo, premium=False, elementos=True):
        """El relleno, el degradado y los brillos de un Text+ con el color nuevo."""
        self._trio_derivado(ruta, tool, 1, base, nuevo)
        if self.tipo1(tool) == 2:
            par = self.paradas(tool)
            if par:
                nuevas = None
                if premium:                                    # la principal Luxe: si es el «B · Premium» de fábrica, el mismo con el color nuevo
                    ref = degradado_premium(base)
                    if len(par) == len(ref) and all(abs(p - rp) < 1e-6 and max(abs(a - b) for a, b in zip(self.valores(nn), rc)) <= 0.002
                                                     for (p, nn), (rp, rc) in zip(par, ref)):
                        nuevas = [c for _, c in degradado_premium(nuevo)]
                for k, (pos, nodos) in enumerate(par):
                    color = nuevas[k] if nuevas else derivar(base, self.valores(nodos), nuevo)
                    for canal, x, v in zip('RGB', nodos, color):
                        self._poner_num(x, v, ruta, f'ShadingGradient1[{pos:g}].{canal}')
        if elementos:
            for n in range(2, 9):
                self._trio_derivado(ruta, tool, n, base, nuevo, brillo=True)

    def color_luxe(self, nuevo, rol):
        # el texto que se VE es el Text1 de dentro del macro Luxe (Shine / Slide / Count); el Template de arriba solo le pasa el texto
        texto = next(((r, n) for r, t, n in self.lista if t == 'TextPlus' and r.endswith('/Text1') and self.tipos.get(r.rsplit('/', 1)[0]) == 'MacroOperator'),
                     None)
        if texto is None:
            self.notas.append('sin macro Luxe (preset de Amro): conserva su color')
            return
        ruta, t1 = texto
        b = self.base_texto(t1)
        if b is None:
            self.notas.append('el Text1 del macro no trae su color')
            return
        self.texto_coloreado(ruta, t1, b, nuevo, premium=(rol == 'main'))
        tpl = self.tool('Template', 'TextPlus')
        if tpl is not None:
            self._trio_derivado('Template', tpl, 1, b, nuevo)
        trama = self.tool('Trama', 'Custom')
        if trama is not None:
            self._trama(trama, b, nuevo)

    def _trama(self, tool, base, nuevo):
        """La trama de puntos de la principal (Impacto): «r1 + (0.086 * a1 - r1) * …»: su color sale del de la letra."""
        nodos, valores = [], []
        for canal, v in (('Red', 'r'), ('Green', 'g'), ('Blue', 'b')):
            e = self.entrada(tool, f'{canal}Expression')
            cad = e.campo('Value') if e is not None else None
            m = re.match(rf'(\s*{v}1 \+ \()(-?\d*\.?\d+(?:[eE][+-]?\d+)?)( \* a1 - {v}1\))', cad.valor) if (cad is not None and cad.tipo == 'cadena') else None
            if not m:
                self.notas.append('la trama no tiene la forma esperada: conserva su color')
                return
            nodos.append((canal, cad, m))
            valores.append(float(m.group(2)))
        color = derivar(base, valores, nuevo)
        for (canal, cad, m), v in zip(nodos, color):
            if abs(float(m.group(2)) - v) >= 5e-5:
                a = cad.a + 1 + m.start(2)
                self.ediciones.append((a, a + len(m.group(2)), _num(v)))
                self.cambios.append(('Trama', f'{canal}Expression', m.group(2), _num(v)))

    def color_kinetic(self, nuevo):
        tpl = self.tool('Template', 'TextPlus')
        if self.clip.lower().startswith('k tape'):            # pegatinas: el color es el de la caja; el texto de encima, tinta o blanco
            caja = self.tool('Caja', 'Background')
            t = self.fondo(caja) if caja is not None else None
            if t is None:
                self.notas.append('la pegatina no trae su caja')
                return
            b = self.valores(t)
            for ruta in ('Caja', 'CajaLuz', 'CajaHonda', 'CajaVivoTinte'):
                self._fondo_derivado(ruta, b, nuevo)
            texto = self.trio(tpl, 1) if tpl is not None else None
            if texto is not None:
                import kinetic_paleta as PAL
                oscuro = _lum(_r4(nuevo)) > 0.55
                if (_lum(self.valores(texto)) < 0.5) != oscuro:
                    for canal, x, v in zip(('Red', 'Green', 'Blue'), texto, PAL.TINTA if oscuro else PAL.BLANCO):
                        self._poner_num(x, v, 'Template', f'{canal}1')
            return
        b = self.base_texto(tpl) if tpl is not None else None
        if b is None:
            self.notas.append('sin Template con color')
            return
        self.texto_coloreado('Template', tpl, b, nuevo)
        self._fondo_derivado('VivoTinte', b, nuevo)

    def color_viral(self, nuevo):
        tpl = self.tool('Template', 'TextPlus')
        if tpl is None:
            self.notas.append('sin Template')
            return
        if self.clip.lower().startswith('v linea'):          # v5.75: la línea con caja: el color es el de la CAJA (elemento 4); la letra sigue blanca
            caja = self.trio(tpl, 4) if 'activa' in self.clip.lower() else None
            if caja is not None:
                for canal, x, v in zip(('Red', 'Green', 'Blue'), caja, _r4(nuevo)):
                    self._poner_num(x, v, 'Template', f'{canal}4')
            return
        if self.clip.lower().startswith('v drag'):           # el relleno (elemento 2) va de gris oscuro a su color por expresión: «0.08 + 0.875 * …»
            t2 = self.trio(tpl, 2, con_expresion=True)
            if t2 is None:
                self.notas.append('el drag no trae su relleno')
                return
            b = self.valores(t2)
            color = _r4(nuevo)
            cad = self.entrada(tpl, 'Red2').campo('Expression')
            razon = re.search(r'Template\.Red1 / (\d*\.?\d+) \* (\d*\.?\d+)', cad.valor) if (cad is not None and cad.tipo == 'cadena') else None
            t1 = self.trio(tpl, 1)
            if razon and t1:                                  # v5.57: el relleno sigue al «Color» del Inspector (Red1, el contorno: × relleno / gris)
                k = float(razon.group(1)) / float(razon.group(2))
                for canal, x1, x2, v in zip(('Red', 'Green', 'Blue'), t1, t2, color):
                    self._poner_num(x1, v * k, 'Template', f'{canal}1')
                    self._poner_num(x2, v, 'Template', f'{canal}2')
                for n in range(3, 9):
                    self._trio_derivado('Template', tpl, n, b, nuevo, brillo=True)
                return
            self._trio_derivado('Template', tpl, 1, b, nuevo)
            for canal, x, v in zip(('Red', 'Green', 'Blue'), t2, color):
                self._poner_num(x, v, 'Template', f'{canal}2')
                cad = self.entrada(tpl, f'{canal}2').campo('Expression')
                m = re.match(r'(\s*)(-?\d*\.?\d+)( \+ )(-?\d*\.?\d+(?:[eE][+-]?\d+)?)( \* )', cad.valor) if (cad is not None and cad.tipo == 'cadena') else None
                if m is None:
                    raise ValueError(f'{self.clip}: la expresión del relleno ({canal}2) no tiene la forma esperada')
                coef = v - float(m.group(2))
                if abs(float(m.group(4)) - coef) >= 5e-5:
                    a = cad.a + 1 + m.start(4)
                    self.ediciones.append((a, a + len(m.group(4)), _num(coef)))
                    self.cambios.append(('Template', f'{canal}2.Expression', m.group(4), _num(coef)))
            for n in range(3, 9):
                self._trio_derivado('Template', tpl, n, b, nuevo, brillo=True)
            return
        b = self.base_texto(tpl)
        if b is None:
            self.notas.append('sin color en el Template')
            return
        self.texto_coloreado('Template', tpl, b, nuevo)
        bt = self.tool('BrilloTxt', 'TextPlus')                # el shatter: la copia clara de la letra y la luz del barrido
        if bt is not None:
            self._trio_derivado('BrilloTxt', bt, 1, b, nuevo)
        self._fondo_derivado('LuzFondo', b, nuevo)


def tipo_de(guion):
    """'kinetic' | 'viral' | 'luxe' (Referencia y Temas 4-6: sets arriba / principal / abajo con macros Luxe) según el 'guion' del pack."""
    return guion if guion in ('kinetic', 'viral') else 'luxe'


def rol_de(tipo, clip):
    """'main' (principal), 'extra' (arriba y abajo) o None (no es texto: aros, subrayados, imagen)."""
    n = str(clip or '').strip().lower()
    if tipo in ('kinetic', 'viral'):
        if n.startswith(('k ring', 'k line')):
            return None
        import fuente_usuario
        return 'main' if fuente_usuario.es_principal({'k': clip}) else 'extra'
    import packs_drt
    rol, _ = packs_drt.parsear_nombre(clip)
    return 'main' if rol in ('main', 'base') else 'extra' if rol in ('context', 'complement') else None


def retocar_tools(tools, tipo, clip, rol, ajuste):
    """Las Tools de UN clip con la letra y el color de su rol. ajuste = {'fuente': [familia, estilo] | None, 'color': (r, g, b) | None}.
    Devuelve (texto nuevo, cambios [(herramienta, entrada, antes, después)], notas)."""
    r = _Retoque(tools, clip)
    if ajuste.get('fuente'):
        r.letra(*ajuste['fuente'])
    if ajuste.get('color'):
        if tipo == 'kinetic':
            r.color_kinetic(ajuste['color'])
        elif tipo == 'viral':
            r.color_viral(ajuste['color'])
        else:
            r.color_luxe(ajuste['color'], rol)
    r.reinicios()
    return r.aplicar(), r.cambios, r.notas


# ------------------------------------------------------------------------------------------------------------------ el .drb
_ELEMENTO = re.compile(r'[ \t]*<Element>\s*<Sm2MpGenerator DbId="([^"]+)">.*?</Sm2MpGenerator>\s*</Element>\n?', re.S)
_NOMBRE = re.compile(r'<Name>(.*?)</Name>')
_BA = re.compile(r'(<CompositionBA>)([0-9a-fA-F]*)(</CompositionBA>)')


def tools_de_blob(hex_comp):
    """(cabecera, tools, partes) de un <CompositionBA>: BE32 + zlib(prefijo + BE32 + [cabecera 00 LE32 zlib(tools)] + resto)."""
    cab = zlib.decompress(binascii.unhexlify(hex_comp)[4:])
    i = cab.index(b'Composition {')
    n = struct.unpack('>I', cab[i - 4:i])[0]
    datos, resto = cab[i:i + n], cab[i + n:]
    j = datos.index(b'\x00')
    z = zlib.decompressobj()
    tools = z.decompress(datos[j + 5:])
    if not z.eof:
        raise ValueError('las Tools de la comp vienen cortadas')
    return datos[:j].decode('utf-8'), tools.decode('utf-8'), (cab[:i - 4], datos[:j], z.unused_data, resto)


def blob_con_tools(hex_comp, tools):
    """El mismo <CompositionBA> con otras Tools (prefijo, cabecera y lo que sigue, intactos)."""
    _, _, (prefijo, cabecera, sobra, resto) = tools_de_blob(hex_comp)
    tb = tools.encode('utf-8')
    datos = cabecera + b'\x00' + struct.pack('<I', len(tb)) + zlib.compress(tb, 9) + sobra
    cab = prefijo + struct.pack('>I', len(datos)) + datos + resto
    nuevo = binascii.hexlify(struct.pack('>I', len(cab)) + zlib.compress(cab, 6)).decode()
    return nuevo.upper() if re.search(r'[A-F]', hex_comp[:400]) else nuevo


def ruta_mpfolder(nombres):
    return next(n for n in nombres if n.endswith('MpFolder.xml') and '/Master/0' in '/' + n)


def retocar_drb(origen, destino, tipo, ajustes_rol, roles=None):
    """Copia el .drb `origen` en `destino` con la letra y el color de cada clip retocados. Devuelve {clip: {'cambios': [...], 'notas': [...]}}.
    `roles` (un set, opcional) recibe los roles de texto que hay en el .drb ('main', 'extra'), tengan ajuste o no."""
    informe = {}
    with zipfile.ZipFile(origen) as zin:
        infos = zin.infolist()
        ruta_xml = ruta_mpfolder([i.filename for i in infos])
        xml = zin.read(ruta_xml).decode('utf-8')
        trozos, ultimo = [], 0
        for m in _ELEMENTO.finditer(xml):
            bloque = m.group(0)
            nombre = _NOMBRE.search(bloque).group(1)
            ba = _BA.search(bloque)
            rol = rol_de(tipo, nombre)
            if rol and ba is not None and roles is not None:
                roles.add(rol)
            ajuste = (ajustes_rol.get(rol) or {}) if rol else {}
            if ba is None or not (ajuste.get('fuente') or ajuste.get('color')):
                continue
            _, tools, _ = tools_de_blob(ba.group(2))
            try:
                nuevas, cambios, notas = retocar_tools(tools, tipo, nombre, rol, ajuste)
            except ValueError as exc:
                raise ErrorPersonalizado(f'clip «{nombre}» de {Path(origen).name}: {exc}') from exc
            informe[nombre] = {'rol': rol, 'cambios': cambios, 'notas': notas}
            if nuevas == tools:
                continue
            hex_nuevo = blob_con_tools(ba.group(2), nuevas)
            a = m.start() + ba.start(2)
            trozos.append(xml[ultimo:a])
            trozos.append(hex_nuevo)
            ultimo = m.start() + ba.end(2)
        trozos.append(xml[ultimo:])
        nuevo_xml = ''.join(trozos)
        tmp = Path(str(destino) + '.tmp')
        with zipfile.ZipFile(tmp, 'w') as zout:
            for info in infos:
                datos = nuevo_xml.encode('utf-8') if info.filename == ruta_xml else zin.read(info.filename)
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)        # mismas fechas: el mismo ajuste da el mismo archivo
                zi.compress_type, zi.external_attr, zi.create_system = info.compress_type, info.external_attr, info.create_system
                zout.writestr(zi, datos)
    os.replace(tmp, destino)
    return informe


def _variantes(origen, destino, ajustes_rol):
    """<pack>.variantes.json con la letra, el color y el degradado nuevos (la vista y guion_captions.datos_variantes lo leen)."""
    import archivos_seguros
    datos = json.loads(Path(origen).read_text(encoding='utf-8'))
    principal = ajustes_rol['main']
    for var in datos.values():
        if not isinstance(var, dict):
            continue
        amro = bool(var.get('amro'))
        for rol, info in (var.get('roles') or {}).items():
            if not isinstance(info, dict):
                continue
            aj = ajustes_rol['main' if rol == 'main' else 'extra']
            if aj['fuente']:
                info['f1'], info['f2'] = list(aj['fuente']), list(aj['fuente'])
            if aj['color'] and not (rol == 'main' and amro):
                info['color'] = a_hex(aj['color'])
                if 'degradado' in info:
                    info['degradado'] = [[p, a_hex(c)] for p, c in degradado_premium(aj['color'])]
        if principal['color'] and not amro:
            var['color'] = a_hex(principal['color'])
    archivos_seguros.escribir_json(destino, datos, indent=1)


# ------------------------------------------------------------------------------------------------------------------ la caché
def carpeta_cache():
    import plantillas
    return Path(plantillas.CARPETA_CACHE_SETTINGS) / 'personalizados'


def _leer_json(ruta):
    try:
        datos = json.loads(Path(ruta).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def origen(nombre):
    """(carpeta, pack.json, {formato: .drb}) del tema de fábrica, con la misma regla que plantillas.buscar_pack: primero un pack del usuario con
    ese nombre (lo que GO usaría), si no el que viaja con el programa."""
    import plantillas
    candidatas = []
    try:
        candidatas.append(Path(plantillas.carpeta_de_packs()) / plantillas.nombre_seguro(nombre))
    except Exception:
        pass
    inc = plantillas.carpeta_incluida()
    if inc is not None:
        candidatas.append(Path(inc) / nombre)
    for carpeta in candidatas:
        datos = _leer_json(carpeta / 'pack.json')
        if not datos:
            continue
        drbs = {}
        for formato, bloque in (datos.get('formatos') or {}).items():
            if formato in ('h', 'v', 'c') and isinstance(bloque, dict) and bloque.get('drb'):
                ruta = Path(bloque['drb'])
                ruta = ruta if ruta.is_absolute() else carpeta / ruta
                if ruta.is_file():
                    drbs[formato] = ruta
        if drbs:
            return carpeta, datos, drbs
    raise ErrorPersonalizado(f'no encuentro el .drb del tema «{nombre}»')


def _sha1(ruta):
    return hashlib.sha1(Path(ruta).read_bytes()).hexdigest()


def acompanantes(drb):
    """Los archivos de fábrica que van junto a un .drb y que el derivado rehace o copia: <pack>.variantes.json (letra, tamaño, mayúsculas y color
    de cada variante: los lee el planificador) y <pack>.posiciones.json."""
    ruta = Path(drb)
    return [ruta.with_name(ruta.stem + sufijo) for sufijo in ('.variantes.json', '.posiciones.json')]


def huella(nombre, norm, drbs, datos=None):
    """La huella del derivado: TODO lo que entra en él. El tema y su REVISION_BIN, los ajustes, GENERADOR, lo que se copia del pack.json de origen
    (version, guion, formatos), el contenido de cada .drb y de sus acompañantes y el degradado premium de los colores elegidos (sale de luxe_macro).
    Si cambia cualquiera, otra carpeta y otro bin (un .variantes.json nuevo sin tocar el .drb ni REVISION_BIN ya no reutiliza el derivado viejo)."""
    import plantillas
    archivos = {}
    for formato in sorted(drbs):
        archivos[f'{formato}/drb'] = _sha1(drbs[formato])
        for ruta in acompanantes(drbs[formato]):
            archivos[f'{formato}/{ruta.name[len(Path(drbs[formato]).stem):]}'] = _sha1(ruta) if ruta.is_file() else None
    origen_ = {k: (datos or {}).get(k) for k in ('version', 'guion', 'formatos')}
    premium = {k: degradado_premium(a_rgb(norm[k])) for k in ('color_principal', 'color_secundario') if norm.get(k)}
    clave = {'base': nombre, 'revision': plantillas.REVISION_BIN.get(nombre, ''), 'ajustes': norm, 'generador': GENERADOR, 'archivos': archivos,
             'pack': origen_, 'premium': premium}
    return hashlib.sha1(json.dumps(clave, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')).hexdigest()


def nombre_pack(nombre, h):
    return f'{nombre}{SEPARADOR}{h[:8]}'


_RE_DERIVADO = re.compile(r'(.+)' + re.escape(SEPARADOR) + r'([0-9a-f]{8})')


def base_de(nombre_del_pack):
    """«VIRAL · a1b2c3d4» -> 'VIRAL' (el tema de un pack derivado); el nombre de un tema de fábrica se devuelve tal cual; None con cualquier otro pack.
    Compara el NOMBRE exacto, como plantillas (FABRICA, REVISION_BIN, buscar_pack): «Viral · superior/inferior» llevan «·» pero no son temas ni
    derivados, y un pack del usuario que se llame «viral» o «Tema 3» tampoco es el tema."""
    nombre = str(nombre_del_pack or '')
    m = _RE_DERIVADO.fullmatch(nombre)
    if m:
        nombre = m.group(1)
    return nombre if nombre in BASES.values() else None


def es_personalizado(nombre_del_pack):
    return bool(_RE_DERIVADO.fullmatch(str(nombre_del_pack or ''))) and base_de(nombre_del_pack) is not None


def _completa(carpeta, h):
    """¿Está en la carpeta el derivado de esa huella, entero y sano? La marca (se escribe la última) guarda el tamaño ('archivos') y el sha1 ('sha1')
    de cada archivo: uno que falta, cambió de tamaño o se estropeó aunque mida lo mismo (el disco, un programa que lo tocó) -> False y se rehace.
    Releerlo entero (de 130 KB en el Tema 4 a 1,2 MB en Referencia) suma 1-2 ms a cada preparar (medido: 3-5 ms en total al reutilizar)."""
    marca = _leer_json(Path(carpeta) / MARCA)
    if not marca or marca.get('huella') != h:
        return False
    archivos, sha1 = marca.get('archivos'), marca.get('sha1')
    if not isinstance(archivos, dict) or not archivos or not isinstance(sha1, dict) or set(sha1) != set(archivos):
        return False
    try:
        for n, tam in archivos.items():
            ruta = Path(carpeta) / n
            if ruta.stat().st_size != tam or _sha1(ruta) != sha1[n]:
                return False
    except OSError:
        return False
    return True


def _tocar(carpeta):
    try:
        os.utime(Path(carpeta) / MARCA, None)
    except OSError:
        pass


def _renombrar(origen_dir, destino_dir):
    for intento in range(10):                    # (en Windows el antivirus o el indexador pueden tener un archivo recién escrito abierto un instante)
        try:
            os.replace(origen_dir, destino_dir)
            return
        except PermissionError:
            if intento == 9:
                raise
            time.sleep(0.05 * (intento + 1))


def limpiar_cache(maximo=MAXIMO_CACHE, cache=None, conservar=None):
    """Borra los packs derivados menos usados de la caché (se rehacen igual si vuelven a pedirse) y los restos de armados a medias."""
    raiz = Path(cache) if cache else carpeta_cache()
    try:
        entradas = [d for d in raiz.iterdir() if d.is_dir()]
    except OSError:
        return
    ahora = time.time()
    vivas = []
    for d in entradas:
        if d.name.startswith('.') and d.name.endswith('.tmp'):
            try:
                if ahora - d.stat().st_mtime > 3600:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass
            continue
        try:
            vivas.append(((d / MARCA).stat().st_mtime, d))
        except OSError:
            continue
    vivas.sort(key=lambda x: x[0], reverse=True)
    limite = max(0, int(maximo))
    if conservar is not None:                       # la que se acaba de pedir se queda siempre (y cuenta dentro del máximo)
        vivas = [v for v in vivas if Path(v[1]) != Path(conservar)]
        limite = max(0, limite - 1)
    for _, d in vivas[limite:]:
        shutil.rmtree(d, ignore_errors=True)


def _armar(tmp, nombre, h, norm, datos_origen, drbs):
    import archivos_seguros
    import plantillas
    tipo = tipo_de(datos_origen.get('guion'))
    ajustes_rol = _por_rol(norm)
    resumen, roles = {}, set()
    for formato, ruta in sorted(drbs.items()):
        informe = retocar_drb(ruta, tmp / ruta.name, tipo, ajustes_rol, roles=roles)
        resumen[formato] = {clip: {'rol': i['rol'], 'cambios': len(i['cambios']), **({'notas': i['notas']} if i['notas'] else {})} for clip, i in informe.items()}
        var, pos = acompanantes(ruta)
        if var.is_file():
            _variantes(var, tmp / var.name, ajustes_rol)
        if pos.is_file():
            shutil.copyfile(pos, tmp / pos.name)
    pedidos = {rol for rol, aj in ajustes_rol.items() if aj['fuente'] or aj['color']}
    if not roles & pedidos:
        # (un pack del usuario que se llama como el tema pero no es él: p. ej. uno viejo sin «guion», cuyos clips «v …» se leerían como Luxe y no
        # tendrían rol. Saldría un «derivado» igual al de origen, sin avisar: mejor un error claro, y GO sigue con el pack de siempre)
        que = 'principal' if pedidos == {'main'} else 'secundario' if pedidos == {'extra'} else ''
        raise ErrorPersonalizado(f'el pack «{nombre}» de {next(iter(drbs.values())).parent} no tiene ningún texto {que + " " if que else ""}que se pueda '
                                 f'personalizar (guion={datos_origen.get("guion")!r}: ¿un pack viejo o importado con el nombre del tema?)')
    datos = {'version': datos_origen.get('version', 2), 'nombre': nombre_pack(nombre, h), 'formatos': {}}
    for formato, ruta in drbs.items():
        bloque = dict((datos_origen.get('formatos') or {}).get(formato) or {})
        bloque.pop('drt', None)
        bloque['drb'] = ruta.name
        datos['formatos'][formato] = bloque
    if datos_origen.get('guion'):
        datos['guion'] = datos_origen['guion']
    # (los datos del derivado van dentro de 'personalizado': un pack.json con 'base' y 'ajustes' es el ESTILO del usuario, no esta copia)
    datos['personalizado'] = {'base': nombre, 'ajustes': norm, 'huella': h, 'revision_base': plantillas.REVISION_BIN.get(nombre, ''), 'generador': GENERADOR}
    archivos_seguros.escribir_json(tmp / 'pack.json', datos, indent=2)
    hechos = sorted(p for p in tmp.iterdir() if p.is_file())
    # ('archivos' sigue siendo {nombre: tamaño}, como antes; el sha1 va aparte)
    archivos_seguros.escribir_json(tmp / MARCA, {'huella': h, 'base': nombre, 'archivos': {p.name: p.stat().st_size for p in hechos},
                                                 'sha1': {p.name: _sha1(p) for p in hechos}, 'clips': resumen}, indent=1)


def preparar(base, ajustes, cache=None, forzar=False):
    """La carpeta del pack DERIVADO de `base` (un tema: 'VIRAL', 't3', 'Tema 3' o un look de antes, 't3:shatter'…) con `ajustes`; None si los ajustes están vacíos.
    La primera vez lo arma (0,1-0,7 s medidos: llámalo en un hilo, nunca en el de la interfaz); luego lo reutiliza de la caché. Lanza ValueError si el tema no
    existe y ErrorPersonalizado si algo falla (quien llama sigue con el pack de fábrica y lo avisa en el Registro)."""
    norm = normalizar(ajustes)
    if not any(norm.values()):
        return None
    nombre = nombre_base(base)
    if nombre is None:
        raise ValueError(f'tema desconocido: {base!r}')
    _, datos_origen, drbs = origen(nombre)
    try:
        h = huella(nombre, norm, drbs, datos_origen)
    except OSError as exc:
        raise ErrorPersonalizado(f'no pude leer el pack de «{nombre}» ({type(exc).__name__}: {exc})') from exc
    raiz = Path(cache) if cache else carpeta_cache()
    destino = raiz / f'{nombre}-{h[:8]}'                   # carpeta ASCII (el nombre con «·» va dentro del pack.json)
    with _CANDADO:
        if not forzar and _completa(destino, h):
            _tocar(destino)
            return destino
        tmp = raiz / f'.{destino.name}.{os.getpid()}.{threading.get_ident()}.tmp'
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            tmp.mkdir(parents=True)
            _armar(tmp, nombre, h, norm, datos_origen, drbs)
            if destino.exists():
                if not forzar and _completa(destino, h):          # otro proceso (otra ventana del programa) lo terminó mientras tanto
                    shutil.rmtree(tmp, ignore_errors=True)
                    return destino
                shutil.rmtree(destino)                            # a medias (un corte) o forzado: se cambia por la nueva
            _renombrar(tmp, destino)
        except ErrorPersonalizado:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        except Exception as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            if _completa(destino, h):                          # otro proceso lo terminó a la vez
                return destino
            raise ErrorPersonalizado(f'no pude armar el pack personalizado de «{nombre}» ({type(exc).__name__}: {exc})') from exc
        limpiar_cache(cache=raiz, conservar=destino)
    return destino


# ------------------------------------------------------------------------------------------------------------------ para GO
def cargar(carpeta):
    """El plantillas.Pack del derivado (como cualquier pack: plantillas.cargar)."""
    import plantillas
    return plantillas.cargar(carpeta)


def para_manifiesto(carpeta, formato_forzado=None):
    """El campo 'plantilla' del manifiesto para el pack derivado de esa carpeta (lo arma plantillas.para_manifiesto, igual que para los de fábrica),
    con 'base' = el tema; {} si no se puede leer. El derivado vive en la caché, donde buscar_pack no mira: mientras se arma, buscar_pack lo
    encuentra por su nombre (y sigue igual para cualquier otro)."""
    import plantillas
    carpeta = Path(carpeta)
    pack = plantillas.cargar(carpeta)
    if pack is None or not pack.formatos:
        return {}
    meta = (_leer_json(carpeta / 'pack.json') or {}).get('personalizado') or {}
    with _CANDADO_MANIFIESTO:
        original = plantillas.buscar_pack

        def buscar(nombre, _original=original):
            return pack if nombre == pack.nombre else _original(nombre)
        plantillas.buscar_pack = buscar
        try:
            salida = plantillas.para_manifiesto(pack.nombre, formato_forzado)
        finally:
            plantillas.buscar_pack = original
    p = salida.get('plantilla') if isinstance(salida, dict) else None
    if isinstance(p, dict):
        p['base'] = meta.get('base') or base_de(pack.nombre)
    return salida


def plantilla(base, ajustes, formato_forzado=None, cache=None):
    """Atajo para GO: el dict 'plantilla' del derivado (preparar + para_manifiesto), o None con los ajustes vacíos."""
    carpeta = preparar(base, ajustes, cache=cache)
    if carpeta is None:
        return None
    return (para_manifiesto(carpeta, formato_forzado) or {}).get('plantilla')


if __name__ == '__main__':
    import argparse
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description='Arma el pack derivado de un tema con la letra y los colores elegidos.')
    ap.add_argument('base', help="t1…t6, «Tema N», un look de antes (t3:shatter) o el nombre del pack (Kinetic, Referencia, VIRAL, Tema4, Tema5, Tema6)")
    ap.add_argument('--fp', default='', help='fuente principal «Familia|Estilo»')
    ap.add_argument('--fs', default='', help='fuente secundaria')
    ap.add_argument('--cp', default='', help='color principal #RRGGBB')
    ap.add_argument('--cs', default='', help='color secundario')
    ap.add_argument('--cache', default=None, help='carpeta de la caché (por defecto ~/DaVinciSubtitles/plantillas_cache/personalizados)')
    ap.add_argument('--forzar', action='store_true')
    a = ap.parse_args()
    t0 = time.time()
    print(preparar(a.base, {'fuente_principal': a.fp, 'fuente_secundaria': a.fs, 'color_principal': a.cp, 'color_secundario': a.cs},
                   cache=a.cache, forzar=a.forzar), f'({time.time() - t0:.2f} s)')
