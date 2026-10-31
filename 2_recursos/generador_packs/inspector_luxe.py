# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/inspector_luxe.py — v5.57: las captions con macro Luxe (Temas 2, 4, 5 y 6) enseñan en el Inspector los controles del
# macro con SOLO el banner de CineCaptions arriba, como el Tema 1 (macro_kinetic).
"""
Pedido: «UTILIZA LAS HERRAMIENTAS DE LUXE SLIDE Y SOLO LE PONES EL BANNER» (Tema 1) y «Sí, en los 6». El Inspector del Edit enseña el PRIMER tool de
la comp (banner_inspector). En los packs con Luxe era el Text+ «Template» (el texto que escribe la app; el Text1 del macro lo lee por expresión): salía
el Text+ en bruto. Aquí se RETOCA el texto de Tools (los Temas 4-6 llevan el Luxe de antes de la v1.09: no se regeneran), con ediciones por POSICIÓN
sobre el lector de pack_personalizado; lo demás queda byte a byte:
  1. el Text+ «Template» entra como PRIMER tool del macro (LuxeSlide / LuxeShine / LuxeCount), sin su banner: así el macro es el primer tool. Las
     curvas (LUTLookup / LUTBezier), los AudioDisplay, la trama y MediaOut1 siguen fuera, como en el .setting de Luxe. La app sigue encontrando el
     Template con FindTool("Template") (probado dentro de un macro con el Tema 1) y las expresiones van por nombre (el Text1 lee Template.StyledText).
     Va el primero dentro del macro para seguir siendo el primer «= TextPlus {» del texto (packs_drt._estilo_de_comp y los bucles del primer Text+);
  2. el texto del Inspector, EDITABLE: Input1 publica Template.StyledText (era Text1.StyledText, que va por expresión). El Luxe Count no tiene caja
     de texto (su cifra sale del texto): se le añade ese Input1 arriba;
  3. la cabecera de Van Beek (headerLogo / headerLabel / Website: los UserControls del propio macro) -> banner_inspector.LABEL (el logo, encima de
     las pestañas); fuera el CCBanner de texto (su InstanceInput y el del Text1) y el del Template (dentro del macro no se ve);
  4. con el auto-ajuste del tamaño de luxe_macro (`tam*math.min(1, 0.86/...)`), la base pasa a Template.Size y el «Size» publicado es ese: se puede
     cambiar y el texto largo se sigue encogiendo solo;
  5. el «reinicio» de Size, Tracking, interlineado y Color = el valor del clip (como macro_kinetic), no el de fábrica de Luxe.
No cambia ninguna entrada de ninguna tool (el render es el mismo), ni las conexiones, la animación, las curvas, MediaOut1 o los nombres. Quedan con su
expresión (se ven pero no se arrastran): Length / Length In / Length Out del Tema 2 (nunca más que el clip) y lo del Count que sale del texto. Los 4
principales de Amro de la Referencia («principal 3/6/7/8»: un GroupOperator primero, sin Template; la app escribe en su Text1) llevan el banner en
los UserControls del grupo.

    estado(tools) -> 'luxe' | 'amro' | 'ya' | 'otro'
    al_inspector(tools) / banner_en_grupo(tools) / retocar(tools) -> tools      (idempotentes)
    comprobar(antes, despues) -> [errores]
    retocar_drb(origen, destino=None) -> {clip: estado}     sin destino, en el sitio; no escribe nada si alguna comp no pasa comprobar
    python inspector_luxe.py <.drb>...
"""
import functools
import os
import re
import sys
import zipfile
from pathlib import Path

for _p in (os.path.dirname(os.path.abspath(__file__)), os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '1_codigo')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import banner_inspector as BI           # noqa: E402  LABEL (el banner con el logo), NOMBRE = 'CCBanner', LABEL_TEXTO
import pack_personalizado as PP         # noqa: E402  el lector con posiciones (arbol / herramientas / tools_de_blob / blob_con_tools)

