# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/viral_comps.py — piezas de Fusion propias del estilo «VIRAL» (polígonos, medida del texto, animaciones): se suman a kinetic_comps.py.
"""
Todo se escribe con las entradas REALES de Resolve 21.1.1 (se comprobó cada una con ImportFusionComp + GetInput y con renders: ver DOCUMENTACION/temas/viral.md).
Trampas medidas:
  · una EXPRESIÓN que falla no avisa: el clip sale NEGRO y opaco. `string.len(...)` y `#...` fallan dentro de una expresión de Fusion (GetInput da None); `math.*`, `time`,
    `comp.RenderEnd`, `Nodo.Size`, `Nodo.Output.DataWindow` y `comp:GetPrefs(...)` sí valen.
  · un polígono es una PolylineMask cuya entrada Polyline sale de un modificador BezierSpline con los puntos (así lo guarda Resolve), no de un PolylineStroke.
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import kinetic_comps as K
from kinetic_comps import enlace, herramienta, n

EM = 640.0 / 1080.0              # el em de «Size = 1» en fracciones del ancho del cuadro (medido contra Resolve)


def poligono(nombre, puntos, x=-220, y=280):
    """Una PolylineMask cerrada de lados rectos. `puntos` = [(x, y)] en el espacio de la máscara (el centro del cuadro es (0, 0))."""
    k = len(puntos)
    filas = []
    for i, (px, py) in enumerate(puntos):
        ax, ay = puntos[(i - 1) % k]
        bx, by = puntos[(i + 1) % k]
        filas.append(f'\t\t\t\t\t\t{{ Linear = true, X = {n(px)}, Y = {n(py)}, LX = {n((ax - px) / 3)}, LY = {n((ay - py) / 3)}, RX = {n((bx - px) / 3)}, RY = {n((by - py) / 3)} }}')
    pts = ',\n'.join(filas)
    return (f'\t\t{nombre} = PolylineMask {{\n\t\t\tDrawMode = "InsertAndModify",\n\t\t\tDrawMode2 = "InsertAndModify",\n\t\t\tInputs = {{\n'
            f'\t\t\t\tFilter = Input {{ Value = FuID {{ "Fast Gaussian" }}, }},\n\t\t\t\tMaskWidth = Input {{ Value = {K.ANCHO}, }},\n\t\t\t\tMaskHeight = Input {{ Value = {K.ALTO}, }},\n'
            f'\t\t\t\tPixelAspect = Input {{ Value = {{ 1, 1 }}, }},\n\t\t\t\tUseFrameFormatSettings = Input {{ Value = 1, }},\n\t\t\t\tClippingMode = Input {{ Value = FuID {{ "None" }}, }},\n'
            f'\t\t\t\tPolyline = Input {{ SourceOp = "{nombre}Poly", Source = "Value", }},\n\t\t\t\tPolyline2 = Input {{ Value = Polyline {{ }}, Disabled = true, }},\n\t\t\t}},\n'
            f'\t\t\tViewInfo = OperatorInfo {{ Pos = {{ {x}, {y} }} }},\n\t\t}},\n'
            f'\t\t{nombre}Poly = BezierSpline {{\n\t\t\tSplineColor = {{ Red = 160, Green = 252, Blue = 4 }},\n\t\t\tCtrlWZoom = false,\n\t\t\tNameSet = true,\n\t\t\tKeyFrames = {{\n'
            f'\t\t\t\t[0] = {{ 0, Flags = {{ Linear = true, LockedY = true }}, Value = Polyline {{\n\t\t\t\t\tClosed = true,\n\t\t\t\t\tPoints = {{\n{pts}\n\t\t\t\t\t}}\n\t\t\t\t}} }}\n'
            f'\t\t\t}}\n\t\t}},\n')
