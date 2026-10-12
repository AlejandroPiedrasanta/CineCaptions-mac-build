# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/resortes_motion.py — mete en el motor OGraf de la Edición PRO las curvas de resorte de Motion (motion.dev).
"""
Las piezas OGraf se dibujan fotograma a fotograma (goToTime) y tienen que ser deterministas: Motion no corre dentro de Resolve. Sus resortes
se calculan aquí una vez (herramientas_dev/generar_resortes.js, corrido con Node DESDE 6_compilacion/node_ograf, donde está
`npm install motion`) y se escriben como tablas
entre las marcas RESORTES:INICIO / RESORTES:FIN de 2_recursos/edicion_pro/ograf/lib/motor.js. En las piezas: S(t, t0, 'rebote') o
E.rebote(p) con P(t, t0, RESORTES.rebote.d, E.rebote).

    python 1_codigo/herramientas_dev/resortes_motion.py
"""
import json
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NODO = RAIZ / '6_compilacion' / 'node_ograf'
MOTOR = RAIZ / '2_recursos' / 'edicion_pro' / 'ograf' / 'lib' / 'motor.js'
INI, FIN = '/* RESORTES:INICIO (lo escribe 1_codigo/herramientas_dev/resortes_motion.py: no lo edites a mano) */', '/* RESORTES:FIN */'


def main():
    guion = (Path(__file__).with_name('generar_resortes.js')).read_text(encoding='utf-8')
    datos = json.loads(subprocess.run(['node', '-'], input=guion, cwd=NODO, capture_output=True, text=True, check=True).stdout)   # node - : require() busca en cwd
    lineas = [INI, '/* Resortes de Motion (motion.dev, MIT): tablas de 65 muestras de 0 a d segundos (lo que tarda en quedarse quieto). */',
              'export const RESORTES = {']
    for nombre, r in datos.items():
        lineas.append(f"  {nombre}: {{ d: {r['duracion']}, k: {r['stiffness']}, a: {r['damping']}, v: [{','.join(str(x) for x in r['tabla'])}] }},")
    lineas += ['};',
               'const _resorte = v => p => { if (p <= 0) return 0; if (p >= 1) return 1; const x = p * (v.length - 1), i = Math.floor(x); return v[i] + (v[i + 1] - v[i]) * (x - i); };',
               'for (const [n, r] of Object.entries(RESORTES)) E[n] = _resorte(r.v);',
               '/* progreso con resorte: S(t, t0, \'rebote\') (la duración es la del resorte; `vel` la acorta o alarga) */',
               'export const S = (t, t0, nombre = \'firme\', vel = 1) => { const r = RESORTES[nombre] || RESORTES.firme; return E[nombre in RESORTES ? nombre : \'firme\']((t - t0) / (r.d * vel)); };',
               FIN]
    bloque = '\n'.join(lineas)
    b = MOTOR.read_bytes().decode('utf-8')
    nl = '\r\n' if '\r\n' in b else '\n'
    s = b.replace('\r\n', '\n')
    if INI in s:
        a, z = s.index(INI), s.index(FIN) + len(FIN)
        s = s[:a] + bloque + s[z:]
    else:                                                   # la primera vez: justo después de P()
        ancla = 'export const P = (t, t0, d, e = E.out3) => e(clamp((t - t0) / Math.max(d, 1e-6)));\n'
        assert s.count(ancla) == 1
        s = s.replace(ancla, ancla + bloque + '\n')
    MOTOR.write_bytes(s.replace('\n', nl).encode('utf-8'))
    print('resortes:', ', '.join(f"{n} ({r['duracion']} s)" for n, r in datos.items()))


if __name__ == '__main__':
    main()
