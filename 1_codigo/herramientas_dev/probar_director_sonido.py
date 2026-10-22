# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_director_sonido.py — pruebas del «AI Sound Director» SIN pantalla y SIN el Resolve del usuario.
"""
    python probar_director_sonido.py [--fase 0|1|2|3|todo] [--video <ruta>] [--salida <carpeta>]

Todo va a la carpeta de salida (por defecto %TEMP%/cc_ai_sound): las preferencias se parchean en memoria, el Registro va a una lista (nunca a
cinecaptions.log) y el estado del director y sus copias, a la salida. Resolve: uno FALSO en memoria para colocar_efectos.py y LuaJIT (lupa) para
su gemelo .lua. Al final, un resumen PASA / FALLA y `informe.json` con las medidas.
"""
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parent
RAIZ = CODIGO.parent
sys.path.insert(0, str(CODIGO))

LOG = []
RESULTADOS = []
INFORME = {}


def ok(nombre, condicion, detalle=''):
    RESULTADOS.append((nombre, bool(condicion), str(detalle)))
    print(('  PASA  ' if condicion else '  FALLA ') + nombre + (f'  ({detalle})' if detalle else ''))
    return bool(condicion)


def entorno(salida):
    """Registro a una lista, preferencias en memoria, estado del director en la salida."""
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    import registro
    registro.anotar = lambda nivel, mensaje, origen='', detalle='': LOG.append((nivel, str(mensaje), origen))
    import ajustes_ui
    ajustes_ui.leer_prefs = lambda: dict(PREFS)
    ajustes_ui.guardar_prefs = lambda *a, **k: None
    import director_sonido_estado as E
    E.CARPETA = Path(salida) / 'sound_director'
    return E


PREFS = {}


def _principal(ruta, nombre):
    spec = importlib.util.spec_from_file_location(nombre, str(ruta))
    M = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = M
    spec.loader.exec_module(M)
    return M


def _git_show(ruta_repo, destino):
    r = subprocess.run(['git', 'show', f'HEAD:{ruta_repo}'], cwd=str(RAIZ), capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode('utf-8', 'replace'))
    Path(destino).write_bytes(r.stdout)
    return Path(destino)


class _Var:
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


def _app_falsa(M, plan_fx, plan_pro, video):
    """Lo mínimo de SubtitleApp para llamar a sus métodos de GO sin ventana."""
    F = types.SimpleNamespace(_efectos_plan=plan_fx, _pro_plan=plan_pro, video_var=_Var(str(video)), msg_queue=types.SimpleNamespace(put=lambda *a: None),
                              _ultimos_bloques=None, _recorte=None, _go_tl_listo=None, _ancho_timeline=1080, _alto_timeline=1920,
                              _plantilla_un_clic=lambda: 'Kinetic', _offset_frames=lambda: None)
    for n in ('_director_sonido_al_colocar', '_director_sonido_arrancar', '_rectificar_planes', '_colocar_efectos'):
        if hasattr(M.SubtitleApp, n):
            setattr(F, n, types.MethodType(getattr(M.SubtitleApp, n), F))
    return F


def _planes_de_muestra():
    fx = {'eventos': [{'tipo': 'intro', 'ini': 0.0, 'asset': 'fuga_de_luz'}, {'tipo': 'corte', 'ini': 3.2, 'asset': 'destello'},
                      {'tipo': 'icono', 'ini': 5.0, 'asset': 'creador'}, {'tipo': 'sonido', 'ini': 0.0, 'archivo': 'x.wav', 'dur': 1.6, 'asset': 'riser'},
                      {'tipo': 'sonido', 'ini': 3.1, 'archivo': 'y.wav', 'dur': 0.5, 'asset': 'whoosh'},
                      {'tipo': 'musica', 'ini': 0.0, 'archivo': 'm.wav', 'dur': 30.0, 'asset': 'musica.mp3'},
                      {'tipo': 'v1', 'zoom': 'suave', 'cortes': [3.2], 'transicion': 'zoom_blur'}],
          'duracion': 30.0, 'resumen': 'intro', 'zonas': [], 'video': 'v.mp4'}
    pro = {'piezas': [{'pieza': 'cifra', 'ini': 5.1, 'fin': 7.0, 'capa': 'delante'}, {'pieza': 'fondo', 'ini': 10.0, 'fin': 13.0, 'capa': 'fondo'},
                      {'pieza': 'orbita', 'ini': 0.2, 'fin': 2.8, 'capa': 'detras'}], 'duracion': 30.0}
    return fx, pro


# ---------------------------------------------------------------------------------------------------------------- fase 0
def fase0(salida):
    print('\n== FASE 0: interruptor, estado, esqueleto y fallback ==')
    E = entorno(salida)
    import shutil
    shutil.rmtree(E.CARPETA, ignore_errors=True)                     # cada corrida empieza sin estado del director
    import director_sonido as D
    PREFS.clear()
    os.environ.pop(D.ENV, None)
    ok('v5.37: encendido por defecto (prefs sin la clave: el director es el dueño del sonido)', D.activo() is True)
    PREFS[D.PREF] = False
    ok('apagado si el usuario lo apaga', D.activo() is False)
    PREFS[D.PREF] = True
    ok('encendido con la preferencia', D.activo() is True)
    os.environ[D.ENV] = '0'
    ok('la variable de entorno manda (0)', D.activo() is False)
    os.environ[D.ENV] = '1'
    PREFS.clear()
    ok('la variable de entorno manda (1)', D.activo() is True)
    os.environ[D.ENV] = '0'

    fx, pro = _planes_de_muestra()
    antes = copy.deepcopy(fx)
    ok('apagado: al_colocar devuelve el MISMO plan', D.al_colocar(fx, {'evento_voz': {'tipo': 'voz_ai'}}, 'v.mp4') is fx and fx == antes)
    ok('apagado: sin plan sigue sin plan', D.al_colocar(None, None, 'v.mp4') is None)
    ok('apagado: no escribe nada en disco', not (E.CARPETA / 'general.json').exists())
    os.environ[D.ENV] = '1'
    ok('encendido sin voz y sin nada pendiente: el MISMO plan', D.al_colocar(fx, {'evento_voz': None}, 'v.mp4') is fx)
    ev = {'tipo': 'voz_ai', 'ini': 0.0, 'archivo': 'voz.wav', 'dur': 30.0, 'asset': 'AI VOICE'}
    nuevo = D.al_colocar(fx, {'evento_voz': ev}, 'v.mp4')
    ok('encendido con voz: una COPIA con el evento voz_ai', nuevo is not fx and fx == antes and sum(1 for e in nuevo['eventos'] if e['tipo'] == 'voz_ai') == 1)
    metadatos = {'eventos', '_ai_sound_video', '_ai_sound_sesion', 'destino_ai'}
    ok('encendido con voz: lo visual del plan no cambia', [e for e in nuevo['eventos'] if e['tipo'] != 'voz_ai'] == antes['eventos']
       and {k: v for k, v in nuevo.items() if k not in metadatos} == {k: v for k, v in antes.items() if k not in metadatos})
    otra = D.al_colocar(nuevo, {'evento_voz': ev}, 'v.mp4')
    ok('re-aplicar no apila voz_ai', sum(1 for e in otra['eventos'] if e['tipo'] == 'voz_ai') == 1)
    preparado = E.cargar('v.mp4')
    ok('preparar voz no confirma la colocación: queda pendiente y sin marca general', preparado.get('pendiente_resolve') is True
       and not preparado.get('en_resolve') and E.general().get('voz_ai_puesta') is not True)
    ok('el acuse exitoso confirma la sesión actual', D.confirmar_colocacion(otra, True, 'Colocación simulada') is True)
    ok('marca «AI VOICE puesta» para poder devolver A1', E.general().get('voz_ai_puesta') is True)
    sin = D.al_colocar(None, {'evento_voz': ev}, 'v.mp4')
    ok('sin plan de Efectos: uno que solo lleva la voz (solo_ai)', sin and sin.get('solo_ai') and [e['tipo'] for e in sin['eventos']] == ['voz_ai'])
    os.environ[D.ENV] = '0'
    limpia = D.al_colocar(None, None, 'v.mp4')
    ok('apagado tras usarlo: plan que SOLO limpia (A1 vuelve)', limpia and limpia.get('solo_ai') and not limpia['eventos'])
    ok('… y la marca se borra', E.general().get('voz_ai_puesta') is False)
    ok('… la siguiente vez, el MISMO plan otra vez', D.al_colocar(fx, None, 'v.mp4') is fx)
    E.poner_general(voz_ai_puesta=True)
    ok('apagado tras usarlo con plan de Efectos: ese plan (colocar_efectos limpia)', D.al_colocar(fx, None, 'v.mp4') is fx and fx == antes)

    real = E.general
    E.general = lambda: (_ for _ in ()).throw(RuntimeError('prueba de fallo'))
    n0 = len(LOG)
    r = D.al_colocar(fx, None, 'v.mp4')
    E.general = real
    ok('fallback: una excepción devuelve el plan original', r is fx)
    ok('fallback: «[AI SOUND] fallback: motor original» en el Registro', any('[AI SOUND] fallback: motor original' in m for _n, m, _o in LOG[n0:]))
    ok('preparar nunca lanza (contexto vacío)', isinstance(D.preparar({}), dict))
    ok('preparar nunca lanza (contexto raro)', isinstance(D.preparar({'video': 12345, 'palabras': 'x'}), dict))

    # los ganchos del script principal, contra el código de HEAD (antes del director): apagado, mismos planes
    print('  (cargando el script principal actual y el de HEAD…)')
    os.environ[D.ENV] = '0'
    M = _principal(CODIGO / 'CineCaptions (script principal).py', 'cc_nuevo')
    viejo = _git_show('1_codigo/CineCaptions (script principal).py', CODIGO / '_cc_head_tmp.py')
    try:
        H = _principal(viejo, 'cc_head')
    finally:
        viejo.unlink()
    for con_pro in (False, True):
        fx1, pro1 = _planes_de_muestra()
        fx2, pro2 = copy.deepcopy(fx1), copy.deepcopy(pro1)
        A = _app_falsa(M, fx1, pro1 if con_pro else None, 'v.mp4')
        B = _app_falsa(H, fx2, pro2 if con_pro else None, 'v.mp4')
        A._director_sonido_arrancar('v.mp4', [], None, 'es')
        A._rectificar_planes()
        B._rectificar_planes()
        iguales = json.dumps(A._efectos_plan, sort_keys=True, default=str) == json.dumps(B._efectos_plan, sort_keys=True, default=str) and \
            json.dumps(A._pro_plan, sort_keys=True, default=str) == json.dumps(B._pro_plan, sort_keys=True, default=str)
        ok(f'apagado = HEAD: _rectificar_planes {"con" if con_pro else "sin"} PRO deja los mismos planes', iguales)
        ok(f'apagado: el plan de Efectos es el MISMO objeto ({"con" if con_pro else "sin"} PRO)', A._efectos_plan is fx1)
        ok('apagado: el director no arrancó ningún hilo', getattr(A, '_director_hilo', 'x') is None)
    for plan in (None, {'eventos': []}):
        A, B = _app_falsa(M, plan, None, 'v.mp4'), _app_falsa(H, copy.deepcopy(plan), None, 'v.mp4')
        ok(f'_colocar_efectos con plan {plan!r}: igual que HEAD (no coloca)', A._colocar_efectos() == B._colocar_efectos() == '')


# ---------------------------------------------------------------------------------------------------------------- material de prueba
def _palabras_de_cache(video):
    """Las palabras del video desde la caché de voz de la app (la transcripción que ya hizo GO), la de más palabras; o None."""
    mejor = None
    for f in (Path.home() / 'DaVinciSubtitles' / 'cache_voz').glob('*.json'):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        if str(d.get('video') or '') == Path(video).name and isinstance(d.get('palabras'), list):
            if mejor is None or len(d['palabras']) > len(mejor):
                mejor = d['palabras']
    return mejor


def _palabras_por_energia(x, sr):
    """«Palabras» de una voz sintética: tramos con voz (20 ms por encima del umbral) separados por ≥ 60 ms."""
    import numpy as np
    m = x.mean(axis=0) if x.ndim > 1 else x
    n = m.size // 960
    rms = 10 * np.log10(np.mean(m[:n * 960].reshape(n, 960).astype(np.float64) ** 2, axis=1) + 1e-12)
    voz = rms > (np.percentile(rms, 95) - 30)
    palabras, ini = [], None
    for i, v in enumerate(np.append(voz, False)):
        if v and ini is None:
            ini = i
        elif not v and ini is not None:
            if palabras and ini * 0.02 - palabras[-1]['end'] < 0.06:
                palabras[-1]['end'] = round(i * 0.02, 3)
            else:
                palabras.append({'start': round(ini * 0.02, 3), 'end': round(i * 0.02, 3), 'word': 'palabra'})
            ini = None
    return palabras


def _leer_todo(ruta, canales=1):
    import numpy as np
    import director_sonido_medir as M
    return np.concatenate(list(M.trozos(ruta, canales=canales)), axis=1)


def _ruido_rosa(n, rng):
    import numpy as np
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / 48000)
    X[1:] /= np.sqrt(f[1:])
    X[0] = 0
    y = np.fft.irfft(X, n)
    return (y / np.sqrt(np.mean(y ** 2))).astype(np.float32)


def _ruido_hvac(n, rng):
    """Aire acondicionado / ventilador: ruido rosa estable con los agudos caídos por encima de ~1,5 kHz."""
    import numpy as np
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / 48000)
    X[1:] /= np.sqrt(f[1:]) * (1 + (f[1:] / 1500.0) ** 2) ** 0.5
    X[0] = 0
    y = np.fft.irfft(X, n)
    return (y / np.sqrt(np.mean(y ** 2))).astype(np.float32)


def _nivel(x):
    import numpy as np
    return 10 * np.log10(np.mean(np.asarray(x, np.float64) ** 2) + 1e-12)


def _a_db(x, db_objetivo):
    import numpy as np
    return (x * 10 ** ((db_objetivo - _nivel(x)) / 20)).astype(np.float32)


