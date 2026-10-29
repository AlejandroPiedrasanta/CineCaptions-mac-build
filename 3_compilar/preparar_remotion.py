# CineCaptions · By Cinema Productions
# 3_compilar/preparar_remotion.py — deja Remotion listo para el instalador (lo llama Actualizar_Windows.ps1 antes de compilar):
#   1. empaqueta las animaciones (1_codigo/remotion → 2_recursos/edicion_pro/remotion/bundle);
#   2. arma 2_recursos/edicion_pro/remotion/runtime: node(.exe) de este equipo, render.mjs/galeria.mjs y SOLO lo necesario para renderizar
#      (@remotion/renderer con su compositor nativo, remotion, react) con `npm install --omit=dev`;
#   3. copia un Chrome sin ventana (chrome-headless-shell): v5.53, el CHROME de Chrome for Testing (la versión con la que prueba Remotion)
#      para ESTA plataforma, bajado de Google; si no se puede, el que baja Remotion (ensureBrowser) o el de Playwright de este equipo.
# En la Mac de GitHub no están las dependencias de desarrollo (1_codigo/remotion/node_modules): usa el bundle ya hecho en Windows (viaja en
# el espejo; es igual en todas las plataformas).
# v5.53: el Node es, por orden, CINECAPTIONS_NODE, 6_compilacion/node26 (herramienta de compilación, fuera de Git) o el del sistema; npm, el
# de esa misma carpeta.
# Lo que ya está y no cambió no se rehace (versiones en runtime/version.json). Uso: python 3_compilar/preparar_remotion.py [--forzar]
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / '1_codigo' / 'remotion'
DEST = RAIZ / '2_recursos' / 'edicion_pro' / 'remotion'
RT = DEST / 'runtime'
WIN = sys.platform == 'win32'
CHROME = '157.0.8080.0'          # v5.53: la TESTED_VERSION de Remotion 4.0.539 (antes, el 156.0.8078.4 de Playwright)
CFT = 'https://storage.googleapis.com/chrome-for-testing-public'


def _node():
    """v5.53: el Node con el que se arma todo y que viaja en runtime/ (CINECAPTIONS_NODE > 6_compilacion/node26 > el del sistema)."""
    pedido = os.environ.get('CINECAPTIONS_NODE')
    if pedido and Path(pedido).is_file():
        return str(Path(pedido))
    propio = RAIZ / '6_compilacion' / 'node26' / ('node.exe' if WIN else 'bin/node')
    if propio.is_file():
        return str(propio)
    return shutil.which('node') or 'node'


def _entorno():
    """El PATH con la carpeta de ese Node delante (npm y los scripts de instalación llaman a «node»)."""
    env = dict(os.environ)
    carpeta = os.path.dirname(_node())
    if carpeta:
        env['PATH'] = carpeta + os.pathsep + env.get('PATH', '')
    return env


def _npm():
    """npm de la misma carpeta que el Node elegido (node npm-cli.js); si no lo trae, el del sistema."""
    carpeta = Path(_node()).parent
    for cli in (carpeta / 'node_modules' / 'npm' / 'bin' / 'npm-cli.js', carpeta.parent / 'lib' / 'node_modules' / 'npm' / 'bin' / 'npm-cli.js'):
        if cli.is_file():
            return [_node(), str(cli)]
    return [shutil.which('npm.cmd' if WIN else 'npm') or 'npm']


def _versiones():
    deps = json.loads((SRC / 'package.json').read_text(encoding='utf-8')).get('dependencies') or {}
    return {k: deps[k] for k in ('@remotion/renderer', 'remotion', 'react', 'react-dom') if k in deps}


def _chrome_origen():
    nombre = 'chrome-headless-shell.exe' if WIN else 'chrome-headless-shell'
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'ms-playwright'
    if sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Caches' / 'ms-playwright'
    for p in sorted(base.glob('chromium_headless_shell-*/*/' + nombre), reverse=True) if base.is_dir() else []:
        return p.parent
    return None


def _chrome_remotion():
    """El chrome-headless-shell que baja Remotion para esta plataforma (queda en runtime/node_modules/.remotion): su carpeta o None."""
    nombre = 'chrome-headless-shell.exe' if WIN else 'chrome-headless-shell'
    r = subprocess.run([_node(), '--input-type=module', '-e',
                        "import {ensureBrowser} from '@remotion/renderer'; await ensureBrowser({logLevel: 'error'}); console.log('ok')"],
                       cwd=RT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900, env=_entorno())
    if r.returncode != 0:
        print('  AVISO: Remotion no pudo bajar Chrome:', (r.stderr or r.stdout)[-400:])
    cache = RT / 'node_modules' / '.remotion'
    for p in cache.rglob(nombre) if cache.is_dir() else []:
        if p.is_file():
            return p.parent
    return None


def _plataforma_cft():
    if WIN:
        return 'win64'
    if sys.platform == 'darwin':
        return 'mac-arm64' if platform.machine() == 'arm64' else 'mac-x64'
    return 'linux64'


