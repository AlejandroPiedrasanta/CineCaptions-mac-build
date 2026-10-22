# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro.py — «Edición PRO»: con un interruptor, GO edita el video en la línea de tiempo de Resolve (motion graphics, la persona
# delante del texto con Magic Mask, velos, marcos, sonidos), además de los captions del tema elegido.
"""
Flujo en GO (lo llama el script principal, nunca rompe GO: si algo falla, el video sale con sus captions como siempre):

    planificar(video, palabras, duracion, cortes, idioma)   (en el hilo de GO, tras transcribir)
        -> edicion_pro_planificador: estilo del video (boda, XV, restaurante, inmobiliaria, detrás de cámara o general), dirección de arte
           con la semilla del video (cada video, distinto), y qué gráfico va en cada momento.
    aplicar(plan, al_estado, offset_frames)                  (tras colocar los captions)
        1. lee el timeline de Resolve (resolución, fps, clips de V1) por el MCP (Studio) o lo que dejó el Puente (Free);
        2. busca a las personas (IA local, edicion_pro_persona) donde un titular va DETRÁS de ellas y afina la posición de los demás
           gráficos para no taparles la cara;
        3. escribe cada gráfico como .ograf (edicion_pro_ograf) a la resolución del timeline, la composición del Magic Mask con los puntos
           de cada persona (Studio) o el recorte ProRes con alfa (Free / sin Magic Mask);
        3b. CAPTIONS DETRÁS DE LA PERSONA (Temas 1–4): lee los bloques que GO acaba de colocar (manifiesto: estilos «guion» y «kinetic»/VIRAL),
           busca la cabeza en cada uno y, en los que se puede (persona grande y quieta, sin otro gráfico encima), sube la pila hasta la coronilla
           para que la cabeza tape la parte de abajo; la persona va recortada en la pista de MÁS ARRIBA (PRO-ENCIMA) solo en esos tramos;
        3c. B-roll de stock (Pexels, con la clave del usuario) en las palabras que nombran cosas, si los Efectos no ponen ya el suyo;
        4. deja ~/DaVinciSubtitles/edicion_pro_plan.json (+ sidecar .lua) y lo coloca DENTRO de Resolve: 2_recursos/edicion_pro/colocar_pro.py
           (Studio, por el MCP) o CineCaptions_EdicionPro.lua (Free, por el Puente).

Preferencias (archivos_seguros, vía ajustes_ui): go_edicion_pro (el interruptor de Inicio y de los Temas 1–4), pro_genero, pro_densidad,
pro_mascara ('auto' | 'magic' | 'ia' | 'no'), pro_sonidos, pro_ia_local, pro_variacion.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import random
import os
import threading
from pathlib import Path

import edicion_pro_ograf as OG
import edicion_pro_planificador as PL

CARPETA = Path.home() / 'DaVinciSubtitles' / 'edicion_pro'
PLAN_JSON = Path.home() / 'DaVinciSubtitles' / 'edicion_pro_plan.json'
DETRAS_CTX = Path.home() / 'DaVinciSubtitles' / 'detras_contexto.json'    # v5.29: lo del último GO que hace falta para «detrás de ti» al momento
OPCIONES_POR_DEFECTO = {'pro_genero': 'auto', 'pro_densidad': 'media', 'pro_mascara': 'auto', 'pro_sonidos': True, 'pro_ia_local': True, 'pro_variacion': 0,
                        'pro_internet': True,          # v5.5.3: fotos de internet con licencia (fuentes_web) para las escenas
                        'pro_motions_completo': False,  # v5.5.8: «Motions completo» (motions_completo.py): un video de motions encima de todo, al final
                        'pro_gancho_intro': True,       # v5.33: «Gancho del inicio» = la intro del primer segundo (intros_gancho)
                        'pro_motions_modo': 'auto', 'pro_motions': [],     # v5.5.7: 'auto' (la IA elige entre todos) o 'elegidos' (solo los de la lista)
                        'pro_sonidos_nivel': 'normal',  # v5.5.7 (página Sonido › Edición PRO): 'suave' | 'normal' | 'fuerte'
                        'pro_sonidos_familias': {'whoosh': True, 'textura': True, 'riser': True},   # movimiento · apariciones · riser + golpe
                        # v5.5.8: Temas 5 y 6 con captions de Fusion EDITABLES (Inspector › texto) en vez de las animaciones de Remotion
                        'pro_captions_editables': True,
                        # v5.5.8: en Studio, el gancho del principio (captions detrás de la persona) con Magic Mask aunque el modo sea «auto»
                        'pro_magic_gancho': True,
                        # v5.5.20: «Captions detrás de ti» (solo Studio): 'suave' | 'media' | 'fuerte' (menú lateral de Proyecto)
                        'pro_detras_intensidad': 'media',
                        # v5.32: dónde va ese caption en un video HORIZONTAL: 'arriba' | 'izquierda' | 'derecha' (en vertical, siempre arriba)
                        'pro_detras_posicion': 'arriba',
                        # v5.5.13: el Tema 1 (neón): lo que el usuario encendió en el menú lateral de Proyecto (pro_lateral_ui); vacío = como la referencia
                        'pro_neon_extras': [],
                        # v5.20: el estilo y los colores de cada función (página Efectos › Edición PRO; estilos_pro.py): {clave: {'v': id, 'c': {hueco: hex}}}
                        'pro_estilos': {},
                        # v5.25: «Emojis animados» (2D Lottie / 3D en movimiento) con lo que se dice: encendido, intensidad y dónde
                        'pro_emojis': True, 'pro_emoji_intensidad': 'media', 'pro_emoji_donde': 'auto'}
NIVEL_SONIDOS_DB = {'suave': -5.0, 'normal': 0.0, 'fuerte': 3.0}
FAMILIA_DE_PISTA = {'PRO-WHOOSH': 'whoosh', 'PRO-TEXTURA': 'textura', 'PRO-RISER': 'riser', 'PRO-HIT': 'riser'}
NOMBRES_GENERO = {'auto': 'Automático', 'general': 'General', 'inmobiliaria': 'Inmobiliaria / venta de casas', 'boda': 'Bodas', 'xv': 'XV años',
                  'restaurante': 'Restaurantes', 'bts': 'Detrás de cámara'}
MANIFIESTO = Path.home() / 'DaVinciSubtitles' / 'subtitles_manifest.json'
AUDIOS = ('.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.aif', '.aiff')   # (lo que GO transcribe sin imagen: el audio del timeline)
DETRAS_CAPTIONS = {'sobria': 0.35, 'media': 0.55, 'espectaculo': 0.8}       # de los bloques de captions donde se puede, cuántos van DETRÁS de la persona
# v5.5.20 (el usuario: «que exista en el menú la intensidad… que se aprecien los captions, que no los tape tanto la Magic Mask»): de los momentos
# que valen, cuántos van detrás (frac); cuánto de la palabra GRANDE de abajo puede tapar la cabeza (tapa, fracción de su alto; tapa_max, del
# cuadro) y cuántos tramos de Magic Mask como mucho (cada uno se rastrea en Resolve: pocos y cortos = Resolve estable)
INTENSIDAD_DETRAS = {'suave': {'frac': 0.25, 'tapa': 0.2, 'tapa_max': 0.035, 'tramos': 3},
                     'media': {'frac': 0.45, 'tapa': 0.3, 'tapa_max': 0.045, 'tramos': 5},
                     'fuerte': {'frac': 0.7, 'tapa': 0.4, 'tapa_max': 0.06, 'tramos': 8}}
NIVELES_DETRAS = ('suave', 'media', 'fuerte')
TRAMO_DETRAS_MAX_S = 12.0                                                    # un recorte de la persona no pasa de esto (el rastreo del Magic Mask va por tramos)
PUNCH_IN = 1.08                                                              # el «punch-in» que alterna en cada salto de V1 (pausas quitadas), como en la skill
MARGEN_RECORTE_S = 0.8
ICONO3D_CADA = {'sobria': 6.0, 'media': 3.5, 'espectaculo': 2.4}            # segundos mínimos entre dos iconos 3D junto a los captions
# v5.25 «Emojis animados»: por intensidad, cada cuánto como mínimo (s), su tamaño (fracción del lado corto del cuadro) y la energía del movimiento
INTENSIDAD_EMOJI = {'suave': {'cada': 7.0, 'tam': 0.13, 'energia': 0.7},
                    'media': {'cada': 4.0, 'tam': 0.16, 'energia': 1.0},
                    'fuerte': {'cada': 2.5, 'tam': 0.20, 'energia': 1.35}}
DONDE_EMOJI = ('auto', 'lado', 'encima', 'cabeza')


# ----------------------------------------------------------------------------------------------------------------------- preferencias
def _prefs():
    try:
        import ajustes_ui
        return ajustes_ui.leer_prefs() or {}
    except Exception:
        return {}


def activado():
    return bool(_prefs().get('go_edicion_pro', False))


TEMAS_PRO = ('Tema5', 'Tema6')            # edicion_pro_tema5.activo: estos temas SON la Edición PRO completa, aunque su interruptor esté apagado


def tema_actual():
    """El tema elegido en el chip «Estilo» de Inicio (preferencia go_pack), o ''."""
    return str(_prefs().get('go_pack') or '')


def en_juego():
    """v5.5.7: ¿la PRO actúa en el próximo GO? Su interruptor, o el tema elegido es el 5 o el 6 (la usan siempre). Las páginas Efectos y Sonido lo
    miran para decir la verdad sobre lo que se aplica (antes, con el Tema 5 y el interruptor apagado, decían «PRO apagada»)."""
    return activado() or tema_actual() in TEMAS_PRO


def neon_elegido():
    """v5.5.13: ¿el tema elegido es el Tema 1 (pack «Kinetic»: su PRO es el estilo neón del kit)?"""
    p = _prefs()
    return str(p.get('go_pack') or p.get('plantilla') or '') == 'Kinetic'


# v5.5.13 (el usuario: «si solo es captions, solo captions; si activo el modo PRO lo hará como el de referencia y si activo cosas del menú
# también lo aplicará; pero el tema por defecto será como la referencia»): con el Tema 1, los interruptores del menú lateral de Proyecto
# (pro_lateral_ui) son SUYOS: 'pro_neon_extras', por defecto ninguno = la referencia exacta; los de los demás temas no cambian.
# v5.33: sin 'gancho': ahora es la intro del primer segundo (intros_gancho) con su propia preferencia (pro_gancho_intro, encendida por defecto
# también en el Tema 1, pedido del usuario); un 'gancho' guardado aquí de antes ya no cuenta (cambiaría la densidad de la PRO del Tema 1)
NEON_EXTRAS = ('pildora', 'broll', 'detras', 'motions_completo', 'escenas', 'kit', 'graficos', 'emoji')   # v5.20: sin 'plantillas' · v5.25: + emoji


def neon_extras(op=None):
    op = opciones_guardadas() if op is None else op
    return [c for c in op.get('pro_neon_extras') or [] if c in NEON_EXTRAS]


def poner_neon_extra(clave, si):
    guardar_opciones({'pro_neon_extras': [c for c in neon_extras() if c != clave] + ([clave] if si else [])})


def opciones_neon(op):
    """Las opciones de la PRO del Tema 1: las del usuario, con lo del menú lateral sacado de SUS interruptores ('_neon_extras')."""
    import pro_lateral_ui as LAT
    ex = set(neon_extras(op))
    op = dict(op)
    antes = str(op.get('pro_mascara') or 'auto')
    op['pro_mascara'] = (antes if antes != 'no' else 'auto') if 'detras' in ex else 'no'
    op['pro_internet'] = 'broll' in ex
    op['pro_motions_completo'] = 'motions_completo' in ex
    ids = [i for c in sorted(ex) for i in LAT.ids_de(c)]
    op['pro_motions_modo'], op['pro_motions'] = 'elegidos', ids or ['-']      # ('-': ninguno; una lista vacía sería «todos»)
    op['_neon_extras'] = sorted(ex)
    return op


def poner_activado(valor):
    import ajustes_ui
    ajustes_ui.guardar_prefs({'go_edicion_pro': bool(valor)})


def opciones_guardadas():
    p = _prefs()
    op = dict(OPCIONES_POR_DEFECTO)
    for k in op:
        if k in p:
            op[k] = p[k]
    return op


def guardar_opciones(cambios):
    import ajustes_ui
    ajustes_ui.guardar_prefs({k: v for k, v in cambios.items() if k in OPCIONES_POR_DEFECTO})


# ----------------------------------------------------------------------------------------------------------------------- plan
def medir(video):
    """(ancho, alto, duración, fps) del archivo, o Nones."""
    try:
        import av
        with av.open(str(video)) as c:
            vs = c.streams.video[0]
            dur = float(c.duration / 1e6) if c.duration else float(vs.duration * vs.time_base) if vs.duration else None
            import rotacion_video as RV                                   # v5.5.8: como lo ve Resolve (videos del celular giran 90°)
            w, h = RV.medidas(vs.codec_context.width, vs.codec_context.height, RV.giro(video))
            return w, h, dur, float(vs.average_rate or 30)
    except Exception:
        return None, None, None, None


def _pesos_ia(palabras, idioma, al_estado=None):
    """Lo importante de cada palabra según la IA local (Qwen, si está instalada). Normalmente ya está en caché (la Asistencia de GO)."""
    try:
        import ia_texto
        if not ia_texto.disponible():
            return None
        if al_estado:
            al_estado('Edición PRO: la IA local elige los titulares…')
        r = ia_texto.analizar(palabras, idioma=idioma)
        return r.get('pesos') or None
    except Exception:
        return None


def planificar(video, palabras, duracion=None, cortes=None, idioma='es', opciones=None, al_estado=None, tema=None, marcas=None):
    """v5.22: `marcas` = posiciones_pro.para_plan (Efectos › «Posición»): van a plan['_marcas'] y, si hacen falta, se arma también el plan
    MÁS DENSO (`_pool`, `_pool_broll`) del que aplicar() saca la pieza de cada marca."""
    op = dict(OPCIONES_POR_DEFECTO, **(opciones or opciones_guardadas()))
    if tema == 'neon':
        op = opciones_neon(op)
    w, h, dur, _fps = medir(video)
    pesos = _pesos_ia(palabras, idioma, al_estado) if op.get('pro_ia_local') else None
    neon_mot = None
    if tema == 'neon':
        try:                                         # v5.5.13: la PRO del Tema 1 = los motions del kit «TEMA 1» (kit_neon_motions), no los gráficos genéricos
            import kit_neon_motions as KM
            neon_mot = KM.escena_motions(palabras, idioma, duracion or dur, cortes=cortes, video=str(video),
                                         usuario=str(op.get('pro_usuario') or '') or None)
        except Exception:
            neon_mot = []
    ocup_neon = [(m['ini'] - 0.3, m['fin'] + 0.3) for m in neon_mot or [] if m.get('capa') != 'iconos']
    densidad = op.get('pro_densidad') or 'media'
    grupos_neon = [c for c in op.get('_neon_extras') or [] if c not in ('detras', 'motions_completo', 'pildora')] if tema == 'neon' else []
    if grupos_neon:                                  # v5.5.17: con el Tema 1 solo quedan los HUECOS entre los motions del kit: más densidad, o no cabía
        densidad = 'espectaculo'                     # nada y lo encendido en el menú «no hacía nada» (probar_pro_lateral.py)
    plan = PL.planificar(palabras, duracion or dur, idioma=idioma, genero=op.get('pro_genero') or 'auto', densidad=densidad,
                         cortes=cortes, vertical=bool(h and w and h > w), pesos=pesos, semilla=int(op.get('pro_variacion') or 0), video=str(video),   # v5.5.3: la RUTA (colores y fotogramas del video para el kit y las escenas)
                         tema=tema, bloqueado=ocup_neon)
    plan['tema'] = tema
    plan['_cortes'] = list(cortes or [])
    if tema == 'neon':
        neonizar(plan)
        plan['kitneon_motions'] = neon_mot
        plan['_palabras'] = [{k: p.get(k) for k in ('word', 'start', 'end')} for p in palabras or [] if p.get('start') is not None]
        extras = [c for c in op['_neon_extras'] if c not in ('detras', 'motions_completo', 'pildora')]
        if extras:                                   # lo encendido en el menú lateral: los motions de siempre, SOLO donde no hay uno del kit
            plan['piezas'] = [p for p in plan.get('piezas') or [] if not any(p['ini'] < b and a < p['fin'] for a, b in ocup_neon)]
        else:
            plan['piezas'] = []
        plan['resumen'] = 'Tema 1 neón: ' + ', '.join(m['fn'] for m in neon_mot)
        if op['_neon_extras']:
            plan['resumen'] += ' + menú: ' + ', '.join(op['_neon_extras'])
    plan['video'] = str(video)
    plan['opciones'] = op
    plan['idioma'] = idioma
    plan['ia_local'] = bool(pesos)
    try:                                             # v5.5.7: solo los motions que el usuario permitió (el seguro final; la IA y las reglas ya no los proponen)
        import motions_catalogo as MC
        plan['piezas'] = MC.filtrar(plan.get('piezas') or [], op)
        if grupos_neon:                              # v5.5.17: cuánto puso cada grupo del menú (al Registro): sin momentos para él, dicho, no «falla»
            import pro_lateral_ui as LAT
            cuenta = {c: sum(1 for p in plan['piezas'] if MC.id_de_pieza(p) in set(LAT.ids_de(c))) for c in grupos_neon}
            plan['_neon_extras_puestos'] = cuenta
            nombres = {o['clave']: o['nombre'] for o in LAT.OPCIONES}
            plan['resumen'] += ' · del menú: ' + ', '.join(f'{nombres.get(c, c)} {n}' if n else f'{nombres.get(c, c)} 0 (este video no tiene un momento '
                                                           'libre para eso)' for c, n in cuenta.items())
    except Exception:
        pass
    plan['broll'] = _broll_de(palabras, duracion or dur, idioma, op, plan) if (tema != 'neon' or op.get('pro_internet')) else []
    if tema == 'neon' and plan['broll']:            # (Tema 1: el B-roll del menú, nunca encima de un motion del kit)
        plan['broll'] = [m for m in plan['broll'] if not any(m['ini'] < b and a < m['ini'] + m['dur'] for a, b in ocup_neon)]
    plan['_marcas'] = {k: v for k, v in (marcas or {}).items() if v and v.get('ts')}
    if any(s in plan['_marcas'] for s in LIBRES):    # v5.22: de dónde sacar la pieza de cada marca (lo que se dice en ESE momento)
        try:
            denso = PL.planificar(palabras, duracion or dur, idioma=idioma, genero=plan.get('genero') or op.get('pro_genero') or 'auto',
                                  densidad='espectaculo', cortes=cortes, vertical=bool(h and w and h > w), pesos=pesos,
                                  semilla=int(op.get('pro_variacion') or 0) + 1, video=str(video), tema=tema)
            plan['_pool'] = denso.get('piezas') or []
        except Exception:
            plan['_pool'] = []
    if 'broll' in plan['_marcas']:
        try:
            import broll
            import efectos_visuales
            ef = efectos_visuales.opciones_guardadas()
            if broll.clave_guardada(ef) and not ef.get('fx_broll'):
                plan['_pool_broll'] = broll.elegir_momentos(palabras, duracion or dur, idioma, 'muchos', margen_ini=0.3, margen_fin=0.5)
        except Exception:
            plan['_pool_broll'] = []
    _referencias(plan)
    soltar_gpu()                                     # v5.5.4: la IA ya eligió: su VRAM, para Resolve (que en ese momento está armando el timeline)
    if plan['broll']:
        plan['resumen'] = plan.get('resumen', '') + f", {len(plan['broll'])} tomas de B-roll"
    return plan


# v5.5.13 — TEMA NEÓN (pedido: «aplica el tema-neon al Tema 1… las opciones de captions y las de la PRO»; kit Escritorio/TEMA 1/graficos/tema-neon.css):
# con el Tema 1 la PRO no saca los colores del video: magenta de acento, lima de segundo acento, texto blanco y paneles morados oscuros
NEON = {'acento': '#FF2DCB', 'acento2': '#D6FF3B', 'colorTexto': '#FFFFFF', 'colorPanel': '#14101E', 'colorBloque': '#2A1258'}


def neonizar(plan):
    """Pone la paleta neón en TODOS los acentos del plan (dirección de arte, kit de la skill, plantillas del catálogo, escenas): un solo paso al final,
    así ninguna pieza se queda con el color del video o el suyo de fábrica. Respeta las que guardan su color a propósito (edicion_pro_kit7.SIN_ACENTO,
    ConceptoK) y los colores que no son de acento (velos negros, textos)."""
    try:
        import edicion_pro_kit7 as K7
        propios = set(K7.SIN_ACENTO) | {'ConceptoK'}
    except Exception:
        propios = {'ConceptoK'}

    def pintar(d):
        if isinstance(d, dict):
            for k, v in list(d.items()):
                if isinstance(v, str) and v.startswith('#') and k in NEON:
                    d[k] = NEON[k]
                elif isinstance(v, (dict, list)):
                    pintar(v)
        elif isinstance(d, list):
            for x in d:
                pintar(x)

    if isinstance(plan.get('direccion'), dict):
        plan['direccion'].update({k: v for k, v in NEON.items() if k != 'acento2'})
    for p in plan.get('piezas') or []:
        if p.get('remotion') in propios:
            continue
        v = p.get('valores')
        if isinstance(v, dict) and p.get('pieza') == 'fondo':           # el fondo de las escenas: el morado del kit (#7A35F5 → #140A28) con brillo magenta
            v.update(color1=NEON['acento'], color2='#140A28', color3='#7A35F5')        # (aurora: color3 → color2 de base, color1 los brillos)
        if isinstance(v, dict):
            pintar(v)
            if p.get('remotion') and str(p['remotion']).endswith('K') and v.get('tema') != 'editorial':
                v.update(acento=NEON['acento'], acento2=NEON['acento2'], tema='neoncc')   # el kit (Kit7.tsx): su paleta «neoncc», magenta + lima
    return plan


def soltar_gpu(voz=True, texto=True):
    """v5.5.4: descarga las IA locales (voz ~6 GB, texto 4–9,5 GB de VRAM) para que Resolve tenga la GPU entera: con ellas cargadas Resolve
    reproducía a tirones, el Magic Mask iba lento y llegó a cerrarse (16 GB no dan para las tres cosas). Se vuelven a cargar solas si hacen falta."""
    try:
        if voz:
            import motor_voz
            motor_voz.liberar()
        if texto:
            import ia_texto
            ia_texto.liberar()
    except Exception:
        pass


def _referencias(plan):
    """v5.5.3: los enlaces para buscar REFERENCIAS del tema del video en Google Imágenes y Pinterest, en el Registro (los abre el usuario, para
    inspirarse: el programa nunca baja de ahí, esas imágenes tienen derechos; las del video salen de bancos con licencia, fuentes_web)."""
    try:
        import urllib.parse
        import registro
        pf = plan.get('perfil') or {}
        tema = ' '.join(str(pf.get('subtema') or pf.get('categoria') or '').split())[:60]
        if not tema:
            return
        q = urllib.parse.quote(tema)
        registro.info(f'Referencias de «{tema}» para inspirarte: Google Imágenes https://www.google.com/search?tbm=isch&q={q} · '
                      f'Pinterest https://www.pinterest.com/search/pins/?q={q}', 'edición PRO')
    except Exception:
        pass


def _broll_de(palabras, duracion, idioma, op, plan):
    """Tomas de stock (Pexels) en las palabras que nombran cosas filmables: solo con la clave del usuario y si los Efectos no ponen ya su B-roll.
    Las que caen sobre una escena de motion graphics se descartan; lo que iba DETRÁS de la persona en una toma pasa delante (la toma la tapa)."""
    try:
        import broll
        import efectos_visuales
        ef = efectos_visuales.opciones_guardadas()
        if ef.get('fx_broll') or not broll.clave_guardada(ef) or not duracion:
            return []
        cuanto = {'sobria': 'pocos', 'media': 'normal', 'espectaculo': 'muchos'}.get(op.get('pro_densidad'), 'normal')
        momentos = broll.elegir_momentos(palabras, duracion, idioma, cuanto)
    except Exception:
        return []
    pantallas = [(p['ini'], p['fin']) for p in plan['piezas'] if p.get('pantalla')]
    momentos = [m for m in momentos if not any(m['ini'] < b + 0.3 and a - 0.3 < m['ini'] + m['dur'] for a, b in pantallas)]
    quitar = set()
    for m in momentos:
        a, b = m['ini'], m['ini'] + m['dur']
        for k, p in enumerate(plan['piezas']):
            if p['ini'] < b and a < p['fin'] and p['capa'] in ('detras', 'velo'):
                if p['capa'] == 'velo':
                    quitar.add(k)
                else:
                    p['capa'], p['persona'] = 'delante', False
    plan['piezas'] = [p for k, p in enumerate(plan['piezas']) if k not in quitar]
    return momentos


# ----------------------------------------------------------------------------------------------------------------------- posiciones (v5.22)
# Efectos › «Posición» (posiciones_pro): el usuario marca en qué segundos va cada efecto. plan['_marcas'] = {sección: {'modo': 'solo'|'suma',
# 'ts': [s del timeline]}} (solo las secciones encendidas). «solo» = únicamente en sus marcas; «suma» = sus marcas y además lo automático.
LIBRES = ('gancho', 'escenas', 'kit', 'graficos')       # la pieza EMPIEZA en la marca (las ligadas a un caption eligen el bloque de ese segundo)


def _seccion(p):
    try:
        import estilos_pro as EST
        return EST.seccion_de_pieza(p)
    except Exception:
        return None


def _marca(plan, seccion):
    m = (plan.get('_marcas') or {}).get(seccion)
    return m if m and m.get('ts') else None


def _avisar_marcas(avisos):
    if avisos:
        try:
            import registro
            registro.aviso('Posiciones de Efectos: ' + ' · '.join(avisos), 'edición pro')
        except Exception:
            pass


def _grande(p):
    return bool(p.get('pantalla')) or (p.get('capa') in ('detras', 'delante', 'fondo') and _seccion(p) != 'pildora')


def _marcas_libres(plan, duracion, pool=(), secciones=LIBRES):
    """Cada marca de una sección «libre» = una pieza de esa sección que empieza en ese segundo: la del plan (o del plan más denso, `pool`)
    más cercana a ese momento, así lo que enseña es de lo que se habla ahí. Con «solo» se van las automáticas de esa sección. Lo grande que
    se pise con una pieza marcada se quita: manda lo que eligió el usuario. Devuelve las piezas puestas."""
    avisos, puestas = [], []
    for sec in secciones:
        m = _marca(plan, sec)
        if not m:
            continue
        propias = [p for p in plan.get('piezas') or [] if _seccion(p) == sec]
        cands = propias + [p for p in pool or [] if _seccion(p) == sec]
        if m.get('modo') != 'suma':
            plan['piezas'] = [p for p in plan.get('piezas') or [] if _seccion(p) != sec]
        usadas = set()
        for t in m['ts']:
            if m.get('modo') == 'suma' and any(abs(float(p['ini']) - t) < 1.0 for p in propias):
                continue                                                  # (ya había una suya ahí)
            if not cands:
                avisos.append(f'«{sec}» en {t:.1f} s: este video no tiene nada de esa sección')
                continue
            base = min(cands, key=lambda p: (id(p) in usadas, abs(float(p['ini']) - t)))
            usadas.add(id(base))
            dur = max(0.8, float(base['fin']) - float(base['ini']))
            a = max(0.05, min(float(t), float(duracion or (t + dur + 0.1)) - dur - 0.05))
            nueva = copy.deepcopy(base)
            nueva.update(ini=round(a, 3), fin=round(a + dur, 3), _marca=True,
                         motivo=f'posición elegida ({t:.1f} s) · ' + str(base.get('motivo') or ''))
            if _grande(nueva):
                plan['piezas'] = [p for p in plan.get('piezas') or []
                                  if p.get('_marca') or not (_grande(p) and p['ini'] < nueva['fin'] + 0.1 and nueva['ini'] - 0.1 < p['fin'])]
            plan['piezas'] = list(plan.get('piezas') or []) + [nueva]
            puestas.append(nueva)
    _avisar_marcas(avisos)
    return puestas


def _ligadas(piezas, m, nombre):
    """De las piezas ligadas a un caption (la píldora), la que suena en cada marca (o la más cercana, a 2 s como mucho)."""
    elegidas, avisos = [], []
    for t in m['ts']:
        dentro = [p for p in piezas if p['ini'] - 0.15 <= t <= p['fin'] + 0.15]
        if not dentro and piezas:
            q = min(piezas, key=lambda p: min(abs(p['ini'] - t), abs(p['fin'] - t)))
            dentro = [q] if min(abs(q['ini'] - t), abs(q['fin'] - t)) <= 2.0 else []
        if not dentro:
            avisos.append(f'«{nombre}» en {t:.1f} s: ahí no hay un caption con algo que poner debajo')
            continue
        if all(dentro[0] is not e for e in elegidas):
            elegidas.append(dentro[0])
    _avisar_marcas(avisos)
    return elegidas


def _marcas_broll(plan, duracion):
    """El B-roll en las marcas: la toma (palabra y consulta) más cercana a cada segundo, empezando ahí. Lo que iba DETRÁS de la persona en
    ese tramo pasa delante (la toma la tapa) y su velo sobra, como en _broll_de."""
    m = _marca(plan, 'broll')
    if not m:
        return
    pool = list(plan.get('broll') or []) + list(plan.get('_pool_broll') or [])
    if not pool:
        _avisar_marcas(['«B-roll» necesita la clave de Pexels (Efectos) y alguna palabra que se pueda filmar en este video'])
        return
    lista = [] if m.get('modo') != 'suma' else list(plan.get('broll') or [])
    usadas = set()
    for t in m['ts']:
        if any(abs(float(x['ini']) - t) < 1.0 for x in lista):
            continue
        base = min(pool, key=lambda x: (id(x) in usadas, abs(float(x['ini']) - t)))
        usadas.add(id(base))
        dur = float(base.get('dur') or 2.5)
        nueva = dict(base, ini=round(max(0.05, min(float(t), float(duracion or t + dur) - dur - 0.05)), 3), _marca=True)
        lista.append(nueva)
        a, b = nueva['ini'], nueva['ini'] + dur
        quitar = set()
        for k, p in enumerate(plan.get('piezas') or []):
            if p['ini'] < b and a < p['fin'] and p.get('capa') in ('detras', 'velo'):
                if p['capa'] == 'velo':
                    quitar.add(k)
                else:
                    p['capa'], p['persona'] = 'delante', False
        plan['piezas'] = [p for k, p in enumerate(plan.get('piezas') or []) if k not in quitar]
    plan['broll'] = sorted(lista, key=lambda x: float(x['ini']))


def _tramos_motions(mc, m, dur):
    """«Motions completo» con «solo mis marcas»: los tramos (s) del video de motions que se ven = las escenas que suenan en cada marca."""
    try:
        escenas = json.loads(Path(mc).with_suffix('.json').read_text(encoding='utf-8')).get('escenas') or []
    except Exception:
        escenas = []
    tramos = []
    for t in m['ts']:
        e = next((e for e in escenas if float(e['ini']) - 0.05 <= t < float(e['fin'])), None)
        a, b = (float(e['ini']), float(e['fin'])) if e else (max(0.0, t - 0.2), min(float(dur), t + 4.0))
        tramos.append([max(0.0, a), min(float(dur), b)])
    tramos.sort()
    unidos = []
    for a, b in tramos:
        if unidos and a <= unidos[-1][1] + 0.05:
            unidos[-1][1] = max(unidos[-1][1], b)
        elif b - a > 0.2:
            unidos.append([a, b])
    return unidos


# ----------------------------------------------------------------------------------------------------------------------- Resolve
_INFO = r'''
tl = project.GetCurrentTimeline() if project else None
info = {'producto': resolve.GetProductName(), 'version': resolve.GetVersionString()}
if tl:
    info.update({'nombre': tl.GetName(), 'fps': float(tl.GetSetting('timelineFrameRate') or 30), 'ancho': int(tl.GetSetting('timelineResolutionWidth') or 1920),
                 'alto': int(tl.GetSetting('timelineResolutionHeight') or 1080), 'inicio': tl.GetStartFrame(), 'v1': []})
    for it in tl.GetItemListInTrack('video', 1) or []:
        mpi = it.GetMediaPoolItem()
        ruta = mpi.GetClipProperty('File Path') if mpi else ''
        try:
            fps_clip = float(mpi.GetClipProperty('FPS') or info['fps']) if mpi else info['fps']
        except Exception:
            fps_clip = info['fps']
        c = {'ini': it.GetStart(), 'fin': it.GetEnd(), 'izq': it.GetLeftOffset(), 'ruta': ruta, 'fps': fps_clip,
             'res': (mpi.GetClipProperty('Resolution') or '') if mpi else '', 'fx': 'CineCaptions FX' in (it.GetFusionCompNameList() or [])}
        for k, n in (('zx', 'ZoomX'), ('zy', 'ZoomY'), ('pan', 'Pan'), ('tilt', 'Tilt')):
            try:
                c[k] = float(it.GetProperty(n))
            except Exception:
                c[k] = 1.0 if k in ('zx', 'zy') else 0.0
        info['v1'].append(c)
    info['sfx'] = []
    for i in range(1, int(tl.GetTrackCount('audio') or 0) + 1):
        n = str(tl.GetTrackName('audio', i) or '')
        if n.upper().startswith('SFX') or n == 'FX-SONIDO':
            info['sfx'] += [x.GetStart() for x in tl.GetItemListInTrack('audio', i) or []]
    info['ocupado'] = []
    for i in range(1, int(tl.GetTrackCount('video') or 0) + 1):
        if tl.GetTrackName('video', i) == 'FX-BROLL':
            info['ocupado'] += [[x.GetStart(), x.GetEnd()] for x in tl.GetItemListInTrack('video', i) or []]
result = info
'''


def _info_timeline():
    """{'fps', 'ancho', 'alto', 'inicio', 'v1': [...], 'producto', 'via': 'mcp'|'puente'} o None."""
    try:
        import resolve_mcp
        if resolve_mcp.ruta_exe() is not None:
            ok, r, _e = resolve_mcp.script(_INFO, timeout=40)
            if ok and isinstance(r, dict) and r.get('fps'):
                r['via'] = 'mcp'
                return r
    except Exception:
        pass
    try:                                     # Free: lo que dejó el Puente al armar el timeline
        import resolve_bridge
        d = resolve_bridge.video_detectado() or {}
        if d.get('fps'):
            v1 = d.get('v1') or []
            return {'fps': float(d['fps']), 'ancho': int(d.get('ancho') or 1920), 'alto': int(d.get('alto') or 1080), 'inicio': int(d.get('inicio') or 0),
                    'v1': v1 if isinstance(v1, list) else [], 'producto': 'DaVinci Resolve', 'via': 'puente'}
    except Exception:
        pass
    return None


def _fuente_de(info, video, t):
    """(archivo, segundo del archivo, clip de V1) del instante t (segundos desde el inicio de lo transcrito)."""
    fps = float(info['fps'])
    f = int(info.get('base', info['inicio'])) + int(round(t * fps))
    for c in info.get('v1') or []:
        if c['ini'] <= f < c['fin'] and c.get('ruta'):
            fps_c = float(c.get('fps') or fps)
            return c['ruta'], int(c['izq']) / fps_c + (f - c['ini']) / fps, c          # el desfase izquierdo va en fotogramas del CLIP
    return str(video), t, None


def _a_timeline(det, clip, W, H):
    """La detección (fracciones de la FUENTE) en fracciones del TIMELINE para ese clip de V1: GO lo pone «ajustado» (un horizontal en un timeline
    vertical queda con bandas), y encima van su zoom (el punch-in), Pan y Tilt. Los puntos del Magic Mask NO pasan por aquí (van en la fuente)."""
    if not det or not det.get('personas') or not clip:
        return det
    try:
        w, h = (int(x) for x in str(clip.get('res') or '').lower().replace(' ', '').split('x')[:2])
    except (TypeError, ValueError):
        w, h = W, H
    if w <= 0 or h <= 0:
        w, h = W, H
    s = min(W / float(w), H / float(h))
    sx, sy = w * s / W, h * s / H
    zx, zy = float(clip.get('zx') or 1.0), float(clip.get('zy') or 1.0)
    pan, tilt = float(clip.get('pan') or 0.0), float(clip.get('tilt') or 0.0)

    def fx(x):
        return 0.5 + (0.5 - sx / 2 + x * sx - 0.5) * zx + pan / W

    def fy(y):
        return 0.5 + (0.5 - sy / 2 + y * sy - 0.5) * zy - tilt / H
    ps = []
    for q in det['personas']:
        x0, y0, x1, y1 = q['bbox']
        n = dict(q, bbox=(fx(x0), fy(y0), fx(x1), fy(y1)), puntos=[(fx(x), fy(y)) for x, y in q.get('puntos') or []])
        if q.get('cabeza'):
            n['cabeza'] = {'alto': q['cabeza'].get('alto', 0) * sy * zy, 'ancho': q['cabeza'].get('ancho', 0) * sx * zx}
        ps.append(n)
    return {'personas': ps, 'arriba': min(q['bbox'][1] for q in ps), 'abajo': max(q['bbox'][3] for q in ps),
            'izq': min(q['bbox'][0] for q in ps), 'der': max(q['bbox'][2] for q in ps)}


def _y_en_fuente(y_tl, clip, W, H):
    """v5.5.20: la inversa de _a_timeline para una ALTURA: (fracción del alto de la fuente del clip de V1, alto de la fuente en píxeles)."""
    if not clip:
        return y_tl, float(H)
    try:
        w, h = (int(x) for x in str(clip.get('res') or '').lower().replace(' ', '').split('x')[:2])
    except (TypeError, ValueError):
        w, h = W, H
    if w <= 0 or h <= 0:
        w, h = W, H
    s = min(W / float(w), H / float(h))
    sy = h * s / H
    zy = float(clip.get('zy') or 1.0)
    tilt = float(clip.get('tilt') or 0.0)
    return ((y_tl - 0.5 + tilt / H) / zy + sy / 2.0) / sy, float(h)


ALTO_PIEZA = {'cifra': 0.17, 'rotulo': 0.12, 'lista': 0.25, 'etiqueta': 0.08, 'cta': 0.30, 'icono': 0.29, 'titular': 0.15, 'nombres': 0.17}
MARGEN_CARA = 0.02                       # aire entre la cara y cualquier cosa (fracción del alto)


def _caras(det):
    """Las cajas de las CARAS (fracciones del timeline, y desde arriba): de la coronilla a la barbilla y del ancho de la cabeza, con margen.
    Regla del usuario: NADA las tapa (ni gráficos, ni emojis, ni captions)."""
    out = []
    for q in (det or {}).get('personas') or []:
        x0, y0, x1, y1 = q['bbox']
        cab = (q.get('cabeza') or {}).get('alto') or 0.2 * (y1 - y0)
        ancho = (q.get('cabeza') or {}).get('ancho') or min(x1 - x0, cab * 0.9)
        cx = q['puntos'][0][0] if q.get('puntos') else (x0 + x1) / 2.0
        out.append((max(0.0, cx - 0.62 * ancho), max(0.0, y0 - 0.01), min(1.0, cx + 0.62 * ancho), min(1.0, y0 + 1.12 * cab)))
    return out


def _fuera_de_la_cara(y, medio, caras, x0=0.0, x1=1.0):
    """El centro y (fracción) más cercano a `y` para algo de media altura `medio` (y ancho [x0, x1]) que no pise ninguna cara, o None si no cabe."""
    malas = [c for c in caras if c[0] < x1 and x0 < c[2]]
    if not malas:
        return y

    def libre(yy):
        return 0.04 + medio <= yy <= 0.96 - medio and all(yy + medio + MARGEN_CARA <= c[1] or yy - medio - MARGEN_CARA >= c[3] for c in malas)
    if libre(y):
        return y
    opciones = [c[1] - MARGEN_CARA - medio for c in malas] + [c[3] + MARGEN_CARA + medio for c in malas]
    opciones = [o for o in opciones if libre(o)]
    return min(opciones, key=lambda o: abs(o - y)) if opciones else None


MARGEN_EMOJI = 0.07                      # el emoji de un caption de los Temas 1–4 va justo encima o debajo de su pila (fracción del alto)


def _caja_vertical(pieza):
    """(arriba, abajo) en fracción del alto de una pieza ya colocada (su centro `y` y su alto por la escala), o None si no se sabe."""
    v = pieza.get('valores') or {}
    alto = pieza.get('alto') or ALTO_PIEZA.get(pieza['pieza'])
    if not alto and pieza.get('remotion'):
        import edicion_pro_catalogo as PC
        alto = PC.ALTO.get(pieza['remotion'])
    if not alto or pieza.get('pantalla') or v.get('y') is None:
        return None
    y, medio = float(v['y']) / 100.0, float(alto) * float(v.get('escala', 1) or 1) / 2.0
    return (max(0.0, y - medio), min(1.0, y + medio))


def _obstaculos(pieza, bloques_cap, puestos):
    """v5.5.2 (regla oficial): las cajas que una pieza de delante NO puede pisar en su tramo: los captions de los Temas 1–4 (con el sitio de su emoji)
    y lo ya colocado delante a la vez (los captions de la PRO de los Temas 5/6 y los demás gráficos). Cajas a todo el ancho: (x0, y0, x1, y1)."""
    a, b = pieza['ini'], pieza['fin']
    out = [(0.0, max(0.0, c['arriba'] - MARGEN_EMOJI), 1.0, min(1.0, c['abajo'] + MARGEN_EMOJI)) for c in bloques_cap or [] if c['ini'] < b and a < c['fin']]
    out += [(0.0, max(0.0, y0 - 0.01), 1.0, min(1.0, y1 + 0.01)) for (i, f, y0, y1) in puestos if i < b and a < f]
    return out


def _ajustar_posiciones(pieza, det, vertical, extra=()):
    """Coloca cada gráfico SIN TAPAR NINGUNA CARA: los de delante, encima o debajo de la cara (o a un lado en horizontal, o más pequeños); el titular
    «detrás» un poco por debajo de la coronilla (la cabeza lo tapa a él, no al revés); la infografía de una escena con «fondo sustituido»,
    detrás de la persona y encima de su cabeza (si no cabe, la escena va a pantalla completa); la órbita, con la mitad de delante por el pecho.
    `det` ya en fracciones del timeline. `extra`: otras cajas que tampoco se pisan (v5.5.2: los captions, para las piezas del kit de la skill)."""
    v = pieza['valores']
    if not det or not det.get('personas'):
        if not extra or not vertical:
            return
        det = {'personas': [], 'arriba': 1.0}
    arriba = float(det['arriba']) * 100.0
    caras = _caras(det) + [tuple(c) for c in extra]
    if pieza['pieza'] == 'orbita':                                    # centrada en el cuello: atrás pasa por detrás de la cabeza, delante por el pecho
        y0, cab_x, _alto, cab = _cabeza(det)
        ancho = max((q.get('cabeza') or {}).get('ancho', 0) for q in det['personas']) or cab * 0.6
        k = max(0.85, min(1.3, cab / 0.12))
        v['escala'] = round(k, 2)
        tres_d = len([x for x in str(v.get('imagenes') or '').split(',') if x.strip()]) >= 3
        medio = (99.0 if tres_d else 58.0) * k / (1920.0 if vertical else 1080.0)   # media altura del icono de delante (px de U=1 → fracción del alto)
        cy = y0 + 0.85 * cab
        ry = (y0 + 1.12 * cab + MARGEN_CARA) + medio - cy              # lo de delante pasa ENTERO por debajo de la barbilla
        v['x'], v['y'] = round(cab_x * 100, 2), round(cy * 100, 2)
        v['rx'] = round(max(18.0, min(42.0, 240.0 * ancho)), 2)
        v['ry'] = round(max(2.0, min(18.0, ry * 100)), 2)
        v['inclinacion'] = round(max(-5.0, min(5.0, float(v.get('inclinacion', 0)))), 1)
        return
    if pieza['capa'] == 'detras' and pieza['pieza'] in ('icono', 'cifra', 'lista'):
        if vertical:
            if arriba < 24.0:                                         # primer plano: no hay sitio encima de la cabeza
                pieza['forzar_pantalla'] = True
                return
            v['y'] = round(max(13.0, arriba - 11.0), 1)
            v['escala'] = round(min(float(v.get('escala', 1)), 0.78 if arriba < 32 else 0.92), 2)
        else:
            centro = (float(det['izq']) + float(det['der'])) / 2.0
            v['x'], v['y'] = (27 if centro >= 0.5 else 73), 45
            v['escala'] = round(min(float(v.get('escala', 1)), 0.85), 2)
        return
    if pieza['capa'] == 'detras':
        v['y'] = round(min(48.0, max(15.0, arriba + 2.5)), 1)          # el centro del titular un poco por debajo de la coronilla: la cabeza tapa su parte de abajo
        return
    alto = pieza.get('alto') or ALTO_PIEZA.get(pieza['pieza'])         # (las tarjetas del Tema 5 traen su alto: depende de lo que enseñan)
    if pieza.get('remotion') and not alto:                            # plantillas Remotion: su alto está en el catálogo
        import edicion_pro_catalogo as PC
        alto = PC.ALTO.get(pieza['remotion'])
    if not alto or pieza.get('pantalla'):
        return
    if not vertical:                                                  # horizontal: al lado contrario de la persona
        centro = (float(det['izq']) + float(det['der'])) / 2.0
        if pieza['pieza'] not in ('etiqueta',):
            v['x'] = 26 if centro >= 0.5 else 74
            v['escala'] = round(min(float(v.get('escala', 1)), 0.85), 2)
        x = float(v.get('x', 50)) / 100.0
        medio_x = 0.22 * float(v.get('escala', 1))
        y = _fuera_de_la_cara(float(v.get('y', 50)) / 100.0, alto * float(v.get('escala', 1)) / 2.0, caras, x - medio_x, x + medio_x)
        if y is not None:
            v['y'] = round(y * 100, 1)
        return
    for k in (1.0, 0.85, 0.7, 0.58):                                  # vertical: encima o debajo de la cara; si no cabe, más pequeño
        esc = round(min(float(pieza['_valores0'].get('escala', 1)) if pieza.get('_valores0') else float(v.get('escala', 1)), 1.0) * k, 2)
        y = _fuera_de_la_cara(float(v.get('y', 50)) / 100.0, alto * esc / 2.0, caras)
        if y is not None:
            v['y'], v['escala'] = round(y * 100, 1), esc
            return
    pieza['quitar'] = True                                            # no cabe en ningún sitio sin tapar la cara: mejor sin él


def _fx_persona(efecto, fuente):
    """v5.20 (página Efectos › Captions detrás de ti, estilos_pro.EFECTOS_PERSONA): los nodos de Fusion que le ponen a la silueta recortada una
    sombra, orillas de color o un resplandor. SOLO herramientas y entradas sacadas de las plantillas de Blackmagic (Templates.drfx de Resolve 21:
    ErodeDilate XAmount, BrightnessContrast Gain/Brightness/PreDividePostMultiply/Alpha, ColorGain Gain*, Blur XBlurSize/Filter, Transform Center,
    Merge Background/Foreground): un nombre adivinado tumbó Resolve una vez. La silueta de color = la del recorte (ensanchada) con el RGB a 1
    (pre-dividido y vuelto a multiplicar: queda en su alfa) y teñida con ColorGain; todo sale del mismo MediaIn (misma resolución).
    Devuelve (texto de las herramientas, nombre de la última)."""
    herramientas, n = [], [0]

    def nombre(base):
        n[0] += 1
        return f'CCFx{base}{n[0]}'

    def num(k, v):
        return f'{k} = Input {{ Value = {float(v):.6g}, }},'

    def enlace(entrada, op):
        return f'{entrada} = Input {{ SourceOp = "{op}", Source = "Output", }},'

    def herr(tipo, nom, entradas):
        herramientas.append('\t\t%s = %s {\n\t\t\tInputs = {\n%s\t\t\t},\n\t\t},\n' % (nom, tipo, ''.join('\t\t\t\t%s\n' % e for e in entradas)))
        return nom

    def rgb(color):
        c = str(color or '#FFFFFF').lstrip('#')[:6].ljust(6, 'F')
        return [int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]

    def silueta(origen, color, ancho=0.0):                     # color None = negra
        src = origen
        if ancho > 0:
            src = herr('ErodeDilate', nombre('Ensancha'), [num('XAmount', ancho), enlace('Input', src)])
        plano = herr('BrightnessContrast', nombre('Plano'), [num('Gain', 0), num('Brightness', 1 if color else 0), num('PreDividePostMultiply', 1),
                                                             num('Alpha', 0), enlace('Input', src)])
        r, g, b = rgb(color) if color else (1.0, 1.0, 1.0)
        if not color or min(r, g, b) > 0.995:
            return plano
        return herr('ColorGain', nombre('Tinte'), [num('LockRGB', 0), num('GainRed', r), num('GainGreen', g), num('GainBlue', b), enlace('Input', plano)])

    def junta(fondo, frente):
        return herr('Merge', nombre('Junta'), [enlace('Background', fondo), enlace('Foreground', frente)])

    def difumina(origen, blur):
        return herr('Blur', nombre('Difumina'), [num('XBlurSize', max(0.5, blur * 1000.0)), 'Filter = Input { Value = FuID { "Gaussian" }, },',
                                                 enlace('Input', origen)])

    # Probado en Resolve 21.1.1 (2026-10-19): el MagicMask NO premultiplica (fuera de la persona el RGB sigue siendo la imagen con alfa 0) y un
    # Merge lo SUMA: la orilla y el resplandor se veían (suman luz) pero la sombra no (negro + imagen = imagen). AlphaMultiply (de las plantillas
    # de Blackmagic) lo premultiplica antes de nada.
    fuente = herr('AlphaMultiply', nombre('Premultiplica'), [enlace('Input', fuente)])
    debajo = []                                                # las capas bajo la persona, de abajo arriba
    if efecto.get('brillo'):                                   # el resplandor: la silueta de color, difuminada
        b = efecto['brillo']
        brillo = difumina(silueta(fuente, b.get('color') or '#FFFFFF', float(b.get('ancho') or 0.0)), float(b.get('blur') or 0.02))
        if float(b.get('fuerza') or 1.0) != 1.0:
            brillo = herr('BrightnessContrast', nombre('Fuerza'), [num('Gain', float(b['fuerza'])), num('Alpha', 1), enlace('Input', brillo)])
        debajo.append(brillo)
    for o in sorted(efecto.get('orillas') or [], key=lambda o: -float(o.get('ancho') or 0)):     # de la más ancha (fuera) a la más fina
        debajo.append(silueta(fuente, o.get('color') or '#FFFFFF', float(o.get('ancho') or 0.004)))
    capa = None
    for c in debajo:
        capa = c if capa is None else junta(capa, c)
    capa = junta(capa, fuente) if capa else fuente             # la persona, encima de todo
    if efecto.get('sombra'):                                   # la sombra de todo lo anterior, difuminada y desplazada
        sh = efecto['sombra']
        negra = herr('ColorGain', nombre('Opacidad'), [num('GainAlpha', float(sh.get('opacidad') or 0.6)), enlace('Input', silueta(capa, None))])
        movida = herr('Transform', nombre('Desplaza'), ['Center = Input { Value = { %.5f, %.5f }, },' % (0.5 + float(sh.get('dx') or 0), 0.5 + float(sh.get('dy') or 0)),
                                                        enlace('Input', difumina(negra, float(sh.get('blur') or 0.01)))])
        capa = junta(movida, capa)
    return ''.join(herramientas), capa


def _comp_magic(puntos, ref, ruta, herramienta='CCProMagic', efecto=None):
    """La composición del Magic Mask (MediaIn → MagicMask → MediaOut) con los puntos de cada persona en el fotograma `ref` del clip.
    `herramienta`: el nombre del MagicMask, DISTINTO en cada clip: así colocar_pro sabe que la página Fusion abrió la composición de ESE clip
    (si se queda con la del anterior, ya rastreada, el rastreo se daba por bueno y el clip quedaba sin recortar, tapando los captions).
    v5.20: `efecto` (estilos_pro.efecto_persona) = sombra / orillas / resplandor de la silueta, entre el MagicMask y el MediaOut."""
    fx, ultimo = _fx_persona(efecto, herramienta) if efecto else ('', herramienta)
    lineas = ',\n'.join('\t\t\t\t\t\t\t{ %.5f, %.5f }' % (x, y) for x, y in puntos)
    texto = '''Composition {
	CurrentTime = 0,
	Tools = ordered() {
		MediaIn1 = MediaIn { ViewInfo = OperatorInfo { Pos = { 0, 50 } }, },
		%(h)s = MagicMask {
			Inputs = {
				Mode = Input { Value = FuID { "Better" }, },
				CorrectEdges = Input { Value = 1, },
				MatteBlur = Input { Value = 0.4, },
				ReferenceTime = Input { Value = %(ref)d, Disabled = true, },
				ProcessedFramesLow = Input { Value = %(ref)d, Disabled = true, },
				ProcessedFramesHigh = Input { Value = %(ref)d, Disabled = true, },
				UseLegacyMagicMask = Input { Value = 0, Disabled = true, },
				IsInitialNotify = Input { Value = 0, },
				IsRefineFrame = Input { Value = 1, },
				Strokes = Input { SourceOp = "%(h)sStrokes", Source = "Value", },
				Input = Input { SourceOp = "MediaIn1", Source = "Output", },
			},
			ViewInfo = OperatorInfo { Pos = { 110, 50 } },
		},
		%(h)sStrokes = BezierSpline {
			SplineColor = { Red = 242, Green = 186, Blue = 59 },
			NameSet = true,
			KeyFrames = {
				[%(ref)d] = { 0, Flags = { Linear = true, LockedY = true }, Value = MagicMaskStrokes {
						PosStrokes = {
%(lineas)s
						}
					} }
			}
		},
%(fx)s		MediaOut1 = MediaOut {
			Inputs = {
				Index = Input { Value = "0", },
				Input = Input { SourceOp = "%(u)s", Source = "Output", },
			},
			ViewInfo = OperatorInfo { Pos = { 220, 50 } },
		},
	},
}
''' % {'ref': int(ref), 'lineas': lineas, 'h': herramienta, 'fx': fx, 'u': ultimo}
    Path(ruta).write_text(texto, encoding='utf-8')
    return Path(ruta)


def intensidad_detras(op=None):
    """v5.5.20: la intensidad de «Captions detrás de ti» ('suave' | 'media' | 'fuerte')."""
    op = opciones_guardadas() if op is None else op
    v = str(op.get('pro_detras_intensidad') or 'media')
    return v if v in INTENSIDAD_DETRAS else 'media'


POSICIONES_DETRAS = ('arriba', 'izquierda', 'derecha')


def posicion_detras(op=None, W=None, H=None):
    """v5.32 (el usuario: «si es vertical la posición es arriba y si es horizontal que aparezca la posición»): dónde va el caption detrás de
    la persona. Con el cuadro (W, H) vertical, siempre 'arriba'; en horizontal, lo elegido en Efectos › Posición ('pro_detras_posicion')."""
    if W is not None and H is not None and float(W) <= float(H):
        return 'arriba'
    op = opciones_guardadas() if op is None else op
    v = str(op.get('pro_detras_posicion') or 'arriba')
    return v if v in POSICIONES_DETRAS else 'arriba'


def desplazar_lado(lado, arriba, abajo, x0, x1, coronilla, cab_x, cab, W, H):
    """v5.32 (horizontal, «Izquierda» / «Derecha»): cuánto se mueve la pila (dx, dy; fracciones del cuadro, x desde la izquierda, y desde
    ARRIBA) para quedar a ESE lado de la persona, a la altura de su cabeza, con la cabeza tapando un poco su borde (el 30 % de la cabeza
    entra en el texto). None si no cabe: ni a la altura de la cabeza, o el texto es tan ancho que, pegado al borde del cuadro, la cabeza
    taparía más que su borde (medido con un caption ancho del Tema 1 en 16:9: le tapaba media palabra)."""
    hw = 0.75 * float(cab) * float(H) / max(1.0, float(W))           # (el ancho de la cabeza, fracción del ancho)
    dy = (coronilla + 0.5 * cab) - (arriba + abajo) / 2.0
    dy = max(0.06 - arriba, min(0.94 - abajo, dy))
    if arriba + dy > coronilla + cab or abajo + dy < coronilla:
        return None
    if lado == 'izquierda':
        dx = max((cab_x - 0.2 * hw) - x1, 0.03 - x0)
        tapado = (x1 + dx) - (cab_x - 0.5 * hw)
    else:
        dx = min((cab_x + 0.2 * hw) - x0, 0.97 - x1)
        tapado = (cab_x + 0.5 * hw) - (x0 + dx)
    if tapado < 0.0 or tapado > 0.3 * hw + 0.025:
        return None
    return dx, dy


def intensidad_emoji(op=None):
    """v5.25: la intensidad de «Emojis animados» ('suave' | 'media' | 'fuerte')."""
    op = opciones_guardadas() if op is None else op
    v = str(op.get('pro_emoji_intensidad') or 'media')
    return v if v in INTENSIDAD_EMOJI else 'media'


def donde_emoji(op=None):
    op = opciones_guardadas() if op is None else op
    v = str(op.get('pro_emoji_donde') or 'auto')
    return v if v in DONDE_EMOJI else 'auto'


def detras_disponible():
    """v5.5.20 (el usuario: «que sirva para DaVinci Resolve Studio; en la versión Free no aparece la opción»): «Captions detrás de ti» va SOLO
    con Studio (Magic Mask); ni en Free ni en el video MP4 sin Resolve. Barato y sin preguntar a Resolve (se llama desde la interfaz): lo último
    que se supo de la edición instalada (instalador_scripts la detecta y la guarda)."""
    if os.environ.get('CINECAPTIONS_SIN_RESOLVE') == '1':
        return False
    try:
        import ajustes_ui
        if ajustes_ui.leer_prefs().get('go_salida_mp4'):
            return False
    except Exception:
        pass
    try:
        import instalador_scripts as ins
        return (ins._CACHE_EDICION.get('valor') or ins._edicion_guardada()) == 'studio'
    except Exception:
        return False


def _bloques_captions():
    """Los bloques de captions de los Temas 1–4 que GO acaba de colocar (estilos «guion» y «kinetic»/VIRAL del manifiesto, del idioma base):
    [{'ini', 'fin' (s), 'arriba', 'abajo' (la caja de la pila, fracción del alto desde ARRIBA), 'linea' (alto de su línea de abajo),
      'xs': centros de sus palabras (fracción del ancho)}]."""
    try:
        m = json.loads(MANIFIESTO.read_text(encoding='utf-8'))
    except Exception:
        return []
    pistas = [t for t in m.get('tracks') or [] if t.get('style') in ('guion', 'kinetic') and t.get('data_path')]
    if not pistas:
        return []
    idioma = pistas[0].get('language')
    out = []
    for t in pistas:
        if t.get('language') != idioma:
            continue
        try:
            cues = json.loads(Path(t['data_path']).read_text(encoding='utf-8')).get('cues') or []
        except Exception:
            continue
        out += bloques_de_cues(cues)
    out.sort(key=lambda b: b['ini'])
    return out


def bloques_de_cues(cues):
    """v5.31: los bloques de _bloques_captions a partir de los cues de un tema (los de un .json del manifiesto o los de vista_tema.planificar):
    Efectos › Posición decide sus sugerencias con ESTOS, los mismos que GO."""
    out = []
    for c in cues or []:
        runs = [r for r in c.get('runs') or [] if isinstance(r, dict)]
        ys = [float(r['y']) for r in runs if isinstance(r.get('y'), (int, float)) and 0 <= r['y'] <= 1]
        xs = [float(r['x']) for r in runs if isinstance(r.get('x'), (int, float)) and 0 <= r['x'] <= 1]
        caja = c.get('caja')
        try:
            if isinstance(caja, (list, tuple)) and len(caja) == 2:
                arriba, abajo = float(caja[0]), float(caja[1])
            elif ys:
                arriba, abajo = min(ys) - 0.03, max(ys) + 0.03
            else:
                continue
            ini, fin = float(c['start']), float(c['end'])
        except (KeyError, TypeError, ValueError):
            continue
        fin = max([fin] + [float(r['fin']) for r in runs if isinstance(r.get('fin'), (int, float))])
        if fin - ini >= 0.5 and 0 <= arriba < abajo <= 1:
            linea = 2.0 * (abajo - max(ys)) if ys and max(ys) < abajo else abajo - arriba     # el alto de la línea de ABAJO (la que tapa la cabeza)
            out.append({'ini': ini, 'fin': fin, 'arriba': arriba, 'abajo': abajo, 'linea': max(0.02, linea), 'xs': xs or [0.5],
                        'palabras': [(str(r.get('texto') or ''), float(r['t']) if isinstance(r.get('t'), (int, float)) else ini) for r in runs],
                        'emoji': c.get('emoji') if isinstance(c.get('emoji'), str) else None})    # (v5.25: el del tema, ya elegido con coherencia)
    out.sort(key=lambda b: b['ini'])
    return out


_DETECCIONES = {}


def _personas(ruta, t):
    """edicion_pro_persona.personas con caché por fotograma (los captions detrás y la regla de la cara miran los mismos)."""
    k = (str(ruta), round(float(t), 2))
    if k not in _DETECCIONES:
        import edicion_pro_persona as PE
        _DETECCIONES[k] = PE.personas(ruta, t)
    return _DETECCIONES[k]


def _cabeza(det):
    """(coronilla, x de la cabeza, alto de la persona, alto de la cabeza) de la persona más grande del fotograma (fracciones, y desde ARRIBA), o None."""
    ps = (det or {}).get('personas') or []
    if not ps:
        return None
    p = max(ps, key=lambda q: q['area'])
    x0, y0, x1, y1 = p['bbox']
    cab = (p.get('cabeza') or {}).get('alto') or 0.18 * (y1 - y0)
    return y0, (p['puntos'][0][0] if p.get('puntos') else (x0 + x1) / 2.0), y1 - y0, cab


# v5.27 (el usuario: «no está funcionando… que tenga topes de recomendación para que el caption quede bien»): lo que hace falta para que un
# caption vaya DETRÁS de la persona, compartido con Efectos › «Posición» (posiciones_pro.zonas_detras pinta en la tira dónde queda bien)
DETRAS_CORONILLA = (0.08, 0.62)       # la coronilla (fracción del alto desde arriba): ni pegada arriba ni tan abajo que el texto no llegue
DETRAS_ALTO_MIN = 0.3                 # la persona ocupa al menos esto del alto
DETRAS_QUIETA = {False: (0.05, 0.08), True: (0.10, 0.12)}       # lo que puede moverse su cabeza (alto, ancho) en el caption; True = marcado
RADIO_MARCA_DETRAS_S = 2.5            # una marca que no puede va al caption más cercano que sí, hasta esto
MOTIVOS_DETRAS = {
    'sin_captions': 'ahí no hay captions (no se habla)',
    'corte': 'cambia de toma a mitad del caption',
    'sin_persona': 'no se ve a ninguna persona',
    'se_mueve': 'la persona se mueve demasiado durante el caption',
    'pequena': 'la persona sale muy pequeña',
    'cabeza_arriba': 'su cabeza está tan arriba que el texto no cabe detrás',
    'cabeza_abajo': 'su cabeza está tan abajo que el texto no llega',
    'lado': 'el caption no le pasa por encima (está a un lado)',
    'no_cabe': 'el texto tendría que moverse demasiado',
    'corto': 'el caption dura muy poco',
    'linea': 'ese caption no tiene la palabra grande abajo',
    'no_cabe_lado': 'a ese lado de la persona no cabe el texto',
}
CORONILLA_LADO_MAX = 0.75             # v5.32: con el texto a un lado (horizontal) la cabeza puede ir pegada arriba, no tan abajo que el texto se salga


def motivo_cabeza(coronilla, alto_p, lateral=False):
    """Por qué esa cabeza no deja poner el texto detrás (clave de MOTIVOS_DETRAS) o None si vale. `lateral` (v5.32): el texto va a un lado
    de la persona, a la altura de la cabeza (horizontal, «Izquierda» / «Derecha»)."""
    if alto_p < DETRAS_ALTO_MIN:
        return 'pequena'
    if lateral:
        return 'cabeza_abajo' if coronilla > CORONILLA_LADO_MAX else None
    if coronilla < DETRAS_CORONILLA[0]:
        return 'cabeza_arriba'
    if coronilla > DETRAS_CORONILLA[1]:
        return 'cabeza_abajo'
    return None


def _dist_bloque(b, t):
    return 0.0 if b['ini'] <= t <= b['fin'] else min(abs(b['ini'] - t), abs(b['fin'] - t))


def _bloque_de(bloques, t):
    """El bloque de captions que suena en el segundo t (±0,15 s) o, si no hay, el más cercano a menos de 2 s; None si no hay ninguno."""
    k = next((k for k, b in enumerate(bloques) if b['ini'] - 0.15 <= t <= b['fin'] + 0.15), None)
    if k is None and bloques:
        k = min(range(len(bloques)), key=lambda j: _dist_bloque(bloques[j], t))
        if _dist_bloque(bloques[k], t) > 2.0:
            k = None
    return k


def _detras_bloque(b, info, video, W, H, cfg, a_cuadro, cortes, forzado, posicion=None):
    """v5.27: ¿ese bloque de captions puede ir DETRÁS de la persona? → (datos, None) o (None, motivo legible).
    Lo marcado por el usuario (`forzado`) se mira también a mitad del caption y admite que la cabeza se mueva el doble (quien camina hacia la
    cámara: en CLIENTE.mp4 la cabeza sube un 6-8 % del cuadro durante el caption y la marca se descartaba); la pila se pone siempre según la
    cabeza en su punto MÁS ALTO, así nunca tapa más de lo que deja la intensidad.
    v5.32: `posicion` (posicion_detras; None = la guardada): en horizontal, 'izquierda' / 'derecha' ponen la pila a ese lado de la cabeza
    (desplazar_lado) y los datos llevan además 'mover' (fracción del ancho, + = a la derecha: el Pan de colocar_pro)."""
    a, z = b['ini'], b['fin']
    lateral = float(W) > float(H) and (posicion or posicion_detras()) in ('izquierda', 'derecha')
    # v5.33 (el usuario: «cuando quiero seleccionar dónde lo quiero me lo impide aunque claramente sí se pueda, hay espacio»): la última
    # línea pequeña bajo la palabra grande ya no impide una MARCA suya; la cabeza tapa poco esa línea (`linea_chica`, abajo). Lo automático
    # sigue eligiendo solo los de palabra grande abajo
    linea_chica = b.get('grande_abajo') is False and not lateral
    if linea_chica and not forzado:
        return None, MOTIVOS_DETRAS['linea']                        # (v5.5.20: la cabeza solo tapa la palabra GRANDE; nunca una línea pequeña)
    if z - a < (0.6 if forzado else 1.0):
        return None, MOTIVOS_DETRAS['corto']                          # (v5.5.20: un caption de medio segundo que salta arriba y vuelve se ve forzado)
    if any(a + 0.12 < c < z - 0.1 for c in cortes):
        return None, MOTIVOS_DETRAS['corte']                          # (v5.27: un corte DENTRO del clip: el recorte dejaría de seguir a la persona)
    ts = [a + 0.12, max(a + 0.12, z - 0.15)]
    if forzado:
        ts.insert(1, (ts[0] + ts[1]) / 2.0)
    fuentes = [_fuente_de(info, video, t) for t in ts]
    if any(f[2] is not fuentes[0][2] for f in fuentes):
        return None, MOTIVOS_DETRAS['corte']                          # cruza un corte de V1: el recorte no seguiría a la persona
    try:
        ds = [_personas(r, t) for r, t, _c in fuentes]
        if a_cuadro is not None:
            vs = [a_cuadro(d, t) for d, t in zip(ds, ts)]
            if any(v is None for v in vs):
                return None, MOTIVOS_DETRAS['sin_persona']
        else:
            vs = [_a_timeline(d, f[2], W, H) for d, f in zip(ds, fuentes)]
        hs = [_cabeza(v) for v in vs]
    except Exception:
        return None, MOTIVOS_DETRAS['sin_persona']
    if not all(hs):
        return None, MOTIVOS_DETRAS['sin_persona']
    tol_y, tol_x = DETRAS_QUIETA[bool(forzado)]
    if max(h[0] for h in hs) - min(h[0] for h in hs) > tol_y or max(h[1] for h in hs) - min(h[1] for h in hs) > tol_x:
        return None, MOTIVOS_DETRAS['se_mueve']
    coronilla, cab_x = min(h[0] for h in hs), sum(h[1] for h in hs) / len(hs)
    alto_p, cab = min(h[2] for h in hs), min(h[3] for h in hs)
    m = motivo_cabeza(coronilla, alto_p, lateral)
    if m:
        return None, MOTIVOS_DETRAS[m]
    if lateral:
        r = desplazar_lado(posicion or posicion_detras(), b['arriba'], b['abajo'], min(b['xs']) - 0.03, max(b['xs']) + 0.03,
                           coronilla, cab_x, cab, W, H)
        if r is None:
            return None, MOTIVOS_DETRAS['no_cabe_lado']
        caras = [c for v in vs for c in _caras(v)]
        return dict(b, subir=-r[1], mover=r[0], clip=fuentes[0][2], det=vs[0] if a_cuadro is not None else ds[0], t_det=ts[0], caras=caras), None
    if not (min(b['xs']) - 0.16 <= cab_x <= max(b['xs']) + 0.16):
        return None, MOTIVOS_DETRAS['lado']
    # cuánto de la pila tapa la cabeza: hasta la frente (~40 % de la cabeza), sin pasar del 45 % de la línea de abajo (la palabra se sigue
    # leyendo); en un plano entero (cabeza pequeña) tapa poco y en un primer plano mucho más
    tapa = max(0.012, min(cfg['tapa_max'] if cfg else 0.055, 0.4 * cab, (cfg['tapa'] if cfg else 0.45) * b['linea']))
    if linea_chica:                                                   # (una línea pequeña abajo: la cabeza solo le roza el pie, se sigue leyendo)
        tapa = max(0.006, min(tapa, 0.28 * b['linea']))
    dy = coronilla + tapa - b['abajo']
    if b['arriba'] + dy < 0.08:
        return None, MOTIVOS_DETRAS['cabeza_arriba']                  # (v5.5.20: no sube al borde de arriba del cuadro —«EMPRESA» pegado arriba—)
    if b['abajo'] + dy < coronilla + min(0.012, tapa) - 1e-6 or b['abajo'] + dy > 0.9 or b['abajo'] + dy - coronilla > tapa + 0.004:
        return None, MOTIVOS_DETRAS['no_cabe']
    # (v5.5.20: si la pila no puede subir más —choca arriba— la cabeza taparía más de lo que deja la intensidad: ese bloque no va detrás)
    caras = [c for v in vs for c in _caras(v)]
    return dict(b, subir=-dy, clip=fuentes[0][2], det=vs[0] if a_cuadro is not None else ds[0], t_det=ts[0], caras=caras), None


def _captions_detras(info, video, fps, ocupado, densidad, decir, preferidos=(), W=1080, H=1920, intensidad=None, bloques=None, a_cuadro=None,
                     marcas=None, cortes=None):
    """Qué bloques de captions van DETRÁS de la persona y cuánto suben. Un bloque vale si la persona es grande, su cabeza no se sale por arriba,
    está quieta en todo el bloque (misma toma), la pila le cae encima en horizontal y no hay otro gráfico ni B-roll en ese momento. La pila sube (o
    baja) hasta que su borde de abajo queda un poco por debajo de la coronilla: la cabeza tapa la parte de abajo de la palabra grande y el resto se lee.
    El primero que vale entra siempre (el gancho), también los de `preferidos` (las palabras fuertes y las preguntas que la PRO ya no repite en un
    titular) y el resto se alternan (`DETRAS_CAPTIONS`): el contraste también retiene.
    Devuelve los tramos [{'ini', 'fin' (s), 'det', 't_det', 'cues': [{'ini', 'fin', 'subir' (fracción del alto, + = arriba)}]}].
    v5.5.20: `intensidad` (INTENSIDAD_DETRAS) manda en cuántos y cuánto tapa; `bloques` = los del tema (el Tema 1 da los suyos, kit_neon.bloques_pro)
    y `a_cuadro(det, t)` pasa la detección de la fuente a lo que se VE (el Tema 1: la placa con sus zooms; None = ahí no se puede).
    v5.22: `marcas` = {'modo', 'ts'} de Efectos › «Posición»: el bloque que suena en cada segundo marcado va detrás SIEMPRE que la persona
    lo permita (aunque haya otro gráfico o le toque descansar); con 'solo', ninguno más. Lo que no se pudo queda en el Registro.
    v5.27: cada bloque lo decide _detras_bloque (con su motivo); `cortes` (s) = los cambios de toma DENTRO del clip; una marca que no puede va
    al caption más cercano que sí (RADIO_MARCA_DETRAS_S)."""
    bloques = _bloques_captions() if bloques is None else bloques
    if not bloques:
        return []
    decir('Edición PRO: buscando dónde los captions van detrás de la persona…')
    cfg = INTENSIDAD_DETRAS.get(intensidad) if intensidad else None
    frac = cfg['frac'] if cfg else DETRAS_CAPTIONS.get(densidad, 0.55)
    cortes_t = sorted(float(c[0] if isinstance(c, (list, tuple)) else c) for c in cortes or [])
    forz, avisos = {}, []                                             # bloque → segundo marcado
    for t in (marcas or {}).get('ts') or []:
        k = _bloque_de(bloques, t)
        if k is not None:
            forz.setdefault(k, t)
        else:
            avisos.append(f'«detrás de ti» en {t:.1f} s: {MOTIVOS_DETRAS["sin_captions"]}')
    solo = bool(marcas) and marcas.get('modo') != 'suma'
    posicion = posicion_detras(W=W, H=H)                              # v5.32: en horizontal, arriba o a un lado de la persona

    def probar(k, forzado):
        return _detras_bloque(bloques[k], info, video, W, H, cfg, a_cuadro, cortes_t, forzado, posicion=posicion)

    # v5.27: las marcas del usuario primero. Si su caption no puede ir detrás, el más cercano que sí (a ±RADIO_MARCA_DETRAS_S de la marca):
    # «lo más cerca donde queda bien»; y el Registro dice el motivo CONCRETO (antes, uno genérico para todo)
    hechos = {}
    for k, t in sorted(forz.items(), key=lambda x: x[1]):
        e, motivo = probar(k, True)
        if e is None:
            cerca = sorted((j for j in range(len(bloques)) if j != k and j not in forz and j not in hechos
                            and _dist_bloque(bloques[j], t) <= RADIO_MARCA_DETRAS_S), key=lambda j: _dist_bloque(bloques[j], t))
            for j in cerca:
                e, _m = probar(j, True)
                if e is not None:
                    avisos.append(f'«detrás de ti» en {t:.1f} s: {motivo}; va en el caption de {bloques[j]["ini"]:.1f} s, lo más cerca donde queda bien')
                    k = j
                    break
            else:
                avisos.append(f'«detrás de ti» en {t:.1f} s: no se puede, {motivo}')
        if e is not None:
            hechos[k] = dict(e, k=k, forzado=True)
    elegidos, acum = [], 1.0 - frac
    for k, b in enumerate(bloques):
        if k in hechos:
            elegidos.append(hechos[k])
            continue
        if solo or k in forz:
            continue
        a, z = b['ini'], b['fin']
        if any(a < o1 and o0 < z for o0, o1 in ocupado):
            continue
        acum += frac
        pref = any(a < p1 and p0 < z for p0, p1 in preferidos)
        if acum < 0.999 and not pref:
            continue
        e, _motivo = probar(k, False)
        if e is None:
            continue
        acum = max(0.0, acum - 1.0)
        elegidos.append(dict(e, k=k, forzado=False))
    _avisar_marcas(avisos)
    # los bloques seguidos (de la misma toma) comparten un solo recorte de la persona: menos rastreos de Magic Mask
    tramos = []
    for e in elegidos:
        k = e['k']
        # v5.5.20: por debajo de `corte` la persona recortada no hace falta (es idéntica a lo que tiene debajo): colocar_pro recorta ahí su
        # capa. Así puede quedarse hasta que el caption termina de SALIR (antes se iba a media salida y el texto saltaba delante de la cabeza)
        # sin tapar el bloque siguiente, que va en su sitio, más abajo
        corte = min(1.0, e['abajo'] - e['subir'] + 0.08)
        sig_b = bloques[k + 1] if k + 1 < len(bloques) else None
        sig = sig_b['ini'] if sig_b else e['fin'] + 0.3
        if sig_b is None or sig_b['arriba'] > corte + 0.01:
            fin = max(e['ini'] + 0.3, e['fin'] + float(e.get('salida', 0.35)))
        else:
            fin = max(e['ini'] + 0.3, min(e['fin'] + 0.2, sig))       # sin tapar el bloque siguiente (ese va normal, delante)
        cue = {'ini': e.get('ini_clip', e['ini']), 'fin': e['fin'], 'subir': round(e['subir'], 4), 'caras': e['caras'],
               'caja': [round(e['arriba'] - e['subir'], 4), round(e['abajo'] - e['subir'], 4)]}     # v5.5.2: dónde queda el caption (sus emojis no lo pisan)
        if abs(float(e.get('mover') or 0.0)) > 1e-4:
            cue['mover'] = round(float(e['mover']), 4)                # (v5.32: horizontal, a un lado de la persona: el Pan)
        t = tramos[-1] if tramos else None
        if t and t['k'] == k - 1 and t['clip'] is e['clip'] and fin - t['ini'] <= TRAMO_DETRAS_MAX_S:
            t.update(fin=fin, k=k, corte=max(t.get('corte', 0.0), corte), forzado=t.get('forzado') or e.get('forzado'))
            t['cues'].append(cue)
            continue
        ini = e['ini']
        if k > 0 and bloques[k - 1]['fin'] > ini:
            ini = min(bloques[k - 1]['fin'], fin - 0.3)               # el bloque anterior aún sale: la persona entra cuando se va
        tramos.append({'ini': ini, 'fin': fin, 'k': k, 'clip': e['clip'], 'det': e['det'], 't_det': e['t_det'], 'cues': [cue], 'corte': corte,
                       'forzado': bool(e.get('forzado'))})
    for a_, b_ in zip(tramos, tramos[1:]):                           # (dos recortes no se pisan en PRO-ENCIMA: colocar_pro quitaría el 2.º)
        a_['fin'] = max(a_['ini'] + 0.2, min(a_['fin'], b_['ini']))
    if cfg and len(tramos) > cfg['tramos']:
        marcados = [t for t in tramos if t.get('forzado')]                # (v5.22: los que marcó el usuario no se recortan nunca)
        libres = [t for t in tramos if not t.get('forzado')]
        cupo = max(0, cfg['tramos'] - len(marcados))
        tramos = marcados + (libres[:1] + sorted(libres[1:], key=lambda t: -(t['fin'] - t['ini']))[:max(0, cupo - 1)] if cupo else [])
        tramos.sort(key=lambda t: t['ini'])                               # el gancho y los más largos
    return tramos


def _encima_de(tramos, info, video, fps, W, H, carpeta, a_cuadro, neon_tema, fx_persona, usar_magic, placa=None, decir=None, progreso=None):
    """Las entradas «encima» de colocar_pro (la persona DELANTE de los captions) para los tramos de _captions_detras.
    v5.29 (el usuario: «necesito una máscara que detecte humanos y cree el matte para que quede en el render»): la persona la recorta la IA
    local (MODNet: solo personas) en un ProRes 4444 con alfa (`modo: 'clip'`, edicion_pro_persona.recorte_prores): Resolve solo lo reproduce,
    no rastrea nada, y sale igual en el visor y en el render. Antes era Magic Mask, que había que rastrear en la página Fusion y a veces no
    quedaba. Con la placa del Tema 1 (`a_cuadro`: lo que se ve son sus zooms) el recorte sale de la PLACA (`placa`: su archivo; sin ella, ese
    tramo no va). Magic Mask solo si se elige a mano en el menú (`usar_magic`)."""
    import edicion_pro_persona as PE
    decir = decir or (lambda t: None)
    out = []
    # v5.31: el avance de verdad (fotogramas recortados de TODOS los tramos) para la barra de «Listo»; una máscara ya guardada cuenta entera al momento
    total = max(1e-6, sum(max(0.1, float(t['fin']) - float(t['ini'])) for t in tramos))
    hecho = [0.0]

    def avance(n, f):
        if progreso:
            try:
                progreso((hecho[0] + f * max(0.1, float(tramos[n]['fin']) - float(tramos[n]['ini']))) / total,
                         f'Recortando a la persona con IA ({n + 1} de {len(tramos)})…')
            except Exception:
                pass
    for n, t in enumerate(tramos):
        f0, f1 = int(round(t['ini'] * fps)), int(round(t['fin'] * fps))
        ref = max(0, min(f1 - f0 - 1, int(round((t['t_det'] - t['ini']) * fps))))
        e = {'ini': f0, 'fin': f1, 'ref': ref, 'cues': [{'ini': int(round(c['ini'] * fps)), 'fin': int(round(c['fin'] * fps)),
                                                        'subir': round(c['subir'] * H, 1), 'caras': _caras_redondas(c.get('caras')),
                                                        'caja': c.get('caja'), 'mover': round(float(c.get('mover') or 0.0) * W, 1)}
                                                       for c in t['cues']]}
        corte = float(t.get('corte') or 1.0)
        if a_cuadro is not None:
            e['fuente'] = 'placa'                                    # (colocar_pro: la transformación, la del clip de la placa, PRO-ZOOM)
        if neon_tema:
            e['subs_pro'] = True                                     # (los captions del Tema 1 son clips en PRO-SUBS / PRO-SUBS2)
        if usar_magic:
            comp = _comp_magic(PE.puntos_fusion(t['det']), ref, carpeta / f'encima_{f0}_{f1}.comp', f'CCProMagicE{f0}', efecto=fx_persona)
            e.update(modo='magic', comp=str(OG.ruta_larga(comp)), herramienta=f'CCProMagicE{f0}')
            alto_clip = None
        else:
            if a_cuadro is not None:
                if not placa:
                    continue                                         # (sin la placa no se sabe qué se ve: ese tramo, sin persona delante)
                fuente, t0 = str(placa), float(t['ini'])
            else:
                fuente, t0, _clip = _fuente_de(info, video, float(t['ini']))
            dur = (f1 - f0) / float(fps) + 0.1
            decir(f'Edición PRO: recortando a la persona con IA para «detrás de ti» ({n + 1} de {len(tramos)})…')
            avance(n, 0.0)
            try:                                                     # v5.31: la máscara GUARDADA (fuera de la caché; se reutiliza al momento)
                destino = PE.mascara_guardada(fuente, t0, t0 + dur, al_progreso=lambda f, n=n: avance(n, f))
            except Exception:
                destino = None
            hecho[0] += max(0.1, float(t['fin']) - float(t['ini']))
            avance(n, 0.0)
            if destino is None:
                continue
            e.update(modo='clip', archivo=str(OG.ruta_larga(destino)))
            alto_clip = 'clip'
        if corte < 0.995:
            if a_cuadro is not None:
                e['recorte_px'] = int(round((1.0 - corte) * H))       # (la placa va a la resolución del timeline)
            else:
                y_src, alto_src = _y_en_fuente(corte, t.get('clip'), W, H)
                if alto_clip == 'clip':                              # (el recorte de la IA va con el lado largo a 1920 como mucho)
                    try:
                        w_src, h_src = (int(x) for x in str((t.get('clip') or {}).get('res') or '').lower().replace(' ', '').split('x')[:2])
                        alto_src *= min(1.0, 1920.0 / max(w_src, h_src))
                    except (TypeError, ValueError):
                        pass
                e['recorte_px'] = int(round(max(0.0, (1.0 - y_src) * alto_src)))
        # v5.5.2: SIN el velo oscuro detrás de estos captions (el usuario: «los captions tienen una sombra fea»); la persona encima ya los separa
        out.append(e)
    return out


def _captions_sin_cara(info, video, ocupado, detras, W, H):
    """REGLA DEL USUARIO: ningún caption tapa una cara. Los bloques que no van detrás de la persona y caerían sobre una cara (al principio o al
    final del bloque) suben encima de la cabeza o bajan debajo de la barbilla (si no cabe en ningún lado, se quedan).
    v5.5.8 (pedido: «some text stay up some stay down… necesito más coherencia»): antes cada bloque iba a lo MÁS CERCANO y en un mismo video
    unos subían a la frente y otros bajaban al pecho. Ahora se elige UN lado para todo el video (debajo de la barbilla, salvo que arriba quepa
    en más bloques) y los bloques seguidos que se mueven comparten la MISMA altura (`_lado_coherente`).
    Devuelve [{'ini', 'fin' (s), 'subir' (fracción, + arriba; 0 si no tapaban), 'caras'}] de los bloques con alguna cara: colocar_pro revisa
    con 'caras' también sus emojis."""
    ya = {round(c['ini'], 3) for t in detras for c in t['cues']}
    filas = []
    for b in _bloques_captions():
        a, z = b['ini'], b['fin']
        if round(a, 3) in ya or any(a < o1 and o0 < z for o0, o1 in ocupado):
            continue
        caras = []
        for t in (a + 0.12, max(a + 0.12, z - 0.15)):
            ruta, t_src, clip = _fuente_de(info, video, t)
            try:
                caras += _caras(_a_timeline(_personas(ruta, t_src), clip, W, H))
            except Exception:
                pass
        if not caras:
            continue
        yc, medio = (b['arriba'] + b['abajo']) / 2.0, (b['abajo'] - b['arriba']) / 2.0
        filas.append({'ini': a, 'fin': z, 'yc': yc, 'medio': medio, 'caras': caras,
                      'x0': max(0.0, min(b['xs']) - 0.2), 'x1': min(1.0, max(b['xs']) + 0.2)})
    out = []
    for f, y in zip(filas, _lado_coherente(filas)):
        yc, medio = f['yc'], f['medio']
        caja = [round(y - medio, 4), round(y + medio, 4)] if y is not None else [round(yc - medio, 4), round(yc + medio, 4)]
        out.append({'ini': f['ini'], 'fin': f['fin'], 'subir': round(yc - y, 4) if y is not None else 0.0, 'caras': f['caras'], 'caja': caja})
    return out


DATOS_OGRAF = {'precio': 1.15, 'grafica': 1.1, 'cifra': 1.0}           # tipo de objeto → su escala en EscenaT5 (ESCALA_OBJ de Skill.tsx)


def _motions_a_ograf(piezas, W, H):
    """v5.5.8 (pedido: «los motions que el usuario pueda retocarlos en el Inspector sin afectar el motion»): las tarjetas de dato de los Temas
    5/6 (precio, cifra, gráfica) van como la pieza OGraf «dato» —valor, moneda, etiqueta, colores, tipografía, posición y tamaño editables en el
    Inspector, la animación se recalcula sola— en vez de un video de Remotion, en el MISMO sitio y tamaño:
      · TarjetaT5 de gráfica (encima de la cabeza): pasa entera a OGraf (su `y` era el borde de arriba; la del dato, el centro);
      · EscenaT5 con un solo objeto de dato: la escena se queda de fondo (Remotion, sin el objeto) y la tarjeta va encima como OGraf, en
        PRO-DELANTE, o en PRO-ICONOS si esa pista ya está ocupada a esa hora (dos clips a la vez en una pista no se colocan)."""
    U = min(W, H) / 1080.0
    ocupado = [(p['ini'], p['fin']) for p in piezas if p.get('capa') == 'delante' and not p.get('quitar')]
    nuevas = []
    for p in piezas:
        v = p.get('valores') or {}
        if p.get('quitar'):
            continue
        if p.get('remotion') == 'TarjetaT5' and v.get('tipo') == 'grafica':
            esc = float(v.get('escala') or 1.0)
            alto = 392 * U * esc / H * 100.0                                # alto de la carta de gráfica de TarjetaT5, en % del cuadro
            sube = float(v.get('sube') or 0)
            p.pop('remotion', None)
            p['pieza'] = 'dato'
            p['valores'] = {'tipo': 'grafica', 'valor': str(v.get('valor') or ''), 'signo': str(v.get('signo') or ''),
                            'etiqueta': str(v.get('etiqueta') or '').upper()[:28], 'tendencia': 'baja' if sube < 0 else 'sube' if sube > 0 else 'plana',
                            'tema': 'claro' if v.get('aspecto') == 'blanco' else 'oscuro', 'acento': v.get('acento') or '#4c7dff',
                            'tiempos': '0.1', 'escala': round(esc * min(W * 0.88, 920 * U) / (700 * U), 3),
                            'x': float(v.get('x', 50)), 'y': round(float(v.get('y', 20)) + alto / 2.0, 2)}
            continue
        objs = v.get('objetos') or []
        if not (p.get('remotion') == 'EscenaT5' and v.get('disposicion', 'objeto') == 'objeto' and len(objs) == 1 and objs[0].get('tipo') in DATOS_OGRAF):
            continue
        o, mitad = objs[0], v.get('mitad', 'completa')
        encima, arriba = mitad == 'encima', mitad == 'arriba'
        tipo = o['tipo']
        k = DATOS_OGRAF[tipo] * (0.8 if (arriba or encima) and tipo != 'cifra' else 1.0) * (0.86 if encima else 1.0)
        ini, fin = round(p['ini'] + max(0.0, float(o.get('t', 0.2)) - 0.1), 3), round(p['fin'] - 0.05, 3)
        if fin - ini < 0.6:
            continue
        sube = float(o.get('sube', 1) or 0)
        nuevas.append({'pieza': 'dato', 'capa': 'iconos' if any(ini < b and a < fin for a, b in ocupado) else 'delante', 'ini': ini, 'fin': fin,
                       'motivo': f'dato editable: {tipo} {o.get("signo", "")}{o.get("valor", "")}',
                       'valores': {'tipo': tipo, 'valor': str(o.get('valor') or ''), 'signo': str(o.get('signo') or ''),
                                   'etiqueta': str(o.get('etiqueta') or ('TOTAL' if tipo == 'precio' else 'GROWTH' if tipo == 'grafica' else '')),
                                   'tendencia': 'baja' if sube < 0 else 'sube', 'tema': 'oscuro' if (encima or v.get('fondo') == 'cristal') else 'claro',
                                   'fuente': 'serif' if v.get('fondo') == 'melocoton' else 'grotesk', 'acento': v.get('acento') or '#4c7dff',
                                   'tiempos': '0.1', 'escala': round(k, 3), 'x': 50.0,
                                   'y': float(v.get('y', 68)) if encima else 29.0 if arriba else 56.0}})
        p['valores'] = dict(v, objetos=[])                                  # la escena, solo de fondo
    piezas.extend(nuevas)
    return len(nuevas)


def _opciones_fuera(yc, medio, caras, x0=0.0, x1=1.0):
    """{'queda': y si no pisa ninguna cara, 'abajo': centro justo debajo de la barbilla más baja, 'arriba': justo encima de la coronilla más
    alta} (None el que no quepa): lo que `_fuera_de_la_cara` elegía por cercanía, por separado."""
    malas = [c for c in caras if c[0] < x1 and x0 < c[2]]

    def libre(yy):
        return 0.04 + medio <= yy <= 0.96 - medio and all(yy + medio + MARGEN_CARA <= c[1] or yy - medio - MARGEN_CARA >= c[3] for c in malas)
    if not malas or libre(yc):
        return {'queda': yc, 'abajo': None, 'arriba': None}
    abajo = max(c[3] for c in malas) + MARGEN_CARA + medio
    arriba = min(c[1] for c in malas) - MARGEN_CARA - medio
    return {'queda': None, 'abajo': abajo if libre(abajo) else None, 'arriba': arriba if libre(arriba) else None}


def _lado_coherente(filas, hueco_s=1.2):
    """El centro final de cada fila ({'yc', 'medio', 'caras', 'x0', 'x1', 'ini', 'fin'}) o None si no cabe: UN lado para todo el video (abajo
    salvo que arriba quepa en más bloques) y una misma altura para los bloques seguidos (a menos de `hueco_s`) que se mueven al mismo lado."""
    ops = [_opciones_fuera(f['yc'], f['medio'], f['caras'], f['x0'], f['x1']) for f in filas]
    n_abajo = sum(1 for o in ops if o['queda'] is None and o['abajo'] is not None)
    n_arriba = sum(1 for o in ops if o['queda'] is None and o['arriba'] is not None)
    lado, otro = ('abajo', 'arriba') if n_abajo >= n_arriba else ('arriba', 'abajo')
    ys, lados = [], []
    for o in ops:
        elegido = None if o['queda'] is not None else lado if o[lado] is not None else otro if o[otro] is not None else None
        ys.append(o['queda'] if elegido is None and o['queda'] is not None else o[elegido] if elegido else None)
        lados.append(elegido)
    # misma altura en las rachas de bloques seguidos movidos al mismo lado (la más baja si van abajo, la más alta si van arriba), si les cabe a todos
    i = 0
    while i < len(filas):
        j = i
        while j + 1 < len(filas) and lados[j + 1] and lados[j + 1] == lados[i] and filas[j + 1]['ini'] - filas[j]['fin'] <= hueco_s:
            j += 1
        if lados[i] and j > i:
            comun = (max if lados[i] == 'abajo' else min)(ys[i:j + 1])
            if all(_opciones_fuera(comun, filas[k]['medio'], filas[k]['caras'], filas[k]['x0'], filas[k]['x1'])['queda'] is not None
                   for k in range(i, j + 1)):
                ys[i:j + 1] = [comun] * (j + 1 - i)
        i = j + 1
    return ys


def _iconos3d_captions(info, ocupado, subidas, caras_de, W, H, densidad):
    """Iconos 3D (3dicons) que FLOTAN arriba a un lado de la pila de captions cuando se nombra algo que tiene uno («precio» → dinero,
    «viral» → fuego…), en vez del emoji plano de ese bloque. Nunca encima de una cara (prueba el otro lado; si no, no va).
    Devuelve [{'ini', 'fin' (s), 'valores'}] y las ventanas donde se apaga el emoji del tema."""
    import edicion_pro_planificador as PL
    disp = OG.iconos3d()
    vertical = H > W
    cada = ICONO3D_CADA.get(densidad, 3.5)
    out, ultimo = [], -99.0
    for b in _bloques_captions():
        a, z = b['ini'], b['fin']
        if a - ultimo < cada or z - a < 0.8 or any(a < o1 and o0 < z for o0, o1 in ocupado):
            continue
        nombre, t_pal = None, a
        for texto, t in b.get('palabras') or []:
            w = PL.plegar(texto)
            n = PL.CONCEPTOS3D.get(w) or PL.ICONO_A_3D.get(PL.CONCEPTOS.get(w, ''))
            if n and n in disp:
                nombre, t_pal = n, max(a, t)
                break
        if not nombre or z - t_pal < 0.6:
            continue
        sube = subidas.get(round(a, 2), 0.0)
        tam = 0.085 if vertical else 0.13
        y = max(tam / 2 + 0.035, b['arriba'] - sube - tam * 0.25)
        ancho = tam * H / W
        caras = caras_de.get(round(a, 2), [])
        x = None
        for cx in (min(0.92 - ancho / 2, max(b['xs']) + 0.12), max(0.08 + ancho / 2, min(b['xs']) - 0.12)):
            if not any(k[0] < cx + ancho / 2 and cx - ancho / 2 < k[2] and k[1] < y + tam / 2 and y - tam / 2 < k[3] for k in caras):
                x = cx
                break
        if x is None:
            continue
        ultimo = a
        out.append({'ini': max(a, t_pal - 0.05), 'fin': z + 0.15, 'valores': {'imagen': nombre, 'tamano': round(tam * 100, 1), 'brillo': 0.75,
                    'flotar': 1.0, 'giro': 8, 'x': round(x * 100, 1), 'y': round(y * 100, 1), 'tiempos': '0'}})
    return out


# ----------------------------------------------------------------------------------------------------------------------- emojis animados (v5.25)
EMOJI_2D = ('animado', 'rebote', 'brillo', 'burbuja', 'sticker')                 # Lottie de Google (o, si ese emoji no tiene, el 3D con ese movimiento)
EMOJI_3D = ('3d_salto', '3d_flota', '3d_giro', '3d_gelatina', '3d_estallido')     # el 3D de Microsoft, siempre en movimiento


def _png_emoji(eid):
    """(nombre del sticker que trae el programa | None, ruta de un PNG 3D bajado | None)."""
    try:
        propio = Path(carpeta_recursos()).parent / 'emojis' / 'png' / f'rcs_emoji_{eid}.png'
        if propio.is_file():
            return eid, None
    except Exception:
        pass
    try:
        import emojis
        r = emojis.ruta_png(eid)
        return None, (Path(r) if r and Path(r).is_file() else None)
    except Exception:
        return None, None


def _assets_emoji(eid, variante):
    """Las props de la imagen de un emoji para EmojiPro: Lottie (2D) y/o el PNG 3D. None si no hay ninguna."""
    v = {}
    if variante in EMOJI_2D:
        try:
            import emojis_animados
            origen, datos = emojis_animados.lottie_de(eid)
        except Exception:
            origen, datos = None, None
        if origen == 'programa':
            v.update(fuente='lottie', lottie=None)
        elif origen == 'datos' and datos:
            v.update(fuente='lottie', lottie=datos)
    if not v:
        propio, ruta = _png_emoji(eid)
        if propio:
            v.update(fuente='png', imagen=None)
        elif ruta is not None:
            import base64
            v.update(fuente='png', imagen='data:image/png;base64,' + base64.b64encode(ruta.read_bytes()).decode('ascii'))
        else:
            return None
    return v


def _choca(cx, cy, ancho, alto, caja, margen=0.012):
    x0, y0, x1, y1 = caja[:4]
    return cx - ancho / 2 < x1 + margen and x0 - margen < cx + ancho / 2 and cy - alto / 2 < y1 + margen and y0 - margen < cy + alto / 2


def _sitio_emoji(b, sube, caras, tam, ancho, donde):
    """(x, y) del centro del emoji (fracciones del cuadro) o None. «lado»: arriba a un lado de la pila de captions; «encima»: centrado sobre la
    pila; «cabeza»: junto a la cabeza (a su lado, a la altura de los ojos); «auto»: lado → encima → cabeza. Nunca sobre una cara ni fuera."""
    arriba = b['arriba'] - sube
    xs = b.get('xs') or [0.5]
    izq, der = min(xs) - 0.1, max(xs) + 0.1                       # (los xs son centros de palabras: la pila llega algo más allá)
    cands = {'lado': [(der + ancho * 0.55, arriba - tam * 0.2), (izq - ancho * 0.55, arriba - tam * 0.2)],
             'encima': [(sum(xs) / len(xs), arriba - tam * 0.62)], 'cabeza': []}
    if caras:
        c = max(caras, key=lambda k: (k[2] - k[0]) * (k[3] - k[1]))
        cy = c[1] + (c[3] - c[1]) * 0.35
        cands['cabeza'] = [(c[2] + ancho * 0.62, cy), (c[0] - ancho * 0.62, cy)]
    orden = {'lado': ['lado', 'encima'], 'encima': ['encima', 'lado'], 'cabeza': ['cabeza', 'lado', 'encima'],
             'auto': ['lado', 'encima', 'cabeza']}.get(donde, ['lado', 'encima', 'cabeza'])
    for clave in orden:
        for x, y in cands[clave]:
            if not (0.03 + ancho / 2 <= x <= 0.97 - ancho / 2 and 0.035 + tam / 2 <= y <= 0.95 - tam / 2):
                continue
            if any(_choca(x, y, ancho, tam, k) for k in caras):
                continue
            if clave != 'encima' and _choca(x, y, ancho, tam, (izq + 0.04, arriba, der - 0.04, b['abajo'] - sube), 0.0):
                continue
            return x, y
    return None


def _emojis_pro(bloques, ocupado, subidas, caras_de, W, H, op, marcas=None):
    """v5.25 «Emojis animados» (Efectos › Edición PRO; el usuario: «emojis con diferentes estilos 3D-2D, siempre animados, archivo Lottie, y la
    posición: que tenga coherencia de dónde se aplica, y la intensidad»). Un emoji ANIMADO con lo que se dice:
      · cuál: el de una palabra de ese caption (diccionario curado emojis_conceptos) o el que el tema ya eligió para él (con su coherencia);
      · dónde: «Dónde» (auto: a un lado de la pila; si no cabe, encima; si no, junto a la cabeza), nunca sobre una cara ni encima de otro
        gráfico (`ocupado`) ni fuera del cuadro;
      · cuántos y cómo: la intensidad (INTENSIDAD_EMOJI: cada cuánto, tamaño y energía del movimiento);
      · `marcas` (Efectos › «Posición»): esos captions van siempre que haya emoji y sitio; con «solo», ninguno más.
    Devuelve (piezas de Remotion «EmojiPro» en la capa «iconos», ventanas (s) donde se apaga el emoji del tema)."""
    import emojis_conceptos as EC
    cfg = INTENSIDAD_EMOJI[intensidad_emoji(op)]
    donde = donde_emoji(op)
    try:
        import estilos_pro as EST
        v, col = EST.resolver('emoji', op)
    except Exception:
        v, col = None, {}
    elegida = (v or {}).get('id')
    tam = cfg['tam'] * min(W, H) / float(H)                        # fracción del alto
    ancho = cfg['tam'] * min(W, H) / float(W)                      # fracción del ancho (es cuadrado)
    forz = {}
    for t in (marcas or {}).get('ts') or []:
        k = next((k for k, b in enumerate(bloques) if b['ini'] - 0.15 <= t <= b['fin'] + 0.15), None)
        if k is None and bloques:
            k = min(range(len(bloques)), key=lambda k: min(abs(bloques[k]['ini'] - t), abs(bloques[k]['fin'] - t)))
            if min(abs(bloques[k]['ini'] - t), abs(bloques[k]['fin'] - t)) > 2.0:
                k = None
        if k is not None:
            forz.setdefault(k, t)
    solo = bool(marcas) and marcas.get('modo') != 'suma'
    out, avisos, ultimo, assets = [], [], -99.0, {}
    for k, b in enumerate(bloques):
        a, z = float(b['ini']), float(b['fin'])
        forzado = k in forz
        if solo and not forzado:
            continue
        if not forzado and (a - ultimo < cfg['cada'] or z - a < 0.8 or any(a < o1 and o0 < z for o0, o1 in ocupado)):
            continue
        # (v5.27: las palabras del Tema 1 —kit_neon.bloques_pro— traen 3 datos; las de los demás temas, 2: «too many values to unpack»)
        cand = [(EC.concepto(str(p[0])), float(p[1]), str(p[0])) for p in b.get('palabras') or [] if len(p) >= 2]
        cand = [c for c in cand if c[0]] + ([(b['emoji'], a, '')] if b.get('emoji') else [])
        variante = elegida or ('rebote' if k % 2 == 0 else '3d_salto')          # (Automático: alterna un 2D y un 3D)
        eid = palabra = None
        t_pal = a
        for c, t, texto in cand:
            if (c, variante) not in assets:
                assets[(c, variante)] = _assets_emoji(c, variante)
            if assets[(c, variante)]:
                eid, t_pal, palabra = c, max(a, t), texto
                break
        if not eid:
            if forzado:
                avisos.append(f'«emojis» en {forz[k]:.1f} s: lo que se dice ahí no tiene un emoji claro')
            continue
        ini = max(a, t_pal - 0.08)
        if not forzado and (z - t_pal < 0.45 or ini - ultimo < cfg['cada']):
            continue                                                  # (la distancia se mide entre lo que de verdad se VE: cuándo sale cada uno)
        pos = _sitio_emoji(b, subidas.get(round(a, 2), 0.0), caras_de.get(round(a, 2), []) or [], tam, ancho, donde)
        if pos is None:
            if forzado:
                avisos.append(f'«emojis» en {forz[k]:.1f} s: no hay sitio sin tapar una cara o los captions')
            continue
        ultimo = ini
        valores = dict(assets[(eid, variante)], id=eid, variante=variante, x=round(pos[0] * 100, 2), y=round(pos[1] * 100, 2),
                       tamano=round(cfg['tam'] * 100, 2), energia=cfg['energia'], acento=col.get('acento') or '#FFC24D')
        out.append({'pieza': 'emoji', 'capa': 'iconos', 'remotion': 'EmojiPro', 'ini': round(ini, 3), 'fin': round(z + 0.25, 3),
                    'valores': valores, '_marca': forzado,
                    'motivo': f'emoji «{eid}»' + (f' por «{palabra}»' if palabra else ' (el del caption)')})
    for p, q in zip(out, out[1:]):                                   # (dos en la misma pista no se pisan: el vigilante quitaría el 2.º)
        p['fin'] = round(max(p['ini'] + 0.4, min(p['fin'], q['ini'] - 0.05)), 3)
    _avisar_marcas(avisos)
    return out, [(p['ini'], p['fin']) for p in out]


def _caras_redondas(caras):
    return [[round(float(x), 4) for x in c] for c in caras or []]


def aplicar(plan, al_estado=None, offset_frames=0, info=None):
    """Pone la Edición PRO en el timeline actual. Devuelve (ok, mensaje)."""
    decir = al_estado or (lambda t: None)
    if not plan or not (plan.get('piezas') or plan.get('tema5') or plan.get('ligero') or plan.get('kitneon')
                        or (plan.get('opciones') or opciones_guardadas()).get('pro_motions_completo')):        # v5.5.8: también solo motions
        return True, ''
    info = info or _info_timeline()
    if not info:
        return False, 'No pude leer el timeline de Resolve (¿está abierto, con el video en V1?)'
    fps, W, H = float(info['fps']), int(info['ancho']), int(info['alto'])
    info['base'] = int(info['inicio']) + int(offset_frames or 0)
    vertical = H > W
    studio = 'studio' in str(info.get('producto') or '').lower() and info.get('via') == 'mcp'
    op = plan.get('opciones') or opciones_guardadas()
    modo_mascara = op.get('pro_mascara') or 'auto'
    try:                                             # v5.20: la sombra / orilla / resplandor de la silueta (página Efectos › Captions detrás de ti)
        import estilos_pro as EST
        fx_persona = EST.efecto_persona(op)
    except Exception:
        fx_persona = None
    # v5.5.7: en «auto» la persona la recorta SIEMPRE la IA local (clip ProRes con alfa), también en Studio: el rastreo del Magic Mask dentro de
    # Resolve lo tumbó dos veces colocando la PRO (2026-10-13 y 14). Así Studio y Free hacen lo mismo y Resolve no calcula nada pesado. Magic Mask,
    # solo si se elige a mano en el menú.
    usar_magic = studio and modo_mascara == 'magic'
    usar_ia = modo_mascara in ('auto', 'ia') or (modo_mascara == 'magic' and not studio)
    # v5.5.8 (pedido del usuario): el GANCHO (el primer tramo de captions detrás de la persona, en los primeros segundos) con Magic Mask en Studio
    # también en «auto»; el resto sigue con el recorte de la IA local (Magic Mask en todo el video llegó a cerrar Resolve)
    magic_gancho = studio and modo_mascara == 'auto' and op.get('pro_magic_gancho', True) is not False
    video = plan.get('video') or ''
    t5 = bool(plan.get('tema5'))                     # Tema 5: la edición completa con el sistema de la skill (edicion_pro_tema5); los Text+ de GO, de respaldo
    # v5.5.8: con captions editables (por defecto) los Temas 5 y 6 dejan los Text+ de GO como captions DE VERDAD (Inspector › editar texto) y usan
    # las mismas mecánicas de captions que los Temas 1–4 (detrás de la persona, sin tapar caras, abajo en las escenas); sus gráficos siguen igual.
    # `cap_t5` = el Tema 5/6 con sus captions de Remotion (no editables), solo si el usuario lo apaga.
    cap_t5 = t5 and (plan.get('opciones') or {}).get('pro_captions_editables', True) is False
    soltar_gpu(texto=not t5)                         # v5.5.4: la GPU para Resolve y el Magic Mask (el Tema 5 aún usa la IA de texto: la suelta él al acabar)
    ligero = bool(plan.get('ligero'))              # Temas 1–4 sin la PRO: solo legibilidad, acompañantes, color y la regla de la cara (edicion_pro_temas)
    neon_tema = bool(plan.get('kitneon'))          # v5.5.13: Tema 1 neón = el estilo del kit: sin persona encima, iconos 3D, acompañantes ni punch-in alterno
    ex_neon = set(op.get('_neon_extras') or []) if neon_tema and not ligero else set()   # …salvo lo que el usuario encendió en el menú lateral
    if neon_tema and plan.get('kitneon_motions') and not plan.get('_neon_ajustado'):
        import kit_neon_motions as KM            # donde hay un motion de abajo, ese caption sobra (el motion ya lo dice); antes de lo del menú
        plan['kitneon'] = KM.ajustar_captions(plan['kitneon'], plan['kitneon_motions'])
        plan['_neon_ajustado'] = True
    divididas = []
    # punch-in de 1,08 en V1 alterno cuando hay saltos (pausas quitadas): lo coloca colocar_pro y las cuentas de posición ya lo tienen en cuenta
    # (antes de planificar el Tema 5: el sticker congelado y la pantalla final copian el encuadre de su clip)
    punch = []
    v1 = sorted(info.get('v1') or [], key=lambda c: c['ini'])
    if len(v1) >= 2 and not any(c.get('fx') for c in v1) and not ligero and not neon_tema:
        for n, c in enumerate(v1):
            if n % 2 == 1 and abs(float(c.get('zx') or 1.0) - 1.0) < 1e-3 and abs(float(c.get('zy') or 1.0) - 1.0) < 1e-3:
                c['zx'] = c['zy'] = PUNCH_IN
                punch.append([int(c['ini']), PUNCH_IN])
    if t5:
        import edicion_pro_persona as PE5
        import edicion_pro_tema5 as T5

        def det5(t):
            ruta, t_src, clip = _fuente_de(info, video, t)
            try:
                return _a_timeline(PE5.personas(ruta, t_src), clip, W, H) if PE5.disponible() else None
            except Exception:
                return None

        def foto5(t):
            ruta, t_src, _clip = _fuente_de(info, video, t)
            return T5.foto(ruta, t_src)

        def recorte5(t):                             # el sticker del gancho: la persona recortada con la IA local y el fondo, como en el timeline
            ruta, t_src, clip = _fuente_de(info, video, t)
            try:
                import edicion_pro_tema5_mm as MM5
                rgb = PE5.fotograma(ruta, t_src) if PE5.disponible() else None
                return MM5.imagenes_sticker(rgb, PE5.mate(rgb), clip, W, H) if rgb is not None else None
            except Exception:
                return None

        def cara5(t):                                # la pantalla final: la cara en el círculo y el fondo
            ruta, t_src, clip = _fuente_de(info, video, t)
            try:
                import edicion_pro_tema5_mm as MM5
                rgb = PE5.fotograma(ruta, t_src) if PE5.disponible() else None
                det = PE5.personas(ruta, t_src) if rgb is not None else None
                return MM5.imagenes_final(rgb, det, clip, W, H) if det and det.get('personas') else None
            except Exception:
                return None
        if plan.get('estilo_t5') == 'editorial':      # Tema 6: el mapa oscuro a pantalla completa no es de su estilo (va la tarjeta blanca del mapa)
            plan['piezas'] = [p for p in plan['piezas'] if p.get('pieza') not in T5.PIEZAS_QUE_QUEDAN]
        quedan = [p for p in plan['piezas'] if p.get('pieza') in T5.PIEZAS_QUE_QUEDAN]      # órbita, plantillas, escenas OGraf…: no son de este sistema
        nuevas, divididas = T5.planificar(plan, vertical, op.get('pro_densidad') or 'media', video, det_de=det5, foto_de=foto5,
                                          ia=op.get('pro_ia_local', True) is not False, idioma=plan.get('idioma') or 'es', estado=decir,
                                          recorte_de=recorte5, cara_de=cara5, usuario=str(op.get('pro_usuario') or ''),
                                          estilo=plan.get('estilo_t5') or 'skill')
        if not cap_t5:                               # captions editables: fuera los captions de Remotion (y sus velos); los Text+ de GO se quedan
            nuevas = [q for q in nuevas if q.get('pieza') not in ('subtitulo', 'velo_caption')]
        plan['piezas'] = quedan + nuevas
    if plan.get('_marcas'):                          # v5.22: Efectos › «Posición»: lo que el usuario marcó manda (antes de vestir, colocar y renderizar)
        try:
            dur_m = float(plan.get('duracion') or 0) or None
            pool = list(plan.get('_pool') or [])
            if t5:                                   # (Temas 5/6: solo piezas de SU sistema; del plan general, las que quedan)
                pool = [p for p in pool if p.get('pieza') in T5.PIEZAS_QUE_QUEDAN]
            puestas = _marcas_libres(plan, dur_m, pool)
            m_pil = _marca(plan, 'pildora')
            if t5 and m_pil:                         # la píldora de los Temas 5/6 viene en sus piezas: la de cada marca
                propias = [p for p in plan['piezas'] if _seccion(p) == 'pildora']
                elegidas = _ligadas(propias, m_pil, 'píldora')
                if m_pil.get('modo') != 'suma':
                    plan['piezas'] = [p for p in plan['piezas'] if _seccion(p) != 'pildora' or any(p is e for e in elegidas)]
            _marcas_broll(plan, dur_m)
            if puestas:
                decir(f'Edición PRO: {len(puestas)} efecto(s) en las posiciones que elegiste…')
        except Exception:
            try:
                import registro
                registro.excepcion(origen='edición PRO (posiciones)')
            except Exception:
                pass
    clave = hashlib.sha1(f'{video}|{W}x{H}@{fps}'.encode('utf-8')).hexdigest()[:10]
    carpeta = OG.ruta_larga(CARPETA / clave)
    carpeta.mkdir(parents=True, exist_ok=True)
    # v5.5.13: Tema 1 neón con la PRO: la PLACA del kit (cámara con muelle, deriva, desenfoques) renderizada en otro hilo mientras va lo demás;
    # solo si V1 es el video entero (con pausas quitadas no cuadraría con la fuente)
    hilo_placa, placa_res = None, {}
    v1_neon = sorted(info.get('v1') or [], key=lambda c: c['ini'])
    # v5.27: GO con el AUDIO del timeline (pulsado sin volver a soltar el video): la imagen es la del clip de V1; el .wav no tiene y la placa
    # fallaba («tuple index out of range») y el mapa de cámara también, así que el Tema 1 se quedaba sin «detrás de ti»
    video_img = video
    if Path(str(video)).suffix.lower() in AUDIOS and len(v1_neon) == 1 and v1_neon[0].get('ruta'):
        video_img = str(v1_neon[0]['ruta'])
    if neon_tema and not ligero and plan.get('kitneon_motions') is not None and len(v1_neon) == 1 and not int(v1_neon[0].get('izq') or 0):
        # (v5.5.14: SIN «import threading» aquí: lo volvía local en toda la función y, sin este tramo, «Motions completo» caía con UnboundLocalError)
        def _placa():
            try:
                import kit_neon_placa as PLA
                placa_res['ruta'] = PLA.para_pro(video_img, plan, carpeta, W, H, fps, progreso=lambda f: placa_res.update(f=float(f)))
            except Exception:
                placa_res['ruta'] = None
        hilo_placa = threading.Thread(target=_placa, daemon=True, name='placa-neon')
        hilo_placa.start()
    # v5.5.9 (el usuario: «más tareas en paralelo, más rapidez»): lo que no depende de nada de lo de abajo arranca YA, en otro hilo, y se recoge
    # donde antes se hacía: «Motions completo» (su render de Remotion corre mientras se buscan las personas, se recortan y se revisan los
    # gráficos) y la descarga del B-roll de stock (la red, mientras la GPU trabaja)
    fondo = {}

    def _motions_completo():
        try:
            import motions_completo as MCO
            bl = [{'ini': b['ini'], 'fin': b['fin'], 'palabras': [{'texto': x, 't': round(max(0.0, float(t) - b['ini']), 3)} for x, t in b.get('palabras') or []]}
                  for b in _bloques_captions()]
            dur_mc = float(plan.get('duracion') or 0) or (max(b['fin'] for b in bl) + 0.5 if bl else 0.0)
            fondo['mc_dur'] = dur_mc
            # sin la IA de texto: con ella el plan tardaba ~110 s (y volvía a cargar en la GPU el modelo que la PRO suelta para Resolve) para
            # unas pocas propuestas que ya pesan menos que las reglas
            try:                                                         # v5.20: el estilo elegido en Efectos › Motions completo
                import estilos_pro as EST
                estilo_mc = EST.motions_completo(op)
            except Exception:
                estilo_mc = {}
            if plan.get('tema') == 'neon' and plan.get('_palabras') and not estilo_mc:     # v5.5.17: el Tema 1: con las piezas del kit «TEMA 1» (kit_neon_completo); con un estilo elegido, el del usuario
                import kit_neon_completo as KC
                fondo['mc'] = KC.crear(plan['_palabras'], dur_mc, W, H, fps, carpeta, plan.get('idioma') or 'es', video_img, decir) if dur_mc > 1.0 else None
                fondo['mc_neon'] = True
            else:
                fondo['mc'] = MCO.crear(bl, dur_mc, W, H, fps, carpeta, plan.get('idioma') or 'es', plan.get('perfil') or {}, video_img, decir,
                                        ia=bool(op.get('pro_motions_ia', False)), estilo=estilo_mc) if bl and dur_mc > 1.0 else None
        except Exception as e:
            fondo['mc_error'] = e

    def _broll():
        try:
            import broll
            import efectos_visuales
            clave_b = broll.clave_guardada(efectos_visuales.opciones_guardadas())
            fondo['broll'] = list(broll.preparar(plan['broll'], 'v' if vertical else 'h', clave_b, decir))
        except Exception as e:
            fondo['broll_error'] = e

    hilos_fondo = {}
    if op.get('pro_motions_completo'):
        hilos_fondo['mc'] = threading.Thread(target=_motions_completo, name='pro-motions-completo', daemon=True)
    if plan.get('broll'):
        decir('Edición PRO: buscando las tomas de B-roll…')
        hilos_fondo['broll'] = threading.Thread(target=_broll, name='pro-broll', daemon=True)
    for h in hilos_fondo.values():
        h.start()
    import edicion_pro_persona as PE
    hay_ia = PE.disponible()
    graficos, persona = [], []
    ventanas, forzadas = {}, set()                 # forzadas: escenas «fondo sustituido» sin sitio encima de la cabeza → pantalla completa
    decir('Edición PRO: buscando a las personas del video…')
    # v5.5.2 REGLA OFICIAL (usuario): nada tapa una CARA ni un CAPTION — ni los gráficos, ni las plantillas, ni el kit, ni los emojis — y todo queda
    # repartido. Los captions de la PRO (Temas 5/6) se colocan PRIMERO; luego cada gráfico de delante esquiva las caras, los captions de ese momento
    # (los de los Temas 1–4 del manifiesto, con sitio para su emoji arriba o abajo) y los demás gráficos que ya estén en pantalla a la vez.
    bloques_cap = _bloques_captions()
    puestos = []                                                       # [(ini, fin, arriba, abajo)] de lo ya colocado delante (fracción del alto)
    for p in sorted(plan['piezas'], key=lambda q: 0 if q['pieza'] == 'subtitulo' else 1):
        det, clip = None, None
        p['_valores0'] = dict(p['valores'])
        if hay_ia and (p.get('ajustar') or p.get('persona')):
            ruta, t_src, clip = _fuente_de(info, video, (p['ini'] + p['fin']) / 2.0)
            try:
                det = PE.personas(ruta, t_src)
            except Exception:
                det = None
        if p.get('ajustar'):
            extra = _obstaculos(p, bloques_cap, puestos) if p['capa'] == 'delante' and p['pieza'] not in ('subtitulo', 'orbita') else []
            det_tl = _a_timeline(det, clip, W, H)
            _ajustar_posiciones(p, det_tl, vertical, extra)
            if p['pieza'] == 'subtitulo' and det_tl and det_tl.get('personas'):
                p['_caras'] = _caras(det_tl)                           # (T5.coordinar: el acompañante bajo este caption tampoco tapa estas caras)
            if p['pieza'] == 'orbita' and p.get('remotion') and det:     # los iconos de Remotion son algo más grandes: un poco más abajo del mentón
                p['valores']['ry'] = round(float(p['valores'].get('ry', 5.0)) + 1.3, 2)
            if p['pieza'] == 'subtitulo' and p.pop('quitar', False):  # sin sitio libre de caras: abajo y más pequeño (un caption no se quita)
                p['valores'].update(y=84.0 if vertical else 86.0, escala=0.8)
            if t5:
                T5.subir_detras(p)
                # v5.5.10: la clave «detrás» solo se lee si va POR ENCIMA de la cabeza; si la persona está tan arriba que el centro del texto
                # cae a media cabeza o más abajo (p. ej. alguien de cuerpo entero caminando: «Europa» quedó tapado), va delante, normal.
                if p['pieza'] == 'subtitulo' and p['capa'] == 'detras' and det_tl and det_tl.get('personas'):
                    yc = float(p['valores'].get('y', 30.0)) / 100.0
                    if any(yc > k['bbox'][1] + 0.5 * (k.get('cabeza') or {}).get('alto', 0.0) for k in det_tl['personas']):
                        p['valores'] = dict(p['_valores0'], modo='normal', y=T5.Y_NORMAL[vertical]) if p.get('_valores0') else dict(p['valores'], modo='normal', y=T5.Y_NORMAL[vertical])
                        p['capa'], p['persona'] = 'subs', False
            caja = _caja_vertical(p)                                    # (ya en su sitio final: lo que venga después lo esquiva)
            if caja and not p.get('quitar') and (p['capa'] == 'delante' or p['pieza'] == 'subtitulo'):
                puestos.append((p['ini'], p['fin']) + caja)
        if p.get('persona') and p['capa'] in ('detras', 'velo'):
            k = (p['ini'], p['fin'])
            if k not in ventanas:
                ventanas[k] = det
            if p.get('forzar_pantalla'):
                forzadas.add(k)
    # v5.5.3: una escena a pantalla completa del director solo tapa a QUIEN HABLA: si en ese tramo el video ya enseña otra cosa (su propio B-roll,
    #         un cartel, una foto: nadie en cuadro en al menos 2 de 3 fotogramas), se quita: no se tapa el material del usuario
    if hay_ia and not t5:
        for p in plan['piezas']:
            if not p.get('escena_mg') or p.get('quitar'):
                continue
            vistos = 0
            for t in (p['ini'] + 0.3, (p['ini'] + p['fin']) / 2.0, p['fin'] - 0.3):
                try:
                    ruta, t_src, _c = _fuente_de(info, video, t)
                    dd = _personas(ruta, t_src)
                    vistos += 1 if dd and dd.get('personas') else 0
                except Exception:
                    vistos += 1
            if vistos < 2:
                p['quitar'] = True
                p['motivo'] = p.get('motivo', '') + ' · quitada: el video ya enseña otra toma'
    if t5:
        T5.coordinar(plan['piezas'])                 # el indicador de pasos / el deslizador, debajo de los captions ya colocados
    # la persona de cada ventana (si no hay nadie, el titular queda delante y sin velo)
    sin_persona = set(forzadas)
    for (a, b), det in ventanas.items():
        f0, f1 = int(round(a * fps)), int(round(b * fps))
        if (a, b) in forzadas or not hay_ia or not det or not det.get('personas') or modo_mascara == 'no':
            sin_persona.add((a, b))
            continue
        ruta, t_src, clip = _fuente_de(info, video, a)
        _r2, _t2, clip2 = _fuente_de(info, video, max(a, b - 1.0 / fps))
        if clip is not None and clip2 is not None and clip is not clip2:
            sin_persona.add((a, b))                                   # cruza un corte de V1 (pausas quitadas): el recorte no seguiría a la persona
            continue
        ref = int(round(((a + b) / 2.0 - a) * fps))
        if usar_magic:
            puntos = PE.puntos_fusion(det)
            comp = _comp_magic(puntos, ref, carpeta / f'magic_{f0}_{f1}.comp', f'CCProMagic{f0}', efecto=fx_persona)
            persona.append({'ini': f0, 'fin': f1, 'modo': 'magic', 'comp': str(OG.ruta_larga(comp)), 'ref': ref, 'herramienta': f'CCProMagic{f0}'})
        elif usar_ia:
            decir('Edición PRO: recortando a la persona con IA local…')
            destino = carpeta / f'persona_{f0}_{f1}.mov'
            try:
                if not destino.exists():
                    PE.recorte_prores(ruta, t_src, t_src + (b - a) + MARGEN_RECORTE_S, destino)
                persona.append({'ini': f0, 'fin': f1, 'modo': 'clip', 'archivo': str(OG.ruta_larga(destino))})
            except Exception:
                sin_persona.add((a, b))
        else:
            sin_persona.add((a, b))
    # B-roll de stock (se descarga ahora: tras los captions, así GO no espera la red antes)
    tomas = []
    if 'broll' in hilos_fondo:                                         # (se descargaba en paralelo desde el principio)
        hilos_fondo['broll'].join()
        try:
            for ev in fondo.get('broll') or []:
                tomas.append({'ini': int(round(float(ev['ini']) * fps)), 'dur': float(ev['dur']), 'archivo': str(OG.ruta_larga(ev['archivo'])),
                              'palabra': ev.get('palabra', ''), '_s': float(ev['ini'])})
        except Exception:
            tomas = []
    plan['_broll_puesto'] = [{'ini': t['_s']} for t in tomas]
    # captions DETRÁS de la persona (lo que hace que valga la pena el Magic Mask)
    encima, tramos = [], []
    a_cuadro_detras, ctx_detras = None, None
    # v5.5.20 (el usuario: «más inteligente, con Magic Mask… igual en los Temas 1 a 6… solo Studio; en Free no aparece»): SOLO en Resolve Studio y
    # SIEMPRE con Magic Mask (puntos solo sobre PERSONAS: la IA local los pone; nunca objetos), con su salida cacheada (colocar_pro: render cache
    # de Fusion = el matte con alfa ya calculado); en Free ni en el MP4 hay «detrás de ti». La intensidad del menú dice cuántos y cuánto tapan.
    # El Tema 1 da sus bloques (los clips neón) y, con la placa, la detección y el recorte salen de la PLACA (lo que se ve, con sus zooms).
    if hay_ia and studio and modo_mascara != 'no' and not cap_t5 and not ligero and (not neon_tema or 'detras' in ex_neon):
        ocupado = [(p['ini'] - 0.1, p['fin'] + 0.1) for p in plan['piezas'] if p['pieza'] != 'marco']
        ocupado += [(m['ini'] - 0.1, m['fin'] + 0.1) for m in plan.get('kitneon_motions') or [] if neon_tema]   # (Tema 1: nunca tapa un motion del kit)
        ocupado += [(t['_s'] - 0.1, t['_s'] + t['dur'] + 0.1) for t in tomas]
        ocupado += [((a - info['base']) / fps, (b - info['base']) / fps) for a, b in info.get('ocupado') or []]
        try:                                     # v5.33: durante el zoom de la intro del gancho la persona recortada no casaría con V1
            import intros_gancho
            if intros_gancho.activa(op):
                ocupado.append((0.0, intros_gancho.fin_zoom_s(op) + 0.05))
        except Exception:
            pass
        bloques_tema, a_cuadro = None, None
        if neon_tema:
            import kit_neon as KN
            bloques_tema = KN.bloques_pro(plan.get('kitneon') or [])
            if hilo_placa is not None:
                try:
                    import kit_neon_placa as PLA
                    a_cuadro = PLA.mapa_camara(video_img, plan, W, H)
                except Exception:
                    bloques_tema = []                                    # sin saber dónde queda la persona en la placa, nada detrás
        try:
            tramos = _captions_detras(info, video, fps, ocupado, op.get('pro_densidad') or 'media', decir,
                                      preferidos=[tuple(x) for x in plan.get('detras_pref') or []], W=W, H=H,
                                      intensidad=intensidad_detras(op), bloques=bloques_tema, a_cuadro=a_cuadro,
                                      marcas=_marca(plan, 'detras'), cortes=plan.get('_cortes'))
        except Exception:
            try:                                 # (v5.27: antes se callaba y las marcas «no hacían nada» sin decir por qué)
                import registro
                registro.excepcion(origen='edición PRO (captions detrás de ti)')
            except Exception:
                pass
            tramos = []
        a_cuadro_detras = a_cuadro                                       # (v5.29: las entradas «encima» se arman al final, con la placa ya hecha)
        ctx_detras = {'ocupado': ocupado, 'bloques': bloques_tema, 'preferidos': [list(x) for x in plan.get('detras_pref') or []]}
    # el resto de los bloques de captions: ninguno tapa una cara (y colocar_pro aparta sus emojis)
    mover = []
    if hay_ia and not cap_t5 and not neon_tema:
        try:
            pantallas = [(p['ini'] - 0.1, p['fin'] + 0.1) for p in plan['piezas'] if p.get('pantalla') and (p['ini'], p['fin']) not in ventanas]
            pantallas += [(t['_s'] - 0.1, t['_s'] + t['dur'] + 0.1) for t in tomas]
            sin_cara = _captions_sin_cara(info, video, pantallas, tramos, W, H)
            for c in sin_cara:
                mover.append({'ini': int(round(c['ini'] * fps)), 'fin': int(round(c['fin'] * fps)), 'subir': round(c['subir'] * H, 1),
                              'caras': _caras_redondas(c['caras']), 'caja': c.get('caja')})
        except Exception:
            mover, sin_cara = [], []
    else:
        sin_cara = []
    # v5.5.3: mientras dura una escena a pantalla completa del director (Escenas9), los captions de los Temas 1–4 bajan a la parte de abajo
    if not cap_t5:
        try:
            import edicion_pro_escenas as ES
            esc = [(p['ini'], p['fin']) for p in plan['piezas'] if p.get('escena_mg') and not p.get('quitar')]
            for bq in (_bloques_captions() if esc else []):
                a, z = bq['ini'], bq['fin']
                if not any(a < e1 - 0.1 and e0 + 0.1 < z for e0, e1 in esc):
                    continue
                yc, medio = (bq['arriba'] + bq['abajo']) / 2.0, (bq['abajo'] - bq['arriba']) / 2.0
                y = min(ES.Y_CAPTIONS[vertical] / 100.0, 0.97 - medio)
                if yc >= y - 0.02:
                    continue                                          # ya iba abajo
                clave = (int(round(a * fps)), int(round(z * fps)))
                mover = [m for m in mover if (m['ini'], m['fin']) != clave]
                mover.append({'ini': clave[0], 'fin': clave[1], 'subir': round((yc - y) * H, 1), 'caras': [], 'caja': [round(y - medio, 4), round(y + medio, 4)]})
        except Exception:
            pass
    # iconos 3D flotando junto a los captions (en vez del emoji de ese bloque)
    iconos3d, sin_emoji = [], []
    try:
        subidas = {round(c['ini'], 2): c['subir'] for t in tramos for c in t['cues']}
        subidas.update({round(c['ini'], 2): c['subir'] for c in sin_cara})
        caras_de = {round(c['ini'], 2): c.get('caras') or [] for t in tramos for c in t['cues']}
        caras_de.update({round(c['ini'], 2): c['caras'] for c in sin_cara})
        ocupado3d = [(p['ini'] - 0.1, p['fin'] + 0.1) for p in plan['piezas'] if p.get('pantalla')] + [(t['_s'], t['_s'] + t['dur']) for t in tomas]
        # v5.25: «Emojis animados» (Lottie 2D / 3D en movimiento) SUSTITUYEN a los iconos 3D fijos; apagados en el menú, no va ninguno
        emo_on = ('emoji' in ex_neon) if neon_tema else bool(op.get('pro_emojis', True))
        if emo_on and not ligero and not cap_t5:
            bl_emo = _bloques_captions()
            if neon_tema:
                import kit_neon as KN
                bl_emo = KN.bloques_pro(plan.get('kitneon') or [])
            oc_emo = ocupado3d + [(p['ini'] - 0.1, p['fin'] + 0.1) for p in plan['piezas'] if p.get('capa') == 'iconos']
            oc_emo += [(m['ini'] - 0.1, m['fin'] + 0.1) for m in plan.get('kitneon_motions') or []] if neon_tema else []
            decir('Edición PRO: eligiendo los emojis animados…')
            emojis_pro, ventanas_emo = _emojis_pro(bl_emo, oc_emo, subidas, caras_de, W, H, op, _marca(plan, 'emoji'))
            plan['piezas'] = list(plan.get('piezas') or []) + emojis_pro
            sin_emoji += [[int(round(a * fps)) - 2, int(round(z * fps))] for a, z in ventanas_emo]
            plan['_emojis_pro'] = [p['motivo'] for p in emojis_pro]
    except Exception:
        try:
            import registro
            registro.excepcion(origen='edición PRO (emojis animados)')
        except Exception:
            pass
        iconos3d = []
    acento = (plan.get('direccion') or {}).get('acento') or '#ffb020'
    for c in iconos3d:
        ruta = OG.construir('icono3d', dict(c['valores'], acento=acento), max(0.4, c['fin'] - c['ini']), carpeta, fps=fps, ancho=W, alto=H)
        graficos.append({'capa': 'iconos', 'ini': int(round(c['ini'] * fps)), 'archivo': str(ruta), 'nombre': 'PRO · Icono 3D'})
        sin_emoji.append([int(round(c['ini'] * fps)) - 2, int(round(c['fin'] * fps))])
    plan['_iconos3d'] = iconos3d
    color_claves = None
    if (ligero or not t5) and not plan.get('solo_captions') and (not neon_tema or 'pildora' in ex_neon):   # Temas 1–4: el velo de legibilidad y los acompañantes, YA con la regla de la cara aplicada (mover)
        try:                                         # v5.5.4: también CON la Edición PRO (pedido: «algún motion debajo de los captions, aunque sea 1 o 2»)
            import edicion_pro_temas as TM
            if neon_tema:                            # v5.5.13: Tema 1 con «Píldora» en el menú: bajo SUS captions neón y nunca con un motion del kit
                import kit_neon as KN
                import kit_neon_motions as KM
                extra = TM.piezas(info, video, plan.get('idioma') or 'es', W, H, fps, [],
                                  dict(plan, piezas=list(plan.get('piezas') or []) + KM.piezas(plan.get('kitneon_motions') or [])),
                                  maximo=3, bloques=KN.bloques_pro(plan['kitneon']))
            else:
                extra = TM.piezas(info, video, plan.get('idioma') or 'es', W, H, fps, mover, plan, maximo=None if ligero else 3)
            m_pil = _marca(plan, 'pildora') if not neon_tema else None
            if m_pil:                                # v5.22: Efectos › «Posición»: la píldora de los captions que suenan en cada marca
                todas = extra if ligero else TM.piezas(info, video, plan.get('idioma') or 'es', W, H, fps, mover, plan, maximo=None)
                elegidas = _ligadas([p for p in todas if _seccion(p) == 'pildora'], m_pil, 'píldora')
                for e in elegidas:
                    e['_marca'] = True
                if m_pil.get('modo') != 'suma':
                    extra = [p for p in extra if _seccion(p) != 'pildora'] + elegidas
                else:
                    extra = extra + [e for e in elegidas if not any(abs(p['ini'] - e['ini']) < 0.05 for p in extra)]
            extra = [p for p in extra if p.get('_marca') or not any(p['ini'] < t['fin'] and t['ini'] < p['fin'] for t in tramos)]   # (no bajo un caption que va detrás; la marcada, sí)
            plan['piezas'] = list(plan.get('piezas') or []) + extra
            if ligero:
                color_claves = TM.color_claves(info, video, fps)
        except Exception:
            pass
    gris = [[int(round(a * fps)), int(round(b * fps))] for a, b in plan.get('gris') or []]
    try:                                             # v5.5.7: también lo que se añadió al aplicar (Tema 5/6, acompañantes): solo motions permitidos
        import motions_catalogo as MC
        plan['piezas'] = MC.filtrar(plan.get('piezas') or [], op)
    except Exception:
        pass
    decir('Edición PRO: preparando los gráficos animados…')
    try:
        _motions_a_ograf(plan['piezas'], W, H)                     # v5.5.8: las tarjetas de dato, editables en el Inspector (OGraf)
    except Exception:
        pass
    try:                                                           # v5.5.8: el VIGILANTE (reglas + IA local) antes de renderizar nada
        import vigilante_pro as VG
        dichas = [(float(t), str(x)) for b in _bloques_captions() for x, t in b.get('palabras') or []]
        VG.revisar_plan(plan['piezas'], dichas)
        if op.get('pro_ia_local', True):
            decir('Edición PRO: la IA revisa que cada gráfico encaje con lo que se dice…')
            VG.revisar_ia(plan['piezas'], dichas, plan.get('idioma') or 'es', estado=decir)
    except Exception:
        pass
    neon = []
    if plan.get('kitneon'):                         # v5.5.13: el Tema 1 neón: sus captions con el motor del kit (KitNeon) en PRO-SUBS / PRO-SUBS2
        import kit_neon as KN
        if plan.get('kitneon_motions'):              # con la PRO: los motions del kit (los captions ya se ajustaron a ellos arriba)
            import kit_neon_motions as KM
            plan['piezas'] = list(plan.get('piezas') or []) + KM.piezas(plan['kitneon_motions'])
        neon = KN.piezas(plan['kitneon'])
        plan['piezas'] = list(plan.get('piezas') or []) + neon
    try:                                             # v5.20: el estilo y los colores elegidos en Efectos › Edición PRO (mandan sobre el color del video y el neón)
        import estilos_pro as EST
        vestidas = EST.vestir(plan, op, t56=bool(t5))
        plan['_estilos'] = vestidas
        if vestidas:
            decir('Edición PRO: con tus estilos de Efectos (' + ', '.join(f"{(EST.seccion(k) or {}).get('titulo', k)}: {n}" for k, n in vestidas.items()) + ')')
    except Exception:
        pass
    # las animaciones de Remotion (mapa + bandera…): todas en una tanda, con un solo navegador; sin Remotion, esas escenas no van
    rm_salida, rm_hechos = {}, {}
    try:
        import edicion_pro_remotion as RM
        trab = []
        for p in plan['piezas']:
            if p['pieza'] == 'subtitulo' and p['capa'] == 'detras' and (p['ini'], p['fin']) in sin_persona:
                import edicion_pro_tema5 as T5
                p['valores'] = dict(p['_valores0'], modo='normal', y=T5.Y_NORMAL[vertical])
                p['capa'], p['persona'] = 'subs', False
            if p['pieza'] in ('orbita', 'foco') and t5 and (p['ini'], p['fin']) in sin_persona:
                p['quitar'] = True                                    # sin la persona recortada: ni órbita (taparía la cara) ni foco (todo gris)
            if p.get('remotion') and not p.get('quitar'):
                props = dict(p['valores'], _ancho=W, _alto=H, _fps=fps, _dur=round(max(0.6, p['fin'] - p['ini']), 3))
                sal = RM.salida_para(p['remotion'], props, carpeta)
                rm_salida[id(p)] = sal
                trab.append({'id': p['remotion'], 'props': props, 'salida': sal})
        rm_hechos = RM.renderizar(trab, decir) if trab else {}
    except Exception:
        rm_hechos = {}

    def con_sombra(p, sal):
        """Tema 5: la clave DETRÁS de la persona con la sombra de la persona encima de las letras (la silueta del fotograma del medio)."""
        destino = Path(str(sal)).with_name(Path(str(sal)).stem + '_sombra.mov')
        if destino.exists():
            return destino
        try:
            import edicion_pro_tema5_mm as MM5
            ruta, t_src, clip = _fuente_de(info, video, (p['ini'] + p['fin']) / 2.0)
            rgb = PE.fotograma(ruta, t_src)
            if rgb is None:
                return None
            fx, fy = MM5.mapeo(clip, W, H)
            return destino if MM5.sombra_en_clip(sal, destino, MM5.silueta(PE.mate(rgb), fx, fy, W, H)) else None
        except Exception:
            return None
    gris_foco = []
    for p in plan['piezas']:
        capa = p['capa']
        if p.get('quitar'):
            continue                                                  # no había sitio sin tapar la cara
        if p['pieza'] == 'foco':                                      # Tema 5: el fondo en blanco y negro (colocar_pro) bajo la persona a color
            gris_foco.append([int(round(p['ini'] * fps)), int(round(p['fin'] * fps))])
            continue
        if p.get('remotion'):
            sal = rm_salida.get(id(p))
            if sal is not None and rm_hechos.get(str(sal)):
                if t5 and hay_ia and p['pieza'] == 'subtitulo' and p['capa'] == 'detras':
                    decir('Edición PRO: la sombra de la persona sobre la palabra de detrás…')
                    sal = con_sombra(p, sal) or sal
                graficos.append({'capa': p['capa'], 'ini': int(round(p['ini'] * fps)), 'archivo': str(OG.ruta_larga(sal)), 'alfa': True,
                                 'dur': round(p['fin'] - p['ini'], 3),             # v5.5.8: el vigilante comprueba que el clip dure lo que debe
                                 # v5.5.13: los motions del Tema 1 NO se llaman «Caption…»: colocar_pro._revisar_persona pasaba los «PRO · Caption» de
                                 # PRO-DETRAS sin persona encima a PRO-DELANTE y, si allí no cabían, los BORRABA (se perdían las pantallas divididas)
                                 'nombre': 'PRO · ' + ('Motion neón' if p['pieza'] == 'neon_motion' else
                                                       {'Ubicacion': 'Mapa + bandera', 'Subtitulo': 'Caption', 'PasosT5': 'Pasos', 'DeslizadorT5': 'Deslizador',
                                                         'EscenaT5': 'Escena', 'AcompananteT5': 'Acompañante', 'VeloCaptionT': 'Velo de legibilidad',
                                                         'TarjetaT5': 'Tarjeta', 'OrbitaT5': 'Órbita', 'StickerT5': 'Sticker',
                                                         'FinalT5': 'Pantalla final', 'EditorialT6': 'Editorial', 'KitNeon': 'Caption neón'}.get(p['remotion'])
                                                        or p.get('plantilla') or p['remotion'])})
            continue
        if (p['ini'], p['fin']) in sin_persona:
            if p['pieza'] == 'orbita':
                continue                                              # sin nadie a quien rodear, no hay órbita
            if capa == 'velo':
                continue                                              # sin la persona delante, el velo solo oscurecería
            if capa == 'detras':
                capa = 'delante'
            if p.get('pantalla'):
                p['valores'] = dict(p['_valores0'])                     # escena sin persona: a pantalla completa, la pieza centrada
        dur = max(0.4, p['fin'] - p['ini'])
        ruta = OG.construir(p['pieza'], p['valores'], dur, carpeta, fps=fps, ancho=W, alto=H)
        graficos.append({'capa': capa, 'ini': int(round(p['ini'] * fps)), 'archivo': str(ruta), 'nombre': f"PRO · {OG.ESQUEMAS[p['pieza']]['nombre']}"})
    # Tema 5: la transición con zoom en los cortes (los de V1 —pausas quitadas— o, con un solo clip, los del propio video), lejos de lo demás
    zoom, plan['_zoom'] = [], []
    if t5:
        try:
            import edicion_pro_tema5_mm as MM5
            cortes = [(int(c['ini']) - info['base']) / fps for c in v1[1:]]
            if len(v1) == 1:
                c = v1[0]
                desde = (int(c['ini']) - info['base']) / fps - int(c.get('izq') or 0) / float(c.get('fps') or fps)
                cortes += [desde + float(x) for x in plan.get('_cortes_video') or []]
            elif not v1:
                cortes += [float(x) for x in plan.get('_cortes_video') or []]
            puestas = [p for p in plan['piezas'] if not p.get('quitar')]
            ocup = [(p['ini'], p['fin']) for p in puestas if p.get('capa') in ('fondo', 'detras', 'velo') or p.get('pantalla') or p.get('persona')]
            ocup += [(d['ini'], d['fin']) for d in divididas] + [(t['_s'], t['_s'] + t['dur']) for t in tomas]
            for t in MM5.transiciones(cortes, ocup, max([p['fin'] for p in puestas] or [0.0])):
                zoom.append([int(round(t * fps)), 5, 6])
                plan['_zoom'].append(t)
        except Exception:
            zoom = []
    rng = random.Random(PL.semilla_de(video, [], int(op.get('pro_variacion') or 0)))
    sonidos = []
    voz_db = None
    if op.get('pro_sonidos', True):                                   # diseño de sonido profesional (edicion_pro_sonido): whooshes, texturas, risers + hits
        import edicion_pro_sonido as PS
        voz_db = PS.nivel_voz(video)                                  # los efectos, siempre bajo la voz de ESTE video
        familias = dict(op.get('pro_sonidos_familias') or {})          # v5.5.7: lo que el usuario apagó en Sonido › Edición PRO
        extra_db = NIVEL_SONIDOS_DB.get(str(op.get('pro_sonidos_nivel') or 'normal'), 0.0)
        for e in PS.disenar(plan, fps, rng, choques=[] if cap_t5 else [(f - info['base']) / fps for f in info.get('sfx') or []],
                            cortes=[(int(f) - info['base']) / fps for f, _z in punch], voz_db=voz_db):
            if familias.get(FAMILIA_DE_PISTA.get(str(e.get('pista')), 'textura'), True) is False:
                continue
            e['db'] = float(e.get('db') or 0.0) + extra_db
            try:                                                      # el volumen, DENTRO del archivo (Resolve 21 ignora el de clip por script)
                e['archivo'] = str(OG.ruta_larga(_con_ganancia(e['archivo'], e.get('db', 0.0))))
                e['db'] = 0.0
            except Exception:
                e['archivo'] = str(OG.ruta_larga(_copia_de_usuario(e['archivo'])))     # nunca de la carpeta del programa: Resolve la retendría
            sonidos.append(e)
    # v5.5.7 (el usuario, Tema 4: «emojis encima de los captions, iconos y motions juntos»): donde la PRO enseña algo (acompañante, órbita, cifra,
    # escena, tarjeta, titular…), el emoji de GO se apaga: una sola cosa a la vez junto al caption
    if not cap_t5:
        for p in plan['piezas']:
            if p.get('quitar') or p.get('pieza') in ('subtitulo', 'velo', 'velo_caption', 'marco', 'fondo') or p.get('capa') == 'velo':
                continue
            sin_emoji.append([int(round(float(p['ini']) * fps)) - 3, int(round(float(p['fin']) * fps)) + 3])
    subs = [p for p in plan['piezas'] if p['pieza'] == 'subtitulo']
    subs_ok = sum(1 for p in subs if rm_hechos.get(str(rm_salida.get(id(p)))))
    neon_ok = sum(1 for p in neon if rm_hechos.get(str(rm_salida.get(id(p)))))
    if hilo_placa is not None:
        decir('Edición PRO: terminando la placa del Tema 1 neón (cámara y desenfoques)…')
        import time as _t
        hasta = _t.time() + 1800
        while hilo_placa.is_alive() and _t.time() < hasta:     # v5.5.13: con señales (el vigilante de GO la daba por atascada a los 4 min)
            hilo_placa.join(15)
            if hilo_placa.is_alive():
                decir(f"Edición PRO: terminando la placa del Tema 1 neón ({int(100 * placa_res.get('f', 0.0))} %)…")
        if placa_res.get('ruta'):
            graficos.append({'capa': 'placa', 'ini': 0, 'archivo': str(OG.ruta_larga(placa_res['ruta'])), 'alfa': False,
                             'dur': round(float(plan.get('duracion') or 0), 3), 'nombre': 'PRO · Placa neón (cámara)'})
    if tramos:                                                     # v5.29: la persona de «detrás de ti», recortada por la IA (matte con alfa)
        encima = _encima_de(tramos, info, video, fps, W, H, carpeta, a_cuadro_detras, neon_tema, fx_persona, usar_magic,
                            placa=placa_res.get('ruta'), decir=decir)
    if 'mc' in hilos_fondo:                                        # v5.5.8: «Motions completo», encima de todo (v5.5.9: se hacía en paralelo)
        try:
            import motions_completo as MCO
            if hilos_fondo['mc'].is_alive():
                decir('Edición PRO: terminando «Motions completo»…')
            hilos_fondo['mc'].join()
            if fondo.get('mc_error') is not None:
                raise fondo['mc_error']
            mc, dur_mc = fondo.get('mc'), float(fondo.get('mc_dur') or 0.0)
            m_mc = _marca(plan, 'motions_completo')
            tramos_mc = _tramos_motions(mc, m_mc, dur_mc) if (mc and m_mc and m_mc.get('modo') != 'suma') else None
            if mc and tramos_mc:                      # v5.22: «solo mis marcas»: el video de motions solo en los tramos marcados (colocar_pro: desde/frames)
                for a, b in tramos_mc:
                    f0 = int(round(a * fps))
                    graficos.append({'capa': 'motions', 'ini': f0, 'desde': f0, 'frames': max(2, int(round(b * fps)) - f0), 'archivo': str(OG.ruta_larga(mc)),
                                     'nombre': 'PRO · Motions completo', 'dur': round(dur_mc, 3), 'opaco': True})
            elif mc:
                graficos.append({'capa': 'motions', 'ini': 0, 'archivo': str(OG.ruta_larga(mc)), 'nombre': 'PRO · Motions completo', 'dur': round(dur_mc, 3),
                                 'opaco': True})
            if mc:
                if op.get('pro_sonidos', True):                           # v5.5.9: sus sonidos (whoosh al entrar cada tarjeta, clics, pops…), bajo la voz
                    import edicion_pro_sonido as PS
                    familias = dict(op.get('pro_sonidos_familias') or {})
                    extra_db = NIVEL_SONIDOS_DB.get(str(op.get('pro_sonidos_nivel') or 'normal'), 0.0)
                    if fondo.get('mc_neon'):
                        import kit_neon_completo as KC
                        eventos_mc = KC.sonidos(KC.plan_de(mc), fps, voz_db if voz_db is not None else PS.nivel_voz(video))
                    else:
                        eventos_mc = MCO.sonidos(mc, fps, rng, voz_db if voz_db is not None else PS.nivel_voz(video))
                    for e in eventos_mc:
                        if familias.get(FAMILIA_DE_PISTA.get(str(e.get('pista')), 'textura'), True) is False:
                            continue
                        if tramos_mc and not any(a * fps - 1 <= float(e.get('ini') or 0) < b * fps for a, b in tramos_mc):
                            continue                                      # (v5.22: solo los sonidos de los tramos marcados)
                        e['db'] = float(e.get('db') or 0.0) + extra_db
                        try:
                            e['archivo'] = str(OG.ruta_larga(_con_ganancia(e['archivo'], e.get('db', 0.0))))
                            e['db'] = 0.0
                        except Exception:
                            e['archivo'] = str(OG.ruta_larga(_copia_de_usuario(e['archivo'])))
                        if plan.get('_ai_sound'):
                            e['origen'] = 'motions'                   # v5.34: el AI Sound Director los deja (van con el diseño de su proyecto)
                        sonidos.append(e)
        except Exception as e:
            try:
                import registro
                registro.aviso(f'Motions completo no se pudo hacer: {type(e).__name__}: {e}', 'motions')
            except Exception:
                pass
    try:                                                           # v5.5.8: el vigilante con ffmpeg: nada roto, vacío ni incompleto llega a Resolve
        import vigilante_pro as VG
        VG.revisar_clips(graficos, fps)
    except Exception:
        pass
    datos = {'fps': fps, 'inicio': info['base'], 'graficos': graficos, 'persona': persona, 'sonidos': sonidos, 'cache': True,
             'captions_propios': bool((cap_t5 and subs and subs_ok >= 0.9 * len(subs)) or (neon and neon_ok >= 0.9 * len(neon))),
             'captions_sonidos': bool(neon), 'color_claves': color_claves,
             'dividida': [[int(round(d['ini'] * fps)), int(round(d['fin'] * fps)), round(d['bajar'] * H, 1)] for d in divididas
                          if any(p.get('remotion') == 'EscenaT5' and abs(p['ini'] - d['ini']) < 1e-3 and rm_hechos.get(str(rm_salida.get(id(p))))
                                 for p in plan['piezas'])],
             'broll': [{k: v for k, v in t.items() if k != '_s'} for t in tomas], 'encima': encima, 'mover': mover, 'punch': punch,
             'sin_emoji': sin_emoji, 'gris': gris, 'gris_foco': gris_foco, 'zoom': zoom,
             'resumen': plan.get('resumen', '')}
    try:                                                              # v5.5.2, el rectificador: riser solo en la intro, cada sonido con su porqué, una cámara
        import rectificador
        motivos = rectificador.pro_final(datos, fps, {'eventos': plan.get('_fx_eventos') or []})
        if motivos:
            plan['_rectificado'] = motivos
            decir(f'Edición PRO: el rectificador quitó {len(motivos)} cosas que no iban')
    except Exception:
        pass
    try:                                                              # v5.34: con el AI Sound Director al mando, sus sonidos sustituyen a los de la PRO
        import director_sonido
        datos['sonidos'] = director_sonido.sonidos_pro(plan, datos['sonidos'], fps)
    except Exception:
        pass
    try:
        import archivos_seguros
        archivos_seguros.escribir_json(PLAN_JSON, datos, indent=1)
    except Exception:
        PLAN_JSON.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding='utf-8')
    try:
        import sidecar_lua
        sidecar_lua.escribir_sidecar(PLAN_JSON, datos)
    except Exception:
        pass
    if ctx_detras is not None:                                        # v5.29: para que «Listo» en Efectos › Posición lo ponga sin rehacer GO
        ctx_detras['aplicados'] = _aplicados_de(encima, fps)          # v5.30: lo que quedó puesto (la tira de Posición lo enseña)
        _guardar_contexto_detras(plan, info, video, video_img, fps, W, H, carpeta, neon_tema, placa_res.get('ruta'), ctx_detras, op)
    instalar_plantillas_una_vez()
    limpiar_cache(conservar=carpeta)
    decir('Edición PRO: colocando la edición en Resolve' + (' (Magic Mask)…' if (persona and usar_magic) or encima else '…'))
    if info.get('via') == 'mcp':
        import resolve_mcp
        script = carpeta_recursos() / 'colocar_pro.py'
        if os.environ.get('CINECAPTIONS_TRAZA_PRO'):                    # (pruebas: un envoltorio que anota cada paso en un archivo)
            script = Path(os.environ['CINECAPTIONS_TRAZA_PRO'])
        ok, mensaje = resolve_mcp.ejecutar_py(script, timeout=600)
    else:
        import resolve_bridge
        if resolve_bridge.modo_actual() == 'manual' and not resolve_bridge.lanzar_puente_auto():
            return False, 'La Edición PRO en Resolve Free necesita el Puente de CineCaptions abierto en Resolve.'
        ok, mensaje = resolve_bridge.ejecutar('edicion_pro', timeout=600)
    return ok, mensaje or plan.get('resumen', '')


def _guardar_contexto_detras(plan, info, video, video_img, fps, W, H, carpeta, neon_tema, placa, ctx, op):
    """v5.29: lo del último GO que hace falta para poner «detrás de ti» DESPUÉS (aplicar_detras), sin rehacer nada: el timeline (V1, inicio),
    los bloques de captions, lo ocupado, la placa del Tema 1 y su plan de cámara, los cortes y el recorte de pausas."""
    try:
        import time as _t
        import archivos_seguros
        import posiciones_pro as POS
        bloques = ctx.get('bloques')
        if bloques is None:
            bloques = _bloques_captions()
        d = {'version': 1, 'hecho': round(_t.time()), 'media': str(video), 'imagen': str(video_img or video),
             'clave': POS.clave_video(video_img or video), 'fps': fps, 'W': W, 'H': H, 'info': info, 'timeline': info.get('nombre'),
             'bloques': bloques, 'ocupado': [list(x) for x in ctx.get('ocupado') or []], 'preferidos': ctx.get('preferidos') or [],
             'densidad': op.get('pro_densidad') or 'media', 'cortes': [list(c) if isinstance(c, (list, tuple)) else c for c in plan.get('_cortes') or []],
             'neon': bool(neon_tema), 'placa': str(placa) if placa else None, 'carpeta': str(carpeta), 'recorte': plan.get('_recorte'),
             'aplicados': ctx.get('aplicados') or [],
             'plan_placa': ({k: plan.get(k) for k in ('kitneon', 'kitneon_motions', '_cortes', 'duracion', '_neon_ajustado')} if neon_tema else None)}
        archivos_seguros.escribir_json(DETRAS_CTX, json.loads(json.dumps(d, ensure_ascii=False, default=str)))
    except Exception:
        try:
            import registro
            registro.excepcion(origen='edición PRO (contexto de «detrás de ti»)')
        except Exception:
            pass


def _aplicados_de(encima, fps):
    """v5.30: el centro (s del timeline de GO) de cada caption que quedó DETRÁS de la persona."""
    return sorted({round((c['ini'] + c['fin']) / 2.0 / float(fps), 2) for e in encima or [] for c in e.get('cues') or []})


def aplicados_para(ruta, ctx):
    """v5.30 (el usuario: «en Efectos › Posición deben estar donde se aplicó»): los captions que están ahora DETRÁS de la persona en el timeline
    (los que puso GO por su cuenta o el último «Listo»), en el tiempo de la tira de `ruta`: con el video y las pausas quitadas por GO, de
    vuelta al tiempo del archivo; con el video y un GO hecho con el audio del timeline, más el desfase del clip. [] si no hay ninguno."""
    ts = [float(t) for t in (ctx or {}).get('aplicados') or []]
    if not ts:
        return []
    import posiciones_pro as POS
    es_audio = Path(str(ruta)).suffix.lower() in AUDIOS
    segs = ((ctx.get('recorte') or {}).get('segmentos') or []) if not es_audio else []
    if segs:                                                          # (la inversa de pausas.mapear)
        out = []
        for t in ts:
            acum = 0.0
            for a, b in segs:
                if t <= acum + (b - a) + 1e-6:
                    out.append(round(a + (t - acum), 2))
                    break
                acum += b - a
        return out
    if not es_audio and Path(str(ctx.get('media') or '')).suffix.lower() in AUDIOS:
        _img, desde, _d = POS.fuente_imagen(ctx['media'], duracion=False)
        return [round(t + float(desde or 0.0), 2) for t in ts]
    return [round(t, 2) for t in ts]


def contexto_detras(ruta):
    """El contexto de «detrás de ti» del último GO si fue de este video (o de su audio del timeline), o None. En un HILO (lee el disco)."""
    try:
        ctx = json.loads(DETRAS_CTX.read_text(encoding='utf-8'))
        import posiciones_pro as POS
        img = POS.fuente_imagen(ruta, duracion=False)
        claves = {POS.clave_video(ruta), POS.clave_video(img[0] or ruta)}
        if ctx.get('clave') in claves or POS.clave_video(ctx.get('media') or '') in claves:
            return ctx
    except Exception:
        pass
    return None


def mapa_a_timeline_go(ruta, ctx):
    """v5.32: la cuenta de _a_timeline_go para un segundo suelto (lo que lee el disco, una vez): t de la tira de `ruta` → t del timeline de ese
    GO, o None. La usa la tira para comprobar cada marca con los MISMOS bloques que usará «Listo» (posiciones_pro.reglas_go)."""
    import posiciones_pro as POS
    es_audio = Path(str(ruta)).suffix.lower() in AUDIOS
    segs = ((ctx.get('recorte') or {}).get('segmentos') or []) if not es_audio else []
    if segs:
        return lambda t: (lambda n: None if n is None else round(float(n), 3))(POS._mapear(float(t), segs))
    if not es_audio and Path(str(ctx.get('media') or '')).suffix.lower() in AUDIOS:
        _img, desde, _d = POS.fuente_imagen(ctx['media'], duracion=False)
        d = float(desde or 0.0)
        return lambda t: round(float(t) - d, 3) if float(t) - d >= 0 else None
    return lambda t: round(float(t), 3)


def _a_timeline_go(ruta, ctx, ts):
    """v5.30: la inversa de aplicados_para: segundos de la tira de `ruta` → segundos del timeline de ese GO."""
    f = mapa_a_timeline_go(ruta, ctx)
    return [x for x in (f(t) for t in ts) if x is not None]


def aplicar_detras(ruta, al_estado=None, marcas_tira=None, modo='solo', al_progreso=None):
    """v5.29 (el usuario: «cuando le dé Listo debe ponerlo automáticamente en la línea de tiempo; va a ser más útil que generar todo»): pone
    «Captions detrás de ti» con las marcas de Efectos › Posición en el timeline ABIERTO de Resolve, sin rehacer GO: con lo que guardó el último
    GO de ese video (DETRAS_CTX) decide los tramos (la misma regla, _captions_detras), recorta a la persona con la IA (matte con alfa) y
    colocar_pro, en modo «solo_encima», cambia SOLO eso. → (ok, mensaje, tramos puestos). En un HILO."""
    decir = al_estado or (lambda t: None)
    ctx = contexto_detras(ruta)
    if ctx is None:
        return False, 'Pulsa GO una vez con este video: después, «Listo» pone «detrás de ti» directo en tu timeline.', 0
    info = _info_timeline()
    if not info:
        return False, 'Abre DaVinci Resolve con el timeline de este video.', 0
    if info.get('via') != 'mcp' or 'studio' not in str(info.get('producto') or '').lower():
        return False, '«Captions detrás de ti» necesita DaVinci Resolve Studio.', 0
    ci = ctx.get('info') or {}
    if ([str(c.get('ruta')) for c in info.get('v1') or []] != [str(c.get('ruta')) for c in ci.get('v1') or []]
            or int(info.get('inicio') or 0) != int(ci.get('inicio') or 0)):
        return False, f'En Resolve está abierto otro timeline: abre «{ctx.get("timeline") or "el de tu último GO"}» y vuelve a darle a «Listo».', 0
    import posiciones_pro as POS
    fps, W, H = float(ctx['fps']), int(ctx['W']), int(ctx['H'])
    if marcas_tira is not None:                                       # v5.30: EXACTAMENTE lo de la tira (vacía = quitarlo del timeline)
        marcas = {'modo': modo if modo in ('solo', 'suma') else 'solo', 'ts': _a_timeline_go(ruta, ctx, marcas_tira)}
    else:
        marcas = (POS.para_plan(ctx['media'], ctx.get('recorte')) or {}).get('detras')
    a_cuadro = None
    if ctx.get('neon'):
        if not ctx.get('placa') or not Path(ctx['placa']).exists():
            return False, 'Falta la placa del Tema 1 de tu último GO: pulsa GO otra vez.', 0
        import kit_neon_placa as PLA
        a_cuadro = PLA.mapa_camara(ctx['imagen'], ctx.get('plan_placa') or {}, W, H)
    tramos = _captions_detras(ci, ctx['media'], fps, [tuple(x) for x in ctx.get('ocupado') or []], ctx.get('densidad') or 'media', decir,
                              preferidos=[tuple(x) for x in ctx.get('preferidos') or []], W=W, H=H, intensidad=intensidad_detras(),
                              bloques=ctx.get('bloques'), a_cuadro=a_cuadro, marcas=marcas, cortes=ctx.get('cortes'))
    op = opciones_guardadas()
    try:
        import estilos_pro as EST
        fx_persona = EST.efecto_persona(op)
    except Exception:
        fx_persona = None
    carpeta = Path(ctx.get('carpeta') or (CARPETA / 'detras'))
    carpeta.mkdir(parents=True, exist_ok=True)
    progreso = al_progreso or (lambda f, texto='': None)                # v5.31: la barra de «Listo» (recortes 0–85 %, Resolve hasta el 100 %)
    progreso(0.02, 'Buscando dónde va cada caption…')
    encima = _encima_de(tramos, ci, ctx['media'], fps, W, H, carpeta, a_cuadro, bool(ctx.get('neon')), fx_persona,
                        str(op.get('pro_mascara') or 'auto') == 'magic', placa=ctx.get('placa'), decir=decir,
                        progreso=lambda f, texto: progreso(0.05 + 0.8 * f, texto))
    try:
        datos = json.loads(PLAN_JSON.read_text(encoding='utf-8'))
    except Exception:
        datos = {}
    if int(datos.get('inicio') if datos.get('inicio') is not None else -1) != int(ci.get('base', ci.get('inicio') or 0)):
        datos = {'fps': fps, 'inicio': int(ci.get('base', ci.get('inicio') or 0)), 'cache': True}   # (el plan guardado es de otro timeline)
    nuevos = [(c['ini'], c['fin']) for e in encima for c in e['cues']]
    datos['mover'] = [m for m in datos.get('mover') or [] if not any(m['ini'] < b and a < m['fin'] for a, b in nuevos)]
    datos.update(encima=encima, solo_encima=True)
    import archivos_seguros
    archivos_seguros.escribir_json(PLAN_JSON, datos, indent=1)
    decir('Edición PRO: poniendo «detrás de ti» en tu timeline…')
    progreso(0.88, 'Poniéndolo en tu timeline de Resolve…')
    try:                                                              # v5.32: la reproducción que dejó GO (menú «Reproducir») hace que Resolve no
        import colocacion                                             # conteste a los scripts y cambiar el timeline mientras tanto lo tumbó
        fin_v1 = max([int(c.get('fin') or 0) for c in ci.get('v1') or []] or [0]) - int(ci.get('inicio') or 0)
        colocacion.detener_reproduccion(dura_s=(fin_v1 / fps) if fin_v1 > 0 else None)
    except Exception:
        pass

    def en_resolve(seg):                                              # v5.32: la barra sigue viva y dice si Resolve no responde (antes, parada)
        try:
            import resolve_bridge
            if resolve_bridge.resolve_colgado(8.0):
                progreso(0.9, 'Resolve no responde; espero a que termine…')
                return
        except Exception:
            pass
        progreso(0.88 + 0.1 * (1.0 - 0.5 ** (float(seg) / 6.0)), 'Poniéndolo en tu timeline de Resolve…')
    try:
        import resolve_mcp
        # v5.33: síncrono (dentro de la llamada del MCP, sin un hilo que cambie el timeline mientras la interfaz de Resolve lo dibuja: así
        # se caía); con Magic Mask (rastreo de hasta 150 s) no cabe en los 60 s del MCP y va en su hilo, como antes
        ok, mensaje = resolve_mcp.ejecutar_py(carpeta_recursos() / 'colocar_pro.py', timeout=600, on_progreso=en_resolve,
                                              sincrono=str(op.get('pro_mascara') or 'auto') != 'magic')
    finally:
        datos['solo_encima'] = False                                  # (un GO o re-aplicar de después vuelve a ponerlo todo, ya con esto)
        archivos_seguros.escribir_json(PLAN_JSON, datos, indent=1)
    if ok:                                                            # v5.30: la tira de Posición enseñará esto (lo que hay ahora en el timeline)
        try:
            import time as _t
            ctx.update(aplicados=_aplicados_de(encima, fps), hecho=round(_t.time()))
            archivos_seguros.escribir_json(DETRAS_CTX, ctx)
        except Exception:
            pass
        progreso(1.0, 'Listo en tu timeline')
    return ok, mensaje, len(encima)


SONIDOS_USUARIO = Path.home() / 'DaVinciSubtitles' / 'edicion_pro_sonidos'      # (no es la caché: los proyectos de Resolve siguen apuntando a ellos)


def _con_ganancia(ruta, db):
    """v5.4.52 (auditoría del render: los efectos sonaban hasta 8 dB POR ENCIMA de la voz): Resolve 21 no aplica el volumen de un clip de audio
    puesto por script (SetProperty('Volume') no existe; es 'AudioVolume' y tampoco lo respeta siempre), así que todos quedaban a 0 dB. Como los
    efectos de GO (sfx_rules.con_volumen), el volumen va DENTRO del archivo: una copia en la carpeta del usuario (nunca la del programa) con la
    ganancia ya aplicada, en estéreo. Se rehace si cambia el original."""
    import av
    import numpy as np
    origen = Path(str(ruta))
    db = round(float(db or 0.0), 1)
    destino = SONIDOS_USUARIO / f'{origen.stem}_v{int(round(db * 10)):+d}.wav'
    if destino.is_file() and destino.stat().st_mtime >= origen.stat().st_mtime:
        return destino
    SONIDOS_USUARIO.mkdir(parents=True, exist_ok=True)
    with av.open(str(origen)) as c:
        st = c.streams.audio[0]
        sr = int(st.rate or 48000)
        rs = av.AudioResampler(format='fltp', layout='stereo', rate=sr)
        partes = [g.to_ndarray() for fr in c.decode(st) for g in rs.resample(fr)]
        partes += [g.to_ndarray() for g in rs.resample(None)]
    x = np.clip(np.concatenate(partes, axis=1) * (10 ** (db / 20.0)), -1.0, 1.0)
    tmp = destino.with_name(destino.stem + '.tmp.wav')
    with av.open(str(tmp), 'w', format='wav') as o:
        s = o.add_stream('pcm_s16le', rate=sr)
        s.layout = 'stereo'
        fr = av.AudioFrame.from_ndarray((x.T.reshape(1, -1) * 32767.0).astype(np.int16), format='s16', layout='stereo')
        fr.sample_rate = sr
        for pk in s.encode(fr):
            o.mux(pk)
        for pk in s.encode():
            o.mux(pk)
    tmp.replace(destino)
    return destino


def _copia_de_usuario(ruta):
    """Resolve vigila la carpeta de cada medio que importa y no deja reemplazarla mientras está abierto: si un sonido saliera de la carpeta del
    programa, el instalador fallaría («Acceso denegado a …/Programs/CineCaptions», v5.4.51). Se le da una COPIA en la carpeta del usuario
    (como efectos_visuales._copia_de_usuario); se rehace si falta o cambió de tamaño."""
    r = Path(str(ruta))
    try:
        from sfx_rules import base_recursos
        Path(r).resolve().relative_to(Path(base_recursos()).resolve())
    except Exception:
        return r                                                       # ya es del usuario (o no se sabe): tal cual
    try:
        destino = SONIDOS_USUARIO / r.parent.name / r.name
        if not destino.is_file() or destino.stat().st_size != r.stat().st_size:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(r, destino)
        return destino
    except Exception:
        return r


def instalar_plantillas_una_vez():
    """Las 9 piezas en la caja de herramientas de Resolve («CineCaptions PRO», para ponerlas a mano), una vez por versión de las piezas."""
    marca = CARPETA / f'.plantillas_{OG.VERSION_PIEZAS}'
    if marca.exists():
        return
    if OG.instalar_plantillas() is not None:
        try:
            CARPETA.mkdir(parents=True, exist_ok=True)
            marca.write_text('ok', encoding='utf-8')
        except OSError:
            pass


def carpeta_recursos() -> Path:
    try:
        from sfx_rules import base_recursos
        return Path(base_recursos()) / 'edicion_pro'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'edicion_pro'


def limpiar_cache(maximo_mb=1500, conservar=None):
    """Borra lo más viejo de ~/DaVinciSubtitles/edicion_pro si pasa de `maximo_mb` (los .ograf y los recortes se rehacen solos). NUNCA la carpeta
    `conservar` (la del video que se acaba de editar): v5.4.52, con muchas pasadas del mismo video esa carpeta sola pasaba del tope y se borraban
    los clips recién hechos (Resolve «no colocó ningún gráfico»)."""
    try:
        guardar = Path(str(conservar)).resolve() if conservar else None
        cajas = sorted((d for d in CARPETA.iterdir() if d.is_dir() and d.name not in ('modelos', 'pruebas')
                        and (guardar is None or d.resolve() != guardar)), key=lambda d: d.stat().st_mtime)
        total = sum(f.stat().st_size for d in cajas for f in d.rglob('*') if f.is_file())
        while cajas and total > maximo_mb * 1e6:
            d = cajas.pop(0)
            tam = sum(f.stat().st_size for f in d.rglob('*') if f.is_file())
            import shutil
            shutil.rmtree(d, ignore_errors=True)
            total -= tam
    except Exception:
        pass
