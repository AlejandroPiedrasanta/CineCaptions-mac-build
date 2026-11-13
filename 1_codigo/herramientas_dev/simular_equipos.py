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
    m, _d = detectar_win([WIN_DEF + r'\Resolve.exe'], prefs={'go_salida_mp4': True})        # «Video sin editores (DaVinci y Premiere)»
    esperar(m == 'ajuste', f'motivo={m}')


@caso('Resolve Windows')
def win_usar_con_premiere():
    # v5.78: «Usar con Premiere Pro»; si por algo quedaran los dos guardados, gana Premiere
    m, _d = detectar_win([WIN_DEF + r'\Resolve.exe'], prefs={'go_premiere': True, 'go_salida_mp4': True})
    esperar(m == 'premiere', f'motivo={m}')


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
    ('error', 'GO · timeline', 'Tienes elegido «Video sin editores (DaVinci y Premiere)» (Ajustes > General). Suelta un video en CineCaptions y pulsa GO, o elige «Usar con DaVinci Resolve» para trabajar con el timeline de Resolve.',
     'modo «Video sin editores»'),
    ('error', 'GO · timeline', 'Tienes elegido «Usar con Premiere Pro» (Ajustes > General). Suelta un video en CineCaptions y pulsa GO: lo coloco en Premiere Pro.',
     'GO trabaja con Premiere Pro'),
    ('error', 'GO · resolve', 'No pude colocar en Premiere Pro: Premiere Pro no contestó. Ábrelo con un proyecto y, si no se conecta, abre una vez Ventana > Extensiones > CineCaptions. Luego pulsa GO otra vez.',
     'Premiere Pro no contestó'),
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


# ---------------------------------------------------------------------------------------------------------------------------------------
# I. Dos informes de clientes (2026-11-10). Windows, RTX 4070 Laptop de 8 GB: «Falla al iniciar: Motor de IA (Qwen3) — faltan modelos»,
#    explicado como «le faltan librerías», con la voz bien y solo sin la IA de texto. Mac 5.78: «La sesión anterior NO llegó a terminar de
#    abrir… Hay un volcado del fallo», explicado como «El programa arrancó», con «Idioma del sistema None».
# ---------------------------------------------------------------------------------------------------------------------------------------
import atexit  # noqa: E402

import salud  # noqa: E402
import vigilancia  # noqa: E402


@contextlib.contextmanager
def motor_qwen(python=True, librerias=(), torch='2.14.1+cu130', asr=True, alineador=True, texto=(), vram=8.0):
    """El motor de voz e IA en el estado pedido, solo en memoria (nada del AppData real); el resto del chequeo, sin motores ni GPU."""
    import cuda_libs
    import motor_compat
    presentes = set()
    if asr:
        presentes.add(motor_voz.REPOS_ASR['1.7B'][0])
    if alineador:
        presentes.add(motor_voz.REPO_ALINEADOR[0])
    presentes |= {repo for clave, repo, *_r in motor_voz.MODELOS_TEXTO if clave in texto}
    with parches((motor_voz, 'python_motor', lambda: types.SimpleNamespace(exists=lambda: True)),
                 (motor_voz, '_python_al_dia', lambda: python), (motor_voz, '_faltan_requisitos', lambda: list(librerias)),
                 (motor_voz, '_dist_instalada', lambda n, v=None: torch if n == 'torch' else '1'),
                 (motor_voz, 'modelo_descargado', lambda repo, minimo=0: repo in presentes), (motor_voz, 'vram_total_gb', lambda: vram),
                 (motor_compat, 'EN_PROCESO', False), (motor_compat, 'instalado', lambda: False),
                 (cuda_libs, 'diagnostico', lambda: {'estado': 'no_aplica'}), (resolve_mcp, 'ruta_exe', lambda: None)):
        yield


def _fila_qwen(**estado):
    with motor_qwen(**estado):
        return next(f for f in salud.comprobar() if f['nombre'] == 'Motor de IA (Qwen3)')


def _anotado_al_arrancar(**estado):
    """Lo que el chequeo de arranque deja en el Registro sobre el motor: [(nivel, mensaje, título de «Qué significa»)]."""
    anotado = []
    with motor_qwen(**estado), parches((registro, 'anotar', lambda nivel, mensaje, origen='', detalle='': anotado.append((nivel, str(mensaje), origen))),
                                       (vigilancia, 'avisar_equipo', lambda: None), (vigilancia, 'poner_motores_al_dia', lambda: None)):
        vigilancia.revisar_salud_al_arrancar()
    return [(n, m, registro_ayuda.explicar(types.SimpleNamespace(nivel=n, mensaje=m, origen=o, detalle=''))[0])
            for n, m, o in anotado if 'Motor de IA' in m and n in ('aviso', 'error')]      # (la nota del resumen, «con aviso: …», es info)


@caso('Informes de clientes')
def cliente_rtx4070_8gb_sin_ia_de_texto_es_aviso_y_lo_dice():
    f = _fila_qwen(texto=())
    d = f['detalle']
    esperar(f['ok'] is not False, f'la voz funciona: no es una falla ({f})')
    esperar('voz' in d and 'IA de texto' in d and 'Qwen3-1.7B' in d and 'librer' not in d, d)
    notas = _anotado_al_arrancar(texto=())
    # (error para que se vea: la ventana Registro solo enseña Errores e Información; pero no es «Falla al iniciar»)
    esperar(notas and all(n[0] == 'error' and n[1].startswith('Al abrir:') for n in notas), notas)
    esperar(all('IA de texto' in n[2] and 'librer' not in n[2] for n in notas), [n[2] for n in notas])


@caso('Informes de clientes')
def motor_qwen_cada_falta_dice_que_falta():
    casos = [(dict(python=False), 'versión anterior', 'pieza'), (dict(librerias=['transformers==5.22.2']), 'librerías', 'librerías'),
             (dict(torch='2.9.0+cu126'), 'PyTorch', 'pieza'), (dict(asr=False), 'modelo de voz', 'pieza'), (dict(alineador=False), 'alineador', 'pieza')]
    malas = []
    for estado, en_detalle, en_titulo in casos:
        f = _fila_qwen(texto=('1.7B',), **estado)
        notas = _anotado_al_arrancar(texto=('1.7B',), **estado)
        nivel, titulo = (notas[0][0], notas[0][2]) if notas else ('', '')
        if f['ok'] is not False or en_detalle not in f['detalle'] or en_titulo not in titulo or nivel != 'error':
            malas.append(f"{estado}: {f['ok']} «{f['detalle']}» → {nivel} «{titulo}»")
    esperar(not malas, '\n      '.join(malas))


@caso('Informes de clientes')
def motor_qwen_completo_sin_avisos():
    f = _fila_qwen(texto=('1.7B',))
    esperar(f['ok'] is True and 'IA de texto 1.7B' in f['detalle'], f)
    esperar(not _anotado_al_arrancar(texto=('1.7B',)))


@caso('Informes de clientes')
def mac_sesion_anterior_bien_explicada():
    mensajes = [('error', 'La sesión anterior NO llegó a terminar de abrir: el programa se quedó atascado (o se cerró) durante el arranque.', 'abrir'),
                ('aviso', 'La sesión anterior de CineCaptions no se cerró bien (se colgó o se cayó).', 'cerró'),
                ('error', 'La sesión anterior se cortó en mitad de «go», en el paso «timeline» (hace 3 min).', 'mitad'),
                ('aviso', 'macOS guardó 2 informe(s) de caída reciente(s) de CineCaptions: CineCaptions-2026-11-09.ips', 'cerró')]
    malas = []
    for nivel, msg, clave in mensajes:
        a = registro_ayuda.explicar(types.SimpleNamespace(nivel=nivel, mensaje=msg, origen='sesión', detalle=''))
        if 'arrancó' in a[0] or 'timeline' in a[0] or clave not in a[0].lower():
            malas.append(f'«{msg[:55]}…» → «{a[0]}»')
    esperar(not malas, '\n      '.join(malas))


CABECERAS = '--- sesion 2026-11-08 10:00:00 ---\n--- sesion 2026-11-09 11:00:00 ---\n'
RUIDO_COM = ('--- sesion 2026-11-09 12:00:00 ---\nWindows fatal exception: code 0x8001010d\n\nThread 0x00005928 [resolve-mcp] (most recent call first):\n'
             '  File "resolve_mcp.py", line 86 in _leer\n')
CAIDA = '--- sesion 2026-11-09 12:00:00 ---\nFatal Python error: Segmentation fault\n\nThread 0x0100 (most recent call first):\n  File "ui.py", line 10 in pintar\n'
ATASCO = '--- sesion 2026-11-09 12:00:00 ---\nTimeout (0:00:20)!\nThread 0x01 (most recent call first):\n  File "CineCaptions.py", line 7000 in __init__\n'


def _cierre_anterior(estado, volcado):
    """_revisar_cierre_anterior con la marca y el fallo_nativo.log del caso, en una carpeta temporal (sin atexit: la marca real no se toca)."""
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_sesion_'))
    (carpeta / 'sesion_abierta.flag').write_text(f'{time.time()}|{estado}', encoding='utf-8')
    (carpeta / 'fallo_nativo.log').write_text(volcado, encoding='utf-8')
    anotado = []
    try:
        with parches((registro, 'CARPETA', carpeta), (registro, 'SESION', carpeta / 'sesion_abierta.flag'),
                     (registro, 'FALLOS_NATIVOS', carpeta / 'fallo_nativo.log'), (atexit, 'register', lambda *a, **k: None),
                     (registro, 'anotar', lambda nivel, mensaje, origen='', detalle='': anotado.append((nivel, str(mensaje)))),
                     (vigilancia, 'tarea_cortada_anterior', lambda: None)):
            registro._revisar_cierre_anterior()
    finally:
        __import__('shutil').rmtree(carpeta, ignore_errors=True)
    return anotado


@caso('Informes de clientes')
def volcado_solo_si_lo_hay():
    """«Hay un volcado del fallo en fallo_nativo.log» salía SIEMPRE (cada arranque escribe su cabecera) y en Windows el ruido de COM parecía
    una caída: solo si la sesión anterior dejó una caída o un atasco de verdad."""
    casos = [(CABECERAS, False), (CABECERAS + RUIDO_COM, False), (CABECERAS + CAIDA, True), (CABECERAS + ATASCO, True),
             (CABECERAS + CAIDA + '--- sesion 2026-11-10 09:00:00 ---\n', False)]
    malas = []
    for volcado, hay in casos:
        dice = any('volcado' in m for _n, m in _cierre_anterior('abriendo', volcado))
        if dice != hay:
            malas.append(f'{volcado.strip().splitlines()[-1][:50]!r}: dice volcado={dice}, esperaba {hay}')
    esperar(not malas, '\n      '.join(malas))


