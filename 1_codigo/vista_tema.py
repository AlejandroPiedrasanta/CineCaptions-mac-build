# CineCaptions · By Cinema Productions
# 1_codigo/vista_tema.py — la vista previa EXACTA del tema elegido en Creativo (v5.5.10): los cues del planificador del tema y el mismo dibujo que GO sin Resolve.
"""
vista_tema.py
-------------
Pedido (2026-10-17): «en Creativo ver la vista previa real de cómo se verá en DaVinci Resolve: que detecte el tema que estoy usando, que al dar play se vea
exactamente como ese tema y que, si cambio la principal, se vea en tiempo real».

    estilo_de_pack(pack)                       -> {'tipo': 'guion'|'kinetic'|'viral', 'pack'} para los 6 temas de fábrica; None para lo demás
    planificar(palabras, roles, pack, ...)     -> los cues que Generar escribiría para Resolve (el MISMO planificador del tema, con las marcas de Principal)
    Cuadros(cues, estilo, ancho, alto, fondo)  -> .cuadro(t) = QImage del instante t: la foto de fondo con los captions dibujados por render_sin_resolve
                                                  (render_temas.py para los Temas 1, 2, 3, 5 y 6; el dibujo propio del Tema 4)

planificar() y Cuadros() rasterizan con Pillow: van en un hilo (correr_en_hilo). cuadro(t) solo compone arrays pequeños: va en el hilo de la interfaz.
"""
from pathlib import Path

import numpy as np

import guion_editor
import plantillas
import render_sin_resolve as RSR


def estilo_de_pack(pack, formato='v'):
    """El estilo de dibujo de un tema de fábrica, o None (pack propio, mezcla, diseño automático: Creativo sigue con su vista de siempre)."""
    pack = str(pack or '')
    if pack not in plantillas.FABRICA:
        return None
    if pack == 'Kinetic':
        return {'tipo': 'kinetic', 'pack': pack}
    if pack == 'VIRAL':
        return {'tipo': 'viral', 'pack': pack}
    if guion_editor.es_guion(pack, formato or 'v'):
        return {'tipo': 'guion', 'pack': pack}
    return None


def _ancla(clave, defecto):
    try:
        import ajustes_ui
        return str(ajustes_ui.leer_prefs().get(clave, defecto))
    except Exception:
        return defecto


def planificar(palabras, roles, pack, estilo, idioma='es', fin_video=None, ancla_guion='medio', video=None):
    """Los cues del tema con las marcas de AHORA, como los escribe Generar (_generar_con_guion / _generar_con_kinetic), más el emoji de cada bloque.
    video: el de Proyecto (el Tema 5 saca de él el color de la frase clave, como Generar)."""
    palabras = [dict(w) for w in palabras or []]
    tipo = (estilo or {}).get('tipo')
    if tipo == 'guion':
        cues = guion_editor.planear(palabras, roles, pack, ancla=ancla_guion, fin_video=fin_video, idioma=idioma, video=video)['cues']
    elif tipo in ('kinetic', 'viral'):
        mains = guion_editor.parametros_de_marcas(palabras, roles)[0]
        if tipo == 'viral':
            import viral_planificador as kp
            res = kp.planificar(palabras, idioma=idioma, ancho_tl=1080, alto_tl=1920, ancla=_ancla('viral_ancla', 'bajo'), mains=mains, fin_video=fin_video)
        else:
            import kinetic_planificador as kp
            res = kp.planificar(palabras, idioma=idioma, ancla=_ancla('kinetic_ancla', 'bajo'), mains=mains, fin_video=fin_video)
        cues = res['cues']
    else:
        return []
    if tipo != 'kinetic':                     # (Kinetic no lleva emojis): el emoji elegido en Creativo para una palabra del bloque
        for c in cues:
            if c.get('emoji'):
                continue
            a, b = float(c.get('start') or 0.0), float(c.get('end') or 0.0)
            for w in palabras:
                t = float(w.get('start') or 0.0)
                if w.get('emoji') and a <= t < b:
                    c['emoji'], c['emoji_ini'] = w['emoji'], t
                    break
    return cues


