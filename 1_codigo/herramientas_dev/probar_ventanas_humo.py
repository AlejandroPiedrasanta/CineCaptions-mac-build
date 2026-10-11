# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_ventanas_humo.py — humo de TODAS las ventanas sin pantalla ni Resolve: crea la app, recorre sus páginas, abre cada ventana y escribe una «huella» de widgets y textos para comparar antes/después de mover código entre módulos.
"""Humo de las ventanas del programa (sin pantalla, sin Resolve, sin tocar prefs reales): crea la ventana principal, recorre sus páginas y abre cada ventana/diálogo.
Escribe una «huella» (clases de widgets y textos visibles) en el archivo dado, para comparar ANTES y DESPUÉS de mover código entre módulos.
python probar_ventanas_humo.py <salida.txt>"""
import faulthandler, importlib.util, os, sys, traceback
from collections import Counter
from pathlib import Path

AQUI = os.environ.get('HUMO_AQUI') or str(Path(__file__).resolve().parent.parent)          # 1_codigo (o la carpeta que se indique)
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['CINECAPTIONS_SIN_MCP'] = '1'
sys.path.insert(0, AQUI)
os.chdir(AQUI)
sys.stdout.reconfigure(encoding='utf-8')
salida = Path(sys.argv[1])
faulthandler.dump_traceback_later(240, exit=True)

spec = importlib.util.spec_from_file_location('cc_main', os.path.join(AQUI, 'CineCaptions (script principal).py'))
M = importlib.util.module_from_spec(spec)
sys.modules['cc_main'] = M
spec.loader.exec_module(M)
import ajustes_ui, archivos_seguros, licencia, resolve_mcp, sfx_rules
licencia.vigente = lambda: True
M.SubtitleApp._revisar_licencia_al_arrancar = lambda s: None
ajustes_ui.guardar_prefs = lambda *a, **k: None
if hasattr(ajustes_ui, 'mezclar_prefs'):
    ajustes_ui.mezclar_prefs = lambda *a, **k: None
archivos_seguros.escribir_json = lambda *a, **k: None
archivos_seguros.mezclar_json = lambda *a, **k: None
sfx_rules.guardar_modo = lambda *a, **k: None
resolve_mcp.ruta_exe = lambda: None
resolve_mcp.estado_cacheado = lambda *a, **k: {}

from PySide6.QtWidgets import QApplication, QWidget, QLabel, QAbstractButton
app = QApplication.instance() or QApplication([])
lineas = []


def huella(nombre, widget):
    try:
        hijos = widget.findChildren(QWidget)
        clases = Counter(type(h).__name__ for h in hijos)
        textos = sorted({(h.text() or '').strip()[:60] for h in hijos if isinstance(h, (QLabel, QAbstractButton)) and (h.text() or '').strip()})
        lineas.append(f'## {nombre}: {type(widget).__name__} hijos={len(hijos)}')
        lineas.append('   clases: ' + ', '.join(f'{k}={v}' for k, v in sorted(clases.items())))
        lineas.append('   textos: ' + ' | '.join(textos))
    except Exception:
        lineas.append(f'## {nombre}: FALLO en huella\n' + traceback.format_exc())


def intentar(nombre, fabrica):
    try:
        w = fabrica()
        app.processEvents()
        huella(nombre, w)
        return w
    except Exception:
        lineas.append(f'## {nombre}: FALLO\n' + traceback.format_exc())
        print('FALLO', nombre, flush=True)
        return None


w = M.SubtitleApp()
w._guardar_preferencias = lambda *a, **k: None
app.processEvents()
huella('SubtitleApp', w)
paginas = []
for attr in ('PAGINAS', 'paginas', '_paginas'):
    v = getattr(w, attr, None)
    if isinstance(v, (dict, list, tuple)) and v:
        paginas = list(v.keys() if isinstance(v, dict) else v)
        break
lineas.append(f'# paginas: {paginas}')
for p in paginas:
    p = p[0] if isinstance(p, (tuple, list)) else p
    try:
        w.ir_a(p)
        app.processEvents()
        huella('pagina ' + p, w)
    except Exception:
        lineas.append(f'## pagina {p}: FALLO\n' + traceback.format_exc())

palabras = [{'word': t, 'start': i * 0.4, 'end': i * 0.4 + 0.35} for i, t in enumerate('hola esto es una prueba de las ventanas del editor con palabras reales'.split())]
roles = ['principal'] * len(palabras)
intentar('ProyectosWindow', lambda: M.ProyectosWindow(w))
intentar('IdiomasTraduccionWindow', lambda: M.IdiomasTraduccionWindow(w))
intentar('BuscadorIdiomaWindow', lambda: M.BuscadorIdiomaWindow(w, 'Idioma', ['Español', 'Inglés', 'Francés'], lambda x: None))
intentar('EmojiPickerWindow', lambda: M.EmojiPickerWindow(w, 'hola', 'es', None, lambda e: None))
intentar('ComposicionWindow', lambda: M.ComposicionWindow(w))
intentar('PlantillasWindow', lambda: M.PlantillasWindow(w, seleccion=None))
ed = intentar('WordTagWindow', lambda: M.WordTagWindow(w, palabras, roles, 'zz_humo_ventanas', idioma='es'))
if ed is not None:
    for nombre, fab in (('LienzoPalabras', lambda: M.LienzoPalabras(ed._fuentes, ed.ROLE_COLOR, M.ACCENT)),):
        intentar(nombre, fab)

salida.write_text('\n'.join(lineas) + '\n', encoding='utf-8')
fallos = [l for l in lineas if 'FALLO' in l]
print('listo:', len(lineas), 'líneas;', len(fallos), 'fallos ->', salida, flush=True)
os._exit(0)