_arbol = functools.lru_cache(maxsize=8)(PP.arbol)       # (la misma comp se lee varias veces: estado, retoque, comprobar)
TEXTO = 'Template'
MACROS = ('LuxeSlide', 'LuxeShine', 'LuxeCount')
CABECERA_VB = ('headerLogo', 'headerLabel', 'Website')
_AJUSTE = re.compile(r'(?P<t>[0-9.]+)\*math\.min\(1, 0\.86/math\.max\(0\.0001, \(tostring\(Template\.StyledText\.Value\):len\(\) \* 0\.80 \* '
                     r'(?P=t) \* 640 / 1080\)\)\)')


# ------------------------------------------------------------------------------------------------------------------------------ lectura
def _tools(nodo):
    """[(nombre, nodo)] de las tools de una tabla de Tools (la raíz o el «Tools = ordered() {» de un macro)."""
    return [(k, v) for k, v in nodo.pares() if k is not None and not k.startswith('[') and v.tipo == 'llamada']


def _campos(nodo):
    return [(k, v) for k, v in nodo.pares() if k is not None] if nodo is not None else []


def _tabla(nodo):
    """El nodo tabla de un valor («ordered() { … }» o «{ … }»)."""
    return nodo.tabla if nodo.tipo == 'llamada' else nodo


def _ini_clave(t, clave, nodo):
    """Dónde empieza «clave = » delante del valor `nodo`."""
    trozo = t[max(0, nodo.a - len(clave) - 40):nodo.a]
    m = re.search(r'(?<![\w])' + re.escape(clave) + r'[ \t\r\n]*=[ \t\r\n]*$', trozo)
    if not m:
        raise ValueError(f'inspector_luxe: no encuentro «{clave} =» delante de su valor')
    return nodo.a - (len(trozo) - m.start())


_COLA = re.compile(r'[ \t\r\n]*,?[ \t\r\n]*')


def _quitar_campo(t, clave, nodo):
    """(ini, fin) del campo «clave = valor,» entero, con su coma y los blancos que siguen (para borrarlo)."""
    return _ini_clave(t, clave, nodo), _COLA.match(t, nodo.b).end()


def _num(nodo_input):
    """El número del Value de un «Input { Value = n, }» sin expresión, o None."""
    if nodo_input is None or nodo_input.tipo != 'llamada' or nodo_input.campo('Expression') is not None:
        return None
    x = PP._numero(nodo_input)
    return x.valor if x is not None else None


def _al_final(t, tabla, texto):
    """La edición que añade «texto» (un campo «X = …, ») al final de una tabla, con su coma delante si hace falta."""
    cierre = tabla.b - 1                                                  # la llave que la cierra
    antes = t[tabla.a:cierre].rstrip()
    return (cierre, cierre, ('' if antes.endswith((',', '{')) else ', ') + texto)


def _aplicar(t, ediciones):
    fin = len(t) + 1
    for a, b, nuevo in sorted(ediciones, key=lambda e: (e[0], e[1]), reverse=True):
        if b > fin:
            raise ValueError('inspector_luxe: dos cambios se pisan')
        t = t[:a] + nuevo + t[b:]
        fin = a
    return t


def _uc_con_banner(nodo):
    uc = nodo.campo('UserControls')
    return uc is not None and any(k == BI.NOMBRE for k, _ in _campos(_tabla(uc)))


def estado(tools):
    """'luxe' (Template + macro Luxe, sin retocar) | 'amro' (grupo primero sin banner) | 'ya' (el primer tool lleva el banner) | 'otro'."""
    top = _tools(_arbol(tools))
    if not top:
        return 'otro'
    n0, v0 = top[0]
    if v0.nombre in ('MacroOperator', 'GroupOperator') and _uc_con_banner(v0):
        return 'ya'
    nombres = [n for n, _ in top]
    if n0 == TEXTO and v0.nombre == 'TextPlus' and len(top) > 1 and top[1][1].nombre == 'MacroOperator' and top[1][0] in MACROS \
            and nombres.count(TEXTO) == 1:
        return 'luxe'
    if v0.nombre == 'GroupOperator' and TEXTO not in nombres:
        return 'amro'
    return 'otro'