@caso('Informes de clientes')
def arranque_atascado_deja_las_pilas():
    """Si la ventana no termina de abrir, a los N s faulthandler escribe la pila de TODOS los hilos en fallo_nativo.log (aunque luego se
    cierre a la fuerza antes del aviso de los 45 s)."""
    import faulthandler
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_atasco_'))
    archivo = open(carpeta / 'fallo_nativo.log', 'a', encoding='utf-8')
    try:
        with parches((registro, '_ARCHIVO_FALLOS', archivo)):
            registro.vigilar_arranque_nativo(1)
            time.sleep(1.6)
            registro.fin_arranque_nativo()
        archivo.flush()
        texto = (carpeta / 'fallo_nativo.log').read_text(encoding='utf-8')
        esperar('Timeout' in texto and 'File' in texto, texto[:200])
    finally:
        faulthandler.cancel_dump_traceback_later()
        archivo.close()
        __import__('shutil').rmtree(carpeta, ignore_errors=True)


@caso('Informes de clientes')
def fallo_nativo_no_crece_sin_fin():
    """El del autor pesaba 1,2 MB (428 sesiones): al abrir, si pasa del tope, el viejo pasa a fallo_nativo.log.1."""
    import faulthandler
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_rota_'))
    ruta = carpeta / 'fallo_nativo.log'
    ruta.write_bytes(b'x' * (registro.MAXIMO_FALLOS_NATIVOS + 10))
    try:
        with parches((registro, 'FALLOS_NATIVOS', ruta), (registro, '_ARCHIVO_FALLOS', None)):
            registro._fallos_nativos()
            abierto = registro._ARCHIVO_FALLOS
        faulthandler.disable()
        abierto.close()
        esperar(ruta.stat().st_size < 200 and (carpeta / 'fallo_nativo.log.1').is_file(), f'{ruta.stat().st_size} bytes')
    finally:
        __import__('shutil').rmtree(carpeta, ignore_errors=True)


@caso('Informes de clientes')
def mac_idioma_del_sistema_nunca_none():
    import locale
    import plistlib
    with parches((locale, 'getlocale', lambda *a: (None, None))):
        v = registro.idioma_del_sistema()
    esperar(v and v != 'None', v)
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_idioma_'))
    viejo = {k: os.environ.pop(k, None) for k in ('LANG', 'LC_ALL', 'LC_MESSAGES')}
    try:
        (carpeta / 'Library' / 'Preferences').mkdir(parents=True)
        with open(carpeta / 'Library' / 'Preferences' / '.GlobalPreferences.plist', 'wb') as f:
            plistlib.dump({'AppleLocale': 'es_ES', 'AppleLanguages': ['es-ES']}, f)
        with parches((locale, 'getlocale', lambda *a: (None, None)), (registro, '_idioma_qt', lambda: None), (sys, 'platform', 'darwin')):
            v = registro.idioma_del_sistema(casa=carpeta)
        esperar(v == 'es_ES', v)
    finally:
        os.environ.update({k: x for k, x in viejo.items() if x is not None})
        __import__('shutil').rmtree(carpeta, ignore_errors=True)


@caso('Informes de clientes')
def informe_dice_si_el_chequeo_sigue_en_marcha():
    with parches((salud, '_ULTIMO', {'filas': None, 'cuando': 0.0, 'empezo': time.time() - 5})):
        lineas = registro._motores()
    esperar(lineas and 'en marcha' in lineas[0], lineas)


# El mismo portátil con la 5.76 (13:07:26 y 13:07:44): «El programa lleva 46 s abriendo y no termina» con el hilo de la ventana en
# escena_go._cargar_referencia, explicado como «Un efecto visual de Inicio falló», y el monitor: «No se puede escribir en … (PermissionError:
# [WinError 32] …\.escritura.tmp): no se guardarán ajustes…», como «Detuvo la tarea».
def _bloqueado(ruta):
    return PermissionError(32, 'El proceso no tiene acceso al archivo porque está siendo utilizado por otro proceso', str(ruta))


@caso('Informes de clientes')
def monitor_escritura_con_bloqueo_de_un_momento_no_es_error():
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_escritura_'))
    real = pathlib.Path.write_text
    try:
        with parches((vigilancia, 'CARPETA', carpeta)):
            fijo = open(carpeta / '.escritura.tmp', 'a', encoding='utf-8')         # otro hilo (o el antivirus) tiene abierto el de nombre fijo
            try:
                a = dict((c, n) for c, n, _m in vigilancia._comprobaciones())
            finally:
                fijo.close()
            veces = {'n': 0}

            def falla_dos(self, *x, **k):
                if self.name.startswith('.escritura') and veces['n'] < 2:
                    veces['n'] += 1
                    raise _bloqueado(self)
                return real(self, *x, **k)
            with parches((pathlib.Path, 'write_text', falla_dos)):
                b = dict((c, n) for c, n, _m in vigilancia._comprobaciones())
            with parches((pathlib.Path, 'write_text', lambda self, *x, **k: (_ for _ in ()).throw(PermissionError(13, 'Acceso denegado', str(self))))):
                c = [(n, m) for k, n, m in vigilancia._comprobaciones() if k == 'escritura']
        restos = sorted(p.name for p in carpeta.iterdir() if p.name != '.escritura.tmp')
        esperar(a.get('escritura') is None, f'con el .tmp de antes abierto por otro: {a}')
        esperar(b.get('escritura') is None, f'con 2 bloqueos de un momento: {b}')
        esperar(c and c[0][0] == 'error' and 'Acceso denegado' in c[0][1], f'si de verdad no se puede escribir, sí debe decirlo: {c}')
        esperar(not restos, f'quedaron archivos de prueba: {restos}')
    finally:
        __import__('shutil').rmtree(carpeta, ignore_errors=True)


@caso('Informes de clientes')
def monitor_y_chequeo_de_arranque_a_la_vez():
    """El chequeo de arranque llama a revisar_ahora() en su hilo mientras el monitor hace su pasada: nunca «no se puede escribir»."""
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_escritura2_'))
    anotado = []
    try:
        with parches((vigilancia, 'CARPETA', carpeta), (vigilancia, '_MONITOR', {'v': None, 'estado': {}}),
                     (registro, 'anotar', lambda nivel, mensaje, origen='', detalle='': anotado.append((nivel, str(mensaje))))):
            for _ in range(15):
                hilos = [threading.Thread(target=vigilancia.revisar_ahora) for _h in range(3)]
                for h in hilos:
                    h.start()
                for h in hilos:
                    h.join(20)
        malas = [m for n, m in anotado if 'escribir' in m]
        esperar(not malas, malas[:2])
    finally:
        __import__('shutil').rmtree(carpeta, ignore_errors=True)


