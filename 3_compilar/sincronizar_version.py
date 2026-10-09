# CineCaptions · By Cinema Productions
# 3_compilar/sincronizar_version.py — pone la versión de version.py en todos los sitios que la repiten (scripts de Resolve, Puente) y avisa si algo no cuadra.
"""
sincronizar_version.py
----------------------
Una sola fuente de la versión: 1_codigo/version.py (APP_VERSION). Los scripts de Resolve (2_recursos/resolve_scripts) llevan su propia línea
«VERSION = "x.y.z (nombre)»» y el Puente lleva «PAQUETE = "x.y.z"»; el programa compara esos números con APP_VERSION al colocar y, si no coinciden,
avisa de «otra versión instalada». Hasta ahora había que cambiarlos a mano al subir la versión y se olvidaban (APP_VERSION 5.3.1 con scripts 5.3.0).

    python sincronizar_version.py            reescribe lo que no cuadre y dice qué cambió
    python sincronizar_version.py --comprobar   solo comprueba (sale con 1 si algo no cuadra)
    python sincronizar_version.py --subir       antes sube el último número de APP_VERSION (5.3.1 -> 5.3.2) y luego sincroniza

Solo toca las líneas que empiezan por un número de versión del programa seguido de « (»: «5.3.0 (subtitulos)». Las versiones propias de un script
(«1.0.37» del Puente, «1.1», una fecha) no se tocan.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VERSION_PY = RAIZ / '1_codigo' / 'version.py'
SCRIPTS = RAIZ / '2_recursos' / 'resolve_scripts'

PATRON_VERSION = re.compile(r'''(?m)^(?P<antes>\s*(?:local\s+)?VERSION\s*=\s*["'])(?P<num>\d+\.\d+\.\d+)(?P<despues>\s\([^"']*\)["'])''')
PATRON_PAQUETE = re.compile(r'''(?m)^(?P<antes>\s*(?:local\s+)?PAQUETE\s*=\s*["'])(?P<num>\d+\.\d+\.\d+)(?P<despues>["'])''')
PATRON_APP = re.compile(r"""(?m)^(APP_VERSION\s*=\s*')(\d+)\.(\d+)\.(\d+)(')""")


def leer_version():
    m = PATRON_APP.search(VERSION_PY.read_text(encoding='utf-8'))
    if not m:
        raise SystemExit('No encontré APP_VERSION en 1_codigo/version.py')
    return f'{m.group(2)}.{m.group(3)}.{m.group(4)}'


def subir():
    """5.3.1 -> 5.3.2 (escribe version.py). Devuelve la nueva."""
    texto = VERSION_PY.read_text(encoding='utf-8', newline='')
    m = PATRON_APP.search(texto)
    if not m:
        raise SystemExit('No encontré APP_VERSION en 1_codigo/version.py')
    nueva = f'{m.group(2)}.{m.group(3)}.{int(m.group(4)) + 1}'
    texto = texto[:m.start()] + f"{m.group(1)}{nueva}{m.group(5)}" + texto[m.end():]
    VERSION_PY.write_text(texto, encoding='utf-8', newline='')
    return nueva


def sincronizar(version, solo_comprobar=False):
    """Devuelve la lista de (archivo, antes, despues) que no cuadraban (y los reescribe si no es solo comprobar)."""
    cambios = []
    for ruta in sorted(SCRIPTS.glob('*')):
        if ruta.suffix.lower() not in ('.py', '.lua'):
            continue
        crudo = ruta.read_bytes()
        try:
            texto = crudo.decode('utf-8')
        except UnicodeDecodeError:
            continue
        nuevo = texto
        for patron in (PATRON_VERSION, PATRON_PAQUETE):
            def cambiar(m, _ruta=ruta):
                if m.group('num') != version:
                    cambios.append((_ruta.name, m.group('num'), version))
                return f"{m.group('antes')}{version}{m.group('despues')}"
            nuevo = patron.sub(cambiar, nuevo)
        if nuevo != texto and not solo_comprobar:
            ruta.write_bytes(nuevo.encode('utf-8'))          # bytes: respeta los saltos de línea del archivo
    return cambios


def main():
    args = sys.argv[1:]
    if '--subir' in args:
        print(f'Versión subida a {subir()}')
    version = leer_version()
    solo = '--comprobar' in args
    cambios = sincronizar(version, solo_comprobar=solo)
    if not cambios:
        print(f'Versión {version}: todo cuadra (scripts de Resolve y Puente).')
        return 0
    for nombre, antes, despues in cambios:
        print(f'  {nombre}: {antes} -> {despues}' + ('  (sin cambiar: --comprobar)' if solo else ''))
    print(f'Versión {version}: ' + (f'{len(cambios)} no cuadran.' if solo else f'{len(cambios)} línea(s) puestas al día.'))
    return 1 if solo else 0


if __name__ == '__main__':
    sys.exit(main())
