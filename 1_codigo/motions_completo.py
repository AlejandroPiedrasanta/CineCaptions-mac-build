# CineCaptions · By Cinema Productions
# 1_codigo/motions_completo.py — v5.5.8 «Motions completo»: un video de motions a pantalla completa para TODO el video, frase a frase, que va en
# PRO-MOTIONS encima de todo (captions, efectos, Edición PRO). El usuario lo corta para que se vea su video debajo.
"""
motions_completo.py
-------------------
Pedido (2026-10-15, con referencias de videos explicativos y carteles de redes): «la opción de solo motions para todo el video completo, por encima
de todo (captions y efectos), un video de solo motions relacionado al tema, para que yo lo corte y el video de abajo lo acompañe; otro proceso al
final de todo; a la par de Edición PRO un botón que diga Motions completo».

    planificar(bloques, dur, idioma, perfil, video, vertical, ia, estado) -> props de la composición MotionsCompleto (Remotion)
    crear(bloques, dur, W, H, fps, carpeta, idioma, perfil, video, decir) -> ruta del .mp4 o None

Cada escena cubre una o varias frases seguidas (2,2–5,5 s; juntas tapan el video entero, sin huecos) y es, por orden de preferencia:
  · un OBJETO de lo que se dice (precio con su moneda, cifra, gráfica, reloj, lista, comparación, pregunta, avatares…), de las reglas del director
    de escenas del Tema 5 (edicion_pro_tema5_escenas) y de la IA local (ia_texto.escenas, validada con desde_ia);
  · si no, una FOTO de internet del tema (edicion_pro_escenas.foto_del_tema: lo que se nombra o el tema del video según la IA), un ICONO 3D del
    concepto (CONCEPTOS3D / los emojis de los acompañantes) o TIPOGRAFÍA cinética de la frase (la palabra clave enorme), sin repetir tipo seguido.
El fondo alterna claro / oscuro / acento del video; la frase va pequeña abajo, como en las referencias.
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MIN_S, MAX_S = 2.2, 5.5                     # duración de cada escena (se juntan frases hasta MIN_S, sin pasar de MAX_S)
OBJETOS = {'precio', 'grafica', 'reloj', 'avatares', 'calendario', 'estado', 'cifra', 'lista', 'comparacion', 'pregunta', 'ficha', 'app', 'ojo', 'barra',
           'muestra'}
VACIAS = set('''a al o u e y the and or of in on at to is it its as be by if so we my me i you your our de del la las el los lo un una unos unas en con
por para que se es son su sus mi mis tu tus muy mas más pero como este esta esto eso esa ese ya no si sí le les nos hay fue ser estar tiene tienen
para this that these those there here what when then than just very really also have has had was were are will would can could do does did not
your about from with they them their um eh ah oh ok okay'''.split())


def _plegar(t):
    t = unicodedata.normalize('NFKD', str(t or '').lower())
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in t if not unicodedata.combining(c)))


def _limpio(t):
    return re.sub(r'^[^\w¿¡$€£¥₦₹]+|[^\w%]+$', '', str(t or ''))


def _segmentos(bloques, dur):
    """Las escenas: frases seguidas juntas hasta MIN_S (sin pasar de MAX_S), contiguas de 0 al final."""
    segs, cur = [], None
    for b in bloques:
        if cur and cur['fin'] - cur['ini'] < MIN_S and b['ini'] - cur['fin'] < 1.0 and b['fin'] - cur['ini'] <= MAX_S:
            cur['fin'] = b['fin']
            cur['bl'].append(b)
        else:
            if cur:
                segs.append(cur)
            cur = {'ini': b['ini'], 'fin': b['fin'], 'bl': [b]}
    if cur:
        segs.append(cur)
    if not segs:
        return []
    segs[0]['ini'] = 0.0
    for a, z in zip(segs, segs[1:]):
        a['fin'] = z['ini']
    segs[-1]['fin'] = max(segs[-1]['fin'], float(dur or segs[-1]['fin']))
    return segs


def _palabras(seg):
    out = []
    for b in seg['bl']:
        for w in b['palabras']:
            texto = _limpio(w['texto'])
            if texto:
                out.append({'t': round(max(0.0, b['ini'] + float(w['t']) - seg['ini']), 3), 'texto': texto})
    if out:                                                                # la escena nunca empieza vacía: todo un poco antes, la primera ya al entrar
        d = min(out[0]['t'], 0.6)
        for p in out:
            p['t'] = round(max(0.0, p['t'] - d - 0.15), 3)
    return out


def _clave(palabras):
    """La palabra que se destaca: una cifra, una de énfasis o la más larga con contenido (nunca una vacía)."""
    try:
        import edicion_pro_tema5 as T5
        enfasis = {_plegar(x) for x in T5.ENFASIS}
    except Exception:
        enfasis = set()
    mejor, nota = None, -1.0
    for i, p in enumerate(palabras):
        w = _plegar(p['texto'])
        if not w or w in VACIAS:
            continue
        n = len(w) + (8 if w in enfasis else 0) + (6 if any(c.isdigit() for c in w) else 0) + 0.01 * i
        if n > nota:
            mejor, nota = i, n
    return mejor


def _titular(ps, k):
    """El titular de una foto: la palabra clave y, si sigue una frase de verdad («emprendimientos DE comida»: la siguiente con contenido a 1–2
    palabras), esa frase tal cual se dijo; si no, solo la clave (nunca «HISTORIAS ACCEDER» ni «TAMBIÉN HISTORIAS DE»)."""
    if k is None:
        return ''
    limpio = lambda t: str(t).strip(' .,;:!?¡¿…"«»()')
    clave = limpio(ps[k]['texto'])
    for j in range(k + 1, min(k + 3, len(ps))):
        if _plegar(ps[j]['texto']) not in VACIAS:
            frase = ' '.join(limpio(p['texto']) for p in ps[k:j + 1])
            return (frase if len(frase) <= 28 else clave).upper()[:28]
    return clave.upper()[:28]


def _icono(palabras):
    """(icono 3D, emoji) del primer concepto con dibujo de lo que se dice."""
    try:
        import edicion_pro_planificador as PL
        c3d = PL.CONCEPTOS3D
    except Exception:
        c3d = {}
    try:
        import edicion_pro_tema5_acomp as AC
        emo = AC.CONCEPTOS_ACOMP
    except Exception:
        emo = {}
    for p in palabras:
        w = _plegar(p['texto'])
        if w in c3d:
            return c3d[w], None, p['texto']
    for p in palabras:
        w = _plegar(p['texto'])
        if w in emo:
            return None, emo[w], p['texto']
    return None, None, ''


def _candidatas(bloques, dur, idioma, ia, estado):
    """Las escenas con objeto del director del Tema 5 (reglas + IA local validada)."""
    out = []
    try:
        import edicion_pro_tema5_escenas as DIR
        out += DIR.escenas(bloques, dur) or []
        if ia:
            import ia_texto
            prop = ia_texto.escenas(bloques, idioma, estado=estado) or []
            if prop:
                out += DIR.desde_ia(bloques, prop, dur) or []
    except Exception:
        pass
    return [c for c in out if c.get('objetos') and c['objetos'][0].get('tipo') in OBJETOS]


def planificar(bloques, dur, idioma='es', perfil=None, video='', vertical=True, ia=True, estado=None):
    segs = _segmentos(bloques, dur)
    if not segs:
        return None
    try:
        import edicion_pro_tema5 as T5
        acento = T5.acento_de_video(video) if video else T5.ACENTOS['azul']
    except Exception:
        acento = '#4C7DFF'
    cands = _candidatas(bloques, dur, idioma, ia, estado)
    escenas = []
    for s in segs:
        ps = _palabras(s)
        k = _clave(ps)
        for i, p in enumerate(ps):
            p['clave'] = i == k
        e = {'ini': round(s['ini'], 3), 'fin': round(s['fin'], 3), 'palabras': ps, 'tipo': 'tipografia'}
        medio = [c for c in cands if s['ini'] - 0.3 <= c['ini'] + 0.4 <= s['fin']]
        if medio:
            c = max(medio, key=lambda c: c.get('prioridad', 0))
            o = dict(c['objetos'][0])
            o['t'] = round(max(0.15, c['ini'] + float(o.get('t', 0.2)) - s['ini']), 3)
            e.update(tipo='objeto', objeto=o)
        escenas.append(e)
    # lo que no tiene objeto: foto de internet del tema, icono 3D o tipografía, sin repetir tipo seguido
    try:
        import edicion_pro_escenas as ES
        formato = 'v' if vertical else 'h'
    except Exception:
        ES = None
    libres = [i for i, e in enumerate(escenas) if e['tipo'] == 'tipografia']
    quiero_foto = set(libres[1::3]) if ES else set()                         # una de cada tres: las fotos no se comen el video
    fotos = {}
    if quiero_foto and ES is not None:
        usadas = []

        def buscar(i):
            textos = [p['texto'] for p in escenas[i]['palabras']]
            try:
                return i, ES.foto_del_tema(textos, perfil or {}, formato, evitar=list(usadas), lado=1080)
            except Exception:
                return i, None
        with ThreadPoolExecutor(4) as ex:
            for i, r in ex.map(buscar, sorted(quiero_foto)):
                if r and r[1]['id'] not in usadas:
                    fotos[i] = r
                    usadas.append(r[1]['id'])
        try:
            import fuentes_web as FW
            FW.anotar_creditos([r[1] for r in fotos.values()], video)
        except Exception:
            pass
    previo = None
    for i, e in enumerate(escenas):
        if e['tipo'] == 'tipografia' and i > 0:
            ps = e['palabras']
            k = next((j for j, p in enumerate(ps) if p.get('clave')), None)
            titulo = ps[k]['texto'] if k is not None else ''
            ic3d, emoji, palabra = _icono(ps)
            if i in fotos and previo != 'foto':
                e.update(tipo='foto', foto=fotos[i][0], titulo=_titular(ps, k))
            elif (ic3d or emoji) and previo != 'icono':
                e.update(tipo='icono', icono=ic3d, emoji=emoji, titulo=(palabra or titulo).capitalize())
        previo = e['tipo']
    # el fondo: claro / oscuro / acento alternados (las fotos van sin fondo)
    ciclo, n = ['claro', 'oscuro', 'claro', 'acento', 'oscuro'], 0
    for e in escenas:
        if e['tipo'] != 'foto':
            e['fondo'] = ciclo[n % len(ciclo)]
            n += 1
    frases = [{'ini': round(b['ini'], 3), 'fin': round(b['fin'], 3), 'texto': ' '.join(_limpio(w['texto']) for w in b['palabras'] if _limpio(w['texto']))}
              for b in bloques]
    return {'escenas': escenas, 'frases': frases, 'acento': acento, 'subtitulos': True}


def crear(bloques, dur, W, H, fps, carpeta, idioma='es', perfil=None, video='', decir=None, ia=True):
    """Planifica y renderiza el video de motions (H.264 opaco, del largo del video). Devuelve su ruta o None. Con caché por contenido."""
    decir = decir or (lambda t: None)
    try:
        import edicion_pro_remotion as RM
    except Exception:
        return None
    if not RM.disponible():
        decir('Motions completo: falta el motor de animaciones (Remotion)')
        return None
    decir('Motions completo: eligiendo una escena para cada frase…')
    if not perfil and ia:                                                  # de qué va el video (las fotos del tema salen de aquí); con caché
        try:
            import ia_texto
            perfil = ia_texto.perfil([w['texto'] for b in bloques for w in b['palabras']], idioma, estado=decir) or {}
        except Exception:
            perfil = {}
    props = planificar(bloques, dur, idioma, perfil, video, H > W, ia, decir)
    if not props or not props['escenas']:
        return None
    props.update(_ancho=int(W), _alto=int(H), _fps=float(fps), _dur=round(float(dur), 3))
    huella = hashlib.sha1(json.dumps(props, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:14]
    salida = Path(carpeta) / f'motions_completo_{huella}.mp4'
    if salida.exists() and salida.stat().st_size > 50_000:
        return salida
    tipos = {}
    for e in props['escenas']:
        tipos[e['tipo']] = tipos.get(e['tipo'], 0) + 1
    decir(f"Motions completo: {len(props['escenas'])} escenas ({', '.join(f'{n} {t}' for t, n in tipos.items())}); animando…")
    ok = _renderizar(RM, props, salida, dur, decir)
    try:
        import registro
        if ok:
            registro.info(f"Motions completo: {len(props['escenas'])} escenas en {salida.name} ({salida.stat().st_size / 1e6:.0f} MB).", 'motions')
        else:
            registro.aviso('Motions completo: Remotion no pudo hacer el video de motions; el resto de la edición queda igual.', 'motions')
    except Exception:
        pass
    return salida if ok else None


def _renderizar(RM, props, salida, dur, decir):
    """Una llamada a render.mjs (modo opaco) leyendo su avance línea a línea."""
    salida.parent.mkdir(parents=True, exist_ok=True)
    RM._permisos()
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'bundle': str(RM.bundle()), 'navegador': RM._chrome(),
                   'trabajos': [{'id': 'MotionsCompleto', 'props': props, 'salida': str(salida), 'opaco': True}]}, f, ensure_ascii=False)
        ruta = f.name
    hecho = False
    try:
        mjs = RM._render_mjs()
        p = subprocess.Popen([RM._node(), str(mjs), ruta], cwd=str(mjs.parent), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                             encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        tope = time.time() + max(900.0, float(dur) * 25.0)
        for linea in p.stdout:
            try:
                r = json.loads(linea)
            except ValueError:
                continue
            if 'progreso' in r:
                decir(f"Motions completo: animando… {int(float(r['progreso']) * 100)} %")
            elif r.get('hecho'):
                hecho = True
            if time.time() > tope:
                p.kill()
                break
        p.wait(timeout=60)
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass
    return hecho and salida.exists() and salida.stat().st_size > 50_000
