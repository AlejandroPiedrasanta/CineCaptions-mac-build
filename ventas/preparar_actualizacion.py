"""CineCaptions Ventas · By Cinema Productions
programa/preparar_actualizacion.py — arma lo que se sube al servidor para que las apps instaladas se actualicen solas (2.11).

    python preparar_actualizacion.py "notas de la versión"

Con los instaladores ya compilados en programa/ (construir_instalador.ps1 y mac/Compilar_Ventas_Mac.ps1), escribe
web/pagos/ventas_app/version.json (versión, fecha, notas y, por equipo, el archivo, su tamaño y su huella SHA-256) e
imprime qué archivo local va a qué ruta del servidor. Se sube a public_html/pagos/ventas_app/ (cerrada al navegador con
su .htaccess): primero los instaladores y AL FINAL version.json, así ninguna app ve una versión cuyo archivo no llegó.
admin.php los da solo con la clave (acciones app_version y app_descargar).
"""
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DESTINO = AQUI.parent / 'web' / 'pagos' / 'ventas_app'


def huella(ruta):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for trozo in iter(lambda: f.read(1024 * 1024), b''):
            h.update(trozo)
    return h.hexdigest()


def main():
    version = re.search(r"^VERSION = '([0-9.]+)'", (AQUI / 'ventas.py').read_text(encoding='utf-8'), re.M).group(1)
    locales = {
        'windows': (AQUI / 'Instalar CineCaptions Ventas.exe', f'Instalar_CineCaptions_Ventas_{version}.exe'),
        'mac_applesilicon': (AQUI / f'CineCaptions_Ventas_Mac_AppleSilicon_{version}.dmg',
                             f'CineCaptions_Ventas_Mac_AppleSilicon_{version}.dmg'),
        'mac_intel': (AQUI / f'CineCaptions_Ventas_Mac_Intel_{version}.dmg', f'CineCaptions_Ventas_Mac_Intel_{version}.dmg'),
    }
    archivos, subir = {}, []
    for plataforma, (local, remoto) in locales.items():
        if not local.is_file():
            sys.exit(f'Falta {local.name}: compílalo antes (versión {version}).')
        if plataforma == 'windows':   # (el .exe dice su versión: que no se suba uno viejo)
            if version.encode('utf-16-le') not in local.read_bytes():
                sys.exit(f'{local.name} no es la versión {version}: vuelve a correr construir_instalador.ps1.')
        archivos[plataforma] = {'archivo': remoto, 'tamano': local.stat().st_size, 'sha256': huella(local)}
        subir.append({'local': str(local), 'remoto': f'pagos/ventas_app/{remoto}'})
    notas = ' '.join(sys.argv[1:]).strip()
    info = {'version': version, 'fecha': dt.date.today().isoformat(), 'notas': notas, 'archivos': archivos}
    DESTINO.mkdir(parents=True, exist_ok=True)
    (DESTINO / 'version.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    subir.append({'local': str(DESTINO / 'version.json'), 'remoto': 'pagos/ventas_app/version.json'})
    print(json.dumps({'version': version, 'subir': subir}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
