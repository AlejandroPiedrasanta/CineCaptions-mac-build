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
def escribir_sidecar(ruta_json, obj):
    """Escribe SOLO el sidecar `<ruta_json>.lua` (el .json ya lo escribio quien\n    llama). Nunca lanza: si falla, el .json sigue sirviendo a 21.0.x/Studio."""
    from pathlib import Path
    try:
        ruta = Path(ruta_json)
        import archivos_seguros
        archivos_seguros.escribir_texto(ruta.with_name(ruta.name + '.lua'), a_lua(obj))
    except Exception:
        return None
def escribir_par(ruta_json, obj):
    """Escribe el `.json` (como siempre) Y el sidecar `<ruta>.lua`.\n\n    `ruta_json` es un Path o str al `.json`. El sidecar es `<ruta_json>.lua`,\n    colocado al lado para que el script lo encuentre por el mismo nombre + \'.lua\'.\n    NUNCA lanza por el sidecar: si falla, el `.json` ya quedo (21.0.x sigue).\n    """
    import json
    from pathlib import Path
    import archivos_seguros
    ruta = Path(ruta_json)
    archivos_seguros.escribir_json(ruta, obj, indent=2)
    try:
        archivos_seguros.escribir_texto(ruta.with_name(ruta.name + '.lua'), a_lua(obj))
    except Exception:
        return None
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