@caso('Informes de clientes')
def arranque_no_lee_la_imagen_de_la_escena():
    """escena_go leía fondo_esfera.jpg en el hilo de la ventana al crearse (y nadie usaba el resultado): en ese portátil esa lectura dejó
    el arranque 46 s parado."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import escena_go
    leidas = []
    real = escena_go.QImage

    def imagen(*a, **k):
        if a and isinstance(a[0], str):
            leidas.append(a[0])
        return real(*a, **k)
    with parches((escena_go, 'QImage', imagen)):
        w = escena_go.EscenaGo()
    w.deleteLater()
    esperar(not [r for r in leidas if 'fondo_esfera' in r], leidas)


def _reparar_motor(lineas_texto, codigo_texto):
    """motor_voz.instalar() («Reparar el motor») con todo simulado (nada se baja ni se instala; listo.json en una carpeta temporal) y la descarga
    de la IA de texto (motor_texto.py --descargar) contando `lineas_texto`. Devuelve (avisos del Registro, último texto del progreso, listo.json)."""
    import cuda_libs
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_reparar_'))
    (carpeta / 'python').mkdir()
    (carpeta / 'python' / 'python.exe').write_text('', encoding='utf-8')
    anotado, progreso = [], []

    def lanzar(argumentos, on_linea, timeout=None, sin_senal=None):
        if '--comprobar' in argumentos:
            on_linea('LISTO', json.dumps({'torch': '2.14.1+cu130', 'cuda': True, 'gpu': 'NVIDIA GeForce RTX 4070 Laptop GPU', 'vram_gb': 8.0,
                                          'modelo_auto': '1.7B'}))
        return 0, []

    def lanzar_texto(script, argumentos, on_linea, timeout=None, sin_senal=None):
        for tipo, texto in lineas_texto:
            on_linea(tipo, texto)
        return codigo_texto, []
    try:
        with parches((motor_voz, 'carpeta', lambda: carpeta), (motor_voz, 'python_motor', lambda: carpeta / 'python' / 'python.exe'),
                     (motor_voz, '_python_al_dia', lambda: True), (motor_voz, 'torch_para_este_equipo', lambda: ('cu130', '2.14.1')),
                     (motor_voz, '_dist_instalada', lambda n, v=None: '2.14.1+cu130' if n == 'torch' else '1'),
                     (motor_voz, '_faltan_requisitos', lambda: []), (motor_voz, '_lanzar', lanzar), (motor_voz, '_lanzar_script', lanzar_texto),
                     (motor_voz, '_borrar_modelos_viejos', lambda: None), (motor_voz, 'ia_texto_para_esta_gpu', lambda: ['1.7B']),
                     (cuda_libs, 'reparar', lambda **k: (True, 'GPU lista')),
                     (registro, 'anotar', lambda nivel, mensaje, origen='', detalle='': anotado.append((nivel, str(mensaje), origen)))):
            motor_voz.instalar(progreso=lambda f, t: progreso.append(t))
        listo = json.loads((carpeta / 'listo.json').read_text(encoding='utf-8'))
    finally:
        __import__('shutil').rmtree(carpeta, ignore_errors=True)
    return [(n, m, o) for n, m, o in anotado if n in ('aviso', 'error')], (progreso or [''])[-1], listo


@caso('Informes de clientes')
def reparar_dice_si_no_bajo_la_ia_de_texto():
    """«Reparar el motor» terminaba en «Motor Qwen3-ASR listo» aunque la IA de texto no se hubiera bajado (sin espacio, sin red): ahora lo dice
    en el Registro (qué no se bajó, por qué y qué hacer) y en el progreso."""
    error = ('ERROR', 'RuntimeError: no se descargó ninguna IA de texto')
    casos = {
        'disco': ([('ESTADO', 'No descargo Qwen/Qwen3-1.7B: necesita unos 6 GB libres y en el disco quedan 3.2 GB'), error], 1, ('disco', '6 GB', '3.2')),
        'disco (mensaje de antes)': ([('ESTADO', 'No descargo Qwen/Qwen3-1.7B: necesita unos 4 GB y en el disco quedan 3.2 GB libres'), error], 1,
                                     ('disco', '3.2')),
        'red': ([('ESTADO', 'Descargando Qwen/Qwen3-1.7B'), ('ESTADO', 'No pude descargar Qwen/Qwen3-1.7B: LocalEntryNotFoundError: An error happened '
                 'while trying to locate the file on the Hub'), error], 1, ('conexión',)),
    }
    malas = []
    for nombre, (lineas, codigo, debe) in casos.items():
        avisos, ultimo, listo = _reparar_motor(lineas, codigo)
        sobre = [m for _n, m, _o in avisos if 'IA de texto' in m]
        titulo = registro_ayuda.explicar(types.SimpleNamespace(nivel='aviso', mensaje=sobre[0], origen=avisos[0][2], detalle=''))[0] if sobre else ''
        if not sobre or not all(d in sobre[0] for d in debe) or 'Qwen3-1.7B' not in sobre[0] or 'sin la IA de texto' not in ultimo \
                or titulo != 'No se descargó la IA de texto' or listo.get('modelo_texto'):
            malas.append(f'{nombre}: avisos={sobre[:1]} · progreso «{ultimo}» · «{titulo}»')
    avisos, ultimo, listo = _reparar_motor([('ESTADO', 'Descargando Qwen/Qwen3-1.7B'), ('LISTO', '1.7B')], 0)
    if avisos or ultimo != 'Motor Qwen3-ASR listo' or listo.get('modelo_texto') != '1.7B':
        malas.append(f'si se bajó: avisos={avisos} · «{ultimo}» · {listo.get("modelo_texto")}')
    # y Ajustes, al terminar «Reparar», ya no lo pinta en verde como si estuviera todo
    pintado = {}
    falso = types.SimpleNamespace(motor_estado=types.SimpleNamespace(configure=lambda **k: pintado.update(k)),
                                  motor_btn=types.SimpleNamespace(configure=lambda **k: None, hide=lambda: None))
    for texto, hay in ((None, []), ('1.7B', ['1.7B'])):
        pintado.clear()
        with parches((motor_voz, 'info_instalado', lambda: {'modelo': '1.7B', 'gpu': 'RTX 4070 Laptop', 'modelo_texto': texto}),
                     (motor_voz, 'modelos_texto_descargados', lambda: list(hay))):
            ajustes_ui.VentanaAjustes._pintar_motor(falso)
        sin = 'sin la IA de texto' in str(pintado.get('text'))
        if sin != (texto is None):
            malas.append(f'Ajustes con modelo_texto={texto}: «{pintado.get("text")}»')
    esperar(not malas, '\n      '.join(malas))


# ---------------------------------------------------------------------------------------------------------------------------------------
# J. Fallos de la interfaz que se ven (revisión con capturas de todas las pantallas, 2026-11-10)
# ---------------------------------------------------------------------------------------------------------------------------------------
def _qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@caso('Interfaz')
def proyectos_con_nombres_largos_y_repetidos():
    """Proyectos guardados: un video de 150 letras («From Klickpin.com-…», de verdad en la lista del autor) ensanchaba todas las filas y los
    botones «Abrir» y «Eliminar» quedaban FUERA de la ventana; y dos videos con el mismo nombre no se distinguían."""
    app = _qapp()
    M = principal()
    import qt_kit
    from PySide6.QtWidgets import QWidget
    largo = 'From Klickpin.com- Need fresh inspiration Save these cozy cottage garden ideas that help you plan a beautiful backyard this spring.mp4'
    items = [{'video_path': rf'C:\Videos\{largo}', 'existe': True, 'modificado_en': 1.79e9},
             {'video_path': r'C:\Clientes\Ana\PRUEBA.mp4', 'existe': True, 'modificado_en': 1.79e9},
             {'video_path': r'D:\Pruebas\PRUEBA.mp4', 'existe': False, 'modificado_en': 1.78e9}]
    padre = QWidget()
    padre.resize(1400, 900)
    with parches((M.proyectos, 'listar', lambda: [dict(i) for i in items])):
        d = M.ProyectosWindow(padre)
        d.show()
        for _ in range(20):
            app.processEvents()
            time.sleep(0.02)
        ancho = d.lista_frame.viewport().width()
        botones = [b for b in d.findChildren(qt_kit.Boton) if getattr(b, '_texto', None) in ('Abrir', 'Eliminar')
                   or (callable(getattr(b, 'text', None)) and b.text() in ('Abrir', 'Eliminar'))]
        fuera = [b.mapTo(d.lista_frame.viewport(), b.rect().topRight()).x() for b in botones
                 if b.mapTo(d.lista_frame.viewport(), b.rect().topRight()).x() > ancho]
        textos = [l.text() for l in d.findChildren(qt_kit.Etiqueta)]
        d.close()
    esperar(botones and not fuera, f'{len(botones)} botones · fuera de la ventana (x > {ancho}): {fuera[:3]}')
    esperar(any('Ana' in t for t in textos) and any('Pruebas' in t for t in textos), f'los dos «PRUEBA.mp4» deben decir su carpeta: {textos}')


@caso('Interfaz')
def registro_dice_1_anotacion():
    _qapp()
    import registro_ui
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_registro_ui_'))
    try:
        with parches((registro, 'CARPETA', carpeta), (registro, 'ARCHIVO', carpeta / 'c.log'), (registro, 'ARCHIVO_ERRORES', carpeta / 'e.log')):
            r = registro.registro()
            antes = list(r._lista)
            r._lista.clear()
            try:
                registro.error('Prueba: KeyError: 7', 'prueba')
                d = registro_ui.DialogoRegistro(None)
                texto = d._cuenta.text()
                d.close()
            finally:
                r._lista.clear()
                r._lista.extend(antes)
    finally:
        __import__('shutil').rmtree(carpeta, ignore_errors=True)
    esperar(texto.startswith('1 anotación'), texto)


@caso('Interfaz')
def editor_no_anota_lo_que_esta_en_marcha():
    """«Corrigiendo la ortografía con IA…» llegaba al Registro como OK y la línea de Inicio lo enseñaba con ✓ (como si estuviera hecho)."""
    M = principal()
    import ui_toast
    vistos = []
    with parches((ui_toast, 'mostrar', lambda padre, texto, **k: vistos.append(texto))):
        aviso = M._AvisoToast(None)
        aviso.configure(text='Corrigiendo la ortografía con IA…')
        aviso.configure(text='✓ 3 correcciones aplicadas (IA) · Ctrl+Z las deshace')
    esperar(vistos == ['✓ 3 correcciones aplicadas (IA) · Ctrl+Z las deshace'], vistos)


@caso('Interfaz')
def panel_de_emojis_no_aplasta_sus_botones():
    """El panel de emojis, como lo abre el editor de palabras (la palabra ya tiene emoji: «Quitar emoji»; y «➕ Mi PNG…»): en una sola fila
    con el estilo no cabía en sus 480 px y «Animado · 3D · Google · Sistema» salía aplastado e ilegible, con los botones cortados."""
    app = _qapp()
    M = principal()
    import emojis
    import qt_kit
    from PySide6.QtWidgets import QAbstractButton, QWidget

    class Maestro(QWidget):
        def _poner_mi_png(self, idx, ruta=None):
            return None

    maestro = Maestro()
    maestro.resize(1000, 760)
    with parches((emojis, 'estilo', lambda: 'sistema')):          # (los del sistema: nada que bajar)
        maestro.show()
        p = M.EmojiPickerWindow(maestro, 'hola', 'es', '😀', lambda *a: None, idx=0)
        p.mostrar_en(10, 10)
        for _ in range(20):
            app.processEvents()
            time.sleep(0.02)
        cortados = [(b.text(), b.sizeHint().width(), b.width()) for b in p.findChildren(QAbstractButton)
                    if b.isVisible() and b.text().strip() and b.sizeHint().width() > b.width() + 2]
        aplastados = [(s.sizeHint().width(), s.width()) for s in p.findChildren(qt_kit.Segmentado) if s.isVisible() and s.width() + 2 < s.sizeHint().width()]
        botones = [b.text() for b in p.findChildren(QAbstractButton) if b.isVisible() and b.text().strip()]
        p.cerrar()
        maestro.close()
    esperar(len(botones) >= 2, f'no se vieron los botones del panel: {botones}')
    esperar(not cortados and not aplastados, f'botones cortados (texto, pide, tiene): {cortados} · estilo aplastado (pide, tiene): {aplastados}')


@caso('Interfaz')
def botones_de_licencia_en_fila_solo_si_caben():
    """Ajustes › Ayuda: «Actualizar licencia» y «Desactivar este equipo» iban siempre en fila en 380 px; en alemán, francés o ruso el
    segundo salía cortado. Ahora van uno encima del otro cuando no caben."""
    _qapp()
    import qt_kit
    from PySide6.QtWidgets import QBoxLayout, QHBoxLayout, QWidget

    def direccion(t1, t2):
        caja = QWidget()
        fila = QHBoxLayout(caja)
        fila.setSpacing(10)
        b1, b2 = qt_kit.Boton(t1, None, tipo='neutro', alto=42, tam=14), qt_kit.Boton(t2, None, tipo='peligro', alto=42, tam=14)
        fila.addWidget(b1)
        fila.addWidget(b2)
        ajustes_ui.VentanaAjustes._acomodar_botones_licencia(types.SimpleNamespace(lic_btn=b1, lic_desact=b2, _lic_fila=fila))
        return fila.direction()

    corta, larga = direccion('Ver', 'Desactivar'), direccion('Diesen Computer deaktivieren', 'Diesen Computer deaktivieren')
    esperar(corta == QBoxLayout.Direction.LeftToRight, f'textos cortos: en fila ({corta})')
    esperar(larga == QBoxLayout.Direction.TopToBottom, f'textos largos: uno encima del otro ({larga})')


@caso('Interfaz')
def titulo_de_cabecera_cabe_en_su_sitio():
    """Panel rápido de Ajustes en francés: «À propos de CineCaptions» (26 px) no cabía y salía cortado a secas («…CineCaption»). Ahora el
    título de las cabeceras encoge la letra hasta el 70 % para caber."""
    app = _qapp()
    import qt_kit
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
    texto = 'À propos de CineCaptions · À propos de CineCaptions'
    natural = qt_kit.Etiqueta(texto, 26, peso='extra').sizeHint().width()
    caja = QWidget()
    caja.setFixedWidth(int(natural * 0.8) + 48)            # (+ la X de cerrar y su separación)
    capa = QVBoxLayout(caja)
    capa.setContentsMargins(0, 0, 0, 0)
    cab = ajustes_ui._cabecera('RÉGLAGES', texto, lambda: None, tam=26)
    capa.addWidget(cab)
    caja.show()
    for _ in range(10):
        app.processEvents()
        time.sleep(0.02)
    titulo = next(l for l in cab.findChildren(QLabel) if l.text() == texto)
    pide, tiene = titulo.fontMetrics().horizontalAdvance(texto), titulo.contentsRect().width()
    derecha = titulo.mapTo(caja, titulo.rect().topRight()).x()
    caja.close()
    esperar(pide <= tiene + 1 and derecha <= caja.width(), f'el título pide {pide} y tiene {tiene}; acaba en x={derecha} (la caja mide {caja.width()})')


@caso('Interfaz')
def segundo_clic_en_su_boton_cierra_el_panel():
    """v5.84 (el usuario, con el chip «Estilo» de Inicio abierto: «cuando vuelva a darle clic que se cierre y si le doy otra vez que abra; va a ser
    más intuitivo en cada botón»). En Windows, Qt cierra un panel emergente con el clic de fuera y, si el panel no lleva WA_NoMouseReplay, se lo
    DEVUELVE al botón que hay debajo: pulsar el chip con su panel abierto lo cerraba y lo volvía a abrir. Sin pantalla Qt no agarra el ratón y no
    devuelve nada, así que se mira lo que lo decide: con qué marca se cierra el panel (con marca al pulsar SU botón; sin ella al pulsar en otro
    sitio, para que ese clic llegue a lo pulsado). Clics por la QWindow (el mismo reparto de Qt que un clic de verdad)."""
    app = _qapp()
    import editor_ui
    import menu_estilo_ui
    import menu_pro_ui
    import qt_kit as ui
    import un_clic_ui
    from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton, QWidget
    cierres = []

    class Espia(QObject):
        def eventFilter(self, obj, e):
            if e.type() == QEvent.Type.Hide and isinstance(obj, QWidget) and obj.isWindow() and obj.windowType() == Qt.WindowType.Popup:
                cierres.append(obj.testAttribute(Qt.WidgetAttribute.WA_NoMouseReplay))
            return False

    def bombear(s):
        fin = time.time() + s
        while time.time() < fin:
            app.processEvents()
            time.sleep(0.01)

    def clic_en(w, punto):
        QTest.mousePress(w.windowHandle(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punto)
        bombear(0.05)
        QTest.mouseRelease(w.windowHandle(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, punto)
        bombear(0.25)

    def probar(nombre, armar, es_menu=False):
        """armar(w, d) -> botón que abre el panel y lo deja en d['p']. Devuelve [] si va bien, o lo que falló."""
        w, d = QWidget(), {}
        w.resize(900, 700)
        boton = armar(w, d)
        w.show()
        w.activateWindow()
        bombear(0.25)
        en_boton, fuera = boton.mapTo(w, boton.rect().center()), QPoint(860, 20)

        def abierto():
            return bool(d.get('p') is not None and ui.vivo(d['p']) and d['p'].isVisible())
        visto, marcas = [], []
        if es_menu:                                  # (QMenu.exec tiene su propio bucle: el segundo clic va por temporizador, dentro)
            def dentro(punto):
                visto.append(abierto())
                n = len(cierres)
                clic_en(w, punto)
                marcas.append(cierres[n:n + 1])
            QTimer.singleShot(300, lambda: dentro(en_boton))
            clic_en(w, en_boton)
            bombear(0.4)
            visto.append(abierto())
            QTimer.singleShot(300, lambda: dentro(fuera))
            clic_en(w, en_boton)
            bombear(0.4)
            visto.append(abierto())
        else:
            for punto in (en_boton, en_boton, en_boton, fuera):
                n = len(cierres)
                clic_en(w, punto)
                visto.append(abierto())
                if len(visto) in (2, 4):
                    marcas.append(cierres[n:n + 1])
        w.close()
        bombear(0.15)
        malo = visto[:4] != [True, False, True, False] or marcas != [[True], [False]]
        return [f'{nombre}: abierto {visto[:4]}, marca al pulsar su botón / fuera {marcas}'] if malo else []

    def chip(w, nombre, valor, abrir):
        c = un_clic_ui.ChipGo('ph.palette', nombre, valor, 'verde', None, menu=True, padre=w)
        c.move(300, 600)
        c.resize(c.sizeHint())
        c.clicked.connect(lambda: abrir(c))
        return c

    def estilo(w, d):
        packs = [{'nombre': f'Tema {i}', 'etiqueta': f'Estilo {i}', 'sirve': True} for i in range(1, 10)]
        return chip(w, 'Estilo', '7', lambda c: d.__setitem__('p', menu_estilo_ui.abrir(w, packs, 'Tema 7', lambda n: None, lambda: None, ancla=c)))

    def pro(w, d):
        return chip(w, 'Edición PRO', 'No', lambda c: d.__setitem__('p', menu_pro_ui.abrir(w, lambda: ({}, False), lambda *a: None, lambda: None,
                                                                                           False, ancla=c)))

    def menu(w, d):
        b = QPushButton('Menos…', w)
        b.setGeometry(40, 40, 120, 36)

        def abrir():
            m = ui.Menu(w)
            m.agregar('uno', lambda: None)
            d['p'] = m
            m.mostrar(b.mapToGlobal(QPoint(0, b.height() + 6)), ancla=b)
        b.clicked.connect(abrir)
        return b

    def letras(w, d):
        b = QPushButton('Del estilo', w)
        b.setGeometry(300, 600, 160, 36)

        def abrir():
            t = editor_ui.TarjetaColores.__new__(editor_ui.TarjetaColores)        # (solo el método: sin armar toda la tarjeta)
            t._aj, t._poner, t.window = {'fuente_principal': ''}, (lambda c, v: None), (lambda: w)
            antes = {id(x) for x in w.findChildren(editor_ui._PopupLetras)}
            editor_ui.TarjetaColores._abrir_letras(t, 'fuente_principal', b)
            nuevos = [x for x in w.findChildren(editor_ui._PopupLetras) if id(x) not in antes]
            d['p'] = nuevos[-1] if nuevos else None
        b.clicked.connect(abrir)
        return b

    espia = Espia()
    app.installEventFilter(espia)
    try:
        fallos = (probar('chip «Estilo»', estilo) + probar('chip «Edición PRO»', pro) + probar('ui.Menu de un botón', menu, es_menu=True)
                  + probar('letras de «Colores y letra»', letras))
    finally:
        app.removeEventFilter(espia)
    esperar(not fallos, ' | '.join(fallos))


@caso('Informes de clientes')
def arranque_lento_y_escritura_bien_explicados():
    pila = ('Hilo principal:\n  File "CineCaptions (script principal).py", line 6785, in _build_ui\n  File "escena_go.py", line 419, in __init__\n'
            '  File "escena_go.py", line 450, in _cargar_referencia\n')
    casos = [('error', 'arranque', 'El programa lleva 46 s abriendo y no termina: algo se quedó esperando.', pila, 'abrir', 'efecto'),
             ('error', 'monitor', 'No se puede escribir en ~\\DaVinciSubtitles (PermissionError: [WinError 32] El proceso no tiene acceso al archivo '
              'porque está siendo utilizado por otro proceso): no se guardarán ajustes, marcas ni el registro.', '', 'carpeta', 'no dejó escribir')]
    malas = []
    for nivel, origen, msg, detalle, debe, no_debe in casos:
        a = registro_ayuda.explicar(types.SimpleNamespace(nivel=nivel, mensaje=msg, origen=origen, detalle=detalle))
        if debe not in a[0].lower() or no_debe in a[0].lower() or a[3] == 'bloquea':
            malas.append(f'«{msg[:45]}…» → «{a[0]}» ({a[3]})')
    esperar(not malas, '\n      '.join(malas))


# ---------------------------------------------------------------------------------------------------------------------------------------
# Cancelar GO y cerrar (auditoría 5.85; errores.log real del 2026-11-10): cancelar no es un fallo, no deja nada en marcha y cerrar no se cuelga
# ---------------------------------------------------------------------------------------------------------------------------------------
_BARRA_CARGA = ('Loading weights:   0%|          | 0/707 [00:00<?, ?it/s]\rLoading weights:  10%|#         | 73/707 '
                '[00:00<00:00, 727.31it/s]\rLoading')


class _RegistroEspia:
    def __init__(self):
        self.lineas = []

    def __getattr__(self, nivel):
        return lambda msg, *a, **k: self.lineas.append((nivel, str(msg)))


def _proceso_vivo(pid, espera_s=2.0):
    """¿Sigue vivo el proceso `pid` pasados `espera_s` segundos?"""
    if sys.platform.startswith('win'):
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x00100000, False, int(pid))            # SYNCHRONIZE
        if not h:
            return False
        try:
            return k.WaitForSingleObject(h, int(espera_s * 1000)) == 0x102      # WAIT_TIMEOUT: sigue vivo
        finally:
            k.CloseHandle(h)
    fin = time.time() + espera_s
    while time.time() < fin:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        time.sleep(0.1)
    return True


@caso('Cancelar GO')
def cancelar_durante_la_voz_no_lanza_otra_pasada():
    """Cancelar con Qwen3-ASR transcribiendo: el motor residente muerto contaba como fallo («El motor de voz residente no pudo (Loading
    weights…): pruebo con una pasada suelta») y se lanzaba OTRA pasada del modelo DESPUÉS de cancelar."""
    espia, lanzados = _RegistroEspia(), []

    class ServidorCancelado:
        def vivo(self):
            return True

        def pedir(self, *a, **k):
            motor_voz.cancelar()                               # (el usuario pulsa Cancelar a mitad)
            return False, _BARRA_CARGA

    wav = os.path.join(tempfile.mkdtemp(prefix='cc_cancelar_'), 'audio.wav')
    open(wav, 'wb').close()
    viejo, salida = motor_voz._SRV_VOZ['s'], None
    try:
        with parches((motor_voz, '_audio_16k', lambda m: wav), (motor_voz, 'modo_gpu', lambda: 'residente'), (motor_voz, '_reg', lambda: espia),
                     (motor_voz, '_lanzar', lambda *a, **k: lanzados.append(a) or (1, [])), (motor_voz, 'abortar', lambda: False)):
            motor_voz._SRV_VOZ['s'] = ServidorCancelado()
            try:
                motor_voz.transcribir(wav, 'es')
                salida = 'terminó sin cancelar'
            except SystemExit as e:
                salida = f'SystemExit: {e}'
            except Exception as e:
                salida = f'{type(e).__name__}: {e}'
    finally:
        motor_voz._SRV_VOZ['s'] = viejo
        if hasattr(motor_voz, 'permitir'):
            motor_voz.permitir()
    esperar(not lanzados, f'tras Cancelar se lanzaron {len(lanzados)} pasadas sueltas más ({salida})')
    esperar(not [x for x in espia.lineas if x[0] in ('aviso', 'error')], f'avisos de fallo tras Cancelar: {espia.lineas}')
    esperar(salida and salida.startswith('SystemExit'), f'debía salir como cancelación: {salida}')


@caso('Cancelar GO')
def motor_cortado_a_mitad_no_queda_vivo():
    """Cancelar llega a mitad de una pasada suelta (SystemExit desde su avance): el proceso del motor seguía vivo con el modelo en la GPU."""
    carpeta = tempfile.mkdtemp(prefix='cc_motor_')
    script, marca = os.path.join(carpeta, 'motor_falso.py'), os.path.join(carpeta, 'pid.txt')
    with open(script, 'w', encoding='utf-8') as f:
        f.write('import os, sys, time\nopen(sys.argv[1], "w").write(str(os.getpid()))\nprint("PROGRESO|0.1", flush=True)\n'
                'for _ in range(300):\n    time.sleep(0.1)\nprint("LISTO|x", flush=True)\n')

    def avance(tipo, texto):
        if tipo == 'PROGRESO':
            raise SystemExit('GO cancelado.')

    salida = None
    with parches((motor_voz, 'python_motor', lambda: pathlib.Path(sys.executable)), (motor_voz, 'esperar_puesta_al_dia', lambda: None),
                 (motor_voz, 'carpeta', lambda: pathlib.Path(carpeta))):
        try:
            motor_voz._lanzar_script(pathlib.Path(script), [marca], avance, sin_senal=60)
            salida = 'terminó'
        except SystemExit:
            salida = 'cancelado'
    pid = int(open(marca, encoding='utf-8').read())
    vivo = _proceso_vivo(pid, espera_s=3.0)
    if vivo:
        subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True) if sys.platform.startswith('win') else os.kill(pid, 9)
    esperar(salida == 'cancelado' and not vivo, f'{salida} · el proceso del motor seguía vivo tras cortarlo: {vivo}')


@caso('Cancelar GO')
def motivo_del_motor_sin_barras_de_carga():
    """El motor de voz se cierra mientras carga el modelo: el motivo del Registro era la barra «Loading weights: 10%|# …» (redibujada con \\r)."""
    codigo = ('import sys, time\nsys.stdin.readline()\nsys.stderr.write(' + repr(_BARRA_CARGA + '\n') + ')\nsys.stderr.flush()\n'
              'time.sleep(0.5)\nsys.exit(1)\n')

    class VozFalsa(motor_voz._ServidorVoz):
        def __init__(self):
            self.modelo = 'falso'
            self.p = subprocess.Popen([sys.executable, '-c', codigo], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.lineas = __import__('queue').Queue()
            self.errores = []
            self.pedido = threading.Lock()
            threading.Thread(target=self._leer, daemon=True).start()
            threading.Thread(target=self._leer_err, daemon=True).start()

    ok, motivo = VozFalsa().pedir('a.wav', 'Spanish', 'a.json', lambda *a: None, timeout=30, sin_senal=10)
    esperar(not ok and '%|' not in motivo and 'Loading' not in motivo, f'motivo: {motivo!r}')
    m = motor_voz.motivo_de_errores(['Traceback (most recent call last):', '  File "motor_qwen.py", line 3, in <module>',
                                     'torch.OutOfMemoryError: CUDA out of memory', 'Loading weights: 100%|#| 707/707 [00:01<00:00]'], '—')
    esperar(m == 'torch.OutOfMemoryError: CUDA out of memory', f'motivo de la excepción: {m!r}')


@caso('Cancelar GO')
def cancelar_mientras_abre_resolve_no_dice_que_se_cerro_solo():
    """Soltar un video y pulsar Cancelar mientras Resolve abre: Cancelar lo cierra a propósito y corta sus esperas («…(cancelado)»); GO lo tomaba
    por un fallo: «Resolve se cerró solo (…): lo vuelvo a abrir y repito» dos veces y «No pude preparar Resolve para tu video» (explicado como
    «No pude traer el audio del timeline»)."""
    M = principal()
    import colocacion
    import registro
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_cancelar_resolve_'))
    falso = types.SimpleNamespace(msg_queue=__import__('queue').Queue(), _cancelar_go=True, _go_tl_listo=threading.Event())
    for nombre in ('_go_reparar_resolve', '_go_proyecto_usuario'):
        setattr(falso, nombre, types.MethodType(getattr(M.SubtitleApp, nombre), falso))
    falso._esperar_vistas_reales = lambda *a, **k: None
    falso._go_proyecto = lambda: 'CineCaptions'
    llamadas, anotado = [], []
    r = registro.registro()
    antes = list(r._lista)
    r._lista.clear()
    resolve_mcp.cancelar_esperas()
    try:
        with parches((registro, 'CARPETA', carpeta), (registro, 'ARCHIVO', carpeta / 'c.log'), (registro, 'ARCHIVO_ERRORES', carpeta / 'e.log'),
                     (resolve_mcp, 'preparar_proyecto', lambda *a, **k: llamadas.append(1) or {'ok': False, 'motivo': 'Resolve no terminó de abrirse (cancelado)'}),
                     (resolve_mcp, 'cerrar', lambda *a, **k: None), (colocacion, 'pids_resolve', lambda: []),
                     (colocacion, 'detener_reproduccion', lambda: None)):
            M.SubtitleApp._go_timeline_del_video(falso, 'video.mp4', {'tl_ancho': 1080, 'tl_alto': 1920, 'tl_fps': 30})
        anotado = [f'{e.nivel}: {e.mensaje}' for e in r._lista if e.nivel in ('aviso', 'error')]
    finally:
        resolve_mcp.permitir_esperas()
        r._lista.clear()
        r._lista.extend(antes)
    esperar(not anotado, ' | '.join(anotado))
    esperar(len(llamadas) == 1, f'tras Cancelar se volvió a preparar Resolve ({len(llamadas)} veces en total)')
    esperar(falso._go_tl_listo.is_set(), 'el paso debía avisar de que terminó (si no, GO espera hasta 900 s)')


@caso('Cancelar GO')
def cerrar_colgado_sale_igual():
    """Al cerrar, un atexit que no vuelve (el 2026-11-10 el programa se quedó ≥ 153 s cerrándose y, mientras, abrirlo otra vez no hacía nada):
    con el tope sale a los pocos segundos y deja las pilas de los hilos en fallo_nativo.log."""
    carpeta = tempfile.mkdtemp(prefix='cc_salida_')
    codigo = (f'import atexit, os, sys, time\nsys.path.insert(0, {CODIGO!r})\nimport registro\nfrom pathlib import Path\nc = Path({carpeta!r})\n'
              'registro.CARPETA, registro.ARCHIVO, registro.ARCHIVO_ERRORES = c, c / "c.log", c / "e.log"\n'
              'registro.FALLOS_NATIVOS = c / "fallo_nativo.log"\nregistro._fallos_nativos()\natexit.register(time.sleep, 60)\n'
              'registro.tope_de_salida(1.5)\nprint("cerrando", flush=True)\natexit._run_exitfuncs()\nos._exit(0)\n')
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, '-c', codigo], capture_output=True, text=True, timeout=40)
        salida = p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        salida = 'no salió en 40 s'
    tarda = time.time() - t0
    try:
        volcado = open(os.path.join(carpeta, 'fallo_nativo.log'), encoding='utf-8', errors='replace').read()
    except OSError:
        volcado = ''
    esperar('cerrando' in salida and tarda < 20 and 'Timeout (' in volcado, f'{tarda:.0f} s · {salida.strip()[-300:]} · volcado: {volcado[-200:]!r}')
    import inspect
    fuente = inspect.getsource(principal().main)
    esperar('tope_de_salida(' in fuente and fuente.index('tope_de_salida(') < fuente.index('_run_exitfuncs'), 'main() no pone el tope antes de los atexit')


