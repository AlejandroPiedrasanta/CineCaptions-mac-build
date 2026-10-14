# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/importar_sonidos.py — elige los mejores sonidos de la biblioteca del autor (E:\...\EFECTOS SONIDO y BODAS & XV) y los deja recortados en 2_recursos/sfx_library/<categoría>. SOLO desarrollo (no entra en el .exe).
"""v5.5.3: importa una selección de la biblioteca de sonidos del autor a sfx_library (categorías nuevas y ampliación de las de siempre).

    python importar_sonidos.py            # plan: qué elegiría por categoría (no escribe nada)
    python importar_sonidos.py --hacer    # recorta y copia; escribe DOCUMENTACION/sfx_origen.json (de dónde salió cada audio)

Por cada categoría: busca en las carpetas indicadas los archivos cuyo nombre cumple el patrón, descarta duplicados (mismo nombre
limpio y duración) y reparte la elección por toda la lista para que haya variedad. Cada audio se recorta: sin silencio al
principio (el golpe cae en la palabra) y como mucho `largo` segundos con fundido de salida. Los cortos (≤ 3 s) van en WAV
16 bit; los largos (aplausos, ambientes, pirotecnia) en MP3 256 kbps. Los que ya existen no se rehacen.
Los derechos de los packs comerciales (Artlist, Envato, Film Score, Netflix Sounds…) son responsabilidad del autor (decidido el 2026-10-13)."""
import json, re, subprocess, sys, unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / '2_recursos' / 'sfx_library'
ORIGEN_JSON = RAIZ / 'DOCUMENTACION' / 'sfx_origen.json'
E = Path(r'E:\VFX-EDICION VIDEOS\DAVINCI RESOLVE\EFECTOS SONIDO')
U = E / 'UTILES'
X = Path(r'E:\VFX-EDICION VIDEOS\DAVINCI RESOLVE\RECURSOS PREMIUN\BODAS  & XV RECURSOS\SONIDOS')
SINO = Path(r'E:\VFX-EDICION VIDEOS\DAVINCI RESOLVE\PANTALLA DE VIDEO\ICONOS DE SI Y NO')
ARTLIST = U / 'Artlist - 200+ Sound Effects'
VARIOS = U / '1_Sfx - Varios'
EXT = ('.wav', '.mp3', '.m4a', '.aif', '.aiff', '.flac', '.ogg')

