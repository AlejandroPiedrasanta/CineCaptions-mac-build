# CineCaptions · By Cinema Productions
# 1_codigo/mapa_codigo.py — consulta el código y la documentación POR TEMA sin leer archivos enteros (mapa, símbolo, módulo, llamadas, ruta, cambios); lo usan el MCP y la línea de comandos.
"""
mapa_codigo.py
------------------------
Para qué: que quien trabaje en el proyecto (una persona o un asistente) conteste «¿qué hace X y dónde está?» gastando lo mínimo, sin abrir el script principal
(13 600 líneas) ni DOCUMENTACION/LEEME.txt. Tres fuentes, todas ya ordenadas:

  DOCUMENTACION/mapa.json     un renglón por tema: id, claves, archivos, símbolos y resumen (de ahí sale el mapa de CLAUDE.md)
  DOCUMENTACION/temas/*.md    el detalle de cada tema (una sección «## id — tema» o «## nota — título»), por grupo
  el código mismo             índice de funciones/clases (ast para .py; regex para .lua/.cs/.ps1) con su línea y su fin

Funciones (las mismas por MCP —herramientas mapa, simbolo, modulo, cambios, resumen— y por línea de comandos):

    mapa(consulta)      temas que encajan con las palabras, con archivos y símbolos (compacto); mapa(id='go-inicio') da el detalle de ese tema
    simbolo(nombre)     el CÓDIGO de esa función/clase/método (solo ella; las clases dan la lista de métodos), con archivo:líneas
    modulo(nombre)      qué es un archivo: su descripción, clases y funciones con línea
    llamadas(nombre)    quién usa esa función/clase (sentido='sale': qué usa ella; niveles=3: la cadena entera, lo que se puede romper al cambiarla)
    ruta(desde, hasta)  la cadena de llamadas más corta entre dos funciones, con la línea de cada llamada
    cambios(n)          las últimas n entradas explicadas del registro de cambios
    resumen()           DOCUMENTACION/RESUMEN.md (una página: qué hace el programa)
    generar()           reescribe el mapa de CLAUDE.md desde mapa.json y avisa de lo que ya no existe (archivos/símbolos/secciones)

Línea de comandos (sin MCP):  6_compilacion/venv315/Scripts/python.exe 1_codigo/mapa_codigo.py mapa go sonido  |  simbolo _go_generar  |  modulo vigilancia  |  generar
                              llamadas _go_generar [entra|sale] [niveles] [archivo]  |  ruta desde hasta
"""
import ast
import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOC = RAIZ / 'DOCUMENTACION'
PRINCIPAL = '1_codigo/CineCaptions (script principal).py'
CARPETAS = ('1_codigo', '2_recursos', '3_compilar', '7_mac')
MARCA_INICIO, MARCA_FIN = '<!-- MAPA:INICIO (lo escribe 1_codigo/mapa_codigo.py generar; no lo edites a mano) -->', '<!-- MAPA:FIN -->'
_PARADA = set('el la los las de del en y o a un una que se por para con al lo es como mas su sus ya no si me mi hay donde cual hace hacer esta este eso esto'.split())


def _norm(t):
    t = unicodedata.normalize('NFD', str(t).lower())
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn')


def _unir_temas(t):
    """«Tema 5» / «tema-5» → «tema5», para que el número (una sola cifra) cuente al buscar."""
    return re.sub(r'\btema[\s_-]*(\d)\b', r'tema\1', t)


def _palabras(texto):
    return re.findall(r'[a-z0-9_]+', _unir_temas(_norm(texto)))


def _cuenta(palabras, w):
    """Cuántas palabras del texto empiezan por w (w de 2 letras: igualdad exacta, para que «go» no case con «algo»)."""
    if len(w) <= 2:
        return sum(1 for x in palabras if x == w)
    return sum(1 for x in palabras if x.startswith(w))


def _terminos(consulta):
    return [w for w in re.findall(r'[a-z0-9_]+', _unir_temas(_norm(consulta))) if len(w) > 1 and w not in _PARADA]


# ---------------------------------------------------------------------------------------------------------------------------------- índice del código
_INDICE = {}          # ruta relativa -> (mtime, [entrada])


def _archivos_de_codigo():
    for c in CARPETAS:
        base = RAIZ / c
        if not base.is_dir():
            continue
        for p in base.rglob('*'):
            if p.suffix.lower() in ('.py', '.lua', '.cs', '.ps1', '.sh') and p.is_file() and '__pycache__' not in p.parts:
                yield p
    for p in RAIZ.glob('*.ps1'):
        yield p


def _bloques(n):
    """Las sentencias de dentro de un if/try/with de nivel de módulo o de clase («if _QT:», «try: from qt_kit import …»): ahí también se definen clases y funciones."""
    if isinstance(n, ast.If):
        return n.body + n.orelse
    if isinstance(n, (ast.Try, getattr(ast, 'TryStar', ast.Try))):
        return n.body + [s for h in n.handlers for s in h.body] + n.orelse + n.finalbody
    if isinstance(n, (ast.With, ast.AsyncWith)):
        return n.body
    return None


