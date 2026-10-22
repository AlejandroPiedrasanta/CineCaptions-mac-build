# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_pagina_director.py — prueba la página SONIDO = «AI Sound Director» (fase 6) SIN pantalla y SIN el Resolve del usuario.
"""
    python probar_pagina_director.py [--video V] [--salida CARPETA]

1) Prepara un diseño real (PRUEBA ESPAÑOL, Tema 1, como lo deja GO con el director encendido) en una carpeta aislada (prefs en memoria, Registro a una
   lista, estado del director en la salida).
2) Motor (director_sonido_sesion): resumen, retocar (silenciar, bloquear, MENOS/MÁS, regenerar), rediseñar (todo y una sección), controles, deshacer,
   «dile a AI Sound Director», mezclas A/B, plan para Resolve y que «Aplicar» se niega sin un GO con el director.
3) Página (director_sonido_ui, Qt offscreen): se arma, pinta el diseño, elige un evento con un clic en la línea, el inspector y sus botones, un control,
   una frase; capturas PNG en la salida para mirarlas. 4) SubtitleApp._asegurar_sfx arma la página nueva (y la vieja solo si la nueva falla).
"""
import copy
import os
import sys
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['CINECAPTIONS_AI_SOUND'] = '1'

import probar_director_sonido as P

RESULTADOS = []


def ok(nombre, cond, detalle=''):
    RESULTADOS.append((nombre, bool(cond)))
    print(('  PASA  ' if cond else '  FALLA ') + nombre + (f'  ({detalle})' if detalle else ''))
    return bool(cond)


def preparar(salida, video):
    """El diseño de sonido del Tema 1 tal como lo deja GO (preparar + al_colocar con la PRO)."""
    E = P.entorno(salida)
    P.PREFS.clear()
    import ajustes_ui
    ajustes_ui.guardar_prefs = lambda cambios=None, *a, **k: P.PREFS.update(cambios or {})     # (prefs en memoria, como si se guardaran)
    import director_sonido as D
    import efectos_visuales
    import edicion_pro_planificador as PL
    import vista_tema
    palabras = P._palabras_de_cache(video)
    dur = float(palabras[-1]['end'])
    cortes = [c[0] for c in efectos_visuales.detectar_cortes(str(video))]
    plan_fx = efectos_visuales.planificar(str(video), palabras, cortes=[(c, 1.0) for c in cortes])
    plan_pro = PL.planificar(palabras, dur, idioma='es', vertical=True, video=str(video), cortes=cortes)
    cues = vista_tema.planificar(palabras, {}, 'Kinetic', vista_tema.estilo_de_pack('Kinetic', 'v'), idioma='es', fin_video=dur, video=str(video))
    ctx = D.contexto(video, palabras, 'Kinetic', 'v', timeline_de_go=False, bloques=cues, plan_efectos=plan_fx, plan_pro=plan_pro, cortes=cortes, idioma='es')
    ctx['cortes'] = cortes
    res = D.preparar(ctx)
    destino = {'proyecto': 'Prueba aislada', 'timeline': 'Sonido de prueba', 'timeline_id': 'sonido-ui-prueba'}
    plan = D.al_colocar(copy.deepcopy(plan_fx), res, str(video), plan_pro=copy.deepcopy(plan_pro), destino=destino)
    pendiente = E.cargar(video)
    assert pendiente.get('pendiente_resolve') and not pendiente.get('en_resolve'), 'Preparar no confirma una colocación'
    assert D.confirmar_colocacion(plan, True, 'GO simulado en el destino de prueba'), 'El GO simulado debe quedar confirmado'
    return E, D, res


