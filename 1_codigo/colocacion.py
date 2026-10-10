# CineCaptions · By Cinema Productions
# 1_codigo/colocacion.py — qué edición de Resolve hay (Free / Studio), si lo colocado en el timeline es REAL, por qué falló en lenguaje claro, cómo repararlo solo y cómo dejar la vista.
"""
colocacion.py  (v5.5)
---------------------
Antes GO decía «¡Listo!» aunque Resolve no hubiera colocado NADA: el script de Resolve termina «bien» cuando no encuentra dónde poner las líneas (lo dejaba en su resultado como
ok=False o «0 líneas colocadas», pero la app sólo miraba que el script hubiera corrido). Este módulo es el que dice la verdad:

    detectar_resolve()      DaVinci Resolve Studio o Free, por qué camino se le habla (MCP, API, Puente) y si GO puede trabajar ahora → el texto de la línea de Inicio
    veredicto(...)          lo que de verdad pasó al colocar: líneas colocadas, avisos, causa en lenguaje claro y el primer remedio
    reparar(...)            lo que se puede arreglar solo (bin del pack a medias, sin timeline, Resolve ocupado) antes de decir que falló
    registrar(...)          UNA entrada clara en el Registro (resultado, edición, camino, cuántas líneas, avisos)
    vista_en_manifiesto()   «abrir siempre con mi vista»: la página Edit, la disposición de pantalla que el usuario guardó (vertical + vista expandida) y el cabezal al inicio
    reproducir_desde_inicio()  al terminar, Resolve en primer plano y «reproducir» desde el principio (Inicio + Espacio)
    guardar_vista_actual()  guarda la disposición de pantalla actual de Resolve como la de CineCaptions (resolve.SaveLayoutPreset)

Prefs: go_reproducir (sí), go_vista_resolve (sí), go_vista_nombre («CineCaptions vertical»).
"""
import json
import re
import sys
import time

from i18n import tr

VISTA_NOMBRE_DEFECTO = 'CineCaptions vertical'


def _prefs():
    try:
        import ajustes_ui
        return ajustes_ui.leer_prefs()
    except Exception:
        return {}


def vista_nombre():
    return str(_prefs().get('go_vista_nombre') or VISTA_NOMBRE_DEFECTO)


# ------------------------------------------------------------------------------------------------------------------------------- 1) la edición
def detectar_resolve(estado=None, refrescar=False):
    """Qué Resolve hay y cómo se le habla. `estado` = lo que ya recogió la ventana (_estado_sistema: 'mcp', 'modo', 'edicion', 'instalado'); sin él se pregunta (con `refrescar` se arranca
    ResolveMCP si hace falta: sólo desde un hilo). Devuelve {'edicion': 'Studio'|'Free'|None, 'camino': 'mcp'|'api'|'puente'|'sin_puente'|'cerrado'|'no_instalado', 'version', 'texto', 'tono':
    'ok'|'aviso'|'error', 'listo': bool, 'ayuda': str}. `listo` = GO puede colocar AHORA por ese camino."""
    estado = dict(estado or {})
    mcp = estado.get('mcp')
    modo = estado.get('modo')
    if mcp is None:
        try:
            import resolve_mcp
            mcp = resolve_mcp.estado(pasivo=not refrescar, refrescar=bool(refrescar))
        except Exception:
            mcp = {}
    mcp = mcp or {}
    if modo is None:
        try:
            import resolve_bridge
            modo = resolve_bridge.modo_actual(pasivo=not refrescar)
        except Exception:
            modo = None
    edicion_guardada = estado.get('edicion')
    if edicion_guardada is None:
        try:
            import instalador_scripts as ins
            edicion_guardada = ins.edicion_de_resolve()
        except Exception:
            edicion_guardada = 'desconocida'
    instalado = estado.get('instalado')
    version = '.'.join(str(mcp.get('version') or '').strip().split('.')[:3])          # «21.1.1.10» → «21.1.1»: la línea de Inicio es corta
    ver = (' ' + version) if version else ''
    if mcp.get('conectado'):
        studio = 'Studio' in str(mcp.get('producto') or '')
        ed = 'Studio' if studio else 'Free'
        texto = tr('DaVinci Resolve {e}{v} detectado', e=ed, v=ver)
        ayuda = '' if studio else tr('Free: GO trabaja por el MCP de Resolve 21. Si no aparece nada en el timeline, el Registro dice el motivo.')
        return dict(edicion=ed, camino='mcp', version=version, texto=texto, tono='ok', listo=True, ayuda=ayuda)
    if modo == 'studio':
        return dict(edicion='Studio', camino='api', version=version, texto=tr('DaVinci Resolve Studio detectado · API directa'), tono='ok', listo=True, ayuda='')
    if modo == 'puente':
        return dict(edicion='Free', camino='puente', version=version, texto=tr('DaVinci Resolve Free detectado · Puente activo'), tono='ok', listo=True, ayuda='')
    if mcp.get('mcp') and not mcp.get('conectado') and (edicion_guardada in ('studio', 'free', 'desconocida', None)):
        ed = {'studio': 'Studio', 'free': 'Free'}.get(edicion_guardada)
        cual = f' {ed}' if ed else ''
        return dict(edicion=ed, camino='cerrado', version=version, texto=tr('DaVinci Resolve{c} cerrado · se abre solo al pulsar GO', c=cual), tono='aviso', listo=True,
                    ayuda=tr('Ábrelo con tu proyecto o deja que GO lo abra.'))
    if edicion_guardada == 'studio':
        return dict(edicion='Studio', camino='cerrado', version=version, texto=tr('DaVinci Resolve Studio cerrado · ábrelo con tu proyecto'), tono='aviso', listo=False, ayuda=tr('Abre Resolve con tu proyecto.'))
    if instalado is False:
        return dict(edicion=None, camino='no_instalado', version='', texto=tr('No encuentro DaVinci Resolve · ¿está instalado?'), tono='error', listo=False,
                    ayuda=tr('Instala DaVinci Resolve (Studio o la versión gratuita) y vuelve a abrir CineCaptions.'))
    if estado.get('proceso') is False:
        ed = {'free': 'Free'}.get(edicion_guardada)
        cual = f' {ed}' if ed else ''
        return dict(edicion=ed, camino='cerrado', version=version, texto=tr('DaVinci Resolve{c} cerrado · ábrelo con tu proyecto', c=cual), tono='aviso', listo=False,
                    ayuda=tr('Abre Resolve con tu proyecto y pulsa GO.'))
    # Resolve abierto sin MCP ni API externa: es Free (o Studio con «External scripting» en None): se habla por el Puente
    paso = tr('Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Puente')
    if sys.platform == 'darwin' or sys.platform.startswith('win'):           # Mac: pulsa el menú; Windows: abre la consola F6 de Resolve y lanza el Puente (lanzar_puente_windows)
        return dict(edicion='Free', camino='sin_puente', version=version, texto=tr('DaVinci Resolve Free detectado · lanzo el Puente al pulsar GO'), tono='aviso', listo=True,
                    ayuda=tr('Si macOS lo pide, da permiso de Accesibilidad a CineCaptions.') if sys.platform == 'darwin' else tr('Resolve tiene que estar al frente y con un proyecto abierto; el Puente se lanza desde su consola (F6).'))
    return dict(edicion='Free', camino='sin_puente', version=version, texto=tr('DaVinci Resolve Free detectado · falta lanzar el Puente'), tono='aviso', listo=False,
                ayuda=tr('En Resolve Free CineCaptions trabaja por un script que se lanza UNA vez por sesión: {p}', p=paso))


