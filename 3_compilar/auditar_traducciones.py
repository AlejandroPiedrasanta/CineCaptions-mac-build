# CineCaptions · By Cinema Productions
# 3_compilar/auditar_traducciones.py — lista los tr("...") del código que no están en los catálogos de idioma (salen en español).
"""
Uso: python 3_compilar/auditar_traducciones.py
Solo mira los tr('texto literal'); lo que se arma con variables o llega ya hecho de otro módulo lo cubre i18n.tr_libre
(por trozos y plantillas del catálogo) siempre que el texto esté en traducciones_extra.json.
"""
import ast
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
RAIZ = Path(__file__).resolve().parent.parent
faltan = {}
for idioma in ('en', 'pt', 'fr', 'de', 'it'):
    textos = json.loads((RAIZ / '2_recursos' / 'locales' / f'{idioma}.json').read_text(encoding='utf-8'))['textos']
    faltan[idioma] = set()
    for f in sorted((RAIZ / '1_codigo').glob('*.py')):
        for n in ast.walk(ast.parse(f.read_text(encoding='utf-8'))):
            if isinstance(n, ast.Call) and getattr(n.func, 'id', None) == 'tr' and n.args \
                    and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                if n.args[0].value not in textos:
                    faltan[idioma].add((f.name, n.lineno, n.args[0].value))
for idioma, cosas in faltan.items():
    print(f'{idioma}: {len(cosas)} sin traducir')
if faltan['en']:
    print('\nFaltan en inglés (primeros 40):')
    for archivo, linea, texto in sorted(faltan['en'])[:40]:
        print(f'  {archivo}:{linea}  {texto[:100]!r}')
