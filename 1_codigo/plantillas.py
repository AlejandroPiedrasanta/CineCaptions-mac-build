# CineCaptions · By Cinema Productions
# 1_codigo/plantillas.py — packs de estilos: leer, guardar, elegir y preparar el pack que se aplica.
"""\nplantillas.py\n-------------\nLos packs de estilos: leerlos, escribirlos y decidir cual se aplica.\n\nUn pack NO es contenido que venga dentro del programa: es un FORMATO. El\nusuario abre en Resolve un timeline con los Text+ nombrados como siempre\n-\'contexto\', \'principal\', \'complemento\', \'contexto 2\'...- pulsa importar, y el\nplugin se lo guarda para siempre. A partir de ahi los packs se crean y se\ncomparten sin tocar el programa.\n\nViven FUERA del instalador, en ~/DaVinciSubtitles/plantillas/, por lo mismo\nque sfx_library: dentro de un .exe los archivos son de solo lectura, y ademas\nasi sobreviven a las actualizaciones.\n\n    ~/DaVinciSubtitles/plantillas/<pack>/\n        pack.json                      el pack en modo .drt   (modelo NUEVO)\n        h/pack.drt  v/pack.drt         el timeline entero, por formato\n        estilos.json                   valores de los sets    (modelo VIEJO)\n        h/01-main.setting ...          el nodo Text+ suelto\n        miniaturas/01.png ...          480 x 270\n\nDOS MODELOS, Y POR QUE HAY DOS\n==============================\n**Modelo .drt (el bueno).** El pack ES el timeline exportado. Al usarlo, el\nscript lo importa en Resolve y pasa los clips al Media Pool; generar solo\nescribe StyledText y no toca nada mas.\n\nHizo falta porque el modelo viejo se demostro incapaz de llevar lo que la\ngente diseña de verdad. Al abrir los .drt del pack base se vio que cada\n\"Text+\" es en realidad un GroupOperator con SoftGlow + TextPlus +\nStyledTextFollower + PolyPath y curvas de animacion. El importador guardaba\nSOLO el nodo TextPlus, asi que tiraba el grupo, el brillo, el recorrido y la\nanimacion — y con ellos la POSICION, que vive en el PolyPath y no en el\n\'Center\' del Text+. De ahi el bug que se reportaba como \"el bloque 2 no\nrespeta su posicion\": nunca se habia capturado.\n\n**Modelo de valores (el viejo).** estilos.json + .setting sueltos. Se\nmantiene porque los packs ya importados siguen funcionando, y porque para un\ndiseño sencillo -sin animacion- basta y no obliga a exportar un timeline.\n\nUn mismo pack puede tener los dos, incluso en formatos distintos: cada\nformato (\'h\', \'v\', \'c\') lleva lo que tenga. Cuando hay .drt, manda el .drt.\n\nLas claves de estilos.json son las mismas que las de AUTO_STYLES en los\nscripts de Resolve (font, style, size, tracking, color), a proposito: asi\napply_auto_style los consume sin traducir nada.\n"""
import json
import os
import re
import shutil
import sys
from pathlib import Path
import packs_drt
from i18n import tr
CARPETA_USUARIO = Path.home() / 'DaVinciSubtitles'
CARPETA_PACKS = CARPETA_USUARIO / 'plantillas'
ARCHIVO_DESCRIPCIONES = CARPETA_PACKS / 'descripciones.json'
LARGO_MAXIMO_DESCRIPCION = 120
def leer_descripciones():
    """{nombre de pack: descripcion corta del usuario}."""
    try:
        datos = json.loads(ARCHIVO_DESCRIPCIONES.read_text(encoding='utf-8'))
        if isinstance(datos, dict):
            return {str(k): str(v) for k, v in datos.items()}
        else:
            return {}
    except Exception:
        return {}
