# CineCaptions · By Cinema Productions
# 1_codigo/ortografia_es.py — ¿es español de verdad aunque el diccionario no la traiga? (v5.5.7)
"""
MEDIDO: el diccionario de pyspellchecker 0.9.1 para español trae casi solo LEMAS. No están «voy», «hay», «estoy», «tiene», «dijo», «quiero», «hablando»,
los plurales («gatos», «casas»), las palabras con pronombres pegados («enseñarte», «dímelo») ni «cómo» o «vídeo». La revisión las subrayaba como faltas y
la corrección automática las CAMBIABA por otra que suena igual: «hay» → «ahí», «Voy» → «Boy».

    conocida(palabra, corrector) -> True si es español aunque el diccionario no la tenga:
        1. lleva tilde y sin ella está en el diccionario («cómo»; al revés no: a «increible» le falta la tilde y se marca);
        2. es una forma irregular común (ser, estar, ir, haber, tener, hacer, poder, decir, ver, dar, saber, querer, poner, venir…);
        3. es una conjugación (regular o con cambio de raíz: e→ie, o→ue, e→i; y los cambios de letra c/qu, g/gu, z/c, zc, g/j) de un infinitivo del
           diccionario, o su futuro / condicional;
        4. plural, femenino, diminutivo, superlativo o adverbio en -mente de una palabra del diccionario;
        5. cualquiera de las anteriores con pronombres pegados («hacerlo», «dímelo», «diciéndote», «cuéntaselo»).

Peca de PRUDENTE: si una falta de verdad coincide con una forma posible, no se marca (antes de cambiar una palabra buena, mejor no tocar ninguna).
"""
import unicodedata

