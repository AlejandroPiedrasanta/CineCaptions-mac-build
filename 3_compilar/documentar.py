# CineCaptions · By Cinema Productions
# 3_compilar/documentar.py — regenera el índice y el mapa del código del LEEME y anota los cambios en el registro.
"""
documentar.py
-------------
Mantiene al día la documentación SIN trabajo a mano:

  1. LEEME.txt: la cabecera con la versión al día (el índice de archivos y el mapa del código que antes se escribían aquí —267 KB, nadie
     los puede leer enteros— se quitaron: ahora se consultan por tema con 1_codigo/mapa_codigo.py / el MCP; cada carpeta ya trae su 0_LEEME.txt).
     Además reescribe el mapa de CLAUDE.md desde DOCUMENTACION/mapa.json y avisa de archivos o símbolos que ya no existen.
  2. REGISTRO_DE_CAMBIOS.txt: compara la huella SHA-256 de cada archivo con la de la vez anterior
     (3_compilar/huellas.json) y, si algo cambió, añade ARRIBA una entrada con la fecha, la versión y
     los archivos nuevos / modificados / quitados (máx. 12 por lista). El registro NO crece sin fin: pasado de 45 KB lo antiguo rota a
     DOCUMENTACION/historial/REGISTRO_<aaaa-mm>.txt y aquí quedan las entradas más nuevas (~30 KB).
  3. El 0_LEEME.txt de cada carpeta numerada: qué es la carpeta y qué hay dentro (cada archivo
     de código con su descripción; cada subcarpeta con lo que guarda).
  4. Avisa si algún archivo de código no tiene el encabezado de autor o si reaparece el nombre
     anterior del programa.

Uso (Construir_Instalador.ps1 lo corre solo en cada compilación):
    python 3_compilar/documentar.py                       # índice + mapa + registro automático
    python 3_compilar/documentar.py --nota "qué y por qué" # además, la explicación del cambio
"""
import ast
import datetime
import hashlib
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
LEEME = RAIZ / 'DOCUMENTACION' / 'LEEME.txt'
REGISTRO = RAIZ / 'DOCUMENTACION' / 'REGISTRO_DE_CAMBIOS.txt'
HUELLAS = RAIZ / '3_compilar' / 'huellas.json'
MARCA_REGISTRO = '=== ENTRADAS (la más nueva arriba) ==='
# lo que se vigila (lo que forma el programa y su documentación); 6_compilacion se rehace sola
VIGILADO = ('1_codigo', '2_recursos', '3_compilar', '4_diseno')      # el Administrador de Licencias vive en su propia carpeta y repositorio
IGNORADO = re.compile(r'(__pycache__|\.pyc$|huellas\.json$|\.exe$|(^|/)0_LEEME\.txt$)')
VIEJO = re.compile('Resolve ' + 'Creator ' + 'Subtitles|ResolveCreator' + 'Subtitles', re.I)

sys.path.insert(0, str(RAIZ / '3_compilar'))
import encabezados  # noqa: E402


def version():
    t = (RAIZ / '1_codigo' / 'version.py').read_text(encoding='utf-8')
    m = re.search(r"APP_VERSION = '([^']+)'", t)
    return m.group(1) if m else '?'


# ---------------------------------------------------------------- índice
def descripcion(p):
    """La 2.ª línea del encabezado: '<ruta> — <qué es>'."""
    rel = p.relative_to(RAIZ).as_posix()
    try:
        for linea in p.read_text(encoding='utf-8', errors='replace').splitlines()[:6]:
            s = re.sub(r'^\s*(?:#|--|//|;|rem)\s+', '', linea)
            for sep in (' — ', ' - '):          # el nombre puede llevar « - » dentro: se compara la ruta entera
                if s.startswith(rel + sep):
                    return s[len(rel) + len(sep):].strip()
    except OSError:
        pass
    return ''


