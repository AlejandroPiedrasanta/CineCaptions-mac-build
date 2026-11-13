# CineCaptions · By Cinema Productions
# 1_codigo/sidecar_lua.py — escribe <archivo>.lua junto a cada .json (canal de lectura para Resolve Free 21.1).
"""Serializa un dict/list de Python a un `.lua` que `return`a la misma tabla.\n\nPor que existe (v3.1.5): Resolve Free 21.1 le quito `io` a los scripts del\nmenu. No pueden abrir archivos, pero SI pueden `loadfile` un `.lua` que\ndevuelve una tabla (unico canal de lectura que sobrevive, medido). Asi que\njunto a cada `.json` que un script Lua tiene que leer, la app deja tambien un\nsidecar `<ruta>.lua` con `return { ... }`. En 21.0.x/Studio se sigue leyendo\nel `.json`; el sidecar solo entra cuando falta `io`. Ver el bloque v3.1.5 de\nCLAUDE.md y [[resolve-21-1-free-menu-sin-escritura]].\n\nEl formato es un subconjunto de Lua que el `parsear_json` de los gemelos\ntambien podria comer, pero aqui va como tabla nativa: se carga con loadfile y\nya es la tabla, sin parsear. Claves siempre `[\"...\"]` (una clave con espacios\no que empieza por numero rompe la forma corta). Numeros tal cual; bool\ntrue/false; None -> se OMITE la clave (en Lua una clave a nil no existe, que\nes justo lo que quiere el lector: `manifest.pack` ausente == nil).\n"""
import math
def _cadena(s):
    out = ['\"']
    for ch in s:
        o = ord(ch)
        if ch == '\\':
            out.append('\\\\')
        else:
            if ch == '\"':
                out.append('\\\"')
            else:
                if ch == '\n':
                    out.append('\\n')
                else:
                    if ch == '\r':
                        out.append('\\r')
                    else:
                        if ch == '\t':
                            out.append('\\t')
                        else:
                            if o < 32:
                                out.append('\\%d' % o)
                            else:
                                out.append(ch)
    out.append('\"')
    return ''.join(out)
def _valor(v):
    if v is None:
        return 'nil'
    else:
        if v is True:
            return 'true'
        else:
            if v is False:
                return 'false'
            else:
                if isinstance(v, str):
                    return _cadena(v)
                else:
                    if isinstance(v, int):
                        return str(v)
                    else:
                        if isinstance(v, float):
                            if math.isinf(v) or math.isnan(v):
                                return '0'
                            else:
                                return repr(v)
                        else:
                            if isinstance(v, dict):
                                return _tabla(v)
                            else:
                                if isinstance(v, (list, tuple)):
                                    partes = [_valor(x) for x in v]
                                    return '{' + ', '.join(partes) + '}'
                                else:
                                    return _cadena(str(v))
def _tabla(d):
    partes = []
    for k, v in d.items():
        if v is not None:
            partes.append('[%s] = %s' % (_cadena(str(k)), _valor(v)))
    return '{' + ', '.join(partes) + '}'
def a_lua(obj):
    """Devuelve el texto `return { ... }` para escribir en el sidecar."""
    return 'return ' + _valor(obj) + '\n'
# v5.55 (Puente 1.0.42): el Free de un cliente llego SIN loadfile ni dofile en los scripts del menu y no leia ningun `<x>.json.lua`
# («Trabajos atendidos: 0»). Se AÑADE un segundo sidecar «<x>.json.free.lua» (el `.json.lua` de siempre se queda: lo leen los Puentes
# 1.0.41 o anteriores y loadfile/dofile, que no escriben en Fusion.prefs). Es UNA expresion-llamada, medida en Studio 21.1.2:
#   - bmd.readfile la evalua en su entorno aislado (fusion ahi es simbolico) y devuelve t, sincrono y sin escribir nada;
#   - fusion:RunScript la ejecuta con el fusion real y publica {ruta, t} en GetData("CineCaptions_sidecar") (asincrono).
# Reglas medidas: extension .lua (RunScript no corre otra), UTF-8 SIN BOM, nada de `return`/`local` fuera de la funcion ni sentencias
# detras (readfile da nil) y nada de valores funcion. `ruta` es la del .json: el lector la compara (sin mayusculas ni tipo de barra).
CLAVE_FREE = 'CineCaptions_sidecar'
def a_lua_free(obj, ruta_json):
    """Devuelve el texto del sidecar hibrido «<ruta_json>.free.lua» (ver arriba)."""
    return ('(function() local t = ' + _valor(obj) + ' if fusion then fusion:SetData("' + CLAVE_FREE + '", {ruta = '
            + _cadena(str(ruta_json)) + ', t = t}) end return t end)()\n')
