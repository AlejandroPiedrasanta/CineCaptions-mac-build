// CineCaptions · By Cinema Productions
// 1_codigo/herramientas_dev/generar_resortes.js — calcula con Motion (motion.dev, MIT; `npm install motion` en 6_compilacion/node_ograf) las curvas de resorte de las
// piezas OGraf de la Edición PRO y las imprime como JSON. Los OGraf se dibujan fotograma a fotograma (goToTime), así que no se usa Motion en
// tiempo real: sus resortes se guardan como TABLAS en 2_recursos/edicion_pro/ograf/lib/motor.js (lo hace 1_codigo/herramientas_dev/resortes_motion.py).
const { spring } = require('motion');

const PRESETS = {
  suave: { stiffness: 140, damping: 20, mass: 1 },     // entra y se asienta sin pasarse casi
  firme: { stiffness: 320, damping: 26, mass: 1 },     // rápido y seco (tarjetas, etiquetas)
  rebote: { stiffness: 210, damping: 13, mass: 1 },    // se pasa un poco y vuelve (iconos, cifras)
  elastico: { stiffness: 260, damping: 9, mass: 1 },   // dos rebotes (golpes de énfasis)
};
const MUESTRAS = 64;
const out = {};
for (const [nombre, p] of Object.entries(PRESETS)) {
  const g = spring({ keyframes: [0, 1], ...p });
  let fin = 0;
  for (let t = 0; t <= 4000; t += 1) {                  // dónde se queda quieto (±0,1 % durante 120 ms)
    let quieto = true;
    for (let k = 0; k <= 120; k += 10) if (Math.abs(g.next(t + k).value - 1) > 0.001) { quieto = false; break; }
    if (quieto) { fin = t; break; }
  }
  const tabla = [];
  for (let i = 0; i <= MUESTRAS; i++) tabla.push(+g.next((fin * i) / MUESTRAS).value.toFixed(4));
  tabla[MUESTRAS] = 1;
  out[nombre] = { duracion: +(fin / 1000).toFixed(3), tabla, ...p };
}
process.stdout.write(JSON.stringify(out));