def resolve_en_proceso():
    """True/False: ¿hay un proceso de DaVinci Resolve corriendo? (None = no se pudo saber). Lanza un proceso del sistema: SOLO desde un hilo, nunca desde la interfaz."""
    import subprocess
    try:
        if sys.platform.startswith('win'):
            r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Resolve.exe', '/NH'], capture_output=True, text=True, errors='replace', timeout=8, creationflags=0x08000000)
            return 'resolve.exe' in (r.stdout or '').lower()
        r = subprocess.run(['pgrep', '-x', 'Resolve'], capture_output=True, text=True, errors='replace', timeout=8)
        return r.returncode == 0
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------------------------------------- 2) la verdad
# (patrón sobre el registro de la corrida, clave, título, qué pasó, pasos, qué reparar solo)
CAUSAS = [
    (r'no tiene bloques|no tiene (palabras|l[ií]neas)|archivo de datos .{0,40}(vac[ií]o|no existe)',
     'vacio', 'No había nada que colocar',
     'La transcripción no dejó ningún bloque de texto (el audio no tiene voz o el idioma elegido no coincide), así que Resolve no tenía qué poner.',
     ['Comprueba que el video suena y que se oye a alguien hablando.', 'Elige el idioma en el chip «Idioma» de Inicio (en vez de «Detectar») y pulsa GO.'], None),
    (r'no encontr[eé] ning[uú]n Text\+|necesita un pack con sets|no pude preparar el pack|0 sets|sin clip para ese rol',
     'pack', 'Resolve no tiene las piezas del estilo',
     'El estilo elegido guarda sus piezas (los títulos) en un bin del Media Pool y Resolve no las tiene o quedaron a medias.',
     ['Lo intento una vez más solo; si sigue igual, en el Media Pool renombra o borra el bin «RCS · …» de ese estilo (CineCaptions lo vuelve a crear) y pulsa GO otra vez.',
      'En Resolve Free, arrastra una vez los clips del pack al Media Pool (Estilos ▸ «Abrir en Resolve»).'], 'pack'),
    (r'no pude crear la pista|no pude preparar (las|la) pistas?|no pude crear la pista de audio',
     'pistas', 'Resolve no dejó crear las pistas de los subtítulos',
     'Para colocar los captions CineCaptions crea pistas nuevas y Resolve no lo permitió (timeline bloqueado, con la selección en otra página o con un diálogo abierto).',
     ['Cierra los diálogos de Resolve, ve a la página Edit y pulsa GO otra vez.', 'Si el timeline está bloqueado (candado), desbloquéalo.'], 'ocupado'),
    (r'No hay ning[uú]n timeline|no hay timeline|sin timeline',
     'timeline', 'No hay un timeline abierto en Resolve',
     'Resolve no tiene un timeline activo donde colocar los subtítulos.',
     ['Abre un timeline en Resolve (o suelta un video en CineCaptions para que se arme uno) y pulsa GO.'], 'timeline'),
    (r'External scripting|no est[aá] aceptando scripts|scripting externo|MENSAJE_SCRIPTING',
     'scripting', 'Resolve no acepta scripts de fuera',
     'En Resolve Studio hay que permitir los scripts externos; en Free, lanzar el Puente desde el menú.',
     ['Studio: Preferencias ▸ Sistema ▸ General ▸ «External scripting using» = Local, y reinicia Resolve.',
      'Free: Área de trabajo > Scripts («Secuencias de comandos» si tu Resolve está en español) > CineCaptions_Puente.'], None),
    (r'no pude escribir su texto|no pude setear el texto',
     'texto', 'Los clips se pusieron pero sin su texto',
     'Resolve colocó los títulos pero no dejó escribir el texto en ellos (el pack elegido no trae un Text+ editable por script).',
     ['Prueba con otro estilo en el chip «Estilo» de Inicio.', 'Si es un estilo tuyo, ábrelo en Resolve y revisa que su Text+ se llame «Template».'], None),
    (r'no pude colocar «|no pude colocar el bloque|no se colocaron|No se coloc[oó] ninguna',
     'clips', 'Resolve no dejó colocar los clips',
     'El script de Resolve corrió, pero ningún clip llegó al timeline (Resolve los rechazó o no había dónde ponerlos).',
     ['Mira el Registro: el motivo está en las líneas «Aviso:» de esta corrida.', 'Prueba con otro timeline o con otro estilo; si el problema sigue, copia el informe del Registro y envíalo a soporte.'], 'ocupado'),
]


def causa_de(texto):
    """(clave, título, qué, pasos, reparación) del primer patrón de CAUSAS que encaja con el registro de la corrida, o None."""
    t = str(texto or '')
    for patron, clave, titulo, que, pasos, rep in CAUSAS:
        if re.search(patron, t, re.I):
            return clave, titulo, que, pasos, rep
    return None


def _contar(texto, res):
    """Cuántas líneas colocó la corrida: del resumen que deja el script («214 líneas colocadas») o, si no, de las líneas «Colocadas N…» de su registro. None = no se pudo saber."""
    mensaje = str((res or {}).get('mensaje') or '') if isinstance(res, dict) else ''
    m = re.search(r'(\d+)\s+l[ií]neas colocadas', mensaje, re.I)
    if m:
        return int(m.group(1))
    sumas = [int(x) for x in re.findall(r'Colocad[oa]s\s+(\d+)', str(texto or ''))]
    return sum(sumas) if sumas else None


def _avisos(texto, tope=6):
    """Las líneas «Aviso: …» / «ERROR: …» de la corrida (sin repetir), para mostrarlas tal cual."""
    vistos, salida = set(), []
    for linea in str(texto or '').splitlines():
        l = linea.strip()
        if re.match(r'(\[[^\]]+\]\s*)?(Aviso|ERROR|Error)\b', l):
            clave = re.sub(r'\d+(\.\d+)?', '#', l)
            if clave not in vistos:
                vistos.add(clave)
                salida.append(l[:220])
    return salida[:tope]