# ---------------------------------------------------------------------------------------------------------------------------------------
# Datos del usuario y GO (auditoría 5.85): un archivo bloqueado un momento no borra nada; GO no reutiliza el audio de otro timeline
# ---------------------------------------------------------------------------------------------------------------------------------------
@contextlib.contextmanager
def _abierto_en_exclusiva(ruta, segundos):
    """Abre `ruta` en exclusiva (nadie más puede ni leerla) durante `segundos`, como un antivirus o una copia de seguridad (solo Windows)."""
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k.CreateFileW.restype = wintypes.HANDLE
    listo = threading.Event()

    def bloquear():
        h = k.CreateFileW(str(ruta), 0x80000000, 0, None, 3, 0, None)            # GENERIC_READ, sin compartir, OPEN_EXISTING
        listo.set()
        time.sleep(segundos)
        k.CloseHandle(h)
    hilo = threading.Thread(target=bloquear, daemon=True)
    hilo.start()
    listo.wait(5)
    try:
        yield
    finally:
        hilo.join(segundos + 5)


@caso('Datos del usuario')
def preferencias_bloqueadas_un_momento_no_se_borran():
    """El antivirus abre preferencias.json en exclusiva mientras se guarda un cambio: mezclar_json lo daba por «roto» y guardaba SOLO el cambio
    (se perdían todas las demás preferencias; reproducido con 0,45 s)."""
    if not sys.platform.startswith('win'):
        return
    import archivos_seguros
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_prefs_'))
    ruta = carpeta / 'preferencias.json'
    original = {'tema': 'azul', 'acento': 'verde', 'motor_voz': 'qwen3', 'go_pack': 'Kinetic', 'idioma_ui': 'es', 'recetas': [1, 2, 3]}
    malas = []
    for segundos, debe_guardar in ((0.45, True), (1.8, False)):
        ruta.write_text(json.dumps(original), encoding='utf-8')
        with _abierto_en_exclusiva(ruta, segundos):
            ok = archivos_seguros.mezclar_json(ruta, {'pagina': 'inicio'})
        final = json.loads(ruta.read_text(encoding='utf-8'))
        if any(final.get(k) != v for k, v in original.items()):
            malas.append(f'bloqueo {segundos} s: quedaron {sorted(final)}')
        if bool(ok) != debe_guardar or (debe_guardar and final.get('pagina') != 'inicio'):
            malas.append(f'bloqueo {segundos} s: devolvió {ok} (se esperaba {debe_guardar})')
    esperar(not malas, ' | '.join(malas))