# ------------------------------------------------------------------------------------------------------------------------------- Luxe
def _template_sin_banner(t, tpl, k0):
    """El texto «Template = TextPlus { … }» sin el banner que le puso banner_inspector.con_banner (dentro del macro no se ve)."""
    uc = tpl.campo('UserControls')
    if uc is None:
        return t[k0:tpl.b]
    entradas = _campos(_tabla(uc))
    if [k for k, _ in entradas] == [BI.NOMBRE]:                       # solo el banner: fuera el UserControls entero (lo que añadió _con_label)
        a, b = _quitar_campo(t, 'UserControls', uc)
    else:
        nodo = next((v for k, v in entradas if k == BI.NOMBRE), None)
        if nodo is None:
            return t[k0:tpl.b]
        a, b = _quitar_campo(t, BI.NOMBRE, nodo)
    return t[k0:a] + t[b:tpl.b]


def _ii(clave, tool, entrada):
    return f'{clave} = InstanceInput {{ SourceOp = "{tool}", Source = "{entrada}", }}, '


def _poner_default(t, ii, valor, ediciones):
    """El «Default» (el reinicio del control) de un InstanceInput = valor."""
    d = ii.campo('Default')
    if d is not None:
        if d.tipo == 'numero' and abs(float(d.valor) - float(valor)) >= 5e-5:
            ediciones.append((d.a, d.b, PP._num(valor)))
    else:
        ediciones.append(_al_final(t, ii.tabla, f'Default = {PP._num(valor)}, '))