def _entradas_py(ruta):
    try:
        arbol = ast.parse(ruta.read_text(encoding='utf-8', errors='replace'))
    except SyntaxError:
        return []
    salida = []

    def recorrer(cuerpo, prefijo, nivel):
        for n in cuerpo:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                salida.append({'nombre': n.name, 'qual': prefijo + n.name, 'tipo': 'def', 'ini': n.lineno, 'fin': n.end_lineno, 'doc': (ast.get_docstring(n) or '').split('\n')[0][:100]})
            elif isinstance(n, ast.ClassDef):
                salida.append({'nombre': n.name, 'qual': prefijo + n.name, 'tipo': 'class', 'ini': n.lineno, 'fin': n.end_lineno, 'doc': (ast.get_docstring(n) or '').split('\n')[0][:100]})
                recorrer(n.body, prefijo + n.name + '.', nivel + 1)
            elif _bloques(n) is not None:
                recorrer(_bloques(n), prefijo, nivel)
            elif isinstance(n, ast.Assign) and nivel == 0:
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id.isupper() and len(t.id) > 3:
                        salida.append({'nombre': t.id, 'qual': t.id, 'tipo': 'const', 'ini': n.lineno, 'fin': n.end_lineno, 'doc': ''})
    recorrer(arbol.body, '', 0)
    return salida


_RX = {'.lua': re.compile(r'^\s*(?:local\s+)?function\s+([\w.:]+)\s*\('),
       '.ps1': re.compile(r'^\s*function\s+([\w-]+)'),
       '.sh': re.compile(r'^\s*(?:function\s+)?(\w+)\s*\(\)\s*\{?'),
       '.cs': re.compile(r'^\s*(?:(?:public|private|internal|protected|static|override|sealed|readonly|unsafe|abstract|partial|extern)\s+)*(?:class\s+(\w+)|[\w<>\[\],.?]+\s+(\w+)\s*\()')}


def _entradas_otras(ruta):
    rx = _RX.get(ruta.suffix.lower())
    lineas = ruta.read_text(encoding='utf-8', errors='replace').split('\n')
    if rx is None:
        return []
    marcas = []
    for i, l in enumerate(lineas, 1):
        m = rx.match(l)
        if m and not l.strip().startswith(('//', '--', '#', 'return', 'new ', 'else', 'if', 'for', 'while', 'using')):
            nombre = next((g for g in m.groups() if g), None)
            if nombre and nombre not in ('if', 'for', 'while', 'switch', 'catch', 'foreach', 'lock', 'using'):
                marcas.append((i, nombre, 'class' if re.search(r'\bclass\s', l) else 'def'))
    salida = []
    for k, (i, nombre, tipo) in enumerate(marcas):
        fin = (marcas[k + 1][0] - 1) if k + 1 < len(marcas) else len(lineas)
        if ruta.suffix.lower() == '.cs':          # llaves: hasta que se cierre
            nivel, visto = 0, False
            for j in range(i - 1, min(len(lineas), i + (6000 if tipo == 'class' else 700))):
                nivel += lineas[j].count('{') - lineas[j].count('}')
                visto = visto or '{' in lineas[j]
                if visto and nivel <= 0:
                    fin = j + 1
                    break
        salida.append({'nombre': nombre.split(':')[-1].split('.')[-1], 'qual': nombre, 'tipo': tipo, 'ini': i, 'fin': fin, 'doc': ''})
    return salida


def indice():
    """{ruta relativa: [entradas]} del código (se rehace solo para los archivos que cambiaron)."""
    vistos = set()
    for p in _archivos_de_codigo():
        rel = p.relative_to(RAIZ).as_posix()
        vistos.add(rel)
        try:
            t = p.stat().st_mtime
        except OSError:
            continue
        if rel not in _INDICE or _INDICE[rel][0] != t:
            try:
                _INDICE[rel] = (t, _entradas_py(p) if p.suffix == '.py' else _entradas_otras(p))
            except Exception:
                _INDICE[rel] = (t, [])
    for rel in list(_INDICE):
        if rel not in vistos:
            del _INDICE[rel]
    return {rel: e for rel, (t, e) in _INDICE.items()}


def _lineas(rel):
    return (RAIZ / rel).read_text(encoding='utf-8', errors='replace').split('\n')


def _buscar(nombre, archivo=''):
    """[(ruta, entrada)] de una función, clase o método: primero el nombre exacto, luego sin mayúsculas, luego parte del nombre; «archivo.funcion» y «Clase.metodo» de .cs/.lua."""
    idx = indice()
    hallados = []
    for nivel in range(3):
        for rel, ents in idx.items():
            if archivo and archivo.lower() not in rel.lower():
                continue
            for e in ents:
                n, q = e['nombre'], e['qual']
                if (nivel == 0 and (n == nombre or q == nombre)) or (nivel == 1 and (n.lower() == nombre.lower() or q.lower() == nombre.lower())) \
                        or (nivel == 2 and nombre.lower() in q.lower()):
                    hallados.append((rel, e))
        if hallados:
            break
    if not hallados and '.' in nombre:                                    # «vigilancia.iniciar»: archivo.función
        pref, _, resto = nombre.partition('.')
        for rel, ents in idx.items():
            if _norm(Path(rel).stem) == _norm(pref):
                hallados += [(rel, e) for e in ents if e['qual'] == resto or e['nombre'] == resto]
    if not hallados and '.' in nombre:                                    # «Instalacion.Desinstalar» en .cs/.lua: método dentro del rango de su clase
        pref, _, resto = nombre.rpartition('.')
        for rel, ents in idx.items():
            for c in ents:
                if c['tipo'] == 'class' and c['nombre'] == pref.split('.')[-1]:
                    hallados += [(rel, e) for e in ents if e['nombre'] == resto and c['ini'] <= e['ini'] <= c['fin'] and e is not c]
    return hallados


