# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/simular_equipos.py — simula equipos de clientes (Windows y Mac) sin tocar el equipo real: dónde está Resolve, IA lenta o colgada, VRAM, drivers, tarjetas del Registro.
"""
    6_compilacion/venv315/Scripts/python.exe 1_codigo/herramientas_dev/simular_equipos.py [--rapido] [filtro]

Nació del reporte de un cliente (v5.71): Resolve Studio 21 instalado en otro disco → «No hay DaVinci Resolve en este equipo», y la IA de texto
en una RTX 5050 de 8 GB con Resolve abierto, cortada a los 100 s y desactivada para toda la sesión. Cada caso es un equipo distinto simulado
con un disco FALSO (se parchean os.path / pathlib / open), procesos falsos o funciones sustituidas; nada escribe en el proyecto ni en las
preferencias reales (los temporales van a la carpeta temporal del sistema). Sin Resolve, sin GPU y sin red.

Sale 0 si todo pasa, 1 si algo falla. --rapido salta los casos que esperan tiempos reales (IA lenta/colgada). `filtro`: solo los casos cuyo
nombre lo contenga. Añade aquí un caso por cada error que reporte un cliente: así no vuelve.
"""
import builtins
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import types

CODIGO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.dirname(CODIGO)
sys.path.insert(0, CODIGO)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

RAPIDO = '--rapido' in sys.argv
FILTRO = next((a for a in sys.argv[1:] if not a.startswith('--')), '')
RESULTADOS = []          # (grupo, nombre, ok, detalle)
CASOS = []


def caso(grupo, lento=False):
    def deco(f):
        CASOS.append((grupo, f, lento))
        return f
    return deco


def esperar(cond, detalle=''):
    if not cond:
        raise AssertionError(detalle or 'condición falsa')


# ---------------------------------------------------------------------------------------------------------------------------------------
# un disco falso: solo existen los archivos/carpetas que dice el caso (el resto del disco real sigue visible para lo que no sea Resolve)
# ---------------------------------------------------------------------------------------------------------------------------------------
def _norm(p):
    return str(p).replace('\\', '/').rstrip('/').lower()


ZONAS = ('/program files', 'program files/blackmagic design', '/applications', 'davinci resolve', 'blackmagic design', 'start menu')


@contextlib.contextmanager
def disco_falso(archivos=(), carpetas=(), contenido=None, plataforma=None, entorno=None):
    """`archivos`/`carpetas`: rutas que existen. Las rutas de las ZONAS que no estén aquí NO existen (aunque existan en este equipo).
    `contenido`: {ruta: bytes} para open(). `plataforma`: 'win32' / 'darwin' durante el caso. `entorno`: variables de entorno extra."""
    arch = {_norm(a) for a in archivos}
    carp = {_norm(c) for c in carpetas}
    for a in list(arch) + list(carp):                       # las carpetas de cada archivo también existen
        partes = a.split('/')
        for i in range(1, len(partes)):
            carp.add('/'.join(partes[:i]))
    cont = {_norm(k): v for k, v in (contenido or {}).items()}

    propias = tuple(_norm(x) for x in (RAIZ, tempfile.gettempdir(), sys.prefix, sys.base_prefix))      # el proyecto (su ruta lleva «DAVINCI RESOLVE»), temporales y Python

    def en_zona(p):
        n = _norm(p)
        return any(z in n for z in ZONAS) and not n.startswith(propias)

    reales = (os.path.isfile, os.path.isdir, os.path.exists, pathlib.Path.is_file, pathlib.Path.is_dir, pathlib.Path.exists, builtins.open)

    def isfile(p):
        return _norm(p) in arch or (False if en_zona(p) else reales[0](p))

    def isdir(p):
        return _norm(p) in carp or (False if en_zona(p) else reales[1](p))

    def exists(p):
        return _norm(p) in arch or _norm(p) in carp or (False if en_zona(p) else reales[2](p))

    def abrir(p, *a, **k):
        if isinstance(p, (str, os.PathLike)) and en_zona(p):
            n = _norm(p)
            if n in cont:
                return io.BytesIO(cont[n])
            raise FileNotFoundError(str(p))
        return reales[6](p, *a, **k)

    viejo_plat = sys.platform
    viejo_env = dict(os.environ)
    os.path.isfile, os.path.isdir, os.path.exists = isfile, isdir, exists
    pathlib.Path.is_file = lambda self: isfile(self)
    pathlib.Path.is_dir = lambda self: isdir(self)
    pathlib.Path.exists = lambda self, **k: exists(self)
    builtins.open = abrir
    if plataforma:
        sys.platform = plataforma
    os.environ.update(entorno or {})
    try:
        yield
    finally:
        os.path.isfile, os.path.isdir, os.path.exists = reales[0], reales[1], reales[2]
        pathlib.Path.is_file, pathlib.Path.is_dir, pathlib.Path.exists = reales[3], reales[4], reales[5]
        builtins.open = reales[6]
        sys.platform = viejo_plat
        os.environ.clear()
        os.environ.update(viejo_env)


@contextlib.contextmanager
def parches(*trios):
    """parches((modulo, 'nombre', valor), …) y los devuelve al salir."""
    viejos = [(m, n, getattr(m, n)) for m, n, _v in trios]
    for m, n, v in trios:
        setattr(m, n, v)
    try:
        yield
    finally:
        for m, n, v in viejos:
            setattr(m, n, v)


# ---------------------------------------------------------------------------------------------------------------------------------------
# módulos del programa
# ---------------------------------------------------------------------------------------------------------------------------------------
import ajustes_ui  # noqa: E402
import ia_texto  # noqa: E402
import instalador_scripts  # noqa: E402
import motor_voz  # noqa: E402
import registro_ayuda  # noqa: E402
import resolve_bridge  # noqa: E402
import resolve_mcp  # noqa: E402

_PRINCIPAL = {}


def principal():
    """El script principal (solo importado, sin ventana) para llamar métodos sueltos de SubtitleApp con un `self` falso."""
    if 'M' not in _PRINCIPAL:
        spec = importlib.util.spec_from_file_location('cc_main_sim', os.path.join(CODIGO, 'CineCaptions (script principal).py'))
        M = importlib.util.module_from_spec(spec)
        sys.modules['cc_main_sim'] = M
        spec.loader.exec_module(M)
        _PRINCIPAL['M'] = M
    return _PRINCIPAL['M']


WIN_DEF = r'C:\Program Files\Blackmagic Design\DaVinci Resolve'
LNK = r'C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Blackmagic Design\DaVinci Resolve\DaVinci Resolve.lnk'


def lnk_hacia(carpeta):
    """Un .lnk con el formato REAL del acceso de Blackmagic (Resolve 21, MSI; revisado 2026-11-05): banderas 0x40dd = IDList + nombre +
    ruta relativa + carpeta de trabajo + ícono, en Unicode y SIN LinkInfo (no trae LocalBasePath). La ruta relativa sube desde el .lnk."""
    import struct
    banderas = 0x1 | 0x4 | 0x8 | 0x10 | 0x40 | 0x80
    cab = struct.pack('<I', 0x4C) + b'\x01\x14\x02\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00\x46' + struct.pack('<I', banderas)
    cab += b'\x00' * (0x4C - len(cab))
    idlist = b'\x14\x00' + b'\x00' * 20
    profundidad = len([p for p in LNK.split('\\')[:-1] if p]) - 1          # carpetas desde la raíz del disco hasta la del .lnk
    relativa = '..\\' * profundidad + carpeta.split(':\\', 1)[1] + '\\Resolve.exe' if carpeta[:3].upper() == LNK[:3].upper() else ''

    def cadena(t):
        return struct.pack('<H', len(t)) + t.encode('utf-16-le')
    datos = cab + struct.pack('<H', len(idlist)) + idlist + cadena('DaVinci Resolve') + cadena(relativa) + cadena(carpeta + '\\')
    return datos + cadena('C:\\WINDOWS\\Installer\\{1E0A7C6D-0000}\\ResolveIcon.exe') + b'\x00' * 4