def cue_de_palabra(cues, palabra, t):
    """Índice del cue donde SALE esa palabra (dicha en t): el que la lleva escrita, el más cercano en el tiempo; None si ninguno la lleva.
    Por tiempo solo no basta: un bloque de Kinetic puede empezar después de su primera palabra (se retrasa para no pisar el anterior)."""
    import guion_planificador as G
    plano = G._plano(str(palabra or ''))
    mejor, dist = None, 4.0
    if not plano:
        return None
    for i, c in enumerate(cues or []):
        textos = [str(r.get('texto') or '') for r in c.get('runs') or []] + [str(ln.get('text') or '') for ln in c.get('lines') or []]
        if not any(plano == G._plano(tok) for txt in textos for tok in txt.split()):
            continue
        a, b = float(c.get('start') or 0.0), float(c.get('end') or 0.0)
        d = 0.0 if a - 0.05 <= t <= b else min(abs(t - a), abs(t - b))
        if d < dist:
            mejor, dist = i, d
    return mejor


def ruta_fondo():
    try:
        import instalador_scripts
        return Path(instalador_scripts.BASE_RECURSOS) / 'creativo' / 'movil_fondo.jpg'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'creativo' / 'movil_fondo.jpg'


def _fondo_cubriendo(ruta, ancho, alto):
    """La foto de muestra cubriendo ancho×alto (recortada al centro), como uint8 HxWx3."""
    from PIL import Image
    try:
        with Image.open(ruta) as im:
            im = im.convert('RGB')
            esc = max(ancho / im.width, alto / im.height)
            im = im.resize((max(1, int(round(im.width * esc))), max(1, int(round(im.height * esc)))), Image.LANCZOS)
            x0, y0 = (im.width - ancho) // 2, (im.height - alto) // 2
            im = im.crop((x0, y0, x0 + ancho, y0 + alto))
            return np.ascontiguousarray(np.asarray(im, dtype=np.uint8))
    except Exception:
        return np.full((alto, ancho, 3), 12, dtype=np.uint8)


# ---------------------------------------------------------------------------------------------------------------------------------------------
# v5.5.10 (pedido: «faltan las animaciones de los captions, están muy fijos»): cada capa entra como su macro en Resolve (aproximado, a la vista):
#   Tema 1 Kinetic   héroe: pop con rebote y un giro que se asienta · cinta: se desliza y se destapa · anillo: crece girando · línea: se dibuja
#                    · el resto (sup, label, serif, script): sube y aparece
#   Tema 2 Referencia  la grande (Luxe Shine): crece con rebote y un destello la cruza · las pequeñas (Luxe Slide): suben deslizándose
#   Tema 3 VIRAL     fina: sube · negrita: pop · shatter: llega grande y encaja con destello · select: la caja se destapa · drag: entra arrastrada
#   Tema 4           palabra a palabra con fundido y un asentamiento mínimo (medido en TEMA 4.mp4: casi sin movimiento)
#   Temas 5/6        palabra a palabra subiendo; la frase clave baja un poco y se asienta
#   emoji            pop con rebote y un balanceo
# Al final del bloque todo se va en SALIDA_S (fundido y un poco más pequeño).
SALIDA_S = 0.16


def _ease(x):
    x = max(0.0, min(1.0, x))
    return 1.0 - (1.0 - x) ** 3


def _rebote(x, s=1.70158):
    x = max(0.0, min(1.0, x)) - 1.0
    return 1.0 + (s + 1.0) * x ** 3 + s * x ** 2


