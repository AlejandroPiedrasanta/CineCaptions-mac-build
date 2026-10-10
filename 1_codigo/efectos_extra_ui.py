# CineCaptions · By Cinema Productions
# 1_codigo/efectos_extra_ui.py — la sección «Más efectos» de la página Efectos: números, pegatinas, énfasis, ambiente, mis efectos y el cierre (outro).
"""
La página Efectos (efectos_pagina.py) muestra esta sección plegada tras un botón «Más efectos». Todo lo que se toca se guarda en las preferencias (las lee
efectos_visuales.planificar → efectos_extra.planificar_extra al hacer GO):

    fx_numeros                                  números 1-2-3 cuando el que habla enumera
    fx_pegatinas / fx_pegatinas_palabras        pegatinas (emojis grandes) en las palabras que se dicen (de fábrica + las del usuario)
    fx_enfasis / fx_enfasis_altura              subrayado o círculo dibujado a mano sobre las frases importantes, y a qué altura
    fx_evitar                                   que los iconos, números y pegatinas no tapen la franja de los captions ni la cara
    fx_overlay / fx_overlay_fuerza              polvo, grano o luz suave en bucle durante todo el video
    fx_propios [ {id, nombre, ruta, uso, modo, opacidad, palabras, activo} ]   mis efectos (MOV/MP4/PNG/GIF/WebP/APNG)
    fx_outro / fx_outro_texto / fx_outro_logo / fx_outro_sonido                el cierre
"""
from pathlib import Path

from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

import efectos_extra as X
import efectos_visuales as F
import qt_kit as ui
from qt_kit import Boton, Dialogo, Entrada, Etiqueta, Interruptor, Segmentado, StringVar, Tarjeta, caja_h
from i18n import tr
from efectos_pagina import FilaCartas

TEXT_MUTED = ui.TEXT_MUTED
# la línea de cada tarjeta cabe en tres renglones: versiones cortas de las descripciones del catálogo
_BREVE = {'polvo': 'Partículas de polvo que brillan y flotan.', 'grano': 'Un grano fino de cine sobre la imagen.', 'luz': 'Un resplandor cálido que se mueve.',
          'cta': 'Un botón «Sígueme» animado al final.', 'logo': 'Tu logo entra con un destello.', 'final': 'El video se oscurece y sale tu logo.'}


def _guardar(cambios):
    try:
        import ajustes_ui
        ajustes_ui.guardar_prefs(cambios)
    except Exception:
        pass


def _opciones(pares):
    """[(clave, texto traducido)] -> (lista de textos, clave->texto, texto->clave)."""
    return [t for _k, t in pares], {k: t for k, t in pares}, {t: k for k, t in pares}


def _fila_segmentos(capa, etiqueta, pares, actual, al_cambiar):
    """Una fila «Etiqueta  [a | b | c]»; devuelve el StringVar. `al_cambiar(clave)`."""
    textos, a_texto, a_clave = _opciones(pares)
    fila, c = caja_h(espacio=10)
    c.addWidget(Etiqueta(etiqueta, 13, color=TEXT_MUTED))
    var = StringVar(a_texto.get(actual, textos[0]))
    c.addWidget(Segmentado(textos, var, lambda _v=None: al_cambiar(a_clave.get(var.get(), pares[0][0])), alto=32, tam=13))
    c.addStretch(1)
    capa.addWidget(fila)
    return var