def al_inspector(tools, tam_editable=True, reinicio=True):
    """Las Tools de una comp Luxe (Template + LuxeSlide/LuxeShine/LuxeCount + curvas + MediaOut1) con el macro de primer tool, el Template dentro
    y primero, el texto del Inspector editable y SOLO el banner de CineCaptions arriba. Lanza ValueError si la comp no tiene la forma esperada."""
    que = estado(tools)
    if que == 'ya':
        return BI.con_banner(tools)                                       # (idempotente: solo el banner al día)
    if que != 'luxe':
        raise ValueError(f'inspector_luxe: no es una comp Luxe con el Template delante ({que})')
    t = tools
    top = _tools(_arbol(t))
    tpl = top[0][1]
    nm, mac = top[1]
    porn = dict(_tools(_tabla(mac.campo('Tools'))))
    if 'Text1' not in porn or porn['Text1'].nombre != 'TextPlus' or TEXTO in porn:
        raise ValueError(f'inspector_luxe: el macro {nm} no trae su Text1 (o ya trae un Template)')
    ed = []
    # 1) el Template sale del primer nivel y entra como PRIMER tool del macro (sin su banner)
    k0 = _ini_clave(t, TEXTO, tpl)
    ed.append((k0, _COLA.match(t, tpl.b).end(), ''))
    tabla_tools = _tabla(mac.campo('Tools'))
    ed.append((tabla_tools.a + 1, tabla_tools.a + 1, ' ' + _template_sin_banner(t, tpl, k0) + ','))
    # 2) lo publicado: fuera el CCBanner de texto; Input1 = Template.StyledText (editable)
    ins = _tabla(mac.campo('Inputs'))
    publicadas = _campos(ins)
    claves = [k for k, _ in publicadas]
    cc = dict(publicadas).get(BI.NOMBRE)
    nuevo_input1 = '' if 'Input1' in claves else _ii('Input1', TEXTO, 'StyledText')     # (Luxe Count: sin caja de texto propia)
    if cc is not None:
        a, b = _quitar_campo(t, BI.NOMBRE, cc)
        ed.append((a, b, nuevo_input1))
    elif nuevo_input1:
        ed.append((ins.a + 1, ins.a + 1, ' ' + nuevo_input1.rstrip()))
    if 'Input1' in claves:
        i1 = dict(publicadas)['Input1']
        so, src = i1.campo('SourceOp'), i1.campo('Source')
        if src is None or src.valor != 'StyledText' or so is None or so.valor not in ('Text1', TEXTO):
            raise ValueError(f'inspector_luxe: Input1 de {nm} no es el texto ({so and so.valor}.{src and src.valor})')
        if so.valor != TEXTO:
            ed.append((so.a, so.b, f'"{TEXTO}"'))
    # 3) Text1: fuera su CCBanner de texto (lo publicaba el InstanceInput de arriba)
    t1 = porn['Text1']
    uc1 = t1.campo('UserControls')
    if uc1 is not None:
        nodo = dict(_campos(_tabla(uc1))).get(BI.NOMBRE)
        if nodo is not None:
            ed.append(_quitar_campo(t, BI.NOMBRE, nodo) + ('',))
    # 4) la cabecera de Van Beek (UserControls del propio macro) -> solo el banner de CineCaptions
    uc = mac.campo('UserControls')
    if uc is not None:
        claves_uc = [k for k, _ in _campos(_tabla(uc))]
        if any(k not in CABECERA_VB + (BI.NOMBRE,) for k in claves_uc):
            raise ValueError(f'inspector_luxe: UserControls inesperados en {nm}: {claves_uc}')
        tb = _tabla(uc)
        ed.append((tb.a, tb.b, '{ ' + BI.LABEL + '}'))
    else:
        ed.append(_al_final(t, mac.tabla, 'UserControls = ordered() { ' + BI.LABEL + '}, '))
    # 5) el auto-ajuste del tamaño con la base en Template.Size: el «Size» del Inspector se puede cambiar
    sc = porn.get('sizeCtrl')
    rs = _tabla(sc.campo('Inputs')).campo('RestingSize') if sc is not None and sc.campo('Inputs') is not None else None
    base_tam = _num(rs)
    ex = rs.campo('Expression') if rs is not None and rs.tipo == 'llamada' else None
    publica_tam = ('sizeCtrl', 'RestingSize')
    if tam_editable and ex is not None:
        m = _AJUSTE.fullmatch(ex.valor)
        tam_tpl = _num(_tabla(tpl.campo('Inputs')).campo('Size'))
        if m and tam_tpl is not None and abs(float(m.group('t')) - float(tam_tpl)) < 5e-5:
            ed.append((ex.a, ex.b, '"' + _con_base(ex.valor, m.group('t')) + '"'))
            publica_tam = (TEXTO, 'Size')
            base_tam = tam_tpl
            for k, ii in publicadas:
                so, src = ii.campo('SourceOp'), ii.campo('Source')
                if so is not None and src is not None and so.valor == 'sizeCtrl' and src.valor == 'RestingSize':
                    ed.append((so.a, so.b, f'"{TEXTO}"'))
                    ed.append((src.a, src.b, '"Size"'))
    # 6) el reinicio de cada control = el valor del clip (Size, Tracking, interlineado, Color)
    if reinicio:
        ins1 = _tabla(t1.campo('Inputs'))
        valores = {('sizeCtrl', 'RestingSize'): base_tam, (TEXTO, 'Size'): base_tam,
                   ('Text1', 'CharacterSpacingClone'): _num(ins1.campo('CharacterSpacing')),
                   ('Text1', 'LineSpacingClone'): _num(ins1.campo('LineSpacing')),
                   ('Text1', 'Red1'): _num(ins1.campo('Red1')), ('Text1', 'Green1'): _num(ins1.campo('Green1')),
                   ('Text1', 'Blue1'): _num(ins1.campo('Blue1'))}
        for k, ii in publicadas:
            so, src = ii.campo('SourceOp'), ii.campo('Source')
            if so is None or src is None:
                continue
            clave = (so.valor, src.valor)
            v = valores.get(publica_tam if clave == ('sizeCtrl', 'RestingSize') else clave)
            if v is not None:
                _poner_default(t, ii, v, ed)
    return _aplicar(t, ed)