_IRREGULARES = set('''
soy eres es somos sois son era eras eramos erais eran fui fuiste fue fuimos fuisteis fueron sere seras sera seremos sereis seran seria serias seriamos
seriais serian sea seas seamos seais sean fuera fueras fueramos fuerais fueran fuese fueses fuesemos fueseis fuesen sed siendo sido
estoy estas esta estamos estais estan estuve estuviste estuvo estuvimos estuvisteis estuvieron estaba estabas estabamos estabais estaban este estes
estemos esteis esten estuviera estuvieras estuvieramos estuvierais estuvieran estuviese estuviesen estando estado estare estaras estara estaremos estareis
estaran estaria estarias estariamos estariais estarian
voy vas va vamos vais van iba ibas ibamos ibais iban vaya vayas vayamos vayais vayan ve id yendo ido ire iras ira iremos ireis iran iria irias iriamos
iriais irian vete idos
he has ha hemos habeis han hay habia habias habiamos habiais habian hube hubiste hubo hubimos hubisteis hubieron habre habras habra habremos habreis habran
habria habrias habriamos habriais habrian haya hayas hayamos hayais hayan hubiera hubieras hubieramos hubierais hubieran hubiese hubiesen habiendo habido
tengo tienes tiene tenemos teneis tienen tuve tuviste tuvo tuvimos tuvisteis tuvieron tendre tendras tendra tendremos tendreis tendran tendria tendrias
tendriamos tendriais tendrian tenga tengas tengamos tengais tengan tuviera tuvieras tuvieramos tuvierais tuvieran tuviese tuviesen ten teniendo tenido
hago haces hace hacemos haceis hacen hice hiciste hizo hicimos hicisteis hicieron hare haras hara haremos hareis haran haria harias hariamos hariais harian
haga hagas hagamos hagais hagan hiciera hicieras hicieramos hicierais hicieran hiciese haz haciendo hecho hecha hechos hechas
puedo puedes puede podemos podeis pueden pude pudiste pudo pudimos pudisteis pudieron podre podras podra podremos podreis podran podria podrias podriamos
podriais podrian pueda puedas podamos podais puedan pudiera pudieras pudieramos pudierais pudieran pudiese pudiendo podido
digo dices dice decimos decis dicen dije dijiste dijo dijimos dijisteis dijeron dire diras dira diremos direis diran diria dirias diriamos diriais dirian
diga digas digamos digais digan dijera dijeras dijeramos dijerais dijeran dijese di diciendo dicho dicha dichos dichas
veo ves ve vemos veis ven vi viste vio vimos visteis vieron veia veias veiamos veiais veian vea veas veamos veais vean viera vieras vieramos vierais vieran
viese visto vista vistos vistas viendo
doy das da damos dais dan di diste dio dimos disteis dieron de des demos deis den diera dieras dieramos dierais dieran diese dando dado dada dados dadas
se sabes sabe sabemos sabeis saben supe supiste supo supimos supisteis supieron sabre sabras sabra sabremos sabreis sabran sabria sabrias sabriamos sabriais
sabrian sepa sepas sepamos sepais sepan supiera supieras supieramos supierais supieran supiese sabiendo sabido
quiero quieres quiere queremos quereis quieren quise quisiste quiso quisimos quisisteis quisieron querre querras querra querremos querreis querran querria
querrias querriamos querriais querrian quiera quieras queramos querais quieran quisiera quisieras quisieramos quisierais quisieran quisiese queriendo querido
pongo pones pone ponemos poneis ponen puse pusiste puso pusimos pusisteis pusieron pondre pondras pondra pondremos pondreis pondran pondria pondrias
pondriamos pondriais pondrian ponga pongas pongamos pongais pongan pusiera pusieras pusieramos pusierais pusieran pusiese pon poniendo puesto puesta
puestos puestas
vengo vienes viene venimos venis vienen vine viniste vino vinimos vinisteis vinieron vendre vendras vendra vendremos vendreis vendran vendria vendrias
vendriamos vendriais vendrian venga vengas vengamos vengais vengan viniera vinieras vinieramos vinierais vinieran viniese ven viniendo venido
salgo sal saldre saldras saldra saldremos saldreis saldran saldria saldrias saldriamos saldriais saldrian salga salgas salgamos salgais salgan
traigo traje trajiste trajo trajimos trajisteis trajeron traiga traigas traigamos traigais traigan trajera trajeras trajeramos trajeran trajese trayendo
traido traida
oigo oyes oye oimos ois oyen oi oiste oyo oisteis oyeron oiga oigas oigamos oigais oigan oyera oyeras oyeran oyese oyendo oido oida
caigo caiga caigas caigamos caigan cayo cayeron cayera cayeras cayeran cayendo caido caida
valgo valga valgas valgan valdre valdras valdra valdremos valdran valdria valdrian
quepo cupe cupiste cupo cupimos cupieron quepa quepas quepan cabre cabra cabria cabrian cupiera
anduve anduviste anduvo anduvimos anduvieron anduviera anduvieran
conduzco conduje condujiste condujo condujimos condujeron conduzca conduzcan condujera
produzco produje produjo produjeron produzca traduzco traduje tradujo tradujeron traduzca introduzco introdujo reduzco redujo
muero mueres muere morimos mueren murio murieron muera mueras muramos mueran muriera murieran muriendo muerto muerta muertos muertas
duermo duermes duerme dormimos duermen durmio durmieron duerma duermas durmamos duerman durmiera durmiendo
roto rota rotos rotas escrito escrita escritos escritas abierto abierta abiertos abiertas vuelto vuelta vueltos vueltas resuelto resuelta devuelto
devuelta envuelto cubierto cubierta descubierto descubierta impreso impresa satisfecho satisfecha deshecho deshecha frito frita
ok vale okay wow video videos youtube instagram tiktok facebook whatsapp online app apps link links email web influencer youtuber podcast
'''.split())

