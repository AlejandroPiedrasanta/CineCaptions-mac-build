# CineCaptions · By Cinema Productions
# 1_codigo/proyecto_pruebas.py — un proyecto TEMPORAL y vacío de Resolve para probar sin ensuciar el del usuario.
"""
Uso (en cualquier script de prueba que use el banco):

    import proyecto_pruebas as PP
    PP.entrar()                       # guarda el proyecto abierto, lo cierra y abre «zz_PRUEBAS_CC» (nuevo, vacío)
    try:
        ... banco_pruebas.preparar / colocar_* / renderizar / limpiar ...
    finally:
        PP.salir()                    # cierra el temporal, vuelve a cargar el del usuario y borra el temporal

Por qué: el banco (zz_BANCO) crea un timeline y re-importa el bin del pack en el proyecto ABIERTO; si es el real del usuario (con clips de packs viejos) los sets se mezclan y se le
ensucia el proyecto. En un proyecto vacío los resultados son fiables y no se toca nada suyo. NO usar si el usuario tiene Resolve abierto trabajando: ver la memoria «resolve-uso-paralelo».
`probar_barrido.py` y `probar_viral.py` lo usan con la opción --temporal.
"""
import json
from pathlib import Path

import resolve_mcp

TEMP = 'zz_PRUEBAS_CC'
ESTADO = Path.home() / 'DaVinciSubtitles' / 'banco' / 'proyecto_previo.json'

_ENTRAR = r'''
pm = resolve.GetProjectManager()
cur = pm.GetCurrentProject()
previo = cur.GetName() if cur else None
if previo != %(temp)r:
    if cur and previo != 'Untitled Project':     # (v5.5.20: guardar el «Untitled Project» vacío de un Resolve recién abierto saca un diálogo que lo bloquea todo)
        pm.SaveProject()
        pm.CloseProject(cur)
    p = pm.CreateProject(%(temp)r) or pm.LoadProject(%(temp)r)
actual = pm.GetCurrentProject()
result = {'previo': previo, 'actual': actual.GetName() if actual else None}
'''

_SALIR = r'''
pm = resolve.GetProjectManager()
cur = pm.GetCurrentProject()
if cur and cur.GetName() == %(temp)r:
    pm.CloseProject(cur)
ok_carga = None
if %(previo)r:
    p = pm.LoadProject(%(previo)r)
    ok_carga = bool(p)
borrado = pm.DeleteProject(%(temp)r)
actual = pm.GetCurrentProject()
result = {'cargado': ok_carga, 'temporal_borrado': bool(borrado), 'actual': actual.GetName() if actual else None}
'''


def entrar():
    """Abre el proyecto temporal. Devuelve {'previo': nombre del que había, 'actual': el temporal}."""
    ok, r, err = resolve_mcp.script(_ENTRAR % {'temp': TEMP}, timeout=90)
    if not ok:
        raise RuntimeError(err)
    if r.get('previo') and r['previo'] != TEMP:
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps(r), encoding='utf-8')
    if r.get('actual') != TEMP:                  # v5.5: CreateProject puede fallar (Resolve recién abierto, diálogo...): seguir probando aquí sería hacerlo en el proyecto REAL del usuario
        raise RuntimeError(f"No pude abrir el proyecto temporal «{TEMP}» (sigue abierto «{r.get('actual')}»): no pruebo nada.")
    return r


def salir():
    """Cierra y borra el temporal y vuelve a cargar el proyecto que había."""
    previo = None
    try:
        previo = json.loads(ESTADO.read_text(encoding='utf-8')).get('previo')
    except Exception:
        pass
    ok, r, err = resolve_mcp.script(_SALIR % {'temp': TEMP, 'previo': previo}, timeout=90)
    return r if ok else err
