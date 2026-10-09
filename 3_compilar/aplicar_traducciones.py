# CineCaptions · By Cinema Productions
# 3_compilar/aplicar_traducciones.py — mete los textos nuevos de traducciones_extra.json en los catálogos de 2_recursos/locales (en, pt, fr, de, it).
"""
Uso:   python 3_compilar/aplicar_traducciones.py          (no pisa lo que ya estaba traducido)
       python 3_compilar/aplicar_traducciones.py --forzar  (sí lo pisa)
traducciones_extra.json = {"texto en español": {"en": ..., "pt": ..., "fr": ..., "de": ..., "it": ...}}
Para ver qué textos del código faltan en los catálogos: python 3_compilar/auditar_traducciones.py
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOCALES = RAIZ / '2_recursos' / 'locales'
forzar = '--forzar' in sys.argv
nuevos = json.loads((Path(__file__).with_name('traducciones_extra.json')).read_text(encoding='utf-8'))
for idioma in ('en', 'pt', 'fr', 'de', 'it'):
    ruta = LOCALES / f'{idioma}.json'
    datos = json.loads(ruta.read_text(encoding='utf-8'))
    textos = datos['textos']
    anadidos = 0
    for es, por_idioma in nuevos.items():
        if idioma in por_idioma and (forzar or es not in textos):
            textos[es] = por_idioma[idioma]
            anadidos += 1
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{idioma}: +{anadidos} (total {len(textos)})')