def motivo_mp4(prefs=None):
    M = principal()
    falso = types.SimpleNamespace()
    with parches((ajustes_ui, 'leer_prefs', lambda: dict(prefs or {}))):
        return M.SubtitleApp._motivo_mp4(falso)


def detectar_win(archivos=(), carpetas=(), contenido=None, proceso=None, discos=('C',), prefs=None):
    resolve_bridge._DIR_RESOLVE[:] = [None, 0.0]
    with disco_falso(archivos, carpetas, contenido, 'win32', {'ProgramData': r'C:\ProgramData', 'APPDATA': r'C:\Users\Cliente\AppData\Roaming'}), \
            parches((resolve_bridge, '_resolve_en_marcha', lambda: proceso), (resolve_bridge, '_discos_fijos', lambda: list(discos))):
        try:
            import winreg
            with parches((winreg, 'OpenKey', _sin_registro)):
                return motivo_mp4(prefs), resolve_bridge._resolve_dir_windows()
        finally:
            resolve_bridge._DIR_RESOLVE[:] = [None, 0.0]


def _sin_registro(*a, **k):
    raise OSError('registro simulado: el instalador de Blackmagic solo deja «Version»')


# ---------------------------------------------------------------------------------------------------------------------------------------
# A. ¿Hay Resolve? (Windows)
# ---------------------------------------------------------------------------------------------------------------------------------------
@caso('Resolve Windows')
def win_ruta_normal():
    m, d = detectar_win([WIN_DEF + r'\Resolve.exe', WIN_DEF + r'\ResolveMCP.exe'])
    esperar(m is None and _norm(d) == _norm(WIN_DEF), f'{m} {d}')


@caso('Resolve Windows')
def win_otro_disco_por_acceso_del_menu():          # el caso del cliente (v5.71)
    otra = r'D:\Programas\DaVinci Resolve Studio'
    m, d = detectar_win([otra + r'\Resolve.exe', LNK], contenido={LNK: lnk_hacia(otra)}, discos=('C', 'D'))
    esperar(m is None and _norm(d) == _norm(otra), f'{m} {d}')


@caso('Resolve Windows')
def win_otro_disco_abierto_sin_acceso():
    otra = r'E:\Blackmagic\Resolve'
    m, d = detectar_win([otra + r'\Resolve.exe'], proceso=otra, discos=('C', 'E'))
    esperar(m is None and _norm(d) == _norm(otra), f'{m} {d}')


@caso('Resolve Windows')
def win_otro_disco_por_barrido_de_discos():
    otra = r'F:\Program Files\Blackmagic Design\DaVinci Resolve'
    m, d = detectar_win([otra + r'\Resolve.exe'], discos=('C', 'D', 'F'))
    esperar(m is None and _norm(d) == _norm(otra), f'{m} {d}')


@caso('Resolve Windows')
def win_usuario_con_tildes_y_espacios():
    otra = r'D:\Edición Ñandú\DaVinci Resolve'
    m, d = detectar_win([otra + r'\Resolve.exe', LNK], contenido={LNK: lnk_hacia(otra)}, discos=('C', 'D'))
    esperar(m is None and _norm(d) == _norm(otra), f'{m} {d}')


@caso('Resolve Windows')
def win_desinstalado_con_carpeta_residual():
    m, _d = detectar_win(carpetas=[WIN_DEF])
    esperar(m == 'sin_resolve', f'motivo={m} (una carpeta vacía no es Resolve)')


@caso('Resolve Windows')
def win_acceso_roto_hacia_disco_quitado():
    m, _d = detectar_win([LNK], contenido={LNK: lnk_hacia(r'G:\DaVinci Resolve')})
    esperar(m == 'sin_resolve', f'motivo={m}')


@caso('Resolve Windows')
def win_sin_resolve():
    m, _d = detectar_win()
    esperar(m == 'sin_resolve', f'motivo={m}')


@caso('Resolve Windows')
def win_ajuste_mp4_con_resolve():
    m, _d = detectar_win([WIN_DEF + r'\Resolve.exe'], prefs={'go_salida_mp4': True})
    esperar(m == 'ajuste', f'motivo={m}')


@caso('Resolve Windows')
def win_fusionscript_sale_de_la_carpeta_real():
    otra = r'D:\DaVinci Resolve'
    resolve_bridge._DIR_RESOLVE[:] = [None, 0.0]
    with disco_falso([otra + r'\Resolve.exe', otra + r'\fusionscript.dll'], plataforma='win32'), \
            parches((resolve_bridge, '_resolve_en_marcha', lambda: otra), (resolve_bridge, '_discos_fijos', lambda: ['C', 'D'])):
        libs = [str(lib) for _m, lib in resolve_bridge._rutas_probables()]
    resolve_bridge._DIR_RESOLVE[:] = [None, 0.0]
    esperar(any(_norm(l) == _norm(otra + r'\fusionscript.dll') for l in libs), str(libs))


@caso('Resolve Windows')
def win_mcp_en_otro_disco():
    otra = r'D:\DaVinci Resolve'
    resolve_bridge._DIR_RESOLVE[:] = [None, 0.0]
    with disco_falso([otra + r'\Resolve.exe', otra + r'\ResolveMCP.exe'], plataforma='win32'), \
            parches((resolve_bridge, '_resolve_en_marcha', lambda: otra), (resolve_bridge, '_discos_fijos', lambda: ['C', 'D'])):
        r = resolve_mcp.ruta_exe()
    resolve_bridge._DIR_RESOLVE[:] = [None, 0.0]
    esperar(r is not None and _norm(r) == _norm(otra + r'\ResolveMCP.exe'), str(r))


@caso('Resolve Windows')
def win_lnk_real_de_este_equipo():
    """El acceso REAL del menú Inicio de este equipo (solo se lee): sin LinkInfo, la carpeta sale de WORKING_DIR / la ruta relativa."""
    real = os.path.join(os.environ.get('ProgramData', r'C:\ProgramData'), r'Microsoft\Windows\Start Menu\Programs\Blackmagic Design\DaVinci Resolve\DaVinci Resolve.lnk')
    if not os.path.isfile(real):
        AVISOS.append('este equipo no tiene el acceso de Resolve en el menú Inicio: caso del .lnk real sin probar')
        return
    carpetas = resolve_bridge._carpetas_del_lnk(real)
    esperar(any(os.path.isfile(os.path.join(c, 'Resolve.exe')) for c in carpetas), f'el .lnk real no dio la carpeta de Resolve: {carpetas}')


@caso('Resolve Windows')
def win_sin_resolve_no_repite_la_busqueda():
    llamadas = []
    resolve_bridge._DIR_RESOLVE[:] = [None, 0.0]
    with disco_falso(plataforma='win32'), parches((resolve_bridge, '_resolve_dir_extra', lambda: llamadas.append(1))):
        for _ in range(20):
            resolve_bridge._resolve_dir_windows()
    resolve_bridge._DIR_RESOLVE[:] = [None, 0.0]
    esperar(len(llamadas) == 1, f'sin Resolve se buscó {len(llamadas)} veces en 20 consultas (debía 1 por minuto)')


# ---------------------------------------------------------------------------------------------------------------------------------------
# B. ¿Hay Resolve? (Mac)
# ---------------------------------------------------------------------------------------------------------------------------------------
def detectar_mac(carpetas=(), archivos=(), prefs=None):
    with disco_falso(archivos, carpetas, plataforma='darwin'):
        return motivo_mp4(prefs)


