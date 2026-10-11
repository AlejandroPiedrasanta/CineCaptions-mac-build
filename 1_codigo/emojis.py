# CineCaptions · By Cinema Productions
# 1_codigo/emojis.py — emojis de las palabras clave: catálogo, biblioteca Fluent 3D, PNG propios y sugerencias por idioma.
"""
emojis.py  (v3.3.0; packs del usuario v3.3.2; emojis del sistema v3.3.3;
            biblioteca desde la ventana v3.3.4)
------------------------------------------------------------------------
Los emojis de las palabras clave. Pedido del usuario (21-09): «poner emojis a
las palabras claves, bonitos y estéticos como los de iOS, que funcione en
todos los idiomas... que salga por encima del bloque de dinámico o en la
parte inferior, a elección».

  - El catalogo viaja en emojis/ (lo arma herramientas/emojis_fluent.py):
    Fluent Emoji 3D de Microsoft (MIT; los de Apple no se pueden
    redistribuir) y, por emoji, sus palabras clave en cada idioma de
    transcripcion que tenga Unicode CLDR.
  - v3.3.2: ademas de ese catalogo, los PNG del USUARIO en
    ~/DaVinciSubtitles/emojis/ (carpeta_usuario): un archivo llamado como
    el emoji reemplaza la imagen de ese id y cualquier otro es un emoji
    «mio». Lo que viaja a Resolve sale SIEMPRE de copia_para_resolve
    (nombre rcs_emoji_<id>.png: el prefijo que reconocen los gemelos).
  - v3.3.3: el catalogo trae ~1 400 emojis de Unicode con claves CLDR y
    solo 271 con PNG Fluent; el resto se dibuja con la FUENTE DEL SISTEMA
    (Apple Color Emoji / Segoe UI Emoji) en cache local, y catalogo() solo
    ofrece los que tienen alguna imagen posible. El emoji viaja centrado
    encima del bloque y dura hasta el fin de su palabra (emoji_fin).
  - El usuario elige a mano (pincel «Emoji» de la ventana de palabras) o
    pide sugerencias: sugerir() busca la palabra en las claves del IDIOMA
    DEL VIDEO, con el ingles de respaldo. Nada se traduce a mano.
  - La eleccion vive en la palabra (w["emoji"] = id): viaja con el
    autoguardado y con «¿Sigues desde ahi?» sin tocar la forma del resultado
    de la ventana. asignar() la pasa a los bloques en un pase APARTE —
    build_manual_cues no se toca (decenas de baterias fijan su salida).
  - Al manifiesto va la copia PERSISTENTE del PNG (la leccion de los SFX de
    esta misma version: una ruta de dentro del programa muere al cerrarlo).
"""
import json
import os
import re
import shutil
import sys
import time
import unicodedata
from pathlib import Path

import sfx_rules

CARPETA_EMOJIS_USADOS = sfx_rules.CARPETA_USUARIO / 'emojis_usados'
CARPETA_USUARIO_EMOJIS = sfx_rules.CARPETA_USUARIO / 'emojis'
CARPETA_CACHE_MINI = sfx_rules.CARPETA_USUARIO / 'emojis_cache' / 'mini'
CARPETA_CACHE_SISTEMA = sfx_rules.CARPETA_USUARIO / 'emojis_cache' / 'sistema'
CARPETA_CACHE_MINI_SISTEMA = sfx_rules.CARPETA_USUARIO / 'emojis_cache' / 'mini_sistema'
LADO_SISTEMA = 256
GRUPO_USUARIO = 'mios'
POSICIONES = ('arriba', 'abajo')

_CACHE = {}
_PREF = {'sistema': False, 'estilo': 'animado'}
ESTILOS = ('animado', 'fluent3d', 'noto', 'sistema')          # v5.5: el estilo de los emojis: «animado» (los Noto animados cuando existen y, si no, 3D), 3D (Fluent), Google (Noto) o los del sistema (planos); 3D y Google se bajan al usarlos (emojis_sets.py)
CARPETA_CACHE_MINI_SET = sfx_rules.CARPETA_USUARIO / 'emojis_cache' / 'mini_set'
_RANGO_GRUPO = {
    'simbolos': 0, 'dinero': 0, 'trabajo': 0, 'corazones': 0, 'objetos': 0,
    'personas': 2, 'manos': 2, 'caras': 3,
}
_VS16 = '\ufe0f'


def carpeta():
    return sfx_rules.base_recursos() / 'emojis'


def carpeta_usuario():
    """La carpeta de los PNG del usuario (existe o no; quien la abre la
    crea)."""
    return CARPETA_USUARIO_EMOJIS


def usar_sistema(valor=None):
    """La preferencia «Emojis del sistema» (la App la fija al arrancar y
    al tocar la casilla del selector). Cambiarla invalida el catalogo:
    la lista de emojis disponibles depende de ella. v5.5: es el caso «sistema» de estilo():
    True lo elige; False vuelve al animado/3D si estaba en el del sistema."""
    if valor is not None and bool(valor) != _PREF['sistema']:
        estilo('sistema' if valor else 'animado')
    return _PREF['sistema']


def estilo(valor=None):
    """v5.5: el estilo de los emojis: 'animado' (los Noto animados cuando existen; si no, 3D), 'fluent3d' (3D fijo, Microsoft; lo que no trae el programa se baja al usarlo), 'noto' (Google fijo) o 'sistema' (la fuente del equipo, planos).
    Cambiarlo invalida el catálogo. Sin argumento devuelve el actual."""
    if valor in ESTILOS and valor != _PREF['estilo']:
        _PREF['estilo'] = valor
        _PREF['sistema'] = valor == 'sistema'
        _CACHE.pop('lista', None)
    return _PREF['estilo']


def _clave_set():
    """El set de imágenes fijas que corresponde al estilo: el 3D de Fluent para «animado» y «fluent3d»; Noto para «noto»; ninguno para «sistema»."""
    return 'fluent3d' if _PREF['estilo'] == 'animado' else _PREF['estilo']


def animados_activo():
    """True si los emojis que tienen versión animada (Noto Animated) viajan como secuencia que se mueve: sólo con el estilo «animado»."""
    return _PREF['estilo'] == 'animado'


def _set_activo():
    """El módulo de sets si el estilo actual es uno que se baja (3D / Google), o None."""
    if _clave_set() in ('fluent3d', 'noto'):
        import emojis_sets
        return emojis_sets
    return None