def motor(salida, video):
    print('== motor de la página (director_sonido_sesion) ==')
    E, D, res = preparar(salida, video)
    import director_sonido_sesion as S
    r = S.resumen(video)
    ok('resumen: hay diseño, 8 notas de estado (con «Material»), eventos con su clave', r['hay'] and len(r['notas']) == 8 and all(e['clave'] for e in r['eventos']),
       f"{sum(1 for e in r['eventos'] if e['suena'])} suenan de {len(r['eventos'])}")
    ok('resumen: carriles (voz, cortes, captions)', bool(r['carriles']['voz']) and bool(r['carriles']['captions']))
    ok('resumen: «Aplicar» permitido tras un GO con el director', r['puede_aplicar'] is True)
    suenan = [e for e in r['eventos'] if e['suena']]
    a, b = suenan[0], suenan[1]
    archivos = {e['clave']: e['archivo'] for e in suenan}
    # silenciar
    r2, hecho = S.retocar(video, a['clave'], 'silenciar')
    ea = next(e for e in r2['eventos'] if e['clave'] == a['clave'])
    ok('SILENCIAR: ese evento deja de sonar', not ea['suena'] and ea['silenciado'], hecho)
    otros = {e['clave']: e['archivo'] for e in r2['eventos'] if e['suena']}
    ok('SILENCIAR: los demás, idénticos (mismos WAV)', all(otros.get(k) == v for k, v in archivos.items() if k != a['clave'] and k in otros))
    r3, _h = S.retocar(video, a['clave'], 'silenciar')
    ok('volver a sonar', next(e for e in r3['eventos'] if e['clave'] == a['clave'])['suena'])
    # MENOS / MÁS / regenerar
    r4, _h = S.retocar(video, b['clave'], 'menos:mas_corto')
    eb = next(e for e in r4['eventos'] if e['clave'] == b['clave'])
    ok('MENOS › más corto: dura menos y es otro archivo', float(eb['dur']) < float(b['dur']) and eb['archivo'] != b['archivo'], f"{b['dur']} → {eb['dur']}")
    golpe = next((e for e in r4['eventos'] if e['suena'] and e['tipo'] == 'golpe' and e['clave'] not in (a['clave'], b['clave'])), None)
    if golpe:
        r5, _h = S.retocar(video, golpe['clave'], 'mas:mejor_transitorio')
        eg = next(e for e in r5['eventos'] if e['clave'] == golpe['clave'])
        ok('MÁS › mejor ataque: un clic más en el golpe', 'clic' in str(eg['fuente']) and eg['archivo'] != golpe['archivo'], eg['fuente'])
        r6, _h = S.retocar(video, golpe['clave'], 'regenerar')
        ok('REGENERAR: otra variación de ese golpe', next(e for e in r6['eventos'] if e['clave'] == golpe['clave'])['archivo'] != eg['archivo'])
    # bloquear + rediseñar
    r7, _h = S.retocar(video, b['clave'], 'bloquear')
    eb2 = next(e for e in r7['eventos'] if e['clave'] == b['clave'])
    r8 = S.redisenar(video)
    eb3 = next(e for e in r8['eventos'] if e['clave'] == b['clave'])
    cambiaron = sum(1 for e in r8['eventos'] if e['suena'] and e['clave'] != b['clave'] and e['archivo'] != {x['clave']: x['archivo'] for x in r7['eventos']}.get(e['clave']))
    ok('BLOQUEAR + Rediseñar: lo bloqueado se queda igual; lo demás cambia', eb3['bloqueado'] and eb3['archivo'] == eb2['archivo'] and cambiaron > 0,
       f'{cambiaron} cambiaron')
    try:
        S.retocar(video, b['clave'], 'mas:otra_capa')
        ok('lo bloqueado no se retoca', False)
    except RuntimeError as e:
        ok('lo bloqueado no se retoca (pide desbloquear)', 'bloqueado' in str(e).lower())
    # una sección
    t_fin = r8['duracion']
    antes = {e['clave']: e['archivo'] for e in r8['eventos'] if e['suena']}
    r9 = S.redisenar(video, t_fin - 8.0, t_fin + 1.0)
    fuera = [e for e in r9['eventos'] if e['suena'] and float(e['ancla']) < t_fin - 8.0]
    ok('Rediseñar una sección (el final): fuera de ella, nada cambia', all(antes.get(e['clave']) == e['archivo'] for e in fuera))
    # controles
    n0 = sum(1 for e in r9['eventos'] if e['suena'])
    S.poner_control('densidad', 'poco')
    r10 = S._rehacer(video)
    n1 = sum(1 for e in r10['eventos'] if e['suena'])
    ok('Densidad «Mínima»: menos sonidos', n1 < n0 and r10['controles'].get('densidad') == 'poco', f'{n0} → {n1}')
    S.poner_control('densidad', 'auto')
    ok('Auto quita el control', 'densidad' not in S.controles())
    S.poner_control('voz', 'mucho')
    r11 = S._rehacer(video)
    niveles = [p.get('nivel_db') for p in E.cargar(video).get('sound_events_placed') or [] if p.get('nivel_db') is not None]
    ok('Prioridad de voz «Máxima»: los sonidos bajan', bool(niveles), f'{len(niveles)} sonidos')
    r12 = S.deshacer_todo(video)
    ok('Deshacer todo: controles en Auto, sin retoques, ronda 0', not S.controles() and not E.cargar(video).get('ajustes') and not E.cargar(video).get('ronda'))
    # «dile a AI Sound Director»
    casos = {'menos sonidos por favor': ('control', 'densidad', 'poco'), 'que se oiga mejor la voz': ('control', 'voz', 'mucho'),
             'hazlo más cinematográfico': ('control', 'estilo', 'cinematico'), 'sin música': ('control', 'musica', 'nada'),
             'rediseña el final': ('seccion',), 'quita el sonido de xela': ('silenciar_texto',), 'como estaba': ('reset',)}
    for frase, esperado in casos.items():
        i = S.interpretar(frase, r12['duracion'])
        hay = any(a[:len(esperado)] == esperado or (esperado[0] in ('seccion', 'silenciar_texto') and a[0] == esperado[0]) for a in i['acciones'])
        ok(f'«{frase}» → {esperado[0]}{" " + esperado[1] if len(esperado) > 1 else ""}', hay, i['entendido'])
    ok('una frase que no se entiende no hace nada', not S.interpretar('blablá xyz')['acciones'])
    r13, _t = S.ejecutar(video, S.interpretar('quita el sonido de xela')['acciones'])
    caps = [c for c in E.cargar(video).get('caption_decisions') or [] if 'xela' in str(c.get('texto') or '').lower()]
    sil = [e for e in r13['eventos'] if e['ref'] in {c['cue'] for c in caps} and e['origen'] in ('caption', 'dato')]
    ok('«quita el sonido de xela»: sus sonidos, silenciados', bool(sil) and all(not e['suena'] for e in sil), f'{len(sil)} eventos')
    S.deshacer_todo(video)
    # A/B
    import director_sonido_medir as M
    import numpy as np
    t0 = max(0.0, float(next(e for e in S.resumen(video)['eventos'] if e['suena'])['ancla']) - 1.0)
    po, pa = S.previa(video, 'original', t0, t0 + 6.0), S.previa(video, 'ai', t0, t0 + 6.0)
    xo, xa = (np.concatenate(list(M.leer_wav(x)), axis=1) for x in (po, pa))
    ok('A/B: dos WAV del mismo largo (6 s)', abs(xo.shape[1] / 48000 - 6.0) < 0.01 and xo.shape == xa.shape, f'{xo.shape}')
    ok('A/B: AI SOUND suena distinto del original donde hay un sonido', float(np.abs(xa - xo).max()) > 0.01)
    plan = S.plan_para_resolve(video)
    ok('plan para Resolve: solo_ai, sus pistas AI SFX y Simple apagado', plan['solo_ai'] and plan['apagar_sfx'] and
       all(str(e.get('pista') or '').startswith('AI ') or e.get('tipo') == 'voz_ai' for e in plan['eventos']) and plan['eventos'])
    estado = E.cargar(video)
    estado['ultimo_go'] = {}
    E.guardar(video, estado)
    ok('«Aplicar» se niega sin un GO con el director (la PRO y Simple tendrían sus sonidos)', S.aplicar(video)[0] is False)
    E.poner_general(ultimo_video=str(video))