def indice():
    grupos = [
        ('1_codigo', '1_codigo\\  EL PROGRAMA (va dentro del .exe)'),
        ('2_recursos/resolve_scripts', '2_recursos\\resolve_scripts\\  SCRIPTS QUE CORREN DENTRO DE DAVINCI RESOLVE'),
        ('2_recursos/motor_qwen', '2_recursos\\motor_qwen\\  MOTOR DE VOZ E IA (corre en su propio Python 3.12)'),
        ('3_compilar', '3_compilar\\  COMPILAR EL .EXE'),
        ('4_diseno', '4_diseno\\  DISEÑO (banner e icono)'),
    ]
    out = []
    for carpeta, titulo in grupos:
        archivos = []
        for p in sorted((RAIZ / carpeta).rglob('*'), key=lambda x: x.as_posix().lower()):
            if not p.is_file() or p.suffix.lower() not in encabezados.COMENTARIO or '__pycache__' in p.parts:
                continue
            if carpeta == '2_recursos' and 'resolve_scripts' not in p.parts and 'motor_qwen' not in p.parts:
                continue
            archivos.append(p)
        if not archivos:
            continue
        out.append(f'  {titulo}')
        for p in archivos:
            rel = p.relative_to(RAIZ).as_posix().replace('/', '\\')
            out.append(f'    {rel}')
            out.append(f'        {descripcion(p) or "(sin descripción: añádela en 3_compilar/encabezados.py)"}')
        out.append('')
    return out


# ---------------------------------------------------------------- mapa del código
def _doc1(nodo):
    d = ast.get_docstring(nodo) or ''
    d = re.sub(r'\s+', ' ', d).strip()
    return (d[:110] + '…') if len(d) > 110 else d


def mapa_py(p):
    arbol = ast.parse(p.read_text(encoding='utf-8'))
    out = []
    for n in arbol.body:
        if isinstance(n, ast.ClassDef):
            out.append(f'    {n.lineno:>5}  class {n.name}' + (f'  — {_doc1(n)}' if _doc1(n) else ''))
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append(f'    {m.lineno:>5}      .{m.name}()' + (f'  — {_doc1(m)}' if _doc1(m) else ''))
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(f'    {n.lineno:>5}  {n.name}()' + (f'  — {_doc1(n)}' if _doc1(n) else ''))
    return out


