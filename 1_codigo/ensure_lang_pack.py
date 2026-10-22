# CineCaptions · By Cinema Productions
# 1_codigo/ensure_lang_pack.py — instala los paquetes de traducción sin internet (Argos Translate) que falten.
"""
ensure_lang_pack.py
--------------------
Instala (si falta) el paquete de idioma de Argos Translate necesario para
traducir de un idioma a otro. Idempotente: si ya esta instalado, no hace nada.

Se puede usar de dos formas:

  1. Desde la terminal:
         python ensure_lang_pack.py <from_code> <to_code>

  2. Importandolo desde otro script (lo hace CineCaptions (script principal).py):
         from ensure_lang_pack import ensure_lang_pack
         ensure_lang_pack("es", "en")
"""
import os
import sys

from i18n import tr

# Argos: tipo de computo y segmentador de frases por defecto
os.environ.setdefault('ARGOS_COMPUTE_TYPE', 'float32')

os.environ.setdefault('ARGOS_CHUNK_TYPE', 'MINISBD')


def certificados_para_urllib():
    """Los certificados raiz para urllib, en TODO el proceso (v3.0.0).

    argostranslate (indice y paquetes) y minisbd (su modelo .onnx) bajan
    con urllib.request a secas. En Windows urllib valida con el almacen
    del sistema; el Python que va DENTRO del .app de macOS no trae
    certificados raiz, asi que cada https fallaba con
    CERTIFICATE_VERIFY_FAILED — argostranslate se lo tragaba (lo manda a
    un logger sin salida en el compilado), reintentaba en recursion y la
    app veia «RecursionError». La traduccion NUNCA funciono en la Mac
    compilada (reporte 15-09: «como si lo intento descargar y no pudo»;
    reproducido aqui simulando la Mac). licencia.py ya usaba certifi
    para SU conexion (por eso activar si funcionaba en la Mac); esto lo
    extiende al proceso entero: OpenSSL lee SSL_CERT_FILE al crear cada
    contexto, asi que basta ponerla antes de la primera descarga.
    setdefault: si el usuario ya la tiene (proxy corporativo), manda la
    suya. En Windows solo SUMA certifi al almacen del sistema.
    """
    try:
        import certifi
        os.environ.setdefault('SSL_CERT_FILE', certifi.where())
    except Exception:
        pass


certificados_para_urllib()


class SinConexion(SystemExit):
    """No se pudo DESCARGAR (red, certificados, bloqueo): no es que el par
    no exista. La app lo distingue para no intentar el pivote por ingles
    con un mensaje que diria «no hay paquete directo» siendo mentira."""


def ensure_lang_pack(from_code: str, to_code: str, log=print) -> None:
    """Instala un paquete Argos con el servicio auxiliar Python 3.14."""
    import motor_compat
    installed = motor_compat.paquetes_instalados()
    if any(p.get('from') == from_code and p.get('to') == to_code for p in installed):
        log(tr('Paquete de traduccion {origen}->{destino} ya estaba instalado.',
               origen=from_code, destino=to_code))
        return
    log(tr('Descargando paquete de traduccion {origen}->{destino} (una sola vez)...',
           origen=from_code, destino=to_code))
    mensajes = []

    def registrar(texto):
        mensajes.append(str(texto))
        if log:
            log(texto)

    try:
        instalado = motor_compat.instalar_paquete(from_code, to_code, log=registrar)
    except Exception as exc:
        raise SinConexion(
            tr('No pude instalar el paquete de traducción {origen}->{destino}:',
               origen=from_code, destino=to_code)
            + f' {type(exc).__name__}: {exc}\n'
            + tr('Revisa la conexión a internet y vuelve a intentarlo.')
        )
    if not instalado:
        detalle = '\n'.join(mensajes[-3:])
        if any(x in detalle.lower() for x in ('url', 'download', 'conexión', 'connection', 'timeout', 'ssl')):
            raise SinConexion(detalle or tr('No se pudo descargar el paquete de traducción.'))
        raise SystemExit(tr('No encontre un paquete de traduccion {origen}->{destino} disponible.',
                            origen=from_code, destino=to_code) + (f'\n{detalle}' if detalle else ''))
    log(tr('Paquete {origen}->{destino} instalado correctamente.',
           origen=from_code, destino=to_code))


def paquetes_instalados():
    """Lista los paquetes disponibles sin cargar Argos en Python 3.15."""
    try:
        import motor_compat
        return motor_compat.paquetes_instalados()
    except Exception:
        return []


def paquetes_disponibles(refrescar=True):
    """Lista el catálogo auxiliar; sin red devuelve lo que ya está instalado."""
    try:
        import motor_compat
        return motor_compat.paquetes_disponibles(refrescar=refrescar)
    except Exception:
        return paquetes_instalados()


def instalar(from_code, to_code, log=print):
    """Instala el par solicitado y devuelve False si falla."""
    try:
        ensure_lang_pack(from_code, to_code, log=log)
        return True
    except SystemExit as exc:
        log(str(exc))
        return False
    except Exception as exc:
        log(tr('No pude instalar {origen}->{destino}: {e}',
               origen=from_code, destino=to_code, e=exc))
        return False


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Uso: python ensure_lang_pack.py <from_code> <to_code>')
    ensure_lang_pack(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    main()