def veredicto(ok, err, desde, n_cues=0):
    """Lo que de verdad pasó al colocar. `ok`/`err` = lo que devolvió resolve_bridge.ejecutar; `desde` = cuándo se pidió (para no leer el resultado de una corrida anterior).
    Devuelve {'ok', 'colocados', 'esperados', 'avisos', 'causa': (clave, título, qué, pasos, reparación) | None, 'mensaje', 'texto'}."""
    res, texto = None, ''
    try:
        import resolve_bridge
        res = resolve_bridge.ultimo_resultado(desde=desde)
        texto = resolve_bridge.texto_ultimo_resultado(desde=desde) or ''
    except Exception:
        res, texto = None, ''
    colocados = _contar(texto, res)
    avisos = _avisos(texto)
    mensaje = str((res or {}).get('mensaje') or '') if isinstance(res, dict) else ''
    ok_real = bool(ok)
    if ok_real and isinstance(res, dict) and res.get('ok') is False:
        ok_real = False                                   # el script corrió, pero dejó dicho que NO colocó nada (antes la app lo daba por bueno)
    if ok_real and colocados == 0:
        ok_real = False
    causa = None
    if not ok_real:
        causa = causa_de('\n'.join([str(err or ''), mensaje, texto]))
    return {'ok': ok_real, 'colocados': colocados, 'esperados': int(n_cues or 0), 'avisos': avisos, 'causa': causa, 'mensaje': mensaje or str(err or ''), 'texto': texto}


def detalle_de_fallo(v):
    """El detalle del error que va al Registro: la marca de la causa («[causa:pack]», la que registro_ayuda convierte en título + pasos), qué pasó y los avisos del script."""
    c = v.get('causa')
    partes = [f'[causa:{c[0]}]' if c else '[causa:clips]']
    if c:
        partes.append(c[2])
    partes.extend((v.get('avisos') or [])[:3])
    return '\n'.join(partes)


def texto_para_usuario(v):
    """El cuadro de aviso cuando no se colocó nada fuera de GO: qué pasó, por qué y qué probar, en lista."""
    c = v.get('causa')
    if not c:
        return frase_de_fallo(v)
    _clave, titulo, que, pasos, _rep = c
    texto = titulo + '.\n\n' + que + '\n\n' + tr('Qué probar:') + '\n' + '\n'.join(f'  {i}. {p}' for i, p in enumerate(pasos, 1))
    if v.get('avisos'):
        texto += '\n\n' + tr('Lo que dijo Resolve:') + '\n' + '\n'.join('  · ' + a for a in v['avisos'][:3])
    return texto


def frase_de_fallo(v):
    """Una frase clara para la línea de Inicio cuando no se colocó nada: causa + primer remedio."""
    c = v.get('causa')
    if c:
        _clave, titulo, _que, pasos, _rep = c
        return titulo + '. ' + (tr('Prueba esto: {p}', p=pasos[0]) if pasos else '')
    base = str(v.get('mensaje') or '').strip().splitlines()
    return (base[0][:170] if base else tr('Resolve no colocó nada en el timeline.')) + ' ' + tr('Mira el Registro.')


# ------------------------------------------------------------------------------------------------------------------------------- 3) reparar solo
def reparar(v, pack=None, al_estado=None):
    """Arregla lo que se puede arreglar sin molestar y SIN borrar nada del proyecto del usuario (los bins «RCS · …» del Media Pool no se tocan: el script de Resolve ya rehace él mismo
    un bin del pack que quedó a medias). Devuelve lo que hizo, en frases; lista vacía = no hay nada que reparar y repetir no serviría (p. ej. scripting externo cerrado)."""
    hecho = []
    c = v.get('causa')
    rep = c[4] if c else 'ocupado'
    if c and rep is None:
        return hecho
    def decir(t):
        if al_estado:
            try:
                al_estado(t)
            except Exception:
                pass
    try:
        import resolve_mcp
        hay_mcp = resolve_mcp.disponible()
        if rep == 'timeline' and hay_mcp:
            decir(tr('Reparando: abriendo un timeline en Resolve…'))
            prep = resolve_mcp.preparar_resolve(abrir=True, pagina='edit', al_estado=al_estado)
            hecho.append(tr('abrí el timeline «{t}» de Resolve', t=prep.get('timeline') or '—') if prep.get('ok') else tr('intenté abrir el timeline y Resolve no respondió'))
            if not prep.get('ok'):
                return hecho
        else:
            decir(tr('Reparando: dejo Resolve libre y vuelvo a intentarlo…') if rep != 'pack' else tr('Reparando: vuelvo a pedirle a Resolve las piezas del estilo…'))
            if hay_mcp:
                resolve_mcp.script("resolve.OpenPage('edit')\nresult = True", timeout=15)
            time.sleep(2.5)
            hecho.append(tr('volví a la página Edit y esperé a que Resolve quedara libre') if hay_mcp else tr('esperé a que Resolve quedara libre'))
            if rep == 'pack':
                hecho.append(tr('el script rehace solo el bin del estilo si estaba a medias (no borré nada de tu Media Pool)'))
        try:
            import vistas_reales
            vistas_reales.reparar_pendiente()               # un timeline temporal de «vista real» que se quedó como actual
        except Exception:
            pass
    except Exception as e:
        hecho.append(tr('no pude reparar ({e})', e=f'{type(e).__name__}'))
    return hecho


# ------------------------------------------------------------------------------------------------------------------------------- 4) el Registro
def registrar(v, edicion=None, camino=None, segundos=None, reparado=None):
    """UNA entrada clara en el Registro: qué pasó, con qué Resolve y por qué camino, y qué se hizo."""
    try:
        import registro
    except Exception:
        return
    partes = []
    if edicion:
        partes.append(tr('Resolve {e}', e=edicion))
    if camino:
        partes.append({'mcp': 'MCP', 'api': tr('API directa'), 'puente': tr('Puente'), 'sin_puente': tr('Puente')}.get(camino, str(camino)))
    if segundos is not None:
        partes.append(tr('{s:.0f} s', s=segundos))
    donde = ' · '.join(partes)
    detalle = '\n'.join(v.get('avisos') or [])
    if v.get('ok'):
        n = v.get('colocados')
        txt = tr('Colocado en Resolve: {n} líneas', n=n) if n else tr('Colocado en Resolve')
        if donde:
            txt += f' ({donde})'
        if reparado:
            txt += ' · ' + tr('tras reparar: {r}', r='; '.join(reparado))
        if v.get('avisos'):
            registro.aviso(txt + ' · ' + tr('{n} avisos', n=len(v['avisos'])), 'colocar en Resolve', detalle=detalle)
        else:
            registro.ok(txt, 'colocar en Resolve')
    else:
        c = v.get('causa')
        primera = (str(v.get('mensaje') or '').splitlines() or [''])[0][:120]
        txt = tr('NO se colocó nada en Resolve') + (f' ({donde})' if donde else '') + ': ' + (c[1] if c else (primera or tr('sin motivo claro')))
        if reparado:
            txt += ' · ' + tr('intenté reparar: {r}', r='; '.join(reparado))
        registro.aviso(txt, 'colocar en Resolve', detalle=(c[2] + '\n' if c else '') + detalle)      # (el ERROR que ve el usuario lo anota GO / el aviso de la ventana, con la causa)


