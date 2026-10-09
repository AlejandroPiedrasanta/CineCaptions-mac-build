# CineCaptions · By Cinema Productions
# 3_compilar/rthook_stanza_stub.py — hook de arranque de PyInstaller (sustituye stanza para que Argos no arrastre torch).
"""
rthook_stanza_stub.py
----------------------
Runtime hook de PyInstaller. Corre DENTRO del programa compilado, antes de
que se ejecute ninguna linea de "CineCaptions (script principal).py" -es el punto
de extension que PyInstaller ofrece justo para esto: meter algo en
sys.modules antes de que el resto del programa haga sus imports normales.

(Recuperado del build original 4.1.0: estaba compilado dentro del .exe.)

POR QUE HACE FALTA
===================
argostranslate.sbd (el modulo que separa el texto en frases antes de
traducir) hace 'import stanza' SIN try/except -a diferencia de 'spacy',
que esta justo arriba en el mismo archivo y si lo lleva-. O sea que
argostranslate.translate, que es lo unico que usa este programa, no puede
ni siquiera IMPORTARSE sin que 'stanza' exista.

Y 'stanza' arrastra 'torch': +497 MB en disco y el 'import faster_whisper'
6x mas lento, asi que no se puede empaquetar sin pagar ese precio en CADA
arranque del programa, lo use o no quien lo abre.

LA SALIDA: 'stanza' NUNCA se usa de verdad en nuestro caso. OJO, la
premisa original de este parrafo QUEDO ROTA (v1.0.69, caso real 12-09):
los paquetes de idioma 1_9 del indice oficial de Argos SI traen carpeta
stanza/ (y ninguna minisbd/), asi que con chunk_type DEFAULT
argostranslate elegia StanzaSentencizer y este stub reventaba en la
PRIMERA traduccion del compilado. La defensa real ahora es
ARGOS_CHUNK_TYPE=MINISBD, puesta con setdefault ANTES de importar
argostranslate en subtitle_transcriber.py y ensure_lang_pack.py: fuerza
MiniSBDSentencizer ignorando el packaged_sbd_path. Este stub queda como
red de seguridad del 'import stanza' de sbd.py (sin el, argostranslate
ni se puede importar) y su mensaje delata si la env var no quedo puesta.

Asi que 'stanza' solo hace falta EXISTIR para que el 'import' no reviente:
no hace falta que HAGA nada. Este stub deja un modulo vacio en su lugar,
con un 'Pipeline' que revienta con un mensaje claro SI alguna vez alguien
llega a necesitarlo de verdad (un paquete de idioma raro que si pida
stanza), en vez de fallar con el 'ModuleNotFoundError' opaco de antes.

Se registra en el .spec con runtime_hooks=[...], y 'stanza' sigue en los
excludes -asi PyInstaller no intenta empaquetar el real, que es lo que
costaba los 497 MB-.
"""
import sys
import types

if 'stanza' not in sys.modules:
    _stub = types.ModuleType('stanza')

    class _PipelineSinStanza:
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "Este programa no incluye 'stanza' (ahorra ~500 MB y evita arrancar "
                "mas lento). El traductor usa MiniSBD (ARGOS_CHUNK_TYPE=MINISBD); si "
                "esto salto es que esa variable no quedo puesta antes de importar "
                "argostranslate — es un fallo del programa, no de tus paquetes de "
                "idioma. Avisa al soporte con este mensaje.")

    _stub.Pipeline = _PipelineSinStanza
    sys.modules['stanza'] = _stub
