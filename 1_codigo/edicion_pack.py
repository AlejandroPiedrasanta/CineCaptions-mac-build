# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pack.py — «Editar en Resolve»: abre un pack de «Pack de estilos» como timeline para modificarlo y exportarlo de nuevo.
"""
Cada estilo de «Pack de estilos» trae un botón ✎ (y el doble clic sobre su tarjeta): abre su timeline (.drt) en Resolve —o, si el pack solo trae el bin (.drb), un
timeline armado con sus clips apilados y ya con los nombres exactos— para cambiar fuente, color, tamaño o posición. Después se exporta (Archivo > Exportar >
Timeline) y se vuelve a añadir con la tarjeta «Añadir plantilla (.drb)».

El trabajo corre dentro de Resolve: 2_recursos/guia_estilo/editar_pack.py, que lee ~/DaVinciSubtitles/editar_pack.json (lo escribe datos_edicion).
"""
import threading
from pathlib import Path

import archivos_seguros
import plantillas
import resolve_mcp

_CERROJO = threading.Lock()
TAMANOS = {'v': (1080, 1920), 'h': (1920, 1080), 'c': (1080, 1080)}


def script():
    import ejemplos_estilo
    return ejemplos_estilo.carpeta_recursos() / 'editar_pack.py'


def datos_edicion(pack, formato):
    """Lo que editar_pack.py necesita: el .drt o el .drb del pack en ese formato y la posición (Pan/Tilt/Zoom en píxeles) de cada clip."""
    if formato not in pack.formatos:
        formato = pack.formatos[0] if pack.formatos else 'v'
    ancho, alto = TAMANOS.get(formato, (1080, 1920))
    drt, drb = pack.ruta_drt(formato), pack.ruta_drb(formato)
    posiciones = {}
    if drb:
        try:
            for clave, (x, y, zx, zy) in plantillas.transformaciones_de_drb(drb).items():
                posiciones[clave] = {'x': x * ancho, 'y': y * alto, 'zx': zx, 'zy': zy}
        except Exception:
            posiciones = {}
    return {'nombre': pack.nombre, 'timeline': f'Editar · {pack.nombre}', 'formato': formato, 'ancho': ancho, 'alto': alto,
            'drt': str(drt or ''), 'drb': str(drb or ''), 'posiciones': posiciones}


def abrir_en_resolve(pack, formato, al_estado=None, abrir_resolve=True):
    """Abre el pack en Resolve para editarlo. Devuelve (ok, mensaje)."""
    prep = resolve_mcp.preparar_resolve(abrir=abrir_resolve, al_estado=al_estado)
    if not prep.get('ok'):
        return False, prep.get('motivo') or 'No pude preparar Resolve.'
    datos = datos_edicion(pack, formato)
    with _CERROJO:
        archivos_seguros.escribir_json(Path.home() / 'DaVinciSubtitles' / 'editar_pack.json', datos)
        return resolve_mcp.ejecutar_py(script(), timeout=240)
