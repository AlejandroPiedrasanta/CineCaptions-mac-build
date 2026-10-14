# CineCaptions · By Cinema Productions
# 1_codigo/catalogo_ia.py — v5.5.2: EL CATÁLOGO ÚNICO de todo lo que la edición puede poner en un video — motion graphics (antiguos y nuevos),
# tomas de B-roll (de stock y animadas) y captions (temas, modos y ganchos) — armado a partir del propio código (nada copiado a mano: si se añade
# una plantilla, una variante o un tema, aparece aquí solo). Sirve para dos cosas:
#   · la lista que lee una persona: DOCUMENTACION/catalogo_motions.md (python 1_codigo/catalogo_ia.py)
#   · lo que lee la IA local: 2_recursos/edicion_pro/catalogo_ia.json y `menu_plantillas(genero)` (las plantillas de la biblioteca que la IA
#     puede elegir por su id en el director de motions, edicion_pro_kit7 / ia_texto.motions)
"""
    construir() -> {'motions': [...], 'broll': [...], 'captions': [...]}    cada entrada: {'id', 'grupo', 'nombre', 'que', 'cuando', 'editable', ...}
    menu_plantillas(genero) -> [(id, descripción corta)]                  exportar() -> (ruta_md, ruta_json)
"""
from __future__ import annotations

import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAMAS_DE_GENERO = {'boda': ('bodas', 'saludos'), 'xv': ('eventos', 'saludos'), 'bts': ('fotografia', 'saludos'), 'inmobiliaria': ('saludos',),
                   'restaurante': ('saludos',), 'general': ('saludos', 'fotografia'), 'auto': ('saludos', 'fotografia')}