def _chrome_cft(tmp):
    """v5.53: baja el chrome-headless-shell CHROME de Chrome for Testing (Google) para esta plataforma y lo descomprime en tmp: su carpeta o
    None. En la Mac también: el que baja Remotion allí (remotion.media) se queda esperando en macOS 26 (issue #12633) y el de Google no."""
    plat = _plataforma_cft()
    url = f'{CFT}/{CHROME}/{plat}/chrome-headless-shell-{plat}.zip'
    z = Path(tmp) / 'chrome.zip'
    x = Path(tmp) / 'x'
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(z, 'wb') as f:
            shutil.copyfileobj(r, f, 1 << 20)
        if not WIN and shutil.which('unzip'):                       # conserva los permisos de ejecución (zipfile los pierde)
            subprocess.run(['unzip', '-q', str(z), '-d', str(x)], check=True, timeout=600)
        else:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(x)
    except (OSError, zipfile.BadZipFile, subprocess.SubprocessError) as e:
        print(f'  AVISO: no pude bajar Chrome {CHROME} ({url}): {e}')
        return None
    nombre = 'chrome-headless-shell.exe' if WIN else 'chrome-headless-shell'
    for p in x.rglob(nombre):
        if p.is_file():
            return p.parent
    return None


def _version_chrome(carpeta):
    """'157.0.8080.0' (la de chrome-headless-shell --version) o ''."""
    exe = Path(carpeta) / ('chrome-headless-shell.exe' if WIN else 'chrome-headless-shell')
    try:
        salida = subprocess.run([str(exe), '--version'], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return ''
    return next((w for w in salida.split() if w[:1].isdigit() and w.count('.') == 3), '')


def main(forzar=False):
    # 1) el bundle
    if not (SRC / 'node_modules' / '@remotion' / 'bundler').exists() and (DEST / 'bundle' / 'index.html').exists():
        print('  bundle: uso el ya empaquetado (aquí no están las dependencias de desarrollo)')
    else:
        r = subprocess.run([_node(), 'empaquetar.mjs'], cwd=SRC, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           env=_entorno())
        if r.returncode != 0 or not (DEST / 'bundle' / 'index.html').exists():
            raise SystemExit('No pude empaquetar las animaciones de Remotion:\n' + (r.stderr or r.stdout)[-1500:])
        print('  bundle listo')
    # 2) el runtime
    RT.mkdir(parents=True, exist_ok=True)
    nodo = _node()
    quiero = {'deps': _versiones(), 'node': subprocess.run([nodo, '--version'], capture_output=True, text=True).stdout.strip()}
    vf = RT / 'version.json'
    tengo = json.loads(vf.read_text(encoding='utf-8')) if vf.exists() else {}
    for f in ('render.mjs', 'galeria.mjs'):
        shutil.copy2(SRC / f, RT / f)
    if forzar or tengo.get('deps') != quiero['deps'] or not (RT / 'node_modules' / '@remotion' / 'renderer').exists():
        (RT / 'package.json').write_text(json.dumps({'name': 'cinecaptions-remotion-runtime', 'private': True, 'type': 'module',
                                                    'dependencies': quiero['deps']}, indent=1), encoding='utf-8')
        shutil.rmtree(RT / 'node_modules', ignore_errors=True)
        r = subprocess.run(_npm() + ['install', '--omit=dev', '--no-audit', '--no-fund'], cwd=RT, capture_output=True, text=True, encoding='utf-8',
                           errors='replace', env=_entorno())
        if r.returncode != 0:
            raise SystemExit('npm install del runtime falló:\n' + (r.stderr or r.stdout)[-1500:])
        shutil.rmtree(RT / 'node_modules' / '.bin', ignore_errors=True)       # enlaces simbólicos que no hacen falta (y estorban al empaquetar)
        print('  dependencias del renderizador instaladas')
    destino_node = RT / ('node.exe' if WIN else 'node')
    if Path(nodo).is_file() and (forzar or tengo.get('node') != quiero['node'] or not destino_node.exists()):
        shutil.copy2(nodo, destino_node)
        print('  node', quiero['node'], 'de', nodo)
    # 3) Chrome sin ventana. v5.53: se rehace también cuando cambia CHROME (version.json guarda la copiada; antes solo si faltaba)
    hay = (RT / 'chrome').exists() and any((RT / 'chrome').rglob('chrome-headless-shell*'))
    quiero['chrome'] = tengo.get('chrome', '') if hay else ''
    if forzar or not hay or quiero['chrome'] != CHROME:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            org = _chrome_cft(tmp)
            if org is None and (forzar or not hay):
                org = _chrome_remotion() or _chrome_origen()
            if org is None:
                if not hay:
                    print('  AVISO: no encontré chrome-headless-shell en este equipo: Remotion lo descargará la primera vez en el PC del usuario')
            else:
                version = _version_chrome(org)
                shutil.rmtree(RT / 'chrome', ignore_errors=True)
                shutil.copytree(org, RT / 'chrome' / org.name, ignore=shutil.ignore_patterns('chrome_debug.log'))
                quiero['chrome'] = version
                print('  chrome-headless-shell', version or '?', 'copiado de', org)
    # la descarga de ensureBrowser ya está copiada en runtime/chrome: sin esto el instalador llevaría Chrome dos veces
    shutil.rmtree(RT / 'node_modules' / '.remotion', ignore_errors=True)
    vf.write_text(json.dumps(quiero, indent=1), encoding='utf-8')
    tam = sum(f.stat().st_size for f in DEST.rglob('*') if f.is_file()) / 1e6
    print(f'  Remotion listo para el instalador ({tam:.0f} MB)')


if __name__ == '__main__':
    main('--forzar' in sys.argv)