def _musica_sintetica(n, rng):
    """Una cama musical: bajo (La, Mi, Re, Do), acordes con ataque lento, bombo cada 0,5 s y charles."""
    import numpy as np
    sr = 48000
    t = np.arange(n) / sr
    y = np.zeros(n, np.float64)
    progresion = [(55.0, (220.0, 261.6, 329.6)), (82.4, (246.9, 329.6, 415.3)), (73.4, (220.0, 293.7, 349.2)), (65.4, (196.0, 261.6, 329.6))]
    for k in range(int(n / sr / 2) + 1):
        a, b = int(k * 2 * sr), min(n, int((k + 1) * 2 * sr))
        if a >= n:
            break
        bajo, acorde = progresion[k % 4]
        tt = t[a:b] - t[a]
        env = np.minimum(1.0, tt / 0.3) * np.exp(-tt * 0.3)
        y[a:b] += 0.5 * np.sin(2 * np.pi * bajo * tt) * env
        for fr in acorde:
            y[a:b] += 0.15 * np.sin(2 * np.pi * fr * tt) * env + 0.05 * np.sin(4 * np.pi * fr * tt) * env
    for k in range(int(n / (0.5 * sr))):
        a = int(k * 0.5 * sr)
        tt = np.arange(min(int(0.25 * sr), n - a)) / sr
        y[a:a + tt.size] += 0.8 * np.sin(2 * np.pi * (50 + 60 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 12)
        h = a + int(0.25 * sr)
        if h < n:
            m = min(int(0.04 * sr), n - h)
            y[h:h + m] += 0.08 * rng.standard_normal(m) * np.exp(-np.arange(m) / sr * 80)
    return y.astype(np.float32)


def _ambiente(nombre, n):
    """Un ambiente de la biblioteca de sonidos del programa, en bucle hasta `n` muestras (mono)."""
    import numpy as np
    ruta = CODIGO.parent / '2_recursos' / 'sfx_library' / 'Ambientes' / nombre
    a = _leer_todo(ruta, 1)[0]
    rep = int(np.ceil(n / a.size))
    return np.tile(a, rep)[:n].astype(np.float32)


def casos_sinteticos(salida):
    """Los casos de voz limpia + fondo (WAV estéreo dual mono, como un video) con lo que se espera de cada uno."""
    import numpy as np
    import director_sonido_medir as M
    carpeta = Path(salida) / 'casos'
    voz_wav = carpeta / 'voz_limpia_sapi.wav'
    if not voz_wav.is_file():
        r = subprocess.run([sys.executable, str(Path(__file__).with_name('_voz_sapi.py')), str(voz_wav)], capture_output=True, text=True)
        if not voz_wav.is_file():
            raise RuntimeError('no hay voz SAPI: ' + r.stderr[-300:])
    voz = _leer_todo(voz_wav, 1)[0]
    voz = _a_db(voz, -20.0)
    n = voz.size
    rng = np.random.default_rng(7)
    palabras = _palabras_por_energia(voz[None, :], 48000)
    t = np.arange(n) / 48000
    hum = (0.6 * np.sin(2 * np.pi * 60 * t) + 0.3 * np.sin(2 * np.pi * 120 * t) + 0.2 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)
    fondos = {
        'limpia': (_a_db(_ruido_rosa(n, rng), -78.0), {'musica': False, 'ruido': ('bajo',), 'ambiente': ('QUIET_INTERIOR', 'INTERIOR', 'ROOM', 'STUDIO')}),
        'ruido_hum': (_a_db(_ruido_rosa(n, rng), -38.0) + _a_db(hum, -40.0), {'musica': False, 'ruido': ('moderado', 'alto'), 'hum': 60}),
        'musica_mezclada': (_a_db(_musica_sintetica(n, rng), -33.0), {'musica': True}),
        'calle': (_a_db(_ambiente('Ambient - City Nightlife.mp3', n), -36.0), {'musica': None, 'ambiente': ('STREET', 'CITY', 'TRAFFIC', 'CROWD', 'CAFE', 'EVENT')}),
        'naturaleza': (_a_db(_ambiente('Ambient - Evening Crickets.mp3', n), -40.0), {'musica': False, 'ambiente': ('NATURE', 'FOREST', 'PARK', 'WATER')}),
        'interior_ventilador': (_a_db(_ruido_hvac(n, rng), -46.0),
                                {'musica': False, 'ambiente': ('INTERIOR', 'ROOM', 'OFFICE', 'STUDIO', 'QUIET_INTERIOR')}),
    }
    casos = {}
    for nombre, (fondo, espera) in fondos.items():
        ruta = carpeta / f'{nombre}.wav'
        mezcla = np.clip(voz + fondo, -1, 1)
        W = M.EscritorWav(ruta, 2)
        W.escribir(np.vstack((mezcla, mezcla)))
        W.cerrar()
        casos[nombre] = (ruta, palabras, espera)
    return casos


# ---------------------------------------------------------------------------------------------------------------- fase 1
TEMAS = ('Kinetic', 'Referencia', 'VIRAL', 'Tema4', 'Tema5', 'Tema6')


def fase1(salida, video):
    print('\n== FASE 1: análisis (tema, identidad, voz, ruido, música, ambiente, captions, motions, narrativa) ==')
    E = entorno(salida)
    import director_sonido as D
    import ia_texto
    ia_texto.disponible = lambda: False                              # el arnés nunca arranca la IA local
    os.environ[D.ENV] = '1'
    PREFS.clear()
    medidas = {}
    # --- casos sintéticos
    for nombre, (ruta, palabras, espera) in casos_sinteticos(salida).items():
        t = time.time()
        ctx = D.contexto(ruta, palabras, 'Referencia', 'v', timeline_de_go=True)
        a, _interno = D.analizar(ctx)                                 # la FASE 1 sola: solo análisis
        res = {'evento_voz': None}
        seg = time.time() - t
        if not ok(f'[{nombre}] el análisis termina sin error', bool(a), f'{seg:.2f} s'):
            continue
        v, mu, amb = a['voz'], a['musica']['en_la_fuente'], a['ambiente']
        medidas[nombre] = {'voz': {k: v.get(k) for k in ('nivel_voz_db', 'suelo_ruido_db', 'snr_db', 'ruido', 'noise_score', 'hum', 'sibilancia', 'problemas')},
                           'loudness': v.get('loudness'), 'musica': {k: mu[k] for k in ('presente', 'confianza')},
                           'ambiente': [(e['contexto'], e['decision']) for e in amb['escenas']], 'segundos': round(seg, 2)}
        if espera.get('musica') is not None:
            ok(f"[{nombre}] música {'presente' if espera['musica'] else 'ausente'}", mu['presente'] == espera['musica'],
               f"confianza {mu['confianza']}: {'; '.join(mu['motivos'][:2])}")
        if espera.get('ruido'):
            ok(f'[{nombre}] ruido {"/".join(espera["ruido"])}', v.get('ruido') in espera['ruido'], f"noise_score {v.get('noise_score')}, SNR {v.get('snr_db')} dB, {v.get('problemas')}, hiss {v.get('hiss')}, viento {v.get('viento')}, hum {v.get('hum')}")
        if espera.get('hum'):
            ok(f"[{nombre}] hum de {espera['hum']} Hz", (v.get('hum') or {}).get('hz') == espera['hum'] and (v.get('hum') or {}).get('fuerza_db', 0) >= 8,
               str(v.get('hum')))
        if espera.get('ambiente'):
            ctxs = [e['contexto'] for e in amb['escenas']]
            ok(f"[{nombre}] ambiente {'/'.join(espera['ambiente'][:3])}…", all(c in espera['ambiente'] for c in ctxs),
               f'{ctxs} <- {amb["escenas"][0]["fuentes"]} · fondo {amb["escenas"][0]["audio"]}')
        ok(f'[{nombre}] nunca AÑADE ambiente sin coherencia', all(e['decision'] != 'ADD_SUBTLE_AMBIENCE' or e['audio'] and e['audio']['nivel_db'] < -80
                                                                  for e in amb['escenas']))
        ok(f'[{nombre}] fase 1 no cambia el audio (no crea ninguna copia)', not list(E.carpeta_de(ruta).glob('*.wav')) if E.carpeta_de(ruta).exists() else True)
    # «se dice calle» con el audio limpio: no se inventa la calle
    ruta, palabras, _e = casos_sinteticos(salida)['limpia']
    dichas = [dict(p, word=w) for p, w in zip(palabras, ['Estoy', 'en', 'la', 'calle', 'con', 'mucho', 'tráfico'] * 50)]
    res = D.preparar(D.contexto(ruta, dichas, 'Referencia', 'v'))
    escenas = (res.get('analisis') or {}).get('ambiente', {}).get('escenas') or []
    ok('[texto «calle» + audio limpio] no inventa ambiente de calle', escenas and all(e['decision'] in ('LEAVE_SILENT', 'KEEP_ORIGINAL_AMBIENCE') for e in escenas),
       str([(e['contexto'], e['decision'], e['por_que'][:60]) for e in escenas]))
    # --- fuentes de música (estrategia del usuario): sin proveedor autorizado nunca ADD_NEW ni la música local legacy; la clave nunca se escribe
    ruta, pal_l, _e = casos_sinteticos(salida)['limpia']
    os.environ.pop('EPIDEMIC_API_KEY', None)
    import director_sonido_epidemic as EP
    EP._olvidar()
    EP._de_dotenv = lambda: None                                    # (un .env real del proyecto no cuenta en la prueba)
    a, _i = D.analizar(D.contexto(ruta, pal_l, 'Kinetic', 'v'))
    ms = a['musica']['estado_sugerido']
    ok('música: sin proveedor autorizado no se añade (y la local es legacy)', ms['estado'] != 'ADD_NEW' and a['musica']['proveedores']['legacy_local'] == 'DISABLED_FOR_NEW_DESIGN',
       ms['por_que'][:140])
    secreto = 'clave-de-prueba-NO-DEBE-APARECER-7731'
    os.environ['EPIDEMIC_API_KEY'] = secreto
    try:
        n0 = len(LOG)
        res = D.preparar(D.contexto(ruta, pal_l, 'Kinetic', 'v', timeline_de_go=True))
        ms = res['analisis']['musica']['estado_sugerido']
        ok('música: con proveedor autorizado y necesidad, ADD_NEW', ms['estado'] == 'ADD_NEW', ms['por_que'][:140])
        ok('la clave de Epidemic nunca se escribe (estado ni Registro)', secreto not in E.ruta_de(ruta).read_text(encoding='utf-8')
           and not any(secreto in m for _n, m, _o in LOG[n0:]))
    finally:
        os.environ.pop('EPIDEMIC_API_KEY', None)
        import director_sonido_epidemic as EP
        EP._olvidar()
    # --- el video real con los 6 temas
    palabras = _palabras_de_cache(video)
    ok('video de prueba con su transcripción (caché de voz de la app)', bool(palabras), f'{len(palabras or [])} palabras')
    if not palabras or not Path(video).is_file():
        return
    import efectos_visuales
    import edicion_pro_planificador as PL
    import vista_tema
    t = time.time()
    cortes = [c[0] for c in efectos_visuales.detectar_cortes(str(video))]
    INFORME['cortes_detectados'] = cortes
    print(f'  (cortes del video, como los busca GO: {len(cortes)} en {time.time() - t:.1f} s)')
    dur = float(palabras[-1]['end'])
    try:
        plan_fx = efectos_visuales.planificar(str(video), palabras, cortes=[(c, 1.0) for c in cortes])
    except Exception as e:
        plan_fx = None
        print('  (sin plan de Efectos:', e, ')')
    try:
        plan_pro = PL.planificar(palabras, dur, idioma='es', vertical=True, video=str(video), cortes=cortes)
    except Exception as e:
        plan_pro = None
        print('  (sin plan PRO:', e, ')')
    perfiles = {}
    for pack in TEMAS:
        estilo = vista_tema.estilo_de_pack(pack, 'v')
        try:
            cues = vista_tema.planificar(palabras, {}, pack, estilo, idioma='es', fin_video=dur, video=str(video)) if estilo else []
        except Exception as e:
            cues = []
            print(f'  ({pack}: sin cues del planificador: {type(e).__name__}: {e})')
        fx0, pro0 = copy.deepcopy(plan_fx), copy.deepcopy(plan_pro)
        ctx = D.contexto(video, palabras, pack, 'v', timeline_de_go=True, bloques=cues, plan_efectos=plan_fx, plan_pro=plan_pro, cortes=cortes, idioma='es')
        ctx['cortes'] = cortes
        t = time.time()
        res = D.preparar(ctx)
        seg = time.time() - t
        a = res.get('analisis') or {}
        if not ok(f'[{pack}] análisis completo', bool(a), f'{seg:.2f} s'):
            continue
        import plantillas
        ok(f'[{pack}] tema detectado «{plantillas.FABRICA[pack]}»', a['tema'] == plantillas.FABRICA[pack], f"estilo {a['rasgos']['estilo']}, PRO {a['rasgos']['modo_pro']}")
        ok(f'[{pack}] captions leídos ({len(cues)})', a['captions']['n'] == len(cues), f"{a['captions']['con_sonido']} con sonido, campos {a['captions']['campos'][:6]}")
        ok(f'[{pack}] motions leídos con su metadata', a['motions']['n'] > 0 and any(c.startswith('pro.') for c in a['motions']['campos']),
           f"{a['motions']['por_origen']} · {[c for c in a['motions']['campos'] if 'valores' in c][:5]}")
        ok(f'[{pack}] narrativa con HOOK', a['narrativa']['roles'].get('HOOK', 0) >= 1, str(a['narrativa']['roles']))
        ok(f'[{pack}] el análisis NO toca los planes de GO', plan_fx == fx0 and plan_pro == pro0)
        ok(f'[{pack}] estado sound_design_project guardado', E.ruta_de(video).is_file() and E.cargar(video).get('tema') == a['tema'])
        perfiles[pack] = a['perfil']['valores']
        medidas[f'video_{pack}'] = {'perfil': a['perfil']['resumen'], 'paleta': a['paleta']['valores'], 'ajustes_paleta': a['paleta']['ajustes'],
                                    'musica': a['musica']['estado_sugerido'], 'ambiente': a['ambiente']['resumen'], 'segundos': round(seg, 2)}
    if len(perfiles) == 6:
        ok('identidad derivada: Tema 1 (kinetic) pega más que Tema 2 (palabra a palabra)', perfiles['Kinetic']['impacto'] > perfiles['Referencia']['impacto'])
        ok('identidad derivada: Tema 2 (toque en cada palabra) más denso que Tema 3 (solo la clave)', perfiles['Referencia']['densidad'] > perfiles['VIRAL']['densidad'])
        ok('identidad derivada: Tema 6 (editorial) más suave que Tema 1', perfiles['Tema6']['transitorios'] < perfiles['Kinetic']['transitorios'])
        ok('identidad derivada: los 6 perfiles son distintos', len({json.dumps(p, sort_keys=True) for p in perfiles.values()}) == 6)
    a = (D.preparar(D.contexto(video, palabras, 'Kinetic', 'v', timeline_de_go=True)) or {}).get('analisis') or {}
    mu = (a.get('musica') or {}).get('en_la_fuente') or {}
    ok('PRUEBA ESPAÑOL: música ya mezclada con la voz (bajo en los huecos)', mu.get('presente') is True, f"confianza {mu.get('confianza')}: {mu.get('motivos')}")
    INFORME['fase1'] = medidas


# ---------------------------------------------------------------------------------------------------------------- fase 2
def _sha(ruta):
    import hashlib
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def _desfase_muestras(a, b, max_lag=2400):
    """El desfase (muestras) entre dos señales por correlación cruzada (FFT) en los primeros 20 s."""
    import numpy as np
    n = min(a.size, b.size, 48000 * 20)
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    m = 1 << int(np.ceil(np.log2(2 * n)))
    c = np.fft.irfft(np.fft.rfft(a, m) * np.conj(np.fft.rfft(b, m)), m)
    c = np.concatenate((c[-max_lag:], c[:max_lag + 1]))
    return int(np.argmax(c)) - max_lag


def _colocar_py(ruta_script, plan, tl_mp, fps=30.0):
    """Corre colocar_efectos.py (el de ahora o el de HEAD) contra el Resolve falso. Devuelve (ok, salida impresa)."""
    import io
    import contextlib
    import resolve_falso as RF
    resolve, proyecto, tl, mp = tl_mp
    spec = importlib.util.spec_from_file_location(f'colocar_{abs(hash(str(ruta_script)))}', str(ruta_script))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    tmp = Path(tempfile.mkdtemp()) / 'efectos_plan.json'
    datos = dict({'fps': fps, 'inicio': tl.GetStartFrame(), 'offset_frames': 0, 'v1': [], 'solo_audio': False, 'solo_ai': False}, **plan)
    tmp.write_text(json.dumps(datos), encoding='utf-8')
    mod.RUTA_JSON = str(tmp)
    mod.resolve, mod.project = resolve, proyecto
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            mod.main()
        return True, out.getvalue()
    except SystemExit as e:
        return False, out.getvalue() + f' [SystemExit {e}]'


LUA_FALSO = r'''
local og = os.getenv
os.getenv = function(k) if k == "USERPROFILE" or k == "HOME" then return CASA end return og(k) end
function nuevo_item(n, ini, dur, pista, tipo)
  local it = {n=n, ini=ini, dur=dur, pista=pista, tipo=tipo, comps={"Composition 1"}, props={}, on=true}
  function it:GetClipEnabled() return self.on end
  function it:SetClipEnabled(v) self.on = v; return true end
  function it:GetStart() return self.ini end
  function it:GetEnd() return self.ini + self.dur end
  function it:GetDuration() return self.dur end
  function it:GetName() return self.n end
  function it:SetName(x) self.n = x; return true end
  function it:SetProperty(k, v) self.props[k] = v; return true end
  function it:GetFusionCompNameList() local r = {} for i, v in ipairs(self.comps) do r[i] = v end return r end
  function it:DeleteFusionCompByName(x) return true end
  function it:ImportFusionComp(r) return {} end
  function it:RenameFusionCompByName(a, b) return true end
  function it:LoadFusionCompByName(x) return true end
  function it:SetFusionOutputCache(v) return true end
  return it
end
function nuevo_resolve(frames_a1, otra_pista)
  local tl = {pistas = {video = {{n="V1", on=true}}, audio = {{n="A1", on=true, sub="stereo"}}}, items = {}}
  tl.items[1] = nuevo_item("video", 86400, frames_a1, 1, "video")
  tl.items[2] = nuevo_item("voz", 86400, frames_a1, 1, "audio")
  if otra_pista then
    tl.pistas.audio[2] = {n="Musica del usuario", on=true, sub="stereo"}
    tl.items[3] = nuevo_item("musica.wav", 86400, frames_a1, 2, "audio")
  end
  function tl:GetName() return "T" end
  function tl:GetSetting(k) if k == "timelineFrameRate" then return "30" end return nil end
  function tl:GetStartFrame() return 86400 end
  function tl:GetTrackCount(t) return #self.pistas[t] end
  function tl:GetTrackName(t, i) return (self.pistas[t][i] or {}).n or "" end
  function tl:SetTrackName(t, i, x) self.pistas[t][i].n = x; return true end
  function tl:AddTrack(t, s) table.insert(self.pistas[t], {n="", on=true, sub=s}); return true end
  function tl:DeleteTrack(t, i)
    table.remove(self.pistas[t], i)
    local r = {}
    for _, x in ipairs(self.items) do
      if not (x.tipo == t and x.pista == i) then
        if x.tipo == t and x.pista > i then x.pista = x.pista - 1 end
        r[#r + 1] = x
      end
    end
    self.items = r; return true
  end
  function tl:GetIsTrackLocked(t, i) return false end
  function tl:SetTrackLock(t, i, v) return true end
  function tl:SetTrackEnable(t, i, v) if v or not NO_APAGA then self.pistas[t][i].on = v end return true end
  function tl:GetIsTrackEnabled(t, i) return self.pistas[t][i].on end
  function tl:GetItemListInTrack(t, i) local r = {} for _, x in ipairs(self.items) do if x.tipo == t and x.pista == i then r[#r + 1] = x end end return r end
  function tl:DeleteClips(xs, b)
    local fuera = {} for _, x in ipairs(xs) do fuera[x] = true end
    local r = {} for _, x in ipairs(self.items) do if not fuera[x] then r[#r + 1] = x end end
    self.items = r; return true
  end
  local clips, raiz = {}, {}
  function raiz:GetClipList() return clips end
  function raiz:GetSubFolderList() return {} end
  function raiz:GetName() return "raiz" end
  local mp = {}
  function mp:GetRootFolder() return raiz end
  function mp:AddSubFolder(r, n) local f = {} function f:GetClipList() return {} end function f:GetSubFolderList() return {} end function f:GetName() return n end return f end
  function mp:GetCurrentFolder() return raiz end
  function mp:SetCurrentFolder(f) return true end
  function mp:ImportMedia(rs)
    local c = {r = rs[1]}
    function c:GetClipProperty(k) if k == "File Path" then return self.r elseif k == "Frames" then return "30" elseif k == "FPS" then return "30" end return nil end
    clips[#clips + 1] = c; return {c}
  end
  function mp:AppendToTimeline(ps)
    local out = {}
    for _, p in ipairs(ps) do
      local tipo = p.mediaType == 1 and "video" or "audio"
      if not (tipo == "audio" and FALLA_APPEND) then
        local it = nuevo_item(p.mediaPoolItem.r, p.recordFrame, p.endFrame - p.startFrame + 1, p.trackIndex, tipo)
        tl.items[#tl.items + 1] = it; out[#out + 1] = it
      end
    end
    return out
  end
  local proj = {}
  function proj:GetName() return "zz_PRUEBAS_CC" end
  function proj:GetCurrentTimeline() return tl end
  function proj:GetMediaPool() return mp end
  local pm = {}
  function pm:GetCurrentProject() return proj end
  local r = {COMPOSITE_SCREEN = 6, COMPOSITE_MULTIPLY = 7, SCALE_FILL = 3}
  function r:GetProjectManager() return pm end
  return r, tl
end
function preparar(frames_a1, otra_pista, pista_sfx)
  resolve, TL = nuevo_resolve(frames_a1, otra_pista)
  if pista_sfx then                    -- los sonidos de Simple que dejó el script de subtítulos (pista «SFX», 3 toques)
    TL.pistas.audio[#TL.pistas.audio + 1] = {n="SFX", on=true, sub="stereo"}
    for k = 1, 3 do TL.items[#TL.items + 1] = nuevo_item("Hit.wav", 86400 + 30 * k, 15, #TL.pistas.audio, "audio") end
  end
end
function sfx_encendidos()
  local n = 0
  for _, x in ipairs(TL.items) do if x.tipo == "audio" and x.n == "Hit.wav" and x.on then n = n + 1 end end
  return n
end
function correr(ruta, sin_io)
  if sin_io then IO_GUARDADO = io end
  local f, e = loadfile(ruta)
  if not f then return false, e end
  if sin_io then io = nil end
  local ok, err = pcall(f)
  if sin_io then io = IO_GUARDADO end
  return ok, err
end
function pistas_audio()
  local out = {}
  for i, p in ipairs(TL.pistas.audio) do
    local n = 0
    for _, x in ipairs(TL.items) do if x.tipo == "audio" and x.pista == i then n = n + 1 end end
    out[#out + 1] = p.n .. "|" .. tostring(p.on) .. "|" .. tostring(p.sub) .. "|" .. n
  end
  return table.concat(out, ";")
end
'''


def _lua_python():
    """El Python con lupa (LuaJIT) para probar los .lua sin Resolve; None si no hay."""
    for c in [os.environ.get('CINECAPTIONS_LUPA_PY')] + [str(p) for p in Path(tempfile.gettempdir()).glob('claude/*/*/scratchpad/venv_lua/Scripts/python.exe')]:
        if c and Path(c).is_file():
            r = subprocess.run([c, '-c', 'import lupa'], capture_output=True)
            if r.returncode == 0:
                return c
    return None


LUA_PRUEBA = r'''
import json, sys, shutil
from pathlib import Path
from lupa import luajit21
lua_src, casa, falso, escenarios = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]).read_text(encoding='utf-8'), json.loads(Path(sys.argv[4]).read_text(encoding='utf-8'))
salida = []
for esc in escenarios:
    L = luajit21.LuaRuntime(unpack_returned_tuples=True)
    L.globals().CASA = str(casa)
    L.execute(falso)
    L.globals().preparar(esc['frames_a1'], esc.get('otra_pista', False), esc.get('pista_sfx', False))
    L.globals().FALLA_APPEND = esc.get('falla_append', False)
    L.globals().NO_APAGA = esc.get('no_apaga', False)
    resultados = []
    for k, plan in enumerate(esc['planes']):
        d = casa / 'DaVinciSubtitles'
        d.mkdir(parents=True, exist_ok=True)
        (d / 'efectos_plan.json').write_text(json.dumps(plan), encoding='utf-8')
        (d / 'efectos_plan.json.lua').write_text(esc['sidecars'][k], encoding='utf-8')
        ok, err = L.globals().correr(lua_src, esc.get('sin_io', False))
        if not ok and 'CINECAPTIONS_REPORTE|' in str(err) and '"ok":true' in str(err).replace(' ', ''):
            ok = True
        resultados.append({'ok': bool(ok), 'err': None if ok else str(err)[:300], 'audio': L.globals().pistas_audio(),
                           'sfx_encendidos': L.globals().sfx_encendidos()})
    salida.append({'nombre': esc['nombre'], 'resultados': resultados})
print('JSON' + json.dumps(salida))
'''


def _escenario_lua(nombre, frames_a1, planes, **kw):
    import sidecar_lua
    sidecars = []
    for p in planes:
        tmp = Path(tempfile.mkdtemp()) / 'efectos_plan.json'
        sidecar_lua.escribir_sidecar(tmp, p)
        sidecars.append(Path(str(tmp) + '.lua').read_text(encoding='utf-8'))
    return dict({'nombre': nombre, 'frames_a1': frames_a1, 'planes': planes, 'sidecars': sidecars}, **kw)


def fase2(salida, video):
    print('\n== FASE 2: voz restaurada (copia), AI VOICE y A1 seguro ==')
    import numpy as np
    E = entorno(salida)
    import director_sonido as D
    import director_sonido_medir as M
    import director_sonido_voz as V
    import ia_texto
    ia_texto.disponible = lambda: False
    os.environ[D.ENV] = '1'
    PREFS.clear()
    muestras = Path(MUESTRAS[0]) if MUESTRAS else Path(salida) / 'muestras'
    muestras.mkdir(parents=True, exist_ok=True)
    informe = {}
    casos = casos_sinteticos(salida)
    pruebas = [('PRUEBA_ESPAÑOL', Path(video), _palabras_de_cache(video), {'procesa': False}),
               ('limpia', casos['limpia'][0], casos['limpia'][1], {'procesa': False}),
               ('ruido_hum', casos['ruido_hum'][0], casos['ruido_hum'][1], {'procesa': True, 'baja_fondo': 10.0}),
               ('calle', casos['calle'][0], casos['calle'][1], {'procesa': True, 'baja_fondo': 4.0, 'tope': 6.0}),
               ('interior_ventilador', casos['interior_ventilador'][0], casos['interior_ventilador'][1], {'procesa': True, 'baja_fondo': 4.0}),
               ('musica_mezclada', casos['musica_mezclada'][0], casos['musica_mezclada'][1], {'procesa': False})]
    for nombre, ruta, pal, espera in pruebas:
        if not Path(ruta).is_file():
            ok(f'[{nombre}] archivo disponible', False, str(ruta))
            continue
        h0 = _sha(ruta)
        t = time.time()
        res = D.preparar(D.contexto(ruta, pal, 'Referencia', 'v', timeline_de_go=True))
        seg = time.time() - t
        v, ev = res.get('voz') or {}, res.get('evento_voz')
        ok(f'[{nombre}] el original NO se toca', _sha(ruta) == h0)
        a, d = v.get('antes') or {}, v.get('despues') or {}
        informe[nombre] = {'segundos': round(seg, 2), 'backend': v.get('backend'), 'nivel': v.get('nivel'), 'motivo': v.get('motivo'),
                           'cadena': [f"{c['filtro']} {c['opciones']}" for c in (v.get('cadena') or [])], 'antes': a, 'despues': d,
                           'guardas': (v.get('guardas') or {}).get('final', {}).get('medidas') if v.get('guardas') else None,
                           'intentos': [(i['fuerza'], i['pasa'], i['motivos'][:2]) for i in ((v.get('guardas') or {}).get('intentos') or [])]}
        if not espera['procesa']:
            ok(f'[{nombre}] se queda la voz original (nivel 0, sin AI VOICE)', ev is None and not v.get('archivo'), v.get('motivo'))
            continue
        if not ok(f'[{nombre}] voz restaurada (copia) y evento voz_ai', bool(ev) and Path(v.get('archivo') or '').is_file(), v.get('motivo')):
            continue
        ok(f'[{nombre}] el fondo baja ≥ {espera["baja_fondo"]} dB', (a.get('suelo_ruido_db') or 0) - (d.get('suelo_ruido_db') or 0) >= espera['baja_fondo'],
           f"{a.get('suelo_ruido_db')} → {d.get('suelo_ruido_db')} dBFS")
        if espera.get('tope'):
            nr = [c for c in v['cadena'] if c['filtro'] == 'nr_espectral']
            ok(f'[{nombre}] el ambiente que se conserva limita la reducción ({espera["tope"]:.0f} dB)', all(float(c['opciones'].split('=')[1].split(':')[0]) <= espera['tope'] for c in nr),
               '; '.join(c['opciones'] for c in nr))
        ok(f'[{nombre}] true peak ≤ −1 dBTP', d.get('tp_db') is not None and d['tp_db'] <= -1.0 + 0.05, f"{a.get('tp_db')} → {d.get('tp_db')} dBTP")
        ok(f'[{nombre}] nivel conservado (±1 LU) o llevado a −18…−12 LUFS', d.get('lufs') is not None and (abs(d['lufs'] - a['lufs']) <= 1.0 or -18.5 <= d['lufs'] <= -11.5),
           f"{a.get('lufs')} → {d.get('lufs')} LUFS")
        g = (v.get('guardas') or {}).get('final') or {}
        ok(f'[{nombre}] guardas antes/después: sin artefactos', not g.get('peor'), '; '.join(g.get('motivos') or []) or str({k: g.get('medidas', {}).get(k) for k in ('ruido_musical', 'envolvente_voz_corr', 'perdida_agudos_db')}))
        x0 = M.leer_wav(ruta) if str(ruta).lower().endswith('.wav') else M.trozos(ruta)
        orig = np.concatenate(list(x0), axis=1).mean(axis=0)
        nueva = np.concatenate(list(M.leer_wav(v['archivo'])), axis=1)
        ok(f'[{nombre}] dura exactamente lo mismo', nueva.shape[1] == orig.size, f'{nueva.shape[1]} / {orig.size} muestras')
        lag = _desfase_muestras(orig, nueva.mean(axis=0))
        ok(f'[{nombre}] sin desfase con el original (≤ 1 ms)', abs(lag) <= 48,
           f'{lag} muestras = {1000 * lag / 48000:.2f} ms: la fase del paso alto (IIR); la reducción de ruido, las muescas y el limitador dan 0')
        import wave
        with wave.open(v['archivo']) as w:
            ok(f'[{nombre}] WAV de 24 bits con los canales del original', w.getsampwidth() == 3 and w.getnchannels() == 2 and w.getframerate() == 48000,
               f'{w.getsampwidth() * 8} bits, {w.getnchannels()} canales, {w.getframerate()} Hz')
        import shutil
        shutil.copy(ruta, muestras / f'VOICE_ORIGINAL_{nombre}.wav')
        shutil.copy(v['archivo'], muestras / f'VOICE_AI_{nombre}.wav')
        if nombre == 'ruido_hum':
            hum_a = (a.get('hum') or {}).get('fuerza_db') or 0
            hum_d = (d.get('hum') or {}).get('fuerza_db') or 0
            ok('[ruido_hum] el hum de 60 Hz desaparece', hum_d < 8.0 and hum_d < hum_a - 6, f'+{hum_a} → +{hum_d} dB')
            t = time.time()
            res2 = D.preparar(D.contexto(ruta, pal, 'Referencia', 'v', timeline_de_go=True))
            ok('[ruido_hum] caché: la segunda vez no se procesa otra vez', (res2.get('voz') or {}).get('desde_cache') is True and res2['evento_voz'] == ev,
               f'{time.time() - t:.2f} s')
    INFORME['fase2'] = informe
    # --- la guarda revierte una reducción agresiva (voz metálica): se queda la original
    ruta, pal, _e = casos['ruido_hum']
    real = V.NivelPyAV.cadena
    V.NivelPyAV.cadena = lambda self, diag, fuerza=1.0, mezclada=False, con_nr=True: [('nr_espectral', 'reduccion=40:dd=0.5:suave=0', 'agresiva (prueba)')]
    try:
        r = V.restaurar(ruta, Path(salida) / 'casos' / 'agresiva.wav', None, pal)
    finally:
        V.NivelPyAV.cadena = real
    motivos = [m for i in (r.get('guardas') or {}).get('intentos') or [] for m in i['motivos']]
    ok('guarda: una reducción agresiva (metálica) se REVIERTE y queda la original', r.get('archivo') is None and r.get('nivel') == 0, f"{r.get('motivo')} · {motivos[:2]}")
    # --- con el audio del timeline (la mezcla de sus pistas) la voz no se sustituye
    res = D.preparar(D.contexto(ruta, pal, 'Referencia', 'v', timeline_de_go=False))
    ok('audio del timeline de Resolve: la voz original se queda', res.get('evento_voz') is None, (res.get('voz') or {}).get('motivo'))
    # --- fallback: si la restauración lanza, GO sigue con el plan original
    real = V.restaurar
    V.restaurar = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('fallo de prueba'))
    E.poner_general(voz_ai_puesta=False)
    estado_viejo = E.cargar(ruta)
    estado_viejo['voz'] = None
    E.guardar(ruta, estado_viejo)
    try:
        n0 = len(LOG)
        res = D.preparar(D.contexto(ruta, pal, 'Referencia', 'v', timeline_de_go=True))
        fx = {'eventos': [{'tipo': 'sonido', 'ini': 1.0, 'archivo': 'x.wav', 'dur': 0.5}]}
        con_sfx = D.al_colocar(fx, res, ruta) or {}                     # (fase 3: los sonidos del director sí van; la voz, no)
        sin_sfx = D.al_colocar(fx, dict(res, sfx=None), ruta)
        capas_ = ('AI MUSIC', 'AI AMBIENCE')                            # (v5.37: la cama de score / el ambiente del autor son capas propias del director)
        ok('fallback: la voz falla → sin evento y el plan de GO intacto', res.get('evento_voz') is None
           and [e for e in (sin_sfx or {}).get('eventos') or [] if e.get('pista') not in capas_] == fx['eventos']
           and not any(e.get('tipo') == 'voz_ai' for e in con_sfx.get('eventos') or []) and fx['eventos'][0] in con_sfx.get('eventos', []),
           [(e.get('tipo'), e.get('pista'), e.get('asset')) for e in con_sfx.get('eventos') or []][:6])
        ok('fallback: «[AI SOUND] fallback: motor original» en el Registro', any('fallback: motor original (voz)' in m for _n, m, _o in LOG[n0:]))
    finally:
        V.restaurar = real
    _fase2_resolve(salida, casos)
    _fase2_go(salida, casos)


