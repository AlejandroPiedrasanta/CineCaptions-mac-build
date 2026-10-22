"""Movimiento sobre el video principal con una composición de Fusion (v5.4.8): zoom lento continuo, temblor con los golpes de sonido, transiciones en los cortes
(zoom-blur, whip pan, glitch) y fondo desenfocado cuando el video no llena el cuadro.

Por qué Fusion y no un clip encima: una composición de Fusion se aplica al clip ANTES de la etapa de color, así que la corrección de color del usuario sigue valiendo
y no hay que renderizar ni apilar un duplicado del video. La comp es un texto (`.comp`) que Resolve importa con `TimelineItem.ImportFusionComp(ruta)` (como las
animaciones de los emojis); todo el movimiento va en EXPRESIONES de Fusion (Lua) que dependen del tiempo en fotogramas, así que no hay claves que escribir.

`texto_comp(...)` solo arma texto: se puede probar sin Resolve. `colocar_efectos.py` (corre dentro de Resolve) la importa en el clip de V1.
"""
from __future__ import annotations

# ----------------------------------------------------------------------------------------------------------------------- ajustes
ZOOM_LENTO = {'suave': 0.06, 'normal': 0.10, 'fuerte': 0.18}                  # cuánto crece el cuadro de principio a fin
TEMBLOR = {'suave': (0.006, 0.020), 'normal': (0.011, 0.035), 'fuerte': (0.018, 0.055)}   # (desplazamiento, golpe de zoom) por golpe
DURACION_TEMBLOR_S = 0.36
TRANSICIONES_V1 = ('zoom_blur', 'whip', 'glitch')
ZOOM_SALTOS = {'suave': 0.06, 'normal': 0.10, 'fuerte': 0.16}              # el «punch-in» que alterna en cada corte seco (pausas quitadas)
ZOOM_INTRO = {'suave': 0.05, 'normal': 0.09, 'fuerte': 0.15}               # v5.5: cuánto se acerca el cuadro mientras sube el riser de la intro (se suelta de golpe en su pico)
SUELTA_INTRO_S = 0.45                                                        # lo que tarda en volver a su tamaño después del pico
VENTANA_CORTE_S = 0.34                                                       # lo que dura la transición (la mitad antes y la mitad después del corte)
NOMBRE_COMP = 'CineCaptions FX'
BORDES_ESPEJO = 3                                                            # Transform › Edges: 0 Canvas · 1 Wrap · 2 Duplicate · 3 Mirror


def _n(x, d=4):
    return ('%.' + str(d) + 'f') % float(x)


def _golpe(h, dur):
    """Envolvente de UN golpe en el fotograma h: 0 antes, sube en 1 fotograma y baja lineal hasta 0 en `dur` fotogramas."""
    return 'math.max(0,1-(time-%s)/%s)*math.min(1,math.max(0,time-%s+1))' % (_n(h, 2), _n(dur, 2), _n(h, 2))


def _triangulo(c, w):
    """1 en el fotograma c y 0 a `w` fotogramas de distancia (en los dos sentidos)."""
    return 'math.max(0,1-math.abs(time-%s)/%s)' % (_n(c, 2), _n(w, 2))


def _suma(terminos):
    return '(' + '+'.join(terminos) + ')' if terminos else '0'


def _tool(clase, nombre, entradas, pos):
    """El texto de una herramienta de la comp. `entradas`: lista de líneas ya formadas `Nombre = Input { … },`."""
    cuerpo = ''.join('\t\t\t\t%s\n' % l for l in entradas)
    return ('\t\t%s = %s {\n\t\t\tInputs = {\n%s\t\t\t},\n\t\t\tViewInfo = OperatorInfo { Pos = { %d, 50 } },\n\t\t},\n' % (nombre, clase, cuerpo, pos))


def _num(nombre, valor, expr=None):
    if expr:
        return '%s = Input { Value = %s, Expression = "%s", },' % (nombre, _n(valor, 4), expr)
    return '%s = Input { Value = %s, },' % (nombre, _n(valor, 4))


def _origen(nombre, de='Output'):
    return 'Input = Input { SourceOp = "%s", Source = "%s", },' % (nombre, de)