# (carpeta de sfx_library, cuántos, largo máx. en s, prefijo del nombre, [(carpeta origen, patrón que SÍ, patrón que NO)])
CATEGORIAS = [
    ('Aplausos', 16, 7.0, '', [(X / 'APLAUSOS', r'', None), (E / 'BODA' / 'APLAUSOS', r'', None), (X / 'GRITOS', r'bravo', None)]),
    ('Gritos y ovación', 10, 6.0, '', [(E / 'GRITOS', r'', None), (X / 'GRITOS', r'ovacion|grito|overcrow', None)]),
    ('Pirotecnia', 12, 7.0, '', [(X / 'PIROTECNIA', r'', None), (E / 'BODA' / 'FUEGOS ARTIFICIALES', r'', None)]),
    ('Dinero', 6, 3.0, '', [(E / 'DINERO', r'', None), (ARTLIST, r'gift box', None)]),
    ('Correcto', 10, 2.5, '', [(E / 'POSITIVO -NEGATIVO' / 'POSITIVO', r'', None), (SINO, r'check mark', None),
                               (ARTLIST, r'done-click|^right$|light up', None), (U / 'SFX RISEX', r'^ding$', None)]),
    ('Error', 10, 2.5, '', [(E / 'POSITIVO -NEGATIVO' / 'ERROR', r'', None), (SINO, r'cross mark', None),
                            (ARTLIST, r'^error|radio error|rejected click', None), (U / 'Meme SFX', r'windows error', None),
                            (U / 'SFX RISEX', r'access denied', None)]),
    ('Tiempo', 10, 4.0, '', [(E / 'TIEMPO - CRONOMETRO', r'', None), (ARTLIST, r'tick|^time$', None), (VARIOS, r'contando', None),
                             (U / 'SFX RISEX', r'rewinding|fast forward', None), (ARTLIST, r'back in time', None)]),
    ('Cámara', 12, 2.5, '', [(E / 'VARIADO' / 'CAMARA', r'\.wav$', None), (U / 'Whooshes', r'canon r focus', None),
                             (VARIOS, r'shutter', None), (E / 'BODA' / 'Plus Two - Wedding SFX', r'super 8 - canon|vhs', None)]),
    ('Latidos', 6, 4.0, '', [(E / 'VARIADO' / 'LATIDOS', r'', None), (ARTLIST, r'heart', None)]),
    ('Papel', 7, 2.5, '', [(E / 'VARIADO' / 'PAPEL', r'', None)]),
    ('Selección', 7, 2.0, '', [(E / 'VARIADO' / 'SELECCION', r'', None)]),
    ('Memes', 40, 4.0, '', [(U / 'Meme SFX', r'', r'windows error|typing'), (E / 'MEMES', r'', None)]),
    ('Teclado y texto', 8, 3.0, '', [(E / 'TEXTOS', r'', None), (U / 'Meme SFX', r'typing', None),
                                     (E / 'BODA' / 'Plus Two - Wedding SFX', r'^pen |potlood', None)]),
    ('Naturaleza', 14, 6.0, '', [(E / 'NATURALEZA', r'animales|lluvia|agua|\\es_', r'ambiente'),
                                 (VARIOS, r'horse|seagul|bird squawk|thunder crack', None)]),
    ('Ambientes', 14, 10.0, '', [(X / 'AMBIENTE', r'', None),
                                 (E / 'BODA' / 'Plus Two - Wedding SFX', r'weddingdinner|gardenparty|bridalparty|partychatter|mariachilive1|italiansquare|beachsunset|crickets_tuscany_ext', None)]),
    ('Fiesta', 8, 4.0, '', [(E / 'FIESTAS', r'lata', None), (E / 'CUMPLEAÑOS INFANTILES' / 'SONIDOS', r'', None),
                            (X / 'APLAUSOS', r'pool', None), (U / 'Meme SFX', r'ta da', None)]),
    ('Cinemático', 20, 5.0, '', [(U / '2_Sfx - Cinematic', r'', None),
                                 (U / 'Netflix Sounds', r'intro hit|tension|something|piano note|what will|anxiety|getting nervous', None),
                                 (ARTLIST, r'cinema|braam|tension|robbery|suspicious|fright|trailer', r'loop')]),
    ('Transiciones', 24, 2.5, '', [(ARTLIST, r'transition|swipe|wipe|slice|zoom|spin', None),
                                   (X / 'OTROS', r'transiti|swish|sonic shift', r'^copia'), (VARIOS, r'paso a un|entrar en|cambiar algo', None)]),
    ('Idea', 7, 3.0, '', [(VARIOS, r'ilusion|idea|shimmer|recuerdo', None), (ARTLIST, r'holy sound|shimmering', None),
                          (U / 'Meme SFX', r'heavenly', None), (E / 'MEMES', r'gospel', None)]),
    ('Explosiones', 8, 4.0, '', [(VARIOS, r'detonate|explode|fireball', None), (E / 'VARIADO' / 'OTROS', r'bomba', None),
                                 (U / 'Cinematic SFX', r'sonic boom', None), (ARTLIST, r'crack|breaking impact|crash glass', None)]),
    ('Pop', 10, 1.5, '', [(U / 'SFX RISEX', r'^pop$', None), (U / 'Meme SFX', r'splat|rubber duck', None),
                          (X / 'OTROS', r'balloonies', None), (ARTLIST, r'bouncy|plastic', None), (E / 'TEXTOS', r'tap_pop', None)]),
    ('Intro y logos', 8, 4.0, '', [(ARTLIST, r'universal logos', None), (X / 'OTROS', r'logos', None)]),
    # las de siempre, ampliadas (prefijo para no pisar los audios de fábrica)
    ('Whoosh', 30, 2.5, 'Pro ', [(U / 'Whooshes', r'small|human|cloth|punch|hit_|space|wobble', None),
                                 (U / 'Cinematic SFX', r'whoosh', r'reverse'), (U / 'SFX RISEX', r'woosh', None), (VARIOS, r'whoosh|woosh', r'^copia')]),
    ('Riser', 14, 5.0, 'Pro ', [(U / 'SFX RISEX', r'riser|sweep|subsonic|airy long|rocket', None), (U / 'Cinematic SFX', r'riser|swell|ramp', None),
                                (ARTLIST, r'riser|^rise$|build|rising tension|flash rise', None), (E / 'RISER', r'', None)]),
    ('Hit', 14, 2.5, 'Pro ', [(U / 'Cinematic SFX', r'hit|slam', None), (ARTLIST, r'impact|hits|^hard$|punch|smash', None),
                              (U / 'SFX RISEX', r'grand hit|impact|metal slam', None)]),
    ('Click', 10, 1.0, 'Pro ', [(VARIOS, r'click|switch', r'^copia'), (ARTLIST, r'click', r'rejected|done')]),
    ('Glitch', 8, 2.0, 'Pro ', [(ARTLIST, r'bad tv|glitch|noise radio|dead connection|no contact|robo noise', None),
                                (U / 'SFX RISEX', r'glitch|dial-up|disc read|network connect', None)]),
]

LIMPIAR = [r'^(copia de|copy of)\s+', r'\s*-\s*sound\s*-\s*sr$', r'_cinem\d*$', r'^es_', r'\s*-\s*sfx producer$',
           r'^(artlist( original| studios| productions| foley)?)\s*-\s*', r'_1$']


