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


def _asegurar_indice(log):
    """Baja el indice de paquetes si no esta, DICIENDO por que si falla.

    argostranslate lo baja solo, pero se traga el error (logger sin
    salida en el compilado) y su get_available_packages reintenta en
    recursion infinita hasta un RecursionError que no dice nada (medido:
    984 intentos). Aqui la descarga va a la vista: sin red, bloqueada o
    sin certificados, el mensaje lleva la causa real y la URL.
    """
    import urllib.request
    import argostranslate.settings as settings
    from pathlib import Path
    ruta = Path(settings.local_package_index)
    if ruta.exists():
        return
    url = settings.remote_package_index
    log(tr('Descargando el índice de paquetes de traducción (una sola vez)...'))
    try:
        datos = urllib.request.urlopen(url, timeout=60).read()
    except Exception as e:
        raise SinConexion(
            tr('No pude descargar el índice de paquetes de traducción ({url}):', url=url)
            + f' {type(e).__name__}: {e}\n'
            + tr('Revisa la conexión a internet y vuelve a intentarlo.')
        )
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(datos)


def ensure_lang_pack(from_code: str, to_code: str, log=print) -> None:
    """Instala el paquete from_code->to_code si no esta ya instalado.

    Lanza SystemExit si no existe un paquete para ese par de idiomas, y
    SinConexion (subclase) si no se pudo descargar. `log` permite
    redirigir los mensajes (la ventana grafica los muestra en pantalla
    en vez de imprimirlos en la consola).
    """
    import logging
    import argostranslate.package as package

    installed = package.get_installed_packages()
    if any(p.from_code == from_code and p.to_code == to_code for p in installed):
        log(tr('Paquete de traduccion {origen}->{destino} ya estaba instalado.',
               origen=from_code, destino=to_code))
        return

    _asegurar_indice(log)
    log(tr('Descargando paquete de traduccion {origen}->{destino} (una sola vez)...',
           origen=from_code, destino=to_code))

    ultimos = []

    class _Captura(logging.Handler):
        def emit(self, registro):
            ultimos.append(registro.getMessage())

    logger = logging.getLogger('argostranslate.utils')
    captura = _Captura()
    logger.addHandler(captura)
    try:
        ok = package.install_package_for_language_pair(from_code, to_code)
    except Exception as e:
        detalle = f' — {ultimos[-1]}' if ultimos else ''
        raise SinConexion(
            tr('No pude descargar el paquete de traducción {origen}->{destino}:',
               origen=from_code, destino=to_code)
            + f' {type(e).__name__}: {e}{detalle}\n'
            + tr('Revisa la conexión a internet y vuelve a intentarlo.')
        )
    finally:
        logger.removeHandler(captura)
    if not ok:
        raise SystemExit(tr('No encontre un paquete de traduccion {origen}->{destino} disponible.',
                            origen=from_code, destino=to_code))
    log(tr('Paquete {origen}->{destino} instalado correctamente.',
           origen=from_code, destino=to_code))


def _a_dict(paquete, instalado):
    return {
        'from': getattr(paquete, 'from_code', ''),
        'to': getattr(paquete, 'to_code', ''),
        'nombre_from': (getattr(paquete, 'from_name', '')
                        or getattr(paquete, 'from_code', '')),
        'nombre_to': (getattr(paquete, 'to_name', '')
                      or getattr(paquete, 'to_code', '')),
        'instalado': instalado,
    }


def paquetes_instalados():
    """Lo que ya esta descargado en esta maquina. No necesita internet."""
    try:
        import argostranslate.package as package
        return [_a_dict(p, True) for p in package.get_installed_packages()]
    except Exception:
        return []


def paquetes_disponibles(refrescar=True):
    """Todo el catalogo, marcando lo que ya esta instalado.

    Necesita internet la primera vez (baja el indice). Sin conexion devuelve
    solo lo instalado, que es informacion util y no una lista vacia: asi la
    ventana puede decir "esto es lo que tienes" en vez de parecer rota.
    """
    try:
        import argostranslate.package as package
    except Exception:
        return []
    instalados = {(p.from_code, p.to_code) for p in package.get_installed_packages()}
    if refrescar:
        try:
            package.update_package_index()
        except Exception:
            return [dict(d) for d in paquetes_instalados()]
    try:
        disponibles = package.get_available_packages()
    except Exception:
        return [dict(d) for d in paquetes_instalados()]
    return [_a_dict(p, (p.from_code, p.to_code) in instalados) for p in disponibles]


def instalar(from_code, to_code, log=print):
    """Descarga e instala un par. Devuelve True si al terminar esta puesto.

    Es lo mismo que hace ensure_lang_pack, pero devolviendo un booleano en
    vez de lanzar: la ventana de idiomas prefiere mostrar el fallo en su
    lista antes que reventar en medio de una descarga de varias.
    """
    try:
        ensure_lang_pack(from_code, to_code, log=log)
        return True
    except SystemExit as e:
        log(str(e))
        return False
    except Exception as e:
        log(tr('No pude instalar {origen}->{destino}: {e}',
               origen=from_code, destino=to_code, e=e))
        return False


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Uso: python ensure_lang_pack.py <from_code> <to_code>')
    ensure_lang_pack(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    main()
