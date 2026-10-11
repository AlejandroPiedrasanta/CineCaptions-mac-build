# CineCaptions · By Cinema Productions
# 1_codigo/ventanas_idioma.py — Ventanas de proyectos recientes y de idiomas de traducción.
"""
ventanas_idioma.py
------------------
Ventanas de proyectos recientes y de idiomas de traducción.

Salió de «CineCaptions (script principal).py» (v5.4.44) SIN cambiar su código: el principal conserva la ventana principal (SubtitleApp) y vuelve a importar estos nombres, así que `cc_main.NombreDeClase` sigue existiendo.
"""
import threading
import time
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QListWidget, QVBoxLayout
from qt_kit import (BooleanVar, Boton, Desplazable, Dialogo, Entrada, Etiqueta, Interruptor, StringVar, Tarjeta, caja_h, caja_v, cancelar, despues, messagebox)
from i18n import tr
import proyectos
import ensure_lang_pack as lang_packs
from ui_comun import (FS_MENOR, NOMBRE_POR_CODIGO, TEXT_COLOR, TEXT_MUTED, _capa_dialogo, _nota, _plegar, _titulo, fuente)
class ProyectosWindow(Dialogo):
    """Lista de proyectos (videos) trabajados previamente.

    Muestra cada uno con: nombre del video, fecha de ultima modificacion,
    y si el archivo original sigue existiendo. Permite cargar, borrar
    individual, o purgar todo.

    Se abre modal desde WordTagWindow ("Proyectos guardados") y desde la
    ventana principal (chips "Recientes" o boton dedicado).

    Al elegir un proyecto: cierra la ventana y llama al callback
    on_load(video_path) para que el llamador reabra el video.
    """
    def __init__(self, master, on_load=None):
        super().__init__(master, tr('Proyectos guardados'), 640, 520, minimo=(480, 360))
        self.on_load = on_load
        self._items = []
        capa = _capa_dialogo(self, (16, 14, 16, 14))
        header, ch = caja_h()
        ch.addWidget(_titulo(tr('Proyectos guardados'), 16))
        ch.addStretch(1)
        ch.addWidget(Boton(tr('Recargar'), self._recargar, alto=28, ancho=90, tam=12))
        capa.addWidget(header)
        self.lista_frame = Desplazable(espacio=6)
        capa.addWidget(self.lista_frame, 1)
        pie, cp = caja_h(espacio=8)
        cp.addStretch(1)
        cp.addWidget(Boton(tr('Purgar todo'), self._purgar_todo, tipo='peligro', alto=32, ancho=140))
        cp.addWidget(Boton(tr('Cerrar'), self.cerrar, tipo='neutro', alto=32, ancho=110))
        capa.addWidget(pie)
        self._recargar()
    def _recargar(self):
        self.lista_frame.limpiar()
        self._items = proyectos.listar()
        if not self._items:
            self.lista_frame.agregar(Etiqueta(tr('Aún no hay proyectos guardados.\nGenera subtítulos de un video para que aparezca aquí.'), color='gray60', alineacion=Qt.AlignmentFlag.AlignCenter), alineacion=Qt.AlignmentFlag.AlignHCenter)
            self.lista_frame.capa.insertSpacing(0, 40)
        else:
            for proy in self._items:
                self._agregar_fila(proy)
    def _agregar_fila(self, proy):
        fila = QFrame()
        fila.setObjectName('fila')
        cf = QHBoxLayout(fila)
        cf.setContentsMargins(12, 8, 10, 8)
        cf.setSpacing(10)
        info, ci = caja_v(espacio=2)
        nombre = proyectos.nombre_display(proy)
        color_nombre = '#E0EBFB' if proy.get('existe') else '#B0836C'
        ci.addWidget(Etiqueta(nombre, 13, True, color_nombre))
        ts = proy.get('modificado_en') or 0
        try:
            fecha = time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))
        except Exception:
            fecha = '?'
        detalle = tr('Última edición: {fecha}', fecha=fecha)
        if not proy.get('existe'):
            detalle += tr('  •  video no encontrado')
        ci.addWidget(Etiqueta(detalle, 12, color='gray55'))
        cf.addWidget(info, 1)
        botones, cb = caja_v(espacio=4)
        if proy.get('existe'):
            cb.addWidget(Boton(tr('Abrir'), lambda p=proy: self._abrir(p), tipo='primario', alto=26, ancho=78, tam=12))
        cb.addWidget(Boton(tr('Eliminar'), lambda p=proy: self._borrar(p), tipo='peligro', alto=26, ancho=78, tam=12))
        cf.addWidget(botones)
        self.lista_frame.agregar(fila)
    def _abrir(self, proy):
        video_path = proy.get('video_path')
        if not video_path or not Path(video_path).exists():
            messagebox.showwarning(tr('Video no encontrado'), tr('El archivo original ya no está en su lugar.'), parent=self)
            return
        try:
            if self.on_load:
                self.on_load(video_path)
        finally:
            self.cerrar()
    def _borrar(self, proy):
        nombre = proyectos.nombre_display(proy)
        if not messagebox.askyesno(tr('Eliminar proyecto'), tr('¿Eliminar el registro y las marcas de \'{nombre}\'?\n\nEl video original NO se borra.', nombre=nombre), parent=self):
            return
        proyectos.borrar(proy.get('video_path'))
        self._recargar()
    def _purgar_todo(self):
        if not self._items:
            return
        if not messagebox.askyesno(tr('Purgar todo'), tr('¿Eliminar los {len} proyectos guardados y todas sus marcas?\n\nLos videos originales NO se borran.', len=len(self._items)), parent=self):
            return
        n = proyectos.purgar_todo()
        messagebox.showinfo(tr('Purga completa'), tr('Se eliminaron {n} proyectos.', n=n), parent=self)
        self._recargar()
