# CineCaptions · By Cinema Productions
# 1_codigo/premiere.py — GO en Adobe Premiere Pro (v5.78): el panel CineCaptions de Premiere coloca el video, los captions y los sonidos.
"""
premiere.py
-----------
Pedido (2026-11-09): «en Ajustes > General la opción para activar Premiere Pro; cuando se active debe funcionar tal cual como DaVinci
Resolve, que coloca todo en el timeline».

Premiere no tiene una API que se pueda llamar desde fuera (Resolve sí: MCP / fusionscript). Lo que sí tiene es ExtendScript dentro de un
panel CEP. Así que:

  0. Ajustes › General: «Usar con Premiere Pro» (pref `go_premiere`), excluyente con «Usar con DaVinci Resolve» (de fábrica) y «Video sin
     editores (DaVinci y Premiere)» (`go_salida_mp4`).
  1. `instalar_panel()` copia `2_recursos/premiere/com.cinecaptions.premiere` (un panel CEP: index.html + fondo.html + jsx/colocar.jsx)
     en la carpeta de extensiones del usuario y enciende `PlayerDebugMode` en CSXS.9-13 (el panel no va firmado; sin eso Premiere no lo
     carga). Premiere lo carga al ARRANCAR: si ya estaba abierto, hay que reiniciarlo una vez.
  2. GO dibuja los captions del estilo sobre transparente (`render_sin_resolve.renderizar_capa`, ProRes 4444 con alfa) y `colocar()` deja
     un pedido (`pedido.json`) en `<datos de usuario>/CineCaptions/premiere` (Windows %APPDATA%, Mac ~/Library/Application Support: lo
     mismo que `Folder.userData` en ExtendScript).
  3. El panel mira la carpeta cada segundo (y escribe `latido.json` cada ~3 s): toma el pedido (lo renombra a `pedido.en_curso.json`, así
     nunca se coloca dos veces), importa el video, la capa y los sonidos en la carpeta «CineCaptions» del proyecto, crea la secuencia con
     el video (V1 + su audio en A1), pone la capa en V2, cada sonido en A2, A3… sin pisarse y la música (si el Sonido de GO eligió una) en
     la pista siguiente (`sonido_de_go`: lo mismo que recibiría Resolve), abre la secuencia con el cabezal al inicio y
     deja `resultado.json`. Sin proyecto abierto crea uno junto al video («<video> (CineCaptions).prproj»).

v5.85 (GO con Premiere cerrado esperaba 240 s y fallaba: Premiere 26 arranca en su pantalla de inicio y el panel solo carga con un proyecto
abierto): `colocar()` escribe ese proyecto ANTES de abrir Premiere (`crear_proyecto`: `2_recursos/premiere/proyecto_vacio.xml`, solo
ajustes, con su GUID nuevo, en gzip como cualquier .prproj) y lo abre con él (`abrir(exe, proyecto)`: «Adobe Premiere Pro.exe <proyecto>»,
lo mismo que un doble clic; Mac `open -a`). El panel lo reconoce (`proyectos_cc`) y lo guarda al terminar.

v5.85 (el usuario: «me pones el video de los captions y no quiero; quiero los textos que se vayan armando en la línea de tiempo»): si el
panel en marcha lo admite (`admite_textos`: latido «panel» ≥ 2) y está la plantilla «Basic Title» de Premiere (`plantilla_texto`), GO no
dibuja la capa: manda TEXTOS (premiere_textos: un .mogrt por texto con su letra, tamaño y colores) e imágenes (cajas, aros, emojis) y el
panel los pone en V2… como clips editables. Si Premiere no los acepta (causa 'textos'), la capa de siempre.

Lo que NO viaja (son de Fusion, solo existen en Resolve): las animaciones propias de los macros (rebotes, barridos, cristal), la Edición
PRO, las transiciones y efectos visuales. Los captions se ven con el dibujo de «GO sin Resolve» (render_temas), los mismos sitios y tiempos.
Todo lo que lanza procesos o espera va en un hilo (nunca en el de la interfaz).
"""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