@caso('Resolve Mac')
def mac_resolve_normal():
    esperar(detectar_mac(['/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/MacOS']) is None)


@caso('Resolve Mac')
def mac_resolve_studio_con_otro_nombre():
    esperar(detectar_mac(['/Applications/DaVinci Resolve Studio/DaVinci Resolve Studio.app/Contents/MacOS']) is None)


@caso('Resolve Mac')
def mac_resolve_en_applications_del_usuario():
    home = str(pathlib.Path.home()).replace('\\', '/')
    esperar(detectar_mac([home + '/Applications/DaVinci Resolve.app/Contents/MacOS']) is None)


@caso('Resolve Mac')
def mac_solo_ajustes_residuales():
    esperar(detectar_mac(['/Library/Application Support/Blackmagic Design/DaVinci Resolve']) == 'sin_resolve')


@caso('Resolve Mac')
def mac_mcp_ruta_oficial():
    exe = '/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolveMCP'
    with disco_falso([exe], plataforma='darwin'):
        r = resolve_mcp.ruta_exe()
    esperar(r is not None and _norm(r) == _norm(exe), str(r))


@caso('Resolve Mac')
def mac_ia_de_texto_no_se_intenta():
    with parches((sys, 'platform', 'darwin')):
        esperar(motor_voz.info_instalado() is None and not ia_texto.activa(), 'en Mac no hay motor Qwen: no debe intentarse')