def estado_animado(c, t):
    """{'a', 'dx', 'dy', 's', 'rot', 'barrido', 'brillo'} de la capa c en el instante t (None si no se ve). dx/dy en píxeles de la capa."""
    e = t - c['t0']
    if e < 0.0 or t >= c['t1']:
        return None
    tipo, k, rol = c.get('tipo') or 'guion', c.get('k') or '', c.get('rol')
    em = float(c.get('em') or 40.0)
    w = float(c.get('w') or 100.0)
    st = {'a': 1.0, 'dx': 0.0, 'dy': 0.0, 's': 1.0, 'rot': 0.0, 'barrido': None, 'brillo': None}

    def q(d):
        return max(0.0, min(1.0, e / d))
    if tipo == 'emoji':
        st.update(s=max(0.0, _rebote(q(0.45), 2.4)), a=q(0.10), rot=-14.0 * (1.0 - _ease(q(0.6))))
    elif tipo == 'kinetic':
        if 'hero' in k:
            st.update(s=0.35 + 0.65 * _rebote(q(0.5), 2.0), a=q(0.12), rot=-6.0 * (1.0 - _ease(q(0.5))))
        elif 'tape' in k:
            st.update(barrido=_ease(q(0.38)), dx=-0.12 * w * (1.0 - _ease(q(0.38))), a=q(0.06))
        elif 'ring' in k:
            st.update(s=0.5 + 0.5 * _rebote(q(0.45), 1.6), rot=-28.0 * (1.0 - _ease(q(0.45))), a=q(0.16))
        elif 'line' in k:
            st.update(barrido=_ease(q(0.32)))
        else:
            st.update(dy=0.5 * em * (1.0 - _ease(q(0.32))), a=q(0.2))
    elif tipo == 'viral':
        if 'shatter' in k:
            st.update(s=1.55 - 0.55 * _ease(q(0.36)), a=q(0.14), brillo=e / 0.55 if e < 0.55 else None)
        elif 'select' in k:
            st.update(barrido=_ease(q(0.34)))
        elif 'drag' in k:
            st.update(dx=0.45 * w * (1.0 - _ease(q(0.36))), a=q(0.16))
        elif 'negrita' in k:
            st.update(s=0.6 + 0.4 * _rebote(q(0.32), 2.0), a=q(0.12))
        else:
            st.update(dy=0.45 * em * (1.0 - _ease(q(0.26))), a=q(0.18))
    elif tipo == 'tema4':
        st.update(a=_ease(q(0.16)), s=0.96 + 0.04 * _ease(q(0.2)), dy=0.08 * em * (1.0 - _ease(q(0.2))))
    elif c.get('pack') in ('Tema5', 'Tema6'):
        if rol == 'main':
            st.update(s=1.16 - 0.16 * _ease(q(0.42)), a=q(0.22), dy=-0.12 * em * (1.0 - _ease(q(0.42))))
        else:
            st.update(dy=0.38 * em * (1.0 - _ease(q(0.3))), a=q(0.22))
    else:                                                               # Tema 2 (Referencia) y los demás packs «guion»
        if rol == 'main':
            st.update(s=0.55 + 0.45 * _rebote(q(0.5), 1.8), a=q(0.14), brillo=(e - 0.16) / 0.6 if 0.16 <= e < 0.76 else None)
        else:
            st.update(dy=0.6 * em * (1.0 - _ease(q(0.34))), a=q(0.2))
    resta = c['t1'] - t
    if resta < SALIDA_S:
        f = max(0.0, resta / SALIDA_S)
        st['a'] *= f
        st['s'] *= 0.92 + 0.08 * f
    return st