def simbolo(nombre, lineas=70, archivo=''):
    """El código de una función, clase o método: «_go_generar», «WordTagWindow._continuar», «Instalacion.Desinstalar». Solo ese trozo."""
    nombre = re.sub(r'^(class|def)\s+', '', str(nombre).strip()).rstrip('()')
    lineas = max(10, min(int(lineas or 70), 400))
    idx = indice()
    hallados = _buscar(nombre, archivo)
    if not hallados:
        return f'«{nombre}» no está en el código. Prueba mapa("{nombre}") o simbolo con otra parte del nombre.'
    if len(hallados) > 1 and (len(hallados) > 4 or hallados[0][1]['qual'].lower() != nombre.lower()) and not (len({e['qual'] for _, e in hallados}) == 1 and len(hallados) <= 4):
        filas = [f"  {rel}:{e['ini']}-{e['fin']}  {e['qual']}  ({e['tipo']})" + (f"  {e['doc']}" if e['doc'] else '') for rel, e in hallados[:25]]
        return f'{len(hallados)} coincidencias para «{nombre}» (afina con el nombre completo «Clase.metodo» o archivo=...):\n' + '\n'.join(filas)
    salida = []
    for rel, e in hallados[:3]:
        todas = _lineas(rel)
        ini, fin = e['ini'], e['fin']
        if e['tipo'] == 'class' and rel.endswith('.py') and fin - ini > lineas:
            metodos = [x for x in idx[rel] if x['qual'].startswith(e['qual'] + '.') and x['qual'].count('.') == e['qual'].count('.') + 1]
            cab = '\n'.join(todas[ini - 1: min(fin, ini + 12)])
            salida.append(f"# {rel}:{ini}-{fin}  class {e['qual']}  ({len(metodos)} métodos; pide uno con simbolo('{e['qual']}.método'))\n{cab}\n...\n# métodos: " +
                          ', '.join(f"{x['nombre']}:{x['ini']}" for x in metodos))
            continue
        tope = min(fin, ini + lineas - 1)
        cuerpo = '\n'.join(todas[ini - 1: tope])
        resto = fin - tope
        salida.append(f"# {rel}:{ini}-{fin}  {e['qual']}" + (f"\n{cuerpo}\n# … faltan {resto} líneas: simbolo('{nombre}', lineas={min(fin - ini + 1, 400)})" if resto > 0 else f"\n{cuerpo}"))
    return '\n\n'.join(salida)


def modulo(nombre):
    """Qué es un archivo: descripción, clases y funciones con su línea."""
    n = _norm(nombre).replace('.py', '').strip()
    cand = []
    for p in _archivos_de_codigo():
        rel = p.relative_to(RAIZ).as_posix()
        stem = _norm(p.stem)
        if n in ('principal', 'script principal', 'main', 'cinecaptions') and rel == PRINCIPAL:
            cand = [rel]
            break
        if stem == n or _norm(p.name) == n:
            cand.append(rel)
    if not cand:
        cand = [p.relative_to(RAIZ).as_posix() for p in _archivos_de_codigo() if n in _norm(p.stem)][:12]
        if not cand:
            return f'no hay ningún archivo de código llamado «{nombre}».'
        if len(cand) > 1:
            return 'varios archivos coinciden: ' + ', '.join(cand)
    rel = cand[0]
    idx = indice().get(rel, [])
    texto = (RAIZ / rel).read_text(encoding='utf-8', errors='replace').split('\n')
    desc = texto[1].lstrip('#/- ').strip() if len(texto) > 1 else ''
    nl = len(texto)
    sal = [f'{rel} ({nl} líneas)', desc]
    clases = [e for e in idx if e['tipo'] == 'class']
    if len(clases) > 30:
        sal.append(f'  ({len(clases)} clases; se muestran las 30 más grandes)')
        clases = sorted(sorted(clases, key=lambda c: c['fin'] - c['ini'], reverse=True)[:30], key=lambda c: c['ini'])
    for c in clases[:30]:
        ms = [e for e in idx if e['qual'].startswith(c['qual'] + '.')]
        sal.append(f"  class {c['qual']}:{c['ini']}-{c['fin']} ({len(ms)} métodos){('  ' + c['doc']) if c['doc'] else ''}")
    libres = [e for e in idx if e['tipo'] == 'def' and '.' not in e['qual']]
    if libres:
        sal.append('  funciones: ' + ', '.join(f"{e['nombre']}:{e['ini']}" for e in libres[:80]) + (' …' if len(libres) > 80 else ''))
    consts = [e for e in idx if e['tipo'] == 'const']
    if consts:
        sal.append('  constantes: ' + ', '.join(e['nombre'] for e in consts[:25]))
    return '\n'.join(s for s in sal if s)


# ---------------------------------------------------------------------------------------------------------------------------------- grafo de llamadas
# Quién usa a quién (ast para .py; regex para .lua), para contestar «¿qué se rompe si cambio X?» sin buscar ni leer. Una arista va de la función que llama
# (o del archivo: «(módulo)») a la función o clase DEL PROYECTO que llama o que pasa sin llamar («callback»: connect, correr_en_hilo, target=…, tablas).
# Lo que no se sabe seguro (obj.metodo() sin saber qué es obj) solo se une si hay ≤3 candidatos y se marca «?»; lo de fuera (Qt, os, …) no aparece.
_LLAMADAS = {}        # ruta relativa -> (mtime, [(llamador, nombre, pista, línea, 'llama'|'usa')], {alias: (módulo, nombre|None)})
_GRAFO = {'firma': None, 'sale': {}, 'entra': {}, 'por_rel': {}, 'cortos': {}}
_MODULO = '(módulo)'
_GENERICOS = set('get set run start stop close show hide update connect emit append extend add remove pop clear copy items keys values join split strip '
                 'format replace read write open load save exec text value setText setValue resize move main'.split())
_RX_LLAMA_LUA = re.compile(r'([A-Za-z_][\w.:]*)\s*\(')