# ---------------------------------------------------------------------------------------------------------------------------------------
# C. IA de texto: el protocolo con el proceso del modelo (procesos falsos de verdad)
# ---------------------------------------------------------------------------------------------------------------------------------------
class _ServidorFalso(ia_texto._Servidor):
    def __init__(self, codigo):
        self.modelo = 'falso'
        self.p = subprocess.Popen([sys.executable, '-c', codigo], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.lineas = __import__('queue').Queue()
        self.errores = []
        threading.Thread(target=self._leer, daemon=True).start()
        threading.Thread(target=self._leer_err, daemon=True).start()


def _fake(cuerpo):
    return 'import sys, time, json\nsys.stdin.readline()\n' + cuerpo + '\ntry:\n    sys.stdin.readline()\nexcept Exception:\n    pass\n'


@caso('IA de texto')
def ia_respuesta_normal():
    ok, t = _ServidorFalso(_fake('print("PROGRESO|0.5", flush=True); print("LISTO|x", flush=True)')).pedir('a', 'b', lambda *a: None, timeout=30, sin_senal=5)
    esperar(ok and t == 'x', f'{ok} {t}')


@caso('IA de texto', lento=True)
def ia_lenta_con_latidos_no_se_corta():           # el caso del cliente: 8 GB + Resolve, una tanda tarda más que sin_senal
    cuerpo = 'for _ in range(7):\n    print("LATIDO|", flush=True); time.sleep(1)\nprint("LISTO|ok", flush=True)'
    with parches((ia_texto, 'AVISO_LENTA_S', 2)):
        ok, t = _ServidorFalso(_fake(cuerpo)).pedir('a', 'b', lambda *a: None, timeout=60, sin_senal=3)
    esperar(ok and t == 'ok', f'{ok} {t}')


@caso('IA de texto', lento=True)
def ia_latidos_sin_avance_se_corta():
    cuerpo = 'for _ in range(40):\n    print("LATIDO|", flush=True); time.sleep(1)\nprint("LISTO|ok", flush=True)'
    with parches((ia_texto, 'SIN_AVANCE_S', 4)):
        t0 = time.time()
        ok, t = _ServidorFalso(_fake(cuerpo)).pedir('a', 'b', lambda *a: None, timeout=60, sin_senal=3)
    esperar(not ok and 'no avanzó' in t and time.time() - t0 < 30, f'{ok} {t}')


@caso('IA de texto', lento=True)
def ia_colgada_en_silencio_se_corta():
    t0 = time.time()
    ok, t = _ServidorFalso(_fake('time.sleep(60)')).pedir('a', 'b', lambda *a: None, timeout=60, sin_senal=3)
    esperar(not ok and 'sin responder' in t and time.time() - t0 < 30, f'{ok} {t}')


@caso('IA de texto', lento=True)
def ia_tope_total_da_un_motivo_claro():
    """Revisión 5.71: al agotarse el tope total (con latidos) se informaba la última línea de stderr (la barra de carga) como motivo."""
    cuerpo = 'import sys\nsys.stderr.write("Loading checkpoint shards: 100%\\n"); sys.stderr.flush()\nfor _ in range(30):\n    print("LATIDO|", flush=True); time.sleep(1)'
    ok, t = _ServidorFalso(_fake(cuerpo)).pedir('a', 'b', lambda *a: None, timeout=4, sin_senal=3)
    esperar(not ok and 'no terminó en 4 s' in t, f'{ok} {t}')


@caso('IA de texto')
def ia_proceso_muere_da_su_error():
    ok, t = _ServidorFalso('import sys\nsys.stdin.readline()\nsys.stderr.write("CUDA out of memory\\n"); sys.exit(3)').pedir('a', 'b', lambda *a: None, timeout=30, sin_senal=5)
    esperar(not ok and 'out of memory' in t, f'{ok} {t}')


@caso('IA de texto')
def ia_linea_error():
    ok, t = _ServidorFalso(_fake('print("ERROR|RuntimeError: sin VRAM", flush=True)')).pedir('a', 'b', lambda *a: None, timeout=30, sin_senal=5)
    esperar(not ok and 'sin VRAM' in t, f'{ok} {t}')


@caso('IA de texto')
def ia_ruta_temporal_con_tildes():
    """El usuario se llama «José Peña»: el pedido viaja por un JSON en %TEMP%; el modelo lo lee y escribe la salida."""
    carpeta = tempfile.mkdtemp(prefix='cc_José Peña Ñ ')
    entrada = os.path.join(carpeta, 'pedido.json')
    salida = os.path.join(carpeta, 'pedido.out.json')
    with open(entrada, 'w', encoding='utf-8') as f:
        json.dump({'palabras': ['hola', 'canción']}, f, ensure_ascii=False)
    cuerpo = ('orden = json.loads(sys.stdin.readline())\n'
              'datos = json.load(open(orden["entrada"], encoding="utf-8"))\n'
              'json.dump({"correcciones": {"1": datos["palabras"][1].upper()}}, open(orden["salida"], "w", encoding="utf-8"), ensure_ascii=False)\n'
              'print("LISTO|" + orden["salida"], flush=True)\nsys.stdin.readline()')
    s = _ServidorFalso('import sys, json\n' + cuerpo)
    ok, t = s.pedir(entrada, salida, lambda *a: None, timeout=30, sin_senal=5)
    datos = json.load(open(salida, encoding='utf-8')) if ok else {}
    __import__('shutil').rmtree(carpeta, ignore_errors=True)
    esperar(ok and datos.get('correcciones', {}).get('1') == 'CANCIÓN', f'{ok} {t} {datos}')


@caso('IA de texto')
def ia_servidor_real_manda_latidos():
    """motor_texto.servidor() de verdad (modelo sustituido por un sleep): mientras trabaja tiene que decir LATIDO."""
    guion = ('import sys, time\nsys.path.insert(0, %r)\nimport motor_texto as m\nm.cargar = lambda p: (None, None, "repo", "cpu")\n'
             'm.calentar = lambda t, mo: None\nm.analizar_con = lambda *a: (time.sleep(%d), m.decir("LISTO", "x"))\nm.servidor(None, 3)\n'
             % (os.path.join(RAIZ, '2_recursos', 'motor_qwen'), 4 if RAPIDO else 17))
    r = subprocess.run([sys.executable, '-c', guion], input='{"entrada":"a","salida":"b"}\n', capture_output=True, text=True, timeout=90)
    lineas = r.stdout.split()
    esperar('LISTA|repo' in lineas and 'LISTO|x' in lineas and (RAPIDO or 'LATIDO|' in lineas), r.stdout + r.stderr[-400:])


# ---------------------------------------------------------------------------------------------------------------------------------------
# D. IA de texto: respaldos y desactivación (analizar() con servidores sustituidos)
# ---------------------------------------------------------------------------------------------------------------------------------------
@contextlib.contextmanager
def ia_simulada(comportamiento):
    """comportamiento(modelo) -> (ok, texto). Escribe la salida cuando ok."""
    llamados = []

    class S:
        def __init__(self, m):
            self.modelo = m

        def vivo(self):
            return True

        def pedir(self, entrada, salida, linea, **k):
            llamados.append(self.modelo)
            ok, t = comportamiento(self.modelo)
            if ok:
                with open(salida, 'w', encoding='utf-8') as f:
                    json.dump({'correcciones': {'0': 'Hola'}, 'pesos': {}, 'emojis': {}}, f)
            return ok, t

        def cerrar(self):
            pass

    with parches((ia_texto, '_Servidor', S), (ia_texto, '_leer_cache', lambda c: None), (ia_texto, '_guardar_cache', lambda c, d: None),
                 (motor_voz, 'info_instalado', lambda: {'modelo_texto': 'gemma4'}), (motor_voz, 'modelo_texto', lambda *a, **k: 'gemma4'),
                 (ia_texto, '_respaldos', lambda m: ['1.7B'] if m != '1.7B' else []), (ia_texto, '_reg', lambda: None)):
        ia_texto._SRV['s'] = None
        ia_texto._PREFERIDO['m'] = None
        ia_texto._FALLOS.update(n=0, avisado=False)
        try:
            yield llamados
        finally:
            ia_texto._SRV['s'] = None
            ia_texto._PREFERIDO['m'] = None
            ia_texto._FALLOS.update(n=0, avisado=False)


PAL = [{'word': 'hola'}]


@caso('IA de texto')
def ia_grande_falla_ligera_salva():
    with ia_simulada(lambda m: (m == '1.7B', 'sin responder 100 s')) as ll:
        r = ia_texto.analizar(PAL)
        esperar(r['correcciones'] == {0: 'Hola'} and ll == ['gemma4', '1.7B'], f'{r} {ll}')
        ia_texto.analizar(PAL)
        esperar(ll[-1] == '1.7B' and len(ll) == 3, f'la segunda vez debe ir directa a la ligera: {ll}')


@caso('IA de texto')
def ia_dos_fallos_desactiva_sin_perder_tiempo():
    with ia_simulada(lambda m: (False, 'sin responder 100 s')) as ll:
        for _ in range(2):
            try:
                ia_texto.analizar(PAL)
            except RuntimeError:
                pass
        n = len(ll)
        esperar(not ia_texto.activa(), 'tras 2 fallos activa() debe ser False (el editor usa el diccionario)')
        try:
            ia_texto.analizar(PAL)
            esperar(False, 'debía lanzar')
        except RuntimeError as e:
            esperar('desactivada' in str(e) and len(ll) == n, f'{e} {ll}')


@caso('IA de texto')
def ia_vuelve_tras_un_fallo():
    estado = {'n': 0}

    def comp(m):
        estado['n'] += 1
        return estado['n'] > 2, 'falló'
    with ia_simulada(comp):
        try:
            ia_texto.analizar(PAL)
        except RuntimeError:
            pass
        ia_texto.analizar(PAL)
        esperar(ia_texto._FALLOS['n'] == 0 and ia_texto.activa(), str(ia_texto._FALLOS))


# ---------------------------------------------------------------------------------------------------------------------------------------
# E. Qué IA de texto y qué torch le tocan a cada equipo
# ---------------------------------------------------------------------------------------------------------------------------------------
TODOS = ['gemma4', 'qwen3.5', '1.7B']


def elegir(total, libre, hay=TODOS):
    with parches((motor_voz, 'modelos_texto_descargados', lambda: list(hay)), (motor_voz, 'vram_total_gb', lambda: total),
                 (motor_voz, 'vram_para_ia_gb', lambda: libre)):
        return motor_voz.modelo_texto({})


@caso('Equipo y GPU')
def gpu_24gb_libre_usa_la_mejor():
    esperar(elegir(24, 22) == 'gemma4')


@caso('Equipo y GPU')
def gpu_16gb_con_resolve_baja_a_la_ligera():
    esperar(elegir(16, 7) == '1.7B', elegir(16, 7))


@caso('Equipo y GPU')
def gpu_8gb_rtx5050_del_cliente():
    m = elegir(8, 2.5, ['1.7B'])
    esperar(m == '1.7B', m)
    usa = dict((c[0], c[4]) for c in motor_voz.MODELOS_TEXTO)[m]
    # MEDIDO 2026-11-05 (i5-12400 + RTX 5070 Ti, 168 palabras, 1.7B): GPU libre 23 s · GPU con 2,5 GB libres 28 s (Windows desaloja lo que no
    # se usa) · CPU 297 s. Pasarla a la CPU cuando «no cabe» sería 10 veces peor: se queda en la GPU y los LATIDOS evitan que la corten.
    esperar(usa > 2.5, 'la 1.7B debería ocupar más de 2,5 GB (si no, revisar MODELOS_TEXTO)')


@caso('Equipo y GPU')
def sin_nvidia_no_rompe():
    esperar(elegir(0, 0, ['1.7B']) == '1.7B')


@caso('Equipo y GPU')
def torch_por_driver():
    casos = {None: 'cpu', 560: 'cu128', 585: 'cu130', 595: 'cu132', 610: 'cu132', 0: 'cu128'}
    for driver, esperado in casos.items():
        with parches((motor_voz, 'hay_gpu_nvidia', lambda: driver is not None), (motor_voz, '_driver_nvidia', lambda: driver or 0)):
            v, ver = motor_voz.torch_para_este_equipo()
        esperar(v == esperado and ver == motor_voz.TORCH[v], f'driver {driver}: {v} {ver} (esperaba {esperado})')


@caso('Equipo y GPU')
def torch_soporta_rtx_50():
    """Las RTX 50 (Blackwell, sm_120) necesitan torch con CUDA 12.8 o más: ninguna variante GPU puede ser más vieja."""
    for v in ('cu128', 'cu130', 'cu132'):
        esperar(int(v[2:]) >= 128 and v in motor_voz.TORCH, v)


# ---------------------------------------------------------------------------------------------------------------------------------------
# F. El Registro explica bien cada error (la tarjeta que ve el cliente)
# ---------------------------------------------------------------------------------------------------------------------------------------
TARJETAS = [
    ('error', 'GO · timeline', 'No hay DaVinci Resolve en este equipo. Suelta un video en CineCaptions y pulsa GO: te lo devuelvo con los subtítulos puestos.',
     'Falta el video'),
    ('error', 'GO · timeline', 'Tienes encendido «Video MP4 en lugar de Resolve» (Ajustes > General). Suelta un video en CineCaptions y pulsa GO, o apágalo.',
     'modo «Video MP4»'),
    ('aviso', 'IA de texto', 'La IA de texto (1.7B) falló: la IA de texto se quedó sin responder 100 s', 'IA de texto'),
    ('aviso', 'IA de texto', 'La IA de texto falló 2 veces seguidas: sigo con el motor de reglas (sin corrección por IA) hasta reiniciar el programa.', 'IA de texto'),
    ('aviso', 'ortografía', 'La IA de texto no pudo corregir la ortografía; la corrijo con el diccionario. (RuntimeError: x)', 'IA de texto'),
]


@caso('Registro')
def registro_cada_error_su_tarjeta():
    malas = []
    for nivel, origen, msg, titulo in TARJETAS:
        a = registro_ayuda.explicar(types.SimpleNamespace(nivel=nivel, mensaje=msg, origen=origen, detalle=''))
        if titulo.lower() not in str(a[0]).lower():
            malas.append(f'«{msg[:60]}…» → «{a[0]}» (esperaba «{titulo}»)')
    esperar(not malas, '\n      '.join(malas))


@caso('Registro')
def registro_pasos_sin_menus_que_no_existen():
    """Los pasos de las tarjetas no pueden mandar a menús quitados de Ajustes (v5.69 quitó «Voz e IA»)."""
    viejos = re.compile(r'Ajustes\s*>\s*Voz e IA|Ajustes\s*>\s*IA\b')
    malas = [t for _p, t, _q, pasos, _i in registro_ayuda._COMPILADAS for p in pasos if viejos.search(p)]
    esperar(not malas, str(malas))


# ---------------------------------------------------------------------------------------------------------------------------------------
# G. Telemetría de errores (v5.71): lo que llega a pagos/errores.php, con un servidor falso en 127.0.0.1
# ---------------------------------------------------------------------------------------------------------------------------------------
import http.server  # noqa: E402
import urllib.parse  # noqa: E402

import licencia  # noqa: E402
import registro  # noqa: E402
import telemetria_errores as tel  # noqa: E402


class _ServidorErrores:
    """Como errores.php: formulario normal o (v5.72, con capturas) multipart. `archivos` = [{nombre: bytes}] por petición.
    `codigo_con_archivos`: el código que da si la petición trae capturas (413 = «demasiado grande»)."""
    def __init__(self):
        self.peticiones = []
        self.archivos = []
        self.codigo = 200
        self.codigo_con_archivos = None
        dueno = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                crudo = self.rfile.read(int(self.headers.get('Content-Length') or 0))
                tipo = self.headers.get('Content-Type') or ''
                campos, archivos = {}, {}
                if tipo.startswith('multipart/form-data'):
                    import email.parser
                    import email.policy
                    msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
                        b'Content-Type: ' + tipo.encode('ascii') + b'\r\n\r\n' + crudo)
                    for parte in msg.iter_parts():
                        nombre = parte.get_param('name', header='content-disposition')
                        if parte.get_filename():
                            archivos[nombre] = parte.get_payload(decode=True)
                        else:
                            campos[nombre] = parte.get_payload(decode=True).decode('utf-8')
                else:
                    campos = {k: v[0] for k, v in urllib.parse.parse_qs(crudo.decode('utf-8')).items()}
                dueno.peticiones.append(campos)
                dueno.archivos.append(archivos)
                codigo = dueno.codigo_con_archivos if archivos and dueno.codigo_con_archivos else dueno.codigo
                self.send_response(codigo)
                if dueno.codigo in (429, 503):
                    self.send_header('Retry-After', '3600')
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            def log_message(self, *a):
                pass
        self.srv = http.server.HTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.srv.server_port}/pagos/errores.php'

    def errores(self):
        return [e for p in self.peticiones for e in json.loads(p['errores'])]

    def cerrar(self):
        self.srv.shutdown()


