# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/resolve_falso.py — un DaVinci Resolve FALSO en memoria para probar los scripts de colocación (colocar_efectos.py) sin el Resolve del usuario.
"""
Lo justo de la API que usan los scripts de colocación: pistas de video y audio con nombre, encendidas/apagadas y su tipo (mono/stereo), clips con
inicio y duración, Media Pool con ImportMedia / AppendToTimeline y fallos a demanda (`falla_append_audio`, `no_apaga_pistas`) para probar los
caminos de error. DeleteTrack corre los índices de los clips de las pistas de arriba, como Resolve. `operaciones` anota cada llamada que cambia algo.
"""


class Clip:
    def __init__(self, ruta, frames=30, fps=30):
        self.ruta, self.frames, self.fps = str(ruta), int(frames), fps

    def GetClipProperty(self, k):
        return {'File Path': self.ruta, 'Frames': str(self.frames), 'FPS': str(self.fps)}.get(k)


class Item:
    def __init__(self, nombre, ini, dur, pista, tipo, clip=None):
        self.n, self.ini, self.dur, self.pista, self.tipo, self.clip = nombre, int(ini), int(dur), int(pista), tipo, clip
        self.props, self.comps, self.enabled = {}, ['Composition 1'], True

    def GetStart(self):
        return self.ini

    def GetEnd(self):
        return self.ini + self.dur

    def GetDuration(self):
        return self.dur

    def GetName(self):
        return self.n

    def SetName(self, x):
        self.n = x
        return True

    def SetProperty(self, k, v):
        self.props[k] = v
        return True

    def GetMediaPoolItem(self):
        return self.clip

    def GetLeftOffset(self):
        return 0

    def SetClipEnabled(self, v):
        self.enabled = bool(v)
        return True

    def GetClipEnabled(self):
        return self.enabled

    def GetFusionCompNameList(self):
        return list(self.comps)

    def DeleteFusionCompByName(self, x):
        if x in self.comps:
            self.comps.remove(x)
        return True

    def ImportFusionComp(self, r):
        self.comps.append('Composition %d' % (len(self.comps) + 1))
        return object()

    def RenameFusionCompByName(self, a, b):
        self.comps = [b if c == a else c for c in self.comps]
        return True

    def LoadFusionCompByName(self, x):
        return True


class Timeline:
    def __init__(self, inicio=86400, frames_a1=1871, fps=30):
        self.inicio, self.fps = inicio, fps
        self.pistas = {'video': [{'nombre': 'V1', 'on': True, 'sub': None}], 'audio': [{'nombre': 'A1', 'on': True, 'sub': 'stereo'}]}
        self.items = [Item('video', inicio, frames_a1, 1, 'video'), Item('voz', inicio, frames_a1, 1, 'audio')]
        self.no_apaga_pistas = False
        self.operaciones = []

    def GetName(self):
        return 'T'

    def GetSetting(self, k):
        return str(self.fps) if k == 'timelineFrameRate' else None

    def GetStartFrame(self):
        return self.inicio

    def GetTrackCount(self, t):
        return len(self.pistas[t])

    def GetTrackName(self, t, i):
        return self.pistas[t][i - 1]['nombre'] if 1 <= i <= len(self.pistas[t]) else ''

    def SetTrackName(self, t, i, x):
        self.pistas[t][i - 1]['nombre'] = x
        self.operaciones.append(('nombre', t, i, x))
        return True

    def AddTrack(self, t, sub=None):
        self.pistas[t].append({'nombre': '', 'on': True, 'sub': sub})
        self.operaciones.append(('pista+', t, sub))
        return True

    def DeleteTrack(self, t, i):
        del self.pistas[t][i - 1]
        self.items = [x for x in self.items if not (x.tipo == t and x.pista == i)]
        for x in self.items:
            if x.tipo == t and x.pista > i:
                x.pista -= 1
        self.operaciones.append(('pista-', t, i))
        return True

    def GetIsTrackLocked(self, t, i):
        return False

    def SetTrackLock(self, t, i, v):
        return True

    def SetTrackEnable(self, t, i, v):
        self.operaciones.append(('encender' if v else 'apagar', t, i))
        if not self.no_apaga_pistas or v:
            self.pistas[t][i - 1]['on'] = bool(v)
        return True

    def GetIsTrackEnabled(self, t, i):
        return self.pistas[t][i - 1]['on']

    def GetItemListInTrack(self, t, i):
        return [x for x in self.items if x.tipo == t and x.pista == i]

    def DeleteClips(self, xs, ripple=False):
        fuera = {id(x) for x in xs}
        self.items = [x for x in self.items if id(x) not in fuera]
        self.operaciones.append(('borrar', len(xs)))
        return True

    # ayudas de la prueba
    def pista(self, nombre, t='audio'):
        return next((i + 1 for i, p in enumerate(self.pistas[t]) if p['nombre'] == nombre), None)

    def resumen(self):
        return {t: [(p['nombre'], p['on'], p['sub'], sorted((x.n, x.ini, x.dur) for x in self.items if x.tipo == t and x.pista == i + 1))
                    for i, p in enumerate(ps)] for t, ps in self.pistas.items()}