def _llamadas_py(ruta):
    arbol = ast.parse(ruta.read_text(encoding='utf-8', errors='replace'))
    imports = {}
    for n in ast.walk(arbol):                     # también los import dentro de funciones (el proyecto importa tarde a menudo)
        if isinstance(n, ast.Import):
            for a in n.names:
                imports[a.asname or a.name.split('.')[0]] = ((a.name if a.asname else a.name.split('.')[0]).split('.')[-1], None)
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                imports[a.asname or a.name] = (n.module.split('.')[-1], a.name) if n.module else (a.name, None)
    aristas = []

    def destino(f):
        """f() → (f, None) · self.f → (f, 'self') · mod.f → (f, 'mod') · otra_cosa.f → (f, '?')."""
        if isinstance(f, ast.Name):
            return f.id, None
        if isinstance(f, ast.Attribute):
            if isinstance(f.value, ast.Name):
                return f.attr, ('self' if f.value.id in ('self', 'cls') else f.value.id)
            return f.attr, '?'
        return None, None

    def anotar(nodo, llamador):
        locales = set()                           # parámetros, variables y funciones anidadas: «ruta» como variable no es la función ruta()
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = nodo.args
            locales = {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg] if x}
            locales |= {n.id if isinstance(n, ast.Name) else n.name for n in ast.walk(nodo) if n is not nodo and (
                (isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)) or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))}
        for n in ast.walk(nodo):
            pasados = ()
            if isinstance(n, ast.Call):
                nombre, pista = destino(n.func)
                if nombre and not (pista is None and nombre in locales):
                    aristas.append((llamador, nombre, pista, n.lineno, 'llama'))
                pasados = list(n.args) + [k.value for k in n.keywords]
            elif isinstance(n, (ast.Tuple, ast.List, ast.Set)):
                pasados = n.elts
            elif isinstance(n, ast.Dict):
                pasados = n.values
            elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.Return)) and n.value is not None:
                pasados = (n.value,)
            for p in pasados:
                if isinstance(p, ast.Name) or (isinstance(p, ast.Attribute) and isinstance(p.value, ast.Name)):
                    nombre, pista = destino(p)
                    if not (pista is None and nombre in locales):
                        aristas.append((llamador, nombre, pista, p.lineno, 'usa'))

    def recorrer(cuerpo, prefijo, contenedor):    # mismos nombres que _entradas_py: las funciones anidadas cuentan como su función de fuera
        for n in cuerpo:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                anotar(n, prefijo + n.name)
            elif isinstance(n, ast.ClassDef):
                recorrer(n.body, prefijo + n.name + '.', prefijo + n.name)
            elif _bloques(n) is not None:
                cabeza = [n.test] if isinstance(n, ast.If) else [i.context_expr for i in getattr(n, 'items', ())]
                for c in cabeza:
                    anotar(c, contenedor)
                recorrer(_bloques(n), prefijo, contenedor)
            else:
                anotar(n, contenedor)
    recorrer(arbol.body, '', _MODULO)
    return aristas, imports


def _llamadas_lua(ruta, entradas):
    aristas = []
    marcas = sorted((e['ini'], e['qual']) for e in entradas)
    actual, k = _MODULO, 0
    for i, l in enumerate(ruta.read_text(encoding='utf-8', errors='replace').split('\n'), 1):
        while k < len(marcas) and marcas[k][0] <= i:
            actual, k = marcas[k][1], k + 1
        codigo = l.split('--', 1)[0]
        if re.match(r'\s*(?:local\s+)?function\b', codigo):          # la definición misma no es una llamada
            codigo = codigo.partition('(')[2]
        for m in _RX_LLAMA_LUA.finditer(codigo):
            aristas.append((actual, re.split(r'[.:]', m.group(1))[-1], 'lua', i, 'llama'))
    return aristas, {}


def _resolver(rel, llamador, nombre, pista, tipo, imports, defs, importados):
    """[((ruta, qual), aproximado)] de lo que puede ser «nombre» llamado desde rel (vacío = de fuera del proyecto o imposible de saber).
    importados: los módulos que rel importa; entre candidatos con el mismo nombre, ganan los de esos módulos."""
    if pista == 'lua':
        r = [c for c in defs.get(nombre, ()) if c[0] == rel]
        if r:
            return [(c, False) for c in r]
        r = [c for c in defs.get(nombre, ()) if c[0].endswith('.lua')]
        return [(c, True) for c in r] if len(r) <= 3 else []
    if pista is None and nombre in imports and imports[nombre][1]:     # from x import f (as g)
        mod, orig = imports[nombre]
        return [(c, False) for c in defs.get(orig, ()) if Path(c[0]).stem == mod and c[1] == orig]
    cands = [c for c in defs.get(nombre, ()) if c[0].endswith('.py')]
    if not cands:
        return []
    if pista is None:
        r = [c for c in cands if c[0] == rel and '.' not in c[1]]
        if r or tipo == 'usa' or nombre in imports:
            return [(c, False) for c in r]
        r = [c for c in cands if '.' not in c[1]]
        return [(r[0], True)] if len(r) == 1 else []
    if pista == 'self':
        clase = llamador.rpartition('.')[0]
        r = [c for c in cands if c[0] == rel and c[1] == f'{clase}.{nombre}']
        if r:
            return [(c, False) for c in r]
        r = [c for c in cands if '.' in c[1]]
        r = [c for c in r if c[0] == rel] or [c for c in r if Path(c[0]).stem in importados] or r
        return [(c, True) for c in r] if len(r) <= 3 else []
    if pista in imports:
        mod, orig = imports[pista]
        for stem, qual in ((orig, nombre), (mod, f'{orig}.{nombre}' if orig else nombre)):
            r = [c for c in cands if stem and Path(c[0]).stem == stem and c[1] == qual]
            if r:
                return [(c, False) for c in r]
        return []
    r = [c for c in cands if c[1] == f'{pista}.{nombre}']                 # Clase.metodo()
    if r:
        r = [c for c in r if c[0] == rel] or r
        return [(c, False) for c in r] if len(r) <= 3 else []
    if tipo == 'usa' or nombre in _GENERICOS or nombre.startswith('__'):
        return []
    r = [c for c in cands if c[0] == rel] or [c for c in cands if Path(c[0]).stem in importados] or cands
    return [(c, True) for c in r] if len(r) <= 3 else []