@contextlib.contextmanager
def telemetria(con_licencia=True, codigo=200):
    srv = _ServidorErrores()
    srv.codigo = codigo
    carpeta = tempfile.mkdtemp(prefix='cc_tel_')
    lic = {'clave': 'CC-AAAA-BBBB-CCCC-DDDD', 'plataforma': 'cinecaptions'} if con_licencia else None
    tel._PENDIENTES.clear(), tel._COLA.clear(), tel._CONTADAS.clear(), tel._CAPTURADAS.clear(), tel._CAPTURAS_MEM.clear()
    tel._ESTADO.update(enviados=0, pausa_hasta=0.0, ultimo_envio={}, capturas=0)
    # (v5.72: las capturas, también en la carpeta temporal: nunca en ~/DaVinciSubtitles/errores_capturas del usuario)
    with parches((tel, 'URL', srv.url), (tel, 'ARCHIVO', pathlib.Path(carpeta) / 'errores_por_enviar.json'), (tel, 'ESPERA_LOTE_S', 0),
                 (tel, 'CAPTURAS', pathlib.Path(carpeta) / 'errores_capturas'),
                 # v5.72: la ficha del equipo NUNCA al servidor real desde las pruebas (puerto cerrado) ni su huella en ~/DaVinciSubtitles
                 (tel, 'URL_FICHA', 'http://127.0.0.1:9/nada'), (tel, 'FICHA_ENVIADA', pathlib.Path(carpeta) / 'ficha_enviada.json'),
                 (licencia, 'local', lambda: lic), (licencia, 'id_equipo', lambda: '3F2A-91BC-04DE-77A1')):
        try:
            yield srv
        finally:
            srv.cerrar()
            tel._PENDIENTES.clear(), tel._COLA.clear(), tel._CONTADAS.clear(), tel._CAPTURADAS.clear(), tel._CAPTURAS_MEM.clear()
            __import__('shutil').rmtree(carpeta, ignore_errors=True)


def _error(msg='GO no pudo terminar: KeyError: 7', origen='GO · colocar', detalle=''):
    casa = str(pathlib.Path.home())
    return registro.Entrada('error', msg, origen, detalle or f'Traceback:\n  File "{casa}\\Videos\\mi video.mp4", line 3\nKeyError: 7')


def _ciclo(*entradas):
    for e in entradas:
        tel._al_anotar(e)
    tel._procesar_cola()
    tel._enviar()


@caso('Telemetría de errores')
def tel_manda_el_error_sin_la_carpeta_del_usuario():
    with telemetria() as srv:
        _ciclo(_error())
        errs = srv.errores()
        esperar(len(srv.peticiones) == 1 and len(errs) == 1, f'{len(srv.peticiones)} peticiones')
        p, e = srv.peticiones[0], errs[0]
        casa = str(pathlib.Path.home())
        todo = json.dumps(p, ensure_ascii=False)
        esperar(p['clave'] == 'CC-AAAA-BBBB-CCCC-DDDD' and p['equipo'] == '3F2A-91BC-04DE-77A1' and p.get('version') and p.get('so'), str(p)[:300])
        esperar(casa.lower() not in todo.lower() and casa.replace('\\', '\\\\').lower() not in todo.lower(), 'el informe lleva la carpeta del usuario')
        esperar(re.fullmatch(r'[0-9a-f]{40}', e['firma']) and e['veces'] == 1 and e['titulo'] and 'KeyError' in e['detalle'], str(e)[:300])
        esperar(not tel._PENDIENTES and not tel.ARCHIVO.exists(), 'enviado: no debe quedar pendiente')


@caso('Telemetría de errores')
def tel_sin_rutas_ni_nombres_de_archivos_ni_lo_de_antes():
    """Revisión 5.71: «lo que pasó justo antes» decía de qué trata el video y el nombre del proyecto; las rutas de otros discos y los
    nombres de los videos salían tal cual."""
    logs = pathlib.Path(tempfile.mkdtemp(prefix='cc_log_'))           # (registro.info escribe en los logs: nunca en los del usuario)
    with telemetria() as srv, parches((registro, 'ARCHIVO', logs / 'cinecaptions.log'), (registro, 'ARCHIVO_ERRORES', logs / 'errores.log')):
        registro.info('La IA entendió el video: boda · discurso del padrino · tono emotivo', 'IA')
        registro.info('Timeline «Boda Maria Lopez» armado con tu video en el proyecto «Boda Maria Lopez»', 'GO')
        e = registro.Entrada('error', "FileNotFoundError: [Errno 2] No such file: 'D:\\Clientes\\Maria Lopez\\boda final.mp4'", 'GO · colocar',
                             'Traceback (most recent call last):\n  File "C:\\Program Files\\CineCaptions\\_internal\\colocacion.py", line 9\n'
                             '  File "E:\\Proyectos\\Juan\\entrevista.mov"\nFileNotFoundError: boda_final.MP4')
        _ciclo(e)
        todo = json.dumps(srv.peticiones, ensure_ascii=False)
        for prohibido in ('Maria', 'Lopez', 'boda', 'padrino', 'Clientes', 'Juan', 'entrevista', 'Proyectos'):
            esperar(prohibido.lower() not in todo.lower(), f'el informe lleva «{prohibido}»')
        esperar('colocacion.py' in todo and 'Program Files' in todo, 'las rutas del PROGRAMA deben quedarse (sirven para el fallo)')
        esperar('archivo.mp4' in todo.lower(), 'debía decir la extensión del archivo anonimizado')
    __import__('shutil').rmtree(logs, ignore_errors=True)


