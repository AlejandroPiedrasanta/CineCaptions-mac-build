# CineCaptions · By Cinema Productions
# 1_codigo/mapa_codigo.py — consulta el código y la documentación POR TEMA sin leer archivos enteros (mapa, símbolo, módulo, cambios); lo usan el MCP y la línea de comandos.
"""
mapa_codigo.py  (v5.3.2)
------------------------
Para qué: que quien trabaje en el proyecto (una persona o un asistente) conteste «¿qué hace X y dónde está?» gastando lo mínimo, sin abrir el script principal
(12 000 líneas) ni LEEME.txt. Tres fuentes, todas ya ordenadas:

  DOCUMENTACION/mapa.json     un renglón por tema: id, claves, archivos, símbolos y resumen (de ahí sale el mapa de CLAUDE.md)
  DOCUMENTACION/temas/*.md    el detalle de cada tema (una sección «## id — tema» o «## nota — título»), por grupo
  el código mismo             índice de funciones/clases (ast para .py; regex para .lua/.cs/.ps1) con su línea y su fin

Funciones (las mismas por MCP —herramientas mapa, simbolo, modulo, cambios, resumen— y por línea de comandos):

    mapa(consulta)      temas que encajan con las palabras, con archivos y símbolos (compacto); mapa(id='go-inicio') da el detalle de ese tema
    simbolo(nombre)     el CÓDIGO de esa función/clase/método (solo ella; las clases dan la lista de métodos), con archivo:líneas
    modulo(nombre)      qué es un archivo: su descripción, clases y funciones con línea
    cambios(n)          las últimas n entradas explicadas del registro de cambios
    resumen()           DOCUMENTACION/RESUMEN.md (una página: qué hace el programa)
    generar()           reescribe el mapa de CLAUDE.md desde mapa.json y avisa de lo que ya no existe (archivos/símbolos/secciones)

Línea de comandos (sin MCP):  6_compilacion/venv314/Scripts/python.exe 1_codigo/mapa_codigo.py mapa go sonido  |  simbolo _go_generar  |  modulo vigilancia  |  generar
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


def _palabras(texto):
    return re.findall(r'[a-z0-9_]+', _norm(texto))


def _cuenta(palabras, w):
    """Cuántas palabras del texto empiezan por w (w de 2 letras: igualdad exacta, para que «go» no case con «algo»)."""
    if len(w) <= 2:
        return sum(1 for x in palabras if x == w)
    return sum(1 for x in palabras if x.startswith(w))


def _terminos(consulta):
    return [w for w in re.findall(r'[a-z0-9_]+', _norm(consulta)) if len(w) > 1 and w not in _PARADA]


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


def simbolo(nombre, lineas=70, archivo=''):
    """El código de una función, clase o método: «_go_generar», «WordTagWindow._continuar», «Instalacion.Desinstalar». Solo ese trozo."""
    nombre = re.sub(r'^(class|def)\s+', '', str(nombre).strip()).rstrip('()')
    lineas = max(10, min(int(lineas or 70), 400))
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


# ---------------------------------------------------------------------------------------------------------------------------------- mapa y temas
def _mapa():
    try:
        return json.loads((DOC / 'mapa.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'grupos': {}, 'temas': []}


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


def mapa(consulta='', id='', completo=False, maximo=5):
    """Busca temas por palabras (compacto), o con id= da el detalle de ese tema."""
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
        return cab + '\n\n'.join(s['texto'] for s in elegidas)
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


def resumen():
    try:
        return (DOC / 'RESUMEN.md').read_text(encoding='utf-8')
    except OSError:
        return 'no hay DOCUMENTACION/RESUMEN.md'


def cambios(n=6):
    """Las últimas n entradas EXPLICADAS del registro de cambios (las automáticas, que solo listan archivos, se saltan)."""
    ruta = RAIZ / 'REGISTRO_DE_CAMBIOS.txt'
    try:
        t = ruta.read_text(encoding='utf-8')
    except OSError:
        return 'no hay REGISTRO_DE_CAMBIOS.txt'
    entradas = re.split(r'(?m)^(?=\d{4}-\d\d-\d\d \d\d:\d\d  ·)', t)
    buenas = [e.strip() for e in entradas if re.match(r'\d{4}-\d\d-\d\d', e) and 'cambio explicado' in e.split('\n', 1)[0]]
    return '\n\n'.join((e if len(e) < 900 else e[:900] + ' …') for e in buenas[:max(1, int(n))]) or 'sin entradas explicadas'


# ---------------------------------------------------------------------------------------------------------------------------------- generar CLAUDE.md
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
            fuentes = [_nombre_corto(a) for a in t['archivos'][:3]] or t['simbolos'][:2]
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
    bloque = MARCA_INICIO + '\n' + '\n'.join(lineas) + '\n' + MARCA_FIN
    ruta = RAIZ / 'CLAUDE.md'
    t = ruta.read_text(encoding='utf-8')
    if MARCA_INICIO in t and MARCA_FIN in t:
        nuevo = t[:t.index(MARCA_INICIO)] + bloque + t[t.index(MARCA_FIN) + len(MARCA_FIN):]
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
        print(mapa(id=args[0]))
    elif orden == 'simbolo':
        print(simbolo(args[0], int(args[1]) if len(args) > 1 else 70))
    elif orden == 'modulo':
        print(modulo(args[0]))
    elif orden == 'cambios':
        print(cambios(int(args[0]) if args else 6))
    elif orden == 'resumen':
        print(resumen())
    elif orden == 'generar':
        av = generar()
        print('CLAUDE.md al día.' + (f' {len(av)} aviso(s):\n  ' + '\n  '.join(av) if av else ' Sin avisos.'))
    else:
        print('órdenes: mapa, tema, simbolo, modulo, cambios, resumen, generar')
    return 0


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    sys.exit(main(sys.argv))