@caso('Datos del usuario')
def vocabulario_bloqueado_no_se_borra():
    """Corregir una palabra con vocabulario.json bloqueado un momento: se reescribía con SOLO la palabra nueva (de 5 términos quedaba 1)."""
    if not sys.platform.startswith('win'):
        return
    import vocabulario
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_vocab_'))
    ruta = carpeta / 'vocabulario.json'
    terminos = {t: {'veces': 2, 'de': [t.lower()], 'ultimo': 1.0} for t in ('Xela', 'FIFA', 'iPhone', 'DJ', 'U2')}
    ruta.write_text(json.dumps({'version': 1, 'terminos': terminos}), encoding='utf-8')
    with parches((vocabulario, 'RUTA', ruta)):
        with _abierto_en_exclusiva(ruta, 0.4):              # (un momento: la lectura fallaba al instante y la escritura, con reintentos, pasaba)
            ok = vocabulario.aprender_par('chakira', 'Shakira')
        quedan = sorted(json.loads(ruta.read_text(encoding='utf-8'))['terminos'])
        esperar(ok and 'Shakira' in quedan and set(terminos) <= set(quedan), f'quedaron {quedan} (devolvió {ok})')


@caso('Datos del usuario')
def go_sin_resultado_nuevo_no_usa_el_audio_de_otro_timeline():
    """Resolve Free: GO en el timeline A y luego en el B; el resultado de B tarda más de 6 s en llegar. Antes contaba como bueno y GO seguía
    con el render de A (seguía en video_var): colocaba en B los captions de A."""
    M = principal()
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_detectar_'))
    render_a = carpeta / 'Timeline A 2026-11-11 10-00-00.wav'
    render_a.write_bytes(b'RIFF')
    mio = carpeta / 'mi_video.mp4'
    mio.write_bytes(b'x')
    falso = types.SimpleNamespace(_video_de_resolve=str(render_a))
    motivo = 'Resolve terminó, pero no entregó un resultado nuevo (el último es de hace 3 min). Haz clic en tu timeline en Resolve y repite GO.'
    import registro
    with parches((resolve_bridge, 'ejecutar', lambda *a, **k: (True, '')), (resolve_bridge, 'esperar_video_detectado', lambda *a, **k: (None, motivo)),
                 (registro, 'CARPETA', carpeta), (registro, 'ARCHIVO', carpeta / 'c.log'), (registro, 'ARCHIVO_ERRORES', carpeta / 'e.log')):
        estado, err = M.SubtitleApp._go_detectar_en_resolve(falso)
    usar = lambda e, r: M.SubtitleApp._go_audio_que_usar(falso, e, str(r))      # noqa: E731
    casos = {('sin resultado nuevo + render de A', estado, render_a): 'fallo', ('error del Puente + render de A', 'error', render_a): 'fallo',
             ('resultado de ahora', 'ok', render_a): 'timeline', ('error + un archivo elegido por el usuario', 'error', mio): 'archivo'}
    malas = [f'{n}: {usar(e, r)} (se esperaba {d})' for (n, e, r), d in casos.items() if usar(e, r) != d]
    esperar(estado != 'ok' and err == motivo and not malas, f'detectar devolvió ({estado}, {err[:40]}…) · ' + ' | '.join(malas))