# lo que no está en una tabla del código (piezas cuyo «cuándo» vive en la lógica de los planificadores), descrito una vez aquí
T5_ESCENAS = {
    'lista': 'se enumeran 2–5 cosas', 'fichas': 'se nombran marcas, apps, lugares o personas', 'comparacion': 'dos opciones opuestas (antes/después)',
    'pregunta': 'quien habla le pregunta al público (con opciones)', 'cifra': 'se dice un número', 'precio': 'una cantidad de dinero',
    'grafica': 'algo que crece', 'reloj': 'un tiempo («en 20 minutos»)', 'avatares': 'clientes, gente, seguidores', 'calendario': 'un día o una fecha',
    'estado': 'un error o algo correcto (✓/✗)', 'muestras': 'se nombran colores', 'app': 'vídeos, contenido, editar, redes', 'ojo': 'lo visual, la atención',
    'icono': 'un objeto con su icono 3D',
}
T5_ACOMP = {
    'lugar': 'un país o ciudad (con su bandera)', 'saludo': '«¡Hola amigos!»', 'redes': 'seguir, comentar, compartir', 'cifra': 'un número',
    'dinero': 'una cantidad de dinero', 'tiempo': 'un tiempo', 'barra': 'un progreso / porcentaje', 'emoji': 'el emoji 3D del concepto o del tema del video',
    'sticker': 'un sticker del concepto',
}
T5_MAGIC = {
    'foco': ('Fondo en blanco y negro con la persona a color', 'algo fuerte o importante (la persona recortada con Magic Mask)'),
    'orbita': ('Iconos girando alrededor de la cabeza', 'el gancho: los conceptos del video pasan por detrás y por delante'),
    'sticker': ('Sticker congelado de la persona', 'el gancho: la persona recortada como pegatina con borde blanco'),
    'sombra': ('Sombra de la persona sobre la palabra de detrás', 'la palabra clave detrás de la persona'),
    'final': ('Pantalla final con avatar y botón', 'cuando pide que le sigan'),
    'tarjeta_mapa': ('Tarjeta del país (mapa)', 'se nombra un país'), 'tarjeta_grafica': ('Tarjeta con la gráfica del %', 'se dice un porcentaje'),
    'tarjeta_tachado': ('La frase tachada', '«no es X» / lo que NO hay que hacer'), 'tarjeta_lista': ('La lista que se va marcando', 'se enumeran cosas'),
    'zoom': ('Transición con zoom en los cortes', 'en los cortes del video'), 'dividida': ('Pantalla dividida (papel arriba, persona abajo)', 'una escena larga'),
}
T6_EDITORIAL = {
    'visor': ('Visor de cámara sobre la cara', 'cuando habla de grabar, la cámara, el contenido'),
    'buscar': ('Barra de búsqueda que se escribe', 'cuando pide comentar una palabra'), 'perfil': ('Perfil con seguidores que cuentan', 'seguidores, comunidad, «mil»'),
    'equipo': ('Píldora del equipo (3 caras)', 'el equipo, «nosotros»'), 'escena': ('Escena melocotón con tarjetas blancas', 'frases largas y clave'),
}
PRO_GENERAL = {
    'ubicacion': ('Mapa + bandera del país', 'se nombra un país o ciudad'), 'fondo': ('Escena con el fondo sustituido (persona delante de un fondo animado)', 'una idea larga'),
    'punch': ('Punch-in (zoom de cámara)', 'énfasis en una frase'), 'gris': ('Tramo en gris', 'contraste dramático'),
}
CAPTION_MODOS = {
    'normal': 'el caption palabra a palabra en el centro-abajo', 'detras': 'la palabra clave grande DETRÁS de la persona (Magic Mask) — gancho',
    'editorial': 'serif fina con la frase clave grande en lima o blanco (Tema 6)', 'arriba': 'sobre el sticker o la pantalla final, arriba',
    'escena': 'en tinta oscura dentro de la escena de papel / melocotón',
}
GANCHOS = {
    'kinetic': ('Títulos de gancho (Kinetic)', 'héroe enorme + cinta + anillo animado y golpe de sonido; recetas: {recetas}'),
    'detras': ('Caption detrás de la persona', 'la palabra fuerte del gancho detrás de la cabeza (Temas 5/6)'),
    'pasos_gancho': ('Indicador 1–2–3 en rojo', '«te doy 3 cosas» en los primeros segundos (Tema 5)'),
    'orbita': ('Órbita de iconos', 'los conceptos del video girando alrededor de la cabeza'),
    'sticker': ('Sticker congelado', 'la persona como pegatina en el gancho'),
    'titulo_neon': ('Título neón con número', 'TituloNeonK: «8 LECCIONES…» en el gancho'),
    'rueda': ('Rueda de hooks', 'RuedaK: «CONVIERTE 1 IDEA / EN 7 HOOKS»'),
    'misterio': ('Misterio numerado', 'MisterioK: «3 secretos» sin revelar'),
    'sonido': ('Riser + golpe del gancho', 'el riser de la intro y el golpe bajo la voz del video'),
}