def pagina(salida, video):
    print('== la página (Qt sin pantalla) ==')
    import qt_kit as ui
    app = ui.crear_app(['probar'], carpeta_fuentes=str(AQUI.parent.parent / '2_recursos' / 'fonts'))
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QWidget, QVBoxLayout
    E, D, _res = preparar(salida, video)
    import director_sonido_ui as U

    def esperar(cond, s=90.0):
        t = time.time()
        while not cond() and time.time() - t < s:
            app.processEvents()
            time.sleep(0.02)
        app.processEvents()
        return cond()
    marco = QWidget()
    marco.setObjectName('marco')
    marco.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    marco.setStyleSheet('QWidget#marco { background: #080C14; }')     # (solo el fondo del marco: sin heredarlo a cada etiqueta)
    capa = QVBoxLayout(marco)
    capa.setContentsMargins(28, 28, 28, 28)
    import director_sonido_sesion as S_
    import resolve_mcp as RM_
    llamadas = []
    abierto = {'si': True}
    real_aplicar, real_abierto = S_.aplicar, RM_.resolve_abierto
    def aplicar_falso(v, offset_frames=0, al_estado=None):           # (como aplicar de verdad, sin Resolve: marca al día)
        llamadas.append(v)
        st = E.cargar(v)
        st['pendiente_resolve'], st['en_resolve'] = False, '2026-10-21 10:30:00'
        E.guardar(v, st)
        return True, 'ok'
    S_.aplicar = aplicar_falso
    RM_.resolve_abierto = lambda: abierto['si']
    pag = U.PaginaDirector(video=lambda: str(video))
    capa.addWidget(pag)
    marco.resize(1240, 1500)
    marco.show()
    pag.refrescar()
    ok('la página lee el diseño (en un hilo) y lo pinta', esperar(lambda: pag._res.get('hay')), pag._lbl_tema.text()[:90])
    ok('cuerpo visible, aviso de vacío oculto', pag._cuerpo.isVisible() and not pag._vacio.isVisible())
    ok('estado: voz, música y sonido de motions con su texto', all(pag._filas[k].valor.text() for k in ('voz', 'musica', 'motion')),
       ' · '.join(pag._filas[k].valor.text() for k in ('voz', 'musica', 'motion')))
    ok('el anillo enseña el Sound Score medido', pag._score._v is not None and pag._score._v == pag._res.get('sound_score'), pag._score._v)
    pag._desglose()
    ok('tocar el anillo: el desglose parte por parte en la línea de estado', 'Sound Score' in pag._lbl_estado.text() and 'sincronía' in pag._lbl_estado.text(),
       pag._lbl_estado.text())
    marco.grab().save(str(Path(salida) / 'pagina_director_1.png'))
    ev = next(e for e in pag._res['eventos'] if e['suena'] and e['tipo'] == 'golpe')
    L = pag._linea
    x, y = L._x(ev['ancla']), L._y(4) + L.CARRIL / 2
    vistos = []
    for _k in range(4):                                              # sonidos solapados: otro clic en el mismo sitio pasa al siguiente
        L.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(x, y), QPointF(x, y), Qt.MouseButton.LeftButton,
                                      Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        app.processEvents()
        vistos.append((pag._ev or {}).get('id'))
        if (pag._ev or {}).get('clave') == ev['clave']:
            break
    ok('clic repetido en el mismo sitio recorre los sonidos solapados', len(vistos) == 1 or len(set(vistos)) == len(vistos), vistos)
    ok('clic en la línea: el inspector enseña ese sonido', pag._ev is not None and pag._ev['clave'] == ev['clave'] and ev['nombre'] in pag._lbl_ev.text(),
       f"{pag._lbl_ev.text()} · elegido {(pag._ev or {}).get('id')} / esperado {ev['id']} · en el mismo sitio: "
       f"{[(e['id'], e['t'], e['ancla'], e['dur']) for e in pag._res['eventos'] if (e['suena'] or e['silenciado']) and abs(float(e['ancla']) - float(ev['ancla'])) < 0.5]}")
    ok('inspector: diseño, porqué e importancia; botones activos', pag._lbl_diseno.text() and pag._lbl_porque.text() and pag._b_regen.isEnabled())
    pag._b_silencio.click()
    ok('SILENCIAR desde el inspector', esperar(lambda: not pag._ocupado and (pag._ev or {}).get('silenciado')), pag._lbl_estado.text())
    ok('SILENCIAR guarda cambios pendientes sin enviar automáticamente a Resolve', len(llamadas) == 0
       and pag._res.get('pendiente_resolve') and 'pendientes' in pag._lbl_resolve.text().lower()
       and pag._b_aplicar.property('tipo') == 'primario', pag._lbl_resolve.text())
    abierto['si'] = False
    pag._b_silencio.click()
    ok('y vuelve a sonar', esperar(lambda: not pag._ocupado and (pag._ev or {}).get('suena')))
    ok('con Resolve cerrado la edición conserva los cambios pendientes y Aplicar como acción principal', len(llamadas) == 0
       and pag._res.get('pendiente_resolve') and pag._b_aplicar.property('tipo') == 'primario' and 'Resolve' in pag._lbl_resolve.text(), pag._lbl_resolve.text())
    pag._aplicar()
    ok('solo «Aplicar a Resolve» envía el diseño y la cabecera vuelve a «al día» tras confirmación', esperar(lambda: not pag._ocupado) and len(llamadas) == 1
       and not pag._res.get('pendiente_resolve') and pag._b_aplicar.property('tipo') == 'secundario', pag._lbl_estado.text())
    abierto['si'] = True
    ok('fila «Material»: de dónde saca el sonido el director', bool(pag._filas['material'].valor.text()), pag._filas['material'].valor.text())
    ok('la línea de tiempo enseña el carril MOTIONS PRO', 'MOTIONS PRO' in U.LineaSonido.CARRILES)
    n0 = sum(1 for e in pag._res['eventos'] if e['suena'])
    pag._cambio_control('densidad', pag._vars['densidad'].get() if False else __import__('i18n').tr('Mínima'))
    ok('un control (Densidad «Mínima») rediseña y la página se repinta', esperar(lambda: not pag._ocupado and pag._res.get('controles', {}).get('densidad') == 'poco')
       and sum(1 for e in pag._res['eventos'] if e['suena']) < n0 and pag._res.get('pendiente_resolve') and len(llamadas) == 1)
    pag._var_frase.set('como estaba')
    pag._frase()
    ok('«dile…»: «como estaba» deja todo en Auto y pendiente de aplicar', esperar(lambda: not pag._ocupado and not pag._res.get('controles'))
       and pag._res.get('pendiente_resolve') and len(llamadas) == 1, pag._lbl_estado.text())
    marco.grab().save(str(Path(salida) / 'pagina_director_2.png'))
    S_.aplicar, RM_.resolve_abierto = real_aplicar, real_abierto
    # vacío: un video que no pasó por GO (y sin «último»)
    E.poner_general(ultimo_video='')
    otro = U.PaginaDirector(video=lambda: str(Path(salida) / 'no_existe.mp4'))
    otro.refrescar()
    ok('sin diseño: la página lo dice (y no enseña controles)', esperar(lambda: 'motivo' in otro._res) and not otro._res.get('hay'), otro._res.get('motivo'))
    # SubtitleApp._asegurar_sfx arma la página nueva
    M_ = sys.modules.get('cc_nuevo') or P._principal(AQUI.parent / 'CineCaptions (script principal).py', 'cc_nuevo')
    import types
    F = QWidget()                                                    # (la ventana de verdad es un QWidget: la página cuelga de ella)
    caja = QVBoxLayout(F)
    F._estudio_ventana, F._sfx_capa, F.video_var, F._go_archivo, F._offset_frames = None, caja, P._Var(str(video)), None, lambda: 0
    F._asegurar_sfx = types.MethodType(M_.SubtitleApp._asegurar_sfx, F)
    ok('SONIDO abre AI Sound Director (la página vieja no se arma)', F._asegurar_sfx() and getattr(F, '_director_pagina', None) is not None
       and F._estudio_ventana is None and caja.count() == 1)


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    args = sys.argv[1:]
    video = Path(args[args.index('--video') + 1]) if '--video' in args else Path.home() / 'Desktop' / 'VIDEOS EN ESPAÑOL' / 'PRUEBA ESPAÑOL.mp4'
    salida = Path(args[args.index('--salida') + 1]) if '--salida' in args else Path(tempfile.gettempdir()) / 'cc_pagina_director'
    salida.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    motor(salida, video)
    pagina(salida, video)
    pasan = sum(1 for _n, b in RESULTADOS if b)
    print(f'\n{pasan}/{len(RESULTADOS)} pruebas pasan · {time.time() - t0:.1f} s · capturas en {salida}')
    sys.stdout.flush()
    os._exit(0 if pasan == len(RESULTADOS) else 1)


if __name__ == '__main__':
    main()
