# CineCaptions · By Cinema Productions
# 1_codigo/monedas.py — qué moneda se NOMBRA al hablar de dinero (₦ naira, € euros, Q quetzales…): el precio de las escenas ya no es siempre «$».
"""
monedas.py
----------
v5.5.8 (pedido: «muestra una moneda diferente cuando digo naira»): las escenas de precio del Tema 5/6 (y sus acompañantes) ponían «$» a todo lo
que no traía el signo escrito. Ahora el signo sale de la moneda que se dice cerca de la cifra (la palabra más cercana gana) o del signo
escrito; «$» solo si se habla de dinero sin nombrar ninguna.

    signo(palabras, escrito='')   el signo de la moneda nombrada en `palabras` (en orden de cercanía) o el `escrito`; '' si ninguna
    PALABRAS                      todas las palabras de moneda (para saber que se habla de dinero)
    SIGNOS                        los signos que se reconocen escritos pegados a la cifra («₦80», «€25»)
Las palabras ambiguas («won» = ganó, «colón», «franco», «real» en español, «córdoba») solo cuentan en plural o con su código.
"""
import re
import unicodedata

MONEDAS = {
    'dolar': '$', 'dolares': '$', 'dollar': '$', 'dollars': '$', 'bucks': '$', 'usd': '$', 'pesos': '$', 'mxn': '$', 'cop': '$',
    'euro': '€', 'euros': '€', 'eur': '€',
    'libra': '£', 'libras': '£', 'pound': '£', 'pounds': '£', 'quid': '£', 'gbp': '£',
    'naira': '₦', 'nairas': '₦', 'ngn': '₦',
    'quetzal': 'Q', 'quetzales': 'Q', 'gtq': 'Q',
    'soles': 'S/',
    'reais': 'R$', 'brl': 'R$',
    'yen': '¥', 'yenes': '¥', 'jpy': '¥', 'yuan': '¥', 'yuanes': '¥', 'renminbi': '¥', 'rmb': '¥', 'cny': '¥',
    'rupia': '₹', 'rupias': '₹', 'rupee': '₹', 'rupees': '₹', 'inr': '₹',
    'wones': '₩', 'krw': '₩',
    'lira': '₺', 'liras': '₺', 'try': None,
    'cedi': '₵', 'cedis': '₵', 'ghs': '₵',
    'colones': '₡', 'crc': '₡',
    'guaranies': '₲', 'pyg': '₲',
    'lempira': 'L', 'lempiras': 'L', 'hnl': 'L',
    'cordobas': 'C$', 'nio': 'C$',
    'bolivares': 'Bs', 'bolivianos': 'Bs',
    'rand': 'R', 'rands': 'R', 'zar': 'R',
    'shilling': 'KSh', 'shillings': 'KSh', 'chelines': 'KSh', 'kes': 'KSh',
    'francos': 'Fr', 'franc': 'Fr', 'francs': 'Fr', 'chf': 'Fr',
    'bitcoin': '₿', 'bitcoins': '₿', 'btc': '₿',
}
MONEDAS = {k: v for k, v in MONEDAS.items() if v}
# también son peso, monedas viejas o calzado («perdí 20 libras», «20 pounds», «soles» de zapato): eligen el signo si YA se habla de dinero,
# pero solas no hacen de una cifra un precio
AMBIGUAS = frozenset({'libra', 'libras', 'pound', 'pounds', 'lira', 'liras', 'rand', 'rands', 'franc', 'francs', 'soles', 'quid', 'bucks'})
PALABRAS = frozenset(MONEDAS) - AMBIGUAS
SIGNOS = ('R$', 'S/', 'C$', 'KSh', 'Bs', '$', '€', '£', '¥', '₦', '₹', '₩', '₺', '₱', '₡', '₲', '₵', '₿')
RE_SIGNO = '|'.join(re.escape(s) for s in SIGNOS)


def _plegar(w):
    w = unicodedata.normalize('NFKD', str(w).lower())
    return re.sub(r'[^a-z]', '', ''.join(c for c in w if not unicodedata.combining(c)))


def signo(palabras, escrito=''):
    """El signo de la primera moneda nombrada en `palabras` (más cercana primero); si no hay, el `escrito` si es un signo conocido; si no, ''."""
    for w in palabras or ():
        s = MONEDAS.get(_plegar(w))
        if s:
            return s
    escrito = str(escrito or '').strip()
    return escrito if escrito in SIGNOS else ''