def construir():
    import edicion_pro_catalogo as PC
    import edicion_pro_kit7 as K7
    motions, broll, captions = [], [], []

    # --- motions: el kit de la skill (nuevo, editable: variantes + colores del video + textos e iconos de la IA)
    for fam, (cuando, datos) in K7.MOTIONS.items():
        comp = K7.COMP[fam]
        motions.append({'id': f'kit_{fam}', 'grupo': 'Kit de la skill (v5.5.2)', 'nombre': comp, 'que': fam, 'cuando': cuando, 'editable': datos,
                        'variantes': K7.VARIANTES.get(comp, []), 'colores': 'los del video (o tema neón / rojo / azul / oro / editorial)'})
    # --- motions: la biblioteca de 100 plantillas (por frases)
    for p in PC.PLANTILLAS:
        pr = p['props']
        texto = pr.get('titulo') or pr.get('texto') or pr.get('pregunta') or pr.get('nombre') or ''
        motions.append({'id': p['id'], 'grupo': f"Biblioteca · {p['rama']}", 'nombre': p['comp'], 'que': texto, 'cuando': ', '.join(p['frases'][:3]) or '(lo elige el plan)',
                        'editable': ', '.join(k for k in pr if k not in ('sticker',)), 'estilo': pr.get('estilo', '')})
    # --- motions: las piezas PRO (OGraf) de los Temas 1–4
    try:
        import edicion_pro_ograf as OG
        for k, esq in OG.ESQUEMAS.items():
            motions.append({'id': f'ograf_{k}', 'grupo': 'Piezas PRO (Temas 1–4)', 'nombre': esq.get('nombre', k), 'que': k,
                            'cuando': 'el planificador PRO (gancho, cifras, listas, nombres, CTA, escenas)', 'editable': ', '.join(n for n, _ in esq.get('props') or [])})
    except Exception:
        pass
    for k, (n, c) in PRO_GENERAL.items():
        motions.append({'id': f'pro_{k}', 'grupo': 'Piezas PRO (Temas 1–4)', 'nombre': n, 'que': k, 'cuando': c, 'editable': ''})
    # --- motions: Tema 5 (skill «Edit VIRAL Reels with AI») y Tema 6 (editorial)
    motions.append({'id': 't5_pasos', 'grupo': 'Tema 5', 'nombre': 'PasosT5', 'que': 'indicador 1–2–3', 'cuando': 'se anuncian N cosas / el paso en que va', 'editable': 'n, actual'})
    motions.append({'id': 't5_deslizador', 'grupo': 'Tema 5', 'nombre': 'DeslizadorT5', 'que': '«Principiante ●── Profesional»', 'cuando': '«de A a B»', 'editable': 'a, b'})
    for k, c in T5_ESCENAS.items():
        motions.append({'id': f't5_escena_{k}', 'grupo': 'Tema 5 · escenas (la IA las dirige)', 'nombre': 'EscenaT5', 'que': k, 'cuando': c, 'editable': 'datos de lo que se dice'})
    for k, c in T5_ACOMP.items():
        motions.append({'id': f't5_acomp_{k}', 'grupo': 'Tema 5/6 · acompañantes bajo el caption', 'nombre': 'AcompananteT5', 'que': k, 'cuando': c, 'editable': 'texto, icono'})
    for k, (n, c) in T5_MAGIC.items():
        motions.append({'id': f't5_mm_{k}', 'grupo': 'Tema 5 · Magic Mask y efectos', 'nombre': n, 'que': k, 'cuando': c, 'editable': ''})
    for k, (n, c) in T6_EDITORIAL.items():
        motions.append({'id': f't6_{k}', 'grupo': 'Tema 6 · editorial', 'nombre': n, 'que': k, 'cuando': c, 'editable': 'texto, valor'})

    # --- B-roll
    broll.append({'id': 'broll_stock', 'grupo': 'B-roll de stock', 'nombre': 'Tomas de Pexels', 'que': 'video real de lo que se nombra',
                  'cuando': 'palabras que nombran cosas filmables (necesita tu clave gratuita de Pexels)', 'editable': 'cuántas: pocos / normal / muchos'})
    for k, (n, c) in {'escena_papel': ('Escena de papel (completa o media pantalla)', 'Tema 5: cifras, listas, iconos 3D, comparaciones'),
                      'escena_melocoton': ('Escena melocotón', 'Tema 6'), 'fondo_sustituido': ('Fondo animado detrás de la persona', 'Temas 1–4 PRO'),
                      'concepto': ('Tarjeta de concepto (ConceptoK)', '«éxito», «fracaso», «proceso», «equipo»'),
                      'ubicacion': ('Mapa + bandera', 'un país o ciudad'), 'sticker': ('Sticker congelado', 'gancho'), 'final': ('Pantalla final', 'cierre')}.items():
        broll.append({'id': f'broll_{k}', 'grupo': 'B-roll animado (motion)', 'nombre': n, 'que': k, 'cuando': c, 'editable': 'textos, colores'})

    # --- captions: temas, modos y ganchos
    try:
        import plantillas
        info = plantillas.TEMAS_INFO
    except Exception:
        info = {}
    for nombre, (titulo, desc) in info.items():
        captions.append({'id': f'tema_{nombre}', 'grupo': 'Temas de captions', 'nombre': titulo, 'que': nombre, 'cuando': desc, 'editable': 'colores, posición, emojis'})
    for nombre in ('Viral Superior', 'Viral Inferior'):
        captions.append({'id': 'pack_' + nombre.lower().replace(' ', '_'), 'grupo': 'Packs de captions', 'nombre': nombre, 'que': nombre,
                         'cuando': 'variantes del VIRAL (arriba / abajo)', 'editable': 'colores, posición'})
    for k, c in CAPTION_MODOS.items():
        captions.append({'id': f'modo_{k}', 'grupo': 'Modos de caption (PRO)', 'nombre': k, 'que': k, 'cuando': c, 'editable': ''})
    try:
        import kinetic_planificador as KP
        recetas = ', '.join(r['nombre'] for r in KP.RECETAS) if hasattr(KP, 'RECETAS') else 'lima, magenta, amarillo, serif'
    except Exception:
        recetas = 'lima, magenta, amarillo, serif'
    for k, (n, c) in GANCHOS.items():
        captions.append({'id': f'gancho_{k}', 'grupo': 'Captions y gráficos de GANCHO (hook)', 'nombre': n, 'que': k, 'cuando': c.format(recetas=recetas), 'editable': ''})
    return {'motions': motions, 'broll': broll, 'captions': captions}


