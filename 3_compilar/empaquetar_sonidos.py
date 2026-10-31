# CineCaptions · By Cinema Productions
# 3_compilar/empaquetar_sonidos.py — copia a 2_recursos/biblioteca_sonido los sonidos de 5_SFX que GO puede poner (y su catálogo): viajan en el .exe.
"""v5.56 (el usuario: «los SFX ya deben de venir en el exe»): el sonido de GO (sonido_skill) buscaba la biblioteca del autor en 5_SFX o en
Desktop\\SFX; sin ellas (otro equipo, o el enlace del Escritorio roto) salían 0 sonidos y los de siempre se apagaban: el Tema 1 sin ningún SFX.

Aquí se arma la copia que viaja con el programa: los archivos de 01_SFX que pueden salir en un video (sonido_skill.pools_de: curados y de los
grupos de POOLS; ~66 archivos, ~13 MB) y catalogo_sfx.json con SOLO esas entradas. Sin la música (02_MUSICA) ni los videos de creadores: no
se pueden redistribuir. sonido_skill.biblioteca() la usa cuando no encuentra 5_SFX ni Desktop\\SFX.

    $PY 3_compilar/empaquetar_sonidos.py              # copia lo que cambió y quita lo que ya no se usa (solo dentro de biblioteca_sonido)
    $PY 3_compilar/empaquetar_sonidos.py --comprobar  # sale con 1 si la copia no está al día (no escribe nada)

Lo corre Construir_Instalador.ps1 antes de PyInstaller. Sin 5_SFX (la Mac en GitHub) no hace nada: queda la copia que ya está en Git."""
import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / '1_codigo'))
import sonido_skill as S

DESTINO = RAIZ / '2_recursos' / S.INCLUIDA
CATALOGO = 'catalogo_sfx.json'


def plan(lib=S.LIB_PROPIA):
    """(catálogo recortado, [rutas relativas]) de lo que debe ir en la copia."""
    cat = S.catalogo(lib)
    usados = sorted({r for v in S.pools_de(cat, lib).values() for r in v})
    return {r: cat[r] for r in usados}, usados


def _igual(a, b):
    return b.is_file() and a.stat().st_size == b.stat().st_size and int(a.stat().st_mtime) == int(b.stat().st_mtime)


def main():
    comprobar = '--comprobar' in sys.argv[1:]
    lib = S.LIB_PROPIA
    if not (lib / '01_SFX').is_dir():
        print(f'Sin {lib}: queda la copia que ya hay en {DESTINO}')
        return 0
    cat, usados = plan(lib)
    texto = json.dumps(cat, ensure_ascii=False, indent=1, sort_keys=True) + '\n'
    copiar = [r for r in usados if not _igual(lib / r, DESTINO / r)]
    sobran = [p for p in (DESTINO / '01_SFX').rglob('*') if p.is_file() and p.relative_to(DESTINO).as_posix() not in cat] \
        if (DESTINO / '01_SFX').is_dir() else []
    viejo = (DESTINO / CATALOGO).read_text(encoding='utf-8') if (DESTINO / CATALOGO).is_file() else ''
    if comprobar:
        al_dia = not copiar and not sobran and viejo == texto
        print('Sonidos del programa: al día' if al_dia else f'Sonidos del programa DESACTUALIZADOS: {len(copiar)} por copiar, {len(sobran)} sobran')
        return 0 if al_dia else 1
    for r in copiar:
        (DESTINO / r).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(lib / r, DESTINO / r)
    for p in sobran:
        p.unlink()
    for d in sorted((DESTINO / '01_SFX').rglob('*'), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    if viejo != texto:
        (DESTINO / CATALOGO).write_text(texto, encoding='utf-8', newline='\n')
    mb = sum((DESTINO / r).stat().st_size for r in usados) / 1e6
    print(f'Sonidos del programa: {len(usados)} archivos ({mb:.1f} MB) · {len(copiar)} copiados · {len(sobran)} quitados')
    return 0


if __name__ == '__main__':
    sys.exit(main())