@caso('Telemetría de errores')
def tel_errores_de_arranque_se_mandan():
    """Revisión 5.71: «la sesión anterior se cortó» se anota antes de iniciar() y nunca salía."""
    logs = pathlib.Path(tempfile.mkdtemp(prefix='cc_log_'))
    with telemetria() as srv, parches((tel, 'activo', lambda: True), (tel, '_ESTADO', dict(tel._ESTADO, iniciado=False)),
                                      (registro, 'ARCHIVO', logs / 'cinecaptions.log'), (registro, 'ARCHIVO_ERRORES', logs / 'errores.log')):
        registro.registro().limpiar()
        registro.error('La sesión anterior se cortó en mitad de «GO» (prueba de arranque)', 'arranque')
        esperar(tel.iniciar(), 'iniciar() debía arrancar')
        esperar(tel.esperar_envios(20) and any('se cortó' in x['mensaje'] for x in srv.errores()), f'{srv.errores()}')
        tel.detener()                                  # (el hilo no debe seguir vivo en los casos siguientes)
    __import__('shutil').rmtree(logs, ignore_errors=True)


@caso('Telemetría de errores')
def tel_al_cerrar_lo_de_la_cola_queda_en_disco():
    with telemetria():
        tel._al_anotar(_error('Fallo justo antes de cerrar'))
        tel._al_salir()                                 # lo que corre atexit
        esperar(tel.ARCHIVO.exists() and len(tel._PENDIENTES) == 1, 'al cerrar, la cola debía quedar en disco')


@caso('Telemetría de errores')
def tel_servidor_guarda_solo_una_parte():
    with telemetria() as srv:
        viejo = tel._post
        tel._post = lambda campos, archivos=None: (srv.peticiones.append(campos), (200, None, {'ok': True, 'guardados': 1}))[1]
        try:
            _ciclo(_error('uno'), _error('dos', 'otro'), _error('tres', 'otro más'))
        finally:
            tel._post = viejo
        esperar(len(tel._PENDIENTES) == 2 and tel._ESTADO['pausa_hasta'] - time.time() > 3000,
                f'quedaban {len(tel._PENDIENTES)} (debían 2) y en pausa una hora')


@caso('Telemetría de errores')
def tel_repeticiones_sin_contar_doble():
    with telemetria() as srv:
        e = _error()
        e.veces = 3
        _ciclo(e)                                   # primera vez: 3
        e.veces = 5
        tel._al_anotar(e)
        tel._procesar_cola()                        # +2 (no 5): queda pendiente por REPETIR_S
        esperar(list(tel._PENDIENTES.values())[0]['veces'] == 2, str(tel._PENDIENTES))
        tel._enviar()
        esperar(len(srv.peticiones) == 1, 'el mismo error no se repite antes de REPETIR_S')
        for f in tel._ESTADO['ultimo_envio']:
            tel._ESTADO['ultimo_envio'][f] -= tel.REPETIR_S + 1
        tel._ESTADO['pausa_hasta'] = 0
        tel._enviar()
        esperar([x['veces'] for x in srv.errores()] == [3, 2], str([x['veces'] for x in srv.errores()]))


@caso('Telemetría de errores')
def tel_mismo_fallo_con_otros_numeros_una_firma():
    esperar(tel.firma('GO · colocar', 'Falló el clip 12 a las 10:41') == tel.firma('GO · colocar', 'Falló el clip 7 a las 11:02'))
    esperar(tel.firma('GO · colocar', 'KeyError: x') != tel.firma('GO · voz', 'KeyError: x'))


@caso('Telemetría de errores')
def tel_avisos_no_se_mandan():
    with telemetria() as srv:
        _ciclo(registro.Entrada('aviso', 'La IA de texto falló', 'IA de texto'), registro.Entrada('info', 'hola', 'x'))
        esperar(not srv.peticiones and not tel._PENDIENTES)


@caso('Telemetría de errores')
def tel_sin_red_queda_en_disco_y_sale_despues():
    with telemetria() as srv:
        url_buena = tel.URL
        tel.URL = 'http://127.0.0.1:9/nada'           # puerto cerrado = sin red
        _ciclo(_error())
        esperar(tel.ARCHIVO.exists() and len(tel._PENDIENTES) == 1 and tel._ESTADO['pausa_hasta'] > time.time(), 'debía quedar en disco y en pausa')
        tel._PENDIENTES.clear()                       # «se reinicia el programa»: lo pendiente se lee del disco
        tel._cargar()
        tel.URL = url_buena
        tel._ESTADO['pausa_hasta'] = 0
        tel._enviar()
        esperar(len(srv.errores()) == 1 and not tel.ARCHIVO.exists(), f'{len(srv.errores())} enviados')


@caso('Telemetría de errores')
def tel_sin_licencia_espera():
    with telemetria(con_licencia=False) as srv:
        _ciclo(_error())
        esperar(not srv.peticiones and len(tel._PENDIENTES) == 1, 'sin licencia no se manda, queda pendiente')


@caso('Telemetría de errores')
def tel_equipo_no_activado_se_descarta():
    with telemetria(codigo=404) as srv:
        _ciclo(_error())
        esperar(len(srv.peticiones) == 1 and not tel._PENDIENTES, 'un 404 no se reintenta')


@caso('Telemetría de errores')
def tel_servidor_saturado_espera():
    with telemetria(codigo=429) as srv:
        _ciclo(_error())
        esperar(len(tel._PENDIENTES) == 1 and tel._ESTADO['pausa_hasta'] - time.time() > 3000, 'un 429 espera su Retry-After')
        tel._enviar()
        esperar(len(srv.peticiones) == 1, 'durante la pausa no se vuelve a pedir')


@caso('Telemetría de errores')
def tel_tope_por_sesion():
    with telemetria() as srv:
        tel._ESTADO['enviados'] = tel.TOPE_SESION
        _ciclo(_error())
        esperar(not srv.peticiones, 'pasado el tope de la sesión no se manda')


@caso('Telemetría de errores')
def tel_anotar_no_bloquea_la_interfaz():
    with telemetria():
        t0 = time.perf_counter()
        for i in range(200):
            tel._al_anotar(_error(f'fallo {i}'))
        ms = (time.perf_counter() - t0) * 1000 / 200
        esperar(ms < 1.0, f'{ms:.2f} ms por error en el hilo que anota')


@caso('Telemetría de errores')
def tel_desde_el_codigo_no_manda():
    viejo = {k: os.environ.pop(k, None) for k in ('CINECAPTIONS_TELEMETRIA', 'CINECAPTIONS_SIN_TELEMETRIA')}
    tenia = hasattr(sys, 'frozen')
    try:
        esperar(not tel.activo(), 'desde el código fuente no debe mandar')
        sys.frozen = True
        esperar(tel.activo(), 'en el .exe sí')
        os.environ['CINECAPTIONS_SIN_TELEMETRIA'] = '1'
        esperar(not tel.activo(), 'CINECAPTIONS_SIN_TELEMETRIA=1 lo apaga')
    finally:
        os.environ.pop('CINECAPTIONS_SIN_TELEMETRIA', None)
        for k, v in viejo.items():
            if v is not None:
                os.environ[k] = v
        if not tenia:
            del sys.frozen


