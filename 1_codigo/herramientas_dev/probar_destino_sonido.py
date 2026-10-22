# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_destino_sonido.py — valida el destino de Sonido antes de mutar pistas en Studio y Free.
"""Guardia del destino de Sonido: Resolve falso, Python y Lua con/sin io.

    python 1_codigo/herramientas_dev/probar_destino_sonido.py

Solo usa temporales y objetos falsos; nunca conecta con Resolve ni guarda preferencias.
"""
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parent
RAIZ = CODIGO.parent
sys.path[:0] = [str(AQUI), str(CODIGO)]

DESTINO = {'proyecto': 'zz_PRUEBAS_CC', 'timeline': 'T'}
CASOS = [
    ('sin destino conserva compatibilidad', None, None, True),
    ('destino de GO coincide', DESTINO, None, True),
    ('otro proyecto', dict(DESTINO, proyecto='Otro'), None, False),
    ('otro timeline', dict(DESTINO, timeline='Otro'), None, False),
    ('destino vacio', {}, None, False),
    ('destino mal formado', 'T', None, False),
    ('nombre vacio', dict(DESTINO, timeline=' '), None, False),
    ('ID coincide', dict(DESTINO, timeline_id='tl-1'), 'tl-1', True),
    ('mismo nombre con otro ID', dict(DESTINO, timeline_id='tl-1'), 'tl-2', False),
    ('ID no comprobable', dict(DESTINO, timeline_id='tl-1'), None, False),
]


def _plan(destino):
    plan = {'fps': 30, 'inicio': 86400, 'solo_ai': True, 'solo_audio': True, 'eventos': [], 'v1': []}
    if destino is not None:
        plan['destino_ai'] = destino
    return plan


def _foto(tl, mp):
    return json.dumps({'pistas': tl.pistas, 'items': [vars(x) for x in tl.items], 'operaciones': tl.operaciones,
                       'bins': [x.GetName() for x in mp.GetRootFolder().GetSubFolderList()]}, sort_keys=True, default=str)


