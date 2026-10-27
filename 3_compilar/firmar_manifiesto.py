# CineCaptions · By Cinema Productions
# 3_compilar/firmar_manifiesto.py — firma el version.json (Ed25519) antes de publicarlo: los programas desde la 5.52 rechazan uno sin firma.
"""
Uso:  python 3_compilar/firmar_manifiesto.py INSTALADORES/version.json   firma (Publicar_Version.ps1 lo llama solo)
      python 3_compilar/firmar_manifiesto.py --claves-nuevas              crea la principal y la de reserva (no pisa las que ya hay) e
                                                                          imprime sus claves públicas para actualizaciones.CLAVES_FIRMA
Las privadas viven FUERA del repositorio, en ~/CineCaptions_claves (o la ruta de la variable CINECAPTIONS_CLAVE_FIRMA). La de reserva
se copia aparte (USB o nube): si se pierde la principal se firma con ella; sin ninguna, los programas instalados ya no se actualizan.
Antes de escribir comprueba la firma con las claves públicas que lleva el programa: una clave que el programa no conoce no publica nada.
"""
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / '1_codigo'))
import actualizaciones      # noqa: E402
import firma_ed25519        # noqa: E402

CARPETA = Path.home() / 'CineCaptions_claves'


def id_clave(publica):
    return hashlib.sha256(publica).hexdigest()[:8]


def claves_nuevas():
    CARPETA.mkdir(exist_ok=True)
    for nombre in ('principal', 'reserva'):
        ruta = CARPETA / f'actualizaciones_{nombre}.key'
        if ruta.exists():
            privada = bytes.fromhex(ruta.read_text(encoding='ascii').strip())
        else:
            privada = firma_ed25519.nueva_privada()
            ruta.write_text(privada.hex() + '\n', encoding='ascii')
        publica = firma_ed25519.publica(privada)
        print(f"    '{id_clave(publica)}': '{publica.hex()}',   # {nombre}")


def leer_privada():
    propia = os.environ.get('CINECAPTIONS_CLAVE_FIRMA')
    for ruta in ([Path(propia)] if propia else [CARPETA / 'actualizaciones_principal.key', CARPETA / 'actualizaciones_reserva.key']):
        if ruta.is_file():
            return bytes.fromhex(ruta.read_text(encoding='ascii').strip()), ruta
    raise SystemExit(f'No encuentro la clave privada de firma en {CARPETA} (ni en CINECAPTIONS_CLAVE_FIRMA): sin ella no se publica.')


def firmar(ruta_json):
    ruta = Path(ruta_json)
    datos = json.loads(ruta.read_text(encoding='utf-8-sig'))
    datos.pop('firma', None)
    privada, origen = leer_privada()
    publica = firma_ed25519.publica(privada)
    valor = firma_ed25519.firmar(privada, actualizaciones.bytes_firmados(datos))
    datos['firma'] = {'alg': 'ed25519', 'clave': id_clave(publica), 'valor': base64.b64encode(valor).decode('ascii')}
    if not actualizaciones.firma_valida(datos):
        raise SystemExit(f'La clave {origen.name} no es ninguna de actualizaciones.CLAVES_FIRMA: los programas la rechazarían. No se firma.')
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'    firmado con {origen.name} ({id_clave(publica)})')


if __name__ == '__main__':
    if sys.argv[1:] == ['--claves-nuevas']:
        claves_nuevas()
    elif len(sys.argv) == 2:
        firmar(sys.argv[1])
    else:
        raise SystemExit(__doc__)