@caso('Datos del usuario')
def sonido_del_usuario_se_guarda_sin_write_text():
    """sfx_modo.json, favoritos, carpetas propias, volúmenes y recortes se escribían con write_text: un corte a mitad los dejaba a medias, se
    leían «de fábrica» y el guardado siguiente pisaba lo elegido sin dejar copia. Ahora van por archivos_seguros y uno roto se aparta como .roto."""
    import ast
    import sfx_rules
    arbol = ast.parse(pathlib.Path(CODIGO, 'sfx_rules.py').read_text(encoding='utf-8'))
    con_write = sorted(f.name for f in ast.walk(arbol) if isinstance(f, ast.FunctionDef) and f.name in ('_escribir_lista', '_escribir_dic', 'guardar_modo')
                       and any(isinstance(n, ast.Attribute) and n.attr in ('write_text', 'write_bytes') for n in ast.walk(f)))
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_sfx_'))
    modo = carpeta / 'sfx_modo.json'
    modo.write_text('{"modo": "simple", "donde": "principal", "sonidos": ["TAP_POP.mp3", "Bass', encoding='utf-8')      # (cortado a mitad)
    with parches((sfx_rules, 'ARCHIVO_MODO', modo), (sfx_rules, 'CARPETA_USUARIO', carpeta)):
        sfx_rules.guardar_modo(donde='todas')
        quedo = json.loads(modo.read_text(encoding='utf-8'))
    roto = modo.with_name(modo.name + '.roto')
    esperar(not con_write and roto.is_file() and quedo.get('donde') == 'todas',
            f'con write_text: {con_write} · copia .roto: {roto.is_file()} · guardado: {quedo.get("donde")}')


@caso('Datos del usuario')
def licencia_con_el_archivo_abierto_un_momento_sigue_activa():
    """licencia.dat leído sin reintentos: si el antivirus lo abría en exclusiva justo al comprobarla, la licencia salía como «no hay» (y se
    escribía a mano, sin fsync: tras un corte de luz podía quedar vacío)."""
    if not sys.platform.startswith('win'):
        return
    import licencia
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_licencia_'))
    ruta = carpeta / 'licencia.dat'
    with parches((licencia, '_archivo', lambda: ruta)):
        licencia._guardar({'equipo': licencia.id_equipo(), 'clave': 'CC-PRUEBA-0000', 'plataforma': 'cinecaptions', 'cliente': 'Prueba'})
        esperar(licencia.local() is not None, 'la licencia recién guardada no se lee')
        with _abierto_en_exclusiva(ruta, 0.4):
            datos = licencia.local()
    esperar(datos is not None and datos.get('clave') == 'CC-PRUEBA-0000', f'con el archivo abierto 0,4 s por otro programa: {datos}')


def _errores_del_registro(funcion):
    """Corre `funcion` con el Registro en una carpeta temporal y devuelve los (origen, mensaje) de los errores que anotó."""
    import registro
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_reg_'))
    r = registro.registro()
    antes = list(r._lista)
    r._lista.clear()
    try:
        with parches((registro, 'CARPETA', carpeta), (registro, 'ARCHIVO', carpeta / 'c.log'), (registro, 'ARCHIVO_ERRORES', carpeta / 'e.log')):
            funcion()
        return [(e.origen, e.mensaje) for e in r._lista if e.nivel == 'error']
    finally:
        r._lista.clear()
        r._lista.extend(antes)


@caso('Datos del usuario')
def preferencias_que_no_se_guardan_lo_dice_el_registro():
    """guardar_prefs devolvía False (archivo bloqueado, disco lleno) y nadie lo miraba: los ajustes volvían atrás al reiniciar sin explicación."""
    import archivos_seguros
    with parches((archivos_seguros, 'mezclar_json', lambda *a, **k: False)):
        if hasattr(ajustes_ui, '_PREFS_FALLO_DICHO'):
            ajustes_ui._PREFS_FALLO_DICHO[0] = False
        errores = _errores_del_registro(lambda: (ajustes_ui.guardar_prefs({'pagina': 'inicio'}), ajustes_ui.guardar_prefs({'pagina': 'sfx'})))
    esperar(len(errores) == 1, f'errores en el Registro: {errores} (uno solo, aunque falle dos veces)')


@caso('Datos del usuario')
def go_sin_emojis_ni_sonidos_lo_dice_el_registro():
    """Un fallo al preparar los emojis o los sonidos de GO devolvía {} en silencio: GO salía sin ellos y el Registro no decía nada."""
    M = principal()
    import emojis
    import sfx_rules
    falso = types.SimpleNamespace(msg_queue=__import__('queue').Queue(), _un_clic=False, plantilla_sel='', video_var=types.SimpleNamespace(get=lambda: ''))

    def roto(*a, **k):
        raise KeyError('fallo de prueba de los emojis')

    def roto_sfx(*a, **k):                          # (otro texto: el Registro junta en una línea el MISMO mensaje repetido en < 4 s)
        raise KeyError('fallo de prueba de los sonidos')
    with parches((emojis, 'asignar', roto), (sfx_rules, 'cargar_reglas', roto_sfx)):
        errores = _errores_del_registro(lambda: (M.SubtitleApp._preparar_emojis(falso, [{'texto': 'hola'}], []),
                                                 M.SubtitleApp._preparar_sfx(falso, [{'texto': 'hola'}])))
    origenes = sorted(o for o, _m in errores)
    esperar(origenes == ['GO · emojis', 'GO · sonidos'], f'errores en el Registro: {errores}')


