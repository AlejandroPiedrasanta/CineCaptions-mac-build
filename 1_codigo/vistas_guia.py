# CineCaptions · By Cinema Productions
# 1_codigo/vistas_guia.py — las vistas REALES (renderizadas por Resolve) de los ejemplos de «Crea tu estilo»: se piden, se reducen y se guardan en caché.
"""
Como «Vista real · Resolve» de los packs (vistas_reales.py), pero para los ejemplos de la galería «Crea tu estilo»: se corre
2_recursos/guia_estilo/construir_guia.py dentro de Resolve (modo 'vistas'), que arma UN timeline temporal con todos los ejemplos —con los macros reales Luxe Shine
y Luxe Slide y los presets de Amro.Films Captions— y saca VARIOS fotogramas de cada uno (ejemplos_estilo.CUADROS_VISTA_S: la animación de entrada y el
resultado final). Aquí se reducen (Pillow) a ~360×640 y se guardan en

    ~/DaVinciSubtitles/plantillas_cache/guia_estilo/vistas/ej_NN_K.jpg

La galería los reproduce en bucle (crea_estilo_ui). Las vistas dependen de las tipografías y los efectos que tenga el Resolve de cada equipo; las de fábrica
(2_recursos/guia_estilo/vistas) se usan hasta que el Resolve del equipo haga las suyas.
"""
import shutil
import tempfile
import threading
import time
from pathlib import Path

import ejemplos_estilo as E
import resolve_mcp

CARPETA = E.CARPETA_VISTAS
MARCA_TEMPORAL = 'RCS · temporal (se limpia solo)'      # la misma marca que borra el siguiente trabajo del programa
ALTO_VISTA = 640


def ruta_de(ident, k):
    return CARPETA / f'ej_{int(ident):02d}_{k}.jpg'


def faltan():
    """Los ejemplos que todavía no tienen su vista real animada (ni la del equipo ni la de fábrica)."""
    return [e['id'] for e in E.EJEMPLOS if E.ruta_video(e) is None and len(E.rutas_vista(e)) < len(E.CUADROS_VISTA_S)]


def _reducir(origen, destino):
    try:
        from PIL import Image
        with Image.open(origen) as img:
            img = img.convert('RGB')
            if img.height > ALTO_VISTA:
                img = img.resize((max(1, round(img.width * ALTO_VISTA / img.height)), ALTO_VISTA), Image.Resampling.LANCZOS)
            img.save(destino, quality=88)
        return True
    except Exception:
        return False


def renderizar(al_estado=None, abrir_resolve=False, ids=None):
    """Resolve renderiza la vista real animada de los ejemplos 'ids' (todos si es None). Devuelve (ok, cuántos | mensaje de error)."""
    from i18n import tr
    prep = resolve_mcp.preparar_resolve(abrir=abrir_resolve, al_estado=al_estado, pagina=None)
    if not prep.get('proyecto'):
        return False, prep.get('motivo') or tr('Resolve no está listo')
    guia = E.carpeta_recursos()
    crudo = Path(tempfile.mkdtemp(prefix='cinecaptions_vista_guia_'))
    ejemplos = [e for e in E.EJEMPLOS if ids is None or e['id'] in ids]
    total = len(ejemplos) * len(E.CUADROS_VISTA_S)
    parar = threading.Event()

    def vigilar():
        """Cuenta los fotogramas que Resolve va dejando para ir contando el avance."""
        while not parar.wait(1.0):
            if al_estado:
                try:
                    al_estado(tr('Resolve está renderizando los ejemplos… {n} de {t}', n=len(list(crudo.glob('*.png'))), t=total))
                except Exception:
                    pass
    if al_estado:
        al_estado(tr('Resolve está renderizando los {n} ejemplos…', n=len(ejemplos)))
        threading.Thread(target=vigilar, daemon=True, name='vigila-vistas-guia').start()
    try:
        datos = E.datos_guia(guia / 'Crea tu estilo.drb', amro=guia / 'Amro principales.drb', fotos=crudo, solo=None if ids is None else set(ids))
        datos['modo'] = 'vistas'
        ok, mensaje = resolve_mcp.abrir_guia(guia / 'construir_guia.py', f"{MARCA_TEMPORAL} · vista guia {time.strftime('%H%M%S')}", datos)
    finally:
        parar.set()
    CARPETA.mkdir(parents=True, exist_ok=True)
    hechos = 0
    for e in ejemplos:
        nuevas = []
        for k in range(len(E.CUADROS_VISTA_S)):
            origen = crudo / f"ej_{e['id']:02d}_{k}.png"
            if origen.is_file() and _reducir(origen, ruta_de(e['id'], k)):
                nuevas.append(k)
        if len(nuevas) == len(E.CUADROS_VISTA_S):
            hechos += 1
    shutil.rmtree(crudo, ignore_errors=True)
    E.olvidar_miniaturas()
    if not hechos:
        return False, mensaje or tr('Resolve no devolvió imágenes')
    return True, hechos