class IdiomasTraduccionWindow(Dialogo):
    """Buscar, descargar y ver los paquetes de idioma de la traduccion.

    OJO con no confundir esto con el idioma del video: para TRANSCRIBIR no
    hace falta descargar nada, el modelo ya trae sus 99 idiomas. Aqui se
    gestiona lo otro, la traduccion, que si va por paquetes de Argos y si se
    baja de internet.
    """
    def __init__(self, master):
        super().__init__(master, tr('Idiomas de traducción'), 640, 560, minimo=(520, 420))
        self.master_app = master
        self._todos = []
        self._filas = []
        self._descargando = set()
        self._repintar_id = None
        self._build_ui()
        self._cargar(refrescar=False)
        despues(200, lambda: self._cargar(refrescar=True), self)
    def _build_ui(self):
        capa = _capa_dialogo(self, (18, 16, 18, 16), 6)
        capa.addWidget(_titulo(tr('Idiomas de traducción'), 18))
        capa.addWidget(_nota(tr('Para TRANSCRIBIR no hace falta descargar nada: el modelo ya entiende todos los idiomas de la lista principal. Esto es solo para traducir los subtítulos a otro idioma.')))
        fila, cf = caja_h(espacio=12, margenes=(0, 6, 0, 0))
        self.buscar_var = StringVar()
        entrada = Entrada(self.buscar_var, placeholder=tr('Buscar idioma (por ejemplo: ruso, ucraniano)'))
        entrada.textEdited.connect(lambda _t: self._pintar_pronto())
        cf.addWidget(entrada, 1)
        self.solo_instalados = BooleanVar(False)
        cf.addWidget(Interruptor(tr('Solo los míos'), self.solo_instalados, self._pintar))
        capa.addWidget(fila)
        self.estado = Etiqueta('', FS_MENOR, color=TEXT_MUTED, envolver=True)
        capa.addWidget(self.estado)
        marco = QFrame()
        marco.setObjectName('marcoLista')
        cm = QVBoxLayout(marco)
        cm.setContentsMargins(4, 6, 4, 6)
        self.lista = Desplazable(espacio=4, margenes=(6, 2, 6, 2))
        cm.addWidget(self.lista)
        capa.addWidget(marco, 1)
        pie, cp = caja_h(margenes=(0, 6, 0, 0))
        cp.addStretch(1)
        cp.addWidget(Boton(tr('Cerrar'), self._cerrar, tipo='primario', alto=36, ancho=110))
        capa.addWidget(pie)
    def _pintar_pronto(self):
        """Repinta al dejar de teclear (120 ms): con 200 filas, repintar en
        cada tecla se notaba."""
        cancelar(self._repintar_id)
        self._repintar_id = despues(120, self._pintar, self)
    def _cargar(self, refrescar):
        """Trae el catalogo. El refresco va en un hilo: baja de internet."""
        if not refrescar:
            self._todos = lang_packs.paquetes_instalados()
            self._pintar()
            self.estado.configure(text=tr('Buscando más idiomas...'), text_color=TEXT_MUTED)
            return
        resultado = {}
        def _trabajar():
            try:
                resultado['lista'] = lang_packs.paquetes_disponibles()
            except Exception as e:
                resultado['error'] = str(e)
        hilo = threading.Thread(target=_trabajar, daemon=True)
        hilo.start()
        def _revisar():
            if hilo.is_alive():
                despues(200, _revisar, self)
                return
            try:
                lista = resultado.get('lista') or []
                if lista:
                    self._todos = lista
                    self._pintar()
                else:
                    self.estado.configure(text=tr('No pude consultar la lista completa (¿sin conexión?). Abajo están los que ya tienes; esos funcionan sin internet.'), text_color='#FFB86B')
            except Exception:
                return None
        despues(200, _revisar, self)
    def _pintar(self):
        self.lista.setUpdatesEnabled(False)
        try:
            self.lista.limpiar()
            self._filas = []
            texto = self.buscar_var.get().strip().lower()
            solo_mios = self.solo_instalados.get()
            visibles = [
                p for p in self._todos
                if (not solo_mios or p['instalado'])
                and (not texto
                     or texto in p['nombre_from'].lower()
                     or texto in p['nombre_to'].lower()
                     or texto in _nombre_es(p['from']).lower()
                     or texto in _nombre_es(p['to']).lower())
            ]
            visibles.sort(key=lambda p: (not p['instalado'], p['nombre_from'], p['nombre_to']))
            n_mios = sum((1 for p in self._todos if p['instalado']))
            self.estado.configure(text=tr('{len} de {len2} pares · 1 descargado', len=len(visibles), len2=len(self._todos)) if n_mios == 1 else tr('{len} de {len2} pares · {n_mios} descargados', len=len(visibles), len2=len(self._todos), n_mios=n_mios), text_color=TEXT_MUTED)
            for p in visibles[:200]:
                self._filas.append(self._fila(p))
            if len(visibles) > 200:
                aviso = Etiqueta(tr('...y {v} más. Escribe en el buscador para encontrar el tuyo.', v=len(visibles) - 200), FS_MENOR, color='#FFB86B')
                self.lista.agregar(aviso)
                self._filas.append(aviso)
        finally:
            self.lista.setUpdatesEnabled(True)
    def _fila(self, paquete):
        marco = QFrame()
        marco.setObjectName('filaSuave')
        cf = QHBoxLayout(marco)
        cf.setContentsMargins(12, 5, 12, 5)
        etiqueta = f"{_nombre_es(paquete['from'])}  →  {_nombre_es(paquete['to'])}"
        cf.addWidget(Etiqueta(etiqueta, FS_MENOR, color=TEXT_COLOR), 1)
        clave = (paquete['from'], paquete['to'])
        if paquete['instalado']:
            cf.addWidget(Etiqueta(tr('✓ descargado'), FS_MENOR, color='#62D196'))
        elif clave in self._descargando:
            cf.addWidget(Etiqueta(tr('descargando...'), FS_MENOR, color='#FFB86B'))
        else:
            cf.addWidget(Boton(tr('Descargar'), lambda p=paquete: self._descargar(p), alto=28, ancho=100, tam=12))
        self.lista.agregar(marco)
        return marco
    def _descargar(self, paquete):
        clave = (paquete['from'], paquete['to'])
        if clave in self._descargando:
            return
        self._descargando.add(clave)
        self._pintar()
        resultado = {}
        def _trabajar():
            resultado['ok'] = lang_packs.instalar(paquete['from'], paquete['to'], log=lambda m: None)
        hilo = threading.Thread(target=_trabajar, daemon=True)
        hilo.start()
        def _revisar():
            if hilo.is_alive():
                despues(300, _revisar, self)
                return
            self._descargando.discard(clave)
            if resultado.get('ok'):
                paquete['instalado'] = True
                try:
                    self.master_app._refrescar_destinos()
                except Exception:
                    pass
            else:
                messagebox.showerror(tr('No pude descargar'), tr('Falló la descarga de {nombre_es} → {nombre_es2}.\n\nRevisa tu conexión y vuelve a intentarlo.', nombre_es=_nombre_es(paquete['from']), nombre_es2=_nombre_es(paquete['to'])), parent=self)
            self._pintar()
        despues(300, _revisar, self)
    def _cerrar(self):
        try:
            self.master_app._refrescar_destinos()
        except Exception:
            pass
        self.cerrar()
