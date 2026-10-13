# CineCaptions · By Cinema Productions
# 3_compilar/preparar_remotion.py — deja Remotion listo para el instalador (lo llama Actualizar_Windows.ps1 antes de compilar):
#   1. empaqueta las animaciones (1_codigo/remotion → 2_recursos/edicion_pro/remotion/bundle);
#   2. arma 2_recursos/edicion_pro/remotion/runtime: node(.exe) de este equipo, render.mjs/galeria.mjs y SOLO lo necesario para renderizar
#      (@remotion/renderer con su compositor nativo, remotion, react) con `npm install --omit=dev`;
#   3. copia un Chrome sin ventana (chrome-headless-shell): el de Playwright de este equipo o, si no hay (la Mac de GitHub), el que baja
#      Remotion (ensureBrowser) para ESTA plataforma.
# En la Mac de GitHub no están las dependencias de desarrollo (1_codigo/remotion/node_modules): usa el bundle ya hecho en Windows (viaja en
# el espejo; es igual en todas las plataformas).
# Lo que ya está y no cambió no se rehace (versiones en runtime/version.json). Uso: python 3_compilar/preparar_remotion.py [--forzar]
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / '1_codigo' / 'remotion'
DEST = RAIZ / '2_recursos' / 'edicion_pro' / 'remotion'
RT = DEST / 'runtime'
WIN = sys.platform == 'win32'


def _npm():
    return shutil.which('npm.cmd' if WIN else 'npm') or 'npm'


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
    r = subprocess.run([shutil.which('node') or 'node', '--input-type=module', '-e',
                        "import {ensureBrowser} from '@remotion/renderer'; await ensureBrowser({logLevel: 'error'}); console.log('ok')"],
                       cwd=RT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
    if r.returncode != 0:
        print('  AVISO: Remotion no pudo bajar Chrome:', (r.stderr or r.stdout)[-400:])
    cache = RT / 'node_modules' / '.remotion'
    for p in cache.rglob(nombre) if cache.is_dir() else []:
        if p.is_file():
            return p.parent
    return None


def main(forzar=False):
    # 1) el bundle
    if not (SRC / 'node_modules' / '@remotion' / 'bundler').exists() and (DEST / 'bundle' / 'index.html').exists():
        print('  bundle: uso el ya empaquetado (aquí no están las dependencias de desarrollo)')
    else:
        r = subprocess.run(['node', 'empaquetar.mjs'], cwd=SRC, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode != 0 or not (DEST / 'bundle' / 'index.html').exists():
            raise SystemExit('No pude empaquetar las animaciones de Remotion:\n' + (r.stderr or r.stdout)[-1500:])
        print('  bundle listo')
    # 2) el runtime
    RT.mkdir(parents=True, exist_ok=True)
    quiero = {'deps': _versiones(), 'node': subprocess.run(['node', '--version'], capture_output=True, text=True).stdout.strip()}
    vf = RT / 'version.json'
    tengo = json.loads(vf.read_text(encoding='utf-8')) if vf.exists() else {}
    for f in ('render.mjs', 'galeria.mjs'):
        shutil.copy2(SRC / f, RT / f)
    if forzar or tengo.get('deps') != quiero['deps'] or not (RT / 'node_modules' / '@remotion' / 'renderer').exists():
        (RT / 'package.json').write_text(json.dumps({'name': 'cinecaptions-remotion-runtime', 'private': True, 'type': 'module',
                                                    'dependencies': quiero['deps']}, indent=1), encoding='utf-8')
        shutil.rmtree(RT / 'node_modules', ignore_errors=True)
        r = subprocess.run([_npm(), 'install', '--omit=dev', '--no-audit', '--no-fund'], cwd=RT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode != 0:
            raise SystemExit('npm install del runtime falló:\n' + (r.stderr or r.stdout)[-1500:])
        shutil.rmtree(RT / 'node_modules' / '.bin', ignore_errors=True)       # enlaces simbólicos que no hacen falta (y estorban al empaquetar)
        print('  dependencias del renderizador instaladas')
    nodo = shutil.which('node')
    destino_node = RT / ('node.exe' if WIN else 'node')
    if nodo and (forzar or tengo.get('node') != quiero['node'] or not destino_node.exists()):
        shutil.copy2(nodo, destino_node)
        print('  node', quiero['node'])
    # 3) Chrome sin ventana
    if forzar or not any((RT / 'chrome').rglob('chrome-headless-shell*')) if (RT / 'chrome').exists() else True:
        org = _chrome_origen() or _chrome_remotion()
        if org is None:
            print('  AVISO: no encontré chrome-headless-shell en este equipo: Remotion lo descargará la primera vez en el PC del usuario')
        else:
            shutil.rmtree(RT / 'chrome', ignore_errors=True)
            shutil.copytree(org, RT / 'chrome' / org.name)
            print('  chrome-headless-shell copiado de', org)
    vf.write_text(json.dumps(quiero, indent=1), encoding='utf-8')
    tam = sum(f.stat().st_size for f in DEST.rglob('*') if f.is_file()) / 1e6
    print(f'  Remotion listo para el instalador ({tam:.0f} MB)')


if __name__ == '__main__':
    main('--forzar' in sys.argv)