def _grafo():
    """El grafo de todo el código (se rehace solo si cambió algún archivo; lo caro, leer cada archivo, se guarda por archivo)."""
    idx = indice()
    firma = tuple(sorted((rel, t) for rel, (t, _) in _INDICE.items()))
    if _GRAFO['firma'] == firma:
        return _GRAFO
    defs, por_rel, stems = {}, {}, {}
    for rel, ents in idx.items():
        por_rel[rel] = {e['qual']: e for e in ents if e['tipo'] in ('def', 'class')}
        stems[Path(rel).stem] = stems.get(Path(rel).stem, 0) + 1
        for e in por_rel[rel].values():
            defs.setdefault(e['nombre'], []).append((rel, e['qual']))
    sale, entra = {}, {}
    for rel in idx:
        if not rel.endswith(('.py', '.lua')):
            continue
        t = _INDICE[rel][0]
        if rel not in _LLAMADAS or _LLAMADAS[rel][0] != t:
            try:
                _LLAMADAS[rel] = (t, *(_llamadas_py(RAIZ / rel) if rel.endswith('.py') else _llamadas_lua(RAIZ / rel, idx[rel])))
            except Exception:
                _LLAMADAS[rel] = (t, [], {})
        _, aristas, imports = _LLAMADAS[rel]
        importados = {m for m, _ in imports.values()} | {o for _, o in imports.values() if o}
        for llamador, nombre, pista, linea, tipo in aristas:
            if nombre not in defs and nombre not in imports:
                continue
            origen = (rel, llamador)
            for dest, aprox in _resolver(rel, llamador, nombre, pista, tipo, imports, defs, importados):
                if dest == origen:
                    continue
                dato = sale.setdefault(origen, {}).get(dest)
                if dato is None:
                    sale[origen][dest] = entra.setdefault(dest, {})[origen] = [linea, tipo, aprox]
                else:
                    dato[1] = 'llama' if 'llama' in (dato[1], tipo) else 'usa'
                    dato[2] = dato[2] and aprox
    for rel in list(_LLAMADAS):
        if rel not in idx:
            del _LLAMADAS[rel]
    cortos = {rel: (rel if stems[Path(rel).stem] > 1 else _nombre_corto(Path(rel).name)) for rel in idx}
    cortos[PRINCIPAL] = 'principal'
    _GRAFO.update(firma=firma, sale=sale, entra=entra, por_rel=por_rel, cortos=cortos)
    return _GRAFO


def _donde(nodo, linea=None):
    rel, qual = nodo
    e = _GRAFO['por_rel'].get(rel, {}).get(qual)
    return f"{_GRAFO['cortos'].get(rel, rel)}:{linea or (e['ini'] if e else 1)}"


def _nodos(nombre, archivo=''):
    """[(ruta, qual)] (hasta 3) de las funciones/clases .py/.lua con ese nombre, o el texto que explica por qué no."""
    nombre = re.sub(r'^(class|def)\s+', '', str(nombre).strip()).rstrip('()')
    hallados = [(rel, e) for rel, e in _buscar(nombre, archivo) if e['tipo'] in ('def', 'class') and rel.endswith(('.py', '.lua'))]
    if not hallados:
        return f'«{nombre}» no es una función ni clase de los .py/.lua. Prueba mapa("{nombre}").'
    nodos = list(dict.fromkeys((rel, e['qual']) for rel, e in hallados))
    if len(nodos) > 3:
        return f'{len(nodos)} coincidencias para «{nombre}» (afina con «Clase.metodo» o archivo=...):\n' + '\n'.join(f"  {rel}:{e['ini']}  {e['qual']}" for rel, e in hallados[:25])
    return nodos


def _marca(tipo, aprox):
    return ('  (callback)' if tipo == 'usa' else '') + ('  ?' if aprox else '')


_LEYENDA = '(callback) = se pasa sin llamarla (connect, hilos, tablas) · ? = deducido por el nombre, compruébalo'


def llamadas(nombre, sentido='entra', niveles=1, archivo=''):
    """Quién usa una función o clase (sentido='entra', con la línea de cada llamada) o qué usa ella ('sale', con dónde está definido).
    niveles>1 sigue la cadena: con 'entra', todo lo que se puede romper al cambiarla."""
    nodos = _nodos(nombre, archivo)
    if isinstance(nodos, str):
        return nodos
    g = _grafo()
    sale = str(sentido or 'entra').lower().startswith(('s', 'o', 'a'))    # sale / out / a qué
    aristas = g['sale'] if sale else g['entra']
    niveles = max(1, min(int(niveles or 1), 6))
    salida, marcas = [], False
    for nodo in nodos:
        filas, vistos = [], {nodo}

        def seguir(n, nivel):
            nonlocal marcas
            for otro, (linea, tipo, aprox) in sorted(aristas.get(n, {}).items(), key=lambda kv: (kv[0][0] != n[0], kv[0][0], kv[1][0])):
                if otro in vistos or len(filas) >= 120:
                    continue
                vistos.add(otro)
                marcas = marcas or tipo == 'usa' or aprox
                filas.append('  ' * nivel + f'{_donde(otro) if sale else _donde(otro, linea)}  {otro[1]}{_marca(tipo, aprox)}')
                if nivel < niveles:
                    seguir(otro, nivel + 1)
        seguir(nodo, 1)
        cab = (f'→ lo que usa «{nodo[1]}» ({_donde(nodo)}; dónde está cada una)' if sale else f'← quién usa «{nodo[1]}» ({_donde(nodo)}; línea de cada llamada)')
        cab += (f', hasta {niveles} niveles' if niveles > 1 else '') + f': {len(filas)}' + (' (cortado en 120)' if len(filas) >= 120 else '')
        if not filas:
            cab += (' — no llama a nada del proyecto' if sale else ' — nadie la llama desde el código (¿señal Qt, getattr, el .lua o la línea de comandos?)')
        salida.append('\n'.join([cab] + filas))
    return '\n\n'.join(salida) + (f'\n{_LEYENDA}' if marcas else '')