def guardar_descripcion(nombre, texto):
    """Guarda (o borra, con texto vacio) la descripcion de un pack."""
    descripciones = leer_descripciones()
    texto = (texto or '').strip()[:LARGO_MAXIMO_DESCRIPCION]
    if texto:
        descripciones[str(nombre)] = texto
    else:
        descripciones.pop(str(nombre), None)
    try:
        CARPETA_PACKS.mkdir(parents=True, exist_ok=True)
        ARCHIVO_DESCRIPCIONES.write_text(json.dumps(descripciones, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        return
ROLES = ('context', 'main', 'complement')
MAX_SETS = 10
MINIATURA = (480, 270)
FORMATOS = ('h', 'v', 'c')
ETIQUETA_FORMATO = {'h': tr('Horizontal'), 'v': tr('Vertical'), 'c': tr('Cuadrado')}
POR_DEFECTO = {'font': 'Montserrat', 'style': 'Regular', 'size': 0.05, 'tracking': 1.0, 'color': (1.0, 1.0, 1.0)}
def nombre_seguro(texto):
    """Un nombre de pack que se pueda usar como carpeta en Windows y en Mac."""
    limpio = re.sub('[<>:\"/\\\\|?*\\x00-\\x1f]', ' ', str(texto or '')).strip()
    limpio = re.sub('\\s+', ' ', limpio)
    limpio = limpio.rstrip('. ')
    return limpio[:60] or 'pack'
def formato_de(ancho, alto):
    """\'h\', \'v\' o \'c\' segun la forma del fotograma.\n\n    El margen del 5%: un 1920x1080 recortado a 1912x1080 sigue siendo\n    horizontal, y un 1080x1080 con un pixel de mas no deja de ser cuadrado.\n    """
    a, b = (float(ancho or 0), float(alto or 0))
    if a <= 0 or b <= 0:
        return 'h'
    else:
        if abs(a - b) <= 0.05 * max(a, b):
            return 'c'
        else:
            return 'v' if b > a else 'h'
def _clave_set(n):
    return f'{int(n):02d}'
def nombre_setting(n, rol):
    """01-main.setting, o base.setting para la plantilla suelta."""
    if rol == 'base':
        return 'base.setting'
    else:
        return f'{_clave_set(n)}-{rol}.setting'
def nombre_miniatura(n):
    return 'base.png' if n == 'base' else f'{_clave_set(n)}.png'
def normalizar_estilo(bruto):
    """Deja un estilo utilizable venga como venga del JSON.\n\n    Un estilos.json editado a mano -que es un caso esperado, para eso es\n    texto- no puede tumbar la generacion entera. Lo que falte se rellena; lo\n    que venga con el tipo raro se convierte o se descarta.\n    """
    if not isinstance(bruto, dict):
        return dict(POR_DEFECTO)
    else:
        e = dict(POR_DEFECTO)
        for clave in ['font', 'style']:
            v = bruto.get(clave)
            if isinstance(v, str) and v.strip():
                    e[clave] = v.strip()
        for clave in ['size', 'tracking', 'line_spacing']:
            v = bruto.get(clave)
            try:
                if v is not None:
                    e[clave] = float(v)
            except (TypeError, ValueError):
                pass
        color = bruto.get('color')
        if isinstance(color, (list, tuple)) and len(color) >= 3:
                try:
                    e['color'] = tuple((max(0.0, min(1.0, float(c))) for c in color[:3]))
                except (TypeError, ValueError):
                    pass
        contorno = bruto.get('outline')
        if isinstance(contorno, dict):
            oc = {}
            try:
                oc['thickness'] = float(contorno.get('thickness', 0.0))
            except (TypeError, ValueError):
                oc['thickness'] = 0.0
            col = contorno.get('color')
            if isinstance(col, (list, tuple)) and len(col) >= 3:
                try:
                    oc['color'] = tuple((max(0.0, min(1.0, float(c))) for c in col[:3]))
                except (TypeError, ValueError):
                    oc['color'] = (0.0, 0.0, 0.0)
            else:
                oc['color'] = (0.0, 0.0, 0.0)
            if oc['thickness'] > 0:
                e['outline'] = oc
        return e
class Pack:
    """Un pack ya leido del disco.\n\n    \'problemas\' no es decoracion: es la lista de lo que le falta, y la ventana\n    la ensena. Un pack a medias tiene que decir en que esta a medias, no\n    aparecer como si estuviera completo y fallar al generar.\n    """
    def __init__(self, nombre, carpeta, datos, incorporado=False):
        self.nombre = nombre
        self.carpeta = Path(carpeta)
        self.datos = datos or {}
        self.problemas = []
        self.notas = []
        self.incorporado = bool(incorporado)
        self._cache_drt = {}
        self._cache_drb = {}
        self._cache_drb_fuentes = {}
    @property
    def guion(self):
        """Marca del estilo «guion» (la frase se arma palabra a palabra: guion_captions.py / guion_planificador.py) o None."""
        g = self.datos.get('guion')
        return None if g == 'mezcla' else (g or None)
    @property
    def mezcla(self):
        """v5.4.30: True si es un estilo propio hecho con «Crea tu estilo» MEZCLANDO looks de los tres temas (mezcla_planificador.py): no lleva clips propios (usa los de Kinetic, Referencia y VIRAL)."""
        return self.datos.get('guion') == 'mezcla'
    @property
    def looks(self):
        """Los looks que rotan en un pack de mezcla (ids de mezcla_planificador.catalogo(): 't1:lima', 't2:3', 't3:shatter'…); [] si no es de mezcla."""
        return [str(i) for i in (self.datos.get('looks') or [])] if self.mezcla else []
    @property
    def kinetic(self):
        """True si es el estilo «Kinetic» (títulos de gancho: kinetic_planificador.py; sus clips son elementos —héroe, cinta, anillo…— y no sets arriba/principal/abajo)."""
        return self.datos.get('guion') in ('kinetic', 'viral')
    @property
    def viral(self):
        """True si es el estilo «VIRAL» (viral_planificador.py): también un pack de ELEMENTOS —por eso `kinetic` también es True y comparten el camino de la app y de Resolve—, pero con sus propios clips («v fina», «v shatter»…) y su propio planificador."""
        return self.datos.get('guion') == 'viral'
    @property
    def formatos(self):
        """Los formatos que este pack trae de verdad, en orden estable."""
        traidos = self.datos.get('formatos') or {}
        return tuple((f for f in FORMATOS if traidos.get(f)))
    def ruta_drt(self, formato):
        """El .drt de ese formato, o None. Rutas relativas a la carpeta."""
        bloque = (self.datos.get('formatos') or {}).get(formato) or {}
        cruda = bloque.get('drt')
        if not cruda:
            return
        else:
            ruta = Path(cruda)
            if not ruta.is_absolute():
                ruta = self.carpeta / ruta
            return ruta if ruta.is_file() else None
    def ruta_drb(self, formato):
        """El .drb (bin exportado) de ese formato, o None. Misma regla que\n        ruta_drt: rutas relativas a la carpeta del pack."""
        bloque = (self.datos.get('formatos') or {}).get(formato) or {}
        cruda = bloque.get('drb')
        if not cruda:
            return
        else:
            ruta = Path(cruda)
            if not ruta.is_absolute():
                ruta = self.carpeta / ruta
            return ruta if ruta.is_file() else None
    def formatos_drt(self):
        return tuple((f for f in self.formatos if self.ruta_drt(f)))
    def formatos_drb(self):
        return tuple((f for f in self.formatos if self.ruta_drb(f)))
    @property
    def modo(self):
        """\'drt\' si el pack lleva timeline O bin exportado; \'valores\' si no.\n\n        El .drb cuenta como modo timeline (v1.0.57): un pack solo-bin se\n        genera por el peldaño drb, no por valores.\n        """
        return 'drt' if self.formatos_drt() or self.formatos_drb() else 'valores'
    @property
    def es_basicos(self):
        """True si es un pack de SUBTITULOS BASICOS (v1.0.69): clips\n        \'basico inferior N\' / \'traducion superior N\' en vez de sets\n        contexto/principal/complemento. No sale en la lista de packs\n        dinamicos ni viaja por para_manifiesto — tiene su propio emisor\n        (basicos_para_manifiesto) y su tarjeta propia en la ventana."""
        return any(((self.info_drb(f) or {}).get('basicos') for f in self.formatos))
    def info_drt(self, formato):
        """Lo que trae el .drt de ese formato, leido sin abrir Resolve.\n\n        Cacheado por instancia: la ventana pregunta varias veces (cuantos\n        sets, que fuentes, que avisos) y cada lectura descomprime todas las\n        comps del timeline.\n        """
        if formato not in self._cache_drt:
            ruta = self.ruta_drt(formato)
            self._cache_drt[formato] = packs_drt.leer(ruta) if ruta else None
        return self._cache_drt[formato]
    def info_drb(self, formato, con_estilos=False):
        """Lo que trae el .drb de ese formato, leido sin abrir Resolve.\n\n        Gemela de info_drt para los packs solo-bin (v1.0.57): mismos\n        campos (packs_drt.leer_drb), cacheada por instancia. \'con_estilos\'\n        (v3.3.3) pide ademas el estilo de cada TextPlus (caro: solo lo usa\n        estilos_para_medir).\n        """
        clave = (formato, bool(con_estilos))
        if clave not in self._cache_drb:
            ruta = self.ruta_drb(formato)
            self._cache_drb[clave] = packs_drt.leer_drb(ruta, con_estilos=con_estilos) if ruta else None
        return self._cache_drb[clave]
    def numeros_de_set(self, formato):
        info = self.info_drt(formato)
        if info and info.get('ok'):
            return list(info['completos'])
        info = self.info_drb(formato)
        if info and info.get('ok'):
            return list(info['completos'])
        bloque = (self.datos.get('formatos') or {}).get(formato) or {}
        sets = bloque.get('sets') or {}
        numeros = []
        for clave in sets:
            try:
                n = int(clave)
            except (TypeError, ValueError):
                continue
            if not 1 <= n <= MAX_SETS:
                continue
            numeros.append(n)
        return sorted(numeros)
    def estilos_de(self, n, formato):
        """Los tres roles de un set, con la forma que espera apply_auto_style.\n\n        Devuelve None si ese set no esta en ese formato — y quien llama tiene\n        que decirlo, no colocar en silencio con el diseno de fabrica.\n        """
        bloque = (self.datos.get('formatos') or {}).get(formato) or {}
        if n == 'base':
            crudo = bloque.get('base')
            return normalizar_estilo(crudo) if crudo else None
        else:
            crudo = (bloque.get('sets') or {}).get(str(int(n)))
            if not isinstance(crudo, dict):
                return
            else:
                return {rol: normalizar_estilo(crudo.get(rol)) for rol in ROLES}
    def resolucion(self, formato):
        """(ancho, alto) del timeline de origen de ese formato, o un valor\n        de referencia razonable si no se guardo (packs de la v1.0.25, que no\n        lo escribian). Solo se usa para la relacion de aspecto de la\n        previsualizacion -nunca para generar-, asi que un valor aproximado\n        no rompe nada."""
        bloque = (self.datos.get('formatos') or {}).get(formato) or {}
        res = bloque.get('resolucion')
        if isinstance(res, (list, tuple)) and len(res) == 2 and all((isinstance(v, (int, float)) and v > 0 for v in res)):
            return (int(res[0]), int(res[1]))
        else:
            return (1080, 1920) if formato == 'v' else (1920, 1080)
    def ruta_setting(self, n, rol, formato):
        """El .setting de ese rol, o None si el pack no lo trae."""
        p = self.carpeta / formato / nombre_setting(n, rol)
        return p if p.is_file() else None
    def ruta_miniatura(self, n):
        p = self.carpeta / 'miniaturas' / nombre_miniatura(n)
        return p if p.is_file() else None
    def fuentes(self):
        """Las (fuente, peso) que necesita el pack, sin repetir.\n\n        Sirve para avisar antes de generar: si falta una tipografia, Resolve\n        pone otra por su cuenta y el pack se ve distinto sin que nadie diga\n        nada. Eso es exactamente el tipo de fallo silencioso que no queremos.\n        """
        vistas = set()
        for formato in self.formatos:
            drb = self.ruta_drb(formato)
            if drb:
                if formato not in self._cache_drb_fuentes:
                    self._cache_drb_fuentes[formato] = packs_drt.fuentes_de_drb(drb)
                vistas.update(self._cache_drb_fuentes[formato])
            info = self.info_drt(formato)
            if info and info.get('ok'):
                    vistas.update(info['fuentes'])
                    continue
            for n in list(self.numeros_de_set(formato)) + ['base']:
                estilos = self.estilos_de(n, formato)
                if not estilos:
                    continue
                else:
                    candidatos = [estilos] if n == 'base' else list(estilos.values())
                    for e in candidatos:
                        vistas.add((e.get('font', ''), e.get('style', '')))
        return sorted((v for v in vistas if v[0]))
    def formato_para(self, ancho, alto):
        """Que variante usar en un timeline de ese tamano.\n\n        Devuelve (formato, aviso). El aviso NO es opcional: si el pack solo\n        trae horizontal y el video es vertical, el resultado se va a ver mal y\n        el usuario tiene que enterarse antes, no al mirar el render.\n        """
        traidos = self.formatos
        if not traidos:
            return (None, f'El pack \'{self.nombre}\' no tiene ningun formato guardado. Vuelve a importarlo.')
        else:
            quiere = formato_de(ancho, alto)
            if quiere in traidos:
                return (quiere, None)
            else:
                orden = {'c': ('v', 'h'), 'v': ('c', 'h'), 'h': ('c', 'v')}[quiere]
                otro = next((f for f in orden if f in traidos), traidos[0])
                return (otro, f'El pack \'{self.nombre}\' no trae version {ETIQUETA_FORMATO[quiere].lower()}: uso la {ETIQUETA_FORMATO[otro].lower()}. Los tamanos de letra no se traducen entre formatos, asi que revisa como queda. Para arreglarlo, añade tambien el timeline {ETIQUETA_FORMATO[quiere].lower()} del pack.')
    def revisar(self):
        """Rellena self.problemas y self.notas. Se llama al cargar.\n\n        \'problemas\' es lo que IMPIDE usar el pack (no tiene formatos, no se\n        puede leer el .drt). \'notas\' es informacion de diagnostico: sets a\n        los que les falta un rol, nombres repetidos. Los dos estan separados\n        desde la v1.0.29 a peticion del usuario -\"si en la plantilla no esta\n        completo x grupo no digas falta esto, simplemente trabaja con los que\n        haya y omites el incompleto\"-.\n\n        Y es lo que hace el generador de todos modos: numeros_de_set()\n        devuelve solo los sets COMPLETOS, asi que un set al que le falta un\n        rol nunca se usa. Avisarlo en naranja era un reproche por algo que ya\n        estaba resuelto solo. Las notas no se tiran: van al tooltip y al\n        registro, para poder diagnosticar cuando haga falta.\n        """
        self.problemas = []
        self.notas = []
        if not self.formatos:
            self.problemas.append(tr('no tiene ningun formato guardado'))
            return self.problemas
        if self.mezcla:                      # sin archivos propios: solo hace falta que sus looks existan en el catálogo
            try:
                import mezcla_planificador
                if not any(mezcla_planificador.look_de(i) for i in self.looks):
                    self.problemas.append(tr('no tiene ningún estilo elegido'))
            except Exception:
                pass
            return self.problemas
        if self.kinetic:                     # sus clips no son sets: lo único que puede faltarle es el .drb
            if not any(self.ruta_drb(f) for f in self.formatos):
                self.problemas.append(tr('falta el archivo .drb del pack'))
            return self.problemas
        else:
            por_aviso, por_nota = ({}, {})
            for formato in self.formatos:
                info = self.info_drt(formato) or self.info_drb(formato)
                if info is not None:
                    if not info.get('ok'):
                        por_aviso.setdefault(info.get('error') or tr('no se puede leer'), []).append(formato)
                    else:
                        if not info.get('completos') and (not info.get('basicos')):
                            por_aviso.setdefault(tr('no tiene ningun set completo'), []).append(formato)
                        else:
                            for linea in packs_drt.detalle(info):
                                por_nota.setdefault(linea, []).append(formato)
                else:
                    lineas = []
                    if not self.numeros_de_set(formato):
                        lineas.append(tr('no tiene ningun set'))
                    for linea in lineas:
                        por_aviso.setdefault(linea, []).append(formato)
                    if self.estilos_de('base', formato) is None:
                        por_nota.setdefault(tr('sin plantilla \'base\' (las palabras sueltas usaran el estilo principal)'), []).append(formato)
            def repartir(origen, destino):
                for linea, formatos in origen.items():
                    if len(formatos) == len(self.formatos):
                        destino.append(linea)
                    else:
                        etiquetas = ', '.join((ETIQUETA_FORMATO[f].lower() for f in formatos))
                        destino.append(tr('{linea} (en {formatos})', linea=linea, formatos=etiquetas))
            repartir(por_aviso, self.problemas)
            repartir(por_nota, self.notas)
            return self.problemas
def carpeta_de_packs():
    return CARPETA_PACKS
def _leer_json(ruta):
    try:
        datos = json.loads(Path(ruta).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None
def cargar(carpeta, incorporado=False):
    """Lee un pack de una carpeta. Devuelve None si no hay nada legible.\n\n    Lee LOS DOS archivos y los mezcla por formato: \'pack.json\' (modelo .drt)\n    y \'estilos.json\' (modelo de valores). Un mismo pack puede tener el\n    timeline de un formato y solo los valores de otro, y las dos cosas del\n    mismo — cuando hay .drt, es el que manda al generar.\n    """
    carpeta = Path(carpeta)
    nuevo = _leer_json(carpeta / 'pack.json') or {}
    viejo = _leer_json(carpeta / 'estilos.json') or {}
    if not nuevo and (not viejo):
        return
    else:
        datos = {'version': 2, 'nombre': nuevo.get('nombre') or viejo.get('nombre') or carpeta.name, 'formatos': {}}
        if nuevo.get('guion'):
            datos['guion'] = str(nuevo['guion'])
        if nuevo.get('guion') == 'mezcla' and isinstance(nuevo.get('looks'), list):
            datos['looks'] = [str(i) for i in nuevo['looks']]
        for origen in [viejo, nuevo]:
            for formato, bloque in (origen.get('formatos') or {}).items():
                if formato in FORMATOS and isinstance(bloque, dict):
                        datos['formatos'].setdefault(formato, {}).update(bloque)
        pack = Pack(datos['nombre'], carpeta, datos, incorporado=incorporado)
        pack.revisar()
        return pack
NOMBRE_INCORPORADO = 'Base títulos dinámicos'
# v5.4.5: los packs de FÁBRICA (nombre interno -> nombre que ve el usuario). El nombre interno no cambia (preferencias, GO, carpetas y proyectos guardados
# lo siguen usando); en pantalla se llaman «Tema 1/2/3» (v5.4.19; antes «Shine Kinetic», «Shine Referencia» y «VIRAL») y NO se pueden quitar de la lista.
FABRICA = {'Kinetic': 'Tema 1', 'Referencia': 'Tema 2', 'VIRAL': 'Tema 3', 'Tema4': 'Tema 4', 'Tema5': 'Tema 5', 'Tema6': 'Tema 6'}
# v5.4.19 (pedido del usuario): SOLO existen esos tres temas en la interfaz: el slider de «Pack de estilos» y el chip «Estilo» de Inicio no enseñan nada más (ni packs importados, ni
# «Viral · superior/inferior», ni «Añadir plantilla», ni «Crea tu estilo»). Los packs siguen en el disco; con False vuelve todo lo de antes.
SOLO_TEMAS = True
# v5.4.20: lo que enseña el panel de cada tema (nombre interno -> (frase corta, qué hace)).
TEMAS_INFO = {
    'Kinetic': ('Títulos de gancho', 'Títulos neón: palabra enorme lima o magenta, pegatinas inclinadas, letra a mano y círculos que se dibujan, con un golpe de sonido.'),
    'Referencia': ('Captions palabra a palabra', 'Una línea fina con la palabra importante en negrita y en grande, al ritmo de la voz.'),
    'VIRAL': ('Subtítulos virales', 'Texto fino con negrita cursiva, efectos de impacto y emojis que aparecen con la voz.'),
    'Tema4': ('Captions limpios', 'Texto blanco que se arma palabra a palabra en un recuadro, con la palabra clave grande y las conectoras pequeñas.'),
    'Tema5': ('Edición total', 'Lo edito todo con el sistema de los reels virales: captions sans + serif, pasos y deslizador en pantalla, escenas de papel, pantalla dividida y sonido.'),
    'Tema6': ('Editorial', 'Edición elegante y cálida: captions en serif fina con la frase clave grande en lima, escenas melocotón con tarjetas blancas, visor de cámara, barra de búsqueda y perfil que cuenta.'),
}


def pack_permitido(nombre):
    """v5.4.22: ¿se enseña este pack? Los tres temas de fábrica y los que hizo o importó el usuario («Crea tu estilo», «Añadir plantilla»); los demás packs que trae el programa
    («Viral · superior/inferior»…) no. Con SOLO_TEMAS = False, todos."""
    if not SOLO_TEMAS or nombre in FABRICA:
        return True
    try:
        p = buscar_pack(nombre)
    except Exception:
        return False
    return p is not None and not getattr(p, 'incorporado', False)


def info_de_tema(nombre):
    """(frase corta, descripción) de un tema de fábrica, o ('', '')."""
    return TEMAS_INFO.get(nombre, ('', ''))


def nombre_visible(nombre):
    """El nombre con el que se enseña un pack (los de fábrica son «Shine …»; el resto, el suyo)."""
    return FABRICA.get(nombre, nombre)


def es_de_fabrica(nombre):
    return nombre in FABRICA


# v5.8: los packs que cambiaron de contenido llevan una «revisión»; los scripts de Resolve la suman al nombre del bin del pack
# ('RCS · <pack> · <revisión> · v'), asi un bin viejo que ya estaba en el proyecto (con los clips anteriores) no se reutiliza.
REVISION_BIN = {'Viral · superior': 'Luxe 5', 'Viral · inferior': 'Luxe 5', 'Referencia': 'Ref 6', 'Kinetic': 'Kin 7', 'VIRAL': 'Vir 5', 'Tema4': 'T4 6', 'Tema5': 'T5 6', 'Tema6': 'T6 6'}   # v5.5.8: T5/T6 2 = su diseño propio (pack_tema5.py); 3 = el banner de CineCaptions en el Inspector (banner_inspector.py); 4 = el banner arriba de todo (encima de las pestañas); 5 = el banner con el LOGO en el Text+ «Template» (el que enseña el Inspector); 6 = sombra oscura para leerse sobre fondos claros (v5.5.10)
NOMBRE_BASICOS = 'Subtítulos básicos'
POSICIONES_BASICOS = ('inferior', 'superior')
_PISTAS_FORMATO = (('horizontal', 'h'), ('vertical', 'v'), ('cuadrado', 'c'), ('square', 'c'))
def carpeta_incluida():
    """La carpeta \'plantillas_incluidas/\' del programa, o None."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent / '2_recursos'
    carpeta = base / 'plantillas_incluidas'
    try:
        return carpeta if carpeta.is_dir() else None
    except OSError:
        return None
_MEMO_INC = {}
def _firma_incluidos():
    """Nombre, tamaño y fecha de cada archivo de plantillas_incluidas (barato: ~55 stat). Cambia si se toca algo."""
    carpeta = carpeta_incluida()
    if carpeta is None:
        return None
    firma = []
    pendientes = [str(carpeta)]
    while pendientes:
        actual = pendientes.pop()
        try:
            with os.scandir(actual) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        pendientes.append(e.path)
                    else:
                        st = e.stat()
                        firma.append((e.path, st.st_size, st.st_mtime_ns))
        except OSError:
            firma.append((actual, '?'))
    return tuple(sorted(firma))
def _memo_incorporados(clave, construir):
    """v5.4: pack_incorporado()/packs_incorporados() se llamaban en ~15 sitios (cada visita a Inicio incluida) y cada
    vez releian los .drt/.drb del disco (~0,3 s). Los Pack son de solo lectura y cachean lo que leen: se comparten."""
    firma = _firma_incluidos()
    memo = _MEMO_INC.get(clave)
    if memo is not None and memo[0] == firma:
        return memo[1]
    valor = construir()
    _MEMO_INC[clave] = (firma, valor)
    return valor
def pack_incorporado():
    """El pack que se entrega con el producto, o None si no hay archivos.\n\n    No se copia a ~/DaVinciSubtitles: se usa directo desde el bundle. Copiarlo\n    lo dejaria congelado en la version que se instalo primero, y ademas\n    duplicaria 400 KB por cada equipo sin ganar nada — no se puede editar de\n    todos modos.\n    """
    return _memo_incorporados('principal', _construir_pack_incorporado)
def _construir_pack_incorporado():
    carpeta = carpeta_incluida()
    if carpeta is None:
        return None
    formatos = {}
    for ruta in sorted(carpeta.glob('*.drt')):
        minus = ruta.name.lower()
        formato = next((f for pista, f in _PISTAS_FORMATO if pista in minus),
                       None)
        if formato and formato not in formatos:
            bloque = {'drt': ruta.name}
            drb = ruta.with_suffix('.drb')
            if drb.is_file():
                bloque['drb'] = drb.name
            try:
                valores = packs_drt.estilos(ruta)
            except Exception:
                valores = {'sets': {}, 'base': None}
            sets = {str(n): roles
                    for n, roles in (valores.get('sets') or {}).items()
                    if roles}
            if sets:
                bloque['sets'] = sets
            if valores.get('base'):
                bloque['base'] = valores['base']
            formatos[formato] = bloque
    if not formatos:
        return None
    pack = Pack(NOMBRE_INCORPORADO, carpeta,
                {'version': 2, 'nombre': NOMBRE_INCORPORADO,
                 'formatos': formatos},
                incorporado=True)
    pack.revisar()
    return pack
def packs_incorporados():
    """TODOS los packs que viajan dentro del programa, el de «auto» primero.\n\n    Desde la v1.0.57 hay mas de uno: el pack base (archivos planos en\n    plantillas_incluidas/, sigue siendo lo que significa «Diseño\n    automatico») y las SUBCARPETAS, una por pack, cada una con su\n    pack.json (el mismo esquema que los packs del usuario, leido con el\n    mismo cargar()). La plantilla «Títulos dinámicos II» llega asi: dos\n    packs solo-.drb (superior/inferior) que comparten la horizontal.\n    Carpetas ASCII; el nombre CON tildes va dentro del pack.json.\n    """
    return list(_memo_incorporados('todos', _construir_packs_incorporados))
def _construir_packs_incorporados():
    packs = []
    principal = pack_incorporado()
    if principal is not None:
        packs.append(principal)
    carpeta = carpeta_incluida()
    if carpeta is None:
        return packs
    else:
        try:
            subcarpetas = sorted((p for p in carpeta.iterdir() if p.is_dir()))
        except OSError:
            return packs
        for sub in subcarpetas:
            pack = cargar(sub, incorporado=True)
            if pack is not None:
                packs.append(pack)
        return packs
_MEMO_PACKS = {}
def _firma_packs():
    """Algo barato que cambia si aparece, desaparece o se toca un pack: el\n    mtime de la carpeta de packs, de la incluida y de sus subcarpetas."""
    firma = []
    for raiz in (carpeta_de_packs(), carpeta_incluida()):
        try:
            if raiz is None or not raiz.is_dir():
                firma.append(None)
                continue
            firma.append(raiz.stat().st_mtime_ns)
            for sub in sorted(p for p in raiz.iterdir() if p.is_dir()):
                firma.append((sub.name, sub.stat().st_mtime_ns))
        except OSError:
            firma.append('?')
    return tuple(firma)
def invalidar_packs():
    """Olvida la lista memorizada (quien escribe un pack la llama; la firma\n    por mtime lo cubre igual, esto es cinturon)."""
    _MEMO_PACKS.clear()
def listar_packs():
    """Todos los packs disponibles. Los incorporados van primero.\n\n    v3.3.3: memo por firma de carpetas. MEDIDO: 1,1 s por llamada (8 .drb\n    leidos) y el arranque la pedia dos veces seguidas.\n    """
    firma = _firma_packs()
    if _MEMO_PACKS.get('firma') == firma:
        return list(_MEMO_PACKS['packs'])
    else:
        packs = _listar_packs()
        _MEMO_PACKS['firma'] = firma
        _MEMO_PACKS['packs'] = list(packs)
        return packs
def _listar_packs():
    packs = packs_incorporados()
    raiz = carpeta_de_packs()
    if raiz.is_dir():
        for carpeta in sorted(raiz.iterdir()):
            if not carpeta.is_dir():
                continue
            else:
                pack = cargar(carpeta)
                if pack is None:
                    continue
                else:
                    repuesto = next((i for i, p in enumerate(packs) if p.incorporado and p.nombre == pack.nombre), None)
                    if repuesto is not None:
                        packs[repuesto] = pack
                    else:
                        packs.append(pack)
    return packs
def guardar_formato(nombre, formato, sets, base=None, resolucion=None):
    """Escribe (o actualiza) UN formato de un pack.\n\n    Se MEZCLA con lo que ya hubiera en vez de sobrescribir el archivo entero:\n    importar el timeline vertical no puede borrar el horizontal que se importo\n    antes. Ese era el error facil de cometer aqui.\n\n    \'sets\' es {numero: {rol: estilo}} y \'base\' un estilo suelto.\n    Devuelve la carpeta del pack.\n    """
    if formato not in FORMATOS:
        raise ValueError(f'formato desconocido: {formato!r}')
    carpeta = carpeta_de_packs() / nombre_seguro(nombre)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / 'estilos.json'

    datos = {}
    if ruta.is_file():
        try:
            previo = json.loads(ruta.read_text(encoding='utf-8'))
            if isinstance(previo, dict):
                datos = previo
        except (OSError, ValueError):
            datos = {}

    datos['version'] = 1
    datos['nombre'] = nombre
    datos.setdefault('formatos', {})

    limpios = {}
    for n, roles in (sets or {}).items():
        try:
            n = int(n)
        except (TypeError, ValueError):
            continue
        if not 1 <= n <= MAX_SETS or not isinstance(roles, dict):
            continue
        limpios[str(n)] = {rol: normalizar_estilo(roles.get(rol))
                           for rol in ROLES if roles.get(rol)}
    bloque = {'sets': limpios}
    if base:
        bloque['base'] = normalizar_estilo(base)
    if resolucion:
        bloque['resolucion'] = [int(resolucion[0]), int(resolucion[1])]
    datos['formatos'][formato] = bloque

    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False),
                    encoding='utf-8')
    return carpeta
def estilos_para_medir(nombre):
    """{formato: {\"rol|n\": {font, style, size, tracking}}} del pack elegido\n    (v3.3.1): lo que la app necesita para MEDIR el ancho de una linea con\n    la tipografia del pack y poner el emoji al final (pedido literal:\n    «que pertenezca a la linea de la palabra»). Manda el .drb cuando lo\n    hay (es el diseño que se importa — leccion v1.0.56); si no, los\n    valores del pack.json. \"auto\" = el pack incorporado; \"media_pool\" o un\n    pack de basicos = {} (sin estilo medible el gemelo pone el emoji\n    encima del bloque, como en la v3.3.0). Nunca lanza.\n    """
    try:
        if nombre in ('media_pool', '', None):
            return {}
        else:
            pack = pack_incorporado() if nombre == 'auto' else buscar_pack(nombre)
            if pack is None or pack.es_basicos:
                return {}
            else:
                fuera = {}
                for f in pack.formatos:
                    estilos = dict((pack.info_drb(f, con_estilos=True) or {}).get('estilos') or {})
                    if not estilos:
                        for n in pack.numeros_de_set(f):
                            for rol, est in (pack.estilos_de(n, f) or {}).items():
                                if est and est.get('font') and est.get('size'):
                                            estilos[f'{rol}|{n}'] = est
                        base = pack.estilos_de('base', f)
                        if base and base.get('font') and base.get('size'):
                                    estilos['base|0'] = base
                    if estilos:
                        fuera[f] = estilos
                return fuera
    except Exception:
        return {}
def buscar_pack(nombre):
    """El pack que se llama asi, mire donde mire. None si no esta.\n\n    Hay que pasar por aca y no por cargar(carpeta_de_packs() / ...): el pack\n    incorporado no vive en la carpeta del usuario, y buscarlo alli devolvia\n    None — o sea, elegirlo y que al generar no se aplicara nada.\n    """
    if nombre in ['auto', 'media_pool', '', None]:
        return
    else:
        directo = cargar(carpeta_de_packs() / nombre_seguro(nombre))
        if directo is not None:
            return directo
        else:
            for incorporado in packs_incorporados():
                if incorporado.nombre == nombre:
                    return incorporado
            return
def guardar_drt(nombre, formato, ruta_drt):
    """Añade (o reemplaza) el timeline de un formato de un pack.\n\n    Devuelve (pack, avisos). No borra lo que ya hubiera de los otros\n    formatos ni el estilos.json del modelo viejo: los dos conviven.\n    """
    if formato not in FORMATOS:
        raise ValueError(f'formato desconocido: {formato!r}')
    else:
        origen = Path(ruta_drt)
        info = packs_drt.leer(origen)
        if not info.get('ok'):
            return (None, [info.get('error') or tr('No pude leer ese .drt.')])
        else:
            carpeta = carpeta_de_packs() / nombre_seguro(nombre)
            (carpeta / formato).mkdir(parents=True, exist_ok=True)
            destino = carpeta / formato / 'pack.drt'
            try:
                shutil.copyfile(origen, destino)
            except OSError as exc:
                return (None, [tr('No pude guardar el pack en {destino}: {exc}', destino=destino, exc=exc)])
            datos = _leer_json(carpeta / 'pack.json') or {}
            datos['version'] = 2
            datos['nombre'] = nombre
            datos.setdefault('formatos', {})
            datos['formatos'].setdefault(formato, {})
            datos['formatos'][formato].update({'drt': f'{formato}/pack.drt', 'origen': origen.name})
            try:
                (carpeta / 'pack.json').write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding='utf-8')
            except OSError as exc:
                return (None, [tr('No pude escribir pack.json: {exc}', exc=exc)])
            pack = cargar(carpeta)
            if pack is None:
                return (None, [tr('Guardé el pack pero no puedo volver a leerlo.')])
            else:
                return (pack, packs_drt.detalle(info))