def _con_base(expresion, tam):
    """La expresión del auto-ajuste con Template.Size en vez del tamaño fijo `tam` (en sus dos apariciones)."""
    return expresion.replace(tam + '*', 'Template.Size*', 1).replace('* ' + tam + ' *', '* Template.Size *', 1)


# ------------------------------------------------------------------------------------------------------------------------------- Amro
def banner_en_grupo(tools):
    """Los cuatro principales de Amro (Referencia «principal 3/6/7/8»: un GroupOperator primero, sin Template): el banner con el logo en los
    UserControls del propio grupo, encima de sus controles. Idempotente."""
    que = estado(tools)
    if que == 'ya':
        return BI.con_banner(tools)
    if que != 'amro':
        raise ValueError(f'inspector_luxe: no es un grupo de Amro ({que})')
    _, grupo = _tools(_arbol(tools))[0]
    uc = grupo.campo('UserControls')
    if uc is not None:                                                    # (ninguno de fábrica lo trae) delante de los que ya tenga
        tb = _tabla(uc)
        return tools[:tb.a + 1] + ' ' + BI.LABEL + tools[tb.a + 1:]
    return _aplicar(tools, [_al_final(tools, grupo.tabla, 'UserControls = ordered() { ' + BI.LABEL + '}, ')])


def retocar(tools):
    """(tools, estado): la comp Luxe con el macro primero, el grupo de Amro con su banner; las demás, tal cual."""
    que = estado(tools)
    if que == 'luxe':
        return al_inspector(tools), que
    if que == 'amro':
        return banner_en_grupo(tools), que
    if que == 'ya':
        return BI.con_banner(tools), que
    return tools, que


# ------------------------------------------------------------------------------------------------------------------------- comprobar
def _nombre(ruta):
    return ruta.rsplit('/', 1)[-1]


def _todos_los_nombres(tabla):
    """Los nombres de TODAS las tools y modificadores, también los de clave entre corchetes (["Follower1Tamaño"] = BezierSpline, que
    PP.herramientas salta) y los de dentro de macros y grupos."""
    fuera = set()
    for k, v in tabla.pares():
        if k is None or v.tipo != 'llamada':
            continue
        fuera.add(k[1:-1].strip('"') if k.startswith('[') else k)       # (el lector guarda ["X"] como «[X]»)
        dentro = v.campo('Tools')
        if dentro is not None and dentro.tipo in ('llamada', 'tabla'):
            fuera |= _todos_los_nombres(dentro)
    return fuera


def _conexiones(tools):
    """[(tool, entrada, SourceOp)] de todas las entradas conectadas (Input { SourceOp = … })."""
    fuera = []
    for r, _tipo, nodo in PP.herramientas(_arbol(tools)):
        ins = nodo.campo('Inputs')
        if ins is None:
            continue
        for k, v in _campos(_tabla(ins)):
            if v.tipo == 'llamada' and v.nombre == 'Input' and v.campo('SourceOp') is not None:
                fuera.append((_nombre(r), k, v.campo('SourceOp').valor))
    return sorted(fuera)


def _publicado_igual(s):
    """Una entrada publicada sin lo que cambia a propósito (el reinicio y lo que pasa del Text1 / sizeCtrl al Template)."""
    s = re.sub(r'Default = [-0-9.eE+]+, ', '', s)
    s = s.replace('SourceOp = "Template", Source = "StyledText"', 'SourceOp = "Text1", Source = "StyledText"')
    return s.replace('SourceOp = "Template", Source = "Size"', 'SourceOp = "sizeCtrl", Source = "RestingSize"')