def ruta(desde, hasta, tope=12):
    """La cadena de llamadas más corta de «desde» a «hasta» (si no la hay, la de vuelta), con la línea de cada llamada."""
    a, b = _nodos(desde), _nodos(hasta)
    for x in (a, b):
        if isinstance(x, str):
            return x
    g = _grafo()
    for ida, origenes, metas in ((True, a, set(b)), (False, b, set(a))):
        previo, nivel, cola = {o: None for o in origenes}, {o: 0 for o in origenes}, list(origenes)
        for n in cola:
            if n in metas:
                camino = [n]
                while previo[camino[-1]] is not None:
                    camino.append(previo[camino[-1]])
                camino.reverse()
                filas = [f'  {_donde(camino[0])}  {camino[0][1]}']
                for p, q in zip(camino, camino[1:]):
                    linea, tipo, aprox = g['sale'][p][q]
                    filas.append(f'  → {_donde(q)}  {q[1]}   (en {_donde(p, linea)}{_marca(tipo, aprox)})')
                cab = f'de «{camino[0][1]}» a «{camino[-1][1]}», {len(camino) - 1} paso(s)'
                if not ida:
                    cab = f'«{desde}» no llega a «{hasta}»; al revés sí: ' + cab
                marcas = any(g['sale'][p][q][1] == 'usa' or g['sale'][p][q][2] for p, q in zip(camino, camino[1:]))
                return '\n'.join([cab] + filas) + (f'\n{_LEYENDA}' if marcas else '')
            if nivel[n] >= tope:
                continue
            for otro in g['sale'].get(n, {}):
                if otro not in previo:
                    previo[otro], nivel[otro] = n, nivel[n] + 1
                    cola.append(otro)
    return f'no hay cadena de llamadas entre «{desde}» y «{hasta}» que se vea en el código (puede ir por una señal Qt, getattr, otro proceso o el .lua).'


# ---------------------------------------------------------------------------------------------------------------------------------- mapa y temas
_CLAVES_TEMA = {'id': '', 'grupo': '', 'tema': '', 'claves': [], 'archivos': [], 'simbolos': [], 'resumen': ''}