def _qimage_rgba(rgb, alfa):
    """QImage premultiplicada de una capa (rgb float HxWx3 0..255, alfa float HxWx1 0..1). Se puede crear fuera del hilo de la interfaz."""
    from PySide6.QtGui import QImage
    h, w = alfa.shape[:2]
    arr = np.empty((h, w, 4), np.uint8)
    arr[..., :3] = np.clip(rgb + 0.5, 0, 255)
    arr[..., 3] = np.clip(alfa[..., 0] * 255.0 + 0.5, 0, 255)
    img = QImage(arr.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
    return img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


class Cuadros:
    """Los cuadros de la vista: la foto de fondo del tamaño de la pantalla del móvil y las capas de TODOS los cues ya rasterizadas.
    El cuadro 9:16 del video va a lo ancho y centrado en la pantalla (render_sin_resolve.encaje), como un reel en un móvil.
    pintar(p, destino, t) dibuja el instante t con las animaciones del tema; cuadro_array(t) es el cuadro quieto (el del MP4, para el banco)."""

    def __init__(self, cues, estilo, ancho, alto, fondo=None):
        from PySide6.QtGui import QImage
        self.ancho, self.alto = int(ancho), int(alto)
        self.cues = list(cues or [])
        self.estilo = estilo
        self.fondo = _fondo_cubriendo(fondo or ruta_fondo(), self.ancho, self.alto)
        emoji_arriba = _ancla('emoji_posicion', '') != 'abajo'          # como GO sin Resolve: arriba, salvo que se eligiera «Abajo» en Sonido
        self.capas = RSR.preparar(self.cues, self.ancho, self.alto, emoji_arriba=emoji_arriba, estilo=estilo)
        self.fondo_img = QImage(self.fondo.data, self.ancho, self.alto, 3 * self.ancho, QImage.Format.Format_RGB888).copy()
        self.sprites = []
        for c in self.capas:
            h, w = c['a'].shape[:2]
            self.sprites.append(dict({k: v for k, v in c.items() if k not in ('rgb', 'a')}, w=w, h=h, img=_qimage_rgba(c['rgb'], c['a'])))

    def pintar(self, p, destino, t):
        """Dibuja con QPainter el instante t (foto + capas animadas) en `destino` (QRectF, coordenadas de quien pinta)."""
        from PySide6.QtCore import QRectF, Qt
        k = destino.width() / float(self.ancho)
        p.drawImage(destino, self.fondo_img)
        for sp in self.sprites:
            if sp['t0'] > t:
                break
            st = estado_animado(sp, t)
            if st is None or st['a'] <= 0.004 or st['s'] <= 0.01:
                continue
            p.save()
            p.setOpacity(p.opacity() * min(1.0, st['a']))
            p.translate(destino.left() + (sp['x'] + sp['w'] / 2.0 + st['dx']) * k, destino.top() + (sp['y'] + sp['h'] / 2.0 + st['dy']) * k)
            if st['rot']:
                p.rotate(st['rot'])
            p.scale(st['s'] * k, st['s'] * k)
            r = QRectF(-sp['w'] / 2.0, -sp['h'] / 2.0, sp['w'], sp['h'])
            if st['barrido'] is not None:
                p.setClipRect(QRectF(r.left(), r.top(), r.width() * st['barrido'], r.height()), Qt.ClipOperation.IntersectClip)
            img = sp['img'] if st['brillo'] is None else self._con_brillo(sp['img'], st['brillo'])
            p.drawImage(r, img)
            p.restore()

    @staticmethod
    def _con_brillo(img, q):
        """La capa con un destello diagonal que la cruza (q de 0 a 1), solo sobre sus letras (como el barrido de Luxe Shine)."""
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QLinearGradient, QPainter
        out = img.copy()
        w, h = out.width(), out.height()
        x = -0.35 * w + 1.7 * w * max(0.0, min(1.0, q))
        g = QLinearGradient(QPointF(x - 0.18 * w, 0), QPointF(x + 0.18 * w, h * 0.4))
        g.setColorAt(0.0, QColor(255, 255, 255, 0))
        g.setColorAt(0.5, QColor(255, 255, 255, 190))
        g.setColorAt(1.0, QColor(255, 255, 255, 0))
        pp = QPainter(out)
        pp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        pp.fillRect(out.rect(), g)
        pp.end()
        return out

    def tramo(self, k):
        """(inicio, fin) del cue k: lo que la vista quieta repite en bucle."""
        if not (0 <= k < len(self.cues)):
            return 0.0, 0.0
        return float(self.cues[k].get('start') or 0.0), float(self.cues[k].get('end') or 0.0)

    def cue_en(self, t):
        """Índice del cue que se ve en t (o el último que empezó antes; el primero si t va antes de todos)."""
        k = 0
        for i, c in enumerate(self.cues):
            if float(c.get('start') or 0.0) <= t:
                k = i
            else:
                break
        return k if self.cues else -1

    def cue_de_palabra(self, palabra, t):
        k = cue_de_palabra(self.cues, palabra, t)
        return k if k is not None else self.cue_en(t)

    def instante_quieto(self, k):
        """Un instante del cue k con TODOS sus elementos ya dentro (para la vista quieta de un bloque)."""
        if not (0 <= k < len(self.cues)):
            return 0.0
        c = self.cues[k]
        a, b = float(c.get('start') or 0.0), float(c.get('end') or 0.0)
        entradas = [cp['t0'] + cp['entrada'] for cp in self.capas if a <= cp['t0'] < b]
        t = (max(entradas) + 0.12) if entradas else a + 0.3
        return max(a, min(t, b - 0.04))

    def cuadro_array(self, t):
        arr = self.fondo.copy()
        RSR.componer(arr, self.capas, float(t))
        return arr

    def cuadro(self, t):
        """QImage (RGB888) del instante t. Se crea en el hilo de la interfaz (solo compone)."""
        from PySide6.QtGui import QImage
        arr = self.cuadro_array(t)
        h, w = arr.shape[:2]
        return QImage(arr.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
