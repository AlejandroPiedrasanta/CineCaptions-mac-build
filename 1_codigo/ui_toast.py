# CineCaptions · By Cinema Productions
# 1_codigo/ui_toast.py — avisos que se cierran solos (toasts).
"""
ui_toast.py
-----------
Avisos que se cierran solos, para no molestar al usuario con un cuadro que
tiene que aceptar cada vez que algo termina bien.

El uso normal es reemplazar los `messagebox.showinfo` de "listo": ese
cuadro modal obliga a hacer clic en Aceptar aunque solo diga "todo salio
bien". Con `mostrar()` de aca aparece un aviso en la ventana por unos
segundos y se cierra solo.

v5.0.0 (Qt): el aviso es una capa DENTRO de la ventana (arriba, centrado),
no una ventana aparte: no roba el foco, se mueve con la ventana y entra con
un fundido. Un clic lo cierra al momento. Misma firma que la v4.
"""
from PySide6.QtCore import QEasingCurve, Qt, QTimer, QVariantAnimation
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsOpacityEffect, QHBoxLayout

import qt_kit as ui


class _Toast(QFrame):
    def __init__(self, ventana, mensaje, color):
        super().__init__(ventana)
        if color == '#0D1627':
            color = '#13213D'
        self.setObjectName('toast')
        self.setStyleSheet(ui.traducir_hoja(f'QFrame#toast {{ background-color: {color}; border: 1px solid #2E5BCC; '
                                            'border-radius: 12px; }'))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        capa = QHBoxLayout(self)
        capa.setContentsMargins(18, 12, 20, 12)
        capa.setSpacing(12)
        capa.addWidget(ui.IconoEstado('ok'), 0, Qt.AlignmentFlag.AlignVCenter)
        texto = ui.Etiqueta(mensaje, 14, color='#FFFFFF', envolver=True)
        texto.setMaximumWidth(560)
        capa.addWidget(texto, 1)
        self._efecto = QGraphicsOpacityEffect(self)
        self._efecto.setOpacity(0.0)
        self.setGraphicsEffect(self._efecto)
        self._anim = None
        self._cerrando = False

    def _fundir(self, desde, hasta, al_final=None):
        anim = QVariantAnimation(self)
        anim.setDuration(180)
        anim.setStartValue(float(desde))
        anim.setEndValue(float(hasta))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(lambda v: self._efecto.setOpacity(float(v)) if ui.vivo(self._efecto) else None)
        if al_final:
            anim.finished.connect(al_final)
        anim.start()
        self._anim = anim

    def colocar(self):
        padre = self.parentWidget()
        self.adjustSize()
        x = max(12, (padre.width() - self.width()) // 2)
        y = max(24, padre.height() // 7)
        self.move(x, y)

    def cerrar(self):
        if self._cerrando or not ui.vivo(self):
            return
        self._cerrando = True
        self._fundir(self._efecto.opacity(), 0.0, self.deleteLater)

    def mousePressEvent(self, e):
        self.cerrar()
        e.accept()


def mostrar(padre, mensaje, duracion_ms=4000, color='#0D1627'):
    """Aviso no modal que se cierra solo tras `duracion_ms` milisegundos.

    Si el usuario quiere quedarse mirándolo mas tiempo, un clic sobre el
    toast lo cierra al toque.
    """
    try:
        import registro
        registro.ok(str(mensaje), 'aviso')
    except Exception:
        pass
    try:
        ventana = padre.window() if padre is not None and ui.vivo(padre) else QApplication.activeWindow()
        if ventana is None:
            return None
        toast = _Toast(ventana, mensaje, color)
        toast.colocar()
        toast.show()
        toast.raise_()
        toast._fundir(0.0, 1.0)
        QTimer.singleShot(int(duracion_ms), toast.cerrar)
        return toast
    except Exception:
        return None