# ====================================================================================== pegatinas: palabra = emoji
class DialogoPegatinas(Dialogo):
    """Qué palabra hace saltar qué pegatina: una línea por palabra, «dinero = 💰». Las de fábrica ya están puestas: aquí se añaden o se cambian (una línea «dinero =» sin nada
    quita la de fábrica)."""

    def __init__(self, padre, al_guardar):
        super().__init__(padre, tr('Palabras de las pegatinas'), 600, 560, minimo=(520, 460))
        self._al_guardar = al_guardar
        capa = QVBoxLayout(self)
        capa.setContentsMargins(22, 20, 22, 18)
        capa.setSpacing(12)
        capa.addWidget(Etiqueta(tr('Palabras de las pegatinas'), 20, peso='extra', color='#FFFFFF'))
        capa.addWidget(Etiqueta(tr('Una línea por palabra: «dinero = bolsa de dinero». Vale pegar el emoji o escribir su nombre en español o inglés («casa = house»). Ya vienen puestas palabras como dinero, casa, fuego o idea; aquí añades las tuyas o cambias una (una línea «dinero =» sin nada la quita).'),
                                13, color='#B4C0D6', envolver=True))
        self._caja = QPlainTextEdit()
        self._caja.setFont(ui.fuente(14))
        propias = F.opciones_guardadas().get('fx_pegatinas_palabras') or {}
        self._caja.setPlainText('\n'.join(f"{k} = {self._glifo(v)}" for k, v in propias.items()))
        self._caja.setMinimumHeight(190)
        capa.addWidget(self._caja, 1)
        self._nota = Etiqueta('', 12, color=TEXT_MUTED, envolver=True)
        capa.addWidget(self._nota)
        fila, cf = caja_h(espacio=10)
        cf.addStretch(1)
        cf.addWidget(Boton(tr('Cancelar'), self.cerrar, alto=36, ancho=110, tam=13))
        cf.addWidget(Boton(tr('Guardar'), self._guardar, tipo='primario', alto=36, ancho=130, tam=13, negrita=True))
        capa.addWidget(fila)
        self._caja.textChanged.connect(self._contar)
        self._contar()

    @staticmethod
    def _glifo(eid):
        try:
            import emojis
            e = emojis.por_id(eid)
            return e['glifo'] if e else str(eid)
        except Exception:
            return str(eid)

    @staticmethod
    def _resolver(texto):
        """El id de emoji de lo que se escribió a la derecha del «=» (glifo, id o nombre en es/en). '' si queda vacío (= quitar), None si no se encuentra."""
        t = texto.strip()
        if not t:
            return ''
        try:
            import emojis
            for e in emojis.catalogo():
                if e.get('glifo') and (t == e['glifo'] or t.replace('️', '') == e['glifo'].replace('️', '')) or t == e.get('id'):
                    return e['id']
            hallados = emojis.buscar(t)
            if hallados:
                return hallados[0]['id']
        except Exception:
            pass
        return None

    def _analizar(self):
        propias, malas = {}, []
        for linea in self._caja.toPlainText().splitlines():
            if not linea.strip():
                continue
            for sep in ('=', ':', '→', '->'):
                if sep in linea:
                    palabra, _s, resto = linea.partition(sep)
                    break
            else:
                malas.append(linea.strip())
                continue
            palabra = palabra.strip().lower()
            eid = self._resolver(resto)
            if not palabra or eid is None:
                malas.append(linea.strip())
            else:
                propias[palabra] = eid
        return propias, malas

    def _contar(self):
        propias, malas = self._analizar()
        txt = tr('{n} palabras tuyas', n=len(propias)) if len(propias) != 1 else tr('1 palabra tuya')
        if malas:
            txt += ' · ' + tr('no entiendo: {l}', l='; '.join(malas[:3]))
        self._nota.configure(text=txt)

    def _guardar(self):
        propias, _malas = self._analizar()
        self._al_guardar(propias)
        self.cerrar()