@caso('Datos del usuario')
def free_sin_sidecar_nuevo_no_usa_el_viejo():
    """Resolve Free 21.1 (sin `io`) solo lee el sidecar «.json.lua»: si no se podía escribir (el antivirus lo tenía abierto), el fallo se tragaba
    y quedaba el del GO ANTERIOR, que Resolve colocaba sin que nadie se enterara."""
    import archivos_seguros
    import registro
    import sidecar_lua
    carpeta = pathlib.Path(tempfile.mkdtemp(prefix='cc_sidecar_'))
    manifiesto = carpeta / 'subtitles_manifest.json'
    for s in sidecar_lua.rutas_sidecar(manifiesto):
        s.write_text('return {video = "VIDEO_ANTERIOR"}\n', encoding='utf-8')
    real = archivos_seguros.escribir_texto

    def bloqueado(ruta, *a, **k):
        if str(ruta).endswith('.lua'):
            raise PermissionError(13, 'El proceso no tiene acceso al archivo porque está siendo utilizado por otro proceso', str(ruta))
        return real(ruta, *a, **k)
    r = registro.registro()
    antes = list(r._lista)
    r._lista.clear()
    try:
        with parches((archivos_seguros, 'escribir_texto', bloqueado), (resolve_mcp, 'ruta_exe', lambda: None), (registro, 'CARPETA', carpeta),
                     (registro, 'ARCHIVO', carpeta / 'c.log'), (registro, 'ARCHIVO_ERRORES', carpeta / 'e.log')):
            ok = sidecar_lua.escribir_sidecar(manifiesto, {'video': 'VIDEO_NUEVO'})
        errores = [e.mensaje for e in r._lista if e.nivel == 'error']
    finally:
        r._lista.clear()
        r._lista.extend(antes)
    viejos = [s.name for s in sidecar_lua.rutas_sidecar(manifiesto) if s.exists() and 'VIDEO_ANTERIOR' in s.read_text(encoding='utf-8')]
    esperar(ok is False and not viejos and errores, f'devolvió {ok!r} · siguen los del GO anterior: {viejos} · errores en el Registro: {errores}')


# ---------------------------------------------------------------------------------------------------------------------------------------
# Scripts de Resolve y packs (auditoría 5.85)
# ---------------------------------------------------------------------------------------------------------------------------------------
def _codigo_de(ruta, nombres):
    """Las funciones y asignaciones `nombres` de un archivo (también funciones anidadas), ejecutadas aparte: para probar los scripts de
    Resolve sin Resolve."""
    import ast
    arbol = ast.parse(pathlib.Path(ruta).read_text(encoding='utf-8'))
    trozos = [n for n in ast.walk(arbol) if (isinstance(n, ast.FunctionDef) and n.name in nombres)
              or (isinstance(n, ast.Assign) and n in arbol.body and any(getattr(t, 'id', '') in nombres for t in n.targets))]
    ns = {'Path': pathlib.Path}
    exec(compile(ast.Module(body=trozos, type_ignores=[]), str(ruta), 'exec'), ns)
    return ns


@caso('Scripts de Resolve y packs')
def agrandar_con_un_fallo_no_deja_la_palabra_al_cuadrado():
    """Studio, palabra grande del estilo «guion» con zoom 2: si una herramienta del macro fallaba DESPUÉS de agrandar RestingSize, la función
    devolvía False y quien llama ponía además ZoomX = 2 (la palabra a ×4). El .lua (su gemelo) da por hecho el tamaño y sigue."""
    ns = _codigo_de(os.path.join(RAIZ, '2_recursos', 'resolve_scripts', 'CineCaptions.py'), ('AGRANDAR_LUXE', 'agrandar_sin_zoom'))

    class Herramienta:
        def __init__(self, **v):
            self.v = v

        def GetInput(self, e):
            return self.v.get(e)

        def SetInput(self, e, x):
            self.v[e] = x
    tam = Herramienta(RestingSize=0.1, StartSize=0.1, EndSize=0.1)

    class Comp:
        def FindTool(self, nombre):
            if nombre == 'glow1':
                raise RuntimeError('FindTool falló')
            return tam if nombre == 'sizeCtrl' else None
    item = types.SimpleNamespace(GetFusionCompByIndex=lambda i: Comp())
    hecho = ns['agrandar_sin_zoom'](item, 2.0)
    esperar(hecho is True and abs(tam.v['RestingSize'] - 0.2) < 1e-9, f'devolvió {hecho} con RestingSize {tam.v["RestingSize"]} (×2 ya hecho)')


@caso('Scripts de Resolve y packs')
def informe_lee_bien_la_version_del_puente():
    """instalacion_scripts.txt y el diagnóstico del Puente decían «sin_lectura (del programa v5.84)»: tomaban la primera línea con VERSION y
    comillas, que es un comentario del Puente."""
    ns = _codigo_de(os.path.join(CODIGO, 'instalador_scripts.py'), ('_version_del_puente_en',))
    texto = pathlib.Path(RAIZ, '2_recursos', 'resolve_scripts', 'CineCaptions_Puente.lua').read_text(encoding='utf-8')
    version = re.search(r'^local VERSION = "([^"]+)"', texto, re.M).group(1)
    leida = ns['_version_del_puente_en'](pathlib.Path(RAIZ, '2_recursos', 'resolve_scripts'))
    esperar(leida.startswith(version + ' '), f'leyó «{leida}» (el Puente es la {version})')


@caso('Scripts de Resolve y packs')
def gemelos_emoji_solo_con_la_caja_de_dos_valores():
    """El emoji de un bloque se pone encima o debajo de su caja (arriba, abajo). El .py (Studio) solo usa la caja si tiene 2 valores; el .lua
    (Free) también con la de 4 de la línea de los Estilos 3 y 7: tomaba x0 por «arriba» y el emoji salía lejos de su línea."""
    carpeta = pathlib.Path(RAIZ, '2_recursos', 'resolve_scripts')
    py = len(re.findall(r'isinstance\(caja, \(list, tuple\)\) and len\(caja\) == 2', (carpeta / 'CineCaptions.py').read_text(encoding='utf-8')))
    lua_texto = (carpeta / 'CineCaptions_Subtitulos.lua').read_text(encoding='utf-8')
    lua_bien = len(re.findall(r'type\(caja\) == "table" and #caja == 2 and tonumber\(caja\[1\]\)', lua_texto))
    lua_todos = len(re.findall(r'type\(caja\) == "table" and .*tonumber\(caja\[1\]\) and tonumber\(caja\[2\]\)', lua_texto))
    esperar(py >= 2 and lua_bien == lua_todos == py, f'.py comprueba 2 valores en {py} sitios; .lua en {lua_bien} de {lua_todos}')


@caso('Scripts de Resolve y packs')
def todo_pack_de_fabrica_tiene_revision_del_bin():
    """Sin revisión, un pack cambiado no se vuelve a importar en los proyectos que ya tienen su bin («Base títulos dinámicos» no la tenía)."""
    import plantillas
    faltan = sorted({p.nombre for p in plantillas.packs_incorporados() if p.incorporado} - set(plantillas.REVISION_BIN))
    esperar(not faltan, f'packs de fábrica sin REVISION_BIN: {faltan}')


# ---------------------------------------------------------------------------------------------------------------------------------------
# Arranque seguro (v5.85, Mac «no abre»): hijos de librerías que no reabren el programa, copias atascadas que se quitan, arranque con tope
# ---------------------------------------------------------------------------------------------------------------------------------------
_HIJO_CONGELADO = r'''
import sys, runpy
sys.frozen = True
sys.argv = ARGV
sys.path.insert(0, CODIGO)
import multiprocessing.resource_tracker as rt
rt.main = lambda fd: print('TRACKER', fd, flush=True)       # el resource_tracker de verdad: aquí solo dice que lo llamaron
try:
    runpy.run_path(SCRIPT, run_name='__main__')
    print('SIGUIO', flush=True)
except SystemExit as e:
    print('SALIDA', e.code, 'Qt' if 'PySide6.QtWidgets' in sys.modules else 'sin Qt', flush=True)
'''


def _como_hijo_congelado(argv, casa):
    """Corre el script principal como el .exe/.app congelado (sys.frozen) con `argv`, con HOME en `casa`. → (segundos, salida)."""
    codigo = (_HIJO_CONGELADO.replace('ARGV', repr(argv)).replace('CODIGO', repr(CODIGO))
              .replace('SCRIPT', repr(os.path.join(CODIGO, 'CineCaptions (script principal).py'))))
    entorno = dict(os.environ, HOME=casa, USERPROFILE=casa, QT_QPA_PLATFORM='offscreen')
    t0 = time.time()
    p = subprocess.run([sys.executable, '-c', codigo], capture_output=True, text=True, timeout=120, env=entorno, cwd=casa,
                       encoding='utf-8', errors='replace')
    return time.time() - t0, (p.stdout + p.stderr).strip()


@caso('Arranque seguro')
def hijo_de_libreria_no_reabre_el_programa():
    """El .exe/.app lanzado como Python por una librería («-B -S -I -c …»: el resource_tracker de multiprocessing, que en la 5.84 abría
    CineCaptions invisible y con el candado) corre SOLO su código y sale, sin Qt, sin candado y sin marca de sesión. Un arranque normal sigue."""
    casa = tempfile.mkdtemp(prefix='cc_hijo_')
    marca = os.path.join(casa, 'hijo.txt')
    pruebas = [
        (['CineCaptions', '-B', '-S', '-I', '-c', 'from multiprocessing.resource_tracker import main;main(9)'], 'TRACKER 9'),
        (['CineCaptions', '-B', '-S', '-I', '-c', "import sys; open(sys.argv[1], 'w').write('ok')", marca], 'SALIDA 0 sin Qt'),
        (['CineCaptions', '-I', '-m', 'platform'], 'SALIDA 0 sin Qt'),
    ]
    for argv, espera in pruebas:
        tarda, salida = _como_hijo_congelado(argv, casa)
        esperar(espera in salida and 'SALIDA 0 sin Qt' in salida and tarda < 30, f'{argv[1:]}: {tarda:.1f} s · {salida[-300:]}')
    esperar(open(marca).read() == 'ok', 'el hijo «-c» no corrió su código con sus argumentos')
    for resto in ('.cinecaptions.lock', 'DaVinciSubtitles'):
        esperar(not os.path.exists(os.path.join(casa, resto)), f'un hijo dejó {resto}: arrancó parte del programa')
    # un arranque normal (una --tarea desconocida) no lo corta la guardia: llega a tareas_instalador
    estado = os.path.join(casa, 'estado.txt')
    _, salida = _como_hijo_congelado(['CineCaptions', '--tarea', 'no_existe', estado], casa)
    esperar('Tarea desconocida' in (open(estado, encoding='utf-8').read() if os.path.exists(estado) else ''), f'--tarea: {salida[-300:]}')
    fuente = open(os.path.join(CODIGO, 'CineCaptions (script principal).py'), encoding='utf-8').read()
    esperar(fuente.index('arranque_seguro.atender_hijo()') < fuente.index('import datetime'), 'la guardia debe ir antes de cargar el programa')