def guardar_drb(nombre, formato, ruta_drb):
    """Añade (o reemplaza) el bin exportado de un formato de un pack.\n\n    Gemela de guardar_drt para el flujo de la v1.0.57: el usuario exporta\n    su bin (clic derecho → Exportar bandeja…), lo importa aqui y el\n    peldaño drb lo mete DIRECTO al Media Pool en cada corrida — posicion y\n    animacion exactas, el flujo que el usuario valido 10/10. Convive con un\n    .drt del mismo formato si lo hay (el prep prueba el drb primero).\n    """
    if formato not in FORMATOS:
        raise ValueError(f'formato desconocido: {formato!r}')
    else:
        origen = Path(ruta_drb)
        info = packs_drt.leer_drb(origen)
        if not info.get('ok'):
            return (None, [info.get('error') or tr('No pude leer ese .drb.')])
        else:
            carpeta = carpeta_de_packs() / nombre_seguro(nombre)
            (carpeta / formato).mkdir(parents=True, exist_ok=True)
            destino = carpeta / formato / 'pack.drb'
            try:
                shutil.copyfile(origen, destino)
            except OSError as exc:
                return (None, [tr('No pude guardar el pack en {destino}: {exc}', destino=destino, exc=exc)])
            datos = _leer_json(carpeta / 'pack.json') or {}
            datos['version'] = 2
            datos['nombre'] = nombre
            datos.setdefault('formatos', {})
            datos['formatos'].setdefault(formato, {})
            datos['formatos'][formato].update({'drb': f'{formato}/pack.drb', 'origen': origen.name})
            try:
                (carpeta / 'pack.json').write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding='utf-8')
            except OSError as exc:
                return (None, [tr('No pude escribir pack.json: {exc}', exc=exc)])
            pack = cargar(carpeta)
            if pack is None:
                return (None, [tr('Guardé el pack pero no puedo volver a leerlo.')])
            else:
                return (pack, packs_drt.detalle(info))