# ------------------------------------------------------------------------------------------------------------------------------- 5) la vista
def archivo_de_la_vista():
    """v5.4.23: la disposición de pantalla que trae el programa (2_recursos/resolve_layouts/<nombre>.preset: vertical y con «Expandir vista»), o '' si no hay. Resolve la importa
    (resolve.ImportLayoutPreset) la primera vez que GO termina, y desde entonces la aplica siempre."""
    try:
        import instalador_scripts
        p = instalador_scripts.BASE_RECURSOS / 'resolve_layouts' / (vista_nombre() + '.preset')
        return str(p) if p.is_file() else ''
    except Exception:
        return ''


def vista_en_manifiesto(ruta_manifiesto):
    """Antes de colocar: apunta en el manifiesto cómo debe quedar Resolve al terminar (el script lo lee): página Edit, la disposición de pantalla guardada (vertical y vista expandida) y el
    cabezal al inicio. `go_vista_resolve` = False lo apaga."""
    try:
        import archivos_seguros
        from pathlib import Path
        p = Path(ruta_manifiesto)
        datos = json.loads(p.read_text(encoding='utf-8'))
        if not isinstance(datos, dict):
            return False
        usar = _prefs().get('go_vista_resolve', True) is not False
        datos['vista'] = {'pagina': 'edit', 'preset': vista_nombre() if usar else '', 'al_inicio': True, 'archivo': archivo_de_la_vista() if usar else ''}
        archivos_seguros.escribir_json(p, datos)
        try:                                       # Resolve Free 21.1 (sin io) lee el manifiesto por su gemelo «.lua»: sin esto no veria la «vista»
            import sidecar_lua
            sidecar_lua.escribir_sidecar(p, datos)
        except Exception:
            pass
        return True
    except Exception:
        return False


_VISTA_GUARDAR = r'''
nombre = %(nombre)r
lista = resolve.GetLayoutPresetList() or []
if nombre in lista:
    ok = bool(resolve.UpdateLayoutPreset(nombre))
else:
    ok = bool(resolve.SaveLayoutPreset(nombre))
result = {'ok': ok, 'ya_existia': nombre in lista, 'lista': list(resolve.GetLayoutPresetList() or [])}
'''
_VISTA_LISTA = r'''
result = {'lista': list(resolve.GetLayoutPresetList() or [])}
'''


def vista_por_puente(accion='guardar', timeout=60):
    """Resolve Free (sin MCP): guardar o aplicar la disposición de pantalla por el Puente (CineCaptions_Vista.lua). Devuelve (ok, mensaje)."""
    import archivos_seguros
    import resolve_bridge
    import sidecar_lua
    ruta = resolve_bridge.CARPETA_COMPARTIDA / 'vista_orden.json'
    orden = {'accion': str(accion), 'nombre': vista_nombre()}
    archivos_seguros.escribir_json(ruta, orden)
    sidecar_lua.escribir_sidecar(ruta, orden)
    if resolve_bridge.modo_actual() == 'manual' and not resolve_bridge.lanzar_puente_auto():
        return False, tr('El Puente de Resolve no está activo: abre Resolve con un proyecto y repite.')
    return resolve_bridge.ejecutar('vista', timeout=timeout)


def guardar_vista_actual():
    """Guarda la disposición de pantalla ACTUAL de Resolve (la que el usuario dejó vertical y con la vista expandida) como la de CineCaptions. Devuelve (ok, texto para el usuario)."""
    try:
        import resolve_mcp
        if not resolve_mcp.disponible():                          # v5.4.23: Resolve Free lo hace por el Puente (antes había que guardarla a mano)
            ok, msg = vista_por_puente('guardar')
            if ok:
                return True, tr('Guardé la disposición actual de Resolve como «{n}»: se aplicará cada vez que GO termine.', n=vista_nombre())
            return False, tr('Resolve no guardó la disposición ({e}).', e=str(msg)[:140])
        ok, r, err = resolve_mcp.script(_VISTA_GUARDAR % {'nombre': vista_nombre()}, timeout=30)
        if ok and (r or {}).get('ok'):
            return True, tr('Guardé la disposición actual de Resolve como «{n}»: se aplicará cada vez que GO termine.', n=vista_nombre())
        return False, tr('Resolve no guardó la disposición ({e}).', e=str(err or r)[:120])
    except Exception as e:
        return False, tr('No pude guardar la disposición ({e}).', e=type(e).__name__)


def vista_guardada():
    """True si Resolve tiene guardada la disposición de CineCaptions; None si no se puede saber (sin conexión)."""
    try:
        import resolve_mcp
        if not resolve_mcp.disponible():
            return None
        ok, r, _e = resolve_mcp.script(_VISTA_LISTA, timeout=20)
        return (vista_nombre() in ((r or {}).get('lista') or [])) if ok else None
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------------------------------------- 6) reproducir
def _hwnd_de_resolve():
    """El HWND de la ventana principal de DaVinci Resolve (Windows), buscando por el PROCESO (Resolve.exe), no por el título: un navegador con una pestaña «DaVinci Resolve…» no cuenta."""
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    hallada = []

    @ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _l):
        if not user32.IsWindowVisible(h):
            return 1
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        proc = kernel32.OpenProcess(0x1000, False, pid.value)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not proc:
            return 1
        try:
            buf = ctypes.create_unicode_buffer(520)
            n = wintypes.DWORD(520)
            if kernel32.QueryFullProcessImageNameW(proc, 0, buf, ctypes.byref(n)) and buf.value.lower().endswith('\\resolve.exe'):
                largo = user32.GetWindowTextLengthW(h)
                if largo > 0:
                    hallada.append(h)
        finally:
            kernel32.CloseHandle(proc)
        return 1
    user32.EnumWindows(cb, 0)
    return hallada[0] if hallada else None


def _cerrar_consola_de_resolve():
    """Cierra (oculta) la consola de comandos de Resolve (la ventana titulada «Resolve»): el Puente sigue vivo. Nunca lanza."""
    try:
        import ctypes
        cerrada = False
        for h, t in _ventanas_de_resolve():
            if t.strip() == 'Resolve':
                ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)       # WM_CLOSE
                cerrada = True
        if cerrada:
            time.sleep(0.5)
    except Exception:
        pass