PANEL = 'com.cinecaptions.premiere'
EXE_WIN = 'Adobe Premiere Pro.exe'
CSXS = range(9, 14)                       # CEP 9 (Premiere 2019) … CEP 12/13 (Premiere 2025-2026)
LATIDO_S = 10.0                           # el panel escribe cada ~3 s; más viejo que esto = Premiere cerrado o sin el panel
ESPERA_ABRIR_S = 240.0                    # Premiere tarda en arrancar (y el usuario puede tener que elegir un proyecto)
ESPERA_COLOCAR_S = 300.0                  # importar y colocar (muchos sonidos en un proyecto grande)
ESPERA_SIN_AVANCE_S = 150.0               # v5.85: con textos, mientras el panel avance se sigue esperando (VIRAL: > 5 min); parado tanto, se corta
PISTAS_SFX = 6
PROYECTO_VACIO = 'proyecto_vacio.xml'     # v5.85: el proyecto sin nada con el que GO abre Premiere (2_recursos/premiere; crear_proyecto)


def _datos_usuario():
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support'
    return Path(os.environ.get('APPDATA') or (Path.home() / 'AppData' / 'Roaming'))


def carpeta_cola():
    """Donde CineCaptions deja los pedidos y el panel de Premiere sus respuestas (CINECAPTIONS_PREMIERE_COLA la cambia en las pruebas)."""
    otra = os.environ.get('CINECAPTIONS_PREMIERE_COLA')
    return Path(otra) if otra else _datos_usuario() / 'CineCaptions' / 'premiere'


def carpeta_extensiones():
    """Las extensiones CEP del usuario (sin permisos de administrador). CINECAPTIONS_PREMIERE_EXT la cambia en las pruebas."""
    otra = os.environ.get('CINECAPTIONS_PREMIERE_EXT')
    return Path(otra) if otra else _datos_usuario() / 'Adobe' / 'CEP' / 'extensions'


def origen_panel():
    from sfx_rules import base_recursos
    return base_recursos() / 'premiere' / PANEL


# ------------------------------------------------------------------------------------------------------------------ dónde está Premiere
def _orden_version(p):
    """Más nuevo primero: «Adobe Premiere Pro 2026» > «… 2025» > «… (Beta)»."""
    nombre = p.name if p.suffix != '.exe' else p.parent.name
    digitos = ''.join(ch for ch in nombre if ch.isdigit())
    return (0 if 'beta' in nombre.lower() else 1, int(digitos or 0))


def ejecutable():
    """La ruta del Premiere Pro instalado más nuevo (Windows: el .exe; Mac: la .app) o None. Solo mira archivos (barato)."""
    if os.environ.get('CINECAPTIONS_PREMIERE_EXE'):              # (pruebas)
        p = Path(os.environ['CINECAPTIONS_PREMIERE_EXE'])
        return p if p.exists() else None
    candidatos = []
    if sys.platform == 'darwin':
        for d in Path('/Applications').glob('Adobe Premiere Pro*'):
            candidatos += [a for a in d.glob('Adobe Premiere Pro*.app') if a.is_dir()]
    else:
        bases = {os.environ.get('ProgramW6432'), os.environ.get('ProgramFiles'), r'C:\Program Files'}
        for b in filter(None, bases):
            for d in Path(b, 'Adobe').glob('Adobe Premiere Pro*'):
                exe = d / EXE_WIN
                if exe.is_file():
                    candidatos.append(exe)
        if not candidatos:
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths' + '\\' + EXE_WIN) as k:
                    v, _ = winreg.QueryValueEx(k, '')
                    if v and Path(v).is_file():
                        candidatos.append(Path(v))
            except OSError:
                pass
    if not candidatos:
        return None
    return sorted(candidatos, key=_orden_version, reverse=True)[0]