def menu_plantillas(genero='general', maximo=40):
    """Las plantillas de la biblioteca que la IA puede elegir para ESTE tipo de video: [(id, «Título · cuándo»)]. Solo las ramas que le tocan."""
    import edicion_pro_catalogo as PC
    ramas = RAMAS_DE_GENERO.get(genero or 'general', RAMAS_DE_GENERO['general'])
    out = []
    for p in PC.PLANTILLAS:
        if p['rama'] in ramas:
            pr = p['props']
            texto = pr.get('titulo') or pr.get('texto') or pr.get('pregunta') or p['comp']
            out.append((p['id'], f"{texto} · {', '.join(p['frases'][:2]) or 'general'}"))
    return out[:maximo]


def exportar():
    datos = construir()
    raiz = AQUI.parent
    rj = raiz / '2_recursos' / 'edicion_pro' / 'catalogo_ia.json'
    rj.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding='utf-8')
    lineas = ['# Catálogo de la edición — motions, B-roll y captions', '',
              'Generado desde el código (`python 1_codigo/catalogo_ia.py`). La IA local elige de aquí (el kit y las plantillas de la biblioteca por su id; '
              'el Tema 5 tiene su propio director de escenas) y todo lo que pone sigue la regla oficial: **ni caras ni captions tapados**.', '']
    for seccion, titulo in (('motions', 'Motion graphics'), ('broll', 'B-roll'), ('captions', 'Captions y ganchos')):
        items = datos[seccion]
        lineas += [f'## {titulo} ({len(items)})', '']
        grupo = None
        for it in items:
            if it['grupo'] != grupo:
                grupo = it['grupo']
                n = sum(1 for x in items if x['grupo'] == grupo)
                lineas += ['', f'### {grupo} ({n})', '', '| id | qué | cuándo | editable |', '|---|---|---|---|']
            extra = (' · variantes: ' + ', '.join(it['variantes'])) if it.get('variantes') else ''
            celda = lambda s: str(s or '').replace('|', '/').replace('\n', ' ')
            lineas.append(f"| `{it['id']}` | {celda(it['nombre'])} — {celda(it['que'])} | {celda(it['cuando'])} | {celda(it['editable'])}{celda(extra)} |")
        lineas.append('')
    rm = raiz / 'DOCUMENTACION' / 'catalogo_motions.md'
    rm.write_text('\n'.join(lineas), encoding='utf-8')
    return rm, rj


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(AQUI))
    md, js = exportar()
    d = json.loads(js.read_text(encoding='utf-8'))
    print(md, js, {k: len(v) for k, v in d.items()})