# ====================================================================================== un efecto propio
class DialogoPropio(Dialogo):
    """Añadir o editar uno de MIS efectos: el archivo, cuándo sale, cómo se mezcla y con cuánta fuerza."""

    def __init__(self, padre, entrada, al_guardar, al_quitar=None):
        nuevo = not entrada
        super().__init__(padre, tr('Nuevo efecto propio') if nuevo else tr('Mi efecto'), 600, 620, minimo=(520, 560))
        self._e = dict(entrada or {'uso': 'intro', 'modo': 'screen', 'opacidad': 100, 'activo': True})
        self._al_guardar = al_guardar
        self._al_quitar = al_quitar
        capa = QVBoxLayout(self)
        capa.setContentsMargins(22, 20, 22, 18)
        capa.setSpacing(12)
        capa.addWidget(Etiqueta(tr('Nuevo efecto propio') if nuevo else tr('Mi efecto'), 20, peso='extra', color='#FFFFFF'))
        capa.addWidget(Etiqueta(tr('Un video o animación tuyo (MOV o MP4, PNG, GIF, WebP animado o APNG) para ponerlo encima del video. Los efectos sobre fondo negro (fuegos, polvo, destellos) van en «Screen»; los que traen transparencia (PNG, GIF, WebP, MOV con alfa), en «Normal».'),
                                13, color='#B4C0D6', envolver=True))
        fila_a, ca = caja_h(espacio=10)
        self._lbl = Etiqueta(Path(str(self._e.get('ruta') or '')).name or tr('Ningún archivo'), 13, color='#E0EBFB')
        ca.addWidget(Boton(tr('Elegir archivo…'), self._elegir, alto=34, tam=13))
        ca.addWidget(self._lbl, 1)
        capa.addWidget(fila_a)
        fila_n, cn = caja_h(espacio=10)
        cn.addWidget(Etiqueta(tr('Nombre'), 13, color=TEXT_MUTED))
        self._nombre = StringVar(str(self._e.get('nombre') or Path(str(self._e.get('ruta') or '')).stem))
        cn.addWidget(Entrada(self._nombre, alto=34, tam=13), 1)
        capa.addWidget(fila_n)
        self._uso = _fila_segmentos(capa, tr('Cuándo sale'), [(k, tr(t)) for k, t in X.USO_PROPIOS], self._e.get('uso', 'intro'), self._cambio_uso)
        self._modo = _fila_segmentos(capa, tr('Mezcla'), [(k, t) for k, t in X.MODOS_PROPIOS], self._e.get('modo', 'screen'), lambda k: self._e.__setitem__('modo', k))
        op = int(self._e.get('opacidad', 100))
        self._op = _fila_segmentos(capa, tr('Fuerza'), [('100', tr('Fuerte')), ('65', tr('Media')), ('35', tr('Suave'))], str(min(('100', '65', '35'), key=lambda v: abs(int(v) - op))),
                                   lambda k: self._e.__setitem__('opacidad', int(k)))
        self._lbl_palabras = Etiqueta(tr('En qué palabras (separadas por comas)'), 13, color=TEXT_MUTED)
        capa.addWidget(self._lbl_palabras)
        self._palabras = QPlainTextEdit()
        self._palabras.setFont(ui.fuente(14))
        self._palabras.setPlainText(', '.join(self._e.get('palabras') or []))
        self._palabras.setFixedHeight(90)
        capa.addWidget(self._palabras)
        self._cambio_uso(self._e.get('uso', 'intro'))
        self._nota = Etiqueta('', 12, color=TEXT_MUTED, envolver=True)
        capa.addWidget(self._nota)
        capa.addStretch(1)
        fila, cf = caja_h(espacio=10)
        if al_quitar and not nuevo:
            cf.addWidget(Boton(tr('Quitar'), self._quitar, tipo='fantasma', alto=36, tam=13))
        cf.addStretch(1)
        cf.addWidget(Boton(tr('Cancelar'), self.cerrar, alto=36, ancho=110, tam=13))
        cf.addWidget(Boton(tr('Guardar'), self._guardar, tipo='primario', alto=36, ancho=130, tam=13, negrita=True))
        capa.addWidget(fila)

    def _cambio_uso(self, clave):
        self._e['uso'] = clave
        visible = clave == 'palabras'
        self._lbl_palabras.setVisible(visible)
        self._palabras.setVisible(visible)

    def _elegir(self):
        try:
            ruta = ui.filedialog.askopenfilename(title=tr('Elige tu efecto'), parent=self.window(),
                                                 filetypes=[(tr('Efectos'), '*.mov *.mp4 *.m4v *.webm *.png *.gif *.webp *.apng'), (tr('Todos'), '*.*')])
        except Exception:
            ruta = ''
        if ruta:
            self._e['ruta'] = ruta
            self._lbl.configure(text=Path(ruta).name)
            if not str(self._nombre.get() or '').strip():
                self._nombre.set(Path(ruta).stem)
            if Path(ruta).suffix.lower() in X.EXT_IMAGEN:             # una imagen o animación con transparencia: lo normal es «Normal»
                self._e['modo'] = 'normal'

    def _guardar(self):
        ruta = str(self._e.get('ruta') or '')
        if not ruta or not Path(ruta).is_file():
            self._nota.configure(text=tr('Elige primero el archivo del efecto.'))
            return
        e = dict(self._e)
        e['nombre'] = str(self._nombre.get() or '').strip() or Path(ruta).stem
        e['id'] = e.get('id') or f"p{abs(hash(ruta)) % 10 ** 6}"
        e['palabras'] = [p.strip() for p in self._palabras.toPlainText().replace('\n', ',').split(',') if p.strip()]
        if e['uso'] == 'palabras' and not e['palabras']:
            self._nota.configure(text=tr('Escribe al menos una palabra, o elige otro momento.'))
            return
        e['activo'] = True if e.get('activo') is None else e['activo']
        self._al_guardar(e)
        self.cerrar()

    def _quitar(self):
        if self._al_quitar:
            self._al_quitar(self._e)
        self.cerrar()