def _fase2_go(salida, casos):
    """De punta a punta SIN el Resolve del usuario: los ganchos de GO (SubtitleApp) → plan de Efectos → efectos_visuales.aplicar → colocar_efectos.py
    contra el Resolve falso. Encendido: AI VOICE puesta y A1 apagada; apagado: el mismo plan y el timeline de siempre."""
    import threading
    import types
    import resolve_falso as RF
    import director_sonido as D
    import efectos_visuales
    import resolve_mcp
    ruta, pal, _e = casos['ruido_hum']
    M_ = sys.modules.get('cc_nuevo') or _principal(CODIGO / 'CineCaptions (script principal).py', 'cc_nuevo')
    tmp = Path(tempfile.mkdtemp())
    efectos_visuales.PLAN_JSON = tmp / 'efectos_plan.json'                 # nunca el ~/DaVinciSubtitles del usuario
    fps = 30.0
    dur = float(_leer_todo(ruta, 1).shape[1]) / 48000
    for encendido in (True, False):
        os.environ[D.ENV] = '1' if encendido else '0'
        E = entorno(salida)
        E.poner_general(voz_ai_puesta=False)
        R = RF.nuevo(frames_a1=int(round(dur * fps)))
        plan = {'eventos': [{'tipo': 'sonido', 'ini': 0.0, 'archivo': str(ruta), 'dur': 0.5, 'asset': 'riser'}], 'duracion': dur, 'resumen': '', 'zonas': [],
                'solo_audio': True, 'video': str(ruta)}
        antes = copy.deepcopy(plan)
        F = _app_falsa(M_, plan, None, ruta)
        F._go_tl_listo = threading.Event()                                   # GO armó el timeline con el video soltado
        F._director_sonido_arrancar(ruta, pal, None, 'es')
        F._director_sonido_al_colocar()
        nuevo = F._efectos_plan
        script = CODIGO.parent / '2_recursos' / 'efectos' / 'colocar_efectos.py'
        llamadas = {}
        real = (resolve_mcp.ruta_exe, resolve_mcp.script, resolve_mcp.ejecutar_py)
        info = {'timeline': 'T', 'ancho': 1080, 'alto': 1920, 'fps': fps, 'inicio': R[2].GetStartFrame()}
        resolve_mcp.ruta_exe = lambda: 'resolve_falso'
        resolve_mcp.script = lambda codigo, timeout=20: (True, info, None) if codigo is efectos_visuales._INFO_TIMELINE else (True, [], None)

        def ejecutar(ruta_script, timeout=600, **k):
            plan_r = json.loads(Path(efectos_visuales.PLAN_JSON).read_text(encoding='utf-8'))
            llamadas['plan'] = plan_r
            return _colocar_py(ruta_script, plan_r, R)
        resolve_mcp.ejecutar_py = ejecutar
        try:
            okk, msg = efectos_visuales.aplicar(nuevo, offset_frames=None)
        finally:
            resolve_mcp.ruta_exe, resolve_mcp.script, resolve_mcp.ejecutar_py = real
        tl = R[2]
        pistas = {p['nombre']: (p['on'], len(tl.GetItemListInTrack('audio', i + 1))) for i, p in enumerate(tl.pistas['audio'])}
        if encendido:
            ok('GO (encendido): el plan de Efectos lleva la voz restaurada', any(e.get('tipo') == 'voz_ai' for e in (nuevo or {}).get('eventos') or []))
            ok('GO (encendido): lo que no es voz del plan, intacto (más las capas de música/ambiente del director)',
               [e for e in nuevo['eventos'] if e['tipo'] != 'voz_ai' and e.get('pista') not in ('AI MUSIC', 'AI AMBIENCE')] == antes['eventos'],
               [(e.get('tipo'), e.get('pista'), e.get('asset')) for e in nuevo['eventos'] if e['tipo'] != 'voz_ai'][:6])
            ok('GO → Resolve (encendido): AI VOICE puesta y A1 apagada', okk and pistas.get('AI VOICE', (0, 0))[1] == 1 and pistas['A1'][0] is False, f'{pistas} · {str(msg)[-100:]}')
        else:
            ok('GO (apagado): el plan de Efectos es el MISMO objeto', nuevo is plan and nuevo == antes)
            ok('GO → Resolve (apagado): ni AI VOICE ni A1 tocada', okk and 'AI VOICE' not in pistas and pistas['A1'][0] is True, f'{pistas}')
            ok('GO → Resolve (apagado): el plan para Resolve no trae nada del director', not any(e.get('tipo') == 'voz_ai' or e.get('pista') for e in llamadas['plan']['eventos'])
               and llamadas['plan'].get('solo_ai') is False)


