# CineCaptions · By Cinema Productions
# 1_codigo/sentimiento.py — si una frase suena positiva o negativa (listas de palabras, sin modelos), para el sonido de los emojis (v5.4.8).
"""
    valencia(texto)  -> +n (positivo) | -n (negativo) | 0

Cuenta palabras de una lista corta por idioma (es, en, pt, fr, de, it); una negación justo antes («no», «not», «nunca»…) le da la vuelta a la palabra. Solo para decidir entre un
sonido «acierto» y un sonido «error»: no pretende ser un análisis de sentimiento de verdad.
"""
from __future__ import annotations

import re
import unicodedata

_POS = """
bueno buena buenos buenas genial excelente increible increibles mejor mejores perfecto perfecta feliz felices amor amo encanta encantan gracias exito ganar ganamos ganador gana
bien bonito bonita hermoso hermosa lindo linda divertido fantastico maravilloso espectacular gratis nuevo nueva facil rapido seguro confianza premio logro logrado ok si claro vamos
good great awesome amazing best perfect happy love like thanks thank win won winner success easy fast safe free new beautiful nice cool fun wonderful fantastic yes yeah
bom boa otimo incrivel melhor feliz amo obrigado sucesso ganhar lindo facil rapido seguro gratis novo
bon bonne super genial meilleur heureux aime merci succes gagner facile rapide gratuit nouveau beau
gut toll super perfekt gluck gluecklich liebe danke erfolg gewinnen einfach schnell kostenlos neu schon
buono ottimo fantastico migliore felice amo grazie successo vincere facile veloce gratis nuovo bello
""".split()
_NEG = """
malo mala malos malas terrible horrible peor peores problema problemas error errores falla fallo perder perdi perdimos pierdes triste odio odiar miedo peligro peligroso dolor caro
cuidado nunca jamas imposible dificil fracaso fraude estafa mentira culpa tarde roto rota feo fea cansado cansada enojo enojado grave riesgo muerte matar caer cayo crisis deuda
bad terrible awful worst problem problems error errors fail failure lose lost sad hate fear danger dangerous pain expensive careful never impossible hard difficult scam fraud lie
fault late broken ugly tired angry risk death kill fall crisis debt wrong stop avoid warning
ruim pessimo problema erro falha perder triste odio medo perigo dor caro cuidado nunca impossivel dificil golpe mentira
mauvais terrible pire probleme erreur echec perdre triste haine peur danger douleur cher attention jamais impossible difficile arnaque mensonge
schlecht schrecklich schlimmste problem fehler verlieren traurig hass angst gefahr schmerz teuer vorsicht niemals unmoglich schwer betrug luge
cattivo terribile peggiore problema errore fallire perdere triste odio paura pericolo dolore caro attenzione mai impossibile difficile truffa bugia
""".split()
_NEGACION = {'no', 'not', 'nunca', 'jamas', 'never', 'sin', 'nem', 'ne', 'pas', 'kein', 'nicht', 'mai', 'non', "don't", 'dont', "isn't", 'isnt', "can't", 'cant'}


def _plegar(t):
    t = unicodedata.normalize('NFKD', str(t or '').lower())
    return ''.join(c for c in t if not unicodedata.combining(c))


_NEGACION = {_plegar(w) for w in _NEGACION}
_POS_S = {_plegar(w) for w in _POS} - _NEGACION
_NEG_S = {_plegar(w) for w in _NEG} - _NEGACION - {'jamais', 'niemals', 'mai'}        # «nunca», «never»… niegan, no puntúan por sí solas


def valencia(texto):
    """Positivo (> 0), negativo (< 0) o 0 para `texto` (una frase o las palabras de un bloque)."""
    palabras = re.findall(r"[\w']+", _plegar(texto))
    puntos = 0
    for i, w in enumerate(palabras):
        v = 1 if w in _POS_S else (-1 if w in _NEG_S else 0)
        if not v:
            continue
        if any(x in _NEGACION for x in palabras[max(0, i - 2):i]):                # «no es bueno», «not very good»: la negación puede ir una palabra antes
            v = -v
        puntos += v
    return puntos