def plantilla_texto(exe=None):
    """v5.85: la plantilla de texto que trae el propio Premiere («Basic Title.mogrt», Gráficos esenciales; hecha en Premiere: su texto se
    puede cambiar entero —letra, tamaño, color, contorno, sombra— desde el panel) o None. No se reparte con CineCaptions: es la del usuario."""
    if os.environ.get('CINECAPTIONS_PREMIERE_MOGRT'):             # (pruebas)
        p = Path(os.environ['CINECAPTIONS_PREMIERE_MOGRT'])
        return p if p.is_file() else None
    exe = Path(exe) if exe else ejecutable()
    if exe is None:
        return None
    bases = [exe / 'Contents', exe.parent] if exe.suffix == '.app' else [exe.parent]
    for b in bases:
        for cand in (b / 'Essential Graphics' / 'Basic Title.mogrt', b / 'Resources' / 'Essential Graphics' / 'Basic Title.mogrt'):
            if cand.is_file():
                return cand
    for b in bases:                                                # (otra versión con otra carpeta: hasta 3 niveles, sin recorrer todo)
        for patron in ('*/Basic Title.mogrt', '*/*/Basic Title.mogrt', '*/*/*/Basic Title.mogrt'):
            for cand in b.glob(patron):
                return cand
    return None


_TEXTO_BASE = {}


def texto_base(plantilla):
    """v5.85: el JSON del «Texto de origen» guardado en la plantilla (.mogrt → project.prgraphic → proyecto gzip → valor en base64: 8 bytes de
    largo + JSON en UTF-16): premiere_textos.mogrt_de_texto escribe ahí el texto y el estilo de cada clip. None si no se puede leer."""
    if not plantilla:
        return None
    clave = str(plantilla)
    if clave not in _TEXTO_BASE:
        valor = None
        try:
            import base64
            import gzip
            import io
            import re
            import zipfile
            with zipfile.ZipFile(plantilla) as z:
                interior = zipfile.ZipFile(io.BytesIO(z.read('project.prgraphic')))
                xml = gzip.decompress(interior.read(interior.namelist()[0])).decode('utf-8', 'replace')
            m = re.search(r'<Name>Source Text</Name>.*?<StartKeyframeValue[^>]*>([^<]+)<', xml, re.S)
            if m:
                crudo = base64.b64decode(m.group(1).strip())
                texto = crudo[8:].decode('utf-16-le')
                json.loads(texto)
                valor = texto
        except Exception:
            valor = None
        _TEXTO_BASE[clave] = valor
    return _TEXTO_BASE[clave]


def abierto():
    """True si Premiere Pro está corriendo. Lanza un proceso en Mac: solo desde un hilo."""
    try:
        if sys.platform == 'darwin':
            r = subprocess.run(['pgrep', '-f', 'Adobe Premiere Pro'], capture_output=True, timeout=5)
            return r.returncode == 0
        import instalador_scripts as ins
        return bool(ins._proceso_corriendo_windows(EXE_WIN))
    except Exception:
        return False