CARPETA_CACHE_SETTINGS = Path.home() / 'DaVinciSubtitles' / 'plantillas_cache'
def materializar_incorporado(pack):
    """Escribe los .setting del pack incorporado en su cache. Idempotente.\n\n    Devuelve la carpeta base de la cache, o None si no se pudo escribir —\n    y en ese caso quien llama sigue sin cache (el modo valores de siempre),\n    nunca aborta. Es la \'opcion B\': el pack instalado en el equipo, para\n    que armar los subtitulos no dependa de pasar clips al Media Pool.\n    """
    try:
        from version import APP_VERSION as _app
    except Exception:
        _app = '?'
    base = CARPETA_CACHE_SETTINGS / 'incorporado'
    try:
        for formato in pack.formatos:
            ruta_drt = pack.ruta_drt(formato)
            if not ruta_drt:
                continue
            destino = base / formato
            marcador = destino / 'generado_por.json'
            try:
                firma = {'app': _app, 'drt_bytes': ruta_drt.stat().st_size}
            except OSError:
                continue
            try:
                vieja = json.loads(marcador.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                vieja = None
            if vieja == firma and any(destino.glob('*.setting')):
                continue
            piezas = packs_drt.settings(ruta_drt)
            if not piezas:
                continue
            destino.mkdir(parents=True, exist_ok=True)
            for (rol, n), texto in piezas.items():
                (destino / nombre_setting(n, rol)).write_text(
                    texto, encoding='utf-8')
            marcador.write_text(json.dumps(firma), encoding='utf-8')
        return base if base.is_dir() else None
    except OSError:
        return None
ACENTOS = 'áéíóúÁÉÍÓÚñÑüÜ'
def _sets_sin_acentos(info):
    """{rol: [numeros de set]} cuya tipografia NO dibuja los ACENTOS.\n\n    v1.0.61, pedido literal: «si la palabra tiene tilde no debes usar la\n    combinacion que tiene la tipografia Tempting o alguna otra que su\n    caligrafia no pueda generar tildes». Solo un False medido veta; el\n    None de puede_dibujar (fuente sin archivo a la vista) NO — vetar por\n    desconocimiento recorta sets sanos.\n    """
    import fuentes_sistema
    tip = (info or {}).get('tipografias') or {}
    fuera = {}
    for clave, fuente in tip.items():
        rol, _, n = clave.partition('|')
        try:
            n = int(n)
        except ValueError:
            pass
        else:
            if rol == 'base' or n <= 0:
                continue
            else:
                familia, estilo = fuente
                if fuentes_sistema.puede_dibujar(familia, estilo, ACENTOS) is False:
                    fuera.setdefault(rol, []).append(n)
    return {rol: sorted(ns) for rol, ns in fuera.items()}
def estilo_arial(estilo):
    """El corte de Arial que mejor imita un estilo pedido: \'Bold\',\n    \'Italic\', \'Bold Italic\' o \'Regular\' (los cuatro vienen con Windows y\n    con macOS, con esos nombres exactos)."""
    n = (estilo or '').lower()
    negrita = any((p in n for p in ['bold', 'black', 'heavy', 'ultra', 'extra', 'semi', '95', '85', '75']))
    cursiva = any((p in n for p in ('italic', 'oblique')))
    if negrita and cursiva:
        return 'Bold Italic'
    else:
        if negrita:
            return 'Bold'
        else:
            if cursiva:
                return 'Italic'
            else:
                return 'Regular'
def _fuentes_respaldo(info):
    """{\"rol|n\": [\"Arial\", estilo]} para los clips cuya tipografia NO esta\n    en el equipo (v2.0.2, pedido literal: «en el caso de no tener la\n    tipografia se use Arial en el grosor o inclinacion de la que falta,\n    ya que viene en el sistema de toda maquina»).\n\n    Se pregunta por la FAMILIA en el sistema (esta_en_el_sistema, el\n    mismo criterio del aviso de la tarjeta): una familia presente con\n    otro peso NO se sustituye — Fusion ya cae dentro de la familia y asi\n    no se pisa una fuente variable que si dibuja ese peso. Los gemelos\n    corren dentro de Resolve sin ver fonts/ ni el registro de fuentes:\n    solo aca se puede medir. Vacio = nada que sustituir.\n    """
    import fuentes_sistema
    tip = (info or {}).get('tipografias') or {}
    fuera = {}
    for clave, fuente in tip.items():
        try:
            familia, estilo = fuente
        except (TypeError, ValueError):
            pass
        else:
            if not familia or fuentes_sistema.esta_en_el_sistema(familia, estilo):
                continue
            else:
                fuera[clave] = ['Arial', estilo_arial(estilo)]
    return fuera
def transformaciones_de_drb(ruta_drb):
    """La posicion y el zoom de pagina Edicion de cada clip de un .drb.\n\n    {\'context|3\': [x, y, zoom_x, zoom_y], \'base|0\': [...],\n     \'basico|inferior|1\': [...]} — mismas claves que los gemelos arman con\n    el rol y el numero de set del clip. X/Y van normalizados (fraccion del\n    ancho/alto del timeline; Y positiva = arriba).\n\n    v3.3.0, reporte: 4 de 550 clientes veian las tres lineas ENCIMADAS en el\n    centro. La posicion del diseño no vive en el comp del clip (Text+ sin\n    Center, PolyPath en reposo en 0): vive en el project.xml del .drb, un\n    blob por clip, y la mayoria de los Resolve la aplican solos al colocar\n    — el de esos clientes no. Como el blob va en zstd y el CI compila con\n    Python 3.12, herramientas/posiciones_drb.py lo decodifica UNA vez y deja\n    \'<nombre>.posiciones.json\' junto al .drb; aqui solo se lee. Sin ese\n    archivo (los .drb que importa el usuario) devuelve {}: todo como antes.\n    """
    if not ruta_drb:
        return {}
    else:
        ruta = Path(ruta_drb)
        fuente = ruta.with_name(ruta.stem + '.posiciones.json')
        try:
            clips = json.loads(fuente.read_text(encoding='utf-8')).get('clips')
        except (OSError, ValueError, AttributeError):
            # v5.3: sin .posiciones.json (un .drb que crea el usuario) se leen del propio .drb:
            # asi el bloque 'imagen' de SU pack tambien dice donde va el icono.
            try:
                clips = packs_drt.posiciones_de_drb(ruta)
            except Exception:
                clips = None
            if not clips:
                return {}
        fuera = {}
        for nombre, t in (clips or {}).items():
            if not (isinstance(t, list) and len(t) == 4):
                continue
            else:
                try:
                    valores = [float(v) for v in t]
                except (TypeError, ValueError):
                    pass
                else:
                    rol, n = packs_drt.parsear_nombre(nombre)
                    if rol is not None and n >= 0:
                            fuera[f'{rol}|{n}'] = valores
                            continue
                    basico = packs_drt.parsear_nombre_basico(nombre)
                    if basico:
                        fuera['|'.join((basico[0], basico[1], str(basico[2])))] = valores
        return fuera
def para_manifiesto(nombre, formato_forzado=None):
    """El campo \'plantilla\' del manifiesto para ese pack, o {}.\n\n    Viajan LOS DOS formatos y normalmente elige el script de Resolve, porque\n    la app no conoce la resolucion del timeline. Eligiendo aqui a ciegas, un\n    pack completo se aplicaria en horizontal sobre un video vertical sin que\n    nadie lo notara.\n\n    \'formato_forzado\' (\"h\", \"v\" o \"c\") es la excepcion: la eleccion EXPLICITA\n    del usuario, que manda sobre la deteccion automatica. Hace falta porque\n    adivinar por la resolucion no siempre acierta — un timeline cuadrado\n    (1080x1080) no es ni una cosa ni la otra, y hay quien monta en horizontal\n    para recortar a vertical despues. Con None se detecta como siempre.\n\n    \'auto\' YA NO ES VACIO. Desde la v1.0.28 \"Diseño automático\" significa \"el\n    pack incorporado, en el formato de este timeline\", no un calculo propio\n    del script. El motivo es el reporte de que el automatico amontonaba el\n    texto y no respetaba el formato: el producto trae timelines hechos a\n    mano (horizontal y vertical; el cuadrado se retiro en la v1.0.55 a\n    pedido del usuario — un timeline cuadrado cae al formato mas parecido,\n    con aviso) justamente para no tener que inventar una disposicion. El\n    pack decide posicion, tamaño,\n    tipografia, color y modo de fusion; el script solo escribe el texto.\n    Si el pack incorporado no esta, se devuelve {} y el script cae a su\n    diseño de respaldo — diciendolo.\n\n    Vive en este modulo y no en la ventana para poder probarlo sin abrir Tk:\n    es la pieza que conecta el pack del disco con los scripts de Resolve, y si\n    se rompe no se nota hasta ver el render.\n    """
    if nombre in ['media_pool', '', None]:
        return {}
    else:
        if formato_forzado not in FORMATOS:
            formato_forzado = None
        if nombre == 'auto':
            pack = pack_incorporado()
        else:
            pack = buscar_pack(nombre)
        if pack is None:
            return {}
        elif getattr(pack, 'mezcla', False):
            return {'plantilla': {'pack': pack.nombre, 'mezcla': True, 'formatos': {}}}      # v5.4.30: el generador arma las pistas con el pack de CADA tema (Kinetic, Referencia, VIRAL)
        else:
            if pack.es_basicos:
                return {}
            else:
                def con_color(e):
                    return dict(e, color=list(e.get('color', (1.0, 1.0, 1.0))))
                formatos = {}
                for formato in pack.formatos:
                    sets = []
                    for n in pack.numeros_de_set(formato):
                        estilos = pack.estilos_de(n, formato)
                        if not estilos:
                            continue
                        else:
                            entrada = {'n': n}
                            for rol, e in estilos.items():
                                entrada[rol] = con_color(e)
                            sets.append(entrada)
                    base = pack.estilos_de('base', formato)
                    drt = pack.ruta_drt(formato)
                    drb_solo = pack.ruta_drb(formato) if not drt else None
                    if not sets and (not base) and (not drt) and (not drb_solo):
                                    continue
                    bloque = {'carpeta': str(pack.carpeta / formato), 'sets': sets}
                    if pack.incorporado:
                        cache = materializar_incorporado(pack)
                        if cache is not None and (cache / formato).is_dir():
                                bloque['carpeta'] = str(cache / formato)
                                bloque['settings_sin_posicion'] = True
                    if base:
                        bloque['base'] = con_color(base)
                    transformaciones = transformaciones_de_drb(pack.ruta_drb(formato))
                    if transformaciones:
                        bloque['transformaciones'] = transformaciones
                    if drt:
                        bloque['drt'] = str(drt)
                        drb = pack.ruta_drb(formato)
                        if drb:
                            bloque['drb'] = str(drb)
                        info = pack.info_drt(formato)
                        if info and info.get('ok'):
                                bloque['sets_drt'] = list(info['completos'])
                                bloque['base_drt'] = bool(info['base'])
                        info_veto = pack.info_drb(formato) if drb else None
                        if not info_veto or not info_veto.get('tipografias'):
                            info_veto = info
                        vetados = _sets_sin_acentos(info_veto)
                        if vetados:
                            bloque['sets_sin_acentos'] = vetados
                        respaldo = _fuentes_respaldo(info_veto)
                        if respaldo:
                            bloque['fuentes_respaldo'] = respaldo
                    else:
                        if drb_solo:
                            bloque['drb'] = str(drb_solo)
                            info = pack.info_drb(formato)
                            if info and info.get('ok'):
                                    bloque['sets_drt'] = list(info['completos'])
                                    bloque['base_drt'] = bool(info['base'])
                                    vetados = _sets_sin_acentos(info)
                                    if vetados:
                                        bloque['sets_sin_acentos'] = vetados
                                    respaldo = _fuentes_respaldo(info)
                                    if respaldo:
                                        bloque['fuentes_respaldo'] = respaldo
                    try:
                        con_imagen = ((pack.info_drb(formato) or {}).get('imagenes')
                                      or (pack.info_drt(formato) or {}).get('imagenes'))
                    except Exception:
                        con_imagen = None
                    if con_imagen:
                        bloque['sets_imagen'] = list(con_imagen)
                    formatos[formato] = bloque
                if not formatos:
                    return {}
                else:
                    plantilla = {'pack': pack.nombre, 'formatos': formatos}
                    if pack.incorporado and pack.nombre in REVISION_BIN:
                        plantilla['revision'] = REVISION_BIN[pack.nombre]
                    if formato_forzado:
                        plantilla['formato_forzado'] = formato_forzado
                    return {'plantilla': plantilla}
_MEMO_IMAGEN = {}
# v5.4.37: packs sin bloque «imagen» cuyo emoji va ENCIMA del texto (el resto: debajo). v5.5.7 (pedido del usuario): también el Tema 2 (Referencia)
# y el 3 (VIRAL): todos los temas con emoji lo llevan arriba, pegado a la pila
EMOJI_ARRIBA = ('Referencia', 'VIRAL', 'Tema4', 'Tema5', 'Tema6')


def bloque_imagen(nombre, formato=None):
    """Donde cae el bloque «imagen» del pack elegido: {'donde': 'abajo'|'arriba', 'zoom': float, 'bloque': bool}.

    'bloque' dice si el pack lo trae. Sin el (o sin pack) el emoji va DEBAJO del texto, a su tamaño normal. Es lo que
    dibujan las vistas previas (Creativo, Proyecto, Composicion) para que se vea donde caera el icono. Nunca lanza.
    """
    por_defecto = {'donde': 'arriba' if nombre in EMOJI_ARRIBA else 'abajo', 'zoom': 1.0, 'bloque': False}
    try:
        if nombre in ('media_pool', '', None, 'dinamico'):
            return dict(por_defecto)
        clave = (nombre, formato)
        if clave in _MEMO_IMAGEN:
            return dict(_MEMO_IMAGEN[clave])
        pack = pack_incorporado() if nombre == 'auto' else buscar_pack(nombre)
        if pack is None or pack.es_basicos or not pack.formatos:
            return dict(por_defecto)
        f = formato if formato in pack.formatos else pack.formatos[0]
        t = transformaciones_de_drb(pack.ruta_drb(f))
        img = t.get('image|1') or next((v for k, v in sorted(t.items()) if k.startswith('image|')), None)
        if not img:
            _MEMO_IMAGEN[clave] = dict(por_defecto)
            return dict(por_defecto)
        principal = t.get('main|1')
        y_main = principal[1] if principal else 0.0
        fuera = {'donde': 'arriba' if img[1] > y_main else 'abajo', 'zoom': float(img[2] or 1.0), 'bloque': True}
        _MEMO_IMAGEN[clave] = fuera
        return dict(fuera)
    except Exception:
        return dict(por_defecto)
def roles_de_variante(nombre, formato, n):
    """{'context': {'f1','f2','tam','color','mayus'}, ...} de la variante n si el pack la trae en su .variantes.json (los
    packs nuevos: dos palabras por linea con dos pesos); {} si no. Nunca lanza."""
    try:
        if nombre in ('media_pool', '', None, 'dinamico') or not n:
            return {}
        pack = pack_incorporado() if nombre == 'auto' else buscar_pack(nombre)
        if pack is None or not pack.formatos:
            return {}
        f = formato if formato in pack.formatos else pack.formatos[0]
        drb = pack.ruta_drb(f)
        if not drb:
            return {}
        datos = json.loads(Path(drb).with_name(Path(drb).stem + '.variantes.json').read_text(encoding='utf-8'))
        return (datos.get(str(n)) or {}).get('roles') or {}
    except Exception:
        return {}
def variantes_de(nombre, formato=None):
    """[{'n', 'nombre', 'color', 'donde', 'zoom'}] de las variantes completas de un pack (para las vistas previas):
    'donde' = 'arriba'|'abajo' segun el bloque «imagen» de esa variante (None si no lo trae). El nombre y el color de
    cada variante viajan en <pack>.variantes.json junto al .drb (solo los packs nuevos). Nunca lanza."""
    try:
        if nombre in ('media_pool', '', None, 'dinamico'):
            return []
        pack = pack_incorporado() if nombre == 'auto' else buscar_pack(nombre)
        if pack is None or pack.es_basicos or not pack.formatos:
            return []
        f = formato if formato in pack.formatos else pack.formatos[0]
        drb = pack.ruta_drb(f)
        t = transformaciones_de_drb(drb) if drb else {}
        extra = {}
        if drb:
            try:
                extra = json.loads(Path(drb).with_name(Path(drb).stem + '.variantes.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                extra = {}
        salida = []
        for n in pack.numeros_de_set(f):
            img = t.get(f'image|{n}') or t.get('image|1')
            principal = t.get(f'main|{n}')
            donde = None
            if img:
                donde = 'arriba' if img[1] > (principal[1] if principal else 0.0) else 'abajo'
            e = extra.get(str(n)) or {}
            ys = None
            if principal:                # (arriba, principal, abajo) en fracción del alto del cuadro, 0 = abajo del todo; aproximado (el Tilt del clip)
                ctx, cmp_ = t.get(f'context|{n}'), t.get(f'complement|{n}')
                ys = (0.5 + (ctx[1] if ctx else principal[1] + 0.08), 0.5 + principal[1], 0.5 + (cmp_[1] if cmp_ else principal[1] - 0.08))
            salida.append({'n': n, 'nombre': str(e.get('nombre') or ''), 'color': e.get('color'), 'donde': donde,
                           'zoom': float(img[2] or 1.0) if img else 1.0, 'y': ys})
        return salida
    except Exception:
        return []
def sirve_en_go(pack, formato=None):
    """¿Se puede elegir este pack para GO / Generar? Un pack de sets (arriba/principal/abajo) sí si trae sets; el estilo «Kinetic» (sus clips son elementos) si trae el formato."""
    if pack is None:
        return False
    if getattr(pack, 'mezcla', False):
        return (formato or 'v') in ('v',) and bool(pack.looks)
    if getattr(pack, 'kinetic', False):
        return (formato or 'v') in pack.formatos
    return bool(pack.numeros_de_set(formato)) if formato else bool(pack.numeros_de_set('h') or pack.numeros_de_set('v'))
def estructura_de(pack):
    """Que bloques trae un pack, para el mosaico: {'arriba','principal','abajo','imagen','simple': bool, 'variantes': n}."""
    try:
        if getattr(pack, 'mezcla', False):
            return {'arriba': False, 'principal': False, 'abajo': False, 'imagen': False, 'simple': False, 'variantes': len(pack.looks), 'nuevo': False, 'kinetic': False, 'viral': False, 'mezcla': True}
        if getattr(pack, 'kinetic', False):
            return {'arriba': False, 'principal': False, 'abajo': False, 'imagen': False, 'simple': False, 'variantes': 0, 'nuevo': False, 'kinetic': True, 'viral': bool(getattr(pack, 'viral', False))}
        f = pack.formatos[0] if pack.formatos else None
        info = (pack.info_drb(f) if f else None) or (pack.info_drt(f) if f else None) or {}
        completos = list(info.get('completos') or [])
        return {'arriba': bool(completos), 'principal': bool(completos), 'abajo': bool(completos),
                'imagen': bool(info.get('imagenes')), 'simple': bool(info.get('base')), 'variantes': len(completos),
                'nuevo': bool(info.get('nuevo'))}
    except Exception:
        return None
def basicos_para_manifiesto(combinacion, formato_forzado=None, pack_nombre=None):
    """{\'plantilla_basicos\': {...}} para el track SRT, o {} si no aplica.\n\n    v1.0.69 (pedido literal 12-09: elegir 1 de las 6 combinaciones del\n    pack de basicos; «basico» viste el subtitulo normal y su pareja\n    «traducion» la pista traducida). \'combinacion\' = \"inferior 2\"\n    (posicion + numero). Viajan LOS DOS formatos y el gemelo elige por\n    resolucion — misma regla que para_manifiesto: la app no conoce el\n    timeline. Vive aqui y no en la ventana por el mismo motivo que\n    para_manifiesto: probarlo sin abrir Tk.\n\n    v1.0.70 (pedido literal: «que exista la posibilidad de añadir\n    plantillas drb su basico + su traducion»): \'pack_nombre\' elige el\n    pack de basicos — None cae al incorporado (compat con la firma\n    v1.0.69). Los gemelos ya leian el nombre del bloque, cero cambios\n    alla.\n    """
    pos, _, n = (combinacion or '').strip().partition(' ')
    if pos not in POSICIONES_BASICOS or not n.isdigit():
        return {}
    else:
        if formato_forzado not in FORMATOS:
            formato_forzado = None
        pack = buscar_pack(pack_nombre or NOMBRE_BASICOS)
        if pack is None or not pack.es_basicos:
            return {}
        else:
            formatos = {}
            for formato in pack.formatos:
                drb = pack.ruta_drb(formato)
                info = pack.info_drb(formato)
                disponibles = (info or {}).get('basicos') or {}
                if drb and int(n) in disponibles.get(pos, ()):
                        formatos[formato] = {'drb': str(drb)}
                        transformaciones = transformaciones_de_drb(drb)
                        if transformaciones:
                            formatos[formato]['transformaciones'] = transformaciones
            if not formatos:
                return {}
            else:
                bloque = {'pack': pack.nombre, 'pos': pos, 'n': int(n), 'formatos': formatos}
                if formato_forzado:
                    bloque['formato_forzado'] = formato_forzado
                return {'plantilla_basicos': bloque}
def borrar_pack(nombre):
    """Quita un pack del disco. Solo toca la carpeta de ese pack.\n\n    El pack incorporado no se puede borrar: vive dentro del programa, donde\n    los archivos son de solo lectura, y volveria en la siguiente\n    actualizacion. Se devuelve False en vez de intentarlo y reventar.\n    """
    carpeta = carpeta_de_packs() / nombre_seguro(nombre)
    if not carpeta.is_dir():
        return False
    else:
        shutil.rmtree(carpeta)
        return True
def preparar_miniaturas(carpeta_bruta, carpeta_pack, mapa):
    """Convierte lo que suelta Resolve en las miniaturas del pack.\n\n    \'mapa\' es {prefijo o nombre de archivo: numero de set (o \"base\")}.\n\n    Tres cosas que hay que hacer aqui y que se ven en los archivos que dejo la\n    prueba del Paso 0:\n\n      - el PNG sale a resolucion completa y pesa 6,2 MB;\n      - ExportStills nombra por TIMECODE (\'cinecaptions_prueba_5.3.1.png\'), no en\n        orden, asi que no se puede confiar en el orden alfabetico. Por eso el\n        script de importacion exporta cada set con su PROPIO prefijo y aqui\n        se busca por prefijo, no por nombre exacto;\n      - deja un .drx al lado de cada png, que no sirve para nada aqui.\n\n    Devuelve (cuantas salieron, [avisos]).\n    """
    carpeta_bruta = Path(carpeta_bruta)
    destino = Path(carpeta_pack) / 'miniaturas'
    destino.mkdir(parents=True, exist_ok=True)
    avisos = []
    try:
        from PIL import Image
    except ImportError:
        avisos.append('no encontre Pillow, dejo las miniaturas sin reescalar')
        Image = None
    hechas = 0
    for clave, n in (mapa or {}).items():
        origen = carpeta_bruta / clave
        if not origen.is_file():
            candidatos = sorted(carpeta_bruta.glob(f'{clave}*.png'))
            origen = candidatos[0] if candidatos else None
        if origen is None or not origen.is_file():
            avisos.append(f'Resolve no dejo la miniatura del set {n}')
            continue
        else:
            salida = destino / nombre_miniatura(n)
            if Image is None:
                shutil.copyfile(origen, salida)
                hechas += 1
                continue
            else:
                try:
                    with Image.open(origen) as img:
                        img = img.convert('RGB')
                        img.thumbnail(MINIATURA, Image.LANCZOS)
                        lienzo = Image.new('RGB', MINIATURA, (18, 18, 18))
                        lienzo.paste(img, ((MINIATURA[0] - img.width) // 2, (MINIATURA[1] - img.height) // 2))
                        lienzo.save(salida, 'PNG', optimize=True)
                    hechas += 1
                except Exception as exc:
                    avisos.append(f'no pude reescalar la miniatura del set {n}: {exc}')
    for sobrante in list(carpeta_bruta.glob('*.drx')) + list(carpeta_bruta.glob('*.png')):
        try:
            sobrante.unlink()
        except OSError:
            pass
    return (hechas, avisos)
RUTA_IMPORTACION = CARPETA_USUARIO / 'importar_estilos.json'
def leer_importacion(ruta=None):
    """Lo que dejo el script de Resolve. Devuelve (datos, error)."""
    ruta = Path(ruta or RUTA_IMPORTACION)
    if not ruta.is_file():
        return (None, f'El script de Resolve no dejó nada en {ruta}. ¿Llegó a correr?')
    else:
        try:
            datos = json.loads(ruta.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            return (None, f'No pude leer {ruta}: {exc}')
        if not isinstance(datos, dict) or not datos.get('ok'):
            return (None, 'El script de Resolve terminó sin extraer nada.')
        else:
            if not datos.get('entradas'):
                return (None, 'El script no encontró ningún Text+ con los nombres del pack en ese timeline.')
            else:
                return (datos, None)
def importar_desde(datos, nombre_pack):
    """Convierte lo extraido por el script de Resolve en un pack instalado.\n\n    Devuelve (pack, avisos). Los avisos vienen del script MAS los de aqui, y\n    hay que enseñarlos: un pack al que le falta la mitad no puede parecer\n    completo.\n    """
    avisos = list(datos.get('avisos') or [])
    formato = datos.get('formato') if datos.get('formato') in FORMATOS else 'h'
    bruta = Path(datos.get('carpeta') or '')
    sets, base = ({}, None)
    for e in datos.get('entradas') or []:
        rol = e.get('rol')
        estilo = normalizar_estilo(e.get('estilo'))
        if rol == 'base':
            base = estilo
            continue
        else:
            if rol not in ROLES:
                continue
        try:
            n = int(e.get('n'))
        except (TypeError, ValueError):
            pass
        else:
            if 1 <= n <= MAX_SETS:
                    sets.setdefault(n, {})[rol] = estilo
    if not sets and base is None:
        return (None, avisos + ['No había ningún estilo utilizable.'])
    else:
        carpeta = guardar_formato(nombre_pack, formato, sets, base=base, resolucion=datos.get('resolucion'))
        destino_set = carpeta / formato
        destino_set.mkdir(parents=True, exist_ok=True)
        copiados, sin_setting = (0, 0)
        for e in datos.get('entradas') or []:
            nombre = e.get('setting')
            if not nombre:
                sin_setting += 1
                continue
            else:
                origen = bruta / nombre
                if not origen.is_file():
                    sin_setting += 1
                    continue
                else:
                    try:
                        shutil.copyfile(origen, destino_set / nombre)
                        copiados += 1
                    except OSError as exc:
                        avisos.append(f'no pude copiar {nombre}: {exc}')
        if sin_setting:
            avisos.append(f'{sin_setting} estilos entran solo con sus valores (fuente, tamaño, color): de esos no se guardó el nodo entero, así que degradados y fondos no viajan.')
        mapa = {}
        for m in datos.get('miniaturas') or []:
            clave = m.get('clave')
            prefijo = m.get('prefijo')
            if not prefijo:
                continue
            else:
                try:
                    mapa[prefijo] = 'base' if clave == 'base' else int(clave)
                except (TypeError, ValueError):
                    pass
        if mapa:
            _, mas = preparar_miniaturas(bruta / 'miniaturas', carpeta, mapa)
            avisos.extend(mas)
        if bruta.name == 'importar_estilos_tmp' and bruta.is_dir():
                shutil.rmtree(bruta, ignore_errors=True)
        pack = cargar(carpeta)
        if pack is None:
            return (None, avisos + ['Guardé el pack pero no puedo volver a leerlo.'])
        else:
            return (pack, avisos)
PRESETS_DINAMICOS = {
    'clasico': {
        'nombre': 'Clásico',
        'estilos': {
            'context': {
                'font': 'Montserrat',
                'style': 'Regular',
                'size': 0.038,
                'tracking': 1.0,
                'color': [1.0, 1.0, 1.0],
            },
            'main': {
                'font': 'Montserrat',
                'style': 'Bold',
                'size': 0.082,
                'tracking': 0.97,
                'color': [1.0, 1.0, 1.0],
            },
            'complement': {
                'font': 'Montserrat',
                'style': 'Italic',
                'size': 0.05,
                'tracking': 1.0,
                'color': [0.88, 0.88, 0.88],
            },
        },
        'ancla_y': 0.196,
        'factor_separacion': 0.54,
    },
    'hormozi': {
        'nombre': 'Hormozi',
        'motor': 'pintado',
        'pintado': {'filas_max': 1, 'modo': 'acumula'},
        'estilos': {
            'context': {
                'font': 'Montserrat',
                'style': 'Bold',
                'size': 0.04,
                'tracking': 1.0,
                'color': [1.0, 1.0, 1.0],
                'outline': {'thickness': 0.12, 'color': [0.0, 0.0, 0.0]},
            },
            'main': {
                'font': 'Montserrat',
                'style': 'ExtraBold',
                'size': 0.095,
                'tracking': 0.97,
                'color': [1.0, 0.85, 0.08],
                'outline': {'thickness': 0.24, 'color': [0.0, 0.0, 0.0]},
            },
            'complement': {
                'font': 'Montserrat',
                'style': 'Bold',
                'size': 0.048,
                'tracking': 1.0,
                'color': [1.0, 1.0, 1.0],
                'outline': {'thickness': 0.12, 'color': [0.0, 0.0, 0.0]},
            },
        },
        'ancla_y': 0.196,
        'factor_separacion': 0.54,
    },
    'gadzhi': {
        'nombre': 'Gadzhi',
        'motor': 'pintado',
        'pintado': {'filas_max': 2, 'modo': 'viaja'},
        'estilos': {
            'context': {
                'font': 'Montserrat',
                'style': 'SemiBold',
                'size': 0.038,
                'tracking': 1.0,
                'color': [1.0, 1.0, 1.0],
            },
            'main': {
                'font': 'Montserrat',
                'style': 'Bold',
                'size': 0.1,
                'tracking': 0.97,
                'color': [1.0, 0.85, 0.08],
            },
            'complement': {
                'font': 'Montserrat',
                'style': 'SemiBold',
                'size': 0.048,
                'tracking': 1.0,
                'color': [1.0, 1.0, 1.0],
            },
            'base': {
                'font': 'Montserrat',
                'style': 'SemiBold',
                'size': 0.055,
                'tracking': 1.0,
                'color': [1.0, 1.0, 1.0],
            },
        },
        'ancla_y': 0.196,
        'factor_separacion': 0.54,
    },
    'minimal': {
        'nombre': 'Minimal',
        'estilos': {
            'context': {
                'font': 'Montserrat',
                'style': 'Light',
                'size': 0.034,
                'tracking': 1.1,
                'color': [1.0, 1.0, 1.0],
            },
            'main': {
                'font': 'Montserrat',
                'style': 'Regular',
                'size': 0.075,
                'tracking': 1.05,
                'color': [1.0, 1.0, 1.0],
            },
            'complement': {
                'font': 'Montserrat',
                'style': 'Light',
                'size': 0.046,
                'tracking': 1.1,
                'color': [0.9, 0.9, 0.9],
            },
        },
        'ancla_y': 0.196,
        'factor_separacion': 0.54,
    },
    'contraste': {
        'nombre': 'Contraste',
        'estilos': {
            'context': {
                'font': 'Montserrat',
                'style': 'Bold',
                'size': 0.036,
                'tracking': 1.0,
                'color': [1.0, 0.85, 0.08],
            },
            'main': {
                'font': 'Montserrat',
                'style': 'Black',
                'size': 0.11,
                'tracking': 0.95,
                'color': [1.0, 1.0, 1.0],
                'outline': {'thickness': 0.3, 'color': [0.0, 0.0, 0.0]},
            },
            'complement': {
                'font': 'Montserrat',
                'style': 'Bold',
                'size': 0.048,
                'tracking': 1.0,
                'color': [1.0, 1.0, 1.0],
            },
        },
        'ancla_y': 0.196,
        'factor_separacion': 0.54,
    },
    'suave': {
        'nombre': 'Suave',
        'estilos': {
            'context': {
                'font': 'Montserrat',
                'style': 'Regular',
                'size': 0.038,
                'tracking': 1.05,
                'color': [0.95, 0.85, 0.8],
            },
            'main': {
                'font': 'Montserrat',
                'style': 'Bold',
                'size': 0.085,
                'tracking': 1.0,
                'color': [1.0, 0.9, 0.75],
            },
            'complement': {
                'font': 'Montserrat',
                'style': 'Italic',
                'size': 0.05,
                'tracking': 1.05,
                'color': [0.9, 0.8, 0.75],
            },
        },
        'ancla_y': 0.22,
        'factor_separacion': 0.54,
    },
}
def diseno_para_manifiesto(pref):
    """El bloque {\'diseno\': ...} del track para el modo Diseño dinámico.\n\n    \'pref\' es lo guardado en preferencias: {preset, estilos{rol: overrides},\n    ancla_y, factor_separacion}. Se resuelve AQUI (preset + overrides ya\n    mezclados) para que los gemelos reciban valores finales: un solo\n    resolvedor, no dos que se separen — la misma regla que\n    para_manifiesto() con los packs.\n    """
    import copy
    pref = dict(pref or {})
    nombre = pref.get('preset') or 'clasico'
    base = PRESETS_DINAMICOS.get(nombre) or PRESETS_DINAMICOS['clasico']
    estilos = copy.deepcopy(base['estilos'])
    over = pref.get('estilos') or {}
    for rol in ['context', 'main', 'complement', 'base']:
        cambios = over.get(rol)
        if isinstance(cambios, dict) and rol in estilos:
                estilos[rol].update(copy.deepcopy(cambios))
    def _num(valor, respaldo):
        try:
            return float(valor)
        except (TypeError, ValueError):
            return respaldo
    diseno = {'preset': nombre, 'estilos': estilos, 'ancla_y': _num(pref.get('ancla_y'), base.get('ancla_y', 0.196)), 'factor_separacion': _num(pref.get('factor_separacion'), base.get('factor_separacion', 0.54)), 'entrada': pref.get('entrada') if pref.get('entrada') in ['fundido', 'ninguna'] else base.get('entrada', 'fundido')}
    if base.get('motor'):
        diseno['motor'] = base['motor']
    if isinstance(base.get('pintado'), dict):
        diseno['pintado'] = dict(base['pintado'])
    return {'diseno': diseno}
TOPE_SIZE_PINTADO = {'v': 0.052, 'c': 0.062, 'h': 0.085}
LINE_SPACING_PINTADO = 1.12
def pintado_para_manifiesto(diseno, formato='h'):
    """La configuracion COMPLETA del pintado v2 para el manifiesto.\n\n    Todo resuelto en la app (un solo resolvedor, la regla de siempre):\n    - \'modo\': \"acumula\" (Hormozi: lo dicho queda pintado) o \"viaja\"\n      (Gadzhi: solo la palabra actual va en bold).\n    - \'estilo_base\': el bloque multilinea de fondo. En \'viaja\' es TEXTO\n      VISIBLE en peso Regular (los subs de Gadzhi se leen enteros); en\n      \'acumula\' es la copia tenue gris que se lee adelantado.\n    - \'estilo_dicha\': lo que se pinta encima (mismo peso blanco en\n      Hormozi; Bold en Gadzhi).\n    - \'estilo_clave\': la palabra marcada (el color editable de \'main\', con\n      su contorno si lo trae).\n    El tamaño sale de \'main\' CAPADO por formato (TOPE_SIZE_PINTADO): las\n    filas se arman por caracteres y un cuerpo mas grande no cabria. La\n    MEDICION debe hacerse con estilo_base (mismo font/peso/size/tracking):\n    en \'viaja\' el bold se dibuja sobre posiciones medidas en Regular a\n    proposito — cae en el borde izquierdo de su gemela y sobresale apenas.\n    """
    d = diseno or {}
    est = d.get('estilos') or {}
    main = est.get('main') or {}
    ctx = est.get('context') or {}
    cfgp = d.get('pintado') or {}
    modo = cfgp.get('modo') if cfgp.get('modo') in ['acumula', 'viaja'] else 'acumula'
    filas_max = max(1, int(cfgp.get('filas_max') or 3))
    tope = TOPE_SIZE_PINTADO.get(formato, TOPE_SIZE_PINTADO['h'])
    size = float(main.get('size') or 0.07)
    size_capado = size > tope
    if size_capado:
        size = tope
    font = main.get('font', 'Montserrat')
    tracking = float(main.get('tracking', 1.0) or 1.0)
    color_clave = list(main.get('color') or [1.0, 0.85, 0.08])[:3]
    color_dicha = list(ctx.get('color') or [1.0, 1.0, 1.0])[:3]
    def _e(peso, color):
        return {'font': font, 'style': peso, 'size': size, 'tracking': tracking, 'color': list(color), 'line_spacing': LINE_SPACING_PINTADO}
    if modo == 'viaja':
        estilo_base = _e('Regular', color_dicha)
        estilo_dicha = _e('Bold', color_dicha)
        estilo_clave = _e('Bold', color_clave)
    else:
        peso = main.get('style', 'Bold')
        estilo_base = _e(peso, [0.5, 0.5, 0.5])
        estilo_dicha = _e(peso, color_dicha)
        estilo_clave = _e(peso, color_clave)
        if isinstance(main.get('outline'), dict):
            estilo_clave['outline'] = dict(main['outline'])
    return {'modo': modo, 'filas_max': filas_max, 'line_spacing': LINE_SPACING_PINTADO, 'size_capado': size_capado, 'estilo_base': estilo_base, 'estilo_dicha': estilo_dicha, 'estilo_clave': estilo_clave}
def destacados_para_manifiesto(diseno):
    """Los estilos {normal, resaltada} para un look de grupos/acumulativo\n    armado desde el Diseño dinámico (hoy: la degradacion del pintado cuando\n    no se puede medir). \'resaltada\' es el \'main\' del preset tal cual;\n    \'normal\' es el mismo estilo con el color del contexto (blanco), para\n    que la degradacion conserve el look elegido en vez de caer a las\n    constantes de fabrica de los gemelos.\n    """
    est = (diseno or {}).get('estilos') or {}
    main = dict(est.get('main') or {})
    if not main:
        return
    else:
        ctx = est.get('context') or {}
        normal = dict(main)
        normal['color'] = list(ctx.get('color') or [1.0, 1.0, 1.0])[:3]
        resaltada = dict(main)
        resaltada['color'] = list(main.get('color') or [1.0, 0.85, 0.08])[:3]
        return {'normal': normal, 'resaltada': resaltada}