def _al_frente(h, intentos=4):
    """Windows no deja que un proceso en segundo plano se ponga al frente (bloqueo del primer plano): se prueba con el truco de unir el hilo de entrada al de la ventana que lo tiene, restaurar si estaba minimizada y SwitchToThisWindow, varias veces.
    True solo si al final Resolve de verdad tiene el foco."""
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    for _ in range(max(1, intentos)):
        if user32.IsIconic(h):
            user32.ShowWindow(h, 9)                                 # SW_RESTORE
        if user32.GetForegroundWindow() == h:
            return True
        pid = wintypes.DWORD()
        hilo_fg = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
        hilo_yo = kernel32.GetCurrentThreadId()
        user32.AllowSetForegroundWindow(-1)                         # ASFW_ANY
        unido = bool(hilo_fg and hilo_fg != hilo_yo and user32.AttachThreadInput(hilo_yo, hilo_fg, True))
        try:
            user32.keybd_event(0x12, 0, 0, 0)                       # un toque de Alt: Windows deja cambiar el foco
            user32.keybd_event(0x12, 0, 2, 0)
            user32.BringWindowToTop(h)
            user32.SetForegroundWindow(h)
            user32.SwitchToThisWindow(h, True)
        finally:
            if unido:
                user32.AttachThreadInput(hilo_yo, hilo_fg, False)
        time.sleep(0.35)
        if user32.GetForegroundWindow() == h:
            return True
    return False


def _ventanas_de_resolve():
    """[(hwnd, título)] de las ventanas visibles con título del proceso Resolve.exe (Windows)."""
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    halladas = []

    @ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _l):
        if not user32.IsWindowVisible(h):
            return 1
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        proc = kernel32.OpenProcess(0x1000, False, pid.value)
        if not proc:
            return 1
        try:
            buf = ctypes.create_unicode_buffer(520)
            n = wintypes.DWORD(520)
            if kernel32.QueryFullProcessImageNameW(proc, 0, buf, ctypes.byref(n)) and buf.value.lower().endswith('\\resolve.exe'):
                largo = user32.GetWindowTextLengthW(h)
                if largo > 0:
                    titulo = ctypes.create_unicode_buffer(largo + 1)
                    user32.GetWindowTextW(h, titulo, largo + 1)
                    halladas.append((h, titulo.value))
        finally:
            kernel32.CloseHandle(proc)
        return 1
    user32.EnumWindows(cb, 0)
    return halladas


