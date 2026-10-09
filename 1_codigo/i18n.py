# CineCaptions · By Cinema Productions
# 1_codigo/i18n.py — idiomas de la interfaz: tr("texto en español") y los catálogos de 2_recursos/locales.
"""
i18n.py  (v3.3.0)
-----------------
La interfaz en 6 idiomas. Pedido del usuario (21-09): «quiero comercializarlo
en otros idiomas... que se pueda elegir el idioma al momento de instalar:
español, inglés, portugués...»; eligio es/en/pt/fr/de/it.

  - tr(texto_en_español, **valores): el ESPAÑOL es la clave (al estilo
    gettext). Asi el codigo se sigue leyendo en español, las baterias que
    buscan textos en español siguen valiendo, y un texto sin traduccion
    sale en español en vez de romper algo. Se llama tr y NO «_»: «_» ya es
    variable local en varias funciones (palabras, _ = ...), y un «_(...)»
    ahi reventaria en ejecucion (la clase de fallo del «dyn» de la v1.0.71).
  - tr NUNCA lanza: una traduccion con un marcador mal escrito cae al
    español ya formateado.
  - El idioma se decide al IMPORTAR (los textos de modulo, como los
    MENSAJE_* de resolve_bridge, se evaluan ahi):
        desde el codigo fuente (pruebas): CINECAPTIONS_IDIOMA o «es» — jamas el del
          sistema ni el .ini, para que las baterias sean deterministas;
        compilado: ~/DaVinciSubtitles/idioma.ini (lo escribe el instalador
          de Windows y el selector de la app) > si ya hay preferencias.json
          (un cliente que actualiza) «es», y se deja escrito > el idioma
          del sistema > «es».
  - Lo que imprimen los scripts DENTRO de Resolve sigue en español: es para
    soporte y trae los centinelas que la app busca (paso_manual_pendiente).
"""

import configparser
import json
import os
import subprocess
import sys
from pathlib import Path

IDIOMAS_UI = {
    'es': 'Español',
    'en': 'English',
    'pt': 'Português',
    'fr': 'Français',
    'de': 'Deutsch',
    'it': 'Italiano',
}

POR_DEFECTO = 'es'

CARPETA = Path.home() / 'DaVinciSubtitles'
ARCHIVO_INI = CARPETA / 'idioma.ini'


def _base_recursos():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / '2_recursos'


def _normalizar(codigo):
    c = str(codigo or '').strip().lower().replace('_', '-')
    c = c.split('-')[0]
    return c if c in IDIOMAS_UI else None


def leer_ini(ruta=None):
    ruta = Path(ruta or ARCHIVO_INI)
    try:
        cp = configparser.ConfigParser(strict=False)
        cp.read(ruta, encoding='utf-8')
        return _normalizar(cp.get('ui', 'idioma', fallback=''))
    except (configparser.Error, OSError, UnicodeDecodeError):
        return None


def guardar_idioma(codigo, ruta=None):
    """Lo que elige el selector de la app (el instalador escribe el mismo
    archivo). Devuelve True si quedo escrito."""
    codigo = _normalizar(codigo)
    if codigo is None:
        return False
    ruta = Path(ruta or ARCHIVO_INI)
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(f'[ui]\nidioma={codigo}\n', encoding='utf-8')
        return True
    except OSError:
        return False


def idioma_del_sistema():
    """El idioma de la interfaz del sistema, o None."""
    try:
        if sys.platform.startswith('win'):
            import ctypes
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            primario = langid & 1023
            return {
                10: 'es', 9: 'en', 22: 'pt', 12: 'fr', 7: 'de', 16: 'it',
            }.get(primario)
        if sys.platform == 'darwin':
            salida = subprocess.run(
                ['defaults', 'read', '-g', 'AppleLanguages'],
                capture_output=True, text=True, timeout=3,
            ).stdout
            for trozo in salida.replace('(', ' ').replace(')', ' ').split():
                c = _normalizar(trozo.strip(' ",'))
                if c:
                    return c
            return None
        return _normalizar(os.environ.get('LANG'))
    except Exception:
        return None


def resolver(compilado, env=None, ini=None, hay_preferencias=False, sistema=None):
    """El idioma que toca, como funcion pura (las baterias la prueban).
    Devuelve (codigo, escribir_ini)."""
    forzado = _normalizar((env or {}).get('CINECAPTIONS_IDIOMA'))
    if forzado:
        return forzado, False
    if not compilado:
        return POR_DEFECTO, False
    if ini:
        return ini, False
    if hay_preferencias:
        return POR_DEFECTO, True
    return (sistema or POR_DEFECTO), True


