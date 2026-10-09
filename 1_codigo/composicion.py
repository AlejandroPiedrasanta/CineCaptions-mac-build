# CineCaptions · By Cinema Productions
# 1_codigo/composicion.py — Composición de los bloques dinámicos: layouts (alineación de contexto/complemento) y desplazamientos.
"""
composicion.py  (v3.4.0)
----------------------------------------------------------------------
La «Composición» de los bloques dinámicos: los LAYOUTS (la alineación
horizontal de contexto y complemento respecto a la principal) y los
desplazamientos Altura / Horizontal del grupo entero. Pedido del usuario con la
captura de otro plugin («COMPOSIÇÃO / LAYOUTS»): 9 formas + AUTO, y que se
aplique a los textos YA PUESTOS en el timeline desde el cabezal.

Lo que manda aqui:
  - El orden vertical lo sigue poniendo la plantilla (contexto arriba,
    principal en medio, complemento abajo). El layout solo dice a que borde
    de la PRINCIPAL se alinea cada linea de apoyo: 'i' (izquierda), 'c'
    (centro = donde la dejo la plantilla) o 'd' (derecha). Un layout son
    dos letras, (contexto, complemento): "ic" = contexto a la izquierda y
    complemento como la plantilla. "auto" = uno distinto por bloque.
  - "cc" con 0/0 ES la plantilla tal cual (la regla v1.0.32 sigue): sin
    composicion los gemelos no escriben NADA.
  - Los gemelos (CineCaptions_Subtitulos.lua / CineCaptions.py) llevan
    COPIAS de layout_del_bloque y desplazamiento_layout; test_v340 exige
    que den lo mismo que estas.
  - La base de cada clip NO se adivina: base = lo que el clip tiene AHORA
    menos lo que ya se le aplico (los 'tramos' del estado por timeline).
    Asi aplicar dos veces no acumula y un ajuste a mano en Resolve se
    conserva.
  - La recomposicion viaja como una ORDEN (composicion_pendiente.json +
    sidecar .lua para 21.1) por la accion 'subtitulos' de siempre: el
    gemelo la mira ANTES del manifiesto y, si es fresca, recompone en vez
    de colocar. Ni el Puente ni el bridge cambian.
"""
import json
import time
from pathlib import Path

import sfx_rules
import sidecar_lua

LADOS = ('i', 'c', 'd')
LAYOUTS = tuple(a + b for a in LADOS for b in LADOS)

# El anillo que recorre "auto" (un layout distinto por bloque)
ANILLO_AUTO = ('id', 'cc', 'di', 'ic', 'dd', 'ci', 'ii', 'cd', 'dc')
DEFECTO = {'layout': 'cc', 'altura': 0.0, 'horizontal': 0.0, 'semilla': 0}
TOPE = 0.4
ORDEN_VALE_S = 600
ARCHIVO_ESTADO = sfx_rules.CARPETA_USUARIO / 'composicion_estado.json'
ARCHIVO_ORDEN = sfx_rules.CARPETA_USUARIO / 'composicion_pendiente.json'


def valida(comp):
    """La composicion normalizada; cualquier rareza cae al defecto."""
    fuera = dict(DEFECTO)
    if not isinstance(comp, dict):
        return fuera
    layout = str(comp.get('layout') or 'cc').lower()
    if layout != 'auto' and layout not in LAYOUTS:
        layout = 'cc'
    fuera['layout'] = layout
    for clave in ('altura', 'horizontal'):
        try:
            v = float(comp.get(clave) or 0.0)
        except (TypeError, ValueError):
            v = 0.0
        fuera[clave] = max(-TOPE, min(TOPE, round(v, 4)))
    try:
        fuera['semilla'] = int(comp.get('semilla') or 0) % len(ANILLO_AUTO)
    except (TypeError, ValueError):
        fuera['semilla'] = 0
    return fuera


def es_defecto(comp):
    c = valida(comp)
    return c['layout'] == 'cc' and not c['altura'] and not c['horizontal']


