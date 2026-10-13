# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_remotion.py — las animaciones de la Edición PRO hechas con Remotion (React), renderizadas en el PC del usuario.
"""
Remotion corre con Node y un Chrome sin ventana. El proyecto está en 1_codigo/remotion (src/*.tsx); `node empaquetar.mjs` lo deja empaquetado en
2_recursos/edicion_pro/remotion/bundle (va en el instalador). Aquí:

    disponible()                         -> ¿hay Node, el renderizador y el bundle?
    renderizar(trabajos, al_estado)      -> {salida: True/False}: [{'id': composición, 'props': {...}, 'salida': .mov}] en UNA llamada a node
                                            (un solo navegador para todo). Cada uno sale en ProRes 4444 con alfa. Caché: si la salida existe, no
                                            se vuelve a renderizar (el nombre lleva el hash de las props).
    salida_para(id, props, carpeta)      -> la ruta .mov de esas props (hash)

Dónde busca cada cosa (primero lo del instalador, luego lo de desarrollo):
    node      2_recursos/edicion_pro/remotion/runtime/node(.exe)  ·  node del sistema
    render    2_recursos/edicion_pro/remotion/runtime/render.mjs (con su node_modules)  ·  1_codigo/remotion/render.mjs
    chrome    2_recursos/edicion_pro/remotion/runtime/chrome/…/chrome-headless-shell(.exe)  ·  Playwright (%LOCALAPPDATA%/ms-playwright)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def _recursos() -> Path:
    try:
        from sfx_rules import base_recursos
        return Path(base_recursos()) / 'edicion_pro' / 'remotion'
    except Exception:
        return AQUI.parent / '2_recursos' / 'edicion_pro' / 'remotion'


def bundle() -> Path:
    return _recursos() / 'bundle'


def _node():
    rt = _recursos() / 'runtime' / ('node.exe' if sys.platform == 'win32' else 'node')
    if rt.exists():
        return str(rt)
    return shutil.which('node')


def _render_mjs():
    for p in (_recursos() / 'runtime' / 'render.mjs', AQUI / 'remotion' / 'render.mjs'):
        if p.exists():
            return p
    return None


def _chrome():
    nombre = 'chrome-headless-shell.exe' if sys.platform == 'win32' else 'chrome-headless-shell'
    rt = _recursos() / 'runtime' / 'chrome'
    if rt.is_dir():
        for p in rt.rglob(nombre):
            return str(p)
    pw = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'ms-playwright'
    if sys.platform == 'darwin':
        pw = Path.home() / 'Library' / 'Caches' / 'ms-playwright'
    if pw.is_dir():
        for p in sorted(pw.glob('chromium_headless_shell-*/**/' + nombre), reverse=True):
            return str(p)
    return ''                                                         # Remotion usa (o descarga) el suyo


def disponible() -> bool:
    return bool(_node() and _render_mjs() and (bundle() / 'index.html').exists())


def _permisos():
    """Mac/Linux: node, Chrome y el compositor de Remotion (con su ffmpeg) tienen que poder ejecutarse (una copia puede perder el bit +x)."""
    if sys.platform == 'win32':
        return
    rt = _recursos() / 'runtime'
    candidatos = [Path(_node() or ''), Path(_chrome() or '')]
    candidatos += [p for p in (rt / 'node_modules' / '@remotion').glob('compositor-*/*') if p.is_file() and not p.suffix]
    for p in candidatos:
        try:
            if p.is_file() and not os.access(p, os.X_OK):
                p.chmod(p.stat().st_mode | 0o111)
        except OSError:
            pass


def comprobar(renderizar_prueba=False) -> str:
    """Para la autoprueba del instalador: '' si todo está, o qué falla. Con renderizar_prueba hace un render real de 1 s (Node + Chrome +
    compositor)."""
    if not disponible():
        return 'falta Node, render.mjs o el bundle'
    _permisos()
    try:
        v = subprocess.run([_node(), '--version'], capture_output=True, text=True, timeout=60,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return f'node no arranca: {e}'
    if not v.startswith('v'):
        return 'node no arranca'
    if not renderizar_prueba:
        return ''
    with tempfile.TemporaryDirectory() as tmp:
        props = {'texto': 'CineCaptions', 'estilo': 'dorado', '_ancho': 360, '_alto': 640, '_fps': 30, '_dur': 1.0}
        sal = salida_para('Pastilla', props, tmp)
        ok = renderizar([{'id': 'Pastilla', 'props': props, 'salida': sal}], timeout=300).get(str(sal))
        return '' if ok else 'el render de prueba no salió'


def salida_para(ident, props, carpeta) -> Path:
    h = hashlib.sha1(json.dumps([ident, props], sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:12]
    return Path(carpeta) / f'rm_{ident}_{h}.mov'


def renderizar(trabajos, al_estado=None, timeout=900):
    """Renderiza los que falten. Devuelve {ruta de salida: ok}."""
    hechos = {str(t['salida']): Path(t['salida']).exists() and Path(t['salida']).stat().st_size > 10000 for t in trabajos}
    pendientes = [t for t in trabajos if not hechos[str(t['salida'])]]
    if not pendientes or not disponible():
        return hechos
    if al_estado:
        al_estado(f'Edición PRO: animando con Remotion ({len(pendientes)})…')
    _permisos()
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'bundle': str(bundle()), 'navegador': _chrome(), 'trabajos': [{**t, 'salida': str(t['salida'])} for t in pendientes]}, f, ensure_ascii=False)
        ruta = f.name
    try:
        mjs = _render_mjs()
        p = subprocess.run([_node(), str(mjs), ruta], cwd=str(mjs.parent), capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for linea in p.stdout.splitlines():
            try:
                r = json.loads(linea)
            except ValueError:
                continue
            if r.get('hecho'):
                hechos[str(Path(r['hecho']))] = True
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass
    for t in pendientes:                                              # lo que haya quedado en disco cuenta
        s = str(t['salida'])
        hechos[s] = hechos.get(s) or (Path(s).exists() and Path(s).stat().st_size > 10000)
    return hechos
