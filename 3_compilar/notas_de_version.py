# CineCaptions · By Cinema Productions
# 3_compilar/notas_de_version.py — imprime las mejoras de una versión (las de ajustes_ui.NOTAS_VERSION), una por línea con viñeta: Publicar_Version.ps1 las manda al manifiesto.
"""
Uso:  python 3_compilar/notas_de_version.py 5.4.2
No importa la interfaz (lee el archivo con ast): corre en cualquier sitio. Sin esa versión en NOTAS_VERSION no imprime nada.
"""
import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
version = sys.argv[1] if len(sys.argv) > 1 else ''
salida = sys.argv[2] if len(sys.argv) > 2 else ''          # archivo de salida opcional (UTF-8)
arbol = ast.parse((RAIZ / '1_codigo' / 'ajustes_ui.py').read_text(encoding='utf-8'))
for nodo in arbol.body:
    if isinstance(nodo, ast.Assign) and any(getattr(t, 'id', '') == 'NOTAS_VERSION' for t in nodo.targets):
        for v, lineas in ast.literal_eval(nodo.value):
            if v == version:
                texto = '\n'.join('• ' + l for l in lineas)
                if salida:                                    # por archivo UTF-8: la consola de Windows rompe las tildes
                    Path(salida).write_text(texto, encoding='utf-8')
                else:
                    sys.stdout.reconfigure(encoding='utf-8')
                    print(texto)