def texto_comp(duracion_frames, fps, zoom=None, golpes=None, nivel_temblor='normal', cortes=None, transicion=None, fondo=None, saltos=None, zoom_saltos=None, zoom_intro=None,
               intro=None):
    """El texto de la composición (None si no hay nada que hacer).

    zoom       'suave' | 'normal' | 'fuerte' | None   zoom lento continuo (de 100 % a 100 % + x a lo largo del clip)
    golpes     [fotograma, …]                          temblor + golpe de zoom en cada uno (fotogramas desde el INICIO del clip)
    cortes     [fotograma, …]                          dónde hay cortes entre tomas
    transicion 'zoom_blur' | 'whip' | 'glitch' | None  qué se hace en cada corte
    saltos     [fotograma, …] + zoom_saltos 'suave'|'normal'|'fuerte'  el cuadro se acerca en un tramo sí y en el siguiente no (cada corte seco del «quitar pausas»)
    zoom_intro {'pico': fotograma, 'nivel': 'suave'|'normal'|'fuerte'} | None   el cuadro se acerca cada vez más deprisa hasta `pico` (el pico del riser) y se suelta de golpe: «zoom hit»
    intro      {'tipo': intros_gancho.ZOOMS, 'desde': fotograma} | None   v5.33: el zoom HACIA FUERA de la intro del gancho (con giro, temblor,
                                                       latigazo, desenfoque o RGB según el tipo; las expresiones salen de intros_gancho)
    fondo      {'lienzo': (W, H), 'clip': (w, h), 'desenfoque': px} | None
                                                       copia del video ampliada y desenfocada DETRÁS (cuando el video no tiene la forma del timeline)
    """
    dur = max(2, int(duracion_frames))
    fps = float(fps or 30)
    golpes = sorted(set(int(h) for h in (golpes or []) if 0 <= h < dur))
    cortes = sorted(set(int(c) for c in (cortes or []) if 0 < c < dur))
    if transicion not in TRANSICIONES_V1:
        cortes = []
    if zoom not in ZOOM_LENTO:
        zoom = None
    saltos = sorted(set(int(c) for c in (saltos or []) if 0 < c < dur)) if zoom_saltos in ZOOM_SALTOS else []
    if not (isinstance(zoom_intro, dict) and zoom_intro.get('nivel') in ZOOM_INTRO):
        zoom_intro = None
    ex = None
    if isinstance(intro, dict) and intro.get('tipo'):
        import intros_gancho
        ex = intros_gancho.expresiones(intro['tipo'], fps, int(intro.get('desde') or 0))
    if not (zoom or golpes or cortes or fondo or saltos or zoom_intro or ex):
        return None
    herramientas = []
    ultimo = 'MediaIn1'
    x = 200

    def encadenar(nombre):
        nonlocal ultimo, x
        ultimo = nombre
        x += 200

    # --- fondo desenfocado: la copia ampliada y borrosa va debajo del video (Merge: el video encima)
    if fondo:
        # el lienzo de la comp pasa a ser el del timeline (si no, Resolve mete el resultado en el cuadro con barras): debajo, el video ampliado hasta llenarlo y
        # desenfocado; encima, el video entero ajustado al ancho (o al alto)
        lw, lh = fondo['lienzo']
        cw, ch = fondo['clip']
        llena = max(lw / float(cw), lh / float(ch))
        cabe = min(lw / float(cw), lh / float(ch))
        herramientas.append(_tool('Background', 'FondoLienzo', [_num('UseFrameFormatSettings', 0), _num('Width', lw, None), _num('Height', lh, None), _num('TopLeftRed', 0), _num('TopLeftGreen', 0),
                                                              _num('TopLeftBlue', 0), _num('TopLeftAlpha', 0)], x))
        x += 200
        herramientas.append(_tool('Scale', 'FondoLleno', [_num('XSize', llena), _num('YSize', llena), _origen('MediaIn1')], x))
        x += 200
        herramientas.append(_tool('Blur', 'FondoBlur', ['Filter = Input { Value = FuID { "Gaussian" }, },', _num('XBlurSize', fondo.get('desenfoque', 40)), _origen('FondoLleno')], x))
        x += 200
        herramientas.append(_tool('Merge', 'FondoMerge1', ['Background = Input { SourceOp = "FondoLienzo", Source = "Output", },', 'Foreground = Input { SourceOp = "FondoBlur", Source = "Output", },',
                                                        'PerformDepthMerge = Input { Value = 0, },'], x))
        x += 200
        herramientas.append(_tool('Scale', 'FondoAjuste', [_num('XSize', cabe), _num('YSize', cabe), _origen('MediaIn1')], x))
        x += 200
        herramientas.append(_tool('Merge', 'FondoMerge2', ['Background = Input { SourceOp = "FondoMerge1", Source = "Output", },', 'Foreground = Input { SourceOp = "FondoAjuste", Source = "Output", },',
                                                         'PerformDepthMerge = Input { Value = 0, },'], x))
        encadenar('FondoMerge2')
    # --- Transform: zoom lento + golpe de zoom + temblor + whip pan + sacudida del glitch
    hay_tr = bool(zoom or golpes or saltos or zoom_intro or ex or (cortes and transicion in ('whip', 'glitch')))
    if hay_tr:
        dur_golpe = max(3.0, DURACION_TEMBLOR_S * fps)
        desp, pico = TEMBLOR.get(nivel_temblor, TEMBLOR['normal'])
        base = '(1+%s*time/%d)' % (_n(ZOOM_LENTO[zoom]), dur) if zoom else '1'
        env = _suma([_golpe(h, dur_golpe) for h in golpes]) if golpes else None
        ventana = max(3.0, VENTANA_CORTE_S * fps)
        medio = ventana / 2.0
        size_expr = base
        if env:
            size_expr = '%s*(1+%s*%s)' % (base, _n(pico), env)
        if saltos:                                                # n = cuántos cortes secos van ya; los tramos impares llevan el acercamiento
            n = '+'.join('((time>=%s) and 1 or 0)' % _n(c, 2) for c in saltos)
            size_expr = '%s*(1+%s*math.fmod(%s,2))' % (size_expr, _n(ZOOM_SALTOS[zoom_saltos]), n)
        if zoom_intro:                                            # sube con el cuadrado del tiempo (cada vez más tensión) hasta el pico y se suelta en SUELTA_INTRO_S con la misma curva
            h = float(zoom_intro.get('pico') or 0)
            a = ZOOM_INTRO[zoom_intro['nivel']]
            suelta = max(3.0, SUELTA_INTRO_S * fps)
            termino = '(time>=%s and %s*(math.max(0,1-(time-%s)/%s))^2 or 0)' % (_n(h, 2), _n(a), _n(h, 2), _n(suelta, 2))
            if h > 1:
                termino = '(time<%s and %s*(time/%s)^2 or 0)+%s' % (_n(h, 2), _n(a), _n(h, 2), termino)
            size_expr = '%s*(1+%s)' % (size_expr, termino)
        # el whip y el glitch mueven el cuadro: se agranda un poco ESE tramo para no enseñar el borde negro
        if cortes and transicion == 'whip':
            size_expr = '%s*(1+0.10*%s)' % (size_expr, _suma([_triangulo(c, medio) for c in cortes]))
        if cortes and transicion == 'glitch':
            size_expr = '%s*(1+0.05*%s)' % (size_expr, _suma([_triangulo(c, medio) for c in cortes]))
        dx = '0'
        dy = '0'
        ang = None
        if env:
            dx = '%s*%s*math.sin(time*7.3)' % (_n(desp), env)
            dy = '%s*%s*math.sin(time*5.9+1.7)' % (_n(desp * 0.8), env)
            ang = '%s*%s*math.sin(time*4.3+0.6)' % (_n(desp * 40.0), env)       # unos 0,4° en el golpe normal
        if cortes and transicion == 'whip':
            # antes del corte el cuadro se va hacia la derecha, después entra desde la izquierda
            partes = ['(%s)*(%s)' % (('(time<%s) and 1 or -1' % _n(c, 2)), _triangulo(c, medio)) for c in cortes]
            dx = '%s+0.34*%s' % (dx, _suma(partes))
        if cortes and transicion == 'glitch':
            sacudida = _suma([_triangulo(c, medio) for c in cortes])
            dx = '%s+0.045*%s*((math.sin(time*37.1)>0) and 1 or -1)' % (dx, sacudida)
            dy = '%s+0.012*%s*((math.sin(time*23.3)>0) and 1 or -1)' % (dy, sacudida)
        if ex:                                                    # v5.33: el zoom hacia fuera de la intro (multiplica a lo demás; vale 1 al acabar)
            size_expr = '%s*%s' % (size_expr, ex['size'])
            if ex['dx']:
                dx = '%s+%s' % (dx, ex['dx'])
            if ex['dy']:
                dy = '%s+%s' % (dy, ex['dy'])
            if ex['angulo']:
                ang = ex['angulo'] if ang is None else '%s+%s' % (ang, ex['angulo'])
        entradas = [_num('Size', 1, size_expr), _origen(ultimo)]
        if (cortes and transicion in ('whip', 'glitch')) or (ex and (ex['dx'] or ex['dy'] or ex['angulo'])):
            entradas.append('Edges = Input { Value = %d, },' % BORDES_ESPEJO)        # lo que sale del cuadro se refleja: nunca una franja negra
        if dx != '0' or dy != '0':
            entradas.append('Center = Input { Value = { 0.5, 0.5 }, Expression = "Point(0.5+%s, 0.5+%s)", },' % (dx, dy))
        if ang:
            entradas.append(_num('Angle', 0, ang))
        herramientas.append(_tool('Transform', 'Movimiento', entradas, x))
        encadenar('Movimiento')
    # --- glitch: el rojo y el azul se separan hacia los lados (cada canal por su lado y se vuelven a sumar con Screen)
    if cortes and transicion == 'glitch':
        ventana = max(3.0, VENTANA_CORTE_S * fps)
        medio = ventana / 2.0
        sep = '0.028*' + _suma([_triangulo(c, medio) for c in cortes]) + '*((math.sin(time*29.7)>0) and 1 or -1)'
        base_in = ultimo
        canales = (('R', (1, 0, 0), '0.5-%s' % sep), ('G', (0, 1, 0), None), ('B', (0, 0, 1), '0.5+%s' % sep))
        salidas = {}
        for letra, (r, g, b_), cx in canales:
            herramientas.append(_tool('ColorCorrector', 'Canal' + letra, [_num('MasterRedGain', r), _num('MasterGreenGain', g), _num('MasterBlueGain', b_), _origen(base_in)], x))
            x += 200
            if cx:
                herramientas.append(_tool('Transform', 'Mueve' + letra, ['Center = Input { Value = { 0.5, 0.5 }, Expression = "Point(%s, 0.5)", },' % cx, 'Edges = Input { Value = %d, },' % BORDES_ESPEJO,
                                                                      _origen('Canal' + letra)], x))
                x += 200
                salidas[letra] = 'Mueve' + letra
            else:
                salidas[letra] = 'Canal' + letra
        herramientas.append(_tool('Merge', 'GlitchM1', ['Background = Input { SourceOp = "%s", Source = "Output", },' % salidas['G'], 'Foreground = Input { SourceOp = "%s", Source = "Output", },' % salidas['R'],
                                                      'ApplyMode = Input { Value = "Screen", },', 'PerformDepthMerge = Input { Value = 0, },'], x))
        x += 200
        herramientas.append(_tool('Merge', 'GlitchM2', ['Background = Input { SourceOp = "GlitchM1", Source = "Output", },', 'Foreground = Input { SourceOp = "%s", Source = "Output", },' % salidas['B'],
                                                      'ApplyMode = Input { Value = "Screen", },', 'PerformDepthMerge = Input { Value = 0, },'], x))
        encadenar('GlitchM2')
    # --- transiciones con desenfoque en los cortes
    if cortes and transicion == 'zoom_blur':
        ventana = max(3.0, VENTANA_CORTE_S * fps)
        medio = ventana / 2.0
        largo = _suma([_triangulo(c, medio) for c in cortes])
        herramientas.append(_tool('DirectionalBlur', 'ZoomBlur', ['Type = Input { Value = 3, },', _num('Length', 0, '0.30*' + largo), _origen(ultimo)], x))
        encadenar('ZoomBlur')
    if cortes and transicion == 'whip':
        ventana = max(3.0, VENTANA_CORTE_S * fps)
        medio = ventana / 2.0
        largo = _suma([_triangulo(c, medio) for c in cortes])
        herramientas.append(_tool('DirectionalBlur', 'WhipBlur', ['Type = Input { Value = 0, },', _num('Length', 0, '0.22*' + largo), _num('Angle', 0), _origen(ultimo)], x))
        encadenar('WhipBlur')
    # --- v5.33: lo que acompaña al zoom de la intro (las mismas herramientas que las transiciones de arriba)
    if ex and ex['zblur']:
        herramientas.append(_tool('DirectionalBlur', 'IntroZoomBlur', ['Type = Input { Value = 3, },', _num('Length', 0, ex['zblur']), _origen(ultimo)], x))
        encadenar('IntroZoomBlur')
    if ex and ex['dblur']:
        herramientas.append(_tool('DirectionalBlur', 'IntroLatigo', ['Type = Input { Value = 0, },', _num('Length', 0, ex['dblur']), _num('Angle', 90),
                                                                     _origen(ultimo)], x))
        encadenar('IntroLatigo')
    if ex and ex['rgb']:                                          # el rojo a un lado y el azul al otro (como el glitch, sumados con Screen)
        base_in = ultimo
        salidas = {}
        for letra, (r, g, b_), cx in (('R', (1, 0, 0), '0.5-%s' % ex['rgb']), ('G', (0, 1, 0), None), ('B', (0, 0, 1), '0.5+%s' % ex['rgb'])):
            herramientas.append(_tool('ColorCorrector', 'IntroCanal' + letra, [_num('MasterRedGain', r), _num('MasterGreenGain', g), _num('MasterBlueGain', b_),
                                                                              _origen(base_in)], x))
            x += 200
            if cx:
                herramientas.append(_tool('Transform', 'IntroMueve' + letra, ['Center = Input { Value = { 0.5, 0.5 }, Expression = "Point(%s, 0.5)", },' % cx,
                                                                              'Edges = Input { Value = %d, },' % BORDES_ESPEJO, _origen('IntroCanal' + letra)], x))
                x += 200
                salidas[letra] = 'IntroMueve' + letra
            else:
                salidas[letra] = 'IntroCanal' + letra
        herramientas.append(_tool('Merge', 'IntroRGB1', ['Background = Input { SourceOp = "%s", Source = "Output", },' % salidas['G'],
                                                         'Foreground = Input { SourceOp = "%s", Source = "Output", },' % salidas['R'],
                                                         'ApplyMode = Input { Value = "Screen", },', 'PerformDepthMerge = Input { Value = 0, },'], x))
        x += 200
        herramientas.append(_tool('Merge', 'IntroRGB2', ['Background = Input { SourceOp = "IntroRGB1", Source = "Output", },',
                                                         'Foreground = Input { SourceOp = "%s", Source = "Output", },' % salidas['B'],
                                                         'ApplyMode = Input { Value = "Screen", },', 'PerformDepthMerge = Input { Value = 0, },'], x))
        encadenar('IntroRGB2')
    salida = ('\t\tMediaIn1 = MediaIn {\n\t\t\tViewInfo = OperatorInfo { Pos = { 0, 50 } },\n\t\t},\n'
              '\t\tMediaOut1 = MediaOut {\n\t\t\tInputs = {\n\t\t\t\tIndex = Input { Value = "0", },\n\t\t\t\t%s\n\t\t\t},\n\t\t\tViewInfo = OperatorInfo { Pos = { %d, 50 } },\n\t\t},\n'
              % (_origen(ultimo), x))
    return ('Composition {\n\tCurrentTime = 0,\n\tRenderRange = { 0, %d },\n\tGlobalRange = { 0, %d },\n\tTools = ordered() {\n%s%s\t},\n}\n'
            % (dur, dur, ''.join(herramientas), salida))


def escribir_comp(ruta, *args, **kwargs):
    """Escribe la comp en `ruta`. Devuelve True si había algo que escribir."""
    from pathlib import Path
    t = texto_comp(*args, **kwargs)
    if not t:
        return False
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(t, encoding='utf-8')
    return True