def _fase2_resolve(salida, casos):
    """AI VOICE en Resolve: colocar_efectos.py contra el Resolve falso, el gemelo .lua en LuaJIT y la regresión «apagado = HEAD»."""
    import resolve_falso as RF
    ruta, pal, _e = casos['ruido_hum']
    import director_sonido as D
    res = D.preparar(D.contexto(ruta, pal, 'Referencia', 'v', timeline_de_go=True))
    ev = res.get('evento_voz')
    if not ok('hay voz restaurada para probar la colocación', bool(ev)):
        return
    fps = 30.0
    frames = int(round(float(ev['dur']) * fps))
    script = CODIGO.parent / '2_recursos' / 'efectos' / 'colocar_efectos.py'
    voz = dict(ev, modo='audio')
    otros = [{'tipo': 'sonido', 'ini': 0.0, 'archivo': str(ruta), 'dur': 0.5, 'asset': 'riser', 'modo': 'audio'}]

    def pistas(tl):
        return {p['nombre']: (p['on'], len(tl.GetItemListInTrack('audio', i + 1)), p['sub']) for i, p in enumerate(tl.pistas['audio'])}
    # a) se pone y A1 se apaga DESPUÉS
    R = RF.nuevo(frames_a1=frames)
    okk, txt = _colocar_py(script, {'eventos': otros + [voz]}, R)
    tl = R[2]
    p = pistas(tl)
    ok('[py] AI VOICE puesta con un clip', okk and p.get('AI VOICE', (0, 0))[1] == 1, txt.strip()[-160:])
    ok('[py] A1 apagada solo DESPUÉS de verificar AI VOICE', p['A1'][0] is False and
       [o for o in tl.operaciones if o[0] in ('append', 'apagar')][-1][0] == 'apagar' and
       max(i for i, o in enumerate(tl.operaciones) if o[0] == 'append') < max(i for i, o in enumerate(tl.operaciones) if o[0] == 'apagar'))
    ok('[py] el clip de AI VOICE empieza con A1 y dura lo mismo', tl.GetItemListInTrack('audio', tl.pista('AI VOICE'))[0].GetStart() == tl.inicio)
    ok('[py] los sonidos de siempre siguen en FX-SONIDO', p.get('FX-SONIDO', (0, 0))[1] == 1)
    # b) re-aplicar no apila
    okk, txt = _colocar_py(script, {'eventos': otros + [voz]}, R)
    p = pistas(tl)
    ok('[py] re-aplicar: una sola pista AI VOICE con un solo clip', sum(1 for x in tl.pistas['audio'] if x['nombre'] == 'AI VOICE') == 1 and p['AI VOICE'][1] == 1 and p['A1'][0] is False)
    # f) director apagado: AI VOICE fuera y A1 vuelve
    okk, txt = _colocar_py(script, {'eventos': otros}, R)
    p = pistas(tl)
    ok('[py] director apagado: AI VOICE fuera y A1 vuelve a sonar', 'AI VOICE' not in p and p['A1'][0] is True, txt.strip()[-120:])
    # g) solo_ai: limpia solo lo suyo
    _colocar_py(script, {'eventos': otros + [voz]}, R)
    okk, txt = _colocar_py(script, {'eventos': [], 'solo_audio': True, 'solo_ai': True}, R)
    p = pistas(tl)
    ok('[py] plan de limpieza (solo_ai): quita AI VOICE, devuelve A1 y NO toca FX-SONIDO', okk and 'AI VOICE' not in p and p['A1'][0] is True and p.get('FX-SONIDO', (0, 0))[1] == 1)
    # c) AppendToTimeline falla → A1 encendida
    R = RF.nuevo(frames_a1=frames)
    R[3].falla_append_audio = True
    okk, txt = _colocar_py(script, {'eventos': [voz]}, R)
    p = pistas(R[2])
    ok('[py] si AI VOICE no entra: A1 sigue encendida y no queda pista AI VOICE', 'AI VOICE' not in p and p['A1'][0] is True and okk, txt.strip()[-120:])
    # d) Resolve no apaga A1 → se quita la copia (nunca dos voces)
    R = RF.nuevo(frames_a1=frames)
    R[2].no_apaga_pistas = True
    okk, txt = _colocar_py(script, {'eventos': [voz]}, R)
    p = pistas(R[2])
    ok('[py] si A1 no se deja apagar: la copia se quita (nunca dos voces)', 'AI VOICE' not in p and p['A1'][0] is True, txt.strip()[-120:])
    # e) otra pista de audio del usuario con clips → la voz no se sustituye
    R = RF.nuevo(frames_a1=frames)
    tl = R[2]
    tl.AddTrack('audio', 'stereo')
    tl.SetTrackName('audio', 2, 'Música del usuario')
    tl.items.append(RF.Item('musica.wav', tl.inicio, frames, 2, 'audio'))
    okk, txt = _colocar_py(script, {'eventos': [voz]}, R)
    p = pistas(tl)
    ok('[py] con otra pista de audio del usuario: la voz original se queda', 'AI VOICE' not in p and p['A1'][0] is True, txt.strip()[-140:])
    # j) la copia no cuadra con A1 (otro video) → no se pone
    R = RF.nuevo(frames_a1=frames + 90)
    okk, txt = _colocar_py(script, {'eventos': [voz]}, R)
    p = pistas(R[2])
    ok('[py] si la copia no cuadra con A1: no se pone y A1 sigue', 'AI VOICE' not in p and p['A1'][0] is True, txt.strip()[-140:])
    # h) A1 apagada por el usuario y sin AI VOICE: no se toca
    R = RF.nuevo(frames_a1=frames)
    R[2].SetTrackEnable('audio', 1, False)
    _colocar_py(script, {'eventos': otros}, R)
    ok('[py] A1 apagada por el usuario (sin AI VOICE): se respeta', R[2].GetIsTrackEnabled('audio', 1) is False)
    # i) apagado = HEAD: mismo plan sin cosas del director → mismo timeline
    viejo = Path(tempfile.mkdtemp()) / 'colocar_efectos_head.py'
    _git_show('2_recursos/efectos/colocar_efectos.py', viejo)
    plan = {'eventos': otros + [{'tipo': 'musica', 'ini': 0.0, 'archivo': str(ruta), 'dur': 20.0, 'asset': 'm', 'modo': 'audio'},
                                {'tipo': 'intro', 'ini': 0.0, 'archivo': str(ruta), 'asset': 'fuga', 'modo': 'screen'},
                                {'tipo': 'icono', 'ini': 2.0, 'secuencia': {'patron': str(ruta) + '%04d.png', 'n': 30}, 'asset': 'creador', 'modo': 'normal'}]}
    Ra, Rb = RF.nuevo(frames_a1=frames), RF.nuevo(frames_a1=frames)
    oa, ta = _colocar_py(script, copy.deepcopy(plan), Ra)
    ob, tb = _colocar_py(viejo, copy.deepcopy(plan), Rb)
    ok('apagado = HEAD: colocar_efectos.py deja el MISMO timeline', oa == ob and Ra[2].resumen() == Rb[2].resumen(), f'{Ra[2].resumen()["audio"]}')
    ok('apagado = HEAD: el mismo resumen impreso', ta.strip().splitlines()[-1:] == tb.strip().splitlines()[-1:], ta.strip().splitlines()[-1:])
    # resolve_mcp._ASEGURAR_AUDIO (final de GO en Studio): con AI VOICE, A1 sigue apagada; sin ella, se enciende como siempre
    import resolve_mcp
    for con_ai in (True, False):
        R = RF.nuevo(frames_a1=frames)
        tl = R[2]
        if con_ai:
            _colocar_py(script, {'eventos': [voz]}, R)
        else:
            tl.SetTrackEnable('audio', 1, False)
        g = {'project': R[1], 'resolve': R[0]}
        exec(resolve_mcp._ASEGURAR_AUDIO, g)
        if con_ai:
            ok('final de GO (asegurar_audio_original): con AI VOICE, A1 sigue apagada', tl.GetIsTrackEnabled('audio', 1) is False and g['result'].get('ai_voice') is True)
        else:
            ok('final de GO (asegurar_audio_original): sin AI VOICE, A1 se enciende como siempre', tl.GetIsTrackEnabled('audio', 1) is True)
    # --- el gemelo .lua (Resolve Free) en LuaJIT
    py = _lua_python()
    if not ok('LuaJIT (lupa) disponible para probar el .lua', bool(py), py or 'sin lupa'):
        return
    lua_src = CODIGO.parent / '2_recursos' / 'resolve_scripts' / 'CineCaptions_Efectos.lua'
    casa = Path(tempfile.mkdtemp())
    base = {'fps': fps, 'inicio': 86400, 'offset_frames': 0, 'v1': [], 'solo_audio': True}
    pv = dict(base, eventos=otros + [voz])
    po = dict(base, eventos=otros)
    pl = dict(base, eventos=[], solo_ai=True)
    escenarios = [_escenario_lua('pone y re-aplica', frames, [pv, pv]), _escenario_lua('apagar el director', frames, [pv, po]),
                  _escenario_lua('limpieza solo_ai', frames, [pv, pl]), _escenario_lua('falla el append', frames, [pv], falla_append=True),
                  _escenario_lua('A1 no se apaga', frames, [pv], no_apaga=True), _escenario_lua('pista del usuario', frames, [pv], otra_pista=True),
                  _escenario_lua('no cuadra', frames + 90, [pv]), _escenario_lua('Free sin io (sidecar)', frames, [pv], sin_io=True)]
    f_esc, f_prog, f_falso = casa / 'escenarios.json', casa / 'prueba_lua.py', casa / 'falso.lua'
    f_esc.write_text(json.dumps(escenarios), encoding='utf-8')
    f_prog.write_text(LUA_PRUEBA, encoding='utf-8')
    f_falso.write_text(LUA_FALSO, encoding='utf-8')
    r = subprocess.run([py, str(f_prog), str(lua_src), str(casa), str(f_falso), str(f_esc)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    linea = next((l for l in r.stdout.splitlines() if l.startswith('JSON')), None)
    if not ok('[lua] el gemelo corre en LuaJIT', bool(linea), (r.stderr or r.stdout)[-300:]):
        return
    res = {e['nombre']: e['resultados'] for e in json.loads(linea[4:])}

    def pistas_lua(txt):
        return {x.split('|')[0]: (x.split('|')[1] == 'true', int(x.split('|')[3]), x.split('|')[2]) for x in txt.split(';') if x}
    a1 = lambda rr: pistas_lua(rr['audio'])
    r1, r2 = res['pone y re-aplica']
    ok('[lua] AI VOICE puesta con un clip y A1 apagada', r1['ok'] and a1(r1).get('AI VOICE', (0, 0))[1] == 1 and a1(r1)['A1'][0] is False, r1['audio'] + str(r1['err'] or ''))
    ok('[lua] re-aplicar no apila', r2['ok'] and list(a1(r2)).count('AI VOICE') == 1 and r2['audio'].count('AI VOICE') == 1 and a1(r2)['AI VOICE'][1] == 1, r2['audio'])
    r1, r2 = res['apagar el director']
    ok('[lua] director apagado: AI VOICE fuera y A1 vuelve', r2['ok'] and 'AI VOICE' not in a1(r2) and a1(r2)['A1'][0] is True, r2['audio'])
    r1, r2 = res['limpieza solo_ai']
    ok('[lua] limpieza solo_ai: quita AI VOICE, A1 vuelve y FX-SONIDO se queda', r2['ok'] and 'AI VOICE' not in a1(r2) and a1(r2)['A1'][0] is True and a1(r2).get('FX-SONIDO', (0, 0))[1] == 1,
       r2['audio'])
    (r1,) = res['falla el append']
    ok('[lua] si AI VOICE no entra: A1 sigue encendida', 'AI VOICE' not in a1(r1) and a1(r1)['A1'][0] is True, r1['audio'] + str(r1['err'] or ''))
    (r1,) = res['A1 no se apaga']
    ok('[lua] si A1 no se deja apagar: la copia se quita', 'AI VOICE' not in a1(r1) and a1(r1)['A1'][0] is True, r1['audio'])
    (r1,) = res['pista del usuario']
    ok('[lua] con otra pista de audio del usuario: la voz original se queda', 'AI VOICE' not in a1(r1) and a1(r1)['A1'][0] is True, r1['audio'])
    (r1,) = res['no cuadra']
    ok('[lua] si la copia no cuadra con A1: no se pone', 'AI VOICE' not in a1(r1) and a1(r1)['A1'][0] is True, r1['audio'])
    (r1,) = res['Free sin io (sidecar)']
    ok('[lua] Free sin io (plan por sidecar): AI VOICE puesta y A1 apagada', r1['ok'] and a1(r1).get('AI VOICE', (0, 0))[1] == 1 and a1(r1)['A1'][0] is False,
       r1['audio'] + str(r1['err'] or ''))


MUESTRAS = []


# ---------------------------------------------------------------------------------------------------------------- fase 3
def _wav_info(ruta):
    import wave
    import numpy as np
    with wave.open(str(ruta), 'rb') as w:
        n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        b = np.frombuffer(w.readframes(n), np.uint8).reshape(-1, 3)
    x = (np.pad(b, ((0, 0), (0, 1))).view('<i4').reshape(-1) << 8 >> 8).astype(np.float64) / 8388608.0
    return {'canales': ch, 'bits': sw * 8, 'sr': sr, 'pico': float(np.abs(x).max()) if x.size else 0.0, 'dur': n / float(sr or 1)}


def fase3(salida, video):
    """AI SFX: qué suena y qué no (6 temas, metadata real), cada sonido a la medida en su WAV, decisiones sobre los sonidos de antes, el plan para
    Resolve (pistas AI SFX, Simple apagado, la PRO marcada), colocar_efectos.py contra el Resolve falso, el gemelo .lua en LuaJIT y GO de punta a punta."""
    print('== FASE 3: AI SFX (decisiones por evento, síntesis a la medida, híbrido, pistas AI) ==')
    import numpy as np
    E = entorno(salida)
    os.environ['CINECAPTIONS_AI_SOUND'] = '1'
    import director_sonido as D
    import director_sonido_diseno as D3
    import director_sonido_eventos as EV
    import efectos_visuales
    import edicion_pro_planificador as PL
    import vista_tema
    palabras = _palabras_de_cache(video)
    if not ok('video de prueba con su transcripción', bool(palabras) and Path(video).is_file()):
        return
    dur = float(palabras[-1]['end'])
    cortes = [c[0] for c in efectos_visuales.detectar_cortes(str(video))]
    plan_fx = efectos_visuales.planificar(str(video), palabras, cortes=[(c, 1.0) for c in cortes])
    plan_pro = PL.planificar(palabras, dur, idioma='es', vertical=True, video=str(video), cortes=cortes)
    medidas, resultados = {}, {}
    legacy = str(RAIZ / '2_recursos' / 'sfx_library').lower()
    for pack in TEMAS:
        estilo = vista_tema.estilo_de_pack(pack, 'v')
        cues = vista_tema.planificar(palabras, {}, pack, estilo, idioma='es', fin_video=dur, video=str(video)) if estilo else []
        for k, c in enumerate(cues):                                    # los «Hit» de Simple que GO deja hoy en cada caption
            c['sfx_eventos'] = [{'t': float(c.get('start') or 0.0), 'sfx': 'impacts', 'sfx_nombre': f'Hit {k % 5 + 1}.wav'}]
        fotos = copy.deepcopy((cues, plan_fx, plan_pro))
        ctx = D.contexto(video, palabras, pack, 'v', timeline_de_go=True, bloques=cues, plan_efectos=plan_fx, plan_pro=plan_pro, cortes=cortes, idioma='es')
        ctx['cortes'] = cortes
        t = time.time()
        res = D.preparar(ctx)
        seg = time.time() - t
        sfx = res.get('sfx') or {}
        dis = sfx.get('diseno') or {}
        r = dis.get('resumen') or {}
        resultados[pack] = (res, ctx, cues)
        if not ok(f'[{pack}] fase 3: diseño y sonidos hechos', bool(sfx.get('eventos')) and bool(r), f"{len(sfx.get('eventos') or [])} sonidos en {sfx.get('segundos')} s"):
            continue
        ok(f'[{pack}] la mayoría de los captions en silencio (LEAVE_SILENT)', r['en_silencio'] >= r['con_sonido'], f"{r['con_sonido']} con sonido / {r['captions']}")
        ok(f'[{pack}] el diseño no toca captions, Efectos ni la PRO', fotos == (cues, plan_fx, plan_pro))
        activos = [e for e in dis['eventos'] if e['decision'] == 'GENERATE']
        ids = {e['id'] for e in activos}
        ok(f'[{pack}] un WAV por sonido elegido (ni más ni menos)', ids == {x['ai']['id'] for x in sfx['eventos']}, f'{len(ids)} vs {len(sfx["eventos"])}')
        infos = [_wav_info(x['archivo']) for x in sfx['eventos']]
        ok(f'[{pack}] WAV 48 kHz, 24 bits, estéreo, pico ≤ −1 dBFS', all(i['sr'] == 48000 and i['bits'] == 24 and i['canales'] == 2 and i['pico'] <= 0.8913 for i in infos),
           f"pico máx {max(i['pico'] for i in infos):.3f}")
        ok(f'[{pack}] todo dentro del video y en pistas AI SFX', all(0.0 <= x['ini'] <= dur + 1.0 and str(x['pista']).startswith('AI SFX') for x in sfx['eventos']))
        ok(f'[{pack}] nada de la biblioteca legacy de la app (DISABLED_FOR_NEW_DESIGN)',
           not any(legacy in str((p.get('eleccion') or {}).get('archivo') or '').lower() for p in sfx['puestos']))
        tope = int(round(2 + 4 * dis['caracter']['densidad']))
        por_ventana = [sum(1 for e in activos if k0 <= e['ancla'] < k0 + 10 and e['origen'] not in ('gancho', 'cierre')) for k0 in np.arange(0, dur, 10.0)]
        ok(f'[{pack}] densidad: como mucho {tope} (+ gancho/cierre) por ventana de 10 s', max(por_ventana or [0]) <= tope + 1, f'{por_ventana}')
        hashes = {}
        for x in sfx['eventos']:
            hashes.setdefault(x['ai']['tipo'], []).append(_sha(x['archivo']))
        ok(f'[{pack}] anti-repetición: dos sonidos del mismo tipo nunca son el mismo clon (salvo el MOTIVO tonal, a propósito)',
           all(len(v) == len(set(v)) for k, v in hashes.items() if k != 'acento'), {k: f'{len(set(v))}/{len(v)}' for k, v in hashes.items()})
        viejos = dis['viejos']
        con = {c['cue'] for c in dis['captions'] if c['decision'] != 'LEAVE_SILENT'}
        ok(f'[{pack}] cada «Hit» de antes con su decisión (REPLACE en los que suenan, REMOVE en el resto)',
           len(viejos) == len(cues) and all((v['decision'] == 'REPLACE') == (v['cue'] in con) for v in viejos), r['viejos'])
        nivel = float(sfx['nivel_voz_db'])
        golpes = [x for x in sfx['eventos'] if x['ai']['tipo'] == 'golpe']
        if golpes:
            import director_sonido_medir as M
            import director_sonido_sintesis as S
            x = np.concatenate(list(M.leer_wav(golpes[0]['archivo'])), axis=1)
            ok(f'[{pack}] el golpe va bajo la voz (RMS < voz − 4 dB)', S.rms_activo_db(x) < nivel - 4.0, f'{S.rms_activo_db(x):.1f} dB vs voz {nivel} dB')
        medidas[pack] = {'resumen': r, 'segundos_fase3': sfx.get('segundos'), 'segundos_total': round(seg, 2), 'fuentes': [p['fuente'] for p in sfx['puestos']]}
        ok(f'[{pack}] fase 3 rápida (< 10 s para {dur:.0f} s de video)', float(sfx.get('segundos') or 99) < 10.0, f"{sfx.get('segundos')} s")
    if len(resultados) == 6:
        acentos = {p: (resultados[p][0].get('sfx') or {}).get('diseno', {}).get('caracter', {}).get('acento') for p in TEMAS}
        ok('identidad: Tema 1 golpe, Tema 5 tic, Tema 6 trazo (sale de su configuración)', acentos['Kinetic'] == 'golpe' and acentos['Tema5'] == 'tick'
           and acentos['Tema6'] == 'trazo', acentos)
        sobrios = [e for p in ('Tema5', 'Tema6') for e in resultados[p][0]['sfx']['diseno']['eventos'] if e['decision'] == 'GENERATE']
        ok('temas sobrios: sin risers ni whooshes en cortes secos', not any(e['tipo'] == 'riser' or e['origen'] == 'corte' for e in sobrios))
        k_res, k_ctx, k_cues = resultados['Kinetic']
        k_ev = [e for e in k_res['sfx']['diseno']['eventos'] if e['decision'] == 'GENERATE' and e['origen'] == 'caption' and e['tipo'] == 'golpe']
        fps = 30.0
        bien = []
        for e in k_ev:
            heroe = next(r_ for r_ in k_cues[e['ref']]['runs'] if str(r_.get('k') or '').startswith('k hero'))
            bien.append(abs(e['ancla'] - (float(heroe['t']) + 0.37 * EV.ANIM_KINETIC['pop']['f'] / fps)) < 1.0 / fps)
        ok('Tema 1: cada golpe cae cuando el héroe llega a su tamaño (±1 fotograma)', bool(bien) and all(bien), f'{sum(bien)}/{len(bien)}')
    INFORME['fase3'] = medidas

    # --- al_colocar: el director es el único dueño del sonido (Efectos KEEP/REPLACE, Simple apagado, la PRO marcada, lo visual intacto)
    res = resultados.get('Kinetic', (None,))[0]
    if not res:
        return
    fx = {'eventos': [{'tipo': 'intro', 'ini': 0.0, 'asset': 'fuga_de_luz'}, {'tipo': 'corte', 'ini': 3.2, 'asset': 'destello'},
                      {'tipo': 'sonido', 'ini': 0.0, 'archivo': 'intro.wav', 'dur': 1.6, 'asset': 'Intro luz', 'pico': 0.6},
                      {'tipo': 'sonido', 'ini': 3.1, 'archivo': 'w.wav', 'dur': 0.5, 'asset': 'corte · whoosh', 'extra': True},
                      {'tipo': 'sonido', 'ini': 58.0, 'archivo': 'o.wav', 'dur': 2.0, 'asset': 'outro · campana', 'crudo': True},
                      {'tipo': 'musica', 'ini': 0.0, 'archivo': 'm.wav', 'dur': 30.0, 'asset': 'musica.mp3'}], 'duracion': dur, 'video': str(video)}
    antes = copy.deepcopy(fx)
    pro = {'piezas': copy.deepcopy(plan_pro.get('piezas') or [])}
    pro_antes = copy.deepcopy(pro)
    E.poner_general(voz_ai_puesta=False, ai_puesto=False)
    nuevo = D.al_colocar(fx, res, str(video), plan_pro=pro)
    evs = nuevo['eventos']
    ok('al_colocar: el plan original no se toca (copia)', fx == antes)
    ok('al_colocar: lo visual de Efectos, idéntico', [e for e in evs if e['tipo'] not in ('sonido', 'voz_ai', 'musica')] == [e for e in antes['eventos'] if e['tipo'] not in ('sonido', 'musica')])
    ok('al_colocar: el sonido «extra» de la biblioteca de siempre → REPLACE (fuera)', not any(e.get('extra') for e in evs))
    ok('al_colocar: los de la intro y la outro → KEEP', any(e.get('asset') == 'Intro luz' for e in evs) and any(e.get('asset') == 'outro · campana' for e in evs))
    ok('al_colocar: la música no la decide la fase 3 (sigue)', any(e['tipo'] == 'musica' for e in evs))
    n_ai = sum(1 for e in evs if str(e.get('pista') or '').startswith('AI SFX'))
    ok('al_colocar: los sonidos del director en sus pistas AI SFX', n_ai == len(res['sfx']['eventos']) and n_ai > 0, n_ai)
    ok('al_colocar: los sonidos de Simple se APAGAN (pistas «SFX…»)', 'SFX' in (nuevo.get('apagar_sfx') or []), nuevo.get('apagar_sfx'))
    ok('al_colocar: la PRO queda marcada (sus sonidos los hace el director) y sus piezas intactas', pro.get('_ai_sound') is True and pro['piezas'] == pro_antes['piezas'])
    ok('al_colocar: queda anotado que hay pistas del director (para limpiarlas al apagarlo)', E.general().get('ai_puesto') is True)
    # apagado: el MISMO plan y la PRO sin marcar
    os.environ['CINECAPTIONS_AI_SOUND'] = '0'
    E.poner_general(voz_ai_puesta=False, ai_puesto=False)
    pro2 = {'piezas': []}
    ok('apagado: al_colocar devuelve el MISMO plan y no marca la PRO', D.al_colocar(fx, res, str(video), plan_pro=pro2) is fx and '_ai_sound' not in pro2)
    E.poner_general(ai_puesto=True)
    limpia = D.al_colocar(None, None, str(video))
    ok('apagado con pistas de antes: plan que solo limpia (solo_ai) y sin apagar Simple', bool(limpia and limpia.get('solo_ai')) and not limpia.get('apagar_sfx'))
    os.environ['CINECAPTIONS_AI_SOUND'] = '1'
    # fallback: sin sonidos del director (falló la fase 3) → nada de apagar Simple ni tocar la PRO
    E.poner_general(voz_ai_puesta=False, ai_puesto=False)
    pro3 = {'piezas': []}
    sin = D.al_colocar(fx, {'sfx': None, 'evento_voz': None}, str(video), plan_pro=pro3)
    ok('fallback: si la fase 3 falla, Efectos, Simple y la PRO como siempre', sin is fx and '_ai_sound' not in pro3)
    import director_sonido_sfx as SFX
    real = SFX.fabricar
    SFX.fabricar = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('prueba'))
    try:
        r_f = D.preparar(D.contexto(video, palabras, 'Kinetic', 'v', timeline_de_go=False, bloques=resultados['Kinetic'][2], plan_efectos=plan_fx, plan_pro=plan_pro))
    finally:
        SFX.fabricar = real
    ok('fallback: si fabricar lanza, «[AI SOUND] fallback» y GO sigue (sin sonidos del director)', r_f.get('sfx') is None and r_f.get('analisis') is not None
       and any('fallback' in m and 'sonidos' in m for _n, m, _o in LOG))
    # sonidos_pro (v5.37): los de la PRO —kit neón del Tema 1, gráficos, Motions completo— los REHACE el director en su mismo instante
    import numpy as np
    pro_dir = salida / 'pro_wavs'
    pro_dir.mkdir(parents=True, exist_ok=True)
    rng_p = np.random.default_rng(7)
    def _wav_pro(nombre, n, pico_s):
        x = (rng_p.standard_normal((2, n)) * 0.05).astype(np.float32)
        k = int(pico_s * SFX.SR)
        x[:, k:k + 480] *= 12.0
        SFX._escribir(pro_dir / nombre, x)
        return str(pro_dir / nombre)
    acentos_d = sorted(float(e['ancla']) for e in E.cargar(str(video)).get('sound_events') or []
                       if e.get('decision') == 'GENERATE' and e.get('origen') == 'caption')
    libre_t = next(t for t in np.arange(5.0, max(dur - 5.0, 6.0), 0.5) if all(abs(t - a) > 1.0 for a in acentos_d))
    lista = [{'pista': 'PRO-WHOOSH', 'ini': int(round((libre_t - 0.30) * 30)), 'archivo': _wav_pro('w.wav', int(0.6 * SFX.SR), 0.30), 'dur': 0.6, 'que': 'escena entra'},
             {'pista': 'PRO-TEXTURA', 'ini': int(round((libre_t + 2.4) * 30)), 'archivo': _wav_pro('t.wav', int(0.3 * SFX.SR), 0.02), 'dur': 0.3, 'que': 'aparece el icono', 'origen': 'motions'}]
    if acentos_d:
        lista.append({'pista': 'PRO-TEXTURA', 'ini': int(round((acentos_d[0] - 0.02) * 30)), 'archivo': _wav_pro('c.wav', int(0.3 * SFX.SR), 0.02), 'dur': 0.3, 'que': 'tic'})
    ok('sonidos_pro: sin marca, la MISMA lista (la PRO de siempre)', D.sonidos_pro({'piezas': []}, lista) is lista)
    rehechos = D.sonidos_pro({'_ai_sound': True, 'video': str(video)}, lista, 30.0)
    ok('sonidos_pro: con el director al mando, los de la PRO REHECHOS por él (archivos suyos, nada de los originales)',
       len(rehechos) >= 2 and all(Path(e['archivo']).is_file() and e['archivo'] not in {x['archivo'] for x in lista} for e in rehechos), len(rehechos))
    ok('sonidos_pro: cada uno en la pista PRO de su familia y en su instante (±3 fotogramas del pico original)',
       any(e['pista'] == 'PRO-WHOOSH' for e in rehechos) and all(e['pista'] in ('PRO-WHOOSH', 'PRO-TEXTURA') for e in rehechos)
       and any(abs(e['ini'] - lista[1]['ini']) <= 3 for e in rehechos if e['pista'] == 'PRO-TEXTURA'),
       [(e['pista'], e['ini']) for e in rehechos])
    if acentos_d:
        ok('sonidos_pro: el que pisaba un acento de caption, en silencio', not any(abs(e['ini'] - lista[2]['ini']) <= 3 and e['pista'] == 'PRO-TEXTURA' for e in rehechos))
    ok('sonidos_pro: lo rehecho queda anotado (pro_sound_events, pro_sfx_plan)', bool(E.cargar(str(video)).get('pro_sound_events')))
    real_r = D.redisenar_pro
    D.redisenar_pro = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('prueba'))
    try:
        ok('sonidos_pro: si rehacerlos falla, fuera los de la PRO salvo Motions completo (nunca los de siempre)',
           D.sonidos_pro({'_ai_sound': True, 'video': str(video)}, lista) == [lista[1]])
    finally:
        D.redisenar_pro = real_r
    # el camino REAL de GO: efectos_visuales.aplicar lleva «apagar_sfx» al plan de Resolve (v5.37: antes se perdía y las pistas SFX sonaban)
    import efectos_visuales as EFV
    import resolve_mcp as RM
    guardado = (RM.ruta_exe, RM.script, RM.ejecutar_py, EFV.PLAN_JSON)
    RM.ruta_exe = lambda: 'resolve.exe'
    RM.script = lambda codigo, timeout=40: ((True, [], None) if codigo is EFV._INFO_V1 else
                                           (True, {'timeline': 'T', 'ancho': 1920, 'alto': 1080, 'fps': 30.0, 'inicio': 86400}, None))
    RM.ejecutar_py = lambda *a, **k: (True, 'ok')
    EFV.PLAN_JSON = salida / 'plan_efectos_prueba.json'
    try:
        EFV.aplicar({'eventos': [], 'apagar_sfx': ['SFX'], 'solo_audio': True, 'video': str(video)})
        datos_r = json.loads(EFV.PLAN_JSON.read_text(encoding='utf-8'))
    except Exception as ex:
        datos_r = {'error': repr(ex)}
    finally:
        RM.ruta_exe, RM.script, RM.ejecutar_py, EFV.PLAN_JSON = guardado
    ok('efectos_visuales.aplicar: «apagar_sfx» llega al plan que lee Resolve', datos_r.get('apagar_sfx') == ['SFX'], datos_r.get('apagar_sfx', datos_r.get('error')))
    princ = (CODIGO / 'CineCaptions (script principal).py').read_text(encoding='utf-8')
    i_p = princ.index('def _preparar_sfx')
    ok('GO: con el director encendido, las reglas de siempre NO mandan sonidos a Resolve (_preparar_sfx → {})',
       'director_sonido.activo()' in princ[i_p:i_p + 12000] and 'return {}' in princ[i_p:i_p + 12000])
    import director_sonido_diseno as D3
    m_k = D3._momento_caption({'start': 1.0, 'lines': [{'role': 'main', 'start': 1.2, 'text': 'HOLA'}, {'role': 'context', 'start': 1.0, 'text': 'y'}]},
                              {'estilo': 'kinetic', 'acento': 'golpe'}, 30.0)
    ok('Tema 1 neón: un bloque sin los clips del tema suena en su palabra principal', bool(m_k) and m_k['tipo'] == 'golpe' and 1.2 < m_k['ancla'] < 1.6, m_k)
    src = (CODIGO / 'edicion_pro.py').read_text(encoding='utf-8')
    ok('edicion_pro.aplicar llama a director_sonido.sonidos_pro tras el rectificador', src.index('director_sonido.sonidos_pro') > src.index('rectificador.pro_final(datos'))

    # --- colocar_efectos.py contra el Resolve falso
    import resolve_falso as RF
    script = CODIGO.parent / '2_recursos' / 'efectos' / 'colocar_efectos.py'
    frames = int(round(dur * 30))
    plan_r = {'eventos': [e for e in evs if str(e.get('pista') or '').startswith('AI SFX')], 'apagar_sfx': nuevo['apagar_sfx']}   # (los visuales los rellena aplicar)

    def con_sfx():
        R = RF.nuevo(frames_a1=frames)
        tl = R[2]
        tl.AddTrack('audio', 'stereo')
        tl.SetTrackName('audio', 2, 'SFX')
        for k in range(3):
            tl.items.append(RF.Item('Hit.wav', tl.inicio + 30 * (k + 1), 15, 2, 'audio'))
        return R

    def ai_clips(tl):
        return sum(len(tl.GetItemListInTrack('audio', i + 1)) for i, p in enumerate(tl.pistas['audio']) if p['nombre'].startswith('AI SFX'))
    R = con_sfx()
    tl = R[2]
    okk, txt = _colocar_py(script, plan_r, R)
    hits = [x for x in tl.items if x.n == 'Hit.wav']
    ok('[py] los sonidos del director en las pistas AI SFX (por nombre)', okk and ai_clips(tl) == n_ai, f'{ai_clips(tl)} de {n_ai} · {txt.strip()[-120:]}')
    ok('[py] los «Hit» de Simple APAGADOS, no borrados', len(hits) == 3 and not any(x.enabled for x in hits))
    ok('[py] A1 (la voz) sin tocar', tl.GetIsTrackEnabled('audio', 1) is True)
    okk, txt = _colocar_py(script, plan_r, R)
    ok('[py] re-aplicar no apila (mismos clips en las pistas AI)', okk and ai_clips(tl) == n_ai, ai_clips(tl))
    okk, txt = _colocar_py(script, {'eventos': [e for e in antes['eventos'] if e['tipo'] == 'sonido' and not e.get('extra')]}, R)
    ok('[py] director apagado: las pistas AI SFX se van', okk and ai_clips(tl) == 0 and not any(p['nombre'].startswith('AI SFX') for p in tl.pistas['audio']))
    R = con_sfx()
    R[3].falla_append_audio = True
    _colocar_py(script, plan_r, R)
    ok('[py] si los sonidos del director no entran, los de Simple NO se apagan', all(x.enabled for x in R[2].items if x.n == 'Hit.wav'))
    R = con_sfx()
    okk, _t = _colocar_py(script, {'eventos': [], 'apagar_sfx': ['SFX'], 'solo_audio': True, 'solo_ai': True}, R)
    ok('[py] diseño en silencio a propósito (0 sonidos): Simple apagado igual', not any(x.enabled for x in R[2].items if x.n == 'Hit.wav'))

    # --- el gemelo .lua (Free) en LuaJIT
    py = _lua_python()
    if not ok('LuaJIT (lupa) disponible para probar el .lua (fase 3)', bool(py), py or 'sin lupa'):
        return
    lua_src = CODIGO.parent / '2_recursos' / 'resolve_scripts' / 'CineCaptions_Efectos.lua'
    casa = Path(tempfile.mkdtemp())
    base = {'fps': 30.0, 'inicio': 86400, 'offset_frames': 0, 'v1': [], 'solo_audio': True}
    pa = dict(base, eventos=plan_r['eventos'], apagar_sfx=plan_r['apagar_sfx'])
    po = dict(base, eventos=[e for e in antes['eventos'] if e['tipo'] == 'sonido' and not e.get('extra')])
    escenarios = [_escenario_lua('sfx pone y re-aplica', frames, [pa, pa], pista_sfx=True), _escenario_lua('sfx apagar el director', frames, [pa, po], pista_sfx=True),
                  _escenario_lua('sfx falla el append', frames, [pa], pista_sfx=True, falla_append=True),
                  _escenario_lua('sfx Free sin io', frames, [pa], pista_sfx=True, sin_io=True)]
    f_esc, f_prog, f_falso = casa / 'escenarios.json', casa / 'prueba_lua.py', casa / 'falso.lua'
    f_esc.write_text(json.dumps(escenarios), encoding='utf-8')
    f_prog.write_text(LUA_PRUEBA, encoding='utf-8')
    f_falso.write_text(LUA_FALSO, encoding='utf-8')
    r = subprocess.run([py, str(f_prog), str(lua_src), str(casa), str(f_falso), str(f_esc)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    linea = next((l for l in r.stdout.splitlines() if l.startswith('JSON')), None)
    if not ok('[lua] el gemelo corre en LuaJIT (fase 3)', bool(linea), (r.stderr or r.stdout)[-300:]):
        return
    rl = {e['nombre']: e['resultados'] for e in json.loads(linea[4:])}

    def ai_lua(rr):
        return sum(int(x.split('|')[3]) for x in rr['audio'].split(';') if x and x.split('|')[0].startswith('AI SFX'))
    r1, r2 = rl['sfx pone y re-aplica']
    ok('[lua] los sonidos del director en las pistas AI SFX y Simple apagado', r1['ok'] and ai_lua(r1) == n_ai and r1['sfx_encendidos'] == 0, f"{ai_lua(r1)} · {r1['err'] or ''}")
    ok('[lua] re-aplicar no apila', r2['ok'] and ai_lua(r2) == n_ai)
    r1, r2 = rl['sfx apagar el director']
    ok('[lua] director apagado: las pistas AI SFX se van', r2['ok'] and ai_lua(r2) == 0 and 'AI SFX' not in r2['audio'])
    (r1,) = rl['sfx falla el append']
    ok('[lua] si los sonidos del director no entran, Simple NO se apaga', r1['sfx_encendidos'] == 3, r1['audio'])
    (r1,) = rl['sfx Free sin io']
    ok('[lua] Free sin io (sidecar): sonidos del director puestos y Simple apagado', r1['ok'] and ai_lua(r1) == n_ai and r1['sfx_encendidos'] == 0, f"{ai_lua(r1)} · {r1['err'] or ''}")

    # --- GO de punta a punta (los ganchos de SubtitleApp) con el Tema 1
    M_ = sys.modules.get('cc_nuevo') or _principal(CODIGO / 'CineCaptions (script principal).py', 'cc_nuevo')
    k_res, k_ctx, k_cues = resultados['Kinetic']
    E.poner_general(voz_ai_puesta=False, ai_puesto=False)
    fx_go, pro_go = copy.deepcopy(plan_fx), copy.deepcopy(plan_pro)
    F = _app_falsa(M_, fx_go, pro_go, video)
    F._ultimos_bloques = k_cues
    F._director_sonido_arrancar(video, palabras, None, 'es')
    F._director_sonido_al_colocar()
    evs_go = (F._efectos_plan or {}).get('eventos') or []
    ok('GO (encendido): el plan de Efectos lleva los sonidos del director', sum(1 for e in evs_go if str(e.get('pista') or '').startswith('AI SFX')) > 0)
    ok('GO (encendido): la PRO queda en manos del director', (F._pro_plan or {}).get('_ai_sound') is True)
    ok('GO (encendido): lo visual de Efectos, idéntico', [e for e in evs_go if e.get('tipo') not in ('sonido', 'voz_ai', 'musica')] ==
       [e for e in plan_fx.get('eventos') or [] if e.get('tipo') not in ('sonido', 'voz_ai', 'musica')])


# ---------------------------------------------------------------------------------------------------------------- fase 4
def _wav_bytes_musica(segundos=24.0, bpm=100.0, seed=3):
    """Una «canción» de prueba de verdad (acordes + bombo al pulso) como WAV en memoria: el falso de Epidemic la sirve como si fuera su MP3."""
    import io
    import wave
    import numpy as np
    sr = 48000
    t = np.arange(int(segundos * sr)) / sr
    x = np.zeros_like(t)
    for k, f in enumerate((220.0, 277.18, 329.63)):
        x += 0.12 * np.sin(2 * np.pi * f * t + k)
    pulso = (t * bpm / 60.0) % 1.0
    x += 0.5 * np.sin(2 * np.pi * 55 * t) * np.exp(-pulso * 18)
    x += 0.05 * np.random.default_rng(seed).standard_normal(t.size) * np.exp(-((t * bpm / 30.0) % 1.0) * 30)
    x = (x / np.abs(x).max() * 0.7 * 32767).astype('<i2')
    b = io.BytesIO()
    with wave.open(b, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(np.repeat(x, 2).tobytes())
    return b.getvalue()


def _wav_bytes_ambiente(segundos=16.0, seed=5):
    import io
    import wave
    import numpy as np
    rng = np.random.default_rng(seed)
    n = int(segundos * 48000)
    x = np.cumsum(rng.standard_normal(n)) * 0.002
    x -= np.convolve(x, np.ones(4801) / 4801, 'same')
    x = (x / (np.abs(x).max() + 1e-9) * 0.4 * 32767).astype('<i2')
    b = io.BytesIO()
    with wave.open(b, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(np.repeat(x, 2).tobytes())
    return b.getvalue()


def fase4(salida, video):
    """Música y ambiente: sin proveedor (decisiones y avisos), con el Epidemic FALSO sirviendo audio de verdad (varios candidatos, MUSIC FIT, una sola
    descarga, copia procesada con ducking, ambiente muy bajo), el control del usuario mandando, al_colocar y colocar_efectos.py en AI MUSIC / AI AMBIENCE."""
    print('\n== FASE 4: música y ambiente (proveedor autorizado, candidatos, ducking, pistas AI MUSIC / AI AMBIENCE) ==')
    import numpy as np
    E = entorno(salida)
    os.environ['CINECAPTIONS_AI_SOUND'] = '1'
    import director_sonido as D
    import director_sonido_capas as CA
    import director_sonido_epidemic as EP
    import director_sonido_medir as M
    sys.path.insert(0, str(AQUI))
    import probar_epidemic as PE
    casos = casos_sinteticos(salida)
    EP._de_dotenv = lambda: None
    EP._olvidar()
    os.environ.pop(EP.ENV, None)
    ruta, pal, _e = casos['limpia']
    ctx = D.contexto(ruta, pal, 'Kinetic', 'v', timeline_de_go=True)
    a, _i = D.analizar(ctx)
    nivel = D._nivel_voz_previsto(ctx, a)
    carpeta = E.carpeta_de(ruta)
    # --- sin proveedor (v5.37: la cama de score de la biblioteca del autor; sin biblioteca, silencio)
    import director_sonido_biblioteca as B
    real_camas = B.camas
    B.camas = lambda *a_, **k_: []
    try:
        m = CA.musica(a, ctx, {'musica': 'medio'}, carpeta, nivel)
    finally:
        B.camas = real_camas
    ok('sin proveedor ni biblioteca: pediste música pero NO se pone una mediocre (NO_MUSIC_REQUIRED + aviso)', m['estado'] == 'NO_MUSIC_REQUIRED'
       and 'Epidemic' in m['por_que'] and not m['plan'], m['por_que'])
    if B.camas(0.6):
        ml = CA.musica(a, ctx, {'musica': 'medio'}, carpeta, nivel)
        ev_l = (ml.get('plan') or [{}])[0]
        ok('sin Epidemic: una cama de score de TU biblioteca (Film Score), procesada a la medida', ml['estado'] == 'ADD_NEW' and Path(ev_l.get('archivo', '')).is_file()
           and 'biblioteca' in (ev_l.get('ai') or {}).get('fuente', ''), ml.get('por_que'))
        xl = _leer_todo(ev_l['archivo'], 2) if ev_l.get('archivo') else None
        habla_l = [w for w in pal if w['end'] - w['start'] > 0.2]
        if xl is not None and habla_l:
            seg = np.concatenate([xl[:, int(w['start'] * 48000):int(w['end'] * 48000)] for w in habla_l[:20]], axis=1)
            ok('la cama del autor va BAJO la voz (≥ 14 dB)', CA._rms_db(seg) < nivel - 14.0, f'{CA._rms_db(seg):.1f} vs voz {nivel}')
        ok('la cama es la misma en el mismo video (no cambia cada GO)', CA.musica(a, ctx, {'musica': 'medio'}, carpeta, nivel)['elegido']['title'] == ml['elegido']['title'])
    am_l = CA.ambiente(dict(a, ambiente={'escenas': [{'ini': 0.0, 'fin': 6.0, 'contexto': 'NATURE', 'confianza': 0.8, 'decision': 'ADD_SUBTLE_AMBIENCE', 'por_que': 'x'},
                                                     {'ini': 6.0, 'fin': 9.0, 'contexto': 'INTERIOR', 'confianza': 0.8, 'decision': 'ADD_SUBTLE_AMBIENCE', 'por_que': 'x'}]}),
                       ctx, {'ambiente': 'medio'}, carpeta, nivel)
    if B.ambientes('NATURE'):
        ok('ambiente sin Epidemic: la grabación de TU biblioteca de ese entorno (naturaleza) y nada inventado para el interior',
           len(am_l['plan']) == 1 and 'biblioteca' in am_l['plan'][0]['ai']['fuente'] and am_l['escenas'][1]['decision'] == 'LEAVE_SILENT', am_l['resumen'])
    ok('control «Sin música»: NO_MUSIC_REQUIRED', CA.musica(a, ctx, {'musica': 'nada'}, carpeta, nivel)['estado'] == 'NO_MUSIC_REQUIRED')
    rm, pm, _ = casos['musica_mezclada']
    ctx_m = D.contexto(rm, pm, 'Kinetic', 'v', timeline_de_go=True)
    a_m, _i = D.analizar(ctx_m)
    km = CA.musica(a_m, ctx_m, {'musica': 'mucho'}, E.carpeta_de(rm), nivel)
    ok('el video ya trae música: KEEP_EXISTING aunque pidas más (dos músicas chocan)', km['estado'] == 'KEEP_EXISTING' and not km['plan'], km['por_que'])
    amb0 = CA.ambiente(a, ctx, {'ambiente': 'mucho'}, carpeta, nivel)
    ok('sin proveedor: el ambiente NO se inventa (LEAVE_SILENT)', not amb0['plan'] and all(e['decision'] != 'ADD_SUBTLE_AMBIENCE' for e in amb0['escenas']),
       [e['decision'] for e in amb0['escenas']][:3])
    # --- con el Epidemic FALSO sirviendo audio de verdad
    srv, base = PE.falso()
    EP.BASE = base
    PE.Falso.visitas.clear()
    PE.Falso.AUDIO = {'trk': _wav_bytes_musica(), 'amb': _wav_bytes_ambiente()}
    PE.Falso.PISTAS = [{'id': 'trkV', 'title': 'Happy Pop With Vocals', 'length': 180, 'bpm': 100},
                       {'id': 'trkB', 'title': 'Light Upbeat Vlog', 'length': 151, 'bpm': 102, 'moods': [{'name': 'Upbeat'}]},
                       {'id': 'trkC', 'title': 'Dark Drone', 'length': 12, 'bpm': 60},
                       {'id': 'trkP', 'title': 'Preview Only Gem', 'length': 200, 'bpm': 100, 'isPreviewOnly': True}]
    PE.Falso.SFX = [{'id': 'ambA', 'title': 'Quiet Room Tone Interior', 'length': 16000}, {'id': 'ambB', 'title': 'Short Click', 'length': 300}]
    os.environ[EP.ENV] = 'es_live_PRUEBA_' + 'y' * 24
    try:
        ok('con clave (falso): el proveedor está configurado', EP.configurada())
        m = CA.musica(a, ctx, {'musica': 'medio'}, carpeta, nivel)
        ok('ADD_NEW: varias candidatas evaluadas y la elegida NO es la primera (la de voces queda fuera)', m['estado'] == 'ADD_NEW'
           and len(m.get('candidatos') or []) >= 3 and (m.get('elegido') or {}).get('asset_id') == 'trkB', m.get('por_que'))
        ok('las solo-preview no se usan', any(c['asset_id'] == 'trkP' and c['music_fit'] < 0 for c in m.get('candidatos') or []))
        ev = (m.get('plan') or [{}])[0]
        x = np.concatenate(list(M.leer_wav(ev['archivo'])), axis=1) if ev.get('archivo') else np.zeros((2, 0))
        dur = float(a['voz']['duracion'])
        ok('la cama de música dura lo mismo que el video (bucle con fundido) y va en AI MUSIC', ev.get('pista') == 'AI MUSIC' and abs(x.shape[1] / 48000 - dur) < 0.05,
           f'{x.shape[1] / 48000:.2f} s de {dur:.2f} s')
        g, tasa = CA._ducking(8 * 48000, [(1.0, 3.0), (5.0, 7.0)], -6.0)
        ok('ducking: −6 dB mientras se habla, vuelve en la pausa (ataque rápido, suelta lenta)', g[int(2.0 * tasa)] < -5.5 and g[int(4.5 * tasa)] > -1.5
           and g[int(3.2 * tasa)] < g[int(4.5 * tasa)], f'habla {g[int(2.0 * tasa)]:.1f} · pausa {g[int(4.5 * tasa)]:.1f} dB')
        tramos = CA._tramos_voz(pal)
        habla = np.concatenate([x[:, int((p[0] + 0.3) * 48000):int(max(p[0] + 0.31, p[1] - 0.1) * 48000)] for p in tramos if p[1] - p[0] > 0.8] or [x[:, :1]], axis=1)
        pausas = [(tramos[i][1], tramos[i + 1][0]) for i in range(len(tramos) - 1) if tramos[i + 1][0] - tramos[i][1] > 1.2]
        if pausas:
            hueco = np.concatenate([x[:, int((p0 + 0.5) * 48000):int((p1 - 0.2) * 48000)] for p0, p1 in pausas], axis=1)
            ok('ducking: la música baja cuando se habla y respira en las pausas', CA._rms_db(hueco) > CA._rms_db(habla) + 3.0,
               f'pausa {CA._rms_db(hueco):.1f} dB vs habla {CA._rms_db(habla):.1f} dB')
        ok('la música va BAJO la voz', CA._rms_db(habla) < nivel - 12.0, f'{CA._rms_db(habla):.1f} vs voz {nivel}')
        n_desc = sum(1 for v in PE.Falso.visitas if v['ruta'].endswith('/download'))
        CA.musica(a, ctx, {'musica': 'medio'}, carpeta, nivel)
        ok('segunda vez: sin volver a descargar (caché profesional)', sum(1 for v in PE.Falso.visitas if v['ruta'].endswith('/download')) == n_desc)
        PE.Falso.PISTAS = [{'id': 'trkQ', 'title': 'Only Preview', 'length': 200, 'bpm': 100, 'isPreviewOnly': True}]
        mq = CA.musica(a, ctx, {'musica': 'medio'}, carpeta, nivel)
        ok('cuenta que solo permite previews: nada de Epidemic (la cama del autor o sin música) y dice por qué',
           not any('Epidemic' in str((e.get('ai') or {}).get('fuente')) for e in mq['plan']) and 'Epidemic' in mq['por_que'] or 'encaja' in mq['por_que'], mq['por_que'])
        am = CA.ambiente(a, ctx, {'ambiente': 'medio'}, carpeta, nivel)
        ok('ambiente: un interior tranquilo conserva su ambiente original (no se añade nada encima)', not am['plan']
           and all(e['decision'] == 'KEEP_ORIGINAL_AMBIENCE' for e in am['escenas']), am['resumen'])
        a_of = dict(a, ambiente={'escenas': [{'escena': 1, 'ini': 0.0, 'fin': dur * 0.5, 'contexto': 'OFFICE', 'confianza': 0.8, 'decision': 'ADD_SUBTLE_AMBIENCE'},
                                             {'escena': 2, 'ini': dur * 0.5, 'fin': dur, 'contexto': 'OFFICE', 'confianza': 0.8, 'decision': 'ADD_SUBTLE_AMBIENCE'}],
                                 'resumen': 'oficina'})
        am = CA.ambiente(a_of, ctx, {}, carpeta, nivel)
        xa = np.concatenate(list(M.leer_wav(am['plan'][0]['archivo'])), axis=1) if am['plan'] else np.zeros((2, 1))
        ok('ambiente ADD_SUBTLE: escenas seguidas = UN tramo, grabación autorizada en AI AMBIENCE, muy por debajo de la voz',
           len(am['plan']) == 1 and am['plan'][0]['pista'] == 'AI AMBIENCE' and abs(am['plan'][0]['dur'] - dur) < 0.05
           and nivel - 36.0 < CA._rms_db(xa) < nivel - 22.0,
           f"{am['resumen']} · {CA._rms_db(xa):.1f} dB")
        ok('ambiente: elige la grabación por su nombre y largo (no el clic corto)', 'Room Tone' in am['plan'][0]['asset'] if am['plan'] else False)
        # al_colocar y Resolve falso
        PE.Falso.PISTAS = [{'id': 'trkB', 'title': 'Light Upbeat Vlog', 'length': 151, 'bpm': 102}]
        PREFS[D.PREF_CONTROLES] = {'musica': 'medio', 'ambiente': 'medio'}
        E.poner_general(voz_ai_puesta=False, ai_puesto=False)
        res = D.preparar(ctx)
        ok('preparar: música y ambiente en el resultado (fase 4)', bool(res.get('capas')) and res['capas']['musica']['estado'] == 'ADD_NEW')
        plan = D.al_colocar({'eventos': [{'tipo': 'musica', 'ini': 0.0, 'archivo': 'vieja.wav', 'dur': 10.0, 'asset': 'vieja'}]}, res, str(ruta))
        pistas = {e.get('pista') for e in plan['eventos']}
        ok('al_colocar: AI MUSIC en el plan y la música de Efectos fuera (la del director manda)', 'AI MUSIC' in pistas
           and not any(e.get('asset') == 'vieja' for e in plan['eventos']))
        estado = E.cargar(ruta)
        ok('estado: decisión de música y planes guardados', (estado.get('music_decision') or {}).get('estado') == 'ADD_NEW' and estado.get('music_plan'))
        import resolve_falso as RF
        script = CODIGO.parent / '2_recursos' / 'efectos' / 'colocar_efectos.py'
        R = RF.nuevo(frames_a1=int(round(dur * 30)))
        okk, txt = _colocar_py(script, {'eventos': [e for e in plan['eventos'] if e.get('pista') in ('AI MUSIC', 'AI AMBIENCE')]}, R)
        nombres = {p['nombre']: len(R[2].GetItemListInTrack('audio', i + 1)) for i, p in enumerate(R[2].pistas['audio'])}
        ok('[py] colocar_efectos: la música en «AI MUSIC» (un clip entero)', okk and nombres.get('AI MUSIC') == 1, f'{nombres} · {txt.strip()[-100:]}')
    finally:
        os.environ.pop(EP.ENV, None)
        EP._olvidar()
        PREFS.pop(D.PREF_CONTROLES, None)
        PE.Falso.AUDIO, PE.Falso.PISTAS, PE.Falso.SFX = {}, None, None
        srv.shutdown()
    # fallback
    real = CA.musica
    CA.musica = lambda *a_, **k_: (_ for _ in ()).throw(RuntimeError('prueba'))
    try:
        r_f = D.preparar(ctx)
    finally:
        CA.musica = real
    ok('fallback: si la música falla, «[AI SOUND] fallback» y GO sigue (sonidos y voz igual)', r_f.get('capas') is None and r_f.get('sfx') is not None
       and any('música y ambiente' in m_ for _n, m_, _o in LOG))


# ---------------------------------------------------------------------------------------------------------------- fase 5
def fase5(salida, video):
    """Mezcla completa, QC en 3 pasadas y Sound Score: la medida de la mezcla cuadra con una suma independiente, un golpe demasiado alto se baja
    solo él hasta quedar ≥ 8 dB bajo la voz, el bus baja si los SFX empujan el true peak (la voz no), y cada parte del score sale de su medida."""
    print('\n== FASE 5: mezcla, QC en 3 pasadas y Sound Score ==')
    import numpy as np
    E = entorno(salida)
    os.environ['CINECAPTIONS_AI_SOUND'] = '1'
    import director_sonido as D
    import director_sonido_medir as M
    import director_sonido_mezcla as MZ
    import efectos_visuales
    import vista_tema
    palabras = _palabras_de_cache(video)
    if not ok('video de prueba con su transcripción (fase 5)', bool(palabras)):
        return
    dur = float(palabras[-1]['end'])
    cortes = [c[0] for c in efectos_visuales.detectar_cortes(str(video))]
    cues = vista_tema.planificar(palabras, {}, 'Kinetic', vista_tema.estilo_de_pack('Kinetic', 'v'), idioma='es', fin_video=dur, video=str(video))
    ctx = D.contexto(video, palabras, 'Kinetic', 'v', timeline_de_go=False, bloques=cues, cortes=cortes, idioma='es')
    ctx['cortes'] = cortes
    t = time.time()
    res = D.preparar(ctx)
    seg = time.time() - t
    qc = res.get('qc') or {}
    ok('preparar: QC y Sound Score en el resultado', bool(qc) and 0 <= qc.get('score', -1) <= 100 and len(qc.get('partes') or {}) == 7,
       f"{qc.get('score')}/100 en {seg:.1f} s")
    ok('cada parte del score con su número, su peso y su porqué', all(set(v) >= {'puntos', 'peso', 'por_que'} and v['por_que'] for v in qc['partes'].values()))
    ok('los pesos suman 100 y la fórmula queda escrita', sum(MZ.PESOS.values()) == 100 and 'sincronía' in qc.get('formula', ''))
    # la medida de la mezcla = una suma independiente (voz + cada WAV en su sitio, como Resolve)
    voz = np.concatenate(list(M.trozos(str(video), canales=2)), axis=1)
    mezcla = voz.copy()
    for e in (res['sfx']['eventos'] or []) + [x for k in ('musica', 'ambiente') for x in (res['capas'][k].get('plan') or [])]:
        y = np.concatenate(list(M.leer_wav(e['archivo'])), axis=1)
        i = int(round(e['ini'] * 48000))
        n = min(y.shape[1], mezcla.shape[1] - i)
        mezcla[:, i:i + n] += y[:2, :n]
    S_ = M.Sonometro(2)
    for i in range(0, mezcla.shape[1], 48000 * 4):
        S_.medir(mezcla[:, i:i + 48000 * 4])
    ref = S_.resultado()
    medida = qc['medidas']['mezcla']
    ok('la mezcla medida en streaming = una suma independiente (LUFS ±0,2, TP ±0,3)', abs(ref['lufs'] - medida['lufs']) <= 0.2 and abs(ref['tp_db'] - medida['tp_db']) <= 0.3,
       f"{medida['lufs']} / {ref['lufs']} LUFS · {medida['tp_db']} / {ref['tp_db']} dBTP")
    # autocorrección: un golpe 12 dB demasiado alto
    estado = E.cargar(video)
    sfx = res['sfx']
    golpe = next(e for e in sfx['diseno']['eventos'] if e['decision'] == 'GENERATE' and e['tipo'] == 'golpe' and _en_voz_test(palabras, e['ancla']))
    alto = D.preparar_sfx(ctx, estado['analisis'], sfx['nivel_voz_db'], sfx['diseno'], mezcla={'eventos': {golpe['clave']: 12.0}, 'bus': 0.0})
    sfx2, _c, qc2 = D.mezclar(ctx, estado['analisis'], estado, alto, res['capas'], None, previas={'eventos': {golpe['clave']: 12.0}, 'bus': 0.0})
    corr = qc2['correcciones']['eventos']
    ok('QC: el golpe que pisa la voz se baja SOLO a él', golpe['clave'] in corr and corr[golpe['clave']] < -3.0, corr)
    ok('QC: tras corregir, todos los sonidos sobre la voz quedan ≥ 8 dB por debajo', qc2['partes']['proteccion']['puntos'] >= 99, qc2['partes']['proteccion']['por_que'])
    ok('QC: las correcciones se SUMAN a las previas (como un fader) y quedan guardadas',
       abs(estado['mezcla_ajustes']['eventos'][golpe['clave']] - (12.0 + corr[golpe['clave']])) < 0.05, estado['mezcla_ajustes'])
    # el bus por true peak: lo empujan los del director → baja su bus; si es la voz, no se toca
    c, bus = MZ.correcciones({'eventos': [], 'mezcla': {'tp_db': -0.4}, 'voz': {'tp_db': -3.0}})
    ok('true peak por los SFX/música: el bus del director baja (≈ −0,9 dB)', -1.2 < bus < -0.6, bus)
    c, bus = MZ.correcciones({'eventos': [], 'mezcla': {'tp_db': 0.8}, 'voz': {'tp_db': 0.9}})
    ok('true peak por la voz original: el director no toca nada (lo dice el Master)', bus == 0.0)
    # la fórmula, con medidas conocidas
    falso = {'eventos': [{'tipo': 'golpe', 'ataque_s': 1.010, 'ancla': 1.0, 'sobre_voz_db': -10.0, 'pista': 'AI SFX IMPACTS'},
                         {'tipo': 'tick', 'ataque_s': 2.0, 'ancla': 2.0, 'sobre_voz_db': -4.0, 'pista': 'AI SFX UI'}],
             'mezcla': {'lufs': -14.0, 'tp_db': -1.5}, 'clipping': 0, 'musica_bajo_voz_db': None}
    st = {'analisis': {'musica': {'en_la_fuente': {'presente': False}}}, 'voz': {'archivo': 'x'}, 'voice_quality_after': {'snr_1_4k_db': 30.0, 'suelo_ruido_db': -60.0},
          'music_decision': {'estado': 'NO_MUSIC_REQUIRED'}, 'sfx_plan': []}
    s, p = MZ.puntuar(falso, st)
    ok('Sound Score: medidas conocidas → partes conocidas (voz 100, ruido 100, sincronía 90, protección 50, mezcla 100)',
       p['voz']['puntos'] == 100 and p['ruido']['puntos'] == 100 and p['sincronia']['puntos'] == 90 and p['proteccion']['puntos'] == 50
       and p['mezcla']['puntos'] == 100, {k: v['puntos'] for k, v in p.items()})
    ok('Sound Score: el total es la suma ponderada', s == round(sum(MZ.PESOS[k] * p[k]['puntos'] / 100 for k in MZ.PESOS)), s)
    INFORME['fase5'] = {'score': qc.get('score'), 'partes': {k: v['puntos'] for k, v in qc['partes'].items()}, 'medidas': qc['medidas'], 'segundos': round(seg, 1)}


def _en_voz_test(palabras, t):
    return any(float(p['start']) <= t <= float(p['end']) for p in palabras)


# ---------------------------------------------------------------------------------------------------------------- main
def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    args = sys.argv[1:]
    fase = args[args.index('--fase') + 1] if '--fase' in args else 'todo'
    salida = Path(args[args.index('--salida') + 1]) if '--salida' in args else Path(tempfile.gettempdir()) / 'cc_ai_sound'
    salida.mkdir(parents=True, exist_ok=True)
    video = Path(args[args.index('--video') + 1]) if '--video' in args else Path.home() / 'Desktop' / 'VIDEOS EN ESPAÑOL' / 'PRUEBA ESPAÑOL.mp4'
    INFORME['video'] = str(video)
    t0 = time.time()
    if '--muestras' in args:
        MUESTRAS.append(args[args.index('--muestras') + 1])
    fases = {'0': fase0, '1': fase1, '2': fase2, '3': fase3, '4': fase4, '5': fase5}
    for k in (sorted(fases) if fase == 'todo' else [fase]):
        t = time.time()
        fn = fases[k]
        fn(salida) if k == '0' else fn(salida, video)
        INFORME[f'segundos_fase{k}'] = round(time.time() - t, 2)
    pasan = sum(1 for _n, b, _d in RESULTADOS if b)
    INFORME['resultados'] = [{'prueba': n, 'pasa': b, 'detalle': d} for n, b, d in RESULTADOS]
    INFORME['registro'] = [m for _n, m, _o in LOG if m.startswith('[AI SOUND]')]
    (salida / 'informe.json').write_text(json.dumps(INFORME, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\n{pasan}/{len(RESULTADOS)} pruebas pasan · {time.time() - t0:.1f} s · informe: {salida / "informe.json"}')
    sys.stdout.flush()
    os._exit(0 if pasan == len(RESULTADOS) else 1)


if __name__ == '__main__':
    main()