class Carpeta:
    def __init__(self, nombre):
        self.nombre, self.clips, self.subs = nombre, [], []

    def GetClipList(self):
        return list(self.clips)

    def GetSubFolderList(self):
        return list(self.subs)

    def GetName(self):
        return self.nombre


class MediaPool:
    def __init__(self, tl, duracion_wav=None):
        self.tl, self.raiz, self.actual = tl, Carpeta('Master'), None
        self.falla_append_audio = False
        self.duracion_wav = duracion_wav or {}

    def GetRootFolder(self):
        return self.raiz

    def AddSubFolder(self, padre, nombre):
        c = Carpeta(nombre)
        padre.subs.append(c)
        return c

    def GetCurrentFolder(self):
        return self.actual or self.raiz

    def SetCurrentFolder(self, c):
        self.actual = c
        return True

    def ImportMedia(self, rutas):
        destino = self.actual or self.raiz
        nuevos = []
        for r in rutas:
            r = r['FilePath'] if isinstance(r, dict) else r
            c = Clip(r, frames=self.duracion_wav.get(str(r), 30))
            destino.clips.append(c)
            nuevos.append(c)
        return nuevos

    def AppendToTimeline(self, pedidos):
        salida = []
        for p in pedidos:
            tipo = 'video' if p.get('mediaType') == 1 else 'audio'
            if tipo == 'audio' and self.falla_append_audio:
                continue
            it = Item(p['mediaPoolItem'].ruta, p['recordFrame'], p['endFrame'] - p['startFrame'] + 1, p['trackIndex'], tipo, p['mediaPoolItem'])
            self.tl.items.append(it)
            salida.append(it)
        self.tl.operaciones.append(('append', len(salida)))
        return salida


class Proyecto:
    def __init__(self, tl, mp):
        self.tl, self.mp = tl, mp

    def GetName(self):
        return 'zz_PRUEBAS_CC'

    def GetCurrentTimeline(self):
        return self.tl

    def GetMediaPool(self):
        return self.mp


class Resolve:
    COMPOSITE_SCREEN, COMPOSITE_MULTIPLY, SCALE_FILL = 6, 7, 3

    def __init__(self, proyecto):
        self.p = proyecto

    def GetProjectManager(self):
        r = self

        class PM:
            def GetCurrentProject(self):
                return r.p
        return PM()


def nuevo(frames_a1=1871, fps=30):
    tl = Timeline(frames_a1=frames_a1, fps=fps)
    mp = MediaPool(tl)
    pr = Proyecto(tl, mp)
    return Resolve(pr), pr, tl, mp