# terminaciones (sin tildes) por conjugación: presente, pretérito, imperfecto, subjuntivos, imperativo, gerundio, participio, infinitivo
_TERM = {
    'ar': ['o', 'as', 'a', 'amos', 'ais', 'an', 'e', 'es', 'emos', 'eis', 'en', 'aste', 'asteis', 'aron', 'aba', 'abas', 'abamos', 'abais', 'aban',
           'ara', 'aras', 'aramos', 'arais', 'aran', 'ase', 'ases', 'asemos', 'aseis', 'asen', 'are', 'ares', 'aremos', 'areis', 'aren',
           'ando', 'ado', 'ada', 'ados', 'adas', 'ad', 'ar'],
    'er': ['o', 'es', 'e', 'emos', 'eis', 'en', 'a', 'as', 'amos', 'ais', 'an', 'i', 'iste', 'io', 'imos', 'isteis', 'ieron', 'ia', 'ias', 'iamos',
           'iais', 'ian', 'iera', 'ieras', 'ieramos', 'ierais', 'ieran', 'iese', 'ieses', 'iesemos', 'ieseis', 'iesen', 'iere', 'ieren',
           'iendo', 'ido', 'ida', 'idos', 'idas', 'ed', 'er', 'yo', 'yeron', 'yera', 'yeras', 'yeran', 'yese', 'yendo'],
    'ir': ['o', 'es', 'e', 'imos', 'is', 'en', 'a', 'as', 'amos', 'ais', 'an', 'i', 'iste', 'io', 'isteis', 'ieron', 'ia', 'ias', 'iamos',
           'iais', 'ian', 'iera', 'ieras', 'ieramos', 'ierais', 'ieran', 'iese', 'ieses', 'iesemos', 'ieseis', 'iesen', 'iere', 'ieren',
           'iendo', 'ido', 'ida', 'idos', 'idas', 'id', 'ir', 'yo', 'yeron', 'yera', 'yeras', 'yeran', 'yese', 'yendo'],
}
_FUT = ['e', 'as', 'a', 'emos', 'eis', 'an', 'ia', 'ias', 'iamos', 'iais', 'ian']
_CLITICOS = sorted(['me', 'te', 'se', 'nos', 'os', 'lo', 'la', 'los', 'las', 'le', 'les'], key=len, reverse=True)
_NOMINAL = [('es', ''), ('s', ''), ('a', 'o'), ('as', 'o'), ('as', 'a'), ('os', 'o'), ('ita', 'a'), ('ito', 'o'), ('itas', 'a'), ('itos', 'o'),
            ('ita', 'o'), ('itos', ''), ('ito', ''), ('illo', 'o'), ('illa', 'a'), ('isimo', 'o'), ('isima', 'o'), ('isimos', 'o'), ('isimas', 'o'),
            ('ces', 'z'), ('cita', 'z'), ('cito', ''), ('quito', 'co'), ('quita', 'ca'), ('guito', 'go'), ('mente', ''), ('mente', 'o')]
_CACHE = {}


def sin_tildes(t):
    """«Cómo» → «como», «pingüino» → «pinguino» (la ñ se queda)."""
    out = [ch for ch in unicodedata.normalize('NFD', str(t)) if unicodedata.category(ch) != 'Mn' or ch == '̃']
    return unicodedata.normalize('NFC', ''.join(out)).lower()


def _indices(corrector):
    """(palabras del diccionario sin tildes, infinitivos) — una vez por diccionario."""
    clave = id(corrector)
    if clave not in _CACHE:
        try:
            todas = {sin_tildes(w) for w in corrector.word_frequency.dictionary.keys()}
        except Exception:
            todas = set()
        inf = {w for w in todas if len(w) >= 3 and w.endswith(('ar', 'er', 'ir'))} | {'ir', 'oir', 'reir', 'freir', 'sonreir'}
        _CACHE.clear()
        _CACHE[clave] = (todas, inf)
    return _CACHE[clave]


def _raices(raiz):
    """La raíz tal cual y deshaciendo los cambios de la conjugación: e→ie / o→ue / u→ue (jugar) / e→i / o→u y las letras c/qu, g/gu, z/c, zc, g/j,
    la g de «tengo / salgo» y la ig de «traigo / oigo»."""
    vistas = {raiz}
    frontera = [raiz]
    for _ in range(2):
        nuevas = []
        for r in frontera:
            cand = []
            for de, a in (('qu', 'c'), ('gu', 'g'), ('c', 'z'), ('zc', 'c'), ('j', 'g'), ('ig', ''), ('g', ''), ('y', ''), ('u', '')):
                if r.endswith(de) and len(r) > len(de):
                    cand.append(r[:-len(de)] + a)
            for de, a in (('ie', 'e'), ('ue', 'o'), ('ue', 'u'), ('i', 'e'), ('u', 'o')):
                k = r.rfind(de)
                if k > 0 or (k == 0 and len(r) > len(de)):
                    cand.append(r[:k] + a + r[k + len(de):])
            for c in cand:
                if c and c not in vistas:
                    vistas.add(c)
                    nuevas.append(c)
        frontera = nuevas
    return vistas