@caso('Arranque seguro')
def como_interprete_solo_reconoce_hijos():
    import arranque_seguro as A
    si = [['x', '-c', 'print(1)'], ['x', '-B', '-S', '-I', '-c', 'c', 'a'], ['x', '-X', 'utf8', '-m', 'mod'], ['x', '-OO', '-m', 'm']]
    no = [['x'], ['x', 'C:/videos/a.mp4'], ['x', '--tarea', 'verificar', 'e.txt'], ['x', '--reinicio'], ['x', '-psn_0_123'],
          ['x', '-c'], ['x', 'video -c.mp4'], ['x', '--multiprocessing-fork', 'pipe_handle=5']]
    malos = [a for a in si if A.como_interprete(a) is None] + [a for a in no if A.como_interprete(a) is not None]
    esperar(not malos, f'mal reconocidos: {malos}')
    esperar(A.como_interprete(['x', '-B', '-c', 'c', 'a', 'b']) == ('-c', 'c', ['a', 'b']), 'el resto de argumentos se pierde')


@caso('Arranque seguro')
def copia_atascada_solo_si_lo_esta():
    """Se cierra la copia del candado SOLO si es un hijo de librería o lleva minutos «abriendo» fuera de la licencia; ante la duda, nunca."""
    import arranque_seguro as A
    exe = '/Applications/CineCaptions.app/Contents/MacOS/CineCaptions'
    ahora = 10_000.0
    tracker = {'exe': exe, 'cmd': exe + ' -B -S -I -c from multiprocessing.resource_tracker import main;main(9)', 'edad': 30}
    normal = {'exe': exe, 'cmd': exe, 'edad': 600}
    con_video = {'exe': exe, 'cmd': exe + ' /Users/x/mi -c video.mp4', 'edad': 600}
    ajeno = {'exe': '/usr/bin/python3', 'cmd': '/usr/bin/python3 -c pass', 'edad': 600}
    casos = [
        ('hijo de librería', tracker, None, True),
        ('abriendo 6 min', normal, (ahora - 360, 'abriendo · creando la ventana'), True),
        ('abriendo 1 min', normal, (ahora - 60, 'abriendo · creando la ventana'), False),
        ('en la licencia 20 min', normal, (ahora - 1200, 'abriendo · ventana de licencia'), False),
        ('abierta y lista', normal, (ahora - 3600, 'listo'), False),
        ('marca de una sesión vieja', dict(normal, edad=30), (ahora - 3600, 'abriendo · antes de la ventana'), False),
        ('video con « -c » en el nombre', con_video, (ahora - 3600, 'listo'), False),
        ('otro programa', ajeno, (ahora - 3600, 'abriendo'), False),
        ('sin datos del proceso', None, (ahora - 3600, 'abriendo'), False),
    ]
    malos = []
    for nombre, info, marca, debe in casos:
        r = A.copia_atascada(999_999, info=info or {}, marca=marca or (ahora, 'listo'), ahora=ahora, ejecutable=exe)
        if bool(r) != debe:
            malos.append(f'{nombre}: {r!r}')
    esperar(not malos, '; '.join(malos))
    esperar(A._edad_ps('1-02:03:04') == 93784 and A._edad_ps(' 05:06') == 306, 'etime de ps mal leído')
    yo = A.info_proceso(os.getpid())
    esperar(yo is not None and yo.get('edad') is not None and yo['edad'] >= 0, f'info del propio proceso: {yo}')


@caso('Arranque seguro')
def candado_ocupado_por_copia_atascada_se_libera():
    """Otra copia con el candado de una sola ventana y atascada: se cierra y esta abre (antes: «ya se encuentra en ejecución» hasta reiniciar).
    Si la copia está bien, sigue viva y esta solo la trae al frente."""
    import arranque_seguro as A
    M = principal()
    casa = tempfile.mkdtemp(prefix='cc_candado_')
    candado = os.path.join(casa, '.cinecaptions.lock')
    tomar = ('import msvcrt, os, time\nf = open(r"%s", "w+")\nmsvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)\n' if sys.platform.startswith('win')
             else 'import fcntl, os, time\nf = open(r"%s", "w+")\nfcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)\n') % candado
    tomar += ('f.write(str(os.getpid())); f.flush()\nopen(r"%s", "w").write(str(os.getpid()))\nprint("tengo", flush=True)\ntime.sleep(120)\n'
              % os.path.join(casa, '.cinecaptions.pid'))
    vieja_home = pathlib.Path.__dict__.get('home')
    viejos = (A.es_cinecaptions, A.leer_marca, A.TOPE_ABRIENDO_S, M._traer_instancia_existente_al_frente)
    resultado = {}
    try:
        pathlib.Path.home = classmethod(lambda cls: pathlib.Path(casa))
        A.es_cinecaptions = lambda info, ejecutable=None: bool(info)
        A.TOPE_ABRIENDO_S = 1
        M._traer_instancia_existente_al_frente = lambda pid=None: None
        for estado, debe_abrir in (('listo', False), ('abriendo · creando la ventana', True)):
            dueno = subprocess.Popen([sys.executable, '-c', tomar], stdout=subprocess.PIPE, text=True)
            try:
                esperar(dueno.stdout.readline().strip() == 'tengo', 'el proceso de prueba no tomó el candado')
                time.sleep(3)
                A.leer_marca = lambda ruta=None, e=estado: (time.time() - 2, e)
                M._NOTAS_ARRANQUE.clear()
                abrio = M._asegurar_instancia_unica()
                try:                                      # (el python.exe de un venv es un lanzador: termina un instante después del de verdad)
                    dueno.wait(3)
                except subprocess.TimeoutExpired:
                    pass
                vivo = dueno.poll() is None
                resultado[estado] = (abrio, vivo, list(M._NOTAS_ARRANQUE))
            finally:
                if M._SINGLE_INSTANCE_LOCK is not None:
                    M._SINGLE_INSTANCE_LOCK.close()
                    M._SINGLE_INSTANCE_LOCK = None
                if dueno.poll() is None:
                    dueno.kill()
                dueno.wait(10)
    finally:
        if vieja_home is not None:
            pathlib.Path.home = vieja_home
        else:
            del pathlib.Path.home
        A.es_cinecaptions, A.leer_marca, A.TOPE_ABRIENDO_S, M._traer_instancia_existente_al_frente = viejos
        M._NOTAS_ARRANQUE.clear()
    abrio, vivo, notas = resultado.get('listo', (None, None, None))
    esperar(abrio is False and vivo is True and not notas, f'con una copia que funciona: {resultado.get("listo")}')
    abrio, vivo, notas = resultado.get('abriendo · creando la ventana', (None, None, None))
    esperar(abrio is True and vivo is False and notas and 'atascada' in notas[0], f'con una copia atascada: {resultado.get("abriendo · creando la ventana")}')


_ARRANQUE_COLGADO = r'''
import os, sys, threading, time
sys.path.insert(0, __CODIGO__)
from pathlib import Path
import registro, vigilancia
c = Path(__CARPETA__)
registro.CARPETA, registro.ARCHIVO, registro.ARCHIVO_ERRORES = c, c / "c.log", c / "e.log"
vigilancia.CARPETA = c
vigilancia.ARRANQUE_SIN_PULSO_S = 1.5
registro._PULSO_UI['t'] = time.time()
if __LATE__:                                 # una interfaz viva (p. ej. un diálogo esperando al usuario) sigue latiendo
    def latir():
        while True:
            registro._PULSO_UI['t'] = time.time(); time.sleep(0.2)
    threading.Thread(target=latir, daemon=True).start()
vigilancia.vigilar_arranque(45, tope_s=1.0)
time.sleep(9)
print("sigue vivo", flush=True)
os._exit(0)
'''


@caso('Arranque seguro')
def arranque_atascado_se_cierra_solo():
    """Sin ventana pasado el tope y con la interfaz sin latir: se anota, la marca lo dice y el proceso sale (suelta el candado). Con la
    interfaz latiendo (un diálogo esperando al usuario) no se toca."""
    resultados = {}
    for late in (False, True):
        carpeta = tempfile.mkdtemp(prefix='cc_arranque_')
        codigo = _ARRANQUE_COLGADO.replace('__CODIGO__', repr(CODIGO)).replace('__CARPETA__', repr(carpeta)).replace('__LATE__', repr(late))
        p = subprocess.run([sys.executable, '-c', codigo], capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace')
        try:
            marca = open(os.path.join(carpeta, 'sesion_abierta.flag'), encoding='utf-8').read()
        except OSError:
            marca = ''
        try:
            errores = open(os.path.join(carpeta, 'e.log'), encoding='utf-8', errors='replace').read()
        except OSError:
            errores = ''
        resultados[late] = (p.returncode, (p.stdout + p.stderr).strip()[-200:], marca, 'no terminó de abrir' in errores)
    codigo, salida, marca, anotado = resultados[False]
    esperar(codigo == 3 and 'sigue vivo' not in salida and 'cortado' in marca and anotado, f'atascado: {resultados[False]}')
    codigo, salida, marca, anotado = resultados[True]
    esperar(codigo == 0 and 'sigue vivo' in salida and 'cortado' not in marca, f'interfaz latiendo: {resultados[True]}')
    fuente = open(os.path.join(CODIGO, 'CineCaptions (script principal).py'), encoding='utf-8').read()
    esperar('vigilar_arranque(45, tope_s=' in fuente, 'main() no pone el tope del arranque')
    esperar("_marcar_sesion('abriendo · ventana de licencia')" in fuente, 'la ventana de licencia no se marca (contaría como atascada)')


@caso('Arranque seguro')
def postinstall_mac_limpia_y_pone_topes():
    """El postinstall quita los hijos huérfanos de la 5.84 (antes y después de las tareas) y ninguna tarea puede colgar el instalador."""
    texto = open(os.path.join(RAIZ, '7_mac', 'pkg', 'scripts', 'postinstall'), encoding='utf-8').read()
    esperar('\r' not in texto, 'postinstall con CRLF: bash no lo corre en la Mac')
    esperar(texto.count('limpiar_huerfanos') >= 3, 'falta limpiar_huerfanos antes o después de las tareas')
    esperar('pgrep -P 1 -f' in texto and 'con_tope "$TOPE"' in texto, 'faltan la limpieza de huérfanos o el tope por tarea')


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