def mapa_lua(p):
    out = []
    for i, linea in enumerate(p.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
        m = re.match(r'^\s*(local\s+)?function\s+([\w.:]+)\s*\(', linea)
        if m and not linea.startswith((' ' * 8, '\t\t')):
            out.append(f'    {i:>5}  {m.group(2)}()')
    return out


def mapa():
    out = []
    for carpeta in ('1_codigo', '2_recursos/resolve_scripts', '2_recursos/motor_qwen'):
        for p in sorted((RAIZ / carpeta).glob('*.*'), key=lambda x: x.name.lower()):
            if p.suffix not in ('.py', '.lua'):
                continue
            rel = p.relative_to(RAIZ).as_posix().replace('/', '\\')
            lineas = p.read_text(encoding='utf-8', errors='replace').count('\n') + 1
            out.append(f'  {rel}  ({lineas} líneas)')
            try:
                out += mapa_py(p) if p.suffix == '.py' else mapa_lua(p)
            except SyntaxError as exc:
                out.append(f'    (no se pudo leer: {exc})')
            out.append('')
    return out


def reemplazar_entre(texto, inicio, fin, lineas):
    a = texto.index(inicio) + len(inicio)
    b = texto.index(fin, a)
    return texto[:a] + '\n' + '\n'.join(lineas).rstrip() + '\n' + texto[b:]


def actualizar_leeme():
    """Pone la versión en la cabecera del LEEME y quita (una sola vez) las secciones 13 y 14 que se escribían aquí (índice de archivos y mapa de código)."""
    if not LEEME.exists():
        print('  (no hay LEEME.txt)')
        return
    t = LEEME.read_text(encoding='utf-8')
    hoy = datetime.date.today().isoformat()
    corte = re.search(r'(?m)^13\. ÍNDICE DE ARCHIVOS', t)
    if corte:
        t = (t[:corte.start()].rstrip() + '\n\n\n13. ÍNDICE DE ARCHIVOS Y MAPA DEL CÓDIGO: ya no se escriben aquí (eran 267 KB).\n' + '-' * 80 + '\n'
             'Qué es cada archivo: el 0_LEEME.txt de su carpeta o «modulo(nombre)» del MCP. Dónde está algo: «mapa(consulta)». El código de una función: «simbolo(nombre)».\n'
             'Sin MCP: 6_compilacion\\venv315\\Scripts\\python.exe 1_codigo\\mapa_codigo.py mapa|simbolo|modulo <palabras>. Una página de todo: DOCUMENTACION\\RESUMEN.md.\n')
    t = re.sub(r'(?m)^\s+13\. Índice de archivos.*\n', '', t)
    t = re.sub(r'(?m)^\s+14\. Mapa del código.*\n', '', t)
    t = re.sub(r'(CINECAPTIONS )[\d.]+', r'\g<1>' + version(), t, count=1)
    t = re.sub(r'(?m)^ (?:Índice y mapa del código actualizados|Documentación al día) el \S+.*$', lambda m: f' Documentación al día el {hoy} (la rehace 3_compilar\\documentar.py)', t)
    aviso = 'LEEME.txt es para PERSONAS (~30 KB). Un asistente NO debe leerlo entero: DOCUMENTACION/RESUMEN.md + mapa()/simbolo() del MCP.'
    if aviso not in t:
        t = t.replace('Este archivo explica TODO el programa', aviso + '\n\nEste archivo explica TODO el programa', 1)
    LEEME.write_text(t, encoding='utf-8')
    print('  LEEME.txt: versión al día')


# ---------------------------------------------------------------- el 0_LEEME.txt de cada carpeta
CARPETAS = {
    '1_codigo': ('EL PROGRAMA', [
        'Todo CineCaptions en Python. Va DENTRO del .exe (3_compilar lo copia y lo compila).',
        'El principal es «CineCaptions (script principal).py»: la ventana, el Editor de palabras, GO,',
        'la licencia y main(). Cada tema pesado tiene su módulo (la lista de abajo).',
        'Cada archivo dice en su 2.ª línea qué es. La lógica completa: LEEME.txt, sección 4.']),
    '2_recursos': ('LO QUE VIAJA DENTRO DEL .EXE (además del código)', [
        'Todo lo de aquí lo busca el programa en BASE_RECURSOS (dentro del .exe, sys._MEIPASS). Los',
        'nombres de las subcarpetas los usa el código: NO se renombran. El logo va suelto aquí',
        'porque así queda también dentro del .exe.']),
    '3_compilar': ('COMPILAR EL .EXE', [
        'Construir_Instalador.ps1 lo hace todo y deja Instalar_CineCaptions_<versión>.exe en INSTALADORES/Windows:',
        '    powershell -ExecutionPolicy Bypass -File 3_compilar\\Construir_Instalador.ps1',
        'Ver LEEME.txt, sección 7.']),
    '4_diseno': ('DISEÑO', [
        'Lo que dibuja el banner y el icono del instalador, y notas sueltas. Nada de aquí va dentro',
        'del .exe: los scripts escriben su resultado en 3_compilar y 2_recursos.']),
    '6_compilacion': ('COMPILACIÓN (TEMPORAL)', [
        'Lo crea 3_compilar/Construir_Instalador.ps1. Se puede borrar entero: se rehace solo',
        '(la próxima compilación tarda más porque vuelve a preparar el entorno).']),
}
FIJAS = {
    '2_recursos/emojis': 'emojis Fluent 3D de Microsoft (MIT) en PNG + LICENCIAS.txt',
    '2_recursos/fonts': 'tipografías: Inter (la interfaz) y las de los packs; LICENCIAS.txt',
    '2_recursos/locales': 'textos de la interfaz en en, pt, fr, de, it (la clave es el español)',
    '2_recursos/motor_qwen': 'motor de voz e IA (corren en su propio Python 3.12) y sus versiones fijas',
    '2_recursos/plantillas_incluidas': 'los packs de estilos que trae el programa (.drt/.drb + posiciones + pack.json)',
    '2_recursos/resolve_scripts': 'los scripts que se instalan en DaVinci Resolve (Lua = Free, Python = Studio) y sfx_rules.json',
    '2_recursos/sfx_library': 'los efectos de sonido, una carpeta por categoría',
    '2_recursos/logo_cinecaptions.png': 'el icono del programa (lo crea 4_diseno/icono/crear_icono.py)',
    '2_recursos/logo_cinecaptions.ico': 'el icono del .exe y del instalador',
    '2_recursos/resolve_scripts/sfx_rules.json': 'cuándo suena cada efecto de sonido (editable sin tocar código)',
    '2_recursos/motor_qwen/requisitos_motor_qwen.txt': 'versiones FIJAS del motor (Python 3.12 + torch + qwen-asr)',
    '3_compilar/app.manifest': 'manifiesto del instalador (sin permisos de administrador)',
    '3_compilar/banner.jpg': 'el banner del instalador (lo dibuja 4_diseno/banner/crear_banner.py)',
    '3_compilar/requirements.txt': 'librerías del programa con versión FIJA (Python 3.14)',
    '3_compilar/huellas.json': 'huellas de cada archivo: con ellas documentar.py anota qué cambió',
    '4_diseno/banner': 'crear_banner.py: dibuja 3_compilar/banner.jpg',
    '4_diseno/icono': 'crear_icono.py + logo_original.jpg: crean 2_recursos/logo_cinecaptions.png y .ico',
    '4_diseno/icono/logo_original.jpg': 'el logo original del que sale el icono',
    '4_diseno/notas': 'notas y pedidos sueltos (no van al programa)',
    '2_recursos/plantillas_incluidas/Plantillas virales cinema Luxe superior': 'pack «Plantillas virales cinema · Luxe · superior» (horizontal y vertical, .drb + .drt)',
    '2_recursos/plantillas_incluidas/Plantillas virales cinema Luxe centro': 'pack «Plantillas virales cinema · Luxe · centro» (horizontal y vertical, .drb + .drt)',
    '2_recursos/plantillas_incluidas/Plantillas virales cinema Luxe inferior': 'pack «Plantillas virales cinema · Luxe · inferior» (horizontal y vertical, .drb + .drt)',
    '2_recursos/plantillas_incluidas/Plantillas virales cinema Amro superior': 'pack «Plantillas virales cinema · Amro · superior» (horizontal y vertical, .drb + .drt)',
    '2_recursos/plantillas_incluidas/Plantillas virales cinema Amro centro': 'pack «Plantillas virales cinema · Amro · centro» (horizontal y vertical, .drb + .drt)',
    '2_recursos/plantillas_incluidas/Plantillas virales cinema Amro inferior': 'pack «Plantillas virales cinema · Amro · inferior» (horizontal y vertical, .drb + .drt)',
    '4_diseno/propuesta_sonido': 'imagenes de la nueva pantalla Sonido (sin pad XY) y 100 mejoras de rendimiento e interfaz',
    '4_diseno/plantillas_virales': 'cómo y con qué se hicieron los packs «Plantillas virales cinema» (scripts, calibración, vistas)',
    '4_diseno/plantillas_virales/vistas': 'una hoja por pack con los sets 1..6 y la base, renderizada en Resolve',
    '4_diseno/plantillas_virales/diseno.json': 'el diseño resuelto de los 12 packs (tamaños y posiciones de los 19 clips de cada uno)',
    '4_diseno/plantillas_virales/cal_v.json': 'calibración vertical: cuánto mide cada preset a un tamaño conocido',
    '4_diseno/plantillas_virales/cal_h.json': 'calibración horizontal (la misma medida a 1920×1080)',
    '4_diseno/plantillas_virales/PLANTILLAS VIRALES CINEMA - como se hicieron.txt': 'el documento de cómo se crearon los packs «Plantillas virales cinema»',
    '2_recursos/plantillas_incluidas/Subtitulos basicos': 'pack «Subtítulos básicos» (horizontal y vertical)',
    '6_compilacion/python-3.15.1': 'el Python principal con el que se compila (sin tocar el sistema)',
    '6_compilacion/venv315': 'el entorno Python 3.15.1 con las librerías fijas de 3_compilar/requirements.txt',
    '6_compilacion/fuentes': 'copia del código preparada para PyInstaller',
    '6_compilacion/work': 'trabajo intermedio de PyInstaller',
    '6_compilacion/dist': 'el programa compilado (lo que va dentro del instalador)',
    '6_compilacion/instalador': 'el instalador compilado antes de pegarle el programa',
    '6_compilacion/autoprueba.txt': 'resultado de la última autoprueba del programa compilado',
}


def _que_es(p):
    rel = p.relative_to(RAIZ).as_posix()
    return descripcion(p) if p.suffix.lower() in encabezados.COMENTARIO else FIJAS.get(rel, '')


def _arbol(carpeta, nivel=1):
    out = []
    hijos = sorted(carpeta.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    for h in hijos:
        if h.name == '0_LEEME.txt' or h.name == '__pycache__':
            continue
        sangria = '    ' * nivel
        if h.is_dir():
            archivos = [x for x in h.rglob('*') if x.is_file() and '__pycache__' not in x.parts]
            out.append(f'{sangria}{h.name}\\   ({len(archivos)} archivos)' +
                       (f'  — {FIJAS[h.relative_to(RAIZ).as_posix()]}' if h.relative_to(RAIZ).as_posix() in FIJAS else ''))
            # se detalla lo que es código o pocos archivos; las bibliotecas grandes, solo el total
            if nivel == 1 and len(archivos) <= 30 and not h.relative_to(RAIZ).as_posix().startswith('6_compilacion'):
                out += _arbol(h, nivel + 1)
        else:
            q = _que_es(h)
            out.append(f'{sangria}{h.name}' + (f'\n{sangria}    {q}' if q else ''))
    return out


def leemes_de_carpeta():
    """Escribe el 0_LEEME.txt de cada carpeta numerada (solo si cambió)."""
    hechos = 0
    for nombre, (titulo, intro) in CARPETAS.items():
        carpeta = RAIZ / nombre
        if not carpeta.is_dir():
            continue
        lineas = ['=' * 78, f' {nombre}\\  —  {titulo}', ' CineCaptions · By Cinema Productions', '=' * 78, '']
        lineas += intro + ['', 'QUÉ HAY DENTRO (lo escribe 3_compilar/documentar.py; no lo edites a mano)',
                           '-' * 78] + _arbol(carpeta) + ['']
        texto = '\n'.join(lineas)
        destino = carpeta / '0_LEEME.txt'
        if not destino.exists() or destino.read_text(encoding='utf-8') != texto:
            destino.write_text(texto, encoding='utf-8')
            hechos += 1
    print(f'  0_LEEME.txt de cada carpeta: {hechos} actualizado/s')


# ---------------------------------------------------------------- registro de cambios
def huellas_actuales():
    h = {}
    for carpeta in VIGILADO:
        for p in (RAIZ / carpeta).rglob('*'):
            if p.is_file():
                rel = p.relative_to(RAIZ).as_posix()
                if not IGNORADO.search(rel):
                    h[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return h


def anotar(nota=''):
    nuevas = huellas_actuales()
    try:
        viejas = json.loads(HUELLAS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        viejas = None
    if viejas is None:
        cambios = None
    else:
        cambios = {'nuevos': sorted(set(nuevas) - set(viejas)),
                   'modificados': sorted(k for k in nuevas if k in viejas and nuevas[k] != viejas[k]),
                   'quitados': sorted(set(viejas) - set(nuevas))}
    hay = cambios is None or any(cambios.values())
    if hay or nota:
        ahora = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        entrada = [f'{ahora}  ·  v{version()}  ·  ' + ('cambio explicado' if nota else '(automático)')]
        if nota:
            entrada += ['    ' + l for l in nota.strip().splitlines()]
        if cambios is None:
            entrada.append(f'    Primera huella: {len(nuevas)} archivos vigilados (desde aquí se anota cada cambio).')
        else:
            for clave, signo in (('nuevos', '+'), ('modificados', '~'), ('quitados', '-')):
                lista = cambios[clave]
                if lista:
                    entrada.append(f'    {clave} ({len(lista)}):')
                    entrada += [f'      {signo} {r}' for r in lista[:12]]
                    if len(lista) > 12:
                        entrada.append(f'      … y {len(lista) - 12} más')
        t = REGISTRO.read_text(encoding='utf-8') if REGISTRO.exists() else MARCA_REGISTRO + '\n'
        if MARCA_REGISTRO not in t:
            t += '\n' + MARCA_REGISTRO + '\n'
        a = t.index(MARCA_REGISTRO) + len(MARCA_REGISTRO)
        resto = t[a:].lstrip('\n')
        t = t[:a] + '\n\n' + '\n'.join(entrada) + '\n' + ('\n' + resto if resto else '')
        REGISTRO.write_text(t, encoding='utf-8')
        print(f'  REGISTRO_DE_CAMBIOS.txt: entrada nueva ({"primera huella" if cambios is None else ", ".join(f"{len(v)} {k}" for k, v in cambios.items() if v) or "nota"})')
    else:
        print('  REGISTRO_DE_CAMBIOS.txt: sin cambios desde la última vez')
    HUELLAS.write_text(json.dumps(nuevas, indent=0, sort_keys=True), encoding='utf-8')
    rotar_registro()


def rotar_registro(maximo=45_000, conservar=30_000):
    """El registro de cambios no crece sin fin: si pasa de `maximo` bytes, lo antiguo se archiva por mes en DOCUMENTACION/historial/."""
    if not REGISTRO.exists() or REGISTRO.stat().st_size <= maximo:
        return
    t = REGISTRO.read_text(encoding='utf-8')
    a = t.index(MARCA_REGISTRO) + len(MARCA_REGISTRO)
    cabecera, cuerpo = t[:a], t[a:]
    entradas = [e for e in re.split(r'(?m)^(?=\d{4}-\d\d-\d\d \d\d:\d\d  ·)', cuerpo) if e.strip()]
    quedan, peso = [], 0
    for e in entradas:
        if peso + len(e) > conservar and len(quedan) >= 12:
            break
        quedan.append(e)
        peso += len(e)
    movidas = entradas[len(quedan):]
    if not movidas:
        return
    carpeta = RAIZ / 'DOCUMENTACION' / 'historial'
    carpeta.mkdir(parents=True, exist_ok=True)
    por_mes = {}
    for e in movidas:
        por_mes.setdefault(e[:7], []).append(e)
    for mes, lista in por_mes.items():
        destino = carpeta / f'REGISTRO_{mes}.txt'
        previo = destino.read_text(encoding='utf-8') if destino.exists() else f'REGISTRO DE CAMBIOS ARCHIVADO · {mes} (la entrada más nueva arriba)\n\n'
        cab, _, resto = previo.partition('\n\n')
        destino.write_text(cab + '\n\n' + ''.join(lista) + resto, encoding='utf-8')
    REGISTRO.write_text(cabecera + '\n\n' + ''.join(quedan) + '\n(Lo anterior está archivado por mes en DOCUMENTACION/historial/REGISTRO_<aaaa-mm>.txt)\n', encoding='utf-8')
    print(f'  REGISTRO_DE_CAMBIOS.txt: {len(movidas)} entradas antiguas archivadas en DOCUMENTACION/historial/')


# ---------------------------------------------------------------- comprobaciones
def revisar():
    avisos = 0
    for rel in encabezados.sin_encabezado():
        print('  AVISO: sin encabezado de autor/descripción:', rel)
        avisos += 1
    for carpeta in VIGILADO + ('.',):
        base = RAIZ / carpeta
        archivos = base.rglob('*') if carpeta != '.' else base.glob('*.txt')
        for p in archivos:
            if p.is_file() and p.suffix.lower() in ('.py', '.lua', '.cs', '.ps1', '.json', '.txt', '.md', '.nsi', '.bat', '.spec', '.sql') \
                    and '__pycache__' not in p.parts and p.name != 'documentar.py':
                if VIEJO.search(p.read_text(encoding='utf-8', errors='replace')):
                    print('  AVISO: aparece el nombre anterior del programa en', p.relative_to(RAIZ))
                    avisos += 1
    return avisos


def main(argv):
    nota = ''
    if '--nota' in argv:
        i = argv.index('--nota')
        nota = ' '.join(argv[i + 1:])
    print(f'Documentación de CineCaptions v{version()}')
    actualizar_leeme()
    leemes_de_carpeta()
    anotar(nota)
    try:
        sys.path.insert(0, str(RAIZ / '1_codigo'))
        import mapa_codigo
        avisos_mapa = mapa_codigo.generar()
        print('  CLAUDE.md: mapa de temas al día' + (f' — {len(avisos_mapa)} aviso/s:' if avisos_mapa else ''))
        for a in avisos_mapa:
            print('    AVISO mapa:', a)
    except Exception as e:                      # la documentación nunca debe romper la compilación
        print('  (no se pudo regenerar el mapa de CLAUDE.md:', e, ')')
    avisos = revisar()
    print('  revisión:', 'todo en orden' if not avisos else f'{avisos} aviso/s')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