def _escribir_texto(texto, pausa=0.012, hwnd=None):
    """Escribe `texto` en la ventana que tiene el foco con SendInput en modo Unicode: no depende del idioma del teclado ni de Bloq Mayus. Con `hwnd`, ANTES de cada caracter mira que esa
    ventana siga teniendo el foco y, si no, PARA (devuelve False): en un Resolve recien abierto el foco se escapaba a media orden y el resto del texto caia en otra aplicacion."""
    import ctypes
    from ctypes import wintypes
    PUL = ctypes.POINTER(ctypes.c_ulong)

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', PUL)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', PUL)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD), ('wParamH', wintypes.WORD)]

    class _UNION(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT), ('hi', HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [('type', wintypes.DWORD), ('u', _UNION)]
    envio = ctypes.windll.user32.SendInput
    foco = ctypes.windll.user32.GetForegroundWindow
    for caracter in texto:
        if hwnd is not None and foco() != hwnd:
            return False
        for marca in (0x0004, 0x0004 | 0x0002):                       # KEYEVENTF_UNICODE, y el mismo con KEYUP
            entrada = INPUT(type=1, u=_UNION(ki=KEYBDINPUT(0, ord(caracter), marca, 0, None)))
            envio(1, ctypes.byref(entrada), ctypes.sizeof(entrada))
        time.sleep(pausa)
    return True


def _borrar_linea_de_consola(user32, consola):
    '''Ctrl+A y Retroceso en la consola de Resolve (deja vacia la linea de entrada); cada tecla solo si la consola SIGUE con el foco.'''
    for vk, bandera in ((0x11, 0), (0x41, 0), (0x41, 2), (0x11, 2), (0x08, 0), (0x08, 2)):
        if user32.GetForegroundWindow() != consola:
            if bandera == 2 and vk == 0x11:
                user32.keybd_event(0x11, 0, 2, 0)                   # (nunca dejar Ctrl apretada)
            return False
        user32.keybd_event(vk, 0, bandera, 0)
        time.sleep(0.03)
    return True


def _ventana_principal(ventanas=None):
    """La ventana principal de Resolve CON un proyecto abierto («DaVinci Resolve - <proyecto>»); la pantalla de proyectos no vale: ahí no hay consola ni timeline."""
    return next((h for h, t in (ventanas if ventanas is not None else _ventanas_de_resolve()) if t.startswith('DaVinci Resolve - ')), None)


# Resolve recién abierto muestra el «Organizador de proyectos» (la pantalla de proyectos): sin un proyecto abierto no hay menú de Scripts ni consola, y el Puente no puede arrancar. La app la pasa sola
# con la accesibilidad de Windows (UI Automation): los botones de Resolve tienen ids fijos que NO cambian con el idioma (btnAddProject = «Crear proyecto», pushButton_Create = «Crear»).
_PS_ORGANIZADOR = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$AE = [System.Windows.Automation.AutomationElement]
$TS = [System.Windows.Automation.TreeScope]
$ids = @(Get-Process Resolve -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
if (-not $ids) { 'NO_RESOLVE'; exit }
function Ventanas {
    $pm = $null; $dlg = $null
    foreach ($id in $ids) {
        $c = New-Object System.Windows.Automation.PropertyCondition($AE::ProcessIdProperty, $id)
        foreach ($v in $AE::RootElement.FindAll($TS::Children, $c)) {
            $cn = $v.Current.ClassName
            if ($cn -like '*NewProjectOptionsDlg*') { $dlg = $v } elseif ($cn -like '*UiProjectManagerDialog*') { $pm = $v }
        }
    }
    return @($pm, $dlg)
}
function Buscar($raiz, $tipo, $fin) {
    $c = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $tipo)
    foreach ($e in $raiz.FindAll($TS::Descendants, $c)) { if ($e.Current.AutomationId -like $fin) { return $e } }
    return $null
}
$pm, $dlg = Ventanas
if (-not $dlg) {
    if (-not $pm) { 'SIN_ORGANIZADOR'; exit }
    $b = Buscar $pm ([System.Windows.Automation.ControlType]::Button) '*projActionBottomFrame.btnAddProject'
    if (-not $b) { 'SIN_BOTON'; exit }
    $b.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    for ($i = 0; $i -lt 32 -and -not $dlg; $i++) { Start-Sleep -Milliseconds 250; $pm, $dlg = Ventanas }
}
if (-not $dlg) { 'SIN_DIALOGO'; exit }
$ed = Buscar $dlg ([System.Windows.Automation.ControlType]::Edit) '*lineEdit_ProjectName'
$nombre = ''
if ($ed) {
    $vp = $ed.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    if ($env:CC_NOMBRE) { try { $vp.SetValue($env:CC_NOMBRE) } catch {} }
    $nombre = $vp.Current.Value
}
$ok = Buscar $dlg ([System.Windows.Automation.ControlType]::Button) '*pushButton_Create'
if (-not $ok) { 'SIN_CREAR'; exit }
$ok.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
'CREADO|' + $nombre
'''

_PS_EXPANDIR = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$AE = [System.Windows.Automation.AutomationElement]
$TS = [System.Windows.Automation.TreeScope]
$ids = @(Get-Process Resolve -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
if (-not $ids) { 'NO_RESOLVE'; exit }
$main = $null
foreach ($id in $ids) {
    $c = New-Object System.Windows.Automation.PropertyCondition($AE::ProcessIdProperty, $id)
    foreach ($v in $AE::RootElement.FindAll($TS::Children, $c)) { if ($v.Current.ClassName -like '*UiMainWindow*') { $main = $v } }
}
if (-not $main) { 'SIN_VENTANA'; exit }
$c = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, [System.Windows.Automation.ControlType]::CheckBox)
$b = $null
foreach ($e in $main.FindAll($TS::Descendants, $c)) { if ($e.Current.AutomationId -like '*btnEditExpandViewer') { $b = $e; break } }
if (-not $b) { 'SIN_BOTON'; exit }
$t = $b.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
if ($t.Current.ToggleState -eq 'On') { 'YA_EXPANDIDA'; exit }
$t.Toggle()
Start-Sleep -Milliseconds 500
if ($t.Current.ToggleState -eq 'On') { 'EXPANDIDA' } else { 'NO_CAMBIO' }
'''


def _ps_uia(codigo, env_extra=None, timeout=45):
    """Corre un script de PowerShell con UI Automation (sin ventana) y devuelve su última línea de salida. Nunca lanza."""
    try:
        import base64
        import os
        import subprocess
        cod = base64.b64encode(codigo.encode('utf-16-le')).decode('ascii')
        r = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', cod], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout, env={**os.environ, **(env_extra or {})}, creationflags=0x08000000)      # CREATE_NO_WINDOW
        salida = (r.stdout or '').strip().splitlines()
        return salida[-1].strip() if salida else ('ERROR ' + (r.stderr or '').strip()[:160])
    except Exception as e:
        return 'ERROR ' + str(e)[:160]


def expandir_vista_windows():
    """Windows: deja «Expandir vista» de Resolve ACTIVADA (el visor a toda la altura, la vista vertical): es una casilla de la barra del timeline (btnEditExpandViewer) que se maneja con UI
    Automation, sin mouse y sin foco. Idempotente. Devuelve (ok, texto)."""
    if not sys.platform.startswith('win'):
        return False, tr('Expandir vista solo se automatiza en Windows.')
    res = _ps_uia(_PS_EXPANDIR)
    if res in ('EXPANDIDA', 'YA_EXPANDIDA'):
        return True, tr('Vista expandida (visor a toda la altura).')
    return False, tr('No pude activar «Expandir vista» en Resolve ({r}).', r=res)


PROYECTO_INICIAL = None                     # nombre del proyecto VACÍO que la app creó solo para pasar el Organizador de proyectos (ArmarVideo lo borra al crear el definitivo)


def pasar_organizador_windows(nombre):
    """Windows: si Resolve está en el Organizador de proyectos, pulsa «Crear proyecto» y «Crear» (con `nombre`). Devuelve 'CREADO|<nombre>', 'SIN_ORGANIZADOR' (todavía no está esa
    pantalla) u otro código de fallo. Nunca lanza."""
    global PROYECTO_INICIAL
    res = _ps_uia(_PS_ORGANIZADOR, {'CC_NOMBRE': str(nombre)})
    if res.startswith('CREADO|'):
        PROYECTO_INICIAL = res.split('|', 1)[1].strip() or None
    return res


# --- Mac (v5.4.24, SIN probar en un Mac real): lo mismo que en Windows por «System Events» (accesibilidad). Los AXIdentifier de Resolve son los mismos ids de Qt que ve UI Automation en
# Windows; si en el Mac no existieran, se cae a los nombres de los botones en español e inglés. Si algo falla, solo queda una línea en el Registro y todo sigue como antes.
_AS_BUSCAR = """
on buscar(raiz, fin, nombres)
    tell application "System Events"
        try
            set todos to entire contents of raiz
        on error
            return missing value
        end try
        repeat with e in todos
            try
                set ident to (value of attribute "AXIdentifier" of e) as text
                if ident ends with fin then return e
            end try
        end repeat
        if (count of nombres) > 0 then
            repeat with e in todos
                try
                    if (role of e) is "AXButton" then
                        set n to (name of e) as text
                        if nombres contains n then return e
                    end if
                end try
            end repeat
        end if
    end tell
    return missing value
end buscar
"""

_AS_ORGANIZADOR = _AS_BUSCAR + """
on run argv
    set nuevo to item 1 of argv
    tell application "System Events"
        if not (exists process "DaVinci Resolve") then return "NO_RESOLVE"
        tell process "DaVinci Resolve"
            set boton to missing value
            repeat with w in windows
                set boton to my buscar(w, "projActionBottomFrame.btnAddProject", {"Crear proyecto", "Create Project", "New Project", "Nuevo proyecto"})
                if boton is not missing value then exit repeat
            end repeat
            if boton is missing value then return "SIN_ORGANIZADOR"
            click boton
            delay 1.5
            set campo to missing value
            set crear to missing value
            repeat 12 times
                repeat with w in windows
                    set campo to my buscar(w, "lineEdit_ProjectName", {})
                    set crear to my buscar(w, "pushButton_Create", {"Crear", "Create"})
                    if crear is not missing value then exit repeat
                end repeat
                if crear is not missing value then exit repeat
                delay 0.5
            end repeat
            if crear is missing value then return "SIN_DIALOGO"
            set puesto to ""
            if campo is not missing value then
                try
                    set value of campo to nuevo
                end try
                try
                    set puesto to (value of campo) as text
                end try
            end if
            click crear
            return "CREADO|" & puesto
        end tell
    end tell
end run
"""

_AS_EXPANDIR = _AS_BUSCAR + """
on run argv
    tell application "System Events"
        if not (exists process "DaVinci Resolve") then return "NO_RESOLVE"
        tell process "DaVinci Resolve"
            repeat with w in windows
                set b to my buscar(w, "btnEditExpandViewer", {})
                if b is not missing value then
                    set v to 0
                    try
                        set v to (value of b) as integer
                    end try
                    if v is 1 then return "YA_EXPANDIDA"
                    click b
                    delay 0.5
                    return "EXPANDIDA"
                end if
            end repeat
        end tell
    end tell
    return "SIN_BOTON"
end run
"""


def _osascript(guion, args=(), timeout=60):
    """Corre un AppleScript y devuelve la última línea de salida (o 'ERROR …'). Nunca lanza."""
    try:
        import subprocess
        r = subprocess.run(['osascript', '-e', guion, *[str(a) for a in args]], capture_output=True, text=True, errors='replace', timeout=timeout)
        salida = (r.stdout or '').strip().splitlines()
        if r.returncode != 0:
            err = (r.stderr or '')
            if '-25211' in err or '-1719' in err or 'assistive' in err.lower():
                return 'ERROR sin permiso de Accesibilidad para CineCaptions'
            return 'ERROR ' + err.strip()[-160:]
        return salida[-1].strip() if salida else 'ERROR sin respuesta'
    except Exception as e:
        return 'ERROR ' + str(e)[:160]


def pasar_organizador_mac(nombre):
    """Mac: lo mismo que `pasar_organizador_windows` (Crear proyecto → Crear). Devuelve 'CREADO|<nombre>', 'SIN_ORGANIZADOR' u otro código. Nunca lanza."""
    global PROYECTO_INICIAL
    if sys.platform != 'darwin':
        return 'NO_MAC'
    res = _osascript(_AS_ORGANIZADOR, [nombre], timeout=90)
    if res.startswith('CREADO|'):
        PROYECTO_INICIAL = res.split('|', 1)[1].strip() or str(nombre)
    return res


def expandir_vista_mac():
    """Mac: deja «Expandir vista» activada (casilla btnEditExpandViewer). Recorrer la ventana principal por accesibilidad es lento: se llama desde un hilo aparte. (ok, texto)."""
    if sys.platform != 'darwin':
        return False, tr('Expandir vista solo se automatiza en Windows y Mac.')
    res = _osascript(_AS_EXPANDIR, timeout=120)
    if res in ('EXPANDIDA', 'YA_EXPANDIDA'):
        return True, tr('Vista expandida (visor a toda la altura).')
    return False, tr('No pude activar «Expandir vista» en Resolve ({r}).', r=res)


def abrir_resolve_windows(decir=None, espera_s=240):
    """Windows (Resolve Free, sin MCP que lo abra): si Resolve no está abierto lo lanza y espera a que muestre un proyecto (por defecto reabre el último). Devuelve True si queda
    abierto con un proyecto. `decir(texto)` va contando. Nunca lanza."""
    if not sys.platform.startswith('win'):
        return False
    try:
        import registro
        if _ventana_principal() is not None:
            return True
        hay_proceso = bool(_ventanas_de_resolve())
        if not hay_proceso:
            import os
            import subprocess
            import resolve_bridge as b
            import resolve_mcp
            exe = os.path.join(b._resolve_dir_windows(), 'Resolve.exe')
            if not os.path.isfile(exe):
                registro.aviso(tr('No encuentro Resolve.exe ({r}): ábrelo tú y repite.', r=exe), 'Puente · Windows')
                return False
            if decir:
                decir(tr('Abriendo DaVinci Resolve…'))
            subprocess.Popen([exe], env=resolve_mcp.entorno_para_resolve(), creationflags=0x00000008 | 0x00000200, close_fds=True)         # DETACHED_PROCESS | NEW_PROCESS_GROUP
        inicio = time.time()
        ultimo, intentos = 0.0, 0
        while time.time() - inicio < espera_s:
            if _ventana_principal() is not None:
                time.sleep(8.0)                                        # recién cargado el proyecto, Resolve aún está armando su interfaz y a los pocos segundos se vuelve a poner al frente solo
                return True
            if intentos < 4 and time.time() - ultimo >= 4.0 and _ventanas_de_resolve():
                # v5.4.23: Resolve abre en el «Organizador de proyectos» (sin proyecto no hay Scripts ni consola): se crea uno vacío; el definitivo lo crea ArmarVideo y este se borra
                ultimo = time.time()
                res = pasar_organizador_windows('CineCaptions_nuevo_' + time.strftime('%H%M%S'))
                if res.startswith('CREADO'):
                    intentos += 1
                    ultimo = time.time() + 25                          # el proyecto tarda en abrirse: no volver a pulsar «Crear proyecto» mientras (saldrían dos)
                    registro.info(tr('Resolve estaba en el Organizador de proyectos: {r}', r=res), 'Puente · Windows')
                    if decir:
                        decir(tr('Creando un proyecto en Resolve…'))
                elif res not in ('SIN_ORGANIZADOR', 'SIN_BOTON'):       # (esas dos = la pantalla aún no está lista: se reintenta sin gastar intentos)
                    intentos += 1
                    registro.info(tr('Resolve estaba en el Organizador de proyectos: {r}', r=res), 'Puente · Windows')
            time.sleep(1.5)
        registro.aviso(tr('Resolve no mostró un proyecto abierto en {s} s: ábrelo tú (la pantalla de proyectos no vale) y repite.', s=int(espera_s)), 'Puente · Windows')
    except Exception:
        try:
            import registro
            registro.excepcion(origen='Puente · abrir Resolve')
        except Exception:
            pass
    return False


def lanzar_puente_windows(espera_s=30, forzar=False):
    """Windows (Resolve Free): arranca el Puente SIN tocar el menú, que cambia de idioma y de lugar. La consola de comandos de Resolve (tecla F6) acepta Lua: se abre, se escribe
    `dofile([[…/CineCaptions_Puente.lua]])` y Enter; el Puente sigue vivo aunque la consola se cierre. Solo si Resolve ya está al frente de verdad (si no, las teclas irían a otra
    aplicación) y la ventana principal es la de siempre (no un diálogo). Devuelve True si el Puente quedó latiendo. Con `forzar` lo lanza aunque ya haya uno latiendo (uno de una versión
    anterior que quedó corriendo tras actualizar: el nuevo le pide el relevo) y espera a que lata el de la versión actual. Nunca lanza."""
    if not sys.platform.startswith('win'):
        return False
    try:
        import registro
        import resolve_bridge as b
        if b.puente_activo() and not forzar:
            return True
        version = b.VERSION_PUENTE_ESPERADA if forzar else None
        import instalador_scripts as ins
        ruta = next((c / 'CineCaptions_Puente.lua' for c in ins.carpetas_scripts_resolve() if (c / 'CineCaptions_Puente.lua').is_file()), None)
        if ruta is None:
            registro.aviso(tr('No encuentro CineCaptions_Puente.lua en la carpeta de scripts de Resolve: usa «Reinstalar scripts» en Ajustes.'), 'Puente · Windows')
            return False
        ventanas = _ventanas_de_resolve()
        principal = _ventana_principal(ventanas)
        if principal is None and abrir_resolve_windows():
            ventanas = _ventanas_de_resolve()
            principal = _ventana_principal(ventanas)
        if principal is None:
            registro.aviso(tr('No veo la ventana principal de DaVinci Resolve (¿abierta con un proyecto?): no puedo lanzar el Puente solo.'), 'Puente · Windows')
            return False
        import ctypes
        user32 = ctypes.windll.user32
        consola = next((h for h, t in ventanas if t.strip() == 'Resolve'), None)
        if consola is None:
            if not _al_frente(principal):
                registro.aviso(tr('Resolve no tomó el foco: no pulso teclas para no escribir en otra aplicación.'), 'Puente · Windows')
                return False
            user32.keybd_event(0x75, 0, 0, 0)                       # F6 = Consola de comandos
            time.sleep(0.05)
            user32.keybd_event(0x75, 0, 2, 0)
            for _ in range(24):
                time.sleep(0.25)
                consola = next((h for h, t in _ventanas_de_resolve() if t.strip() == 'Resolve'), None)
                if consola:
                    break
        if consola is None:
            registro.aviso(tr('La consola de comandos de Resolve (F6) no se abrió: no puedo lanzar el Puente solo.'), 'Puente · Windows')
            return False
        if not _al_frente(consola):
            registro.aviso(tr('La consola de Resolve no tomó el foco: no escribo en ella.'), 'Puente · Windows')
            return False
        time.sleep(0.4)
        orden = 'dofile([[' + str(ruta).replace('\\', '/') + ']])'
        escrito = False
        for intento in range(3):                                    # (Unicode puro: con Bloq Mayús activo pynput escribía todo en MAYÚSCULAS y Lua no conoce «DOFILE»)
            if user32.GetForegroundWindow() != consola and not _al_frente(consola, intentos=3):
                break
            if intento:
                _borrar_linea_de_consola(user32, consola)
            if _escribir_texto(orden, hwnd=consola):
                escrito = True
                break
            registro.aviso(tr('El foco salió de la consola de Resolve mientras escribía: paro de teclear y lo reintento ({n}/3).', n=intento + 1), 'Puente · Windows')
            time.sleep(2.0)
        if not escrito:
            registro.aviso(tr('No pude escribir el comando en la consola de Resolve (el foco no se quedaba en ella): no lanzo el Puente solo para no teclear en otra aplicación.'), 'Puente · Windows')
            return False
        time.sleep(0.15)
        inicio = time.time()
        proximo_enter = 0.0
        while time.time() - inicio < espera_s:
            if time.time() - inicio >= proximo_enter:
                # Enter (con el foco otra vez en la consola: si Resolve lo recuperó mientras se escribía, la orden se quedaba escrita sin ejecutar). Si ya se ejecutó, un Enter en un campo
                # vacío no hace nada: se repite cada 9 s hasta que el Puente late.
                if _al_frente(consola, intentos=2) and user32.GetForegroundWindow() == consola:     # (si la consola no tiene el foco, el Enter iría a otra ventana: no se pulsa)
                    user32.keybd_event(0x0D, 0x1C, 0, 0)
                    time.sleep(0.05)
                    user32.keybd_event(0x0D, 0x1C, 2, 0)
                proximo_enter += 9.0
            if b.puente_activo() and (version is None or b.version_del_puente() == version):
                registro.info(tr('El Puente se lanzó solo desde la consola de Resolve.'), 'Puente · Windows')
                try:
                    user32.PostMessageW(consola, 0x0010, 0, 0)       # se cierra la consola: el Puente sigue
                except Exception:
                    pass
                return True
            time.sleep(0.5)
        registro.aviso(tr('Escribí el comando en la consola de Resolve pero el Puente no empezó a latir en {s} s (¿la consola estaba en Python en vez de Lua?).', s=int(espera_s)), 'Puente · Windows')
    except Exception:
        try:
            import registro
            registro.excepcion(origen='Puente · Windows')
        except Exception:
            pass
    return False


def reproducir_desde_inicio(esperar_s=0.5):
    """Al terminar GO: trae Resolve al frente, va al principio del timeline (tecla Inicio) y pulsa «reproducir» (Espacio). Resolve no tiene una llamada de script para reproducir, así que
    se manda la tecla a SU ventana; si no se puede asegurar que Resolve tiene el foco, NO se manda nada (el Espacio iría a otra ventana). Devuelve (ok, texto)."""
    try:
        if sys.platform.startswith('win'):
            import ctypes
            user32 = ctypes.windll.user32
            try:                                                   # v5.4.24: la vista vertical y expandida SIEMPRE (si Resolve la tiene como casilla; sin foco ni mouse)
                import registro
                ok_v, txt_v = expandir_vista_windows()
                (registro.info if ok_v else registro.aviso)(txt_v, 'GO · vista')
            except Exception:
                pass
            _cerrar_consola_de_resolve()                          # (la consola del Puente reaparece sola cada vez que imprime y tapa el timeline: Inicio y Espacio tienen que ir a la ventana principal)
            h = _ventana_principal() or _hwnd_de_resolve()
            if not h:
                return False, tr('No encontré la ventana de DaVinci Resolve para reproducir.')
            if not _al_frente(h):
                return False, tr('Resolve no tomó el foco (otra ventana lo tiene): no reproduzco para no pulsar teclas en otra aplicación.')
            time.sleep(max(0.2, float(esperar_s)))
            if user32.GetForegroundWindow() != h:               # (el foco se pudo perder en esa pausa)
                return False, tr('Resolve no tomó el foco (otra ventana lo tiene): no reproduzco para no pulsar teclas en otra aplicación.')
            for vk in (0x24, 0x20):                                # Inicio, Espacio
                user32.keybd_event(vk, 0, 0, 0)
                time.sleep(0.04)
                user32.keybd_event(vk, 0, 2, 0)
                time.sleep(0.25)
            return True, tr('Reproduciendo el timeline desde el principio.')
        if sys.platform == 'darwin':
            import subprocess
            guion = ('tell application "DaVinci Resolve" to activate\ndelay 0.6\ntell application "System Events"\n'
                     'if (name of first process whose frontmost is true) is not "DaVinci Resolve" then error "sin foco"\n'
                     'key code 115\ndelay 0.25\nkey code 49\nend tell')
            r = subprocess.run(['osascript', '-e', guion], capture_output=True, text=True, errors='replace', timeout=20)
            if r.returncode != 0:
                return False, tr('No pude reproducir en Resolve ({e}). Si macOS lo pide, da permiso de Accesibilidad a CineCaptions.', e=(r.stderr or '').strip()[-100:])

            def _expandir():                                       # v5.4.24: la vista vertical y expandida SIEMPRE (sin probar en un Mac real; si falla solo queda en el Registro)
                try:
                    import registro
                    ok_v, txt_v = expandir_vista_mac()
                    (registro.info if ok_v else registro.aviso)(txt_v, 'GO · vista')
                except Exception:
                    pass
            import threading
            threading.Thread(target=_expandir, daemon=True, name='expandir-vista-mac').start()
            return True, tr('Reproduciendo el timeline desde el principio.')
    except Exception as e:
        return False, tr('No pude reproducir en Resolve ({e}).', e=type(e).__name__)
    return False, tr('Reproducir no está disponible en este sistema.')