def fuente_sistema():
    """La fuente de emojis a color del equipo, o None si no esta."""
    if sys.platform.startswith('win'):
        ruta = Path(os.environ.get('WINDIR') or 'C:\\Windows') / 'Fonts' / 'seguiemj.ttf'
    elif sys.platform == 'darwin':
        ruta = Path('/System/Library/Fonts/Apple Color Emoji.ttc')
    else:
        ruta = Path('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf')
    return ruta if ruta.is_file() else None


def _tamanos_fuente():
    if sys.platform == 'darwin':
        return (160, 96, 64)
    return (LADO_SISTEMA, 160, 128, 109)


def _abrir_fuente_sistema():
    if 'fuente' not in _CACHE:
        fuente = None
        ruta = fuente_sistema()
        if ruta is not None:
            try:
                from PIL import ImageFont
                for tam in _tamanos_fuente():
                    try:
                        fuente = ImageFont.truetype(str(ruta), tam)
                        break
                    except Exception:
                        continue
            except Exception:
                fuente = None
        _CACHE['fuente'] = fuente
    return _CACHE['fuente']


def _dibujar(glifo, fuente):
    """El glifo dibujado a color, recortado y en un cuadrado transparente
    (o None si la fuente no dibujo nada)."""
    from PIL import Image, ImageDraw
    tam = int(fuente.size)
    img = Image.new('RGBA', (tam * 2, tam * 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((tam // 2, tam // 2), glifo, font=fuente,
                             embedded_color=True)
    caja = img.getbbox()
    if not caja:
        return None
    recorte = img.crop(caja)
    lado = max(recorte.width, recorte.height)
    cuadro = Image.new('RGBA', (lado, lado), (0, 0, 0, 0))
    cuadro.paste(recorte, ((lado - recorte.width) // 2, (lado - recorte.height) // 2))
    return cuadro


def _tiene_color(img):
    """Si el dibujo lleva color de verdad: una fuente que Pillow no sabe
    dibujar a color sale en gris (R = G = B)."""
    pixeles = list(img.getdata())
    for r, g, b, a in pixeles[::53]:
        if a > 128 and (abs(r - g) > 16 or abs(g - b) > 16):
            return True
    return False


def puede_dibujar_sistema():
    """True si la fuente del sistema existe y Pillow la dibuja A COLOR.
    Se prueba UNA vez con 🔥 (en el Mac no se pudo verificar desde aqui:
    por eso el respaldo a los Fluent es automatico y se dice)."""
    if 'sistema_ok' not in _CACHE:
        ok = False
        try:
            fuente = _abrir_fuente_sistema()
            if fuente is not None:
                img = _dibujar('🔥', fuente)
                ok = img is not None and _tiene_color(img)
        except Exception:
            ok = False
        _CACHE['sistema_ok'] = ok
    return _CACHE['sistema_ok']


def _glifos_del_sistema():
    """Los codepoints que la fuente del sistema tiene (su cmap), o None si
    no se pudo leer (entonces no se filtra: se confia en el dibujo)."""
    if 'cmap' not in _CACHE:
        codigos = None
        try:
            ruta = fuente_sistema()
            if ruta is not None:
                import fuentes_sistema
                codigos = fuentes_sistema._codigos_de_cmap(ruta)
        except Exception:
            codigos = None
        _CACHE['cmap'] = codigos
    return _CACHE['cmap']


def _sistema_dibuja(glifo):
    """Si el emoji (un solo simbolo, con o sin VS16) esta en la fuente."""
    if not glifo:
        return False
    base = glifo.replace(_VS16, '')
    if not base:
        return False
    codigos = _glifos_del_sistema()
    if codigos is None:
        return True
    return all(ord(c) in codigos for c in base)


def sistema_activo():
    return usar_sistema() and puede_dibujar_sistema()


def renderizar_sistema(eid, forzar=False):
    """El PNG del emoji dibujado con la fuente del sistema, en cache
    (emojis_cache/sistema/<id>.png), o None. `forzar`: aunque el estilo elegido no sea el del
    sistema (v5.5: el que no tiene su versión 3D o Google se dibuja así)."""
    e = por_id(eid)
    if not e or not e.get('glifo') or not (sistema_activo() or (forzar and puede_dibujar_sistema())):
        return None
    if not _sistema_dibuja(e['glifo']):
        return None
    destino = CARPETA_CACHE_SISTEMA / f'{eid}.png'
    if destino.is_file():
        return destino
    try:
        img = _dibujar(e['glifo'], _abrir_fuente_sistema())
        if img is None:
            return None
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_name(f'{destino.name}.{_marca_temporal()}')
        img.save(temporal, format='PNG')
        os.replace(temporal, destino)
        return destino
    except Exception:
        return destino if destino.is_file() else None


def _marca_temporal():
    import threading
    return f'{os.getpid()}.{threading.get_ident()}.copiando'


def preparar_minis(al_terminar=None):
    """Fabrica en un hilo daemon las miniaturas que falten (las del
    sistema y las del usuario): el selector abre con todo listo (mientras
    tanto dibuja el glifo, ruta_mini(fabricar=False)). Devuelve el hilo."""
    import threading

    def trabajo():
        try:
            for e in list(catalogo()):
                ruta_mini(e['id'])
        except Exception:
            pass
        try:
            if al_terminar:
                al_terminar()
        except Exception:
            return

    hilo = threading.Thread(target=trabajo, daemon=True)
    hilo.start()
    return hilo


def plegar(texto):
    """Minusculas (casefold) y sin tildes: la MISMA regla con la que la
    herramienta guardo las claves. Sin eso «Fuego» no encontraria «fuego»."""
    t = unicodedata.normalize('NFD', str(texto or '').casefold())
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn').strip()


def _slug(texto):
    """Un id de archivo: minusculas ascii con '_' y SIN digito final
    (Resolve toma «algo_1.png» por una secuencia de imagenes; la misma
    regla que la herramienta que arma el catalogo)."""
    s = re.sub('[^a-z0-9]+', '_', plegar(texto)).strip('_') or 'archivo'
    if s[-1:].isdigit():
        return s + '_x'
    return s


def _catalogo_base():
    """El catalogo que viaja con el programa (emojis/indice.json)."""
    if 'base' not in _CACHE:
        try:
            datos = json.loads((carpeta() / 'indice.json').read_text(encoding='utf-8'))
            lista = [e for e in (datos.get('emojis') or [])
                     if isinstance(e, dict) and e.get('id')]
        except (OSError, ValueError, AttributeError):
            lista = []
        _CACHE['base'] = lista
    return _CACHE['base']


_FIRMA = {'t': 0.0, 'v': None}
VIGENCIA_FIRMA_S = 0.75          # catalogo() se llama cientos de veces por redibujado: la carpeta se vuelve a mirar como mucho cada 0,75 s


def _firma_usuario():
    """Algo barato que cambia cuando el usuario toca su carpeta: el mtime
    de la carpeta y de sus subcarpetas (catalogo() se llama cientos de
    veces por guion — listar 4000 archivos cada vez no vale; v5.7: ni
    mirar las subcarpetas cada vez: con 400 emojis en un guion eran ~4 s
    de redibujado). Los cambios de la propia interfaz llaman a _invalidar()."""
    ahora = time.monotonic()
    if _FIRMA['t'] and ahora - _FIRMA['t'] < VIGENCIA_FIRMA_S:
        return _FIRMA['v']
    raiz = carpeta_usuario()
    try:
        if not raiz.is_dir():
            firma = None
        else:
            lista = [raiz.stat().st_mtime_ns]
            for sub in sorted(p for p in raiz.iterdir() if p.is_dir()):
                lista.append(sub.stat().st_mtime_ns)
            firma = tuple(lista)
    except OSError:
        firma = None
    _FIRMA['t'], _FIRMA['v'] = ahora, firma
    return firma


def _casar(stem, por_glifo, por_id, por_nombre):
    """Con que emoji conocido va un archivo del usuario, por su NOMBRE:
    el glifo («🔥»), el codepoint («1F525», «U+1F525», «1f525-fe0f»,
    «emoji_u1f525») o el id / nombre ingles («fire», «Fire»,
    «grinning_face», «Grinning Face»). None = es un emoji suyo."""
    s = str(stem or '').strip()
    limpio = s.replace(_VS16, '')
    if limpio in por_glifo:
        return por_glifo[limpio]
    m = re.fullmatch('(?:emoji_)?(?:u\\+?)?([0-9a-f]{4,6}(?:[-_ ][0-9a-f]{4,6})*)', s.lower())
    if m:
        try:
            glifo = ''.join(chr(int(h, 16)) for h in re.split('[-_ ]', m.group(1)))
        except (ValueError, OverflowError):
            glifo = ''
        glifo = glifo.replace(_VS16, '')
        if glifo in por_glifo:
            return por_glifo[glifo]
    clave = plegar(re.sub('[_\\-]+', ' ', s))
    if not clave:
        return None
    clave_id = re.sub('[^a-z0-9]+', '_', clave).strip('_')
    if clave_id in por_id:
        return por_id[clave_id]
    return por_nombre.get(clave)


def _archivos_usuario():
    """Los PNG de la biblioteca del usuario (subcarpetas incluidas), en
    orden estable."""
    try:
        return sorted(p for p in carpeta_usuario().rglob('*.png') if p.is_file())
    except OSError:
        return []


def _indices(base):
    """Los tres indices con los que _casar resuelve un nombre de archivo."""
    por_glifo = {e.get('glifo', ''): e for e in base if e.get('glifo')}
    por_id = {e['id']: e for e in base}
    por_nombre = {}
    for e in base:
        nombres = (e.get('claves') or {}).get('en') or ()
        if not nombres:
            continue
        por_nombre.setdefault(plegar(nombres[0]), e)
    return por_glifo, por_id, por_nombre


def _con_usuario(base):
    """El catalogo base con los PNG del usuario: los que casan REEMPLAZAN
    la imagen (misma entrada, mismas claves); los demas se suman al final
    como grupo GRUPO_USUARIO con su nombre de archivo de unica clave."""
    archivos = _archivos_usuario()
    if not archivos:
        return list(base)
    por_glifo, por_id, por_nombre = _indices(base)
    reemplazos, propios, vistos, exactos = {}, [], set(), set()
    for p in archivos:
        e = _casar(p.stem, por_glifo, por_id, por_nombre)
        if e is not None:
            if e['id'] in exactos:
                continue
            reemplazos[e['id']] = str(p)
            if p.stem == e['id']:
                exactos.add(e['id'])
            continue
        eid = 'mio_' + _slug(p.stem)
        if eid in por_id or eid in vistos:
            continue
        vistos.add(eid)
        legible = plegar(re.sub('[_\\-]+', ' ', p.stem)) or p.stem
        propios.append({
            'id': eid,
            'glifo': '',
            'grupo': GRUPO_USUARIO,
            'archivo': str(p),
            'usuario': True,
            'claves': {'en': [legible]},
        })
    lista = []
    for e in base:
        if e['id'] in reemplazos:
            e = dict(e, archivo=reemplazos[e['id']], usuario=True)
        lista.append(e)
    return lista + propios


def _disponible(e):
    """Si hay alguna imagen posible para ese emoji: la Fluent que viaja,
    la del usuario, o la fuente del sistema (v3.3.3: el catalogo trae
    ~1 400 emojis y solo 271 con PNG Fluent; el resto existe solo si el
    sistema los dibuja)."""
    if e.get('usuario') or e.get('archivo'):
        return True
    S = _set_activo()
    if S is not None and S.hay(_clave_set(), e):
        return True
    if S is not None:                                         # 3D / Google: lo que no tienen se dibuja con la fuente del sistema, si la hay
        return puede_dibujar_sistema() and _sistema_dibuja(e.get('glifo'))
    return sistema_activo() and _sistema_dibuja(e.get('glifo'))


def catalogo():
    """[{id, glifo, grupo, archivo, claves{idioma: [...]}}] en el orden del
    catalogo, mas los PNG del usuario (v3.3.2; 'usuario': True y
    'archivo' absoluto), y solo los que tienen alguna imagen posible
    (v3.3.3: los que no traen PNG Fluent entran si la fuente del sistema
    los dibuja). [] si la carpeta no esta (un compilado sin emojis/): el
    resto del programa sigue igual, sin emojis. Los cambios en la carpeta
    del usuario se ven en la siguiente llamada."""
    firma = (_firma_usuario(), usar_sistema(), _clave_set())
    if 'lista' not in _CACHE or _CACHE.get('firma') != firma:
        base = _catalogo_base()
        lista = _con_usuario(base) if firma[0] is not None else list(base)
        lista = [e for e in lista if _disponible(e)]
        _CACHE['lista'] = lista
        _CACHE['por_id'] = {e['id']: e for e in lista}
        _CACHE['firma'] = firma
    return _CACHE['lista']


def por_id(eid):
    catalogo()
    return _CACHE['por_id'].get(eid)


def origen_de(eid):
    """('usuario' | 'sistema' | 'fluent', ruta) de la imagen que manda
    para ese emoji, o (None, None). Prioridad: el pack del usuario, la
    fuente del sistema (si la preferencia esta activa y dibuja), Fluent."""
    e = por_id(eid)
    if not e:
        return (None, None)
    if e.get('usuario'):
        return ('usuario', Path(e['archivo']))
    S = _set_activo()
    if S is not None:
        r = S.ruta(_clave_set(), eid)
        if r is not None:
            return ('set', r)
        if S.hay(_clave_set(), e):
            S.pedir(_clave_set(), e)                         # sin bajar todavía: se pide en segundo plano (copia_para_resolve lo baja al momento) y mientras sale el de siempre
        if e.get('archivo') and _clave_set() == 'fluent3d':
            return ('fluent', carpeta() / 'png' / e['archivo'])
        ruta = renderizar_sistema(eid, forzar=True)
        if ruta is not None:
            return ('sistema', ruta)
        if e.get('archivo'):
            return ('fluent', carpeta() / 'png' / e['archivo'])
        return (None, None)
    if sistema_activo():
        ruta = renderizar_sistema(eid)
        if ruta is not None:
            return ('sistema', ruta)
    if e.get('archivo'):
        return ('fluent', carpeta() / 'png' / e['archivo'])
    return (None, None)


def ruta_png(eid):
    return origen_de(eid)[1]


def _fabricar_mini(origen, mini):
    try:
        if not mini.is_file() or mini.stat().st_mtime < origen.stat().st_mtime:
            from PIL import Image
            with Image.open(origen) as img:
                img = img.convert('RGBA')
                img.thumbnail((48, 48), Image.LANCZOS)
                lienzo = Image.new('RGBA', (48, 48), (0, 0, 0, 0))
                lienzo.paste(img, ((48 - img.width) // 2, (48 - img.height) // 2))
            mini.parent.mkdir(parents=True, exist_ok=True)
            temporal = mini.with_name(f'{mini.name}.{_marca_temporal()}')
            lienzo.save(temporal, format='PNG')
            os.replace(temporal, mini)
        return mini
    except Exception:
        return mini if mini.is_file() else origen


def ruta_mini(eid, fabricar=True):
    """La miniatura de 48 px del selector. Para un PNG del usuario o del
    sistema se fabrica UNA vez (Pillow) en emojis_cache/ y se rehace si el
    origen cambio; si no se puede, el propio PNG (el selector lo reduce
    igual). Con fabricar=False no dibuja nada: devuelve la mini si YA esta
    (el selector no puede pararse 30 s dibujando 1 400 emojis; eso lo hace
    preparar_minis en su hilo) y None si no."""
    if not fabricar:
        e = por_id(eid)
        if not e:
            return None
        if e.get('usuario'):
            mini = CARPETA_CACHE_MINI / f'{eid}.png'
            return mini if mini.is_file() else None
        S = _set_activo()
        if S is not None:
            r = S.ruta(_clave_set(), eid)
            if r is not None:                                  # el PNG de este set ya está bajado: su miniatura se hace al momento (48 px, una sola)
                return _fabricar_mini(r, CARPETA_CACHE_MINI_SET / _clave_set() / f'{eid}.png')
            if S.hay(_clave_set(), e):
                S.pedir(_clave_set(), e)
        if (sistema_activo() or (S is not None and puede_dibujar_sistema())) and _sistema_dibuja(e.get('glifo')) and not (S is not None and e.get('archivo')):
            mini = CARPETA_CACHE_MINI_SISTEMA / f'{eid}.png'
            return mini if mini.is_file() else None
        if e.get('archivo'):
            return carpeta() / 'mini' / e['archivo']
        return None
    origen, ruta = origen_de(eid)
    if ruta is None:
        return None
    if origen == 'set':
        return _fabricar_mini(ruta, CARPETA_CACHE_MINI_SET / _clave_set() / f'{eid}.png')
    if origen == 'fluent':
        return carpeta() / 'mini' / ruta.name
    if origen == 'sistema':
        return _fabricar_mini(ruta, CARPETA_CACHE_MINI_SISTEMA / f'{eid}.png')
    return _fabricar_mini(ruta, CARPETA_CACHE_MINI / f'{eid}.png')


def copia_para_resolve(eid):
    """La ruta que viaja a Resolve: emojis_usados/rcs_emoji_<id>.png.

    El nombre lleva el prefijo que los gemelos reconocen como NUESTRO
    (es_clip_texto_nuestro: sin el, la pista EMOJI contaria como ajena y
    cada corrida apilaria otra) y ningun id termina en digito. Para un
    emoji Fluent del programa es la copia de siempre (ruta_persistente);
    para uno del usuario o del sistema se copia con ese nombre y se
    re-copia si el PNG cambio de tamaño o de fecha. None si no hay
    archivo; si copiar falla, la ruta original (nunca peor que antes)."""
    S = _set_activo()
    if S is not None:                                          # v5.5: en 3D / Google el emoji se baja AHORA si falta (unos segundos; sin internet sale el de siempre)
        e = por_id(eid)
        if e is not None and S.ruta(_clave_set(), eid) is None and S.hay(_clave_set(), e):
            S.asegurar(_clave_set(), e)
    origen, png = origen_de(eid)
    if png is None or not png.is_file():
        return None
    if origen == 'fluent':
        return str(sfx_rules.ruta_persistente(str(png), carpeta=CARPETA_EMOJIS_USADOS))
    destino = CARPETA_EMOJIS_USADOS / f'rcs_emoji_{eid}.png'
    try:
        st_o = png.stat()
        if (not destino.is_file()
                or destino.stat().st_size != st_o.st_size
                or destino.stat().st_mtime < st_o.st_mtime
                or (origen == 'set' and not _mismo_contenido(png, destino))):      # al cambiar de estilo el nombre es el mismo: se compara el contenido
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporal = destino.with_name(destino.name + '.copiando')
            shutil.copyfile(png, temporal)
            os.replace(temporal, destino)
        return str(destino)
    except OSError:
        return str(png)


def _invalidar():
    """Olvida la lista: pisar un archivo de la biblioteca no cambia el mtime
    de la carpeta y _firma_usuario no lo veria."""
    _CACHE.pop('lista', None)
    _CACHE.pop('firma', None)
    _FIRMA['t'] = 0.0


def _mismo_contenido(a, b):
    try:
        import filecmp
        return filecmp.cmp(str(a), str(b), shallow=False)
    except OSError:
        return False


def _copiar_a_biblioteca(origen, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(f'{destino.name}.{_marca_temporal()}')
    shutil.copyfile(origen, temporal)
    os.replace(temporal, destino)
    _invalidar()


def guardar_en_biblioteca(ruta_png):
    """«➕ Mi PNG…» (v3.3.4, pedido literal: «el usuario elige el png que
    quiere que aparezca justo en esa palabra... que se vaya ampliando su
    biblioteca»): copia el PNG a la biblioteca y devuelve el id con el que
    catalogo() lo ofrece (mio_<slug>). El mismo archivo dos veces es el
    mismo id; otro contenido con el mismo nombre va como «nombre (2)». Si
    el nombre casa con un emoji del catalogo («fire.png», «🔥.png») se
    guarda como «nombre (mío)»: «Mi PNG» pone una imagen EN ESA PALABRA, no
    reemplaza 🔥 en todo el guion sin avisar (para eso esta
    reemplazar_con_png)."""
    origen = Path(ruta_png)
    if not origen.is_file():
        raise FileNotFoundError(str(origen))
    stem = origen.stem.strip() or 'imagen'
    if _casar(stem, *_indices(_catalogo_base())) is not None:
        stem = f'{stem} (mío)'
    tomados = {}
    for p in _archivos_usuario():
        tomados.setdefault('mio_' + _slug(p.stem), p)
    raiz, n = carpeta_usuario(), 1
    while True:
        nombre = stem if n == 1 else f'{stem} ({n})'
        eid = 'mio_' + _slug(nombre)
        otro = tomados.get(eid)
        if otro is None:
            _copiar_a_biblioteca(origen, raiz / f'{nombre}.png')
            return eid
        if _mismo_contenido(origen, otro):
            return eid
        n += 1


def reemplazar_con_png(eid, ruta_png):
    """«Usar mi PNG en lugar de este emoji…» (v3.3.4, pedido literal:
    «reemplazar los emojis por el png del usuario»): copia el PNG a la
    biblioteca con el nombre EXACTO del id («fire.png»), que _casar
    resuelve por id y que en _con_usuario gana a cualquier otro nombre.
    Desde ahi todas las palabras con ese emoji lo muestran y
    copia_para_resolve lo manda a Resolve. Devuelve la ruta."""
    if str(eid).startswith('mio_') or por_id(eid) is None:
        raise ValueError(f'no es un emoji del catálogo: {eid}')
    origen = Path(ruta_png)
    if not origen.is_file():
        raise FileNotFoundError(str(origen))
    destino = carpeta_usuario() / f'{eid}.png'
    _copiar_a_biblioteca(origen, destino)
    return destino


def quitar_de_biblioteca(eid):
    """Borra de la biblioteca lo que nuestra interfaz puso: el archivo de
    un emoji «mio», o SOLO «<id>.png» de un reemplazo (si otro archivo
    sigue casando con ese emoji, sigue mandando: la carpeta es del
    usuario). Devuelve la ruta borrada, o None si no habia nada."""
    raiz = carpeta_usuario()
    if str(eid).startswith('mio_'):
        e = por_id(eid)
        ruta = Path(e['archivo']) if e and e.get('archivo') else None
    else:
        ruta = raiz / f'{eid}.png'
    if ruta is None or not ruta.is_file():
        return None
    try:
        dentro = ruta.resolve().is_relative_to(raiz.resolve())
    except (OSError, ValueError, AttributeError):
        dentro = False
    if not dentro:
        return None
    ruta.unlink()
    _invalidar()
    return ruta


def buscar(texto, idiomas=('es', 'en')):
    """Lo que el buscador del selector ensena: emojis con alguna clave que
    CONTIENE el texto, en cualquiera de esos idiomas. Vacio = todos."""
    q = plegar(texto)
    if not q:
        return catalogo()
    fuera = []
    for e in catalogo():
        claves = e.get('claves') or {}
        if any(q in k for cod in idiomas for k in (claves.get(cod) or ())):
            fuera.append(e)
    return fuera


def _nucleo(palabra):
    """La palabra plegada sin la puntuacion pegada ('¡Fuego!' -> 'fuego')."""
    w = plegar(palabra)
    while w and not w[0].isalnum():
        w = w[1:]
    while w and not w[-1].isalnum():
        w = w[:-1]
    return w


def sugerir(palabra, idioma, limite=6):
    """Ids de emoji para una palabra, del mas al menos claro.

    Coincidencias, de mas a menos fuerte: el NOMBRE del emoji (la primera
    clave), otra clave exacta, la clave como raiz de la palabra (plural o
    diminutivo: «fuegos», «dinerito»; hasta 4 letras de mas) y la palabra
    como parte de una clave de varias («bolsa de dinero» para «dinero»).
    Primero el idioma del video; el ingles vale un tercio. Palabras de menos
    de 3 letras no sugieren nada (conectores, siglas).
    """
    w = _nucleo(palabra)
    if len(w) < 3:
        return []
    puntos = {}
    orden = {}
    for peso, cod in ((3, idioma), (1, 'en')):
        for n, e in enumerate(catalogo()):
            orden.setdefault(e['id'], n)
            mejor = 0
            for i, k in enumerate((e.get('claves') or {}).get(cod) or ()):
                if len(k) < 3:
                    continue
                if k == w:
                    p = 10 if i == 0 else 8
                elif len(k) >= 4 and w.startswith(k) and len(w) - len(k) <= 4:
                    p = 5
                elif ' ' in k and w in k.split():
                    p = 3
                else:
                    continue
                mejor = max(mejor, p)
            if mejor:
                puntos[e['id']] = max(puntos.get(e['id'], 0), mejor * peso)
    ids = sorted(puntos, key=lambda i: (
        -puntos[i], _RANGO_GRUPO.get(por_id(i)['grupo'], 1), orden[i]))
    return ids[:limite]


def _linea_de(cue, rol, t):
    """Que linea del bloque lleva el emoji (v3.3.1): la del ROL de la
    palabra (contexto/principal/complemento; base -> la linea base), y si
    no hay, la ultima que ya empezo cuando se dice la palabra."""
    lineas = cue.get('lines') or []
    if not lineas:
        return 0
    buscado = rol if rol in ('context', 'main', 'complement') else 'base'
    for k, l in enumerate(lineas):
        if l.get('role') == buscado:
            return k
    k_ult = 0
    for k, l in enumerate(lineas):
        try:
            if float(l.get('start', cue.get('start')) or 0) <= t:
                k_ult = k
        except (TypeError, ValueError):
            continue
    return k_ult


def asignar(bloques, palabras, roles=None):
    """Copia a cada bloque el emoji de sus palabras (w['emoji']).

    Una palabra cae en el bloque que ya empezo cuando ella se dice (el
    ultimo con start <= el de la palabra). Si un bloque junta varias con
    emoji, gana la primera. Devuelve cuantos bloques llevan emoji. Un id
    que el catalogo no conoce se ignora (un .marcas.json de otra version).
    v3.3.1: ademas cue['emoji_linea'] = la linea a la que pertenece la
    palabra (por su rol, 'roles' paralelo a 'palabras'; sin roles, por
    tiempo): el gemelo pone el emoji al FINAL de esa linea.
    """
    for b in bloques:
        b.pop('emoji', None)
        b.pop('emoji_linea', None)
    con = 0
    ordenados = sorted(bloques, key=lambda b: float(b.get('start') or 0))
    for i, w in enumerate(palabras or ()):
        eid = w.get('emoji') if isinstance(w, dict) else None
        if not eid or por_id(eid) is None:
            continue
        t = float(w.get('start') or 0) + 0.001
        destino = None
        for b in ordenados:
            if float(b.get('start') or 0) <= t:
                destino = b
            else:
                break
        if destino is None or destino.get('emoji'):
            continue
        destino['emoji'] = eid
        rol = roles[i] if roles is not None and i < len(roles) else None
        destino['emoji_linea'] = _linea_de(destino, rol, t)
        try:
            destino['emoji_fin'] = float(w.get('end') or w.get('start') or 0)
            destino['emoji_ini'] = float(w.get('start') or 0)
        except (TypeError, ValueError):
            pass
        con += 1
    return con


def _medidor_cache():
    import medir_texto
    cache = {}

    def medidor_de(est):
        clave = (str(est.get('font') or ''), str(est.get('style') or ''),
                 float(est.get('size') or 0), float(est.get('tracking') or 1.0))
        if clave not in cache:
            try:
                cache[clave] = medir_texto.medidor(
                    clave[0], clave[1] or 'Regular', clave[2], tracking=clave[3])
            except Exception:
                cache[clave] = None
        return cache[clave]

    return medidor_de


def medir_anchos_lineas(bloques, estilos_por_formato):
    """Mide TODAS las lineas de todos los bloques con la tipografia del
    pack (v3.4.0, la «Composición»: los gemelos alinean contexto y
    complemento a los bordes de la principal, y para eso necesitan el
    ancho de cada linea por formato y por set) y lo deja en la linea:
        l["medidas"] = {formato: {"rol|n": ancho_em}}
    — la clave es la MISMA que el gemelo arma al colocar ("context|3",
    "base|0"): una linea base lleva "base|0" si el pack lo trae y si no
    las "main|n" de cada set (lo que hace el gemelo). Unidad: fraccion de
    la ALTURA del fotograma al Size de esa linea (medir_texto). Lo que no
    se puede medir se omite (el gemelo deja esa linea donde la plantilla
    la puso y lo cuenta). Devuelve (lineas medidas, [fuentes sin medir]).
    """
    medidor_de = _medidor_cache()
    medidas_n, sin_medir = 0, []
    for b in bloques:
        for linea in (b.get('lines') or []):
            texto = str(linea.get('text') or '').strip()
            if not texto:
                continue
            rol = linea.get('role') or 'base'
            medidas = {}
            for formato, estilos in (estilos_por_formato or {}).items():
                por_clave = {}
                candidatos = [(c, e) for c, e in (estilos or {}).items()
                              if c.partition('|')[0] == rol]
                if rol == 'base' and not candidatos:
                    candidatos = [(c, e) for c, e in (estilos or {}).items()
                                  if c.partition('|')[0] == 'main']
                for clave, est in candidatos:
                    if not est or not est.get('size'):
                        continue
                    medir = medidor_de(est)
                    if medir is None:
                        sin_medir.append(
                            f"{est.get('font')} {est.get('style') or ''}".strip())
                        continue
                    anchos = medir([texto])
                    if not anchos:
                        continue
                    por_clave[str(clave)] = round(float(anchos[0]), 4)
                if por_clave:
                    medidas[formato] = por_clave
            if medidas:
                linea['medidas'] = medidas
                medidas_n += 1
    return medidas_n, sorted(set(sin_medir))


def medir_anchos_emoji(bloques, estilos_por_formato):
    """Mide, para cada bloque con emoji, el ancho de SU linea con la
    tipografia del pack (v3.3.1) y lo deja en la linea:
        l["emoji_medidas"] = {formato: {"n": [ancho_em, alto_em]}}
    — por FORMATO y por SET, porque los dos los decide Resolve; en
    fraccion de la ALTURA del fotograma (la unidad de Fusion 'Size', la
    misma del pintado: medir_texto), con el texto EXACTO de la linea (la
    mayuscula ya aplicada). Una linea base usa el estilo 'base|0' si el
    pack lo trae y si no el de la principal de cada set (lo que hace el
    gemelo). Solo se escribe lo medible: sin medida, el gemelo pone el
    emoji encima del bloque, como en la v3.3.0. Devuelve (bloques medidos,
    [fuentes que no se pudieron medir]).
    """
    import medir_texto
    medidos, sin_medir, cache = 0, [], {}

    def medidor_de(est):
        clave = (str(est.get('font') or ''), str(est.get('style') or ''),
                 float(est.get('size') or 0), float(est.get('tracking') or 1.0))
        if clave not in cache:
            try:
                cache[clave] = medir_texto.medidor(
                    clave[0], clave[1] or 'Regular', clave[2], tracking=clave[3])
            except Exception:
                cache[clave] = None
        return cache[clave]

    for b in bloques:
        if not b.get('emoji'):
            continue
        lineas = b.get('lines') or []
        try:
            k = int(b.get('emoji_linea') or 0)
        except (TypeError, ValueError):
            k = 0
        if not 0 <= k < len(lineas):
            continue
        linea = lineas[k]
        texto = str(linea.get('text') or '').strip()
        if not texto:
            continue
        rol = linea.get('role') or 'base'
        medidas = {}
        for formato, estilos in (estilos_por_formato or {}).items():
            por_set = {}
            candidatos = [(c, e) for c, e in (estilos or {}).items()
                          if c.partition('|')[0] == rol]
            if rol == 'base' and not candidatos:
                candidatos = [(c, e) for c, e in (estilos or {}).items()
                              if c.partition('|')[0] == 'main']
            for clave, est in candidatos:
                n = clave.partition('|')[2]
                if not est or not est.get('size'):
                    continue
                medir = medidor_de(est)
                if medir is None:
                    sin_medir.append(
                        f"{est.get('font')} {est.get('style') or ''}".strip())
                    continue
                anchos = medir([texto])
                if not anchos:
                    continue
                por_set[str(n)] = [round(float(anchos[0]), 4),
                                   round(float(est['size']), 4)]
            if por_set:
                medidas[formato] = por_set
        if medidas:
            linea['emoji_medidas'] = medidas
            medidos += 1
    return medidos, sorted(set(sin_medir))


CARPETA_COMPS = sfx_rules.CARPETA_USUARIO / 'emoji_comps'


def texto_comp_animacion(largo, entrada, salida):
    """Texto de la comp de Fusion que le da al emoji su ENTRADA (rebote de 8 fotogramas) y/o su SALIDA (6 fotogramas). Gemela de comp_animacion_emoji
    de CineCaptions_Subtitulos.lua y de _comp_animacion_emoji de CineCaptions.py."""
    t = "(math.min(1,math.max(0,time/8))-1)"
    pop = "(1+2.70158*%s^3+1.70158*%s^2)" % (t, t) if entrada else "1"
    fuera = "math.max(0,math.min(1,(%d-time)/6))" % largo if salida else "1"
    expr = "math.max(0.001,%s*%s)" % (pop, fuera)
    return ("Composition {\n\tCurrentTime = 0,\n\tRenderRange = { 0, %d },\n\tGlobalRange = { 0, %d },\n\tTools = ordered() {\n"
            "\t\tTransform1 = Transform {\n\t\t\tInputs = {\n\t\t\t\tSize = Input { Value = 1, Expression = \"%s\", },\n"
            "\t\t\t\tInput = Input { SourceOp = \"MediaIn1\", Source = \"Output\", },\n\t\t\t},\n"
            "\t\t\tViewInfo = OperatorInfo { Pos = { 200, 50 } },\n\t\t},\n"
            "\t\tMediaIn1 = MediaIn {\n\t\t\tViewInfo = OperatorInfo { Pos = { 0, 50 } },\n\t\t},\n"
            "\t\tMediaOut1 = MediaOut {\n\t\t\tInputs = {\n\t\t\t\tIndex = Input { Value = \"0\", },\n"
            "\t\t\t\tInput = Input { SourceOp = \"Transform1\", Source = \"Output\", },\n\t\t\t},\n"
            "\t\t\tViewInfo = OperatorInfo { Pos = { 400, 50 } },\n\t\t},\n\t},\n}\n") % (largo, largo, expr)


def comps_animacion(bloques, secuencias=None, fps=None, extra_fin=0.05):
    """v5.4.36 — Resolve Free no tiene `io`: el script no puede escribir la comp de Fusion que anima cada emoji (rebote al entrar y encogerse al salir),
    así que la deja escrita la app. Una comp por (largo en fotogramas, entrada, salida) en ~/DaVinciSubtitles/emoji_comps/ (se reusan entre corridas);
    el script usa la de largo más cercano (±3 fotogramas) de la lista `ids`. Sin fps conocido se cubren los de uso común. Devuelve {'carpeta', 'ids'} o {}."""
    try:
        fps_pos = [float(fps)] if fps and float(fps) > 1 else [23.976, 24.0, 25.0, 29.97, 30.0, 50.0, 59.94, 60.0]
        pedidas = set()                                                  # (largo, entrada, salida)
        for b in bloques or []:
            eid = b.get('emoji')
            if not eid:
                continue
            try:
                ini = float(b['emoji_ini'] if b.get('emoji_ini') is not None else b.get('start') or 0.0)
                dur = float(b['end']) + float(extra_fin) - ini
            except (KeyError, TypeError, ValueError):
                continue
            if dur <= 0:
                continue
            try:
                n = int(((secuencias or {}).get(eid) or {}).get('n') or 0)
            except (TypeError, ValueError):
                n = 0
            for f in fps_pos:
                for k in (-1, 0, 1):
                    largo = max(2, int(round(dur * f)) + k)
                    if n >= 2 and largo > n:                             # secuencia animada en bucle: entra el 1.º tramo y sale el último
                        pedidas.add((n, 1, 0))
                        pedidas.add((max(2, largo - n * ((largo - 1) // n)), 0, 1))
                    else:
                        pedidas.add((largo, 1, 1))
        if not pedidas:
            return {}
        CARPETA_COMPS.mkdir(parents=True, exist_ok=True)
        ids = []
        for largo, e, s in sorted(pedidas):
            ruta = CARPETA_COMPS / ('cinecaptions_emoji_%d_%d%d.comp' % (largo, e, s))
            if not ruta.is_file():
                tmp = ruta.with_suffix('.tmp')
                tmp.write_text(texto_comp_animacion(largo, bool(e), bool(s)), encoding='utf-8')
                os.replace(tmp, ruta)
            ids.append('%d_%d%d' % (largo, e, s))
        return {'carpeta': str(CARPETA_COMPS), 'ids': ids}
    except Exception:
        return {}


def para_manifiesto(bloques, posicion=None, forzar=False, fps=None):
    """Las claves del track: {'emojis': {id: ruta}}, o {} si ningun bloque
    lleva emoji. Las rutas son las copias PERSISTENTES
    (~/DaVinciSubtitles/emojis_usados/...). 'posicion' (v3.3.0) ya no
    viaja: el emoji va al final de su linea (v3.3.1) y sin medida los
    gemelos lo ponen encima del bloque."""
    rutas = {}
    for eid in sorted({b.get('emoji') for b in bloques if b.get('emoji')}):
        ruta = copia_para_resolve(eid)
        if not ruta:
            continue
        rutas[eid] = ruta
    if not rutas:
        return {}
    # v5.3: el emoji va en el bloque 'imagen' del pack y, si no lo trae, DEBAJO de las lineas
    # ('abajo'). 'arriba' y 'linea' (al final de su linea, v3.3.1) quedan por si se piden.
    if posicion not in ('abajo', 'arriba', 'linea'):
        posicion = 'abajo'
    pista = {'emojis': rutas, 'emoji_posicion': posicion}
    # v5.5: los que tienen version animada viajan ademas como secuencia de PNG (el script los importa como clip que se mueve)
    try:
        import emojis_animados
        secuencias = {}
        for eid in (rutas if animados_activo() else ()):
            e = por_id(eid) or {}
            if e.get('glifo') and not e.get('usuario'):
                datos = emojis_animados.secuencia_resolve(e['glifo'])
                if datos:
                    secuencias[eid] = datos
        if secuencias:
            pista['emojis_secuencias'] = secuencias
    except Exception:
        pass
    if forzar:
        pista['emoji_forzar'] = True          # la eleccion del usuario manda sobre el bloque «imagen» del pack
    comps = comps_animacion(bloques, pista.get('emojis_secuencias'), fps)
    if comps:
        pista['emoji_comps'] = comps          # Free (sin io): las comps de entrada/salida las deja escritas la app
    return pista


if __name__ == '__main__':
    assert catalogo(), 'falta emojis/indice.json (corre la herramienta)'
    assert 'fire' in sugerir('¡Fuego!', 'es'), sugerir('¡Fuego!', 'es')
    assert 'fire' in sugerir('fogo', 'pt')
    assert 'money_bag' in sugerir('dinero', 'es'), sugerir('dinero', 'es')
    assert sugerir('de', 'es') == []
    b = [{'start': 0.0, 'end': 1.0}, {'start': 1.0, 'end': 2.0}]
    assert asignar(b, [{'word': 'x', 'start': 1.2, 'emoji': 'fire'}]) == 1
    assert b[1]['emoji'] == 'fire' and 'emoji' not in b[0]
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        _viejo = CARPETA_USUARIO_EMOJIS
        globals()['CARPETA_USUARIO_EMOJIS'] = Path(tmp) / 'emojis'
        _invalidar()
        try:
            png = Path(tmp) / 'Logo.png'
            png.write_bytes((carpeta() / 'png' / por_id('fire')['archivo']).read_bytes())
            eid = guardar_en_biblioteca(png)
            assert eid == 'mio_logo' and por_id(eid)['usuario'], eid
            assert guardar_en_biblioteca(png) == eid
            fuego = Path(tmp) / 'fire.png'
            fuego.write_bytes(png.read_bytes())
            assert guardar_en_biblioteca(fuego) == 'mio_fire_mio'
            assert origen_de('fire')[0] != 'usuario'
            reemplazar_con_png('fire', png)
            assert origen_de('fire') == ('usuario', carpeta_usuario() / 'fire.png')
            assert quitar_de_biblioteca('fire') is not None
            assert origen_de('fire')[0] != 'usuario'
            assert quitar_de_biblioteca(eid) is not None and por_id(eid) is None
        finally:
            globals()['CARPETA_USUARIO_EMOJIS'] = _viejo
            _invalidar()
    print('emojis.py: OK', len(catalogo()), 'emojis')


# ---------------------------------------------------------------------------------------------------------------------
# v5.5: las secuencias animadas de los emojis MAS USADOS se dejan listas en segundo plano (al abrir el programa y al empezar a
# transcribir), asi la primera generacion con emojis no espera la red.
_POPULARES = ('fire', 'rocket', 'money_bag', 'star', 'sparkles', 'red_heart', 'check_mark_button', 'warning', 'light_bulb', 'trophy',
              'gem_stone', 'crown', 'thumbs_up', 'clapping_hands', 'face_with_tears_of_joy', 'smiling_face_with_heart_eyes',
              'thinking_face', 'exploding_head', 'eyes', 'hundred_points', 'party_popper', 'money_with_wings', 'chart_increasing',
              'bullseye', 'megaphone', 'alarm_clock', 'brain', 'flexed_biceps', 'folded_hands', 'waving_hand', 'skull', 'bomb',
              'collision', 'dashing_away', 'high_voltage', 'sun', 'globe_showing_americas', 'house', 'automobile', 'airplane',
              'camera', 'movie_camera', 'microphone', 'headphone', 'musical_note', 'books', 'laptop', 'mobile_phone', 'key',
              'locked', 'gift', 'birthday_cake', 'pizza', 'hamburger', 'hot_beverage', 'soccer_ball', 'dollar_banknote',
              'credit_card', 'shopping_cart', 'package', 'bell', 'red_question_mark', 'red_exclamation_mark', 'backhand_index_pointing_down',
              'victory_hand', 'ok_hand', 'raising_hands', 'face_screaming_in_fear', 'face_with_monocle', 'partying_face', 'smiling_face_with_sunglasses',
              'rolling_on_the_floor_laughing', 'loudly_crying_face', 'pleading_face', 'winking_face', 'handshake', 'balance_scale',
              'magnifying_glass_tilted_left', 'link', 'gear', 'hammer_and_wrench', 'stopwatch', 'calendar', 'memo', 'newspaper',
              'bar_chart', 'chart_decreasing', 'police_car_light', 'no_entry', 'prohibited', 'cross_mark', 'sparkling_heart', 'rainbow',
              'four_leaf_clover', 'tada', 'glowing_star', 'direct_hit')
_PRECALENTANDO = {'activo': False}


def populares(n=100):
    """Los glifos de los emojis mas usados que existen en el catalogo."""
    glifos = []
    por_id_ = {e['id']: e for e in catalogo()}
    for eid in _POPULARES:
        e = por_id_.get(eid)
        if e and e.get('glifo') and e['glifo'] not in glifos:
            glifos.append(e['glifo'])
    return glifos[:n]


def precalentar_secuencias(n=100):
    """Baja y prepara en un hilo (de baja prioridad) las secuencias de los emojis populares. Idempotente; sin red no insiste."""
    if _PRECALENTANDO['activo']:
        return False
    _PRECALENTANDO['activo'] = True

    def trabajo():
        import time
        import emojis_animados
        fallos = 0
        try:
            for g in populares(n):
                datos = emojis_animados.secuencia_resolve(g)
                if datos is None and not emojis_animados._marca_sin_version(g).is_file():
                    fallos += 1
                    if fallos >= 3:
                        break              # sin red: se reintenta en el proximo arranque
                else:
                    fallos = 0
                time.sleep(0.05)
        finally:
            _PRECALENTANDO['activo'] = False
    import threading
    threading.Thread(target=trabajo, daemon=True, name='emojis-secuencias').start()
    return True