def limpio(nombre):
    n = unicodedata.normalize('NFKD', Path(nombre).stem).encode('ascii', 'ignore').decode('ascii')   # nombres ASCII: viajan a Resolve
    for p in LIMPIAR:
        n = re.sub(p, '', n, flags=re.I)
    n = re.sub(r'[_]+', ' ', n)
    partes = [p for p in re.split(r'\s+-\s+', n) if p.strip()]
    if len(partes) >= 3:                       # «Autor - Pack - Sonido»: queda el sonido
        n = partes[-1]
    n = re.sub(r'^\d+(\.\d+)?\s+', '', n)      # «37.2 Idea» -> «Idea»
    n = re.sub(r'\s+', ' ', n).strip(' -.')
    return (n[:1].upper() + n[1:])[:44] if n else 'Sonido'


def duracion(p):
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)],
                           capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def candidatos(fuentes):
    vistos, lista = set(), []
    for carpeta, si, no in fuentes:
        if not carpeta.is_dir():
            print(f'  ! no existe {carpeta}')
            continue
        for a in sorted(carpeta.rglob('*')):
            if a.suffix.lower() not in EXT or not a.is_file():
                continue
            rel = str(a.relative_to(carpeta)).lower()
            if si and not re.search(si, rel, re.I):
                continue
            if no and re.search(no, rel, re.I):
                continue
            if a not in vistos:
                vistos.add(a)
                lista.append(a)
    return lista


def repartir(lista, n):
    if len(lista) <= n:
        return list(lista)
    paso = len(lista) / n
    return [lista[int(i * paso)] for i in range(n)]


def plan():
    todos = {}
    for cat, cuantos, largo, prefijo, fuentes in CATEGORIAS:
        cands = candidatos(fuentes)
        with ThreadPoolExecutor(8) as ex:
            durs = list(ex.map(duracion, cands))
        unicos, firmas = [], set()
        for a, d in zip(cands, durs):
            if d < 0.08:
                continue
            firma = (limpio(a.name).lower(), round(d, 1))
            if firma in firmas:
                continue
            firmas.add(firma)
            unicos.append((a, d))
        # los cortos primero cuando sobra donde elegir (un SFX de 20 s recortado suena a corte)
        if len(unicos) > cuantos * 2:
            unicos = [u for u in unicos if u[1] <= largo * 2.5] or unicos
        todos[cat] = (largo, prefijo, repartir(unicos, cuantos))
    return todos


def nombre_destino(cat, prefijo, a, d, largo, usados):
    base = prefijo + limpio(a.name)
    ext = '.wav' if min(d, largo) <= 3.0 else '.mp3'
    nombre, i = base, 2
    while (nombre.lower() + ext) in usados:            # 'usados' ya trae los audios que había en la carpeta
        nombre, i = f'{base} {i}', i + 1
    usados.add(nombre.lower() + ext)
    return nombre + ext


def convertir(origen, destino, d, largo):
    filtros = ['silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.01']
    if d > largo:
        filtros += [f'atrim=0:{largo:.2f}', f'afade=t=out:st={max(0.0, largo - 0.4):.2f}:d=0.4']
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', str(origen), '-af', ','.join(filtros), '-ac', '2', '-ar', '44100']
    cmd += ['-c:a', 'pcm_s16le'] if destino.suffix == '.wav' else ['-c:a', 'libmp3lame', '-b:a', '256k']
    subprocess.run(cmd + [str(destino)], check=True, timeout=120)


def main():
    hacer = '--hacer' in sys.argv
    todos = plan()
    origen = json.loads(ORIGEN_JSON.read_text(encoding='utf-8')) if ORIGEN_JSON.exists() else {}
    total = 0
    for cat, (largo, prefijo, elegidos) in todos.items():
        print(f'## {cat}: {len(elegidos)}')
        carpeta = DESTINO / cat
        usados = {p.name.lower() for p in carpeta.iterdir()} if carpeta.is_dir() else set()
        ya = {v for k, v in origen.items() if k.startswith(cat + '/')}
        for a, d in elegidos:
            if str(a) in ya:                              # ya importado en una pasada anterior
                continue
            nombre = nombre_destino(cat, prefijo, a, d, largo, usados)
            print(f'   {nombre:48} <- {a.name[:50]} ({d:.1f} s)')
            if hacer:
                carpeta.mkdir(parents=True, exist_ok=True)
                convertir(a, carpeta / nombre, d, largo)
                origen[f'{cat}/{nombre}'] = str(a)
            total += 1
    if hacer:
        ORIGEN_JSON.write_text(json.dumps(origen, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    print(f'TOTAL {total} sonidos' + ('' if hacer else ' (plan; --hacer para copiarlos)'))


if __name__ == '__main__':
    main()