def _nombre_es(codigo):
    """El nombre en español de un codigo de idioma, si lo conocemos."""
    return NOMBRE_POR_CODIGO.get(str(codigo or '').lower(), codigo)
class BuscadorIdiomaWindow(Dialogo):
    """Buscador de idiomas compartido (v1.0.68, pedido literal: «a la
    seccion de los idiomas añadeles un buscador, tanto a donde se
    establece el idioma y el del traductor»).

    Recibe la lista de nombres y un callback, y el clic en un idioma lo
    aplica EN EL ACTO y cierra — la regla de la casa de que toda ventana que
    recoge una decision la aplica al tocarla. Desacoplada de la App a
    proposito: se puede probar sola. v5.0.0: la lista es una QListWidget
    (rapida y con teclado: flechas + Enter).
    """
    def __init__(self, master, titulo, nombres, al_elegir):
        super().__init__(master, titulo, 360, 440, minimo=(320, 300))
        self._nombres = list(nombres)
        self._al_elegir = al_elegir
        self._filas = []
        capa = _capa_dialogo(self, (16, 14, 16, 14), 8)
        capa.addWidget(_titulo(titulo, 14))
        self.buscar_var = StringVar()
        self.entrada = Entrada(self.buscar_var, placeholder=tr('🔍  Escribe para buscar (sin tildes también)'))
        self.entrada.textEdited.connect(lambda _t: self._pintar())
        self.entrada.returnPressed.connect(self._primero)
        capa.addWidget(self.entrada)
        self.aviso = Etiqueta('', FS_MENOR, color=TEXT_MUTED)
        self.aviso.hide()
        capa.addWidget(self.aviso)
        marco = Tarjeta(margenes=(4, 4, 4, 4))
        self.lista = QListWidget()
        self.lista.setFont(fuente(13))
        self.lista.setUniformItemSizes(True)
        self.lista.itemClicked.connect(lambda it: self._elegir(it.text()))
        self.lista.itemActivated.connect(lambda it: self._elegir(it.text()))
        marco.capa.addWidget(self.lista)
        capa.addWidget(marco, 1)
        self._pintar()
        self.entrada.setFocus()
    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self.entrada.hasFocus():
            self.lista.setFocus()
            if self.lista.currentRow() < 0 and self.lista.count():
                self.lista.setCurrentRow(0)
            return
        super().keyPressEvent(e)
    def _pintar(self):
        texto = _plegar(self.buscar_var.get().strip())
        nombres = [n for n in self._nombres if texto in _plegar(n)]
        aviso = None
        if texto and (not nombres):
            aviso = tr('(nada con «{strip}»)', strip=self.buscar_var.get().strip())
            nombres = self._nombres
        self.aviso.setVisible(bool(aviso))
        self.aviso.setText(aviso or '')
        self.lista.clear()
        self.lista.addItems(nombres)
        self._filas = nombres
    def _primero(self):
        if self.lista.count():
            fila = max(0, self.lista.currentRow())
            self._elegir(self.lista.item(fila).text())
    def _elegir(self, nombre):
        try:
            self._al_elegir(nombre)
        finally:
            self.cerrar()