def _decidir():
    compilado = bool(getattr(sys, 'frozen', False))
    ini = leer_ini() if compilado else None
    hay_pref = (CARPETA / 'preferencias.json').is_file() if compilado else False
    sistema = idioma_del_sistema() if compilado and not ini and not hay_pref else None
    codigo, escribir = resolver(compilado, os.environ, ini, hay_pref, sistema)
    if escribir:
        guardar_idioma(codigo)
    return codigo


global IDIOMA, _CATALOGO, _NOMBRES
IDIOMA = _decidir()
_CATALOGO = {}
_NOMBRES = {}


def _cargar(codigo):
    textos, nombres = {}, {}
    try:
        datos = json.loads(
            (_base_recursos() / 'locales' / f'{codigo}.json').read_text(encoding='utf-8')
        )
        textos = datos.get('textos') or {}
        nombres = datos.get('idiomas') or {}
    except (OSError, ValueError, AttributeError):
        pass
    return textos, nombres


def cambiar_idioma_en_caliente(codigo):
    """Solo para las pruebas (el programa cambia de idioma al reiniciar)."""
    global IDIOMA, _CATALOGO, _NOMBRES
    IDIOMA = _normalizar(codigo) or POR_DEFECTO
    _CATALOGO, _NOMBRES = _cargar(IDIOMA) if IDIOMA != 'es' else ({}, {})


cambiar_idioma_en_caliente(IDIOMA)


def idioma():
    return IDIOMA


def tr(texto, /, **valores):
    """El texto en el idioma de la interfaz. Con valores, les da formato.

    'texto' es posicional-only (v3.4.1): con `tr("... {texto}", texto=x)`
    el marcador chocaba con el parametro y Tk moria con «got multiple
    values for argument 'texto'» (el selector de emojis, buscando algo que
    no existe). Asi el marcador puede llamarse como quiera.
    """
    traducido = _CATALOGO.get(texto) or texto
    if not valores:
        return traducido
    try:
        return traducido.format(**valores)
    except (KeyError, ValueError, IndexError, AttributeError):
        try:
            return texto.format(**valores)
        except (KeyError, ValueError, IndexError, AttributeError):
            return texto


_LIBRE = {'idioma': None, 'trozos': [], 'plantillas': []}


def _preparar_libre():
    """Indice de tr_libre: los textos del catalogo que son trozos fijos (ordenados del mas largo al mas corto) y los que llevan {marcadores}."""
    import re
    trozos, plantillas = [], []
    for clave, valor in _CATALOGO.items():
        if not clave or not valor or clave == valor:
            continue
        if '{' in clave:
            import re as _re
            if len(_re.sub(r'\{[^{}]*\}', '', clave).strip()) < 16:         # plantillas casi sin texto fijo («{n} de {total}») casarian con cualquier frase
                continue
            try:
                patron = ''.join('(?P<%s>.+?)' % m.group(1) if m.lastindex else re.escape(m.group(0))
                                 for m in re.finditer(r'\{([A-Za-z_]\w*)(?:[^{}]*)\}|[^{]+|\{', clave))
                plantillas.append((re.compile('^' + patron + '$', re.S), valor))
            except re.error:
                pass
        elif len(clave.strip()) >= 10:
            trozos.append((clave, valor))
    trozos.sort(key=lambda kv: -len(kv[0]))
    _LIBRE.update(idioma=IDIOMA, trozos=trozos, plantillas=plantillas)


def tr_libre(texto):
    """Traduce un texto que llega YA ARMADO (un mensaje de error de otro modulo, la linea de estado, lo que contesta un script de Resolve): entero si esta en
    el catalogo; si no, por plantilla ({marcadores}); si no, reemplazando cada trozo conocido. Lo que no conoce lo deja como esta. Nunca lanza."""
    try:
        if IDIOMA == 'es' or not texto or not isinstance(texto, str):
            return texto
        if _LIBRE['idioma'] != IDIOMA:
            _preparar_libre()
        directo = _CATALOGO.get(texto)
        if directo:
            return directo
        for patron, valor in _LIBRE['plantillas']:
            m = patron.match(texto)
            if m:
                valores = {k: tr_libre(v) for k, v in m.groupdict().items()}
                try:
                    return valor.format(**valores)
                except ValueError:                          # un marcador numerico ({f:g}): se reintenta con los numeros como numeros
                    try:
                        return valor.format(**{k: (int(v) if v.isdigit() else float(v) if v.replace('.', '', 1).isdigit() else v) for k, v in valores.items()})
                    except (KeyError, ValueError, IndexError):
                        break
                except (KeyError, IndexError):
                    break
        for clave, valor in _LIBRE['trozos']:
            if clave in texto:
                texto = texto.replace(clave, valor)
        return texto
    except Exception:
        return texto


def nombre_idioma(codigo, respaldo=None):
    """El nombre de un idioma (de transcripcion o traduccion) en el idioma
    de la interfaz; sin dato, el respaldo (el nombre en español)."""
    return _NOMBRES.get(codigo) or respaldo or codigo