@caso('Telemetría de errores')
def tel_hilo_de_punta_a_punta():
    logs = pathlib.Path(tempfile.mkdtemp(prefix='cc_log_'))           # (registro.error escribe en los logs: nunca en los del usuario)
    with telemetria() as srv, parches((tel, 'activo', lambda: True), (tel, '_ESTADO', dict(tel._ESTADO, iniciado=False)),
                                      (registro, 'ARCHIVO', logs / 'cinecaptions.log'), (registro, 'ARCHIVO_ERRORES', logs / 'errores.log')):
        registro.registro().limpiar()                 # (iniciar() manda lo que ya haya en el Registro: solo lo de este caso)
        esperar(tel.iniciar(), 'iniciar() debía arrancar')
        registro.error('Algo salió mal en la prueba de punta a punta', 'prueba')
        esperar(tel.esperar_envios(20) and len(srv.errores()) == 1, f'{len(srv.errores())} errores recibidos')
        tel.detener()                                  # (el hilo no debe seguir vivo en los casos siguientes)
    __import__('shutil').rmtree(logs, ignore_errors=True)


def _imagen_prueba(ancho=3440, alto=1440):
    from PySide6.QtGui import QColor, QImage, QPainter
    img = QImage(ancho, alto, QImage.Format.Format_RGB32)
    img.fill(QColor('#13121a'))
    p = QPainter(img)
    p.fillRect(100, 100, ancho // 3, alto // 3, QColor('#e0246e'))
    p.end()
    return img


def _con_captura(e, tomas=('pantalla',)):
    """Lo que hace el capturador del hilo de la interfaz (sin pantalla de verdad): las imágenes en memoria para ese error. v5.73: `tomas`
    = las que salieron ('pantalla' y/o 'ventana', en ese orden, como _tomar_capturas)."""
    tel._al_anotar(e)
    tel._procesar_cola()
    medidas = {'pantalla': (3440, 1440), 'ventana': (2293, 960)}
    tel._CAPTURAS_MEM[tel.firma(e.origen, e.mensaje)] = [
        (c, _imagen_prueba(*medidas[c]), {'tipo': c, 'ancho': medidas[c][0], 'alto': medidas[c][1]}) for c in tomas]
    tel._guardar_capturas()


@caso('Telemetría de errores')
def tel_captura_va_con_su_error():
    """v5.72: la captura (JPEG reducido a 1920) viaja en multipart como «captura_<firma>», con equipo_datos, y se borra al llegar."""
    with telemetria() as srv:
        e = _error()
        _con_captura(e)
        f = tel.firma(e.origen, e.mensaje)
        esperar(tel._archivo_captura(f).exists() and tel._PENDIENTES[f].get('captura'), 'la captura debía quedar en disco con su error')
        tel._enviar()
        esperar(len(srv.peticiones) == 1, f'{len(srv.peticiones)} peticiones')
        arch = srv.archivos[0].get('captura_' + f)
        esperar(arch and arch[:3] == b'\xff\xd8\xff' and len(arch) <= tel.CAPTURA_MAX_BYTES, 'debía llegar un JPEG')
        from PySide6.QtGui import QImage
        img = QImage.fromData(arch)
        esperar(img.width() == tel.CAPTURA_ANCHO, f'ancho {img.width()} (debía reducirse a {tel.CAPTURA_ANCHO})')
        esperar(srv.errores()[0].get('captura') == 'pantalla', str(srv.errores()[0])[:200])
        datos = srv.peticiones[0].get('equipo_datos') or ''
        esperar('RAM' in datos and 'CPU' in datos and len(datos) <= 300, f'equipo_datos: {datos!r}')
        esperar(not tel._archivo_captura(f).exists() and not tel._PENDIENTES, 'enviada: la captura debía borrarse')


@caso('Telemetría de errores')
def tel_dos_capturas_pantalla_y_programa():
    """v5.73 (pedido: «2 capturas, una del programa y una de la pantalla completa»): en Windows van las dos, «captura_<firma>» (pantalla) y
    «ventana_<firma>» (la ventana del programa), con ventana: true en su error; al llegar se borran las dos."""
    with telemetria() as srv:
        e = _error()
        _con_captura(e, ('pantalla', 'ventana'))
        f = tel.firma(e.origen, e.mensaje)
        esperar(tel._archivo_captura(f).exists() and tel._archivo_captura(f, 'ventana').exists(), 'las dos debían quedar en disco')
        tel._enviar()
        esperar(len(srv.peticiones) == 1, f'{len(srv.peticiones)} peticiones')
        a = srv.archivos[0]
        esperar(a.get('captura_' + f, b'')[:3] == b'\xff\xd8\xff' and a.get('ventana_' + f, b'')[:3] == b'\xff\xd8\xff', f'archivos: {list(a)}')
        err = srv.errores()[0]
        esperar(err.get('captura') == 'pantalla' and err.get('ventana') is True, str(err)[:200])
        esperar(not list(tel.CAPTURAS.glob('*.jpg')) and not tel._PENDIENTES, 'enviadas: las dos debían borrarse')


@caso('Telemetría de errores')
def tel_solo_la_del_programa_va_como_captura():
    """v5.73: si la de pantalla falla (o en Mac), la del programa va como «captura_<firma>» con captura='ventana': un errores.php anterior
    la guarda igual."""
    with telemetria() as srv:
        e = _error()
        _con_captura(e, ('ventana',))
        f = tel.firma(e.origen, e.mensaje)
        tel._enviar()
        a = srv.archivos[0]
        esperar(('captura_' + f) in a and ('ventana_' + f) not in a, f'archivos: {list(a)}')
        err = srv.errores()[0]
        esperar(err.get('captura') == 'ventana' and not err.get('ventana'), str(err)[:200])


@caso('Telemetría de errores')
def tel_capturas_sueltas_se_limpian():
    """v5.73: al abrir, «<firma>.ventana.jpg» de un error pendiente se conserva; las que no tienen su error se borran."""
    with telemetria():
        e = _error()
        _con_captura(e, ('pantalla', 'ventana'))
        f = tel.firma(e.origen, e.mensaje)
        tel._guardar()
        huerfana = tel.CAPTURAS / (('0' * 40) + '.ventana.jpg')
        huerfana.write_bytes(b'\xff\xd8\xff')
        tel._PENDIENTES.clear()
        tel._cargar()
        esperar(tel._archivo_captura(f).exists() and tel._archivo_captura(f, 'ventana').exists(), 'las del error pendiente debían quedarse')
        esperar(tel._PENDIENTES.get(f, {}).get('ventana') and not huerfana.exists(), 'la huérfana debía borrarse')


@caso('Telemetría de errores')
def tel_captura_grande_reintenta_sin_ella():
    """v5.72: si el servidor dice 413 (o 400: PHP tiró el formulario por post_max_size), el error sale sin captura (v5.73: sin las dos)."""
    with telemetria() as srv:
        srv.codigo_con_archivos = 413
        e = _error()
        _con_captura(e, ('pantalla', 'ventana'))
        tel._enviar()
        esperar(len(srv.peticiones) == 1 and len(tel._PENDIENTES) == 1, 'con 413 el error debía quedarse')
        esperar(not any(d.get('captura') or d.get('ventana') for d in tel._PENDIENTES.values()) and not list(tel.CAPTURAS.glob('*.jpg')),
                'sin sus capturas')
        tel._ESTADO['pausa_hasta'] = 0
        tel._enviar()
        esperar(len(srv.peticiones) == 2 and not srv.archivos[1] and not tel._PENDIENTES, 'la segunda vez, sin captura y guardado')


@caso('Telemetría de errores')
def tel_capturas_una_por_error_y_tope():
    """v5.72: una captura por error DISTINTO y CAPTURAS_SESION por sesión; nada de capturas sin capturador (sin Qt)."""
    pedidas = []

    class Falso:
        class pedir:
            emit = staticmethod(pedidas.append)
    with telemetria(), parches((tel, '_ESTADO', dict(tel._ESTADO, capturador=Falso(), capturas=0))):
        for i in range(3):
            tel._al_anotar(_error('el mismo fallo'))
        esperar(len(pedidas) == 1, f'el mismo error pidió {len(pedidas)} capturas')
        for i in range(20):
            tel._al_anotar(_error(f'fallo distinto', origen=f'origen {chr(65 + i)}'))
        esperar(len(pedidas) == tel.CAPTURAS_SESION, f'{len(pedidas)} capturas (tope {tel.CAPTURAS_SESION})')
    with telemetria(), parches((tel, '_ESTADO', dict(tel._ESTADO, capturador=Falso(), capturas=0))):
        pedidas.clear()
        tel._al_anotar(_error('de la sesión anterior'), capturar=False)
        esperar(not pedidas, 'los errores de arranque no llevan captura')


@caso('Telemetría de errores')
def tel_capturas_sueltas_se_borran_al_abrir():
    with telemetria():
        tel.CAPTURAS.mkdir(parents=True, exist_ok=True)
        suelta = tel.CAPTURAS / ('a' * 40 + '.jpg')
        suelta.write_bytes(b'x')
        tel._cargar()
        esperar(not suelta.exists(), 'una captura sin su error pendiente debía borrarse')


# ---------------------------------------------------------------------------------------------------------------------------------------
# G2. Actualización obligatoria (v5.72): force_update + version_minima del version.json firmado
# ---------------------------------------------------------------------------------------------------------------------------------------
import actualizaciones  # noqa: E402


def _manifiesto(version='5.72.0', **raiz):
    archivos = {actualizaciones.clave_plataforma(): {'url': 'https://x/Instalar.exe', 'sha256': '0' * 64, 'tam': 1}}
    return dict({'estable': {'version': version, 'notas': 'x', 'fecha': '2026-11-05', 'archivos': archivos}}, **raiz)


@caso('Actualización obligatoria')
def obligatoria_solo_por_debajo_de_la_minima():
    with parches((actualizaciones, 'firma_valida', lambda d: True)):
        r = actualizaciones._interpretar(_manifiesto(force_update=True, version_minima='5.72'), '5.71')
        esperar(r['estado'] == 'nueva' and r.get('obligatoria') and r.get('minima') == '5.72', str(r))
        r = actualizaciones._interpretar(_manifiesto('5.73.0', force_update=True, version_minima='5.72'), '5.72')
        esperar(r['estado'] == 'nueva' and not r.get('obligatoria'), f'5.72 >= mínima: aviso normal, no obligatoria ({r})')
        r = actualizaciones._interpretar(_manifiesto(force_update=False, version_minima='5.72'), '5.71')
        esperar(not r.get('obligatoria'), 'force_update false: no obligatoria')
        r = actualizaciones._interpretar(_manifiesto(version_minima='5.72'), '5.71')
        esperar(not r.get('obligatoria'), 'sin force_update: no obligatoria')
        r = actualizaciones._interpretar(_manifiesto(force_update='true', version_minima='5.72'), '5.71')
        esperar(not r.get('obligatoria'), 'force_update tiene que ser true de verdad (no un texto)')


@caso('Actualización obligatoria')
def obligatoria_sin_instalador_no_bloquea():
    """Sin instalador para ESTA plataforma el programa no podría actualizarse: no se bloquea para nada."""
    with parches((actualizaciones, 'firma_valida', lambda d: True)):
        m = _manifiesto(force_update=True, version_minima='5.72')
        m['estable']['archivos'] = {}
        r = actualizaciones._interpretar(m, '5.71')
        esperar(r['estado'] == 'nueva' and not r.get('obligatoria'), str(r))


@caso('Actualización obligatoria')
def obligatoria_sin_firma_no_vale():
    """force_update va dentro de lo firmado: un manifiesto sin firma válida no obliga (ni ofrece) nada."""
    r = actualizaciones._interpretar(_manifiesto(force_update=True, version_minima='9.0'), '5.71')
    esperar(r['estado'] == 'error' and not r.get('obligatoria'), str(r))


# ---------------------------------------------------------------------------------------------------------------------------------------
# H. Reglas que ya rompieron el .exe (revisión del código)
# ---------------------------------------------------------------------------------------------------------------------------------------
def _fuentes():
    for carpeta in (CODIGO, os.path.join(RAIZ, '2_recursos', 'motor_qwen')):
        for nombre in os.listdir(carpeta):
            if nombre.endswith('.py'):
                yield os.path.join(carpeta, nombre)


@caso('Código')
def codigo_sin_threadpool_lazy():
    malas = [os.path.basename(f) for f in _fuentes()
             if re.search(r'^\s*from concurrent\.futures import .*ThreadPoolExecutor', open(f, encoding='utf-8', errors='replace').read(), re.M)]
    esperar(not malas, 'Python 3.15 en el .exe: usar «from concurrent.futures.thread import ThreadPoolExecutor» en ' + ', '.join(malas))


@caso('Código')
def codigo_sin_rutas_fijas_de_resolve_fuera_del_detector():
    """Una ruta «C:\\Program Files\\Blackmagic…\\DaVinci Resolve\\<archivo>» escrita a mano falla con Resolve en otro disco."""
    patron = re.compile(r"""['"]C:\\\\Program Files\\\\Blackmagic Design\\\\DaVinci Resolve\\\\[A-Za-z]""")
    malas = []
    for f in _fuentes():
        for i, linea in enumerate(open(f, encoding='utf-8', errors='replace'), 1):
            if patron.search(linea) and not linea.lstrip().startswith('#'):
                malas.append(f'{os.path.basename(f)}:{i}')
    if malas:
        AVISOS.append('rutas fijas a archivos de Resolve (revisar si deben usar _resolve_dir_windows): ' + ', '.join(malas[:12]))


# ---------------------------------------------------------------------------------------------------------------------------------------
AVISOS = []


def main():
    t0 = time.time()
    for grupo, f, lento in CASOS:
        nombre = f.__name__
        if FILTRO and FILTRO.lower() not in (grupo + ' ' + nombre).lower():
            continue
        if lento and RAPIDO:
            RESULTADOS.append((grupo, nombre, None, 'saltado (--rapido)'))
            continue
        try:
            f()
            RESULTADOS.append((grupo, nombre, True, ''))
        except Exception as e:
            det = str(e) if isinstance(e, AssertionError) else traceback.format_exc(limit=4)
            RESULTADOS.append((grupo, nombre, False, det))
    grupo_ant = None
    for grupo, nombre, ok, det in RESULTADOS:
        if grupo != grupo_ant:
            print(f'\n== {grupo}')
            grupo_ant = grupo
        marca = 'OK  ' if ok else ('--  ' if ok is None else 'FALLA')
        print(f'  {marca} {nombre}' + (f'\n      {det.strip()}' if det and not ok else ''))
    for a in AVISOS:
        print(f'\nAVISO: {a}')
    fallos = sum(1 for r in RESULTADOS if r[2] is False)
    print(f'\n{len(RESULTADOS)} casos · {fallos} fallos · {time.time() - t0:.0f} s')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
