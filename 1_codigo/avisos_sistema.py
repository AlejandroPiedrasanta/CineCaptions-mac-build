"""Avisos del sistema operativo (v5.4.8): cuando GO termina y CineCaptions no está al frente (estás en Resolve, en otro programa o con la ventana
minimizada), sale una notificación del sistema («Tus subtítulos están listos»). Se apaga en Ajustes › General › «Avisarme al terminar».

Usa la bandeja del sistema de Qt (QSystemTrayIcon): en Windows sale como notificación, en macOS como aviso del Centro de notificaciones. Si el sistema no
tiene bandeja, no hace nada. Todo es de mejor esfuerzo: un aviso que falla nunca estropea un GO.
"""
from __future__ import annotations

_BANDEJA = {'icono': None}


def activado() -> bool:
    try:
        import ajustes_ui
        return ajustes_ui.leer_prefs().get('avisos_sistema', True) is not False
    except Exception:
        return True


def ventana_al_frente(ventana) -> bool:
    """True si el usuario está mirando CineCaptions (no hace falta avisarle)."""
    try:
        return bool(ventana.isActiveWindow()) and not ventana.isMinimized()
    except Exception:
        return False


def avisar(ventana, titulo: str, texto: str, error: bool = False, forzar: bool = False) -> bool:
    """Muestra la notificación si el aviso está activado y la ventana no está al frente. Devuelve True si se mostró."""
    try:
        if not forzar and (not activado() or ventana_al_frente(ventana)):
            return False
        from PySide6.QtWidgets import QSystemTrayIcon, QApplication
        from PySide6.QtCore import QTimer
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        icono = _BANDEJA['icono']
        if icono is None:
            icono = QSystemTrayIcon(QApplication.windowIcon() or ventana.windowIcon(), ventana)
            _BANDEJA['icono'] = icono
        icono.show()
        marca = QSystemTrayIcon.MessageIcon.Warning if error else QSystemTrayIcon.MessageIcon.Information
        icono.showMessage(titulo, texto, marca, 8000)
        QTimer.singleShot(12000, icono.hide)               # no se queda un icono suelto en la bandeja
        return True
    except Exception:
        return False
