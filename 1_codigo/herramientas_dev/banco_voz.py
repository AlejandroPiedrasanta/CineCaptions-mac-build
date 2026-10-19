# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/banco_voz.py — v5.5.17: mide la transcripción (WER y la lista de errores) contra un texto CORRECTO, para comparar
# motores, modelos y el vocabulario con números. SOLO desarrollo.
"""
    python 1_codigo/herramientas_dev/banco_voz.py <video | palabras.json> <referencia.txt> [--contexto "Xela, FIFA"] [--sin-vocabulario]
                                                  [--idioma es] [--modelo large-v3-turbo]

Con un video transcribe por el camino del programa (subtitle_transcriber: Qwen3-ASR o Whisper según las preferencias); con un .json usa esas
palabras ({'palabras': [...]}, la caché de voz o el json del motor). Después aplica lo que hace GO antes de la IA de texto (vocabulario.aplicar
y vocabulario.unificar; con --sin-vocabulario, solo unificar) y mide antes y después. El WER compara palabras sin signos ni mayúsculas, CON
tildes (una tilde mal puesta es una falta). Referencias en herramientas_dev/banco_voz/. Para el motor real desde Claude: LOCALAPPDATA a la ruta
//localhost/c$/… (ver la memoria appdata-virtualizada-claude).
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def normalizar(texto):
    t = re.sub(r'(\d)\s*%', r'\1 %', str(texto).lower())                 # («100%» = «100 %»: formato, no un error)
    return [w for w in re.sub(r"[¿¡.,;:!?\"'«»()\[\]…“”]", ' ', t).split() if w]


def alinear(ref, hip):
    """Distancia de edición por palabras con la lista de errores [(tipo, ref, hip)]."""
    n, m = len(ref), len(hip)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (ref[i - 1] != hip[j - 1]))
    errores, i, j = [], n, m
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hip[j - 1]):
            if ref[i - 1] != hip[j - 1]:
                errores.append(('cambio', ref[i - 1], hip[j - 1]))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            errores.append(('falta', ref[i - 1], ''))
            i -= 1
        else:
            errores.append(('sobra', '', hip[j - 1]))
            j -= 1
    return d[n][m], errores[::-1]


def medir(nombre, palabras, ref):
    hip = normalizar(' '.join(str(p.get('word', '')) for p in palabras))
    dist, errores = alinear(ref, hip)
    print(f'{nombre:28s} WER {100.0 * dist / max(1, len(ref)):5.1f} %  ({dist} de {len(ref)})  ' +
          ', '.join(f'{r or "∅"}→{h or "∅"}' for _t, r, h in errores))
    return dist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('fuente')
    ap.add_argument('referencia')
    ap.add_argument('--contexto', default=None)
    ap.add_argument('--sin-vocabulario', action='store_true')
    ap.add_argument('--ia', action='store_true', help='también la IA de texto de GO (marcar_todo: corrección + ortografía)')
    ap.add_argument('--idioma', default='es')
    ap.add_argument('--modelo', default='large-v3-turbo')
    a = ap.parse_args()
    import vocabulario
    ref = normalizar(Path(a.referencia).read_text(encoding='utf-8'))
    f = Path(a.fuente)
    if f.suffix.lower() == '.json':
        d = json.loads(f.read_text(encoding='utf-8'))
        palabras = d.get('palabras') if isinstance(d, dict) else d
        etiqueta = f.stem
    else:
        import subtitle_transcriber as st
        contexto = vocabulario.contexto() if a.contexto is None else a.contexto
        palabras = st.transcribe(str(f), a.idioma, a.modelo, contexto=contexto)
        etiqueta = 'voz' + (' + contexto' if contexto else '')
    medir(etiqueta, palabras, ref)
    if a.sin_vocabulario:
        u, n = vocabulario.unificar(palabras)
        medir(f'+ unificar ({n})', u, ref)
    else:
        v, n1 = vocabulario.aplicar(palabras)
        u, n2 = vocabulario.unificar(v)
        medir(f'+ vocabulario ({n1}) + unificar ({n2})', u, ref)
    if a.ia:                                                             # lo que hace GO después: IA de texto + ortografía (ia_texto.marcar_todo)
        import ia_texto
        finales, _roles, resumen = ia_texto.marcar_todo([dict(p) for p in u], a.idioma, con_emojis=False, quitar_signos=False)
        medir(f'+ IA de texto ({resumen.get("cambios")}, {resumen.get("modelo")})', finales, ref)
        ia_texto.liberar()


if __name__ == '__main__':
    main()