def rutas_sidecar(ruta_json):
    """Los sidecars que acompañan a un .json: [<ruta>.lua, <ruta>.free.lua] (para borrarlos junto con el .json)."""
    from pathlib import Path
    ruta = Path(ruta_json)
    return [ruta.with_name(ruta.name + '.lua'), ruta.with_name(ruta.name + '.free.lua')]
def _escribir_sidecars(ruta, obj):
    """v5.85 (auditoría): True si quedaron los dos. Antes un fallo (el antivirus con el archivo abierto más de ~1 s) se tragaba y quedaba el
    sidecar del GO ANTERIOR: en Free 21.1 (sin `io`) es lo único que lee Resolve y colocaba lo de antes sin que nadie se enterara. Ahora el que
    no se pudo escribir se intenta BORRAR (mejor sin datos que con los viejos) y el fallo va al Registro (error en Free)."""
    import archivos_seguros
    fallos = []
    for destino, texto in ((ruta.with_name(ruta.name + '.lua'), lambda: a_lua(obj)),
                           (ruta.with_name(ruta.name + '.free.lua'), lambda: a_lua_free(obj, ruta))):
        try:
            archivos_seguros.escribir_texto(destino, texto())
        except Exception as e:
            fallos.append(f'{destino.name}: {type(e).__name__}: {e}')
            try:
                destino.unlink(missing_ok=True)
            except OSError:
                pass
    if fallos:
        _anotar_fallo(ruta, fallos)
    return not fallos
def _anotar_fallo(ruta, fallos):
    try:
        import registro
        from i18n import tr
        try:
            import resolve_mcp
            libre = resolve_mcp.ruta_exe() is None              # (Studio lee el .json: ahí el sidecar no hace falta)
        except Exception:
            libre = True
        texto = tr('No pude preparar «{f}» para DaVinci Resolve Free (otro programa, como el antivirus, lo tenía abierto). Vuelve a pulsar GO.',
                   f=getattr(ruta, 'name', str(ruta)))
        (registro.error if libre else registro.aviso)(texto, 'Resolve Free', detalle='\n'.join(fallos))
    except Exception:
        pass
def escribir_sidecar(ruta_json, obj):
    """Escribe SOLO los sidecars `<ruta_json>.lua` y `<ruta_json>.free.lua` (el .json ya lo escribio quien\n    llama). Nunca lanza: si falla, el .json sigue sirviendo a 21.0.x/Studio.
    v5.85: devuelve True si quedaron los dos (False: ver _escribir_sidecars)."""
    from pathlib import Path
    try:
        return _escribir_sidecars(Path(ruta_json), obj)
    except Exception:
        return False
def escribir_par(ruta_json, obj):
    """Escribe el `.json` (como siempre) Y el sidecar `<ruta>.lua`.\n\n    `ruta_json` es un Path o str al `.json`. El sidecar es `<ruta_json>.lua`,\n    colocado al lado para que el script lo encuentre por el mismo nombre + \'.lua\'.\n    NUNCA lanza por el sidecar: si falla, el `.json` ya quedo (21.0.x sigue).\n    """
    import json
    from pathlib import Path
    import archivos_seguros
    ruta = Path(ruta_json)
    archivos_seguros.escribir_json(ruta, obj, indent=2)
    try:
        return _escribir_sidecars(ruta, obj)
    except Exception:
        return False
if __name__ == '__main__':
    import lupa
    casos = [{'a': 1, 'b': 'hola', 'c': True, 'd': None, 'e': [1, 2, 'x']}, {'tracks': [{'style': 'din', 'data_path': 'C:\\x\\y.json', 'n': 3}], 'pack': None, 'texto': 'con \"comillas\" y\nsalto\ttab'}, {'1raro': 'clave que empieza por numero', 'con espacio': 9}, [], {'vacio': {}}]
    L = lupa.LuaRuntime(unpack_returned_tuples=True)
    for c in casos:
        texto = a_lua(c)
        chunk = L.eval('function(s) return load(s)() end')
        t = chunk(texto)
        def comparar(py, lua):
            if isinstance(py, dict):
                for k, v in py.items():
                    if v is None:
                        assert lua[k] is None, ('clave nil debe faltar', k)
                        continue
                    else:
                        comparar(v, lua[k])
            else:
                if isinstance(py, (list, tuple)):
                    for i, v in enumerate(py):
                        comparar(v, lua[i + 1])
                else:
                    if isinstance(py, bool):
                        assert bool(lua) == py, (py, lua)
                    else:
                        if isinstance(py, (int, float)):
                            assert abs(float(lua) - float(py)) < 1e-09, (py, lua)
                        else:
                            assert str(lua) == str(py), (repr(py), repr(lua))
        comparar(c, t)
    print('sidecar_lua: TODO EN VERDE')
