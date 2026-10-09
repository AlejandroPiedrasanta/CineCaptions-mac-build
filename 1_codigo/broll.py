# CineCaptions · By Cinema Productions
# 1_codigo/broll.py — B-roll de bancos de stock (Pexels) en las palabras que nombran cosas concretas (v5.4.8).
"""
Cuando se dice «casa», «coche» o «playa», GO puede enseñar 2 s de una toma de apoyo (B-roll) de un banco gratuito de video. Necesita la CLAVE DE API del usuario
(gratis en pexels.com/api; se pega en la página Efectos › Más efectos › «B-roll»): sin ella no hace nada.

    elegir_momentos(palabras, duracion, idioma, cuanto)  -> [{'ini', 'dur', 'palabra', 'consulta'}]   qué palabras dan B-roll y qué buscar (en inglés)
    buscar(consulta, formato, clave)                     -> {'id', 'url', 'ancho', 'alto', 'dur'} | None
    preparar(momentos, formato, clave, al_estado)        -> [{'tipo': 'broll', 'ini', 'dur', 'asset', 'archivo'}] ya descargados en ~/DaVinciSubtitles/broll_cache

Las palabras que dan B-roll son sustantivos concretos de una lista (es, en, pt, fr, de, it): «casa» → se busca «house». La API se puede cambiar con la
variable de entorno CINECAPTIONS_PEXELS_URL (las pruebas usan un servidor local). Las tomas son de Pexels (licencia gratuita, sin atribución obligatoria).
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

URL_API = 'https://api.pexels.com/videos/search'
CACHE = Path.home() / 'DaVinciSubtitles' / 'broll_cache'
CANTIDAD = {'pocos': (14.0, 3), 'normal': (9.0, 6), 'muchos': (6.0, 12)}        # (cada cuántos segundos como mínimo, tope)
DUR_BROLL_S = 2.2


def _plegar(t):
    t = unicodedata.normalize('NFKD', str(t or '').lower())
    return ''.join(c for c in t if not unicodedata.combining(c)).strip(" .,;:!?¡¿\"'()[]«»…")


def url_api():
    import os
    return os.environ.get('CINECAPTIONS_PEXELS_URL') or URL_API


def clave_guardada(op=None):
    return str((op or {}).get('pexels_key') or '').strip()


# cosas concretas que se pueden filmar -> la consulta en inglés (el banco busca en inglés). Palabra plegada (sin acentos, minúsculas).
SUSTANTIVOS = {}
for _q, _ps in {
    'house': 'casa casas house houses home hogar maison haus', 'kitchen': 'cocina kitchen cuisine kuche cucina', 'garden': 'jardin garden jardim garten giardino',
    'swimming pool': 'piscina pool alberca piscine schwimmbad', 'beach': 'playa beach praia plage strand spiaggia', 'ocean': 'mar oceano ocean sea mer meer',
    'mountain': 'montana montanas mountain mountains montanha montagne berg', 'forest': 'bosque forest floresta foret wald foresta', 'city skyline': 'ciudad city cidade ville stadt citta',
    'street': 'calle street rua rue strasse strada', 'building': 'edificio building predio batiment gebaude', 'office': 'oficina office escritorio bureau buro ufficio',
    'car driving': 'coche carro auto car automovil voiture wagen macchina', 'airplane': 'avion airplane plane aviao flugzeug aereo', 'boat': 'barco boat ship navio bateau schiff nave',
    'train': 'tren train trem zug treno', 'bicycle': 'bicicleta bicycle bike velo fahrrad', 'motorcycle': 'moto motocicleta motorcycle motorbike',
    'dog': 'perro perros dog dogs cachorro chien hund cane', 'cat': 'gato gatos cat cats gatto chat katze', 'horse': 'caballo horse cavalo cheval pferd cavallo', 'birds': 'pajaro pajaros bird birds passaro oiseau vogel',
    'food': 'comida food nourriture essen cibo', 'coffee': 'cafe coffee kaffee caffe', 'pizza': 'pizza', 'burger': 'hamburguesa burger hamburger', 'fruit': 'fruta frutas fruit fruits fruits obst frutta',
    'salad': 'ensalada salad salada salade salat insalata', 'wine': 'vino wine vinho vin wein', 'beer': 'cerveza beer cerveja biere bier birra',
    'money': 'dinero money plata dinheiro argent geld soldi billetes cash', 'watch': 'reloj watch relogio montre uhr orologio', 'smartphone': 'telefono celular movil smartphone phone telemovel telephone handy',
    'laptop': 'computadora ordenador laptop computer notebook computador ordinateur', 'camera': 'camara camera fotografia photography', 'microphone': 'microfono microphone podcast',
    'books': 'libro libros book books livro livre buch libri', 'clothes': 'ropa clothes clothing roupa vetements kleidung vestiti', 'shoes': 'zapatos shoes sapatos chaussures schuhe scarpe',
    'flowers': 'flor flores flower flowers fleurs blumen fiori', 'tree': 'arbol arboles tree trees arvore arbre baum albero', 'sunset': 'sol sun sunset atardecer pordosol soleil sonne sole',
    'rain': 'lluvia rain chuva pluie regen pioggia', 'snow': 'nieve snow neve neige schnee', 'fire': 'fuego fire fogo feu feuer fuoco', 'water': 'agua water eau wasser acqua',
    'night sky': 'noche night noite nuit nacht notte estrellas stars', 'family': 'familia family famille familie famiglia', 'children playing': 'ninos children kids criancas enfants kinder bambini',
    'baby': 'bebe baby neonato', 'gym workout': 'gimnasio gym workout ejercicio entrenamiento treino musculacao', 'football': 'futbol football soccer futebol',
    'basketball': 'baloncesto basketball basquete basket', 'guitar': 'guitarra guitar violao guitare gitarre chitarra', 'concert': 'concierto concert show konzert concerto',
    'party': 'fiesta party festa fete feier', 'wedding': 'boda wedding casamento mariage hochzeit matrimonio', 'travel': 'viaje viajar travel viagem voyage reise viaggio',
    'hotel': 'hotel resort', 'airport': 'aeropuerto airport aeroporto aeroport flughafen', 'shopping': 'tienda shop store shopping mercado market compras loja magasin geschaft',
    'meeting': 'reunion meeting reuniao besprechung riunione', 'team working': 'equipo team equipe mannschaft squadra', 'luxury villa': 'lujo luxury luxo luxe luxus lusso mansion',
    'real estate': 'inmueble inmobiliaria realty property imovel immobilier immobilie', 'swimming': 'nadar swimming natacion natation schwimmen nuoto',
    'cooking': 'cocinar cooking cozinhar cuisiner kochen cucinare', 'yoga': 'yoga', 'running': 'correr running corrida courir laufen correre', 'sky clouds': 'cielo sky ceu ciel himmel nubes clouds',
    'desert': 'desierto desert deserto wuste', 'waterfall': 'cascada waterfall cachoeira cascade wasserfall', 'lake': 'lago lake lac see', 'river': 'rio river fleuve fluss fiume',
    'road trip': 'carretera road estrada route', 'skyscraper': 'rascacielos skyscraper gratte-ciel wolkenkratzer grattacielo', 'bridge': 'puente bridge ponte pont brucke',
    'construction': 'construccion construction construcao chantier bau costruzione', 'doctor': 'doctor medico medecin arzt dottore hospital', 'school classroom': 'escuela school escola ecole schule scuola',
}.items():
    for _p in _ps.split():
        SUSTANTIVOS.setdefault(_p, _q)


def _consulta_de(palabra, idioma=None):
    """La consulta en inglés para una palabra que nombra algo concreto y filmable (de la lista), o None."""
    return SUSTANTIVOS.get(_plegar(palabra))


def elegir_momentos(palabras, duracion, idioma, cuanto='normal', margen_ini=2.0, margen_fin=3.0):
    """Las palabras que piden B-roll (separadas por el mínimo de `cuanto`, lejos del principio y del final) y su consulta. Una misma consulta no se repite."""
    sep, tope = CANTIDAD.get(cuanto, CANTIDAD['normal'])
    tope = max(1, min(tope, int(float(duracion or 0.0) // 10) + 1))
    vistos, salida = set(), []
    for p in palabras or []:
        w = _plegar(p.get('word') or p.get('text') or '')
        t = float(p.get('start', 0.0))
        if len(w) < 4 or not (margen_ini <= t <= max(margen_ini, float(duracion or 0.0) - margen_fin)):
            continue
        if salida and t - salida[-1]['ini'] < sep:
            continue
        q = _consulta_de(w, idioma)
        if not q or q in vistos:
            continue
        vistos.add(q)
        salida.append({'ini': round(max(0.0, t - 0.15), 3), 'dur': DUR_BROLL_S, 'palabra': w, 'consulta': q})
        if len(salida) >= tope:
            break
    return salida


def buscar(consulta, formato, clave, timeout=20):
    """La mejor toma de Pexels para esa consulta (vertical para 'v', horizontal para 'h'). None si no hay o falla la red/clave."""
    orient = {'v': 'portrait', 'h': 'landscape'}.get(formato, 'square')
    url = f"{url_api()}?query={urllib.parse.quote(consulta)}&orientation={orient}&per_page=10&size=medium"
    try:
        req = urllib.request.Request(url, headers={'Authorization': clave, 'User-Agent': 'CineCaptions'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            datos = json.loads(r.read().decode('utf-8'))
    except Exception:
        return None
    mejor, mejor_puntos = None, -1
    for v in datos.get('videos') or []:
        dur = float(v.get('duration') or 0)
        if dur < 3.0 or dur > 40.0:
            continue
        for f in v.get('video_files') or []:
            if str(f.get('file_type') or 'video/mp4') != 'video/mp4' or not f.get('link'):
                continue
            ancho = int(f.get('width') or 0)
            if ancho < 480 or ancho > 2200:
                continue
            puntos = 1000 - abs(ancho - (1080 if formato in ('v', 'h') else 1080))               # lo más cercano a 1080 px
            if puntos > mejor_puntos:
                mejor_puntos = puntos
                mejor = {'id': str(v.get('id')), 'url': f['link'], 'ancho': ancho, 'alto': int(f.get('height') or 0), 'dur': dur}
    return mejor


def preparar(momentos, formato, clave, al_estado=None):
    """Busca y descarga la toma de cada momento. Devuelve los eventos del plan (los que fallan se saltan: sin red o sin clave no hay B-roll y GO sigue igual)."""
    import descargas
    eventos = []
    CACHE.mkdir(parents=True, exist_ok=True)
    for m in momentos:
        if al_estado:
            try:
                al_estado(f"B-roll: {m['consulta']}…")
            except Exception:
                pass
        clip = buscar(m['consulta'], formato, clave)
        if not clip:
            continue
        destino = CACHE / f"{clip['id']}.mp4"
        try:
            if not destino.is_file() or destino.stat().st_size < 20000:
                descargas.descargar(clip['url'], destino, timeout=30)
        except Exception:
            continue
        if destino.is_file() and destino.stat().st_size > 20000:
            eventos.append({'tipo': 'broll', 'ini': m['ini'], 'dur': min(m['dur'], clip['dur'] - 0.2), 'asset': m['consulta'], 'archivo': str(destino), 'palabra': m['palabra']})
    return eventos