def layout_del_bloque(comp, bloque):
    """El layout de ESE bloque: el fijo, o con 'auto' uno del anillo elegido
    por el FOTOGRAMA donde arranca el bloque (su primera linea). Por el
    fotograma y no por el indice: al recomponer, los bloques se cuentan en
    el timeline, y un bloque omitido al colocar (sin set) o borrado a mano
    correria los indices y la base «actual − anterior» saldria mal en
    AUTO. El floor(bloque / 9) rompe la periodicidad de 9 (bloques de 45
    fotogramas darian siempre el mismo). Gemela en los dos scripts."""
    c = valida(comp)
    if c['layout'] != 'auto':
        return c['layout']
    b = max(0, int(bloque or 0))
    return ANILLO_AUTO[(b + b // 9 + c['semilla']) % len(ANILLO_AUTO)]


def desplazamiento_layout(lado, w_main, w_linea):
    """Cuanto se corre una linea de apoyo (en las unidades de los anchos)
    para que su borde coincida con el de la principal: 'i' -> los bordes
    izquierdos juntos, 'd' -> los derechos, 'c' -> nada. Gemela en los dos
    scripts."""
    if lado == 'i':
        return -(float(w_main) - float(w_linea)) / 2.0
    if lado == 'd':
        return (float(w_main) - float(w_linea)) / 2.0
    return 0.0


def lados(layout):
    """('i'|'c'|'d' del contexto, idem del complemento)."""
    layout = str(layout or 'cc')
    if len(layout) != 2 or layout[0] not in LADOS or layout[1] not in LADOS:
        return ('c', 'c')
    return (layout[0], layout[1])


def cargar_estado():
    try:
        datos = json.loads(ARCHIVO_ESTADO.read_text(encoding='utf-8'))
        return datos if isinstance(datos, dict) else {}
    except Exception:
        return {}


def guardar_estado(datos):
    try:
        ARCHIVO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ARCHIVO_ESTADO.write_text(
            json.dumps(datos, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        pass


def tramos(clave):
    """[{"desde": frame, "composicion": {...}}, ...] de ese timeline, en
    orden; [] si nunca se compuso (= la plantilla tal cual)."""
    lista = cargar_estado().get(str(clave)) or []
    fuera = []
    for t in lista:
        if isinstance(t, dict) and isinstance(t.get('desde'), (int, float)):
            fuera.append({
                'desde': int(t['desde']),
                'composicion': valida(t.get('composicion')),
            })
    fuera.sort(key=lambda t: t['desde'])
    return fuera


def registrar_colocacion(clave, comp):
    """Una colocacion (generar/regenerar) deja clips frescos con LA
    composicion del manifiesto desde el bloque 0."""
    datos = cargar_estado()
    datos[str(clave)] = [{'desde': 0, 'composicion': valida(comp)}]
    guardar_estado(datos)


def registrar_aplicacion(clave, desde_frame, comp):
    """Un «Aplicar desde F»: los tramos desde F en adelante pasan a la
    composicion nueva; los de antes se quedan."""
    desde_frame = max(0, int(desde_frame or 0))
    lista = [t for t in tramos(clave) if t['desde'] < desde_frame]
    lista.append({'desde': desde_frame, 'composicion': valida(comp)})
    datos = cargar_estado()
    datos[str(clave)] = lista
    guardar_estado(datos)


def tramo_para(lista, frame):
    """La composicion que llevan los clips que empiezan en 'frame', o None
    si ninguna (clips de antes de la v3.4.0 o nunca compuestos)."""
    actual = None
    for t in (lista or []):
        if int(t.get('desde', 0)) <= int(frame):
            actual = t.get('composicion')
    return valida(actual) if actual is not None else None


def medidas_para_orden(cues):
    """{formato: {"rol|n": {texto: ancho_em}}} a partir de los cues ya
    medidos por emojis.medir_anchos_lineas (l['medidas'] = {formato:
    {'rol|n': ancho_em}}). El gemelo busca por el texto EXACTO que escribio
    en StyledText."""
    fuera = {}
    for cue in (cues or []):
        for l in (cue.get('lines') or []):
            texto = str(l.get('text') or '').strip()
            medidas = l.get('medidas')
            if not texto or not isinstance(medidas, dict):
                continue
            for formato, por_clave in medidas.items():
                if not isinstance(por_clave, dict):
                    continue
                destino = fuera.setdefault(str(formato), {})
                for clave, ancho in por_clave.items():
                    try:
                        destino.setdefault(str(clave), {})[texto] = round(float(ancho), 4)
                    except (TypeError, ValueError):
                        continue
    return fuera


def estilos_para_orden(estilos):
    """{formato: {"rol|n": {font, style, size}}} a partir de
    plantillas.estilos_para_medir: SOLO lo que el gemelo usa para reconocer
    un clip ya puesto por su estilo (v3.4.1: Resolve no etiqueta el clip del
    timeline con el nombre del clip del bin, y el tamaño del Text+ es la
    señal fiable). Sin color ni tracking: el sidecar va mas corto."""
    fuera = {}
    for formato, por_clave in (estilos or {}).items():
        if not isinstance(por_clave, dict):
            continue
        for clave, est in por_clave.items():
            if not isinstance(est, dict) or est.get('size') is None:
                continue
            try:
                size = round(float(est['size']), 4)
            except (TypeError, ValueError):
                continue
            fuera.setdefault(str(formato), {})[str(clave)] = {
                'font': str(est.get('font') or ''),
                'style': str(est.get('style') or ''),
                'size': size,
            }
    return fuera


def armar_orden(comp, desde, lista_tramos, medidas, language, estilos=None):
    return {
        'creada_en': time.time(),
        'version': 1,
        'desde': 'todo' if desde == 'todo' else 'cabezal',
        'nueva': valida(comp),
        'anterior': [
            {'desde': int(t['desde']), 'composicion': valida(t['composicion'])}
            for t in (lista_tramos or [])
        ],
        'medidas': medidas or {},
        'estilos': estilos_para_orden(estilos),
        'language': str(language or 'es'),
    }


def dejar_orden(orden):
    """El .json y su sidecar .lua (21.1 lee con loadfile)."""
    ARCHIVO_ORDEN.parent.mkdir(parents=True, exist_ok=True)
    sidecar_lua.escribir_par(ARCHIVO_ORDEN, orden)
    return ARCHIVO_ORDEN


def retirar_orden():
    """Fuera la orden y su sidecar (exito o fallo: una orden huerfana no
    puede convertir el proximo clic de colocar en una recomposicion)."""
    for f in (ARCHIVO_ORDEN, ARCHIVO_ORDEN.with_name(ARCHIVO_ORDEN.name + '.lua')):
        try:
            f.unlink()
        except OSError:
            pass


def orden_fresca(orden, ahora=None):
    """Lo mismo que decide el gemelo: solo vale una orden de menos de
    ORDEN_VALE_S segundos."""
    try:
        edad = (ahora or time.time()) - float(orden.get('creada_en') or 0)
        return -5 <= edad <= ORDEN_VALE_S
    except (TypeError, ValueError):
        return False


if __name__ == '__main__':
    assert valida(None) == DEFECTO and es_defecto({})
    assert estilos_para_orden({
        'v': {
            'main|1': {'font': 'A', 'style': 'B', 'size': 0.12345, 'color': [1]},
            'x|1': {'font': 'A'},
        },
    }) == {'v': {'main|1': {'font': 'A', 'style': 'B', 'size': 0.1235}}}
    assert armar_orden({}, 'todo', [], {}, 'es')['estilos'] == {}
    assert valida({'layout': 'ID', 'altura': 9, 'horizontal': 'x'}) == {
        'layout': 'id', 'altura': TOPE, 'horizontal': 0.0, 'semilla': 0}
    assert layout_del_bloque({'layout': 'di'}, 7) == 'di'
    assert layout_del_bloque({'layout': 'auto'}, 0) == ANILLO_AUTO[0]
    assert layout_del_bloque({'layout': 'auto', 'semilla': 2}, 0) == ANILLO_AUTO[2]
    assert len({layout_del_bloque({'layout': 'auto'}, 45 * k)
                for k in range(9)}) >= 6, 'AUTO tiene que variar entre bloques'
    assert len({layout_del_bloque({'layout': 'auto'}, 30 * k)
                for k in range(9)}) >= 6
    assert desplazamiento_layout('i', 100, 40) == -30
    assert desplazamiento_layout('d', 100, 40) == 30
    assert desplazamiento_layout('c', 100, 40) == 0
    assert lados('id') == ('i', 'd') and lados('auto') == ('c', 'c')
    lista = [
        {'desde': 0, 'composicion': DEFECTO},
        {'desde': 90, 'composicion': {'layout': 'ii'}},
    ]
    assert tramo_para(lista, 89)['layout'] == 'cc'
    assert tramo_para(lista, 90)['layout'] == 'ii'
    assert tramo_para([], 5) is None
    cues = [{'lines': [{'role': 'context', 'text': 'Vas a',
                        'medidas': {'v': {'context|1': 0.31, 'context|2': 0.3}}}]}]
    assert medidas_para_orden(cues) == {
        'v': {'context|1': {'Vas a': 0.31}, 'context|2': {'Vas a': 0.3}}}
    o = armar_orden({'layout': 'auto'}, 'cabezal', lista, {}, 'es')
    assert o['desde'] == 'cabezal' and o['nueva']['layout'] == 'auto'
    assert orden_fresca(o) and not orden_fresca({'creada_en': 0})
    print('composicion.py: OK')