def _verbal(w, inf):
    if w in _IRREGULARES or w in inf:
        return True
    for suf in _FUT:                                   # futuro y condicional: el infinitivo entero + terminación
        if w.endswith(suf) and w[:-len(suf)] in inf:
            return True
    for clase, terms in _TERM.items():
        for t in terms:
            if w.endswith(t) and len(w) > len(t):
                for r in _raices(w[:-len(t)]):
                    if r + clase in inf:
                        return True
    return False


def _nominal(w, todas):
    for de, a in _NOMINAL:
        if w.endswith(de) and len(w) - len(de) >= 2 and (w[:-len(de)] + a) in todas:
            return True
    return False


def conocida(palabra, corrector):
    """True si `palabra` es español aunque el diccionario no la traiga (ver arriba). Nunca lanza."""
    try:
        w0 = str(palabra).strip().lower()
        w = sin_tildes(w0)
        if not w:
            return True
        todas, inf = _indices(corrector)
        if w in _IRREGULARES:
            return True
        if w in todas:                                  # «cómo» (el diccionario solo trae «como») sí; «increible» NO: le falta la tilde y la corrección se la pone
            return w != w0
        if w0 != w and sin_tildes(w0) == w and w0 in todas:
            return True
        if _verbal(w, inf) or _nominal(w, todas):
            return True
        resto = w                                       # pronombres pegados: hasta dos («cuéntaselo», «dímelo», «hacerlo», «diciéndote»)
        for _ in range(2):
            c = next((c for c in _CLITICOS if resto.endswith(c) and len(resto) - len(c) >= 2), None)
            if c is None:
                break
            resto = resto[:-len(c)]
            if resto in inf or _verbal(resto, inf):
                return True
        return False
    except Exception:
        return True


# erratas típicas que el diccionario de lemas no sabe arreglar (la buena es una forma conjugada o son dos palabras). Solo las INEQUÍVOCAS:
# nada de «haber/a ver», «hay/ahí/ay», «echo/hecho», «valla/vaya», que dependen de la frase (eso lo hace la IA de texto).
ERRATAS = {
    'kiero': 'quiero', 'kieres': 'quieres', 'kiere': 'quiere', 'nesecito': 'necesito', 'nesesito': 'necesito', 'nesecitas': 'necesitas',
    'nesecita': 'necesita', 'nesecitamos': 'necesitamos', 'ubo': 'hubo', 'ubiera': 'hubiera', 'abia': 'había', 'abian': 'habían', 'iva': 'iba',
    'ivan': 'iban', 'ivamos': 'íbamos', 'hiba': 'iba', 'esque': 'es que', 'osea': 'o sea', 'enserio': 'en serio', 'porfavor': 'por favor',
    'aveces': 'a veces', 'apesar': 'a pesar', 'atraves': 'a través', 'atravez': 'a través', 'haci': 'así', 'dijistes': 'dijiste',
    'fuistes': 'fuiste', 'hicistes': 'hiciste', 'tuvistes': 'tuviste', 'pudistes': 'pudiste', 'haiga': 'haya', 'naiden': 'nadie',
    'nadien': 'nadie', 'orita': 'ahorita', 'ahy': 'ahí', 'despues': 'después', 'tambien': 'también', 'porque': 'porque', 'encambio': 'en cambio',
    'derrepente': 'de repente', 'almenos': 'al menos', 'talvez': 'tal vez', 'quizas': 'quizás', 'aun': 'aun', 'conque': 'conque',
}
