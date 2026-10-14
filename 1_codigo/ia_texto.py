# CineCaptions · By Cinema Productions
# 1_codigo/ia_texto.py — IA de texto local (Qwen3): corrige, elige palabras clave y emojis virales, quita signos.
"""
ia_texto.py  (v5.1; v5.2 emojis, signos y servidor)
---------------------------------------------------
La IA de texto: corrige la transcripcion, elige las palabras clave y los
emojis con criterio de subtitulos VIRALES, con un modelo LOCAL (Qwen3
Instruct, en el motor de voz; sin coste por uso, sin internet despues de
instalarlo).

Se apoya en lo que ya funcionaba:
  * los tiempos de cada palabra NO se tocan (las correcciones son palabra
    por palabra en la misma posicion);
  * los grupos contexto / principal / complemento los arma
    sugerencias_ia._roles_por_bloque, con sus reglas: el modelo solo dice
    cuanto pesa cada palabra en su frase, mezclado con el puntaje de
    siempre. Asi una respuesta rara del modelo no puede romper el diseño;
  * v5.2: los emojis que propone el modelo se traducen al catalogo del
    programa (emojis.catalogo): uno que no tenga imagen no se pone; se
    respetan los elegidos a mano y nunca van dos palabras seguidas con emoji.

v5.2: el modelo queda CARGADO unos minutos (motor_texto.py --servidor): la
segunda pulsacion de «Asistencia» tarda segundos. Antes de transcribir
se libera (liberar()) para dejarle la GPU al motor de voz.

Si la IA no esta instalada (o falla), roles_inteligentes() usa el motor de
siempre (heuristico) y corregir no cambia nada: el un-clic funciona igual.
"""
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import motor_voz
import sugerencias_ia

PESO_IA = 0.7          # cuanto manda el modelo frente al puntaje de siempre
DENSIDAD_UN_CLIC = 0.9
INACTIVO_S = 180       # segundos que el modelo queda cargado sin trabajo
SIN_SENAL_S = 100      # v5.11: sin ninguna línea del modelo durante tanto = colgado (una pasada normal da una línea cada pocos segundos; antes 240 s: se veía «cargando» 4 min)
AVISO_LENTA_S = 35     # a partir de aquí se le dice al usuario que la IA tarda y cuánto falta para probar el modelo ligero
FALLOS_SEGUIDOS_MAX = 2
_FALLOS = {'n': 0, 'avisado': False}


def _reg():
    try:
        import registro
        return registro
    except Exception:
        return None


def abortar():
    """Mata la IA de texto SIN pedir el candado (quien lo tiene puede ser quien está colgado): el vigía lo usa; el pedido en curso falla y analizar()
    prueba con el modelo de respaldo / el motor de reglas."""
    s = _SRV.get('s')
    if s is not None and s.vivo():
        try:
            s.p.kill()
            return True
        except Exception:
            pass
    return False
# los signos que se quitan con «Asistencia» (pedido: «que quite . comillas
# todos los signos»): el estilo de los subtitulos virales va sin puntuacion
SIGNOS = '.,;:…"\'“”«»‘’()[]{}¡!¿?-–—'
VS16 = '️'


def script():
    return motor_voz._base_recursos() / 'motor_qwen' / 'motor_texto.py'


def disponible():
    info = motor_voz.info_instalado()
    return bool(info and info.get('modelo_texto'))