# ====================================================================================== la sección
class SeccionExtras(QWidget):
    """Las tarjetas de «Más efectos». Cada control guarda su preferencia al momento."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self._dialogo = None
        self.tarjetas = []                                 # las tarjetas con ejemplo animado (la página las mueve solo mientras se ven)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(18)
        op = F.opciones_guardadas()
        # ---- números, pegatinas y énfasis
        t1 = self._tarjeta(tr('Números, pegatinas y énfasis'), tr('Pequeños detalles que salen solos en el momento justo. Los iconos, números y pegatinas esquivan la franja de los captions y la cara de quien habla.'))
        self._fila(t1.capa, 'numeros', tr('Números'), tr('Un número en una esquina cuando enumeras («primero», «paso 2»…).'),
                   [('no', tr('Sin números'), tr('No salen números.')), ('si', tr('Números 1, 2, 3…'), tr('Sale el número de cada paso al decirlo.'), False)],
                   'si' if op.get('fx_numeros') else 'no', lambda k: _guardar({'fx_numeros': k == 'si'}))
        self._fila(t1.capa, 'pegatinas', tr('Pegatinas'), tr('Un emoji grande salta en una esquina cuando dices su palabra (dinero → bolsa de dinero).'),
                   [('no', tr('Sin pegatinas'), tr('No salen pegatinas.')), ('si', tr('Pegatinas'), tr('Un emoji grande con borde blanco al decir la palabra.'), False)],
                   'si' if op.get('fx_pegatinas') else 'no', lambda k: _guardar({'fx_pegatinas': k == 'si'}))
        fila_p, cp = caja_h(espacio=12)
        cp.addWidget(Boton(tr('Palabras de las pegatinas…'), self._abrir_pegatinas, alto=32, tam=12))
        cp.addStretch(1)
        t1.capa.addWidget(fila_p)
        self._fila(t1.capa, 'enfasis', tr('Énfasis dibujado a mano'), tr('La frase importante se subraya o se encierra en un círculo, trazado a mano.'),
                   [('no', tr('Sin énfasis'), tr('Las frases quedan como están.')), ('subrayado', tr('Subrayado'), tr('Un trazo amarillo bajo la frase.'), False),
                    ('circulo', tr('Círculo'), tr('Un círculo amarillo alrededor de la frase.'), False)], op.get('fx_enfasis') or 'no', lambda k: _guardar({'fx_enfasis': k}))
        self._fila(t1.capa, 'alturaenfasis', tr('Altura del énfasis'), tr('Dónde cae el trazo: depende de dónde pone el texto el estilo que uses.'),
                   [('arriba', tr('Arriba'), tr('El trazo cae en la parte de arriba.'), False), ('centro', tr('Centro'), tr('El trazo cae en el centro.'), False),
                    ('abajo', tr('Abajo'), tr('El trazo cae en la parte de abajo.'), False)], op.get('fx_enfasis_altura') or 'centro', lambda k: _guardar({'fx_enfasis_altura': k}))
        self._v_evitar = ui.BooleanVar(bool(op.get('fx_evitar', True)))
        t1.capa.addWidget(Interruptor(tr('No tapar los captions ni la cara'), self._v_evitar, lambda: _guardar({'fx_evitar': bool(self._v_evitar.get())}), tam=14, color='#FFFFFF'))
        capa.addWidget(t1)
        # ---- ambiente
        t2 = self._tarjeta(tr('Ambiente'), tr('Un efecto suave en bucle sobre todo el video, mezclado en «Screen» para que solo sume luz.'))
        self._fila(t2.capa, 'ambiente', tr('Ambiente'), '', [('', tr('Sin ambiente'), tr('El video queda limpio.'))] + [(i, tr(n), tr(_BREVE.get(i, d)), False) for i, n, d in X.OVERLAYS],
                   op.get('fx_overlay') or '', lambda k: _guardar({'fx_overlay': k}))
        fuerza = float(op.get('fx_overlay_fuerza', 0.45))
        _clave_f = {'0.25': 'suave', '0.45': 'normal', '0.75': 'fuerte'}
        self._fila(t2.capa, 'fuerzaambiente', tr('Fuerza del ambiente'), tr('Cuánta luz suma el ambiente que elegiste.'),
                   [('suave', tr('Suave'), tr('Apenas se nota.'), False), ('normal', tr('Normal'), tr('Se nota sin molestar.'), False), ('fuerte', tr('Fuerte'), tr('Se nota bastante.'), False)],
                   _clave_f[min(_clave_f, key=lambda v: abs(float(v) - fuerza))], lambda k: _guardar({'fx_overlay_fuerza': float({v: c for c, v in _clave_f.items()}[k])}))
        capa.addWidget(t2)
        # ---- cierre
        t3 = self._tarjeta(tr('Cierre del video'), tr('Los últimos segundos con una invitación a seguirte: un botón animado, tu logo o una pantalla final, con su sonido.'))
        self._fila(t3.capa, 'cierre', tr('Cierre'), '', [('', tr('Sin cierre'), tr('El video termina sin nada más.'))] + [(i, tr(n), tr(_BREVE.get(i, d)), False) for i, n, d in X.OUTROS],
                   op.get('fx_outro') or '', lambda k: _guardar({'fx_outro': k}))
        fila_t, ct = caja_h(espacio=10)
        ct.addWidget(Etiqueta(tr('Texto'), 13, color=TEXT_MUTED))
        self._texto = StringVar(str(op.get('fx_outro_texto') or ''))
        entrada = Entrada(self._texto, placeholder=tr('SÍGUEME PARA MÁS'), alto=34, tam=13)
        entrada.editingFinished.connect(lambda: _guardar({'fx_outro_texto': str(self._texto.get() or '').strip()}))
        ct.addWidget(entrada, 1)
        t3.capa.addWidget(fila_t)
        fila_l, cl = caja_h(espacio=10)
        self._lbl_logo = Etiqueta(Path(str(op.get('fx_outro_logo') or '')).name or tr('Sin logo'), 13, color='#E0EBFB')
        cl.addWidget(Boton(tr('Elegir logo…'), self._elegir_logo, alto=32, tam=12))
        cl.addWidget(Boton(tr('Quitar'), self._quitar_logo, tipo='fantasma', alto=32, tam=12))
        cl.addWidget(self._lbl_logo, 1)
        t3.capa.addWidget(fila_l)
        self._v_snd = ui.BooleanVar(bool(op.get('fx_outro_sonido', True)))
        t3.capa.addWidget(Interruptor(tr('Sonido en el cierre'), self._v_snd, lambda: _guardar({'fx_outro_sonido': bool(self._v_snd.get())}), tam=14, color='#FFFFFF'))
        capa.addWidget(t3)
        # ---- B-roll de stock
        t5 = self._tarjeta(tr('B-roll de stock'), tr('Tomas de apoyo gratuitas de Pexels cuando dices cosas concretas (casa, playa, coche…). Hace falta tu clave de API gratuita (se saca en pexels.com/api). Se colocan DEBAJO de los captions y el audio original sigue sonando.'))
        self._fila(t5.capa, 'broll', tr('B-roll en las palabras concretas'), '',
                   [('no', tr('Sin B-roll'), tr('Solo tu video.')), ('si', tr('B-roll de stock'), tr('Una toma de apoyo cuando dices algo concreto.'), False)],
                   'si' if op.get('fx_broll') else 'no', lambda k: _guardar({'fx_broll': k == 'si'}))
        fila_k, ck = caja_h(espacio=10)
        ck.addWidget(Etiqueta(tr('Clave de Pexels'), 13, color=TEXT_MUTED))
        self._clave = StringVar(str(op.get('pexels_key') or ''))
        e_clave = Entrada(self._clave, placeholder=tr('Pega aquí tu clave'), alto=34, tam=13)
        from PySide6.QtWidgets import QLineEdit
        e_clave.setEchoMode(QLineEdit.EchoMode.Password)
        e_clave.editingFinished.connect(lambda: _guardar({'pexels_key': str(self._clave.get() or '').strip()}))
        ck.addWidget(e_clave, 1)
        t5.capa.addWidget(fila_k)
        _fila_segmentos(t5.capa, tr('Cuántas tomas'), [('pocos', tr('Pocas')), ('normal', tr('Normales')), ('muchos', tr('Muchas'))], op.get('fx_broll_cuanto') or 'normal',
                        lambda k: _guardar({'fx_broll_cuanto': k}))
        capa.addWidget(t5)
        # ---- sonido extra: sonidos de corte y de gancho, música de fondo, normalizar
        try:
            import ajustes_ui
            pref = ajustes_ui.leer_prefs()
        except Exception:
            pref = {}
        t6 = self._tarjeta(tr('Sonido extra'), tr('Sonidos que acompañan a los efectos y una música de fondo que baja sola cuando hablas (con un hueco de silencio antes del golpe de la palabra clave).'))
        for clave, texto, defecto in (('fx_sonido_cortes', tr('Un sonido en cada corte con transición'), True), ('fx_sonido_gancho', tr('Riser y golpe antes de la palabra clave del gancho'), True),
                                      ('sfx_normalizar', tr('Igualar el volumen de todos los sonidos'), True), ('sfx_emoji_contexto', tr('Sonido de los emojis según la frase (positiva o negativa)'), True)):
            var = ui.BooleanVar(pref.get(clave, defecto) is not False)
            setattr(self, '_v_' + clave, var)
            t6.capa.addWidget(Interruptor(texto, var, lambda c=clave, v=var: _guardar({c: bool(v.get())}), tam=14, color='#FFFFFF'))
        musica = dict(pref.get('musica_go') or {})
        self._musica = {'activo': bool(musica.get('activo')), 'ruta': str(musica.get('ruta') or ''), 'db': float(musica.get('db') or 0.0), 'alinear': musica.get('alinear', True) is not False}
        self._v_musica = ui.BooleanVar(self._musica['activo'])
        t6.capa.addWidget(Interruptor(tr('Música de fondo automática'), self._v_musica, lambda: self._guardar_musica(activo=bool(self._v_musica.get())), tam=14, color='#FFFFFF'))
        fila_m, cm = caja_h(espacio=10)
        self._lbl_musica = Etiqueta(Path(self._musica['ruta']).name or tr('Ninguna música elegida'), 13, color='#E0EBFB')
        cm.addWidget(Boton(tr('Elegir música…'), self._elegir_musica, alto=32, tam=12))
        cm.addWidget(Boton(tr('Elegir carpeta…'), self._elegir_carpeta_musica, alto=32, tam=12))
        cm.addWidget(self._lbl_musica, 1)
        t6.capa.addWidget(fila_m)
        _fila_segmentos(t6.capa, tr('Volumen de la música'), [('-4', tr('Baja')), ('0', tr('Normal')), ('4', tr('Alta'))], min(('-4', '0', '4'), key=lambda v: abs(float(v) - self._musica['db'])),
                        lambda k: self._guardar_musica(db=float(k)))
        self._v_alinear = ui.BooleanVar(self._musica['alinear'])
        t6.capa.addWidget(Interruptor(tr('Alinear el pulso de la música con el golpe y los efectos'), self._v_alinear, lambda: self._guardar_musica(alinear=bool(self._v_alinear.get())), tam=14, color='#FFFFFF'))
        capa.addWidget(t6)
        # ---- mis efectos
        self._t4 = self._tarjeta(tr('Mis efectos'), tr('Pon tus propios efectos: fuegos, destellos, marcos, animaciones… en la intro, en los cortes, en todo el video o en las palabras que elijas.'))
        self._lista = QVBoxLayout()
        self._lista.setSpacing(8)
        self._t4.capa.addLayout(self._lista)
        fila_b, cb = caja_h(espacio=10)
        cb.addWidget(Boton(tr('Añadir efecto…'), lambda: self._editar(None), tipo='primario', alto=36, tam=13))
        cb.addStretch(1)
        self._t4.capa.addWidget(fila_b)
        capa.addWidget(self._t4)
        self._pintar_propios()

    def _fila(self, capa, tipo, titulo, ayuda, opciones, actual, guardar):
        """Un ajuste con su ejemplo animado: título, ayuda y una fila de tarjetas (una por opción), como la intro."""
        capa.addWidget(Etiqueta(titulo, 15, peso='medio', color='#E0EBFB'))
        if ayuda:
            capa.addWidget(Etiqueta(ayuda, 12, color=TEXT_MUTED, envolver=True))
        validas = {o[0] for o in opciones}
        fila = FilaCartas(tipo, opciones, actual if actual in validas else opciones[0][0], guardar)
        capa.addWidget(fila)
        self.tarjetas.extend(fila.tarjetas)
        return fila

    @staticmethod
    def _tarjeta(titulo, descripcion):
        t = Tarjeta(espacio=12, margenes=(22, 18, 22, 18))
        t.capa.addWidget(Etiqueta(titulo, 18, peso='medio', color='#FFFFFF'))
        t.capa.addWidget(Etiqueta(descripcion, 13, color=TEXT_MUTED, envolver=True))
        return t

    # -- pegatinas
    def _abrir_pegatinas(self):
        if self._dialogo is not None and ui.vivo(self._dialogo):
            self._dialogo.close()
        self._dialogo = DialogoPegatinas(self.window(), lambda propias: _guardar({'fx_pegatinas_palabras': propias}))
        self._dialogo.show()

    # -- música de fondo
    def _guardar_musica(self, **cambios):
        self._musica.update(cambios)
        _guardar({'musica_go': dict(self._musica)})

    def _elegir_musica(self):
        try:
            ruta = ui.filedialog.askopenfilename(title=tr('Elige la música de fondo'), parent=self.window(), filetypes=[(tr('Audio'), '*.mp3 *.wav *.m4a *.aac *.flac *.ogg'), (tr('Todos'), '*.*')])
        except Exception:
            ruta = ''
        if ruta:
            self._poner_ruta_musica(ruta)

    def _elegir_carpeta_musica(self):
        try:
            ruta = ui.filedialog.askdirectory(title=tr('Elige una carpeta con músicas'), parent=self.window())
        except Exception:
            ruta = ''
        if ruta:
            self._poner_ruta_musica(ruta)

    def _poner_ruta_musica(self, ruta):
        self._guardar_musica(ruta=str(ruta), activo=True)
        self._v_musica.set(True)
        self._lbl_musica.configure(text=Path(ruta).name)

    # -- logo del cierre
    def _elegir_logo(self):
        try:
            ruta = ui.filedialog.askopenfilename(title=tr('Elige tu logo'), parent=self.window(), filetypes=[(tr('Imagen'), '*.png *.jpg *.jpeg *.webp'), (tr('Todos'), '*.*')])
        except Exception:
            ruta = ''
        if ruta:
            _guardar({'fx_outro_logo': ruta})
            self._lbl_logo.configure(text=Path(ruta).name)

    def _quitar_logo(self):
        _guardar({'fx_outro_logo': ''})
        self._lbl_logo.configure(text=tr('Sin logo'))

    # -- mis efectos
    def _propios(self):
        return [dict(e) for e in (F.opciones_guardadas().get('fx_propios') or []) if isinstance(e, dict)]

    def _pintar_propios(self):
        while self._lista.count():
            it = self._lista.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        usos = {k: tr(t) for k, t in X.USO_PROPIOS}
        for e in self._propios():
            fila, c = caja_h(espacio=10)
            var = ui.BooleanVar(e.get('activo', True) is not False)
            c.addWidget(Interruptor(str(e.get('nombre') or e.get('id')), var, lambda e=e, v=var: self._activar(e, bool(v.get())), tam=13, color='#FFFFFF'))
            c.addStretch(1)
            c.addWidget(Etiqueta(f"{usos.get(e.get('uso'), '')} · {dict(X.MODOS_PROPIOS).get(e.get('modo'), '')}", 12, color=TEXT_MUTED))
            c.addWidget(Boton(tr('Editar'), lambda e=e: self._editar(e), tipo='fantasma', alto=30, tam=12))
            host = QWidget()
            host.setLayout(c)
            self._lista.addWidget(host)
        if not self._lista.count():
            self._lista.addWidget(Etiqueta(tr('Todavía no has añadido ninguno.'), 13, color=TEXT_MUTED))

    def _guardar_lista(self, lista):
        _guardar({'fx_propios': lista})
        self._pintar_propios()

    def _activar(self, e, activo):
        lista = self._propios()
        for x in lista:
            if x.get('id') == e.get('id'):
                x['activo'] = bool(activo)
        _guardar({'fx_propios': lista})

    def _editar(self, e):
        def guardar(nuevo):
            lista = [x for x in self._propios() if x.get('id') != nuevo.get('id')]
            lista.append(nuevo)
            self._guardar_lista(lista)

        def quitar(viejo):
            self._guardar_lista([x for x in self._propios() if x.get('id') != viejo.get('id')])
        if self._dialogo is not None and ui.vivo(self._dialogo):
            self._dialogo.close()
        self._dialogo = DialogoPropio(self.window(), e, guardar, quitar)
        self._dialogo.show()