def probar_python(casa):
    import resolve_falso as RF
    spec = importlib.util.spec_from_file_location('colocar_guardia', RAIZ / '2_recursos/efectos/colocar_efectos.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for nombre, destino, identificador, permitido in CASOS:
        r, p, tl, mp = RF.nuevo()
        tl.AddTrack('audio', 'stereo')
        tl.SetTrackName('audio', 2, 'AI SFX IMPACTS')
        tl.items.append(RF.Item('AI anterior', 86400, 30, 2, 'audio'))
        tl.operaciones.clear()
        if identificador is not None:
            tl.GetUniqueId = lambda: identificador
        ruta = casa / 'efectos_plan.json'
        ruta.write_text(json.dumps(_plan(destino)), encoding='utf-8')
        mod.RUTA_JSON, mod.resolve, mod.project = str(ruta), r, p
        antes = _foto(tl, mp)
        ok, error = True, ''
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                mod.main()
        except SystemExit as e:
            ok, error = False, str(e)
        assert ok is permitido, f'Python {nombre}: {error}'
        if not permitido:
            assert antes == _foto(tl, mp), f'Python {nombre}: altero pistas, clips o bins'
            assert 'Sonido no se aplico' in error, f'Python {nombre}: falta explicacion'
        print(f'PASA Python: {nombre}')
    # El proyecto inyectado por el trabajo puede ser anterior al proyecto actual.
    r, anterior, tl, mp = RF.nuevo()
    _, actual, tl_actual, mp_actual = RF.nuevo()
    actual.GetName = lambda: 'Otro'
    r.p = actual
    mod.resolve, mod.project = r, anterior
    ruta.write_text(json.dumps(_plan(DESTINO)), encoding='utf-8')
    fotos = _foto(tl, mp), _foto(tl_actual, mp_actual)
    try:
        mod.main()
    except SystemExit as e:
        assert 'Sonido no se aplico' in str(e)
    else:
        raise AssertionError('Python: no comprobo el proyecto actual')
    assert fotos == (_foto(tl, mp), _foto(tl_actual, mp_actual))
    print('PASA Python: reconsulta proyecto actual sin tocar el anterior ni el actual')
    return len(CASOS) + 1


def probar_transmision(casa):
    import efectos_visuales as EV
    import resolve_mcp as RM
    ruta = casa / 'transmision.json'
    info = {'proyecto': DESTINO['proyecto'], 'timeline': 'T', 'ancho': 1080, 'alto': 1920, 'fps': 30, 'inicio': 86400}
    with patch.object(EV, 'PLAN_JSON', ruta), patch.object(RM, 'ruta_exe', return_value='Resolve falso'), \
            patch.object(RM, 'script', return_value=(True, info, None)), patch.object(RM, 'ejecutar_py', return_value=(True, 'ok')):
        ok, mensaje = EV.aplicar(_plan(dict(DESTINO, timeline_id='tl-1')))
        assert ok, mensaje
    assert json.loads(ruta.read_text(encoding='utf-8'))['destino_ai'] == dict(DESTINO, timeline_id='tl-1')
    print('PASA transmision: destino_ai llega completo al plan que lee Resolve')
    return 1


def probar_lua(casa):
    from lupa import luajit21
    import probar_director_sonido as P
    import sidecar_lua
    carpeta = casa / 'DaVinciSubtitles'
    carpeta.mkdir(parents=True, exist_ok=True)
    for sin_io in (False, True):
        for nombre, destino, identificador, permitido in CASOS:
            lua = luajit21.LuaRuntime(unpack_returned_tuples=True)
            lua.globals().CASA = str(casa)
            lua.execute(P.LUA_FALSO)
            lua.execute('''
                preparar(1871, false, true)
                TL.pistas.audio[#TL.pistas.audio + 1] = {n="AI SFX IMPACTS", on=true, sub="stereo"}
                TL.items[#TL.items + 1] = nuevo_item("AI anterior", 86400, 30, #TL.pistas.audio, "audio")
                TOCO_MEDIA_POOL = 0
                local p = resolve:GetProjectManager():GetCurrentProject()
                local obtener = p.GetMediaPool
                function p:GetMediaPool() TOCO_MEDIA_POOL = TOCO_MEDIA_POOL + 1; return obtener(self) end
                function foto() return pistas_audio() .. "|" .. #TL.items .. "|" .. sfx_encendidos() end
                print = function(...) end
            ''')
            if identificador is not None:
                lua.globals().ID_ESPERADO = identificador
                lua.execute('function TL:GetUniqueId() return ID_ESPERADO end')
            antes = lua.globals().foto()
            plan = _plan(destino)
            (carpeta / 'efectos_plan.json').write_text(json.dumps(plan), encoding='utf-8')
            (carpeta / 'efectos_plan.json.lua').write_text(sidecar_lua.a_lua(plan), encoding='utf-8')
            ok, error = lua.globals().correr(str(RAIZ / '2_recursos/resolve_scripts/CineCaptions_Efectos.lua'), sin_io)
            if sin_io and not ok and 'CINECAPTIONS_REPORTE|' in str(error):
                reporte = json.loads(str(error).split('CINECAPTIONS_REPORTE|', 1)[1])
                ok, error = reporte['ok'], reporte.get('mensaje', '')
            assert bool(ok) is permitido, f'Lua sin_io={sin_io} {nombre}: {error}'
            if not permitido:
                assert lua.globals().TOCO_MEDIA_POOL == 0, f'Lua {nombre}: llego al Media Pool'
                assert antes == lua.globals().foto(), f'Lua {nombre}: altero pistas o clips'
                assert 'Sonido no se aplico' in str(error), f'Lua {nombre}: falta explicacion'
            print(f'PASA Lua {"sin io" if sin_io else "con io"}: {nombre}')
    return len(CASOS) * 2


def main():
    with tempfile.TemporaryDirectory(prefix='cc_destino_sonido_') as tmp:
        casa = Path(tmp)
        if '--solo-lua' in sys.argv:
            total = probar_lua(casa)
        else:
            total = probar_python(casa) + probar_transmision(casa)
            try:
                import lupa  # noqa: F401
            except ImportError:
                import probar_director_sonido as P
                interprete = P._lua_python()
                if not interprete:
                    raise RuntimeError('Falta lupa para verificar el gemelo Lua. Define CINECAPTIONS_LUPA_PY.')
                subprocess.run([interprete, str(Path(__file__).resolve()), '--solo-lua'], check=True)
                total += len(CASOS) * 2
            else:
                total += probar_lua(casa)
        print(f'{total}/{total} casos correctos; Resolve del usuario intacto.')


if __name__ == '__main__':
    main()