# ---------------------------------------------------------------------------
# el servidor (un proceso con el modelo cargado)
# ---------------------------------------------------------------------------
class _Servidor:
    def __init__(self, modelo):
        self.modelo = modelo
        entorno = dict(os.environ)
        entorno['PYTHONIOENCODING'] = 'utf-8'
        entorno['PYTHONUNBUFFERED'] = '1'
        entorno.pop('PYTHONPATH', None)
        entorno.pop('PYTHONHOME', None)
        self.p = subprocess.Popen([str(motor_voz.python_motor()), '-u', str(script()), '--servidor',
                                   '--modelo', modelo, '--inactivo', str(INACTIVO_S)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=entorno, creationflags=motor_voz.SIN_VENTANA, cwd=str(motor_voz.carpeta()))
        self.lineas = queue.Queue()
        self.errores = []
        threading.Thread(target=self._leer, daemon=True, name='ia-texto-out').start()
        threading.Thread(target=self._leer_err, daemon=True, name='ia-texto-err').start()

    def _leer(self):
        for linea in iter(self.p.stdout.readline, b''):
            self.lineas.put(linea.decode('utf-8', 'replace').rstrip())
        self.lineas.put(None)

    def _leer_err(self):
        for linea in iter(self.p.stderr.readline, b''):
            self.errores.append(linea.decode('utf-8', 'replace').rstrip())
            del self.errores[:-40]

    def vivo(self):
        return self.p.poll() is None

    def pedir(self, entrada, salida, linea_cb, timeout=900, sin_senal=SIN_SENAL_S):
        """v5.11: `sin_senal` = segundos sin ninguna línea del modelo tras los que se da por colgado, se mata y se devuelve el fallo (antes esperaba
        hasta 15 min con el candado tomado)."""
        self.p.stdin.write((json.dumps({'entrada': entrada, 'salida': salida}) + '\n').encode('utf-8'))
        self.p.stdin.flush()
        inicio = ultima = time.time()
        ultimo_aviso = 0.0
        while time.time() - inicio < timeout:
            try:
                linea = self.lineas.get(timeout=1.0)
            except queue.Empty:
                if not self.vivo():
                    break
                callada = time.time() - ultima
                if callada > sin_senal:
                    self.cerrar()
                    return False, f'la IA de texto se quedó sin responder {int(sin_senal)} s'
                if callada > AVISO_LENTA_S and time.time() - ultimo_aviso > 10:
                    ultimo_aviso = time.time()
                    try:
                        linea_cb('ESTADO', f'La IA de texto tarda más de lo normal… si no responde en {max(1, int(sin_senal - callada))} s pruebo con el modelo ligero.')
                    except Exception:
                        pass
                continue
            ultima = time.time()
            if linea is None:
                break
            tipo, _, resto = linea.partition('|')
            if tipo == 'LISTO':
                return True, resto
            if tipo == 'ERROR':
                return False, resto
            if tipo == 'FIN':
                break
            linea_cb(tipo, resto)
        return False, (self.errores[-1] if self.errores else 'la IA de texto se cerró')

    def cerrar(self):
        try:
            self.p.stdin.write(b'salir\n')
            self.p.stdin.flush()
            self.p.wait(timeout=8)
        except Exception:
            try:
                self.p.kill()
            except Exception:
                pass


_SRV = {'s': None}
_PREFERIDO = {'m': None}      # el modelo que SÍ funcionó tras fallar el grande: en esta sesión se va directo a él (no se vuelven a perder ~100 s cada vez)
_LOCK = threading.Lock()


def liberar():
    """Descarga el modelo (deja la GPU para el motor de voz o para Resolve)."""
    with _LOCK:
        s, _SRV['s'] = _SRV['s'], None
    if s is not None:
        s.cerrar()


def precargar():
    """v5.3: arranca la IA de texto EN SEGUNDO PLANO (modelo + calentamiento) sin bloquear a nadie. Se llama al pulsar GO
    (mientras la voz trabaja) o al terminar la voz: cuando llegan las palabras, el modelo ya esta listo. True si quedo en
    marcha o ya estaba."""
    try:
        if not disponible():
            return False
        if not _LOCK.acquire(blocking=False):          # un pedido esta corriendo: el servidor ya existe
            return True
        try:
            s = _SRV['s']
            if s is None or not s.vivo():
                info = motor_voz.info_instalado() or {}
                _SRV['s'] = _Servidor(motor_voz.modelo_texto(info))
            return True
        finally:
            _LOCK.release()
    except Exception:
        _SRV['s'] = None
        return False


# v5.4.25: el resultado de la IA se guarda por huella (palabras + idioma + modo + modelo + motor): volver a pulsar GO sobre el mismo video (probar otro tema) no vuelve a correr el modelo
# (7 s con la GPU libre, hasta 2 min cuando hay otras cosas usándola) y deja el mismo resultado. Se guarda con archivos_seguros; se conservan las últimas 80.
_CACHE_MAX = 80


def _carpeta_cache():
    return Path.home() / 'DaVinciSubtitles' / 'ia_cache'


def _clave_cache(textos, idioma, modo, modelo):
    import hashlib
    try:
        motor = hashlib.sha1(script().read_bytes()).hexdigest()[:12]
    except Exception:
        motor = 'sin-motor'
    base = json.dumps({'v': 1, 'palabras': textos, 'idioma': idioma, 'modo': modo or '', 'modelo': modelo, 'motor': motor}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(base.encode('utf-8')).hexdigest()


def _resultado_de_datos(datos):
    return {'correcciones': {int(k): v for k, v in (datos.get('correcciones') or {}).items()},
            'pesos': {int(k): float(v) for k, v in (datos.get('pesos') or {}).items()},
            'emojis': {int(k): str(v) for k, v in (datos.get('emojis') or {}).items()},
            'modelo': datos.get('modelo'), 'segundos': datos.get('segundos')}


def _leer_cache(clave):
    try:
        import archivos_seguros
        datos = archivos_seguros.leer_json(_carpeta_cache() / (clave + '.json'), None)
        if isinstance(datos, dict) and 'correcciones' in datos and 'pesos' in datos:
            return _resultado_de_datos(datos)
    except Exception:
        pass
    return None


def _guardar_cache(clave, datos):
    try:
        import archivos_seguros
        carpeta = _carpeta_cache()
        archivos_seguros.escribir_json(carpeta / (clave + '.json'), {k: datos.get(k) for k in ('correcciones', 'pesos', 'emojis', 'modelo', 'segundos')})
        viejos = sorted(carpeta.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[_CACHE_MAX:]
        for f in viejos:
            try:
                f.unlink()
            except OSError:
                pass
    except Exception:
        pass


def _sin_traducciones(textos, resultado, idioma):
    """v5.4.51: la IA a veces «corrige» TRADUCIENDO (en un vídeo en inglés, «effects» -> «efectos»). Con el diccionario del idioma: si la palabra
    original existe en ese idioma y la «corrección» no, no es una corrección y se descarta."""
    if str(idioma or '')[:2] != 'en':                                # (los diccionarios con tildes no las traen todas: «como» -> «cómo» se perdería;
        return resultado                                               #  ahí manda la barrera de letras del motor, motor_texto.traduce)
    try:
        import ortografia
        corrector = ortografia._corrector(idioma)
    except Exception:
        corrector = None
    if corrector is None or not resultado.get('correcciones'):
        return resultado
    limpia = lambda t: ''.join(c for c in str(t).lower() if c.isalpha() or c in "'")      # noqa: E731
    buenas = {}
    for i, nueva in resultado['correcciones'].items():
        vieja = textos[i] if 0 <= i < len(textos) else ''
        v, n = limpia(vieja), limpia(nueva)
        if v and n and v != n and corrector.known([v]) and not corrector.known([n]):
            continue
        buenas[i] = nueva
    return dict(resultado, correcciones=buenas)


def analizar(palabras, idioma='es', progreso=None, estado=None, modo=None):
    """Corre el modelo. Devuelve {'correcciones': {i: palabra}, 'pesos': {i: 0..1},
    'emojis': {i: glifo}}. Lanza RuntimeError si no se pudo."""
    textos = [str(p.get('word', '')).strip() for p in palabras]
    clave = None
    try:
        clave = _clave_cache(textos, idioma, modo, motor_voz.modelo_texto())
        guardado = _leer_cache(clave)
        if guardado is not None:
            r0 = _reg()
            if r0:
                r0.info('Resultado de la IA reutilizado (mismas palabras, mismo idioma): no se vuelve a correr el modelo.', 'IA de texto')
            return _sin_traducciones(textos, guardado, idioma)
    except Exception:
        clave = None
    fd, entrada = tempfile.mkstemp(prefix='cinecaptions_texto_', suffix='.json')
    os.close(fd)
    salida = entrada[:-5] + '.out.json'
    Path(entrada).write_text(json.dumps({'idioma': idioma, 'palabras': textos, 'modo': modo or ''}, ensure_ascii=False), encoding='utf-8')

    def linea(tipo, texto):
        if tipo == 'PROGRESO' and progreso:
            try:
                progreso(float(texto))
            except ValueError:
                pass
        elif tipo == 'ESTADO' and estado:
            estado(texto)

    try:
        info = motor_voz.info_instalado() or {}
        modelo = motor_voz.modelo_texto(info)
        r = _reg()
        if _FALLOS['n'] >= FALLOS_SEGUIDOS_MAX:
            # v5.11: dos fallos seguidos = no se vuelve a perder tiempo con la IA de texto en esta sesión (motor de reglas); reiniciar la reactiva
            if not _FALLOS['avisado']:
                _FALLOS['avisado'] = True
                if r:
                    r.error('La IA de texto falló %d veces seguidas: sigo con el motor de reglas (sin corrección por IA) hasta reiniciar el programa. '
                            'Revisa Ajustes > General > Motor de voz > Reparar.' % _FALLOS['n'], 'IA de texto')
            raise RuntimeError('la IA de texto está desactivada en esta sesión tras fallar varias veces')
        # v5.11: si el modelo grande falla, se cambia SOLO al ligero (1.7B) antes de rendirse; cada intento queda en el Registro
        modelos = [modelo] + (['1.7B'] if modelo != '1.7B' else [])
        if _PREFERIDO['m'] and _PREFERIDO['m'] != modelo:
            modelos = [_PREFERIDO['m']]
        ok, texto = False, ''
        for k, m in enumerate(modelos):
            with _LOCK:
                s = _SRV['s']
                if s is None or not s.vivo() or (k and getattr(s, 'modelo', None) != m):
                    if estado:
                        estado('Cargando la IA de texto (la primera vez tarda unos segundos)…' if not k else 'La IA de texto falló; pruebo con el modelo ligero…')
                    s = _Servidor(m)
                    _SRV['s'] = s
                try:
                    ok, texto = s.pedir(entrada, salida, linea)
                except Exception as e:                 # p. ej. el proceso murió antes de aceptar el pedido (tubería rota)
                    ok, texto = False, f'{type(e).__name__}: {e}'
                if not ok:
                    # un servidor muerto o colgado no se reutiliza
                    s.cerrar()
                    _SRV['s'] = None
            if ok:
                if k and r:
                    r.ok(f'La IA de texto funcionó con el modelo {m}.', 'IA de texto')
                if k:
                    _PREFERIDO['m'] = m
                break
            if r:
                r.aviso(f'La IA de texto ({m}) falló: {str(texto)[:200]}', 'IA de texto')
        if not ok:
            _FALLOS['n'] += 1
            raise RuntimeError(texto)
        if _FALLOS['n'] and r:
            r.ok('La IA de texto volvió a funcionar.', 'IA de texto')
        _FALLOS['n'], _FALLOS['avisado'] = 0, False
        datos = json.loads(Path(salida).read_text(encoding='utf-8'))
        if clave:
            _guardar_cache(clave, datos)
        return _sin_traducciones(textos, _resultado_de_datos(datos), idioma)
    finally:
        for f in (entrada, salida):
            try:
                os.unlink(f)
            except OSError:
                pass


def escenas(bloques, idioma='es', estado=None):
    """v5.4.51, el director de escenas del Tema 5: la IA local lee las frases de los captions (una cadena por bloque) y propone qué ilustrar
    [{'b': índice del bloque, 'tipo', 'datos', 'anclas'}] (motor_texto, modo 'escenas'). [] si no hay IA o falla (el Tema 5 sigue con sus reglas).
    Con caché por huella, como analizar()."""
    if not bloques or not disponible() or _FALLOS['n'] >= FALLOS_SEGUIDOS_MAX:
        return []
    textos = [str(b) for b in bloques]
    modelo = motor_voz.modelo_texto()
    clave = _clave_cache(textos, idioma, 'escenas', modelo)
    archivo = _carpeta_cache() / ('escenas_' + clave + '.json')
    try:
        import archivos_seguros
        datos = archivos_seguros.leer_json(archivo, None)
        if isinstance(datos, dict) and isinstance(datos.get('escenas'), list):
            return datos['escenas']
    except Exception:
        pass
    fd, entrada = tempfile.mkstemp(prefix='cinecaptions_escenas_', suffix='.json')
    os.close(fd)
    salida = entrada[:-5] + '.out.json'
    Path(entrada).write_text(json.dumps({'modo': 'escenas', 'idioma': idioma, 'bloques': textos}, ensure_ascii=False), encoding='utf-8')
    try:
        with _LOCK:
            s = _SRV['s']
            if s is None or not s.vivo():
                if estado:
                    estado('Cargando la IA de texto para dirigir las escenas…')
                s = _Servidor(_PREFERIDO['m'] or modelo)
                _SRV['s'] = s
            try:
                ok, texto = s.pedir(entrada, salida, lambda tipo, t: estado(t) if (estado and tipo == 'ESTADO') else None, timeout=600)
            except Exception as e:
                ok, texto = False, f'{type(e).__name__}: {e}'
            if not ok:
                s.cerrar()
                _SRV['s'] = None
        r = _reg()
        if not ok:
            if r:
                r.aviso(f'El director de escenas (IA) falló: {str(texto)[:200]}; sigo con las reglas.', 'IA de texto')
            return []
        datos = json.loads(Path(salida).read_text(encoding='utf-8'))
        try:
            import archivos_seguros
            archivos_seguros.escribir_json(archivo, {'escenas': datos.get('escenas') or [], 'segundos': datos.get('segundos')})
        except Exception:
            pass
        if r:
            r.info(f"Director de escenas (IA): {len(datos.get('escenas') or [])} propuestas en {datos.get('segundos')} s.", 'IA de texto')
        return datos.get('escenas') or []
    except Exception:
        return []
    finally:
        for f in (entrada, salida):
            try:
                os.unlink(f)
            except OSError:
                pass


CATEGORIAS = ('boda', 'xv', 'fotografia', 'inmobiliaria', 'restaurante', 'cocina', 'negocios', 'finanzas', 'marketing', 'fitness', 'salud', 'belleza',
              'moda', 'viajes', 'tecnologia', 'educacion', 'motivacion', 'humor', 'familia', 'deporte', 'musica', 'otro')
TONOS = ('elegante', 'energico', 'divertido', 'calmado', 'serio', 'inspirador', 'tecnico')


def perfil(palabras_texto, idioma='es', estado=None):
    """v5.5.2: de qué va el video, para la edición: {'categoria', 'subtema', 'tono', 'iconos', 'publico'} (motor_texto, modo 'perfil'), o {} si no hay IA.
    Con caché por huella del texto. La categoría y el tono son de CATEGORIAS / TONOS; los iconos, de los animados que existen."""
    texto = ' '.join(str(w) for w in palabras_texto or []).strip()
    if len(texto.split()) < 8 or not disponible() or _FALLOS['n'] >= FALLOS_SEGUIDOS_MAX:
        return {}
    import edicion_pro_kit7 as K7
    iconos = K7.iconos_disponibles()
    modelo = motor_voz.modelo_texto()
    clave = _clave_cache([texto[:6000]], idioma, 'perfil', modelo)
    archivo = _carpeta_cache() / ('perfil_' + clave + '.json')
    try:
        import archivos_seguros
        datos = archivos_seguros.leer_json(archivo, None)
        if isinstance(datos, dict) and isinstance(datos.get('perfil'), dict):
            return datos['perfil']
    except Exception:
        pass
    fd, entrada = tempfile.mkstemp(prefix='cinecaptions_perfil_', suffix='.json')
    os.close(fd)
    salida = entrada[:-5] + '.out.json'
    Path(entrada).write_text(json.dumps({'modo': 'perfil', 'idioma': idioma, 'texto': texto[:6000], 'categorias': list(CATEGORIAS), 'tonos': list(TONOS),
                                         'iconos': iconos}, ensure_ascii=False), encoding='utf-8')
    try:
        with _LOCK:
            s = _SRV['s']
            if s is None or not s.vivo():
                if estado:
                    estado('Cargando la IA de texto para entender el video…')
                s = _Servidor(_PREFERIDO['m'] or modelo)
                _SRV['s'] = s
            try:
                ok, texto_r = s.pedir(entrada, salida, lambda tipo, t: estado(t) if (estado and tipo == 'ESTADO') else None, timeout=300)
            except Exception as e:
                ok, texto_r = False, f'{type(e).__name__}: {e}'
            if not ok:
                s.cerrar()
                _SRV['s'] = None
        if not ok:
            r = _reg()
            if r:
                r.aviso(f'La IA no pudo entender de qué va el video: {str(texto_r)[:200]}; sigo sin su perfil.', 'IA de texto')
            return {}
        datos = json.loads(Path(salida).read_text(encoding='utf-8'))
        p = datos.get('perfil') or {}
        try:
            import archivos_seguros
            archivos_seguros.escribir_json(archivo, {'perfil': p, 'segundos': datos.get('segundos')})
        except Exception:
            pass
        r = _reg()
        if r and p:
            r.info(f"La IA entiende el video: {p.get('categoria') or '—'} · {p.get('subtema') or '—'} · tono {p.get('tono') or '—'} "
                   f"({datos.get('segundos')} s).", 'IA de texto')
        return p
    except Exception:
        return {}
    finally:
        for f in (entrada, salida):
            try:
                os.unlink(f)
            except OSError:
                pass


def motions(bloques, idioma='es', estado=None, genero='general', contexto='', solo=None):
    """v5.5.2, el director de motions del kit de la skill: la IA local lee las frases y elige del MENÚ (edicion_pro_kit7.MOTIONS) qué motion poner,
    dónde y con qué textos e iconos → [{'b', 'motion', 'datos', 'ancla'}] (motor_texto, modo 'motions'). [] si no hay IA o falla (siguen las reglas).
    edicion_pro_kit7.desde_ia lo valida. Con caché por huella (frases + menú), como escenas()."""
    if not bloques or not disponible() or _FALLOS['n'] >= FALLOS_SEGUIDOS_MAX:
        return []
    import edicion_pro_kit7 as K7
    textos = [str(b) for b in bloques]
    menu = K7.menu_para_ia(genero, solo)                                # el kit + las escenas + las plantillas de este tipo de video (v5.5.3: `solo` = esas familias)
    iconos = K7.iconos_disponibles()
    modelo = motor_voz.modelo_texto()
    clave = _clave_cache(textos + [json.dumps(menu, ensure_ascii=False, sort_keys=True), str(contexto or '')], idioma, 'motions', modelo)
    archivo = _carpeta_cache() / ('motions_' + clave + '.json')
    try:
        import archivos_seguros
        datos = archivos_seguros.leer_json(archivo, None)
        if isinstance(datos, dict) and isinstance(datos.get('motions'), list):
            return datos['motions']
    except Exception:
        pass
    fd, entrada = tempfile.mkstemp(prefix='cinecaptions_motions_', suffix='.json')
    os.close(fd)
    salida = entrada[:-5] + '.out.json'
    Path(entrada).write_text(json.dumps({'modo': 'motions', 'idioma': idioma, 'bloques': textos, 'menu': menu, 'iconos': iconos, 'contexto': str(contexto or '')},
                                        ensure_ascii=False), encoding='utf-8')
    try:
        with _LOCK:
            s = _SRV['s']
            if s is None or not s.vivo():
                if estado:
                    estado('Cargando la IA de texto para elegir los motions…')
                s = _Servidor(_PREFERIDO['m'] or modelo)
                _SRV['s'] = s
            try:
                ok, texto = s.pedir(entrada, salida, lambda tipo, t: estado(t) if (estado and tipo == 'ESTADO') else None, timeout=600)
            except Exception as e:
                ok, texto = False, f'{type(e).__name__}: {e}'
            if not ok:
                s.cerrar()
                _SRV['s'] = None
        r = _reg()
        if not ok:
            if r:
                r.aviso(f'El director de motions (IA) falló: {str(texto)[:200]}; sigo con las reglas.', 'IA de texto')
            return []
        datos = json.loads(Path(salida).read_text(encoding='utf-8'))
        try:
            import archivos_seguros
            archivos_seguros.escribir_json(archivo, {'motions': datos.get('motions') or [], 'segundos': datos.get('segundos')})
        except Exception:
            pass
        if r:
            r.info(f"Director de motions (IA): {len(datos.get('motions') or [])} propuestas en {datos.get('segundos')} s.", 'IA de texto')
        return datos.get('motions') or []
    except Exception:
        return []
    finally:
        for f in (entrada, salida):
            try:
                os.unlink(f)
            except OSError:
                pass


def aplicar_correcciones(palabras, correcciones):
    """Copia de las palabras con las correcciones puestas (mismos tiempos)."""
    nuevas = [dict(p) for p in palabras]
    for i, texto in (correcciones or {}).items():
        if 0 <= i < len(nuevas) and texto.strip():
            nuevas[i]['word'] = texto.strip()
    return nuevas


# ---------------------------------------------------------------------------
# v5.2: signos y emojis
# ---------------------------------------------------------------------------
def marcar_fin_de_frase(palabras):
    """Deja w['fin_frase'] en cada palabra ANTES de quitar los signos (los
    cortes de bloque la respetan: sin puntos no se pierden las frases)."""
    import dynamic_subtitles as dyn
    total = len(palabras)
    for i, w in enumerate(palabras):
        if 'fin_frase' in w:
            continue
        siguiente = palabras[i + 1] if i + 1 < total else None
        w['fin_frase'] = bool(siguiente is not None and dyn.hay_corte_de_frase(w, siguiente))
    return palabras


def sin_signos(palabras, signos=SIGNOS):
    """Quita los signos del principio y del final de cada palabra (y las
    comillas de dentro). Una palabra que quedaria vacia se deja como estaba.
    Devuelve cuantas cambiaron."""
    marcar_fin_de_frase(palabras)
    cambios = 0
    for w in palabras:
        for clave in ('word', 'orig'):
            if clave not in w:
                continue
            original = str(w[clave])
            limpia = original.strip().strip(signos)
            for c in '"“”«»':
                limpia = limpia.replace(c, '')
            if limpia and limpia != original:
                w[clave] = limpia
                if clave == 'word':
                    cambios += 1
    return cambios


def _por_glifo():
    """{glifo sin VS16: id} del catalogo (solo emojis con imagen posible)."""
    try:
        import emojis
        return {str(e.get('glifo') or '').replace(VS16, ''): e['id'] for e in emojis.catalogo() if e.get('glifo')}
    except Exception:
        return {}


_DEMOSTRATIVOS = {'este', 'esta', 'esto', 'estos', 'estas', 'ese', 'esa', 'eso', 'esos', 'esas', 'aquel', 'aquella',
                  'aquello', 'mi', 'mis', 'tu', 'tus', 'su', 'sus', 'yo', 'el', 'ella', 'ellos', 'nos', 'les',
                  'this', 'that', 'these', 'those', 'it', 'my', 'your', 'his', 'her', 'its', 'our', 'their',
                  'isso', 'esse', 'essa', 'isto', 'meu', 'seu', 'sua', 'ce', 'cette', 'ces', 'mon', 'ton', 'son'}


def _sin_carga(texto):
    limpio = str(texto or '').strip(SIGNOS)
    if len(limpio) < 3 or limpio.lower() in _DEMOSTRATIVOS:
        return True
    try:
        import dynamic_subtitles as dyn
        return dyn.es_conector(limpio)
    except Exception:
        return False


def emojis_de_ia(palabras, propuestos, idioma='es', roles=None):
    """{indice: id_del_catalogo} a partir de los glifos que propuso la IA:
    solo los que existen en el catalogo, nunca dos palabras seguidas, nunca
    el mismo emoji a menos de 8 palabras, y nunca encima de uno puesto a mano
    (w['emoji'] sin w['emoji_ia']). Un emoji que cae en una palabra sin
    carga («este») pasa a la principal mas cercana de su frase."""
    por_glifo = _por_glifo()
    elegidos = {}
    ultimo_por_id = {}
    frase, n_frase = [], 0                             # v5.4.25: a qué frase pertenece cada palabra (el emoji de «miedo» caía en «guitarra», la última palabra de la frase ANTERIOR)
    for w in palabras:
        frase.append(n_frase)
        if w.get('fin_frase'):
            n_frase += 1
    for i in sorted(propuestos or {}):
        if not 0 <= i < len(palabras):
            continue
        destino = i
        # en los virales el emoji acompaña a la palabra destacada (la principal), de SU frase
        if _sin_carga(palabras[i].get('word')) or (roles is not None and roles[i] != 'main'):
            cerca = [j for j in range(max(0, i - 4), min(len(palabras), i + 5))
                     if roles is not None and roles[j] == 'main' and frase[j] == frase[i]]
            if cerca:
                destino = min(cerca, key=lambda j: abs(j - i))
            elif _sin_carga(palabras[i].get('word')):
                continue
        glifo = propuestos[i]
        i = destino
        w = palabras[i]
        if w.get('emoji') and not w.get('emoji_ia'):
            continue
        if i in elegidos:
            continue
        eid = por_glifo.get(str(glifo).replace(VS16, '').strip())
        if eid is None:
            # el glifo no esta: lo mas parecido para esa palabra (claves CLDR)
            try:
                import emojis
                ids = emojis.sugerir(w.get('word', ''), idioma)
                eid = ids[0] if ids else None
            except Exception:
                eid = None
        if eid is None:
            continue
        if (i - 1) in elegidos or (i + 1) in elegidos:
            continue
        if eid in ultimo_por_id and i - ultimo_por_id[eid] < 8:
            continue
        elegidos[i] = eid
        ultimo_por_id[eid] = i
    return elegidos


def poner_emojis(palabras, elegidos):
    """Pone los emojis de la IA (marcados como tales: otra pasada los puede
    cambiar, a los del usuario no los toca). Devuelve cuantos puso."""
    for w in palabras:
        if w.get('emoji_ia'):
            w.pop('emoji', None)
            w.pop('emoji_ia', None)
    n = 0
    for i, eid in elegidos.items():
        if 0 <= i < len(palabras) and not palabras[i].get('emoji'):
            palabras[i]['emoji'] = eid
            palabras[i]['emoji_ia'] = True
            n += 1
    return n


def _roles_por_ia(palabras, pesos, base, densidad, variante, tamanos, peso_conector):
    """v5.2 (pedido: «que la IA que selecciona el texto sea mas inteligente»):
    con la IA, el CENTRO de cada grupo es la palabra que ella eligio en esa
    oracion (la regla de siempre preferia el verbo: «GASTAR» antes que
    «ventas»). El grupo alrededor lo sigue armando dyn.grupo_alrededor, con
    las mismas reglas de diseño. {indice: rol}."""
    import dynamic_subtitles as dyn
    n_ctx, n_main, n_cmp = dyn.normalizar_tamanos(tamanos)
    oraciones = dyn.segmentar_oraciones(palabras)
    roles = {i: 'base' for i in range(len(palabras))}

    def vale(i):
        return not _sin_carga(palabras[i].get('word', ''))

    candidatas = []
    for k, (desde, hasta) in enumerate(oraciones):
        orden = sorted((i for i in range(desde, hasta) if vale(i) and (pesos.get(i, 0) > 0 or base.get(i, 0) > 0)),
                       key=lambda i: (-pesos.get(i, 0.0), -base.get(i, 0.0)))
        if orden:
            candidatas.append((k, orden))
    # primero las oraciones donde la IA vio algo fuerte
    candidatas.sort(key=lambda c: -(pesos.get(c[1][0], 0.0) * 2 + base.get(c[1][0], 0.0)))
    cupo = max(1, int(len(candidatas) * max(0.1, min(1.0, densidad)) + 0.9999)) if candidatas else 0
    hechas = 0
    for k, orden in candidatas:
        if hechas >= cupo:
            break
        desde, hasta = oraciones[k]
        opciones = orden[variante % len(orden):] + orden[:variante % len(orden)]
        for centro in opciones:
            grupo = dyn.grupo_alrededor(palabras, centro, desde, hasta, n_ctx, n_main, n_cmp,
                                        peso_conector=peso_conector)
            if len(set(grupo.values())) < 2:
                continue
            mains = [j for j, r in grupo.items() if r == 'main']
            if not mains or roles.get(min(mains) - 1) == 'main' or roles.get(max(mains) + 1) == 'main':
                continue
            roles.update(grupo)
            hechas += 1
            break
    return roles


ARCHIVO_ORTO = Path.home() / 'DaVinciSubtitles' / 'orto_cache.json'
_ORTO = {'datos': None}
TOPE_ORTO = 4000          # trozos guardados (el mas viejo sale primero)


def _orto_cargar():
    if _ORTO['datos'] is None:
        try:
            _ORTO['datos'] = json.loads(ARCHIVO_ORTO.read_text(encoding='utf-8'))
        except Exception:
            _ORTO['datos'] = {}
    return _ORTO['datos']


def _orto_guardar():
    try:
        datos = _ORTO['datos'] or {}
        if len(datos) > TOPE_ORTO:
            for k in list(datos)[:len(datos) - TOPE_ORTO]:
                datos.pop(k, None)
        ARCHIVO_ORTO.parent.mkdir(parents=True, exist_ok=True)
        temporal = ARCHIVO_ORTO.with_suffix('.tmp')
        temporal.write_text(json.dumps(datos, ensure_ascii=False), encoding='utf-8')
        temporal.replace(ARCHIVO_ORTO)
    except Exception:
        pass


def _trozos_para_orto(palabras, minimo=40):
    """[(desde, hasta)] con cortes en pausas o signos, de unas 40 palabras: cada trozo se corrige (y se guarda) por separado."""
    import dynamic_subtitles as dyn
    trozos, ini = [], 0
    for desde, hasta in dyn.segmentar_oraciones(palabras):
        if hasta - ini >= minimo:
            trozos.append((ini, hasta))
            ini = hasta
    if ini < len(palabras):
        trozos.append((ini, len(palabras)))
    return trozos


def correcciones_ortografia(palabras, idioma='es', al_avanzar=None):
    """v5.5: {indice: palabra corregida} de TODO el guion, pero solo se le pregunta a la IA por los trozos que no se habian
    corregido antes (la respuesta de cada trozo se guarda por su texto): reabrir un video o retocar unas palabras ya no
    vuelve a pasar todo por el modelo."""
    import hashlib
    datos = _orto_cargar()
    cambios, nuevos = {}, 0
    trozos = _trozos_para_orto(palabras)
    for k, (desde, hasta) in enumerate(trozos):
        sub = [dict(w) for w in palabras[desde:hasta]]
        clave = hashlib.sha1((idioma + '' + ''.join(str(w.get('word', '')) for w in sub)).encode('utf-8')).hexdigest()[:24]
        if clave in datos:
            local = {int(i): t for i, t in datos[clave].items()}
        else:
            r = analizar(sub, idioma, modo='ortografia')
            local = {int(i): t for i, t in (r.get('correcciones') or {}).items()}
            datos[clave] = {str(i): t for i, t in local.items()}
            nuevos += 1
        for i, t in local.items():
            cambios[desde + i] = t
        if al_avanzar:
            try:
                al_avanzar(k + 1, len(trozos))
            except Exception:
                pass
    if nuevos:
        _orto_guardar()
    return cambios


def roles_inteligentes(palabras, idioma='es', pesos=None, tamanos=None, peso_conector=None,
                       densidad=DENSIDAD_UN_CLIC, variante=0):
    """Lista de roles ('context'/'main'/'complement'/None) para todo el guion.
    'variante' (0..3) da otras versiones, como el boton de sugerir de siempre."""
    variante = int(variante) % sugerencias_ia.VARIANTES
    densidad = max(0.1, min(1.0, densidad + sugerencias_ia._AJUSTE_DENSIDAD.get(variante, 0.0)))
    base = sugerencias_ia._scores_heuristico(palabras, idioma)
    try:        # v5.4: «Arriba N · Principal N · Abajo N» es una REGLA: grupos de exactamente esas palabras, con la principal importante
        import dynamic_subtitles as dyn
        n_ctx, n_main, n_cmp = dyn.normalizar_tamanos(tamanos)
        tope = max([v for v in base.values()] + [1e-6])
        importancia = []
        for i, w in enumerate(palabras):
            if _sin_carga(w.get('word', '')):
                importancia.append(-1.0)
            else:
                importancia.append(0.05 + (0.9 * pesos.get(i, 0.0) if pesos else 0.0) + 0.55 * min(1.0, base.get(i, 0.0) / tope))
        # las variantes (0..3) desplazan un poco el reparto para dar otras versiones igual de validas
        if variante:
            for i in range(len(importancia)):
                if importancia[i] > 0:
                    importancia[i] += 0.12 * (((i * 2654435761 + variante * 40503) >> 7) % 100) / 100.0
        try:
            import ajustes_ui
            por_pausas = bool(ajustes_ui.leer_prefs().get('armar_por_pausas', True))
        except Exception:
            por_pausas = True
        grupos = dyn.grupos_estrictos(palabras, importancia, n_ctx, n_main, n_cmp, por_pausas=por_pausas)
        if any(r == 'main' for r in grupos.values()):
            return [grupos.get(i) for i in range(len(palabras))]
    except Exception as e:
        print('grupos estrictos:', e)
    if pesos:
        try:
            roles = _roles_por_ia(palabras, pesos, base, densidad, variante, tamanos, peso_conector)
            if any(r == 'main' for r in roles.values()):
                return [None if roles.get(i, 'base') == 'base' else roles[i] for i in range(len(palabras))]
        except Exception as e:
            print('roles por IA:', e)
    if pesos:
        scores = {}
        for i in range(len(palabras)):
            h = base.get(i, 0.0)
            ia = pesos.get(i, 0.0)
            # la IA sube lo que importa; el heuristico desempata el resto
            scores[i] = PESO_IA * ia + (1 - PESO_IA) * h if h > 0 else 0.0
    else:
        scores = base
    roles = sugerencias_ia._roles_por_bloque(palabras, scores, densidad, variante, tamanos, peso_conector)
    return [None if roles.get(i, 'base') == 'base' else roles[i] for i in range(len(palabras))]


def emojis_sin_ia(palabras, roles, idioma='es', cada=10):
    """Sin la IA: emojis por las claves del catalogo en las principales, con
    la misma densidad viral (uno cada ~10 palabras, nunca seguidos)."""
    propuestos = {}
    try:
        import emojis
    except Exception:
        return {}
    ultimo = -cada
    for i, w in enumerate(palabras):
        if roles[i] != 'main' or i - ultimo < cada:
            continue
        ids = emojis.sugerir(w.get('word', ''), idioma)
        if ids:
            propuestos[i] = ids[0]
            ultimo = i
    return propuestos


def marcar_todo(palabras, idioma='es', progreso=None, estado=None, tamanos=None, peso_conector=None,
                con_emojis=True, quitar_signos=True):
    """Lo que hace el un-clic: corregir + elegir + emojis + sin signos.
    Devuelve (palabras_corregidas, roles, resumen) — sin IA instalada, el
    motor de siempre (y los emojis por las claves del catalogo)."""
    resumen = {'ia': False, 'cambios': 0, 'modelo': None, 'emojis': 0, 'signos': 0}
    pesos, propuestos = None, None
    palabras = [dict(p) for p in palabras]
    marcar_fin_de_frase(palabras)
    if disponible():
        try:
            r = analizar(palabras, idioma, progreso=progreso, estado=estado)
            palabras = aplicar_correcciones(palabras, r['correcciones'])
            pesos = r['pesos']
            propuestos = r.get('emojis') or {}
            resumen.update(ia=True, cambios=len(r['correcciones']), modelo=r.get('modelo'))
        except Exception as e:
            resumen['error'] = str(e)[:200]
            r = _reg()
            if r:
                r.aviso(f'La IA de texto no pudo: {str(e)[:200]}. Sigo con el motor de reglas (sin corrección por IA).', 'IA de texto')
    # los roles se eligen CON la puntuacion (las reglas de siempre miran los
    # finales de frase); despues se quitan los signos: los indices no cambian
    roles = roles_inteligentes(palabras, idioma, pesos, tamanos, peso_conector)
    if quitar_signos:
        resumen['signos'] = sin_signos(palabras)
    if con_emojis:
        if propuestos is not None:
            elegidos = emojis_de_ia(palabras, propuestos, idioma, roles)
        else:
            elegidos = emojis_sin_ia(palabras, roles, idioma)
        resumen['emojis'] = poner_emojis(palabras, elegidos)
    resumen['grupos'] = sum(1 for r in roles if r == 'main')
    return palabras, roles, resumen