def comprobar(antes, despues):
    """Los errores de la comp retocada (lista vacía = bien): el render no cambia y el Inspector enseña lo que debe."""
    try:
        raiz = _arbol(despues)
    except ValueError as exc:
        return [f'no se lee: {exc}']
    que = estado(antes)
    top = _tools(raiz)
    n0, v0 = top[0]
    ra = {r: (tipo, nodo) for r, tipo, nodo in PP.herramientas(_arbol(antes))}
    rd = {r: (tipo, nodo) for r, tipo, nodo in PP.herramientas(raiz)}
    err = []
    # las mismas tools (nombre y tipo) y ningún nombre repetido
    if sorted((_nombre(r), t) for r, (t, _) in ra.items()) != sorted((_nombre(r), t) for r, (t, _) in rd.items()):
        err.append('cambian las tools')
    if len({_nombre(r) for r in rd}) != len(rd):
        err.append('nombres de tool repetidos')
    # TODAS las entradas de las tools iguales (texto exacto), salvo el auto-ajuste del tamaño: el render no cambia
    ina = {_nombre(r): n.campo('Inputs') for r, (t, n) in ra.items()}
    for r, (t, n) in rd.items():
        x = n.campo('Inputs')
        if t in ('MacroOperator', 'GroupOperator') or x is None:
            continue
        y = ina.get(_nombre(r))
        ta, td = (antes[y.a:y.b] if y is not None else None), despues[x.a:x.b]
        if ta != td:
            m = _AJUSTE.search(ta or '')
            if not (_nombre(r) == 'sizeCtrl' and m and td == ta.replace(m.group(0), _con_base(m.group(0), m.group('t')))):
                err.append(f'cambian las entradas de {_nombre(r)}')
    # las mismas conexiones, todas a tools que existen
    cd = _conexiones(despues)
    if _conexiones(antes) != cd:
        err.append('cambian las conexiones')
    nombres = _todos_los_nombres(raiz)
    err += [f'{tool}.{entrada} <- {so}: no existe' for tool, entrada, so in cd if so not in nombres]
    if v0.nombre not in ('MacroOperator', 'GroupOperator'):
        return err + [f'el primer tool es {n0}:{v0.nombre}']
    # cada SourceOp publicado existe (dentro del macro o, como las curvas de Luxe, a primer nivel)
    for k, ii in _campos(_tabla(v0.campo('Inputs'))):
        so = ii.campo('SourceOp')
        if so is None or so.valor not in nombres:
            err.append(f'{n0}.{k} publica {so and so.valor}: no existe')
        elif so.valor == TEXTO and _tabla(rd[f'{n0}/{TEXTO}'][1].campo('Inputs')).campo(ii.campo('Source').valor) is None:
            err.append(f'{n0}.{k} publica Template.{ii.campo("Source").valor}: el Template no la trae')
    # el macro / grupo: Outputs, ViewInfo, CustomData y CtrlWZoom iguales; lo publicado, igual salvo lo que cambia a propósito
    ma = _arbol(antes).campo(n0)
    for campo in ('Outputs', 'ViewInfo', 'CustomData', 'CtrlWZoom'):
        x, y = ma.campo(campo), v0.campo(campo)
        if (x is None) != (y is None) or (x is not None and antes[x.a:x.b] != despues[y.a:y.b]):
            err.append(f'cambia {n0}.{campo}')
    pa = dict(_campos(_tabla(ma.campo('Inputs'))))
    for k, ii in _campos(_tabla(v0.campo('Inputs'))):
        if k in pa and _publicado_igual(antes[pa[k].a:pa[k].b]) != _publicado_igual(despues[ii.a:ii.b]):
            err.append(f'cambia la entrada publicada {k}')
    # el banner: UNO, el del logo, en los UserControls del primer tool; nada de la cabecera de Van Beek ni del CCBanner de texto
    if despues.count(BI.NOMBRE + ' = {') != 1 or BI.LABEL not in despues or not _uc_con_banner(v0):
        err.append('el banner no está solo en el primer tool')
    if BI.NOMBRE + ' = InstanceInput' in despues or BI.LABEL_TEXTO in despues:
        err.append('queda el CCBanner de texto')
    err += [f'queda {k}' for k in CABECERA_VB if re.search(r'\b' + k + r' = \{', despues)]
    if que == 'luxe':
        if f'{n0}/{TEXTO}' not in rd or _tools(_tabla(v0.campo('Tools')))[0][0] != TEXTO:
            err.append('el Template no es el primer tool del macro')
        primero = re.search(r'(\w+) = TextPlus \{', despues)
        if not primero or primero.group(1) != TEXTO:
            err.append('el primer Text+ del texto no es el Template (packs_drt._estilo_de_comp)')
        i1 = dict(_campos(_tabla(v0.campo('Inputs')))).get('Input1')
        if i1 is None or i1.campo('SourceOp').valor != TEXTO or i1.campo('Source').valor != 'StyledText':
            err.append('Input1 no publica Template.StyledText')
        # el orden de lo publicado no cambia (los LBLC_NumInputs de cada grupo siguen cuadrando): sale CCBanner y, en el Count, entra Input1
        ka = [k for k in pa if k != BI.NOMBRE]
        kd = [k for k, _ in _campos(_tabla(v0.campo('Inputs')))]
        if kd != ka and kd != ['Input1'] + ka:
            err.append('cambia el orden de lo publicado')
    if not any(v.nombre == 'MediaOut' for _, v in top):
        err.append('sin MediaOut1 de primer nivel (el clip saldría negro)')
    if retocar(despues)[0] != despues or BI.con_banner(despues) != despues:
        err.append('no es idempotente')
    return err