def _mapa():
    try:
        m = json.loads((DOC / 'mapa.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'grupos': {}, 'temas': []}
    for t in m.get('temas', []):                     # un tema al que le falte una clave NO debe tumbar mapa() (generar() avisa)
        t['_faltan'] = [k for k in _CLAVES_TEMA if k not in t]
        for k, v in _CLAVES_TEMA.items():
            t.setdefault(k, list(v) if isinstance(v, list) else v)
    return m


_SECC = {}


def secciones():
    """[{grupo, id, titulo, texto}] de DOCUMENTACION/temas/*.md (una sección por «## »)."""
    carpeta = DOC / 'temas'
    salida = []
    for p in sorted(carpeta.glob('*.md')):
        t = p.stat().st_mtime
        if p.name not in _SECC or _SECC[p.name][0] != t:
            bloques = re.split(r'(?m)^## ', p.read_text(encoding='utf-8'))[1:]
            lista = []
            for b in bloques:
                cab, _, cuerpo = b.partition('\n')
                id_, _, titulo = cab.partition(' — ')
                lista.append({'grupo': p.stem, 'id': id_.strip(), 'titulo': (titulo or cab).strip(), 'texto': cuerpo.strip()})
            _SECC[p.name] = (t, lista)
        salida += _SECC[p.name][1]
    return salida


_LARGO = 4000                                        # una sección más larga sale como índice de partes (ahorra tokens)


def _partes(texto, id_, parte='', completo=False):
    """Sección corta o completo=True: entera. Larga: primer párrafo + índice; parte='3' o parte='palabras' da solo esas partes."""
    if completo or (len(texto) <= _LARGO and not parte):
        return texto
    trozos = [p.strip() for p in re.split(r'\n\s*\n', texto) if p.strip()]
    if parte:
        p = str(parte).strip()
        if p.isdigit():
            elegidos = [trozos[int(p) - 1]] if 0 < int(p) <= len(trozos) else []
        else:
            ter = _terminos(p)
            elegidos = [x for x in trozos if ter and all(_cuenta(_palabras(x), w) for w in ter)]
        return '\n\n'.join(elegidos) if elegidos else f'ninguna parte de «{id_}» con «{p}»; mapa(id="{id_}") da el índice.'
    def rotulo(x):
        r = re.match(r'\*\*(.+?)\*\*', x)
        return (r.group(1) if r else x.replace('\n', ' '))[:90]
    indice = '\n'.join(f'  {i}. {rotulo(x)}' for i, x in enumerate(trozos[1:], 2))
    return (f'{trozos[0]}\n\n— Sección larga ({len(texto)} car.): pide solo lo que necesites con '
            f'mapa(id="{id_}", parte="N" o "palabras"); completo=True la da entera.\n{indice}')


def mapa(consulta='', id='', completo=False, maximo=5, parte=''):
    """Busca temas por palabras (compacto), o con id= da el detalle de ese tema (si es largo, un índice; parte= elige)."""
    m = _mapa()
    temas = {t['id']: t for t in m['temas']}
    secs = secciones()
    if id:
        id_ = str(id).strip()
        if id_ in m.get('grupos', {}):
            return f"{id_}: {m['grupos'][id_]}\n" + '\n'.join(f"  {s['id']} — {s['titulo']} ({len(s['texto'])} car.)" for s in secs if s['grupo'] == id_)
        elegidas = [s for s in secs if s['id'] == id_ or _norm(s['titulo']) == _norm(id_)]
        if not elegidas:
            return f'no hay tema «{id_}». Temas: ' + ', '.join(sorted(temas)) + '. Grupos: ' + ', '.join(m.get('grupos', {}))
        t = temas.get(elegidas[0]['id'])
        cab = f"[{t['id']}] {t['tema']}  (DOCUMENTACION/temas/{t['grupo']}.md)\n  archivos: {', '.join(t['archivos']) or '—'}\n  símbolos: {', '.join(t['simbolos']) or '—'}\n" if t else ''
        return cab + _partes('\n\n'.join(s['texto'] for s in elegidas), id_, parte, completo)
    ter = _terminos(consulta)
    if not ter:
        return 'Grupos: ' + ' | '.join(f'{g}: {d}' for g, d in m.get('grupos', {}).items()) + '\nPasa palabras (consulta="sonido emoji") o id="go-inicio".'
    puntos = {}
    for t in m['temas']:
        base = _palabras(' '.join(t['claves'] + [t['id'].replace('-', ' ')]))
        medio = _palabras(t['tema'] + ' ' + t['resumen'])
        fuentes = _palabras(' '.join(t['archivos'] + t['simbolos']))
        p = sum((4 if _cuenta(base, w) else 0) + (2 if _cuenta(medio, w) else 0) + (1 if _cuenta(fuentes, w) else 0) for w in ter)
        if p:
            puntos[t['id']] = puntos.get(t['id'], 0) + p
    for s in secs:
        pal, tit = _palabras(s['titulo'] + ' ' + s['texto']), _palabras(s['titulo'])
        p = sum(min(_cuenta(pal, w), 3) + (3 if _cuenta(tit, w) else 0) for w in ter)
        if p:
            clave = s['id'] if s['id'] in temas else f"{s['grupo']}#{s['titulo'][:40]}"
            puntos[clave] = puntos.get(clave, 0) + p
    if not puntos:
        return f'nada para «{consulta}». Prueba otras palabras o mapa() sin argumentos para ver los grupos.'
    orden = sorted(puntos, key=lambda k: -puntos[k])[:int(maximo)]
    salida = []
    for k in orden:
        if k in temas:
            t = temas[k]
            sec = next((s for s in secs if s['id'] == k), None)
            linea = f"[{k}] {t['tema']} — {t['resumen']}\n    archivos: {', '.join(t['archivos'][:6]) or '—'} · símbolos: {', '.join(t['simbolos'][:6]) or '—'} · detalle: mapa(id='{k}') ({len(sec['texto']) if sec else 0} car.)"
            if completo and sec:
                linea += '\n' + sec['texto'][:3500]
        else:
            g, _, tit = k.partition('#')
            sec = next((s for s in secs if s['grupo'] == g and s['titulo'].startswith(tit)), None)
            linea = f"[nota · {g}] {sec['titulo'] if sec else tit}\n    " + ((sec['texto'] if completo else sec['texto'][:300].replace('\n', ' ') + ('…' if len(sec['texto']) > 300 else '')) if sec else '')
        salida.append(linea)
    return '\n'.join(salida)


def _version():
    """APP_VERSION de 1_codigo/version.py (la única fuente); '' si no se puede leer."""
    try:
        return re.search(r"(?m)^APP_VERSION\s*=\s*['\"]([\d.]+)['\"]", (RAIZ / '1_codigo' / 'version.py').read_text(encoding='utf-8')).group(1)
    except (OSError, AttributeError):
        return ''


def resumen():
    try:
        t = (DOC / 'RESUMEN.md').read_text(encoding='utf-8')
    except OSError:
        return 'no hay DOCUMENTACION/RESUMEN.md'
    v = _version()
    return re.sub(r'(?m)^# CineCaptions [\d.]+', '# CineCaptions ' + v, t, count=1) if v else t


def cambios(n=6):
    """Las últimas n entradas EXPLICADAS del registro de cambios (las automáticas, que solo listan archivos, se saltan)."""
    ruta = DOC / 'REGISTRO_DE_CAMBIOS.txt'
    try:
        t = ruta.read_text(encoding='utf-8')
    except OSError:
        return 'no hay REGISTRO_DE_CAMBIOS.txt'
    entradas = re.split(r'(?m)^(?=\d{4}-\d\d-\d\d \d\d:\d\d  ·)', t)
    buenas = [e.strip() for e in entradas if re.match(r'\d{4}-\d\d-\d\d', e) and 'cambio explicado' in e.split('\n', 1)[0]]
    return '\n\n'.join((e if len(e) < 900 else e[:900] + ' …') for e in buenas[:max(1, int(n))]) or 'sin entradas explicadas'


# ---------------------------------------------------------------------------------------------------------------------------------- generar CLAUDE.md
_SIN_TEMA_OK = ('__init__', 'version')            # (version.py ya lo cubre el tema «version»)


def sin_tema():
    """Archivos de código (1_codigo/*.py y los scripts de 2_recursos) que NINGÚN tema de mapa.json nombra: la señal de que alguien añadió código y no lo conectó al mapa."""
    citados = set()
    for t in _mapa()['temas']:
        for a in t['archivos']:
            citados.update((Path(a).stem.lower(), Path(a).name.lower()))
    salida = []
    candidatos = sorted((RAIZ / '1_codigo').glob('*.py')) + sorted((RAIZ / '2_recursos').rglob('*.py')) + sorted((RAIZ / '2_recursos').rglob('*.lua'))
    for p in candidatos:
        if '__pycache__' in p.parts or 'fuentes' in p.parts or p.stem in _SIN_TEMA_OK:
            continue
        if p.stem.lower() not in citados and p.name.lower() not in citados:
            salida.append(p.relative_to(RAIZ).as_posix())
    return salida


def _nombre_corto(a):
    return a.replace('.py', '').replace('CineCaptions (script principal)', 'principal')


def generar(escribir=True):
    """Reescribe el bloque de mapa de CLAUDE.md desde mapa.json y devuelve los avisos (lo que ya no existe)."""
    m = _mapa()
    idx = indice()
    # «existe» = aparece como identificador en algún archivo de código (cubre constantes, atributos de clase y variables, no solo def/class)
    nombres = set()
    archivos_reales = set()
    for c in CARPETAS + ('4_diseno',):
        base = RAIZ / c
        if not base.is_dir():
            continue
        for p in base.rglob('*'):
            if '__pycache__' in p.parts or not p.is_file():
                continue
            archivos_reales.add(p.name)
            archivos_reales.add(p.relative_to(RAIZ).as_posix())
            if p.suffix.lower() in ('.py', '.lua', '.cs', '.ps1', '.sh', '.spec') and p.stat().st_size < 3_000_000:
                nombres.update(re.findall(r'[A-Za-z_]\w{3,}', p.read_text(encoding='utf-8', errors='replace')))
    for p in RAIZ.glob('*'):
        archivos_reales.add(p.name)
    suf = tuple('/' + a for a in archivos_reales if '/' in a)
    secs = {s['id'] for s in secciones()}
    avisos = []
    lineas = []
    for g, titulo in m['grupos'].items():
        ts = [t for t in m['temas'] if t['grupo'] == g]
        if not ts:
            continue
        partes = []
        for t in ts:
            fuentes = [_nombre_corto(a) for a in t['archivos'][:1]] or t['simbolos'][:1]
            partes.append(f"`{t['id']}`" + (f" [{' '.join(fuentes)}]" if fuentes else ''))
            for a in t['archivos']:
                if a not in archivos_reales and not any(r.endswith('/' + a) for r in archivos_reales if '/' in r):
                    avisos.append(f"{t['id']}: archivo «{a}» no existe")
            for s_ in t['simbolos']:
                if s_ not in nombres:
                    avisos.append(f"{t['id']}: símbolo «{s_}» ya no existe")
            if t['id'] not in secs:
                avisos.append(f"{t['id']}: sin sección en DOCUMENTACION/temas/{g}.md")
        lineas.append(f'- **{g}** ({titulo}): ' + ' · '.join(partes))
    for t in m['temas']:
        if t.get('_faltan'):
            avisos.append(f"{t['id']}: a mapa.json le falta la clave {', '.join(t['_faltan'])}")
    for a in sin_tema():
        avisos.append(f'«{a}» no está en ningún tema de mapa.json (añádelo a `archivos` de un tema o crea uno)')
    bloque = MARCA_INICIO + '\n' + '\n'.join(lineas) + '\n' + MARCA_FIN
    ruta = RAIZ / 'CLAUDE.md'
    t = ruta.read_text(encoding='utf-8')
    if MARCA_INICIO in t and MARCA_FIN in t:
        nuevo = t[:t.index(MARCA_INICIO)] + bloque + t[t.index(MARCA_FIN) + len(MARCA_FIN):]
        if _version():
            nuevo = re.sub(r'(?m)^(App PySide6 \()v[\d.]+(\))', lambda mo: mo.group(1) + 'v' + _version() + mo.group(2), nuevo, count=1)
        if escribir and nuevo != t:
            ruta.write_text(nuevo, encoding='utf-8', newline='')
    else:
        avisos.append('CLAUDE.md no tiene las marcas del mapa')
    return avisos


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 0
    orden, args = argv[1], argv[2:]
    if orden == 'mapa':
        print(mapa(' '.join(a for a in args if not a.startswith('--')), completo='--completo' in args))
    elif orden == 'tema':
        print(mapa(id=args[0], parte=' '.join(args[1:]), completo='--completo' in args) if '--completo' not in args[1:] else mapa(id=args[0], completo=True))
    elif orden == 'simbolo':
        print(simbolo(args[0], int(args[1]) if len(args) > 1 else 70))
    elif orden == 'modulo':
        print(modulo(args[0]))
    elif orden == 'llamadas':
        print(llamadas(args[0], args[1] if len(args) > 1 else 'entra', int(args[2]) if len(args) > 2 else 1, args[3] if len(args) > 3 else ''))
    elif orden == 'ruta':
        print(ruta(args[0], args[1]))
    elif orden == 'cambios':
        print(cambios(int(args[0]) if args else 6))
    elif orden == 'resumen':
        print(resumen())
    elif orden == 'sin_tema':
        print('\n'.join(sin_tema()) or 'todo el código está en algún tema')
    elif orden == 'generar':
        av = generar()
        print('CLAUDE.md al día.' + (f' {len(av)} aviso(s):\n  ' + '\n  '.join(av) if av else ' Sin avisos.'))
    else:
        print('órdenes: mapa, tema, simbolo, modulo, llamadas, ruta, cambios, resumen, sin_tema, generar')
    return 0


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    sys.exit(main(sys.argv))
