// CineCaptions · Edición PRO — «Velo»: oscurece el fondo (va DEBAJO de la persona recortada: ella queda nítida y el titular se lee).
import { PiezaPro, el, P, E, clamp, rgb } from './lib/motor.js';

export default class Velo extends PiezaPro {
  static DEFAULTS = { forma: 'arriba', color: '#000000', intensidad: 0.45, fundido: 0.5 };
  static SALIDA = 0.45;
  static FUENTES = [];
  static CSS = `.v{position:absolute;inset:0}`;

  construir(s) {
    const [r, g, b] = rgb(s.color), a = clamp(+s.intensidad || 0.45, 0, 1);
    const c = x => `rgba(${r},${g},${b},${(a * x).toFixed(3)})`;
    this.v = el('div', 'v', this._escena);
    this.v.style.background = s.forma === 'completo' ? c(1)
      : s.forma === 'abajo' ? `linear-gradient(0deg,${c(1)},${c(0.55)} 35%,${c(0)} 70%)`
      : s.forma === 'vineta' ? `radial-gradient(120% 90% at 50% 45%,${c(0.15)} 30%,${c(1)} 100%)`
      : `linear-gradient(180deg,${c(1)},${c(0.6)} 35%,${c(0.12)} 65%,${c(0)} 85%)`;
  }

  pintar(t, q, s) {
    if (this.v) this.v.style.opacity = (P(t, 0, Math.max(0.05, +s.fundido || 0.5), E.io3) * (1 - E.io3(q))).toFixed(3);
  }
}