# ------------------------------------------------------------------------------------------------------------------------------ .drb
def retocar_drb(origen, destino=None):
    """El .drb con cada comp retocada (solo cambian las Tools de sus CompositionBA: prefijo, cabecera y cola intactos). Sin `destino`, en el
    sitio. Si alguna comp no pasa `comprobar`, lanza ValueError y no escribe nada. Devuelve {clip: estado}."""
    origen = Path(origen)
    destino = Path(destino) if destino else origen
    informe, errores = {}, []
    with zipfile.ZipFile(origen) as zin:
        infos = zin.infolist()
        ruta_xml = PP.ruta_mpfolder([i.filename for i in infos])
        xml = zin.read(ruta_xml).decode('utf-8')
        trozos, ultimo = [], 0
        for m in PP._ELEMENTO.finditer(xml):
            bloque = m.group(0)
            ba = PP._BA.search(bloque)
            if ba is None:
                continue
            nombre = PP._NOMBRE.search(bloque).group(1)
            _, tools, _ = PP.tools_de_blob(ba.group(2))
            nuevas, que = retocar(tools)
            informe[nombre] = que
            if nuevas == tools:
                continue
            errores += [f'{nombre}: {e}' for e in comprobar(tools, nuevas)]
            hex_nuevo = PP.blob_con_tools(ba.group(2), nuevas)
            if PP.tools_de_blob(hex_nuevo)[1] != nuevas:
                errores.append(f'{nombre}: el CompositionBA no vuelve igual')
            a = m.start() + ba.start(2)
            trozos += [xml[ultimo:a], hex_nuevo]
            ultimo = m.start() + ba.end(2)
        if xml.count('<CompositionBA>') != sum(1 for m in PP._ELEMENTO.finditer(xml) if PP._BA.search(m.group(0))):
            errores.append('hay comps fuera de los clips (no se retocarían)')
        if errores:
            raise ValueError(f'inspector_luxe: {origen.name}: ' + '; '.join(errores[:8]))
        if ultimo == 0:
            return informe
        trozos.append(xml[ultimo:])
        nuevo_xml = ''.join(trozos)
        tmp = Path(str(destino) + '.tmp')
        with zipfile.ZipFile(tmp, 'w') as zout:
            for info in infos:
                datos = nuevo_xml.encode('utf-8') if info.filename == ruta_xml else zin.read(info.filename)
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type, zi.external_attr, zi.create_system = info.compress_type, info.external_attr, info.create_system
                zout.writestr(zi, datos)
    os.replace(tmp, destino)
    return informe


if __name__ == '__main__':
    for a in sys.argv[1:]:
        inf = retocar_drb(a)
        cuenta = {}
        for que in inf.values():
            cuenta[que] = cuenta.get(que, 0) + 1
        print(f'{Path(a).name}: ' + ', '.join(f'{k} {v}' for k, v in sorted(cuenta.items())))