def abrir(exe=None, proyecto=None):
    """Abre Premiere Pro (sin esperar); con `proyecto` (.prproj) lo abre directamente con él, como un doble clic, sin pasar por su pantalla de
    inicio (v5.85). False si no está instalado."""
    exe = exe or ejecutable()
    if exe is None:
        return False
    extra = [str(proyecto)] if proyecto else []
    try:
        if sys.platform == 'darwin':
            subprocess.Popen(['open', '-a', str(exe)] + extra)
        else:
            subprocess.Popen([str(exe)] + extra, cwd=str(Path(exe).parent),
                             creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
        return True
    except OSError:
        return False


def plantilla_proyecto():
    from sfx_rules import base_recursos
    return base_recursos() / 'premiere' / PROYECTO_VACIO


_CREADOS = []                             # los proyectos que este GO (u otro anterior de esta sesión) escribió y abrió: el panel los guarda


def crear_proyecto(ruta):
    """v5.85: escribe en `ruta` un proyecto de Premiere vacío (no pisa nada: si ya existe, «… 2.prproj»). Es XML en gzip, igual en Windows
    y Mac; sale de `proyecto_vacio.xml`, que solo lleva ajustes (los de fábrica de un proyecto nuevo de Premiere 26.5: nada de medios, rutas
    ni plantillas de Adobe), con su GUID y el de su carpeta raíz nuevos (dos proyectos nunca comparten identidad).
    → la ruta escrita (Path) o None si no se pudo (sin plantilla o carpeta sin permiso)."""
    import gzip
    import re
    tmp = None
    try:
        xml = plantilla_proyecto().read_text(encoding='utf-8')
        m = re.search(r'<RootProjectItem ObjectURef="([0-9a-fA-F-]{36})"', xml)
        if not m or '<MZ.Project.GUID>' not in xml:
            return None
        xml = xml.replace(m.group(1), str(uuid.uuid4()))
        xml = re.sub(r'<MZ\.Project\.GUID>[^<]*</MZ\.Project\.GUID>', lambda _m: f'<MZ.Project.GUID>{uuid.uuid4()}</MZ.Project.GUID>', xml, count=1)
        ruta = _ruta_libre(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = ruta.with_name(f'{ruta.name}.{uuid.uuid4().hex[:8]}.tmp')
        tmp.write_bytes(gzip.compress(xml.encode('utf-8'), mtime=0))
        os.replace(tmp, ruta)
        return ruta
    except OSError:
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass
        return None


# ------------------------------------------------------------------------------------------------------------------ el panel
def _iguales(a, b):
    """True si la carpeta instalada `b` tiene los mismos archivos (y bytes) que `a`."""
    for f in a.rglob('*'):
        if f.is_file():
            g = b / f.relative_to(a)
            try:
                if not g.is_file() or g.stat().st_size != f.stat().st_size or g.read_bytes() != f.read_bytes():
                    return False
            except OSError:
                return False
    return True


def _modo_depuracion():
    """PlayerDebugMode = 1 en CSXS.9-13: lo que deja a Premiere cargar un panel sin firmar. True si hubo que cambiar algo."""
    cambiado = False
    if sys.platform == 'darwin':
        for n in CSXS:
            dominio = f'com.adobe.CSXS.{n}'
            try:
                r = subprocess.run(['defaults', 'read', dominio, 'PlayerDebugMode'], capture_output=True, text=True, timeout=5)
                if r.returncode == 0 and r.stdout.strip() == '1':
                    continue
                subprocess.run(['defaults', 'write', dominio, 'PlayerDebugMode', '1'], capture_output=True, timeout=5)
                cambiado = True
            except Exception:
                pass
        return cambiado
    import winreg
    for n in CSXS:
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, rf'Software\Adobe\CSXS.{n}', 0,
                                    winreg.KEY_READ | winreg.KEY_WRITE) as k:
                try:
                    v, _ = winreg.QueryValueEx(k, 'PlayerDebugMode')
                    if str(v) == '1':
                        continue
                except OSError:
                    pass
                winreg.SetValueEx(k, 'PlayerDebugMode', 0, winreg.REG_SZ, '1')
                cambiado = True
        except OSError:
            pass
    return cambiado


def instalar_panel():
    """Copia el panel en las extensiones de Adobe si falta o cambió, y enciende PlayerDebugMode.
    → {'ok', 'instalado' (copiado ahora), 'ruta', 'texto'}. Desde un hilo."""
    origen = origen_panel()
    destino = carpeta_extensiones() / PANEL
    if not (origen / 'CSXS' / 'manifest.xml').is_file():
        return {'ok': False, 'instalado': False, 'ruta': str(destino), 'texto': f'falta el panel de Premiere en {origen}'}
    copiado = False
    try:
        if not destino.is_dir() or not _iguales(origen, destino):
            if destino.exists():
                shutil.rmtree(destino, ignore_errors=True)
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(origen, destino, dirs_exist_ok=True)
            copiado = True
    except OSError as e:
        return {'ok': False, 'instalado': False, 'ruta': str(destino), 'texto': f'no pude copiar el panel en {destino.parent}: {e}'}
    depuracion = False
    try:
        depuracion = _modo_depuracion()
    except Exception:
        pass
    return {'ok': True, 'instalado': copiado or depuracion, 'ruta': str(destino), 'texto': ''}


def preparar():
    """Lo que hace Ajustes al encender «Adobe Premiere Pro»: instala el panel. → {'ok', 'premiere' (ruta o None), 'reiniciar', 'texto'}."""
    r = instalar_panel()
    exe = ejecutable()
    reiniciar = bool(r.get('instalado')) and abierto()
    return {'ok': r['ok'], 'premiere': str(exe) if exe else None, 'reiniciar': reiniciar, 'texto': r.get('texto', '')}


# ------------------------------------------------------------------------------------------------------------------ pedido y respuesta
def latido():
    """Lo último que dijo el panel ({'t' ms, 'version', 'proyecto'}) o None."""
    try:
        d = json.loads((carpeta_cola() / 'latido.json').read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def panel_vivo(max_s=LATIDO_S):
    d = latido()
    try:
        return bool(d) and (time.time() - float(d.get('t') or 0) / 1000.0) < max_s
    except (TypeError, ValueError):
        return False


PANEL_TEXTOS = 2                          # v5.85: desde esta versión del panel (latido «panel»), los textos editables


def admite_textos():
    """v5.85: ¿este GO puede mandar TEXTOS (premiere_textos) en vez de la capa de video? Hace falta la plantilla de texto de Premiere y que
    el panel que corre los entienda: con Premiere cerrado, al abrirse carga el panel nuevo (colocar() lo instala antes); abierto con el panel
    viejo (sin «panel» en el latido) no se recarga solo hasta reiniciarlo una vez. Desde un hilo (en Mac `abierto` lanza pgrep)."""
    if plantilla_texto() is None:
        return False
    if panel_vivo():
        try:
            return int((latido() or {}).get('panel') or 0) >= PANEL_TEXTOS
        except (TypeError, ValueError):
            return False
    return not abierto()


def nombre_de(exe):
    """«Adobe Premiere Pro 2026» (la carpeta del .exe en Windows, la .app en Mac); «Adobe Premiere Pro» si no se sabe."""
    if not exe:
        return 'Adobe Premiere Pro'
    exe = Path(exe)
    nombre = exe.stem if exe.suffix == '.app' else exe.parent.name
    return nombre if nombre.lower().startswith('adobe premiere pro') else 'Adobe Premiere Pro'


def estado():
    """v5.78 (el usuario: «que en Inicio diga conexión con Premiere Pro, que ya no diga DaVinci Resolve»): lo que Inicio y la barra enseñan
    con «Usar con Premiere Pro». Desde un hilo (en Mac lanza pgrep); barato: archivos, latido y procesos.
    → {'instalado', 'nombre', 'abierto', 'conectado', 'version', 'proyecto'}"""
    exe = ejecutable()
    vivo = panel_vivo()
    lat = (latido() or {}) if vivo else {}
    return {'instalado': exe is not None or vivo, 'nombre': nombre_de(exe), 'abierto': vivo or (exe is not None and abierto()),
            'conectado': vivo, 'version': str(lat.get('version') or ''), 'proyecto': str(lat.get('proyecto') or '')}


def textos_estado(est):
    """(línea de Inicio, tono, (título, detalle) de la barra y la tarjeta lateral) para el estado de `estado()`. tono: 'ok' | 'aviso' | 'error'.
    La línea lleva «detectado» como la de Resolve: el nombre en claro y desde ahí en el color del estado (un_clic_ui.LineaGo)."""
    from i18n import tr
    est = est or {}
    n = est.get('nombre') or 'Adobe Premiere Pro'
    if est.get('conectado'):
        detalle = ' · '.join(x for x in (n, est.get('version'), tr('proyecto «{p}»', p=est['proyecto']) if est.get('proyecto') else '') if x)
        return tr('{n} detectado · conectado', n=n), 'ok', (tr('Premiere Pro conectado'), detalle)
    if est.get('abierto'):
        return (tr('{n} abierto · conectando… (si no conecta, reinícialo una vez)', n=n), 'aviso',
                (tr('Premiere Pro · conectando…'), tr('Si no conecta: reinícialo una vez')))
    if est.get('instalado'):
        return tr('{n} detectado · cerrado: GO lo abre solo', n=n), 'aviso', (tr('Premiere Pro cerrado'), tr('GO lo abre solo'))
    return (tr('No encuentro Adobe Premiere Pro · instálalo o elige «Usar con DaVinci Resolve» en Ajustes'), 'error',
            (tr('Premiere Pro no encontrado'), tr('¿Está instalado?')))


def _ruta_libre(ruta):
    ruta = Path(ruta)
    if not ruta.exists():
        return ruta
    for n in range(2, 200):
        cand = ruta.with_name(f'{ruta.stem} {n}{ruta.suffix}')
        if not cand.exists():
            return cand
    return ruta.with_name(f'{ruta.stem} {int(time.time())}{ruta.suffix}')


def _duracion(ruta):
    import av
    try:
        c = av.open(str(ruta))
    except Exception:
        return 0.5
    try:
        if c.duration:
            return max(0.05, float(c.duration) / 1e6)
        if c.streams.audio:
            a = c.streams.audio[0]
            if a.duration:
                return max(0.05, float(a.duration * a.time_base))
        return 0.5
    finally:
        c.close()


def sonido_de_go(cues, res=None):
    """(sfx, musica), cada uno [(t, ruta, dur|None)]: lo MISMO que Resolve recibiría. Con el Sonido de GO (la biblioteca del autor o el AI
    Sound Director: `res` = su resultado ya cerrado) van sus efectos ya horneados (recorte, fundido y nivel dentro del archivo) y su música,
    y no los sonidos de siempre (en Resolve él es el único dueño del sonido); si no diseñó nada, los de siempre de cada palabra."""
    res = res or {}
    sfx = [(float(e.get('ini') or 0.0), e['archivo'], e.get('dur')) for e in ((res.get('sfx') or {}).get('eventos') or [])
           if e.get('archivo') and Path(e['archivo']).is_file()]
    musica = [(float(m.get('ini') or 0.0), m['archivo'], m.get('dur'))
              for m in (((res.get('capas') or {}).get('musica') or {}).get('plan') or []) if m.get('archivo') and Path(m['archivo']).is_file()]
    if sfx or musica:
        return sfx, musica
    import render_sin_resolve
    return [(t, r, None) for t, r in render_sin_resolve.eventos_sfx(cues)], []


def _sonidos(lista):
    durs, salida = {}, []
    for e in sorted(lista or [], key=lambda x: x[0]):
        t, ruta = e[0], e[1]
        dur = e[2] if len(e) > 2 else None
        if not ruta or not Path(ruta).is_file():
            continue
        ruta = str(Path(ruta).resolve())
        if not dur:
            if ruta not in durs:
                durs[ruta] = _duracion(ruta)
            dur = durs[ruta]
        salida.append({'ruta': ruta, 't': round(max(0.0, float(t)), 4), 'dur': round(float(dur), 4)})
    return salida


def armar_pedido(video, capa, sfx, nombre_estilo='', musica=None, piezas=None):
    """El pedido para el panel. capa: lo que devuelve render_sin_resolve.renderizar_capa; sfx / musica: [(t, ruta[, dur])] (sonido_de_go).
    v5.85: piezas = premiere_textos.preparar (textos editables + imágenes) en vez de la capa (capa = None)."""
    video = Path(video)
    sonidos = _sonidos(sfx)
    if piezas:
        plantilla = plantilla_texto()
        return {
            'id': uuid.uuid4().hex, 'version': 2, 'creado': time.time(), 'video': str(video.resolve()), 'capa': None, 'solo_audio': False,
            'duracion': piezas.get('duracion'), 'fps': piezas.get('fps'), 'secuencia': f'{video.stem} (CineCaptions)', 'bin': 'CineCaptions',
            'sfx': sonidos, 'musica': _sonidos(musica), 'pistas_sfx': PISTAS_SFX,
            'proyecto_nuevo': str(_ruta_libre(video.with_name(f'{video.stem} (CineCaptions).prproj')).resolve()), 'estilo': nombre_estilo or '',
            'plantilla': str(plantilla) if plantilla else None,
            'textos': piezas.get('textos') or [], 'imagenes': piezas.get('imagenes') or [],
            'carriles_texto': piezas.get('carriles_texto') or 0, 'carriles_imagen': piezas.get('carriles_imagen') or 0,
            'ancho': piezas.get('ancho'), 'alto': piezas.get('alto'),
        }
    return {
        'id': uuid.uuid4().hex,
        'version': 1,
        'creado': time.time(),
        'video': str(video.resolve()),
        'capa': str(Path(capa['ruta']).resolve()),
        'solo_audio': bool(capa.get('solo_audio')),
        'duracion': capa.get('duracion'),
        'fps': capa.get('fps'),
        'secuencia': f'{video.stem} (CineCaptions)',
        'bin': 'CineCaptions',
        'sfx': sonidos,
        'musica': _sonidos(musica),
        'pistas_sfx': PISTAS_SFX,
        'proyecto_nuevo': str(_ruta_libre(video.with_name(f'{video.stem} (CineCaptions).prproj')).resolve()),
        'estilo': nombre_estilo or '',
    }


def enviar(pedido):
    """Deja el pedido (escritura atómica: el panel nunca lee uno a medias) y borra la respuesta anterior."""
    import archivos_seguros
    cola = carpeta_cola()
    cola.mkdir(parents=True, exist_ok=True)
    for viejo in ('resultado.json', 'resultado.tmp', 'progreso.json'):
        try:
            (cola / viejo).unlink()
        except OSError:
            pass
    archivos_seguros.escribir_json(cola / 'pedido.json', pedido, ensure_ascii=True, indent=1)
    return pedido['id']


def retirar():
    """Quita un pedido que el panel aún no tomó (GO cancelado o sin respuesta): que no se coloque solo al abrir Premiere más tarde."""
    try:
        (carpeta_cola() / 'pedido.json').unlink()
    except OSError:
        pass


def progreso(id_pedido):
    """v5.85: (hechos, total) de las piezas que el panel lleva colocadas en ESE pedido (lo escribe cada 10), o None."""
    try:
        d = json.loads((carpeta_cola() / 'progreso.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get('id') != id_pedido:
        return None
    return int(d.get('hechos') or 0), int(d.get('total') or 0)


def resultado(id_pedido):
    try:
        d = json.loads((carpeta_cola() / 'resultado.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get('id') == id_pedido else None


def colocar(pedido, cancelado=None, aviso=None, espera_abrir_s=ESPERA_ABRIR_S, espera_colocar_s=ESPERA_COLOCAR_S):
    """Manda el pedido a Premiere Pro (lo abre si está cerrado) y espera a que el panel lo coloque. Desde un hilo.
    → {'ok', 'secuencia', 'sfx', 'proyecto', 'error', 'causa'} (causa: 'sin_premiere' | 'panel' | 'sin_panel' | 'reiniciar' | 'premiere')
    · {'ok': False, 'cancelado': True}"""
    def decir(texto):
        if aviso:
            try:
                aviso(texto)
            except Exception:
                pass

    inst = instalar_panel()
    if not inst['ok']:
        return {'ok': False, 'causa': 'panel', 'error': inst['texto']}
    exe = ejecutable()
    if exe is None and not panel_vivo():
        return {'ok': False, 'causa': 'sin_premiere',
                'error': 'No encuentro Adobe Premiere Pro en este equipo. Instálalo (o elige «Usar con DaVinci Resolve» en Ajustes > General).'}
    estaba_abierto = abierto()
    proyecto = None
    if not estaba_abierto and not panel_vivo() and pedido.get('proyecto_nuevo'):
        # v5.85: Premiere cerrado → se abre YA con el proyecto nuevo (sin proyecto se queda en su pantalla de inicio y el panel no carga)
        proyecto = crear_proyecto(pedido['proyecto_nuevo'])
        if proyecto is not None:
            pedido['proyecto_nuevo'] = str(proyecto)
            _CREADOS.append(str(proyecto))
            del _CREADOS[:-10]
        else:
            try:
                import registro
                from i18n import tr
                registro.aviso(tr('No pude crear el proyecto de Premiere Pro junto al video ({r}): lo abro sin proyecto.', r=pedido['proyecto_nuevo']),
                               'GO · Premiere Pro')
            except Exception:
                pass
    pedido['proyectos_cc'] = list(_CREADOS)          # (el panel guarda al terminar los proyectos que escribió CineCaptions, no los del usuario)
    id_pedido = enviar(pedido)
    if not panel_vivo():
        if estaba_abierto:
            decir('Esperando a Premiere Pro…')
        else:
            decir('Abriendo Adobe Premiere Pro…')
            abrir(exe, proyecto)
    limite = time.time() + espera_abrir_s
    tomado = False
    visto_vivo = False
    ultimo_avance = None
    while True:
        if cancelado and cancelado():
            retirar()
            return {'ok': False, 'cancelado': True}
        r = resultado(id_pedido)
        if r is not None:
            if not r.get('ok'):
                r.setdefault('causa', 'premiere')
            return r
        if not tomado and not (carpeta_cola() / 'pedido.json').exists():
            tomado = True                            # el panel lo tomó: colocando (mientras coloca no late: ExtendScript es de un hilo)
            limite = time.time() + espera_colocar_s
            decir('Colocando en Premiere Pro…')
        if tomado:                                   # v5.85: el avance de los textos e imágenes: mientras siga, se sigue esperando
            pr = progreso(id_pedido)
            if pr and pr != ultimo_avance:
                ultimo_avance = pr
                limite = max(limite, time.time() + ESPERA_SIN_AVANCE_S)
                try:
                    from i18n import tr
                    decir(tr('Colocando en Premiere Pro… {h} de {t}', h=pr[0], t=pr[1]))
                except Exception:
                    pass
        if not tomado and not visto_vivo and panel_vivo():
            visto_vivo = True
            decir('Premiere Pro conectado…')
        if time.time() > limite:
            retirar()
            if tomado:
                return {'ok': False, 'causa': 'premiere',
                        'error': 'Premiere Pro tomó el pedido pero no terminó de colocarlo (¿hay una ventana abierta en Premiere?).'}
            if estaba_abierto and inst.get('instalado'):
                return {'ok': False, 'causa': 'reiniciar',
                        'error': 'Cierra Premiere Pro y vuelve a abrirlo: el panel de CineCaptions se acaba de instalar y Premiere solo lo carga al arrancar. Luego pulsa GO otra vez.'}
            return {'ok': False, 'causa': 'sin_panel',
                    'error': 'Premiere Pro no contestó. Ábrelo con un proyecto y, si no se conecta, abre una vez Ventana > Extensiones > CineCaptions. Luego pulsa GO otra vez.'}
        time.sleep(0.25)
