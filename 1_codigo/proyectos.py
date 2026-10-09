# CineCaptions · By Cinema Productions
# 1_codigo/proyectos.py — registro de proyectos (vídeos) trabajados: recientes, abrir, borrar.
"""\nproyectos.py\n------------\nRegistro persistente de proyectos (videos) trabajados. Complementa\n`guardar_marcas` / `cargar_marcas` del main con:\n\n- Listado ordenado por fecha modificado (para chips \"Recientes\" y\n  ventana \"Proyectos guardados\").\n- Borrado individual y purga total.\n- Guardado del path completo del video de origen (necesario para\n  re-abrir un proyecto sin que el usuario tenga que buscarlo de nuevo).\n\nFormato en disco:\n  ~/DaVinciSubtitles/<project_name>.marcas.json    (marcas — legacy)\n  ~/DaVinciSubtitles/proyectos/<hash>.json          (metadatos)\n\nEl hash es SHA1 del path absoluto normalizado del video, asi el mismo\narchivo reabierto encuentra su registro aunque el project_name coincida\ncon otro video.\n"""
import hashlib
import json
import time
from pathlib import Path
SHARED_FOLDER = Path.home() / 'DaVinciSubtitles'
PROYECTOS_DIR = SHARED_FOLDER / 'proyectos'
def _hash_video(video_path):
    """SHA1 del path absoluto normalizado del video."""
    p = str(Path(video_path).expanduser().resolve()).lower()
    return hashlib.sha1(p.encode('utf-8')).hexdigest()[:16]
def _ruta_proyecto(video_path):
    return PROYECTOS_DIR / f'{_hash_video(video_path)}.json'
def guardar(video_path, project_name, idioma=None, traducir_ingles=False, extra=None):
    """Registra o actualiza el proyecto asociado a `video_path`.\n\n    No guarda las marcas (eso lo hace guardar_marcas en el main), solo\n    los metadatos para poder listar, buscar y re-abrir.\n    """
    if not video_path:
        return
    else:
        PROYECTOS_DIR.mkdir(parents=True, exist_ok=True)
        ruta = _ruta_proyecto(video_path)
        ahora = time.time()
        datos_previos = {}
        if ruta.exists():
            try:
                datos_previos = json.loads(ruta.read_text(encoding='utf-8'))
            except Exception:
                datos_previos = {}
        datos = {**datos_previos, 'video_path': str(Path(video_path).expanduser().resolve()), 'project_name': project_name, 'idioma': idioma or datos_previos.get('idioma'), 'traducir_ingles': bool(traducir_ingles), 'creado_en': datos_previos.get('creado_en', ahora), 'modificado_en': ahora}
        if extra:
            datos.update(extra)
        import archivos_seguros
        archivos_seguros.escribir_json(ruta, datos, indent=2)
        return ruta
def cargar(video_path):
    """Devuelve el dict del proyecto asociado a `video_path` o None."""
    if not video_path:
        return
    else:
        ruta = _ruta_proyecto(video_path)
        if not ruta.exists():
            return
        else:
            try:
                return json.loads(ruta.read_text(encoding='utf-8'))
            except Exception:
                return None
def listar(limite=None):
    """Devuelve la lista de proyectos ordenados por modificado_en desc.\n\n    Cada elemento es el dict guardado + la clave \'existe\' con True si el\n    video_path referenciado sigue existiendo en disco. Los proyectos\n    cuyo video ya no existe se listan igual (para que el usuario pueda\n    purgarlos), marcados con existe=False.\n    """
    if not PROYECTOS_DIR.exists():
        return []
    else:
        items = []
        for ruta in PROYECTOS_DIR.glob('*.json'):
            try:
                datos = json.loads(ruta.read_text(encoding='utf-8'))
            except Exception:
                pass
            else:
                vp = datos.get('video_path')
                datos['existe'] = bool(vp) and Path(vp).exists()
                datos['_ruta_meta'] = str(ruta)
                items.append(datos)
        items.sort(key=lambda d: d.get('modificado_en', 0), reverse=True)
        if limite:
            items = items[:limite]
        return items
def borrar(video_path, borrar_marcas=True):
    """Elimina el registro del proyecto y (opcionalmente) sus marcas."""
    ruta = _ruta_proyecto(video_path)
    if ruta.exists():
        try:
            ruta.unlink()
        except Exception:
            pass
    if borrar_marcas:
        project_name = Path(video_path).stem
        marcas = SHARED_FOLDER / f'{project_name}.marcas.json'
        if marcas.exists():
            try:
                marcas.unlink()
            except Exception:
                return
def purgar_todo(incluir_marcas=True):
    """Borra TODOS los proyectos guardados. Devuelve la cantidad borrada."""
    n = 0
    if PROYECTOS_DIR.exists():
        for ruta in PROYECTOS_DIR.glob('*.json'):
            try:
                ruta.unlink()
                n += 1
            except Exception:
                pass
    if incluir_marcas:
        for ruta in SHARED_FOLDER.glob('*.marcas.json'):
            try:
                ruta.unlink()
            except Exception:
                pass
    return n
def nombre_display(proyecto):
    """Etiqueta corta para mostrar en la UI."""
    if not proyecto:
        return '(sin nombre)'
    else:
        vp = proyecto.get('video_path') or ''
        if vp:
            return Path(vp).name
        else:
            return proyecto.get('project_name') or '(sin nombre)'
